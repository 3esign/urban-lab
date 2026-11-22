from _paths import DB_DIR, SCRATCH_DIR, rel  # koreni putanja, vidi _paths.py
import gc, hashlib, json, math, os, struct, sys, time, urllib.request, zlib
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(str(DB_DIR))
OUT = BASE / "raw" / "wave3_osm"
OUT.mkdir(parents=True, exist_ok=True)
MANIFEST = BASE / "manifest.jsonl"

CBD = {
    "beograd":    (20.4612, 44.8125),
    "zagreb":     (15.9772, 45.8130),
    "sarajevo":   (18.4131, 43.8563),
    "novi_pazar": (20.5122, 43.1367),
    "travnik":    (17.6658, 44.2264),
}

# Core + L-ring bboxes (slightly wider than Wave 2 POIs to include Pančevo & full L hinterlands)
COUNTRY_CITIES = {
    "serbia": {
        "beograd":    (19.90, 44.30, 21.00, 45.12),
        "novi_pazar": (20.00, 42.90, 20.80, 43.40),
    },
    "croatia": {
        "zagreb":     (15.55, 45.55, 16.50, 46.05),
    },
    "bosnia-herzegovina": {
        "sarajevo":   (18.00, 43.65, 18.75, 44.15),
        "travnik":    (17.35, 44.05, 18.05, 44.45),
    },
}

MACRO_MAP = {
    "forest": "forest",
    "wood": "forest",
    "farmland": "agriculture",
    "farmyard": "agriculture",
    "orchard": "agriculture",
    "vineyard": "agriculture",
    "meadow": "agriculture",
    "allotments": "agriculture",
    "industrial": "industrial",
    "commercial": "commercial_retail",
    "retail": "commercial_retail",
    "residential": "residential",
    "quarry": "extraction_quarry",
    "park": "urban_green",
    "recreation_ground": "urban_green",
    "grass": "urban_green",
    "scrub": "nature_scrub",
    "heath": "nature_scrub",
    "cemetery": "civic_other",
    "military": "civic_other",
    "nature_reserve": "urban_green",
}

# Minimum polygon area (km2) to include in simplified GeoJSON output
MIN_GEOJSON_KM2 = {
    "industrial": 0.005,
    "commercial_retail": 0.005,
    "extraction_quarry": 0.01,
    "forest": 0.08,
    "agriculture": 0.08,
    "residential": 0.12,
}

def haversine_km(lon1, lat1, lon2, lat2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))

def dist_ring(km):
    if km < 1.0: return "0-1 km (CBD)"
    if km < 3.0: return "1-3 km (Inner)"
    if km < 6.0: return "3-6 km (Urban)"
    if km < 15.0: return "6-15 km (Suburban)"
    return "15+ km (Hinterland)"

def ring_area_km2(pts, cos_lat):
    # Shoelace formula in km2 using local equirectangular scaling
    n = len(pts)
    if n < 3: return 0.0
    s = 0.0
    for i in range(n - 1):
        s += pts[i][0] * pts[i+1][1] - pts[i+1][0] * pts[i][1]
    deg2 = abs(s) * 0.5
    km_per_deg_lat = 111.132
    km_per_deg_lon = 111.320 * cos_lat
    return deg2 * km_per_deg_lat * km_per_deg_lon

def simplify_ring(pts, tol=0.00035, max_pts=70):
    # Fast vertex decimation + Ramer-Douglas-Peucker
    n = len(pts)
    if n <= 6:
        return [[round(x, 5), round(y, 5)] for x, y in pts]
    # Pre-stride if huge (>500 vertices)
    if n > 500:
        step = max(1, n // 250)
        pts = pts[::step]
        if pts[-1] != pts[0]:
            pts = list(pts) + [pts[0]]
    # Iterative RDP on open ring
    def rdp(arr, eps):
        if len(arr) < 3:
            return arr
        stack = [(0, len(arr) - 1)]
        keep = [False] * len(arr)
        keep[0] = keep[-1] = True
        eps2 = eps * eps
        while stack:
            a, b = stack.pop()
            if b - a <= 1:
                continue
            ax, ay = arr[a]
            bx, by = arr[b]
            dx, dy = bx - ax, by - ay
            l2 = dx*dx + dy*dy
            max_d2 = -1.0
            idx = -1
            for i in range(a + 1, b):
                px, py = arr[i]
                if l2 == 0.0:
                    d2 = (px - ax)**2 + (py - ay)**2
                else:
                    t = max(0.0, min(1.0, ((px - ax)*dx + (py - ay)*dy) / l2))
                    projx = ax + t * dx
                    projy = ay + t * dy
                    d2 = (px - projx)**2 + (py - projy)**2
                if d2 > max_d2:
                    max_d2 = d2
                    idx = i
            if max_d2 > eps2 and idx != -1:
                keep[idx] = True
                stack.append((a, idx))
                stack.append((idx, b))
        return [arr[i] for i in range(len(arr)) if keep[i]]

    closed = (pts[0] == pts[-1])
    base = pts[:-1] if closed else pts
    # Split closed ring into two halves to preserve shape under RDP
    mid = len(base) // 2
    res = rdp(base[:mid+1], tol)[:-1] + rdp(base[mid:] + [base[0]], tol)
    if len(res) > max_pts:
        res = rdp(base[:mid+1], tol * 2.2)[:-1] + rdp(base[mid:] + [base[0]], tol * 2.2)
    if len(res) < 4:
        res = [base[0], base[len(base)//3], base[(2*len(base))//3], base[0]]
    if res[0] != res[-1]:
        res.append(res[0])
    return [[round(x, 5), round(y, 5)] for x, y in res]

def http_range_bytes(url, start, end):
    req = urllib.request.Request(url, headers={"User-Agent": "SvemirUrbanLab/3.0", "Range": f"bytes={start}-{end}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()

def parse_zip_cd(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "SvemirUrbanLab/3.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        total_len = int(resp.headers["Content-Length"])
    tail_len = min(65536, total_len)
    tail = http_range_bytes(url, total_len - tail_len, total_len - 1)
    idx = tail.rfind(b"PK\x05\x06")
    _, _, _, _, total_entries, cd_size, cd_offset, _ = struct.unpack_from("<4sHHHHIIH", tail, idx)
    cd = http_range_bytes(url, cd_offset, cd_offset + cd_size - 1)
    entries = {}
    pos = 0
    while pos < len(cd):
        if cd[pos:pos+4] != b"PK\x01\x02": break
        (_, _, _, _, cm, _, _, _, csize, usize, fnl, exl, cml, _, _, _, loff) = struct.unpack_from("<4sHHHHHHIIIHHHHHII", cd, pos)
        fn = cd[pos+46:pos+46+fnl].decode("utf-8", errors="replace")
        entries[fn] = (cm, csize, usize, loff)
        pos += 46 + fnl + exl + cml
    return entries

def get_member_data_range(url, entry):
    cm, csize, usize, loff = entry
    hdr = http_range_bytes(url, loff, loff + 29)
    _, _, _, _, _, _, _, _, _, fnl, exl = struct.unpack_from("<4sHHHHHIIIHH", hdr, 0)
    data_start = loff + 30 + fnl + exl
    return cm, data_start, csize, usize

def stream_member_to_file(url, entry, dest_path):
    cm, data_start, csize, usize = get_member_data_range(url, entry)
    req = urllib.request.Request(url, headers={"User-Agent": "SvemirUrbanLab/3.0", "Range": f"bytes={data_start}-{data_start+csize-1}"})
    decomp = zlib.decompressobj(-15) if cm == 8 else None
    with urllib.request.urlopen(req, timeout=180) as resp, open(dest_path, "wb") as out_f:
        while True:
            chunk = resp.read(65536)
            if not chunk: break
            out_f.write(decomp.decompress(chunk) if decomp else chunk)
        if decomp:
            out_f.write(decomp.flush())

def decode_dbf_fields(dbf_f):
    hdr = dbf_f.read(32)
    num_rec, hdr_len, rec_len = struct.unpack_from("<IHH", hdr, 4)
    fields = []
    pos = 32
    while pos < hdr_len - 1:
        fd = dbf_f.read(32)
        if not fd or fd[0] == 0x0D:
            break
        name = fd[:11].split(b"\x00", 1)[0].decode("ascii", errors="replace")
        ftype = chr(fd[11])
        flen = fd[16]
        fields.append((name, ftype, flen))
        pos += 32
    dbf_f.seek(hdr_len)
    return num_rec, rec_len, fields

def parse_dbf_row(raw, fields):
    out = {}
    p = 1
    for name, ftype, flen in fields:
        out[name] = raw[p:p+flen].decode("utf-8", errors="replace").strip()
        p += flen
    return out

def process_country(country, city_bboxes):
    t0 = time.time()
    url = f"https://download.geofabrik.de/europe/{country}-latest-free.shp.zip"
    print(f"\n=== STREAMING GEOFABRIK LANDUSE: {country} ===", flush=True)
    entries = parse_zip_cd(url)
    shp_e = entries["gis_osm_landuse_a_free_1.shp"]
    dbf_e = entries["gis_osm_landuse_a_free_1.dbf"]
    print(f"  SHP={shp_e[1]/1048576:.1f} MB comp ({shp_e[2]/1048576:.1f} MB uncomp), DBF={dbf_e[1]/1048576:.2f} MB comp", flush=True)

    tmp_dbf = OUT / f"_tmp_{country}_landuse.dbf"
    stream_member_to_file(url, dbf_e, tmp_dbf)

    # Stats & feature containers per city
    city_stats = {cid: defaultdict(lambda: {"count": 0, "area_km2": 0.0}) for cid in city_bboxes}
    city_feats = {cid: [] for cid in city_bboxes}
    city_totals = Counter()

    cm, data_start, csize, usize = get_member_data_range(url, shp_e)
    req = urllib.request.Request(url, headers={"User-Agent": "SvemirUrbanLab/3.0", "Range": f"bytes={data_start}-{data_start+csize-1}"})
    decomp = zlib.decompressobj(-15) if cm == 8 else None

    with open(tmp_dbf, "rb") as dbf_f, urllib.request.urlopen(req, timeout=300) as resp:
        num_rec, rec_len, fields = decode_dbf_fields(dbf_f)
        print(f"  DBF records={num_rec:,}, rec_len={rec_len}, streaming SHP...", flush=True)

        buf = bytearray()
        eof = False

        def ensure(n_bytes):
            nonlocal eof
            while len(buf) < n_bytes and not eof:
                chunk = resp.read(131072)
                if not chunk:
                    eof = True
                    if decomp:
                        tail = decomp.flush()
                        if tail: buf.extend(tail)
                    break
                data = decomp.decompress(chunk) if decomp else chunk
                if data:
                    buf.extend(data)
            return len(buf) >= n_bytes

        # Skip 100-byte SHP file header
        if not ensure(100):
            raise RuntimeError("Truncated SHP header")
        del buf[:100]

        rec_idx = 0
        while rec_idx < num_rec:
            if not ensure(8):
                break
            _rnum, content_words = struct.unpack_from(">II", buf, 0)
            content_bytes = content_words * 2
            if not ensure(8 + content_bytes):
                break
            drec = dbf_f.read(rec_len)
            rec_idx += 1

            # Extract shape type and bbox
            stype = struct.unpack_from("<I", buf, 8)[0]
            if stype == 5 and content_bytes >= 44 and drec and drec[0] != 0x2A:
                xmin, ymin, xmax, ymax = struct.unpack_from("<dddd", buf, 12)
                # Quick bbox hit check across cities in this country
                hits = [cid for cid, (bx0, by0, bx1, by1) in city_bboxes.items()
                        if xmax >= bx0 and xmin <= bx1 and ymax >= by0 and ymin <= by1]
                if hits:
                    d = parse_dbf_row(drec, fields)
                    fclass = d.get("fclass", "")
                    macro = MACRO_MAP.get(fclass, "other")
                    name = d.get("name", "")
                    osm_id = d.get("osm_id", "")

                    num_parts, num_pts = struct.unpack_from("<II", buf, 44)
                    parts_off = 52
                    pts_off = 52 + num_parts * 4
                    if pts_off + num_pts * 16 <= 8 + content_bytes and num_parts >= 1 and num_pts >= 4:
                        parts = list(struct.unpack_from(f"<{num_parts}I", buf, parts_off))
                        parts.append(num_pts)
                        clat = (ymin + ymax) * 0.5
                        clon = (xmin + xmax) * 0.5
                        cos_lat = math.cos(math.radians(clat))

                        # Compute area from parts (outer ring positive, holes/extra rings approx)
                        outer_pts = []
                        total_area_km2 = 0.0
                        for pi in range(num_parts):
                            p0, p1 = parts[pi], parts[pi+1]
                            cnt_p = p1 - p0
                            if cnt_p < 3: continue
                            coords = list(struct.iter_unpack("<dd", memoryview(buf)[pts_off + p0*16 : pts_off + p1*16]))
                            # Signed area determines CW (outer in ESRI) vs CCW (hole in ESRI)
                            s = 0.0
                            for k in range(len(coords) - 1):
                                s += coords[k][0] * coords[k+1][1] - coords[k+1][0] * coords[k][1]
                            area_part = abs(s) * 0.5 * 111.132 * (111.320 * cos_lat)
                            # In ESRI shapefile, outer rings are clockwise (s < 0), holes are CCW (s > 0)
                            if pi == 0 or s < 0:
                                total_area_km2 += area_part
                                if pi == 0:
                                    outer_pts = coords
                            else:
                                total_area_km2 = max(0.0, total_area_km2 - area_part)

                        if total_area_km2 <= 0.0 and outer_pts:
                            total_area_km2 = ring_area_km2(outer_pts, cos_lat)

                        for cid in hits:
                            cx, cy = CBD[cid]
                            dkm = haversine_km(clon, clat, cx, cy)
                            rng = dist_ring(dkm)
                            st = city_stats[cid][(rng, macro, fclass)]
                            st["count"] += 1
                            st["area_km2"] += total_area_km2
                            city_totals[cid] += 1

                            min_a = MIN_GEOJSON_KM2.get(macro)
                            if min_a is not None and total_area_km2 >= min_a and outer_pts:
                                simp = simplify_ring(outer_pts, tol=0.0004 if total_area_km2 >= 0.2 else 0.00025)
                                city_feats[cid].append({
                                    "type": "Feature",
                                    "properties": {
                                        "city_id": cid,
                                        "osm_id": osm_id,
                                        "fclass": fclass,
                                        "macro_group": macro,
                                        "name": name,
                                        "area_km2": round(total_area_km2, 4),
                                        "area_ha": round(total_area_km2 * 100.0, 2),
                                        "dist_cbd_km": round(dkm, 2),
                                        "ring": rng,
                                        "lon": round(clon, 5),
                                        "lat": round(clat, 5),
                                    },
                                    "geometry": {"type": "Polygon", "coordinates": [simp]},
                                })

            del buf[:8 + content_bytes]
            if rec_idx % 100000 == 0:
                print(f"    ... processed {rec_idx:,}/{num_rec:,} polygons ({time.time()-t0:.1f}s)", flush=True)

    try:
        tmp_dbf.unlink()
    except Exception:
        pass

    for cid in city_bboxes:
        # Save summary JSON
        sum_rows = []
        macro_area = Counter()
        for (rng, macro, fclass), st in sorted(city_stats[cid].items()):
            sum_rows.append({
                "city_id": cid, "ring": rng, "macro_group": macro, "fclass": fclass,
                "polygon_count": st["count"], "area_km2": round(st["area_km2"], 4), "area_ha": round(st["area_km2"]*100.0, 2)
            })
            macro_area[macro] += st["area_km2"]

        sum_p = OUT / f"geofabrik_landuse_summary_{cid}.json"
        sum_p.write_text(json.dumps({
            "source": url, "city_id": cid, "bbox": city_bboxes[cid],
            "total_polygons_counted": city_totals[cid],
            "macro_area_km2": {k: round(v, 2) for k, v in macro_area.most_common()},
            "by_ring_and_fclass": sum_rows,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        # Save per-city GeoJSON of major economic/landuse polygons
        gj_p = OUT / f"geofabrik_landuse_{cid}.geojson"
        # Keep top features sorted by area descending (cap at 2500 per city to stay fast)
        feats = sorted(city_feats[cid], key=lambda f: -f["properties"]["area_km2"])[:2500]
        gj_p.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False), encoding="utf-8")

        print(f"  [SAVED] {cid:11s}: counted={city_totals[cid]:>7,} polys | geojson={len(feats):>4} ({gj_p.stat().st_size/1024:.0f} KB) | forest={macro_area['forest']:.1f} km2, agri={macro_area['agriculture']:.1f} km2, ind={macro_area['industrial']:.1f} km2, comm={macro_area['commercial_retail']:.1f} km2", flush=True)

        for p, layer_tag, desc in [
            (sum_p, "osm_geofabrik_landuse_summary", f"Geofabrik OSM Landuse Summary ({country}->{cid}: {city_totals[cid]} polygons)"),
            (gj_p, "osm_geofabrik_landuse_geojson", f"Geofabrik OSM Landuse Polygons GeoJSON ({country}->{cid}: {len(feats)} major polygons)"),
        ]:
            rec = {
                "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "ok": True, "city": cid, "layer": layer_tag, "source_name": desc,
                "url": url, "http_status": 206, "bytes": p.stat().st_size,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "local_path": rel(p),
            }
            with open(MANIFEST, "a", encoding="utf-8") as mf:
                mf.write(json.dumps(rec, ensure_ascii=False) + "\n")

    gc.collect()
    print(f"  Done {country} in {time.time()-t0:.1f}s", flush=True)

if __name__ == "__main__":
    for country, bboxes in COUNTRY_CITIES.items():
        process_country(country, bboxes)
    print("\nDONE 16_collect_wave3_geofabrik_landuse_stream.py", flush=True)
