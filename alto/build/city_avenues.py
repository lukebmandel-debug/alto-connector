"""City engine v2, avenues (design section 3): which named through-roads are avenues, what each one is in each domain,
and how an avenue is drawn on graph paper.

- `chains(m, names)`: each street name's real course, as ordered polylines (same-named ways joined end to end; a dual
  carriageway counts once; small gaps are bridged when the next piece carries on the same way).
- `classify(m, domains, majors, diagonals)`: one record per avenue (per chain) with its ordered pieces across domains,
  each a `lattice` line of its domain (it runs along the domain's axes), a `seam` (it runs along the boundary of two
  domains) or a `diagonal` (it cuts across the domain's lattice); `free`/`void` outside the grid domains.
- `octi_path(...)`: the best path of at most 3 runs (2 bends) along the domain's axes or at 45 degrees between lattice
  nodes near an avenue's ends, fitted to the avenue's real course.
- `draw(recs, domains, nodes)`: the page polylines of the diagonal pieces (with LEAD turns into the streets they join;
  pieces of one avenue meet at a seam node with one rounded bend), `{"n", "k": 0, "d": 1, "p", "dom"}`.
- `name_lines(...)`: lattice lines named by vote of the real streets running along them (lifted from palace_grid 1.9.78's
  tilted-district naming and generalised: any domain, any frame, a name per real span).
- `labels(streets)`: label anchors on major lines (design 3.5).

Pure: no network, no globals touched. Real coordinates are build_map px (x east, y south); page coordinates are the
grid's px. A domain's page transform is a rotation by `a` degrees plus the translation `o` (city_types.Domain).
"""
from __future__ import annotations

import heapq
import math
import re

from .palace_grid import CW, CH, LEAD, norm, numbered, _dp, _inside

AV_SUFFIX = re.compile(r"\b(Avenue|Ave|Boulevard|Blvd|Pike|Road|Rd|Parkway|Pkwy|Drive|Dr|Way|Highway)\.?$", re.I)
NOT_AVENUE = re.compile(r"(Expressway|Interstate|Freeway|Turnpike|Tunnel|Ramp|Exit|Bridge|^I-|^US \d|^Route )", re.I)
MIN_KM = 1200.0          # px of chain (1 px = 1 m at scale 1) before a road can be an avenue
JOIN = 25.0              # same-named way ends this close are one street
GAP = 250.0              # a gap this long between pieces that carry on the same way is bridged
AXIS_DEG = 8.0           # a stretch within this of a domain axis runs along the lattice
LATTICE_FRAC = 0.70
SEAM_FRAC = 0.60
SEAM_PX = 90.0
BEND_PX = 40.0           # cost of one bend, page px (design 3.2)
ORDER_PX = 80.0           # cost of crossing two lattice lines in the other order than the avenue really does (city_report.c_order)
ORDER_TIE = 0.25          # rows: two real crossings this close are one intersection (no order between them)
PROBES = [(math.cos(k * math.pi / 4), math.sin(k * math.pi / 4)) for k in range(8)]


# ── small geometry ─────────────────────────────────────────────────────────
def _pairs(flat):
    return [(flat[i], flat[i + 1]) for i in range(0, len(flat) - 1, 2)]


def _flat(pts):
    return [round(v, 1) for q in pts for v in q]


def plen(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def segd(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy or 1e-12
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(a[0] + t * dx - p[0], a[1] + t * dy - p[1])


class PolyIndex:
    """A polyline's segments in a bucket grid: poly_d(p, index) gives exactly poly_d(p, pts), fast for long chains."""

    def __init__(self, pts, cell=120.0):
        self.pts, self.cell, self.b = list(pts), cell, {}
        for a, b in zip(self.pts, self.pts[1:]):
            i0, i1 = sorted((int(a[0] // cell), int(b[0] // cell)))
            j0, j1 = sorted((int(a[1] // cell), int(b[1] // cell)))
            for i in range(i0, i1 + 1):
                for j in range(j0, j1 + 1):
                    self.b.setdefault((i, j), []).append((a, b))
        xs = [q[0] for q in self.pts]; ys = [q[1] for q in self.pts]
        self.box = (min(xs) - 2 * cell, min(ys) - 2 * cell, max(xs) + 2 * cell, max(ys) + 2 * cell) if xs else (0, 0, 0, 0)
        self.rmax = int(max(self.box[2] - self.box[0], self.box[3] - self.box[1]) // cell) + 2

    def _brute(self, p):
        return min(segd(p, a, b) for a, b in zip(self.pts, self.pts[1:]))

    def dist(self, p, limit=None):
        """Exact distance to the polyline; with `limit`, any value >= limit when the polyline is farther than that."""
        if len(self.pts) == 1:
            return math.dist(p, self.pts[0])
        x0, y0, x1, y1 = self.box
        if not (x0 <= p[0] <= x1 and y0 <= p[1] <= y1):
            if limit is not None and (max(x0 - p[0], p[0] - x1, 0) > limit or max(y0 - p[1], p[1] - y1, 0) > limit):
                return limit
            return self._brute(p)
        c = self.cell
        ci, cj = int(p[0] // c), int(p[1] // c)
        best = None
        for r in range(self.rmax + 1):
            for i in range(ci - r, ci + r + 1):
                for j in (range(cj - r, cj + r + 1) if i in (ci - r, ci + r) else (cj - r, cj + r)):
                    for a, b in self.b.get((i, j), ()):
                        d = segd(p, a, b)
                        if best is None or d < best:
                            best = d
            # every segment not yet seen is more than r * cell away
            if best is not None and best <= r * c:
                return best
            if limit is not None and r * c > limit:
                return limit if best is None else min(best, limit)
        return self._brute(p)


def poly_d(p, pts):
    """Distance from p to a polyline."""
    if isinstance(pts, PolyIndex):
        return pts.dist(p)
    if len(pts) == 1:
        return math.dist(p, pts[0])
    return min(segd(p, a, b) for a, b in zip(pts, pts[1:]))


def ring_d(p, ring):
    return min(segd(p, ring[i], ring[(i + 1) % len(ring)]) for i in range(len(ring)))


def resample(pts, step):
    """Points every `step` along a polyline (ends kept), with the direction (rad) of the segment each lies on."""
    out = []
    if len(pts) < 2:
        return [(pts[0][0], pts[0][1], 0.0)] if pts else []
    acc = 0.0
    for a, b in zip(pts, pts[1:]):
        L = math.dist(a, b)
        if L <= 0:
            continue
        th = math.atan2(b[1] - a[1], b[0] - a[0])
        t = acc
        while t < L:
            out.append((a[0] + (b[0] - a[0]) * t / L, a[1] + (b[1] - a[1]) * t / L, th))
            t += step
        acc = t - L
    a, b = pts[-2], pts[-1]
    out.append((b[0], b[1], math.atan2(b[1] - a[1], b[0] - a[0])))
    return out


def adiff(a, b, period=math.pi):
    """|a - b| folded into [0, period/2]."""
    d = (a - b) % period
    return min(d, period - d)


# ── chains: each name's real course ────────────────────────────────────────
def _ways(m, names):
    w = {}
    for st in m.get("streets", []):
        if st.get("t") or not st.get("n"):
            continue
        n = norm(st["n"])
        if names is not None and n not in names:
            continue
        P = _pairs(st["p"])
        if len(P) >= 2 and plen(P) > 1:
            w.setdefault(n, []).append((P, st.get("k", 9)))
    return w


def _longest_path(ways):
    """ways: [pts]. Endpoints within JOIN are one node. -> the longest simple path (double sweep) as a polyline."""
    nodes = []

    def node(p):
        for i, q in enumerate(nodes):
            if math.dist(p, q) <= JOIN:
                return i
        nodes.append(p)
        return len(nodes) - 1
    adj = {}
    for wi, P in enumerate(ways):
        a, b = node(P[0]), node(P[-1])
        L = plen(P)
        adj.setdefault(a, []).append((b, L, wi, False))
        adj.setdefault(b, []).append((a, L, wi, True))

    def sweep(s):
        dist, prev = {s: 0.0}, {}
        pq = [(0.0, s)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist[u]:
                continue
            for v, L, wi, rev in adj.get(u, []):
                if d + L < dist.get(v, 1e18):
                    dist[v] = d + L; prev[v] = (u, wi, rev)
                    heapq.heappush(pq, (d + L, v))
        far = max(dist, key=dist.get)
        return far, dist, prev
    comps, seen = [], set()
    for s in adj:
        if s in seen:
            continue
        a, dist, _ = sweep(s)
        seen |= set(dist)
        b, dist2, prev = sweep(a)
        path, v = [], b
        while v != a:
            u, wi, rev = prev[v]
            P = ways[wi]
            seg = P if not rev else P[::-1]     # walking u -> v: P runs u->v when not reversed in adj of u
            path = list(seg) + path[1:] if path else list(seg)
            v = u
        comps.append(path if path else ways[next(iter(adj[s]))[2]])
    return comps


def _dir_end(pts, at_end, d=120.0):
    """Unit direction of the polyline at an end, pointing outwards."""
    seq = pts[::-1] if at_end else pts
    p0 = seq[0]
    acc, q = 0.0, seq[-1]
    for a, b in zip(seq, seq[1:]):
        acc += math.dist(a, b)
        if acc >= d:
            q = b
            break
    vx, vy = p0[0] - q[0], p0[1] - q[1]
    L = math.hypot(vx, vy) or 1.0
    return (vx / L, vy / L)


def _dup(a, b, tol=60.0):
    """Share of a's samples within tol of b (a parallel carriageway, or a repeat)."""
    S = resample(a, 40)
    return sum(1 for x, y, _ in S if poly_d((x, y), b) <= tol) / max(1, len(S))


def _one_way(P, back=0.5):
    """A path that goes out and comes back (the two carriageways of a divided road joined at both ends, the
    Benjamin Franklin Parkway's loop round Logan Circle): cut at its far point, keeping the leg out. A path whose end
    is less than `back` of its far point's distance from its start comes back."""
    if len(P) < 3:
        return P
    k = max(range(len(P)), key=lambda i: (P[i][0] - P[0][0]) ** 2 + (P[i][1] - P[0][1]) ** 2)
    far = math.dist(P[k], P[0])
    if 0 < k < len(P) - 1 and far > 0 and math.dist(P[-1], P[0]) < back * far:
        return P[:k + 1]
    return P


def chains(m, names=None, gap=GAP):
    """{name: [polyline, ...]} each name's real course, longest first. names: a set of norm() names, or None (all)."""
    out = {}
    for n, ws in _ways(m, names).items():
        paths = sorted((_one_way(P) for P in _longest_path([P for P, _ in ws])), key=plen, reverse=True)
        acc = []
        for P in paths:
            if any(_dup(P, Q) > .6 for Q in acc):
                continue
            acc.append(P)
        changed = True
        while changed and len(acc) > 1:
            changed = False
            best = None
            for i in range(len(acc)):
                for j in range(len(acc)):
                    if i == j:
                        continue
                    A, B = acc[i], acc[j]
                    for ea in (True, False):          # an end of A
                        for sb in (True, False):      # the start (False) or end (True) of B
                            pa = A[-1] if ea else A[0]
                            pb = B[-1] if sb else B[0]
                            g = math.dist(pa, pb)
                            if g > gap:
                                continue
                            da, db = _dir_end(A, ea), _dir_end(B, sb)
                            # B carries on the way A goes: A's outward direction is against B's outward one
                            if da[0] * db[0] + da[1] * db[1] > -0.5:
                                continue
                            if g > 30 and ((pb[0] - pa[0]) * da[0] + (pb[1] - pa[1]) * da[1]) < .5 * g:
                                continue
                            if best is None or g < best[0]:
                                best = (g, i, j, ea, sb)
            if best:
                _, i, j, ea, sb = best
                A, B = acc[i], acc[j]
                A2 = A if ea else A[::-1]
                B2 = B[::-1] if sb else B
                acc = [c for k, c in enumerate(acc) if k not in (i, j)] + [A2 + B2]
                changed = True
        out[n] = sorted(acc, key=plen, reverse=True)
    return out


# ── domains ────────────────────────────────────────────────────────────────
def _dget(d, k, default=None):
    return d.get(k, default) if isinstance(d, dict) else getattr(d, k, default)


def area(ring):
    return abs(sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(ring, ring[1:] + ring[:1]))) / 2


def dom_finder(domains):
    """-> f(x, y) -> domain id or None. Smaller domains win (they sit inside the root's ring)."""
    ds = sorted(((area(list(map(tuple, _dget(d, "poly")))), _dget(d, "id"), list(map(tuple, _dget(d, "poly"))))
                 for d in domains if _dget(d, "poly")), key=lambda t: t[0])

    def f(x, y):
        for _, i, ring in ds:
            if _inside((x, y), [ring]):
                return i
        return None
    return f


def candidates(m, majors=(), diagonals=()):
    """Names that can be avenues (design 3.1). Motorways and expressways are not avenues unless forced (diagonals):
    they are drawn by the transit/highway layer, and a 'diagonal' expressway would cut the graph paper apart."""
    maj = {norm(x) for x in majors}
    dia = {norm(x) for x in diagonals}
    out = set(dia)
    for st in m.get("streets", []):
        if st.get("t") or not st.get("n"):
            continue
        n, k = norm(st["n"]), st.get("k", 9)
        if NOT_AVENUE.search(n) or k == 0:
            continue
        if (1 <= k <= 2) or (k <= 3 and AV_SUFFIX.search(n)) or n in maj:
            out.add(n)
    return out


def classify(m, domains, majors=(), diagonals=(), min_len=MIN_KM, scale=None):
    """-> [{"n", "len", "pieces": [{"dom", "kind", "frac", "fam", "pts", "len", "seam"?}], "forced"}] for every avenue.

    kind: "lattice" (>= 70% of the piece within 8 degrees of its domain's axes; fam "h" or "v" says which axis),
    "seam" (the whole avenue lies >= 60% within 90 px of a boundary between two grid domains; seam = (a, b)),
    "diagonal", "free" (in a free domain) or "void" (in no domain). Pieces are in the avenue's order."""
    sc = scale if scale is not None else (m.get("scale") or 1.0)
    dia = {norm(x) for x in diagonals}
    names = candidates(m, majors, diagonals)
    which = dom_finder(domains)
    info = {_dget(d, "id"): d for d in domains}
    rings = {i: list(map(tuple, _dget(d, "poly"))) for i, d in info.items() if _dget(d, "poly")}
    grid_ids = {i for i, d in info.items() if _dget(d, "kind", "grid") == "grid"}
    root_id = max(rings, key=lambda i: area(rings[i])) if rings else None
    inner = [i for i in rings if i != root_id]           # the root's ring is the map's edge, never a seam
    out = []
    for n, cs in chains(m, names).items():
        for ci, P in enumerate(cs):
            L = plen(P)
            if L < min_len * sc:
                continue
            S = resample(P, 20.0)
            lab = []
            for x, y, th in S:
                d = which(x, y)
                pair = None
                if d is not None and d in grid_ids and inner and \
                        min(ring_d((x, y), rings[o]) for o in inner) <= SEAM_PX * sc:
                    # on a boundary between two grid domains: another grid domain is right across
                    r_ = (SEAM_PX + 30) * sc
                    for ux, uy in PROBES:
                        o = which(x + ux * r_, y + uy * r_)
                        if o is not None and o != d and o in grid_ids:
                            pair = tuple(sorted((d, o)))
                            break
                lab.append((d, pair, th))
            seam_share = sum(1 for _, p, _ in lab if p) / max(1, len(lab))
            seam_on = seam_share >= SEAM_FRAC and n not in dia
            keys = [("seam", p) if (seam_on and p) else ("dom", d) for d, p, _ in lab]
            # runs of one label; runs shorter than 600 px take their neighbour's label
            runs = []
            for i, k in enumerate(keys):
                if runs and runs[-1][0] == k:
                    runs[-1][2] = i
                else:
                    runs.append([k, i, i])
            changed = True
            while changed and len(runs) > 1:
                changed = False
                for r in range(len(runs)):
                    k, a, b = runs[r]
                    if (b - a + 1) * 20 < 600:
                        nb = runs[r - 1] if r > 0 else runs[r + 1]
                        if r > 0 and r + 1 < len(runs) and (runs[r + 1][2] - runs[r + 1][1]) > (runs[r - 1][2] - runs[r - 1][1]):
                            nb = runs[r + 1]
                        runs[r][0] = nb[0]
                        merged = []
                        for q in runs:
                            if merged and merged[-1][0] == q[0]:
                                merged[-1][2] = q[2]
                            else:
                                merged.append(list(q))
                        runs = merged
                        changed = True
                        break
            pieces = []
            for (kind, key), a, b in runs:
                pts = [(x, y) for x, y, _ in S[a:b + 1]]
                if len(pts) < 2:
                    continue
                pl = plen(pts)
                if kind == "seam":
                    pieces.append({"dom": key[0], "kind": "seam", "seam": key, "pts": pts, "len": round(pl), "frac": None})
                    continue
                d = key
                if d is None:
                    pieces.append({"dom": None, "kind": "void", "pts": pts, "len": round(pl), "frac": None})
                    continue
                dk = _dget(info[d], "kind", "grid")
                if dk != "grid":
                    pieces.append({"dom": d, "kind": "free", "pts": pts, "len": round(pl), "frac": None})
                    continue
                th0 = _dget(info[d], "theta", 0.0)
                fh = sum(1 for _, _, th in S[a:b + 1] if adiff(th, th0) <= math.radians(AXIS_DEG))
                fv = sum(1 for _, _, th in S[a:b + 1] if adiff(th, th0 + math.pi / 2) <= math.radians(AXIS_DEG))
                tot = b - a + 1
                frac = (fh + fv) / tot
                kind2 = "lattice" if frac >= LATTICE_FRAC else "diagonal"
                if n in dia and frac < 0.9:
                    kind2 = "diagonal"
                pc = {"dom": d, "kind": kind2, "pts": pts, "len": round(pl), "frac": round(frac, 2)}
                if kind2 == "lattice":
                    pc["fam"] = "h" if fh >= fv else "v"
                pieces.append(pc)
            out.append({"n": n, "chain": ci, "len": round(L), "forced": n in dia, "seam_share": round(seam_share, 2),
                        "pieces": pieces})
    out.sort(key=lambda r: -r["len"])
    return out


# ── page transforms ────────────────────────────────────────────────────────
def to_page(dom, p):
    a = math.radians(_dget(dom, "a", 0.0) or 0.0)
    ox, oy = _dget(dom, "o", (0.0, 0.0)) or (0.0, 0.0)
    c, s = math.cos(a), math.sin(a)
    return (ox + p[0] * c - p[1] * s, oy + p[0] * s + p[1] * c)


def to_local(dom, p):
    a = math.radians(_dget(dom, "a", 0.0) or 0.0)
    ox, oy = _dget(dom, "o", (0.0, 0.0)) or (0.0, 0.0)
    c, s = math.cos(a), math.sin(a)
    x, y = p[0] - ox, p[1] - oy
    return (x * c + y * s, -x * s + y * c)


# ── the octilinear path ────────────────────────────────────────────────────
def dirs8(mode="page45", cw=CW, ch=CH):
    """The 8 run directions. page45: axes and true 45 degrees (Luke's rule). node: the lattice diagonal (|di| = |dj|),
    which passes through every node but is atan(CH/CW) = 35.3 degrees on the page for 240x170 blocks."""
    if mode == "node":
        L = math.hypot(cw, ch)
        d = (cw / L, ch / L)
    else:
        d = (math.sqrt(.5), math.sqrt(.5))
    return [(1, 0), (0, 1), (-1, 0), (0, -1), (d[0], d[1]), (-d[0], d[1]), (-d[0], -d[1]), (d[0], -d[1])]


def _solve(u, v, D):
    """l1, l2 with l1 u + l2 v = D, or None."""
    det = u[0] * v[1] - u[1] * v[0]
    if abs(det) < 1e-9:
        return None
    l1 = (D[0] * v[1] - D[1] * v[0]) / det
    l2 = (u[0] * D[1] - u[1] * D[0]) / det
    return l1, l2


def shared(path, avoid, tol=3.0):
    """Length of path that runs along (collinear with, on top of) the segments in avoid."""
    tot = 0.0
    for a, b in zip(path, path[1:]):
        L = math.dist(a, b)
        if L < 1:
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        bx0, bx1 = min(a[0], b[0]) - tol, max(a[0], b[0]) + tol
        by0, by1 = min(a[1], b[1]) - tol, max(a[1], b[1]) + tol
        for c, d in avoid:
            if max(c[0], d[0]) < bx0 or min(c[0], d[0]) > bx1 or max(c[1], d[1]) < by0 or min(c[1], d[1]) > by1:
                continue                                  # (exact: such a segment is farther than tol everywhere)
            if segd(c, a, b) > tol and segd(d, a, b) > tol and segd(a, c, d) > tol and segd(b, c, d) > tol:
                continue
            if abs((c[0] - a[0]) * uy - (c[1] - a[1]) * ux) > tol or abs((d[0] - a[0]) * uy - (d[1] - a[1]) * ux) > tol:
                continue
            t0, t1 = sorted(((c[0] - a[0]) * ux + (c[1] - a[1]) * uy, (d[0] - a[0]) * ux + (d[1] - a[1]) * uy))
            tot += max(0.0, min(L, t1) - max(0.0, t0))
    return tot


def _cost(path, S, back, bound=None):
    """Mean distance of the chain samples to the path, and of the path's samples to the chain (both ways, so a path
    cannot cut a corner the avenue really turns, nor wander where it never goes). bound: stop early (returning a value
    >= bound) once the cost is sure to reach it (the sums only grow, so the pruning is exact)."""
    if bound is not None:
        lim = 2 * bound * len(S)
        d1 = 0.0
        for p in S:
            d1 += poly_d(p, path)
            if d1 >= lim:
                return bound
        d1 /= len(S)
        Q = [(x, y) for x, y, _ in resample(path, max(20.0, plen(path) / 30))]
        lim2 = (2 * bound - d1) * max(1, len(Q))
        d2 = 0.0
        for q in Q:
            d2 += poly_d(q, back)
            if d2 >= lim2:
                return bound
        return (d1 + d2 / max(1, len(Q))) / 2
    d1 = sum(poly_d(p, path) for p in S) / len(S)
    Q = [(x, y) for x, y, _ in resample(path, max(20.0, plen(path) / 30))]
    d2 = sum(poly_d(q, back) for q in Q) / max(1, len(Q))
    return (d1 + d2) / 2


def _crossings(path, xs, ys):
    """{("v", x) | ("h", y): arc length along path where it first crosses that lattice column / row}."""
    out, acc = {}, 0.0
    for a, b in zip(path, path[1:]):
        L = math.dist(a, b)
        if L < 1e-9:
            continue
        for o, vals, k in (("v", xs, 0), ("h", ys, 1)):
            lo, hi = sorted((a[k], b[k]))
            if hi - lo < 1e-9:
                continue
            for v in vals:
                if lo < v < hi and (o, v) not in out:
                    out[(o, v)] = acc + (v - a[k]) / (b[k] - a[k]) * L
        acc += L
    return out


def _order_inv(want, got, tie, gap):
    """Pairs of lattice lines the path crosses in the other order than the avenue really does (a real near-tie, under
    `tie` apart, has no order; a drawn near-tie, under `gap`, is not counted either: city_report.c_order's rule)."""
    ks = [k for k in want if k in got]
    return sum(1 for i in range(len(ks)) for j in range(i + 1, len(ks))
               if (want[ks[j]] - want[ks[i]]) * (got[ks[j]] - got[ks[i]]) < 0
               and abs(want[ks[j]] - want[ks[i]]) > tie and abs(got[ks[j]] - got[ks[i]]) > gap)


def octi_path(chain, ends_a, ends_b, bend_px=BEND_PX, mode="page45", min_run=30.0, cw=CW, ch=CH, avoid=(), lines=None):
    """Best path of at most 3 runs from one of ends_a to one of ends_b, fitted to `chain` (page or local px).
    -> {"p": [pts], "bends", "cost", "a", "b"} or None. ends_*: [(x, y)] candidate end nodes (nearest first).
    lines: (xs, ys) the drawn lattice columns and rows: a path that crosses two of them in the other order than the
    chain does costs ORDER_PX more per pair (Ogden Avenue crossed Loomis before Randolph)."""
    if len(chain) < 2:
        return None
    S = [(x, y) for x, y, _ in resample(chain, max(20.0, plen(chain) / 40))]
    back = _dp(chain, 6)
    U = dirs8(mode, cw, ch)
    best = None
    want = _crossings(chain, *lines) if lines else None
    for ia, a in enumerate(ends_a):
        for ib, b in enumerate(ends_b):
            D = (b[0] - a[0], b[1] - a[1])
            Dl = math.hypot(*D)
            if Dl < 1:
                continue
            Dh = (D[0] / Dl, D[1] / Dl)
            fw = [u for u in U if u[0] * Dh[0] + u[1] * Dh[1] > -0.2]
            cands = []
            # 0 bends
            for u in U:
                if abs(u[0] * D[1] - u[1] * D[0]) < 0.5 and u[0] * D[0] + u[1] * D[1] > 0:
                    cands.append([a, b])
            # 1 bend
            for u in fw:
                for v in fw:
                    if u == v:
                        continue
                    s = _solve(u, v, D)
                    if s and s[0] >= min_run and s[1] >= min_run:
                        cands.append([a, (a[0] + u[0] * s[0], a[1] + u[1] * s[0]), b])
            # 2 bends: the first run's length is the free parameter
            for u in fw:
                for v in fw:
                    if v == u:
                        continue
                    for w in fw:
                        if w == v:
                            continue
                        for k in range(1, 17):
                            l1 = Dl * 1.2 * k / 17
                            p1 = (a[0] + u[0] * l1, a[1] + u[1] * l1)
                            s = _solve(v, w, (b[0] - p1[0], b[1] - p1[1]))
                            if not s or s[0] < min_run or s[1] < min_run:
                                continue
                            p2 = (p1[0] + v[0] * s[0], p1[1] + v[1] * s[0])
                            cands.append([a, p1, p2, b])
            for path in cands:
                pen = bend_px * (len(path) - 2) + 0.15 * (ia + ib) * bend_px
                if best is not None and pen >= best["cost"]:
                    continue
                c = _cost(path, S, back, None if best is None else best["cost"] - pen) + pen
                if best is not None and c >= best["cost"]:
                    continue
                if avoid:       # two avenues never share a run (1.9.78 drew Chester and Kingsessing on one row)
                    c += shared(path, avoid) / cw * 3 * bend_px
                if want and (best is None or c < best["cost"]):
                    c += ORDER_PX * _order_inv(want, _crossings(path, *lines), ORDER_TIE * ch, (cw + ch) / 4)
                if best is None or c < best["cost"]:
                    best = {"p": path, "bends": len(path) - 2, "cost": c, "a": ia, "b": ib}
    if best:
        best["cost"] = round(best["cost"], 1)
        best["fit"] = round(_cost(best["p"], S, back), 1)
    return best


def near_nodes(p, nodes, r, k=3):
    """The k drawn lattice nodes nearest p within r (nearest first)."""
    c = sorted((math.dist(p, q), q) for q in nodes if abs(q[0] - p[0]) <= r and abs(q[1] - p[1]) <= r)
    return [q for d, q in c[:k] if d <= r]


def lead(a, nxt, axes=((1, 0), (0, 1))):
    """The point LEAD back along the lattice axis closest to the first run (the avenue turns out of that street)."""
    dx, dy = nxt[0] - a[0], nxt[1] - a[1]
    if abs(dx) >= abs(dy):
        return (a[0] - math.copysign(LEAD, dx or 1), a[1])
    return (a[0], a[1] - math.copysign(LEAD, dy or 1))


def draw_piece(pts_local, nodes, fixed=(None, None), mode="page45", bend_px=BEND_PX, reach=1.5, clip=None, avoid=()):
    """One diagonal piece in its domain's local frame. pts_local: the mapped chain. nodes: drawn lattice nodes (local).
    fixed: a given end (a seam node, local) instead of a lattice node. -> {"p", "j": [ja, jb], "bends", "fit"} or None."""
    r = reach * max(CW, CH)
    ends, joined = [], []
    for e, fx, q in ((0, fixed[0], pts_local[0]), (1, fixed[1], pts_local[-1])):
        if fx is not None:
            ends.append([fx]); joined.append(2)
            continue
        nn = near_nodes(q, nodes, r) or near_nodes(q, nodes, 2 * r, k=1)
        if nn:
            ends.append(nn); joined.append(1)
        else:
            ends.append([q]); joined.append(0)      # past the drawn lattice: it ends on the domain's edge
    xs = sorted({round(q[0], 1) for q in nodes})
    ys = sorted({round(q[1], 1) for q in nodes})
    best = octi_path(pts_local, ends[0], ends[1], bend_px=bend_px, mode=mode, avoid=avoid, lines=(xs, ys) if nodes else None)
    if not best:
        return None
    P = list(best["p"])
    if joined[0] == 1:
        P.insert(0, lead(P[0], P[1]))
    if joined[1] == 1:
        P.append(lead(P[-1], P[-2]))
    return {"p": P, "j": [int(joined[0] > 0), int(joined[1] > 0)], "bends": best["bends"], "fit": best["fit"]}


def seam_node(p_page, seam_segs=None, snaps=None, r=CW):
    """Where an avenue crosses a seam on the page: its mapped crossing point, snapped to the nearest seam point
    (Q_k or line end, `snaps`) within one block, else projected onto the seam."""
    if snaps:
        q = min(snaps, key=lambda s: math.dist(s, p_page))
        if math.dist(q, p_page) <= r:
            return tuple(q)
    if seam_segs:
        best = None
        for x0, y0, x1, y1 in seam_segs:
            dx, dy = x1 - x0, y1 - y0
            L2 = dx * dx + dy * dy or 1e-9
            t = max(0.0, min(1.0, ((p_page[0] - x0) * dx + (p_page[1] - y0) * dy) / L2))
            q = (x0 + t * dx, y0 + t * dy)
            if best is None or math.dist(q, p_page) < math.dist(best, p_page):
                best = q
        return best
    return tuple(p_page)


def draw(recs, domains, nodes, seams=None, mode="page45", bend_px=BEND_PX):
    """Page polylines of every avenue's diagonal pieces. domains: [Domain] with `mapping` (real -> local; a
    palace_grid.Mapping or any callable) and a/o. nodes: {dom id: [(x, y) local drawn lattice nodes]}.
    seams: optional [Seam] (its `segs` and `hinge` points give the seam nodes). Consecutive diagonal pieces in different
    domains meet at one seam node (one rounded bend there, not counted in either piece's 2 bends).
    -> [{"n", "k": 0, "d": 1, "p", "dom", "j", "bends"}] (one street per run of joined pieces)."""
    info = {_dget(d, "id"): d for d in domains}
    seam_by = {}
    for s in seams or []:
        seam_by[tuple(sorted((_dget(s, "a"), _dget(s, "b"))))] = s
    out = []
    taken = {}                     # dom -> local segments of avenues drawn so far (longest avenue first)
    for rec in sorted(recs, key=lambda r: -r.get("len", 0)):
        pcs = rec["pieces"]
        drawn = []
        for i, pc in enumerate(pcs):
            if pc["kind"] != "diagonal" or pc["dom"] not in info:
                continue
            dom = info[pc["dom"]]
            mp = _dget(dom, "mapping")
            loc = [mp(x, y) for x, y in pc["pts"]] if mp else list(pc["pts"])
            fixed = [None, None]
            for side, j in ((0, i - 1), (1, i + 1)):
                if 0 <= j < len(pcs) and pcs[j]["dom"] not in (None, pc["dom"]) and pcs[j]["dom"] in info \
                        and pcs[j]["kind"] in ("diagonal", "lattice", "seam"):
                    other = info[pcs[j]["dom"]]
                    mo = _dget(other, "mapping")
                    # one seam node per boundary: both pieces use the same real point (between their ends)
                    lo_, hi_ = (j, i) if side == 0 else (i, j)
                    e0, e1 = pcs[lo_]["pts"][-1], pcs[hi_]["pts"][0]
                    e_real = ((e0[0] + e1[0]) / 2, (e0[1] + e1[1]) / 2)
                    pa = to_page(dom, mp(*e_real) if mp else e_real)
                    pb = to_page(other, mo(*e_real) if mo else e_real)
                    pa, pb = (pa, pb) if pc["dom"] < pcs[j]["dom"] else (pb, pa)      # the same sum both ways
                    mid = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)
                    s = seam_by.get(tuple(sorted((pc["dom"], pcs[j]["dom"]))))
                    snaps = None
                    if s is not None:
                        snaps = [q for h in (_dget(s, "hinge") or []) for q in (h if isinstance(h, (list, tuple)) and h
                                 and isinstance(h[0], (list, tuple)) else [])]
                    node = seam_node(mid, _dget(s, "segs") if s is not None else None, snaps)
                    fixed[side] = to_local(dom, node)
            res = draw_piece(loc, nodes.get(pc["dom"], []), tuple(fixed), mode=mode, bend_px=bend_px,
                             avoid=taken.get(pc["dom"], ()))
            if not res:
                continue
            taken.setdefault(pc["dom"], []).extend(zip(res["p"][1:-2], res["p"][2:-1]))
            page = [to_page(dom, q) for q in res["p"]]
            drawn.append((i, page, res, pc["dom"]))
        # pieces that meet at a seam node are one street
        merged = []
        for i, page, res, d in drawn:
            if merged and merged[-1]["last"] == i - 1 and math.dist(merged[-1]["pts"][-1], page[0]) < 1.0:
                merged[-1]["pts"] += page[1:]
                merged[-1]["last"] = i
                merged[-1]["bends"].append(res["bends"])
                merged[-1]["j"][1] = res["j"][1]
                continue
            merged.append({"pts": page, "last": i, "bends": [res["bends"]], "dom": d, "j": list(res["j"])})
        for mg in merged:
            out.append({"n": rec["n"], "k": 0, "d": 1, "p": _flat(mg["pts"]), "dom": mg["dom"], "j": mg["j"],
                        "bends": mg["bends"]})
    return out


# ── naming lattice lines by vote ───────────────────────────────────────────
def name_lines(m, theta, to_local_fn, steps, inside=None, majors=(), min_len=500.0, tol=22.5, k_max=3,
               per_span=True):
    """Name a domain's lattice lines after the real streets that run along them (1.9.78's tilted-district vote,
    generalised). theta: the domain's real 'h' axis angle (rad). to_local_fn(x, y) -> (u, v) the real point in the
    lattice's local frame, where an 'h' line lies at v = k * steps['h'] and a 'v' line at u = k * steps['v'].
    inside(x, y): the domain's real region. Each real through-street (k <= k_max, numbered, or a major) votes with its
    length-weighted middle for the line nearest it in its own family.
    -> {(fam, k): [{"n", "lo", "hi", "len"}]} best name first; with per_span, further names that cover other spans of
    the same line (a lattice line with several real names along it)."""
    maj = {norm(x) for x in majors}
    cand = {}
    tol_r = math.radians(tol)
    for st in m.get("streets", []):
        nm = norm(st.get("n") or "")
        if not nm or st.get("t") or (st.get("k", 9) > k_max and not numbered(nm) and nm not in maj):
            continue
        acc = {"h": [0.0, 0.0, 1e18, -1e18], "v": [0.0, 0.0, 1e18, -1e18]}
        P = _pairs(st["p"])
        for (ax, ay), (bx, by) in zip(P, P[1:]):
            mx, my = (ax + bx) / 2, (ay + by) / 2
            if inside is not None and not inside(mx, my):
                continue
            L = math.hypot(bx - ax, by - ay)
            if L < 4:
                continue
            th = math.atan2(by - ay, bx - ax)
            fam = "h" if adiff(th, theta) < tol_r else "v" if adiff(th, theta + math.pi / 2) < tol_r else None
            if not fam:
                continue
            u, v = to_local_fn(mx, my)
            off, along = (v, u) if fam == "h" else (u, v)
            a = acc[fam]
            a[0] += L; a[1] += off * L
            ua, va = to_local_fn(ax, ay)
            ub, vb = to_local_fn(bx, by)
            lo, hi = sorted((ua, ub) if fam == "h" else (va, vb))
            a[2] = min(a[2], lo); a[3] = max(a[3], hi)
        for fam, (tot, so, lo, hi) in acc.items():
            if tot < min_len:
                continue
            k = round((so / tot) / steps[fam])
            rank = (0 if nm in maj else 1 if st.get("k", 9) <= 1 else 2, -tot)
            cand.setdefault((fam, k), {})
            c = cand[(fam, k)].get(nm)
            if c is None:
                cand[(fam, k)][nm] = [rank, lo, hi, tot]
            else:      # one street in several OSM pieces: one vote, its whole extent
                c[0] = min(c[0], rank); c[1] = min(c[1], lo); c[2] = max(c[2], hi); c[3] += tot
                c[0] = (c[0][0], -c[3])
    out = {}
    for key, cs in cand.items():
        ranked = sorted(cs.items(), key=lambda kv: kv[1][0])
        acc_ = []
        for nm, (rank, lo, hi, tot) in ranked:
            if acc_ and not per_span:
                break
            ov = sum(max(0.0, min(hi, a["hi"]) - max(lo, a["lo"])) for a in acc_)
            if acc_ and ov > 0.2 * (hi - lo):
                continue
            acc_.append({"n": nm, "lo": round(lo, 1), "hi": round(hi, 1), "len": round(tot)})
        out[key] = acc_
    return out


# ── labels ─────────────────────────────────────────────────────────────────
def labels(streets, cw=CW, ch=CH, char_w=9.0, h=18.0, every=8):
    """Label anchors for major lines (k == 0, avenues d, lattice majors L): each straight run >= 2 blocks gets a label
    at its middle, rotated to the run and flipped to read left to right, repeated every `every` blocks; greedy by
    importance, dropping a label whose box overlaps one already placed. -> [{"n", "x", "y", "a"}]."""
    runs = []
    for st in streets:
        n = st.get("n")
        if not n or not (st.get("k", 9) == 0 or st.get("d") or st.get("L")) or st.get("o"):
            continue
        P = _pairs(st["p"])
        imp = (0 if st.get("k") == 0 and not st.get("d") else 1 if st.get("d") else 2)
        for a, b in zip(P, P[1:]):
            L = math.dist(a, b)
            if L >= 2 * min(cw, ch):
                runs.append((imp, -L, n, a, b))
    runs.sort()
    placed, boxes = [], []
    for imp, negL, n, a, b in runs:
        L = -negL
        ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        if ang > 90:
            ang -= 180
        elif ang <= -90:
            ang += 180
        w = char_w * len(n)
        if w > L * .9:
            continue
        reps = max(1, int(L // (every * cw)) + 1)
        for r in range(reps):
            t = (r + .5) / reps
            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            c, s = abs(math.cos(math.radians(ang))), abs(math.sin(math.radians(ang)))
            hw, hh = (w * c + h * s) / 2, (w * s + h * c) / 2
            box = (x - hw, y - hh, x + hw, y + hh)
            if any(box[0] < q[2] and q[0] < box[2] and box[1] < q[3] and q[1] < box[3] for q in boxes):
                continue
            boxes.append(box)
            placed.append({"n": n, "x": round(x, 1), "y": round(y, 1), "a": round(ang, 1)})
    return placed
