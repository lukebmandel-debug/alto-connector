"""A trolley runs ON a street. The router here carries a surface line onto the streets the palace's grid actually draws:
the unit grid edges and the clean diagonal avenues (the Parkway, Woodland, Chester ...). Each stop is put on the nearest drawn
street (no street within STOP_R of it: the stop is dropped, it would float), and consecutive stops are joined by the cheapest
way along drawn streets, cheap meaning close to where the real track runs. Nothing here ever draws a street: a track it
returns lies on streets by construction, a diagonal stays one clean diagonal line, and a stop no street supports is gone.

    street_graph(edges, diag)            -> {node: {node: length}}   (nodes are (x, y) rounded to 0.1 px)
    street_graph(segments)               -> the same over drawn segments at ANY angle (tilted domains, seams, polygon tiles)
    drawn_segs(tiles, tq, edges, te, streets) -> [(x0, y0, x1, y1)]: every street piece the page draws
    route(adj, real, stops, ...)         -> (edges, kept stop indices)

The grade-separated lines (subway, el, PATCO, Regional Rail) of a city with several street-grid domains are routed by
octi_route over each domain's own lattice: axis and diagonal steps of that domain (never a square stair-step across a
tilted one), joined where the track crosses a seam (the domain's page clip ring) by a run along the seam.

    CityMap(doms)                        -> real px -> page px through the domain that owns the point
    octi_route(cmap, real, stops, branches) -> (edges, kept, ekey)
"""
from __future__ import annotations

import heapq
import math

CELL = 80.0


def _k(x, y):
    return (round(x + 0.0, 1), round(y + 0.0, 1))


def street_graph(edges, diag=None):
    """With `diag` None, `edges` is any list of drawn segments [x0, y0, x1, y1] at any angle (see _street_graph_any).
    Otherwise (the square grid, unchanged since 1.9.78) edges: unit grid edges [x0, y0, x1, y1] (axis-aligned); diag: [(ax, ay, bx, by)], the clean diagonal avenues.
    A diagonal is cut at every grid edge it crosses (so a trolley can turn off it there) and a grid edge it crosses is
    cut at the crossing."""
    if diag is None:
        return _street_graph_any(edges)
    adj = {}
    cuts = {}                                  # edge index -> [crossing points]

    def link(a, b):
        if a == b:
            return
        d = math.hypot(a[0] - b[0], a[1] - b[1])
        adj.setdefault(a, {})[b] = d
        adj.setdefault(b, {})[a] = d
    dcuts = [[] for _ in diag]
    for di, (ax, ay, bx, by) in enumerate(diag):
        for ei, (x0, y0, x1, y1) in enumerate(edges):
            if y0 == y1:                        # horizontal edge
                if by == ay:
                    continue
                t = (y0 - ay) / (by - ay)
                x = ax + t * (bx - ax)
                if not (0 < t < 1 and min(x0, x1) - 1 <= x <= max(x0, x1) + 1):
                    continue
                pt = (x, y0)
            elif x0 == x1:                      # vertical edge
                if bx == ax:
                    continue
                t = (x0 - ax) / (bx - ax)
                y = ay + t * (by - ay)
                if not (0 < t < 1 and min(y0, y1) - 1 <= y <= max(y0, y1) + 1):
                    continue
                pt = (x0, y)
            else:
                continue
            pk = _k(*pt)
            for end in ((x0, y0), (x1, y1)):    # a crossing at a grid node is that node
                if math.hypot(end[0] - pt[0], end[1] - pt[1]) < 3:
                    pk = _k(*end)
            cuts.setdefault(ei, []).append(pk)
            dcuts[di].append((t, pk))
    for ei, (x0, y0, x1, y1) in enumerate(edges):
        a, b = _k(x0, y0), _k(x1, y1)
        pts = sorted(set(cuts.get(ei, [])), key=lambda p: (p[0] - a[0]) ** 2 + (p[1] - a[1]) ** 2)
        chain = [a] + [p for p in pts if p not in (a, b)] + [b]
        for u, v in zip(chain, chain[1:]):
            link(u, v)
    for di, (ax, ay, bx, by) in enumerate(diag):
        chain = [_k(ax, ay)] + [p for _, p in sorted(dcuts[di])] + [_k(bx, by)]
        keep = [chain[0]]
        for p in chain[1:]:
            if p != keep[-1]:
                keep.append(p)
        for u, v in zip(keep, keep[1:]):
            link(u, v)
    return adj


def _bucket(pts):
    b = {}
    for x, y in pts:
        b.setdefault((int(x // CELL), int(y // CELL)), []).append((x, y))
    return b


def _dev(b, x, y, cap=250.0):
    cx, cy = int(x // CELL), int(y // CELL)
    best = cap
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            for px, py in b.get((cx + i, cy + j), ()):
                d = math.hypot(px - x, py - y)
                if d < best:
                    best = d
    return best


def real_points(ways, mp, step=30.0):
    """The real track (map px polylines) in grid px, sampled every ~step px."""
    out = []
    for w in ways:
        pts = [mp(w[k], w[k + 1]) for k in range(0, len(w) - 1, 2)]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            n = max(1, int(math.hypot(bx - ax, by - ay) // step))
            out += [(ax + (bx - ax) * i / n, ay + (by - ay) * i / n) for i in range(n)]
        if pts:
            out.append(pts[-1])
    return out


def _edge_dev(b, u, v):
    n = max(2, int(math.hypot(u[0] - v[0], u[1] - v[1]) // 40) + 1)
    return sum(_dev(b, u[0] + (v[0] - u[0]) * i / n, u[1] + (v[1] - u[1]) * i / n) for i in range(n + 1)) / (n + 1)


def stop_node(adj, b, x, y, radius):
    """The street node a stop at (x, y) hangs on: an end of the nearest drawn street piece, or None when no street
    runs within `radius` of it."""
    best, bd = None, radius
    for u, nb in adj.items():
        for v in nb:
            if v < u:
                continue
            dx, dy = v[0] - u[0], v[1] - u[1]
            L2 = dx * dx + dy * dy or 1e-9
            t = max(0.0, min(1.0, ((x - u[0]) * dx + (y - u[1]) * dy) / L2))
            d = math.hypot(u[0] + t * dx - x, u[1] + t * dy - y)
            if d <= bd:
                bd, best = d, (u if t < .5 else v)
    return best


def _dijkstra(adj, cost, src, dst):
    dist, prev, q = {src: 0.0}, {}, [(0.0, src)]
    while q:
        d, u = heapq.heappop(q)
        if u == dst:
            break
        if d > dist.get(u, 1e18):
            continue
        for v, L in adj[u].items():
            c = d + cost(u, v, L)
            if c < dist.get(v, 1e18):
                dist[v], prev[v] = c, u
                heapq.heappush(q, (c, v))
    if dst not in dist:
        return None
    path = [dst]
    while path[-1] != src:
        path.append(prev[path[-1]])
    return path[::-1]


def route(adj, real, stops, branches, radius=85.0, dev_avg=60.0, max_dev=110.0, under=(), why=None, ramp=0.0, bend=0.0,
          split=0.0, carry=False, anchors=None, track=None, slack=450.0, share=1.0, tunnels_first=False, pref=None,
          octi2=None):
    """stops: [(x, y)] in grid px; branches: lists of indices into stops, in ride order; under: the indices of the stops
    that are underground stations (a tunnel needs no street: two such stops that no street joins are joined by a straight
    tunnel). Returns (edges, kept, tunnel) where edges is a set of ((x, y), (x, y)) pieces (each ordered low to high),
    kept the set of stop indices the line calls at and tunnel the pieces that run under no street. why: a list that
    collects why a pair of stops was not joined. ramp (px, 0 = off): an underground station off every street (a portal)
    is joined to its surface neighbour by a short tunnel ramp to the street node within `ramp` px of it nearest the real
    track, then by the streets. bend (px, 0 = off): what a turn costs, so that a trolley on a square grid under a
    diagonal real track takes one or two turns, not a stair-step at every corner. The engine-v2 options (all off on the
    square path): split (px): a stop stands at the foot of its perpendicular on the nearest street piece (the piece is cut
    there) unless that is within `split` px of the piece's end, so a stop on a long seam or avenue piece does not pull
    the line off it; carry: the line keeps its heading through a stop (a turn at a stop costs like any other); anchors: a
    dict filled with {stop index: node}; track: a _Track of the real track (true distances, not the 250 px capped
    buckets); slack (px): how much longer than 2.2x the straight line a join may be; share: a later branch rides
    street pieces an earlier branch of the line already takes at this share of the cost (branches share their trunk);
    tunnels_first: two underground stations whose street join turns more than once are joined by their straight tunnel
    (the real tunnel runs under the blocks; it is not drawn as a stair-step of streets); pref(u, v): True for a piece of
    a street the line's stops name (it rides its own street: no stray cost there, wherever the mapping drew it);
    octi2(a, b, dv) -> [a, corner, b]: the shape of a tunnel (default: straight)."""
    b = _bucket(real)
    memo = {}

    def dv(u, v):
        key = (u, v) if u < v else (v, u)
        if key not in memo:
            if pref is not None and pref(*key):
                memo[key] = 0.0
            elif track is None:
                memo[key] = _edge_dev(b, *key)
            else:
                (ux, uy), (vx, vy) = key
                n = max(2, int(math.hypot(vx - ux, vy - uy) // 40) + 1)
                memo[key] = sum(track.d(ux + (vx - ux) * i / n, uy + (vy - uy) * i / n, 4 * max_dev)
                                for i in range(n + 1)) / (n + 1)
        return memo[key]

    es, kept, tunnel = set(), set(), set()

    def cost(u, v, L):
        c = L * (1 + (dv(u, v) / dev_avg) ** 2)
        if share != 1.0 and ((u, v) if u < v else (v, u)) in es:
            c *= share
        return c
    for br in branches:
        nodes = []                              # (stop index, node)
        for si in br:
            if anchors and si in anchors:       # the caller already stood this stop on its street
                n = anchors[si]
            else:
                n = (_split_node(adj, stops[si][0], stops[si][1], radius, split) if split
                     else stop_node(adj, b, stops[si][0], stops[si][1], radius))
            if n is None and si in under:       # an underground station off every street stands where it is
                n = _k(*stops[si])
            if n is not None:
                nodes.append((si, n))
        runs, cur, head = [], None, None        # unbroken runs of stops: [stop indices, edges, tunnel edges]
        for k in range(len(nodes)):
            if cur is None:
                cur = [[nodes[k][0]], set(), set()]
            if k == len(nodes) - 1:
                runs.append(cur)
                break
            (sa, na), (sb, nb) = nodes[k], nodes[k + 1]
            got = None                          # the pieces that join the two stops, or None
            if na == nb:
                got = (set(), set())
            else:
                ramps = set()
                if ramp and (na in adj) != (nb in adj) and (sa if na not in adj else sb) in under:
                    off_ = na if na not in adj else nb
                    cand = [(math.hypot(u[0] - off_[0], u[1] - off_[1]) + 2 * _dev(b, *u), u) for u in adj
                            if abs(u[0] - off_[0]) <= ramp and abs(u[1] - off_[1]) <= ramp
                            and math.hypot(u[0] - off_[0], u[1] - off_[1]) <= ramp]
                    if cand:
                        on = min(cand)[1]
                        ramps = {(off_, on) if off_ < on else (on, off_)}
                        na, nb = (on, nb) if off_ == na else (na, on)
                path = None
                if na in adj and nb in adj:
                    h0 = head if (carry and not ramps and cur is not None and len(cur[0]) > 1) else None
                    path = _dijkstra_bends(adj, cost, na, nb, bend, h0) if bend else _dijkstra(adj, cost, na, nb)
                if ramps and path is not None and len(path) == 1:
                    path = None
                straight = math.hypot(na[0] - nb[0], na[1] - nb[1])
                bad = None
                if not path:
                    bad = "no street joins them"
                else:
                    plen = sum(adj[u][v] for u, v in zip(path, path[1:]))
                    mdev = sum(dv(u, v) * adj[u][v] for u, v in zip(path, path[1:])) / (plen or 1)
                    if mdev > max_dev:
                        bad = "the streets between them stray %d px from the real track" % mdev
                    elif plen > 2.2 * straight + slack:
                        bad = "the streets between them are a %d px detour for %d px" % (plen, straight)
                if tunnels_first and sa in under and sb in under and na != nb and \
                        (bad or sum(1 for a_, b_, c_ in zip(path, path[1:], path[2:])
                                    if _turn(_ang(a_, b_), _ang(b_, c_)) > 2) > 1):
                    bad = bad or "the streets between two underground stations turn more than once"
                if not bad:
                    got = ({(u, v) if u < v else (v, u) for u, v in zip(path, path[1:])} | ramps, ramps)
                    head = _ang(path[-2], path[-1]) if len(path) > 1 else head
                elif sa in under and sb in under:   # a tunnel between two underground stations
                    pts = octi2(na, nb, dv) if octi2 else [na, nb]
                    tes = {(u, v) if u < v else (v, u) for u, v in zip(pts, pts[1:]) if u != v}
                    got = (tes, tes)
                    head = None
                elif why is not None:
                    why.append((sa, sb, bad))
            if got is None:                     # no track joins them: the ride ends here, a new run starts
                runs.append(cur)
                cur, head = None, None
                continue
            cur[0].append(sb)
            cur[1] |= got[0]
            cur[2] |= got[1]
        # a branch is one piece of track: the run that reaches the tunnel (else the longest) stays, the stops cut off from
        # it are not drawn
        if runs:
            best = max(runs, key=lambda r: (sum(1 for si in r[0] if si in under), len(r[0])))
            if len([r for r in runs if len(r[0]) > 1]) and len(best[0]) < 2:
                best = max(runs, key=lambda r: len(r[0]))
            if len(best[0]) >= 2:
                kept |= set(best[0])
                es |= best[1]
                tunnel |= best[2]
                if anchors is not None:
                    node = dict(nodes)
                    anchors.update({si: node[si] for si in best[0] if si in node})
    return es, kept, tunnel


def _split_node(adj, x, y, radius, end, dirn=None):
    """The street node a stop at (x, y) stands on: the foot of its perpendicular on the nearest drawn street piece within
    `radius` (the piece is cut there, so the stop is ON the street and the line need not leave it), or that piece's end
    when the foot is within `end` px of it; None when no street runs within `radius`. dirn: the real track's direction
    there (a unit vector): a piece across it (more than 50 degrees off) counts `radius` farther (the stop stands on the
    street the line runs along, not on a cross street a spur away)."""
    best, bd = None, 2 * radius if dirn else radius
    for u, nb in adj.items():
        if abs(u[0] - x) > radius + 2000 or abs(u[1] - y) > radius + 2000:
            continue
        for v in nb:
            if v < u:
                continue
            dx, dy = v[0] - u[0], v[1] - u[1]
            L2 = dx * dx + dy * dy or 1e-9
            t = max(0.0, min(1.0, ((x - u[0]) * dx + (y - u[1]) * dy) / L2))
            d = math.hypot(u[0] + t * dx - x, u[1] + t * dy - y)
            if d > radius:
                continue
            if dirn and abs(dx * dirn[0] + dy * dirn[1]) < 0.64 * math.sqrt(L2):
                d += radius
            if d <= bd:
                bd, best = d, (u, v, t)
    if best is None:
        return None
    u, v, t = best
    L = math.hypot(v[0] - u[0], v[1] - u[1])
    if t * L <= end:
        return u
    if (1 - t) * L <= end:
        return v
    p = _k(u[0] + t * (v[0] - u[0]), u[1] + t * (v[1] - u[1]))
    if p in adj:
        return p
    del adj[u][v]
    del adj[v][u]
    for a in (u, v):
        d = math.hypot(a[0] - p[0], a[1] - p[1])
        adj.setdefault(p, {})[a] = d
        adj[a][p] = d
    return p


# ── any angle: the generic street graph ─────────────────────────────────────────────────────────────────────────────
SNAP = 3.0              # px: a crossing this near a segment's end is that end (a T at a street's corner)
BUCKET = 64.0           # px: the bucket grid that finds the segments that may cross
MERGE = 0.3             # px: two graph nodes nearer than this are one node


def _pairs(f):
    return [(f[k], f[k + 1]) for k in range(0, len(f) - 1, 2)]


def drawn_segs(tiles=(), tq=(), edges=(), te=(), streets=()):
    """Every street piece the page draws, as (x0, y0, x1, y1): the sides of the upright tiles, the sides of the polygon
    tiles (`tq`: flat rings, a tilted domain's blocks and the cut blocks at a seam), the loose edges, the loose tilted
    edges (`te`: flat polylines) and the streets drawn on their own: diagonal avenues (`d`, without the leads that run
    along the street they join), lattice majors (`L`), seams (`sm`) and bridges (`o`)."""
    out, seen = [], set()

    def add(ax, ay, bx, by):
        if abs(ax - bx) < 1e-6 and abs(ay - by) < 1e-6:
            return
        k = (round(ax, 1), round(ay, 1), round(bx, 1), round(by, 1))
        if k[2:] + k[:2] in seen or k in seen:
            return
        seen.add(k)
        out.append((float(ax), float(ay), float(bx), float(by)))
    for a, b, c, d in tiles:
        add(a, b, c, b); add(c, b, c, d); add(c, d, a, d); add(a, d, a, b)
    for f in tq:
        P = _pairs(f)
        if len(P) > 1 and P[0] == P[-1]:
            P = P[:-1]
        for u, v in zip(P, P[1:] + P[:1]):
            add(*u, *v)
    for e in edges:
        add(*e[:4])
    for f in te:
        P = _pairs(f)
        for u, v in zip(P, P[1:]):
            add(*u, *v)
    for st in streets:
        if not (st.get("d") or st.get("L") or st.get("sm") or st.get("o")):
            continue
        q = st["p"]
        if st.get("d"):
            j = st.get("j", (1, 1))
            q2 = q[(2 if j[0] else 0):len(q) - (2 if j[1] else 0)]
            q = q2 if len(q2) >= 4 else q                  # a street with no lead to strip (a tilted lattice line) stays whole
        P = _pairs(q)
        for u, v in zip(P, P[1:]):
            add(*u, *v)
    return out


def _cells_along(ax, ay, bx, by, cell):
    n = max(1, int(math.hypot(bx - ax, by - ay) // (cell / 2)) + 1)
    return {(int((ax + (bx - ax) * k / n) // cell), int((ay + (by - ay) * k / n) // cell)) for k in range(n + 1)}


class _Nodes:
    """Graph nodes, merged when nearer than MERGE px; keys are (x, y) rounded to 0.1 px."""

    def __init__(self):
        self.b = {}

    def key(self, x, y):
        cx, cy = int(x // 1.0), int(y // 1.0)
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                for k in self.b.get((cx + i, cy + j), ()):
                    if math.hypot(k[0] - x, k[1] - y) < MERGE:
                        return k
        k = _k(x, y)
        self.b.setdefault((cx, cy), []).append(k)
        return k


def _hits(a, b, tol=0.5):
    """Where segment a meets segment b: [(t on a, u on b, x, y)] (a crossing, a T, or the ends of a collinear overlap)."""
    ax, ay, bx, by = a
    cx, cy, dx, dy = b
    rx, ry, sx, sy = bx - ax, by - ay, dx - cx, dy - cy
    La, Lb = math.hypot(rx, ry) or 1e-9, math.hypot(sx, sy) or 1e-9
    den = rx * sy - ry * sx
    if abs(den) <= 1e-7 * La * Lb:                       # parallel: only a collinear overlap meets
        if abs((cx - ax) * ry - (cy - ay) * rx) / La > tol:
            return []
        out = []
        for px, py in ((cx, cy), (dx, dy)):
            t = ((px - ax) * rx + (py - ay) * ry) / (La * La)
            if -tol / La <= t <= 1 + tol / La:
                out.append((t, ((px - cx) * sx + (py - cy) * sy) / (Lb * Lb), px, py))
        for px, py in ((ax, ay), (bx, by)):
            u = ((px - cx) * sx + (py - cy) * sy) / (Lb * Lb)
            if -tol / Lb <= u <= 1 + tol / Lb:
                out.append((((px - ax) * rx + (py - ay) * ry) / (La * La), u, px, py))
        return out
    t = ((cx - ax) * sy - (cy - ay) * sx) / den
    u = ((cx - ax) * ry - (cy - ay) * rx) / den
    if -tol / La <= t <= 1 + tol / La and -tol / Lb <= u <= 1 + tol / Lb:
        return [(t, u, ax + t * rx, ay + t * ry)]
    return []


def _street_graph_any(segs):
    """The street graph over drawn segments at any angle: every segment is cut wherever another one crosses it or ends on
    it (a crossing within SNAP px of a segment's end is that end), so a trolley can turn at every intersection, of
    tilted streets, upright ones and seams alike. Nodes are (x, y) rounded to 0.1 px."""
    segs = [tuple(float(v) for v in s[:4]) for s in segs]
    segs = [s for s in segs if math.hypot(s[2] - s[0], s[3] - s[1]) > 0.05]
    reg, cells = {}, []
    for si, (ax, ay, bx, by) in enumerate(segs):
        cs = _cells_along(ax, ay, bx, by, BUCKET)
        cells.append(cs)
        for cx, cy in cs:
            for i in (-1, 0, 1):
                for j in (-1, 0, 1):
                    reg.setdefault((cx + i, cy + j), set()).add(si)
    cuts = [[] for _ in segs]
    for si, s in enumerate(segs):
        cand = set()
        for c in cells[si]:
            cand |= reg.get(c, set())
        for sj in cand:
            if sj <= si:
                continue
            for t, u, x, y in _hits(s, segs[sj]):
                for e in ((s[0], s[1]), (s[2], s[3]), segs[sj][:2], segs[sj][2:]):
                    if math.hypot(e[0] - x, e[1] - y) < SNAP:
                        x, y = e
                        break
                cuts[si].append((min(1.0, max(0.0, t)), x, y))
                cuts[sj].append((min(1.0, max(0.0, u)), x, y))
    nodes, adj = _Nodes(), {}
    for si, (ax, ay, bx, by) in enumerate(segs):
        chain = [(0.0, ax, ay)] + sorted(cuts[si]) + [(1.0, bx, by)]
        keys = []
        for _, x, y in chain:
            k = nodes.key(x, y)
            if not keys or keys[-1] != k:
                keys.append(k)
        for u, v in zip(keys, keys[1:]):
            if u == v:
                continue
            d = math.hypot(u[0] - v[0], u[1] - v[1])
            adj.setdefault(u, {})[v] = d
            adj.setdefault(v, {})[u] = d
    return adj


# ── several domains: real -> page, and octilinear routing of the grade-separated lines ─────────────────────────────
def _ring(r):
    if not r:
        return None
    if isinstance(r[0], (int, float)):
        r = _pairs(r)
    r = [(float(x), float(y)) for x, y in r]
    if len(r) > 1 and r[0] == r[-1]:
        r = r[:-1]
    return r


def _in_ring(r, x, y):
    ins = False
    n = len(r)
    for k in range(n):
        (ax, ay), (bx, by) = r[k], r[(k + 1) % n]
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            ins = not ins
    return ins


def _ring_d(r, x, y):
    n = len(r)
    best = 1e18
    for k in range(n):
        (ax, ay), (bx, by) = r[k], r[(k + 1) % n]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy or 1e-9
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
        best = min(best, math.hypot(ax + t * dx - x, ay + t * dy - y))
    return best


class _Dom:
    """One street-grid domain as the router sees it: its real polygon, its real -> local mapping (Domain.mapping), its
    Lattice (page(), local(), node(), xg, yg) and its page clip ring (None: the rest of the page, the root)."""

    def __init__(self, dom, lat):
        self.dom, self.lat, self.id = dom, lat, dom.id
        self.poly, self.clip = _ring(dom.poly), _ring(dom.clip)
        self.xg, self.yg = list(lat.xg), list(lat.yg)
        o, ex, ey = lat.page(0.0, 0.0), lat.page(1.0, 0.0), lat.page(0.0, 1.0)
        self.ux = (ex[0] - o[0], ex[1] - o[1])                    # page direction of the local x axis (unit: T_d is rigid)
        self.uy = (ey[0] - o[0], ey[1] - o[1])
        self.pbox = None
        if self.poly:
            xs, ys = [p[0] for p in self.poly], [p[1] for p in self.poly]
            self.pbox = (min(xs), min(ys), max(xs), max(ys))
        self.area = abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(self.poly, self.poly[1:] + self.poly[:1]))) / 2 \
            if self.poly else 0.0
        self.cbox = None
        if self.clip:
            xs, ys = [p[0] for p in self.clip], [p[1] for p in self.clip]
            self.cbox = (min(xs), min(ys), max(xs), max(ys))
        self.cw, self.ch = _spacing(self.xg), _spacing(self.yg)        # the block, from the lattice (any CW x CH)
        self.step = max(self.cw, self.ch)
        self.blk = (self.cw + self.ch) / 2.0
        self.m45 = _m45(self.cw, self.ch)

    def owns_real(self, x, y):
        if not self.poly:
            return False
        b = self.pbox
        return b[0] <= x <= b[2] and b[1] <= y <= b[3] and _in_ring(self.poly, x, y)

    def in_clip(self, x, y):
        b = self.cbox
        return b[0] <= x <= b[2] and b[1] <= y <= b[3] and _in_ring(self.clip, x, y)


class CityMap:
    """Real map px -> page px through the domain that owns the point (point in the domain's real polygon; outside every
    polygon, the nearest domain). doms: [(Domain, Lattice)] (city_types.Domain with .mapping real -> local and .clip
    the page clip ring; E2's Lattice)."""

    def __init__(self, doms):
        self.ds = [_Dom(d, l) for d, l in doms]
        self.rest = [d for d in self.ds if not d.clip]           # the domain(s) with no clip: everything no clip claims
        root = self.rest[0] if self.rest else max(self.ds, key=lambda d: d.area)
        self.blk = root.blk                                      # px of one block (the root's), the unit of every distance

    def dom_real(self, x, y):
        own = [d for d in self.ds if d.owns_real(x, y)]
        if own:                                          # nested polygons: the innermost (the smallest) owns it
            return own[0] if len(own) == 1 else min(own, key=lambda d: d.area)
        return min(self.ds, key=lambda d: _ring_d(d.poly, x, y) if d.poly else 1e17)

    def __call__(self, x, y):
        d = self.dom_real(x, y)
        return d.lat.page(*d.dom.mapping(x, y))

    def dom_page(self, x, y):
        """The domain whose page region holds (x, y)."""
        for d in self.ds:
            if d.clip and d.in_clip(x, y):
                return d
        if self.rest:
            return self.rest[0]
        return min(self.ds, key=lambda d: _ring_d(d.clip, x, y))

    def edge(self, x, y, tol=1.0):
        """True when (x, y) lies on a domain's clip ring (a seam, or a domain's edge)."""
        return any(d.clip and _ring_d(d.clip, x, y) <= tol for d in self.ds)

    def lane_key(self, u, v):
        """(domain id, "h"|"v", line index) when the page piece u-v runs along a lattice line of the domain it lies in,
        else None (a diagonal, a seam, a connector: a line keeps its centre there)."""
        mx, my = (u[0] + v[0]) / 2, (u[1] + v[1]) / 2
        d = self.dom_page(mx, my)
        (ax, ay), (bx, by) = d.lat.local(*u), d.lat.local(*v)
        if abs(ay - by) < 0.05 and abs(ax - bx) > 0.05:
            j = _nearest(d.yg, (ay + by) / 2)
            if abs(d.yg[j] - (ay + by) / 2) < 0.5:
                return (d.id, "h", j)
        if abs(ax - bx) < 0.05 and abs(ay - by) > 0.05:
            i = _nearest(d.xg, (ax + bx) / 2)
            if abs(d.xg[i] - (ax + bx) / 2) < 0.5:
                return (d.id, "v", i)
        return None

    def normal(self, key):
        """Page unit vector a lane offset of `key` moves along."""
        d = next(d for d in self.ds if d.id == key[0])
        return d.uy if key[1] == "h" else d.ux


def _spacing(G):
    """A lattice's line step (the median gap; lattices are even), 205 px when it has one line."""
    gaps = sorted(abs(b - a) for a, b in zip(G, G[1:]) if abs(b - a) > 1e-6)
    return gaps[len(gaps) // 2] if gaps else 205.0


def _nearest(G, v):
    from bisect import bisect_left
    i = bisect_left(G, v)
    if i <= 0:
        return 0
    if i >= len(G):
        return len(G) - 1
    return i if G[i] - v < v - G[i - 1] else i - 1


DIRS = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))
# every size below is in BLOCKS of the domain (Lattice spacing: (column step + row step) / 2), never page px, so the router
# reads the same on any block shape (CW x CH)
CORR = 2.25             # blocks: the lattice nodes this near the real track are the router's candidates
SEAM_R = 1.25           # blocks: a node this near a seam may run straight to it (on an axis or diagonal of its domain)
DEV_R = 1.0             # blocks: how far a grade-separated run may stray from the real track before the router dislikes it
BEND = 4.0              # blocks: the cost of one 45-degree bend (a 90-degree bend costs 1.8x, a near-U-turn 8x)
STOP_NODE = 1.0         # blocks: a station stands on a lattice node this near it, or is not drawn
STOP_W = 1.5            # cost of each px a station is moved from its real place
STRAY_MAX = 2.5         # blocks: no run strays farther than this from the real track
NEAR45 = 0.8            # degrees: a lattice move (p columns, q rows) this close to 45 degrees is a 45-degree run
SHARE = 0.4             # a branch runs on track another branch of its line already uses at this share of the cost
RIVER_X = 4.0           # blocks: what crossing a river costs (a line crosses where its real track does, not back and forth)


def _ang(u, v):
    return math.degrees(math.atan2(v[1] - u[1], v[0] - u[0]))


def _turn(a, b):
    d = abs((b - a + 180.0) % 360.0 - 180.0)
    return d


def _m45(cw, ch):
    """The smallest lattice move (p columns, q rows) whose page angle is within NEAR45 of a true 45 degrees, or None
    (a square lattice: its index diagonal is already 45)."""
    best = None
    for p in range(1, 9):
        for q in range(1, 9):
            if math.gcd(p, q) != 1:
                continue
            if abs(math.degrees(math.atan2(q * ch, p * cw)) - 45.0) <= NEAR45:
                L = math.hypot(p * cw, q * ch)
                if best is None or L < best[2]:
                    best = (p, q, L)
    return None if best is None or best[:2] == (1, 1) else best[:2]


class _Track:
    """The real track (page px samples): the distance from any point to it, up to a cap."""

    def __init__(self, pts, cell):
        self.c = max(20.0, float(cell))
        self.b = {}
        for x, y in pts:
            self.b.setdefault((int(x // self.c), int(y // self.c)), []).append((x, y))

    def d(self, x, y, cap):
        c = self.c
        cx, cy = int(x // c), int(y // c)
        best, r = cap, 0
        while (r - 1) * c <= best:
            for i in range(-r, r + 1):
                for j in (range(-r, r + 1) if abs(i) == r else (-r, r)):
                    for px, py in self.b.get((cx + i, cy + j), ()):
                        dd = math.hypot(px - x, py - y)
                        if dd < best:
                            best = dd
            r += 1
            if r > 64:
                break
        return best


def octi_graph(cmap, real):
    """The lattice graph a grade-separated line may run on: the nodes of every domain within CORR blocks of the real
    track (page px samples `real`), stepping along the domain's axes, its index diagonals and its 45-degree moves
    (_m45); where the track nears a seam, rays from the nodes along the axes and diagonals to the seam, and runs along
    the seam between the points they reach.
    -> (adj {node: {node: length}}, info {(u, v): (dom id, i0, j0, i1, j1) | None})  (nodes: page (x, y) rounded 0.1)"""
    adj, info = {}, {}
    valid = {}

    def ok(d, x, y):
        k = (d.id, round(x, 1), round(y, 1))
        if k not in valid:
            valid[k] = cmap.dom_page(x, y) is d or cmap.edge(x, y)
        return valid[k]

    def link(u, v, inf):
        if u == v:
            return
        L = math.hypot(u[0] - v[0], u[1] - v[1])
        adj.setdefault(u, {})[v] = L
        adj.setdefault(v, {})[u] = L
        info[(u, v)] = inf
        info[(v, u)] = None if inf is None else (inf[0], inf[3], inf[4], inf[1], inf[2])
    nodes = {}                                       # dom id -> {(i, j)}
    pts = real[::2] if len(real) > 4000 else real
    for d in cmap.ds:
        got = nodes.setdefault(d.id, set())
        R = CORR * d.blk
        for x, y in pts:
            if d.cbox and not (d.cbox[0] - R <= x <= d.cbox[2] + R and d.cbox[1] - R <= y <= d.cbox[3] + R):
                continue
            lx, ly = d.lat.local(x, y)
            i0, j0 = _nearest(d.xg, lx - R), _nearest(d.yg, ly - R)
            i1, j1 = _nearest(d.xg, lx + R), _nearest(d.yg, ly + R)
            for i in range(i0, i1 + 1):
                for j in range(j0, j1 + 1):
                    if (i, j) not in got and math.hypot(d.xg[i] - lx, d.yg[j] - ly) <= R:
                        got.add((i, j))
        got_ok = set()
        for i, j in got:
            p = d.lat.page(d.xg[i], d.yg[j])
            if ok(d, *p):
                got_ok.add((i, j))
        nodes[d.id] = got_ok
    for d in cmap.ds:
        got = nodes[d.id]
        P = {n: _k(*d.lat.page(d.xg[n[0]], d.yg[n[1]])) for n in got}
        moves = list(DIRS[:4])
        if d.m45:
            moves += [d.m45, (d.m45[0], -d.m45[1])]
        for (i, j) in got:
            for di, dj in moves:
                n2 = (i + di, j + dj)
                if n2 not in got:
                    continue
                u, v = P[(i, j)], P[n2]
                long_ = abs(di) > 1 or abs(dj) > 1
                if all(ok(d, u[0] + (v[0] - u[0]) * f, u[1] + (v[1] - u[1]) * f)
                       for f in ((0.2, 0.4, 0.5, 0.6, 0.8) if long_ else (0.5,))):
                    link(u, v, (d.id, i, j, n2[0], n2[1]))
    # seams: a node near a domain's clip ring runs on along each of its directions to the ring; the points reached on
    # one ring edge are joined in order along it (the seam is a drawn line)
    rings = [d.clip for d in cmap.ds if d.clip]
    if not rings:
        return adj, info
    on_edge = {}                                     # (ring index, edge index) -> [(t, node)]
    for d in cmap.ds:
        R = SEAM_R * d.blk
        for (i, j) in nodes[d.id]:
            p = d.lat.page(d.xg[i], d.yg[j])
            near = [(ri, r) for ri, r in enumerate(rings) if _ring_d(r, *p) <= R]
            if not near:
                continue
            u = _k(*p)
            for ri, r in near:                          # a lattice node on a ring is a seam point of that ring
                for ei in range(len(r)):
                    a, b = r[ei], r[(ei + 1) % len(r)]
                    dd = _seg_pd(p, a, b)
                    if dd[0] <= 0.5:
                        on_edge.setdefault((ri, ei), []).append((dd[1], u))
            cw = d.xg[min(i + 1, len(d.xg) - 1)] - d.xg[max(i - 1, 0)]
            ch = d.yg[min(j + 1, len(d.yg) - 1)] - d.yg[max(j - 1, 0)]
            for di, dj in DIRS:
                q = d.lat.page(d.xg[i] + di * cw, d.yg[j] + dj * ch)
                dx, dy = q[0] - p[0], q[1] - p[1]
                L = math.hypot(dx, dy) or 1.0
                dx, dy = dx / L, dy / L
                best = None
                for ri, r in near:
                    for ei in range(len(r)):
                        a, b = r[ei], r[(ei + 1) % len(r)]
                        h = _ray(p, (dx, dy), a, b)
                        if h and 1.0 < h[0] <= R and (best is None or h[0] < best[0]):
                            best = (h[0], h[1], ri, ei)
                if best is None:
                    continue
                s = (p[0] + dx * best[0], p[1] + dy * best[0])
                if not ok(d, (p[0] + s[0]) / 2, (p[1] + s[1]) / 2):
                    continue
                sk = _k(*s)
                link(u, sk, None)
                on_edge.setdefault((best[2], best[3]), []).append((best[1], sk))
    gap = 1.5 * max(d.step for d in cmap.ds)
    for (ri, ei), lst in on_edge.items():
        lst = sorted(set(lst))
        r = rings[ri]
        a, b = r[ei], r[(ei + 1) % len(r)]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        for (t0, u), (t1, v) in zip(lst, lst[1:]):
            if (t1 - t0) * L <= gap:
                link(u, v, None)
    return adj, info


def _seg_pd(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy or 1e-9
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(a[0] + t * dx - p[0], a[1] + t * dy - p[1]), t


def _ray(p, d, a, b):
    """Ray p + s*d (s >= 0, d a unit step) against segment a-b: (s, t along a-b) or None."""
    ex, ey = b[0] - a[0], b[1] - a[1]
    den = d[0] * ey - d[1] * ex
    if abs(den) < 1e-9:
        return None
    s = ((a[0] - p[0]) * ey - (a[1] - p[1]) * ex) / den
    t = ((a[0] - p[0]) * d[1] - (a[1] - p[1]) * d[0]) / den
    if s < 0 or not (-1e-6 <= t <= 1 + 1e-6):
        return None
    return s, t


def _dijkstra_bends(adj, cost, src, dst, bend=None, h0=None):
    """Cheapest path src -> dst where a bend costs `bend` (px) scaled by how sharp it is (states: node, heading). h0: the
    heading the line arrives at src with (a turn right at src costs too); None: any."""
    B = 400.0 if bend is None else bend
    start = (src, None if h0 is None else round(h0))
    dist, prev, q, n = {start: 0.0}, {}, [(0.0, 0, start)], 0
    while q:
        c, _, st = heapq.heappop(q)
        u, h = st
        if c > dist.get(st, 1e18):
            continue
        if u == dst:
            path = [u]
            while st in prev:
                st = prev[st]
                path.append(st[0])
            return path[::-1]
        for v, L in adj[u].items():
            a = round(_ang(u, v))
            t = 0.0 if h is None else _turn(h, a)
            if t > 100:
                pen = 4 * B
            elif t > 2:
                pen = B * (0.6 + 0.4 * t / 90.0)
            else:
                pen = 0.0
            c2 = c + cost(u, v, L) + pen
            s2 = (v, a)
            if c2 < dist.get(s2, 1e18):
                dist[s2], prev[s2] = c2, st
                n += 1
                heapq.heappush(q, (c2, n, s2))
    return None


def _bend_pen(t, B):
    """What a turn of t degrees costs a grade-separated line: nothing straight on, one B for a 45-degree bend, 1.8 B for
    a square corner, a near-U-turn 8 B (a transit map line bends seldom and gently)."""
    if t <= 2.0:
        return 0.0
    if t <= 60.0:
        return B * (0.5 + t / 90.0)
    if t <= 95.0:
        return 1.2 * B * (0.5 + t / 90.0)
    return 8.0 * B


def _octi_seg(adj, cost, srcs, dsts, B):
    """Cheapest path from any (node, heading, start cost) in srcs to any node of dsts {node: arrival cost}, a bend
    costing _bend_pen. -> (path, heading at the end) or None."""
    dist, prev, q, n = {}, {}, [], 0
    for u, h, c0 in srcs:
        st = (u, h)
        if c0 < dist.get(st, 1e18):
            dist[st] = c0
            n += 1
            heapq.heappush(q, (c0, n, st))
    while q:
        c, _, st = heapq.heappop(q)
        if st[0] == "T":
            st = prev[st]
            h = st[1]
            path = [st[0]]
            while st in prev:
                st = prev[st]
                path.append(st[0])
            return path[::-1], h
        if c > dist.get(st, 1e18):
            continue
        u, h = st
        if u in dsts:
            tst = ("T", u, h)
            c2 = c + dsts[u]
            if c2 < dist.get(tst, 1e18):
                dist[tst], prev[tst] = c2, st
                n += 1
                heapq.heappush(q, (c2, n, tst))
        for v, L in adj[u].items():
            a = round(_ang(u, v))
            pen = 0.0 if h is None else _bend_pen(_turn(h, a), B)
            ec = cost(u, v, L)
            if ec is None:
                continue
            c2 = c + ec + pen
            s2 = (v, a)
            if c2 < dist.get(s2, 1e18):
                dist[s2], prev[s2] = c2, st
                n += 1
                heapq.heappush(q, (c2, n, s2))
    return None


def octi_route(cmap, real, stops, branches, dev=None, anchors=None, rivers=()):
    """A grade-separated line over the domains' lattices, branch by branch in ride order: each station on a lattice node
    (or seam point) within STOP_NODE blocks of it, chosen with the route (cost: how far it moves), the line carrying
    its heading through the station (a bend at a station costs like any other), consecutive stations joined by the
    cheapest octilinear way (close to the real track, few and gentle bends, never more than STRAY_MAX blocks from it);
    a later branch rides the track an earlier one laid at a discount, so branches share their trunk.
    real: the real track in page px; stops: [(x, y)] page px; anchors: a dict filled with {stop index: node};
    rivers: [{p: flat page polyline}] (the centre lines a crossing is counted on).
    -> (edges {(u, v)}, kept stop indices, info {(u, v): (dom id, i0, j0, i1, j1) | None})"""
    adj, info = octi_graph(cmap, real)
    blk = cmap.blk
    trk = _Track(real, blk / 2)
    DEV = (dev if dev is not None else DEV_R * blk)
    cap = (STRAY_MAX + 1.0) * blk
    memo, used = {}, set()
    rcell = 2 * blk
    rsegs = {}
    for rv in rivers or ():
        rp = rv["p"]
        for q in range(0, len(rp) - 3, 2):
            sg = (rp[q], rp[q + 1], rp[q + 2], rp[q + 3])
            for c in _cells_along(*sg, rcell):
                rsegs.setdefault(c, []).append(sg)

    def crossings(u, v):
        if not rsegs:
            return 0
        seen = set()
        for c in _cells_along(u[0], u[1], v[0], v[1], rcell):
            for sg in rsegs.get(c, ()):
                if sg not in seen and _hits((u[0], u[1], v[0], v[1]), sg, tol=0.0):
                    seen.add(sg)
        return len(seen)

    def dvm(u, v):
        key = (u, v) if u < v else (v, u)
        if key not in memo:
            L = math.hypot(v[0] - u[0], v[1] - u[1])
            n = max(2, int(L // (blk / 4)) + 1)
            ds = [trk.d(u[0] + (v[0] - u[0]) * i / n, u[1] + (v[1] - u[1]) * i / n, cap) for i in range(n + 1)]
            memo[key] = (sum(ds) / len(ds), max(ds), crossings(u, v))
        return memo[key]

    def cost(u, v, L):
        mean, mx, nx = dvm(u, v)
        if mx > STRAY_MAX * blk:
            return None
        c = L * (1 + (mean / DEV) ** 2) + nx * RIVER_X * blk
        return c * SHARE if ((u, v) if u < v else (v, u)) in used else c
    nb = {}
    cell = max(100.0, blk)
    for u in adj:
        nb.setdefault((int(u[0] // cell), int(u[1] // cell)), []).append(u)

    def cands(x, y):
        R = STOP_NODE * cmap.dom_page(x, y).blk
        out = {}
        cx, cy = int(x // cell), int(y // cell)
        k = int(R // cell) + 1
        for i in range(-k, k + 1):
            for j in range(-k, k + 1):
                for u in nb.get((cx + i, cy + j), ()):
                    dd = math.hypot(u[0] - x, u[1] - y)
                    if dd <= R:
                        out[u] = STOP_W * dd + 0.5 * trk.d(u[0], u[1], cap)
        return out
    B = BEND * blk
    es, kept, fixed = set(), set(), {}
    for br in branches:
        seq = []
        for si in br:
            c = {fixed[si]: 0.0} if si in fixed else cands(*stops[si])
            if c:
                seq.append((si, c))
        if len(seq) < 2:
            if seq and seq[0][0] in fixed:
                kept.add(seq[0][0])
            continue
        si0, c0 = seq[0]
        srcs, cur = [(u, None, c) for u, c in c0.items()], None
        for si, cs in seq[1:]:
            dsts = dict(cs)
            taken = set(fixed.values()) - ({fixed[si]} if si in fixed else set())
            if cur is not None:
                taken.add(cur)
            if any(u not in taken for u in dsts):
                dsts = {u: c for u, c in dsts.items() if u not in taken}
            got = _octi_seg(adj, cost, srcs, dsts, B)
            if got is None:
                continue                                 # unreachable: this station is not drawn, the line goes on
            path, h = got
            if cur is None:
                fixed.setdefault(si0, path[0])
                kept.add(si0)
            fixed.setdefault(si, path[-1])
            kept.add(si)
            for u, v in zip(path, path[1:]):
                e = (u, v) if u < v else (v, u)
                es.add(e)
                used.add(e)
            cur = path[-1]
            srcs = [(cur, h, 0.0)]
    if anchors is not None:
        anchors.update({si: fixed[si] for si in kept if si in fixed})
    return es, kept, {e: info.get(e) for e in es}


def octi2_in(cmap):
    """A tunnel between two underground stations drawn like an avenue: a run along its domain's axis and a 45-degree run
    (of the domain at its middle), the corner on the side nearer the real track. -> octi2(a, b, dv) for route()."""
    def f(a, b, dv):
        d = cmap.dom_page((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        ux, uy = d.ux, d.uy
        L = math.hypot(*ux) or 1.0
        ux, uy = (ux[0] / L, ux[1] / L), (uy[0] / L, uy[1] / L)
        dx, dy = b[0] - a[0], b[1] - a[1]
        lx, ly = dx * ux[0] + dy * ux[1], dx * uy[0] + dy * uy[1]          # the step in the domain's own frame
        m = min(abs(lx), abs(ly))
        if m < 1.0 or abs(abs(lx) - abs(ly)) < 1.0:
            return [a, b]
        sx, sy = math.copysign(m, lx), math.copysign(m, ly)                # the 45-degree part
        best = None
        for first in (True, False):
            if first:                                                     # 45 first, then the axis run
                c = (a[0] + sx * ux[0] + sy * uy[0], a[1] + sx * ux[1] + sy * uy[1])
            else:                                                         # the axis run, then 45
                c = (b[0] - sx * ux[0] - sy * uy[0], b[1] - sx * ux[1] - sy * uy[1])
            c = _k(*c)
            cost = dv(a, c) * math.hypot(c[0] - a[0], c[1] - a[1]) + dv(c, b) * math.hypot(b[0] - c[0], b[1] - c[1])
            if best is None or cost < best[0]:
                best = (cost, c)
        return [a, best[1], b]
    return f
