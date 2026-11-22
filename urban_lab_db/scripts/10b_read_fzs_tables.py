from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import json
from pathlib import Path

OUT = Path(str(DB_DIR / "raw" / "wave2_l"))

def show_pages(fn, pages):
    d = json.loads((OUT / fn).read_text(encoding="utf-8"))
    print(f"\n================ {fn} ================")
    for p in pages:
        t = d.get(str(p), {}).get("text", "")
        if t:
            print(f"\n--- PAGE {p} ---")
            print(t[:2600])

show_pages("parsed_fzs_sbk_2025_pages.json", [8, 12, 15, 16, 19, 21, 28, 30])
show_pages("parsed_fzs_ks_2026_pages.json", [19, 20, 21, 22, 26, 29, 31])
show_pages("parsed_zpr_ks_2025_pages.json", [6, 14, 30, 35, 84])
