from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import json
import ssl
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

ctx = ssl.create_default_context()
HDRS = {"User-Agent": "UrbanLabResearch/1.0", "Accept": "application/json, */*"}

def get(url, data=None, headers=None, timeout=18):
    h = dict(HDRS)
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.status, resp.read()

def test(label, fn):
    try:
        res = fn()
        print(f"[OK] {label}: {res}", flush=True)
    except Exception as e:
        print(f"[ERR] {label}: {type(e).__name__}: {e}", flush=True)

# 1. EU TED v3 award notices for Zagreb + SRB + BIH
def probe_ted():
    out = {}
    for label, q in [
        ("HRV_ZG_awards", 'buyer-country IN (HRV) AND buyer-city ~ "Zagreb" AND notice-type IN (can-standard, can-social, can-modif) AND publication-date >= 20240101'),
        ("SRB_any", 'buyer-country IN (SRB) AND publication-date >= 20220101'),
        ("BIH_any", 'buyer-country IN (BIH) AND publication-date >= 20220101'),
    ]:
        payload = json.dumps({
            "query": q,
            "fields": ["publication-number", "publication-date", "notice-type", "buyer-name", "buyer-city", "winner-name", "winner-city", "result-value-lot", "tender-value", "classification-cpv", "notice-title", "received-submissions-type-val"],
            "limit": 3
        }).encode("utf-8")
        st, raw = get("https://api.ted.europa.eu/v3/notices/search", data=payload, headers={"Content-Type": "application/json"})
        d = json.loads(raw)
        out[label] = {"total": d.get("totalNoticeCount"), "sample_keys": list(d.get("notices", [{}])[0].keys()) if d.get("notices") else [], "sample": d.get("notices", [])[:1]}
    return json.dumps(out, ensure_ascii=False)[:1200]

test("EU TED v3", probe_ted)

# 2. BiH EJN OData root entity sets
def probe_ejn():
    st, raw = get("https://open.ejn.gov.ba/")
    return raw.decode("utf-8", errors="replace")[:700]
test("BiH EJN root", probe_ejn)

# 3. data.zagreb.hr full package list (filter interesting)
def probe_zg():
    st, raw = get("https://data.zagreb.hr/api/3/action/package_list")
    pkgs = json.loads(raw)["result"]
    interesting = [p for p in pkgs if any(k in p.lower() for k in ["gup", "prostorn", "dozvol", "nabav", "3d", "katast", "nekretn", "zgrad", "stan", "promet", "zrak", "izbor", "energ", "gradnj", "parcel"])]
    return f"total={len(pkgs)}, interesting({len(interesting)}): {interesting[:35]}"
test("data.zagreb.hr list", probe_zg)

# 4. data.gov.rs Cyrillic & Latin searches
def probe_rs():
    out = {}
    for q in ["јавне", "набавке", "дозволе", "грађевинске", "цеоп", "катастар", "порез", "ваздух"]:
        u = "https://data.gov.rs/api/1/datasets/?q=" + urllib.parse.quote(q) + "&page_size=5"
        st, raw = get(u)
        d = json.loads(raw)
        out[q] = {"total": d.get("total"), "titles": [x.get("title") for x in d.get("data", [])[:3]]}
    return json.dumps(out, ensure_ascii=False)[:1100]
test("data.gov.rs Cyrillic", probe_rs)

# 5. Ookla S3 shapefiles listing (2024 & 2025)
def probe_ookla():
    import xml.etree.ElementTree as ET
    out = []
    for yr in ("2025", "2024"):
        st, raw = get(f"https://ookla-open-data.s3.amazonaws.com/?list-type=2&prefix=shapefiles/performance/type=fixed/year={yr}/&max-keys=10")
        root = ET.fromstring(raw)
        ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
        keys = [(c.find("s3:Key", ns).text, int(c.find("s3:Size", ns).text)) for c in root.findall("s3:Contents", ns)]
        out.extend(keys)
    return out[:8]
test("Ookla S3 shapefiles", probe_ookla)

# 6. Overpass count of buildings in NP & TR + transit stops in SA/NP/TR
def probe_overpass():
    q = """[out:json][timeout:20];
    way[building](43.115,20.485,43.160,20.545); out count;
    way[building](44.210,17.630,44.240,17.700); out count;
    node[highway=bus_stop](43.800,18.280,43.900,18.480); out count;
    """
    st, raw = get("https://overpass-api.de/api/interpreter", data=("data=" + urllib.parse.quote(q)).encode("utf-8"), timeout=25)
    return raw.decode("utf-8", errors="replace")[:700]
test("Overpass NP/TR buildings + SA stops", probe_overpass)

# 7. Inspect local SEPA 2024 CSV & Sjenica 2026 XLSX
def probe_local():
    mdir = Path(str(DB_DIR / "raw" / "wave4" / "mobility_and_permits"))
    sepa = mdir / "srb_air_emissions_2024.csv"
    lines = sepa.read_text(encoding="utf-8-sig", errors="replace").splitlines()[:5]
    import openpyxl
    wb = openpyxl.load_workbook(mdir / "sjenica_property_prices_2026.xlsx", read_only=True)
    ws = wb.active
    sjen_rows = [list(r) for _, r in zip(range(8), ws.iter_rows(values_only=True))]
    wb.close()
    return {"sepa_head": lines, "sjenica_sheets": wb.sheetnames, "sjenica_head": sjen_rows}
test("Local SEPA & Sjenica", probe_local)
