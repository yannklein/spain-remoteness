"""Setting: green cover, relief, summer greenness, village character."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import compute_setting as cs  # noqa: E402


def test_tile_names():
    assert cs.worldcover_tile(40.4, -3.7) == "N39W006"
    assert cs.worldcover_tile(43.3, 5.4) == "N42E003"
    assert cs.dem_tile(40.4, -3.7) == "Copernicus_DSM_COG_30_N40_00_W004_00_DEM"
    assert cs.dem_tile(-0.5, 0.5) == "Copernicus_DSM_COG_30_S01_00_E000_00_DEM"


class FakeGrid(cs.TileGrid):
    """1° tiles of 0.01° pixels whose value is the tile's own number, row-major from the top."""
    def load(self, key):
        lat0, lon0 = key
        arr = np.full((100, 100), 10 * (lat0 % 10) + (lon0 % 10), dtype=np.int16)
        arr[:50, :] += 50   # northern half of each tile differs
        return arr, lat0 + 1, lon0, 0.01, 0.01

    def key(self, lat, lon):
        import math
        return (math.floor(lat), math.floor(lon))


def test_circle_reads_across_tiles():
    g = FakeGrid(tile_deg=1)
    vals = g.values_in_circle(40.0, 3.0, 5)          # the corner of four tiles
    assert {int(v) for v in np.unique(vals)} == {2, 3, 142, 143}   # south halves of the 40° tiles, north halves of the 39° ones
    km = 5
    assert abs(len(vals) - np.pi * (km / 1.1132) ** 2 / np.cos(np.radians(40)) * 100 / 100) < 40   # ~ circle area in pixels


def test_cover_shares():
    vals = np.array([10, 10, 20, 40, 50, 80, 0, 30])
    got = cs.cover_shares(vals)
    # nature and built-up are shares of the land (water is not counted against them); water is a share of everything
    assert got == {"nature": 4 / 6 * 100, "water": 1 / 7 * 100, "built": 1 / 6 * 100}   # 0 = no data, left out
    assert cs.cover_shares(np.array([0, 0])) is None


def test_relief():
    assert cs.relief(np.array([450.0, 900.0, -32767.0, 600.0])) == 450.0     # nodata left out
    assert cs.relief(np.array([], dtype=float)) is None


def test_pmb_cards():
    html = ('<h3>Agulo</h3><p>La Gomera</p>, <p>Canarias</p><img>'
            '<h3 class="x">Alcúdia</h3><span>Mallorca</span> , <span>Illes Balears</span>')
    assert cs.parse_pmb(html) == [("Agulo", "La Gomera", "Canarias"), ("Alcúdia", "Mallorca", "Illes Balears")]


def test_pmb_matching_uses_the_region():
    munis = [{"code": "10164", "name": "San Martín de Trevejo", "lat": 40.2, "lng": -6.79},
             {"code": "07003", "name": "Alcúdia", "lat": 39.85, "lng": 3.12},
             {"code": "46025", "name": "L'Alcúdia", "lat": 39.19, "lng": -0.5},
             {"code": "38001", "name": "Agulo", "lat": 28.18, "lng": -17.19}]
    got, missing = cs.match_pmb([("Agulo", "La Gomera", "Canarias"), ("Alcúdia", "Mallorca", "Illes Balears"),
                                 ("Nowhere", "X", "Aragón"), ("Bulnes", "Asturias", "Principado de Asturias"),
                                 ("Trevejo", "Cáceres", "Extremadura")], munis)
    # Bulnes is a village of Cabrales (33008), Trevejo of Villamiel (10210), not San Martín de Trevejo
    assert got == {"38001", "07003", "33008", "10210"} and missing == ["Nowhere (Aragón)"]


def test_merimee_counts_by_code_then_coordinates():
    rows = [{"COG_Insee_lors_de_la_protection": "10064", "coordonnees_au_format_WGS84": ""},
            {"COG_Insee_lors_de_la_protection": "75104", "coordonnees_au_format_WGS84": ""},
            {"COG_Insee_lors_de_la_protection": "99999", "coordonnees_au_format_WGS84": "48.1, 2.5"},
            {"COG_Insee_lors_de_la_protection": "10064", "coordonnees_au_format_WGS84": ""}]
    codes = {"10064", "75056", "45001"}
    got = cs.count_merimee(rows, codes, lambda lng, lat: "45001" if lat > 48 else None)
    assert got == {"10064": 2, "75056": 1, "45001": 1}


def test_output_rows_and_csv():
    places = {"meta": {}, "municipalities": [{"code": "44001", "name": "Ababuj", "province": "Teruel", "pop": 73}]}
    values = {"44001": {"nature": 61.24, "water": 0.0, "built": 1.04, "ndvi": 0.4123, "relief": 312.6, "elev": 1281.2,
                        "label": None, "historic": 0, "listed": 1}}
    out = cs.build_output(places, values, {})
    assert out["m"]["44001"] == [61.2, 0.0, 1.0, 0.41, 313, 1281, None, 0, 1, 73]
    header, rows = cs.setting_csv_rows(out, places["municipalities"])
    assert header[4:] == ["nature_pct", "water_pct", "built_pct", "ndvi_july", "relief_m", "elevation_m", "label",
                          "historic_centre", "listed_buildings"]
    assert rows[0][4:] == [61.2, 0.0, 1.0, 0.41, 313, 1281, None, 0, 1]


def test_labelled_villages_by_name_first():
    munis = [{"code": "24284", "name": "Monpazier", "lat": 44.68, "lng": 0.89},
             {"code": "24081", "name": "Capdrot", "lat": 44.68, "lng": 0.95},
             {"code": "74999", "name": "Saint-Martin", "lat": 46.0, "lng": 6.0},
             {"code": "38999", "name": "Saint-Martin", "lat": 45.2, "lng": 5.7}]
    rows = [{"nom": "Monpazier", "latitude": "44.68", "longitude": "0.95"},      # the point falls in Capdrot
            {"nom": "Saint-Martin", "latitude": "45.21", "longitude": "5.71"},   # two namesakes: the nearest
            {"nom": "Lost", "latitude": "1", "longitude": "1"}]
    assert cs.locate_named(rows, munis, lambda lng, lat: "24081") == {"24284", "38999", "24081"}


def test_historic_centre_contains_the_town_centre():
    square = {"type": "MultiPolygon", "coordinates": [[[[5.0, 43.0], [5.1, 43.0], [5.1, 43.1], [5.0, 43.1], [5.0, 43.0]]],
                                                      [[[6.0, 43.0], [6.1, 43.0], [6.1, 43.1], [6.0, 43.1], [6.0, 43.0]]]]}
    munis = [{"code": "A", "lat": 43.05, "lng": 5.05}, {"code": "B", "lat": 43.05, "lng": 6.05},
             {"code": "C", "lat": 43.05, "lng": 5.5}]
    assert cs.centres_inside([square], munis) == {"A", "B"}   # every part counts; C is outside
