"""The palace's real transit, drawn like its streets: the lines palace_map reads
from the route relations (SEPTA's subways, trolleys and Regional Rail, PATCO)
are carried onto the palace's even grid. Every rail way is snapped to the grid
lines (straight runs, square turns — the page rounds them like its streets), a
line that shares a street with another runs in its own lane beside it, and the
stations stand on their lines.

    snap(tr, mp, xg, yg, W, H) -> {"lines": [{id, n, c, k, p: [flat polylines], s: [stop idx]}],
                                    "stops": [{n, x, y, l: [line ids]}],
                                    "ge": [(i0, j0, i1, j1)]  # the grid edges the lines run along (palace_grid draws a street
                                                              # under any that has none: a line never runs through a void)}
"""
from __future__ import annotations

import math
from bisect import bisect_left

LANE = 7.0              # px between two lines that share a street
MAX_STOP_GAP = 130.0    # a stop farther than this from its line (about half a block) is not drawn: its track was trimmed or never fetched


def _near(v, G):
    """Index of the grid coordinate nearest v."""
    i = bisect_left(G, v)
    if i <= 0:
        return 0
    if i >= len(G):
        return len(G) - 1
    return i if G[i] - v < v - G[i - 1] else i - 1


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


def _trunk(es, pts):
    """A line's track between its own stops. OSM carries every siding and yard a
    route touches, and on the grid they read as boxy loops; the shortest ways
    between the line's stops are the line. `pts` are the stops' nodes. A line
    that does not connect up (or has under two stops) keeps all its edges."""
    from collections import deque
    adj = {}
    for a, b in es:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    nodes = list(adj)
    if len(pts) < 2 or not nodes:
        return es
    snapped = []
    for x, y in pts:
        snapped.append(min(nodes, key=lambda n: (n[0] - x) ** 2 + (n[1] - y) ** 2))
    snapped = list(dict.fromkeys(snapped))
    keep = set()
    for i, src in enumerate(snapped):
        prev = {src: None}
        q = deque([src])
        while q:
            u = q.popleft()
            for v in adj[u]:
                if v not in prev:
                    prev[v] = u
                    q.append(v)
        for dst in snapped[i + 1:]:
            if dst not in prev:
                continue
            u = dst
            while prev[u] is not None:
                keep.add((u, prev[u]) if (u, prev[u]) in es else (prev[u], u))
                u = prev[u]
    return keep or es


def snap(tr, mp, xg, yg, W, H):
    if not tr or not tr.get("lines"):
        return {"lines": [], "stops": [], "ge": []}
    edges = {}                                           # line id -> set of unit edges
    for ln in tr["lines"]:
        es = set()
        for w in ln["w"]:
            es |= _edges_of(w, mp, xg, yg)
        edges[ln["id"]] = es

    # each line keeps the track between its own stops (no yards or sidings)
    for ln in tr["lines"]:
        pts = []
        for k in ln["s"]:
            st = tr["stops"][k]
            gx, gy = mp(st["x"], st["y"])
            pts.append((_near(gx, xg), _near(gy, yg)))
        edges[ln["id"]] = _trunk(edges[ln["id"]], pts)

    # lanes: lines sharing a grid line (a street) run side by side
    use = {}                                             # (axis, index) -> {line id: edges}
    for lid, es in edges.items():
        for a, b in es:
            key = ("h", a[1]) if a[1] == b[1] else ("v", a[0])
            use.setdefault(key, {}).setdefault(lid, set()).add((a, b))
    order = [ln["id"] for ln in tr["lines"]]
    off = {}                                             # (line id, axis, index) -> px
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
            off[(lid, key[0], key[1])] = (k - (n - 1) / 2) * LANE

    def at(lid, node, es_nodes):
        i, j = node
        hz, vt = es_nodes
        x = xg[i] + (off.get((lid, "v", i), 0) if vt else 0)
        y = yg[j] + (off.get((lid, "h", j), 0) if hz else 0)
        return (round(x, 1), round(y, 1))

    lines_out, geo = [], {}
    for ln in tr["lines"]:
        es = edges[ln["id"]]
        if not es:
            continue
        inc = {}
        for a, b in es:
            for n, o in ((a, b), (b, a)):
                f = inc.setdefault(n, [False, False])
                f[0 if a[1] == b[1] else 1] = True       # [horizontal edge here, vertical edge here]
        polys = []
        for path in _paths(es):
            pts = [at(ln["id"], n, inc[n]) for n in path]
            flat = []
            for k, p in enumerate(pts):                  # straight runs: only their ends
                if 0 < k < len(pts) - 1 and ((pts[k - 1][0] == p[0] == pts[k + 1][0]) or
                                             (pts[k - 1][1] == p[1] == pts[k + 1][1])):
                    continue
                flat += [p[0], p[1]]
            polys.append(flat)
        geo[ln["id"]] = polys
        lines_out.append({"id": ln["id"], "n": ln["n"], "c": ln["c"], "k": ln["k"], "p": polys, "s": ln["s"]})

    def onto(polys, x, y):
        best, bd = None, 1e18
        for f in polys:
            for k in range(0, len(f) - 3, 2):
                ax, ay, bx, by = f[k], f[k + 1], f[k + 2], f[k + 3]
                dx, dy = bx - ax, by - ay
                L2 = dx * dx + dy * dy or 1e-9
                t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
                px, py = ax + t * dx, ay + t * dy
                d = math.hypot(px - x, py - y)
                if d < bd:
                    best, bd = (px, py), d
        return best, bd

    # a stop stands ON its line: at the nearest point of every line that calls there. Lines that
    # share the street (their lanes a few px apart) share one dot, between the lanes; lines that
    # part company there (the dot would float between them) each get their own dot on their own
    # track. A line whose track never reaches the stop (it was trimmed, or its tiles never came)
    # does not call there: no dot for a stop nobody's line passes.
    stops_out, remap = [], {}                            # remap: (old stop idx, line id) -> new idx
    calls = {ln["id"]: set(ln["s"]) for ln in tr["lines"]}
    for si, s in enumerate(tr["stops"]):
        gx, gy = mp(s["x"], s["y"])
        found = []
        for lid in s["l"]:
            if si not in calls.get(lid, ()):                 # a stop is a line's only if the line lists it back
                continue
            p, d = onto(geo.get(lid, []), gx, gy)
            if p and d <= MAX_STOP_GAP:
                found.append((lid, p))
        groups = []
        for lid, p in found:
            for g in groups:
                if all(math.hypot(p[0] - q[0], p[1] - q[1]) <= 2 * LANE + .1 for _, q in g):
                    g.append((lid, p))
                    break
            else:
                groups.append([(lid, p)])
        for g in groups:
            for lid, _ in g:
                remap[(si, lid)] = len(stops_out)
            stops_out.append({"n": s["n"], "x": round(sum(p[0] for _, p in g) / len(g), 1),
                              "y": round(sum(p[1] for _, p in g) / len(g), 1), "l": [lid for lid, _ in g]})
    for ln in lines_out:
        ln["s"] = list(dict.fromkeys(remap[(k, ln["id"])] for k in ln["s"] if (k, ln["id"]) in remap))
    ge = sorted({(a[0], a[1], b[0], b[1]) for es in edges.values() for a, b in es})
    return {"lines": lines_out, "stops": stops_out, "ge": ge}      # ge: every grid edge a line runs along (index pairs)
