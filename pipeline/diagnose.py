"""Compare TravelTime endpoints on known short public transport trips.

Each pair below has an obvious commuter connection (tram, Cercanías or a
frequent bus), so all of them should be reachable well within 3 hours.

  python3 pipeline/diagnose.py
"""

import json

from common import PLACES_FILE, load_json
from compute_times import ARRIVAL_TIMES, MAX_SECONDS, Client, arrival_times

PAIRS = [  # (origin, destination)
    ("30005", "30030"),  # Alcantarilla -> Murcia
    ("41081", "41091"),  # La Rinconada -> Sevilla
    ("03104", "03066"),  # Petrer -> Elda
    ("49021", "49275"),  # Benavente -> Zamora
    ("08012", "08113"),  # Avinyó -> Manresa
    ("08012", "08019"),  # Avinyó -> Barcelona
    ("46220", "46250"),  # Sagunt -> València
    ("28131", "28079"),  # San Lorenzo de El Escorial -> Madrid (known good)
]


def main():
    by = {m["code"]: m for m in load_json(PLACES_FILE)["municipalities"]}
    loc = lambda c: {"id": c, "coords": {"lat": by[c]["lat"], "lng": by[c]["lng"]}}  # noqa: E731
    fast, regular = Client("fast"), Client("regular")
    arrivals = arrival_times()

    print(f"{'origin -> destination':45s} {'fast':>11s} " + " ".join(f"{'reg@' + t:>11s}" for t in ARRIVAL_TIMES))
    for o, d in PAIRS:
        locs = [loc(o), loc(d)]
        res = []
        # 1) fast endpoint, one search on its own (rules out batching effects)
        body = {"locations": locs, "arrival_searches": {"many_to_one": [{
            "id": "s", "arrival_location_id": d, "departure_location_ids": [o],
            "transportation": {"type": "public_transport"}, "arrival_time_period": "weekday_morning",
            "travel_time": MAX_SECONDS, "properties": ["travel_time"]}]}}
        r = fast.post("/time-filter/fast", body)
        res.append(_minutes(r))
        # 2) regular endpoint with a real timetable arrival time
        for at in arrivals:
            body = {"locations": locs, "arrival_searches": [{
                "id": "s", "arrival_location_id": d, "departure_location_ids": [o],
                "transportation": {"type": "public_transport"}, "arrival_time": at,
                "travel_time": MAX_SECONDS, "properties": ["travel_time"]}]}
            res.append(_minutes(regular.post("/time-filter", body)))
        label = f"{by[o]['name']} -> {by[d]['name']} ({by[o]['point']})"
        print(f"{label:45s} " + " ".join(f"{x:>11s}" for x in res))


def _minutes(payload):
    try:
        locs = payload["results"][0]["locations"]
        if not locs:
            return "unreach"
        p = locs[0]["properties"]
        p = p[0] if isinstance(p, list) else p
        return f"{round(p['travel_time'] / 60)} min"
    except (KeyError, IndexError):
        return "err:" + json.dumps(payload)[:40]


if __name__ == "__main__":
    main()
