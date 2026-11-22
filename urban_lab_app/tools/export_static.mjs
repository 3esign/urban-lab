#!/usr/bin/env node
/**
 * Urban Lab — izvoz žive v4.2 baze u statičke fajlove za GitHub Pages.
 *
 * Podiže server.mjs (isti API koji proverava tests/api_smoke.mjs), snima odgovore
 * u docs/data/ i dodaje indeks pretrage direktno iz baze. Baza se samo čita.
 *
 *   node urban_lab_app/tools/export_static.mjs [--port 8793] [--skip-dossiers]
 */
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { DatabaseSync } from 'node:sqlite';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '../..');
const OUT = path.join(ROOT, 'docs', 'data');
const DB_PATH = process.env.URBAN_LAB_DB || path.join(ROOT, 'urban_lab_db/curated/urban_lab_5cities_v4.sqlite');
const args = process.argv.slice(2);
const PORT = Number(args[args.indexOf('--port') + 1]) || 8793;
const SKIP_DOSSIERS = args.includes('--skip-dossiers');
const BASE = `http://127.0.0.1:${PORT}`;
const CITIES = ['beograd', 'zagreb', 'sarajevo', 'novi_pazar', 'travnik'];
const BUILDINGS_LIMIT = 8000; // gornja granica koju server dozvoljava
const TRANSIT_LIMIT = 11000;

// ── pomoćne ────────────────────────────────────────────────────────────────
const r5 = n => Math.round(n * 1e5) / 1e5;
function roundCoords(c) {
  if (typeof c[0] === 'number') return [r5(c[0]), r5(c[1])];
  const out = c.map(roundCoords);
  // posle zaokruživanja izbaci uzastopne duplikate tačaka u prstenu/liniji
  if (out.length && typeof out[0][0] === 'number') {
    const dedup = [out[0]];
    for (let i = 1; i < out.length; i++) {
      const a = dedup[dedup.length - 1], b = out[i];
      if (a[0] !== b[0] || a[1] !== b[1]) dedup.push(b);
    }
    return dedup;
  }
  return out;
}
function compactFC(fc, { drop = [], truncate = {} } = {}) {
  const features = [];
  for (const f of fc.features || []) {
    if (!f.geometry) continue;
    const props = {};
    for (const [k, v] of Object.entries(f.properties || {})) {
      if (v === null || v === '' || drop.includes(k)) continue;
      props[k] = (truncate[k] && typeof v === 'string' && v.length > truncate[k]) ? v.slice(0, truncate[k]) + '…' : v;
    }
    features.push({ type: 'Feature', geometry: { type: f.geometry.type, coordinates: roundCoords(f.geometry.coordinates) }, properties: props });
  }
  const out = { type: 'FeatureCollection', features };
  if (fc.top_network) out.top_network = fc.top_network;
  return out;
}
const written = [];
function write(rel, obj) {
  const full = path.join(OUT, rel);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  const body = JSON.stringify(obj);
  fs.writeFileSync(full, body);
  written.push({ file: rel, bytes: Buffer.byteLength(body), n: Array.isArray(obj.features) ? obj.features.length : null });
  return obj;
}
async function api(p) {
  const res = await fetch(BASE + p);
  if (!res.ok) throw new Error(`${p} → HTTP ${res.status}`);
  return res.json();
}
async function waitForServer() {
  for (let i = 0; i < 120; i++) {
    try { const r = await fetch(BASE + '/api/health'); if (r.ok) return r.json(); } catch {}
    await new Promise(r => setTimeout(r, 500));
  }
  throw new Error('server se nije podigao');
}

// ── izvoz ──────────────────────────────────────────────────────────────────
const server = spawn(process.execPath, [path.join(ROOT, 'urban_lab_app/server.mjs'), '--port', String(PORT)], { stdio: 'ignore' });
let exitCode = 0;
try {
  const health = await waitForServer();
  if (!SKIP_DOSSIERS) fs.rmSync(path.join(OUT, 'dossier'), { recursive: true, force: true });

  write('bootstrap.json', await api('/api/bootstrap'));

  const gazIds = new Set();
  const collect = fc => { for (const f of fc.features) if (f.properties.gazetteer_id) gazIds.add(f.properties.gazetteer_id); return fc; };

  const zoneKinds = {
    admin: {}, zagreb_mo: {}, np_naselja: {}, hinterland: {},
    tax_zones: { drop: ['source_doc', 'geometry_basis', 'rzs_idter'] },
    corridors: {},
    bakeries: { drop: ['osm_id'] },
    landuse: { drop: ['osm_id', 'lon', 'lat', 'area_ha'] }
  };
  for (const [kind, opt] of Object.entries(zoneKinds)) {
    const fc = write(`zones/${kind}.geojson`, compactFC(await api(`/api/layers/zones?kind=${kind}&city=all`), opt));
    if (['admin', 'zagreb_mo', 'np_naselja', 'hinterland', 'tax_zones'].includes(kind)) collect(fc);
  }
  for (const c of ['beograd', 'novi_pazar']) {
    write(`zones/grid_1km_${c}.geojson`, compactFC(await api(`/api/layers/zones?kind=grid_1km&city=${c}`),
      { drop: ['idter', 'idindikator', 'ordinalid', 'nindikator', 'idstatuspoverljivosti', 'SHAPE__Length', 'SHAPE__Area', 'objectid', 'idjezik'] }));
  }

  const layerCounts = {};
  for (const c of CITIES) {
    const per = {
      buildings3d: [`/api/layers/buildings3d?city=${c}&limit=${BUILDINGS_LIMIT}`, { drop: ['building_uid', 'city_id', 'parcel_uid'] }],
      ookla: [`/api/layers/ookla?city=${c}`, { drop: ['tile_uid', 'city_id'] }],
      elections: [`/api/layers/elections?city=${c}`, { drop: ['station_uid', 'city_id'], truncate: { winner_list: 90 } }],
      procurement: [`/api/layers/procurement?city=${c}`, {}],
      transit: [`/api/layers/transit?city=${c}&limit=${TRANSIT_LIMIT}`, { drop: ['stop_uid', 'city_id', 'lat', 'lon'] }],
      rentgap: [`/api/layers/rentgap?city=${c}`, { drop: ['min_lon', 'max_lon', 'min_lat', 'max_lat'] }],
      commuting: [`/api/layers/commuting?city=${c}`, {}]
    };
    layerCounts[c] = {};
    for (const [name, [url, opt]] of Object.entries(per)) {
      const fc = write(`city/${c}/${name}.geojson`, compactFC(await api(url), opt));
      layerCounts[c][name] = fc.features.length;
      if (name === 'rentgap') collect(fc);
    }
  }

  // Indeks pretrage i stvarni ukupni brojevi — direktno iz baze (samo čitanje).
  const db = new DatabaseSync(DB_PATH, { readOnly: true });
  const zones = db.prepare(`
    SELECT gazetteer_id AS id, city_id AS c, feature_class AS fc, canonical_name AS n,
           ROUND(centroid_lat, 5) AS lat, ROUND(centroid_lon, 5) AS lon
    FROM spatial_gazetteer WHERE centroid_lat IS NOT NULL AND centroid_lon IS NOT NULL
    ORDER BY disambiguation_weight DESC`).all();
  const documents = db.prepare(`
    SELECT primary_city_id AS c, trust_tier AS t, doc_type AS dt, published_at AS d, title AS n, primary_url AS u
    FROM evidence_documents WHERE title IS NOT NULL ORDER BY published_at DESC`).all();
  write('search.json', { zones, documents });

  const cityCore = {};
  for (const r of db.prepare(`SELECT city_id, gazetteer_id FROM spatial_gazetteer WHERE feature_class = 'city_core'`).all()) {
    cityCore[r.city_id] = r.gazetteer_id; gazIds.add(r.gazetteer_id);
  }
  const totals = {};
  for (const [name, table] of Object.entries({ buildings3d: 'xs_buildings_3d', transit: 'transit_stops', ookla: 'ookla_broadband_tiles', polling_stations: 'polling_stations' })) {
    for (const r of db.prepare(`SELECT city_id, COUNT(*) AS n FROM ${table} GROUP BY city_id`).all()) {
      (totals[r.city_id] ||= {})[name] = r.n;
    }
  }
  db.close();

  // Dosije po zoni (svi nivoi poverenja); provenance_claims i city već stoje u bootstrap.json.
  let dossiers = 0, dossierBytes = 0;
  if (!SKIP_DOSSIERS) {
    for (const id of [...gazIds].sort((a, b) => a - b)) {
      const d = await api(`/api/dossier?gazetteer_id=${id}`);
      if (!d.ok) continue;
      delete d.provenance_claims; delete d.city; delete d.active_tiers;
      const full = path.join(OUT, 'dossier', `${id}.json`);
      fs.mkdirSync(path.dirname(full), { recursive: true });
      const body = JSON.stringify(d);
      fs.writeFileSync(full, body);
      dossiers++; dossierBytes += Buffer.byteLength(body);
    }
  } else if (fs.existsSync(path.join(OUT, 'dossier'))) {
    for (const f of fs.readdirSync(path.join(OUT, 'dossier'))) { dossiers++; dossierBytes += fs.statSync(path.join(OUT, 'dossier', f)).size; }
  }

  write('meta.json', {
    generated_at: new Date().toISOString(),
    schema_version: health.schema_version,
    db_file: health.db_file,
    cities: CITIES,
    city_core: cityCore,
    layer_counts: layerCounts,
    db_totals: totals,
    limits: { buildings3d: BUILDINGS_LIMIT, transit: TRANSIT_LIMIT },
    dossiers: { count: dossiers, bytes: dossierBytes },
    files: written
  });

  const total = written.reduce((s, w) => s + w.bytes, 0) + dossierBytes;
  for (const w of written) console.log(String(w.bytes).padStart(10), String(w.n ?? '').padStart(6), w.file);
  console.log(`dosijea: ${dossiers} (${(dossierBytes / 1e6).toFixed(1)} MB) · ukupno ${(total / 1e6).toFixed(1)} MB → ${path.relative(ROOT, OUT)}`);
} catch (e) {
  console.error('IZVOZ PAO:', e.message);
  exitCode = 1;
} finally {
  server.kill();
}
process.exit(exitCode);
