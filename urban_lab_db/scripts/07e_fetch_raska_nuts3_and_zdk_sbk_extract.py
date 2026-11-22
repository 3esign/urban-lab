import json, sys, re
from pathlib import Path
import pypdf

sys.path.insert(0, str(Path(__file__).parent))
from common_net import RAW_DIR, fetch_url, append_manifest, sha256_file

WL = RAW_DIR / "wave2_l"
WXL = RAW_DIR / "wave2_xl"

# 1. Eurostat NUTS3 GDP for ALL RS21x regions (to capture Raska oblast = Novi Pazar/Tutin/Raska & Zlatiborska = Sjenica)
url_rs21 = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nama_10r_3gdp"
    "?format=JSON&lang=EN&geo=RS211&geo=RS212&geo=RS213&geo=RS214&geo=RS215&geo=RS216&geo=RS217&geo=RS218&sinceTimePeriod=2019"
)
r = fetch_url(url_rs21, dest=WXL / "eurostat_nama_10r_3gdp_rs21.json", city="novi_pazar", layer="wave2_xl_eurostat", source_name="Eurostat NUTS3 GDP Sumadija & Western Serbia (incl. Raska & Zlatibor)", timeout=45)
print(f"Eurostat RS21x NUTS3: ok={r.get('ok')} bytes={r.get('bytes',0):,}")
if r.get("ok"):
    d = json.loads((WXL / "eurostat_nama_10r_3gdp_rs21.json").read_text(encoding="utf-8"))
    cats = d["dimension"]["geo"]["category"]["label"]
    print("  RS21x geos:", cats)

# 2. Extract FZS ZDK 2026 pages (Visoko, Zenica, Kakanj, Breza) + FZS KS 2026 (forestry, agri, trade, tourism) + FZS SBK 2025 (forestry, agri, trade, tourism)
def dump_pages_text(pdf_path, pages):
    r = pypdf.PdfReader(str(pdf_path))
    out = {}
    for p in pages:
        if 1 <= p <= len(r.pages):
            out[p] = r.pages[p-1].extract_text() or ""
    return out

zdk_pages = dump_pages_text(WL / "fzs_zdk_2025.pdf", [8, 12, 13, 14, 15, 16, 17, 21, 22, 23, 29, 31])
(WL / "parsed_fzs_zdk_2026_key.json").write_text(json.dumps(zdk_pages, ensure_ascii=False, indent=2), encoding="utf-8")
print("\n=== ZDK KEY EXCERPTS (p.14 pop, p.17 emp/wage, p.21 wheat, p.23 forestry, p.29 trade, p.31 tourism) ===")
for p in [14, 17, 21, 23, 29, 31]:
    txt = zdk_pages.get(p, "")
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    print(f"--- ZDK p.{p} ---")
    for l in lines[:18]:
        print("  ", l[:120])

# Also inspect FZS KS 2026 forestry, agriculture, trade, tourism & FZS SBK 2025 forestry, agriculture, trade, tourism
print("\n=== FZS KS 2026 FORESTRY/AGRI/TRADE/TOURISM ===")
ks_pdf = pypdf.PdfReader(str(RAW_DIR / "sarajevo/fzs_kanton_sarajevo_2026.pdf"))
for p in [19, 20, 21, 22, 29, 31]:
    if p <= len(ks_pdf.pages):
        lines = [l.strip() for l in (ks_pdf.pages[p-1].extract_text() or "").splitlines() if l.strip()]
        print(f"--- KS p.{p} ---")
        for l in lines[:14]:
            print("  ", l[:120])

print("\n=== FZS SBK 2025 FORESTRY/AGRI/TRADE/TOURISM ===")
sbk_pdf = pypdf.PdfReader(str(RAW_DIR / "travnik/fzs_sbk_travnik_2025.pdf"))
for p in [19, 21, 28, 30]:
    if p <= len(sbk_pdf.pages):
        lines = [l.strip() for l in (sbk_pdf.pages[p-1].extract_text() or "").splitlines() if l.strip()]
        print(f"--- SBK p.{p} ---")
        for l in lines[:14]:
            print("  ", l[:120])
