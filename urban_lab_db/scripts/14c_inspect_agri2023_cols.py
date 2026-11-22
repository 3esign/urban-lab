from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import json, re
from pathlib import Path
import openpyxl

BASE = Path(str(DB_DIR))
AGRI_DIR = BASE / "raw" / "wave3" / "rzs_agri2023"
OUT = BASE / "raw" / "wave3" / "rzs_agri2023_parsed_all_munis.json"

CYR_TO_LAT = {
    "А":"A","Б":"B","В":"V","Г":"G","Д":"D","Ђ":"Đ","Е":"E","Ж":"Ž","З":"Z","И":"I","Ј":"J","К":"K","Л":"L","Љ":"Lj",
    "М":"M","Н":"N","Њ":"Nj","О":"O","П":"P","Р":"R","С":"S","Т":"T","Ћ":"Ć","У":"U","Ф":"F","Х":"H","Ц":"C","Ч":"Č","Џ":"Dž","Ш":"Š",
    "а":"a","б":"b","в":"v","г":"g","д":"d","ђ":"đ","е":"e","ж":"ž","з":"z","и":"i","ј":"j","к":"k","л":"l","љ":"lj",
    "м":"m","н":"n","њ":"nj","о":"o","п":"p","р":"r","с":"s","т":"t","ћ":"ć","у":"u","ф":"f","х":"h","ц":"c","ч":"č","џ":"dž","ш":"š",
}
def cyr2lat(s):
    if s is None: return ""
    return "".join(CYR_TO_LAT.get(ch, ch) for ch in str(s))

def norm_name(s):
    t = cyr2lat(s).upper().strip()
    t = re.sub(r"\s+", " ", t)
    for a, b in [("Č","C"),("Ć","C"),("Š","S"),("Ž","Z"),("Đ","DJ"),("DŽ","DZ")]:
        t = t.replace(a, b)
    t = re.sub(r"\bGRAD\b", "", t).strip(" -–")
    return t

def to_num(v):
    if v is None: return None
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip().replace(" ", "").replace("\xa0", "").replace(",", ".")
    if s in ("", "-", "–", "...", "z", "*", "0.0"):
        return 0.0 if s == "0.0" else None
    try: return float(s)
    except: return None

def dump_table_headers(p):
    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = []
    for i, r in enumerate(ws.iter_rows(values_only=True)):
        rows.append(list(r))
        if i >= 18: break
    wb.close()
    print(f"\n--- {p.name} ---")
    for i, r in enumerate(rows[:14]):
        vals = [(j, cyr2lat(c).replace("\n", " ").strip()[:28]) for j, c in enumerate(r) if c is not None]
        if vals:
            print(f"  r{i:02d}: {vals[:12]}")

for fn in [
    "pp2023_01_tabela-21_cir.xlsx",
    "pp2023_02_tabela-22_cir.xlsx",
    "pp2023_03_tabela-23_cir.xlsx",
    "pp2023_07_tabela-27_cir.xlsx",
    "pp2023_09_tabela-41_brojstoke_cir.xlsx",
    "pp2023_12_tabela-51_cir.xlsx",
    "pp2023_15_tabela-54_cir.xlsx",
    "pp2023_16_tabela-61_cir.xlsx",
]:
    p = AGRI_DIR / fn
    if p.exists():
        dump_table_headers(p)
