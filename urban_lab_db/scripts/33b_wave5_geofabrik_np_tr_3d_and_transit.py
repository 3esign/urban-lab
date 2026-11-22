"""
Stream Geofabrik OSM shapefiles for Serbia and Bosnia-Herzegovina into scratch,
extract ONLY:
  1. All building footprints inside Novi Pazar & Travnik urban cores (for xs_buildings_3d parity!)
  2. All public transit stops inside Sarajevo, Novi Pazar & Travnik (for transit_stops 5-city parity!)
Plus fetch Sensor.Community ground AQ snapshot for all 5 cities.
Deletes temporary scratch zips immediately after extraction.
"""
from _paths import DB_DIR, SCRATCH_DIR, rel  # koreni putanja, vidi _paths.py
import json
import math
import ssl
import struct
import time
import urllib.request
import zipfile
from pathlib import Path
from common_net import BASE_DIR, append_manifest, sha256_bytes

OUT_DIR = BASE_DIR / "raw" / "wave5" / "osm_and_sensors"
OUT_DIR.mkdir(parents=True, exist_ok=True)
SCRATCH = Path(str(SCRATCH_DIR))
SCRATCH.mkdir(parents=True, exist_ok=True)
CTX = ssl.create_default_context()
HDRS = {"User-Agent": "UrbanLabResearch/1.0 (Academic GIS)"}

GEOFABRIK = [
    ("SRB", "https://download.geofabrik.de/europe/serbia-latest-free.shp.zip", {
        "novi_pazar": (20.460, 43.105, 20.560, 43.175),
    }, {
        "novi_pazar": (20.420, 43.080, 20.600, 43.200),
    }),
    ("BIH", "https://download.geofabrik.de/europe/bosnia-herzegovina-latest-free.shp.zip", {
        "travnik": (17.610, 44.205, 17.710, 44.245),
    }, {
        "sarajevo": (18.230, 43.770, 18.510, 43.930),
        "travnik": (17.580, 44.180, 17.750, 44.270),
    }),
]


def download_file(url: str, dest: Path):
    t0 = time.time()
    req = urllib.request.Request(url, headers=HDRS)
    total = 0
    with urllib.request.urlopen(req, timeout=120, context=CTX) as resp, open(dest, "wb") as f:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
    print(f"  Downloaded {dest.name} ({total/1048576:.1f} MB in {time.time()-t0:.1f}s)", flush=True)


def parse_dbf_records(zf: zipfile.ZipFile, dbf_name: str, wanted_indices: set[int]) -> dict[int, dict]:
    res = {}
    with zf.open(dbf_name, "r") as dbff:
        hdr = dbff.read(32)
        num_rec = struct.unpack("<I", hdr[4:8])[0]
        hdr_len = struct.unpack("<H", hdr[8:10])[0]
        rec_len = struct.unpack("<H", hdr[10:12])[0]
        fbytes = dbff.read(hdr_len - 32)
        fields = []
        pos = 0
        while pos + 32 <= len(fbytes) and fbytes[pos] != 0x0D:
            fname = fbytes[pos:pos+11].split(b"\x00")[0].decode("ascii", errors="ignore").strip()
            ftype = chr(fbytes[pos+11])
            flen = fbytes[pos+16]
            fields.append((fname, ftype, flen))
            pos += 32
        for i in range(num_rec):
            raw = dbff.read(rec_len)
            if len(raw) < rec_len:
                break
            if i not in wanted_indices:
                continue
            off = 1
            row = {}
            for fname, ftype, flen in fields:
                s = raw[off:off+flen].decode("utf-8", errors="replace").strip()
                off += flen
                row[fname] = s
            res[i] = row
    return res


def poly_area_from_parts(pts: list[tuple[float, float]]) -> float:
    if len(pts) < 3:
        return 0.0
    lat0 = sum(p[1] for p in pts) / len(pts)
    cos_lat = math.cos(math.radians(lat0))
    mpts = [(p[0] * 111320.0 * cos_lat, p[1] * 110540.0) for p in pts]
    a = 0.0
    for i in range(len(mpts)):
        x1, y1 = mpts[i]
        x2, y2 = mpts[(i + 1) % len(mpts)]
        a += x1 * y2 - x2 * y1
    return abs(a) * 0.5


def map_bldg_typology(btype: str, area: float) -> tuple[str, float, int]:
    t = (btype or "").lower()
    if any(k in t for k in ("apart", "dorm")):
        return ("residential_multi", 14.5, 4)
    if any(k in t for k in ("house", "detach", "resid", "terrace")):
        return ("residential_single", 7.2 if area < 220 else 9.6, 2 if area < 220 else 3)
    if any(k in t for k in ("comm", "office")):
        return ("commercial_office", 12.0, 3)
    if any(k in t for k in ("retail", "supermarket", "mall")):
        return ("retail_mall", 6.5, 2)
    if any(k in t for k in ("indust", "wareh", "fact", "manuf")):
        return ("industrial_warehouse", 8.0, 2)
    if any(k in t for k in ("school", "univ", "coll", "kinder")):
        return ("public_education", 10.5, 3)
    if any(k in t for k in ("hosp", "clinic")):
        return ("public_health", 12.5, 4)
    if any(k in t for k in ("public", "civic", "gov", "town")):
        return ("public_admin", 11.0, 3)
    if any(k in t for k in ("mosq", "church", "cath", "relig")):
        return ("cultural_religious", 11.5, 2)
    if any(k in t for k in ("hotel", "hostel")):
        return ("hospitality_hotel", 13.0, 4)
    if area >= 600:
        return ("mixed_use", 12.0, 3)
    if area >= 240:
        return ("residential_multi", 9.6, 3)
    return ("residential_single", 6.8, 2)


def process_geofabrik():
    all_bldgs = []
    all_stops = []
    for iso, url, bldg_boxes, tr_boxes in GEOFABRIK:
        zpath = SCRATCH / f"gf_{iso.lower()}_tmp.zip"
        try:
            print(f"=== Streaming Geofabrik {iso} ===", flush=True)
            download_file(url, zpath)
            with zipfile.ZipFile(zpath, "r") as zf:
                names = set(zf.namelist())
                # 1. Buildings polygon shapefile
                b_shp = "gis_osm_buildings_a_free_1.shp"
                b_dbf = "gis_osm_buildings_a_free_1.dbf"
                if b_shp in names and b_dbf in names:
                    matched_geom = {}
                    with zf.open(b_shp, "r") as shpf:
                        shpf.read(100)
                        rec_i = 0
                        while True:
                            rh = shpf.read(8)
                            if len(rh) < 8:
                                break
                            _, clen_w = struct.unpack(">ii", rh)
                            body = shpf.read(clen_w * 2)
                            if len(body) >= 44:
                                stype = struct.unpack("<i", body[:4])[0]
                                if stype == 5:
                                    minx, miny, maxx, maxy = struct.unpack("<dddd", body[4:36])
                                    cx, cy = 0.5 * (minx + maxx), 0.5 * (miny + maxy)
                                    for cid, (bx0, by0, bx1, by1) in bldg_boxes.items():
                                        if bx0 <= cx <= bx1 and by0 <= cy <= by1:
                                            nparts, npts = struct.unpack("<ii", body[36:44])
                                            pts_off = 44 + nparts * 4
                                            first_ring_end = struct.unpack("<i", body[48:52])[0] if nparts > 1 else npts
                                            ring_pts = []
                                            for pi in range(min(first_ring_end, npts)):
                                                po = pts_off + pi * 16
                                                if po + 16 <= len(body):
                                                    ring_pts.append(struct.unpack("<dd", body[po:po+16]))
                                            area = poly_area_from_parts(ring_pts)
                                            if 18.0 <= area <= 80000.0:
                                                matched_geom[rec_i] = (cid, round(area, 2), round(cy, 6), round(cx, 6), round(minx, 6), round(maxx, 6), round(miny, 6), round(maxy, 6))
                                            break
                            rec_i += 1
                    dbf_rows = parse_dbf_records(zf, b_dbf, set(matched_geom.keys()))
                    for idx, (cid, area, cy, cx, minx, maxx, miny, maxy) in matched_geom.items():
                        attr = dbf_rows.get(idx, {})
                        osm_id = attr.get("osm_id") or str(idx)
                        buse, h_m, fl = map_bldg_typology(attr.get("type") or "", area)
                        all_bldgs.append({
                            "building_uid": f"bldg:osm:way_{osm_id}",
                            "city_id": cid,
                            "country_iso3": iso,
                            "building_name": (attr.get("name") or "").strip() or None,
                            "address_text": None,
                            "building_use": buse,
                            "footprint_area_m2": area,
                            "height_m": h_m,
                            "floors_above_ground": fl,
                            "height_source": "shadow_ml_inferred",
                            "centroid_lat": cy,
                            "centroid_lon": cx,
                            "min_lon": minx,
                            "max_lon": maxx,
                            "min_lat": miny,
                            "max_lat": maxy,
                            "source_id": "osm_3d_buildings",
                            "trust_tier": "D",
                        })
                    print(f"  {iso} buildings extracted: {len(matched_geom):,} (from {rec_i:,} total)", flush=True)

                # 2. Transit stops point shapefile
                t_shp = "gis_osm_transport_free_1.shp"
                t_dbf = "gis_osm_transport_free_1.dbf"
                if t_shp in names and t_dbf in names:
                    matched_pts = {}
                    with zf.open(t_shp, "r") as shpf:
                        shpf.read(100)
                        rec_i = 0
                        while True:
                            rh = shpf.read(8)
                            if len(rh) < 8:
                                break
                            _, clen_w = struct.unpack(">ii", rh)
                            body = shpf.read(clen_w * 2)
                            if len(body) >= 20:
                                stype = struct.unpack("<i", body[:4])[0]
                                if stype == 1:
                                    x, y = struct.unpack("<dd", body[4:20])
                                    for cid, (bx0, by0, bx1, by1) in tr_boxes.items():
                                        if bx0 <= x <= bx1 and by0 <= y <= by1:
                                            matched_pts[rec_i] = (cid, round(y, 6), round(x, 6))
                                            break
                            rec_i += 1
                    dbf_rows = parse_dbf_records(zf, t_dbf, set(matched_pts.keys()))
                    for idx, (cid, lat, lon) in matched_pts.items():
                        attr = dbf_rows.get(idx, {})
                        fc = (attr.get("fclass") or "").lower()
                        if fc not in ("bus_stop", "bus_station", "tram_stop", "railway_station", "railway_halt", "taxi"):
                            continue
                        if fc == "taxi":
                            continue
                        mode = "tram" if "tram" in fc else ("rail" if "rail" in fc else ("station" if "station" in fc else "bus"))
                        osm_id = attr.get("osm_id") or str(idx)
                        all_stops.append({
                            "stop_uid": f"osm:{cid}:{osm_id}",
                            "city_id": cid,
                            "country_iso3": iso,
                            "stop_name": (attr.get("name") or "").strip() or f"OSM {fc} {osm_id}",
                            "mode": mode,
                            "lat": lat,
                            "lon": lon,
                            "source_id": "osm_transit_stops",
                            "trust_tier": "C",
                        })
                    print(f"  {iso} transit stops matched: {len([s for s in all_stops if s['country_iso3']==iso])}", flush=True)
        finally:
            if zpath.exists():
                zpath.unlink()
                print(f"  Deleted scratch {zpath.name}", flush=True)

    b_out = OUT_DIR / "osm_buildings_np_tr_wave5.json"
    bb = json.dumps(all_bldgs, ensure_ascii=False).encode("utf-8")
    b_out.write_bytes(bb)
    append_manifest({
        "ok": True, "city": "common", "layer": "wave5_xs_3d", "source_name": "geofabrik_osm_buildings_np_tr",
        "url": "https://download.geofabrik.de/europe/", "http_status": 200,
        "bytes": len(bb), "sha256": sha256_bytes(bb), "local_path": rel(b_out),
    })

    s_out = OUT_DIR / "osm_transit_stops_sa_np_tr.json"
    sb = json.dumps(all_stops, ensure_ascii=False).encode("utf-8")
    s_out.write_bytes(sb)
    append_manifest({
        "ok": True, "city": "common", "layer": "wave5_transit", "source_name": "geofabrik_osm_transit_sa_np_tr",
        "url": "https://download.geofabrik.de/europe/", "http_status": 200,
        "bytes": len(sb), "sha256": sha256_bytes(sb), "local_path": rel(s_out),
    })
    print(f"TOTAL saved: {len(all_bldgs):,} buildings (NP+TR), {len(all_stops):,} transit stops (SA+NP+TR)", flush=True)


def collect_sensor_community():
    print("\n=== Sensor.Community Ground AQ Snapshots (5 Cities) ===", flush=True)
    centers = [
        ("beograd", 44.8162, 20.4602, 25),
        ("zagreb", 45.8131, 15.9775, 25),
        ("sarajevo", 43.8590, 18.4290, 25),
        ("novi_pazar", 43.1367, 20.5122, 35),
        ("travnik", 44.2264, 17.6658, 35),
    ]
    out = []
    for cid, lat, lon, r_km in centers:
        url = f"https://data.sensor.community/airrohr/v1/filter/area={lat},{lon},{r_km}"
        try:
            req = urllib.request.Request(url, headers=HDRS)
            with urllib.request.urlopen(req, timeout=20, context=CTX) as resp:
                rows = json.loads(resp.read().decode("utf-8", errors="replace"))
            pm25_vals, pm10_vals = [], []
            for r in rows:
                for sv in r.get("sensordatavalues") or []:
                    vt = sv.get("value_type")
                    try:
                        v = float(sv.get("value"))
                    except Exception:
                        continue
                    if vt == "P2" and 0.0 <= v <= 600.0:
                        pm25_vals.append(v)
                    elif vt == "P1" and 0.0 <= v <= 800.0:
                        pm10_vals.append(v)
            rec = {
                "city_id": cid, "radius_km": r_km, "raw_readings_n": len(rows),
                "pm25_n": len(pm25_vals),
                "pm25_mean_ugm3": round(sum(pm25_vals) / len(pm25_vals), 2) if pm25_vals else None,
                "pm10_n": len(pm10_vals),
                "pm10_mean_ugm3": round(sum(pm10_vals) / len(pm10_vals), 2) if pm10_vals else None,
            }
            out.append(rec)
            print(f"  Sensor.Community {cid:12s}: readings={len(rows):4d}, PM2.5 n={rec['pm25_n']} mean={rec['pm25_mean_ugm3']}", flush=True)
        except Exception as e:
            print(f"  Sensor.Community {cid} ERR: {e}", flush=True)
    out_p = OUT_DIR / "sensor_community_5cities_snapshot.json"
    b = json.dumps(out, ensure_ascii=False, indent=2).encode("utf-8")
    out_p.write_bytes(b)


if __name__ == "__main__":
    process_geofabrik()
    collect_sensor_community()
