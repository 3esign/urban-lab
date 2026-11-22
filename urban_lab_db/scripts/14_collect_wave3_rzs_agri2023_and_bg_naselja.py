from _paths import rel  # putanje u manifestu su relativne na koren repozitorijuma
import json, os, re, sys, urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common_net import RAW_DIR, fetch_url, append_manifest, sha256_file

OUT = RAW_DIR / "wave3"
AGRI_OUT = OUT / "rzs_agri2023"
AGRI_OUT.mkdir(parents=True, exist_ok=True)

BEOGRAD_OPSTINE = {
    "70092": "Barajevo", "70106": "Voždovac", "70114": "Vračar", "70122": "Grocka",
    "70149": "Zvezdara", "70157": "Zemun", "70165": "Lazarevac", "70173": "Mladenovac",
    "70181": "Novi Beograd", "70190": "Obrenovac", "70203": "Palilula", "70211": "Rakovica",
    "70220": "Savski venac", "70238": "Sopot", "70246": "Stari grad", "70254": "Čukarica",
    "71293": "Surčin",
}

def query_arcgis_geojson(base_url, where="1=1", out_fields="*", max_pages=10):
    all_features = []
    offset = 0
    page_size = 500
    for _ in range(max_pages):
        params = {
            "where": where, "outFields": out_fields, "outSR": "4326",
            "f": "geojson", "resultOffset": str(offset), "resultRecordCount": str(page_size),
        }
        url = f"{base_url}/query?{urllib.parse.urlencode(params)}"
        r = fetch_url(url, save_manifest=False, timeout=60)
        if not r["ok"]:
            print(f"  [ArcGIS FAIL] {r.get('error')}")
            break
        obj = json.loads(r["_bytes"].decode("utf-8"))
        feats = obj.get("features", [])
        all_features.extend(feats)
        if len(feats) < page_size:
            break
        offset += page_size
    return {"type": "FeatureCollection", "features": all_features}

def collect_rzs_agri2023():
    print("=== 1. RZS POPIS POLJOPRIVREDE 2023 (tabele-pp, bazapodatakapp, brosure) ===", flush=True)
    pages = [
        ("tabele_pp", "https://popispoljoprivrede.stat.gov.rs/rezultati24/tabele-pp/"),
        ("prvi_rezultati", "https://popispoljoprivrede.stat.gov.rs/rezultati24/prvi-rezultati-1/"),
        ("baza_pp", "https://popispoljoprivrede.stat.gov.rs/rezultati24/bazapodatakapp/"),
        ("brosure_pp", "https://popispoljoprivrede.stat.gov.rs/rezultati24/brosure/"),
    ]
    all_file_links = []
    for tag, url in pages:
        dest = AGRI_OUT / f"page_{tag}.html"
        r = fetch_url(url, dest=dest, city="common", layer="rzs_agri2023_index", source_name=f"RZS Popis poljoprivrede 2023 page: {tag}", timeout=35)
        print(f"  Page {tag:16s}: ok={r['ok']} bytes={r.get('bytes',0):,}", flush=True)
        if r["ok"]:
            html = dest.read_text(encoding="utf-8", errors="replace")
            links = re.findall(r'href=["\']([^"\']+\.(?:xlsx?|csv|zip|pdf))["\']', html, flags=re.I)
            data_links = re.findall(r'href=["\']([^"\']*data\.stat\.gov\.rs[^"\']*)["\']', html, flags=re.I)
            print(f"    -> {len(links)} file links, {len(data_links)} data.stat links", flush=True)
            for l in links:
                full = urllib.parse.urljoin(url, l)
                all_file_links.append((tag, full))
            for dl in data_links[:5]:
                print(f"    data.stat: {dl}", flush=True)

    # Deduplicate and download all Excel/CSV files (and key summary PDFs)
    seen = set()
    excel_links = []
    pdf_links = []
    for tag, full in all_file_links:
        if full in seen: continue
        seen.add(full)
        low = full.lower()
        if low.endswith((".xlsx", ".xls", ".csv", ".zip")):
            excel_links.append((tag, full))
        elif low.endswith(".pdf"):
            pdf_links.append((tag, full))

    print(f"  Unique Excel/CSV/ZIP: {len(excel_links)} | Unique PDF: {len(pdf_links)}", flush=True)
    for i, (tag, full) in enumerate(excel_links[:25]):
        fn = re.sub(r'[^a-zA-Z0-9._-]+', '_', os.path.basename(urllib.parse.urlparse(full).path))
        dest = AGRI_OUT / f"pp2023_{i+1:02d}_{fn}"
        res = fetch_url(full, dest=dest, city="common", layer="rzs_agri2023_tables", source_name=f"RZS Popis poljoprivrede 2023 ({tag}): {fn}", timeout=45)
        print(f"    [DL {i+1:02d}] {fn[:52]:52s} ok={res['ok']} {res.get('bytes',0):>9,} B", flush=True)

    if len(excel_links) == 0 and pdf_links:
        for i, (tag, full) in enumerate(pdf_links[:8]):
            fn = re.sub(r'[^a-zA-Z0-9._-]+', '_', os.path.basename(urllib.parse.urlparse(full).path))
            dest = AGRI_OUT / f"pp2023_pdf_{i+1:02d}_{fn}"
            res = fetch_url(full, dest=dest, city="common", layer="rzs_agri2023_pdf", source_name=f"RZS Popis poljoprivrede 2023 PDF ({tag}): {fn}", timeout=45)
            print(f"    [PDF {i+1:02d}] {fn[:52]:52s} ok={res['ok']} {res.get('bytes',0):>9,} B", flush=True)

    # Also check RZS ArcGIS Hosted folder for any Popis poljoprivrede 2023 services!
    hosted_p = RAW_DIR / "common" / "rzs_gis_folder_Hosted.json"
    if hosted_p.exists():
        h = json.loads(hosted_p.read_text(encoding="utf-8", errors="replace"))
        svcs = [s.get("name", "") for s in h.get("services", [])]
        agri_svcs = [s for s in svcs if any(k in s.lower() for k in ["polj", "agri", "pp23", "pp_23", "2023", "gazd", "naselj"])]
        print("  RZS ArcGIS Hosted matching services:", agri_svcs[:25], flush=True)

    # Check data.stat.gov.rs OpenData API for Popis poljoprivrede 2023 (SDMX / opendata.stat.gov.rs)
    r_od = fetch_url("https://opendata.stat.gov.rs/data/Wcf/AsyncInterface.svc/GetIndList", save_manifest=False, timeout=25)
    print(f"  opendata.stat.gov.rs GetIndList: ok={r_od['ok']} bytes={r_od.get('bytes',0)}", flush=True)


def collect_beograd_naselja_and_rzs_gis():
    print("\n=== 2. RZS ARCGIS: BEOGRAD ALL SETTLEMENTS (NASELJA POPIS 2022) ===", flush=True)
    # Check layer index of Indikatori_popis_stanivnistva_2022_1 to find settlements layer (same source as novi_pazar_99_naselja)
    r_meta = fetch_url("https://gis.stat.gov.rs/server/rest/services/Hosted/Indikatori_popis_stanivnistva_2022_1/FeatureServer?f=json", save_manifest=False, timeout=30)
    naselja_layer_id = None
    if r_meta["ok"]:
        meta = json.loads(r_meta["_bytes"].decode("utf-8"))
        for lyr in meta.get("layers", []):
            nm = lyr.get("name", "")
            if "nas" in nm.lower() or "ind1" in nm.lower():
                print(f"    Layer {lyr['id']:2d}: {nm}", flush=True)
            if "ind1_nas" in nm.lower():
                naselja_layer_id = lyr["id"]
    if naselja_layer_id is None:
        # Fallback: inspect which layer was used for Novi Pazar
        naselja_layer_id = 25
    print(f"  Using settlements layer id={naselja_layer_id}", flush=True)

    bg_parents = ",".join(f"'{c}'" for c in BEOGRAD_OPSTINE.keys())
    fc = query_arcgis_geojson(
        f"https://gis.stat.gov.rs/server/rest/services/Hosted/Indikatori_popis_stanivnistva_2022_1/FeatureServer/{naselja_layer_id}",
        where=f"idjezik=2 AND idindikator=1 AND parentid IN ({bg_parents})",
        max_pages=4,
    )
    print(f"  Beograd settlements fetched: {len(fc['features'])}", flush=True)
    if fc["features"]:
        out_p = OUT / "rzs_beograd_naselja_popis2022.geojson"
        out_p.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
        append_manifest({
            "ok": True, "city": "beograd", "layer": "settlements_popis2022_rzs",
            "source_name": f"RZS ArcGIS Popis 2022 Beograd Settlements ({len(fc['features'])} polygons)",
            "url": f"https://gis.stat.gov.rs/server/rest/services/Hosted/Indikatori_popis_stanivnistva_2022_1/FeatureServer/{naselja_layer_id}",
            "http_status": 200, "bytes": out_p.stat().st_size, "sha256": sha256_file(out_p), "local_path": rel(out_p)
        })
        print(f"  [SAVED] {out_p.name} ({out_p.stat().st_size:,} B)", flush=True)

    # Also fetch Serbia all municipalities polygons (Opstine_dashboard) for Pančevo & national supply chain / agri2023 mapping!
    ops_p = OUT / "rzs_srbija_sve_opstine.geojson"
    if not ops_p.exists():
        fc_ops = query_arcgis_geojson(
            "https://gis.stat.gov.rs/server/rest/services/Hosted/Opstine_dashboard/FeatureServer/0",
            where="1=1", max_pages=2
        )
        print(f"  Serbia all municipalities fetched: {len(fc_ops['features'])}", flush=True)
        if fc_ops["features"]:
            ops_p.write_text(json.dumps(fc_ops, ensure_ascii=False), encoding="utf-8")
            append_manifest({
                "ok": True, "city": "common", "layer": "admin_boundaries_srb_all_rzs",
                "source_name": f"RZS ArcGIS Opstine_dashboard All Serbia ({len(fc_ops['features'])} municipalities)",
                "url": "https://gis.stat.gov.rs/server/rest/services/Hosted/Opstine_dashboard/FeatureServer/0",
                "http_status": 200, "bytes": ops_p.stat().st_size, "sha256": sha256_file(ops_p), "local_path": rel(ops_p)
            })

if __name__ == "__main__":
    collect_rzs_agri2023()
    collect_beograd_naselja_and_rzs_gis()
    print("\nDONE 14_collect_wave3_rzs_agri2023_and_bg_naselja.py", flush=True)
