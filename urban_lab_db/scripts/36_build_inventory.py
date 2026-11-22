"""Urban Lab — inventar: tabele/pogledi zive v4.2 baze, poklapanje manifest.jsonl <-> raw/, masa po folderima.
Samo cita (baza se otvara read-only). Izlaz: docs/00_INVENTAR.md i curated/analysis/inventory.json"""
import json, os, sqlite3, sys, hashlib
from pathlib import Path
from datetime import datetime, timezone
BASE = Path(__file__).resolve().parent.parent
DB = BASE / "curated" / "urban_lab_5cities_v4.sqlite"
DB3 = BASE / "curated" / "urban_lab_5cities.sqlite"

def db_inv(p):
    con = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
    out = {"tables": [], "views": []}
    for name, typ in con.execute("select name,type from sqlite_master where type in ('table','view') and name not like 'sqlite_%' order by name"):
        try: n = con.execute(f'select count(*) from "{name}"').fetchone()[0]
        except Exception as e: n = f"ERR {e}"
        try: cols = [r[1] for r in con.execute(f'pragma table_info("{name}")')]
        except Exception as e: cols = []; n = f"ERR {e}"
        out["tables" if typ == "table" else "views"].append({"name": name, "rows": n, "cols": len(cols), "has_city": any(c in ("city", "city_id", "city_key", "city_slug") for c in cols)})
    con.close(); return out

def size(p): return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
def nfiles(p): return sum(1 for f in p.rglob("*") if f.is_file())

raw = BASE / "raw"
raw_files = {f.resolve() for f in raw.rglob("*") if f.is_file()}
man = []; bad = 0
for l in open(BASE / "manifest.jsonl", encoding="utf-8"):
    l = l.strip()
    if not l: continue
    try: man.append(json.loads(l))
    except Exception: bad += 1
man_paths = {}
for m in man:
    lp = m.get("local_path")
    if lp: man_paths.setdefault((BASE.parent / lp).resolve(), []).append(m)  # relativno na koren repozitorijuma
missing = sorted(p.relative_to(BASE).as_posix() for p in man_paths if not p.exists())
orphans = sorted(str(p.relative_to(BASE)) for p in raw_files - set(man_paths))
inv = {
    "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "v4": db_inv(DB), "v3": db_inv(DB3),
    "manifest": {"rows": len(man), "bad_lines": bad, "ok_true": sum(1 for m in man if m.get("ok")), "ok_false": sum(1 for m in man if m.get("ok") is False),
                 "with_local_path": sum(1 for m in man if m.get("local_path")), "distinct_paths": len(man_paths),
                 "paths_missing_on_disk": missing, "raw_files": len(raw_files), "raw_not_in_manifest": orphans},
    "mass": {d.name: {"bytes": size(d), "files": nfiles(d)} for d in sorted(raw.iterdir()) if d.is_dir()},
    "curated": {d.name: {"bytes": size(d), "files": nfiles(d)} for d in sorted((BASE / "curated").iterdir()) if d.is_dir()},
}
(BASE / "curated" / "analysis" / "inventory.json").write_text(json.dumps(inv, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: inv[k] for k in ("manifest",)}, ensure_ascii=False)[:3000])
print("v4 tables", len(inv["v4"]["tables"]), "views", len(inv["v4"]["views"]), "| v3 tables", len(inv["v3"]["tables"]), "views", len(inv["v3"]["views"]))
for t in inv["v4"]["tables"]: print(f'  T {t["name"]:48} {t["rows"]}')
for t in inv["v4"]["views"]: print(f'  V {t["name"]:48} {t["rows"]}')

# ---------- Markdown: docs/00_INVENTAR.md i scripts/INDEX.md ----------
import re
def mb(b): return f"{b/1e6:.1f} MB"
L = ["# Urban Lab — inventar (generisano)", "", f"Generisano: {inv['generated']} · skripta `scripts/36_build_inventory.py` (samo čita). Ne uređuje se ručno.", "",
     "## Baze", "", "| Baza | Tabele | Pogledi | Neispravno |", "|---|---|---|---|"]
for k, f in (("v4", DB), ("v3", DB3)):
    br = [t["name"] for t in inv[k]["tables"] + inv[k]["views"] if isinstance(t["rows"], str)]
    L.append(f"| `curated/{f.name}` ({mb(f.stat().st_size)}) | {len(inv[k]['tables'])} | {len(inv[k]['views'])} | {', '.join(br) or '—'} |")
aux = re.compile(r"_(rtree|fts)(_|$)|_fts$|_rtree$")
L += ["", "## Živa baza v4.2 — tabele sa podacima", "", "Pomoćne FTS/R-tree tabele su izostavljene.", "", "| Tabela | Redova | Kolona |", "|---|---:|---:|"]
L += [f"| `{t['name']}` | {t['rows']} | {t['cols']} |" for t in inv["v4"]["tables"] if not aux.search(t["name"])]
L += ["", "## Živa baza v4.2 — pogledi", "", "| Pogled | Redova |", "|---|---:|"]
L += [f"| `{t['name']}` | {t['rows']} |" for t in inv["v4"]["views"]]
m = inv["manifest"]
L += ["", "## Sirovi fajlovi (`raw/`)", "", "| Folder | Fajlova | Masa |", "|---|---:|---:|"]
L += [f"| `raw/{k}` | {v['files']} | {mb(v['bytes'])} |" for k, v in inv["mass"].items()]
L += ["", "## Manifest ↔ disk", "",
      f"- Redova u `manifest.jsonl`: {m['rows']} (uspešnih {m['ok_true']}, neuspešnih {m['ok_false']}); različitih lokalnih putanja: {m['distinct_paths']}.",
      f"- Putanja iz manifesta kojih nema na disku: {len(m['paths_missing_on_disk'])}.",
      f"- Fajlova u `raw/`: {m['raw_files']}; od toga bez reda u manifestu: {len(m['raw_not_in_manifest'])}.", "", "### Fajlovi u `raw/` bez reda u manifestu", ""]
L += [f"- `{p.replace(os.sep, '/')}`" for p in m["raw_not_in_manifest"]]
(BASE / "docs").mkdir(exist_ok=True)
(BASE / "docs" / "00_INVENTAR.md").write_text("\n".join(L) + "\n", encoding="utf-8")

WAVES = [(1, 6, "Talas 1 — osnovne baze 5 gradova → baza v1"), (7, 11, "Talas 2 — makro (XL), zaleđe (L), lanci snabdevanja (S) → baza v2"),
         (12, 17, "Talas 3 — APR Srbija, Popis poljoprivrede 2023, poreske zone, landuse → baza v3"), (18, 20, "Analitička studija nad v3"),
         (21, 28, "Talas 4 — nauka, nabavke, vesti, senzori, izbori, 3D zgrade → baza v4.1"), (29, 35, "Talas 5 — TED, CORDIS, Ookla, tranzit → baza v4.2"), (36, 99, "Održavanje")]
def kind(n):
    if re.search(r"probe|inspect|discover|check|audit|read_", n): return "sonda"
    if re.search(r"build_urban|upgrade_db|load_|bootstrap", n): return "gradnja baze"
    if re.search(r"verify|analytics|charts|inventory", n): return "analiza"
    if re.search(r"parse|extract|digitize", n): return "obrada"
    return "sakupljanje"
S = ["# Skripte — indeks (generisano)", "", "Generiše `36_build_inventory.py`. Skripte ostaju u jednom folderu: uvoze `common_net.py` iz istog foldera i većina ima apsolutnu putanju do `urban_lab_db`.",
     "Vrsta je izvedena iz imena fajla. Slovo iza broja (b, c, d…) znači popravku ili nastavak istog koraka; koja varijanta je dala konačan fajl nije ovde utvrđeno.", ""]
files = sorted(f.name for f in (BASE / "scripts").glob("*.py"))
for lo, hi, title in WAVES:
    rows = [f for f in files if re.match(r"\d+", f) and lo <= int(re.match(r"\d+", f).group()) <= hi]
    if not rows: continue
    S += [f"## {title}", "", "| Skripta | Vrsta |", "|---|---|"] + [f"| `{f}` | {kind(f)} |" for f in rows] + [""]
S += ["## Zajedničko", "", "- `common_net.py` — mrežni sloj i upis u `manifest.jsonl`; uvoze ga ostale skripte.", ""]
(BASE / "scripts" / "INDEX.md").write_text("\n".join(S), encoding="utf-8")
print("MD OK")
