# Urban Lab — inventar (generisano)

Generisano: 2026-11-22T12:41:54+00:00 · skripta `scripts/36_build_inventory.py` (samo čita). Ne uređuje se ručno.

## Baze

| Baza | Tabele | Pogledi | Neispravno |
|---|---|---|---|
| `curated/urban_lab_5cities_v4.sqlite` (135.4 MB) | 86 | 28 | — |
| `curated/urban_lab_5cities.sqlite` (37.2 MB) | 26 | 13 | v_osm_centrality_rings |

## Živa baza v4.2 — tabele sa podacima

Pomoćne FTS/R-tree tabele su izostavljene.

| Tabela | Redova | Kolona |
|---|---:|---:|
| `admin_units` | 362 | 22 |
| `apr_serbia_supply_chain` | 2926 | 14 |
| `cities` | 5 | 27 |
| `commuting_and_flows` | 31 | 12 |
| `companies_sr` | 66040 | 17 |
| `companies_sr_hinterland` | 7882 | 13 |
| `document_entity_mentions` | 2564 | 6 |
| `document_geo_mentions` | 2970 | 15 |
| `domain_signals_procurement` | 1850 | 16 |
| `domain_signals_science` | 638 | 13 |
| `domain_signals_sensors` | 1957 | 14 |
| `election_cycles` | 5 | 12 |
| `election_station_crosswalk` | 605 | 6 |
| `election_station_results` | 74025 | 12 |
| `entities` | 883 | 12 |
| `entity_aliases` | 1733 | 7 |
| `entity_identifiers` | 465 | 9 |
| `entity_relations` | 306 | 14 |
| `event_evidence_links` | 35 | 3 |
| `event_locations` | 5 | 5 |
| `event_studies` | 3 | 13 |
| `event_study_observations` | 36 | 13 |
| `evidence_documents` | 2942 | 20 |
| `fiscal_budgets` | 16 | 16 |
| `gazetteer_aliases` | 6218 | 7 |
| `hinterland_agri_forestry_trade` | 7 | 14 |
| `hinterland_units` | 36 | 16 |
| `macro_worldbank` | 120 | 6 |
| `mv_election_station_metrics` | 3479 | 24 |
| `ookla_broadband_tiles` | 5179 | 20 |
| `osm_landuse_major_zones` | 9650 | 12 |
| `osm_landuse_summary` | 373 | 7 |
| `osm_pois` | 77330 | 11 |
| `polling_stations` | 3479 | 24 |
| `property_tax_zones_gis_summary` | 21 | 14 |
| `property_zones_prices` | 194 | 11 |
| `provenance_claims` | 6 | 13 |
| `rzs_agri_census_2023` | 203 | 29 |
| `s_bakery_unit_model` | 5 | 16 |
| `s_scale_input_costs` | 5 | 17 |
| `schema_migrations` | 3 | 4 |
| `sector_structure` | 559 | 11 |
| `sepa_industrial_emissions` | 148 | 17 |
| `source_registry` | 40 | 13 |
| `sources_manifest` | 422 | 12 |
| `spatial_gazetteer` | 2043 | 24 |
| `transit_stops` | 10678 | 13 |
| `trust_tiers` | 5 | 9 |
| `urban_events` | 5 | 15 |
| `xl_corridors_projects_strategies` | 11 | 10 |
| `xl_macro_indicators` | 357 | 6 |
| `xl_regional_gdp_nuts3` | 81 | 9 |
| `xs_building_permits` | 5 | 18 |
| `xs_buildings_3d` | 32385 | 29 |
| `xs_cadastral_parcels` | 84 | 25 |
| `xs_zoning_envelopes` | 84 | 18 |
| `zagreb_budget_lines` | 7316 | 10 |
| `zagreb_commercial_leases` | 320 | 9 |
| `zagreb_markets` | 31 | 7 |
| `zagreb_real_estate_market` | 418 | 15 |

## Živa baza v4.2 — pogledi

| Pogled | Redova |
|---|---:|
| `v_5cities_landuse_profile` | 5 |
| `v_5cities_master_scorecard` | 5 |
| `v_beograd_opstine_economy` | 17 |
| `v_bid_rent_profiles` | 74 |
| `v_city_comparison` | 5 |
| `v_city_zone_profile_unified` | 388 |
| `v_data_quality_audit` | 19 |
| `v_election_procurement_zone_join` | 52 |
| `v_election_station_metrics` | 3479 |
| `v_event_study_did_summary` | 3 |
| `v_geo_location_dossier` | 2970 |
| `v_l_hinterland_summary` | 5 |
| `v_ookla_digital_divide_by_city` | 5 |
| `v_osm_5cities_centrality` | 25 |
| `v_osm_centrality_rings` | 361 |
| `v_procurement_buyer_supplier_network` | 573 |
| `v_procurement_structural_indicators` | 11 |
| `v_s_bakery_5cities_comparison` | 5 |
| `v_science_eu_grants_by_city` | 5 |
| `v_sector_specialization_lq` | 120 |
| `v_srb_supply_chain_by_muni` | 173 |
| `v_srb_wheat_mills_bakeries_balance` | 170 |
| `v_transit_accessibility_by_city` | 5 |
| `v_trust_tier_coverage_by_city` | 20 |
| `v_xl_country_structural_profile` | 33 |
| `v_xl_latest_nuts3_gdp` | 13 |
| `v_xs_3d_morphology_by_zone` | 76 |
| `v_xs_development_rent_gap` | 84 |

## Sirovi fajlovi (`raw/`)

| Folder | Fajlova | Masa |
|---|---:|---:|
| `raw/beograd` | 7 | 45.9 MB |
| `raw/common` | 27 | 21.3 MB |
| `raw/novi_pazar` | 8 | 6.3 MB |
| `raw/sarajevo` | 6 | 10.4 MB |
| `raw/travnik` | 6 | 4.0 MB |
| `raw/wave2_l` | 32 | 50.4 MB |
| `raw/wave2_osm` | 5 | 10.8 MB |
| `raw/wave2_xl` | 19 | 0.2 MB |
| `raw/wave3` | 32 | 23.5 MB |
| `raw/wave3_osm` | 10 | 9.1 MB |
| `raw/wave4` | 223 | 258.8 MB |
| `raw/wave5` | 21 | 29.8 MB |
| `raw/zagreb` | 41 | 39.4 MB |

## Manifest ↔ disk

- Redova u `manifest.jsonl`: 442 (uspešnih 355, neuspešnih 87); različitih lokalnih putanja: 398.
- Putanja iz manifesta kojih nema na disku: 54.
- Fajlova u `raw/`: 437; od toga bez reda u manifestu: 96.

### Fajlovi u `raw/` bez reda u manifestu

- `raw/common/apr_serbia_nace2_baseline.json`
- `raw/wave2_l/apr_bakery_supply_chain_core.json`
- `raw/wave2_l/apr_hinterland_summary.json`
- `raw/wave2_l/parsed_fzs_ks_2026_pages.json`
- `raw/wave2_l/parsed_fzs_sbk_2025_pages.json`
- `raw/wave2_l/parsed_fzs_zdk_2026_key.json`
- `raw/wave2_l/parsed_rzs_commuting_2022.json`
- `raw/wave2_l/parsed_zpr_ks_2025_pages.json`
- `raw/wave3/apr_hinterland_v3_summary.json`
- `raw/wave3/apr_serbia_supply_chain_summary.json`
- `raw/wave3/beograd_odluka_clean.txt`
- `raw/wave3/beograd_zones_parsed.json`
- `raw/wave3/novi_pazar_odluka_clean.txt`
- `raw/wave3/novi_pazar_zones_parsed.json`
- `raw/wave3/rzs_agri2023_all_munis.json`
- `raw/wave4/elections/cik_24_eu.bin`
- `raw/wave4/elections/cik_dbname_35.json`
- `raw/wave4/elections/cik_dbname_36.json`
- `raw/wave4/elections/cik_dbname_37.json`
- `raw/wave4/elections/cik_dbname_38.json`
- `raw/wave4/elections/cik_dbname_39.json`
- `raw/wave4/elections/cik_dbname_40.json`
- `raw/wave4/elections/cik_dbname_41.json`
- `raw/wave4/elections/cik_dbname_42.json`
- `raw/wave4/elections/cik_el_list_24.bin`
- `raw/wave4/elections/cik_test.bin`
- `raw/wave4/elections/dip_lok_2025.zip`
- `raw/wave4/elections/dip_parl_2024.zip`
- `raw/wave4/elections/parsed_cik_2024_sa_tr.json`
- `raw/wave4/elections/parsed_dip_2024_zagreb.json`
- `raw/wave4/elections/parsed_dip_2025_zagreb.json`
- `raw/wave4/elections/parsed_rik_2023_bg_np.json`
- `raw/wave4/mobility_and_permits/gtfs_stops_beograd_bg_suburban.json`
- `raw/wave4/mobility_and_permits/gtfs_stops_beograd_bg_urban.json`
- `raw/wave4/mobility_and_permits/gtfs_stops_zagreb_zet.json`
- `raw/wave4/mobility_and_permits/gtfs_zet_zagreb.zip`
- `raw/wave4/mobility_and_permits/gtfs_zet_zagreb_summary.json`
- `raw/wave4/mobility_and_permits/mobility_permits_summary.json`
- `raw/wave4/news/news_rss_gdelt_5cities.json`
- `raw/wave4/probes/cik_2024_root.bin`
- `raw/wave4/probes/cik_custom.js`
- `raw/wave4/probes/cik_customFunctions.js`
- `raw/wave4/probes/cik_home_index.js`
- `raw/wave4/probes/cik_race4_js.bin`
- `raw/wave4/probes/cik_race5_js.bin`
- `raw/wave4/probes/datagovhr_fiskal.bin`
- `raw/wave4/probes/datagovhr_izbori.bin`
- `raw/wave4/probes/datagovrs_gtfs.bin`
- `raw/wave4/probes/datagovrs_izbori.bin`
- `raw/wave4/probes/datagovrs_jn.bin`
- `raw/wave4/probes/datagovrs_rgz.bin`
- `raw/wave4/probes/datazagreb_3d.bin`
- `raw/wave4/probes/datazagreb_nabava.bin`
- `raw/wave4/probes/dip_477.html`
- `raw/wave4/probes/dip_lok_2021_zip.bin`
- `raw/wave4/probes/dip_lok_2025_zip.bin`
- `raw/wave4/probes/dip_open_page.bin`
- `raw/wave4/probes/dip_parl_2024_page.bin`
- `raw/wave4/probes/dip_parl_2024_zip.bin`
- `raw/wave4/probes/ejn_admin_units.bin`
- `raw/wave4/probes/ejn_an_sample.bin`
- `raw/wave4/probes/ejn_ca_sa.bin`
- `raw/wave4/probes/ejn_ca_tr.bin`
- `raw/wave4/probes/ejn_swagger.bin`
- `raw/wave4/probes/ookla_list.bin`
- `raw/wave4/probes/openalex_bg.bin`
- `raw/wave4/probes/openmeteo_aq.bin`
- `raw/wave4/probes/probe_summary.json`
- `raw/wave4/probes/rez_izb_rs.bin`
- `raw/wave4/probes/rs_datasets_nabavk.bin`
- `raw/wave4/probes/rs_dozvole_cyr.json`
- `raw/wave4/probes/rs_jn_cyr.json`
- `raw/wave4/probes/rs_orgs_rik.bin`
- `raw/wave4/probes/rs_orgs_ujn.bin`
- `raw/wave4/probes/rs_rgz_cyr.json`
- `raw/wave4/probes/rs_vazduh_cyr.json`
- `raw/wave4/probes/rss_biznisinfo.bin`
- `raw/wave4/probes/rss_freemedia.bin`
- `raw/wave4/probes/rss_poslovni.bin`
- `raw/wave4/probes/rss_stoplus.bin`
- `raw/wave4/probes/rss_travnikgrad.bin`
- `raw/wave4/probes/worldbank_remit.bin`
- `raw/wave4/probes/zet_dl.html`
- `raw/wave4/probes/zet_gtfs_direct.bin`
- `raw/wave4/probes/zet_gtfs_page.bin`
- `raw/wave4/procurement_bih/ejn_awards_sarajevo_travnik_consolidated.json`
- `raw/wave4/science/openalex_collab_matrix_5cities.json`
- `raw/wave4/science/openalex_eu_funded_5cities.json`
- `raw/wave4/science/openalex_institutions_5cities.json`
- `raw/wave4/science/openalex_works_about_5cities.json`
- `raw/wave4/sensors/openmeteo_air_monthly_5cities.json`
- `raw/wave4/sensors/openmeteo_weather_monthly_5cities.json`
- `raw/wave4/sensors/worldbank_diaspora_macro_3countries.json`
- `raw/wave4/xs_3d/xs_buildings_3d_5cities_consolidated.json`
- `raw/wave5/cordis/cordis_5cities_consolidated.json`
- `raw/wave5/osm_and_sensors/sensor_community_5cities_snapshot.json`
