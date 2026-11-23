"""Incentives: official list parsers, coverage rules, outputs."""
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import compute_incentives as ci  # noqa: E402

RANGO_X = """                             Asentamientos Rango X, con ISDT < 100
      Denominación Asentamiento                      Municipio           Provincia
ABABUJ                                 ABABUJ                        TERUEL
ABELLA                                 LASPAÚLES                     HUESCA
ALDEHUELA DE SANTA CRUZ (LA)           SANTA CRUZ DE GRÍO            ZARAGOZA
VILLANUEVA DEL REBOLLAR DE LA SIERRA   VILLANUEVA DEL REBOLLAR DE LA SIERRA TERUEL
BLECUA                                 BLECUA Y TORRES               HUESCA
"""
CONCEJOS = """                  CONCEJO                     TIPOLOGÍA
Allande                      Concejos en riesgo de despoblamiento
Bimenes                      Concejos en crisis demográfica
"""
CLM_RESIDENCE = """Código INE              Núcleo/Barrio/Pedanía      Provincia            Clasificación de Zona     habitual
02021        Casas de Juan Núñez                ALBACETE       INTENSA DESPOBLACIÓN                        20
02024        Casas-Ibáñez                       ALBACETE       INTERMEDIA AGRÍCOLA                          0
02021        Some pedanía                       ALBACETE       EXTREMA DESPOBLACIÓN                        25
"""
CLM_PURCHASE = """           Núcleo/Barrio/Pedanía      Provincia   Código INE          Clasificación de Zona   vivienda
Abengibre                          ALBACETE       02001        INTENSA DESPOBLACIÓN                          15
"""
RIOJA = """ Anexo: Relación de municipios de La Rioja con
 derecho a deducción: "Por la adquisición,
 construcción o rehabilitación de vivienda habitual
 en pequeños municipios de La Rioja”, “Por cada hijo de 0 a 3 años”
    Código             Municipio             Código               Municipio      Código                Municipio
      12      Abalos                           630      Fonzaleche                1275     Rodezno
21/10/2026 - Manual práctico de Renta 2025. Parte 2. Deducciones autonómicas                     Página 524
                                   Anexo: Relación de municipios de La Rioja con derecho a deducción: "Por la adquisición, const
      129     Robres del Castillo              1036     Nalda                  913      Lumbreras
 Anexo: Relación de municipios de La Rioja con
 derecho a deducción: "Por adquisición o
    Código              Municipio
      999      Elsewhere
"""
MUNIS = [
    {"code": "44001", "name": "Ababuj", "province": "Teruel", "pop": 73, "lat": 40.55, "lng": -0.81},
    {"code": "22140", "name": "Laspaúles", "province": "Huesca", "pop": 250, "lat": 42.47, "lng": 0.6},
    {"code": "50235", "name": "Santa Cruz de Grío", "province": "Zaragoza", "pop": 150, "lat": 41.37, "lng": -1.43},
    {"code": "44256", "name": "Villanueva del Rebollar de la Sierra", "province": "Teruel", "pop": 60, "lat": 41.0, "lng": -1.0},
    {"code": "22066", "name": "Blecua y Torres", "province": "Huesca", "pop": 200, "lat": 42.1, "lng": -0.2},
    {"code": "33001", "name": "Allande", "province": "Asturias", "pop": 1600, "lat": 43.27, "lng": -6.61},
    {"code": "33006", "name": "Bimenes", "province": "Asturias", "pop": 1700, "lat": 43.33, "lng": -5.55},
    {"code": "33044", "name": "Oviedo", "province": "Asturias", "pop": 220000, "lat": 43.36, "lng": -5.85},
]


def test_rango_x_maps_settlements_to_their_municipality():
    got = ci.parse_rango_x(RANGO_X, MUNIS)
    # Ababuj and Villanueva (one space before the province) are their own settlement; Blecua is Blecua y Torres's
    assert got == {"44001": None, "22140": "partial", "50235": "partial", "44256": None, "22066": None}


def test_concejos_by_name():
    assert ci.parse_concejos(CONCEJOS, MUNIS) == {"33001": None, "33006": None}


def test_clm_lists_keep_the_best_value_per_code_and_drop_zero():
    assert ci.parse_clm(CLM_RESIDENCE) == {"02021": 25}
    assert ci.parse_clm(CLM_PURCHASE) == {"02001": 15}


def test_valencia_fund_this_year_or_the_previous():
    text = 'WKT,id,cod_ine_mun,fondo_coop_mun_2023,fondo_coop_mun_2024,fondo_coop_mun_2025,noms_mun\n' \
           '"POLY",1,12081,S,S,S,Navajas\n"POLY",2,46250,N,N,N,València\n"POLY",3,3001,N,S,N,Atzúbia\n'
    assert ci.parse_valencia(text) == {"12081", "03001"}


RIOJA_MUNIS = [{"code": c, "name": n} for c, n in (("26001", "Ábalos"), ("26063", "Fonzaleche"), ("26127", "Rodezno"),
                                                    ("26012", "Almarza de Cameros"), ("26126", "Robres del Castillo"),
                                                    ("26103", "Nalda"), ("26091", "Lumbreras de Cameros"))]


def test_rioja_first_annex_across_page_headers_with_codes_checked_against_names():
    # 129 is a typo in the manual (it reads as 26012, Almarza): the name wins; "0 a 3 años" is not a row
    assert ci.parse_rioja(RIOJA, RIOJA_MUNIS) == {"26001", "26063", "26127", "26126", "26103", "26091"}


def test_cover_rules():
    munis = MUNIS + [{"code": "24089", "name": "León", "province": "León", "pop": 120000, "lat": 42.6, "lng": -5.57},
                     {"code": "24900", "name": "Near León", "province": "León", "pop": 5000, "lat": 42.65, "lng": -5.6},
                     {"code": "24901", "name": "Far village", "province": "León", "pop": 5000, "lat": 42.9, "lng": -6.6}]
    capitals = {"24": (42.6, -5.57)}
    assert ci.covered({"pop_lt": 2000}, ["33"], munis, capitals) == {"33001", "33006"}
    assert ci.covered({"region": True}, ["33"], munis, capitals) == {"33001", "33006", "33044"}
    # 10,000 in general, 3,000 within 30 km of the capital
    assert ci.covered({"cyl_rural": True}, ["24"], munis, capitals) == {"24901"}


def test_output_rows_and_details():
    offers = [dict(id="a", kind="tax"), dict(id="b", kind="grant")]
    cover = {"a": {"33001": "25%"}, "b": {"33001": None, "33006": None}}
    out = ci.build_output({"meta": {}, "municipalities": MUNIS}, offers, cover, {})
    assert out["m"]["33001"] == [[0, "25%"], [1, None]]
    assert out["m"]["33044"] == []
    header, rows = ci.incentives_csv_rows(out, MUNIS)
    assert header[4:] == ["n_tax", "n_grant", "n_business", "offers"]
    assert rows[5][4:] == [1, 1, 0, "a; b"]


@pytest.mark.parametrize("cc", ["es", "fr"])
def test_config_is_consistent(cc):
    cfg = importlib.import_module(f"countries.{cc}_incentives")
    ids = [o["id"] for o in cfg.OFFERS]
    assert len(ids) == len(set(ids))
    for o in cfg.OFFERS:
        assert o["kind"] in ("tax", "grant", "business") and o["title"] and o["amount"] and o["source"] and o["valid"]
        assert o["age_max"] in (None, 35, 36, 40)
        if cc == "es":
            assert set(o["cover"]) <= {"pop_lt", "pop_le", "region", "list", "codes", "cyl_rural"}
            assert all(len(p) == 2 for p in o["provinces"])
            if "list" in o["cover"]:
                assert o["cover"]["list"] in cfg.LISTS
