from _paths import rel  # putanje u manifestu su relativne na koren repozitorijuma
import gc, json, sys, time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common_net import RAW_DIR, fetch_url, append_manifest, sha256_file

OUT = RAW_DIR / "wave3"
OUT.mkdir(parents=True, exist_ok=True)

# 100% verified against RZS Opstine_dashboard & APR NazivOpstine (Cyrillic):
BG_RING_CODES = {
    "80314": "Pančevo",
    "80420": "Stara Pazova",
    "80179": "Inđija",
    "80322": "Pećinci",
    "80357": "Ruma",
    "71099": "Smederevo",
    "70360": "Valjevo",
}
NP_RING_CODES = {
    "71188": "Tutin",
    "71072": "Sjenica",
    "71021": "Raška",
}

def iter_podaci(obj):
    p = obj.get("Podaci") if isinstance(obj, dict) else obj
    if isinstance(p, list):
        for x in p: yield None, x
    elif isinstance(p, dict):
        for k, v in p.items(): yield k, v

def run():
    t0 = time.time()
    print("=== WAVE 3.1b: EXACT RZS-VERIFIED APR HINTERLAND (Pančevo + BG ring + NP ring) ===", flush=True)
    rf = fetch_url("https://openapi.apr.gov.rs/api/opendata/companies/financial-statements", save_manifest=False, timeout=120)
    if not rf["ok"]:
        print("[FAIL] FI:", rf.get("error")); sys.exit(1)
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
                }
    del f_obj; gc.collect()

    rc = fetch_url("https://openapi.apr.gov.rs/api/opendata/companies", save_manifest=False, timeout=120)
    if not rc["ok"]:
        print("[FAIL] Comp:", rc.get("error")); sys.exit(1)
    c_obj = json.loads(rc["_bytes"].decode("utf-8"))
    del rc
    presek = c_obj.get("DatumPreseka") if isinstance(c_obj, dict) else ""

    out_bg = OUT / "apr_beograd_hinterland_v3.jsonl"
    out_np = OUT / "apr_novi_pazar_hinterland_v3.jsonl"
    out_sum = OUT / "apr_hinterland_v3_summary.json"

    muni_stats = {}
    bg_cnt = np_cnt = 0
    with open(out_bg, "w", encoding="utf-8") as f_bg, open(out_np, "w", encoding="utf-8") as f_np:
        for k, v in iter_podaci(c_obj):
            if not isinstance(v, dict): continue
            mc = str(v.get("SifraOpstine") or "").strip()
            if mc in BG_RING_CODES:
                ring = "beograd"
                label = BG_RING_CODES[mc]
            elif mc in NP_RING_CODES:
                ring = "novi_pazar"
                label = NP_RING_CODES[mc]
            else:
                continue

            mb = str(v.get("MaticniBroj") or k or "").strip().zfill(8)
            fi = fi_map.get(mb)
            rec = dict(v)
            rec.setdefault("MaticniBroj", mb)
            rec["_ring"] = ring
            rec["_muni_label"] = label
            if fi: rec["fi"] = fi

            if ring == "beograd":
                f_bg.write(json.dumps(rec, ensure_ascii=False) + "\n")
                bg_cnt += 1
            else:
                f_np.write(json.dumps(rec, ensure_ascii=False) + "\n")
                np_cnt += 1

            st = muni_stats.setdefault(mc, {
                "city_hub": ring, "muni_code": mc, "muni_name": label, "apr_name": v.get("NazivOpstine", ""),
                "companies": 0, "with_fi": 0, "employees": 0, "revenue_k_rsd": 0.0,
                "bakery_1071": 0, "mill_1061": 0, "grain_0111": 0, "wood_02_16": 0
            })
            st["companies"] += 1
            nace = str(v.get("SifraDelatnosti") or "").strip()
            if nace == "1071": st["bakery_1071"] += 1
            elif nace == "1061": st["mill_1061"] += 1
            elif nace == "0111": st["grain_0111"] += 1
            elif nace.startswith(("02", "16")): st["wood_02_16"] += 1
            if fi:
                st["with_fi"] += 1
                try: st["employees"] += int(float(fi["BrojZaposlenih"] or 0))
                except: pass
                try: st["revenue_k_rsd"] += float(fi["PoslovniPrihod"] or 0)
                except: pass

    del c_obj, fi_map; gc.collect()

    summary = {"presek": presek, "bg_ring_count": bg_cnt, "np_ring_count": np_cnt, "municipalities": list(muni_stats.values())}
    out_sum.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    for city, p, cnt in [("beograd", out_bg, bg_cnt), ("novi_pazar", out_np, np_cnt)]:
        append_manifest({
            "ok": True, "city": city, "layer": "hinterland_apr_rgfi_v3_verified",
            "source_name": f"APR Hinterland v3 RZS-verified codes ({city} ring: {cnt} firms, incl. Pančevo 80314, presek {presek})",
            "url": "https://openapi.apr.gov.rs/api/opendata/companies",
            "http_status": 200, "bytes": p.stat().st_size, "sha256": sha256_file(p), "local_path": rel(p)
        })

    print(f"[OK] BG ring={bg_cnt:,}, NP ring={np_cnt:,} (elapsed {time.time()-t0:.1f}s)")
    for st in sorted(muni_stats.values(), key=lambda x: (x["city_hub"], -x["companies"])):
        print(f"  {st['city_hub']:10s} | {st['muni_code']} {st['muni_name']:14s} ({st['apr_name']:14s}) | firms={st['companies']:>5,} | fi={st['with_fi']:>5,} | emp={st['employees']:>6,} | rev={st['revenue_k_rsd']/117000:>7.1f} M EUR | bak={st['bakery_1071']} mill={st['mill_1061']} grain={st['grain_0111']} wood={st['wood_02_16']}")

if __name__ == "__main__":
    run()
