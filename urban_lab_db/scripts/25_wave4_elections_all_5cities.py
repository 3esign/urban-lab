import csv
import io
import json
import re
import shutil
import sys
import time
import zipfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_net import RAW_DIR, fetch_url

PDIR = RAW_DIR / "wave4" / "probes"
OUT_DIR = RAW_DIR / "wave4" / "elections"
OUT_DIR.mkdir(parents=True, exist_ok=True)
MOB_DIR = RAW_DIR / "wave4" / "mobility_and_permits"
MOB_DIR.mkdir(parents=True, exist_ok=True)


def analyze_zet_gtfs():
    src = PDIR / "zet_gtfs_direct.bin"
    if not src.exists() or src.stat().st_size < 10000:
        print("ZET GTFS missing!")
        return
    dst = MOB_DIR / "gtfs_zet_zagreb.zip"
    shutil.copy2(src, dst)
    info = {"city_id": "zagreb", "label": "zet_zagreb", "stops": 0, "routes": 0, "trips": 0, "route_types": {}}
    with zipfile.ZipFile(dst, "r") as zf:
        names = set(zf.namelist())
        if "stops.txt" in names:
            stops_list = []
            with io.TextIOWrapper(zf.open("stops.txt"), encoding="utf-8-sig", errors="replace") as f:
                for row in csv.DictReader(f):
                    try:
                        stops_list.append({
                            "id": row.get("stop_id"),
                            "name": row.get("stop_name"),
                            "lat": float(row["stop_lat"]),
                            "lon": float(row["stop_lon"]),
                        })
                    except Exception:
                        pass
            info["stops"] = len(stops_list)
            (MOB_DIR / "gtfs_stops_zagreb_zet.json").write_text(json.dumps(stops_list, ensure_ascii=False), encoding="utf-8")
        if "routes.txt" in names:
            rt = defaultdict(int)
            with io.TextIOWrapper(zf.open("routes.txt"), encoding="utf-8-sig", errors="replace") as f:
                for row in csv.DictReader(f):
                    info["routes"] += 1
                    rt[str(row.get("route_type", "unk"))] += 1
            info["route_types"] = dict(rt)
        if "trips.txt" in names:
            with io.TextIOWrapper(zf.open("trips.txt"), encoding="utf-8-sig", errors="replace") as f:
                info["trips"] = sum(1 for _ in csv.DictReader(f))
    (MOB_DIR / "gtfs_zet_zagreb_summary.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"=== ZET Zagreb GTFS: stops={info['stops']}, routes={info['routes']}, trips={info['trips']}, route_types={info['route_types']} ===")


def collect_serbia_rik():
    print("\n=== 1. Serbia RIK Polling Stations (rezultatiizbora.rs/data.json — BG + NP) ===")
    dest = OUT_DIR / "srb_rik_2023_all.json"
    r = fetch_url("https://rezultatiizbora.rs/data.json", dest=dest, city="common", layer="wave4_elections_srb", source_name="rik_2023_data_json", timeout=60, retries=2)
    if not r["ok"]:
        print("  [FAIL] rezultatiizbora.rs/data.json:", r.get("error"))
        return
    raw = r.pop("_bytes", b"")
    d = json.loads(raw.decode("utf-8", errors="replace"))
    print("  Top-level keys:", list(d.keys()) if isinstance(d, dict) else f"list({len(d)})")
    if isinstance(d, dict):
        for k, v in list(d.items())[:8]:
            if isinstance(v, list):
                print(f"    key '{k}': list({len(v)}), sample0={str(v[0])[:180] if v else None}")
            elif isinstance(v, dict):
                print(f"    key '{k}': dict({len(v)}), sample_keys={list(v.keys())[:8]}")
            else:
                print(f"    key '{k}': {str(v)[:120]}")


def inspect_dip_zagreb():
    print("\n=== 2. Croatia DIP 2025 Local & 2024 Parliamentary ZIPs (Zagreb) ===")
    for slug, fn in [("dip_lok_2025", "dip_lok_2025_zip.bin"), ("dip_parl_2024", "dip_parl_2024_zip.bin")]:
        src = PDIR / fn
        if not src.exists():
            continue
        dst = OUT_DIR / f"{slug}.zip"
        shutil.copy2(src, dst)
        with zipfile.ZipFile(dst, "r") as zf:
            names = zf.namelist()
            zg_files = [n for n in names if "21" in n or "zagreb" in n.lower() or "skupstina" in n.lower() or "grad" in n.lower()]
            print(f"  {slug}: total_files={len(names)}, sample={names[:8]}")
            print(f"    ZG-matching sample ({len(zg_files)}): {zg_files[:12]}")
            # Peek first matching CSV for Zagreb
            csv_cands = [n for n in names if n.lower().endswith(".csv") and ("21" in n or "zagreb" in n.lower() or "izb_1" in n.lower() or "ij01" in n.lower())]
            if not csv_cands:
                csv_cands = [n for n in names if n.lower().endswith(".csv")]
            if csv_cands:
                sample_f = csv_cands[0]
                with io.TextIOWrapper(zf.open(sample_f), encoding="utf-8-sig", errors="replace") as f:
                    lines = [f.readline().strip() for _ in range(3)]
                print(f"    Sample CSV '{sample_f}':")
                for ln in lines:
                    print(f"      {ln[:200]}")


def inspect_cik_bih():
    print("\n=== 3. BiH CIK izbori.ba 2024 Local Elections API ===")
    cik_html = (PDIR / "cik_2024_root.bin").read_text(encoding="utf-8", errors="replace")
    # Find apiUrl value in HTML
    m_all = re.findall(r'id=["\']([^"\']*)["\'][^>]*value=["\']([^"\']*)["\']', cik_html, flags=re.I)
    print("  CIK hidden inputs:", m_all[:15])
    # Also search for https://www.izbori.ba or api strings in cik_home_index.js
    hi_p = PDIR / "cik_home_index.js"
    if hi_p.exists():
        txt = hi_p.read_text(encoding="utf-8", errors="replace")
        m_race = re.findall(r'race[4567]_[a-zA-Z0-9_]+', txt)
        print("  CIK race4-7 endpoints:", list(dict.fromkeys(m_race))[:25])
    # Test direct CIK API base
    for base_test in [
        "https://www.izbori.ba/api_2024/api/ElectionResult/GetBasicData/35/6",
        "https://www.izbori.ba/Rezultati_izbora/api/ElectionResult/GetBasicData/35/6",
    ]:
        rr = fetch_url(base_test, dest=OUT_DIR / "cik_test.bin", city="sarajevo", layer="wave4_probe", source_name="cik_test", timeout=12, retries=0, save_manifest=False)
        print(f"  CIK test {base_test}: ok={rr['ok']} err={rr.get('error')}")


if __name__ == "__main__":
    analyze_zet_gtfs()
    collect_serbia_rik()
    inspect_dip_zagreb()
    inspect_cik_bih()
