# Climate: heat, hot nights and frost per municipality

Date: 2026-11-23 · Status: approved 2026-11-23 (metrics proposed; "free Copernicus account!")

## Intent
Summer heat is becoming a deal-breaker for living somewhere (inland Spain especially); winter cold matters too.
This adds a Climate map per country and gems criteria.

## Approaches
- **A. ERA5-Land daily statistics (Copernicus CDS), chosen.** Gridded at about 9 km, daily highs and lows, CC BY licence, can be cut to each country, free account.
- B. E-OBS (station-based grid): better at extremes, but its licence covers non-commercial research and education.
- C. WorldClim monthly normals: no account, but no counts of hot days.

## Metrics (per municipality, mean over 2015-2024)
- **Days per year:** hot days (daily max ≥ 35 °C), hot nights (daily min ≥ 20 °C), frost days (daily min < 0 °C).
- **Averages:** the July high (mean daily max in July) and the January low (mean daily min in January).
- **Sampling:**
  - each municipality takes the grid cell at its town centre (the same point as the travel times);
  - coastal points that fall on a sea cell take the nearest land cell within 3 cells.
- **Known bias:** ERA5-Land is 2–3 °C cooler than stations on extreme days (Montoro, 14 Aug 2021: 44.9 vs 47.4 °C measured). Hot-day counts are conservative, and the notes say so. Grid cells average out mountain villages and valleys.

## Map and gems
- **Map:**
  - buttons: Hot days | Hot nights | Frost;
  - light = fewer days;
  - the tooltip gives all five figures.
- **Gems:** "Hot days ≤ X" and "Frost days ≤ X", both off by default.
- **Mode switch:** two rows of four.

## Data
- **Downloads:** ERA5-Land daily max and min of 2 m temperature, UTC+1, one request per box, statistic and year.
- **Boxes:**
  - Spain: peninsula with the Balearics, Ceuta and Melilla `[44, -9.5, 35, 4.5]`, and the Canaries `[29.5, -18.3, 27.5, -13.3]`;
  - France: `[51.2, -5.3, 41.3, 9.7]`.
- **Locations:**
  - cache: `.cache/<cc>/climate/`;
  - outputs: `climate.json`, `climate.csv`.
