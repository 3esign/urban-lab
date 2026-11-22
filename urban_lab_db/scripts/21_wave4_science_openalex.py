import json
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_net import RAW_DIR, fetch_url

OUT_DIR = RAW_DIR / "wave4" / "science"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MAILTO = "urbanlab-research@svemir.local"

# 1. Core research institutions in the 5 cities (Uloga B: Science IN city)
INSTITUTION_QUERIES = [
    ("beograd", "SRB", "University of Belgrade", "Belgrade"),
    ("beograd", "SRB", "Institute of Economic Sciences Belgrade", "Belgrade"),
    ("beograd", "SRB", "Institute of Physics Belgrade", "Belgrade"),
    ("beograd", "SRB", "Singidunum University", "Belgrade"),
    ("zagreb", "HRV", "University of Zagreb", "Zagreb"),
    ("zagreb", "HRV", "Rudjer Boskovic Institute", "Zagreb"),
    ("zagreb", "HRV", "Institute of Economics, Zagreb", "Zagreb"),
    ("sarajevo", "BIH", "University of Sarajevo", "Sarajevo"),
    ("sarajevo", "BIH", "International Burch University", "Sarajevo"),
    ("sarajevo", "BIH", "Sarajevo School of Science and Technology", "Sarajevo"),
    ("novi_pazar", "SRB", "State University of Novi Pazar", "Novi Pazar"),
    ("novi_pazar", "SRB", "International University of Novi Pazar", "Novi Pazar"),
    ("travnik", "BIH", "University of Travnik", "Travnik"),
    ("travnik", "BIH", "International University Travnik", "Travnik"),
]

# 2. Research ABOUT each city (Uloga A: urban economy, planning, housing, air, transport, governance)
CITY_TOPICS = {
    "beograd": [
        ("urban_econ", 'Belgrade ("urban" OR "real estate" OR "housing" OR "economy" OR "transport" OR "planning")'),
        ("env_gov", 'Belgrade ("air pollution" OR "PM2.5" OR "gentrification" OR "public procurement" OR "municipality")'),
    ],
    "zagreb": [
        ("urban_econ", 'Zagreb ("urban" OR "real estate" OR "housing" OR "economy" OR "transport" OR "planning")'),
        ("env_gov", 'Zagreb ("earthquake" OR "gentrification" OR "tourism" OR "air quality" OR "municipality")'),
    ],
    "sarajevo": [
        ("urban_econ", 'Sarajevo ("urban" OR "economy" OR "housing" OR "planning" OR "transport" OR "tourism")'),
        ("env_gov", 'Sarajevo ("air pollution" OR "PM2.5" OR "heating" OR "governance" OR "municipality")'),
    ],
    "novi_pazar": [
        ("urban_econ", '"Novi Pazar" ("economy" OR "urban" OR "textile" OR "trade" OR "population" OR "migration" OR "development" OR "municipality")'),
        ("env_gov", '"Novi Pazar" ("air" OR "environment" OR "education" OR "politics" OR "Serbia")'),
    ],
    "travnik": [
        ("urban_econ", 'Travnik ("Bosnia" OR "Herzegovina" OR "urban" OR "economy" OR "tourism" OR "heritage" OR "municipality" OR "industry")'),
        ("env_gov", 'Travnik ("Bosnia" AND ("air" OR "environment" OR "education" OR "development" OR "Vlasic"))'),
    ],
}


def api_get_json(url: str, dest: Path, city: str, source_name: str):
    r = fetch_url(
        url,
        dest=dest,
        city=city,
        layer="wave4_science_openalex",
        source_name=source_name,
        timeout=35,
        retries=2,
        headers={"Accept": "application/json", "User-Agent": f"SvemirUrbanLab/4.1 (mailto:{MAILTO})"},
    )
    if not r["ok"]:
        print(f"  [FAIL] {source_name}: {r.get('error')}")
        return None
    raw = r.pop("_bytes", b"")
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        print(f"  [JSON ERR] {source_name}: {e}")
        return None


def main():
    institutions_found = []
    seen_inst_ids = set()

    print("=== 1. OpenAlex Institutions (Uloga B: Science IN 5 cities) ===")
    for city_id, iso3, query, expected_city in INSTITUTION_QUERIES:
        params = urllib.parse.urlencode({"search": query, "per-page": 5, "mailto": MAILTO})
        url = f"https://api.openalex.org/institutions?{params}"
        slug = "".join(c if c.isalnum() else "_" for c in query.lower())[:45]
        data = api_get_json(url, OUT_DIR / f"inst_search_{city_id}_{slug}.json", city_id, f"openalex_inst_{slug}")
        time.sleep(0.25)
        if not data or not data.get("results"):
            continue
        # Pick best matching institution by country code
        iso2_map = {"SRB": "RS", "HRV": "HR", "BIH": "BA"}
        target_cc = iso2_map[iso3]
        picked = None
        for cand in data["results"]:
            cc = (cand.get("country_code") or "").upper()
            if cc == target_cc:
                picked = cand
                break
        if not picked:
            picked = data["results"][0]
        oa_id = (picked.get("id") or "").split("/")[-1]
        if not oa_id or oa_id in seen_inst_ids:
            continue
        seen_inst_ids.add(oa_id)
        geo = picked.get("geo") or {}
        rec = {
            "city_id": city_id,
            "country_iso3": iso3,
            "openalex_id": oa_id,
            "ror_id": picked.get("ror"),
            "display_name": picked.get("display_name"),
            "type": picked.get("type"),
            "works_count": picked.get("works_count", 0),
            "cited_by_count": picked.get("cited_by_count", 0),
            "country_code": picked.get("country_code"),
            "geo_city": geo.get("city"),
            "lat": geo.get("latitude"),
            "lon": geo.get("longitude"),
            "homepage_url": picked.get("homepage_url"),
            "counts_by_year": picked.get("counts_by_year", []),
            "summary_stats": picked.get("summary_stats", {}),
            "topics": [
                {"name": t.get("display_name"), "count": t.get("count")}
                for t in (picked.get("topics") or [])[:8]
            ],
        }
        institutions_found.append(rec)
        print(f"  + {city_id:10s} | {oa_id:12s} | {rec['display_name']} | works={rec['works_count']} cited={rec['cited_by_count']}")

    (OUT_DIR / "openalex_institutions_5cities.json").write_text(
        json.dumps(institutions_found, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n=== 2. OpenAlex Works ABOUT 5 cities (Uloga A) ===")
    all_works = []
    seen_work_ids = set()
    for city_id, queries in CITY_TOPICS.items():
        city_count = 0
        for qname, qstr in queries:
            # Sort by cited_by_count desc (seminal) AND recent (2020-2026)
            for mode, extra_filter, sort_by, per_page in [
                ("top_cited", "publication_year:>2014", "cited_by_count:desc", 35),
                ("recent_2022_2026", "publication_year:>2021", "publication_date:desc", 30),
            ]:
                params = urllib.parse.urlencode({
                    "search": qstr,
                    "filter": extra_filter,
                    "sort": sort_by,
                    "per-page": per_page,
                    "select": "id,doi,title,publication_year,publication_date,type,cited_by_count,open_access,primary_location,authorships,concepts,topics,grants,language,abstract_inverted_index",
                    "mailto": MAILTO,
                })
                url = f"https://api.openalex.org/works?{params}"
                dest = OUT_DIR / f"works_about_{city_id}_{qname}_{mode}.json"
                data = api_get_json(url, dest, city_id, f"openalex_about_{city_id}_{qname}_{mode}")
                time.sleep(0.25)
                if not data:
                    continue
                for w in data.get("results", []):
                    wid = (w.get("id") or "").split("/")[-1]
                    if not wid or wid in seen_work_ids:
                        continue
                    title = (w.get("title") or "").strip()
                    if not title:
                        continue
                    seen_work_ids.add(wid)
                    # Check if any author institution is one of our 5-city institutions
                    auth_inst_ids = []
                    for a in (w.get("authorships") or []):
                        for inst in (a.get("institutions") or []):
                            iid = (inst.get("id") or "").split("/")[-1]
                            if iid:
                                auth_inst_ids.append(iid)
                    in_local = any(iid in seen_inst_ids for iid in auth_inst_ids)
                    role = "both" if in_local else "about_city"
                    # Reconstruct short abstract snippet (max 500 chars) if available
                    inv = w.get("abstract_inverted_index") or {}
                    abstract_snip = ""
                    if inv:
                        pos_words = []
                        for word, positions in inv.items():
                            for p in positions:
                                if p < 85:
                                    pos_words.append((p, word))
                        pos_words.sort(key=lambda x: x[0])
                        abstract_snip = " ".join(x[1] for x in pos_words)[:550]
                    oa_url = (w.get("open_access") or {}).get("oa_url")
                    prim_loc = w.get("primary_location") or {}
                    landing = prim_loc.get("landing_page_url") or w.get("doi") or w.get("id")
                    all_works.append({
                        "work_id": wid,
                        "city_id": city_id,
                        "science_role": role,
                        "query_topic": qname,
                        "title": title,
                        "abstract_snippet": abstract_snip,
                        "publication_year": w.get("publication_year"),
                        "publication_date": w.get("publication_date") or f"{w.get('publication_year')}-01-01",
                        "type": w.get("type"),
                        "language": w.get("language") or "en",
                        "doi": w.get("doi"),
                        "landing_url": landing,
                        "open_access_url": oa_url,
                        "cited_by_count": w.get("cited_by_count", 0),
                        "institution_ids": list(dict.fromkeys(auth_inst_ids))[:10],
                        "grants": w.get("grants") or [],
                        "concepts": [
                            {"name": c.get("display_name"), "score": c.get("score")}
                            for c in (w.get("concepts") or [])[:6]
                        ],
                    })
                    city_count += 1
        print(f"  City {city_id:10s}: collected {city_count} unique works ABOUT city")

    print("\n=== 3. OpenAlex EU-Funded / Horizon Grants & Cross-City Collaboration Matrix ===")
    # Query collaboration counts between flagship universities of the 5 cities
    flagships = {}
    for inst in institutions_found:
        if inst["city_id"] not in flagships or inst["works_count"] > flagships[inst["city_id"]]["works_count"]:
            flagships[inst["city_id"]] = inst

    collab_matrix = []
    city_list = list(flagships.keys())
    for i in range(len(city_list)):
        for j in range(i + 1, len(city_list)):
            c1, c2 = city_list[i], city_list[j]
            id1, id2 = flagships[c1]["openalex_id"], flagships[c2]["openalex_id"]
            params = urllib.parse.urlencode({
                "filter": f"authorships.institutions.id:{id1},authorships.institutions.id:{id2},publication_year:>2015",
                "per-page": 1,
                "mailto": MAILTO,
            })
            url = f"https://api.openalex.org/works?{params}"
            data = api_get_json(url, OUT_DIR / f"collab_{c1}_{c2}.json", "common", f"openalex_collab_{c1}_{c2}")
            time.sleep(0.2)
            cnt = (data or {}).get("meta", {}).get("count", 0)
            collab_matrix.append({
                "city_a": c1,
                "inst_a_id": id1,
                "inst_a_name": flagships[c1]["display_name"],
                "city_b": c2,
                "inst_b_id": id2,
                "inst_b_name": flagships[c2]["display_name"],
                "coauthored_works_2016_2026": cnt,
            })
            print(f"  Collab {c1} <-> {c2}: {cnt} joint papers (2016-2026)")

    # Horizon Europe / H2020 funded works by flagship institutions (Funder ID: F4320338335 Horizon Europe, F4320320300 European Commission)
    eu_funded_works = []
    for cid, inst in flagships.items():
        params = urllib.parse.urlencode({
            "filter": f"authorships.institutions.id:{inst['openalex_id']},grants.funder:F4320320300|F4320338335,publication_year:>2019",
            "sort": "cited_by_count:desc",
            "per-page": 25,
            "select": "id,doi,title,publication_year,publication_date,type,cited_by_count,open_access,primary_location,grants,concepts,language",
            "mailto": MAILTO,
        })
        url = f"https://api.openalex.org/works?{params}"
        data = api_get_json(url, OUT_DIR / f"eu_funded_{cid}.json", cid, f"openalex_eufunded_{cid}")
        time.sleep(0.25)
        cnt = (data or {}).get("meta", {}).get("count", 0)
        print(f"  EU/EC-funded works (2020-2026) at {inst['display_name']}: total_meta={cnt}, fetched={len((data or {}).get('results', []))}")
        eu_funded_works.append({
            "city_id": cid,
            "inst_id": inst["openalex_id"],
            "inst_name": inst["display_name"],
            "total_ec_horizon_works_2020_2026": cnt,
            "sample_works": (data or {}).get("results", []),
        })

    (OUT_DIR / "openalex_works_about_5cities.json").write_text(
        json.dumps(all_works, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "openalex_collab_matrix_5cities.json").write_text(
        json.dumps(collab_matrix, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "openalex_eu_funded_5cities.json").write_text(
        json.dumps(eu_funded_works, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nDONE OpenAlex: {len(institutions_found)} institutions, {len(all_works)} works, {len(collab_matrix)} collab pairs.")


if __name__ == "__main__":
    main()
