# Urban Lab „Ekonomija grada“

Uporedna prostorno-ekonomska baza i GIS za pet gradova: **Beograd, Zagreb, Sarajevo, Novi Pazar i Travnik**.
Cilj je laboratorija u kojoj se isti podaci gledaju kroz različite ekonomske modele i skale, od parcele do makro-regiona.

**Interfejs uživo: https://3esign.github.io/urban-lab/**

*Comparative spatial-economics database and web GIS for five cities in Serbia, Croatia and Bosnia and Herzegovina. Documentation is in Serbian.*

## Stanje

| Deo | Stanje |
|---|---|
| Baza v4.2 (SQLite) | 86 tabela, 28 pogleda; gradi se skriptama iz javnih izvora |
| API server | radi; samo čita bazu, bez npm zavisnosti |
| Web interfejs (mapa 2D/3D) | statički sajt u `docs/`, objavljen preko GitHub Pages; radi bez servera i bez baze |
| Ponovljivost gradnje od nule | **nije proverena** — skripte su nastajale talas po talas |

## Šta je u repozitorijumu

| Putanja | Sadržaj |
|---|---|
| `docs/` | GitHub Pages sajt: `index.html`, `app.js`, `styles.css` i `data/` (statički izvoz baze, oko 39 MB) |
| `urban_lab_app/` | `server.mjs` (Node 24, ugrađeni `node:sqlite`), `tools/export_static.mjs`, `tests/` |
| `urban_lab_db/scripts/` | 84 Python skripte: sakupljanje, obrada, gradnja baze, analiza; redosled u `INDEX.md` |
| `urban_lab_db/schema_v4/` | šema v4, migracija v4.2, JSON ugovor NLP→GIS |
| `urban_lab_db/manifest.jsonl` | poreklo svakog preuzimanja: URL, SHA-256, status, relativna putanja |
| `urban_lab_db/curated/boundaries/` | 16 GeoJSON slojeva (granice, zone, landuse, koridori) |
| `urban_lab_db/curated/tables/`, `analysis/` | CSV izvozi, metrike i grafikoni |
| `urban_lab_db/docs/` | dokumenti po redosledu nastanka; `00_INVENTAR.md` je generisan popis |

## Šta nije u repozitorijumu

- `urban_lab_db/raw/` — sirovi preuzeti fajlovi (437 fajlova, 488 MB).
- `urban_lab_db/curated/*.sqlite` — baze v3 (37 MB) i v4.2 (135 MB, iznad GitHub granice od 100 MB po fajlu).

Oba su u `.gitignore`. Bez baze v4.2 ne rade server i izvoz; sajt u `docs/` radi i bez nje, jer čita već izvezene fajlove. `manifest.jsonl` čuva URL i SHA-256 svakog sirovog fajla, ali alat koji bi ih ponovo preuzeo i proverio još nije napisan.

## Pokretanje

Potrebni su Node 24+ i Python 3.12+, i baza na putanji `urban_lab_db/curated/urban_lab_5cities_v4.sqlite`.

```
npm start          # server na http://127.0.0.1:8787
npm test           # provera svih API ruta za pet gradova
npm run export     # baza → statički fajlovi u docs/data/ (posle svake promene baze)
npm run test:site  # provera sajta u headless Chrome-u; prima i URL, npr. adresu na Pages
python urban_lab_db/scripts/36_build_inventory.py   # osvežava inventar
```

Promenljive okruženja: `URBAN_LAB_DB` (putanja baze za server), `PORT`, `HOST`, `URBAN_LAB_DB_DIR` (koren podataka za skripte), `URBAN_LAB_SCRATCH` (privremeni arhivi; podrazumevano `.scratch/`).

## Interfejs (GitHub Pages)

Pages ne pokreće server, pa sajt ne zove API: `export_static.mjs` podiže `server.mjs`, snima svaki sloj kao GeoJSON, dosije za 418 zona i indeks pretrage u `docs/data/`. Lokalni server služi isti `docs/` folder, pa je lokalni prikaz isti kao objavljeni.

- **Gradovi i skale:** pet gradova; XS–XL uključuje odgovarajuće slojeve i zum.
- **Slojevi:** opštine/četvrti, mjesni odbori i naselja, poreske zone, mreža 1 km, Ookla, pekare i pijace, 3D zgrade, rent-gap parcele, javni prevoz, izbori, nabavke, zaleđe, dnevne migracije, namena zemljišta, koridori.
- **Sočivo:** boji zone po izabranom pokazatelju, na skali zajedničkoj za svih pet gradova.
- **Nivo poverenja (A1–D):** filtrira objekte na mapi i redove u dosijeu.
- **Dosije zone:** pregled, prostor, politika, dokazi.
- **Donja tabla:** uporedna tabela, šta-ako model pekare, studije događaja, izvori i granice.

Granice statičkog izdanja: filter poverenja u dosijeu uklanja redove iz lista, ali zbirni brojevi ostaju nad svim nivoima; za Novi Pazar je izvezeno 8.000 najviših od 17.200 zgrada; 3D zgrade su kvadri nad okvirom zgrade. Podloga mape su OpenStreetMap pločice, a MapLibre GL se učitava sa unpkg.com.

## Skale

Podaci su organizovani po skalama: **XS** (parcela, zgrada), **S** (ulica, kvart, lokalni lanci snabdevanja), **M** (grad i opštine), **L** (zaleđe i dnevne migracije), **XL** (koridori, makro-region). Opis je u `urban_lab_db/docs/01_ARHITEKTURA_BAZA_I_INTERFEJSA_SMLXL.md`.

## Poznate rupe

- 87 od 442 reda manifesta su neuspela preuzimanja.
- 96 sirovih fajlova nema red u manifestu (spisak u `00_INVENTAR.md`).
- Novi Pazar nema javne nabavke u bazi; izbori su gusti samo za Beograd i Novi Pazar.
- Pogled `v_osm_centrality_rings` u arhivskoj bazi v3 je neispravan.

## Izvori i prava

Podaci potiču iz javnih izvora: OpenStreetMap preko Geofabrika, geoBoundaries, zvanične statistike i registri (RZS, APR, FZS, DZS, data.gov.rs, data.zagreb.hr), Eurostat, Svetska banka, OpenAlex, CORDIS, TED, Ookla. Svaki izvor ima svoju licencu; uslovi daljeg deljenja **nisu provereni izvor po izvor**. Katalog izvora je u `urban_lab_db/docs/02_…`, `04_…` i `05_…`.

Licenca koda još nije izabrana.
