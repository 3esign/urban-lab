import csv
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

# 1. Zagreb additional A1 LiDAR ZG3D quarters (CSV+GeoJSON from data.zagreb.hr)
# We already have Donji Grad in raw/zagreb/. Let's also fetch Trnje (business/modernist) and Novi Zagreb istok (socialist high-rise)
ZG3D_EXTRA = [
    (
        "trnje",
        "Trnje",
        "https://data.zagreb.hr/dataset/0e2a16af-c993-477c-93fb-3d9a7114d064/resource/b3127fd7-f447-47b9-8e23-7420e4c57e2b/download/zg3d_gc_trnje_2022_2264678255288625683.csv",
        "https://data.zagreb.hr/dataset/0e2a16af-c993-477c-93fb-3d9a7114d064/resource/eb87e912-df5c-4f71-8920-f8b63ef08999/download/zg3d_gc_trnje_2022_-5402852497803139915.geojson",
    ),
    (
        "novi_zagreb_istok",
        "Novi Zagreb - istok",
        "https://data.zagreb.hr/dataset/456a13c7-c888-48d7-bf8f-7a77eb4fd99e/resource/b2845745-afd6-4272-a31a-5e5906bed6e2/download/zg3d_gc_novi_zagreb_istok_2022_-6846733335818527028.csv",
        "https://data.zagreb.hr/dataset/456a13c7-c888-48d7-bf8f-7a77eb4fd99e/resource/035c6bf5-8975-4290-9faf-148db8f3bbf1/download/zg3d_gc_novi_zagreb_istok_2022_-3108577300901486921.geojson",
    ),
]

# 2. Urban core bounding boxes for OSM 3D buildings (south, west, north, east)
OSM_3D_CORES = [
    ("beograd", "SRB", "Beograd centar + Novi Beograd blokovi", (44.795, 20.410, 44.828, 20.485)),
    ("sarajevo", "BIH", "Sarajevo Centar + Stari Grad + Novo Sarajevo + Ilidza", (43.822, 18.300, 43.868, 18.445)),
    ("novi_pazar", "SRB", "Novi Pazar urbano jezgro (Zona I-III)", (43.120, 20.485, 43.160, 20.545)),
    ("travnik", "BIH", "Travnik urbano jezgro + Kalibunar", (44.215, 17.630, 44.240, 17.695)),
]

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def ring_area_m2(coords):
    """Shoelace area in m^2 from [(lon, lat), ...] using local equirectangular projection."""
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


def extract_zg3d_geojson(path: Path, quarter_slug: str, quarter_name: str, limit: int = 3500):
    """Extract compact normalized 3D building records from ZG3D GeoJSON (handles both 2D/3D Polygon/MultiPolygon)."""
    d = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    feats = d.get("features") or []
    out = []
    # Sort by Volume descending so we capture all major buildings if capped, or all if <= limit
    def vol_key(f):
        try:
            return float((f.get("properties") or {}).get("Volume") or 0)
        except Exception:
            return 0.0

    feats_sorted = sorted(feats, key=vol_key, reverse=True)
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
        # Check if coordinates look like WGS84 (Zagreb lon ~15.8-16.2, lat ~45.7-45.9)
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
            "building_use": "unknown",
            "footprint_area_m2": round(area, 2),
            "height_m": round(h, 2),
            "ground_elevation_m": parse_float(p.get("Z_Min")),
            "floors_above_ground": max(1, int(round(h / 3.2))),
            "height_source": "lidar_3d_city_model",
            "trust_tier": "A1",
            "year_survey": p.get("Godina_izv"),
            "centroid_lat": round(sum(lats) / len(lats), 6),
            "centroid_lon": round(sum(lons) / len(lons), 6),
            "min_lon": round(min(lons), 6),
            "max_lon": round(max(lons), 6),
            "min_lat": round(min(lats), 6),
            "max_lat": round(max(lats), 6),
            "source_id": "zagreb_zg3d_lidar",
        })
    return len(feats), out


def main():
    all_buildings = []

    print("=== 1. Processing Zagreb A1 LiDAR ZG3D (Donji Grad + Trnje + Novi Zagreb istok) ===")
    dg_path = RAW_DIR / "zagreb" / "zg3d-gradska-cetvrt-donji-grad-2022_geojson.geojson"
    if dg_path.exists():
        tot, recs = extract_zg3d_geojson(dg_path, "donji_grad", "Donji grad", limit=3000)
        all_buildings.extend(recs)
        print(f"  + ZG3D Donji grad: raw={tot}, extracted={len(recs)}")

    for qslug, qname, csv_url, geo_url in ZG3D_EXTRA:
        dest_geo = OUT_DIR / f"zg3d_{qslug}_2022.geojson"
        r = fetch_url(geo_url, dest=dest_geo, city="zagreb", layer="wave4_xs_3d_zg", source_name=f"zg3d_{qslug}", timeout=60, retries=2)
        if r["ok"]:
            tot, recs = extract_zg3d_geojson(dest_geo, qslug, qname, limit=2500)
            all_buildings.extend(recs)
            print(f"  + ZG3D {qname}: raw={tot}, extracted={len(recs)}")
        else:
            print(f"  [FAIL] ZG3D {qname}: {r.get('error')}")
        time.sleep(0.5)

    print("\n=== 2. Fetching OSM 3D Buildings (height / building:levels) for BG, SA, NP, TR ===")
    for city_id, iso3, desc, (s, w, n, e) in OSM_3D_CORES:
        # Query ways with building tag AND (height OR building:levels) to get real 3D massing
        q = f"""
[out:json][timeout:45];
(
  way["building"]["height"]({s},{w},{n},{e});
  way["building"]["building:levels"]({s},{w},{n},{e});
);
out body geom;
"""
        raw_bytes = None
        for ov_url in OVERPASS_URLS:
            data_enc = urllib.parse.urlencode({"data": q}).encode("utf-8")
            r = fetch_url(
                ov_url,
                dest=OUT_DIR / f"osm_3d_{city_id}.json",
                city=city_id,
                layer="wave4_xs_3d_osm",
                source_name=f"osm_3d_{city_id}",
                timeout=60,
                data=data_enc,
                retries=1,
            )
            if r["ok"]:
                raw_bytes = r.pop("_bytes", b"")
                break
            time.sleep(2.0)

        if not raw_bytes:
            print(f"  [FAIL] OSM 3D {city_id}")
            continue

        try:
            d = json.loads(raw_bytes.decode("utf-8", errors="replace"))
        except Exception as ex:
            print(f"  [JSON ERR] OSM 3D {city_id}: {ex}")
            continue

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
                tier = "C"  # Strict v4.1 CHECK compliance!
            else:
                continue

            lons = [p[0] for p in pts]
            lats = [p[1] for p in pts]
            b_name = tags.get("name") or tags.get("addr:housename")
            addr_parts = [tags.get("addr:street", ""), tags.get("addr:housenumber", "")]
            addr = " ".join(x for x in addr_parts if x).strip() or None
            city_recs.append({
                "building_uid": f"bldg:osm:{city_id}:way_{el['id']}",
                "city_id": city_id,
                "country_iso3": iso3,
                "zone_hint": tags.get("addr:suburb") or tags.get("addr:city") or desc,
                "building_name": b_name,
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

        # Keep up to 3500 largest/tallest buildings per city so DB stays fast and rich
        city_recs.sort(key=lambda x: x["footprint_area_m2"] * x["height_m"], reverse=True)
        kept = city_recs[:3500]
        all_buildings.extend(kept)
        print(f"  + OSM 3D {city_id:10s}: raw_ways={len(els)}, valid={len(city_recs)}, kept={len(kept)}")
        time.sleep(1.5)

    (OUT_DIR / "xs_buildings_3d_5cities_consolidated.json").write_text(
        json.dumps(all_buildings, ensure_ascii=False), encoding="utf-8"
    )
    by_city = {}
    for b in all_buildings:
        by_city[b["city_id"]] = by_city.get(b["city_id"], 0) + 1
    print(f"\nDONE XS 3D Buildings: total={len(all_buildings)} | by_city={by_city}")


if __name__ == "__main__":
    main()
