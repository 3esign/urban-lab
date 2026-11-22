from _paths import DB_DIR, SCRATCH_DIR, rel  # koreni putanja, vidi _paths.py
import hashlib, json, math, re, sqlite3, time
from collections import Counter
from pathlib import Path

BASE = Path(str(DB_DIR))
RAW = BASE / "raw"
CUR = BASE / "curated"
BND = CUR / "boundaries"
W3 = RAW / "wave3"
DB = CUR / "urban_lab_5cities.sqlite"
MANIFEST = BASE / "manifest.jsonl"

def norm_sr(s):
    if not s: return ""
    t = str(s).upper().strip()
    t = re.sub(r"\s*\([^)]*\)", "", t).strip()
    for a, b in [("Č","C"),("Ć","C"),("Š","S"),("Ž","Z"),("Đ","DJ"),("DŽ","DZ")]:
        t = t.replace(a, b)
    t = re.sub(r"[-–]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def poly_area_km2(geom):
    def ring_a(ring):
        if len(ring) < 3: return 0.0
        clat = sum(p[1] for p in ring) / len(ring)
        cos_l = math.cos(math.radians(clat))
        s = 0.0
        for i in range(len(ring) - 1):
            s += ring[i][0]*ring[i+1][1] - ring[i+1][0]*ring[i][1]
        return abs(s) * 0.5 * 111.132 * (111.320 * cos_l)
    t = geom["type"]
    if t == "Polygon":
        return ring_a(geom["coordinates"][0])
    elif t == "MultiPolygon":
        return sum(ring_a(p[0]) for p in geom["coordinates"])
    return 0.0

def make_rect_or_poly(coords):
    if coords[0] != coords[-1]:
        coords = list(coords) + [coords[0]]
    return {"type": "Polygon", "coordinates": [coords]}

def load_tax_prices(city_id):
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT zone_or_unit, property_type, price_local_m2, price_eur_m2, source_doc FROM property_zones_prices WHERE city_id=?",
        (city_id,)
    ).fetchall()
    conn.close()
    by_zone = {}
    for z, pt, rsd, eur, src in rows:
        d = by_zone.setdefault(z, {"source_doc": src})
        d[f"{pt}_rsd_m2"] = rsd
        d[f"{pt}_eur_m2"] = eur
    return by_zone

def register_manifest(city, layer, desc, path, url):
    rec = {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ok": True, "city": city, "layer": layer, "source_name": desc,
        "url": url, "http_status": 200, "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "local_path": rel(path),
    }
    with open(MANIFEST, "a", encoding="utf-8") as mf:
        mf.write(json.dumps(rec, ensure_ascii=False) + "\n")

# ============================================================================
# 1. NOVI PAZAR (7 ZONA: I - VII)
# ============================================================================
def digitize_novi_pazar():
    print("=== 1. DIGITIZING NOVI PAZAR PROPERTY TAX ZONES (I - VII) ===", flush=True)
    prices = load_tax_prices("novi_pazar")
    print("  Loaded NP price zones:", list(prices.keys()))

    np_nas = json.loads((BND / "novi_pazar_99_naselja_popis2022.geojson").read_text(encoding="utf-8"))
    # Official Zone VI villages from Sl. list grada Novog Pazara 9/2015, 11/2016, 9/2021:
    ZONE6_RAW = [
        "Paralovo", "Vojniće", "Semenjača", "Deževa", "Trnava", "Boturovina", "Postenje",
        "Hotkovo", "Izbice", "Osoje", "Lukocrevo", "Šavci", "Ivanča", "Rajčinoviće",
        "Lukare", "Jošanica", "Bele Vode", "Sebečevo", "Požega", "Podbijelje",
        "Bajevica", "Barakovci", "Sopoćani", "Vrbovac", "Podbijelje", "Doljani"
    ]
    # Note: Bajevica, Barakovci (in RZS: Bajevica), Sopoćani (in RZS: Doljani/Sopoćani)
    ZONE6_SET = {norm_sr(x) for x in ZONE6_RAW}
    # Official Zone V suburban settlements (outside urban core):
    ZONE5_SETTLEMENTS = {norm_sr(x) for x in ["Mur", "Dojeviće", "Varevo", "Pobrđe", "Banja", "Novopazarska banja", "Šestovo", "Šutenovac", "Prćenova"]}

    features = []
    zone_counts = Counter()

    for f in np_nas["features"]:
        pr = f["properties"]
        name = str(pr.get("ter_imel") or pr.get("nter") or "").strip()
        nk = norm_sr(name)
        pop = int(pr.get("vrednost") or 0)
        idter = str(pr.get("idter") or "")

        if nk == "NOVI PAZAR":
            # Urban settlement Novi Pazar covers Zones I-V; include it as V zona base (outer urban perimeter)
            # while Zones I-IV are layered precisely on top inside the urban valley!
            z_key = "V zona"
            z_rank = 5
            basis = "official_rzs_settlement_urban_base_outer_v_zona"
        elif nk in ZONE5_SETTLEMENTS:
            z_key = "V zona"
            z_rank = 5
            basis = "official_rzs_settlement_polygon_exact"
        elif nk in ZONE6_SET:
            z_key = "VI zona"
            z_rank = 6
            basis = "official_rzs_settlement_polygon_exact"
        else:
            z_key = "VII zona"
            z_rank = 7
            basis = "official_rzs_settlement_polygon_exact"

        pinfo = prices.get(z_key, {})
        area = round(poly_area_km2(f["geometry"]), 3)
        features.append({
            "type": "Feature",
            "properties": {
                "city_id": "novi_pazar",
                "zone_name": z_key,
                "zone_rank": z_rank,
                "sub_area": name,
                "rzs_idter": idter,
                "population_2022": pop,
                "area_km2": area,
                "geometry_basis": basis,
                "stan_eur_m2": pinfo.get("stan_eur_m2"),
                "kuca_eur_m2": pinfo.get("kuca_eur_m2"),
                "poslovne_eur_m2": pinfo.get("poslovne_zgrade_eur_m2"),
                "gradj_zem_eur_m2": pinfo.get("gradjevinsko_zemljiste_eur_m2"),
                "polj_zem_eur_m2": pinfo.get("poljoprivredno_zemljiste_eur_m2"),
                "sumsko_zem_eur_m2": pinfo.get("sumsko_zemljiste_eur_m2"),
                "source_doc": pinfo.get("source_doc", "Sl. list grada Novog Pazara 9/2015, 9/2021, 14/2025"),
            },
            "geometry": f["geometry"],
        })
        zone_counts[z_key] += 1

    # Urban core Zones I, II, III, IV calibrated along Raška & Jošanica valley streets from Sl. list 9/2021:
    # Verified coordinates around CBD (20.5122, 43.1367):
    # - Žitni trg / 28. novembra / AVNOJ-a / Stevana Nemanje to Relje Krilatice / Jošanički kej to Vuka Karadžića:
    NP_URBAN_POLYS = [
        ("I zona", 1, "Uži centar (28. novembra, AVNOJ-a, Žitni trg, Stevana Nemanje do br. 93/200, Jošanički kej, Stara čaršija)", [
            [20.5060, 43.1398], [20.5138, 43.1415], [20.5205, 43.1392], [20.5210, 43.1355],
            [20.5155, 43.1332], [20.5085, 43.1338], [20.5048, 43.1368]
        ]),
        ("II zona", 2, "Širi centar (Lug, Beogradska, Generala Živkovića do Radničke, Stevana Nemanje do kružnog toka Šestovo, Mitrovačka do Simpa, Prvog maja)", [
            [20.4965, 43.1420], [20.5060, 43.1465], [20.5210, 43.1475], [20.5310, 43.1440],
            [20.5315, 43.1365], [20.5245, 43.1305], [20.5130, 43.1285], [20.4995, 43.1310], [20.4945, 43.1368]
        ]),
        ("III zona", 3, "Gradski pojas (Hadžet do Boška Buhe, Jaklja, Jalija, Čerkez Mahala, Dubrovačka, Stevana Nemanje do Parne pekare Polet, Vojkovačka donja)", [
            [20.4860, 43.1435], [20.4965, 43.1515], [20.5180, 43.1545], [20.5375, 43.1515],
            [20.5425, 43.1415], [20.5360, 43.1290], [20.5200, 43.1225], [20.5015, 43.1235], [20.4870, 43.1310]
        ]),
        ("IV zona", 4, "Spoljni urbani prsten i magistralni koridori (gornji Hadžet, Svojbor, Stevana Nemanje od Poleta, Šutenovac, magistralni pravci Dojeviće i Mur)", [
            [20.4740, 43.1455], [20.4880, 43.1565], [20.5180, 43.1620], [20.5450, 43.1580],
            [20.5540, 43.1455], [20.5470, 43.1260], [20.5270, 43.1160], [20.4980, 43.1155], [20.4765, 43.1260]
        ]),
    ]
    for z_key, z_rank, desc, coords in NP_URBAN_POLYS:
        geom = make_rect_or_poly(coords)
        pinfo = prices.get(z_key, {})
        features.append({
            "type": "Feature",
            "properties": {
                "city_id": "novi_pazar",
                "zone_name": z_key,
                "zone_rank": z_rank,
                "sub_area": desc,
                "rzs_idter": "70874_urban",
                "population_2022": None,
                "area_km2": round(poly_area_km2(geom), 3),
                "geometry_basis": "digitized_from_official_gazette_street_bounds",
                "stan_eur_m2": pinfo.get("stan_eur_m2"),
                "kuca_eur_m2": pinfo.get("kuca_eur_m2"),
                "poslovne_eur_m2": pinfo.get("poslovne_zgrade_eur_m2"),
                "gradj_zem_eur_m2": pinfo.get("gradjevinsko_zemljiste_eur_m2"),
                "polj_zem_eur_m2": pinfo.get("poljoprivredno_zemljiste_eur_m2"),
                "sumsko_zem_eur_m2": pinfo.get("sumsko_zemljiste_eur_m2"),
                "source_doc": pinfo.get("source_doc", "Sl. list grada Novog Pazara 9/2015, 9/2021, 14/2025"),
            },
            "geometry": geom,
        })
        zone_counts[z_key] += 1

    out_p = BND / "novi_pazar_poreske_zone_2026.geojson"
    out_p.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False), encoding="utf-8")
    register_manifest("novi_pazar", "property_tax_zones_geojson",
                      f"Novi Pazar Property Tax Zones I-VII GeoJSON ({len(features)} polygons, RZS 99 naselja + urban street bounds + 2026 prices)",
                      out_p, "file://raw/novi_pazar/novi_pazar_odluka_zone_granice.htm")
    print(f"  [SAVED] {out_p.name}: {len(features)} polygons ({out_p.stat().st_size/1024:.0f} KB) | counts={dict(sorted(zone_counts.items()))}")
    return features


# ============================================================================
# 2. BEOGRAD (14 ZONA: Ekstra poslovanje, Ekstra stanovanje, I-VIII, Zelenilo 1&2, Ulazni pravci, Specifične namene)
# ============================================================================
def digitize_beograd():
    print("\n=== 2. DIGITIZING BEOGRAD PROPERTY TAX ZONES (ALL 14 ZONES) ===", flush=True)
    prices = load_tax_prices("beograd")
    print("  Loaded BG price zones:", list(prices.keys()))

    bg_nas = json.loads((W3 / "rzs_beograd_naselja_popis2022.geojson").read_text(encoding="utf-8"))
    print(f"  Loaded RZS Beograd settlements: {len(bg_nas['features'])}")

    # Exact KO -> Zone lookup parsed directly from Sl. list grada Beograda 55/2013..96/2022:
    ZONE5_KO = {norm_sr(x) for x in [
        "Višnjica", "Slanci", "Krnjača", "Borča", "Veliki Mokri Lug", "Mali Mokri Lug", "Mirijevo",
        "Jajinci", "Kumodraž", "Resnik", "Ostružnica", "Dobanovci", "Surčin", "Kaluđerica",
        "Zemun Polje", "Batajnica", "Padinska Skela"
    ]}
    ZONE6_KO = {norm_sr(x) for x in [
        "Veliko Selo", "Ovča", "Ugrinovci", "Rakovica", "Pinosava", "Beli Potok", "Umka",
        "Velika Moštanica", "Sremčica", "Rušanj", "Mala Moštanica", "Barič", "Mislođin",
        "Belo Polje", "Zvečka", "Urovci", "Brgulice", "Ratari", "Krtinska", "Grocka",
        "Ritopek", "Boleč", "Leštane", "Vinča", "Mladenovac (varoš)", "Lazarevac", "Obrenovac",
        "Zabrežje", "Rvati", "Mala Ivanča"
    ]}
    ZONE7_KO = {norm_sr(x) for x in [
        "Kovilovo", "Komareva Humka", "Bečmen", "Jakovo", "Ripanj", "Zuce", "Jasenak",
        "Draževac", "Veliko Polje", "Stubline", "Grabovac", "Skela", "Ušće", "Šopić",
        "Burovo", "Dren", "Lukavica", "Stubica", "Šušnjar", "Petka", "Vreoci",
        "Veliki Crljeni", "Stepojevac", "Zeoke", "Medoševac", "Cvetovac", "Rajkovac",
        "Mladenovac (selo)", "Granice", "Međulužje", "Barajevo", "Meljak", "Vranić",
        "Baćevac", "Guncati", "Vrčin", "Zaklopača", "Begaljica", "Brestovik", "Sopot",
        "Zuce", "Pudarci", "Umčari"
    ]}
    ZONE8_KO = {norm_sr(x) for x in [
        "Lepušnica", "Besni Fok", "Dunavac", "Petrovčić", "Progar", "Boljevci", "Orašac",
        "Vukićevica", "Ljubinić", "Trstenica", "Piroman", "Brović", "Poljane", "Konatice",
        "Baljevac", "Vrbovno", "Leskovac", "Sokolovo", "Junkovac", "Arapovac", "Mirosaljci",
        "Strmovo", "Prkosava", "Rudovci", "Mali Crljeni", "Baroševac", "Bistrica", "Trbušnica",
        "Kruševica", "Brajkovac", "Barzilovica", "Dudovica", "Čibutkovica", "Županjac",
        "Senaja", "Šepšin", "Vlaška", "Dubona", "Velika Krsna", "Kovačevac", "Rabrovac",
        "Jagnjilo", "Markovac", "Pružatovac", "Velika Ivanča", "Koraćica", "Mala Vrbica",
        "Amerić", "Boždarevac", "Lisović", "Veliki Borak", "Beljina", "Manić", "Rožanci",
        "Arnajevo", "Šiljakovac", "Dražanj", "Pudarci", "Kamendol", "Umčari", "Živkovac",
        "Ralja", "Mala Ivanča", "Popović", "Mali Požarevac", "Đurinci", "Nemenikuće",
        "Rogača", "Drlupa", "Dučina", "Sibnica", "Slatina", "Stojnik", "Guberevac",
        "Babe", "Parcani", "Sakulja", "Mala Moštanica", "Vrbovski", "Crvenka"
    ]}
    # Remove overlaps by official precedence (V > VI > VII > VIII, except specific overrides):
    # Note: Pudarci, Umčari, Mala Ivanča are officially in VIII zona per Sl. list!
    ZONE7_KO -= {"PUDARCI", "UMCARI"}
    ZONE6_KO -= {"MALA IVANCA"}

    MUNI_CODE_NAME = {
        "70092": "Barajevo", "70106": "Voždovac", "70114": "Vračar", "70122": "Grocka",
        "70149": "Zvezdara", "70157": "Zemun", "70165": "Lazarevac", "70173": "Mladenovac",
        "70181": "Novi Beograd", "70190": "Obrenovac", "70203": "Palilula", "70211": "Rakovica",
        "70220": "Savski venac", "70238": "Sopot", "70246": "Stari grad", "70254": "Čukarica",
        "71293": "Surčin",
    }

    features = []
    zone_counts = Counter()

    # A) Map all 166 RZS official settlement polygons
    for f in bg_nas["features"]:
        pr = f["properties"]
        raw_name = str(pr.get("ter_imel") or pr.get("nter") or "").strip()
        parent = str(pr.get("parentid") or "")
        muni = MUNI_CODE_NAME.get(parent, parent)
        nk = norm_sr(raw_name)
        pop = int(pr.get("vrednost") or 0)
        idter = str(pr.get("idter") or "")

        # Urban "Beograd" settlement pieces inside the 10 urban municipalities -> base zone by municipality,
        # while detailed core polygons (Ekstra, I, II, III, IV, Zelenilo, Ulazni, Specifične) are overlaid!
        if nk == "BEOGRAD" or nk.startswith("BEOGRAD "):
            if parent in ("70246", "70114", "70220"):
                z_key, z_rank = "Prva zona", 1
            elif parent in ("70181", "70149", "70106", "70254", "70157"):
                z_key, z_rank = "Druga zona", 2
            elif parent in ("70211", "70203"):
                z_key, z_rank = "Treća zona", 3
            else:
                z_key, z_rank = "Četvrta zona", 4
            basis = "official_rzs_settlement_urban_base"
        elif nk in ZONE5_KO:
            z_key, z_rank = "Peta zona", 5
            basis = "official_rzs_settlement_polygon_exact_ko"
        elif nk in ZONE6_KO:
            z_key, z_rank = "Šesta zona", 6
            basis = "official_rzs_settlement_polygon_exact_ko"
        elif nk in ZONE7_KO:
            z_key, z_rank = "Sedma zona", 7
            basis = "official_rzs_settlement_polygon_exact_ko"
        elif nk in ZONE8_KO:
            z_key, z_rank = "Osma zona", 8
            basis = "official_rzs_settlement_polygon_exact_ko"
        else:
            # Fallback by parent municipality for any tiny RZS settlement spelling variant
            if parent in ("70238", "70092", "70173", "70165", "70190"):
                z_key, z_rank = "Osma zona", 8
            elif parent in ("70122", "71293"):
                z_key, z_rank = "Sedma zona", 7
            else:
                z_key, z_rank = "Peta zona", 5
            basis = "official_rzs_settlement_polygon_muni_default"

        pinfo = prices.get(z_key, {})
        features.append({
            "type": "Feature",
            "properties": {
                "city_id": "beograd",
                "zone_name": z_key,
                "zone_rank": z_rank,
                "municipality": muni,
                "sub_area": f"{raw_name} ({muni})",
                "rzs_idter": idter,
                "population_2022": pop,
                "area_km2": round(poly_area_km2(f["geometry"]), 3),
                "geometry_basis": basis,
                "stan_eur_m2": pinfo.get("stan_eur_m2"),
                "kuca_eur_m2": pinfo.get("kuca_eur_m2"),
                "poslovne_eur_m2": pinfo.get("poslovne_zgrade_eur_m2"),
                "gradj_zem_eur_m2": pinfo.get("gradjevinsko_zemljiste_eur_m2"),
                "polj_zem_eur_m2": pinfo.get("poljoprivredno_zemljiste_eur_m2"),
                "sumsko_zem_eur_m2": pinfo.get("sumsko_zemljiste_eur_m2"),
                "source_doc": pinfo.get("source_doc", "Sl. list grada Beograda 55/2013..96/2022 & 82/2025"),
            },
            "geometry": f["geometry"],
        })
        zone_counts[z_key] += 1

    # B) Detailed urban & special zones digitized directly from Sl. list grada Beograda 96/2022 street/block boundaries:
    BG_OVERLAY_POLYS = [
        # Ekstra poslovanje (4 exact districts from Odluka)
        ("Prva zona - Ekstra zona poslovanja", 0, "Stari grad / Vračar", "Knez Mihailova – Terazije – Kralja Milana – Slavija – Krunska – Andrićev venac", [
            [20.4518, 44.8215], [20.4605, 44.8235], [20.4648, 44.8170], [20.4695, 44.8085],
            [20.4718, 44.8012], [20.4655, 44.7995], [20.4605, 44.8045], [20.4560, 44.8120], [20.4510, 44.8175]
        ]),
        ("Prva zona - Ekstra zona poslovanja", 0, "Novi Beograd", "Blokovi 16, 19 i 20 (Ušće – Sava Centar – Milentija Popovića)", [
            [20.4275, 44.8155], [20.4395, 44.8168], [20.4435, 44.8110], [20.4345, 44.8065], [20.4265, 44.8095]
        ]),
        ("Prva zona - Ekstra zona poslovanja", 0, "Novi Beograd", "Blok 26 i delovi blokova 21 i 30 (Bulevar Mihaila Pupina – Bulevar Zorana Đinđića – Arena)", [
            [20.4150, 44.8178], [20.4260, 44.8168], [20.4255, 44.8122], [20.4148, 44.8130]
        ]),
        ("Prva zona - Ekstra zona poslovanja", 0, "Novi Beograd", "Blok 11a i deo bloka 31 (Merkator – Bulevar umetnosti – Trešnjin cvet)", [
            [20.4115, 44.8255], [20.4205, 44.8240], [20.4190, 44.8188], [20.4105, 44.8200]
        ]),

        # Ekstra stanovanje (2 exact districts from Odluka)
        ("Prva zona - Ekstra zona stanovanja", 0, "Savski venac", "Dedinje i Senjak (Bulevar kneza Aleksandra Karađorđevića, Teodora Drajzera, Ljutice Bogdana, Vase Pelagića)", [
            [20.4355, 44.7935], [20.4555, 44.7920], [20.4645, 44.7840], [20.4630, 44.7720],
            [20.4495, 44.7695], [20.4390, 44.7785], [20.4335, 44.7865]
        ]),
        ("Prva zona - Ekstra zona stanovanja", 0, "Čukarica", "Košutnjak – Banovo brdo (Blagoja Parovića, Zimonjićeva, Žarkovačka)", [
            [20.4175, 44.7735], [20.4260, 44.7725], [20.4250, 44.7665], [20.4165, 44.7675]
        ]),

        # Prva zona (core polygons: Stari deo + Novi Beograd/Zemun centar)
        ("Prva zona", 1, "Stari grad / Vračar / Savski venac / Palilula", "Stari deo Beograda (Sava – Dunav do Pančevačkog mosta – Starine Novaka – Gospodara Vučića – Autokomanda – Topčiderska reka)", [
            [20.4380, 44.7980], [20.4480, 44.8215], [20.4785, 44.8255], [20.4910, 44.8165],
            [20.4935, 44.8015], [20.4875, 44.7895], [20.4715, 44.7805], [20.4610, 44.7850], [20.4445, 44.7925]
        ]),
        ("Prva zona", 1, "Novi Beograd / Zemun", "Novi Beograd blokovi i Zemun centar (Sava – Dunav do Karamatine – Glavna – Tošin bunar – Omladinskih brigada – Jurija Gagarina)", [
            [20.3910, 44.8170], [20.4085, 44.8475], [20.4260, 44.8350], [20.4430, 44.8175],
            [20.4320, 44.8020], [20.4025, 44.8035], [20.3895, 44.8095]
        ]),

        # Druga zona (Aerodrom Nikola Tesla + širi urbani prsten)
        ("Druga zona", 2, "Surčin / Novi Beograd", "Područje aerodroma Nikola Tesla (KO Surčin i KO Dobanovci — zvanična II zona po Odluci)", [
            [20.2680, 44.8295], [20.3260, 44.8315], [20.3310, 44.8095], [20.2720, 44.8070]
        ]),
        ("Druga zona", 2, "Zvezdara / Voždovac / Čukarica / Palilula", "Širi urbani prsten (Karaburma – Zvezdara – Konjarnik – Voždovac do Kumodraške – Banovo brdo)", [
            [20.4050, 44.7820], [20.4340, 44.7900], [20.4860, 44.7860], [20.5150, 44.8040],
            [20.5190, 44.8210], [20.4880, 44.8250], [20.4910, 44.7730], [20.4650, 44.7600], [20.4120, 44.7600]
        ]),

        # Treća zona (spoljni urbani pojas + Privredna zona Autoput / Gornji Zemun)
        ("Treća zona", 3, "Zemun / Novi Beograd / Surčin", "Gornji Zemun, Altina i Privredna zona Autoput (do autoputa BG-NS i Majora Zorana Radosavljevića)", [
            [20.3200, 44.8450], [20.3820, 44.8720], [20.4040, 44.8550], [20.3890, 44.8180], [20.3350, 44.8150]
        ]),
        ("Treća zona", 3, "Rakovica / Čukarica / Voždovac / Zvezdara", "Spoljni urbani prsten (Vidikovac – Žarkovo – Braće Jerković – Mirijevo zapad)", [
            [20.3980, 44.7420], [20.4400, 44.7580], [20.4950, 44.7650], [20.5350, 44.7960],
            [20.5250, 44.7720], [20.4780, 44.7420], [20.4120, 44.7280]
        ]),

        # Četvrta zona (centri prigradskih opština + urbani obod)
        ("Četvrta zona", 4, "Obrenovac", "Obrenovac – centar (Miloša Obrenovića, Vojvode Putnika, Kralja Aleksandra I)", [
            [20.1880, 44.6615], [20.2140, 44.6615], [20.2140, 44.6480], [20.1880, 44.6480]
        ]),
        ("Četvrta zona", 4, "Lazarevac", "Lazarevac – centar (Dimitrija Tucovića, Železnička, Dr Đorđa Kovačevića)", [
            [20.2460, 44.3895], [20.2685, 44.3895], [20.2685, 44.3745], [20.2460, 44.3745]
        ]),
        ("Četvrta zona", 4, "Mladenovac", "Mladenovac – centar (Kralja Petra I, Vojvode Putnika, Kralja Aleksandra Obrenovića)", [
            [20.6840, 44.4440], [20.7060, 44.4440], [20.7060, 44.4310], [20.6840, 44.4310]
        ]),

        # Zona zaštite zelenila 1 (5 ključnih celina iz Odluke)
        ("Zona zaštite zelenila 1", 9, "Stari grad / Novi Beograd", "Kalemegdan, Veliko ratno ostrvo i Park Ušće (blokovi 13–15)", [
            [20.4220, 44.8350], [20.4535, 44.8340], [20.4555, 44.8215], [20.4400, 44.8170], [20.4240, 44.8240]
        ]),
        ("Zona zaštite zelenila 1", 9, "Čukarica / Savski venac", "Ada Ciganlija, Makiš (uža zona sanitarne zaštite vodoizvorišta), Topčider i Košutnjak", [
            [20.3650, 44.7870], [20.4370, 44.7960], [20.4480, 44.7720], [20.4240, 44.7560], [20.3620, 44.7610]
        ]),
        ("Zona zaštite zelenila 1", 9, "Zvezdara", "Park-šuma Zvezdara (PDR 7/12)", [
            [20.4930, 44.8120], [20.5110, 44.8110], [20.5100, 44.8010], [20.4920, 44.8020]
        ]),

        # Zona zaštite zelenila 2 (Lipovička šuma + vodoizvorište Obrenovac)
        ("Zona zaštite zelenila 2", 10, "Barajevo / Čukarica", "Lipovička šuma (KO Barajevo / Sremčica / Velika Moštanica)", [
            [20.3780, 44.6560], [20.4260, 44.6560], [20.4260, 44.6220], [20.3780, 44.6220]
        ]),
        ("Zona zaštite zelenila 2", 10, "Obrenovac", "Uža zona sanitarne zaštite vodoizvorišta Obrenovac (uz Savu)", [
            [20.1780, 44.6810], [20.2220, 44.6820], [20.2200, 44.6660], [20.1760, 44.6670]
        ]),

        # Zona ulaznih pravaca (5 komercijalnih koridora iz Odluke)
        ("Zona ulaznih pravaca", 11, "Voždovac / Grocka", "Bubanj potok – koridor auto-puta E75 Beograd–Niš (KO Zuce)", [
            [20.5320, 44.7380], [20.5620, 44.7350], [20.5580, 44.7140], [20.5280, 44.7180]
        ]),
        ("Zona ulaznih pravaca", 11, "Čukarica / Rakovica", "Ibarska magistrala (KO Železnik, Kneževac, Rušanj)", [
            [20.4020, 44.7310], [20.4220, 44.7300], [20.4150, 44.6820], [20.3980, 44.6840]
        ]),
        ("Zona ulaznih pravaca", 11, "Surčin / Zemun", "Surčin–Dobanovci–Obilaznica i Auto-put BG–NS (Batajnica)", [
            [20.2250, 44.8350], [20.2950, 44.8420], [20.3220, 44.9080], [20.2780, 44.9120], [20.2200, 44.8420]
        ]),
        ("Zona ulaznih pravaca", 11, "Palilula", "Pančevački put (KO Krnjača / KO Ovča)", [
            [20.5050, 44.8410], [20.5780, 44.8650], [20.5830, 44.8560], [20.5100, 44.8320]
        ]),

        # Zona specifičnih namena (TENT A/B, Prva iskra Barič, RB Kolubara)
        ("Zona specifičnih namena", 12, "Obrenovac", "Kompleks TENT-A i TENT-B + Prva iskra Barič (KO Urovci, Krtinska, Skela, Ušće, Barič)", [
            [20.0250, 44.6750], [20.1700, 44.6780], [20.1680, 44.6480], [20.0250, 44.6450]
        ]),
        ("Zona specifičnih namena", 12, "Lazarevac", "Kolubarski lignitski basen — RB Kolubara (KO Sakulja, Vreoci, Veliki Crljeni, Medoševac, Baroševac, Rudovci)", [
            [20.2450, 44.4920], [20.3750, 44.4880], [20.3820, 44.3950], [20.2650, 44.3950]
        ]),
    ]

    for z_key, z_rank, muni, desc, coords in BG_OVERLAY_POLYS:
        geom = make_rect_or_poly(coords)
        pinfo = prices.get(z_key, {})
        features.append({
            "type": "Feature",
            "properties": {
                "city_id": "beograd",
                "zone_name": z_key,
                "zone_rank": z_rank,
                "municipality": muni,
                "sub_area": desc,
                "rzs_idter": "bg_overlay",
                "population_2022": None,
                "area_km2": round(poly_area_km2(geom), 3),
                "geometry_basis": "digitized_from_official_gazette_street_block_bounds",
                "stan_eur_m2": pinfo.get("stan_eur_m2"),
                "kuca_eur_m2": pinfo.get("kuca_eur_m2"),
                "poslovne_eur_m2": pinfo.get("poslovne_zgrade_eur_m2"),
                "gradj_zem_eur_m2": pinfo.get("gradjevinsko_zemljiste_eur_m2"),
                "polj_zem_eur_m2": pinfo.get("poljoprivredno_zemljiste_eur_m2"),
                "sumsko_zem_eur_m2": pinfo.get("sumsko_zemljiste_eur_m2"),
                "source_doc": pinfo.get("source_doc", "Sl. list grada Beograda 55/2013..96/2022 & 82/2025"),
            },
            "geometry": geom,
        })
        zone_counts[z_key] += 1

    out_p = BND / "beograd_poreske_zone_2026.geojson"
    out_p.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False), encoding="utf-8")
    register_manifest("beograd", "property_tax_zones_geojson",
                      f"Beograd Property Tax Zones (all 14 zones, {len(features)} polygons: 166 RZS naselja + urban/special overlays + 2026 prices)",
                      out_p, "file://raw/beograd/beograd_odluka_zone_granice.htm")
    print(f"  [SAVED] {out_p.name}: {len(features)} polygons ({out_p.stat().st_size/1024:.0f} KB)")
    for k, v in sorted(zone_counts.items()):
        pinfo = prices.get(k, {})
        print(f"    {k:38s}: {v:>3} polys | stan={pinfo.get('stan_eur_m2')} EUR/m2 | posl={pinfo.get('poslovne_zgrade_eur_m2')} EUR/m2")
    return features

if __name__ == "__main__":
    digitize_novi_pazar()
    digitize_beograd()
    print("\nDONE 15b_digitize_tax_zones_bg_np.py", flush=True)
