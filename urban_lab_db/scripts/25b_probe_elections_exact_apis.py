import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_net import RAW_DIR, fetch_url

PDIR = RAW_DIR / "wave4" / "probes"

print("=== 1. CIK izbori.ba apiUrl extraction ===")
cik_html = (PDIR / "cik_2024_root.bin").read_text(encoding="utf-8", errors="replace")
print("CIK apiUrl / input hidden matches:", re.findall(r'(?:apiUrl|resId|hdn[A-Za-z0-9_]+)[^>\n]{0,120}', cik_html)[:15])
r_hi = fetch_url("https://www.izbori.ba/rezultati_izbora/js/home-index.min.js?20", dest=PDIR / "cik_home_index.js", city="common", layer="wave4_probe", source_name="cik_hi", timeout=15, retries=1, save_manifest=False)
if r_hi["ok"]:
    txt = r_hi.pop("_bytes", b"").decode("utf-8", errors="replace")
    print("CIK home-index.min.js URLs:", re.findall(r'["\']([^"\']*(?:api|http|data|Basic|Polling|Electoral|Candidate|Party|Result)[^"\']*)["\']', txt, flags=re.I)[:35])

print("\n=== 2. rezultatiizbora.rs data/JS extraction ===")
rez_html = (PDIR / "rez_izb_rs.bin").read_text(encoding="utf-8", errors="replace")
print("rezultatiizbora.rs scripts/json:", re.findall(r'(?:src|href)=["\']([^"\']+\.(?:js|json|csv)[^"\']*)["\']', rez_html)[:20])
print("rezultatiizbora.rs inline API/data hints:", re.findall(r'["\']([^"\']*(?:api|json|csv|beograd|pazar|izbori|data)[^"\']*)["\']', rez_html, flags=re.I)[:25])

print("\n=== 3. DIP izbori.hr direct archive URLs probe ===")
for name, url in [
    ("dip_parl_2024_page", "https://www.izbori.hr/arhiva-izbora/index.html#/app/parlament-2024"),
    ("dip_parl_2024_zip", "https://www.izbori.hr/arhiva-izbora/data/parlament/2024/zip/rezultati.zip"),
    ("dip_lok_2025_zip", "https://www.izbori.hr/arhiva-izbora/data/lokalni/2025/zip/rezultati.zip"),
    ("dip_lok_2021_zip", "https://www.izbori.hr/arhiva-izbora/data/lokalni/2021/zip/rezultati.zip"),
    ("dip_arhiva_js", "https://www.izbori.hr/arhiva-izbora/data/lokalni/2025/index.json"),
    ("zet_gtfs_direct", "https://www.zet.hr/gtfs-scheduled/latest"),
    ("zet_gtfs_zip2", "https://www.zet.hr/UserDocsImages/Prilozi/gtfs.zip"),
]:
    r = fetch_url(url, dest=PDIR / f"{name}.bin", city="zagreb", layer="wave4_probe", source_name=name, timeout=15, retries=1, save_manifest=False)
    if r["ok"]:
        raw = r.pop("_bytes", b"")
        print(f"  [OK]   {name:20s}: bytes={len(raw):9d} ctype={r.get('content_type','')[:45]} head={raw[:60]!r}")
    else:
        print(f"  [FAIL] {name:20s}: {r.get('error')}")
