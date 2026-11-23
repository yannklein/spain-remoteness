"""Climate metrics from gridded daily temperatures."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import compute_climate as cc  # noqa: E402


def test_period_mean_selects_years_and_month():
    from datetime import datetime
    dates = [datetime(2014, 7, 1), datetime(2015, 1, 1), datetime(2015, 7, 1), datetime(2024, 7, 1), datetime(2025, 7, 1)]
    values = np.array([[[100.0]], [[0.0]], [[30.0]], [[40.0]], [[100.0]]])
    assert cc.period_mean(values, dates, month=7).tolist() == [[35.0]]       # July 2015 and 2024 only
    assert cc.period_mean(values, dates).tolist() == [[70 / 3]]               # every step of 2015-2024


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
