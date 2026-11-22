from _paths import rel  # putanje u manifestu su relativne na koren repozitorijuma
import json
import ssl
import time
import urllib.error
import urllib.request
from common_net import BASE_DIR, append_manifest, sha256_bytes

OUT_DIR = BASE_DIR / "raw" / "wave5" / "procurement"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CTX = ssl.create_default_context()
HDRS = {
    "User-Agent": "UrbanLabResearch/1.0 (Academic Urban Economics)",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

VALID_FIELDS = [
    "publication-number", "publication-date", "notice-type", "procedure-type",
    "buyer-name", "buyer-city", "buyer-country", "classification-cpv", "notice-title",
    "winner-name", "winner-city", "winner-country",
    "result-value-lot", "result-value-notice", "tender-value", "tender-value-cur",
    "BT-720-Tender", "BT-27-Procedure", "winner-decision-date",
]


def post_ted(payload, retries=3):
    data = json.dumps(payload).encode("utf-8")
    for attempt in range(retries):
        try:
            req = urllib.request.Request("https://api.ted.europa.eu/v3/notices/search", data=data, headers=HDRS)
            with urllib.request.urlopen(req, timeout=35, context=CTX) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 8 * (attempt + 1)
                print(f"  TED 429, sleeping {wait}s...", flush=True)
                time.sleep(wait)
            else:
                raise
    return None


def main():
    time.sleep(5)
    queries = [
        ("zagreb", "HRV", 'buyer-country IN (HRV) AND buyer-city ~ "Zagreb" AND notice-type IN (can-standard, can-social) AND publication-date >= 20250101', 3),
        ("beograd", "SRB", 'buyer-country IN (SRB) AND publication-date >= 20200101', 2),
        ("sarajevo", "BIH", 'buyer-country IN (BIH) AND publication-date >= 20200101', 2),
    ]
    all_notices = []
    for city_hint, iso, q, pages in queries:
        cnt = 0
        for p in range(1, pages + 1):
            try:
                res = post_ted({"query": q, "fields": VALID_FIELDS, "page": p, "limit": 100})
                if not res:
                    break
                notices = res.get("notices") or []
                total = res.get("totalNoticeCount")
                for n in notices:
                    n["_urbanlab_city_hint"] = city_hint
                    n["_urbanlab_iso3"] = iso
                all_notices.extend(notices)
                cnt += len(notices)
                print(f"  TED {city_hint} p{p}: +{len(notices)} (total available: {total})", flush=True)
                if len(notices) < 100:
                    break
                time.sleep(4.0)
            except Exception as e:
                print(f"  TED {city_hint} p{p} err: {e}", flush=True)
                break
        time.sleep(4.0)

    out_p = OUT_DIR / "ted_v3_awards_zg_srb_bih.json"
    b = json.dumps({"fields": VALID_FIELDS, "count": len(all_notices), "notices": all_notices}, ensure_ascii=False, indent=2).encode("utf-8")
    out_p.write_bytes(b)
    append_manifest({
        "ok": True, "city": "common", "layer": "wave5_procurement", "source_name": "eu_ted_v3_api",
        "url": "https://api.ted.europa.eu/v3/notices/search", "http_status": 200,
        "bytes": len(b), "sha256": sha256_bytes(b), "local_path": rel(out_p),
    })
    print(f"Saved {len(all_notices)} TED notices to {out_p.name}", flush=True)

    # Also inspect BiH EJN Suppliers / AwardNotices for supplier mapping
    print("\nProbing BiH EJN AwardNotices & Suppliers...", flush=True)
    for ep in ["AwardNotices?$top=2", "Suppliers?$top=2", "ProcedureContractSummaries?$top=2"]:
        try:
            req = urllib.request.Request(f"https://open.ejn.gov.ba/{ep}", headers={"User-Agent": "UrbanLabResearch/1.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=20, context=CTX) as resp:
                d = json.loads(resp.read().decode("utf-8", errors="replace"))
                vals = d.get("value") or []
                print(f"  EJN {ep}: keys={list(vals[0].keys()) if vals else 'EMPTY'}", flush=True)
        except Exception as e:
            print(f"  EJN {ep} err: {e}", flush=True)


if __name__ == "__main__":
    main()
