"""The water between a city and the land across it (Manhattan: the Hudson and the East River).

A city whose far banks are kept (a preset's far_bank: Brooklyn and Queens facing Manhattan) has grid domains no seam
reaches: islands across the water, which the Layout places where the root's mapping puts their real outline. That
mapping stretches the real river by the root's last street spacing (a few real metres per page block at the shore),
so the water came out thousands of px wide, the land across it floated alone and no river was drawn between: the
river lines OpenStreetMap has for such a city are short, one-sided or missing (the East River is only a water polygon).

Designed instead, as a river is everywhere else (palace_river): the water between two banks is a band of one width,

  compact(lay, by_id, root, seams, m)   moves every island (and the islands that touch it) toward the root until the
                                        gap between the two shores is the band and its margins; only across real water
  channels(...)                         the band: the midline of the gap between the root's shore cells and the island's,
                                        smoothed and run off the glass at both ends, as palace_river.course draws any river

Pure: no I/O. Only a city with `m["far_bank"]` comes here, so every other city is untouched by construction.
"""
from __future__ import annotations

import math
from bisect import bisect_left

from .palace_river import WIDE_W, resample, smooth, run_off, STEP

MARGIN = 44.0            # px of glass between a shore's cells and the band (a street stops BANK_GAP = 34 short of the water)
CELL_HALF = 105.0        # px: about half a block, from a cell's centre to its edge
TARGET = WIDE_W + 2 * MARGIN + 2 * CELL_HALF     # px between the centres of the two shores' nearest cells
SLACK = 1.15             # an island already this close (x TARGET) stays where it is
GROUP = 3.0              # blocks: islands this close are one land across the water and move together
WET_SHARE = 0.2          # of the real line between two shores that lies in water for the gap to be a river
WATER_MIN = 40000.0     # real px (m) squared: a water ring smaller than this is a pond, not the river


def _ring_inside(ring, x, y):
    c = False
    n = len(ring)
    for i in range(n):
        (x0, y0), (x1, y1) = ring[i], ring[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


class _Wet:
    """Is a real point in the big water of the map (the river polygons, not ponds)?"""

    def __init__(self, m):
        self.rings = []
        for r in m.get("water") or []:
            p = [(r[i], r[i + 1]) for i in range(0, len(r) - 1, 2)]
            if len(p) < 3:
                continue
            a = 0.0
            for (x0, y0), (x1, y1) in zip(p, p[1:] + p[:1]):
                a += x0 * y1 - x1 * y0
            if abs(a) / 2 < WATER_MIN:
                continue
            xs, ys = [q[0] for q in p], [q[1] for q in p]
            self.rings.append((min(xs), min(ys), max(xs), max(ys), p))

    def __call__(self, x, y):
        n = 0
        for x0, y0, x1, y1, p in self.rings:
            if x0 <= x <= x1 and y0 <= y <= y1 and _ring_inside(p, x, y):
                n += 1
        return n % 2 == 1

    def share(self, a, b, k=14):
        if not self.rings:
            return 0.0
        return sum(self((a[0] + (b[0] - a[0]) * t / k), (a[1] + (b[1] - a[1]) * t / k)) for t in range(1, k)) / (k - 1)


MAX_W = 3600.0           # px: the widest band (the Hudson, ~4.5 blocks); a real river is as wide as it is, to here


def river_width(wet, root_map, root_ix, pts, n=24):
    """The page width of the water between the root and a land across it: the real water along the shortest lines between
    their shores (the cross-section, in metres) carried to page px by how far the root's own mapping stretches that way.
    -> the samples, px (one per line measured)."""
    pairs = []
    for c in pts:
        r = root_ix.nearest(c[0], 1e18 if not pairs else 3 * TARGET)
        if r:
            pairs.append((r[0], c, r[1]))
    pairs.sort(key=lambda t: t[0])
    ws = []
    for _d, b, a in pairs[:n]:
        ra, rb = a[1], b[1]
        L = math.dist(ra, rb)
        if L < 1:
            continue
        u = ((rb[0] - ra[0]) / L, (rb[1] - ra[1]) / L)
        loc = getattr(root_map, "loc", None)
        if loc is not None and getattr(loc, "xr", None) and getattr(loc, "yr", None) and len(loc.xr) > 1 and len(loc.yr) > 1:
            # the stretch of the whole lattice (page px a real metre, across the avenues and along them), not of the one place the
            # river happens to touch: the real Hudson is about two East Rivers wide and a third of Manhattan's width
            kx = (loc.xg[-1] - loc.xg[0]) / ((loc.xr[-1] - loc.xr[0]) or 1.0)
            ky = (loc.yg[-1] - loc.yg[0]) / ((loc.yr[-1] - loc.yr[0]) or 1.0)
            ta, tb = loc.turn(*ra), loc.turn(ra[0] + u[0] * 250.0, ra[1] + u[1] * 250.0)
            k = math.hypot((tb[0] - ta[0]) / 250.0 * kx, (tb[1] - ta[1]) / 250.0 * ky)
        else:
            pa, pb = root_map(*ra), root_map(ra[0] + u[0] * 250.0, ra[1] + u[1] * 250.0)
            k = math.dist(pa, pb) / 250.0
        ws.append(wet.share(ra, rb, 40) * L * k)
    return ws


def _median_w(ws):
    if not ws:
        return WIDE_W
    ws = sorted(ws)
    return max(WIDE_W, min(MAX_W, ws[len(ws) // 2]))


def footprint(d, mp, rect, in_real, unlocal):
    """The cells a grid domain would draw, as [(page centre, real centre)] (the lattice cells whose real place is in it)."""
    gv, gh = mp.loc.gv, mp.loc.gh
    x0, y0, x1, y1 = rect
    i0, i1 = int(math.ceil(x0 / gv - 1e-9)), int(math.floor(x1 / gv + 1e-9))
    j0, j1 = int(math.ceil(y0 / gh - 1e-9)), int(math.floor(y1 / gh + 1e-9))
    out = []
    for j in range(j0, j1):
        for i in range(i0, i1):
            lx, ly = (i + .5) * gv, (j + .5) * gh
            rx, ry = unlocal(mp.loc, lx, ly)
            if in_real(d, rx, ry):
                out.append((mp.page(lx, ly), (rx, ry)))
    return out


class _Index:
    """Page points in a grid of buckets, for the nearest of a set to a point."""

    def __init__(self, items, cell=480.0):
        self.cell, self.b = cell, {}
        for it in items:
            self.b.setdefault((int(it[0][0] // cell), int(it[0][1] // cell)), []).append(it)

    def nearest(self, p, limit=1e18):
        ci, cj = int(p[0] // self.cell), int(p[1] // self.cell)
        best = None
        for r in range(0, 60):
            for i in range(ci - r, ci + r + 1):
                for j in (range(cj - r, cj + r + 1) if i in (ci - r, ci + r) else (cj - r, cj + r)):
                    for it in self.b.get((i, j), ()):
                        d = math.dist(p, it[0])
                        if best is None or d < best[0]:
                            best = (d, it)
            if best and best[0] <= r * self.cell:
                break
            if r * self.cell > limit:
                break
        return best


def _nearest_pair(A, ix_b):
    """(distance, a, b) of the closest pair between the items A (page, real) and the indexed set."""
    best = None
    for a in A:
        r = ix_b.nearest(a[0], 1e18 if best is None else best[0] + 1)
        if r and (best is None or r[0] < best[0]):
            best = (r[0], a, r[1])
    return best


def islands_of(by_id, root, seams):
    """The grid domains no seam joins to the root, in groups of islands that lie against each other."""
    joined = {root}
    grew = True
    while grew:
        grew = False
        for sm in seams:
            if (sm.a in joined) != (sm.b in joined):
                joined |= {sm.a, sm.b}
                grew = True
    return [did for did in by_id if did not in joined], joined


def compact(lay, by_id, root, seams, m, in_real, unlocal, blk):
    """Bring each island across water to the band's gap off the root. -> [{ids, shift, gap_was, gap, wet}] (one per
    group that moved; the groups that did not move, with `shift` None) and the footprints it measured."""
    isl, joined = islands_of(by_id, root, seams)
    if not isl:
        return [], {}
    wet = _Wet(m)
    fp = {did: footprint(by_id[did], lay.maps[did], lay.rect[did], in_real, unlocal) for did in [root] + isl}
    near = GROUP * blk
    grp = {did: did for did in isl}

    def find(x):
        while grp[x] != x:
            grp[x] = grp[grp[x]]
            x = grp[x]
        return x
    for i, a in enumerate(isl):
        ixa = _Index(fp[a])
        for b in isl[i + 1:]:
            pr = _nearest_pair(fp[b], ixa)
            if pr and pr[0] < near:
                grp[find(a)] = find(b)
    groups = {}
    for did in isl:
        groups.setdefault(find(did), []).append(did)
    root_ix = _Index(fp[root])
    rep = []
    # how wide the water is: every land on one side of the root (west, east, ...) is across the same river, so its lines
    # are measured together (Brooklyn Heights and Astoria are both across the East River, whatever each line reads)
    rc = (sum(c[0][0] for c in fp[root]) / len(fp[root]), sum(c[0][1] for c in fp[root]) / len(fp[root]))
    pooled = {}
    side_of = {}
    for ids in groups.values():
        pts = [c for did in ids for c in fp[did]]
        gx, gy = sum(c[0][0] for c in pts) / len(pts), sum(c[0][1] for c in pts) / len(pts)
        key = ("x", gx > rc[0]) if abs(gx - rc[0]) >= abs(gy - rc[1]) else ("y", gy > rc[1])
        side_of[tuple(ids)] = key
        pr = _nearest_pair(pts, root_ix)
        if pr and wet.share(pr[2][1], pr[1][1]) >= WET_SHARE:
            pooled.setdefault(key, []).extend(river_width(wet, lay.maps[root], root_ix, pts))
    # the nearest land first: a far group may stand behind a near one
    order = []
    for ids in groups.values():
        pts = [c for did in ids for c in fp[did]]
        pr = _nearest_pair(pts, root_ix)
        order.append((pr[0] if pr else 1e18, ids))
    order.sort(key=lambda t: t[0])
    for _d0, ids in order:
        shift = [0.0, 0.0]
        gap0 = gap = None
        wet_share = None
        w_g, target = WIDE_W, TARGET
        for _ in range(4):
            pts = [((c[0][0] + shift[0], c[0][1] + shift[1]), c[1]) for did in ids for c in fp[did]]
            pr = _nearest_pair(pts, root_ix)
            if not pr:
                break
            d, b, a = pr
            if gap0 is None:
                gap0 = d
                wet_share = wet.share(a[1], b[1])
                if wet_share < WET_SHARE:
                    break                                   # land between them, not a river: left where it is
                w_g = _median_w(pooled.get(side_of[tuple(ids)]))
                target = w_g + 2 * MARGIN + 2 * CELL_HALF
            gap = d
            if d <= target * SLACK and d >= target / SLACK:
                break
            u = ((a[0][0] - b[0][0]) / (d or 1.0), (a[0][1] - b[0][1]) / (d or 1.0))
            s = d - target
            shift[0] += u[0] * s
            shift[1] += u[1] * s
        river = bool(wet_share is not None and wet_share >= WET_SHARE)
        if gap0 is None or not river or (shift[0] == 0.0 and shift[1] == 0.0):
            rep.append({"ids": ids, "shift": None, "gap_was": gap0, "wet": wet_share, "river": river, "w": w_g})
            continue
        for did in ids:
            mp = lay.maps[did]
            mp.o = (mp.o[0] + shift[0], mp.o[1] + shift[1])
        for did in ids:
            fp[did] = [((c[0][0] + shift[0], c[0][1] + shift[1]), c[1]) for c in fp[did]]
        rep.append({"ids": ids, "shift": (round(shift[0], 1), round(shift[1], 1)), "gap_was": gap0, "gap": gap, "wet": wet_share, "river": True, "w": w_g})
    return rep, fp


LINK = 7000.0            # px: shore points this close, with no cell of the root's between them, are one river's
BIN = 160.0              # px along the river: the shore points are averaged in bins this long
SIGMA = 420.0            # px: how far the band's smoothing reaches (palace_river.course)
HINT_R = 1800.0          # real px: a named point this close to a band's shore names it


def _bins(pts):
    """The shore points of one river as an ordered polyline: along their principal axis, averaged in bins."""
    n = len(pts)
    mx, my = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    syy = sum((p[1] - my) ** 2 for p in pts)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
    th = 0.5 * math.atan2(2 * sxy, sxx - syy)
    ux, uy = math.cos(th), math.sin(th)
    t = sorted(((p[0] - mx) * ux + (p[1] - my) * uy, p) for p in pts)
    out, cur, c0 = [], [], None
    for tv, p in t:
        if c0 is None or tv - c0 > BIN:
            if cur:
                out.append((sum(q[0] for q in cur) / len(cur), sum(q[1] for q in cur) / len(cur)))
            cur, c0 = [], tv
        cur.append(p)
    if cur:
        out.append((sum(q[0] for q in cur) / len(cur), sum(q[1] for q in cur) / len(cur)))
    return out


def channels(m, root, fp, rep, off, reach, hints=()):
    """The bands: one smooth river of WIDE_W per land across the water, along the midline of the gap between the root's
    shore and the island's (palace_river.course: smoothed, run off the glass at both ends). `off` is the page shift the
    footprints have not had yet. -> [{n, w, p, _q}] like city_engine._rivers."""
    pts = []                                              # (page midpoint, real point of the root's shore, its river's width)
    ix_root = _Index(fp[root])
    for r in rep:
        if not r.get("river"):
            continue
        G = [c for did in r["ids"] for c in fp[did]]
        ix_g = _Index(G)
        wr = r.get("w") or WIDE_W
        rng = 1.7 * (wr + 2 * MARGIN + 2 * CELL_HALF)
        for c in G:
            q = ix_root.nearest(c[0], rng)
            if q and q[0] <= rng:
                pts.append((((c[0][0] + q[1][0][0]) / 2, (c[0][1] + q[1][0][1]) / 2), q[1][1], wr))
        for c in fp[root]:
            q = ix_g.nearest(c[0], rng)
            if q and q[0] <= rng:
                pts.append((((c[0][0] + q[1][0][0]) / 2, (c[0][1] + q[1][0][1]) / 2), c[1], wr))
    if not pts:
        return []
    # one river per run of shore points that lie within LINK of one another
    ix = _Index([(p[0], i) for i, p in enumerate(pts)], cell=LINK)
    lab = list(range(len(pts)))

    def find(x):
        while lab[x] != x:
            lab[x] = lab[lab[x]]
            x = lab[x]
        return x
    for i, (p, _, _w) in enumerate(pts):
        for gi in (-1, 0, 1):
            for gj in (-1, 0, 1):
                for q, j in ix.b.get((int(p[0] // LINK) + gi, int(p[1] // LINK) + gj), ()):
                    if j != i and find(i) != find(j) and math.dist(p, q) <= LINK:
                        mid = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
                        r_ = ix_root.nearest(mid, TARGET)
                        if r_ is None or r_[0] > 0.35 * TARGET:        # the shore runs on there; not across the root's own land
                            lab[find(i)] = find(j)
    runs = {}
    for i in range(len(pts)):
        runs.setdefault(find(i), []).append(pts[i])
    out = []
    for run in sorted(runs.values(), key=lambda r: -len(r)):
        if len(run) < 6:
            continue
        mid = _bins([(p[0][0] + off[0], p[0][1] + off[1]) for p in run])
        if len(mid) < 3:
            continue
        c = resample(mid, STEP)
        c = smooth(smooth(c, SIGMA), SIGMA * .45)
        # to the edge of the glass at both ends (the page clips it there). A river that runs down the page runs on straight down
        # it: the way the last bins happened to lean is not where the water goes (the Hudson fanned out toward the bottom corner)
        (x0, y0), (x1, y1) = c[0], c[-1]
        if abs(y1 - y0) > 2.5 * abs(x1 - x0):
            n = int(reach // STEP) + 1
            c = [(x0, y0 - STEP * k) for k in range(n, 0, -1)] + list(c) + [(x1, y1 + STEP * k) for k in range(1, n + 1)]
        else:
            c = run_off(c, d=reach)
        name, best = "", HINT_R
        for h in hints or ():                         # the name whose point lies nearest the band's shore
            d = min(math.hypot(h["x"] - p[1][0], h["y"] - p[1][1]) for p in run)
            if d < best:
                best, name = d, h["n"]
        wd = sorted(p[2] for p in run)
        out.append({"n": name, "w": round(wd[len(wd) // 2]), "ch": 1, "p": [round(v, 1) for q in c for v in q], "_q": c})
    return out


def hints_of(m):
    """[{n, x, y}] the preset's river names as real map px (the preset's `river_names`: [name, lat, lon])."""
    try:
        from . import city_presets
        from .. import palace_map as pm
        pre = city_presets.get(m.get("place") or "")
        bb, sc = m.get("bbox"), m.get("scale") or 1.0
        if not pre or not bb:
            return []
        out = []
        for n, la, lo in pre.get("river_names") or []:
            x, y = pm.project(la, lo, bb, sc)
            out.append({"n": n, "x": x, "y": y})
        return out
    except Exception:                                       # noqa: BLE001 — a city without names draws its bands unnamed
        return []


def wet_line(m, line, share=0.6):
    """Is a real polyline (x, y pairs) mostly in the big water of the map?"""
    w = _Wet(m)
    if not line or not w.rings:
        return False
    n = len(line)
    hits = sum(w(*p) for p in line)
    return hits >= share * n


# ── the open water: the bay and the sea (not a river's band) ────────────────
DEBUG = False
SEA_CELL = 60.0          # px: the raster the open water is found on
SEA_REACH = 8.0          # blocks: a page cell this far from every drawn cell is not read back to the real map
SEA_MIN = 56             # cells: a pool of open water smaller than this is not drawn
SEA_TOL = 1.6            # x cell: the outline's simplification before it is rounded


def _chaikin(R, k=2):
    for _ in range(k):
        out = []
        n = len(R)
        for i in range(n):
            a, b = R[i], R[(i + 1) % n]
            out += [(a[0] * .75 + b[0] * .25, a[1] * .75 + b[1] * .25), (a[0] * .25 + b[0] * .75, a[1] * .25 + b[1] * .75)]
        R = out
    return R


def _dp(pts, tol):
    if len(pts) < 3:
        return pts
    a, b = pts[0], pts[-1]
    L = math.dist(a, b) or 1e-9
    k, kd = 0, -1.0
    for i in range(1, len(pts) - 1):
        d = abs((b[0] - a[0]) * (a[1] - pts[i][1]) - (a[0] - pts[i][0]) * (b[1] - a[1])) / L
        if d > kd:
            k, kd = i, d
    if kd <= tol:
        return [a, b]
    return _dp(pts[:k + 1], tol)[:-1] + _dp(pts[k:], tol)


def _fill(occ, nx, ny, c, ring):
    """Mark the cells whose centre is inside a page ring (even-odd, scanline)."""
    ys = [p[1] for p in ring]
    n = len(ring)
    for j in range(max(0, int(min(ys) // c) + 1), min(ny, int(max(ys) // c) + 3)):
        y = (j - .5) * c
        xs = sorted(ring[i][0] + (y - ring[i][1]) * (ring[(i + 1) % n][0] - ring[i][0]) / (ring[(i + 1) % n][1] - ring[i][1])
                    for i in range(n) if (ring[i][1] > y) != (ring[(i + 1) % n][1] > y))
        for k in range(0, len(xs) - 1, 2):
            for i in range(max(0, int(xs[k] // c) + 1), min(nx, int(xs[k + 1] // c) + 2)):
                occ[j * nx + i] = 1


def sea(g, land_rings, outside=None):
    """The open water of a far-bank city as rings of page px (g["sea"]; the page fills them as water under the streets): where
    the rivers meet and run out past the land. Manhattan is an island, the Hudson on one side and the East River on the
    other, so the water between the two bands that no land holds is the harbour at its tip, and the land beyond each band
    (New Jersey, Brooklyn and Queens) stays dry. The drawn city is the blocks, the street lines, the free domains' outlines
    and the parks; a cell next to any of them is land's own margin. Fewer than two bands: no open water is drawn."""
    bands = [rv for rv in g.get("river") or () if len(rv.get("p") or ()) >= 8]
    if len(bands) < 2:
        return []
    W, H = g["W"], g["H"]
    c = SEA_CELL
    nx, ny = int(W // c) + 3, int(H // c) + 3                 # one cell of glass past each edge, and one of margin
    occ = bytearray(nx * ny)

    def mark(x, y, r=2):
        i, j = int(x // c) + 1, int(y // c) + 1
        for a in range(i - r, i + r + 1):
            for b in range(j - r, j + r + 1):
                if 0 <= a < nx and 0 <= b < ny:
                    occ[b * nx + a] = 1

    def line(p):
        for k in range(0, len(p) - 3, 2):
            x0, y0, x1, y1 = p[k], p[k + 1], p[k + 2], p[k + 3]
            n = max(1, int(math.hypot(x1 - x0, y1 - y0) // (c * .5)))
            for t in range(n + 1):
                mark(x0 + (x1 - x0) * t / n, y0 + (y1 - y0) * t / n)
        if len(p) >= 2:
            mark(p[-2], p[-1])
    for t in g.get("tiles") or ():
        for x in range(int(t[0] // c), int(t[2] // c) + 1):
            for y in range(int(t[1] // c), int(t[3] // c) + 1):
                mark((x + .5) * c, (y + .5) * c, 0)
    for k in ("edges", "tq", "te"):
        for p in g.get(k) or ():
            line(list(p) + list(p[:2]) if k == "tq" else p)
    for st in g.get("streets") or ():
        line(st["p"])
    for pk in g.get("parks") or ():
        for r in pk.get("r") or ():
            line(list(r) + list(r[:2]))
    for rd in (g.get("hw") or {}).get("roads") or ():            # the highways, which run along the shore (West Side Highway)
        for pl in rd.get("p") or ():
            line(pl)
    for ring in land_rings or ():
        if len(ring) >= 3:
            _fill(occ, nx, ny, c, [(p[0], p[1]) for p in ring])
            line([v for p in ring for v in p] + [ring[0][0], ring[0][1]])
    # the side of each band the other bands are on: the water lies between them (the bands run the long way of the page)
    ax = []
    for rv in bands:
        q = rv["p"]
        pts = [(q[k], q[k + 1]) for k in range(0, len(q) - 1, 6)]
        if pts[-1] != (q[-2], q[-1]):
            pts.append((q[-2], q[-1]))
        ys = [p[1] for p in pts]
        if abs(ys[-1] - ys[0]) < 2.5 * abs(pts[-1][0] - pts[0][0]):
            return []                                           # a band that does not run down the page: no rule for it here
        ax.append(sorted((p[1], p[0]) for p in pts))

    def band_x(k, y):
        t = ax[k]
        i = bisect_left([v[0] for v in t], y)
        if i <= 0:
            return t[0][1]
        if i >= len(t):
            return t[-1][1]
        (y0, x0), (y1, x1) = t[i - 1], t[i]
        return x0 + (x1 - x0) * (y - y0) / ((y1 - y0) or 1.0)
    mid = (sum(band_x(k, H / 2) for k in range(len(bands))) / len(bands))
    inward = [1 if mid > band_x(k, H / 2) else -1 for k in range(len(bands))]

    def ok(i, j):
        """The cell may be water: between the bands, and not past the box's far edge (where the real map stops and nothing
        is known: Manhattan goes on north of the box, it is not sea)."""
        x, y = (i - .5) * c, (j - .5) * c
        return all((x - band_x(k, y)) * inward[k] > -c for k in range(len(bands))) and not (outside and outside(x, y))

    def inside_bands(i, j):
        x, y = (i - .5) * c, (j - .5) * c
        return all((x - band_x(k, y)) * inward[k] > -c for k in range(len(bands)))
    # the water: what a band reaches through the cells no land holds, between the bands
    water = bytearray(nx * ny)
    stack = []
    for rv in g.get("river") or ():
        q = rv["p"]
        hw = rv["w"] / 2
        for k in range(0, len(q) - 3, 2):
            x0, y0, x1, y1 = q[k], q[k + 1], q[k + 2], q[k + 3]
            n = max(1, int(math.hypot(x1 - x0, y1 - y0) // (c * .5)))
            for t in range(n + 1):
                px, py = x0 + (x1 - x0) * t / n, y0 + (y1 - y0) * t / n
                for a in range(int((px - hw) // c), int((px + hw) // c) + 1):
                    for b in range(int((py - hw) // c), int((py + hw) // c) + 1):
                        i, j = a + 1, b + 1
                        if 0 <= i < nx and 0 <= j < ny and not water[j * nx + i] and math.hypot((a + .5) * c - px, (b + .5) * c - py) <= hw + c * .7 and inside_bands(i, j):
                            water[j * nx + i] = 1
                            stack.append(j * nx + i)
    while stack:
        v = stack.pop()
        vi, vj = v % nx, v // nx
        for a, b in ((vi + 1, vj), (vi - 1, vj), (vi, vj + 1), (vi, vj - 1)):
            if 0 <= a < nx and 0 <= b < ny and not water[b * nx + a] and not occ[b * nx + a] and ok(a, b):
                water[b * nx + a] = 1
                stack.append(b * nx + a)
    # a pool of open water too small to matter is dropped
    seen = bytearray(nx * ny)
    for s0 in range(nx * ny):
        if water[s0] and not seen[s0]:
            comp, stack = [], [s0]
            seen[s0] = 1
            while stack:
                v = stack.pop()
                comp.append(v)
                vi, vj = v % nx, v // nx
                for a, b in ((vi + 1, vj), (vi - 1, vj), (vi, vj + 1), (vi, vj - 1)):
                    if 0 <= a < nx and 0 <= b < ny and water[b * nx + a] and not seen[b * nx + a]:
                        seen[b * nx + a] = 1
                        stack.append(b * nx + a)
            if len(comp) < SEA_MIN:
                for v in comp:
                    water[v] = 0
    # the water runs under the land's margin (the real shore of the island is laid over it, see land_of)
    grown = bytearray(water)
    for j in range(ny):
        for i in range(nx):
            if water[j * nx + i]:
                for b in range(max(0, j - 2), min(ny, j + 3)):
                    for a in range(max(0, i - 2), min(nx, i + 3)):
                        grown[b * nx + a] = 1
    water = grown
    # the outline: the edges of the water cells with the water on the right, joined into loops
    edges = {}
    for j in range(ny):
        for i in range(nx):
            if not water[j * nx + i]:
                continue
            for e, (di, dj) in ((((i, j), (i + 1, j)), (0, -1)), (((i + 1, j), (i + 1, j + 1)), (1, 0)),
                                (((i + 1, j + 1), (i, j + 1)), (0, 1)), (((i, j + 1), (i, j)), (-1, 0))):
                a, b = i + di, j + dj
                if 0 <= a < nx and 0 <= b < ny and water[b * nx + a]:
                    continue
                edges.setdefault(e[0], []).append(e[1])
    rings = []
    for start in list(edges):
        while edges.get(start):
            loop = [start]
            cur = edges[start].pop()
            while cur != start:
                loop.append(cur)
                outs = edges.get(cur)
                if not outs:
                    break
                cur = outs.pop()
            if len(loop) >= 4:
                rings.append(loop)
    out = []
    for loop in rings:
        pts = [((v[0] - 1) * c, (v[1] - 1) * c) for v in loop]
        k = max(range(len(pts)), key=lambda i: math.dist(pts[i], pts[0]))          # a closed ring: simplified in two halves
        pts = _dp(pts[:k + 1], SEA_TOL * c)[:-1] + _dp(pts[k:] + [pts[0]], SEA_TOL * c)[:-1]
        if len(pts) < 3:
            continue
        out.append([round(v, 1) for q in pts for v in q])
    return out


# ── the island's own shore, exact ───────────────────────────────────────────
LAND_RES = 25.0          # real px (m): the raster the island's land is found on
LAND_TOL = 18.0          # real px (m): its outline is simplified to this
LAND_WATER_MIN = 500000.0   # real px (m) squared: water smaller than this (the reservoir, ponds, docks) is not a shore


def _ring_area(r):
    a = 0.0
    for (x0, y0), (x1, y1) in zip(r, r[1:] + r[:1]):
        a += x0 * y1 - x1 * y0
    return a / 2


def land_of(m, seed, to_page):
    """The real land of the island that holds `seed` (a real point on it), as rings of page px: the map's big water
    polygons rasterised in REAL px, the land flooded from the seed, its outline traced, simplified and carried onto the
    page by `to_page` (the island's own lattice mapping, the one its blocks stand on), so the shore and the blocks
    coincide. The page lays it over the water, which runs under its margin."""
    c = LAND_RES
    nx, ny = int(m["W"] // c) + 1, int(m["H"] // c) + 1
    wet = bytearray(nx * ny)
    for r in m.get("water") or ():
        ring = [(r[i], r[i + 1]) for i in range(0, len(r) - 1, 2)]
        if len(ring) < 3 or abs(_ring_area(ring)) < LAND_WATER_MIN:
            continue
        n = len(ring)
        for j in range(max(0, int(min(p[1] for p in ring) // c)), min(ny, int(max(p[1] for p in ring) // c) + 1)):
            y = (j + .5) * c
            xs = sorted(ring[k][0] + (y - ring[k][1]) * (ring[(k + 1) % n][0] - ring[k][0]) / (ring[(k + 1) % n][1] - ring[k][1])
                        for k in range(n) if (ring[k][1] > y) != (ring[(k + 1) % n][1] > y))
            for k in range(0, len(xs) - 1, 2):
                for i in range(max(0, int(xs[k] // c)), min(nx, int(xs[k + 1] // c) + 1)):
                    wet[j * nx + i] ^= 1                              # even-odd, so an island in a river is land again
    si, sj = min(nx - 1, max(0, int(seed[0] // c))), min(ny - 1, max(0, int(seed[1] // c)))
    if wet[sj * nx + si]:
        return []
    land = bytearray(nx * ny)
    land[sj * nx + si] = 1
    stack = [sj * nx + si]
    while stack:
        v = stack.pop()
        vi, vj = v % nx, v // nx
        for a, b in ((vi + 1, vj), (vi - 1, vj), (vi, vj + 1), (vi, vj - 1)):
            if 0 <= a < nx and 0 <= b < ny and not land[b * nx + a] and not wet[b * nx + a]:
                land[b * nx + a] = 1
                stack.append(b * nx + a)
    edges = {}
    for j in range(ny):
        for i in range(nx):
            if not land[j * nx + i]:
                continue
            for e, (di, dj) in ((((i, j), (i + 1, j)), (0, -1)), (((i + 1, j), (i + 1, j + 1)), (1, 0)),
                                (((i + 1, j + 1), (i, j + 1)), (0, 1)), (((i, j + 1), (i, j)), (-1, 0))):
                a, b = i + di, j + dj
                if 0 <= a < nx and 0 <= b < ny and land[b * nx + a]:
                    continue
                edges.setdefault(e[0], []).append(e[1])
    rings = []
    for start in list(edges):
        while edges.get(start):
            loop = [start]
            cur = edges[start].pop()
            while cur != start:
                loop.append(cur)
                outs = edges.get(cur)
                if not outs:
                    break
                cur = outs.pop()
            if len(loop) >= 8:
                rings.append(loop)
    out = []
    for loop in rings:
        pts = [(v[0] * c, v[1] * c) for v in loop]
        k = max(range(len(pts)), key=lambda i: math.dist(pts[i], pts[0]))
        pts = _dp(pts[:k + 1], LAND_TOL)[:-1] + _dp(pts[k:] + [pts[0]], LAND_TOL)[:-1]
        if len(pts) < 3:
            continue
        q = []
        for a, b in zip(pts, pts[1:] + pts[:1]):                      # long edges are cut so the mapping can bend them
            n = max(1, int(math.dist(a, b) // 150.0))
            q += [(a[0] + (b[0] - a[0]) * t / n, a[1] + (b[1] - a[1]) * t / n) for t in range(n)]
        pg = [to_page(x, y) for x, y in q]
        if abs(_ring_area(pg)) > 1e6:
            out.append([round(v, 1) for p in pg for v in p])
    return out
