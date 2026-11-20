"""Measured internet speed per municipality, from Ookla open data.

Source: Speedtest by Ookla Global Fixed and Mobile Network Performance Maps
(s3://ookla-open-data, CC BY-NC-SA 4.0): zoom-16 tiles (~600 m) with average
download/upload/latency and test/device counts, one Parquet file per quarter
and type. The last 4 quarters are pooled; each tile goes to the municipality
containing its centre; values are test-weighted means and are only published
with enough evidence (MIN_TESTS tests from MIN_DEVICES devices).

Usage: python pipeline/compute_internet.py [--quarters 2025-4,2026-1,...]
"""

import re
from datetime import datetime, timezone

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
    """{type: [Tile]} -> {code: {type: [down_mbps, up_mbps, lat_ms, tests, devices]}}.

    Tile = (lng, lat, d_kbps, u_kbps, lat_ms, tests, devices). Test-weighted
    means; values None below the minimum evidence; counts always kept.
    """
    sums = {}
    for kind, tl in tiles.items():
        for lng, lat, d, u, lt, tests, devices in tl:
            code = locate(lng, lat)
            if code is None or not tests:
                continue
            s = sums.setdefault(code, {}).setdefault(kind, [0, 0, 0, 0, 0])
            s[0] += d * tests
            s[1] += u * tests
            s[2] += lt * tests
            s[3] += tests
            s[4] += devices
    out = {}
    for code, kinds in sums.items():
        for kind, (d, u, lt, tests, devices) in kinds.items():
            if tests >= MIN_TESTS and devices >= MIN_DEVICES:
                row = [round(d / tests / 1000, 1), round(u / tests / 1000, 1), round(lt / tests), tests, devices]
            else:
                row = [None, None, None, tests, devices]
            out.setdefault(code, {})[kind] = row
    return out


def build_output(places, agg, quarters):
    empty = [None, None, None, 0, 0]
    m = {}
    for mu in places["municipalities"]:
        a = agg.get(mu["code"], {})
        m[mu["code"]] = list(a.get("fixed", empty)) + list(a.get("mobile", empty)) + [mu.get("pop")]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "params": {
            "source": SOURCE,
            "licence": LICENCE,
            "quarters": [f"{y}-Q{q}" for y, q in quarters],
            "min_tests": MIN_TESTS,
            "min_devices": MIN_DEVICES,
            "population_year": places["meta"].get("population_year"),
            "notes": [],
        },
        # code -> [f_down, f_up, f_lat, f_tests, f_devices, m_down, m_up, m_lat, m_tests, m_devices, population]
        "m": m,
    }


def internet_csv_rows(output, munis):
    header = ["code", "name", "province", "population"]
    for kind in TYPES:
        header += [f"{kind}_down_mbps", f"{kind}_up_mbps", f"{kind}_latency_ms", f"{kind}_tests", f"{kind}_devices"]
    rows = [[m["code"], m["name"], m.get("province"), m.get("pop")] + output["m"][m["code"]][:10] for m in munis]
    return header, rows
