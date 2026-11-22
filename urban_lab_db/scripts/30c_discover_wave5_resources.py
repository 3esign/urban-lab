from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import json
import ssl
import urllib.request
import urllib.parse
from pathlib import Path

ctx = ssl.create_default_context()
HDRS = {"User-Agent": "UrbanLabResearch/1.0", "Accept": "application/json, */*"}

def get_json(url, data=None, headers=None, timeout=20):
    h = dict(HDRS)
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))

# 1. BiH EJN EntitySets list
print("=== 1. BiH EJN EntitySets ===", flush=True)
try:
    ejn = get_json("https://open.ejn.gov.ba/")
    names = [x["name"] for x in ejn.get("value", [])]
    print("All sets:", [n for n in names if not n.endswith("Base")], flush=True)
except Exception as e:
    print("EJN err:", e, flush=True)

# 2. EU TED v3 award fields test (HRV Zagreb, SRB, BIH)
print("\n=== 2. EU TED v3 Fields & Counts ===", flush=True)
try:
    for lbl, q in [
        ("ZG_awards_2024plus", 'buyer-country IN (HRV) AND buyer-city ~ "Zagreb" AND notice-type IN (can-standard, can-social, can-modif) AND publication-date >= 20240101'),
        ("SRB_2022plus", 'buyer-country IN (SRB) AND publication-date >= 20220101'),
        ("BIH_2022plus", 'buyer-country IN (BIH) AND publication-date >= 20220101'),
    ]:
        payload = json.dumps({
            "query": q,
            "fields": [
                "publication-number", "publication-date", "notice-type",
                "buyer-name", "buyer-city", "buyer-country",
                "winner-name", "winner-city", "winner-country",
                "tender-value", "tender-value-cur", "total-value", "total-value-cur",
                "result-value-lot", "result-value-lot-cur",
                "classification-cpv", "notice-title", "procedure-type",
                "received-submissions-type-val", "contract-conclusion-date"
            ],
            "limit": 2
        }).encode("utf-8")
        d = get_json("https://api.ted.europa.eu/v3/notices/search", data=payload, headers={"Content-Type": "application/json"})
        print(lbl, "total=", d.get("totalNoticeCount"), "sample=", json.dumps(d.get("notices", [])[:1], ensure_ascii=False)[:650], flush=True)
except Exception as e:
    print("TED err:", e, flush=True)

# 3. data.zagreb.hr target packages
print("\n=== 3. data.zagreb.hr Resources ===", flush=True)
for slug in [
    "ukupan-promet-nekretnina",
    "ugovori-o-najmu-stanova-2022",
    "katastarska-opcina-katastarska-prostorna-jedinica-za-podrucje-grada-zagreba",
    "podaci-o-kvaliteti-zraka-u-gradu-zagrebu-dordiceva-2023",
    "podaci-o-kvaliteti-zraka-u-gradu-zagrebu-ksaver-2023",
    "podaci-o-kvaliteti-zraka-u-gradu-zagrebu-pescenica-2023",
    "podaci-o-kvaliteti-zraka-u-gradu-zagrebu-siget-2023",
]:
    try:
        d = get_json(f"https://data.zagreb.hr/api/3/action/package_show?id={slug}")["result"]
        res = [(r.get("name"), r.get("format"), r.get("url")) for r in d.get("resources", [])]
        print(f"  {slug}: {res}", flush=True)
    except Exception as e:
        print(f"  {slug} ERR: {e}", flush=True)

# 4. data.gov.rs building permits resources
print("\n=== 4. data.gov.rs Building Permits ===", flush=True)
try:
    d = get_json("https://data.gov.rs/api/1/datasets/?q=" + urllib.parse.quote("дозволе") + "&page_size=5")
    for ds in d.get("data", []):
        print("  DS:", ds.get("title"), "| slug:", ds.get("slug"), flush=True)
        for r in ds.get("resources", [])[:5]:
            print("    RES:", r.get("title"), "|", r.get("format"), "|", r.get("url"), flush=True)
except Exception as e:
    print("data.gov.rs err:", e, flush=True)

# 5. Local SEPA & Sjenica check
print("\n=== 5. Local SEPA & Sjenica ===", flush=True)
mdir = Path(str(DB_DIR / "raw" / "wave4" / "mobility_and_permits"))
sepa = mdir / "srb_air_emissions_2024.csv"
print("SEPA head:", sepa.read_text(encoding="utf-8-sig", errors="replace").splitlines()[:4], flush=True)
import openpyxl
wb = openpyxl.load_workbook(mdir / "sjenica_property_prices_2026.xlsx", read_only=True)
ws = wb.active
print("Sjenica sheets:", wb.sheetnames, flush=True)
for r in list(ws.iter_rows(values_only=True))[:6]:
    print("  SJ:", r, flush=True)
wb.close()
