import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build_places  # noqa: E402
import compute_times  # noqa: E402
from common import BASE_FILE, haversine_km, load_json, zone  # noqa: E402

INE_SAMPLE = """﻿Municipios;Sexo;Periodo;Total
44216 Teruel;Total;2024;36.240
44216 Teruel;Total;2023;35.994
44216 Teruel;Hombres;2024;17.800
28065 Getafe;Total;2024;189.000
28065 Getafe;Total;2023;187.000
33016 Castrillón;Total;2024;22.000
45165 Talavera de la Reina;Total;2024;84.000
Total Nacional;Total;2024;48.619.695
"""


def test_parse_ine_csv_takes_latest_year_and_total_sex():
    pops, year = build_places.parse_ine_csv(INE_SAMPLE)
    assert year == 2024
    assert pops["44216"] == 36240
    assert pops["28065"] == 189000
    assert "Total Nacional"[:5] not in pops


def test_parse_overpass_maps_ine_code_to_admin_centre():
    payload = {"elements": [
        {"type": "relation", "id": 1, "tags": {"ine:municipio": "44216"},
         "members": [{"type": "way", "ref": 9, "role": "outer"},
                     {"type": "node", "ref": 7, "role": "admin_centre"}]},
        {"type": "relation", "id": 2, "tags": {"ine:municipio": "282650"},  # with control digit
         "members": [{"type": "node", "ref": 8, "role": "admin_centre"}]},
        {"type": "node", "id": 7, "lat": 40.344, "lon": -1.106},
        {"type": "node", "id": 8, "lat": 40.3, "lon": -3.7},
    ]}
    out = build_places.parse_overpass(payload)
    assert out["44216"] == (40.344, -1.106)
    assert out["28265"] == (40.3, -3.7)


def base():
    return [dict(m) for m in load_json(BASE_FILE)["municipalities"]]


def test_classify_with_population():
    munis = base()
    pops, _ = build_places.parse_ine_csv(INE_SAMPLE)
    by = {m["code"]: m for m in build_places.classify(munis, pops)}
    assert by["28079"]["tier"] == 1            # Madrid
    assert by["44216"]["tier"] == 2            # Teruel: capital despite 36k
    assert by["28065"]["tier"] == 2            # Getafe >100k ...
    assert by["28065"]["metro"] == "Madrid"    # ... labelled as Madrid metro
    assert by["45165"]["tier"] == 3            # Talavera 84k
    assert by["33016"]["tier"] is None         # Castrillón 22k
    assert by["15078"]["tier"] == 2            # Santiago (regional capital)
    assert sum(m["urban"] for m in munis) == sum(m["tier"] is not None for m in munis)


def test_classify_without_population_uses_fallback_list():
    by = {m["code"]: m for m in build_places.classify(base(), {})}
    assert by["36057"]["tier"] == 2            # Vigo
    assert by["45165"]["tier"] is None         # no tier 3 without INE data
    assert by["08101"]["metro"] == "Barcelona"


def test_zones_keep_islands_separate():
    by = {m["code"]: m for m in base()}
    assert zone(by["07040"]) == "island:Mallorca"
    assert zone(by["51001"]) == "ceuta"
    assert zone(by["44216"]) == "mainland"


def fake_post(self, path, body):
    """Pretend public transport runs at 60 km/h straight-line, max 3 h."""
    locs = {l["id"]: l["coords"] for l in body["locations"]}
    searches = body["arrival_searches"]
    searches = searches["many_to_one"] if isinstance(searches, dict) else searches
    results = []
    for s in searches:
        a = locs[s["arrival_location_id"]]
        out, unreachable = [], []
        for oid in s["departure_location_ids"]:
            o = locs[oid]
            secs = haversine_km(a["lat"], a["lng"], o["lat"], o["lng"]) / 60 * 3600
            if secs <= s["travel_time"]:
                props = {"travel_time": int(secs)}
                out.append({"id": oid, "properties": [props] if path == "/time-filter" else props})
            else:
                unreachable.append(oid)
        results.append({"search_id": s["id"], "locations": out, "unreachable": unreachable})
    self.calls += 1
    return {"results": results}


def run_fake(monkeypatch, tmp_path, endpoint):
    monkeypatch.setenv("TRAVELTIME_APP_ID", "x")
    monkeypatch.setenv("TRAVELTIME_API_KEY", "y")
    monkeypatch.setattr(compute_times, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(compute_times.Client, "post", fake_post)
    munis = build_places.classify(base(), {})
    dests = [m for m in munis if m["tier"] is not None]
    client = compute_times.Client(endpoint)
    results = compute_times.compute_all(munis, dests, client, use_cache=False)
    return munis, dests, client, results


def test_compute_and_aggregate_fast(monkeypatch, tmp_path):
    munis, dests, client, results = run_fake(monkeypatch, tmp_path, "fast")
    assert client.calls == -(-len(dests) // 10)
    cities, rows = compute_times.aggregate(munis, dests, results)
    for code, (t1, c1, t2, c2, t3, c3) in rows.items():
        # nested tiers: more cities can only make the nearest one closer
        if t1 >= 0:
            assert 0 <= t2 <= t1
        if t2 >= 0:
            assert 0 <= t3 <= t2
    assert rows["28079"][0] == 0                         # Madrid to itself
    assert cities[rows["44216"][1]]["name"] == "València"  # Teruel's nearest metro
    assert cities[rows["44216"][3]]["code"] == "44216"     # nearest hub is Teruel itself
    assert rows["38001"][0] == -1                          # Tenerife: no metro on the island
    # islands never reach mainland cities
    assert rows["07040"][0] == -1 and rows["07040"][2] == 0


def test_regular_endpoint_chunks(monkeypatch, tmp_path):
    munis, dests, client, results = run_fake(monkeypatch, tmp_path, "regular")
    _, _, _, fast = run_fake(monkeypatch, tmp_path, "fast")
    # within 180 km (3 h at 60 km/h) both endpoints must agree, chunks merged back
    assert results["28079"] == fast["28079"]
    assert len(results["28079"]) == 2000                 # 1,999 within 180 km + itself (> one chunk)
    assert client.calls > -(-len(dests) // 10)


def test_city_alone_in_its_zone_needs_no_request(monkeypatch, tmp_path):
    """Ceuta is the only municipality in its zone: no empty search may be sent."""
    sent = []

    def recording_post(self, path, body):
        for srch in body["arrival_searches"]["many_to_one"]:
            assert srch["departure_location_ids"], "empty departure_location_ids sent"
            sent.append(srch["id"])
        return fake_post(self, path, body)

    monkeypatch.setenv("TRAVELTIME_APP_ID", "x")
    monkeypatch.setenv("TRAVELTIME_API_KEY", "y")
    monkeypatch.setattr(compute_times, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(compute_times.Client, "post", recording_post)
    munis = build_places.classify(base(), {})
    dests = [m for m in munis if m["code"] in ("51001", "52001", "28079")]
    res = compute_times.compute_all(munis, dests, compute_times.Client("fast"), use_cache=False)
    assert "51001" not in sent and "52001" not in sent and "28079" in sent
    assert res["51001"] == {"51001": 0}


def test_bad_credentials_exit_without_fallback(monkeypatch, tmp_path, capsys):
    import pytest
    from common import HTTPStatusError

    calls = []

    def unauthorized(self, path, body):
        calls.append(path)
        raise HTTPStatusError(401, "HTTP 401: Application Id or Api Key is invalid")

    monkeypatch.setenv("TRAVELTIME_APP_ID", "x")
    monkeypatch.setenv("TRAVELTIME_API_KEY", "y")
    monkeypatch.setattr(compute_times, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(compute_times.Client, "post", unauthorized)
    monkeypatch.setattr(sys, "argv", ["compute_times.py", "--limit", "2"])
    with pytest.raises(SystemExit) as exc:
        compute_times.main()
    assert "credentials" in str(exc.value)
    assert calls == ["/time-filter/fast"]   # no pointless fallback to /time-filter
