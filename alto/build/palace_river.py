"""The rivers of the Memory Palace city: smooth bands, not map lines.

The grid (palace_grid) carries the streets onto graph paper, stretching the real
map unevenly, so a river carried point by point comes out lumpy. Here a river is
designed instead:

- its course is the longest piece of its OpenStreetMap centre line (never the
  banks, side channels and islands folded together), carried onto the grid,
  then smoothed so it bends only where the river really bends, with a few wide
  curves and no kinks;
- it runs off the edge of the city at both ends (the page clips it to the glass);
- a wide river that is the city's edge (palace_map._across_wide_river: the
  Delaware at Philadelphia; the land across it is not drawn) is a broad band
  along that edge of the grid, leaning the way the real river leans, with the
  glass margin widened to hold it;
- one band width per kind of river, whatever the real width, so the city looks
  designed (a street-sized one for the narrow river, a broad one for the wide).

rivers(m, mp, xg, yg, cw, ch, W, H) -> (river, W): [{n, w, p}] with p a flat
list of smooth, evenly spaced grid px points, and the glass width the grid needs.
"""
from __future__ import annotations

import math

NARROW_W = 100            # a river a city's streets bridge (the Schuylkill)
WIDE_W = 230              # the river a city stands on the edge of (the Delaware)
STEP = 40.0               # px between the points of a smoothed course
SIGMA = 320.0             # px: how far the smoothing reaches along the course
LEAN = 0.22               # how much of the wide river's real lean the band keeps
GAP = 56                  # grid px between the last column and the wide river's near bank
EDGE = 70                 # glass past a river's far bank
RUN_OFF = 3200            # px a course is carried on past the ends it already has


def _pairs(flat):
    return [(flat[i], flat[i + 1]) for i in range(0, len(flat) - 1, 2)]


def _len(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def _main_piece(rivers, name):
    best, bl = None, 0.0
    for r in rivers:
        if r.get("n") != name:
            continue
        p = _pairs(r["p"])
        if len(p) >= 2 and _len(p) > bl:
            best, bl = p, _len(p)
    return best


def _channel_line(rivers, name, tol=30.0):
    """A named river's pieces joined end to end (OSM splits a river into many ways): the longest course."""
    ways = [_pairs(r["p"]) for r in rivers if r.get("n") == name and len(r.get("p") or ()) >= 4]
    chains = []
    while ways:
        ch = list(ways.pop(0))
        grew = True
        while grew:
            grew = False
            for k, w in enumerate(ways):
                if math.dist(w[0], ch[-1]) < tol:
                    ch += w[1:]
                elif math.dist(w[-1], ch[0]) < tol:
                    ch = w[:-1] + ch
                elif math.dist(w[-1], ch[-1]) < tol:
                    ch += w[::-1][1:]
                elif math.dist(w[0], ch[0]) < tol:
                    ch = w[::-1][:-1] + ch
                else:
                    continue
                ways.pop(k)
                grew = True
                break
        chains.append(ch)
    return max(chains, key=_len, default=None)


def river_line(m, name):
    """The real line a page river band is drawn from: a named channel's whole course (m["channels"]), else its longest
    piece."""
    keep = {str(n).lower() for n in m.get("channels") or ()}
    return _channel_line(m.get("rivers", []), name) if str(name).lower() in keep else _main_piece(m.get("rivers", []), name)


def resample(pts, step=STEP):
    """Points evenly `step` apart along the polyline (the last one is kept)."""
    if len(pts) < 2:
        return list(pts)
    out = [pts[0]]
    carry = 0.0
    for a, b in zip(pts, pts[1:]):
        d = math.dist(a, b)
        if d < 1e-9:
            continue
        t = step - carry
        while t <= d:
            out.append((a[0] + (b[0] - a[0]) * t / d, a[1] + (b[1] - a[1]) * t / d))
            t += step
        carry = d - (t - step)
    if math.dist(out[-1], pts[-1]) > step * .15:
        out.append(pts[-1])
    else:
        out[-1] = pts[-1]
    return out


def smooth(pts, sigma=SIGMA, step=STEP):
    """A Gaussian-smoothed copy of an evenly spaced course; its ends are held in
    place (the course is mirrored through each end first, so it does not shrink)."""
    n = len(pts)
    if n < 3:
        return list(pts)
    k = int(math.ceil(3 * sigma / step))
    pad_a = [(2 * pts[0][0] - pts[min(n - 1, i)][0], 2 * pts[0][1] - pts[min(n - 1, i)][1]) for i in range(k, 0, -1)]
    pad_b = [(2 * pts[-1][0] - pts[max(0, n - 1 - i)][0], 2 * pts[-1][1] - pts[max(0, n - 1 - i)][1]) for i in range(1, k + 1)]
    ext = pad_a + list(pts) + pad_b
    wts = [math.exp(-.5 * (i * step / sigma) ** 2) for i in range(-k, k + 1)]
    tot = sum(wts)
    out = []
    for i in range(k, k + n):
        x = sum(w * ext[i + j - k][0] for j, w in enumerate(wts)) / tot
        y = sum(w * ext[i + j - k][1] for j, w in enumerate(wts)) / tot
        out.append((x, y))
    out[0], out[-1] = pts[0], pts[-1]
    return out


def run_off(pts, d=RUN_OFF, step=STEP, ends=(True, True)):
    """The course carried straight on past both ends (or only the `ends` given), along the way it was heading."""
    if len(pts) < 3:
        return pts

    def tangent(a, b):
        L = math.dist(a, b) or 1.0
        return ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    t0 = tangent(pts[min(len(pts) - 1, 6)], pts[0])
    t1 = tangent(pts[max(0, len(pts) - 7)], pts[-1])
    head = [(pts[0][0] + t0[0] * s, pts[0][1] + t0[1] * s) for s in range(int(d), 0, -int(step))] if ends[0] else []
    tail = [(pts[-1][0] + t1[0] * s, pts[-1][1] + t1[1] * s) for s in range(int(step), int(d) + 1, int(step))] if ends[1] else []
    return head + list(pts) + tail


def course(pts, sigma=SIGMA, ends=(True, True)):
    """A river's centre line carried onto the grid -> its smooth course, run off the ends (those in `ends`: a channel's end
    at a confluence or a lake inside the box stops there)."""
    c = resample(pts, STEP)
    c = smooth(c, sigma)
    c = smooth(c, sigma * .45)          # a second, light pass takes the last wobble out of the stretched bends
    if not ends[0]:
        c[0] = tuple(pts[0])            # the end it stops at stays where it is (the branches meet at one point)
    if not ends[1]:
        c[-1] = tuple(pts[-1])
    return run_off(c, ends=ends)


def _flat(pts):
    return [round(v, 1) for q in pts for v in q]


def rivers(m, mp, xg, yg, cw, ch, W, H):
    """(river list, glass width). See the module docstring."""
    out = []
    bank = m.get("bank") or {}
    names = []
    for r in m.get("rivers", []):
        if r.get("n") and r["n"] not in names:
            names.append(r["n"])
    realW, realH = m.get("W", 1), m.get("H", 1)
    new_w = W
    for name in names:
        line = _main_piece(m["rivers"], name)
        if not line or _len(line) < .6 * min(realW, realH):
            continue                                     # a creek, not the river the city is on
        real = resample(line, 25.0)
        wide = bank.get("n") == name and bank.get("side") == "e" and xg
        if wide:
            # the wide river along the east edge: rows as the streets have them, its lean kept a little
            tur = [mp.turn(x, y) for x, y in real]
            x0 = min(t[0] for t in tur)
            xe = xg[-1] + GAP + WIDE_W / 2
            pts = [(xe + LEAN * (t[0] - x0), mp._interp(t[1], mp.yr, mp.yg, ch)) for t in tur]
            c = course(pts, SIGMA * 1.4)
            w = WIDE_W
            new_w = max(new_w, int(max(p[0] for p in c if -50 < p[1] < H + 50) + w / 2 + EDGE))
        else:
            pts = [mp(x, y) for x, y in real]
            c = course(pts)
            w = NARROW_W
        out.append({"n": name, "w": w, "p": _flat(c)})
    # a wide river with no centre line in the box (the box stops short of the river's own line, only its
    # near bank is in): water along the whole east edge of the map is a band along that edge of the grid
    if not any(r["w"] == WIDE_W for r in out) and xg:
        for r in m.get("water", []):
            q = _pairs(r)
            ys = [y for _, y in q]
            if q and max(x for x, _ in q) >= realW - 2 and max(ys) - min(ys) >= .3 * realH:
                xe = xg[-1] + GAP + WIDE_W / 2
                out.append({"n": "", "w": WIDE_W, "p": _flat([(xe, yg[0] - ch * .6), (xe, yg[-1] + ch * .6)])})
                new_w = max(new_w, int(xe + WIDE_W / 2 + EDGE))
                break
    return out, new_w
