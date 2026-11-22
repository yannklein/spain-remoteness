"""Public transport travel times to the nearest airport, by airport category.

Same method as compute_times.py (TravelTime /time-filter, best of three
Tuesday arrivals, 3 h cap, origins within 300 km in the same zone), with
airports from airports.py as destinations. Each airport is computed once;
the nearest airport is then picked for 3 nested tiers x 2 variants
(year-round routes only / seasonal routes included).

Env: TRAVELTIME_APP_ID, TRAVELTIME_API_KEY
Usage: python pipeline/compute_airports.py [--limit N] [--only MAD,OPO] [--no-cache]
       --limit / --only print a border sample and write no output files.
"""

import argparse
import sys
from datetime import datetime, timezone

import airports as airport_list
import common
import crossborder
from common import (AIRPORT_CACHE_DIR, AIRPORTS_CSV, AIRPORTS_OUTPUT_FILE, PLACES_FILE,
                    HTTPStatusError, add_country_arg, dump_json, load_json, paths, write_csv)
from compute_times import (ARRIVAL_TIMES, MAX_SECONDS, TIERS, Client, cache_dir,
                           compute_all)

COUNTRY = {"ES": "Spain", "PT": "Portugal", "FR": "France", "GI": "Gibraltar"}

# (municipality, airport) pairs printed after every run: cross-border links
# depend on TravelTime having the buses/trains that cross the border.
BORDER_CHECKS = [("36057", "OPO"), ("06015", "LIS"), ("20045", "BIQ"), ("17066", "PGF"),
                 ("11022", "GIB"), ("21010", "FAO"), ("25243", "TLS")]


def _order(a):
    return (a["tier_summer"] or 9, a["tier_year"] or 9, a["name"])


def aggregate_airports(munis, airports, results):
    """Per municipality: [y1, ya1, y2, ya2, y3, ya3, s1, sa1, s2, sa2, s3, sa3].

    y* uses tier_year, s* tier_summer; minutes rounded, airport index into
    the returned (sorted) list, -1/-1 when no eligible airport within the cap.
    """
    aps = sorted(airports, key=_order)
    out = {}
    for m in munis:
        row = []
        for key in ("tier_year", "tier_summer"):
            for tier in TIERS:
                best_t, best_i = None, -1
                for i, a in enumerate(aps):
                    if a[key] is None or a[key] > tier:
                        continue
                    t = results.get(a["code"], {}).get(m["code"])
                    if t is not None and (best_t is None or t < best_t):
                        best_t, best_i = t, i
                row += [-1, -1] if best_t is None else [round(best_t / 60), best_i]
        out[m["code"]] = row
    return aps, out


def reach_counts(airports, results):
    """Number of municipalities that reach each airport within the cap."""
    return {a["code"]: sum(1 for k in results.get(a["code"], {}) if not k.startswith("AIR:"))
            for a in airports}


def build_output(places, airports, rows, results):
    by_code = {m["code"]: m for m in places["municipalities"]}
    reach = reach_counts(airports, results)
    dead = [f"{a['name']} ({a['iata']})" for a in airports if not reach[a["code"]]]
    notes = list(airport_list.NOTES)
    if dead:
        notes.append("No public transport link in TravelTime's data, so never the nearest: "
                     + ", ".join(dead) + ".")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "params": {
            "mode": "public_transport",
            "arrival": f"best of {', '.join(ARRIVAL_TIMES)} on a Tuesday",
            "arrival_times": ARRIVAL_TIMES,
            "max_minutes": MAX_SECONDS // 60,
            "population_year": places["meta"].get("population_year"),
            "notes": notes,
        },
        # [iata, name, country, lat, lng, tier_year, tier_summer, note, reach]
        # reach = municipalities that get there within the cap (0 = no transit link in the data)
        "airports": [[a["iata"], a["name"], a["country"], a["lat"], a["lng"],
                      a["tier_year"], a["tier_summer"], a["note"], reach[a["code"]]] for a in airports],
        # code -> [y1, ya1, y2, ya2, y3, ya3, s1, sa1, s2, sa2, s3, sa3, population]
        "m": {c: r + [by_code[c].get("pop")] for c, r in rows.items()},
    }


def airports_csv_rows(output, munis):
    """One row per municipality: minutes and IATA code of the nearest airport per variant/tier, then the
    border station each time goes through when it is an estimate (empty when measured)."""
    header = ["code", "name", "province", "population"]
    for v in ("y", "s"):
        for tier in TIERS:
            header += [f"{v}{tier}_min", f"{v}{tier}_airport"]
    header += [f"{v}{tier}_via" for v in ("y", "s") for tier in TIERS]
    gateways = output.get("gateways", [])
    rows = []
    for m in munis:
        r = output["m"].get(m["code"], [-1] * 12)
        row = [m["code"], m["name"], m.get("province"), m.get("pop")]
        for k in range(6):
            t, i = r[k * 2], r[k * 2 + 1]
            row += [None, None] if t < 0 else [t, output["airports"][i][0]]
        via = r[13] if len(r) > 13 and r[13] else [-1] * 6
        row += [gateways[g][1] if g >= 0 else None for g in via]
        rows.append(row)
    return header, rows


def print_border_checks(munis, results):
    names = {m["code"]: m["name"] for m in munis}
    for code, iata in getattr(airport_list, "BORDER_CHECKS", BORDER_CHECKS):
        got = results.get("AIR:" + iata)
        if got is None:
            continue
        t = got.get(code)
        print(f"  {names.get(code, code)} -> {iata}: " + ("unreachable" if t is None else f"{round(t / 60)} min"))


def configure(cc):
    global AIRPORT_CACHE_DIR, AIRPORTS_CSV, AIRPORTS_OUTPUT_FILE, PLACES_FILE, airport_list
    p = paths(cc)
    AIRPORT_CACHE_DIR, AIRPORTS_CSV, AIRPORTS_OUTPUT_FILE, PLACES_FILE = (
        p.airports_cache, p.airports_csv, p.airports_json, p.places)
    common.TOPO_FILE, common.PLACES_FILE = p.topo, p.places
    import importlib
    airport_list = importlib.import_module(f"countries.{cc}_airports") if cc != "es" else airport_list


def apply_points(dests, points_file):
    """Use snapped / moved airport points from data/<cc>/airport_points.json (place_airports.py)."""
    if not points_file.exists():
        return dests
    pts = load_json(points_file)
    out = []
    for d in dests:
        p = pts.get(d["iata"], {})
        out.append(dict(d, lat=p["lat"], lng=p["lng"]) if "lat" in p else d)
    return out


def main():
    ap = argparse.ArgumentParser()
    add_country_arg(ap)
    ap.add_argument("--limit", type=int, help="only compute the first N airports (testing)")
    ap.add_argument("--only", help="comma-separated IATA codes to compute (testing)")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()
    if args.country != "es":
        configure(args.country)

    places = load_json(PLACES_FILE)
    munis = places["municipalities"]
    dests = apply_points(airport_list.destinations(), PLACES_FILE.parent / "airport_points.json")
    partial = bool(args.limit or args.only)
    if args.only:
        wanted = {c.strip().upper() for c in args.only.split(",")}
        dests = [d for d in dests if d["iata"] in wanted]
    if args.limit:
        dests = sorted(dests, key=_order)[:args.limit]

    client = Client("regular")
    cdir = AIRPORT_CACHE_DIR / cache_dir(client).name
    cdir.mkdir(parents=True, exist_ok=True)
    from compute_hospitals import invalidate_moved
    invalidate_moved(dests, cdir, cdir / "positions.json")
    try:
        results = compute_all(munis, dests, client, use_cache=not args.no_cache, cdir=cdir)
    except HTTPStatusError as e:
        if e.code in (401, 403):
            sys.exit(f"TravelTime rejected the credentials ({e}).\n"
                     "Check TRAVELTIME_APP_ID / TRAVELTIME_API_KEY on https://account.traveltime.com")
        raise

    print("Border checks:")
    print_border_checks(munis, results)
    if partial:
        print(f"Partial run ({len(dests)} airports): no output written ({client.calls} API calls)")
        return

    # foreign airports estimated through border stations (shared with compute_times: same cache)
    xb = crossborder.config(args.country)
    gw_cdir = paths(args.country).times_cache / cache_dir(client).name
    results.update(compute_all(munis, crossborder.gateway_dests(xb), client, use_cache=not args.no_cache, cdir=gw_cdir))
    codes = {d["code"] for d in dests}
    via = crossborder.apply_hops(results, [h for h in (xb.HOPS if xb else []) if h[1] in codes],
                                 {m["code"] for m in munis}, MAX_SECONDS)
    aps, rows = aggregate_airports(munis, dests, results)
    output = build_output(places, aps, rows, results)
    slots = crossborder.via_slots(rows, aps, via, crossborder.gateway_ids(xb))
    # border stations estimates go through: [id, name, lat, lng]; each m row ends with via:
    # null when every time is measured, else the gateway index per slot (y1..y3, s1..s3; -1 = measured)
    output["gateways"] = crossborder.gateway_list(xb)
    output["m"] = {c: r + [slots[c]] for c, r in output["m"].items()}
    dump_json(output, AIRPORTS_OUTPUT_FILE, compact=True)
    write_csv(AIRPORTS_CSV, *airports_csv_rows(output, munis))
    print(f"Wrote {AIRPORTS_OUTPUT_FILE} and {AIRPORTS_CSV.name} ({client.calls} API calls)")


if __name__ == "__main__":
    main()
