"""The palace's real transit, drawn like its streets: the lines palace_map reads
from the route relations (SEPTA's subways, trolleys and Regional Rail, PATCO)
are carried onto the palace's even grid. A trolley runs ON a street: palace_transit_route
routes it along the streets the grid really draws (grid edges and the clean diagonal avenues) and
drops a stop no drawn street supports; it never makes a street. The grade-separated lines (subway,
el, PATCO, Regional Rail) are snapped to the grid lines (straight runs, square turns — the page
rounds them like its streets), a
line that shares a street with another runs in its own lane beside it, and the
stations stand on their lines.

    snap(tr, mp, xg, yg, W, H) -> {"lines": [{id, n, c, k, p: [flat polylines], s: [stop idx]}],
                                    "stops": [{n, x, y, l: [line ids]}],
                                    "ge": [(i0, j0, i1, j1)]  # the grid edges the grade-separated lines run along (palace_grid draws a street
                                                              # under any that has none: a line never runs through a void)}

A city of several street-grid domains (engine v2) passes doms=[(Domain, Lattice)] (city_types.Domain: .id, .poly real
ring, .mapping real -> local, .clip page ring; city_lattice.Lattice: page(), local(), node(), xg, yg) and the drawn
segments `segs` (palace_transit_route.drawn_segs: tiles, tq, edges, te, d/L/sm/o streets). Then a trolley is routed on
the drawn streets at any angle, and a grade-separated line runs on each domain's own axes and diagonals (octilinear in
its domain, joined along the seam where it crosses one), and "ge" holds (dom, i0, j0, i1, j1) axis edges. One square
domain (or no doms) takes the square path above, unchanged: its output is byte-identical to 1.9.78's.
"""
from __future__ import annotations

import math
from bisect import bisect_left

STOP_R = 85.0           # a trolley stop with no drawn street this near (grid px) is dropped: it would float
DEV_AVG = 60.0          # px: how far a street may stray from the real track before the router stops liking it
MAX_DEV = 150.0         # px: a routed stretch whose mean distance from the real track is more than this is not used
LANE = 7.0              # px between two lines that share a street
RAMP = 500.0            # px (engine v2 only): an underground station off every street reaches its first street by a tunnel ramp this long at most
TRAM_BEND = 70.0        # px (engine v2 only): what one turn costs a trolley (no stair-step under a diagonal real track)
# engine v2 (several domains): the same sizes in BLOCKS of the page (the root lattice's (column step + row step) / 2), so
# they hold on any block shape; 1 block = 205 px on the 240 x 170 page
V2 = {"stop_r": 85.0 / 205, "dev_avg": 0.5, "max_dev": 0.9, "ramp": 500.0 / 205, "bend": 0.9,
      "split": 0.15, "gap": 130.0 / 205, "slack": 450.0 / 205,
      "named": 1.0,     # a stop "A & B" stands where the drawn streets A and B cross, if they cross this near it
      "along": 0.75,    # else on the drawn street A (or B) it names, if that runs this near it (and the real track too)
      "far": 1.5}       # the street a line's stops share (it runs along it): the stop stands on it this far off at most
CORNER = 16.0           # px (engine v2): the page rounds a line's turns with a 14 px radius; a dot stays this far from a turn
MAX_STOP_GAP = 130.0    # a stop farther than this from its line (about half a block) is not drawn: its track was trimmed or never fetched


def _near(v, G):
    """Index of the grid coordinate nearest v."""
    i = bisect_left(G, v)
    if i <= 0:
        return 0
    if i >= len(G):
        return len(G) - 1
    return i if G[i] - v < v - G[i - 1] else i - 1


def _stop_node(es, xg, yg, gx, gy):
    """The grid node a stop at (gx, gy) hangs on: the nearer end of the track edge nearest to it,
    or None when no track edge passes within MAX_STOP_GAP of it."""
    best, bd = None, MAX_STOP_GAP
    for a, b in es:
        ax, ay, bx, by = xg[a[0]], yg[a[1]], xg[b[0]], yg[b[1]]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy or 1e-9
        t = max(0.0, min(1.0, ((gx - ax) * dx + (gy - ay) * dy) / L2))
        d = math.hypot(ax + t * dx - gx, ay + t * dy - gy)
        if d <= bd:
            bd, best = d, (a if t < .5 else b)
    return best


def _walk(a, b, first_h):
    """Grid nodes from a to b by straight runs along grid lines: keep going the way
    the line was going, then turn once."""
    (i0, j0), (i1, j1) = a, b
    if i0 == i1 or j0 == j1:
        corner = None
    elif first_h:
        corner = (i1, j0)
    else:
        corner = (i0, j1)
    out = []
    for p, q in ((a, corner or b), (corner, b) if corner else (None, None)):
        if p is None:
            continue
        di = (q[0] > p[0]) - (q[0] < p[0])
        dj = (q[1] > p[1]) - (q[1] < p[1])
        n = max(abs(q[0] - p[0]), abs(q[1] - p[1]))
        out += [(p[0] + di * k, p[1] + dj * k) for k in range(n)]
    out.append(b)
    return out


def _edges_of(poly, mp, xg, yg):
    """The unit grid edges one real polyline (map px) is snapped to."""
    nodes = []
    for k in range(0, len(poly) - 1, 2):
        gx, gy = mp(poly[k], poly[k + 1])
        n = (_near(gx, xg), _near(gy, yg))
        if not nodes or nodes[-1] != n:
            nodes.append(n)
    path, horiz = [], True
    for a, b in zip(nodes, nodes[1:]):
        if a[0] != b[0] and a[1] == b[1]:
            horiz = True
        elif a[1] != b[1] and a[0] == b[0]:
            horiz = False
        else:
            horiz = abs(b[0] - a[0]) >= abs(b[1] - a[1]) if len(path) < 2 else horiz
        seg = _walk(a, b, horiz)
        path += seg if not path else seg[1:]
    es = set()
    for a, b in zip(path, path[1:]):
        if a != b:
            es.add((a, b) if a < b else (b, a))
    return es


def _paths(edges):
    """Edges -> maximal paths (a path ends where the line ends or branches)."""
    adj = {}
    for a, b in edges:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen, out = set(), []

    def take(a, b):
        return (a, b) if a < b else (b, a)
    starts = [n for n, v in adj.items() if len(v) != 2] + [n for n, v in adj.items() if len(v) == 2]
    for s in starts:
        for nb in adj[s]:
            if take(s, nb) in seen:
                continue
            path, prev, cur = [s], s, nb
            seen.add(take(s, nb))
            path.append(cur)
            while len(adj[cur]) == 2:
                nx = adj[cur][0] if adj[cur][0] != prev else adj[cur][1]
                e = take(cur, nx)
                if e in seen:
                    break
                seen.add(e)
                prev, cur = cur, nx
                path.append(cur)
            out.append(path)
    return out


def _trunk(es, branches):
    """A line's track between its own stops. OSM carries every siding and yard a
    route touches, and on the grid they read as boxy loops; the shortest way
    from each stop to the next one *of the same branch* is the line (never a
    shortcut between stops that are not neighbours, never a link between two
    branches). `branches` are lists of nodes, one per stop that has track near
    it, in ride order. Track left dangling past the last stop of a branch (a
    yard lead, the part of a line that runs off the map) is cut back to that
    stop. A line that does not connect up (or has under two stops) keeps all
    its edges."""
    from collections import deque
    adj = {}
    for a, b in es:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    if not adj:
        return es
    pts = [list(dict.fromkeys(br)) for br in branches]
    if sum(len(p) for p in pts) < 2:
        return es
    keep, stopn = set(), {n for p in pts for n in p}
    for br in pts:
        for src, dst in zip(br, br[1:]):
            prev = {src: None}
            q = deque([src])
            while q and dst not in prev:
                u = q.popleft()
                for v in adj[u]:
                    if v not in prev:
                        prev[v] = u
                        q.append(v)
            if dst not in prev:
                continue
            u = dst
            while prev[u] is not None:
                keep.add((u, prev[u]) if (u, prev[u]) in es else (prev[u], u))
                u = prev[u]
    if not keep:
        return es
    return _prune(keep, stopn)


def _prune(es, stopn):
    """Cut dangling track: a chain that ends in a free end with no stop on it goes."""
    adj = {}
    for a, b in es:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    work = [n for n, v in adj.items() if len(v) == 1 and n not in stopn]
    while work:
        n = work.pop()
        if n not in adj or len(adj[n]) != 1 or n in stopn:
            continue
        (m,) = adj[n]
        adj[m].discard(n)
        del adj[n]
        if len(adj[m]) == 1 and m not in stopn:
            work.append(m)
        elif not adj[m]:
            del adj[m]
    return {(a, b) for a in adj for b in adj[a] if a < b}


def snap(tr, mp, xg, yg, W, H, streets=(), edges_=(), doms=None, segs=None, octi=None, rivers=()):
    """octi: None = octilinear per domain when there are several domains (else the square path); True forces the
    per-domain path even for one domain (a single-domain city whose rail should not stair-step either). rivers (engine v2):
    the page's river centre lines [{p: flat}], so a grade-separated line crosses one only where its real track does."""
    if not tr or not tr.get("lines"):
        return {"lines": [], "stops": [], "ge": []}
    square = False
    if octi is None:
        octi = bool(doms) and len(doms) > 1
        if not octi and not doms and mp is not None and tr.get("v", 1) >= 2:
            # a generic reading (any city but 1.9.78 Philadelphia) on the one-domain square grid: its rail runs
            # octilinear on that grid too (axis, 45 degree and index-diagonal runs, no stair-steps under a diagonal track)
            doms, octi, square = [(_RootDom(mp), _SquareLattice(xg, yg))], True, True
    if octi:
        out = _snap_octi(tr, doms, streets, edges_, segs, rivers)
        if square:                                       # the square grid's ge: (i0, j0, i1, j1) as palace_grid draws them
            out["ge"] = sorted({tuple(e[1:]) for e in out["ge"]})
        return out
    if mp is None and doms:                              # one domain: the root (page == its local frame)
        d, lat = doms[0]
        mp, xg, yg = d.mapping, list(lat.xg), list(lat.yg)
    return _snap_square(tr, mp, xg, yg, W, H, streets, edges_)


class _RootDom:
    """The one square domain of a v1 grid as a city_types.Domain for the router: real px -> grid px is `mp`."""
    id, poly, clip, holes = 0, None, None, ()

    def __init__(self, mp):
        self.mapping = mp


class _SquareLattice:
    """The v1 square grid as a Lattice: page == local, lines at xg / yg."""

    def __init__(self, xg, yg):
        self.xg, self.yg = list(xg), list(yg)

    def page(self, lx, ly):
        return (lx, ly)

    def local(self, x, y):
        return (x, y)

    def node(self, i, j):
        return (self.xg[i], self.yg[j])


def _snap_square(tr, mp, xg, yg, W, H, streets, edges_):
    P = lambda n: (round(xg[n[0]], 1), round(yg[n[1]], 1))             # grid index node -> point
    edges = {}                                           # line id -> set of edges between points
    tunnels = {}                                         # line id -> the pieces that run underground, under no street
    ge, dropped = set(), set()                           # ge: grid edges (index pairs) drawn lines run along that may need a street
    surface = [ln for ln in tr["lines"] if ln["k"] == "tram"]
    if surface:
        from .palace_transit_route import street_graph, real_points, route
        diag = []
        for st in streets:
            if st.get("d"):                              # [lead] a ... b [lead]: the clean avenue is a -> b
                q = st["p"]
                j = st.get("j", (1, 1))
                q = q[(2 if j[0] else 0):len(q) - (2 if j[1] else 0)]
                diag += [tuple(q[k:k + 4]) for k in range(0, len(q) - 3, 2)]
        adj = street_graph(list(edges_), diag)

    for ln in tr["lines"]:
        if ln["k"] == "tram":
            # a trolley runs on a street: its track is routed along the streets the grid draws; a stop no drawn
            # street comes near, or that the track cannot reach, is not drawn
            stops = [mp(st["x"], st["y"]) for st in tr["stops"]]
            under = _under(tr, ln)                       # the subway-surface tunnel's stations and portals
            es, kept, tun = route(adj, real_points(ln["w"], mp), stops, ln.get("b") or [ln["s"]],
                                  STOP_R, DEV_AVG, MAX_DEV, under)
            edges[ln["id"]] = es
            tunnels[ln["id"]] = tun
            for si in ln["s"]:
                if si not in kept:
                    dropped.add((si, ln["id"]))
            continue
        es = set()
        for w in ln["w"]:
            es |= _edges_of(w, mp, xg, yg)
        # the line keeps the track between its own stops (no yards or sidings), branch by branch
        branches = []
        for br in ln.get("b") or [ln["s"]]:
            pts = []
            for k in br:
                st = tr["stops"][k]
                gx, gy = mp(st["x"], st["y"])
                node = _stop_node(es, xg, yg, gx, gy)      # a stop with no track of its line near it is not a stop of the drawn line
                if node:
                    pts.append(node)
            branches.append(pts)
        es = _trunk(es, branches)
        ge |= {(a[0], a[1], b[0], b[1]) for a, b in es}
        edges[ln["id"]] = {(P(a), P(b)) if P(a) < P(b) else (P(b), P(a)) for a, b in es}

    def keyf(a, b):
        if a[1] == b[1]:
            return ("h", a[1])
        if a[0] == b[0]:
            return ("v", a[0])
        return None                                      # a diagonal avenue: a line keeps its centre
    out = _finish(tr, edges, tunnels, dropped, mp, keyf, lambda k: (0.0, 1.0) if k[0] == "h" else (1.0, 0.0))
    _real_on_page(tr, out, mp)
    if tr.get("v", 1) >= 2 and len(xg) > 1 and len(yg) > 1:      # a generic reading (1.9.78 Philadelphia's stays as it was)
        _trim_stubs(out, ((xg[1] - xg[0]) + (yg[1] - yg[0])) / 2)
    out["ge"] = sorted(ge)                               # ge: the grid edges the grade-separated lines run along (index pairs)
    return out


def _under(tr, ln):
    """The stops of a trolley that may stand underground (reached by a tunnel ramp, no street under them). A generic
    reading (tr["v"] == 2) says so per stop from OSM ("u": a stop on a tunnel way, or tagged underground / below
    ground level); Philadelphia's 1.9.78 reading has no such flag: there every stop not named "A & B" (a street
    corner) is a tunnel station or a portal."""
    if tr.get("v", 1) >= 2:
        return {si for si in ln["s"] if tr["stops"][si].get("u")}
    return {si for si in ln["s"] if " & " not in tr["stops"][si]["n"]}


RX_TOL = 0.4             # blocks: the real track carried onto the page (line "rx") is simplified this much


def _real_on_page(tr, out, f, blk=205.0):
    """A generic reading (tr["v"] == 2): each drawn line carries its real track mapped onto the page ("rx": flat
    polylines, simplified), so the audit can allow exactly the river crossings the real track makes (a tunnel or a
    bridge) without the raw map. The 1.9.78 reading (no "v") is left byte-identical."""
    if tr.get("v", 1) < 2:
        return
    from .palace_transit_audit import _dp
    src = {ln["id"]: ln for ln in tr["lines"]}
    for ln in out["lines"]:
        rx = []
        for w in src[ln["id"]]["w"]:
            pts = [f(w[k], w[k + 1]) for k in range(0, len(w) - 1, 2)]
            pts = [p for p in pts if p is not None]
            if len(pts) > 1:
                rx.append([round(v) for p in _dp(pts, RX_TOL * blk) for v in p])
        ln["rx"] = rx
    out["v"] = 2


def _gap_chords(ln, stops, f, blk):
    """Points along the chord between two consecutive stops of a branch whose real track has a gap between them (the
    route relation in OSM misses a way: they stand on track pieces that do not join), so the router can still join
    them; a generic reading only. Pieces join where their ends are within a quarter block."""
    polys = []
    for w in ln["w"]:
        pts = [f(w[k], w[k + 1]) for k in range(0, len(w) - 1, 2)]
        pts = [p for p in pts if p is not None]
        if pts:
            polys.append(pts)
    if not polys:
        return []
    par = list(range(len(polys)))

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    ends = [(i, p) for i, q in enumerate(polys) for p in (q[0], q[-1])]
    tol = blk / 4
    cell = {}
    for i, p in ends:
        cell.setdefault((int(p[0] // tol), int(p[1] // tol)), []).append((i, p))
    for i, p in ends:
        cx, cy = int(p[0] // tol), int(p[1] // tol)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j, q in cell.get((cx + dx, cy + dy), ()):
                    if j != i and math.hypot(p[0] - q[0], p[1] - q[1]) <= tol:
                        par[find(i)] = find(j)
    for i, q in enumerate(polys):                         # a piece that touches another mid-way (a junction) joins it too
        for j, r in enumerate(polys):
            if i < j and find(i) != find(j) and any(math.hypot(a[0] - b[0], a[1] - b[1]) <= tol
                                                     for a in (q[0], q[-1]) for b in r[::max(1, len(r) // 40)]):
                par[find(i)] = find(j)

    def piece(x, y):
        best, bi = 1e18, None
        for i, q in enumerate(polys):
            for a in q[::max(1, len(q) // 60)]:
                d = (a[0] - x) ** 2 + (a[1] - y) ** 2
                if d < best:
                    best, bi = d, i
        return find(bi) if bi is not None else None
    out = []
    for br in ln.get("b") or [ln["s"]]:
        for a, b in zip(br, br[1:]):
            (ax, ay), (bx, by) = stops[a], stops[b]
            if piece(ax, ay) != piece(bx, by):
                n = max(1, int(math.hypot(bx - ax, by - ay) // (blk / 4)))
                out += [(ax + (bx - ax) * i / n, ay + (by - ay) * i / n) for i in range(n + 1)]
    return out


def _finish(tr, edges, tunnels, dropped, mp, keyf, normal, group=2 * LANE, rel=0.0, anchor=None, gap=MAX_STOP_GAP,
            corner=0.0):
    """Lanes, polylines and stops of the routed lines. edges: {line id: {(a, b)}} page points; keyf(a, b): the lattice
    line a piece runs along ((dom, "h"|"v", index) or the square grid's ("h", y) / ("v", x)), None for a diagonal or a
    seam (a line keeps its centre there); normal(key): the page unit vector its lanes shift along. anchor: {(stop index,
    line id): page node} the router stood the stop on (its dot goes on the track there, in ride order); gap: px;
    corner (px, 0 = off): the radius the page rounds a line's turns with (palace_transit_js E.rp): a dot that would
    stand within it of a turn slides along its run to just outside it, so it is on the rounded line the page draws."""
    # lanes: lines sharing a grid line (a street) run side by side
    use = {}                                             # lattice line -> {line id: edges}
    for lid, es in edges.items():
        for a, b in es:
            key = keyf(a, b)
            if key is None:
                continue
            use.setdefault(key, {}).setdefault(lid, set()).add((a, b))
    order = [ln["id"] for ln in tr["lines"]]
    off = {}                                             # (line id, *key) -> px
    for key, per in use.items():
        lanes = {}
        for lid in order:
            if lid not in per:
                continue
            taken = {lanes[o] for o in lanes if per[o] & per[lid]}
            k = 0
            while k in taken:
                k += 1
            lanes[lid] = k
        n = max(lanes.values()) + 1
        for lid, k in lanes.items():
            off[(lid,) + tuple(key)] = (k - (n - 1) / 2) * LANE

    def at(lid, node, keys):
        if None in keys or len({k[0] for k in keys if len(k) == 3}) > 1:
            return node                                  # a diagonal (or two domains' lines) here: the centre
        x, y = node
        for k in sorted(keys, key=str):
            o = off.get((lid,) + tuple(k), 0)
            nx, ny = normal(k)
            if nx:
                x = x + o * nx
            if ny:
                y = y + o * ny
        return (round(x, 1), round(y, 1))

    def straight(a, p, c):
        """p lies on the straight run a -> c (the polyline needs only the run's ends)."""
        cr = (p[0] - a[0]) * (c[1] - p[1]) - (p[1] - a[1]) * (c[0] - p[0])
        dt = (p[0] - a[0]) * (c[0] - p[0]) + (p[1] - a[1]) * (c[1] - p[1])
        if rel and dt > 0:                               # a turned lattice: its rounded nodes are collinear to within rel
            return abs(cr) < 0.5 or abs(cr) < rel * math.hypot(p[0] - a[0], p[1] - a[1]) * math.hypot(c[0] - p[0], c[1] - p[1])
        return abs(cr) < 0.5 and dt > 0

    lines_out, geo = [], {}
    for ln in tr["lines"]:
        es = edges[ln["id"]]
        if not es:
            continue
        inc = {}
        for a, b in es:
            k = keyf(a, b)
            for n in (a, b):
                inc.setdefault(n, set()).add(k)          # the lattice lines (None: a diagonal) the line has here
        polys = []
        for path in _paths(es):
            pts = [at(ln["id"], n, inc[n]) for n in path]
            flat = []
            for k, p in enumerate(pts):                  # straight runs: only their ends
                if 0 < k < len(pts) - 1 and straight(pts[k - 1], p, pts[k + 1]):
                    continue
                flat += [p[0], p[1]]
            polys.append(flat)
        geo[ln["id"]] = polys
        lines_out.append({"id": ln["id"], "n": ln["n"], "c": ln["c"], "k": ln["k"], "p": polys, "s": ln["s"]})
        if tunnels.get(ln["id"]):                        # the tunnel pieces, whole (the audit does not look for a street over them)
            lines_out[-1]["u"] = [[v for pt in e for v in pt] for e in sorted(tunnels[ln["id"]])]

    def onto(polys, x, y):
        best, bd, at_ = None, 1e18, None
        for f in polys:
            for k in range(0, len(f) - 3, 2):
                ax, ay, bx, by = f[k], f[k + 1], f[k + 2], f[k + 3]
                dx, dy = bx - ax, by - ay
                L2 = dx * dx + dy * dy or 1e-9
                t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
                px, py = ax + t * dx, ay + t * dy
                d = math.hypot(px - x, py - y)
                if d < bd:
                    best, bd, at_ = (px, py), d, (f, k)
        if corner and best is not None:
            best = off_corner(best, *at_)
        return best, bd

    def turn_at(f, k):
        """True when the polyline f turns at its vertex k (flat index)."""
        if k < 2 or k > len(f) - 4:
            return False
        a = math.atan2(f[k + 1] - f[k - 1], f[k] - f[k - 2])
        b = math.atan2(f[k + 3] - f[k + 1], f[k + 2] - f[k])
        return abs((math.degrees(b - a) + 180.0) % 360.0 - 180.0) > 20.0

    def off_corner(p, f, k):
        ax, ay, bx, by = f[k], f[k + 1], f[k + 2], f[k + 3]
        L = math.hypot(bx - ax, by - ay)
        if L < 1e-6:
            return p
        t = math.hypot(p[0] - ax, p[1] - ay) / L
        lo = corner / L if turn_at(f, k) else 0.0
        hi = 1.0 - corner / L if turn_at(f, k + 2) else 1.0
        if lo > hi:                                      # a run shorter than two corners: its middle
            lo = hi = 0.5
        t2 = min(max(t, lo), hi)
        return p if t2 == t else (ax + t2 * (bx - ax), ay + t2 * (by - ay))

    # a stop stands ON its line: at the nearest point of every line that calls there. Lines that
    # share the street (their lanes a few px apart) share one dot, between the lanes; lines that
    # part company there (the dot would float between them) each get their own dot on their own
    # track. A line whose track never reaches the stop (it was trimmed, or its tiles never came)
    # does not call there: no dot for a stop nobody's line passes.
    stops_out, remap = [], {}                            # remap: (old stop idx, line id) -> new idx
    strict = tr.get("v", 1) >= 2                         # a generic reading: a shared dot is on every line it serves
    calls = {ln["id"]: set(ln["s"]) for ln in tr["lines"]}
    for si, s in enumerate(tr["stops"]):
        gx, gy = mp(s["x"], s["y"])
        found = []
        for lid in s["l"]:
            if si not in calls.get(lid, ()) or (si, lid) in dropped:     # a stop is a line's only if the line lists it back (and a street carries it)
                continue
            ax, ay = anchor.get((si, lid), (gx, gy)) if anchor else (gx, gy)
            p, d = onto(geo.get(lid, []), ax, ay)
            if p and d <= gap:
                found.append((lid, p))
        groups = []
        for lid, p in found:
            for g in groups:
                if all(math.hypot(p[0] - q[0], p[1] - q[1]) <= group + .1 for _, q in g) and (not strict or _mean_ok(g + [(lid, p)])):
                    g.append((lid, p))
                    break
            else:
                groups.append([(lid, p)])
        for g in groups:
            for lid, _ in g:
                remap[(si, lid)] = len(stops_out)
            stops_out.append({"n": s["n"], "x": round(sum(p[0] for _, p in g) / len(g), 1),
                              "y": round(sum(p[1] for _, p in g) / len(g), 1), "l": [lid for lid, _ in g]})
    for ln, src in zip(lines_out, [x for x in tr["lines"] if edges[x["id"]]]):
        bs = [list(dict.fromkeys(remap[(k, ln["id"])] for k in br if (k, ln["id"]) in remap))
              for br in (src.get("b") or [src["s"]])]
        ln["b"] = [b for b in bs if b]
        ln["s"] = list(dict.fromkeys(k for b in ln["b"] for k in b))
    return {"lines": lines_out, "stops": stops_out}


DOT_TOL = 3.6           # px: a shared stop dot stands this near every line it serves (palace_transit_audit.TOL)


def _mean_ok(g):
    """A group of lines may share one dot only if the dot (their mean point) is on each of them: two lanes 7 px apart
    share it, the outer two of three lanes on one street do not (they get their own dots)."""
    mx, my = sum(p[0] for _, p in g) / len(g), sum(p[1] for _, p in g) / len(g)
    return all(math.hypot(p[0] - mx, p[1] - my) <= DOT_TOL for _, p in g)


def _norm_name(n):
    n = " " + n.lower().replace(".", "").replace("-", " ") + " "
    for a, b in ((" street ", " st "), (" avenue ", " ave "), (" boulevard ", " blvd "), (" road ", " rd "),
                 (" drive ", " dr "), (" north ", " n "), (" south ", " s "), (" east ", " e "), (" west ", " w ")):
        n = n.replace(a, b)
    return " ".join(n.split())


def _named(streets):
    """{normalised name: [[(x, y), ...] page polylines]} of the drawn named streets."""
    out = {}
    for st in streets:
        if st.get("n") and len(st.get("p", ())) >= 4:
            p = st["p"]
            out.setdefault(_norm_name(st["n"]), []).append([(p[k], p[k + 1]) for k in range(0, len(p) - 1, 2)])
    return out


def _seg_d(x, y, a0, a1):
    dx, dy = a1[0] - a0[0], a1[1] - a0[1]
    L2 = dx * dx + dy * dy or 1e-9
    t = max(0.0, min(1.0, ((x - a0[0]) * dx + (y - a0[1]) * dy) / L2))
    return math.hypot(a0[0] + t * dx - x, a0[1] + t * dy - y)


def _poly_d(poly, x, y):
    return min((_seg_d(x, y, a, b) for a, b in zip(poly, poly[1:])), default=1e18)


def _stop_points(named, tr, ln, stops, r_cross, r_along, r_far):
    """Where each stop "A & B" of a trolley line stands on its drawn streets -> ({stop index: (page point, along)},
    [the drawn polylines the line runs along]). The street a run of stops shares (A of "A & 49th", "A & 50th" ...) is the
    street the line runs along: the stop stands where the drawn A crosses the drawn B (within r_cross), else on the drawn
    A (within r_far: the line rides its own street even where the domain mapping drew it a block off), never on B alone.
    Where A is drawn more than once near the line (a seam and a lattice line one block apart), every stop takes the copy
    most of the branch's stops lie along, so the line does not hop between the two. A stop with no shared street takes
    the crossing of its two streets, else the nearer of them within r_along (along = False: the caller checks it is on
    the real track)."""
    out, polys = {}, {}
    for br in ln.get("b") or [ln["s"]]:
        names = [[_norm_name(p) for p in tr["stops"][si]["n"].split(" & ")] for si in br]
        along = []
        for k, nm in enumerate(names):
            nb = [set(names[k2]) for k2 in (k - 1, k + 1) if 0 <= k2 < len(names)]
            sh = [n for n in nm if any(n in o for o in nb)]
            along.append(sh[0] if len(nm) == 2 and sh else None)
        pop = {}                                         # (name, polyline index) -> stops of this branch along it
        for si, a in zip(br, along):
            for pi, poly in enumerate(named.get(a, ()) if a else ()):
                if _poly_d(poly, *stops[si]) <= r_far:
                    pop[(a, pi)] = pop.get((a, pi), 0) + 1
        for si, a, nm in zip(br, along, names):
            if si in out or len(nm) != 2:
                continue
            if a:
                A = named.get(a, ())
                near = [(pop.get((a, pi), 0), -_poly_d(poly, *stops[si]), pi) for pi, poly in enumerate(A)
                        if _poly_d(poly, *stops[si]) <= r_far]
                if not near:
                    continue
                pi = max(near)[2]
                other = nm[1] if nm[0] == a else nm[0]
                q = _at_named({"a": [A[pi]], "b": named.get(other, ())}, "a & b", *stops[si], r_cross, r_far, only_a=True)
                if q is not None:
                    out[si] = (q, True)
                    polys[(a, pi)] = A[pi]
            else:
                q = _at_named(named, tr["stops"][si]["n"], *stops[si], r_cross, r_along)
                if q is not None:
                    out[si] = (q, False)
    return out, list(polys.values())


def _at_named(named, name, x, y, r_cross, r_along, only_a=False):
    """Where a stop called "A & B" stands on the drawn streets: the crossing of A and B nearest (x, y) within r_cross,
    else the nearest point of A (or B; only_a: A only) within r_along; None when its streets are not drawn near it."""
    parts = [_norm_name(p) for p in name.split(" & ")]
    if len(parts) != 2:
        return None
    A, B = named.get(parts[0], ()), named.get(parts[1], ())
    best, bd = None, r_cross
    for pa in A:
        for a0, a1 in zip(pa, pa[1:]):
            if min(math.hypot(a0[0] - x, a0[1] - y), math.hypot(a1[0] - x, a1[1] - y)) > r_cross + math.hypot(a1[0] - a0[0], a1[1] - a0[1]):
                continue
            for pb in B:
                for b0, b1 in zip(pb, pb[1:]):
                    rx, ry, sx, sy = a1[0] - a0[0], a1[1] - a0[1], b1[0] - b0[0], b1[1] - b0[1]
                    den = rx * sy - ry * sx
                    if abs(den) < 1e-9:
                        continue
                    t = ((b0[0] - a0[0]) * sy - (b0[1] - a0[1]) * sx) / den
                    u = ((b0[0] - a0[0]) * ry - (b0[1] - a0[1]) * rx) / den
                    if -1e-6 <= t <= 1 + 1e-6 and -1e-6 <= u <= 1 + 1e-6:
                        px, py = a0[0] + t * rx, a0[1] + t * ry
                        d = math.hypot(px - x, py - y)
                        if d < bd:
                            best, bd = (px, py), d
    if best is not None:
        return best
    bd = r_along
    for poly in list(A) + ([] if only_a else list(B)):
        for a0, a1 in zip(poly, poly[1:]):
            dx, dy = a1[0] - a0[0], a1[1] - a0[1]
            L2 = dx * dx + dy * dy or 1e-9
            t = max(0.0, min(1.0, ((x - a0[0]) * dx + (y - a0[1]) * dy) / L2))
            px, py = a0[0] + t * dx, a0[1] + t * dy
            d = math.hypot(px - x, py - y)
            if d < bd:
                best, bd = (px, py), d
    return best


def _on_polys(polys, tol=1.5):
    """u, v -> True when the street piece u-v lies on one of the page polylines (the streets a trolley's stops name)."""
    segs = [(a, b) for p in polys for a, b in zip(p, p[1:])]
    if not segs:
        return None
    cell = 400.0
    idx = {}
    for k, (a, b) in enumerate(segs):
        for c in _cells(a, b, cell):
            idx.setdefault(c, []).append(k)

    def on(u, v):
        cx, cy = int((u[0] + v[0]) / 2 // cell), int((u[1] + v[1]) / 2 // cell)
        for k in idx.get((cx, cy), ()):
            a, b = segs[k]
            if _seg_d(u[0], u[1], a, b) <= tol and _seg_d(v[0], v[1], a, b) <= tol:
                return True
        return False
    return on


def _cells(a, b, cell):
    n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) // (cell / 2)) + 1)
    return {(int((a[0] + (b[0] - a[0]) * k / n) // cell), int((a[1] + (b[1] - a[1]) * k / n) // cell)) for k in range(n + 1)}


def _track_dir(real, x, y):
    """The unit direction of the real track (page samples) where it passes nearest (x, y), or None."""
    if len(real) < 3:
        return None
    k = min(range(len(real)), key=lambda i: (real[i][0] - x) ** 2 + (real[i][1] - y) ** 2)
    a, b = real[max(0, k - 2)], real[min(len(real) - 1, k + 2)]
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    return ((b[0] - a[0]) / L, (b[1] - a[1]) / L) if L > 1e-6 else None


def _cut(f, a0, a1):
    """The part of flat polyline f between arc lengths a0 and a1."""
    out, run = [], 0.0
    for k in range(0, len(f) - 3, 2):
        x0, y0, x1, y1 = f[k], f[k + 1], f[k + 2], f[k + 3]
        L = math.hypot(x1 - x0, y1 - y0)
        if L > 0 and run + L >= a0 and run <= a1:
            t0, t1 = max(0.0, (a0 - run) / L), min(1.0, (a1 - run) / L)
            p0 = (round(x0 + (x1 - x0) * t0, 1), round(y0 + (y1 - y0) * t0, 1))
            p1 = (round(x0 + (x1 - x0) * t1, 1), round(y0 + (y1 - y0) * t1, 1))
            if not out:
                out += list(p0)
            out += list(p1)
        run += L
    return out


def _trim_stubs(out, blk, keep=1.0):
    """A track end that is joined to nothing and runs on more than palace_transit_audit.STUB_BLOCKS past its last drawn stop
    (the stop beyond was not drawn: no street carried it) is cut `keep` blocks past that stop."""
    from .palace_transit_audit import _near, STUB_BLOCKS, TOL
    stops = out.get("stops") or []
    for ln in out.get("lines") or []:
        polys = ln.get("p") or []
        idx = set(ln.get("s") or []) | {i for br in ln.get("b") or [] for i in br}
        pts = [(stops[i]["x"], stops[i]["y"]) for i in idx if i < len(stops)]
        for pi, f in enumerate(polys):
            if len(f) < 4:
                continue
            arcs = [a for d, _p, a in (_near([f], x, y) for x, y in pts) if d <= TOL]
            if not arcs:
                continue
            L = sum(math.hypot(f[k + 2] - f[k], f[k + 3] - f[k + 1]) for k in range(0, len(f) - 3, 2))

            def free(x, y):
                return not any(_near([g], x, y)[0] <= 1.5 for gi, g in enumerate(polys) if gi != pi)
            a0, a1 = 0.0, L
            if free(f[0], f[1]) and min(arcs) > STUB_BLOCKS * blk:
                a0 = min(arcs) - keep * blk
            if free(f[-2], f[-1]) and L - max(arcs) > STUB_BLOCKS * blk:
                a1 = max(arcs) + keep * blk
            if (a0, a1) != (0.0, L):
                polys[pi] = _cut(f, a0, a1)


def _snap_octi(tr, doms, streets, edges_, segs, rivers=()):
    """Several domains: trolleys on the drawn streets at any angle, grade-separated lines octilinear per domain."""
    from .palace_transit_route import CityMap, street_graph, drawn_segs, real_points, route, octi_route, _Track, _split_node, octi2_in
    cm = CityMap(doms)
    blk = cm.blk                                         # every size in blocks of this page (any CW x CH)
    edges, tunnels, dropped, ge, rkey, anchor = {}, {}, set(), set(), {}, {}
    laid, stood = set(), {}                              # edges and station nodes earlier grade-separated lines took
    if any(ln["k"] == "tram" for ln in tr["lines"]):
        adj = street_graph(list(segs if segs is not None else drawn_segs(edges=edges_, streets=streets)))
    stops0 = [cm(st["x"], st["y"]) for st in tr["stops"]]

    def stops_for(lid):
        """The stops in page px as this line sees them: a station of several lines (a generic reading) stands at the
        line's own platform ("lp"), not at the middle of the whole complex."""
        if not any(st.get("lp") for st in tr["stops"]):
            return stops0
        return [cm(*st["lp"][lid]) if lid in (st.get("lp") or {}) else p for st, p in zip(tr["stops"], stops0)]
    pre, pref = {}, {}                                   # every trolley stop on its street first (the piece cut there),
    named = _named(streets) if any(ln["k"] == "tram" for ln in tr["lines"]) else {}
    for ln in tr["lines"]:                               # so no line's track holds a piece another line's stop later cuts
        if ln["k"] == "tram":
            stops = stops_for(ln["id"])
            real = real_points(ln["w"], cm)
            trk = _Track(real, blk / 2)
            onst, along = _stop_points(named, tr, ln, stops, V2["named"] * blk, V2["along"] * blk, V2["far"] * blk)
            pref[ln["id"]] = along
            for si in dict.fromkeys(k for br in (ln.get("b") or [ln["s"]]) for k in br):
                n = None
                q, al = onst.get(si, (None, False))
                if q is not None and (al or trk.d(q[0], q[1], blk) <= V2["along"] * blk):     # its own streets, as drawn, on its track
                    n = _split_node(adj, q[0], q[1], 2.0, V2["split"] * blk)
                if n is None:
                    n = _split_node(adj, stops[si][0], stops[si][1], V2["stop_r"] * blk, V2["split"] * blk,
                                    _track_dir(real, *stops[si]))
                if n is not None:
                    pre[(si, ln["id"])] = n
    for ln in tr["lines"]:
        stops = stops_for(ln["id"])
        real = real_points(ln["w"], cm)
        if tr.get("v", 1) >= 2:
            real = real + _gap_chords(ln, stops, cm, blk)
        at = {si: n for (si, lid), n in pre.items() if lid == ln["id"]}
        if ln["k"] == "tram":
            under = _under(tr, ln)
            es, kept, tun = route(adj, real, stops, ln.get("b") or [ln["s"]],
                                  V2["stop_r"] * blk, V2["dev_avg"] * blk, V2["max_dev"] * blk, under,
                                  ramp=V2["ramp"] * blk, bend=V2["bend"] * blk, split=V2["split"] * blk, carry=True,
                                  anchors=at, track=_Track(real, blk / 2), slack=V2["slack"] * blk, share=0.5,
                                  tunnels_first=True, pref=_on_polys(pref.get(ln["id"], ())), octi2=octi2_in(cm))
            edges[ln["id"]] = es
            tunnels[ln["id"]] = tun
            dropped |= {(si, ln["id"]) for si in ln["s"] if si not in kept}
        else:
            gen = tr.get("v", 1) >= 2                   # a generic reading: lines on one real trunk share its corridor
            es, kept, info = octi_route(cm, real, stops, ln.get("b") or [ln["s"]], anchors=at, rivers=rivers,
                                        shared=laid if gen else None, prefer=stood if gen else None)
            laid |= es
            for si, n in at.items():
                stood.setdefault(si, n)
            edges[ln["id"]] = es
            for e, inf in info.items():
                if inf is None:
                    continue
                d, i0, j0, i1, j1 = inf
                if j0 == j1 or i0 == i1:
                    rkey[e] = (d, "h", j0) if j0 == j1 else (d, "v", i0)
                    ge.add((d,) + min((i0, j0), (i1, j1)) + max((i0, j0), (i1, j1)))
                else:
                    rkey[e] = None
        anchor.update({(si, ln["id"]): p for si, p in at.items()})

    def keyf(a, b):
        e = (a, b) if a < b else (b, a)
        return rkey[e] if e in rkey else cm.lane_key(a, b)
    out = _finish(tr, edges, tunnels, dropped, cm, keyf, cm.normal, group=LANE, rel=2e-3,   # one dot per pair of next lanes
                  anchor=anchor, gap=V2["gap"] * blk, corner=CORNER)
    _real_on_page(tr, out, cm, blk)
    _trim_stubs(out, blk)
    out["ge"] = sorted(ge)                               # (dom, i0, j0, i1, j1): lattice edges a grade-separated line runs along
    return out
