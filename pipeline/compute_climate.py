"""Climate per municipality from ERA5-Land daily statistics (Copernicus CDS), 2015-2024 averages.

Per municipality (the grid cell at its town centre, ~9 km; the nearest land cell on the coast):
  hot days      daily maximum >= 35 °C, per year
  hot nights    daily minimum >= 20 °C ("tropical nights"), per year
  frost days    daily minimum < 0 °C, per year
  July high     mean daily maximum in July; January low: mean daily minimum in January
ERA5-Land runs cooler than weather stations on the hottest days (Montoro, 14 Aug 2021: 44.9 °C vs
47.4 °C measured), so hot-day counts are conservative.

Needs a free CDS account: ~/.cdsapirc with the API token, and the dataset licence accepted on
https://cds.climate.copernicus.eu/datasets/derived-era5-land-daily-statistics
Usage: python pipeline/compute_climate.py --country es|fr [--download-only]
"""

import argparse
import math
from datetime import datetime, timezone

from common import add_country_arg, dump_json, load_json, paths, write_csv

DATASET = "derived-era5-land-daily-statistics"
YEARS = range(2015, 2025)
STATS = ("daily_maximum", "daily_minimum")
# [north, west, south, east] per country; each country downloads its own boxes (self-contained)
BOXES = {
    "es": {"peninsula": [44.0, -9.5, 35.0, 4.5], "canarias": [29.5, -18.3, 27.5, -13.3]},
    "fr": {"metropole": [51.2, -5.3, 41.3, 9.7]},
}
HOT, TROPICAL, FROST = 35.0, 20.0, 0.0


def cache_file(p, box, stat, year):
    return p.climate_cache / f"{box}-{stat}-{year}.nc"


PARALLEL = 6   # the CDS queues several requests per user; one at a time would take most of a day


def download(cc):
    from concurrent.futures import ThreadPoolExecutor
    import cdsapi
    p = paths(cc)
    p.climate_cache.mkdir(parents=True, exist_ok=True)
    todo = [(box, area, stat, year) for box, area in BOXES[cc].items() for year in YEARS for stat in STATS
            if not cache_file(p, box, stat, year).exists()]

    def fetch(job):
        box, area, stat, year = job
        f = cache_file(p, box, stat, year)
        tmp = f.with_suffix(f".{stat}.part")
        print(f"requesting {box} {stat} {year}", flush=True)
        cdsapi.Client(quiet=True, progress=False).retrieve(DATASET, {
            "variable": ["2m_temperature"], "year": str(year),
            "month": [f"{m:02d}" for m in range(1, 13)], "day": [f"{d:02d}" for d in range(1, 32)],
            "daily_statistic": stat, "time_zone": "utc+01:00", "frequency": "1_hourly", "area": area,
        }, str(tmp))
        tmp.rename(f)
        print(f"done {box} {stat} {year}", flush=True)

    with ThreadPoolExecutor(PARALLEL) as pool:
        list(pool.map(fetch, todo))


def year_metrics(tmax, tmin, months):
    """Per grid cell for one year (arrays day x lat x lon, °C; months per day) -> dict of lat x lon arrays."""
    import numpy as np
    with np.errstate(invalid="ignore"):
        out = {
            "hot": (tmax >= HOT).sum(axis=0).astype(float),
            "nights": (tmin >= TROPICAL).sum(axis=0).astype(float),
            "frost": (tmin < FROST).sum(axis=0).astype(float),
            "jul_high": np.nanmean(tmax[months == 7], axis=0),
            "jan_low": np.nanmean(tmin[months == 1], axis=0),
        }
    sea = np.isnan(tmax).all(axis=0)
    for k in out:
        out[k][sea] = np.nan
    return out


METRICS = ("hot", "nights", "frost", "jul_high", "jan_low")


def sample_index(grid, lat, lon, la, lo, reach=3):
    """(i, j) of the cell at (la, lo), or of the nearest land cell within `reach` cells; None outside / at sea."""
    import numpy as np
    step_lat = abs(float(lat[1] - lat[0])) if len(lat) > 1 else 0.1
    step_lon = abs(float(lon[1] - lon[0])) if len(lon) > 1 else 0.1
    if not (min(lat) - step_lat <= la <= max(lat) + step_lat and min(lon) - step_lon <= lo <= max(lon) + step_lon):
        return None
    i, j = int(np.abs(lat - la).argmin()), int(np.abs(lon - lo).argmin())
    if not np.isnan(grid[i, j]):
        return i, j
    best = None
    for di in range(-reach, reach + 1):
        for dj in range(-reach, reach + 1):
            ii, jj = i + di, j + dj
            if 0 <= ii < grid.shape[0] and 0 <= jj < grid.shape[1] and not np.isnan(grid[ii, jj]):
                d = math.hypot(di, dj)
                if best is None or d < best[0]:
                    best = (d, ii, jj)
    return (best[1], best[2]) if best else None


def sample(grid, lat, lon, la, lo):
    ij = sample_index(grid, lat, lon, la, lo)
    return None if ij is None else float(grid[ij])


def build_output(places, values, params):
    """values: {code: [hot, nights, frost, jul_high, jan_low]} -> JSON rows (+ population)."""
    m = {}
    for mu in places["municipalities"]:
        v = values.get(mu["code"])
        m[mu["code"]] = ([None] * 5 if v is None else [round(x, 1) if x is not None else None for x in v]) + [mu.get("pop")]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "params": dict(params, population_year=places["meta"].get("population_year")),
        # code -> [hot days >= 35 °C, hot nights >= 20 °C, frost days < 0 °C (per year), July high °C, January low °C,
        #          population]; means over the period
        "m": m,
    }


def climate_csv_rows(output, munis):
    header = ["code", "name", "province", "population", "hot_days", "hot_nights", "frost_days", "july_high_c", "january_low_c"]
    return header, [[mu["code"], mu["name"], mu.get("province"), mu.get("pop")] + (output["m"].get(mu["code"]) or [None] * 6)[:5]
                    for mu in munis]


def box_grids(p, box):
    """Mean metrics over YEARS for one box -> (lat, lon, {metric: grid})."""
    import netCDF4
    import numpy as np
    sums, n, lat, lon = None, 0, None, None
    for year in YEARS:
        days = {}
        for stat in STATS:
            with netCDF4.Dataset(cache_file(p, box, stat, year)) as d:
                t = d.variables["valid_time"]
                dates = netCDF4.num2date(t[:], t.units)
                days[stat] = (np.ma.filled(d.variables["t2m"][:].astype(float), np.nan) - 273.15,
                              np.array([x.month for x in dates]))
                lat, lon = d.variables["latitude"][:].data, d.variables["longitude"][:].data
        (tmax, months), (tmin, _) = days["daily_maximum"], days["daily_minimum"]
        got = year_metrics(tmax, tmin, months)
        sums = got if sums is None else {k: sums[k] + got[k] for k in METRICS}
        n += 1
    return lat, lon, {k: sums[k] / n for k in METRICS}


def compute(cc):
    p = paths(cc)
    places = load_json(p.places)
    grids = {box: box_grids(p, box) for box in BOXES[cc]}
    values, missing = {}, []
    for mu in places["municipalities"]:
        got = None
        for lat, lon, g in grids.values():
            ij = sample_index(g["hot"], lat, lon, mu["lat"], mu["lng"])
            if ij is not None:
                got = [float(g[k][ij]) for k in METRICS]
                break
        if got is None:
            missing.append(mu["name"])
        else:
            values[mu["code"]] = got
    params = {"source": "ERA5-Land daily statistics (Copernicus Climate Change Service)", "period": f"{YEARS[0]}-{YEARS[-1]}",
              "thresholds": {"hot": HOT, "nights": TROPICAL, "frost": FROST},
              "notes": ["ERA5-Land is a ~9 km grid: it runs 2-3 °C cooler than weather stations on the hottest days, so "
                        "hot-day counts are conservative, and it averages mountain villages with their valleys."]}
    out = build_output(places, values, params)
    dump_json(out, p.climate_json, compact=True)
    write_csv(p.climate_csv, *climate_csv_rows(out, places["municipalities"]))
    print(f"Wrote {p.climate_json} ({len(values)} municipalities; no grid cell for {len(missing)}: {missing[:10]})")


def main():
    ap = argparse.ArgumentParser()
    add_country_arg(ap)
    ap.add_argument("--download-only", action="store_true")
    args = ap.parse_args()
    download(args.country)
    if args.download_only:
        return
    compute(args.country)


if __name__ == "__main__":
    main()
