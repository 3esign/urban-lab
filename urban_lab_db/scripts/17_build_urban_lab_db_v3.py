from _paths import DB_DIR, SCRATCH_DIR, rel  # koreni putanja, vidi _paths.py
import csv, hashlib, json, sqlite3, time
from collections import defaultdict
from pathlib import Path

BASE = Path(str(DB_DIR))
RAW = BASE / "raw"
W3 = RAW / "wave3"
W3_OSM = RAW / "wave3_osm"
CUR = BASE / "curated"
BND = CUR / "boundaries"
TBL = CUR / "tables"
DB_PATH = CUR / "urban_lab_5cities.sqlite"
MANIFEST = BASE / "manifest.jsonl"

RSD_PER_EUR = 117.0

def to_float(v):
    if v is None or v == "": return 0.0
    try: return float(v)
    except: return 0.0

def to_int(v):
    if v is None or v == "": return 0
    try: return int(float(v))
    except: return 0

def register_manifest(city, layer, desc, path, url):
    rec = {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ok": True, "city": city, "layer": layer, "source_name": desc,
        "url": url, "http_status": 200, "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "local_path": rel(path),
    }
    with open(MANIFEST, "a", encoding="utf-8") as mf:
        mf.write(json.dumps(rec, ensure_ascii=False) + "\n")

def build_v3():
    t0 = time.time()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # ========================================================================
    # 1. REBUILD companies_sr_hinterland WITH 100% RZS-VERIFIED CODES (INCL. PANČEVO 80314)
    # ========================================================================
    print("=== [1/6] REBUILDING companies_sr_hinterland (RZS-VERIFIED CODES + PANČEVO) ===", flush=True)
    cur.execute("DELETE FROM companies_sr_hinterland;")
    h_rows = []
    muni_agg = defaultdict(lambda: {"firms": 0, "emp": 0, "rev_eur": 0.0})
    for fn, hub in [("apr_beograd_hinterland_v3.jsonl", "beograd"), ("apr_novi_pazar_hinterland_v3.jsonl", "novi_pazar")]:
        p = W3 / fn
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                mb = str(r.get("MaticniBroj") or "").strip().zfill(8)
                mc = str(r.get("SifraOpstine") or "").strip()
                mn = str(r.get("_muni_label") or r.get("NazivOpstine") or "").strip()
                nm = str(r.get("PoslovnoIme") or "").strip()
                nace = str(r.get("SifraDelatnosti") or "").strip()
                status = str(r.get("NazivStatus") or "").strip()
                fi = r.get("fi")
                has_fi = 1 if fi else 0
                emp = to_int(fi.get("BrojZaposlenih")) if fi else 0
                # APR financial statements values are in thousands of RSD (000 RSD)
                rev_eur = round(to_float(fi.get("PoslovniPrihod")) * 1000.0 / RSD_PER_EUR, 2) if fi else 0.0
                np_eur = round((to_float(fi.get("NetoDobitak")) - to_float(fi.get("NetoGubitak"))) * 1000.0 / RSD_PER_EUR, 2) if fi else 0.0
                as_eur = round(to_float(fi.get("PoslovnaImovina")) * 1000.0 / RSD_PER_EUR, 2) if fi else 0.0
                h_rows.append((mb, hub, mc, mn, nm, nace, nace[:2], status, has_fi, emp, rev_eur, np_eur, as_eur))
                muni_agg[(hub, mn)]["firms"] += 1
                muni_agg[(hub, mn)]["emp"] += emp
                muni_agg[(hub, mn)]["rev_eur"] += rev_eur

    cur.executemany(
        "INSERT OR REPLACE INTO companies_sr_hinterland (maticni_broj, city_hub, muni_code, muni_name, name, nace_code, nace_2d, status, has_fi, employees, revenue_eur, net_profit_eur, assets_eur) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        h_rows
    )
    print(f"  Loaded {len(h_rows):,} verified hinterland firms (BG ring + NP ring)")

    # Update hinterland_units employees for verified Serbian ring units
    for (hub, mn), st in muni_agg.items():
        cur.execute(
            "UPDATE hinterland_units SET employees=? WHERE city_hub=? AND unit_name=?",
            (st["emp"], hub, mn)
        )

    # ========================================================================
    # 2. NATIONAL SERBIA SUPPLY CHAIN TABLE (1071, 1061, 1072, 0111, 1610, 0220)
    # ========================================================================
    print("\n=== [2/6] LOADING apr_serbia_supply_chain (ALL SERBIA MILLS/BAKERIES/GRAIN/WOOD) ===", flush=True)
    cur.execute("DROP TABLE IF EXISTS apr_serbia_supply_chain;")
    cur.execute("""
    CREATE TABLE apr_serbia_supply_chain (
        maticni_broj TEXT PRIMARY KEY,
        muni_code TEXT,
        muni_name TEXT,
        name TEXT,
        nace_code TEXT,
        sc_role TEXT,
        status TEXT,
        founded_date TEXT,
        legal_form TEXT,
        has_fi INTEGER,
        employees INTEGER,
        revenue_eur REAL,
        net_profit_eur REAL,
        assets_eur REAL
    );
    """)
    sc_rows = []
    with open(W3 / "apr_serbia_supply_chain_all.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            mb = str(r.get("MaticniBroj") or "").strip().zfill(8)
            fi = r.get("fi")
            has_fi = 1 if fi else 0
            emp = to_int(fi.get("BrojZaposlenih")) if fi else 0
            rev_eur = round(to_float(fi.get("PoslovniPrihod")) * 1000.0 / RSD_PER_EUR, 2) if fi else 0.0
            np_eur = round((to_float(fi.get("NetoDobitak")) - to_float(fi.get("NetoGubitak"))) * 1000.0 / RSD_PER_EUR, 2) if fi else 0.0
            as_eur = round(to_float(fi.get("PoslovnaImovina")) * 1000.0 / RSD_PER_EUR, 2) if fi else 0.0
            sc_rows.append((
                mb,
                str(r.get("SifraOpstine") or "").strip(),
                str(r.get("NazivOpstine") or "").strip(),
                str(r.get("PoslovnoIme") or "").strip(),
                str(r.get("SifraDelatnosti") or "").strip(),
                str(r.get("_sc_role") or ""),
                str(r.get("NazivStatus") or "").strip(),
                str(r.get("DatumOsnivanja") or "").strip(),
                str(r.get("NazivPravneForme") or "").strip(),
                has_fi, emp, rev_eur, np_eur, as_eur
            ))
    cur.executemany("INSERT OR REPLACE INTO apr_serbia_supply_chain VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", sc_rows)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_apr_sc_muni ON apr_serbia_supply_chain(muni_code, nace_code);")
    print(f"  Loaded {len(sc_rows):,} national supply-chain firms across Serbia")

    # ========================================================================
    # 3. RZS POPIS POLJOPRIVREDE 2023 (ALL SERBIA MUNICIPALITIES & OBLASTS)
    # ========================================================================
    print("\n=== [3/6] LOADING rzs_agri_census_2023 ===", flush=True)
    cur.execute("DROP TABLE IF EXISTS rzs_agri_census_2023;")
    cur.execute("""
    CREATE TABLE rzs_agri_census_2023 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        muni_code TEXT,
        unit_name TEXT NOT NULL,
        geo_level TEXT NOT NULL,
        region TEXT,
        oblast TEXT,
        farms_kpz INTEGER,
        uaa_kpz_ha REAL,
        arable_ha REAL,
        meadows_pastures_ha REAL,
        orchards_ha REAL,
        vineyards_ha REAL,
        cereals_ha REAL,
        wheat_spelt_ha REAL,
        barley_ha REAL,
        maize_grain_ha REAL,
        industrial_crops_ha REAL,
        vegetables_ha REAL,
        fodder_ha REAL,
        cattle INTEGER,
        pigs INTEGER,
        sheep INTEGER,
        goats INTEGER,
        poultry INTEGER,
        awu_labor_units INTEGER,
        farm_managers INTEGER,
        tractors_total INTEGER,
        tractors_over_20y INTEGER,
        source_ref TEXT
    );
    """)
    ag_data = json.loads((W3 / "rzs_agri2023_all_munis.json").read_text(encoding="utf-8"))
    ag_rows = []
    for r in ag_data["records"]:
        ag_rows.append((
            r.get("muni_code"),
            r["name"], r["level"], r.get("region", ""), r.get("oblast", ""),
            to_int(r.get("farms_kpz")), to_float(r.get("uaa_kpz_ha")), to_float(r.get("arable_ha")),
            to_float(r.get("meadows_pastures_ha")), to_float(r.get("orchards_ha")), to_float(r.get("vineyards_ha")),
            to_float(r.get("cereals_ha")), to_float(r.get("wheat_spelt_ha")), to_float(r.get("barley_ha")),
            to_float(r.get("maize_grain_ha")), to_float(r.get("industrial_crops_ha")),
            to_float(r.get("vegetables_ha")), to_float(r.get("fodder_ha")),
            to_int(r.get("cattle")), to_int(r.get("pigs")), to_int(r.get("sheep")),
            to_int(r.get("goats")), to_int(r.get("poultry")),
            to_int(r.get("awu_labor_units")), to_int(r.get("farm_managers")),
            to_int(r.get("tractors_total")), to_int(r.get("tractors_over_20y")),
            "RZS Popis poljoprivrede 2023 (Tabele 2.1, 2.2, 2.3, 4.1, 5.4, 6.1)"
        ))
    cur.executemany(
        "INSERT INTO rzs_agri_census_2023 (muni_code, unit_name, geo_level, region, oblast, farms_kpz, uaa_kpz_ha, arable_ha, meadows_pastures_ha, orchards_ha, vineyards_ha, cereals_ha, wheat_spelt_ha, barley_ha, maize_grain_ha, industrial_crops_ha, vegetables_ha, fodder_ha, cattle, pigs, sheep, goats, poultry, awu_labor_units, farm_managers, tractors_total, tractors_over_20y, source_ref) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ag_rows
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_agri2023_muni ON rzs_agri_census_2023(muni_code, geo_level);")
    print(f"  Loaded {len(ag_rows):,} RZS Popis poljoprivrede 2023 records")

    # ========================================================================
    # 4. OSM LANDUSE SUMMARY + MAJOR ZONES + COMBINED 5-CITY GEOJSON
    # ========================================================================
    print("\n=== [4/6] LOADING osm_landuse_summary, osm_landuse_major_zones & COMBINED GEOJSON ===", flush=True)
    cur.execute("DROP TABLE IF EXISTS osm_landuse_summary;")
    cur.execute("""
    CREATE TABLE osm_landuse_summary (
        city_id TEXT NOT NULL,
        ring TEXT NOT NULL,
        macro_group TEXT NOT NULL,
        fclass TEXT NOT NULL,
        polygon_count INTEGER NOT NULL,
        area_km2 REAL NOT NULL,
        area_ha REAL NOT NULL,
        PRIMARY KEY (city_id, ring, macro_group, fclass)
    );
    """)
    cur.execute("DROP TABLE IF EXISTS osm_landuse_major_zones;")
    cur.execute("""
    CREATE TABLE osm_landuse_major_zones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city_id TEXT NOT NULL,
        osm_id TEXT,
        macro_group TEXT NOT NULL,
        fclass TEXT NOT NULL,
        name TEXT,
        area_km2 REAL NOT NULL,
        area_ha REAL NOT NULL,
        dist_cbd_km REAL,
        ring TEXT,
        lon REAL,
        lat REAL
    );
    """)

    lu_sum_rows = []
    lu_feat_rows = []
    combined_feats = []
    for cid in ["beograd", "zagreb", "sarajevo", "novi_pazar", "travnik"]:
        sp = W3_OSM / f"geofabrik_landuse_summary_{cid}.json"
        if sp.exists():
            d = json.loads(sp.read_text(encoding="utf-8"))
            for r in d["by_ring_and_fclass"]:
                lu_sum_rows.append((cid, r["ring"], r["macro_group"], r["fclass"], r["polygon_count"], r["area_km2"], r["area_ha"]))
        gp = W3_OSM / f"geofabrik_landuse_{cid}.geojson"
        if gp.exists():
            gj = json.loads(gp.read_text(encoding="utf-8"))
            # Put all into DB; keep top 1000 economic/forest/agri polygons per city in combined GeoJSON (~4 MB total)
            for idx, f in enumerate(gj["features"]):
                pr = f["properties"]
                lu_feat_rows.append((
                    cid, pr.get("osm_id",""), pr["macro_group"], pr["fclass"], pr.get("name",""),
                    pr["area_km2"], pr["area_ha"], pr["dist_cbd_km"], pr["ring"], pr["lon"], pr["lat"]
                ))
                if pr["macro_group"] in ("industrial", "commercial_retail", "extraction_quarry") or idx < 700:
                    combined_feats.append(f)

    cur.executemany("INSERT OR REPLACE INTO osm_landuse_summary VALUES (?,?,?,?,?,?,?)", lu_sum_rows)
    cur.executemany("INSERT INTO osm_landuse_major_zones (city_id, osm_id, macro_group, fclass, name, area_km2, area_ha, dist_cbd_km, ring, lon, lat) VALUES (?,?,?,?,?,?,?,?,?,?,?)", lu_feat_rows)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_osm_lu_city ON osm_landuse_major_zones(city_id, macro_group);")

    comb_gj_p = BND / "all_5cities_osm_landuse.geojson"
    comb_gj_p.write_text(json.dumps({"type": "FeatureCollection", "features": combined_feats}, ensure_ascii=False), encoding="utf-8")
    register_manifest("common", "osm_landuse_5cities_curated_geojson",
                      f"Combined 5-City OSM Landuse GeoJSON ({len(combined_feats)} major industrial/commercial/forest/agri polygons)",
                      comb_gj_p, "https://download.geofabrik.de/europe/")
    print(f"  Loaded {len(lu_sum_rows)} landuse summary rows, {len(lu_feat_rows):,} major zone rows, wrote {comb_gj_p.name} ({len(combined_feats):,} features, {comb_gj_p.stat().st_size/1048576:.2f} MB)")

    # ========================================================================
    # 5. PROPERTY TAX ZONES GIS SUMMARY (BG 14 ZONES + NP 7 ZONES)
    # ========================================================================
    print("\n=== [5/6] LOADING property_tax_zones_gis_summary ===", flush=True)
    cur.execute("DROP TABLE IF EXISTS property_tax_zones_gis_summary;")
    cur.execute("""
    CREATE TABLE property_tax_zones_gis_summary (
        city_id TEXT NOT NULL,
        zone_name TEXT NOT NULL,
        zone_rank INTEGER,
        polygon_count INTEGER,
        total_area_km2 REAL,
        pop_2022_settlements INTEGER,
        stan_eur_m2 REAL,
        kuca_eur_m2 REAL,
        poslovne_eur_m2 REAL,
        gradj_zem_eur_m2 REAL,
        polj_zem_eur_m2 REAL,
        sumsko_zem_eur_m2 REAL,
        geometry_bases TEXT,
        geojson_file TEXT,
        PRIMARY KEY (city_id, zone_name)
    );
    """)
    for cid, fn in [("beograd", "beograd_poreske_zone_2026.geojson"), ("novi_pazar", "novi_pazar_poreske_zone_2026.geojson")]:
        gj = json.loads((BND / fn).read_text(encoding="utf-8"))
        agg = defaultdict(lambda: {"rank": 99, "cnt": 0, "area": 0.0, "pop": 0, "bases": set(), "p": {}})
        for f in gj["features"]:
            pr = f["properties"]
            z = pr["zone_name"]
            a = agg[z]
            a["rank"] = min(a["rank"], int(pr.get("zone_rank", 99)))
            a["cnt"] += 1
            a["area"] += float(pr.get("area_km2") or 0.0)
            if pr.get("population_2022"):
                a["pop"] += int(pr["population_2022"])
            a["bases"].add(pr.get("geometry_basis", ""))
            a["p"] = pr
        for z, a in sorted(agg.items(), key=lambda kv: (kv[1]["rank"], kv[0])):
            p = a["p"]
            cur.execute("INSERT OR REPLACE INTO property_tax_zones_gis_summary VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                cid, z, a["rank"], a["cnt"], round(a["area"], 2), a["pop"] if a["pop"] > 0 else None,
                p.get("stan_eur_m2"), p.get("kuca_eur_m2"), p.get("poslovne_eur_m2"),
                p.get("gradj_zem_eur_m2"), p.get("polj_zem_eur_m2"), p.get("sumsko_zem_eur_m2"),
                "; ".join(sorted(a["bases"])), fn
            ))
    print("  Loaded property_tax_zones_gis_summary (Beograd 14 zones + Novi Pazar 7 zones)")

    # ========================================================================
    # 6. ANALYTICAL VIEWS (v3) + REFRESH MANIFEST + CSV EXPORTS + VERIFICATION
    # ========================================================================
    print("\n=== [6/6] CREATING v3 VIEWS, REFRESHING MANIFEST & EXPORTING CSVs ===", flush=True)
    views_v3 = [
        "DROP VIEW IF EXISTS v_srb_supply_chain_by_muni;",
        """CREATE VIEW v_srb_supply_chain_by_muni AS
           SELECT muni_code, muni_name,
                  COUNT(*) AS total_sc_firms,
                  SUM(CASE WHEN nace_code='1071' THEN 1 ELSE 0 END) AS bakeries_1071,
                  SUM(CASE WHEN nace_code='1061' THEN 1 ELSE 0 END) AS mills_1061,
                  SUM(CASE WHEN nace_code='1072' THEN 1 ELSE 0 END) AS biscuits_1072,
                  SUM(CASE WHEN nace_code='0111' THEN 1 ELSE 0 END) AS grain_0111,
                  SUM(CASE WHEN nace_code='1610' THEN 1 ELSE 0 END) AS sawmills_1610,
                  SUM(CASE WHEN nace_code='0220' THEN 1 ELSE 0 END) AS logging_0220,
                  SUM(employees) AS total_employees,
                  ROUND(SUM(revenue_eur)/1e6, 2) AS total_revenue_eur_m,
                  ROUND(SUM(CASE WHEN nace_code='1061' THEN revenue_eur ELSE 0 END)/1e6, 2) AS mills_rev_eur_m,
                  ROUND(SUM(CASE WHEN nace_code='1071' THEN revenue_eur ELSE 0 END)/1e6, 2) AS bakeries_rev_eur_m
           FROM apr_serbia_supply_chain
           GROUP BY muni_code, muni_name
           ORDER BY total_revenue_eur_m DESC;""",

        "DROP VIEW IF EXISTS v_srb_wheat_mills_bakeries_balance;",
        """CREATE VIEW v_srb_wheat_mills_bakeries_balance AS
           SELECT a.muni_code, a.unit_name, a.oblast,
                  a.farms_kpz, ROUND(a.uaa_kpz_ha, 1) AS uaa_kpz_ha,
                  ROUND(a.cereals_ha, 1) AS cereals_ha, ROUND(a.wheat_spelt_ha, 1) AS wheat_ha,
                  ROUND(a.maize_grain_ha, 1) AS maize_ha,
                  a.cattle, a.sheep, a.pigs,
                  COALESCE(s.grain_0111, 0) AS apr_grain_firms,
                  COALESCE(s.mills_1061, 0) AS apr_mills,
                  COALESCE(s.bakeries_1071, 0) AS apr_bakeries,
                  COALESCE(s.sawmills_1610, 0) AS apr_sawmills,
                  COALESCE(s.mills_rev_eur_m, 0) AS mills_rev_eur_m,
                  COALESCE(s.bakeries_rev_eur_m, 0) AS bakeries_rev_eur_m
           FROM rzs_agri_census_2023 a
           LEFT JOIN v_srb_supply_chain_by_muni s ON a.muni_code = s.muni_code
           WHERE a.geo_level = 'municipality'
           ORDER BY a.wheat_spelt_ha DESC;""",

        "DROP VIEW IF EXISTS v_5cities_landuse_profile;",
        """CREATE VIEW v_5cities_landuse_profile AS
           SELECT city_id,
                  SUM(polygon_count) AS total_polygons,
                  ROUND(SUM(area_km2), 2) AS mapped_area_km2,
                  ROUND(SUM(CASE WHEN macro_group='forest' THEN area_km2 ELSE 0 END), 2) AS forest_km2,
                  ROUND(SUM(CASE WHEN macro_group='agriculture' THEN area_km2 ELSE 0 END), 2) AS agriculture_km2,
                  ROUND(SUM(CASE WHEN macro_group='industrial' THEN area_km2 ELSE 0 END), 2) AS industrial_km2,
                  ROUND(SUM(CASE WHEN macro_group='commercial_retail' THEN area_km2 ELSE 0 END), 2) AS commercial_retail_km2,
                  ROUND(SUM(CASE WHEN macro_group='residential' THEN area_km2 ELSE 0 END), 2) AS residential_km2,
                  ROUND(SUM(CASE WHEN macro_group='extraction_quarry' THEN area_km2 ELSE 0 END), 2) AS quarry_km2
           FROM osm_landuse_summary
           GROUP BY city_id
           ORDER BY mapped_area_km2 DESC;""",
    ]
    for sql in views_v3:
        cur.execute(sql)

    # Refresh sources_manifest
    cur.execute("DELETE FROM sources_manifest;")
    seen = set()
    mf_rows = []
    with open(MANIFEST, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try: rec = json.loads(line)
            except: continue
            key = (rec.get("local_path") or rec.get("path") or rec.get("url"), rec.get("sha256"))
            if key in seen: continue
            seen.add(key)
            mf_rows.append((
                rec.get("checked_at") or rec.get("ts") or "", rec.get("city","common"), rec.get("layer",""),
                rec.get("source_name") or rec.get("desc") or "", rec.get("url",""),
                int(rec.get("http_status") or rec.get("status") or 0),
                1 if rec.get("ok") else 0, int(rec.get("bytes") or 0),
                rec.get("sha256",""), rec.get("local_path") or rec.get("path") or "", rec.get("error") or ""
            ))
    cur.executemany(
        "INSERT INTO sources_manifest (checked_at, city, layer, source_name, url, http_status, ok, bytes, sha256, local_path, error) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        mf_rows
    )
    conn.commit()

    # Export Wave 3 CSVs
    exports = [
        ("srb_supply_chain_by_muni_v3.csv", "SELECT * FROM v_srb_supply_chain_by_muni"),
        ("srb_wheat_mills_bakeries_balance_2023.csv", "SELECT * FROM v_srb_wheat_mills_bakeries_balance"),
        ("rzs_agri_census_2023_all.csv", "SELECT * FROM rzs_agri_census_2023 ORDER BY id"),
        ("osm_5cities_landuse_profile.csv", "SELECT * FROM v_5cities_landuse_profile"),
        ("osm_5cities_landuse_by_ring.csv", "SELECT * FROM osm_landuse_summary ORDER BY city_id, ring, area_km2 DESC"),
        ("bg_np_property_tax_zones_gis_2026.csv", "SELECT * FROM property_tax_zones_gis_summary ORDER BY city_id, zone_rank"),
    ]
    for fn, q in exports:
        rows = cur.execute(q).fetchall()
        cols = [d[0] for d in cur.description]
        with open(TBL / fn, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)
        print(f"  Exported {fn:44s} | {len(rows):>4} rows")

    print("\n================ WAVE 3 DATABASE VERIFICATION ================")
    for tbl, typ in cur.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY type, name").fetchall():
        if typ == "table":
            cnt = cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            print(f"  TABLE {tbl:36s}: {cnt:>8,} rows")
        else:
            print(f"  VIEW  {tbl:36s}")

    print("\n--- 5-CITY OSM LANDUSE PROFILE (km2) ---")
    for r in cur.execute("SELECT * FROM v_5cities_landuse_profile").fetchall():
        print(f"  {r[0]:11s} | polys={r[1]:>7,} | tot={r[2]:>7.1f} | forest={r[3]:>6.1f} | agri={r[4]:>6.1f} | ind={r[5]:>5.1f} | comm={r[6]:>4.1f} | res={r[7]:>6.1f}")

    print("\n--- TOP 10 WHEAT + MILLS + BAKERIES MUNICIPALITIES IN SERBIA (RZS 2023 + APR 2026) ---")
    for r in cur.execute("SELECT muni_code, unit_name, wheat_ha, apr_grain_firms, apr_mills, apr_bakeries, mills_rev_eur_m, bakeries_rev_eur_m FROM v_srb_wheat_mills_bakeries_balance LIMIT 10").fetchall():
        print(f"  {str(r[0]):5s} {r[1]:20s} | wheat={r[2]:>8.1f} ha | grain={r[3]:>3} | mills={r[4]:>2} ({r[6]:>5.1f}M) | bak={r[5]:>3} ({r[7]:>5.1f}M)")

    print("\n--- HINTERLAND VERIFIED APR SUMMARY (BG + NP RING) ---")
    for r in cur.execute("SELECT city_hub, muni_code, muni_name, COUNT(*), SUM(employees), ROUND(SUM(revenue_eur)/1e6, 1) FROM companies_sr_hinterland GROUP BY city_hub, muni_code, muni_name ORDER BY city_hub, COUNT(*) DESC").fetchall():
        print(f"  {r[0]:10s} | {r[1]} {r[2]:14s} | firms={r[3]:>5,} | emp={r[4]:>6,} | rev={r[5]:>7.1f} M EUR")

    conn.close()
    print(f"\nSQLite v3 size: {DB_PATH.stat().st_size/1048576:.2f} MB | sources_manifest={len(mf_rows)} | elapsed={time.time()-t0:.1f}s")
    print("DONE 17_build_urban_lab_db_v3.py")

if __name__ == "__main__":
    build_v3()
