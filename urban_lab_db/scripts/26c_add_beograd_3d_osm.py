import json
import math
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_net import RAW_DIR, fetch_url

OUT_DIR = RAW_DIR / "wave4" / "xs_3d"
CONSOL = OUT_DIR / "xs_buildings_3d_5cities_consolidated.json"
FAST_OVERPASS = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"


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


def map_use(tags):
    b = (tags.get("building") or "").lower()
    am = (tags.get("amenity") or "").lower()
    if b in ("apartments", "residential", "dormitory"):
        return "residential_multi"
    if b in ("house", "detached", "semidetached_house"):
        return "residential_single"
    if b in ("commercial", "office") or tags.get("office"):
        return "commercial_office"
    if b in ("retail", "mall", "supermarket"):
        return "retail_mall"
    if b in ("industrial", "warehouse"):
        return "industrial_warehouse"
    if b in ("school", "university", "college") or am in ("school", "university"):
        return "public_education"
    if b in ("hospital", "clinic") or am in ("hospital", "clinic"):
        return "public_health"
    if b in ("public", "civic", "government"):
        return "public_admin"
    if b in ("church", "mosque", "cathedral") or am == "place_of_worship":
        return "cultural_religious"
    if b in ("hotel",):
        return "hospitality_hotel"
    return "unknown"


def extract_zg3d(path: Path, slug: str, qname: str, lim: int):
    d = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    feats = sorted(d.get("features") or [], key=lambda f: float((f.get("properties") or {}).get("Volume") or 0), reverse=True)
    out = []
    for f in feats[:lim]:
        p = f.get("properties") or {}
        g = f.get("geometry") or {}
        coords = g.get("coordinates")
        if not coords:
            continue
        pts = []
        if g.get("type") == "Polygon" and coords[0]:
            pts = [(c[0], c[1]) for c in coords[0] if len(c) >= 2]
        elif g.get("type") == "MultiPolygon" and coords[0] and coords[0][0]:
            pts = [(c[0], c[1]) for c in coords[0][0] if len(c) >= 2]
        if not pts:
            continue
        lons = [x[0] for x in pts]
        lats = [x[1] for x in pts]
        if not (15.0 <= sum(lons)/len(lons) <= 17.0 and 45.0 <= sum(lats)/len(lats) <= 46.5):
            continue
        h = parse_float(p.get("Z_Delta"))
        area = parse_float(p.get("SArea")) or ring_area_m2(pts)
        if not h or h < 2.0 or h > 300.0 or area < 10.0:
            continue
        oid = p.get("OBJECTID") or len(out) + 1
        out.append({
            "building_uid": f"bldg:zg3d:{slug}:{oid}",
            "city_id": "zagreb",
            "country_iso3": "HRV",
            "zone_hint": qname,
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
    return out


def parse_osm_elements(els, city_id, iso3, zhint, seen_uids):
    out = []
    for el in els:
        uid = f"bldg:osm:{city_id}:way_{el['id']}"
        if uid in seen_uids:
            continue
        pts = [(pt["lon"], pt["lat"]) for pt in (el.get("geometry") or []) if "lon" in pt and "lat" in pt]
        if len(pts) < 3:
            continue
        area = ring_area_m2(pts)
        if area < 15.0 or area > 250000.0:
            continue
        tags = el.get("tags") or {}
        h_exp = parse_float(tags.get("height"))
        lv_f = parse_float(tags.get("building:levels"))
        lv = int(round(lv_f)) if lv_f and 1 <= lv_f <= 100 else None
        if h_exp and 2.5 <= h_exp <= 350.0:
            hm, hsrc, tier = round(h_exp, 2), "osm_explicit_height", "B"
            if not lv:
                lv = max(1, int(round(hm / 3.2)))
        elif lv:
            hm, hsrc, tier = round(lv * 3.2, 2), "osm_levels_estimated", "C"
        else:
            continue
        lons = [p[0] for p in pts]
        lats = [p[1] for p in pts]
        seen_uids.add(uid)
        out.append({
            "building_uid": uid,
            "city_id": city_id,
            "country_iso3": iso3,
            "zone_hint": tags.get("addr:suburb") or zhint,
            "building_name": tags.get("name"),
            "address_text": " ".join(x for x in [tags.get("addr:street", ""), tags.get("addr:housenumber", "")] if x).strip() or None,
            "building_use": map_use(tags),
            "footprint_area_m2": round(area, 2),
            "height_m": hm,
            "ground_elevation_m": None,
            "floors_above_ground": lv,
            "height_source": hsrc,
            "trust_tier": tier,
            "centroid_lat": round(sum(lats) / len(lats), 6),
            "centroid_lon": round(sum(lons) / len(lons), 6),
            "min_lon": round(min(lons), 6),
            "max_lon": round(max(lons), 6),
            "min_lat": round(min(lats), 6),
            "max_lat": round(max(lats), 6),
            "source_id": "osm_3d_buildings",
        })
    return out


def main():
    all_b = []
    seen = set()

    # 1. Zagreb 3 LiDAR quarters (A1)
    for fp, slug, qname, lim in [
        (RAW_DIR / "zagreb" / "zg3d-gradska-cetvrt-donji-grad-2022_geojson.geojson", "donji_grad", "Donji grad", 2500),
        (OUT_DIR / "zg3d_trnje_2022.geojson", "trnje", "Trnje", 2000),
        (OUT_DIR / "zg3d_novi_zagreb_istok_2022.geojson", "novi_zagreb_istok", "Novi Zagreb - istok", 2000),
    ]:
        if fp.exists():
            recs = extract_zg3d(fp, slug, qname, lim)
            for r in recs:
                seen.add(r["building_uid"])
            all_b.extend(recs)
            print(f"+ ZG3D {qname:22s}: {len(recs)}", flush=True)

    # 2. Reuse already downloaded Sarajevo OSM 3D
    sa_p = OUT_DIR / "osm_3d_sarajevo.json"
    if sa_p.exists() and sa_p.stat().st_size > 1000:
        d = json.loads(sa_p.read_text(encoding="utf-8", errors="replace"))
        recs = parse_osm_elements(d.get("elements") or [], "sarajevo", "BIH", "Sarajevo Centar", seen)
        all_b.extend(recs)
        print(f"+ Sarajevo OSM 3D (cached): {len(recs)}", flush=True)

    # 3. Fast Overpass (maps.mail.ru only!) for Beograd, Novi Pazar, Travnik
    TARGETS = [
        ("beograd", "SRB", "bg_stari_grad", "Stari grad", (44.812, 20.452, 44.823, 20.468)),
        ("beograd", "SRB", "bg_nbg_usce", "Novi Beograd", (44.808, 20.422, 44.819, 20.440)),
        ("novi_pazar", "SRB", "np_core", "Novi Pazar Zona I-II", (43.128, 20.495, 43.152, 20.532)),
        ("travnik", "BIH", "tr_core", "Travnik Centar", (44.218, 17.640, 44.236, 17.685)),
    ]
    for cid, iso, slug, zhint, (s, w, n, e) in TARGETS:
        q = f'[out:json][timeout:25];(way["building"]["height"]({s},{w},{n},{e});way["building"]["building:levels"]({s},{w},{n},{e}););out body geom 1500;'
        r = fetch_url(
            FAST_OVERPASS,
            dest=OUT_DIR / f"osm_3d_{slug}.json",
            city=cid,
            layer="wave4_xs_3d_osm",
            source_name=f"osm_3d_{slug}",
            timeout=35,
            data=urllib.parse.urlencode({"data": q}).encode("utf-8"),
            retries=1,
        )
        if r["ok"]:
            d = json.loads(r.pop("_bytes", b"").decode("utf-8", errors="replace"))
            recs = parse_osm_elements(d.get("elements") or [], cid, iso, zhint, seen)
            all_b.extend(recs)
            print(f"+ {slug:16s}: raw={len(d.get('elements') or []):4d}, added={len(recs):4d}", flush=True)
        else:
            print(f"[FAIL] {slug}: {r.get('error')}", flush=True)

    CONSOL.write_text(json.dumps(all_b, ensure_ascii=False), encoding="utf-8")
    by_city = {}
    for x in all_b:
        by_city[x["city_id"]] = by_city.get(x["city_id"], 0) + 1
    print(f"\nDONE 5-City 3D Consolidated: total={len(all_b)} | by_city={by_city}", flush=True)


if __name__ == "__main__":
    main()
