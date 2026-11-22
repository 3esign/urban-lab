from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import os, json, re
from pathlib import Path
import pypdf

BASE = Path(str(DB_DIR))
OUT = BASE / "raw" / "wave2_l"
OUT.mkdir(parents=True, exist_ok=True)

def dump_pdf_pages(pdf_path, label, keywords):
    print(f"\n================ {label} ================")
    r = pypdf.PdfReader(str(pdf_path))
    hits = {}
    for idx, page in enumerate(r.pages):
        txt = page.extract_text() or ""
        tl = txt.lower()
        matched = [k for k in keywords if k in tl]
        if matched:
            hits[idx + 1] = {"matched": matched, "text": txt}
    print(f"Matched {len(hits)}/{len(r.pages)} pages")
    for pno, info in sorted(hits.items()):
        lines = [l.strip() for l in info["text"].splitlines() if l.strip()]
        head = " | ".join(lines[:3])[:130]
        print(f"  p.{pno:>3d} [{','.join(info['matched'][:4])}]: {head}")
    return hits

# 1. FZS SBK 2025: ALL 12 municipalities of SBK (Travnik, Vitez, Novi Travnik, Busovaca, Kiseljak, Donji Vakuf, Bugojno, Jajce...)
# plus forestry (sječa drva), agriculture (pšenica), tourism, construction
sbk_hits = dump_pdf_pages(
    BASE / "raw/travnik/fzs_sbk_travnik_2025.pdf",
    "FZS SBK 2025 (Travnik + Lasvanska dolina + Kiseljak)",
    ["vitez", "šumarstv", "sječa", "pšenic", "poljoprivred", "turiz", "noćenj", "građevin", "stanov", "plać", "zaposlen", "nezaposlen"]
)
(OUT / "parsed_fzs_sbk_2025_pages.json").write_text(json.dumps(sbk_hits, ensure_ascii=False, indent=2), encoding="utf-8")

# 2. FZS KS 2026: forestry, agriculture, tourism, construction, transport
ks_hits = dump_pdf_pages(
    BASE / "raw/sarajevo/fzs_kanton_sarajevo_2026.pdf",
    "FZS Kanton Sarajevo 2026 (Sarajevo sectors)",
    ["šumarstv", "sječa", "pšenic", "poljoprivred", "turiz", "noćenj", "građevin", "prijevoz", "završen"]
)
(OUT / "parsed_fzs_ks_2026_pages.json").write_text(json.dumps(ks_hits, ensure_ascii=False, indent=2), encoding="utf-8")

# 3. ZPR KS Izvjestaj o razvoju 2025: GDP, export/import, tourism, construction, spatial links
zpr_hits = dump_pdf_pages(
    BASE / "raw/sarajevo/zpr_ks_izvjestaj_razvoj_2025.pdf",
    "ZPR KS Izvjestaj o razvoju 2025",
    ["bdp", "bruto domaći", "izvoz", "uvoz", "turist", "noćenj", "šum", "poljoprivred", "koridor", "aerodrom"]
)
(OUT / "parsed_zpr_ks_2025_pages.json").write_text(json.dumps(zpr_hits, ensure_ascii=False, indent=2), encoding="utf-8")

# 4. Also analyze existing APR JSONL for Beograd & Novi Pazar for the S->L Bakery Supply Chain!
print("\n================ APR S->L BAKERY SUPPLY CHAIN (BEOGAD & NOVI PAZAR CORE) ================")
SUPPLY_NACE = {
    "1071": "Pekare (proizvodnja hleba, svežeg peciva)",
    "1072": "Dvopek, keks, trajno pecivo",
    "1061": "Mlinovi (proizvodnja mlinskih proizvoda)",
    "0111": "Gajenje žita (pšenica, kukuruz)",
    "0210": "Gajenje šuma",
    "0220": "Seča drveća",
    "1610": "Rezanje i obrada drveta (pilane)",
    "4621": "Trgovina na veliko žitom i stočnom hranom",
    "4636": "Trgovina na veliko šećerom, čokoladom i slatkišima",
    "4673": "Trgovina na veliko drvetom i građ. materijalom",
    "4724": "Trgovina na malo hlebom, testeninama i kolačima",
}

supply_summary = {}
for cid, path in [
    ("beograd", BASE / "raw/beograd/apr_beograd_companies.jsonl"),
    ("novi_pazar", BASE / "raw/novi_pazar/apr_novi_pazar_companies.jsonl"),
]:
    stats = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            nace = str(r.get("SifraDelatnosti") or "").strip()
            if nace in SUPPLY_NACE:
                st = stats.setdefault(nace, {"desc": SUPPLY_NACE[nace], "firms": 0, "with_fi": 0, "employees": 0, "revenue_eur": 0.0, "profit_eur": 0.0, "top_firms": []})
                st["firms"] += 1
                fi = r.get("fi")
                if fi:
                    st["with_fi"] += 1
                    emp = int(fi.get("BrojZaposlenih") or 0)
                    rev = float(fi.get("PoslovniPrihod") or fi.get("UkupniPrihodi") or 0) * 1000.0 / 117.0
                    prof = float(fi.get("NetoDobitak") or 0) * 1000.0 / 117.0
                    st["employees"] += emp
                    st["revenue_eur"] += rev
                    st["profit_eur"] += prof
                    st["top_firms"].append((rev, r.get("PoslovnoIme") or r.get("Naziv") or "", emp, r.get("SifraOpstine")))
    for nace, st in sorted(stats.items()):
        st["top_firms"].sort(reverse=True)
        st["top_firms"] = [{"name": x[1], "revenue_eur": round(x[0], 0), "employees": x[2], "muni": x[3]} for x in st["top_firms"][:5]]
        st["revenue_eur"] = round(st["revenue_eur"], 0)
        st["profit_eur"] = round(st["profit_eur"], 0)
        print(f"  {cid:11s} | {nace} {st['desc'][:36]:36s} | firms={st['firms']:>4} | emp={st['employees']:>5} | rev={st['revenue_eur']/1e6:>7.2f} M EUR")
    supply_summary[cid] = stats

(OUT / "apr_bakery_supply_chain_core.json").write_text(json.dumps(supply_summary, ensure_ascii=False, indent=2), encoding="utf-8")
print("DONE 10_extract_wave2_pdfs.py")
