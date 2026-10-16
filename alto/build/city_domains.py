"""City engine v2, step 2: domains (ENGINE-DESIGN.md section 1.3, and the domain side of sections 2 and 8).

    det = detect(m)                 # Detection: domains, seam candidates, per-cell classes, notes
    doms = domains(m)               # just the [Domain] (city_types.Domain)
    print(describe(doms, m, det.seams))

Pure python, no I/O, no global state. Real px are build_map px (x east, y south); angles are screen degrees.

What it does, in order (constants below):
 1. orientation field + initial labels (city_field), majority filter (3 passes, 5 of 9);
 2. water split: cells mostly under water, and the cells along every river whose band is >= RIVER_MIN_W wide,
    become WATER; components never cross them, so the same angle on two banks gives two domains;
 3. 4-connected components; components < MIN_KM2 join the label they share most border with (R2, 4 rounds);
    adjacent grid components whose modes differ by < MERGE_DEG merge (the smaller joins the larger);
 4. the -1 cells are classed from raw street: 's' void (< VOID_LEN px of street), 'X' seam band (>= BAND_SHARE of
    the length within BAND_DEG of a nearby domain's mode), 'N' free (dense and irregular). Connected N+void
    regions with >= MIN_KM2 of N become FREE domains; band cells go to the domain whose axes carry most of
    their length; remaining void / small irregular cells go to the nearest domain (BFS, never across water);
 5. each connected region of a label is one Domain (largest grid domain first: the root). Polygon = traced
    cell boundary, Douglas-Peucker at POLY_TOL cells; holes kept as `d.holes`;
 6. ownership: every street (all classes) is cut into sub-pieces <= C/2; a sub-piece belongs to the domain of
    its midpoint cell, except next to another domain, where a piece that does not fit its cell's axes
    (FIT_DEG) but fits the neighbour's goes to the neighbour (so numbered streets switch domain at the hinge,
    not at the cell edge). Cells with no domain (water, empty) hand their pieces to the nearest domain cell on
    the same bank (no river crossing). Runs shorter than SHORT_RUN between two runs of one owner are re-owned.
    Domain.streets = [{**street, "p": piece, "id": index in m["streets"]}];
 7. seam candidates: one city_types.Seam per pair of touching domains (kind "grid" | "strip" | "free"), plus
    one per domain facing water (b="water", kind "water"); `real` = the shared cell boundary (DP at 0.6 cell).
    Extra attributes: bends [(street name, (x, y))] where a street leaves one domain's axes for the other's,
    angle/rms of the line fitted through the bends (RANSAC) or through the boundary, length, void_share, avenue.

Extra attributes on each Domain (not in the shared contract): mode (deg), area (km2), holes [ring],
cells (set of (cx, cy)), share (of the city's domain area), coherence, label.
"""
from __future__ import annotations

import collections
import math
from dataclasses import dataclass, field as _dc_field

from alto.build import city_field as cf
from alto.build.city_types import Domain, Seam

MIN_KM2 = 0.6          # R2: a region smaller than this joins its neighbour
MERGE_DEG = 10.0       # R2: adjacent grids closer than this are one grid
RIVER_MIN_W = 60.0     # m: a river band at least this wide splits domains
WET = 0.5              # a cell this much under water is water
VOID_LEN = 300.0       # m of street (k <= 4) under which a -1 cell is void
BAND_SHARE = 0.65      # share of a -1 cell's street within BAND_DEG of a nearby mode -> seam band
BAND_DEG = 8.0
FIT_DEG = 8.0          # a piece "fits" a domain within this many degrees of its axes
POLY_TOL = 1.2         # polygon DP tolerance, cells
SEAM_TOL = 0.6         # seam polyline DP tolerance, cells
FREE_ENCLOSED_KM2 = 2.0   # an irregular region smaller than this, mostly enclosed by grid, is shared out among
FREE_ENCLOSED = 0.6       # ... the grids around it (this share of its border touching grid) like a seam band
POCKET_COH = 0.45      # raw coherence that makes an irregular region a grid of its own
REFINE_R = 2           # cells: a piece that does not fit its cell's domain may go to a fitting domain this near
SHORT_RUN = 60.0       # m: an ownership run shorter than this between two runs of one owner is re-owned
NEAR = 3               # cells searched for the owner of a piece in a cell without a domain
WATER = -2


@dataclass
class Detection:
    domains: list
    seams: list
    field: object
    cls: list                  # per cell: None empty, "w" water, "g" grid, "s" void, "X" band, "N" irregular
    dom: list                  # per cell: domain id or None
    unowned: list = _dc_field(default_factory=list)   # street pieces no domain took
    across: list = _dc_field(default_factory=list)    # (domain a, domain b) facing each other across water
    rivers: list = _dc_field(default_factory=list)    # [(name, median width m, [(x, y)])] that split
    notes: list = _dc_field(default_factory=list)


# ----------------------------------------------------------------------------------------------- geometry

def _pairs(flat):
    return [(flat[i], flat[i + 1]) for i in range(0, len(flat) - 1, 2)]


def _dp(pts, tol):
    """Douglas-Peucker on an open polyline."""
    if len(pts) < 3:
        return list(pts)
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    st = [(0, len(pts) - 1)]
    while st:
        i, j = st.pop()
        ax, ay = pts[i]
        bx, by = pts[j]
        L = math.hypot(bx - ax, by - ay)
        best, bk = -1.0, -1
        for k in range(i + 1, j):
            px, py = pts[k]
            d = (abs((bx - ax) * (ay - py) - (ax - px) * (by - ay)) / L) if L > 1e-9 else math.hypot(px - ax, py - ay)
            if d > best:
                best, bk = d, k
        if bk >= 0 and best > tol:
            keep[bk] = True
            st += [(i, bk), (bk, j)]
    return [p for p, k in zip(pts, keep) if k]


def _dp_ring(ring, tol):
    if len(ring) < 4:
        return list(ring)
    # start at the vertex farthest from the first one so the closing point is a real corner
    far = max(range(len(ring)), key=lambda i: (ring[i][0] - ring[0][0]) ** 2 + (ring[i][1] - ring[0][1]) ** 2)
    a = _dp(ring[:far + 1], tol)
    b = _dp(ring[far:] + [ring[0]], tol)
    return a[:-1] + b[:-1]


def ring_area(r):
    return 0.5 * sum(r[i][0] * r[(i + 1) % len(r)][1] - r[(i + 1) % len(r)][0] * r[i][1] for i in range(len(r)))


def in_ring(x, y, r):
    c = False
    n = len(r)
    for i in range(n):
        ax, ay = r[i]
        bx, by = r[i - 1]
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            c = not c
    return c


def _seg_cross(a, b, c, d):
    def o(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return (o(a, b, c) > 0) != (o(a, b, d) > 0) and (o(c, d, a) > 0) != (o(c, d, b) > 0)


def _fit_line(pts):
    """Total-least-squares line -> (angle deg mod 180, rms px, centre)."""
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    syy = sum((p[1] - my) ** 2 for p in pts)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
    ang = 0.5 * math.atan2(2 * sxy, sxx - syy)
    nx_, ny_ = -math.sin(ang), math.cos(ang)
    rms = math.sqrt(sum(((p[0] - mx) * nx_ + (p[1] - my) * ny_) ** 2 for p in pts) / n)
    return math.degrees(ang) % 180.0, rms, (mx, my)


def _ransac_line(pts, tol):
    """The line through the most points within tol (all pairs), refitted on its inliers."""
    if len(pts) < 2:
        return None
    best = None
    pts = pts[:80]
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            (ax, ay), (bx, by) = pts[i], pts[j]
            L = math.hypot(bx - ax, by - ay)
            if L < 1e-6:
                continue
            inl = [p for p in pts if abs((bx - ax) * (ay - p[1]) - (ax - p[0]) * (by - ay)) / L <= tol]
            if best is None or len(inl) > len(best):
                best = inl
    if not best or len(best) < 2:
        return None
    ang, rms, c = _fit_line(best)
    return ang, rms, c, best


# ----------------------------------------------------------------------------------------------- rasters

def _comps(grid, nx, ny, key):
    """4-connected components of the cells whose key(value) is not None and equal -> [(k, [cells])], id grid."""
    cid = [[None] * nx for _ in range(ny)]
    out = []
    for y in range(ny):
        for x in range(nx):
            k = key(grid[y][x])
            if k is None or cid[y][x] is not None:
                continue
            cid[y][x] = len(out)
            q, cells = [(x, y)], []
            while q:
                a, b = q.pop()
                cells.append((a, b))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    A, B = a + dx, b + dy
                    if 0 <= A < nx and 0 <= B < ny and cid[B][A] is None and key(grid[B][A]) == k:
                        cid[B][A] = len(out)
                        q.append((A, B))
            out.append((k, cells))
    return out, cid


def _majority(lab, nx, ny, passes=3):
    for _ in range(passes):
        new = [r[:] for r in lab]
        for y in range(ny):
            for x in range(nx):
                if lab[y][x] is None or lab[y][x] == WATER:
                    continue
                c = collections.Counter(lab[y + dy][x + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                                        if 0 <= y + dy < ny and 0 <= x + dx < nx
                                        and lab[y + dy][x + dx] is not None and lab[y + dy][x + dx] != WATER)
                v, n = c.most_common(1)[0]
                if n >= 5:
                    new[y][x] = v
        lab = new
    return lab


def _fill_rings(rings, W, H, sub):
    """Fine boolean raster (rows of bytearray) of the union of the rings (each ring filled even-odd)."""
    fx, fy = int(W // sub) + 1, int(H // sub) + 1
    wet = [bytearray(fx) for _ in range(fy)]
    for flat in rings:
        r = _pairs(flat)
        if len(r) < 3:
            continue
        rows = collections.defaultdict(list)
        for i in range(len(r)):
            (ax, ay), (bx, by) = r[i - 1], r[i]
            if ay == by:
                continue
            lo, hi = (ay, by) if ay < by else (by, ay)
            j0 = max(0, int(math.ceil(lo / sub - .5)))
            j1 = min(fy - 1, int(math.floor(hi / sub - .5)))
            for j in range(j0, j1 + 1):
                yc = (j + .5) * sub
                if lo <= yc < hi:
                    rows[j].append(ax + (bx - ax) * (yc - ay) / (by - ay))
        for j, xs in rows.items():
            xs.sort()
            row = wet[j]
            for k in range(0, len(xs) - 1, 2):
                i0 = max(0, int(math.ceil(xs[k] / sub - .5)))
                i1 = min(fx - 1, int(math.floor(xs[k + 1] / sub - .5)))
                if i1 >= i0:
                    row[i0:i1 + 1] = b"\x01" * (i1 - i0 + 1)
    return wet, fx, fy


def _river_width(wet, fx, fy, sub, pts, step):
    """Median wet width (px) across a river centre line, probing perpendicular at samples every `step` px."""
    ws = []
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        L = math.hypot(bx - ax, by - ay)
        if L < 1e-6:
            continue
        ux, uy = (bx - ax) / L, (by - ay) / L
        n = max(1, int(L // step))
        for k in range(n):
            px, py = ax + (bx - ax) * (k + .5) / n, ay + (by - ay) * (k + .5) / n
            i, j = int(px // sub), int(py // sub)
            if not (0 <= i < fx and 0 <= j < fy) or not wet[j][i]:
                ws.append(0.0)
                continue
            w = 0.0
            for sgn in (1, -1):
                t = 0.0
                while t < 3000:
                    qi, qj = int((px - sgn * uy * (t + sub / 2)) // sub), int((py + sgn * ux * (t + sub / 2)) // sub)
                    if not (0 <= qi < fx and 0 <= qj < fy) or not wet[qj][qi]:
                        break
                    t += sub / 2
                w += t
            ws.append(w)
    ws.sort()
    return ws[len(ws) // 2] if ws else 0.0


def _water(m, f, rivers):
    """(water cell grid of bool, [(name, width, pts)] barrier rivers)."""
    nx, ny, C, sc = f.nx, f.ny, f.C, f.scale
    W, H = f.W, f.H
    sub = 10.0 * sc
    rings = m.get("water") or []
    wet, fx, fy = _fill_rings(rings, W, H, sub)
    water = [[False] * nx for _ in range(ny)]
    per = int(round(C / sub))
    for cy in range(ny):
        rows = wet[cy * per:min(fy, (cy + 1) * per)]
        if not any(any(r) for r in rows):
            continue
        for cx in range(nx):
            i0, i1 = cx * per, min(fx, (cx + 1) * per)
            tot = len(rows) * (i1 - i0)
            if tot and sum(sum(r[i0:i1]) for r in rows) / tot >= WET:
                water[cy][cx] = True
    barriers = []
    src = rivers if rivers is not None else (m.get("rivers") or [])
    for r in src:
        pts = r["p"] if r.get("p") and isinstance(r["p"][0], (list, tuple)) else _pairs(r.get("p") or [])
        if len(pts) < 2 or sum(math.dist(a, b) for a, b in zip(pts, pts[1:])) < 4 * C:
            continue
        w = r.get("w") if r.get("w") is not None and rivers is not None else _river_width(wet, fx, fy, sub, pts, 50.0 * sc)
        if w < RIVER_MIN_W * sc:
            continue
        barriers.append((r.get("n") or "", round(w / sc), pts))
        prev = None
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            L = math.hypot(bx - ax, by - ay)
            n = max(1, int(L // (C / 4)))
            for k in range(n + 1):
                cx, cy = int((ax + (bx - ax) * k / n) // C), int((ay + (by - ay) * k / n) // C)
                if prev and prev[0] != cx and prev[1] != cy and 0 <= cx < nx and 0 <= prev[1] < ny:
                    water[prev[1]][cx] = True              # close the diagonal step (4-connected barrier)
                if 0 <= cx < nx and 0 <= cy < ny:
                    water[cy][cx] = True
                prev = (cx, cy)
    return water, barriers


# ----------------------------------------------------------------------------------------------- tracing

def _rings(cells, C, W, H):
    """Boundary rings of a cell set (real px), outer first."""
    S = set(cells)
    E = collections.defaultdict(list)
    for (x, y) in S:
        for a, b, dx, dy in (((x, y), (x + 1, y), 0, -1), ((x + 1, y), (x + 1, y + 1), 1, 0),
                             ((x + 1, y + 1), (x, y + 1), 0, 1), ((x, y + 1), (x, y), -1, 0)):
            if (x + dx, y + dy) not in S:
                E[a].append(b)
    rings = []
    while E:
        a = next(iter(E))
        r = [a]
        d_in = None
        while True:
            outs = E.get(r[-1])
            if not outs:
                break
            if len(outs) > 1 and d_in is not None:
                # at a pinch vertex keep to the same cell: prefer the right turn
                rx, ry = -d_in[1], d_in[0]
                outs.sort(key=lambda b: 0 if (b[0] - r[-1][0], b[1] - r[-1][1]) == (rx, ry) else 1)
            b = outs.pop(0)
            if not outs:
                del E[r[-1]]
            d_in = (b[0] - r[-1][0], b[1] - r[-1][1])
            if b == r[0]:
                break
            r.append(b)
        if len(r) >= 4:
            rings.append([(min(W, x * C), min(H, y * C)) for x, y in r])
    rings.sort(key=lambda r: -abs(ring_area(r)))
    return rings


def _chains(edges):
    """Chain undirected unit edges ((x0, y0), (x1, y1)) into polylines (longest first)."""
    adj = collections.defaultdict(list)
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    used = set()
    out = []

    def walk(s, n):
        line = [s, n]
        used.add(frozenset((s, n)))
        while True:
            cur = line[-1]
            nxt = [q for q in adj[cur] if frozenset((cur, q)) not in used]
            if len(adj[cur]) != 2 or not nxt:
                break
            used.add(frozenset((cur, nxt[0])))
            line.append(nxt[0])
        return line
    for s in [v for v in adj if len(adj[v]) != 2] + list(adj):
        for n in adj[s]:
            if frozenset((s, n)) not in used:
                out.append(walk(s, n))
    out.sort(key=lambda l: -len(l))
    return out


# ----------------------------------------------------------------------------------------------- detect

def _isdom(v):
    return v is not None and v >= 0


def detect(m, field=None, rivers=None, min_km2=MIN_KM2, merge_deg=MERGE_DEG):
    """Domains, ownership and seam candidates of a map -> Detection. See the module docstring.
    `rivers`: optional [{n, p, w?}] centre lines (real px, flat or point list) used instead of m["rivers"]."""
    f = field or cf.field(m)
    nx, ny, C, sc = f.nx, f.ny, f.C, f.scale
    W, H = f.W, f.H
    modes = list(f.modes)
    notes = []
    minc = max(1, int(round(min_km2 * 1e6 * sc * sc / (C * C))))
    lab = cf.labels(f)
    water, barriers = _water(m, f, rivers)
    for y in range(ny):
        for x in range(nx):
            if water[y][x]:
                lab[y][x] = WATER
    lab = _majority(lab, nx, ny)

    def nb4(a, b):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if 0 <= a + dx < nx and 0 <= b + dy < ny:
                yield a + dx, b + dy

    def landkey(v):
        return None if v is None or v == WATER else v

    # small grid components join their neighbour (R2)
    for _ in range(4):
        comps, cid = _comps(lab, nx, ny, landkey)
        changed = False
        for i, (l, cells) in enumerate(comps):
            if l == -1 or len(cells) >= minc:
                continue
            nb = collections.Counter(lab[B][A] for a, b in cells for A, B in nb4(a, b)
                                     if cid[B][A] not in (None, i))
            if nb:
                v = nb.most_common(1)[0][0]
                if v != l:
                    for a, b in cells:
                        lab[b][a] = v
                    changed = True
        if not changed:
            break
    # adjacent grids within MERGE_DEG are one grid (smaller joins larger)
    for _ in range(4):
        comps, cid = _comps(lab, nx, ny, landkey)
        changed = False
        for i, (l, cells) in sorted(enumerate(comps), key=lambda t: len(t[1][1])):
            if l < 0:
                continue
            nbs = collections.Counter(cid[B][A] for a, b in cells for A, B in nb4(a, b)
                                      if cid[B][A] not in (None, i) and comps[cid[B][A]][0] >= 0)
            for j, _n in nbs.most_common():
                lj, cj = comps[j]
                if lj != l and len(cj) > len(cells) and cf.lat_dist(modes[l], modes[lj]) < merge_deg:
                    for a, b in cells:
                        lab[b][a] = lj
                    changed = True
                    notes.append("merged %.1f into %.1f (%d cells)" % (modes[l], modes[lj], len(cells)))
                    break
        if not changed:
            break

    # classify the -1 cells from raw street
    raw = collections.defaultdict(list)            # (cx, cy) -> [(lattice angle, L)] for -1 cells
    for _, ax, ay, bx, by in cf.street_segments(m):
        L = math.hypot(bx - ax, by - ay)
        if L < 1e-6:
            continue
        a = cf.seg_angle(ax, ay, bx, by)
        n = max(1, int(L // (C / 2)))
        for k in range(n):
            t = (k + .5) / n
            cx, cy = int((ax + (bx - ax) * t) // C), int((ay + (by - ay) * t) // C)
            if 0 <= cx < nx and 0 <= cy < ny and lab[cy][cx] == -1:
                raw[(cx, cy)].append((a, L / n))
    cls = [[None] * nx for _ in range(ny)]
    band_pick = {}
    for y in range(ny):
        for x in range(nx):
            v = lab[y][x]
            if v is None:
                continue
            if v == WATER:
                cls[y][x] = "w"
                continue
            if v >= 0:
                cls[y][x] = "g"
                continue
            if f.S[y][x] < VOID_LEN * sc:
                cls[y][x] = "s"
                continue
            near = {lab[y + dy][x + dx] for dy in range(-2, 3) for dx in range(-2, 3)
                    if 0 <= x + dx < nx and 0 <= y + dy < ny and _isdom(lab[y + dy][x + dx])}
            cand = sorted(near) if near else list(range(len(modes)))
            tot = sum(L for _, L in raw[(x, y)]) or 1.0
            per = {c: sum(L for a, L in raw[(x, y)] if cf.lat_dist(a, modes[c]) <= BAND_DEG) for c in cand}
            fit = sum(L for a, L in raw[(x, y)] if any(cf.lat_dist(a, modes[c]) <= BAND_DEG for c in cand))
            if near and fit / tot >= BAND_SHARE:
                cls[y][x] = "X"
                band_pick[(x, y)] = max(per, key=per.get)
            else:
                cls[y][x] = "N"
    # free domains: connected irregular+void regions with enough irregular cells
    FREE0 = 1000
    fcomps, _ = _comps(cls, nx, ny, lambda v: 1 if v in ("N", "s") else None)
    nfree = 0
    for _, cells in fcomps:
        nN = sum(1 for a, b in cells if cls[b][a] == "N")
        if nN < minc:
            continue
        cs = set(cells)
        # an irregular region whose own raw street is one coherent grid off its neighbours' axes is a grid of
        # its own (the field there was blurred by its neighbours): it becomes a new mode
        X_ = sum(f.X[b][a] for a, b in cells if cls[b][a] == "N")
        Y_ = sum(f.Y[b][a] for a, b in cells if cls[b][a] == "N")
        S_ = sum(f.S[b][a] for a, b in cells if cls[b][a] == "N") or 1.0
        own = math.degrees(math.atan2(Y_, X_) / 4.0) % 90.0
        notes.append("irregular region %.2f km2 at cell %s: raw angle %.1f coherence %.2f" % (
            nN * C * C / 1e6 / sc / sc, cells[0], own, math.hypot(X_, Y_) / S_))
        nbl = {lab[B][A] for a, b in cells for A, B in nb4(a, b) if _isdom(lab[B][A])}
        if math.hypot(X_, Y_) / S_ >= POCKET_COH and all(cf.lat_dist(own, modes[l]) >= merge_deg for l in nbl):
            near = [i for i in range(len(modes)) if cf.lat_dist(own, modes[i]) < merge_deg]
            if near:
                li = min(near, key=lambda i: cf.lat_dist(own, modes[i]))     # a weak mode that lost its cells
            else:
                modes.append(round(own, 1))
                li = len(modes) - 1
            for a, b in cells:
                if cls[b][a] == "N":
                    cls[b][a] = "g"
                lab[b][a] = li
            notes.append("irregular region at cell %s is a grid of its own at %.1f" % (cells[0], modes[li]))
            continue
        border = collections.Counter("g" if _isdom(lab[B][A]) or cls[B][A] == "X" else "o" for a, b in cells for A, B in nb4(a, b)
                                     if (A, B) not in cs and lab[B][A] != WATER)
        if (nN * C * C / 1e6 / sc / sc < FREE_ENCLOSED_KM2
                and border["g"] >= FREE_ENCLOSED * max(1, border["g"] + border["o"])):
            # a small irregular pocket between grids (a fan): shared out like a seam band
            for a, b in cells:
                near = {lab[b + dy][a + dx] for dy in range(-2, 3) for dx in range(-2, 3)
                        if 0 <= a + dx < nx and 0 <= b + dy < ny and _isdom(lab[b + dy][a + dx])}
                per = {c: sum(L for g, L in raw[(a, b)] if cf.lat_dist(g, modes[c]) <= BAND_DEG) for c in near}
                if per and max(per.values()) > 0:
                    band_pick[(a, b)] = max(per, key=per.get)
            notes.append("irregular pocket of %.2f km2 at cell %s shared out among its grids" % (
                len(cells) * C * C / 1e6 / sc / sc, cells[0]))
            continue
        for a, b in cells:
            lab[b][a] = FREE0 + nfree
        nfree += 1
    for (x, y), l in band_pick.items():
        lab[y][x] = l
    # remaining -1 cells: nearest labelled cell (multi-source BFS over land)
    q = collections.deque((x, y) for y in range(ny) for x in range(nx) if _isdom(lab[y][x]))
    while q:
        a, b = q.popleft()
        for A, B in nb4(a, b):
            if lab[B][A] == -1:
                lab[B][A] = lab[b][a]
                q.append((A, B))
    # one Domain per connected region of a label
    comps, cid = _comps(lab, nx, ny, lambda v: v if v is not None and v >= 0 else None)
    keep = []
    for i, (l, cells) in enumerate(comps):
        if len(cells) < minc:
            notes.append("dropped an isolated %s region of %.2f km2 at cell %s" % (
                "free" if l >= FREE0 else "%.1f deg" % modes[l], len(cells) * C * C / 1e6 / sc / sc, cells[0]))
            continue
        keep.append(i)
    keep.sort(key=lambda i: (comps[i][0] >= FREE0, -len(comps[i][1])))
    dom = [[None] * nx for _ in range(ny)]
    doms = []
    tot_cells = sum(len(comps[i][1]) for i in keep) or 1
    for did, i in enumerate(keep):
        l, cells = comps[i]
        for a, b in cells:
            dom[b][a] = did
        rings = _rings(cells, C, W, H)
        poly = _dp_ring(rings[0], POLY_TOL * C) if rings else []
        mode = modes[l] if l < FREE0 else None
        d = Domain(id=did, kind="free" if l >= FREE0 else "grid",
                   theta=math.radians(cf.wrap45(mode)) if mode is not None else 0.0,
                   poly=[(round(x, 1), round(y, 1)) for x, y in poly], streets=[])
        d.mode = mode
        d.label = l
        d.cells = set(cells)
        d.area = round(len(cells) * C * C / 1e6 / sc / sc, 2)
        d.share = round(len(cells) / tot_cells, 3)
        d.holes = [[(round(x, 1), round(y, 1)) for x, y in _dp_ring(r, POLY_TOL * C)] for r in rings[1:]
                   if abs(ring_area(r)) >= 2 * C * C]
        d.coherence = 0.0
        doms.append(d)

    unowned = _own(m, f, dom, doms, barriers)
    # refine each domain's angle from its own aligned street (length-weighted circular mean of 4 theta)
    for d in doms:
      for win in ((10.0, 5.0) if d.kind == "grid" else (None,)):
        sx = sy = tot = 0.0
        ref = d.mode if win else None
        for s in d.streets:
            if s.get("k", 9) > cf.KMAX or s.get("t"):
                continue
            for (ax, ay), (bx, by) in zip(*(lambda p: (p, p[1:]))(_pairs(s["p"]))):
                L = math.hypot(bx - ax, by - ay)
                a = cf.seg_angle(ax, ay, bx, by)
                if L < 1 or (ref is not None and cf.lat_dist(a, ref) > win):
                    continue
                r = math.radians(4 * a)
                sx += L * math.cos(r)
                sy += L * math.sin(r)
                tot += L
        if tot:
            mean = math.degrees(math.atan2(sy, sx)) / 4.0 % 90.0
            d.coherence = round(math.hypot(sx, sy) / tot, 3)
            if d.kind == "grid":
                d.theta = math.radians(cf.wrap45(mean))
                d.mode = round(mean, 2)
    seams, across = _seams(m, f, dom, doms, cls, water)
    return Detection(domains=doms, seams=seams, field=f, cls=cls, dom=dom, unowned=unowned, across=across,
                     rivers=[(n, w, pts) for n, w, pts in barriers], notes=notes)


def domains(m, field=None, rivers=None):
    """[Domain] of a map (city_types.Domain; root = the largest grid domain = id 0). See detect()."""
    return detect(m, field, rivers).domains


# ----------------------------------------------------------------------------------------------- ownership

def _own(m, f, dom, doms, barriers):
    nx, ny, C, sc = f.nx, f.ny, f.C, f.scale
    # river polylines cut into short chunks with bounding boxes, for same-bank tests
    chunks = []
    for _, _, pts in barriers:
        for i in range(0, len(pts) - 1, 16):
            ch = pts[i:i + 17]
            xs, ys = [p[0] for p in ch], [p[1] for p in ch]
            chunks.append((min(xs), min(ys), max(xs), max(ys), ch))

    def crosses(a, b):
        x0, x1 = min(a[0], b[0]), max(a[0], b[0])
        y0, y1 = min(a[1], b[1]), max(a[1], b[1])
        for cx0, cy0, cx1, cy1, ch in chunks:
            if cx1 < x0 or cx0 > x1 or cy1 < y0 or cy0 > y1:
                continue
            for p, q in zip(ch, ch[1:]):
                if _seg_cross(a, b, p, q):
                    return True
        return False

    near_cache = {}

    def nearest(mid):
        cx, cy = int(mid[0] // C), int(mid[1] // C)
        best, bd = None, None
        for r in range(1, NEAR + 1):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    X, Y = cx + dx, cy + dy
                    if not (0 <= X < nx and 0 <= Y < ny) or dom[Y][X] is None:
                        continue
                    c = ((X + .5) * C, (Y + .5) * C)
                    d = (c[0] - mid[0]) ** 2 + (c[1] - mid[1]) ** 2
                    if (bd is None or d < bd) and not crosses(mid, c):
                        best, bd = dom[Y][X], d
            if best is not None:
                return best
        return None

    unowned = []
    short = SHORT_RUN * sc
    for si, s in enumerate(m.get("streets") or []):
        pts = _pairs(s.get("p") or [])
        if len(pts) < 2:
            continue
        subs = []                     # [(a, b, owner)]
        for a, b in zip(pts, pts[1:]):
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            n = max(1, int(math.ceil(L / (C / 2))))
            ang = cf.seg_angle(a[0], a[1], b[0], b[1]) if L >= 1e-6 else None
            for k in range(n):
                p = (a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n)
                q = (a[0] + (b[0] - a[0]) * (k + 1) / n, a[1] + (b[1] - a[1]) * (k + 1) / n) if k < n - 1 else b
                mid = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
                cx, cy = int(mid[0] // C), int(mid[1] // C)
                o = dom[cy][cx] if 0 <= cx < nx and 0 <= cy < ny else None
                if o is None:
                    key = (cx, cy, mid[0] > (cx + .5) * C, mid[1] > (cy + .5) * C)
                    o = near_cache[key] if key in near_cache and not chunks else nearest(mid)
                    near_cache[key] = o
                elif ang is not None and L >= 15 * sc and doms[o].kind == "grid":
                    R = REFINE_R
                    nbs = {dom[cy + dy][cx + dx] for dy in range(-R, R + 1) for dx in range(-R, R + 1)
                           if 0 <= cx + dx < nx and 0 <= cy + dy < ny and dom[cy + dy][cx + dx] is not None}
                    if len(nbs) > 1 and cf.lat_dist(ang, doms[o].mode) > FIT_DEG:
                        fits = [(cf.lat_dist(ang, doms[d].mode), d) for d in nbs
                                if d != o and doms[d].kind == "grid" and cf.lat_dist(ang, doms[d].mode) <= FIT_DEG]
                        if fits:
                            o = min(fits)[1]
                subs.append((p, q, o))
        # runs, then re-own short runs sandwiched between runs of one owner
        runs = []
        for p, q, o in subs:
            if runs and runs[-1][0] == o:
                runs[-1][1].append(q)
                runs[-1][2] += math.dist(p, q)
            else:
                runs.append([o, [p, q], math.dist(p, q)])
        changed = True
        while changed and len(runs) >= 3:
            changed = False
            for i in range(1, len(runs) - 1):
                if runs[i][2] < short and runs[i - 1][0] == runs[i + 1][0] != runs[i][0]:
                    runs[i - 1][1] += runs[i][1][1:] + runs[i + 1][1][1:]
                    runs[i - 1][2] += runs[i][2] + runs[i + 1][2]
                    del runs[i:i + 2]
                    changed = True
                    break
        for o, line, _L in runs:
            piece = dict(s)
            piece["p"] = [round(v, 1) for q in _dedupe(line) for v in q]
            piece["id"] = si
            (unowned if o is None else doms[o].streets).append(piece)
    return unowned


def _dedupe(line):
    """Drop the split points that are collinear with their neighbours (the C/2 cuts inside one segment)."""
    if len(line) < 3:
        return line
    out = [line[0]]
    for i in range(1, len(line) - 1):
        a, b, c = out[-1], line[i], line[i + 1]
        cr = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if abs(cr) > 1e-6 * max(1.0, math.dist(a, c)) ** 2:
            out.append(b)
    out.append(line[-1])
    return out


# ----------------------------------------------------------------------------------------------- seams

def _seams(m, f, dom, doms, cls, water):
    nx, ny, C, sc = f.nx, f.ny, f.C, f.scale
    pair_edges = collections.defaultdict(list)
    void_n = collections.Counter()
    for y in range(ny):
        for x in range(nx):
            a = dom[y][x]
            for dx, dy in ((1, 0), (0, 1)):
                X, Y = x + dx, y + dy
                if not (X < nx and Y < ny):
                    continue
                b = dom[Y][X]
                e = ((X, Y), (X, Y + 1)) if dx else ((X, Y), (X + 1, Y))
                if a is not None and b is not None and a != b:
                    k = (min(a, b), max(a, b))
                    pair_edges[k].append(e)
                    if cls[y][x] == "s" or cls[Y][X] == "s":
                        void_n[k] += 1
                elif (a is None) != (b is None) and (water[y][x] or water[Y][X]):
                    pair_edges[(a if a is not None else b, "water")].append(e)
    # bends: a street whose consecutive pieces belong to two grid domains and fit each one's axes
    bends = collections.defaultdict(list)
    ends = collections.defaultdict(list)           # street id -> [(domain, first pt, last pt, a0, a1)]
    for d in doms:
        for s in d.streets:
            p = _pairs(s["p"])
            if len(p) >= 2:
                ends[s["id"]].append((d.id, p, s.get("n") or ""))
    for sid, lst in ends.items():
        for (da, pa, n), (db, pb, _) in ((u, v) for u in lst for v in lst if u[0] < v[0]):
            A, B = doms[da], doms[db]
            if A.kind != "grid" or B.kind != "grid":
                continue
            for (p_end, p_prev), (q_end, q_next) in (((pa[-1], _back(pa[::-1], sc)), (pb[0], _back(pb, sc))),
                                                      ((pb[-1], _back(pb[::-1], sc)), (pa[0], _back(pa, sc)))):
                if math.dist(p_end, q_end) > 1:
                    continue
                a1 = cf.seg_angle(p_prev[0], p_prev[1], p_end[0], p_end[1])
                a2 = cf.seg_angle(q_end[0], q_end[1], q_next[0], q_next[1])
                fa = lambda a, D: cf.lat_dist(a, D.mode) <= 6
                if (fa(a1, A) and fa(a2, B)) or (fa(a1, B) and fa(a2, A)):
                    bends[(da, db)].append((n, (round(p_end[0], 1), round(p_end[1], 1))))
    out = []
    for k, edges in pair_edges.items():
        a, b = k
        lines = [_dp([(min(f.W, x * C), min(f.H, y * C)) for x, y in ch], SEAM_TOL * C) for ch in _chains(edges)]
        lines = [l for l in lines if len(l) >= 2]
        if not lines:
            continue
        if b == "water":
            kind = "water"
        elif doms[a].kind == "free" or doms[b].kind == "free":
            kind = "free"
        elif void_n[k] >= .5 * len(edges):
            kind = "strip"
        else:
            kind = "grid"
        s = Seam(a=a, b=b, kind=kind, real=[(round(x, 1), round(y, 1)) for x, y in lines[0]])
        s.pieces = lines[1:]
        s.length = round(len(edges) * C / sc)
        s.void_share = round(void_n[k] / len(edges), 2) if b != "water" else 0.0
        s.bends = bends.get(k, [])
        fit = _ransac_line([p for _, p in s.bends], 60 * sc) if len(s.bends) >= 4 else None
        if fit and len(fit[3]) >= 4:
            s.angle, s.rms, s.centre = round(fit[0], 1), round(fit[1], 1), fit[2]
            s.fit = "bends"
            s.hinges = len(fit[3])
        else:
            pts = [q for l in lines for q in l]
            ang, rms, c = _fit_line(pts)
            s.angle, s.rms, s.centre, s.fit, s.hinges = round(ang, 1), round(rms, 1), c, "boundary", 0
        s.boundary = s.real                       # the shared cell boundary (staircase at C, DP at SEAM_TOL)
        s.avenue = _seam_avenue(m, s, sc) if b != "water" else None
        if s.avenue and getattr(s, "avenue_line", None):
            s.real = s.avenue_line                # the avenue itself, where it runs along the seam
        elif s.fit == "bends":                    # the straight line through the bends, over the seam's extent
            th = math.radians(s.angle)
            ux, uy = math.cos(th), math.sin(th)
            cx, cy = s.centre
            ts = [(p[0] - cx) * ux + (p[1] - cy) * uy for l in lines for p in l]
            s.real = [(round(cx + ux * t, 1), round(cy + uy * t, 1)) for t in (min(ts), max(ts))]
        out.append(s)
    out.sort(key=lambda s: (s.b == "water", -s.length))
    # domains facing each other across water: both touch one water component
    across = collections.Counter()
    lines_ = [[(x, y) for x in range(nx)] for y in range(ny)] + [[(x, y) for y in range(ny)] for x in range(nx)]
    for ln in lines_:
        last, gap = None, 0
        for x, y in ln:
            d = dom[y][x]
            if d is not None:
                if last is not None and last != d and 1 <= gap <= 3:
                    across[(min(last, d), max(last, d))] += 1
                last, gap = d, 0
            elif water[y][x] and last is not None:
                gap += 1
            else:
                last, gap = None, 0
    return out, sorted(k for k, v in across.items() if v >= 3)


def _back(p, sc, reach=40.0):
    """The point at least `reach` px along the polyline from its first point (or its far end): the direction
    of a piece where it ends is taken over that stretch, so a short stub at the very end does not decide it."""
    acc = 0.0
    for a, b in zip(p, p[1:]):
        acc += math.dist(a, b)
        if acc >= reach * sc:
            return b
    return p[-1]


def _seam_avenue(m, s, sc):
    """The named k <= 3 street lying along the seam: most length within 90 px (fitted line) or 150 px (cell
    boundary) of it and within 14 degrees of its direction; at least 40% of the seam's length."""
    th = math.radians(s.angle)
    ux, uy = math.cos(th), math.sin(th)
    cx, cy = s.centre
    tol = (90 if s.fit == "bends" else 150) * sc
    pts = s.real + [q for l in s.pieces for q in l]
    ts = [(p[0] - cx) * ux + (p[1] - cy) * uy for p in pts]
    t0, t1 = min(ts) - 100 * sc, max(ts) + 100 * sc
    per = collections.Counter()
    segs = collections.defaultdict(list)
    for st in m.get("streets") or []:
        if st.get("k", 9) > 3 or not st.get("n"):
            continue
        p = _pairs(st["p"])
        for (ax, ay), (bx, by) in zip(p, p[1:]):
            L = math.hypot(bx - ax, by - ay)
            if L < 1:
                continue
            a = math.degrees(math.atan2(by - ay, bx - ax)) % 180.0
            dd = abs(a - s.angle) % 180.0
            if min(dd, 180 - dd) > 14:
                continue
            mx, my = (ax + bx) / 2, (ay + by) / 2
            t = (mx - cx) * ux + (my - cy) * uy
            if not (t0 <= t <= t1):
                continue
            if s.fit == "bends":
                dist = abs(-(mx - cx) * uy + (my - cy) * ux)
            else:
                dist = min(math.dist((mx, my), q) for q in _dense(pts, 100 * sc))
            if dist <= tol:
                per[st["n"]] += L
                segs[st["n"]].append((t, (ax, ay), (bx, by)))
    if not per:
        return None
    n, L = per.most_common(1)[0]
    s.avenue_len = round(L / sc)
    if L < .4 * s.length * sc:
        return None
    # the avenue's own line along the seam: its pieces in order along the seam, joined
    line = []
    for _, a, b in sorted(segs[n]):
        if (b[0] - a[0]) * ux + (b[1] - a[1]) * uy < 0:
            a, b = b, a
        for q in (a, b):
            if not line or math.dist(line[-1], q) > 2 * sc:
                line.append(q)
    s.avenue_line = [(round(x, 1), round(y, 1)) for x, y in _dp(line, 3 * sc)]
    return n


def _dense(pts, step):
    out = []
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.dist(a, b) // step))
        out += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n)]
    return out + pts[-1:]


# ----------------------------------------------------------------------------------------------- describe

def latlon(m, x, y):
    """Real px -> (lat, lon) through the map's bbox [s, w, n, e]."""
    s, w, n, e = m["bbox"]
    return round(n - (y / m["H"]) * (n - s), 4), round(w + (x / m["W"]) * (e - w), 4)


def describe(doms, m=None, seams=None, width=64):
    """Compact text summary: one line per domain (and seam), then an ASCII map drawn from the polygons
    (letters A.. = grid domains in id order, lower case = free domains, '.' = none)."""
    out = []
    root = next((d for d in doms if d.kind == "grid"), None)
    for d in doms:
        ang = math.degrees(d.theta)
        rel = ""
        if root is not None and d.kind == "grid":
            r = (ang - math.degrees(root.theta) + 45) % 90 - 45
            rel = " rel %+.1f" % r
        area = getattr(d, "area", None)
        xs = [p[0] for p in d.poly] or [0]
        ys = [p[1] for p in d.poly] or [0]
        out.append("%s %-4s %-5s theta %6.1f%s  %s km2  streets %d  bbox x%d-%d y%d-%d  poly %d pts%s" % (
            _letter(d), "#%d" % d.id, d.kind, ang, rel, "%.1f" % area if area is not None else "?",
            len(d.streets or []), min(xs), max(xs), min(ys), max(ys), len(d.poly),
            "  holes %d" % len(d.holes) if getattr(d, "holes", None) else ""))
        if m is not None and d.poly:
            out.append("      latlon " + " ".join("(%.3f,%.3f)" % latlon(m, x, y) for x, y in d.poly))
    for s in seams or []:
        out.append("seam %s|%s %-5s len %5d m  angle %5.1f rms %4.0f (%s, %d hinges)  void %.2f  avenue %s" % (
            _letter_of(doms, s.a), "~" if s.b == "water" else _letter_of(doms, s.b), s.kind, getattr(s, "length", 0),
            getattr(s, "angle", 0), getattr(s, "rms", 0), getattr(s, "fit", "?"), getattr(s, "hinges", 0),
            getattr(s, "void_share", 0), s.avenue))
    if doms:
        xs = [p[0] for d in doms for p in d.poly]
        ys = [p[1] for d in doms for p in d.poly]
        W = (m or {}).get("W") or max(xs)
        H = (m or {}).get("H") or max(ys)
        st = W / width
        for j in range(int(H / (st * 1.8)) + 1):
            row = ""
            for i in range(width):
                x, y = (i + .5) * st, (j + .5) * st * 1.8
                ch = "."
                for d in doms:
                    if d.poly and in_ring(x, y, d.poly) and not any(in_ring(x, y, h) for h in getattr(d, "holes", [])):
                        ch = _letter(d)
                        break
                row += ch
            out.append("   " + row)
    return "\n".join(out)


def _letter(d):
    c = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[d.id % 26]
    return c.lower() if d.kind == "free" else c


def _letter_of(doms, i):
    return _letter(doms[i]) if isinstance(i, int) and 0 <= i < len(doms) else str(i)
