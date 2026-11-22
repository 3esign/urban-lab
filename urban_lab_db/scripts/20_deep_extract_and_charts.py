from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import sqlite3
import json
import math
import csv
from pathlib import Path
from collections import defaultdict

BASE = Path(str(DB_DIR))
DB = BASE / "curated" / "urban_lab_5cities.sqlite"
BOUND = BASE / "curated" / "boundaries"
OUT = BASE / "curated" / "analysis"
CHARTS = OUT / "charts"
OUT.mkdir(parents=True, exist_ok=True)
CHARTS.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

def q(sql, params=()):
    return [dict(r) for r in cur.execute(sql, params).fetchall()]

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def geom_radial_stats(geom, lat0, lon0):
    pts = []
    gtype = geom.get("type")
    coords = geom.get("coordinates", [])
    if gtype == "Polygon":
        if coords:
            pts.extend(coords[0])
    elif gtype == "MultiPolygon":
        for poly in coords:
            if poly and poly[0]:
                pts.extend(poly[0])
    if not pts:
        return None
    dists = [haversine_km(lat0, lon0, p[1], p[0]) for p in pts]
    clat = sum(p[1] for p in pts) / len(pts)
    clon = sum(p[0] for p in pts) / len(pts)
    cdist = haversine_km(lat0, lon0, clat, clon)
    dists_sorted = sorted(dists)
    n = len(dists_sorted)
    return {
        "centroid_dist": cdist,
        "mean_vertex_dist": sum(dists) / n,
        "min_dist": dists_sorted[0],
        "max_dist": dists_sorted[-1],
    }

def ols_log_linear(xs, ys):
    pairs = [(x, math.log(y)) for x, y in zip(xs, ys) if x is not None and y is not None and y > 0]
    n = len(pairs)
    if n < 3:
        return None
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    sxx = sum((p[0]-mx)**2 for p in pairs)
    sxy = sum((p[0]-mx)*(p[1]-my) for p in pairs)
    syy = sum((p[1]-my)**2 for p in pairs)
    if sxx == 0:
        return None
    b = sxy / sxx
    a = my - b * mx
    r2 = (sxy**2) / (sxx * syy) if syy > 0 else 0.0
    half_dist = math.log(2) / (-b) if b < 0 else None
    pct_per_km = (math.exp(b) - 1.0) * 100.0
    return {
        "n": n,
        "intercept_eur": round(math.exp(a), 2),
        "slope_b": round(b, 5),
        "decay_beta": round(-b, 5),
        "pct_change_per_km": round(pct_per_km, 2),
        "half_price_dist_km": round(half_dist, 2) if half_dist else None,
        "r2": round(r2, 4),
    }

cities = q("SELECT * FROM cities ORDER BY population DESC")
city_cbd = {c["city_id"]: (c["cbd_lat"], c["cbd_lon"]) for c in cities}

# Inspect exact macro_groups in osm_landuse_summary
macro_groups = [r["macro_group"] for r in q("SELECT DISTINCT macro_group FROM osm_landuse_summary ORDER BY macro_group")]
print("EXACT MACRO_GROUPS:", macro_groups)

# 1. Refined Tax Zone Distances (BG & NP)
def compute_zone_radial(geojson_path, city_id):
    lat0, lon0 = city_cbd[city_id]
    with open(geojson_path, "r", encoding="utf-8") as f:
        gj = json.load(f)
    by_zone = defaultdict(list)
    for feat in gj.get("features", []):
        props = feat.get("properties", {})
        zname = props.get("zone_name") or props.get("zona") or props.get("name")
        area = float(props.get("area_km2") or 1.0)
        st = geom_radial_stats(feat.get("geometry", {}), lat0, lon0)
        if st and zname:
            by_zone[zname].append((st, area))
    out = {}
    for zname, vals in by_zone.items():
        tot_a = sum(a for _, a in vals)
        w_cent = sum(s["centroid_dist"] * a for s, a in vals) / tot_a
        w_vert = sum(s["mean_vertex_dist"] * a for s, a in vals) / tot_a
        if len(vals) <= 3 and w_cent < 0.55 * w_vert:
            eff_d = w_vert * 0.75
            d_method = "ring_mid_radius"
        else:
            eff_d = w_cent
            d_method = "weighted_centroid"
        out[zname] = {
            "eff_dist_km": round(eff_d, 2),
            "centroid_dist_km": round(w_cent, 2),
            "mean_vertex_dist_km": round(w_vert, 2),
            "min_dist_km": round(min(s["min_dist"] for s, _ in vals), 2),
            "max_dist_km": round(max(s["max_dist"] for s, _ in vals), 2),
            "poly_count": len(vals),
            "dist_method": d_method
        }
    return out

bg_rad = compute_zone_radial(BOUND / "beograd_poreske_zone_2026.geojson", "beograd")
np_rad = compute_zone_radial(BOUND / "novi_pazar_poreske_zone_2026.geojson", "novi_pazar")

tax_rows = q("SELECT * FROM property_tax_zones_gis_summary ORDER BY city_id, zone_rank")
enriched_zones = []
for row in tax_rows:
    r = dict(row)
    rad = (bg_rad if r["city_id"] == "beograd" else np_rad).get(r["zone_name"], {})
    r.update(rad)
    r["ratio_poslovno_stan"] = round(r["poslovne_eur_m2"] / r["stan_eur_m2"], 3) if r["stan_eur_m2"] and r["poslovne_eur_m2"] else None
    r["ratio_gradj_polj"] = round(r["gradj_zem_eur_m2"] / r["polj_zem_eur_m2"], 2) if r["gradj_zem_eur_m2"] and r["polj_zem_eur_m2"] else None
    r["land_share_apt_pct"] = round(r["gradj_zem_eur_m2"] / r["stan_eur_m2"] * 100, 1) if r["gradj_zem_eur_m2"] and r["stan_eur_m2"] else None
    enriched_zones.append(r)

with open(OUT / "bid_rent_tax_zones_bg_np_2026.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(enriched_zones[0].keys()))
    w.writeheader()
    w.writerows(enriched_zones)

# Bid-Rent Regressions: include BG monocentric (excluding special zones AND excluding Zone IV satellite centers!)
bid_regs = {}
for cid in ["beograd", "novi_pazar"]:
    all_z = [z for z in enriched_zones if z["city_id"] == cid and z.get("eff_dist_km") is not None]
    conc_z = [z for z in all_z if not any(k in z["zone_name"].lower() for k in ["zelenil", "ulazni", "specifi"])]
    subsets = [("all_zones", all_z), ("concentric_with_z4", conc_z)]
    if cid == "beograd":
        mono_z = [z for z in conc_z if "četvrta" not in z["zone_name"].lower()]
        subsets.append(("monocentric_excl_z4_satellites", mono_z))
    for tag, sub in subsets:
        bid_regs[f"{cid}_{tag}"] = {
            "stan": ols_log_linear([z["eff_dist_km"] for z in sub], [z["stan_eur_m2"] for z in sub]),
            "kuca": ols_log_linear([z["eff_dist_km"] for z in sub], [z["kuca_eur_m2"] for z in sub]),
            "poslovne": ols_log_linear([z["eff_dist_km"] for z in sub], [z["poslovne_eur_m2"] for z in sub]),
            "gradj_zem": ols_log_linear([z["eff_dist_km"] for z in sub], [z["gradj_zem_eur_m2"] for z in sub]),
            "polj_zem": ols_log_linear([z["eff_dist_km"] for z in sub], [z["polj_zem_eur_m2"] for z in sub]),
        }

sa_units = q("SELECT unit_name, dist_cbd_km, avg_apt_price_eur_m2, avg_net_wage_eur, population, density_per_km2 FROM admin_units WHERE city_id='sarajevo' AND avg_apt_price_eur_m2 IS NOT NULL ORDER BY dist_cbd_km")
sa_core = [u for u in sa_units if "Trnovo" not in u["unit_name"] and "Bjela" not in u["unit_name"]]
bid_regs["sarajevo_all"] = {"stan": ols_log_linear([u["dist_cbd_km"] for u in sa_units], [u["avg_apt_price_eur_m2"] for u in sa_units])}
bid_regs["sarajevo_urban_core"] = {"stan": ols_log_linear([u["dist_cbd_km"] for u in sa_core], [u["avg_apt_price_eur_m2"] for u in sa_core])}

print("\n=== BID-RENT REGRESSIONS (INCL. BG MONOCENTRIC EXCL. Z4 SATELLITES) ===")
for k, v in bid_regs.items():
    print(f"[{k}]")
    for ptype, reg in v.items():
        if reg:
            print(f"  {ptype:10s}: P0={reg['intercept_eur']:7.1f} EUR, beta={reg['decay_beta']:.4f} ({reg['pct_change_per_km']:+.2f}%/km), D_half={str(reg['half_price_dist_km']):>5s} km, R2={reg['r2']:.4f} (n={reg['n']})")

# 2. Landuse Ring Matrix using EXACT macro_groups
RING_ORDER = ['0-1 km (CBD)', '1-3 km (Inner)', '3-6 km (Urban)', '6-15 km (Suburban)', '15+ km (Hinterland)']
lu_raw = q("""
    SELECT city_id, ring, macro_group, SUM(polygon_count) AS polygons, SUM(area_km2) AS area_km2
    FROM osm_landuse_summary
    GROUP BY city_id, ring, macro_group
""")
lu_matrix = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
for r in lu_raw:
    lu_matrix[r["city_id"]][r["ring"]][r["macro_group"]] += r["area_km2"]

# Map any quarry/mining/extraction macro_group dynamically
quarry_keys = [g for g in macro_groups if "quarry" in g or "mine" in g or "extract" in g]
green_keys = [g for g in macro_groups if "green" in g or "park" in g or "recreat" in g or "nature" in g]
print("QUARRY KEYS:", quarry_keys, "GREEN KEYS:", green_keys)

lu_rows_csv = []
print("\n=== LANDUSE RING SHARES (%) BY CITY (EXACT QUARRY/MINING) ===")
for cid in ["beograd", "zagreb", "sarajevo", "novi_pazar", "travnik"]:
    for ring in RING_ORDER:
        m = lu_matrix[cid][ring]
        tot = sum(m.values())
        if tot == 0:
            continue
        res = m.get("residential", 0)
        com = m.get("commercial_retail", 0)
        ind = m.get("industrial", 0)
        agr = m.get("agriculture", 0)
        frs = m.get("forest", 0)
        qry = sum(m.get(k, 0) for k in quarry_keys)
        grn = sum(m.get(k, 0) for k in green_keys)
        oth = tot - (res + com + ind + agr + frs + qry + grn)
        row = {
            "city_id": cid, "ring": ring, "total_km2": round(tot, 2),
            "residential_pct": round(res/tot*100, 1),
            "commercial_pct": round(com/tot*100, 1),
            "industrial_pct": round(ind/tot*100, 1),
            "agriculture_pct": round(agr/tot*100, 1),
            "forest_pct": round(frs/tot*100, 1),
            "quarry_pct": round(qry/tot*100, 1),
            "green_recreation_pct": round(grn/tot*100, 1),
            "other_pct": round(max(oth, 0)/tot*100, 1),
            "residential_km2": round(res, 2),
            "industrial_km2": round(ind, 2),
            "agriculture_km2": round(agr, 2),
            "forest_km2": round(frs, 2),
            "quarry_km2": round(qry, 2),
        }
        lu_rows_csv.append(row)
        if qry > 0.5:
            print(f"  {cid:10s} | {ring:20s} | quarry={qry:.2f} km2 ({row['quarry_pct']}%) | green={grn:.2f} km2 ({row['green_recreation_pct']}%)")

with open(OUT / "landuse_rings_5cities_shares.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(lu_rows_csv[0].keys()))
    w.writeheader()
    w.writerows(lu_rows_csv)

# 3. Exact Serbia Wheat-Mills-Bakeries Balance (fixing NP muni_code & BG city-level code 71308!)
np_muni_row = q("SELECT muni_code, unit_name FROM rzs_agri_census_2023 WHERE geo_level='municipality' AND unit_name LIKE '%Novi Pazar%'")
print("NP RZS MUNI ROW:", np_muni_row)
NP_CODE_SET = {str(r["muni_code"]) for r in np_muni_row}
BG_CODES_SET = {str(r["unit_code"]) for r in q("SELECT unit_code FROM admin_units WHERE city_id='beograd'")} | {"71308", "70203"}
BG_RING_CODES = {'80314', '80420', '80179', '80357', '80322', '71099', '70360'}
NP_RING_CODES = {'71072', '71188', '71021'}

all_muni_bal = q("""
    SELECT a.muni_code, a.unit_name, a.region, a.oblast, a.farms_kpz, a.uaa_kpz_ha, a.arable_ha,
           a.meadows_pastures_ha, a.cereals_ha, a.wheat_spelt_ha, a.maize_grain_ha,
           a.cattle, a.sheep, a.pigs, a.tractors_total, a.tractors_over_20y
    FROM rzs_agri_census_2023 a
    WHERE a.geo_level = 'municipality'
""")

def classify_code(mc, oblast=None, uname=""):
    mc = str(mc or "")
    if mc in BG_CODES_SET or (oblast and "Beograd" in oblast):
        return "Beograd (17 opština)"
    if mc in BG_RING_CODES:
        return "Beogradski prsten (7 opština)"
    if mc in NP_CODE_SET or "Novi Pazar" in uname:
        return "Novi Pazar (Grad)"
    if mc in NP_RING_CODES:
        return "Novopazarski prsten (Sjenica/Tutin/Raška)"
    if mc.startswith("8"):
        return "Ostatak Vojvodine"
    return "Ostatak Centralne/Južne Srbije"

groups = defaultdict(lambda: defaultdict(float))
for m in all_muni_bal:
    g = classify_code(m["muni_code"], m["oblast"], m["unit_name"])
    groups[g]["munis"] += 1
    for k in ["farms_kpz", "uaa_kpz_ha", "arable_ha", "meadows_pastures_ha", "wheat_spelt_ha", "maize_grain_ha", "cattle", "sheep", "pigs"]:
        groups[g][k] += (m[k] or 0)

apr_all = q("SELECT muni_code, muni_name, nace_code, employees, revenue_eur, net_profit_eur FROM apr_serbia_supply_chain")
apr_grp = defaultdict(lambda: defaultdict(float))
for a in apr_all:
    g = classify_code(a["muni_code"], None, a["muni_name"] or "")
    nc = a["nace_code"]
    apr_grp[g][f"cnt_{nc}"] += 1
    apr_grp[g][f"rev_{nc}_m"] += (a["revenue_eur"] or 0) / 1e6
    apr_grp[g][f"emp_{nc}"] += (a["employees"] or 0)

print("\n=== FIXED TERRITORIAL BALANCE (VERIFIED BG + NP) ===")
bal_rows = []
for g in ["Beograd (17 opština)", "Beogradski prsten (7 opština)", "Novi Pazar (Grad)", "Novopazarski prsten (Sjenica/Tutin/Raška)", "Ostatak Vojvodine", "Ostatak Centralne/Južne Srbije"]:
    ag = groups[g]
    ap = apr_grp[g]
    row = {
        "group": g,
        "munis_agri": int(ag["munis"]),
        "wheat_ha": round(ag["wheat_spelt_ha"], 1),
        "est_wheat_tonnes_5t_ha": round(ag["wheat_spelt_ha"] * 5.0, 0),
        "maize_ha": round(ag["maize_grain_ha"], 1),
        "cattle": int(ag["cattle"]),
        "sheep": int(ag["sheep"]),
        "pigs": int(ag["pigs"]),
        "grain_firms_0111": int(ap["cnt_0111"]),
        "grain_rev_m": round(ap["rev_0111_m"], 2),
        "mills_1061": int(ap["cnt_1061"]),
        "mills_rev_m": round(ap["rev_1061_m"], 2),
        "bakeries_1071": int(ap["cnt_1071"]),
        "bakeries_rev_m": round(ap["rev_1071_m"], 2),
        "biscuits_1072": int(ap["cnt_1072"]),
        "biscuits_rev_m": round(ap["rev_1072_m"], 2),
        "sawmills_1610": int(ap["cnt_1610"]),
        "sawmills_rev_m": round(ap["rev_1610_m"], 2),
    }
    bal_rows.append(row)
    print(f"  {g:42s} | wheat={row['wheat_ha']:9.1f}ha (~{row['est_wheat_tonnes_5t_ha']/1000:6.1f}kt) | mills={row['mills_1061']:3d} ({row['mills_rev_m']:6.2f}M) | bak={row['bakeries_1071']:3d} ({row['bakeries_rev_m']:6.2f}M) | bisc={row['biscuits_1072']:2d} ({row['biscuits_rev_m']:5.1f}M) | saw={row['sawmills_1610']:3d} ({row['sawmills_rev_m']:5.1f}M) | cattle={row['cattle']:6d} sheep={row['sheep']:6d}")

with open(OUT / "srb_wheat_mills_bakeries_territorial_balance.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(bal_rows[0].keys()))
    w.writeheader()
    w.writerows(bal_rows)

# Full names of Top 5 firms in 1061, 1071, 1072, 1610 + Novi Pazar supply chain firms
print("\n=== FULL NAMES TOP 5 FIRMS BY ROLE ===")
for nc in ["1061", "1071", "1072", "1610"]:
    print(f"  [NACE {nc}]")
    for f in q("SELECT name, muni_name, employees, ROUND(revenue_eur/1e6,2) AS rev_m, ROUND(net_profit_eur/1e6,2) AS prof_m FROM apr_serbia_supply_chain WHERE nace_code=? ORDER BY revenue_eur DESC LIMIT 5", (nc,)):
        print(f"    {f['name']} | {f['muni_name']} | emp={f['employees']} | rev={f['rev_m']}M | prof={f['prof_m']}M")

print("\n=== NOVI PAZAR & RING SUPPLY CHAIN FIRMS (TOP 12) ===")
for f in q("SELECT nace_code, sc_role, name, muni_name, employees, ROUND(revenue_eur/1e6,2) AS rev_m FROM apr_serbia_supply_chain WHERE muni_code IN ('70840','71072','71188','71021') OR muni_code IN (" + ",".join(f"'{c}'" for c in NP_CODE_SET) + ") ORDER BY revenue_eur DESC LIMIT 12"):
    print(f"    {f['nace_code']} | {f['name']} | {f['muni_name']} | emp={f['employees']} | rev={f['rev_m']}M")

# Top LQ per city (city level)
print("\n=== TOP LQ SPECIALIZATIONS BY CITY ===")
for cid in ["beograd", "sarajevo", "novi_pazar", "travnik"]:
    rows = q("""
        SELECT unit_name, nace_section, nace_name, companies_count, unit_share_pct, location_quotient, benchmark_scope
        FROM sector_structure
        WHERE city_id=? AND companies_count >= 15 AND location_quotient IS NOT NULL
        ORDER BY location_quotient DESC LIMIT 6
    """, (cid,))
    print(f"  [{cid}]")
    for r in rows:
        print(f"    {r['unit_name']:20s} | {r['nace_section']} {r['nace_name'][:32]:32s} | n={r['companies_count']:4d} ({r['unit_share_pct']:4.1f}%) | LQ={r['location_quotient']:.2f} ({r['benchmark_scope']})")

# S-scale sensitivity test (+20% flour, +15% labor, +20% rent)
print("\n=== S-SCALE BAKERY SENSITIVITY TEST (IMPACT ON BREAKEVEN LOAVES/DAY) ===")
bak = q("SELECT * FROM v_s_bakery_5cities_comparison ORDER BY monthly_total_cost_eur DESC")
for b in bak:
    tot = b["monthly_total_cost_eur"]
    be = b["breakeven_loaves_per_day"]
    d_flour = round(be * (0.20 * b["monthly_flour_eur"] / tot), 1)
    d_labor = round(be * (0.15 * b["monthly_labor_eur"] / tot), 1)
    d_rent  = round(be * (0.20 * b["monthly_rent_eur"] / tot), 1)
    print(f"  {b['city_id']:10s}: BE={be:3d}/d | +20% flour -> +{d_flour:4.1f} | +15% labor -> +{d_labor:4.1f} | +20% rent -> +{d_rent:4.1f}")

# REGENERATE CHARTS 1, 2, 3 WITH FIXED NUMBERS
def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def build_chart_1_bid_rent():
    W, H = 1120, 560
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" style="font-family:Segoe UI,Arial,sans-serif;background:#0f172a">']
    svg.append('<text x="32" y="36" fill="#f8fafc" font-size="20" font-weight="700">Bid-Rent gradijenti 2026: Beograd (14 zona) · Novi Pazar (7 zona) · Sarajevo (FGU 2024)</text>')
    svg.append('<text x="32" y="56" fill="#94a3b8" font-size="12">Levo: cena stanova (EUR/m²) po radijalnoj udaljenosti sa eksponencijalnim fitom · Desno: odnos poslovnog i stambenog m² (P_posl / P_stan)</text>')

    px0, px1, py0, py1 = 75, 565, 95, 485
    svg.append(f'<rect x="{px0}" y="{py0}" width="{px1-px0}" height="{py1-py0}" fill="#1e293b" rx="8" stroke="#334155"/>')
    max_d, max_p = 45.0, 2600.0
    def sx(d): return px0 + (min(d, max_d)/max_d)*(px1-px0)
    def sy(p): return py1 - (min(p, max_p)/max_p)*(py1-py0)

    for pval in [0, 500, 1000, 1500, 2000, 2500]:
        yy = sy(pval)
        svg.append(f'<line x1="{px0}" y1="{yy:.1f}" x2="{px1}" y2="{yy:.1f}" stroke="#334155" stroke-dasharray="3,4"/>')
        svg.append(f'<text x="{px0-8}" y="{yy+4:.1f}" fill="#94a3b8" font-size="11" text-anchor="end">{pval}</text>')
    for dval in [0, 5, 10, 15, 20, 30, 40]:
        xx = sx(dval)
        svg.append(f'<line x1="{xx:.1f}" y1="{py0}" x2="{xx:.1f}" y2="{py1}" stroke="#334155" stroke-dasharray="3,4"/>')
        svg.append(f'<text x="{xx:.1f}" y="{py1+18}" fill="#94a3b8" font-size="11" text-anchor="middle">{dval} km</text>')
    svg.append(f'<text x="{(px0+px1)/2}" y="{py1+38}" fill="#cbd5e1" font-size="12" text-anchor="middle">Radijalna udaljenost od CBD-a (km)</text>')
    svg.append(f'<text x="24" y="{(py0+py1)/2}" fill="#cbd5e1" font-size="12" text-anchor="middle" transform="rotate(-90 24 {(py0+py1)/2})">Cena stana (EUR/m²)</text>')

    series_cfg = [
        ("beograd_monocentric_excl_z4_satellites", "#38bdf8", "Beograd monocentrično (bez Z.IV satelita, n=9)"),
        ("novi_pazar_concentric_with_z4", "#f59e0b", "Novi Pazar (zone I–VII, n=7)"),
        ("sarajevo_urban_core", "#34d399", "Sarajevo (urbane općine bez Trnova, n=6)"),
    ]
    for key, col, lbl in series_cfg:
        reg = bid_regs[key]["stan"]
        if reg:
            pts_str = []
            max_r = 40 if "beograd" in key else (15 if "novi_pazar" in key else 18)
            for i in range(0, 41):
                d = max_r * i / 40.0
                p = reg["intercept_eur"] * math.exp(reg["slope_b"] * d)
                pts_str.append(f"{sx(d):.1f},{sy(p):.1f}")
            svg.append(f'<polyline points="{" ".join(pts_str)}" fill="none" stroke="{col}" stroke-width="2.5" opacity="0.92"/>')

    for z in enriched_zones:
        if z["city_id"] == "beograd" and z["stan_eur_m2"]:
            is_z4 = "četvrta" in z["zone_name"].lower()
            is_spec = any(k in z["zone_name"].lower() for k in ["zelenil", "ulazni", "specifi"])
            col = "#facc15" if is_z4 else ("#7dd3fc" if is_spec else "#38bdf8")
            r = 6.5 if is_z4 else (4.5 if is_spec else 5.5)
            cx, cy = sx(z["eff_dist_km"]), sy(z["stan_eur_m2"])
            svg.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{col}" stroke="#0f172a" stroke-width="1.2"/>')
            if is_z4:
                svg.append(f'<text x="{cx-8:.1f}" y="{cy-8:.1f}" fill="#fde047" font-size="9.5" text-anchor="end">BG Z.IV (sateliti 41km)</text>')
            elif z["zone_rank"] in (1, 3, 8):
                short = z["zone_name"].replace("Zona ", "Z.")[:12]
                svg.append(f'<text x="{cx+7:.1f}" y="{cy-5:.1f}" fill="#bae6fd" font-size="9.5">{esc(short)}</text>')
        elif z["city_id"] == "novi_pazar" and z["stan_eur_m2"]:
            cx, cy = sx(z["eff_dist_km"]), sy(z["stan_eur_m2"])
            svg.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5.5" fill="#f59e0b" stroke="#0f172a" stroke-width="1.2"/>')
            if z["zone_rank"] in (1, 4, 7):
                svg.append(f'<text x="{cx+7:.1f}" y="{cy+4:.1f}" fill="#fde68a" font-size="9.5">NP {esc(z["zone_name"])}</text>')

    for u in sa_units:
        cx, cy = sx(u["dist_cbd_km"]), sy(u["avg_apt_price_eur_m2"])
        is_tr = "Trnovo" in u["unit_name"]
        svg.append(f'<rect x="{cx-4:.1f}" y="{cy-4:.1f}" width="8" height="8" fill="{"#f43f5e" if is_tr else "#34d399"}" stroke="#0f172a" stroke-width="1"/>')
        if is_tr or u["unit_name"] in ("Stari Grad Sarajevo", "Ilidža"):
            svg.append(f'<text x="{cx+7:.1f}" y="{cy-4:.1f}" fill="{"#fda4af" if is_tr else "#a7f3d0"}" font-size="9.5">{esc(u["unit_name"].replace(" Sarajevo",""))}</text>')

    ly = py0 + 18
    for idx, (key, col, lbl) in enumerate(series_cfg):
        reg = bid_regs[key]["stan"]
        y_i = ly + idx * 19
        svg.append(f'<line x1="{px1-285}" y1="{y_i-4}" x2="{px1-265}" y2="{y_i-4}" stroke="{col}" stroke-width="3"/>')
        svg.append(f'<text x="{px1-258}" y="{y_i}" fill="#e2e8f0" font-size="10">{esc(lbl)}: {reg["pct_change_per_km"]:+.1f}%/km (R²={reg["r2"]:.2f})</text>')
    svg.append(f'<rect x="{px1-280}" y="{ly+52}" width="8" height="8" fill="#f43f5e"/><text x="{px1-258}" y="{ly+60}" fill="#fda4af" font-size="10">Bjelašnica / Trnovo (turistička inverzija)</text>')

    bx0, bx1, by0, by1 = 620, 1085, 95, 485
    svg.append(f'<rect x="{bx0}" y="{by0}" width="{bx1-bx0}" height="{by1-by0}" fill="#1e293b" rx="8" stroke="#334155"/>')
    svg.append(f'<text x="{(bx0+bx1)/2}" y="{by0+22}" fill="#e2e8f0" font-size="12.5" font-weight="600" text-anchor="middle">Premija poslovnog prostora (P_poslovno / P_stan)</text>')

    bars = []
    for z in enriched_zones:
        if z["city_id"] == "beograd" and z["ratio_poslovno_stan"]:
            lbl = "BG " + z["zone_name"].replace("Prva zona - ", "").replace("Zona ", "Z.").replace("Ekstra zona ", "Ek.").replace("poslovanja", "posl.").replace("stanovanja", "stan.").replace("zaštite zelenila ", "Zel.").replace("ulaznih pravaca", "Ulaz.").replace("specifičnih namena", "Spec.")
            bars.append((lbl, z["ratio_poslovno_stan"], "#38bdf8"))
        elif z["city_id"] == "novi_pazar" and z["ratio_poslovno_stan"]:
            lbl = "NP " + z["zone_name"].replace(" zona", "")
            bars.append((lbl, z["ratio_poslovno_stan"], "#f59e0b"))

    n_b = len(bars)
    row_h = (by1 - by0 - 52) / max(n_b, 1)
    max_r = 2.2
    x_left = bx0 + 108
    x_right = bx1 - 24
    x_one = x_left + (1.0 / max_r) * (x_right - x_left)
    svg.append(f'<line x1="{x_one:.1f}" y1="{by0+34}" x2="{x_one:.1f}" y2="{by1-18}" stroke="#cbd5e1" stroke-dasharray="3,3" opacity="0.6"/>')
    svg.append(f'<text x="{x_one:.1f}" y="{by1-5}" fill="#94a3b8" font-size="10" text-anchor="middle">1,0× (paritet)</text>')
    x_two = x_left + (2.0 / max_r) * (x_right - x_left)
    svg.append(f'<line x1="{x_two:.1f}" y1="{by0+34}" x2="{x_two:.1f}" y2="{by1-18}" stroke="#f59e0b" stroke-dasharray="3,3" opacity="0.4"/>')
    svg.append(f'<text x="{x_two:.1f}" y="{by1-5}" fill="#fde68a" font-size="10" text-anchor="middle">2,0×</text>')

    for i, (lbl, val, col) in enumerate(bars):
        yy = by0 + 36 + i * row_h
        bw = (val / max_r) * (x_right - x_left)
        svg.append(f'<text x="{x_left-6}" y="{yy+row_h*0.72:.1f}" fill="#cbd5e1" font-size="9.5" text-anchor="end">{esc(lbl)}</text>')
        svg.append(f'<rect x="{x_left}" y="{yy+1.5:.1f}" width="{bw:.1f}" height="{max(row_h-3.5, 4):.1f}" fill="{col}" rx="2" opacity="0.88"/>')
        svg.append(f'<text x="{x_left+bw+5:.1f}" y="{yy+row_h*0.72:.1f}" fill="#f8fafc" font-size="9.5">{val:.2f}×</text>')

    svg.append('<text x="32" y="544" fill="#64748b" font-size="10.5">Izvor: SQLite v3 (Sl. list BG 82/2025, Sl. list NP 14/2025, FGU RCN FBiH 2024) + digitalizovani GeoJSON slojevi zona.</text>')
    svg.append('</svg>')
    (CHARTS / "01_bid_rent_gradients_bg_np_sa.svg").write_text("\n".join(svg), encoding="utf-8")

def build_chart_2_landuse():
    W, H = 1120, 560
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" style="font-family:Segoe UI,Arial,sans-serif;background:#0f172a">']
    svg.append('<text x="32" y="36" fill="#f8fafc" font-size="20" font-weight="700">Von Thünenovi prstenovi namene zemljišta (OSM Landuse, 180.096 poligona)</text>')
    svg.append('<text x="32" y="56" fill="#94a3b8" font-size="12">Udeo makro-klasa zemljišta (%) po koncentričnim prstenovima udaljenosti od CBD-a za svih 5 gradova</text>')

    cats = [
        ("residential_pct", "#f97316", "Stanovanje"),
        ("commercial_pct", "#ec4899", "Komercijala"),
        ("industrial_pct", "#8b5cf6", "Industrija"),
        ("agriculture_pct", "#eab308", "Poljoprivreda"),
        ("forest_pct", "#22c55e", "Šuma"),
        ("quarry_pct", "#94a3b8", "Kopovi/Kamenolomi"),
        ("green_recreation_pct", "#14b8a6", "Parkovi/Rekreacija"),
        ("other_pct", "#334155", "Ostalo"),
    ]
    lx = 32
    for _, col, lbl in cats:
        svg.append(f'<rect x="{lx}" y="70" width="12" height="12" fill="{col}" rx="2"/>')
        svg.append(f'<text x="{lx+16}" y="80" fill="#e2e8f0" font-size="11">{esc(lbl)}</text>')
        lx += 16 + len(lbl)*6.8 + 14

    city_order = [
        ("beograd", "BEOGRAD (5.270 km²) — Panonsko-rečna metropola"),
        ("zagreb", "ZAGREB (3.058 km²) — Podmedvednički koridor"),
        ("sarajevo", "SARAJEVO (3.932 km²) — Dinarska kotlina"),
        ("travnik", "TRAVNIK (3.105 km²) — Lašvanska dolina"),
        ("novi_pazar", "NOVI PAZAR (1.875 km²) — Planinska kotlina"),
    ]
    by_city = defaultdict(list)
    for r in lu_rows_csv:
        by_city[r["city_id"]].append(r)

    positions = [
        (32, 102, 340, 195), (390, 102, 340, 195), (748, 102, 340, 195),
        (32, 320, 518, 195), (570, 320, 518, 195)
    ]
    short_ring = {
        '0-1 km (CBD)': '0–1 km',
        '1-3 km (Inner)': '1–3 km',
        '3-6 km (Urban)': '3–6 km',
        '6-15 km (Suburban)': '6–15 km',
        '15+ km (Hinterland)': '15+ km',
    }
    for (cid, title), (px, py, pw, ph) in zip(city_order, positions):
        svg.append(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" fill="#1e293b" rx="8" stroke="#334155"/>')
        svg.append(f'<text x="{px+12}" y="{py+22}" fill="#f8fafc" font-size="12" font-weight="700">{esc(title)}</text>')
        rows = by_city[cid]
        bx0 = px + 60
        bw_tot = pw - 74
        for idx, r in enumerate(rows):
            yy = py + 38 + idx * 29
            svg.append(f'<text x="{bx0-6}" y="{yy+14}" fill="#cbd5e1" font-size="10.5" text-anchor="end">{short_ring[r["ring"]]}</text>')
            cur_x = bx0
            for key, col, _ in cats:
                val = r[key]
                if val > 0:
                    w = (val / 100.0) * bw_tot
                    svg.append(f'<rect x="{cur_x:.1f}" y="{yy}" width="{w:.1f}" height="20" fill="{col}"/>')
                    if val >= 14:
                        svg.append(f'<text x="{cur_x+w/2:.1f}" y="{yy+14}" fill="#0f172a" font-size="9.5" font-weight="700" text-anchor="middle">{val:.0f}%</text>')
                    cur_x += w

    svg.append('<text x="32" y="544" fill="#64748b" font-size="10.5">Izvor: SQLite v3 (`osm_landuse_summary`), Geofabrik OSM ekstrakcija (SRB/HRV/BiH), 22.11.2026.</text>')
    svg.append('</svg>')
    (CHARTS / "02_landuse_von_thunen_rings_5cities.svg").write_text("\n".join(svg), encoding="utf-8")

def build_chart_3_supply_chain():
    W, H = 1120, 560
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" style="font-family:Segoe UI,Arial,sans-serif;background:#0f172a">']
    svg.append('<text x="32" y="36" fill="#f8fafc" font-size="20" font-weight="700">Lanac „Pšenica – Mlinovi – Pekare“: Srbija (L/XL) i ekonomika pekare u 5 gradova (S-skala)</text>')
    svg.append('<text x="32" y="56" fill="#94a3b8" font-size="12">Levo: teritorijalna asimetrija pšenice (ha), mlinova i pekara (prihod M EUR) · Desno: mesečni troškovi i tačka pokrića (vekni/dan)</text>')

    px0, py0, pw, ph = 32, 82, 520, 430
    svg.append(f'<rect x="{px0}" y="{py0}" width="{pw}" height="{ph}" fill="#1e293b" rx="8" stroke="#334155"/>')
    svg.append(f'<text x="{px0+14}" y="{py0+24}" fill="#f8fafc" font-size="13" font-weight="700">A. Teritorijalni bilans (Srbija): Pšenica vs. Prerada (Mlinovi + Pekare)</text>')

    sel_groups = [r for r in bal_rows[:4]]
    max_w = max(r["wheat_ha"] for r in sel_groups) or 1
    max_rev = max(r["mills_rev_m"] + r["bakeries_rev_m"] for r in sel_groups) or 1

    svg.append(f'<rect x="{px0+14}" y="{py0+36}" width="11" height="11" fill="#eab308"/><text x="{px0+30}" y="{py0+46}" fill="#cbd5e1" font-size="10.5">Pšenica (ha, Popis 2023)</text>')
    svg.append(f'<rect x="{px0+190}" y="{py0+36}" width="11" height="11" fill="#38bdf8"/><text x="{px0+206}" y="{py0+46}" fill="#cbd5e1" font-size="10.5">Mlinovi 1061 (M EUR)</text>')
    svg.append(f'<rect x="{px0+340}" y="{py0+36}" width="11" height="11" fill="#f97316"/><text x="{px0+356}" y="{py0+46}" fill="#cbd5e1" font-size="10.5">Pekare 1071 (M EUR)</text>')

    for idx, r in enumerate(sel_groups):
        yy = py0 + 70 + idx * 84
        svg.append(f'<text x="{px0+14}" y="{yy}" fill="#f8fafc" font-size="12" font-weight="600">{esc(r["group"])}</text>')
        bar_max_w = pw - 175
        w1 = max((r["wheat_ha"] / max_w) * bar_max_w, 4)
        svg.append(f'<rect x="{px0+14}" y="{yy+8}" width="{w1:.1f}" height="16" fill="#eab308" rx="2"/>')
        svg.append(f'<text x="{px0+20+w1:.1f}" y="{yy+20}" fill="#fde047" font-size="10.5">{r["wheat_ha"]:,.0f} ha</text>')
        wm = (r["mills_rev_m"] / max_rev) * bar_max_w
        wb = (r["bakeries_rev_m"] / max_rev) * bar_max_w
        svg.append(f'<rect x="{px0+14}" y="{yy+30}" width="{wm:.1f}" height="16" fill="#38bdf8" rx="2"/>')
        svg.append(f'<rect x="{px0+14+wm:.1f}" y="{yy+30}" width="{max(wb,2):.1f}" height="16" fill="#f97316" rx="2"/>')
        svg.append(f'<text x="{px0+20+wm+wb:.1f}" y="{yy+42}" fill="#e2e8f0" font-size="10.5">Mlin {r["mills_rev_m"]:.1f}M + Pek {r["bakeries_rev_m"]:.1f}M</text>')
        svg.append(f'<text x="{px0+14}" y="{yy+62}" fill="#94a3b8" font-size="10">Goveda: {r["cattle"]:,} · Ovce: {r["sheep"]:,} · Pilane (1610): {r["sawmills_1610"]} ({r["sawmills_rev_m"]:.1f}M EUR)</text>')

    qx0, qy0, qw, qh = 572, 82, 516, 430
    svg.append(f'<rect x="{qx0}" y="{qy0}" width="{qw}" height="{qh}" fill="#1e293b" rx="8" stroke="#334155"/>')
    svg.append(f'<text x="{qx0+14}" y="{qy0+24}" fill="#f8fafc" font-size="13" font-weight="700">B. Ekonomika pekare u 5 gradova (EUR/mesec i vekni/dan)</text>')

    cost_parts = [
        ("monthly_labor_eur", "#6366f1", "Rad"),
        ("monthly_flour_eur", "#eab308", "Brašno"),
        ("monthly_rent_eur", "#ec4899", "Kirija"),
        ("monthly_wood_eur", "#22c55e", "Drvo"),
        ("monthly_elec_eur", "#38bdf8", "Struja"),
    ]
    lx = qx0 + 14
    for _, col, lbl in cost_parts:
        svg.append(f'<rect x="{lx}" y="{qy0+36}" width="11" height="11" fill="{col}"/><text x="{lx+15}" y="{qy0+46}" fill="#cbd5e1" font-size="10.5">{lbl}</text>')
        lx += 78

    max_cost = 13500.0
    bar_w_max = qw - 140
    for idx, b in enumerate(bak):
        yy = qy0 + 78 + idx * 66
        svg.append(f'<text x="{qx0+14}" y="{yy}" fill="#f8fafc" font-size="12" font-weight="700">{esc(b["city_name"])} — {b["monthly_total_cost_eur"]:,.0f} EUR/mes · Hleb: {b["bread_500g_retail_eur"]:.2f} EUR</text>')
        cur_x = qx0 + 14
        tot_drawn = 0
        for col_k, col, _ in cost_parts:
            v = b[col_k] or 0
            w = (v / max_cost) * bar_w_max
            svg.append(f'<rect x="{cur_x:.1f}" y="{yy+8}" width="{w:.1f}" height="22" fill="{col}"/>')
            cur_x += w
            tot_drawn += v
        rem = max((b["monthly_total_cost_eur"] or 0) - tot_drawn, 0)
        if rem > 0:
            w = (rem / max_cost) * bar_w_max
            svg.append(f'<rect x="{cur_x:.1f}" y="{yy+8}" width="{w:.1f}" height="22" fill="#475569"/>')
            cur_x += w
        svg.append(f'<rect x="{qx0+qw-112}" y="{yy+6}" width="98" height="26" fill="#0f172a" stroke="#f59e0b" rx="5"/>')
        svg.append(f'<text x="{qx0+qw-63}" y="{yy+23}" fill="#fde68a" font-size="11.5" font-weight="700" text-anchor="middle">{b["breakeven_loaves_per_day"]} vekni/dan</text>')
        svg.append(f'<text x="{qx0+14}" y="{yy+44}" fill="#94a3b8" font-size="10">Brašno {b["cost_share_flour_pct"]:.1f}% · Rad {b["cost_share_labor_pct"]:.1f}% · Kirija {b["cost_share_rent_pct"]:.1f}% · PDV hleb {b["vat_bread_pct"]:.0f}% · OSM pekara: {b["osm_bakeries_in_region"]}</text>')

    svg.append('<text x="32" y="544" fill="#64748b" font-size="10.5">Izvor: SQLite v3 (RZS Popis poljoprivrede 2023, APR 2024 FI 2.926 firmi, s_bakery_unit_model, s_scale_input_costs).</text>')
    svg.append('</svg>')
    (CHARTS / "03_wheat_mills_bakeries_and_s_scale.svg").write_text("\n".join(svg), encoding="utf-8")

build_chart_1_bid_rent()
build_chart_2_landuse()
build_chart_3_supply_chain()

with open(OUT / "v3_refined_study_summary.json", "w", encoding="utf-8") as f:
    json.dump({
        "bid_rent_regressions": bid_regs,
        "enriched_tax_zones": enriched_zones,
        "landuse_rings": lu_rows_csv,
        "srb_supply_chain_balance": bal_rows,
    }, f, ensure_ascii=False, indent=2)
print("DONE PRECISION PATCH.")
