from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import json
import sys
from pathlib import Path
sys.path.insert(0, str(DB_DIR / "scripts"))
from common_net import RAW_DIR, fetch_url

zg3d = json.loads((RAW_DIR / "zagreb" / "ckan_search_zg3d.json").read_text(encoding="utf-8"))
for p in zg3d.get("result", {}).get("results", []):
    if p["name"] in ("o-d-matrica-putovanja", "zg3d-gradska-cetvrt-donji-grad-2022"):
        for res in p.get("resources", []):
            fmt = (res.get("format") or "").upper()
            url = res.get("url") or ""
            if p["name"] == "o-d-matrica-putovanja" or fmt in ("CSV", "GEOJSON"):
                fname = f"{p['name']}_{fmt.lower()}.{fmt.lower()}"
                r = fetch_url(url, dest=RAW_DIR / "zagreb" / fname, city="zagreb", layer=p["name"], source_name=f"Zagreb {p['title']} ({fmt})", timeout=60)
                print(f"[ZG-BONUS] {fname}: ok={r['ok']} bytes={r.get('bytes')} err={r.get('error')}")
