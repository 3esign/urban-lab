#!/usr/bin/env node
/**
 * Provera statičkog sajta u pravom pregledaču (headless Chrome preko CDP, bez zavisnosti).
 *   node urban_lab_app/tests/site_check.mjs [URL] [--shots DIR]
 * Podrazumevani URL je lokalni server; isti test radi i nad GitHub Pages adresom.
 */
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const argv = process.argv.slice(2);
const URL_ = argv.find(a => /^https?:/.test(a)) || 'http://127.0.0.1:8791/';
const SHOTS = argv.includes('--shots') ? argv[argv.indexOf('--shots') + 1] : null;
const CHROME = process.env.CHROME || ['C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', '/usr/bin/google-chrome', '/usr/bin/chromium'].find(p => fs.existsSync(p));
const PORT = 9333 + Math.floor(Math.random() * 500);
const prof = fs.mkdtempSync(path.join(path.resolve(SHOTS || os.tmpdir()), 'prof-'));
const sleep = ms => new Promise(r => setTimeout(r, ms));

const chrome = spawn(CHROME, ['--headless=new', '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--no-first-run', `--user-data-dir=${prof}`, `--remote-debugging-port=${PORT}`, '--window-size=1500,900', 'about:blank'], { stdio: 'ignore' });
const checks = []; const errors = []; const failed = [];
const ok = (name, pass, info = '') => { checks.push({ name, pass: !!pass, info: String(info) }); if (!pass) console.log('  PAD', name, info); };
let code = 1;
try {
  let target;
  for (let i = 0; i < 60 && !target; i++) { try { target = (await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()).find(t => t.type === 'page'); } catch { await sleep(300); } }
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let seq = 0; const waiters = new Map();
  ws.onmessage = m => {
    const d = JSON.parse(m.data);
    if (d.id && waiters.has(d.id)) { waiters.get(d.id)(d); waiters.delete(d.id); }
    else if (d.method === 'Runtime.exceptionThrown') errors.push(d.params.exceptionDetails.exception?.description || d.params.exceptionDetails.text);
    else if (d.method === 'Runtime.consoleAPICalled' && d.params.type === 'error') errors.push(d.params.args.map(a => a.value || a.description).join(' '));
    else if (d.method === 'Network.responseReceived' && d.params.response.status >= 400) failed.push(d.params.response.status + ' ' + d.params.response.url);
    else if (d.method === 'Network.loadingFailed' && !d.params.canceled) failed.push('FAIL ' + d.params.errorText);
  };
  const send = (method, params = {}) => new Promise(res => { const id = ++seq; waiters.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
  const ev = async expr => {
    const r = await send('Runtime.evaluate', { expression: `(async()=>{${expr}})()`, awaitPromise: true, returnByValue: true });
    if (r.result?.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description || 'eval');
    return r.result?.result?.value;
  };
  const shot = async name => { if (!SHOTS) return; const r = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(path.join(SHOTS, name + '.png'), Buffer.from(r.result.data, 'base64')); };
  await send('Runtime.enable'); await send('Network.enable'); await send('Page.enable');
  await send('Page.navigate', { url: URL_ });

  // čeka da nema učitavanja i da mapa miruje; vraća true/false kao vrednost izraza `settled`
  const wait = `let settled=false; { const L=()=>document.getElementById('loading').style.display!=='none'; const S=ms=>new Promise(r=>setTimeout(r,ms)); for(let i=0;i<300&&!settled;i++){ const u=window.urbanLab; if(document.body.dataset.ready && u && !L() && u.map.loaded() && !u.map.isMoving()) { await S(350); if(!L() && u.map.loaded() && !u.map.isMoving()) settled=true; } else await S(200); } }`;
  ok('sajt se učitao i mapa je spremna', await ev(`${wait} return settled;`));
  const cities = await ev(`return window.urbanLab.meta.cities`);
  ok('pet gradova u meta.json', cities?.length === 5, cities);

  for (const c of cities) {
    await ev(`document.querySelector('[data-city="${c}"]').click(); ${wait}`);
    const d = await ev(`const u=window.urbanLab; return { title: document.getElementById('dTitle').textContent, zc: u.state.dossier?.zone.city_id }`);
    ok(`${c}: dosije gradskog jezgra`, d.zc === c, JSON.stringify(d));
    for (const s of ['XS', 'S', 'M', 'L', 'XL']) {
      await ev(`document.querySelector('[data-scale="${s}"]').click(); ${wait}`);
      const r = await ev(`const u=window.urbanLab, out=[]; for(const l of u.layers){ const f=l.file(u.state.city); if(!u.state.on.has(l.id)||!f) continue; const exp=u.meta.layer_counts[u.state.city]?.[l.id]; const vis=u.map.getLayer(l.id)&&u.map.getLayoutProperty(l.id,'visibility')!=='none'; const rendered=u.map.queryRenderedFeatures({layers:[l.id]}).length; out.push({id:l.id, n:l._n, exp:exp??null, loaded:l._file===f, vis:!!vis, rendered}); } return out;`);
      for (const l of r) ok(`${c} ${s}: sloj ${l.id}`, l.loaded && l.vis && (l.exp == null || l.exp === l.n) && (l.n < 50 || l.rendered > 0), JSON.stringify(l)); // retki slojevi (zbirne tačke) ne moraju biti u kadru
      if (s === 'XS' || s === 'M') await shot(`${c}_${s}`);
    }
    await ev(`document.querySelector('[data-scale="M"]').click(); document.getElementById('btn2d').click(); ${wait}`);
  }

  // klik na zonu → popup i dosije te zone
  await ev(`document.querySelector('[data-city="sarajevo"]').click(); ${wait}`);
  const clicked = await ev(`const u=window.urbanLab; const c=u.map.getCenter(); for(let i=0;i<50 && !u.map.queryRenderedFeatures(u.map.project(c),{layers:['admin']}).length;i++) await new Promise(r=>setTimeout(r,200)); u.map.fire('click',{point:u.map.project(c),lngLat:c}); await new Promise(r=>setTimeout(r,1500)); return { title: document.getElementById('dTitle').textContent, open: !document.body.classList.contains('right-collapsed'), popup: !!document.querySelector('.maplibregl-popup'), fc: u.state.dossier.zone.feature_class, zoom: u.map.getZoom(), under: u.map.queryRenderedFeatures(u.map.project(c)).map(f=>f.layer.id+':'+f.properties.gazetteer_id).join(',') };`);
  ok('klik na mapu otvara popup i dosije zone', clicked.open && clicked.popup && clicked.fc !== 'city_core', JSON.stringify(clicked));
  for (const t of ['prostor', 'politika', 'dokazi', 'pregled']) {
    const len = await ev(`document.querySelector('[data-dtab="${t}"]').click(); return document.getElementById('dBody').textContent.length`);
    ok(`dosije: tabla ${t}`, len > 80, len);
  }
  await shot('sarajevo_dosije');

  // filter poverenja nad 3D zgradama
  await ev(`document.querySelector('[data-scale="XS"]').click(); ${wait}`);
  const tf = await ev(`const u=window.urbanLab, T=ms=>new Promise(r=>setTimeout(r,ms));
    const all=u.map.queryRenderedFeatures({layers:['buildings3d']}).length;
    document.querySelector('[data-preset="A1,A2"]').click(); await T(2000);
    const left=u.map.queryRenderedFeatures({layers:['buildings3d']}); const bad=left.filter(f=>!['A1','A2'].includes(f.properties.trust_tier)).length;
    const notice=!!document.querySelector('#dBody .notice-box'); document.querySelector('[data-preset="A1,A2,B,C,D"]').click(); await T(2000);
    return { all, left:left.length, bad, notice, back:u.map.queryRenderedFeatures({layers:['buildings3d']}).length };`);
  ok('filter poverenja skriva nivoe van izbora i vraća ih', tf.all > 0 && tf.bad === 0 && tf.left < tf.all && tf.back === tf.all && tf.notice, JSON.stringify(tf));
  await shot('sarajevo_XS_3d');

  // pretraga
  const sr = await ev(`const T=ms=>new Promise(r=>setTimeout(r,ms)); const i=document.getElementById('search'); i.value='centar'; i.dispatchEvent(new Event('input')); await T(2500); const n=document.querySelectorAll('#searchResults [data-zid]').length, dn=document.querySelectorAll('#searchResults [data-url]').length; const first=document.querySelector('#searchResults [data-zid]'); const name=first?.querySelector('span').textContent; first?.click(); await T(1500); return { zones:n, docs:dn, name, title:document.getElementById('dTitle').textContent };`);
  ok('pretraga vraća zone i otvara dosije izabrane', sr.zones > 0 && sr.name === sr.title, JSON.stringify(sr));

  // donja tabla
  const tr = await ev(`const u=window.urbanLab, out={}; document.querySelector('[data-tray="scorecard"]').click(); out.rows=document.querySelectorAll('.scorecard-table tbody tr').length;
    document.querySelector('[data-tray="sim"]').click(); out.base=u.boot.bakery_model.every(b=>u.bakery(b).loaves===b.breakeven_loaves_per_day); out.cards=document.querySelectorAll('.sim-city-card').length;
    const s=document.querySelector('[data-sim="flour"]'); s.value=150; s.dispatchEvent(new Event('input',{bubbles:true})); out.up=u.boot.bakery_model.every(b=>u.bakery(b).loaves>b.breakeven_loaves_per_day);
    document.querySelector('[data-tray="events"]').click(); out.studies=document.querySelectorAll('.did-card').length; out.charts=document.querySelectorAll('.did-chart polyline').length;
    document.querySelector('[data-tray="izvori"]').click(); out.src=document.getElementById('trayBody').textContent.includes('Ookla'); return out;`);
  ok('uporedna tabela ima pet redova', tr.rows === 5, tr.rows);
  ok('simulator na 100 % daje prag iz baze, skuplje brašno ga diže', tr.base && tr.up && tr.cards === 5, JSON.stringify(tr));
  ok('studije događaja imaju grafike', tr.studies > 0 && tr.charts >= tr.studies, JSON.stringify(tr));
  ok('tabla izvora navodi Ookla licencu', tr.src);
  await ev(`document.querySelector('[data-tray="events"]').click(); await new Promise(r=>setTimeout(r,500));`); await shot('studije');

  const realFailed = failed.filter(f => !/favicon/.test(f));
  ok('nema JS grešaka', errors.filter(e => !/favicon/.test(e)).length === 0, errors.slice(0, 5).join(' | '));
  ok('nema neuspelih mrežnih zahteva', realFailed.length === 0, [...new Set(realFailed)].slice(0, 8).join(' | '));
  ws.close();
  const pass = checks.filter(c => c.pass).length;
  console.log(`${URL_} → ${pass}/${checks.length} provera prošlo`);
  code = pass === checks.length ? 0 : 1;
} catch (e) { console.error('TEST PAO:', e.message); }
finally { chrome.kill(); await sleep(800); try { fs.rmSync(prof, { recursive: true, force: true }); } catch {} }
process.exit(code);
