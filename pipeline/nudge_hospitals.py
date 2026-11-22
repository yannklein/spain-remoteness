"""Move hospital arrival points that TravelTime can't attach to its network.

After compute_hospitals.py, hospitals reached by no municipality (reach 0 in
web/public/data/hospitals.json) usually sit on a point TravelTime can't start
from (inside a campus, behind a fence). For each one, points on rings of 200,
400 and 600 m are tried from the hospital's own municipality (one 11:30 arrival
search per point) and the first point that is reached replaces the arrival
point, recorded as an exact override in data/hospital_overrides.json (so
re-running place_hospitals.py keeps it) and applied to data/hospitals.json.
Positions already probed without success are recorded too and not probed again.
compute_hospitals.py recomputes moved hospitals (their cache is invalidated).

Env: TRAVELTIME_APP_ID, TRAVELTIME_API_KEY
Usage: python pipeline/nudge_hospitals.py
"""

import math

import argparse

import compute_hospitals
from common import HTTPStatusError, add_country_arg, dump_json, load_json, paths
from compute_times import MAX_SECONDS, Client, arrival_times, parse_results

RINGS_M = (200, 400, 600)
DIRECTIONS = 8


def ring(lat, lng):
    """[(metres, lat, lng)]: the point itself, then 8 directions on each ring, nearest first."""
    out = [(0, lat, lng)]
    for r in RINGS_M:
        for k in range(DIRECTIONS):
            a = math.radians(k * 360 / DIRECTIONS)
            dlat = r * math.cos(a) / 111320
            dlng = r * math.sin(a) / (111320 * math.cos(math.radians(lat)))
            out.append((r, lat + dlat, lng + dlng))
    return out


def first_reachable(points, reach):
    """First (metres, lat, lng, minutes) whose reach(lat, lng) returns minutes, else None."""
    for r, lat, lng in points:
        t = reach(lat, lng)
        if t is not None:
            return r, lat, lng, t
    return None


def main():
    ap = argparse.ArgumentParser()
    add_country_arg(ap)
    cc = ap.parse_args().country
    if cc != "es":
        compute_hospitals.configure(cc)
    PLACED_FILE, OUTPUT_FILE, OVERRIDES = paths(cc).hospitals_placed, paths(cc).hospitals_json, paths(cc).hospital_overrides
    placed = load_json(PLACED_FILE)
    out = load_json(OUTPUT_FILE)
    dead = {h[0] for h in out["hospitals"] if h[9] == 0}
    places = {m["code"]: m for m in load_json(paths(cc).places)["municipalities"]}
    overrides = load_json(OVERRIDES) if OVERRIDES.exists() else {}
    client = Client("regular")
    at = arrival_times()[1]

    def reach_from(origin):
        def reach(lat, lng):
            body = {"locations": [{"id": "o", "coords": {"lat": origin["lat"], "lng": origin["lng"]}},
                                  {"id": "p", "coords": {"lat": lat, "lng": lng}}],
                    "arrival_searches": [{"id": "s", "arrival_location_id": "p", "departure_location_ids": ["o"],
                                          "transportation": {"type": "public_transport"}, "arrival_time": at,
                                          "travel_time": MAX_SECONDS, "properties": ["travel_time"]}]}
            try:
                got = parse_results(client.post("/time-filter", body)).get("s", {})
            except HTTPStatusError as e:
                if e.code == 422:  # "couldn't start the search at the given point"
                    return None
                raise
            return round(got["o"] / 60) if "o" in got else None
        return reach

    fixed, failed = [], []
    for h in placed:
        if h["codcnh"] not in dead:
            continue
        origin = places.get(h["muni"])
        probed = overrides.get(h["codcnh"], {}).get("unattachable_at")
        if not origin or probed == [h["lat"], h["lng"]]:
            failed.append(h["name"])
            continue
        got = first_reachable(ring(h["lat"], h["lng"]), reach_from(origin))
        if not got:
            failed.append(f"{h['name']} ({origin['name']})")
            overrides.setdefault(h["codcnh"], {})["unattachable_at"] = [h["lat"], h["lng"]]
            print(f"  no attachable point near {h['name']}")
            continue
        r, lat, lng, t = got
        if r == 0:  # the point attaches after all (transient empty response): drop the stale cache
            (compute_hospitals.CACHE_DIR / "regular-0830-1130-1430" / f"HOS:{h['codcnh']}.json").unlink(missing_ok=True)
        h["lat"], h["lng"] = round(lat, 6), round(lng, 6)
        h["point_source"] = f"{h['point_source']}+nudged{r}"
        overrides[h["codcnh"]] = {"lat": h["lat"], "lng": h["lng"], "exact": True, "source": h["point_source"],
                                  "note": f"moved {r} m so TravelTime attaches ({h['name']})"}
        fixed.append(h["name"])
        print(f"  {h['name']}: moved {r} m, {t} min from {origin['name']}")
    dump_json(placed, PLACED_FILE)
    dump_json(overrides, OVERRIDES)
    print(f"{len(fixed)} hospitals moved, {len(failed)} still unattached ({client.calls} API calls)")
    if failed:
        print("  unattached:", ", ".join(failed))


if __name__ == "__main__":
    main()
