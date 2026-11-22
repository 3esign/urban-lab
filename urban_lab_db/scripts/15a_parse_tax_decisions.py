from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import html, json, re
from pathlib import Path

BASE = Path(str(DB_DIR))
RAW = BASE / "raw"
OUT = RAW / "wave3"
OUT.mkdir(parents=True, exist_ok=True)

def clean_html(p):
    txt = p.read_text(encoding="utf-8", errors="replace")
    txt = re.sub(r"<(br|p|div|tr|li|h[1-6])[^>]*>", "\n", txt, flags=re.I)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = html.unescape(txt)
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n\s*\n+", "\n", txt).strip()
    return txt

# 1. Novi Pazar
np_txt = clean_html(RAW / "novi_pazar" / "novi_pazar_odluka_zone_granice.htm")
(OUT / "novi_pazar_odluka_clean.txt").write_text(np_txt, encoding="utf-8")

np_zones = {}
for label, pat in [
    ("I zona", r"Prva zona obuhvata ulice:(.*?)(?=Druga zona obuhvata)"),
    ("II zona", r"Druga zona obuhvata ulice:(.*?)(?=Treća zona obuhvata)"),
    ("III zona", r"Treća zona obuhvata ulice:(.*?)(?=Četvrta zona obuhvata)"),
    ("IV zona", r"Četvrta zona obuhvata ulice:(.*?)(?=Peta zona obuhvata)"),
    ("V zona", r"Peta zona obuhvata ulice:(.*?)(?=Šesta zona obuhvata)"),
    ("VI zona", r"Šesta zona obuhvata sela i naselja i to:(.*?)(?=Sedma zona obuhvata)"),
    ("VII zona", r"Sedma zona obuhvata sela i naselja i to:(.*?)(?=Član 3|$)"),
]:
    m = re.search(pat, np_txt, flags=re.S | re.I)
    body = m.group(1).strip() if m else ""
    np_zones[label] = body
    print(f"[NP] {label:8s}: {len(body):>4} chars | sample={body[:120]}")

(OUT / "novi_pazar_zones_parsed.json").write_text(json.dumps(np_zones, ensure_ascii=False, indent=2), encoding="utf-8")

# 2. Beograd
bg_txt = clean_html(RAW / "beograd" / "beograd_odluka_zone_granice.htm")
(OUT / "beograd_odluka_clean.txt").write_text(bg_txt, encoding="utf-8")

spisak_idx = bg_txt.find("SPISAK ZONA")
spisak = bg_txt[spisak_idx:] if spisak_idx >= 0 else bg_txt
headers = [
    "PRVA ZONA - EKSTRA ZONA STANOVANJA",
    "PRVA ZONA - EKSTRA ZONA POSLOVANJA",
    "PRVA ZONA",
    "DRUGA ZONA",
    "TREĆA ZONA",
    "ČETVRTA ZONA",
    "PETA ZONA",
    "ŠESTA ZONA",
    "SEDMA ZONA",
    "OSMA ZONA",
    "ZONA ZAŠTITE ZELENILA 1",
    "ZONA ZAŠTITE ZELENILA 2",
    "ZONA ULAZNIH PRAVACA",
    "ZONA SPECIFIČNIH NAMENA",
]
# Find exact line-level occurrences
lines = [l.strip() for l in spisak.split("\n") if l.strip()]
bg_sections = {}
cur_h = None
for l in lines:
    if l in headers:
        cur_h = l
        bg_sections[cur_h] = []
    elif cur_h is not None:
        bg_sections[cur_h].append(l)

print("\n[BG] Parsed sections:")
bg_summary = {}
for h, ls in bg_sections.items():
    full = "\n".join(ls)
    # Extract mentioned KO / settlements
    kos = re.findall(r"Obuhvata katastarsk[eu] opštin[eu]:([^\n]+)", full, flags=re.I)
    bg_summary[h] = {"lines": len(ls), "chars": len(full), "ko_mentions": kos, "text": full}
    print(f"  {h:38s}: {len(ls):>3} lines, {len(full):>5} chars, ko_clauses={len(kos)}")
    for k in kos[:4]:
        print(f"     KO: {k.strip()[:140]}")

(OUT / "beograd_zones_parsed.json").write_text(json.dumps(bg_summary, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nDONE 15a_parse_tax_decisions.py")
