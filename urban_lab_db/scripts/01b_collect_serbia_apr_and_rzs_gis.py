from _paths import rel  # putanje u manifestu su relativne na koren repozitorijuma
import json
import sys
import urllib.parse
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common_net import RAW_DIR, fetch_url, append_manifest, sha256_file

BEOGRAD_OPSTINE = {
    "70092": "Barajevo", "70106": "Voždovac", "70114": "Vračar", "70122": "Grocka",
    "70149": "Zvezdara", "70157": "Zemun", "70165": "Lazarevac", "70173": "Mladenovac",
    "70181": "Novi Beograd", "70190": "Obrenovac", "70203": "Palilula", "70211": "Rakovica",
    "70220": "Savski venac", "70238": "Sopot", "70246": "Stari grad", "70254": "Čukarica",
    "71293": "Surčin",
}
NOVI_PAZAR_OPSTINA = "70874"


def extract_records(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        # Find the largest list value in the dict
        best = []
        for k, v in obj.items():
            if isinstance(v, list) and len(v) > len(best):
                best = v
            elif isinstance(v, dict):
                sub = extract_records(v)
                if len(sub) > len(best):
                    best = sub
        return best
    return []


def collect_apr_fixed():
    print("[APR] Fetching live APR Open Data (companies + financial-statements)...")
    r_comp = fetch_url(
        "https://openapi.apr.gov.rs/api/opendata/companies",
        dest=None, city="common", layer="apr_companies_stream",
        source_name="APR Open Data Companies full", timeout=90, save_manifest=False
    )
    if not r_comp["ok"]:
        print("[APR] companies FAILED:", r_comp.get("error"))
        return
    comp_obj = json.loads(r_comp["_bytes"].decode("utf-8"))
    if isinstance(comp_obj, dict):
        print("[APR] companies top keys:", {k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in comp_obj.items()})
    comp_rows = extract_records(comp_obj)
    print(f"[APR] extracted companies: {len(comp_rows)}")
    if comp_rows:
        print("[APR] sample company:", json.dumps(comp_rows[0], ensure_ascii=False)[:400])

    r_fi = fetch_url(
        "https://openapi.apr.gov.rs/api/opendata/companies/financial-statements",
        dest=None, city="common", layer="apr_fi_stream",
        source_name="APR Open Data Financial Statements full", timeout=90, save_manifest=False
    )
    fi_map = {}
    if r_fi["ok"]:
        fi_obj = json.loads(r_fi["_bytes"].decode("utf-8"))
        if isinstance(fi_obj, dict):
            print("[APR] fi top keys:", {k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in fi_obj.items()})
        fi_rows = extract_records(fi_obj)
        print(f"[APR] extracted FI rows: {len(fi_rows)}")
        if fi_rows:
            print("[APR] sample FI:", json.dumps(fi_rows[0], ensure_ascii=False)[:400])
        for row in fi_rows:
            mb = str(row.get("MaticniBroj") or row.get("maticniBroj") or row.get("RegistrationNumber") or "").strip().zfill(8)
            if mb and mb != "00000000":
                fi_map[mb] = row

    bg_codes = set(BEOGRAD_OPSTINE.keys())
    bg_rows, np_rows = [], []
    nat_nace2 = Counter()
    bg_muni_counts = Counter()

    for row in comp_rows:
        m_code = str(row.get("SifraOpstine") or row.get("sifraOpstine") or row.get("MunicipalityCode") or "").strip()
        mb = str(row.get("MaticniBroj") or row.get("maticniBroj") or row.get("RegistrationNumber") or "").strip().zfill(8)
        nace = str(row.get("SifraDelatnosti") or row.get("sifraDelatnosti") or row.get("ActivityCode") or "").strip()
        if nace:
            nat_nace2[nace[:2]] += 1
        if m_code in bg_codes:
            rec = dict(row)
            if mb in fi_map:
                rec["fi"] = fi_map[mb]
            bg_rows.append(rec)
            bg_muni_counts[m_code] += 1
        elif m_code == NOVI_PAZAR_OPSTINA:
            rec = dict(row)
            if mb in fi_map:
                rec["fi"] = fi_map[mb]
            np_rows.append(rec)

    bg_path = RAW_DIR / "beograd" / "apr_beograd_companies.jsonl"
    with open(bg_path, "w", encoding="utf-8") as f:
        for r in bg_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    np_path = RAW_DIR / "novi_pazar" / "apr_novi_pazar_companies.jsonl"
    with open(np_path, "w", encoding="utf-8") as f:
        for r in np_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    nat_path = RAW_DIR / "common" / "apr_serbia_nace2_baseline.json"
    nat_obj = {
        "total_companies_serbia": len(comp_rows),
        "total_fi_serbia": len(fi_map),
        "beograd_companies": len(bg_rows),
        "beograd_with_fi": sum(1 for r in bg_rows if "fi" in r),
        "novi_pazar_companies": len(np_rows),
        "novi_pazar_with_fi": sum(1 for r in np_rows if "fi" in r),
        "beograd_by_municipality": {f"{k} {BEOGRAD_OPSTINE[k]}": bg_muni_counts[k] for k in sorted(bg_codes)},
        "nace2_counts_serbia": dict(nat_nace2.most_common()),
    }
    nat_path.write_text(json.dumps(nat_obj, ensure_ascii=False, indent=2), encoding="utf-8")

    for city, p, cnt in [("beograd", bg_path, len(bg_rows)), ("novi_pazar", np_path, len(np_rows))]:
        append_manifest({
            "ok": True, "city": city, "layer": "companies_apr_rgfi",
            "source_name": f"APR Open Data Companies + RGFI 2025 ({city}: {cnt} companies)",
            "url": "https://openapi.apr.gov.rs/api/opendata/companies",
            "http_status": 200, "bytes": p.stat().st_size, "sha256": sha256_file(p),
            "local_path": rel(p),
        })
    print(f"[APR] DONE: Beograd={len(bg_rows)} (with FI={nat_obj['beograd_with_fi']}), Novi Pazar={len(np_rows)} (with FI={nat_obj['novi_pazar_with_fi']})")
    print("[APR] BG municipalities:", nat_obj["beograd_by_municipality"])


def query_arcgis_geojson(base_url: str, where: str = "1=1", geometry: str | None = None, out_fields: str = "*", max_pages: int = 10):
    all_features = []
    offset = 0
    page_size = 1000
    for _ in range(max_pages):
        params = {
            "where": where,
            "outFields": out_fields,
            "outSR": "4326",
            "f": "geojson",
            "resultOffset": str(offset),
            "resultRecordCount": str(page_size),
        }
        if geometry:
            params["geometry"] = geometry
            params["geometryType"] = "esriGeometryEnvelope"
            params["inSR"] = "4326"
            params["spatialRel"] = "esriSpatialRelIntersects"
        url = f"{base_url}/query?{urllib.parse.urlencode(params)}"
        r = fetch_url(url, save_manifest=False, timeout=60)
        if not r["ok"]:
            print(f"  [ArcGIS] query failed: {r.get('error')}")
            break
        obj = json.loads(r["_bytes"].decode("utf-8"))
        feats = obj.get("features", [])
        all_features.extend(feats)
        if len(feats) < page_size:
            break
        offset += page_size
    return {"type": "FeatureCollection", "features": all_features}


def collect_rzs_gis_layers():
    print("\n[RZS-GIS] Downloading Beograd (17 opstina) + Novi Pazar boundaries & 1km Census 2022 grids...")
    # 1. All municipalities of Beograd (17) + Novi Pazar from Opstine_dashboard
    bg_np_codes = ",".join(f"'{c}'" for c in list(BEOGRAD_OPSTINE.keys()) + [NOVI_PAZAR_OPSTINA])
    # First check sample matbro format
    sample_fc = query_arcgis_geojson("https://gis.stat.gov.rs/server/rest/services/Hosted/Opstine_dashboard/FeatureServer/0", where="1=1", max_pages=1)
    print(f"  [RZS] Opstine_dashboard total fetched: {len(sample_fc['features'])}")
    if sample_fc["features"]:
        print("  [RZS] sample props:", sample_fc["features"][0]["properties"])
    bg_feats = []
    np_feats = []
    for f in sample_fc["features"]:
        mb = str(f["properties"].get("matbro") or "").strip()
        if mb in BEOGRAD_OPSTINE:
            bg_feats.append(f)
        elif mb == NOVI_PAZAR_OPSTINA:
            np_feats.append(f)

    for cid, feats, fname in [
        ("beograd", bg_feats, "rzs_beograd_17_opstina.geojson"),
        ("novi_pazar", np_feats, "rzs_novi_pazar_opstina.geojson"),
    ]:
        p = RAW_DIR / cid / fname
        p.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False), encoding="utf-8")
        append_manifest({
            "ok": True, "city": cid, "layer": "admin_boundaries_rzs",
            "source_name": f"RZS ArcGIS Opstine_dashboard ({cid}, {len(feats)} polygons)",
            "url": "https://gis.stat.gov.rs/server/rest/services/Hosted/Opstine_dashboard/FeatureServer/0",
            "http_status": 200, "bytes": p.stat().st_size, "sha256": sha256_file(p), "local_path": rel(p),
        })
        print(f"  [RZS] Saved {fname}: {len(feats)} features")

    # 2. Census 2022 Indicators by Municipality (PS22_IND1_OPS = layer 24)
    # Check what indicators exist in layer 24
    ind_bg_np = query_arcgis_geojson(
        "https://gis.stat.gov.rs/server/rest/services/Hosted/Indikatori_popis_stanivnistva_2022_1/FeatureServer/24",
        where=f"idjezik=2 AND ter_kod IN ({bg_np_codes})",
        max_pages=5,
    )
    print(f"  [RZS] PS22_IND1_OPS (BG+NP): {len(ind_bg_np['features'])} features")
    if ind_bg_np["features"]:
        inds = sorted({(f['properties'].get('idindikator'), f['properties'].get('nindikator')) for f in ind_bg_np['features']})
        print("  [RZS] Indicators in IND1_OPS:", inds[:10])
    p_ind = RAW_DIR / "common" / "rzs_popis2022_ind1_bg_np_ops.geojson"
    p_ind.write_text(json.dumps(ind_bg_np, ensure_ascii=False), encoding="utf-8")
    append_manifest({
        "ok": True, "city": "common", "layer": "census_2022_ops_rzs",
        "source_name": f"RZS Popis 2022 Indikatori po opstinama (BG+NP, {len(ind_bg_np['features'])} rows)",
        "url": "https://gis.stat.gov.rs/server/rest/services/Hosted/Indikatori_popis_stanivnistva_2022_1/FeatureServer/24",
        "http_status": 200, "bytes": p_ind.stat().st_size, "sha256": sha256_file(p_ind), "local_path": rel(p_ind),
    })

    # 3. 1 km x 1 km Census 2022 Grid for Beograd and Novi Pazar!
    for cid, bbox_str in [
        ("beograd", "20.20,44.65,20.70,44.95"),
        ("novi_pazar", "20.25,42.98,20.72,43.28"),
    ]:
        # First check one feature to know idjezik and idindikator for population
        grid_fc = query_arcgis_geojson(
            "https://gis.stat.gov.rs/server/rest/services/Hosted/Indikatori_Popis_stanovistva_grid_4/FeatureServer/0",
            where="idjezik=2",
            geometry=bbox_str,
            max_pages=6,
        )
        p_g = RAW_DIR / cid / f"rzs_popis2022_grid_1km_{cid}.geojson"
        p_g.write_text(json.dumps(grid_fc, ensure_ascii=False), encoding="utf-8")
        append_manifest({
            "ok": True, "city": cid, "layer": "census_2022_grid_1km",
            "source_name": f"RZS Popis 2022 1km x 1km Grid ({cid}, {len(grid_fc['features'])} cells)",
            "url": "https://gis.stat.gov.rs/server/rest/services/Hosted/Indikatori_Popis_stanovistva_grid_4/FeatureServer/0",
            "http_status": 200, "bytes": p_g.stat().st_size, "sha256": sha256_file(p_g), "local_path": rel(p_g),
        })
        ind_names = sorted({f["properties"].get("nindikator") for f in grid_fc["features"]})
        print(f"  [RZS-GRID] {cid}: {len(grid_fc['features'])} cells, indicators={ind_names[:5]}")


if __name__ == "__main__":
    collect_apr_fixed()
    collect_rzs_gis_layers()
