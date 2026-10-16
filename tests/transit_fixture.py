"""Fixtures for the transit tests of the city engine v2: a stub of E2's Lattice (design 8.2: page(), local(), node()),
the Philadelphia snap inputs of v1.9.78 (tests/fixtures/transit/philly_snap_args.json.gz: the real lines and stops, the
grid's mapping tables, the drawn upright streets), and a two-domain Philadelphia made from them by hand: the square
lattice everywhere but West/Southwest Philadelphia, where a lattice turned by `deg` degrees replaces it."""
import gzip
import json
import math
from pathlib import Path

from alto.build.city_types import Domain
from alto.build.palace_grid import CW, CH, mapping_from

HERE = Path(__file__).resolve().parent
PHILLY = HERE / "fixtures" / "transit" / "philly_snap_args.json.gz"          # the 1.9.78 build (its 40-degree box)
SQUARE = HERE / "fixtures" / "transit" / "philly_square_args.json.gz"        # the same build with no tilted district


class Lat:
    """Stub of city_lattice.Lattice: a rigid page transform T_d (rotate by `a` degrees, then shift by `o`)."""

    def __init__(self, dom, xg, yg, cw=CW, ch=CH, a=0.0, o=(0.0, 0.0)):
        self.dom, self.xg, self.yg, self.cw, self.ch = dom, list(xg), list(yg), cw, ch
        self.c, self.s, self.o = math.cos(math.radians(a)), math.sin(math.radians(a)), o

    def page(self, lx, ly):
        return (self.o[0] + lx * self.c - ly * self.s, self.o[1] + lx * self.s + ly * self.c)

    def local(self, x, y):
        dx, dy = x - self.o[0], y - self.o[1]
        return (dx * self.c + dy * self.s, -dx * self.s + dy * self.c)

    def node(self, i, j):
        return self.page(self.xg[i], self.yg[j])


def philly_args(square=False):
    return json.loads(gzip.open(SQUARE if square else PHILLY, "rt").read())


def _inv(mp, gx, gy):
    """Page px -> real px for a palace_grid.Mapping (its inverse: piecewise linear back, then turn back)."""
    tx = mp._interp(gx, mp.xg, mp.xr, (mp.xr[1] - mp.xr[0]) if len(mp.xr) > 1 else 1)
    ty = mp._interp(gy, mp.yg, mp.yr, (mp.yr[1] - mp.yr[0]) if len(mp.yr) > 1 else 1)
    c, s = math.cos(mp.th), math.sin(mp.th)
    x, y = tx - mp.cx, ty - mp.cy
    return (x * c - y * s + mp.cx, x * s + y * c + mp.cy)


def _clip(p, q, box):
    x0, y0, x1, y1 = box
    t0, t1 = 0.0, 1.0
    dx, dy = q[0] - p[0], q[1] - p[1]
    for pp, qq in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if abs(pp) < 1e-9:
            if qq < 0:
                return None
            continue
        t = qq / pp
        if pp < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return None
    return ((p[0] + t0 * dx, p[1] + t0 * dy), (p[0] + t1 * dx, p[1] + t1 * dy))


def _outside(a, b, box):
    """The pieces of segment a-b outside the box."""
    sg = _clip(a, b, box)
    if sg is None:
        return [(a, b)]
    out = []
    if math.hypot(sg[0][0] - a[0], sg[0][1] - a[1]) > 1e-6:
        out.append((a, sg[0]))
    if math.hypot(sg[1][0] - b[0], sg[1][1] - b[1]) > 1e-6:
        out.append((sg[1], b))
    return out


def philly_two_domains(deg=38.0, A=None, east=3000.0):
    """-> (A, doms [(Domain, Lat)], segs, te, streets, box). Domain 1 is the page box of 1.9.78's tilted district
    (x from the grid's left edge to the column right of real x=3000, y from the row above real y=6000 to the bottom),
    its lattice turned `deg` degrees about the box centre; its lattice lines, clipped to the box, are its streets (te).
    Made from the square-only build: its upright streets inside the box are left out and its diagonal avenues are cut
    at the box (the turned lattice carries them inside)."""
    A = A or philly_args(square=True)
    mp = mapping_from(A["grid"])
    xg, yg = A["xg"], A["yg"]
    ix, jy = mp(east, 6000)[0], mp(1, 6000)[1]
    iE = next((i for i, x in enumerate(xg) if x >= ix), len(xg) - 1)
    jT = max((j for j, y in enumerate(yg) if y <= jy), default=0)
    box = (xg[0], yg[jT], xg[iE], yg[-1])
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    R = math.hypot(box[2] - box[0], box[3] - box[1]) / 2 + max(CW, CH)
    n, m = int(R // CW) + 1, int(R // CH) + 1
    root = Domain(id=0, kind="grid", theta=0.0, poly=[(-1e6, -1e6), (1e6, -1e6), (1e6, 1e6), (-1e6, 1e6)], mapping=mp)
    lat0 = Lat(root, xg, yg)
    clip = [(box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])]
    ring = []
    for (ax, ay), (bx, by) in zip(clip, clip[1:] + clip[:1]):
        k = max(1, int(math.hypot(bx - ax, by - ay) // 100))
        ring += [_inv(mp, ax + (bx - ax) * t / k, ay + (by - ay) * t / k) for t in range(k)]
    lat1 = Lat(None, [k * CW for k in range(-n, n + 1)], [k * CH for k in range(-m, m + 1)], a=deg, o=(cx, cy))
    # the turned domain's own mapping: real -> its local frame, turned by the real lattice angle (the main grid's plus
    # deg) and scaled evenly (the page scale at the box centre), so the real turned streets lie along its lattice
    rcx, rcy = _inv(mp, cx, cy)
    (ax, ay), (bx, by), (qx, qy) = mp(rcx, rcy), mp(rcx + 10, rcy), mp(rcx, rcy + 10)
    sc = math.sqrt(abs((bx - ax) * (qy - ay) - (by - ay) * (qx - ax))) / 10
    th1 = mp.th + math.radians(deg)
    c1, s1 = math.cos(-th1), math.sin(-th1)

    def mapping1(x, y):
        dx, dy = x - rcx, y - rcy
        return (sc * (dx * c1 - dy * s1), sc * (dx * s1 + dy * c1))
    d1 = Domain(id=1, kind="grid", theta=th1, poly=ring, a=deg, o=(cx, cy), clip=clip, mapping=mapping1)
    lat1.dom = d1
    te = []
    for lx in lat1.xg:
        sg = _clip(lat1.page(lx, -R), lat1.page(lx, R), box)
        if sg and math.hypot(sg[1][0] - sg[0][0], sg[1][1] - sg[0][1]) > 30:
            te.append([sg[0][0], sg[0][1], sg[1][0], sg[1][1]])
    for ly in lat1.yg:
        sg = _clip(lat1.page(-R, ly), lat1.page(R, ly), box)
        if sg and math.hypot(sg[1][0] - sg[0][0], sg[1][1] - sg[0][1]) > 30:
            te.append([sg[0][0], sg[0][1], sg[1][0], sg[1][1]])

    def inside(x, y):
        return box[0] + 1 < x < box[2] - 1 and box[1] + 1 < y < box[3] - 1
    edges = [e for e in A["edges"] if not inside((e[0] + e[2]) / 2, (e[1] + e[3]) / 2)]
    streets = []
    for s in A["streets"]:
        if not s.get("d"):
            streets.append(s)
            continue
        P = list(zip(s["p"][0::2], s["p"][1::2]))
        cur = []
        for a, b in zip(P, P[1:]):                       # the parts of the avenue outside the box
            out = []
            for piece in _outside(a, b, box):
                out.append(piece)
            for q0, q1 in out:
                if cur and math.hypot(cur[-1][0] - q0[0], cur[-1][1] - q0[1]) < 1e-6:
                    cur.append(q1)
                else:
                    if len(cur) > 1:
                        streets.append(dict(s, j=[0, 0], p=[round(v, 1) for q in cur for v in q]))
                    cur = [q0, q1]
        if len(cur) > 1:
            streets.append(dict(s, j=[0, 0], p=[round(v, 1) for q in cur for v in q]))
    # the seam is a drawn line (its avenue): the box's top and right edges; the lines of both domains end on it
    streets = streets + [{"n": "", "k": 1, "sm": 1, "p": [box[0], box[1], box[2], box[1], box[2], box[3]]}]
    from alto.build.palace_transit_route import drawn_segs
    segs = drawn_segs(edges=edges, te=te, streets=streets)
    return A, [(root, lat0), (d1, lat1)], segs, te, edges, streets, box
