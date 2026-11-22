"""Municipality polygons from the site's TopoJSON, and point-in-municipality lookup.

No GIS dependency: the TopoJSON is decoded here (quantized, delta-encoded
arcs; negative indices are reversed arcs) and points are tested with
even-odd ray casting over all rings, so holes are excluded.
"""

import math

import common
from common import load_json


def _decode_arcs(topo):
    t = topo.get("transform")
    arcs = []
    for arc in topo["arcs"]:
        if t:
            (sx, sy), (tx, ty) = t["scale"], t["translate"]
            x = y = 0
            pts = []
            for dx, dy in arc:
                x += dx
                y += dy
                pts.append((x * sx + tx, y * sy + ty))
        else:
            pts = [(p[0], p[1]) for p in arc]
        arcs.append(pts)
    return arcs


def _ring(arcs, indices):
    pts = []
    for i in indices:
        a = arcs[i] if i >= 0 else arcs[~i][::-1]
        # consecutive arcs share their joining point
        pts.extend(a if not pts else a[1:])
    return pts


def load_municipalities(path=None, layer="municipalities"):
    """code -> polygons -> rings of (lng, lat); first ring outer, the rest holes."""
    topo = load_json(path or common.TOPO_FILE)
    arcs = _decode_arcs(topo)
    out = {}
    for g in topo["objects"][layer]["geometries"]:
        if g["type"] == "Polygon":
            polys = [g["arcs"]]
        elif g["type"] == "MultiPolygon":
            polys = g["arcs"]
        else:
            continue
        out[str(g["id"])] = [[_ring(arcs, r) for r in poly] for poly in polys]
    return out


def _inside(rings, x, y):
    """Even-odd rule over all rings of one polygon (holes flip it back out)."""
    inside = False
    for ring in rings:
        n = len(ring)
        j = n - 1
        for i in range(n):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                inside = not inside
            j = i
    return inside


class MuniIndex:
    """Grid of 0.1-degree cells listing the polygons whose bbox touches each cell."""

    CELL = 0.1

    def __init__(self, polys):
        self.items = []
        self.grid = {}
        for code, plist in polys.items():
            for rings in plist:
                xs = [p[0] for p in rings[0]]
                ys = [p[1] for p in rings[0]]
                bbox = (min(xs), min(ys), max(xs), max(ys))
                k = len(self.items)
                self.items.append((code, bbox, rings))
                for cx in range(self._c(bbox[0]), self._c(bbox[2]) + 1):
                    for cy in range(self._c(bbox[1]), self._c(bbox[3]) + 1):
                        self.grid.setdefault((cx, cy), []).append(k)

    def _c(self, v):
        return math.floor(v / self.CELL)

    def locate(self, lng, lat):
        for k in self.grid.get((self._c(lng), self._c(lat)), ()):
            code, (x0, y0, x1, y1), rings = self.items[k]
            if x0 <= lng <= x1 and y0 <= lat <= y1 and _inside(rings, lng, lat):
                return code
        return None
