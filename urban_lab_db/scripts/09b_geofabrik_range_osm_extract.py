from _paths import DB_DIR, SCRATCH_DIR, rel  # koreni putanja, vidi _paths.py
import io, os, sys, json, struct, zlib, time, hashlib, urllib.request
from collections import Counter
from pathlib import Path

BASE = Path(str(DB_DIR))
OUT = BASE / "raw" / "wave2_osm"
OUT.mkdir(parents=True, exist_ok=True)
MANIFEST = BASE / "manifest.jsonl"

COUNTRY_CITIES = {
    "bosnia-herzegovina": {
        "sarajevo": (18.00, 43.65, 18.75, 44.12),
        "travnik":  (17.35, 44.08, 18.05, 44.45),
    },
    "croatia": {
        "zagreb":   (15.60, 45.58, 16.45, 46.02),
    },
    "serbia": {
        "novi_pazar": (20.00, 42.90, 20.80, 43.40),
        "beograd":    (19.95, 44.30, 20.90, 45.12),
    },
}

def http_range(url, start, end):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SvemirUrbanLab/2.0", "Range": f"bytes={start}-{end}"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()

def parse_zip_central_dir(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "SvemirUrbanLab/2.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        total_len = int(resp.headers["Content-Length"])
        accept_ranges = resp.headers.get("Accept-Ranges", "")
    print(f"  ZIP size={total_len/(1024*1024):.1f} MB, Accept-Ranges={accept_ranges}", flush=True)
    tail_len = min(65536, total_len)
    tail = http_range(url, total_len - tail_len, total_len - 1)
    idx = tail.rfind(b"PK\x05\x06")
    if idx < 0:
        raise RuntimeError("EOCD not found")
    _, _, _, _, total_entries, cd_size, cd_offset, _ = struct.unpack_from("<4sHHHHIIH", tail, idx)
    cd = http_range(url, cd_offset, cd_offset + cd_size - 1)
    entries = {}
    pos = 0
    while pos < len(cd):
        if cd[pos:pos+4] != b"PK\x01\x02":
            break
        (_, _, _, _, comp_method, _, _, _, comp_size, uncomp_size, fname_len, extra_len, comm_len, _, _, _, local_off) = struct.unpack_from("<4sHHHHHHIIIHHHHHII", cd, pos)
        fname = cd[pos+46:pos+46+fname_len].decode("utf-8", errors="replace")
        entries[fname] = (comp_method, comp_size, uncomp_size, local_off)
        pos += 46 + fname_len + extra_len + comm_len
    return entries

def fetch_zip_member(url, entry):
    comp_method, comp_size, uncomp_size, local_off = entry
    hdr = http_range(url, local_off, local_off + 29)
    _, _, _, _, _, _, _, _, _, fn_len, ex_len = struct.unpack_from("<4sHHHHHIIIHH", hdr, 0)
    data_start = local_off + 30 + fn_len + ex_len
    comp_data = http_range(url, data_start, data_start + comp_size - 1)
    if comp_method == 0:
        return comp_data
    elif comp_method == 8:
        return zlib.decompress(comp_data, -15)
    raise RuntimeError(f"Unsupported ZIP method {comp_method}")

def iter_shp_dbf(shp_bytes, dbf_bytes):
    # Pure-Python streaming ESRI Shapefile + DBF reader (Point=1, Polygon=5, Polyline=3)
    # Parse DBF header
    num_rec, hdr_len, rec_len = struct.unpack_from("<IHH", dbf_bytes, 4)
    fields = []
    pos = 32
    while pos < hdr_len - 1 and dbf_bytes[pos] != 0x0D:
        name = dbf_bytes[pos:pos+11].split(b"\x00", 1)[0].decode("ascii", errors="replace")
        ftype = chr(dbf_bytes[pos+11])
        flen = dbf_bytes[pos+16]
        fields.append((name, ftype, flen))
        pos += 32

    shp_pos = 100
    shp_len = len(shp_bytes)
    dbf_pos = hdr_len
    rec_idx = 0
    while shp_pos + 8 <= shp_len and rec_idx < num_rec:
        _rnum, content_words = struct.unpack_from(">II", shp_bytes, shp_pos)
        shp_pos += 8
        content_bytes = content_words * 2
        if shp_pos + content_bytes > shp_len:
            break
        stype = struct.unpack_from("<I", shp_bytes, shp_pos)[0]
        lon = lat = None
        if stype == 1 and content_bytes >= 20:
            lon, lat = struct.unpack_from("<dd", shp_bytes, shp_pos + 4)
        elif stype in (3, 5, 8, 13, 15, 23, 25) and content_bytes >= 36:
            xmin, ymin, xmax, ymax = struct.unpack_from("<dddd", shp_bytes, shp_pos + 4)
            lon, lat = (xmin + xmax) / 2.0, (ymin + ymax) / 2.0
        shp_pos += content_bytes

        # Read corresponding DBF record
        drec_raw = dbf_bytes[dbf_pos:dbf_pos+rec_len]
        dbf_pos += rec_len
        rec_idx += 1
        if lon is None or not drec_raw or drec_raw[0] == 0x2A:
            continue
        yield lon, lat, drec_raw, fields

def decode_dbf_record(drec_raw, fields):
    out = {}
    p = 1
    for name, ftype, flen in fields:
        val = drec_raw[p:p+flen].decode("utf-8", errors="replace").strip()
        p += flen
        if ftype == "N":
            try: val = int(val) if "." not in val else float(val)
            except: pass
        out[name] = val
    return out

def extract_country(country, city_bboxes):
    url = f"https://download.geofabrik.de/europe/{country}-latest-free.shp.zip"
    print(f"\n=== GEOFABRIK RANGE EXTRACT: {country} ===", flush=True)
    entries = parse_zip_central_dir(url)
    city_items = {cid: [] for cid in city_bboxes}

    for layer_base in ["gis_osm_pois_free_1", "gis_osm_pois_a_free_1", "gis_osm_transport_free_1"]:
        if f"{layer_base}.shp" not in entries or f"{layer_base}.dbf" not in entries:
            print(f"  [SKIP] {layer_base} not found")
            continue
        shp_e = entries[f"{layer_base}.shp"]
        dbf_e = entries[f"{layer_base}.dbf"]
        mb = (shp_e[1] + dbf_e[1]) / (1024*1024)
        print(f"  Fetching {layer_base} ({mb:.2f} MB compressed)...", flush=True)
        shp_b = fetch_zip_member(url, shp_e)
        dbf_b = fetch_zip_member(url, dbf_e)

        layer_tag = "transport" if "transport" in layer_base else ("poi_area" if "_a_" in layer_base else "poi_pt")
        kept = 0
        for lon, lat, drec_raw, fields in iter_shp_dbf(shp_b, dbf_b):
            for cid, (x0, y0, x1, y1) in city_bboxes.items():
                if x0 <= lon <= x1 and y0 <= lat <= y1:
                    rec = decode_dbf_record(drec_raw, fields)
                    city_items[cid].append({
                        "osm_id": str(rec.get("osm_id", "")),
                        "code": rec.get("code"),
                        "fclass": str(rec.get("fclass", "")),
                        "name": str(rec.get("name", "") or "").strip(),
                        "layer": layer_tag,
                        "lon": round(lon, 6),
                        "lat": round(lat, 6),
                    })
                    kept += 1
        print(f"    -> extracted {kept:,} features across {list(city_bboxes.keys())}", flush=True)
        del shp_b, dbf_b

    for cid, rows in city_items.items():
        out_p = OUT / f"geofabrik_osm_pois_{cid}.json"
        payload = json.dumps({"source": url, "city": cid, "bbox": city_bboxes[cid], "count": len(rows), "items": rows}, ensure_ascii=False)
        out_p.write_text(payload, encoding="utf-8")
        fc = Counter(r["fclass"] for r in rows)
        print(f"  [SAVED] {out_p.name}: {len(rows):,} POIs ({out_p.stat().st_size:,} B) | bakery={fc.get('bakery',0)} market={fc.get('marketplace',0)} supermkt={fc.get('supermarket',0)} bank={fc.get('bank',0)} cafe={fc.get('cafe',0)} rail={fc.get('railway_station',0)}", flush=True)
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "ok": True, "city": cid, "layer": "osm_geofabrik_pois_transport",
            "source_name": f"Geofabrik OSM POIs + Transport ({country} -> {cid} core+hinterland: {len(rows)} features)",
            "url": url, "http_status": 206, "bytes": out_p.stat().st_size,
            "sha256": hashlib.sha256(out_p.read_bytes()).hexdigest(),
            "local_path": rel(out_p),
        }
        with open(MANIFEST, "a", encoding="utf-8") as mf:
            mf.write(json.dumps(rec, ensure_ascii=False) + "\n")

for country, bboxes in COUNTRY_CITIES.items():
    extract_country(country, bboxes)

print("\nDONE 09b_geofabrik_range_osm_extract.py", flush=True)
