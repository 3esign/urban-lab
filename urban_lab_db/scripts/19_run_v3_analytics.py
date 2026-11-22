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
OUT.mkdir(parents=True, exist_ok=True)

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

def geom_centroid(geom):
    # Area-weighted or simple vertex-mean centroid for Polygon / MultiPolygon
    pts = []
    gtype = geom.get("type")
    coords = geom.get("coordinates", [])
    if gtype == "Polygon":
        ring = coords[0] if coords else []
        pts.extend(ring)
    elif gtype == "MultiPolygon":
        for poly in coords:
            if poly and poly[0]:
                pts.extend(poly[0])
    if not pts:
        return None, None
    lons = [p[0] for p in pts]
    lats = [p[1] for p in pts]
    return sum(lats)/len(lats), sum(lons)/len(lons)

def ols_log_linear(xs, ys):
    # ln(y) = a + b*x  => gradient beta = -b (decay per km), R^2
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
    # half-distance: distance where price halves = ln(2)/(-b)
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

def pearson_r(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 3:
        return None
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    num = sum((p[0]-mx)*(p[1]-my) for p in pairs)
    den = math.sqrt(sum((p[0]-mx)**2 for p in pairs) * sum((p[1]-my)**2 for p in pairs))
    return round(num / den, 4) if den > 0 else None

results = {}

# 1. Core 5-city comparison & macro/NUTS3/XL/Hinterland
results["cities"] = q("SELECT * FROM cities ORDER BY population DESC")
results["v_city_comparison"] = q("SELECT * FROM v_city_comparison ORDER BY population DESC")
results["fiscal_budgets"] = q("SELECT * FROM fiscal_budgets ORDER BY city_id, total_budget_eur DESC")
results["xl_nuts3_gdp"] = q("SELECT * FROM v_xl_latest_nuts3_gdp ORDER BY gdp_eur_per_capita DESC")
results["xl_country_structural"] = q("SELECT * FROM v_xl_country_structural_profile ORDER BY indicator_key, country_iso")
results["xl_corridors"] = q("SELECT * FROM xl_corridors_projects_strategies ORDER BY investment_mio_eur DESC")
results["l_hinterland_summary"] = q("SELECT * FROM v_l_hinterland_summary")
results["l_hinterland_units"] = q("SELECT * FROM hinterland_units ORDER BY city_hub, dist_cbd_km")
results["l_agri_forestry_trade"] = q("SELECT * FROM hinterland_agri_forestry_trade ORDER BY city_hub")
results["commuting_flows"] = q("SELECT * FROM commuting_and_flows ORDER BY city_hub, commuters_total DESC")

# 2. Top LQ specializations per city (city-wide or main unit)
results["sector_lq_top"] = q("""
    SELECT city_id, unit_name, nace_section, nace_name, companies_count, unit_share_pct, benchmark_share_pct, location_quotient, benchmark_scope
    FROM sector_structure
    WHERE location_quotient IS NOT NULL AND companies_count >= 10
    ORDER BY city_id, location_quotient DESC
""")
results["beograd_opstine"] = q("SELECT * FROM v_beograd_opstine_economy ORDER BY apr_rev_eur_per_capita DESC")

# 3. Wheat - Mills - Bakeries & Supply Chain (Serbia + 5 cities S-scale)
results["s_bakery_5cities"] = q("SELECT * FROM v_s_bakery_5cities_comparison ORDER BY monthly_total_cost_eur DESC")
results["s_input_costs"] = q("SELECT * FROM s_scale_input_costs")
results["s_bakery_model"] = q("SELECT * FROM s_bakery_unit_model")

results["srb_sc_totals_by_nace"] = q("""
    SELECT nace_code, sc_role, COUNT(*) AS firms,
           SUM(CASE WHEN has_fi=1 THEN 1 ELSE 0 END) AS firms_with_fi,
           SUM(COALESCE(employees,0)) AS employees,
           ROUND(SUM(COALESCE(revenue_eur,0))/1e6, 2) AS revenue_eur_m,
           ROUND(SUM(COALESCE(net_profit_eur,0))/1e6, 2) AS net_profit_eur_m,
           ROUND(SUM(COALESCE(assets_eur,0))/1e6, 2) AS assets_eur_m,
           COUNT(DISTINCT muni_code) AS munis_present
    FROM apr_serbia_supply_chain
    GROUP BY nace_code, sc_role
    ORDER BY revenue_eur_m DESC
""")

# HHI & Top 10 firms per supply chain role
sc_concentration = {}
for role_row in results["srb_sc_totals_by_nace"]:
    nace = role_row["nace_code"]
    firms = q("""
        SELECT maticni_broj, name, muni_name, employees,
               ROUND(COALESCE(revenue_eur,0)/1e6, 3) AS rev_m,
               ROUND(COALESCE(net_profit_eur,0)/1e6, 3) AS profit_m
        FROM apr_serbia_supply_chain
        WHERE nace_code = ? AND revenue_eur > 0
        ORDER BY revenue_eur DESC
    """, (nace,))
    tot_rev = sum(f["rev_m"] for f in firms)
    hhi = sum(((f["rev_m"]/tot_rev)*100)**2 for f in firms) if tot_rev > 0 else 0
    cr4 = sum(f["rev_m"] for f in firms[:4]) / tot_rev * 100 if tot_rev > 0 else 0
    cr10 = sum(f["rev_m"] for f in firms[:10]) / tot_rev * 100 if tot_rev > 0 else 0
    sc_concentration[nace] = {
        "sc_role": role_row["sc_role"],
        "firms_rev_pos": len(firms),
        "total_rev_m": round(tot_rev, 2),
        "hhi": round(hhi, 1),
        "cr4_pct": round(cr4, 1),
        "cr10_pct": round(cr10, 1),
        "top10": firms[:10]
    }
results["srb_sc_concentration"] = sc_concentration

# Serbia agri census 2023 regional & municipality totals
results["rzs_agri_regions"] = q("""
    SELECT unit_name, geo_level, farms_kpz, uaa_kpz_ha, arable_ha, meadows_pastures_ha,
           orchards_ha, cereals_ha, wheat_spelt_ha, maize_grain_ha, industrial_crops_ha,
           cattle, pigs, sheep, goats, poultry, awu_labor_units, tractors_total, tractors_over_20y
    FROM rzs_agri_census_2023
    WHERE geo_level != 'municipality'
    ORDER BY geo_level, uaa_kpz_ha DESC
""")

results["rzs_agri_top_wheat_munis"] = q("""
    SELECT * FROM v_srb_wheat_mills_bakeries_balance
    ORDER BY wheat_ha DESC LIMIT 20
""")
results["rzs_agri_top_mills_munis"] = q("""
    SELECT * FROM v_srb_wheat_mills_bakeries_balance
    ORDER BY mills_rev_eur_m DESC LIMIT 15
""")
results["rzs_agri_top_bakeries_munis"] = q("""
    SELECT * FROM v_srb_wheat_mills_bakeries_balance
    ORDER BY bakeries_rev_eur_m DESC LIMIT 15
""")

# Specific rings: Belgrade 17 munis, Belgrade hinterland ring (Pancevo, Stara Pazova, Indjija, Ruma, Pecinci, Smederevo, Valjevo), Novi Pazar + ring (Sjenica, Tutin, Raska)
bg_muni_names = [r["unit_name"] for r in results["beograd_opstine"]]
bg_ring_codes = ['80314', '80420', '80179', '80357', '80322', '71099', '70360'] # Pancevo, Stara Pazova, Indjija, Ruma, Pecinci, Smederevo, Valjevo
np_ring_codes = ['70840', '71072', '71188', '71021'] # NP (check code below), Sjenica, Tutin, Raska

results["bg_and_np_agri_sc_detail"] = q("""
    SELECT a.muni_code, a.unit_name, a.region, a.oblast, a.farms_kpz, a.uaa_kpz_ha, a.arable_ha,
           a.meadows_pastures_ha, a.cereals_ha, a.wheat_spelt_ha, a.maize_grain_ha,
           a.cattle, a.sheep, a.pigs, a.tractors_total, a.tractors_over_20y,
           COALESCE(b.apr_grain_firms,0) AS apr_grain_firms,
           COALESCE(b.apr_mills,0) AS apr_mills,
           COALESCE(b.apr_bakeries,0) AS apr_bakeries,
           COALESCE(b.apr_sawmills,0) AS apr_sawmills,
           COALESCE(b.mills_rev_eur_m,0) AS mills_rev_eur_m,
           COALESCE(b.bakeries_rev_eur_m,0) AS bakeries_rev_eur_m
    FROM rzs_agri_census_2023 a
    LEFT JOIN v_srb_wheat_mills_bakeries_balance b ON a.muni_code = b.muni_code
    WHERE a.geo_level = 'municipality'
      AND (a.oblast LIKE '%Beograd%' OR a.muni_code IN ('80314','80420','80179','80357','80322','71099','70360')
           OR a.unit_name LIKE '%Novi Pazar%' OR a.unit_name LIKE '%Sjenica%' OR a.unit_name LIKE '%Tutin%' OR a.unit_name LIKE '%Raška%' OR a.unit_name LIKE '%Raska%')
    ORDER BY a.oblast, a.wheat_spelt_ha DESC
""")

# Also check APR supply chain firms in BG 17 munis, BG ring, NP + ring directly by muni_code/name
results["hinterland_firms_summary"] = q("""
    SELECT city_hub, muni_code, muni_name, COUNT(*) AS firms,
           SUM(COALESCE(employees,0)) AS employees,
           ROUND(SUM(COALESCE(revenue_eur,0))/1e6, 2) AS revenue_eur_m,
           ROUND(SUM(COALESCE(net_profit_eur,0))/1e6, 2) AS net_profit_eur_m
    FROM companies_sr_hinterland
    GROUP BY city_hub, muni_code, muni_name
    ORDER BY city_hub, revenue_eur_m DESC
""")

# 4. Landuse rings across 5 cities
results["landuse_profile"] = q("SELECT * FROM v_5cities_landuse_profile ORDER BY mapped_area_km2 DESC")
results["landuse_by_ring_macro"] = q("""
    SELECT city_id, ring, macro_group, SUM(polygon_count) AS polygons,
           ROUND(SUM(area_km2), 3) AS area_km2
    FROM osm_landuse_summary
    GROUP BY city_id, ring, macro_group
    ORDER BY city_id, ring, area_km2 DESC
""")
results["landuse_rings_distinct"] = q("SELECT DISTINCT ring FROM osm_landuse_summary ORDER BY ring")
results["landuse_major_industrial_top"] = q("""
    SELECT city_id, macro_group, fclass, name, ROUND(area_km2, 3) AS area_km2, ROUND(dist_cbd_km, 2) AS dist_cbd_km, ring
    FROM osm_landuse_major_zones
    WHERE macro_group IN ('industrial', 'commercial_retail', 'quarry')
    ORDER BY city_id, area_km2 DESC
""")
results["osm_5cities_centrality"] = q("SELECT * FROM v_osm_5cities_centrality ORDER BY city_id, ring")

# 5. Bid-Rent gradients BG & NP (SQLite + GeoJSON centroid distances) + Sarajevo + Travnik + Zagreb leases
results["tax_zones_gis_summary"] = q("SELECT * FROM property_tax_zones_gis_summary ORDER BY city_id, zone_rank")
results["property_zones_prices_all"] = q("SELECT * FROM property_zones_prices ORDER BY city_id, property_type, price_eur_m2 DESC")

city_cbd = {c["city_id"]: (c["cbd_lat"], c["cbd_lon"]) for c in results["cities"]}

def compute_zone_distances(geojson_path, city_id):
    lat0, lon0 = city_cbd[city_id]
    with open(geojson_path, "r", encoding="utf-8") as f:
        gj = json.load(f)
    by_zone = defaultdict(list)
    for feat in gj.get("features", []):
        props = feat.get("properties", {})
        zname = props.get("zone_name") or props.get("zona") or props.get("name")
        area = props.get("area_km2") or 1.0
        clat, clon = geom_centroid(feat.get("geometry", {}))
        if clat is not None and zname:
            d = haversine_km(lat0, lon0, clat, clon)
            by_zone[zname].append((d, float(area) if area else 1.0, props))
    out = {}
    for zname, vals in by_zone.items():
        tot_w = sum(v[1] for v in vals)
        w_dist = sum(v[0]*v[1] for v in vals) / tot_w if tot_w > 0 else sum(v[0] for v in vals)/len(vals)
        min_d = min(v[0] for v in vals)
        max_d = max(v[0] for v in vals)
        out[zname] = {
            "weighted_dist_cbd_km": round(w_dist, 2),
            "min_dist_km": round(min_d, 2),
            "max_dist_km": round(max_d, 2),
            "poly_count": len(vals),
            "sample_props_keys": list(vals[0][2].keys()) if vals else []
        }
    return out

bg_zone_dists = compute_zone_distances(BOUND / "beograd_poreske_zone_2026.geojson", "beograd")
np_zone_dists = compute_zone_distances(BOUND / "novi_pazar_poreske_zone_2026.geojson", "novi_pazar")
results["bg_zone_dists"] = bg_zone_dists
results["np_zone_dists"] = np_zone_dists

# Join tax_zones_gis_summary with computed distances & compute ratios + regressions
enriched_zones = []
for row in results["tax_zones_gis_summary"]:
    cid = row["city_id"]
    zname = row["zone_name"]
    dinfo = (bg_zone_dists if cid == "beograd" else np_zone_dists).get(zname, {})
    r = dict(row)
    r["dist_cbd_km"] = dinfo.get("weighted_dist_cbd_km")
    r["min_dist_km"] = dinfo.get("min_dist_km")
    r["max_dist_km"] = dinfo.get("max_dist_km")
    if r["stan_eur_m2"] and r["poslovne_eur_m2"]:
        r["ratio_poslovno_stan"] = round(r["poslovne_eur_m2"] / r["stan_eur_m2"], 3)
    else:
        r["ratio_poslovno_stan"] = None
    if r["gradj_zem_eur_m2"] and r["polj_zem_eur_m2"] and r["polj_zem_eur_m2"] > 0:
        r["ratio_gradj_polj"] = round(r["gradj_zem_eur_m2"] / r["polj_zem_eur_m2"], 2)
    else:
        r["ratio_gradj_polj"] = None
    if r["stan_eur_m2"] and r["gradj_zem_eur_m2"] and r["stan_eur_m2"] > 0:
        r["land_share_of_apt_pct"] = round(r["gradj_zem_eur_m2"] / r["stan_eur_m2"] * 100, 1)
    else:
        r["land_share_of_apt_pct"] = None
    enriched_zones.append(r)

results["enriched_tax_zones"] = enriched_zones

# Bid-Rent OLS regressions
bid_rent_regs = {}
for cid in ["beograd", "novi_pazar"]:
    zrows = [z for z in enriched_zones if z["city_id"] == cid and z["dist_cbd_km"] is not None]
    # Standard concentric zones (excluding special/green zones for BG when fitting concentric ring decay)
    zrows_core = [z for z in zrows if "Zelenilo" not in z["zone_name"] and "Specifi" not in z["zone_name"] and "Ulazni" not in z["zone_name"]]
    for label, subset in [("all_zones", zrows), ("concentric_zones", zrows_core)]:
        bid_rent_regs[f"{cid}_{label}"] = {
            "stan": ols_log_linear([z["dist_cbd_km"] for z in subset], [z["stan_eur_m2"] for z in subset]),
            "kuca": ols_log_linear([z["dist_cbd_km"] for z in subset], [z["kuca_eur_m2"] for z in subset]),
            "poslovne": ols_log_linear([z["dist_cbd_km"] for z in subset], [z["poslovne_eur_m2"] for z in subset]),
            "gradj_zem": ols_log_linear([z["dist_cbd_km"] for z in subset], [z["gradj_zem_eur_m2"] for z in subset]),
            "polj_zem": ols_log_linear([z["dist_cbd_km"] for z in subset], [z["polj_zem_eur_m2"] for z in subset]),
        }

# Sarajevo bid-rent regression using admin_units dist_cbd_km + property_zones_prices
sa_units = q("SELECT unit_name, dist_cbd_km, avg_apt_price_eur_m2, avg_net_wage_eur, population, density_per_km2 FROM admin_units WHERE city_id='sarajevo' AND avg_apt_price_eur_m2 IS NOT NULL ORDER BY dist_cbd_km")
results["sarajevo_units_bidrent"] = sa_units
# Excluding Bjelasnica/Trnovo tourist outlier if present
sa_core = [u for u in sa_units if "Trnovo" not in u["unit_name"] and "Bjela" not in u["unit_name"]]
bid_rent_regs["sarajevo_all"] = {"stan": ols_log_linear([u["dist_cbd_km"] for u in sa_units], [u["avg_apt_price_eur_m2"] for u in sa_units])}
bid_rent_regs["sarajevo_urban_no_trnovo"] = {"stan": ols_log_linear([u["dist_cbd_km"] for u in sa_core], [u["avg_apt_price_eur_m2"] for u in sa_core])}
results["bid_rent_regressions"] = bid_rent_regs

# Belgrade 17 municipalities correlations (wage, rev/capita, density, dist_cbd)
bg_ops = results["beograd_opstine"]
results["beograd_17_correlations"] = {
    "r_dist_wage": pearson_r([o["dist_cbd_km"] for o in bg_ops], [o["avg_net_wage_eur"] for o in bg_ops]),
    "r_dist_rev_pc": pearson_r([o["dist_cbd_km"] for o in bg_ops], [o["apr_rev_eur_per_capita"] for o in bg_ops]),
    "r_wage_rev_pc": pearson_r([o["avg_net_wage_eur"] for o in bg_ops], [o["apr_rev_eur_per_capita"] for o in bg_ops]),
    "r_density_wage": pearson_r([o["density_per_km2"] for o in bg_ops], [o["avg_net_wage_eur"] for o in bg_ops]),
}

# Zagreb commercial leases summary
results["zagreb_leases_summary"] = q("""
    SELECT status, COUNT(*) AS n,
           ROUND(AVG(monthly_rent_eur), 2) AS avg_rent_eur,
           ROUND(MIN(monthly_rent_eur), 2) AS min_rent_eur,
           ROUND(MAX(monthly_rent_eur), 2) AS max_rent_eur,
           ROUND(SUM(monthly_rent_eur), 2) AS total_monthly_eur
    FROM zagreb_commercial_leases
    WHERE monthly_rent_eur IS NOT NULL AND monthly_rent_eur > 0
    GROUP BY status
""")
# Median rent for Zagreb leases
zg_rents = [r[0] for r in cur.execute("SELECT monthly_rent_eur FROM zagreb_commercial_leases WHERE monthly_rent_eur > 0 ORDER BY monthly_rent_eur").fetchall()]
if zg_rents:
    results["zagreb_leases_quantiles"] = {
        "n": len(zg_rents),
        "p10": zg_rents[int(len(zg_rents)*0.1)],
        "p25": zg_rents[int(len(zg_rents)*0.25)],
        "median": zg_rents[len(zg_rents)//2],
        "p75": zg_rents[int(len(zg_rents)*0.75)],
        "p90": zg_rents[int(len(zg_rents)*0.9)],
        "max": zg_rents[-1]
    }

# Save full JSON
out_json = OUT / "v3_analytical_metrics.json"
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

# Check plotting libs
libs = {}
for mod in ["matplotlib", "numpy", "scipy", "pandas"]:
    try:
        __import__(mod)
        libs[mod] = True
    except Exception:
        libs[mod] = False
print("LIBS:", libs)

# Print compact executive summary to stdout so we can inspect exact numbers
print("\n=== 1. CITIES COMPARISON ===")
for c in results["v_city_comparison"]:
    print(c)

print("\n=== 2. BID-RENT REGRESSIONS ===")
print(json.dumps(results["bid_rent_regressions"], indent=2))

print("\n=== 3. ENRICHED TAX ZONES BG & NP ===")
for z in enriched_zones:
    print(f"{z['city_id']:10s} | #{z['zone_rank']:2d} {z['zone_name']:28s} | d={str(z['dist_cbd_km']):>5s}km | area={z['total_area_km2']:7.2f} | stan={str(z['stan_eur_m2']):>7s} | posl={str(z['poslovne_eur_m2']):>7s} | ratio={str(z['ratio_poslovno_stan']):>5s} | grZem={str(z['gradj_zem_eur_m2']):>6s} | polj={str(z['polj_zem_eur_m2']):>5s} | G/P={str(z['ratio_gradj_polj']):>6s}")

print("\n=== 4. SRB SUPPLY CHAIN TOTALS & CONCENTRATION ===")
for r in results["srb_sc_totals_by_nace"]:
    conc = sc_concentration[r["nace_code"]]
    print(f"{r['nace_code']} ({r['sc_role']:16s}): firms={r['firms']:4d} (FI:{r['firms_with_fi']:4d}), emp={r['employees']:6d}, rev={r['revenue_eur_m']:7.2f}M, prof={r['net_profit_eur_m']:6.2f}M, munis={r['munis_present']:3d} | HHI={conc['hhi']:6.1f}, CR4={conc['cr4_pct']:4.1f}%, CR10={conc['cr10_pct']:4.1f}%")

print("\n=== 5. LANDUSE PROFILE ===")
for r in results["landuse_profile"]:
    print(r)
print("LANDUSE RINGS:", [r["ring"] for r in results["landuse_rings_distinct"]])

print("\n=== 6. S-SCALE BAKERY 5 CITIES ===")
for r in results["s_bakery_5cities"]:
    print(f"{r['city_id']:10s}: flour={r['flour_t500_eur_kg']} wood={r['firewood_hardwood_eur_prm']} elec={r['elec_eur_kwh_small']} rent={r['commercial_rent_eur_m2_month']} totCost={r['monthly_total_cost_eur']} bread={r['bread_500g_retail_eur']} BE={r['breakeven_loaves_per_day']}/d (flour%={r['cost_share_flour_pct']} labor%={r['cost_share_labor_pct']} rent%={r['cost_share_rent_pct']}) OSM_bak={r['osm_bakeries_in_region']}")

print("\n=== 7. BEOGRAD 17 CORRELATIONS & ZAGREB LEASES ===")
print("BG17 corr:", results["beograd_17_correlations"])
print("ZG leases:", results.get("zagreb_leases_quantiles"))
print("Saved full metrics to:", out_json)
