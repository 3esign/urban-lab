import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_net import RAW_DIR, fetch_url

EDIR = RAW_DIR / "wave4" / "elections"
PDIR = RAW_DIR / "wave4" / "probes"

# 1. Inspect RIK data.json exact station schema + counts for BG & NP
rik = json.loads((EDIR / "srb_rik_2023_all.json").read_text(encoding="utf-8"))
st = rik["stations"]
print("RIK meta.by_election:", json.dumps(rik["meta"].get("by_election"), ensure_ascii=False)[:450])
print("RIK station[0]:", json.dumps(st[0], ensure_ascii=False)[:450])
bg_st = [s for s in st if "београд" in (s.get("city") or "").lower() or "beograd" in (s.get("city") or "").lower()]
np_st = [s for s in st if "нови пазар" in (s.get("city") or "").lower() or "novi pazar" in (s.get("city") or "").lower()]
print(f"RIK counts -> Beograd: {len(bg_st)} stations | Novi Pazar: {len(np_st)} stations")

# 2. Inspect DIP 2025 local ZUP_21 (Grad Zagreb) and DIP 2024 parl CSVs for GRAD ZAGREB
with zipfile.ZipFile(EDIR / "dip_lok_2025.zip") as zf:
    z21 = [n for n in zf.namelist() if "ZUP_21" in n or "21_" in n or "ZAGREB" in n.upper()]
    print("DIP 2025 ZUP_21 files:", z21[:20])

with zipfile.ZipFile(EDIR / "dip_parl_2024.zip") as zf:
    csvs = [n for n in zf.namelist() if n.endswith(".csv") and "inozemstvo" not in n and "posebna" not in n]
    print("DIP 2024 Parl regular CSVs:", csvs[:15])

# 3. Inspect CIK test response & find exact CIK 2024 Local Elections API URL for Općinska vijeća
cik_test = (EDIR / "cik_test.bin").read_text(encoding="utf-8", errors="replace")
print("CIK test raw:", cik_test[:300])

# Read cik_home_index.js around race6 or race7 or GetBasicData
hi = (PDIR / "cik_home_index.js").read_text(encoding="utf-8", errors="replace")
idx = hi.find("dataServiceRace6")
if idx < 0:
    idx = hi.find("race6_")
print("CIK race6 snippet:", hi[max(0, idx-100):idx+700])

# Try fetching CIK 2024 active election list from api_2018 and api_2024
for label, url in [
    ("cik_el_list_18", "https://www.izbori.ba/api_2018/race_getelections/1"),
    ("cik_el_list_24", "https://www.izbori.ba/api_2024/race_getelections/1"),
    ("cik_24_eu", "https://www.izbori.ba/api_2024/race6_electoralunit/35"),
    ("cik_18_eu", "https://www.izbori.ba/api_2018/race6_electoralunit/35"),
    ("cik_18_basic", "https://www.izbori.ba/api_2018/race6_basicinfo/35"),
    ("cik_18_res", "https://www.izbori.ba/api_2018/result_getlast/1"),
]:
    r = fetch_url(url, dest=EDIR / f"{label}.bin", city="sarajevo", layer="wave4_probe", source_name=label, timeout=12, retries=0, save_manifest=False)
    if r["ok"]:
        txt = r.pop("_bytes", b"").decode("utf-8", errors="replace")
        print(f"  [OK]   {label}: len={len(txt)} | {txt[:220]}")
    else:
        print(f"  [FAIL] {label}: {r.get('error')}")
