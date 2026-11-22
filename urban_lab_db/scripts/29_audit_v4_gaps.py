from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(str(DB_DIR / "curated" / "urban_lab_5cities_v4.sqlite"))
con = sqlite3.connect(str(DB_PATH))
cur = con.cursor()

t0 = time.time()
print("=== DB PRAGMAS ===", flush=True)
jm = cur.execute("PRAGMA journal_mode").fetchone()[0]
pc = cur.execute("PRAGMA page_count").fetchone()[0]
ps = cur.execute("PRAGMA page_size").fetchone()[0]
print(f"journal_mode={jm} size_mb={pc*ps/1048576:.2f}", flush=True)

tables = [
    r[0]
    for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
]

print(f"\n=== TABLES (non-shadow) ===", flush=True)
empty_tables = []
for t in tables:
    if any(t.endswith(suf) for suf in ("_content", "_data", "_docsize", "_idx", "_config", "_node", "_parent", "_rowid")):
        continue
    cnt = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
    cols = [r[1] for r in cur.execute(f'PRAGMA table_info("{t}")').fetchall()]
    city_col = next((c for c in ("city_id", "city", "city_slug", "home_city_id", "primary_city_id") if c in cols), None)
    dist_str = ""
    if city_col and cnt > 0:
        rows = cur.execute(
            f'SELECT COALESCE(CAST("{city_col}" AS TEXT), "NULL"), COUNT(*) FROM "{t}" GROUP BY "{city_col}" ORDER BY COUNT(*) DESC LIMIT 6'
        ).fetchall()
        dist_str = " | " + ", ".join(f"{k}:{v}" for k, v in rows)
    print(f"{t:38s} {cnt:>9d}{dist_str}", flush=True)
    if cnt == 0:
        empty_tables.append(t)

print(f"\n=== EMPTY TABLES ({len(empty_tables)}) ===", flush=True)
print(", ".join(empty_tables), flush=True)

print("\n=== VIEWS (row count + ms) ===", flush=True)
for (v,) in cur.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name").fetchall():
    tv = time.time()
    try:
        cnt = cur.execute(f'SELECT COUNT(*) FROM "{v}"').fetchone()[0]
        print(f"  {v:42s} rows={cnt:<8d} ({(time.time()-tv)*1000:.1f} ms)", flush=True)
    except Exception as e:
        print(f"  {v:42s} ERROR: {e}", flush=True)

print("\n=== DOMAIN SIGNALS SENSORS ===", flush=True)
for r in cur.execute(
    "SELECT sensor_metric, city_id, COUNT(*), MIN(period_start), MAX(period_end), trust_tier FROM domain_signals_sensors GROUP BY sensor_metric, city_id, trust_tier ORDER BY sensor_metric, city_id"
).fetchall():
    print(" ", r, flush=True)

print("\n=== EVIDENCE DOCUMENTS ===", flush=True)
for r in cur.execute(
    "SELECT doc_type, trust_tier, COUNT(*) FROM evidence_documents GROUP BY doc_type, trust_tier ORDER BY COUNT(*) DESC"
).fetchall():
    print(" ", r, flush=True)

print("\n=== URBAN EVENTS & EVENT STUDIES ===", flush=True)
for r in cur.execute("SELECT event_id, city_id, event_category, primary_t0, corroborated_trust_tier FROM urban_events").fetchall():
    print("  EVT:", r, flush=True)
for r in cur.execute("SELECT study_id, event_id, outcome_metric, identification_grade FROM event_studies").fetchall():
    print("  STUDY:", r, flush=True)

print("\n=== ENTITIES & RELATIONS ===", flush=True)
for r in cur.execute("SELECT entity_type, country_iso3, COUNT(*) FROM entities GROUP BY entity_type, country_iso3 ORDER BY COUNT(*) DESC").fetchall():
    print("  ENT:", r, flush=True)
for r in cur.execute("SELECT relation_type, COUNT(*) FROM entity_relations GROUP BY relation_type").fetchall():
    print("  REL:", r, flush=True)

print("\n=== POLLING STATIONS GEO COVERAGE ===", flush=True)
for r in cur.execute(
    "SELECT city_id, election_id, COUNT(*), SUM(CASE WHEN lat IS NOT NULL THEN 1 ELSE 0 END) AS has_gps, SUM(CASE WHEN gazetteer_id IS NOT NULL THEN 1 ELSE 0 END) AS has_gaz, SUM(render_as_pin) AS pins FROM polling_stations GROUP BY city_id, election_id"
).fetchall():
    print("  PS:", r, flush=True)

print(f"\nDone in {time.time()-t0:.2f}s", flush=True)
con.close()
