from _paths import rel  # putanje u manifestu su relativne na koren repozitorijuma
import os, sys, json, re, time, urllib.parse
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common_net import RAW_DIR, fetch_url, append_manifest, sha256_file

OUT = RAW_DIR / "wave2_l"
OUT.mkdir(parents=True, exist_ok=True)

# 1. APR Open Data: extract Hinterland municipalities for Belgrade & Novi Pazar
# Belgrade L-ring (Pančevo, Stara Pazova, Inđija, Pećinci, Ruma, Smederevo, Valjevo, Šabac)
# Novi Pazar L-ring (Tutin, Sjenica, Raška, Kraljevo)
HINTERLAND_TARGETS_SRB = {
    "beograd_ring": ["PANČEVO", "PANCEVO", "STARA PAZOVA", "INĐIJA", "INDJIJA", "PEĆINCI", "PECINCI", "RUMA", "SMEDEREVO", "VALJEVO"],
    "novi_pazar_ring": ["TUTIN", "SJENICA", "RAŠKA", "RASKA"],
}

def norm_sr(s):
    if not s: return ""
    t = s.upper().strip()
    for a, b in [("Č","C"),("Ć","C"),("Š","S"),("Ž","Z"),("Đ","DJ"),("DŽ","DZ")]:
        t = t.replace(a, b)
    return t

def collect_apr_hinterland():
    print("=== 1. APR HINTERLAND (BG ring + NP ring) + SUPPLY CHAIN NACE ===", flush=True)
    out_bg = OUT / "apr_beograd_hinterland.jsonl"
    out_np = OUT / "apr_novi_pazar_hinterland.jsonl"
    out_sum = OUT / "apr_hinterland_summary.json"
    if out_bg.exists() and out_np.exists() and out_sum.exists() and out_bg.stat().st_size > 10000:
        print("  [CACHED] APR hinterland already exists.")
        return

    rc = fetch_url("https://openapi.apr.gov.rs/api/opendata/companies", save_manifest=False, timeout=90)
    rf = fetch_url("https://openapi.apr.gov.rs/api/opendata/companies/financial-statements", save_manifest=False, timeout=90)
    if not rc["ok"] or not rf["ok"]:
        print("  [FAIL] APR:", rc.get("error"), rf.get("error"))
        return

    c_obj = json.loads(rc["_bytes"].decode("utf-8"))
    f_obj = json.loads(rf["_bytes"].decode("utf-8"))
    presek = c_obj.get("DatumPreseka")

    def iter_p(obj):
        p = obj.get("Podaci") if isinstance(obj, dict) else obj
        if isinstance(p, list):
            for x in p: yield None, x
        elif isinstance(p, dict):
            for k, v in p.items(): yield k, v

    fi_map = {}
    for k, v in iter_p(f_obj):
        if isinstance(v, dict):
            mb = str(v.get("MaticniBroj") or k or "").strip().zfill(8)
            fi_map[mb] = v
    del f_obj

    # Find municipality codes dynamically from NazivOpstine or SifraOpstine
    bg_targets = {"PANCEVO", "STARA PAZOVA", "INDJIJA", "PECINCI", "RUMA", "SMEDEREVO", "VALJEVO"}
    np_targets = {"TUTIN", "SJENICA", "RASKA"}
    # Known RZS municipality codes as fallback
    BG_RING_CODES = {"80284": "Pančevo", "80411": "Stara Pazova", "80152": "Inđija", "80314": "Pećinci", "80357": "Ruma", "71099": "Smederevo", "70289": "Valjevo"}
    NP_RING_CODES = {"71200": "Tutin", "71064": "Sjenica", "71013": "Raška"}

    bg_rows, np_rows = [], []
    muni_stats = {}

    for k, v in iter_p(c_obj):
        if not isinstance(v, dict): continue
        mc = str(v.get("SifraOpstine") or v.get("OpstinaSifra") or "").strip()
        mn = str(v.get("NazivOpstine") or v.get("OpstinaNaziv") or "").strip()
        mn_n = norm_sr(mn)
        ring = None
        label = mn or BG_RING_CODES.get(mc) or NP_RING_CODES.get(mc) or mc
        if mc in BG_RING_CODES or any(t == mn_n or mn_n.startswith(t + " ") for t in bg_targets):
            ring = "beograd_ring"
            label = BG_RING_CODES.get(mc, mn)
        elif mc in NP_RING_CODES or any(t == mn_n or mn_n.startswith(t + " ") for t in np_targets):
            ring = "novi_pazar_ring"
            label = NP_RING_CODES.get(mc, mn)

        if ring:
            mb = str(v.get("MaticniBroj") or k or "").strip().zfill(8)
            rec = dict(v)
            rec.setdefault("MaticniBroj", mb)
            rec["_ring"] = ring
            rec["_muni_label"] = label
            fi = fi_map.get(mb)
            if fi:
                rec["fi"] = fi
            if ring == "beograd_ring": bg_rows.append(rec)
            else: np_rows.append(rec)

            st = muni_stats.setdefault(f"{ring}|{mc}|{label}", {
                "ring": ring, "code": mc, "name": label, "companies": 0, "with_fi": 0,
                "employees": 0, "revenue_k_rsd": 0, "bakery_1071": 0, "mill_1061": 0, "grain_0111": 0, "wood_02_16": 0
            })
            st["companies"] += 1
            nace = str(v.get("SifraDelatnosti") or "").strip()
            if nace == "1071": st["bakery_1071"] += 1
            elif nace == "1061": st["mill_1061"] += 1
            elif nace == "0111": st["grain_0111"] += 1
            elif nace.startswith(("02", "16")): st["wood_02_16"] += 1
            if fi:
                st["with_fi"] += 1
                try: st["employees"] += int(fi.get("BrojZaposlenih") or 0)
                except: pass
                try: st["revenue_k_rsd"] += float(fi.get("PoslovniPrihod") or fi.get("UkupniPrihodi") or 0)
                except: pass

    del c_obj, fi_map

    with open(out_bg, "w", encoding="utf-8") as f:
        for r in bg_rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(out_np, "w", encoding="utf-8") as f:
        for r in np_rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")

    summary = {"presek": presek, "bg_ring_count": len(bg_rows), "np_ring_count": len(np_rows), "municipalities": list(muni_stats.values())}
    out_sum.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    for city, p, cnt in [("beograd", out_bg, len(bg_rows)), ("novi_pazar", out_np, len(np_rows))]:
        append_manifest({
            "ok": True, "city": city, "layer": "hinterland_apr_rgfi",
            "source_name": f"APR Hinterland Companies + RGFI ({city} ring: {cnt} firms, presek {presek})",
            "url": "https://openapi.apr.gov.rs/api/opendata/companies",
            "http_status": 200, "bytes": p.stat().st_size, "sha256": sha256_file(p), "local_path": rel(p)
        })
    print(f"  [OK] BG ring={len(bg_rows)}, NP ring={len(np_rows)}")
    for st in sorted(muni_stats.values(), key=lambda x: (x["ring"], -x["companies"])):
        print(f"    {st['ring']:15s} | {st['code']:5s} {st['name']:16s} | firms={st['companies']:>5} | emp={st['employees']:>6} | rev={st['revenue_k_rsd']/1e6:>7.1f}M RSD | bak={st['bakery_1071']} mill={st['mill_1061']} grain={st['grain_0111']} wood={st['wood_02_16']}")


# 2. RZS Popis 2022 Excel tables (Daily commuting / Dnevne migracije) + Popis poljoprivrede 2023
def collect_rzs_commuting_and_agri():
    print("\n=== 2. RZS POPIS 2022 COMMUTING + POPIS POLJOPRIVREDE 2023 ===", flush=True)
    r_idx = fetch_url("https://popis2022.stat.gov.rs/sr-latn/popisni-podaci-eksel-tabele/", dest=OUT/"rzs_popis2022_excel_index.html", city="common", layer="wave2_l", source_name="RZS Popis 2022 Excel tables index", timeout=35)
    if r_idx["ok"]:
        html = (OUT/"rzs_popis2022_excel_index.html").read_text(encoding="utf-8", errors="replace")
        links = re.findall(r'href=["\']([^"\']+\.xlsx?)["\']', html, flags=re.I)
        print(f"  Found {len(links)} Excel links on popis2022.stat.gov.rs")
        comm_links = [l for l in links if any(k in l.lower() for k in ["dnevn", "migra", "radn", "ekonom", "zapos", "delatn"])]
        print("  Commuting/economic links:", comm_links[:12])
        for i, lk in enumerate(comm_links[:6]):
            full = urllib.parse.urljoin("https://popis2022.stat.gov.rs/sr-latn/popisni-podaci-eksel-tabele/", lk)
            fn = re.sub(r'[^a-zA-Z0-9._-]+', '_', os.path.basename(urllib.parse.urlparse(full).path))
            res = fetch_url(full, dest=OUT/f"rzs_popis2022_{fn}", city="common", layer="wave2_l_commuting", source_name=f"RZS Popis 2022 Excel: {fn}", timeout=40)
            print(f"    {fn[:45]:45s} | ok={res['ok']} | {res.get('bytes',0):>9,} B")

    r_ag = fetch_url("https://popispoljoprivrede.stat.gov.rs/sr-Latn/rezultati/", dest=OUT/"rzs_popis_poljoprivrede_2023.html", city="common", layer="wave2_l", source_name="RZS Popis poljoprivrede 2023 results page", timeout=35)
    if not r_ag["ok"]:
        r_ag = fetch_url("https://popispoljoprivrede.stat.gov.rs/", dest=OUT/"rzs_popis_poljoprivrede_2023.html", city="common", layer="wave2_l", source_name="RZS Popis poljoprivrede 2023 home", timeout=35)
    if r_ag["ok"]:
        html = (OUT/"rzs_popis_poljoprivrede_2023.html").read_text(encoding="utf-8", errors="replace")
        links = re.findall(r'href=["\']([^"\']+\.(?:xlsx?|pdf))["\']', html, flags=re.I)
        print(f"  Found {len(links)} links on popispoljoprivrede.stat.gov.rs:", links[:8])
        for lk in links[:4]:
            full = urllib.parse.urljoin("https://popispoljoprivrede.stat.gov.rs/", lk)
            fn = re.sub(r'[^a-zA-Z0-9._-]+', '_', os.path.basename(urllib.parse.urlparse(full).path))
            res = fetch_url(full, dest=OUT/f"rzs_agri2023_{fn}", city="common", layer="wave2_l_agriculture", source_name=f"RZS Popis poljoprivrede 2023: {fn}", timeout=40)
            print(f"    {fn[:45]:45s} | ok={res['ok']} | {res.get('bytes',0):>9,} B")


# 3. Zagreb & Croatia CKAN: Poslovni prostori (rents!), Trznice (markets!), Gospodarske zone, Zagrebacka zupanija
def collect_zagreb_ckan_wave2():
    print("\n=== 3. ZAGREB & HR CKAN (poslovni prostori, trznice, ZET, Zagrebacka zupanija) ===", flush=True)
    searches = [
        ("zagreb_poslovni_prostori", "https://data.zagreb.hr/api/3/action/package_search?q=poslovni+prostor&rows=10"),
        ("zagreb_trznice", "https://data.zagreb.hr/api/3/action/package_search?q=trznice&rows=10"),
        ("zagreb_turizam_promet", "https://data.zagreb.hr/api/3/action/package_search?q=promet+ili+turizam&rows=10"),
        ("zagreb_gospodarstvo", "https://data.zagreb.hr/api/3/action/package_search?q=gospodar&rows=10"),
        ("hr_zagrebacka_zupanija", "https://data.gov.hr/ckan/api/3/action/package_search?q=zagrebacka+zupanija&rows=12"),
        ("hr_poljoprivreda_opg", "https://data.gov.hr/ckan/api/3/action/package_search?q=upisnik+poljoprivrednika&rows=6"),
    ]
    downloaded = 0
    for tag, url in searches:
        dest = OUT / f"ckan_{tag}.json"
        r = fetch_url(url, dest=dest, city="zagreb", layer="wave2_ckan", source_name=f"CKAN search {tag}", timeout=30)
        if not r["ok"]:
            print(f"  [FAIL] {tag}")
            continue
        try:
            d = json.loads(dest.read_text(encoding="utf-8", errors="replace"))
            pkgs = d.get("result", {}).get("results", [])
            print(f"  [CKAN] {tag}: {len(pkgs)} packages")
            for p in pkgs[:4]:
                pname = p.get("name", "")
                ptitle = p.get("title", "")[:65]
                print(f"    - {pname}: {ptitle}")
                for res in p.get("resources", []):
                    fmt = (res.get("format") or "").upper()
                    rurl = res.get("url") or ""
                    if fmt in ("CSV", "JSON", "GEOJSON", "XLSX") and rurl and downloaded < 10:
                        if any(k in (pname + " " + rurl).lower() for k in ["poslovn", "trznic", "zakup", "proracun", "zupanij", "zona", "zet", "stanov", "gospodar", "poljopriv"]):
                            fn = f"ckan_dl_{pname[:32]}_{res.get('id','')[:6]}.{fmt.lower()}"
                            rr = fetch_url(rurl, dest=OUT/fn, city="zagreb", layer="wave2_ckan_data", source_name=f"{ptitle} ({fmt})", timeout=35)
                            print(f"      -> dl {fn}: ok={rr['ok']} {rr.get('bytes',0):,} B")
                            if rr["ok"]: downloaded += 1
                            break
        except Exception as e:
            print(f"  [ERR] {tag}: {e}")


# 4. BiH FZS ZDK u brojkama (Visoko, Zenica, Kakanj, Breza — bridge between Sarajevo & Travnik!) + FZS Kantoni u brojkama index
def collect_bih_zdk_and_sbk():
    print("\n=== 4. BIH FZS ZDK (Visoko/Zenica/Kakanj/Breza) + SBK BUDGET 2026 ===", flush=True)
    r_fzs = fetch_url("https://fzs.ba/index.php/publikacije/godisnji-bilteni/kantoni-u-brojkama/", dest=OUT/"fzs_kantoni_index.html", city="sarajevo", layer="wave2_l", source_name="FZS Kantoni u brojkama index", timeout=35)
    if r_fzs["ok"]:
        html = (OUT/"fzs_kantoni_index.html").read_text(encoding="utf-8", errors="replace")
        pdfs = re.findall(r'href=["\']([^"\']+\.pdf)["\']', html, flags=re.I)
        print(f"  Found {len(pdfs)} PDFs on FZS Kantoni u brojkama")
        zdk_pdfs = [u for u in pdfs if any(k in u.lower() for k in ["zenic", "zdk", "4_", "04_"])]
        print("  ZDK candidates:", zdk_pdfs[:5])
        for u in zdk_pdfs[:1]:
            full = urllib.parse.urljoin("https://fzs.ba/", u)
            res = fetch_url(full, dest=OUT/"fzs_zdk_u_brojkama.pdf", city="sarajevo", layer="wave2_l_hinterland", source_name="FZS Zenicko-dobojski kanton u brojkama PDF", timeout=45)
            print(f"  -> fzs_zdk_u_brojkama.pdf: ok={res['ok']} {res.get('bytes',0):,} B")
    else:
        # Try direct known FZS URL patterns
        for u in [
            "https://fzs.ba/wp-content/uploads/2025/09/Zenicko-dobojski-kanton-u-brojkama-2025.pdf",
            "https://fzs.ba/wp-content/uploads/2025/08/Zenicko-dobojski-kanton-u-brojkama-2025.pdf",
            "https://fzs.ba/wp-content/uploads/2026/01/Zenicko-dobojski-kanton-u-brojkama-2025.pdf",
            "https://fzs.ba/wp-content/uploads/2024/09/Zenicko-dobojski-kanton-u-brojkama-2024.pdf",
        ]:
            res = fetch_url(u, dest=OUT/"fzs_zdk_u_brojkama.pdf", city="sarajevo", layer="wave2_l_hinterland", source_name="FZS ZDK u brojkama PDF", timeout=30)
            if res["ok"] and res.get("bytes", 0) > 100000:
                print(f"  -> DIRECT OK {u}: {res['bytes']:,} B")
                break

    # Also try FZS Statistički godišnjak / publikacije page to find agriculture/forestry/tourism
    r_sbk = fetch_url("https://sbk-ksb.gov.ba/hr/dokumenti/budzet-proracun.html", dest=OUT/"sbk_budzet_page.html", city="travnik", layer="wave2_l_fiscal", source_name="SBK/KSB Cantonal Budget Page", timeout=30)
    print(f"  SBK budget page: ok={r_sbk['ok']} {r_sbk.get('bytes',0):,} B")


if __name__ == "__main__":
    collect_apr_hinterland()
    collect_rzs_commuting_and_agri()
    collect_zagreb_ckan_wave2()
    collect_bih_zdk_and_sbk()
    print("\nDONE 08_collect_wave2_hinterland_l.py", flush=True)
