import json, re, sys
from pathlib import Path
import openpyxl, pypdf

sys.path.insert(0, str(Path(__file__).parent))
from common_net import RAW_DIR, fetch_url

WL = RAW_DIR / "wave2_l"
WXL = RAW_DIR / "wave2_xl"

# 1. Try direct FZS ZDK PDF URLs (same pattern as KS 2026/03 and SBK 2025/07)
print("=== 1. FZS ZDK PDF ===")
zdk_p = WL / "fzs_zdk_2025.pdf"
if not (zdk_p.exists() and zdk_p.stat().st_size > 100000):
    for u in [
        "https://fzs.ba/wp-content/uploads/2026/03/zenicko-dobojski-kanton.pdf",
        "https://fzs.ba/wp-content/uploads/2025/07/zenicko-dobojski-kanton.pdf",
        "https://fzs.ba/wp-content/uploads/2025/08/zenicko-dobojski-kanton.pdf",
        "https://fzs.ba/wp-content/uploads/2025/09/zenicko-dobojski-kanton.pdf",
        "https://fzs.ba/wp-content/uploads/2026/02/zenicko-dobojski-kanton.pdf",
    ]:
        r = fetch_url(u, dest=zdk_p, city="sarajevo", layer="wave2_l_hinterland", source_name=f"FZS ZDK u brojkama PDF ({u})", timeout=35)
        if r.get("ok") and r.get("bytes", 0) > 100000:
            print(f"  [OK] {u} -> {r['bytes']:,} B")
            break
else:
    print(f"  [CACHED] {zdk_p.stat().st_size:,} B")

if zdk_p.exists() and zdk_p.stat().st_size > 100000:
    pdf = pypdf.PdfReader(str(zdk_p))
    print(f"  ZDK PDF pages={len(pdf.pages)}")
    for idx in [11, 14, 15, 18, 20]:
        if idx < len(pdf.pages):
            txt = (pdf.pages[idx].extract_text() or "").strip()
            for line in txt.splitlines():
                if any(k in line.lower() for k in ["visoko", "zenica", "kakanj", "breza", "ukupno", "pšenica", "šumskih"]):
                    print(f"    p.{idx+1}: {line[:120]}")

# 2. Cyrillic -> Latin helper for RZS Excel tables
CYR = {
    'А':'A','Б':'B','В':'V','Г':'G','Д':'D','Ђ':'Đ','Е':'E','Ж':'Ž','З':'Z','И':'I','Ј':'J','К':'K','Л':'L','Љ':'Lj',
    'М':'M','Н':'N','Њ':'Nj','О':'O','П':'P','Р':'R','С':'S','Т':'T','Ћ':'Ć','У':'U','Ф':'F','Х':'H','Ц':'C','Ч':'Č','Џ':'Dž','Ш':'Š',
    'а':'a','б':'b','в':'v','г':'g','д':'d','ђ':'đ','е':'e','ж':'ž','з':'z','и':'i','ј':'j','к':'k','л':'l','љ':'lj',
    'м':'m','н':'n','њ':'nj','о':'o','п':'p','р':'r','с':'s','т':'t','ћ':'ć','у':'u','ф':'f','х':'h','ц':'c','ч':'č','џ':'dž','ш':'š',
}
def cyr2lat(s):
    return "".join(CYR.get(ch, ch) for ch in str(s or ""))

# 3. Parse RZS Popis 2022 Daily Commuting for BG (17 + ring) and NP (+ ring)
print("\n=== 2. RZS POPIS 2022 DAILY COMMUTING (LATINIZED) ===")
TARGETS_SRB = [
    "Beogradski region", "Grad Beograd", "Barajevo", "Voždovac", "Vračar", "Grocka", "Zvezdara", "Zemun",
    "Lazarevac", "Mladenovac", "Novi Beograd", "Obrenovac", "Palilula", "Rakovica", "Savski venac", "Sopot",
    "Stari grad", "Surčin", "Čukarica",
    "Pančevo", "Stara Pazova", "Inđija", "Pećinci", "Ruma", "Smederevo", "Valjevo",
    "Novi Pazar", "Tutin", "Sjenica", "Raška"
]
target_set = {t.lower() for t in TARGETS_SRB}
dm_p = WL / "rzs_popis2022_dnevne_migracije_aktivnog_stanovnistva_koje_obavlja_zanimanje_po_polu_i_tipu_naselja.xlsx"
wb = openpyxl.load_workbook(dm_p, read_only=True, data_only=True)
ws = wb[wb.sheetnames[0]]
comm_rows = []
for row in ws.iter_rows(values_only=True):
    name = cyr2lat(row[0]).strip()
    sex = cyr2lat(row[1]).strip().lower()
    if sex == "s" and name.lower() in target_set:
        # cols: total, same_muni, other_muni_same_area, other_area, foreign
        rec = {
            "name": name,
            "total_commuters": row[2],
            "same_muni": row[3],
            "other_muni_same_area": row[4],
            "other_area": row[5],
            "foreign": row[6],
        }
        comm_rows.append(rec)
        print(f"  {name:20s} | tot={str(rec['total_commuters']):>7} | same_muni={str(rec['same_muni']):>6} | same_area={str(rec['other_muni_same_area']):>6} | other_area={str(rec['other_area']):>6} | foreign={str(rec['foreign']):>4}")
wb.close()
(WL / "parsed_rzs_commuting_2022.json").write_text(json.dumps(comm_rows, ensure_ascii=False, indent=2), encoding="utf-8")

# 4. Parse Eurostat RS NUTS3 GDP (latest available year) + Gas prices + Tourism nights + Min wages
def parse_eurostat(path):
    d = json.loads(path.read_text(encoding="utf-8"))
    ids, sizes, dims = d["id"], d["size"], d["dimension"]
    idx_maps = []
    for dim_id in ids:
        cat = dims[dim_id]["category"]
        idx_maps.append((dim_id, {v: k for k, v in cat["index"].items()}, cat.get("label", {})))
    rows = []
    for k_str, val in d.get("value", {}).items():
        k = int(k_str)
        coords = []
        for sz in reversed(sizes):
            coords.append(k % sz); k //= sz
        coords.reverse()
        rec = {"value": val}
        for (dim_id, inv, labels), c in zip(idx_maps, coords):
            code = inv[c]
            rec[dim_id] = code
            rec[dim_id + "_label"] = labels.get(code, code)
        rows.append(rec)
    return rows

print("\n=== 3. EUROSTAT RS & HR NUTS3 GDP (LATEST PER GEO) ===")
gdp_rows = parse_eurostat(WXL / "eurostat_nama_10r_3gdp_full.json")
by_geo_unit = {}
for r in gdp_rows:
    if r["unit"] in ("MIO_EUR", "EUR_HAB", "PPS_EU27_2020_HAB"):
        key = (r["geo"], r["unit"])
        if key not in by_geo_unit or r["time"] > by_geo_unit[key]["time"]:
            by_geo_unit[key] = r
for geo in sorted({k[0] for k in by_geo_unit}):
    m = by_geo_unit.get((geo, "MIO_EUR"), {})
    e = by_geo_unit.get((geo, "EUR_HAB"), {})
    p = by_geo_unit.get((geo, "PPS_EU27_2020_HAB"), {})
    print(f"  {geo:6s} {m.get('geo_label','')[:30]:30s} ({m.get('time')}) | {m.get('value')} M EUR | {e.get('value')} EUR/st | {p.get('value')} PPS/st")

print("\n=== 4. EUROSTAT TOURISM NIGHTS (NUTS2) & MIN WAGE ===")
t_rows = parse_eurostat(WXL / "eurostat_tour_occ_nin2.json")
latest_t = {}
for r in t_rows:
    if r.get("nace_r2") == "I551-I553" and r.get("c_resid") == "TOTAL":
        key = r["geo"]
        if key not in latest_t or r["time"] > latest_t[key]["time"]:
            latest_t[key] = r
for g, r in sorted(latest_t.items()):
    print(f"  TOUR {g:6s} {r['geo_label'][:32]:32s} ({r['time']}): {r['value']:,.0f} nights")

mw_rows = parse_eurostat(WXL / "eurostat_earn_mw_cur.json")
for g in ("HR", "RS"):
    sub = sorted([r for r in mw_rows if r["geo"] == g], key=lambda x: x["time"])[-3:]
    print(f"  MINWAGE {g}: " + ", ".join(f"{r['time']}={r['value']} EUR" for r in sub))

# 5. Parse Zagreb Business Leases (all columns + bakeries/food!)
print("\n=== 5. ZAGREB COMMERCIAL LEASES (FULL COLUMNS) ===")
zk_p = WL / "ckan_dl_registar-ugovora-o-zakupu-korist_64a475.xlsx"
wb = openpyxl.load_workbook(zk_p, read_only=True, data_only=True)
ws = wb[wb.sheetnames[0]]
zrows = list(ws.iter_rows(values_only=True))
print("  Header:", list(zrows[1]))
for r in zrows[2:7]:
    print("  Row:", [str(x)[:35] if x is not None else "" for x in r])
wb.close()

# 6. Parse HR OPG Upisnik 2024 for Grad Zagreb & Zagrebacka zupanija
print("\n=== 6. HR UPISNIK POLJOPRIVREDNIKA 2024 (ZAGREB + ZAGREBACKA ZUPANIJA) ===")
opg_p = WL / "ckan_dl_upisnik_poljoprivrednika-broj-pg_a3ccdb.xlsx"
wb = openpyxl.load_workbook(opg_p, read_only=True, data_only=True)
ws = wb[wb.sheetnames[0]]
in_zg = False
for i, r in enumerate(ws.iter_rows(values_only=True)):
    if i < 3: continue
    lbl = str(r[0] or "").strip()
    if any(k in lbl.lower() for k in ["grad zagreb", "zagrebačka", "velika gorica", "samobor", "zaprešić", "sveta nedelja", "dugo selo", "jastrebarsko", "ivanić-grad", "vrbovec", "sveti ivan zelina"]):
        print(f"  {lbl:32s} | {list(r[1:14])}")
wb.close()

# 7. Parse World Bank extended XL latest values
print("\n=== 7. WORLD BANK EXTENDED XL (LATEST 2022-2025) ===")
for fn in sorted(WXL.glob("wb_*.json")):
    try:
        arr = json.loads(fn.read_text(encoding="utf-8"))
        if len(arr) >= 2 and isinstance(arr[1], list):
            latest = {}
            for rec in arr[1]:
                if rec.get("value") is not None:
                    iso = rec["countryiso3code"]
                    yr = rec["date"]
                    if iso not in latest or yr > latest[iso][0]:
                        latest[iso] = (yr, round(float(rec["value"]), 2))
            print(f"  {fn.stem:28s} | " + " | ".join(f"{k}:{v[1]}({v[0]})" for k, v in sorted(latest.items())))
    except Exception as e:
        print(f"  {fn.stem}: ERR {e}")
