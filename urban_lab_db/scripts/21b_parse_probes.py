import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_net import RAW_DIR, fetch_url

PROBES_DIR = RAW_DIR / "wave4" / "probes"

print("=== 1. BiH open.ejn.gov.ba Swagger Schemas ===")
sw = json.loads((PROBES_DIR / "ejn_swagger.bin").read_text(encoding="utf-8", errors="replace"))
paths = list(sw.get("paths", {}).keys())
print("Total paths:", len(paths), "Award/Contract paths:", [p for p in paths if "Award" in p or "Contract" in p or "Admin" in p][:20])
schemas = sw.get("components", {}).get("schemas", {})
for sname in ["AwardNotice", "Award", "AdministrativeUnit", "ContractingAuthority", "AwardNoticeBase"]:
    if sname in schemas:
        props = list(schemas[sname].get("properties", {}).keys())
        print(f"  Schema {sname}: {props[:25]}")
# Also check exact AwardNotices path parameters
for p in ["/AwardNotices", "/Awards", "/AdministrativeUnits"]:
    if p in sw.get("paths", {}):
        get_op = sw["paths"][p].get("get", {})
        resp_ref = json.dumps(get_op.get("responses", {}).get("200", {}))[:220]
        print(f"  Path {p} params:", [x.get("name") for x in get_op.get("parameters", [])][:10], "resp:", resp_ref)

print("\n=== 2. data.zagreb.hr 3D datasets ===")
zg3d = json.loads((PROBES_DIR / "datazagreb_3d.bin").read_text(encoding="utf-8", errors="replace"))
for pkg in zg3d.get("result", {}).get("results", []):
    res_urls = [(r.get("format"), r.get("url")) for r in pkg.get("resources", []) if (r.get("format") or "").upper() in ("CSV", "GEOJSON", "JSON")]
    print(f"  ZG pkg: {pkg.get('name')} | {pkg.get('title')} | res={res_urls[:3]}")

print("\n=== 3. ZET GTFS links ===")
zet_html = (PROBES_DIR / "zet_gtfs_page.bin").read_text(encoding="utf-8", errors="replace")
zet_links = re.findall(r'href=["\']([^"\']*(?:gtfs|zip)[^"\']*)["\']', zet_html, flags=re.I)
print("  ZET links:", list(dict.fromkeys(zet_links))[:15])

print("\n=== 4. DIP izbori.hr open data links ===")
dip_html = (PROBES_DIR / "dip_open_page.bin").read_text(encoding="utf-8", errors="replace")
dip_links = re.findall(r'href=["\']([^"\']*(?:\.zip|\.csv|\.xlsx|rezultat|zagreb)[^"\']*)["\']', dip_html, flags=re.I)
print("  DIP links:", list(dict.fromkeys(dip_links))[:20])

print("\n=== 5. data.gov.hr izbori & fiskalizacija ===")
for fn in ["datagovhr_izbori.bin", "datagovhr_fiskal.bin"]:
    d = json.loads((PROBES_DIR / fn).read_text(encoding="utf-8", errors="replace"))
    print(f"  {fn}: count={d.get('result', {}).get('count')}")
    for pkg in d.get("result", {}).get("results", [])[:6]:
        print(f"    - {pkg.get('title')} ({len(pkg.get('resources', []))} res) | {(pkg.get('resources') or [{}])[0].get('url')}")

print("\n=== 6. CIK izbori.ba JS endpoints ===")
cik_html = (PROBES_DIR / "cik_2024_root.bin").read_text(encoding="utf-8", errors="replace")
cik_scripts = re.findall(r'(?:src|href)=["\']([^"\']+\.js[^"\']*)["\']', cik_html, flags=re.I)
print("  CIK scripts:", cik_scripts[:15])

print("\n=== 7. data.gov.rs GTFS + Cyrillic queries ===")
gtfs_rs = json.loads((PROBES_DIR / "datagovrs_gtfs.bin").read_text(encoding="utf-8", errors="replace"))
for ds in gtfs_rs.get("data", []):
    title = ds.get("title", "")
    if "београд" in title.lower() or "beograd" in title.lower() or "gtfs" in title.lower():
        urls = [(r.get("format"), r.get("url")) for r in ds.get("resources", [])[:3]]
        print(f"  RS GTFS: {title} | {urls}")

for label, q in [
    ("rs_jn_cyr", "јавне набавке"),
    ("rs_izbori_cyr", "избори"),
    ("rs_rgz_cyr", "непокретности"),
    ("rs_vazduh_cyr", "ваздух"),
    ("rs_dozvole_cyr", "грађевинске дозволе"),
]:
    url = f"https://data.gov.rs/api/1/datasets/?q={urllib.parse.quote(q)}&page_size=8"
    r = fetch_url(url, dest=PROBES_DIR / f"{label}.json", city="common", layer="wave4_probe", source_name=label, timeout=15, retries=1, save_manifest=False)
    if r["ok"]:
        dd = json.loads(r.pop("_bytes", b"").decode("utf-8"))
        print(f"  data.gov.rs '{q}': total={dd.get('total')}")
        for ds in dd.get("data", [])[:4]:
            res0 = (ds.get("resources") or [{}])[0]
            print(f"    - {ds.get('title')} | res_n={len(ds.get('resources',[]))} | {res0.get('format')} {res0.get('url')}")
