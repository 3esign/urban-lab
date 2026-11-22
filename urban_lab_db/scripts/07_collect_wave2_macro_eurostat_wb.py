from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import os, sys, json, time
sys.path.insert(0, os.path.dirname(__file__))
from common_net import fetch_url

def fetch_and_save(url, dest, city, desc, timeout=40):
    res = fetch_url(url, dest=dest, city=city, layer="wave2_xl", source_name=desc, timeout=timeout)
    return {"ok": res.get("ok"), "bytes": res.get("bytes", 0), "status": res.get("http_status")}

BASE = str(DB_DIR)
OUT = os.path.join(BASE, "raw", "wave2_xl")
os.makedirs(OUT, exist_ok=True)

# 1. Eurostat REST JSON API (official open API, no key required)
EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

eurostat_queries = [
    # NUTS3 Regional GDP (MIO_EUR and EUR_HAB and PPS_HAB) for Croatia & Serbia
    (
        "eurostat_nama_10r_3gdp_hr_rs.json",
        f"{EUROSTAT_BASE}/nama_10r_3gdp?format=JSON&lang=EN&unit=MIO_EUR&unit=EUR_HAB&unit=PPS_EU27_2020_HAB"
        "&geo=HR050&geo=HR065&geo=HR064&geo=HR027&geo=HR028"
        "&geo=RS110&geo=RS122&geo=RS127&geo=RS215&geo=RS214&geo=RS226"
        "&sinceTimePeriod=2018",
        "Eurostat NUTS3 GDP (Zagreb+ring, Belgrade+ring, Novi Pazar/Raska+Zlatibor)",
    ),
    # Non-household electricity prices (EUR/kWh, all taxes/levies excl VAT & incl) for HR, RS, BA
    (
        "eurostat_nrg_pc_205_elec_business.json",
        f"{EUROSTAT_BASE}/nrg_pc_205?format=JSON&lang=EN&currency=EUR&unit=KWH&nrg_cons=MWH20-499&nrg_cons=MWH_LT20"
        "&tax=X_TAX&tax=X_VAT&tax=I_TAX&geo=HR&geo=RS&geo=BA&sinceTimePeriod=2021",
        "Eurostat Business Electricity Prices (HR, RS, BA) for S-scale bakery energy cost",
    ),
    # Non-household gas prices (EUR/kWh) for HR, RS, BA
    (
        "eurostat_nrg_pc_203_gas_business.json",
        f"{EUROSTAT_BASE}/nrg_pc_203?format=JSON&lang=EN&currency=EUR&unit=KWH&nrg_cons=GJ_LT1000&nrg_cons=GJ1000-9999"
        "&tax=X_VAT&tax=I_TAX&geo=HR&geo=RS&geo=BA&sinceTimePeriod=2021",
        "Eurostat Business Gas Prices (HR, RS, BA)",
    ),
    # Functional Urban Area (FUA) population for Zagreb & Belgrade
    (
        "eurostat_urb_lpop1_fua_zg_bg.json",
        f"{EUROSTAT_BASE}/urb_lpop1?format=JSON&lang=EN&cities=HR001F&cities=RS001F&cities=HR001C&cities=RS001C&sinceTimePeriod=2015",
        "Eurostat FUA Population (Zagreb FUA & Belgrade FUA)",
    ),
    # Urban Audit tourism & transport for Zagreb & Belgrade
    (
        "eurostat_urb_ctour_zg_bg.json",
        f"{EUROSTAT_BASE}/urb_ctour?format=JSON&lang=EN&cities=HR001C&cities=RS001C&cities=HR001F&cities=RS001F&sinceTimePeriod=2018",
        "Eurostat Urban Audit Tourism (Zagreb & Belgrade)",
    ),
    (
        "eurostat_urb_ctran_zg_bg.json",
        f"{EUROSTAT_BASE}/urb_ctran?format=JSON&lang=EN&cities=HR001C&cities=RS001C&sinceTimePeriod=2018",
        "Eurostat Urban Audit Transport (Zagreb & Belgrade)",
    ),
    # Regional tourism nights spent at NUTS2 (HR05 Grad Zagreb, HR06 Sjeverna HR, RS11 Beograd, RS21 Sumadija i Zapadna Srbija)
    (
        "eurostat_tour_occ_nin2_hr_rs.json",
        f"{EUROSTAT_BASE}/tour_occ_nin2?format=JSON&lang=EN&c_resid=TOTAL&c_resid=FOR&unit=NR&nace_r2=I551-I553"
        "&geo=HR05&geo=HR06&geo=RS11&geo=RS21&geo=RS12&sinceTimePeriod=2019",
        "Eurostat NUTS2 Tourism Nights Spent (Zagreb, Belgrade, Sumadija/West Serbia)",
    ),
    # Minimum wages (semi-annual EUR) HR & RS
    (
        "eurostat_earn_mw_cur_hr_rs.json",
        f"{EUROSTAT_BASE}/earn_mw_cur?format=JSON&lang=EN&currency=EUR&geo=HR&geo=RS&sinceTimePeriod=2020",
        "Eurostat Minimum Wage EUR (HR, RS)",
    ),
    # Airport passengers (monthly/annual) HR & RS
    (
        "eurostat_avia_paoa_hr_rs.json",
        f"{EUROSTAT_BASE}/avia_paoa?format=JSON&lang=EN&unit=PAS&tra_meas=PAS_CRD&schedule=TOT&tra_cov=TOTAL"
        "&rep_airp=HR_LDZA&rep_airp=RS_LYBE&sinceTimePeriod=2019",
        "Eurostat Airport Passengers ZAG (LDZA) & BEG (LYBE)",
    ),
]

print("=== 1. EUROSTAT WAVE 2 ===")
for fn, url, desc in eurostat_queries:
    res = fetch_and_save(url, os.path.join(OUT, fn), "common", desc, timeout=40)
    print(f"  {fn:42s} | ok={res['ok']} | {res['bytes']:>9,} B | status={res['status']}")
    time.sleep(0.5)

# 2. World Bank extended XL indicators (SRB, HRV, BIH, 2015-2025)
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
    "wb_lpi_overall.json": ("LP.LPI.OVRL.XQ", "Logistics Performance Index (1-5)"),
    "wb_forest_area_pct.json": ("AG.LND.FRST.ZS", "Forest area (% of land area)"),
    "wb_arable_land_pct.json": ("AG.LND.ARBL.ZS", "Arable land (% of land area)"),
}

print("\n=== 2. WORLD BANK EXTENDED XL ===")
for fn, (ind, desc) in WB_INDICATORS.items():
    url = f"https://api.worldbank.org/v2/country/SRB;HRV;BIH/indicator/{ind}?format=json&date=2015:2025&per_page=200"
    res = fetch_and_save(url, os.path.join(OUT, fn), "common", f"World Bank {desc}", timeout=30)
    print(f"  {fn:34s} | ok={res['ok']} | {res['bytes']:>7,} B | status={res['status']}")
    time.sleep(0.25)

print("DONE 07_collect_wave2_macro_eurostat_wb.py")
