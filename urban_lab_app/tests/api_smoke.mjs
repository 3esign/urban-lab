#!/usr/bin/env node
/**
 * Urban Lab API smoke test: starts server.mjs on a spare port, calls every
 * API route for all 5 cities, and prints a pass/fail matrix with row counts.
 * Usage: node tests/api_smoke.mjs [--port 8799] [--json out.json]
 */
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const arg = (k, d) => { const i = process.argv.indexOf(k); return i !== -1 ? process.argv[i + 1] : d; };
const PORT = Number(arg('--port', 8799));
const JSON_OUT = arg('--json', '');
const BASE = `http://127.0.0.1:${PORT}`;

const results = [];
let failed = 0;

function size(d) {
  if (!d || typeof d !== 'object') return null;
  if (Array.isArray(d)) return d.length;
  if (Array.isArray(d.features)) return d.features.length;
  for (const k of ['data', 'geojson', 'fc']) {
    if (d[k] && Array.isArray(d[k].features)) return d[k].features.length;
  }
  for (const k of ['results', 'rows', 'cities', 'items', 'flows']) {
    if (Array.isArray(d[k])) return d[k].length;
  }
  return null;
}

async function hit(label, url, check, expect = 200) {
  const t0 = performance.now();
  const rec = { label, url };
  try {
    const r = await fetch(BASE + url);
    const text = await r.text();
    rec.status = r.status;
    rec.bytes = text.length;
    rec.ms = Math.round(performance.now() - t0);
    let d = null;
    try { d = JSON.parse(text); } catch { /* static */ }
    rec.n = size(d);
    rec.keys = d && !Array.isArray(d) ? Object.keys(d).slice(0, 14) : undefined;
    let ok = r.status === expect && (expect !== 200 || !(d && d.ok === false));
    if (ok && check) {
      const msg = check(d, rec);
      if (msg) { ok = false; rec.note = msg; }
    }
    if (!ok && d && d.error) rec.note = d.error;
    if (rec.delta !== undefined) rec.note = (rec.note ? rec.note + ' ' : '') + `(Δ ${rec.delta} B vs all tiers)`;
    rec.ok = ok;
    rec.sample = d;
  } catch (e) {
    rec.ok = false; rec.note = String(e.message || e);
  }
  if (!rec.ok) failed++;
  results.push(rec);
  console.log(`${rec.ok ? 'PASS' : 'FAIL'}  ${String(rec.status ?? '---').padEnd(4)}${String(rec.n ?? '-').padStart(7)} rows ${String(rec.bytes ?? 0).padStart(9)} B ${String(rec.ms ?? 0).padStart(6)} ms  ${label}${rec.note ? '  <- ' + rec.note : ''}`);
  return rec;
}

const nonEmpty = d => (size(d) > 0 ? null : 'empty result');

const srv = spawn(process.execPath, [path.join(here, '..', 'server.mjs'), '--port', String(PORT)], { stdio: ['ignore', 'pipe', 'pipe'] });
let srvErr = '';
srv.stderr.on('data', b => { srvErr += b; });
srv.stdout.on('data', () => {});

async function waitUp() {
  for (let i = 0; i < 60; i++) {
    try { const r = await fetch(BASE + '/api/health'); if (r.ok) return true; } catch { /* retry */ }
    await new Promise(r => setTimeout(r, 250));
  }
  return false;
}

try {
  if (!(await waitUp())) throw new Error('server did not start: ' + srvErr.slice(0, 800));

  await hit('health', '/api/health');
  const boot = await hit('bootstrap', '/api/bootstrap', d => (Array.isArray(d.cities) && d.cities.length === 5 ? null : `expected 5 cities, got ${d.cities?.length}`));
  const cities = (boot.sample?.cities || []).map(c => c.city_slug || c.slug || c.city_id);
  console.log('cities:', cities.join(', '));

  for (const kind of ['admin', 'zagreb_mo', 'np_naselja', 'hinterland', 'tax_zones', 'corridors', 'bakeries', 'landuse']) {
    await hit(`zones kind=${kind} city=all`, `/api/layers/zones?kind=${kind}&city=all`, nonEmpty);
  }
  await hit('zones kind=grid_1km city=beograd', '/api/layers/zones?kind=grid_1km&city=beograd', nonEmpty);
  await hit('zones kind=grid_1km city=novi_pazar', '/api/layers/zones?kind=grid_1km&city=novi_pazar', nonEmpty);
  for (const c of cities) {
    const cb = (boot.sample.cities.find(x => (x.city_slug || x.slug || x.city_id) === c)) || {};
    const lat = cb.cbd_lat, lon = cb.cbd_lon;
    const bbox = [lon - 0.03, lat - 0.02, lon + 0.03, lat + 0.02].map(v => v.toFixed(5)).join(',');
    await hit(`[${c}] zones admin`, `/api/layers/zones?kind=admin&city=${c}`, nonEmpty);
    await hit(`[${c}] buildings3d bbox`, `/api/layers/buildings3d?city=${c}&bbox=${bbox}`, nonEmpty);
    await hit(`[${c}] ookla`, `/api/layers/ookla?city=${c}`, nonEmpty);
    await hit(`[${c}] elections`, `/api/layers/elections?city=${c}`, nonEmpty);
    await hit(`[${c}] procurement`, `/api/layers/procurement?city=${c}`);
    await hit(`[${c}] transit`, `/api/layers/transit?city=${c}`, nonEmpty);
    await hit(`[${c}] rentgap`, `/api/layers/rentgap?city=${c}`, nonEmpty);
    await hit(`[${c}] commuting`, `/api/layers/commuting?city=${c}`, nonEmpty);
    const full = await hit(`[${c}] dossier lat/lon all tiers`, `/api/dossier?city=${c}&lat=${lat}&lon=${lon}`);
    for (const t of ['A1', 'A2', 'B', 'C', 'D']) {
      await hit(`[${c}] dossier tiers=${t}`, `/api/dossier?city=${c}&lat=${lat}&lon=${lon}&tiers=${t}`, (d, rec) => {
        rec.delta = rec.bytes - full.bytes;
        return JSON.stringify(d.active_tiers) === JSON.stringify([t]) ? null : 'active_tiers mismatch: ' + JSON.stringify(d.active_tiers);
      });
    }
    await hit(`[${c}] search`, `/api/search?q=centar&city=${c}`);
  }
  // Trust-Tier filter must partition each layer: sum of per-tier counts == all-tier count
  for (const layer of ['ookla', 'elections', 'procurement', 'rentgap', 'transit']) {
    const all = await hit(`tier partition ${layer} ALL`, `/api/layers/${layer}?city=sarajevo`);
    let sum = 0; const parts = [];
    for (const t of ['A1', 'A2', 'B', 'C', 'D']) {
      const r = await fetch(BASE + `/api/layers/${layer}?city=sarajevo&tiers=${t}`).then(x => x.json());
      const n = size(r) ?? 0; sum += n; parts.push(`${t}=${n}`);
    }
    const ok = sum === all.n;
    results.push({ label: `tier partition ${layer} sum`, ok, note: `${parts.join(' ')} sum=${sum} all=${all.n}` });
    console.log(`${ok ? 'PASS' : 'FAIL'}  tier partition ${layer}: ${parts.join(' ')} sum=${sum} all=${all.n}`);
  }
  await hit('unknown route -> 404', '/api/nope', null, 404);
  await hit('path traversal blocked -> 404', '/..%2f..%2fserver.mjs', null, 404);
  await hit('static styles.css', '/styles.css');
  await hit('static index.html (frontend)', '/');
} catch (e) {
  console.error('FATAL', e.message);
  failed++;
} finally {
  srv.kill();
}

const pass = results.filter(r => r.ok).length;
console.log(`\nSUMMARY: ${pass}/${results.length} passed, ${results.length - pass} failed`);
if (srvErr.trim()) console.log('--- server stderr ---\n' + srvErr.slice(0, 4000));
if (JSON_OUT) {
  fs.writeFileSync(JSON_OUT, JSON.stringify(results.map(({ sample, ...r }) => ({ ...r, top: sample && !Array.isArray(sample) ? Object.fromEntries(Object.entries(sample).filter(([, v]) => typeof v !== 'object' || v === null).slice(0, 12)) : undefined })), null, 2));
  console.log('written', JSON_OUT);
}
process.exit(results.length - pass > 0 ? 1 : 0);
