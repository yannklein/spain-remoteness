# Airports map: design

Date: 2026-11-20 · Status: approved 2026-11-20

## Intent

Add a second dataset next to the "nearest main city" one: for every Spanish
municipality, the public transport time to the nearest airport, by airport
category. Like the first dataset, everything the pipeline produces lands in a
file that can be reused outside the web map (QGIS in particular).

## Goals

- Per municipality, the time to the nearest airport of each category, and which airport it is.
- Three nested airport categories, each computed twice: year-round routes only, and with summer-only routes included.
- Shown on the existing page, switchable between the Cities and Airports maps.
- A flat CSV next to each JSON (airports *and* the existing cities data) that QGIS can join to the boundaries by `code`.

## Non-goals

- No GitHub Actions. The pipeline runs locally and the user commits the output. The existing `.github/workflows/compute.yml` stays as it is (not extended, not removed).
- No changes to the city pipeline's results or method.

## Anti-goals

- Counting airports with no scheduled passenger flights (Teruel, Huesca, Ciudad Real, Burgos if confirmed). They would make nearby villages look connected when nobody can fly from there.

## Approaches considered

- **A. Separate script reusing the existing code, same page (chosen).** `pipeline/compute_airports.py` imports the TravelTime client, zone rule and cache helpers. The city pipeline stays untouched; one page, one deploy.
- B. Make `compute_times.py` generic (`--dataset airports`). Less duplication, but each change risks the computed city data, and the airport-specific parts (terminal points, summer variant) would become special cases.
- C. Same pipeline as A on a separate page. Duplicates the panel and map code, and users can't flip between views.

## Airport categories (decided)

Nested like the city tiers: each wider category includes the narrower ones.

| Tier | Name | Rule |
|---|---|---|
| 1 | Intercontinental | Scheduled long-haul flights (see rule below) |
| 2 | Europe | Scheduled flights to other European countries (see rule below) |
| 3 | Any airport | Any scheduled passenger flight, domestic included |

Each airport has two tiers: `tier_year` (year-round routes only) and `tier_summer`
(summer-only routes counted too). `tier_summer <= tier_year` always. `null` means
"not a destination in that mode".

**Rules (my calls, to confirm):**

- *Intercontinental*: at least one scheduled route longer than 4,000 km (great-circle).
  This captures the Americas, the Gulf and Asia, and leaves out Morocco, Turkey, Israel and Cape Verde-style routes, which behave like European ones. Expected year-round: Madrid, Barcelona (plus possibly Tenerife Norte for Caracas); with summer: + Málaga, Palma, Bilbao and others the research finds.
- *Europe*: at least one scheduled route to another European country, and that route has to be year-round for `tier_year`. One weekly London flight is enough, deliberately: the question is "can I fly abroad from here".

## Airport list (builder)

A hand-curated `pipeline/airports.py`, in the spirit of `pipeline/cities.py`:

```python
# iata, name, country, lat, lng, tier_year, tier_summer, note
("MAD", "Adolfo Suárez Madrid-Barajas", "ES", 40.4936, -3.5668, 1, 1, ""),
```

- Scope: every Spanish airport with any scheduled passenger flight, plus the foreign airports near the border (next section). That means the AENA network, plus non-AENA ones such as Castellón and Lleida-Alguaire if they have scheduled flights. Heliports (Ceuta, Algeciras) and general aviation airfields are excluded.
- Coordinates are the **passenger terminal** (or its public transport stop), not the runway centroid or the host municipality's centre.
- Routes are checked against current sources (AENA, airport route pages, airline schedules) for the 2026 schedules. The `note` field records the route or reason behind each tier (e.g. "summer: United EWR"). Excluded airports stay in the file with both tiers `None` and a reason, so the decision is visible.
- Each airport carries a `country` (`ES`, `PT`, `FR`, `GI`).
- The zone (mainland / island / Melilla) is derived with the existing `zone()` rule. Each island airport needs its `island` set, matching `municipalities_base.json` naming.

## Foreign airports (decided: include the ones that make sense)

Rule (my call): a foreign airport is included if it has scheduled passenger flights and
a Spanish border area could plausibly reach it within the 3 h cap. All are in the
"mainland" zone, and origins are still Spanish municipalities only.

| Candidate | Serves | Likely tier |
|---|---|---|
| Lisbon (LIS) | Extremadura, western Andalucía | 1 |
| Porto (OPO) | Galicia, Zamora/Salamanca border | 1 |
| Faro (FAO) | Huelva coast | 2, 1 with summer (EWR) |
| Gibraltar (GIB) | La Línea, Campo de Gibraltar | 2 (UK only) |
| Biarritz (BIQ) | Gipuzkoa, Navarra | 2 |
| Pau (PUF), Tarbes-Lourdes (LDE) | Aragonese/Navarrese Pyrenees | 3 / 2, to verify |
| Toulouse (TLS) | Val d'Aran, Pyrenees | 2, 1 with summer if Montreal still flies |
| Perpignan (PGF) | Alt Empordà, Ripollès | 2 |

- The builder verifies tiers like any other airport. Candidates that turn out to reach no Spanish municipality within 3 h simply never win the nearest-airport step. They stay in the file, which costs a few searches.
- **Excluded:** Moroccan airports next to Ceuta and Melilla (Tanger, Nador). Crossing those borders on foot is restricted and irregular, and TravelTime has no reliable transit data there. Bragança and Vila Real (PT) have a single domestic route and almost no transit access from Spain.
- **Risk to check first:** whether TravelTime's timetables include cross-border buses and trains (Vigo→Porto, Badajoz→Lisbon, Irun/Hendaye→Biarritz, Figueres→Perpignan, La Línea→Gibraltar on foot). The builder runs these few trips with `--limit` before the full run and records the outcome in the README. If a link is missing, the airport stays in the file but the page says that link isn't covered.

## Pipeline: `pipeline/compute_airports.py`

- Reuses `Client.regular`, `arrival_times`, `parse_results`, `zone`, `haversine_km` from `compute_times.py` / `common.py`. Small refactors that only *move* shared code are fine. Behaviour and city output must stay identical.
- Same method as cities: many-to-one arrival searches, arrive at 08:30 / 11:30 / 14:30 on the next Tuesday, best of the three, 3 h cap, origins within 300 km in the same zone, origins at town centres from `data/places.json`.
- Airport location ids are prefixed (`AIR:MAD`) so they never collide with INE codes. The airport's own municipality is an origin like any other (its time isn't forced to 0).
- Each airport is computed once, whatever its tier. Aggregation then runs 6 times (3 tiers × year/summer), using only the airports eligible in that mode.
- Cache: `.cache/airports/regular-0830-1130-1430/<IATA>.json`, so an interrupted run resumes.
- Same CLI as `compute_times.py`: `--limit N`, `--no-cache`. No `--endpoint fast` (not needed).
- Cost: about 45 airports, roughly 3–9 searches each, so a few hundred searches, a few minutes on the free key.

## Output

`web/public/data/airports.json` (compact, same conventions as `remoteness.json`):

```jsonc
{
  "generated_at": "...",
  "params": { "mode": "public_transport", "arrival": "...", "arrival_times": [...],
              "max_minutes": 180, "population_year": 2025, "notes": [] },
  // [iata, name, country, lat, lng, tier_year, tier_summer, note]
  "airports": [["MAD", "Madrid-Barajas", "ES", 40.49, -3.57, 1, 1, ""], ...],
  // code -> [y1_min, y1_ap, y2_min, y2_ap, y3_min, y3_ap,
  //          s1_min, s1_ap, s2_min, s2_ap, s3_min, s3_ap, population]
  // min = minutes, -1 = over 3 h / none in zone; ap = index into airports, -1 = none
  "m": { "01001": [...] }
}
```

CSVs, one row per municipality, UTF-8 with header, written by each script next to its JSON:

- `web/public/data/airports.csv`: `code,name,province,population,y1_min,y1_airport,y2_min,y2_airport,y3_min,y3_airport,s1_min,s1_airport,s2_min,s2_airport,s3_min,s3_airport` (airport as IATA code).
- `web/public/data/remoteness.csv`: `code,name,province,population,t1_min,t1_city,t2_min,t2_city,t3_min,t3_city` (city as INE code). `compute_times.py` gains this export. Running it from cache regenerates the CSV without API calls.
- Unreachable / over 3 h = **empty cell** (NULL in QGIS), not -1. `code` is text, zero-padded (`01001`), to match the boundaries' ids.

## Web page

- **Dataset switch** at the top of the panel: `Cities | Airports`. It's reflected in the URL hash (`#airports`) so a view can be linked. Title, lead text, category buttons, help text, headline, "How this map is made" and attribution change with it.
- **Airports mode:**
  - Category buttons are `Intercontinental | Europe | Any airport`, with counts. The default is Europe, mirroring Regional hubs.
  - An **"Include summer-only routes"** checkbox, off by default (year-round is the conservative reading). Toggling it swaps between the `y*` and `s*` values and updates the counts and airport markers.
  - No grey "main city" municipalities. Every municipality is coloured, including the one hosting the airport.
  - Airport markers sized by tier, labelled by name or IATA at higher zooms, like the city dots.
  - Tooltip: time, then "to Málaga (AGP)", or "to Porto (OPO, Portugal)" for foreign airports.
  - Headline: "**X%** of people are more than **1 hour** by public transport from an intercontinental airport", population-weighted over all municipalities.
  - Same colour bins and legend as the cities map, minus the grey swatch.
- Cities mode behaves exactly as today.
- Only the data of the active dataset needs to be loaded at startup. The other loads when it's first selected.

## Known limitations (to state on the page / README)

- Times use a November-style weekday timetable from TravelTime. Summer-only airport shuttles aren't reflected even when summer routes are counted.
- Cross-border public transport depends on TravelTime's coverage; whatever the pre-check finds missing is stated.
- Ceuta and Melilla only count Spanish airports (Melilla's own; Ceuta has none).
- Same TravelTime coverage gaps as the cities map.

## Tests

Extend `pipeline/tests/test_pipeline.py` (mocked API, as today):

- Tier filtering and aggregation for both year/summer modes, including an airport that only exists in summer mode.
- The `AIR:` id prefix round-trips.
- CSV: empty cells for unreachable, zero-padded codes, one row per municipality.
- The city JSON is unchanged by the refactor (same output for the same cached inputs).

## Left to the builder

- Researching and verifying the airport list and its tiers (the main effort). Record sources in the notes.
- Marker icon/styling and exact copy, matching the existing look.
- README section mirroring the cities one (method, local commands, sources).
