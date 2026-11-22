from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import hashlib
import json
import math
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(str(DB_DIR))
RAW_W4 = BASE_DIR / "raw" / "wave4"
V4_DB = BASE_DIR / "curated" / "urban_lab_5cities_v4.sqlite"
MANIFEST_PATH = BASE_DIR / "manifest.jsonl"

NOW_ISO = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
BAM_TO_EUR = 1.0 / 1.95583
USD_TO_EUR = 0.92

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

CITY_ISO = {"beograd": "SRB", "zagreb": "HRV", "sarajevo": "BIH", "novi_pazar": "SRB", "travnik": "BIH"}


def norm_balkan(text: str) -> str:
    if not text:
        return ""
    s = "".join(CYR_MAP.get(ch, ch) for ch in str(text))
    s = s.replace("đ", "dj").replace("Đ", "dj")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-zA-Z0-9\s\-]", " ", s).lower()
    return re.sub(r"\s+", " ", s).strip()


def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()


def classify_topic(text: str) -> str:
    t = norm_balkan(text)
    if any(k in t for k in ["stan", "nekretnin", "kirij", "housing", "real estate", "kvadrat", "rent"]):
        return "land_rent_housing"
    if any(k in t for k in ["gup", "pdr", "urban", "plan", "gradnj", "dozvol", "katast", "zoning"]):
        return "urban_planning_gup"
    if any(k in t for k in ["tender", "nabavk", "ugovor", "procurement", "ponud"]):
        return "public_procurement"
    if any(k in t for k in ["budzet", "proracun", "porez", "fiskal", "budget", "tax"]):
        return "fiscal_budget"
    if any(k in t for k in ["saobracaj", "promet", "autoput", "cesta", "metro", "tramvaj", "gtfs", "transport", "railway", "koridor"]):
        return "transport_corridor"
    if any(k in t for k in ["plat", "plac", "zaposlen", "nezaposlen", "radnik", "wage", "labor", "labour"]):
        return "labor_wages"
    if any(k in t for k in ["vazduh", "zrak", "pm2", "zagadj", "air", "pollution", "grejanj", "energ", "klim", "earthquake", "potres"]):
        return "energy_air_climate"
    if any(k in t for k in ["turiz", "tourism", "hotel", "airbnb", "gost"]):
        return "tourism_shortterm_rent"
    if any(k in t for k in ["protest", "strajk", "blokad", "strike"]):
        return "social_friction_protest"
    if any(k in t for k in ["izbor", "glasan", "skupstin", "opcinsk", "election", "voter", "parliament"]):
        return "governance_elections"
    if any(k in t for k in ["fabrik", "industrij", "izvoz", "kompanij", "firm", "investic", "supply", "trade", "textile"]):
        return "industry_supply_chain"
    if any(k in t for k in ["doznak", "dijaspor", "remittanc", "migrac", "migration"]):
        return "diaspora_remittances"
    if any(k in t for k in ["univerzit", "nau", "znanost", "research", "science", "innovation", "university"]):
        return "science_rd_innovation"
    return "other"


def classify_party_bloc(country_iso3: str, name: str) -> tuple[str, int]:
    """Classify party/list into comparative_bloc + is_minority_list."""
    t = norm_balkan(name)
    if country_iso3 == "SRB":
        if any(k in t for k in ["aleksandar vucic", "srbija ne sme", "sns", "ivica dacic", "sps"]):
            return ("incumbent_national", 0)
        if any(k in t for k in ["srbija protiv nasilja", "zeleno", "moramo"]):
            return ("opposition_civic_green", 0)
        if any(k in t for k in ["nada", "dveri", "zavetnici", "narodna stranka"]):
            return ("opposition_center_right", 0)
        if any(k in t for k in ["spp", "usame zukorlic", "sda sandzaka", "sulejman ugljanin", "svm", "manjin", "bosnjac", "albanc", "rom", "ruska stranka", "sandzak"]):
            return ("minority_regional", 1)
        return ("other", 0)
    if country_iso3 == "HRV":
        if "hdz" in t:
            return ("incumbent_national", 0)
        if "mozemo" in t or "tomasevic" in t:
            return ("incumbent_local", 0)
        if any(k in t for k in ["sdp", "centar", "fokus", "rijeke pravde"]):
            return ("opposition_civic_green", 0)
        if any(k in t for k in ["most", "domovinski pokret", "suverenist", "selak raspudic", "herman", "lovric"]):
            return ("opposition_center_right", 0)
        if "nezavisn" in t or "kandidacijska lista grupe biraca" in t:
            return ("independent_local", 0)
        return ("other", 0)
    if country_iso3 == "BIH":
        if any(k in t for k in ["sda", "stranka demokratske akcije", "df", "demokratska fronta", "szbih", "stranka za bih"]):
            return ("opposition_center_right", 0)
        if any(k in t for k in ["nip", "narod i pravda", "sdp", "nasa stranka", "trojka"]):
            return ("incumbent_local", 0)
        if any(k in t for k in ["hdz", "hrvatska demokratska"]):
            return ("minority_regional", 0)
        if "nezavisn" in t:
            return ("independent_local", 0)
        return ("other", 0)
    return ("other", 0)


def register_sources(conn: sqlite3.Connection):
    sources = [
        ("openalex_api", "OpenAlex Global Research Graph API", "science_about_city", "B", "ALL_5", "universal_5cities", "rest_api", "weekly", "https://api.openalex.org", "CC0", "none", "Works about & in 5 cities + coauthorship graph"),
        ("bih_ejn_odata", "BiH Portal javnih nabavki (open.ejn.gov.ba OData)", "politics_procurement", "A1", "BIH", "champion_city_module", "odata_api", "daily", "https://open.ejn.gov.ba", "Open Government Data BiH", "low", "Official public procurement awards for Sarajevo & Travnik"),
        ("open_meteo_cams_aq", "Open-Meteo Copernicus CAMS Air Quality API", "sensor_environment", "A1", "ALL_5", "universal_5cities", "rest_api", "daily", "https://air-quality-api.open-meteo.com", "CC BY 4.0 / CAMS", "none", "Hourly/monthly PM2.5, PM10, NO2, SO2, EAQI 2024-2026"),
        ("open_meteo_era5_wx", "Open-Meteo ERA5 Historical Weather & HDD API", "sensor_environment", "A1", "ALL_5", "universal_5cities", "rest_api", "daily", "https://archive-api.open-meteo.com", "CC BY 4.0 / ERA5", "none", "Daily temperature, precipitation, HDD18C 2024-2026"),
        ("worldbank_wdi_api", "World Bank WDI API (Remittances & Macro)", "diaspora_social", "A2", "ALL_5", "national_macro", "rest_api", "annual", "https://api.worldbank.org/v2", "CC BY 4.0", "none", "Remittances, R&D, credit, tourism, CPI 2015-2025"),
        ("beograd_gtfs_od", "Beograd Gradski & Prigradski GTFS (data.gov.rs)", "sensor_digital_mobility", "A1", "BG", "champion_city_module", "bulk_csv_zip", "monthly", "https://data.gov.rs", "Open Data RS", "none", "Stops, routes, trips for Belgrade public transit"),
        ("zagreb_zet_gtfs", "ZET Zagreb Official GTFS Scheduled Feed", "sensor_digital_mobility", "A1", "ZG", "champion_city_module", "bulk_csv_zip", "weekly", "https://www.zet.hr/gtfs-scheduled/latest", "Open Data HR", "none", "Stops, tram/bus routes, trips for Zagreb ZET"),
        ("srb_rik_elections", "RIK Srbija Rezultati po biračkim mestima (via rezultatiizbora.rs)", "politics_elections", "A1", "SRB", "universal_5cities", "bulk_csv_zip", "event_driven", "https://rezultatiizbora.rs/data.json", "Public Official Tallies", "none", "Geocoded polling station results for Beograd & Novi Pazar (2023)"),
        ("hrv_dip_elections", "DIP RH Otvoreni podaci izbora (izbori.hr)", "politics_elections", "A1", "HRV", "universal_5cities", "bulk_csv_zip", "event_driven", "https://www.izbori.hr/arhiva-izbora", "Open Data HR", "none", "Official polling station tallies for Zagreb (Parl 2024 + Local 2025)"),
        ("bih_cik_elections", "CIK BiH Potvrđeni izborni rezultati API (izbori.ba)", "politics_elections", "A1", "BIH", "universal_5cities", "rest_api", "event_driven", "https://www.izbori.ba", "Public Official Tallies", "none", "Official polling station tallies for Sarajevo & Travnik"),
        ("zagreb_zg3d_lidar", "Grad Zagreb ZG3D 2022 LiDAR 3D Model (data.zagreb.hr)", "spatial_cadastre_3d", "A1", "ZG", "champion_city_module", "bulk_csv_zip", "static", "https://data.zagreb.hr", "Open Data Zagreb", "none", "LiDAR 3D building footprints, heights & volumes (Donji Grad, Trnje, NZ Istok)"),
        ("osm_3d_buildings", "OpenStreetMap 3D Buildings (Overpass height/levels)", "spatial_cadastre_3d", "C", "ALL_5", "universal_5cities", "rest_api", "monthly", "https://overpass-api.de", "ODbL", "none", "OSM 3D building footprints with explicit height (B) or levels-estimated (C)"),
        ("gdelt_doc_2", "GDELT Project 2.0 DOC API", "news_global", "C", "ALL_5", "universal_5cities", "rest_api", "realtime_15m", "https://api.gdeltproject.org", "Open Public", "low", "Global news monitoring for 5 cities"),
        ("rss_stoplus", "Radio Sto Plus (Novi Pazar RSS)", "news_hyperlocal", "C", "NP", "champion_city_module", "rss_atom", "daily", "https://radiostoplus.com/feed/", "Public RSS", "low", "Hyperlocal Novi Pazar news"),
        ("rss_freemedia", "Free Media (Novi Pazar RSS)", "news_hyperlocal", "C", "NP", "champion_city_module", "rss_atom", "daily", "https://freemedia.rs/feed/", "Public RSS", "low", "Hyperlocal Novi Pazar news"),
        ("rss_rtvnp", "RTV Novi Pazar RSS", "news_hyperlocal", "C", "NP", "champion_city_module", "rss_atom", "daily", "https://rtvnp.rs/feed/", "Public RSS", "low", "Hyperlocal Novi Pazar public broadcaster"),
        ("rss_sandzakpress", "Sandzak Press RSS", "news_hyperlocal", "C", "NP", "champion_city_module", "rss_atom", "daily", "https://sandzakpress.net/feed/", "Public RSS", "low", "Regional Sandzak news"),
        ("rss_travnikgrad", "Travnik-grad.info RSS", "news_hyperlocal", "C", "TR", "champion_city_module", "rss_atom", "daily", "https://travnik-grad.info/feed/", "Public RSS", "low", "Hyperlocal Travnik portal"),
        ("rss_drukciji", "Drukciji Radio (Srednja Bosna RSS)", "news_hyperlocal", "C", "TR", "champion_city_module", "rss_atom", "daily", "https://drukciji.ba/feed/", "Public RSS", "low", "Central Bosnia / Travnik-Vitez local news"),
        ("rss_tntportal", "TNT Portal Travnik RSS", "news_hyperlocal", "C", "TR", "champion_city_module", "rss_atom", "daily", "https://tntportal.ba/feed/", "Public RSS", "low", "Hyperlocal Travnik portal"),
        ("rss_biznisinfo", "BiznisInfo.ba RSS", "news_regional", "C", "BIH", "champion_city_module", "rss_atom", "daily", "https://www.biznisinfo.ba/feed/", "Public RSS", "low", "BiH business & investment news"),
        ("rss_fokus_ekon", "Fokus.ba Biznis RSS", "news_regional", "C", "BIH", "champion_city_module", "rss_atom", "daily", "https://www.fokus.ba/biznis/feed/", "Public RSS", "low", "BiH economic news"),
        ("rss_poslovni", "Poslovni dnevnik RSS", "news_regional", "C", "HRV", "champion_city_module", "rss_atom", "daily", "https://www.poslovni.hr/feed", "Public RSS", "low", "Croatia business & real estate news"),
        ("rss_zagreb_info", "Zagreb.info RSS", "news_hyperlocal", "C", "ZG", "champion_city_module", "rss_atom", "daily", "https://www.zagreb.info/feed/", "Public RSS", "low", "Hyperlocal Zagreb urban news"),
        ("rss_danas_ekon", "Danas Ekonomija RSS", "news_regional", "C", "SRB", "champion_city_module", "rss_atom", "daily", "https://www.danas.rs/rubrika/ekonomija/feed/", "Public RSS", "low", "Serbia economic news"),
        ("rss_danas_bg", "Danas Beograd RSS", "news_hyperlocal", "C", "BG", "champion_city_module", "rss_atom", "daily", "https://www.danas.rs/rubrika/beograd/feed/", "Public RSS", "low", "Hyperlocal Belgrade urban news"),
        ("rss_novaekon", "Nova Ekonomija RSS", "news_regional", "C", "SRB", "champion_city_module", "rss_atom", "daily", "https://novaekonomija.rs/feed", "Public RSS", "low", "Serbia macroeconomic & urban finance news"),
        ("rss_n1_biznis", "N1 Srbija Biznis RSS", "news_regional", "C", "SRB", "champion_city_module", "rss_atom", "daily", "https://n1info.rs/biznis/feed/", "Public RSS", "low", "Regional business news"),
    ]
    conn.executemany(
        """
        INSERT OR REPLACE INTO source_registry
        (source_id, source_name, domain_axis, default_trust_tier, jurisdiction_scope, coverage_class,
         access_method, cadence, base_url, license_or_terms, pii_risk_level, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        sources,
    )


def sync_manifest(conn: sqlite3.Connection):
    if not MANIFEST_PATH.exists():
        return 0
    existing_urls = set(
        r[0] for r in conn.execute("SELECT url || '|' || COALESCE(sha256,'') FROM sources_manifest").fetchall()
    )
    added = 0
    with open(MANIFEST_PATH, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            key = f"{rec.get('url','')}|{rec.get('sha256') or ''}"
            if key in existing_urls:
                continue
            existing_urls.add(key)
            conn.execute(
                """
                INSERT INTO sources_manifest
                (checked_at, city, layer, source_name, url, http_status, ok, bytes, sha256, local_path, error)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    rec.get("checked_at") or NOW_ISO,
                    rec.get("city") or "common",
                    rec.get("layer") or "wave4",
                    rec.get("source_name") or "",
                    rec.get("url") or "",
                    rec.get("http_status"),
                    1 if rec.get("ok") else 0,
                    rec.get("bytes"),
                    rec.get("sha256"),
                    rec.get("local_path"),
                    rec.get("error"),
                ),
            )
            added += 1
    return added


class GazetteerIndex:
    """Fast in-memory mirror of spatial_gazetteer + aliases for deterministic NLP->GIS & spatial anchoring."""
    def __init__(self, conn: sqlite3.Connection):
        self.places = {}
        self.city_core = {}
        self.by_city_munis = defaultdict(list)
        self.alias_map = defaultdict(list)  # normalized_alias -> list of (gaz_id, city_id, fclass, weight, lat, lon, unc, is_ambig)

        for r in conn.execute("SELECT * FROM spatial_gazetteer").fetchall():
            d = dict(r)
            self.places[d["gazetteer_id"]] = d
            if d["feature_class"] == "city_core" and d["city_id"]:
                self.city_core[d["city_id"]] = d["gazetteer_id"]
            if d["feature_class"] in ("municipality", "district_cetvrt", "mjesni_odbor", "settlement_naselje", "tax_zone") and d["city_id"]:
                self.by_city_munis[d["city_id"]].append(d)

        for r in conn.execute(
            """
            SELECT a.gazetteer_id, a.normalized_alias, a.is_ambiguous,
                   g.city_id, g.feature_class, g.disambiguation_weight, g.centroid_lat, g.centroid_lon, g.spatial_uncertainty_m
            FROM gazetteer_aliases a
            JOIN spatial_gazetteer g ON a.gazetteer_id = g.gazetteer_id
            WHERE length(a.normalized_alias) >= 4
            """
        ).fetchall():
            self.alias_map[r["normalized_alias"]].append(dict(r))

        # Build prioritized search terms (non-generic, len >= 5 or exact city/muni names)
        self.stop_terms = {
            "grad", "opstina", "opcina", "centar", "novi", "stari", "polje", "brdo", "selo",
            "ulica", "park", "dom", "banka", "hotel", "trzni", "zavod", "skola", "institut",
            "bosna", "srbija", "hrvatska", "sever", "jug", "istok", "zapad", "nova", "mala", "velika",
        }
        self.vocab_terms = [
            k for k in self.alias_map.keys()
            if len(k) >= 5 and k not in self.stop_terms and not k.isdigit()
        ]
        # Group by city + multi-city for fast scanning
        self.city_terms = defaultdict(list)
        for term in self.vocab_terms:
            cands = self.alias_map[term]
            # Keep only meaningful spatial features (not tiny noisy POIs with generic words)
            good = [c for c in cands if c["feature_class"] in ("city_core", "municipality", "district_cetvrt", "tax_zone", "hinterland_unit", "industrial_zone", "market", "corridor_xl", "mjesni_odbor")]
            if not good:
                continue
            cids = {c["city_id"] for c in good if c["city_id"]}
            for cid in cids:
                self.city_terms[cid].append((term, good))

    def match_muni_name(self, city_id: str, muni_text: str):
        nt = norm_balkan(muni_text)
        if not nt:
            return self.city_core.get(city_id)
        # Strip administrative prefixes
        nt_clean = re.sub(r"\b(gradska opstina|opstina|opcina|grad|kanton)\b", "", nt).strip()
        best = None
        best_score = -1
        for d in self.by_city_munis.get(city_id, []):
            gn = d["normalized_name"]
            if gn == nt or gn == nt_clean:
                return d["gazetteer_id"]
            if len(gn) >= 4 and (gn in nt_clean or nt_clean in gn):
                sc = len(gn) + (5 if d["feature_class"] in ("municipality", "district_cetvrt") else 0)
                if sc > best_score:
                    best_score = sc
                    best = d["gazetteer_id"]
        return best or self.city_core.get(city_id)

    def nearest_zone(self, city_id: str, lat: float, lon: float):
        best_id = self.city_core.get(city_id)
        best_d2 = 1e9
        for d in self.by_city_munis.get(city_id, []):
            if d["feature_class"] not in ("municipality", "district_cetvrt", "tax_zone", "mjesni_odbor"):
                continue
            d2 = (d["centroid_lat"] - lat) ** 2 + (d["centroid_lon"] - lon) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_id = d["gazetteer_id"]
        return best_id

    def extract_geo_mentions(self, text: str, source_city_id: str):
        nt = " " + norm_balkan(text) + " "
        if len(nt) < 6:
            return []
        hits = []
        seen_gids = set()
        # Check terms relevant to source_city_id first (fast & high precision)
        for term, cands in self.city_terms.get(source_city_id, []):
            if f" {term} " not in nt:
                continue
            # 4-step disambiguation score
            best_c = None
            best_s = -1.0
            for c in cands:
                sc = (0.45 if c["city_id"] == source_city_id else 0.0) + 0.12 + 0.08 * min(1.0, (c["disambiguation_weight"] or 1.0) / 10.0)
                if c["feature_class"] in ("municipality", "district_cetvrt", "tax_zone"):
                    sc += 0.20
                if sc > best_s:
                    best_s = sc
                    best_c = c
            if best_c and best_c["gazetteer_id"] not in seen_gids:
                seen_gids.add(best_c["gazetteer_id"])
                fc = best_c["feature_class"]
                if fc == "city_core":
                    prec, pin = "city_core", 0
                elif fc == "municipality" or fc == "district_cetvrt":
                    prec, pin = "municipality", 0
                elif fc == "tax_zone":
                    prec, pin = "tax_zone", 0
                elif fc == "mjesni_odbor":
                    prec, pin = "neighborhood_mo", 0
                elif fc == "hinterland_unit":
                    prec, pin = "hinterland_ring", 0
                elif fc == "corridor_xl":
                    prec, pin = "corridor_line", 0
                else:
                    prec, pin = "exact_point", 1
                hits.append({
                    "gazetteer_id": best_c["gazetteer_id"],
                    "surface_form": term,
                    "geo_precision": prec,
                    "lat": best_c["centroid_lat"],
                    "lon": best_c["centroid_lon"],
                    "unc_m": best_c["spatial_uncertainty_m"],
                    "match_method": "gazetteer_context_disambiguated" if best_c["is_ambiguous"] else "gazetteer_exact",
                    "confidence": round(min(0.98, 0.55 + best_s * 0.45), 3),
                    "evidence": f"source_city={source_city_id};term={term};fc={fc}",
                    "render_as_pin": pin,
                })
        # Prefer more specific mentions if available, keep top 4
        hits.sort(key=lambda x: (0 if x["geo_precision"] != "city_core" else 1, -x["confidence"]))
        if not hits and source_city_id in self.city_core:
            gid = self.city_core[source_city_id]
            p = self.places[gid]
            hits.append({
                "gazetteer_id": gid,
                "surface_form": p["canonical_name"],
                "geo_precision": "city_core",
                "lat": p["centroid_lat"],
                "lon": p["centroid_lon"],
                "unc_m": p["spatial_uncertainty_m"],
                "match_method": "structured_admin_code",
                "confidence": 0.70,
                "evidence": f"source_city_fallback={source_city_id}",
                "render_as_pin": 0,
            })
        return hits[:4]


def load_science(conn: sqlite3.Connection, gaz: GazetteerIndex):
    sdir = RAW_W4 / "science"
    inst_p = sdir / "openalex_institutions_5cities.json"
    works_p = sdir / "openalex_works_about_5cities.json"
    collab_p = sdir / "openalex_collab_matrix_5cities.json"
    if not inst_p.exists():
        return {}

    insts = json.loads(inst_p.read_text(encoding="utf-8"))
    oa_to_ent = {}
    for x in insts:
        eid = f"ent:inst:openalex:{x['openalex_id']}"
        oa_to_ent[x["openalex_id"]] = eid
        conn.execute(
            """
            INSERT OR REPLACE INTO entities
            (entity_id, entity_type, canonical_name, normalized_name, country_iso3, primary_city_id, status, trust_tier)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (eid, "university_rd", x["display_name"], norm_balkan(x["display_name"]), x["country_iso3"], x["city_id"], "active", "B"),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO entity_identifiers
            (entity_id, id_scheme, id_value, country_iso3, match_method, match_confidence, review_status, source_id)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (eid, "openalex_inst_id", x["openalex_id"], x["country_iso3"], "deterministic_registry", 1.0, "auto_accepted", "openalex_api"),
        )
        if x.get("ror_id"):
            conn.execute(
                """
                INSERT OR IGNORE INTO entity_identifiers
                (entity_id, id_scheme, id_value, country_iso3, match_method, match_confidence, review_status, source_id)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (eid, "ror_id", x["ror_id"].split("/")[-1], x["country_iso3"], "deterministic_registry", 1.0, "auto_accepted", "openalex_api"),
            )

    rel_n = 0
    if collab_p.exists():
        for c in json.loads(collab_p.read_text(encoding="utf-8")):
            ea = oa_to_ent.get(c["inst_a_id"])
            eb = oa_to_ent.get(c["inst_b_id"])
            if ea and eb and ea != eb and c.get("coauthored_works_2016_2026", 0) > 0:
                conn.execute(
                    """
                    INSERT INTO entity_relations
                    (subject_entity_id, relation_type, object_entity_id, numeric_value, numeric_unit,
                     valid_from, valid_to, trust_tier, epistemic_status, primary_url, captured_at, notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        ea, "collaborates_research_with", eb, float(c["coauthored_works_2016_2026"]), "COUNT",
                        "2016-01-01", "2026-11-22", "B", "factual_record",
                        f"https://api.openalex.org/works?filter=authorships.institutions.id:{c['inst_a_id']},authorships.institutions.id:{c['inst_b_id']}",
                        NOW_ISO, f"Coauthored papers 2016-2026 ({c['city_a']} <-> {c['city_b']})",
                    ),
                )
                rel_n += 1

    works_n = 0
    mentions_n = 0
    if works_p.exists():
        works = json.loads(works_p.read_text(encoding="utf-8"))
        for w in works:
            wid = w["work_id"]
            doc_id = f"doc:openalex:{wid}"
            cid = w["city_id"]
            title = w["title"]
            summary = w.get("abstract_snippet") or ""
            url = w.get("landing_url") or f"https://openalex.org/{wid}"
            pub_dt = w.get("publication_date") or f"{w.get('publication_year', 2024)}-01-01"
            topic = classify_topic(title + " " + summary)
            conn.execute(
                """
                INSERT OR IGNORE INTO evidence_documents
                (doc_id, source_id, doc_type, trust_tier, epistemic_role, primary_city_id, country_iso3,
                 title, summary_text, language, published_at, fetched_at, primary_url, raw_sha256, topic_primary, nlp_pipeline_version)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    doc_id, "openalex_api", "scientific_paper", "B", "peer_reviewed_finding", cid, CITY_ISO[cid],
                    title, summary, (w.get("language") or "en")[:10], pub_dt, NOW_ISO, url,
                    sha256_str(doc_id + "|" + title), topic, "gazetteer-v4.1-deterministic",
                ),
            )
            inst_ent = None
            for iid in (w.get("institution_ids") or []):
                if iid in oa_to_ent:
                    inst_ent = oa_to_ent[iid]
                    break
            wtype = "journal_article"
            if (w.get("type") or "") == "dissertation":
                wtype = "dissertation"
            elif "proceedings" in (w.get("type") or ""):
                wtype = "conference"
            conn.execute(
                """
                INSERT OR IGNORE INTO domain_signals_science
                (work_uid, doc_id, science_role, work_type, city_id, institution_entity_id, pub_year,
                 doi_or_grant_no, cited_by_count, open_access_url, concepts_json, trust_tier)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    f"openalex:{wid}", doc_id, w.get("science_role", "about_city"), wtype, cid, inst_ent,
                    int(w.get("publication_year") or 2024), w.get("doi"), int(w.get("cited_by_count") or 0),
                    w.get("open_access_url"), json.dumps(w.get("concepts") or [], ensure_ascii=False), "B",
                ),
            )
            if inst_ent:
                conn.execute(
                    "INSERT OR IGNORE INTO document_entity_mentions (doc_id, entity_id, surface_form, mention_role, confidence) VALUES (?,?,?,?,?)",
                    (doc_id, inst_ent, inst_ent, "research_institution", 1.0),
                )
            for gm in gaz.extract_geo_mentions(title + " " + summary, cid):
                conn.execute(
                    """
                    INSERT INTO document_geo_mentions
                    (doc_id, gazetteer_id, surface_form, geo_role, geo_precision, lat, lon,
                     spatial_uncertainty_m, match_method, geo_confidence, disambiguation_evidence, render_as_pin)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        doc_id, gm["gazetteer_id"], gm["surface_form"], "subject_location", gm["geo_precision"],
                        gm["lat"], gm["lon"], gm["unc_m"], gm["match_method"], gm["confidence"], gm["evidence"], gm["render_as_pin"],
                    ),
                )
                mentions_n += 1
            works_n += 1
    return {"institutions": len(insts), "collab_relations": rel_n, "works": works_n, "geo_mentions": mentions_n}


def load_procurement_bih(conn: sqlite3.Connection, gaz: GazetteerIndex):
    p = RAW_W4 / "procurement_bih" / "ejn_awards_sarajevo_travnik_consolidated.json"
    if not p.exists():
        return {}
    rows = json.loads(p.read_text(encoding="utf-8"))
    buyers_seen = set()
    loaded = 0
    for row in rows:
        aid = row.get("Id")
        cid = row.get("_urbanlab_city_id", "sarajevo")
        buyer_name = (row.get("ContractingAuthorityName") or "Unknown Authority").strip()
        buyer_jib = re.sub(r"\D", "", str(row.get("ContractingAuthorityTaxNumber") or ""))
        buyer_city = (row.get("ContractingAuthorityCityName") or "").strip()
        buyer_ent = f"ent:pub:bih:{buyer_jib}" if buyer_jib else f"ent:pub:bih:ejn_{row.get('ContractingAuthorityId', aid)}"

        if buyer_ent not in buyers_seen:
            buyers_seen.add(buyer_ent)
            etype = "municipality_authority" if ("OPĆIN" in buyer_name.upper() or "OPŠTIN" in buyer_name.upper() or "GRAD " in buyer_name.upper() or "KANTON" in buyer_name.upper()) else "public_institution"
            conn.execute(
                """
                INSERT OR IGNORE INTO entities
                (entity_id, entity_type, canonical_name, normalized_name, country_iso3, primary_city_id, status, trust_tier)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (buyer_ent, etype, buyer_name, norm_balkan(buyer_name), "BIH", cid, "active", "A1"),
            )
            if buyer_jib:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO entity_identifiers
                    (entity_id, id_scheme, id_value, country_iso3, match_method, match_confidence, review_status, source_id)
                    VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (buyer_ent, "bih_jib", buyer_jib, "BIH", "deterministic_registry", 1.0, "auto_accepted", "bih_ejn_odata"),
                )

        doc_id = f"doc:ejn:award:{aid}"
        title = (row.get("ProcedureName") or row.get("LotName") or f"EJN Award {aid}").strip()
        award_dt = (row.get("ContractDate") or row.get("LastUpdated") or "2025-01-01")[:10]
        val_bam = float(row.get("Value") or 0.0)
        val_eur = round(max(0.0, val_bam * BAM_TO_EUR), 2)
        est_bam = row.get("HighestAcceptableOfferValue")
        est_eur = round(float(est_bam) * BAM_TO_EUR, 2) if (est_bam and float(est_bam) > 0) else None
        bidders = row.get("NumberOfReceivedOffers")
        bidders_int = int(bidders) if bidders is not None and int(bidders) >= 0 else None
        url = f"https://open.ejn.gov.ba/Awards?$filter=Id%20eq%20{aid}"
        gaz_id = gaz.match_muni_name(cid, buyer_city or buyer_name)

        conn.execute(
            """
            INSERT OR IGNORE INTO evidence_documents
            (doc_id, source_id, doc_type, trust_tier, epistemic_role, primary_city_id, country_iso3,
             title, summary_text, language, published_at, fetched_at, primary_url, raw_sha256, topic_primary, nlp_pipeline_version)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                doc_id, "bih_ejn_odata", "procurement_award", "A1", "primary_record", cid, "BIH",
                title[:280], f"Authority: {buyer_name} ({buyer_city}); Type: {row.get('ContractType')}; Category: {row.get('ContractCategoryName')}; Value: {val_bam:,.2f} BAM; Bidders: {bidders_int}",
                "bs", award_dt, NOW_ISO, url, sha256_str(doc_id + "|" + title), "public_procurement", "structured-odata-v4.1",
            ),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO domain_signals_procurement
            (contract_uid, doc_id, city_id, country_iso3, gazetteer_id, buyer_entity_id, winner_entity_id,
             cpv_code, cpv_division, procedure_type, award_date, estimated_value_eur, contract_value_eur,
             currency_orig, bidders_count, trust_tier)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                f"ejn:bih:{aid}", doc_id, cid, "BIH", gaz_id, buyer_ent, None,
                row.get("ContractSubcategoryName"), row.get("ContractCategoryName"), row.get("ProcedureType"),
                award_dt, est_eur, val_eur, "BAM", bidders_int, "A1",
            ),
        )
        conn.execute(
            "INSERT OR IGNORE INTO document_entity_mentions (doc_id, entity_id, surface_form, mention_role, confidence) VALUES (?,?,?,?,?)",
            (doc_id, buyer_ent, buyer_name, "contracting_authority", 1.0),
        )
        if gaz_id and gaz_id in gaz.places:
            gp = gaz.places[gaz_id]
            prec = "city_core" if gp["feature_class"] == "city_core" else "municipality"
            conn.execute(
                """
                INSERT INTO document_geo_mentions
                (doc_id, gazetteer_id, surface_form, geo_role, geo_precision, lat, lon,
                 spatial_uncertainty_m, match_method, geo_confidence, disambiguation_evidence, render_as_pin)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    doc_id, gaz_id, buyer_city or buyer_name, "authority_seat", prec,
                    gp["centroid_lat"], gp["centroid_lon"], gp["spatial_uncertainty_m"],
                    "structured_admin_code", 0.92, f"ejn_city={buyer_city}", 0,
                ),
            )
        loaded += 1
    return {"contracts": loaded, "buyers": len(buyers_seen)}


def load_news(conn: sqlite3.Connection, gaz: GazetteerIndex):
    p = RAW_W4 / "news" / "news_rss_gdelt_5cities.json"
    if not p.exists():
        return {}
    arts = json.loads(p.read_text(encoding="utf-8")).get("articles") or []
    loaded = 0
    mentions = 0
    for a in arts:
        h = a.get("raw_sha256") or sha256_str((a.get("url") or "") + "|" + (a.get("title") or ""))
        doc_id = f"doc:news:{h[:16]}"
        cid = a["city_id"]
        src_id = a.get("source_id") or "gdelt_doc_2"
        title = (a.get("title") or "").strip()
        if not title:
            continue
        summary = (a.get("summary") or "")[:600]
        topic = classify_topic(title + " " + summary)
        conn.execute(
            """
            INSERT OR IGNORE INTO evidence_documents
            (doc_id, source_id, doc_type, trust_tier, epistemic_role, primary_city_id, country_iso3,
             title, summary_text, language, published_at, fetched_at, primary_url, raw_sha256, topic_primary, nlp_pipeline_version)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                doc_id, src_id, "news_article", "C", "media_report", cid, a.get("country_iso3") or CITY_ISO[cid],
                title[:300], summary, (a.get("language") or "sr")[:10], a.get("published_at") or NOW_ISO[:10],
                NOW_ISO, a.get("url") or "https://example.org", h, topic, "gazetteer-v4.1-deterministic",
            ),
        )
        if conn.total_changes > 0:
            loaded += 1
            for gm in gaz.extract_geo_mentions(title + " " + summary, cid):
                conn.execute(
                    """
                    INSERT INTO document_geo_mentions
                    (doc_id, gazetteer_id, surface_form, geo_role, geo_precision, lat, lon,
                     spatial_uncertainty_m, match_method, geo_confidence, disambiguation_evidence, render_as_pin)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        doc_id, gm["gazetteer_id"], gm["surface_form"], "subject_location", gm["geo_precision"],
                        gm["lat"], gm["lon"], gm["unc_m"], gm["match_method"], gm["confidence"], gm["evidence"], gm["render_as_pin"],
                    ),
                )
                mentions += 1
    return {"articles": loaded, "geo_mentions": mentions}


def load_sensors_and_gtfs_and_event_study(conn: sqlite3.Connection, gaz: GazetteerIndex):
    sdir = RAW_W4 / "sensors"
    air_p = sdir / "openmeteo_air_monthly_5cities.json"
    wb_p = sdir / "worldbank_diaspora_macro_3countries.json"
    sens_n = 0

    air_rows = json.loads(air_p.read_text(encoding="utf-8")) if air_p.exists() else []
    for r in air_rows:
        cid = r["city_id"]
        pt = r["point_id"]
        ym = r["month"]
        p_start = f"{ym}-01"
        p_end = f"{ym}-28"
        gid = gaz.city_core.get(cid)
        if pt == "sarajevo_ilidza":
            gid = gaz.match_muni_name("sarajevo", "Ilidza")
        for metric, val, unit in [
            ("openaq_pm25_ugm3", r.get("pm25_mean_ugm3"), "ug/m3"),
            ("openaq_no2_ugm3", r.get("no2_mean_ugm3"), "ug/m3"),
        ]:
            if val is None:
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO domain_signals_sensors
                (source_id, city_id, gazetteer_id, grid_cell_id, sensor_metric, period_start, period_end,
                 cadence, value_num, value_unit, sample_n, trust_tier)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                ("open_meteo_cams_aq", cid, gid, pt, metric, p_start, p_end, "monthly", float(val), unit, int(r.get("hours_n") or 720), "A1"),
            )
            sens_n += 1

    # World Bank remittances (remittances_mio_eur) anchored to each city's country
    if wb_p.exists():
        wb_rows = json.loads(wb_p.read_text(encoding="utf-8"))
        iso_to_cities = {"SRB": ["beograd", "novi_pazar"], "HRV": ["zagreb"], "BIH": ["sarajevo", "travnik"]}
        for r in wb_rows:
            if r.get("indicator_slug") == "remittances_received_usd" and r.get("value") is not None:
                yr = r["year"]
                val_mio_eur = round((float(r["value"]) * USD_TO_EUR) / 1e6, 2)
                for cid in iso_to_cities.get(r["country_iso3"], []):
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO domain_signals_sensors
                        (source_id, city_id, gazetteer_id, grid_cell_id, sensor_metric, period_start, period_end,
                         cadence, value_num, value_unit, sample_n, trust_tier)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        ("worldbank_wdi_api", cid, gaz.city_core.get(cid), f"wb_{r['country_iso3']}", "remittances_mio_eur", f"{yr}-01-01", f"{yr}-12-31", "annual", val_mio_eur, "mio_EUR", 1, "A2"),
                    )
                    sens_n += 1

    # GTFS mobility aggregates as A1 sensor evidence documents
    mdir = RAW_W4 / "mobility_and_permits"
    for fn, cid, src_id, title in [
        ("mobility_permits_summary.json", "beograd", "beograd_gtfs_od", "Beograd GTFS 2026 (Gradski + Prigradski javni prevoz)"),
        ("gtfs_zet_zagreb_summary.json", "zagreb", "zagreb_zet_gtfs", "ZET Zagreb GTFS 2026 (Tramvaji + Autobusi)"),
    ]:
        fp = mdir / fn
        if not fp.exists():
            continue
        d = json.loads(fp.read_text(encoding="utf-8"))
        doc_id = f"doc:gtfs:{cid}:2026"
        conn.execute(
            """
            INSERT OR IGNORE INTO evidence_documents
            (doc_id, source_id, doc_type, trust_tier, epistemic_role, primary_city_id, country_iso3,
             title, summary_text, language, published_at, fetched_at, primary_url, raw_sha256, topic_primary, extraction_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                doc_id, src_id, "sensor_aggregate", "A1", "primary_record", cid, CITY_ISO[cid],
                title, json.dumps(d, ensure_ascii=False)[:500], "sr" if cid == "beograd" else "hr",
                "2026-11-05", NOW_ISO, "https://data.gov.rs" if cid == "beograd" else "https://www.zet.hr/gtfs-scheduled/latest",
                sha256_str(doc_id), "transport_corridor", json.dumps(d, ensure_ascii=False),
            ),
        )

    # Real Empirical Event-Study ES-03: Winter Heating Season PM2.5 Shock (t0 = 2025-11-01)
    # Comparing Treated Core (Sarajevo Centar / Ilidza + Novi Pazar) vs Control (Zagreb CBD) using REAL Open-Meteo CAMS data!
    if air_rows:
        evt_id = "evt:sa:2025-11:winter_heating_pm25_shock"
        conn.execute(
            """
            INSERT OR REPLACE INTO urban_events
            (event_id, city_id, event_category, title, summary, t0_announced, t0_enacted, t0_effective,
             primary_t0, primary_t0_type, severity_score, corroborated_trust_tier, verification_status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                evt_id, "sarajevo", "environmental_crisis",
                "Zimska grejna sezona 2025/2026 — skok PM2.5 čestica u sarajevskoj kotlini (CAMS A1)",
                "Empirijsko poređenje mesečnih koncentracija PM2.5 pre (maj–oktobar 2025) i tokom grejne sezone (novembar 2025 – februar 2026) u Sarajevu (Centar/Ilidža) u odnosu na kontrolni grad Zagreb i Istočno Sarajevo.",
                "2025-10-15", "2025-10-15", "2025-11-01", "2025-11-01", "effective", 4.5, "A1", "official_record_verified",
            ),
        )
        conn.execute(
            "INSERT OR IGNORE INTO event_locations (event_id, gazetteer_id, impact_role, impact_radius_km) VALUES (?,?,?,?)",
            (evt_id, gaz.city_core["sarajevo"], "epicenter", 10.0),
        )
        study_id = "es:sa_vs_zg:winter_heating_pm25_2025_2026"
        conn.execute(
            """
            INSERT OR REPLACE INTO event_studies
            (study_id, event_id, study_title, hypothesis, t0_anchor_type, t0_date, outcome_metric, outcome_unit,
             treatment_definition, control_definition, identification_grade, effective_trust_tier, min_upstream_tier)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                study_id, evt_id,
                "ES-03: Zimski šok energetskog siromaštva i PM2.5 (Sarajevo vs. Zagreb kontrola, 2025/26)",
                "Početak grejne sezone (t0=2025-11) proizvodi višestruko veći skok PM2.5 u sarajevskoj kotlini (čvrsta goriva + inverzija) nego u kontrolnom gradu Zagrebu.",
                "effective", "2025-11-01", "openaq_pm25_ugm3", "ug/m3",
                "Sarajevo Centar (CAMS A1 mesečni prosek PM2.5)",
                "Zagreb CBD (CAMS A1 mesečni prosek PM2.5 u istim mesecima)",
                "staggered_multi_city_did", "D", "A1",
            ),
        )
        by_pt_m = {(r["point_id"], r["month"]): r for r in air_rows}
        rel_months = [
            (-4, "2025-07"), (-3, "2025-08"), (-2, "2025-09"), (-1, "2025-10"),
            (0, "2025-11"), (1, "2025-12"), (2, "2026-01"), (3, "2026-02"),
        ]
        for cohort, pt_id, cid in [
            ("treated_core", "sarajevo_centar", "sarajevo"),
            ("control_local", "zagreb_cbd", "zagreb"),
            ("spillover_ring", "istocno_sarajevo_control", "sarajevo"),
        ]:
            base_row = by_pt_m.get((pt_id, "2025-10"))
            base_val = base_row["pm25_mean_ugm3"] if base_row else None
            for rp, ym in rel_months:
                row = by_pt_m.get((pt_id, ym))
                if not row:
                    continue
                conn.execute(
                    """
                    INSERT OR REPLACE INTO event_study_observations
                    (study_id, cohort_group, rel_period, rel_unit, calendar_period, city_id, gazetteer_id,
                     metric_value, baseline_value, sample_n, upstream_trust_tier)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        study_id, cohort, rp, "month", ym, cid, gaz.city_core.get(cid),
                        row["pm25_mean_ugm3"], base_val, row["hours_n"], "A1",
                    ),
                )

    return {"sensor_observations": sens_n}


def load_elections(conn: sqlite3.Connection, gaz: GazetteerIndex):
    edir = RAW_W4 / "elections"
    cycles_def = [
        ("elec:srb:2023-12-17:parl", "SRB", "RIK", "parliamentary_national", "2023-12-17", 1, "Parlamentarni izbori u Srbiji 2023 (Beograd + Novi Pazar BM)", 3.0, 1, "srb_rik_elections"),
        ("elec:hrv:2024-04-17:parl", "HRV", "DIP", "parliamentary_national", "2024-04-17", 1, "Izbori za Hrvatski sabor 2024 (Grad Zagreb BM)", 5.0, 0, "hrv_dip_elections"),
        ("elec:hrv:2025-05-18:local_zg_assembly", "HRV", "DIP", "city_assembly", "2025-05-18", 1, "Lokalni izbori 2025 — Skupština Grada Zagreba (BM)", 5.0, 0, "hrv_dip_elections"),
        ("elec:hrv:2025-05-18:local_zg_mayor", "HRV", "DIP", "mayor_executive", "2025-05-18", 1, "Lokalni izbori 2025 — Gradonačelnik Grada Zagreba (1. krug BM)", None, 0, "hrv_dip_elections"),
    ]
    for cyc in cycles_def:
        conn.execute(
            """
            INSERT OR REPLACE INTO election_cycles
            (election_id, country_iso3, authority_body, election_level, election_date, round_no,
             title, legal_threshold_pct, minority_natural_threshold, source_id, trust_tier)
            VALUES (?,?,?,?,?,?,?,?,?,?,'A1')
            """,
            cyc,
        )

    stations_loaded = 0
    results_loaded = 0

    def insert_station_and_results(st_list, elec_id_override=None):
        nonlocal stations_loaded, results_loaded
        for s in st_list:
            eid = elec_id_override or s["election_id"]
            cid = s["city_id"]
            iso = s["country_iso3"]
            muni = s.get("muni") or cid
            scode = str(s["station_code"])
            stype = s.get("station_type") or "regular"
            suid = f"ps:{eid}:{cid}:{norm_balkan(muni).replace(' ','_')[:20]}:{scode}:{stype}"

            lat = s.get("lat")
            lon = s.get("lon")
            if lat is not None and lon is not None:
                gid = gaz.nearest_zone(cid, float(lat), float(lon))
                gprec, unc, rpin = "exact_point", 50.0, 1
            else:
                gid = gaz.match_muni_name(cid, muni)
                gp = gaz.places.get(gid)
                lat = gp["centroid_lat"] if gp else None
                lon = gp["centroid_lon"] if gp else None
                gprec = "municipality" if (gp and gp["feature_class"] != "city_core") else "city_core"
                unc = gp["spatial_uncertainty_m"] if gp else 2000.0
                rpin = 0

            reg = s.get("registered")
            cast = int(s.get("voted") or 0)
            valid = int(s.get("valid") or 0)
            invalid = int(s.get("invalid") or 0)
            if valid + invalid > cast:
                cast = valid + invalid
            if stype == "regular" and reg is not None and cast > reg:
                reg = cast

            conn.execute(
                """
                INSERT OR REPLACE INTO polling_stations
                (station_uid, election_id, city_id, country_iso3, constituency_code, municipality_name,
                 station_code, station_name, address_text, station_type, gazetteer_id, lat, lon,
                 geo_precision, spatial_uncertainty_m, render_as_pin, registered_voters, ballots_cast,
                 valid_ballots, invalid_ballots, trust_tier)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'A1')
                """,
                (
                    suid, eid, cid, iso, s.get("constituency"), muni, scode,
                    (s.get("station_name") or f"BM {scode}")[:180], s.get("address"), stype, gid,
                    lat, lon, gprec, unc, rpin, reg, cast, valid, invalid,
                ),
            )
            stations_loaded += 1
            votes_map = s.get("votes") or {}
            for lname, vcnt in votes_map.items():
                vcnt = int(vcnt or 0)
                if vcnt <= 0:
                    continue
                bloc, is_min = classify_party_bloc(iso, lname)
                share = round(100.0 * vcnt / valid, 2) if valid > 0 else None
                if share is not None and share > 100.0:
                    share = 100.0
                conn.execute(
                    """
                    INSERT OR REPLACE INTO election_station_results
                    (station_uid, election_id, list_or_candidate_name, comparative_bloc, is_minority_list,
                     votes_count, vote_share_valid_pct, trust_tier)
                    VALUES (?,?,?,?,?,?,?,'A1')
                    """,
                    (suid, eid, lname[:180], bloc, is_min, vcnt, share),
                )
                results_loaded += 1

    # 1. RIK 2023 (BG + NP)
    p_rik = edir / "parsed_rik_2023_bg_np.json"
    if p_rik.exists():
        insert_station_and_results(json.loads(p_rik.read_text(encoding="utf-8")))

    # 2. DIP 2024 Parl (Zagreb)
    p_dip24 = edir / "parsed_dip_2024_zagreb.json"
    if p_dip24.exists():
        insert_station_and_results(json.loads(p_dip24.read_text(encoding="utf-8")))

    # 3. DIP 2025 Local (Zagreb Skupština + Gradonačelnik)
    p_dip25 = edir / "parsed_dip_2025_zagreb.json"
    if p_dip25.exists():
        d25 = json.loads(p_dip25.read_text(encoding="utf-8"))
        insert_station_and_results(d25.get("skupstina") or [])
        insert_station_and_results(d25.get("gradonacelnik") or [])

    # 4. CIK BiH (Sarajevo + Travnik) if collected
    p_cik = edir / "parsed_cik_2024_sa_tr.json"
    if p_cik.exists():
        cik_rows = json.loads(p_cik.read_text(encoding="utf-8"))
        if cik_rows:
            seen_cycs = set()
            for s in cik_rows:
                eid = s["election_id"]
                if eid not in seen_cycs:
                    seen_cycs.add(eid)
                    edate = s.get("election_date") or "2024-10-06"
                    lvl = "mayor_executive" if "mayor" in eid else "municipality_council"
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO election_cycles
                        (election_id, country_iso3, authority_body, election_level, election_date, round_no,
                         title, legal_threshold_pct, minority_natural_threshold, source_id, trust_tier)
                        VALUES (?,?,?,?,?,?,?,?,?,?,'A1')
                        """,
                        (eid, "BIH", "CIK", lvl, edate, 1, f"CIK BiH Lokalni izbori {edate[:4]} ({lvl} — Sarajevo & Travnik)", 3.0 if lvl == "municipality_council" else None, 0, "bih_cik_elections"),
                    )
            insert_station_and_results(cik_rows)

    return {"polling_stations": stations_loaded, "station_results": results_loaded}


def load_xs_3d_buildings(conn: sqlite3.Connection, gaz: GazetteerIndex):
    p = RAW_W4 / "xs_3d" / "xs_buildings_3d_5cities_consolidated.json"
    if not p.exists():
        return {}
    bldgs = json.loads(p.read_text(encoding="utf-8"))
    loaded = 0
    for b in bldgs:
        cid = b["city_id"]
        gid = gaz.nearest_zone(cid, b["centroid_lat"], b["centroid_lon"])
        gfa = round(b["footprint_area_m2"] * (b.get("floors_above_ground") or max(1, int(round(b["height_m"] / 3.2)))), 2)
        conn.execute(
            """
            INSERT OR REPLACE INTO xs_buildings_3d
            (building_uid, city_id, country_iso3, gazetteer_id, building_name, address_text, building_use,
             footprint_area_m2, height_m, ground_elevation_m, floors_above_ground, gross_floor_area_m2,
             height_source, centroid_lat, centroid_lon, min_lon, max_lon, min_lat, max_lat, source_id, trust_tier)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                b["building_uid"], cid, b["country_iso3"], gid, b.get("building_name"), b.get("address_text"),
                b.get("building_use") or "unknown", b["footprint_area_m2"], b["height_m"], b.get("ground_elevation_m"),
                b.get("floors_above_ground"), gfa, b["height_source"],
                b["centroid_lat"], b["centroid_lon"], b["min_lon"], b["max_lon"], b["min_lat"], b["max_lat"],
                b["source_id"], b["trust_tier"],
            ),
        )
        loaded += 1
    return {"buildings_3d": loaded}


def main():
    assert V4_DB.exists(), f"Run 27a_bootstrap_v4_gazetteer.py first! Missing {V4_DB}"
    conn = sqlite3.connect(str(V4_DB))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    print("1. Registering Wave 4 sources & syncing SHA-256 manifest...", flush=True)
    register_sources(conn)
    m_added = sync_manifest(conn)
    print(f"   manifest rows added: {m_added}", flush=True)

    print("2. Building in-memory Gazetteer NLP->GIS index...", flush=True)
    gaz = GazetteerIndex(conn)
    print(f"   places={len(gaz.places)}, vocab_terms={len(gaz.vocab_terms)}", flush=True)

    print("3. Loading OpenAlex Science (Institutions, Collab Graph, Works)...", flush=True)
    st_sci = load_science(conn, gaz)
    print("  ", st_sci, flush=True)

    print("4. Loading BiH EJN Public Procurement (Sarajevo + Travnik)...", flush=True)
    st_proc = load_procurement_bih(conn, gaz)
    print("  ", st_proc, flush=True)

    print("5. Loading Multi-City RSS & GDELT News + NLP->GIS Geo-Mentions...", flush=True)
    st_news = load_news(conn, gaz)
    print("  ", st_news, flush=True)

    print("6. Loading Independent Sensors (Open-Meteo CAMS AQ, World Bank, GTFS) + ES-03 Event-Study...", flush=True)
    st_sens = load_sensors_and_gtfs_and_event_study(conn, gaz)
    print("  ", st_sens, flush=True)

    print("7. Loading Electoral Geography by Polling Station (RIK + DIP + CIK)...", flush=True)
    st_elec = load_elections(conn, gaz)
    print("  ", st_elec, flush=True)

    print("8. Loading XS 3D Buildings + Native SQLite R-Tree (ZG3D LiDAR + OSM 3D 5 Cities)...", flush=True)
    st_3d = load_xs_3d_buildings(conn, gaz)
    print("  ", st_3d, flush=True)

    conn.commit()

    # Final Integrity & Analytical Views Verification
    fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
    summary = {
        "db_path": str(V4_DB),
        "db_size_bytes": V4_DB.stat().st_size,
        "foreign_key_errors": len(fk_errors),
        "manifest_added": m_added,
        "science": st_sci,
        "procurement": st_proc,
        "news": st_news,
        "sensors": st_sens,
        "elections": st_elec,
        "xs_3d": st_3d,
        "table_counts": {},
    }
    for tbl in [
        "source_registry", "sources_manifest", "entities", "entity_identifiers", "entity_relations",
        "spatial_gazetteer", "gazetteer_aliases", "gazetteer_rtree",
        "evidence_documents", "document_geo_mentions", "document_entity_mentions",
        "domain_signals_procurement", "domain_signals_science", "domain_signals_sensors",
        "election_cycles", "polling_stations", "election_station_results",
        "xs_buildings_3d", "xs_buildings_rtree",
        "urban_events", "event_studies", "event_study_observations",
    ]:
        summary["table_counts"][tbl] = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]

    # Sample key analytical views!
    summary["view_trust_coverage"] = [dict(r) for r in conn.execute("SELECT * FROM v_trust_tier_coverage_by_city").fetchall()]
    summary["view_procurement"] = [dict(r) for r in conn.execute("SELECT * FROM v_procurement_structural_indicators").fetchall()]
    summary["view_event_study_did"] = [dict(r) for r in conn.execute("SELECT * FROM v_event_study_did_summary").fetchall()]
    summary["view_election_summary"] = [
        dict(r) for r in conn.execute(
            """
            SELECT election_id, city_id, COUNT(*) AS stations_n,
                   ROUND(AVG(turnout_pct), 2) AS avg_turnout_pct,
                   ROUND(AVG(invalid_ballots_pct), 2) AS avg_invalid_pct,
                   ROUND(AVG(winning_margin_pp), 2) AS avg_margin_pp,
                   ROUND(AVG(effective_num_parties_enp), 3) AS avg_enp
            FROM v_election_station_metrics
            WHERE station_type = 'regular'
            GROUP BY election_id, city_id
            ORDER BY city_id, election_id
            """
        ).fetchall()
    ]
    summary["view_xs_3d_by_city"] = [
        dict(r) for r in conn.execute(
            """
            SELECT city_id, COUNT(*) AS buildings_n,
                   ROUND(SUM(footprint_area_m2)/1e6, 3) AS footprint_km2,
                   ROUND(SUM(volume_m3)/1e6, 2) AS volume_mio_m3,
                   ROUND(AVG(height_m), 2) AS avg_height_m,
                   ROUND(MAX(height_m), 2) AS max_height_m,
                   ROUND(100.0 * SUM(CASE WHEN trust_tier IN ('A1','A2') THEN 1 ELSE 0 END) / COUNT(*), 1) AS high_trust_pct
            FROM xs_buildings_3d
            GROUP BY city_id
            ORDER BY buildings_n DESC
            """
        ).fetchall()
    ]
    conn.close()

    out_sum = BASE_DIR / "curated" / "analysis" / "v4_wave4_build_summary.json"
    out_sum.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== WAVE 4 v4.1 BUILD COMPLETE ===")
    print(f"DB size: {summary['db_size_bytes']:,} bytes | FK errors: {summary['foreign_key_errors']}")
    print("Table counts:", json.dumps(summary["table_counts"], indent=2))
    print("Election metrics:", json.dumps(summary["view_election_summary"], indent=2))
    print("XS 3D by city:", json.dumps(summary["view_xs_3d_by_city"], indent=2))
    print("ES-03 DiD:", json.dumps(summary["view_event_study_did"], indent=2))


if __name__ == "__main__":
    main()
