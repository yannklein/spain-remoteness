# Hospitals map: design

Date: 2026-11-21 · Status: approved 2026-11-21 (tiers + approach A + catalogue download confirmed by the user)

## Intent

A fourth dataset: public transport time from every municipality to the nearest hospital, for someone
working remotely who "could need anything" (an emergency, a specialist, planned care). It follows the
same pattern as the airports map: JSON + CSV per municipality, a mode on the page.

## Categories (nested, decided)

| Tier | Name | Rule (from the Catálogo Nacional de Hospitales 2025) |
|---|---|---|
| 1 | Major hospital | tier 2 **and** at least one haemodynamics room (`HEM` > 0, cath lab: heart attacks, strokes, major trauma) **and** ≥ 100 beds |
| 2 | Public hospital (default) | general hospital (`Cód. Clase de Centro` = C11) that is **public**: functional dependency 1–8, **or** concierto "Red de utilización pública (RUP)" or "Concierto sustitutorio" (e.g. Figueres, Olot, Palamós, private on paper but in Catalonia's public network) |
| 3 | Any hospital | any general hospital (C11), private included |

- Left out: specialised (C12: mutual-insurance trauma clinics, oncology, standalone maternity/children's), long-stay (C13), mental health (C14), other inpatient centres (C190).
  - Call: excluding C12 drops public maternity/children's hospitals, but those sit inside complexes with a general hospital, so travel times barely change.
- Equipment and concierto marked `DC` ("dato en complejo") are read from the hospital's complex row (`CODIDCOM`).
- Counts in the 2025 file: 549 general hospitals; 321 public by the rule above; 106 major (cath lab at the site and ≥ 100 beds; a complex's lab counts for its largest site only).

## Approaches considered

- **A. Match each catalogue hospital to OpenStreetMap (chosen).** One Overpass query for `amenity=hospital` in Spain, matched by normalised name within the same municipality (falling back to the nearest OSM hospital within 2 km of the geocoded address). The arrival point is the nearest public transport stop within 400 m of the OSM hospital, else its entrance (`entrance=*` node), else its centroid. Unmatched hospitals are geocoded from their address with Nominatim (1 request/s, project User-Agent).
- B. Geocode every address with Nominatim. Points land on street addresses or campus centres, which brings back the airport-terminal "can't attach" problem, and needs ~550 requests. Not chosen.

## Method

- Same TravelTime method as cities/airports: arrive by 08:30 / 11:30 / 14:30 on the next Tuesday, best of three, 3 h cap, origins within 300 km in the same zone, town-centre origins. Hospital ids are prefixed `HOS:<CODCNH>`.
- Zone: a hospital's zone comes from its municipality in `places.json` (islands, Ceuta, Melilla).
- Each hospital is computed once; aggregation picks the nearest per tier. Cache: `.cache/hospitals/<method>/`.
- The `reach` per hospital is stored, as for airports. Hospitals nobody reaches are reported in `params.notes` (a hint that the arrival point didn't attach).

## Hospital in town (decided with the user after review)

A municipality that contains a hospital of the category counts as close: 0 min to its own hospital,
tooltip "in town", even where TravelTime has no transit from the town centre to it (~660k people in
Marbella, Cuenca, Estepona, Ceuta… had shown "none within 3 h").

## Output

- `web/public/data/hospitals.json`:
  - `hospitals: [[codcnh, name, municipality_code, lat, lng, tier, beds, public(0/1), cath_lab(0/1), reach, point_source]]`
  - `m: code -> [t1, h1, t2, h2, t3, h3, population]`, with minutes or -1 and the hospital index or -1.
- `hospitals.csv` (+ `.csvt`): `code,name,province,population,t1_min,t1_hospital,t2_min,t2_hospital,t3_min,t3_hospital`, where the hospital column holds `CODCNH`.
- `data/hospitals.json`: the matched hospital list with coordinates and how each was placed (OSM stop / entrance / centroid / Nominatim). It is committed so the positions can be reviewed and fixed by hand.

## Web

- The mode switch gets a fourth button, **Hospitals** (`#hospitals`).
- Buttons: **Major | Public | Any**; the default is Public.
- Same colour scale and legend as the cities map (minutes). Municipalities aren't greyed out; markers show hospitals of the selected tier.
- Tooltip: time, then "to Hospital García Orcoyen (Estella-Lizarra)", plus the tier description.
- Headline: "**X%** of people are more than **30 min** by public transport from a public hospital", population-weighted. (30 min, not 60, because hospitals are far denser than airports.)
- "How this map is made": source and rules, plus the caveat that the catalogue doesn't say which private hospitals have a 24 h emergency department.

## Tests

- Tier rules on a fixture workbook: public by dependency, by RUP, by sustitutorio; partial concierto is not public; DC is resolved through the complex; C12–C14 are excluded.
- Name normalisation and matching; the stop-selection rule; zone assignment.
- Aggregation for nested tiers; CSV layout.

## Known limitations

- The catalogue is dated 31 Dec 2024.
- Arrival points come from OSM and may be off for some campuses. `data/hospitals.json` records how each one was placed.
- Same TravelTime coverage gaps as the other maps.
