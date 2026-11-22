import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_net import RAW_DIR, fetch_url

EDIR = RAW_DIR / "wave4" / "elections"
API_CIK = "https://www.izbori.ba/api_2018"
LANG = "1"

TARGET_MUNIS = {
    "STARI GRAD SARAJEVO": "sarajevo",
    "CENTAR SARAJEVO": "sarajevo",
    "NOVO SARAJEVO": "sarajevo",
    "NOVI GRAD SARAJEVO": "sarajevo",
    "ILIDŽA": "sarajevo",
    "ILIDZA": "sarajevo",
    "VOGOŠĆA": "sarajevo",
    "VOGOSCA": "sarajevo",
    "HADŽIĆI": "sarajevo",
    "HADZICI": "sarajevo",
    "ILIJAŠ": "sarajevo",
    "ILIJAS": "sarajevo",
    "TRNOVO": "sarajevo",
    "TRAVNIK": "travnik",
}


def match_city(name: str):
    u = (name or "").upper().strip()
    if "ISTOČN" in u or "ISTOCN" in u or "NOVI TRAVNIK" in u or "(RS)" in u or "RS)" in u:
        return None
    for k, cid in TARGET_MUNIS.items():
        if k == u or u.startswith(k + " ") or u.endswith(" " + k):
            return cid
    return None


def cik_get(path: str, tag: str, city="common", save=False):
    url = f"{API_CIK}{path}"
    r = fetch_url(
        url,
        dest=(EDIR / f"{tag}.json") if save else None,
        city=city,
        layer="wave4_elections_bih",
        source_name=tag,
        timeout=20,
        retries=1,
        save_manifest=save,
    )
    if not r["ok"]:
        return None
    raw = r.pop("_bytes", b"")
    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return None


def main():
    # Discover all resId 28..45 and check which one is full BiH 2024 Local Elections!
    chosen = None
    for rid in [36, 37, 38, 35, 34, 33, 32, 31, 30, 40, 42, 43, 44]:
        r = fetch_url(f"{API_CIK}/administration_electionresultcontroller_getdatabasename/{rid}", city="common", layer="wave4_probe", source_name=f"cik_db_{rid}", timeout=10, retries=0, save_manifest=False)
        if not r["ok"]:
            continue
        dbn = r.pop("_bytes", b"").decode("utf-8", errors="replace").strip().strip('"')
        if not dbn or len(dbn) > 80 or "<html" in dbn.lower():
            continue
        for rnum in (9, 8):
            d = cik_get(f"/race{rnum}_electoralunit/{dbn}/{LANG}", f"cik_probe_{rid}_r{rnum}")
            if isinstance(d, list) and len(d) >= 50:
                print(f"[FOUND FULL LOCAL DB] resId={rid} dbName={dbn} race{rnum}_eus={len(d)}", flush=True)
                chosen = (rid, dbn)
                break
        if chosen:
            break

    if not chosen:
        # Fallback: also test 2020 MUNI (resId=35) or 2022 GEN (resId=39)
        print("Testing resId=35 (2020MUNI) and resId=39 (2022GEN) explicitly...", flush=True)
        for rid, dbn, rlist in [
            (35, "WebResult_2020MUNIP6_2023_10_25_8_15_1", [9, 8, 7, 6, 5]),
            (39, "WebResult_2022GENP1_2025_11_19_14_41_56", [1, 2, 4, 5]),
        ]:
            for rnum in rlist:
                d = cik_get(f"/race{rnum}_electoralunit/{dbn}/{LANG}", f"cik_fb_{rid}_r{rnum}")
                if isinstance(d, list) and len(d) >= 20:
                    print(f"[FALLBACK FOUND] resId={rid} dbName={dbn} race{rnum}_eus={len(d)}", flush=True)
                    chosen = (rid, dbn)
                    break
            if chosen:
                break

    if not chosen:
        print("No full BiH CIK DB found!", flush=True)
        return

    rid, dbn = chosen
    elec_year = "2024-10-06" if "2024" in dbn else ("2022-10-02" if "2022" in dbn else "2020-11-15")
    collected = []

    # Check both race 9 (Municipal Council) and race 8 (Mayor)
    for rnum, level_slug, res_ep in [
        (9, "local_council", "partyresult"),
        (8, "local_mayor", "candidatesresult"),
    ]:
        eu_list = cik_get(f"/race{rnum}_electoralunit/{dbn}/{LANG}", f"cik_{rid}_r{rnum}_eu", save=True)
        if not isinstance(eu_list, list) or len(eu_list) < 20:
            continue
        matched = []
        for eu in eu_list:
            cid = match_city(eu.get("name") or "")
            if cid:
                matched.append((cid, eu))
        print(f"=== CIK {elec_year} ({dbn}) race{rnum} ({level_slug}): {len(matched)} matched municipalities ===", flush=True)

        for cid, eu in matched:
            euid = eu.get("electoralUnitId") or eu.get("id")
            muni_name = eu.get("name") or str(euid)
            ps_list = cik_get(f"/race{rnum}_pollingstation/{dbn}/{euid}/{LANG}", f"cik_r{rnum}_ps_{euid}", city=cid)
            if not isinstance(ps_list, list) or not ps_list:
                continue
            # Take all stations for Travnik (council), and up to 25 per SA municipality (including postal/absentee)
            cap = 80 if (cid == "travnik" and rnum == 9) else (22 if rnum == 9 else 10)
            sample_ps = ps_list if len(ps_list) <= cap else (ps_list[: cap - 3] + ps_list[-3:])
            got = 0
            for st in sample_ps:
                psid = st.get("pollingStationId") or st.get("id")
                bi = cik_get(f"/race{rnum}_pollingstationsbasicinfo/{dbn}/{psid}/{LANG}", f"cik_bi_{psid}", city=cid)
                rs = cik_get(f"/race{rnum}_pollingstations{res_ep}/{dbn}/{psid}/{LANG}", f"cik_rs_{psid}", city=cid)
                if not isinstance(bi, dict) or not isinstance(rs, list) or not rs:
                    continue
                reg = int(bi.get("totalVoters") or bi.get("registeredVoters") or 0)
                valid = int(bi.get("validVotes") or 0)
                invalid = int(bi.get("invalidBlankBallots") or 0) + int(bi.get("invalidOthersBallots") or 0)
                cast = int(bi.get("totalVotes") or (valid + invalid))
                if valid + invalid > cast:
                    cast = valid + invalid
                votes = {}
                for item in rs:
                    nm = item.get("name") or item.get("partyName") or item.get("candidateName") or "Unknown"
                    v = int(item.get("totalVotes") or item.get("votes") or 0)
                    if v > 0:
                        votes[nm] = v
                if not votes:
                    continue
                st_name = (st.get("name") or str(psid)).strip()
                upn = st_name.upper()
                st_type = "regular"
                if "POŠT" in upn or "POST" in upn or "ODSUT" in upn or "NN" in upn:
                    st_type = "absentee_postal"
                elif "MOBIL" in upn:
                    st_type = "mobile_team"
                elif "NEPOTVR" in upn:
                    st_type = "unconfirmed_ballots"
                elif "DKP" in upn or "AMBAS" in upn:
                    st_type = "diplomatic"
                if st_type == "regular" and reg > 0 and cast > reg:
                    reg = cast
                collected.append({
                    "city_id": cid,
                    "country_iso3": "BIH",
                    "election_id": f"elec:bih:{elec_year}:{level_slug}",
                    "election_date": elec_year,
                    "db_name": dbn,
                    "constituency": str(eu.get("code") or euid),
                    "muni": muni_name,
                    "station_code": str(st.get("code") or psid),
                    "station_name": st_name,
                    "station_type": st_type,
                    "registered": reg if reg > 0 else None,
                    "voted": cast,
                    "valid": valid,
                    "invalid": invalid,
                    "votes": votes,
                })
                got += 1
            print(f"  + {cid:8s} | {muni_name:22s}: total_bm={len(ps_list):3d}, fetched={got:3d}", flush=True)

    (EDIR / "parsed_cik_2024_sa_tr.json").write_text(json.dumps(collected, ensure_ascii=False, indent=2), encoding="utf-8")
    sa_n = sum(1 for x in collected if x["city_id"] == "sarajevo")
    tr_n = sum(1 for x in collected if x["city_id"] == "travnik")
    print(f"\nDONE CIK BiH ({dbn}): total={len(collected)} polling stations (Sarajevo={sa_n}, Travnik={tr_n})", flush=True)


if __name__ == "__main__":
    main()
