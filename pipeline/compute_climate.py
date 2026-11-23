"""Climate per municipality from the Copernicus "Climate indicators for Europe" (C3S / EEA), 2015-2024 averages.

The indicators are computed by Copernicus from ERA5 reanalysis on a 0.25° grid (~25 km), yearly or monthly:
  hot days      days a year with a maximum >= 35 °C
  hot nights    days a year with a minimum >= 20 °C ("tropical nights")
  frost days    days a year with a minimum < 0 °C
  July high     monthly mean of the daily maximum in July; January low: of the daily minimum in January
Each municipality takes the grid cell at its town centre. A 25 km cell averages mountains with valleys, so
mountain villages read milder and valley towns cooler than they are on the hottest days.

Needs a free CDS account (~/.cdsapirc with the API token) and the licence of the dataset accepted on
https://cds.climate.copernicus.eu/datasets/sis-ecde-climate-indicators (CC BY 4.0). Five small downloads.
Usage: python pipeline/compute_climate.py --country es|fr [--download-only]
"""

import argparse
import math
import zipfile
from datetime import datetime, timezone

from common import add_country_arg, dump_json, load_json, paths, write_csv

DATASET = "sis-ecde-climate-indicators"
YEARS = range(2015, 2025)
BASE = {"origin": "reanalysis", "spatial_aggregation": "gridded", "version": "v2_0"}
# metric -> (request, netCDF variable, month or None for yearly values, Kelvin?)
INDICATORS = {
    "hot": (dict(variable="hot_days", temporal_aggregation="yearly", other_parameters="35_c"), "hot_days", None, False),
    "nights": (dict(variable="tropical_nights", temporal_aggregation="yearly"), "tropical_nights", None, False),
    "frost": (dict(variable="frost_days", temporal_aggregation="yearly"), "frost_days", None, False),
    "jul_high": (dict(variable="daily_maximum_temperature", temporal_aggregation="monthly", other_parameters="mean"),
                 "t2m", 7, True),
    "jan_low": (dict(variable="daily_minimum_temperature", temporal_aggregation="monthly", other_parameters="mean"),
                "t2m", 1, True),
}
METRICS = tuple(INDICATORS)


def download(cc):
    import cdsapi
    p = paths(cc)
    p.climate_cache.mkdir(parents=True, exist_ok=True)
    client = cdsapi.Client(quiet=True, progress=False)
    for metric, (req, _, _, _) in INDICATORS.items():
        z = p.climate_cache / f"{req['variable']}.zip"
        if not z.exists():
            print(f"requesting {req['variable']}", flush=True)
            client.retrieve(DATASET, dict(BASE, **req), str(z.with_suffix(".part")))
            z.with_suffix(".part").rename(z)


def period_mean(values, dates, years=YEARS, month=None):
    """Mean over the time steps in `years` (and `month` for monthly series): time x lat x lon -> lat x lon."""
    import numpy as np
    idx = [k for k, d in enumerate(dates) if d.year in years and (month is None or d.month == month)]
    return np.nanmean(values[idx], axis=0)


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


def load_grids(p):
    """{metric: grid} over YEARS, plus lat and lon (all indicators share the grid)."""
    import netCDF4
    import numpy as np
    grids, lat, lon = {}, None, None
    for metric, (req, var, month, kelvin) in INDICATORS.items():
        with zipfile.ZipFile(p.climate_cache / f"{req['variable']}.zip") as z:
            name = next(n for n in z.namelist() if n.endswith(".nc"))
            data = z.read(name)
        with netCDF4.Dataset("inmemory.nc", memory=data) as d:
            t = d.variables["time"]
            dates = netCDF4.num2date(t[:], t.units)
            values = np.ma.filled(d.variables[var][:].astype(float), np.nan)
            lat, lon = d.variables["lat"][:].data, d.variables["lon"][:].data
        grid = period_mean(values, dates, month=month)
        grids[metric] = grid - 273.15 if kelvin else grid
    return lat, lon, grids


def compute(cc):
    p = paths(cc)
    places = load_json(p.places)
    lat, lon, grids = load_grids(p)
    values, missing = {}, []
    for mu in places["municipalities"]:
        ij = sample_index(grids["hot"], lat, lon, mu["lat"], mu["lng"])
        if ij is None:
            missing.append(mu["name"])
        else:
            values[mu["code"]] = [float(grids[k][ij]) for k in METRICS]
    params = {"source": "Copernicus Climate Change Service, Climate indicators for Europe (ERA5 reanalysis, 0.25°)",
              "period": f"{YEARS[0]}-{YEARS[-1]}",
              "notes": ["A ~25 km grid: mountain villages read milder and valley towns slightly cooler on the hottest days "
                        "than their own weather station would say."]}
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
