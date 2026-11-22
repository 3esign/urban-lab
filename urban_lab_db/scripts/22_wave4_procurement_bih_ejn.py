import json
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_net import RAW_DIR, fetch_url

OUT_DIR = RAW_DIR / "wave4" / "procurement_bih"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def odata_get(endpoint: str, params: dict, dest: Path, city: str, source_name: str):
    qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    url = f"https://open.ejn.gov.ba{endpoint}?{qs}"
    r = fetch_url(url, dest=dest, city=city, layer="wave4_procurement_bih", source_name=source_name, timeout=45, retries=2)
    if not r["ok"]:
        print(f"  [FAIL] {source_name}: {r.get('error')}")
        return []
    raw = r.pop("_bytes", b"")
    try:
        data = json.loads(raw.decode("utf-8"))
        return data.get("value", []) if isinstance(data, dict) else []
    except Exception as e:
        print(f"  [JSON ERR] {source_name}: {e}")
        return []


def main():
    # Server enforces max 50 rows/page -> paginate cleanly by 50!
    CITY_QUERIES = [
        ("sarajevo", "sarajevo_core", "contains(ContractingAuthorityCityName,'SARAJEVO') and ContractDate ge 2024-06-01T00:00:00Z", 8),
        ("sarajevo", "sarajevo_ilidza", "contains(ContractingAuthorityCityName,'ILID') and ContractDate ge 2024-01-01T00:00:00Z", 5),
        ("sarajevo", "sarajevo_outer_ks", "(contains(ContractingAuthorityCityName,'VOGO') or contains(ContractingAuthorityCityName,'HAD') or contains(ContractingAuthorityCityName,'ILIJA')) and ContractDate ge 2024-01-01T00:00:00Z", 4),
        ("travnik", "travnik_all", "contains(ContractingAuthorityCityName,'TRAVNIK') and ContractDate ge 2023-01-01T00:00:00Z", 6),
    ]

    all_awards = []
    seen_ids = set()

    for city_id, tag, flt, max_pages in CITY_QUERIES:
        tag_total = 0
        for page in range(max_pages):
            skip = page * 50
            rows = odata_get(
                "/Awards",
                {
                    "$filter": flt,
                    "$orderby": "ContractDate desc",
                    "$top": 50,
                    "$skip": skip,
                },
                OUT_DIR / f"ejn_awards_{tag}_p{page}.json",
                city_id,
                f"ejn_awards_{tag}_p{page}",
            )
            time.sleep(0.25)
            added = 0
            for row in rows:
                aid = row.get("Id")
                if aid in seen_ids:
                    continue
                seen_ids.add(aid)
                row["_urbanlab_city_id"] = city_id
                row["_urbanlab_tag"] = tag
                all_awards.append(row)
                added += 1
                tag_total += 1
            if len(rows) < 50:
                break
        print(f"  + {tag:22s}: total_collected={tag_total}")

    (OUT_DIR / "ejn_awards_sarajevo_travnik_consolidated.json").write_text(
        json.dumps(all_awards, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    sa_rows = [x for x in all_awards if x["_urbanlab_city_id"] == "sarajevo"]
    tr_rows = [x for x in all_awards if x["_urbanlab_city_id"] == "travnik"]
    sa_sb = sum(1 for x in sa_rows if x.get("NumberOfReceivedOffers") == 1)
    tr_sb = sum(1 for x in tr_rows if x.get("NumberOfReceivedOffers") == 1)
    sa_bam = sum(float(x.get("Value") or 0) for x in sa_rows)
    tr_bam = sum(float(x.get("Value") or 0) for x in tr_rows)
    print(f"\nDONE BiH EJN Deep: total={len(all_awards)} | Sarajevo={len(sa_rows)} (single_bidder={sa_sb}, BAM={sa_bam:,.0f}) | Travnik={len(tr_rows)} (single_bidder={tr_sb}, BAM={tr_bam:,.0f})")


if __name__ == "__main__":
    main()
