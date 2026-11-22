from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import json
from pathlib import Path

W5 = Path(str(DB_DIR / "raw" / "wave5"))

print("=== 1. PARSING CORDIS 5 CITIES ===", flush=True)
all_projects = []
seen = set()
CITY_MATCH_TOKENS = {
    "beograd": ["belgrade", "beograd", "rs110"],
    "zagreb": ["zagreb", "hr050"],
    "sarajevo": ["sarajevo"],
    "novi_pazar": ["novi pazar"],
    "travnik": ["travnik"],
}

for cid in ["beograd", "zagreb", "sarajevo", "novi_pazar", "travnik"]:
    fp = W5 / "cordis" / f"cordis_{cid}.json"
    if not fp.exists():
        continue
    d = json.loads(fp.read_text(encoding="utf-8", errors="replace"))
    total_hits = int((d.get("result") or {}).get("header", {}).get("search", {}).get("totalHits") or (d.get("result") or {}).get("totalHits") or 0)
    hits = (d.get("hits") or {}).get("hit") or []
    if isinstance(hits, dict):
        hits = [hits]
    cnt = 0
    local_eur_sum = 0.0
    for h in hits:
        proj = h.get("project") or {}
        pid = str(proj.get("id") or proj.get("rcn") or "")
        if not pid:
            continue
        key = f"{cid}:{pid}"
        if key in seen:
            continue
        # Extract organizations located in this city
        orgs_raw = (((proj.get("relations") or {}).get("associations") or {}).get("organization")) or []
        if isinstance(orgs_raw, dict):
            orgs_raw = [orgs_raw]
        local_orgs = []
        tokens = CITY_MATCH_TOKENS[cid]
        for o in orgs_raw:
            attrs = o.get("@attributes") or {}
            addr = o.get("address") or {}
            city_s = str(addr.get("city") or "").lower()
            name_s = str(o.get("legalName") or "").lower()
            if any(t in city_s or t in name_s for t in tokens):
                ec_c = float(attrs.get("ecContribution") or 0.0)
                local_orgs.append({
                    "org_id": str(o.get("id") or ""),
                    "legal_name": o.get("legalName"),
                    "short_name": o.get("shortName"),
                    "vat_number": o.get("vatNumber"),
                    "role": attrs.get("type"),
                    "ec_contribution_eur": ec_c,
                    "city": addr.get("city"),
                    "country": addr.get("country"),
                    "geolocation": addr.get("geolocation"),
                })
        # Keep if local org matched OR city explicitly in title/objective
        txt = f"{proj.get('title','')} {proj.get('objective','')}".lower()
        if not local_orgs and not any(t in txt for t in tokens):
            continue
        seen.add(key)
        local_sum = sum(x["ec_contribution_eur"] for x in local_orgs)
        ec_max = float(proj.get("ecMaxContribution") or 0.0)
        local_eur_sum += local_sum if local_sum > 0 else 0.0
        # Framework programme
        progs = (((proj.get("relations") or {}).get("associations") or {}).get("programme")) or []
        if isinstance(progs, dict):
            progs = [progs]
        fw = next((p.get("frameworkProgramme") for p in progs if p.get("frameworkProgramme")), "HORIZON")
        all_projects.append({
            "city_id": cid,
            "project_id": pid,
            "acronym": proj.get("acronym"),
            "title": proj.get("title"),
            "objective": (proj.get("objective") or "")[:700],
            "status": proj.get("status"),
            "framework": fw,
            "start_date": proj.get("startDate"),
            "end_date": proj.get("endDate"),
            "total_cost_eur": float(proj.get("totalCost") or 0.0),
            "ec_max_contribution_eur": ec_max,
            "local_city_ec_contribution_eur": round(local_sum, 2),
            "local_orgs": local_orgs,
            "url": f"https://cordis.europa.eu/project/id/{pid}",
        })
        cnt += 1
    print(f"  CORDIS {cid:12s}: totalHits={total_hits:4d} | parsed={cnt:3d} | local_org_EUR={local_eur_sum/1e6:.2f}M", flush=True)

out_p = W5 / "cordis" / "cordis_5cities_consolidated.json"
out_p.write_text(json.dumps(all_projects, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Saved {len(all_projects)} CORDIS projects to {out_p.name}", flush=True)

print("\n=== 2. INSPECTING ZAGREB CSVs (CP1250/UTF-8) ===", flush=True)
zdir = W5 / "zagreb_market"
for fp in sorted(zdir.glob("*.csv")):
    raw = fp.read_bytes()
    for enc in ("utf-8-sig", "cp1250", "latin-1"):
        try:
            txt = raw.decode(enc)
            break
        except Exception:
            continue
    lines = txt.splitlines()
    print(f"--- {fp.name} ({len(lines)} lines, enc={enc}) ---", flush=True)
    for ln in lines[:5]:
        print("  ", ln[:180], flush=True)
