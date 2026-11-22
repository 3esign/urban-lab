from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import json, re
from pathlib import Path
import openpyxl

BASE = Path(str(DB_DIR))
AGRI_DIR = BASE / "raw" / "wave3" / "rzs_agri2023"
OPS_P = BASE / "raw" / "wave3" / "rzs_srbija_sve_opstine.geojson"
OUT_P = BASE / "raw" / "wave3" / "rzs_agri2023_all_munis.json"

CYR_TO_LAT = {
    "А":"A","Б":"B","В":"V","Г":"G","Д":"D","Ђ":"Đ","Е":"E","Ж":"Ž","З":"Z","И":"I","Ј":"J","К":"K","Л":"L","Љ":"Lj",
    "М":"M","Н":"N","Њ":"Nj","О":"O","П":"P","Р":"R","С":"S","Т":"T","Ћ":"Ć","У":"U","Ф":"F","Х":"H","Ц":"C","Ч":"Č","Џ":"Dž","Ш":"Š",
    "а":"a","б":"b","в":"v","г":"g","д":"d","ђ":"đ","е":"e","ж":"ž","з":"z","и":"i","ј":"j","к":"k","л":"l","љ":"lj",
    "м":"m","н":"n","њ":"nj","о":"o","п":"p","р":"r","с":"s","т":"t","ћ":"ć","у":"u","ф":"f","х":"h","ц":"c","ч":"č","џ":"dž","ш":"š",
}
def cyr2lat(s):
    if s is None: return ""
    return "".join(CYR_TO_LAT.get(ch, ch) for ch in str(s))

def norm_key(s):
    t = cyr2lat(s).upper().strip()
    t = re.sub(r"\s+", " ", t)
    for a, b in [("Č","C"),("Ć","C"),("Š","S"),("Ž","Z"),("Đ","DJ"),("DŽ","DZ")]:
        t = t.replace(a, b)
    t = t.replace(" - ", "-").replace(" – ", "-")
    t = re.sub(r"-GRAD$", "", t).strip()
    t = re.sub(r"^GRAD ", "", t).strip()
    return t

def to_num(v):
    if v is None: return None
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip().replace(" ", "").replace("\xa0", "").replace(",", ".")
    if s in ("", "-", "–", "...", "z", "*"):
        return None
    try: return float(s)
    except: return None

# Load RZS official municipality code mapping
rzs_name_to_code = {}
rzs_code_meta = {}
if OPS_P.exists():
    gj = json.loads(OPS_P.read_text(encoding="utf-8"))
    for f in gj["features"]:
        pr = f["properties"]
        code = str(pr.get("matbro") or "").strip()
        nm = str(pr.get("imeolat") or cyr2lat(pr.get("imeo")) or "").strip()
        if code and nm:
            rzs_code_meta[code] = {"name": nm, "okrug": cyr2lat(pr.get("okrug","")), "region": cyr2lat(pr.get("region",""))}
            k = norm_key(nm)
            rzs_name_to_code[k] = code
            if "-" in k:
                rzs_name_to_code[k.split("-", 1)[1].strip()] = code

def parse_excel_rows(path, start_row, col_map):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = []
    cur_region = ""
    cur_oblast = ""
    for i, r in enumerate(ws.iter_rows(values_only=True)):
        if i < start_row: continue
        raw_name = r[0] if len(r) > 0 else None
        if raw_name is None: continue
        name = cyr2lat(str(raw_name)).strip()
        if not name or name.startswith("1)") or name.startswith("Napomena") or name.startswith("Izvor") or name.startswith("*"):
            continue
        low = name.lower()
        if "republika srbija" in low or low.startswith("srbija –") or low.startswith("srbija -"):
            level = "macro"
        elif "region" in low:
            cur_region = name
            level = "region"
        elif "oblast" in low:
            cur_oblast = name
            level = "oblast"
        else:
            level = "municipality"

        rec = {"raw_name": name, "level": level, "region": cur_region, "oblast": cur_oblast}
        for field, idx in col_map.items():
            rec[field] = to_num(r[idx]) if idx < len(r) else None
        rows.append(rec)
    wb.close()
    return rows

# Verify Tabela 2.3 column indices dynamically first
wb23 = openpyxl.load_workbook(AGRI_DIR / "pp2023_03_tabela-23_cir.xlsx", read_only=True, data_only=True)
ws23 = wb23[wb23.sheetnames[0]]
h23 = [list(r) for i, r in enumerate(ws23.iter_rows(values_only=True)) if i < 5]
wb23.close()
print("Tabela 2.3 header r2:", [(j, cyr2lat(c).replace("\n"," ").strip()) for j, c in enumerate(h23[2]) if c is not None])

# Parse each table
t21 = parse_excel_rows(AGRI_DIR / "pp2023_01_tabela-21_cir.xlsx", 4, {
    "farms_kpz": 1, "uaa_kpz_ha": 2, "kitchen_garden_ha": 4, "arable_ha": 6,
    "meadows_pastures_ha": 8, "orchards_ha": 10, "vineyards_ha": 12
})
t22 = parse_excel_rows(AGRI_DIR / "pp2023_02_tabela-22_cir.xlsx", 3, {
    "arable_farms": 1, "arable_total_ha": 2, "cereals_ha": 3, "industrial_crops_ha": 7, "vegetables_ha": 8, "fodder_ha": 10
})
# In Tabela 2.3: col 1=PG zita, 2=zita ukupno, 3=psenica i krupnik, 4=durum, 5=raz, 6=jecam, 7=ovas, 8=kukuruz za zrno (verify from header!)
kukuruz_idx = 8
for j, c in enumerate(h23[2]):
    if c and "кукуруз" in str(c).lower():
        kukuruz_idx = j
        break
print(f"Tabela 2.3 kukuruz_idx={kukuruz_idx}")
t23 = parse_excel_rows(AGRI_DIR / "pp2023_03_tabela-23_cir.xlsx", 3, {
    "cereals_farms": 1, "cereals_t23_ha": 2, "wheat_spelt_ha": 3, "barley_ha": 6, "maize_grain_ha": kukuruz_idx
})
t41 = parse_excel_rows(AGRI_DIR / "pp2023_09_tabela-41_brojstoke_cir.xlsx", 3, {
    "cattle": 1, "pigs": 3, "sheep": 5, "goats": 7, "poultry": 9
})
t54 = parse_excel_rows(AGRI_DIR / "pp2023_15_tabela-54_cir.xlsx", 4, {
    "awu_labor_units": 1, "farm_managers": 2
})
t61 = parse_excel_rows(AGRI_DIR / "pp2023_16_tabela-61_cir.xlsx", 3, {
    "tractors_total": 1, "tractors_over_20y": 7
})

# Merge by (level, oblast, raw_name)
merged = {}
def absorb(rows):
    for r in rows:
        key = (r["level"], norm_key(r["oblast"]), norm_key(r["raw_name"]))
        if key not in merged:
            # Handle Belgrade vs Niš Palilula disambiguation!
            nk = norm_key(r["raw_name"])
            code = None
            if r["level"] == "municipality":
                if nk == "PALILULA":
                    code = "70203" if "BEOGRAD" in norm_key(r["oblast"]) else "71315"
                else:
                    code = rzs_name_to_code.get(nk)
            merged[key] = {
                "muni_code": code,
                "name": r["raw_name"],
                "level": r["level"],
                "region": r["region"],
                "oblast": r["oblast"],
            }
        for k, v in r.items():
            if k not in ("raw_name", "level", "region", "oblast") and v is not None:
                merged[key][k] = v

for dataset in (t21, t22, t23, t41, t54, t61):
    absorb(dataset)

all_recs = list(merged.values())
munis = [x for x in all_recs if x["level"] == "municipality"]
oblasts = [x for x in all_recs if x["level"] == "oblast"]
matched_codes = sum(1 for x in munis if x.get("muni_code"))
print(f"Merged: {len(all_recs)} total rows | {len(munis)} municipalities ({matched_codes} matched to RZS matbro) | {len(oblasts)} oblasts")

# Print key focus hubs & rings
focus_names = {"BEOGRADSKA OBLAST", "BEOGRAD", "ZEMUN", "PALILULA", "SURCIN", "OBRENOVAC", "GROCKA", "MLADENOVAC", "LAZAREVAC",
               "PANCEVO", "STARA PAZOVA", "INDJIJA", "PECINCI", "RUMA", "SMEDEREVO", "VALJEVO",
               "NOVI PAZAR", "TUTIN", "SJENICA", "RASKA", "KRALJEVO"}
print("\n--- KEY MUNICIPALITIES (POPIS POLJOPRIVREDE 2023) ---")
for x in munis:
    if norm_key(x["name"]) in focus_names:
        print(f"  {str(x.get('muni_code') or '-----'):5s} {x['name']:18s} | PG={int(x.get('farms_kpz') or 0):>5} | KPZ={x.get('uaa_kpz_ha') or 0:>8.1f} ha | žita={x.get('cereals_ha') or 0:>8.1f} | pšenica={x.get('wheat_spelt_ha') or 0:>8.1f} | kukuruz={x.get('maize_grain_ha') or 0:>8.1f} | goveda={int(x.get('cattle') or 0):>6} | ovce={int(x.get('sheep') or 0):>6}")

OUT_P.write_text(json.dumps({"source": "RZS Popis poljoprivrede 2023 (Tabele 2.1, 2.2, 2.3, 4.1, 5.4, 6.1)", "count": len(all_recs), "records": all_recs}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nSaved {OUT_P.name} ({OUT_P.stat().st_size:,} B)")
