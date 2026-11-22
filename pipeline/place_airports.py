"""Snap airport points to the airport's public transport stop, then move the ones that still don't attach.

TravelTime can't start a search from inside a terminal (see README, Spain's airports). For each
airport of a country's list:
1. the nearest stop within 1.5 km whose name says airport (aéroport, aeroport, aérogare, airport,
   aeropuerto, aeroport, terminal), else any stop within 600 m, else the listed point;
2. with --nudge (after compute_airports has run), airports nobody reaches are probed on rings of
   200/400/600 m from the commune they stand in, as for hospitals (nudge_hospitals.ring).
Results go to data/<cc>/airport_points.json, which compute_airports applies (moved airports are
recomputed).

Usage: python pipeline/place_airports.py --country fr [--nudge]
"""

import argparse
import importlib
import re

from common import add_country_arg, dump_json, haversine_km, load_json, paths
from place_hospitals import STOP_FILTERS, _overpass, _plain

AIRPORT_WORDS = re.compile(r"\b(a[eé]roport|aeroport|a[eé]rogare|airport|aeropuerto|aeroporto|terminal)", re.I)
NAMED_RADIUS_M, ANY_RADIUS_M = 1500, 600


def pick_stop(a, stops):
    """(lat, lng, source, stop_name) for the best stop near airport `a`, or None."""
    best = None
    for s in stops:
        d = haversine_km(a["lat"], a["lng"], s["lat"], s["lng"]) * 1000
        named = bool(AIRPORT_WORDS.search(_plain(s.get("name") or "")))
        if (named and d <= NAMED_RADIUS_M) or d <= ANY_RADIUS_M:
            key = (not named, d)
            if best is None or key < best[0]:
                best = (key, s)
    if not best:
        return None
    s = best[1]
    return s["lat"], s["lng"], "stop", s.get("name")


def fetch_stops_around(points, radius):
    parts = "".join(f"node{f}(around:{radius},{lat},{lng});" for lat, lng in points for f in STOP_FILTERS)
    return [{"lat": e["lat"], "lng": e["lon"], "name": e.get("tags", {}).get("name")}
            for e in _overpass(f"[out:json][timeout:300];({parts});out;")]


def snap(cc):
    p = paths(cc)
    airports = importlib.import_module(f"countries.{cc}_airports").destinations()
    stops = fetch_stops_around([(a["lat"], a["lng"]) for a in airports], NAMED_RADIUS_M)
    points = load_json(p.data / "airport_points.json") if (p.data / "airport_points.json").exists() else {}
    for a in airports:
        if points.get(a["iata"], {}).get("exact"):
            continue  # a moved point (nudge) wins
        got = pick_stop(a, stops)
        if got:
            points[a["iata"]] = {"lat": round(got[0], 6), "lng": round(got[1], 6), "source": "stop", "stop_name": got[3]}
    dump_json(points, p.data / "airport_points.json")
    print(f"{sum(1 for v in points.values() if v.get('source') == 'stop')} of {len(airports)} airports snapped to a stop")


def nudge(cc):
    from compute_times import MAX_SECONDS, Client, arrival_times, parse_results
    from common import HTTPStatusError
    from geo import MuniIndex, load_municipalities
    from nudge_hospitals import first_reachable, ring
    p = paths(cc)
    out = load_json(p.airports_json)
    points = load_json(p.data / "airport_points.json") if (p.data / "airport_points.json").exists() else {}
    places = {m["code"]: m for m in load_json(p.places)["municipalities"]}
    index = MuniIndex(load_municipalities(p.topo))
    client, at = Client("regular"), arrival_times()[1]
    moved, failed = [], []
    for a in out["airports"]:
        iata, lat, lng, reach = a[0], a[3], a[4], a[8]
        if reach or points.get(iata, {}).get("unattachable_at") == [lat, lng]:
            continue
        origin = places.get(index.locate(lng, lat) or "")
        if not origin:
            failed.append(f"{iata} (outside {cc})")
            continue

        def reach_fn(la, ln, origin=origin):
            body = {"locations": [{"id": "o", "coords": {"lat": origin["lat"], "lng": origin["lng"]}},
                                  {"id": "p", "coords": {"lat": la, "lng": ln}}],
                    "arrival_searches": [{"id": "s", "arrival_location_id": "p", "departure_location_ids": ["o"],
                                          "transportation": {"type": "public_transport"}, "arrival_time": at,
                                          "travel_time": MAX_SECONDS, "properties": ["travel_time"]}]}
            try:
                got = parse_results(client.post("/time-filter", body)).get("s", {})
            except HTTPStatusError as e:
                if e.code == 422:
                    return None
                raise
            return round(got["o"] / 60) if "o" in got else None

        got = first_reachable(ring(lat, lng), reach_fn)
        if not got:
            points.setdefault(iata, {})["unattachable_at"] = [lat, lng]
            failed.append(iata)
            continue
        r, la, ln, t = got
        if r == 0:  # the point attaches after all: its cached empty result is stale
            (p.airports_cache / "regular-0830-1130-1430" / f"AIR:{iata}.json").unlink(missing_ok=True)
        points[iata] = {"lat": round(la, 6), "lng": round(ln, 6), "exact": True, "source": f"nudged{r}",
                        "note": f"moved {r} m so TravelTime attaches; {t} min from {origin['name']}"}
        moved.append(iata)
    dump_json(points, p.data / "airport_points.json")
    print(f"moved {len(moved)} {moved}; still unattached {len(failed)} {failed} ({client.calls} API calls)")


def main():
    ap = argparse.ArgumentParser()
    add_country_arg(ap)
    ap.add_argument("--nudge", action="store_true", help="probe unreached airports (TravelTime calls)")
    args = ap.parse_args()
    nudge(args.country) if args.nudge else snap(args.country)


if __name__ == "__main__":
    main()
