import csv
import json
import math
import time
import urllib.error
import urllib.request
from http.client import HTTPException
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
COUNTRIES = ("es", "fr")


def paths(cc):
    """Everything a country reads and writes lives in its own folders (self-contained)."""
    data, out, cache = DATA / cc, ROOT / "web" / "public" / "data" / cc, ROOT / ".cache" / cc
    return SimpleNamespace(
        cc=cc, data=data, out=out, cache=cache,
        base=data / "municipalities_base.json", places=data / "places.json", topo=out / "municipalities.topo.json",
        cities_json=out / "remoteness.json", cities_csv=out / "remoteness.csv", times_cache=cache / "times",
        airports_json=out / "airports.json", airports_csv=out / "airports.csv", airports_cache=cache / "airports",
        internet_json=out / "internet.json", internet_csv=out / "internet.csv", internet_cache=cache / "internet",
        hospitals_json=out / "hospitals.json", hospitals_csv=out / "hospitals.csv", hospitals_cache=cache / "hospitals",
        incentives_json=out / "incentives.json", incentives_csv=out / "incentives.csv", incentives_cache=cache / "incentives",
        climate_json=out / "climate.json", climate_csv=out / "climate.csv", climate_cache=cache / "climate",
        housing_json=out / "housing.json", housing_csv=out / "housing.csv", housing_cache=cache / "housing",
        hospitals_placed=data / "hospitals.json", hospital_overrides=data / "hospital_overrides.json",
    )


def add_country_arg(ap):
    ap.add_argument("--country", default="es", choices=COUNTRIES, help="country to build (default: es)")


# Spain is the default country (scripts switch with --country, see each module's configure()).
_ES = paths("es")
BASE_FILE = _ES.base
PLACES_FILE = _ES.places
OUTPUT_FILE = _ES.cities_json
CACHE_DIR = _ES.times_cache
TOPO_FILE = _ES.topo
CITIES_CSV = _ES.cities_csv
AIRPORTS_OUTPUT_FILE = _ES.airports_json
AIRPORTS_CSV = _ES.airports_csv
AIRPORT_CACHE_DIR = _ES.airports_cache

class HTTPStatusError(RuntimeError):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


USER_AGENT = "spain-remoteness/1.0 (+https://github.com/yannklein/spain-remoteness)"


def http(url, data=None, headers=None, timeout=300, retries=4):
    """POST (if data) or GET with retries and exponential backoff. Returns bytes."""
    hdrs = {"User-Agent": USER_AGENT}
    hdrs.update(headers or {})
    body = None
    if data is not None:
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=body, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            detail = e.read().decode(errors="replace")[:500]
            # 4xx other than 429 will not get better by retrying
            if e.code != 429 and 400 <= e.code < 500:
                raise HTTPStatusError(e.code, f"HTTP {e.code} for {url}: {detail}") from e
            print(f"  HTTP {e.code}, retrying ({attempt + 1}/{retries}): {detail[:120]}")
        except (urllib.error.URLError, TimeoutError, ConnectionError, HTTPException) as e:
            last = e
            print(f"  network error, retrying ({attempt + 1}/{retries}): {e}")
        time.sleep(min(60, 5 * 2 ** attempt))
    raise RuntimeError(f"giving up on {url}: {last}")


def haversine_km(a_lat, a_lng, b_lat, b_lng):
    r = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp = p2 - p1
    dl = math.radians(b_lng - a_lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def zone(m):
    """Territory a municipality belongs to: travel never crosses zones.

    Each island is its own zone, as are Ceuta and Melilla; everything
    else is the mainland. Places that are not municipalities (airports)
    carry their zone explicitly.
    """
    if m.get("zone"):
        return m["zone"]
    if m.get("island"):
        return "island:" + m["island"]
    prov = m["code"][:2]
    if prov == "51":
        return "ceuta"
    if prov == "52":
        return "melilla"
    return "mainland"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump_json(obj, path, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if compact:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(obj, f, ensure_ascii=False, indent=1)


TEXT_COLUMNS = {"code", "name", "province"}


def write_csv(path, header, rows):
    """Flat table for GIS tools: None becomes an empty cell (NULL in QGIS).

    Also writes a QGIS .csvt sidecar so zero-padded codes (01001) stay text.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow(["" if v is None else v for v in r])
    def kind(i, c):
        if c in TEXT_COLUMNS or c.endswith(("_city", "_airport", "_hospital", "_via", "_source")):
            return '"String"'
        return '"Real"' if any(isinstance(r[i], float) for r in rows) else '"Integer"'

    types = [kind(i, c) for i, c in enumerate(header)]
    path.with_suffix(".csvt").write_text(",".join(types) + "\n", encoding="utf-8")
