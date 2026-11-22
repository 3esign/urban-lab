import json
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common_net import RAW_DIR, fetch_url

# Fast Overpass queries around CBD (overpass-api.de worked cleanly for Belgrade 5.08 MB!)
TARGETS = [
    ("travnik",    "Travnik",    44.2264, 17.6658, 3500),
    ("novi_pazar", "Novi Pazar", 43.1367, 20.5122, 4000),
    ("sarajevo",   "Sarajevo",   43.8590, 18.4290, 6500),
    ("zagreb",     "Zagreb",     45.8131, 15.9775, 5500),
]

EP = "https://overpass-api.de/api/interpreter"

for cid, cname, lat, lon, rad in TARGETS:
    dest = RAW_DIR / cid / f"osm_economic_pois_{cid}.json"
    if dest.exists() and dest.stat().st_size > 2000:
        print(f"[OSM-FAST] {cid}: already present ({dest.stat().st_size} B)", flush=True)
        continue
    ql = f"""[out:json][timeout:25];
(
  node["shop"](around:{rad},{lat},{lon});
  node["office"](around:{rad},{lat},{lon});
  node["craft"](around:{rad},{lat},{lon});
  node["amenity"~"^(restaurant|cafe|bar|fast_food|bank|atm|school|university|hospital|clinic|pharmacy|townhall|post_office|bus_station)$"](around:{rad},{lat},{lon});
  node["tourism"~"^(hotel|hostel|museum)$"](around:{rad},{lat},{lon});
  node["railway"~"^(station|tram_stop)$"](around:{rad},{lat},{lon});
);
out tags;"""
    payload = urllib.parse.urlencode({"data": ql}).encode("utf-8")
    r = fetch_url(
        EP, dest=dest, city=cid, layer="osm_economic_pois",
        source_name=f"OSM Overpass Economic POIs ({cname}, r={rad}m around CBD)",
        timeout=35, headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=payload, retries=1,
    )
    if r["ok"] and r.get("bytes", 0) > 200:
        obj = json.loads(r["_bytes"].decode("utf-8"))
        print(f"[OSM-FAST] {cid}: OK {len(obj.get('elements',[]))} POIs ({r['bytes']:,} B) in {r['elapsed_s']}s", flush=True)
    else:
        print(f"[OSM-FAST] {cid}: FAIL {r.get('error')}", flush=True)
    time.sleep(2.5)
