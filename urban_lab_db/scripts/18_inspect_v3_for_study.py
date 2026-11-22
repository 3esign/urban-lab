from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import sqlite3
import os
import json
from pathlib import Path

BASE = Path(str(DB_DIR))
DB = BASE / "curated" / "urban_lab_5cities.sqlite"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
views = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")]

print("=== TABLES ===")
for t in tables:
    cnt = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
    cols = [c[1] for c in cur.execute(f'PRAGMA table_info("{t}")')]
    print(f"- {t} ({cnt} rows): {', '.join(cols)}")

print("\n=== VIEWS ===")
for v in views:
    try:
        cnt = cur.execute(f'SELECT COUNT(*) FROM "{v}"').fetchone()[0]
        cols = [c[1] for c in cur.execute(f'PRAGMA table_info("{v}")')]
        print(f"- {v} ({cnt} rows): {', '.join(cols)}")
    except Exception as e:
        print(f"- {v} (ERR: {e})")

print("\n=== CURATED FILES ===")
for sub in ["boundaries", "tables"]:
    p = BASE / "curated" / sub
    if p.exists():
        print(f"[{sub}]")
        for f in sorted(p.iterdir()):
            print(f"  {f.name} ({f.stat().st_size / 1024:.1f} KB)")
