from _paths import rel  # putanje u manifestu su relativne na koren repozitorijuma
import json
import sys
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common_net import BASE_DIR, RAW_DIR, fetch_url, append_manifest, sha256_file

# RZS municipality codes for 17 municipalities of City of Belgrade + Novi Pazar
BEOGRAD_OPSTINE = {
    "70092": "Barajevo",
    "70106": "Voždovac",
    "70114": "Vračar",
    "70122": "Grocka",
    "70149": "Zvezdara",
    "70157": "Zemun",
    "70165": "Lazarevac",
    "70173": "Mladenovac",
    "70181": "Novi Beograd",
    "70190": "Obrenovac",
    "70203": "Palilula",
    "70211": "Rakovica",
    "70220": "Savski venac",
    "70238": "Sopot",
    "70246": "Stari grad",
    "70254": "Čukarica",
    "71293": "Surčin",
}
NOVI_PAZAR_OPSTINA = "70874"


def collect_documents():
    docs = [
        ("beograd", "property_tax_zones", "Beograd poreske zone i cene m2 2026 (Sl. list 82/2025)",
         "http://demo.paragraf.rs/demo/combined/Old/t/t2025_10/BG_082_2025_002.htm",
         RAW_DIR / "beograd" / "beograd_poreske_zone_cene_2026.htm"),
        ("beograd", "budget", "Budzet Grada Beograda 2026 (Sl. list 6/2026)",
         "http://demo.paragraf.rs/demo/combined/Old/t/t2026_03/BG_006_2026_001.htm",
         RAW_DIR / "beograd" / "beograd_budzet_2026.htm"),
        ("beograd", "property_tax_zone_boundaries_decision", "Odluka o odredjivanju zona na teritoriji Grada Beograda",
         "http://demo.paragraf.rs/demo/combined/Old/t/t2022_11/BG_096_2022_005.htm",
         RAW_DIR / "beograd" / "beograd_odluka_zone_granice.htm"),
        ("novi_pazar", "property_tax_zones", "Novi Pazar poreske zone i cene m2 2026 (Sl. list 14/2025)",
         "http://demo.paragraf.rs/demo/combined/Old/t/t2026_01/NP_014_2025_002.htm",
         RAW_DIR / "novi_pazar" / "novi_pazar_poreske_zone_cene_2026.htm"),
        ("novi_pazar", "property_tax_zone_boundaries_decision", "Odluka o odredjivanju zona Novi Pazar (Sl. list 9/2021)",
         "http://demo.paragraf.rs/demo/combined/Old/t/t2021_10/NP_009_2021_002.htm",
         RAW_DIR / "novi_pazar" / "novi_pazar_odluka_zone_granice.htm"),
        ("novi_pazar", "budget", "Budzet Grada Novog Pazara 2026 potpisan PDF",
         "https://www.novipazar.rs/images/dokumenti/budzet/2026/Budzet%20za%202026%20-%20potpisan.pdf",
         RAW_DIR / "novi_pazar" / "novi_pazar_budzet_2026.pdf"),
        ("novi_pazar", "budget_guide", "Gradjanski vodic kroz budzet Novog Pazara 2026 PDF",
         "https://www.novipazar.rs/images/dokumenti/budzet/2026/Gradjanski_vodic_kroz_nacrt_budzeta_za_2026.pdf",
         RAW_DIR / "novi_pazar" / "novi_pazar_gradjanski_vodic_2026.pdf"),
        ("common", "rzs_municipalities_stats", "RZS Opstine i regioni u RS 2025 PDF",
         "https://publikacije.stat.gov.rs/G2025/pdf/G202526001.pdf",
         RAW_DIR / "common" / "rzs_opstine_i_regioni_2025.pdf"),
        ("common", "rzs_wages_html", "RZS Prosecne zarade po opstinama HTML (2026)",
         "https://publikacije.stat.gov.rs/G2026/HtmlL/G20261262.html",
         RAW_DIR / "common" / "rzs_zarade_2026_1262.html"),
        ("common", "rzs_prices_newbuild_html", "RZS Cene stanova novogradnje HTML (2026)",
         "https://publikacije.stat.gov.rs/G2026/HtmlL/G20261084.html",
         RAW_DIR / "common" / "rzs_cene_novogradnje_2026_1084.html"),
    ]
    for city, layer, name, url, dest in docs:
        r = fetch_url(url, dest=dest, city=city, layer=layer, source_name=name, timeout=60)
        print(f"[DOC] {city}/{layer}: ok={r['ok']} bytes={r.get('bytes')} err={r.get('error')}")


def collect_apr_live():
    print("[APR] Fetching live APR Open Data (companies + financial-statements)...")
    r_comp = fetch_url(
        "https://openapi.apr.gov.rs/api/opendata/companies",
        dest=None,
        city="common",
        layer="companies_raw_stream",
        source_name="APR Open Data Companies (Srbija full)",
        timeout=90,
    )
    if not r_comp["ok"]:
        print(f"[APR] companies FAILED: {r_comp.get('error')}")
        return

    r_fi = fetch_url(
        "https://openapi.apr.gov.rs/api/opendata/companies/financial-statements",
        dest=None,
        city="common",
        layer="companies_fi_raw_stream",
        source_name="APR Open Data Financial Statements (Srbija full)",
        timeout=90,
    )
    fi_map = {}
    if r_fi["ok"]:
        fi_data = json.loads(r_fi["_bytes"].decode("utf-8"))
        # handle list or dict wrapper
        fi_rows = fi_data if isinstance(fi_data, list) else fi_data.get("data", fi_data.get("items", []))
        for row in fi_rows:
            mb = str(row.get("MaticniBroj") or row.get("maticniBroj") or "").strip()
            if mb:
                fi_map[mb] = row
        print(f"[APR] Loaded {len(fi_map)} financial statement rows")
    else:
        print(f"[APR] financial-statements FAILED: {r_fi.get('error')}")

    comp_data = json.loads(r_comp["_bytes"].decode("utf-8"))
    comp_rows = comp_data if isinstance(comp_data, list) else comp_data.get("data", comp_data.get("items", []))
    print(f"[APR] Total Serbia companies: {len(comp_rows)}")

    # Detect exact field names from first record
    sample = comp_rows[0] if comp_rows else {}
    print("[APR] Sample company keys:", list(sample.keys())[:20])

    # Check municipality codes for Belgrade by name match too, to be 100% sure none missed
    bg_codes = set(BEOGRAD_OPSTINE.keys())
    found_muni = {}
    bg_rows = []
    np_rows = []
    all_serbia_nace = Counter()
    all_serbia_total = 0

    for row in comp_rows:
        m_code = str(row.get("SifraOpstine") or row.get("sifraOpstine") or "").strip()
        m_name = str(row.get("Opstina") or row.get("NazivOpstine") or row.get("opstina") or "").strip()
        nace = str(row.get("SifraDelatnosti") or row.get("sifraDelatnosti") or "").strip()
        mb = str(row.get("MaticniBroj") or row.get("maticniBroj") or "").strip()

        if m_code and m_name:
            found_muni[m_code] = m_name
        all_serbia_total += 1
        if nace:
            all_serbia_nace[nace[:2]] += 1

        if m_code in bg_codes or ("београд" in m_name.lower() or "beograd" in m_name.lower() or "сурчин" in m_name.lower() or "земун" in m_name.lower() or "врачар" in m_name.lower() or "вождовац" in m_name.lower() or "звездара" in m_name.lower() or "палилула" in m_name.lower() and m_code.startswith("70")):
            if m_code in bg_codes or m_code == "71293":
                merged = dict(row)
                if mb in fi_map:
                    merged["fi"] = fi_map[mb]
                bg_rows.append(merged)
        elif m_code == NOVI_PAZAR_OPSTINA:
            merged = dict(row)
            if mb in fi_map:
                merged["fi"] = fi_map[mb]
            np_rows.append(merged)

    bg_path = RAW_DIR / "beograd" / "apr_beograd_companies.jsonl"
    with open(bg_path, "w", encoding="utf-8") as f:
        for r in bg_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    np_path = RAW_DIR / "novi_pazar" / "apr_novi_pazar_companies.jsonl"
    with open(np_path, "w", encoding="utf-8") as f:
        for r in np_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Save Serbia national NACE-2 baseline (needed for Location Quotient!)
    nat_path = RAW_DIR / "common" / "apr_serbia_nace2_baseline.json"
    nat_obj = {
        "total_companies_serbia": all_serbia_total,
        "total_fi_serbia": len(fi_map),
        "nace2_counts": dict(all_serbia_nace.most_common()),
        "beograd_count": len(bg_rows),
        "novi_pazar_count": len(np_rows),
        "belgrade_muni_codes_seen": {k: found_muni.get(k, BEOGRAD_OPSTINE[k]) for k in sorted(bg_codes)},
    }
    nat_path.write_text(json.dumps(nat_obj, ensure_ascii=False, indent=2), encoding="utf-8")

    for city, p, cnt in [("beograd", bg_path, len(bg_rows)), ("novi_pazar", np_path, len(np_rows))]:
        append_manifest({
            "ok": True,
            "city": city,
            "layer": "companies_apr_rgfi",
            "source_name": f"APR Open Data Companies + RGFI ({city}, {cnt} rows)",
            "url": "https://openapi.apr.gov.rs/api/opendata/companies",
            "http_status": 200,
            "bytes": p.stat().st_size,
            "sha256": sha256_file(p),
            "local_path": rel(p),
        })
    print(f"[APR] Saved Beograd={len(bg_rows)} companies, Novi Pazar={len(np_rows)} companies")


def collect_rzs_gis():
    print("[RZS-GIS] Inspecting https://gis.stat.gov.rs/server/rest/services ...")
    r = fetch_url(
        "https://gis.stat.gov.rs/server/rest/services?f=json",
        dest=RAW_DIR / "common" / "rzs_gis_services_root.json",
        city="common",
        layer="gis_catalog",
        source_name="RZS ArcGIS REST Services root",
    )
    if not r["ok"]:
        print("[RZS-GIS] root failed:", r.get("error"))
        return
    root = json.loads(r["_bytes"].decode("utf-8"))
    print("[RZS-GIS] folders:", root.get("folders"), "services:", len(root.get("services", [])))

    # Inspect Hosted folder too
    for folder in root.get("folders", []):
        rf = fetch_url(
            f"https://gis.stat.gov.rs/server/rest/services/{urllib.parse.quote(folder)}?f=json",
            dest=RAW_DIR / "common" / f"rzs_gis_folder_{folder}.json",
            city="common",
            layer="gis_catalog",
            source_name=f"RZS ArcGIS REST folder {folder}",
        )
        if rf["ok"]:
            fdata = json.loads(rf["_bytes"].decode("utf-8"))
            svcs = [s.get("name") for s in fdata.get("services", [])]
            print(f"[RZS-GIS] folder {folder}: {len(svcs)} services -> {svcs[:15]}")


if __name__ == "__main__":
    collect_documents()
    collect_apr_live()
    collect_rzs_gis()
