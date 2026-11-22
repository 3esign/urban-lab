-- ============================================================================
-- Urban Lab "Ekonomija grada" — SQLite Schema Migration v3 -> v4
-- Scope: Trust-Tier & Provenance, Cross-Jurisdiction Entities, Local Gazetteer
--        (FTS5 + R-Tree), NLP->GIS Geo-Mentions, Domain Signals, Canonical
--        Urban Events, and Event-Study (t0 / DiD) Causal Panel.
-- Target: SQLite 3.35+ (verified on SQLite 3.53.1 with FTS5, RTREE, JSON1)
-- Compatibility: Strictly additive over urban_lab_5cities.sqlite (v3).
--                Zero destructive changes to v3 tables or views.
-- ============================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- ----------------------------------------------------------------------------
-- 0. SCHEMA VERSIONING & GOVERNANCE METADATA
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    description TEXT NOT NULL,
    backward_compatible INTEGER NOT NULL DEFAULT 1 CHECK (backward_compatible IN (0, 1))
);

INSERT OR IGNORE INTO schema_migrations (version, description, backward_compatible)
VALUES
(
    'v4.0.0-design',
    'Trust-Tier A1/A2/B/C/D, Cross-Jurisdiction Entity Graph, Multi-Scale Gazetteer (FTS5+RTree), NLP->GIS Mentions, Domain Signals, Canonical Events, Event-Study t0/DiD Panel',
    1
),
(
    'v4.1.0-design',
    'Electoral Geography by Polling Station (RIK/DIP/CIK + ENP/Crosswalk) & 3D/Parcel XS Layer (Cadastre, GUP/PDR/ISPU Zoning Envelopes, 3D Buildings + R-Tree, Permits, Development Rent Gap)',
    1
);

-- ----------------------------------------------------------------------------
-- 1. TRUST-TIER TAXONOMY & SOURCE REGISTRY (Epistemic Governance)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trust_tiers (
    tier_code TEXT PRIMARY KEY CHECK (tier_code IN ('A1', 'A2', 'B', 'C', 'D')),
    tier_rank INTEGER NOT NULL UNIQUE CHECK (tier_rank BETWEEN 1 AND 5),
    label_sr TEXT NOT NULL,
    label_en TEXT NOT NULL,
    ui_visual_style TEXT NOT NULL,
    default_map_opacity REAL NOT NULL CHECK (default_map_opacity > 0.0 AND default_map_opacity <= 1.0),
    allows_causal_baseline INTEGER NOT NULL CHECK (allows_causal_baseline IN (0, 1)),
    requires_upstream_evidence INTEGER NOT NULL CHECK (requires_upstream_evidence IN (0, 1)),
    description TEXT NOT NULL
);

INSERT OR REPLACE INTO trust_tiers VALUES
('A1', 1, 'Primarni registar / zakon / fizički senzor', 'Primary Official Register, Law or Physical Sensor',
 'solid_fill_crisp_border', 0.90, 1, 0,
 'Direktni mašinski API zvaničnog registra, zakonski akt u Službenom listu ili kalibrisani fizički/satelitski senzor (APR, open.ejn.gov.ba, ISPU, Fiskalizacija RH, VIIRS, OpenAQ, Ookla, GTFS).'),
('A2', 2, 'Zvanična statistika / publikovani izveštaj', 'Official Statistical Publication or Curated Report',
 'solid_fill_soft_border', 0.85, 1, 0,
 'Zvanični statistički godišnjaci, popisi i budžetski PDF/XLS izveštaji (RZS, DZS, FZS, Eurostat, World Bank, NBS/HNB/CBBiH) sa vremenskim kašnjenjem ili agregacijom.'),
('B',  3, 'Recenzirana nauka / dokumentovana istraga', 'Peer-Reviewed Science or Documented Investigation',
 'hatched_fill_accent_border', 0.75, 1, 0,
 'Recenzirani naučni radovi, disertacije, EU/WBIF projektne studije i istraživačke baze zasnovane na primarnim dokumentima (OpenAlex, CORDIS, NaRDuS, CroRIS, CIN, KRIK, GONG, OCCRP Aleph).'),
('C',  4, 'Medijski puls / oglasi / crowdsourcing', 'Media Signal, Listings, Sentiment or Crowdsourcing',
 'translucent_pulse_or_heatmap', 0.55, 0, 0,
 'Vesti, najave investicija, sentiment, oglasnici i građanski signali (GDELT, ACLED, Media Cloud, eKapija, lokalni RSS portali, oglasnici). Vodeći signal, ne konačan dokaz.'),
('D',  5, 'Izvedeni model / LLM ekstrakcija / simulacija', 'Derived Model, LLM Inference or What-If Projection',
 'dashed_outline_projected', 0.50, 0, 1,
 'Ekonomski modeli, NLP/LLM klasifikacije, imputacije i šta-ako simulacije. Uvek nasleđuju najniži trust_tier ulaznih podataka i zahtevaju eksplicitnu vezu ka uzvodnim izvorima.');

CREATE TABLE IF NOT EXISTS source_registry (
    source_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    domain_axis TEXT NOT NULL CHECK (domain_axis IN (
        'structure_v3', 'politics_procurement', 'politics_planning', 'politics_elections',
        'politics_subsidies', 'politics_ownership', 'news_global', 'news_regional',
        'news_hyperlocal', 'news_investigative', 'science_about_city', 'science_in_city',
        'sensor_satellite', 'sensor_environment', 'sensor_digital_mobility',
        'market_realtime', 'financial_stress', 'diaspora_social', 'spatial_cadastre_3d'
    )),
    default_trust_tier TEXT NOT NULL REFERENCES trust_tiers(tier_code),
    jurisdiction_scope TEXT NOT NULL,          -- 'ALL_5', 'SRB', 'HRV', 'BIH', 'BG', 'ZG', 'SA', 'NP', 'TR'
    coverage_class TEXT NOT NULL CHECK (coverage_class IN ('universal_5cities', 'champion_city_module', 'national_macro')),
    access_method TEXT NOT NULL CHECK (access_method IN ('rest_api', 'odata_api', 'oai_pmh', 'bulk_csv_zip', 'rss_atom', 'html_portal', 'pdf_gazette', 'raster_tile', 'manual_curated')),
    cadence TEXT NOT NULL CHECK (cadence IN ('realtime_15m', 'daily', 'weekly', 'monthly', 'quarterly', 'annual', 'event_driven', 'static')),
    base_url TEXT NOT NULL,
    license_or_terms TEXT,
    pii_risk_level TEXT NOT NULL DEFAULT 'low' CHECK (pii_risk_level IN ('none', 'low', 'medium_public_officials', 'high_restricted')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    notes TEXT
);

-- ----------------------------------------------------------------------------
-- 2. CROSS-JURISDICTION ENTITY GRAPH & RESOLUTION
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY,                -- stable URN, e.g. 'ent:company:srb:07022471' or 'ent:inst:openalex:I4068193'
    entity_type TEXT NOT NULL CHECK (entity_type IN (
        'company', 'public_institution', 'municipality_authority', 'university_rd',
        'person_public_role', 'ngo_thinktank', 'media_outlet',
        'infrastructure_project', 'political_party', 'spatial_zone'
    )),
    canonical_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,             -- lowercased, Latin-transliterated, diacritics folded, legal suffix stripped
    country_iso3 TEXT CHECK (country_iso3 IN ('SRB', 'HRV', 'BIH', 'EU', 'INT', NULL)),
    primary_city_id TEXT REFERENCES cities(city_id),
    nace_code TEXT,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'bankrupt', 'blocked', 'dissolved', 'planned', 'unknown')),
    trust_tier TEXT NOT NULL REFERENCES trust_tiers(tier_code),
    public_interest_basis TEXT,                -- REQUIRED if entity_type='person_public_role' (legal hygiene guard)
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (entity_type != 'person_public_role' OR (public_interest_basis IS NOT NULL AND length(trim(public_interest_basis)) >= 8))
);

CREATE INDEX IF NOT EXISTS idx_entities_type_city ON entities(entity_type, primary_city_id);
CREATE INDEX IF NOT EXISTS idx_entities_norm_name ON entities(normalized_name, country_iso3);

CREATE TABLE IF NOT EXISTS entity_identifiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    id_scheme TEXT NOT NULL CHECK (id_scheme IN (
        'srb_mb', 'srb_pib', 'hrv_oib', 'hrv_mbs', 'bih_jib', 'bih_mbs',
        'ejn_org_id', 'ujn_org_id', 'eojn_org_id',
        'openalex_inst_id', 'ror_id', 'orcid', 'cordis_org_id',
        'wikidata_qid', 'lei', 'aleph_entity_id', 'osm_id',
        'rik_list_id', 'dip_list_id', 'cik_party_id',
        'v3_xl_corridor_id', 'v3_hinterland_unit_id'
    )),
    id_value TEXT NOT NULL,
    country_iso3 TEXT NOT NULL DEFAULT 'INT',
    match_method TEXT NOT NULL DEFAULT 'deterministic_registry' CHECK (match_method IN (
        'deterministic_registry', 'crosswalk_table', 'fuzzy_trigram', 'llm_verified', 'human_verified'
    )),
    match_confidence REAL NOT NULL DEFAULT 1.0 CHECK (match_confidence > 0.0 AND match_confidence <= 1.0),
    review_status TEXT NOT NULL DEFAULT 'auto_accepted' CHECK (review_status IN ('auto_accepted', 'needs_review', 'human_verified', 'rejected')),
    source_id TEXT REFERENCES source_registry(source_id),
    UNIQUE (id_scheme, country_iso3, id_value)
);

CREATE INDEX IF NOT EXISTS idx_ent_id_entity ON entity_identifiers(entity_id);
CREATE INDEX IF NOT EXISTS idx_ent_id_lookup ON entity_identifiers(id_scheme, id_value);

CREATE TABLE IF NOT EXISTS entity_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    alias_text TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    script TEXT DEFAULT 'latin' CHECK (script IN ('latin', 'cyrillic', 'mixed', 'acronym')),
    lang TEXT DEFAULT 'sr-hr-bs',
    is_official INTEGER NOT NULL DEFAULT 0 CHECK (is_official IN (0, 1)),
    UNIQUE (entity_id, normalized_alias)
);

CREATE INDEX IF NOT EXISTS idx_ent_alias_norm ON entity_aliases(normalized_alias);

CREATE TABLE IF NOT EXISTS entity_relations (
    relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_entity_id TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL CHECK (relation_type IN (
        'awarded_contract_to', 'bid_on_tender_of', 'subsidized_by', 'owns_share_of',
        'controls_or_manages', 'holds_public_office_in', 'regulates_plan_for',
        'collaborates_research_with', 'located_in_zone', 'financed_project',
        'account_blocked_at', 'bankruptcy_case_of', 'affiliated_with'
    )),
    object_entity_id TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    numeric_value REAL,                        -- e.g. contract EUR, ownership %, grant EUR
    numeric_unit TEXT,                         -- 'EUR', 'PCT', 'SHARES', 'COUNT'
    valid_from TEXT,                           -- ISO date YYYY-MM-DD
    valid_to TEXT,                             -- NULL = ongoing / unknown end
    trust_tier TEXT NOT NULL REFERENCES trust_tiers(tier_code),
    epistemic_status TEXT NOT NULL DEFAULT 'factual_record' CHECK (epistemic_status IN (
        'factual_record', 'structural_indicator', 'reported_claim', 'inferred_link'
    )),
    evidence_doc_id TEXT,                      -- FK added conceptually to evidence_documents(doc_id)
    primary_url TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    notes TEXT,
    CHECK (subject_entity_id != object_entity_id)
);

CREATE INDEX IF NOT EXISTS idx_ent_rel_subj ON entity_relations(subject_entity_id, relation_type);
CREATE INDEX IF NOT EXISTS idx_ent_rel_obj ON entity_relations(object_entity_id, relation_type);
CREATE INDEX IF NOT EXISTS idx_ent_rel_dates ON entity_relations(valid_from, valid_to);

-- ----------------------------------------------------------------------------
-- 3. LOCAL MULTI-SCALE GAZETTEER (Bootstrapped from v3 + FTS5 + R-Tree)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS spatial_gazetteer (
    gazetteer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_key TEXT NOT NULL UNIQUE,        -- e.g. 'city:beograd', 'admin:beograd:70254', 'taxzone:novi_pazar:I_zona'
    city_id TEXT REFERENCES cities(city_id),   -- NULL allowed for multi-city XL corridors or national units
    country_iso3 TEXT NOT NULL CHECK (country_iso3 IN ('SRB', 'HRV', 'BIH', 'INT')),
    scale_level TEXT NOT NULL CHECK (scale_level IN ('XS', 'S', 'M', 'L', 'XL')),
    feature_class TEXT NOT NULL CHECK (feature_class IN (
        'city_core', 'municipality', 'district_cetvrt', 'mjesni_odbor', 'settlement_naselje',
        'tax_zone', 'hinterland_unit', 'industrial_zone', 'commercial_zone', 'landuse_polygon',
        'transport_hub', 'market', 'university_campus', 'street_corridor', 'polling_station',
        'cadastral_municipality', 'planning_block', 'corridor_xl', 'poi_landmark'
    )),
    canonical_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,             -- folded Latin lowercase
    parent_gazetteer_id INTEGER REFERENCES spatial_gazetteer(gazetteer_id),
    -- Anchors back to v3 tables (nullable, depending on origin)
    v3_source_table TEXT,                      -- 'cities', 'admin_units', 'hinterland_units', 'property_tax_zones_gis_summary', 'osm_landuse_major_zones', 'osm_pois', 'xl_corridors_projects_strategies'
    v3_source_pk TEXT,
    -- Geometry summary (WGS84 EPSG:4326)
    centroid_lat REAL NOT NULL CHECK (centroid_lat BETWEEN -90.0 AND 90.0),
    centroid_lon REAL NOT NULL CHECK (centroid_lon BETWEEN -180.0 AND 180.0),
    min_lon REAL NOT NULL,
    max_lon REAL NOT NULL,
    min_lat REAL NOT NULL,
    max_lat REAL NOT NULL,
    area_km2 REAL,
    spatial_uncertainty_m REAL NOT NULL DEFAULT 500.0 CHECK (spatial_uncertainty_m >= 0.0),
    dist_cbd_km REAL,
    ring TEXT,
    disambiguation_weight REAL NOT NULL DEFAULT 1.0, -- prior prominence (population / area / admin rank)
    geojson_ref TEXT,                          -- relative path in curated/boundaries/ + feature key
    trust_tier TEXT NOT NULL DEFAULT 'A1' REFERENCES trust_tiers(tier_code),
    CHECK (min_lon <= max_lon AND min_lat <= max_lat)
);

CREATE INDEX IF NOT EXISTS idx_gaz_city_class ON spatial_gazetteer(city_id, feature_class);
CREATE INDEX IF NOT EXISTS idx_gaz_norm_name ON spatial_gazetteer(normalized_name, city_id);
CREATE INDEX IF NOT EXISTS idx_gaz_v3_ref ON spatial_gazetteer(v3_source_table, v3_source_pk);

-- R-Tree spatial index (no SpatiaLite extension required!)
CREATE VIRTUAL TABLE IF NOT EXISTS gazetteer_rtree USING rtree(
    gazetteer_id,
    min_lon, max_lon,
    min_lat, max_lat
);

CREATE TRIGGER IF NOT EXISTS trg_gazetteer_ai_rtree
AFTER INSERT ON spatial_gazetteer BEGIN
    INSERT INTO gazetteer_rtree(gazetteer_id, min_lon, max_lon, min_lat, max_lat)
    VALUES (NEW.gazetteer_id, NEW.min_lon, NEW.max_lon, NEW.min_lat, NEW.max_lat);
END;

CREATE TRIGGER IF NOT EXISTS trg_gazetteer_au_rtree
AFTER UPDATE OF min_lon, max_lon, min_lat, max_lat ON spatial_gazetteer BEGIN
    DELETE FROM gazetteer_rtree WHERE gazetteer_id = OLD.gazetteer_id;
    INSERT INTO gazetteer_rtree(gazetteer_id, min_lon, max_lon, min_lat, max_lat)
    VALUES (NEW.gazetteer_id, NEW.min_lon, NEW.max_lon, NEW.min_lat, NEW.max_lat);
END;

CREATE TRIGGER IF NOT EXISTS trg_gazetteer_ad_rtree
AFTER DELETE ON spatial_gazetteer BEGIN
    DELETE FROM gazetteer_rtree WHERE gazetteer_id = OLD.gazetteer_id;
END;

-- Gazetteer aliases (Latin, Cyrillic, English exonyms, Balkan case inflections, colloquial names)
CREATE TABLE IF NOT EXISTS gazetteer_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gazetteer_id INTEGER NOT NULL REFERENCES spatial_gazetteer(gazetteer_id) ON DELETE CASCADE,
    alias_text TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    alias_type TEXT NOT NULL CHECK (alias_type IN (
        'canonical', 'cyrillic', 'english_exonym', 'inflected_stem',
        'colloquial_local', 'official_code', 'historical'
    )),
    city_hint TEXT REFERENCES cities(city_id),
    is_ambiguous INTEGER NOT NULL DEFAULT 0 CHECK (is_ambiguous IN (0, 1)),
    UNIQUE (gazetteer_id, normalized_alias)
);

CREATE INDEX IF NOT EXISTS idx_gaz_alias_norm ON gazetteer_aliases(normalized_alias);

-- FTS5 full-text lookup for fast Balkan gazetteer matching
CREATE VIRTUAL TABLE IF NOT EXISTS gazetteer_fts USING fts5(
    alias_text,
    normalized_alias,
    content='gazetteer_aliases',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS trg_gaz_alias_ai AFTER INSERT ON gazetteer_aliases BEGIN
    INSERT INTO gazetteer_fts(rowid, alias_text, normalized_alias)
    VALUES (NEW.id, NEW.alias_text, NEW.normalized_alias);
END;

CREATE TRIGGER IF NOT EXISTS trg_gaz_alias_ad AFTER DELETE ON gazetteer_aliases BEGIN
    INSERT INTO gazetteer_fts(gazetteer_fts, rowid, alias_text, normalized_alias)
    VALUES ('delete', OLD.id, OLD.alias_text, OLD.normalized_alias);
END;

CREATE TRIGGER IF NOT EXISTS trg_gaz_alias_au AFTER UPDATE ON gazetteer_aliases BEGIN
    INSERT INTO gazetteer_fts(gazetteer_fts, rowid, alias_text, normalized_alias)
    VALUES ('delete', OLD.id, OLD.alias_text, OLD.normalized_alias);
    INSERT INTO gazetteer_fts(rowid, alias_text, normalized_alias)
    VALUES (NEW.id, NEW.alias_text, NEW.normalized_alias);
END;

-- ----------------------------------------------------------------------------
-- 4. EVIDENCE DOCUMENTS, NLP->GIS MENTIONS & PROVENANCE
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS evidence_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL UNIQUE,               -- deterministic hash ID, e.g. 'doc:ejn:2026:123456'
    source_id TEXT NOT NULL REFERENCES source_registry(source_id),
    manifest_id INTEGER REFERENCES sources_manifest(id),
    doc_type TEXT NOT NULL CHECK (doc_type IN (
        'procurement_notice', 'procurement_award', 'urban_plan_act', 'building_permit',
        'subsidy_grant', 'election_result', 'parliament_transcript', 'public_consultation',
        'news_article', 'protest_event_record', 'investigative_report',
        'scientific_paper', 'dissertation', 'patent_filing', 'eu_project_grant',
        'sensor_aggregate', 'market_listing_aggregate', 'financial_stress_record', 'policy_report',
        'cadastral_extract', '3d_building_survey'
    )),
    trust_tier TEXT NOT NULL REFERENCES trust_tiers(tier_code),
    epistemic_role TEXT NOT NULL DEFAULT 'primary_record' CHECK (epistemic_role IN (
        'primary_record', 'peer_reviewed_finding', 'documented_investigation',
        'media_report', 'public_opinion', 'derived_extraction'
    )),
    primary_city_id TEXT REFERENCES cities(city_id),
    country_iso3 TEXT CHECK (country_iso3 IN ('SRB', 'HRV', 'BIH', 'EU', 'INT', NULL)),
    title TEXT NOT NULL,
    summary_text TEXT,
    language TEXT NOT NULL DEFAULT 'sr',
    published_at TEXT NOT NULL,                -- ISO-8601 UTC or YYYY-MM-DD
    fetched_at TEXT NOT NULL,
    primary_url TEXT NOT NULL,
    raw_sha256 TEXT NOT NULL,
    topic_primary TEXT CHECK (topic_primary IN (
        'land_rent_housing', 'urban_planning_gup', 'public_procurement', 'fiscal_budget',
        'transport_corridor', 'labor_wages', 'industry_supply_chain', 'energy_air_climate',
        'tourism_shortterm_rent', 'science_rd_innovation', 'social_friction_protest',
        'financial_stress', 'diaspora_remittances', 'governance_elections', 'other'
    )),
    sentiment_score REAL CHECK (sentiment_score IS NULL OR (sentiment_score BETWEEN -1.0 AND 1.0)),
    nlp_pipeline_version TEXT,                 -- e.g. 'gazetteer-v4.0+llm-extract-v1'
    extraction_json TEXT CHECK (extraction_json IS NULL OR json_valid(extraction_json))
);

CREATE INDEX IF NOT EXISTS idx_docs_city_date ON evidence_documents(primary_city_id, published_at);
CREATE INDEX IF NOT EXISTS idx_docs_tier_topic ON evidence_documents(trust_tier, topic_primary);
CREATE INDEX IF NOT EXISTS idx_docs_source ON evidence_documents(source_id, doc_type);

CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    title,
    summary_text,
    content='evidence_documents',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS trg_docs_ai AFTER INSERT ON evidence_documents BEGIN
    INSERT INTO documents_fts(rowid, title, summary_text)
    VALUES (NEW.id, NEW.title, COALESCE(NEW.summary_text, ''));
END;

CREATE TRIGGER IF NOT EXISTS trg_docs_ad AFTER DELETE ON evidence_documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, title, summary_text)
    VALUES ('delete', OLD.id, OLD.title, COALESCE(OLD.summary_text, ''));
END;

CREATE TRIGGER IF NOT EXISTS trg_docs_au AFTER UPDATE OF title, summary_text ON evidence_documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, title, summary_text)
    VALUES ('delete', OLD.id, OLD.title, COALESCE(OLD.summary_text, ''));
    INSERT INTO documents_fts(rowid, title, summary_text)
    VALUES (NEW.id, NEW.title, COALESCE(NEW.summary_text, ''));
END;

-- NLP -> GIS Geocoded Mentions (bridges unstructured text to spatial_gazetteer)
CREATE TABLE IF NOT EXISTS document_geo_mentions (
    mention_id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL REFERENCES evidence_documents(doc_id) ON DELETE CASCADE,
    gazetteer_id INTEGER REFERENCES spatial_gazetteer(gazetteer_id),
    surface_form TEXT NOT NULL,                -- exact text span found, e.g. "na Ilidži", "u zoni I Novog Pazara"
    char_start INTEGER,
    char_end INTEGER,
    geo_role TEXT NOT NULL DEFAULT 'subject_location' CHECK (geo_role IN (
        'subject_location', 'affected_zone', 'origin_flow', 'destination_flow',
        'authority_seat', 'publisher_dateline', 'comparative_reference'
    )),
    geo_precision TEXT NOT NULL CHECK (geo_precision IN (
        'exact_point', 'parcel_building', 'street_corridor', 'tax_zone',
        'neighborhood_mo', 'municipality', 'hinterland_ring', 'city_core',
        'corridor_line', 'country_macro', 'unresolved'
    )),
    lat REAL CHECK (lat IS NULL OR (lat BETWEEN -90.0 AND 90.0)),
    lon REAL CHECK (lon IS NULL OR (lon BETWEEN -180.0 AND 180.0)),
    spatial_uncertainty_m REAL NOT NULL CHECK (spatial_uncertainty_m >= 0.0),
    match_method TEXT NOT NULL CHECK (match_method IN (
        'structured_api_coords', 'structured_admin_code', 'gazetteer_exact',
        'gazetteer_inflected_stem', 'gazetteer_context_disambiguated',
        'llm_span_to_gazetteer', 'unresolved'
    )),
    geo_confidence REAL NOT NULL CHECK (geo_confidence >= 0.0 AND geo_confidence <= 1.0),
    disambiguation_evidence TEXT,              -- concise trace, e.g. 'source_city=sarajevo + co_mention=Bascarsija'
    render_as_pin INTEGER NOT NULL DEFAULT 0 CHECK (render_as_pin IN (0, 1)),
    -- STRICT MAP HYGIENE: never drop a city_core / country_macro / unresolved mention as a fake street pin!
    CHECK (NOT (render_as_pin = 1 AND geo_precision IN ('city_core', 'hinterland_ring', 'country_macro', 'unresolved')))
);

CREATE INDEX IF NOT EXISTS idx_dgm_doc ON document_geo_mentions(doc_id);
CREATE INDEX IF NOT EXISTS idx_dgm_gaz ON document_geo_mentions(gazetteer_id, geo_precision);
CREATE INDEX IF NOT EXISTS idx_dgm_conf ON document_geo_mentions(geo_confidence, render_as_pin);

CREATE TABLE IF NOT EXISTS document_entity_mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL REFERENCES evidence_documents(doc_id) ON DELETE CASCADE,
    entity_id TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    surface_form TEXT NOT NULL,
    mention_role TEXT NOT NULL CHECK (mention_role IN (
        'contracting_authority', 'winning_bidder', 'bidder', 'subsidy_recipient',
        'plan_proponent', 'research_institution', 'investor', 'affected_actor',
        'protest_organizer', 'mentioned_general'
    )),
    confidence REAL NOT NULL DEFAULT 1.0 CHECK (confidence > 0.0 AND confidence <= 1.0),
    UNIQUE (doc_id, entity_id, mention_role)
);

CREATE INDEX IF NOT EXISTS idx_dem_entity ON document_entity_mentions(entity_id, mention_role);

-- ----------------------------------------------------------------------------
-- 5. SPECIALIZED HIGH-VOLUME DOMAIN SIGNAL TABLES (Structured Fast-Path)
-- ----------------------------------------------------------------------------

-- 5A. Public Procurement Awards & Structural Competition Indicators (BiH EJN, SRB UJN, HR EOJN/TED)
CREATE TABLE IF NOT EXISTS domain_signals_procurement (
    contract_uid TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL REFERENCES evidence_documents(doc_id) ON DELETE CASCADE,
    city_id TEXT REFERENCES cities(city_id),
    country_iso3 TEXT NOT NULL CHECK (country_iso3 IN ('SRB', 'HRV', 'BIH')),
    gazetteer_id INTEGER REFERENCES spatial_gazetteer(gazetteer_id),
    buyer_entity_id TEXT REFERENCES entities(entity_id),
    winner_entity_id TEXT REFERENCES entities(entity_id),
    cpv_code TEXT,
    cpv_division TEXT,
    procedure_type TEXT,
    award_date TEXT NOT NULL,
    estimated_value_eur REAL,
    contract_value_eur REAL NOT NULL CHECK (contract_value_eur >= 0.0),
    currency_orig TEXT,
    bidders_count INTEGER CHECK (bidders_count IS NULL OR bidders_count >= 0),
    -- Strictly objective structural indicators (no accusation labels!)
    single_bidder_flag INTEGER GENERATED ALWAYS AS (CASE WHEN bidders_count = 1 THEN 1 ELSE 0 END) STORED,
    value_to_estimate_ratio REAL GENERATED ALWAYS AS (
        CASE WHEN estimated_value_eur IS NOT NULL AND estimated_value_eur > 0
             THEN ROUND(contract_value_eur / estimated_value_eur, 4)
             ELSE NULL END
    ) STORED,
    trust_tier TEXT NOT NULL DEFAULT 'A1' REFERENCES trust_tiers(tier_code)
);

CREATE INDEX IF NOT EXISTS idx_proc_city_date ON domain_signals_procurement(city_id, award_date);
CREATE INDEX IF NOT EXISTS idx_proc_buyer_winner ON domain_signals_procurement(buyer_entity_id, winner_entity_id);
CREATE INDEX IF NOT EXISTS idx_proc_cpv ON domain_signals_procurement(cpv_division, single_bidder_flag);

-- 5B. Science & Innovation Layer (Uloga A: About City + Uloga B: In City R&D)
CREATE TABLE IF NOT EXISTS domain_signals_science (
    work_uid TEXT PRIMARY KEY,                 -- e.g. 'openalex:W12345', 'cordis:101012345', 'epo:EP123456'
    doc_id TEXT NOT NULL REFERENCES evidence_documents(doc_id) ON DELETE CASCADE,
    science_role TEXT NOT NULL CHECK (science_role IN ('about_city', 'in_city_rd', 'both')),
    work_type TEXT NOT NULL CHECK (work_type IN ('journal_article', 'dissertation', 'conference', 'policy_study', 'eu_grant', 'patent')),
    city_id TEXT REFERENCES cities(city_id),
    institution_entity_id TEXT REFERENCES entities(entity_id),
    pub_year INTEGER NOT NULL,
    doi_or_grant_no TEXT,
    cited_by_count INTEGER DEFAULT 0,
    grant_amount_eur REAL,
    open_access_url TEXT,
    concepts_json TEXT CHECK (concepts_json IS NULL OR json_valid(concepts_json)),
    trust_tier TEXT NOT NULL DEFAULT 'B' REFERENCES trust_tiers(tier_code)
);

CREATE INDEX IF NOT EXISTS idx_sci_city_role ON domain_signals_science(city_id, science_role, pub_year);
CREATE INDEX IF NOT EXISTS idx_sci_inst ON domain_signals_science(institution_entity_id);

-- 5C. Independent Physical, Satellite, Digital & Real-Time Market Sensors (Universal 5-City Panel)
CREATE TABLE IF NOT EXISTS domain_signals_sensors (
    obs_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL REFERENCES source_registry(source_id),
    city_id TEXT NOT NULL REFERENCES cities(city_id),
    gazetteer_id INTEGER REFERENCES spatial_gazetteer(gazetteer_id),
    grid_cell_id TEXT,                         -- H3 index, 1km census cell, or 610m Ookla quadkey
    sensor_metric TEXT NOT NULL CHECK (sensor_metric IN (
        'viirs_radiance_nw', 'ghsl_built_vol_m3', 'openaq_pm25_ugm3', 'openaq_no2_ugm3',
        'sentinel5p_no2_molm2', 'entsoe_load_mw', 'ookla_fixed_dl_mbps', 'ookla_mobile_dl_mbps',
        'gtfs_reachable_jobs_30m', 'hr_fiscal_receipts_eur', 'hr_evisitor_nights',
        'asking_rent_eur_m2', 'asking_sale_eur_m2', 'job_postings_count',
        'blocked_accounts_count', 'bankruptcies_count', 'remittances_mio_eur'
    )),
    period_start TEXT NOT NULL,                -- ISO date YYYY-MM-DD
    period_end TEXT NOT NULL,
    cadence TEXT NOT NULL CHECK (cadence IN ('hourly', 'daily', 'weekly', 'monthly', 'quarterly', 'annual')),
    value_num REAL NOT NULL,
    value_unit TEXT NOT NULL,
    sample_n INTEGER,
    trust_tier TEXT NOT NULL REFERENCES trust_tiers(tier_code),
    manifest_id INTEGER REFERENCES sources_manifest(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_sens_obs
    ON domain_signals_sensors(source_id, city_id, COALESCE(gazetteer_id, -1), COALESCE(grid_cell_id, ''), sensor_metric, period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_sens_city_metric_time ON domain_signals_sensors(city_id, sensor_metric, period_start);
CREATE INDEX IF NOT EXISTS idx_sens_gaz_metric ON domain_signals_sensors(gazetteer_id, sensor_metric, period_start);

-- ----------------------------------------------------------------------------
-- 5D. ELECTORAL GEOGRAPHY BY POLLING STATION (RIK Serbia / DIP Croatia / CIK BiH)
--     Strictly aggregate official tally data (A1). Zero individual voter PII.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS election_cycles (
    election_id TEXT PRIMARY KEY,              -- e.g. 'elec:srb:2024-06-02:local_bg', 'elec:hrv:2025-05-18:local_zg', 'elec:bih:2024-10-06:local'
    country_iso3 TEXT NOT NULL CHECK (country_iso3 IN ('SRB', 'HRV', 'BIH')),
    authority_body TEXT NOT NULL CHECK (authority_body IN ('RIK', 'GIK', 'DIP', 'CIK')),
    election_level TEXT NOT NULL CHECK (election_level IN (
        'parliamentary_national', 'presidential', 'entity_parliament_fbih', 'cantonal_assembly',
        'city_assembly', 'municipality_council', 'mayor_executive', 'district_cetvrt_mo', 'eu_parliament'
    )),
    election_date TEXT NOT NULL,               -- ISO YYYY-MM-DD
    round_no INTEGER NOT NULL DEFAULT 1 CHECK (round_no IN (1, 2)),
    title TEXT NOT NULL,
    legal_threshold_pct REAL CHECK (legal_threshold_pct IS NULL OR (legal_threshold_pct >= 0.0 AND legal_threshold_pct <= 50.0)),
    minority_natural_threshold INTEGER NOT NULL DEFAULT 0 CHECK (minority_natural_threshold IN (0, 1)),
    source_id TEXT NOT NULL REFERENCES source_registry(source_id),
    trust_tier TEXT NOT NULL DEFAULT 'A1' REFERENCES trust_tiers(tier_code),
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_elec_cycles_country_date ON election_cycles(country_iso3, election_date);

CREATE TABLE IF NOT EXISTS polling_stations (
    station_uid TEXT PRIMARY KEY,              -- e.g. 'ps:elec:bih:2024-10-06:local:139A001'
    election_id TEXT NOT NULL REFERENCES election_cycles(election_id) ON DELETE CASCADE,
    city_id TEXT NOT NULL REFERENCES cities(city_id),
    country_iso3 TEXT NOT NULL CHECK (country_iso3 IN ('SRB', 'HRV', 'BIH')),
    constituency_code TEXT,                    -- HR izborna jedinica / BiH osnovna izborna jedinica / SRB opština kod
    municipality_name TEXT NOT NULL,
    station_code TEXT NOT NULL,                -- official BM code (e.g. '14', '0042', '139A001')
    station_name TEXT NOT NULL,                -- e.g. 'OŠ Vuk Karadžić', 'MZ Grbavica I'
    address_text TEXT,
    station_type TEXT NOT NULL DEFAULT 'regular' CHECK (station_type IN (
        'regular', 'absentee_postal', 'mobile_team', 'unconfirmed_ballots', 'diplomatic', 'prison_institution'
    )),
    -- Spatial links (polygon anchor + optional exact XS building/parcel anchor)
    gazetteer_id INTEGER REFERENCES spatial_gazetteer(gazetteer_id),
    parcel_uid TEXT,                           -- optional logical link to xs_cadastral_parcels(parcel_uid)
    building_uid TEXT,                         -- optional logical link to xs_buildings_3d(building_uid)
    lat REAL CHECK (lat IS NULL OR (lat BETWEEN -90.0 AND 90.0)),
    lon REAL CHECK (lon IS NULL OR (lon BETWEEN -180.0 AND 180.0)),
    geo_precision TEXT NOT NULL DEFAULT 'municipality' CHECK (geo_precision IN (
        'exact_point', 'parcel_building', 'street_corridor', 'neighborhood_mo', 'municipality', 'city_core', 'unresolved'
    )),
    spatial_uncertainty_m REAL NOT NULL DEFAULT 500.0 CHECK (spatial_uncertainty_m >= 0.0),
    render_as_pin INTEGER NOT NULL DEFAULT 0 CHECK (render_as_pin IN (0, 1)),
    -- Aggregate official ballot counts (zero PII)
    registered_voters INTEGER CHECK (registered_voters IS NULL OR registered_voters >= 0),
    ballots_cast INTEGER NOT NULL CHECK (ballots_cast >= 0),
    valid_ballots INTEGER NOT NULL CHECK (valid_ballots >= 0),
    invalid_ballots INTEGER NOT NULL CHECK (invalid_ballots >= 0),
    turnout_pct REAL GENERATED ALWAYS AS (
        CASE WHEN registered_voters IS NOT NULL AND registered_voters > 0
             THEN ROUND(100.0 * ballots_cast / registered_voters, 2)
             ELSE NULL END
    ) STORED,
    invalid_ballots_pct REAL GENERATED ALWAYS AS (
        CASE WHEN ballots_cast > 0
             THEN ROUND(100.0 * invalid_ballots / ballots_cast, 2)
             ELSE NULL END
    ) STORED,
    doc_id TEXT REFERENCES evidence_documents(doc_id),
    trust_tier TEXT NOT NULL DEFAULT 'A1' REFERENCES trust_tiers(tier_code),
    UNIQUE (election_id, municipality_name, station_code, station_type),
    -- Ballot arithmetic & map hygiene guardrails
    CHECK (valid_ballots + invalid_ballots <= ballots_cast),
    CHECK (station_type != 'regular' OR registered_voters IS NULL OR ballots_cast <= registered_voters),
    CHECK (NOT (render_as_pin = 1 AND geo_precision IN ('city_core', 'unresolved')))
);

CREATE INDEX IF NOT EXISTS idx_ps_elec_city ON polling_stations(election_id, city_id);
CREATE INDEX IF NOT EXISTS idx_ps_gaz ON polling_stations(gazetteer_id, station_type);

CREATE TABLE IF NOT EXISTS election_station_results (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_uid TEXT NOT NULL REFERENCES polling_stations(station_uid) ON DELETE CASCADE,
    election_id TEXT NOT NULL REFERENCES election_cycles(election_id) ON DELETE CASCADE,
    party_or_list_entity_id TEXT REFERENCES entities(entity_id),
    ballot_number INTEGER CHECK (ballot_number IS NULL OR ballot_number > 0),
    list_or_candidate_name TEXT NOT NULL,
    -- Cross-country comparative classification for 5-city Public Choice analysis
    comparative_bloc TEXT NOT NULL DEFAULT 'other' CHECK (comparative_bloc IN (
        'incumbent_national', 'incumbent_local', 'opposition_civic_green', 'opposition_center_right',
        'minority_regional', 'independent_local', 'coalition_mixed', 'other'
    )),
    is_minority_list INTEGER NOT NULL DEFAULT 0 CHECK (is_minority_list IN (0, 1)),
    votes_count INTEGER NOT NULL CHECK (votes_count >= 0),
    vote_share_valid_pct REAL CHECK (vote_share_valid_pct IS NULL OR (vote_share_valid_pct >= 0.0 AND vote_share_valid_pct <= 100.0)),
    preferential_votes_top INTEGER CHECK (preferential_votes_top IS NULL OR preferential_votes_top >= 0),
    trust_tier TEXT NOT NULL DEFAULT 'A1' REFERENCES trust_tiers(tier_code),
    UNIQUE (station_uid, list_or_candidate_name)
);

CREATE INDEX IF NOT EXISTS idx_esr_station ON election_station_results(station_uid, votes_count DESC);
CREATE INDEX IF NOT EXISTS idx_esr_elec_entity ON election_station_results(election_id, party_or_list_entity_id);
CREATE INDEX IF NOT EXISTS idx_esr_bloc ON election_station_results(election_id, comparative_bloc);

-- Temporal crosswalk between polling stations across election cycles (handles renumbering & splits)
CREATE TABLE IF NOT EXISTS election_station_crosswalk (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_station_uid TEXT NOT NULL REFERENCES polling_stations(station_uid) ON DELETE CASCADE,
    to_station_uid TEXT NOT NULL REFERENCES polling_stations(station_uid) ON DELETE CASCADE,
    spatial_overlap_weight REAL NOT NULL DEFAULT 1.0 CHECK (spatial_overlap_weight > 0.0 AND spatial_overlap_weight <= 1.0),
    match_method TEXT NOT NULL CHECK (match_method IN (
        'exact_code_and_address', 'same_building_renumbered', 'voronoi_area_weighted', 'gazetteer_parent_fallback'
    )),
    notes TEXT,
    UNIQUE (from_station_uid, to_station_uid),
    CHECK (from_station_uid != to_station_uid)
);

-- ----------------------------------------------------------------------------
-- 5E. 3D / PARCEL XS MICRO-LAYER (Cadastre, GUP/PDR/ISPU Zoning Envelopes,
--     3D Buildings + Native R-Tree, and CEOP/ISPU Building Permits)
--     Privacy guard: NO personal names of private natural-person owners.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS xs_cadastral_parcels (
    parcel_uid TEXT PRIMARY KEY,               -- e.g. 'parcel:srb:ko_70254:1234_2', 'parcel:hrv:ko_335304:512_1', 'parcel:bih:ko_ilidza:88_3'
    city_id TEXT NOT NULL REFERENCES cities(city_id),
    country_iso3 TEXT NOT NULL CHECK (country_iso3 IN ('SRB', 'HRV', 'BIH')),
    cadastral_municipality TEXT NOT NULL,      -- Katastarska opština / općina (KO)
    ko_code TEXT,
    parcel_number TEXT NOT NULL,               -- e.g. '1234/2'
    gazetteer_id INTEGER REFERENCES spatial_gazetteer(gazetteer_id),
    tax_zone_name TEXT,                        -- logical match to v3 property_tax_zones_gis_summary.zone_name
    land_class TEXT NOT NULL CHECK (land_class IN (
        'building_land', 'agricultural_arable', 'forest', 'public_infrastructure',
        'water', 'industrial_brownfield', 'mixed_unclassified'
    )),
    ownership_regime TEXT NOT NULL DEFAULT 'unknown' CHECK (ownership_regime IN (
        'public_state', 'public_municipal', 'private_physical', 'private_corporate',
        'mixed_coownership', 'public_enterprise', 'restitution_disputed', 'unknown'
    )),
    -- Only institutional/corporate entities allowed here (enforced against private natural persons via entities table)
    institutional_owner_entity_id TEXT REFERENCES entities(entity_id),
    area_m2 REAL NOT NULL CHECK (area_m2 > 0.0),
    centroid_lat REAL NOT NULL CHECK (centroid_lat BETWEEN -90.0 AND 90.0),
    centroid_lon REAL NOT NULL CHECK (centroid_lon BETWEEN -180.0 AND 180.0),
    min_lon REAL NOT NULL,
    max_lon REAL NOT NULL,
    min_lat REAL NOT NULL,
    max_lat REAL NOT NULL,
    assessed_tax_eur_m2 REAL CHECK (assessed_tax_eur_m2 IS NULL OR assessed_tax_eur_m2 >= 0.0),
    market_est_eur_m2 REAL CHECK (market_est_eur_m2 IS NULL OR market_est_eur_m2 >= 0.0),
    geojson_ref TEXT,                          -- path/key in curated/xs_parcels/ (GeoJSON or FlatGeobuf)
    source_id TEXT NOT NULL REFERENCES source_registry(source_id),
    doc_id TEXT REFERENCES evidence_documents(doc_id),
    trust_tier TEXT NOT NULL DEFAULT 'A1' REFERENCES trust_tiers(tier_code),
    captured_at TEXT NOT NULL,
    UNIQUE (country_iso3, cadastral_municipality, parcel_number),
    CHECK (min_lon <= max_lon AND min_lat <= max_lat),
    CHECK (ownership_regime != 'private_physical' OR institutional_owner_entity_id IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_parcels_city_ko ON xs_cadastral_parcels(city_id, cadastral_municipality, land_class);
CREATE INDEX IF NOT EXISTS idx_parcels_gaz_tax ON xs_cadastral_parcels(gazetteer_id, tax_zone_name);

-- Regulatory Zoning Envelopes (GUP / PDR / ISPU / ZPR KS) — measures political rent creation over time!
CREATE TABLE IF NOT EXISTS xs_zoning_envelopes (
    envelope_uid TEXT PRIMARY KEY,             -- e.g. 'zone:hrv:ispu:zg_m1_042', 'zone:srb:pdr_bg:blok_18'
    city_id TEXT NOT NULL REFERENCES cities(city_id),
    country_iso3 TEXT NOT NULL CHECK (country_iso3 IN ('SRB', 'HRV', 'BIH')),
    parcel_uid TEXT REFERENCES xs_cadastral_parcels(parcel_uid) ON DELETE CASCADE,
    gazetteer_id INTEGER REFERENCES spatial_gazetteer(gazetteer_id),
    plan_doc_id TEXT REFERENCES evidence_documents(doc_id),
    plan_name TEXT NOT NULL,                   -- e.g. 'GUP Beograda 2041', 'GUP Grada Zagreba', 'RP Centar Marijin Dvor'
    zone_code TEXT NOT NULL,                   -- e.g. 'M1', 'S', 'K2', 'I', 'Z1'
    permitted_use TEXT NOT NULL CHECK (permitted_use IN (
        'residential', 'commercial', 'mixed_use', 'industrial', 'public_facility',
        'green_recreation', 'agricultural', 'protected_heritage', 'infrastructure'
    )),
    max_far REAL CHECK (max_far IS NULL OR (max_far >= 0.0 AND max_far <= 30.0)),
    max_coverage_ratio REAL CHECK (max_coverage_ratio IS NULL OR (max_coverage_ratio >= 0.0 AND max_coverage_ratio <= 1.0)),
    max_height_m REAL CHECK (max_height_m IS NULL OR (max_height_m >= 0.0 AND max_height_m <= 400.0)),
    max_floors INTEGER CHECK (max_floors IS NULL OR (max_floors >= 0 AND max_floors <= 120)),
    min_green_ratio REAL CHECK (min_green_ratio IS NULL OR (min_green_ratio >= 0.0 AND min_green_ratio <= 1.0)),
    effective_from TEXT NOT NULL,              -- ISO date YYYY-MM-DD (allows tracking rezoning shocks!)
    effective_to TEXT,                         -- NULL = currently in force
    source_id TEXT NOT NULL REFERENCES source_registry(source_id),
    trust_tier TEXT NOT NULL DEFAULT 'A1' REFERENCES trust_tiers(tier_code),
    CHECK (parcel_uid IS NOT NULL OR gazetteer_id IS NOT NULL),
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE INDEX IF NOT EXISTS idx_zoning_parcel_time ON xs_zoning_envelopes(parcel_uid, effective_from, effective_to);
CREATE INDEX IF NOT EXISTS idx_zoning_city_use ON xs_zoning_envelopes(city_id, permitted_use, zone_code);

-- 3D Building Massing Table (LiDAR City Models / OSM 3D / Copernicus GHSL Built-V)
CREATE TABLE IF NOT EXISTS xs_buildings_3d (
    building_uid TEXT PRIMARY KEY,             -- e.g. 'bldg:zg_3d:104921', 'bldg:osm:way_981234'
    city_id TEXT NOT NULL REFERENCES cities(city_id),
    country_iso3 TEXT NOT NULL CHECK (country_iso3 IN ('SRB', 'HRV', 'BIH')),
    parcel_uid TEXT REFERENCES xs_cadastral_parcels(parcel_uid) ON DELETE SET NULL,
    gazetteer_id INTEGER REFERENCES spatial_gazetteer(gazetteer_id),
    operator_entity_id TEXT REFERENCES entities(entity_id),
    building_name TEXT,
    address_text TEXT,
    building_use TEXT NOT NULL DEFAULT 'unknown' CHECK (building_use IN (
        'residential_single', 'residential_multi', 'commercial_office', 'retail_mall',
        'industrial_warehouse', 'public_education', 'public_health', 'public_admin',
        'cultural_religious', 'hospitality_hotel', 'mixed_use', 'under_construction',
        'ruin_vacant', 'unknown'
    )),
    footprint_area_m2 REAL NOT NULL CHECK (footprint_area_m2 > 0.0),
    height_m REAL NOT NULL CHECK (height_m > 0.0 AND height_m <= 450.0),
    ground_elevation_m REAL,
    floors_above_ground INTEGER CHECK (floors_above_ground IS NULL OR floors_above_ground >= 1),
    floors_underground INTEGER CHECK (floors_underground IS NULL OR floors_underground >= 0),
    gross_floor_area_m2 REAL CHECK (gross_floor_area_m2 IS NULL OR gross_floor_area_m2 > 0.0),
    -- Automatically computed 3D physical volume
    volume_m3 REAL GENERATED ALWAYS AS (ROUND(footprint_area_m2 * height_m, 2)) STORED,
    roof_type TEXT DEFAULT 'unknown' CHECK (roof_type IN ('flat', 'gabled', 'hipped', 'dome', 'complex', 'unknown')),
    height_source TEXT NOT NULL CHECK (height_source IN (
        'lidar_3d_city_model', 'cadastre_register', 'building_permit_ceop_ispu',
        'osm_explicit_height', 'osm_levels_estimated', 'ghsl_3d_raster', 'shadow_ml_inferred'
    )),
    year_built INTEGER CHECK (year_built IS NULL OR (year_built BETWEEN 1400 AND 2040)),
    energy_class TEXT CHECK (energy_class IS NULL OR energy_class IN ('A+', 'A', 'B', 'C', 'D', 'E', 'F', 'G')),
    heating_source TEXT DEFAULT 'unknown' CHECK (heating_source IN (
        'district_heating', 'natural_gas', 'heat_pump_electric', 'solid_fuel_coal_wood', 'oil', 'unknown'
    )),
    centroid_lat REAL NOT NULL CHECK (centroid_lat BETWEEN -90.0 AND 90.0),
    centroid_lon REAL NOT NULL CHECK (centroid_lon BETWEEN -180.0 AND 180.0),
    min_lon REAL NOT NULL,
    max_lon REAL NOT NULL,
    min_lat REAL NOT NULL,
    max_lat REAL NOT NULL,
    geometry_ref TEXT,                         -- GeoJSON / FlatGeobuf / 3D Tiles feature pointer
    source_id TEXT NOT NULL REFERENCES source_registry(source_id),
    trust_tier TEXT NOT NULL REFERENCES trust_tiers(tier_code),
    -- Height-provenance honesty: ML/level-estimated heights cannot claim A1
    CHECK (min_lon <= max_lon AND min_lat <= max_lat),
    CHECK (height_source NOT IN ('osm_levels_estimated', 'shadow_ml_inferred') OR trust_tier IN ('C', 'D'))
);

CREATE INDEX IF NOT EXISTS idx_bldg_city_use ON xs_buildings_3d(city_id, building_use);
CREATE INDEX IF NOT EXISTS idx_bldg_parcel ON xs_buildings_3d(parcel_uid);
CREATE INDEX IF NOT EXISTS idx_bldg_gaz_heat ON xs_buildings_3d(gazetteer_id, heating_source);

-- Native SQLite R-Tree for instant 3D viewport tiling without SpatiaLite
CREATE VIRTUAL TABLE IF NOT EXISTS xs_buildings_rtree USING rtree(
    bldg_rowid,
    min_lon, max_lon,
    min_lat, max_lat
);

CREATE TRIGGER IF NOT EXISTS trg_xs_bldg_ai_rtree
AFTER INSERT ON xs_buildings_3d BEGIN
    INSERT INTO xs_buildings_rtree(bldg_rowid, min_lon, max_lon, min_lat, max_lat)
    VALUES (NEW.rowid, NEW.min_lon, NEW.max_lon, NEW.min_lat, NEW.max_lat);
END;

CREATE TRIGGER IF NOT EXISTS trg_xs_bldg_au_rtree
AFTER UPDATE OF min_lon, max_lon, min_lat, max_lat ON xs_buildings_3d BEGIN
    DELETE FROM xs_buildings_rtree WHERE bldg_rowid = OLD.rowid;
    INSERT INTO xs_buildings_rtree(bldg_rowid, min_lon, max_lon, min_lat, max_lat)
    VALUES (NEW.rowid, NEW.min_lon, NEW.max_lon, NEW.min_lat, NEW.max_lat);
END;

CREATE TRIGGER IF NOT EXISTS trg_xs_bldg_ad_rtree
AFTER DELETE ON xs_buildings_3d BEGIN
    DELETE FROM xs_buildings_rtree WHERE bldg_rowid = OLD.rowid;
END;

-- Building Permits & Construction Pipeline (CEOP Serbia / ISPU eDozvola Croatia / BiH Municipal Permits)
CREATE TABLE IF NOT EXISTS xs_building_permits (
    permit_uid TEXT PRIMARY KEY,               -- e.g. 'perm:ceop:ROP-BG-12345-2026', 'perm:ispu:ZG-2026-991'
    doc_id TEXT NOT NULL REFERENCES evidence_documents(doc_id) ON DELETE CASCADE,
    city_id TEXT NOT NULL REFERENCES cities(city_id),
    country_iso3 TEXT NOT NULL CHECK (country_iso3 IN ('SRB', 'HRV', 'BIH')),
    parcel_uid TEXT REFERENCES xs_cadastral_parcels(parcel_uid) ON DELETE SET NULL,
    building_uid TEXT REFERENCES xs_buildings_3d(building_uid) ON DELETE SET NULL,
    gazetteer_id INTEGER REFERENCES spatial_gazetteer(gazetteer_id),
    investor_entity_id TEXT REFERENCES entities(entity_id),
    authority_entity_id TEXT REFERENCES entities(entity_id),
    permit_type TEXT NOT NULL CHECK (permit_type IN (
        'location_conditions', 'building_permit', 'occupancy_permit',
        'demolition_permit', 'legalization', 'plan_amendment'
    )),
    status TEXT NOT NULL CHECK (status IN ('applied', 'issued', 'rejected', 'expired', 'revoked', 'completed')),
    issue_date TEXT NOT NULL,
    planned_gfa_m2 REAL CHECK (planned_gfa_m2 IS NULL OR planned_gfa_m2 >= 0.0),
    planned_units_count INTEGER CHECK (planned_units_count IS NULL OR planned_units_count >= 0),
    planned_floors INTEGER CHECK (planned_floors IS NULL OR planned_floors >= 0),
    estimated_investment_eur REAL CHECK (estimated_investment_eur IS NULL OR estimated_investment_eur >= 0.0),
    communal_fee_eur REAL CHECK (communal_fee_eur IS NULL OR communal_fee_eur >= 0.0),
    trust_tier TEXT NOT NULL DEFAULT 'A1' REFERENCES trust_tiers(tier_code)
);

CREATE INDEX IF NOT EXISTS idx_perm_city_date ON xs_building_permits(city_id, issue_date, permit_type);
CREATE INDEX IF NOT EXISTS idx_perm_parcel ON xs_building_permits(parcel_uid);
CREATE INDEX IF NOT EXISTS idx_perm_investor ON xs_building_permits(investor_entity_id);

-- ----------------------------------------------------------------------------
-- 6. CANONICAL URBAN EVENTS (De-duplicated Real-World Shocks & Decisions)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS urban_events (
    event_id TEXT PRIMARY KEY,                 -- e.g. 'evt:np:2025-11:tax_zone_revaluation_2026'
    city_id TEXT NOT NULL REFERENCES cities(city_id),
    event_category TEXT NOT NULL CHECK (event_category IN (
        'urban_plan_change', 'tax_policy_shock', 'infrastructure_milestone',
        'major_procurement_award', 'private_investment_entry', 'factory_closure_layoff',
        'subsidy_eu_grant', 'protest_strike_blockade', 'environmental_crisis',
        'macro_fiscal_shock', 'housing_rent_shock', 'election_turnover'
    )),
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    -- Multi-timestamp t0 anatomy (real estate moves on announcement; taxes on enactment; traffic on opening!)
    t0_announced TEXT,                         -- ISO date YYYY-MM-DD
    t0_enacted TEXT,                           -- legal adoption / contract signing date
    t0_effective TEXT,                         -- physical opening / tax effective / shock date
    primary_t0 TEXT NOT NULL,                  -- chosen canonical t0 for default alignment
    primary_t0_type TEXT NOT NULL CHECK (primary_t0_type IN ('announced', 'enacted', 'effective')),
    magnitude_eur REAL,                        -- optional financial scale in EUR
    severity_score REAL CHECK (severity_score IS NULL OR (severity_score BETWEEN 1.0 AND 5.0)),
    -- Epistemic monotonicity: highest (best) corroborating tier vs lowest cited tier
    corroborated_trust_tier TEXT NOT NULL REFERENCES trust_tiers(tier_code),
    verification_status TEXT NOT NULL DEFAULT 'draft' CHECK (verification_status IN (
        'draft', 'multi_source_corroborated', 'official_record_verified', 'disputed', 'retracted'
    )),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_events_city_t0 ON urban_events(city_id, primary_t0);
CREATE INDEX IF NOT EXISTS idx_events_cat_tier ON urban_events(event_category, corroborated_trust_tier);

CREATE TABLE IF NOT EXISTS event_evidence_links (
    event_id TEXT NOT NULL REFERENCES urban_events(event_id) ON DELETE CASCADE,
    doc_id TEXT NOT NULL REFERENCES evidence_documents(doc_id) ON DELETE CASCADE,
    link_role TEXT NOT NULL CHECK (link_role IN (
        'primary_legal_basis', 'official_confirmation', 'scientific_analysis',
        'media_announcement', 'media_followup', 'contradicting_evidence'
    )),
    PRIMARY KEY (event_id, doc_id)
);

CREATE TABLE IF NOT EXISTS event_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL REFERENCES urban_events(event_id) ON DELETE CASCADE,
    gazetteer_id INTEGER NOT NULL REFERENCES spatial_gazetteer(gazetteer_id),
    impact_role TEXT NOT NULL DEFAULT 'epicenter' CHECK (impact_role IN (
        'epicenter', 'direct_corridor', 'affected_zone', 'spillover_ring', 'control_comparison'
    )),
    impact_radius_km REAL CHECK (impact_radius_km IS NULL OR impact_radius_km >= 0.0),
    UNIQUE (event_id, gazetteer_id, impact_role)
);

CREATE INDEX IF NOT EXISTS idx_evt_loc_gaz ON event_locations(gazetteer_id, impact_role);

-- ----------------------------------------------------------------------------
-- 7. EVENT-STUDY (t0) & DIFFERENCE-IN-DIFFERENCES (DiD) CAUSAL PANEL
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS event_studies (
    study_id TEXT PRIMARY KEY,                 -- e.g. 'es:bg_np:tax_zone_2026_vs_asking'
    event_id TEXT NOT NULL REFERENCES urban_events(event_id) ON DELETE CASCADE,
    study_title TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    t0_anchor_type TEXT NOT NULL CHECK (t0_anchor_type IN ('announced', 'enacted', 'effective')),
    t0_date TEXT NOT NULL,
    outcome_metric TEXT NOT NULL,              -- matches domain_signals_sensors.sensor_metric or v3 metric key
    outcome_unit TEXT NOT NULL,
    treatment_definition TEXT NOT NULL,        -- e.g. 'within 0-2 km of interchange / Zona I'
    control_definition TEXT NOT NULL,          -- e.g. 'matched 3-6 km ring same city / peer city'
    identification_grade TEXT NOT NULL CHECK (identification_grade IN (
        'descriptive_before_after',            -- lowest: no control group (UI warns: correlation only!)
        'matched_control_did',                 -- treated vs control ring DiD
        'staggered_multi_city_did',            -- cross-city DiD across 5 cities
        'synthetic_control',
        'quasi_experimental_iv_rdd'            -- e.g. tax-zone boundary RDD!
    )),
    effective_trust_tier TEXT NOT NULL REFERENCES trust_tiers(tier_code),
    min_upstream_tier TEXT NOT NULL REFERENCES trust_tiers(tier_code),
    -- EPISTEMIC MONOTONICITY GUARD: study effective tier cannot be stronger than 'D' (derived)
    -- unless explicitly audited, and min_upstream_tier records the weakest input tier.
    CHECK (effective_trust_tier = 'D')
);

CREATE TABLE IF NOT EXISTS event_study_observations (
    obs_id INTEGER PRIMARY KEY AUTOINCREMENT,
    study_id TEXT NOT NULL REFERENCES event_studies(study_id) ON DELETE CASCADE,
    cohort_group TEXT NOT NULL CHECK (cohort_group IN (
        'treated_core', 'treated_ring_1', 'spillover_ring', 'control_local', 'control_peer_city'
    )),
    rel_period INTEGER NOT NULL,               -- relative time to t0, e.g. -12, -6, -3, -1, 0, +1, +3, +6, +12
    rel_unit TEXT NOT NULL DEFAULT 'month' CHECK (rel_unit IN ('day', 'week', 'month', 'quarter', 'year')),
    calendar_period TEXT NOT NULL,             -- e.g. '2025-11'
    city_id TEXT NOT NULL REFERENCES cities(city_id),
    gazetteer_id INTEGER REFERENCES spatial_gazetteer(gazetteer_id),
    metric_value REAL NOT NULL,
    baseline_value REAL,                       -- value at rel_period = -1 (or pre-t0 mean)
    pct_change_vs_baseline REAL GENERATED ALWAYS AS (
        CASE WHEN baseline_value IS NOT NULL AND baseline_value != 0
             THEN ROUND(100.0 * (metric_value - baseline_value) / ABS(baseline_value), 3)
             ELSE NULL END
    ) STORED,
    sample_n INTEGER,
    upstream_trust_tier TEXT NOT NULL REFERENCES trust_tiers(tier_code),
    source_doc_id TEXT REFERENCES evidence_documents(doc_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_eso_panel
    ON event_study_observations(study_id, cohort_group, rel_period, rel_unit, city_id, COALESCE(gazetteer_id, -1));
CREATE INDEX IF NOT EXISTS idx_eso_study_period ON event_study_observations(study_id, rel_period, cohort_group);

-- ----------------------------------------------------------------------------
-- 8. PROVENANCE & CLAIM AUDIT LOG (No Trust-Tier Laundering)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS provenance_claims (
    claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_table TEXT NOT NULL,
    target_pk TEXT NOT NULL,
    claim_type TEXT NOT NULL CHECK (claim_type IN (
        'numeric_metric', 'spatial_assignment', 'entity_link', 'event_date', 'did_estimate', 'policy_summary'
    )),
    claimed_value_text TEXT NOT NULL,
    upstream_doc_ids_json TEXT NOT NULL CHECK (json_valid(upstream_doc_ids_json)),
    derived_trust_tier TEXT NOT NULL REFERENCES trust_tiers(tier_code),
    min_upstream_tier TEXT NOT NULL REFERENCES trust_tiers(tier_code),
    extractor_version TEXT NOT NULL,
    excerpt_quote TEXT,
    verified_by TEXT,                          -- NULL if automated; human/reviewer ID if audited
    verified_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    -- Prevent silent trust-laundering: if unverified, derived_trust_tier rank cannot beat min_upstream_tier rank
    CHECK (verified_by IS NOT NULL OR derived_trust_tier IN ('C', 'D') OR derived_trust_tier = min_upstream_tier)
);

CREATE INDEX IF NOT EXISTS idx_prov_target ON provenance_claims(target_table, target_pk);

-- ----------------------------------------------------------------------------
-- 9. ANALYTICAL VIEWS FOR URBAN LAB GIS INTERFACE (v4)
-- ----------------------------------------------------------------------------

-- 9A. Click-on-Map Location Dossier: binds any polygon/zone to its trust-tiered documents & events
CREATE VIEW IF NOT EXISTS v_geo_location_dossier AS
SELECT
    g.gazetteer_id,
    g.canonical_key,
    g.city_id,
    g.scale_level,
    g.feature_class,
    g.canonical_name,
    d.doc_id,
    d.doc_type,
    d.trust_tier,
    tt.tier_rank,
    tt.label_sr AS trust_label_sr,
    d.topic_primary,
    d.published_at,
    d.title,
    d.sentiment_score,
    d.primary_url,
    m.geo_role,
    m.geo_precision,
    m.geo_confidence,
    m.spatial_uncertainty_m,
    m.render_as_pin
FROM document_geo_mentions m
JOIN spatial_gazetteer g ON m.gazetteer_id = g.gazetteer_id
JOIN evidence_documents d ON m.doc_id = d.doc_id
JOIN trust_tiers tt ON d.trust_tier = tt.tier_code
ORDER BY tt.tier_rank ASC, d.published_at DESC;

-- 9B. Procurement Structural Risk Indicators by City & Year (objective metrics only)
CREATE VIEW IF NOT EXISTS v_procurement_structural_indicators AS
SELECT
    p.city_id,
    p.country_iso3,
    substr(p.award_date, 1, 4) AS award_year,
    COUNT(*) AS contracts_count,
    ROUND(SUM(p.contract_value_eur) / 1e6, 3) AS total_value_eur_m,
    SUM(p.single_bidder_flag) AS single_bidder_contracts,
    ROUND(100.0 * SUM(p.single_bidder_flag) / NULLIF(COUNT(*), 0), 2) AS single_bidder_pct,
    ROUND(AVG(p.value_to_estimate_ratio), 4) AS avg_contract_to_estimate_ratio,
    COUNT(DISTINCT p.winner_entity_id) AS unique_winners,
    COUNT(DISTINCT p.buyer_entity_id) AS unique_buyers
FROM domain_signals_procurement p
GROUP BY p.city_id, p.country_iso3, substr(p.award_date, 1, 4);

-- 9C. Event-Study Difference-in-Differences (DiD) Summary View
CREATE VIEW IF NOT EXISTS v_event_study_did_summary AS
WITH agg AS (
    SELECT
        o.study_id,
        o.cohort_group,
        CASE WHEN o.rel_period < 0 THEN 'pre' ELSE 'post' END AS phase,
        AVG(o.metric_value) AS mean_val,
        AVG(o.pct_change_vs_baseline) AS mean_pct_chg,
        COUNT(*) AS obs_n,
        MAX(tt.tier_rank) AS worst_tier_rank
    FROM event_study_observations o
    JOIN trust_tiers tt ON o.upstream_trust_tier = tt.tier_code
    GROUP BY o.study_id, o.cohort_group, CASE WHEN o.rel_period < 0 THEN 'pre' ELSE 'post' END
)
SELECT
    es.study_id,
    es.study_title,
    e.city_id,
    e.event_category,
    es.t0_anchor_type,
    es.t0_date,
    es.outcome_metric,
    es.identification_grade,
    es.min_upstream_tier,
    ROUND(t_pre.mean_val, 4) AS treated_pre_mean,
    ROUND(t_post.mean_val, 4) AS treated_post_mean,
    ROUND(t_post.mean_val - t_pre.mean_val, 4) AS treated_delta,
    ROUND(c_pre.mean_val, 4) AS control_pre_mean,
    ROUND(c_post.mean_val, 4) AS control_post_mean,
    ROUND(c_post.mean_val - c_pre.mean_val, 4) AS control_delta,
    ROUND((t_post.mean_val - t_pre.mean_val) - COALESCE(c_post.mean_val - c_pre.mean_val, 0.0), 4) AS did_estimate,
    ROUND(t_post.mean_pct_chg - COALESCE(c_post.mean_pct_chg, 0.0), 3) AS did_pct_points
FROM event_studies es
JOIN urban_events e ON es.event_id = e.event_id
LEFT JOIN agg t_pre  ON es.study_id = t_pre.study_id  AND t_pre.cohort_group  = 'treated_core'  AND t_pre.phase  = 'pre'
LEFT JOIN agg t_post ON es.study_id = t_post.study_id AND t_post.cohort_group = 'treated_core'  AND t_post.phase = 'post'
LEFT JOIN agg c_pre  ON es.study_id = c_pre.study_id  AND c_pre.cohort_group  = 'control_local' AND c_pre.phase  = 'pre'
LEFT JOIN agg c_post ON es.study_id = c_post.study_id AND c_post.cohort_group = 'control_local' AND c_post.phase = 'post';

-- 9D. Trust-Tier & Coverage Asymmetry Monitor across the 5 Cities
CREATE VIEW IF NOT EXISTS v_trust_tier_coverage_by_city AS
SELECT
    c.city_id,
    c.name AS city_name,
    c.population,
    COALESCE(d.trust_tier, 'NONE') AS trust_tier,
    COUNT(d.doc_id) AS docs_count,
    ROUND(COUNT(d.doc_id) * 100000.0 / NULLIF(c.population, 0), 2) AS docs_per_100k_pop,
    SUM(CASE WHEN d.doc_type IN ('procurement_notice','procurement_award') THEN 1 ELSE 0 END) AS procurement_docs,
    SUM(CASE WHEN d.doc_type IN ('scientific_paper','dissertation','eu_project_grant','patent_filing') THEN 1 ELSE 0 END) AS science_docs,
    SUM(CASE WHEN d.doc_type IN ('news_article','protest_event_record','investigative_report') THEN 1 ELSE 0 END) AS news_discourse_docs
FROM cities c
LEFT JOIN evidence_documents d ON c.city_id = d.primary_city_id
GROUP BY c.city_id, c.name, c.population, COALESCE(d.trust_tier, 'NONE');

-- 9E. Electoral Geography Station Metrics (Turnout, Winning Margin, Laakso-Taagepera ENP)
CREATE VIEW IF NOT EXISTS v_election_station_metrics AS
WITH shares AS (
    SELECT
        r.station_uid,
        r.list_or_candidate_name,
        r.comparative_bloc,
        r.votes_count,
        CASE WHEN ps.valid_ballots > 0 THEN 1.0 * r.votes_count / ps.valid_ballots ELSE 0.0 END AS s,
        ROW_NUMBER() OVER (PARTITION BY r.station_uid ORDER BY r.votes_count DESC, r.list_or_candidate_name ASC) AS rk
    FROM election_station_results r
    JOIN polling_stations ps ON r.station_uid = ps.station_uid
),
station_agg AS (
    SELECT
        station_uid,
        COUNT(*) AS lists_count,
        SUM(s * s) AS hhi_votes,
        CASE WHEN SUM(s * s) > 0 THEN ROUND(1.0 / SUM(s * s), 3) ELSE NULL END AS effective_num_parties_enp,
        MAX(CASE WHEN rk = 1 THEN list_or_candidate_name END) AS winner_list,
        MAX(CASE WHEN rk = 1 THEN comparative_bloc END) AS winner_bloc,
        ROUND(100.0 * MAX(CASE WHEN rk = 1 THEN s ELSE 0.0 END), 2) AS winner_share_pct,
        ROUND(100.0 * MAX(CASE WHEN rk = 2 THEN s ELSE 0.0 END), 2) AS runner_up_share_pct
    FROM shares
    GROUP BY station_uid
)
SELECT
    ps.station_uid,
    ps.election_id,
    ec.authority_body,
    ec.election_level,
    ec.election_date,
    ps.city_id,
    ps.municipality_name,
    ps.station_code,
    ps.station_name,
    ps.station_type,
    ps.gazetteer_id,
    g.canonical_name AS gazetteer_zone,
    g.dist_cbd_km,
    ps.registered_voters,
    ps.ballots_cast,
    ps.valid_ballots,
    ps.turnout_pct,
    ps.invalid_ballots_pct,
    sa.lists_count,
    sa.winner_list,
    sa.winner_bloc,
    sa.winner_share_pct,
    ROUND(sa.winner_share_pct - COALESCE(sa.runner_up_share_pct, 0.0), 2) AS winning_margin_pp,
    sa.effective_num_parties_enp
FROM polling_stations ps
JOIN election_cycles ec ON ps.election_id = ec.election_id
LEFT JOIN spatial_gazetteer g ON ps.gazetteer_id = g.gazetteer_id
LEFT JOIN station_agg sa ON ps.station_uid = sa.station_uid;

-- 9F. Electoral Competition vs. Public Procurement Capital Flow by Gazetteer Zone (Public Choice Join)
CREATE VIEW IF NOT EXISTS v_election_procurement_zone_join AS
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
    FROM v_election_station_metrics
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

-- 9G. XS Parcel Development Rent Gap (Existing 3D GFA vs. GUP/PDR/ISPU Allowed Envelope)
CREATE VIEW IF NOT EXISTS v_xs_development_rent_gap AS
WITH bldg_parcel AS (
    SELECT
        parcel_uid,
        COUNT(*) AS buildings_count,
        ROUND(SUM(footprint_area_m2), 2) AS existing_footprint_m2,
        ROUND(SUM(COALESCE(gross_floor_area_m2, footprint_area_m2 * COALESCE(floors_above_ground, MAX(1, CAST(ROUND(height_m / 3.1) AS INTEGER))))), 2) AS existing_gfa_m2,
        ROUND(SUM(volume_m3), 2) AS existing_volume_m3,
        ROUND(MAX(height_m), 2) AS max_existing_height_m
    FROM xs_buildings_3d
    WHERE parcel_uid IS NOT NULL
    GROUP BY parcel_uid
)
SELECT
    p.parcel_uid,
    p.city_id,
    p.cadastral_municipality,
    p.parcel_number,
    p.tax_zone_name,
    p.land_class,
    p.ownership_regime,
    p.area_m2 AS parcel_area_m2,
    z.envelope_uid,
    z.plan_name,
    z.zone_code,
    z.permitted_use,
    z.max_far,
    z.max_height_m AS allowed_max_height_m,
    COALESCE(bp.buildings_count, 0) AS buildings_count,
    COALESCE(bp.existing_footprint_m2, 0.0) AS existing_footprint_m2,
    COALESCE(bp.existing_gfa_m2, 0.0) AS existing_gfa_m2,
    COALESCE(bp.existing_volume_m3, 0.0) AS existing_volume_m3,
    ROUND(p.area_m2 * z.max_far, 2) AS max_allowed_gfa_m2,
    ROUND(MAX(0.0, (p.area_m2 * z.max_far) - COALESCE(bp.existing_gfa_m2, 0.0)), 2) AS unused_buildable_gfa_m2,
    CASE WHEN z.max_far IS NOT NULL AND z.max_far > 0
         THEN ROUND(100.0 * COALESCE(bp.existing_gfa_m2, 0.0) / (p.area_m2 * z.max_far), 2)
         ELSE NULL END AS far_utilization_pct,
    ROUND(
        MAX(0.0, (p.area_m2 * z.max_far) - COALESCE(bp.existing_gfa_m2, 0.0)) * COALESCE(p.market_est_eur_m2, p.assessed_tax_eur_m2),
        2
    ) AS implied_development_headroom_eur
FROM xs_cadastral_parcels p
LEFT JOIN xs_zoning_envelopes z
    ON p.parcel_uid = z.parcel_uid AND z.effective_to IS NULL
LEFT JOIN bldg_parcel bp
    ON p.parcel_uid = bp.parcel_uid;

-- 9H. 3D Urban Morphology & Heating/Energy Vulnerability by Gazetteer Zone
CREATE VIEW IF NOT EXISTS v_xs_3d_morphology_by_zone AS
SELECT
    b.city_id,
    b.gazetteer_id,
    g.canonical_name AS zone_name,
    g.dist_cbd_km,
    COUNT(*) AS buildings_count,
    ROUND(SUM(b.footprint_area_m2), 1) AS total_footprint_m2,
    ROUND(SUM(b.volume_m3), 1) AS total_volume_m3,
    ROUND(AVG(b.height_m), 2) AS avg_height_m,
    ROUND(MAX(b.height_m), 2) AS max_height_m,
    ROUND(100.0 * SUM(CASE WHEN b.heating_source = 'solid_fuel_coal_wood' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS solid_fuel_buildings_pct,
    ROUND(100.0 * SUM(CASE WHEN b.trust_tier IN ('A1', 'A2') THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS high_trust_3d_pct
FROM xs_buildings_3d b
LEFT JOIN spatial_gazetteer g ON b.gazetteer_id = g.gazetteer_id
GROUP BY b.city_id, b.gazetteer_id, g.canonical_name, g.dist_cbd_km;

COMMIT;
