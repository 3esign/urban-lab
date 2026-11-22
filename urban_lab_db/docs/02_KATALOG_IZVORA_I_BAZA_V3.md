# Urban Lab „Ekonomija grada“ — Katalog prikupljenih baza podataka (5 gradova)

**Sesija:** `c1795299369016b6gi`  
**Koren baze:** `urban_lab_db/`  
**Datum prikupljanja i verifikacije:** `2026-11-21` / `2026-11-22` (Talas 1 + Talas 2 Multi-Scale v2)  
**Ukupan obim (v2):** **212 fajlova**, **223,45 MB** (`raw/` 151 fajl / 180,05 MB · `curated/` 30 fajlova / 43,01 MB · `scripts/` 29 fajlova / 0,25 MB)  
**Glavna SQLite baza (v2):** `curated\urban_lab_5cities.sqlite` (**32,85 MB**, **21 tabela**, **10 analitičkih `VIEW`-ova**, **175** revizorskih zapisa u `sources_manifest`)  
**Prostorni slojevi (v2):** **13 WGS84 GeoJSON fajlova** (uklj. `all_5cities_admin_units.geojson`, `all_5cities_hinterland_l.geojson`, `s_scale_bakeries_markets_5cities.geojson` i `xl_strategic_corridors.geojson`) + **16 CSV tabela**  
**Multi-Scale (XS/S/M/L/XL) arhitektura baze i interfejsa:** `01_ARHITEKTURA_BAZA_I_INTERFEJSA_SMLXL.md`

---

## 1. Uporedni presek 5 gradova (iz `v_city_comparison`)

*Referentni kursevi za harmonizaciju u EUR (2026): `1 EUR = 1,95583 BAM` (fiksni valutni odbor BiH), `1 EUR = 117,0 RSD` (srednji kurs NBS), `1 EUR = 1,0 EUR`.*

| Grad | Država | Stanovništvo (god.) | Površina (km²) | Gustina (st/km²) | Budžet 2026 (M EUR) | Budžet / st (EUR) | Neto plata (EUR) | Cena stana (EUR/m²) | Priuštivost (m²/plata) | Godina plate za 55 m² | Reg. pravnih lica |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Beograd** | SRB | 1.681.405 (2022) | 3.222,68 | 521,7 | 1.755,44 | 1.044,03 | 1.278,44 | 2.172,29* | 0,589 | 7,79 | 64.715 |
| **Zagreb** | HRV | 767.131 (2021) | 641,24 | 1.196,3 | 3.154,00 | 4.111,42 | 1.760,00 | 3.518,00** | 0,500 | 9,16 | *OAuth2* |
| **Sarajevo (KS)** | BIH | 421.531 (2024) | 1.276,90 | 330,1 | 1.021,86*** | 2.424,17 | 871,24 | 1.994,04**** | 0,437 | 10,49 | 23.336 |
| **Novi Pazar** | SRB | 106.720 (2022) | 742,00 | 143,8 | 44,89 | 420,46 | 797,25 | 1.089,31* | 0,732 | 6,26 | 1.325 |
| **Travnik** | BIH | 50.970 (2024) | 529,00 | 96,4 | 20,43*** | 400,25 | 591,05 | 823,18**** | 0,718 | 6,38 | 1.172 |

*\* Beograd i Novi Pazar: zvanična poreska osnovica Zona I za 2026 (tržišna novogradnja u centru je viša). \*\* Zagreb: DZS prosečna cena novih stanova H1 2026 (3.554 EUR bez POS-a). \*\*\* Sarajevo KS: kantonalni budžet 1.998,59 M KM; Grad Sarajevo (26,15 M KM) i 4 gradske općine (~254,3 M KM) evidentirani su zasebno u `fiscal_budgets`. Travnik: samo općinski budžet (39,96 M KM, bez SBK kantona). \*\*\*\* Sarajevo (Centar) i Travnik (grad): FGU Registar cijena nekretnina FBiH 2024, sekundarno tržište.*

---

## 2. Mapa institucionalnih nadležnosti (zašto je harmonizacija obavezna)

| Grad | Institucionalna struktura | Šta obuhvata „gradski“ budžet | Metodološka zamka u multi-city poređenju |
|---|---|---|---|
| **Beograd** | Grad + 17 gradskih opština | Gradski nivo (190,22 mlrd RSD) + 17 opština (15,17 mlrd RSD) = 205,39 mlrd RSD | Opštine imaju mali fiskalni kapacitet (7,4% zbirnog budžeta); glavna nadležnost je na Gradu. |
| **Zagreb** | Grad sa statusom županije + 17 četvrti + 218 MO | Konsolidirani proračun (3,15 mlrd EUR / rebalans 3,34 mlrd EUR) uključuje i zdravstvo, obrazovanje, EU fondove | Najviši budžet po stanovniku (4.111 EUR) delom zato što Zagreb objedinjuje i županijske nadležnosti. |
| **Sarajevo** | **Kanton Sarajevo** (9 općina) + **Grad Sarajevo** (4 općine) + **općine** | Kanton = 1.998,59 M KM; Grad = 26,15 M KM; 4 gradske općine = ~254,3 M KM (Centar 87,78; Novo SA 70,20; Novi Grad 67,28; Stari Grad ~29) | Uzimanje samo „Grada Sarajeva“ (26 M KM) potpuno bi iskrivilo analizu; realna uporediva jedinica sa BG i ZG je **Kanton + Grad + općine**. |
| **Novi Pazar** | Jedinstveni Grad (99 naseljenih mesta) | 5,252 mlrd RSD (44,89 M EUR), bez pod-opština | Zdravstvo/prosveta (plate) idu iz republičkog budžeta; doprinos za građevinsko zemljište čini ~13,3% gradskih prihoda (700 M RSD). |
| **Travnik** | Općina u SBK/KSB (sjedište kantona) | Općina = 39,96 M KM (20,43 M EUR), od čega 33,1% kapitalni izdaci (13,24 M KM) | Policija, obrazovanje i zdravstvo su na nivou SBK kantona, pa je općinski budžet komunalno-infrastrukturnog karaktera. |

---

## 3. Matrica prikupljenih baza (5 gradova × slojevi)

| Sloj | Beograd | Zagreb | Sarajevo | Novi Pazar | Travnik |
|---|---|---|---|---|---|
| **Admin. granice (WGS84 GeoJSON)** | **17 opština** (RZS ArcGIS) | **17 četvrti + 218 MO** (SHP HTRS96→WGS84) | **9 općina KS** (geoBoundaries ADM3) | **Grad + 99 naselja** (RZS ArcGIS) | **Općina** (geoBoundaries ADM3) |
| **Mikro-grid / 3D zgrade** | **1 km grid 2022** (1.421 ćelija, RZS) | **ZG3D Donji Grad** (5,32 MB GeoJSON + CSV) + katalog 17 četvrti | *Rupa* (ZPR WebCity zahteva dalju provjeru WFS/REST) | **1 km grid 2022** (1.215 ćelija, RZS) | *Rupa* (`gis.opcinatravnik.com.ba` web preglednik) |
| **Demografija** | RZS Popis 2022 po opštinama i 1 km gridu | DZS Popis 2011 & 2021 po 17 četvrti i 68 naselja + Eurostat `urb_cpop1` | FZS procena 2020–2024 po 9 općina + Popis 2013 | RZS Popis 2022 (grad + 99 naselja + 1 km grid) | FZS procena 2020–2024 (50.970) + Popis 2013 |
| **Budžeti / Fiskalno** | Budžet 2026 HTML (Sl. list 6/2026, 205,39 mlrd RSD) | **7.316 CSV stavki 2026** + projekcije 2027/2028 + 2023–2025 | Budžet KS 2026 PDF (302 str., 1.998,59 M KM) + Grad + 4 općine | Budžet 2026 potpisan PDF (40 str.) + Građanski vodič | Budžet 2026 PDF (56 str.) + Rebalans 2026 + Izvršenje 2025 XLS + Dug 2026 XLSX |
| **Cene nekretnina / Poreske zone** | **14 poreskih zona 2026** × 7 tipova (`BG_082_2025_002.htm`) + opis granica | DZS H1 2026 novogradnja (3.518 EUR/m²) + DZS indeksi 2025/2026 | **FGU RCN 2024**: 7 općina + 4 kompleksa (notarski ugovori!) | **7 poreskih zona 2026** × 8 tipova (`NP_014_2025_002.htm`) + opis granica | **FGU RCN 2024**: Travnik grad (1.610 KM/m²) + Vlašić (1.800 KM/m²) |
| **Privreda / Firme / Sektori (NACE)** | **64.715 firmi + 54.343 RGFI** (APR Open Data) + LQ po 17 opština | *Rupa*: Sudski registar (`sudreg-data.gov.hr`) zahteva besplatni OAuth2 ključ | **23.336 pravnih lica** × 9 općina × 19 NACE sektora (FZS) + LQ | **1.325 firmi + 1.154 RGFI** (APR Open Data) + LQ | **1.172 pravnih lica** × 19 NACE sektora (FZS SBK) + LQ |
| **Plate i tržište rada** | RZS jul 2026 & jan 2026 po 17 opština | DZS 2026 + Eurostat `urb_clma` | FZS 2021–2024 po 9 općina (plate, zaposleni, nezaposleni) | RZS jul 2026 & jan 2026 | FZS 2021–2024 (12.993 zap., 1.156 KM neto, 7.086 nezap.) |
| **Mobilnost / POI** | **13.413 OSM ekonomskih POI-jeva** (prstenovi 0–1, 1–3, 3–6, 6+ km) | **O-D matrica putovanja** (308×308 zona, CSV) | *Rate-limit na Overpassu* (skripta spremna) | *Rate-limit na Overpassu* (skripta spremna) | *Rate-limit na Overpassu* (skripta spremna) |
| **Makro (zajedničko)** | World Bank 2018–2025 (BDP/st nominalni i PPP, inflacija, nezaposlenost, FX) za SRB, HRV, BIH | isto | isto | isto | isto |

---

## 4. Prvi verifikovani ekonomski nalazi iz izgrađene baze

1. **Beograd — dvopolni poslovni centar (APR RGFI, `v_beograd_opstine_economy`):**
   - **Novi Beograd** generiše **31,44 mlrd EUR** prihoda (12.847 firmi, 183.728 zaposlenih, 149.892 EUR/st).
   - **Stari grad** (0,61 km od CBD) ima najveću gustinu prihoda po stanovniku (**263.333 EUR/st**, 7.390 firmi, 11,78 mlrd EUR) i najvišu neto platu (**1.822,60 EUR**).
   - **Savski venac** ima **227.597 EUR/st** (5.248 firmi, 8,35 mlrd EUR).
   - Snažan dohodovni gradijent: Stari grad (1.823 EUR) → Vračar (1.679) → Savski venac (1.669) → Novi Beograd (1.611) → periferne opštine (~900–960 EUR).
2. **Novi Pazar — logističko-građevinsko-trgovački čvor (`sector_structure`, `property_zones_prices`):**
   - Ekstremna koncentracija u **H Prevoz i skladištenje (LQ = 2,986; 277 firmi = 20,9%)**, **P Obrazovanje (LQ = 1,797)** i **F Građevinarstvo (LQ = 1,653; 225 firmi)**.
   - U I poreskoj zoni poslovni prostor (**2.132,67 EUR/m²**) je skoro **2× skuplji od stana (1.089,31 EUR/m²)** — jasan potpis trgovačke rente.
   - Doprinos za uređivanje građevinskog zemljišta (700 M RSD) čini **13,3%** budžeta za 2026.
3. **Sarajevo — najizraženiji jaz između cena stanova i plata (`v_bid_rent_profiles`, `v_city_comparison`):**
   - Čist bid-rent pad (FGU RCN 2024): Stari Grad (**2.055 EUR/m²**) → Centar (**1.994**) → Novo Sarajevo (**1.958**) → Novi Grad (**1.590**) → Ilidža (**1.534**) → Vogošća (**1.432**), uz planinsku turističku anomaliju Bjelašnica/Trnovo (**2.066 EUR/m²**).
   - Najlošija priuštivost stanovanja u uzorku: **10,49 godišnjih prosečnih neto plata** za stan od 55 m² (naspram 9,16 u Zagrebu, 6,38 u Travniku i 6,26 u Novom Pazaru).
   - **Ilidža** ima izrazitu klaster specijalizaciju u **L Poslovanje nekretninama (LQ = 2,271; 688 pravnih lica)**.
4. **Zagreb — najdublja fiskalna i 3D granularnost (`zagreb_budget_lines`, `ZG3D`, `O-D`):**
   - Najveći pojedinačni izvor prihoda u 2026: porez na dohodak od nesamostalnog rada (**1.380 M EUR**), kapitala (**152 M EUR**), tekuće pomoći (**428,59 M EUR**), EU kapitalne pomoći (**127,62 M EUR**), komunalne naknade (**110 M EUR**).
   - Najveći rashodovni razdjeli: Obrazovanje/sport/mladi (**1.031,12 M EUR**), Socijalna zaštita/zdravstvo (**538,40 M EUR**), Mjesna samouprava/promet/komunalije (**410,98 M EUR**), Izgradnja/prostorno uređenje (**375,27 M EUR**).
   - Demografski „donut effect“ (2011→2021): jezgro Donji Grad (−15,7%) i Gornji Grad (−14,7%) gube stanovnike, dok Novi Zagreb–zapad (+10,0%) i Stenjevec (+4,8%) rastu.
5. **Travnik — kantonalni obrazovno-turističko-administrativni centar:**
   - Visok udeo kapitalnih izdataka (**33,1%** općinskog budžeta 2026 = 13,24 M KM).
   - Specijalizacija u odnosu na SBK: **I Ugostiteljstvo (LQ = 1,615)**, **P Obrazovanje (LQ = 1,453)**, **N Administrativne usluge (LQ = 1,276)**, **Q Zdravstvo (LQ = 1,193)**.
   - Turistička premija Vlašića: apartmani na Vlašiću (1.800 KM/m²) su skuplji od stanova u samom gradu Travniku (1.610 KM/m²).

---

## 5. Struktura fajlova u sesiji (`urban_lab_db/`)

- `curated/urban_lab_5cities.sqlite` — glavna SQLite baza (21,53 MB; 10 tabela: `cities`, `admin_units`, `fiscal_budgets`, `zagreb_budget_lines`, `property_zones_prices`, `companies_sr`, `sector_structure`, `osm_pois`, `macro_worldbank`, `sources_manifest` + 5 analitičkih pogleda)
- `curated/boundaries/` — 10 WGS84 GeoJSON fajlova:
  - `all_5cities_admin_units.geojson` (45 osnovnih jedinica svih 5 gradova)
  - `beograd_17_opstina.geojson`, `beograd_grid_1km_popis2022.geojson` (1.421 ćelija)
  - `zagreb_17_cetvrti.geojson`, `zagreb_218_mjesnih_odbora.geojson` (HTRS96/TM → WGS84)
  - `sarajevo_9_opcina_ks.geojson`, `travnik_opcina.geojson`
  - `novi_pazar_grad.geojson`, `novi_pazar_99_naselja_popis2022.geojson`, `novi_pazar_grid_1km_popis2022.geojson` (1.215 ćelija)
- `curated/tables/` — 8 CSV eksporta spremnih za QGIS / Excel / Web UI (`cities_comparison.csv`, `admin_units_all.csv`, `fiscal_budgets_2025_2026.csv`, `property_zones_prices.csv`, `sector_structure_lq.csv`, `beograd_opstine_economy.csv`, `osm_centrality_rings.csv`, `macro_worldbank.csv`)
- `raw/` — 95 neizmenjenih izvornih fajlova (PDF budžeti, FZS/RZS/DZS publikacije, HTML odluke, SHP zipovi, CSV proračun Zagreba, ZG3D Donji Grad, O-D matrica, APR JSONL, OSM Beograd, World Bank & Eurostat JSON)
- `manifest.jsonl` — kompletan revizorski trag svakog preuzimanja (URL, HTTP status, bajtovi, SHA-256, datum provere)
- `scripts/` — 15 reproducibilnih Python skripti za osvežavanje i ponovnu izgradnju baze

---

## 6. Podela: Provereno / Zaključeno / Nije gledano (rupe)

- **Provereno (preuzeto, SHA-256 overeno, parsirano i upisano u bazu):**
  - Svi fajlovi u `manifest.jsonl` sa `ok=1`, sve koordinate 10 GeoJSON slojeva (uključujući HTRS96/TM → WGS84 inverznu projekciju Zagreba), APR cenzus Beograda (64.715 firmi) i Novog Pazara (1.325 firmi), RZS Popis 2022 i 1 km gridovi, RZS zarade jul 2026, poreske zone BG (14) i NP (7), Zagreb 7.316 stavki proračuna 2026 + ZG3D Donji Grad + O-D matrica, FZS Kanton Sarajevo 2025/2026 i SBK 2025, FGU RCN FBiH 2024, zvanični PDF budžeti KS/Travnik/NP, World Bank makro serije i Eurostat Urban Audit za Zagreb.
- **Zaključeno (izvedeno računski iz proverenih tabela):**
  - Konverzije u EUR po referentnom kursu (117,0 RSD/EUR; 1,95583 BAM/EUR), Location Quotient (`LQ`) po NACE sektorima, indeks priuštivosti stanovanja (godine prosečne plate za 55 m²), udaljenosti centroida od CBD-a i gustine po km².
- **Nije gledano / Rupe za sledeći talas:**
  1. **OSM ekonomski POI-jevi za Zagreb, Sarajevo, Novi Pazar i Travnik:** javni Overpass serveri su posle velikog Beograd upita (13.413 POI / 5,08 MB) vratili timeout/rate-limit; skripta `04c_collect_osm_fast.py` je spremna za naknadni prolaz ili preuzimanje sa Geofabrik `.osm.pbf` ekstrakta.
  2. **Registar firmi za Zagreb (`sudreg-data.gov.hr`):** besplatan OAuth2 API, ali zahteva registraciju klijenta (nije urađeno jer se ne registrujemo bez Semirovog naloga).
  3. **Poligoni poreskih zona Beograda (14) i Novog Pazara (7):** imamo pun tekst odluka sa ulicama (`beograd_odluka_zone_granice.htm`, `novi_pazar_odluka_zone_granice.htm`), ali same granice zona nisu objavljene kao otvoreni GeoJSON — potrebna je digitalizacija ili provera `gis.beoland.com`.
  4. **Pojedinačne transakcije nekretnina (RGZ / FGU javni uvid):** javni portali ne nude masovni otvoreni API/CSV, pa baza trenutno koristi zvanične zonske i općinske proseke iz RGZ/FGU/DZS izveštaja.
  5. **Kantonalni budžet SBK (za Travnik) i pojedinačni PDF-ovi 4 sarajevske općine:** u bazi su usvojeni ukupni iznosi za 4 općine Sarajeva iz zvaničnih saopštenja, dok su puni PDF budžeti skinuti za Kanton Sarajevo, Novi Pazar i Travnik.


---

## Talas 3 (v3) — Dubinska baza Srbije, digitalizovane poreske zone BG/NP i OSM Landuse 5 gradova (22.11.2026)

- **Mereno stanje `urban_lab_db/` (v3):** **275 fajlova / 272,23 MB** · **SQLite `urban_lab_5cities.sqlite` = 35,52 MB** (**26 tabela** · **13 analitičkih pogleda** · **215** revizorskih zapisa u `sources_manifest`) · **16 WGS84 GeoJSON slojeva** · **22 CSV eksporta**.
- **APR Pančevo + ispravka RZS šifara hinterlanda (`companies_sr_hinterland`, 7.882 firmi):**
  - Otkrivena i otklonjena greška pomeranja opštinskih šifara iz Talasa 2 (ćirilični APR nazivi upareni 1-na-1 sa `rzs_srbija_sve_opstine.geojson`).
  - **Beogradski prsten (7.260 firmi / 90.174 radnika / 13,19 mlrd EUR):** Pančevo (`80314`: 1.895 firmi / 2.490,5 M EUR), Stara Pazova (`80420`: 1.414 / 3.125,9 M EUR), Valjevo (`70360`: 1.227 / 2.067,3 M EUR), Smederevo (`71099`: 1.020 / 1.691,8 M EUR), Inđija (`80179`: 783 / 1.612,0 M EUR), Ruma (`80357`: 646 / 900,8 M EUR), Pećinci (`80322`: 275 / 1.303,6 M EUR).
  - **Novopazarski prsten (622 firme / 4.133 radnika / 287,9 M EUR):** Raška (`71021`: 263), Tutin (`71188`: 210), Sjenica (`71072`: 149).
- **APR nacionalni lanac snabdevanja cele Srbije (`apr_serbia_supply_chain`, 2.926 firmi u 173 opštine):**
  - `0111` žitarice/uljarice (1.486 firmi / 2.153,6 M EUR), `1071` pekare (667 / 659,3 M EUR), `1610` pilane (489 / 253,3 M EUR), `1061` mlinovi (165 / 447,7 M EUR), `1072` keks/trajno pecivo (81 / 476,3 M EUR), `0220` seča drveća (38 / 3,6 M EUR).
- **RZS Popis poljoprivrede 2023 (`rzs_agri_census_2023`, 203 zapisa — 170 opština + 25 oblasti + regioni + Srbija):**
  - Preuzeto 14 zvaničnih Excel tabela (`tabela-21..61_cir.xlsx`) i RZS ArcGIS `Popis_poljoprivrede_2023_Opstine` (197 opština).
  - Spojeni pogled `v_srb_wheat_mills_bakeries_balance`: Pančevo ima 13.226 ha pšenice i 5 mlinova (58,5 M EUR), Ruma 15.523 ha, dok Novi Pazar ima samo 1.406 ha pšenice (uz 6.772 goveda i 20.089 ovaca), a Sjenica 26.602 goveda i 53.033 ovce.
- **Digitalizovane granice poreskih zona 2026 (`property_tax_zones_gis_summary` + 2 nova GeoJSON sloja):**
  - `curated/boundaries/beograd_poreske_zone_2026.geojson`: **svih 14 zona / 192 poligona** (166 zvaničnih RZS poligona naselja za V–VIII zonu + digitalizovani urbani/specijalni poligoni Ekstra poslovanja, Ekstra stanovanja, I–IV, Zelenilo 1&2, Ulazni pravci, Specifične namene iz `Sl. list grada Beograda 55/2013..96/2022`), povezano sa zvaničnim cenama 2026 (`Sl. list 82/2025`).
  - `curated/boundaries/novi_pazar_poreske_zone_2026.geojson`: **svih 7 zona / 103 poligona** (99 zvaničnih RZS poligona naselja za V–VII zonu + 4 gradske zone I–IV po uličnim opisima `Sl. list grada Novog Pazara 9/2015..9/2021`), povezano sa cenama 2026 (`Sl. list 14/2025`).
- **OSM `landuse` svih 5 gradova i okruženja (`osm_landuse_summary`, `osm_landuse_major_zones` + `all_5cities_osm_landuse.geojson`):**
  - Streaming Geofabrik ekstrakcija 1.223.354 poligona (SRB/HRV/BiH) -> **180.096** obrađenih poligona u 5 gradskih regiona (`Beograd`: 3.257,4 km² poljoprivrede / 1.085,4 km² šume / 54,9 km² industrije; `Zagreb`: 1.707,8 km² šume / 840,1 km² poljoprivrede / 24,4 km² industrije; `Sarajevo`: 2.950,4 km² šume / 767,0 km² poljoprivrede; `Travnik`: 2.170,3 km² šume / 852,4 km² poljoprivrede; `Novi Pazar`: 1.696,9 km² šume / 73,3 km² poljoprivrede).
