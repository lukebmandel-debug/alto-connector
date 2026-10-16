"""City engine v2: one domain's even lattice on the page (design sections 2.5, 4.4 and 8.2).

A domain's lattice lives in its own LOCAL frame (local px: column i at x = xg[i], row j at y = yg[j], exactly today's
grid tables) and reaches the page by a rigid transform T_d: page = R(a) . local + o, a in degrees, screen convention
(y down, so a positive angle turns clockwise on the screen; this is also what SVG rotate(a) does). The domain's page
region is a clip ring (any simple polygon, page px). `Lattice` answers geometry questions; `emit()` turns a lattice
into exactly what the page draws and walks.

PAGE DATA CONTRACT (what the integrator puts into the map `m` that palace.py draws; every key below is OPTIONAL and a
page without them renders exactly as before):

  m["tiles"]   [[x0, y0, x1, y1], ...]  upright full blocks (today's meaning). In v2 only the ROOT domain's full cells.
  m["edges"]   [[x0, y0, x1, y1], ...]  upright loose street segments no block draws (today's meaning), root domain only.
  m["tq"]      [[x0, y0, x1, y1, x2, y2, ...], ...]  polygon tiles, page px, >= 3 vertices, in ring order: every
               tilted domain's cells and every cut block of any domain (root included). Drawn like a tile: the outline
               as a rounded polygon (corner radius R = 20) of minor street, coloured by the district at its centroid.
  m["te"]      [[x0, y0, x1, y1, ...], ...]  loose street polylines of tilted domains (and of the root where a line is
               cut by a seam), minor weight; corners rounded with R.
  m["streets"] each lattice line of each domain as one street {"n": name, "k": 0 major | 1, "p": [x0, y0, x1, y1, ...]}
               (the polyline the walking graph, labels and hover hits use, as today). New optional key "L": 1 marks a
               HEAVY line (a major lattice line in any domain, and the seam avenue): the page draws it as one heavy tube
               along its polyline (rounded at its bends), in the colour of each district it passes. When ANY street
               carries "L", the page's old heavy overlay of tile edges (M.cols / M.rows) is switched off, so the root
               domain's majors must carry "L" too (emit() does that). A line that ends on a seam ends with a 40 px lead
               ALONG the seam (a rounded T-join); a hinge line (through=) ends exactly on the seam and join_hinges()
               makes the two sides one polyline with one rounded bend. The seam itself must be a street too (named
               avenue or ""), with "L": 1 when it is an avenue: lines T into it, and the walking graph crosses domains
               through it.
  blocks       [{"id", "x", "y", "lots": [[cx, cy, w, h, deg], ...]}]  unchanged shape; x, y = the block's page centroid,
               deg = the domain's page angle a (lots stand square to their own block). The page's lot hit test, edit
               mode '+' lots, drag slots and building cards already honour deg. Optional "r": [x, y] real centre.
  landmarks    {"n", "x", "y", "box": [x0, y0, x1, y1], "a": deg, "page"}: NEW optional "a". box is the landmark's
               block in its domain's local orientation, placed UNROTATED around the page centre (x, y); the page
               rotates the drawing by a about the box centre and un-rotates the pointer before its box tests.

Units: page px throughout (1 lattice block = CW x CH = 240 x 170 unless a domain swaps roles), angles in degrees.
Pure module: no I/O, no globals mutated.
"""
from __future__ import annotations

import math

CW, CH = 240, 170              # the page block (palace_grid.CW/CH; repeated here so this module imports nothing heavy)
R = 20                         # the page's corner radius for rounded tiles and turns
LEAD = 40                      # a line that ends on a seam turns along it this far (design 2.5)
FULL, KEEP = 0.98, 0.35        # cell area fractions: full tile / cut block / sliver (design 2.5)
GAP = 12                       # lots: the gap between row houses and the street (palace_grid.blocks)


# ── plane geometry ──────────────────────────────────────────────────────────
def area(poly) -> float:
    """Signed area (positive = clockwise on the screen, y down)."""
    n = len(poly)
    return sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n)) / 2


def centroid(poly):
    a = area(poly)
    if abs(a) < 1e-9:
        n = len(poly) or 1
        return (sum(p[0] for p in poly) / n, sum(p[1] for p in poly) / n)
    cx = cy = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        f = x0 * y1 - x1 * y0
        cx += (x0 + x1) * f
        cy += (y0 + y1) * f
    return (cx / (6 * a), cy / (6 * a))


def inside(poly, x, y) -> bool:
    """Point in a simple polygon (even-odd); a point ON the boundary counts as inside (within 0.01 px)."""
    n = len(poly)
    c = False
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        if _segdist(x, y, ax, ay, bx, by) < 0.01:
            return True
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            c = not c
    return c


def _segdist(x, y, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
    return math.hypot(ax + t * dx - x, ay + t * dy - y)


def clip_convex(subject, clipper):
    """Sutherland-Hodgman: `subject` (any simple ring) clipped by the CONVEX ring `clipper`."""
    out = list(subject)
    sgn = 1 if area(clipper) >= 0 else -1
    n = len(clipper)
    for i in range(n):
        ax, ay = clipper[i]
        bx, by = clipper[(i + 1) % n]

        def side(p):
            return sgn * ((bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax))
        src, out = out, []
        if not src:
            break
        for k in range(len(src)):
            p, q = src[k], src[(k + 1) % len(src)]
            sp, sq = side(p), side(q)
            if sp >= 0:
                out.append(p)
            if (sp >= 0) != (sq >= 0):
                t = sp / (sp - sq)
                out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    # drop repeated points
    res = []
    for p in out:
        if not res or math.hypot(p[0] - res[-1][0], p[1] - res[-1][1]) > 1e-6:
            res.append(p)
    if len(res) > 1 and math.hypot(res[0][0] - res[-1][0], res[0][1] - res[-1][1]) <= 1e-6:
        res.pop()
    return res if len(res) >= 3 else []


def seg_in_poly(poly, a, b):
    """The parts of segment ab inside the ring `poly` (any simple polygon): [(t0, t1), ...], 0 <= t <= 1."""
    if poly is None:
        return [(0.0, 1.0)]
    ts = [0.0, 1.0]
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = len(poly)
    for i in range(n):
        cx, cy = poly[i]
        ex, ey = poly[(i + 1) % n][0] - cx, poly[(i + 1) % n][1] - cy
        d = dx * ey - dy * ex
        if abs(d) < 1e-12:
            continue
        t = ((cx - a[0]) * ey - (cy - a[1]) * ex) / d
        u = ((cx - a[0]) * dy - (cy - a[1]) * dx) / d
        if -1e-9 <= u <= 1 + 1e-9 and 0 < t < 1:
            ts.append(t)
    ts.sort()
    out = []
    for t0, t1 in zip(ts, ts[1:]):
        if t1 - t0 < 1e-9:
            continue
        tm = (t0 + t1) / 2
        if inside(poly, a[0] + tm * dx, a[1] + tm * dy):
            if out and abs(out[-1][1] - t0) < 1e-9:
                out[-1] = (out[-1][0], t1)
            else:
                out.append((t0, t1))
    return out


def _r1(v):
    return round(v, 1)


def flat(pts):
    return [_r1(v) for p in pts for v in p]


# ── one domain's lattice ────────────────────────────────────────────────────
class Lattice:
    """dom: city_types.Domain (uses .a, .o, .clip); xg/yg: the local column / row positions (ascending);
    cw/ch: the domain's block (CH x CW when its roles are swapped, design 2.4). lm_cells: cells a landmark stands on."""

    def __init__(self, dom, xg, yg, cw=CW, ch=CH, lm_cells=()):
        self.dom = dom
        self.a = float(getattr(dom, "a", 0.0) or 0.0)
        o = getattr(dom, "o", (0.0, 0.0)) or (0.0, 0.0)
        self.o = (float(o[0]), float(o[1]))
        clip = getattr(dom, "clip", None)
        self.clip = [tuple(map(float, p)) for p in clip] if clip else None
        self.xg, self.yg = list(xg), list(yg)
        self.cw, self.ch = cw, ch
        self.lm_cells = set(map(tuple, lm_cells))
        r = math.radians(self.a)
        self._c, self._s = math.cos(r), math.sin(r)

    # T_d and its inverse
    def page(self, lx, ly):
        return (lx * self._c - ly * self._s + self.o[0], lx * self._s + ly * self._c + self.o[1])

    def local(self, x, y):
        x, y = x - self.o[0], y - self.o[1]
        return (x * self._c + y * self._s, -x * self._s + y * self._c)

    def node(self, i, j):
        return self.page(self.xg[i], self.yg[j])

    def cell_rect(self, i, j):
        """The cell's four page corners (unclipped), clockwise on the screen."""
        return [self.node(i, j), self.node(i + 1, j), self.node(i + 1, j + 1), self.node(i, j + 1)]

    def cell_poly(self, i, j):
        """The cell clipped to the domain's region ([] when it is outside)."""
        q = self.cell_rect(i, j)
        return clip_convex(self.clip, q) if self.clip else q

    def inside(self, x, y):
        return True if self.clip is None else inside(self.clip, x, y)

    own = False                    # True: a lattice segment is drawn only beside a drawn cell (city_engine.DomLattice)

    def seg_in(self, a, b):
        """The parts of page segment ab inside the domain's region: [(t0, t1), ...]."""
        return seg_in_poly(self.clip, a, b)

    def clip_poly(self, poly):
        """A convex page polygon clipped to the domain's region."""
        return clip_convex(self.clip, poly) if self.clip else poly

    def frac(self, poly, i, j):
        full = (self.xg[i + 1] - self.xg[i]) * (self.yg[j + 1] - self.yg[j])
        return abs(area(poly)) / full if poly and full else 0.0

    def line_ends(self, fam, k):
        """A whole lattice line across the tables: column k ('v') or row k ('h')."""
        if fam == "v":
            return self.page(self.xg[k], self.yg[0]), self.page(self.xg[k], self.yg[-1])
        return self.page(self.xg[0], self.yg[k]), self.page(self.xg[-1], self.yg[k])

    def seg(self, fam, k, m):
        """The m-th lattice segment of line (fam, k): between crossings m and m + 1 (page points)."""
        if fam == "v":
            return self.node(k, m), self.node(k, m + 1)
        return self.node(m, k), self.node(m + 1, k)

    def lot_page(self, lx, ly, w, h):
        x, y = self.page(lx, ly)
        return [_r1(x), _r1(y), _r1(w), _r1(h), _r1(self.a)]


# ── what the page draws ─────────────────────────────────────────────────────
def emit(lat: Lattice, names=None, majors=(), through=(), root=None, lots=True, lead=LEAD, wet=None, seams=()):
    """Everything the page needs of one domain (see the contract in the module docstring).

    names:   {"v": [name per column index], "h": [name per row index]} ("" or missing: unnamed)
    majors:  names drawn heavy ("L": 1)
    through: {(fam, k), ...} hinge lines: they end exactly on the seam (no lead) and join_hinges() joins them across it
    seams:   [(x0, y0, x1, y1), ...] the page segments of this domain's seams (Seam.segs): a line that ends on one turns
             along it for `lead` px (a T-join); a line that ends on the domain's outer edge (the city's edge) just ends,
             as today's grid does
    root:    True for the root domain (a = 0): its full cells go to "tiles" and full loose segments to "edges" in today's
             upright format; default: a == 0
    wet:     optional predicate wet((x, y)) -> True where a lot must not stand (water)
    Returns {"tiles", "edges", "tq", "te", "streets", "blocks", "cells"}; "cells" maps (i, j) -> kind
    ("full" | "cut" | "plaza" | "merged" | "sliver" | "out" | "lm") for reports and tests."""
    names = names or {}
    majors = set(majors)
    through = set(through)
    root = (abs(lat.a) < 1e-9) if root is None else root
    nx, ny = len(lat.xg) - 1, len(lat.yg) - 1

    def name(fam, k):
        ls = names.get(fam) or []
        return (ls[k] if k < len(ls) else "") or ""

    # 1. cells
    cells, polys = {}, {}
    for j in range(ny):
        for i in range(nx):
            if (i, j) in lat.lm_cells:
                cells[(i, j)] = "lm"
                continue
            p = lat.cell_poly(i, j)
            f = lat.frac(p, i, j)
            corners_in = all(lat.inside(*q) for q in lat.cell_rect(i, j))
            if f > FULL and corners_in:
                cells[(i, j)] = "full"
                p = lat.cell_rect(i, j)
            elif f >= KEEP:
                cells[(i, j)] = "cut"
            elif f > 1e-3:
                cells[(i, j)] = "sliver"
            else:
                cells[(i, j)] = "out"
                continue
            polys[(i, j)] = p

    # 2. slivers: merged into the neighbour across their longest stub (that stub of line is deleted), or kept as a
    #    plaza when the stub is a major or hinge line, or dropped when no neighbour can take them
    removed = set()                                       # (fam, k, m): lattice segments no longer drawn or walked
    for (i, j), kind in sorted(cells.items()):
        if kind != "sliver":
            continue
        cand = []
        for fam, k, m, nb in (("h", j, i, (i, j - 1)), ("h", j + 1, i, (i, j + 1)),
                              ("v", i, j, (i - 1, j)), ("v", i + 1, j, (i + 1, j))):
            a, b = lat.seg(fam, k, m)
            L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
            ins = sum(t1 - t0 for t0, t1 in lat.seg_in(a, b))
            if 1e-6 < ins < 1 - 1e-6 and cells.get(nb) in ("full", "cut"):
                cand.append((ins * L, fam, k, m, nb))
        if not cand:
            cells[(i, j)] = "out"
            polys.pop((i, j), None)
            continue
        cand.sort(reverse=True)
        _, fam, k, m, nb = cand[0]
        if name(fam, k) in majors or (fam, k) in through:
            cells[(i, j)] = "plaza"
            continue
        i0, j0 = min(i, nb[0]), min(j, nb[1])
        i1, j1 = max(i, nb[0]) + 1, max(j, nb[1]) + 1
        big = [lat.page(lat.xg[i0], lat.yg[j0]), lat.page(lat.xg[i1], lat.yg[j0]),
               lat.page(lat.xg[i1], lat.yg[j1]), lat.page(lat.xg[i0], lat.yg[j1])]
        polys[nb] = lat.clip_poly(big)
        cells[nb] = "cut"
        cells[(i, j)] = "merged"
        polys.pop((i, j), None)
        removed.add((fam, k, m))

    drawn = {c for c, kd in cells.items() if kd in ("full", "cut", "plaza")}

    # 3. the drawing: tiles / tq, and the loose pieces of line
    tiles, tq = [], []
    for c in sorted(drawn, key=lambda c: (c[1], c[0])):
        p = polys[c]
        if root and cells[c] == "full":
            xs, ys = [q[0] for q in p], [q[1] for q in p]
            tiles.append([_r1(min(xs)), _r1(min(ys)), _r1(max(xs)), _r1(max(ys))])
        else:
            tq.append(flat(p))

    def covered(fam, k, m):
        if fam == "v":
            return (k - 1, m) in drawn or (k, m) in drawn
        return (m, k - 1) in drawn or (m, k) in drawn

    def lm_side(fam, k, m):
        sides = ((k - 1, m), (k, m)) if fam == "v" else ((m, k - 1), (m, k))
        return any(s in lat.lm_cells for s in sides)

    def in_lm(fam, k, m):
        """A segment strictly inside a landmark's footprint (both sides are landmark cells)."""
        sides = ((k - 1, m), (k, m)) if fam == "v" else ((m, k - 1), (m, k))
        return all(s in lat.lm_cells for s in sides)

    edges, te, streets = [], [], []
    for fam, count, steps in (("v", nx + 1, ny), ("h", ny + 1, nx)):
        for k in range(count):
            nm, maj = name(fam, k), name(fam, k) in majors
            # every walkable piece of this line: lattice segments clipped to the region, minus the removed stubs
            pieces = []                                    # [(a, b, m, full?)] in order along the line
            for m in range(steps):
                if (fam, k, m) in removed:
                    pieces.append(None)
                    continue
                a, b = lat.seg(fam, k, m)
                ivs = lat.seg_in(a, b)
                if lat.own and not covered(fam, k, m) and not lm_side(fam, k, m):
                    ivs = []
                if not ivs:
                    pieces.append(None)
                for t0, t1 in ivs:
                    pa = (a[0] + t0 * (b[0] - a[0]), a[1] + t0 * (b[1] - a[1]))
                    pb = (a[0] + t1 * (b[0] - a[0]), a[1] + t1 * (b[1] - a[1]))
                    if math.hypot(pb[0] - pa[0], pb[1] - pa[1]) > 0.5:
                        pieces.append((pa, pb, m, t0 < 1e-9 and t1 > 1 - 1e-9))
                    else:
                        pieces.append(None)
            # runs of touching pieces = the line's polylines
            runs, cur = [], []
            for pc in pieces:
                if pc is None or (cur and math.hypot(pc[0][0] - cur[-1][1][0], pc[0][1] - cur[-1][1][1]) > 0.5):
                    if cur:
                        runs.append(cur)
                    cur = [pc] if pc else []
                else:
                    cur.append(pc)
            if cur:
                runs.append(cur)
            for run in runs:
                pts = [run[0][0]] + [pc[1] for pc in run]
                d0 = _unit(pts[1], pts[0])                 # direction arriving at the start end (walking backwards)
                d1 = _unit(pts[-2], pts[-1])
                head, tail = [], []
                if (fam, k) not in through and lead > 0:
                    u, room = _seam_dir(seams, pts[0], d0)
                    if u and room > 1:
                        L_ = min(lead, room * .5)
                        head = [(pts[0][0] + u[0] * L_, pts[0][1] + u[1] * L_)]
                    u, room = _seam_dir(seams, pts[-1], d1)
                    if u and room > 1:
                        L_ = min(lead, room * .5)
                        tail = [(pts[-1][0] + u[0] * L_, pts[-1][1] + u[1] * L_)]
                line = head[::-1] + pts + tail
                st = {"n": nm, "k": 0 if maj else 1, "p": flat(line)}
                if maj:
                    st["L"] = 1
                streets.append(st)
                # loose pieces: the segments no drawn cell outlines
                loose, lc = [], []
                for idx, pc in enumerate(run):
                    if not covered(fam, k, pc[2]) and not in_lm(fam, k, pc[2]):
                        if root and pc[3]:
                            a, b = pc[0], pc[1]
                            edges.append([_r1(min(a[0], b[0])), _r1(min(a[1], b[1])), _r1(max(a[0], b[0])), _r1(max(a[1], b[1]))])
                            if lc:
                                loose.append(lc)
                            lc = []
                            continue
                        if not lc:
                            lc = ([] if idx else head[::-1]) + [pc[0]]
                        lc.append(pc[1])
                        if idx == len(run) - 1:
                            lc += tail
                    elif lc:
                        loose.append(lc)
                        lc = []
                if lc:
                    loose.append(lc)
                te.extend(flat(q) for q in loose if len(q) >= 2)

    # 4. blocks and lots: two fronts of row houses per block (palace_grid.blocks), square to the block; a lot of a cut
    #    block is kept only when its whole rectangle (2 px out) lies inside the block's polygon
    blocks = []
    if lots:
        for c in sorted(drawn, key=lambda c: (c[1], c[0])):
            if cells[c] == "plaza":
                continue
            i, j = c
            ok_cells = {c}
            if cells[c] == "cut":                         # a merged sliver's own cell joins its neighbour
                for nb in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
                    if cells.get(nb) == "merged":
                        ok_cells.add(nb)
            poly = polys[c]
            ls = []
            for (ci, cj) in sorted(ok_cells, key=lambda q: (q[1], q[0])):
                x0, x1, y0, y1 = lat.xg[ci], lat.xg[ci + 1], lat.yg[cj], lat.yg[cj + 1]
                w = (x1 - x0 - 3 * GAP) / 2
                h = (y1 - y0 - 3 * GAP - 30) / 2
                for yy in (y0 + GAP + h / 2, y1 - GAP - h / 2):
                    for xx in (x0 + GAP + w / 2, x1 - GAP - w / 2):
                        cx, cy = lat.page(xx, yy)
                        if wet and wet((cx, cy)):
                            continue
                        if cells[c] != "full":
                            hw, hh = w / 2 + 2, h / 2 + 2        # the whole lot, and a little room from the street
                            corners = [lat.page(xx + sx * hw, yy + sy * hh) for sx in (-1, 1) for sy in (-1, 1)]
                            if not all(inside(poly, *q) for q in corners):
                                continue
                        ls.append(lat.lot_page(xx, yy, w, h))
            if ls:
                ctr = centroid(poly)
                blocks.append({"x": _r1(ctr[0]), "y": _r1(ctr[1]), "lots": ls, "cell": [i, j]})
    blocks.sort(key=lambda b: (b["y"], b["x"]))
    for k, b in enumerate(blocks):
        b["id"] = k
    return {"tiles": tiles, "edges": edges, "tq": tq, "te": te, "streets": streets, "blocks": blocks, "cells": cells}


def _unit(a, b):
    """The unit vector from a to b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1.0
    return (dx / L, dy / L)


def _seam_dir(seams, p, d):
    """When p lies on one of the seam segments: that seam's direction signed to agree with d (the smaller turn) and the
    room left along it; else (None, 0)."""
    for x0, y0, x1, y1 in seams or ():
        if _segdist(p[0], p[1], x0, y0, x1, y1) < 0.5:
            L = math.hypot(x1 - x0, y1 - y0) or 1.0
            u = ((x1 - x0) / L, (y1 - y0) / L)
            if u[0] * d[0] + u[1] * d[1] < 0:
                return (-u[0], -u[1]), math.hypot(x0 - p[0], y0 - p[1])
            return u, math.hypot(x1 - p[0], y1 - p[1])
    return None, 0.0


def join_hinges(streets, tol=2.5):
    """Hinge lines: two streets of one name whose ends meet (within tol px) become one polyline with one bend at the
    meeting point (the page rounds it). Returns a new list; "L" is kept when either piece had it."""
    out = [dict(s, p=list(s["p"])) for s in streets]
    changed = True
    while changed:
        changed = False
        for x in range(len(out)):
            a = out[x]
            if not a.get("n"):
                continue
            for y in range(x + 1, len(out)):
                b = out[y]
                if b.get("n") != a["n"]:
                    continue
                pa, pb = a["p"], b["p"]
                ends = (((pa[-2], pa[-1]), (pb[0], pb[1]), lambda: pa + pb[2:]),
                        ((pa[-2], pa[-1]), (pb[-2], pb[-1]), lambda: pa + _rev(pb)[2:]),
                        ((pa[0], pa[1]), (pb[-2], pb[-1]), lambda: pb + pa[2:]),
                        ((pa[0], pa[1]), (pb[0], pb[1]), lambda: _rev(pb) + pa[2:]))
                for e0, e1, mk in ends:
                    if math.hypot(e0[0] - e1[0], e0[1] - e1[1]) <= tol:
                        a["p"] = mk()
                        if b.get("L"):
                            a["L"] = 1
                        a["k"] = min(a.get("k", 1), b.get("k", 1))
                        out.pop(y)
                        changed = True
                        break
                if changed:
                    break
            if changed:
                break
    return out


def _rev(p):
    return [v for i in range(len(p) - 2, -1, -2) for v in (p[i], p[i + 1])]


def landmark(lat: Lattice, i0, j0, i1, j1, n, page=""):
    """A landmark standing on cells i0..i1-1 x j0..j1-1 of a domain: its page record with the rotation "a" (contract)."""
    lx, ly = (lat.xg[i0] + lat.xg[i1]) / 2, (lat.yg[j0] + lat.yg[j1]) / 2
    w, h = lat.xg[i1] - lat.xg[i0], lat.yg[j1] - lat.yg[j0]
    x, y = lat.page(lx, ly)
    out = {"n": n, "x": _r1(x), "y": _r1(y), "r": [], "box": [_r1(x - w / 2), _r1(y - h / 2), _r1(x + w / 2), _r1(y + h / 2)],
           "page": page}
    if abs(lat.a) > 1e-9:
        out["a"] = _r1(lat.a)
    return out


def rot_point(x, y, cx, cy, deg):
    """(x, y) turned by deg (screen convention, as SVG rotate) about (cx, cy)."""
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    dx, dy = x - cx, y - cy
    return (cx + dx * c - dy * s, cy + dx * s + dy * c)
