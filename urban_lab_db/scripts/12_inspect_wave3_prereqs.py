from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import os, re, json, sqlite3, struct, urllib.request
from pathlib import Path

BASE = Path(str(DB_DIR))
RAW = BASE / "raw"
DB = BASE / "curated" / "urban_lab_5cities.sqlite"

conn = sqlite3.connect(DB)
print("=== 1. property_zones_prices ===")
cols = [r[1] for r in conn.execute("PRAGMA table_info(property_zones_prices)")]
print("Cols:", cols)
for r in conn.execute("SELECT * FROM property_zones_prices ORDER BY city_id, rowid"):
    print(" ", r)

print("\n=== 2. companies_sr_hinterland breakdown ===")
for r in conn.execute("SELECT city_hub, muni_code, muni_name, count(*), sum(employees) FROM companies_sr_hinterland GROUP BY city_hub, muni_code, muni_name ORDER BY city_hub, count(*) DESC"):
    print(" ", r)

print("\n=== 3. NOVI PAZAR ODLUKA ZONE GRANICE (FULL TEXT) ===")
np_p = RAW / "novi_pazar" / "novi_pazar_odluka_zone_granice.htm"
if np_p.exists():
    txt = np_p.read_text(encoding="utf-8", errors="replace")
    clean = re.sub(r"<(br|p|div|tr|li)[^>]*>", "\n", txt, flags=re.I)
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = re.sub(r"[ \t]+", " ", clean)
    clean = re.sub(r"\n\s*\n+", "\n", clean).strip()
    print(clean[:9000])

print("\n=== 4. BEOGRAD ODLUKA ZONE GRANICE (STRUCTURE / HEADINGS) ===")
bg_p = RAW / "beograd" / "beograd_odluka_zone_granice.htm"
if bg_p.exists():
    txt = bg_p.read_text(encoding="utf-8", errors="replace")
    clean = re.sub(r"<(br|p|div|tr|li)[^>]*>", "\n", txt, flags=re.I)
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = re.sub(r"[ \t]+", " ", clean)
    clean = re.sub(r"\n\s*\n+", "\n", clean).strip()
    print(f"Total clean chars: {len(clean)}")
    for line in clean.split("\n"):
        if any(k in line.lower() for k in ["zona", "član", "clan", "opštin", "opstin", "ekstra", "ulaznih", "zaštite", "specifi"]):
            if len(line) < 220:
                print("  >", line)

print("\n=== 5. RZS POPIS POLJOPRIVREDE 2023 HTML LINKS ===")
ag_html = RAW / "wave2_l" / "rzs_popis_poljoprivrede_2023.html"
if ag_html.exists():
    txt = ag_html.read_text(encoding="utf-8", errors="replace")
    links = re.findall(r'href=["\']([^"\']+)["\']', txt, flags=re.I)
    for l in sorted(set(links)):
        if any(k in l.lower() for k in ["rezult", "tabel", "excel", "xlsx", "csv", "opstin", "baza", "data.stat", "publik", "pdf", "saop", "sr-latn"]):
            print(" ", l)

print("\n=== 6. GEOJSON ATTRIBUTE KEYS (BG 17 opstina & NP 99 naselja) ===")
for fn in ["beograd_17_opstina.geojson", "novi_pazar_99_naselja_popis2022.geojson"]:
    gj = json.loads((BASE / "curated" / "boundaries" / fn).read_text(encoding="utf-8"))
    print(f"  {fn}: {len(gj['features'])} features, sample props:", gj["features"][0]["properties"])
    if "novi_pazar" in fn:
        names = [f["properties"].get("naselje_imel") or f["properties"].get("NAZIV") or f["properties"].get("name") or str(list(f["properties"].values())[:3]) for f in gj["features"]]
        print("   NP sample names:", names[:20])

print("\n=== 7. GEOFABRIK LANDUSE LAYER SIZES ===")
def list_zip_landuse(country):
    url = f"https://download.geofabrik.de/europe/{country}-latest-free.shp.zip"
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "SvemirUrbanLab/3.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        total_len = int(resp.headers["Content-Length"])
    req = urllib.request.Request(url, headers={"User-Agent": "SvemirUrbanLab/3.0", "Range": f"bytes={max(0, total_len-65536)}-{total_len-1}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        tail = resp.read()
    idx = tail.rfind(b"PK\x05\x06")
    _, _, _, _, total_entries, cd_size, cd_offset, _ = struct.unpack_from("<4sHHHHIIH", tail, idx)
    req = urllib.request.Request(url, headers={"User-Agent": "SvemirUrbanLab/3.0", "Range": f"bytes={cd_offset}-{cd_offset+cd_size-1}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        cd = resp.read()
    pos = 0
    print(f"-- {country} --")
    while pos < len(cd):
        if cd[pos:pos+4] != b"PK\x01\x02": break
        (_, _, _, _, cm, _, _, _, csize, usize, fnl, exl, cml, _, _, _, loff) = struct.unpack_from("<4sHHHHHHIIIHHHHHII", cd, pos)
        fn = cd[pos+46:pos+46+fnl].decode("utf-8", errors="replace")
        if any(k in fn for k in ["landuse", "natural_a", "roads"]) and fn.endswith((".shp", ".dbf")):
            print(f"  {fn:35s} comp={csize/(1024*1024):6.2f} MB  uncomp={usize/(1024*1024):6.2f} MB")
        pos += 46 + fnl + exl + cml

for c in ["serbia", "croatia", "bosnia-herzegovina"]:
    try:
        list_zip_landuse(c)
    except Exception as e:
        print(f"  ERR {c}: {e}")
