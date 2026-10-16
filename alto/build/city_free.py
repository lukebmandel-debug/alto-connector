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


# ── a free domain inside a grid city (city_engine step 13) ─────────────────
IDW_EPS = 30.0          # page px: the residual field is exact at the anchors, smooth between them
ANCHOR_MAX = 80
FREE_STUB = 0.5         # blocks: a dangling free piece shorter than this is dropped (clutter, not a street)
JOIN_FAR = 1.6         # blocks: a street that really runs on past the free edge reaches this far for a grid node
DUAL_PX = 40.0          # page px: two same-named carriageways this close are one street
FRONT_MAX = 110.0       # page px: a free lot farther than this from every drawn street stands in an open field: none
PARK_MIN = 20000.0      # real m2: a free park smaller than this is not drawn (unless the brief names it)


class FreeMap:
    """Real px -> page px for a free domain: the similarity T fitted to the anchors (real points on the free domain's
    edge -> where the neighbouring grid domain draws them) plus an inverse-distance blend of the anchors' residuals,
    so the free streets meet the grid's drawn lines at the edge exactly and are a pure similarity far from it."""

    def __init__(self, src, dst, rotate=True):
        if len(src) > ANCHOR_MAX:
            k = len(src) / ANCHOR_MAX
            idx = sorted({int(i * k) for i in range(ANCHOR_MAX)})
            src, dst = [src[i] for i in idx], [dst[i] for i in idx]
        self.T = fit_similarity(src, dst, rotate=rotate)
        self.src = list(src)
        self.res = [(q[0] - sim(self.T, p)[0], q[1] - sim(self.T, p)[1]) for p, q in zip(src, dst)]
        self.rms = math.sqrt(sum(a * a + b * b for a, b in self.res) / max(1, len(self.res)))
        self.shift = (0.0, 0.0)
        self._c = {}

    def residual(self, p):
        key = (int(p[0] // 15), int(p[1] // 15))
        r = self._c.get(key)
        if r is None:
            e2 = (IDW_EPS / max(1e-6, self.T[0])) ** 2
            sw = sx = sy = 0.0
            for (x, y), (rx, ry) in zip(self.src, self.res):
                w = 1.0 / ((p[0] - x) ** 2 + (p[1] - y) ** 2 + e2)
                sw += w; sx += w * rx; sy += w * ry
            r = (sx / sw, sy / sw) if sw else (0.0, 0.0)
            self._c[key] = r
        return r

    def __call__(self, x, y=None):
        p = (x, y) if y is not None else x
        q = sim(self.T, p)
        r = self.residual(p)
        return (q[0] + r[0] + self.shift[0], q[1] + r[1] + self.shift[1])

    def inverse(self, X, Y):
        s, a, tx, ty = self.T
        c, si = math.cos(-a), math.sin(-a)
        p = (0.0, 0.0)
        for _ in range(4):
            r = self.residual(p) if _ else (0.0, 0.0)
            u, v = X - self.shift[0] - r[0] - tx, Y - self.shift[1] - r[1] - ty
            p = ((c * u - si * v) / s, (si * u + c * v) / s)
        return p

    def tables(self):
        """The similarity alone as Mapping tables + page angle + origin (palace_place.page_of / city_report read
        them): local = s * real, page = R(a) local + (tx, ty)."""
        s, a, tx, ty = self.T
        big = 1e6
        return ({"t": 0.0, "cx": 0.0, "cy": 0.0, "xr": [-big, big], "xg": [-big * s, big * s],
                 "yr": [-big, big], "yg": [-big * s, big * s]},
                math.degrees(a), (tx + self.shift[0], ty + self.shift[1]))


def _runs_in(P, region):
    """Runs of consecutive vertices inside region, each carried one vertex past both ends (to meet the grid)."""
    ins = [_inside(p, [region]) for p in P]
    out, i, n = [], 0, len(P)
    while i < n:
        if not ins[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and ins[j + 1]:
            j += 1
        out.append((P[max(0, i - 1):min(n, j + 2)], i > 0, j < n - 1))
        i = j + 1
    return out


def _dense(P, step):
    out = [P[0]]
    for a, b in zip(P, P[1:]):
        n = max(1, int(math.dist(a, b) // step))
        out += [(a[0] + (b[0] - a[0]) * t / n, a[1] + (b[1] - a[1]) * t / n) for t in range(1, n + 1)]
    return out


def streets_in(m, region, fm, bad, nodes, blk, majors=(), step=8.0):
    """The free domain's streets on the page: real streets of `region` (select), mapped by fm, smoothed, cut where
    `bad(p)` (inside a grid domain's drawn blocks, the river, off the page), ends that stop at the grid's edge joined
    to the nearest drawn lattice node within 0.7 block, T-joins snapped (shared vertices). -> [street dicts] with
    fr = 1; heavy (L) when k <= 1 and named, or a major."""
    sts = select(m, region)
    polys, meta = [], []
    for st in sts:
        for P, ext0, ext1 in _runs_in(_pairs(st["p"]), region):
            Q = [fm(*p) for p in P]
            if len(Q) < 2:
                continue
            Q = smooth(Q)
            D = _dense(Q, step)
            flags = [bad(p) for p in D]
            cur, cut0 = [], 2 if ext0 else False      # 2: the real street runs on past the free domain's edge
            for k, (p, f) in enumerate(zip(D, flags)):
                if f:
                    if len(cur) >= 2:
                        polys.append(cur); meta.append((st, cut0, True))
                    cur, cut0 = [], True
                    continue
                cur.append(p)
            if len(cur) >= 2:
                polys.append(cur); meta.append((st, cut0, 2 if ext1 else False))
    # ends at the grid's edge -> the nearest drawn node (a lattice line's end): one street
    B = 300.0
    nb = {}
    for q in nodes:
        nb.setdefault((int(q[0] // B), int(q[1] // B)), []).append(q)

    def nearest(p, r):
        best = None
        for i in range(int(p[0] // B) - 1, int(p[0] // B) + 2):
            for j in range(int(p[1] // B) - 1, int(p[1] // B) + 2):
                for q in nb.get((i, j), ()):
                    d = math.dist(p, q)
                    if d <= r and (best is None or d < best[0]):
                        best = (d, q)
        return best[1] if best else None
    out_p, out_m, joined = [], [], []
    for P, (st, c0, c1) in zip(polys, meta):
        P = _dp(P, 1.5)
        j = [0, 0]
        for e, cut in ((0, c0), (1, c1)):
            if not cut:
                continue
            p = P[0] if e == 0 else P[-1]
            q = nearest(p, (0.7 if cut is True else JOIN_FAR) * blk)
            if q is not None:
                if e == 0:
                    P = [tuple(q)] + P
                else:
                    P = P + [tuple(q)]
                j[e] = 1
        out_p.append([tuple(p) for p in P]); out_m.append(st); joined.append(j)
    # a dual carriageway is one street: a piece running beside a longer one of the same name is dropped
    order = sorted(range(len(out_p)), key=lambda i: -plen(out_p[i]))
    kept, idx = [], {}
    for i in order:
        n = norm(out_m[i].get("n") or "")
        P = out_p[i]
        if n and n in idx:
            S = _dense(P, 20.0)
            near = sum(1 for q in S if any(min(segd(q, a, b) for a, b in zip(Q, Q[1:])) < DUAL_PX for Q in idx[n]))
            if near >= 0.7 * len(S):
                continue
        kept.append(i)
        if n:
            idx.setdefault(n, []).append(P)
    kept.sort()
    out_p = [out_p[i] for i in kept]; out_m = [out_m[i] for i in kept]; joined = [joined[i] for i in kept]
    snap_ends(out_p)
    maj = {norm(x) for x in majors}
    res = []
    for P, st, j in zip(out_p, out_m, joined):
        L = plen(P)
        if L < 12 or (L < FREE_STUB * blk and not any(j)):
            continue
        n = norm(st.get("n") or "")
        rec = {"n": n, "k": st.get("k", 4), "fr": 1, "p": [round(v, 1) for q in P for v in q]}
        if n and (st.get("k", 9) <= 1 or n in maj):
            rec["L"] = 1
        res.append(rec)
    return res


def parks_in(m, region, fm, names=(), min_area=PARK_MIN):
    """Parks whose outline stands mostly in the free domain, mapped and smoothed: page park records ("pg": 1, so
    palace_parks.shape draws them as they are)."""
    from .palace_parks import short_name
    sc = m.get("scale") or 1.0
    want = {x.lower() for x in names}
    out = []
    for pk in m.get("parks", []):
        rings = [_pairs(r) for r in pk.get("r") or [] if r and len(r) >= 6]
        if not rings:
            continue
        R = max(rings, key=lambda r: abs(_area(r)))
        A = abs(_area(R)) / (sc * sc)
        n = pk.get("n") or ""
        if A < min_area and n.lower() not in want:
            continue
        if not n:
            continue
        cx, cy = sum(p[0] for p in R) / len(R), sum(p[1] for p in R) / len(R)
        if sum(_inside(p, [region]) for p in R) < 0.6 * len(R) or not _inside((cx, cy), [region]):
            continue
        Q = [fm(*p) for p in R]
        Q = _dp(Q + Q[:1], 6.0)[:-1]
        if len(Q) < 3:
            continue
        pa = abs(_area(Q))
        tx, ty = sum(p[0] for p in Q) / len(Q), sum(p[1] for p in Q) / len(Q)
        out.append({"n": short_name(n), "k": "park", "z": max(1, int(pa / (CW * CH))), "pg": 1,
                    "r": [[round(v) for q in Q for v in q]], "p": [], "o": [], "t": [round(tx), round(ty)],
                    "_full": n})
    return out


def _area(R):
    return sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(R, R[1:] + R[:1])) / 2


def blocks_in(streets, ring, water_rings, parks, keep, pad=40.0):
    """Blocks with lots between the free streets, inside the page ring of the free domain: palace_place.lots on a
    window around it (the grid's drawn region and the parks filled, so no face reaches into them); keep(x, y) filters
    lots (off the river, out of the grid). -> [{x, y, lots, fr}] in page px."""
    from .palace_place import lots
    xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
    x0, y0 = min(xs) - pad, min(ys) - pad
    W, H = max(xs) - x0 + pad, max(ys) - y0 + pad

    def sh(flat):
        return [round(v - (x0 if i % 2 == 0 else y0), 1) for i, v in enumerate(flat)]
    sub = {"W": W, "H": H, "streets": [{"k": s["k"], "p": sh(s["p"])} for s in streets],
           "water": [sh(r) for r in water_rings], "parks": [{"r": [sh(r) for r in pk["r"]]} for pk in parks]}
    # the free domain's own edge closes the faces along it
    flat = [v for q in ring + ring[:1] for v in q]
    sub["streets"].append({"k": 5, "p": sh(flat)})
    B = 150.0
    sb = {}
    for s in streets:
        P = _pairs(s["p"])
        for a, c in zip(P, P[1:]):
            for i in range(int(min(a[0], c[0]) // B), int(max(a[0], c[0]) // B) + 1):
                for j in range(int(min(a[1], c[1]) // B), int(max(a[1], c[1]) // B) + 1):
                    sb.setdefault((i, j), []).append((a, c))

    def fronts(x, y):
        i, j = int(x // B), int(y // B)
        return any(segd((x, y), a, c) <= FRONT_MAX for u in (i - 1, i, i + 1) for v in (j - 1, j, j + 1)
                   for a, c in sb.get((u, v), ()))
    out = []
    for b in lots(sub, cell=6):
        bx, by = b["x"] + x0, b["y"] + y0
        if not _inside((bx, by), [ring]):
            continue
        L = [[round(l[0] + x0, 1), round(l[1] + y0, 1)] + l[2:] for l in b["lots"]]
        L = [l for l in L if keep(l[0], l[1]) and fronts(l[0], l[1])]
        if L:
            out.append({"x": round(bx, 1), "y": round(by, 1), "lots": L, "fr": 1})
    return out
