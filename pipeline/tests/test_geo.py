import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geo  # noqa: E402
from common import PLACES_FILE, load_json  # noqa: E402

# Two unit squares side by side, sharing arc 0 (x=1 edge), quantized with a transform.
# Square A: (0,0)-(1,1); square B: (1,0)-(2,1). Arc 0 goes (1,0)->(1,1); B uses it reversed (~0 = -1).
FIXTURE = {
    "type": "Topology",
    "transform": {"scale": [0.5, 0.5], "translate": [10.0, 20.0]},
    "objects": {"municipalities": {"type": "GeometryCollection", "geometries": [
        {"type": "Polygon", "id": "A", "arcs": [[0, 1]]},
        {"type": "Polygon", "id": "B", "arcs": [[-1, 2]]},
    ]}},
    # quantized + delta-encoded: units of 0.5 degrees
    "arcs": [
        [[2, 0], [0, 2]],                    # (11,20) -> (11,21)
        [[2, 2], [-2, 0], [0, -2], [2, 0]],  # (11,21) -> (10,21) -> (10,20) -> (11,20)
        [[2, 0], [2, 0], [0, 2], [-2, 0]],   # (11,20) -> (12,20) -> (12,21) -> (11,21)
    ],
}

HOLE = {
    "type": "Topology",
    "objects": {"municipalities": {"type": "GeometryCollection", "geometries": [
        {"type": "Polygon", "id": "R", "arcs": [[0], [1]]},
    ]}},
    "arcs": [
        [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
        [[4, 4], [4, 6], [6, 6], [6, 4], [4, 4]],
    ],
}


def test_decodes_quantized_topology(tmp_path):
    p = tmp_path / "t.json"
    import json
    p.write_text(json.dumps(FIXTURE))
    idx = geo.MuniIndex(geo.load_municipalities(p))
    assert idx.locate(10.5, 20.5) == "A"
    assert idx.locate(11.5, 20.5) == "B"
    assert idx.locate(12.5, 20.5) is None
    assert idx.locate(10.5, 21.5) is None


def test_hole_is_excluded(tmp_path):
    import json
    p = tmp_path / "h.json"
    p.write_text(json.dumps(HOLE))
    idx = geo.MuniIndex(geo.load_municipalities(p))
    assert idx.locate(2, 2) == "R"
    assert idx.locate(5, 5) is None


def code_of(name):
    return next(m["code"] for m in load_json(PLACES_FILE)["municipalities"] if m["name"] == name)


def test_real_boundaries():
    idx = geo.MuniIndex(geo.load_municipalities())
    assert idx.locate(-3.7038, 40.4168) == "28079"      # Puerta del Sol
    assert idx.locate(2.6502, 39.5696) == "07040"       # Palma
    assert idx.locate(-16.2546, 28.4636) == "38038"     # Santa Cruz de Tenerife
    assert idx.locate(-9.139, 38.722) is None           # Lisbon
    assert idx.locate(1.5218, 42.5063) is None          # Andorra la Vella
    assert idx.locate(0.0, 39.0) is None                # at sea
    assert idx.locate(-5.8, 35.77) is None              # Tanger
    assert idx.locate(1.9806, 42.4635) == code_of("Llívia")
    assert idx.locate(-2.7495, 42.7346) == code_of("Condado de Treviño")
