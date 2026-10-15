"""A trolley runs ON a street. The router here carries a surface line onto the streets the palace's grid actually draws:
the unit grid edges and the clean diagonal avenues (the Parkway, Woodland, Chester ...). Each stop is put on the nearest drawn
street (no street within STOP_R of it: the stop is dropped, it would float), and consecutive stops are joined by the cheapest
way along drawn streets, cheap meaning close to where the real track runs. Nothing here ever draws a street: a track it
returns lies on streets by construction, a diagonal stays one clean diagonal line, and a stop no street supports is gone.

    street_graph(edges, diag)            -> {node: {node: length}}   (nodes are (x, y) rounded to 0.1 px)
    route(adj, real, stops, ...)         -> (edges, kept stop indices)
"""
from __future__ import annotations

import heapq
import math

CELL = 80.0


def _k(x, y):
    return (round(x + 0.0, 1), round(y + 0.0, 1))


def street_graph(edges, diag):
    """edges: unit grid edges [x0, y0, x1, y1] (axis-aligned); diag: [(ax, ay, bx, by)], the clean diagonal avenues.
    A diagonal is cut at every grid edge it crosses (so a trolley can turn off it there) and a grid edge it crosses is
    cut at the crossing."""
    adj = {}
    cuts = {}                                   # edge index -> [crossing points]

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


def route(adj, real, stops, branches, radius=85.0, dev_avg=60.0, max_dev=110.0, under=(), why=None):
    """stops: [(x, y)] in grid px; branches: lists of indices into stops, in ride order; under: the indices of the stops
    that are underground stations (a tunnel needs no street: two such stops that no street joins are joined by a straight
    tunnel). Returns (edges, kept, tunnel) where edges is a set of ((x, y), (x, y)) pieces (each ordered low to high),
    kept the set of stop indices the line calls at and tunnel the pieces that run under no street. why: a list that
    collects why a pair of stops was not joined."""
    b = _bucket(real)
    memo = {}

    def dv(u, v):
        key = (u, v) if u < v else (v, u)
        if key not in memo:
            memo[key] = _edge_dev(b, *key)
        return memo[key]

    def cost(u, v, L):
        return L * (1 + (dv(u, v) / dev_avg) ** 2)
    es, kept, tunnel = set(), set(), set()
    for br in branches:
        nodes = []                              # (stop index, node)
        for si in br:
            n = stop_node(adj, b, stops[si][0], stops[si][1], radius)
            if n is None and si in under:       # an underground station off every street stands where it is
                n = _k(*stops[si])
            if n is not None:
                nodes.append((si, n))
        runs, cur = [], None                    # unbroken runs of stops: [stop indices, edges, tunnel edges]
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
                path = _dijkstra(adj, cost, na, nb) if na in adj and nb in adj else None
                straight = math.hypot(na[0] - nb[0], na[1] - nb[1])
                bad = None
                if not path:
                    bad = "no street joins them"
                else:
                    plen = sum(adj[u][v] for u, v in zip(path, path[1:]))
                    mdev = sum(dv(u, v) * adj[u][v] for u, v in zip(path, path[1:])) / (plen or 1)
                    if mdev > max_dev:
                        bad = "the streets between them stray %d px from the real track" % mdev
                    elif plen > 2.2 * straight + 450:
                        bad = "the streets between them are a %d px detour for %d px" % (plen, straight)
                if not bad:
                    got = ({(u, v) if u < v else (v, u) for u, v in zip(path, path[1:])}, set())
                elif sa in under and sb in under:   # a tunnel between two underground stations
                    e = (na, nb) if na < nb else (nb, na)
                    got = ({e}, {e})
                elif why is not None:
                    why.append((sa, sb, bad))
            if got is None:                     # no track joins them: the ride ends here, a new run starts
                runs.append(cur)
                cur = None
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
    return es, kept, tunnel
