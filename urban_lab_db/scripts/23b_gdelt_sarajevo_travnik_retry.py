import hashlib
import json
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_net import RAW_DIR, fetch_url

OUT_DIR = RAW_DIR / "wave4" / "news"
p = OUT_DIR / "news_rss_gdelt_5cities.json"
data = json.loads(p.read_text(encoding="utf-8"))
seen = {a.get("raw_sha256") for a in data["articles"]}

for city_id, iso3, q in [
    ("sarajevo", "BIH", 'Sarajevo (economy OR urban OR air OR infrastructure OR investment)'),
    ("travnik", "BIH", 'Travnik (Bosnia OR economy OR investment OR road OR tourism)'),
]:
    time.sleep(8.0)
    params = urllib.parse.urlencode({"query": q, "mode": "artlist", "maxrecords": 40, "timespan": "3m", "format": "json"})
    url = f"https://api.gdeltproject.org/api/v2/doc/doc?{params}"
    r = fetch_url(url, dest=OUT_DIR / f"gdelt_artlist_{city_id}_retry.json", city=city_id, layer="wave4_news_gdelt", source_name=f"gdelt_{city_id}_retry", timeout=25, retries=2)
    if not r["ok"]:
        print(f"  [FAIL] gdelt_{city_id}: {r.get('error')}")
        continue
    d = json.loads(r.pop("_bytes", b"").decode("utf-8", errors="replace"))
    arts = d.get("articles") or []
    added = 0
    for a in arts:
        h = hashlib.sha256(((a.get("url") or "") + "|" + (a.get("title") or "")).encode("utf-8")).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        seendate = a.get("seendate") or ""
        iso_dt = f"{seendate[:4]}-{seendate[4:6]}-{seendate[6:8]}" if len(seendate) >= 8 else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        data["articles"].append({
            "city_id": city_id,
            "country_iso3": iso3,
            "source_id": "gdelt_doc_2",
            "source_name": f"GDELT ({a.get('domain', 'web')})",
            "domain_axis": "news_global",
            "title": (a.get("title") or "").strip(),
            "url": a.get("url") or "",
            "summary": f"Domain: {a.get('domain')}; Lang: {a.get('language')}; Country: {a.get('sourcecountry')}",
            "published_at": iso_dt,
            "language": (a.get("language") or "en")[:12].lower(),
            "raw_sha256": h,
        })
        added += 1
    print(f"  [OK] gdelt_{city_id}: +{added} articles (fetched={len(arts)})")

p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("Updated total news articles:", len(data["articles"]))
