"""The Mind Palace's parks: green glass on the grid, with their paths (Luke, 2026-10-14).

The real parks (palace_map: OSM rings) are carried onto the even grid and
snapped to it: a park is the set of grid blocks (cells) its outline mostly
covers, drawn as one rectilinear green shape with rounded corners, inset from
the streets that frame it. Inside, a few geometric walkways: the city squares
get their characteristic cross / diagonal paths and a centre plaza, a mall its
walk and cross walks, a big park (Fairmount, FDR) a spine trail with side legs,
straight segments the page joins with rounded elbows.

Two steps, because the buildings are placed later than the city is made:
  pick(...)  at set_up time → raw parks, {n, k, c: [[i0, j0, i1, j1], ...]}
             (cell runs: compact, stored in the map dict as "parks");
  shape(...) at page time   → what the page draws, {n, k, r: [ring, ...],
             p: [path, ...], o: [[x, y, r], ...], t: [x, y], z}; a cell with a
             building's lot on it is cut out of the park first, so a park never
             moves a building and never greens one's block.
"""
from __future__ import annotations

import math
import re
from bisect import bisect_right

from .palace_grid import _dp, _inside, _pairs

INSET = 14                 # how far the green stands in from the streets around it
AUTO_HA = 15               # a park of at least this many hectares is "major" without being asked for
_SKIP = re.compile(r"cemetery|golf|driving|athletic|supersite|parkway|fields?\b|complex|playground|trail|"
                   r"arboretum|recreation|rec\b|baseball|basketball|skate|dog|community garden|garden$", re.I)
# the page's short names
_SHORT = [(r"^(east|west)\s+fairmount park$", "Fairmount Park"), (r"^franklin delano roosevelt park$", "FDR Park"),
          (r"^clarence h\.? clark park$", "Clark Park"), (r"^independence national historical park$", "Independence Park"),
          (r"^bartram'?s garden$", "Bartram's Garden")]
# the characters of the well-known ones: x = diagonals, + = cross, * = both, mall = a walk with cross walks
_KIND = [(r"rittenhouse", "x"), (r"washington square", "*"), (r"franklin square", "*"), (r"logan", "+o"),
         (r"clark park", "x"), (r"independence mall", "mall"), (r"penn treaty", "+"), (r"eakins|marconi|penn park", "x"),
         (r"hunting park", "*")]


def short_name(n: str) -> str:
    for rx, s in _SHORT:
        if re.search(rx, n, re.I):
            return s
    return n


def _kind(n: str, ncell: int) -> str:
    for rx, k in _KIND:
        if re.search(rx, n, re.I):
            return k
    return "trail" if ncell >= 6 else "x"


def _cell(xg, yg, x, y):
    i, j = bisect_right(xg, x) - 1, bisect_right(yg, y) - 1
    return (i, j) if 0 <= i < len(xg) - 1 and 0 <= j < len(yg) - 1 else None


def _runs(cells):
    """Cells → horizontal runs [i0, j0, i1, j1] (i1, j1 exclusive), then runs of equal width stacked."""
    rows: dict = {}
    for i, j in cells:
        rows.setdefault(j, []).append(i)
    runs = []
    for j in sorted(rows):
        v = sorted(rows[j]); s = p = v[0]
        for i in v[1:]:
            if i != p + 1:
                runs.append([s, j, p + 1, j + 1]); s = i
            p = i
        runs.append([s, j, p + 1, j + 1])
    out: list = []
    for r in runs:
        for o in out:
            if o[0] == r[0] and o[2] == r[2] and o[3] == r[1]:
                o[3] = r[3]; break
        else:
            out.append(r)
    return out


def _cells_of(runs):
    return {(i, j) for i0, j0, i1, j1 in runs for i in range(i0, i1) for j in range(j0, j1)}


def pick(m: dict, mp, xg, yg, names=(), blocked=(), wet=None) -> list:
    """The major parks of the map m (real map px) as cells of the grid.

    names: parks to draw whatever their size; the rest are major when they cover
    AUTO_HA hectares or more (m px are metres). blocked: cells that belong to
    something else (landmark buildings)."""
    want = [re.sub(r"\s+", " ", n.strip().lower()) for n in names or ()]
    groups: dict = {}
    for pk in m.get("parks", []):
        n = (pk.get("n") or "").strip()
        if n:
            groups.setdefault(n, []).append(pk)
    cand = []
    for n, pks in groups.items():
        rings = [r for pk in pks for r in pk["r"] if r and len(r) >= 6]
        area = 0.0
        for r in rings:
            q = _pairs(r)
            area += abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(q, q[1:] + q[:1]))) / 2
        named = n.lower() in want or short_name(n).lower() in want
        if named or (area >= AUTO_HA * 1e4 and not _SKIP.search(n)):
            cand.append((0 if named else 1, -area, n, rings, named))
    cand.sort(key=lambda c: c[:3])                   # the asked-for ones claim their blocks first
    taken = set(blocked)
    out = []
    for _, _, n, rings, named in cand:
        gr = [[mp(x, y) for x, y in _pairs(r)] for r in rings]
        xs = [p[0] for r in gr for p in r]; ys = [p[1] for r in gr for p in r]
        i0, i1 = bisect_right(xg, min(xs)) - 1, bisect_right(xg, max(xs))
        j0, j1 = bisect_right(yg, min(ys)) - 1, bisect_right(yg, max(ys))
        cov = {}
        for i in range(max(0, i0), min(len(xg) - 1, i1)):
            for j in range(max(0, j0), min(len(yg) - 1, j1)):
                if (i, j) in taken:
                    continue
                n_in = 0
                for a in range(4):
                    for b in range(4):
                        p = (xg[i] + (xg[i + 1] - xg[i]) * (a + .5) / 4, yg[j] + (yg[j + 1] - yg[j]) * (b + .5) / 4)
                        if _inside(p, gr):
                            n_in += 1
                if n_in:
                    cov[(i, j)] = n_in / 16
        cells = {c for c, v in cov.items() if v >= .5 and not (wet and wet(((xg[c[0]] + xg[c[0] + 1]) / 2, (yg[c[1]] + yg[c[1] + 1]) / 2)))}
        if not cells and cov:                         # a small park: the one block it mostly stands in
            c, v = max(cov.items(), key=lambda kv: kv[1])
            if v >= .2:
                cells = {c}
        if not cells:
            continue
        if len(cells) >= 12:                           # a big park's edge: spurs trimmed, one-block notches filled
            def ctr(c):
                return ((xg[c[0]] + xg[c[0] + 1]) / 2, (yg[c[1]] + yg[c[1] + 1]) / 2)
            for _ in range(2):
                nb = lambda c, S: sum(q in S for q in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)))
                cells = {c for c in cells if nb(c, cells) >= 2}
                add = {(i, j) for i, j in {(c[0] + a, c[1] + b) for c in cells for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))}
                       if (i, j) not in cells and (i, j) not in taken and 0 <= i < len(xg) - 1 and 0 <= j < len(yg) - 1
                       and nb((i, j), cells) >= 3 and not (wet and wet(ctr((i, j))))}
                cells |= add
        if named and 1 < len(cells) <= 6 and _kind(n, len(cells)) != "trail":      # a square is a clean rectangle of blocks
            I, J = [c[0] for c in cells], [c[1] for c in cells]
            cells |= {(i, j) for i in range(min(I), max(I) + 1) for j in range(min(J), max(J) + 1)} - taken
        taken |= cells
        out.append({"n": n, "c": _runs(cells)})
    return out


# ── shape: outline, paths ──────────────────────────────────────────────────
def _components(cells):
    left, comps = set(cells), []
    while left:
        st = [left.pop()]; comp = set(st)
        while st:
            i, j = st.pop()
            for q in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                if q in left:
                    left.discard(q); comp.add(q); st.append(q)
        comps.append(comp)
    return comps


_DIRS = {(1, 0): (0, 1), (0, 1): (-1, 0), (-1, 0): (0, -1), (0, -1): (1, 0)}      # heading → the way inward (the right hand)


def _outline(cells, xg, yg, d):
    """The union of the cells as closed rings (flat ints), every side pulled d px inward."""
    edges: dict = {}
    for i, j in cells:
        for a, b, nb in (((i, j), (i + 1, j), (i, j - 1)), ((i + 1, j), (i + 1, j + 1), (i + 1, j)),
                         ((i + 1, j + 1), (i, j + 1), (i, j + 1)), ((i, j + 1), (i, j), (i - 1, j))):
            if nb not in cells:
                edges.setdefault(a, []).append(b)
    rings = []
    while edges:
        a = next(iter(edges)); ring = [a]; prev = None
        while True:
            nxt = edges.get(a)
            if not nxt:
                break
            if len(nxt) > 1 and prev is not None:         # a pinch: keep the lobes apart, turn right
                hd = (a[0] - prev[0], a[1] - prev[1]); hd = (hd[0] and hd[0] // abs(hd[0]), hd[1] and hd[1] // abs(hd[1]))
                rt = _DIRS[hd]
                nxt.sort(key=lambda b: 0 if (b[0] - a[0], b[1] - a[1]) == rt else 1)
            b = nxt.pop(0)
            if not nxt:
                del edges[a]
            prev, a = a, b
            if a == ring[0]:
                break
            ring.append(a)
        if len(ring) >= 4:
            rings.append(ring)
    out = []
    for ring in rings:
        n = len(ring)
        keep = []
        for k in range(n):                                 # drop the vertices in the middle of a straight side
            p0, p1, p2 = ring[k - 1], ring[k], ring[(k + 1) % n]
            if (p1[0] - p0[0]) * (p2[1] - p1[1]) - (p1[1] - p0[1]) * (p2[0] - p1[0]) != 0:
                keep.append(p1)
        flat = []
        n = len(keep)
        for k in range(n):
            p0, p1, p2 = keep[k - 1], keep[k], keep[(k + 1) % n]
            di = tuple((p1[t] - p0[t]) // max(1, abs(p1[t] - p0[t])) if p1[t] != p0[t] else 0 for t in (0, 1))
            do = tuple((p2[t] - p1[t]) // max(1, abs(p2[t] - p1[t])) if p2[t] != p1[t] else 0 for t in (0, 1))
            ni, no = _DIRS[di], _DIRS[do]
            flat += [round(xg[p1[0]] + d * (ni[0] + no[0])), round(yg[p1[1]] + d * (ni[1] + no[1]))]
        out.append(flat)
    return out


def _clip(pl, ok, step=9):
    """A polyline cut to where ok(x, y) holds: [[x, y, ...], ...] (runs of at least 30 px)."""
    runs, cur = [], []
    for (x0, y0), (x1, y1) in zip(pl, pl[1:]):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) // step))
        for t in range(n + 1):
            x, y = x0 + (x1 - x0) * t / n, y0 + (y1 - y0) * t / n
            if ok(x, y):
                cur.append((x, y))
            elif cur:
                runs.append(cur); cur = []
    if cur:
        runs.append(cur)
    res = []
    for r in runs:
        r = _dp(r, 1.5)
        if sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(r, r[1:])) >= 30:
            res.append([round(v) for q in r for v in q])
    return res


def _paths(kind, comp, xg, yg, ok):
    """Walkways and plazas of one block-set (bbox frame), clipped to the green."""
    I, J = [c[0] for c in comp], [c[1] for c in comp]
    i0, i1, j0, j1 = min(I), max(I) + 1, min(J), max(J) + 1
    x0, x1, y0, y1 = xg[i0] + INSET + 8, xg[i1] - INSET - 8, yg[j0] + INSET + 8, yg[j1] - INSET - 8
    cx, cy = (xg[i0] + xg[i1]) / 2, (yg[j0] + yg[j1]) / 2
    w, h = x1 - x0, y1 - y0
    paths, plaza = [], []
    def add(pl, close=False):
        paths.extend(_clip(pl + ([pl[0]] if close else []), ok))
    if kind in ("x", "*", "+", "+o"):
        add([(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)], True)                  # the walk around it
        if kind in ("x", "*"):
            add([(x0, y0), (x1, y1)]); add([(x1, y0), (x0, y1)])
        if kind in ("+", "*", "+o"):
            add([(x0, cy), (x1, cy)]); add([(cx, y0), (cx, y1)])
        plaza.append([round(cx), round(cy), round(min(w, h) * (.2 if kind == "+o" else .13))])
    elif kind == "mall":
        horiz = (i1 - i0) > (j1 - j0)
        if horiz:
            add([(x0, cy), (x1, cy)])
            for i in range(i0 + 1, i1):
                add([(xg[i], y0), (xg[i], y1)])
            plaza += [[round((xg[i] + xg[i + 1]) / 2), round(cy), 14] for i in range(i0, i1)]
        else:
            add([(cx, y0), (cx, y1)])
            for j in range(j0 + 1, j1):
                add([(x0, yg[j]), (x1, yg[j])])
            plaza += [[round(cx), round((yg[j] + yg[j + 1]) / 2), 14] for j in range(j0, j1)]
    else:                                                  # trail: a spine through the middle of the green along its long side, legs to the sides
        wide = (i1 - i0) >= (j1 - j0)
        spine = []
        rng = range(i0, i1) if wide else range(j0, j1)
        for a in rng:
            col = sorted(c[1] if wide else c[0] for c in comp if (c[0] if wide else c[1]) == a)
            if not col:
                if spine and spine[-1] is not None:
                    spine.append(None)
                continue
            mid = col[len(col) // 2]
            pt = (((xg[a] + xg[a + 1]) / 2, (yg[mid] + yg[mid + 1]) / 2) if wide else ((xg[mid] + xg[mid + 1]) / 2, (yg[a] + yg[a + 1]) / 2))
            spine.append(pt + ((col[0], col[-1]),))
        seg, segs = [], []
        for s in spine + [None]:
            if s is None:
                if len(seg) >= 2:
                    segs.append(seg)
                seg = []
            else:
                seg.append(s)
        for sg in segs:
            add([s[:2] for s in sg])
            for q, s in enumerate(sg):
                if q % 3 != 1:
                    continue
                sgn = 1 if (q // 3) % 2 else -1
                for e in s[2]:                       # a leg toward the nearest and the farthest block of this slice, on the diagonal
                    if wide:
                        ey = (yg[e] + yg[e + 1]) / 2
                        if abs(ey - s[1]) > 60:
                            add([(s[0], s[1]), (s[0] + sgn * (xg[1] - xg[0]) * .45, s[1] + (ey - s[1]) * .85)])
                    else:
                        ex = (xg[e] + xg[e + 1]) / 2
                        if abs(ex - s[0]) > 60:
                            add([(s[0], s[1]), (s[0] + (ex - s[0]) * .85, s[1] + sgn * (yg[1] - yg[0]) * .45)])
            plaza += [[round(sg[0][0]), round(sg[0][1]), 12], [round(sg[-1][0]), round(sg[-1][1]), 12]]
    plaza = [p for p in plaza if ok(p[0], p[1])]
    return paths, plaza


def _frame(f):
    """A v2 park's domain frame f = [a, ox, oy, x0, gv, nx, y0, gh, ny]: (local xg, yg, local -> page, page -> local)."""
    a, ox, oy, x0, gv, nx, y0, gh, ny = f
    xg = [x0 + gv * i for i in range(int(nx))]
    yg = [y0 + gh * j for j in range(int(ny))]
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    fwd = lambda x, y: (x * c - y * s + ox, x * s + y * c + oy)                       # noqa: E731
    back = lambda x, y: ((x - ox) * c + (y - oy) * s, -(x - ox) * s + (y - oy) * c)   # noqa: E731
    return xg, yg, fwd, back


def _to_page(rec, fwd):
    """A shaped park drawn in its domain's local frame, turned onto the page."""
    def ring(r):
        out = []
        for k in range(0, len(r) - 1, 2):
            x, y = fwd(r[k], r[k + 1])
            out += [round(x), round(y)]
        return out
    rec["r"] = [ring(r) for r in rec["r"]]
    rec["p"] = [ring(p) for p in rec["p"]]
    rec["o"] = [[round(fwd(o[0], o[1])[0]), round(fwd(o[0], o[1])[1]), o[2]] for o in rec["o"]]
    tx, ty = fwd(*rec["t"])
    rec["t"] = [round(tx), round(ty)]
    return rec


def shape(raw, xg, yg, used=(), min_pts=0) -> list:
    """The parks to draw: raw (from pick) less the cells of `used` (points: building lots). A park with a domain frame
    ("f", city engine v2: a park on a turned district's lattice) is shaped on that lattice and turned onto the page;
    the others on the page grid xg, yg."""
    out = []
    for pk in raw or []:
        if pk.get("pg"):                                   # city engine v2 free domain: already page rings, as drawn
            out.append({k: v for k, v in pk.items() if k not in ("pg", "_full")})
            continue
        if not pk.get("c"):                                # an old city's raw OSM rings: not for drawing
            continue
        if pk.get("f"):
            lxg, lyg, fwd, back = _frame(pk["f"])
            for rec in shape([{k: v for k, v in pk.items() if k != "f"}], lxg, lyg, [back(x, y) for x, y in used], min_pts):
                out.append(_to_page(rec, fwd))
            continue
        cut = {c for c in (_cell(xg, yg, x, y) for x, y in used) if c}
        cells = _cells_of(pk["c"]) - cut
        for comp in _components(cells):
            def ok(x, y, comp=comp):
                m_ = INSET - 2
                return all((_cell(xg, yg, x + sx * m_, y + sy * m_) in comp) for sx in (-1, 1) for sy in (-1, 1))
            kind = _kind(pk["n"], len(comp))
            paths, plaza = _paths(kind, comp, xg, yg, ok)
            I = sorted(c[0] for c in comp); J = sorted(c[1] for c in comp)
            mx, my = sum(I) / len(I), sum(J) / len(J)
            lc = min(comp, key=lambda c: (c[0] + .5 - mx - .5) ** 2 + (c[1] - my) ** 2 * 1.0)
            ly = (yg[lc[1] + 1] - 30) if len(comp) == 1 else (yg[lc[1]] + yg[lc[1] + 1]) / 2
            out.append({"n": short_name(pk["n"]), "k": kind, "z": len(comp),
                        "r": _outline(comp, xg, yg, INSET), "p": paths, "o": plaza,
                        "t": [round((xg[lc[0]] + xg[lc[0] + 1]) / 2), round(ly)]})
    return out
