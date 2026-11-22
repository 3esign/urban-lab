# Urban Lab „Ekonomija grada“ — Uporedna analitička studija pet gradova (Baza v3)

**Gradovi u uzorku:** Beograd · Zagreb · Sarajevo (Kanton) · Novi Pazar · Travnik  
**Izvor podataka:** `curated/urban_lab_5cities.sqlite` (v3, 35,52 MB, 26 tabela, 13 pogleda, 215 revizorskih zapisa) + 16 WGS84 GeoJSON slojeva  
**Reproducibilne skripte:** `scripts/19_run_v3_analytics.py` · `scripts/20_deep_extract_and_charts.py`  
**Prateći eksporti i grafikoni:** `curated/analysis/` (3 CSV tabele, 2 JSON sažetka, 4 vektorska SVG grafikona)  
**Datum izrade:** `2026-11-22`

---

## Rezime glavnih empirijskih nalaza

1. **Alonso–Muth–Mills Bid-Rent i dokaz policentričnosti (Beograd vs. Novi Pazar vs. Sarajevo):**
   - Kada se iz beogradskih poreskih zona za 2026. izdvoje satelitska opštinska jezgra u **Četvrtoj zoni** (Lazarevac, Mladenovac, Obrenovac, Sopot, Barajevo na ~40,9 km od CBD-a), monocentrični eksponencijalni Bid-Rent model objašnjava **$R^2 = 0,9139$** varijanse cena stanova (**`-4,54%/km`**, poludistanca cene $D_{1/2} = 14,92\ \text{km}$), **$R^2 = 0,9011$** za poslovni prostor (**`-4,99%/km`**) i **$R^2 = 0,9858$** za poljoprivredno zemljište (**`-5,73%/km`**). **Građevinsko zemljište opada gotovo 3× strmije od stanova (`-12,08%/km`, $D_{1/2} = 5,38\ \text{km}$, $R^2 = 0,8518$)** — direktan empirijski dokaz da je cena gradnje prostorno konstantna dok se lokaciona renta kapitalizuje u zemljištu.
   - **Novi Pazar** ima **3,6× strmiji Bid-Rent pad** stanova (**`-15,32%/km`**, $D_{1/2} = 4,17\ \text{km}$, $R^2 = 0,8262$) i ekstremnu kompresiju cene poljoprivrednog zemljišta (**`-26,89%/km`**, sa `18,71` na `0,26 EUR/m²` — pad od **72×** za 12 km), pri čemu koeficijent prenamene (`građevinsko / poljoprivredno`) skače sa `17,5×` u Zoni I na **`120,5×`** u Zoni VII.
   - **Otkrivena metodološka razlika u poreskoj politici:** u Novom Pazaru odnos `P_poslovno / P_stan` je administrativno zaključan na **`1,958×`** (`1,931–1,960×`) u svih 7 zona, dok u Beogradu realno odražava prostornu specijalizaciju: maksimum u **Zoni ulaznih pravaca (`1,409×`)** i **Ekstra zoni poslovanja (`1,353×`)**, a pad ispod pariteta u **Ekstra zoni stanovanja (`0,801×`, Dedinje/Senjak)** i perifernim zonama (`0,857–0,934×`).
   - **Sarajevo** bez planinske turističke inverzije **Bjelašnica/Trnovo (`2.065,6 EUR/m²` na >20 km!)** prati čist urbani pad od **`-3,29%/km`** ($R^2 = 0,6831$), slično Beogradu, ali ima najtežu priuštivost stanovanja u uzorku (**`10,49` godišnjih neto plata** za stan od 55 m²).

2. **Von Thünenovi prstenovi namene zemljišta (OSM `landuse`, 180.096 poligona):**
   - **Beograd** (`5.270 km²` mapiranog okruženja) jedini pokazuje klasični panonski Von Thünenov prelaz: urbano jezgro (0–3 km) → industrijsko-komercijalni pojas (1–6 km, `10,8%` industrije u prstenu 1–3 km) → **poljoprivredni prsten od 6–15 km (`53,0%`) i 15+ km (`63,3%`, ukupno `3.257,4 km²`)**, uz `66,1 km²` površinskih kopova (Kolubara/Kostolac) u spoljnom prstenu.
   - **Zagreb** (`3.058 km²`) je **asimetrični koridor**: Medvednica gura šumu već na 6–15 km (`48,9%`) i 15+ km (`58,7%`), dok poljoprivreda (`23,9%–29,1%`) i logističko-industrijske zone pune južnu i istočnu savsku dolinu.
   - **Sarajevo (`77,2%` šume u 15+ km), Travnik (`73,4%`) i Novi Pazar (`98,1%` šume u 6–15 km i `89,8%` u 15+ km)** pokazuju **topografsko gušenje Von Thünenovih prstenova**: planinske kotline potiskuju poljoprivredu (u Novom Pazaru samo `73,3 km²` oranica naspram `1.696,9 km²` šume) i sabijaju stanovanje i industriju u uske rečne doline.

3. **Lanac „Pšenica – Mlinovi – Pekare“ (Weberova lokaciona teorija u praksi):**
   - **Srbija (RZS Popis 2023 × APR 2.926 firmi):** savršena prostorna podela rada po Weberu: **Vojvodina + beogradski prsten** drže sirovinu (`47,4%` pšenice u ostatku Vojvodine + `9,5%` u 7 opština BG prstena), **beogradski prsten (7 opština)** drži **`30,9%` svih mlinarskih prihoda Srbije (`138,5 M EUR` — Granexport Pančevo `44,3 M`, Žitopromet Stara Pazova `30,6 M`, Ruma `23,1 M`, Inđija `14,3 M`)**, dok **17 beogradskih opština** drži **`58,0%` prihoda pekarske industrije Srbije (`382,4 M EUR` — Don Don Zemun `153,1 M`, Trgocentar Palilula `93,7 M`, AS-Braća Stanković Grocka `49,8 M`)**.
   - **Suprotnost — Novi Pazar i Sarajevo:** Novi Pazar ima svega `1.406 ha` pšenice (procenjeni lokalni deficit ~45–58%), a Kanton Sarajevo samo `162 ha` / `592 t` pšenice (<1,3% godišnje potrebe, pokrivenost uvoza izvozom `24,4%`). Nasuprot tome, novopazarski prsten (Pešter/Sjenica/Tutin/Raška) je **stočarsko-šumarska sila** (`48.342` goveda — više nego ceo Beograd sa `34.643` — i `113.259` ovaca), a SBK/Travnik je **drvno-prerađivačka zona** (`389.000 m³` drveta, najjeftinije ogrevno drvo u uzorku: `45 EUR/prm`).
   - **S-skala (mikroekonomika pekare u 5 gradova):** uprkos najvišim ukupnim troškovima (`11.840 EUR/mes`), **Zagreb** ima **najnižu tačku pokrića (`286 vekni/dan`)** zahvaljujući višoj maloprodajnoj ceni hleba (`1,45 EUR`) i sniženom PDV-u (`5%`), dok **Novi Pazar (`485 vekni/dan`)** i **Beograd (`466 vekni/dan`)** rade na najužoj jediničnoj marži (hleb `0,65–0,70 EUR`, PDV `10%`), zbog čega su izuzetno osetljivi na rast zarada (`+15%` troška rada podiže breakeven za `+32` do `+35 vekni/dan`), dok su **Sarajevo i Travnik** najosetljiviji na cenu uvoznog brašna (`+20%` brašna → `+28` do `+31 vekna/dan`, PDV `17%`).

---

## 1. Uporedni makro-mezo-mikro profil pet gradova (M → XL)

![Makro, fiskalni kapacitet i priuštivost stanovanja u 5 gradova](curated/analysis/charts/04_multi_city_macro_fiscal_affordability.svg)

*Referentni kursevi harmonizacije (2026): `1 EUR = 117,0 RSD` (SRB), `1 EUR = 1,95583 BAM` (BIH valutni odbor), `1 EUR = 1,0 EUR` (HRV).*

| Pokazatelj | Beograd | Zagreb | Sarajevo (KS) | Novi Pazar | Travnik |
|---|---:|---:|---:|---:|---:|
| **Država / Valuta** | SRB (`RSD`) | HRV (`EUR`) | BIH (`BAM`) | SRB (`RSD`) | BIH (`BAM`) |
| **Stanovništvo (godina)** | 1.681.405 (2022) | 767.131 (2021) | 421.531 (2024) | 106.720 (2022) | 50.970 (2024) |
| **Površina / Gustina** | 3.222,7 km² · 521,7/km² | 641,2 km² · 1.196,3/km² | 1.276,9 km² · 330,1/km² | 742,0 km² · 143,8/km² | 529,0 km² · 96,4/km² |
| **Budžet 2026 (M EUR)** | 1.755,44* | 3.154,00** | 1.021,86*** | 44,87 | 20,40**** |
| **Budžet / stanovniku (EUR)** | 1.044,03 | 4.111,42 | 2.424,17 | 420,46 | 400,25 |
| **Prosečna neto plata (EUR)** | 1.278,44 | 1.760,00 | 871,24 | 797,25 | 591,05 |
| **Cena stana (EUR/m²)** | 2.172,29 (Zona I) | 3.518,00 (DZS novo) | 1.994,04 (Centar RCN) | 1.089,31 (Zona I) | 823,18 (Grad RCN) |
| **Priuštivost (m² / 1 plata)** | 0,589 | 0,500 | 0,437 | 0,732 | 0,718 |
| **Godina neto plate za 55 m²** | **7,79** | **9,16** | **10,49** | **6,26** | **6,38** |
| **Registrovanih firmi** | 64.715 (APR) | 54.075 (DZS/FINA) | 23.336 (FZS KS) | 1.325 (APR) | 1.172 (FZS SBK) |
| **NUTS3 BDP/st (EUR · PPS)** | 19.300 · 31.500 (2023) | 37.500 · 52.500 (2024) | *n/a NUTS3* | 5.800 · 9.500 (Raška, 2023) | *n/a NUTS3* |
| **Firme / 1.000 stanovnika** | 38,5 | 70,5 | 55,4 | 12,4 (d.o.o./a.d.) | 23,0 |

*\* Beograd = Grad + 17 opština. \*\* Zagreb ima status županije (uključuje zdravstvo, obrazovanje i EU kohezione fondove). \*\*\* Sarajevo = budžet Kantona Sarajevo (Grad Sarajevo je dodatnih 26,15 M KM, a 4 gradske općine ~254,3 M KM). \*\*\*\* Travnik = samo općinski budžet (bez SBK kantona), sa 33,1% kapitalnih izdataka.*

### 1.1. Ekonomska specijalizacija (Location Quotient) i aglomeracioni motori

Iz tabele `sector_structure` i `v_beograd_opstine_economy` jasno se izdvaja pet različitih urbanih ekonomskih arhetipova:

- **Beograd — dvopolna metropola usluga, finansija i IKT-a sa snažnim industrijskim L-prstenom:**
  - Unutar 17 opština beleži se izuzetno snažna korelacija između udaljenosti od CBD-a i neto plate (**$r = -0,794$**), između neto plate i prihoda firmi po stanovniku (**$r = +0,842$**) i između gustine naseljenosti i neto plate (**$r = +0,714$**).
  - **Stari grad** (`LQ = 2,25` u ugostiteljstvu `I`, `LQ = 1,86` u IKT-u `J` sa 1.025 firmi) ostvaruje `263.333 EUR` prihoda po stanovniku, **Savski venac** dominira finansijama (`K`, `LQ = 2,06`) i nekretninama (`L`, `LQ = 2,03`), dok **Novi Beograd** nosi najveću apsolutnu masu privrede (`31,44 mlrd EUR` prihoda, `183.728` zaposlenih).
  - **Dnevne migracije (`commuting_and_flows`, RZS Popis 2022):** Beogradski region beleži `166.942` dnevnih migranata, pri čemu prsten 7 spoljnih opština (`companies_sr_hinterland`: **7.260 firmi, 90.174 radnika, 13,19 mlrd EUR prihoda**) funkcioniše kao integrisano funkcionalno urbano područje — npr. **Pančevo** šalje `10.866` radnika van svoje oblasti, **Stara Pazova** `6.356`, **Smederevo** `4.635`, **Inđija** `2.391`.
- **Zagreb — EU kapitalni i fiskalni lider sa najvišim BDP-om u PPS (`52.500 EUR/st`, 2024):**
  - Grad Zagreb sam generiše **`29,12 mlrd EUR` BDP-a** (`HR050`), a zajedno sa Zagrebačkom županijom (`6,03 mlrd EUR`, `HR065`) čini funkcionalno jezgro od `35,14 mlrd EUR`.
  - Iz `zagreb_commercial_leases` (`275` aktivnih/evidentiranih ugovora sa pozitivnom zakupninom): medijalni mesečni zakup gradskog poslovnog prostora iznosi **`59,54 EUR`** (`P25 = 16,97 EUR`, `P75 = 206,33 EUR`, `P90 = 680,94 EUR`, maksimum `4.714,80 EUR`) — ogroman raspon između subvencionisanih zanatsko-udružnih prostora i atraktivnih lokacija Donjeg Grada.
- **Sarajevo (KS) — potrošačko-uslužna i turistička kotlina sa industrijskim krilima na ulazima:**
  - Visok budžetski kapacitet po stanovniku (`2.424 EUR/st` na nivou KS) prati dubok spoljnotrgovinski deficit (`24,4%` pokrivenosti uvoza izvozom) i `1,57 M` turističkih noćenja (2025).
  - Unutar KS postoji jasna prostorna podela: **Stari Grad** specijalizovan za ugostiteljstvo/turizam (`I`, `LQ = 2,38`), **Ilidža** za nekretnine (`L`, `LQ = 2,27`), a ulazne prigradske općine **Ilijaš** (`C` prerađivačka `LQ = 2,86`; `A` poljoprivreda/šumarstvo `LQ = 5,80`) i **Hadžići** (`C`, `LQ = 2,34`; `A`, `LQ = 5,18`) nose realnu proizvodnju.
- **Novi Pazar — trgovačko-logističko-građevinski čvor u regionalnom BDP jazu:**
  - Raška oblast ima najniži NUTS3 BDP po glavi stanovnika u uzorku (**`5.800 EUR` nominalno / `9.500 PPS`**, tj. 3,3× niže od Beograda i 5,5× niže od Zagreba u PPS-u).
  - Uprkos tome, grad pokazuje ekstremnu preduzetničku specijalizaciju u **transportu i skladištenju (`H`, `LQ = 2,99`, 277 firmi = 20,9% svih pravnih lica)**, **obrazovanju (`P`, `LQ = 1,80`)** i **građevinarstvu (`F`, `LQ = 1,65`, 225 firmi)**, dok su lokalne cene poslovnog prostora i stanova podržane visokim prilivom doznaka i ulogom regionalnog trgovačkog centra.
- **Travnik — kantonalno-obrazovni i turistički centar povezan sa lašvanskom industrijom:**
  - Specijalizacija u okviru SBK: **ugostiteljstvo (`I`, `LQ = 1,61`)**, **obrazovanje (`P`, `LQ = 1,45`)**, **administracija (`N`, `LQ = 1,28`)** i **zdravstvo (`Q`, `LQ = 1,19`)**, dok susedni L-prsten (Vitez, Novi Travnik, Zenica na 7–19 km) nosi tešku i prerađivačku industriju (`ArcelorMittal` `3,18 km²`, `Vitezit` `1,85 km²`, `MMK Bratstvo` `0,41 km²`).

### 1.2. XL infrastrukturni koridori — kako menjaju ekonomsku geografiju uzorka

Pet ključnih koridora iz `xl_corridors_projects_strategies` direktno redefinišu udaljenost i trošak transporta u modelu:
- **TEN-T Koridor Vc (`4.500 M EUR`, 2015–2030):** skraćuje gravitacionu vezu Sarajevo ↔ ZDK ↔ Slavonija/Budimpešta i spušta cenu dopreme hrane u Sarajevo.
- **TEN-T Koridor X (`2.800 M EUR`, 2023–2030)** i **Zagrebački željeznički čvor / RH2 (`1.800 M EUR`, 2021–2030):** jačaju intermodalnu osu Beograd–Zagreb–Rijeka.
- **Autoput A2 Požega–Duga Poljana–Boljare (`1.700 M EUR`, 2024–2032):** jedini XL projekat koji strukturno izvlači **Novi Pazar i Pešter** iz saobraćajne izolacije (trenutni razlog zašto NP ima `LQ = 2,99` u drumskom transportu).
- **Brza cesta Lašva–Vitez–Travnik–Jajce (`350 M EUR`, 2023–2029):** spaja Travnik i Lašvansku dolinu direktno na Koridor Vc i pretvara Travnik–Vitez–Zenica u jedinstveno tržište rada.

---

## 2. Lanac snabdevanja „Pšenica – Mlinovi – Pekare“ (i šuma/pilane)

![Lanac Pšenica–Mlinovi–Pekare u Srbiji i S-skala pekare u 5 gradova](curated/analysis/charts/03_wheat_mills_bakeries_and_s_scale.svg)

### 2.1. Nacionalna struktura i tržišna koncentracija u Srbiji (`apr_serbia_supply_chain`, 2.926 firmi)

Analiza svih registrovanih pravnih lica u šest ključnih NACE šifara cele Srbije (`173` opštine, finansijski izveštaji APR 2024) otkriva **izrazitu razliku u tržišnoj koncentraciji duž lanca vrednosti** (mereno Herfindahl-Hirschman indeksom `HHI` i udelom 4/10 najvećih firmi `CR4`/`CR10` po prihodu):

| NACE | Karika lanca | Firme (sa FI) | Opštine | Zaposleni | Prihod (M EUR) | Neto dobit (M EUR) | Profitna marža | HHI | CR4 (%) | CR10 (%) | Tržišna struktura |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `0111` | Žitarice i uljarice | 1.486 (1.264) | 140 | 9.415 | 2.153,56 | 89,51 | 4,16% | **100,5** | 13,0% | 23,8% | Visoko konkurentna / atomizirana |
| `1061` | **Mlinovi (mlevenje žita)** | **165 (152)** | **84** | **2.326** | **447,74** | **17,04** | **3,81%** | **473,3** | **33,0%** | **60,1%** | Umereno koncentrisano usko grlo |
| `1071` | **Pekare (hleb i pecivo)** | **667 (584)** | **127** | **12.006** | **659,28** | **30,21** | **4,58%** | **860,2** | **48,3%** | **62,1%** | Dualno: 3 giganta + 600 malih |
| `1072` | Keks i trajno pecivo | 81 (68) | 42 | 3.799 | 476,30 | 38,83 | **8,15%** | **2.349,8** | **86,0%** | **96,2%** | Oligopol (Bambi, Štark, Jaffa) |
| `1610` | Pilane i rezanje drveta | 489 (435) | 116 | 3.387 | 253,34 | 5,57 | 2,20% | **187,4** | 20,4% | 32,3% | Disperzovana regionalna mreža |
| `0220` | Seča drveća (d.o.o.) | 38 (30) | 28 | 42 | 3,58 | 0,10 | 2,79% | 1.611,9 | 74,1% | 95,7% | Mala baza (šume mahom javna JP) |

**Ključni ekonomski zaključak (koncentracija i marža):**
- Kako se roba kreće niz lanac vrednosti od sirovine ka trajnom brendiranom proizvodu, koncentracija skače **23×** (`HHI = 100,5` u ratarstvu → `473,3` u mlinovima → `860,2` u pekarama → **`2.349,8`** u keks/konditorskoj industriji), a neto profitna marža se udvostručuje (`3,81%` u mlinovima → **`8,15%`** u trajnom pecivu).
- **Vodeći igrači po karikama (provereno iz APR):**
  - **Mlinovi (`1061`, CR4 = 33,0%):** *Granexport* Pančevo (`44,30 M EUR`, 77 radnika), *DPS Klas Group* Šabac (`38,51 M EUR`), *Danubius* Novi Sad (`34,46 M EUR`), *Žitopromet-Mlinpek* Stara Pazova (`30,64 M EUR`), *Žitopromet-Mlin* Senta (`29,69 M EUR`).
  - **Pekare (`1071`, CR4 = 48,3%):** *Don Don* Zemun (`153,12 M EUR`, 1.906 radnika — sam drži `23,2%` prihoda svih pravnih lica u pekarstvu Srbije!), *Trgocentar* Palilula BG (`93,71 M EUR`, dobit `12,83 M EUR`), *AS-Braća Stanković* Grocka (`49,83 M EUR`), *Pekara Pons* Čačak (`21,96 M EUR`), *Moka* Čačak (`21,28 M EUR`).
  - **Trajno pecivo (`1072`, CR3 = 82,6%):** *Bambi* Požarevac (`147,97 M EUR`, dobit `31,40 M EUR` = marža `21,2%`!), *Atlantic Štark* Voždovac (`139,35 M EUR`), *Jaffa* Crvenka/Kula (`105,93 M EUR`).
  - **Pilane (`1610`):** *Crown Forest* Ivanjica (`17,31 M EUR`), *Milutinovići* Ivanjica (`16,64 M EUR`), *Bio Energy Point* Stari grad BG (`10,77 M EUR`), *Labor SRB* Sremska Mitrovica (`6,89 M EUR`).

### 2.2. Teritorijalni bilans: Beograd vs. Beogradski prsten vs. Novi Pazar vs. Peštersko-raški prsten

Spajanjem **RZS Popisa poljoprivrede 2023** (`170` opština) i **APR lanca snabdevanja** (`curated/analysis/srb_wheat_mills_bakeries_territorial_balance.csv`) dobijamo jasan prostorni bilans Srbije:

| Teritorijalna celina | Pšenica i spelta (ha) | Proc. prinos* (kt @ 5 t/ha) | Kukuruz (ha) | Goveda | Ovce | Mlinovi `1061` (br · M EUR) | Pekare `1071` (br · M EUR) | Pilane `1610` (br · M EUR) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Beograd (17 opština)** | 31.851,7 | 159,3 | 34.579,0 | 34.643 | 76.143 | 27 · **33,34** | **273 · 382,39** | 74 · 28,3 |
| **Beogradski prsten (7 opština)** | **64.177,3** | **320,9** | 74.006,2 | 43.312 | 108.290 | **13 · 138,47** | 33 · 15,01 | 24 · 11,6 |
| **Novi Pazar (Grad)** | **1.406,4** | **7,0** | 717,7 | 6.772 | 20.089 | 1 · **2,95** | 6 · **3,73** | 4 · 5,5 |
| **Novopazarski prsten (Sjenica/Tutin/Raška)** | 6.190,8 | 31,0 | 852,2 | **41.570** | **93.170** | 2 · **4,92** | 2 · 0,00 | **12 · 1,5** |
| **Ostatak Vojvodine** | 315.676,5 | 1.578,4 | 413.035,0 | 205.401 | 290.239 | 62 · 178,13 | 137 · 75,74 | 60 · 31,6 |
| **Ostatak Centralne/Južne Srbije** | 256.057,1 | 1.280,3 | 323.580,0 | 395.799 | 1.118.636 | 60 · 89,93 | 216 · 182,41 | 315 · 174,9 |

*\* Procenjeni prinos (`Zaključeno`): uzet nacionalni benchmark `5,0 t/ha` za poređenje potencijala; u planinskim opštinama (Novi Pazar, Sjenica, Tutin) stvarni prinosi su niži (~3,5–4,0 t/ha). Regionalna starost mehanizacije (RZS 2023): udeo traktora starijih od 20 godina iznosi `62,9%` u Vojvodini, `75,0%` u Šumadiji i Zapadnoj Srbiji, `79,3%` u Beogradskom regionu i `80,9%` u Južnoj i Istočnoj Srbiji.*

**Četiri ključna prostorna otkrića ovog bilansa:**
1. **Weberova trijada Beograda:** Na samo 15–40 km od centra Beograda leži moćna žitnica (`Ruma 15.523 ha`, `Pančevo 13.226 ha`, `Pećinci 8.583 ha`, `Surčin 8.360 ha`, `Stara Pazova 8.056 ha`, `Inđija 7.583 ha`, `Smederevo 6.696 ha`, `Obrenovac 6.388 ha`). Mlinovi su pozicionirani **na prstenu** gde je zemlja jeftinija a prilaz žitu i Dunavu/auto-putu direktan (`Pančevo 58,5 M EUR`, `Stara Pazova 30,6 M EUR`, `Ruma 23,1 M EUR`, `Surčin 18,4 M EUR`, `Inđija 14,3 M EUR`), dok su **pekare unutar grada** (`Zemun 163,7 M EUR`, `Palilula 108,8 M EUR`, `Grocka 49,8 M EUR`) radi svakodnevne jutarnje distribucije. Uz pretpostavljenu potrošnju od ~`113 kg` zrna pšenice/st/god (`85 kg` brašna pri 75% randmana), Beograd + 7 opština prstena (~`2,25 M` stanovnika, potreba ~`254 kt`) proizvode `~480 kt` pšenice — **~189% samodovoljnosti**!
2. **Strukturna asimetrija Novog Pazara (deficit žita, suficit stočarstva i drveta):** Sam Grad Novi Pazar (`106.720` st, godišnja potreba ~`12,1 kt` pšenice) sa `1.406,4 ha` proizvodi oko `5,5–7,0 kt` (pokrivenost svega **45–58%**). Lokalna prerada žita svedena je na jedan mlin u NP (`Žitoprodukt NIM`, `2,95 M EUR`) i jedan veći mlin u Raškoj (`Finagro`, `4,92 M EUR`). Zato je **pekarstvo Novog Pazara strukturno uvozno zavisno od vojvođanskog/šumadijskog brašna**, dok je prava resursna osnova regiona **Peštersko stočarstvo** (`Sjenica 26.602 goveda + 53.033 ovce`; `Tutin 13.514 goveda + 29.409 ovaca`) i **drvoprerada** (`Bronja` NP `5,23 M EUR`, 9 pilana u Tutinu).
3. **Paralela u BiH i Hrvatskoj (`hinterland_agri_forestry_trade`):**
   - **Kanton Sarajevo** (`421.531` st) proizvodi samo **`592 t` pšenice (`162 ha`)** — manje od **1,3%** godišnjih potreba (~`48 kt`), što direktno objašnjava zašto je veleprodajna cena brašna T-500 u Sarajevu i Travniku **`0,55 EUR/kg`** — gotovo **90% skuplja nego u Beogradu (`0,29 EUR/kg`)**!
   - **Srednjobosanski kanton (Travnik/Vitez)** ima `4.395 t` pšenice (`1.346 ha`), ali ima masivnu šumsku proizvodnju (**`389.000 m³` drvne mase / `115.000 m³` ogrevnog drveta**), što ga čini jedinim gradom u uzorku gde energent za pekare na drva (`45 EUR/prm`) delimično kompenzuje skupo brašno.
   - **Zagreb** u svom neposrednom M+L okruženju ima **`19.456` registrovanih poljoprivrednih gazdinstava** (`6.047` u Gradu + `13.409` u Zagrebačkoj županiji) i brzu železničko-drumsku vezu sa Slavonijom (`0,40 EUR/kg` brašna T-500).

### 2.3. S-skala: Ekonomika pojedinačne pekare u pet gradova i analiza osetljivosti

Model standardizovane gradske pekare (`v_s_bakery_5cities_comparison`, ista tehnološka proizvodna jedinica kalibrisana na lokalne ulazne cene, kirije, bruto minimalac, energente i PDV):

| Grad | Brašno T-500 (€/kg) | Drvo (€/prm) | Struja (€/kWh) | Kirija (€/m²) | PDV hleb (%) | Ukupni trošak (€/mes) | Udeo brašna (%) | Udeo rada (%) | Udeo kirije (%) | Cena hleba 500g (€) | **Tačka pokrića (vekni/dan)** | +20% brašno (Δ vekni) | +15% rad (Δ vekni) | +20% kirija (Δ vekni) | OSM pekara u regiji |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Zagreb** | 0,40 | 75,0 | 0,222 | 22,0 | **5%** | **11.840** | 22,3% | **49,6%** | 11,1% | **1,45** | **286** | +12,8 | +21,3 | +6,4 | 426 |
| **Sarajevo** | **0,55** | 56,0 | 0,138 | 16,0 | **17%** | 10.706 | 33,9% | 40,9% | 9,0% | 1,02 | **410** | **+27,8** | +25,1 | +7,4 | 134 |
| **Travnik** | **0,55** | **45,0** | 0,138 | **9,0** | **17%** | 10.130 | **35,8%** | 43,2% | **5,3%** | 0,92 | **430** | **+30,8** | +27,9 | +4,6 | 26 |
| **Beograd** | **0,29** | 78,0 | 0,156 | 18,0 | 10% | 8.887 | **21,5%** | 46,3% | **12,2%** | 0,70 | **466** | +20,1 | **+32,3** | **+11,3** | 575 |
| **Novi Pazar** | 0,33 | 52,0 | 0,156 | 14,0 | 10% | **8.590** | 25,4% | 47,9% | 9,8% | **0,65** | **485** | +24,6 | **+34,8** | +9,5 | 9* |

*\* Napomena o OSM pokrivenosti: mali broj OSM pekara u Novom Pazaru (9) odražava slabije volontersko mapiranje u OpenStreetMap-u, ne stvarni broj pekara na terenu (uporediti sa APR i gustoćom maloprodaje).*

**Ključna mikroekonomska poruka (Paradoks breakeven-a):**
- **Najjeftiniji grad po ulaznim troškovima (Novi Pazar, `8.590 EUR/mes`) zahteva najveći dnevni obim prodaje (`485 vekni/dan`) da bi opstao**, dok **najskuplji grad (Zagreb, `11.840 EUR/mes`) opstaje sa samo `286 vekni/dan`**!
- Uzrok su **tri poluge**: (1) **fiskalna politika PDV-a na osnovnu hranu** (`5%` u Hrvatskoj vs. `10%` u Srbiji vs. jedinstvenih `17%` u BiH — BiH pekari gube `12` procentnih poena neto prihoda u odnosu na Zagreb pri svakoj vekni); (2) **regulacija/kupovna moć cene osnovnog hleba** (`0,65–0,70 EUR` u SRB vs. `1,45 EUR` u ZG); i (3) **šok-osetljivost**: u BiH (Sarajevo, Travnik) najveći rizik je **cenovni šok uvoznog brašna** (`+20%` traži `+28` do `+31` vekni/dan), dok je u Srbiji (Beograd, Novi Pazar) najveći rizik **rast troška rada** (`+15%` traži `+32` do `+35` vekni/dan), što objašnjava brzu konsolidaciju u industrijske pekare (Don Don) i pritisak na male zanatske radnje.

---

## 3. Prostorna anatomija: Von Thünenovi `landuse` prstenovi pet gradova

![Von Thünenovi prstenovi namene zemljišta u 5 gradova](curated/analysis/charts/02_landuse_von_thunen_rings_5cities.svg)

Iz streaming ekstrakcije Geofabrik OSM slojeva (`180.096` poligona, `curated/analysis/landuse_rings_5cities_shares.csv`) dobijamo precizan profil namene zemljišta po prstenovima udaljenosti od CBD-a za svaki grad:

| Grad (ukupno mapirano) | Prsten | Površina (km²) | Stanovanje | Komercijala | Industrija | Poljoprivreda | Šuma | Kopovi / Ostalo+Zelenilo |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **Beograd** (`5.270,2 km²`) | 0–1 km | 1,62 | 58,2% | **21,4%** | 0,0% | 0,0% | 0,6% | 19,8% |
| | 1–3 km | 17,71 | 37,4% | 6,3% | **10,8%** | 0,4% | 17,0% | 28,2% |
| | 3–6 km | 50,88 | 33,4% | 5,5% | **8,9%** | 7,8% | 25,0% | 19,4% |
| | 6–15 km | 382,16 | 14,4% | 1,1% | 2,7% | **53,0%** | 20,4% | 8,3% |
| | 15+ km | 4.817,85 | 10,0% | 0,1% | 0,8% | **63,3%** | 20,6% | 1,4% kopovi · 3,8% |
| **Zagreb** (`3.058,1 km²`) | 0–1 km | 2,06 | 53,3% | **22,4%** | 0,0% | 0,0% | 7,9% | 16,4% |
| | 1–3 km | 18,44 | 56,0% | 8,4% | 1,5% | 1,1% | 17,0% | 15,9% |
| | 3–6 km | 66,97 | 41,6% | 5,6% | **4,8%** | 4,8% | 21,5% | 21,8% |
| | 6–15 km | 534,79 | 14,0% | 1,5% | 1,6% | 23,9% | **48,9%** | 10,0% |
| | 15+ km | 2.435,85 | 6,2% | 0,2% | 0,5% | 29,1% | **58,7%** | 5,4% |
| **Sarajevo** (`3.931,9 km²`) | 0–1 km | 1,94 | 71,6% | 2,6% | 0,0% | 0,3% | 9,3% | 16,2% |
| | 1–3 km | 25,41 | 58,0% | 0,7% | 0,5% | 4,6% | **27,5%** | 8,7% |
| | 3–6 km | 69,23 | 26,0% | 0,5% | **2,1%** | 21,0% | **47,2%** | 3,2% |
| | 6–15 km | 586,62 | 7,6% | 0,2% | 0,7% | 18,6% | **68,4%** | 4,6% |
| | 15+ km | 3.248,67 | 0,7% | 0,0% | 0,1% | 19,8% | **77,2%** | 2,2% |
| **Travnik** (`3.105,1 km²`) | 0–1 km | 4,72 | 87,1% | 0,0% | 0,0% | 0,0% | 11,1% | 1,8% |
| | 1–3 km | 27,41 | 0,4% | 0,0% | 1,0% | **51,9%** | 37,8% | 8,9% |
| | 3–6 km | 76,76 | 8,5% | 0,1% | 0,2% | 39,8% | **50,8%** | 0,6% |
| | 6–15 km | 646,19 | 2,3% | 0,2% | 0,4% | 34,6% | **61,3%** | 1,0% |
| | 15+ km | 2.350,04 | 1,1% | 0,0% | 0,2% | 24,8% | **73,4%** | 0,5% |
| **Novi Pazar** (`1.875,0 km²`) | 0–1 km | 2,58 | **90,0%** | 0,1% | 1,0% | 2,4% | 0,7% | 5,7% |
| | 1–3 km | 10,38 | 59,8% | 0,5% | **6,8%** | 12,0% | 16,4% | 4,5% |
| | 3–6 km | 17,56 | 16,2% | 0,0% | 1,2% | 6,0% | **75,4%** | 1,1% |
| | 6–15 km | 307,12 | 0,4% | 0,0% | 0,0% | 0,2% | **98,1%** | 1,2% |
| | 15+ km | 1.537,40 | 1,4% | 0,0% | 0,1% | 4,6% | **89,8%** | 4,1% |

### 3.1. Četiri prostorno-ekonomska zaključka iz prstenova i POI centralnosti

1. **Tri topografska režima Von Thünena:**
   - **Ravničarski (Beograd):** klasičan radijalni redosled bez oštrih fizičkih barijera — komercijalni CBD (`21,4%` u 0–1 km) → unutrašnji industrijsko-lučki pojas (`10,8%` u 1–3 km, `8,9%` u 3–6 km) → ogromni poljoprivredni prsten (`53,0%` u 6–15 km, `63,3%` u 15+ km) i ekstraktivni/energetski pojas (`66,1 km²` površinskih kopova, Železara Smederevo `2,75 km²`, Rafinerija Pančevo `1,49 km²`).
   - **Asimetrični predplaninski (Zagreb):** gotovo identičan komercijalni CBD kao Beograd (`22,4%` u 0–1 km), ali **dvostruko brži rast šumskog udela** (`48,9%` već na 6–15 km zbog Medvednice) i pomeren industrijski prsten dalje od centra (`4,8%` u 3–6 km, te zone u 6–15 km i Jalševac na 29,5 km).
   - **Kotlinski (Sarajevo, Travnik, Novi Pazar):** reljef „reže“ urbani prostor na 3–6 km. U Sarajevu šuma prelazi `47,2%` već na 3–6 km, u Travniku `50,8%`, a u Novom Pazaru **`75,4%` na 3–6 km i `98,1%` na 6–15 km**! Posledica za tržište nekretnina: **kotlinska topografija deluje kao prirodni regulator ponude zemljišta**, što u Sarajevu i Novom Pazaru stvara povišenu gustinu gradnje u dolini i gura cene u centru naviše u odnosu na lokalne plate.
2. **Prostorna raspodela ekonomskih POI-jeva (`v_osm_5cities_centrality`, 77.330 tačaka):**
   - **Beograd** (`33.388` POI) i **Zagreb** (`32.191` POI) imaju gotovo identičnu gustinu urbanog jezgra u 0–1 km (`3.055` vs. `2.804` POI, `221` vs. `138` kafića, `46` vs. `36` banaka), ali u prstenu **3–6 km Zagreb dostiže svoj apsolutni maksimum (`9.609` POI, `409` kafića)** naspram Beogradovih `8.205` — potpis gušćeg, kompaktnijeg srednjeg prstena Zagreba (`1.196 st/km²` vs. `522 st/km²`).
   - **Sarajevo** (`8.876` POI) ima **linearno razvučenu centralnost** duž tramvajske ose Miljacke: `1–3 km` (`2.054` POI) i `6–15 km` (`2.030` POI — Novi Grad / Ilidža!) gotovo su jednaki po broju tačaka, potvrđujući jak sekundarni pol na Ilidži (`73` supermarketa i `11` pijaca u prstenu 6–15 km!).
   - **Travnik (`1.844` POI)** ima izrazito snažan spoljni prsten (`15+ km: 941` POI i `6–15 km: 462` POI — tj. Vitez, Novi Travnik i Zenica) koji je brojniji od samog gradskog jezgra (`233` POI), dokazujući da Travnik ekonomski funkcioniše kao deo policentričnog lašvansko-zeničkog koridora.

---

## 4. Alonso–Muth–Mills Bid-Rent gradijenti: Beograd (14 zona) vs. Novi Pazar (7 zona) vs. Sarajevo i Travnik

![Bid-Rent gradijenti i odnos poslovnog i stambenog prostora](curated/analysis/charts/01_bid_rent_gradients_bg_np_sa.svg)

### 4.1. Metodološka napomena (rešena GIS „donut-centroid“ zamka)

Kod koncentričnih prstenastih poreskih zona koje okružuju centar grada (posebno **Novi Pazar zone I–IV**), geometrijski centroid prstena pada tik uz sam CBD (`0,08–0,37 km`), čime se veštački sabija osa udaljenosti. U skripti `20_deep_extract_and_charts.py` ta zamka je otklonjena: za prstenaste poligone koji obuhvataju CBD izračunat je **efektivni srednji radijus prstena** (`0,75 × srednja udaljenost temena od CBD-a`), dok je za višenaseobinske zone (BG V–VIII, NP V–VII) zadržana površinski ponderisana udaljenost centroida RZS naselja. Puni podaci za svih 21 zonu nalaze se u `curated/analysis/bid_rent_tax_zones_bg_np_2026.csv`.

### 4.2. Kompletna matrica poreskih zona 2026 — Beograd (14 zona) i Novi Pazar (7 zona)

| Grad | Poreska zona 2026 | Efekt. udalj. (km) | Površina (km²) | Stan (€/m²) | Poslovni (€/m²) | Odnos `Posl/Stan` | Građ. zem. (€/m²) | Polj. zem. (€/m²) | Skok `Građ/Polj` | Udeo zemlj. u stanu |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **BG** | Ekstra zona poslovanja | 1,50 | 4,08 | 2.270,61 | **3.071,19** | **1,353×** | 685,18 | — | — | 30,2% |
| **BG** | Ekstra zona stanovanja | 3,96 | 5,06 | **2.346,45** | 1.879,01 | **0,801×** | **688,55** | — | — | 29,3% |
| **BG** | Prva zona | 2,62 | 50,82 | 2.172,29 | 2.290,41 | 1,054× | 685,18 | — | — | **31,5%** |
| **BG** | Druga zona | 8,62 | 289,08 | 1.609,69 | 1.734,47 | 1,078× | 288,81 | 4,56 | **63,3×** | 17,9% |
| **BG** | Treća zona | 6,96 | 148,70 | 1.174,90 | 1.181,40 | 1,006× | 98,31 | 4,56 | 21,6× | 8,4% |
| **BG** | **Četvrta zona (sateliti!)** | **40,89** | 8,60 | **985,52** | 979,16 | 0,994× | 42,69 | 4,56 | 9,4× | 4,3% |
| **BG** | Peta zona | 13,97 | 429,76 | 885,27 | 824,13 | 0,931× | 29,27 | 2,97 | 9,9× | 3,3% |
| **BG** | Šesta zona | 22,92 | 444,49 | 675,04 | 671,91 | 0,995× | 17,21 | 1,76 | 9,8× | 2,5% |
| **BG** | Sedma zona | 30,07 | 735,08 | 588,27 | 504,31 | 0,857× | 11,71 | 1,03 | 11,4× | 2,0% |
| **BG** | Osma zona | 38,78 | 1.229,74 | 412,46 | 385,24 | 0,934× | 8,33 | 0,79 | 10,5× | 2,0% |
| **BG** | *Zona zaštite zelenila 1* | 5,70 | 28,18 | 1.377,88 | 1.526,88 | 1,108× | 175,26 | 4,00 | 43,8× | 12,7% |
| **BG** | *Zona zaštite zelenila 2* | 21,74 | 20,17 | 640,26 | 596,39 | 0,931× | 16,63 | 1,63 | 10,2× | 2,6% |
| **BG** | ***Zona ulaznih pravaca*** | 14,40 | 58,67 | 986,45 | **1.389,62** | **1,409×** | 66,27 | 4,56 | 14,5× | 6,7% |
| **BG** | *Zona specifičnih namena* | 40,17 | 141,36 | 640,26 | 520,49 | 0,813× | 12,42 | 1,19 | 10,4× | 1,9% |
| **NP** | **I zona** | 0,44 | 0,89 | **1.089,31** | **2.132,67** | **1,958×** | **326,79** | **18,71** | 17,5× | **30,0%** |
| **NP** | **II zona** | 1,01 | 4,85 | 788,90 | 1.523,33 | 1,931× | 315,93 | 10,69 | 29,6× | **40,0%** |
| **NP** | **III zona** | 1,61 | 12,69 | 622,48 | 1.218,66 | 1,958× | 186,72 | 5,98 | 31,2× | 30,0% |
| **NP** | **IV zona** | 2,31 | 26,31 | 414,96 | 812,46 | 1,958× | 124,49 | 3,63 | 34,3× | 30,0% |
| **NP** | **V zona** | 2,18 | 34,19 | 276,64 | 542,26 | 1,960× | 82,99 | 2,10 | 39,5× | 30,0% |
| **NP** | **VI zona** | 7,94 | 141,31 | 181,55 | 355,45 | 1,958× | 70,93 | 0,60 | **118,2×** | 39,1% |
| **NP** | **VII zona** | 12,76 | 566,04 | 104,39 | 204,37 | 1,958× | 31,32 | 0,26 | **120,5×** | 30,0% |

### 4.3. Eksponencijalni Bid-Rent nagibi ($\ln P(d) = \alpha - \beta \cdot d$)

| Grad / Uzorak | Tip nekretnine | $n$ | Centralni presek $P_0$ (€/m²) | Nagib $\beta$ (po km) | Pad cene po km (%) | Poludistanca $D_{1/2}$ (km) | $R^2$ |
|---|---|---:|---:|---:|---:|---:|---:|
| **Beograd** (monocentrično, bez Z.IV satelita) | **Stan** | 9 | 2.216,8 | 0,0464 | **-4,54%/km** | **14,92 km** | **0,9139** |
| **Beograd** (monocentrično, bez Z.IV satelita) | Kuća | 9 | 1.831,0 | 0,0517 | -5,04%/km | 13,41 km | 0,8624 |
| **Beograd** (monocentrično, bez Z.IV satelita) | **Poslovni prostor** | 9 | 2.352,0 | 0,0512 | **-4,99%/km** | **13,53 km** | **0,9011** |
| **Beograd** (monocentrično, bez Z.IV satelita) | **Građevinsko zemlj.** | 9 | 583,2 | **0,1288** | **-12,08%/km** | **5,38 km** | **0,8518** |
| **Beograd** (monocentrično, bez Z.IV satelita) | Poljoprivredno zemlj. | 6 | 7,0 | 0,0590 | -5,73%/km | 11,75 km | **0,9858** |
| *Beograd (svih 14 zona uklj. Z.IV i spec.)* | *Stan* | *14* | *1.833,3* | *0,0314* | *-3,09%/km* | *22,05 km* | *0,6790* |
| **Novi Pazar** (sve zone I–VII) | **Stan** | 7 | 745,3 | **0,1663** | **-15,32%/km** | **4,17 km** | **0,8262** |
| **Novi Pazar** (sve zone I–VII) | Kuća | 7 | 653,3 | 0,1566 | -14,50%/km | 4,43 km | 0,7974 |
| **Novi Pazar** (sve zone I–VII) | **Poslovni prostor** | 7 | 1.454,7 | **0,1660** | **-15,30%/km** | **4,18 km** | **0,8272** |
| **Novi Pazar** (sve zone I–VII) | **Građevinsko zemlj.** | 7 | 240,7 | 0,1651 | -15,21%/km | 4,20 km | 0,7878 |
| **Novi Pazar** (sve zone I–VII) | **Poljoprivredno zemlj.** | 7 | 10,0 | **0,3132** | **-26,89%/km** | **2,21 km** | **0,8719** |
| **Sarajevo** (6 urbanih općina, bez Trnova) | **Stan (FGU RCN 2024)** | 6 | 2.211,4 | 0,0335 | **-3,29%/km** | **20,72 km** | **0,6831** |
| *Sarajevo (svih 7 općina uklj. Bjelašnicu)* | *Stan/apartman* | *7* | *1.800,3* | *0,0009* | *-0,09%/km* | *792 km* | *0,0015* |

### 4.4. Pet teorijsko-empirijskih uvida iz Bid-Rent poređenja

1. **Zakon konstrukcionog poda (Beograd):** u Beogradu građevinsko zemljište gubi pola vrednosti za samo **`5,38 km`** (`-12,08%/km`), dok stanovi gube pola vrednosti za **`14,92 km`** (`-4,54%/km`). Zbog toga udeo cene zemljišta u ceni stana pada sa **`31,5%`** u Prvoj zoni na svega **`2,0%`** u Sedmoj i Osmoj zoni. U Novom Pazaru, naprotiv, poreska osnovica građevinskog zemljišta je normativno fiksirana na **`30,0%` vrednosti stana** u većini zona (I, III, IV, V, VII), osim u II zoni (`40,0%`) i VI zoni (`39,1%`) — što pokazuje da je novopazarski cenovnik **delimično parametarski (formula-driven)**, dok beogradski ima dovoljno tržišnih ugovora po zonama da odvoji dinamiku zemljišta od cene gradnje!
2. **Policentrična anomalija Beograda (Četvrta zona na 40,9 km):** uvođenje Četvrte zone obara $R^2$ monocentričnog modela sa `0,914` na `0,695`, jer urbani centri prigradskih opština (Lazarevac, Mladenovac, Obrenovac) drže `985,5 EUR/m²` na 41 km od Terazija — skuplje nego Peta zona (`885,3 EUR/m²`) na 14 km! To je merljiv dokaz **Fujita–Ogawa policentričnih sub-centara**.
3. **Komercijalna premija i logistički koridori:** u Beogradu najvišu komercijalnu premiju nema ni Stari grad, već **Zona ulaznih pravaca (`1,409×`, poslovno `1.389,6` vs. stan `986,5 EUR/m²`)** — trgovački parkovi, logistički centri i auto-saloni duž auto-puta i magistrala — a odmah iza nje **Ekstra zona poslovanja (`1,353×`, `3.071,2 EUR/m²`)**. Suprotno tome, u **Ekstra zoni stanovanja** (Dedinje/Senjak) stanovanje pobeđuje poslovni prostor (`0,801×`). U Novom Pazaru je `1,958×` odnos jasan odraz **trgovačke čaršijske rente u Zoni I** (`2.132,7` vs. `1.089,3 EUR/m²`), koju je opštinska uprava potom proporcionalno preslikala na zone II–VII.
4. **Konverzijski skok (`građevinsko / poljoprivredno`) kao barometar pritiska urbanizacije:** u Beogradu na ivici urbanog tkiva (Druga zona, 8,6 km) prenamena poljoprivrednog u građevinsko zemljište uvećava poresku vrednost **`63,3×`** (`4,56 → 288,81 EUR/m²`), a u Trećoj zoni **`21,6×`**, dok se od Pete do Osme zone stabilizuje oko **`10–11×`**. U Novom Pazaru skok raste od `17,5×` u centru (gde je čak i poljoprivredno zemljište skupo `18,71 EUR/m²` zbog špekulativne nade u urbanizaciju!) do **`120,5×`** u Zoni VII (`0,26 → 31,32 EUR/m²`).
5. **Planinska turistička inverzija (Sarajevo & Travnik):** i u Sarajevu i u Travniku klasični Bid-Rent pad se lomi na planinskim skijalištima — **apartmani na Bjelašnici/Trnovu (`2.065,6 EUR/m²`) skuplji su od stanova u Starom Gradu (`2.055,4 EUR/m²`) i Centru (`1.994,0 EUR/m²`)**, čime potpuno poništavaju monocentričnu regresiju ($R^2$ pada sa `0,683` na `0,0015`!). Isti obrazac važi u Travniku: **apartmani na Vlašiću (`920,3 EUR/m²`) su `+11,8%` skuplji od stanova u samom gradu (`823,2 EUR/m²`)**. Unutar Sarajeva dodatno se vidi „mikro-premija novogradnje“: kompleks **Nova Otoka (`1.922,5 EUR/m²`)** na 4–5 km od centra prodaje se skoro po ceni Centra, dok **Tibra Stup (`1.334,5 EUR/m²`)** na ~9 km beleži oštar diskont zbog gustine i saobraćajnog zagušenja.

---

## 5. Podela nalaza: Provereno / Zaključeno / Granice i kvalitet v3 baze

### Provereno (direktno izmereno u SQLite v3 i GeoJSON fajlovima)
- Svi agregati u tabelama odeljaka 1–4 izvučeni su reproduktivnim skriptama `19_run_v3_analytics.py` i `20_deep_extract_and_charts.py` bez ručnog unosa: `2.926` APR firmi nacionalnog lanca snabdevanja Srbije, `7.882` firmi prstena BG/NP, `66.040` firmi BG/NP, `203` zapisa RZS Popisa poljoprivrede 2023, `180.096` OSM `landuse` poligona, `77.330` OSM POI tačaka, `21` digitalizovana poreska zona BG/NP (`295` poligona), `11` sarajevskih i `2` travnička RCN tržišna segmenta, `275` gradskih zakupa Zagreba, `12` NUTS3 BDP jedinica i `11` XL koridora/strategija.
- Verifikovana su sva 4 vektorska grafikona u `curated/analysis/charts/` i 3 izvezene CSV tabele + 2 JSON fajla u `curated/analysis/`.

### Zaključeno (ekonometrijski i računski izvedeno)
- Sve eksponencijalne Bid-Rent regresije ($\beta$, $D_{1/2}$, $R^2$), Pearsonove korelacije za 17 opština Beograda, `HHI`/`CR4`/`CR10` indeksi koncentracije, efektivni srednji radijusi za koncentrične prstenaste zone Novog Pazara I–IV, testovi osetljivosti S-skale pekare (`+20%` brašno / `+15%` rad / `+20%` kirija) i bilans samodovoljnosti pšenice pod eksplicitnom pretpostavkom `5,0 t/ha` prinosa i `113 kg` pšenice/st/god.

### Granice podataka i uočene tehničke anomalije u v3 bazi (QA nalaz)
1. **Neuporedivost osnove cena nekretnina između zemalja:** Beograd i Novi Pazar koriste zvanične **poreske osnovice za 2026** (koje su u centralnim zonama niže od tržišne novogradnje), Sarajevo i Travnik koriste **FGU RCN notarske ugovore sekundarnog tržišta (2024)**, a Zagreb **DZS prosek komercijalne novogradnje (H1 2026)**. Uporedivost *unutar* grada (nagibi $\beta$, odnosi zona) je visoka; apsolutne nivoe *između* gradova treba uvek čitati uz ovu napomenu.
2. **Neuporedivost obuhvata firmi (d.o.o. vs. preduzetnici PR):** APR otvoreni podaci u v3 obuhvataju privredna društva sa finansijskim izveštajima (d.o.o., a.d.), ali **ne obuhvataju paušalne i knjigaške preduzetnike (PR)** — zbog čega je stvaran broj malih zanatskih pekara (posebno u Novom Pazaru) znatno veći od 6 registrovanih d.o.o. pekara.
3. **Nejednakost OSM volonterske pokrivenosti:** dok Beograd (`49.140` poligona) i Zagreb (`112.844` poligona) imaju izuzetno detaljan OSM `landuse` i POI sloj, Novi Pazar (`2.577` poligona, `9` mapiranih pekara) i Travnik (`4.556` poligona) imaju znatno grublje mapiranje mikro-objekata i komercijalnih zona (`0,0–0,1%` u 0–1 km jer su lokali u prizemljima označeni unutar opšteg `residential` poligona).
4. **Aproksimativne granice centralnih poreskih zona:** periferne zone (BG V–VIII, NP V–VII) koriste tačne RZS poligone naselja, dok su centralne i specijalne zone (BG Ekstra/I–IV, NP I–IV) aproksimativni poligoni rekonstruisani iz uličnih opisa Službenih listova (ne katastarski sloj po parceli).
5. **Uočeni tehnički bug u SQLite v3 pogledu (za sledeću reviziju baze):** pogled `v_osm_centrality_rings` u bazi v3 baca grešku `no such column: ring_km` (nasleđen iz v1 pre prelaska na kolonu `ring` u v2; funkcionalna zamena je već prisutan pogled `v_osm_5cities_centrality`). Takođe, `rzs_agri_census_2023` nema redove za čisto urbane šifre bez poljoprivrednog zemljišta (npr. `70203` Palilula BG i `71308` Beograd-grad), pa spajanja sa APR-om moraju koristiti `FULL`/`LEFT` agregaciju iz `apr_serbia_supply_chain`, što je ovde urađeno u `20_deep_extract_and_charts.py`.

---

## 6. Indeks generisanih analitičkih artefakata u sesiji

- **Studija:** `urban_lab_db/docs/03_ANALITICKA_STUDIJA_5_GRADOVA_V3.md`
- **Vektorski grafikoni (SVG):**
  - `urban_lab_db/curated/analysis/charts/01_bid_rent_gradients_bg_np_sa.svg`
  - `urban_lab_db/curated/analysis/charts/02_landuse_von_thunen_rings_5cities.svg`
  - `urban_lab_db/curated/analysis/charts/03_wheat_mills_bakeries_and_s_scale.svg`
  - `urban_lab_db/curated/analysis/charts/04_multi_city_macro_fiscal_affordability.svg`
- **Izvezene analitičke tabele (spremne za Web GIS / QGIS / Excel):**
  - `urban_lab_db/curated/analysis/bid_rent_tax_zones_bg_np_2026.csv`
  - `urban_lab_db/curated/analysis/landuse_rings_5cities_shares.csv`
  - `urban_lab_db/curated/analysis/srb_wheat_mills_bakeries_territorial_balance.csv`
  - `urban_lab_db/curated/analysis/v3_refined_study_summary.json`
  - `urban_lab_db/curated/analysis/v3_analytical_metrics.json`
