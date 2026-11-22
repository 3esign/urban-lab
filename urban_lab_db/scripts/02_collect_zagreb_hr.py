import json
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common_net import RAW_DIR, fetch_url


def collect_zagreb_ckan():
    print("[ZAGREB] Querying data.zagreb.hr CKAN API...")
    queries = [
        ("gradske_cetvrti", "gradske četvrti"),
        ("mjesni_odbori", "mjesni odbori"),
        ("proracun", "proračun"),
        ("zg3d", "zg3d"),
        ("ekonomija", "ekonomija"),
        ("komunalna", "komunalna"),
    ]
    all_pkgs = {}
    for tag, q in queries:
        url = f"https://data.zagreb.hr/api/3/action/package_search?q={urllib.parse.quote(q)}&rows=50"
        r = fetch_url(
            url,
            dest=RAW_DIR / "zagreb" / f"ckan_search_{tag}.json",
            city="zagreb",
            layer="ckan_catalog",
            source_name=f"data.zagreb.hr CKAN search: {q}",
        )
        if r["ok"]:
            data = json.loads(r["_bytes"].decode("utf-8"))
            results = data.get("result", {}).get("results", [])
            print(f"  [CKAN {tag}] count={data.get('result',{}).get('count')} returned={len(results)}")
            for p in results:
                all_pkgs[p["name"]] = p
        else:
            print(f"  [CKAN {tag}] FAILED: {r.get('error')}")

    # Download key geospatial and budget resources directly from discovered packages
    downloaded = 0
    for name, pkg in all_pkgs.items():
        title = pkg.get("title", "")
        nl = (name + " " + title).lower()
        is_target = any(k in nl for k in [
            "gradske-cetvrti", "gradske četvrti",
            "mjesni-odbori", "mjesni odbori",
            "proracun", "proračun",
        ])
        if not is_target:
            continue
        for res in pkg.get("resources", []):
            fmt = (res.get("format") or "").upper()
            rurl = res.get("url") or ""
            rname = (res.get("name") or res.get("id") or "res").lower()
            if not rurl.startswith("http"):
                continue
            # Prefer GeoJSON, JSON, ZIP (SHP), CSV, XLSX; limit huge files
            if fmt in ("GEOJSON", "JSON", "CSV", "ZIP", "SHP", "XLSX") or any(ext in rurl.lower() for ext in [".geojson", ".json", ".zip", ".csv", ".xlsx"]):
                if "zg3d" in nl:
                    continue
                safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in f"{name[:45]}_{res.get('id','')[:8]}_{rurl.split('/')[-1][:35]}")
                if not any(safe.lower().endswith(e) for e in [".geojson", ".json", ".zip", ".csv", ".xlsx", ".pdf"]):
                    safe += "." + (fmt.lower() if fmt else "bin")
                dest = RAW_DIR / "zagreb" / safe
                if dest.exists():
                    continue
                rr = fetch_url(rurl, dest=dest, city="zagreb", layer=f"ckan_{fmt.lower() or 'data'}", source_name=f"{title} :: {res.get('name','')}", timeout=60)
                print(f"  [DL] {safe}: ok={rr['ok']} bytes={rr.get('bytes')} err={rr.get('error')}")
                downloaded += 1
                if downloaded >= 25:
                    break
        if downloaded >= 25:
            break


def collect_zagreb_docs_and_eurostat():
    docs = [
        ("zagreb", "boundaries_gc_zip", "Grad Zagreb: Gradske cetvrti (17) rpj_gc.zip",
         "https://data.zagreb.hr/dataset/9c52e229-09bf-4569-8e01-37f338070d02/resource/f2406ad9-34bf-4235-aa24-d71a08ae2863/download/rpj_gc.zip",
         RAW_DIR / "zagreb" / "rpj_gc.zip"),
        ("zagreb", "census_2021_pdf", "Popis 2021 konacni rezultati Grad Zagreb PDF",
         "https://www.zagreb.hr/userdocsimages/arhiva/statistika/popis%202021%20kona%C4%8Dni%20rezultati/Popis%202021._kona%C4%8Dni%20rezultati_Grad%20Zagreb_web.pdf",
         RAW_DIR / "zagreb" / "zagreb_popis_2021_konacni.pdf"),
        ("zagreb", "dzs_cities_pdf", "DZS Statistical Postcards of Cities PDF",
         "https://podaci.dzs.hr/media/qoapefdk/statistical-postcards-of-cities_eng.pdf",
         RAW_DIR / "zagreb" / "dzs_statistical_postcards_cities.pdf"),
        ("zagreb", "dzs_wages_2025", "DZS place / pokazatelji 2025 HTML",
         "https://podaci.dzs.hr/2025/hr/97161",
         RAW_DIR / "zagreb" / "dzs_2025_97161.html"),
        ("zagreb", "dzs_2026_121605", "DZS pokazatelji 2026 HTML",
         "https://podaci.dzs.hr/2026/hr/121605",
         RAW_DIR / "zagreb" / "dzs_2026_121605.html"),
        ("zagreb", "budget_2026_news", "Grad Zagreb Proracun 2026 (3.15 mlrd EUR)",
         "https://www.iusinfo.hr/aktualno/dnevne-novosti/gradska-skupstina-usvojila-proracun-grada-zagreba-od-3-15-milijardi-eura-za-2026-67397-67399",
         RAW_DIR / "zagreb" / "zagreb_proracun_2026_info.html"),
        ("common", "eurostat_urb_cpop1", "Eurostat Urban Audit Population (Zagreb HR001C + Beograd RS001C)",
         "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/urb_cpop1?format=JSON&lang=EN&cities=HR001C&cities=RS001C",
         RAW_DIR / "common" / "eurostat_urb_cpop1_zg_bg.json"),
        ("common", "eurostat_urb_clma", "Eurostat Urban Audit Labour Market (Zagreb HR001C + Beograd RS001C)",
         "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/urb_clma?format=JSON&lang=EN&cities=HR001C&cities=RS001C",
         RAW_DIR / "common" / "eurostat_urb_clma_zg_bg.json"),
        ("common", "eurostat_urb_clivcon", "Eurostat Urban Audit Living Conditions (Zagreb HR001C + Beograd RS001C)",
         "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/urb_clivcon?format=JSON&lang=EN&cities=HR001C&cities=RS001C",
         RAW_DIR / "common" / "eurostat_urb_clivcon_zg_bg.json"),
        ("common", "data_gov_hr_sudreg", "data.gov.hr Sudski registar CKAN metadata",
         "https://data.gov.hr/ckan/api/3/action/package_show?id=sudski-registar",
         RAW_DIR / "zagreb" / "data_gov_hr_sudreg_meta.json"),
    ]
    for city, layer, name, url, dest in docs:
        r = fetch_url(url, dest=dest, city=city, layer=layer, source_name=name, timeout=60)
        print(f"[ZG-DOC] {city}/{layer}: ok={r['ok']} bytes={r.get('bytes')} err={r.get('error')}")


if __name__ == "__main__":
    collect_zagreb_ckan()
    collect_zagreb_docs_and_eurostat()
