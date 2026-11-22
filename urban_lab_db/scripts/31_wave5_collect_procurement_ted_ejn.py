from _paths import rel  # putanje u manifestu su relativne na koren repozitorijuma
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from common_net import BASE_DIR, append_manifest, sha256_bytes

OUT_DIR = BASE_DIR / "raw" / "wave5" / "procurement"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CTX = ssl.create_default_context()
HDRS = {"User-Agent": "UrbanLabResearch/1.0", "Accept": "application/json"}


def post_json(url, payload, timeout=30):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={**HDRS, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
        raw = resp.read()
        return json.loads(raw.decode("utf-8", errors="replace")), raw


def get_json(url, timeout=30):
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
        raw = resp.read()
        return json.loads(raw.decode("utf-8", errors="replace")), raw


def collect_ted():
    print("=== 1. Collecting EU TED v3 Contract Award Notices (Zagreb + SRB + BIH) ===", flush=True)
    # First discover which value/winner fields are accepted by TED v3
    candidate_fields = [
        "publication-number", "publication-date", "notice-type", "procedure-type",
        "buyer-name", "buyer-city", "buyer-country", "classification-cpv", "notice-title",
        "winner-name", "winner-city", "winner-country",
        "result-value-lot", "result-value-notice", "tender-value", "tender-value-cur",
        "received-submissions-type-code", "received-submissions-type-val",
        "BT-720-Tender", "BT-27-Procedure", "BT-500-Organization-Company",
    ]
    base_fields = [
        "publication-number", "publication-date", "notice-type", "procedure-type",
        "buyer-name", "buyer-city", "buyer-country", "classification-cpv", "notice-title",
    ]
    extra_candidates = [
        "winner-name", "winner-city", "winner-country",
        "result-value-lot", "result-value-notice", "tender-value", "tender-value-cur",
        "contract-value-lot", "framework-maximum-value-lot",
        "organisation-name-tenderer", "organisation-city-tenderer",
        "BT-720-Tender", "BT-27-Procedure", "BT-759-LotResult",
        "winner-decision-date", "contract-conclusion-date",
    ]
    good_fields = list(base_fields)
    for f in extra_candidates:
        try:
            post_json("https://api.ted.europa.eu/v3/notices/search", {
                "query": 'buyer-country IN (HRV) AND notice-type IN (can-standard) AND publication-date >= 20250101',
                "fields": ["publication-number", f],
                "limit": 1,
            }, timeout=15)
            good_fields.append(f)
        except urllib.error.HTTPError:
            pass
    print("  Valid TED v3 fields:", good_fields, flush=True)

    queries = [
        ("zagreb", "HRV", 'buyer-country IN (HRV) AND buyer-city ~ "Zagreb" AND notice-type IN (can-standard, can-social) AND publication-date >= 20250101', 4),
        ("beograd", "SRB", 'buyer-country IN (SRB) AND publication-date >= 20210101', 2),
        ("sarajevo", "BIH", 'buyer-country IN (BIH) AND publication-date >= 20210101', 2),
    ]
    all_notices = []
    for city_hint, iso, q, max_pages in queries:
        city_cnt = 0
        for page in range(1, max_pages + 1):
            try:
                res, raw = post_json("https://api.ted.europa.eu/v3/notices/search", {
                    "query": q,
                    "fields": good_fields,
                    "page": page,
                    "limit": 100,
                    "scope": "ACTIVE" if iso == "HRV" else "ALL",
                }, timeout=35)
                notices = res.get("notices") or []
                if not notices:
                    break
                for n in notices:
                    n["_urbanlab_city_hint"] = city_hint
                    n["_urbanlab_iso3"] = iso
                all_notices.extend(notices)
                city_cnt += len(notices)
                if len(notices) < 100:
                    break
                time.sleep(0.3)
            except Exception as e:
                print(f"  TED {city_hint} p{page} err: {e}", flush=True)
                # fallback without scope if needed
                if page == 1:
                    try:
                        res, raw = post_json("https://api.ted.europa.eu/v3/notices/search", {
                            "query": q,
                            "fields": good_fields,
                            "page": 1,
                            "limit": 100,
                        }, timeout=35)
                        notices = res.get("notices") or []
                        for n in notices:
                            n["_urbanlab_city_hint"] = city_hint
                            n["_urbanlab_iso3"] = iso
                        all_notices.extend(notices)
                        city_cnt += len(notices)
                    except Exception as e2:
                        print(f"  TED fallback {city_hint} err: {e2}", flush=True)
                break
        print(f"  TED {city_hint} ({iso}): collected {city_cnt} notices", flush=True)

    out_path = OUT_DIR / "ted_v3_awards_zg_srb_bih.json"
    out_bytes = json.dumps({"fields": good_fields, "count": len(all_notices), "notices": all_notices}, ensure_ascii=False, indent=2).encode("utf-8")
    out_path.write_bytes(out_bytes)
    append_manifest({
        "ok": True, "city": "common", "layer": "wave5_procurement", "source_name": "eu_ted_v3_api",
        "url": "https://api.ted.europa.eu/v3/notices/search", "http_status": 200,
        "bytes": len(out_bytes), "sha256": sha256_bytes(out_bytes), "local_path": rel(out_path),
    })
    print(f"  Saved {len(all_notices)} TED notices to {out_path.name}", flush=True)


def collect_bih_ejn_suppliers():
    print("\n=== 2. Collecting BiH EJN LotContracts (Winners/Suppliers for Sarajevo & Travnik) ===", flush=True)
    # Inspect our existing BiH awards to grab their ProcedureIds / NoticeIds
    awards_p = BASE_DIR / "raw" / "wave4" / "procurement_bih" / "ejn_awards_sarajevo_travnik_consolidated.json"
    if not awards_p.exists():
        print("  No existing BiH awards file.", flush=True)
        return
    awards = json.loads(awards_p.read_text(encoding="utf-8"))
    # Probe LotContracts schema first
    try:
        sample, _ = get_json("https://open.ejn.gov.ba/LotContracts?$top=2")
        rows = sample.get("value") or []
        print("  LotContracts keys:", list(rows[0].keys()) if rows else "EMPTY", flush=True)
    except Exception as e:
        print("  LotContracts probe err:", e, flush=True)
        return

    # Fetch recent LotContracts for Sarajevo and Travnik authorities!
    # Filter by ContractingAuthorityCityName or ContractingAuthorityId from our awards
    collected = []
    seen_ids = set()
    # Pull top 400 Sarajevo + top 200 Travnik LotContracts ordered by ContractDate desc
    filters = [
        ("sarajevo", "contains(tolower(ContractingAuthorityCityName),'sarajevo') or contains(tolower(ContractingAuthorityCityName),'ilidza') or contains(tolower(ContractingAuthorityCityName),'ilidža') or contains(tolower(ContractingAuthorityCityName),'vogošća') or contains(tolower(ContractingAuthorityCityName),'hadžići') or contains(tolower(ContractingAuthorityCityName),'ilijaš')"),
        ("travnik", "contains(tolower(ContractingAuthorityCityName),'travnik')"),
    ]
    for cid, flt in filters:
        for skip in (0, 200, 400):
            if cid == "travnik" and skip >= 400:
                break
            q = urllib.parse.urlencode({
                "$filter": flt,
                "$orderby": "ContractDate desc",
                "$top": 200,
                "$skip": skip,
            })
            url = f"https://open.ejn.gov.ba/LotContracts?{q}"
            try:
                data, _ = get_json(url, timeout=30)
                vals = data.get("value") or []
                if not vals:
                    break
                for v in vals:
                    vid = v.get("Id")
                    if vid not in seen_ids:
                        seen_ids.add(vid)
                        v["_urbanlab_city_id"] = cid
                        collected.append(v)
                print(f"  EJN LotContracts {cid} skip={skip}: +{len(vals)}", flush=True)
                if len(vals) < 200:
                    break
                time.sleep(0.25)
            except Exception as e:
                print(f"  EJN LotContracts {cid} skip={skip} err: {e}", flush=True)
                break

    # Also test matching by ProcedureId if ContractingAuthorityCityName filter isn't supported on LotContracts
    if not collected:
        print("  Fallback: fetching latest 1000 LotContracts and matching ProcedureId/AwardId...", flush=True)
        proc_to_city = {a.get("ProcedureId"): a.get("_urbanlab_city_id") for a in awards if a.get("ProcedureId")}
        for skip in range(0, 1200, 200):
            url = f"https://open.ejn.gov.ba/LotContracts?$orderby=Id%20desc&$top=200&$skip={skip}"
            try:
                data, _ = get_json(url, timeout=30)
                vals = data.get("value") or []
                if not vals:
                    break
                matched = 0
                for v in vals:
                    pid = v.get("ProcedureId")
                    if pid in proc_to_city and v.get("Id") not in seen_ids:
                        seen_ids.add(v.get("Id"))
                        v["_urbanlab_city_id"] = proc_to_city[pid]
                        collected.append(v)
                        matched += 1
                print(f"  Fallback skip={skip}: fetched={len(vals)}, matched={matched}", flush=True)
                time.sleep(0.25)
            except Exception as e:
                print(f"  Fallback err: {e}", flush=True)
                break

    out_path = OUT_DIR / "ejn_bih_lotcontracts_suppliers.json"
    out_bytes = json.dumps(collected, ensure_ascii=False, indent=2).encode("utf-8")
    out_path.write_bytes(out_bytes)
    append_manifest({
        "ok": True, "city": "common", "layer": "wave5_procurement", "source_name": "bih_ejn_lotcontracts_odata",
        "url": "https://open.ejn.gov.ba/LotContracts", "http_status": 200,
        "bytes": len(out_bytes), "sha256": sha256_bytes(out_bytes), "local_path": rel(out_path),
    })
    print(f"  Saved {len(collected)} BiH LotContracts to {out_path.name}", flush=True)


if __name__ == "__main__":
    collect_ted()
    collect_bih_ejn_suppliers()
