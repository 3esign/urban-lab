import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_net import RAW_DIR, fetch_url

PDIR = RAW_DIR / "wave4" / "probes"
EDIR = RAW_DIR / "wave4" / "elections"
API_CIK = "https://www.izbori.ba/api_2018"
DB_2024 = "WebResult_2024MUNI_2024_9_19_20_28_13"
LANG = "1"

hi = (PDIR / "cik_home_index.js").read_text(encoding="utf-8", errors="replace")
for pat in ["race8_polling", "race9_polling", "race9_electoralunit", "race8_electoralunit"]:
    for m in re.finditer(pat, hi):
        s = max(0, m.start() - 25)
        e = min(len(hi), m.end() + 95)
        print(f"JS [{pat}]: {hi[s:e]}")
        break
# Find ALL occurrences of race9_ and race8_ strings
r9_all = list(dict.fromkeys(re.findall(r'race9_[a-zA-Z0-9_]+/["\'\+\w/]+', hi)))
r8_all = list(dict.fromkeys(re.findall(r'race8_[a-zA-Z0-9_]+/["\'\+\w/]+', hi)))
print("ALL race9 calls:", r9_all[:20])
print("ALL race8 calls:", r8_all[:20])

# Also test 1 Travnik station immediately
eu9 = json.loads((EDIR / "cik_36_r9_eu.json").read_text(encoding="utf-8"))
tr_eu = next(x for x in eu9 if "TRAVNIK" in (x.get("name") or "").upper() and "NOVI" not in (x.get("name") or "").upper())
print("Travnik EU:", tr_eu)
r_ps = fetch_url(f"{API_CIK}/race9_pollingstation/{DB_2024}/{tr_eu['electoralUnitId']}/{LANG}", city="travnik", layer="wave4_probe", source_name="cik_tr_ps", timeout=15, retries=0, save_manifest=False)
ps_list = json.loads(r_ps.pop("_bytes", b"[]").decode("utf-8"))
print("Travnik PS[0]:", ps_list[0] if ps_list else None)
ps0 = ps_list[0]["pollingStationId"] if ps_list else None

for label, path in [
    ("bi_db_ps", f"/race9_pollingstationsbasicinfo/{DB_2024}/{ps0}"),
    ("bi_db_ps_lang", f"/race9_pollingstationsbasicinfo/{DB_2024}/{ps0}/{LANG}"),
    ("bi_db_eu_ps", f"/race9_pollingstationsbasicinfo/{DB_2024}/{tr_eu['electoralUnitId']}/{ps0}/{LANG}"),
    ("pr_db_ps", f"/race9_pollingstationspartyresult/{DB_2024}/{ps0}"),
    ("pr_db_ps_lang", f"/race9_pollingstationspartyresult/{DB_2024}/{ps0}/{LANG}"),
    ("muni_bi", f"/race9_electoralunitbasicinfo/{DB_2024}/{tr_eu['electoralUnitId']}/{LANG}"),
    ("muni_pr", f"/race9_electoralunitpartyresult/{DB_2024}/{tr_eu['electoralUnitId']}/{LANG}"),
]:
    r = fetch_url(API_CIK + path, city="travnik", layer="wave4_probe", source_name=label, timeout=12, retries=0, save_manifest=False)
    if r["ok"]:
        txt = r.pop("_bytes", b"").decode("utf-8", errors="replace")
        print(f"  [OK]   {label:16s}: len={len(txt)} | {txt[:200]}")
    else:
        print(f"  [FAIL] {label:16s}: {r.get('error')}")
