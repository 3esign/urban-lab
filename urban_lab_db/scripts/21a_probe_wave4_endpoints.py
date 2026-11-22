import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_net import BASE_DIR, RAW_DIR, fetch_url

OUT_DIR = RAW_DIR / "wave4" / "probes"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 1. Inspect existing ZG3D CSV & wave3_osm folder
zg3d_csv = RAW_DIR / "zagreb" / "zg3d-gradska-cetvrt-donji-grad-2022_csv.csv"
if zg3d_csv.exists():
    with open(zg3d_csv, "r", encoding="utf-8-sig", errors="replace") as f:
        sample_lines = [f.readline().strip() for _ in range(4)]
    print("ZG3D CSV size:", zg3d_csv.stat().st_size, "bytes")
    for i, ln in enumerate(sample_lines):
        print(f"  L{i}: {ln[:200]}")

w3_osm = RAW_DIR / "wave3_osm"
if w3_osm.exists():
    print("wave3_osm files:", [(p.name, p.stat().st_size) for p in w3_osm.iterdir()])

# 2. Probe live APIs
PROBES = [
    ("ejn_swagger", "https://open.ejn.gov.ba/docs/v1/swagger.json", "bih"),
    ("ejn_admin_units", "https://open.ejn.gov.ba/AdministrativeUnits?$top=5", "bih"),
    ("ejn_award_notices", "https://open.ejn.gov.ba/AwardNotices?$top=3&$orderby=AwardDate%20desc", "bih"),
    ("datagovrs_jn", "https://data.gov.rs/api/1/datasets/?q=javne+nabavke&page_size=10", "srb"),
    ("datagovrs_gtfs", "https://data.gov.rs/api/1/datasets/?q=gtfs&page_size=10", "srb"),
    ("datagovrs_izbori", "https://data.gov.rs/api/1/datasets/?q=izbori&page_size=10", "srb"),
    ("datagovrs_rgz", "https://data.gov.rs/api/1/datasets/?q=nepokretnosti&page_size=10", "srb"),
    ("datazagreb_3d", "https://data.zagreb.hr/api/3/action/package_search?q=3d&rows=15", "hrv"),
    ("datazagreb_nabava", "https://data.zagreb.hr/api/3/action/package_search?q=nabava&rows=10", "hrv"),
    ("datagovhr_izbori", "https://data.gov.hr/ckan/api/3/action/package_search?q=izbori&rows=10", "hrv"),
    ("datagovhr_fiskal", "https://data.gov.hr/ckan/api/3/action/package_search?q=fiskalizacija&rows=10", "hrv"),
    ("openalex_bg", "https://api.openalex.org/works?search=Belgrade+urban+economy&per-page=3&mailto=urbanlab@svemir.local", "all"),
    ("gdelt_sa", "https://api.gdeltproject.org/api/v2/doc/doc?query=Sarajevo%20economy&mode=artlist&maxrecords=3&format=json", "all"),
    ("openmeteo_aq", "https://air-quality-api.open-meteo.com/v1/air-quality?latitude=43.8563&longitude=18.4131&hourly=pm2_5,pm10,nitrogen_dioxide&start_date=2025-01-01&end_date=2025-01-03", "all"),
    ("zet_gtfs_page", "https://www.zet.hr/odredbe/datoteke-u-gtfs-formatu/669", "hrv"),
    ("rss_stoplus", "https://radiostoplus.com/feed/", "srb"),
    ("rss_freemedia", "https://freemedia.rs/feed/", "srb"),
    ("rss_travnikgrad", "https://travnik-grad.info/feed/", "bih"),
    ("rss_klix_biznis", "https://www.klix.ba/rss/biznis", "bih"),
    ("rss_biznisinfo", "https://www.biznisinfo.ba/feed/", "bih"),
    ("rss_poslovni", "https://www.poslovni.hr/feed", "hrv"),
    ("dip_open_page", "https://www.izbori.hr/site/izbori-referendumi/lokalni-izbori/lokalni-izbori-2025/rezultati-lokalnih-izbora-2025/otvoreni-podaci-3561/3561", "hrv"),
    ("cik_2024_root", "https://www.izbori.ba/Rezultati_izbora/?resId=35&langId=1", "bih"),
    ("worldbank_remit", "https://api.worldbank.org/v2/country/SRB;HRV;BIH/indicator/BX.TRF.PWKR.CD.DT?format=json&date=2015:2025&per_page=100", "all"),
]

results = []
for name, url, scope in PROBES:
    dest = OUT_DIR / f"{name}.bin"
    r = fetch_url(url, dest=dest, city="common", layer="wave4_probe", source_name=name, timeout=20, retries=1, save_manifest=False)
    preview = ""
    if r["ok"]:
        raw = r.pop("_bytes", b"")
        preview = raw[:180].decode("utf-8", errors="replace").replace("\n", " ").replace("\r", " ")
    results.append({
        "name": name,
        "ok": r["ok"],
        "status": r.get("http_status"),
        "bytes": r.get("bytes", 0),
        "err": r.get("error"),
        "preview": preview[:140],
    })
    print(f"[{ 'OK' if r['ok'] else 'FAIL' }] {name:18s} bytes={r.get('bytes',0):8d} err={r.get('error') or '-'} | {preview[:90]}")

(OUT_DIR / "probe_summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("Done probing:", sum(1 for x in results if x["ok"]), "/", len(results))
