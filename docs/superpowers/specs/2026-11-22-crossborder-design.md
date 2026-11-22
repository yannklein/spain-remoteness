# Cross-border cities and airports, through border stations

Date: 2026-11-22 · Status: draft, awaiting approval

## Intent

A remote worker living near a border uses the city or airport on the other side: Hendaye → San Sebastián, Annemasse → Geneva, Tui → Porto. The cities and airports maps should count them, for both Spain and France.

TravelTime has almost no cross-border public transport. In November 2026 no Spanish municipality reached Lisbon, Porto, Faro, Toulouse, Biarritz or Perpignan airports, and from France only a handful of communes reached Geneva (6), Luxembourg (2), Karlsruhe (2) and Charleroi (1). Adding foreign destinations as they are therefore changes almost nothing.

## Approaches

- **A. Add the foreign cities as plain destinations.** Cheap, and everything stays measured, but Spain gains nothing and France very little. Rejected.
- **B. Border stations (chosen by the user).** TravelTime measures the trip to a home-country stop that has a cross-border service (a "gateway"). A researched onward time from timetables (a "hop") is then added. The result is an estimate and is marked as one.

## Goals

- Foreign cities count on the cities map, and foreign airports count on the airports map, for `es` and `fr`.
- A time reached through a gateway is always marked as an estimate, on the map (hatched), in the tooltip ("via Hendaye") and in the CSV.
- Each country stays self-contained. Its gateways, hops and foreign destinations live in its own config and caches.

## Non-goals

- Hospitals. A foreign emergency department is a different question (insurance, language).
- Chaining timetables exactly. The estimate assumes the onward service connects.

## Anti-goals

- An estimate shown as if it were measured.
- A home-country time getting worse. The result is always the minimum of the measured time and the estimate.

## How it works

- **Gateway:** a stop in the home country served by a scheduled, year-round, weekday cross-border service (train, tram or bus). It is computed like any destination (`GW:<id>`): best of the three Tuesday arrivals, 3 h cap, origins within 250 km, same zone.
- **Hop:** `(gateway, destination code, minutes, service, source)`.
  - **Minutes:** the scheduled ride time of the fastest weekday service, plus 10 minutes for the change.
  - **Ride:** from the gateway stop to the destination's point, which is the main station for a city and the terminal stop for an airport.
  - **Sources:** operator timetables, checked in November 2026. A service that is only seasonal, or runs on fewer than 5 weekdays, doesn't count.
- **Estimate:** for each municipality and foreign destination, the time is min over hops of (time to the gateway + hop minutes). It is kept only if it beats the measured time to that destination and stays within 3 h. The rest of the aggregation (nearest per tier, seasonal variants) is unchanged.
- **Outputs:**
  - **JSON:**
    - each JSON gains `gateways: [[id, name, lat, lng]]`;
    - each municipality row gains one trailing element: `null` when everything is measured, else the gateway index per slot (`-1` = measured);
    - the existing indices don't move.
  - **CSV:** gains a `*_via` column per tier or variant, holding the gateway name, or empty when measured.
- **Web:** estimated cells get the hatch already used by internet estimates. The tooltip shows "≈ 1 h 35 to Porto, via Tui station (estimate)", and the method text explains it.

## Foreign destinations (my calls, for review)

Tiers follow each country's own rule: for Spain the municipal population thresholds and capitals, for France the size of the smallest métropoles. Only places that can plausibly be reached within 3 h are listed. Each one has:

- a code `<ISO2>:<slug>` (e.g. `PT:porto`), which goes in the `*_city` CSV column;
- its main station as its point;
- its municipal population.

- **Spain's cities map**
  - **Tier 1:** Lisboa, Toulouse.
  - **Tier 2:**
    - Portugal: Porto, Braga, Guimarães, Viana do Castelo, Bragança, Guarda, Castelo Branco, Portalegre, Évora, Faro;
    - France: Perpignan, Pau, Tarbes, Bordeaux, Foix;
    - Andorra: Andorra la Vella (national capital).
  - **Tier 3:** Bayonne. Gibraltar stays out (34k, under the 50k threshold).
- **France's cities map**
  - **Tier 1:** Barcelona, Bilbao, Donostia/San Sebastián, Genève, Lausanne, Basel, Luxembourg, Bruxelles, Liège, Charleroi, Saarbrücken, Karlsruhe, Freiburg, Torino.
  - **Tier 2:** Girona, Andorra la Vella, Neuchâtel, Mons, Tournai, Namur, Aosta, Cuneo, Monaco.
  - **Tier 3:** Irun, Sanremo, Kortrijk, Mouscron, Offenburg.
- **New foreign airports**
  - **For France:** Zürich (ZRH, tier 1), Brussels (BRU, tier 1), Frankfurt (FRA, tier 1) and Bilbao (BIO, tier 2).
  - **For Spain:** Bordeaux (BOD, tier 1).
  - The existing foreign airports (Spain: LIS, OPO, FAO, TLS, BIQ, PGF, LDE, PUF, GIB; France: GVA, LUX, CRL, FKB, SCN, GRO, EAS, BCN) get hops.
- **Gateways, about 15–25 per country.** Examples:
  - **Spain:** Irun, Portbou, Figueres-Vilafant, Puigcerdà, La Seu d'Urgell, Tui, Vigo, Badajoz, Ayamonte, Huelva, Sevilla bus station, Fuentes de Oñoro.
  - **France:** Hendaye, Cerbère, Perpignan, Latour-de-Carol, Annemasse, Saint-Julien, Saint-Louis, Mulhouse, Strasbourg, Forbach, Thionville, Longwy, Jeumont, Lille, Menton, Modane.
  - The exact list follows from the timetables researched during the build.

## Files

- **Config:** `pipeline/countries/{es,fr}_crossborder.py` holds `FOREIGN_CITIES`, `GATEWAYS` and `HOPS`, with the new foreign airports added to the country's airport list.
- **Shared code:** a new `pipeline/crossborder.py`, used by `compute_times.py` and `compute_airports.py`.
- **Caches:** gateway results go in the country's existing times cache.
- **Cost:** about 150 TravelTime searches for Spain and about 400 for France, once.

## Tests

- **Estimate:** the minimum over hops, and "measured wins when faster".
- **Cap:** at 3 h, no estimate is kept.
- **Output indices:** `-1` for measured slots, and the pre-existing indices are unchanged.
- **CSV:** the `*_via` columns.
- **Config check:** every hop names a known gateway and destination, and minutes are > 0.
- **Spain regeneration:** the test is updated to the new outputs.

## Left to the builder

- Exact gateway coordinates (snapped to the stop, as for airports).
- Hop research.
- Copy for the method text, and the airports note on cross-border links, which is rewritten to explain the gateways.
