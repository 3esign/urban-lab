import json
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common_net import RAW_DIR, fetch_url

REMAINING = {
    "zagreb":     ("Zagreb",     (45.755, 15.880, 45.855, 16.065)),
    "sarajevo":   ("Sarajevo",   (43.805, 18.285, 43.895, 18.465)),
    "novi_pazar": ("Novi Pazar", (43.095, 20.455, 43.175, 20.565)),
    "travnik":    ("Travnik",    (44.190, 17.600, 44.260, 17.730)),
}

ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

for cid, (cname, (s, w, n, e)) in REMAINING.items():
    dest = RAW_DIR / cid / f"osm_economic_pois_{cid}.json"
    if dest.exists() and dest.stat().st_size > 2000:
        print(f"[OSM-REM] {cid} already exists ({dest.stat().st_size} B)")
        continue
    ql = f"""[out:json][timeout:35];
(
  node["shop"]({s},{w},{n},{e});
  node["office"]({s},{w},{n},{e});
  node["craft"]({s},{w},{n},{e});
  node["amenity"~"^(restaurant|cafe|bar|pub|fast_food|bank|atm|school|university|college|hospital|clinic|pharmacy|townhall|courthouse|post_office|bus_station)$"]({s},{w},{n},{e});
  node["tourism"~"^(hotel|hostel|museum)$"]({s},{w},{n},{e});
  node["railway"~"^(station|tram_stop)$"]({s},{w},{n},{e});
);
out tags;"""
    payload = urllib.parse.urlencode({"data": ql}).encode("utf-8")
    ok = False
    for ep in ENDPOINTS:
        r = fetch_url(
            ep, dest=dest, city=cid, layer="osm_economic_pois",
            source_name=f"OSM Overpass Economic & Urban POIs ({cname})",
            timeout=45, headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=payload, retries=0,
        )
        if r["ok"] and r.get("bytes", 0) > 200:
            try:
                obj = json.loads(r["_bytes"].decode("utf-8"))
                if "elements" in obj:
                    print(f"[OSM-REM] {cid} OK via {ep.split('/')[2]}: {len(obj['elements'])} elements ({r['bytes']} B)")
                    ok = True
                    break
            except Exception:
                pass
        print(f"[OSM-REM] {cid} fail on {ep.split('/')[2]}: {r.get('error')}")
        time.sleep(1.5)
    if not ok:
        print(f"[OSM-REM] {cid} ALL ENDPOINTS FAILED")
    time.sleep(2)
