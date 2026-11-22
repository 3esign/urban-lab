from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import json, os, sys
import pypdf

BASE = str(DB_DIR)

def inspect_pdf_toc(path, label, max_pages=15):
    print(f"\n=== PDF: {label} ({os.path.getsize(path):,} B) ===")
    r = pypdf.PdfReader(path)
    print(f"Total pages: {len(r.pages)}")
    for i in range(min(max_pages, len(r.pages))):
        txt = (r.pages[i].extract_text() or "").strip()
        first_lines = [l.strip() for l in txt.splitlines() if l.strip()][:6]
        if first_lines:
            print(f"  p.{i+1}: " + " | ".join(first_lines)[:180])

inspect_pdf_toc(os.path.join(BASE, "raw/common/rzs_opstine_i_regioni_2025.pdf"), "RZS Opstine i regioni 2025", 12)
inspect_pdf_toc(os.path.join(BASE, "raw/sarajevo/fzs_kanton_sarajevo_2026.pdf"), "FZS Kanton Sarajevo 2026", 12)
inspect_pdf_toc(os.path.join(BASE, "raw/travnik/fzs_sbk_travnik_2025.pdf"), "FZS SBK Travnik 2025", 12)
inspect_pdf_toc(os.path.join(BASE, "raw/sarajevo/zpr_ks_izvjestaj_razvoj_2025.pdf"), "ZPR KS Izvjestaj razvoj 2025", 10)

for fn in ["geoboundaries_HRV_ADM2.geojson", "geoboundaries_BIH_ADM3.geojson", "geoboundaries_SRB_ADM2.geojson"]:
    p = os.path.join(BASE, "raw/common", fn)
    with open(p, "r", encoding="utf-8") as f:
        gj = json.load(f)
    feats = gj.get("features", [])
    names = [ft.get("properties", {}).get("shapeName", "") for ft in feats]
    print(f"\n=== GEO: {fn} | count={len(feats)} ===")
    print("  sample:", names[:15])
    # check specific hinterland matches
    hits = [n for n in names if any(k in n.lower() for k in [
        "zagreb", "gorica", "samobor", "zapre", "nedelja", "dugo selo",
        "vitez", "travnik", "busova", "kiseljak", "visoko", "zenica", "kakanj", "breza", "pale", "sokolac", "isto",
        "panče", "pance", "pazova", "inđij", "indjij", "tutin", "sjenic", "rašk", "rask"
    ])]
    print("  hinterland hits:", hits[:40])
