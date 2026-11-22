from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import json
from pathlib import Path
import pypdf

BASE = Path(str(DB_DIR / "raw"))

# 1. RS21x NUTS3 GDP
d = json.loads((BASE / "wave2_xl/eurostat_nama_10r_3gdp_rs21.json").read_text(encoding="utf-8"))
ids, sizes, dims = d["id"], d["size"], d["dimension"]
idx_maps = [(dim_id, {v: k for k, v in dims[dim_id]["category"]["index"].items()}, dims[dim_id]["category"].get("label", {})) for dim_id in ids]
by_gu = {}
for k_str, val in d.get("value", {}).items():
    k = int(k_str); coords = []
    for sz in reversed(sizes): coords.append(k % sz); k //= sz
    coords.reverse()
    rec = {"value": val}
    for (dim_id, inv, labels), c in zip(idx_maps, coords):
        code = inv[c]; rec[dim_id] = code; rec[dim_id+"_label"] = labels.get(code, code)
    if rec["unit"] in ("MIO_EUR", "EUR_HAB", "PPS_EU27_2020_HAB"):
        key = (rec["geo"], rec["unit"])
        if key not in by_gu or rec["time"] > by_gu[key]["time"]:
            by_gu[key] = rec
print("=== RS21x NUTS3 GDP (incl. RS217 Raska / Novi Pazar) ===")
for g in ["RS217", "RS211", "RS218", "RS214"]:
    m = by_gu.get((g, "MIO_EUR"), {}); e = by_gu.get((g, "EUR_HAB"), {}); p = by_gu.get((g, "PPS_EU27_2020_HAB"), {})
    print(f"  {g} {m.get('geo_label',''):24s} ({m.get('time')}) | {m.get('value')} M EUR | {e.get('value')} EUR/st | {p.get('value')} PPS/st")

# 2. KS p.23 forestry + ZPR KS GDP page
ks_pdf = pypdf.PdfReader(str(BASE / "sarajevo/fzs_kanton_sarajevo_2026.pdf"))
print("\n=== KS p.23 FORESTRY ===")
print((ks_pdf.pages[22].extract_text() or "")[:1200])

zpr_pdf = pypdf.PdfReader(str(BASE / "sarajevo/zpr_ks_izvjestaj_razvoj_2025.pdf"))
print("\n=== ZPR KS p.6 & p.14-18 GDP ===")
for p in [6, 15, 16, 17, 18]:
    txt = zpr_pdf.pages[p-1].extract_text() or ""
    for line in txt.splitlines():
        if any(k in line.lower() for k in ["bdp", "bruto domaći", "milijard", "per capita", "po stanovniku", "izvoz", "uvoz", "zaposlen"]):
            print(f"  p.{p}: {line.strip()[:120]}")
