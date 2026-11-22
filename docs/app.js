/* Urban Lab „Ekonomija grada“ — statički 2D/3D GIS (GitHub Pages).
 * Čita samo fajlove iz ./data/ koje pravi urban_lab_app/tools/export_static.mjs iz baze v4.2.
 * Bez servera i bez zavisnosti osim MapLibre GL. */
(() => {
'use strict';

// ── osnovno ────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const safeUrl = u => (typeof u === 'string' && /^https?:\/\//i.test(u)) ? esc(u) : '';
const nf = (v, d = 0) => (v == null || !Number.isFinite(Number(v))) ? '—' : Number(v).toLocaleString('sr-Latn-RS', { minimumFractionDigits: d, maximumFractionDigits: d });
const norm = s => String(s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'dj');
const cache = new Map();
let pending = 0;
function getJSON(rel) {
  if (!cache.has(rel)) {
    pending++; $('loading').style.display = '';
    cache.set(rel, fetch('data/' + rel).then(r => { if (!r.ok) throw new Error(rel + ' → ' + r.status); return r.json(); })
      .finally(() => { if (--pending === 0) $('loading').style.display = 'none'; }));
  }
  return cache.get(rel);
}

// Paleta: sekvencijalna jedna nijansa (tamno→svetlo na tamnoj podlozi), kategorije u fiksnom redu.
const SEQ = ['#104281', '#1c5cab', '#2a78d6', '#5598e7', '#9ec5f4'];
const CAT = { blue: '#3987e5', orange: '#d95926', aqua: '#199e70', yellow: '#c98500', magenta: '#d55181', green: '#0ca30c', violet: '#9085e9', red: '#e66767' };
const GRAY = '#64748b';
const LANDUSE = { agriculture: ['Poljoprivreda', CAT.yellow], forest: ['Šuma', CAT.green], residential: ['Stanovanje', CAT.blue], industrial: ['Industrija', CAT.violet], commercial_retail: ['Trgovina', CAT.orange], extraction_quarry: ['Kop', CAT.magenta] };
const BLOCS = { incumbent_national: ['Vlast (nacionalna)', CAT.blue], opposition_civic_green: ['Opozicija građansko-zelena', CAT.orange], opposition_center_right: ['Opozicija desni centar', CAT.aqua], minority_regional: ['Manjinske/regionalne', CAT.yellow], other: ['Ostalo', GRAY] };
const POI = { bakery: ['Pekara', CAT.orange], marketplace: ['Pijaca', CAT.aqua], railway_station: ['Žel. stanica', CAT.violet], bus_station: ['Autobuska stanica', CAT.blue] };
const matchExpr = (key, dict) => ['match', ['get', key], ...Object.entries(dict).flatMap(([k, v]) => [k, v[1]]), GRAY];

const TIERS = ['A1', 'A2', 'B', 'C', 'D'];
const CITY_ZOOM = { beograd: 9.4, zagreb: 10.8, sarajevo: 11.2, novi_pazar: 11.4, travnik: 11.6 };
const SCALES = {
  XS: { zoom: 15, pitch: 55, on: ['buildings3d', 'rentgap', 'transit', 'elections'], note: 'zgrada · parcela · biračko mesto' },
  S:  { zoom: 12.6, pitch: 0, on: ['subzones', 'tax_zones', 'bakeries', 'ookla'], note: 'naselje · poreska zona · pekara' },
  M:  { zoom: null, pitch: 0, on: ['admin', 'procurement'], note: 'opština · gradska četvrt' },
  L:  { zoom: 8.2, pitch: 0, on: ['admin', 'hinterland', 'commuting', 'landuse'], note: 'prsten zaleđa · dnevne migracije' },
  XL: { zoom: 5.6, pitch: 0, on: ['admin', 'corridors'], note: 'koridori · makro-region', center: [18.4, 44.5] }
};
const LENSES = [
  { key: 'avg_net_wage_eur', label: 'Neto zarada', unit: 'EUR', d: 0 },
  { key: 'avg_apt_price_eur_m2', label: 'Cena stana', unit: 'EUR/m²', d: 0 },
  { key: 'affordability_years_55m2', label: 'Godina zarada za 55 m²', unit: 'god', d: 1 },
  { key: 'density_per_km2', label: 'Gustina naseljenosti', unit: 'st/km²', d: 0 },
  { key: 'avg_fixed_dl_mbps', label: 'Brzina interneta (Ookla)', unit: 'Mb/s', d: 0 },
  { key: 'avg_turnout_pct', label: 'Izlaznost na izborima', unit: '%', d: 1 },
  { key: 'transit_stops_n', label: 'Stajališta javnog prevoza', unit: 'kom', d: 0 },
  { key: 'dist_cbd_km', label: 'Udaljenost od centra', unit: 'km', d: 1 }
];

const state = { city: 'beograd', scale: 'M', mode3d: false, tiers: new Set(TIERS), lens: LENSES[0], on: new Set(SCALES.M.on), dossier: null, dTab: 'pregled', trayTab: null };
let boot, meta, map, breaks = [];

// ── slojevi ────────────────────────────────────────────────────────────────
// file(city) → putanja ili null kad sloj za taj grad ne postoji
const lensFill = () => ['case', ['!', ['has', state.lens.key]], 'rgba(148,163,184,0.10)', ['step', ['get', state.lens.key], SEQ[0], ...breaks.flatMap((b, i) => [b, SEQ[i + 1]])]];
const seqStep = (key, stops) => ['step', ['coalesce', ['get', key], 0], SEQ[0], ...stops.flatMap((b, i) => [b, SEQ[i + 1]])];
const LAYERS = [
  { id: 'admin', group: 'M', label: 'Opštine / četvrti', sw: SEQ[2], zone: true, file: () => 'zones/admin.geojson',
    make: s => [{ id: 'admin', type: 'fill', source: s, paint: { 'fill-color': lensFill(), 'fill-opacity': 0.72 } },
                { id: 'admin-line', type: 'line', source: s, paint: { 'line-color': '#e2e8f0', 'line-width': 1, 'line-opacity': 0.55 } }] },
  { id: 'subzones', group: 'S', label: 'Mjesni odbori / naselja', sw: SEQ[3], zone: true,
    file: c => c === 'zagreb' ? 'zones/zagreb_mo.geojson' : c === 'novi_pazar' ? 'zones/np_naselja.geojson' : null,
    make: s => [{ id: 'subzones', type: 'fill', source: s, paint: { 'fill-color': lensFill(), 'fill-opacity': 0.6 } },
                { id: 'subzones-line', type: 'line', source: s, paint: { 'line-color': '#e2e8f0', 'line-width': 0.6, 'line-opacity': 0.5 } }] },
  { id: 'tax_zones', group: 'S', label: 'Poreske zone (cena stana)', sw: SEQ[4], zone: true,
    file: c => (c === 'beograd' || c === 'novi_pazar') ? 'zones/tax_zones.geojson' : null,
    legend: { title: 'Poreska osnovica stana, EUR/m²', stops: [300, 700, 1200, 1800] },
    make: s => [{ id: 'tax_zones', type: 'fill', source: s, paint: { 'fill-color': seqStep('stan_eur_m2', [300, 700, 1200, 1800]), 'fill-opacity': 0.6 } },
                { id: 'tax_zones-line', type: 'line', source: s, paint: { 'line-color': '#0f1623', 'line-width': 0.4 } }] },
  { id: 'grid', group: 'S', label: 'Popis 2022, mreža 1 km', sw: SEQ[1],
    file: c => (c === 'beograd' || c === 'novi_pazar') ? `zones/grid_1km_${c}.geojson` : null,
    legend: { title: 'Stanovnika po km²', stops: [100, 1000, 4000, 10000] },
    make: s => [{ id: 'grid', type: 'fill', source: s, paint: { 'fill-color': seqStep('vrednost', [100, 1000, 4000, 10000]), 'fill-opacity': 0.6 } }] },
  { id: 'ookla', group: 'S', label: 'Internet — Ookla pločice', sw: SEQ[3], file: c => `city/${c}/ookla.geojson`,
    legend: { title: 'Fiksni download, Mb/s', stops: [50, 120, 200, 300] },
    make: s => [{ id: 'ookla', type: 'fill-extrusion', source: s, paint: { 'fill-extrusion-color': seqStep('avg_d_mbps', [50, 120, 200, 300]), 'fill-extrusion-height': ['get', 'extrude_h'], 'fill-extrusion-opacity': 0.7 } }], flatIn2d: 'fill-extrusion-height' },
  { id: 'bakeries', group: 'S', label: 'Pekare, pijace, stanice', sw: CAT.orange, file: () => 'zones/bakeries.geojson', cats: ['fclass', POI],
    make: s => [{ id: 'bakeries', type: 'circle', source: s, paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 8, 2, 14, 5], 'circle-color': matchExpr('fclass', POI), 'circle-stroke-color': '#0f1623', 'circle-stroke-width': 1 } }] },
  { id: 'buildings3d', group: 'XS', label: '3D zgrade', sw: CAT.violet, file: c => `city/${c}/buildings3d.geojson`,
    legend: { title: 'Visina zgrade, m', stops: [6, 12, 25, 50] },
    make: s => [{ id: 'buildings3d', type: 'fill-extrusion', source: s, paint: { 'fill-extrusion-color': seqStep('height_m', [6, 12, 25, 50]), 'fill-extrusion-height': ['get', 'height_m'], 'fill-extrusion-opacity': 0.85 } }], flatIn2d: 'fill-extrusion-height' },
  { id: 'rentgap', group: 'XS', label: 'Rent-gap parcele (neiskorišćen FAR)', sw: CAT.red, zone: true, file: c => `city/${c}/rentgap.geojson`,
    make: s => [{ id: 'rentgap', type: 'fill-extrusion', source: s, paint: { 'fill-extrusion-color': CAT.red, 'fill-extrusion-height': ['coalesce', ['get', 'extrude_h'], 10], 'fill-extrusion-opacity': 0.3 } }], flatIn2d: 'fill-extrusion-height' },
  { id: 'transit', group: 'XS', label: 'Stajališta javnog prevoza', sw: CAT.aqua, file: c => `city/${c}/transit.geojson`,
    make: s => [{ id: 'transit', type: 'circle', source: s, paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 9, 1.2, 15, 4.5], 'circle-color': CAT.aqua, 'circle-opacity': 0.85 } }] },
  { id: 'elections', group: 'XS', label: 'Izbori — biračka mesta', sw: CAT.blue, file: c => `city/${c}/elections.geojson`, cats: ['winner_bloc', BLOCS],
    make: s => [{ id: 'elections', type: 'circle', source: s, paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 9, ['case', ['==', ['get', 'kind'], 'zone_aggregate'], 11, 2.5], 15, ['case', ['==', ['get', 'kind'], 'zone_aggregate'], 13, 7]],
      'circle-color': matchExpr('winner_bloc', BLOCS), 'circle-stroke-color': '#0f1623', 'circle-stroke-width': 1, 'circle-opacity': 0.9 } }] },
  { id: 'procurement', group: 'M', label: 'Javne nabavke (TED / EJN)', sw: CAT.yellow, file: c => `city/${c}/procurement.geojson`,
    make: s => [{ id: 'procurement', type: 'circle', source: s, paint: { 'circle-radius': ['interpolate', ['linear'], ['sqrt', ['coalesce', ['get', 'contracts_n'], 1]], 1, 7, 15, 26], 'circle-color': CAT.yellow, 'circle-opacity': 0.55, 'circle-stroke-color': '#fde68a', 'circle-stroke-width': 1.5 } }] },
  { id: 'hinterland', group: 'L', label: 'Zaleđe (L prsten)', sw: CAT.magenta, zone: true, file: () => 'zones/hinterland.geojson',
    make: s => [{ id: 'hinterland', type: 'fill', source: s, paint: { 'fill-color': CAT.magenta, 'fill-opacity': 0.16 } },
                { id: 'hinterland-line', type: 'line', source: s, paint: { 'line-color': CAT.magenta, 'line-width': 1.4, 'line-dasharray': [3, 2] } }] },
  { id: 'commuting', group: 'L', label: 'Dnevne migracije', sw: '#e2e8f0', file: c => `city/${c}/commuting.geojson`,
    make: s => [{ id: 'commuting', type: 'line', source: s, layout: { 'line-cap': 'round' }, paint: { 'line-color': '#e2e8f0', 'line-opacity': 0.75, 'line-width': ['interpolate', ['linear'], ['coalesce', ['get', 'commuters_total'], 0], 0, 1.5, 20000, 9] } }] },
  { id: 'landuse', group: 'L', label: 'Namena zemljišta (OSM)', sw: CAT.green, file: () => 'zones/landuse.geojson', cats: ['macro_group', LANDUSE],
    make: s => [{ id: 'landuse', type: 'fill', source: s, paint: { 'fill-color': matchExpr('macro_group', LANDUSE), 'fill-opacity': 0.45 } }] },
  { id: 'corridors', group: 'XL', label: 'Strateški koridori', sw: CAT.orange, file: () => 'zones/corridors.geojson',
    make: s => [{ id: 'corridors', type: 'line', source: s, layout: { 'line-cap': 'round' }, paint: { 'line-color': CAT.orange, 'line-width': ['interpolate', ['linear'], ['coalesce', ['get', 'investment_mio_eur'], 0], 0, 2, 3000, 7], 'line-opacity': 0.9 } }] }
];
const ORDER = ['landuse', 'grid', 'hinterland', 'admin', 'subzones', 'tax_zones', 'ookla', 'rentgap', 'buildings3d', 'commuting', 'corridors', 'transit', 'bakeries', 'procurement', 'elections'];
const byId = Object.fromEntries(LAYERS.map(l => [l.id, l]));
const subLayerIds = l => l._ids || [];

const tierFilter = () => ['any', ['!', ['has', 'trust_tier']], ['in', ['get', 'trust_tier'], ['literal', [...state.tiers]]]];

async function syncLayers() {
  for (const id of ORDER) {
    const l = byId[id];
    const file = l.file(state.city);
    const want = state.on.has(id) && !!file;
    if (!want) { for (const sid of subLayerIds(l)) if (map.getLayer(sid)) map.setLayoutProperty(sid, 'visibility', 'none'); continue; }
    if (l._file !== file) {
      let data;
      try { data = await getJSON(file); } catch (e) { console.warn(e); continue; }
      if (l.file(state.city) !== file) continue; // grad promenjen dok se učitavalo
      l._file = file; l._n = data.features.length;
      if (map.getSource('s-' + id)) map.getSource('s-' + id).setData(data);
      else {
        map.addSource('s-' + id, { type: 'geojson', data });
        const defs = l.make('s-' + id);
        l._ids = defs.map(d => d.id);
        for (const d of defs) map.addLayer(d);
      }
    }
    for (const sid of subLayerIds(l)) {
      map.setLayoutProperty(sid, 'visibility', 'visible');
      map.setFilter(sid, tierFilter());
      map.moveLayer(sid);
    }
    if (l.flatIn2d) map.setPaintProperty(id, l.flatIn2d, state.mode3d ? byId[id].make('x')[0].paint[l.flatIn2d] : 0);
  }
  renderLayerList(); renderLegend();
}

// ── sočivo: zajednička skala za svih pet gradova ───────────────────────────
async function computeBreaks() {
  const admin = await getJSON('zones/admin.geojson');
  const vals = admin.features.map(f => f.properties[state.lens.key]).filter(v => typeof v === 'number').sort((a, b) => a - b);
  const q = p => vals[Math.min(vals.length - 1, Math.floor(p * vals.length))];
  breaks = vals.length ? [...new Set([0.2, 0.4, 0.6, 0.8].map(q))].filter((b, i, a) => i === 0 || b > a[i - 1]) : [];
  while (breaks.length < 4) breaks.push((breaks[breaks.length - 1] ?? 0) + 1); // step traži rastuće pragove
  state.lensN = vals.length; state.lensCov = {};
  for (const f of admin.features) if (typeof f.properties[state.lens.key] === 'number') state.lensCov[f.properties.city_id] = (state.lensCov[f.properties.city_id] || 0) + 1;
  for (const id of ['admin', 'subzones']) if (map.getLayer(id)) map.setPaintProperty(id, 'fill-color', lensFill());
}

function rampHTML(title, stops, d = 0) {
  return `<div class="sub-hd">${esc(title)}</div><div class="legend-bar" style="background:linear-gradient(90deg,${SEQ.map((c, i) => `${c} ${i * 20}%,${c} ${(i + 1) * 20}%`).join(',')})"></div>
    <div class="legend-ticks"><span>min</span>${stops.map(s => `<span>${nf(s, d)}</span>`).join('')}<span>max</span></div>`;
}
function renderLegend() {
  const cityName = boot.cities.find(c => c.city_id === state.city)?.city_name;
  const cov = state.lensCov?.[state.city] || 0;
  let h = rampHTML(`${state.lens.label}, ${state.lens.unit}`, breaks, state.lens.d);
  h += `<div class="kpi-note">Skala je zajednička za svih pet gradova (kvintili, ${nf(state.lensN)} jedinica). ${esc(cityName)}: ${cov ? nf(cov) + ' jedinica ima vrednost' : 'nema ovaj podatak — zone su sive'}.</div>`;
  for (const id of ORDER) {
    const l = byId[id];
    if (!state.on.has(id) || !l.file(state.city)) continue;
    if (l.legend) h += `<div style="margin-top:10px">${rampHTML(l.legend.title, l.legend.stops)}</div>`;
    if (l.cats) h += `<div style="margin-top:10px"><div class="sub-hd">${esc(l.label)}</div><div class="legend-cats">${Object.values(l.cats[1]).map(([n, c]) => `<span><i class="layer-swatch" style="background:${c}"></i>${esc(n)}</span>`).join('')}</div></div>`;
  }
  $('legend').innerHTML = h;
}

// ── leva tabla ─────────────────────────────────────────────────────────────
function renderTiers() {
  $('tierGrid').innerHTML = boot.trust_tiers.map(t => `<div class="tier-pill ${state.tiers.has(t.tier_code) ? 'active' : ''}" data-tier="${esc(t.tier_code)}" title="${esc(t.label_sr)} — ${esc(t.description)}" role="button" tabindex="0">${esc(t.tier_code)}<small>${esc(t.label_sr.split(/[\s/]/)[0])}</small></div>`).join('');
}
function setTiers(list) {
  state.tiers = new Set(list.length ? list : TIERS);
  renderTiers(); syncLayers(); if (state.dossier) renderDossier();
}
function renderLenses() {
  $('lensList').innerHTML = LENSES.map(l => `<button class="lens-btn ${l === state.lens ? 'active' : ''}" data-lens="${l.key}"><span>${esc(l.label)}</span><span class="lens-tag">${esc(l.unit)}</span></button>`).join('');
}
function renderLayerList() {
  $('layerCity').textContent = boot.cities.find(c => c.city_id === state.city)?.city_name || '';
  let h = '', g = '';
  for (const l of LAYERS) {
    if (l.group !== g) { g = l.group; h += `<div class="layer-group">${g} · ${esc(SCALES[g].note)}</div>`; }
    const file = l.file(state.city);
    const n = meta.layer_counts[state.city]?.[l.id] ?? (l._file === file ? l._n : null);
    const cnt = !file ? 'nema za grad' : n == null ? '' : nf(n);
    h += `<div class="layer-row ${file ? '' : 'off'}"><label><input type="checkbox" data-layer="${l.id}" ${state.on.has(l.id) ? 'checked' : ''} ${file ? '' : 'disabled'}><span class="layer-swatch" style="background:${l.sw}"></span>${esc(l.label)}</label><span class="layer-cnt">${cnt}</span></div>`;
  }
  $('layerList').innerHTML = h;
}

// ── gornja traka ───────────────────────────────────────────────────────────
function renderTop() {
  $('cityPills').innerHTML = boot.cities.map(c => `<button class="pill-btn ${c.city_id === state.city ? 'active' : ''}" data-city="${esc(c.city_id)}">${esc(c.city_name)}</button>`).join('');
  $('scalePills').innerHTML = Object.keys(SCALES).map(s => `<button class="pill-btn scale-btn ${s === state.scale ? 'active' : ''}" data-scale="${s}" title="${esc(SCALES[s].note)}">${s}</button>`).join('');
  $('btn2d').classList.toggle('active', !state.mode3d); $('btn3d').classList.toggle('active', state.mode3d);
  const c = boot.cities.find(x => x.city_id === state.city);
  $('hud').innerHTML = `<div class="hud-chip"><strong>${esc(c.city_name)}</strong> ${esc(c.country_iso3)}</div>
    <div class="hud-chip">Stanovnika <strong class="num">${nf(c.population)}</strong></div>
    <div class="hud-chip">Neto zarada <strong class="num">${nf(c.avg_net_wage_eur)} EUR</strong></div>
    <div class="hud-chip">Stan u jezgru <strong class="num">${nf(c.core_housing_eur_m2)} EUR/m²</strong></div>
    <div class="hud-chip">Skala <strong>${state.scale}</strong> ${esc(SCALES[state.scale].note)}</div>`;
}
function fly() {
  const sc = SCALES[state.scale], c = boot.cities.find(x => x.city_id === state.city);
  map.flyTo({ center: sc.center || [c.cbd_lon, c.cbd_lat], zoom: sc.zoom ?? CITY_ZOOM[state.city] ?? 11, pitch: state.mode3d ? Math.max(sc.pitch, 55) : 0, bearing: state.mode3d ? -15 : 0, duration: 1100 });
}
function setCity(id, { open = true } = {}) {
  state.city = id; renderTop(); fly(); syncLayers(); renderTray();
  if (open && meta.city_core[id]) openDossier(meta.city_core[id], false);
}
function setScale(s) {
  state.scale = s; state.on = new Set(SCALES[s].on);
  state.mode3d = !!SCALES[s].pitch; // skala bira prikaz; dugme 2D/3D ga posle menja ručno
  renderTop(); fly(); syncLayers();
}
function setMode(m3) { state.mode3d = m3; renderTop(); map.easeTo({ pitch: m3 ? 55 : 0, bearing: m3 ? -15 : 0, duration: 700 }); syncLayers(); }

// ── klik: popup + dosije ───────────────────────────────────────────────────
const POPUP_FIELDS = {
  buildings3d: f => [f.building_name || f.address_text || 'Zgrada', [['Visina', nf(f.height_m, 1) + ' m'], ['Spratova', nf(f.floors_above_ground)], ['Osnova', nf(f.footprint_area_m2) + ' m²'], ['Namena', f.building_use], ['Izvor visine', f.height_source]]],
  ookla: f => ['Ookla pločica ' + (f.quarter || ''), [['Download', nf(f.avg_d_mbps, 1) + ' Mb/s'], ['Upload', nf(f.avg_u_mbps, 1) + ' Mb/s'], ['Latencija', nf(f.avg_lat_ms) + ' ms'], ['Testova', nf(f.tests_count)]]],
  elections: f => [f.station_name || f.name, [['Izbori', f.election_date + ' · ' + f.authority_body], ['Upisano', nf(f.registered_voters)], ['Izlaznost', nf(f.turnout_pct, 1) + ' %'], ['Prva lista', (BLOCS[f.winner_bloc] || [f.winner_bloc])[0]], ['Prednost', nf(f.winning_margin_pp, 1) + ' pp'], ['Preciznost', f.geo_precision]]],
  transit: f => [f.stop_name || 'Stajalište', [['Vid', f.mode], ['Od centra', nf(f.dist_cbd_km, 1) + ' km']]],
  bakeries: f => [f.name || (POI[f.fclass] || [f.fclass])[0], [['Vrsta', (POI[f.fclass] || [f.fclass])[0]], ['Od centra', nf(f.dist_cbd_km, 1) + ' km'], ['Prsten', f.ring]]],
  procurement: f => [f.zone_name, [['Ugovora', nf(f.contracts_n)], ['Vrednost', nf(f.total_eur_m, 2) + ' mil. EUR'], ['Jedan ponuđač', nf(f.single_bidder_pct, 1) + ' %'], ['Period', (f.first_date || '') + ' – ' + (f.last_date || '')]]],
  rentgap: f => [f.tax_zone_name || f.cadastral_municipality, [['Dozvoljen FAR', nf(f.max_far, 1)], ['Iskorišćenost FAR', nf(f.far_utilization_pct, 1) + ' %'], ['Neiskorišćen BGP', nf(f.unused_buildable_gfa_m2) + ' m²'], ['Tržišna procena', nf(f.market_est_eur_m2) + ' EUR/m²']]],
  commuting: f => [`${f.origin_name} → ${f.dest_name}`, [['Dnevnih migranata', nf(f.commuters_total)], ['Van opštine', nf(f.commuters_external)], ['Uloga', f.ring_role]]],
  corridors: f => [f.name, [['Investicija', nf(f.investment_mio_eur) + ' mil. EUR']]],
  landuse: f => [f.name || (LANDUSE[f.macro_group] || [f.macro_group])[0], [['Namena', f.fclass], ['Površina', nf(f.area_km2, 2) + ' km²'], ['Prsten', f.ring]]],
  grid: f => ['Ćelija 1 km (Popis ' + (f.god || '2022') + ')', [['Stanovnika', nf(f.vrednost)]]],
  tax_zones: f => [f.unit_name || f.zone_name, [['Stan', nf(f.stan_eur_m2) + ' EUR/m²'], ['Poslovni prostor', nf(f.poslovne_eur_m2) + ' EUR/m²'], ['Građ. zemljište', nf(f.gradj_zem_eur_m2, 1) + ' EUR/m²'], ['Polj. zemljište', nf(f.polj_zem_eur_m2, 2) + ' EUR/m²']]],
  hinterland: f => [f.unit_name, [['Stanovnika', nf(f.population)], ['Od centra', nf(f.dist_cbd_km, 1) + ' km'], ['Dnevnih migranata', nf(f.commuters_total)], ['Uloga', f.supply_chain_role]]]
};
function zonePopup(f) {
  const rows = LENSES.filter(l => typeof f[l.key] === 'number').slice(0, 6).map(l => [l.label, nf(f[l.key], l.d) + ' ' + l.unit]);
  if (f.population != null) rows.unshift(['Stanovnika', nf(f.population)]);
  return [f.unit_name, rows];
}
let popup;
function onClick(e) {
  const ids = ORDER.flatMap(id => subLayerIds(byId[id])).filter(id => map.getLayer(id) && map.getLayoutProperty(id, 'visibility') !== 'none' && !id.endsWith('-line'));
  const feats = map.queryRenderedFeatures(e.point, { layers: ids });
  if (popup) popup.remove();
  if (!feats.length) return;
  const top = feats[0], p = top.properties;
  const [title, rows] = (POPUP_FIELDS[top.layer.id] || zonePopup)(p);
  const tier = p.trust_tier ? `<span class="t-badge t-${esc(p.trust_tier)}">${esc(p.trust_tier)}</span> ` : '';
  popup = new maplibregl.Popup({ maxWidth: '300px' }).setLngLat(e.lngLat)
    .setHTML(`<div class="popup-t">${tier}${esc(title)}</div>${rows.filter(r => r[1] != null && !/^—/.test(String(r[1])) && !/undefined/.test(String(r[1]))).map(r => `<div class="popup-r"><span>${esc(r[0])}</span><b>${esc(r[1])}</b></div>`).join('')}`).addTo(map);
  const zoneFeat = feats.find(f => byId[f.layer.id]?.zone && f.properties.gazetteer_id);
  if (zoneFeat) openDossier(zoneFeat.properties.gazetteer_id, true);
}

// ── dosije ─────────────────────────────────────────────────────────────────
async function openDossier(id, show) {
  try {
    state.dossier = await getJSON(`dossier/${id}.json`);
    if (show) { document.body.classList.remove('right-collapsed'); $('btnRight').classList.add('active'); }
    renderDossier();
  } catch { /* za tu tačku nema izvezenog dosijea */ }
}
const badge = t => t ? `<span class="t-badge t-${esc(t)}">${esc(t)}</span>` : '';
const kpi = (label, val, note = '') => `<div class="kpi-card"><div class="kpi-label">${esc(label)}</div><div class="kpi-val num">${val}</div>${note ? `<div class="kpi-note">${esc(note)}</div>` : ''}</div>`;
const inTier = r => !r.trust_tier || state.tiers.has(r.trust_tier);
const table = (heads, rows) => rows.length ? `<table class="mini-table"><thead><tr>${heads.map(h => `<th class="${h[1] ? 'num' : ''}">${esc(h[0])}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map((c, i) => `<td class="${heads[i][1] ? 'num' : ''}">${c}</td>`).join('')}</tr>`).join('')}</tbody></table>` : '<div class="empty">Nema podataka za ovu zonu i izabrane nivoe poverenja.</div>';
const sec = (title, body) => `<div><div class="section-hd"><span>${esc(title)}</span></div>${body}</div>`;
const SCOPE = { zone: 'za zonu', city: 'za ceo grad', city_context: 'gradski kontekst — za samu zonu nema zapisa' };

const D_TABS = {
  pregled: ['Pregled', d => {
    const a = d.admin || {}, u = d.unified || {}, z = d.zone;
    const maxLq = Math.max(1, ...d.sectors.map(s => s.location_quotient || 0));
    return `<div class="kpi-grid">
        ${kpi('Stanovnika', nf(a.population), a.population_year ? 'Popis ' + a.population_year : '')}
        ${kpi('Gustina', nf(a.density_per_km2) + ' /km²')}
        ${kpi('Neto zarada', nf(a.avg_net_wage_eur) + ' EUR')}
        ${kpi('Firmi', nf(a.companies_count), a.companies_rev_eur_m != null ? 'prihod ' + nf(a.companies_rev_eur_m) + ' mil. EUR' : '')}
        ${kpi('Od centra', nf(z.dist_cbd_km, 1) + ' km')}
        ${kpi('Površina', nf(z.area_km2 ?? a.area_km2, 1) + ' km²')}
      </div>
      ${a.source_note ? `<div class="kpi-note">Izvor: ${esc(a.source_note)}</div>` : ''}
      ${sec('Sektori — lokacijski količnik (LQ)', d.sectors.length ? d.sectors.map(s => `<div class="bar-row"><div class="bar-meta"><span title="${esc(s.unit_name)}">${esc(s.nace_section)} · ${esc(s.nace_name)}</span><span class="num">${nf(s.location_quotient, 2)}</span></div><div class="bar-track"><div class="bar-fill" style="width:${Math.min(100, 100 * s.location_quotient / maxLq)}%;background:${SEQ[3]}"></div></div></div>`).join('') + `<div class="kpi-note">LQ &gt; 1: sektor je zastupljeniji nego u proseku. Jedinica: ${esc(d.sectors[0].unit_name)}.</div>` : '<div class="empty">Nema sektorske strukture.</div>')}
      ${sec('Cene nekretnina (grad)', table([['Zona'], ['Vrsta'], ['EUR/m²', 1]], d.property_prices.map(p => [esc(p.zone_or_unit), esc(p.property_type), nf(p.price_eur_m2)])))}`;
  }],
  prostor: ['Prostor', d => {
    const o = d.ookla.zone || {}, ob = d.ookla.city_benchmark || {};
    return `${sec(`3D zgrade (${SCOPE[d.buildings_3d.scope]})`, table([['Nivo'], ['Izvor visine'], ['Broj', 1], ['Pros. m', 1], ['Maks. m', 1]], d.buildings_3d.by_tier.filter(inTier).map(b => [badge(b.trust_tier), esc(b.height_source), nf(b.count), nf(b.avg_height_m, 1), nf(b.max_height_m, 1)])))}
      ${sec(`Internet (${SCOPE[d.ookla.scope]})`, `<div class="kpi-grid">${kpi('Download', nf(o.weighted_dl_mbps, 1) + ' Mb/s', 'grad: ' + nf(ob.weighted_dl_mbps, 1))}${kpi('Upload', nf(o.weighted_ul_mbps, 1) + ' Mb/s', 'grad: ' + nf(ob.weighted_ul_mbps, 1))}${kpi('Pločica', nf(o.tiles_n))}${kpi('Testova', nf(o.tests_n))}</div>`)}
      ${sec('Javni prevoz', table([['Vid'], ['Nivo'], ['Stajališta', 1]], d.transit.filter(inTier).map(t => [esc(t.mode), badge(t.trust_tier), nf(t.stops_n)])))}
      ${sec('Rent-gap parcele', table([['Zona'], ['FAR', 1], ['Iskor. %', 1], ['Rezerva, mil. EUR', 1]], d.rent_gap.filter(inTier).map(r => [esc(r.tax_zone_name || r.cadastral_municipality), nf(r.max_far, 1), nf(r.far_utilization_pct, 1), nf((r.implied_development_headroom_eur || 0) / 1e6, 1)])))}
      ${sec('Klima i vazduh (grad)', table([['Metrika'], ['Nivo'], ['Prosek', 1], ['Maks.', 1]], (d.sensors || []).filter(inTier).map(s => [esc(s.sensor_metric) + ' <span class="layer-cnt">' + esc(s.value_unit) + '</span>', badge(s.trust_tier), nf(s.avg_val, 1), nf(s.max_val, 1)])))}
      ${(d.sepa || []).length ? sec('Industrijske emisije (SEPA)', table([['Postrojenje'], ['Zagađivač'], ['t/god', 1]], d.sepa.filter(inTier).map(s => [esc(s.facility_name || s.company_name), esc(s.pollutant_name), nf(s.quantity_kg_year / 1000)]))) : ''}`;
  }],
  politika: ['Politika', d => {
    const ps = d.procurement.stats || {};
    return `${sec('Izborni ciklusi', table([['Datum'], ['Telo'], ['BM', 1], ['Izlaznost %', 1], ['Prednost pp', 1], ['ENP', 1]], d.elections.cycles.map(c => [esc(c.election_date), esc(c.authority_body), nf(c.stations_n), nf(c.avg_turnout_pct, 1), nf(c.avg_margin_pp, 1), nf(c.avg_enp, 2)])))}
      ${sec('Liste po glasovima', table([['Lista'], ['Glasova', 1], ['%', 1]], d.elections.top_parties.map(p => [`<span title="${esc(p.list_or_candidate_name)}">${esc(String(p.list_or_candidate_name).slice(0, 60))}</span><br><span class="layer-cnt">${esc((BLOCS[p.comparative_bloc] || [p.comparative_bloc])[0])}</span>`, nf(p.votes), nf(p.avg_share_pct, 1)])))}
      ${sec(`Javne nabavke (${SCOPE[d.procurement.scope]})`, `<div class="kpi-grid">${kpi('Ugovora', nf(ps.contracts_n))}${kpi('Vrednost', nf(ps.total_eur_m, 2) + ' mil. EUR')}${kpi('Jedan ponuđač', nf(ps.single_bidder_pct, 1) + ' %')}</div>
        <div style="display:flex;flex-direction:column;gap:6px;margin-top:8px">${d.procurement.contracts.filter(inTier).map(c => `<div class="doc-card">${safeUrl(c.primary_url) ? `<a href="${safeUrl(c.primary_url)}" target="_blank" rel="noopener noreferrer">${esc(c.doc_title || c.contract_uid)}</a>` : `<span>${esc(c.doc_title || c.contract_uid)}</span>`}<div class="doc-meta">${badge(c.trust_tier)}<span>${esc(c.award_date)}</span><span>${esc(c.buyer_name)}</span>${c.contract_value_eur ? `<span class="num">${nf(c.contract_value_eur)} EUR</span>` : ''}</div></div>`).join('') || '<div class="empty">Nema ugovora.</div>'}</div>`)}`;
  }],
  dokazi: ['Dokazi', d => {
    const docs = d.documents.items.filter(inTier), sci = (d.science || []).filter(inTier);
    const card = (x, extra) => `<div class="doc-card">${safeUrl(x.primary_url) ? `<a href="${safeUrl(x.primary_url)}" target="_blank" rel="noopener noreferrer">${esc(x.title)}</a>` : `<span>${esc(x.title)}</span>`}<div class="doc-meta">${badge(x.trust_tier)}${extra}</div></div>`;
    return `${sec(`Dokumenti (${SCOPE[d.documents.scope] || 'za zonu'})`, `<div style="display:flex;flex-direction:column;gap:6px">${docs.map(x => card(x, `<span>${esc(x.doc_type)}</span><span>${esc(x.published_at || '')}</span><span>${esc(x.geo_role || '')}</span>`)).join('') || '<div class="empty">Nema dokumenata za izabrane nivoe.</div>'}</div>`)}
      ${sec('Nauka i EU projekti (grad)', `<div style="display:flex;flex-direction:column;gap:6px">${sci.map(x => card(x, `<span>${esc(x.work_type)} ${esc(x.pub_year)}</span>${x.grant_amount_eur ? `<span class="num">${nf(x.grant_amount_eur)} EUR</span>` : `<span class="num">${nf(x.cited_by_count)} citata</span>`}<span>${esc(x.institution_name || '')}</span>`)).join('') || '<div class="empty">Nema zapisa.</div>'}</div>`)}`;
  }]
};
function renderDossier() {
  const d = state.dossier; if (!d) return;
  const z = d.zone, cityName = boot.cities.find(c => c.city_id === z.city_id)?.city_name || '';
  $('dTitle').textContent = z.canonical_name;
  $('dSub').innerHTML = `${badge(z.trust_tier)}<span>${esc(cityName)}</span><span>${esc(z.scale_level)} · ${esc(z.feature_class)}</span>`;
  $('dTabs').innerHTML = Object.entries(D_TABS).map(([k, v]) => `<button class="tab-btn ${k === state.dTab ? 'active' : ''}" data-dtab="${k}">${v[0]}</button>`).join('');
  const filtered = state.tiers.size < TIERS.length;
  $('dBody').innerHTML = (filtered ? `<div class="notice-box">Filter poverenja (${[...state.tiers].join(', ')}) ovde uklanja redove iz lista. Zbirni brojevi (internet, izbori, nabavke) računati su nad svim nivoima.</div>` : '') + D_TABS[state.dTab][1](d);
  $('dBody').scrollTop = 0;
}

// ── donja tabla ────────────────────────────────────────────────────────────
const sim = { flour: 100, energy: 100, labor: 100, rent: 100, price: 100 };
const TRAY = {
  scorecard: ['Uporedna tabela', () => {
    const cols = [['population', 'Stanovnika', 0], ['avg_net_wage_eur', 'Neto zarada EUR', 0], ['core_housing_eur_m2', 'Stan EUR/m²', 0], ['years_wage_for_55m2', 'God. zarada / 55 m²', 1], ['budget_eur_per_cap', 'Budžet EUR/st', 0], ['companies_count', 'Firmi', 0], ['ookla_dl_mbps', 'Internet Mb/s', 0], ['avg_turnout_pct', 'Izlaznost %', 1], ['avg_enp', 'ENP', 2], ['eu_cordis_eur_m', 'EU projekti mil. EUR', 1], ['avg_pm25_ugm3', 'PM2.5 µg/m³', 1], ['transit_stops_n', 'Stajališta', 0], ['buildings_3d_n', '3D zgrada', 0], ['evidence_docs_n', 'Dokumenata', 0]];
    return `<table class="scorecard-table"><thead><tr><th>Grad</th>${cols.map(c => `<th>${esc(c[1])}</th>`).join('')}</tr></thead><tbody>${boot.cities.map(c => `<tr data-city="${esc(c.city_id)}"><td><strong>${esc(c.city_name)}</strong></td>${cols.map(k => `<td class="num">${nf(c[k[0]], k[2])}</td>`).join('')}</tr>`).join('')}</tbody></table>
      <div class="kpi-note" style="margin-top:8px">Klik na red menja grad. Osnove nisu iste u svim gradovima (period zarade, osnov cene stana, obuhvat budžeta) — vidi tablu „Izvori i granice“.</div>`;
  }],
  sim: ['Šta-ako: pekara', () => {
    const sl = (k, label) => `<div class="slider-row"><label><span>${label}</span><span class="num" id="sv-${k}">${sim[k]} %</span></label><input type="range" min="50" max="200" step="5" value="${sim[k]}" data-sim="${k}"></div>`;
    return `<div class="sim-layout"><div class="sim-controls"><div class="sub-hd">Promena ulaznih cena (100 % = stanje u bazi)</div>${sl('flour', 'Brašno T-500')}${sl('energy', 'Energija (struja + drva)')}${sl('labor', 'Rad')}${sl('rent', 'Zakup lokala')}${sl('price', 'Cena hleba 500 g')}<button class="mini-btn" id="simReset">Vrati na 100 %</button></div><div><div class="sim-cards" id="simCards"></div><div class="kpi-note" style="margin-top:8px">Model male pekare iz pogleda <span class="num">v_s_bakery_5cities_comparison</span>: prag rentabilnosti = mesečni trošak ÷ (cena hleba bez PDV-a) ÷ 30 dana, zaokruženo naviše. Ostali troškovi ostaju nepromenjeni.</div></div></div>`;
  }],
  events: ['Studije događaja', () => `<div class="did-grid">${boot.event_studies.map((s, i) => `<div class="did-card"><h4>${esc(s.study_title)}</h4><div class="doc-meta">${badge(s.effective_trust_tier)}<span>t₀ ${esc(s.t0_date)}</span><span>${esc(s.outcome_unit || s.outcome_metric)}</span></div>
      <div class="did-legend"><span><i style="background:${CAT.blue}"></i>Tretirana grupa</span><span><i style="background:${CAT.orange}"></i>Kontrola</span></div>${didChart(s, i)}
      <div class="kpi-grid">${kpi('Tretirana Δ', nf(s.treated_delta, 2))}${kpi('Kontrola Δ', nf(s.control_delta, 2))}</div>${kpi('Razlika razlika (DiD)', nf(s.did_estimate, 2) + ' ' + esc(s.outcome_unit || ''))}
      <div class="kpi-note">${esc(s.hypothesis || '')}</div><div class="kpi-note">Tretman: ${esc(s.treatment_definition || '')} · Kontrola: ${esc(s.control_definition || '')}</div></div>`).join('')}</div>`],
  izvori: ['Izvori i granice', () => {
    const t = meta.db_totals, lc = meta.layer_counts;
    const cut = boot.cities.map(c => { const tot = t[c.city_id]?.buildings3d, n = lc[c.city_id]?.buildings3d; return tot > n ? `${esc(c.city_name)}: prikazano ${nf(n)} najviših od ${nf(tot)} zgrada` : null; }).filter(Boolean);
    return `<div class="src-grid"><div>
        <p><strong>Šta je ovo.</strong> Statički izvoz baze ${esc(meta.schema_version)} od ${esc(meta.generated_at.slice(0, 10))}. Sajt nema server: svaki sloj je fajl u <span class="num">data/</span>, a dosije postoji za ${nf(meta.dossiers.count)} zona.</p>
        <p><strong>Granice.</strong> ${cut.length ? cut.join('; ') + '. ' : ''}Novi Pazar nema javne nabavke u bazi. Izbori su po biračkom mestu samo za Beograd i Novi Pazar; Zagreb, Sarajevo i Travnik imaju zbirne tačke. 3D zgrade su kvadri nad okvirom zgrade, ne stvarne osnove; deo visina je procena (nivoi C i D).</p>
        <p><strong>Nivoi poverenja.</strong> ${boot.trust_tiers.map(x => `${badge(x.tier_code)} ${esc(x.label_sr)}`).join(' · ')}</p>
      </div><div>
        <p><strong>Izvori podataka.</strong> RZS, APR, RIK (Srbija); DZS, DIP, Grad Zagreb (Hrvatska); FZS, CIK, EJN (BiH); Eurostat, EU CORDIS, TED; OpenStreetMap saradnici (ODbL); GTFS operateri; OpenAQ, Copernicus ERA5/CAMS; brzine interneta: Speedtest® by Ookla® Global Fixed Network Performance Maps (CC BY-NC-SA 4.0). Podloga mape: © OpenStreetMap saradnici.</p>
        <p>Prava na pojedine izvedene skupove nisu proverena jedan po jedan; upotreba je nekomercijalna i istraživačka.</p>
        <p><a href="https://github.com/3esign/urban-lab" target="_blank" rel="noopener noreferrer">Kod, šema i skripte na GitHub-u</a></p>
        ${table([['Tabela'], ['Redova', 1], ['Gradova', 1]], boot.data_quality.map(q => [esc(q.domain_table), nf(q.total_rows), nf(q.cities_covered)]))}
      </div></div>`;
  }]
};
function bakery(b) {
  const parts = { flour: b.monthly_flour_eur * sim.flour / 100, energy: (b.monthly_wood_eur + b.monthly_elec_eur) * sim.energy / 100, labor: b.monthly_labor_eur * sim.labor / 100, rent: b.monthly_rent_eur * sim.rent / 100 };
  const other = b.monthly_total_cost_eur - (b.monthly_flour_eur + b.monthly_wood_eur + b.monthly_elec_eur + b.monthly_labor_eur + b.monthly_rent_eur);
  const total = parts.flour + parts.energy + parts.labor + parts.rent + other;
  const netPrice = b.bread_500g_retail_eur * sim.price / 100 / (1 + b.vat_bread_pct / 100);
  return { parts: { ...parts, other }, total, loaves: Math.ceil(total / netPrice / 30 - 1e-9) };
}
const SIM_PARTS = [['flour', 'Brašno', CAT.blue], ['energy', 'Energija', CAT.orange], ['labor', 'Rad', CAT.aqua], ['rent', 'Zakup', CAT.yellow], ['other', 'Ostalo', GRAY]];
function renderSim() {
  if (!$('simCards')) return;
  for (const k in sim) if ($('sv-' + k)) $('sv-' + k).textContent = sim[k] + ' %';
  $('simCards').innerHTML = boot.bakery_model.map(b => {
    const r = bakery(b), base = b.breakeven_loaves_per_day, dl = r.loaves - base;
    return `<div class="sim-city-card"><h4><span>${esc(b.city_name)}</span></h4><div><span class="sim-big num">${nf(r.loaves)}</span><span class="sim-delta ${dl > 0 ? 'bad' : dl < 0 ? 'good' : ''}">${dl === 0 ? 'osnova' : (dl > 0 ? '▲ +' : '▼ ') + nf(dl)}</span></div><div class="kpi-note">vekni dnevno do praga · osnova ${nf(base)}</div>
      <div class="stack-bar">${SIM_PARTS.map(([k, n, c]) => `<div title="${n}: ${nf(r.parts[k])} EUR (${nf(100 * r.parts[k] / r.total, 1)} %)" style="width:${100 * r.parts[k] / r.total}%;background:${c};margin-right:2px"></div>`).join('')}</div>
      <div class="kpi-note num">${nf(r.total)} EUR mesečno</div></div>`;
  }).join('') + `<div class="legend-cats" style="grid-column:1/-1">${SIM_PARTS.map(([, n, c]) => `<span><i class="layer-swatch" style="background:${c}"></i>${n}</span>`).join('')}</div>`;
}
function didChart(s, idx) {
  const obs = s.observations || []; if (!obs.length) return '<div class="empty">Nema opažanja.</div>';
  const W = 300, H = 120, L = 30, R = 8, T = 8, B = 20;
  const xs = [...new Set(obs.map(o => o.rel_period))].sort((a, b) => a - b);
  const ys = obs.map(o => o.metric_value).filter(v => v != null);
  const y0 = Math.min(0, ...ys), y1 = Math.max(...ys) * 1.08 || 1;
  const X = v => L + (W - L - R) * (xs.length > 1 ? (v - xs[0]) / (xs[xs.length - 1] - xs[0]) : 0.5);
  const Y = v => T + (H - T - B) * (1 - (v - y0) / (y1 - y0));
  const series = [['treated', CAT.blue], ['control', CAT.orange]].map(([key, color]) => {
    const pts = obs.filter(o => String(o.cohort_group).startsWith(key) && o.metric_value != null).sort((a, b) => a.rel_period - b.rel_period);
    return { color, pts, name: key === 'treated' ? 'Tretirana' : 'Kontrola' };
  }).filter(sr => sr.pts.length);
  const grid = [y0, (y0 + y1) / 2, y1].map(v => `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="rgba(148,163,184,0.15)"/><text x="${L - 4}" y="${Y(v) + 3}" text-anchor="end">${nf(v, v < 10 ? 1 : 0)}</text>`).join('');
  const marks = series.map(sr => `<polyline fill="none" stroke="${sr.color}" stroke-width="2" stroke-linejoin="round" points="${sr.pts.map(p => X(p.rel_period) + ',' + Y(p.metric_value)).join(' ')}"/>` +
    sr.pts.map(p => `<circle cx="${X(p.rel_period)}" cy="${Y(p.metric_value)}" r="4" fill="${sr.color}" stroke="#0f1623" stroke-width="2"/><circle class="did-hit" cx="${X(p.rel_period)}" cy="${Y(p.metric_value)}" r="10" fill="transparent" data-tip="${esc(sr.name)} · ${esc(p.calendar_period)} (t${p.rel_period >= 0 ? '+' : ''}${p.rel_period}): ${nf(p.metric_value, 2)} ${esc(s.outcome_unit || '')}"/>`).join('')).join('');
  const t0 = xs[0] <= 0 && xs[xs.length - 1] >= 0 ? `<line x1="${X(0)}" x2="${X(0)}" y1="${T}" y2="${H - B}" stroke="#cbd5e1" stroke-dasharray="3 3"/><text x="${X(0)}" y="${H - 6}" text-anchor="middle">t₀</text>` : '';
  return `<svg class="did-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Tok ishoda pre i posle događaja, studija ${idx + 1}">${grid}${t0}${xs[0] < 0 ? `<text x="${L}" y="${H - 6}">t${xs[0]}</text>` : ''}${xs[xs.length - 1] > 0 ? `<text x="${W - R}" y="${H - 6}" text-anchor="end">t+${xs[xs.length - 1]}</text>` : ''}${marks}</svg>`;
}
function renderTray() {
  $('trayTabs').innerHTML = Object.entries(TRAY).map(([k, v]) => `<button class="tray-tab ${k === state.trayTab ? 'active' : ''}" data-tray="${k}">${v[0]}</button>`).join('');
  $('tray').classList.toggle('expanded', !!state.trayTab);
  $('trayNote').textContent = `baza ${meta.schema_version} · izvoz ${meta.generated_at.slice(0, 10)}`;
  $('trayBody').innerHTML = state.trayTab ? TRAY[state.trayTab][1]() : '';
  if (state.trayTab === 'sim') renderSim();
}

// ── pretraga ───────────────────────────────────────────────────────────────
async function doSearch(q) {
  const box = $('searchResults'); q = norm(q.trim());
  if (q.length < 2) { box.classList.remove('open'); return; }
  const idx = await getJSON('search.json');
  if (!idx._n) { for (const z of idx.zones) z._n = norm(z.n); for (const d of idx.documents) d._n = norm(d.n); idx._n = true; }
  const zones = idx.zones.filter(z => z._n.includes(q)).sort((a, b) => (b.c === state.city) - (a.c === state.city)).slice(0, 8);
  const docs = idx.documents.filter(d => d._n.includes(q) && state.tiers.has(d.t)).slice(0, 8);
  const cn = id => boot.cities.find(c => c.city_id === id)?.city_name || '';
  box.innerHTML = (zones.length ? `<div class="sr-group-title">Zone i mesta</div>` + zones.map(z => `<div class="sr-item" data-zid="${z.id}" data-lat="${z.lat}" data-lon="${z.lon}" data-c="${esc(z.c || '')}"><span>${esc(z.n)}</span><small>${esc(cn(z.c))} · ${esc(z.fc)}</small></div>`).join('') : '') +
    (docs.length ? `<div class="sr-group-title">Dokumenti</div>` + docs.map(d => `<div class="sr-item" data-url="${safeUrl(d.u)}"><span>${badge(d.t)} ${esc(String(d.n).slice(0, 70))}</span><small>${esc(cn(d.c))}</small></div>`).join('') : '') ||
    '<div class="sr-item"><small>Nema rezultata.</small></div>';
  box.classList.add('open');
}

// ── događaji ───────────────────────────────────────────────────────────────
function bind() {
  document.addEventListener('click', e => {
    const t = e.target.closest('[data-city],[data-scale],[data-tier],[data-preset],[data-lens],[data-dtab],[data-tray],[data-zid],[data-url]');
    if (!e.target.closest('.search-wrap')) $('searchResults').classList.remove('open');
    if (!t) return;
    const ds = t.dataset;
    if (ds.zid) {
      $('searchResults').classList.remove('open');
      if (ds.c && ds.c !== state.city && boot.cities.some(c => c.city_id === ds.c)) { state.city = ds.c; renderTop(); syncLayers(); renderTray(); }
      map.flyTo({ center: [Number(ds.lon), Number(ds.lat)], zoom: 13, duration: 1000 });
      openDossier(Number(ds.zid), true);
    } else if ('url' in ds) { if (ds.url) window.open(ds.url, '_blank', 'noopener'); }
    else if (ds.city) setCity(ds.city);
    else if (ds.scale) setScale(ds.scale);
    else if (ds.tier) { const s = new Set(state.tiers); s.has(ds.tier) ? s.delete(ds.tier) : s.add(ds.tier); setTiers([...s]); }
    else if (ds.preset) setTiers(ds.preset.split(','));
    else if (ds.lens) { state.lens = LENSES.find(l => l.key === ds.lens); renderLenses(); computeBreaks().then(renderLegend); }
    else if (ds.dtab) { state.dTab = ds.dtab; renderDossier(); }
    else if (ds.tray) { state.trayTab = state.trayTab === ds.tray ? null : ds.tray; renderTray(); }
  });
  $('layerList').addEventListener('change', e => { const id = e.target.dataset.layer; if (!id) return; e.target.checked ? state.on.add(id) : state.on.delete(id); syncLayers(); });
  $('trayBody').addEventListener('input', e => { const k = e.target.dataset.sim; if (k) { sim[k] = Number(e.target.value); renderSim(); } });
  $('trayBody').addEventListener('click', e => { if (e.target.id === 'simReset') { for (const k in sim) sim[k] = 100; renderTray(); } });
  const tip = $('tip');
  $('trayBody').addEventListener('mousemove', e => {
    const h = e.target.closest('[data-tip]');
    if (!h) { tip.style.display = 'none'; return; }
    tip.textContent = h.dataset.tip; tip.style.display = 'block';
    tip.style.left = Math.min(window.innerWidth - tip.offsetWidth - 8, e.clientX + 12) + 'px'; tip.style.top = (e.clientY - 34) + 'px';
  });
  $('trayBody').addEventListener('mouseleave', () => { tip.style.display = 'none'; });
  $('btn2d').onclick = () => setMode(false); $('btn3d').onclick = () => setMode(true);
  $('btnLeft').onclick = () => $('btnLeft').classList.toggle('active', !document.body.classList.toggle('left-collapsed'));
  $('btnRight').onclick = () => $('btnRight').classList.toggle('active', !document.body.classList.toggle('right-collapsed'));
  $('dClose').onclick = () => { document.body.classList.add('right-collapsed'); $('btnRight').classList.remove('active'); };
  let st; $('search').addEventListener('input', e => { clearTimeout(st); st = setTimeout(() => doSearch(e.target.value), 180); });
  $('search').addEventListener('focus', e => doSearch(e.target.value));
  document.addEventListener('keydown', e => { if (e.key === 'Enter' && e.target.dataset?.tier) e.target.click(); if (e.key === 'Escape') $('searchResults').classList.remove('open'); });
}

// ── start ──────────────────────────────────────────────────────────────────
async function start() {
  try {
    [boot, meta] = await Promise.all([getJSON('bootstrap.json'), getJSON('meta.json')]);
  } catch (e) {
    $('dSub').textContent = 'Podaci nisu učitani: ' + e.message; document.body.classList.remove('right-collapsed'); return;
  }
  const order = meta.cities; boot.cities.sort((a, b) => order.indexOf(a.city_id) - order.indexOf(b.city_id));
  const hashCity = location.hash.slice(1); if (order.includes(hashCity)) state.city = hashCity;
  $('ver').textContent = String(meta.schema_version).replace(/-.*/, '');
  const c = boot.cities.find(x => x.city_id === state.city);
  map = new maplibregl.Map({
    container: 'map', center: [c.cbd_lon, c.cbd_lat], zoom: CITY_ZOOM[state.city], maxPitch: 70, attributionControl: { compact: true },
    style: { version: 8, sources: { base: { type: 'raster', tileSize: 256, maxzoom: 19, attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> saradnici · internet: Ookla® CC BY-NC-SA',
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'] } },
      layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#090d14' } }, { id: 'base', type: 'raster', source: 'base', paint: { 'raster-opacity': 0.55, 'raster-saturation': -0.85, 'raster-brightness-max': 0.55, 'raster-contrast': 0.1 } }] }
  });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'bottom-right');
  map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left');
  window.urbanLab = { map, state, bakery, layers: LAYERS, get boot() { return boot; }, get meta() { return meta; } }; // za proveru i konzolu
  renderTop(); renderTiers(); renderLenses(); renderLayerList(); renderTray(); bind();
  map.on('load', async () => {
    await computeBreaks(); await syncLayers();
    map.on('click', onClick);
    map.on('mousemove', e => { map.getCanvas().style.cursor = map.queryRenderedFeatures(e.point).some(f => f.source !== 'base') ? 'pointer' : ''; });
    openDossier(meta.city_core[state.city], false);
    document.body.dataset.ready = '1';
  });
}
start();
})();
