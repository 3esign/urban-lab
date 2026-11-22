import hashlib
import json
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_net import RAW_DIR, fetch_url

OUT_DIR = RAW_DIR / "wave4" / "news"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Balanced multi-city RSS feeds (including hyper-local NP & TR + regional econ press)
RSS_FEEDS = [
    ("novi_pazar", "SRB", "rss_stoplus", "Radio Sto Plus (Novi Pazar)", "news_hyperlocal", "https://radiostoplus.com/feed/"),
    ("novi_pazar", "SRB", "rss_freemedia", "Free Media (Novi Pazar)", "news_hyperlocal", "https://freemedia.rs/feed/"),
    ("novi_pazar", "SRB", "rss_rtvnp", "RTV Novi Pazar", "news_hyperlocal", "https://rtvnp.rs/feed/"),
    ("novi_pazar", "SRB", "rss_sandzakpress", "Sandzak Press", "news_hyperlocal", "https://sandzakpress.net/feed/"),
    ("travnik", "BIH", "rss_travnikgrad", "Travnik-grad.info", "news_hyperlocal", "https://travnik-grad.info/feed/"),
    ("travnik", "BIH", "rss_drukciji", "Drukciji Radio (Srednja Bosna)", "news_hyperlocal", "https://drukciji.ba/feed/"),
    ("travnik", "BIH", "rss_tntportal", "TNT Portal (Travnik)", "news_hyperlocal", "https://tntportal.ba/feed/"),
    ("sarajevo", "BIH", "rss_biznisinfo", "BiznisInfo.ba", "news_regional", "https://www.biznisinfo.ba/feed/"),
    ("sarajevo", "BIH", "rss_indikator", "Indikator.ba", "news_regional", "https://www.indikator.ba/index.php?format=feed&type=rss"),
    ("sarajevo", "BIH", "rss_fokus_ekon", "Fokus.ba Biznis", "news_regional", "https://www.fokus.ba/biznis/feed/"),
    ("zagreb", "HRV", "rss_poslovni", "Poslovni dnevnik (HR)", "news_regional", "https://www.poslovni.hr/feed"),
    ("zagreb", "HRV", "rss_lider", "Lider Media (HR)", "news_regional", "https://lidermedia.hr/rss/"),
    ("zagreb", "HRV", "rss_zagreb_info", "Zagreb.info", "news_hyperlocal", "https://www.zagreb.info/feed/"),
    ("beograd", "SRB", "rss_danas_ekon", "Danas Ekonomija (SRB)", "news_regional", "https://www.danas.rs/rubrika/ekonomija/feed/"),
    ("beograd", "SRB", "rss_danas_bg", "Danas Beograd", "news_hyperlocal", "https://www.danas.rs/rubrika/beograd/feed/"),
    ("beograd", "SRB", "rss_novaekon", "Nova Ekonomija (SRB)", "news_regional", "https://novaekonomija.rs/feed"),
    ("beograd", "SRB", "rss_n1_biznis", "N1 Srbija Biznis", "news_regional", "https://n1info.rs/biznis/feed/"),
]


def strip_html(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_pubdate(dt_str: str) -> str:
    if not dt_str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        dt = parsedate_to_datetime(dt_str)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", dt_str)
        return m.group(1) if m else datetime.now(timezone.utc).strftime("%Y-%m-%d")


def parse_rss_xml(raw: bytes):
    items = []
    try:
        root = ET.fromstring(raw)
    except Exception:
        return items
    # RSS 2.0 <item> or Atom <entry>
    for el in root.findall(".//item"):
        title = (el.findtext("title") or "").strip()
        link = (el.findtext("link") or "").strip()
        desc = strip_html(el.findtext("description") or "")
        pub = parse_pubdate(el.findtext("pubDate") or "")
        cats = [c.text.strip() for c in el.findall("category") if c.text]
        if title and link:
            items.append({"title": title, "url": link, "summary": desc[:600], "published_at": pub, "categories": cats[:6]})
    if not items:
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for el in root.findall(".//a:entry", ns):
            title = (el.findtext("a:title", "", ns) or "").strip()
            link_el = el.find("a:link", ns)
            link = (link_el.attrib.get("href") if link_el is not None else "") or ""
            desc = strip_html(el.findtext("a:summary", "", ns) or "")
            pub = parse_pubdate(el.findtext("a:updated", "", ns) or "")
            if title and link:
                items.append({"title": title, "url": link, "summary": desc[:600], "published_at": pub, "categories": []})
    return items


def main():
    all_articles = []
    feed_stats = []

    print("=== 1. Collecting Multi-City Local & Economic RSS Feeds ===")
    for city_id, iso3, src_id, src_name, axis, url in RSS_FEEDS:
        r = fetch_url(url, dest=OUT_DIR / f"{src_id}.xml", city=city_id, layer="wave4_news_rss", source_name=src_id, timeout=20, retries=1)
        if not r["ok"]:
            print(f"  [FAIL] {src_id:18s} ({city_id}): {r.get('error')}")
            feed_stats.append({"source_id": src_id, "city_id": city_id, "ok": False, "count": 0, "error": r.get("error")})
            continue
        raw = r.pop("_bytes", b"")
        items = parse_rss_xml(raw)
        print(f"  [OK]   {src_id:18s} ({city_id:10s}): {len(items):3d} articles")
        feed_stats.append({"source_id": src_id, "city_id": city_id, "ok": True, "count": len(items)})
        for it in items:
            it["city_id"] = city_id
            it["country_iso3"] = iso3
            it["source_id"] = src_id
            it["source_name"] = src_name
            it["domain_axis"] = axis
            it["raw_sha256"] = hashlib.sha256((it["url"] + "|" + it["title"]).encode("utf-8")).hexdigest()
            all_articles.append(it)
        time.sleep(0.25)

    print("\n=== 2. Collecting GDELT DOC 2.0 (rate-limited polite spacing) ===")
    gdelt_queries = [
        ("beograd", "SRB", 'Belgrade (economy OR urban OR housing OR protest OR infrastructure OR investment)'),
        ("zagreb", "HRV", 'Zagreb (economy OR urban OR housing OR transport OR infrastructure OR investment)'),
        ("sarajevo", "BIH", 'Sarajevo (economy OR urban OR air OR pollution OR infrastructure OR investment)'),
        ("novi_pazar", "SRB", '"Novi Pazar" (Serbia OR economy OR protest OR road OR investment OR municipality)'),
        ("travnik", "BIH", 'Travnik (Bosnia OR economy OR investment OR road OR municipality OR tourism)'),
    ]
    gdelt_articles = []
    for city_id, iso3, q in gdelt_queries:
        time.sleep(5.5)
        params = urllib.parse.urlencode({
            "query": q,
            "mode": "artlist",
            "maxrecords": 40,
            "timespan": "3m",
            "format": "json",
        })
        url = f"https://api.gdeltproject.org/api/v2/doc/doc?{params}"
        r = fetch_url(url, dest=OUT_DIR / f"gdelt_artlist_{city_id}.json", city=city_id, layer="wave4_news_gdelt", source_name=f"gdelt_{city_id}", timeout=25, retries=1)
        if not r["ok"]:
            print(f"  [FAIL] gdelt_{city_id}: {r.get('error')}")
            continue
        raw = r.pop("_bytes", b"")
        try:
            d = json.loads(raw.decode("utf-8", errors="replace"))
            arts = d.get("articles") or []
            print(f"  [OK]   gdelt_{city_id:10s}: {len(arts)} articles")
            for a in arts:
                seendate = a.get("seendate") or ""
                iso_dt = f"{seendate[:4]}-{seendate[4:6]}-{seendate[6:8]}" if len(seendate) >= 8 else datetime.now(timezone.utc).strftime("%Y-%m-%d")
                gdelt_articles.append({
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
                    "raw_sha256": hashlib.sha256(((a.get("url") or "") + "|" + (a.get("title") or "")).encode("utf-8")).hexdigest(),
                })
        except Exception as e:
            print(f"  [PARSE ERR] gdelt_{city_id}: {e}")

    combined = all_articles + gdelt_articles
    (OUT_DIR / "news_rss_gdelt_5cities.json").write_text(
        json.dumps({"feed_stats": feed_stats, "articles": combined}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nDONE News: RSS={len(all_articles)}, GDELT={len(gdelt_articles)}, Total={len(combined)}")


if __name__ == "__main__":
    main()
