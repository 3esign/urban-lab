import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_net import RAW_DIR, fetch_url

OUT_DIR = RAW_DIR / "wave4" / "sensors"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 5 core cities + 2 ES-03 control/sub-city points (Ilidza & Istocno Sarajevo)
SENSOR_POINTS = [
    ("beograd", "beograd_cbd", 44.8125, 20.4612),
    ("zagreb", "zagreb_cbd", 45.8131, 15.9775),
    ("sarajevo", "sarajevo_centar", 43.8563, 18.4131),
    ("sarajevo", "sarajevo_ilidza", 43.8294, 18.3090),
    ("sarajevo", "istocno_sarajevo_control", 43.8220, 18.3680),
    ("novi_pazar", "novi_pazar_cbd", 43.1367, 20.5122),
    ("travnik", "travnik_cbd", 44.2264, 17.6658),
]

START_DATE = "2024-01-01"
END_DATE = "2026-10-31"


def fetch_json(url: str, dest: Path, city: str, source_name: str):
    r = fetch_url(url, dest=dest, city=city, layer="wave4_sensors", source_name=source_name, timeout=45, retries=2)
    if not r["ok"]:
        print(f"  [FAIL] {source_name}: {r.get('error')}")
        return None
    raw = r.pop("_bytes", b"")
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        print(f"  [JSON ERR] {source_name}: {e}")
        return None


def main():
    monthly_air = []
    monthly_weather = []

    print("=== 1. Open-Meteo Air Quality (2024-01 to 2026-10) for 5 Cities + ES-03 Points ===")
    for city_id, pt_id, lat, lon in SENSOR_POINTS:
        # Air Quality API supports historical range from mid-2022 onwards
        url_aq = (
            f"https://air-quality-api.open-meteo.com/v1/air-quality"
            f"?latitude={lat}&longitude={lon}"
            f"&hourly=pm10,pm2_5,nitrogen_dioxide,sulphur_dioxide,european_aqi"
            f"&start_date={START_DATE}&end_date={END_DATE}&timezone=UTC"
        )
        data = fetch_json(url_aq, OUT_DIR / f"openmeteo_aq_{pt_id}.json", city_id, f"openmeteo_aq_{pt_id}")
        time.sleep(0.3)
        if data and "hourly" in data:
            h = data["hourly"]
            times = h.get("time") or []
            pm25 = h.get("pm2_5") or []
            pm10 = h.get("pm10") or []
            no2 = h.get("nitrogen_dioxide") or []
            so2 = h.get("sulphur_dioxide") or []
            eaqi = h.get("european_aqi") or []
            by_month = defaultdict(lambda: {"pm25": [], "pm10": [], "no2": [], "so2": [], "eaqi": [], "pm25_exceed_25": 0})
            for i, ts in enumerate(times):
                ym = ts[:7]
                if i < len(pm25) and pm25[i] is not None:
                    by_month[ym]["pm25"].append(pm25[i])
                    if pm25[i] > 25.0:
                        by_month[ym]["pm25_exceed_25"] += 1
                if i < len(pm10) and pm10[i] is not None:
                    by_month[ym]["pm10"].append(pm10[i])
                if i < len(no2) and no2[i] is not None:
                    by_month[ym]["no2"].append(no2[i])
                if i < len(so2) and so2[i] is not None:
                    by_month[ym]["so2"].append(so2[i])
                if i < len(eaqi) and eaqi[i] is not None:
                    by_month[ym]["eaqi"].append(eaqi[i])
            for ym in sorted(by_month.keys()):
                b = by_month[ym]
                if not b["pm25"]:
                    continue
                monthly_air.append({
                    "city_id": city_id,
                    "point_id": pt_id,
                    "lat": lat,
                    "lon": lon,
                    "month": ym,
                    "hours_n": len(b["pm25"]),
                    "pm25_mean_ugm3": round(sum(b["pm25"]) / len(b["pm25"]), 2),
                    "pm25_p95_ugm3": round(sorted(b["pm25"])[int(0.95 * (len(b["pm25"]) - 1))], 2),
                    "pm25_exceed_25_hours": b["pm25_exceed_25"],
                    "pm10_mean_ugm3": round(sum(b["pm10"]) / len(b["pm10"]), 2) if b["pm10"] else None,
                    "no2_mean_ugm3": round(sum(b["no2"]) / len(b["no2"]), 2) if b["no2"] else None,
                    "so2_mean_ugm3": round(sum(b["so2"]) / len(b["so2"]), 2) if b["so2"] else None,
                    "eaqi_mean": round(sum(b["eaqi"]) / len(b["eaqi"]), 2) if b["eaqi"] else None,
                })
            print(f"  + AQ {pt_id:25s}: {len(by_month)} months, {len(times)} hourly points")

    print("\n=== 2. Open-Meteo Archive Weather & Heating Degree Days (2024-01 to 2026-10) ===")
    for city_id, pt_id, lat, lon in SENSOR_POINTS[:5] + SENSOR_POINTS[5:]:
        if pt_id in ("sarajevo_ilidza", "istocno_sarajevo_control"):
            continue
        url_wx = (
            f"https://archive-api.open-meteo.com/v1/archive"
            f"?latitude={lat}&longitude={lon}"
            f"&daily=temperature_2m_mean,temperature_2m_max,temperature_2m_min,precipitation_sum"
            f"&start_date={START_DATE}&end_date={END_DATE}&timezone=UTC"
        )
        data = fetch_json(url_wx, OUT_DIR / f"openmeteo_wx_{pt_id}.json", city_id, f"openmeteo_wx_{pt_id}")
        time.sleep(0.3)
        if data and "daily" in data:
            d = data["daily"]
            dates = d.get("time") or []
            tmean = d.get("temperature_2m_mean") or []
            tmax = d.get("temperature_2m_max") or []
            tmin = d.get("temperature_2m_min") or []
            prec = d.get("precipitation_sum") or []
            by_m = defaultdict(lambda: {"tmean": [], "hdd18": 0.0, "cdd24": 0.0, "prec": 0.0, "frost_days": 0, "heat35_days": 0})
            for i, dt in enumerate(dates):
                ym = dt[:7]
                if i < len(tmean) and tmean[i] is not None:
                    tm = tmean[i]
                    by_m[ym]["tmean"].append(tm)
                    by_m[ym]["hdd18"] += max(0.0, 18.0 - tm)
                    by_m[ym]["cdd24"] += max(0.0, tm - 24.0)
                if i < len(tmin) and tmin[i] is not None and tmin[i] < 0.0:
                    by_m[ym]["frost_days"] += 1
                if i < len(tmax) and tmax[i] is not None and tmax[i] >= 35.0:
                    by_m[ym]["heat35_days"] += 1
                if i < len(prec) and prec[i] is not None:
                    by_m[ym]["prec"] += prec[i]
            for ym in sorted(by_m.keys()):
                b = by_m[ym]
                if not b["tmean"]:
                    continue
                monthly_weather.append({
                    "city_id": city_id,
                    "point_id": pt_id,
                    "month": ym,
                    "days_n": len(b["tmean"]),
                    "temp_mean_c": round(sum(b["tmean"]) / len(b["tmean"]), 2),
                    "hdd_18c": round(b["hdd18"], 1),
                    "cdd_24c": round(b["cdd24"], 1),
                    "precip_mm": round(b["prec"], 1),
                    "frost_days": b["frost_days"],
                    "heat35_days": b["heat35_days"],
                })
            print(f"  + WX {pt_id:25s}: {len(by_m)} months, {len(dates)} daily points")

    print("\n=== 3. World Bank Macro & Diaspora Remittances Panel (SRB, HRV, BIH 2015-2025) ===")
    WB_INDICATORS = [
        ("BX.TRF.PWKR.CD.DT", "remittances_received_usd"),
        ("BX.TRF.PWKR.DT.GD.ZS", "remittances_pct_gdp"),
        ("FP.CPI.TOTL.ZG", "inflation_cpi_pct"),
        ("GB.XPD.RSDV.GD.ZS", "rd_expenditure_pct_gdp"),
        ("ST.INT.ARVL", "intl_tourism_arrivals"),
        ("FS.AST.PRVT.GD.ZS", "domestic_credit_private_pct_gdp"),
        ("IT.NET.BBND.P2", "fixed_broadband_per_100"),
        ("NY.GDP.PCAP.PP.CD", "gdp_per_capita_ppp_usd"),
        ("SL.UEM.TOTL.ZS", "unemployment_ilo_pct"),
    ]
    wb_records = []
    for ind_code, ind_slug in WB_INDICATORS:
        url = f"https://api.worldbank.org/v2/country/SRB;HRV;BIH/indicator/{ind_code}?format=json&date=2015:2025&per_page=100"
        data = fetch_json(url, OUT_DIR / f"wb_{ind_slug}.json", "common", f"wb_{ind_slug}")
        time.sleep(0.2)
        if data and isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
            cnt = 0
            for row in data[1]:
                if row.get("value") is not None:
                    wb_records.append({
                        "country_iso3": row.get("countryiso3code"),
                        "indicator_code": ind_code,
                        "indicator_slug": ind_slug,
                        "year": int(row.get("date")),
                        "value": row.get("value"),
                    })
                    cnt += 1
            print(f"  + WB {ind_slug:32s}: {cnt} non-null observations")

    (OUT_DIR / "openmeteo_air_monthly_5cities.json").write_text(
        json.dumps(monthly_air, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "openmeteo_weather_monthly_5cities.json").write_text(
        json.dumps(monthly_weather, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "worldbank_diaspora_macro_3countries.json").write_text(
        json.dumps(wb_records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nDONE Sensors+WB: {len(monthly_air)} air-months, {len(monthly_weather)} weather-months, {len(wb_records)} WB rows.")


if __name__ == "__main__":
    main()
