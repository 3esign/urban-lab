import os, sys, json, urllib.request, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common_net import RAW_DIR, fetch_url

# 1. Check disk free space on C:
usage = shutil.disk_usage("C:\\")
print(f"C: free = {usage.free / (1024**3):.2f} GB / total = {usage.total / (1024**3):.2f} GB")

# 2. Check Geofabrik shapefile ZIP sizes (HEAD request)
for country in ["bosnia-herzegovina", "croatia", "serbia"]:
    url = f"https://download.geofabrik.de/europe/{country}-latest-free.shp.zip"
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "SvemirUrbanLab/2.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            cl = int(resp.headers.get("Content-Length", 0))
            print(f"  Geofabrik {country:20s} shp.zip: HTTP {resp.status}, {cl/(1024*1024):.1f} MB")
    except Exception as e:
        print(f"  Geofabrik {country:20s} ERR: {e}")

# 3. Download FZS ZDK (KantBr4.pdf) + check latest ZDK 2025
OUT_L = RAW_DIR / "wave2_l"
r_zdk = fetch_url("https://fzs.ba/Podaci/KantBr4.pdf", dest=OUT_L / "fzs_zdk_kantbr4.pdf", city="sarajevo", layer="wave2_l_hinterland", source_name="FZS ZDK u brojkama (KantBr4.pdf)", timeout=45)
print(f"  FZS ZDK KantBr4.pdf: ok={r_zdk.get('ok')} bytes={r_zdk.get('bytes',0):,}")

# 4. Extended Eurostat NUTS3 GDP with all ring regions
OUT_XL = RAW_DIR / "wave2_xl"
url_gdp = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nama_10r_3gdp"
    "?format=JSON&lang=EN&geo=HR050&geo=HR065&geo=HR064&geo=HR027&geo=HR028"
    "&geo=RS110&geo=RS122&geo=RS127&geo=RS215&geo=RS214&sinceTimePeriod=2018"
)
r_gdp = fetch_url(url_gdp, dest=OUT_XL / "eurostat_nama_10r_3gdp_full.json", city="common", layer="wave2_xl_eurostat", source_name="Eurostat NUTS3 GDP full 5-city regions", timeout=45)
print(f"  Eurostat NUTS3 GDP full: ok={r_gdp.get('ok')} bytes={r_gdp.get('bytes',0):,}")

# 5. Also ensure World Bank extended indicators are downloaded (in case task-40 stalled on old Eurostat)
WB_INDICATORS = {
    "wb_remittances_pct_gdp.json": ("BX.TRF.PWKR.DT.GD.ZS", "Personal remittances received (% GDP)"),
    "wb_trade_pct_gdp.json": ("NE.TRD.GNFS.ZS", "Trade (% of GDP)"),
    "wb_fdi_inflows_pct_gdp.json": ("BX.KLT.DINV.WD.GD.ZS", "FDI net inflows (% GDP)"),
    "wb_agriculture_pct_gdp.json": ("NV.AGR.TOTL.ZS", "Agriculture, forestry, fishing (% GDP)"),
    "wb_industry_pct_gdp.json": ("NV.IND.TOTL.ZS", "Industry incl. construction (% GDP)"),
    "wb_services_pct_gdp.json": ("NV.SRV.TOTL.ZS", "Services (% GDP)"),
    "wb_urban_pop_pct.json": ("SP.URB.TOTL.IN.ZS", "Urban population (% of total)"),
    "wb_exports_pct_gdp.json": ("NE.EXP.GNFS.ZS", "Exports of goods and services (% GDP)"),
    "wb_imports_pct_gdp.json": ("NE.IMP.GNFS.ZS", "Imports of goods and services (% GDP)"),
    "wb_forest_area_pct.json": ("AG.LND.FRST.ZS", "Forest area (% of land area)"),
    "wb_arable_land_pct.json": ("AG.LND.ARBL.ZS", "Arable land (% of land area)"),
}
for fn, (ind, desc) in WB_INDICATORS.items():
    p = OUT_XL / fn
    if p.exists() and p.stat().st_size > 200:
        continue
    url = f"https://api.worldbank.org/v2/country/SRB;HRV;BIH/indicator/{ind}?format=json&date=2015:2025&per_page=200"
    rr = fetch_url(url, dest=p, city="common", layer="wave2_xl_wb", source_name=f"World Bank {desc}", timeout=30)
    print(f"  WB {fn:30s}: ok={rr.get('ok')} {rr.get('bytes',0):,} B")
