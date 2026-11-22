# Skripte — indeks (generisano)

Generiše `36_build_inventory.py`. Skripte ostaju u jednom folderu: uvoze `common_net.py` iz istog foldera i većina ima apsolutnu putanju do `urban_lab_db`.
Vrsta je izvedena iz imena fajla. Slovo iza broja (b, c, d…) znači popravku ili nastavak istog koraka; koja varijanta je dala konačan fajl nije ovde utvrđeno.

## Talas 1 — osnovne baze 5 gradova → baza v1

| Skripta | Vrsta |
|---|---|
| `01_collect_serbia_apr_docs.py` | sakupljanje |
| `01b_collect_serbia_apr_and_rzs_gis.py` | sakupljanje |
| `01c_collect_apr_fixed.py` | sakupljanje |
| `02_collect_zagreb_hr.py` | sakupljanje |
| `02b_collect_zagreb_od_3d.py` | sakupljanje |
| `03_collect_bih_sarajevo_travnik.py` | sakupljanje |
| `03b_collect_bih_budgets.py` | sakupljanje |
| `04_collect_osm_comparative_gis.py` | sakupljanje |
| `04b_collect_osm_remaining.py` | sakupljanje |
| `04c_collect_osm_fast.py` | sakupljanje |
| `04d_collect_osm_alt.py` | sakupljanje |
| `05_build_urban_lab_db.py` | gradnja baze |
| `06_verify_and_analyze_db.py` | analiza |

## Talas 2 — makro (XL), zaleđe (L), lanci snabdevanja (S) → baza v2

| Skripta | Vrsta |
|---|---|
| `07_collect_wave2_macro_eurostat_wb.py` | sakupljanje |
| `07a_inspect_existing_sources.py` | sonda |
| `07b_fix_eurostat_and_zdk.py` | sakupljanje |
| `07c_check_geofabrik_zdk_wb.py` | sonda |
| `07d_fetch_zdk_and_parse_all_wave2.py` | obrada |
| `07e_fetch_raska_nuts3_and_zdk_sbk_extract.py` | obrada |
| `08_collect_wave2_hinterland_l.py` | sakupljanje |
| `09_collect_wave2_osm_supply_chain.py` | sakupljanje |
| `09b_geofabrik_range_osm_extract.py` | obrada |
| `10_extract_wave2_pdfs.py` | obrada |
| `10b_read_fzs_tables.py` | sonda |
| `10c_inspect_wave2_tables.py` | sonda |
| `10d_read_raska_and_ks.py` | sonda |
| `11_build_urban_lab_db_v2.py` | gradnja baze |

## Talas 3 — APR Srbija, Popis poljoprivrede 2023, poreske zone, landuse → baza v3

| Skripta | Vrsta |
|---|---|
| `12_inspect_wave3_prereqs.py` | sonda |
| `13_collect_wave3_apr_srb_supply_chain.py` | sakupljanje |
| `13b_fix_apr_hinterland_exact_codes.py` | sakupljanje |
| `14_collect_wave3_rzs_agri2023_and_bg_naselja.py` | sakupljanje |
| `14b_inspect_agri2023_and_pancevo_code.py` | sonda |
| `14c_inspect_agri2023_cols.py` | sonda |
| `14d_parse_rzs_agri2023_full.py` | obrada |
| `15a_parse_tax_decisions.py` | obrada |
| `15b_digitize_tax_zones_bg_np.py` | obrada |
| `16_collect_wave3_geofabrik_landuse_stream.py` | sakupljanje |
| `17_build_urban_lab_db_v3.py` | gradnja baze |

## Analitička studija nad v3

| Skripta | Vrsta |
|---|---|
| `18_inspect_v3_for_study.py` | sonda |
| `19_run_v3_analytics.py` | analiza |
| `20_deep_extract_and_charts.py` | analiza |

## Talas 4 — nauka, nabavke, vesti, senzori, izbori, 3D zgrade → baza v4.1

| Skripta | Vrsta |
|---|---|
| `21_wave4_science_openalex.py` | sakupljanje |
| `21a_probe_wave4_endpoints.py` | sonda |
| `21b_parse_probes.py` | sonda |
| `21c_inspect_ejn_cik_dip.py` | sonda |
| `21d_wave4_science_works_fix.py` | sakupljanje |
| `21e_wave4_science_about_deep.py` | sakupljanje |
| `22_wave4_procurement_bih_ejn.py` | sakupljanje |
| `23_wave4_news_gdelt_local_rss.py` | sakupljanje |
| `23b_gdelt_sarajevo_travnik_retry.py` | sakupljanje |
| `24_wave4_sensors_air_weather_wb.py` | sakupljanje |
| `24b_wave4_gtfs_and_rzs_permits.py` | sakupljanje |
| `25_wave4_elections_all_5cities.py` | sakupljanje |
| `25a_discover_elections_gtfs_permits.py` | sonda |
| `25b_probe_elections_exact_apis.py` | sonda |
| `25c_inspect_elections_formats.py` | sonda |
| `25d_parse_rik_dip_and_fetch_cik.py` | obrada |
| `25e_finalize_elections_5cities.py` | sakupljanje |
| `25f_fetch_cik_2024_sarajevo_travnik.py` | sakupljanje |
| `25g_fetch_cik_2024_full_bih.py` | sakupljanje |
| `25h_cik_exact_probe.py` | sonda |
| `25i_collect_cik_2024_final.py` | sakupljanje |
| `26_wave4_xs_3d_buildings_5cities.py` | sakupljanje |
| `26b_wave4_xs_3d_fast.py` | sakupljanje |
| `26c_add_beograd_3d_osm.py` | sakupljanje |
| `26d_patch_np_tr_3d.py` | sakupljanje |
| `27a_bootstrap_v4_gazetteer.py` | gradnja baze |
| `27b_load_wave4_into_v4_db.py` | gradnja baze |
| `28_wave4_deep_analytics.py` | analiza |

## Talas 5 — TED, CORDIS, Ookla, tranzit → baza v4.2

| Skripta | Vrsta |
|---|---|
| `29_audit_v4_gaps.py` | sonda |
| `30_probe_wave5_apis.py` | sonda |
| `30b_probe_wave5_details.py` | sonda |
| `30c_discover_wave5_resources.py` | sonda |
| `31_wave5_collect_procurement_ted_ejn.py` | sakupljanje |
| `31b_wave5_fetch_ted_gentle.py` | sakupljanje |
| `32_wave5_collect_cordis_eurostat_zg_rs.py` | sakupljanje |
| `32b_parse_cordis_and_inspect_zg.py` | sonda |
| `33_wave5_collect_osm_buildings_transit_sensors.py` | sakupljanje |
| `33b_wave5_geofabrik_np_tr_3d_and_transit.py` | sakupljanje |
| `34_wave5_collect_ookla_5cities.py` | sakupljanje |
| `35_upgrade_db_to_v4_2.py` | gradnja baze |

## Održavanje

| Skripta | Vrsta |
|---|---|
| `36_build_inventory.py` | analiza |

## Zajedničko

- `common_net.py` — mrežni sloj i upis u `manifest.jsonl`; uvoze ga ostale skripte.
