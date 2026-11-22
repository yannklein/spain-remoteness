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
        assert 0 < ride < 180 and service and source
    assert len({(h[0], h[1]) for h in cfg.HOPS}) == len(cfg.HOPS)   # no duplicate hop


def test_destinations_for_gateways_and_foreign_cities():
    cfg = crossborder.config("fr")
    gws = crossborder.gateway_dests(cfg)
    assert {d["code"] for d in gws} == {"GW:" + g for g in cfg.GATEWAYS}
    assert all(d["zone"] == "mainland" and d["max_km"] == crossborder.GATEWAY_KM for d in gws)
    cities = crossborder.foreign_city_dests(cfg)
    geneve = next(d for d in cities if d["code"] == "CH:geneve")
    assert geneve["tier"] == 1 and geneve["max_km"] == crossborder.DIRECT_KM and geneve["zone"] == "mainland"
