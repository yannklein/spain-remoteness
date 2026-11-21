# Internet Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For municipalities without enough local speed tests, estimate speeds from tests within 10 km. For every municipality, add the official 2025 coverage (≥100 Mbps, ≥1 Gbps, 5G).

**Architecture:** `compute_internet.py` gains a radius estimate (tile pool around each town centre, restricted to tiles located in Spain) and a coverage reader (`openpyxl` on the ministry XLSX, cached in `.cache/internet/`). The JSON row and CSV grow. `internet.ts` draws estimates paler, adds estimate and coverage lines to the tooltip, and counts estimates in the headline.

**Tech Stack:** Python 3.12 + DuckDB + openpyxl, pytest; TypeScript, MapLibre.

**Spec:** `docs/superpowers/specs/2026-11-21-internet-gaps-design.md` (extends `2026-11-21-internet-design.md`).

## Global Constraints

- **Estimate radius:** 10 km (haversine) from the municipality's town centre in `data/places.json`.
  - Only tiles whose centre locates to *some* Spanish municipality count.
  - The same 4 quarters, `MIN_TESTS = 20` and `MIN_DEVICES = 5` (busiest quarter, devices summed over tiles) apply, with test-weighted means.
  - An estimate is computed only where the measured value is `None`, for fixed and mobile separately.
- **Coverage source:**
  - File: `https://digital.gob.es/content/dam/portal-mtdfp/avance-digital/telecomunicacion-e-infraestructuras-digitales/areas_interes/banda-ancha/cobertura/documents/Cobertura_BA_Espa%C3%B1a_2021-2025_MUN_PROV_CCAA_Nacional_datosgob_DEF.xlsx`, cached at `.cache/internet/coverage_2021-2025.xlsx`.
  - Sheet `Municipio_%hogar`; key column `CMUN` (5-digit text).
  - Value columns are matched by header prefix, `Cob. 100Mbps`, `Cob. 1Gbps` and `5G\n(` (not `5G-Banda`), taking the **latest** `(junio YYYY)` year present.
  - Values are shares from 0 to 1, stored as **integer percent** (rounded, capped 0–100).
  - Credit line: "Coverage: Ministerio para la Transformación Digital y de la Función Pública (SETID)".
- **JSON row (index):**
  - 0–9 as before (measured);
  - 10–13 `f_est_down, f_est_up, f_est_lat, f_est_tests`;
  - 14–17 `m_est_down, m_est_up, m_est_lat, m_est_tests`;
  - 18–20 `cov_100, cov_1g, cov_5g`;
  - 21 `population`.
- **params:** `estimate_radius_km: 10`, `coverage: {source, year}`.
- **CSV, appended after the existing columns:** `fixed_est_down_mbps, fixed_est_up_mbps, fixed_est_latency_ms, fixed_est_tests, mobile_est_down_mbps, mobile_est_up_mbps, mobile_est_latency_ms, mobile_est_tests, coverage_100mbps_pct, coverage_1gbps_pct, coverage_5g_pct`.
- **Web:**
  - Estimated municipalities use the same colours at fill-opacity 0.45 (measured stay 0.88).
  - Legend line: "Paler: estimated from speed tests within 10 km".
  - Tooltip estimate line: "Estimated from N tests within 10 km (only K local tests)", or "(no local tests)" when K = 0.
  - Coverage line on every internet tooltip, from whichever values exist: "Official coverage 2025: ≥100 Mbps for X% of households · 1 Gbps Y% · 5G Z%".
  - Headline counts measured + estimated, then states the estimated share and the unknown share of people.

## Review Focus

1. **A municipality with a measured value** must never get an estimate, nor be drawn pale. Test in Task 1.
2. **Border villages:** Portuguese/French tiles within 10 km must not feed estimates (they don't locate to a Spanish code). Test in Task 1.
3. **The population index moved** from 10 to 21. Every TypeScript reader of the row (headline, `internetProps`, pop fallback) and `internet_csv_rows` must use the new index. Check in Task 1 (tests) and Task 2 (browser).
4. **Coverage file quirks:** codes as text vs numbers, empty cells, a municipality missing from the sheet (Usansolo?) gives `None`, not a crash. Test in Task 1.
5. **Paler estimates must be distinguishable from measured values** in the same colour bin, with the legend saying so. Browser check in Task 2.

---

### Task 1: Estimates and coverage in the pipeline

**Files:** Modify `pipeline/compute_internet.py`, `pipeline/requirements.txt` (add `openpyxl>=3.1`). Test `pipeline/tests/test_internet.py`.

**Interfaces (produces):**
- `estimate(tiles, located: dict[tuple[float, float], str | None], centres: dict[str, tuple[float, float]], need: dict[str, set[str]], km=10) -> dict[str, dict[str, list]]`
  - `need` maps type → codes lacking a measured value. Output is code → type → `[down, up, lat, tests]`, with values `None` below the minimum evidence.
  - Only codes in `need[type]` appear. Tiles with `located[(lng, lat)] is None` are skipped.
  - Uses a 0.1° grid index over the tiles.
- `read_coverage(path) -> tuple[int, dict[str, list[int | None]]]` returns the year and code → `[cov_100, cov_1g, cov_5g]`, as described in Global Constraints.
- `fetch_coverage() -> Path` downloads the XLSX once into the cache with `common.http`.
- `build_output(places, agg, quarters, est=None, coverage=None, coverage_year=None)` produces the row layout from Global Constraints.
- `internet_csv_rows` appends the new CSV columns.

- [ ] **Step 1: Write the failing tests.**
  - `test_estimate_only_where_missing`: two codes, one in `need`. Only that code gets an estimate, built from tiles within 10 km (a tile at 12 km is ignored).
  - `test_estimate_skips_foreign_tiles`: a tile with `located` → `None` inside the radius doesn't count.
  - `test_estimate_evidence_rule`: 25 tests from devices 1, 1, 2, 1 across quarters gives `None` values with `tests` kept.
  - `test_read_coverage_fixture`:
    - Build a tiny workbook in `tmp_path` with openpyxl. Use sheet `Municipio_%hogar`, `CMUN` as text and as int, headers for 2024 and 2025, a `5G-Banda 3,5GHz` column that must be ignored, and an empty cell.
    - Expect year 2025, the right percentages, `None` for the empty cell, and codes zero-padded.
  - `test_output_row_layout`: row length 22, population at index 21, estimate and coverage at the specified indexes. CSV header ends with the 11 new columns, and the `.csvt` has Real for the speeds and Integer for the tests and percentages.
- [ ] **Step 2: Run, expect failures.** `python3 -m pytest -q pipeline/tests/test_internet.py`
- [ ] **Step 3: Implement.** Wire `main()`:
  - compute `located` for all tiles (already memoised);
  - `need` from the measured output;
  - centres from `places.json`;
  - read coverage;
  - print how many municipalities got estimates and coverage.
- [ ] **Step 4: Run all tests, then the real run.** `python3 pipeline/compute_internet.py --quarters 2025-4,2026-1,2026-2,2026-3`.
  - Expect about 3,700 fixed estimates and coverage for about 8,130 municipalities.
  - Spot-check Renieblas (estimate plus coverage) and Madrid (measured, no estimate, coverage).
- [ ] **Step 5: README** (method + credit + new CSV columns). **Commit** "Estimate internet speeds from nearby tests; add official coverage".

### Task 2: Web: estimates, coverage, headline

**Files:** Modify `web/src/internet.ts`, `web/src/main.ts` (pop fallback index, fill opacity), `web/index.html` (notes).

**Interfaces:**
- `internetProps(row)` adds `fed fe u fel fet med meu mel met` (estimates), `c100 c1g c5g`, and `est_f`/`est_m` flags (1 when the value shown is an estimate).
  - Measured keys stay `fd fu fl ft fv md mu ml mt mv`.
  - The fill reads a **display key** with fallback: `coalesce(measured, estimate)`.
- `internetFill` stays a colour expression. A new `internetOpacity(mobile): ExpressionSpecification` returns 0.45 when the measured value is missing and the estimate exists, otherwise 0.88. `main.ts` applies it to `fill-opacity` in internet mode and resets to 0.88 otherwise.
- `internetTooltip` shows the measured block or the estimate block, then the coverage line.
- `internetHeadline` counts measured or estimated values, using population index 21.
- `internetLegend` gains the paler line, rendered as a half-opacity swatch.

- [ ] **Step 1: Implement and run `npm run build`.** Expected: no type errors.
- [ ] **Step 2: Browser check.**
  - The map opens on Download/fixed, with pale municipalities filling most of the grey.
  - Renieblas's tooltip shows the estimate line and coverage.
  - Madrid shows measured values and coverage.
  - The headline gives estimated and unknown shares.
  - The mobile toggle works.
  - Cities and Airports are unchanged.
- [ ] **Step 3: Commit** "Show estimated speeds and official coverage on the internet map".
