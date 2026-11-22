import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common_net import RAW_DIR, fetch_url


def collect_bih_docs():
    docs = [
        ("sarajevo", "fzs_stats_2026_pdf", "FZS Kanton Sarajevo u brojkama 2026 PDF",
         "http://fzs.ba/wp-content/uploads/2026/03/kanton-sarajevo.pdf",
         RAW_DIR / "sarajevo" / "fzs_kanton_sarajevo_2026.pdf"),
        ("sarajevo", "zpr_dev_report_2025_pdf", "ZPR KS Izvjestaj o razvoju Kantona Sarajevo za 2025 PDF",
         "https://zpr.ks.gov.ba/sites/zpr.ks.gov.ba/files/2026-09/4-materijal-za-razmatranje_izvjestaj-o-razvoju-ks-za-2025_0.pdf",
         RAW_DIR / "sarajevo" / "zpr_ks_izvjestaj_razvoj_2025.pdf"),
        ("sarajevo", "budget_ks_page", "Ministarstvo finansija KS preuzimanja budzet",
         "https://mf.ks.gov.ba/preuzimanja/budzet",
         RAW_DIR / "sarajevo" / "mf_ks_budzet_page.html"),
        ("sarajevo", "budget_ks_2026_node", "Ministarstvo finansija KS Budzet 2026 node/4673",
         "https://mf.ks.gov.ba/node/4673",
         RAW_DIR / "sarajevo" / "mf_ks_budzet_2026_node.html"),
        ("travnik", "fzs_stats_sbk_2025_pdf", "FZS Srednjobosanski kanton u brojkama 2025 PDF (uklj. Travnik)",
         "https://fzs.ba/wp-content/uploads/2025/07/srednjobosanski-kanton.pdf",
         RAW_DIR / "travnik" / "fzs_sbk_travnik_2025.pdf"),
        ("travnik", "budget_page", "Opcina Travnik Budzet dokumenti HTML",
         "https://opcinatravnik.com.ba/ba/dokumenti/budzet-2",
         RAW_DIR / "travnik" / "opcina_travnik_budzet_page.html"),
        ("common", "fbih_rcn_2024_pdf", "FGU Registar cijena nekretnina FBiH Izvjestaj 2024 PDF (Sarajevo + Travnik)",
         "https://www.katastar.ba/download/Izvjestaj_RCN_2024f.pdf",
         RAW_DIR / "common" / "fgu_rcn_fbih_2024.pdf"),
        ("common", "fbih_popis_2013_pdf", "FZS Konacni rezultati Popisa 2013 PDF",
         "https://fzs.ba/wp-content/uploads/2016/12/Konacni-rezultati-Popisa-2013.pdf",
         RAW_DIR / "common" / "fzs_popis_2013_konacni.pdf"),
        ("common", "ippfbih_meta", "IPP FBiH metapodaci / servisi",
         "https://metapodaci.ippfbih.gov.ba/srv/api/records?any=Sarajevo",
         RAW_DIR / "sarajevo" / "ippfbih_records_sarajevo.json"),
    ]
    for city, layer, name, url, dest in docs:
        r = fetch_url(url, dest=dest, city=city, layer=layer, source_name=name, timeout=60)
        print(f"[BIH-DOC] {city}/{layer}: ok={r['ok']} bytes={r.get('bytes')} err={r.get('error')}")


def collect_geoboundaries():
    # Official geoBoundaries open API (CC BY 4.0) for SRB, HRV, BIH ADM2 (municipalities/counties) & ADM3 where available
    targets = [
        ("SRB", "ADM2"),
        ("HRV", "ADM2"),
        ("BIH", "ADM2"),
        ("BIH", "ADM3"),
    ]
    for iso, adm in targets:
        api_url = f"https://www.geoboundaries.org/api/current/gbOpen/{iso}/{adm}/"
        r = fetch_url(
            api_url,
            dest=RAW_DIR / "common" / f"geoboundaries_{iso}_{adm}_meta.json",
            city="common",
            layer="admin_boundaries_meta",
            source_name=f"geoBoundaries {iso} {adm} metadata",
        )
        if not r["ok"]:
            print(f"[GB] {iso}/{adm} meta FAILED: {r.get('error')}")
            continue
        meta = json.loads(r["_bytes"].decode("utf-8"))
        gj_url = meta.get("simplifiedGeometryGeoJSON") or meta.get("gjDownloadURL")
        if gj_url:
            rg = fetch_url(
                gj_url,
                dest=RAW_DIR / "common" / f"geoboundaries_{iso}_{adm}.geojson",
                city="common",
                layer="admin_boundaries_geojson",
                source_name=f"geoBoundaries {iso} {adm} GeoJSON",
                timeout=90,
            )
            print(f"[GB] {iso}/{adm} GeoJSON: ok={rg['ok']} bytes={rg.get('bytes')} err={rg.get('error')}")


def collect_worldbank_fx_macro():
    # World Bank Open Data API for SRB, HRV, BIH: GDP per capita (PPP & nominal), population, inflation, exchange rate
    indicators = [
        ("NY.GDP.PCAP.CD", "gdp_pcap_usd"),
        ("NY.GDP.PCAP.PP.CD", "gdp_pcap_ppp"),
        ("PA.NUS.FCRF", "fx_lcu_per_usd"),
        ("FP.CPI.TOTL.ZG", "inflation_pct"),
        ("SL.UEM.TOTL.ZS", "unemployment_pct"),
    ]
    for ind, slug in indicators:
        url = f"https://api.worldbank.org/v2/country/SRB;HRV;BIH/indicator/{ind}?format=json&per_page=100&date=2018:2025"
        r = fetch_url(
            url,
            dest=RAW_DIR / "common" / f"worldbank_{slug}.json",
            city="common",
            layer="macro_worldbank",
            source_name=f"World Bank {ind} (SRB, HRV, BIH)",
        )
        print(f"[WB] {slug}: ok={r['ok']} bytes={r.get('bytes')}")


if __name__ == "__main__":
    collect_bih_docs()
    collect_geoboundaries()
    collect_worldbank_fx_macro()
