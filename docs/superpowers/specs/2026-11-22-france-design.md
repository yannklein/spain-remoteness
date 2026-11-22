# France: all four maps, self-contained per country

Date: 2026-11-22 · Status: approved 2026-11-22 (scope, categories and structure confirmed by the user)

## Intent

Do for metropolitan France everything the site does for Spain: cities, airports, internet and hospitals,
for the same reader (someone deciding where they could live and work remotely). Each country's data is
**self-contained**: its own inputs, caches, outputs and CSVs, which can be rebuilt and reused (QGIS)
without the other.

## Goals

- `--country es|fr` on every pipeline; per-country folders for data, caches and outputs.
- Spain's outputs unchanged by the restructure (same bytes, new paths).
- The same four maps for metropolitan France (incl. Corsica), with French category definitions.
- A Spain / France switch on the page.

## Non-goals

- Overseas France (DOM): later.
- Cross-country analysis (a French village's nearest Spanish hospital). Foreign airports near the border are the
  one exception, as for Spain.

## Anti-goals

- Spain's data silently changing because of shared code.
- A country's map loading the other country's files.

## Approaches considered

- **A. Shared code, per-country configuration (chosen).** `pipeline/countries/es.py` and `fr.py` hold what differs (sources, category rules, zones, bounding boxes, map views, curated lists); the pipelines take `--country`.
- B. A copy of the pipeline per country. Rejected: the copies drift, and every fix (retries, stops, moved points) would need doing twice.

## Layout (decided)

```
data/es/…  data/fr/…                        inputs and curated lists (places.json, hospitals.json, overrides…)
pipeline/countries/{es,fr}.py               country configuration
.cache/es/…  .cache/fr/…                    caches (times, airports, internet, hospitals)
web/public/data/es/…  web/public/data/fr/…  outputs: *.json, *.csv, *.csvt, municipalities.topo.json
```

- Spain's existing files move with `git mv`. A restructure test regenerates Spain's outputs from cache and compares them byte for byte with the committed ones (apart from `generated_at`).
- The page reads `./data/<cc>/…`. The hash becomes `#<cc>/<mode>` (e.g. `#fr/hospitals`); old hashes (`#airports`) keep meaning Spain.

## France base data

- **Communes** (metropolitan: departments 01–95 incl. 2A/2B, ~34,900):
  - from `geo.api.gouv.fr/communes` (code, name, department, population, `mairie` point);
  - the town-hall point is the origin, the equivalent of Spain's OSM town centres, with the commune centroid as fallback;
  - the population year is the INSEE *populations légales* year served by the API.
- **Boundaries:** Etalab *contours administratifs* 2025, `communes-100m`, converted to TopoJSON (communes + departments as the province layer) with `npx mapshaper`, quantised so the file stays at a reasonable size. Paris, Lyon and Marseille are single communes.
- **Zones:** Corsica (2A, 2B) is `island:Corse`; everything else is mainland. Ferries to small islands (Belle-Île, Yeu, Ouessant…) are left to TravelTime's timetables.

## Categories (approved)

| Map | 1 | 2 (default) | 3 |
|---|---|---|---|
| Cities | central communes of the 22 *métropoles* | + every *préfecture* + communes > 100k | + communes > 50k |
| Airports | route > 4,000 km | ≥ 1 route to another European country | any scheduled flight |
| Hospitals | CHU/CHR (FINESS category 101) with an emergency department | + public *centres hospitaliers* (355) with an emergency department | + private medicine/surgery/obstetrics establishments with an emergency department |
| Internet | Ookla speeds, estimates within 10 km, official coverage (Arcep) | | |

- Airports keep the year-round / seasonal variants. Foreign airports with scheduled flights within reach of the border are listed: Geneva, Luxembourg, Brussels-Charleroi, Karlsruhe/Baden-Baden, Saarbrücken, Girona, San Sebastián, Barcelona. Basel-Mulhouse is on French soil. As in Spain, a cross-border check runs first.
- Hospitals: an emergency department means a general emergency activity in the latest DREES SAE base (table URGENCES, by geographic FINESS number). "Major" is CHU/CHR sites with an emergency department.
- Internet official coverage: Arcep *Ma connexion internet* statistics per commune, latest quarter: `elig_thd100/nbr` and `elig_thd1g/nbr` as % of premises. There is no 5G per commune (the column stays empty for France). The estimate gate (no fixed estimate where ≥ 100 Mbps coverage < 50%) applies.

## TravelTime budget

- **Same method as Spain:** best of three Tuesday arrivals, 3 h cap, best-of-chunks.
- **Hospital radius:** tier 2/3 hospitals search origins within **150 km**, tier 1 within 300 km (a per-destination `max_km`).
- **Estimate for France:** cities ~3,000–4,000 searches, airports ~2,000, hospitals ~8,000–10,000.
- **Order of the runs:** cities, then internet (no TravelTime), airports, hospitals. If TravelTime rejects requests for quota reasons, the run stops, the cache keeps what's done, and the user is asked.

## Web

- A country switch (`Spain | France`) above the mode switch. Titles say "rural Spain" / "rural France".
- Map views per country: France has Metropole / Corse.
- Copy, help texts and "How this map is made" per country. The category labels come from the country config, and the JSON params carry the copy the page needs.
- Data for a country loads only when that country is selected.

## Tests

- The Spain byte-for-byte restructure test.
- Country config loading.
- France: commune parsing, zone rule, category rules on fixtures, Lambert-93 → WGS84 conversion for FINESS coordinates (checked against known points), the SAE emergency filter, the Arcep parsing, the per-destination radius.

## Known limitations

- About 35k communes make the French TopoJSON and JSON larger (a few MB). They load only when France is chosen.
- The same TravelTime coverage caveats apply (local buses, cross-border links).
