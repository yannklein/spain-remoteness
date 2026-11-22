"""Cross-border destinations reached through border stations (gateways)."""
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import crossborder  # noqa: E402

CAP = 10800
MUNIS = {"A", "B", "C"}


def hop(gw, dest, ride):
    return (gw, dest, ride, "test service", "test")


def test_estimate_is_gateway_time_plus_ride_plus_change():
    results = {"GW:g1": {"A": 600, "GW:g1": 0}}
    via = crossborder.apply_hops(results, [hop("g1", "XX:city", 30)], MUNIS, CAP)
    assert results["XX:city"] == {"A": 600 + (30 + crossborder.TRANSFER_MIN) * 60}
    assert via == {"XX:city": {"A": "g1"}}


def test_best_hop_wins():
    results = {"GW:g1": {"A": 600}, "GW:g2": {"A": 300}}
    via = crossborder.apply_hops(results, [hop("g1", "XX:city", 30), hop("g2", "XX:city", 60)], MUNIS, CAP)
    # g1: 600 + 2400 = 3000; g2: 300 + 4200 = 4500
    assert results["XX:city"]["A"] == 3000 and via["XX:city"]["A"] == "g1"


def test_measured_time_wins_when_faster():
    results = {"GW:g1": {"A": 600, "B": 600}, "XX:city": {"A": 900}}
    via = crossborder.apply_hops(results, [hop("g1", "XX:city", 30)], MUNIS, CAP)
    assert results["XX:city"]["A"] == 900 and "A" not in via["XX:city"]
    assert results["XX:city"]["B"] == 3000 and via["XX:city"]["B"] == "g1"


def test_no_estimate_beyond_the_cap():
    results = {"GW:g1": {"A": CAP - 600}}
    via = crossborder.apply_hops(results, [hop("g1", "XX:city", 30)], MUNIS, CAP)
    assert "A" not in results.get("XX:city", {}) and not via.get("XX:city")


def test_only_municipalities_get_estimates():
    results = {"GW:g1": {"GW:g1": 0, "A": 60}}
    crossborder.apply_hops(results, [hop("g1", "XX:city", 30)], MUNIS, CAP)
    assert set(results["XX:city"]) == {"A"}


def test_cached_results_are_not_mutated():
    measured = {"A": 9000}
    results = {"GW:g1": {"A": 60}, "XX:city": measured}
    crossborder.apply_hops(results, [hop("g1", "XX:city", 30)], MUNIS, CAP)
    assert measured == {"A": 9000} and results["XX:city"]["A"] == 60 + 2400


def test_via_slots_name_the_gateway_of_the_chosen_destination():
    ordered = [{"code": "ES:x"}, {"code": "XX:city"}]
    rows = {"A": [30, 1, 20, 0], "B": [30, 0, -1, -1], "C": [50, 1, 50, 1]}
    via = {"XX:city": {"A": "g2", "C": "g1"}}
    out = crossborder.via_slots(rows, ordered, via, ["g1", "g2"])
    assert out == {"A": [1, -1], "B": None, "C": [0, 0]}


@pytest.mark.parametrize("cc,airports_module", [("es", "airports"), ("fr", "countries.fr_airports")])
def test_country_config_is_consistent(cc, airports_module):
    cfg = crossborder.config(cc)
    iatas = {"AIR:" + a[0] for a in importlib.import_module(airports_module).AIRPORTS}
    for code, (name, tier, lat, lng, pop) in cfg.FOREIGN_CITIES.items():
        assert code[:2].isupper() and code[2] == ":" and code[:2] != cc.upper()
        assert tier in (1, 2, 3) and pop > 0 and -20 < lng < 20 and 35 < lat < 52
    for gw, dest, ride, service, source in cfg.HOPS:
        assert gw in cfg.GATEWAYS, gw
        assert dest in cfg.FOREIGN_CITIES or dest in iatas, dest
        assert 0 < ride and ride + crossborder.TRANSFER_MIN < 180 and service and source   # else it can never count
    assert len({(h[0], h[1]) for h in cfg.HOPS}) == len(cfg.HOPS)   # no duplicate hop


def test_destinations_for_gateways_and_foreign_cities():
    cfg = crossborder.config("fr")
    gws = crossborder.gateway_dests(cfg)
    assert {d["code"] for d in gws} == {"GW:" + g for g in cfg.GATEWAYS}
    assert all(d["zone"] == "mainland" and d["max_km"] == crossborder.GATEWAY_KM for d in gws)
    cities = crossborder.foreign_city_dests(cfg)
    geneve = next(d for d in cities if d["code"] == "CH:geneve")
    assert geneve["tier"] == 1 and geneve["max_km"] == crossborder.DIRECT_KM and geneve["zone"] == "mainland"


def test_hops_through_a_home_city_of_the_slot_tier_are_skipped():
    hops = [hop("lille", "BE:tournai", 25), hop("perpignan", "ES:barcelona", 80), hop("tui", "PT:viana", 75)]
    city_tier = {"lille": 1, "perpignan": 2, "tui": None}   # tier of the home city each gateway stands in
    names = lambda hs: [h[0] for h in hs]                   # noqa: E731
    assert names(crossborder.hops_for_tier(hops, city_tier, 1)) == ["perpignan", "tui"]
    assert names(crossborder.hops_for_tier(hops, city_tier, 2)) == ["tui"]
    assert names(crossborder.hops_for_tier(hops, city_tier, 3)) == ["tui"]


def test_gateway_city_tiers_locate_the_home_municipality():
    cfg = type("Cfg", (), {"GATEWAYS": {"a": ("A station", 1.0, 2.0), "b": ("B stop", 3.0, 4.0), "c": ("C", 5.0, 6.0)}})
    where = {(2.0, 1.0): "M1", (4.0, 3.0): "M2"}
    tiers = {"M1": 2, "M2": None}
    got = crossborder.gateway_city_tiers(cfg, lambda lng, lat: where.get((lng, lat)), tiers.get)
    assert got == {"a": 2, "b": None, "c": None}


def test_cities_skip_a_border_station_inside_a_city_of_the_slot_tier(monkeypatch):
    import compute_times
    import geo
    munis = [{"code": "L", "name": "Lille", "tier": 1, "lat": 0, "lng": 0, "pop": 1},
             {"code": "V", "name": "Village", "tier": None, "lat": 0, "lng": 0, "pop": 1}]
    foreign = [{"code": "BE:tournai", "name": "Tournai", "tier": 2, "lat": 0, "lng": 0, "pop": 1}]
    cfg = type("Cfg", (), {"GATEWAYS": {"lille": ("Lille station", 50.6, 3.07), "bridge": ("Bridge", 1.0, 1.0)},
                           "HOPS": [("lille", "BE:tournai", 25, "SNCB", "test"), ("bridge", "BE:tournai", 100, "bus", "test")]})
    monkeypatch.setattr(geo, "load_municipalities", lambda path=None: None)
    monkeypatch.setattr(geo, "MuniIndex", lambda _m: type("I", (), {"locate": staticmethod(
        lambda lng, lat: "L" if lat > 50 else None)})())
    results = {"L": {"L": 0, "V": 7200}, "BE:tournai": {}, "GW:lille": {"V": 600}, "GW:bridge": {"V": 600}}
    cities, rows, slots = compute_times.aggregate_with_border(munis, [munis[0]] + foreign, results, cfg)
    tour = next(i for i, c in enumerate(cities) if c["code"] == "BE:tournai")
    # tier 2: Lille counts, so the Lille hop is out; the bridge one (600 + 110 min = 7200 s) only ties Lille
    assert rows["V"][2:4] == [120, 0] and slots["V"] is None
    # with a faster bridge hop the estimate wins tier 2 and names the bridge
    cfg.HOPS = [("lille", "BE:tournai", 25, "SNCB", "test"), ("bridge", "BE:tournai", 50, "bus", "test")]
    cities, rows, slots = compute_times.aggregate_with_border(munis, [munis[0]] + foreign, results, cfg)
    assert rows["V"][2:4] == [70, tour] and slots["V"] == [-1, 1, 1]
