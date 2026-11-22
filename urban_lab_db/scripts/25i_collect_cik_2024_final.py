import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_net import RAW_DIR, fetch_url

EDIR = RAW_DIR / "wave4" / "elections"
API_CIK = "https://www.izbori.ba/api_2018"
DB_2024 = "WebResult_2024MUNI_2024_9_19_20_28_13"
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
    "TRNOVO (FBIH)": "sarajevo",
    "TRAVNIK": "travnik",
}


def match_city(name: str):
    u = (name or "").upper().strip()
    if "ISTOČN" in u or "ISTOCN" in u or "NOVI TRAVNIK" in u or "(RS)" in u:
        return None
    for k, cid in TARGET_MUNIS.items():
        if k == u or (k != "TRNOVO (FBIH)" and u.startswith(k)):
            return cid
    return None


def cik_json(path: str):
    r = fetch_url(API_CIK + path, city="common", layer="wave4_elections_bih", source_name="cik_st", timeout=15, retries=1, save_manifest=False)
    if not r["ok"]:
        return None
    try:
        return json.loads(r.pop("_bytes", b"").decode("utf-8", errors="replace"))
    except Exception:
        return None


def fetch_one_station(task):
    cid, eu, st, rnum, res_ep, elec_id = task
    psid = st.get("pollingStationId")
    bi = cik_json(f"/race{rnum}_pollingstationsbasicinfo/{DB_2024}/{psid}")
    rs = cik_json(f"/race{rnum}_pollingstations{res_ep}/{DB_2024}/{psid}/{LANG}")
    if not isinstance(bi, dict) or not isinstance(rs, list) or not rs:
        return None
    reg = int(bi.get("numberOfVoters") or bi.get("totalVoters") or 0)
    valid = int(bi.get("validVotes") or 0)
    invalid = int(bi.get("totalInvalidVotes") or (int(bi.get("invalidBlankBallots") or 0) + int(bi.get("invalidOthersBallots") or 0)))
    cast = int(bi.get("totalVotes") or (valid + invalid))
    if valid + invalid > cast:
        cast = valid + invalid
    votes = {}
    for item in rs:
        nm = (item.get("name") or item.get("partyName") or item.get("candidateName") or "Unknown").strip()
        v = int(item.get("totalVotes") or item.get("votes") or 0)
        if v > 0:
            votes[nm] = v
    if not votes:
        return None
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
    return {
        "city_id": cid,
        "country_iso3": "BIH",
        "election_id": elec_id,
        "election_date": "2024-10-06",
        "db_name": DB_2024,
        "constituency": str(eu.get("code") or eu.get("electoralUnitId")),
        "muni": (eu.get("name") or "").strip(),
        "station_code": str(st.get("code") or psid),
        "station_name": st_name,
        "address": (st.get("location") or "").strip() or None,
        "station_type": st_type,
        "registered": reg if reg > 0 else None,
        "voted": cast,
        "valid": valid,
        "invalid": invalid,
        "votes": votes,
    }


def main():
    eu_list = json.loads((EDIR / "cik_36_r9_eu.json").read_text(encoding="utf-8"))
    matched = [(match_city(eu.get("name") or ""), eu) for eu in eu_list]
    matched = [(c, e) for c, e in matched if c]
    print(f"Matched {len(matched)} BiH municipalities for CIK 2024 Local Council (race9):", [(c, e["name"]) for c, e in matched], flush=True)

    tasks = []
    for cid, eu in matched:
        euid = eu["electoralUnitId"]
        ps_list = cik_json(f"/race9_pollingstation/{DB_2024}/{euid}/{LANG}") or []
        # Take ALL Travnik stations (76) and ALL Stari Grad/Centar/Ilidza/etc. up to 40 per SA muni (or all if <=50)
        cap = 100 if cid == "travnik" else 45
        chosen_ps = ps_list if len(ps_list) <= cap else (ps_list[: cap - 4] + ps_list[-4:])
        for st in chosen_ps:
            tasks.append((cid, eu, st, 9, "partyresult", "elec:bih:2024-10-06:local_council"))
        print(f"  Queued {cid:8s} | {eu['name']:22s}: {len(chosen_ps)}/{len(ps_list)} stations", flush=True)

    results = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = [ex.submit(fetch_one_station, t) for t in tasks]
        for fut in as_completed(futs):
            res = fut.result()
            if res:
                results.append(res)

    (EDIR / "parsed_cik_2024_sa_tr.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    sa_n = sum(1 for x in results if x["city_id"] == "sarajevo")
    tr_n = sum(1 for x in results if x["city_id"] == "travnik")
    print(f"\nDONE CIK 2024 BiH: {len(results)}/{len(tasks)} stations collected! (Sarajevo={sa_n}, Travnik={tr_n})", flush=True)


if __name__ == "__main__":
    main()
