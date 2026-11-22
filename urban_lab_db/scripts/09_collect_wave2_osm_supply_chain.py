from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import os, sys, json, time, urllib.request, urllib.parse, hashlib

BASE = str(DB_DIR)
OUT = os.path.join(BASE, "raw", "wave2_osm")
os.makedirs(OUT, exist_ok=True)
MANIFEST = os.path.join(BASE, "manifest.jsonl")

ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

# Tight city cores for comparative urban POI density + S-scale bakery & supply-chain ecosystems
CITIES = {
    "travnik":    {"lat": 44.2264, "lon": 17.6658, "r_core": 6000,  "r_supply": 25000},
    "novi_pazar": {"lat": 43.1367, "lon": 20.5122, "r_core": 8000,  "r_supply": 30000},
    "sarajevo":   {"lat": 43.8563, "lon": 18.4131, "r_core": 12000, "r_supply": 35000},
    "zagreb":     {"lat": 45.8130, "lon": 15.9772, "r_core": 12000, "r_supply": 35000},
    "beograd":    {"lat": 44.8125, "lon": 20.4612, "r_core": 12000, "r_supply": 40000},
}

def query_overpass(ql, out_path, city_id, desc):
    if os.path.exists(out_path) and os.path.getsize(out_path) > 200:
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if "elements" in d and len(d["elements"]) > 0:
                print(f"  [CACHED] {os.path.basename(out_path)}: {len(d['elements'])} elements")
                return len(d["elements"])
        except Exception:
            pass

    data = urllib.parse.urlencode({"data": ql}).encode("utf-8")
    for ep in ENDPOINTS:
        try:
            req = urllib.request.Request(
                ep, data=data,
                headers={"User-Agent": "SvemirUrbanLab/2.0 (research)", "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=55) as resp:
                raw = resp.read()
                if len(raw) > 50 and raw.lstrip().startswith(b"{"):
                    parsed = json.loads(raw.decode("utf-8", errors="replace"))
                    elems = parsed.get("elements", [])
                    with open(out_path, "wb") as f:
                        f.write(raw)
                    rec = {
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "city": city_id,
                        "desc": desc,
                        "url": ep,
                        "path": os.path.relpath(out_path, BASE),
                        "status": resp.status,
                        "ok": True,
                        "bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "elements": len(elems),
                    }
                    with open(MANIFEST, "a", encoding="utf-8") as mf:
                        mf.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    print(f"  [OK] {os.path.basename(out_path):42s} | {len(elems):>6} elems | {len(raw):>9,} B | via {ep.split('/')[2]}")
                    return len(elems)
        except Exception as e:
            print(f"  [RETRY] {os.path.basename(out_path)} on {ep.split('/')[2]}: {str(e)[:80]}")
            time.sleep(2.5)
    print(f"  [FAIL] {os.path.basename(out_path)}")
    return -1

# PART 1: Missing comparative core economic POIs for the 4 cities (Travnik, Novi Pazar, Sarajevo, Zagreb)
print("=== PART 1: CORE ECONOMIC POIS (4 MISSING CITIES) ===", flush=True)
for cid in ["travnik", "novi_pazar", "sarajevo", "zagreb"]:
    c = CITIES[cid]
    lat, lon, r = c["lat"], c["lon"], c["r_core"]
    ql = f"""[out:json][timeout:45];
(
  nwr["shop"~"^(bakery|supermarket|convenience|clothes|butcher|hardware|furniture|mall|department_store)$"](around:{r},{lat},{lon});
  nwr["amenity"~"^(cafe|restaurant|fast_food|bank|pharmacy|marketplace|fuel|school|university|hospital|clinic|bus_station)$"](around:{r},{lat},{lon});
  nwr["office"](around:{r},{lat},{lon});
  nwr["industrial"](around:{r},{lat},{lon});
  nwr["craft"](around:{r},{lat},{lon});
  nwr["tourism"~"^(hotel|hostel|guest_house|attraction|museum)$"](around:{r},{lat},{lon});
);
out center qt;"""
    query_overpass(ql, os.path.join(OUT, f"osm_core_pois_{cid}.json"), cid, f"OSM core economic POIs ({cid}, r={r}m)")
    time.sleep(3.0)

# PART 2: S-to-L Bakery & Local Supply-Chain Ecosystem for ALL 5 CITIES (bakeries, mills, sawmills/wood, markets, farms, industrial/rail hubs)
print("\n=== PART 2: S->L SUPPLY CHAIN ECOSYSTEM (ALL 5 CITIES) ===", flush=True)
for cid in ["travnik", "novi_pazar", "sarajevo", "zagreb", "beograd"]:
    c = CITIES[cid]
    lat, lon, r = c["lat"], c["lon"], c["r_supply"]
    ql = f"""[out:json][timeout:45];
(
  nwr["shop"="bakery"](around:{r},{lat},{lon});
  nwr["craft"~"^(bakery|miller|sawmill|carpenter)$"](around:{r},{lat},{lon});
  nwr["industrial"~"^(mill|sawmill|timber|bakery|food|agriculture|warehouse|logistics)$"](around:{r},{lat},{lon});
  nwr["man_made"~"^(silo|windmill|watermill)$"](around:{r},{lat},{lon});
  nwr["amenity"="marketplace"](around:{r},{lat},{lon});
  nwr["shop"~"^(farm|greengrocer|agrarian|timber|fuel|trade)$"](around:{r},{lat},{lon});
  nwr["railway"="station"](around:{r},{lat},{lon});
);
out center qt;"""
    query_overpass(ql, os.path.join(OUT, f"osm_supply_chain_{cid}.json"), cid, f"OSM S->L bakery/mill/timber/market supply chain ({cid}, r={r}m)")
    time.sleep(3.0)

print("DONE 09_collect_wave2_osm_supply_chain.py", flush=True)
