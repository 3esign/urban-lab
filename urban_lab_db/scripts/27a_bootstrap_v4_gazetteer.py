from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import ast
import json
import math
import re
import shutil
import sqlite3
import sys
import unicodedata
from pathlib import Path

BASE_DIR = Path(str(DB_DIR))
V3_DB = BASE_DIR / "curated" / "urban_lab_5cities.sqlite"
V4_DB = BASE_DIR / "curated" / "urban_lab_5cities_v4.sqlite"
MIGRATION_SQL = BASE_DIR / "schema_v4" / "migration_v4.sql"

CYR_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ђ": "dj", "е": "e", "ж": "z",
    "з": "z", "и": "i", "ј": "j", "к": "k", "л": "l", "љ": "lj", "м": "m", "н": "n",
    "њ": "nj", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "ћ": "c", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "c", "џ": "dz", "ш": "s",
    "А": "a", "Б": "b", "В": "v", "Г": "g", "Д": "d", "Ђ": "dj", "Е": "e", "Ж": "z",
    "З": "z", "И": "i", "Ј": "j", "К": "k", "Л": "l", "Љ": "lj", "М": "m", "Н": "n",
    "Њ": "nj", "О": "o", "П": "p", "Р": "r", "С": "s", "Т": "t", "Ћ": "c", "У": "u",
    "Ф": "f", "Х": "h", "Ц": "c", "Ч": "c", "Џ": "dz", "Ш": "s",
}

CITY_ISO = {
    "beograd": "SRB",
    "zagreb": "HRV",
    "sarajevo": "BIH",
    "novi_pazar": "SRB",
    "travnik": "BIH",
}

CITY_CBD = {
    "beograd": (44.8125, 20.4612),
    "zagreb": (45.8131, 15.9775),
    "sarajevo": (43.8563, 18.4131),
    "novi_pazar": (43.1367, 20.5122),
    "travnik": (44.2264, 17.6658),
}


def norm_balkan(text: str) -> str:
    if not text:
        return ""
    s = "".join(CYR_MAP.get(ch, ch) for ch in text)
    s = s.replace("đ", "dj").replace("Đ", "dj")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-zA-Z0-9\s\-]", " ", s).lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def clean_unit_name(raw_name: str) -> str:
    """Fix v3 Zagreb local_board bug where unit_name is a dict string {'JMS_IME': '...'}."""
    if not raw_name:
        return ""
    s = str(raw_name).strip()
    if s.startswith("{") and "JMS_IME" in s:
        try:
            obj = ast.literal_eval(s)
            if isinstance(obj, dict) and obj.get("JMS_IME"):
                return str(obj["JMS_IME"]).strip()
        except Exception:
            m = re.search(r"['\"]JMS_IME['\"]\s*:\s*['\"]([^'\"]+)['\"]", s)
            if m:
                return m.group(1).strip()
    return s


def generate_balkan_inflections(name: str) -> list[tuple[str, str]]:
    """Generate canonical + Balkan case inflections (locative/genitive/instrumental) for NLP->GIS."""
    out = []
    n = norm_balkan(name)
    if not n or len(n) < 3:
        return out
    out.append((name, "canonical"))

    # English exonyms for core cities
    exonyms = {
        "beograd": [("Belgrade", "english_exonym"), ("Београд", "cyrillic"), ("Beogradu", "inflected_stem"), ("Beograda", "inflected_stem")],
        "zagreb": [("Zagrebu", "inflected_stem"), ("Zagreba", "inflected_stem")],
        "sarajevo": [("Sarajevu", "inflected_stem"), ("Sarajeva", "inflected_stem")],
        "novi pazar": [("Novom Pazaru", "inflected_stem"), ("Novog Pazara", "inflected_stem"), ("Нови Пазар", "cyrillic")],
        "travnik": [("Travniku", "inflected_stem"), ("Travnika", "inflected_stem")],
    }
    if n in exonyms:
        out.extend(exonyms[n])

    # Morphological inflections for single/two-word Balkan toponyms
    parts = n.split()
    last = parts[-1]
    prefix = " ".join(parts[:-1])
    pfx = (prefix + " ") if prefix else ""
    if len(last) >= 4:
        if last.endswith("a"):
            stem = last[:-1]
            for suf in ("i", "e", "u", "om"):
                out.append((pfx + stem + suf, "inflected_stem"))
        elif last.endswith("vac") or last.endswith("nac") or last.endswith("rac"):
            stem = last[:-2] + "c"
            for suf in ("u", "a"):
                out.append((pfx + stem + suf, "inflected_stem"))
        elif last.endswith("o"):
            stem = last[:-1]
            for suf in ("u", "a"):
                out.append((pfx + stem + suf, "inflected_stem"))
        elif last[-1] in "bcdfghjklmnprstvz":
            for suf in ("u", "a"):
                out.append((pfx + last + suf, "inflected_stem"))

    # Strip trailing "sarajevo" or "grad" colloquial aliases to enable context disambiguation
    if n.endswith(" sarajevo") and len(parts) >= 2:
        short = n[: -len(" sarajevo")].strip()
        if len(short) >= 4:
            out.append((short, "colloquial_local"))
    return out


def make_bbox(lat: float, lon: float, area_km2: float | None, default_rad_km: float = 0.5):
    if area_km2 and area_km2 > 0:
        rad_km = max(0.05, math.sqrt(area_km2 / math.pi))
    else:
        rad_km = default_rad_km
    dlat = rad_km / 111.0
    dlon = rad_km / max(20.0, 111.32 * math.cos(math.radians(lat)))
    return (
        round(lon - dlon, 6),
        round(lon + dlon, 6),
        round(lat - dlat, 6),
        round(lat + dlat, 6),
    )


def main():
    assert V3_DB.exists(), f"Missing v3 DB: {V3_DB}"
    assert MIGRATION_SQL.exists(), f"Missing migration SQL: {MIGRATION_SQL}"

    # 1. Copy untouched v3 DB to v4 DB
    if V4_DB.exists():
        V4_DB.unlink()
    shutil.copy2(V3_DB, V4_DB)
    print(f"Copied v3 -> v4 DB: {V4_DB.name} ({V4_DB.stat().st_size:,} bytes)")

    conn = sqlite3.connect(str(V4_DB))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    # 2. Apply v4.1 DDL migration
    sql_text = MIGRATION_SQL.read_text(encoding="utf-8")
    conn.executescript(sql_text)
    conn.execute("PRAGMA foreign_keys = ON;")
    print("Applied migration_v4.sql cleanly.")

    # 3. Bootstrap spatial_gazetteer from all 8 v3 anchor tables
    cur = conn.cursor()
    inserted_places = 0
    inserted_aliases = 0
    city_gaz_ids = {}

    def add_place(
        canonical_key, city_id, iso3, scale, fclass, name, parent_id,
        v3_table, v3_pk, lat, lon, area_km2, unc_m, dist_cbd, ring, weight, geo_ref, tier="A1"
    ):
        nonlocal inserted_places, inserted_aliases
        if lat is None or lon is None:
            return None
        lat, lon = float(lat), float(lon)
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        norm = norm_balkan(name)
        if not norm:
            return None
        min_lon, max_lon, min_lat, max_lat = make_bbox(lat, lon, area_km2, default_rad_km=max(0.1, unc_m / 1000.0))
        cur.execute(
            """
            INSERT OR IGNORE INTO spatial_gazetteer (
                canonical_key, city_id, country_iso3, scale_level, feature_class,
                canonical_name, normalized_name, parent_gazetteer_id,
                v3_source_table, v3_source_pk,
                centroid_lat, centroid_lon, min_lon, max_lon, min_lat, max_lat,
                area_km2, spatial_uncertainty_m, dist_cbd_km, ring, disambiguation_weight, geojson_ref, trust_tier
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                canonical_key, city_id, iso3, scale, fclass,
                name, norm, parent_id,
                v3_table, str(v3_pk),
                lat, lon, min_lon, max_lon, min_lat, max_lat,
                area_km2, unc_m, dist_cbd, ring, weight, geo_ref, tier
            ),
        )
        row = cur.execute("SELECT gazetteer_id FROM spatial_gazetteer WHERE canonical_key = ?", (canonical_key,)).fetchone()
        if not row:
            return None
        gid = row[0]
        inserted_places += 1
        for alias_txt, alias_type in generate_balkan_inflections(name):
            anorm = norm_balkan(alias_txt)
            if not anorm or len(anorm) < 3:
                continue
            cur.execute(
                """
                INSERT OR IGNORE INTO gazetteer_aliases
                (gazetteer_id, alias_text, normalized_alias, alias_type, city_hint, is_ambiguous)
                VALUES (?,?,?,?,?,0)
                """,
                (gid, alias_txt, anorm, alias_type, city_id),
            )
            if cur.rowcount > 0:
                inserted_aliases += 1
        return gid

    # 3a. cities (5)
    for r in conn.execute("SELECT * FROM cities").fetchall():
        gid = add_place(
            f"city:{r['city_id']}", r["city_id"], r["country_iso3"], "M", "city_core",
            r["name"], None, "cities", r["city_id"],
            r["cbd_lat"], r["cbd_lon"], r["area_km2"], 8000.0, 0.0, "core", 10.0,
            f"all_5cities_admin_units.geojson#{r['city_id']}", "A1"
        )
        city_gaz_ids[r["city_id"]] = gid

    # 3b. admin_units (362 — fixing ZG JMS_IME bug!)
    fixed_zg_jms = 0
    for r in conn.execute("SELECT * FROM admin_units").fetchall():
        raw_nm = r["unit_name"]
        clean_nm = clean_unit_name(raw_nm)
        if clean_nm != str(raw_nm or "").strip():
            fixed_zg_jms += 1
        lvl = (r["admin_level"] or "").lower()
        if "local_board" in lvl or "mjesni" in lvl:
            fclass, scale, unc = "mjesni_odbor", "S", 500.0
        elif "district" in lvl or "cetvrt" in lvl:
            fclass, scale, unc = "district_cetvrt", "M", 1500.0
        elif "naselje" in lvl or "settlement" in lvl:
            fclass, scale, unc = "settlement_naselje", "S", 800.0
        else:
            fclass, scale, unc = "municipality", "M", 2000.0
        lat = r["centroid_lat"] if r["centroid_lat"] is not None else CITY_CBD[r["city_id"]][0]
        lon = r["centroid_lon"] if r["centroid_lon"] is not None else CITY_CBD[r["city_id"]][1]
        add_place(
            f"admin:{r['city_id']}:{r['id']}", r["city_id"], CITY_ISO[r["city_id"]], scale, fclass,
            clean_nm, city_gaz_ids.get(r["city_id"]), "admin_units", r["id"],
            lat, lon, r["area_km2"], unc, r["dist_cbd_km"], None,
            min(8.0, 1.0 + math.log10(max(10.0, float(r["population"] or 100.0)))),
            f"all_5cities_admin_units.geojson#{r['id']}", "A1"
        )

    # 3c. hinterland_units (36 — join centroids from GeoJSON if available)
    h_centroids = {}
    h_geo = BASE_DIR / "curated" / "boundaries" / "all_5cities_hinterland_l.geojson"
    if h_geo.exists():
        gj = json.loads(h_geo.read_text(encoding="utf-8", errors="replace"))
        for feat in gj.get("features") or []:
            pr = feat.get("properties") or {}
            uid = pr.get("unit_id") or pr.get("name") or pr.get("unit_name")
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates")
            pts = []
            if geom.get("type") == "Polygon" and coords:
                pts = coords[0]
            elif geom.get("type") == "MultiPolygon" and coords and coords[0]:
                pts = coords[0][0]
            if uid and pts:
                h_centroids[str(uid)] = (sum(p[1] for p in pts)/len(pts), sum(p[0] for p in pts)/len(pts))
                if pr.get("unit_name"):
                    h_centroids[norm_balkan(pr["unit_name"])] = h_centroids[str(uid)]

    for r in conn.execute("SELECT * FROM hinterland_units").fetchall():
        hub = r["city_hub"]
        latlon = h_centroids.get(str(r["unit_id"])) or h_centroids.get(norm_balkan(r["unit_name"])) or CITY_CBD.get(hub, (44.0, 18.0))
        iso = r["country_iso"] if r["country_iso"] in ("SRB", "HRV", "BIH") else CITY_ISO.get(hub, "INT")
        add_place(
            f"hinterland:{r['unit_id']}", hub if hub in CITY_ISO else None, iso, "L", "hinterland_unit",
            r["unit_name"], city_gaz_ids.get(hub), "hinterland_units", r["unit_id"],
            latlon[0], latlon[1], 120.0, 5000.0, r["dist_cbd_km"], r["ring_role"], 3.0,
            f"all_5cities_hinterland_l.geojson#{r['unit_id']}", "A2"
        )

    # 3d. property_tax_zones_gis_summary (21 — BG 14 + NP 7)
    tz_centroids = {}
    for cid, fname in [("beograd", "beograd_poreske_zone_2026.geojson"), ("novi_pazar", "novi_pazar_poreske_zone_2026.geojson")]:
        fp = BASE_DIR / "curated" / "boundaries" / fname
        if fp.exists():
            gj = json.loads(fp.read_text(encoding="utf-8", errors="replace"))
            for feat in gj.get("features") or []:
                pr = feat.get("properties") or {}
                zn = pr.get("zone_name") or pr.get("zona") or pr.get("name")
                geom = feat.get("geometry") or {}
                coords = geom.get("coordinates")
                pts = []
                if geom.get("type") == "Polygon" and coords:
                    pts = coords[0]
                elif geom.get("type") == "MultiPolygon" and coords and coords[0]:
                    pts = coords[0][0]
                if zn and pts:
                    tz_centroids[(cid, norm_balkan(zn))] = (sum(p[1] for p in pts)/len(pts), sum(p[0] for p in pts)/len(pts))

    for r in conn.execute("SELECT * FROM property_tax_zones_gis_summary").fetchall():
        cid = r["city_id"]
        latlon = tz_centroids.get((cid, norm_balkan(r["zone_name"]))) or CITY_CBD[cid]
        add_place(
            f"taxzone:{cid}:{norm_balkan(r['zone_name']).replace(' ', '_')}", cid, CITY_ISO[cid], "S", "tax_zone",
            f"{r['zone_name']} ({cid})", city_gaz_ids.get(cid), "property_tax_zones_gis_summary", f"{cid}:{r['zone_name']}",
            latlon[0], latlon[1], r["total_area_km2"], 600.0, None, f"rank_{r['zone_rank']}", 4.0,
            r["geojson_file"], "A1"
        )

    # 3e. osm_landuse_major_zones (named zones — ~359)
    for r in conn.execute("SELECT * FROM osm_landuse_major_zones WHERE name IS NOT NULL AND trim(name) != ''").fetchall():
        fc = "industrial_zone" if (r["fclass"] or "") == "industrial" else ("commercial_zone" if (r["fclass"] or "") in ("commercial", "retail") else "landuse_polygon")
        add_place(
            f"landuse:{r['city_id']}:{r['id']}", r["city_id"], CITY_ISO[r["city_id"]], "S", fc,
            r["name"], city_gaz_ids.get(r["city_id"]), "osm_landuse_major_zones", r["id"],
            r["lat"], r["lon"], r["area_km2"], 350.0, r["dist_cbd_km"], r["ring"], 1.5,
            f"all_5cities_osm_landuse.geojson#{r['id']}", "B"
        )

    # 3f. osm_pois key named anchors (universities, hospitals, stations, airports, markets, malls)
    key_fclasses = (
        "university", "college", "hospital", "railway_station", "station", "airport",
        "bus_station", "marketplace", "mall", "town_hall", "stadium", "museum", "theatre"
    )
    placeholders = ",".join("?" for _ in key_fclasses)
    poi_rows = conn.execute(
        f"SELECT * FROM osm_pois WHERE name IS NOT NULL AND length(trim(name)) >= 4 AND fclass IN ({placeholders})",
        key_fclasses,
    ).fetchall()
    for r in poi_rows:
        fc_raw = (r["fclass"] or "").lower()
        if fc_raw in ("university", "college"):
            fc = "university_campus"
        elif fc_raw in ("railway_station", "station", "airport", "bus_station"):
            fc = "transport_hub"
        elif fc_raw == "marketplace":
            fc = "market"
        else:
            fc = "poi_landmark"
        add_place(
            f"poi:{r['city_id']}:{r['id']}", r["city_id"], CITY_ISO[r["city_id"]], "XS", fc,
            r["name"], city_gaz_ids.get(r["city_id"]), "osm_pois", r["id"],
            r["lat"], r["lon"], 0.02, 50.0, r["dist_cbd_km"], r["ring"], 1.2, None, "B"
        )

    # 3g. zagreb_markets (31)
    for r in conn.execute("SELECT * FROM zagreb_markets").fetchall():
        add_place(
            f"market:zagreb:{r['id']}", "zagreb", "HRV", "S", "market",
            r["name"], city_gaz_ids.get("zagreb"), "zagreb_markets", r["id"],
            r["lat"], r["lon"], 0.015, 40.0, r["dist_cbd_km"], None, 2.0, None, "A1"
        )

    # 3h. xl_corridors_projects_strategies (11)
    for r in conn.execute("SELECT * FROM xl_corridors_projects_strategies").fetchall():
        aff = (r["affected_cities"] or "").lower()
        lat, lon = 44.3, 18.6
        cid = None
        for c in ("beograd", "zagreb", "sarajevo", "novi_pazar", "travnik"):
            if c in aff or c.replace("_", " ") in aff:
                lat, lon = CITY_CBD[c]
                if "," not in aff and "/" not in aff:
                    cid = c
                break
        add_place(
            f"xl:{r['item_id']}", cid, "INT", "XL", "corridor_xl",
            r["name"], None, "xl_corridors_projects_strategies", r["item_id"],
            lat, lon, 500.0, 15000.0, None, "XL", 5.0, "xl_strategic_corridors.geojson", "A2"
        )

    # 4. Flag ambiguous aliases (normalized_alias appearing across >1 city or >1 gazetteer_id)
    conn.execute(
        """
        UPDATE gazetteer_aliases
        SET is_ambiguous = 1
        WHERE normalized_alias IN (
            SELECT normalized_alias
            FROM gazetteer_aliases
            GROUP BY normalized_alias
            HAVING COUNT(DISTINCT gazetteer_id) > 1
        )
        """
    )

    conn.commit()
    g_cnt = conn.execute("SELECT COUNT(*) FROM spatial_gazetteer").fetchone()[0]
    a_cnt = conn.execute("SELECT COUNT(*) FROM gazetteer_aliases").fetchone()[0]
    amb_cnt = conn.execute("SELECT COUNT(DISTINCT normalized_alias) FROM gazetteer_aliases WHERE is_ambiguous = 1").fetchone()[0]
    rt_cnt = conn.execute("SELECT COUNT(*) FROM gazetteer_rtree").fetchone()[0]
    fk_err = conn.execute("PRAGMA foreign_key_check").fetchall()
    conn.close()

    print(f"DONE v4.1 Gazetteer Bootstrap:")
    print(f"  spatial_gazetteer : {g_cnt} places (fixed ZG JMS_IME={fixed_zg_jms})")
    print(f"  gazetteer_aliases : {a_cnt} aliases (ambiguous terms flagged={amb_cnt})")
    print(f"  gazetteer_rtree   : {rt_cnt} R-Tree bboxes")
    print(f"  foreign_key_check : {len(fk_err)} errors")


if __name__ == "__main__":
    main()
