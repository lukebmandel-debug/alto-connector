"""City engine v2, free mode (design section 6): where the streets form no grid (London, Rome, central Paris, a free
domain inside a grid city) graph paper is abandoned for smoothed real geometry.

- `select(m, region)`: the streets that are drawn: class k <= 3, named k = 4 streets whose name runs at least 300 m in
  the region, and every street a landmark or station fronts.
- the mapping is a similarity transform (scale sigma, rotation, translation): `fit_similarity(src, dst)` fits it by
  least squares to anchors (the seam nodes shared with neighbouring grid domains); a whole-free city uses
  `auto_sigma()` (the page's blocks about as big as graph paper's) and no rotation.
- each street: DP at 12 page px, then Chaikin x2 (`smooth`); an end within 25 px of another street is snapped onto it
  and the meeting point is added to that street too, so the Directions graph (palace_place.graph) joins them
  (`snap_ends`).
- joining grid domains (`clip_out`, `join`): free streets never enter a grid domain's page region; one that reaches
  the region's edge ends on the nearest boundary node within 0.6 block.
- blocks: the faces of the drawn street network, found as in palace_place (raster flood fill); lots come from
  palace_place.lots() (largest inscribed rectangle turned to the block's own street angle, up to 4 pieces,
  [cx, cy, w, h, deg]); the page tiles are the faces' outlines as polygons (`M.tq`, flat [x0, y0, x1, y1, ...]).
  Faces over 0.25 km2 (real) get no lots.

`build(m, ...)` runs all of it and returns a page map palace.py can draw ({W, H, streets, water, parks, landmarks,
stations, tq, blocks, free: {T, sigma}}). Pure; no network.
"""
from __future__ import annotations

import math

from .palace_grid import CW, CH, PAD, norm, _dp, _chaikin, _inside
from .city_avenues import _pairs, _flat, plen, segd

DP_PX = 12.0
SNAP_PX = 25.0
K4_MIN = 300.0          # real m
FRONT_PX = 40.0         # a street this close to a landmark/station is the street it fronts (real px)
BIG_FACE = 0.25e6       # real m2: a face this big (a park, a yard) gets no lots
TQ_CELL = 6             # raster cell for the faces' outlines (page px)


# ── which streets ──────────────────────────────────────────────────────────
def select(m, region=None, k_max=3, k4_min=K4_MIN, front_px=FRONT_PX):
    """-> the real streets (dicts of m["streets"]) free mode draws in `region` (a real ring, or None: everywhere)."""
    sc = m.get("scale") or 1.0

    def inside(p):
        return region is None or _inside(p, [region])
    pts_of = []
    for st in m.get("streets", []):
        if st.get("t"):
            continue
        P = [p for p in _pairs(st["p"]) if inside(p)]
        if len(P) >= 2:
            pts_of.append((st, P))
    k4len = {}
    for st, P in pts_of:
        if st.get("k", 9) == 4 and st.get("n"):
            k4len[norm(st["n"])] = k4len.get(norm(st["n"]), 0.0) + plen(P)
    poi = [(l["x"], l["y"]) for l in m.get("landmarks", [])] + [(s["x"], s["y"]) for s in m.get("stations", [])]
    poi += [(s["x"], s["y"]) for s in (m.get("transit") or {}).get("stops", [])]
    out = []
    for st, P in pts_of:
        k = st.get("k", 9)
        keep = k <= k_max or (k == 4 and st.get("n") and k4len.get(norm(st["n"]), 0) >= k4_min * sc)
        if not keep and k <= 5 and poi:
            keep = any(min(segd(q, a, b) for a, b in zip(P, P[1:])) <= front_px * sc for q in poi
                       if abs(q[0] - P[0][0]) < 3000 and abs(q[1] - P[0][1]) < 3000)
        if keep:
            out.append(st)
    return out


# ── the similarity transform ───────────────────────────────────────────────
def fit_similarity(src, dst, rotate=True):
    """Least-squares similarity src -> dst: (s, a (rad), tx, ty). With rotate=False the angle is 0."""
    n = len(src)
    if n == 0:
        return (1.0, 0.0, 0.0, 0.0)
    sx = sum(p[0] for p in src) / n; sy = sum(p[1] for p in src) / n
    dx = sum(p[0] for p in dst) / n; dy = sum(p[1] for p in dst) / n
    if n == 1:
        return (1.0, 0.0, dx - sx, dy - sy)
    a_ = b_ = q = 0.0
    for (x, y), (u, v) in zip(src, dst):
        x, y, u, v = x - sx, y - sy, u - dx, v - dy
        a_ += x * u + y * v
        b_ += x * v - y * u
        q += x * x + y * y
    if q < 1e-9:
        return (1.0, 0.0, dx - sx, dy - sy)
    if rotate:
        ang = math.atan2(b_, a_)
        s = math.hypot(a_, b_) / q
    else:
        ang, s = 0.0, a_ / q
    c, si = math.cos(ang), math.sin(ang)
    return (s, ang, dx - s * (c * sx - si * sy), dy - s * (si * sx + c * sy))


def sim(T, p):
    s, a, tx, ty = T
    c, si = math.cos(a), math.sin(a)
    return (s * (c * p[0] - si * p[1]) + tx, s * (si * p[0] + c * p[1]) + ty)


def auto_sigma(m, streets, region=None, lo=1.0, hi=3.5):
    """Page px per real px so that the drawn network's mean spacing becomes one graph-paper block: a lattice of
    spacing a has 2/a of street per unit area, so a = 2 * area / length."""
    L = sum(plen(_pairs(s["p"])) for s in streets) or 1.0
    if region:
        A = abs(sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(region, region[1:] + region[:1]))) / 2
    else:
        A = m["W"] * m["H"]
    a = 2 * A / L
    return max(lo, min(hi, math.sqrt(CW * CH) / max(1.0, a)))


# ── drawing the streets ────────────────────────────────────────────────────
def smooth(pts, dp=DP_PX, n=2):
    if len(pts) < 3:
        return list(pts)
    return _chaikin(_dp(list(pts), dp), n)


def _nearest_on(p, P):
    best = (1e18, None, None)
    for i, (a, b) in enumerate(zip(P, P[1:])):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy or 1e-12
        t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
        q = (a[0] + t * dx, a[1] + t * dy)
        d = math.dist(p, q)
        if d < best[0]:
            best = (d, q, i)
    return best


def snap_ends(polys, tol=SNAP_PX):
    """An end within tol of another street (and not already on it) moves onto it; the meeting point is inserted
    into that street so the two share a vertex (a T-join the page rounds and the graph routes through)."""
    B = 200
    buckets = {}
    for pi, P in enumerate(polys):
        for x, y in P[::max(1, len(P) // 50)] + [P[-1]]:
            buckets.setdefault((int(x // B), int(y // B)), set()).add(pi)
    inserts = {}
    for pi, P in enumerate(polys):
        for e in (0, -1):
            p = P[e]
            cands = set()
            for bx in range(int(p[0] // B) - 2, int(p[0] // B) + 3):
                for by in range(int(p[1] // B) - 2, int(p[1] // B) + 3):
                    cands |= buckets.get((bx, by), set())
            best = (tol + 1e-9, None, None, None)
            for qi in cands:
                if qi == pi:
                    continue
                d, q, si = _nearest_on(p, polys[qi])
                if d < best[0]:
                    best = (d, q, si, qi)
            d, q, si, qi = best
            if q is None or d < 0.05:
                continue
            P[e] = q
            inserts.setdefault(qi, []).append((si, q))
    for qi, ins in inserts.items():
        P = polys[qi]
        for si, q in sorted(ins, key=lambda t: (-t[0], -math.dist(P[t[0]], t[1]))):
            if min(math.dist(q, P[si]), math.dist(q, P[si + 1])) > .05:
                P.insert(si + 1, q)
    return polys


def _seg_ring(a, b, ring):
    """Parameters t in (0, 1) where segment ab crosses the ring."""
    ts = []
    n = len(ring)
    for i in range(n):
        c, d = ring[i], ring[(i + 1) % n]
        den = (b[0] - a[0]) * (d[1] - c[1]) - (b[1] - a[1]) * (d[0] - c[0])
        if abs(den) < 1e-12:
            continue
        t = ((c[0] - a[0]) * (d[1] - c[1]) - (c[1] - a[1]) * (d[0] - c[0])) / den
        u = ((c[0] - a[0]) * (b[1] - a[1]) - (c[1] - a[1]) * (b[0] - a[0])) / den
        if 0 < t < 1 and 0 <= u <= 1:
            ts.append(t)
    return sorted(ts)


def clip_out(polys, rings):
    """The parts of each polyline outside every ring (a grid domain's page region): [(poly index, pts)]."""
    out = []
    for pi, P in enumerate(polys):
        cur = []
        for a, b in zip(P, P[1:]):
            cuts = sorted({0.0, 1.0, *[t for r in rings for t in _seg_ring(a, b, r)]})
            for t0, t1 in zip(cuts, cuts[1:]):
                p0 = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
                p1 = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
                mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
                if any(_inside(mid, [r]) for r in rings):
                    if len(cur) >= 2:
                        out.append((pi, cur))
                    cur = []
                    continue
                if not cur:
                    cur = [p0]
                cur.append(p1)
        if len(cur) >= 2:
            out.append((pi, cur))
    return out


def join(pieces, rings, nodes, block=None):
    """A free street that ends on a grid region's edge ends on the nearest boundary node (a lattice line's end)
    within 0.6 block instead (a rounded join on the page)."""
    r = 0.6 * (block or (CW + CH) / 2)
    edges = [(rg[i], rg[(i + 1) % len(rg)]) for rg in rings for i in range(len(rg))]
    out = []
    for pi, P in pieces:
        P = list(P)
        for e in (0, -1):
            if edges and min(segd(P[e], a, b) for a, b in edges) <= 2.0 and nodes:
                q = min(nodes, key=lambda n: math.dist(n, P[e]))
                if math.dist(q, P[e]) <= r:
                    P[e] = tuple(q)
        out.append((pi, P))
    return out


# ── blocks: the faces of the drawn network ─────────────────────────────────
def faces(page, cell=TQ_CELL, min_area=None, max_area=None):
    """Outlines of the blocks (raster faces of the page streets/water/parks): [[(x, y), ...]] convex outlines,
    as flat lists for M.tq. Uses palace_place's raster at a coarser cell."""
    from .palace_place import _Grid, _blocks, STREET_HALF
    g = _Grid(page["W"], page["H"], cell)
    for s in page.get("streets", []):
        g.stroke(s["p"], STREET_HALF.get(s.get("k", 4), 4) + 4)
    if page.get("water"):
        g.fill(page["water"])
    out = []
    w = g.w
    for _lab, cells, edge in _blocks(page, g):
        A = len(cells) * cell * cell
        if edge or (min_area and A < min_area) or (max_area and A > max_area):
            continue
        pts = [((i % w + .5) * cell, (i // w + .5) * cell) for i in cells]
        hull = _hull(pts)
        if len(hull) >= 3:
            out.append(hull)
    return out


def _hull(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


# ── the whole free region ──────────────────────────────────────────────────
def build(m, region=None, T=None, sigma=None, rotate=0.0, grid_rings=(), boundary_nodes=(), with_lots=True,
          pad=PAD):
    """Free mode for a region (real ring) or the whole map. T: a similarity (s, a, tx, ty) fitted to seam anchors
    (fit_similarity); else sigma (auto_sigma) and `rotate` (rad, the root's page rotation) with the region's corner
    at (pad, pad). grid_rings: page regions of grid domains the free streets must stay out of; boundary_nodes:
    their lattice line ends on those edges. -> page map dict."""
    sts = select(m, region)
    if T is None:
        s = sigma or auto_sigma(m, sts, region)
        ring = region or [(0, 0), (m["W"], 0), (m["W"], m["H"]), (0, m["H"])]
        c, si = math.cos(rotate), math.sin(rotate)
        R = [(s * (c * x - si * y), s * (si * x + c * y)) for x, y in ring]
        T = (s, rotate, pad - min(p[0] for p in R), pad - min(p[1] for p in R))
    polys, meta = [], []
    for st in sts:
        P = [sim(T, p) for p in _pairs(st["p"]) if region is None or _inside(p, [region])]
        if len(P) < 2:
            continue
        P = smooth(P)
        if plen(P) < 8:
            continue
        polys.append(P); meta.append(st)
    snap_ends(polys)
    pieces = [(i, P) for i, P in enumerate(polys)]
    if grid_rings:
        pieces = join(clip_out(polys, list(grid_rings)), list(grid_rings), list(boundary_nodes))
    streets = []
    for i, P in pieces:
        st = meta[i]
        streets.append({"n": st.get("n") or "", "k": st.get("k", 4), "p": _flat(P)})
    xs = [v for s in streets for v in s["p"][0::2]] or [0]
    ys = [v for s in streets for v in s["p"][1::2]] or [0]
    W, H = int(max(xs) + pad), int(max(ys) + pad)

    def ring_page(r):
        return [round(v, 1) for x, y in _pairs(r) for v in sim(T, (x, y))]
    inside_r = (lambda p: True) if region is None else (lambda p: _inside(p, [region]))
    water = [ring_page(r) for r in m.get("water", []) if any(inside_r(q) for q in _pairs(r))]
    parks = [{"n": p.get("n", ""), "r": [ring_page(r) for r in p["r"]]} for p in m.get("parks", [])
             if any(inside_r(q) for r in p["r"] for q in _pairs(r))]
    lms = []
    for l in m.get("landmarks", []):
        if inside_r((l["x"], l["y"])):
            x, y = sim(T, (l["x"], l["y"]))
            lms.append({"n": l["n"], "x": round(x, 1), "y": round(y, 1), "r": [ring_page(r) for r in l.get("r") or []]})
    stations = []
    for s in m.get("stations", []):
        if inside_r((s["x"], s["y"])):
            x, y = sim(T, (s["x"], s["y"]))
            stations.append(dict(s, x=round(x, 1), y=round(y, 1)))
    page = {"W": W, "H": H, "streets": streets, "water": water, "parks": parks, "landmarks": lms,
            "stations": stations, "free": {"T": [round(v, 6) for v in T], "sigma": round(T[0], 4)}}
    big = BIG_FACE * T[0] * T[0] / ((m.get("scale") or 1.0) ** 2)
    tq = faces(page, max_area=big)
    page["tq"] = [[round(v, 1) for q in h for v in q] for h in tq]
    if with_lots:
        from .palace_place import lots
        bl = lots({"W": W, "H": H, "streets": streets, "water": water, "parks": parks,
                   "landmarks": [l for l in lms if l["r"]]})
        huge = faces(page, min_area=big)          # parks, yards: no buildings
        page["blocks"] = [b for b in bl if not any(_inside((b["x"], b["y"]), [h]) for h in huge)]
    return page
