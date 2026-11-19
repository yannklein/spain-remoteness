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
data/municipalities_base.json   8,132 INE municipalities (codes, names, islands, centroids)
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
web/public/data/remoteness.json  → per municipality and tier: minutes + nearest city
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
3. The workflow commits `web/public/data/remoteness.json`; Coolify picks up the push and redeploys.

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
- Basemap: [OpenFreeMap](https://openfreemap.org) Positron
