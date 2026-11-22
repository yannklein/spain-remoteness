"""Climate metrics from gridded daily temperatures."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import compute_climate as cc  # noqa: E402


def test_year_counts_per_cell():
    # 2 cells, 4 days; days 0-1 in January, days 2-3 in July
    tmax = np.array([[[10, 36]], [[12, 35]], [[30, 34.9]], [[32, 40]]], dtype=float)   # (day, lat, lon)
    tmin = np.array([[[-1, 5]], [[0, -0.5]], [[21, 19.9]], [[20, 25]]], dtype=float)
    months = np.array([1, 1, 7, 7])
    got = cc.year_metrics(tmax, tmin, months)
    assert got["hot"].tolist() == [[0, 3]]
    assert got["nights"].tolist() == [[2, 1]]
    assert got["frost"].tolist() == [[1, 1]]
    assert got["jul_high"].tolist() == [[31, 37.45]]
    assert got["jan_low"].tolist() == [[-0.5, 2.25]]


def test_sea_cells_stay_nan_and_points_take_the_nearest_land_cell():
    lat = np.array([41.0, 40.9, 40.8])
    lon = np.array([1.0, 1.1, 1.2])
    grid = np.array([[np.nan, np.nan, np.nan], [np.nan, 5.0, 6.0], [np.nan, 7.0, 8.0]])
    assert cc.sample(grid, lat, lon, 40.9, 1.1) == 5.0          # on a land cell
    assert cc.sample(grid, lat, lon, 41.0, 1.0) == 5.0          # sea cell: nearest land cell
    assert cc.sample(grid, lat, lon, 45.0, 9.0) is None         # outside the box


def test_output_rows_and_csv():
    places = {"meta": {"population_year": 2025}, "municipalities": [
        {"code": "41091", "name": "Sevilla", "province": "Sevilla", "pop": 680000}]}
    out = cc.build_output(places, {"41091": [61.23, 35.04, 0.4, 36.02, 5.66]}, {"period": "2015-2024"})
    assert out["m"]["41091"] == [61.2, 35.0, 0.4, 36.0, 5.7, 680000]
    header, rows = cc.climate_csv_rows(out, places["municipalities"])
    assert header[4:] == ["hot_days", "hot_nights", "frost_days", "july_high_c", "january_low_c"]
    assert rows[0][4:] == [61.2, 35.0, 0.4, 36.0, 5.7]
