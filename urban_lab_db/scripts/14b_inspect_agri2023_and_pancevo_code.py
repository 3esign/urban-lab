import json, sys, urllib.parse
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common_net import RAW_DIR, fetch_url, append_manifest, sha256_file

OUT = RAW_DIR / "wave3"
AGRI_OUT = OUT / "rzs_agri2023"

print("=== 1. EXACT RZS/APR MUNICIPALITY CODES (Pančevo, Stara Pazova, BG & NP ring) ===")
# Check from rzs_srbija_sve_opstine.geojson
ops_p = OUT / "rzs_srbija_sve_opstine.geojson"
if ops_p.exists():
    gj = json.loads(ops_p.read_text(encoding="utf-8"))
    print("  Opstine_dashboard sample props:", gj["features"][0]["properties"])
    targets = ["pan", "pazov", "inđ", "indj", "peć", "pec", "ruma", "smeder", "valjev", "tutin", "sjenic", "rašk", "rask", "novi pazar", "šabac", "sabac", "kraljev"]
    for f in gj["features"]:
        pr = f["properties"]
        s = " ".join(str(v) for v in pr.values()).lower()
        if any(t in s for t in targets):
            print("  RZS:", pr.get("matbro"), pr.get("naziv_lat") or pr.get("opstina_imel") or pr.get("naziv") or pr)

# Also check actual SifraOpstine + NazivOpstine inside apr_serbia_supply_chain_all.jsonl
sc_p = OUT / "apr_serbia_supply_chain_all.jsonl"
if sc_p.exists():
    muni_pairs = Counter()
    with open(sc_p, "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            muni_pairs[(str(r.get("SifraOpstine","")), str(r.get("NazivOpstine","")))] += 1
    print("\n  APR SifraOpstine + NazivOpstine matches:")
    for (mc, mn), cnt in sorted(muni_pairs.items()):
        low = mn.lower()
        if any(k in low for k in ["панч", "panč", "panc", "пазов", "pazov", "инђ", "inđ", "пећ", "рум", "смедер", "ваљев", "тутин", "сјениц", "рашк", "пазар"]):
            print(f"    {mc:6s} | {mn:30s} | supply_chain_firms={cnt}")

print("\n=== 2. INSPECT RZS POPIS POLJOPRIVREDE 2023 EXCEL TABLES ===")
try:
    import openpyxl
    for p in sorted(AGRI_OUT.glob("pp2023_*.xlsx")):
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
        sh = wb.sheetnames
        ws = wb[sh[0]]
        rows = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i < 6:
                non_empty = [str(c)[:35] for c in row if c is not None][:6]
                if non_empty:
                    rows.append(f"r{i}:{non_empty}")
            else:
                break
        wb.close()
        print(f"  {p.name:36s} | sheets={sh[:3]} | {' ; '.join(rows[:3])}")
except Exception as e:
    print("  openpyxl err:", e)

print("\n=== 3. FETCH RZS ARCGIS POPIS POLJOPRIVREDE 2023 OPSTINE ===")
for svc in ["Popis_poljoprivrede_2023_Opstine", "Indikatori_popis_poljoprivrede_2023_bez_naselja_1"]:
    u = f"https://gis.stat.gov.rs/server/rest/services/Hosted/{svc}/FeatureServer?f=json"
    r = fetch_url(u, save_manifest=False, timeout=25)
    print(f"  Service {svc}: ok={r['ok']}")
    if r["ok"]:
        meta = json.loads(r["_bytes"].decode("utf-8"))
        for lyr in meta.get("layers", [])[:15]:
            print(f"    layer {lyr['id']}: {lyr['name']}")
        # If layer 0 exists in Popis_poljoprivrede_2023_Opstine, download all 197 opstine attributes (returnGeometry=false to be tiny & fast!)
        if svc == "Popis_poljoprivrede_2023_Opstine" and meta.get("layers"):
            lid = meta["layers"][0]["id"]
            q_url = f"https://gis.stat.gov.rs/server/rest/services/Hosted/{svc}/FeatureServer/{lid}/query?where=1%3D1&outFields=*&returnGeometry=false&f=json&resultRecordCount=1000"
            rq = fetch_url(q_url, dest=AGRI_OUT / "rzs_arcgis_pp2023_opstine.json", city="common", layer="rzs_agri2023_arcgis_ops", source_name="RZS ArcGIS Popis poljoprivrede 2023 Opstine (all attributes)", timeout=45)
            if rq["ok"]:
                d = json.loads((AGRI_OUT / "rzs_arcgis_pp2023_opstine.json").read_text(encoding="utf-8"))
                feats = d.get("features", [])
                print(f"    -> Downloaded {len(feats)} opstine records!")
                if feats:
                    print("    -> Sample attributes:", list(feats[0]["attributes"].items())[:20])
            else:
                print("    -> Query failed:", rq.get("error"))
