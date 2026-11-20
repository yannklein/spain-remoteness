# Internet map: design

Date: 2026-11-21 · Status: approved 2026-11-21

## Intent

A third dataset next to Cities and Airports. It answers **"could I work remotely from here?"**
with the internet speeds people actually measure in each municipality. As before, everything the
pipeline produces is a JSON + CSV per municipality, reusable in QGIS.

## Goals

- Per municipality: measured download, upload and latency, for fixed broadband and for mobile,
  with the number of tests behind each figure.
- A third "Internet" view on the existing page, switchable like Cities / Airports.
- Honest gaps: a municipality with too few tests says so; it doesn't get a made-up value.

## Non-goals

- Official coverage figures ("can fibre be installed here"). That source was considered and set aside (see Approaches).
- A combined "remote-work score".
- Changing the Cities or Airports datasets.

## Anti-goals

- Showing a village as slow or fast on the strength of one or two speed tests.

## Approaches considered

- **A. Official coverage (% households that can get ≥100 Mbps / gigabit), measured speeds as detail.**
  Answers "can I get fibre", but the latest municipal download is June 2024 and most places read ~100%.
- **B. Ookla measured speeds (chosen by the user).** Measured performance and recent data (quarterly,
  latest ~2026). Sparse in small villages; licence CC BY-NC-SA 4.0. The user accepted the
  non-commercial licence and prefers this for precision and freshness.
- C. A composite score, dropped: it hides judgement calls and can't be checked against a source.

## Data source (decided)

[Speedtest by Ookla Global Fixed and Mobile Network Performance Maps](https://registry.opendata.aws/speedtest-global-performance/):
public S3 bucket `ookla-open-data`, Parquet, one file per quarter and per type (fixed, mobile),
zoom-16 web-Mercator tiles (~600 m in Spain). Per tile: `avg_d_kbps`, `avg_u_kbps`, `avg_lat_ms`,
`tests`, `devices`, tile geometry. No account needed.

Licence: CC BY-NC-SA 4.0. The page and README credit "Speedtest® by Ookla® Global Fixed and Mobile
Network Performance Maps" and state that the derived internet data is under the same licence.

## Method (my calls)

- **Period:** the **last 4 published quarters**, pooled to get enough tests in small places. The
  pipeline picks the latest available quarters itself and records them in the output.
- **Tile → municipality:** a tile belongs to the municipality containing its centre (point in polygon
  against the same IGN boundaries the map uses, `web/public/data/municipalities.topo.json`).
  Tiles at sea or outside Spain are dropped.
- **Aggregation:** per municipality and type, the **test-weighted mean** of the tile averages
  (Ookla's own recommended way to aggregate tiles), over all 4 quarters.
  Download/upload in Mbps (1 decimal), latency in ms (integer).
- **Minimum evidence:** a value is published only with **≥ 20 tests from ≥ 5 devices** over the
  period. Below that: no value, shown as "not enough speed tests". The counts are always published.
- **Tooling:** DuckDB (one new Python dependency, `pip install duckdb`) reads the Parquet files
  straight from S3 with a bounding-box filter on Spain, so nothing global is downloaded.
  The point-in-polygon step is plain Python on the TopoJSON. Raw per-quarter extracts for Spain are
  cached in `.cache/internet/`.
- Runs locally like the others: `python3 pipeline/compute_internet.py`. No API key.

## Output

`web/public/data/internet.json`:

```jsonc
{
  "generated_at": "...",
  "params": { "source": "Speedtest by Ookla ...", "licence": "CC BY-NC-SA 4.0",
              "quarters": ["2025-Q3", "2025-Q4", "2026-Q1", "2026-Q2"],
              "min_tests": 20, "min_devices": 5, "notes": [] },
  // code -> [f_down, f_up, f_lat, f_tests, f_devices, m_down, m_up, m_lat, m_tests, m_devices, population]
  // down/up Mbps, lat ms; null when below the minimum evidence
  "m": { "01001": [...] }
}
```

`web/public/data/internet.csv` (+ `.csvt`): `code,name,province,population,fixed_down_mbps,
fixed_up_mbps,fixed_latency_ms,fixed_tests,fixed_devices,mobile_down_mbps,mobile_up_mbps,
mobile_latency_ms,mobile_tests,mobile_devices`. Empty cell = not enough tests.

## Web page

- The mode switch becomes `Cities | Airports | Internet`, with hash `#internet`.
- **Title:** "How good is the internet in rural Spain?". **Lead:** "Average measured … speed per municipality, from Speedtest by Ookla, last 4 quarters."
- The three buttons are **Download | Upload | Latency**. Default: **Upload**, because video calls and sending work are what usually break first on a rural line. Download is the familiar figure, one click away.
- **Checkbox "Mobile instead of fixed broadband"**, off by default.
- **Colour bins**, sequential like the other maps, light = good for remote work, dark = poor:
  - Download (Mbps): ≥ 300 · 100–300 · 50–100 · 25–50 · 10–25 · < 10
  - Upload (Mbps): ≥ 100 · 50–100 · 20–50 · 10–20 · 3–10 · < 3
  - Latency (ms): < 20 · 20–35 · 35–50 · 50–80 · 80–120 · ≥ 120
  - Plus a neutral grey for "not enough speed tests".
- **Tooltip:** download / upload / latency for the selected type, then "from N tests on M devices". Below the minimum: "not enough speed tests (N)".
- **Headline:** "**X%** of people live where measured fixed upload is under **10 Mbps**", population-weighted, counting only municipalities with enough tests (the share without data is stated alongside). Thresholds follow the selected metric: download < 25 Mbps, upload < 10 Mbps, latency > 80 ms.
- **"How this map is made":** source, period, aggregation, minimum evidence, licence, caveats.

## Known limitations (stated on the page / README)

- Speed tests measure the plans people have, not what could be installed. A village with fibre whose residents keep cheap plans reads slower than it could be.
- Small municipalities often have too few tests and stay grey.
- Tiles are assigned by their centre point, so a tile straddling a border counts for one municipality.

## Tests

Pipeline (pytest, no network): point-in-polygon on a small TopoJSON fixture; test-weighted mean; the
min-tests/min-devices rule; tiles outside Spain dropped; CSV empty cells, codes as text, `.csvt`;
quarter selection picks the latest 4 from a list of available keys.

## Left to the builder

- The exact S3 paths/partitioning (discover them from the bucket listing) and the DuckDB query.
- Marker-free map styling, legend copy, exact wording of help texts.
- README section mirroring the other two.
