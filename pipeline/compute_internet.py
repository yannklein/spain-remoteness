"""Measured internet speed per municipality, from Ookla open data.

Source: Speedtest by Ookla Global Fixed and Mobile Network Performance Maps
(s3://ookla-open-data, CC BY-NC-SA 4.0): zoom-16 tiles (~600 m) with average
download/upload/latency and test/device counts, one Parquet file per quarter
and type. The last 4 quarters are pooled; each tile goes to the municipality
containing its centre; values are test-weighted means and are only published
with enough evidence (MIN_TESTS tests from MIN_DEVICES devices).

Usage: python pipeline/compute_internet.py [--quarters 2025-4,2026-1,...]
"""

import argparse
import gzip
import json
import math
import re
import urllib.parse
from datetime import datetime, timezone

from common import (PLACES_FILE, ROOT, dump_json, haversine_km, http, load_json, write_csv)
from geo import MuniIndex, load_municipalities

INTERNET_OUTPUT_FILE = ROOT / "web" / "public" / "data" / "internet.json"
INTERNET_CSV = ROOT / "web" / "public" / "data" / "internet.csv"
CACHE = ROOT / ".cache" / "internet"
BUCKET = "https://ookla-open-data.s3.amazonaws.com/"
PREFIX = "parquet/performance/"
BBOX = (-18.5, 27.4, 4.5, 44.0)
ESTIMATE_KM = 10
COVERAGE_URL = ("https://digital.gob.es/content/dam/portal-mtdfp/avance-digital/telecomunicacion-e-infraestructuras-digitales/"
                "areas_interes/banda-ancha/cobertura/documents/"
                "Cobertura_BA_Espa%C3%B1a_2021-2025_MUN_PROV_CCAA_Nacional_datosgob_DEF.xlsx")
COVERAGE_SOURCE = "Ministerio para la Transformación Digital y de la Función Pública (SETID)"   # lng/lat box around Spain incl. Canarias; point-in-polygon does the rest

MIN_TESTS = 20
MIN_DEVICES = 5
TYPES = ("fixed", "mobile")
SOURCE = "Speedtest® by Ookla® Global Fixed and Mobile Network Performance Maps"
LICENCE = ("Speedtest® by Ookla® Global Fixed and Mobile Network Performance Maps, CC BY-NC-SA 4.0. "
           "The internet data derived here is shared under the same licence.")

_KEY = re.compile(r"type=(fixed|mobile)/year=(\d{4})/quarter=(\d)/[^/]+\.parquet$")


def latest_quarters(keys, n=4):
    """The n most recent (year, quarter) with a Parquet file for both fixed and mobile, ascending."""
    seen = {}
    for k in keys:
        m = _KEY.search(k)
        if m:
            seen.setdefault((int(m.group(2)), int(m.group(3))), set()).add(m.group(1))
    complete = sorted(q for q, kinds in seen.items() if kinds >= set(TYPES))
    return complete[-n:]


def aggregate(tiles, locate):
    """{type: [[Tile] per quarter]} -> {code: {type: [down_mbps, up_mbps, lat_ms, tests, devices]}}.

    Tile = (lng, lat, d_kbps, u_kbps, lat_ms, tests, devices). Speeds are
    test-weighted means over all tiles and quarters. `devices` is the most
    devices seen in any one quarter (summed over the municipality's tiles):
    Ookla counts devices per tile and quarter, so summing over quarters would
    count one household four times. Values are None below the minimum evidence.
    """
    sums = {}
    for kind, quarters in tiles.items():
        for qi, tl in enumerate(quarters):
            for lng, lat, d, u, lt, tests, devices in tl:
                code = locate(lng, lat)
                if code is None or not tests:
                    continue
                s = sums.setdefault(code, {}).setdefault(kind, [0, 0, 0, 0, {}])
                s[0] += d * tests
                s[1] += u * tests
                s[2] += lt * tests
                s[3] += tests
                s[4][qi] = s[4].get(qi, 0) + devices
    out = {}
    for code, kinds in sums.items():
        for kind, (d, u, lt, tests, per_q) in kinds.items():
            devices = max(per_q.values())
            if tests >= MIN_TESTS and devices >= MIN_DEVICES:
                row = [round(d / tests / 1000, 1), round(u / tests / 1000, 1), round(lt / tests), tests, devices]
            else:
                row = [None, None, None, tests, devices]
            out.setdefault(code, {})[kind] = row
    return out


def _evidence(d, u, lt, tests, devices):
    if tests >= MIN_TESTS and devices >= MIN_DEVICES:
        return [round(d / tests / 1000, 1), round(u / tests / 1000, 1), round(lt / tests)]
    return [None, None, None]


def estimate(tiles, located, centres, need, km=ESTIMATE_KM):
    """Speeds for municipalities without a measured value, from tiles within `km` of their town centre.

    Only tiles that locate to a Spanish municipality count (no foreign networks).
    Same evidence rule and test-weighted means as measured values.
    -> {code: {type: [down, up, lat, tests]}}
    """
    out = {}
    cell = 0.1
    for kind, quarters in tiles.items():
        codes = need.get(kind, set())
        if not codes:
            continue
        grid = {}
        for qi, tl in enumerate(quarters):
            for t in tl:
                if located.get((t[0], t[1])) is None or not t[5]:
                    continue
                grid.setdefault((math.floor(t[0] / cell), math.floor(t[1] / cell)), []).append((qi, t))
        for code in codes:
            if code not in centres:
                continue
            lng, lat = centres[code]
            rx = math.ceil(km / (111.32 * math.cos(math.radians(lat)) * cell)) + 1
            ry = math.ceil(km / (111.32 * cell)) + 1
            cx, cy = math.floor(lng / cell), math.floor(lat / cell)
            d = u = lt = tests = 0
            per_q = {}
            for gx in range(cx - rx, cx + rx + 1):
                for gy in range(cy - ry, cy + ry + 1):
                    for qi, t in grid.get((gx, gy), ()):
                        if haversine_km(lat, lng, t[1], t[0]) > km:
                            continue
                        d += t[2] * t[5]
                        u += t[3] * t[5]
                        lt += t[4] * t[5]
                        tests += t[5]
                        per_q[qi] = per_q.get(qi, 0) + t[6]
            if tests:
                devices = max(per_q.values())
                out.setdefault(code, {})[kind] = _evidence(d, u, lt, tests, devices) + [tests]
    return out


_COV = {"cov_100": re.compile(r"^Cob\. 100Mbps"), "cov_1g": re.compile(r"^Cob\. 1Gbps"),
        "cov_5g": re.compile(r"^5G\s*\(")}
_YEAR = re.compile(r"\(junio (\d{4})\)")


def read_coverage(path):
    """Official % of households covered, latest year: -> (year, {code: [cov_100, cov_1g, cov_5g]})."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb["Municipio_%hogar"]
    rows = ws.iter_rows(values_only=True)
    header = [str(h).strip() if h is not None else "" for h in next(rows)]
    year = max(int(m.group(1)) for h in header for m in [_YEAR.search(h)] if m)
    cols = {}
    for key, rx in _COV.items():
        for i, h in enumerate(header):
            if rx.search(h) and f"(junio {year})" in h:
                cols[key] = i
    code_i = header.index("CMUN")
    out = {}
    for r in rows:
        if r[code_i] is None:
            continue
        code = str(r[code_i]).strip().split(".")[0].zfill(5)
        vals = []
        for key in _COV:
            v = r[cols[key]] if key in cols else None
            vals.append(None if not isinstance(v, (int, float)) else max(0, min(100, round(v * 100))))
        out[code] = vals
    wb.close()
    return year, out


def fetch_coverage():
    f = CACHE / "coverage_2021-2025.xlsx"
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_bytes(http(COVERAGE_URL, timeout=120))
        tmp.rename(f)
    return f


def build_output(places, agg, quarters, est=None, coverage=None, coverage_year=None):
    empty = [None, None, None, 0, 0]
    est, coverage = est or {}, coverage or {}
    m = {}
    for mu in places["municipalities"]:
        c = mu["code"]
        a = agg.get(c, {})
        row = list(a.get("fixed", empty)) + list(a.get("mobile", empty))
        e = est.get(c, {})
        for i, kind in enumerate(("fixed", "mobile")):
            measured = row[i * 5] is not None
            row += [None] * 4 if measured else list(e.get(kind, [None, None, None, None]))
        row += list(coverage.get(c, [None, None, None])) + [mu.get("pop")]
        m[c] = row
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "params": {
            "source": SOURCE,
            "licence": LICENCE,
            "quarters": [f"{y}-Q{q}" for y, q in quarters],
            "min_tests": MIN_TESTS,
            "min_devices": MIN_DEVICES,
            "estimate_radius_km": ESTIMATE_KM,
            "coverage": {"source": COVERAGE_SOURCE, "year": coverage_year},
            "population_year": places["meta"].get("population_year"),
            "notes": [],
        },
        # code -> [f_down, f_up, f_lat, f_tests, f_devices, m_down, m_up, m_lat, m_tests, m_devices,
        #          f_est_down, f_est_up, f_est_lat, f_est_tests, m_est_down, m_est_up, m_est_lat, m_est_tests,
        #          cov_100, cov_1g, cov_5g, population]
        "m": m,
    }


def internet_csv_rows(output, munis):
    header = ["code", "name", "province", "population"]
    for kind in TYPES:
        header += [f"{kind}_down_mbps", f"{kind}_up_mbps", f"{kind}_latency_ms", f"{kind}_tests", f"{kind}_devices"]
    for kind in TYPES:
        header += [f"{kind}_est_down_mbps", f"{kind}_est_up_mbps", f"{kind}_est_latency_ms", f"{kind}_est_tests"]
    header += ["coverage_100mbps_pct", "coverage_1gbps_pct", "coverage_5g_pct"]
    rows = [[m["code"], m["name"], m.get("province"), m.get("pop")] + output["m"][m["code"]][:21] for m in munis]
    return header, rows


def list_keys():
    """All Parquet keys under the performance prefix (anonymous S3 listing)."""
    keys, token = [], None
    while True:
        q = {"list-type": "2", "prefix": PREFIX}
        if token:
            q["continuation-token"] = token
        xml = http(BUCKET + "?" + urllib.parse.urlencode(q), timeout=60).decode()
        keys += re.findall(r"<Key>([^<]+)</Key>", xml)
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", xml)
        if not m:
            return keys
        token = m.group(1)


def parquet_url(kind, year, q):
    return (f"s3://ookla-open-data/{PREFIX}type={kind}/year={year}/quarter={q}/"
            f"{year}-{(q - 1) * 3 + 1:02d}-01_performance_{kind}_tiles.parquet")


def fetch_quarter(kind, year, q):
    """Tiles inside BBOX for one quarter, cached as gzipped JSON in .cache/internet/."""
    f = CACHE / f"{kind}-{year}-Q{q}.json.gz"
    if f.exists():
        with gzip.open(f, "rt") as fh:
            return [tuple(t) for t in json.load(fh)]
    import duckdb  # only needed when downloading
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
    x0, y0, x1, y1 = BBOX
    rows = con.execute(
        f"SELECT tile_x, tile_y, avg_d_kbps, avg_u_kbps, avg_lat_ms, tests, devices "
        f"FROM read_parquet('{parquet_url(kind, year, q)}') "
        f"WHERE tile_x BETWEEN {x0} AND {x1} AND tile_y BETWEEN {y0} AND {y1}").fetchall()
    CACHE.mkdir(parents=True, exist_ok=True)
    with gzip.open(f, "wt") as fh:
        json.dump(rows, fh)
    return [tuple(r) for r in rows]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quarters", help="comma-separated YEAR-Q list, e.g. 2025-4,2026-1 (default: latest 4)")
    args = ap.parse_args()

    if args.quarters:
        quarters = [tuple(int(v) for v in s.split("-")) for s in args.quarters.split(",")]
    else:
        quarters = latest_quarters(list_keys())
    print("Quarters:", ", ".join(f"{y}-Q{q}" for y, q in quarters))

    tiles = {kind: [] for kind in TYPES}
    for kind in TYPES:
        for y, q in quarters:
            got = fetch_quarter(kind, y, q)
            print(f"  {kind} {y}-Q{q}: {len(got)} tiles in the box")
            tiles[kind].append(got)

    index = MuniIndex(load_municipalities())
    located = {}

    def locate(lng, lat):
        k = (lng, lat)
        if k not in located:
            located[k] = index.locate(lng, lat)
        return located[k]

    agg = aggregate(tiles, locate)
    places = load_json(PLACES_FILE)
    measured = build_output(places, agg, quarters)
    need = {kind: {c for c, r in measured["m"].items() if r[i * 5] is None} for i, kind in enumerate(TYPES)}
    centres = {m["code"]: (m["lng"], m["lat"]) for m in places["municipalities"]}
    est = estimate(tiles, located, centres, need)
    cov_year, coverage = read_coverage(fetch_coverage())
    output = build_output(places, agg, quarters, est=est, coverage=coverage, coverage_year=cov_year)
    dump_json(output, INTERNET_OUTPUT_FILE, compact=True)
    write_csv(INTERNET_CSV, *internet_csv_rows(output, places["municipalities"]))

    inside = sum(1 for v in located.values() if v)
    print(f"{inside} of {len(located)} distinct tiles located in a municipality")
    for i, kind in enumerate(TYPES):
        n = sum(1 for r in output["m"].values() if r[i * 5] is not None)
        print(f"  {kind}: {n} municipalities with enough tests")
    for i, kind in enumerate(TYPES):
        n = sum(1 for r in output["m"].values() if r[10 + i * 4] is not None)
        print(f"  {kind}: {n} more municipalities with an estimate from tests within {ESTIMATE_KM} km")
    print(f"  official coverage {cov_year}: {sum(1 for r in output['m'].values() if r[18] is not None)} municipalities")
    print(f"Wrote {INTERNET_OUTPUT_FILE} and {INTERNET_CSV.name}")


if __name__ == "__main__":
    main()
