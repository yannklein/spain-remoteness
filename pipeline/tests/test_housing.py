"""Housing prices: readers, nearby estimates, scopes, outputs."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import compute_housing as ch  # noqa: E402


def test_serpavi_takes_the_latest_year_with_a_value():
    header = ["CPRO", "NPRO", "CUMUN", "NMUN",
              "BI_ALVHEPCO_TVC_23", "BI_ALVHEPCO_TVU_23", "ALQM2_LV_M_VC_23", "ALQM2_LV_M_VU_23",
              "BI_ALVHEPCO_TVC_24", "BI_ALVHEPCO_TVU_24", "ALQM2_LV_M_VC_24", "ALQM2_LV_M_VU_24"]
    rows = [["44", "Teruel", "44216", "Teruel", 300, 40, 6.0, 4.5, 320, None, 6.5, None],
            ["01", "Araba", "01001", "Alegría", None, None, None, None, None, None, None, None]]
    got = ch.read_serpavi(header, rows)
    assert got["44216"] == {"rf": (6.5, 320, 2024), "rh": (4.5, 40, 2023)}
    assert "01001" not in got


def test_appraisal_sheet_carries_the_province_down():
    rows = [["", "Provincia", "Municipio", "Valor tasado de vivienda", "", "", "", "Número de tasaciones", "", ""],
            ["", "", "", "Hasta cinco años", "Con más de cinco años", "Total", "", "Hasta", "Más", "Total"],
            ["", "Almería", "Almería", "2397.6", "1769.2", "1796.4", "", "88.0", "635.0", "723.0"],
            ["", "", "Ejido (El)", "n.r", "1360.8", "1371.6", "", "20.0", "352.0", "372.0"],
            ["", "Cádiz", "Rota", "n.r", "2889.9", "2877.5", "", "9.0", "120.0", "129.0"],
            ["", "Fuente: ...", "", "", "", "", "", "", "", ""]]
    assert ch.read_appraisal_sheet(rows) == [("Almería", "Almería", 1796.4, 723), ("Almería", "Ejido (El)", 1371.6, 372),
                                             ("Cádiz", "Rota", 2877.5, 129)]


def test_names_match_with_articles_and_bilingual_forms():
    assert ch.normalise("Ejido (El)") == ch.normalise("El Ejido")
    assert ch.normalise("Palmas de Gran Canaria (Las)") == ch.normalise("Las Palmas de Gran Canaria")
    munis = [{"code": "04902", "name": "El Ejido", "province": "Almería", "pop": 84000},
             {"code": "03014", "name": "Alacant", "province": "Alacant", "pop": 360000},
             {"code": "03065", "name": "Elx", "province": "Alacant", "pop": 240000},
             {"code": "04013", "name": "Almería", "province": "Almería", "pop": 200000}]
    provinces = {ch.normalise("Almería"): "04", ch.normalise("Alicante"): "03"}   # the Ministry's own names and codes
    towns = [("Almería", "Ejido (El)", 1371.6, 372), ("Alicante", "Alicante", 2000.0, 900), ("Alicante", "Elche", 1800.0, 500),
             ("Almería", "Nowhere", 1.0, 1)]
    matched, unmatched = ch.match_towns(towns, munis, provinces)
    assert matched == {"04902": (1371.6, 372), "03014": (2000.0, 900), "03065": (1800.0, 500)}
    assert unmatched == ["Nowhere (Almería)"]


def test_province_csv_latest_free_market_quarter():
    text = ("﻿Año;Trimestre;Valor;Régimen;CPRO;Provincia;Comunidad_Autónoma;CODAUTO\n"
            "2026;1;1000,5;Libre;4;Almería;Andalucía;1\n2026;2;1010,0;Libre;4;Almería;Andalucía;1\n"
            "2026;2;;Protegida;4;Almería;Andalucía;1\n2026;2;900;Libre;44;Teruel;Aragón;2\n2026;3;;Libre;44;Teruel;Aragón;2\n"
            "2026;2;4000;Libre;;Total CCAA;Madrid;13\n2026;2;1500;Libre;;Total CCAA;Andalucía;1\n")
    # single-province regions (Madrid) only appear as region totals; other totals are ignored
    assert ch.read_province_csv(text) == ("2026 Q2", {"04": 1010.0, "44": 900.0, "28": 4000.0})


def test_anil_marks_pooled_or_weak_predictions_as_area_model():
    rows = [{"INSEE_C": "37099", "loypredm2": "8,9", "TYPPRED": "maille", "nbobs_com": "54", "R2_adj": "0,75"},
            {"INSEE_C": "75056", "loypredm2": "25,3", "TYPPRED": "commune", "nbobs_com": "9000", "R2_adj": "0,8"},
            {"INSEE_C": "23096", "loypredm2": "7,1", "TYPPRED": "commune", "nbobs_com": "12", "R2_adj": "0,7"}]
    assert ch.read_anil(rows) == {"37099": (8.9, 54, 3), "75056": (25.3, 9000, 0), "23096": (7.1, 12, 3)}


def test_dvf_commune_medians_with_counts():
    rows = [{"code_geo": "23096", "echelle_geo": "commune", "nb_ventes_whole_maison": "520", "med_prix_m2_whole_maison": "1174",
             "nb_ventes_whole_appartement": "0", "med_prix_m2_whole_appartement": ""},
            {"code_geo": "23", "echelle_geo": "departement", "nb_ventes_whole_maison": "9", "med_prix_m2_whole_maison": "9"}]
    assert ch.read_dvf(rows) == {"23096": {"bh": (1174.0, 520)}}


def test_nearby_estimate_is_count_weighted_and_needs_enough_evidence():
    pts = {"A": (0.0, 40.0), "B": (0.05, 40.0), "C": (0.06, 40.0), "FAR": (1.0, 40.0)}
    own = {"B": (4.0, 30), "C": (6.0, 10), "FAR": (100.0, 1000)}
    got = ch.pool_nearby(pts, own, min_count=10)
    assert got == {"A": (4.5, 40)}            # (4*30 + 6*10) / 40; FAR is beyond 10 km; B and C have their own
    assert ch.pool_nearby(pts, own, min_count=50) == {}


def test_output_rows_scopes_and_missing_values():
    places = {"meta": {"population_year": 2025}, "municipalities": [
        {"code": "44216", "name": "Teruel", "province": "Teruel", "pop": 36000},
        {"code": "48001", "name": "Abadiño", "province": "Bizkaia", "pop": 7000}]}
    values = {"44216": {"rh": (4.53, 40, 0), "rf": (6.5, 320, 0), "bh": (1234.0, 50, 2), "bf": (1234.0, 50, 2)},
              "48001": {"bh": (2500.0, 10, 2), "bf": (2500.0, 10, 2)}}
    out = ch.build_output(places, values, {"sources": []})
    assert out["m"]["44216"] == [4.5, 6.5, 1230, 1230, 0, 0, 2, 2, 40, 320, 50, 50, 36000]
    assert out["m"]["48001"][:4] == [None, None, 2500, 2500] and out["m"]["48001"][4:6] == [None, None]
    header, rows = ch.housing_csv_rows(out, places["municipalities"])
    assert header[:8] == ["code", "name", "province", "population", "rent_house", "rent_flat", "buy_house", "buy_flat"]
    assert rows[0][8:12] == ["own", "own", "province", "province"]
    assert rows[1][4:6] == [None, None] and rows[1][8:10] == [None, None]


def test_anil_arrondissements_merge_into_their_city():
    rows = [{"INSEE_C": "75101", "loypredm2": "30", "TYPPRED": "commune", "nbobs_com": "100", "R2_adj": "0,8"},
            {"INSEE_C": "75120", "loypredm2": "20", "TYPPRED": "commune", "nbobs_com": "300", "R2_adj": "0,8"}]
    assert ch.read_anil(rows) == {"75056": (22.5, 400, 0)}
