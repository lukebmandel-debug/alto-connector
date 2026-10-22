"""The other boroughs at full detail (1.9.145): every street of Brooklyn, Queens, the Bronx, Staten Island and upper Manhattan on
Alto's graph paper, drawn IN PLACE on New York's page (city_manhattan's layout; city_boroughs.Outer carries the real city onto it).

Luke's rules (feedback_alto_palace_style): a perfectly even grid where the city has one — the real city decides which streets exist and
their order, every block of a grid the same size, each grid at its own angle, hinged where real grids meet, nothing from nowhere (a street
starts and stops on a crossing street); smoothed real streets where there is no grid.

Unlike city_engine (which lays every grid out afresh on its own page, hundreds of metres from where the street really is), each grid here
keeps its place: city_domains.detect finds the grids in real px; on the page each grid's lines are snapped to one even pitch and phase
fitted to where the streets really run (an error under half a block), so the blocks meet the real shore, parks and roads the rest of the
page already draws. build() returns page geometry (tq block rings, te loose lines, streets for names and heavy lines) and, per grid, its
frame (FILL domain: angle, origin, pitch, phase, the block cells) for the buildings (fill()).
"""
from __future__ import annotations

import math
from collections import defaultdict

ALIGN_DEG = 14.0              # a street piece within this of a grid axis runs along it
PITCH_MIN, PITCH_MAX = 70.0, 760.0   # page px: a plausible block side
MERGE_FRAC = 0.33             # two lines of one family closer than this share of the pitch are one street (a divided road)
SIDES_MIN = 2                 # a block needs this many of its four sides on real streets
COVER = 0.55                  # ... a side counts when a street runs along this share of it
GAP_JOIN = 1.3                # blocks: two runs of one street this close are one run
MIN_LINE_PX = 160.0           # page px: a line shorter than this is no lattice line
EVEN_WIN = 4                  # rungs: a grid's spacing is evened over this many lines either side
HEAVY_K = 1                   # k <= this (motorway, trunk, primary) is a heavy line
NAME_AVE = ("Avenue", "Boulevard", "Parkway", "Broadway", "Expressway", "Highway")
CELL_RASTER = 48.0            # page px: the land and park masks
ENCLOSED = 0.5               # a face is a block when streets run along this share of its edge
MAX_BLOCK_PX2 = 3.5e5         # page px^2 (about 330 m square in New York): a face bigger than this is open ground, not a block


# ── small geometry ──────────────────────────────────────────────────────────
def _pairs(p):
    if p and isinstance(p[0], (list, tuple)):
        return [tuple(q) for q in p]
    return [(p[i], p[i + 1]) for i in range(0, len(p) - 1, 2)]


def _in_ring(r, x, y):
    c = False
    n = len(r)
    j = n - 1
    for i in range(n):
        xi, yi = r[i]
        xj, yj = r[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


class Mask:
    """A boolean raster over the page (CELL_RASTER px): rings filled even-odd, then `clear` rings emptied."""

    def __init__(self, W, H, rings=(), clear=(), cell=CELL_RASTER):
        self.c, self.nx, self.ny = cell, int(W / cell) + 2, int(H / cell) + 2
        self.b = bytearray(self.nx * self.ny)
        for r in rings:
            self._fill(r, 1, xor=True)
        for r in clear:
            self._fill(r, 0)

    def _fill(self, r, v, xor=False):
        pts = _pairs(r)
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        j0, j1 = max(0, int(min(ys) / self.c)), min(self.ny - 1, int(max(ys) / self.c) + 1)
        n = len(pts)
        for j in range(j0, j1 + 1):
            y = (j + .5) * self.c
            xs = []
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 > y) != (y1 > y):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            row = j * self.nx
            for a, b in zip(xs[0::2], xs[1::2]):
                i0, i1 = max(0, int(a / self.c + .5)), min(self.nx - 1, int(b / self.c - .5))
                for i in range(i0, i1 + 1):
                    if xor:
                        self.b[row + i] ^= 1
                    else:
                        self.b[row + i] = v

    def __call__(self, x, y):
        i, j = int(x / self.c), int(y / self.c)
        return 0 <= i < self.nx and 0 <= j < self.ny and self.b[j * self.nx + i] == 1


class Labels:
    """Which domain owns each page cell (CELL_RASTER px) of a box: the detection's own cells (real px squares) carried onto the page —
    a domain's traced polygon is simplified and can overlap its neighbour's by a cell, its cells never do."""

    def __init__(self, det, to_page, cell=CELL_RASTER):
        from array import array
        f = det.field
        quads = []
        for cy in range(f.ny):
            row = det.dom[cy]
            for cx in range(f.nx):
                d = row[cx]
                if d is None:
                    continue
                C = f.C
                quads.append((d, [to_page(cx * C, cy * C), to_page((cx + 1) * C, cy * C), to_page((cx + 1) * C, (cy + 1) * C), to_page(cx * C, (cy + 1) * C)]))
        xs = [p[0] for _d, q in quads for p in q] or [0.0]
        ys = [p[1] for _d, q in quads for p in q] or [0.0]
        self.c, self.x0, self.y0 = cell, min(xs), min(ys)
        self.nx, self.ny = int((max(xs) - self.x0) / cell) + 2, int((max(ys) - self.y0) / cell) + 2
        self.b = array("H", [0xFFFF]) * (self.nx * self.ny)
        for d, q in quads:
            ys_ = [p[1] for p in q]
            j0, j1 = max(0, int((min(ys_) - self.y0) / cell)), min(self.ny - 1, int((max(ys_) - self.y0) / cell) + 1)
            for j in range(j0, j1 + 1):
                y = self.y0 + (j + .5) * cell
                xs_ = []
                for k in range(4):
                    (ax, ay), (bx, by) = q[k], q[(k + 1) % 4]
                    if (ay > y) != (by > y):
                        xs_.append(ax + (y - ay) * (bx - ax) / (by - ay))
                if len(xs_) < 2:
                    continue
                a, b = min(xs_), max(xs_)
                i0, i1 = max(0, int((a - self.x0) / cell + .5)), min(self.nx - 1, int((b - self.x0) / cell - .5))
                for i in range(i0, i1 + 1):
                    self.b[j * self.nx + i] = d

    def __call__(self, x, y):
        i, j = int((x - self.x0) / self.c), int((y - self.y0) / self.c)
        if 0 <= i < self.nx and 0 <= j < self.ny:
            v = self.b[j * self.nx + i]
            return None if v == 0xFFFF else v
        return None


def _mode_angle(segs):
    """The dominant axis angle (radians, in [0, pi/2)) of [(x0, y0, x1, y1)], length weighted, 1 degree bins smoothed."""
    h = [0.0] * 90
    for x0, y0, x1, y1 in segs:
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 1:
            continue
        a = math.degrees(math.atan2(y1 - y0, x1 - x0)) % 90.0
        h[int(a) % 90] += L
    sm = [sum(h[(i + k) % 90] * w for k, w in ((-2, .25), (-1, .6), (0, 1), (1, .6), (2, .25))) for i in range(90)]
    i0 = max(range(90), key=lambda i: sm[i])
    # refine: the weighted mean within 5 degrees of the peak (wrapping)
    num = den = 0.0
    for x0, y0, x1, y1 in segs:
        L = math.hypot(x1 - x0, y1 - y0)
        a = math.degrees(math.atan2(y1 - y0, x1 - x0)) % 90.0
        d = (a - (i0 + .5) + 45) % 90 - 45
        if abs(d) <= 5:
            num += d * L
            den += L
    return math.radians(((i0 + .5) + (num / den if den else 0)) % 90.0)


def _union(iv, gap):
    """Merge [a, b] intervals closer than gap."""
    out = []
    for a, b in sorted(iv):
        if out and a <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def _covered(iv, a, b):
    """The share of [a, b] the intervals cover."""
    if b <= a:
        return 0.0
    s = 0.0
    for x, y in iv:
        s += max(0.0, min(b, y) - max(a, x))
    return s / (b - a)


# ── one grid domain ─────────────────────────────────────────────────────────
class Grid:
    """A grid domain on the page: frame (u along the angle a, v across it) about origin o; its column lines (constant u) at us[i] and its
    row lines (constant v) at vs[j], locally even (_even); lines {index: {"n", "k", "iv"}} per family. U(t) / V(t): the position of a
    line index (a fraction is a point between two lines; past the ends the end spacing goes on)."""

    def __init__(self, a, o):
        self.a, self.o = a, o
        self.c, self.s = math.cos(a), math.sin(a)

    def to(self, x, y):
        x, y = x - self.o[0], y - self.o[1]
        return (x * self.c + y * self.s, -x * self.s + y * self.c)

    def back(self, u, v):
        return (u * self.c - v * self.s + self.o[0], u * self.s + v * self.c + self.o[1])

    @staticmethod
    def _at(P, t):
        n = len(P)
        if t <= 0:
            return P[0] + t * (P[1] - P[0])
        if t >= n - 1:
            return P[-1] + (t - n + 1) * (P[-1] - P[-2])
        i = int(t)
        return P[i] + (t - i) * (P[i + 1] - P[i])

    @staticmethod
    def _idx(P, x):
        """The cell index (floor) of position x between lines."""
        from bisect import bisect_right
        return bisect_right(P, x) - 1

    def U(self, t):
        return self._at(self.us, t)

    def V(self, t):
        return self._at(self.vs, t)


def _lines(segs, along):
    """Family lines from frame segments [(off, a0, a1, name, k)]: same-named pieces within 60 px are one line; unnamed ones within 15 px.
    -> [{"off", "iv", "n", "k", "L"}] sorted by offset."""
    named, anon = defaultdict(list), []
    for s in segs:
        (named[s[3]] if s[3] else anon).append(s)
    out = []

    def make(group):
        tot = sum(s[2] - s[1] for s in group) or 1.0
        offs = sorted((s[0], s[2] - s[1]) for s in group)
        acc, med = 0.0, offs[0][0]
        for o, w in offs:
            acc += w
            if acc >= tot / 2:
                med = o
                break
        return {"off": med, "iv": _union([[s[1], s[2]] for s in group], 40.0), "n": group[0][3], "k": min(s[4] for s in group), "L": tot}
    for n, ss in named.items():
        ss.sort()
        cur = [ss[0]]
        for s in ss[1:]:
            if s[0] - cur[-1][0] <= 60.0:
                cur.append(s)
            else:
                out.append(make(cur))
                cur = [s]
        out.append(make(cur))
    anon.sort()
    cur = []
    for s in anon:
        if cur and s[0] - cur[-1][0] > 15.0:
            out.append(make(cur))
            cur = []
        cur.append(s)
    if cur:
        out.append(make(cur))
    return sorted((l for l in out if l["L"] >= MIN_LINE_PX * .5), key=lambda l: l["off"])


def _even(lines):
    """The lines of one family on a locally even ladder: lines closer than MERGE_FRAC of the local spacing are one street (a divided road);
    each gap is so many rungs (a missing street leaves an empty rung); every rung's position is a local linear fit of the lines within
    EVEN_WIN rungs, so neighbouring blocks are one size while the ladder follows the real city over kilometres. -> (positions, {rung: line})
    or None when the family has fewer than 3 lines or no plausible spacing."""
    good = [l for l in lines if l["L"] >= MIN_LINE_PX]
    if len(good) < 3:
        return None
    offs = [l["off"] for l in good]
    gaps = [b - a for a, b in zip(offs, offs[1:])]

    def local(t):                                   # the typical spacing round line t
        w = sorted(g for g in gaps[max(0, t - EVEN_WIN):t + EVEN_WIN] if PITCH_MIN <= g <= PITCH_MAX)
        return w[len(w) // 2] if w else None
    if not any(PITCH_MIN <= g_ <= PITCH_MAX for g_ in gaps):
        return None
    merged = [dict(good[0])]
    for t in range(1, len(good)):
        sp = local(t) or PITCH_MIN
        l = good[t]
        o = merged[-1]
        if l["off"] - o["off"] < MERGE_FRAC * sp:
            keep = dict(o if (o["k"], -o["L"]) <= (l["k"], -l["L"]) else l)
            keep["iv"] = _union(o["iv"] + l["iv"], 40.0)
            keep["L"] = o["L"] + l["L"]
            keep["off"] = (o["off"] * o["L"] + l["off"] * l["L"]) / (o["L"] + l["L"])
            merged[-1] = keep
        else:
            merged.append(dict(l))
    if len(merged) < 3:
        return None
    rung = [0]
    mo = [l["off"] for l in merged]
    mg = [b - a for a, b in zip(mo, mo[1:])]
    for t, gp in enumerate(mg):
        w = sorted(g_ for g_ in mg[max(0, t - EVEN_WIN):t + EVEN_WIN] if PITCH_MIN <= g_ <= PITCH_MAX)
        sp = max(w[len(w) // 2] if w else gp, PITCH_MIN)
        rung.append(rung[-1] + max(1, int(round(gp / sp))))
    K = rung[-1] + 1
    pos = []
    for k in range(K):
        win = EVEN_WIN
        pts = []
        while len(pts) < 2:                         # (past a wide gap the window grows to the nearest lines)
            pts = [(r, l["off"], l["L"]) for r, l in zip(rung, merged) if abs(r - k) <= win]
            win *= 2
        sw = sum(w for _r, _o, w in pts)
        mr = sum(r * w for r, _o, w in pts) / sw
        mo_ = sum(o * w for _r, o, w in pts) / sw
        var = sum(w * (r - mr) ** 2 for r, _o, w in pts)
        b = sum(w * (r - mr) * (o - mo_) for r, o, w in pts) / var if var > 1e-9 else 0.0
        pos.append(mo_ + b * (k - mr))
    for k in range(1, K):                           # never out of order
        if pos[k] <= pos[k - 1] + PITCH_MIN * .5:
            pos[k] = pos[k - 1] + PITCH_MIN * .5
    return pos, {r: l for r, l in zip(rung, merged)}


def _grid(pieces, poly_page):
    """A Grid from a domain's street pieces on the page ([(points, name, k)]), or None when it has no even grid."""
    segs = [(p[i][0], p[i][1], p[i + 1][0], p[i + 1][1]) for p, _n, _k in pieces for i in range(len(p) - 1)]
    if not segs:
        return None
    a = _mode_angle(segs)
    xs, ys = [p[0] for p in poly_page], [p[1] for p in poly_page]
    g = Grid(a, ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2))
    fam = {"u": [], "v": []}            # "u": lines of constant u (columns, running along v); "v": constant v (rows)
    diag = []
    for p, n, k in pieces:
        q = [g.to(*pt) for pt in p]
        run = []
        for (u0, v0), (u1, v1) in zip(q, q[1:]):
            d = math.degrees(math.atan2(v1 - v0, u1 - u0)) % 180.0
            if min(d, 180 - d) <= ALIGN_DEG:
                fam["v"].append(((v0 + v1) / 2, min(u0, u1), max(u0, u1), n, k))
            elif abs(d - 90) <= ALIGN_DEG:
                fam["u"].append(((u0 + u1) / 2, min(v0, v1), max(v0, v1), n, k))
            else:
                run.append(((u0, v0), (u1, v1)))
                continue
            if len(run) >= 1:
                diag.append((run, n, k))
                run = []
        if run:
            diag.append((run, n, k))
    eu, ev = _even(_lines(fam["u"], "v")), _even(_lines(fam["v"], "u"))
    if not eu or not ev:
        return None
    g.us, g.cols = eu
    g.vs, g.rows = ev
    g.diag = diag
    return g


def _snap_iv(iv, P, have):
    """A line's runs with their ends on crossing lines: each end to the nearest rung that has a line (within .6 of a rung), else the
    nearest rung. -> [(i0, i1)] rung runs (i0 < i1). P: the crossing family's positions."""
    out = []

    def frac(x):
        i = Grid._idx(P, x)
        if i < 0:
            return (x - P[0]) / (P[1] - P[0])
        if i >= len(P) - 1:
            return len(P) - 1 + (x - P[-1]) / (P[-1] - P[-2])
        return i + (x - P[i]) / (P[i + 1] - P[i])

    def near(x):
        r = round(x)
        best = None
        for j in (r, r - 1, r + 1):
            if j in have and abs(j - x) <= .6 and (best is None or abs(j - x) < abs(best - x)):
                best = j
        return best if best is not None else r
    for a, b in _union([[frac(a), frac(b)] for a, b in iv], GAP_JOIN):        # a street broken for less than GAP_JOIN blocks runs on
        i0, i1 = near(a), near(b)
        if i1 > i0:
            out.append((i0, i1))
    return out


def lattice(g, inside, land, park):
    """Blocks and lines of a Grid. inside(x, y): the page point is the domain's; land / park: page masks.
    A block is a face of the street lattice: the grid cells (on land, the domain's, no park) joined across every cell side no street runs
    along — a real block one avenue long and one street deep, however many pitches that is. A face bigger than MAX_BLOCK_PX2 is no block (a
    cemetery, a yard, an airfield). -> (blocks {cell: face id}, faces [cells], column runs {i: [(j0, j1)]}, row runs {j: [(i0, i1)]})."""
    def keep(runs, at):
        """A run's steps whose middle is the domain's (and the region's) and on land: runs split where they leave it."""
        out = []
        for a, b in runs:
            cur = None
            for k in range(a, b):
                X, Y = at(k + .5)
                if inside(X, Y) and land(X, Y):
                    cur = cur or [k, k]
                    cur[1] = k + 1
                elif cur:
                    out.append(tuple(cur))
                    cur = None
            if cur:
                out.append(tuple(cur))
        return out
    cr = {i: keep(_snap_iv(l["iv"], g.vs, g.rows), lambda k, i=i: g.back(g.U(i), g.V(k))) for i, l in g.cols.items()}
    rr = {j: keep(_snap_iv(l["iv"], g.us, g.cols), lambda k, j=j: g.back(g.U(k), g.V(j))) for j, l in g.rows.items()}
    blocks, faces = {}, []
    if not g.cols or not g.rows:
        return blocks, faces, cr, rr
    vcl = {(i, j) for i, runs in cr.items() for a, b in runs for j in range(a, b)}      # column i closes the side between (i-1, j) and (i, j)
    hcl = {(i, j) for j, runs in rr.items() for a, b in runs for i in range(a, b)}      # row j closes the side between (i, j-1) and (i, j)
    i0, i1, j0, j1 = min(g.cols) - 1, max(g.cols) + 1, min(g.rows) - 1, max(g.rows) + 1
    ok = {}

    def cell_ok(i, j):
        k = (i, j)
        if k not in ok:
            X, Y = g.back(g.U(i + .5), g.V(j + .5))
            ok[k] = inside(X, Y) and land(X, Y) and not park(X, Y)
        return ok[k]
    seen = set()
    pu = (g.us[-1] - g.us[0]) / max(1, len(g.us) - 1)
    pv = (g.vs[-1] - g.vs[0]) / max(1, len(g.vs) - 1)
    cap = MAX_BLOCK_PX2 / (pu * pv)
    for i in range(i0, i1):
        for j in range(j0, j1):
            if (i, j) in seen or not cell_ok(i, j):
                continue
            comp, st, big = [], [(i, j)], False
            seen.add((i, j))
            while st:
                a, b = st.pop()
                comp.append((a, b))
                if len(comp) > cap:
                    big = True
                for na, nb, closed in ((a + 1, b, (a + 1, b) in vcl), (a - 1, b, (a, b) in vcl),
                                       (a, b + 1, (a, b + 1) in hcl), (a, b - 1, (a, b) in hcl)):
                    if closed or (na, nb) in seen or not (i0 <= na < i1 and j0 <= nb < j1) or not cell_ok(na, nb):
                        continue
                    seen.add((na, nb))
                    st.append((na, nb))
            # a face is a block when streets run along most of its edge (ENCLOSED); ground beyond a grid's last street is open on one side
            S = set(comp)
            tot = cov = 0
            for a, b in comp:
                for nb, closed in (((a - 1, b), (a, b) in vcl), ((a + 1, b), (a + 1, b) in vcl), ((a, b - 1), (a, b) in hcl), ((a, b + 1), (a, b + 1) in hcl)):
                    if nb not in S:
                        tot += 1
                        cov += closed
            if big or cov < ENCLOSED * tot:
                continue
            fid = len(faces)
            faces.append(comp)
            for c in comp:
                blocks[c] = fid
    return blocks, faces, cr, rr


def _outline(cells):
    """The outer boundary of a set of grid cells, as lattice corners [(i, j)] counter-clockwise, collinear points dropped."""
    S = set(cells)
    nxt = {}
    for i, j in S:
        if (i, j - 1) not in S:
            nxt[(i, j)] = (i + 1, j)
        if (i + 1, j) not in S:
            nxt[(i + 1, j)] = (i + 1, j + 1)
        if (i, j + 1) not in S:
            nxt[(i + 1, j + 1)] = (i, j + 1)
        if (i - 1, j) not in S:
            nxt[(i, j + 1)] = (i, j)
    loops, used = [], set()
    for st in sorted(nxt):
        if st in used:
            continue
        loop, p = [], st
        while p not in used and p in nxt:
            used.add(p)
            loop.append(p)
            p = nxt[p]
        loops.append(loop)
    best = max(loops, key=len)
    out = []
    n = len(best)
    for k in range(n):
        a, b, c = best[k - 1], best[k], best[(k + 1) % n]
        if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) != 0:
            out.append(b)
    return out


def emit(g, blocks, faces, cr, rr, out, dom_index):
    """Page geometry of one grid into out: tq (each face's outline), te (line runs with no block either side), streets (names, heavy lines)."""
    def P(u, v):
        x, y = g.back(u, v)
        return [round(x), round(y)]                     # whole page px (about half a metre)
    for comp in faces:
        out["tq"].append([v for i, j in _outline(comp) for v in P(g.U(i), g.V(j))])
    for i, runs in cr.items():
        for j0, j1 in runs:
            seg = None
            for j in range(j0, j1):
                bare = (i - 1, j) not in blocks and (i, j) not in blocks
                if bare:
                    seg = seg or [j, j]
                    seg[1] = j + 1
                elif seg:
                    out["te"].append(P(g.U(i), g.V(seg[0])) + P(g.U(i), g.V(seg[1])))
                    seg = None
            if seg:
                out["te"].append(P(g.U(i), g.V(seg[0])) + P(g.U(i), g.V(seg[1])))
    for j, runs in rr.items():
        for i0, i1 in runs:
            seg = None
            for i in range(i0, i1):
                bare = (i, j - 1) not in blocks and (i, j) not in blocks
                if bare:
                    seg = seg or [i, i]
                    seg[1] = i + 1
                elif seg:
                    out["te"].append(P(g.U(seg[0]), g.V(j)) + P(g.U(seg[1]), g.V(j)))
                    seg = None
            if seg:
                out["te"].append(P(g.U(seg[0]), g.V(j)) + P(g.U(seg[1]), g.V(j)))
    for fam, lines, runs in (("u", g.cols, cr), ("v", g.rows, rr)):
        for idx, l in lines.items():
            for a, b in runs.get(idx, ()):
                p = (P(g.U(idx), g.V(a)) + P(g.U(idx), g.V(b))) if fam == "u" else (P(g.U(a), g.V(idx)) + P(g.U(b), g.V(idx)))
                heavy = l["k"] <= HEAVY_K
                st = {"n": l["n"] or "", "k": max(1, l["k"]) if heavy else 3, "p": p}     # primary k 1 (every zoom), the rest 3 (close in)
                if heavy:
                    st["L"] = 1
                if st["n"] or heavy:
                    out["streets"].append(st)
    # the buildings' frame: each face's cells and its box (a building is clipped to its face's box when the face is a rectangle)
    fb = []
    for comp in faces:
        xs, ys = [c[0] for c in comp], [c[1] for c in comp]
        fb.append([min(xs), min(ys), max(xs) + 1, max(ys) + 1, 1 if len(comp) == (max(xs) + 1 - min(xs)) * (max(ys) + 1 - min(ys)) else 0])
    out["doms"].append({"a": round(math.degrees(g.a), 4), "o": [round(g.o[0], 2), round(g.o[1], 2)], "us": [round(v, 1) for v in g.us],
                        "vs": [round(v, 1) for v in g.vs], "b": sorted([c[0], c[1], f] for c, f in blocks.items()), "fb": fb, "i": dom_index})


def _chain(pieces, tol=30.0):
    """Pieces [(points, name, k)] of one name joined end to end where they meet (within tol px)."""
    by = defaultdict(list)
    for p, n, k in pieces:
        by[(n, k)].append(list(p))
    out = []
    for (n, k), ps in by.items():
        while ps:
            cur = ps.pop()
            grew = True
            while grew:
                grew = False
                for i, q in enumerate(ps):
                    for a, b, rev in ((cur[-1], q[0], False), (cur[-1], q[-1], True), (cur[0], q[-1], None), (cur[0], q[0], "both")):
                        if math.hypot(a[0] - b[0], a[1] - b[1]) <= tol:
                            if rev is False:
                                cur = cur + q[1:]
                            elif rev is True:
                                cur = cur + q[::-1][1:]
                            elif rev is None:
                                cur = q + cur[1:]
                            else:
                                cur = q[::-1] + cur[1:]
                            ps.pop(i)
                            grew = True
                            break
                    if grew:
                        break
            out.append((cur, n, k))
    return out


def free_lines(pieces, out, smooth):
    """A region with no grid: its real streets smoothed (te), the main ones (primary) as named diagonals; a highway or trunk is
    the light boroughs' own heavy line (city_boroughs.roads_page) and is not drawn again."""
    for p, n, k in _chain(pieces):
        if len(p) < 2 or k == 0:
            continue
        q = smooth(p) if len(p) > 2 else p
        flat = [round(v) for pt in q for v in pt]
        if k <= HEAVY_K:
            out["streets"].append({"n": n or "", "k": 1, "d": 1, "p": flat})
        else:
            out["te"].append(flat)
            if n:
                out["streets"].append({"n": n, "k": 3, "p": flat})


def build(m_real, to_page, land, park, inside_city=None, dom_base=0):
    """Every street of a region (m_real: palace_map.build_map in real px) on the page. to_page(x, y): real px -> page px; land / park:
    page masks; inside_city(x, y): the page point is the region's to draw (a borough's outline). -> {"tq", "te", "streets", "doms", "free"}."""
    from . import city_domains, city_free
    out = {"tq": [], "te": [], "streets": [], "doms": [], "free": [], "stats": {}}
    det = city_domains.detect(m_real)
    inside_city = inside_city or (lambda x, y: True)
    lab = Labels(det, to_page)
    for d in det.domains:
        pieces = []
        for st in d.streets or ():
            pts = _pairs(st.get("p") or [])
            if len(pts) >= 2 and st.get("k", 4) <= 4:
                pieces.append(([to_page(*q) for q in pts], st.get("n") or "", st.get("k", 4)))
        poly = [to_page(*q) for q in d.poly]
        if len(poly) < 3:
            continue

        def inside(x, y, did=d.id):
            return lab(x, y) == did and inside_city(x, y)
        g = _grid(pieces, poly) if d.kind == "grid" else None
        if g is None:
            free_lines([(p, n, k) for p, n, k in pieces if inside(*p[len(p) // 2])], out, lambda p: city_free.smooth(p, 8.0, 1))
            out["free"].append([round(v, 1) for q in poly for v in q])
            continue
        blocks, faces, cr, rr = lattice(g, inside, land, park)
        emit(g, blocks, faces, cr, rr, out, dom_base + len(out["doms"]))
        diag = [([g.back(*run[0][0])] + [g.back(*s_[1]) for s_ in run], n, k) for run, n, k in g.diag if k == 1]
        for pts, n, k in _chain(diag):              # a diagonal avenue across the grid: one clean line
            if inside(*pts[len(pts) // 2]):
                out["streets"].append({"n": n or "", "k": 1, "d": 1, "p": [round(v) for q in city_free.smooth(pts, 10.0, 1) for v in q]})
        out["stats"][d.id] = {"blocks": len(faces), "deg": round(math.degrees(g.a), 1),
                              "cols": len(g.cols), "rows": len(g.rows)}
    return out


# ── New York: the boroughs around Manhattan's layout (city_manhattan._the_rest calls nyc()) ──────────────────────────
CTX: dict = {}                    # set by palace.set_up for the NYC preset: {"cache_dir", "offline"}
REGIONS = (("Brooklyn and Queens", ("Brooklyn", "Queens")), ("The Bronx", ("The Bronx",)), ("Staten Island", ("Staten Island",)),
           ("Upper Manhattan", ("Manhattan",)))
PARK_MIN_M2 = 4000.0              # a park this big (0.4 ha) is drawn
# the other boroughs' landmarks, drawn with their own art (palace_skyline): name, lat, lon, art, footprint width and depth (m)
LANDMARKS = (("Barclays Center", 40.6826, -73.9754, "bcl", 230, 200), ("Brooklyn Museum", 40.6712, -73.9636, "bkm", 150, 70),
             ("Soldiers' and Sailors' Arch", 40.6741, -73.9701, "ssa", 30, 20), ("Wonder Wheel", 40.5740, -73.9787, "ww", 40, 16),
             ("Parachute Jump", 40.5733, -73.9844, "pj", 30, 30), ("Yankee Stadium", 40.8296, -73.9262, "yank", 290, 260),
             ("NYBG Conservatory", 40.8633, -73.8800, "nybg", 110, 40), ("Citi Field", 40.7571, -73.8458, "citi", 260, 270),
             ("Unisphere", 40.7466, -73.8448, "uni", 90, 90), ("St. George Ferry Terminal", 40.6437, -74.0736, "sgt", 150, 70),
             ("The Met Cloisters", 40.8649, -73.9317, "clo", 120, 60))
BOX_DEG = (0.07, 0.09)            # degrees: a borough is laid out a box at a time (about 8 km) ...
BOX_PAD = 0.012                   # ... each seeing this much past its core


def _raw(bbox, cache_dir):
    """The cached OSM tiles covering the box (city_setup's tiles), merged; the missing ones are reported, never fetched here (a
    set_up that has not cached the boroughs draws them lighter, as before)."""
    import json as _json
    from pathlib import Path
    from .city_setup import plan_tiles
    from ..palace_map import merge_raw
    files, need = plan_tiles(bbox, cache_dir)
    raws = []
    for f in files:
        try:
            raws.append(_json.loads(Path(f).read_text("utf-8")))
        except (OSError, ValueError):
            continue
    return (merge_raw(*raws) if raws else {"elements": []}), need


def _ring_area(r):
    pts = _pairs(r)
    return abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))) / 2


def nyc(g, outer, streets, te, park_cells, roads_light):
    """Brooklyn, Queens, the Bronx, Staten Island and upper Manhattan at full detail on New York's page (g: city_manhattan's map, its sea,
    land and Manhattan's blocks already drawn). roads_light: what roads_page drew in these boroughs ([(kind, item)]: ("te", polyline) for a
    secondary road, ("st", street) for a primary one); where a borough's lattice is drawn they give way to it. Returns a report."""
    import time as _time
    from ..palace_map import build_map, project
    cache = CTX.get("cache_dir")
    if not cache:
        return {"skipped": "no cache"}
    W, H = g["W"], g["H"]
    t0 = _time.time()
    sea = Mask(W, H, g.get("sea") or [], clear=g.get("land") or [])
    occ = Mask(W, H, [[t[0], t[1], t[2], t[1], t[2], t[3], t[0], t[3]] for t in g.get("tiles") or []] + list(g.get("tq") or []))
    # real (Manhattan's box projection) <-> lat/lon, linear
    x0, y0 = outer.P1(40.7, -74.0)
    x1, y1 = outer.P1(40.8, -73.9)
    kx, ky = (x1 - x0) / 0.1, (y0 - y1) / 0.1

    def ll(x, y):
        return 40.7 - (y - y0) / ky, -74.0 + (x - x0) / kx
    rep = {"regions": {}}
    g.setdefault("tq", [])
    bdoms = g.setdefault("bdoms", [])
    frees_all = []
    for name, boros in REGIONS:
        rings = [r for b in boros for r in outer.boros.get(b, [])]
        if not rings:
            continue
        page_rings = [[v for p in r for v in outer(*p)] for r in rings]
        mask = Mask(W, H, page_rings)
        xs = [p[0] for r in rings for p in r]
        ys = [p[1] for r in rings for p in r]
        s_, w_ = ll(min(xs), max(ys))
        n_, e_ = ll(max(xs), min(ys))
        rr_ = rep["regions"][name] = {"missing": 0, "blocks": 0, "lines": 0, "streets": 0, "parks": 0, "grids": 0, "free": 0, "boxes": 0}
        # the region a box at a time (a grid is found and fitted where it is: one detection over a whole borough lumps grids a few
        # degrees apart into one); each box keeps what lies in its core, the margin only lets its grids see their streets past it
        nb_la = max(1, int(math.ceil((n_ - s_) / BOX_DEG[0])))
        nb_lo = max(1, int(math.ceil((e_ - w_) / BOX_DEG[1])))
        dla, dlo = (n_ - s_) / nb_la, (e_ - w_) / nb_lo
        for bi in range(nb_la):
            for bj in range(nb_lo):
                core = (s_ + bi * dla, w_ + bj * dlo, s_ + (bi + 1) * dla, w_ + (bj + 1) * dlo)
                bbox = (round(core[0] - BOX_PAD, 4), round(core[1] - BOX_PAD * 1.3, 4), round(core[2] + BOX_PAD, 4), round(core[3] + BOX_PAD * 1.3, 4))
                core_pg = [outer(*outer.P1(la, lo)) for la, lo in ((core[0], core[1]), (core[0], core[3]), (core[2], core[3]), (core[2], core[1]))]
                cx_, cy_ = sum(p[0] for p in core_pg) / 4, sum(p[1] for p in core_pg) / 4
                if not any(mask(*p) for p in core_pg + [(cx_, cy_)]) and not any(
                        mask(core_pg[0][0] + (core_pg[2][0] - core_pg[0][0]) * a / 4, core_pg[0][1] + (core_pg[2][1] - core_pg[0][1]) * a / 4)
                        for a in range(5)):
                    continue
                raw, missing = _raw(bbox, cache)
                rr_["missing"] += len(missing)
                if not raw.get("elements"):
                    continue
                m = build_map(raw, bbox)
                sc = m.get("scale", 1.0)
                kxr = math.cos(math.radians((bbox[0] + bbox[2]) / 2)) * 111320 * sc
                kyr = 110574 * sc

                def to_page(x, y, bbox=bbox, kxr=kxr, kyr=kyr):
                    lat, lon = bbox[2] - y / kyr, bbox[1] + x / kxr
                    return outer(*outer.P1(lat, lon))

                def inside_city(x, y, mask=mask, core_pg=core_pg):
                    return mask(x, y) and not occ(x, y) and _in_ring(core_pg, x, y)
                parks = []
                for pk in m.get("parks") or []:
                    rs = [r for r in pk.get("r") or [] if len(r) >= 6]
                    if not rs or sum(_ring_area(r) for r in rs) < PARK_MIN_M2 * sc * sc:
                        continue
                    from .city_domains import _dp as _dp_
                    prs = [[round(v) for q in _dp_([to_page(*q) for q in _pairs(r)] + [to_page(*_pairs(r)[0])], 8.0)[:-1] for v in q] for r in rs]
                    prs = [r_ for r_ in prs if len(r_) >= 6]
                    if not prs:
                        continue
                    c = _pairs(prs[0])
                    cx, cy = sum(p[0] for p in c) / len(c), sum(p[1] for p in c) / len(c)
                    if not inside_city(cx, cy):
                        continue
                    parks.append({"n": pk.get("n") or "", "k": "park", "z": 1, "r": prs, "p": [], "o": [], "t": [round(cx), round(cy)], "pg": 1})
                park = Mask(W, H, [r for pk in parks for r in pk["r"]] + [r for pk in park_cells if pk.get("pg") for r in pk["r"]])
                out = build(m, to_page, lambda x, y: not sea(x, y), park, inside_city, dom_base=len(bdoms))
                gone = set()                                # the light roads here are drawn again from the box's own streets
                for kind, it in roads_light:
                    p = it["p"] if kind == "st" else it
                    mx, my = p[2 * (len(p) // 4)], p[2 * (len(p) // 4) + 1]
                    if inside_city(mx, my):
                        gone.add(id(it))
                streets[:] = [s_ for s_ in streets if id(s_) not in gone]
                te[:] = [t_ for t_ in te if id(t_) not in gone]
                have = {pk["n"] for pk in park_cells if pk.get("n")}
                park_cells += [pk for pk in parks if not (pk["n"] and pk["n"] in have)]
                g["tq"] += out["tq"]
                te += out["te"]
                streets += out["streets"]
                bdoms += out["doms"]
                frees_all += out["free"]
                rr_["boxes"] += 1
                for k_, v_ in (("blocks", len(out["tq"])), ("lines", len(out["te"])), ("streets", len(out["streets"])), ("parks", len(parks)),
                               ("grids", len(out["doms"])), ("free", len(out["free"]))):
                    rr_[k_] += v_
    # the landmarks of the other boroughs, at their real place, the blocks under them cleared
    a, b, c, d = outer.ax[0], outer.ax[1], outer.ay[0], outer.ay[1]
    kpx = math.sqrt(abs(a * d - b * c))                         # page px per metre (the affine's mean scale)
    have = {l.get("n") for l in g.get("landmarks") or []}
    lmb = []
    for n, la, lo, art, wm, dm in LANDMARKS:
        if n in have:
            continue
        x, y = outer(*outer.P1(la, lo))
        if not (0 < x < W and 0 < y < H):
            continue
        hw, hd = wm * kpx / 2, dm * kpx / 2
        box = [round(x - hw, 1), round(y - hd, 1), round(x + hw, 1), round(y + hd, 1)]
        g.setdefault("landmarks", []).append({"n": n, "x": round(x, 1), "y": round(y, 1), "box": box, "page": "", "art": art})
        lmb.append(box)
    if lmb:
        def under(r):
            pts = _pairs(r)
            cx, cy = sum(p_[0] for p_ in pts) / len(pts), sum(p_[1] for p_ in pts) / len(pts)
            return any(bx[0] - 20 <= cx <= bx[2] + 20 and bx[1] - 20 <= cy <= bx[3] + 20 for bx in lmb)
        g["tq"] = [r for r in g["tq"] if not under(r)]
    rep["landmarks"] = len(lmb)
    # every neighbourhood the map knows, named close in (the spaced ones in g["far"] show at every zoom; palace_tiles puts these in the tiles)
    far = [(f["x"], f["y"]) for f in g.get("far") or []]
    nb, seen_n = [], set()
    for n, k, x, y in outer.places:
        if n in seen_n or k not in ("suburb", "neighbourhood"):
            continue
        X, Y = outer(x, y)
        if not (0 < X < W and 0 < Y < H) or sea(X, Y) or occ(X, Y) or any(math.hypot(X - a_, Y - b_) < 900 for a_, b_ in far):
            continue
        seen_n.add(n)
        nb.append({"n": n, "x": round(X), "y": round(Y)})
    g["nb"] = nb
    rep["names"] = len(nb)
    # the buildings (fill_records), kept on the map for the fill-in (palace.set_up hands them to palace_fillin.fill_data and drops them)
    if bdoms and CTX.get("fill"):
        t1 = _time.time()
        regions = [Mask(W, H, [[v for p in r for v in outer(*p)] for b in bs for r in outer.boros.get(b, [])]) for _n, bs in REGIONS]
        pmask = Mask(W, H, [r for pk in park_cells if pk.get("pg") for r in pk.get("r") or []])
        from .city_boroughs import BBOX
        doms, recs = fill_records(bdoms, frees_all, lambda la, lo: outer(*outer.P1(la, lo)),
                                  lambda x, y: any(r(x, y) for r in regions) and not occ(x, y)
                                  and not any(bx[0] <= x <= bx[2] and bx[1] <= y <= bx[3] for bx in lmb), sea, pmask, cache, BBOX)
        g["bfill"] = {"doms": doms, "recs": recs}
        rep["buildings"] = [len(r) for r in recs]
        rep["fill_s"] = round(_time.time() - t1, 1)
    rep["s"] = round(_time.time() - t0, 1)
    return rep


# ── the buildings of the boroughs (the fill-in's records, palace_fillin's encoding) ───────────────────────────────
INSET = 12.0                      # page px between a building and its block's streets (palace_fillin.INSET)
INDEX_CELL = 1024.0               # page px: the index from a page cell to the grids with blocks there


def fill_records(bdoms, frees, to_page_ll, region_ok, sea, park, cache_dir, bbox):
    """Every cached building (bld-*.json tiles of the box, each read on its own, duplicates by OSM id dropped) on the page: inside a
    grid's block, clipped and squared to it (row houses as one shape per block front, palace_fillin.block_fronts); in a region with no
    grid (frees: page rings), as it stands. -> (FILL doms [[a, ox, oy]], records per level [(dom, j, i, units, height, name)]); the
    grids are doms 0..len(bdoms)-1, the free ground the last."""
    import json as _json
    from pathlib import Path
    from . import palace_fillin as pf
    from .. import palace_map as pmap
    grids = []
    idx = defaultdict(set)
    for k, d in enumerate(bdoms):
        g = Grid(math.radians(d["a"]), tuple(d["o"]))
        g.us, g.vs = d["us"], d["vs"]
        g.blocks = {(b[0], b[1]): b[2] for b in d["b"]}
        g.fb = d["fb"]
        grids.append(g)
        for i, j in g.blocks:
            X, Y = g.back(g.U(i + .5), g.V(j + .5))
            idx[(int(X // INDEX_CELL), int(Y // INDEX_CELL))].add(k)
    free = Mask(*_extent(frees), frees) if frees else (lambda x, y: False)
    fdom = len(grids)
    recs = [[], [], [], []]
    fronts = defaultdict(list)
    seen = set()
    s, w, n, e = bbox
    files = []
    for f in Path(cache_dir).glob("bld-*.json"):
        try:
            a, b, c, d_ = (float(v) for v in f.stem[4:].split("_"))
        except ValueError:
            continue
        if a < n and c > s and b < e and d_ > w:
            files.append(f)
    for f in sorted(files):
        try:
            raw = _json.loads(f.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        els = [el for el in raw.get("elements") or () if (el.get("type"), el.get("id")) not in seen]
        seen.update((el.get("type"), el.get("id")) for el in els)
        for ring, tags, area, h in pf.buildings({"elements": els}):
            t = pf.tier_of(tags, area, h)
            if t is None:
                continue
            pg = [to_page_ll(la, lo) for la, lo in ring]
            if len(pg) > 3 and pg[0] == pg[-1]:
                pg = pg[:-1]
            cx, cy = sum(p[0] for p in pg) / len(pg), sum(p[1] for p in pg) / len(pg)
            if not region_ok(cx, cy) or sea(cx, cy) or park(cx, cy):
                continue
            hit = None
            for k in idx.get((int(cx // INDEX_CELL), int(cy // INDEX_CELL)), ()):
                g = grids[k]
                u, v = g.to(cx, cy)
                ij = (Grid._idx(g.us, u), Grid._idx(g.vs, v))
                if ij in g.blocks:
                    hit = (k, g, ij)
                    break
            nm = str(tags.get("name") or "")[:60] if t <= 2 else ""
            q = pf.QUANT[t - 1]
            if hit is None:
                if not free(cx, cy):
                    continue
                loc = pmap.simplify_ring(pg, float(max(1, t)))
                u_ = pf._clean([(int(round(x / q)), int(round(y / q))) for x, y in loc])
                if u_ and abs(pmap.ring_area(u_)) * q * q >= 6:
                    recs[t - 1].append((fdom, 0, 0, u_, int(round(min(h, 400))), nm))
                continue
            k, g, (i, j) = hit
            loc = [g.to(*p) for p in pg]
            f = g.fb[g.blocks[(i, j)]]
            if f[4]:                                    # a rectangular face: the building stays whole inside it
                x0, y0, x1, y1 = g.U(f[0]), g.V(f[1]), g.U(f[2]), g.V(f[3])
                i, j = f[0], f[1]
            else:
                x0, y0, x1, y1 = g.U(i), g.V(j), g.U(i + 1), g.V(j + 1)
            gg = pf._clip(pf._snap(loc), x0 + INSET, y0 + INSET, x1 - INSET, y1 - INSET)
            if not gg:
                continue
            if t == 4:
                fronts[(k, i, j)].append((min(p[0] for p in gg), min(p[1] for p in gg), max(p[0] for p in gg), max(p[1] for p in gg)))
                continue
            if len(gg) > 4 and not pf._rectilinear([(round(x), round(y)) for x, y in gg]):
                gg = pmap.simplify_ring(gg, float(t if t <= 2 else 3))
            u_ = pf._clean([(int(round(x / q)), int(round(y / q))) for x, y in gg])
            if u_ and abs(pmap.ring_area(u_)) * q * q >= 6:
                recs[t - 1].append((k, j, i, u_, int(round(min(h, 400))), nm))
    q4 = pf.QUANT[3]
    for (k, i, j), boxes in sorted(fronts.items()):
        g = grids[k]
        f = g.fb[g.blocks[(i, j)]]
        bx = (g.U(f[0]), g.V(f[1]), g.U(f[2]), g.V(f[3])) if f[4] and (i, j) == (f[0], f[1]) else (g.U(i), g.V(j), g.U(i + 1), g.V(j + 1))
        for r in pf.block_fronts(boxes, *bx, INSET):
            u_ = pf._clean([(int(round(r[0] / q4)), int(round(r[1] / q4))), (int(round(r[2] / q4)), int(round(r[1] / q4))),
                            (int(round(r[2] / q4)), int(round(r[3] / q4))), (int(round(r[0] / q4)), int(round(r[3] / q4)))])
            if u_:
                recs[3].append((k, j, i, u_, 0, ""))
    doms = [[round(math.degrees(g.a), 4), round(g.o[0], 2), round(g.o[1], 2)] for g in grids] + [[0.0, 0.0, 0.0]]
    return doms, recs


def _extent(rings):
    xs = [v for r in rings for v in r[0::2]]
    ys = [v for r in rings for v in r[1::2]]
    return max(xs) + 10, max(ys) + 10
