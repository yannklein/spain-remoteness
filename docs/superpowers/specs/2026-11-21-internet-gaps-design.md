# Internet map: filling the gaps (estimates + official coverage)

Date: 2026-11-21 · Status: approved 2026-11-21 · Extends `2026-11-21-internet-design.md`

## Why

4,454 of 8,132 municipalities (1.4 M people, median 172 inhabitants) are grey on the internet map:
1,230 have no speed test at all, 2,676 have 1–19, 548 have too few devices. The user wants to say
something useful about those places too ("could I work remotely from here?").

## Approaches considered

- **A. Estimate from nearby tests (chosen, combined with D).** For a municipality without enough local tests,
  pool the tests within 10 km of its town centre. Simulated: 3,754 of the 4,454 get an estimate.
- **D. Official coverage (chosen, combined with A).** The ministry's municipal file says what share of
  households *can* get fast fixed broadband. It's a different measure from speed tests, so it goes in the
  tooltip and CSV, not in the map colours.
- B. Lower thresholds (10 tests / 3 devices): only +911 municipalities, each on two or three households. Dropped.
- C. 8 quarters instead of 4: more, but older tests. Dropped for now.

## A: estimates from nearby tests (my calls)

- Applies to municipalities **without** a measured value (fixed and mobile separately). Measured values
  are never replaced.
- Pool: every tile whose centre is **within 10 km of the municipality's town centre** (`data/places.json`
  lat/lng) **and** located in a Spanish municipality, so no Portuguese or French tiles. Same 4 quarters.
- **No fixed estimate where official ≥ 100 Mbps coverage is under 50%** (decided with the user after the
  build showed 490 such villages, e.g. Renieblas estimated at 300 Mbps from Soria city with 0% coverage).
  Mobile estimates are kept there.
- Same evidence rule as measured values (≥ 20 tests, ≥ 5 devices within one quarter), same test-weighted means.
- Map: same colour scale, drawn **paler** (lower fill opacity), with a legend line "Paler: estimated from
  speed tests within 10 km". Tooltip: "Estimated from 340 tests within 10 km (no local tests)" or
  "(only 6 local tests)".
- Headline: counts measured and estimated values together, and says how many people the estimates
  cover and how many remain unknown.

## D: official coverage (my calls)

- Source: Ministerio para la Transformación Digital y de la Función Pública (SETID), "Cobertura de banda
  ancha en España 2021–2025, municipal, provincial, CCAA y nacional"
  (`Cobertura_BA_España_2021-2025_MUN_PROV_CCAA_Nacional_datosgob_DEF.xlsx`, 6.5 MB, digital.gob.es,
  updated 16 June 2026). Latest year in the file: 2025 (situation at 30 June 2025).
- The pipeline downloads it once into `.cache/internet/` and reads it with `openpyxl` (new dependency).
- Kept per municipality, latest year only: % of households covered at **≥ 100 Mbps** and at
  **≥ 1 Gbps** (fixed), and **5G** (mobile). Exact columns to be confirmed in the file; if one is missing,
  it is left out and the rest still ship.
- Shown for **every** municipality as a tooltip line: "Official coverage 2025: ≥ 100 Mbps for 96% of
  households · 1 Gbps 94% · 5G 99%". Not used for colours or the headline.
- Credited on the page and README: "Coverage: Ministerio para la Transformación Digital y de la
  Función Pública (SETID)".

## Output changes

- `internet.json` row grows. After the 10 existing values come:
  - `f_est_down, f_est_up, f_est_lat, f_est_tests` and the same 4 for mobile (null when measured, or when the estimate lacks evidence);
  - `cov_100, cov_1g, cov_5g`, then population last.
  - `params` gains `estimate_radius_km: 10` and the coverage source and year.
- `internet.csv` gains matching columns: `fixed_est_down_mbps`, … `coverage_100mbps_pct`,
  `coverage_1gbps_pct`, `coverage_5g_pct`.

## Tests

Estimates only for municipalities without a measured value; foreign tiles excluded; 10 km radius
respected; evidence rule applied; XLSX parsing on a tiny fixture workbook; CSV columns and `.csvt` types.
