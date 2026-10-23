"""Parks kept on dry land (Luke, 2026-10-22: "There are parks going into the water, make parks accurate").

A park is drawn from its blocks (the lattice parks) or its real outline carried onto the page (the five boroughs' parks);
either can reach past the drawn shore: a block cut by the shore is drawn whole, and an OSM park often takes in the water
beside it (Jamaica Bay Park, Plumb Beach). At build each park that reaches the water the page draws (the open water less
the land laid over it, and the river bands) is fitted again: its own outline less that water, a little beach (MARGIN)
left between the green and the water's bank, found on scan rows STEP px apart, traced and smoothed. A park that stays dry
is drawn exactly as before. Pure: the map in, rings out; no page code changes."""
from __future__ import annotations

import math

from .palace_grid import _chaikin, _dp

STEP = 24.0               # page px between the scan rows (and the cells along them)
MARGIN = 26.0             # page px of beach between the green and the water (its bank drawn green half of it)
SMOOTH, TOL = 0, 10.0     # the traced outline: Chaikin passes, then Douglas-Peucker tolerance (page px; the page rounds its corners)
BUCKET = 256.0


def _rings(flat_list):
    return [list(zip(r[0::2], r[1::2])) for r in flat_list or () if r and len(r) >= 6]


class _Edges:
    """The edges of some rings, bucketed by y: the x where a row crosses them (even-odd)."""

    def __init__(self, rings):
        self.b: dict = {}
        for r in rings:
            for (x0, y0), (x1, y1) in zip(r, r[1:] + r[:1]):
                if y0 == y1:
                    continue
                for k in range(int(min(y0, y1) // BUCKET), int(max(y0, y1) // BUCKET) + 1):
                    self.b.setdefault(k, []).append((x0, y0, x1, y1))

    def spans(self, y):
        xs = sorted(x0 + (y - y0) * (x1 - x0) / (y1 - y0) for x0, y0, x1, y1 in self.b.get(int(y // BUCKET), ())
                    if (y0 > y) != (y1 > y))
        return [(xs[k], xs[k + 1]) for k in range(0, len(xs) - 1, 2)]


def _union(sp):
    out = []
    for a, b in sorted(sp):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def _minus(sp, cut):
    out = []
    for a, b in sp:
        cur = a
        for c, d in cut:
            if d <= cur or c >= b:
                continue
            if c > cur:
                out.append((cur, c))
            cur = max(cur, d)
        if cur < b:
            out.append((cur, b))
    return out


class Water:
    """The water a palace page draws, as spans along rows: the open water (M.sea, even-odd) less the land laid over it
    (M.land), and every river band not part of the open water (the page draws those as wide strokes)."""

    def __init__(self, m):
        sea = _rings(m.get("sea"))
        self.sea, self.land = _Edges(sea), _Edges(_rings(m.get("land")))
        self.discs: dict = {}                           # the bands as discs along their course, bucketed by y
        for r in m.get("river") or []:
            if r.get("ch") and sea:
                continue
            p = list(zip(r["p"][0::2], r["p"][1::2]))
            hw = (r.get("w") or 100) / 2.0
            st = max(4.0, hw / 3)
            for (x0, y0), (x1, y1) in zip(p, p[1:]):
                n = max(1, int(math.hypot(x1 - x0, y1 - y0) / st))
                for t in range(n + 1):
                    x, y = x0 + (x1 - x0) * t / n, y0 + (y1 - y0) * t / n
                    for k in range(int((y - hw) // BUCKET), int((y + hw) // BUCKET) + 1):
                        self.discs.setdefault(k, []).append((x, y, hw))
        self.any = bool(self.sea.b or self.discs)

    def spans(self, y, pad=0.0):
        """The wet spans of row y, each widened by pad on both sides."""
        sp = _minus(self.sea.spans(y), self.land.spans(y)) if self.sea.b else []
        for x, cy, hw in self.discs.get(int(y // BUCKET), ()):
            dy = abs(y - cy)
            if dy < hw:
                h = math.sqrt(hw * hw - dy * dy)
                sp.append((x - h, x + h))
        return _union([(a - pad, b + pad) for a, b in sp])


def fit(rings, water, step=None, margin=MARGIN):
    """A park's rings (flat page px) less the water and a beach of `margin`: new rings, or None when it stays dry."""
    R = _rings(rings)
    if not R or not water.any:
        return None
    step = step or STEP
    park = _Edges(R)
    ys = [p[1] for r in R for p in r]
    xs = [p[0] for r in R for p in r]
    x0, y0 = min(xs), min(ys)
    nx, ny = int((max(xs) - x0) / step) + 2, int((max(ys) - y0) / step) + 2
    grid, touched, kept = [bytearray(nx) for _ in range(ny)], False, 0
    for j in range(ny):
        y = y0 + (j + .5) * step
        inn = _union(park.spans(y))
        if not inn:
            continue
        wet = _union(water.spans(y - margin, margin) + water.spans(y, margin) + water.spans(y + margin, margin))
        dry = _minus(inn, wet)
        if not touched and dry != inn:
            touched = True
        for a, b in dry:
            for i in range(max(0, int((a - x0) / step + .5)), min(nx, int((b - x0) / step + .5))):
                grid[j][i] = 1
                kept += 1
    if not touched:
        return None
    from .city_boroughs import _trace
    out = []
    for loop in _trace(grid, nx, ny, step):
        if len(loop) < 3:
            continue
        sm = _chaikin([(x0 + x, y0 + y) for x, y in loop], SMOOTH, closed=True)
        sm = _dp(sm + sm[:1], TOL)[:-1]
        if len(sm) >= 3 and abs(_area(sm)) >= 4 * step * step:
            out.append([round(v) for p in sm for v in p])
    return out


def _area(r):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(r, r[1:] + r[:1])) / 2


def inside(rings, x, y):
    c = False
    for r in _rings(rings):
        for (x0, y0), (x1, y1) in zip(r, r[1:] + r[:1]):
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                c = not c
    return c
