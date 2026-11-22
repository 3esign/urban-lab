import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_net import RAW_DIR, fetch_url

PROBES_DIR = RAW_DIR / "wave4" / "probes"
sw = json.loads((PROBES_DIR / "ejn_swagger.bin").read_text(encoding="utf-8", errors="replace"))
schemas = sw.get("components", {}).get("schemas", {})
for s in ["AwardNoticeExtendedListDto", "AwardExtendedListDto", "ContractingAuthorityExtendedListDto", "LotContractExtendedListDto", "AdministrativeUnitExtendedListDto"]:
    if s in schemas:
        print(f"SCHEMA {s}:", list(schemas[s].get("properties", {}).keys()))

# Test fetching 2 AwardNotices without orderby, and ContractingAuthorities filtered by Sarajevo/Travnik
for name, url in [
    ("ejn_an_sample", "https://open.ejn.gov.ba/AwardNotices?$top=2"),
    ("ejn_ca_sa", "https://open.ejn.gov.ba/ContractingAuthorities?$top=5&$filter=contains(Name,'Sarajevo')"),
    ("ejn_ca_tr", "https://open.ejn.gov.ba/ContractingAuthorities?$top=5&$filter=contains(Name,'Travnik')"),
    ("cik_race4_js", "https://www.izbori.ba/rezultati_izbora/js/home-index-race-4.min.js?30"),
    ("cik_race5_js", "https://www.izbori.ba/rezultati_izbora/js/home-index-race-5.min.js?20"),
    ("rs_orgs_ujn", "https://data.gov.rs/api/1/organizations/?q=nabavk"),
    ("rs_orgs_rik", "https://data.gov.rs/api/1/organizations/?q=izborn"),
    ("rs_datasets_nabavk", "https://data.gov.rs/api/1/datasets/?q=nabavke&page_size=10"),
    ("rs_datasets_port", "https://data.gov.rs/api/1/datasets/?organization=kantselarija-za-javne-nabavke&page_size=10"),
]:
    r = fetch_url(url, dest=PROBES_DIR / f"{name}.bin", city="common", layer="wave4_probe", source_name=name, timeout=20, retries=1, save_manifest=False)
    if r["ok"]:
        txt = r.pop("_bytes", b"").decode("utf-8", errors="replace")
        if "cik_race" in name:
            urls = re.findall(r'["\']([^"\']*(?:json|data|Results|Basic|Polling|Race|Race\d)[^"\']*)["\']', txt, flags=re.I)
            print(f"[OK] {name}: len={len(txt)} | json-like={list(dict.fromkeys(urls))[:20]}")
        else:
            print(f"[OK] {name}: len={len(txt)} | {txt[:260]}")
    else:
        print(f"[FAIL] {name}: {r.get('error')}")
