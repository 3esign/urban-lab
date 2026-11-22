# Urban Lab „Ekonomija grada“ — Nadogradnja baze v4.1 → v4.2 (Talas 5)

**Sesija:** `c1795299369016b6gi`  
**Datum:** `2026-11-22`  
**Živa baza (v4.2):** `curated/urban_lab_5cities_v4.sqlite` (**129,12 MB**, `PRAGMA integrity_check = ok`, `PRAGMA foreign_key_check = 0`, **28/28 pogleda bez greške**)  
**Osnovna v3 baza:** `curated/urban_lab_5cities.sqlite` (**100% netaknuta**)  
**Migraciona šema:** `schema_v4/migration_v4_2.sql` (verzionisana kao `v4.2.0-upgrade`, strogo aditivna)  
**Verifikacioni JSON:** `curated/analysis/v4_2_upgrade_summary.json`

---

## 1. Šta je unapređeno (v4.1 → v4.2: pre i posle)

| Dimenzija / Tabela | v4.1 (pre) | v4.2 (posle) | Gradova | Ključna promena |
|---|---:|---:|---:|---|
| **Veličina baze / Integritet** | 91,84 MB (1 pokvaren pogled) | **129,12 MB** (`ok`, 0 FK grešaka) | **5/5** | Popravljen `v_osm_centrality_rings`, dodati indeksi i materijalizovani keš |
| **Ispravni pogledi (`views`)** | 20/21 | **28/28** | **5/5** | +7 novih GIS/executive pogleda; `v_election_procurement_zone_join`: **1.242 ms → 5,4 ms (230× brže)** |
| **Prazne ključne v4 tabele** | **7 praznih** | **0 praznih** | **5/5** | Popunjene sve: `election_station_crosswalk`, `entity_aliases`, `event_evidence_links`, `provenance_claims`, `xs_cadastral_parcels`, `xs_zoning_envelopes`, `xs_building_permits` |
| **`evidence_documents`** | 2.118 | **2.942** | **5/5** | +700 EU TED, +113 EU CORDIS, +5 Ookla, +5 dozvola, +1 Sjenica |
| **`entities` / `entity_aliases`** | 233 / 0 | **883 / 1.733** | **5/5** | TED kupci i pobednici, CORDIS institucije, Top APR firme (BG/NP), SEPA postrojenja, stranke |
| **`entity_relations`** | 10 | **306** | **4/5** | +296 realnih `awarded_contract_to` veza (EU TED) + 10 naučnih koautorstava |
| **`domain_signals_procurement`** | 1.150 (samo BiH) | **1.850** | **4/5** | +300 Zagreb (**469,04 M EUR**), +200 Srbija/BG, +200 BiH/SA (EU TED v3 `A1`) + 1.150 BiH EJN |
| **`domain_signals_science`** | 525 | **638** | **5/5** | +113 EU CORDIS Horizon projekata (**60,0 M EUR** ukupno po gradovima, `A1`) |
| **`domain_signals_sensors`** | 531 | **1.957** | **5/5** | +1.020 ERA5 (HDD18/mraz/≥35°C), +373 WB WDI, Ookla, SEPA, Zagreb tržište, Sensor.Community |
| **`xs_buildings_3d` + R-Tree** | 9.298 (`NP: 5, TR: 43`) | **32.385** (`NP: 17.200, TR: 5.935`) | **5/5** | +23.087 realnih OSM/Geofabrik otisaka za NP i TR (pošteno obeleženih `D` bez pranja poverenja!) |
| **`ookla_broadband_tiles` + R-Tree** | *nije postojalo* | **5.179** (155.617 merenja) | **5/5** | Univerzalna `A1` 610m širokopojasna mreža (Ookla Q4 2025) za svih 5 gradova |
| **`transit_stops` + R-Tree** | *nije postojalo* | **10.678** | **5/5** | 9.705 `A1` GTFS stajališta (BG 5.902, ZG 3.803) + 973 `C` OSM stajališta (SA 941, TR 20, NP 12) |
| **`xs_cadastral_parcels` / `xs_zoning_envelopes`** | 0 / 0 | **84 / 84** (`3.293` povezanih zgrada) | **5/5** | 58 realnih katastarskih opština Zagreba (`DKP_K_OPCINA`) + referentne zone BG/NP/SA/TR; `v_xs_development_rent_gap` aktivan za 5/5 gradova |
| **`election_station_crosswalk`** | 0 | **605** | **1/5 (ZG)** | Determinističko uparivanje DIP 2024 Parl ↔ DIP 2025 Skupština/Gradonačelnik + `28.717` rezultata vezano za entitete stranaka |
| **`zagreb_real_estate_market` / `sepa_industrial_emissions`** | *nije postojalo* | **418 / 148** | **ZG / SRB** | Zvanični promet i gradski najam stanova ZG (2022–2024) + SEPA 2024 PRTR industrijske emisije |
| **`urban_events` / `event_studies` / `provenance_claims`** | 1 / 1 / 0 | **5 / 3 / 6** | **5/5** | 35 dokaza u `event_evidence_links`; 3 DiD studije (`ES-01`, `ES-03`, `ES-04`); 6 revidiranih tragova porekla |

---

## 2. Novi empirijski nalazi iz žive baze v4.2

### 2.1. Master uporedna tabela 5 gradova (`v_5cities_master_scorecard`)

| Grad | Stan. | Budžet EUR/st | Plata EUR | Kvadrat EUR/m² | Nabavke (`N` / M EUR) | EU CORDIS (`N` / M EUR) | 3D zgrade (`N` / M m³) | Prevoz (staj.) | Ookla DL (Mbps) | Pros. PM2.5 | HDD18 (2025) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Beograd** | 1.681.405 | 1.044 | 1.278 | 2.172 | 200 / TED IPA* | **38 / 31,83** | 1.824 / 14,12 | **5.902** (`A1`) | 215,07 | 19,57 | 2.269 |
| **Zagreb** | 767.131 | **4.111** | **1.760** | **3.518** | 300 / **469,04** | 37 / 21,76 | 6.496 / **338,92** | 3.803 (`A1`) | **301,57** | 18,52 | 2.561 |
| **Sarajevo** | 421.531 | 2.424 | 871 | 1.994 | **1.050** / 15,92 | 37 / 6,31 | 930 / 8,65 | 941 (`C`) | 114,26 | **23,75** | 2.556 |
| **Novi Pazar** | 106.720 | 421 | 797 | 1.089 | 0 | 0 / 0,00 | **17.200** / 21,38 | 12 (`C`) | **150,03** | 12,40* | **2.728** |
| **Travnik** | 50.970 | 400 | 591 | 823 | 300 / 2,57 | 1 / 0,08 | 5.935 / 7,62 | 20 (`C`) | 68,61 | 13,78* | 2.629 |

*\*Napomene o izvorima:* (a) SRB TED obaveštenja su pretežno prethodne objave/IPA tenderi bez popunjene finalne dodeljene vrednosti u `result-value-notice`; (b) godišnji prosek `PM2.5` u tabeli je Copernicus CAMS 10 km rešetka — prizemni senzori `Sensor.Community` od 22.11.2026. direktno potvrđuju dolinsku inverziju u manjim gradovima: **Travnik `84,75 µg/m³`**, **Novi Pazar `40,90 µg/m³`** naspram **Beograda `9,04 µg/m³`** i **Zagreba `6,32 µg/m³`**.

### 2.2. Digitalni jaz 5 gradova — jezgro vs. periferija (`v_ookla_digital_divide_by_city`, Q4 2025 `A1`)

| Grad | 610m pločica | Testova | Pond. DL (Mbps) | Pond. UL (Mbps) | Latencija (ms) | Jezgro 0–3 km (Mbps) | Periferija >6 km (Mbps) | Odnos jezgro/periferija |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Zagreb** | 1.807 | 54.372 | **301,57** | **176,28** | **6,08** | 262,73 | **280,00** | **0,94×** (zrela FTTH mreža i u prstenu) |
| **Beograd** | 2.143 | 72.553 | 215,07 | 114,66 | 7,75 | 188,22 | 158,91 | 1,18× |
| **Novi Pazar** | 181 | 3.848 | **150,03** | **81,85** | 12,77 | 137,28 | 48,23 | **2,85×** (najstrmiji unutar-gradski jaz!) |
| **Sarajevo** | 787 | 22.715 | 114,26 | 22,73 | 10,88 | 113,32 | 87,69 | 1,29× (niski upload: DOCSIS/xDSL) |
| **Travnik** | 261 | 2.129 | 68,61 | 12,51 | 20,96 | 58,67 | 52,95 | 1,11× (4,4× sporiji DL, 14× sporiji UL od ZG) |

---

## 3. Transparentne granice i preostale rupe

1. **Nacionalne javne nabavke Srbije (JN Portal / UJN):** `jnportal.ujn.gov.rs` vraća HTTP 401 bez autentifikacije, a `data.gov.rs` za upit `набавке` vraća 0 skupova → Beograd ima 200 EU TED/IPA tendera, dok Novi Pazar ostaje na 0 u `domain_signals_procurement` dok se ne obezbedi direktan UJN/CEOP dump.
2. **RZS građevinske dozvole (`opendata.stat.gov.rs`):** WCF CSV servis (`050202IND01` i `050204IND01`) ponovo je vratio timeout; `xs_building_permits` je popunjen zvaničnim godišnjim agregatima za svih 5 gradova (`A2`), a ne pojedinačnim rešenjima po parceli.
3. **BiH EJN dobavljači (`winner_entity_id`):** `open.ejn.gov.ba/Awards` i `LotContracts` ne izlažu polje `SupplierName` u javnom OData pogledu bez posebnog povezivanja; zato je `winner_entity_id` popunjen za **296 EU TED** ugovora (uglavnom Zagreb, npr. Grad Zagreb → Petrol 92,98 M EUR, Plinacro → Monter 51,84 M EUR, HEP → Končar 15,10 M EUR), dok BiH EJN čuva ugovorne organe (`buyer_entity_id`) i broj ponuđača (`single_bidder_flag`).
4. **Disk higijena:** Privremeni arhive (Ookla 240 MB + Geofabrik SRB 457 MB + BiH 384 MB = 1,08 GB) obrađene su strimingom u `data/brain/scratch/` i odmah obrisane — ceo `urban_lab_db/` folder zauzima **~653 MB**.
