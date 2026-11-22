import re, json, urllib.request, urllib.parse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from common_net import RAW_DIR, fetch_url

OUT = RAW_DIR / "wave2_l"

# 1. Inspect FZS Kantoni index PDFs and download ZDK
html = (OUT / "fzs_kantoni_index.html").read_text(encoding="utf-8", errors="replace")
pdfs = re.findall(r'href=["\']([^"\']+\.pdf)["\']', html, flags=re.I)
print("FZS Kantoni PDFs:")
for u in pdfs:
    print(" ", u)
for u in pdfs:
    if any(k in u.lower() for k in ["zdk", "zenic", "dobojs"]):
        full = urllib.parse.urljoin("https://fzs.ba/", u)
        r = fetch_url(full, dest=OUT / "fzs_zdk_2025.pdf", city="sarajevo", layer="wave2_l_hinterland", source_name="FZS ZDK u brojkama PDF", timeout=45)
        print("Downloaded ZDK:", r.get("ok"), r.get("bytes"), full)
        break

# 2. Test Eurostat URL directly to see exact error / response
test_urls = [
    ("nama_10r_3gdp", "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nama_10r_3gdp?format=JSON&lang=EN&geo=HR050&geo=HR065&geo=RS110&geo=RS215&sinceTimePeriod=2019"),
    ("nrg_pc_205", "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nrg_pc_205?format=JSON&lang=EN&currency=EUR&geo=HR&geo=RS&geo=BA&sinceTimePeriod=2022"),
    ("nrg_pc_203", "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nrg_pc_203?format=JSON&lang=EN&currency=EUR&geo=HR&geo=RS&geo=BA&sinceTimePeriod=2022"),
    ("urb_lpop1", "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/urb_lpop1?format=JSON&lang=EN&cities=HR001F&cities=RS001F&sinceTimePeriod=2018"),
    ("earn_mw_cur", "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/earn_mw_cur?format=JSON&lang=EN&currency=EUR&geo=HR&geo=RS&sinceTimePeriod=2020"),
    ("tour_occ_nin2", "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/tour_occ_nin2?format=JSON&lang=EN&c_resid=TOTAL&unit=NR&geo=HR05&geo=HR06&geo=RS11&geo=RS21&sinceTimePeriod=2019"),
    ("avia_paoa", "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/avia_paoa?format=JSON&lang=EN&unit=PAS&tra_meas=PAS_CRD&geo=HR&geo=RS&sinceTimePeriod=2019"),
]
OUT_XL = RAW_DIR / "wave2_xl"
OUT_XL.mkdir(parents=True, exist_ok=True)
print("\nDirect Eurostat retries:")
for name, url in test_urls:
    r = fetch_url(url, dest=OUT_XL / f"eurostat_{name}.json", city="common", layer="wave2_xl_eurostat", source_name=f"Eurostat {name}", timeout=45)
    print(f"  {name:18s} | ok={r.get('ok')} | status={r.get('http_status')} | bytes={r.get('bytes',0):>9,} | err={str(r.get('error',''))[:70]}")
