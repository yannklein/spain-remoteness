"""Place catalogue hospitals on the map, using OpenStreetMap.

Each hospital of the Catálogo Nacional de Hospitales (tiers 1-3) is matched to an
OSM `amenity=hospital` in the same municipality by name. Its arrival point is the
nearest public transport stop within STOP_RADIUS_M of the OSM hospital (TravelTime
can't attach points inside a campus to its walking network), else an entrance on
the hospital outline, else the OSM centre. Hospitals OSM doesn't have are geocoded
from their address with Nominatim, then get the same stop rule.

Writes data/hospitals.json (committed, so positions can be reviewed and fixed).
Usage: python pipeline/place_hospitals.py
"""

import json
import re
import time
import unicodedata
import urllib.parse

import hospitals as catalogue
from common import PLACES_FILE, USER_AGENT, dump_json, haversine_km, http, load_json, paths
from geo import MuniIndex, load_municipalities

OUTPUT = paths("es").hospitals_placed
OVERPASS = "https://overpass-api.de/api/interpreter"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
STOP_RADIUS_M = 400
MIN_OVERLAP = 0.5
GENERIC = {
    "hospital", "hospitales", "clinica", "clinic", "clinico", "universitario", "universitaria", "universitari",
    "general", "comarcal", "de", "del", "la", "las", "el", "los", "l", "d", "i", "y", "e", "en", "s", "a",
    "centro", "centre", "sanitario", "medico", "complejo", "hospitalario", "consorci", "fundacion", "fundacio",
    "grupo", "sl", "slu", "sa", "hosp", "h", "u",
    # Basque / Galician / Catalan generic words
    "ospitalea", "ospitala", "osi", "organizacion", "sanitaria", "integrada", "complexo", "publico", "publica",
    "da", "do", "das", "dos", "alto",
    # too common in Spanish hospital names to tell hospitals apart
    "nuestra", "senora", "virgen", "san", "santa", "sant", "santo",
}
OVERRIDES = paths("es").hospital_overrides  # keyed by CODCNH (catalogue code), not municipality
OSM_CACHE = catalogue.CACHE / "osm_hospitals.json"


def normalise(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    tokens = re.findall(r"[a-z0-9]+", s)
    return " ".join(t for t in tokens if t not in GENERIC)


# word endings that still name the same place (Basque genitives: Zumarraga / Zumarragako, Bidasoa / Bidasoko)
SUFFIXES = {"", "a", "o", "e", "n", "k", "ko", "ako", "eko", "oko", "go", "ren"}
# OSM "hospitals" that are not hospitals
NOT_HOSPITALS = ("centro de salud", "centre d atencio primaria", "cap ", "urgencias", "policlinico",
                 "centro pet", "consultorio", "ambulatorio")


def _same_word(a, b):
    if a == b:
        return True
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n >= 5 and a[n:] in SUFFIXES and b[n:] in SUFFIXES


def _tokens(name, town):
    """(all distinctive words, the same without the town's name)."""
    words = set(normalise(name).split())
    town_words = set(normalise(town).split()) if town else set()
    return words, {w for w in words if not any(_same_word(w, t) for t in town_words)}


def _plain(name):
    return " ".join(re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()))


def _score(a, b):
    """(F1 of matched words, overlap on the smaller set)."""
    if not a or not b:
        return 0.0, 0.0
    small, big = (a, b) if len(a) <= len(b) else (b, a)
    m = sum(1 for w in small if any(_same_word(w, v) for v in big))
    return 2 * m / (len(a) + len(b)), m / len(small)


def match(hosp, osm_hospitals):
    """Best-fitting OSM hospital in the same municipality, or None.

    The town's name is not evidence: "Hospital Clínic de Barcelona" must not match
    "Hospital de Nens de Barcelona". A hospital named only after its town matches an
    OSM hospital also named only after the town, and only when it is the town's only
    catalogue hospital (hosp["siblings"] == 1).
    """
    town = hosp.get("muni_name")
    words, own = _tokens(hosp["name"], town)
    cands = [o for o in osm_hospitals
             if o["muni"] == hosp["muni"] and not _plain(o.get("name", "")).startswith(NOT_HOSPITALS)]
    best, key = None, (0.0, 0.0)
    for o in cands:
        o_words, o_own = _tokens(o.get("name", ""), town)
        if own and o_own:
            f1, overlap = _score(own, o_own)
        elif not own and not o_own and o_words:
            f1, overlap = _score(words, o_words)
        else:
            continue
        if overlap >= MIN_OVERLAP and (f1, overlap) > key:
            best, key = o, (f1, overlap)
    if best is None and hosp.get("siblings", 1) == 1:
        town_only = [o for o in cands if o.get("name") and not _tokens(o["name"], town)[1]]
        if len(town_only) == 1:
            best = town_only[0]
    return best


def apply_override(h, overrides, osm_hospitals):
    """Hand-set anchor from data/hospital_overrides.json: {codcnh: {"osm_name": ...} or {"lat", "lng"}}."""
    o = overrides.get(h["codcnh"])
    if not o:
        return None
    if "osm_name" not in o and "lat" not in o:  # only a probe record (see nudge_hospitals.py)
        return None
    if "osm_name" in o:
        return next((dict(c, osm_id=c["id"], via="override") for c in osm_hospitals if c.get("name") == o["osm_name"]), None)
    return {"lat": o["lat"], "lng": o["lng"], "entrances": [], "osm_id": None, "via": "override", "id": None,
            "exact": bool(o.get("exact"))}


def place_anchor(a, stops):
    """Arrival point for an anchor: exact overrides are used as-is (e.g. a point moved so it attaches)."""
    if a.get("exact"):
        return a["lat"], a["lng"], "override", None
    return pick_point(a, stops)


def pick_point(h, stops):
    """(lat, lng, source, stop_name): closest stop within STOP_RADIUS_M, else an entrance, else the centre."""
    best, dist = None, STOP_RADIUS_M / 1000
    for s in stops:
        d = haversine_km(h["lat"], h["lng"], s["lat"], s["lng"])
        if d <= dist:
            best, dist = s, d
    if best:
        return best["lat"], best["lng"], "stop", best.get("name")
    if h.get("entrances"):
        lat, lng = h["entrances"][0]
        return lat, lng, "entrance", None
    return h["lat"], h["lng"], "osm", None


STOP_FILTERS = ('["highway"="bus_stop"]', '["public_transport"="platform"]', '["public_transport"="stop_position"]',
                '["railway"~"^(station|halt|tram_stop)$"]', '["station"="subway"]')


def _overpass(query):
    body = ("data=" + urllib.parse.quote(query)).encode()
    return json.loads(http(OVERPASS, data=body, timeout=400))["elements"]


def fetch_osm_hospitals():
    """OSM hospitals in Spain with centre, name and outline entrances (cached)."""
    if OSM_CACHE.exists():
        return load_json(OSM_CACHE)
    q = """[out:json][timeout:300];
area["ISO3166-1"="ES"][admin_level=2]->.es;
nwr["amenity"="hospital"](area.es)->.h;
.h out center tags;
way.h; node(w)["entrance"];
out;"""
    els = _overpass(q)
    hosp, entr = [], {}
    for e in els:
        if e.get("tags", {}).get("amenity") == "hospital":
            c = e.get("center") or {"lat": e.get("lat"), "lon": e.get("lon")}
            if c.get("lat") is None:
                continue
            hosp.append({"id": f"{e['type'][0]}{e['id']}", "name": e["tags"].get("name", ""),
                         "lat": c["lat"], "lng": c["lon"], "entrances": []})
        elif "entrance" in e.get("tags", {}):
            entr[e["id"]] = (e["lat"], e["lon"])
    # attach entrances to the hospital whose centre is closest (they come from hospital outlines)
    for lat, lng in entr.values():
        near = min(hosp, key=lambda h: (h["lat"] - lat) ** 2 + (h["lng"] - lng) ** 2, default=None)
        if near and haversine_km(lat, lng, near["lat"], near["lng"]) < 1:
            near["entrances"].append((lat, lng))
    dump_json(hosp, OSM_CACHE, compact=True)
    return hosp


def fetch_stops(points):
    """Public transport stops within STOP_RADIUS_M of any of the given (lat, lng) points."""
    stops = []
    for i in range(0, len(points), 150):
        chunk = points[i:i + 150]
        parts = "".join(f"node{f}(around:{STOP_RADIUS_M},{lat},{lng});" for lat, lng in chunk for f in STOP_FILTERS)
        for e in _overpass(f"[out:json][timeout:300];({parts});out;"):
            stops.append({"lat": e["lat"], "lng": e["lon"], "name": e.get("tags", {}).get("name")})
        time.sleep(2)
    return stops


def geocode(h, muni_name):
    q = {"q": f"{h['address']}, {h['postcode']} {muni_name}, España", "format": "json", "limit": 1, "countrycodes": "es"}
    time.sleep(1.1)  # Nominatim usage policy: max 1 request per second
    res = json.loads(http(NOMINATIM + "?" + urllib.parse.urlencode(q), headers={"User-Agent": USER_AGENT}, timeout=60))
    if not res:
        q["q"] = f"{h['name']}, {muni_name}, España"
        time.sleep(1.1)
        res = json.loads(http(NOMINATIM + "?" + urllib.parse.urlencode(q), headers={"User-Agent": USER_AGENT}, timeout=60))
    if not res and h.get("postcode"):  # last resort: the postcode area within the municipality
        q = {"postalcode": h["postcode"], "city": muni_name, "country": "España", "format": "json", "limit": 1}
        time.sleep(1.1)
        res = json.loads(http(NOMINATIM + "?" + urllib.parse.urlencode(q), headers={"User-Agent": USER_AGENT}, timeout=60))
        if res:
            return float(res[0]["lat"]), float(res[0]["lon"]), "postcode"
    return (float(res[0]["lat"]), float(res[0]["lon"]), "address") if res else None


def settle_muni(h, locate):
    """The commune the hospital's point stands in (the register's commune if the point is off the map)."""
    return locate(h["lng"], h["lat"]) or h["muni"]


def main_fr():
    """France: FINESS has coordinates, so no OSM matching; snap to the nearest stop and apply overrides."""
    import hospitals_fr
    p = paths("fr")
    hosps = hospitals_fr.read_hospitals_fr(hospitals_fr.fetch_finess(), hospitals_fr.fetch_urgences())
    index = MuniIndex(load_municipalities(p.topo))
    overrides = load_json(p.hospital_overrides) if p.hospital_overrides.exists() else {}
    stops = fetch_stops([(h["lat"], h["lng"]) for h in hosps])
    out = []
    for h in hosps:
        a = apply_override(h, overrides, []) or {"lat": h["lat"], "lng": h["lng"], "entrances": [], "via": "finess"}
        lat, lng, source, stop_name = place_anchor(a, stops)
        if a.get("exact"):
            source = overrides[h["codcnh"]].get("source", "override")
        elif source == "osm":
            source = "finess"
        h = dict(h, lat=round(lat, 6), lng=round(lng, 6), point_source=source, osm_id=None, stop_name=stop_name)
        h["muni"] = settle_muni(h, index.locate)
        out.append(h)
    dump_json(out, p.hospitals_placed)
    from collections import Counter
    print("placed:", len(out), dict(Counter(x["point_source"] for x in out)))


def main():
    import argparse
    from common import add_country_arg
    ap = argparse.ArgumentParser()
    add_country_arg(ap)
    if ap.parse_args().country == "fr":
        return main_fr()
    places = {m["code"]: m for m in load_json(PLACES_FILE)["municipalities"]}
    hosps = [h for h in catalogue.read_catalogue(catalogue.fetch_catalogue()) if h["tier"]]
    index = MuniIndex(load_municipalities())
    osm = fetch_osm_hospitals()
    for o in osm:
        o["muni"] = index.locate(o["lng"], o["lat"])
    print(f"{len(hosps)} catalogue hospitals, {len(osm)} OSM hospitals")

    from collections import Counter as _C
    per_muni = _C(h["muni"] for h in hosps)
    for h in hosps:
        h["muni_name"] = places.get(h["muni"], {}).get("name", "")
        h["siblings"] = per_muni[h["muni"]]
    overrides = load_json(OVERRIDES) if OVERRIDES.exists() else {}
    anchors = {}  # codcnh -> {"lat","lng","entrances","osm_id","via"}
    for h in hosps:
        o = apply_override(h, overrides, osm)
        if o:
            anchors[h["codcnh"]] = o
            continue
        o = match(h, osm)
        if o:
            anchors[h["codcnh"]] = dict(o, osm_id=o["id"], via="osm")
    missing = [h for h in hosps if h["codcnh"] not in anchors]
    print(f"matched in OSM: {len(anchors)}; geocoding {len(missing)} with Nominatim")
    for h in missing:
        p = geocode(h, places.get(h["muni"], {}).get("name", ""))
        if p:
            via = "nominatim" if p[2] == "address" else "postcode"
            anchors[h["codcnh"]] = {"lat": p[0], "lng": p[1], "entrances": [], "osm_id": None, "via": via}
        else:
            print(f"  not found: {h['name']} ({h['muni']})")

    stops = fetch_stops([(a["lat"], a["lng"]) for a in anchors.values()])
    out = []
    for h in hosps:
        a = anchors.get(h["codcnh"])
        if not a:
            continue
        lat, lng, source, stop_name = place_anchor(a, stops)
        if a.get("exact"):
            source = overrides[h["codcnh"]].get("source", "override")
        elif a["via"] in ("nominatim", "postcode", "override"):
            source = f"{a['via']}+stop" if source == "stop" else a["via"]
        h = {k: v for k, v in h.items() if k not in ("muni_name", "siblings")}
        out.append(dict(h, lat=round(lat, 6), lng=round(lng, 6), point_source=source,
                        osm_id=a["osm_id"], stop_name=stop_name))
    dump_json(out, OUTPUT)
    from collections import Counter
    print("placed:", len(out), dict(Counter(x["point_source"] for x in out)))


if __name__ == "__main__":
    main()
