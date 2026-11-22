from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(str(DB_DIR))
V4_DB = BASE_DIR / "curated" / "urban_lab_5cities_v4.sqlite"
RAW_W4 = BASE_DIR / "raw" / "wave4"

conn = sqlite3.connect(str(V4_DB))
conn.row_factory = sqlite3.Row

report = {}

# 1. Core integrity check: v3 tables untouched vs v4 tables
v3_tables = [
    "cities", "admin_units", "companies_sr", "hinterland_units",
    "property_tax_zones_gis_summary", "osm_landuse_major_zones", "osm_pois",
    "zagreb_markets", "xl_corridors_projects_strategies",
]
report["v3_counts"] = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in v3_tables}
report["fk_errors"] = len(conn.execute("PRAGMA foreign_key_check").fetchall())

# 2. Trust-tier & documents coverage by city
report["trust_coverage"] = [dict(r) for r in conn.execute("SELECT * FROM v_trust_tier_coverage_by_city ORDER BY city_id, trust_tier").fetchall()]

# 3. Election metrics by city & election_id (regular vs postal/absentee!)
report["elections_by_city"] = [
    dict(r) for r in conn.execute(
        """
        SELECT city_id, election_id, authority_body, station_type,
               COUNT(*) AS stations_n,
               SUM(registered_voters) AS sum_reg,
               SUM(ballots_cast) AS sum_cast,
               ROUND(100.0 * SUM(ballots_cast) / NULLIF(SUM(registered_voters), 0), 2) AS weighted_turnout_pct,
               ROUND(AVG(invalid_ballots_pct), 2) AS avg_invalid_pct,
               ROUND(AVG(winning_margin_pp), 2) AS avg_margin_pp,
               ROUND(AVG(effective_num_parties_enp), 3) AS avg_enp
        FROM v_election_station_metrics
        GROUP BY city_id, election_id, authority_body, station_type
        ORDER BY city_id, election_id, station_type
        """
    ).fetchall()
]

# Top/Bottom turnout & ENP municipalities in Belgrade (RIK 2023) and Sarajevo (CIK 2024)
report["beograd_muni_elections"] = [
    dict(r) for r in conn.execute(
        """
        SELECT municipality_name, COUNT(*) AS bm_n,
               ROUND(100.0 * SUM(ballots_cast) / NULLIF(SUM(registered_voters), 0), 2) AS turnout_pct,
               ROUND(AVG(winning_margin_pp), 2) AS avg_margin_pp,
               ROUND(AVG(effective_num_parties_enp), 3) AS avg_enp,
               SUM(CASE WHEN winner_bloc = 'incumbent_national' THEN 1 ELSE 0 END) AS bm_won_incumbent,
               SUM(CASE WHEN winner_bloc = 'opposition_civic_green' THEN 1 ELSE 0 END) AS bm_won_civic_opp
        FROM v_election_station_metrics
        WHERE city_id = 'beograd' AND election_id = 'elec:srb:2023-12-17:parl'
        GROUP BY municipality_name
        ORDER BY turnout_pct DESC
        """
    ).fetchall()
]

# Public Choice Join: Elections vs Procurement by Gazetteer Zone (Sarajevo + Travnik!)
report["election_procurement_join"] = [
    dict(r) for r in conn.execute(
        """
        SELECT * FROM v_election_procurement_zone_join
        ORDER BY procurement_eur_m DESC
        """
    ).fetchall()
]

# 4. BiH EJN Procurement breakdown by city & year & top buyers
report["procurement_summary"] = [dict(r) for r in conn.execute("SELECT * FROM v_procurement_structural_indicators ORDER BY city_id, award_year").fetchall()]
report["procurement_top_buyers"] = [
    dict(r) for r in conn.execute(
        """
        SELECT p.city_id, e.canonical_name AS buyer_name, COUNT(*) AS contracts_n,
               ROUND(SUM(p.contract_value_eur)/1e6, 3) AS total_eur_m,
               SUM(p.single_bidder_flag) AS sb_n,
               ROUND(100.0 * SUM(p.single_bidder_flag)/COUNT(*), 1) AS sb_pct
        FROM domain_signals_procurement p
        JOIN entities e ON p.buyer_entity_id = e.entity_id
        GROUP BY p.city_id, e.canonical_name
        ORDER BY total_eur_m DESC
        LIMIT 12
        """
    ).fetchall()
]

# 5. Air Quality & Heating Degree Days (2024-2026) comparative panel across 5 cities
report["air_winter_vs_summer"] = [
    dict(r) for r in conn.execute(
        """
        SELECT city_id, grid_cell_id,
               ROUND(AVG(CASE WHEN substr(period_start,6,2) IN ('11','12','01','02') THEN value_num END), 2) AS winter_pm25,
               ROUND(AVG(CASE WHEN substr(period_start,6,2) IN ('06','07','08') THEN value_num END), 2) AS summer_pm25,
               ROUND(MAX(value_num), 2) AS peak_month_pm25,
               COUNT(*) AS months_n
        FROM domain_signals_sensors
        WHERE sensor_metric = 'openaq_pm25_ugm3'
        GROUP BY city_id, grid_cell_id
        ORDER BY winter_pm25 DESC
        """
    ).fetchall()
]
report["event_study_did"] = [dict(r) for r in conn.execute("SELECT * FROM v_event_study_did_summary").fetchall()]

# 6. Science (Uloga A & B + collaboration network)
report["science_by_city"] = [
    dict(r) for r in conn.execute(
        """
        SELECT city_id,
               COUNT(*) AS works_n,
               SUM(CASE WHEN science_role = 'about_city' THEN 1 ELSE 0 END) AS about_only,
               SUM(CASE WHEN science_role = 'both' THEN 1 ELSE 0 END) AS both_local_about,
               SUM(CASE WHEN science_role = 'in_city_rd' THEN 1 ELSE 0 END) AS in_city_rd,
               SUM(cited_by_count) AS total_citations,
               MAX(cited_by_count) AS max_citations
        FROM domain_signals_science
        GROUP BY city_id
        ORDER BY works_n DESC
        """
    ).fetchall()
]
report["science_collab"] = [
    dict(r) for r in conn.execute(
        """
        SELECT ea.canonical_name AS inst_a, ea.primary_city_id AS city_a,
               eb.canonical_name AS inst_b, eb.primary_city_id AS city_b,
               CAST(r.numeric_value AS INTEGER) AS joint_papers
        FROM entity_relations r
        JOIN entities ea ON r.subject_entity_id = ea.entity_id
        JOIN entities eb ON r.object_entity_id = eb.entity_id
        WHERE r.relation_type = 'collaborates_research_with'
        ORDER BY joint_papers DESC
        """
    ).fetchall()
]

# 7. XS 3D Morphology by city & top zones
report["xs_3d_by_city"] = [
    dict(r) for r in conn.execute(
        """
        SELECT city_id, height_source, trust_tier, COUNT(*) AS buildings_n,
               ROUND(SUM(footprint_area_m2)/1e6, 3) AS footprint_km2,
               ROUND(SUM(volume_m3)/1e6, 2) AS volume_mio_m3,
               ROUND(AVG(height_m), 2) AS avg_height_m,
               ROUND(MAX(height_m), 2) AS max_height_m
        FROM xs_buildings_3d
        GROUP BY city_id, height_source, trust_tier
        ORDER BY city_id, buildings_n DESC
        """
    ).fetchall()
]

# 8. NLP -> GIS top resolved zones (Location Dossier test)
report["nlp_gis_top_zones"] = [
    dict(r) for r in conn.execute(
        """
        SELECT city_id, canonical_name, feature_class,
               COUNT(DISTINCT doc_id) AS docs_n,
               SUM(CASE WHEN trust_tier = 'A1' THEN 1 ELSE 0 END) AS tier_a1,
               SUM(CASE WHEN trust_tier = 'B' THEN 1 ELSE 0 END) AS tier_b,
               SUM(CASE WHEN trust_tier = 'C' THEN 1 ELSE 0 END) AS tier_c
        FROM v_geo_location_dossier
        WHERE feature_class != 'city_core'
        GROUP BY city_id, canonical_name, feature_class
        ORDER BY docs_n DESC
        LIMIT 20
        """
    ).fetchall()
]

# 9. World Bank latest remittances & macro comparison (latest available year per country)
wb_p = RAW_W4 / "sensors" / "worldbank_diaspora_macro_3countries.json"
if wb_p.exists():
    wb = json.loads(wb_p.read_text(encoding="utf-8"))
    latest = {}
    for row in wb:
        k = (row["country_iso3"], row["indicator_slug"])
        if k not in latest or row["year"] > latest[k]["year"]:
            latest[k] = row
    report["wb_latest"] = list(latest.values())

# 10. FTS5 & R-Tree live query smoke tests
report["fts5_test_ilidza_pazar"] = conn.execute(
    "SELECT COUNT(*) FROM documents_fts WHERE documents_fts MATCH 'ilidz* OR pazar* OR travnik* OR zagreb* OR beograd*'"
).fetchone()[0]
report["rtree_3d_zagreb_center"] = conn.execute(
    "SELECT COUNT(*) FROM xs_buildings_rtree WHERE max_lon >= 15.965 AND min_lon <= 15.990 AND max_lat >= 45.805 AND min_lat <= 45.818"
).fetchone()[0]

conn.close()
out_p = BASE_DIR / "curated" / "analysis" / "v4_wave4_deep_analytics.json"
out_p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print("DONE Deep Analytics ->", out_p)
print("FK errors:", report["fk_errors"], "| FTS5 hits:", report["fts5_test_ilidza_pazar"], "| ZG Center 3D R-Tree:", report["rtree_3d_zagreb_center"])
print("Elections by city:", json.dumps(report["elections_by_city"], indent=2))
print("Election-Procurement Join:", json.dumps(report["election_procurement_join"][:10], indent=2))
print("Air Winter vs Summer:", json.dumps(report["air_winter_vs_summer"], indent=2))
print("ES-03 DiD:", json.dumps(report["event_study_did"], indent=2))
print("XS 3D:", json.dumps(report["xs_3d_by_city"], indent=2))
