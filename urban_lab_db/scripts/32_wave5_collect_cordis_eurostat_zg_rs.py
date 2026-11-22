import json
import time
import urllib.parse
from pathlib import Path
from common_net import BASE_DIR, fetch_url, append_manifest, sha256_bytes

OUT_DIR = BASE_DIR / "raw" / "wave5"
(OUT_DIR / "cordis").mkdir(parents=True, exist_ok=True)
(OUT_DIR / "eurostat").mkdir(parents=True, exist_ok=True)
(OUT_DIR / "zagreb_market").mkdir(parents=True, exist_ok=True)
(OUT_DIR / "serbia_permits").mkdir(parents=True, exist_ok=True)


def collect_cordis():
    print("=== 1. Collecting EU CORDIS Horizon Projects for 5 Cities ===", flush=True)
    city_queries = [
        ("beograd", "('Belgrade' OR 'Beograd')"),
        ("zagreb", "('Zagreb')"),
        ("sarajevo", "('Sarajevo')"),
        ("novi_pazar", "('Novi Pazar')"),
        ("travnik", "('Travnik' OR 'Central Bosnia')"),
    ]
    all_projects = []
    seen = set()
    for cid, qterm in city_queries:
        q = f"contenttype='project' AND {qterm}"
        url = f"https://cordis.europa.eu/search/en?q={urllib.parse.quote(q)}&p=1&num=40&srt=Relevance:decreasing&format=json"
        rec = fetch_url(url, dest=OUT_DIR / "cordis" / f"cordis_{cid}.json", city=cid, layer="wave5_science_eu", source_name="eu_cordis_api", timeout=30)
        if not rec["ok"]:
            print(f"  CORDIS {cid} ERR: {rec.get('error')}", flush=True)
            continue
        try:
            d = json.loads(rec["_bytes"].decode("utf-8", errors="replace"))
            hits = (d.get("payload") or {}).get("hits", {}).get("hit") or []
            if isinstance(hits, dict):
                hits = [hits]
            cnt = 0
            for h in hits:
                proj = h.get("project") or {}
                pid = proj.get("id") or proj.get("rcn")
                if not pid:
                    continue
                key = f"{cid}:{pid}"
                if key in seen:
                    continue
                seen.add(key)
                all_projects.append({
                    "city_id": cid,
                    "project_id": str(pid),
                    "rcn": proj.get("rcn"),
                    "acronym": proj.get("acronym"),
                    "title": proj.get("title"),
                    "objective": (proj.get("objective") or "")[:600],
                    "status": proj.get("status"),
                    "framework": proj.get("frameworkProgramme"),
                    "start_date": proj.get("startDate"),
                    "end_date": proj.get("endDate"),
                    "total_cost_eur": proj.get("totalCost"),
                    "ec_max_contribution_eur": proj.get("ecMaxContribution"),
                    "url": f"https://cordis.europa.eu/project/id/{pid}",
                })
                cnt += 1
            print(f"  CORDIS {cid}: {cnt} EU projects", flush=True)
        except Exception as e:
            print(f"  CORDIS {cid} parse err: {e}", flush=True)
        time.sleep(0.3)

    out_p = OUT_DIR / "cordis" / "cordis_5cities_consolidated.json"
    b = json.dumps(all_projects, ensure_ascii=False, indent=2).encode("utf-8")
    out_p.write_bytes(b)
    print(f"  Total CORDIS EU projects saved: {len(all_projects)}", flush=True)


def collect_eurostat_nuts3():
    print("\n=== 2. Collecting Eurostat NUTS-3 GDP & Population (BG, ZG, NP-Raska + L-Rings) ===", flush=True)
    # HR050=Grad Zagreb, HR042=Zagrebacka zupanija, HR043=Krapinsko-zagorska, HR044=Varazdinska, HR04D=Karlovacka, HR04E=Sisacko-moslavacka
    # RS110=Beogradska oblast, RS122=Juznobanatska (Pancevo), RS127=Sremska, RS215=Raska (Novi Pazar!), RS217=Zlatiborska (Sjenica/Uzice)
    geos = ["HR050", "HR042", "HR043", "HR04D", "HR04E", "RS110", "RS122", "RS127", "RS215", "RS217"]
    geo_q = "&".join(f"geo={g}" for g in geos)
    urls = [
        ("nama_10r_3gdp_mio_eur", f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nama_10r_3gdp?{geo_q}&sinceTimePeriod=2018&unit=MIO_EUR"),
        ("nama_10r_3gdp_pps_hab", f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nama_10r_3gdp?{geo_q}&sinceTimePeriod=2018&unit=PPS_EU27_2020_HAB"),
        ("demo_r_pjanaggr3", f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/demo_r_pjanaggr3?{geo_q}&sinceTimePeriod=2018&sex=T&age=TOTAL"),
    ]
    for slug, u in urls:
        rec = fetch_url(u, dest=OUT_DIR / "eurostat" / f"eurostat_{slug}.json", city="common", layer="wave5_macro_nuts3", source_name=f"eurostat_{slug}", timeout=30)
        print(f"  Eurostat {slug}: ok={rec['ok']} bytes={rec.get('bytes')}", flush=True)


def collect_zagreb_market_and_cadastre():
    print("\n=== 3. Collecting data.zagreb.hr Real Estate Transactions, Rents & Cadastral Municipalities ===", flush=True)
    files = [
        ("ukupan_promet_nekretnina_2024.csv", "https://data.zagreb.hr/dataset/6b9455e8-ac67-4dbc-b1ec-58266a9f7495/resource/1fdc8c52-326a-4d30-b494-12681ab07686/download/ukupan-promet-nekretnina-2024.csv"),
        ("ukupan_promet_nekretnina_2023.csv", "https://data.zagreb.hr/dataset/6b9455e8-ac67-4dbc-b1ec-58266a9f7495/resource/0fc8f986-151f-422e-a385-c72c348c14ae/download/ukupan-promet-nekretnina-2023.csv"),
        ("ukupan_promet_nekretnina_2022.csv", "https://data.zagreb.hr/dataset/6b9455e8-ac67-4dbc-b1ec-58266a9f7495/resource/b29f751e-4eb4-41e0-b1cb-48d300318442/download/ukupan-promet-nekretnina-2022.csv"),
        ("ugovori_najam_stanova_2024.csv", "https://data.zagreb.hr/dataset/cf3efb54-bec8-4c5c-a6e0-72aac0dc756d/resource/71ec8a99-1960-4729-8b9d-6bba771202e1/download/ugovori-o-najmu-stanova_2024.csv"),
        ("ugovori_najam_stanova_2023.csv", "https://data.zagreb.hr/dataset/cf3efb54-bec8-4c5c-a6e0-72aac0dc756d/resource/13c5c5d0-abbb-4322-a30d-dd5c6afff9db/download/ugovori-o-najmu-stanova-2023.csv"),
        ("dkp_k_opcina_zagreb.csv", "https://data.zagreb.hr/dataset/8b8bc69a-d52e-4f1e-806e-c719b8e3d11a/resource/34923e9f-ed35-4750-85e7-5fafa78af59e/download/dkp_k_opcina.csv"),
    ]
    for fn, u in files:
        rec = fetch_url(u, dest=OUT_DIR / "zagreb_market" / fn, city="zagreb", layer="wave5_zagreb_market", source_name=f"data_zagreb_{fn[:-4]}", timeout=35)
        print(f"  Zagreb {fn}: ok={rec['ok']} bytes={rec.get('bytes')}", flush=True)


def collect_serbia_rzs_permits():
    print("\n=== 4. Attempting RZS Serbia Building Permits CSV (050202IND01 & 050204IND01) ===", flush=True)
    for code, slug in [("050202IND01", "rzs_permits_buildings"), ("050204IND01", "rzs_permits_dwellings")]:
        u = f"https://opendata.stat.gov.rs/data/WcfJsonRestService.Service1.svc/dataset/{code}/1/csv"
        rec = fetch_url(u, dest=OUT_DIR / "serbia_permits" / f"{slug}.csv", city="common", layer="wave5_serbia_permits", source_name=slug, timeout=50, retries=1)
        print(f"  RZS {slug}: ok={rec['ok']} bytes={rec.get('bytes')} err={rec.get('error')}", flush=True)


if __name__ == "__main__":
    collect_cordis()
    collect_eurostat_nuts3()
    collect_zagreb_market_and_cadastre()
    collect_serbia_rzs_permits()
