"""Step 1: build data/places.json.

For every municipality: a representative point (the OSM town centre if
available, else the geometric centroid), the latest INE population, and
whether it is a "main city" destination for tier 1, 2 or 3.

Sources (each with a graceful fallback):
  * INE table 29005 "Cifras oficiales del padrón por municipio"
  * OpenStreetMap admin_centre nodes via the Overpass API

Usage: python pipeline/build_places.py [--offline]
"""

import csv
import io
import sys
from datetime import datetime, timezone

import cities
from common import BASE_FILE, PLACES_FILE, dump_json, haversine_km, http, load_json

INE_URL = "https://www.ine.es/jaxiT3/files/t/csv_bdsc/29005.csv"
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
OVERPASS_QUERY = """
[out:json][timeout:900];
area["ISO3166-1"="ES"][admin_level=2]->.es;
rel(area.es)["boundary"="administrative"]["admin_level"="8"]["ine:municipio"]->.m;
.m out body;
node(r.m:"admin_centre");
out skel;
"""

URBAN_POP = 50_000
HUB_POP = 100_000


def _num(s):
    s = (s or "").strip().replace(".", "").replace(" ", "")
    if not s or s in {"..", "-"}:
        return None
    try:
        return int(float(s.replace(",", ".")))
    except ValueError:
        return None


def parse_ine_csv(text):
    """Return ({code: population}, year) for the latest year in INE table 29005."""
    text = text.lstrip("﻿")
    dialect = ";" if text.count(";") > text.count("\t") else "\t"
    reader = csv.reader(io.StringIO(text), delimiter=dialect)
    header = [h.strip().lower() for h in next(reader)]

    def col(*names):
        for i, h in enumerate(header):
            if any(n in h for n in names):
                return i
        return None

    i_mun, i_sex, i_per, i_tot = col("municipio"), col("sexo"), col("periodo"), col("total")
    if None in (i_mun, i_per, i_tot):
        raise ValueError(f"unexpected INE header: {header}")
    by_year = {}
    for row in reader:
        if len(row) <= max(i_mun, i_per, i_tot):
            continue
        if i_sex is not None and row[i_sex].strip().lower() not in {"total", "ambos sexos"}:
            continue
        code = row[i_mun].strip()[:5]
        if not code.isdigit():
            continue
        pop = _num(row[i_tot])
        if pop is None:
            continue
        year = row[i_per].strip()[:4]
        by_year.setdefault(year, {})[code] = pop
    if not by_year:
        raise ValueError("no rows parsed from INE csv")
    year = max(by_year)
    return by_year[year], int(year)


def fetch_population():
    print("Fetching INE population (table 29005)...")
    raw = http(INE_URL, timeout=300).decode("utf-8", errors="replace")
    pops, year = parse_ine_csv(raw)
    print(f"  {len(pops)} municipalities, year {year}")
    return pops, year


def parse_overpass(payload):
    """Return {ine_code: (lat, lng)} from relations + admin_centre nodes."""
    nodes = {}
    rels = []
    for el in payload.get("elements", []):
        if el["type"] == "node":
            nodes[el["id"]] = (el["lat"], el["lon"])
        elif el["type"] == "relation":
            rels.append(el)
    out = {}
    for rel in rels:
        code = (rel.get("tags", {}).get("ine:municipio") or "").strip()
        if not code.isdigit():
            continue
        code = code[:5].zfill(5)
        for mem in rel.get("members", []):
            if mem.get("type") == "node" and mem.get("role") == "admin_centre":
                if mem["ref"] in nodes:
                    out[code] = nodes[mem["ref"]]
                break
    return out


def fetch_town_centres():
    import json

    print("Fetching OSM admin_centre nodes from Overpass...")
    last = None
    for url in OVERPASS_URLS:
        try:
            raw = http(url, data=("data=" + OVERPASS_QUERY).encode(),
                       headers={"Content-Type": "application/x-www-form-urlencoded"},
                       timeout=1200, retries=2)
            centres = parse_overpass(json.loads(raw))
            print(f"  {len(centres)} town centres from {url}")
            return centres
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"  {url} failed: {e}")
    raise RuntimeError(f"all Overpass endpoints failed: {last}")


def metro_label(m, by_code):
    for metro, (core, prov) in cities.METRO_CORES.items():
        if m["code"] == core or m["code"][:2] != prov:
            continue
        c = by_code[core]
        if haversine_km(m["lat"], m["lng"], c["lat"], c["lng"]) <= cities.METRO_RADIUS_KM:
            return metro
    return None


def classify(munis, pops):
    """Set pop, urban, tier (1/2/3 or None) and metro on each municipality."""
    by_code = {m["code"]: m for m in munis}
    capitals = set(cities.PROVINCIAL_CAPITALS) | set(cities.OTHER_REGIONAL_CAPITALS)
    have_pop = bool(pops)
    for m in munis:
        code = m["code"]
        pop = pops.get(code) if have_pop else None
        m["pop"] = pop
        tier = None
        if code in cities.METROS:
            tier = 1
        elif code in capitals:
            tier = 2
        elif have_pop and pop is not None and pop >= HUB_POP:
            tier = 2
        elif not have_pop and code in cities.OVER_100K_FALLBACK:
            tier = 2
        elif have_pop and pop is not None and pop >= URBAN_POP:
            tier = 3
        m["tier"] = tier
        m["urban"] = tier is not None
        metro = None
        if code in cities.OVER_100K_FALLBACK:
            metro = cities.OVER_100K_FALLBACK[code][1]
        elif tier is not None and tier > 1 and code not in capitals:
            metro = metro_label(m, by_code)
        if metro:
            m["metro"] = metro
    return munis


def main(offline=False):
    base = load_json(BASE_FILE)["municipalities"]
    munis = [dict(m) for m in base]
    notes = []

    pops, pop_year = {}, None
    centres = {}
    if not offline:
        try:
            pops, pop_year = fetch_population()
        except Exception as e:  # noqa: BLE001
            notes.append(f"INE population unavailable ({e}); tier 3 falls back to tier 2")
            print("  WARNING:", notes[-1])
        try:
            centres = fetch_town_centres()
        except Exception as e:  # noqa: BLE001
            notes.append(f"OSM town centres unavailable ({e}); using geometric centroids")
            print("  WARNING:", notes[-1])

    for m in munis:
        if m["code"] in centres:
            m["lat"], m["lng"] = (round(v, 5) for v in centres[m["code"]])
            m["point"] = "osm"
        else:
            m["point"] = "centroid"

    classify(munis, pops)
    counts = {t: sum(1 for m in munis if m["tier"] is not None and m["tier"] <= t) for t in (1, 2, 3)}
    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "population_year": pop_year,
        "town_centres_from_osm": sum(1 for m in munis if m["point"] == "osm"),
        "destinations_per_tier": counts,
        "notes": notes,
    }
    print("Destinations per tier:", counts)
    dump_json({"meta": meta, "municipalities": munis}, PLACES_FILE, compact=True)
    print(f"Wrote {PLACES_FILE}")


if __name__ == "__main__":
    main(offline="--offline" in sys.argv)
