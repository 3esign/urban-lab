"""
Stream-download Ookla Open Data 2025 Q4 Fixed Broadband Shapefile ZIP into scratch,
extract ONLY 610m tiles inside the 5 Urban Lab cities' bounding boxes using pure Python
(zero geopandas/pyarrow dependency), write compact JSON to raw/wave5/ookla/, and
immediately delete the 251 MB temporary zip so disk stays clean.
"""
from _paths import DB_DIR, SCRATCH_DIR, rel  # koreni putanja, vidi _paths.py
import io
import json
import os
import ssl
import struct
import time
import urllib.request
import zipfile
from pathlib import Path
from common_net import BASE_DIR, append_manifest, sha256_bytes

OUT_DIR = BASE_DIR / "raw" / "wave5" / "ookla"
OUT_DIR.mkdir(parents=True, exist_ok=True)
SCRATCH_ZIP = Path(str(SCRATCH_DIR / "ookla_fixed_2025q4_tmp.zip"))
SCRATCH_ZIP.parent.mkdir(parents=True, exist_ok=True)

OOKLA_URL = "https://ookla-open-data.s3.amazonaws.com/shapefiles/performance/type=fixed/year=2025/quarter=4/2025-10-01_performance_fixed_tiles.zip"

# (min_lon, min_lat, max_lon, max_lat) for 5 cities (+ inner L-ring)
CITY_BBOXES = {
    "beograd":    (20.18, 44.62, 20.72, 44.96),
    "zagreb":     (15.78, 45.68, 16.22, 45.92),
    "sarajevo":   (18.18, 43.74, 18.56, 43.96),
    "novi_pazar": (20.38, 43.05, 20.65, 43.23),
    "travnik":    (17.54, 44.14, 17.79, 44.30),
}
# Union bounding box for ultra-fast early reject in SHP reader
U_MIN_LON = min(b[0] for b in CITY_BBOXES.values())
U_MIN_LAT = min(b[1] for b in CITY_BBOXES.values())
U_MAX_LON = max(b[2] for b in CITY_BBOXES.values())
U_MAX_LAT = max(b[3] for b in CITY_BBOXES.values())


def download_zip():
    t0 = time.time()
    print(f"Downloading Ookla 2025 Q4 Fixed ZIP to scratch ({SCRATCH_ZIP.name})...", flush=True)
    ctx = ssl.create_default_context()
    req = urllib.request.Request(OOKLA_URL, headers={"User-Agent": "UrbanLabResearch/1.0"})
    total = 0
    with urllib.request.urlopen(req, timeout=120, context=ctx) as resp, open(SCRATCH_ZIP, "wb") as f:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
    print(f"Downloaded {total / 1048576:.1f} MB in {time.time() - t0:.1f}s", flush=True)


def extract_5cities():
    t0 = time.time()
    tiles_by_city = {c: [] for c in CITY_BBOXES}
    matched_idx = {}  # 0-based record index -> (city_id, cx, cy, minx, miny, maxx, maxy)

    with zipfile.ZipFile(SCRATCH_ZIP, "r") as zf:
        names = zf.namelist()
        shp_name = next(n for n in names if n.endswith(".shp"))
        dbf_name = next(n for n in names if n.endswith(".dbf"))
        print(f"Scanning SHP ({shp_name}) for 5-city bboxes...", flush=True)

        # Read SHP sequentially (record header 8B + shape_type 4B + bbox 32B for Polygon=5)
        with zf.open(shp_name, "r") as shpf:
            hdr = shpf.read(100)
            rec_i = 0
            while True:
                rh = shpf.read(8)
                if len(rh) < 8:
                    break
                rec_num, content_len_words = struct.unpack(">ii", rh)
                content_bytes = content_len_words * 2
                body = shpf.read(content_bytes)
                if len(body) < 36:
                    rec_i += 1
                    continue
                stype = struct.unpack("<i", body[:4])[0]
                if stype == 5:  # Polygon
                    minx, miny, maxx, maxy = struct.unpack("<dddd", body[4:36])
                    if not (maxx < U_MIN_LON or minx > U_MAX_LON or maxy < U_MIN_LAT or miny > U_MAX_LAT):
                        cx = 0.5 * (minx + maxx)
                        cy = 0.5 * (miny + maxy)
                        for cid, (bx0, by0, bx1, by1) in CITY_BBOXES.items():
                            if bx0 <= cx <= bx1 and by0 <= cy <= by1:
                                matched_idx[rec_i] = (cid, round(cx, 6), round(cy, 6), round(minx, 6), round(miny, 6), round(maxx, 6), round(maxy, 6))
                                break
                rec_i += 1
        print(f"Scanned {rec_i:,} global tiles -> matched {len(matched_idx):,} tiles in 5 cities ({time.time()-t0:.1f}s)", flush=True)

        # Now scan DBF sequentially and read ONLY matched record indices!
        with zf.open(dbf_name, "r") as dbff:
            dbf_hdr = dbff.read(32)
            num_records = struct.unpack("<I", dbf_hdr[4:8])[0]
            header_len = struct.unpack("<H", dbf_hdr[8:10])[0]
            record_len = struct.unpack("<H", dbf_hdr[10:12])[0]
            field_bytes = dbff.read(header_len - 32)
            fields = []
            pos = 0
            while pos + 32 <= len(field_bytes) and field_bytes[pos] != 0x0D:
                fname = field_bytes[pos:pos+11].split(b"\x00")[0].decode("ascii", errors="ignore").strip()
                ftype = chr(field_bytes[pos+11])
                flen = field_bytes[pos+16]
                fields.append((fname, ftype, flen))
                pos += 32
            print("DBF fields:", [f[0] for f in fields], f"rec_len={record_len} n={num_records:,}", flush=True)

            for i in range(num_records):
                rec_raw = dbff.read(record_len)
                if len(rec_raw) < record_len:
                    break
                if i not in matched_idx:
                    continue
                cid, cx, cy, minx, miny, maxx, maxy = matched_idx[i]
                offset = 1  # skip deletion flag byte
                row = {"city_id": cid, "lon": cx, "lat": cy, "bbox": [minx, miny, maxx, maxy]}
                for fname, ftype, flen in fields:
                    val_s = rec_raw[offset:offset+flen].decode("ascii", errors="ignore").strip()
                    offset += flen
                    if ftype in ("N", "F"):
                        if val_s:
                            row[fname] = float(val_s) if "." in val_s else int(val_s)
                        else:
                            row[fname] = None
                    else:
                        row[fname] = val_s
                tiles_by_city[cid].append(row)

    summary = {}
    all_tiles = []
    for cid, rows in tiles_by_city.items():
        all_tiles.extend(rows)
        dls = [r["avg_d_kbps"] / 1000.0 for r in rows if r.get("avg_d_kbps") is not None]
        uls = [r["avg_u_kbps"] / 1000.0 for r in rows if r.get("avg_u_kbps") is not None]
        lats = [r["avg_lat_ms"] for r in rows if r.get("avg_lat_ms") is not None]
        tests = sum(r.get("tests") or 0 for r in rows)
        devices = sum(r.get("devices") or 0 for r in rows)
        # Weighted by tests
        w_dl = sum((r["avg_d_kbps"] / 1000.0) * (r.get("tests") or 1) for r in rows if r.get("avg_d_kbps") is not None) / max(1, sum((r.get("tests") or 1) for r in rows if r.get("avg_d_kbps") is not None))
        w_ul = sum((r["avg_u_kbps"] / 1000.0) * (r.get("tests") or 1) for r in rows if r.get("avg_u_kbps") is not None) / max(1, sum((r.get("tests") or 1) for r in rows if r.get("avg_u_kbps") is not None))
        w_lat = sum(r["avg_lat_ms"] * (r.get("tests") or 1) for r in rows if r.get("avg_lat_ms") is not None) / max(1, sum((r.get("tests") or 1) for r in rows if r.get("avg_lat_ms") is not None))
        summary[cid] = {
            "tiles_n": len(rows),
            "tests_total": tests,
            "devices_total": devices,
            "weighted_dl_mbps": round(w_dl, 2),
            "weighted_ul_mbps": round(w_ul, 2),
            "weighted_lat_ms": round(w_lat, 2),
            "median_tile_dl_mbps": round(sorted(dls)[len(dls) // 2], 2) if dls else None,
            "p90_tile_dl_mbps": round(sorted(dls)[int(len(dls) * 0.9)], 2) if dls else None,
        }
        print(f"  Ookla {cid:12s}: tiles={len(rows):4d}, tests={tests:6d}, wDL={summary[cid]['weighted_dl_mbps']:6.2f} Mbps, wUL={summary[cid]['weighted_ul_mbps']:6.2f} Mbps, lat={summary[cid]['weighted_lat_ms']:5.1f} ms", flush=True)

    out_p = OUT_DIR / "ookla_fixed_2025q4_5cities.json"
    b = json.dumps({"quarter": "2025-Q4", "period_start": "2025-10-01", "period_end": "2025-12-31", "source_url": OOKLA_URL, "summary": summary, "tiles": all_tiles}, ensure_ascii=False).encode("utf-8")
    out_p.write_bytes(b)
    append_manifest({
        "ok": True, "city": "common", "layer": "wave5_ookla", "source_name": "ookla_open_data_fixed_2025q4",
        "url": OOKLA_URL, "http_status": 200,
        "bytes": len(b), "sha256": sha256_bytes(b), "local_path": rel(out_p),
    })
    print(f"Saved {len(all_tiles):,} 610m tiles ({len(b)/1024:.1f} KB) to {out_p.name}", flush=True)


def main():
    try:
        download_zip()
        extract_5cities()
    finally:
        if SCRATCH_ZIP.exists():
            SCRATCH_ZIP.unlink()
            print("Cleaned up temporary scratch zip.", flush=True)


if __name__ == "__main__":
    main()
