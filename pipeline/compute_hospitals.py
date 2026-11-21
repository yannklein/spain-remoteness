"""Public transport travel times to the nearest hospital, by hospital tier.

Same method as compute_times.py / compute_airports.py (TravelTime /time-filter,
best of three Tuesday arrivals, 3 h cap, origins within 300 km in the same zone),
with the hospitals placed by place_hospitals.py (data/hospitals.json) as
destinations. Tiers (hospitals.py): 1 major, 2 public, 3 any general hospital.

Env: TRAVELTIME_APP_ID, TRAVELTIME_API_KEY
Usage: python pipeline/compute_hospitals.py [--limit N] [--only CODCNH,...] [--no-cache]
       --limit / --only write no output files.
"""

import argparse
import sys
from datetime import datetime, timezone

from common import (DATA, PLACES_FILE, ROOT, HTTPStatusError, dump_json, load_json, write_csv, zone)
from compute_times import ARRIVAL_TIMES, MAX_SECONDS, TIERS, Client, cache_dir, compute_all

PLACED_FILE = DATA / "hospitals.json"
OUTPUT_FILE = ROOT / "web" / "public" / "data" / "hospitals.json"
CSV_FILE = ROOT / "web" / "public" / "data" / "hospitals.csv"
CACHE_DIR = ROOT / ".cache" / "hospitals"
SOURCE = "Catálogo Nacional de Hospitales 2025, Ministerio de Sanidad"


def destinations(placed, places):
    """Hospitals as TravelTime destinations; zone from their municipality (islands, Ceuta, Melilla)."""
    by = {m["code"]: m for m in places["municipalities"]}
    out = []
    for h in placed:
        if not h.get("tier") or h.get("lat") is None:
            continue
        m = by.get(h["muni"], {"code": h["muni"]})
        out.append(dict(h, code="HOS:" + h["codcnh"], zone=zone(m)))
    return out


def _order(h):
    return (h["tier"], -(h.get("beds") or 0), h["name"])


def aggregate_hospitals(munis, hospitals, results):
    """Per municipality [t1, h1, t2, h2, t3, h3]: minutes (-1 = none within the cap), hospital index (-1)."""
    hs = sorted(hospitals, key=_order)
    out = {}
    for m in munis:
        row = []
        for tier in TIERS:
            best_t, best_i = None, -1
            for i, h in enumerate(hs):
                if h["tier"] > tier:
                    continue
                t = results.get(h["code"], {}).get(m["code"])
                if t is not None and (best_t is None or t < best_t):
                    best_t, best_i = t, i
            row += [-1, -1] if best_t is None else [round(best_t / 60), best_i]
        out[m["code"]] = row
    return hs, out


def build_output(places, hospitals, rows, results):
    by = {m["code"]: m for m in places["municipalities"]}
    reach = {h["code"]: sum(1 for k in results.get(h["code"], {}) if not k.startswith("HOS:")) for h in hospitals}
    dead = [f"{h['name']} ({by.get(h['muni'], {}).get('name', h['muni'])})" for h in hospitals if not reach[h["code"]]]
    notes = []
    if dead:
        notes.append("Not reached by anyone in TravelTime's data (arrival point may not attach to the network): "
                     + ", ".join(dead) + ".")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "params": {
            "mode": "public_transport",
            "arrival": f"best of {', '.join(ARRIVAL_TIMES)} on a Tuesday",
            "arrival_times": ARRIVAL_TIMES,
            "max_minutes": MAX_SECONDS // 60,
            "source": SOURCE,
            "population_year": places["meta"].get("population_year"),
            "notes": notes,
        },
        # [codcnh, name, muni, lat, lng, tier, beds, public, cath_lab, reach, point_source]
        "hospitals": [[h["codcnh"], h["name"], h["muni"], h["lat"], h["lng"], h["tier"], h.get("beds"),
                       1 if h.get("public") else 0, 1 if h.get("cath_lab") else 0, reach[h["code"]],
                       h.get("point_source")] for h in hospitals],
        # code -> [t1, h1, t2, h2, t3, h3, population]
        "m": {c: r + [by[c].get("pop")] for c, r in rows.items()},
    }


def hospitals_csv_rows(output, munis):
    header = ["code", "name", "province", "population"]
    for tier in TIERS:
        header += [f"t{tier}_min", f"t{tier}_hospital"]
    rows = []
    for m in munis:
        r = output["m"].get(m["code"], [-1] * 6)
        row = [m["code"], m["name"], m.get("province"), m.get("pop")]
        for k in range(3):
            t, i = r[k * 2], r[k * 2 + 1]
            row += [None, None] if t < 0 else [t, output["hospitals"][i][0]]
        rows.append(row)
    return header, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="only compute the first N hospitals (testing)")
    ap.add_argument("--only", help="comma-separated CODCNH codes to compute (testing)")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    places = load_json(PLACES_FILE)
    munis = places["municipalities"]
    dests = destinations(load_json(PLACED_FILE), places)
    partial = bool(args.limit or args.only)
    if args.only:
        wanted = {c.strip() for c in args.only.split(",")}
        dests = [d for d in dests if d["codcnh"] in wanted]
    if args.limit:
        dests = sorted(dests, key=_order)[:args.limit]

    client = Client("regular")
    cdir = CACHE_DIR / cache_dir(client).name
    try:
        results = compute_all(munis, dests, client, use_cache=not args.no_cache, cdir=cdir)
    except HTTPStatusError as e:
        if e.code in (401, 403):
            sys.exit(f"TravelTime rejected the credentials ({e}).\n"
                     "Check TRAVELTIME_APP_ID / TRAVELTIME_API_KEY on https://account.traveltime.com")
        raise

    if partial:
        for d in dests:
            n = sum(1 for k in results.get(d["code"], {}) if not k.startswith("HOS:"))
            print(f"  {d['name']}: reached from {n} municipalities")
        print(f"Partial run ({len(dests)} hospitals): no output written ({client.calls} API calls)")
        return

    hs, rows = aggregate_hospitals(munis, dests, results)
    output = build_output(places, hs, rows, results)
    dump_json(output, OUTPUT_FILE, compact=True)
    write_csv(CSV_FILE, *hospitals_csv_rows(output, munis))
    print(f"Wrote {OUTPUT_FILE} and {CSV_FILE.name} ({client.calls} API calls)")
    for n in output["params"]["notes"]:
        print(" ", n)


if __name__ == "__main__":
    main()
