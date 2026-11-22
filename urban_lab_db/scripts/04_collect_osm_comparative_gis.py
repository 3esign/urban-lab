import json
import math
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common_net import RAW_DIR, fetch_url

# Core urban bounding boxes (south, west, north, east) + CBD coordinates (lat, lon)
# Chosen to cover dense functional urban core + inner ring for comparable micro-economic density & bid-rent
CITIES_BBOX = {
    "beograd": {
        "name": "Beograd",
        "cbd": (44.8162, 20.4602),  # Trg Republike
        "bbox": (44.725, 20.340, 44.875, 20.555),
    },
    "zagreb": {
        "name": "Zagreb",
        "cbd": (45.8131, 15.9775),  # Trg bana Jelacica
        "bbox": (45.745, 15.860, 45.865, 16.085),
    },
    "sarajevo": {
        "name": "Sarajevo",
        "cbd": (43.8590, 18.4290),  # Bascarsija / Ferhadija
        "bbox": (43.805, 18.285, 43.895, 18.465),
    },
    "novi_pazar": {
        "name": "Novi Pazar",
        "cbd": (43.1367, 20.5122),  # Centar / Gradski trg
        "bbox": (43.095, 20.455, 43.175, 20.565),
    },
    "travnik": {
        "name": "Travnik",
        "cbd": (44.2264, 17.6658),  # Centar Travnika
        "bbox": (44.190, 17.600, 44.260, 17.730),
    },
}

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
]


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def classify_poi(tags: dict) -> tuple[str, str]:
    if "shop" in tags:
        return ("retail", tags["shop"])
    if "office" in tags:
        return ("office_business", tags["office"])
    if "craft" in tags:
        return ("craft_industry", tags["craft"])
    if tags.get("landuse") == "industrial" or tags.get("industrial"):
        return ("craft_industry", tags.get("industrial") or "industrial")
    am = tags.get("amenity", "")
    if am in ("restaurant", "cafe", "bar", "pub", "fast_food", "food_court"):
        return ("hospitality", am)
    if am in ("bank", "atm", "bureau_de_change"):
        return ("finance", am)
    if am in ("school", "university", "college", "kindergarten"):
        return ("education", am)
    if am in ("hospital", "clinic", "doctors", "pharmacy", "dentist"):
        return ("health", am)
    if am in ("townhall", "courthouse", "police", "post_office", "public_building"):
        return ("public_admin", am)
    if tags.get("tourism") in ("hotel", "hostel", "guest_house", "apartment", "museum"):
        return ("tourism", tags["tourism"])
    if tags.get("public_transport") == "station" or tags.get("railway") in ("station", "tram_stop") or tags.get("amenity") == "bus_station":
        return ("transit_hub", tags.get("railway") or tags.get("amenity") or "station")
    return ("other", am or "unknown")


def query_overpass(ql: str, city: str, dest: Path, layer: str, name: str):
    payload = urllib.parse.urlencode({"data": ql}).encode("utf-8")
    for ep in OVERPASS_ENDPOINTS:
        r = fetch_url(
            ep,
            dest=dest,
            city=city,
            layer=layer,
            source_name=name,
            timeout=90,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=payload,
            retries=1,
        )
        if r["ok"] and r.get("bytes", 0) > 100:
            try:
                obj = json.loads(r["_bytes"].decode("utf-8"))
                if "elements" in obj:
                    return obj
            except Exception:
                pass
        time.sleep(2)
    return None


def collect_city_pois():
    for cid, cfg in CITIES_BBOX.items():
        s, w, n, e = cfg["bbox"]
        # Query nodes & ways (center) for economic & urban centrality POIs
        ql = f"""[out:json][timeout:60];
(
  node["shop"]({s},{w},{n},{e});
  node["office"]({s},{w},{n},{e});
  node["craft"]({s},{w},{n},{e});
  node["amenity"~"^(restaurant|cafe|bar|pub|fast_food|bank|atm|school|university|college|hospital|clinic|pharmacy|townhall|courthouse|post_office|bus_station)$"]({s},{w},{n},{e});
  node["tourism"~"^(hotel|hostel|museum)$"]({s},{w},{n},{e});
  node["railway"~"^(station|tram_stop)$"]({s},{w},{n},{e});
  way["amenity"~"^(university|hospital|school|townhall|bus_station)$"]({s},{w},{n},{e});
);
out center tags;"""
        dest = RAW_DIR / cid / f"osm_economic_pois_{cid}.json"
        print(f"[OSM-POI] Fetching {cid} bbox=({s},{w},{n},{e})...")
        obj = query_overpass(ql, cid, dest, "osm_economic_pois", f"OSM Overpass Economic & Urban POIs ({cfg['name']})")
        if obj:
            els = obj.get("elements", [])
            print(f"  [OSM-POI] {cid}: {len(els)} elements saved")
        else:
            print(f"  [OSM-POI] {cid}: FAILED all endpoints")
        time.sleep(3)


if __name__ == "__main__":
    collect_city_pois()
