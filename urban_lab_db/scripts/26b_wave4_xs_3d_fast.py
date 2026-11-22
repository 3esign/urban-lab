import json
import math
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_net import RAW_DIR, fetch_url

OUT_DIR = RAW_DIR / "wave4" / "xs_3d"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def ring_area_m2(coords):
    if len(coords) < 3:
        return 0.0
    lat0 = sum(c[1] for c in coords) / len(coords)
    kx = 111320.0 * math.cos(math.radians(lat0))
    ky = 110540.0
    area = 0.0
    for i in range(len(coords)):
        x1, y1 = coords[i][0] * kx, coords[i][1] * ky
        x2, y2 = coords[(i + 1) % len(coords)][0] * kx, coords[(i + 1) % len(coords)][1] * ky
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def parse_float(val):
    if val is None:
        return None
    s = str(val).strip().lower().replace("m", "").replace(",", ".").strip()
    try:
        v = float(s)
        return v if v > 0 else None
    except Exception:
        return None


def map_osm_building_use(tags: dict) -> str:
    b = (tags.get("building") or "").lower()
    am = (tags.get("amenity") or "").lower()
    sh = (tags.get("shop") or "").lower()
    if b in ("apartments", "residential", "dormitory"):
        return "residential_multi"
    if b in ("house", "detached", "semidetached_house", "terrace"):
        return "residential_single"
    if b in ("commercial", "office") or tags.get("office"):
        return "commercial_office"
    if b in ("retail", "supermarket", "mall") or sh:
        return "retail_mall"
    if b in ("industrial", "warehouse", "manufacture", "factory"):
        return "industrial_warehouse"
    if b in ("school", "university", "college", "kindergarten") or am in ("school", "university", "college"):
        return "public_education"
    if b in ("hospital", "clinic") or am in ("hospital", "clinic"):
        return "public_health"
    if b in ("public", "civic", "government", "townhall") or am in ("townhall", "courthouse", "police"):
        return "public_admin"
    if b in ("church", "mosque", "cathedral", "synagogue", "chapel") or am == "place_of_worship":
        return "cultural_religious"
    if b in ("hotel",) or tags.get("tourism") == "hotel":
        return "hospitality_hotel"
    if b == "construction":
        return "under_construction"
    if b == "ruins":
        return "ruin_vacant"
    return "unknown"


def extract_zg3d_geojson(path: Path, quarter_slug: str, quarter_name: str, limit: int = 2500):
    d = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    feats = d.get("features") or []
    def vol_key(f):
        try:
            return float((f.get("properties") or {}).get("Volume") or 0)
        except Exception:
            return 0.0
    feats_sorted = sorted(feats, key=vol_key, reverse=True)
    out = []
    for f in feats_sorted[:limit]:
        p = f.get("properties") or {}
        g = f.get("geometry") or {}
        gtype = g.get("type")
        coords = g.get("coordinates")
        if not coords:
            continue
        pts = []
        if gtype == "Polygon" and coords and coords[0]:
            pts = [(c[0], c[1]) for c in coords[0] if len(c) >= 2]
        elif gtype == "MultiPolygon" and coords and coords[0] and coords[0][0]:
            pts = [(c[0], c[1]) for c in coords[0][0] if len(c) >= 2]
        if not pts:
            continue
        lons = [x[0] for x in pts]
        lats = [x[1] for x in pts]
        if not (15.0 <= sum(lons)/len(lons) <= 17.0 and 45.0 <= sum(lats)/len(lats) <= 46.5):
            continue
        h = parse_float(p.get("Z_Delta"))
        area = parse_float(p.get("SArea"))
        if not h or h < 2.0 or h > 300.0:
            continue
        if not area or area < 10.0:
            area = ring_area_m2(pts)
        if area < 10.0:
            continue
        oid = p.get("OBJECTID") or len(out) + 1
        out.append({
            "building_uid": f"bldg:zg3d:{quarter_slug}:{oid}",
            "city_id": "zagreb",
            "country_iso3": "HRV",
            "zone_hint": quarter_name,
            "building_name": None,
            "address_text": None,
            "building_use": "unknown",
            "footprint_area_m2": round(area, 2),
            "height_m": round(h, 2),
            "ground_elevation_m": parse_float(p.get("Z_Min")),
            "floors_above_ground": max(1, int(round(h / 3.2))),
            "height_source": "lidar_3d_city_model",
            "trust_tier": "A1",
            "centroid_lat": round(sum(lats) / len(lats), 6),
            "centroid_lon": round(sum(lons) / len(lons), 6),
            "min_lon": round(min(lons), 6),
            "max_lon": round(max(lons), 6),
            "min_lat": round(min(lats), 6),
            "max_lat": round(max(lats), 6),
            "source_id": "zagreb_zg3d_lidar",
        })
    return len(feats), out


# Compact high-density CBD / core bboxes so Overpass responds in 3-8 seconds!
OSM_3D_CORES = [
    ("beograd", "SRB", "Stari grad + Savski venac + NBG Blokovi", (44.802, 20.435, 44.822, 20.472)),
    ("sarajevo", "BIH", "Centar + Stari Grad + Novo Sarajevo", (43.845, 18.380, 43.864, 18.436)),
    ("novi_pazar", "SRB", "Novi Pazar Zona I-II", (43.128, 20.495, 43.152, 20.532)),
    ("travnik", "BIH", "Travnik Centar + Kalibunar", (44.218, 17.640, 44.236, 17.685)),
]

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


def main():
    all_buildings = []

    print("=== 1. Parsing 3 Zagreb A1 LiDAR ZG3D quarters (already downloaded) ===", flush=True)
    zg_files = [
        (RAW_DIR / "zagreb" / "zg3d-gradska-cetvrt-donji-grad-2022_geojson.geojson", "donji_grad", "Donji grad", 2500),
        (OUT_DIR / "zg3d_trnje_2022.geojson", "trnje", "Trnje", 2000),
        (OUT_DIR / "zg3d_novi_zagreb_istok_2022.geojson", "novi_zagreb_istok", "Novi Zagreb - istok", 2000),
    ]
    for fp, slug, qname, lim in zg_files:
        if fp.exists():
            tot, recs = extract_zg3d_geojson(fp, slug, qname, limit=lim)
            all_buildings.extend(recs)
            print(f"  + ZG3D {qname:22s}: raw={tot:5d}, extracted={len(recs):4d}", flush=True)

    print("\n=== 2. Fetching OSM 3D Buildings (compact cores) for BG, SA, NP, TR ===", flush=True)
    for city_id, iso3, desc, (s, w, n, e) in OSM_3D_CORES:
        q = f'[out:json][timeout:22];(way["building"]["height"]({s},{w},{n},{e});way["building"]["building:levels"]({s},{w},{n},{e}););out body geom 2500;'
        raw_bytes = None
        for ov_url in OVERPASS_URLS:
            data_enc = urllib.parse.urlencode({"data": q}).encode("utf-8")
            r = fetch_url(
                ov_url,
                dest=OUT_DIR / f"osm_3d_{city_id}.json",
                city=city_id,
                layer="wave4_xs_3d_osm",
                source_name=f"osm_3d_{city_id}",
                timeout=30,
                data=data_enc,
                retries=0,
            )
            if r["ok"]:
                raw_bytes = r.pop("_bytes", b"")
                break
            print(f"    retry mirror for {city_id}: {ov_url} failed ({r.get('error')})", flush=True)
            time.sleep(1.0)
        if not raw_bytes:
            print(f"  [FAIL] OSM 3D {city_id}", flush=True)
            continue
        d = json.loads(raw_bytes.decode("utf-8", errors="replace"))
        els = d.get("elements") or []
        city_recs = []
        for el in els:
            geom = el.get("geometry") or []
            if len(geom) < 3:
                continue
            pts = [(pt["lon"], pt["lat"]) for pt in geom if "lon" in pt and "lat" in pt]
            if len(pts) < 3:
                continue
            area = ring_area_m2(pts)
            if area < 15.0 or area > 250000.0:
                continue
            tags = el.get("tags") or {}
            h_explicit = parse_float(tags.get("height"))
            lvls_f = parse_float(tags.get("building:levels"))
            lvls = int(round(lvls_f)) if lvls_f and 1 <= lvls_f <= 100 else None
            if h_explicit and 2.5 <= h_explicit <= 350.0:
                height_m = round(h_explicit, 2)
                h_src = "osm_explicit_height"
                tier = "B"
                if not lvls:
                    lvls = max(1, int(round(height_m / 3.2)))
            elif lvls:
                height_m = round(lvls * 3.2, 2)
                h_src = "osm_levels_estimated"
                tier = "C"
            else:
                continue
            lons = [p[0] for p in pts]
            lats = [p[1] for p in pts]
            addr = " ".join(x for x in [tags.get("addr:street", ""), tags.get("addr:housenumber", "")] if x).strip() or None
            city_recs.append({
                "building_uid": f"bldg:osm:{city_id}:way_{el['id']}",
                "city_id": city_id,
                "country_iso3": iso3,
                "zone_hint": tags.get("addr:suburb") or desc,
                "building_name": tags.get("name"),
                "address_text": addr,
                "building_use": map_osm_building_use(tags),
                "footprint_area_m2": round(area, 2),
                "height_m": height_m,
                "ground_elevation_m": None,
                "floors_above_ground": lvls,
                "height_source": h_src,
                "trust_tier": tier,
                "centroid_lat": round(sum(lats) / len(lats), 6),
                "centroid_lon": round(sum(lons) / len(lons), 6),
                "min_lon": round(min(lons), 6),
                "max_lon": round(max(lons), 6),
                "min_lat": round(min(lats), 6),
                "max_lat": round(max(lats), 6),
                "source_id": "osm_3d_buildings",
            })
        city_recs.sort(key=lambda x: x["footprint_area_m2"] * x["height_m"], reverse=True)
        all_buildings.extend(city_recs)
        print(f"  + OSM 3D {city_id:10s}: raw={len(els):4d}, valid={len(city_recs):4d}", flush=True)
        time.sleep(1.0)

    (OUT_DIR / "xs_buildings_3d_5cities_consolidated.json").write_text(
        json.dumps(all_buildings, ensure_ascii=False), encoding="utf-8"
    )
    by_city = {}
    for b in all_buildings:
        by_city[b["city_id"]] = by_city.get(b["city_id"], 0) + 1
    print(f"\nDONE XS 3D Fast: total={len(all_buildings)} | by_city={by_city}", flush=True)


if __name__ == "__main__":
    main()
