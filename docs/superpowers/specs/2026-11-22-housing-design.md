# Housing: rent and buy prices per municipality

Date: 2026-11-22 · Status: approved 2026-11-22 ("rent and buy", "A and B", "ok")

## Intent
For the remote worker choosing where to live, housing cost is usually the main reason to go rural. This adds a
Housing map per country, with rent and purchase prices per m², which also become gems criteria.

## Approaches
- **Spain, buy:**
  - A. No sale price per village. Chosen, combined with B.
  - B. A coarse price: Ministry appraisal values for towns over 25,000 and the province average elsewhere, always marked as such. Chosen.
  - C. Ask the notaries for permission to reuse their per-municipality prices. Deferred: their terms forbid redistribution without written permission.
- **One build path:** a pipeline per country writes housing.json and .csv, the same as the internet map. No TravelTime calls.

## Sources (checked 2026-11-22)

| | Rent (€/m² per month) | Buy (€/m²) |
|---|---|---|
| **Spain** | SERPAVI (MIVAU) database 2011–2024. For each municipality: the latest year of 2022–2024 with a value, median €/m² for single-family houses (VU) and flats (VC), with the number of leases (at least 10 leases to be published). | MIVAU appraisal value: free-market housing for towns over 25,000 (latest quarter, all dwellings, matched by name within the province), and the province average (latest quarter) for everywhere else. Always marked as coarse |
| **France** | ANIL "carte des loyers" 2025 (advertised rents including charges, predicted for every commune), houses and flats. Shown as an estimate where the prediction is pooled over an area (TYPPRED "maille"), has an R² under 0.5, or rests on fewer than 30 listings | DVF statistics (Etalab), 10 half-years: median €/m² of house and flat sales, with sale counts. No DVF in Alsace-Moselle (57, 67, 68) |

## Behaviour
- **Review fixes (2026-11-23):** single-province regions matched by name (Murcia/Navarra swap); Paris/Lyon/Marseille scope from the listings-weighted share of weak arrondissements; DVF medians outside 200–30,000 €/m² dropped; the gems rent criterion is off by default (a missing figure would exclude the smallest villages); Spanish appraisals are "any home" and "appraisals".
- **Missing own value:** Spanish rent and French buy are estimated from municipalities within 10 km. The estimate is the count-weighted mean of their medians, with at least 10 leases or 5 sales in total. It is hatched and named "nearby" in the tooltip and CSV. Otherwise the value is missing (grey).
- **Scope per value:** 0 own, 1 nearby, 2 province average (Spain buy), 3 area model (France rent).
- **Map:**
  - buttons Rent | Buy; checkbox "Flats instead of houses" (houses by default);
  - light colours = cheap;
  - hatching on anything that isn't the municipality's own figure.
- **Gems:**
  - "Rent ≤ €X/m²", off by default (changed in review);
  - "Price to buy ≤ €X/m²", off by default; when on, Spanish villages are judged on their province average, and the tooltip says so;
  - a missing value fails the criterion.
- **Prices are not comparable between countries:** Spanish rents come from real leases, French rents from listings including charges. The method notes say so.

## Non-goals
- Notary prices (option C).
- History and trends.
- Rents for social housing.
