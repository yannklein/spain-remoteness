"""France step 1: data/fr/places.json and web/public/data/fr/municipalities.topo.json.

- Communes of metropolitan France from geo.api.gouv.fr (INSEE code, name,
  department, population = latest *populations légales*, town-hall point).
  The town hall (`mairie`) is the travel origin, like Spain's town centres; the
  commune centroid is the fallback.
- City tiers (nested): 1 central communes of the 22 métropoles; 2 + every
  préfecture + communes over 100k; 3 + communes over 50k.
- Boundaries: Etalab "contours administratifs" (communes, 100 m simplification),
  converted to TopoJSON (communes + departments) with mapshaper. Only communes
  present in both the API and the boundaries are kept, so the two always match.

Usage: python pipeline/build_places_fr.py
"""

import gzip
import json
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone

from common import dump_json, http, paths
from countries import fr

API = "https://geo.api.gouv.fr/communes"
CONTOURS = "https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/{year}/geojson/communes-100m.geojson.gz"
P = paths("fr")


def resolve(named, communes):
    """{(department, name)} -> {INSEE code}; exits if any is missing."""
    by = {(c["codeDepartement"], c["nom"]): c["code"] for c in communes}
    missing = sorted(n for n in named if n not in by)
    if missing:
        sys.exit(f"not found in the commune list: {missing}")
    return {by[n] for n in named}


def build(communes, metropoles, prefectures):
    metro_codes = resolve(metropoles, communes)
    pref_codes = resolve(prefectures, communes)
    out = []
    for c in communes:
        dep = c["codeDepartement"]
        if dep not in fr.METRO_DEPARTMENTS:
            continue
        pop = c.get("population") or 0
        if c["code"] in metro_codes:
            tier = 1
        elif c["code"] in pref_codes or pop > 100_000:
            tier = 2
        elif pop > 50_000:
            tier = 3
        else:
            tier = None
        point = "mairie" if c.get("mairie") else "centroid"
        lng, lat = (c.get("mairie") or c["centre"])["coordinates"]
        out.append({"code": c["code"], "name": c["nom"], "province": dep, "lat": round(lat, 5), "lng": round(lng, 5),
                    "point": point, "pop": c.get("population"), "tier": tier, "urban": tier is not None,
                    "zone": fr.zone_of(dep)})
    return out


def fetch_communes():
    out = []
    for dep in fr.METRO_DEPARTMENTS:
        q = urllib.parse.urlencode({"codeDepartement": dep, "fields": "nom,code,codeDepartement,population,mairie,centre"})
        out += json.loads(http(f"{API}?{q}", timeout=120))
    return out


def fetch_contours():
    for year in (datetime.now().year, datetime.now().year - 1):
        f = P.cache / "base" / f"communes-100m-{year}.geojson"
        if f.exists():
            return f, year
        try:
            raw = http(CONTOURS.format(year=year), timeout=600)
        except Exception as e:  # noqa: BLE001 - try the previous year
            print(f"  contours {year}: {e}")
            continue
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(gzip.decompress(raw))
        return f, year
    sys.exit("no commune boundaries available")


def build_topology(geojson, keep, dest):
    """Communes (id = INSEE code, name) + departments, as TopoJSON, metropolitan only."""
    with open(geojson, encoding="utf-8") as fh:
        gj = json.load(fh)
    gj["features"] = [{"type": "Feature", "geometry": f["geometry"],
                       "properties": {"id": f["properties"]["code"], "name": f["properties"]["nom"],
                                      "dep": f["properties"]["code"][:2]}}
                      for f in gj["features"] if f["properties"]["code"] in keep]
    filtered = geojson.with_name("communes-metro.geojson")
    filtered.write_text(json.dumps(gj), encoding="utf-8")
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["npx", "--yes", "mapshaper@0.6",
           "-i", str(filtered), "name=municipalities",
           "-simplify", "12%", "keep-shapes",   # ~35k communes: keep the page download reasonable
           "-dissolve", "dep", "+", "name=provinces",
           "-target", "municipalities,provinces",
           "-o", "format=topojson", "quantization=30000", "id-field=id", str(dest)]
    subprocess.run(cmd, check=True)


def main():
    communes = fetch_communes()
    print(f"{len(communes)} communes from geo.api.gouv.fr")
    contours, year = fetch_contours()
    with open(contours, encoding="utf-8") as fh:
        contour_codes = {f["properties"]["code"] for f in json.load(fh)["features"]}
    places = [p for p in build(communes, fr.METROPOLES, fr.PREFECTURES) if p["code"] in contour_codes]
    dropped = {c["code"] for c in communes if c["codeDepartement"] in fr.METRO_DEPARTMENTS} - {p["code"] for p in places}
    if dropped:
        print(f"  {len(dropped)} communes without boundaries {year} dropped: {sorted(dropped)[:10]}")
    build_topology(contours, {p["code"] for p in places}, P.topo)
    meta = {"built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "country": "fr",
            "population_source": "INSEE populations légales via geo.api.gouv.fr", "population_year": None,
            "boundaries": f"Etalab contours administratifs {year} (communes, 100 m)",
            "destinations_per_tier": {t: sum(1 for p in places if p["tier"] and p["tier"] <= t) for t in (1, 2, 3)},
            "notes": []}
    dump_json({"meta": meta, "municipalities": places}, P.places, compact=True)
    print(f"Wrote {P.places} ({len(places)} communes; tiers {meta['destinations_per_tier']}) and {P.topo}")


if __name__ == "__main__":
    main()
