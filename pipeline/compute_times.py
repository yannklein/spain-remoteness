"""Step 2: public transport travel times to the nearest main city.

For every destination city we ask TravelTime how long it takes to arrive
there by public transport from every municipality in the same zone
(mainland / island / Ceuta / Melilla) within MAX_KM, and keep the best
of several weekday arrival times ("best connection of the day").
Up to 3 hours is measured; anything slower is "3h+ / unreachable".

Then, per municipality and per tier, we keep the fastest city.

Why the regular /time-filter endpoint: the /fast one only knows a generic
"weekday morning" profile and misses many regional connections (see
pipeline/diagnose.py: La Rinconada -> Sevilla, Benavente -> Zamora...).

Env: TRAVELTIME_APP_ID, TRAVELTIME_API_KEY
Usage: python pipeline/compute_times.py [--limit N] [--endpoint regular|fast]
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import common
import crossborder
from common import (CACHE_DIR, CITIES_CSV, OUTPUT_FILE, PLACES_FILE, HTTPStatusError, add_country_arg,
                    dump_json, haversine_km, http, load_json, paths, write_csv, zone)

API = "https://api.traveltimeapp.com/v4"
MAX_SECONDS = 10800              # 3 h cap
MAX_KM = 300                     # beyond this, 3 h by public transport is out of reach (AVE included)
ARRIVAL_TIMES = ["08:30", "11:30", "14:30"]   # Madrid local time, on a Tuesday
SEARCHES_PER_REQUEST = 10
CHUNK = 1999                     # regular endpoint: 2,000 ids per search, minus the arrival location
SECONDS_PER_SEARCH = 0.55        # free keys allow ~120 searches/min; each search is a "hit"
TIERS = (1, 2, 3)


def headers():
    app_id = os.environ.get("TRAVELTIME_APP_ID")
    key = os.environ.get("TRAVELTIME_API_KEY")
    if not app_id or not key:
        sys.exit("TRAVELTIME_APP_ID and TRAVELTIME_API_KEY must be set")
    return {"Content-Type": "application/json", "X-Application-Id": app_id, "X-Api-Key": key}


def next_tuesday():
    tz = ZoneInfo("Europe/Madrid")
    d = datetime.now(tz) + timedelta(days=1)
    while d.weekday() != 1:
        d += timedelta(days=1)
    return d.date()


def arrival_times(times=ARRIVAL_TIMES):
    """Next Tuesday at each local time, as UTC ISO strings."""
    tz = ZoneInfo("Europe/Madrid")
    day = next_tuesday()
    out = []
    for t in times:
        h, m = map(int, t.split(":"))
        local = datetime(day.year, day.month, day.day, h, m, tzinfo=tz)
        out.append(local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    return out


def next_weekday_8am():
    """First arrival time (kept for diagnose.py)."""
    return arrival_times()[0]


def origins_for(dest, munis, max_km=MAX_KM):
    """Municipalities in the destination's zone within max_km (a destination may set its own "max_km")."""
    z = zone(dest)
    max_km = dest.get("max_km", max_km)
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


def _locations(locs):
    return [{"id": c, "coords": {"lat": m["lat"], "lng": m["lng"]}} for c, m in locs.items()]


class Client:
    def __init__(self, endpoint="regular"):
        self.endpoint = endpoint
        self.headers = headers()
        self.next_allowed = 0.0
        self.calls = 0

    def post(self, path, body):
        wait = self.next_allowed - time.time()
        if wait > 0:
            time.sleep(wait)
        searches = body["arrival_searches"]
        n = len(searches["many_to_one"]) if isinstance(searches, dict) else len(searches)
        self.next_allowed = time.time() + n * SECONDS_PER_SEARCH
        self.calls += 1
        return json.loads(http(f"{API}{path}", data=body, headers=self.headers, timeout=300))

    def fast(self, batch):
        """batch: list of (dest, origins). One request, up to 10 searches."""
        locs, searches = {}, []
        for dest, origins in batch:
            locs[dest["code"]] = dest
            locs.update((o["code"], o) for o in origins)
            searches.append({
                "id": dest["code"],
                "arrival_location_id": dest["code"],
                "departure_location_ids": [o["code"] for o in origins],
                "transportation": {"type": "public_transport"},
                "arrival_time_period": "weekday_morning",
                "travel_time": MAX_SECONDS,
                "properties": ["travel_time"],
            })
        body = {"locations": _locations(locs), "arrival_searches": {"many_to_one": searches}}
        return parse_results(self.post("/time-filter/fast", body))

    def regular(self, batch, times):
        """Same as fast(), via /time-filter: one search per (city, arrival time, chunk of
        2,000 origins), 10 searches per request, keeping the best time per origin."""
        out = {}
        searches, locs = [], {}

        def flush():
            if not searches:
                return
            body = {"locations": _locations(locs), "arrival_searches": list(searches)}
            for sid, got in parse_results(self.post("/time-filter", body)).items():
                best = out.setdefault(sid.split("#")[0], {})
                for oid, t in got.items():
                    if oid not in best or t < best[oid]:
                        best[oid] = t
            searches.clear()
            locs.clear()

        for dest, origins in batch:
            for at in times:
                for i in range(0, len(origins), CHUNK):
                    chunk = origins[i:i + CHUNK]
                    locs[dest["code"]] = dest
                    locs.update((o["code"], o) for o in chunk)
                    searches.append({
                        "id": f"{dest['code']}#{at}#{i}",
                        "arrival_location_id": dest["code"],
                        "departure_location_ids": [o["code"] for o in chunk],
                        "transportation": {"type": "public_transport"},
                        "arrival_time": at,
                        "travel_time": MAX_SECONDS,
                        "properties": ["travel_time"],
                    })
                    if len(searches) == SEARCHES_PER_REQUEST:
                        flush()
        flush()
        return out


def cache_dir(client):
    """Separate cache per method, so a config change never reuses stale results."""
    tag = "fast" if client.endpoint == "fast" else "regular-" + "-".join(t.replace(":", "") for t in ARRIVAL_TIMES)
    return CACHE_DIR / tag


def compute_all(munis, dests, client, use_cache=True, cdir=None):
    """Return {dest_code: {origin_code: seconds}}, using/refreshing the disk cache."""
    cdir = cdir or cache_dir(client)
    cdir.mkdir(parents=True, exist_ok=True)
    results, todo = {}, []
    for d in dests:
        f = cdir / f"{d['code']}.json"
        if use_cache and f.exists():
            results[d["code"]] = load_json(f)
        else:
            todo.append(d)
    print(f"{len(dests)} destinations, {len(dests) - len(todo)} cached, {len(todo)} to compute "
          f"({client.endpoint} endpoint)")

    times = arrival_times() if client.endpoint == "regular" else None
    # one city per batch for the regular endpoint (its chunks already fill a request);
    # 10 per batch for fast. Cities are grouped by zone so a batch shares its origins.
    per_batch = 1 if client.endpoint == "regular" else SEARCHES_PER_REQUEST
    todo.sort(key=lambda d: (zone(d), d["code"]))
    for i in range(0, len(todo), per_batch):
        group = todo[i:i + per_batch]
        batch = [(d, origins_for(d, munis)) for d in group]
        print(f"[{i + len(group)}/{len(todo)}] " + ", ".join(d["name"] for d in group))
        # a city alone in its zone (Ceuta, Melilla, Eivissa...) has nobody to reach it
        to_ask = [(d, o) for d, o in batch if o]
        got = {}
        if to_ask:
            got = client.fast(to_ask) if client.endpoint == "fast" else client.regular(to_ask, times)
        for d, _ in batch:
            res = got.get(d["code"], {})
            res[d["code"]] = 0
            results[d["code"]] = res
            dump_json(res, cdir / f"{d['code']}.json", compact=True)
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


def aggregate_with_border(munis, dests, results, xb):
    """aggregate(), with foreign cities estimated through border stations; also returns the via slots.

    Per tier, a border station inside a home city that already counts at that tier is not used: the
    trip passes through that city, so the foreign city is never the nearest one (Lille-Flandres -> Tournai).
    """
    ids = crossborder.gateway_ids(xb)
    if not xb:
        cities, rows = aggregate(munis, dests, results)
        return cities, rows, {m: None for m in rows}
    from geo import MuniIndex, load_municipalities
    tier_of = {m["code"]: m.get("tier") for m in munis}
    gw_tier = crossborder.gateway_city_tiers(xb, MuniIndex(load_municipalities(common.TOPO_FILE)).locate, tier_of.get)
    codes = {d["code"] for d in dests}
    hops = [h for h in xb.HOPS if h[1] in codes]
    muni_codes = set(tier_of)
    cities, rows, slots = None, None, {}
    for tier in TIERS:
        res = dict(results)  # apply_hops copies the per-destination dicts it changes
        via = crossborder.apply_hops(res, crossborder.hops_for_tier(hops, gw_tier, tier), muni_codes, MAX_SECONDS)
        cities, rows_t = aggregate(munis, dests, res)
        slots_t = crossborder.via_slots(rows_t, cities, via, ids)
        if rows is None:
            rows = {m: list(r) for m, r in rows_t.items()}
        k = (tier - 1) * 2
        for m, r in rows_t.items():
            rows[m][k:k + 2] = r[k:k + 2]
            slots.setdefault(m, [-1] * len(TIERS))[tier - 1] = slots_t[m][tier - 1] if slots_t[m] else -1
    return cities, rows, {m: (v if any(x >= 0 for x in v) else None) for m, v in slots.items()}


def cities_csv_rows(output, munis):
    """One row per municipality: minutes and code of the nearest city per tier, then the border
    station each time goes through when it is an estimate (empty when measured)."""
    header = ["code", "name", "province", "population",
              "t1_min", "t1_city", "t2_min", "t2_city", "t3_min", "t3_city", "t1_via", "t2_via", "t3_via"]
    gateways = output.get("gateways", [])
    rows = []
    for m in munis:
        r = output["m"].get(m["code"])
        row = [m["code"], m["name"], m.get("province"), m.get("pop")]
        for tier in TIERS:
            t, c = (r[(tier - 1) * 2], r[(tier - 1) * 2 + 1]) if r else (-1, -1)
            row += [None, None] if t < 0 else [t, output["cities"][c][0]]
        via = r[8] if r and len(r) > 8 and r[8] else [-1, -1, -1]
        row += [gateways[g][1] if g >= 0 else None for g in via]
        rows.append(row)
    return header, rows


def configure(cc):
    """Point this module (and common) at a country's folders."""
    global CACHE_DIR, OUTPUT_FILE, CITIES_CSV, PLACES_FILE
    p = paths(cc)
    CACHE_DIR, OUTPUT_FILE, CITIES_CSV, PLACES_FILE = p.times_cache, p.cities_json, p.cities_csv, p.places
    common.TOPO_FILE, common.PLACES_FILE = p.topo, p.places


def main():
    ap = argparse.ArgumentParser()
    add_country_arg(ap)
    ap.add_argument("--limit", type=int, help="only compute the first N destinations (testing)")
    ap.add_argument("--endpoint", choices=["regular", "fast"], default="regular")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--csv-only", action="store_true",
                    help="rewrite the CSV from the existing JSON, no API calls")
    args = ap.parse_args()
    if args.country != "es":
        configure(args.country)

    places = load_json(PLACES_FILE)
    munis = places["municipalities"]
    if args.csv_only:
        write_csv(CITIES_CSV, *cities_csv_rows(load_json(OUTPUT_FILE), munis))
        print(f"Wrote {CITIES_CSV}")
        return
    dests = [m for m in munis if m["tier"] is not None]
    if args.limit:
        dests = sorted(dests, key=lambda d: d["tier"])[:args.limit]
    # foreign cities, measured directly nearby and estimated through border stations
    xb = None if args.limit else crossborder.config(args.country)
    foreign, gateways = crossborder.foreign_city_dests(xb), crossborder.gateway_dests(xb)

    client = Client(args.endpoint)
    try:
        results = compute_all(munis, dests + foreign + gateways, client, use_cache=not args.no_cache)
    except HTTPStatusError as e:
        if e.code in (401, 403):
            sys.exit(f"TravelTime rejected the credentials ({e}).\n"
                     "Check TRAVELTIME_APP_ID / TRAVELTIME_API_KEY on https://account.traveltime.com")
        raise

    cities, rows, slots = aggregate_with_border(munis, dests + foreign, results, xb)
    notes = list(places["meta"].get("notes", []))
    if xb:
        notes.append(f"Cities across the border count too: TravelTime has almost no cross-border public transport, "
                     f"so they are reached through border stations (time to the station + the scheduled ride + "
                     f"{crossborder.TRANSFER_MIN} min to change); those times are estimates.")
    arrival = ("weekday morning (fast endpoint profile)" if client.endpoint == "fast"
               else f"best of {', '.join(ARRIVAL_TIMES)} on a Tuesday")
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "params": {
            "mode": "public_transport",
            "arrival": arrival,
            "arrival_times": ARRIVAL_TIMES if client.endpoint == "regular" else [],
            "endpoint": client.endpoint,
            "max_minutes": MAX_SECONDS // 60,
            "population_year": places["meta"].get("population_year"),
            "notes": notes,
        },
        # [code, name, tier, lat, lng, metro, population]
        "cities": [[d["code"], d["name"], d["tier"], d["lat"], d["lng"], d.get("metro"), d.get("pop")]
                   for d in cities],
        # border stations estimates go through: [id, name, lat, lng]
        "gateways": crossborder.gateway_list(xb),
        # code -> [t1_min, t1_city, t2_min, t2_city, t3_min, t3_city, urban, population, via]
        # via: null when every time is measured, else the gateway index per tier (-1 = measured)
        "m": {},
    }
    by_code = {m["code"]: m for m in munis}
    for c, r in rows.items():
        output["m"][c] = r + [1 if by_code[c]["urban"] else 0, by_code[c].get("pop"), slots[c]]
    dump_json(output, OUTPUT_FILE, compact=True)
    write_csv(CITIES_CSV, *cities_csv_rows(output, munis))
    print(f"Wrote {OUTPUT_FILE} and {CITIES_CSV.name} ({client.calls} API calls)")


if __name__ == "__main__":
    main()
