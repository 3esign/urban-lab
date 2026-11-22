import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_net import RAW_DIR, fetch_url

OUT_DIR = RAW_DIR / "wave4" / "probes"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 1. Check CIK izbori.ba dataService JS files from cik_2024_root.bin
cik_html = (OUT_DIR / "cik_2024_root.bin").read_text(encoding="utf-8", errors="replace")
all_js = re.findall(r'src=["\']([^"\']+\.js[^"\']*)["\']', cik_html, flags=re.I)
print("CIK all JS files:", all_js)
for js in all_js:
    if "data" in js.lower() or "service" in js.lower() or "app" in js.lower() or "custom" in js.lower():
        full = js if js.startswith("http") else f"https://www.izbori.ba{js}"
        r = fetch_url(full, dest=OUT_DIR / f"cik_{Path(js.split('?')[0]).name}", city="common", layer="wave4_probe", source_name="cik_js", timeout=15, retries=1, save_manifest=False)
        if r["ok"]:
            txt = r.pop("_bytes", b"").decode("utf-8", errors="replace")
            api_hits = re.findall(r'["\']([^"\']*(?:api|json|data|Basic|Polling|Race|Electoral|Rezultati)[^"\']*)["\']', txt, flags=re.I)
            print(f"  CIK JS {js}: len={len(txt)} hits={list(dict.fromkeys(api_hits))[:25]}")

# 2. Check DIP open data hub page (/site/ostalo/opce-informacije/rezultati-izbora-otvoreni-podaci/477)
r_dip = fetch_url(
    "https://www.izbori.hr/site/ostalo/opce-informacije/rezultati-izbora-otvoreni-podaci/477",
    dest=OUT_DIR / "dip_477.html",
    city="zagreb",
    layer="wave4_probe",
    source_name="dip_477",
    timeout=20,
    retries=1,
    save_manifest=False,
)
if r_dip["ok"]:
    h = r_dip.pop("_bytes", b"").decode("utf-8", errors="replace")
    zips = re.findall(r'href=["\']([^"\']*(?:\.zip|\.csv|\.xlsx|2024|2025)[^"\']*)["\']', h, flags=re.I)
    print("\nDIP 477 links:", list(dict.fromkeys(zips))[:30])

# 3. Check ZET GTFS download page
r_zet = fetch_url(
    "https://www.zet.hr/preuzimanja/odredbe/datoteke-u-gtfs-formatu/669",
    dest=OUT_DIR / "zet_dl.html",
    city="zagreb",
    layer="wave4_probe",
    source_name="zet_dl",
    timeout=20,
    retries=1,
    save_manifest=False,
)
if r_zet["ok"]:
    h = r_zet.pop("_bytes", b"").decode("utf-8", errors="replace")
    zlinks = re.findall(r'href=["\']([^"\']*(?:gtfs|zip|UserDocsImages)[^"\']*)["\']', h, flags=re.I)
    print("\nZET dl links:", list(dict.fromkeys(zlinks))[:20])

# 4. Check RZS Building Permits JSON sample (050202IND01)
r_rzs = fetch_url(
    "https://opendata.stat.gov.rs/data/WcfJsonRestService.Service1.svc/dataset/050202IND01/1/json",
    dest=OUT_DIR / "rzs_050202IND01.json",
    city="common",
    layer="wave4_probe",
    source_name="rzs_permits",
    timeout=30,
    retries=1,
    save_manifest=False,
)
if r_rzs["ok"]:
    raw = r_rzs.pop("_bytes", b"")
    print(f"\nRZS 050202IND01 OK: {len(raw)} bytes | preview={raw[:300].decode('utf-8', errors='replace')}")
else:
    print(f"\nRZS 050202IND01 FAIL: {r_rzs.get('error')}")

# 5. Check RIK rezultati / rezultatiizbora.rs
for name, url in [
    ("rik_api_test", "https://www.rik.parlament.gov.rs/extfile/sr/files/additionalDocuments/"),
    ("rez_izb_rs", "https://rezultatiizbora.rs/"),
    ("ookla_list", "https://ookla-open-data.s3.amazonaws.com/?list-type=2&prefix=shapefiles/performance/type=fixed/year=2025/"),
]:
    rr = fetch_url(url, dest=OUT_DIR / f"{name}.bin", city="common", layer="wave4_probe", source_name=name, timeout=20, retries=1, save_manifest=False)
    if rr["ok"]:
        raw = rr.pop("_bytes", b"")
        print(f"[OK] {name}: {len(raw)} bytes | {raw[:240].decode('utf-8', errors='replace').replace(chr(10),' ')}")
    else:
        print(f"[FAIL] {name}: {rr.get('error')}")
