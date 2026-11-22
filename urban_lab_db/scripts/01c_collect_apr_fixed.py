from _paths import rel  # putanje u manifestu su relativne na koren repozitorijuma
import json
import sys
import urllib.parse
from collections import Counter, defaultdict
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


def iter_podaci(obj):
    p = obj.get("Podaci") if isinstance(obj, dict) else obj
    if isinstance(p, list):
        for x in p:
            yield None, x
    elif isinstance(p, dict):
        for k, v in p.items():
            yield k, v


def run_apr():
    print("[APR-FIX] Fetching companies & financial statements...")
    rc = fetch_url("https://openapi.apr.gov.rs/api/opendata/companies", save_manifest=False, timeout=90)
    rf = fetch_url("https://openapi.apr.gov.rs/api/opendata/companies/financial-statements", save_manifest=False, timeout=90)
    if not rc["ok"] or not rf["ok"]:
        print("FAILED:", rc.get("error"), rf.get("error"))
        return

    c_obj = json.loads(rc["_bytes"].decode("utf-8"))
    f_obj = json.loads(rf["_bytes"].decode("utf-8"))
    presek = c_obj.get("DatumPreseka")

    # Inspect sample
    c_iter = iter_podaci(c_obj)
    k0, v0 = next(c_iter)
    print(f"[APR-FIX] Presek={presek}, sample company key={k0}, val={json.dumps(v0, ensure_ascii=False)[:400]}")
    f_iter = iter_podaci(f_obj)
    fk0, fv0 = next(f_iter)
    print(f"[APR-FIX] sample FI key={fk0}, val={json.dumps(fv0, ensure_ascii=False)[:400]}")

    fi_map = {}
    for k, v in iter_podaci(f_obj):
        if isinstance(v, dict):
            mb = str(v.get("MaticniBroj") or k or "").strip().zfill(8)
            fi_map[mb] = v
    print(f"[APR-FIX] Indexed {len(fi_map)} FI records")

    bg_codes = set(BEOGRAD_OPSTINE.keys())
    bg_rows, np_rows = [], []
    nat_nace2 = Counter()
    bg_muni_counts = Counter()
    total_srb = 0

    for k, v in iter_podaci(c_obj):
        if not isinstance(v, dict):
            continue
        total_srb += 1
        mb = str(v.get("MaticniBroj") or k or "").strip().zfill(8)
        m_code = str(v.get("SifraOpstine") or v.get("OpstinaSifra") or "").strip()
        nace = str(v.get("SifraDelatnosti") or v.get("DelatnostSifra") or "").strip()
        if nace:
            nat_nace2[nace[:2]] += 1
        if m_code in bg_codes:
            rec = dict(v)
            rec.setdefault("MaticniBroj", mb)
            if mb in fi_map:
                rec["fi"] = fi_map[mb]
            bg_rows.append(rec)
            bg_muni_counts[m_code] += 1
        elif m_code == NOVI_PAZAR_OPSTINA:
            rec = dict(v)
            rec.setdefault("MaticniBroj", mb)
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

    nat_obj = {
        "datum_preseka": presek,
        "total_companies_serbia": total_srb,
        "total_fi_serbia": len(fi_map),
        "beograd_companies": len(bg_rows),
        "beograd_with_fi": sum(1 for r in bg_rows if "fi" in r),
        "novi_pazar_companies": len(np_rows),
        "novi_pazar_with_fi": sum(1 for r in np_rows if "fi" in r),
        "beograd_by_municipality": {f"{k} {BEOGRAD_OPSTINE[k]}": bg_muni_counts[k] for k in sorted(bg_codes)},
        "nace2_counts_serbia": dict(nat_nace2.most_common()),
    }
    nat_path = RAW_DIR / "common" / "apr_serbia_nace2_baseline.json"
    nat_path.write_text(json.dumps(nat_obj, ensure_ascii=False, indent=2), encoding="utf-8")

    for city, p, cnt in [("beograd", bg_path, len(bg_rows)), ("novi_pazar", np_path, len(np_rows))]:
        append_manifest({
            "ok": True, "city": city, "layer": "companies_apr_rgfi",
            "source_name": f"APR Open Data Companies + RGFI 2025 ({city}: {cnt} companies, presek {presek})",
            "url": "https://openapi.apr.gov.rs/api/opendata/companies",
            "http_status": 200, "bytes": p.stat().st_size, "sha256": sha256_file(p), "local_path": rel(p),
        })
    print(f"[APR-FIX] DONE! Serbia={total_srb}, Beograd={len(bg_rows)} (FI={nat_obj['beograd_with_fi']}), Novi Pazar={len(np_rows)} (FI={nat_obj['novi_pazar_with_fi']})")
    print("[APR-FIX] BG muni counts:", nat_obj["beograd_by_municipality"])


def fetch_np_settlements_rzs():
    print("\n[RZS-NAS] Fetching Novi Pazar 99 settlements (PS22_IND1_NAS)...")
    params = urllib.parse.urlencode({
        "where": "idjezik=2 AND parentid='70874'",
        "outFields": "*",
        "outSR": "4326",
        "f": "geojson",
        "resultRecordCount": "500",
    })
    url = f"https://gis.stat.gov.rs/server/rest/services/Hosted/Indikatori_popis_stanivnistva_2022_1/FeatureServer/29/query?{params}"
    r = fetch_url(url, dest=RAW_DIR / "novi_pazar" / "rzs_novi_pazar_naselja_popis2022.geojson",
                  city="novi_pazar", layer="settlements_popis2022", source_name="RZS Popis 2022 Naselja Novog Pazara GeoJSON")
    if r["ok"]:
        fc = json.loads(r["_bytes"].decode("utf-8"))
        print(f"  [RZS-NAS] parentid='70874': {len(fc.get('features', []))} settlements")
        if len(fc.get("features", [])) == 0:
            # Try by geo_sifra range 729990..731064 or bounding box
            params2 = urllib.parse.urlencode({
                "where": "idjezik=2",
                "geometry": "20.25,42.98,20.72,43.28",
                "geometryType": "esriGeometryEnvelope",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "*",
                "outSR": "4326",
                "f": "geojson",
                "resultRecordCount": "500",
            })
            url2 = f"https://gis.stat.gov.rs/server/rest/services/Hosted/Indikatori_popis_stanivnistva_2022_1/FeatureServer/29/query?{params2}"
            r2 = fetch_url(url2, dest=RAW_DIR / "novi_pazar" / "rzs_novi_pazar_naselja_popis2022.geojson",
                           city="novi_pazar", layer="settlements_popis2022", source_name="RZS Popis 2022 Naselja Novog Pazara (bbox) GeoJSON")
            if r2["ok"]:
                fc2 = json.loads(r2["_bytes"].decode("utf-8"))
                print(f"  [RZS-NAS] bbox fallback: {len(fc2.get('features', []))} settlements")


if __name__ == "__main__":
    run_apr()
    fetch_np_settlements_rzs()
