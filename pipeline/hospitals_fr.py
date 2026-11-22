"""France: hospitals with a general emergency department, with tiers.

Sources
- FINESS "établissements géolocalisés" (Ministère de la Santé, data.gouv.fr):
  every establishment site with category, public status and Lambert-93 coordinates.
- DREES SAE, base administrative (latest year), table URGENCES2: sites (FINESS
  géographique) with a general emergency activity (URG = "GEN", visits > 0).

Tiers (nested; only sites with a general emergency department)
  1 Major:  CHU/CHR sites (FINESS category 101)
  2 Public: public hospitals: public establishment (codesph 1), ESPIC (6),
            PSPH (3), army hospitals (114) or public cooperation groups (697)
  3 Any:    every site with a general emergency department, private clinics included

Usage: python pipeline/hospitals_fr.py   (prints counts; used by place_hospitals --country fr)
"""

import csv
import io
import math
import re

from common import http, paths

FINESS_DATASET = "https://www.data.gouv.fr/api/1/datasets/finess-extraction-du-fichier-des-etablissements/"
SAE_ATTACHMENTS = ("https://data.drees.solidarites-sante.gouv.fr/api/explore/v2.1/catalog/datasets/"
                   "707_bases-administratives-sae/attachments")
CACHE = paths("fr").hospitals_cache
PUBLIC_SPH = {"1", "3", "6"}
PUBLIC_CATEGORIES = {"101", "114", "697"}
METRO_DEPS_EXCLUDED = re.compile(r"^(97|98|9[A-F])")


def lambert93_to_wgs84(x, y):
    """RGF93 / Lambert-93 (EPSG:2154) -> (lat, lng) in degrees (inverse conformal conic, GRS80)."""
    n, c, xs, ys = 0.7256077650532670, 11754255.426096, 700000.0, 12655612.049876
    e, lon0 = 0.0818191910428158, math.radians(3.0)
    dx, dy = x - xs, y - ys
    r = math.hypot(dx, dy)
    gamma = math.atan(dx / -dy)
    lng = lon0 + gamma / n
    latiso = -1 / n * math.log(abs(r / c))
    lat = 2 * math.atan(math.exp(latiso)) - math.pi / 2
    for _ in range(10):
        s = e * math.sin(lat)
        lat = 2 * math.atan(((1 + s) / (1 - s)) ** (e / 2) * math.exp(latiso)) - math.pi / 2
    return math.degrees(lat), math.degrees(lng)


def commune_of(dep, com):
    """INSEE commune code; Paris, Lyon and Marseille arrondissements map to their commune."""
    code = dep + com
    if code.startswith("751"):
        return "75056"
    if code.startswith("6938"):
        return "69123"
    if code.startswith("132") and code != "13200":
        return "13055"
    return code


def read_emergency_sites(path):
    """FINESS géographique numbers with a general emergency activity (URG = GEN, visits > 0)."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        rows = csv.DictReader(fh, delimiter=";")
        return {r["FI"] for r in rows if r.get("URG") == "GEN" and (r.get("PASSU") or "0").isdigit()
                and int(r["PASSU"]) > 0}


def read_hospitals_fr(finess_path, urgences_path):
    er = read_emergency_sites(urgences_path)
    structures, coords = {}, {}
    with open(finess_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.rstrip("\n").split(";")
            if f[0] == "structureet" and f[1] in er:
                structures[f[1]] = f
            elif f[0] == "geolocalisation" and f[1] in er and "2154" in f[4]:
                # precision: 1-3 address-level, 4 = commune centroid (ADMIN-EXPRESS)
                coords[f[1]] = (float(f[2]), float(f[3]), f[4].split(",")[0])
    out = []
    for fi, f in structures.items():
        dep = f[13]
        if METRO_DEPS_EXCLUDED.match(dep) or fi not in coords:
            continue
        x, y, precision = coords[fi]
        lat, lng = lambert93_to_wgs84(x, y)
        category, sph = f[18], f[26]
        public = sph in PUBLIC_SPH or category in PUBLIC_CATEGORIES or category == "355"
        tier = 1 if category == "101" else 2 if public else 3
        out.append({"codcnh": fi, "name": (f[4] or f[3]).strip().strip('"').strip().title(), "muni": commune_of(dep, f[12]),
                    "address": " ".join(x for x in (f[7], f[8], f[9]) if x), "postcode": f[15][:5],
                    "beds": None, "cls": category, "public": public, "cath_lab": False, "tier": tier,
                    "lat": round(lat, 6), "lng": round(lng, 6), "precise": precision != "4"})
    return out


def fetch_finess():
    import json
    meta = json.loads(http(FINESS_DATASET, timeout=60))
    res = next(r for r in meta["resources"] if "olocalis" in (r.get("title") or ""))
    f = CACHE / f"finess_geo_{res['url'].rsplit('/', 2)[-2]}.csv"
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_bytes(http(res["url"], timeout=900))
        tmp.rename(f)
    return f


def fetch_urgences():
    """URGENCES2 table of the latest SAE base administrative (7z), extracted into the cache."""
    import json
    att = json.loads(http(SAE_ATTACHMENTS + "?limit=100", timeout=60))["attachments"]
    sevenz = sorted((a for a in att if re.search(r"SAE (\d{4}) Base administrative.*7z", a["metas"]["title"])),
                    key=lambda a: a["metas"]["title"])[-1]
    year = re.search(r"SAE (\d{4})", sevenz["metas"]["title"]).group(1)
    out = CACHE / f"URGENCES2_{year}.csv"
    if out.exists():
        return out
    archive = CACHE / f"sae_{year}_admin.7z"
    if not archive.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(http(sevenz["href"], timeout=900))
    import py7zr
    with py7zr.SevenZipFile(archive) as z:
        name = next(n for n in z.getnames() if n.endswith(f"Base CSV/URGENCES2_{year}.csv"))
        data = z.read([name])[name].read()
    out.write_bytes(data)
    return out


def main():
    from collections import Counter
    hs = read_hospitals_fr(fetch_finess(), fetch_urgences())
    c = Counter(h["tier"] for h in hs)
    print(f"{len(hs)} metropolitan sites with a general emergency department; "
          f"cumulative tiers 1/2/3: {c[1]}, {c[1] + c[2]}, {len(hs)}")


if __name__ == "__main__":
    main()
