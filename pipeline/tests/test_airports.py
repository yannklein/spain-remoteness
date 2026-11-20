import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import airports  # noqa: E402
from common import PLACES_FILE, load_json  # noqa: E402

BY = {a[0]: a for a in airports.AIRPORTS}
ISLANDS = {m["island"] for m in load_json(PLACES_FILE)["municipalities"] if m.get("island")}


def test_iata_codes_unique_and_well_formed():
    codes = [a[0] for a in airports.AIRPORTS]
    assert len(codes) == len(set(codes))
    assert all(re.fullmatch(r"[A-Z]{3}", c) for c in codes)


def test_tiers_are_consistent():
    for iata, _, _, _, _, ty, ts, _, _ in airports.AIRPORTS:
        assert ty in (None, 1, 2, 3) and ts in (None, 1, 2, 3), iata
        if ty is not None:
            assert ts is not None and ts <= ty, iata


def test_zones_are_known():
    for a in airports.AIRPORTS:
        z = a[7]
        assert z in ("mainland", "melilla") or (z.startswith("island:") and z[7:] in ISLANDS), a[0]


def test_coordinates_are_plausible():
    for iata, _, country, lat, lng, *_ in airports.AIRPORTS:
        assert country in ("ES", "PT", "FR", "GI"), iata
        if country == "ES":
            assert 27.5 <= lat <= 44.5 and -18.5 <= lng <= 4.5, iata
        else:  # near the border: inside a box ~400 km around the peninsula
            assert 35.0 <= lat <= 47.0 and -10.5 <= lng <= 6.0, iata


def test_excluded_airports_say_why():
    for a in airports.AIRPORTS:
        if a[5] is None and a[6] is None:
            assert a[8].strip(), a[0]


def test_pinned_airports():
    for code in ("MAD", "BCN", "LIS", "OPO"):
        assert BY[code][5] == 1, code
    for code in ("TEV", "HSK"):
        assert BY[code][5] is None and BY[code][6] is None, code
    assert BY["MLN"][7] == "melilla"
    assert not any(a[7] == "island:Formentera" for a in airports.AIRPORTS)
    assert "TNG" not in BY and "NDR" not in BY


def test_destinations_only_eligible_with_prefixed_codes():
    dests = airports.destinations()
    assert dests and all(d["code"] == "AIR:" + d["iata"] for d in dests)
    assert all(d["tier_year"] is not None or d["tier_summer"] is not None for d in dests)
    assert "TEV" not in {d["iata"] for d in dests}
    assert set(dests[0]) == {"code", "iata", "name", "country", "lat", "lng",
                             "tier_year", "tier_summer", "zone", "note"}


# --- compute_airports -------------------------------------------------------

import compute_airports  # noqa: E402
import compute_times  # noqa: E402
from test_pipeline import base, fake_post  # noqa: E402

FAKE = [
    {"code": "AIR:MAD", "iata": "MAD", "name": "Madrid", "country": "ES", "lat": 40.49, "lng": -3.57,
     "tier_year": 1, "tier_summer": 1, "zone": "mainland", "note": ""},
    {"code": "AIR:VLC", "iata": "VLC", "name": "Valencia", "country": "ES", "lat": 39.49, "lng": -0.47,
     "tier_year": 2, "tier_summer": 2, "zone": "mainland", "note": ""},
    {"code": "AIR:XXX", "iata": "XXX", "name": "Summer only", "country": "ES", "lat": 40.34, "lng": -1.11,
     "tier_year": None, "tier_summer": 3, "zone": "mainland", "note": "summer"},   # at Teruel
    {"code": "AIR:IBZ", "iata": "IBZ", "name": "Eivissa", "country": "ES", "lat": 38.87, "lng": 1.37,
     "tier_year": 2, "tier_summer": 2, "zone": "island:Eivissa", "note": ""},
]


def run_airports(monkeypatch, tmp_path, post=fake_post):
    monkeypatch.setenv("TRAVELTIME_APP_ID", "x")
    monkeypatch.setenv("TRAVELTIME_API_KEY", "y")
    monkeypatch.setattr(compute_times.Client, "post", post)
    munis = base()
    client = compute_times.Client("regular")
    results = compute_times.compute_all(munis, [dict(a) for a in FAKE], client,
                                        use_cache=False, cdir=tmp_path)
    return munis, compute_airports.aggregate_airports(munis, [dict(a) for a in FAKE], results)


def test_aggregate_nested_and_summer_only(monkeypatch, tmp_path):
    _, (aps, rows) = run_airports(monkeypatch, tmp_path)
    xxx = next(i for i, a in enumerate(aps) if a["iata"] == "XXX")
    for code, r in rows.items():
        assert len(r) == 12
        for base_i in (0, 6):
            t1, t2, t3 = r[base_i], r[base_i + 2], r[base_i + 4]
            if t1 >= 0:
                assert 0 <= t2 <= t1, code
            if t2 >= 0:
                assert 0 <= t3 <= t2, code
        for k in range(3):
            if r[k * 2] >= 0:
                assert 0 <= r[6 + k * 2] <= r[k * 2], code   # summer never slower
        assert xxx not in (r[1], r[3], r[5]), code             # never chosen year-round
    assert rows["44216"][11] == xxx                            # Teruel: summer tier 3 is XXX
    assert rows["44216"][5] != xxx


def test_no_airport_on_island_or_ceuta(monkeypatch, tmp_path):
    _, (aps, rows) = run_airports(monkeypatch, tmp_path)
    assert rows["07024"] == [-1] * 12                          # Formentera
    assert rows["51001"] == [-1] * 12                          # Ceuta
    ibz = next(i for i, a in enumerate(aps) if a["iata"] == "IBZ")
    assert rows["07026"][3] == ibz                             # Eivissa town -> IBZ (tier 2)


def test_airport_ids_do_not_collide(monkeypatch, tmp_path):
    seen = []

    def recording(self, path, body):
        for s in body["arrival_searches"]:
            seen.append(s["arrival_location_id"])
            assert not any(o.startswith("AIR:") for o in s["departure_location_ids"])
        return fake_post(self, path, body)

    run_airports(monkeypatch, tmp_path, recording)
    assert seen and all(a.startswith("AIR:") for a in seen)


def test_airports_csv(monkeypatch, tmp_path):
    from common import write_csv
    munis, (aps, rows) = run_airports(monkeypatch, tmp_path)
    places = {"meta": {"population_year": 2025}, "municipalities": munis}
    results = {a["code"]: {"x": 1} for a in aps}
    output = compute_airports.build_output(places, aps, rows, results)
    assert output["airports"][0][:3] == [aps[0]["iata"], aps[0]["name"], "ES"]
    assert len(output["m"]["44216"]) == 13
    assert output["params"]["notes"] == airports.NOTES
    header, csv_rows = compute_airports.airports_csv_rows(output, munis)
    assert header == ["code", "name", "province", "population",
                      "y1_min", "y1_airport", "y2_min", "y2_airport", "y3_min", "y3_airport",
                      "s1_min", "s1_airport", "s2_min", "s2_airport", "s3_min", "s3_airport"]
    by = {r[0]: r for r in csv_rows}
    assert by["07024"][4:] == [None] * 12
    assert by["44216"][15] == "XXX"
    p = tmp_path / "airports.csv"
    write_csv(p, header, csv_rows)
    assert p.with_suffix(".csvt").read_text().startswith('"String"')


def test_partial_run_writes_nothing(monkeypatch, tmp_path):
    monkeypatch.setenv("TRAVELTIME_APP_ID", "x")
    monkeypatch.setenv("TRAVELTIME_API_KEY", "y")
    monkeypatch.setattr(compute_times.Client, "post", fake_post)
    monkeypatch.setattr(compute_airports, "AIRPORTS_OUTPUT_FILE", tmp_path / "airports.json")
    monkeypatch.setattr(compute_airports, "AIRPORTS_CSV", tmp_path / "airports.csv")
    monkeypatch.setattr(compute_airports, "AIRPORT_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(sys, "argv", ["compute_airports.py", "--only", "MAD"])
    compute_airports.main()
    assert not (tmp_path / "airports.json").exists()
    assert not (tmp_path / "airports.csv").exists()
    assert (tmp_path / "cache").exists()


def test_output_flags_airports_nobody_reaches():
    """An airport with no transit link must be flagged, not look like a real result."""
    munis = [{"code": "52001", "name": "Melilla", "province": "Melilla", "pop": 86780}]
    aps = [dict(FAKE[0]), {"code": "AIR:MLN", "iata": "MLN", "name": "Melilla", "country": "ES",
                           "lat": 35.28, "lng": -2.96, "tier_year": 3, "tier_summer": 3,
                           "zone": "melilla", "note": ""}]
    results = {"AIR:MAD": {"AIR:MAD": 0, "28079": 2000}, "AIR:MLN": {"AIR:MLN": 0}}
    aps, rows = compute_airports.aggregate_airports(munis, aps, results)
    places = {"meta": {"population_year": 2025}, "municipalities": munis}
    out = compute_airports.build_output(places, aps, rows, results)
    reach = {a[0]: a[8] for a in out["airports"]}
    assert reach == {"MAD": 1, "MLN": 0}
    assert any("Melilla (MLN)" in n for n in out["params"]["notes"])
    assert not any("Madrid" in n for n in out["params"]["notes"][len(airports.NOTES):])
