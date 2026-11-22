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


data = json.loads(CONSOL.read_text(encoding="utf-8")) if CONSOL.exists() else []
seen = {x["building_uid"] for x in data}
counts = {}
for x in data:
    counts[x["city_id"]] = counts.get(x["city_id"], 0) + 1
print("Before patch:", counts, flush=True)

PATCH_TARGETS = [
    ("novi_pazar", "SRB", "Novi Pazar Zona I", (43.133, 20.506, 43.145, 20.524)),
    ("travnik", "BIH", "Travnik Centar", (44.221, 17.652, 44.232, 17.676)),
]

for cid, iso, zhint, (s, w, n, e) in PATCH_TARGETS:
    if counts.get(cid, 0) >= 50:
        continue
    q = f'[out:json][timeout:18];(way["building"]["height"]({s},{w},{n},{e});way["building"]["building:levels"]({s},{w},{n},{e}););out body geom 800;'
    r = fetch_url(
        FAST_OVERPASS,
        dest=OUT_DIR / f"osm_3d_{cid}_cbd.json",
        city=cid,
        layer="wave4_xs_3d_osm",
        source_name=f"osm_3d_{cid}_cbd",
        timeout=25,
        data=urllib.parse.urlencode({"data": q}).encode("utf-8"),
        retries=1,
    )
    if not r["ok"]:
        # Fallback: take ALL buildings in tiny core and estimate 2 floors if no levels tag? No, keep honest — only tagged!
        print(f"  [WARN] {cid} Overpass failed: {r.get('error')}", flush=True)
        continue
    els = json.loads(r.pop("_bytes", b"").decode("utf-8", errors="replace")).get("elements") or []
    added = 0
    for el in els:
        uid = f"bldg:osm:{cid}:way_{el['id']}"
        if uid in seen:
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
        seen.add(uid)
        data.append({
            "building_uid": uid,
            "city_id": cid,
            "country_iso3": iso,
            "zone_hint": zhint,
            "building_name": tags.get("name"),
            "address_text": " ".join(x for x in [tags.get("addr:street", ""), tags.get("addr:housenumber", "")] if x).strip() or None,
            "building_use": "unknown",
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
        added += 1
    print(f"  + {cid}: raw={len(els)}, added={added}", flush=True)

CONSOL.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
counts2 = {}
for x in data:
    counts2[x["city_id"]] = counts2.get(x["city_id"], 0) + 1
print("After patch:", counts2, "total=", len(data), flush=True)
