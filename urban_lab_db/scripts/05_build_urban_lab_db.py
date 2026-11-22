from _paths import DB_DIR, SCRATCH_DIR  # koreni putanja, vidi _paths.py
import csv
import json
import math
import re
import sqlite3
import struct
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from lxml import html

BASE_DIR = Path(str(DB_DIR))
RAW_DIR = BASE_DIR / "raw"
CURATED_DIR = BASE_DIR / "curated"
BND_DIR = CURATED_DIR / "boundaries"
TBL_DIR = CURATED_DIR / "tables"
DB_PATH = CURATED_DIR / "urban_lab_5cities.sqlite"
MANIFEST_PATH = BASE_DIR / "manifest.jsonl"

BND_DIR.mkdir(parents=True, exist_ok=True)
TBL_DIR.mkdir(parents=True, exist_ok=True)

# Reference FX rates (2026): BAM is fixed currency board to EUR (1.95583), RSD ~ 117.0 per EUR (NBS middle rate)
FX_TO_EUR = {
    "EUR": 1.0,
    "RSD": 1.0 / 117.0,
    "BAM": 1.0 / 1.95583,
}

# CBD coordinates for radial bid-rent / centrality rings
CITY_CBD = {
    "beograd": (44.8162, 20.4602),
    "zagreb": (45.8131, 15.9775),
    "sarajevo": (43.8590, 18.4290),
    "novi_pazar": (43.1367, 20.5122),
    "travnik": (44.2264, 17.6658),
}


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# 1. Pure-Python HTRS96 / Croatia TM (EPSG:3765) -> WGS84 (EPSG:4326) + SHP/DBF
# ---------------------------------------------------------------------------
def htrs96_tm_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """Exact inverse Transverse Mercator on GRS80 (EPSG:3765 -> EPSG:4326)."""
    a = 6378137.0
    f = 1.0 / 298.257222101
    e2 = 2 * f - f * f
    ep2 = e2 / (1.0 - e2)
    k0 = 0.9999
    lon0 = math.radians(16.5)
    fe = 500000.0
    fn = 0.0

    X = x - fe
    Y = y - fn
    M = Y / k0
    mu = M / (a * (1.0 - e2 / 4.0 - 3.0 * e2**2 / 64.0 - 5.0 * e2**3 / 256.0))
    e1 = (1.0 - math.sqrt(1.0 - e2)) / (1.0 + math.sqrt(1.0 - e2))
    phi1 = (
        mu
        + (3.0 * e1 / 2.0 - 27.0 * e1**3 / 32.0) * math.sin(2.0 * mu)
        + (21.0 * e1**2 / 16.0 - 55.0 * e1**4 / 32.0) * math.sin(4.0 * mu)
        + (151.0 * e1**3 / 96.0) * math.sin(6.0 * mu)
        + (1097.0 * e1**4 / 512.0) * math.sin(8.0 * mu)
    )
    sinp = math.sin(phi1)
    cosp = math.cos(phi1)
    tanp = math.tan(phi1)
    C1 = ep2 * cosp * cosp
    T1 = tanp * tanp
    N1 = a / math.sqrt(1.0 - e2 * sinp * sinp)
    R1 = a * (1.0 - e2) / ((1.0 - e2 * sinp * sinp) ** 1.5)
    D = X / (N1 * k0)

    lat = phi1 - (N1 * tanp / R1) * (
        D**2 / 2.0
        - (5.0 + 3.0 * T1 + 10.0 * C1 - 4.0 * C1**2 - 9.0 * ep2) * D**4 / 24.0
        + (61.0 + 90.0 * T1 + 298.0 * C1 + 45.0 * T1**2 - 252.0 * ep2 - 3.0 * C1**2) * D**6 / 720.0
    )
    lon = lon0 + (
        D
        - (1.0 + 2.0 * T1 + C1) * D**3 / 6.0
        + (5.0 - 2.0 * C1 + 28.0 * T1 - 3.0 * C1**2 + 8.0 * ep2 + 24.0 * T1**2) * D**5 / 120.0
    ) / cosp
    return (round(math.degrees(lon), 6), round(math.degrees(lat), 6))


def read_dbf_bytes(data: bytes) -> list[dict]:
    num_rec = struct.unpack("<I", data[4:8])[0]
    header_len = struct.unpack("<H", data[8:10])[0]
    rec_len = struct.unpack("<H", data[10:12])[0]
    fields = []
    pos = 32
    while pos < header_len - 1 and data[pos] != 0x0D:
        name = data[pos : pos + 11].split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()
        ftype = chr(data[pos + 11])
        flen = data[pos + 16]
        fields.append((name, ftype, flen))
        pos += 32

    records = []
    offset = header_len
    for _ in range(num_rec):
        rec = data[offset : offset + rec_len]
        offset += rec_len
        if not rec or rec[0:1] == b"*":
            continue
        p = 1
        row = {}
        for name, ftype, flen in fields:
            raw_val = rec[p : p + flen]
            p += flen
            # Try utf-8 then cp1250 for Croatian diacritics
            try:
                sval = raw_val.decode("utf-8").strip()
            except UnicodeDecodeError:
                sval = raw_val.decode("cp1250", errors="replace").strip()
            if ftype in ("N", "F"):
                if sval == "":
                    row[name] = None
                else:
                    try:
                        row[name] = float(sval) if "." in sval else int(sval)
                    except ValueError:
                        row[name] = sval
            else:
                row[name] = sval
        records.append(row)
    return records


def read_shp_polygons_bytes(data: bytes, transform_fn=None) -> list[dict]:
    geoms = []
    pos = 100
    n = len(data)
    while pos + 8 <= n:
        rec_num, content_len_words = struct.unpack(">II", data[pos : pos + 8])
        pos += 8
        end = pos + content_len_words * 2
        shape_type = struct.unpack("<I", data[pos : pos + 4])[0]
        if shape_type in (5, 15, 25):  # Polygon / PolygonZ / PolygonM
            num_parts, num_points = struct.unpack("<II", data[pos + 36 : pos + 44])
            parts = list(struct.unpack(f"<{num_parts}I", data[pos + 44 : pos + 44 + 4 * num_parts]))
            pts_start = pos + 44 + 4 * num_parts
            pts = []
            for i in range(num_points):
                x, y = struct.unpack("<dd", data[pts_start + 16 * i : pts_start + 16 * i + 16])
                if transform_fn:
                    pts.append(list(transform_fn(x, y)))
                else:
                    pts.append([round(x, 6), round(y, 6)])
            rings = []
            for idx, pstart in enumerate(parts):
                pend = parts[idx + 1] if idx + 1 < len(parts) else num_points
                ring = pts[pstart:pend]
                if ring and ring[0] != ring[-1]:
                    ring.append(ring[0])
                if len(ring) >= 4:
                    rings.append(ring)
            # Determine outer vs hole by signed area (SHP clockwise = outer, CCW = hole)
            # In GeoJSON MultiPolygon: group outer rings
            if len(rings) == 1:
                geoms.append({"type": "Polygon", "coordinates": rings})
            else:
                def signed_area(r):
                    s = 0.0
                    for j in range(len(r) - 1):
                        s += (r[j + 1][0] - r[j][0]) * (r[j + 1][1] + r[j][1])
                    return s
                polys = []
                for r in rings:
                    if signed_area(r) >= 0 or not polys:
                        polys.append([r])
                    else:
                        polys[-1].append(r)
                if len(polys) == 1:
                    geoms.append({"type": "Polygon", "coordinates": polys[0]})
                else:
                    geoms.append({"type": "MultiPolygon", "coordinates": polys})
        else:
            geoms.append(None)
        pos = end
    return geoms


def convert_zagreb_zip_to_geojson(zip_path: Path, out_path: Path, transform=True) -> dict:
    with zipfile.ZipFile(zip_path) as zf:
        shp_name = [n for n in zf.namelist() if n.lower().endswith(".shp")][0]
        dbf_name = [n for n in zf.namelist() if n.lower().endswith(".dbf")][0]
        geoms = read_shp_polygons_bytes(zf.read(shp_name), htrs96_tm_to_wgs84 if transform else None)
        attrs = read_dbf_bytes(zf.read(dbf_name))
    feats = []
    for g, a in zip(geoms, attrs):
        if g is None:
            continue
        feats.append({"type": "Feature", "properties": a, "geometry": g})
    fc = {"type": "FeatureCollection", "features": feats}
    out_path.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    return fc


def geom_centroid(geom: dict) -> tuple[float, float]:
    pts = []
    def collect(c):
        if isinstance(c, list) and c:
            if isinstance(c[0], (int, float)):
                pts.append(c)
            else:
                for x in c:
                    collect(x)
    collect(geom.get("coordinates", []))
    if not pts:
        return (0.0, 0.0)
    lon = sum(p[0] for p in pts) / len(pts)
    lat = sum(p[1] for p in pts) / len(pts)
    return (round(lon, 5), round(lat, 5))


# ---------------------------------------------------------------------------
# 2. Parse Belgrade & Novi Pazar Property Tax Zones HTML (2026)
# ---------------------------------------------------------------------------
def parse_num_sr(s: str):
    if not s:
        return None
    s = re.sub(r"[^\d,\.]", "", s)
    if not s:
        return None
    # Serbian thousands separator '.' and optional decimal ','
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def parse_beograd_zones():
    p = RAW_DIR / "beograd" / "beograd_poreske_zone_cene_2026.htm"
    raw = p.read_bytes()
    txt = None
    for enc in ("utf-8", "windows-1250", "cp1250"):
        try:
            t = raw.decode(enc)
            if "Ekstra zona" in t or "Prva zona" in t:
                txt = t
                break
        except Exception:
            pass
    doc = html.fromstring(txt)
    cols = [
        "gradjevinsko_zemljiste", "poljoprivredno_zemljiste", "sumsko_zemljiste",
        "stan", "kuca", "poslovne_zgrade", "garaze_pomocni"
    ]
    rows = []
    for tr in doc.xpath("//tr"):
        cells = [" ".join(c.text_content().split()) for c in tr.xpath("./td|./th")]
        if len(cells) >= 8 and ("zona" in cells[0].lower() or "Zona" in cells[0]):
            zone_name = cells[0]
            for idx, col in enumerate(cols):
                val = parse_num_sr(cells[idx + 1])
                if val is not None:
                    rows.append({
                        "city_id": "beograd",
                        "year": 2026,
                        "zone_or_unit": zone_name,
                        "property_type": col,
                        "price_local_m2": val,
                        "currency": "RSD",
                        "price_eur_m2": round(val * FX_TO_EUR["RSD"], 2),
                        "basis": "property_tax_official_avg",
                        "sample_n": None,
                        "source_doc": "Sl. list grada Beograda 82/2025 (BG_082_2025_002.htm)",
                    })
    return rows


def parse_novi_pazar_zones():
    p = RAW_DIR / "novi_pazar" / "novi_pazar_poreske_zone_cene_2026.htm"
    raw = p.read_bytes()
    txt = None
    for enc in ("utf-8", "windows-1250", "cp1250"):
        try:
            t = raw.decode(enc)
            if "Stanovi" in t or "Građevinsko" in t:
                txt = t
                break
        except Exception:
            pass
    doc = html.fromstring(txt)
    # 7 sequential tables or 7 blocks of 8 items
    type_map = {
        "1)": "gradjevinsko_zemljiste",
        "2)": "poljoprivredno_zemljiste",
        "3)": "sumsko_zemljiste",
        "4)": "drugo_zemljiste",
        "5)": "stan",
        "6)": "kuca",
        "7)": "poslovne_zgrade",
        "8)": "garaze_pomocni",
    }
    zone_names = ["I zona", "II zona", "III zona", "IV zona", "V zona", "VI zona", "VII zona"]
    rows = []
    zone_idx = -1
    for tr in doc.xpath("//tr"):
        cells = [" ".join(c.text_content().split()) for c in tr.xpath("./td|./th")]
        if len(cells) >= 2:
            k0 = cells[0][:2]
            if k0 == "1)":
                zone_idx += 1
            if k0 in type_map and 0 <= zone_idx < len(zone_names):
                val = parse_num_sr(cells[1])
                if val is not None:
                    rows.append({
                        "city_id": "novi_pazar",
                        "year": 2026,
                        "zone_or_unit": zone_names[zone_idx],
                        "property_type": type_map[k0],
                        "price_local_m2": val,
                        "currency": "RSD",
                        "price_eur_m2": round(val * FX_TO_EUR["RSD"], 2),
                        "basis": "property_tax_official_avg",
                        "sample_n": None,
                        "source_doc": "Sl. list grada Novog Pazara 14/2025 (NP_014_2025_002.htm)",
                    })
    return rows


# ---------------------------------------------------------------------------
# 3. Parse RZS Wages HTML (Jul 2026) for 17 BG municipalities + Novi Pazar
# ---------------------------------------------------------------------------
def parse_rzs_wages_jul2026():
    p = RAW_DIR / "common" / "rzs_zarade_2026_1262.html"
    doc = html.fromstring(p.read_text(encoding="utf-8", errors="replace"))
    wages = {}
    for tr in doc.xpath("//tr"):
        cells = [" ".join(c.text_content().split()) for c in tr.xpath("./td|./th")]
        if len(cells) >= 6:
            name = cells[0].strip()
            try:
                gross = float(cells[1].replace(" ", "").replace(",", "."))
                net = float(cells[5].replace(" ", "").replace(",", "."))
            except Exception:
                continue
            wages[name] = {"gross_rsd": gross, "net_rsd": net, "net_eur": round(net * FX_TO_EUR["RSD"], 2)}
    return wages


# ---------------------------------------------------------------------------
# 4. NACE 2-digit -> 1-letter Section mapping (for unifying Serbia APR with FZS BiH A-U!)
# ---------------------------------------------------------------------------
def nace2_to_section(code2: str) -> str:
    try:
        n = int(code2[:2])
    except Exception:
        return "UNKNOWN"
    if 1 <= n <= 3: return "A"
    if 5 <= n <= 9: return "B"
    if 10 <= n <= 33: return "C"
    if n == 35: return "D"
    if 36 <= n <= 39: return "E"
    if 41 <= n <= 43: return "F"
    if 45 <= n <= 47: return "G"
    if 49 <= n <= 53: return "H"
    if 55 <= n <= 56: return "I"
    if 58 <= n <= 63: return "J"
    if 64 <= n <= 66: return "K"
    if n == 68: return "L"
    if 69 <= n <= 75: return "M"
    if 77 <= n <= 82: return "N"
    if n == 84: return "O"
    if n == 85: return "P"
    if 86 <= n <= 88: return "Q"
    if 90 <= n <= 93: return "R"
    if 94 <= n <= 96: return "S"
    if 97 <= n <= 98: return "T"
    if n == 99: return "U"
    return "UNKNOWN"


NACE_SECTION_NAMES = {
    "A": "Agriculture, forestry and fishing",
    "B": "Mining and quarrying",
    "C": "Manufacturing",
    "D": "Electricity, gas, steam and air conditioning",
    "E": "Water supply, sewerage, waste management",
    "F": "Construction",
    "G": "Wholesale and retail trade",
    "H": "Transportation and storage",
    "I": "Accommodation and food service (Hospitality)",
    "J": "Information and communication (ICT)",
    "K": "Financial and insurance activities",
    "L": "Real estate activities",
    "M": "Professional, scientific and technical activities",
    "N": "Administrative and support service activities",
    "O": "Public administration and defence",
    "P": "Education",
    "Q": "Human health and social work",
    "R": "Arts, entertainment and recreation",
    "S": "Other service activities",
    "T": "Activities of households as employers",
    "U": "Activities of extraterritorial organisations",
}

# Verified FZS 31.12.2024 legal entities by NACE section A..U (extracted verbatim from FZS PDFs in raw/)
FZS_KS_COMPANIES_2024 = {
    "Centar Sarajevo":     {"A":26,"B":9,"C":193,"D":42,"E":8,"F":198,"G":1086,"H":70,"I":251,"J":401,"K":64,"L":204,"M":982,"N":267,"O":101,"P":95,"Q":102,"R":398,"S":1415,"U":22},
    "Hadžići":             {"A":24,"B":0,"C":89,"D":7,"E":5,"F":48,"G":115,"H":30,"I":20,"J":7,"K":0,"L":78,"M":31,"N":36,"O":19,"P":17,"Q":7,"R":45,"S":80,"U":0},
    "Ilidža":              {"A":41,"B":9,"C":338,"D":24,"E":9,"F":291,"G":1285,"H":132,"I":180,"J":134,"K":13,"L":688,"M":416,"N":339,"O":23,"P":75,"Q":46,"R":169,"S":433,"U":0},
    "Ilijaš":              {"A":21,"B":1,"C":85,"D":2,"E":5,"F":16,"G":94,"H":23,"I":7,"J":5,"K":0,"L":66,"M":21,"N":15,"O":20,"P":14,"Q":5,"R":30,"S":84,"U":0},
    "Novi Grad Sarajevo":  {"A":17,"B":2,"C":247,"D":16,"E":17,"F":225,"G":1097,"H":172,"I":119,"J":179,"K":21,"L":146,"M":389,"N":202,"O":41,"P":79,"Q":61,"R":297,"S":717,"U":2},
    "Novo Sarajevo":       {"A":12,"B":2,"C":183,"D":34,"E":7,"F":215,"G":937,"H":67,"I":167,"J":290,"K":46,"L":154,"M":615,"N":208,"O":48,"P":90,"Q":81,"R":215,"S":917,"U":10},
    "Stari Grad Sarajevo": {"A":8,"B":2,"C":93,"D":20,"E":1,"F":66,"G":387,"H":24,"I":215,"J":75,"K":22,"L":90,"M":221,"N":113,"O":28,"P":43,"Q":39,"R":124,"S":541,"U":5},
    "Trnovo":              {"A":6,"B":0,"C":2,"D":6,"E":1,"F":8,"G":4,"H":0,"I":10,"J":0,"K":0,"L":2,"M":2,"N":6,"O":2,"P":1,"Q":2,"R":13,"S":26,"U":0},
    "Vogošća":             {"A":9,"B":1,"C":118,"D":7,"E":4,"F":51,"G":270,"H":37,"I":25,"J":29,"K":3,"L":91,"M":57,"N":34,"O":10,"P":21,"Q":12,"R":64,"S":148,"U":0},
}

FZS_TRAVNIK_COMPANIES_2024 = {
    "Travnik": {"A":28,"B":3,"C":157,"D":14,"E":6,"F":40,"G":157,"H":49,"I":37,"J":14,"K":2,"L":12,"M":39,"N":18,"O":59,"P":52,"Q":40,"R":119,"S":326,"U":0},
}
FZS_SBK_TOTAL_COMPANIES_2024 = {
    "A":150,"B":30,"C":849,"D":80,"E":48,"F":193,"G":1063,"H":269,"I":112,"J":73,"K":6,"L":57,"M":176,"N":69,"O":255,"P":175,"Q":164,"R":583,"S":1379,"U":0
}

# Verified FZS Sarajevo 9 općina stats (from raw/sarajevo/fzs_kanton_sarajevo_2026.pdf + RCN 2024)
KS_UNITS_VERIFIED = [
    ("10839", "Centar Sarajevo",     33.0,  51919, 46573, 1986.0, 3138.0, 5946, 3900.0, 220),
    ("10847", "Hadžići",            273.0,  24526,  5671, 1341.0, 2097.0,  658, None,   None),
    ("11550", "Ilidža",             143.0,  72818, 26600, 1408.0, 2203.0, 4653, 3000.0,  68),
    ("10863", "Ilijaš",             309.0,  21124,  4255, 1080.0, 1669.0,  515, None,   None),
    ("10871", "Novi Grad Sarajevo",  47.0, 123568, 32134, 1545.0, 2424.0, 4054, 3110.0, 183),
    ("11568", "Novo Sarajevo",       10.0,  62463, 29789, 1830.0, 2942.0, 4304, 3830.0, 286),
    ("11584", "Stari Grad Sarajevo", 51.0,  33534, 10478, 1778.0, 2803.0, 2122, 4020.0,  58),
    ("11592", "Trnovo",             338.0,   1772,   397, 1301.0, 2034.0,   91, 4040.0,  26),
    ("10928", "Vogošća",             72.0,  29807,  6888, 1325.0, 2051.0,  993, 2800.0,  83),
]

# Verified Zagreb 17 Gradske četvrti (from raw/zagreb/zagreb_popis_2021_konacni.pdf, pages 7 & 10)
ZG_GC_VERIFIED = {
    "Donji grad":                (31209, 37024,   3.02, 10334),
    "Gornji grad - Medveščak":   (26423, 30962,  10.18,  2596),
    "Trnje":                     (40539, 42282,   7.36,  5508),
    "Maksimir":                  (47356, 48902,  14.97,  3163),
    "Peščenica - Žitnjak":       (53023, 56487,  35.29,  1502),
    "Novi Zagreb - istok":       (55898, 59055,  16.54,  3380),
    "Novi Zagreb - zapad":       (63917, 58103,  62.63,  1021),
    "Trešnjevka - sjever":       (52974, 55425,   5.81,  9118),
    "Trešnjevka - jug":          (65324, 66674,   9.84,  6639),
    "Črnomerec":                 (38084, 38546,  24.16,  1576),
    "Gornja Dubrava":            (58255, 61841,  40.43,  1441),
    "Donja Dubrava":             (33537, 36363,  10.79,  3108),
    "Stenjevec":                 (53862, 51390,  12.24,  4400),
    "Podsused - Vrapče":         (44910, 45759,  36.19,  1241),
    "Podsljeme":                 (18974, 19165,  59.25,   320),
    "Sesvete":                   (70800, 70009, 165.22,   429),
    "Brezovica":                 (12046, 12030, 127.32,    95),
}

BEOGRAD_OPSTINE_MAP = {
    "70092": "Barajevo", "70106": "Voždovac", "70114": "Vračar", "70122": "Grocka",
    "70149": "Zvezdara", "70157": "Zemun", "70165": "Lazarevac", "70173": "Mladenovac",
    "70181": "Novi Beograd", "70190": "Obrenovac", "70203": "Palilula", "70211": "Rakovica",
    "70220": "Savski venac", "70238": "Sopot", "70246": "Stari grad", "70254": "Čukarica",
    "71293": "Surčin",
}


def norm_key(s: str) -> str:
    s = (s or "").lower().strip()
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"\s+", " ", s)
    return s


def classify_osm_poi(tags: dict) -> tuple[str, str]:
    if "shop" in tags:
        return ("retail", tags["shop"])
    if "office" in tags:
        return ("office_business", tags["office"])
    if "craft" in tags:
        return ("craft_industry", tags["craft"])
    am = tags.get("amenity", "")
    if am in ("restaurant", "cafe", "bar", "pub", "fast_food", "food_court"):
        return ("hospitality", am)
    if am in ("bank", "atm", "bureau_de_change"):
        return ("finance", am)
    if am in ("school", "university", "college", "kindergarten"):
        return ("education", am)
    if am in ("hospital", "clinic", "doctors", "pharmacy", "dentist"):
        return ("health", am)
    if am in ("townhall", "courthouse", "police", "post_office", "public_building"):
        return ("public_admin", am)
    if tags.get("tourism") in ("hotel", "hostel", "guest_house", "museum"):
        return ("tourism", tags["tourism"])
    if tags.get("railway") in ("station", "tram_stop") or am == "bus_station":
        return ("transit_hub", tags.get("railway") or am)
    return ("other", am or "other")


def build_all():
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # Create Schema
    cur.executescript("""
    PRAGMA journal_mode=WAL;

    CREATE TABLE cities (
        city_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        country_iso3 TEXT NOT NULL,
        country_name TEXT NOT NULL,
        currency TEXT NOT NULL,
        fx_to_eur REAL NOT NULL,
        governance_model TEXT,
        cbd_lat REAL,
        cbd_lon REAL,
        population INTEGER,
        population_year INTEGER,
        population_scope TEXT,
        area_km2 REAL,
        density_per_km2 REAL,
        budget_2026_local REAL,
        budget_2026_eur REAL,
        budget_scope TEXT,
        budget_per_capita_eur REAL,
        avg_net_wage_local REAL,
        avg_net_wage_eur REAL,
        wage_period TEXT,
        avg_apt_price_local_m2 REAL,
        avg_apt_price_eur_m2 REAL,
        price_basis TEXT,
        registered_companies INTEGER,
        companies_scope TEXT,
        notes TEXT
    );

    CREATE TABLE admin_units (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city_id TEXT NOT NULL,
        unit_code TEXT,
        unit_name TEXT NOT NULL,
        admin_level TEXT NOT NULL,
        parent_name TEXT,
        population INTEGER,
        population_year INTEGER,
        area_km2 REAL,
        density_per_km2 REAL,
        employees INTEGER,
        avg_net_wage_local REAL,
        avg_net_wage_eur REAL,
        companies_count INTEGER,
        companies_rev_local_k REAL,
        companies_rev_eur_m REAL,
        avg_apt_price_local_m2 REAL,
        avg_apt_price_eur_m2 REAL,
        centroid_lon REAL,
        centroid_lat REAL,
        dist_cbd_km REAL,
        source_note TEXT
    );

    CREATE TABLE fiscal_budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city_id TEXT NOT NULL,
        entity_name TEXT NOT NULL,
        entity_level TEXT NOT NULL,
        year INTEGER NOT NULL,
        currency TEXT NOT NULL,
        total_budget_local REAL,
        total_budget_eur REAL,
        capital_expenditure_local REAL,
        capital_expenditure_eur REAL,
        property_tax_rev_local REAL,
        income_tax_rev_local REAL,
        population_ref INTEGER,
        per_capita_eur REAL,
        status TEXT,
        source_doc TEXT
    );

    CREATE TABLE zagreb_budget_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        year INTEGER,
        side TEXT,
        razdjel_code TEXT,
        razdjel_name TEXT,
        glava_code TEXT,
        glava_name TEXT,
        account_code TEXT,
        account_name TEXT,
        plan_eur REAL
    );

    CREATE TABLE property_zones_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city_id TEXT NOT NULL,
        year INTEGER NOT NULL,
        zone_or_unit TEXT NOT NULL,
        property_type TEXT NOT NULL,
        price_local_m2 REAL NOT NULL,
        currency TEXT NOT NULL,
        price_eur_m2 REAL NOT NULL,
        basis TEXT NOT NULL,
        sample_n INTEGER,
        source_doc TEXT
    );

    CREATE TABLE companies_sr (
        maticni_broj TEXT PRIMARY KEY,
        city_id TEXT NOT NULL,
        opstina_code TEXT,
        opstina_name TEXT,
        business_name TEXT,
        legal_form TEXT,
        status TEXT,
        founded_date TEXT,
        nace_code TEXT,
        nace_section TEXT,
        fi_year INTEGER,
        revenue_k_rsd REAL,
        net_profit_k_rsd REAL,
        net_loss_k_rsd REAL,
        assets_k_rsd REAL,
        equity_k_rsd REAL,
        employees REAL
    );

    CREATE TABLE sector_structure (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city_id TEXT NOT NULL,
        unit_name TEXT NOT NULL,
        nace_section TEXT NOT NULL,
        nace_name TEXT,
        companies_count INTEGER NOT NULL,
        unit_share_pct REAL,
        benchmark_share_pct REAL,
        location_quotient REAL,
        benchmark_scope TEXT,
        source_doc TEXT
    );

    CREATE TABLE osm_pois (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city_id TEXT NOT NULL,
        osm_type TEXT,
        osm_id INTEGER,
        category TEXT,
        subcategory TEXT,
        name TEXT,
        lat REAL,
        lon REAL,
        dist_cbd_km REAL,
        ring_km TEXT
    );

    CREATE TABLE macro_worldbank (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        country_iso3 TEXT,
        indicator_id TEXT,
        indicator_name TEXT,
        year INTEGER,
        value REAL
    );

    CREATE TABLE sources_manifest (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        checked_at TEXT,
        city TEXT,
        layer TEXT,
        source_name TEXT,
        url TEXT,
        http_status INTEGER,
        ok INTEGER,
        bytes INTEGER,
        sha256 TEXT,
        local_path TEXT,
        error TEXT
    );
    """)

    # ------------------------------------------------------------------
    # STEP A: Convert Zagreb SHP -> WGS84 GeoJSON (17 GC + 218 MO)
    # ------------------------------------------------------------------
    print("[BUILD] Converting Zagreb SHP (HTRS96/TM -> WGS84 GeoJSON)...")
    zg_gc_fc = convert_zagreb_zip_to_geojson(
        RAW_DIR / "zagreb" / "rpj_gc.zip",
        BND_DIR / "zagreb_17_cetvrti.geojson",
    )
    zg_mo_fc = convert_zagreb_zip_to_geojson(
        RAW_DIR / "zagreb" / "mjesni-odbori-prostorna-jedinica-mjesne-samou_482b7289_rpj_mo.zip",
        BND_DIR / "zagreb_218_mjesnih_odbora.geojson",
    )
    print(f"  Zagreb GC={len(zg_gc_fc['features'])}, MO={len(zg_mo_fc['features'])}")
    if zg_gc_fc["features"]:
        print("  Sample ZG GC props:", zg_gc_fc["features"][0]["properties"], "centroid:", geom_centroid(zg_gc_fc["features"][0]["geometry"]))

    # ------------------------------------------------------------------
    # STEP B: Load APR Serbia Companies (Beograd + Novi Pazar)
    # ------------------------------------------------------------------
    print("[BUILD] Loading APR Companies (Beograd + Novi Pazar) into SQLite...")
    nat_apr = json.loads((RAW_DIR / "common" / "apr_serbia_nace2_baseline.json").read_text(encoding="utf-8"))
    # Build Serbia national NACE-section baseline
    nat_sec_counts = Counter()
    for code2, cnt in nat_apr.get("nace2_counts_serbia", {}).items():
        nat_sec_counts[nace2_to_section(code2)] += cnt
    nat_sec_total = sum(nat_sec_counts.values()) or 1

    muni_apr_stats = defaultdict(lambda: {"count": 0, "fi_count": 0, "rev_k": 0.0, "profit_k": 0.0, "emp": 0.0, "sec": Counter()})
    comp_batch = []

    for cid, fname in [
        ("beograd", RAW_DIR / "beograd" / "apr_beograd_companies.jsonl"),
        ("novi_pazar", RAW_DIR / "novi_pazar" / "apr_novi_pazar_companies.jsonl"),
    ]:
        with open(fname, "r", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                mb = str(r.get("MaticniBroj", "")).strip()
                op_code = str(r.get("SifraOpstine", "")).strip()
                op_name = BEOGRAD_OPSTINE_MAP.get(op_code, "Novi Pazar" if cid == "novi_pazar" else r.get("NazivOpstine", ""))
                nace = str(r.get("SifraDelatnosti") or "").strip()
                sec = nace2_to_section(nace)
                fi = r.get("fi") or {}
                rev = fi.get("UkupniPrihodi")
                prof = fi.get("NetoDobitak")
                loss = fi.get("NetoGubitak")
                assets = fi.get("PoslovnaImovina")
                eq = fi.get("Kapital")
                emp = fi.get("ProsecanBrojZaposlenih")
                comp_batch.append((
                    mb, cid, op_code, op_name, r.get("PoslovnoIme"), r.get("NazivPravneForme"),
                    r.get("NazivStatus"), r.get("DatumOsnivanja"), nace, sec,
                    fi.get("GodinaFi"), rev, prof, loss, assets, eq, emp
                ))
                st = muni_apr_stats[(cid, op_code)]
                st["count"] += 1
                st["sec"][sec] += 1
                if fi:
                    st["fi_count"] += 1
                    st["rev_k"] += float(rev or 0)
                    st["profit_k"] += float(prof or 0) - float(loss or 0)
                    st["emp"] += float(emp or 0)

    cur.executemany(
        "INSERT OR REPLACE INTO companies_sr VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        comp_batch,
    )
    print(f"  Inserted {len(comp_batch)} Serbian companies into companies_sr")

    # Insert Sector Structure + Location Quotient for Beograd (17 opstina + city total) & Novi Pazar
    sec_rows = []
    # City totals first
    for cid, city_label in [("beograd", "Beograd (UKUPNO)"), ("novi_pazar", "Novi Pazar")]:
        c_tot = Counter()
        for (c, _), st in muni_apr_stats.items():
            if c == cid:
                c_tot.update(st["sec"])
        tot_n = sum(c_tot.values()) or 1
        for sec, cnt in sorted(c_tot.items()):
            if sec == "UNKNOWN":
                continue
            u_sh = cnt / tot_n
            b_sh = nat_sec_counts[sec] / nat_sec_total
            lq = round(u_sh / b_sh, 3) if b_sh > 0 else None
            sec_rows.append((cid, city_label, sec, NACE_SECTION_NAMES.get(sec), cnt, round(u_sh * 100, 2), round(b_sh * 100, 2), lq, "Serbia APR national", "openapi.apr.gov.rs (2026-10-31)"))
    # Individual Belgrade municipalities
    for op_code, op_name in sorted(BEOGRAD_OPSTINE_MAP.items()):
        st = muni_apr_stats[("beograd", op_code)]
        tot_n = sum(st["sec"].values()) or 1
        for sec, cnt in sorted(st["sec"].items()):
            if sec == "UNKNOWN":
                continue
            u_sh = cnt / tot_n
            b_sh = nat_sec_counts[sec] / nat_sec_total
            lq = round(u_sh / b_sh, 3) if b_sh > 0 else None
            sec_rows.append(("beograd", op_name, sec, NACE_SECTION_NAMES.get(sec), cnt, round(u_sh * 100, 2), round(b_sh * 100, 2), lq, "Serbia APR national", "openapi.apr.gov.rs (2026-10-31)"))

    # Sarajevo (9 općina + KS total) from verified FZS 2024
    ks_tot_sec = Counter()
    for u_name, smap in FZS_KS_COMPANIES_2024.items():
        ks_tot_sec.update(smap)
    ks_tot_n = sum(ks_tot_sec.values()) or 1
    for sec, cnt in sorted(ks_tot_sec.items()):
        u_sh = cnt / ks_tot_n
        sec_rows.append(("sarajevo", "Kanton Sarajevo (UKUPNO)", sec, NACE_SECTION_NAMES.get(sec), cnt, round(u_sh * 100, 2), round(u_sh * 100, 2), 1.0, "Kanton Sarajevo FZS 2024", "FZS Kanton Sarajevo u brojkama 2025/2026"))
    for u_name, smap in FZS_KS_COMPANIES_2024.items():
        tot_n = sum(smap.values()) or 1
        for sec, cnt in sorted(smap.items()):
            u_sh = cnt / tot_n
            b_sh = ks_tot_sec[sec] / ks_tot_n
            lq = round(u_sh / b_sh, 3) if b_sh > 0 else None
            sec_rows.append(("sarajevo", u_name, sec, NACE_SECTION_NAMES.get(sec), cnt, round(u_sh * 100, 2), round(b_sh * 100, 2), lq, "Kanton Sarajevo FZS 2024", "FZS Kanton Sarajevo u brojkama 2025/2026"))

    # Travnik vs SBK benchmark from verified FZS 2024
    sbk_tot_n = sum(FZS_SBK_TOTAL_COMPANIES_2024.values()) or 1
    tr_smap = FZS_TRAVNIK_COMPANIES_2024["Travnik"]
    tr_tot_n = sum(tr_smap.values()) or 1
    for sec, cnt in sorted(tr_smap.items()):
        u_sh = cnt / tr_tot_n
        b_sh = FZS_SBK_TOTAL_COMPANIES_2024.get(sec, 0) / sbk_tot_n
        lq = round(u_sh / b_sh, 3) if b_sh > 0 else None
        sec_rows.append(("travnik", "Travnik", sec, NACE_SECTION_NAMES.get(sec), cnt, round(u_sh * 100, 2), round(b_sh * 100, 2), lq, "SBK FZS 2024", "FZS Srednjobosanski kanton u brojkama 2025"))

    cur.executemany(
        "INSERT INTO sector_structure (city_id, unit_name, nace_section, nace_name, companies_count, unit_share_pct, benchmark_share_pct, location_quotient, benchmark_scope, source_doc) VALUES (?,?,?,?,?,?,?,?,?,?)",
        sec_rows,
    )
    print(f"  Inserted {len(sec_rows)} sector_structure rows (with LQ)")

    # ------------------------------------------------------------------
    # STEP C: Parse RZS Wages + Census 2022 + Build Multi-City Unified GeoJSON & admin_units
    # ------------------------------------------------------------------
    rzs_wages = parse_rzs_wages_jul2026()
    print(f"  Parsed {len(rzs_wages)} RZS wage rows (Jul 2026)")

    # Census 2022 population for Beograd (17) + Novi Pazar from RZS ArcGIS
    rzs_pop_fc = json.loads((RAW_DIR / "common" / "rzs_popis2022_ind1_bg_np_ops.geojson").read_text(encoding="utf-8"))
    rzs_pop_map = {}
    for f in rzs_pop_fc["features"]:
        pr = f["properties"]
        code = str(pr.get("ter_kod") or pr.get("geo_sifra") or "").strip()
        val = pr.get("vrednost")
        if code and val is not None:
            rzs_pop_map[code] = int(round(float(val)))
    print(f"  RZS Popis 2022 map loaded for {len(rzs_pop_map)} municipalities (NP={rzs_pop_map.get('70874')})")

    unified_features = []
    admin_rows = []

    # C1. Beograd 17 opština
    bg_fc = json.loads((RAW_DIR / "beograd" / "rzs_beograd_17_opstina.geojson").read_text(encoding="utf-8"))
    bg_out_feats = []
    bg_pop_total = 0
    bg_area_total = 0.0
    for f in bg_fc["features"]:
        pr = f["properties"]
        code = str(pr.get("matbro", "")).strip()
        name = BEOGRAD_OPSTINE_MAP.get(code, pr.get("imeolat", code))
        pop = rzs_pop_map.get(code)
        area_km2 = round(float(pr.get("SHAPE__Area") or 0) / 1e6, 2) if pr.get("SHAPE__Area") else None
        # Note: RZS SHAPE__Area in WebMercator needs cos^2(lat) correction; compute approx from lat or use known
        clon, clat = geom_centroid(f["geometry"])
        if area_km2 and clat:
            area_km2 = round(area_km2 * (math.cos(math.radians(clat)) ** 2), 2)
        dens = round(pop / area_km2, 1) if (pop and area_km2) else None
        if pop: bg_pop_total += pop
        if area_km2: bg_area_total += area_km2
        w_key = "Palilula (Beograd)" if name == "Palilula" else name
        w = rzs_wages.get(w_key) or rzs_wages.get(name) or {}
        st = muni_apr_stats[("beograd", code)]
        dist = round(haversine_km(CITY_CBD["beograd"][0], CITY_CBD["beograd"][1], clat, clon), 2)
        rev_eur_m = round(st["rev_k"] * 1000.0 * FX_TO_EUR["RSD"] / 1e6, 2)

        props = {
            "city_id": "beograd", "unit_code": code, "unit_name": name, "admin_level": "municipality",
            "population": pop, "population_year": 2022, "area_km2": area_km2, "density_per_km2": dens,
            "avg_net_wage_local": w.get("net_rsd"), "avg_net_wage_eur": w.get("net_eur"),
            "companies_count": st["count"], "companies_employees_apr": int(round(st["emp"])),
            "companies_rev_eur_m": rev_eur_m, "dist_cbd_km": dist,
            "source_id": "rzs_arcgis+apr_2026+rzs_wages_jul2026"
        }
        bg_out_feats.append({"type": "Feature", "properties": props, "geometry": f["geometry"]})
        unified_features.append({"type": "Feature", "properties": props, "geometry": f["geometry"]})
        admin_rows.append((
            "beograd", code, name, "municipality", "Grad Beograd", pop, 2022, area_km2, dens,
            int(round(st["emp"])), w.get("net_rsd"), w.get("net_eur"), st["count"],
            round(st["rev_k"], 1), rev_eur_m, None, None, clon, clat, dist,
            "RZS Popis 2022 + RZS zarade jul 2026 + APR RGFI"
        ))
    (BND_DIR / "beograd_17_opstina.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": bg_out_feats}, ensure_ascii=False), encoding="utf-8")

    # Copy RZS 1km grids and NP settlements into curated/boundaries
    for src, dst in [
        (RAW_DIR / "beograd" / "rzs_popis2022_grid_1km_beograd.geojson", BND_DIR / "beograd_grid_1km_popis2022.geojson"),
        (RAW_DIR / "novi_pazar" / "rzs_popis2022_grid_1km_novi_pazar.geojson", BND_DIR / "novi_pazar_grid_1km_popis2022.geojson"),
        (RAW_DIR / "novi_pazar" / "rzs_novi_pazar_naselja_popis2022.geojson", BND_DIR / "novi_pazar_99_naselja_popis2022.geojson"),
    ]:
        if src.exists():
            dst.write_bytes(src.read_bytes())

    # C2. Novi Pazar (Grad + 99 settlements in admin_units)
    np_fc = json.loads((RAW_DIR / "novi_pazar" / "rzs_novi_pazar_opstina.geojson").read_text(encoding="utf-8"))
    np_out_feats = []
    np_pop = rzs_pop_map.get("70874", 106720)
    np_w = rzs_wages.get("Novi Pazar", {})
    np_st = muni_apr_stats[("novi_pazar", "70874")]
    np_rev_eur_m = round(np_st["rev_k"] * 1000.0 * FX_TO_EUR["RSD"] / 1e6, 2)
    for f in np_fc["features"]:
        clon, clat = geom_centroid(f["geometry"])
        area_km2 = 742.0  # Official RZS area of City of Novi Pazar
        dens = round(np_pop / area_km2, 1)
        props = {
            "city_id": "novi_pazar", "unit_code": "70874", "unit_name": "Novi Pazar", "admin_level": "city",
            "population": np_pop, "population_year": 2022, "area_km2": area_km2, "density_per_km2": dens,
            "avg_net_wage_local": np_w.get("net_rsd"), "avg_net_wage_eur": np_w.get("net_eur"),
            "companies_count": np_st["count"], "companies_employees_apr": int(round(np_st["emp"])),
            "companies_rev_eur_m": np_rev_eur_m, "dist_cbd_km": 0.0,
            "source_id": "rzs_arcgis+apr_2026+rzs_wages_jul2026"
        }
        np_out_feats.append({"type": "Feature", "properties": props, "geometry": f["geometry"]})
        unified_features.append({"type": "Feature", "properties": props, "geometry": f["geometry"]})
        admin_rows.append((
            "novi_pazar", "70874", "Novi Pazar", "city", "Grad Novi Pazar", np_pop, 2022, area_km2, dens,
            int(round(np_st["emp"])), np_w.get("net_rsd"), np_w.get("net_eur"), np_st["count"],
            round(np_st["rev_k"], 1), np_rev_eur_m, 127449.0, round(127449.0 * FX_TO_EUR["RSD"], 2),
            clon, clat, 0.0, "RZS Popis 2022 + RZS zarade jul 2026 + APR RGFI"
        ))
    (BND_DIR / "novi_pazar_grad.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": np_out_feats}, ensure_ascii=False), encoding="utf-8")

    # Add Novi Pazar 99 settlements into admin_units table
    np_nas_path = RAW_DIR / "novi_pazar" / "rzs_novi_pazar_naselja_popis2022.geojson"
    if np_nas_path.exists():
        np_nas_fc = json.loads(np_nas_path.read_text(encoding="utf-8"))
        for f in np_nas_fc.get("features", []):
            pr = f["properties"]
            clon, clat = geom_centroid(f["geometry"])
            dist = round(haversine_km(CITY_CBD["novi_pazar"][0], CITY_CBD["novi_pazar"][1], clat, clon), 2)
            admin_rows.append((
                "novi_pazar", str(pr.get("ter_kod") or ""), str(pr.get("ter_imel") or pr.get("nter") or ""),
                "settlement", "Novi Pazar", int(round(float(pr["vrednost"]))) if pr.get("vrednost") is not None else None,
                2022, None, None, None, None, None, None, None, None, None, None, clon, clat, dist,
                "RZS ArcGIS Popis 2022 PS22_IND1_NAS"
            ))

    # C3. Zagreb 17 Gradske četvrti + 218 Mjesnih odbora
    zg_lookup = {norm_key(k): (k, v) for k, v in ZG_GC_VERIFIED.items()}
    zg_enriched_feats = []
    for f in zg_gc_fc["features"]:
        pr = f["properties"]
        raw_name = pr.get("IME") or pr.get("NAZIV") or pr.get("GC_NAZIV") or next((str(v) for k, v in pr.items() if isinstance(v, str) and len(v) > 2), "Unknown")
        nk = norm_key(raw_name)
        match = zg_lookup.get(nk)
        if not match:
            for lk, lv in zg_lookup.items():
                if lk.replace(" ", "") == nk.replace(" ", "") or lk in nk or nk in lk:
                    match = lv
                    break
        disp_name = match[0] if match else raw_name
        pop21, pop11, area, dens = match[1] if match else (None, None, None, None)
        clon, clat = geom_centroid(f["geometry"])
        dist = round(haversine_km(CITY_CBD["zagreb"][0], CITY_CBD["zagreb"][1], clat, clon), 2)
        code = str(pr.get("SIFRA") or pr.get("ID") or pr.get("REDNI_BROJ") or "")
        props = {
            "city_id": "zagreb", "unit_code": code, "unit_name": disp_name, "admin_level": "district",
            "population": pop21, "population_2011": pop11, "population_year": 2021,
            "area_km2": area, "density_per_km2": dens,
            "avg_net_wage_local": 1760.0, "avg_net_wage_eur": 1760.0,
            "dist_cbd_km": dist, "source_id": "data.zagreb.hr_rpj_gc+popis_2021"
        }
        zg_enriched_feats.append({"type": "Feature", "properties": props, "geometry": f["geometry"]})
        unified_features.append({"type": "Feature", "properties": props, "geometry": f["geometry"]})
        admin_rows.append((
            "zagreb", code, disp_name, "district", "Grad Zagreb", pop21, 2021, area, dens,
            None, 1760.0, 1760.0, None, None, None, None, None, clon, clat, dist,
            "data.zagreb.hr RPJ_GC + DZS Popis 2021"
        ))
    (BND_DIR / "zagreb_17_cetvrti.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": zg_enriched_feats}, ensure_ascii=False), encoding="utf-8")

    # Add 218 Mjesnih odbora to admin_units
    for f in zg_mo_fc["features"]:
        pr = f["properties"]
        clon, clat = geom_centroid(f["geometry"])
        dist = round(haversine_km(CITY_CBD["zagreb"][0], CITY_CBD["zagreb"][1], clat, clon), 2)
        mo_name = pr.get("IME") or pr.get("NAZIV") or pr.get("MO_NAZIV") or str(pr)
        mo_code = str(pr.get("SIFRA") or pr.get("ID") or "")
        parent_gc = str(pr.get("GC") or pr.get("GC_NAZIV") or "Grad Zagreb")
        admin_rows.append((
            "zagreb", mo_code, str(mo_name), "local_board", parent_gc, None, None, None, None,
            None, None, None, None, None, None, None, None, clon, clat, dist,
            "data.zagreb.hr RPJ_MO (HTRS96->WGS84)"
        ))

    # C4. Sarajevo (9 općina KS) & Travnik from geoBoundaries BIH ADM3
    bih_fc = json.loads((RAW_DIR / "common" / "geoboundaries_BIH_ADM3.geojson").read_text(encoding="utf-8"))
    ks_by_short = {
        "centar": KS_UNITS_VERIFIED[0],
        "hadžići": KS_UNITS_VERIFIED[1],
        "hadzici": KS_UNITS_VERIFIED[1],
        "ilidža": KS_UNITS_VERIFIED[2],
        "ilidza": KS_UNITS_VERIFIED[2],
        "ilijaš": KS_UNITS_VERIFIED[3],
        "ilijas": KS_UNITS_VERIFIED[3],
        "novi grad": KS_UNITS_VERIFIED[4],
        "novo sarajevo": KS_UNITS_VERIFIED[5],
        "stari grad": KS_UNITS_VERIFIED[6],
        "trnovo (bih)": KS_UNITS_VERIFIED[7],
        "trnovo": KS_UNITS_VERIFIED[7],
        "vogošća": KS_UNITS_VERIFIED[8],
        "vogosca": KS_UNITS_VERIFIED[8],
    }
    sa_feats = []
    tr_feats = []
    seen_ks = set()
    for f in bih_fc["features"]:
        sname = (f["properties"].get("shapeName") or "").strip()
        snl = sname.lower()
        clon, clat = geom_centroid(f["geometry"])
        # Filter strictly by Sarajevo Canton bbox to exclude Novi Grad (RS), Trnovo (RS), Istocni Stari Grad
        if 17.95 <= clon <= 18.75 and 43.55 <= clat <= 44.18 and "istočn" not in snl and "istocn" not in snl and "(rs)" not in snl:
            matched = ks_by_short.get(snl)
            if matched and matched[1] not in seen_ks:
                seen_ks.add(matched[1])
                code, uname, area, pop, emp, net_km, gross_km, comp_n, rcn_km, rcn_n = matched
                dens = round(pop / area, 1)
                dist = round(haversine_km(CITY_CBD["sarajevo"][0], CITY_CBD["sarajevo"][1], clat, clon), 2)
                props = {
                    "city_id": "sarajevo", "unit_code": code, "unit_name": uname, "admin_level": "municipality",
                    "population": pop, "population_year": 2024, "area_km2": area, "density_per_km2": dens,
                    "employees": emp, "avg_net_wage_local": net_km, "avg_net_wage_eur": round(net_km * FX_TO_EUR["BAM"], 2),
                    "companies_count": comp_n,
                    "avg_apt_price_local_m2": rcn_km,
                    "avg_apt_price_eur_m2": round(rcn_km * FX_TO_EUR["BAM"], 2) if rcn_km else None,
                    "dist_cbd_km": dist, "source_id": "geoboundaries_BIH_ADM3+FZS_2025+FGU_RCN_2024"
                }
                sa_feats.append({"type": "Feature", "properties": props, "geometry": f["geometry"]})
                unified_features.append({"type": "Feature", "properties": props, "geometry": f["geometry"]})
                admin_rows.append((
                    "sarajevo", code, uname, "municipality", "Kanton Sarajevo", pop, 2024, area, dens,
                    emp, net_km, round(net_km * FX_TO_EUR["BAM"], 2), comp_n, None, None,
                    rcn_km, round(rcn_km * FX_TO_EUR["BAM"], 2) if rcn_km else None,
                    clon, clat, dist, "FZS Kanton Sarajevo 2025/2026 + FGU RCN 2024"
                ))
        elif snl == "travnik":
            area = 529.0
            pop = 50970
            emp = 12993
            net_km = 1156.0
            comp_n = 1172
            rcn_km = 1610.0
            props = {
                "city_id": "travnik", "unit_code": "10901", "unit_name": "Travnik", "admin_level": "municipality",
                "population": pop, "population_year": 2024, "area_km2": area, "density_per_km2": round(pop / area, 1),
                "employees": emp, "avg_net_wage_local": net_km, "avg_net_wage_eur": round(net_km * FX_TO_EUR["BAM"], 2),
                "companies_count": comp_n,
                "avg_apt_price_local_m2": rcn_km, "avg_apt_price_eur_m2": round(rcn_km * FX_TO_EUR["BAM"], 2),
                "dist_cbd_km": 0.0, "source_id": "geoboundaries_BIH_ADM3+FZS_SBK_2025+FGU_RCN_2024"
            }
            tr_feats.append({"type": "Feature", "properties": props, "geometry": f["geometry"]})
            unified_features.append({"type": "Feature", "properties": props, "geometry": f["geometry"]})
            admin_rows.append((
                "travnik", "10901", "Travnik", "municipality", "Srednjobosanski kanton", pop, 2024, area,
                round(pop / area, 1), emp, net_km, round(net_km * FX_TO_EUR["BAM"], 2), comp_n, None, None,
                rcn_km, round(rcn_km * FX_TO_EUR["BAM"], 2), clon, clat, 0.0,
                "FZS SBK u brojkama 2025 + FGU RCN 2024"
            ))

    # Ensure any KS municipality not matched by name in geoBoundaries is still in admin_units
    for m in KS_UNITS_VERIFIED:
        if m[1] not in seen_ks:
            code, uname, area, pop, emp, net_km, gross_km, comp_n, rcn_km, rcn_n = m
            admin_rows.append((
                "sarajevo", code, uname, "municipality", "Kanton Sarajevo", pop, 2024, area, round(pop / area, 1),
                emp, net_km, round(net_km * FX_TO_EUR["BAM"], 2), comp_n, None, None,
                rcn_km, round(rcn_km * FX_TO_EUR["BAM"], 2) if rcn_km else None,
                None, None, None, "FZS Kanton Sarajevo 2025/2026 (no matching GB polygon)"
            ))

    (BND_DIR / "sarajevo_9_opcina_ks.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": sa_feats}, ensure_ascii=False), encoding="utf-8")
    (BND_DIR / "travnik_opcina.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": tr_feats}, ensure_ascii=False), encoding="utf-8")
    (BND_DIR / "all_5cities_admin_units.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": unified_features}, ensure_ascii=False), encoding="utf-8")

    cur.executemany(
        "INSERT INTO admin_units (city_id, unit_code, unit_name, admin_level, parent_name, population, population_year, area_km2, density_per_km2, employees, avg_net_wage_local, avg_net_wage_eur, companies_count, companies_rev_local_k, companies_rev_eur_m, avg_apt_price_local_m2, avg_apt_price_eur_m2, centroid_lon, centroid_lat, dist_cbd_km, source_note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        admin_rows,
    )
    print(f"  Unified GeoJSON: {len(unified_features)} core polygons (BG={len(bg_out_feats)}, ZG={len(zg_enriched_feats)}, SA={len(sa_feats)}, NP={len(np_out_feats)}, TR={len(tr_feats)})")
    print(f"  Total admin_units rows: {len(admin_rows)}")

    # ------------------------------------------------------------------
    # STEP D: Cities Master Table (5 harmonized cities)
    # ------------------------------------------------------------------
    bg_net_w = (rzs_wages.get("Beogradska oblast") or rzs_wages.get("Beogradski region") or {}).get("net_rsd", 149577.0)
    np_net_w = (rzs_wages.get("Novi Pazar") or {}).get("net_rsd", 93278.0)

    cities_data = [
        ("beograd", "Beograd", "SRB", "Serbia", "RSD", FX_TO_EUR["RSD"],
         "Unitarni grad sa 17 gradskih opština (2-stepeni lokalni model)",
         44.8162, 20.4602, bg_pop_total or 1681405, 2022, "Grad Beograd (17 opština, RZS Popis 2022)",
         3222.68, round((bg_pop_total or 1681405) / 3222.68, 1),
         205387000000.0, round(205387000000.0 * FX_TO_EUR["RSD"], 2), "Grad Beograd + 17 opština (2026 usvojeni)",
         round((205387000000.0 * FX_TO_EUR["RSD"]) / (bg_pop_total or 1681405), 2),
         bg_net_w, round(bg_net_w * FX_TO_EUR["RSD"], 2), "Jul 2026 (RZS)",
         254158.0, round(254158.0 * FX_TO_EUR["RSD"], 2), "Poreska osnovica Zona I stanovi 2026 (Ekstra 274.535 RSD/m2)",
         nat_apr["beograd_companies"], "APR privredna društva (17 opština, presek 2026-10-31)",
         "Najveći privredni registar (64.715 firmi + 54.343 RGFI); 14 poreskih zona; RZS 1km grid"),

        ("zagreb", "Zagreb", "HRV", "Croatia", "EUR", 1.0,
         "Grad sa statusom županije (17 gradskih četvrti + 218 mjesnih odbora)",
         45.8131, 15.9775, 767131, 2021, "Grad Zagreb (DZS Popis 2021 konačni)",
         641.24, 1196.3,
         3154000000.0, 3154000000.0, "Konsolidirani proračun Grada Zagreba 2026 (rebalans 3,34 mlrd EUR)",
         round(3154000000.0 / 767131, 2),
         1760.0, 1760.0, "Ljeto 2026 (DZS / Grad Zagreb)",
         3518.0, 3518.0, "DZS prosječna cijena prodanih novih stanova H1 2026",
         None, "Sudski registar (zahtijeva OAuth2 ključ na sudreg-data.gov.hr)",
         "Najdublji otvoreni GIS i fiskalni sloj (218 MO, ZG3D 2022, konsolidirani proračun CSV 2023-2028)"),

        ("sarajevo", "Sarajevo", "BIH", "Bosnia and Herzegovina", "BAM", FX_TO_EUR["BAM"],
         "Trostepeni model: Kanton Sarajevo (9 općina) + Grad Sarajevo (4 općine) + općine (stvarne fiskalne jedinice)",
         43.8590, 18.4290, 421531, 2024, "Kanton Sarajevo 9 općina (Grad Sarajevo 4 općine = 271.484, FZS 30.06.2024)",
         1276.9, 330.1,
         1998591126.0, round(1998591126.0 * FX_TO_EUR["BAM"], 2), "Budžet Kantona Sarajevo 2026 (Grad 26,15M + 4 općine ~254,3M KM zasebno)",
         round((1998591126.0 * FX_TO_EUR["BAM"]) / 421531, 2),
         1704.0, round(1704.0 * FX_TO_EUR["BAM"], 2), "Prosjek 2024 (FZS KS; Centar 1.986 KM)",
         3900.0, round(3900.0 * FX_TO_EUR["BAM"], 2), "FGU RCN 2024 prosjek Centar (Stari Grad 4.020, Novo SA 3.830 KM/m2)",
         23336, "FZS Registar pravnih lica KS 31.12.2024 (+ 7.678 dijelova + 12.876 obrta)",
         "Ključni metodološki nalaz: bez agregacije Kanton+Grad+Općine budžet Sarajeva bi bio neuporediv sa BG i ZG"),

        ("novi_pazar", "Novi Pazar", "SRB", "Serbia", "RSD", FX_TO_EUR["RSD"],
         "Jedinstvena jedinica lokalne samouprave (Grad, 99 naseljenih mesta)",
         43.1367, 20.5122, np_pop, 2022, "Grad Novi Pazar (RZS Popis 2022)",
         742.0, round(np_pop / 742.0, 1),
         5250000000.0, round(5250000000.0 * FX_TO_EUR["RSD"], 2), "Budžet Grada Novog Pazara 2026 (potpisan)",
         round((5250000000.0 * FX_TO_EUR["RSD"]) / np_pop, 2),
         np_net_w, round(np_net_w * FX_TO_EUR["RSD"], 2), "Jul 2026 (RZS)",
         127449.0, round(127449.0 * FX_TO_EUR["RSD"], 2), "Poreska osnovica Zona I stanovi 2026 (poslovni 249.522 RSD/m2)",
         nat_apr["novi_pazar_companies"], "APR privredna društva (presek 2026-10-31; + 470 NVO)",
         "Snažna preduzetničko-trgovačka struktura (poslovni m2 u I zoni 2x skuplji od stana); 99 naselja + 1km grid"),

        ("travnik", "Travnik", "BIH", "Bosnia and Herzegovina", "BAM", FX_TO_EUR["BAM"],
         "Općina u Srednjobosanskom kantonu (SBK/KSB, sjedište kantona)",
         44.2264, 17.6658, 50970, 2024, "Općina Travnik (FZS procjena 30.06.2024)",
         529.0, round(50970 / 529.0, 1),
         39900000.0, round(39900000.0 * FX_TO_EUR["BAM"], 2), "Budžet Općine Travnik 2026 (bez kantonalnog SBK budžeta)",
         round((39900000.0 * FX_TO_EUR["BAM"]) / 50970, 2),
         1156.0, round(1156.0 * FX_TO_EUR["BAM"], 2), "Prosjek 2024 (FZS SBK)",
         1610.0, round(1610.0 * FX_TO_EUR["BAM"], 2), "FGU RCN 2024 prosjek stanova Travnik grad (Vlašić 1.800 KM/m2)",
         1172, "FZS Registar pravnih lica Travnik 31.12.2024 (+ 656 dijelova)",
         "Kompaktan srednjobosanski centar; odlična budžetska serija 2013-2026 + XLS izvršenje + XLSX javni dug"),
    ]
    cur.executemany("INSERT INTO cities VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cities_data)

    # ------------------------------------------------------------------
    # STEP E: Fiscal Budgets + Zagreb Detailed 2026 CSV Budget Lines
    # ------------------------------------------------------------------
    budgets_rows = [
        ("beograd", "Grad Beograd (ukupno: Grad + 17 opština)", "city_consolidated", 2026, "RSD", 205387000000.0, round(205387000000.0*FX_TO_EUR["RSD"],2), None, None, round(176e9*0.13,2), round(176e9*0.61,2), bg_pop_total or 1681405, round(205387000000.0*FX_TO_EUR["RSD"]/(bg_pop_total or 1681405),2), "adopted", "Sl. list grada Beograda 6/2026 (BG_006_2026_001.htm)"),
        ("beograd", "Grad Beograd (gradski nivo bez opština)", "city_core", 2026, "RSD", 190215000000.0, round(190215000000.0*FX_TO_EUR["RSD"],2), None, None, None, None, bg_pop_total or 1681405, round(190215000000.0*FX_TO_EUR["RSD"]/(bg_pop_total or 1681405),2), "adopted", "beograd.rs / Sl. list 6/2026"),
        ("beograd", "Gradske opštine Beograda (17 ukupno)", "municipalities_sum", 2026, "RSD", 15172000000.0, round(15172000000.0*FX_TO_EUR["RSD"],2), None, None, None, None, bg_pop_total or 1681405, round(15172000000.0*FX_TO_EUR["RSD"]/(bg_pop_total or 1681405),2), "adopted", "beograd.rs / Sl. list 6/2026"),
        ("zagreb", "Grad Zagreb (konsolidirani proračun izvorni)", "city_county_consolidated", 2026, "EUR", 3154000000.0, 3154000000.0, None, None, None, 1380000000.0, 767131, round(3154000000.0/767131,2), "adopted", "data.zagreb.hr konsolidirani-plan-prihodi/rashodi-2026 CSV"),
        ("zagreb", "Grad Zagreb (rebalans rujan 2026)", "city_county_consolidated", 2026, "EUR", 3340000000.0, 3340000000.0, None, None, None, None, 767131, round(3340000000.0/767131,2), "rebalanced", "zagreb.hr rujan 2026"),
        ("sarajevo", "Kanton Sarajevo", "canton", 2026, "BAM", 1998591126.0, round(1998591126.0*FX_TO_EUR["BAM"],2), 52782338.0, round(52782338.0*FX_TO_EUR["BAM"],2), None, 456402626.0, 421531, round(1998591126.0*FX_TO_EUR["BAM"]/421531,2), "adopted", "mf.ks.gov.ba budzet-kantona-sarajevo-za-2026-godinu_0.pdf (PDF verifikovano)"),
        ("sarajevo", "Grad Sarajevo (4 gradske općine, gradska administracija)", "city_admin", 2026, "BAM", 26154700.0, round(26154700.0*FX_TO_EUR["BAM"],2), None, None, None, None, 271484, round(26154700.0*FX_TO_EUR["BAM"]/271484,2), "adopted", "sarajevo.ba"),
        ("sarajevo", "Općina Centar Sarajevo", "municipality", 2026, "BAM", 87780000.0, round(87780000.0*FX_TO_EUR["BAM"],2), 40000000.0, round(40000000.0*FX_TO_EUR["BAM"],2), None, None, 51919, round(87780000.0*FX_TO_EUR["BAM"]/51919,2), "adopted", "centar.ba"),
        ("sarajevo", "Općina Novo Sarajevo", "municipality", 2026, "BAM", 70200000.0, round(70200000.0*FX_TO_EUR["BAM"],2), None, None, None, None, 62463, round(70200000.0*FX_TO_EUR["BAM"]/62463,2), "adopted", "novosarajevo.ba"),
        ("sarajevo", "Općina Novi Grad Sarajevo", "municipality", 2026, "BAM", 67280000.0, round(67280000.0*FX_TO_EUR["BAM"],2), None, None, None, None, 123568, round(67280000.0*FX_TO_EUR["BAM"]/123568,2), "adopted", "novigradsarajevo.ba / fena.ba"),
        ("sarajevo", "Općina Stari Grad Sarajevo", "municipality", 2026, "BAM", 29000000.0, round(29000000.0*FX_TO_EUR["BAM"],2), None, None, None, None, 33534, round(29000000.0*FX_TO_EUR["BAM"]/33534,2), "draft_adopted_base", "starigrad.ba"),
        ("novi_pazar", "Grad Novi Pazar", "city", 2026, "RSD", 5252130000.0, round(5252130000.0*FX_TO_EUR["RSD"],2), None, None, 450000000.0, 1412000000.0, np_pop, round(5252130000.0*FX_TO_EUR["RSD"]/np_pop,2), "adopted", "novipazar.rs Budzet za 2026 - potpisan.pdf (PDF verifikovano)"),
        ("novi_pazar", "Grad Novi Pazar", "city", 2025, "RSD", 4800000000.0, round(4800000000.0*FX_TO_EUR["RSD"],2), None, None, 318000000.0, None, np_pop, round(4800000000.0*FX_TO_EUR["RSD"]/np_pop,2), "adopted", "novipazar.rs"),
        ("travnik", "Općina Travnik", "municipality", 2026, "BAM", 39963000.0, round(39963000.0*FX_TO_EUR["BAM"],2), 13242865.29, round(13242865.29*FX_TO_EUR["BAM"],2), None, None, 50970, round(39963000.0*FX_TO_EUR["BAM"]/50970,2), "adopted", "opcinatravnik.com.ba Budzet_za_2026._godinu.pdf (PDF verifikovano)"),
    ]
    cur.executemany(
        "INSERT INTO fiscal_budgets (city_id, entity_name, entity_level, year, currency, total_budget_local, total_budget_eur, capital_expenditure_local, capital_expenditure_eur, property_tax_rev_local, income_tax_rev_local, population_ref, per_capita_eur, status, source_doc) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        budgets_rows,
    )

    # Load Zagreb 2026 CSV revenues & expenditures
    zg_lines = []
    for side, fname in [
        ("revenue", RAW_DIR / "zagreb" / "proracun-grada-zagreba-2026_2e8a08fd_konsolidirani-plan-prihodi-2026-csv.csv"),
        ("expenditure", RAW_DIR / "zagreb" / "proracun-grada-zagreba-2026_e4654d21_konsolidirani-plan-rashodi-2026-csv.csv"),
    ]:
        if fname.exists():
            with open(fname, "r", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.DictReader(f, delimiter=";")
                for row in reader:
                    plan_s = (row.get("Plan") or row.get("PLAN") or "0").replace(".", "").replace(",", ".").strip()
                    try:
                        val = float(plan_s)
                    except ValueError:
                        val = 0.0
                    zg_lines.append((
                        2026, side,
                        row.get("OznakaRazdjela", ""), row.get("NazivRazdjela", ""),
                        row.get("OznakaGlave", ""), row.get("NazivGlave", ""),
                        row.get("OznakaOdjeljka") or row.get("OznakaPodskupine") or row.get("OznakaSkupine") or "",
                        row.get("NazivOdjeljka") or row.get("NazivPodskupine") or row.get("NazivSkupine") or row.get("NazivAktivnosti") or "",
                        val,
                    ))
    cur.executemany(
        "INSERT INTO zagreb_budget_lines (year, side, razdjel_code, razdjel_name, glava_code, glava_name, account_code, account_name, plan_eur) VALUES (?,?,?,?,?,?,?,?,?)",
        zg_lines,
    )
    print(f"  Loaded {len(zg_lines)} detailed Zagreb 2026 budget lines into SQLite")

    # ------------------------------------------------------------------
    # STEP F: Property Zones & Market Prices (all 5 cities)
    # ------------------------------------------------------------------
    prop_rows = []
    prop_rows.extend(parse_beograd_zones())
    prop_rows.extend(parse_novi_pazar_zones())

    # Sarajevo & Travnik from verified FGU RCN 2024 Table 2 & Table 3
    bih_rcn = [
        ("sarajevo", 2024, "Stari Grad Sarajevo", "stan", 4020.0, "BAM", "rcn_market_secondary_avg", 58, "FGU RCN FBiH 2024 Tabela 2"),
        ("sarajevo", 2024, "Centar Sarajevo", "stan", 3900.0, "BAM", "rcn_market_secondary_avg", 220, "FGU RCN FBiH 2024 Tabela 2"),
        ("sarajevo", 2024, "Novo Sarajevo", "stan", 3830.0, "BAM", "rcn_market_secondary_avg", 286, "FGU RCN FBiH 2024 Tabela 2"),
        ("sarajevo", 2024, "Novi Grad Sarajevo", "stan", 3110.0, "BAM", "rcn_market_secondary_avg", 183, "FGU RCN FBiH 2024 Tabela 2"),
        ("sarajevo", 2024, "Ilidža", "stan", 3000.0, "BAM", "rcn_market_secondary_avg", 68, "FGU RCN FBiH 2024 Tabela 2"),
        ("sarajevo", 2024, "Vogošća", "stan", 2800.0, "BAM", "rcn_market_secondary_avg", 83, "FGU RCN FBiH 2024 Tabela 2"),
        ("sarajevo", 2024, "Trnovo (apartmani Bjelašnica)", "apartman", 4040.0, "BAM", "rcn_market_secondary_avg", 26, "FGU RCN FBiH 2024 Tabela 2"),
        ("sarajevo", 2024, "Kompleks Nova Otoka", "stan_kompleks", 3760.0, "BAM", "rcn_market_secondary_avg", 40, "FGU RCN FBiH 2024 Tabela 3"),
        ("sarajevo", 2024, "Kompleks Miljacka", "stan_kompleks", 3470.0, "BAM", "rcn_market_secondary_avg", 35, "FGU RCN FBiH 2024 Tabela 3"),
        ("sarajevo", 2024, "Kompleks Bulevar", "stan_kompleks", 3120.0, "BAM", "rcn_market_secondary_avg", 52, "FGU RCN FBiH 2024 Tabela 3"),
        ("sarajevo", 2024, "Kompleks Tibra Stup", "stan_kompleks", 2610.0, "BAM", "rcn_market_secondary_avg", 159, "FGU RCN FBiH 2024 Tabela 3"),
        ("travnik",  2024, "Travnik (grad)", "stan", 1610.0, "BAM", "rcn_market_secondary_avg", 48, "FGU RCN FBiH 2024 Tabela 2"),
        ("travnik",  2024, "Travnik (apartmani Vlašić)", "apartman", 1800.0, "BAM", "rcn_market_secondary_avg", 21, "FGU RCN FBiH 2024 Tabela 2"),
        ("zagreb",   2026, "Grad Zagreb (sve novogradnje H1 2026)", "stan_novogradnja", 3518.0, "EUR", "dzs_market_newbuild_avg", None, "DZS H1 2026"),
        ("zagreb",   2026, "Grad Zagreb (komercijalna novogradnja bez POS)", "stan_novogradnja", 3554.0, "EUR", "dzs_market_newbuild_avg", None, "DZS H1 2026"),
    ]
    for cid, yr, zu, pt, val, ccy, basis, sn, sdoc in bih_rcn:
        prop_rows.append({
            "city_id": cid, "year": yr, "zone_or_unit": zu, "property_type": pt,
            "price_local_m2": val, "currency": ccy, "price_eur_m2": round(val * FX_TO_EUR[ccy], 2),
            "basis": basis, "sample_n": sn, "source_doc": sdoc,
        })

    cur.executemany(
        "INSERT INTO property_zones_prices (city_id, year, zone_or_unit, property_type, price_local_m2, currency, price_eur_m2, basis, sample_n, source_doc) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [(r["city_id"], r["year"], r["zone_or_unit"], r["property_type"], r["price_local_m2"], r["currency"], r["price_eur_m2"], r["basis"], r["sample_n"], r["source_doc"]) for r in prop_rows],
    )
    print(f"  Inserted {len(prop_rows)} property_zones_prices rows across all 5 cities")

    # ------------------------------------------------------------------
    # STEP G: OSM Economic POIs (for every city file present on disk)
    # ------------------------------------------------------------------
    poi_batch = []
    poi_counts_city = Counter()
    for cid, (cbd_lat, cbd_lon) in CITY_CBD.items():
        p = RAW_DIR / cid / f"osm_economic_pois_{cid}.json"
        if not p.exists():
            continue
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for el in obj.get("elements", []):
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")
            if lat is None or lon is None:
                continue
            tags = el.get("tags") or {}
            cat, sub = classify_osm_poi(tags)
            dist = round(haversine_km(cbd_lat, cbd_lon, lat, lon), 3)
            if dist <= 1.0: ring = "0-1km"
            elif dist <= 3.0: ring = "1-3km"
            elif dist <= 6.0: ring = "3-6km"
            else: ring = "6km+"
            poi_batch.append((cid, el.get("type"), el.get("id"), cat, sub, tags.get("name"), lat, lon, dist, ring))
            poi_counts_city[cid] += 1

    cur.executemany(
        "INSERT INTO osm_pois (city_id, osm_type, osm_id, category, subcategory, name, lat, lon, dist_cbd_km, ring_km) VALUES (?,?,?,?,?,?,?,?,?,?)",
        poi_batch,
    )
    print(f"  Inserted {len(poi_batch)} OSM economic POIs: {dict(poi_counts_city)}")

    # ------------------------------------------------------------------
    # STEP H: World Bank Macro Indicators
    # ------------------------------------------------------------------
    wb_batch = []
    for p in sorted((RAW_DIR / "common").glob("worldbank_*.json")):
        try:
            arr = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(arr, list) and len(arr) >= 2 and isinstance(arr[1], list):
                for rec in arr[1]:
                    if rec.get("value") is not None:
                        wb_batch.append((
                            rec.get("countryiso3code"),
                            (rec.get("indicator") or {}).get("id"),
                            (rec.get("indicator") or {}).get("value"),
                            int(rec["date"]),
                            float(rec["value"]),
                        ))
        except Exception:
            pass
    cur.executemany(
        "INSERT INTO macro_worldbank (country_iso3, indicator_id, indicator_name, year, value) VALUES (?,?,?,?,?)",
        wb_batch,
    )
    print(f"  Inserted {len(wb_batch)} World Bank macro rows")

    # ------------------------------------------------------------------
    # STEP I: Sources Manifest
    # ------------------------------------------------------------------
    if MANIFEST_PATH.exists():
        m_batch = []
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                m = json.loads(line)
                m_batch.append((
                    m.get("checked_at"), m.get("city"), m.get("layer"), m.get("source_name"),
                    m.get("url"), m.get("http_status"), 1 if m.get("ok") else 0,
                    m.get("bytes"), m.get("sha256"), m.get("local_path"), m.get("error")
                ))
        cur.executemany(
            "INSERT INTO sources_manifest (checked_at, city, layer, source_name, url, http_status, ok, bytes, sha256, local_path, error) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            m_batch,
        )
        print(f"  Inserted {len(m_batch)} manifest rows")

    # ------------------------------------------------------------------
    # STEP J: Indexes & Analytical Views
    # ------------------------------------------------------------------
    cur.executescript("""
    CREATE INDEX idx_companies_city_op ON companies_sr(city_id, opstina_code);
    CREATE INDEX idx_companies_nace ON companies_sr(city_id, nace_section);
    CREATE INDEX idx_pois_city_cat ON osm_pois(city_id, category, ring_km);
    CREATE INDEX idx_units_city_lvl ON admin_units(city_id, admin_level);

    CREATE VIEW v_city_comparison AS
    SELECT
        city_id, name, country_iso3, currency,
        population, population_year, area_km2, density_per_km2,
        ROUND(budget_2026_eur / 1e6, 2) AS budget_2026_eur_m,
        budget_per_capita_eur,
        avg_net_wage_eur,
        avg_apt_price_eur_m2,
        ROUND(avg_net_wage_eur / NULLIF(avg_apt_price_eur_m2, 0), 3) AS affordability_m2_per_wage,
        ROUND((avg_apt_price_eur_m2 * 55.0) / NULLIF(avg_net_wage_eur * 12.0, 0), 2) AS years_wage_for_55m2,
        registered_companies
    FROM cities
    ORDER BY population DESC;

    CREATE VIEW v_beograd_opstine_economy AS
    SELECT
        u.unit_code, u.unit_name, u.population, u.area_km2, u.density_per_km2,
        u.avg_net_wage_eur,
        u.companies_count,
        u.employees AS apr_employees,
        u.companies_rev_eur_m,
        ROUND(u.companies_rev_eur_m * 1e6 / NULLIF(u.population, 0), 0) AS apr_rev_eur_per_capita,
        u.dist_cbd_km
    FROM admin_units u
    WHERE u.city_id = 'beograd' AND u.admin_level = 'municipality'
    ORDER BY u.companies_rev_eur_m DESC;

    CREATE VIEW v_bid_rent_profiles AS
    SELECT city_id, year, zone_or_unit, property_type, price_local_m2, currency, price_eur_m2, basis, sample_n
    FROM property_zones_prices
    WHERE property_type IN ('stan', 'poslovne_zgrade', 'gradjevinsko_zemljiste', 'stan_novogradnja', 'apartman')
    ORDER BY city_id, property_type, price_eur_m2 DESC;

    CREATE VIEW v_sector_specialization_lq AS
    SELECT city_id, unit_name, nace_section, nace_name, companies_count, unit_share_pct, benchmark_share_pct, location_quotient, benchmark_scope
    FROM sector_structure
    WHERE location_quotient >= 1.20 AND companies_count >= 15
    ORDER BY city_id, location_quotient DESC;

    CREATE VIEW v_osm_centrality_rings AS
    SELECT city_id, ring_km, category, COUNT(*) AS poi_count, ROUND(AVG(dist_cbd_km), 2) AS avg_dist_km
    FROM osm_pois
    GROUP BY city_id, ring_km, category
    ORDER BY city_id, ring_km, poi_count DESC;
    """)

    conn.commit()

    # ------------------------------------------------------------------
    # STEP K: Export Curated CSV Tables
    # ------------------------------------------------------------------
    exports = [
        ("cities_comparison.csv", "SELECT * FROM v_city_comparison"),
        ("admin_units_all.csv", "SELECT * FROM admin_units"),
        ("fiscal_budgets_2025_2026.csv", "SELECT * FROM fiscal_budgets"),
        ("property_zones_prices.csv", "SELECT * FROM property_zones_prices"),
        ("sector_structure_lq.csv", "SELECT * FROM sector_structure"),
        ("beograd_opstine_economy.csv", "SELECT * FROM v_beograd_opstine_economy"),
        ("osm_centrality_rings.csv", "SELECT * FROM v_osm_centrality_rings"),
        ("macro_worldbank.csv", "SELECT * FROM macro_worldbank"),
    ]
    for fname, sql in exports:
        rows = cur.execute(sql).fetchall()
        cols = [d[0] for d in cur.description]
        with open(TBL_DIR / fname, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)

    print("\n=== FINAL VERIFICATION SUMMARY ===")
    for tbl in ["cities", "admin_units", "fiscal_budgets", "zagreb_budget_lines", "property_zones_prices", "companies_sr", "sector_structure", "osm_pois", "macro_worldbank", "sources_manifest"]:
        cnt = cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"  {tbl:25s}: {cnt:,}")

    print("\n--- v_city_comparison ---")
    for r in cur.execute("SELECT * FROM v_city_comparison"):
        print(" ", r)

    conn.close()
    print(f"\nSQLite DB built successfully: {DB_PATH} ({DB_PATH.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build_all()
