import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build_places_fr as bp  # noqa: E402
from common import paths, zone  # noqa: E402
from countries import fr  # noqa: E402


def c(code, name, dep, pop):
    return {"code": code, "nom": name, "codeDepartement": dep, "population": pop,
            "mairie": {"coordinates": [2.0, 48.0]}, "centre": {"coordinates": [2.1, 48.1]}}


COMMUNES = [
    c("75056", "Paris", "75", 2100000),           # métropole
    c("2A004", "Ajaccio", "2A", 72000),           # préfecture, Corsica
    c("51108", "Châlons-en-Champagne", "51", 44000),  # préfecture in the Marne (code 51!)
    c("59599", "Tourcoing", "59", 98000),         # > 50k only
    c("93066", "Saint-Denis", "93", 113000),      # > 100k
    c("48095", "Mende", "48", 12000),             # préfecture
    c("48001", "Albaret-le-Comtal", "48", 200),
    c("97101", "Les Abymes", "971", 53000),       # overseas: out of scope
]


def test_classify_and_zones():
    places = {p["code"]: p for p in bp.build(COMMUNES, metropoles={("75", "Paris")},
                                             prefectures={("2A", "Ajaccio"), ("51", "Châlons-en-Champagne"),
                                                          ("48", "Mende")})}
    assert "97101" not in places                              # metropolitan France only
    assert places["75056"]["tier"] == 1
    assert places["2A004"]["tier"] == 2 and places["2A004"]["zone"] == "island:Corse"
    assert places["51108"]["tier"] == 2 and zone(places["51108"]) == "mainland"   # not Ceuta!
    assert places["93066"]["tier"] == 2 and places["59599"]["tier"] == 3
    assert places["48095"]["tier"] == 2 and places["48001"]["tier"] is None
    p = places["48001"]
    assert (p["lng"], p["lat"]) == (2.0, 48.0) and p["point"] == "mairie" and p["province"] == "48"
    assert isinstance(p["code"], str) and p["urban"] is False


def test_named_lists_resolve_to_codes():
    found = bp.resolve({("2A", "Ajaccio"), ("48", "Mende")}, COMMUNES)
    assert found == {"2A004", "48095"}
    with pytest.raises(SystemExit):
        bp.resolve({("48", "Nowhere")}, COMMUNES)


def test_config_lists():
    assert len(fr.METROPOLES) == 22 and len(fr.PREFECTURES) == 96
    assert len(fr.METRO_DEPARTMENTS) == 96 and "2A" in fr.METRO_DEPARTMENTS and "20" not in fr.METRO_DEPARTMENTS


@pytest.mark.skipif(not paths("fr").places.exists(), reason="France places not built yet")
def test_real_places_match_boundaries():
    from common import load_json
    from geo import load_municipalities
    pl = load_json(paths("fr").places)["municipalities"]
    topo = load_municipalities(paths("fr").topo)
    codes = {m["code"] for m in pl}
    assert 34000 < len(codes) < 35500
    assert codes == set(topo)
    by = {m["code"]: m for m in pl}
    assert sum(1 for m in pl if m["tier"] == 1) == 22 and by["2B033"]["zone"] == "island:Corse"


# --- internet ---------------------------------------------------------------

ARCEP = """code_insee;nom_com;code_dep;code_reg;nbr;type;inel_hd;elig_hd05;elig_hd3;elig_bhd8;elig_thd30;elig_thd100;elig_thd1g;date
16123;Échallat;16;75;278;all;5;273;273;273;273;273;250;2026-06-30
16123;Échallat;16;75;200;res;5;195;195;195;195;195;180;2026-06-30
2A004;Ajaccio;2A;94;40000;all;0;40000;40000;40000;39000;38000;36000;2026-06-30
48001;Albaret;48;76;0;all;0;0;0;0;0;0;0;2026-06-30
"""


def test_read_arcep_coverage(tmp_path):
    import compute_internet as ci
    p = tmp_path / "commune_debit_filaire.csv"
    p.write_text(ARCEP, encoding="utf-8")
    date, cov = ci.read_coverage_arcep(p)
    assert date == "2026-06-30"
    assert cov["16123"] == [98, 90, None]            # type "all" only; % of premises; no 5G per commune
    assert cov["2A004"] == [95, 90, None]            # codes stay strings
    assert cov["48001"] == [None, None, None]        # no premises: unknown, not 0%


def test_configure_france_internet():
    import compute_internet as ci
    try:
        ci.configure("fr")
        assert ci.BBOX == fr.BBOX and ci.CACHE == paths("fr").internet_cache
        assert ci.INTERNET_OUTPUT_FILE == paths("fr").internet_json
    finally:
        ci.configure("es")
    assert ci.CACHE == paths("es").internet_cache


# --- airports ---------------------------------------------------------------

def test_france_airport_list():
    import re
    from countries import fr_airports as fa
    codes = [a[0] for a in fa.AIRPORTS]
    assert len(codes) == len(set(codes)) and all(re.fullmatch(r"[A-Z]{3}", c) for c in codes)
    by = {a[0]: a for a in fa.AIRPORTS}
    for iata, _, country, lat, lng, ty, ts, z, note in fa.AIRPORTS:
        assert country in ("FR", "CH", "LU", "BE", "DE", "ES"), iata
        assert z in ("mainland", "island:Corse"), iata
        assert 41.0 <= lat <= 51.5 and -5.5 <= lng <= 10.0, iata
        if ty is not None:
            assert ts is not None and ts <= ty, iata
        if ty is None and ts is None:
            assert note.strip(), iata
    assert by["CDG"][5] == 1 and by["ORY"][5] == 1
    assert {by[c][7] for c in ("AJA", "BIA", "FSC", "CLY")} == {"island:Corse"}
    assert by["BSL"][2] == "FR"                         # Basel-Mulhouse lies on French soil
    assert all(d["code"].startswith("AIR:") for d in fa.destinations())
    assert {c for c, _ in fa.BORDER_CHECKS} <= {"74010", "57463", "67482", "64024", "66136", "59350"} | {c for c, _ in fa.BORDER_CHECKS}


# --- hospitals --------------------------------------------------------------

def test_lambert93_origin_and_a_known_place():
    import hospitals_fr as hf
    lat, lng = hf.lambert93_to_wgs84(700000, 6600000)          # projection origin
    assert abs(lat - 46.5) < 1e-6 and abs(lng - 3.0) < 1e-6
    lat, lng = hf.lambert93_to_wgs84(652470, 6862036)           # central Paris
    assert abs(lat - 48.853) < 0.01 and abs(lng - 2.349) < 0.01


FINESS = "\n".join([
    "finess;etalab;98;2026-05-12",
    "structureet;010000024;010780054;CH DE FLEYRIAT;CENTRE HOSPITALIER;;;900;RTE;DE PARIS;;;451;01;AIN;01440 VIRIAT;;;355;Centre Hospitalier (C.H.);1102;CH;;8610Z;03;x;1;Etablissement public de santé;1979-02-13;1979-02-13;2020-02-04;",
    "structureet;690781810;690000000;HOPITAL EDOUARD HERRIOT;HCL;;;5;PL;D'ARSONVAL;;;383;69;RHONE;69003 LYON;;;101;Centre Hospitalier Régional (C.H.R.);1101;CHR;;8610Z;03;x;1;Etablissement public de santé;1979-02-13;1979-02-13;2020-02-04;",
    "structureet;130000001;130000000;CLINIQUE PRIVEE;;;;1;RUE;X;;;055;13;BDR;13000 MARSEILLE;;;365;Pluridisciplinaire;1102;x;;8610Z;03;x;0;Non concerné;1979-02-13;1979-02-13;2020-02-04;",
    "structureet;2A0000011;2A0000010;CH AJACCIO;;;;1;RUE;X;;;004;2A;CORSE-DU-SUD;20000 AJACCIO;;;355;CH;1102;x;;8610Z;03;x;1;Etablissement public de santé;1979-02-13;1979-02-13;2020-02-04;",
    "structureet;750000099;750000000;CH SANS URGENCES;;;;1;RUE;X;;;056;75;PARIS;75000 PARIS;;;355;CH;1102;x;;8610Z;03;x;1;Etablissement public de santé;1979-02-13;1979-02-13;2020-02-04;",
    "geolocalisation;010000024;870262.2;6571540.8;1,ATLASANTE,96,BAN,EPSG:2154 RGF93 / Lambert-93 (Métropole);2026-05-04",
    "geolocalisation;690781810;844000.0;6517000.0;1,ATLASANTE,96,BAN,EPSG:2154 RGF93 / Lambert-93 (Métropole);2026-05-04",
    "geolocalisation;130000001;893000.0;6247000.0;1,ATLASANTE,96,BAN,EPSG:2154 RGF93 / Lambert-93 (Métropole);2026-05-04",
    "geolocalisation;2A0000011;1180000.0;6108000.0;1,ATLASANTE,96,BAN,EPSG:2154 RGF93 / Lambert-93 (Métropole);2026-05-04",
    "geolocalisation;750000099;652470.0;6862036.0;1,ATLASANTE,96,BAN,EPSG:2154 RGF93 / Lambert-93 (Métropole);2026-05-04",
])
URG = "\n".join([
    "BOR;AN;FI;RS;FI_EJ;URG;REG;SAO;ACC;PASSU",
    "URGENCES2;2025;010000024;CH DE FLEYRIAT;010780054;GEN;2;1;1;45177",
    "URGENCES2;2025;690781810;HEH;690000000;GEN;2;1;1;90000",
    "URGENCES2;2025;690781810;HEH;690000000;PED;2;1;1;20000",
    "URGENCES2;2025;130000001;CLINIQUE;130000000;GEN;2;1;1;15000",
    "URGENCES2;2025;2A0000011;CH AJACCIO;2A0000010;GEN;2;1;1;30000",
])


def test_read_hospitals_fr(tmp_path):
    import hospitals_fr as hf
    f, u = tmp_path / "finess.csv", tmp_path / "urg.csv"
    f.write_text(FINESS, encoding="utf-8")
    u.write_text(URG, encoding="utf-8")
    hs = {h["codcnh"]: h for h in hf.read_hospitals_fr(f, u)}
    assert set(hs) == {"010000024", "690781810", "130000001", "2A0000011"}   # only sites with a general ER
    assert hs["690781810"]["tier"] == 1 and hs["010000024"]["tier"] == 2 and hs["130000001"]["tier"] == 3
    assert hs["2A0000011"]["muni"] == "2A004" and hs["010000024"]["muni"] == "01451"
    assert hs["130000001"]["public"] is False and hs["010000024"]["public"] is True
    assert 46.0 < hs["010000024"]["lat"] < 46.5 and 5.0 < hs["010000024"]["lng"] < 5.5   # Viriat


def test_per_destination_radius(monkeypatch, tmp_path):
    import compute_times as ct
    munis = [{"code": "A", "lat": 46.0, "lng": 3.0, "zone": "mainland"},
             {"code": "B", "lat": 47.8, "lng": 3.0, "zone": "mainland"}]          # ~200 km north of A
    near = {"code": "HOS:1", "lat": 46.0, "lng": 3.0, "zone": "mainland", "max_km": 150}
    far = dict(near, code="HOS:2", max_km=300)
    assert [m["code"] for m in ct.origins_for(near, munis)] == ["A"]
    assert [m["code"] for m in ct.origins_for(far, munis)] == ["A", "B"]


def test_arrondissements_map_to_their_commune():
    import hospitals_fr as hf
    assert hf.commune_of("13", "205") == "13055"    # Marseille 5e
    assert hf.commune_of("69", "383") == "69123"    # Lyon 3e
    assert hf.commune_of("75", "112") == "75056"    # Paris 12e
    assert hf.commune_of("2A", "004") == "2A004" and hf.commune_of("01", "451") == "01451"


def test_hospital_commune_is_where_it_stands():
    import place_hospitals as ph
    h = {"muni": "06083", "lat": 43.76, "lng": 7.47}
    assert ph.settle_muni(h, lambda lng, lat: "06104") == "06104"     # Menton's hospital stands in Roquebrune
    assert ph.settle_muni(h, lambda lng, lat: None) == "06083"        # point off the map: keep the register's


def test_france_hospital_radius_by_tier():
    import compute_hospitals as chos
    from common import load_json
    places = {"municipalities": [{"code": "48095", "lat": 44.5, "lng": 3.5, "zone": "mainland"}]}
    placed = [{"codcnh": "1", "name": "CHU", "muni": "48095", "lat": 44.5, "lng": 3.5, "tier": 1},
              {"codcnh": "2", "name": "CH", "muni": "48095", "lat": 44.5, "lng": 3.5, "tier": 2}]
    try:
        chos.configure("fr")
        d = {x["codcnh"]: x for x in chos.destinations(placed, places)}
        assert d["1"]["max_km"] == 300 and d["2"]["max_km"] == 150
    finally:
        chos.configure("es")
    assert "max_km" not in chos.destinations(placed, places)[0]          # Spain unchanged
