import json
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_net import RAW_DIR, fetch_url

OUT_DIR = RAW_DIR / "wave4" / "science"
MAILTO = "urbanlab-research@svemir.local"

existing_path = OUT_DIR / "openalex_works_about_5cities.json"
all_works = json.loads(existing_path.read_text(encoding="utf-8")) if existing_path.exists() else []
seen_ids = {w["work_id"] for w in all_works}
inst_path = OUT_DIR / "openalex_institutions_5cities.json"
seen_inst_ids = {x["openalex_id"] for x in json.loads(inst_path.read_text(encoding="utf-8"))} if inst_path.exists() else set()

# High-precision title.search filters per city (with urban/economic/environmental/spatial focus)
CITY_TITLE_FILTERS = [
    ("beograd", "title.search:Belgrade,publication_year:>2015", "Belgrade urban OR economy OR housing OR air OR transport OR planning"),
    ("beograd", "title.search:Belgrade,publication_year:>2018", "Belgrade population OR real estate OR municipality OR energy"),
    ("zagreb", "title.search:Zagreb,publication_year:>2015", "Zagreb urban OR economy OR housing OR earthquake OR transport OR tourism"),
    ("zagreb", "title.search:Zagreb,publication_year:>2018", "Zagreb planning OR air OR municipality OR energy OR demography"),
    ("sarajevo", "title.search:Sarajevo,publication_year:>2015", "Sarajevo urban OR economy OR air OR pollution OR housing OR planning"),
    ("sarajevo", "title.search:Sarajevo,publication_year:>2018", "Sarajevo tourism OR transport OR heating OR governance OR demography"),
    ("novi_pazar", 'title.search:"Novi Pazar",publication_year:>2010', ""),
    ("travnik", "title.search:Travnik,publication_year:>2010", ""),
]

added_by_city = {}
for city_id, flt, srch in CITY_TITLE_FILTERS:
    for sort_by, per_page in [("cited_by_count:desc", 35), ("publication_date:desc", 25)]:
        params_dict = {"filter": flt, "sort": sort_by, "per-page": per_page, "mailto": MAILTO}
        if srch:
            params_dict["search"] = srch
        url = f"https://api.openalex.org/works?{urllib.parse.urlencode(params_dict)}"
        tag = f"title_{city_id}_{sort_by.split(':')[0]}_{len(srch)}"
        r = fetch_url(url, dest=OUT_DIR / f"{tag}.json", city=city_id, layer="wave4_science_openalex", source_name=tag, timeout=35, retries=2)
        time.sleep(0.25)
        if not r["ok"]:
            print(f"  [FAIL] {tag}: {r.get('error')}")
            continue
        data = json.loads(r.pop("_bytes", b"").decode("utf-8", errors="replace"))
        for w in data.get("results", []):
            wid = (w.get("id") or "").split("/")[-1]
            title = (w.get("title") or "").strip()
            if not wid or not title or wid in seen_ids:
                continue
            seen_ids.add(wid)
            auth_inst_ids = [
                (inst.get("id") or "").split("/")[-1]
                for a in (w.get("authorships") or [])
                for inst in (a.get("institutions") or [])
                if inst.get("id")
            ]
            role = "both" if any(i in seen_inst_ids for i in auth_inst_ids) else "about_city"
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
                "query_topic": "about_city_title",
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
            added_by_city[city_id] = added_by_city.get(city_id, 0) + 1

existing_path.write_text(json.dumps(all_works, ensure_ascii=False, indent=2), encoding="utf-8")
by_city_total = {}
for w in all_works:
    by_city_total[w["city_id"]] = by_city_total.get(w["city_id"], 0) + 1
print(f"DONE Deep OpenAlex ABOUT: newly_added={added_by_city} | total_all_works={len(all_works)} | by_city={by_city_total}")
