"""Setting per municipality: green around, summer greenness, relief and water, village character.

Green and setting (sampled around each town centre):
  nature %    forest, shrubland, grassland, wetland, moss within 3 km (ESA WorldCover 2021, read at 80 m from
              the 10 m cloud-optimised tiles); water % (rivers, lakes, sea) and built-up % likewise
  ndvi_july   mean July vegetation index within 3 km, 2021-2025 (MODIS 500 m 16-day composites, NASA, via the
              Microsoft Planetary Computer): ~0.2 brown, ~0.4 mixed, 0.6+ lush green
  relief      highest minus lowest point within 5 km (Copernicus DEM GLO-90); elevation at the town centre
Character:
  Spain       Los Pueblos más Bonitos de España (the association's list), historic ensembles ("conjunto
              histórico") and heritage-listed buildings (Bienes de Interés Cultural) from Wikidata
  France      Plus Beaux Villages de France, Petites Cités de Caractère, protected historic centres
              ("sites patrimoniaux remarquables", Géoportail de l'Urbanisme), listed monuments (Mérimée)
Usage: python pipeline/compute_setting.py --country es|fr
"""

import argparse
import csv
import html as htmlmod
import io
import json
import math
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import numpy as np

from common import add_country_arg, dump_json, load_json, paths, write_csv
from compute_housing import _names, normalise

GREEN_KM, RELIEF_KM, NDVI_KM = 3, 5, 3
NATURE = (10, 20, 30, 90, 95, 100)   # trees, shrubland, grassland, wetland, mangroves, moss & lichen
WATER, BUILT = (80,), (50,)
WC_URL = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{}_Map.tif"
WC_DECIMATE = 8                      # read the 10 m tiles' 80 m overview
DEM_URL = "https://copernicus-dem-90m.s3.amazonaws.com/{0}/{0}.tif"
DEM_NODATA = -32767
NDVI_YEARS = range(2021, 2026)
UA = {"User-Agent": "remoteness-map-pipeline/1.0 (open data)"}


def worldcover_tile(lat, lon):
    la, lo = 3 * math.floor(lat / 3), 3 * math.floor(lon / 3)
    return f"{'N' if la >= 0 else 'S'}{abs(la):02d}{'E' if lo >= 0 else 'W'}{abs(lo):03d}"


def dem_tile(lat, lon):
    la, lo = math.floor(lat), math.floor(lon)
    return f"Copernicus_DSM_COG_30_{'N' if la >= 0 else 'S'}{abs(la):02d}_00_{'E' if lo >= 0 else 'W'}{abs(lo):03d}_00_DEM"


class TileGrid:
    """Values of a tiled lat/lon raster within a radius, reading each tile once (small LRU cache)."""

    def __init__(self, tile_deg, cache=6):
        self.tile_deg, self.cache, self.tiles = tile_deg, cache, {}

    def key(self, lat, lon):
        d = self.tile_deg
        return (d * math.floor(lat / d), d * math.floor(lon / d))

    def load(self, key):   # -> (array, top latitude, left longitude, pixel height °, pixel width °) or None
        raise NotImplementedError

    def tile(self, key):
        if key not in self.tiles:
            if len(self.tiles) >= self.cache:
                self.tiles.pop(next(iter(self.tiles)))
            self.tiles[key] = self.load(key)
        return self.tiles[key]

    def values_in_circle(self, lat, lon, km):
        dlat = km / 111.32
        dlon = km / (111.32 * math.cos(math.radians(lat)))
        keys = {self.key(a, b) for a in (lat - dlat, lat + dlat) for b in (lon - dlon, lon + dlon)}
        out = []
        for k in sorted(keys):
            t = self.tile(k)
            if t is None:
                continue
            arr, top, left, ph, pw = t
            r0 = max(0, int((top - (lat + dlat)) / ph)); r1 = min(arr.shape[0], int((top - (lat - dlat)) / ph) + 1)
            c0 = max(0, int((lon - dlon - left) / pw)); c1 = min(arr.shape[1], int((lon + dlon - left) / pw) + 1)
            if r0 >= r1 or c0 >= c1:
                continue
            sub = arr[r0:r1, c0:c1]
            plat = top - (np.arange(r0, r1) + 0.5) * ph
            plon = left + (np.arange(c0, c1) + 0.5) * pw
            dy = (plat[:, None] - lat) * 111.32
            dx = (plon[None, :] - lon) * 111.32 * math.cos(math.radians(lat))
            out.append(sub[dy ** 2 + dx ** 2 <= km ** 2])
        return np.concatenate(out) if out else np.array([])


def _read(url, decimate=1):
    import rasterio
    from rasterio.enums import Resampling
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif", GDAL_HTTP_MAX_RETRY="4"):
        try:
            src = rasterio.open("/vsicurl/" + url)
        except rasterio.errors.RasterioIOError:
            return None   # no tile: open sea
        with src:
            h, w = src.height // decimate, src.width // decimate
            arr = src.read(1, out_shape=(h, w), resampling=Resampling.nearest)
            b = src.bounds
            return arr, b.top, b.left, (b.top - b.bottom) / h, (b.right - b.left) / w


class WorldCover(TileGrid):
    def __init__(self):
        super().__init__(3, cache=4)

    def load(self, key):
        return _read(WC_URL.format(worldcover_tile(key[0] + 1, key[1] + 1)), WC_DECIMATE)


class Dem(TileGrid):
    def __init__(self):
        super().__init__(1, cache=12)

    def load(self, key):
        t = _read(DEM_URL.format(dem_tile(key[0] + 0.5, key[1] + 0.5)))
        return None if t is None else (t[0].astype(float),) + t[1:]


def cover_shares(vals):
    vals = vals[vals > 0]
    if not len(vals):
        return None
    n = len(vals)
    land = int((~np.isin(vals, WATER)).sum())   # sea and lakes don't count against nature
    share = lambda k: (np.isin(vals, k).sum() / land * 100) if land else 0.0   # noqa: E731
    return {"nature": share(NATURE), "water": np.isin(vals, WATER).sum() / n * 100, "built": share(BUILT)}


def relief(vals):
    vals = vals[(vals > DEM_NODATA) & np.isfinite(vals)] if len(vals) else vals
    return float(vals.max() - vals.min()) if len(vals) else None


# ---- summer greenness (MODIS) -----------------------------------------------------------------------------------

def stac_items(bbox, year):
    body = json.dumps({"collections": ["modis-13A1-061"], "bbox": bbox, "limit": 200,
                       "datetime": f"{year}-07-01T00:00:00Z/{year}-07-31T23:59:59Z"}).encode()
    req = urllib.request.Request("https://planetarycomputer.microsoft.com/api/stac/v1/search", data=body,
                                 headers=dict(UA, **{"Content-Type": "application/json"}))
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)["features"]


def sas_token(href):
    """Read token for the storage account and container of an asset href (the collection token is refused)."""
    account = urllib.parse.urlparse(href).netloc.split(".")[0]
    container = urllib.parse.urlparse(href).path.strip("/").split("/")[0]
    req = urllib.request.Request(f"https://planetarycomputer.microsoft.com/api/sas/v1/token/{account}/{container}", headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["token"]


def ndvi_july(points, bbox):
    """{code: mean July NDVI within NDVI_KM} over NDVI_YEARS (each 16-day composite overlapping July)."""
    import rasterio
    from rasterio.warp import transform
    sums, counts, tokens = {}, {}, {}
    for year in NDVI_YEARS:
        for item in stac_items(bbox, year):
            raw = item["assets"]["500m_16_days_NDVI"]["href"]
            base = raw.split("/")[2] + "/" + raw.split("/")[3]
            if base not in tokens:
                tokens[base] = sas_token(raw)
            href = raw + "?" + tokens[base]
            with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"), rasterio.open("/vsicurl/" + href) as src:
                arr = src.read(1).astype(float)
                arr[arr < -2000] = np.nan
                arr *= 1e-4
                codes = list(points)
                xs, ys = transform("EPSG:4326", src.crs, [points[c][1] for c in codes], [points[c][0] for c in codes])
                inv = ~src.transform
                rad = NDVI_KM * 1000 / src.res[0]
                for c, x, y in zip(codes, xs, ys):
                    col, row = inv * (x, y)
                    if not (0 <= row < src.height and 0 <= col < src.width):
                        continue
                    r0, r1 = int(max(0, row - rad)), int(min(src.height, row + rad + 1))
                    c0, c1 = int(max(0, col - rad)), int(min(src.width, col + rad + 1))
                    sub = arr[r0:r1, c0:c1]
                    rr, cc = np.mgrid[r0:r1, c0:c1]
                    v = sub[((rr + 0.5 - row) ** 2 + (cc + 0.5 - col) ** 2) <= rad ** 2]
                    v = v[np.isfinite(v)]
                    if len(v):
                        sums[c] = sums.get(c, 0) + float(v.mean())
                        counts[c] = counts.get(c, 0) + 1
            print(f"  NDVI {item['id']}", flush=True)
    return {c: sums[c] / counts[c] for c in sums}


# ---- character ----------------------------------------------------------------------------------------------------

def parse_pmb(page):
    """[(village, province or island, region)] from the association's list page."""
    out = []
    for m in re.finditer(r"<h3[^>]*>(.*?)</h3>(.*?)(?=<h3|<img|$)", page, flags=re.S):
        name = htmlmod.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
        rest = [htmlmod.unescape(x).strip() for x in re.sub(r"<[^>]+>", "|", m.group(2)).split("|")]
        rest = [x for x in rest if x and x != ","]
        if name and len(rest) >= 2:
            out.append((name, rest[0], rest[1]))
    return out


# region names on the association's site -> INE province codes
REGIONS = {
    "andalucia": ["04", "11", "14", "18", "21", "23", "29", "41"], "aragon": ["22", "44", "50"], "asturias": ["33"],
    "illes balears": ["07"], "baleares": ["07"], "canarias": ["35", "38"], "cantabria": ["39"],
    "castilla la mancha": ["02", "13", "16", "19", "45"],
    "castilla y leon": ["05", "09", "24", "34", "37", "40", "42", "47", "49"], "cataluna": ["08", "17", "25", "43"],
    "catalunya": ["08", "17", "25", "43"], "comunidad valenciana": ["03", "12", "46"],
    "comunitat valenciana": ["03", "12", "46"], "extremadura": ["06", "10"], "galicia": ["15", "27", "32", "36"],
    "madrid": ["28"], "comunidad de madrid": ["28"], "murcia": ["30"], "region de murcia": ["30"], "navarra": ["31"],
    "principado de asturias": ["33"], "islas baleares": ["07"], "comunidad foral de navarra": ["31"],
    "pais vasco": ["01", "20", "48"], "euskadi": ["01", "20", "48"], "la rioja": ["26"],
}
# villages that are not municipalities of their own, or named differently -> their municipality's INE code
PMB_VILLAGES = {
    "arties": "25025", "bagergue": "25025", "garos": "25025",          # Naut Aran
    "ainsa": "22907", "el burgo de osma": "42043", "zahara de la sierra": "11042",
    "barcena mayor": "39086", "carmona": "39014", "mogrovejo": "39015", "beget": "17039", "durro": "25043",
    "bulnes": "33008", "llastres": "33019", "tazones": "33076", "torazu": "33009",
    "castrillo de los polvazares": "24008", "penalba de santiago": "24115", "puentedey": "09216",
    "roda de isabena": "22129", "oseira": "32076", "ponte maceira": "15002", "vilanova dos infantes": "32024",
    "trevejo": "10210",
}


def match_pmb(cards, munis):
    found, missing = set(), []
    for name, _sub, region in cards:
        provs = REGIONS.get(normalise(region))
        key = normalise(name)
        cands = [m for m in munis if (provs is None or m["code"][:2] in provs) and
                 (key in _names(m["name"]) or any((n.endswith(" " + key) or n.startswith(key + " ")) and len(n) - len(key) < 4
                                                  for n in _names(m["name"])))]
        if key in PMB_VILLAGES:
            found.add(PMB_VILLAGES[key])
        elif len(cands) >= 1:
            exact = [m for m in cands if key in _names(m["name"])]
            found.add((exact or cands)[0]["code"])
        else:
            missing.append(f"{name} ({region})")
    return found, missing


def locate_named(rows, munis, locate):
    """Communes of labelled villages ({nom, latitude, longitude}): by name (the nearest namesake), else by the point."""
    from common import haversine_km
    by_name = {}
    for m in munis:
        for n in _names(m["name"]):
            by_name.setdefault(n, []).append(m)
    out = set()
    for r in rows:
        lat, lng = float(r["latitude"]), float(r["longitude"])
        cands = by_name.get(normalise(r["nom"]), [])
        if cands:
            out.add(min(cands, key=lambda m: haversine_km(lat, lng, m["lat"], m["lng"]))["code"])
        else:
            c = locate(lng, lat)
            if c:
                out.add(c)
    return out


def centres_inside(geometries, munis):
    """Codes of municipalities whose town centre lies inside any of the (multi)polygons (lon/lat)."""
    from shapely.geometry import Point, shape
    from shapely.strtree import STRtree
    polys = [shape(g) for g in geometries]
    tree = STRtree(polys)
    out = set()
    for m in munis:
        pt = Point(m["lng"], m["lat"])
        if any(polys[i].covers(pt) for i in tree.query(pt)):
            out.add(m["code"])
    return out


def count_merimee(rows, codes, locate):
    """Listed monuments per commune: by INSEE code (arrondissements -> their city), else by coordinates."""
    from hospitals_fr import commune_of
    out = {}
    for r in rows:
        raw = (r.get("COG_Insee_lors_de_la_protection") or "").split(";")[0].strip()   # "13058;13068": the first
        code = commune_of(raw[:2], raw[2:]) if len(raw) == 5 else None
        if code not in codes:
            code = None
            xy = (r.get("coordonnees_au_format_WGS84") or "").split(",")
            if len(xy) == 2:
                try:
                    code = locate(float(xy[1]), float(xy[0]))
                except ValueError:
                    code = None
        if code in codes:
            out[code] = out.get(code, 0) + 1
    return out


def sparql(query, tries=6):
    """Wikidata query; waits and retries when rate-limited (HTTP 429)."""
    import time
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": query, "format": "json"})
    req = urllib.request.Request(url, headers=dict(UA, Accept="application/sparql-results+json"))
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.load(r)["results"]["bindings"]
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == tries - 1:
                raise
            wait = int(e.headers.get("Retry-After") or 70)
            print(f"Wikidata rate limit: waiting {wait} s", flush=True)
            time.sleep(wait)


def fetch_text(url, dest, encoding="utf-8"):
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=600) as r:
            dest.write_bytes(r.read())
    return dest.read_text(encoding=encoding, errors="replace")


def character_es(p, munis):
    page = fetch_text("https://www.lospueblosmasbonitosdeespana.org/pueblos/", p.setting_cache / "pmb.html")
    pmb, missing = match_pmb(parse_pmb(page), munis)
    if missing:
        print(f"Pueblos más Bonitos not matched: {missing}", file=sys.stderr)
    codes = {m["code"] for m in munis}
    loc = "?i wdt:P131 ?x . ?x wdt:P131? ?m . ?m wdt:P772 ?ine ."

    def cached(name, query):   # Wikidata answers are cached: the query service throttles hard at times
        f = p.setting_cache / f"wikidata_{name}.json"
        if not f.exists():
            dump_json(sparql(query), f, compact=True)
        return load_json(f)
    bic_pairs = {(b["i"]["value"], b["ine"]["value"]) for b in
                 cached("bic", f"SELECT DISTINCT ?i ?ine WHERE {{ ?i wdt:P1435 wd:Q23712 . {loc} }}")}
    bic = {}
    for _, c in bic_pairs:
        if c in codes:
            bic[c] = bic.get(c, 0) + 1
    historic = {b["ine"]["value"] for b in cached("historic", f"SELECT DISTINCT ?i ?ine WHERE {{ ?i wdt:P31 wd:Q3317612 . {loc} }}")}
    out = {}
    for c in codes:
        out[c] = {"label": "pmb" if c in pmb else None, "historic": 1 if c in historic else 0, "listed": bic.get(c, 0)}
    return out, {"labels": f"Los Pueblos más Bonitos de España ({len(pmb)} municipalities)",
                 "heritage": "Wikidata (CC0): conjuntos históricos and Bienes de Interés Cultural"}


def lonlat(geom):
    """The WFS answers EPSG:4326 in latitude, longitude order: swap to longitude, latitude (France: lat > lon)."""
    def fix(c):
        return [fix(x) for x in c] if isinstance(c[0], list) else ([c[1], c[0]] if c[0] > c[1] else c)
    return {"type": geom["type"], "coordinates": fix(geom["coordinates"])}


def character_fr(p, munis, locate):
    from hospitals_fr import commune_of
    codes = {m["code"] for m in munis}
    rows = csv.DictReader(io.StringIO(fetch_text("https://ministere-culture.s3.sbg.io.cloud.ovh.net/POP/merimee.csv",
                                                 p.setting_cache / "merimee.csv")), delimiter="|")
    listed = count_merimee(rows, codes, locate)
    pbvf = locate_named(csv.DictReader(io.StringIO(fetch_text(
            "https://static.data.gouv.fr/resources/les-plus-beaux-villages-de-france-183-communes-labellisees-geolocalisees/"
            "20261009-092412/plus-beaux-villages-de-france.csv", p.setting_cache / "pbvf.csv").lstrip("\ufeff")), delimiter=";"),
        munis, locate)
    pcc = {r["code_commune"] for r in csv.DictReader(io.StringIO(fetch_text(
        "https://static.data.gouv.fr/resources/petites-cites-de-caractere-de-france-aout-2023/20230906-082506/"
        "petites-cites-de-caracteres-2023.csv", p.setting_cache / "pcc.csv")))}
    geoms, start = [], 0
    while True:   # protected historic centres: AC4 easements of the Géoportail de l'Urbanisme
        url = ("https://data.geopf.fr/wfs/ows?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=wfs_sup:assiette_sup_s"
               f"&OUTPUTFORMAT=application/json&SRSNAME=EPSG:4326&CQL_FILTER=suptype%3D%27ac4%27&COUNT=500&STARTINDEX={start}")
        feats = json.loads(fetch_text(url, p.setting_cache / f"spr_{start}.json"))["features"]
        geoms += [lonlat(f["geometry"]) for f in feats if f.get("geometry")]
        if len(feats) < 500:
            break
        start += 500
    spr = centres_inside(geoms, munis)   # a commune counts when its town centre lies inside a protected area
    out = {}
    for c in codes:
        label = "pbvf" if c in pbvf else "pcc" if commune_of(c[:2], c[2:]) in pcc or c in pcc else None
        out[c] = {"label": label, "historic": 1 if c in spr else 0, "listed": listed.get(c, 0)}
    return out, {"labels": f"Plus Beaux Villages de France ({len(pbvf)}), Petites Cités de Caractère 2023 ({len(pcc)})",
                 "heritage": "Mérimée (Ministère de la Culture); sites patrimoniaux remarquables (Géoportail de l'Urbanisme)"}


# ---- output -------------------------------------------------------------------------------------------------------

FIELDS = ("nature", "water", "built", "ndvi", "relief", "elev", "label", "historic", "listed")


def build_output(places, values, params):
    def rnd(k, v):
        if v is None or k in ("label", "historic", "listed"):
            return v
        return round(v, 2) if k == "ndvi" else int(round(v)) if k in ("relief", "elev") else round(v, 1)
    m = {}
    for mu in places["municipalities"]:
        v = values.get(mu["code"], {})
        m[mu["code"]] = [rnd(k, v.get(k)) for k in FIELDS] + [mu.get("pop")]
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "params": dict(params, green_km=GREEN_KM, relief_km=RELIEF_KM, ndvi_km=NDVI_KM),
            # code -> [nature %, water %, built %, July NDVI, relief m, elevation m, label, historic centre, listed buildings, pop]
            "m": m}


def setting_csv_rows(output, munis):
    header = ["code", "name", "province", "population", "nature_pct", "water_pct", "built_pct", "ndvi_july", "relief_m",
              "elevation_m", "label", "historic_centre", "listed_buildings"]
    return header, [[mu["code"], mu["name"], mu.get("province"), mu.get("pop")] + (output["m"].get(mu["code"]) or [None] * 10)[:9]
                    for mu in munis]


def main():
    from geo import MuniIndex, load_municipalities
    ap = argparse.ArgumentParser()
    add_country_arg(ap)
    args = ap.parse_args()
    p = paths(args.country)
    places = load_json(p.places)
    munis = sorted(places["municipalities"], key=lambda m: (worldcover_tile(m["lat"], m["lng"]), m["lat"], m["lng"]))
    values = {m["code"]: {} for m in munis}

    def stage(name, compute):
        """Each stage's results are cached: a failure later on doesn't redo the tile reads."""
        f = p.setting_cache / f"stage_{name}.json"
        if f.exists():
            got = load_json(f)
        else:
            got = compute()
            p.setting_cache.mkdir(parents=True, exist_ok=True)
            dump_json(got, f, compact=True)
        for c, v in got.items():
            values[c].update(v)

    def cover():
        wc, out = WorldCover(), {}
        for i, m in enumerate(munis):
            s = cover_shares(wc.values_in_circle(m["lat"], m["lng"], GREEN_KM))
            if s:
                out[m["code"]] = s
            if i % 2000 == 0:
                print(f"cover {i}/{len(munis)}", flush=True)
        return out

    def heights():
        dem, out = Dem(), {}
        for i, m in enumerate(sorted(munis, key=lambda m: (dem_tile(m["lat"], m["lng"]), m["lat"]))):
            here = dem.values_in_circle(m["lat"], m["lng"], 0.2)
            here = here[here > DEM_NODATA] if len(here) else here
            out[m["code"]] = {"relief": relief(dem.values_in_circle(m["lat"], m["lng"], RELIEF_KM)),
                              "elev": float(here.mean()) if len(here) else None}
            if i % 2000 == 0:
                print(f"relief {i}/{len(munis)}", flush=True)
        return out

    def green():
        lats = [m["lat"] for m in munis]; lngs = [m["lng"] for m in munis]
        got = ndvi_july({m["code"]: (m["lat"], m["lng"]) for m in munis},
                        [min(lngs) - 0.1, min(lats) - 0.1, max(lngs) + 0.1, max(lats) + 0.1])
        return {c: {"ndvi": v} for c, v in got.items()}

    stage("cover", cover)
    stage("relief", heights)
    stage("ndvi", green)
    index = MuniIndex(load_municipalities(p.topo))
    char, char_params = (character_es(p, munis) if args.country == "es" else character_fr(p, munis, index.locate))
    for c, v in char.items():
        values[c].update(v)
    params = dict(char_params, sources=["ESA WorldCover 2021 (CC BY 4.0)", "MODIS MOD13A1/MYD13A1 NDVI (NASA), 2021-2025",
                                        "Copernicus DEM GLO-90"])
    out = build_output(places, values, params)
    dump_json(out, p.setting_json, compact=True)
    write_csv(p.setting_csv, *setting_csv_rows(out, places["municipalities"]))
    print(f"Wrote {p.setting_json}")


if __name__ == "__main__":
    main()
