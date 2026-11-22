from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import importlib
import json
import sqlite3
import urllib.request
import urllib.error
import ssl
from pathlib import Path

DB_PATH = Path(str(DB_DIR / "curated" / "urban_lab_5cities_v4.sqlite"))

print("=== PYTHON PACKAGES ===", flush=True)
for pkg in ["pandas", "pyarrow", "fastparquet", "duckdb", "shapely", "geopandas", "openpyxl", "xlrd", "requests", "scipy", "numpy", "rasterio", "fiona"]:
    try:
        m = importlib.import_module(pkg)
        print(f"  OK  {pkg}: {getattr(m, '__version__', '?')}", flush=True)
    except Exception:
        print(f"  NO  {pkg}", flush=True)

print("\n=== BROKEN VIEW SQL ===", flush=True)
con = sqlite3.connect(str(DB_PATH))
for name, sql in con.execute("SELECT name, sql FROM sqlite_master WHERE type='view' AND name IN ('v_osm_centrality_rings', 'v_osm_5cities_centrality')").fetchall():
    print(f"--- {name} ---\n{sql}\n", flush=True)
print("--- osm_pois columns ---", [r[1] for r in con.execute("PRAGMA table_info(osm_pois)").fetchall()], flush=True)
print("--- domain_signals_procurement sample ---", con.execute("SELECT contract_uid, city_id, buyer_entity_id, winner_entity_id, contract_value_eur, award_date FROM domain_signals_procurement LIMIT 3").fetchall(), flush=True)
print("--- evidence_documents sample ---", con.execute("SELECT doc_id, source_id, doc_type, primary_city_id, trust_tier FROM evidence_documents LIMIT 5").fetchall(), flush=True)
con.close()

ctx = ssl.create_default_context()
HDRS = {"User-Agent": "UrbanLabResearch/1.0 (Academic Urban Economics; +https://example.org)", "Accept": "application/json, */*"}

def probe(label, url, data=None, headers=None, timeout=15):
    h = dict(HDRS)
    if headers:
        h.update(headers)
    try:
        req = urllib.request.Request(url, data=data, headers=h)
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read(600)
            ct = resp.headers.get("Content-Type", "")
            print(f"  [OK {resp.status}] {label} | ct={ct[:40]} | len>={len(body)} | head={body[:160]!r}", flush=True)
            return True
    except urllib.error.HTTPError as e:
        err_b = e.read(200) if hasattr(e, "read") else b""
        print(f"  [HTTP {e.code}] {label} | {err_b[:140]!r}", flush=True)
    except Exception as e:
        print(f"  [ERR] {label} | {type(e).__name__}: {e}", flush=True)
    return False

print("\n=== LIVE API PROBES ===", flush=True)
# 1. EU TED v3 Search API (POST)
ted_payload = json.dumps({
    "query": "buyer-country IN (HRV) AND publication-date >= 20240101",
    "fields": ["publication-number", "publication-date", "buyer-name", "buyer-city", "tender-value", "classification-cpv"],
    "limit": 3
}).encode("utf-8")
probe("EU TED v3 HRV", "https://api.ted.europa.eu/v3/notices/search", data=ted_payload, headers={"Content-Type": "application/json"})

# 2. Serbia data.gov.rs search (javne nabavke / gradjevinske dozvole / APR / CEOP)
probe("data.gov.rs nabavke", "https://data.gov.rs/api/1/datasets/?q=nabavke&page_size=5")
probe("data.gov.rs dozvole", "https://data.gov.rs/api/1/datasets/?q=dozvole&page_size=5")
probe("data.gov.rs budzet", "https://data.gov.rs/api/1/datasets/?q=budzet&page_size=5")
probe("Serbia UJN Portal API", "https://jnportal.ujn.gov.rs/api/search/GetAllContractAwardNotices?take=3&skip=0")

# 3. Croatia data.gov.hr & data.zagreb.hr
probe("data.zagreb.hr GUP/dozvole", "https://data.zagreb.hr/api/3/action/package_search?q=prostorni+OR+dozvole+OR+nabava+OR+nekretnine&rows=10")
probe("data.gov.hr nabava/gradnja", "https://data.gov.hr/ckan/api/3/action/package_search?q=javna+nabava+OR+gradjenje+OR+dozvole&rows=10")

# 4. Ookla Open Data AWS S3 index (fixed Q3 2024 / Q4 2024 / Q1 2025 / Q2 2025)
probe("Ookla S3 list", "https://ookla-open-data.s3.amazonaws.com/?list-type=2&prefix=parquet/performance/type=fixed/year=2025/&max-keys=10")
probe("Ookla S3 list 2024", "https://ookla-open-data.s3.amazonaws.com/?list-type=2&prefix=parquet/performance/type=fixed/year=2024/&max-keys=10")

# 5. Ground air quality (EEA / OpenAQ / SEPA / EkoAkcija / Sensor.Community)
probe("Sensor.Community API (area NP)", "https://data.sensor.community/airrohr/v1/filter/area=43.1367,20.5122,30")
probe("Sensor.Community API (area TR)", "https://data.sensor.community/airrohr/v1/filter/area=44.2264,17.6658,30")
probe("Sensor.Community API (area SA)", "https://data.sensor.community/airrohr/v1/filter/area=43.859,18.429,20")
probe("EEA Air Quality Discomap / API", "https://eeadmz1-downloads-api-appservice.azurewebsites.net/City?country=HR")
probe("EkoAkcija BiH", "https://zrak.ekoakcija.org/")

# 6. EU CORDIS / Kohesio / WBIF / Eurostat
probe("CORDIS API HRV/SRB/BIH", "https://cordis.europa.eu/search/en?q=contenttype%3D%27project%27%20AND%20(%27Zagreb%27%20OR%20%27Belgrade%27%20OR%20%27Sarajevo%27)&p=1&num=5&format=json")
probe("Eurostat JSON API (demo_r_pjanaggr3 / nama_10r_3gdp)", "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nama_10r_3gdp?geo=HR050&geo=RS110&sinceTimePeriod=2020&unit=MIO_EUR")

# 7. Overpass OSM buildings check for Novi Pazar
probe("Overpass NP buildings count", "https://overpass-api.de/api/interpreter", data=b"data=[out:json][timeout:15];way[building](43.125,20.495,43.155,20.535);out count;")
