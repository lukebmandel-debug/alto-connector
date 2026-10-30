"""Manhattan's own layout (the NYC preset, map["layout"] == "manhattan"): the Commissioners' Grid, drawn by Philadelphia's
rules (Luke, 2026-10-20, "Direction A") instead of the generic engine v2, which read Manhattan badly (39 columns where the
island has 18 avenues, downtown as six overlapping free tangles, rivers 5-8x Philadelphia's, far banks as floating
islands).

    root     the avenues (a fixed list, west to east) x every numbered street, Houston St to the box's north edge; every
             block the same long 2.6 : 1 rectangle, Manhattan's own block shape. Broadway is the one diagonal.
    village  west of 6th Ave between 14th St and Houston St: its own even grid at its own real angle, hinged on 6th Ave,
             14th St and Houston St (Philadelphia's angled seams).
    lower    below Houston St to the Battery: its own even grid at Broadway's angle, its lines the real streets in their
             real order.
    shore    the island's real shoreline (the water polygons, piers taken off), carried through the root's mapping, so
             every domain shares one smooth outline; cut blocks along it.
    water    the Hudson and the East River as even bands along that shore, one body with the harbour; nothing north of the
             box's edge (Manhattan goes on). Islands in the water (Roosevelt, Governors) are drawn small inside it.
    far      New Jersey, Brooklyn and Queens are not drawn as streets: a faint grid that fades out (palace_manhattan_js),
             the East River bridges crossing to it, and the boroughs' names.

build() returns the map dict the page draws, with the same keys city_engine.build() returns (tiles, edges, tq, te,
streets, doms, blocks, ...), so palace.py, the transit snap, the fill-in and placement read it like any v2 city.
Pure: no I/O. Every other city is untouched (palace_grid.grid() only comes here for this layout)."""
from __future__ import annotations

import math
import re

from .city_lattice import Lattice, emit, inside as ring_inside, centroid, seg_in_poly, clip_convex, flat, landmark
from .city_spec import LayoutSpec, Child
from .city_types import Domain
from .palace_grid import Mapping, norm, _pairs

LAYOUT = "manhattan"
CWM, CHM = 390, 150            # one block: Manhattan's long block, 2.6 : 1 (page px)
LOTS_X = 3                     # lots along each long front of a root block (three row houses, not two squat ones)
OX, OY = 2200, 260             # the root lattice's page origin (room for the Hudson and the far bank west of it)
BAND_W, BAND_E = 330, 250      # the Hudson's and the East River's bands (page px; Philadelphia's Delaware is 230)
CELL = 25.0                    # m: the land raster
PIER = 3                       # cells: an opening this wide takes the piers off the shore
GHOST_W = 1300                 # page px of faint far-bank grid beyond each band
SHORE_M = 160.0                # m: the shore lies at most this far past the island's own streets

# the avenues, west to east: (label, OSM names, [(from street number northwards, label)])
AVENUES = [
    ("12th Avenue", ("12th Avenue", "Riverside Drive"), [(66, "Riverside Drive")]),
    ("11th Avenue", ("11th Avenue", "West End Avenue"), [(59, "West End Avenue")]),
    ("10th Avenue", ("10th Avenue", "Amsterdam Avenue"), [(59, "Amsterdam Avenue")]),
    ("9th Avenue", ("9th Avenue", "Columbus Avenue"), [(59, "Columbus Avenue")]),
    ("8th Avenue", ("8th Avenue", "Central Park West"), [(59, "Central Park West")]),
    ("7th Avenue", ("7th Avenue",), []),
    ("6th Avenue", ("6th Avenue", "Avenue of the Americas"), []),
    ("5th Avenue", ("5th Avenue",), []),
    ("Madison Avenue", ("Madison Avenue",), []),
    ("4th Avenue", ("Park Avenue", "Park Avenue South", "4th Avenue"), [(17, "Park Avenue South"), (32, "Park Avenue")]),
    ("Lexington Avenue", ("Lexington Avenue",), []),
    ("3rd Avenue", ("3rd Avenue",), []),
    ("2nd Avenue", ("2nd Avenue",), []),
    ("1st Avenue", ("1st Avenue",), []),
    ("Avenue A", ("Avenue A", "York Avenue"), [(59, "York Avenue")]),
    ("Avenue B", ("Avenue B", "East End Avenue"), [(59, "East End Avenue")]),
    ("Avenue C", ("Avenue C",), []),
    ("Avenue D", ("Avenue D",), []),
]
SIXTH = 6                      # the column the Village hinges on
MAJOR_ROWS = {0, 14, 23, 34, 42, 57, 59, 72, 79, 86, 96, 110}
ROW_ALIAS = {"central park south": 59, "cathedral parkway": 110, "central park north": 110,
             "east houston street": 0, "west houston street": 0, "houston street": 0}
_NUM = re.compile(r"^(?:west |east )?(\d+)(?:st|nd|rd|th) street$")
FAR = [("New Jersey", "w", .45), ("Brooklyn", "e", .88), ("Queens", "e", .42)]         # far-bank names: side, height share
BRIDGES = ("Brooklyn Bridge", "Manhattan Bridge", "Williamsburg Bridge", "Ed Koch Queensboro Bridge")
# parks every New Yorker knows that are under palace_parks.AUTO_HA (Luke, 2026-10-22: "I feel like Battery Park is missing")
PARKS = ("Battery Park",)
_HINGES = ("6th Avenue", "Avenue of the Americas", "West 14th Street", "14th Street", "West Houston Street",
           "East Houston Street", "Houston Street")

# the same, as data (city_spec.LayoutSpec): the NYC preset's layout, the first spec; build() reads every value below
# from the spec it is given, so another city of fixed avenues x numbered streets is a new spec, not new code
NYC = LayoutSpec(
    name=LAYOUT, builder="axes", root_axes=tuple((a, tuple(ns), tuple(tuple(r) for r in ren)) for a, ns, ren in AVENUES),
    hinge_axis=AVENUES[SIXTH][0], base_row=0, row_alias=tuple(sorted(ROW_ALIAS.items())),
    major_rows=tuple(sorted(MAJOR_ROWS)),
    children=(Child(region=("west_of", AVENUES[SIXTH][0], 14, 0), hinges=_HINGES, cap=(14, 14)),       # the Village
              Child(region=("south_of", 0), hinges=_HINGES, cap=(26, 30), tip_rows=True)),             # Lower Manhattan
    shore="raster", shore_cell_m=CELL, must_parks=PARKS, fill_budget=150_000,
    river_names=(), far=tuple(FAR), bridges=BRIDGES)


def applies(m) -> bool:
    return (m or {}).get("layout") == LAYOUT


# ── small geometry ──────────────────────────────────────────────────────────
def _segs(p):
    return [(p[i], p[i + 1], p[i + 2], p[i + 3]) for i in range(0, len(p) - 3, 2)]


def _clip_half(poly, axis, val, keep_le):
    """Sutherland-Hodgman against one axis-aligned half-plane."""
    out = []
    n = len(poly)
    for k in range(n):
        a, b = poly[k - 1], poly[k]
        ia = (a[axis] <= val) if keep_le else (a[axis] >= val)
        ib = (b[axis] <= val) if keep_le else (b[axis] >= val)
        if ib:
            if not ia:
                t = (val - a[axis]) / ((b[axis] - a[axis]) or 1e-9)
                out.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
            out.append(b)
        elif ia:
            t = (val - a[axis]) / ((b[axis] - a[axis]) or 1e-9)
            out.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
    return out


def _chaikin(pts, n=2):
    for _ in range(n):
        out = [pts[0]]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            out += [(.75 * x0 + .25 * x1, .75 * y0 + .25 * y1), (.25 * x0 + .75 * x1, .25 * y0 + .75 * y1)]
        out.append(pts[-1])
        pts = out
    return pts


def _smooth(vals, k):
    """A moving median then a moving mean over k samples (the shore: piers and slips off, curves kept)."""
    n = len(vals)
    med = [sorted(vals[max(0, i - k):i + k + 1])[len(vals[max(0, i - k):i + k + 1]) // 2] for i in range(n)]
    return [sum(med[max(0, i - k):i + k + 1]) / len(med[max(0, i - k):i + k + 1]) for i in range(n)]


def _dp(pts, tol):
    if len(pts) < 3:
        return pts
    (ax, ay), (bx, by) = pts[0], pts[-1]
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy) or 1e-9
    k, dmax = 0, -1.0
    for i in range(1, len(pts) - 1):
        d = abs((pts[i][0] - ax) * dy - (pts[i][1] - ay) * dx) / L
        if d > dmax:
            k, dmax = i, d
    if dmax <= tol:
        return [pts[0], pts[-1]]
    return _dp(pts[:k + 1], tol)[:-1] + _dp(pts[k:], tol)


def _wmedian(vals):
    """Length-weighted median of [(value, weight)]."""
    vals = sorted(vals)
    tot = sum(w for _, w in vals) / 2
    acc = 0.0
    for v, w in vals:
        acc += w
        if acc >= tot:
            return v
    return vals[-1][0] if vals else 0.0


class _Turn:
    """Real px -> a frame turned by -th about (cx, cy) (the avenues vertical), and back."""

    def __init__(self, th, cx, cy):
        self.th, self.cx, self.cy = th, cx, cy
        self.c, self.s = math.cos(-th), math.sin(-th)

    def __call__(self, x, y):
        x, y = x - self.cx, y - self.cy
        return (x * self.c - y * self.s + self.cx, x * self.s + y * self.c + self.cy)

    def back(self, u, v):
        u, v = u - self.cx, v - self.cy
        return (u * self.c + v * self.s + self.cx, -u * self.s + v * self.c + self.cy)


def _interp(v, R, G, step_r, step_g):
    """Piecewise linear through the lines' real positions R -> page positions G, the end blocks' scale past them."""
    if v <= R[0]:
        return G[0] - (R[0] - v) * step_g / step_r
    if v >= R[-1]:
        return G[-1] + (v - R[-1]) * step_g / step_r
    lo, hi = 0, len(R) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if R[mid] <= v:
            lo = mid
        else:
            hi = mid
    return G[lo] + (v - R[lo]) / max(1e-9, R[hi] - R[lo]) * (G[hi] - G[lo])


# ── the land ────────────────────────────────────────────────────────────────
class Land:
    """The real map's land on a CELL raster: water polygons filled, the piers opened off, components labelled."""

    def __init__(self, m):
        W, H = m["W"], m["H"]
        self.nx, self.ny = int(W // CELL) + 1, int(H // CELL) + 1
        nx, ny = self.nx, self.ny
        wet = [bytearray(nx) for _ in range(ny)]
        for r in m.get("water", []):
            pts = _pairs(r)
            if len(pts) < 3:
                continue
            ys = [p[1] for p in pts]
            for j in range(max(0, int(min(ys) // CELL)), min(ny, int(max(ys) // CELL) + 1)):
                y = (j + .5) * CELL
                xs = sorted(x0 + (y - y0) * (x1 - x0) / (y1 - y0) for (x0, y0), (x1, y1) in zip(pts, pts[-1:] + pts[:-1])
                            if (y0 > y) != (y1 > y))
                row = wet[j]
                for a, b in zip(xs[::2], xs[1::2]):
                    for i in range(max(0, int(math.ceil(a / CELL - .5))), min(nx, int(math.floor(b / CELL - .5)) + 1)):
                        row[i] = 1
        land = [bytearray(1 - v for v in row) for row in wet]
        self.land = self._open(land, PIER)
        self.comp, self.sizes = self._label(self.land)

    def _open(self, g, k):
        """Erode then dilate by k cells (a square): piers and slips narrower than 2k + 1 cells come off."""
        nx, ny = self.nx, self.ny

        def er(g, val):
            out = [bytearray(nx) for _ in range(ny)]
            for j in range(ny):
                for i in range(nx):
                    ok = val
                    for dj in (-k, 0, k):
                        jj = min(ny - 1, max(0, j + dj))
                        for di in (-k, 0, k):
                            ii = min(nx - 1, max(0, i + di))
                            if (g[jj][ii] == 1) != (val == 1):
                                ok = 1 - val
                                break
                        if ok != val:
                            break
                    out[j][i] = ok
            return out
        return er(er(g, 1), 0)

    def _label(self, g):
        nx, ny = self.nx, self.ny
        comp = [[-1] * nx for _ in range(ny)]
        sizes = []
        for j in range(ny):
            for i in range(nx):
                if g[j][i] and comp[j][i] < 0:
                    cid, n, st = len(sizes), 0, [(i, j)]
                    comp[j][i] = cid
                    while st:
                        a, b = st.pop()
                        n += 1
                        for c, d in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                            if 0 <= c < nx and 0 <= d < ny and g[d][c] and comp[d][c] < 0:
                                comp[d][c] = cid
                                st.append((c, d))
                    sizes.append(n)
        return comp, sizes

    def cid(self, x, y):
        i, j = int(x // CELL), int(y // CELL)
        if 0 <= i < self.nx and 0 <= j < self.ny:
            return self.comp[j][i]
        return -1

    def touches_edge(self, cid):
        nx, ny = self.nx, self.ny
        return any(self.comp[0][i] == cid or self.comp[ny - 1][i] == cid for i in range(nx)) or \
            any(self.comp[j][0] == cid or self.comp[j][nx - 1] == cid for j in range(ny))

    def cells(self, cid):
        return [((i + .5) * CELL, (j + .5) * CELL) for j in range(self.ny) for i in range(self.nx) if self.comp[j][i] == cid]


# ── lines of a domain from the real streets ─────────────────────────────────
def _angle_mode(segs, tr_th):
    """The street angle (degrees, mod 90, in (-45, 45]) that most street length runs at, measured after turning by tr_th."""
    hist = [0.0] * 90
    for x0, y0, x1, y1, _n in segs:
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 8:
            continue
        a = (math.degrees(math.atan2(y1 - y0, x1 - x0)) - math.degrees(tr_th)) % 90
        hist[int(a) % 90] += L
    sm = [sum(hist[(k + d) % 90] for d in range(-3, 4)) for k in range(90)]
    k = max(range(90), key=lambda i: sm[i])
    a = k + .5
    return a - 90 if a > 45 else a


def _pick(segs, tr, tol=18.0, min_v=220.0, min_h=180.0, merge=40.0, cap_v=99, cap_h=99, skip=()):
    """The lattice lines of a domain: named streets running within tol degrees of the frame's axes, each placed at its
    length-weighted median across the axis, in order; lines nearer than `merge` m are one (the longer keeps its name)."""
    acc = {}
    for x0, y0, x1, y1, n in segs:
        if not n or norm(n) in skip:
            continue
        a, b = tr(x0, y0), tr(x1, y1)
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        if L < 5:
            continue
        ang = abs(math.degrees(math.atan2(dy, dx))) % 180
        if ang < tol or ang > 180 - tol:
            fam, pos = "h", (a[1] + b[1]) / 2
        elif abs(ang - 90) < tol:
            fam, pos = "v", (a[0] + b[0]) / 2
        else:
            continue
        e = acc.setdefault((fam, n), [0.0, []])
        e[0] += L
        e[1].append((pos, L))
    out = {}
    for fam, mn, cap in (("v", min_v, cap_v), ("h", min_h, cap_h)):
        ls = sorted((_wmedian(v[1]), v[0], n) for (f, n), v in acc.items() if f == fam and v[0] >= mn)
        merged = []
        for pos, L, n in ls:
            if merged and pos - merged[-1][0] < merge:
                if L > merged[-1][1]:
                    merged[-1] = (pos, L, n)
                continue
            merged.append((pos, L, n))
        while len(merged) > cap:
            k = min(range(len(merged)), key=lambda i: merged[i][1])
            merged.pop(k)
        out[fam] = merged
    return out


# ── the page lattices ───────────────────────────────────────────────────────
class _Lat(Lattice):
    """A lattice clipped by a page ring, minus page rectangles (the root less the Village's notch), its cells cut
    along the shore."""

    def __init__(self, dom, xg, yg, ring, notches=(), cw=CWM, ch=CHM, lm_cells=()):
        super().__init__(dom, xg, yg, cw=cw, ch=ch, lm_cells=lm_cells)
        self.ring = ring
        self.notches = list(notches)
        self.holes = set()                 # cells a park covers: no block, no street through them

    def _sides(self, a, b):
        """The two cells either side of lattice segment ab (page points), or ()."""
        from bisect import bisect_right
        (ax, ay), (bx, by) = self.local(*a), self.local(*b)
        mx, my = (ax + bx) / 2, (ay + by) / 2
        if abs(ax - bx) < 1:
            k = min(range(len(self.xg)), key=lambda q: abs(self.xg[q] - mx))
            j = bisect_right(self.yg, my) - 1
            return ((k - 1, j), (k, j))
        if abs(ay - by) < 1:
            k = min(range(len(self.yg)), key=lambda q: abs(self.yg[q] - my))
            i = bisect_right(self.xg, mx) - 1
            return ((i, k - 1), (i, k))
        return ()

    def _in_notch(self, x, y, tol=1.0):
        return any(x0 + tol < x < x1 - tol and y0 + tol < y < y1 - tol for x0, y0, x1, y1 in self.notches)

    def cell_poly(self, i, j):
        if (i, j) in self.holes:
            return []
        q = self.cell_rect(i, j)
        cx, cy = centroid(q)
        if self._in_notch(cx, cy):
            return []
        return clip_convex(self.ring, q)

    def inside(self, x, y):
        return ring_inside(self.ring, x, y) and not self._in_notch(x, y)

    def seg_in(self, a, b):
        if self.holes:
            sd = self._sides(a, b)
            if sd and all(c in self.holes for c in sd):
                return []
        ivs = seg_in_poly(self.ring, a, b)
        out = []
        for t0, t1 in ivs:
            mx = a[0] + (t0 + t1) / 2 * (b[0] - a[0])
            my = a[1] + (t0 + t1) / 2 * (b[1] - a[1])
            if not self._in_notch(mx, my):
                out.append((t0, t1))
        return out

    def clip_poly(self, poly):
        return clip_convex(self.ring, poly)


class _DomMap:
    """Real px -> page px of one domain: its Mapping (real -> local) then T_d (local -> page)."""

    def __init__(self, loc, a, o):
        self.loc, self.a, self.o = loc, a, o
        r = math.radians(a)
        self._c, self._s = math.cos(r), math.sin(r)

    def page(self, lx, ly):
        return (lx * self._c - ly * self._s + self.o[0], lx * self._s + ly * self._c + self.o[1])

    def __call__(self, x, y):
        return self.page(*self.loc(x, y))


def _numbered(n, alias=None):
    k = (n or "").strip().lower()
    alias = ROW_ALIAS if alias is None else alias
    if k in alias:
        return alias[k]
    mm = _NUM.match(k)
    return int(mm.group(1)) if mm else None


def _row_name(num):
    if num == 0:
        return "Houston Street"
    suf = "th" if 10 <= num % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(num % 10, "th")
    return f"{num}{suf} Street"


# ── build ───────────────────────────────────────────────────────────────────
def build(m, majors=(), diagonals=(), rail_specs=(), lm_specs=(), parks=(), spec=None) -> dict:
    spec = spec or NYC                                             # the layout as data (city_spec.LayoutSpec)
    axes, alias = spec.root_axes, spec.alias()
    kids = {c.region[0]: c for c in spec.children}
    vil_c, low_c = kids.get("west_of"), kids.get("south_of")
    base = spec.base_row
    vtop = vil_c.region[2] if vil_c else None                      # the Village's north row (14th St)
    parks = tuple(parks or ()) + tuple(p for p in spec.must_parks if p not in (parks or ()))
    segs = [(x0, y0, x1, y1, s.get("n") or "") for s in m.get("streets", []) for x0, y0, x1, y1 in _segs(s["p"])]
    land = Land(m)
    # the island: the land component the avenues stand on
    votes = {}
    av_names = {n for _l, ns, _r in axes for n in ns}
    for x0, y0, x1, y1, n in segs:
        if n in av_names:
            c = land.cid((x0 + x1) / 2, (y0 + y1) / 2)
            if c >= 0:
                votes[c] = votes.get(c, 0) + math.hypot(x1 - x0, y1 - y0)
    isl = max(votes, key=votes.get)

    def on(x, y):
        return land.cid(x, y) == isl
    msegs = [s for s in segs if on((s[0] + s[2]) / 2, (s[1] + s[3]) / 2)]

    # 1. the root frame: the avenues' own angle
    av_segs = [s for s in msegs if s[4] in av_names]
    # the avenues' angle mod 90 (real px, y down): an avenue at screen angle phi - 90 (north-north-east) runs vertically
    # once the map is turned by -phi, and the cross streets horizontally
    th = math.radians(_angle_mode(av_segs, 0.0))
    cx, cy = m["W"] / 2, m["H"] / 2
    tr = _Turn(th, cx, cy)
    # columns: each avenue's length-weighted median turned x (its near-vertical pieces only)
    cols = []
    for label, names, ren in axes:
        pos = []
        for x0, y0, x1, y1, n in av_segs:
            if n in names:
                a, b = tr(x0, y0), tr(x1, y1)
                L = math.hypot(b[0] - a[0], b[1] - a[1])
                if L > 5 and abs(b[0] - a[0]) < .3 * L:
                    pos.append(((a[0] + b[0]) / 2, L))
        if sum(w for _, w in pos) > 400:
            cols.append((_wmedian(pos), label, ren))
    cols.sort()
    xr = [c[0] for c in cols]
    six = next((k for k, c in enumerate(cols) if c[1] == spec.hinge_axis), None)
    # rows: every numbered street (east of 6th Ave below 14th St: the Village's own streets carry numbers too)
    rows = {}
    for x0, y0, x1, y1, n in msegs:
        num = _numbered(n, alias)
        if num is None:
            continue
        a, b = tr(x0, y0), tr(x1, y1)
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 5 or abs(b[1] - a[1]) > .3 * L:
            continue
        if vil_c and num < vtop and num != base and six is not None and (a[0] + b[0]) / 2 < xr[six]:
            continue
        rows.setdefault(num, []).append(((a[1] + b[1]) / 2, L, min(a[0], b[0]), max(a[0], b[0])))
    # the box's north edge crosses the grid on a slant (the avenues lean 29 degrees): the grid stops at the last street
    # that still crosses most of the island, so its top is one straight street, never a stair-stepped diagonal
    span = {num: max(t[3] for t in v) - min(t[2] for t in v) for num, v in rows.items()}
    ref = sorted(span[n] for n in span if 60 <= n <= 100) or sorted(span.values())
    ref = ref[len(ref) // 2]
    top_n = 0
    for n in sorted(k for k in span if k > 0):
        if n >= 60 and span[n] < .55 * ref:
            break
        top_n = n
    rows = {n: [(t[0], t[1]) for t in v] for n, v in rows.items() if n <= top_n}
    rws = sorted(((_wmedian(v), num) for num, v in rows.items() if sum(w for _, w in v) > 150), key=lambda t: t[0])
    # keep the longest run where the numbers rise northwards (y falls): a stray piece never reorders the grid
    best = []
    for k in range(len(rws)):
        run = [rws[k]]
        for t in rws[k + 1:]:
            if t[1] < run[-1][1]:
                run.append(t)
        if len(run) > len(best):
            best = run
    rws = best
    if base not in [n for _y, n in rws]:
        raise ValueError("%s: no base row %d" % (spec.name, base))
    rws = [t for t in rws if t[1] >= base]
    yr = [t[0] for t in rws]
    row_num = [t[1] for t in rws]
    xg = [i * CWM for i in range(len(xr))]
    yg = [j * CHM for j in range(len(yr))]
    sx = CWM / ((xr[-1] - xr[0]) / (len(xr) - 1))
    sy = CHM / ((yr[-1] - yr[0]) / (len(yr) - 1))
    loc = Mapping(th, cx, cy, xr, xg, yr, yg)
    for attr, v in (("gv", CWM), ("gh", CHM)):
        setattr(loc, attr, v)

    # the rest of New York (city_boroughs.py, when the set-up fetched it): it reaches west, south and north of the
    # island, so the page's origin moves to leave room for it
    ox, oy, outer = OX, OY, None
    if m.get("outer"):
        try:
            from .city_boroughs import Outer
            outer = Outer(m, tr, xr, yr, xg, yg, CWM, CHM, land, isl)
            ox, oy = max(OX, outer.need[0]), max(OY, outer.need[1])
        except Exception:                                   # noqa: BLE001 — data it cannot read: Manhattan alone, as before
            outer = None

    def rootmap(x, y):                                             # real -> root page, the end blocks' scale past the lines
        u, v = tr(x, y)
        return (_interp(u, xr, xg, xr[1] - xr[0] if u < xr[0] else xr[-1] - xr[-2], CWM) + ox,
                _interp(v, yr, yg, yr[1] - yr[0] if v < yr[0] else yr[-1] - yr[-2], CHM) + oy)
    root_m = _DomMap(loc, 0.0, (ox, oy))
    yH = oy + yg[-1]                                                # Houston St on the page
    ytop = oy
    x6 = ox + xg[six]
    j14 = row_num.index(vtop) if vtop in row_num else None
    y14 = oy + yg[j14] if j14 is not None else yH - (vtop or 0) * CHM

    # 2. the shore: the island's west and east edge every 20 m along the turned frame, piers off, smoothed, on the page
    pts = land.cells(isl)
    tp = [tr(x, y) for x, y in pts]
    vmin, vmax = min(p[1] for p in tp), max(p[1] for p in tp)
    step = 20.0
    nb = int((vmax - vmin) / step) + 1
    lo, hi = [None] * nb, [None] * nb
    for u, v in tp:
        k = int((v - vmin) / step)
        lo[k] = u if lo[k] is None else min(lo[k], u)
        hi[k] = u if hi[k] is None else max(hi[k], u)
    # where the box cuts a river short the land runs on to the next island (the Harlem River, Randall's Island): the shore
    # never lies more than SHORE_M beyond where Manhattan's own streets (avenues, numbered streets, downtown's) end
    slo, shi = [None] * nb, [None] * nb
    for x0, y0, x1, y1, n in msegs:
        if not (n in av_names or _numbered(n, alias) is not None or tr(x0, y0)[1] > yr[-1]):
            continue
        for x, y in ((x0, y0), (x1, y1)):
            u, v = tr(x, y)
            k = int((v - vmin) / step)
            if 0 <= k < nb:
                slo[k] = u if slo[k] is None else min(slo[k], u)
                shi[k] = u if shi[k] is None else max(shi[k], u)
    for k in range(nb):
        near = [q for q in range(max(0, k - 8), min(nb, k + 9)) if slo[q] is not None]
        if lo[k] is not None and near:
            lo[k] = max(lo[k], min(slo[q] for q in near) - SHORE_M)
            hi[k] = min(hi[k], max(shi[q] for q in near) + SHORE_M)
    ks = [k for k in range(nb) if lo[k] is not None and vmin + (k + .5) * step >= yr[0] - CHM * .4 / sy]
    lo_s = _smooth([lo[k] for k in ks], 6)
    hi_s = _smooth([hi[k] for k in ks], 6)
    west, east, shore_real = [], [], []
    for k, a, b in zip(ks, lo_s, hi_s):
        v = vmin + (k + .5) * step
        if k % 6 == 0:
            shore_real += [tr.back(a - CELL / 2, v), tr.back(b + CELL / 2, v)]
        pw = rootmap(*tr.back(a - CELL / 2, v))
        pe = rootmap(*tr.back(b + CELL / 2, v))
        if pw[1] < ytop:
            continue
        west.append(pw)
        east.append(pe)
    west = _dp(west, 6.0)
    east = _dp(east, 6.0)
    # the top: the box's edge (straight across: Manhattan goes on north of it)
    west[0] = (west[0][0], ytop - CHM * .5)
    east[0] = (east[0][0], ytop - CHM * .5)
    tip = [((west[-1][0] + east[-1][0]) / 2, max(west[-1][1], east[-1][1]) + 40)]
    shore = _dp(_chaikin(west + tip + east[::-1], 2), 3.0)          # a ring: down the west side, up the east
    ring = [(round(x, 1), round(y, 1)) for x, y in shore]

    # 3. the domains' page regions
    root_ring = _clip_half(ring, 1, yH + 2, True)
    notch = (-1e6, y14 + 2, x6 - 2, yH - 2)
    vil_ring = _clip_half(_clip_half(_clip_half(ring, 0, x6 - 2, True), 1, y14 + 2, False), 1, yH - 2, True)
    low_ring = _clip_half(ring, 1, yH + 2, False)

    # 4. the Village and Lower Manhattan: their own even grids at their own real angles
    def real_rect(u0, v0, u1, v1):
        return [tr.back(u0, v0), tr.back(u1, v0), tr.back(u1, v1), tr.back(u0, v1)]
    U0, U1 = min(p[0] for p in tp) - 2000, max(p[0] for p in tp) + 2000
    V0, V1 = vmin - 2000, vmax + 2000
    yrH, yr14 = yr[-1], (yr[j14] if j14 is not None else yr[-1] - (vtop or 0) * 80)
    # the real polygons the domains own (no overlap: a point belongs to exactly one)
    polys = {0: [tr.back(U0, V0), tr.back(U1, V0), tr.back(U1, yrH), tr.back(xr[six], yrH), tr.back(xr[six], yr14),
                 tr.back(U0, yr14)],
             1: real_rect(U0, yr14, xr[six], yrH), 2: real_rect(U0, yrH, U1, V1)}
    skip_v = {norm(n) for n in spec.hinge_names()}
    child = {}
    for did, rng, kid in ((1, vil_ring, vil_c), (2, low_ring, low_c)):
        if kid is None or len(rng) < 3:
            continue
        cap = kid.cap
        rp = polys[did]
        dsegs = [s for s in msegs if ring_inside(rp, (s[0] + s[2]) / 2, (s[1] + s[3]) / 2)]
        rel = _angle_mode(dsegs, th)
        rel = max(-kid.clamp, min(kid.clamp, rel)) if kid.angle is None else kid.angle
        thd = th + math.radians(rel)
        trd = _Turn(thd, cx, cy)
        L = _pick(dsegs, trd, cap_v=cap[0], cap_h=cap[1], skip=skip_v)
        lv, lh = L.get("v", []), L.get("h", [])
        if len(lv) < 3 or len(lh) < 3:
            continue
        if kid.tip_rows:
            # the Battery: no street crosses it, so the even spread would squeeze its 400 m south of the last street
            # into the half-block margin; unnamed rows at downtown's own street spacing carry the grid on to the tip
            tipv = max((trd(x, y)[1] for x, y in pts if ring_inside(rp, x, y)), default=lh[-1][0])
            gaps = sorted(b[0] - a[0] for a, b in zip(lh, lh[1:]))
            stp = gaps[len(gaps) // 2]
            lh = lh + [(lh[-1][0] + stp * (k + 1), 0.0, "") for k in range(int((tipv - lh[-1][0]) / stp - .5))]
        dxr, dyr = [t[0] for t in lv], [t[0] for t in lh]
        # graph paper over the whole region: its real lines, in order, spread evenly across the region turned by the
        # domain's angle (half a block of margin at each end), so no land of the region is left without blocks
        r_ = math.radians(rel)
        loc_ring = [(x * math.cos(r_) + y * math.sin(r_), -x * math.sin(r_) + y * math.cos(r_)) for x, y in rng]
        lx0, lx1 = min(p[0] for p in loc_ring), max(p[0] for p in loc_ring)
        ly0, ly1 = min(p[1] for p in loc_ring), max(p[1] for p in loc_ring)
        gv, gh = (lx1 - lx0) / len(dxr), (ly1 - ly0) / len(dyr)
        dxg = [lx0 + gv / 2 + i * gv for i in range(len(dxr))]
        dyg = [ly0 + gh / 2 + j * gh for j in range(len(dyr))]
        dloc = Mapping(thd, cx, cy, dxr, dxg, dyr, dyg)
        dloc.gv, dloc.gh = gv, gh
        # one unnamed line half a block outside the region's box at each end: the blocks between it and the first
        # street are the region's edge blocks, cut by the shore and the seams (the line itself is never inside)
        child[did] = dict(rel=rel, loc=dloc, o=(0.0, 0.0), xg=[dxg[0] - gv] + dxg + [dxg[-1] + gv],
                          yg=[dyg[0] - gh] + dyg + [dyg[-1] + gh], ring=rng,
                          names={"v": [""] + [t[2] for t in lv] + [""], "h": [""] + [t[2] for t in lh] + [""]})

    # 5. emit every domain
    dom_root = Domain(id=0, kind="grid", theta=th, poly=polys[0], a=0.0, o=(ox, oy), mapping=loc, gv=CWM, gh=CHM)
    if lo_s:                                                        # the grid's top edge: Manhattan goes on north of it
        shore_real += [tr.back(lo_s[0] + (hi_s[0] - lo_s[0]) * t / 12, yr[0]) for t in range(13)]
    root_names = {"v": [c[1] for c in cols], "h": [_row_name(n) for n in row_num]}
    maj = {norm(n) for n in majors or ()} | {norm(c[1]) for c in cols} | {norm(_row_name(n)) for n in row_num if n in spec.major_rows}
    lat_root = _Lat(dom_root, xg, yg, root_ring, notches=[notch])
    doms, lats, maps = [dom_root], {0: lat_root}, {0: root_m}
    for did, c in child.items():
        d = Domain(id=did, kind="grid", theta=c["loc"].th, poly=polys[did], a=c["rel"], o=c["o"], mapping=c["loc"],
                   clip=[(round(x, 1), round(y, 1)) for x, y in c["ring"]], gv=c["loc"].gv, gh=c["loc"].gh)
        doms.append(d)
        lats[did] = _Lat(d, c["xg"], c["yg"], c["ring"], cw=c["loc"].gv, ch=c["loc"].gh)
        maps[did] = _DomMap(c["loc"], c["rel"], c["o"])
    landmarks_out, lm_cells = _landmarks(m, doms, lats, maps, lm_specs)      # before the blocks: a landmark's cells are its own
    park_cells = _parks(m, doms, lats, maps, parks, lm_cells)                  # ... and a park's: no block or street through it
    for pk in park_cells:
        did = pk.pop("_dom")
        cs = {(i, j) for i0, j0, i1, j1 in pk["c"] for i in range(i0, i1) for j in range(j0, j1)}
        if len(cs) >= 4:
            lats[did].holes |= cs
    seams = {0: [(x6, y14, x6, yH)], 1: [(x6, y14, x6, yH), (-1e5, y14, x6, y14), (-1e5, yH, x6, yH)], 2: [(-1e5, yH, 1e5, yH)]}
    outs = {}
    for d in doms:
        lat = lats[d.id]
        names = root_names if d.id == 0 else child[d.id]["names"]
        dm = maj if d.id == 0 else {norm(n) for n in majors or ()}
        outs[d.id] = emit(lat, names={k: [norm(n) for n in v] for k, v in names.items()}, majors=dm, root=(d.id == 0),
                          seams=seams[d.id], lots=True)
    return _finish(m, doms, lats, maps, outs, cols, row_num, rootmap, ring, west, east, ytop, yH, land, isl, tr,
                   majors, diagonals, park_cells, landmarks_out, lm_cells, outer=outer, shore_real=shore_real, org=(ox, oy),
                   spec=spec)


def _split_y(p, yc):
    """A polyline cut where it crosses y = yc: (the part south of it, the part north of it), either may be []."""
    pts = _pairs(p)
    s, n = [], []
    for a, b in zip(pts, pts[1:]):
        if (a[1] - yc) * (b[1] - yc) < 0:
            t = (yc - a[1]) / (b[1] - a[1])
            c = (a[0] + t * (b[0] - a[0]), yc)
            (s if a[1] > yc else n).extend([a, c])
            (s if b[1] > yc else n).extend([c, b])
        else:
            (s if (a[1] + b[1]) / 2 > yc else n).extend([a, b])

    def dedup(q):
        out = []
        for v in q:
            if not out or math.hypot(v[0] - out[-1][0], v[1] - out[-1][1]) > .05:
                out.append(v)
        return out
    return dedup(s), dedup(n)


def _finish(m, doms, lats, maps, outs, cols, row_num, rootmap, ring, west, east, ytop, yH, land, isl, tr,
            majors, diagonals, park_cells, landmarks_out, lm_cells, outer=None, shore_real=(), org=(OX, OY), spec=None):
    tiles, edges, tq, te, streets, blocks = [], [], [], [], [], []
    for did in sorted(outs):
        o = outs[did]
        tiles += o["tiles"]; edges += o["edges"]; tq += o["tq"]; te += o["te"]
        streets += o["streets"]
        for b in o["blocks"]:
            b = dict(b)
            cell = b.pop("cell", None)
            if did == 0 and cell:
                b["lots"] = _root_lots(lats[0], *cell) or b["lots"]
            blocks.append(b)
    # renamed stretches of an avenue (10th Ave is Amsterdam Ave north of 59th St)
    lat0 = lats[0]
    y_of = {num: lat0.page(0, lat0.yg[j])[1] for j, num in enumerate(row_num)}
    ren_by = {norm(c[1]): c[2] for c in cols if c[2]}
    out_st = []
    for st in streets:
        rn = ren_by.get(st["n"])
        if not rn:
            out_st.append(st)
            continue
        rest, name = st["p"], st["n"]
        for yc, nm in sorted(((y_of[num], norm(nm)) for num, nm in rn if num in y_of), key=lambda t: -t[0]):
            ys = rest[1::2]                                         # from Houston northwards: south of the cut keeps the name
            if not ys:
                break
            if yc >= max(ys):
                name = nm
                continue
            if yc <= min(ys):
                break
            s_, n_ = _split_y(rest, yc)
            if len(s_) >= 2:
                out_st.append({**st, "n": name, "p": [round(v, 1) for v in flat(s_)]})
            rest, name = [round(v, 1) for v in flat(n_)], nm
        if len(rest) >= 4:
            out_st.append({**st, "n": name, "p": rest})
    streets = out_st
    # Broadway: the one diagonal, through the root (Union Sq, Herald Sq, Times Sq, Columbus Circle), joined to the
    # Lower grid's own Broadway at Houston St
    diag = []
    for dn in diagonals or ():
        real = [s for s in m.get("streets", []) if s.get("n") == dn]
        pts = []
        for s in real:
            for x, y in _pairs(s["p"]):
                u, v = tr(x, y)
                if land.cid(x, y) == isl and v <= lat0.dom.mapping.yr[-1]:
                    pts.append((v, x, y))
        if len(pts) < 10:
            continue
        pts.sort()
        # one point every 60 m along the turned axis: the median of the pieces there (a dual carriageway is one line)
        bins = {}
        for v, x, y in pts:
            bins.setdefault(int(v // 60), []).append(rootmap(x, y))
        line = [(sorted(p[0] for p in q)[len(q) // 2], sorted(p[1] for p in q)[len(q) // 2]) for _k, q in sorted(bins.items())]
        line = _dp(line, 60.0)
        if len(line) < 2:
            continue
        low = [q for s in streets if s["n"] == norm(dn) for q in _pairs(s["p"]) if q[1] >= yH - 5]
        if low:
            line[-1] = (min(low, key=lambda q: q[1])[0], yH)            # meets Lower Manhattan's own Broadway at Houston St
        else:
            line[-1] = (line[-1][0], yH)
        line = [p for p in line if ytop - 1 <= p[1] <= yH + 1]
        st = {"n": norm(dn), "k": 0, "L": 1, "p": flat(line)}
        streets.append(st)
        diag.append(line)
        # a lot under the diagonal is no lot
        for b in blocks:
            b["lots"] = [lt for lt in b["lots"] if min(_pd(lt[0], lt[1], line)) > max(lt[2], lt[3]) / 2 + 14]
        blocks = [b for b in blocks if b["lots"]]
    blocks.sort(key=lambda b: (b["y"], b["x"]))
    for k, b in enumerate(blocks):
        b["id"] = k
    W = int(max(p[0] for p in ring) + BAND_E + GHOST_W + 300)
    H = int(max(p[1] for p in ring) + 2400)
    return _water_and_rest(m, doms, lats, maps, streets, tiles, edges, tq, te, blocks, ring, west, east, ytop, yH,
                           W, H, land, isl, tr, rootmap, cols, row_num, majors, park_cells, landmarks_out, lm_cells,
                           outer=outer, shore_real=shore_real, org=org, spec=spec or NYC)


def _root_lots(lat, i, j):
    """A root block's lots: LOTS_X row houses along each of its two long fronts, square to the block, each kept only
    when it stands wholly inside the block (a block the shore cuts keeps the ones on land)."""
    from .city_lattice import GAP
    poly = lat.cell_poly(i, j)
    if not poly:
        return []
    x0, x1, y0, y1 = lat.xg[i], lat.xg[i + 1], lat.yg[j], lat.yg[j + 1]
    w = (x1 - x0 - (LOTS_X + 1) * GAP) / LOTS_X
    h = (y1 - y0 - 3 * GAP) / 2
    out = []
    for yy in (y0 + GAP + h / 2, y1 - GAP - h / 2):
        for k in range(LOTS_X):
            xx = x0 + GAP + w / 2 + k * (w + GAP)
            corners = [lat.page(xx + sx * (w / 2 + 2), yy + sy * (h / 2 + 2)) for sx in (-1, 1) for sy in (-1, 1)]
            if all(ring_inside(poly, *q) for q in corners):
                out.append(lat.lot_page(xx, yy, w, h))
    return out


def _pd(x, y, line):
    """Distances from (x, y) to each segment of a polyline."""
    out = []
    for (ax, ay), (bx, by) in zip(line, line[1:]):
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy or 1e-9
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
        out.append(math.hypot(ax + t * dx - x, ay + t * dy - y))
    return out or [1e9]


def _offset(line, d):
    """A polyline moved d px sideways (left of travel is negative), corners mitred and smoothed."""
    out = []
    n = len(line)
    for i in range(n):
        a = line[max(0, i - 1)]
        b = line[min(n - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1e-9
        out.append((line[i][0] - dy / L * d, line[i][1] + dx / L * d))
    return out


def _water_and_rest(m, doms, lats, maps, streets, tiles, edges, tq, te, blocks, ring, west, east, ytop, yH, W, H,
                    land, isl, tr, rootmap, cols, row_num, majors, park_cells, landmarks_out, lm_cells, outer=None,
                    shore_real=(), org=(OX, OY), spec=None):
    spec = spec or NYC
    from .city_engine import _dom_out
    from types import SimpleNamespace
    # the water: one body, the Hudson west of the island, the East River east of it, the harbour below its tip;
    # from the box's top edge down (nothing north of it), the far banks beyond it land
    wl = _chaikin(west, 2)
    el_ = _chaikin(east, 2)
    w_out = [(x - BAND_W, y) for x, y in wl]
    e_out = [(x + BAND_E, y) for x, y in el_]
    tipy = max(p[1] for p in ring)
    bot = tipy + 2400
    # below the tip the harbour opens: New Jersey's and Brooklyn's shores run on south, a bay wide between them
    third = [p for p in w_out if p[1] > tipy - (tipy - ytop) / 3]
    xw_ = min(p[0] for p in third) - 250
    xe_ = max(p[0] for p in e_out if p[1] > tipy - (tipy - ytop) / 3) + 250
    w_out = _chaikin([p for p in w_out if p[1] < tipy - 900] + [(xw_, tipy), (xw_ - 150, bot)], 3)
    e_out = _chaikin([p for p in e_out if p[1] < tipy - 900] + [(xe_, tipy), (xe_ + 150, bot)], 3)
    top = ytop - CHM * .5
    sea = [(w_out[0][0], top)] + w_out[1:] + e_out[::-1][:-1] + [(e_out[0][0], top)]
    sea = [(round(x, 1), round(y, 1)) for x, y in _dp(sea, 4.0)]
    # the islands in the water (Roosevelt, Governors): drawn small where they are, inside the water
    isles = []
    for cid, n in enumerate(land.sizes):
        if cid == isl or n * CELL * CELL < 40000 or land.touches_edge(cid):
            continue
        cs = land.cells(cid)
        pg = [rootmap(x, y) for x, y in cs]
        ys = [p[1] for p in pg]
        y0, y1 = min(ys), max(ys)
        if y1 < top:
            continue
        mx = sum(p[0] for p in pg) / len(pg)
        # inside a band: a slim island down its middle
        def side_x(yy, line):
            best = min(line, key=lambda p: abs(p[1] - yy))
            return best[0]
        if y1 <= tipy:
            xe = side_x((y0 + y1) / 2, el_)
            xw = side_x((y0 + y1) / 2, wl)
            if mx > xe:
                cxm, wd = xe + BAND_E / 2, BAND_E * .32
            elif mx < xw:
                cxm, wd = xw - BAND_W / 2, BAND_W * .32
            else:
                continue
            y0, y1 = max(y0, top + 40), y1
            if y1 - y0 < 60:
                continue
            r_ = wd / 2
            isles.append([cxm - r_, y0 + r_, cxm, y0, cxm + r_, y0 + r_, cxm + r_, y1 - r_, cxm, y1, cxm - r_, y1 - r_])
        else:                                                       # in the harbour: its own shape, smoothed
            hull = _hull(pg)
            if len(hull) >= 3:
                isles.append(flat([(round(x, 1), round(y, 1)) for x, y in hull]))
    land_rings = [flat(ring)] + isles
    river = [{"n": "Hudson River", "w": BAND_W, "ch": 1, "p": flat(_offset_side(wl, -BAND_W / 2))},
             {"n": "East River", "w": BAND_E, "ch": 1, "p": flat(_offset_side(el_, BAND_E / 2))}]
    for rv in river:
        rv["p"] = [round(v, 1) for v in rv["p"]]
    # bridges over the East River: the real bridge's landing on the island, straight across the band to the far bank
    for bn in (spec.bridges if outer is None else ()):
        real = [s for s in m.get("streets", []) if (s.get("n") or "").startswith(bn)]
        if not real:
            continue
        on_isl = [rootmap(x, y) for s in real for x, y in _pairs(s["p"]) if land.cid(x, y) == isl]
        if not on_isl:
            continue
        best = max(on_isl, key=lambda p: p[0])                      # where it leaves the island: its eastmost point on it
        xe = min(el_, key=lambda q: abs(q[1] - best[1]))[0]
        y_ = best[1]
        # long enough to land on the far bank and carry its name (a short deck shows only part of it)
        streets.append({"n": norm(bn), "k": 0, "o": 1, "p": [round(xe - 30, 1), round(y_, 1), round(xe + BAND_E + 560, 1), round(y_, 1)]})
    # the root's tables and the rest of the map
    lat0, mp0 = lats[0], maps[0]
    tables = Mapping(mp0.loc.th, mp0.loc.cx, mp0.loc.cy, mp0.loc.xr, [x + mp0.o[0] for x in mp0.loc.xg], mp0.loc.yr,
                     [y + mp0.o[1] for y in mp0.loc.yg]).tables()
    g = {k: v for k, v in m.items() if k not in ("streets", "water", "rivers", "rails", "trails", "stations", "landmarks",
                                                 "parks", "W", "H", "majors", "transit", "far_bank", "outer")}
    majors_n = {norm(s) for s in majors or ()}
    g.update(W=W, H=H, streets=streets, rails=[], trails=[], parks=park_cells, stations=[], landmarks=landmarks_out,
             rivers=[], river=river, water=[], tiles=tiles, edges=edges, tq=tq, te=te,
             majors=sorted(majors_n | {s["n"] for s in streets if s.get("k") == 0 and s.get("n")}),
             grid=tables, cols=[norm(c[1]) for c in cols], rows=[norm(_row_name(n)) for n in row_num])
    g["doms"] = [_dom_out(d, lats[d.id], SimpleNamespace(loc=maps[d.id].loc, a=maps[d.id].a, o=maps[d.id].o), d.id == 0)
                 for d in doms]
    g["seams"] = []
    g["sea"] = [flat(sea)]
    g["land"] = land_rings
    g["ghost"] = _ghost(w_out, e_out, top, org)
    g["far"] = []                                                   # the boroughs' names on their faint banks
    for n, side, share in (spec.far if outer is None else ()):
        y = top + share * (tipy - top)
        line = wl if side == "w" else el_
        x = min(line, key=lambda p: abs(p[1] - y))[0]
        x = x - BAND_W - GHOST_W * .4 if side == "w" else x + BAND_E + GHOST_W * .4
        g["far"].append({"n": n, "x": round(x), "y": round(y), "r": 1})
    if outer is not None:
        def man(x, y):                                              # real -> page on Manhattan's own lattices
            own = [d for d in doms if ring_inside(d.poly, x, y)]
            return maps[(own[0] if own else doms[0]).id](x, y)
        _the_rest(g, outer, org, shore_real, ring, sea, tipy, streets, te, park_cells, man, m.get("streets", ()), spec.bridges)
        W, H = g["W"], g["H"]
    g["blocks"] = blocks
    # transit on the drawn domains
    from .palace_transit import snap as snap_transit
    from .palace_transit_route import drawn_segs
    segs = drawn_segs(tiles, tq, edges, te, streets)
    tr_doms = [(d, lats[d.id]) for d in doms]
    transit = snap_transit(m.get("transit"), None, None, None, W, H, streets=streets, edges_=edges, doms=tr_doms,
                           segs=segs, rivers=river)
    for t_ in transit.pop("ge", []):
        if len(t_) == 5:
            did, a0, b0, a1, b1 = t_
            lat = lats.get(did)
        else:
            a0, b0, a1, b1 = t_
            lat = lat0
        if lat is None:
            continue
        p0, p1 = lat.node(a0, b0), lat.node(a1, b1)
        if abs(lat.a) < 1e-9:
            edges.append([round(min(p0[0], p1[0]), 1), round(min(p0[1], p1[1]), 1), round(max(p0[0], p1[0]), 1),
                          round(max(p0[1], p1[1]), 1)])
        else:
            te.append([round(p0[0], 1), round(p0[1], 1), round(p1[0], 1), round(p1[1], 1)])
    _despike(transit)
    g["transit"] = transit
    from .city_highways import attach as attach_highways
    attach_highways(g, m)
    _clip_hw(g, ring)
    if outer is not None:                                           # the bands only carry the names now (the water is the sea):
        for rv in g["river"]:                                       # none where the band turns ashore above the grid's top
            q = [(rv["p"][k], rv["p"][k + 1]) for k in range(0, len(rv["p"]) - 1, 2) if rv["p"][k + 1] > ytop + 3 * CHM]
            rv["p"] = flat(q) if len(q) >= 6 else rv["p"]
    g["engine"] = {"path": LAYOUT, "domains": len(doms), "cols": len(cols), "rows": len(row_num),
                   "angles": [round(d.a, 2) for d in doms]}
    return g


def _despike(transit):
    """A line snapped across two grids can zigzag where they meet (out along Houston St and back): a sharp turn between
    two short diagonal legs with no stop on them is cut straight. Right-angle turns along the streets are kept."""
    recs = [s_ for s_ in transit.get("stops") or [] if "x" in s_]
    stops = [(s_["x"], s_["y"]) for s_ in recs]

    def axis(a, b):
        d = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 90
        return d < 3 or d > 87
    for L in transit.get("lines") or []:
        out = []
        for fl in L.get("p") or []:
            q = _pairs(fl)
            changed = True
            while changed and len(q) > 2:
                changed = False
                for k in range(1, len(q) - 1):
                    a, b, c = q[k - 1], q[k], q[k + 1]
                    l1, l2 = math.dist(a, b), math.dist(b, c)
                    if l1 < 1 or l2 < 1 or l1 > 900 or l2 > 900 or (axis(a, b) and axis(b, c)):
                        continue
                    cosv = ((a[0] - b[0]) * (c[0] - b[0]) + (a[1] - b[1]) * (c[1] - b[1])) / (l1 * l2)
                    if cosv < math.cos(math.radians(105)) or math.dist(a, c) > .8 * (l1 + l2):
                        continue
                    on = [i for i, st in enumerate(stops) if math.dist(st, a) > 25 and math.dist(st, c) > 25
                          and min(_pd(st[0], st[1], [a, b, c])) < 25]
                    if any(math.dist(stops[i], b) > 25 for i in on):
                        continue                                    # a stop along a leg: the line keeps its way
                    for i in on:                                    # a stop at the spike's tip moves onto the straight line
                        st = stops[i]
                        dx, dy = c[0] - a[0], c[1] - a[1]
                        t_ = max(0.0, min(1.0, ((st[0] - a[0]) * dx + (st[1] - a[1]) * dy) / (dx * dx + dy * dy or 1e-9)))
                        stops[i] = (a[0] + t_ * dx, a[1] + t_ * dy)
                        recs[i]["x"], recs[i]["y"] = round(stops[i][0], 1), round(stops[i][1], 1)
                    q.pop(k)
                    changed = True
                    break
            out.append([round(v, 1) for v in flat(q)])
        L["p"] = out


def _clip_hw(g, ring, tol=90.0):
    """The highways on the island only: a run of a route, a tunnel or a bridge span that leaves the island (the West
    Side Highway carried past the Village's last street, a tunnel's way under the river) is cut where it leaves."""
    def near(x, y):
        return ring_inside(ring, x, y) or min(_pd(x, y, ring + ring[:1])) < tol

    def runs(fl):
        out, cur = [], []
        for x, y in _pairs(fl):
            if near(x, y):
                cur.append((x, y))
            else:
                if len(cur) >= 2:
                    out.append(flat(cur))
                cur = []
        if len(cur) >= 2:
            out.append(flat(cur))
        return out
    hw = g.get("hw") or {}
    keep = []
    for r in hw.get("roads") or []:
        r["p"] = [q for fl in r.get("p") or [] for q in runs(fl)]
        if not r["p"]:
            continue
        for k in ("tn", "br"):
            if r.get(k):
                r[k] = [q for fl in r[k] for q in runs(fl)] if all(isinstance(v, list) for v in r[k]) else r[k]
        if r.get("sh"):
            r["sh"] = [s_ for s_ in r["sh"] if near(s_[0], s_[1])]
        keep.append(r)
    if hw:
        hw["roads"] = keep


def _offset_side(line, d):
    return [(x + d, y) for x, y in line]


def _hull(pts):
    pts = sorted(set((round(x), round(y)) for x, y in pts))
    if len(pts) < 3:
        return pts

    def cr(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def _the_rest(g, outer, o, shore_real, ring, band, tipy, streets, te, park_cells, man=None, mstreets=(), bridges=BRIDGES):
    """The other four boroughs and upper Manhattan, lighter (city_boroughs.Outer): their main roads (trunk and primary
    as named heavy lines, secondary as minor ones, bridges with decks), big parks, borough and neighbourhood names, and
    the real water of the whole city as one shape around them; no faint far-bank grid then."""
    outer.setup(o, shore_real)
    outer.sea_real()
    light = []                                                      # what the full boroughs (city_outer_lattice) may replace
    for (n, c, br), pg in outer.roads_page(man):
        p = [round(v) for q in pg for v in q]
        if c <= 2:
            st = {"n": norm(n) if n else "", "k": 0 if c <= 2 else 1, "p": p}
            if n:
                st["L"] = 1
            if br:
                st["o"] = 1
            streets.append(st)
            if c == 2 and not br:
                light.append(("st", st))
        else:
            te.append(p)
            light.append(("te", p))
    if man is not None:                                             # an East River bridge the outer roads lack (the Manhattan
        from .city_boroughs import _merge                           # Bridge's span): from the island's own streets, each point
        have = {s_["n"] for s_ in streets if s_.get("o")}           # by the mapping that draws its ground
        for bn in bridges:
            if any(h.startswith(norm(bn)) for h in have):
                continue
            ways = [(bn, _pairs(s_["p"])) for s_ in mstreets if (s_.get("n") or "").startswith(bn)]
            for _k, pts in _merge(ways):
                pg = _dp([man(*q) if outer.detailed(*q) else outer(*q) for q in pts], 6.0)
                if len(pg) >= 2:
                    streets.append({"n": norm(bn), "k": 0, "o": 1, "L": 1, "p": [round(v) for q in pg for v in q]})
    park_cells += outer.parks_page()
    g["far"] = outer.names_page(man)
    g["tun"], g["fy"] = outer.crossings_page(man)                 # tunnels and ferries (palace_crossings.py)
    xs = [v for s in streets for v in s["p"][0::2]] + [v for t in te for v in t[0::2]]
    ys = [v for s in streets for v in s["p"][1::2]] + [v for t in te for v in t[1::2]]
    g["W"] = int(max(max(xs), outer.ext[0] + o[0]) + 900)
    g["H"] = int(max(max(ys), outer.ext[1] + o[1]) + 900)
    band_top = _clip_half(band, 1, tipy - 300, True)
    rings = outer.page_sea(g["W"], g["H"], ring, band_top if len(band_top) >= 3 else band)
    g["sea"] = [[round(v) for p in _chaikin(r + r[:1], 1)[:-1] for v in p] for r in rings if len(r) >= 3]
    g["land"] = [flat(ring)] + outer.isles_page()
    g.pop("ghost", None)
    # every street of the other boroughs and upper Manhattan, on the page where it really runs (city_outer_lattice.py)
    from . import city_outer_lattice
    try:
        g["boroughs"] = city_outer_lattice.nyc(g, outer, streets, te, park_cells, light)
    except Exception as e:                                          # noqa: BLE001 — the lighter boroughs stay
        import traceback; g["boroughs"] = {"error": repr(e)[:300], "at": traceback.format_exc()[-900:]}


def _ghost(w_out, e_out, top, o=(OX, OY)):
    """The far banks' faint grid (palace_manhattan_js draws it): the water's outer edge on each side (from the box's top
    edge down past the harbour), the block, the root's origin (the faint grid lines up with the avenues), the fade's width."""
    w = _dp([(w_out[0][0], top)] + list(w_out), 20.0)
    e = _dp([(e_out[0][0], top)] + list(e_out), 20.0)
    return {"w": [round(v, 1) for v in flat(w)], "e": [round(v, 1) for v in flat(e)], "c": [CWM, CHM], "o": [round(o[0], 1), round(o[1], 1)],
            "d": GHOST_W}


def _landmarks(m, doms, lats, maps, lm_specs):
    """Each landmark building on the cells its real footprint covers in the domain it stands in (a tower: one cell)."""
    from .palace_towers import tower_key
    from .palace_skyline import art_hints

    def find(name):
        nl = name.lower()
        for coll in (m.get("landmarks", []), m.get("stations", [])):
            for x in coll:
                if x.get("n", "").lower() == nl:
                    return x
        for coll in (m.get("landmarks", []), m.get("stations", [])):
            for x in coll:
                if nl in x.get("n", "").lower() or x.get("n", "").lower() in nl:
                    return x
        return None

    def owner(x, y):
        own = [d for d in doms if ring_inside(d.poly, x, y)]
        return own[0] if own else doms[0]
    out, cells_by = [], {d.id: set() for d in doms}
    for spec in lm_specs or ():
        f = find(spec.get("name") or "")
        if not f:
            continue
        d = owner(f["x"], f["y"])
        lat, mp = lats[d.id], maps[d.id]
        rings = [q for q in (f.get("r") or []) if q]
        P = [mp.loc(x, y) for q in rings for x, y in _pairs(q)] if rings else [mp.loc(f["x"], f["y"])]
        xg, yg = lat.xg, lat.yg
        nx, ny = len(xg) - 1, len(yg) - 1
        gv, gh = xg[1] - xg[0], yg[1] - yg[0]
        lx0, lx1 = min(p[0] for p in P), max(p[0] for p in P)
        ly0, ly1 = min(p[1] for p in P), max(p[1] for p in P)
        if tower_key(spec.get("name") or "") or not rings:
            a0 = max(0, min(nx - 1, int(((lx0 + lx1) / 2 - xg[0]) // gv)))
            b0 = max(0, min(ny - 1, int(((ly0 + ly1) / 2 - yg[0]) // gh)))
            a1, b1 = a0 + 1, b0 + 1
        else:
            a0 = max(0, int(math.floor((lx0 - xg[0]) / gv + .2))); a1 = min(nx, int(math.ceil((lx1 - xg[0]) / gv - .2)))
            b0 = max(0, int(math.floor((ly0 - yg[0]) / gh + .2))); b1 = min(ny, int(math.ceil((ly1 - yg[0]) / gh - .2)))
            if a1 <= a0:
                a0 = max(0, min(nx - 1, int(((lx0 + lx1) / 2 - xg[0]) // gv))); a1 = a0 + 1
            if b1 <= b0:
                b0 = max(0, min(ny - 1, int(((ly0 + ly1) / 2 - yg[0]) // gh))); b1 = b0 + 1
        cells = {(i, j) for i in range(a0, a1) for j in range(b0, b1)}
        if cells & cells_by[d.id]:                                   # taken: the nearest free cell beside it
            ci, cj = a0, b0
            near_ = sorted(((ci + u, cj + v) for u in (-1, 0, 1) for v in (-1, 0, 1) if 0 <= ci + u < nx and 0 <= cj + v < ny),
                           key=lambda c: abs(c[0] - ci) + abs(c[1] - cj))
            free_ = [c for c in near_ if c not in cells_by[d.id] and lat.cell_poly(*c)]
            if not free_:
                continue
            (a0, b0), = free_[:1]
            a1, b1 = a0 + 1, b0 + 1
            cells = {(a0, b0)}
        if not all(lat.cell_poly(*c) for c in cells):
            continue
        cells_by[d.id] |= cells
        lm = landmark(lat, a0, b0, a1, b1, spec.get("label") or spec["name"], spec.get("page") or "")
        h = art_hints(spec)
        if h:
            lm.update(h)
        out.append(lm)
        lat.lm_cells |= cells
    return out, cells_by


def _parks(m, doms, lats, maps, parks, lm_cells):
    from .palace_parks import pick as pick_parks
    out, taken = [], set()
    for d in doms:
        lat, mp = lats[d.id], maps[d.id]
        mine = []
        for pk in m.get("parks", []):
            rings = [r for r in pk.get("r") or [] if r and len(r) >= 6]
            if not rings or (pk.get("n") or "") in taken:
                continue
            big = max(rings, key=lambda r: len(r))
            cx_ = sum(big[0::2]) / (len(big) // 2)
            cy_ = sum(big[1::2]) / (len(big) // 2)
            if ring_inside(d.poly, cx_, cy_):
                mine.append(pk)
        if not mine:
            continue
        nx_, ny_ = len(lat.xg) - 1, len(lat.yg) - 1
        blocked = set(lm_cells.get(d.id, ())) | {(i, j) for i in range(nx_) for j in range(ny_) if not lat.cell_poly(i, j)}
        for pk in pick_parks(dict(m, parks=mine), mp.loc, lat.xg, lat.yg, parks or (), blocked, None):
            pk["f"] = [round(mp.a, 6), round(mp.o[0], 2), round(mp.o[1], 2), round(lat.xg[0], 2),
                       round(lat.xg[1] - lat.xg[0], 4), len(lat.xg), round(lat.yg[0], 2), round(lat.yg[1] - lat.yg[0], 4),
                       len(lat.yg)]
            pk["_dom"] = d.id
            out.append(pk)
            taken.add(pk["n"])
    return out
