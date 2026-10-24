"""The Memory Palace's city as a diagram: a basic grid, the exceptions only where
the city really has them.

palace_map.build_map gives the real geometry. A Memory Palace does not want
that — it wants the city the way a subway map wants it: the main streets
straightened into a level, upright grid (the whole map turned so its own
street grid runs square to the screen), a street that truly runs on a slant
(a parkway, an old turnpike) kept as one clean diagonal, the river a simple
band, railways the same straight lines, landmarks a name and a point. Small
streets, alleys, parks' shapes and building outlines are left out.

schematic(m, keep=None) → a map dict of the same shape (W, H, streets, water,
rivers, trails, rails, stations, landmarks, majors), plus "rot" — how the
real map was turned and moved — so district bounds given in latitude and
longitude land in the same place (palace_place.to_px reads it).
"""
from __future__ import annotations

import math

SNAP_DEG = 22          # a stretch within this of level / upright becomes level / upright
TOL = 24               # simplification of the real lines, map px
MERGE = 16             # parallel lines closer than this are one line
REACH = 60             # a line's end reaches on to a crossing line this close
MIN_LEN = 450          # a kept street shorter than this (after merging) is left out


def _dp(pts, tol):
    """Douglas–Peucker on [(x, y), ...]."""
    if len(pts) < 3:
        return pts
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy) or 1e-9
    i_best, d_best = 0, -1.0
    for i in range(1, len(pts) - 1):
        d = abs(dy * (pts[i][0] - x0) - dx * (pts[i][1] - y0)) / L
        if d > d_best:
            i_best, d_best = i, d
    if d_best <= tol:
        return [pts[0], pts[-1]]
    return _dp(pts[:i_best + 1], tol)[:-1] + _dp(pts[i_best:], tol)


def _dp_ring(pts, tol):
    """Douglas–Peucker on a closed ring: split at the point farthest from the first."""
    if len(pts) < 4:
        return pts
    k = max(range(len(pts)), key=lambda i: (pts[i][0] - pts[0][0]) ** 2 + (pts[i][1] - pts[0][1]) ** 2)
    a = _dp(pts[:k + 1], tol)
    b = _dp(pts[k:] + [pts[0]], tol)
    return a[:-1] + b[:-1]


def _seg_dist(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy or 1e-9
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(a[0] + t * dx - p[0], a[1] + t * dy - p[1])


def _pairs(flat):
    return [(flat[i], flat[i + 1]) for i in range(0, len(flat) - 1, 2)]


def grid_angle(m, names=None) -> float:
    """The city's own street grid, as one angle (radians, mod 90°), from its main streets."""
    sx = sy = 0.0
    for s in m.get("streets", []):
        if s.get("t") or s.get("k", 9) > 2 or (names is not None and s.get("n") not in names):
            continue
        p = s["p"]
        for i in range(0, len(p) - 2, 2):
            L = math.hypot(p[i + 2] - p[i], p[i + 3] - p[i + 1])
            th = math.atan2(p[i + 3] - p[i + 1], p[i + 2] - p[i])
            sx += L * math.cos(4 * th); sy += L * math.sin(4 * th)
    return math.atan2(sy, sx) / 4 if (sx or sy) else 0.0


def _kind(a, b):
    ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180
    if ang < SNAP_DEG or ang > 180 - SNAP_DEG:
        return "h"
    if abs(ang - 90) < SNAP_DEG:
        return "v"
    return "d"


def _runs(lines, axis):
    """Level (axis 'h') or upright ('v') stretches → merged lines [(at, lo, hi, name, k)]:
    stretches of one street at about the same height join; gaps under 160 px close."""
    out = []
    by = {}
    for (n, k, a, b) in lines:
        at = (a[1] + b[1]) / 2 if axis == "h" else (a[0] + b[0]) / 2
        lo, hi = sorted((a[0], b[0]) if axis == "h" else (a[1], b[1]))
        by.setdefault(n, []).append([at, lo, hi, k, hi - lo])
    for n, segs in by.items():
        segs.sort(key=lambda s: s[0])
        groups = []
        for s in segs:
            g = next((g for g in groups if abs(g["at"] - s[0]) < 45), None)
            if g is None:
                g = {"at": s[0], "w": 0.0, "segs": []}
                groups.append(g)
            g["segs"].append(s)
            w = sum(x[4] for x in g["segs"]) or 1
            g["at"] = sum(x[0] * x[4] for x in g["segs"]) / w
        for g in groups:
            iv = sorted((s[1], s[2], s[3]) for s in g["segs"])
            cur = list(iv[0])
            for lo, hi, k in iv[1:]:
                if lo <= cur[1] + 420:
                    cur[1] = max(cur[1], hi); cur[2] = min(cur[2], k)
                else:
                    out.append((g["at"], cur[0], cur[1], n, cur[2])); cur = [lo, hi, k]
            out.append((g["at"], cur[0], cur[1], n, cur[2]))
    return out


def _snap_coords(vals, tol):
    """Cluster a list of coordinates; each maps to its cluster's mean."""
    order = sorted(set(vals))
    clusters, cur = [], []
    for v in order:
        if cur and v - cur[-1] > tol:
            clusters.append(cur); cur = []
        cur.append(v)
    if cur:
        clusters.append(cur)
    out = {}
    for c in clusters:
        mean = sum(c) / len(c)
        for v in c:
            out[v] = mean
    return out


def _turn(m, th):
    """A function turning real map px about the map's centre by -th."""
    cx, cy = m["W"] / 2, m["H"] / 2
    c, s = math.cos(-th), math.sin(-th)

    def f(x, y):
        x, y = x - cx, y - cy
        return (x * c - y * s + cx, x * s + y * c + cy)
    return f


def schematic(m, keep=None) -> dict:
    """The diagram of a real map (see the module docstring). keep: street names to
    keep besides the main ones (k ≤ 2); the map's `majors` always stay."""
    majors = set(m.get("majors") or [])
    keepset = set(keep or []) | majors
    th = grid_angle(m)
    turn = _turn(m, th)

    # ── streets: straightened, merged, snapped to one grid ──
    # a street is kept whole once any stretch of it is a main road (OSM grades a
    # street block by block; the diagram draws the street)
    names = {s["n"] for s in m.get("streets", []) if s.get("n") and not s.get("t")
             and (s["n"] in keepset or s.get("k", 9) <= 2)}
    level, upright, slant = [], [], []
    for s in m.get("streets", []):
        if s.get("t") or s.get("n") not in names or s.get("k", 9) >= 5:
            continue
        pts = _dp([turn(x, y) for x, y in _pairs(s["p"])], TOL)
        for a, b in zip(pts, pts[1:]):
            if math.hypot(b[0] - a[0], b[1] - a[1]) < 8:
                continue
            kd = _kind(a, b)
            (level if kd == "h" else upright if kd == "v" else slant).append((s["n"], s.get("k", 4), a, b))
    H = _runs(level, "h")
    V = _runs(upright, "v")
    H = [h for h in H if h[2] - h[1] >= MIN_LEN or h[3] in majors]
    V = [v for v in V if v[2] - v[1] >= MIN_LEN or v[3] in majors]
    ys = _snap_coords([h[0] for h in H], MERGE)
    xs = _snap_coords([v[0] for v in V], MERGE)
    H = [(ys[h[0]],) + h[1:] for h in H]
    V = [(xs[v[0]],) + v[1:] for v in V]
    # a line's end reaches on to the crossing line it nearly meets, so the grid joins up
    def reach(lines, cross):
        out = []
        for at, lo, hi, n, k in lines:
            near_lo = [c[0] for c in cross if abs(c[0] - lo) < REACH and c[1] - 20 <= at <= c[2] + 20]
            near_hi = [c[0] for c in cross if abs(c[0] - hi) < REACH and c[1] - 20 <= at <= c[2] + 20]
            if near_lo:
                lo = min(near_lo, key=lambda c: abs(c - lo))
            if near_hi:
                hi = min(near_hi, key=lambda c: abs(c - hi))
            out.append((at, lo, hi, n, k))
        return out
    H2, V2 = reach(H, V), reach(V, H)
    streets = [{"n": n, "k": k, "p": [round(lo, 1), round(at, 1), round(hi, 1), round(at, 1)]} for at, lo, hi, n, k in H2]
    streets += [{"n": n, "k": k, "p": [round(at, 1), round(lo, 1), round(at, 1), round(hi, 1)]} for at, lo, hi, n, k in V2]
    # the slants: each street's slanted stretches, chained, one clean line each
    by: dict = {}
    for n, k, a, b in slant:
        by.setdefault((n, k), []).append((a, b))
    for (n, k), segs in by.items():
        chains = []
        for a, b in segs:
            for ch in chains:
                if math.hypot(ch[-1][0] - a[0], ch[-1][1] - a[1]) < 30:
                    ch.append(b); break
                if math.hypot(ch[0][0] - b[0], ch[0][1] - b[1]) < 30:
                    ch.insert(0, a); break
            else:
                chains.append([a, b])
        for ch in chains:
            ch = _dp(ch, TOL * 2)
            L = sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(ch, ch[1:]))
            if L < 260 and n not in majors:
                continue
            # its ends land on the grid where it meets it
            def land(p):
                best, bd = p, REACH
                for at, lo, hi, *_ in H2:
                    if lo - 10 <= p[0] <= hi + 10 and abs(p[1] - at) < bd:
                        best, bd = (p[0], at), abs(p[1] - at)
                for at, lo, hi, *_ in V2:
                    if lo - 10 <= p[1] <= hi + 10 and abs(p[0] - at) < bd:
                        best, bd = (at, p[1]), abs(p[0] - at)
                return best
            ch[0], ch[-1] = land(ch[0]), land(ch[-1])
            streets.append({"n": n, "k": k, "p": [round(v, 1) for q in ch for v in q]})

    # ── the frame: everything kept, turned, moved to start at the corner ──
    allx = [v for s in streets for v in s["p"][0::2]]
    ally = [v for s in streets for v in s["p"][1::2]]
    x0, y0 = min(allx) - 40, min(ally) - 40
    x1, y1 = max(allx) + 40, max(ally) + 40

    def mv(x, y):
        return (round(x - x0, 1), round(y - y0, 1))

    def flat(pts):
        return [v for p in pts for v in mv(*p)]
    for s in streets:
        s["p"] = flat(_pairs(s["p"]))

    def inside(p):
        return x0 - 300 <= p[0] <= x1 + 300 and y0 - 300 <= p[1] <= y1 + 300

    # ── the river: its big bodies of water, simplified to a band ──
    water = []
    for r in m.get("water", []):
        pts = [turn(x, y) for x, y in _pairs(r)]
        a = 0.0
        for (px, py), (qx, qy) in zip(pts, pts[1:] + pts[:1]):
            a += px * qy - qx * py
        if abs(a) / 2 < 15000:
            continue
        pts = _dp_ring(pts, 28)
        if len(pts) >= 3:
            water.append(flat(pts))
    rivers = []
    for r in m.get("rivers", []):
        pts = _dp([turn(x, y) for x, y in _pairs(r["p"])], 40)
        if len(pts) >= 2:
            rivers.append({"n": r["n"], "p": flat(pts)})

    # ── railways: main lines and subways (no trolleys), straightened like the
    #    streets; a line's parallel tracks fold into one ──
    pieces = []
    for r in m.get("rails", []):
        if r.get("k") not in ("rail", "subway") or not (r.get("c") or r.get("n")):
            continue                      # a named line only: no yards, sidings, freight spurs
        pts = _dp([turn(x, y) for x, y in _pairs(r["p"])], TOL)
        out = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            kd = _kind(a, b)
            if kd == "h":
                yy = (a[1] + b[1]) / 2
                out[-1] = (out[-1][0], yy); out.append((b[0], yy))
            elif kd == "v":
                xx = (a[0] + b[0]) / 2
                out[-1] = (xx, out[-1][1]); out.append((xx, b[1]))
            else:
                out.append(b)
        L = sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(out, out[1:]))
        pieces.append((L, r, out))
    pieces.sort(key=lambda t: -t[0])
    kept_segs: list = []                  # (a, b) of every track already drawn
    rails = []
    for L, r, out in pieces:
        run, runs = [out[0]], []
        for a, b in zip(out, out[1:]):
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            dup = any(_seg_dist(mid, c, d) < 30 for c, d in kept_segs)
            if dup:
                if len(run) > 1:
                    runs.append(run)
                run = [b]
            else:
                run.append(b)
        if len(run) > 1:
            runs.append(run)
        for run in runs:
            RL = sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(run, run[1:]))
            if RL < 260:
                continue
            kept_segs.extend(zip(run, run[1:]))
            rails.append({**{k: v for k, v in r.items() if k != "p"}, "p": flat(run)})
    trails = []
    for t in m.get("trails", []):
        pts = _dp([turn(x, y) for x, y in _pairs(t["p"])], TOL)
        L = sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(pts, pts[1:]))
        if L >= 600:
            trails.append({"n": t["n"], "p": flat(pts)})
    stations = []
    for s in m.get("stations", []):
        if s.get("k") not in ("rail", "subway"):
            continue
        x, y = mv(*turn(s["x"], s["y"]))
        stations.append({**s, "x": x, "y": y})
    landmarks = []
    for l in m.get("landmarks", []):
        x, y = mv(*turn(l["x"], l["y"]))
        if "station" in l["n"].lower() and any(math.hypot(st["x"] - x, st["y"] - y) < 220 for st in stations):
            continue                      # the station names it already
        landmarks.append({"n": l["n"], "x": x, "y": y, "r": []})
    W, Hh = int(math.ceil(x1 - x0)), int(math.ceil(y1 - y0))
    return {**{k: v for k, v in m.items() if k not in ("streets", "water", "rivers", "rails", "trails",
                                                      "stations", "landmarks", "parks", "W", "H")},
            "W": W, "H": Hh, "streets": streets, "water": water, "rivers": rivers, "rails": rails,
            "trails": trails, "stations": stations, "landmarks": landmarks, "parks": [],
            "rot": {"t": round(th, 6), "cx": m["W"] / 2, "cy": m["H"] / 2, "dx": round(x0, 2), "dy": round(y0, 2)},
            "schematic": 1}
