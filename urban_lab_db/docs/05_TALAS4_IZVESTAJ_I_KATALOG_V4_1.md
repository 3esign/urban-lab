# Urban Lab „Ekonomija grada“ — Talas 4: Veliko sakupljanje i živa baza v4.1 (5 gradova)

**Sesija:** `c1795299369016b6gi`  
**Datum:** `2026-11-22`  
**Opseg:** Beograd, Zagreb, Sarajevo, Novi Pazar, Travnik (+ L-prstenovi)  
**Nova živa baza (v4.1):** `curated/urban_lab_5cities_v4.sqlite` (**91,84 MB**, **26** netaknutih v3 tabela + **29** v4.1 logičkih tabela + **4** virtuelne `FTS5`/`R-Tree` tabele + **21** pogled, **`PRAGMA foreign_key_check = 0`**)  
**Osnovna baza (v3):** `curated/urban_lab_5cities.sqlite` (**100% netaknuta**)  
**Ukupan disk otisak (`urban_lab_db/`):** **544 fajla / 558,20 MB** (samo Talas 4 sirovi podaci `raw/wave4/`: **223 fajla / 246,78 MB**, **400** zapisa sa SHA-256 tragom u `sources_manifest`)

---

## 1. Šta je prikupljeno i učitano u bazu v4.1 (pregled 7 stubova)

| Stub / Domen | Primarni izvori | `trust_tier` | Obim u `urban_lab_5cities_v4.sqlite` | Pokrivenost 5 gradova |
|---|---|---:|---|---|
| **0. Lokalni Gazetteer (NLP→GIS)** | Bootstrap iz 8 v3 tabela + popravljen ZG `JMS_IME` (218 MO) | `A1/A2/B` | **2.043** mesta, **6.218** aliasa (**363** dvosmislena), **2.043** R-Tree bbox-a | **5/5** (`BG, ZG, SA, NP, TR`) |
| **1. Izborna geografija (BM)** | RIK SRB (`rezultatiizbora.rs`), DIP HRV (`izbori.hr` 2024+2025), CIK BiH (`izbori.ba` 2024) | **`A1`** | **5** izbornih ciklusa, **3.479** biračkih mesta, **74.025** rezultata lista | **5/5** (`BG 1180, NP 99, ZG 1816, SA 308, TR 76`) |
| **2. Javne nabavke** | BiH Portal javnih nabavki (`open.ejn.gov.ba` OData API) | **`A1`** | **1.150** ugovora, **221** ugovorni organ (JIB), **18,49 M EUR** (`36,17 M BAM`) | **2/5** šampionski BiH modul (`SA 850, TR 300`) |
| **3. Nauka O i U gradu** | OpenAlex API (`works`, `institutions`, koautorstvo) | **`B`** | **12** univerziteta/instituta, **525** radova (**86.018** citata), **10** koautorskih veza | **5/5** (`ZG 125, SA 123, BG 121, NP 82, TR 74`) |
| **4. Vesti & javni puls** | **15** lokalnih/regionalnih RSS + **GDELT DOC 2.0** | **`C`** | **442** članka → **2.157** ukupnih NLP→GIS geo-pominjanja (`documents_fts` indeks) | **5/5** (`BG 180, SA 90, ZG 79, NP 62, TR 30`) |
| **5. Nezavisni senzori & GTFS** | Open-Meteo CAMS AQ + ERA5 (2024–2026), World Bank (2015–2025), GTFS BG & ZET, Sjenica 2026, SEPA 2024 | **`A1/A2`** | **531** mesečna/godišnja senzorska opservacija (iz **173.880** satnih AQ + **5.175** dnevnih WX merenja) + **9.705** GTFS stajališta | **5/5** univerzalni AQ/WX/WB; GTFS za `BG + ZG` |
| **6. 3D / XS objekti + R-Tree** | Grad Zagreb ZG3D LiDAR (3 četvrti) + OSM 3D (Overpass) | **`A1/B/C`** | **9.298** 3D zgrada + **9.298** R-Tree zapisa (`361,9 M m³` zapremine) | **5/5** (`ZG 6496 A1, BG 1824, SA 930, TR 43, NP 5`) |

---

## 2. Ključni empirijski nalazi iz žive baze v4.1

### 2.1. Izborna geografija po biračkim mestima (`v_election_station_metrics` — 3.479 BM, `A1`)

| Grad | Izbori | Organ | Broj BM | Upisani birači (uzorak) | Ponder. izlaznost | Nevažeći | Pros. margina (pp) | Laakso–Taagepera ENP |
|---|---|---|---:|---:|---:|---:|---:|---:|
| **Beograd** | Parlamentarni 2023 | RIK | 1.180 | 1.605.877 | **59,02%** | 2,51% | 20,81 | 3,224 |
| **Novi Pazar** | Parlamentarni 2023 | RIK | 99 | 91.163 | **50,72%** | 4,52% | 28,83 | 2,894 |
| **Zagreb** | Parlamentarni 2024 | DIP | 606 | 652.313 | **67,77%** | 2,22% | **6,13** | 4,396 |
| **Zagreb** | Lokalni 2025 (Skupština) | DIP | 605 | 667.789 | **42,61%** | 1,86% | 26,58 | 4,145 |
| **Zagreb** | Lokalni 2025 (Gradonačelnik) | DIP | 605 | 667.752 | **42,62%** | 1,71% | 30,44 | 3,529 |
| **Sarajevo (9 općina)** | Lokalni 2024 (Opć. vijeća) | CIK | 308 | 207.214 | **44,81%** | **6,16%** | 13,14 | **4,783** |
| **Travnik** | Lokalni 2024 (Opć. vijeće) | CIK | 76 | 47.438 | **48,79%** | 5,16% | **49,95** | **2,212** |

- **Prostorna polarizacija Beograda (Tiebout sortiranje uživo):** na svih 1.180 GPS-geokodiranih biračkih mesta vidi se oštra linija razdvajanja koja prati v3 gradijent plata i poreskih zona: u centralnim opštinama sa najvišom platom (**Vračar 63/63 BM = 100%**, **Stari grad 56/56 = 100%**, **Savski venac 33/35 = 94,3%**, **Novi Beograd 120/142 = 84,5%**) pobeđuje građanska opozicija, dok u prigradskom prstenu (**Mladenovac 59/59**, **Obrenovac 55/55**, **Grocka 40/40**, **Sopot 33/33**, **Barajevo 28/28**, **Surčin 27/27**) 100% biračkih mesta dobija nacionalna vlast.
- **Zagreb — demobilizacija na lokalnim izborima:** pad izlaznosti od **−25,16 pp** između parlamentarnih (67,77%, margina 6,13 pp) i lokalnih izbora 2025 (42,61%, margina 26,58 pp za Skupštinu i 30,44 pp za Gradonačelnika).

### 2.2. Public Choice spoj: izborna fragmentacija vs. javne nabavke (`v_election_procurement_zone_join`)

Direktno SQL spajanje CIK 2024 biračkih mesta i BiH `open.ejn.gov.ba` ugovora po opštinama Sarajeva i Travnika daje neočekivan empirijski rezultat:

| Zona / Općina | Grad | BM (`N`) | Izlaznost | Margina (pp) | ENP | EJN ugovori | Vrednost (M EUR) | 1 ponuđač (`single_bidder`) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **Ilidža** | Sarajevo | 45 | 44,47% | 11,45 | 4,033 | 250 | **5,755** | 13,20% |
| **Ilijaš** | Sarajevo | 35 | 55,94% | 17,78 | 3,242 | 48 | **2,999** | 8,33% |
| **Centar Sarajevo** | Sarajevo | 45 | 41,92% | 8,11 | 5,344 | 230 | **2,595** | **16,09%** |
| **Travnik** | Travnik | 76 | 49,83% | **49,95** | **2,212** | 300 | **2,568** | **8,67%** |
| **Novo Sarajevo** | Sarajevo | 44 | 39,95% | **5,12** | **6,520** | 105 | **1,435** | **20,00%** |
| **Novi Grad Sarajevo** | Sarajevo | 45 | 39,43% | 10,94 | 5,445 | 33 | 1,152 | 9,09% |
| **Hadžići** | Sarajevo | 37 | 55,04% | 26,40 | 3,319 | 52 | 1,085 | 11,54% |
| **Vogošća** | Sarajevo | 17 | 44,31% | 16,97 | 4,318 | 100 | 0,581 | 2,00% |
| **Stari Grad Sarajevo** | Sarajevo | 35 | 42,85% | 8,19 | 5,719 | 32 | 0,321 | 6,25% |

*Uvid:* suprotno prostoj intuiciji da viša stranačka konkurencija automatski smanjuje koncentraciju javnih nabavki, najfragmentiranije urbane općine Sarajeva (**Novo Sarajevo ENP 6,52** i **Centar ENP 5,34**) imaju **viši udeo ugovora sa jednim ponuđačem (20,0% i 16,1%)** od politički dominantnog **Travnika (ENP 2,21, single-bidder 8,67%)** — što delom odražava specijalizovane komunalne/kliničke/kantonalne nabavke locirane u centru Sarajeva i opravdava strukturno (ne optužujuće!) praćenje CPV kategorija.

### 2.3. Vazduh, energetsko siromaštvo, klima i ES-03 DiD (`Open-Meteo CAMS + ERA5`, `A1`, 2024–2026)

| Grad / Tačka | Zimski $\text{PM}_{2.5}$ (nov–feb) | Letnji $\text{PM}_{2.5}$ (jun–avg) | Pik mesec $\text{PM}_{2.5}$ | Zima / Leto | 2025 Grejni dani (`HDD18`) | 2025 Mrazni dani / ≥35°C |
|---|---:|---:|---:|---:|---:|---:|
| **Sarajevo — Ilidža & Istočno SA** | **44,84 µg/m³** | 12,85 µg/m³ | **60,62 µg/m³** | **3,49×** | 2.556 | 60 / 4 |
| **Zagreb CBD** | 33,79 µg/m³ | 8,69 µg/m³ | 48,92 µg/m³ | **3,89×** | 2.561 | 60 / 1 |
| **Beograd CBD** | 33,50 µg/m³ | 10,81 µg/m³ | 44,64 µg/m³ | 3,10× | 2.269 | 49 / **15** |
| **Sarajevo — Centar** | 32,24 µg/m³ | 10,45 µg/m³ | 42,63 µg/m³ | 3,09× | 2.556 | 60 / 4 |
| **Travnik CBD** | 20,98 µg/m³ | 8,91 µg/m³ | 29,89 µg/m³ | 2,35× | 2.629 | 48 / 0 |
| **Novi Pazar CBD** | 18,55 µg/m³ | 8,13 µg/m³ | 23,94 µg/m³ | 2,28× | **2.728** | **81** / 11 |

- **Metodološki nalaz (rezolucija senzora):** Copernicus CAMS (~10 km rešetka) jasno hvata zimsku temperaturnu inverziju zapadne sarajevske kotline (**Ilidža / Istočno Sarajevo 44,84 µg/m³**, pik 60,62) i panonske zime Zagreba i Beograda, ali u uskim dolinama **Novog Pazara i Travnika** prostorno usrednjava dolinsko loženje sa okolnim planinama (pa je za NP i TR neophodno dodati prizemne stanice SEPA/FHMZ!). Istovremeno, ERA5 pokazuje da je **Novi Pazar klimatski najzahtevniji za grejanje (2.728 HDD i 81 mrazni dan u 2025)**, dok **Beograd ima najsnažniji letnji toplotni stres (15 dana ≥35°C)**.
- **ES-03 DiD (`v_event_study_did_summary`):** za zimu 2025/26 (`t0 = 2025-11-01`), Sarajevo Centar skače za `+22,36 µg/m³` (10,92 → 33,28), dok Zagreb CBD beleži `+26,30 µg/m³` (9,35 → 35,65), pa je `did_estimate = -3,94 µg/m³` (`derived_trust_tier = D`, `min_upstream_tier = A1`).

### 2.4. Naučna mreža 5 gradova, doznake dijaspore i GTFS mobilnost

- **OpenAlex naučna gravitacija (2016–2026):** koautorsku mrežu nose tri velike metropole — **UB ↔ UNIZG (1.096 zajedničkih radova)**, **UB ↔ UNSA (463)**, **UNIZG ↔ UNSA (433)**. Univerziteti srednjih gradova oslanjaju se na svoje glavne gradove — **UB ↔ DUNP Novi Pazar (219)** i **UNSA ↔ Univerzitet u Travniku (44)** — dok je direktna saradnja između manjih gradova gotovo nulta (**NP ↔ TR: 6 radova**, **ZG ↔ TR: 5**).
- **World Bank 2025 — paradoks doznaka vs. R&D:**
  - **BiH:** doznake = **10,72% BDP-a (3,49 mlrd USD)** naspram R&D ulaganja od svega **0,21% BDP-a** (odnos **50 : 1**!).
  - **Hrvatska:** doznake = **6,90% BDP-a (7,25 mlrd USD)**, R&D = **1,39% BDP-a**, BDP PPP/st = **50.946 USD**, nezaposlenost = **5,00%**.
  - **Srbija:** doznake = **6,56% BDP-a (6,56 mlrd USD)**, R&D = **0,94% BDP-a**, BDP PPP/st = **33.910 USD**, nezaposlenost = **7,12%**.
- **GTFS javni prevoz (`A1`, novembar 2026):** **Beograd** ima **5.902 stajališta** (3.304 gradska + 2.598 prigradska), **533 linije** (10 tramvajskih, 6 trolejbuskih, 517 autobuskih) i **81.509 polazaka**; **Zagreb ZET** ima **3.803 stajališta**, **154 linije** (19 tramvajskih, 135 autobuskih) i **51.015 polazaka**.
- **Sjenica 2026 (L-prsten Novog Pazara, `data.gov.rs`):** zvanična poreska osnovica u Zoni I iznosi **75.044 RSD/m² (~641 EUR/m²)** za stanove, dok prenamena poljoprivrednog (43,2 RSD/m²) u građevinsko zemljište (4.638 RSD/m²) stvara skok vrednosti od **107,4×** — potvrđujući obrazac iz Novog Pazara i u L-okruženju.

### 2.5. 3D / XS morfologija objekata (`xs_buildings_3d` + `xs_buildings_rtree`)

| Grad | Izvor visine | `trust_tier` | Broj zgrada | Otisak (`km²`) | 3D zapremina (`M m³`) | Pros. visina | Max visina |
|---|---|---:|---:|---:|---:|---:|---:|
| **Zagreb** (3 četvrti) | `lidar_3d_city_model` (ZG3D) | **`A1`** | **6.496** | 15,849 | **338,92** | 17,03 m | 96,55 m |
| **Beograd** (Stari grad + Ušće) | `osm_explicit_height` + `osm_levels_estimated` | **`B / C`** | **1.824** | 0,776 | **14,12** | 16,35 m | 115,00 m |
| **Sarajevo** (Centar/SG/NS) | `osm_explicit_height` + `osm_levels_estimated` | **`B / C`** | **930** | 0,485 | **8,65** | 14,10 m | 100,00 m |
| **Travnik** (Centar) | `osm_explicit_height` + `osm_levels_estimated` | **`B / C`** | **43** | 0,018 | **0,16** | 9,31 m | 25,00 m |
| **Novi Pazar** (Zona I) | `osm_levels_estimated` | **`C`** | **5** | 0,006 | **0,05** | 7,68 m | 9,60 m |

*Provera brzine i integriteta:* `xs_buildings_rtree` viewport upit za centar Zagreba vraća **1.597** zgrada nativno bez SpatiaLite-a; `documents_fts` FTS5 pretraga vraća **928** dokumenata.

---

## 3. Poznate granice pokrivenosti i sledeće rupe (transparentna evidencija)

1. **Javne nabavke za Srbiju i Hrvatsku:** BiH `open.ejn.gov.ba` radi savršeno (1.150 ugovora), dok `data.gov.rs` trenutno vraća prazan skup za upit `javne nabavke`, a HR EOJN/TED zahteva poseban API/bulk konektor.
2. **RZS građevinske dozvole (`opendata.stat.gov.rs`):** WCF JSON servis je više puta vratio timeout na punom preuzimanju (zahteva parcijalni/filtirani upit ili CSV sa `stat.gov.rs`).
3. **3D pokrivenost za Novi Pazar (5) i Travnik (43):** OSM ima vrlo malo `building:levels` tagova u manjim gradovima → sledeći korak za 100% uporedivu 3D masu svih 5 gradova je **Copernicus GHSL Built-H/Built-V (100 m raster)** ili **Microsoft/Overture Building Footprints**.
4. **GDELT za Travnik:** vraćao je HTTP 429 rate-limit, ali je pokrivenost za Travnik uspešno nadomeštena kroz **3 hiper-lokalna RSS izvora** (30 članaka) i **74 OpenAlex naučna rada**.
5. **Prizemne mernе stanice kvaliteta vazduha za NP/TR + Ookla 610m Internet pločice + VIIRS noćno svetlo:** spremni za dopunu kao naredni senzorski modul ili direktno u fazi izrade web GIS aplikacije.
