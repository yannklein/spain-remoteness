# How far is rural Spain from a city?

A map of every Spanish municipality coloured by how long it takes to reach the
nearest **main city by public transport**, taking the best connection of a weekday.

The question "what is a main city?" has no single answer, so the map lets you
switch between three definitions:

| Tier | Definition | Why |
|---|---|---|
| **Metros** | The 6 municipalities over 500k people: Madrid, Barcelona, València, Sevilla, Zaragoza, Málaga | "How far from a big city?" |
| **Regional hubs** (default) | The 50 provincial capitals + Ceuta, Melilla, Mérida, Santiago de Compostela + every municipality over 100k | Where hospitals, universities, courts and administration are. Teruel (36k) counts because it serves a whole province. |
| **All urban** | Regional hubs + every municipality over 50k | 50k is the core-city threshold Eurostat uses for Functional Urban Areas |

Tiers are nested, so a municipality's time can only drop as the definition widens.
Main-city municipalities themselves are shown in grey; everything else gets a colour.
Suburbs over 100k (Getafe, L'Hospitalet, Dos Hermanas...) remain destinations
but are labelled with their metro.

## How it works

```
data/es/municipalities_base.json   8,132 INE municipalities (codes, names, islands, centroids)
        │
        ▼  pipeline/build_places.py
        │    + INE table 29005 (latest padrón)      → population, >100k / >50k tiers
        │    + OpenStreetMap admin_centre nodes     → town-centre point per municipality
        ▼
data/places.json
        │
        ▼  pipeline/compute_times.py  (TravelTime /v4/time-filter)
        │    many-to-one searches per city: "arrive at city X next Tuesday at
        │    08:30 / 11:30 / 14:30 from every municipality in the same zone
        │    within 300 km", 2,000 origins per search, best time kept, capped at 3 h
        ▼
web/public/data/es/remoteness.json  → per municipality and tier: minutes + nearest city
web/public/data/es/remoteness.csv   → same, flat table for QGIS (see below)
        │
        ▼  web/ (Vite + TypeScript + MapLibre)
Docker image (nginx, static) → Coolify
```

Details worth knowing:

- **Zones.** Travel never crosses the sea: every island, Ceuta and Melilla are their own
  zone. Menorca, Formentera, La Gomera or El Hierro, for example, have no main city and
  read "3h+ / no service".
- **Origins are town centres,** not geometric centroids. Large municipalities like Lorca or
  Cáceres have centroids far out in the countryside, which would add a long walk.
  If OSM has no `admin_centre` for a municipality, the centroid is used.
- **Why several arrival times.** Rural lines may run two or three times a day. Benavente to Zamora
  has no trip arriving at 08:30 but a 97 min one arriving at 11:30, so the map keeps the best of the three.
  Edit `ARRIVAL_TIMES` in `pipeline/compute_times.py` to change this.
- **Why not the fast endpoint.** `/time-filter/fast` only has a generic "weekday morning" profile and missed
  many regional trips (La Rinconada to Sevilla, Avinyó to Barcelona). `pipeline/diagnose.py` compares both
  endpoints on known commuter trips; `--endpoint fast` is still available.
- **Known gaps.** Some local bus networks are absent from TravelTime's data (Alcantarilla to Murcia,
  Petrer to Elda come out unreachable on every endpoint).
- **Fallbacks.** If the INE download fails, the >100k list in `pipeline/cities.py` is used
  and "All urban" equals "Regional hubs".
- **Cost.** About 775 searches (~80 requests) per full run, ~7 min at the free-key pace of
  ~110 searches/min. Per-city results are cached in `.cache/times/<method>/`, so an interrupted
  run resumes where it stopped.

## Airports map

The same page has an **Airports** view (`#airports`): public transport time from each
municipality to the nearest airport, with the same method as the cities map (best of
08:30 / 11:30 / 14:30 Tuesday arrivals, 3 h cap, islands on their own).

| Category | Rule |
|---|---|
| **Intercontinental** | at least one scheduled route longer than 4,000 km (Americas, Gulf, Asia) |
| **Europe** (default) | at least one scheduled route to another European country |
| **Any airport** | any scheduled passenger flight, domestic included |

Categories are nested. Each airport has two of them: counting **year-round** routes only, or
also **seasonal** ones (summer-only, or winter-only in the Canaries). The page's
"Include seasonal routes" checkbox switches between them. Málaga, for example, is intercontinental
all year (Air Transat to Montréal); Bilbao and Palma only with seasonal routes (United to Newark).

The list lives in `pipeline/airports.py`, with the deciding route and its source in each note.
Tiers marked "verify" were set from incomplete schedule information (checked November 2026).
Airports with no scheduled flights (Teruel, Huesca, Ciudad Real, Burgos, Albacete) are listed
but excluded.

Details worth knowing:

- **Arrival points are the airport's bus/rail stop** from OpenStreetMap, not the terminal:
  TravelTime cannot attach a point inside a terminal to its walking network and returned every
  terminal as unreachable. Four stops still did not attach and were moved 300–600 m (noted per airport).
- **Foreign airports are in the list but never win.** Lisbon, Porto, Faro, Biarritz, Perpignan,
  Toulouse, Tarbes and Pau were included for border areas, but TravelTime has no cross-border buses or trains:
  no Spanish municipality reaches them (November 2026 check, `--only OPO,LIS,...`). Gibraltar works
  on foot from La Línea and San Roque.
- **Coverage gaps.** Murcia-Corvera, Lleida-Alguaire, Castellón, Salamanca, El Hierro, La Gomera and
  Melilla airports (and Tarbes and Pau across the border) are not reachable in TravelTime's data. Each
  airport's `reach` (municipalities that get there) is stored in `airports.json`; the page fades
  unreachable airports, leaves them out of the counts and names them in the tooltip of nearby places. Where an airport bus
  is missing, the time is mostly walking (Maó to Menorca airport: 86 min).
- **Timetables are a November weekday's.** Summer-only airport shuttles are not reflected, even
  with seasonal routes counted.

```bash
export TRAVELTIME_APP_ID=... TRAVELTIME_API_KEY=...
python3 pipeline/compute_airports.py --only OPO,MAD   # test a few airports, writes nothing
python3 pipeline/compute_airports.py                  # everything (~50 requests, a few minutes)
```

Output: `web/public/data/es/airports.json` and `airports.csv`. Per-airport results are cached in
`.cache/airports/`; delete an airport's file there after changing its coordinates.

## Internet map

The **Internet** view (`#internet`) answers "could I work remotely from here?" with the speeds people
actually measure: average download, upload and latency per municipality, for fixed broadband and
(with the checkbox) mobile.

- **Source:** Speedtest® by Ookla® Global Fixed and Mobile Network Performance Maps, CC BY-NC-SA 4.0.
  The internet data derived here is shared under the same licence.
  Ookla publishes ~600 m tiles per quarter, with average speeds and the number of tests and devices behind them.
- **Period:** the last 4 published quarters, pooled (currently 2025-Q4 to 2026-Q3).
- **Method:**
  - Each tile goes to the municipality containing its centre (point in polygon on the map's own
    boundaries, `pipeline/geo.py`).
  - Values are test-weighted means over all tiles and quarters.
  - A value is published only with at least **20 tests** over the 4 quarters and **5 devices within one
    quarter**; otherwise the municipality is grey ("not enough speed tests") and only the counts are given.
    Ookla counts devices per tile and quarter, so devices are summed over a municipality's tiles but not
    over quarters (one household testing every quarter is still one device). `*_devices` in the CSV is
    the busiest quarter's count.
- **Estimates for places without enough local tests:** the tests of every tile within **10 km** of the
  village's town centre are pooled, with the same evidence rule and weighting. Only tiles located in Spain
  count. No fixed-broadband estimate is made where official coverage says **fewer than 50%** of households
  can get 100 Mbps (e.g. Renieblas, 8 km from Soria: 0%), because the nearby tests then describe the next
  town. Estimates fill ~3,250 municipalities for fixed broadband and ~4,400 for mobile; they are drawn hatched (true colour,
  white diagonal lines) on the map and kept in separate `*_est_*` CSV columns. Measured values are never replaced.
- **Official coverage (every municipality):** the share of households that *can* get ≥ 100 Mbps, ≥ 1 Gbps
  and 5G, latest year (2025, situation at 30 June). Source: Ministerio para la Transformación Digital y de
  la Función Pública (SETID), "Cobertura de banda ancha en España 2021–2025" (municipal file, downloaded
  once into `.cache/internet/`). Shown in the tooltip and in `coverage_*_pct`; not used for colours.
  It is often the more telling figure for villages: ~700 municipalities have under half of households
  able to get 100 Mbps.
- **What it shows:** wherever there are enough tests, fixed internet is fast. Practically nobody lives where
  measured fixed upload is under 10 Mbps. The gap is evidence: most municipalities under 1,000 people
  have too few tests.
- **Limitations:**
  - Speed tests measure the plans people have, not what could be installed.
  - Tiles straddling a border count for one municipality.
  - The boundaries are simplified (~200 m), so some seafront tiles fall "in the sea" and are dropped
    (e.g. ~16% of Cádiz's tests). Snapping them to the nearest municipality would also pull in
    Portuguese or Gibraltar tiles, so they are left out.

```bash
pip install -r pipeline/requirements.txt          # DuckDB (Ookla Parquet on S3), openpyxl (coverage file)
python3 pipeline/compute_internet.py              # latest 4 quarters; no API key needed (~4 min)
python3 pipeline/compute_internet.py --quarters 2025-1,2025-2,2025-3,2025-4
```

Quarter extracts for Spain are cached in `.cache/internet/`.

## Hospitals map

The **Hospitals** view (`#hospitals`) answers "if I work remotely here and need a hospital, how far is it?",
with the same public transport method as the cities and airports maps.

| Category | Rule (Catálogo Nacional de Hospitales 2025, Ministerio de Sanidad) |
|---|---|
| **Major** | public general hospital with a cardiac cath lab (`HEM` > 0) and ≥ 100 beds |
| **Public** (default) | public general hospital: run by a public body, or in the public network by agreement ("Red de utilización pública", "Concierto sustitutorio": e.g. Figueres, Olot, Palamós) |
| **Any** | any general hospital, private clinics included |

Specialised, long-stay, mental-health and other inpatient centres are left out. Currently 106 major,
321 public and 549 general hospitals.

- **Placing hospitals** (`pipeline/place_hospitals.py` → `data/es/hospitals.json`): the catalogue has addresses,
  not coordinates. Each hospital is matched by name to an OpenStreetMap hospital in the same municipality
  (Basque/Galician name forms handled); its arrival point is the nearest bus/rail stop within 400 m (TravelTime
  can't attach points inside a campus), else an entrance, else the OSM centre. Unmatched hospitals are placed
  from their address or postcode with Nominatim; `data/es/hospital_overrides.json` (keyed by CODCNH) fixes the rest
  by hand. `point_source` in `data/es/hospitals.json` says how each was placed.
- **Complexes:** the catalogue reports equipment once per hospital complex; its cath lab is assigned to the
  complex's largest site only. Formentera's 13-bed hospital reports a cath lab and is excluded from "major" by
  the 100-bed rule.
- **Points that don't attach** (`pipeline/nudge_hospitals.py`): hospitals nobody reaches are probed on rings of
  200/400/600 m from their own town; the first reachable point is kept as an exact override in
  `data/es/hospital_overrides.json` (16 hospitals moved). Positions already probed without success are recorded so
  they aren't probed again.
- **Coverage gaps:** 30 hospitals stay unreachable in TravelTime's data even after that, mostly where local
  buses are missing (e.g. Virgen de la Arrixaca in Murcia, Costa del Sol in Marbella, Ceuta's hospital).
  Places near them fall back to the next hospital; the list is in `hospitals.json` `params.notes` and on the page.
- **Hospital in town counts as close:** a municipality containing a hospital of the category gets 0 min to it
  ("in town"), even when TravelTime has no transit from the town centre to it (e.g. Marbella, Ceuta, Cuenca).
- **Caveat:** the catalogue doesn't say which private clinics have a 24 h emergency department.

```bash
python3 pipeline/place_hospitals.py      # catalogue + OSM + Nominatim -> data/es/hospitals.json (a few minutes)
python3 pipeline/compute_hospitals.py    # TravelTime, ~2,700 searches (~25 min), cached in .cache/hospitals/
python3 pipeline/nudge_hospitals.py      # move points of unreached hospitals, then run compute_hospitals.py again
```

## France (metropolitan)

The same four maps exist for metropolitan France (incl. Corsica): pick **France** at the top of the panel
(`#fr/cities`, `#fr/airports`, `#fr/internet`, `#fr/hospitals`).

**Each country is self-contained.** Everything a country reads and writes lives in its own folders:

```
data/es/  data/fr/                         inputs and curated lists (places.json, hospitals.json, overrides…)
web/public/data/es/  web/public/data/fr/   outputs: remoteness / airports / internet / hospitals .json .csv .csvt + boundaries
.cache/es/  .cache/fr/                     caches
```

Every pipeline takes `--country es|fr` (default `es`); Spain's outputs are checked to regenerate byte for byte.

| Map | France specifics |
|---|---|
| Base | ~34,700 communes from geo.api.gouv.fr (INSEE populations légales); origin = town hall (*mairie*); Etalab 2026 commune boundaries, simplified. Corsica is its own zone. |
| Cities | 1 central communes of the 22 *métropoles* · 2 + every *préfecture* + communes > 100k · 3 + communes > 50k |
| Airports | `pipeline/countries/fr_airports.py`, same rules as Spain. Points snapped to the airport's stop (`place_airports.py`, `data/fr/airport_points.json`). Cross-border links (Geneva, Luxembourg…) are mostly missing from TravelTime; 10 regional airports have no transit in the data. |
| Internet | Ookla as for Spain; official coverage from Arcep *Ma connexion internet* (share of premises ≥ 100 Mbps / 1 Gbps; no 5G per commune). |
| Hospitals | Only sites with a general emergency department (DREES SAE, table URGENCES2), positioned with FINESS coordinates (Lambert-93) and snapped to stops. 1 CHU/CHR · 2 public (incl. ESPIC, army hospitals) · 3 any. Search radius 150 km (300 km for CHU/CHR). |

```bash
python3 pipeline/build_places_fr.py                       # communes, city tiers, boundaries (npx mapshaper)
python3 pipeline/compute_times.py --country fr            # ~3,200 searches
python3 pipeline/compute_internet.py --country fr         # no API key
python3 pipeline/place_airports.py --country fr           # snap airports to stops (Overpass)
python3 pipeline/compute_airports.py --country fr
python3 pipeline/place_airports.py --country fr --nudge   # move points nobody reaches, then compute again
python3 pipeline/place_hospitals.py --country fr          # FINESS + SAE, snap to stops
python3 pipeline/compute_hospitals.py --country fr        # ~5,000 searches
python3 pipeline/nudge_hospitals.py --country fr          # then compute_hospitals again
```

## Using the data in QGIS

Both datasets come as a flat CSV, one row per municipality, next to the JSON:

- `web/public/data/es/remoteness.csv`: `t1_min`..`t3_min` minutes to the nearest metro / regional hub /
  urban area, `t*_city` its INE code.
- `web/public/data/es/airports.csv`: `y1_min`..`y3_min` (year-round) and `s1_min`..`s3_min` (with seasonal
  routes) minutes to the nearest intercontinental / Europe / any airport, `*_airport` its IATA code.

- `web/public/data/es/hospitals.csv`: `t1_min`..`t3_min` minutes to the nearest major / public / any hospital,
  `t*_hospital` its catalogue code (CODCNH, see `data/es/hospitals.json`).
- `web/public/data/es/internet.csv`: `fixed_down_mbps`, `fixed_up_mbps`, `fixed_latency_ms`, `fixed_tests`,
  `fixed_devices` and the same for `mobile_*` (measured; empty = not enough local tests), then
  `fixed_est_*` / `mobile_est_*` (estimated from tests within 10 km, only where there is no measured value)
  and `coverage_100mbps_pct`, `coverage_1gbps_pct`, `coverage_5g_pct` (official 2025 coverage).

Empty cells in the first two mean over 3 hours or no airport/city reachable. Load the CSV as a delimited text layer
without geometry and join it on `code` to a municipalities layer whose INE code is a 5-digit text field
(for example `web/public/data/es/municipalities.topo.json`, whose feature ids are those codes). The `.csvt` file next to each
CSV makes QGIS read `code` as text, so `01001` keeps its leading zero.
`python3 pipeline/compute_times.py --csv-only` rebuilds the cities CSV from the JSON without API calls.

## Running it

### Hosting on Coolify

The repo root has a `Dockerfile`: it builds `web/` with Node and serves the static
result with nginx (`nginx.conf`: gzip, long cache on hashed assets, 1 h on data).

1. Coolify → New resource → Public/GitHub repository → `yannklein/spain-remoteness`, branch `main`.
2. Build pack: **Dockerfile**. Ports exposes: **80**. No environment variables needed.
3. Set the domain and keep **auto deploy** on, so every data commit redeploys.

### Computing the data (GitHub Actions)

1. Add repo secrets `TRAVELTIME_APP_ID` and `TRAVELTIME_API_KEY`
   (Settings → Secrets and variables → Actions).
2. Actions → **Compute travel times** → Run workflow. Put `5` in *limit* first for a smoke test
   (it prints a sample and does not commit), then run it with *limit* empty.
3. The workflow commits `web/public/data/es/remoteness.json`; Coolify picks up the push and redeploys.

The compute workflow also runs quarterly, since timetables change.

### Locally

```bash
python3 pipeline/build_places.py            # needs internet (INE + Overpass)
export TRAVELTIME_APP_ID=... TRAVELTIME_API_KEY=...
python3 pipeline/compute_times.py --limit 5 # smoke test
python3 pipeline/compute_times.py           # everything
python3 -m pytest -q pipeline/tests         # tests use a mocked API

cd web && npm install && npm run dev
```

## Sources & licences

- Municipality boundaries: IGN / CNIG via [es-atlas](https://github.com/martgnz/es-atlas) (MIT)
- Municipality list and island mapping: [spanish-cities-info](https://www.npmjs.com/package/spanish-cities-info) (ISC), verified against INE
- Population: INE, *Cifras oficiales de población de los municipios españoles* (table 29005)
- Town centres: © OpenStreetMap contributors (ODbL)
- Travel times: [TravelTime API](https://traveltime.com)
- Internet speeds: [Speedtest® by Ookla® Global Fixed and Mobile Network Performance Maps](https://github.com/teamookla/ookla-open-data) (CC BY-NC-SA 4.0)
- Hospitals: Ministerio de Sanidad, [Catálogo Nacional de Hospitales](https://www.sanidad.gob.es/estadEstudios/estadisticas/sisInfSanSNS/ofertaRecursos/hospitales/home.htm) (2025); hospital positions © OpenStreetMap contributors (ODbL) and Nominatim
- Broadband coverage: Ministerio para la Transformación Digital y de la Función Pública (SETID), [Información de cobertura](https://digital.gob.es/telecomunicaciones-infraestructuras-digitales/areas-interes/banda-ancha/informacion-cobertura)
- France: communes and populations © INSEE via [geo.api.gouv.fr](https://geo.api.gouv.fr); boundaries © IGN / Etalab [contours administratifs](https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/); hospitals: FINESS (Ministère de la Santé) and [DREES SAE](https://data.drees.solidarites-sante.gouv.fr); internet coverage © [Arcep](https://data.arcep.fr) Ma connexion internet
- Basemap: [OpenFreeMap](https://openfreemap.org) Positron
