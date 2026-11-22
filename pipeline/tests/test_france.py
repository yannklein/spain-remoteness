import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build_places_fr as bp  # noqa: E402
from common import paths, zone  # noqa: E402
from countries import fr  # noqa: E402


def c(code, name, dep, pop):
    return {"code": code, "nom": name, "codeDepartement": dep, "population": pop,
            "mairie": {"coordinates": [2.0, 48.0]}, "centre": {"coordinates": [2.1, 48.1]}}


COMMUNES = [
    c("75056", "Paris", "75", 2100000),           # métropole
    c("2A004", "Ajaccio", "2A", 72000),           # préfecture, Corsica
    c("51108", "Châlons-en-Champagne", "51", 44000),  # préfecture in the Marne (code 51!)
    c("59599", "Tourcoing", "59", 98000),         # > 50k only
    c("93066", "Saint-Denis", "93", 113000),      # > 100k
    c("48095", "Mende", "48", 12000),             # préfecture
    c("48001", "Albaret-le-Comtal", "48", 200),
    c("97101", "Les Abymes", "971", 53000),       # overseas: out of scope
]


def test_classify_and_zones():
    places = {p["code"]: p for p in bp.build(COMMUNES, metropoles={("75", "Paris")},
                                             prefectures={("2A", "Ajaccio"), ("51", "Châlons-en-Champagne"),
                                                          ("48", "Mende")})}
    assert "97101" not in places                              # metropolitan France only
    assert places["75056"]["tier"] == 1
    assert places["2A004"]["tier"] == 2 and places["2A004"]["zone"] == "island:Corse"
    assert places["51108"]["tier"] == 2 and zone(places["51108"]) == "mainland"   # not Ceuta!
    assert places["93066"]["tier"] == 2 and places["59599"]["tier"] == 3
    assert places["48095"]["tier"] == 2 and places["48001"]["tier"] is None
    p = places["48001"]
    assert (p["lng"], p["lat"]) == (2.0, 48.0) and p["point"] == "mairie" and p["province"] == "48"
    assert isinstance(p["code"], str) and p["urban"] is False


def test_named_lists_resolve_to_codes():
    found = bp.resolve({("2A", "Ajaccio"), ("48", "Mende")}, COMMUNES)
    assert found == {"2A004", "48095"}
    with pytest.raises(SystemExit):
        bp.resolve({("48", "Nowhere")}, COMMUNES)


def test_config_lists():
    assert len(fr.METROPOLES) == 22 and len(fr.PREFECTURES) == 96
    assert len(fr.METRO_DEPARTMENTS) == 96 and "2A" in fr.METRO_DEPARTMENTS and "20" not in fr.METRO_DEPARTMENTS


@pytest.mark.skipif(not paths("fr").places.exists(), reason="France places not built yet")
def test_real_places_match_boundaries():
    from common import load_json
    from geo import load_municipalities
    pl = load_json(paths("fr").places)["municipalities"]
    topo = load_municipalities(paths("fr").topo)
    codes = {m["code"] for m in pl}
    assert 34000 < len(codes) < 35500
    assert codes == set(topo)
    by = {m["code"]: m for m in pl}
    assert sum(1 for m in pl if m["tier"] == 1) == 22 and by["2B033"]["zone"] == "island:Corse"
