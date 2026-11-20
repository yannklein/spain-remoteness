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
