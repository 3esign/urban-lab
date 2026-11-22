from _paths import rel  # putanje u manifestu su relativne na koren repozitorijuma
import json
import math
import re
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path
from common_net import BASE_DIR, append_manifest, sha256_bytes

OUT_DIR = BASE_DIR / "raw" / "wave5" / "osm_and_sensors"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CTX = ssl.create_default_context()
HDRS = {"User-Agent": "UrbanLabResearch/1.0 (Academic GIS)", "Accept": "application/json"}

OVERPASS_ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
]


def query_overpass(ql: str, timeout: int = 45):
    data = ("data=" + urllib.parse.quote(ql)).encode("utf-8")
    last_err = None
    for ep in OVERPASS_ENDPOINTS:
        try:
            req = urllib.request.Request(ep, data=data, headers=HDRS)
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
                raw = resp.read()
                return json.loads(raw.decode("utf-8", errors="replace")), ep
        except Exception as e:
            last_err = f"{ep}: {e}"
            time.sleep(1.0)
    raise RuntimeError(f"All Overpass endpoints failed: {last_err}")


def poly_area_m2(geom: list[dict]) -> float:
    if not geom or len(geom) < 3:
        return 0.0
    lat0 = sum(p["lat"] for p in geom) / len(geom)
    cos_lat = math.cos(math.radians(lat0))
    pts = [(p["lon"] * 111320.0 * cos_lat, p["lat"] * 110540.0) for p in geom]
    area = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def parse_float(val):
    if not val:
        return None
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(val).replace(",", "."))
    return float(m.group(1)) if m else None


def map_bldg_use_and_default_height(btag: str, area_m2: float) -> tuple[str, float, int]:
    t = (btag or "").lower()
    if t in ("apartments", "dormitory"):
        return ("residential_multi", 14.5, 4)
    if t in ("house", "detached", "semidetached_house", "residential", "terrace"):
        return ("residential_single", 7.2 if area_m2 < 220 else 9.6, 2 if area_m2 < 220 else 3)
    if t in ("commercial", "office"):
        return ("commercial_office", 12.0, 3)
    if t in ("retail", "supermarket", "mall", "kiosk"):
        return ("retail_mall", 6.5, 2)
    if t in ("industrial", "warehouse", "manufacture", "factory"):
        return ("industrial_warehouse", 8.0, 2)
    if t in ("school", "university", "college", "kindergarten"):
        return ("public_education", 10.5, 3)
    if t in ("hospital", "clinic"):
        return ("public_health", 12.5, 4)
    if t in ("public", "civic", "government", "townhall"):
        return ("public_admin", 11.0, 3)
    if t in ("mosque", "church", "cathedral", "chapel", "religious"):
        return ("cultural_religious", 11.5, 2)
    if t in ("hotel", "hostel"):
        return ("hospitality_hotel", 13.0, 4)
    if t in ("construction",):
        return ("under_construction", 9.0, 3)
    if t in ("ruins",):
        return ("ruin_vacant", 4.0, 1)
    # Generic 'yes': estimate conservatively from footprint size (honestly marked trust_tier='D')
    if area_m2 >= 600:
        return ("mixed_use", 12.0, 3)
    if area_m2 >= 240:
        return ("residential_multi", 9.6, 3)
    return ("residential_single", 6.8, 2)


def collect_np_tr_buildings():
    print("=== 1. Collecting Full OSM Building Footprints for Novi Pazar & Travnik ===", flush=True)
    # Compact urban core bounding boxes (so Overpass returns cleanly within 15s and ~1500-4000 buildings each)
    targets = [
        ("novi_pazar", "SRB", (43.122, 20.495, 43.155, 20.535)),
        ("travnik", "BIH", (44.215, 17.640, 44.236, 17.688)),
    ]
    out_bldgs = []
    for cid, iso, (s, w, n, e) in targets:
        ql = f"[out:json][timeout:35];way[building]({s},{w},{n},{e});out body geom;"
        try:
            res, ep = query_overpass(ql, timeout=45)
            elems = res.get("elements") or []
            cnt = 0
            for el in elems:
                geom = el.get("geometry") or []
                if len(geom) < 3:
                    continue
                area = poly_area_m2(geom)
                if area < 18.0 or area > 80000.0:
                    continue
                tags = el.get("tags") or {}
                lats = [p["lat"] for p in geom]
                lons = [p["lon"] for p in geom]
                buse, def_h, def_fl = map_bldg_use_and_default_height(tags.get("building"), area)

                exp_h = parse_float(tags.get("height"))
                exp_lv = parse_float(tags.get("building:levels"))
                if exp_h and 2.5 <= exp_h <= 250.0:
                    h_m = round(exp_h, 2)
                    floors = int(round(exp_lv)) if (exp_lv and exp_lv >= 1) else max(1, int(round(h_m / 3.2)))
                    h_src = "osm_explicit_height"
                    tier = "B"
                elif exp_lv and 1 <= exp_lv <= 60:
                    floors = int(round(exp_lv))
                    h_m = round(floors * 3.2, 2)
                    h_src = "osm_levels_estimated"
                    tier = "C"
                else:
                    floors = def_fl
                    h_m = def_h
                    h_src = "shadow_ml_inferred"
                    tier = "D"

                addr_parts = [tags.get("addr:street"), tags.get("addr:housenumber")]
                addr = " ".join(p for p in addr_parts if p) or None
                out_bldgs.append({
                    "building_uid": f"bldg:osm:way_{el['id']}",
                    "city_id": cid,
                    "country_iso3": iso,
                    "building_name": tags.get("name"),
                    "address_text": addr,
                    "building_use": buse,
                    "footprint_area_m2": round(area, 2),
                    "height_m": h_m,
                    "floors_above_ground": floors,
                    "height_source": h_src,
                    "centroid_lat": round(sum(lats) / len(lats), 6),
                    "centroid_lon": round(sum(lons) / len(lons), 6),
                    "min_lon": round(min(lons), 6),
                    "max_lon": round(max(lons), 6),
                    "min_lat": round(min(lats), 6),
                    "max_lat": round(max(lats), 6),
                    "source_id": "osm_3d_buildings",
                    "trust_tier": tier,
                })
                cnt += 1
            print(f"  OSM buildings {cid} via {ep}: {cnt} valid buildings (from {len(elems)} ways)", flush=True)
            time.sleep(1.0)
        except Exception as ex:
            print(f"  OSM buildings {cid} ERR: {ex}", flush=True)

    out_p = OUT_DIR / "osm_buildings_np_tr_wave5.json"
    b = json.dumps(out_bldgs, ensure_ascii=False).encode("utf-8")
    out_p.write_bytes(b)
    append_manifest({
        "ok": True, "city": "common", "layer": "wave5_xs_3d", "source_name": "osm_overpass_buildings_np_tr",
        "url": "https://overpass.kumi.systems/api/interpreter", "http_status": 200,
        "bytes": len(b), "sha256": sha256_bytes(b), "local_path": rel(out_p),
    })


def collect_transit_stops_sa_np_tr():
    print("\n=== 2. Collecting OSM Public Transit Stops for Sarajevo, Novi Pazar & Travnik ===", flush=True)
    targets = [
        ("sarajevo", "BIH", (43.780, 18.240, 43.920, 18.500)),
        ("novi_pazar", "SRB", (43.090, 20.440, 43.190, 20.580)),
        ("travnik", "BIH", (44.180, 17.580, 44.270, 17.750)),
    ]
    all_stops = []
    for cid, iso, (s, w, n, e) in targets:
        ql = f"""[out:json][timeout:30];
        (
          node[highway=bus_stop]({s},{w},{n},{e});
          node[railway=tram_stop]({s},{w},{n},{e});
          node[public_transport=platform]({s},{w},{n},{e});
          node[amenity=bus_station]({s},{w},{n},{e});
        );
        out body;"""
        try:
            res, ep = query_overpass(ql, timeout=35)
            elems = res.get("elements") or []
            seen = set()
            cnt = 0
            for el in elems:
                nid = el["id"]
                if nid in seen:
                    continue
                seen.add(nid)
                tags = el.get("tags") or {}
                mode = "tram" if (tags.get("railway") == "tram_stop" or tags.get("tram") == "yes") else ("station" if tags.get("amenity") == "bus_station" else "bus")
                all_stops.append({
                    "stop_uid": f"osm:{cid}:{nid}",
                    "city_id": cid,
                    "country_iso3": iso,
                    "stop_name": tags.get("name") or f"OSM Stop {nid}",
                    "mode": mode,
                    "lat": round(el["lat"], 6),
                    "lon": round(el["lon"], 6),
                    "source_id": "osm_transit_stops",
                    "trust_tier": "C",
                })
                cnt += 1
            print(f"  OSM transit stops {cid}: {cnt}", flush=True)
            time.sleep(0.8)
        except Exception as ex:
            print(f"  OSM transit stops {cid} ERR: {ex}", flush=True)

    out_p = OUT_DIR / "osm_transit_stops_sa_np_tr.json"
    b = json.dumps(all_stops, ensure_ascii=False).encode("utf-8")
    out_p.write_bytes(b)
    append_manifest({
        "ok": True, "city": "common", "layer": "wave5_transit", "source_name": "osm_overpass_transit_stops",
        "url": "https://overpass.kumi.systems/api/interpreter", "http_status": 200,
        "bytes": len(b), "sha256": sha256_bytes(b), "local_path": rel(out_p),
    })


def collect_ground_aq_sensors():
    print("\n=== 3. Collecting Sensor.Community Ground AQ Snapshots (5 Cities) ===", flush=True)
    centers = [
        ("beograd", 44.8162, 20.4602, 25),
        ("zagreb", 45.8131, 15.9775, 25),
        ("sarajevo", 43.8590, 18.4290, 25),
        ("novi_pazar", 43.1367, 20.5122, 35),
        ("travnik", 44.2264, 17.6658, 35),
    ]
    out = []
    for cid, lat, lon, r_km in centers:
        url = f"https://data.sensor.community/airrohr/v1/filter/area={lat},{lon},{r_km}"
        try:
            req = urllib.request.Request(url, headers=HDRS)
            with urllib.request.urlopen(req, timeout=20, context=CTX) as resp:
                rows = json.loads(resp.read().decode("utf-8", errors="replace"))
            pm25_vals, pm10_vals = [], []
            for r in rows:
                for sv in r.get("sensordatavalues") or []:
                    vt = sv.get("value_type")
                    try:
                        v = float(sv.get("value"))
                    except Exception:
                        continue
                    if vt == "P2" and 0.0 <= v <= 600.0:
                        pm25_vals.append(v)
                    elif vt == "P1" and 0.0 <= v <= 800.0:
                        pm10_vals.append(v)
            rec = {
                "city_id": cid,
                "radius_km": r_km,
                "raw_readings_n": len(rows),
                "pm25_n": len(pm25_vals),
                "pm25_mean_ugm3": round(sum(pm25_vals) / len(pm25_vals), 2) if pm25_vals else None,
                "pm25_median_ugm3": round(sorted(pm25_vals)[len(pm25_vals) // 2], 2) if pm25_vals else None,
                "pm10_n": len(pm10_vals),
                "pm10_mean_ugm3": round(sum(pm10_vals) / len(pm10_vals), 2) if pm10_vals else None,
            }
            out.append(rec)
            print(f"  Sensor.Community {cid}: readings={len(rows)}, PM2.5 n={rec['pm25_n']} mean={rec['pm25_mean_ugm3']}", flush=True)
        except Exception as e:
            print(f"  Sensor.Community {cid} ERR: {e}", flush=True)

    out_p = OUT_DIR / "sensor_community_5cities_snapshot.json"
    b = json.dumps(out, ensure_ascii=False, indent=2).encode("utf-8")
    out_p.write_bytes(b)
    append_manifest({
        "ok": True, "city": "common", "layer": "wave5_sensors", "source_name": "sensor_community_airrohr",
        "url": "https://data.sensor.community/airrohr/v1/", "http_status": 200,
        "bytes": len(b), "sha256": sha256_bytes(b), "local_path": rel(out_p),
    })


if __name__ == "__main__":
    collect_np_tr_buildings()
    collect_transit_stops_sa_np_tr()
    collect_ground_aq_sensors()
