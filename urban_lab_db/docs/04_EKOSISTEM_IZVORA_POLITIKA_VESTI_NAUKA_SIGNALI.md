# Urban Lab „Ekonomija grada“ — Prošireni ekosistem izvora: Politika, Vesti, Nauka i Alternativni signali

**Sesija:** `c1795299369016b6gi`  
**Datum istraživanja:** `2026-11-22`  
**Opseg:** Beograd, Zagreb, Sarajevo, Novi Pazar, Travnik (+ njihova šira okruženja L i makro-koridori XL)  
**Cilj dokumenta:** Proširenje Urban Laba iz statične baze zvanične statistike (v1–v3: demografija, APR, budžeti, poreske zone, OSM `landuse`) u **višeslojni opservatorijum i istraživačku laboratoriju** koja povezuje prostor, kapital, politiku, javni diskurs, naučno znanje i fizičko-digitalne senzore.

---

## 1. Epistemološki okvir: zašto zvanična statistika nije dovoljna

Baza v3 daje **skelet ekonomije grada** (godišnje preseke iz RZS/DZS/FZS, APR, budžeta i OSM-a). Međutim, analitička studija v3 pokazala je **tri strukturne slepe tačke** koje sama statistika ne može da objasni:

1. **Vremenski rascep (retrovizor vs. vetrobran):** zvanični popisi, RCN izveštaji i RGFI bilansi kasne 6–24 meseca. Grad se menja dnevno kroz tendere, dozvole, šokove cena, štrajkove, zatvaranja fabrika i vesti.
2. **Politička ekonomija rente:** u v3 smo empirijski izmerili da prenamena poljoprivrednog u građevinsko zemljište diže vrednost **17,5× do 120,5×** (Novi Pazar) i da se cene poslovnog prostora i stanova u BG i NP formiraju po potpuno različitim pravilima. To ne stvara „čisto tržište“, nego **političke i planske odluke** (GUP/PDR, skupštine, koncesije, javne nabavke, subvencije).
3. **Nevidljiva ekonomija Balkana (dijaspora, siva ekonomija, energetsko siromaštvo):** u Novom Pazaru i Travniku cena kvadrata i građevinski talas ne mogu da se objasne samo prijavljenim platama i APR bilansima. Za to su potrebni **nezavisni senzori** (noćno svetlo iz svemira, potrošnja struje, kvalitet vazduha, doznake dijaspore, oglasi, blokade računa).

Zato Urban Lab treba da spaja **četiri vremensko-epistemička sloja**:

| Sloj | Ritam osvežavanja | Uloga u ekonomiji grada | Primeri izvora |
|---|---|---|---|
| **1. Struktura (postojeća v3 baza)** | Godišnje / višegodišnje | Dugoročna anatomija grada i okruženja | Popisi, APR/FZS firme, budžeti, poreske zone, OSM `landuse` |
| **2. Politika, pravo i javni kapital** | Mesečno / po odluci | Ko menja pravila igre i gde teče javni novac | Javne nabavke, GUP/PDR, CEOP/ISPU dozvole, subvencije, EU/WBIF fondovi, izbori po biračkim mestima, vlasničke mreže |
| **3. Vesti, događaji i senzori (puls)** | Dnevno / nedeljno / 15-min | Šokovi, očekivanja, konflikti, stvarni promet i fizički metabolizam | GDELT, ACLED, Media Cloud, lokalni mediji, fiskalizacija HR, OpenAQ/SEPA, VIIRS, ENTSO-E, Ookla, GTFS, oglasi, blokade |
| **4. Nauka i znanje (teorije + R&D)** | Kontinuirano | (A) Šta nauka već zna *o* gradu; (B) gde grad stvara znanje *u* prostoru | OpenAlex, CORDIS, NaRDuS/eNauka, CroRIS/CROSBI/Dabar, UNSA, EPO patenti, EIZ/FREN/WB/OECD |

---

## 2. Osa I — POLITIKA, MOĆ I INSTITUCIJE (*ko odlučuje o prostoru i novcu*)

### 2.1. Javne nabavke i tokovi javnog kapitala
Umesto samo zbirnog budžeta, pojedinačni ugovori pokazuju **koja ulica/opština dobija kapitalne radove**, koje firme dobijaju poslove, gde postoji koncentracija dobavljača i gde se javlja samo 1 ponuđač (indikator rizika konkurencije).
- **BiH (Sarajevo, Travnik) — najjači otvoreni API u regionu:** Portal javnih nabavki `ejn.gov.ba` ima zvaničan **REST / OData Open API** sa Swagger dokumentacijom (`open.ejn.gov.ba/docs/index.html`) i webhook-ovima (`next.ejn.gov.ba/en/open-data`).
- **Srbija (Beograd, Novi Pazar):** `jnportal.ujn.gov.rs` sinhronizuje otvorene arhive (CSV/ZIP) na nacionalni portal `data.gov.rs` (uData REST API). Dopunski: `budzeti.data.gov.rs` (Otvoreni budžeti lokalnih samouprava).
- **Hrvatska (Zagreb):** `eojn.hr` (EOJN RH) + registar ugovora + EU **TED (Tenders Electronic Daily)** i `data.europa.eu` za nabavke iznad EU pragova.

### 2.2. Prostorno planiranje, građevinske dozvole i stvaranje urbane rente
Promena namene zemljišta je najjači pojedinačni politički generator bogatstva u gradu.
- **Hrvatska (Zagreb):** **ISPU** (`mpgi.gov.hr` / `portal-ispu-api.gov.hr`) objedinjuje *ePlanove* (namena svake katastarske čestice), *eDozvolu*, *eGrađevinski dnevnik* i *eNekretnine*.
- **Srbija (Beograd, Novi Pazar):** **CEOP** (Centralna evidencija objedinjene procedure pri APR-u) za građevinske i upotrebne dozvole + Službeni listovi gradova (GUP, PDR, izmene zona, takse, koncesije).
- **BiH (Sarajevo, Travnik):** **Zavod za planiranje razvoja Kantona Sarajevo** (regulacioni planovi, urbanistički projekti, GIS preglednik dozvola KS) + `ippfbih.gov.ba` + opštinski glasnici Travnika.

### 2.3. Subvencije, državna pomoć i međunarodni investicioni fondovi
- **Srbija:** Komisija za kontrolu državne pomoći (`kkdp.gov.rs` — *E-registar državne pomoći* i *De minimis* registar) + **ISDACON** (Ministarstvo za evropske integracije — razvojna pomoć).
- **Hrvatska (Zagreb):** **Kohesio** (`kohesio.ec.europa.eu`) — milioni projekata EU kohezione politike sa tačnim korisnicima, iznosima i lokacijama (RDF/Wikibase otvoreni podaci).
- **Srbija & BiH (BG, SA, NP, TR):** **WBIF (Western Balkans Investment Framework — `wbif.eu`)** — grantovi i krediti za saobraćaj (Koridor Vc, obilaznice), energetiku, vode, fakultetske kampuse i komunalnu infrastrukturu, sa ESIA studijama uticaja.

### 2.4. Izborna geografija na nivou biračkog mesta (Politička ekonomija u GIS-u)
Ukrštanjem glasova po biračkim mestima sa cenom kvadrata, platom, gustinom i kapitalnim ulaganjima testiraju se **Public Choice**, **Tiebout sortiranje** i **političko-budžetski ciklusi** (da li opštine/kvartovi drugačije glasaju u zavisnosti od ekonomske strukture, i da li investicije prate političku mapu).
- **Srbija:** RIK (`rik.parlament.gov.rs`, CSV/XLSX po biračkim mestima) + civilni otvoreni repozitorijum `rezultatiizbora.rs` (JSON/CSV).
- **Hrvatska:** DIP (`izbori.hr` — ZIP/CSV arhive po svakom biračkom mestu, uključujući preferencijalne glasove).
- **BiH:** CIK (`izbori.ba` — potvrđeni rezultati po biračkim mestima).

### 2.5. Skupštine, javne konsultacije i mreže moći/vlasništva
- **Parlamenti i javne rasprave:** **Otvoreni parlament** (Srbija), **Parlametar** (HR/BiH), **e-Savjetovanja** (`savjetovanja.gov.hr` — komentari građana i firmi na zakone i strategije), **eKonsultacije** (`ekonsultacije.gov.ba`).
- **Mreže povezanosti i sukobi interesa:** **GONG Mozaik veza** (Hrvatska — graf politički izloženih osoba i kompanija), **CIN BiH baze podataka** (`cin.ba` — imovina političara, poticaji, budžetske rezerve, javne nabavke), **KRIK / CINS** baze (Srbija), **OCCRP Aleph API** (milioni dokumenata, registara, sudskih spisa i istraživačkih baza širom regiona).

---

## 3. Osa II — VESTI, JAVNI DISKURZ I DOGAĐAJI (*puls, šokovi i narativi*)

Vesti su **vodeći (leading) i visokofrekventni senzor** ekonomije grada: hvataju najave investicija, zatvaranja fabrika, skokove kirija, štrajkove, poplave, prostorne konflikte i promene očekivanja mesecima pre nego što se pojave u statistici.

### 3.1. Globalni mašinski tokovi vesti i događaja (API)
- **GDELT Project 2.0 (DOC 2.0 + GEO 2.0 API + BigQuery GKG):** prati svetske i regionalne vesti na 100+ jezika svakih 15 minuta; izvlači tačne koordinate, entitete (firme/institucije), teme (`ECON_HOUSING`, `PROTEST`, `INFRASTRUCTURE`, `INFLATION`) i ton/sentiment. Besplatan pristup.
- **ACLED API (Armed Conflict Location & Event Data):** precizno geokodirani protesti, štrajkovi, blokade puteva i građanski sukobi. Za Urban Lab to je **sloj društvenog trenja** (protesti oko GUP-a, zagađenja, radničkih prava, cena grejanja/prevoza).
- **Media Cloud API (MIT/Harvard):** analiza *uokviravanja* (framing) — kako različiti mediji u istom gradu opisuju isti ekonomski projekat (npr. „razvojni megaprojekat“ vs. „gentrifikacija / uzurpacija javnog prostora“).

### 3.2. Regionalna ekonomska štampa (signali investicija i tržišnih šokova)
- **Srbija / BiH / Hrvatska (zajednički ekonomski puls):** *eKapija* (najbogatiji izvor najava investicija, tendera i gradilišta pre realizacije), *Bloomberg Adria*, *Poslovni dnevnik / Lider* (HR), *Akta.ba / BiznisInfo / Indikator.ba* (BiH).
- **Hiper-lokalni mediji (presudni za Novi Pazar i Travnik):** globalni agregatori gotovo ne pokrivaju manje gradove; lokalna ekonomija se vidi kroz lokalne RSS/portale (*Radio Sto Plus, Free Media, RTV Novi Pazar, SANA* za NP; *Travnik-grad.info, Drukčiji radio, Fena/Klix lokalno* za Travnik).

### 3.3. Istraživačko novinarstvo kao sloj „skrivene ekonomije“
- **KRIK, CINS, BIRN (Detektor), CIN BiH, Oštro:** jedini javni izvori koji dokumentuju **neformalne tokove kapitala, nelegalnu gradnju, naduvane cene infrastrukturnih ugovora, kartelsko ponašanje i zarobljavanje urbanističkih planova**.

---

## 4. Osa III — NAUKA, INOVACIJE I ZNANJE (*dva različita sloja u Urban Labu*)

Nauka u platformi ima **dve razdvojene, komplementarne uloge**:

### 4.1. Uloga A: Nauka *O* gradu (epistemička baza znanja i modela)
Svaki grad i svaki ekonomski fenomen na mapi može biti direktno vezan za recenzirane studije, disertacije i lokalna terenska merenja:
- **OpenAlex API (`api.openalex.org`):** potpuno otvoren, besplatan REST API sa 250M+ naučnih radova, konceptima (*Urban economics*, *Real estate*, *Agglomeration*, *Transport*), citatima i linkovima ka otvorenim PDF-ovima.
- **Nacionalni repozitorijumi doktorskih disertacija i radova (neprocenjivi jer sadrže duboke mikro-studije na srpskom/hrvatskom/bosanskom kojih nema u međunarodnim bazama):**
  - **Srbija:** **NaRDuS** (Nacionalni repozitorijum doktorskih disertacija) + **eNauka** (nacionalni CRIS portal istraživača, ustanova i projekata).
  - **Hrvatska:** **CroRIS** + **CROSBI** (Hrvatska znanstvena bibliografija) + **Dabar** (digitalni akademski repozitoriji, podrška za OAI-PMH).
  - **BiH:** Repozitoriji Univerziteta u Sarajevu (**UNSA**), radovi sa **DUNP/IUNP** (Novi Pazar) i **Univerziteta u Travniku**.
- **Think-tankovi i razvojne institucije:** World Bank Open Knowledge Repository, EBRD Transition Reports, OECD Regions & Cities, Ekonomski institut Zagreb (EIZ), FREN i CEVES (Beograd), CPI / Ekonomski institut Sarajevo.

### 4.2. Uloga B: Nauka *U* gradu (R&D klasteri, ljudski kapital i inovacije kao prostorni faktor)
Gde se u gradu stvara novo znanje, tehnologija i visokoplaćeni poslovi?
- **OpenAlex Institutions & kolaboracione mreže:** merenje istraživačkog autputa, citiranosti, tematske specijalizacije i globalne umreženosti univerziteta u svih 5 gradova (UBG, UNIZG, UNSA, DUNP/IUNP, Univerzitet u Travniku).
- **CORDIS (Horizon Europe / EU Open Data):** tačni iznosi evropskih naučnih grantova po instituciji, gradu i temi — direktan indikator integracije u evropsku ekonomiju znanja.
- **EPO OPS API (European Patent Office):** patenti po adresi podnosioca/pronalazača (SRB, HRV, BiH) → prostorna mapa tehnoloških inovacija.
- **Tehnološki parkovi i kampusi** (NTP Beograd, ZICER Zagreb, sarajevski IT hubovi, univerzitetski kampusi) kao lokalni gravitacioni centri kirija i startap koncentracije.

---

## 5. Osa IV — „PITAMO SE“: ALTERNATIVNI, FIZIČKI I NEVIDLJIVI SENZORI EKONOMIJE GRADA

Pored politike, vesti i nauke, moderna urbana ekonomija sve više koristi **nezavisne, neadministrativne izvore** koji hvataju realnost tamo gde država kasni ili ne meri:

### 5.1. Svemirski i fizički senzori (*podaci koje niko ne može administrativno da „ulepša“*)
- **VIIRS Nighttime Lights (EOG / NASA):** noćno zračenje na ~500m rezoluciji. Globalno dokazan proxy za lokalni BDP i **detektor sive ekonomije** (kada noćna svetlost i gradnja rastu brže od prijavljenog APR/FZS prometa — ključno za Novi Pazar i Travnik!).
- **Copernicus Urban Atlas & GHSL (Global Human Settlement Layer):** satelitski slojevi namene zemljišta za evropske FUA regione i **višedecenijska dinamika širenja izgrađenih površina i zapremine zgrada (1975–2030)** — popunjava praznine gde nema 3D katastra (Sarajevo, Travnik, Novi Pazar).
- **Kvalitet vazduha kao ekonomsko-socijalni senzor (OpenAQ v3 API + SEPA SRB + EkoAkcija/FHMZ BiH + Sentinel-5P NO₂):**
  - Zimski ekstremi $\text{PM}_{2.5}/\text{PM}_{10}$ u Sarajevu, Novom Pazaru i Travniku nisu samo ekologija — oni su **mapa energetskog siromaštva** (loženje uglja/drva vs. gas/daljinsko grejanje) i direktnog zdravstvenog/produktivnog gubitka grada.
  - $\text{NO}_2$ iz satelita (Sentinel-5P) meri intenzitet saobraćaja i industrije.
- **ENTSO-E Transparency Platform API:** satna potrošnja i opterećenje elektroenergetske mreže — „ekonomski EKG“ (dnevni, sezonski i krizni ciklusi proizvodnje).
- **Klimatski i geološki rizici (Landsat/ECOSTRESS toplotna ostrva, JRC poplavne karte):** fizički rizici koji se sve snažnije ugrađuju u cenu kvadrata, osiguranje i trošak infrastrukture.

### 5.2. Real-time potrošnja, mobilnost i digitalna infrastruktura
- **Fiskalizacija uživo (Porezna uprava RH):** agregirani podaci o broju i iznosu fiskalizovanih računa po delatnostima i županijama — najbliže **real-time potrošnji** u regionu (benchmark model za Zagreb).
- **Turizam i pritisak kratkoročnog najma:** **eVisitor** (Hrvatska — mesečni dolasci i noćenja po destinaciji) + signali platformi kratkoročnog zakupa (Airbnb/Booking) → merenje turistifikacije i istiskivanja stanara (Baščaršija, Donji Grad, Stari grad BG, Bjelašnica, Vlašić).
- **GTFS javni prevoz (Beograd `data.gov.rs`, Zagreb ZET static+realtime, Sarajevo Javni prevoz KS):** omogućava računanje **izohrona dostupnosti (30/45 min)** — koliko radnih mesta i usluga stanovnik svakog kvarta realno može da dosegne (efektivna veličina tržišta rada po Prud'homme & Lee).
- **Ookla Open Data (Speedtest 610m tiles, Parquet/Shapefile):** stvarne brzine fiksne i mobilne mreže po kvartovima za svih 5 gradova — direktna mapa **digitalnog jaza** i spremnosti za ekonomiju znanja.

### 5.3. Tržišni signali uživo, finansijski stres i ulični nivo (XS–S skala)
- **Oglasi za posao** (*Infostud, MojPosao, MojPosao.ba*): tražena zanimanja, veštine i oglašene plate *danas* (pokazuje kuda se gradska privreda transformiše za 1–3 godine).
- **Oglasi za nekretnine i kirije** (*Halo Oglasi / 4zida, Njuškalo, OLX.ba*): *asking* cene i kirije u odnosu na poreske osnovice iz v3 baze → otkriva jaz između fiskalne procene i stvarnog pritiska tržišta.
- **Kardiovaskularni stres-test privrede (blokade računa i stečajevi):**
  - Srbija: **NBS Registar dužnika u prinudnoj naplati** + **ALSU** portal stečajeva.
  - Hrvatska: **FINA** blokade/ovrhe + **e-Oglasna ploča sudova** (izvoz CSV/Excel).
  - BiH: **CBBiH Jedinstveni registar računa** (JRR).
- **Ulični kompjuterski vid & ekonomska arheologija:** *Mapillary / KartaView* (automatska detekcija praznih izloga, gradilišta, stanja fasada) + **Wayback Machine** + istorijski ortofoto (*Geosrbija, DGU Geoportal, Katastar.ba*) za praćenje promene lokala i parcela kroz 20 godina.

### 5.4. „Nevidljivi“ društveni i transnacionalni motori
- **Dijaspora i doznake:** podaci platnog bilansa centralnih banaka (**NBS, HNB, CBBiH**) + frekvencija avionskih i međunarodnih autobuskih linija (DACH, Turska, Skandinavija). Ključni nedostajući faktor za razumevanje tržišta nekretnina, potrošnje i malih investicija u Novom Pazaru, Travniku i Sarajevu.
- **Društveni kapital i „Consumer City“ (Glaeser):** prostorna gustina obrazovnih, kulturnih, sportskih i verskih ustanova, udruženja građana, biblioteka, pozorišta i javnih događaja — objašnjava zašto pojedini kvartovi drže visoku rentu i kvalitet života mimo same blizine posla.

---

## 6. Matrica pokrivenosti novih izvora za svih 5 gradova

| Kategorija izvora | Beograd | Zagreb | Sarajevo | Novi Pazar | Travnik | Otvorenost / API |
|---|---|---|---|---|---|---|
| **Javne nabavke** | `data.gov.rs` (CSV/ZIP) | `eojn.hr` + EU TED | **`open.ejn.gov.ba` REST API** | `data.gov.rs` (CSV/ZIP) | **`open.ejn.gov.ba` REST API** | Visoka (BiH najbolji API) |
| **Prostorni planovi / Dozvole** | CEOP + Sl. list BG | **ISPU / ePlanovi / eDozvola** | ZPR KS GIS + `ippfbih` | CEOP + Sl. list NP | Opštinski planovi / glasnik | Asimetrična (HR najbolji GIS) |
| **Subvencije / EU / WBIF** | `kkdp.gov.rs` + WBIF + ISDACON | **Kohesio (EU)** + RH registar | WBIF + DEI + CIN poticaji | `kkdp.gov.rs` + WBIF | WBIF + FBiH/SBK | Visoka za EU/WBIF; srednja lokalno |
| **Izbori (biračka mesta)** | RIK CSV + `rezultatiizbora.rs` | DIP ZIP/CSV | CIK `izbori.ba` | RIK CSV + `rezultatiizbora.rs` | CIK `izbori.ba` | Visoka (CSV/JSON/web) |
| **Vesti i konflikti (globalno)** | GDELT + ACLED + Media Cloud | GDELT + ACLED + Media Cloud | GDELT + ACLED + Media Cloud | GDELT + ACLED (tanje!) | GDELT + ACLED (tanje!) | Besplatni API-ji |
| **Vesti (lokalno + istrage)** | eKapija, KRIK, CINS, BIRN | Poslovni, Gong, Oštro | Akta, CIN, BIRN/Detektor | Sto Plus, Free Media, RTV NP | Travnik-grad, Drukčiji, CIN | RSS / javne baze |
| **Nauka (globalno + lokalno)** | OpenAlex + CORDIS + NaRDuS/eNauka | OpenAlex + CORDIS + **CroRIS/Dabar** | OpenAlex + CORDIS + UNSA | OpenAlex + NaRDuS/eNauka | OpenAlex + lokalni radovi | OpenAlex/CORDIS/OAI-PMH |
| **Sateliti & Digital (svih 5 jednako!)** | **VIIRS + GHSL + Ookla + OpenAQ** | **VIIRS + Urban Atlas + GHSL + Ookla + OpenAQ** | **VIIRS + GHSL + Ookla + OpenAQ** | **VIIRS + GHSL + Ookla + OpenAQ** | **VIIRS + GHSL + Ookla + OpenAQ** | **100% uporedivo svih 5 gradova!** |
| **Real-time potrošnja / Prevoz** | GTFS (`data.gov.rs`) | **Fiskalizacija RH + eVisitor + ZET GTFS-RT** | Javni prevoz KS | Ograničeno (lokalni red vožnje) | Ograničeno | HR prednjači |
| **Finansijski stres (blokade/stečaji)** | NBS prinudna + ALSU | FINA + `e-Oglasna` | CBBiH JRR | NBS prinudna + ALSU | CBBiH JRR | Javni portali / izvoz |

---

## 7. Metodološke zamke i otvorena pitanja („pitamo se“)

Pre nego što ijedan novi izvor uđe u bazu, Urban Lab mora da reši **pet suštinskih dizajnerskih pitanja**:

1. **Rangiranje poverenja izvora (`trust_tier`):** statistički registar, satelitsko merenje, naučni rad i novinski članak nemaju istu dokaznu težinu. Predlog 3 nivoa obeležavanja svake stavke u bazi:
   - `Tier A` — zvanični registri, zakonski akti i fizički/satelitski senzori (APR, `ejn.gov.ba`, VIIRS, OpenAQ, Ookla, GTFS).
   - `Tier B` — recenzirana nauka i dokumentovane istraživačke baze sa primarnim dokazima (OpenAlex, CORDIS, CIN, KRIK, GONG).
   - `Tier C` — medijski signali, sentiment, oglasi i crowdsourcing (GDELT, lokalni RSS, oglasnici).
2. **Pravna i etička higijena (politika i istrage):** čim se uđe u politiku, tendere i vlasničke mreže, podaci se tiču konkretnih lica i firmi. Pravilo sistema: **nikakvo automatsko „optuživanje“ ili lepljenje etiketa** — beleže se samo *proverljivi strukturni indikatori* (npr. „1 ponuđač na tenderu“, „vrednost ugovora / procenjena vrednost“, „broj izmena plana“) uz obavezan primarni URL, datum i sirovi izvor.
3. **Problem „velikog vs. malog grada“ (asimetrija signala):** Beograd i Zagreb imaju hiljade vesti u GDELT-u, hiljade radova u OpenAlex-u i GTFS/fiskalizaciju; Novi Pazar i Travnik imaju malo globalnih vesti i radova. Rešenje: **dvostruka arhitektura** — (a) *Univerzalni sloj* koji jednako pokriva svih 5 gradova (VIIRS, GHSL, Ookla, OpenAQ, javne nabavke, izbori, OpenAlex) i (b) *Dubinski „šampionski“ slojevi* po gradu (Zagreb: Fiskalizacija + ISPU + Kohesio; Sarajevo/Travnik: `ejn.gov.ba` API + CIN; Beograd/NP: APR + CEOP + NBS blokade).
4. **Kako tekst (vest, zakon, disertacija) staviti na mapu (NLP → GIS)?** Svaki nestrukturisani dokument prolazi kroz **lokalni gazetteer** (nazivi opština, naselja, ulica, industrijskih zona i firmi iz naše v3 baze + OSM-a) → dobija `(city_id, admin_unit_id, lat/lon, date, topic, sentiment, entity_ids, source_url)`. Tako klikom na npr. „Ilidža“ ili „Novi Pazar Zona I“ na mapi dobijaš ne samo brojeve, nego i *aktivne tendere, izmene plana, naučne radove i vesti iz poslednjih 90 dana*.
5. **Uzročnost vs. medijska buka:** kako u Urban Labu razlikovati stvarni ekonomski šok od medijske kampanje? Kroz **event-study dizajn**: svaka krupna politička odluka ili vest (npr. usvajanje GUP-a, otvaranje deonice autoputa, uvođenje nove poreske zone, zatvaranje fabrike) postaje vremenska oznaka $t_0$ oko koje se mere promene u oglasima, tenderima, noćnom svetlu i prometu u radijusu od 1–5 km.
