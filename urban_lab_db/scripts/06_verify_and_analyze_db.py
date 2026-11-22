from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import json
import sqlite3
from pathlib import Path

BASE = Path(str(DB_DIR))
DB = BASE / "curated" / "urban_lab_5cities.sqlite"
BND = BASE / "curated" / "boundaries"

conn = sqlite3.connect(str(DB))
cur = conn.cursor()

print("================ 1. GEOJSON BOUNDARY BBOX CHECK ================")
for gj in sorted(BND.glob("*.geojson")):
    fc = json.loads(gj.read_text(encoding="utf-8"))
    feats = fc.get("features", [])
    lons, lats = [], []
    def walk(c):
        if isinstance(c, list) and c:
            if isinstance(c[0], (int, float)):
                lons.append(c[0]); lats.append(c[1])
            else:
                for x in c: walk(x)
    for f in feats:
        if f.get("geometry"):
            walk(f["geometry"].get("coordinates", []))
    if lons:
        print(f"  {gj.name:42s} | feats={len(feats):4d} | lon=[{min(lons):.3f}, {max(lons):.3f}] lat=[{min(lats):.3f}, {max(lats):.3f}] | {gj.stat().st_size:,} B")
    else:
        print(f"  {gj.name:42s} | feats={len(feats):4d} | EMPTY GEOM")

print("\n================ 2. 5-CITY MASTER COMPARISON ================")
for r in cur.execute("SELECT * FROM v_city_comparison"):
    print(" ", r)

print("\n================ 3. BEOGRAD TOP 10 OPSTINA BY APR REVENUE ================")
for r in cur.execute("SELECT unit_name, population, avg_net_wage_eur, companies_count, apr_employees, companies_rev_eur_m, apr_rev_eur_per_capita, dist_cbd_km FROM v_beograd_opstine_economy LIMIT 10"):
    print(" ", r)

print("\n================ 4. ZAGREB TOP 10 REVENUE & EXPENDITURE ACCOUNTS 2026 ================")
print("  --- TOP REVENUES (EUR) ---")
for r in cur.execute("SELECT account_code, account_name, ROUND(SUM(plan_eur)/1e6, 2) AS m_eur FROM zagreb_budget_lines WHERE side='revenue' GROUP BY account_code, account_name ORDER BY SUM(plan_eur) DESC LIMIT 10"):
    print("   ", r)
print("  --- TOP RAZDJELI EXPENDITURES (EUR) ---")
for r in cur.execute("SELECT razdjel_code, razdjel_name, ROUND(SUM(plan_eur)/1e6, 2) AS m_eur FROM zagreb_budget_lines WHERE side='expenditure' GROUP BY razdjel_code, razdjel_name ORDER BY SUM(plan_eur) DESC LIMIT 10"):
    print("   ", r)

print("\n================ 5. SECTOR SPECIALIZATION (TOP LQ PER CITY) ================")
for cid in ["beograd", "novi_pazar", "sarajevo", "travnik"]:
    print(f"  --- {cid.upper()} ---")
    sql = """
    SELECT unit_name, nace_section, nace_name, companies_count, unit_share_pct, location_quotient
    FROM sector_structure
    WHERE city_id = ? AND companies_count >= 15
      AND (unit_name LIKE '%UKUPNO%' OR unit_name IN ('Novi Pazar', 'Travnik', 'Centar Sarajevo', 'Stari grad', 'Novi Beograd', 'Ilidža'))
    ORDER BY location_quotient DESC LIMIT 8
    """
    for r in cur.execute(sql, (cid,)):
        print("   ", r)

print("\n================ 6. BID-RENT PROFILES (EUR/m2) ================")
for cid in ["beograd", "novi_pazar", "sarajevo", "travnik", "zagreb"]:
    print(f"  --- {cid.upper()} ---")
    for r in cur.execute("SELECT zone_or_unit, property_type, price_local_m2, currency, price_eur_m2, sample_n FROM v_bid_rent_profiles WHERE city_id=? AND property_type IN ('stan','poslovne_zgrade','stan_novogradnja','apartman') ORDER BY property_type, price_eur_m2 DESC LIMIT 12", (cid,)):
        print("   ", r)

print("\n================ 7. OSM ECONOMIC POIs BY CITY & RING ================")
for r in cur.execute("SELECT city_id, COUNT(*) AS total_pois, SUM(CASE WHEN ring_km='0-1km' THEN 1 ELSE 0 END) AS r0_1, SUM(CASE WHEN ring_km='1-3km' THEN 1 ELSE 0 END) AS r1_3, SUM(CASE WHEN ring_km='3-6km' THEN 1 ELSE 0 END) AS r3_6, SUM(CASE WHEN ring_km='6km+' THEN 1 ELSE 0 END) AS r6p FROM osm_pois GROUP BY city_id ORDER BY total_pois DESC"):
    print(" ", r)

print("\n================ 8. STORAGE FOOTPRINT ================")
all_files = [p for p in BASE.rglob("*") if p.is_file()]
tot_b = sum(p.stat().st_size for p in all_files)
print(f"  Total files: {len(all_files)}, Total size: {tot_b / (1024*1024):.2f} MB ({tot_b:,} B)")
for sub in ["raw", "curated", "scripts"]:
    sf = [p for p in (BASE / sub).rglob("*") if p.is_file()]
    sb = sum(p.stat().st_size for p in sf)
    print(f"    {sub:10s}: {len(sf):3d} files, {sb / (1024*1024):.2f} MB")

conn.close()
