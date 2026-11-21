# Hospitals Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Public transport time from each municipality to the nearest major / public / any general hospital, as JSON + CSV and a fourth "Hospitals" mode.

**Architecture:**
- `pipeline/hospitals.py` reads the Catálogo Nacional de Hospitales and assigns tiers.
- `pipeline/place_hospitals.py` matches hospitals to OpenStreetMap and picks arrival points, writing `data/hospitals.json`.
- `pipeline/compute_hospitals.py` reuses `compute_times.compute_all` (like airports) and writes `hospitals.{json,csv}`.
- `web/src/hospitals.ts` provides the new mode.

**Tech Stack:** Python 3.12 (openpyxl, stdlib), TravelTime API, pytest; TypeScript, MapLibre.

**Spec:** `docs/superpowers/specs/2026-11-21-hospitals-design.md`

## Global Constraints

- **Catalogue:** `https://www.sanidad.gob.es/estadEstudios/estadisticas/sisInfSanSNS/ofertaRecursos/hospitales/docs/CNH_2025.xlsx`, cached at `.cache/hospitals/CNH_2025.xlsx`.
  - Sheets: `DIRECTORIO DE HOSPITALES` (CODCNH, Nombre Centro, Dirección, Cód. Municipio as 6 digits, where the first 5 are the INE code; CAMAS, Cód. Clase de Centro, Cód. Dep. Funcional, Código Postal) and `ESTRUCTURA FUNCIONAL` (CODCNH, Concierto, CODIDCOM, HEM).
  - `DC` values are resolved through the complex row `CODIDCOM`.
- **Tiers:**
  - 3 = class C11.
  - 2 = C11 and public, where public means dependency in {1…8} or concierto ∈ {"Red de utilización pública (RUP)", "Concierto sustitutorio"}.
  - 1 = tier 2 and HEM > 0.
- **Arrival point:**
  - The nearest public transport stop (`highway=bus_stop`, `public_transport=platform|stop_position`, `railway=station|halt|tram_stop`, `station=subway`) within **400 m** of the matched OSM hospital centre.
  - Otherwise an `entrance=*` node within the hospital's way/relation.
  - Otherwise the OSM centre.
  - Unmatched hospitals: Nominatim (`https://nominatim.openstreetmap.org/search`, 1 request/s, `common.USER_AGENT`), then the same stop rule.
- **TravelTime:** the same parameters as airports. Ids `HOS:<CODCNH>`; zone from the municipality in `places.json`; cache `.cache/hospitals/<cache_dir(client).name>/`.
- **Outputs:** as in the spec. Headline threshold **30 min**. Mode hash `#hospitals`. Buttons "Major | Public | Any"; the default is Public (tier 2).

## Review Focus

1. **Catalan public-network hospitals listed as private** (Figueres, Olot, Palamós) must be tier 2. Test in Task 1.
2. **Hospitals in a complex** (`DC` values) get the complex's HEM and concierto. Test in Task 1.
3. **A hospital whose stop lies across a river or road** can still fail to attach. `reach` = 0 must be reported in notes, not silently ignored. Test in Task 3.
4. **Island and Ceuta/Melilla hospitals** take their zone from the municipality, so Ceuta reaches Ceuta's hospital. Test in Task 3.
5. **Name matching false positives** ("Hospital San Juan de Dios" exists in many cities) must be avoided by matching within the same municipality first and requiring the fallback within 2 km of the geocoded address. Test in Task 2.

---

### Task 1: Catalogue reader and tiers
**Files:** Create `pipeline/hospitals.py`, `pipeline/tests/test_hospitals.py`.
**Produces:**
- `read_catalogue(path) -> list[dict]` with keys `codcnh, name, address, postcode, muni (5-digit), beds, cls, public (bool), cath_lab (bool), tier (1|2|3|None)`.
- `fetch_catalogue() -> Path` downloads into the cache once.

- [ ] **Step 1:** Write fixture-workbook tests:
  - public by dependency;
  - public by RUP, with private dependency (Figueres-like);
  - public by sustitutorio;
  - partial concierto with private dependency gives tier 3;
  - `DC` resolved via the complex for HEM and concierto;
  - C12/C13/C14 give tier None;
  - the 6-digit municipality code becomes 5 digits.
- [ ] **Step 2:** Run the tests and watch them fail.
- [ ] **Step 3:** Implement and run all tests.
- [ ] **Step 4:** Run on the real file and print the counts per tier. Expect about 140 / 350 / 549 cumulative. Check that Hospital de Figueres is tier 2.
- [ ] **Step 5:** Commit.

### Task 2: Placing hospitals
**Files:** Create `pipeline/place_hospitals.py`; add tests to `pipeline/tests/test_hospitals.py`.
**Produces:**
- `normalise(name) -> str`: lowercase, accents and punctuation removed; drops generic words (hospital, clinica, clínic, universitario, general, de, del, la, el, y, i…).
- `match(hosp, osm_hospitals, muni_of) -> osm | None`: same municipality, the best token overlap ≥ 0.5, else None.
- `pick_point(osm_h, stops, entrances) -> (lat, lng, source)`.
- CLI that writes `data/hospitals.json`: a list of the catalogue dicts plus `lat, lng, point_source ("stop"|"entrance"|"osm"|"nominatim+stop"|"nominatim"), osm_id, stop_name`. It prints how many hospitals were placed each way.

- [ ] **Step 1:** Write tests:
  - normalisation;
  - a match within the same municipality;
  - no match across municipalities with the same name ("San Juan de Dios" in Pamplona vs Córdoba);
  - stop within 400 m chosen over the entrance;
  - a stop at 500 m ignored.
- [ ] **Step 2:** Run the tests and watch them fail. Implement. Run all tests.
- [ ] **Step 3:** Real run: one Overpass query (hospitals as `out center tags;` and the stops around them), with Nominatim for the unmatched. Report the matched share; expect ≥ 85% matched by OSM.
- [ ] **Step 4:** Commit with `data/hospitals.json`.

### Task 3: Travel times
**Files:** Create `pipeline/compute_hospitals.py`; add tests.
**Produces:**
- `destinations(placed, places) -> list[dict]` with `code "HOS:<id>"` and `zone` from the municipality.
- `aggregate_hospitals(munis, hospitals, results) -> (sorted hospitals, rows)` with rows `[t1,h1,t2,h2,t3,h3]`.
- `build_output(...)`, which adds `reach` and a notes entry listing hospitals nobody reaches.
- `hospitals_csv_rows(...)`.
- CLI with `--limit`, `--only`, `--no-cache`; partial runs write nothing.

- [ ] **Step 1:** Tests with `fake_post`:
  - nested tiers;
  - a Ceuta hospital reached from Ceuta and not from Algeciras;
  - a `reach` 0 hospital is noted;
  - CSV layout;
  - a partial run writes nothing.
- [ ] **Step 2:** Run the tests and watch them fail. Implement. Run all tests.
- [ ] **Step 3:** Real run with the user's TravelTime keys in the shell. Spot-check Estella → García Orcoyen, a Soria village, and Ceuta. List any `reach` 0 hospitals and fix their points in `data/hospitals.json` the same way as airports, recording a ruling.
- [ ] **Step 4:** Update the README (section + QGIS + sources) and commit with the data.

### Task 4: Web: hospitals mode
**Files:** Create `web/src/hospitals.ts`; modify `web/src/main.ts`, `web/index.html`, `web/src/style.css` (4 mode buttons).
- The 4th mode reuses the minutes colour scale, markers and tooltip pattern from the airports mode (`hospitals.ts` mirrors `airports.ts`: load, props `h1..h3`/`ha1..ha3`, markers, counts, tooltip, headline at 30 min).
- [ ] **Step 1:** Implement, then `npm run build`.
- [ ] **Step 2:** Browser check:
  - `#hospitals` opens on Public;
  - the three tiers recolour the map, with counts;
  - the tooltip names the hospital and its municipality;
  - the headline reads correctly;
  - the other three modes still work.
- [ ] **Step 3:** Commit.
