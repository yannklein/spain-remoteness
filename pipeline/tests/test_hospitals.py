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


# --- placing hospitals ------------------------------------------------------

import place_hospitals as ph  # noqa: E402


def test_normalise_drops_generic_words_and_accents():
    assert ph.normalise("Hospital Universitario Gregorio Marañón") == "gregorio maranon"
    assert ph.normalise("Clínica Universidad de Navarra") == "universidad navarra"
    assert ph.normalise("Hospital D'Olot I Comarcal de La Garrotxa") == "olot garrotxa"


def osm(id_, name, muni, lat=40.0, lng=-3.0):
    return {"id": id_, "name": name, "muni": muni, "lat": lat, "lng": lng, "entrances": []}


def test_match_within_same_municipality_only():
    pamplona = {"codcnh": "1", "name": "Hospital San Juan de Dios", "muni": "31201"}
    cands = [osm("w1", "Hospital San Juan de Dios", "14021"),        # Córdoba: same name, wrong town
             osm("w2", "Clínica San Juan de Dios", "31201")]
    assert ph.match(pamplona, cands)["id"] == "w2"
    assert ph.match({"codcnh": "2", "name": "Hospital San Juan de Dios", "muni": "08019"}, cands) is None


def test_match_needs_enough_overlap():
    h = {"codcnh": "1", "name": "Hospital Universitario Río Hortega", "muni": "47186"}
    assert ph.match(h, [osm("w1", "Hospital Clínico Universitario de Valladolid", "47186")]) is None
    assert ph.match(h, [osm("w2", "Hospital Universitario Río Hortega", "47186")])["id"] == "w2"


def test_pick_point_prefers_close_stop():
    h = {"lat": 40.0, "lng": -3.0, "entrances": [(40.0005, -3.0005)]}
    near = {"lat": 40.002, "lng": -3.0, "name": "Hospital"}          # ~220 m
    far = {"lat": 40.0045, "lng": -3.0, "name": "Lejos"}             # ~500 m
    assert ph.pick_point(h, [far, near]) == (40.002, -3.0, "stop", "Hospital")
    assert ph.pick_point(h, [far]) == (40.0005, -3.0005, "entrance", None)
    assert ph.pick_point({"lat": 40.0, "lng": -3.0, "entrances": []}, [far]) == (40.0, -3.0, "osm", None)


# --- travel times -----------------------------------------------------------

import compute_hospitals as chos  # noqa: E402
import compute_times  # noqa: E402
from common import PLACES_FILE, load_json  # noqa: E402
from test_pipeline import fake_post  # noqa: E402


def placed(code, name, muni, lat, lng, tier):
    return {"codcnh": code, "name": name, "muni": muni, "lat": lat, "lng": lng, "tier": tier,
            "beds": 100, "public": tier <= 2, "cath_lab": tier == 1, "point_source": "stop"}


PLACED = [
    placed("H1", "Gran Hospital", "28079", 40.42, -3.70, 1),          # Madrid
    placed("H2", "Hospital Teruel", "44216", 40.34, -1.11, 2),
    placed("H3", "Clínica Privada", "44216", 40.345, -1.105, 3),
    placed("H4", "Hospital Ceuta", "51001", 35.89, -5.32, 2),
    placed("H5", "Hospital Fantasma", "50297", 0.0, 0.0, 2),          # unreachable point
]


def run(monkeypatch, tmp_path):
    monkeypatch.setenv("TRAVELTIME_APP_ID", "x")
    monkeypatch.setenv("TRAVELTIME_API_KEY", "y")
    monkeypatch.setattr(compute_times.Client, "post", fake_post)
    places = load_json(PLACES_FILE)
    dests = chos.destinations(PLACED, places)
    results = compute_times.compute_all(places["municipalities"], dests, compute_times.Client("regular"),
                                        use_cache=False, cdir=tmp_path)
    hs, rows = chos.aggregate_hospitals(places["municipalities"], dests, results)
    return places, dests, results, hs, rows


def test_destinations_take_zone_from_municipality():
    places = load_json(PLACES_FILE)
    d = {x["codcnh"]: x for x in chos.destinations(PLACED, places)}
    assert d["H4"]["zone"] == "ceuta" and d["H1"]["zone"] == "mainland"
    assert d["H1"]["code"] == "HOS:H1"


def test_nested_tiers_and_ceuta(monkeypatch, tmp_path):
    places, dests, results, hs, rows = run(monkeypatch, tmp_path)
    idx = {h["codcnh"]: i for i, h in enumerate(hs)}
    for code, (t1, h1, t2, h2, t3, h3) in rows.items():
        if t1 >= 0:
            assert 0 <= t2 <= t1
        if t2 >= 0:
            assert 0 <= t3 <= t2
    assert rows["51001"][3] == idx["H4"]                # Ceuta reaches its own hospital
    assert rows["11004"][3] != idx["H4"]                # Algeciras never crosses the sea
    assert rows["44216"][5] in (idx["H2"], idx["H3"])   # Teruel: nearest any-hospital is local


def test_unreached_hospital_is_noted(monkeypatch, tmp_path):
    places, dests, results, hs, rows = run(monkeypatch, tmp_path)
    out = chos.build_output(places, hs, rows, results)
    reach = {h[0]: h[9] for h in out["hospitals"]}
    assert reach["H5"] == 0 and reach["H1"] > 0
    assert any("Hospital Fantasma" in n for n in out["params"]["notes"])
    header, csv_rows = chos.hospitals_csv_rows(out, places["municipalities"])
    assert header == ["code", "name", "province", "population", "t1_min", "t1_hospital",
                      "t2_min", "t2_hospital", "t3_min", "t3_hospital"]
    assert len(csv_rows) == 8132


def test_partial_run_writes_nothing(monkeypatch, tmp_path):
    monkeypatch.setenv("TRAVELTIME_APP_ID", "x")
    monkeypatch.setenv("TRAVELTIME_API_KEY", "y")
    monkeypatch.setattr(compute_times.Client, "post", fake_post)
    p = tmp_path / "placed.json"
    p.write_text(__import__("json").dumps(PLACED))
    monkeypatch.setattr(chos, "PLACED_FILE", p)
    monkeypatch.setattr(chos, "OUTPUT_FILE", tmp_path / "hospitals.json")
    monkeypatch.setattr(chos, "CSV_FILE", tmp_path / "hospitals.csv")
    monkeypatch.setattr(chos, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(sys, "argv", ["compute_hospitals.py", "--only", "H1"])
    chos.main()
    assert not (tmp_path / "hospitals.json").exists() and not (tmp_path / "hospitals.csv").exists()


def test_match_basque_genitive_and_local_generic_words():
    for cat, osm_name, muni in [("Hospital de Zumarraga (Osi Goierri - Alto Urola)", "Zumarragako Ospitalea", "20080"),
                                ("Hospital Bidasoa (Osi Bidasoa)", "Bidasoko Ospitalea", "20036"),
                                ("Organización Sanitaria Integrada Debagoiena", "Debagoieneko Ospitalea", "20055")]:
        h = {"codcnh": "1", "name": cat, "muni": muni}
        assert ph.match(h, [osm("w", osm_name, muni)]) is not None, cat
    # a shared beginning of 3 letters is not enough
    assert ph.match({"codcnh": "1", "name": "Hospital San Rafael", "muni": "1"}, [osm("w", "Hospital Santa Ana", "1")]) is None


def test_overrides_place_named_osm_hospital(tmp_path):
    over = {"15073": {"osm_name": "Hospital da Barbanza"}, "36038": {"lat": 42.43, "lng": -8.66, "note": "Montecelo"}}
    cands = [osm("w9", "Hospital da Barbanza", "15073", 42.6, -8.9)]
    assert ph.apply_override({"codcnh": "15073", "muni": "15073"}, over, cands)["id"] == "w9"
    a = ph.apply_override({"codcnh": "36038", "muni": "36038"}, over, cands)
    assert (a["lat"], a["lng"]) == (42.43, -8.66)
    assert ph.apply_override({"codcnh": "x", "muni": "1"}, over, cands) is None


def test_ring_points_start_at_the_point_and_widen():
    import nudge_hospitals as nh
    from common import haversine_km
    pts = nh.ring(40.0, -3.0)
    assert pts[0] == (0, 40.0, -3.0)
    dists = [round(haversine_km(40.0, -3.0, lat, lng) * 1000) for _, lat, lng in pts[1:]]
    assert dists == sorted(dists) and 190 <= dists[0] <= 210 and 590 <= dists[-1] <= 610
    assert len(pts) == 1 + 3 * 8


def test_first_attaching_point_is_chosen():
    import nudge_hospitals as nh
    tried = []

    def reach(lat, lng):
        tried.append((lat, lng))
        return 25 if len(tried) == 4 else None

    got = nh.first_reachable(nh.ring(40.0, -3.0), reach)
    assert got[1:3] == tried[3] and got[3] == 25 and len(tried) == 4
    assert nh.first_reachable(nh.ring(40.0, -3.0), lambda a, b: None) is None


def test_common_religious_words_do_not_make_a_match():
    h = {"codcnh": "1", "name": "Hospital Nuestra Señora de Gracia", "muni": "50297"}
    assert ph.match(h, [osm("w", "Centro Neuropsiquiátrico Nuestra Señora del Carmen", "50297")]) is None
    h = {"codcnh": "2", "name": "Hospital Virgen de La Luz", "muni": "16078"}
    assert ph.match(h, [osm("w", "Hospital Virgen del Puerto", "16078")]) is None


def test_exact_override_skips_stop_snapping():
    over = {"9": {"lat": 40.0, "lng": -3.0, "exact": True}}
    a = ph.apply_override({"codcnh": "9", "muni": "1"}, over, [])
    assert a["exact"] is True
    stop = {"lat": 40.001, "lng": -3.0, "name": "Parada"}
    assert ph.place_anchor(a, [stop])[:3] == (40.0, -3.0, "override")


def test_moved_hospitals_lose_their_cache(tmp_path):
    cdir = tmp_path / "c"
    cdir.mkdir()
    (cdir / "HOS:A.json").write_text("{}")
    (cdir / "HOS:B.json").write_text("{}")
    pos = tmp_path / "positions.json"
    pos.write_text('{"HOS:A": [40.0, -3.0], "HOS:B": [41.0, -2.0]}')
    dests = [{"code": "HOS:A", "lat": 40.0, "lng": -3.0}, {"code": "HOS:B", "lat": 41.1, "lng": -2.0}]
    chos.invalidate_moved(dests, cdir, pos)
    assert (cdir / "HOS:A.json").exists() and not (cdir / "HOS:B.json").exists()
    assert __import__("json").loads(pos.read_text())["HOS:B"] == [41.1, -2.0]


def test_probe_only_override_is_not_a_position():
    over = {"7": {"unattachable_at": [40.0, -3.0]}}
    assert ph.apply_override({"codcnh": "7", "muni": "1"}, over, []) is None
