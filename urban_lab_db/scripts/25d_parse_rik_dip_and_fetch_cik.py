import csv
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_net import RAW_DIR, fetch_url

EDIR = RAW_DIR / "wave4" / "elections"
PDIR = RAW_DIR / "wave4" / "probes"


def parse_rik_bg_np():
    rik = json.loads((EDIR / "srb_rik_2023_all.json").read_text(encoding="utf-8"))
    meta_2023 = rik["meta"]["by_election"].get("parl2023", {})
    # Check full keys of a station to map list names accurately
    s0 = rik["stations"][0]
    print("RIK station full keys:", list(s0.keys()))
    print("RIK votes sample:", str(s0.get("votes"))[:220], "lists meta:", str(meta_2023.get("lists") or rik["meta"].get("lists"))[:220])

    out = []
    for s in rik["stations"]:
        city_raw = (s.get("city") or "").strip()
        if city_raw == "Београд":
            cid = "beograd"
        elif city_raw == "Нови Пазар":
            cid = "novi_pazar"
        else:
            continue
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
            "registered": s.get("registered"),
            "voted": s.get("voted") or s.get("ballots"),
            "valid": s.get("valid"),
            "invalid": s.get("invalid"),
            "votes": s.get("votes") or {},
        })
    (EDIR / "parsed_rik_2023_bg_np.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    bg_n = sum(1 for x in out if x["city_id"] == "beograd")
    np_n = sum(1 for x in out if x["city_id"] == "novi_pazar")
    print(f"[OK] Parsed RIK 2023: Beograd={bg_n}, Novi Pazar={np_n}, total={len(out)}")


def parse_dip_zagreb():
    # 1. Parliamentary 2024 CSVs (I, II, VI constituencies cover Grad Zagreb!)
    zg_parl = []
    with zipfile.ZipFile(EDIR / "dip_parl_2024.zip", "r") as zf:
        for fname in ["CSV/02_01_rezultati.csv", "CSV/02_02_rezultati.csv", "CSV/02_06_rezultati.csv"]:
            if fname not in zf.namelist():
                continue
            raw = zf.read(fname)
            # DIP CSVs use cp1250 or utf-8
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("cp1250", errors="replace")
            reader = csv.reader(io.StringIO(text), delimiter=";")
            header = next(reader, [])
            # Lists start after column 14 (Nevažeći listići)
            # Find index of 'Nevažeći' or 'Važeći'
            val_idx = next((i for i, h in enumerate(header) if "važeći" in h.lower() or "vazeci" in h.lower()), 13)
            inv_idx = val_idx + 1
            list_cols = [(i, header[i].strip()) for i in range(inv_idx + 1, len(header)) if header[i].strip()]
            for row in reader:
                if len(row) <= inv_idx:
                    continue
                grad_col = (row[5] or "").strip().upper()
                zup_col = (row[3] or "").strip().upper()
                if grad_col != "ZAGREB" and "GRAD ZAGREB" not in zup_col:
                    continue
                def to_int(x):
                    try:
                        return int(str(x).replace(".", "").strip())
                    except Exception:
                        return 0
                reg = to_int(row[10])
                cast = to_int(row[12]) or to_int(row[11])
                valid = to_int(row[val_idx])
                invalid = to_int(row[inv_idx])
                votes = {}
                for ci, cname in list_cols:
                    if ci < len(row):
                        v = to_int(row[ci])
                        if v > 0:
                            votes[cname] = v
                zg_parl.append({
                    "city_id": "zagreb",
                    "country_iso3": "HRV",
                    "election_id": "elec:hrv:2024-04-17:parl",
                    "constituency": row[0].strip(),
                    "muni": f"Grad Zagreb (IJ {row[0].strip()})",
                    "station_code": f"{row[0].strip()}-{row[6].strip()}",
                    "station_name": row[7].strip() or row[8].strip(),
                    "address": row[9].strip(),
                    "registered": reg,
                    "voted": cast,
                    "valid": valid,
                    "invalid": invalid,
                    "votes": votes,
                })
    (EDIR / "parsed_dip_2024_zagreb.json").write_text(json.dumps(zg_parl, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Parsed DIP 2024 Parliamentary Grad Zagreb: {len(zg_parl)} polling stations")

    # 2. Local 2025 Grad Zagreb (krug-1/ZUP_21/557_21.xlsx)
    zg_lok = []
    with zipfile.ZipFile(EDIR / "dip_lok_2025.zip", "r") as zf:
        if "krug-1/ZUP_21/557_21.xlsx" in zf.namelist():
            wb = openpyxl.load_workbook(io.BytesIO(zf.read("krug-1/ZUP_21/557_21.xlsx")), read_only=True, data_only=True)
            print("  DIP 2025 ZUP_21 sheets:", wb.sheetnames)
            for sname in wb.sheetnames:
                ws = wb[sname]
                rows_iter = ws.iter_rows(values_only=True)
                hdr = next(rows_iter, None)
                r1 = next(rows_iter, None)
                print(f"    Sheet '{sname}' hdr[:12]={hdr[:12] if hdr else None}")
                print(f"    Sheet '{sname}' r1[:12]={r1[:12] if r1 else None}")
            wb.close()


def discover_and_fetch_cik():
    hi = (PDIR / "cik_home_index.js").read_text(encoding="utf-8", errors="replace")
    # Print dbService definition
    idx = hi.find("dbService")
    print("\n=== CIK dbService & api_2018 exact routes ===")
    print(hi[max(0, idx-30):idx+1100])
    # Also find all string literals containing '/race' or '/api' or 'Get'
    routes = re.findall(r'["\'](/[a-zA-Z0-9_/\-]+)["\']', hi)
    print("CIK routes in home-index.min.js:", list(dict.fromkeys([r for r in routes if len(r) > 4]))[:40])


if __name__ == "__main__":
    parse_rik_bg_np()
    parse_dip_zagreb()
    discover_and_fetch_cik()
