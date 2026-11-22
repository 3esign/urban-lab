from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import json, csv
from pathlib import Path
import openpyxl

BASE = Path(str(DB_DIR / "raw"))
WL = BASE / "wave2_l"
WXL = BASE / "wave2_xl"

# 1. Inspect Eurostat JSON-stat helper
def parse_eurostat(path):
    d = json.loads(path.read_text(encoding="utf-8"))
    ids = d["id"]
    sizes = d["size"]
    dims = d["dimension"]
    # build label maps
    idx_maps = []
    for dim_id in ids:
        cat = dims[dim_id]["category"]
        inv = {v: k for k, v in cat["index"].items()}
        labels = cat.get("label", {})
        idx_maps.append((dim_id, inv, labels))
    vals = d.get("value", {})
    rows = []
    for k_str, val in vals.items():
        k = int(k_str)
        coords = []
        rem = k
        for sz in reversed(sizes):
            coords.append(rem % sz)
            rem //= sz
        coords.reverse()
        rec = {"value": val}
        for (dim_id, inv, labels), c in zip(idx_maps, coords):
            code = inv[c]
            rec[dim_id] = code
            rec[dim_id + "_label"] = labels.get(code, code)
        rows.append(rec)
    return rows

print("=== 1. EUROSTAT NUTS3 GDP (HR & RS) ===")
if (WXL / "eurostat_nama_10r_3gdp_full.json").exists():
    rows = parse_eurostat(WXL / "eurostat_nama_10r_3gdp_full.json")
    for u in ["MIO_EUR", "EUR_HAB", "PPS_EU27_2020_HAB"]:
        sub = [r for r in rows if r.get("unit") == u and r.get("time") in ("2022", "2023", "2024")]
        if sub:
            latest_t = max(r["time"] for r in sub)
            print(f"  Unit={u} (latest={latest_t}):")
            for r in sorted([x for x in sub if x["time"] == latest_t], key=lambda x: x["geo"]):
                print(f"    {r['geo']:6s} {r['geo_label'][:32]:32s} | {r['value']}")

print("\n=== 2. EUROSTAT BUSINESS ELECTRICITY PRICES (nrg_pc_205, EUR/kWh) ===")
if (WXL / "eurostat_nrg_pc_205.json").exists():
    rows = parse_eurostat(WXL / "eurostat_nrg_pc_205.json")
    # Filter band IB (20-499 MWh) and IA (<20 MWh), X_VAT & I_TAX, latest periods
    sub = [r for r in rows if r.get("nrg_cons") in ("MWH_LT20", "MWH20-499") and r.get("tax") in ("X_VAT", "I_TAX")]
    times = sorted(set(r["time"] for r in sub))[-3:]
    for r in sorted([x for x in sub if x["time"] in times], key=lambda x: (x["geo"], x["nrg_cons"], x["tax"], x["time"])):
        print(f"  {r['geo']} | {r['time']} | {r['nrg_cons']:10s} | {r['tax']:5s} | {r['value']} EUR/kWh")

print("\n=== 3. EUROSTAT FUA POPULATION (urb_lpop1) ===")
if (WXL / "eurostat_urb_lpop1.json").exists():
    rows = parse_eurostat(WXL / "eurostat_urb_lpop1.json")
    sub = [r for r in rows if r.get("indic_ur") == "DE1001V"]
    for r in sorted(sub, key=lambda x: (x["cities"], x["time"]))[-12:]:
        print(f"  {r['cities']} {r['cities_label'][:25]:25s} | {r['time']} | {r['value']:,.0f}")

print("\n=== 4. RZS POPIS 2022 DNEVNE MIGRACIJE (SAMPLE) ===")
dm_p = WL / "rzs_popis2022_dnevne_migracije_aktivnog_stanovnistva_koje_obavlja_zanimanje_po_polu_i_tipu_naselja.xlsx"
if dm_p.exists():
    wb = openpyxl.load_workbook(dm_p, read_only=True, data_only=True)
    print("  Sheets:", wb.sheetnames)
    ws = wb[wb.sheetnames[0]]
    targets = ["beograd", "novi pazar", "pančevo", "stara pazova", "inđija", "pećinci", "tutin", "sjenica", "raška", "obrenovac", "mladenovac", "lazarevac", "surčin", "zemun", "novi beograd"]
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i < 12:
            print(f"  r{i}: {[c for c in row[:10] if c is not None][:8]}")
        else:
            s0 = str(row[0] or row[1] or "").strip().lower()
            if any(t == s0 or s0.startswith(t) for t in targets):
                print(f"  MATCH r{i}: {list(row[:10])}")
    wb.close()

print("\n=== 5. ZAGREB REGISTAR ZAKUPA POSLOVNIH PROSTORA & TRZNICE ===")
zk_p = WL / "ckan_dl_registar-ugovora-o-zakupu-korist_64a475.xlsx"
if zk_p.exists():
    wb = openpyxl.load_workbook(zk_p, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows_z = list(ws.iter_rows(values_only=True))
    print(f"  Zakup rows={len(rows_z)}, sheets={wb.sheetnames}")
    for r in rows_z[:6]:
        print("   ", [str(x)[:40] if x is not None else "" for x in r[:10]])
    wb.close()

tr_p = WL / "ckan_dl_geoportal-gradske-trznice_a24500.csv"
if tr_p.exists():
    txt = tr_p.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    print(f"  Trznice CSV lines={len(txt)}")
    for l in txt[:8]:
        print("   ", l[:140])

print("\n=== 6. HR UPISNIK POLJOPRIVREDNIKA 2024 (HEADER + ZAGREB COUNT) ===")
opg_p = WL / "ckan_dl_upisnik_poljoprivrednika-broj-pg_a3ccdb.xlsx"
if opg_p.exists():
    wb = openpyxl.load_workbook(opg_p, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    print("  Sheets:", wb.sheetnames)
    zg_cnt, zz_cnt, tot = 0, 0, 0
    for i, r in enumerate(ws.iter_rows(values_only=True)):
        if i < 5:
            print(f"  r{i}: {list(r[:10])}")
        else:
            tot += 1
            joined = " ".join(str(x or "") for x in r[:6]).lower()
            if "grad zagreb" in joined: zg_cnt += 1
            elif "zagrebačka" in joined or "zagrebacka" in joined: zz_cnt += 1
    print(f"  Total PG rows={tot:,} | Grad Zagreb={zg_cnt:,} | Zagrebacka zupanija={zz_cnt:,}")
    wb.close()
