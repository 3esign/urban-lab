from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import csv, json, math, os, re, sqlite3, time
from collections import Counter, defaultdict
from pathlib import Path
import openpyxl

BASE = Path(str(DB_DIR))
RAW = BASE / "raw"
CUR = BASE / "curated"
BND = CUR / "boundaries"
TBL = CUR / "tables"
DB_PATH = CUR / "urban_lab_5cities.sqlite"

RSD_PER_EUR = 117.0
BAM_PER_EUR = 1.95583

CBD = {
    "beograd":    (44.8125, 20.4612),
    "zagreb":     (45.8130, 15.9772),
    "sarajevo":   (43.8563, 18.4131),
    "novi_pazar": (43.1367, 20.5122),
    "travnik":    (44.2264, 17.6658),
}

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(min(1.0, math.sqrt(a)))

def dist_ring(km):
    if km <= 1.0: return "0-1 km (CBD)"
    if km <= 3.0: return "1-3 km (Inner)"
    if km <= 6.0: return "3-6 km (Urban)"
    if km <= 15.0: return "6-15 km (Suburban)"
    return "15+ km (Hinterland L)"

def parse_eurostat_json(path):
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

def norm_name(s):
    if not s: return ""
    t = str(s).lower().strip()
    for a, b in [("č","c"),("ć","c"),("š","s"),("ž","z"),("đ","dj"),("dž","dz"),("grad ",""),("općina ",""),("opstina ",""),(" municipality",""),(" city","")]:
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t).strip()


def build_v2():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")

    print("=== [1/9] UPGRADING CITIES & FISCAL_BUDGETS (Zagreb FINA firms + SBK 2026 cantonal budget) ===")
    cur.execute("""UPDATE cities
        SET registered_companies = 54075,
            companies_scope = 'FINA aktivni poduzetnici 2025 prel. (2024 konačno: 52.718; prihod 89,8 mlrd EUR; +11.867 u Zagrebačkoj žup.)'
        WHERE city_id = 'zagreb';""")
    cur.execute("DELETE FROM fiscal_budgets WHERE source_doc LIKE 'wave2:%';")
    wave2_budgets = [
        ("travnik", "Kanton SBK/KSB (rebalans jul 2026)", "canton", 2026, "BAM", 496189872.0, round(496189872.0/BAM_PER_EUR, 2), None, None, None, None, 243590, round((496189872.0/BAM_PER_EUR)/243590, 2), "adopted_rebalans", "wave2:sbk-ksb.gov.ba (jul 2026; inicijalni 470,59 M KM)"),
        ("sarajevo", "Grad Istočno Sarajevo (nivo grada 2024)", "city_hinterland", 2024, "BAM", 25500000.0, round(25500000.0/BAM_PER_EUR, 2), None, None, None, None, 61516, round((25500000.0/BAM_PER_EUR)/61516, 2), "adopted", "wave2:Grad Istocno Sarajevo budzet 2024 (6 opstina RS zasebno)"),
    ]
    cur.executemany("""INSERT INTO fiscal_budgets
        (city_id, entity_name, entity_level, year, currency, total_budget_local, total_budget_eur,
         capital_expenditure_local, capital_expenditure_eur, property_tax_rev_local, income_tax_rev_local,
         population_ref, per_capita_eur, status, source_doc)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", wave2_budgets)

    print("\n=== [2/9] REBUILDING OSM_POIS FOR ALL 5 CITIES (Geofabrik HTTP-Range: 77,330 features!) ===")
    cur.execute("DROP TABLE IF EXISTS osm_pois;")
    cur.execute("""
    CREATE TABLE osm_pois (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city_id TEXT NOT NULL,
        osm_id TEXT,
        layer TEXT,
        category TEXT,
        fclass TEXT,
        name TEXT,
        lat REAL,
        lon REAL,
        dist_cbd_km REAL,
        ring TEXT
    );
    """)
    CAT_MAP = {
        "bakery": "food_bakery", "butcher": "food_retail", "greengrocer": "food_retail", "marketplace": "food_market",
        "supermarket": "retail_grocery", "convenience": "retail_grocery", "beverages": "food_retail",
        "cafe": "hospitality", "restaurant": "hospitality", "fast_food": "hospitality", "bar": "hospitality", "pub": "hospitality",
        "hotel": "tourism", "hostel": "tourism", "guesthouse": "tourism", "motel": "tourism", "museum": "tourism", "attraction": "tourism",
        "bank": "finance", "atm": "finance",
        "pharmacy": "health", "hospital": "health", "clinic": "health", "doctors": "health", "dentist": "health",
        "school": "education", "university": "education", "college": "education", "kindergarten": "education",
        "railway_station": "transport_hub", "railway_halt": "transport_hub", "bus_station": "transport_hub", "bus_stop": "transport_local",
        "tram_stop": "transport_local", "airport": "transport_xl", "helipad": "transport_xl",
        "fuel": "energy_mobility", "industrial": "industry", "works": "industry", "mall": "retail_major", "department_store": "retail_major",
        "clothes": "retail_general", "furniture": "retail_general", "hardware": "retail_general", "doityourself": "retail_general",
    }
    osm_rows_to_insert = []
    bakeries_markets_geojson = []
    osm_counts = {}
    for cid in ["beograd", "zagreb", "sarajevo", "novi_pazar", "travnik"]:
        p = RAW / "wave2_osm" / f"geofabrik_osm_pois_{cid}.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        clat, clon = CBD[cid]
        cnt = 0
        for it in d["items"]:
            lat, lon = float(it["lat"]), float(it["lon"])
            dkm = round(haversine_km(clat, clon, lat, lon), 3)
            ring = dist_ring(dkm)
            fc = it.get("fclass", "")
            cat = CAT_MAP.get(fc, "other_" + (it.get("layer") or "poi"))
            osm_rows_to_insert.append((cid, it.get("osm_id"), it.get("layer"), cat, fc, it.get("name"), lat, lon, dkm, ring))
            cnt += 1
            if fc in ("bakery", "marketplace", "railway_station", "bus_station"):
                bakeries_markets_geojson.append({
                    "type": "Feature",
                    "properties": {
                        "city_id": cid, "fclass": fc, "category": cat, "name": it.get("name") or "",
                        "dist_cbd_km": dkm, "ring": ring, "osm_id": it.get("osm_id")
                    },
                    "geometry": {"type": "Point", "coordinates": [lon, lat]}
                })
        osm_counts[cid] = cnt
    cur.executemany(
        "INSERT INTO osm_pois (city_id, osm_id, layer, category, fclass, name, lat, lon, dist_cbd_km, ring) VALUES (?,?,?,?,?,?,?,?,?,?)",
        osm_rows_to_insert
    )
    cur.execute("CREATE INDEX idx_osm_city_fc ON osm_pois(city_id, fclass);")
    cur.execute("CREATE INDEX idx_osm_city_ring ON osm_pois(city_id, ring);")
    print(f"  Inserted {len(osm_rows_to_insert):,} OSM POIs across all 5 cities: {osm_counts}")

    # Write S-scale Bakeries, Markets & Transit Hubs GeoJSON
    s_gj_path = BND / "s_scale_bakeries_markets_5cities.geojson"
    s_gj_path.write_text(json.dumps({"type": "FeatureCollection", "features": bakeries_markets_geojson}, ensure_ascii=False), encoding="utf-8")
    print(f"  Wrote {s_gj_path.name}: {len(bakeries_markets_geojson):,} features ({s_gj_path.stat().st_size:,} B)")

    print("\n=== [3/9] LOADING HINTERLAND APR COMPANIES (SRB BG-RING + NP-RING) INTO companies_sr_hinterland ===")
    cur.execute("DROP TABLE IF EXISTS companies_sr_hinterland;")
    cur.execute("""
    CREATE TABLE companies_sr_hinterland (
        maticni_broj TEXT PRIMARY KEY,
        city_hub TEXT NOT NULL,
        muni_code TEXT,
        muni_name TEXT,
        name TEXT,
        nace_code TEXT,
        nace_2d TEXT,
        status TEXT,
        has_fi INTEGER,
        employees INTEGER,
        revenue_eur REAL,
        net_profit_eur REAL,
        assets_eur REAL
    );
    """)
    hint_comp_rows = []
    for city_hub, fn in [("beograd", "apr_beograd_hinterland.jsonl"), ("novi_pazar", "apr_novi_pazar_hinterland.jsonl")]:
        fp = RAW / "wave2_l" / fn
        if not fp.exists(): continue
        with open(fp, "r", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                mb = str(r.get("MaticniBroj") or "").strip()
                nace = str(r.get("SifraDelatnosti") or "").strip()
                fi = r.get("fi") or {}
                has_fi = 1 if fi else 0
                emp = int(round(float(fi.get("ProsecanBrojZaposlenih") or fi.get("BrojZaposlenih") or 0))) if fi else 0
                rev = round(float(fi.get("UkupniPrihodi") or fi.get("PoslovniPrihod") or 0) * 1000.0 / RSD_PER_EUR, 2) if fi else 0.0
                prof = round(float(fi.get("NetoDobitak") or 0) * 1000.0 / RSD_PER_EUR, 2) if fi else 0.0
                assets = round(float(fi.get("PoslovnaImovina") or fi.get("UkupnaAktiva") or 0) * 1000.0 / RSD_PER_EUR, 2) if fi else 0.0
                hint_comp_rows.append((
                    mb, city_hub, str(r.get("SifraOpstine") or ""), r.get("_muni_label") or "",
                    r.get("PoslovnoIme") or r.get("Naziv") or "", nace, nace[:2],
                    r.get("Status") or "", has_fi, emp, rev, prof, assets
                ))
    cur.executemany("INSERT OR REPLACE INTO companies_sr_hinterland VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", hint_comp_rows)
    cur.execute("CREATE INDEX idx_csh_hub_nace ON companies_sr_hinterland(city_hub, nace_code);")
    print(f"  Loaded {len(hint_comp_rows):,} APR hinterland companies (BG ring + NP ring)")

    print("\n=== [4/9] LOADING ZAGREB COMMERCIAL LEASES (320) & MARKETS (31) ===")
    cur.execute("DROP TABLE IF EXISTS zagreb_commercial_leases;")
    cur.execute("""
    CREATE TABLE zagreb_commercial_leases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contract_no TEXT,
        contract_type TEXT,
        tenant TEXT,
        address TEXT,
        subject TEXT,
        sign_date TEXT,
        monthly_rent_eur REAL,
        status TEXT
    );
    """)
    zk_p = RAW / "wave2_l" / "ckan_dl_registar-ugovora-o-zakupu-korist_64a475.xlsx"
    if zk_p.exists():
        wb = openpyxl.load_workbook(zk_p, read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]
        z_ins = []
        for i, r in enumerate(ws.iter_rows(values_only=True)):
            if i < 2 or not r[0]: continue
            try: rent = float(r[15]) if r[15] not in (None, "") else 0.0
            except: rent = 0.0
            z_ins.append((str(r[5] or ""), str(r[7] or ""), str(r[8] or ""), str(r[9] or ""), str(r[10] or ""), str(r[11] or "")[:10], rent, str(r[21] or "")))
        wb.close()
        cur.executemany("INSERT INTO zagreb_commercial_leases (contract_no, contract_type, tenant, address, subject, sign_date, monthly_rent_eur, status) VALUES (?,?,?,?,?,?,?,?)", z_ins)
        paid = [x[6] for x in z_ins if x[6] > 0]
        paid.sort()
        med_rent = paid[len(paid)//2] if paid else 0
        print(f"  Loaded {len(z_ins)} Zagreb municipal commercial leases (paid={len(paid)}, median={med_rent:.2f} EUR/month)")

    cur.execute("DROP TABLE IF EXISTS zagreb_markets;")
    cur.execute("""
    CREATE TABLE zagreb_markets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        address TEXT,
        lon REAL,
        lat REAL,
        dist_cbd_km REAL,
        operator TEXT
    );
    """)
    tr_p = RAW / "wave2_l" / "ckan_dl_geoportal-gradske-trznice_a24500.csv"
    if tr_p.exists():
        with open(tr_p, "r", encoding="utf-8-sig", errors="replace") as f:
            rdr = csv.DictReader(f)
            m_ins = []
            for row in rdr:
                try:
                    lon, lat = float(row["X"]), float(row["Y"])
                except:
                    continue
                dkm = round(haversine_km(CBD["zagreb"][0], CBD["zagreb"][1], lat, lon), 2)
                m_ins.append((row.get("naziv",""), row.get("adresa",""), lon, lat, dkm, row.get("nadlezan","")))
            cur.executemany("INSERT INTO zagreb_markets (name, address, lon, lat, dist_cbd_km, operator) VALUES (?,?,?,?,?,?)", m_ins)
            print(f"  Loaded {len(m_ins)} Zagreb official markets (Tržnice Zagreb)")

    print("\n=== [5/9] LOADING L-SCALE: HINTERLAND UNITS, COMMUTING FLOWS, AGRI/FORESTRY/TRADE ===")
    # 5A. RZS Popis 2022 Commuting Flows + Zagreb O-D top flows
    cur.execute("DROP TABLE IF EXISTS commuting_and_flows;")
    cur.execute("""
    CREATE TABLE commuting_and_flows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city_hub TEXT NOT NULL,
        origin_name TEXT NOT NULL,
        dest_scope TEXT NOT NULL,
        flow_type TEXT NOT NULL,
        commuters_total INTEGER,
        within_same_muni INTEGER,
        other_muni_same_area INTEGER,
        other_area_commuters INTEGER,
        foreign_commuters INTEGER,
        year INTEGER,
        source_ref TEXT
    );
    """)
    comm_p = RAW / "wave2_l" / "parsed_rzs_commuting_2022.json"
    comm_map = {}
    if comm_p.exists():
        c_data = json.loads(comm_p.read_text(encoding="utf-8"))
        bg_ring_set = {"pančevo", "stara pazova", "inđija", "pećinci", "ruma", "smederevo", "valjevo"}
        np_set = {"novi pazar", "tutin", "sjenica", "raška"}
        c_ins = []
        for r in c_data:
            nm = r["name"]
            nl = nm.lower()
            if nl in np_set:
                hub = "novi_pazar"
                dscope = "core_city" if nl == "novi pazar" else "hinterland_ring_L"
            elif nl in bg_ring_set:
                hub = "beograd"
                dscope = "hinterland_ring_L"
            else:
                hub = "beograd"
                dscope = "beograd_core_or_suburban_muni"
            c_ins.append((hub, nm, dscope, "daily_work_commuting_census", int(r["total_commuters"] or 0), int(r["same_muni"] or 0), int(r["other_muni_same_area"] or 0), int(r["other_area"] or 0), int(r["foreign"] or 0), 2022, "RZS Popis 2022 dnevne_migracije.xlsx"))
            comm_map[norm_name(nm)] = r
        cur.executemany("INSERT INTO commuting_and_flows (city_hub, origin_name, dest_scope, flow_type, commuters_total, within_same_muni, other_muni_same_area, other_area_commuters, foreign_commuters, year, source_ref) VALUES (?,?,?,?,?,?,?,?,?,?,?)", c_ins)
        print(f"  Loaded {len(c_ins)} RZS Popis 2022 commuting records")

    # Also summarize Zagreb O-D matrix (308x308) total daily trips into commuting_and_flows
    od_p = RAW / "zagreb" / "o-d-matrica-putovanja_csv.csv"
    if od_p.exists():
        with open(od_p, "r", encoding="utf-8-sig", errors="replace") as f:
            lines = [l.strip() for l in f if l.strip()]
        sep = ";" if ";" in lines[0] else ","
        hdr = lines[0].split(sep)
        total_trips = 0.0
        intra_trips = 0.0
        inter_trips = 0.0
        zone_count = 0
        for row_i, l in enumerate(lines[1:]):
            parts = l.split(sep)
            if len(parts) < 3: continue
            zone_count += 1
            for col_j, val in enumerate(parts[1:]):
                try:
                    v = float(val.replace(",", "."))
                    total_trips += v
                    if col_j == row_i: intra_trips += v
                    else: inter_trips += v
                except: pass
        cur.execute(
            "INSERT INTO commuting_and_flows (city_hub, origin_name, dest_scope, flow_type, commuters_total, within_same_muni, other_muni_same_area, other_area_commuters, foreign_commuters, year, source_ref) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("zagreb", f"Zagreb Traffic Model ({zone_count} zones)", "zagreb_core_and_fua", "od_daily_trips_matrix", int(round(total_trips)), int(round(intra_trips)), int(round(inter_trips)), 0, 0, 2022, "data.zagreb.hr o-d-matrica-putovanja_csv.csv")
        )
        print(f"  Summarized Zagreb O-D matrix ({zone_count} zones): total={total_trips:,.0f} trips (intra={intra_trips:,.0f}, inter={inter_trips:,.0f})")

    # 5B. Hinterland Units (L-scale comparative table across ALL 5 CITIES)
    cur.execute("DROP TABLE IF EXISTS hinterland_units;")
    cur.execute("""
    CREATE TABLE hinterland_units (
        unit_id TEXT PRIMARY KEY,
        city_hub TEXT NOT NULL,
        country_iso TEXT NOT NULL,
        unit_name TEXT NOT NULL,
        admin_region TEXT,
        dist_cbd_km REAL,
        ring_role TEXT NOT NULL,
        population INTEGER,
        pop_year INTEGER,
        employees INTEGER,
        net_wage_eur REAL,
        firms_count INTEGER,
        commuters_total INTEGER,
        commuters_external INTEGER,
        supply_chain_role TEXT,
        source_ref TEXT
    );
    """)

    # Collect APR hinterland summary
    apr_h_map = {}
    apr_sum_p = RAW / "wave2_l" / "apr_hinterland_summary.json"
    if apr_sum_p.exists():
        for m in json.loads(apr_sum_p.read_text(encoding="utf-8")).get("municipalities", []):
            apr_h_map[norm_name(m["name"])] = m

    # Verified hinterland records for all 5 cities (from FZS SBK 2025, FZS ZDK 2026, APR 2026, RZS Popis 2022, DZS/FINA 2024/2025, geoBoundaries)
    HINTERLAND_DATA = [
        # BEOGRAD L-RING (outside 17 BG municipalities; RZS Popis 2022 commuting + APR 2026 + Eurostat NUTS3)
        ("bg_l_pancevo", "beograd", "SRB", "Pančevo", "Južnobanatska oblast", 17.5, "industrial_commuter_satellite", 115454, 2022, None, None, None, 18817, 10866, "Žitarice (Banat), petrohemija, najveći dnevni komuterski priliv u BG (10.866)", "RZS Popis 2022 + Eurostat RS122"),
        ("bg_l_stara_pazova", "beograd", "SRB", "Stara Pazova", "Sremska oblast", 29.0, "logistics_industrial_commuter", 62318, 2022, None, None, 125, 13050, 6356, "Logistički parkovi na Koridoru X, mlinovi/pekarska industrija, 6.356 dnevnih migranata", "RZS Popis 2022 + APR 2026 + Eurostat RS127"),
        ("bg_l_indjija", "beograd", "SRB", "Inđija", "Sremska oblast", 43.0, "agri_industrial_corridor", 43443, 2022, None, None, 1376, 7343, 2391, "69 APR firmi za žitarice (Srem žitnica) + IT/industrijska zona na Koridoru X", "RZS Popis 2022 + APR 2026"),
        ("bg_l_pecinci", "beograd", "SRB", "Pećinci", "Sremska oblast", 40.0, "logistics_agri_hub", 18401, 2022, None, None, 1895, 4694, 1496, "36 APR firmi za žitarice, 5 mlinova, 10 pekara, 24 drvne — Šimanovci logistički hab", "RZS Popis 2022 + APR 2026"),
        ("bg_l_ruma", "beograd", "SRB", "Ruma", "Sremska oblast", 57.0, "agri_industrial_corridor", 48621, 2022, None, None, 646, 7374, 1952, "26 firmi žitarice, 2 mlina, 10 drvo; čvorište A3–Fruškogorski koridor", "RZS Popis 2022 + APR 2026"),
        ("bg_l_smederevo", "beograd", "SRB", "Smederevo", "Podunavska oblast", 44.0, "heavy_industry_agri_port", 97930, 2022, None, None, 1020, None, None, "Dunavska luka, čeličana, voćarstvo/vinogradarstvo, 10 firmi žitarice", "RZS Popis 2022 + APR 2026"),
        ("bg_l_valjevo", "beograd", "SRB", "Valjevo", "Kolubarska oblast", 77.0, "regional_industrial_timber", 82169, 2022, None, None, 230, 9079, 1753, "3 mlina, 5 drvnih firmi, brza saobraćajnica ka A2 (Miloš Veliki)", "RZS Popis 2022 + APR 2026"),

        # ZAGREB L-RING (Zagrebačka županija — Eurostat FUA 1,225,505; FINA 2024: 11,867 firms, 87,866 emp, 14.5B EUR rev; OPG 2024: 11,056 OPGs)
        ("zg_l_velika_gorica", "zagreb", "HRV", "Velika Gorica", "Zagrebačka županija", 14.5, "airport_commuter_logistics", 61075, 2021, None, 1517.0, None, None, None, "Međunarodni aerodrom ZAG (4,72M putnika), najveći poduzetnički centar ZŽ, Turopolje poljoprivreda/šume", "DZS Popis 2021 + FINA 2024 + Eurostat HR065"),
        ("zg_l_samobor", "zagreb", "HRV", "Samobor", "Zagrebačka županija", 20.5, "suburban_craft_tourism", 37435, 2021, None, 1517.0, None, None, None, "Snažno obrtništvo, gastronomija/pekarstvo, šumsko zaleđe Samoborskog gorja, dnevni komuteri", "DZS Popis 2021 + FINA 2024"),
        ("zg_l_zapresic", "zagreb", "HRV", "Zaprešić", "Zagrebačka županija", 15.5, "suburban_rail_commuter", 24133, 2021, None, 1517.0, None, None, None, "Prigradska željeznica HŽ zapad, stambeno-poslovni satelit Zagreba", "DZS Popis 2021 + FINA 2024"),
        ("zg_l_sveta_nedelja", "zagreb", "HRV", "Sveta Nedelja", "Zagrebačka županija", 16.0, "tax_competitive_tech_logistics", 18221, 2021, None, 1517.0, None, None, None, "Nulti prirez/porezna konkurentnost, Rimac/IT i logistički centri — obrnut tok radnika iz ZG!", "DZS Popis 2021 + FINA 2024"),
        ("zg_l_dugo_selo", "zagreb", "HRV", "Dugo Selo", "Zagrebačka županija", 20.0, "rail_logistics_commuter", 17676, 2021, None, 1517.0, None, None, None, "Glavno željezničko čvorište istok (veza prema Slavoniji/žitnici i Mađarskoj)", "DZS Popis 2021 + FINA 2024"),
        ("zg_l_jastrebarsko", "zagreb", "HRV", "Jastrebarsko", "Zagrebačka županija", 32.0, "agri_wine_logistics_A1", 14562, 2021, None, 1517.0, None, None, None, "Poslovna zona uz A1, vinarstvo Plešivica, šumarstvo i OPG baza", "DZS Popis 2021 + HR Upisnik PG 2024"),
        ("zg_l_ivanic_grad", "zagreb", "HRV", "Ivanić-Grad", "Zagrebačka županija", 35.0, "energy_agri_A3", 12982, 2021, None, 1517.0, None, None, None, "Moslavina poljoprivreda/uljarice/žitarice, energetski čvor uz A3", "DZS Popis 2021 + HR Upisnik PG 2024"),
        ("zg_l_vrbovec", "zagreb", "HRV", "Vrbovec", "Zagrebačka županija", 36.0, "food_processing_agri_hub", 12981, 2021, None, 1517.0, None, None, None, "Prehrambena industrija (PIK Vrbovec) i stočarsko-ratarska opskrba Zagreba", "DZS Popis 2021 + HR Upisnik PG 2024"),
        ("zg_l_sv_ivan_zelina", "zagreb", "HRV", "Sveti Ivan Zelina", "Zagrebačka županija", 27.0, "agri_vineyard_commuter", 14602, 2021, None, 1517.0, None, None, None, "Prigorje OPG-ovi, voćarstvo/vinogradarstvo i prigradski komuteri", "DZS Popis 2021 + HR Upisnik PG 2024"),

        # SARAJEVO L-RING (Cross-entity RS + ZDK + SBK! Exact FZS ZDK 2026 & FZS SBK 2025 verified numbers!)
        ("sa_l_istocno_novo_sa", "sarajevo", "BIH", "Istočno Novo Sarajevo", "Grad Istočno Sarajevo (RS)", 4.8, "cross_entity_urban_extension", 10642, 2013, None, 700.0, None, None, None, "Neposredni prekogranični (entitetski) produžetak Sarajeva: stanogradnja, trgovina, dnevni komuteri", "Popis 2013 + Grad Istočno Sarajevo"),
        ("sa_l_istocna_ilidza", "sarajevo", "BIH", "Istočna Ilidža", "Grad Istočno Sarajevo (RS)", 7.5, "cross_entity_airport_commuter", 14763, 2013, None, 700.0, None, None, None, "Uz aerodrom SJJ i Dobrinju; svakodnevna dvosmerna integracija rada i potrošnje sa KS", "Popis 2013 + Grad Istočno Sarajevo"),
        ("sa_l_pale", "sarajevo", "BIH", "Pale", "Grad Istočno Sarajevo (RS)", 15.0, "university_timber_mountain_tourism", 20909, 2013, None, 700.0, None, None, None, "Univerzitet, Jahorina turizam, snažno šumarstvo i drvoprerada (ogrevno drvo/pilane za SA)", "Popis 2013 + Grad Istočno Sarajevo"),
        ("sa_l_sokolac", "sarajevo", "BIH", "Sokolac", "Grad Istočno Sarajevo (RS)", 34.0, "forestry_timber_livestock_plateau", 12021, 2013, None, 670.0, None, None, None, "Romanijski plato: drvna industrija, ogrevno drvo i stočarstvo za sarajevsku kotlinu", "Popis 2013"),
        ("sa_l_visoko", "sarajevo", "BIH", "Visoko", "Zeničko-dobojski kanton (ZDK)", 24.0, "industrial_food_export_corridor", 39938, 2013, 10301, round(991.0/BAM_PER_EUR, 2), 991, None, None, "Koridor Vc sever: 991 pravno lice, 10.301 zaposlen, kožarska/mesna/prehrambena industrija i mlinovi za SA", "FZS ZDK u brojkama 2026 (p.12, p.17)"),
        ("sa_l_breza", "sarajevo", "BIH", "Breza", "Zeničko-dobojski kanton (ZDK)", 24.5, "mining_energy_commuter", 14168, 2013, 2698, round(1358.0/BAM_PER_EUR, 2), 233, None, None, "Rudnik mrkog uglja (energetika), 2.698 zap., visoka plata (1.358 KM), dnevni komuteri ka Ilijašu/SA", "FZS ZDK u brojkama 2026 (p.12, p.17)"),
        ("sa_l_kakanj", "sarajevo", "BIH", "Kakanj", "Zeničko-dobojski kanton (ZDK)", 41.0, "energy_cement_corridor_Vc", 37441, 2013, 6731, round(1451.0/BAM_PER_EUR, 2), 514, None, None, "Termoelektrana Kakanj + Tvornica cementa (energetska i građevinska kičma Koridora Vc)", "FZS ZDK u brojkama 2026 (p.12, p.17)"),
        ("sa_l_kiseljak", "sarajevo", "BIH", "Kiseljak", "Srednjobosanski kanton (SBK)", 27.0, "bridge_trade_beverage_commuter", 19967, 2024, 4420, round(1066.0/BAM_PER_EUR, 2), 455, None, None, "Zapadni ulaz u SA (most KS–SBK): Sarajevski kiseljak, trgovina, građevinarstvo, 4.420 zap.", "FZS SBK u brojkama 2025 (p.12, p.15)"),
        ("sa_l_kresevo", "sarajevo", "BIH", "Kreševo", "Srednjobosanski kanton (SBK)", 30.0, "craft_industry_timber", 4732, 2024, 1261, round(1252.0/BAM_PER_EUR, 2), 130, None, None, "Visoka stopa zaposlenosti po glavi, metaloprerada, šumarstvo i građ. materijali za SA", "FZS SBK u brojkama 2025 (p.12, p.15)"),
        ("sa_l_fojnica", "sarajevo", "BIH", "Fojnica", "Srednjobosanski kanton (SBK)", 40.0, "forestry_spa_tourism", 11148, 2024, 2306, round(1112.0/BAM_PER_EUR, 2), 185, None, None, "Šumarstvo/ogrevno drvo (Vranica), banjski turizam Reumal", "FZS SBK u brojkama 2025 (p.12, p.15)"),

        # NOVI PAZAR L-RING (Tutin, Sjenica, Raška — APR 2026 + RZS Popis 2022)
        ("np_l_tutin", "novi_pazar", "SRB", "Tutin", "Raška oblast", 24.0, "timber_furniture_commuter_ring", 33053, 2022, None, None, 317, None, None, "Peštersko-šumsko zaleđe: 317 APR firmi (7 drvo/pilane, 0 mlinova), nameštaj, dijaspora, radna veza sa NP", "RZS Popis 2022 + APR 2026"),
        ("np_l_sjenica", "novi_pazar", "SRB", "Sjenica", "Zlatiborska oblast", 43.0, "livestock_dairy_plateau_corridor", 24083, 2022, None, None, 137, 847, 68, "Pešterska visoravan: stočarstvo, mlekarstvo (sjenički sir/meso za NP i BG), buduća petlja Duga Poljana A2!", "RZS Popis 2022 + APR 2026"),
        ("np_l_raska", "novi_pazar", "SRB", "Raška", "Raška oblast", 19.5, "rail_gateway_kopaonik_corridor", 21498, 2022, None, None, 70, 4392, 390, "Najbliža železnička stanica za NP (Ibarska dolina), 1 mlin, Kopaonik turizam, glavna logistička kapija ka severu", "RZS Popis 2022 + APR 2026"),

        # TRAVNIK L-RING (Lašvanska dolina + SBK + Zenica/ZDK — exact FZS SBK 2025 & FZS ZDK 2026!)
        ("tr_l_vitez", "travnik", "BIH", "Vitez", "Srednjobosanski kanton (SBK)", 12.0, "retail_industrial_powerhouse", 25667, 2024, 6956, round(978.0/BAM_PER_EUR, 2), 890, None, None, "PC 96 trgovačko-industrijski gigant (FIS, namještaj, PVC, maloprodaja): 6.956 zap. na 25.667 st. — ekonomski blizanac Travnika!", "FZS SBK u brojkama 2025 (p.12, p.15)"),
        ("tr_l_novi_travnik", "travnik", "BIH", "Novi Travnik", "Srednjobosanski kanton (SBK)", 10.0, "industrial_defense_satellite", 23275, 2024, 4560, round(1238.0/BAM_PER_EUR, 2), 480, None, None, "Industrijski satelit (10 km): mašinska/namjenska industrija (BNT), viša plata od Travnika (1.238 vs 1.156 KM)", "FZS SBK u brojkama 2025 (p.12, p.15)"),
        ("tr_l_busovaca", "travnik", "BIH", "Busovača", "Srednjobosanski kanton (SBK)", 23.0, "corridor_forestry_transition", 17366, 2024, 2331, round(1094.0/BAM_PER_EUR, 2), 260, None, None, "Veza Lašvanske doline sa Koridorom Vc (Kaonik), šumarstvo i drvoprerada", "FZS SBK u brojkama 2025 (p.12, p.15)"),
        ("tr_l_donji_vakuf", "travnik", "BIH", "Donji Vakuf", "Srednjobosanski kanton (SBK)", 25.0, "forestry_timber_gateway_west", 13503, 2024, 2265, round(1177.0/BAM_PER_EUR, 2), 210, None, None, "Prevoj Komar — direktna sirovinska baza ŠPD Srednjobosanske šume (ogrevno drvo/trupci) za Travnik", "FZS SBK u brojkama 2025 (p.12, p.15)"),
        ("tr_l_bugojno", "travnik", "BIH", "Bugojno", "Srednjobosanski kanton (SBK)", 34.0, "agri_vrbas_valley_subcenter", 30449, 2024, 5837, round(1041.0/BAM_PER_EUR, 2), 540, None, None, "Skopaljska dolina: poljoprivreda, kožarstvo, metaloprerada, 5.837 zap.", "FZS SBK u brojkama 2025 (p.12, p.15)"),
        ("tr_l_jajce", "travnik", "BIH", "Jajce", "Srednjobosanski kanton (SBK)", 42.0, "hydro_energy_heritage_tourism", 25649, 2024, 3994, round(1297.0/BAM_PER_EUR, 2), 410, None, None, "Hidroenergetika (Pliva/Vrbas), turizam, zapadni kraj buduće brze ceste Lašva–Travnik–Jajce", "FZS SBK u brojkama 2025 (p.12, p.15)"),
        ("tr_l_zenica", "travnik", "BIH", "Zenica", "Zeničko-dobojski kanton (ZDK)", 24.5, "regional_industrial_rail_Vc_hub", 110663, 2013, 27248, round(1326.0/BAM_PER_EUR, 2), 1974, None, None, "Najbliža željeznica i Koridor Vc za Travnik (25 km): 27.248 zap., 1.974 pravna lica, čeličana i logistika", "FZS ZDK u brojkama 2026 (p.12, p.17)"),
    ]
    cur.executemany("INSERT INTO hinterland_units VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", HINTERLAND_DATA)
    print(f"  Loaded {len(HINTERLAND_DATA)} L-scale hinterland municipalities across all 5 city regions")

    # 5C. Hinterland Agriculture, Forestry, External Trade & Tourism (L/M regional metabolism)
    cur.execute("DROP TABLE IF EXISTS hinterland_agri_forestry_trade;")
    cur.execute("""
    CREATE TABLE hinterland_agri_forestry_trade (
        region_id TEXT PRIMARY KEY,
        city_hub TEXT NOT NULL,
        region_name TEXT NOT NULL,
        wheat_tonnes REAL,
        wheat_ha REAL,
        timber_total_m3 REAL,
        firewood_hardwood_m3 REAL,
        agri_farms_opg_count INTEGER,
        exports_mio_eur REAL,
        imports_mio_eur REAL,
        trade_coverage_pct REAL,
        tourism_nights INTEGER,
        tourism_year INTEGER,
        source_ref TEXT
    );
    """)
    H_METAB = [
        ("ks_sarajevo", "sarajevo", "Kanton Sarajevo (M)", 592.0, 162.0, 115000.0, 25000.0, None, round(1806.468/BAM_PER_EUR, 1), round(7396.468/BAM_PER_EUR, 1), 24.4, 1568480, 2025, "FZS KS 2026 (p.21,23,29) + ZPR KS 2025 (p.35,84)"),
        ("zdk_bridge", "sarajevo", "Zeničko-dobojski kanton (L-most SA↔TR)", 7796.0, 1887.0, 280000.0, 59000.0, None, round(2125.951/BAM_PER_EUR, 1), round(2194.311/BAM_PER_EUR, 1), 96.9, None, 2024, "FZS ZDK 2026 (p.21,23,29)"),
        ("sbk_travnik", "travnik", "Srednjobosanski kanton (M+L Travnik/Vitez)", 4395.0, 1346.0, 389000.0, 115000.0, None, round(892.783/BAM_PER_EUR, 1), round(1328.553/BAM_PER_EUR, 1), 67.2, None, 2024, "FZS SBK 2025 (p.19,21,28)"),
        ("zg_core", "zagreb", "Grad Zagreb (M)", None, None, None, None, 6047, None, None, None, 2721617, 2025, "HR Upisnik PG 2024 (4.058 OPG + 1.931 PG) + Eurostat tour_occ_nin2 2025"),
        ("zg_county_l", "zagreb", "Zagrebačka županija (L-prsten)", None, None, None, None, 13409, None, None, None, 1306374, 2025, "HR Upisnik PG 2024 (11.056 OPG + 2.188 PG) + Eurostat HR06 2025"),
        ("bg_region", "beograd", "Beogradski region + Srem/Banat prsten (M+L)", None, None, None, None, None, None, None, None, 3593933, 2025, "Eurostat tour_occ_nin2 RS11 2025 + APR (249 žito firmi, 38 mlinova u BG+prstenu)"),
        ("np_raska", "novi_pazar", "Novi Pazar + Raška/Pešter prsten (M+L)", None, None, None, None, None, None, None, None, 4679759, 2025, "Eurostat tour_occ_nin2 RS21 (region) 2025 + APR (5 žito firmi, 2 mlina, 37 drvno-građ.)"),
    ]
    cur.executemany("INSERT INTO hinterland_agri_forestry_trade VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", H_METAB)
    print(f"  Loaded {len(H_METAB)} regional metabolism rows (wheat, firewood m3, OPGs, trade coverage %, tourism nights)")

    # Build L-scale Hinterland GeoJSON from geoBoundaries (HRV_ADM2, BIH_ADM3, SRB_ADM2)
    print("  Building all_5cities_hinterland_l.geojson from official geoBoundaries...")
    h_by_norm = {norm_name(r[3]): r for r in HINTERLAND_DATA}
    h_features = []
    geo_sources = [
        ("SRB", RAW / "common" / "geoboundaries_SRB_ADM2.geojson"),
        ("HRV", RAW / "common" / "geoboundaries_HRV_ADM2.geojson"),
        ("BIH", RAW / "common" / "geoboundaries_BIH_ADM3.geojson"),
    ]
    matched_units = set()
    for iso, gp in geo_sources:
        gj = json.loads(gp.read_text(encoding="utf-8"))
        for ft in gj.get("features", []):
            sname = ft.get("properties", {}).get("shapeName", "")
            sn = norm_name(sname)
            # Disambiguate Croatia's "Općina Sveta Nedelja" (Istria) vs "Grad Sveta Nedelja" (Zagreb county) & "Općina Visoko" (HR) vs "Visoko" (BIH)
            if iso == "HRV" and ("općina sveta nedelja" in sname.lower() or "općina visoko" in sname.lower()):
                continue
            row = h_by_norm.get(sn)
            if row and row[2] == iso and row[0] not in matched_units:
                matched_units.add(row[0])
                h_features.append({
                    "type": "Feature",
                    "properties": {
                        "unit_id": row[0], "city_hub": row[1], "country_iso": row[2],
                        "unit_name": row[3], "admin_region": row[4], "dist_cbd_km": row[5],
                        "ring_role": row[6], "population": row[7], "employees": row[9],
                        "net_wage_eur": row[10], "firms_count": row[11],
                        "commuters_total": row[12], "commuters_external": row[13],
                        "supply_chain_role": row[14],
                    },
                    "geometry": ft["geometry"]
                })
    h_gj_path = BND / "all_5cities_hinterland_l.geojson"
    h_gj_path.write_text(json.dumps({"type": "FeatureCollection", "features": h_features}, ensure_ascii=False), encoding="utf-8")
    print(f"  Wrote {h_gj_path.name}: {len(h_features)}/{len(HINTERLAND_DATA)} matched L-ring polygons ({h_gj_path.stat().st_size:,} B)")

    print("\n=== [6/9] LOADING S-SCALE INPUT COSTS & COMPARATIVE BAKERY UNIT MODEL (5 CITIES) ===")
    # Extract exact 2026-S1 Eurostat business electricity prices (nrg_pc_205) for HR, RS, BA
    elec_map = {}
    nrg_p = RAW / "wave2_xl" / "eurostat_nrg_pc_205.json"
    if nrg_p.exists():
        for r in parse_eurostat_json(nrg_p):
            if r.get("time") == "2026-S1" and r.get("tax") == "X_VAT" and r.get("nrg_cons") in ("MWH_LT20", "MWH20-499"):
                elec_map[(r["geo"], r["nrg_cons"])] = float(r["value"])
    print("  Verified Eurostat 2026-S1 electricity (X_VAT EUR/kWh):", elec_map)

    cur.execute("DROP TABLE IF EXISTS s_scale_input_costs;")
    cur.execute("""
    CREATE TABLE s_scale_input_costs (
        city_id TEXT PRIMARY KEY,
        country_iso TEXT NOT NULL,
        elec_eur_kwh_small REAL,
        elec_eur_kwh_med REAL,
        flour_t500_eur_kg REAL,
        firewood_hardwood_eur_prm REAL,
        firewood_origin TEXT,
        flour_origin TEXT,
        min_wage_gross_eur REAL,
        min_wage_net_eur REAL,
        employer_labor_cost_mult REAL,
        vat_standard_pct REAL,
        vat_bread_pct REAL,
        corp_tax_small_pct REAL,
        commercial_rent_eur_m2_month REAL,
        bread_500g_retail_eur REAL,
        source_ref TEXT
    );
    """)
    S_INPUTS = [
        ("beograd", "SRB", elec_map.get(("RS","MWH_LT20"), 0.156), elec_map.get(("RS","MWH20-499"), 0.1679),
         0.29, 78.0, "L/XL (Šumadija/Podrinje/stovarišta; Srbijašume baza 42 EUR + prevoz/cepanje)", "L (Srem/Banat/Vojvodina, 249 žito firmi i 38 mlinova u prstenu)",
         744.0, 551.0, 1.1515, 20.0, 10.0, 15.0, 18.0, 0.70, "Eurostat nrg_pc_205 2026-S1 + earn_mw_cur 2026 + Srbijašume/InfoTim + poreski zakoni SRB 2026"),
        ("zagreb", "HRV", elec_map.get(("HR","MWH_LT20"), 0.222), elec_map.get(("HR","MWH20-499"), 0.1879),
         0.40, 75.0, "L (Turopolje/Samoborsko gorje/Hrvatske šume + dostava)", "L/XL (Zagrebačka žup. 11.056 OPG + Slavonija žitnica)",
         1050.0, 800.0, 1.165, 25.0, 5.0, 10.0, 22.0, 1.45, "Eurostat nrg_pc_205 2026-S1 + earn_mw_cur 2026 + Hrvatske šume + ZG registar zakupa + zakoni RH 2026"),
        ("sarajevo", "BIH", elec_map.get(("BA","MWH_LT20"), 0.1383), elec_map.get(("BA","MWH20-499"), 0.1273),
         0.55, 56.0, "L (Sarajevo-šume/Pale/Sokolac/Fojnica bukva)", "XL/L (KS proizvodi samo 592 t pšenice = 1,4% potreba -> uvoz SRB/HR/Posavina)",
         825.0, 525.0, 1.105, 17.0, 17.0, 10.0, 16.0, 1.02, "Eurostat nrg_pc_205 2026-S1 + FZS KS 2026 (592 t pšenice) + Odluka FBiH min. plaća 1.027 KM 2026"),
        ("novi_pazar", "SRB", elec_map.get(("RS","MWH_LT20"), 0.156), elec_map.get(("RS","MWH20-499"), 0.1679),
         0.33, 52.0, "L-lokalno (Golija/Rogozna/Tutin/Srbijašume — direktna blizina šume)", "XL (NP+prsten ima samo 5 žito firmi i 2 mlina -> doprema iz Vojvodine/Šumadije + transport)",
         744.0, 551.0, 1.1515, 20.0, 10.0, 15.0, 14.0, 0.65, "Eurostat nrg_pc_205 2026-S1 + APR 2026 NP/Tutin/Sjenica/Raška + poreske zone NP 2026"),
        ("travnik", "BIH", elec_map.get(("BA","MWH_LT20"), 0.1383), elec_map.get(("BA","MWH20-499"), 0.1273),
         0.55, 45.0, "L-lokalno (ŠPD Srednjobosanske šume / Komar / Vlašić: 115.000 m³ ogrevnog drveta u SBK!)", "L/XL (SBK 4.395 t + ZDK 7.796 t pšenice — delimično lokalno, većina mlinovi Jelah/uvoz)",
         825.0, 525.0, 1.105, 17.0, 17.0, 10.0, 9.0, 0.92, "Eurostat nrg_pc_205 2026-S1 + FZS SBK 2025 (115k m3 ogrevno drvo, 4.395 t pšenice) + FBiH 2026"),
    ]
    cur.executemany("INSERT INTO s_scale_input_costs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", S_INPUTS)

    # Calculate comparative S-scale Bakery Unit Economics Model (Standard Reference Artisan Bakery: 60 m2, 4 staff @ 1.25x min wage, 220 kg flour/day = 6,600 kg/mo, 12 prm firewood/mo + 1,800 kWh elec/mo)
    cur.execute("DROP TABLE IF EXISTS s_bakery_unit_model;")
    cur.execute("""
    CREATE TABLE s_bakery_unit_model (
        city_id TEXT PRIMARY KEY,
        monthly_flour_eur REAL,
        monthly_wood_eur REAL,
        monthly_elec_eur REAL,
        monthly_labor_eur REAL,
        monthly_rent_eur REAL,
        monthly_other_ops_eur REAL,
        monthly_total_cost_eur REAL,
        bread_net_price_eur REAL,
        breakeven_loaves_per_day INTEGER,
        cost_share_flour_pct REAL,
        cost_share_energy_wood_pct REAL,
        cost_share_labor_pct REAL,
        cost_share_rent_pct REAL,
        osm_bakeries_in_region INTEGER,
        spatial_footprint_summary TEXT
    );
    """)
    for row in S_INPUTS:
        cid = row[0]
        elec_s, flour_kg, wood_prm = row[2], row[4], row[5]
        min_gross, emp_mult, vat_b, rent_m2, retail_p = row[8], row[10], row[12], row[14], row[15]
        m_flour = round(6600.0 * flour_kg, 2)
        m_wood = round(12.0 * wood_prm, 2)
        m_elec = round(1800.0 * elec_s, 2)
        m_labor = round(4.0 * (min_gross * 1.20) * emp_mult, 2)
        m_rent = round(60.0 * rent_m2, 2)
        m_other = round((m_flour + m_wood + m_elec) * 0.18, 2) # yeast, salt, water, packaging, accounting
        m_tot = round(m_flour + m_wood + m_elec + m_labor + m_rent + m_other, 2)
        net_p = round(retail_p / (1.0 + vat_b / 100.0), 3)
        be_day = int(math.ceil((m_tot / net_p) / 30.0))
        b_cnt = cur.execute("SELECT COUNT(*) FROM osm_pois WHERE city_id=? AND fclass='bakery'", (cid,)).fetchone()[0]
        foot = f"S: 60 m² (radijus 600 m) | M: zakup {rent_m2} EUR/m² | L drvo: {wood_prm} EUR/prm | L/XL brašno: {flour_kg} EUR/kg | XL PDV hleb: {vat_b}%"
        cur.execute(
            "INSERT INTO s_bakery_unit_model VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid, m_flour, m_wood, m_elec, m_labor, m_rent, m_other, m_tot, net_p, be_day,
             round(100*m_flour/m_tot, 1), round(100*(m_wood+m_elec)/m_tot, 1),
             round(100*m_labor/m_tot, 1), round(100*m_rent/m_tot, 1), b_cnt, foot)
        )
    print("  Computed comparative S-scale Bakery Unit Economics model for all 5 cities")

    print("\n=== [7/9] LOADING XL-SCALE: EUROSTAT NUTS3 GDP, WORLD BANK EXTENDED, CORRIDORS & STRATEGIES ===")
    cur.execute("DROP TABLE IF EXISTS xl_regional_gdp_nuts3;")
    cur.execute("""
    CREATE TABLE xl_regional_gdp_nuts3 (
        nuts_code TEXT NOT NULL,
        region_name TEXT NOT NULL,
        city_hub TEXT NOT NULL,
        scale_role TEXT NOT NULL,
        year INTEGER NOT NULL,
        gdp_mio_eur REAL,
        gdp_eur_per_capita REAL,
        gdp_pps_per_capita REAL,
        source_ref TEXT,
        PRIMARY KEY (nuts_code, year)
    );
    """)
    NUTS_HUB = {
        "HR050": ("zagreb", "M_core"), "HR065": ("zagreb", "L_hinterland"), "HR064": ("zagreb", "L_outer_ring"),
        "HR027": ("zagreb", "L_outer_ring"), "HR028": ("zagreb", "L_outer_ring"),
        "RS110": ("beograd", "M_core"), "RS122": ("beograd", "L_hinterland"), "RS127": ("beograd", "L_hinterland"),
        "RS217": ("novi_pazar", "L_region_raska"), "RS211": ("novi_pazar", "L_hinterland_zlatibor"),
        "RS218": ("novi_pazar", "XL_corridor_sumadija"), "RS214": ("novi_pazar", "XL_corridor_moravica"),
    }
    gdp_pivot = defaultdict(lambda: {"name": "", "MIO_EUR": None, "EUR_HAB": None, "PPS_EU27_2020_HAB": None})
    for fn in ["eurostat_nama_10r_3gdp_full.json", "eurostat_nama_10r_3gdp_rs21.json"]:
        p = RAW / "wave2_xl" / fn
        if not p.exists(): continue
        for r in parse_eurostat_json(p):
            g = r.get("geo")
            if g not in NUTS_HUB: continue
            u = r.get("unit")
            if u in ("MIO_EUR", "EUR_HAB", "PPS_EU27_2020_HAB"):
                yr = int(r["time"])
                gdp_pivot[(g, yr)]["name"] = r.get("geo_label", g)
                gdp_pivot[(g, yr)][u] = float(r["value"])
    for (g, yr), vals in sorted(gdp_pivot.items()):
        hub, role = NUTS_HUB[g]
        cur.execute("INSERT OR REPLACE INTO xl_regional_gdp_nuts3 VALUES (?,?,?,?,?,?,?,?,?)",
                    (g, vals["name"], hub, role, yr, vals["MIO_EUR"], vals["EUR_HAB"], vals["PPS_EU27_2020_HAB"], "Eurostat nama_10r_3gdp"))
    print(f"  Loaded {len(gdp_pivot)} Eurostat NUTS3 GDP region-year rows")

    # World Bank Extended XL Indicators
    cur.execute("DROP TABLE IF EXISTS xl_macro_indicators;")
    cur.execute("""
    CREATE TABLE xl_macro_indicators (
        country_iso TEXT NOT NULL,
        indicator_key TEXT NOT NULL,
        indicator_name TEXT,
        year INTEGER NOT NULL,
        value REAL,
        source_ref TEXT,
        PRIMARY KEY (country_iso, indicator_key, year)
    );
    """)
    wb_ins = []
    for p in sorted((RAW / "wave2_xl").glob("wb_*.json")):
        key = p.stem.replace("wb_", "")
        arr = json.loads(p.read_text(encoding="utf-8"))
        if len(arr) >= 2 and isinstance(arr[1], list):
            for rec in arr[1]:
                if rec.get("value") is not None:
                    wb_ins.append((rec["countryiso3code"], key, rec.get("indicator",{}).get("value",""), int(rec["date"]), round(float(rec["value"]), 4), f"World Bank {p.name}"))
    cur.executemany("INSERT OR REPLACE INTO xl_macro_indicators VALUES (?,?,?,?,?,?)", wb_ins)
    print(f"  Loaded {len(wb_ins)} World Bank extended XL indicator rows (remittances, trade, FDI, forest, arable...)")

    # XL Corridors, International Projects, Airports & National Strategies
    cur.execute("DROP TABLE IF EXISTS xl_corridors_projects_strategies;")
    cur.execute("""
    CREATE TABLE xl_corridors_projects_strategies (
        item_id TEXT PRIMARY KEY,
        item_type TEXT NOT NULL,
        name TEXT NOT NULL,
        affected_cities TEXT NOT NULL,
        countries TEXT NOT NULL,
        investment_mio_eur REAL,
        horizon_years TEXT,
        financier_or_owner TEXT,
        economic_mechanism TEXT,
        source_ref TEXT
    );
    """)
    XL_ITEMS = [
        ("cor_tent_x_rail", "corridor_wbif", "TEN-T Koridor X (Železnica Beograd–Niš + krak ka Zagrebu)", "beograd,zagreb", "SRB,HRV", 2800.0, "2023-2030", "EU WBIF (600M grant) + EIB + EBRD", "Smanjuje troškove transporta i spaja BG i ZG u pan-evropsku kargo/putničku osu Centralna Evropa–Egej", "WBIF / EU za tebe / MGSI"),
        ("cor_tent_vc", "corridor_wbif", "TEN-T Mediteranski koridor Vc (Budimpešta–Osijek–Zenica–Visoko–Sarajevo–Ploče)", "sarajevo,travnik,zagreb", "BIH,HRV", 4500.0, "2015-2030", "WBIF + EIB + EBRD (>3 mlrd EUR) + Autoceste FBiH", "Glavna izvozno-uvozna arterija BiH: spaja Sarajevo, ZDK (Visoko/Zenica) i Lašvansku dolinu (preko čvora Lašva) sa EU i lukom Ploče", "WBIF / Autoceste FBiH"),
        ("cor_a2_pozega_boljare", "corridor_national", "Autoput A2 Požega–Duga Poljana–Boljare (Beograd–Južni Jadran)", "beograd,novi_pazar", "SRB,MNE", 1700.0, "2024-2032", "Budžet SRB + bilateralno/PPP + WBIF priprema", "Strukturni prelom za Novi Pazar i Pešter (petlja Duga Poljana): skraćuje vezu NP–Beograd na ~2,5h i spaja sa lukom Bar", "MGSI / PPRS 2021-2035"),
        ("cor_lasva_travnik_jajce", "corridor_fbih", "Brza cesta Lašva–Vitez–Nević Polje–Travnik–Jajce", "travnik,sarajevo", "BIH", 350.0, "2023-2029", "Budžet FBiH / Autoceste FBiH (Program javnih investicija)", "Integracija Lašvanske doline (Vitez–Novi Travnik–Travnik) u jednu 15-minutnu radnu zonu i brza veza sa Koridorom Vc i Sarajevom", "Autoceste FBiH / FMF FBiH"),
        ("cor_zg_rail_npoo", "corridor_eu_npoo", "Zagrebački željeznički čvor i Mediteranski/RH2 koridor (Rijeka–Zagreb–Botovo)", "zagreb", "HRV", 1800.0, "2021-2030", "EU CEF + NPOO + HŽ Infrastruktura", "Jača ulogu Zagreba kao intermodalnog logističkog čvora između luke Rijeka, Mađarske i Austrije", "NRS Hrvatska 2030 / HŽI"),
        ("air_beg_2025", "airport_hub_xl", "Aerodrom Beograd Nikola Tesla (BEG)", "beograd", "SRB", None, "2025", "VINCI Airports / Air Serbia", "8.911.987 putnika u 2025 (+6,5%), 116 destinacija — najveći regionalni avio-hab", "BEG / opensky.rs 2025"),
        ("air_zag_2025", "airport_hub_xl", "Aerodrom Zagreb Franjo Tuđman (ZAG)", "zagreb", "HRV", None, "2025", "MZLZ / Croatia Airlines / Ryanair", "4.721.563 putnika (+9,4%) i 12.408 t karga u 2025 — u Velikoj Gorici (L-prsten)", "zagreb-airport.hr 2025"),
        ("air_sjj_2025", "airport_hub_xl", "Međunarodni aerodrom Sarajevo (SJJ)", "sarajevo,travnik", "BIH", None, "2025", "J.P. MAS / subvencionisane linije KS", "2.226.692 putnika u 2025 (+22%, top-4 rast u Evropi) — motor turističkog buma Sarajeva (1,57M noćenja)", "sarajevo-airport.ba / ACI Europe 2025"),
        ("strat_pprs_2035", "strategy_national", "Prostorni plan Republike Srbije 2021–2035", "beograd,novi_pazar", "SRB", None, "2021-2035", "Republika Srbija / APPURS", "Definiše policentrični razvoj, metropolitensko područje Beograda i razvojnu osu Zapadne Srbije / Sandžaka", "appurs.gov.rs"),
        ("strat_nrs_hr_2030", "strategy_national", "Nacionalna razvojna strategija Republike Hrvatske do 2030. (NRS 2030)", "zagreb", "HRV", None, "2021-2030", "Vlada RH / EU kohezioni fondovi", "Zelena i digitalna tranzicija, uravnotežen regionalni razvoj, usmeravanje >25 mlrd EUR EU fondova", "nn.hr / razvoj.gov.hr"),
        ("strat_fbih_ks_2027", "strategy_regional", "Strategija razvoja FBiH & Kantona Sarajevo 2021–2027", "sarajevo,travnik", "BIH", None, "2021-2027", "Vlada FBiH / ZPR KS / SBK", "Jačanje konkurentnosti, turizam, zelena tranzicija, digitalizacija i ruralni razvoj (praćeno u ZPR KS 2025)", "zpr.ks.gov.ba / ippfbih.gov.ba"),
    ]
    cur.executemany("INSERT INTO xl_corridors_projects_strategies VALUES (?,?,?,?,?,?,?,?,?,?)", XL_ITEMS)
    print(f"  Loaded {len(XL_ITEMS)} XL strategic corridors, airports & development strategies")

    # Build XL Strategic Corridors & Hubs GeoJSON
    xl_feats = [
        {"type": "Feature", "properties": {"id": "cor_tent_x", "name": "TEN-T Koridor X (Zagreb–Beograd–Niš)", "scale": "XL", "investment_mio_eur": 2800},
         "geometry": {"type": "LineString", "coordinates": [[15.9772, 45.8130], [16.40, 45.65], [18.01, 45.16], [19.84, 44.99], [20.4612, 44.8125], [21.25, 44.01], [21.8958, 43.3209]]}},
        {"type": "Feature", "properties": {"id": "cor_tent_vc", "name": "TEN-T Koridor Vc (Osijek–Doboj–Zenica–Visoko–Sarajevo–Mostar–Ploče)", "scale": "XL", "investment_mio_eur": 4500},
         "geometry": {"type": "LineString", "coordinates": [[18.6939, 45.5550], [18.0870, 44.7318], [17.9077, 44.2034], [18.1781, 43.9890], [18.4131, 43.8563], [17.96, 43.65], [17.8078, 43.3438], [17.433, 43.041]]}},
        {"type": "Feature", "properties": {"id": "cor_a2_np", "name": "Autoput A2 Beograd–Požega–Duga Poljana (Novi Pazar)–Boljare", "scale": "XL", "investment_mio_eur": 1700},
         "geometry": {"type": "LineString", "coordinates": [[20.4612, 44.8125], [20.20, 44.45], [20.34, 43.89], [20.036, 43.846], [20.220, 43.266], [20.5122, 43.1367], [20.13, 43.05]]}},
        {"type": "Feature", "properties": {"id": "cor_lasva_tr", "name": "Brza cesta Lašva–Vitez–Travnik–Jajce", "scale": "L_XL", "investment_mio_eur": 350},
         "geometry": {"type": "LineString", "coordinates": [[17.95, 44.13], [17.790, 44.154], [17.6658, 44.2264], [17.40, 44.15], [17.270, 44.342]]}},
        {"type": "Feature", "properties": {"id": "air_beg", "name": "Aerodrom BEG (8,91M putnika 2025)", "scale": "XL", "passengers_2025": 8911987},
         "geometry": {"type": "Point", "coordinates": [20.3091, 44.8184]}},
        {"type": "Feature", "properties": {"id": "air_zag", "name": "Aerodrom ZAG (4,72M putnika 2025)", "scale": "XL", "passengers_2025": 4721563},
         "geometry": {"type": "Point", "coordinates": [16.0688, 45.7429]}},
        {"type": "Feature", "properties": {"id": "air_sjj", "name": "Aerodrom SJJ (2,23M putnika 2025)", "scale": "XL", "passengers_2025": 2226692},
         "geometry": {"type": "Point", "coordinates": [18.3315, 43.8246]}},
    ]
    xl_gj_path = BND / "xl_strategic_corridors.geojson"
    xl_gj_path.write_text(json.dumps({"type": "FeatureCollection", "features": xl_feats}, ensure_ascii=False), encoding="utf-8")
    print(f"  Wrote {xl_gj_path.name}: {len(xl_feats)} XL corridor & airport features")

    print("\n=== [8/9] CREATING MULTI-SCALE ANALYTICAL VIEWS (v2) ===")
    views_sql = [
        """DROP VIEW IF EXISTS v_osm_5cities_centrality;""",
        """CREATE VIEW v_osm_5cities_centrality AS
           SELECT city_id, ring,
                  COUNT(*) AS total_pois,
                  SUM(CASE WHEN fclass='bakery' THEN 1 ELSE 0 END) AS bakeries,
                  SUM(CASE WHEN fclass='marketplace' THEN 1 ELSE 0 END) AS markets,
                  SUM(CASE WHEN fclass='supermarket' THEN 1 ELSE 0 END) AS supermarkets,
                  SUM(CASE WHEN fclass='cafe' THEN 1 ELSE 0 END) AS cafes,
                  SUM(CASE WHEN fclass='bank' THEN 1 ELSE 0 END) AS banks,
                  SUM(CASE WHEN category='transport_hub' THEN 1 ELSE 0 END) AS transit_hubs
           FROM osm_pois
           GROUP BY city_id, ring
           ORDER BY city_id,
             CASE ring WHEN '0-1 km (CBD)' THEN 1 WHEN '1-3 km (Inner)' THEN 2 WHEN '3-6 km (Urban)' THEN 3 WHEN '6-15 km (Suburban)' THEN 4 ELSE 5 END;""",

        """DROP VIEW IF EXISTS v_s_bakery_5cities_comparison;""",
        """CREATE VIEW v_s_bakery_5cities_comparison AS
           SELECT b.city_id, c.name AS city_name, i.country_iso,
                  i.flour_t500_eur_kg, i.firewood_hardwood_eur_prm, i.elec_eur_kwh_small,
                  i.min_wage_gross_eur, i.commercial_rent_eur_m2_month, i.vat_bread_pct,
                  b.monthly_flour_eur, b.monthly_wood_eur, b.monthly_elec_eur,
                  b.monthly_labor_eur, b.monthly_rent_eur, b.monthly_total_cost_eur,
                  i.bread_500g_retail_eur, b.breakeven_loaves_per_day,
                  b.cost_share_flour_pct, b.cost_share_labor_pct, b.cost_share_rent_pct,
                  b.osm_bakeries_in_region
           FROM s_bakery_unit_model b
           JOIN s_scale_input_costs i ON b.city_id = i.city_id
           JOIN cities c ON b.city_id = c.city_id
           ORDER BY b.monthly_total_cost_eur DESC;""",

        """DROP VIEW IF EXISTS v_l_hinterland_summary;""",
        """CREATE VIEW v_l_hinterland_summary AS
           SELECT h.city_hub,
                  COUNT(*) AS ring_municipalities,
                  SUM(COALESCE(h.population, 0)) AS ring_pop_sum,
                  SUM(COALESCE(h.employees, 0)) AS ring_employees_known,
                  ROUND(AVG(h.dist_cbd_km), 1) AS avg_dist_km,
                  SUM(COALESCE(h.commuters_total, 0)) AS commuters_total_known,
                  SUM(COALESCE(h.commuters_external, 0)) AS commuters_external_known,
                  GROUP_CONCAT(h.unit_name, ', ') AS units_list
           FROM hinterland_units h
           GROUP BY h.city_hub;""",

        """DROP VIEW IF EXISTS v_xl_latest_nuts3_gdp;""",
        """CREATE VIEW v_xl_latest_nuts3_gdp AS
           SELECT g.nuts_code, g.region_name, g.city_hub, g.scale_role, g.year,
                  g.gdp_mio_eur, g.gdp_eur_per_capita, g.gdp_pps_per_capita
           FROM xl_regional_gdp_nuts3 g
           JOIN (SELECT nuts_code, MAX(year) AS max_y FROM xl_regional_gdp_nuts3 WHERE gdp_mio_eur IS NOT NULL GROUP BY nuts_code) m
             ON g.nuts_code = m.nuts_code AND g.year = m.max_y
           ORDER BY g.city_hub, g.gdp_eur_per_capita DESC;""",

        """DROP VIEW IF EXISTS v_xl_country_structural_profile;""",
        """CREATE VIEW v_xl_country_structural_profile AS
           SELECT m.country_iso, m.indicator_key, m.year, m.value
           FROM xl_macro_indicators m
           JOIN (SELECT country_iso, indicator_key, MAX(year) AS max_y FROM xl_macro_indicators GROUP BY country_iso, indicator_key) lm
             ON m.country_iso = lm.country_iso AND m.indicator_key = lm.indicator_key AND m.year = lm.max_y
           ORDER BY m.indicator_key, m.country_iso;""",
    ]
    for sql in views_sql:
        cur.execute(sql)

    # Refresh sources_manifest from manifest.jsonl
    cur.execute("DELETE FROM sources_manifest;")
    mf_path = BASE / "manifest.jsonl"
    if mf_path.exists():
        seen = set()
        mf_rows = []
        with open(mf_path, "r", encoding="utf-8") as f:
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
                    rec.get("source_name") or rec.get("desc") or "",
                    rec.get("url",""), int(rec.get("http_status") or rec.get("status") or 0),
                    1 if rec.get("ok") else 0, int(rec.get("bytes") or 0),
                    rec.get("sha256",""), rec.get("local_path") or rec.get("path") or "",
                    rec.get("error") or ""
                ))
        if mf_rows:
            cur.executemany(
                "INSERT INTO sources_manifest (checked_at, city, layer, source_name, url, http_status, ok, bytes, sha256, local_path, error) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                mf_rows
            )
        print(f"  Refreshed sources_manifest: {len(mf_rows)} unique audited records")

    conn.commit()

    print("\n=== [9/9] EXPORTING NEW WAVE-2 CSV TABLES ===")
    exports = [
        ("osm_5cities_centrality_v2.csv", "SELECT * FROM v_osm_5cities_centrality"),
        ("s_bakery_5cities_model.csv", "SELECT * FROM v_s_bakery_5cities_comparison"),
        ("l_hinterland_units_5cities.csv", "SELECT * FROM hinterland_units ORDER BY city_hub, dist_cbd_km"),
        ("l_commuting_and_flows.csv", "SELECT * FROM commuting_and_flows ORDER BY city_hub, commuters_total DESC"),
        ("l_hinterland_agri_forestry_trade.csv", "SELECT * FROM hinterland_agri_forestry_trade"),
        ("xl_nuts3_gdp_latest.csv", "SELECT * FROM v_xl_latest_nuts3_gdp"),
        ("xl_country_structural_profile.csv", "SELECT * FROM v_xl_country_structural_profile"),
        ("xl_corridors_projects_strategies.csv", "SELECT * FROM xl_corridors_projects_strategies"),
    ]
    for fn, q in exports:
        rows = cur.execute(q).fetchall()
        cols = [d[0] for d in cur.description]
        out_csv = TBL / fn
        with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)
        print(f"  Exported {fn:40s} | {len(rows):>4} rows")

    # Verification summary printout
    print("\n================ WAVE 2 DATABASE VERIFICATION ================")
    for tbl, typ in cur.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY type, name").fetchall():
        if typ == "table":
            cnt = cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            print(f"  TABLE {tbl:36s}: {cnt:>8,} rows")
        else:
            print(f"  VIEW  {tbl:36s}")

    print("\n--- S-SCALE BAKERY UNIT MODEL (5 CITIES) ---")
    for r in cur.execute("SELECT city_id, monthly_flour_eur, monthly_wood_eur, monthly_elec_eur, monthly_labor_eur, monthly_rent_eur, monthly_total_cost_eur, bread_500g_retail_eur, breakeven_loaves_per_day, osm_bakeries_in_region FROM v_s_bakery_5cities_comparison").fetchall():
        print(f"  {r[0]:11s} | flour={r[1]:>7.0f} | wood={r[2]:>5.0f} | elec={r[3]:>5.0f} | labor={r[4]:>6.0f} | rent={r[5]:>5.0f} | TOT={r[6]:>7.0f} EUR/m | retail={r[7]:.2f} | BE={r[8]:>3}/dan | OSM_bak={r[9]}")

    print("\n--- XL NUTS3 GDP LATEST ---")
    for r in cur.execute("SELECT * FROM v_xl_latest_nuts3_gdp").fetchall():
        print(f"  {r[0]:6s} {r[1]:30s} | hub={r[2]:10s} | {r[4]} | {r[5]:>9.1f} M EUR | {r[6]:>6.0f} EUR/st | {r[7]:>6.0f} PPS")

    print("\n--- L HINTERLAND SUMMARY ---")
    for r in cur.execute("SELECT city_hub, ring_municipalities, ring_pop_sum, avg_dist_km, commuters_total_known, commuters_external_known FROM v_l_hinterland_summary").fetchall():
        print(f"  {r[0]:11s} | munis={r[1]:>2} | pop={r[2]:>7,} | avg_km={r[3]:>4.1f} | comm_tot={r[4]:>6,} | comm_ext={r[5]:>6,}")

    conn.close()
    print(f"\nSQLite size: {DB_PATH.stat().st_size / (1024*1024):.2f} MB")
    print("DONE 11_build_urban_lab_db_v2.py")

if __name__ == "__main__":
    build_v2()
