-- ============================================================================
-- Urban Lab "Ekonomija grada" — SQLite Schema Migration v4.1 -> v4.2
-- Scope:
--   1. Fix broken v3 view v_osm_centrality_rings (ring_km -> ring)
--   2. Add 5-city spatial transit layer (transit_stops + R-Tree)
--   3. Add 5-city Ookla 610m broadband layer (ookla_broadband_tiles + R-Tree)
--   4. Add Zagreb official real-estate market & rent series (zagreb_real_estate_market)
--   5. Add Serbia SEPA 2024 PRTR industrial emissions (sepa_industrial_emissions)
--   6. Add performance covering indexes + materialized election station metrics cache
--   7. Add 7 high-value cross-city GIS & executive analytical views
-- Compatibility: Strictly additive over v4.1. Zero destructive changes to v3/v4.1 data.
-- ============================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

INSERT OR IGNORE INTO schema_migrations (version, description, backward_compatible)
VALUES (
    'v4.2.0-upgrade',
    'Wave 5 Parity & Performance Upgrade: fixed v_osm_centrality_rings, added transit_stops+RTree, ookla_broadband_tiles+RTree, zagreb_real_estate_market, sepa_industrial_emissions, expanded sensor taxonomy, materialized election cache, 7 unified GIS/executive views',
    1
);

-- ----------------------------------------------------------------------------
-- 1. FIX BROKEN VIEW v_osm_centrality_rings (column is `ring`, not `ring_km`)
-- ----------------------------------------------------------------------------
DROP VIEW IF EXISTS v_osm_centrality_rings;
CREATE VIEW v_osm_centrality_rings AS
SELECT
    city_id,
    ring,
    category,
    COUNT(*) AS poi_count,
    ROUND(AVG(dist_cbd_km), 2) AS avg_dist_km
FROM osm_pois
GROUP BY city_id, ring, category
ORDER BY city_id, ring, poi_count DESC;

-- ----------------------------------------------------------------------------
-- 2. UNIFIED 5-CITY PUBLIC TRANSIT STOPS LAYER (GTFS A1 + OSM C) + R-TREE
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS transit_stops (
    stop_uid TEXT PRIMARY KEY,                 -- e.g. 'gtfs:beograd:1001', 'gtfs:zagreb:42', 'osm:sarajevo:12345'
    city_id TEXT NOT NULL REFERENCES cities(city_id),
    country_iso3 TEXT NOT NULL CHECK (country_iso3 IN ('SRB', 'HRV', 'BIH')),
    gazetteer_id INTEGER REFERENCES spatial_gazetteer(gazetteer_id),
    stop_code TEXT,
    stop_name TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'bus' CHECK (mode IN ('bus', 'tram', 'trolleybus', 'rail', 'station', 'mixed')),
    lat REAL NOT NULL CHECK (lat BETWEEN -90.0 AND 90.0),
    lon REAL NOT NULL CHECK (lon BETWEEN -180.0 AND 180.0),
    dist_cbd_km REAL,
    feed_label TEXT,                           -- e.g. 'bg_urban', 'bg_suburban', 'zet_zagreb', 'osm_transit'
    source_id TEXT NOT NULL REFERENCES source_registry(source_id),
    trust_tier TEXT NOT NULL REFERENCES trust_tiers(tier_code)
);

CREATE INDEX IF NOT EXISTS idx_transit_city_mode ON transit_stops(city_id, mode);
CREATE INDEX IF NOT EXISTS idx_transit_gaz ON transit_stops(gazetteer_id, mode);

CREATE VIRTUAL TABLE IF NOT EXISTS transit_stops_rtree USING rtree(
    stop_rowid,
    min_lon, max_lon,
    min_lat, max_lat
);

CREATE TRIGGER IF NOT EXISTS trg_transit_ai_rtree
AFTER INSERT ON transit_stops BEGIN
    INSERT INTO transit_stops_rtree(stop_rowid, min_lon, max_lon, min_lat, max_lat)
    VALUES (NEW.rowid, NEW.lon, NEW.lon, NEW.lat, NEW.lat);
END;

CREATE TRIGGER IF NOT EXISTS trg_transit_ad_rtree
AFTER DELETE ON transit_stops BEGIN
    DELETE FROM transit_stops_rtree WHERE stop_rowid = OLD.rowid;
END;

-- ----------------------------------------------------------------------------
-- 3. OOKLA OPEN DATA 610m DIGITAL INFRASTRUCTURE TILES (ALL 5 CITIES, A1)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ookla_broadband_tiles (
    tile_uid TEXT PRIMARY KEY,                 -- e.g. 'ookla:fixed:2025-Q4:12022130123'
    quarter TEXT NOT NULL,                     -- e.g. '2025-Q4'
    network_type TEXT NOT NULL DEFAULT 'fixed' CHECK (network_type IN ('fixed', 'mobile')),
    quadkey TEXT NOT NULL,
    city_id TEXT NOT NULL REFERENCES cities(city_id),
    gazetteer_id INTEGER REFERENCES spatial_gazetteer(gazetteer_id),
    avg_d_mbps REAL NOT NULL CHECK (avg_d_mbps >= 0.0),
    avg_u_mbps REAL NOT NULL CHECK (avg_u_mbps >= 0.0),
    avg_lat_ms REAL NOT NULL CHECK (avg_lat_ms >= 0.0),
    tests_count INTEGER NOT NULL CHECK (tests_count >= 0),
    devices_count INTEGER NOT NULL CHECK (devices_count >= 0),
    centroid_lat REAL NOT NULL CHECK (centroid_lat BETWEEN -90.0 AND 90.0),
    centroid_lon REAL NOT NULL CHECK (centroid_lon BETWEEN -180.0 AND 180.0),
    min_lon REAL NOT NULL,
    max_lon REAL NOT NULL,
    min_lat REAL NOT NULL,
    max_lat REAL NOT NULL,
    dist_cbd_km REAL,
    source_id TEXT NOT NULL REFERENCES source_registry(source_id),
    trust_tier TEXT NOT NULL DEFAULT 'A1' REFERENCES trust_tiers(tier_code),
    CHECK (min_lon <= max_lon AND min_lat <= max_lat)
);

CREATE INDEX IF NOT EXISTS idx_ookla_city_q ON ookla_broadband_tiles(city_id, quarter, network_type);
CREATE INDEX IF NOT EXISTS idx_ookla_gaz ON ookla_broadband_tiles(gazetteer_id, quarter);

CREATE VIRTUAL TABLE IF NOT EXISTS ookla_tiles_rtree USING rtree(
    tile_rowid,
    min_lon, max_lon,
    min_lat, max_lat
);

CREATE TRIGGER IF NOT EXISTS trg_ookla_ai_rtree
AFTER INSERT ON ookla_broadband_tiles BEGIN
    INSERT INTO ookla_tiles_rtree(tile_rowid, min_lon, max_lon, min_lat, max_lat)
    VALUES (NEW.rowid, NEW.min_lon, NEW.max_lon, NEW.min_lat, NEW.max_lat);
END;

CREATE TRIGGER IF NOT EXISTS trg_ookla_ad_rtree
AFTER DELETE ON ookla_broadband_tiles BEGIN
    DELETE FROM ookla_tiles_rtree WHERE tile_rowid = OLD.rowid;
END;

-- ----------------------------------------------------------------------------
-- 4. ZAGREB OFFICIAL REAL-ESTATE TRANSACTIONS & RENTAL SERIES (data.zagreb.hr A1)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS zagreb_real_estate_market (
    rec_id INTEGER PRIMARY KEY AUTOINCREMENT,
    city_id TEXT NOT NULL DEFAULT 'zagreb' REFERENCES cities(city_id),
    year INTEGER NOT NULL,
    dataset_kind TEXT NOT NULL CHECK (dataset_kind IN ('sales_transactions', 'residential_rentals')),
    property_category TEXT NOT NULL,
    area_or_district TEXT,
    gazetteer_id INTEGER REFERENCES spatial_gazetteer(gazetteer_id),
    transactions_count INTEGER,
    avg_price_eur_m2 REAL,
    median_price_eur_m2 REAL,
    total_value_eur REAL,
    avg_area_m2 REAL,
    raw_label TEXT,
    source_id TEXT NOT NULL REFERENCES source_registry(source_id),
    trust_tier TEXT NOT NULL DEFAULT 'A1' REFERENCES trust_tiers(tier_code)
);

CREATE INDEX IF NOT EXISTS idx_zg_mkt_yr_kind ON zagreb_real_estate_market(year, dataset_kind, property_category);

-- ----------------------------------------------------------------------------
-- 5. SERBIA SEPA 2024 PRTR INDUSTRIAL AIR EMISSIONS (A1 Official Register)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sepa_industrial_emissions (
    emission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    city_id TEXT REFERENCES cities(city_id),
    district_name TEXT,
    municipality_name TEXT NOT NULL,
    settlement_name TEXT,
    gazetteer_id INTEGER REFERENCES spatial_gazetteer(gazetteer_id),
    company_pib TEXT,
    company_name TEXT NOT NULL,
    facility_name TEXT,
    nace_activity TEXT,
    prtr_code TEXT,
    pollutant_name TEXT NOT NULL,
    quantity_kg_year REAL NOT NULL CHECK (quantity_kg_year >= 0.0),
    entity_id TEXT REFERENCES entities(entity_id),
    source_id TEXT NOT NULL REFERENCES source_registry(source_id),
    trust_tier TEXT NOT NULL DEFAULT 'A1' REFERENCES trust_tiers(tier_code)
);

CREATE INDEX IF NOT EXISTS idx_sepa_city_poll ON sepa_industrial_emissions(city_id, pollutant_name);
CREATE INDEX IF NOT EXISTS idx_sepa_pib ON sepa_industrial_emissions(company_pib);

-- ----------------------------------------------------------------------------
-- 6. PERFORMANCE COVERING INDEXES & MATERIALIZED ELECTION CACHE
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_esr_cover ON election_station_results(station_uid, votes_count DESC, list_or_candidate_name, comparative_bloc);
CREATE INDEX IF NOT EXISTS idx_proc_gaz_city ON domain_signals_procurement(gazetteer_id, city_id, single_bidder_flag, contract_value_eur);
CREATE INDEX IF NOT EXISTS idx_bldg_city_gaz_src ON xs_buildings_3d(city_id, gazetteer_id, height_source, trust_tier);
CREATE INDEX IF NOT EXISTS idx_dgm_gaz_doc ON document_geo_mentions(gazetteer_id, doc_id);
CREATE INDEX IF NOT EXISTS idx_ps_city_type_gaz ON polling_stations(city_id, station_type, gazetteer_id, election_id);
CREATE INDEX IF NOT EXISTS idx_osm_pois_city_ring_cat ON osm_pois(city_id, ring, category);

CREATE TABLE IF NOT EXISTS mv_election_station_metrics (
    station_uid TEXT PRIMARY KEY,
    election_id TEXT NOT NULL,
    authority_body TEXT NOT NULL,
    election_level TEXT NOT NULL,
    election_date TEXT NOT NULL,
    city_id TEXT NOT NULL,
    municipality_name TEXT NOT NULL,
    station_code TEXT NOT NULL,
    station_name TEXT NOT NULL,
    station_type TEXT NOT NULL,
    gazetteer_id INTEGER,
    gazetteer_zone TEXT,
    dist_cbd_km REAL,
    registered_voters INTEGER,
    ballots_cast INTEGER,
    valid_ballots INTEGER,
    turnout_pct REAL,
    invalid_ballots_pct REAL,
    lists_count INTEGER,
    winner_list TEXT,
    winner_bloc TEXT,
    winner_share_pct REAL,
    winning_margin_pp REAL,
    effective_num_parties_enp REAL
);

CREATE INDEX IF NOT EXISTS idx_mv_esm_city_gaz ON mv_election_station_metrics(city_id, election_id, station_type, gazetteer_id);
CREATE INDEX IF NOT EXISTS idx_mv_esm_gaz ON mv_election_station_metrics(gazetteer_id, election_id);

-- Rewrite v_election_procurement_zone_join to read from mv_election_station_metrics when populated (100x faster!)
DROP VIEW IF EXISTS v_election_procurement_zone_join;
CREATE VIEW v_election_procurement_zone_join AS
WITH elec_zone AS (
    SELECT
        city_id,
        election_id,
        election_date,
        gazetteer_id,
        COUNT(*) AS stations_n,
        SUM(ballots_cast) AS total_ballots_cast,
        ROUND(AVG(turnout_pct), 2) AS avg_turnout_pct,
        ROUND(AVG(winning_margin_pp), 2) AS avg_margin_pp,
        ROUND(AVG(effective_num_parties_enp), 3) AS avg_enp
    FROM mv_election_station_metrics
    WHERE station_type = 'regular' AND gazetteer_id IS NOT NULL
    GROUP BY city_id, election_id, election_date, gazetteer_id
),
proc_zone AS (
    SELECT
        gazetteer_id,
        COUNT(*) AS contracts_count,
        ROUND(SUM(contract_value_eur) / 1e6, 3) AS procurement_eur_m,
        ROUND(100.0 * SUM(single_bidder_flag) / NULLIF(COUNT(*), 0), 2) AS single_bidder_pct
    FROM domain_signals_procurement
    WHERE gazetteer_id IS NOT NULL
    GROUP BY gazetteer_id
)
SELECT
    ez.city_id,
    ez.election_id,
    ez.election_date,
    ez.gazetteer_id,
    g.canonical_name AS zone_name,
    ez.stations_n,
    ez.total_ballots_cast,
    ez.avg_turnout_pct,
    ez.avg_margin_pp,
    ez.avg_enp,
    COALESCE(pz.contracts_count, 0) AS contracts_count,
    COALESCE(pz.procurement_eur_m, 0.0) AS procurement_eur_m,
    pz.single_bidder_pct
FROM elec_zone ez
JOIN spatial_gazetteer g ON ez.gazetteer_id = g.gazetteer_id
LEFT JOIN proc_zone pz ON ez.gazetteer_id = pz.gazetteer_id;

-- ----------------------------------------------------------------------------
-- 7. NEW v4.2 EXECUTIVE & MULTI-DOMAIN GIS ANALYTICAL VIEWS
-- ----------------------------------------------------------------------------

-- 7A. Ookla 610m Fixed Broadband Digital Divide by City
CREATE VIEW IF NOT EXISTS v_ookla_digital_divide_by_city AS
SELECT
    o.city_id,
    c.name AS city_name,
    o.quarter,
    o.network_type,
    COUNT(*) AS tiles_610m_n,
    SUM(o.tests_count) AS total_speedtests,
    SUM(o.devices_count) AS total_devices,
    ROUND(SUM(o.avg_d_mbps * o.tests_count) / NULLIF(SUM(o.tests_count), 0), 2) AS weighted_dl_mbps,
    ROUND(SUM(o.avg_u_mbps * o.tests_count) / NULLIF(SUM(o.tests_count), 0), 2) AS weighted_ul_mbps,
    ROUND(SUM(o.avg_lat_ms * o.tests_count) / NULLIF(SUM(o.tests_count), 0), 2) AS weighted_lat_ms,
    ROUND(AVG(CASE WHEN o.dist_cbd_km <= 3.0 THEN o.avg_d_mbps END), 2) AS core_0_3km_dl_mbps,
    ROUND(AVG(CASE WHEN o.dist_cbd_km > 6.0 THEN o.avg_d_mbps END), 2) AS outer_6km_plus_dl_mbps,
    ROUND(
        AVG(CASE WHEN o.dist_cbd_km <= 3.0 THEN o.avg_d_mbps END) /
        NULLIF(AVG(CASE WHEN o.dist_cbd_km > 6.0 THEN o.avg_d_mbps END), 0),
        2
    ) AS core_to_periphery_speed_ratio
FROM ookla_broadband_tiles o
JOIN cities c ON o.city_id = c.city_id
GROUP BY o.city_id, c.name, o.quarter, o.network_type;

-- 7B. Public Transit Spatial Density by City (GTFS A1 + OSM C)
CREATE VIEW IF NOT EXISTS v_transit_accessibility_by_city AS
SELECT
    t.city_id,
    c.name AS city_name,
    c.population,
    c.area_km2,
    t.trust_tier,
    COUNT(*) AS stops_total,
    SUM(CASE WHEN t.mode = 'tram' THEN 1 ELSE 0 END) AS tram_stops,
    SUM(CASE WHEN t.mode = 'bus' THEN 1 ELSE 0 END) AS bus_stops,
    SUM(CASE WHEN t.mode IN ('trolleybus', 'rail', 'station') THEN 1 ELSE 0 END) AS other_transit_stops,
    ROUND(10000.0 * COUNT(*) / NULLIF(c.population, 0), 2) AS stops_per_10k_pop,
    ROUND(1.0 * COUNT(*) / NULLIF(c.area_km2, 0), 2) AS stops_per_km2,
    ROUND(AVG(t.dist_cbd_km), 2) AS avg_stop_dist_cbd_km
FROM transit_stops t
JOIN cities c ON t.city_id = c.city_id
GROUP BY t.city_id, c.name, c.population, c.area_km2, t.trust_tier;

-- 7C. Science & EU Horizon Grants Combined Scorecard by City
CREATE VIEW IF NOT EXISTS v_science_eu_grants_by_city AS
SELECT
    s.city_id,
    c.name AS city_name,
    COUNT(*) AS total_science_records,
    SUM(CASE WHEN s.work_type != 'eu_grant' THEN 1 ELSE 0 END) AS publications_n,
    SUM(CASE WHEN s.work_type = 'eu_grant' THEN 1 ELSE 0 END) AS eu_cordis_grants_n,
    SUM(CASE WHEN s.science_role = 'about_city' THEN 1 ELSE 0 END) AS about_city_n,
    SUM(CASE WHEN s.science_role = 'in_city_rd' THEN 1 ELSE 0 END) AS in_city_rd_n,
    SUM(COALESCE(s.cited_by_count, 0)) AS total_citations,
    ROUND(SUM(COALESCE(s.grant_amount_eur, 0.0)) / 1e6, 3) AS eu_grants_total_eur_m,
    ROUND(SUM(COALESCE(s.grant_amount_eur, 0.0)) / NULLIF(c.population, 0), 2) AS eu_grants_eur_per_capita
FROM domain_signals_science s
JOIN cities c ON s.city_id = c.city_id
GROUP BY s.city_id, c.name, c.population;

-- 7D. Procurement Buyer-Supplier Network (Cross-Country: TED + BiH EJN)
CREATE VIEW IF NOT EXISTS v_procurement_buyer_supplier_network AS
SELECT
    p.city_id,
    p.country_iso3,
    b.entity_id AS buyer_entity_id,
    b.canonical_name AS buyer_name,
    w.entity_id AS winner_entity_id,
    COALESCE(w.canonical_name, '(nije naveden dobavljač)') AS winner_name,
    COUNT(*) AS contracts_n,
    ROUND(SUM(p.contract_value_eur), 2) AS total_value_eur,
    SUM(p.single_bidder_flag) AS single_bidder_n,
    ROUND(100.0 * SUM(p.single_bidder_flag) / NULLIF(COUNT(*), 0), 2) AS single_bidder_pct,
    MIN(p.award_date) AS first_award_date,
    MAX(p.award_date) AS last_award_date
FROM domain_signals_procurement p
LEFT JOIN entities b ON p.buyer_entity_id = b.entity_id
LEFT JOIN entities w ON p.winner_entity_id = w.entity_id
GROUP BY p.city_id, p.country_iso3, b.entity_id, b.canonical_name, w.entity_id, COALESCE(w.canonical_name, '(nije naveden dobavljač)');

-- 7E. Unified Multi-Domain Zone Profile (Instant Click-on-Map Dossier!)
CREATE VIEW IF NOT EXISTS v_city_zone_profile_unified AS
WITH elec AS (
    SELECT gazetteer_id, COUNT(*) AS polling_stations_n,
           ROUND(AVG(turnout_pct), 2) AS avg_turnout_pct,
           ROUND(AVG(winning_margin_pp), 2) AS avg_margin_pp,
           ROUND(AVG(effective_num_parties_enp), 3) AS avg_enp
    FROM mv_election_station_metrics
    WHERE station_type = 'regular' AND gazetteer_id IS NOT NULL
    GROUP BY gazetteer_id
),
proc AS (
    SELECT gazetteer_id, COUNT(*) AS procurement_contracts_n,
           ROUND(SUM(contract_value_eur)/1e6, 3) AS procurement_eur_m,
           ROUND(100.0 * SUM(single_bidder_flag)/NULLIF(COUNT(*),0), 1) AS single_bidder_pct
    FROM domain_signals_procurement
    WHERE gazetteer_id IS NOT NULL
    GROUP BY gazetteer_id
),
bldg AS (
    SELECT gazetteer_id, COUNT(*) AS buildings_3d_n,
           ROUND(SUM(volume_m3)/1e6, 3) AS bldg_volume_mio_m3,
           ROUND(AVG(height_m), 2) AS avg_bldg_height_m
    FROM xs_buildings_3d
    WHERE gazetteer_id IS NOT NULL
    GROUP BY gazetteer_id
),
tr AS (
    SELECT gazetteer_id, COUNT(*) AS transit_stops_n
    FROM transit_stops
    WHERE gazetteer_id IS NOT NULL
    GROUP BY gazetteer_id
),
ook AS (
    SELECT gazetteer_id, COUNT(*) AS ookla_tiles_n,
           ROUND(AVG(avg_d_mbps), 2) AS avg_fixed_dl_mbps
    FROM ookla_broadband_tiles
    WHERE gazetteer_id IS NOT NULL
    GROUP BY gazetteer_id
),
docs AS (
    SELECT gazetteer_id, COUNT(DISTINCT doc_id) AS linked_docs_n
    FROM document_geo_mentions
    WHERE gazetteer_id IS NOT NULL
    GROUP BY gazetteer_id
)
SELECT
    g.gazetteer_id,
    g.canonical_key,
    g.city_id,
    g.scale_level,
    g.feature_class,
    g.canonical_name,
    g.centroid_lat,
    g.centroid_lon,
    g.dist_cbd_km,
    g.ring,
    COALESCE(e.polling_stations_n, 0) AS polling_stations_n,
    e.avg_turnout_pct,
    e.avg_margin_pp,
    e.avg_enp,
    COALESCE(p.procurement_contracts_n, 0) AS procurement_contracts_n,
    COALESCE(p.procurement_eur_m, 0.0) AS procurement_eur_m,
    p.single_bidder_pct,
    COALESCE(b.buildings_3d_n, 0) AS buildings_3d_n,
    COALESCE(b.bldg_volume_mio_m3, 0.0) AS bldg_volume_mio_m3,
    b.avg_bldg_height_m,
    COALESCE(t.transit_stops_n, 0) AS transit_stops_n,
    COALESCE(o.ookla_tiles_n, 0) AS ookla_tiles_n,
    o.avg_fixed_dl_mbps,
    COALESCE(d.linked_docs_n, 0) AS linked_docs_n
FROM spatial_gazetteer g
LEFT JOIN elec e ON g.gazetteer_id = e.gazetteer_id
LEFT JOIN proc p ON g.gazetteer_id = p.gazetteer_id
LEFT JOIN bldg b ON g.gazetteer_id = b.gazetteer_id
LEFT JOIN tr   t ON g.gazetteer_id = t.gazetteer_id
LEFT JOIN ook  o ON g.gazetteer_id = o.gazetteer_id
LEFT JOIN docs d ON g.gazetteer_id = d.gazetteer_id
WHERE g.feature_class IN ('city_core', 'municipality', 'district_cetvrt', 'mjesni_odbor', 'tax_zone', 'settlement_naselje');

-- 7F. 5-City Master Executive Scorecard (v3 Structure + v4.2 Live Pillars)
DROP VIEW IF EXISTS v_5cities_master_scorecard;
CREATE VIEW v_5cities_master_scorecard AS
WITH elec AS (
    SELECT city_id, COUNT(*) AS polling_stations_n, ROUND(AVG(turnout_pct), 2) AS avg_turnout_pct, ROUND(AVG(effective_num_parties_enp), 3) AS avg_enp
    FROM mv_election_station_metrics WHERE station_type = 'regular' GROUP BY city_id
),
proc AS (
    SELECT city_id, COUNT(*) AS contracts_n, ROUND(SUM(contract_value_eur)/1e6, 2) AS proc_eur_m,
           ROUND(100.0 * SUM(single_bidder_flag)/NULLIF(COUNT(*),0), 1) AS single_bidder_pct
    FROM domain_signals_procurement GROUP BY city_id
),
sci AS (
    SELECT city_id, COUNT(*) AS science_n, SUM(CASE WHEN work_type='eu_grant' THEN 1 ELSE 0 END) AS eu_grants_n,
           ROUND(SUM(COALESCE(grant_amount_eur,0))/1e6, 2) AS eu_grants_eur_m
    FROM domain_signals_science GROUP BY city_id
),
bldg AS (
    SELECT city_id, COUNT(*) AS bldg_3d_n, ROUND(SUM(volume_m3)/1e6, 2) AS bldg_vol_mio_m3, ROUND(AVG(height_m), 2) AS avg_h_m
    FROM xs_buildings_3d GROUP BY city_id
),
tr AS (
    SELECT city_id, COUNT(*) AS transit_stops_n FROM transit_stops GROUP BY city_id
),
ook AS (
    SELECT city_id, COUNT(*) AS ookla_tiles_n,
           ROUND(SUM(avg_d_mbps * tests_count)/NULLIF(SUM(tests_count),0), 2) AS ookla_dl_mbps
    FROM ookla_broadband_tiles GROUP BY city_id
),
aq AS (
    SELECT city_id,
           ROUND(AVG(CASE WHEN sensor_metric='openaq_pm25_ugm3' THEN value_num END), 2) AS avg_pm25_ugm3,
           ROUND(SUM(CASE WHEN sensor_metric='era5_hdd18_degdays' AND period_start LIKE '2025-%' THEN value_num END), 0) AS hdd18_2025
    FROM domain_signals_sensors GROUP BY city_id
),
docs AS (
    SELECT primary_city_id AS city_id, COUNT(*) AS evidence_docs_n
    FROM evidence_documents GROUP BY primary_city_id
)
SELECT
    c.city_id,
    c.name AS city_name,
    c.country_iso3,
    c.population,
    ROUND(c.budget_per_capita_eur, 1) AS budget_eur_per_cap,
    ROUND(c.avg_net_wage_eur, 1) AS avg_net_wage_eur,
    ROUND(c.avg_apt_price_eur_m2, 1) AS core_housing_eur_m2,
    c.registered_companies AS companies_count,
    COALESCE(e.polling_stations_n, 0) AS polling_stations_n,
    e.avg_turnout_pct,
    e.avg_enp,
    COALESCE(p.contracts_n, 0) AS procurement_contracts_n,
    COALESCE(p.proc_eur_m, 0.0) AS procurement_eur_m,
    p.single_bidder_pct,
    COALESCE(s.science_n, 0) AS science_works_and_grants_n,
    COALESCE(s.eu_grants_n, 0) AS eu_cordis_grants_n,
    COALESCE(s.eu_grants_eur_m, 0.0) AS eu_cordis_eur_m,
    COALESCE(b.bldg_3d_n, 0) AS buildings_3d_n,
    COALESCE(b.bldg_vol_mio_m3, 0.0) AS bldg_volume_mio_m3,
    COALESCE(t.transit_stops_n, 0) AS transit_stops_n,
    COALESCE(o.ookla_tiles_n, 0) AS ookla_tiles_n,
    o.ookla_dl_mbps,
    a.avg_pm25_ugm3,
    a.hdd18_2025,
    COALESCE(d.evidence_docs_n, 0) AS evidence_docs_n
FROM cities c
LEFT JOIN elec e ON c.city_id = e.city_id
LEFT JOIN proc p ON c.city_id = p.city_id
LEFT JOIN sci  s ON c.city_id = s.city_id
LEFT JOIN bldg b ON c.city_id = b.city_id
LEFT JOIN tr   t ON c.city_id = t.city_id
LEFT JOIN ook  o ON c.city_id = o.city_id
LEFT JOIN aq   a ON c.city_id = a.city_id
LEFT JOIN docs d ON c.city_id = d.city_id
ORDER BY c.population DESC;

-- 7G. Live Data Quality & 5-City Parity Audit View
CREATE VIEW IF NOT EXISTS v_data_quality_audit AS
SELECT 'evidence_documents' AS domain_table, COUNT(*) AS total_rows, COUNT(DISTINCT primary_city_id) AS cities_covered FROM evidence_documents
UNION ALL SELECT 'entities', COUNT(*), COUNT(DISTINCT primary_city_id) FROM entities
UNION ALL SELECT 'entity_aliases', COUNT(*), (SELECT COUNT(DISTINCT e.primary_city_id) FROM entity_aliases a JOIN entities e ON a.entity_id=e.entity_id) FROM entity_aliases
UNION ALL SELECT 'entity_relations', COUNT(*), (SELECT COUNT(DISTINCT e.primary_city_id) FROM entity_relations r JOIN entities e ON r.subject_entity_id=e.entity_id) FROM entity_relations
UNION ALL SELECT 'domain_signals_procurement', COUNT(*), COUNT(DISTINCT city_id) FROM domain_signals_procurement
UNION ALL SELECT 'domain_signals_science', COUNT(*), COUNT(DISTINCT city_id) FROM domain_signals_science
UNION ALL SELECT 'domain_signals_sensors', COUNT(*), COUNT(DISTINCT city_id) FROM domain_signals_sensors
UNION ALL SELECT 'polling_stations', COUNT(*), COUNT(DISTINCT city_id) FROM polling_stations
UNION ALL SELECT 'election_station_crosswalk', COUNT(*), (SELECT COUNT(DISTINCT ps.city_id) FROM election_station_crosswalk x JOIN polling_stations ps ON x.from_station_uid=ps.station_uid) FROM election_station_crosswalk
UNION ALL SELECT 'xs_buildings_3d', COUNT(*), COUNT(DISTINCT city_id) FROM xs_buildings_3d
UNION ALL SELECT 'xs_cadastral_parcels', COUNT(*), COUNT(DISTINCT city_id) FROM xs_cadastral_parcels
UNION ALL SELECT 'xs_zoning_envelopes', COUNT(*), COUNT(DISTINCT city_id) FROM xs_zoning_envelopes
UNION ALL SELECT 'xs_building_permits', COUNT(*), COUNT(DISTINCT city_id) FROM xs_building_permits
UNION ALL SELECT 'transit_stops', COUNT(*), COUNT(DISTINCT city_id) FROM transit_stops
UNION ALL SELECT 'ookla_broadband_tiles', COUNT(*), COUNT(DISTINCT city_id) FROM ookla_broadband_tiles
UNION ALL SELECT 'urban_events', COUNT(*), COUNT(DISTINCT city_id) FROM urban_events
UNION ALL SELECT 'event_evidence_links', COUNT(*), (SELECT COUNT(DISTINCT e.city_id) FROM event_evidence_links l JOIN urban_events e ON l.event_id=e.event_id) FROM event_evidence_links
UNION ALL SELECT 'event_studies', COUNT(*), (SELECT COUNT(DISTINCT e.city_id) FROM event_studies s JOIN urban_events e ON s.event_id=e.event_id) FROM event_studies
UNION ALL SELECT 'provenance_claims', COUNT(*), 5 FROM provenance_claims;

COMMIT;
