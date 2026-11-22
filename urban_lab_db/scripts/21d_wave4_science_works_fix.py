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

# Load already collected institutions
inst_path = OUT_DIR / "openalex_institutions_5cities.json"
institutions_found = json.loads(inst_path.read_text(encoding="utf-8")) if inst_path.exists() else []
seen_inst_ids = {x["openalex_id"] for x in institutions_found}

# Clean OpenAlex searches (no parentheses/unsupported fields)
CITY_QUERIES = {
    "beograd": [
        ("urban_econ", "Belgrade urban economy housing real estate"),
        ("env_transport", "Belgrade air pollution transport urban planning"),
    ],
    "zagreb": [
        ("urban_econ", "Zagreb urban economy housing real estate"),
        ("env_transport", "Zagreb earthquake tourism urban planning transport"),
    ],
    "sarajevo": [
        ("urban_econ", "Sarajevo urban economy housing planning tourism"),
        ("env_transport", "Sarajevo air pollution PM2.5 heating governance"),
    ],
    "novi_pazar": [
        ("urban_econ", "Novi Pazar economy urban textile population migration"),
        ("env_transport", "Novi Pazar Serbia development environment education"),
    ],
    "travnik": [
        ("urban_econ", "Travnik Bosnia economy urban tourism heritage"),
        ("env_transport", "Travnik Bosnia environment municipality development"),
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
    all_works = []
    seen_work_ids = set()

    print("=== 1. OpenAlex Works ABOUT 5 cities (Uloga A) ===")
    for city_id, queries in CITY_QUERIES.items():
        city_count = 0
        for qname, qstr in queries:
            for mode, extra_filter, sort_by, per_page in [
                ("top_cited", "publication_year:>2014", "cited_by_count:desc", 35),
                ("recent", "publication_year:>2021", "publication_date:desc", 30),
            ]:
                params = urllib.parse.urlencode({
                    "search": qstr,
                    "filter": extra_filter,
                    "sort": sort_by,
                    "per-page": per_page,
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
                    # Basic city relevance filter for smaller cities so noise doesn't enter
                    check_txt = (title + " " + " ".join((w.get("abstract_inverted_index") or {}).keys())).lower()
                    must_tokens = {
                        "beograd": ["belgrade", "beograd"],
                        "zagreb": ["zagreb"],
                        "sarajevo": ["sarajevo"],
                        "novi_pazar": ["novi pazar", "pazar"],
                        "travnik": ["travnik"],
                    }[city_id]
                    if not any(tok in check_txt for tok in must_tokens):
                        continue
                    seen_work_ids.add(wid)
                    auth_inst_ids = []
                    for a in (w.get("authorships") or []):
                        for inst in (a.get("institutions") or []):
                            iid = (inst.get("id") or "").split("/")[-1]
                            if iid:
                                auth_inst_ids.append(iid)
                    in_local = any(iid in seen_inst_ids for iid in auth_inst_ids)
                    role = "both" if in_local else "about_city"
                    inv = w.get("abstract_inverted_index") or {}
                    abstract_snip = ""
                    if inv:
                        pos_words = [(p, wd) for wd, poss in inv.items() for p in poss if p < 85]
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
                        "concepts": [
                            {"name": c.get("display_name"), "score": c.get("score")}
                            for c in (w.get("concepts") or [])[:6]
                        ],
                    })
                    city_count += 1
        print(f"  City {city_id:10s}: collected {city_count} verified relevant works ABOUT city")

    print("\n=== 2. OpenAlex Top Local R&D Works IN 5 cities (Uloga B - Economics/Urban/Env) ===")
    flagships = {}
    for inst in institutions_found:
        if inst["city_id"] not in flagships or inst["works_count"] > flagships[inst["city_id"]]["works_count"]:
            flagships[inst["city_id"]] = inst

    in_city_added = 0
    for cid, inst in flagships.items():
        params = urllib.parse.urlencode({
            "search": "economy OR urban OR environment OR energy OR transport OR finance",
            "filter": f"authorships.institutions.id:{inst['openalex_id']},publication_year:>2019",
            "sort": "cited_by_count:desc",
            "per-page": 25,
            "mailto": MAILTO,
        })
        url = f"https://api.openalex.org/works?{params}"
        data = api_get_json(url, OUT_DIR / f"works_in_{cid}.json", cid, f"openalex_in_{cid}")
        time.sleep(0.25)
        cnt_local = 0
        for w in (data or {}).get("results", []):
            wid = (w.get("id") or "").split("/")[-1]
            if not wid or wid in seen_work_ids:
                continue
            title = (w.get("title") or "").strip()
            if not title:
                continue
            seen_work_ids.add(wid)
            oa_url = (w.get("open_access") or {}).get("oa_url")
            prim_loc = w.get("primary_location") or {}
            landing = prim_loc.get("landing_page_url") or w.get("doi") or w.get("id")
            all_works.append({
                "work_id": wid,
                "city_id": cid,
                "science_role": "in_city_rd",
                "query_topic": "local_rd_flagship",
                "title": title,
                "abstract_snippet": "",
                "publication_year": w.get("publication_year"),
                "publication_date": w.get("publication_date") or f"{w.get('publication_year')}-01-01",
                "type": w.get("type"),
                "language": w.get("language") or "en",
                "doi": w.get("doi"),
                "landing_url": landing,
                "open_access_url": oa_url,
                "cited_by_count": w.get("cited_by_count", 0),
                "institution_ids": [inst["openalex_id"]],
                "concepts": [
                    {"name": c.get("display_name"), "score": c.get("score")}
                    for c in (w.get("concepts") or [])[:6]
                ],
            })
            cnt_local += 1
            in_city_added += 1
        print(f"  Flagship IN {cid:10s} ({inst['display_name']}): +{cnt_local} R&D works")

    (OUT_DIR / "openalex_works_about_5cities.json").write_text(
        json.dumps(all_works, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nDONE OpenAlex Works Fix: total={len(all_works)} unique verified works (in_city_rd added={in_city_added})")


if __name__ == "__main__":
    main()
