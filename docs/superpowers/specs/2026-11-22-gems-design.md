# Gems: small places that tick a remote worker's boxes

Date: 2026-11-22 · Status: approved 2026-11-22 ("A", then "go for it")

## Intent

This adds a fifth map per country that combines the four existing ones. It is for someone choosing a small place to live and work remotely from, who has their own idea of "close enough". They set the thresholds, and the map shows which small municipalities meet all of them ("gems") and which miss only one ("near misses").

## Approaches

- **A. Thresholds; only small places can be gems (chosen).** Cities stay destinations but are never gems themselves.
- B. Thresholds; any municipality can be a gem. Rejected: the green would mostly be cities and their suburbs.
- C. A weighted 0–100 score. Rejected: it is harder to read than "meets my needs or not".

## Goals

- **The map:** a `gems` mode for `es` and `fr`, built in the page from the four existing JSON files. No new data and no TravelTime calls.
- **Controls** (each criterion except size can be switched off):

  | Control | Choices | Default |
  |---|---|---|
  | Size | under 1k / 2k / 5k / 10k / 20k / 50k / any | under 20,000 inhabitants |
  | Internet | 10 / 25 / 50 / 100 / 300 Mbps download, on fixed, mobile or either; "count estimates" checkbox | ≥ 100 Mbps fixed, estimates counted |
  | City | tier, within 30 min to 3 h | a hub within 1 h |
  | Airport | tier, within 30 min to 3 h, seasonal checkbox | a European airport within 1 h 30, year-round |
  | Hospital | tier, within 15 min to 3 h | a public hospital within 45 min |

- **Classes:**
  - **gem:** all active criteria are met;
  - **near miss:** exactly one is missed;
  - **other:** everything else;
  - **too big:** over the size limit, so never a gem.
- **Meeting a criterion:**
  - **City:** a place that is itself a city of the chosen tier meets it.
  - **Hospital:** "in town" (0 min) meets it.
  - **Fails it:** unreachable within 3 h, or no internet value.
  - **Size:** an unknown population counts as small.
- **Tooltip:** every active criterion with its value and ✓/✗, e.g. "Airport 1 h 50 (limit 1 h 30) ✗".
- **Headline:** the counts of gems and near misses.
- **List:** the gems, sorted by download speed (the first 100). Clicking one zooms to it.
- **Hash:** the settings are kept in the hash (`#fr/gems?pop=20000&net=fixed:100&est=1&city=2:60&air=2:90&summer=0&hosp=2:45`, `off` for a disabled criterion), so a reload keeps them and the link can be shared.

## Non-goals

- New data: housing, climate, schools.
- A pipeline output: the filters are the user's, so nothing is precomputed. QGIS users can join the four CSVs on `code`.

## Anti-goals

- A big city or suburb shown as a gem.
- Missing data read as "fine".
- The map and the counts disagreeing.

## My calls

- **One judging function:** a single function, `judge()`, decides each class. The map colours through feature-state set from it, so the map, counts, list and tooltip can't disagree.
- **Colours:**
  - gem: gold `#d99a00`;
  - near miss: pale gold `#f2d27e`;
  - other: light grey `#f1f0ec`;
  - too big: the urban grey `#b9b7b1`.
- **Tests:** vitest, a new dev dependency, tests the pure logic in `web/src/gems.ts`.
