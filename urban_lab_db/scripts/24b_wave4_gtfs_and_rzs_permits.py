import csv
import io
import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_net import RAW_DIR, fetch_url

OUT_DIR = RAW_DIR / "wave4" / "mobility_and_permits"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def analyze_gtfs_zip(zip_path: Path, city_id: str, label: str):
    res = {"city_id": city_id, "label": label, "zip_path": str(zip_path), "stops": 0, "routes": 0, "trips": 0, "agencies": [], "route_types": {}}
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
        if "agency.txt" in names:
            with io.TextIOWrapper(zf.open("agency.txt"), encoding="utf-8-sig", errors="replace") as f:
                for row in csv.DictReader(f):
                    res["agencies"].append(row.get("agency_name"))
        if "stops.txt" in names:
            stops_list = []
            with io.TextIOWrapper(zf.open("stops.txt"), encoding="utf-8-sig", errors="replace") as f:
                for row in csv.DictReader(f):
                    try:
                        lat = float(row.get("stop_lat", ""))
                        lon = float(row.get("stop_lon", ""))
                        stops_list.append({"id": row.get("stop_id"), "name": row.get("stop_name"), "lat": lat, "lon": lon})
                    except Exception:
                        pass
            res["stops"] = len(stops_list)
            # Save lightweight stops summary
            (OUT_DIR / f"gtfs_stops_{city_id}_{label}.json").write_text(
                json.dumps(stops_list, ensure_ascii=False), encoding="utf-8"
            )
        if "routes.txt" in names:
            rt = defaultdict(int)
            with io.TextIOWrapper(zf.open("routes.txt"), encoding="utf-8-sig", errors="replace") as f:
                for row in csv.DictReader(f):
                    res["routes"] += 1
                    rt[str(row.get("route_type", "unk"))] += 1
            res["route_types"] = dict(rt)
        if "trips.txt" in names:
            with io.TextIOWrapper(zf.open("trips.txt"), encoding="utf-8-sig", errors="replace") as f:
                res["trips"] = sum(1 for _ in csv.DictReader(f))
    return res


def main():
    summary = {"gtfs": [], "rzs_permits": {}, "extra_files": []}

    print("=== 1. Belgrade GTFS (Urban + Suburban, data.gov.rs 2026-11-05) ===")
    BG_GTFS = [
        ("bg_urban", "https://data.gov.rs/s/resources/gradski-javni-prevoz-u-beogradu-gtfs/20261105-115729/bgprev-belgrade-rs-3-.zip"),
        ("bg_suburban", "https://data.gov.rs/s/resources/prigradski-javni-prevoz-u-u-beogradu-gtfs/20261105-115922/bgprevsuburb-belgrade-rs-1-.zip"),
    ]
    for lbl, url in BG_GTFS:
        dest = OUT_DIR / f"gtfs_{lbl}.zip"
        r = fetch_url(url, dest=dest, city="beograd", layer="wave4_gtfs", source_name=f"gtfs_{lbl}", timeout=60, retries=2)
        if r["ok"]:
            info = analyze_gtfs_zip(dest, "beograd", lbl)
            summary["gtfs"].append(info)
            print(f"  + {lbl:12s}: stops={info['stops']}, routes={info['routes']}, trips={info['trips']}, route_types={info['route_types']}")
        else:
            print(f"  [FAIL] {lbl}: {r.get('error')}")

    print("\n=== 2. RZS Open Data Building Permits JSON (050202IND01 & 050204IND01) ===")
    RZS_URLS = [
        ("permits_buildings", "https://opendata.stat.gov.rs/data/WcfJsonRestService.Service1.svc/dataset/050202IND01/1/json"),
        ("permits_dwellings", "https://opendata.stat.gov.rs/data/WcfJsonRestService.Service1.svc/dataset/050204IND01/1/json"),
    ]
    for slug, url in RZS_URLS:
        dest = OUT_DIR / f"rzs_{slug}.json"
        r = fetch_url(url, dest=dest, city="common", layer="wave4_rzs_permits", source_name=f"rzs_{slug}", timeout=45, retries=2)
        if r["ok"]:
            raw = r.pop("_bytes", b"")
            try:
                data = json.loads(raw.decode("utf-8-sig", errors="replace"))
                print(f"  + RZS {slug}: {len(data)} rows | sample keys={list(data[0].keys()) if isinstance(data, list) and data else type(data)}")
                if isinstance(data, list) and data:
                    print(f"    sample row 0: {str(data[0])[:220]}")
                    # Filter for Beograd, Novi Pazar, Pancevo, Raska, Tutin, Sjenica
                    filtered = []
                    for row in data:
                        txt = json.dumps(row, ensure_ascii=False).lower()
                        if any(k in txt for k in ["београд", "beograd", "нови пазар", "novi pazar", "панчев", "рашка", "тутин", "сјениц", "врачар", "стари град", "нови београд", "земун", "вождовац", "звездара", "чукарица", "палилула", "савски венац", "раковица"]):
                            filtered.append(row)
                    (OUT_DIR / f"rzs_{slug}_bg_np_hinterland.json").write_text(
                        json.dumps(filtered, ensure_ascii=False), encoding="utf-8"
                    )
                    summary["rzs_permits"][slug] = {"total_rows": len(data), "bg_np_hinterland_rows": len(filtered)}
                    print(f"    filtered BG+NP+L rows: {len(filtered)}")
            except Exception as e:
                print(f"  [PARSE ERR] {slug}: {e}")
        else:
            print(f"  [FAIL] {slug}: {r.get('error')}")

    print("\n=== 3. Extra Official Open Data (Sjenica 2026 Property Prices & SEPA Air Emissions 2024) ===")
    EXTRAS = [
        ("novi_pazar", "sjenica_property_prices_2026.xlsx", "https://data.gov.rs/s/resources/prosecne-cene-nepokretnosti-na-podrucju-opstine-sjenica-u-2026-godini/20260609-104652/prosecne-cene-nepokretnosti-sjenica-2026.xlsx"),
        ("common", "srb_air_emissions_2024.csv", "https://data.gov.rs/s/resources/emisije-u-vazdukh/20260424-123951/emisije-u-vazduh-2024.csv"),
    ]
    for cid, fname, url in EXTRAS:
        dest = OUT_DIR / fname
        r = fetch_url(url, dest=dest, city=cid, layer="wave4_official_extra", source_name=fname, timeout=30, retries=2)
        summary["extra_files"].append({"file": fname, "ok": r["ok"], "bytes": r.get("bytes", 0)})
        print(f"  [{'OK' if r['ok'] else 'FAIL'}] {fname}: bytes={r.get('bytes', 0)}")

    (OUT_DIR / "mobility_permits_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\nDONE Mobility & RZS Permits.")


if __name__ == "__main__":
    main()
