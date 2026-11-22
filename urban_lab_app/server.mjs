#!/usr/bin/env node
/**
 * Urban Lab "Ekonomija grada" — Live v4.2 Spatial API & Static Server
 * Zero external npm dependencies (uses Node 24 built-in node:http + node:sqlite).
 * Strictly read-only against urban_lab_5cities_v4.sqlite.
 */
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { DatabaseSync } from 'node:sqlite';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PUBLIC_DIR = path.resolve(__dirname, '../docs'); // isti statički sajt koji služi GitHub Pages
const DB_PATH = process.env.URBAN_LAB_DB || path.resolve(__dirname, '../urban_lab_db/curated/urban_lab_5cities_v4.sqlite');
const BOUNDARIES_DIR = path.resolve(__dirname, '../urban_lab_db/curated/boundaries');

function parsePort() {
  const idx = process.argv.indexOf('--port');
  if (idx !== -1 && process.argv[idx + 1]) return Number(process.argv[idx + 1]);
  if (process.env.PORT) return Number(process.env.PORT);
  return 8787;
}
const PORT = parsePort();
const HOST = process.env.HOST || '127.0.0.1';

if (!fs.existsSync(DB_PATH)) {
  console.error(`[FATAL] SQLite database not found at: ${DB_PATH}`);
  process.exit(1);
}

const db = new DatabaseSync(DB_PATH, { readOnly: true });
const STARTED_AT = new Date().toISOString();

const ALL_TIERS = ['A1', 'A2', 'B', 'C', 'D'];
function parseTiers(raw) {
  if (!raw) return ALL_TIERS;
  const list = String(raw).split(',').map(s => s.trim().toUpperCase()).filter(t => ALL_TIERS.includes(t));
  return list.length ? list : ALL_TIERS;
}

function tierInClause(tiers) {
  return tiers.map(() => '?').join(',');
}

function norm(s) {
  return String(s || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

function parseBbox(raw) {
  if (!raw) return null;
  const parts = String(raw).split(',').map(Number);
  if (parts.length !== 4 || parts.some(n => !Number.isFinite(n))) return null;
  return { minLon: parts[0], minLat: parts[1], maxLon: parts[2], maxLat: parts[3] };
}

function bboxToPolygon(minLon, minLat, maxLon, maxLat) {
  return {
    type: 'Polygon',
    coordinates: [[
      [minLon, minLat],
      [maxLon, minLat],
      [maxLon, maxLat],
      [minLon, maxLat],
      [minLon, minLat]
    ]]
  };
}

function ringCentroid(coords) {
  if (!coords || !coords.length) return [0, 0];
  let x = 0, y = 0, n = 0;
  for (const pt of coords) {
    if (Array.isArray(pt) && pt.length >= 2) {
      x += pt[0];
      y += pt[1];
      n++;
    }
  }
  return n ? [x / n, y / n] : [0, 0];
}

function featureCentroid(geom) {
  if (!geom) return [0, 0];
  if (geom.type === 'Point') return geom.coordinates;
  if (geom.type === 'Polygon') return ringCentroid(geom.coordinates[0]);
  if (geom.type === 'MultiPolygon') {
    let bestRing = geom.coordinates[0]?.[0] || [];
    for (const poly of geom.coordinates) {
      if (poly[0] && poly[0].length > bestRing.length) bestRing = poly[0];
    }
    return ringCentroid(bestRing);
  }
  return [0, 0];
}

// ---------------------------------------------------------------------------
// Preload Gazetteer Lookup & Enriched GeoJSON Caches
// ---------------------------------------------------------------------------
const gazByCityName = new Map();
const gazById = new Map();
for (const z of db.prepare(`SELECT * FROM spatial_gazetteer`).all()) {
  gazById.set(z.gazetteer_id, z);
  const k = `${z.city_id}|${norm(z.canonical_name)}`;
  if (!gazByCityName.has(k)) gazByCityName.set(k, z);
}

const zoneProfileById = new Map();
for (const zp of db.prepare(`SELECT * FROM v_city_zone_profile_unified`).all()) {
  zoneProfileById.set(zp.gazetteer_id, zp);
}

const adminPriceByCityName = new Map();
for (const a of db.prepare(`SELECT city_id, unit_name, avg_apt_price_eur_m2, avg_net_wage_eur, companies_count, companies_rev_eur_m, employees, density_per_km2, population FROM admin_units`).all()) {
  adminPriceByCityName.set(`${a.city_id}|${norm(a.unit_name)}`, a);
}

const cityRows = db.prepare(`SELECT * FROM cities`).all();
const cityMap = new Map(cityRows.map(c => [c.city_id, c]));

const geoCache = new Map();
function loadRawGeoJSON(filename) {
  if (geoCache.has(filename)) return geoCache.get(filename);
  const full = path.join(BOUNDARIES_DIR, filename);
  if (!fs.existsSync(full)) return { type: 'FeatureCollection', features: [] };
  const data = JSON.parse(fs.readFileSync(full, 'utf8'));
  geoCache.set(filename, data);
  return data;
}

function buildEnrichedAdminUnits() {
  const raw = loadRawGeoJSON('all_5cities_admin_units.geojson');
  const features = raw.features.map(f => {
    const p = { ...f.properties };
    const key = `${p.city_id}|${norm(p.unit_name)}`;
    const gaz = gazByCityName.get(key);
    const prof = gaz ? zoneProfileById.get(gaz.gazetteer_id) : null;
    const adm = adminPriceByCityName.get(key);
    const city = cityMap.get(p.city_id);

    const aptPrice = p.avg_apt_price_eur_m2 ?? adm?.avg_apt_price_eur_m2 ?? city?.avg_apt_price_eur_m2 ?? null;
    const wage = p.avg_net_wage_eur ?? adm?.avg_net_wage_eur ?? city?.avg_net_wage_eur ?? null;
    const affordabilityYrs = (aptPrice && wage) ? Number(((aptPrice * 55) / (wage * 12)).toFixed(2)) : null;

    return {
      type: 'Feature',
      geometry: f.geometry,
      properties: {
        ...p,
        gazetteer_id: gaz?.gazetteer_id ?? null,
        canonical_key: gaz?.canonical_key ?? null,
        scale_level: gaz?.scale_level ?? 'M',
        feature_class: gaz?.feature_class ?? 'municipality',
        ring: gaz?.ring ?? null,
        trust_tier: gaz?.trust_tier ?? 'A2',
        avg_apt_price_eur_m2: aptPrice,
        avg_net_wage_eur: wage,
        affordability_years_55m2: affordabilityYrs,
        companies_count: p.companies_count ?? adm?.companies_count ?? null,
        companies_rev_eur_m: p.companies_rev_eur_m ?? adm?.companies_rev_eur_m ?? null,
        polling_stations_n: prof?.polling_stations_n ?? 0,
        avg_turnout_pct: prof?.avg_turnout_pct ?? null,
        avg_margin_pp: prof?.avg_margin_pp ?? null,
        avg_enp: prof?.avg_enp ?? null,
        procurement_contracts_n: prof?.procurement_contracts_n ?? 0,
        procurement_eur_m: prof?.procurement_eur_m ?? 0,
        single_bidder_pct: prof?.single_bidder_pct ?? null,
        buildings_3d_n: prof?.buildings_3d_n ?? 0,
        bldg_volume_mio_m3: prof?.bldg_volume_mio_m3 ?? 0,
        avg_bldg_height_m: prof?.avg_bldg_height_m ?? null,
        transit_stops_n: prof?.transit_stops_n ?? 0,
        ookla_tiles_n: prof?.ookla_tiles_n ?? 0,
        avg_fixed_dl_mbps: prof?.avg_fixed_dl_mbps ?? null,
        linked_docs_n: prof?.linked_docs_n ?? 0
      }
    };
  });
  return { type: 'FeatureCollection', features };
}

function buildEnrichedSubzones(kind) {
  if (kind === 'zagreb_mo') {
    const raw = loadRawGeoJSON('zagreb_218_mjesnih_odbora.geojson');
    return {
      type: 'FeatureCollection',
      features: raw.features.map(f => {
        const name = f.properties.JMS_IME || 'Nepoznato';
        const gaz = gazByCityName.get(`zagreb|${norm(name)}`);
        const prof = gaz ? zoneProfileById.get(gaz.gazetteer_id) : null;
        return {
          type: 'Feature',
          geometry: f.geometry,
          properties: {
            city_id: 'zagreb',
            unit_name: name,
            unit_code: f.properties.JMS_MB,
            scale_level: 'S',
            feature_class: 'mjesni_odbor',
            gazetteer_id: gaz?.gazetteer_id ?? null,
            trust_tier: 'A1',
            dist_cbd_km: gaz?.dist_cbd_km ?? null,
            buildings_3d_n: prof?.buildings_3d_n ?? 0,
            avg_bldg_height_m: prof?.avg_bldg_height_m ?? null,
            transit_stops_n: prof?.transit_stops_n ?? 0,
            avg_fixed_dl_mbps: prof?.avg_fixed_dl_mbps ?? null,
            linked_docs_n: prof?.linked_docs_n ?? 0
          }
        };
      })
    };
  }
  if (kind === 'np_naselja') {
    const raw = loadRawGeoJSON('novi_pazar_99_naselja_popis2022.geojson');
    return {
      type: 'FeatureCollection',
      features: raw.features.map(f => {
        const name = f.properties.ter_imel || f.properties.nter || 'Nepoznato';
        const gaz = gazByCityName.get(`novi_pazar|${norm(name)}`);
        const prof = gaz ? zoneProfileById.get(gaz.gazetteer_id) : null;
        return {
          type: 'Feature',
          geometry: f.geometry,
          properties: {
            city_id: 'novi_pazar',
            unit_name: name,
            population: f.properties.vrednost ?? null,
            scale_level: 'S',
            feature_class: 'settlement_naselje',
            gazetteer_id: gaz?.gazetteer_id ?? null,
            trust_tier: 'A2',
            dist_cbd_km: gaz?.dist_cbd_km ?? null,
            buildings_3d_n: prof?.buildings_3d_n ?? 0,
            avg_bldg_height_m: prof?.avg_bldg_height_m ?? null,
            avg_fixed_dl_mbps: prof?.avg_fixed_dl_mbps ?? null,
            polling_stations_n: prof?.polling_stations_n ?? 0,
            avg_turnout_pct: prof?.avg_turnout_pct ?? null
          }
        };
      })
    };
  }
  if (kind === 'hinterland') {
    const raw = loadRawGeoJSON('all_5cities_hinterland_l.geojson');
    return {
      type: 'FeatureCollection',
      features: raw.features.map(f => {
        const p = f.properties;
        const gaz = gazByCityName.get(`${p.city_hub}|${norm(p.unit_name)}`);
        return {
          type: 'Feature',
          geometry: f.geometry,
          properties: {
            ...p,
            city_id: p.city_hub,
            gazetteer_id: gaz?.gazetteer_id ?? null,
            scale_level: 'L',
            feature_class: 'hinterland_unit',
            trust_tier: 'A2'
          }
        };
      })
    };
  }
  if (kind === 'tax_zones') {
    const bg = loadRawGeoJSON('beograd_poreske_zone_2026.geojson');
    const np = loadRawGeoJSON('novi_pazar_poreske_zone_2026.geojson');
    const mapFeat = (f, cid) => {
      const p = f.properties;
      const gaz = gazByCityName.get(`${cid}|${norm(p.zone_name)}`) || gazByCityName.get(`${cid}|${norm(p.municipality)}`);
      return {
        type: 'Feature',
        geometry: f.geometry,
        properties: {
          ...p,
          city_id: cid,
          unit_name: `${p.zone_name}${p.sub_area ? ' — ' + p.sub_area : ''}`,
          gazetteer_id: gaz?.gazetteer_id ?? null,
          trust_tier: 'A1'
        }
      };
    };
    return {
      type: 'FeatureCollection',
      features: [
        ...bg.features.map(f => mapFeat(f, 'beograd')),
        ...np.features.map(f => mapFeat(f, 'novi_pazar'))
      ]
    };
  }
  return { type: 'FeatureCollection', features: [] };
}

const ENRICHED_ADMIN = buildEnrichedAdminUnits();
const ENRICHED_ZG_MO = buildEnrichedSubzones('zagreb_mo');
const ENRICHED_NP_NASELJA = buildEnrichedSubzones('np_naselja');
const ENRICHED_HINTERLAND = buildEnrichedSubzones('hinterland');
let ENRICHED_TAX_ZONES = null; // lazy load (10.6 MB combined)

function getTaxZones() {
  if (!ENRICHED_TAX_ZONES) ENRICHED_TAX_ZONES = buildEnrichedSubzones('tax_zones');
  return ENRICHED_TAX_ZONES;
}

// ---------------------------------------------------------------------------
// API Route Handlers
// ---------------------------------------------------------------------------
function handleHealth() {
  const stat = fs.statSync(DB_PATH);
  const mig = db.prepare(`SELECT version, applied_at FROM schema_migrations ORDER BY rowid DESC LIMIT 1`).get();
  const audit = db.prepare(`SELECT * FROM v_data_quality_audit`).all();
  return {
    ok: true,
    started_at: STARTED_AT,
    db_file: path.basename(DB_PATH),
    db_size_mb: Number((stat.size / (1024 * 1024)).toFixed(2)),
    schema_version: mig?.version || 'v4.2.0-upgrade',
    tables_audit: audit
  };
}

function handleBootstrap() {
  const scorecard = db.prepare(`SELECT * FROM v_5cities_master_scorecard`).all();
  const cityComp = db.prepare(`SELECT * FROM v_city_comparison`).all();
  const compMap = new Map(cityComp.map(r => [r.city_id, r]));

  const cities = scorecard.map(s => {
    const c = cityMap.get(s.city_id) || {};
    const cc = compMap.get(s.city_id) || {};
    return {
      ...s,
      cbd_lat: c.cbd_lat,
      cbd_lon: c.cbd_lon,
      currency: c.currency,
      fx_to_eur: c.fx_to_eur,
      governance_model: c.governance_model,
      area_km2: c.area_km2,
      density_per_km2: c.density_per_km2,
      budget_scope: c.budget_scope,
      price_basis: c.price_basis,
      wage_period: c.wage_period,
      notes: c.notes,
      affordability_m2_per_wage: cc.affordability_m2_per_wage ?? null,
      years_wage_for_55m2: cc.years_wage_for_55m2 ?? null,
      budget_2026_eur_m: cc.budget_2026_eur_m ?? null
    };
  });

  const eventStudies = db.prepare(`SELECT * FROM v_event_study_did_summary`).all();
  const studyMeta = db.prepare(`SELECT study_id, hypothesis, treatment_definition, control_definition, outcome_unit, effective_trust_tier FROM event_studies`).all();
  const studyMetaMap = new Map(studyMeta.map(m => [m.study_id, m]));
  const studyObs = db.prepare(`SELECT * FROM event_study_observations ORDER BY study_id, cohort_group, rel_period`).all();
  const obsByStudy = new Map();
  for (const o of studyObs) {
    if (!obsByStudy.has(o.study_id)) obsByStudy.set(o.study_id, []);
    obsByStudy.get(o.study_id).push(o);
  }

  return {
    cities,
    trust_tiers: db.prepare(`SELECT * FROM trust_tiers ORDER BY tier_rank`).all(),
    ookla_divide: db.prepare(`SELECT * FROM v_ookla_digital_divide_by_city ORDER BY weighted_dl_mbps DESC`).all(),
    bakery_model: db.prepare(`SELECT * FROM v_s_bakery_5cities_comparison`).all(),
    bakery_inputs: db.prepare(`SELECT * FROM s_scale_input_costs`).all(),
    transit_summary: db.prepare(`SELECT * FROM v_transit_accessibility_by_city ORDER BY stops_total DESC`).all(),
    science_summary: db.prepare(`SELECT * FROM v_science_eu_grants_by_city ORDER BY eu_grants_total_eur_m DESC`).all(),
    trust_coverage: db.prepare(`SELECT * FROM v_trust_tier_coverage_by_city ORDER BY city_id, trust_tier`).all(),
    landuse_profile: db.prepare(`SELECT * FROM v_5cities_landuse_profile`).all(),
    hinterland_summary: db.prepare(`SELECT * FROM v_l_hinterland_summary`).all(),
    xl_corridors: db.prepare(`SELECT * FROM xl_corridors_projects_strategies`).all(),
    xl_nuts3: db.prepare(`SELECT * FROM v_xl_latest_nuts3_gdp ORDER BY gdp_eur_per_capita DESC`).all(),
    xl_macro: db.prepare(`SELECT * FROM v_xl_country_structural_profile`).all(),
    election_cycles: db.prepare(`SELECT * FROM election_cycles ORDER BY election_date DESC`).all(),
    urban_events: db.prepare(`SELECT * FROM urban_events ORDER BY primary_t0 DESC`).all(),
    event_studies: eventStudies.map(es => ({
      ...es,
      ...(studyMetaMap.get(es.study_id) || {}),
      observations: obsByStudy.get(es.study_id) || []
    })),
    provenance_claims: db.prepare(`SELECT * FROM provenance_claims ORDER BY claim_id`).all(),
    data_quality: db.prepare(`SELECT * FROM v_data_quality_audit`).all(),
    procurement_structural: db.prepare(`SELECT * FROM v_procurement_structural_indicators ORDER BY city_id, award_year DESC`).all()
  };
}

function handleZonesLayer(url) {
  const kind = url.searchParams.get('kind') || 'admin';
  const city = url.searchParams.get('city') || 'all';
  const tiers = parseTiers(url.searchParams.get('tiers'));

  let fc;
  if (kind === 'admin') fc = ENRICHED_ADMIN;
  else if (kind === 'zagreb_mo') fc = ENRICHED_ZG_MO;
  else if (kind === 'np_naselja') fc = ENRICHED_NP_NASELJA;
  else if (kind === 'hinterland') fc = ENRICHED_HINTERLAND;
  else if (kind === 'tax_zones') fc = getTaxZones();
  else if (kind === 'corridors') fc = loadRawGeoJSON('xl_strategic_corridors.geojson');
  else if (kind === 'bakeries') fc = loadRawGeoJSON('s_scale_bakeries_markets_5cities.geojson');
  else if (kind === 'landuse') fc = loadRawGeoJSON('all_5cities_osm_landuse.geojson');
  else if (kind === 'grid_1km') {
    const file = city === 'novi_pazar' ? 'novi_pazar_grid_1km_popis2022.geojson' : 'beograd_grid_1km_popis2022.geojson';
    fc = loadRawGeoJSON(file);
  } else {
    fc = ENRICHED_ADMIN;
  }

  let feats = fc.features || [];
  if (city && city !== 'all' && kind !== 'corridors' && kind !== 'grid_1km') {
    feats = feats.filter(f => (f.properties.city_id || f.properties.city_hub) === city);
  }
  if (kind === 'admin' || kind === 'zagreb_mo' || kind === 'np_naselja' || kind === 'hinterland' || kind === 'tax_zones') {
    feats = feats.filter(f => !f.properties.trust_tier || tiers.includes(f.properties.trust_tier));
  }
  return { type: 'FeatureCollection', features: feats };
}

function handleBuildings3D(url) {
  const city = url.searchParams.get('city') || 'all';
  const tiers = parseTiers(url.searchParams.get('tiers'));
  const bbox = parseBbox(url.searchParams.get('bbox'));
  const limit = Math.min(Math.max(Number(url.searchParams.get('limit') || 3200), 100), 8000);

  const params = [];
  let sql;
  if (bbox) {
    sql = `
      SELECT b.building_uid, b.city_id, b.parcel_uid, b.gazetteer_id, b.building_name, b.address_text,
             b.building_use, b.footprint_area_m2, b.height_m, b.floors_above_ground,
             b.gross_floor_area_m2, b.volume_m3, b.height_source, b.heating_source, b.trust_tier,
             b.min_lon, b.max_lon, b.min_lat, b.max_lat
      FROM xs_buildings_rtree r
      JOIN xs_buildings_3d b ON b.rowid = r.bldg_rowid
      WHERE r.max_lon >= ? AND r.min_lon <= ? AND r.max_lat >= ? AND r.min_lat <= ?
        AND b.trust_tier IN (${tierInClause(tiers)})
    `;
    params.push(bbox.minLon, bbox.maxLon, bbox.minLat, bbox.maxLat, ...tiers);
  } else {
    sql = `
      SELECT b.building_uid, b.city_id, b.parcel_uid, b.gazetteer_id, b.building_name, b.address_text,
             b.building_use, b.footprint_area_m2, b.height_m, b.floors_above_ground,
             b.gross_floor_area_m2, b.volume_m3, b.height_source, b.heating_source, b.trust_tier,
             b.min_lon, b.max_lon, b.min_lat, b.max_lat
      FROM xs_buildings_3d b
      WHERE b.trust_tier IN (${tierInClause(tiers)})
    `;
    params.push(...tiers);
  }
  if (city && city !== 'all') {
    sql += ` AND b.city_id = ?`;
    params.push(city);
  }
  sql += ` ORDER BY COALESCE(b.height_m, 0) DESC, COALESCE(b.footprint_area_m2, 0) DESC LIMIT ?`;
  params.push(limit);

  const rows = db.prepare(sql).all(...params);
  const features = [];
  for (const r of rows) {
    if (r.min_lon == null || r.max_lon == null || r.min_lat == null || r.max_lat == null) continue;
    features.push({
      type: 'Feature',
      geometry: bboxToPolygon(r.min_lon, r.min_lat, r.max_lon, r.max_lat),
      properties: {
        building_uid: r.building_uid,
        city_id: r.city_id,
        parcel_uid: r.parcel_uid,
        gazetteer_id: r.gazetteer_id,
        building_name: r.building_name,
        address_text: r.address_text,
        building_use: r.building_use || 'unknown',
        footprint_area_m2: r.footprint_area_m2,
        height_m: Number(r.height_m || 6),
        floors_above_ground: r.floors_above_ground,
        gross_floor_area_m2: r.gross_floor_area_m2,
        volume_m3: r.volume_m3,
        height_source: r.height_source,
        heating_source: r.heating_source,
        trust_tier: r.trust_tier
      }
    });
  }
  return {
    type: 'FeatureCollection',
    meta: { returned: features.length, limit, tiers, city },
    features
  };
}

function handleOokla(url) {
  const city = url.searchParams.get('city') || 'all';
  const tiers = parseTiers(url.searchParams.get('tiers'));
  const bbox = parseBbox(url.searchParams.get('bbox'));

  const params = [];
  let sql;
  if (bbox) {
    sql = `
      SELECT o.tile_uid, o.city_id, o.gazetteer_id, o.avg_d_mbps, o.avg_u_mbps, o.avg_lat_ms,
             o.tests_count, o.devices_count, o.dist_cbd_km, o.trust_tier, o.quarter,
             o.min_lon, o.max_lon, o.min_lat, o.max_lat
      FROM ookla_tiles_rtree r
      JOIN ookla_broadband_tiles o ON o.rowid = r.tile_rowid
      WHERE r.max_lon >= ? AND r.min_lon <= ? AND r.max_lat >= ? AND r.min_lat <= ?
        AND o.trust_tier IN (${tierInClause(tiers)})
    `;
    params.push(bbox.minLon, bbox.maxLon, bbox.minLat, bbox.maxLat, ...tiers);
  } else {
    sql = `
      SELECT o.tile_uid, o.city_id, o.gazetteer_id, o.avg_d_mbps, o.avg_u_mbps, o.avg_lat_ms,
             o.tests_count, o.devices_count, o.dist_cbd_km, o.trust_tier, o.quarter,
             o.min_lon, o.max_lon, o.min_lat, o.max_lat
      FROM ookla_broadband_tiles o
      WHERE o.trust_tier IN (${tierInClause(tiers)})
    `;
    params.push(...tiers);
  }
  if (city && city !== 'all') {
    sql += ` AND o.city_id = ?`;
    params.push(city);
  }
  sql += ` LIMIT 5500`;

  const rows = db.prepare(sql).all(...params);
  const features = rows.map(r => ({
    type: 'Feature',
    geometry: bboxToPolygon(r.min_lon, r.min_lat, r.max_lon, r.max_lat),
    properties: {
      tile_uid: r.tile_uid,
      city_id: r.city_id,
      gazetteer_id: r.gazetteer_id,
      avg_d_mbps: Number(r.avg_d_mbps.toFixed(1)),
      avg_u_mbps: Number(r.avg_u_mbps.toFixed(1)),
      avg_lat_ms: Number(r.avg_lat_ms.toFixed(1)),
      tests_count: r.tests_count,
      devices_count: r.devices_count,
      dist_cbd_km: r.dist_cbd_km,
      quarter: r.quarter,
      trust_tier: r.trust_tier,
      extrude_h: Math.min(Math.round(r.avg_d_mbps * 3.5), 1400)
    }
  }));
  return { type: 'FeatureCollection', meta: { returned: features.length }, features };
}

function handleElections(url) {
  const city = url.searchParams.get('city') || 'all';
  const electionId = url.searchParams.get('election_id') || '';
  const tiers = parseTiers(url.searchParams.get('tiers'));

  const paramsPin = [...tiers];
  let sqlPin = `
    SELECT p.station_uid, p.city_id, p.municipality_name, p.station_code, p.station_name,
           p.address_text, p.gazetteer_id, p.lat, p.lon, p.geo_precision, p.render_as_pin,
           p.trust_tier, m.election_id, m.authority_body, m.election_date,
           m.registered_voters, m.ballots_cast, m.turnout_pct, m.winner_list,
           m.winner_bloc, m.winner_share_pct, m.winning_margin_pp, m.effective_num_parties_enp
    FROM polling_stations p
    JOIN mv_election_station_metrics m ON m.station_uid = p.station_uid
    WHERE p.render_as_pin = 1 AND p.lat IS NOT NULL AND p.lon IS NOT NULL
      AND p.trust_tier IN (${tierInClause(tiers)})
  `;
  if (city && city !== 'all') { sqlPin += ` AND p.city_id = ?`; paramsPin.push(city); }
  if (electionId) { sqlPin += ` AND m.election_id = ?`; paramsPin.push(electionId); }

  const pinRows = db.prepare(sqlPin).all(...paramsPin);

  // Honest aggregate bubbles for non-pin stations (Sarajevo, Travnik, Zagreb) — never fake pin coordinates!
  const paramsAgg = [...tiers];
  let sqlAgg = `
    SELECT p.city_id, m.election_id, m.authority_body, m.election_date, p.gazetteer_id,
           COALESCE(g.canonical_name, p.municipality_name) AS zone_name,
           p.geo_precision, p.trust_tier,
           AVG(COALESCE(g.centroid_lat, p.lat)) AS lat,
           AVG(COALESCE(g.centroid_lon, p.lon)) AS lon,
           COUNT(*) AS stations_n,
           SUM(m.registered_voters) AS registered_voters,
           SUM(m.ballots_cast) AS ballots_cast,
           ROUND(AVG(m.turnout_pct), 2) AS turnout_pct,
           ROUND(AVG(m.winning_margin_pp), 2) AS winning_margin_pp,
           ROUND(AVG(m.effective_num_parties_enp), 2) AS effective_num_parties_enp,
           MAX(m.winner_list) AS top_winner_sample,
           MAX(m.winner_bloc) AS winner_bloc
    FROM polling_stations p
    JOIN mv_election_station_metrics m ON m.station_uid = p.station_uid
    LEFT JOIN spatial_gazetteer g ON g.gazetteer_id = p.gazetteer_id
    WHERE p.render_as_pin = 0
      AND p.trust_tier IN (${tierInClause(tiers)})
  `;
  if (city && city !== 'all') { sqlAgg += ` AND p.city_id = ?`; paramsAgg.push(city); }
  if (electionId) { sqlAgg += ` AND m.election_id = ?`; paramsAgg.push(electionId); }
  sqlAgg += ` GROUP BY p.city_id, m.election_id, p.gazetteer_id, p.geo_precision, p.trust_tier`;

  const aggRows = db.prepare(sqlAgg).all(...paramsAgg);

  const features = [
    ...pinRows.map(r => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [r.lon, r.lat] },
      properties: {
        kind: 'exact_station',
        station_uid: r.station_uid,
        city_id: r.city_id,
        gazetteer_id: r.gazetteer_id,
        name: `${r.municipality_name} · BM ${r.station_code}`,
        station_name: r.station_name,
        authority_body: r.authority_body,
        election_id: r.election_id,
        election_date: r.election_date,
        geo_precision: r.geo_precision,
        trust_tier: r.trust_tier,
        registered_voters: r.registered_voters,
        ballots_cast: r.ballots_cast,
        turnout_pct: r.turnout_pct,
        winner_list: r.winner_list,
        winner_bloc: r.winner_bloc,
        winner_share_pct: r.winner_share_pct,
        winning_margin_pp: r.winning_margin_pp,
        enp: r.effective_num_parties_enp
      }
    })),
    ...aggRows.filter(r => r.lat && r.lon).map(r => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [r.lon, r.lat] },
      properties: {
        kind: 'zone_aggregate',
        city_id: r.city_id,
        gazetteer_id: r.gazetteer_id,
        name: `${r.zone_name} (${r.stations_n} BM agregat)`,
        authority_body: r.authority_body,
        election_id: r.election_id,
        election_date: r.election_date,
        geo_precision: r.geo_precision,
        trust_tier: r.trust_tier,
        stations_n: r.stations_n,
        registered_voters: r.registered_voters,
        ballots_cast: r.ballots_cast,
        turnout_pct: r.turnout_pct,
        winner_list: r.top_winner_sample,
        winner_bloc: r.winner_bloc,
        winning_margin_pp: r.winning_margin_pp,
        enp: r.effective_num_parties_enp
      }
    }))
  ];

  return {
    type: 'FeatureCollection',
    meta: { exact_pins: pinRows.length, zone_aggregates: aggRows.length },
    features
  };
}

function handleProcurement(url) {
  const city = url.searchParams.get('city') || 'all';
  const tiers = parseTiers(url.searchParams.get('tiers'));

  const params = [...tiers];
  let sql = `
    SELECT p.city_id, p.gazetteer_id, COALESCE(g.canonical_name, p.city_id) AS zone_name,
           g.centroid_lat AS lat, g.centroid_lon AS lon, p.trust_tier,
           COUNT(*) AS contracts_n,
           ROUND(SUM(COALESCE(p.contract_value_eur, 0)) / 1e6, 3) AS total_eur_m,
           SUM(COALESCE(p.single_bidder_flag, 0)) AS single_bidder_n,
           ROUND(100.0 * SUM(COALESCE(p.single_bidder_flag, 0)) / NULLIF(COUNT(*), 0), 1) AS single_bidder_pct,
           MIN(p.award_date) AS first_date, MAX(p.award_date) AS last_date
    FROM domain_signals_procurement p
    LEFT JOIN spatial_gazetteer g ON g.gazetteer_id = p.gazetteer_id
    WHERE p.trust_tier IN (${tierInClause(tiers)})
  `;
  if (city && city !== 'all') { sql += ` AND p.city_id = ?`; params.push(city); }
  sql += ` GROUP BY p.city_id, p.gazetteer_id, p.trust_tier`;

  const spots = db.prepare(sql).all(...params);
  const features = spots.filter(s => s.lat && s.lon).map(s => ({
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
    properties: {
      city_id: s.city_id,
      gazetteer_id: s.gazetteer_id,
      zone_name: s.zone_name,
      trust_tier: s.trust_tier,
      contracts_n: s.contracts_n,
      total_eur_m: s.total_eur_m,
      single_bidder_n: s.single_bidder_n,
      single_bidder_pct: s.single_bidder_pct,
      first_date: s.first_date,
      last_date: s.last_date
    }
  }));

  const netParams = [];
  let netSql = `SELECT * FROM v_procurement_buyer_supplier_network WHERE 1=1`;
  if (city && city !== 'all') { netSql += ` AND city_id = ?`; netParams.push(city); }
  netSql += ` ORDER BY COALESCE(total_value_eur, 0) DESC, contracts_n DESC LIMIT 40`;
  const topNetwork = db.prepare(netSql).all(...netParams);

  return { type: 'FeatureCollection', features, top_network: topNetwork };
}

function handleTransit(url) {
  const city = url.searchParams.get('city') || 'all';
  const tiers = parseTiers(url.searchParams.get('tiers'));
  const bbox = parseBbox(url.searchParams.get('bbox'));
  const limit = Math.min(Number(url.searchParams.get('limit') || 4500), 11000);

  const params = [];
  let sql;
  if (bbox) {
    sql = `
      SELECT t.stop_uid, t.city_id, t.gazetteer_id, t.stop_name, t.mode, t.lat, t.lon,
             t.dist_cbd_km, t.feed_label, t.trust_tier
      FROM transit_stops_rtree r
      JOIN transit_stops t ON t.rowid = r.stop_rowid
      WHERE r.max_lon >= ? AND r.min_lon <= ? AND r.max_lat >= ? AND r.min_lat <= ?
        AND t.trust_tier IN (${tierInClause(tiers)})
    `;
    params.push(bbox.minLon, bbox.maxLon, bbox.minLat, bbox.maxLat, ...tiers);
  } else {
    sql = `
      SELECT t.stop_uid, t.city_id, t.gazetteer_id, t.stop_name, t.mode, t.lat, t.lon,
             t.dist_cbd_km, t.feed_label, t.trust_tier
      FROM transit_stops t
      WHERE t.trust_tier IN (${tierInClause(tiers)})
    `;
    params.push(...tiers);
  }
  if (city && city !== 'all') { sql += ` AND t.city_id = ?`; params.push(city); }
  sql += ` LIMIT ?`;
  params.push(limit);

  const rows = db.prepare(sql).all(...params);
  return {
    type: 'FeatureCollection',
    meta: { returned: rows.length },
    features: rows.map(r => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [r.lon, r.lat] },
      properties: r
    }))
  };
}

function handleRentGap(url) {
  const city = url.searchParams.get('city') || 'all';
  const tiers = parseTiers(url.searchParams.get('tiers'));

  const params = [...tiers];
  let sql = `
    SELECT rg.*, p.gazetteer_id, p.min_lon, p.max_lon, p.min_lat, p.max_lat,
           p.centroid_lat, p.centroid_lon, p.assessed_tax_eur_m2, p.market_est_eur_m2, p.trust_tier
    FROM v_xs_development_rent_gap rg
    JOIN xs_cadastral_parcels p ON p.parcel_uid = rg.parcel_uid
    WHERE p.trust_tier IN (${tierInClause(tiers)})
  `;
  if (city && city !== 'all') { sql += ` AND rg.city_id = ?`; params.push(city); }

  const rows = db.prepare(sql).all(...params);
  return {
    type: 'FeatureCollection',
    features: rows.filter(r => r.min_lon != null && r.max_lon != null).map(r => ({
      type: 'Feature',
      geometry: bboxToPolygon(r.min_lon, r.min_lat, r.max_lon, r.max_lat),
      properties: {
        ...r,
        extrude_h: Math.min(Math.max(Math.round((r.allowed_max_height_m || 18) * 1.4), 10), 120)
      }
    }))
  };
}

function handleCommuting(url) {
  const city = url.searchParams.get('city') || 'all';
  const hl = ENRICHED_HINTERLAND.features;
  const features = [];
  for (const f of hl) {
    const p = f.properties;
    if (city && city !== 'all' && p.city_hub !== city) continue;
    const hub = cityMap.get(p.city_hub);
    if (!hub) continue;
    const [oLon, oLat] = featureCentroid(f.geometry);
    if (!oLon || !oLat) continue;
    // Slight arc midpoint for clean visual curve
    const midLon = (oLon + hub.cbd_lon) / 2;
    const midLat = (oLat + hub.cbd_lat) / 2 + 0.035;
    features.push({
      type: 'Feature',
      geometry: {
        type: 'LineString',
        coordinates: [[oLon, oLat], [midLon, midLat], [hub.cbd_lon, hub.cbd_lat]]
      },
      properties: {
        city_id: p.city_hub,
        origin_name: p.unit_name,
        dest_name: hub.name,
        gazetteer_id: p.gazetteer_id,
        dist_cbd_km: p.dist_cbd_km,
        ring_role: p.ring_role,
        population: p.population,
        commuters_total: p.commuters_total || 0,
        commuters_external: p.commuters_external || 0,
        supply_chain_role: p.supply_chain_role,
        trust_tier: 'A2'
      }
    });
  }
  return { type: 'FeatureCollection', features };
}

function handleDossier(url) {
  const tiers = parseTiers(url.searchParams.get('tiers'));
  const tierClause = tierInClause(tiers);
  let gazId = Number(url.searchParams.get('gazetteer_id') || 0);
  const cityParam = url.searchParams.get('city') || '';
  const nameParam = url.searchParams.get('name') || '';
  const latParam = Number(url.searchParams.get('lat'));
  const lonParam = Number(url.searchParams.get('lon'));

  let zone = gazId ? gazById.get(gazId) : null;
  if (!zone && cityParam && nameParam) {
    zone = gazByCityName.get(`${cityParam}|${norm(nameParam)}`) || null;
  }
  if (!zone && Number.isFinite(latParam) && Number.isFinite(lonParam)) {
    zone = db.prepare(`
      SELECT * FROM spatial_gazetteer
      WHERE centroid_lat IS NOT NULL AND centroid_lon IS NOT NULL
        ${cityParam ? 'AND city_id = ?' : ''}
      ORDER BY ((centroid_lat - ?) * (centroid_lat - ?) + (centroid_lon - ?) * (centroid_lon - ?)) ASC
      LIMIT 1
    `).get(...(cityParam ? [cityParam, latParam, latParam, lonParam, lonParam] : [latParam, latParam, lonParam, lonParam]));
  }
  if (!zone && cityParam) {
    zone = db.prepare(`SELECT * FROM spatial_gazetteer WHERE city_id = ? AND feature_class = 'city_core' LIMIT 1`).get(cityParam);
  }
  if (!zone) return { ok: false, error: 'Zona nije pronađena u spatial_gazetteer' };

  gazId = zone.gazetteer_id;
  const cid = zone.city_id;
  const city = cityMap.get(cid) || null;
  const cityCoreGaz = cid ? db.prepare(`SELECT gazetteer_id FROM spatial_gazetteer WHERE city_id = ? AND feature_class = 'city_core' LIMIT 1`).get(cid) : null;
  const isCityWide = zone.feature_class === 'city_core' || (cid === 'travnik' && zone.feature_class === 'municipality') || (cid === 'novi_pazar' && zone.feature_class === 'municipality');

  // Admin & economic profile
  const adminRow = cid ? (
    db.prepare(`SELECT * FROM admin_units WHERE city_id = ? AND LOWER(unit_name) = LOWER(?) LIMIT 1`).get(cid, zone.canonical_name)
    || db.prepare(`SELECT * FROM admin_units WHERE city_id = ? AND LOWER(unit_name) LIKE LOWER(?) LIMIT 1`).get(cid, `%${zone.canonical_name}%`)
  ) : null;

  const unified = zoneProfileById.get(gazId) || null;

  // 3D Morphology breakdown by trust tier (zone-level; fallback to city if city_core)
  const bldgScopeSql = isCityWide ? `city_id = ?` : `gazetteer_id = ?`;
  const bldgScopeArg = isCityWide ? cid : gazId;
  const buildingsByTier = db.prepare(`
    SELECT trust_tier, height_source, COUNT(*) AS count,
           ROUND(AVG(height_m), 1) AS avg_height_m,
           ROUND(MAX(height_m), 1) AS max_height_m,
           ROUND(SUM(COALESCE(volume_m3, 0)) / 1e6, 3) AS volume_mio_m3,
           ROUND(SUM(COALESCE(footprint_area_m2, 0)) / 1e4, 2) AS footprint_ha
    FROM xs_buildings_3d
    WHERE ${bldgScopeSql} AND trust_tier IN (${tierClause})
    GROUP BY trust_tier, height_source
    ORDER BY count DESC
  `).all(bldgScopeArg, ...tiers);

  const buildingsTotalAllTiers = db.prepare(`SELECT COUNT(*) AS c FROM xs_buildings_3d WHERE ${bldgScopeSql}`).get(bldgScopeArg).c;

  // Rent-gap parcels
  const rentGap = db.prepare(`
    SELECT rg.*, p.assessed_tax_eur_m2, p.market_est_eur_m2, p.trust_tier
    FROM v_xs_development_rent_gap rg
    JOIN xs_cadastral_parcels p ON p.parcel_uid = rg.parcel_uid
    WHERE (p.gazetteer_id = ? OR (? = 1 AND rg.city_id = ?))
      AND p.trust_tier IN (${tierClause})
    ORDER BY COALESCE(rg.implied_development_headroom_eur, 0) DESC
    LIMIT 12
  `).all(gazId, isCityWide ? 1 : 0, cid || '', ...tiers);

  // Ookla broadband in zone + city benchmark
  const ooklaScopeSql = isCityWide ? `city_id = ?` : `gazetteer_id = ?`;
  const ooklaZone = db.prepare(`
    SELECT COUNT(*) AS tiles_n, SUM(tests_count) AS tests_n, SUM(devices_count) AS devices_n,
           ROUND(SUM(avg_d_mbps * tests_count) / NULLIF(SUM(tests_count), 0), 2) AS weighted_dl_mbps,
           ROUND(SUM(avg_u_mbps * tests_count) / NULLIF(SUM(tests_count), 0), 2) AS weighted_ul_mbps,
           ROUND(SUM(avg_lat_ms * tests_count) / NULLIF(SUM(tests_count), 0), 2) AS weighted_lat_ms,
           ROUND(MIN(avg_d_mbps), 1) AS min_dl, ROUND(MAX(avg_d_mbps), 1) AS max_dl
    FROM ookla_broadband_tiles
    WHERE ${ooklaScopeSql} AND trust_tier IN (${tierClause})
  `).get(bldgScopeArg, ...tiers);

  const ooklaCity = cid ? db.prepare(`SELECT * FROM v_ookla_digital_divide_by_city WHERE city_id = ? LIMIT 1`).get(cid) : null;

  // Transit stops in zone
  const transitModes = db.prepare(`
    SELECT mode, trust_tier, COUNT(*) AS stops_n
    FROM transit_stops
    WHERE ${ooklaScopeSql} AND trust_tier IN (${tierClause})
    GROUP BY mode, trust_tier
    ORDER BY stops_n DESC
  `).all(bldgScopeArg, ...tiers);

  // Elections in zone
  const elecSummary = db.prepare(`
    SELECT m.election_id, m.authority_body, m.election_date, m.election_level,
           COUNT(*) AS stations_n,
           SUM(m.registered_voters) AS registered_voters,
           SUM(m.ballots_cast) AS ballots_cast,
           ROUND(AVG(m.turnout_pct), 2) AS avg_turnout_pct,
           ROUND(AVG(m.winning_margin_pp), 2) AS avg_margin_pp,
           ROUND(AVG(m.effective_num_parties_enp), 2) AS avg_enp
    FROM mv_election_station_metrics m
    JOIN polling_stations p ON p.station_uid = m.station_uid
    WHERE (m.gazetteer_id = ? OR (? = 1 AND m.city_id = ?))
      AND p.trust_tier IN (${tierClause})
    GROUP BY m.election_id, m.authority_body, m.election_date, m.election_level
    ORDER BY m.election_date DESC
  `).all(gazId, isCityWide ? 1 : 0, cid || '', ...tiers);

  const topParties = db.prepare(`
    SELECT r.list_or_candidate_name, r.comparative_bloc, SUM(r.votes_count) AS votes,
           ROUND(AVG(r.vote_share_valid_pct), 2) AS avg_share_pct, r.election_id
    FROM election_station_results r
    JOIN polling_stations p ON p.station_uid = r.station_uid
    WHERE (p.gazetteer_id = ? OR (? = 1 AND p.city_id = ?))
      AND r.trust_tier IN (${tierClause})
    GROUP BY r.election_id, r.list_or_candidate_name, r.comparative_bloc
    ORDER BY votes DESC
    LIMIT 8
  `).all(gazId, isCityWide ? 1 : 0, cid || '', ...tiers);

  // Procurement in zone (or city fallback flagged clearly)
  let procRows = db.prepare(`
    SELECT p.contract_uid, p.award_date, p.contract_value_eur, p.estimated_value_eur,
           p.bidders_count, p.single_bidder_flag, p.procedure_type, p.cpv_division, p.trust_tier,
           b.canonical_name AS buyer_name, w.canonical_name AS winner_name, d.primary_url, d.title AS doc_title
    FROM domain_signals_procurement p
    LEFT JOIN entities b ON b.entity_id = p.buyer_entity_id
    LEFT JOIN entities w ON w.entity_id = p.winner_entity_id
    LEFT JOIN evidence_documents d ON d.doc_id = p.doc_id
    WHERE (p.gazetteer_id = ? OR (? = 1 AND p.city_id = ?))
      AND p.trust_tier IN (${tierClause})
    ORDER BY COALESCE(p.contract_value_eur, 0) DESC, p.award_date DESC
    LIMIT 15
  `).all(gazId, isCityWide ? 1 : 0, cid || '', ...tiers);

  let procScope = isCityWide ? 'city' : 'zone';
  if (!procRows.length && cid && !isCityWide) {
    // Provide city-level context transparently if zone has no direct procurement geocoding (e.g. ZG city-core TED)
    procRows = db.prepare(`
      SELECT p.contract_uid, p.award_date, p.contract_value_eur, p.estimated_value_eur,
             p.bidders_count, p.single_bidder_flag, p.procedure_type, p.cpv_division, p.trust_tier,
             b.canonical_name AS buyer_name, w.canonical_name AS winner_name, d.primary_url, d.title AS doc_title
      FROM domain_signals_procurement p
      LEFT JOIN entities b ON b.entity_id = p.buyer_entity_id
      LEFT JOIN entities w ON w.entity_id = p.winner_entity_id
      LEFT JOIN evidence_documents d ON d.doc_id = p.doc_id
      WHERE p.city_id = ? AND p.trust_tier IN (${tierClause})
      ORDER BY COALESCE(p.contract_value_eur, 0) DESC, p.award_date DESC
      LIMIT 8
    `).all(cid, ...tiers);
    if (procRows.length) procScope = 'city_context';
  }

  const procStats = db.prepare(`
    SELECT COUNT(*) AS contracts_n,
           ROUND(SUM(COALESCE(contract_value_eur, 0)) / 1e6, 3) AS total_eur_m,
           ROUND(100.0 * SUM(COALESCE(single_bidder_flag, 0)) / NULLIF(COUNT(*), 0), 1) AS single_bidder_pct
    FROM domain_signals_procurement
    WHERE ${procScope === 'zone' ? 'gazetteer_id = ?' : 'city_id = ?'}
      AND trust_tier IN (${tierClause})
  `).get(procScope === 'zone' ? gazId : (cid || ''), ...tiers);

  // Sector LQ
  const sectors = cid ? db.prepare(`
    SELECT nace_section, nace_name, companies_count, unit_share_pct, location_quotient, unit_name
    FROM sector_structure
    WHERE city_id = ? AND (LOWER(unit_name) = LOWER(?) OR LOWER(unit_name) LIKE LOWER(?) OR unit_name = (SELECT name FROM cities WHERE city_id = ?))
    ORDER BY CASE WHEN LOWER(unit_name) = LOWER(?) THEN 0 ELSE 1 END, location_quotient DESC
    LIMIT 8
  `).all(cid, zone.canonical_name, `%${zone.canonical_name}%`, cid, zone.canonical_name) : [];

  // Bid-rent & property prices
  const propPrices = cid ? db.prepare(`
    SELECT year, zone_or_unit, property_type, price_eur_m2, basis, source_doc
    FROM property_zones_prices
    WHERE city_id = ? AND property_type IN ('stan', 'stanovi', 'poslovni_prostor', 'gradjevinsko_zemljiste', 'apartment', 'residential')
    ORDER BY price_eur_m2 DESC
    LIMIT 8
  `).all(cid) : [];

  // Climate & Air quality sensors
  const sensors = cid ? db.prepare(`
    SELECT sensor_metric, value_unit, trust_tier,
           ROUND(AVG(value_num), 2) AS avg_val, ROUND(MAX(value_num), 2) AS max_val,
           MAX(period_end) AS latest_period, COUNT(*) AS obs_n
    FROM domain_signals_sensors
    WHERE city_id = ? AND trust_tier IN (${tierClause})
      AND sensor_metric IN ('openaq_pm25_ugm3', 'openaq_no2_ugm3', 'ground_pm25_ugm3', 'era5_hdd18_degdays', 'era5_heat35_days', 'era5_temp_mean_c')
    GROUP BY sensor_metric, value_unit, trust_tier
  `).all(cid, ...tiers) : [];

  // SEPA industrial emissions (SRB)
  const sepa = cid ? db.prepare(`
    SELECT company_name, facility_name, pollutant_name, quantity_kg_year, municipality_name, trust_tier
    FROM sepa_industrial_emissions
    WHERE (gazetteer_id = ? OR city_id = ?) AND trust_tier IN (${tierClause})
    ORDER BY quantity_kg_year DESC
    LIMIT 6
  `).all(gazId, cid, ...tiers) : [];

  // Science & EU CORDIS
  const science = cid ? db.prepare(`
    SELECT s.work_type, s.pub_year, s.cited_by_count, s.grant_amount_eur, s.trust_tier,
           d.title, d.primary_url, e.canonical_name AS institution_name
    FROM domain_signals_science s
    LEFT JOIN evidence_documents d ON d.doc_id = s.doc_id
    LEFT JOIN entities e ON e.entity_id = s.institution_entity_id
    WHERE s.city_id = ? AND s.trust_tier IN (${tierClause})
    ORDER BY COALESCE(s.grant_amount_eur, 0) DESC, COALESCE(s.cited_by_count, 0) DESC
    LIMIT 8
  `).all(cid, ...tiers) : [];

  // Linked Evidence Documents (zone direct + city core fallback)
  let docs = db.prepare(`
    SELECT doc_id, doc_type, trust_tier, trust_label_sr, topic_primary, published_at,
           title, primary_url, geo_role, geo_precision, geo_confidence
    FROM v_geo_location_dossier
    WHERE gazetteer_id = ? AND trust_tier IN (${tierClause})
    ORDER BY tier_rank ASC, published_at DESC
    LIMIT 25
  `).all(gazId, ...tiers);

  let docsScope = 'zone';
  if (docs.length < 5 && cid) {
    const cityDocs = db.prepare(`
      SELECT d.doc_id, d.doc_type, d.trust_tier, t.label_sr AS trust_label_sr, d.topic_primary,
             d.published_at, d.title, d.primary_url, SUBSTR(d.raw_sha256, 1, 12) AS sha_short
      FROM evidence_documents d
      JOIN trust_tiers t ON t.tier_code = d.trust_tier
      WHERE d.primary_city_id = ? AND d.trust_tier IN (${tierClause})
      ORDER BY t.tier_rank ASC, d.published_at DESC
      LIMIT 15
    `).all(cid, ...tiers);
    const seen = new Set(docs.map(d => d.doc_id));
    for (const cd of cityDocs) {
      if (!seen.has(cd.doc_id)) docs.push({ ...cd, geo_role: 'city_context' });
    }
    if (!seen.size) docsScope = 'city_context';
  }

  // Provenance claims relevant to city
  const claims = db.prepare(`SELECT * FROM provenance_claims ORDER BY claim_id`).all();

  return {
    ok: true,
    active_tiers: tiers,
    zone,
    city,
    admin: adminRow,
    unified,
    buildings_3d: {
      scope: isCityWide ? 'city' : 'zone',
      total_all_tiers: buildingsTotalAllTiers,
      by_tier: buildingsByTier
    },
    rent_gap: rentGap,
    ookla: {
      scope: isCityWide ? 'city' : 'zone',
      zone: ooklaZone,
      city_benchmark: ooklaCity
    },
    transit: transitModes,
    elections: {
      cycles: elecSummary,
      top_parties: topParties
    },
    procurement: {
      scope: procScope,
      stats: procStats,
      contracts: procRows
    },
    sectors,
    property_prices: propPrices,
    sensors,
    sepa,
    science,
    documents: {
      scope: docsScope,
      items: docs
    },
    provenance_claims: claims
  };
}

function handleSearch(url) {
  const q = (url.searchParams.get('q') || '').trim();
  const city = url.searchParams.get('city') || 'all';
  const tiers = parseTiers(url.searchParams.get('tiers'));
  if (q.length < 2) return { zones: [], entities: [], documents: [] };

  const like = `%${q}%`;
  const zParams = [like, like];
  let zSql = `
    SELECT gazetteer_id, city_id, scale_level, feature_class, canonical_name,
           centroid_lat, centroid_lon, dist_cbd_km, trust_tier
    FROM spatial_gazetteer
    WHERE (canonical_name LIKE ? OR normalized_name LIKE ?)
      AND centroid_lat IS NOT NULL AND centroid_lon IS NOT NULL
  `;
  if (city && city !== 'all') { zSql += ` AND city_id = ?`; zParams.push(city); }
  zSql += ` ORDER BY disambiguation_weight DESC LIMIT 12`;
  const zones = db.prepare(zSql).all(...zParams);

  const eParams = [like, ...tiers];
  let eSql = `
    SELECT entity_id, entity_type, canonical_name, primary_city_id, country_iso3, trust_tier
    FROM entities
    WHERE canonical_name LIKE ? AND trust_tier IN (${tierInClause(tiers)})
  `;
  if (city && city !== 'all') { eSql += ` AND primary_city_id = ?`; eParams.push(city); }
  eSql += ` LIMIT 10`;
  const entities = db.prepare(eSql).all(...eParams);

  const dParams = [like, ...tiers];
  let dSql = `
    SELECT doc_id, primary_city_id, doc_type, trust_tier, topic_primary, published_at, title, primary_url
    FROM evidence_documents
    WHERE (title LIKE ? OR summary_text LIKE ?) AND trust_tier IN (${tierInClause(tiers)})
  `;
  dParams.splice(1, 0, like);
  if (city && city !== 'all') { dSql += ` AND primary_city_id = ?`; dParams.push(city); }
  dSql += ` ORDER BY published_at DESC LIMIT 10`;
  const documents = db.prepare(dSql).all(...dParams);

  return { zones, entities, documents };
}

// ---------------------------------------------------------------------------
// Static File Server & HTTP Router
// ---------------------------------------------------------------------------
const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.geojson': 'application/geo+json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon'
};

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    'Access-Control-Allow-Origin': '*'
  });
  res.end(body);
}

const server = http.createServer((req, res) => {
  try {
    const url = new URL(req.url, `http://${HOST}:${PORT}`);
    const p = url.pathname;

    if (p.startsWith('/api/')) {
      const t0 = performance.now();
      let data;
      if (p === '/api/health') data = handleHealth();
      else if (p === '/api/bootstrap') data = handleBootstrap();
      else if (p === '/api/layers/zones') data = handleZonesLayer(url);
      else if (p === '/api/layers/buildings3d') data = handleBuildings3D(url);
      else if (p === '/api/layers/ookla') data = handleOokla(url);
      else if (p === '/api/layers/elections') data = handleElections(url);
      else if (p === '/api/layers/procurement') data = handleProcurement(url);
      else if (p === '/api/layers/transit') data = handleTransit(url);
      else if (p === '/api/layers/rentgap') data = handleRentGap(url);
      else if (p === '/api/layers/commuting') data = handleCommuting(url);
      else if (p === '/api/dossier') data = handleDossier(url);
      else if (p === '/api/search') data = handleSearch(url);
      else return sendJson(res, 404, { ok: false, error: `Unknown API route: ${p}` });

      const ms = (performance.now() - t0).toFixed(1);
      res.setHeader('X-Query-Time-Ms', ms);
      return sendJson(res, 200, data);
    }

    // Static assets
    let relPath = p === '/' ? '/index.html' : p;
    relPath = path.normalize(relPath).replace(/^(\.\.[/\\])+/, '');
    const fullPath = path.join(PUBLIC_DIR, relPath);
    if (!fullPath.startsWith(PUBLIC_DIR) || !fs.existsSync(fullPath) || fs.statSync(fullPath).isDirectory()) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      return res.end('Not found');
    }
    const ext = path.extname(fullPath).toLowerCase();
    res.writeHead(200, {
      'Content-Type': MIME[ext] || 'application/octet-stream',
      'Cache-Control': 'no-cache'
    });
    fs.createReadStream(fullPath).pipe(res);
  } catch (err) {
    console.error('[API ERROR]', err);
    sendJson(res, 500, { ok: false, error: err.message });
  }
});

server.listen(PORT, HOST, () => {
  console.log(`\n============================================================`);
  console.log(`  URBAN LAB "EKONOMIJA GRADA" — Interactive 2D/3D GIS v4.2`);
  console.log(`  URL: http://${HOST}:${PORT}`);
  console.log(`  DB : ${DB_PATH}`);
  console.log(`============================================================\n`);
});
