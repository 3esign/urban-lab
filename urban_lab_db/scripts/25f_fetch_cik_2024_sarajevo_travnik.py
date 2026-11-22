import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_net import RAW_DIR, fetch_url

EDIR = RAW_DIR / "wave4" / "elections"
API_CIK = "https://www.izbori.ba/api_2018"
DB_2024 = "WebResult_2024MUNIP1_2026_2_11_13_38_50"
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
    if "ISTOČN" in u or "ISTOCN" in u or "NOVI TRAVNIK" in u or "(RS)" in u:
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
    # Race 5 = Mayors/Nacelnici; Race 9 = Municipal Councils (Općinska vijeća)! Let's test both!
    for rnum, path in [
        (5, f"/race5_electoralunit/{DB_2024}/{LANG}"),
        (9, f"/race9_electoralunit/{DB_2024}/{LANG}"),
        (8, f"/race8_electoralunit/{DB_2024}/{LANG}"),
    ]:
        d = cik_get(path, f"cik2024_r{rnum}_eu", save=True)
        print(f"Probe race{rnum}: type={type(d).__name__}, len={len(d) if isinstance(d, list) else 0}")
        if isinstance(d, list) and d:
            print(f"  sample0={str(d[0])[:180]}")

    collected = []
    # Collect Race 9 (Municipal Council — best for ENP & party competition!) AND Race 5 (Mayor — executive race!)
    for rnum, elec_id, res_ep in [
        (9, "elec:bih:2024-10-06:local_council", "partyresult"),
        (5, "elec:bih:2024-10-06:local_mayor", "candidatesresult"),
    ]:
        eu_path = EDIR / f"cik2024_r{rnum}_eu.json"
        if not eu_path.exists():
            continue
        eu_list = json.loads(eu_path.read_text(encoding="utf-8", errors="replace"))
        if not isinstance(eu_list, list) or not eu_list:
            continue
        matched = []
        for eu in eu_list:
            nm = eu.get("name") or ""
            cid = match_city(nm)
            if cid:
                matched.append((cid, eu))
        print(f"\n=== CIK 2024 Race {rnum} ({elec_id}): matched {len(matched)} municipalities ===")

        for cid, eu in matched:
            euid = eu.get("electoralUnitId") or eu.get("id")
            muni_name = eu.get("name") or str(euid)
            ps_list = cik_get(f"/race{rnum}_pollingstation/{DB_2024}/{euid}/{LANG}", f"cik24_r{rnum}_ps_{euid}", city=cid, save=False)
            if not isinstance(ps_list, list) or not ps_list:
                # Fallback: municipal-level result!
                bi = cik_get(f"/race{rnum}_electoralunitbasicinfo/{DB_2024}/{euid}/{LANG}", f"cik24_r{rnum}_mbi_{euid}", city=cid)
                rs = cik_get(f"/race{rnum}_electoralunit{res_ep}/{DB_2024}/{euid}/{LANG}", f"cik24_r{rnum}_mrs_{euid}", city=cid)
                print(f"  [MUNI FALLBACK] {muni_name}: bi={bool(bi)}, rs={len(rs) if isinstance(rs, list) else 0}")
                continue

            # Fetch polling station details (cap at 35 for large SA munis on race9, 15 on race5; all stations up to 80 for Travnik!)
            cap = 80 if (cid == "travnik" and rnum == 9) else (30 if rnum == 9 else 15)
            got = 0
            # Include both regular and postal/absentee stations by taking first cap-3 + last 3
            sample_ps = ps_list if len(ps_list) <= cap else (ps_list[: cap - 3] + ps_list[-3:])
            for st in sample_ps:
                psid = st.get("pollingStationId") or st.get("id")
                bi = cik_get(f"/race{rnum}_pollingstationsbasicinfo/{DB_2024}/{psid}/{LANG}", f"cik_bi_{psid}", city=cid)
                rs = cik_get(f"/race{rnum}_pollingstations{res_ep}/{DB_2024}/{psid}/{LANG}", f"cik_rs_{psid}", city=cid)
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
                    "election_id": elec_id,
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
            print(f"  + {cid:8s} | {muni_name:22s}: total_bm={len(ps_list):3d}, fetched={got:3d}")

    (EDIR / "parsed_cik_2024_sa_tr.json").write_text(json.dumps(collected, ensure_ascii=False, indent=2), encoding="utf-8")
    sa_n = sum(1 for x in collected if x["city_id"] == "sarajevo")
    tr_n = sum(1 for x in collected if x["city_id"] == "travnik")
    print(f"\nDONE CIK 2024 BiH: total={len(collected)} polling stations (Sarajevo={sa_n}, Travnik={tr_n})")


if __name__ == "__main__":
    main()
