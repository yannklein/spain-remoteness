import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import compute_internet as ci  # noqa: E402
from common import PLACES_FILE, load_json, write_csv  # noqa: E402

P = "parquet/performance/type={k}/year={y}/quarter={q}/"


def key(kind, y, q, file=True):
    base = P.format(k=kind, y=y, q=q)
    return base + f"{y}-{(q - 1) * 3 + 1:02d}-01_performance_{kind}_tiles.parquet" if file else base


def test_latest_quarters_needs_both_types():
    keys = []
    for y, q in [(2025, 2), (2025, 3), (2025, 4), (2026, 1), (2026, 2)]:
        keys += [key("fixed", y, q), key("mobile", y, q), key("fixed", y, q, file=False)]
    keys += [key("fixed", 2026, 3), key("mobile", 2026, 3, file=False)]   # mobile not out yet
    assert ci.latest_quarters(keys) == [(2025, 3), (2025, 4), (2026, 1), (2026, 2)]


def tile(d, u, lat, tests, devices):
    return (0.0, 0.0, d, u, lat, tests, devices)


def test_test_weighted_mean():
    tiles = {"fixed": [tile(100_000, 10_000, 20, 10, 3), tile(20_000, 2_000, 60, 30, 4)], "mobile": []}
    agg = ci.aggregate(tiles, lambda lng, lat: "X")
    assert agg["X"]["fixed"] == [40.0, 4.0, 50, 40, 7]
    assert "mobile" not in agg["X"]


def test_minimum_evidence():
    def one(tests, devices):
        return ci.aggregate({"fixed": [tile(50_000, 5_000, 30, tests, devices)]}, lambda a, b: "X")["X"]["fixed"]
    assert one(40, 2) == [None, None, None, 40, 2]          # one household testing a lot
    assert one(19, 10) == [None, None, None, 19, 10]
    assert one(20, 5) == [50.0, 5.0, 30, 20, 5]


def test_unlocated_tiles_dropped():
    agg = ci.aggregate({"fixed": [tile(1, 1, 1, 100, 100)]}, lambda lng, lat: None)
    assert agg == {}


def test_output_has_every_municipality():
    places = load_json(PLACES_FILE)
    out = ci.build_output(places, {}, [(2025, 4), (2026, 1)])
    assert len(out["m"]) == 8132
    pop = places["municipalities"][0]["pop"]
    assert out["m"][places["municipalities"][0]["code"]] == [None, None, None, 0, 0, None, None, None, 0, 0, pop]
    assert out["params"]["quarters"] == ["2025-Q4", "2026-Q1"]
    assert out["params"]["min_tests"] == 20 and out["params"]["min_devices"] == 5
    assert "CC BY-NC-SA 4.0" in out["params"]["licence"]


def test_internet_csv(tmp_path):
    places = load_json(PLACES_FILE)
    munis = places["municipalities"]
    agg = {munis[0]["code"]: {"fixed": [96.0, 18.4, 31, 120, 40]}}
    out = ci.build_output(places, agg, [(2026, 1)])
    header, rows = ci.internet_csv_rows(out, munis)
    assert header == ["code", "name", "province", "population",
                      "fixed_down_mbps", "fixed_up_mbps", "fixed_latency_ms", "fixed_tests", "fixed_devices",
                      "mobile_down_mbps", "mobile_up_mbps", "mobile_latency_ms", "mobile_tests", "mobile_devices"]
    assert len(rows) == 8132
    assert rows[0][4:9] == [96.0, 18.4, 31, 120, 40] and rows[0][9:12] == [None, None, None]
    p = tmp_path / "internet.csv"
    write_csv(p, header, rows)
    line = p.read_text(encoding="utf-8").splitlines()[1]
    assert line.startswith("01001,") and ",96.0,18.4,31,120,40,,,,0,0" in line
    types = p.with_suffix(".csvt").read_text().strip().split(",")
    assert types[0] == '"String"' and types[header.index("fixed_tests")] == '"Integer"'
    assert types[header.index("fixed_down_mbps")] == '"Real"'          # decimals must survive in QGIS


def test_fetch_quarter_uses_cache(monkeypatch, tmp_path):
    import gzip
    import json
    monkeypatch.setattr(ci, "CACHE", tmp_path)
    tiles = [[-3.7, 40.4, 100000, 10000, 20, 50, 9]]
    with gzip.open(tmp_path / "fixed-2026-Q1.json.gz", "wt") as f:
        json.dump(tiles, f)

    class NoDuck:
        def __getattr__(self, name):
            raise AssertionError("DuckDB must not be used when the cache exists")

    monkeypatch.setitem(sys.modules, "duckdb", NoDuck())
    assert ci.fetch_quarter("fixed", 2026, 1) == [tuple(t) for t in tiles]
