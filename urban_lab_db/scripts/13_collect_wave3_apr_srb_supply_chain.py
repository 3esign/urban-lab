from _paths import rel  # putanje u manifestu su relativne na koren repozitorijuma
import gc, json, sys, time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common_net import RAW_DIR, fetch_url, append_manifest, sha256_file

OUT = RAW_DIR / "wave3"
OUT.mkdir(parents=True, exist_ok=True)

TARGET_NACE4 = {
    "1071": "bakery_bread_pastry",
    "1061": "grain_mill_products",
    "1072": "rusks_biscuits_preserved_pastry",
    "0111": "growing_cereals_oilseeds",
    "1610": "sawmilling_planing_wood",
    "0220": "logging_forestry",
}

def norm_sr(s):
    if not s: return ""
    t = str(s).upper().strip()
    for a, b in [("Č","C"),("Ć","C"),("Š","S"),("Ž","Z"),("Đ","DJ"),("DŽ","DZ")]:
        t = t.replace(a, b)
    return t

def iter_podaci(obj):
    p = obj.get("Podaci") if isinstance(obj, dict) else obj
    if isinstance(p, list):
        for x in p:
            yield None, x
    elif isinstance(p, dict):
        for k, v in p.items():
            yield k, v

def run():
    t0 = time.time()
    print("=== WAVE 3.1: APR PANCEVO + SERBIA NATIONAL BAKERY/MILL/GRAIN/WOOD SUPPLY CHAIN ===", flush=True)
    # 1. Fetch financial statements first, keep compact dict, then free raw bytes immediately
    print("  [1/3] Fetching APR financial statements...", flush=True)
    rf = fetch_url("https://openapi.apr.gov.rs/api/opendata/companies/financial-statements", save_manifest=False, timeout=120)
    if not rf["ok"]:
        print("  [FAIL] APR FI:", rf.get("error"))
        sys.exit(1)
    f_obj = json.loads(rf["_bytes"].decode("utf-8"))
    del rf
    fi_map = {}
    for k, v in iter_podaci(f_obj):
        if isinstance(v, dict):
            mb = str(v.get("MaticniBroj") or k or "").strip().zfill(8)
            if mb and mb != "00000000":
                fi_map[mb] = {
                    "BrojZaposlenih": v.get("ProsecanBrojZaposlenih") or v.get("BrojZaposlenih") or 0,
                    "PoslovniPrihod": v.get("PoslovniPrihodi") or v.get("PoslovniPrihod") or v.get("UkupniPrihodi") or 0,
                    "NetoDobitak": v.get("NetoDobitak") or 0,
                    "NetoGubitak": v.get("NetoGubitak") or 0,
                    "PoslovnaImovina": v.get("PoslovnaImovina") or v.get("UkupnaAktiva") or 0,
                    "Godina": v.get("Godina") or v.get("IzvestajnaGodina") or "",
                }
    del f_obj
    gc.collect()
    print(f"  -> FI loaded: {len(fi_map):,} companies (compact dict)", flush=True)

    # 2. Fetch companies
    print("  [2/3] Fetching APR companies...", flush=True)
    rc = fetch_url("https://openapi.apr.gov.rs/api/opendata/companies", save_manifest=False, timeout=120)
    if not rc["ok"]:
        print("  [FAIL] APR companies:", rc.get("error"))
        sys.exit(1)
    c_obj = json.loads(rc["_bytes"].decode("utf-8"))
    del rc
    presek = c_obj.get("DatumPreseka") if isinstance(c_obj, dict) else ""

    # First quick discovery of Pančevo municipality code(s)
    pancevo_codes = Counter()
    muni_code_to_name = {}
    all_rows_ref = c_obj.get("Podaci") if isinstance(c_obj, dict) else c_obj
    sample_keys = None

    for k, v in iter_podaci(c_obj):
        if not isinstance(v, dict): continue
        if sample_keys is None:
            sample_keys = list(v.keys())
            print("  Sample company keys:", sample_keys, flush=True)
        mc = str(v.get("SifraOpstine") or v.get("OpstinaSifra") or "").strip()
        mn = str(v.get("NazivOpstine") or v.get("OpstinaNaziv") or "").strip()
        mesto = str(v.get("Mesto") or v.get("SedisteMesto") or v.get("NazivMesta") or "").strip()
        if mc and mn and mc not in muni_code_to_name:
            muni_code_to_name[mc] = mn
        mn_n = norm_sr(mn)
        me_n = norm_sr(mesto)
        if "PANCEV" in mn_n or me_n == "PANCEVO" or me_n in ("STARCEVO", "OMOLJICA", "KACAREVO", "JABUKA", "BANATSKI BRESTOVAC", "GLOGONJ", "DOLOVO"):
            if mc.startswith("80"):
                pancevo_codes[(mc, mn, me_n)] += 1

    print("  Discovered Pančevo (code, opstina, mesto) top matches:", pancevo_codes.most_common(10), flush=True)
    # Determine authoritative Pančevo code(s):
    pa_code_counts = Counter()
    for (mc, mn, me), cnt in pancevo_codes.items():
        if "PANCEV" in norm_sr(mn) or me == "PANCEVO":
            pa_code_counts[mc] += cnt
    PANCEVO_CODES = {mc for mc, cnt in pa_code_counts.items() if cnt >= 50}
    if not PANCEVO_CODES:
        PANCEVO_CODES = {"80292", "80284"}
    print(f"  Selected Pančevo SifraOpstine: {sorted(PANCEVO_CODES)} (counts={dict(pa_code_counts)})", flush=True)

    # 3. Single pass extraction: Pančevo companies + National supply chain
    print("  [3/3] Extracting Pančevo + National supply chain (1071, 1061, 1072, 0111, 1610, 0220)...", flush=True)
    out_pa = OUT / "apr_pancevo_companies.jsonl"
    out_sc = OUT / "apr_serbia_supply_chain_all.jsonl"
    out_sc_sum = OUT / "apr_serbia_supply_chain_summary.json"

    pa_count = 0
    pa_with_fi = 0
    pa_emp = 0
    pa_rev = 0.0
    pa_nace = Counter()

    sc_count = 0
    sc_by_nace = defaultdict(lambda: {"companies": 0, "with_fi": 0, "employees": 0, "revenue_k_rsd": 0.0, "net_profit_k_rsd": 0.0})
    sc_by_muni = defaultdict(lambda: {
        "muni_code": "", "muni_name": "", "total_firms": 0, "employees": 0, "revenue_k_rsd": 0.0,
        "bakery_1071": 0, "mill_1061": 0, "biscuit_1072": 0, "grain_0111": 0, "sawmill_1610": 0, "logging_0220": 0,
        "mill_rev_k_rsd": 0.0, "bakery_rev_k_rsd": 0.0, "grain_rev_k_rsd": 0.0, "wood_rev_k_rsd": 0.0
    })

    with open(out_pa, "w", encoding="utf-8") as f_pa, open(out_sc, "w", encoding="utf-8") as f_sc:
        for k, v in iter_podaci(c_obj):
            if not isinstance(v, dict): continue
            mc = str(v.get("SifraOpstine") or v.get("OpstinaSifra") or "").strip()
            mn = str(v.get("NazivOpstine") or v.get("OpstinaNaziv") or muni_code_to_name.get(mc) or "").strip()
            nace = str(v.get("SifraDelatnosti") or "").strip()
            mb = str(v.get("MaticniBroj") or k or "").strip().zfill(8)
            fi = fi_map.get(mb)

            is_pa = mc in PANCEVO_CODES
            is_sc = nace in TARGET_NACE4

            if is_pa or is_sc:
                rec = dict(v)
                rec.setdefault("MaticniBroj", mb)
                if fi:
                    rec["fi"] = fi
                emp = int(float(fi["BrojZaposlenih"] or 0)) if fi else 0
                rev = float(fi["PoslovniPrihod"] or 0) if fi else 0.0
                npf = (float(fi["NetoDobitak"] or 0) - float(fi["NetoGubitak"] or 0)) if fi else 0.0

                if is_pa:
                    rec["_ring"] = "beograd_ring"
                    rec["_muni_label"] = "Pančevo"
                    f_pa.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    pa_count += 1
                    pa_nace[nace[:2]] += 1
                    if fi:
                        pa_with_fi += 1
                        pa_emp += emp
                        pa_rev += rev

                if is_sc:
                    rec["_sc_role"] = TARGET_NACE4[nace]
                    f_sc.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    sc_count += 1
                    st = sc_by_nace[nace]
                    st["companies"] += 1
                    if fi:
                        st["with_fi"] += 1
                        st["employees"] += emp
                        st["revenue_k_rsd"] += rev
                        st["net_profit_k_rsd"] += npf

                    ms = sc_by_muni[mc]
                    ms["muni_code"] = mc
                    if mn and not ms["muni_name"]:
                        ms["muni_name"] = mn
                    elif not ms["muni_name"]:
                        ms["muni_name"] = str(v.get("Mesto") or mc)
                    ms["total_firms"] += 1
                    ms["employees"] += emp
                    ms["revenue_k_rsd"] += rev
                    if nace == "1071":
                        ms["bakery_1071"] += 1
                        ms["bakery_rev_k_rsd"] += rev
                    elif nace == "1061":
                        ms["mill_1061"] += 1
                        ms["mill_rev_k_rsd"] += rev
                    elif nace == "1072":
                        ms["biscuit_1072"] += 1
                        ms["bakery_rev_k_rsd"] += rev
                    elif nace == "0111":
                        ms["grain_0111"] += 1
                        ms["grain_rev_k_rsd"] += rev
                    elif nace == "1610":
                        ms["sawmill_1610"] += 1
                        ms["wood_rev_k_rsd"] += rev
                    elif nace == "0220":
                        ms["logging_0220"] += 1
                        ms["wood_rev_k_rsd"] += rev

    del c_obj, fi_map
    gc.collect()

    summary = {
        "presek": presek,
        "pancevo": {
            "codes": sorted(PANCEVO_CODES),
            "companies": pa_count,
            "with_fi": pa_with_fi,
            "employees": pa_emp,
            "revenue_k_rsd": round(pa_rev, 2),
            "revenue_eur_m": round(pa_rev / 117.0 / 1000.0, 2),
            "top_nace2": dict(pa_nace.most_common(12)),
        },
        "national_supply_chain": {
            "total_companies": sc_count,
            "by_nace": {k: {**v, "role": TARGET_NACE4[k], "revenue_eur_m": round(v["revenue_k_rsd"]/117.0/1000.0, 2)} for k, v in sorted(sc_by_nace.items())},
            "municipalities_count": len(sc_by_muni),
            "by_municipality": sorted(sc_by_muni.values(), key=lambda x: -x["revenue_k_rsd"]),
        }
    }
    out_sc_sum.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    for city, layer, p, desc in [
        ("beograd", "hinterland_apr_pancevo", out_pa, f"APR Open Data Pančevo ({pa_count} firms, {pa_emp} emp, presek {presek})"),
        ("common", "serbia_national_supply_chain_apr", out_sc, f"APR Open Data Serbia National Supply Chain 1071/1061/1072/0111/1610/0220 ({sc_count} firms, presek {presek})"),
    ]:
        append_manifest({
            "ok": True, "city": city, "layer": layer, "source_name": desc,
            "url": "https://openapi.apr.gov.rs/api/opendata/companies",
            "http_status": 200, "bytes": p.stat().st_size, "sha256": sha256_file(p), "local_path": rel(p)
        })

    print(f"\n[OK] Pančevo: {pa_count:,} companies (with FI={pa_with_fi:,}), emp={pa_emp:,}, rev={pa_rev/117000:,.1f} M EUR", flush=True)
    print(f"[OK] National Supply Chain: {sc_count:,} companies across {len(sc_by_muni)} municipalities:", flush=True)
    for k, v in summary["national_supply_chain"]["by_nace"].items():
        print(f"    NACE {k} ({v['role']:32s}): {v['companies']:>5,} firms | emp={v['employees']:>6,} | rev={v['revenue_eur_m']:>8.1f} M EUR", flush=True)
    print(f"Elapsed: {time.time()-t0:.1f}s", flush=True)

if __name__ == "__main__":
    run()
