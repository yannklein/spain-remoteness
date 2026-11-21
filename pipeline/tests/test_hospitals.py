import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hospitals  # noqa: E402

DIR_H = ["CCN", "CODCNH", "Nombre Centro", "Dirección", "Teléfono", "Cód. Municipio", "Municipio",
         "Cód. Provincia", "Provincia", "Cód. CCAA", "CCAA", "Código Postal", "CAMAS",
         "Cód. Clase de Centro", "Clase de Centro", "Cód. Dep. Funcional", "Dependencia Funcional",
         "Forma parte Complejo", "CODIDCOM", "Nombre del Complejo", "ALTA", "Email"]
EST_H = ["CCN", "CODCNH", "Nombre Centro", "Cód. Provincia", "Provincia", "Cód. CCAA", "CCAA", "AD",
         "Cod Concierto", "Concierto", "Forma parte Complejo", "CODIDCOM", "Nombre del Complejo",
         "Es Comlejo", "ALTA", "TAC", "RMN", "GAM", "HEM"]


def d(code, name, muni6, cls, dep, beds=100, comp=None):
    return ["x", code, name, "Calle 1", "", muni6, "M", "", "", "", "", "28001", beds, cls, "", dep, "",
            "S" if comp else "N", comp, None, "N", ""]


def e(code, concierto, hem, comp=None, is_complex="N"):
    return ["x", code, "n", "", "", "", "", "", "", concierto, "S" if comp else "N", comp, None, is_complex,
            "N", "0", "0", "0", hem]


def fixture(tmp_path):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "DIRECTORIO DE HOSPITALES"
    ws.append(DIR_H)
    rows = [
        d("A", "Hospital Público Grande", "280796", "C11", "2"),        # public by dependency, cath lab
        d("B", "Hospital de Figueres", "170665", "C11", "20"),          # private dependency, RUP
        d("C", "Clínica Sustituta", "100370", "C11", "20"),             # private, concierto sustitutorio
        d("D", "Clínica Privada", "280796", "C11", "20"),               # partial concierto -> not public
        d("E", "Hospital en Complejo", "410917", "C11", "2", beds=400, comp="X"),  # main site of complex X
        d("S", "Hospital Satélite", "070241", "C11", "2", beds=20, comp="X"),     # small site, same complex
        d("T", "Hospital Pequeño", "070241", "C11", "2", beds=13),     # reports a cath lab, 13 beds
        d("F", "Hospital Oncológico", "280796", "C12", "2"),
        d("G", "Larga Estancia", "280796", "C13", "2"),
        d("H", "Salud Mental", "280796", "C14", "2"),
    ]
    for r in rows:
        ws.append(r)
    ws2 = wb.create_sheet("ESTRUCTURA FUNCIONAL")
    ws2.append(EST_H)
    for r in [e("A", "Sin concierto", "2"), e("B", "Red de utilización pública (RUP)", "0"),
              e("C", "Concierto sustitutorio", "0"), e("D", "Concierto parcial", "1"),
              e("E", "DC", "DC", comp="X"), e("S", "DC", "DC", comp="X"),
              e("X", "Sin concierto", "3", is_complex="S"),
              e("T", "Sin concierto", "1"), e("F", "Sin concierto", "0"), e("G", "Sin concierto", "0"), e("H", "Sin concierto", "0")]:
        ws2.append(r)
    p = tmp_path / "cnh.xlsx"
    wb.save(p)
    return {h["codcnh"]: h for h in hospitals.read_catalogue(p)}


def test_tiers(tmp_path):
    h = fixture(tmp_path)
    assert h["A"]["tier"] == 1 and h["A"]["public"] and h["A"]["cath_lab"]
    assert h["B"]["tier"] == 2 and h["B"]["public"]           # Catalan public network, private on paper
    assert h["C"]["tier"] == 2
    assert h["D"]["tier"] == 3 and not h["D"]["public"]       # partial agreement is not the public network
    assert h["E"]["tier"] == 1 and h["E"]["cath_lab"]         # equipment read from its complex
    # the complex's cath lab is at its main (largest) site, not at every site (Formentera vs Ibiza)
    assert h["S"]["tier"] == 2 and not h["S"]["cath_lab"] and h["S"]["public"]
    assert h["T"]["tier"] == 2                                # too small to be a major hospital (Formentera)
    assert h["F"]["tier"] is None and h["G"]["tier"] is None and h["H"]["tier"] is None


def test_fields(tmp_path):
    h = fixture(tmp_path)
    assert h["A"]["muni"] == "28079" and h["B"]["muni"] == "17066"
    assert h["A"]["name"] == "Hospital Público Grande" and h["A"]["beds"] == 100
    assert h["A"]["address"] == "Calle 1" and h["A"]["postcode"] == "28001"
