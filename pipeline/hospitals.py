"""Hospitals from the Catálogo Nacional de Hospitales (Ministerio de Sanidad), with tiers.

Tier 3  Any hospital: general hospital (class C11), private included.
Tier 2  Public hospital: C11 run by a public body (functional dependency 1-8),
        or in the public network by agreement: concierto "Red de utilización
        pública (RUP)" or "Concierto sustitutorio" (e.g. Figueres, Olot,
        Palamós: private on paper, part of Catalonia's public network).
Tier 1  Major hospital: tier 2 with at least one haemodynamics room (HEM,
        a cath lab: heart attacks, strokes, major trauma) and at least
        MAJOR_MIN_BEDS beds (Formentera's 13-bed hospital reports a cath lab).

Specialised (C12), long-stay (C13), mental-health (C14) and other inpatient
centres (C190) are left out. Equipment and concierto marked "DC" ("dato en
complejo") are read from the hospital's complex row (CODIDCOM).
"""

from common import http, paths

CATALOGUE_URL = ("https://www.sanidad.gob.es/estadEstudios/estadisticas/sisInfSanSNS/"
                 "ofertaRecursos/hospitales/docs/CNH_2025.xlsx")
CACHE = paths("es").hospitals_cache
PUBLIC_DEPENDENCIES = {str(i) for i in range(1, 9)}
MAJOR_MIN_BEDS = 100
PUBLIC_CONCIERTOS = {"Red de utilización pública (RUP)", "Concierto sustitutorio"}


def fetch_catalogue():
    f = CACHE / "CNH_2025.xlsx"
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_bytes(http(CATALOGUE_URL, timeout=120))
        tmp.rename(f)
    return f


def _sheet(wb, name):
    rows = wb[name].iter_rows(values_only=True)
    header = [str(h).strip() if h is not None else "" for h in next(rows)]
    return [dict(zip(header, r)) for r in rows if any(v is not None for v in r)]


def _txt(v):
    return "" if v is None else str(v).strip()


def read_catalogue(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    directory = _sheet(wb, "DIRECTORIO DE HOSPITALES")
    structure = {_txt(r["CODCNH"]): r for r in _sheet(wb, "ESTRUCTURA FUNCIONAL")}
    wb.close()

    def field(code, key):
        r = structure.get(code)
        v = _txt(r.get(key)) if r else ""
        if v == "DC":  # value is held by the complex the hospital belongs to
            c = structure.get(_txt(r.get("CODIDCOM")))
            v = _txt(c.get(key)) if c else ""
        return v

    def beds_of(r):
        b = _txt(r.get("CAMAS"))
        return int(b) if b.isdigit() else 0

    # A complex's equipment is counted once for the whole complex; it sits at its main
    # (largest) site, not at every satellite (e.g. Formentera in the Ibiza complex).
    main_site = {}
    for r in directory:
        comp = _txt(r.get("CODIDCOM"))
        if comp and (comp not in main_site or beds_of(r) > main_site[comp][1]):
            main_site[comp] = (_txt(r["CODCNH"]), beds_of(r))

    def equipment(code, key):
        r = structure.get(code)
        if r and _txt(r.get(key)) == "DC":
            comp = _txt(r.get("CODIDCOM"))
            if main_site.get(comp, (None,))[0] != code:
                return "0"
        return field(code, key)

    out = []
    for r in directory:
        code = _txt(r["CODCNH"])
        if not code:
            continue
        cls = _txt(r["Cód. Clase de Centro"])
        public = (_txt(r["Cód. Dep. Funcional"]) in PUBLIC_DEPENDENCIES
                  or field(code, "Concierto") in PUBLIC_CONCIERTOS)
        hem = equipment(code, "HEM")
        cath = hem.isdigit() and int(hem) > 0
        beds = _txt(r.get("CAMAS"))
        tier = None
        if cls == "C11":
            tier = 3
            if public:
                tier = 1 if cath and beds_of(r) >= MAJOR_MIN_BEDS else 2
        out.append({
            "codcnh": code,
            "name": _txt(r["Nombre Centro"]),
            "address": _txt(r.get("Dirección")).rstrip(" -"),
            "postcode": _txt(r.get("Código Postal")),
            "muni": _txt(r["Cód. Municipio"]).zfill(6)[:5],
            "beds": int(beds) if beds.isdigit() else None,
            "cls": cls,
            "public": public,
            "cath_lab": cath,
            "tier": tier,
        })
    return out
