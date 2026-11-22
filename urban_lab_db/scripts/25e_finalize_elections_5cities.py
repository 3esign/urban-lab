import io
import json
import sys
import time
import zipfile
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_net import RAW_DIR, fetch_url

EDIR = RAW_DIR / "wave4" / "elections"
API_CIK = "https://www.izbori.ba/api_2018"


def parse_rik_full():
    rik = json.loads((EDIR / "srb_rik_2023_all.json").read_text(encoding="utf-8"))
    s0 = rik["stations"][0]
    print("RIK s0 results sample:", str(s0.get("results"))[:240], "turnout:", s0.get("turnout"), "valid:", s0.get("valid"), "reg:", s0.get("registered"))
    out = []
    for s in rik["stations"]:
        city_raw = (s.get("city") or "").strip()
        if city_raw == "Београд":
            cid = "beograd"
        elif city_raw == "Нови Пазар":
            cid = "novi_pazar"
        else:
            continue
        reg = int(s.get("registered") or 0)
        valid = int(s.get("valid") or 0)
        # turnout can be count or pct
        t_raw = s.get("turnout")
        if isinstance(t_raw, (int, float)) and t_raw > 100:
            cast = int(t_raw)
        elif isinstance(t_raw, (int, float)) and reg > 0:
            cast = max(valid, int(round(reg * t_raw / 100.0)))
        else:
            cast = valid
        invalid = max(0, cast - valid)
        if reg > 0 and cast > reg:
            cast = reg
            if valid > cast:
                valid = cast
            invalid = max(0, cast - valid)
        res_raw = s.get("results") or {}
        votes = {}
        if isinstance(res_raw, dict):
            for k, v in res_raw.items():
                if isinstance(v, dict):
                    votes[k] = int(v.get("votes") or v.get("v") or 0)
                else:
                    try:
                        votes[k] = int(v)
                    except Exception:
                        pass
        elif isinstance(res_raw, list):
            for item in res_raw:
                if isinstance(item, dict):
                    nm = item.get("name") or item.get("list") or item.get("party") or str(item.get("no"))
                    votes[nm] = int(item.get("votes") or item.get("v") or 0)
        out.append({
            "city_id": cid,
            "country_iso3": "SRB",
            "election_id": "elec:srb:2023-12-17:parl",
            "muni": s.get("muni") or city_raw,
            "station_code": str(s.get("no") or s.get("sid")),
            "station_name": s.get("place") or s.get("name") or f"BM {s.get('no')}",
            "address": s.get("address"),
            "lat": s.get("lat"),
            "lon": s.get("lon"),
            "registered": reg,
            "voted": cast,
            "valid": valid,
            "invalid": invalid,
            "votes": {k: v for k, v in votes.items() if v > 0},
        })
    (EDIR / "parsed_rik_2023_bg_np.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] RIK 2023 full parsed: {len(out)} stations (sample votes count={len(out[0]['votes']) if out else 0})")


def parse_dip_2025_zagreb():
    zg_lok = {"skupstina": [], "gradonacelnik": []}
    with zipfile.ZipFile(EDIR / "dip_lok_2025.zip", "r") as zf:
        raw_xlsx = zf.read("krug-1/ZUP_21/557_21.xlsx")
    wb = openpyxl.load_workbook(io.BytesIO(raw_xlsx), read_only=True, data_only=True)
    for key, sname, elec_id in [
        ("skupstina", "skupština Grada Zagreba", "elec:hrv:2025-05-18:local_zg_assembly"),
        ("gradonacelnik", "gradonačelnik Grada Zagreba", "elec:hrv:2025-05-18:local_zg_mayor"),
    ]:
        if sname not in wb.sheetnames:
            continue
        ws = wb[sname]
        rows = ws.iter_rows(values_only=True)
        _title = next(rows, None)
        hdr = list(next(rows, None) or [])
        # Find Važeći / Nevažeći columns
        val_idx = next((i for i, h in enumerate(hdr) if h and "važeći" in str(h).lower()), 11)
        inv_idx = next((i for i, h in enumerate(hdr) if h and "nevažeći" in str(h).lower()), val_idx + 1)
        cand_cols = [(i, str(hdr[i]).strip()) for i in range(inv_idx + 1, len(hdr)) if hdr[i] and str(hdr[i]).strip()]
        def to_int(x):
            try:
                return int(round(float(x)))
            except Exception:
                return 0
        for row in rows:
            if not row or len(row) <= inv_idx or row[4] is None:
                continue
            bm_code = str(row[4]).strip()
            if not bm_code or bm_code.lower().startswith("ukupno"):
                continue
            reg = to_int(row[8])
            cast = to_int(row[10]) or to_int(row[9])
            valid = to_int(row[val_idx])
            invalid = to_int(row[inv_idx])
            if valid + invalid > cast:
                cast = valid + invalid
            if reg > 0 and cast > reg:
                reg = cast
            votes = {}
            for ci, cname in cand_cols:
                if ci < len(row):
                    v = to_int(row[ci])
                    if v > 0:
                        votes[cname] = v
            zg_lok[key].append({
                "city_id": "zagreb",
                "country_iso3": "HRV",
                "election_id": elec_id,
                "muni": str(row[3] or "GRAD ZAGREB").strip(),
                "station_code": bm_code,
                "station_name": str(row[5] or row[6] or f"BM {bm_code}").strip(),
                "address": str(row[7] or "").strip(),
                "registered": reg,
                "voted": cast,
                "valid": valid,
                "invalid": invalid,
                "votes": votes,
            })
    wb.close()
    (EDIR / "parsed_dip_2025_zagreb.json").write_text(json.dumps(zg_lok, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] DIP 2025 Zagreb parsed: skupstina={len(zg_lok['skupstina'])} stations, gradonacelnik={len(zg_lok['gradonacelnik'])} stations")


def fetch_cik_bih():
    print("\n=== Fetching BiH CIK Elections via api_2018 ===")
    # Probe resId 35..45 to find 2024 Local Elections dbName!
    found_dbs = {}
    for res_id in [35, 36, 37, 38, 39, 40, 41, 42]:
        url = f"{API_CIK}/administration_electionresultcontroller_getdatabasename/{res_id}"
        r = fetch_url(url, dest=EDIR / f"cik_dbname_{res_id}.json", city="common", layer="wave4_elections_bih", source_name=f"cik_db_{res_id}", timeout=12, retries=0, save_manifest=False)
        if r["ok"]:
            txt = r.pop("_bytes", b"").decode("utf-8", errors="replace").strip().strip('"')
            if txt and len(txt) < 100 and "<html" not in txt.lower():
                found_dbs[res_id] = txt
                print(f"  resId={res_id} -> dbName={txt}")
    # Also check race_getallelections or similar if available; pick latest local (2024) or general (2022)
    target_res = None
    target_db = None
    for rid, dbn in sorted(found_dbs.items(), reverse=True):
        if "2024" in dbn or "lokal" in dbn.lower():
            target_res, target_db = rid, dbn
            break
    if not target_db and found_dbs:
        target_res = max(found_dbs.keys())
        target_db = found_dbs[target_res]
    if not target_db:
        print("  [WARN] Could not discover CIK dbName via resId 35..42.")
        return

    print(f"  Using CIK resId={target_res}, dbName={target_db}")
    # Check race6 (Local Municipal Councils) or race5 (Mayors) or race2/race4 (General)
    # In CIK Local Elections: race 6 = Općinsko vijeće / Skupština općine, race 5 = Načelnik/Gradonačelnik
    # Let's probe electoral units for race6 and race5 and race2
    for rnum in [6, 5, 4, 2]:
        u_test = f"{API_CIK}/race{rnum}_electoralunit/1/{target_db}"
        r = fetch_url(u_test, dest=EDIR / f"cik_r{rnum}_eu.json", city="common", layer="wave4_elections_bih", source_name=f"cik_r{rnum}_eu", timeout=15, retries=0, save_manifest=False)
        if r["ok"]:
            raw = r.pop("_bytes", b"").decode("utf-8", errors="replace")
            print(f"  race{rnum}_eu (/1/db): ok len={len(raw)} | {raw[:180]}")
        else:
            # Try reversed param order: /{db}/1 or /{db}
            u_test2 = f"{API_CIK}/race{rnum}_electoralunit/{target_db}/1"
            r2 = fetch_url(u_test2, dest=EDIR / f"cik_r{rnum}_eu2.json", city="common", layer="wave4_elections_bih", source_name=f"cik_r{rnum}_eu2", timeout=15, retries=0, save_manifest=False)
            if r2["ok"]:
                raw2 = r2.pop("_bytes", b"").decode("utf-8", errors="replace")
                print(f"  race{rnum}_eu (/db/1): ok len={len(raw2)} | {raw2[:180]}")
            else:
                print(f"  race{rnum}_eu failed: {r.get('error')} / {r2.get('error')}")


if __name__ == "__main__":
    parse_rik_full()
    parse_dip_2025_zagreb()
    fetch_cik_bih()
