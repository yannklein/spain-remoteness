"""Step 2: public transport travel times to the nearest main city.

For every destination city we ask TravelTime how long it takes to arrive
there on a weekday morning by public transport, from every municipality
in the same zone (mainland / island / Ceuta / Melilla) within MAX_KM.
Up to 3 hours is measured; anything slower is "3h+ / unreachable".

Then, per municipality and per tier, we keep the fastest city.

Env: TRAVELTIME_APP_ID, TRAVELTIME_API_KEY
Usage: python pipeline/compute_times.py [--limit N] [--endpoint fast|regular]
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from common import (CACHE_DIR, OUTPUT_FILE, PLACES_FILE, HTTPStatusError,
                    dump_json, haversine_km, http, load_json, zone)

API = "https://api.traveltimeapp.com/v4"
MAX_SECONDS = 10800          # 3 h, the maximum the fast endpoint allows
MAX_KM = 350                 # beyond this, 3 h by public transport is out of reach
MAX_KM_REGULAR = 250         # tighter radius for the (2,000-locations) regular endpoint
SEARCHES_PER_REQUEST = 10
REGULAR_CHUNK = 1999         # 2,000 ids per search, minus the arrival location
MIN_INTERVAL_S = 0.6         # stay well below 120 hits/min on a free key
TIERS = (1, 2, 3)


def headers():
    app_id = os.environ.get("TRAVELTIME_APP_ID")
    key = os.environ.get("TRAVELTIME_API_KEY")
    if not app_id or not key:
        sys.exit("TRAVELTIME_APP_ID and TRAVELTIME_API_KEY must be set")
    return {"Content-Type": "application/json", "X-Application-Id": app_id, "X-Api-Key": key}


def next_weekday_8am():
    """Next Tuesday 08:30 Madrid time, as UTC ISO string (regular endpoint)."""
    tz = ZoneInfo("Europe/Madrid")
    d = datetime.now(tz) + timedelta(days=1)
    while d.weekday() != 1:
        d += timedelta(days=1)
    d = d.replace(hour=8, minute=30, second=0, microsecond=0)
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def origins_for(dest, munis, max_km):
    z = zone(dest)
    return [m for m in munis
            if m["code"] != dest["code"] and zone(m) == z
            and haversine_km(dest["lat"], dest["lng"], m["lat"], m["lng"]) <= max_km]


def parse_results(payload):
    """{search_id: {location_id: seconds}} from a time-filter response (fast or regular)."""
    out = {}
    for res in payload.get("results", []):
        times = out.setdefault(res["search_id"], {})
        for loc in res.get("locations", []):
            props = loc.get("properties")
            if isinstance(props, list):  # regular endpoint: list of property objects
                props = props[0] if props else {}
            tt = (props or {}).get("travel_time")
            if tt is not None:
                times[loc["id"]] = int(tt)
    return out


class Client:
    def __init__(self, endpoint):
        self.endpoint = endpoint
        self.headers = headers()
        self.last = 0.0
        self.calls = 0

    def post(self, path, body):
        wait = MIN_INTERVAL_S - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        self.last = time.time()
        self.calls += 1
        return json.loads(http(f"{API}{path}", data=body, headers=self.headers, timeout=300))

    def fast(self, batch):
        """batch: list of (dest, origins). One request, up to 10 searches."""
        locs = {}
        searches = []
        for dest, origins in batch:
            locs[dest["code"]] = dest
            for o in origins:
                locs[o["code"]] = o
            searches.append({
                "id": dest["code"],
                "arrival_location_id": dest["code"],
                "departure_location_ids": [o["code"] for o in origins],
                "transportation": {"type": "public_transport"},
                "arrival_time_period": "weekday_morning",
                "travel_time": MAX_SECONDS,
                "properties": ["travel_time"],
            })
        body = {
            "locations": [{"id": c, "coords": {"lat": m["lat"], "lng": m["lng"]}} for c, m in locs.items()],
            "arrival_searches": {"many_to_one": searches},
        }
        return parse_results(self.post("/time-filter/fast", body))

    def regular(self, batch, arrival_time):
        """Same as fast() but via /time-filter, chunked to 2,000 ids per search."""
        out = {}
        searches, locs = [], {}

        def flush():
            if not searches:
                return
            body = {"locations": [{"id": c, "coords": {"lat": m["lat"], "lng": m["lng"]}}
                                  for c, m in locs.items()],
                    "arrival_searches": list(searches)}
            for sid, times in parse_results(self.post("/time-filter", body)).items():
                out.setdefault(sid.split("#")[0], {}).update(times)
            searches.clear()
            locs.clear()

        for dest, origins in batch:
            for i in range(0, max(len(origins), 1), REGULAR_CHUNK):
                chunk = origins[i:i + REGULAR_CHUNK]
                if not chunk:
                    continue
                locs[dest["code"]] = dest
                for o in chunk:
                    locs[o["code"]] = o
                searches.append({
                    "id": f"{dest['code']}#{i}",
                    "arrival_location_id": dest["code"],
                    "departure_location_ids": [o["code"] for o in chunk],
                    "transportation": {"type": "public_transport"},
                    "arrival_time": arrival_time,
                    "travel_time": MAX_SECONDS,
                    "properties": ["travel_time"],
                })
                if len(searches) == SEARCHES_PER_REQUEST:
                    flush()
        flush()
        return out


def compute_all(munis, dests, client, use_cache=True):
    """Return {dest_code: {origin_code: seconds}}, using/refreshing the disk cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    todo = []
    for d in dests:
        f = CACHE_DIR / f"{d['code']}.json"
        if use_cache and f.exists():
            results[d["code"]] = load_json(f)
        else:
            todo.append(d)
    print(f"{len(dests)} destinations, {len(dests) - len(todo)} cached, {len(todo)} to compute")

    max_km = MAX_KM if client.endpoint == "fast" else MAX_KM_REGULAR
    arrival_time = next_weekday_8am() if client.endpoint == "regular" else None
    # group destinations by zone so a batch shares most of its origins
    todo.sort(key=lambda d: (zone(d), d["code"]))
    for i in range(0, len(todo), SEARCHES_PER_REQUEST):
        group = todo[i:i + SEARCHES_PER_REQUEST]
        batch = [(d, origins_for(d, munis, max_km)) for d in group]
        names = ", ".join(d["name"] for d in group)
        print(f"[{i + len(group)}/{len(todo)}] {names}")
        # a city alone in its zone (Ceuta, Melilla, Eivissa...) has nobody to reach it
        to_ask = [(d, o) for d, o in batch if o]
        got = {}
        if to_ask:
            got = client.fast(to_ask) if client.endpoint == "fast" else client.regular(to_ask, arrival_time)
        for d, _ in batch:
            times = got.get(d["code"], {})
            times[d["code"]] = 0
            results[d["code"]] = times
            dump_json(times, CACHE_DIR / f"{d['code']}.json", compact=True)
    return results


def aggregate(munis, dests, results):
    """Per municipality and tier: (minutes, city index) of the fastest destination."""
    cities = sorted(dests, key=lambda d: (d["tier"], -(d.get("pop") or 0), d["name"]))
    index = {d["code"]: i for i, d in enumerate(cities)}
    out = {}
    for m in munis:
        row = []
        for tier in TIERS:
            best_t, best_c = None, None
            for d in cities:
                if d["tier"] > tier:
                    continue
                t = results.get(d["code"], {}).get(m["code"])
                if t is not None and (best_t is None or t < best_t):
                    best_t, best_c = t, index[d["code"]]
            row += [-1, -1] if best_t is None else [round(best_t / 60), best_c]
        out[m["code"]] = row
    return cities, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="only compute the first N destinations (testing)")
    ap.add_argument("--endpoint", choices=["fast", "regular", "auto"], default="auto")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    places = load_json(PLACES_FILE)
    munis = places["municipalities"]
    dests = [m for m in munis if m["tier"] is not None]
    if args.limit:
        dests = sorted(dests, key=lambda d: d["tier"])[:args.limit]

    endpoint = "fast" if args.endpoint == "auto" else args.endpoint
    client = Client(endpoint)
    try:
        results = compute_all(munis, dests, client, use_cache=not args.no_cache)
    except HTTPStatusError as e:
        if e.code in (401, 403):
            sys.exit(f"TravelTime rejected the credentials ({e}).\n"
                     "Check TRAVELTIME_APP_ID / TRAVELTIME_API_KEY on https://account.traveltime.com")
        if args.endpoint != "auto":
            raise
        print(f"fast endpoint failed ({e}); falling back to regular /time-filter")
        client = Client("regular")
        results = compute_all(munis, dests, client, use_cache=not args.no_cache)

    cities, rows = aggregate(munis, dests, results)
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "params": {
            "mode": "public_transport",
            "arrival": "weekday morning" if client.endpoint == "fast" else next_weekday_8am(),
            "endpoint": client.endpoint,
            "max_minutes": MAX_SECONDS // 60,
            "population_year": places["meta"].get("population_year"),
            "notes": places["meta"].get("notes", []),
        },
        # [code, name, tier, lat, lng, metro, population]
        "cities": [[d["code"], d["name"], d["tier"], d["lat"], d["lng"], d.get("metro"), d.get("pop")]
                   for d in cities],
        # code -> [t1_min, t1_city, t2_min, t2_city, t3_min, t3_city, urban, population]
        "m": {},
    }
    by_code = {m["code"]: m for m in munis}
    for c, r in rows.items():
        output["m"][c] = r + [1 if by_code[c]["urban"] else 0, by_code[c].get("pop")]
    dump_json(output, OUTPUT_FILE, compact=True)
    print(f"Wrote {OUTPUT_FILE} ({client.calls} API calls)")


if __name__ == "__main__":
    main()
