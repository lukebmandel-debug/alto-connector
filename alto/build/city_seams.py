"""City engine v2, steps S5-S6: seams between domains and the layout of the domains on the page
(design sections 2 and 4.3).

A seam is where two domains (two street grids at different angles) meet. In the real city it is an
avenue (Baltimore Ave between West and Southwest Philadelphia, Kensington Ave in the north-east): one
family of streets KINKS on it (the numbered streets bend 52 degrees on Baltimore and run on as the
tilted grid's streets), the other family of each side stops on it. On the page the seam is therefore
drawn as a straight line at its own, ANGLED, direction; lines of either side end on it with a rounded
T-join, and the streets that really continue cross it with one rounded kink (a hinge).

Angle of the seam (design 2.3), with the ONE trade-off constant R_TOL:
along the seam the hinge streets must meet at the same points from both sides, so
`g_child / |sin a_child| = g_parent / |sin a_parent|` (a = angle between the seam and the family).
The fold line (the mirror line of the two families) gives equal spacing; the real seam angle in
general does not. The seam is drawn at `phi = phi_real + t (phi_fold - phi_real)` with the smallest t in
[0, 1] for which the child's block width is within R_TOL of a standard block (CW or CH; the child's
roles are chosen here, which makes a seam at 45 degrees exact because CW/CH = sqrt 2).

    seams(domains, lines=None, avenues=None, rivers=None, sigma=1.0) -> [Seam]      (S5)
    equalise(seam, lines_a, lines_b) -> stats                                         (slot equalisation)
    layout(domains, seams, lines, pad=PAD) -> Layout                                  (S6)
    plan(domains, avenues=None, majors=(), sigma=None, rivers=None) -> (seams, lines, Layout)   (S4-S6 in order)
    solve_phi(phi_real, d_p, d_q, g_p, nominals, tol) -> dict                         (the seam-angle rule)
    tilt(theta_p, theta_q) -> (raw, snapped)                                          (child page tilt)

Conventions: real px are build_map px (x east, y south); angles are screen degrees (y down). A domain's
theta is normalised here to within 45 degrees of its parent's (same lattice, a multiple of 90 apart) so its
local "h" family is the one nearest the parent's rows. Seam.a is the parent (placed first), Seam.b the child.
Extra per-seam data the layout needs live in `seam.info` (a dict): see `_Part` below.
"""
from __future__ import annotations

import math
import random
from collections import Counter, deque

from .city_lines import CW, CH, centroid, mapping as local_mapping, select as select_lines, scale as city_scale, \
    block_aspect, block_ch, ASPECT_MAX
from .city_types import Seam
from .palace_grid import PAD, LEAD, _dp, _pairs, norm

R_TOL = 0.10            # THE trade-off: a child block may differ from a standard block by at most 10% (0 = strict fold)
HINGE_NEAR = 130.0      # a street's run in one domain and its run in the other this close = one street bending
HINGE_ALIGN = 6.0       # degrees: a run follows a domain axis
RUN_MIN = 150.0         # px of aligned run on each side of a bend
RANSAC_TOL = 60.0       # px: a bend on the hinge line
HINGE_MIN = 4           # bends on one line to make a hinge seam
AV_NEAR, AV_DEG, AV_SHARE = 90.0, 14.0, 0.4     # the seam avenue: near, parallel, covering 40%
SNAP45 = 4.0            # a tilt this close to 45 degrees is 45
SNAP0 = 1.0             # a tilt this close to 0 is 0 (one grid split only by a river: Center City | West Philadelphia)
TEE_SNAP = 6.0          # a tee seam snaps to a nearby axis/45/fold within this
ADJ_D = 300.0           # px: polygons this close touch
SAMPLE = 50.0           # px between boundary samples
FOLD_MIN_CROSS = 30.0   # the fold must cross the hinge family at least this much
EXT = 1.5               # blocks a child lattice may be extended toward a seam it faces


# ── small geometry ──────────────────────────────────────────────────────────
def _wrap(a):
    """A line angle in (-90, 90]."""
    a = (a + 90.0) % 180.0 - 90.0
    return 90.0 if a == -90.0 else a


def _ldiff(a, b):
    """Signed smallest difference between two line angles, in (-90, 90]."""
    return _wrap(a - b)


def _cd90(a, b):
    d = abs(a - b) % 90.0
    return min(d, 90.0 - d)


def _unit(deg):
    r = math.radians(deg)
    return (math.cos(r), math.sin(r))


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _rot(p, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def _segd(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def _ring_d(p, ring):
    n = len(ring)
    return min(_segd(p, ring[i], ring[(i + 1) % n]) for i in range(n))


def _inside(p, ring):
    x, y = p
    c = False
    n = len(ring)
    for i in range(n):
        (x0, y0), (x1, y1) = ring[i], ring[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


def area(poly):
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                   for i in range(len(poly)))) / 2 if len(poly) >= 3 else 0.0


def fit_line(pts):
    """Orthogonal regression: (mx, my, angle deg) of the best line through pts, and the rms distance."""
    n = len(pts)
    mx, my = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts); syy = sum((p[1] - my) ** 2 for p in pts)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
    a = 0.5 * math.degrees(math.atan2(2 * sxy, sxx - syy))
    nx, ny = -math.sin(math.radians(a)), math.cos(math.radians(a))
    rms = math.sqrt(sum(((p[0] - mx) * nx + (p[1] - my) * ny) ** 2 for p in pts) / n)
    return (mx, my, _wrap(a)), rms


def _ldist(p, l):
    mx, my, a = l
    return abs(-(p[0] - mx) * math.sin(math.radians(a)) + (p[1] - my) * math.cos(math.radians(a)))


def _lpos(p, l):
    mx, my, a = l
    return (p[0] - mx) * math.cos(math.radians(a)) + (p[1] - my) * math.sin(math.radians(a))


def clip_half(poly, n, c, keep="le"):
    """Sutherland-Hodgman: the part of a convex polygon with n.x <= c (keep="le") or >= c ("ge")."""
    out = []
    sg = 1.0 if keep == "le" else -1.0
    m = len(poly)
    for i in range(m):
        a, b = poly[i], poly[(i + 1) % m]
        sa, sb = sg * (_dot(n, a) - c), sg * (_dot(n, b) - c)
        if sa <= 0:
            out.append(a)
        if (sa <= 0) != (sb <= 0):
            t = sa / (sa - sb)
            out.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
    return out


def _seg_interval(p0, p1, convex):
    """Parameter interval [t0, t1] of segment p0->p1 inside a convex polygon (any orientation), or None."""
    m = len(convex)
    if m < 3:
        return None
    sgn = 1.0 if sum(convex[i][0] * convex[(i + 1) % m][1] - convex[(i + 1) % m][0] * convex[i][1] for i in range(m)) > 0 else -1.0
    t0, t1 = 0.0, 1.0
    d = (p1[0] - p0[0], p1[1] - p0[1])
    for i in range(m):
        a, b = convex[i], convex[(i + 1) % m]
        e = (b[0] - a[0], b[1] - a[1])
        nrm = (sgn * -e[1], sgn * e[0])                 # inward normal
        num = _dot(nrm, (p0[0] - a[0], p0[1] - a[1]))
        den = _dot(nrm, d)
        if abs(den) < 1e-12:
            if num < 0:
                return None
            continue
        t = -num / den
        if den > 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return None
    return (t0, t1)


def _isect(n1, c1, n2, c2):
    det = n1[0] * n2[1] - n1[1] * n2[0]
    if abs(det) < 1e-12:
        return None
    return ((c1 * n2[1] - c2 * n1[1]) / det, (n1[0] * c2 - n2[0] * c1) / det)


# ── the seam-angle rule (design 2.3 / 2.4) ──────────────────────────────────
def tilt(theta_p, theta_q):
    """Child page tilt relative to the parent, degrees: (raw in [-45, 45), snapped: +-45 within SNAP45, else 0.5)."""
    raw = ((theta_q - theta_p + 45.0) % 90.0) - 45.0
    if abs(abs(raw) - 45.0) <= SNAP45:
        return raw, (45.0 if raw > 0 else -45.0)
    if abs(raw) <= SNAP0:
        return raw, 0.0
    return raw, round(raw * 2) / 2


def spacing_ratio(phi, d_p, d_q):
    """|sin(phi - d_q)| / |sin(phi - d_p)|: the child's hinge-family spacing over the parent's that makes the
    two families meet at the same points along a seam at angle phi."""
    sp = abs(math.sin(math.radians(phi - d_p)))
    sq = abs(math.sin(math.radians(phi - d_q)))
    return sq / sp if sp > 1e-9 else float("inf")


def fold_angle(d_p, d_q, near=None):
    """The fold (mirror) line of two line directions: of the two bisectors, the one crossing d_p by at least
    FOLD_MIN_CROSS degrees, and of those the one nearest `near`."""
    b1 = _wrap((d_p + _ldiff(d_q, d_p) / 2.0))
    cands = [b1, _wrap(b1 + 90.0)]
    ok = [c for c in cands if abs(_ldiff(c, d_p)) >= FOLD_MIN_CROSS] or sorted(cands, key=lambda c: -abs(_ldiff(c, d_p)))[:1]
    if near is None:
        return ok[0]
    return min(ok, key=lambda c: abs(_ldiff(c, near)))


def solve_phi(phi_real, d_p, d_q, g_p, nominals=(CW, CH), tol=R_TOL):
    """The page angle of a hinge seam. d_p, d_q: page directions of the hinge family on each side; g_p: the
    parent family's page spacing; nominals: the block widths the child family may take. Returns
    {phi, t, fold, r (geometric spacing ratio), g (child family spacing), nominal, ratio (g/nominal), err}."""
    fold = fold_angle(d_p, d_q, phi_real)
    span = _ldiff(fold, phi_real)

    def at(t):
        phi = _wrap(phi_real + t * span)
        r = spacing_ratio(phi, d_p, d_q)
        g = r * g_p
        nom = min(nominals, key=lambda x: abs(g / x - 1))
        return phi, r, g, nom, abs(g / nom - 1)
    t_ok = None
    prev = 0.0
    for k in range(0, 101):
        t = k / 100.0
        if at(t)[4] <= tol + 1e-12:
            t_ok = t
            if k:
                lo, hi = prev, t                         # refine: smallest t meeting the tolerance
                for _ in range(40):
                    mid = (lo + hi) / 2
                    if at(mid)[4] <= tol + 1e-12:
                        hi = mid
                    else:
                        lo = mid
                t_ok = hi
            break
        prev = t
    t_ok = 1.0 if t_ok is None else round(t_ok, 9)
    phi, r, g, nom, e = at(t_ok)
    return {"phi": phi, "t": t_ok, "fold": fold, "r": r, "g": g, "nominal": nom, "ratio": g / nom,
            "err": abs(_ldiff(phi, phi_real))}


# ── real-geometry analysis ──────────────────────────────────────────────────
def _runs(streets, theta_deg):
    """Aligned runs of the named streets: (name, family, start, end, length). family "h" runs along
    theta, "v" along theta + 90."""
    out = []
    for st in streets or ():
        if st.get("t") or not st.get("n") or st.get("k", 9) > 4:
            continue
        pts = _dp(_pairs(st["p"]), 8)
        cur = None
        for a, b in zip(pts, pts[1:]):
            L = math.dist(a, b)
            ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
            fam = "h" if _cd90(ang, theta_deg) <= HINGE_ALIGN and abs(_ldiff(ang, theta_deg)) < 45 else \
                  "v" if _cd90(ang, theta_deg) <= HINGE_ALIGN else None
            if L < 20:
                if cur:
                    cur[3] = b
                continue
            if cur and cur[1] == fam and fam is not None:
                cur[3] = b; cur[4] += L
            else:
                if cur and cur[1] is not None and cur[4] >= RUN_MIN:
                    out.append(tuple(cur))
                cur = [norm(st["n"]), fam, a, b, L]
        if cur and cur[1] is not None and cur[4] >= RUN_MIN:
            out.append(tuple(cur))
    return out


def bends(P, Q, near=None, theta_p=None, theta_q=None):
    """Same-named streets that run along one of P's axes in P and one of Q's axes in Q and meet within
    HINGE_NEAR px: [{x, y, n, fa, fb}] (fa / fb: the family in P / Q). near: boundary samples; a bend
    farther than 2 ADJ_D from all of them is ignored."""
    tp = math.degrees(P.theta if theta_p is None else theta_p)
    tq = math.degrees(Q.theta if theta_q is None else theta_q)
    rp, rq = _runs(P.streets, tp), _runs(Q.streets, tq)
    byq: dict = {}
    for r in rq:
        byq.setdefault(r[0], []).append(r)
    out = []
    for n, fa, a0, a1, _ in rp:
        for _, fb, b0, b1, _ in byq.get(n, ()):
            d, pa, pb = min((math.dist(x, y), x, y) for x in (a0, a1) for y in (b0, b1))
            if d > HINGE_NEAR:
                continue
            p = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)
            if near and min(math.dist(p, s) for s in near) > 2 * ADJ_D:
                continue
            if any(o["n"] == n and math.dist((o["x"], o["y"]), p) < RANSAC_TOL for o in out):
                continue
            out.append({"x": p[0], "y": p[1], "n": n, "fa": fa, "fb": fb})
    return out


def ransac(pts, tol=RANSAC_TOL, min_sep=150.0, seed=1):
    """The largest set of points within tol of one line (deterministic). -> (inliers, line, rms) or None."""
    if len(pts) < 2:
        return None
    pairs = [(i, j) for i in range(len(pts)) for j in range(i + 1, len(pts))]
    if len(pairs) > 3000:
        pairs = random.Random(seed).sample(pairs, 3000)
    best = None
    for i, j in pairs:
        a, b = pts[i], pts[j]
        if math.dist(a, b) < min_sep:
            continue
        l = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])))
        inl = [k for k, p in enumerate(pts) if _ldist(p, l) < tol]
        if not best or len(inl) > len(best):
            best = inl
    if not best:
        return None
    line, rms = fit_line([pts[k] for k in best])
    return best, line, rms


def seam_avenue(streets, line, t0, t1):
    """The named street (k <= 3) with the most length within AV_NEAR px of the line, within AV_DEG of its
    direction and inside its extent; it must cover AV_SHARE of the seam. -> (name, length, points) or None."""
    tally: dict = {}
    pts: dict = {}
    for st in streets or ():
        if st.get("t") or not st.get("n") or st.get("k", 9) > 3:
            continue
        p = _pairs(st["p"])
        for u, v in zip(p, p[1:]):
            L = math.dist(u, v)
            if L < 5:
                continue
            ang = math.degrees(math.atan2(v[1] - u[1], v[0] - u[0]))
            mid = ((u[0] + v[0]) / 2, (u[1] + v[1]) / 2)
            if abs(_ldiff(ang, line[2])) <= AV_DEG and _ldist(mid, line) < AV_NEAR and t0 - 200 <= _lpos(mid, line) <= t1 + 200:
                n = norm(st["n"])
                tally[n] = tally.get(n, 0.0) + L
                pts.setdefault(n, []).extend([u, v])
    if not tally:
        return None
    n = max(tally, key=tally.get)
    if tally[n] < AV_SHARE * (t1 - t0):
        return None
    return n, tally[n], pts[n]


def _samples(ring, step=SAMPLE):
    out = []
    n = len(ring)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        L = math.dist(a, b)
        k = max(1, int(L // step))
        for j in range(k):
            t = j / k
            out.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
    return out


def shared(P, Q, dmax=ADJ_D):
    """Boundary samples of the smaller polygon that lie within dmax of the other: (samples in ring order,
    median gap)."""
    small, big = (P, Q) if area(P.poly) <= area(Q.poly) else (Q, P)
    s = _samples(small.poly)
    hits = [(i, p, _ring_d(p, big.poly)) for i, p in enumerate(s)]
    near = [(i, p, (0.0 if _inside(p, big.poly) else d)) for i, p, d in hits if d <= dmax or _inside(p, big.poly)]
    if not near:
        return [], 0.0
    # ring order, starting after the largest index gap (so a run that wraps the ring start stays contiguous)
    idx = [i for i, _, _ in near]
    gaps = [((idx[(k + 1) % len(idx)] - idx[k]) % len(s), k) for k in range(len(idx))]
    start = (max(gaps)[1] + 1) % len(idx)
    near = near[start:] + near[:start]
    ds = sorted(d for _, _, d in near)
    return [p for _, p, _ in near], ds[len(ds) // 2]


def _tree(domains, adj):
    """BFS from the largest grid domain over adjacencies, longest shared boundary first: [(parent, child)]."""
    grid = [d for d in domains if d.kind == "grid"]
    if not grid:
        return [], None
    root = max(grid, key=lambda d: area(d.poly))
    placed = {root.id}
    order = []
    while True:
        cand = [(L, a, b) for (a, b), L in adj.items() if (a in placed) != (b in placed)]
        if not cand:
            break
        L, a, b = max(cand, key=lambda c: (c[0], -min(c[1], c[2])))
        p, c = (a, b) if a in placed else (b, a)
        order.append((p, c)); placed.add(c)
    return order, root.id


# ── S5: seams ───────────────────────────────────────────────────────────────
def _river_near(p, rivers, w=200.0):
    for rv in rivers or ():
        q = _pairs(rv["p"]) if isinstance(rv, dict) else rv
        if any(_segd(p, u, v) < w for u, v in zip(q, q[1:])):
            return True
    return False


def seams(domains, lines=None, avenues=None, rivers=None, sigma=1.0, cw=CW, ch=CH, aspect=None, majors=()):
    """Every seam between adjacent grid domains, oriented parent -> child along the layout tree. This also
    normalises each child's theta (within 45 deg of its parent's) and sets each child's roles (which family
    gets CW) from the seam-angle rule. With `lines` ({id: select output}) the hinge pairs are equalised."""
    doms = {d.id: d for d in domains}
    grid = [d for d in domains if d.kind == "grid" and d.poly]
    adj, sh = {}, {}
    for i, P in enumerate(grid):
        for Q in grid[i + 1:]:
            s, gap = shared(P, Q)
            if len(s) * SAMPLE >= 400:
                adj[(P.id, Q.id)] = len(s) * SAMPLE
                sh[(P.id, Q.id)] = sh[(Q.id, P.id)] = (s, gap)
    order, root = _tree(grid, adj)
    out = []
    for pid, cid in order:
        P, Q = doms[pid], doms[cid]
        tp = math.degrees(P.theta)
        raw, snap = tilt(tp, math.degrees(Q.theta))
        Q.theta = math.radians(tp + raw)                       # same lattice, the frame nearest the parent's
        samples, gap = sh[(pid, cid)]
        parts = []
        bl = bends(P, Q, samples)
        rs = ransac([(b["x"], b["y"]) for b in bl]) if len(bl) >= HINGE_MIN else None
        used = set()
        if rs and len(rs[0]) >= HINGE_MIN and len({bl[k]["n"] for k in rs[0]}) >= 3:
            inl, line, rms = rs
            fams = Counter((bl[k]["fa"], bl[k]["fb"]) for k in inl).most_common(1)[0][0]
            inl = [k for k in inl if (bl[k]["fa"], bl[k]["fb"]) == fams]
            pts = [(bl[k]["x"], bl[k]["y"]) for k in inl]
            ts = [_lpos(p, line) for p in pts]
            t0, t1 = min(ts), max(ts)
            # the seam reaches as far as the shared boundary does along the hinge line
            near = [p for p in samples if _ldist(p, line) < 2.5 * RANSAC_TOL + 0.5 * cw / max(sigma, 1e-9)]
            if near:
                t0, t1 = min(t0, min(_lpos(p, line) for p in near)), max(t1, max(_lpos(p, line) for p in near))
            av = seam_avenue((P.streets or []) + (Q.streets or []), line, t0, t1)
            if av:                        # the seam runs as far as its avenue does along the hinge line
                ta = [_lpos(p, line) for p in av[2] if _ldist(p, line) < AV_NEAR]
                if ta:
                    t0, t1 = min(t0, min(ta)), max(t1, max(ta))
            used = {i for i, p in enumerate(samples) if _ldist(p, line) < 2.5 * RANSAC_TOL + 0.5 * cw / max(sigma, 1e-9)}
            parts.append({"kind": "hinge", "line": line, "rms": rms, "t": (t0, t1),
                          "bends": [bl[k] for k in inl], "fa": fams[0], "fb": fams[1],
                          "names": sorted({bl[k]["n"] for k in inl}),
                          "avenue": av[0] if av else None, "avenue_len": av[1] if av else 0.0,
                          "anchor": av[2] if av else pts})
        # the rest of the shared boundary: tee / strip / water parts (contiguous runs, DP-split)
        run, runs_ = [], []
        for i, p in enumerate(samples):
            if i in used:
                if run:
                    runs_.append(run); run = []
            else:
                run.append(p)
        if run:
            runs_.append(run)
        for r in runs_:
            if len(r) * SAMPLE < 400:
                continue
            simp = _dp(r, 1.2 * 200)
            for a, b in zip(simp, simp[1:]):
                seg = [p for p in r if _segd(p, a, b) < 1.2 * 200]
                if len(seg) * SAMPLE < 400:
                    continue
                line, rms = fit_line(seg)
                ts = [_lpos(p, line) for p in seg]
                water = sum(_river_near(p, rivers) for p in seg) > len(seg) / 2
                kind = "water" if water else ("strip" if gap * sigma >= 0.6 * ch else "tee")
                parts.append({"kind": kind, "line": line, "rms": rms, "t": (min(ts), max(ts)), "anchor": seg,
                              "width": (gap if kind == "strip" else 0.0)})
        if not parts:
            continue
        # order the parts along the boundary
        parts.sort(key=lambda pt: min(range(len(samples)), key=lambda i: _ldist(samples[i], pt["line"]) + abs(
            _lpos(samples[i], pt["line"]) - pt["t"][0]) * 0.01))
        main = next((pt for pt in parts if pt["kind"] == "hinge"), None) or \
            max(parts, key=lambda pt: pt["t"][1] - pt["t"][0])
        for pt in parts:
            pt["phi_rel"] = _ldiff(pt["line"][2], tp)       # real angle relative to the parent's frame
        # the child's roles from the hinge part (relative frame: parent rows at 0, columns at 90)
        roles = getattr(Q, "roles", "vh") or "vh"
        hp = next((pt for pt in parts if pt["kind"] == "hinge"), None)
        if hp:
            proles = getattr(P, "roles", "vh") or "vh"
            asp = aspect or {}
            g_p = cw if (hp["fa"] == "v") == (proles[0] == "v") else block_ch(asp.get(P.id), cw, ch, proles)
            d_p = 0.0 if hp["fa"] == "h" else 90.0
            d_q = snap + (0.0 if hp["fb"] == "h" else 90.0)
            # the child's hinge family takes cw, or the spacing the real seam angle gives it on an even page (a
            # 45-degree seam off a parent family of block b continues as a child family of b*sqrt2: Kensington's long
            # blocks), kept within [ch, ASPECT_MAX*cw]; without the block-aspect rule, the child's real block shape
            chq = block_ch(asp.get(Q.id), cw, ch, "hv" if hp["fb"] == "v" else "vh")
            if aspect is not None:
                g0 = spacing_ratio(hp["phi_rel"], d_p, d_q) * g_p
                chq = float(max(ch, min(ASPECT_MAX * cw, round(g0 / 10.0) * 10.0)))
            sol = solve_phi(hp["phi_rel"], d_p, d_q, g_p, (cw, chq))
            Q.ch_page = None if sol["nominal"] == cw else sol["nominal"]
            hp["solve_rel"] = sol
            gets_cw = sol["nominal"] == cw
            roles = ("vh" if gets_cw else "hv") if hp["fb"] == "v" else ("hv" if gets_cw else "vh")
            Q.roles = roles
        sm = Seam(a=pid, b=cid, kind=main["kind"], real=[_end(main, 0), _end(main, 1)],
                  avenue=main.get("avenue"), phi=main["phi_rel"], segs=[], hinge=[],
                  ratio=main.get("solve_rel", {}).get("ratio", 1.0), err=main.get("solve_rel", {}).get("err", 0.0))
        sm.info = {"parts": parts, "tilt_raw": raw, "tilt": snap, "shared": len(samples) * SAMPLE, "gap": gap,
                   "root": root}
        out.append(sm)
    if lines:
        for sm in out:
            if sm.a in lines and sm.b in lines:
                equalise(sm, lines[sm.a], lines[sm.b])
    return out


def _end(part, k):
    mx, my, a = part["line"]
    t = part["t"][k]
    u = _unit(a)
    return (mx + u[0] * t, my + u[1] * t)


def must_names(seam_list, did):
    """Street names the line selection of domain `did` must keep: hinge streets and seam avenues."""
    out = set()
    for sm in seam_list:
        if did in (sm.a, sm.b):
            for pt in sm.info["parts"]:
                out.update(pt.get("names", ()))
                if pt.get("avenue"):
                    out.add(pt["avenue"])
    return out


# ── slot equalisation (design 2.5) ──────────────────────────────────────────
def _pairs_of(A, B, names):
    pos = {}
    for k, l in enumerate(A):
        if l.get("n") in names:
            pos.setdefault(l["n"], []).append(k)
    out = []
    for k2, l in enumerate(B):
        if l.get("n") in pos:
            out.append((pos[l["n"]][0], k2, l["n"]))
    out.sort()
    return out


def _monotone(pairs):
    """The longest chain of pairs whose child index moves the same way as the parent's (+1 or -1)."""
    best = []
    for sg in (1, -1):
        seq = [(k, sg * k2, n) for k, k2, n in pairs]
        n = len(seq)
        L = [1] * n; prv = [-1] * n
        for i in range(n):
            for j in range(i):
                if seq[j][0] < seq[i][0] and seq[j][1] < seq[i][1] and L[j] + 1 > L[i]:
                    L[i], prv[i] = L[j] + 1, j
        if n:
            i = max(range(n), key=lambda q: L[q]); ch = []
            while i >= 0:
                ch.append(pairs[i]); i = prv[i]
            if len(ch) > len(best):
                best = list(reversed(ch)); bsg = sg
    return (best, bsg) if best else ([], 1)


def equalise(seam, lines_a, lines_b):
    """Between consecutive hinge pairs the parent and the child must have the same number of lines in the
    hinge family: drop the child's least important optional lines, or insert unnamed child slots. Modifies
    lines_b in place; records seam.hinge = [(name, k, k2)] and returns the counts."""
    hp = next((pt for pt in seam.info["parts"] if pt["kind"] == "hinge"), None)
    st = {"dropped": 0, "inserted": 0, "mismatch": 0, "pairs": 0}
    if not hp:
        return st
    fa, fb = hp["fa"], hp["fb"]
    A, B = lines_a[fa], lines_b[fb]
    names = set(hp["names"])
    for _ in range(200):
        chain, sg = _monotone(_pairs_of(A, B, names))
        changed = False
        for (k1, j1, _), (k2, j2, _) in zip(chain, chain[1:]):
            need, have = k2 - k1, abs(j2 - j1)
            lo, hi = min(j1, j2), max(j1, j2)
            if have > need:
                cand = [j for j in range(lo + 1, hi) if not B[j].get("must") and B[j].get("n") not in names]
                if len(cand) < have - need:
                    continue
                j = min(cand, key=lambda q: (B[q].get("k", 9) <= 3, B[q].get("len", 0)))
                del B[j]; st["dropped"] += 1; changed = True
                break
            if have < need:
                gaps = [(B[j + 1]["pos"] - B[j]["pos"], j) for j in range(lo, hi)]
                _, j = max(gaps)
                a, b = B[j], B[j + 1]
                sp = [[min(x[0] for x in a["spans"] + b["spans"]), max(x[1] for x in a["spans"] + b["spans"])]]
                B.insert(j + 1, {"n": None, "pos": (a["pos"] + b["pos"]) / 2, "spans": sp, "major": False,
                                 "len": 0.0, "bridges": [], "k": 9, "must": False, "slot": True})
                st["inserted"] += 1; changed = True
                break
        if not changed:
            break
    chain, sg = _monotone(_pairs_of(A, B, names))
    for (k1, j1, _), (k2, j2, _) in zip(chain, chain[1:]):
        if k2 - k1 != abs(j2 - j1):
            st["mismatch"] += 1
    for i, l in enumerate(B):
        l["i"] = i
    seam.hinge = [(n, k, j) for k, j, n in chain]
    seam.info["hinge_sign"] = sg
    st["pairs"] = len(chain)
    seam.info["equalise"] = st
    return st


# ── S6: layout ──────────────────────────────────────────────────────────────
class DomainMapping:
    """Real px -> page px for one domain: its local lattice mapping, turned by a (deg) and moved by o."""

    def __init__(self, local, a=0.0, o=(0.0, 0.0)):
        self.loc, self.a, self.o = local, a, o

    def local(self, x, y):
        return self.loc(x, y)

    def page(self, lx, ly):
        p = _rot((lx, ly), self.a)
        return (p[0] + self.o[0], p[1] + self.o[1])

    def to_local(self, x, y):
        return _rot((x - self.o[0], y - self.o[1]), -self.a)

    def __call__(self, x, y):
        return self.page(*self.loc(x, y))

    def normal(self, fam):
        """Page unit normal of a family's lines (n . page = local coordinate + n . o)."""
        return _rot((1.0, 0.0) if fam == "v" else (0.0, 1.0), self.a)

    def dirn(self, fam):
        return _rot((0.0, 1.0) if fam == "v" else (1.0, 0.0), self.a)

    def tables(self):
        t = self.loc.tables()
        t.update(a=round(self.a, 6), o=[round(self.o[0], 3), round(self.o[1], 3)])
        return t


class Layout:
    """The result of layout(): maps[id] (DomainMapping), lines[id], rect[id] (local lattice rect),
    region[id] (child: convex page ring), seams (with page geometry in seam.segs / seam.info)."""

    def __init__(self):
        self.maps, self.lines, self.rect, self.region, self.subtract, self.seams = {}, {}, {}, {}, {}, []
        self.report = {}

    def clip(self, did, poly):
        """A convex page polygon (a cell, say) clipped to domain did's page region: a list of convex pieces."""
        pieces = [poly]
        own = self.region.get(did)
        if own:
            pieces = [_clip_convex(p, own) for p in pieces]
            pieces = [p for p in pieces if len(p) >= 3]
        for K in self.subtract.get(did, ()):
            nxt = []
            for p in pieces:
                nxt.extend(_minus_convex(p, K))
            pieces = nxt
        return [p for p in pieces if area(p) > 1e-6]

    def segment(self, did, p0, p1):
        """The parts of a page segment inside domain did's region: [(t0, t1)] in segment parameter."""
        own = self.region.get(did)
        iv = [(0.0, 1.0)]
        if own:
            r = _seg_interval(p0, p1, own)
            iv = [r] if r else []
        for K in self.subtract.get(did, ()):
            r = _seg_interval(p0, p1, K)
            if not r:
                continue
            nxt = []
            for a, b in iv:
                if r[1] <= a or r[0] >= b:
                    nxt.append((a, b)); continue
                if r[0] > a:
                    nxt.append((a, r[0]))
                if r[1] < b:
                    nxt.append((r[1], b))
            iv = nxt
        return [(a, b) for a, b in iv if b - a > 1e-9]


def _clip_convex(poly, convex):
    m = len(convex)
    sgn = 1.0 if sum(convex[i][0] * convex[(i + 1) % m][1] - convex[(i + 1) % m][0] * convex[i][1] for i in range(m)) > 0 else -1.0
    out = poly
    for i in range(m):
        a, b = convex[i], convex[(i + 1) % m]
        e = (b[0] - a[0], b[1] - a[1])
        nrm = (sgn * -e[1], sgn * e[0])
        out = clip_half(out, nrm, _dot(nrm, a), "ge")
        if len(out) < 3:
            return []
    return out


def _minus_convex(poly, K):
    """poly minus convex K: disjoint convex pieces."""
    m = len(K)
    sgn = 1.0 if sum(K[i][0] * K[(i + 1) % m][1] - K[(i + 1) % m][0] * K[i][1] for i in range(m)) > 0 else -1.0
    out, rest = [], poly
    for i in range(m):
        a, b = K[i], K[(i + 1) % m]
        e = (b[0] - a[0], b[1] - a[1])
        nrm = (sgn * -e[1], sgn * e[0])
        piece = clip_half(rest, nrm, _dot(nrm, a), "le")
        if len(piece) >= 3 and area(piece) > 1e-6:
            out.append(piece)
        rest = clip_half(rest, nrm, _dot(nrm, a), "ge")
        if len(rest) < 3:
            break
    return out


def _rect_ring(mp, rect):
    x0, y0, x1, y1 = rect
    return [mp.page(x0, y0), mp.page(x1, y0), mp.page(x1, y1), mp.page(x0, y1)]


def _fit_angle_page(pts):
    return fit_line(pts)[0][2] if len(pts) >= 2 else None


def _anchor_pts(part, step=100.0):
    t0, t1 = part["t"]
    n = max(2, int((t1 - t0) // step) + 1)
    mx, my, a = part["line"]
    u = _unit(a)
    return [(mx + u[0] * (t0 + (t1 - t0) * k / (n - 1)), my + u[1] * (t0 + (t1 - t0) * k / (n - 1))) for k in range(n)]


def layout(domains, seam_list, lines, pad=PAD, cw=CW, ch=CH, tol=R_TOL, natural=False):
    """Place every domain: the root at angle 0, each child by its seam with the parent (hinge: the hinge streets
    meet exactly on the seam; tee / strip / water: least squares on the seam samples and on same-named lines).
    Sets d.a, d.o, d.mapping, d.clip and seam.phi / segs / ratio / err / hinge; returns a Layout."""
    doms = {d.id: d for d in domains}
    lay = Layout(); lay.seams = seam_list
    root = seam_list[0].info["root"] if seam_list else max((d for d in domains if d.kind == "grid"), key=lambda d: area(d.poly)).id
    gs = {}
    for did, L in lines.items():
        gs[did] = {"v": L["gv"], "h": L["gh"]}

    def make(did, a, o):
        L = lines[did]
        mp = DomainMapping(local_mapping(L, gs[did]["v"], gs[did]["h"]), a, o)
        lay.maps[did] = mp; lay.lines[did] = L
        nx, ny = max(0, len(L["v"]) - 1), max(0, len(L["h"]) - 1)
        lay.rect[did] = [0.0, 0.0, nx * gs[did]["v"], ny * gs[did]["h"]]
        d = doms[did]; d.a, d.o, d.mapping, d.lines = a, o, mp, L
        return mp

    make(root, 0.0, (0.0, 0.0))
    for sm in seam_list:
        P, Q = doms[sm.a], doms[sm.b]
        mpP = lay.maps[sm.a]
        aQ = mpP.a + sm.info["tilt"]
        parts = sm.info["parts"]
        hp = next((pt for pt in parts if pt["kind"] == "hinge"), None)
        rep = {"kind": sm.kind}
        # page line of every part, in the parent's page frame
        for pt in parts:
            pts = [mpP(*p) for p in (pt["anchor"] if pt["kind"] == "hinge" else _anchor_pts(pt))]
            phi_real = _fit_angle_page([mpP(b["x"], b["y"]) for b in pt["bends"]] if pt["kind"] == "hinge" else pts)
            ref = pt["phi_rel"] + mpP.a
            phi_real = ref if phi_real is None else ref + _ldiff(phi_real, ref)
            if pt is hp:
                fa, fb = hp["fa"], hp["fb"]
                d_p = mpP.a + (0.0 if fa == "h" else 90.0)
                d_q = aQ + (0.0 if fb == "h" else 90.0)
                g_p = gs[sm.a][fa]
                nominal = lines[sm.b]["gv" if fb == "v" else "gh"]
                noms = (nominal,)
                if natural:                    # an even page: the child family takes the real seam's spacing
                    g0 = spacing_ratio(phi_real, d_p, d_q) * g_p
                    noms = (nominal, max(ch, min(ASPECT_MAX * cw, g0)))
                sol = solve_phi(phi_real, d_p, d_q, g_p, noms, tol)
                phi = sol["phi"]
                gs[sm.b][fb] = sol["g"]
                pt["solve"] = sol
                rep.update(phi_real=phi_real, phi=phi, fold=sol["fold"], t=sol["t"], r=sol["r"],
                           block_ratio=sol["ratio"], err=sol["err"], phi_true=ref,
                           err_true=abs(_ldiff(phi, ref)))
            else:
                phi = _snap_tee(phi_real, mpP.a, aQ)
            phi = ref + _ldiff(phi, ref)                     # keep the real orientation (for the sides)
            u = _unit(phi); n = (-u[1], u[0])
            c = sorted(_dot(n, p) for p in pts)[len(pts) // 2]
            pt["page"] = {"phi": phi, "u": u, "n": n, "c": c, "phi_real": phi_real}
        # the child's offsets: least squares on seam samples, then the hinge family exactly through Q_k
        mpQ = make(sm.b, aQ, (0.0, 0.0))
        mainp = _main_part(sm)
        anch = _anchor_pts(mainp) if mainp else []
        cv = ch_ = None
        if any(pt["kind"] == "water" for pt in parts):
            cv, ch_ = _named_offsets(lay, sm.a, sm.b)
            anch = anch or [p for pt in parts for p in _anchor_pts(pt)]
        offs = {}
        for fam in ("v", "h"):
            nq = mpQ.normal(fam)
            vals = sorted(_dot(nq, mpP(*p)) - (mpQ.local(*p)[0] if fam == "v" else mpQ.local(*p)[1]) for p in anch)
            offs[fam] = vals[len(vals) // 2] if vals else 0.0
        if cv is not None:
            offs["v"] = cv
        if ch_ is not None:
            offs["h"] = ch_
        if hp and sm.hinge:
            hpg = hp["page"]
            fa, fb = hp["fa"], hp["fb"]
            nP, nQ = mpP.normal(fa), mpQ.normal(fb)
            cP = _dot(nP, mpP.o)
            gq = gs[sm.b][fb]
            res, Qk = [], []
            for name, k, k2 in sm.hinge:
                q = _isect(nP, cP + k * gs[sm.a][fa], hpg["n"], hpg["c"])
                Qk.append((name, k, k2, q))
                res.append(_dot(nQ, q) - k2 * gq)
            offs[fb] = sum(res) / len(res)
            resid = max(abs(_dot(nQ, q) - (offs[fb] + k2 * gq)) for _, _, k2, q in Qk)
            rep["hinge_resid_px"] = resid
            sm.hinge = [{"n": n_, "a": k, "b": k2, "fa": fa, "fb": fb, "at": q} for n_, k, k2, q in Qk]
        nv, nh = mpQ.normal("v"), mpQ.normal("h")
        o = (offs["v"] * nv[0] + offs["h"] * nh[0], offs["v"] * nv[1] + offs["h"] * nh[1])
        make(sm.b, aQ, o)
        sm.phi = (hp or parts[0])["page"]["phi"]
        if hp:
            sm.ratio, sm.err = hp["solve"]["ratio"], hp["solve"]["err"]
        rep["tilt"] = sm.info["tilt"]; rep["roles"] = getattr(Q, "roles", "vh")
        rep["g_child"] = dict(gs[sm.b])
        lay.report[(sm.a, sm.b)] = rep
    # a grid domain no seam reaches (an island of grid in a free area): turned by its own tilt against the
    # root, placed so its outline lands where the root's mapping puts it
    for did in lines:
        if did in lay.maps or did not in doms:
            continue
        d, mpR = doms[did], lay.maps[root]
        raw, snap = tilt(math.degrees(doms[root].theta), math.degrees(d.theta))
        if abs(math.degrees(d.theta) - (math.degrees(doms[root].theta) + raw)) > 1e-6:
            pass                                   # theta is used as selected (lines were built in it)
        mpQ = make(did, mpR.a + _ldiff(math.degrees(lines[did]["theta"]), math.degrees(doms[root].theta)), (0.0, 0.0))
        anch = _samples(d.poly, 100.0) if d.poly else []
        offs = {}
        for fam in ("v", "h"):
            nq = mpQ.normal(fam)
            vals = sorted(_dot(nq, mpR(*p)) - (mpQ.local(*p)[0] if fam == "v" else mpQ.local(*p)[1]) for p in anch)
            offs[fam] = vals[len(vals) // 2] if vals else 0.0
        nv, nh = mpQ.normal("v"), mpQ.normal("h")
        make(did, mpQ.a, (offs["v"] * nv[0] + offs["h"] * nh[0], offs["v"] * nv[1] + offs["h"] * nh[1]))
        lay.report[(None, did)] = {"kind": "unconnected", "tilt": mpQ.a}
    # page segments of every part (corners where consecutive parts meet), regions
    for sm in seam_list:
        mpP = lay.maps[sm.a]
        parts = sm.info["parts"]
        segs = []
        for pt in parts:
            pg = pt["page"]
            ends = [mpP(*_end(pt, 0)), mpP(*_end(pt, 1))]
            t0, t1 = sorted(_dot(pg["u"], e) for e in ends)
            base = (pg["n"][0] * pg["c"], pg["n"][1] * pg["c"])
            segs.append([(base[0] + pg["u"][0] * t0, base[1] + pg["u"][1] * t0),
                         (base[0] + pg["u"][0] * t1, base[1] + pg["u"][1] * t1)])
        sm.segs = [(s[0][0], s[0][1], s[1][0], s[1][1]) for s in segs]
    _regions(lay, doms, seam_list, root)
    # global shift: the smallest page coordinate of any region becomes pad
    rings = [r for did in lay.maps for r in [lay.region.get(did) or _rect_ring(lay.maps[did], lay.rect[did])]]
    mx = min(p[0] for r in rings for p in r); my = min(p[1] for r in rings for p in r)
    dx, dy = pad - mx, pad - my
    _shift(lay, doms, seam_list, dx, dy)
    for did in lay.maps:
        doms[did].clip = lay.region.get(did) or _rect_ring(lay.maps[did], lay.rect[did])
    return lay


def _named_offsets(lay, pid, cid):
    """Water seams: same-named lines in the same-angle family must face each other across the band."""
    mpP, mpQ = lay.maps[pid], lay.maps[cid]
    LP, LQ = lay.lines[pid], lay.lines[cid]
    out = []
    for fam in ("v", "h"):
        if abs(_ldiff(mpP.a, mpQ.a)) > 1e-6:
            out.append(None); continue
        g = mpP.loc.gv if fam == "v" else mpP.loc.gh
        gq = mpQ.loc.gv if fam == "v" else mpQ.loc.gh
        nq = mpQ.normal(fam)
        byn = {l["n"]: i for i, l in enumerate(LP[fam]) if l.get("n")}
        vals = sorted(_dot(nq, mpP.o) + byn[l["n"]] * g - i * gq for i, l in enumerate(LQ[fam]) if l.get("n") in byn)
        out.append(vals[len(vals) // 2] if vals else None)
    return out


def _snap_tee(phi_real, a_p, a_q):
    cands = [a_p + k * 45.0 for k in range(4)] + [a_q + k * 45.0 for k in range(4)]
    best = min(cands, key=lambda c: abs(_ldiff(c, phi_real)))
    if abs(_ldiff(best, phi_real)) <= TEE_SNAP:
        return _wrap(best)
    return round(phi_real * 2) / 2


CHAIN_MIN_DEG = 20.0    # a neighbouring part joins the clipping chain only when it turns at least this much
CHAIN_EXT = 6.0         # blocks: a lattice grows this far to reach its chain's corner (3 for a one-part seam)
CHAIN_GAP = 3.0         # blocks: ... and when its corner with the chain lies this close to both parts' ends


def _corner(pa, pb):
    """The page point where two parts' page lines meet (None when they are nearly parallel)."""
    A, B = pa["page"], pb["page"]
    if abs(_ldiff(A["phi"], B["phi"])) < CHAIN_MIN_DEG:
        return None
    return _isect(A["n"], A["c"], B["n"], B["c"])


def clip_chain(sm, lay=None, cpg=None, blk=CW):
    """The parts of a seam that clip, in boundary order: the main part (the hinge, else the longest tee/strip) and
    each tee/strip part right beside it that turns off it at a convex corner of the child's region (design 2.6:
    the seam is a chain of segments; the corner where they meet is where the real boundary turns, as Baltimore Ave
    turns down Woodland Ave's side at the 40th Street junction). -> (part indices, {(i, j): corner page point})."""
    parts = sm.info["parts"]
    main = _main_part(sm)
    if main is None or main["kind"] == "water":
        return [], {}
    km = parts.index(main)
    chain, corners = [km], {}
    if cpg is None or "page" not in main:
        return chain, corners

    def side(pt, p):
        pg = pt["page"]
        return _dot(pg["n"], p) - pg["c"]
    for step in (-1, 1):
        k = km + step
        if not (0 <= k < len(parts)):
            continue
        nb = parts[k]
        if nb["kind"] not in ("tee", "strip") or "page" not in nb or k >= len(sm.segs) or km >= len(sm.segs):
            continue
        q = _corner(main, nb)
        if q is None:
            continue
        sa, sb = sm.segs[km], sm.segs[k]
        da = min(math.dist(q, sa[:2]), math.dist(q, sa[2:]))
        db = min(math.dist(q, sb[:2]), math.dist(q, sb[2:]))
        if da > CHAIN_GAP * blk or db > CHAIN_GAP * blk:
            continue
        # convex for the child: the child lies on its side of both lines, and neither part's far end is cut by the other
        fa = max((sa[:2], sa[2:]), key=lambda e: math.dist(e, q))
        fb = max((sb[:2], sb[2:]), key=lambda e: math.dist(e, q))
        sm_, sn_ = side(main, cpg), side(nb, cpg)
        if sm_ == 0 or sn_ == 0 or side(nb, fa) * sn_ < 0 or side(main, fb) * sm_ < 0:
            continue
        # the corner never cuts a hinge street off: every kink lies on the child's side of the turning part
        if any(isinstance(h, dict) and side(nb, h["at"]) * sn_ < -1.0 for h in sm.hinge):
            continue
        chain = [k] + chain if step < 0 else chain + [k]
        corners[tuple(sorted((km, k)))] = q
    return chain, corners


def _regions(lay, doms, seam_list, root):
    """Child region: its lattice rect, extended EXT blocks toward the seams it faces, cut by its side of every
    clipping part of the seam (the chain: the main part and its convex neighbours, meeting at their corners) and by
    the perpendiculars at the chain's two outer ends. Parent: minus each child's region."""
    for sm in seam_list:
        cid = sm.b
        mpQ, mpP = lay.maps[cid], lay.maps[sm.a]
        main = _main_part(sm)
        if not main or main["kind"] == "water":
            sm.info["clip"], sm.info["corners"] = [], {}
            continue
        # which side of the seam the child is on: its own centre, mapped by the parent
        cq = centroid(doms[cid].poly)
        cpg = mpP(*cq)
        blk = max(mpP.loc.gv, mpP.loc.gh)
        chain, corners = clip_chain(sm, lay, cpg, blk)
        ext = _extend(lay, cid, sm, cap=CHAIN_EXT if len(chain) > 1 else 3.0, segs=[sm.segs[k] for k in chain])
        _extend(lay, sm.a, sm, cap=CHAIN_EXT if len(chain) > 1 else 3.0, segs=[sm.segs[k] for k in chain])
        allp = sm.info["parts"]
        # the corners become the parts' shared ends
        for (i, j), q in corners.items():
            for k in (i, j):
                x0, y0, x1, y1 = sm.segs[k]
                if math.dist(q, (x0, y0)) <= math.dist(q, (x1, y1)):
                    sm.segs[k] = (q[0], q[1], x1, y1)
                else:
                    sm.segs[k] = (x0, y0, q[0], q[1])
        sm.info["clip"], sm.info["corners"] = chain, {"%d-%d" % k: q for k, q in corners.items()}
        big = 1e7
        S = [(-big, -big), (big, -big), (big, big), (-big, big)]
        Ssub = list(S)
        for k in chain:
            pt = allp[k]
            pg = pt["page"]
            sgn = _dot(pg["n"], cpg) - pg["c"]
            w = 0.0 if pt["kind"] != "strip" else pt.get("width", 0.0) * 0.5 * lay.lines[sm.a].get("sigma", 1.0)
            if sgn >= 0:
                S = clip_half(S, pg["n"], pg["c"] + w, "ge"); Ssub = clip_half(Ssub, pg["n"], pg["c"] - w, "ge")
            else:
                S = clip_half(S, pg["n"], pg["c"] - w, "le"); Ssub = clip_half(Ssub, pg["n"], pg["c"] + w, "le")
        # the perpendiculars at the chain's outer ends (a single part: at both of its ends)
        segs = [((sm.segs[k][0], sm.segs[k][1]), (sm.segs[k][2], sm.segs[k][3])) for k in chain]
        if len(segs) == 1:
            a, b = segs[0]
            caps = [(a, b), (b, a)]
        else:
            caps = []
            for k_, nb_ in ((0, 1), (len(segs) - 1, len(segs) - 2)):
                a, b = segs[k_]
                o = max((a, b), key=lambda q: min(math.dist(q, segs[nb_][0]), math.dist(q, segs[nb_][1])))
                caps.append((o, b if o == a else a))
        for o, inner in caps:
            u = (inner[0] - o[0], inner[1] - o[1]); L = math.hypot(*u) or 1.0; u = (u[0] / L, u[1] / L)
            S = clip_half(S, u, _dot(u, o), "ge"); Ssub = clip_half(Ssub, u, _dot(u, o), "ge")
        ring = _clip_convex(_rect_ring(mpQ, ext), S)
        lay.region[cid] = ring
        lay.rect[cid] = ext
        lay.subtract.setdefault(sm.a, []).append(Ssub)


def _main_part(sm):
    """The part of a seam that clips: the hinge part, else the longest tee/strip part (the other parts are
    recorded in seam.info for the report; multi-part clipping is not done yet)."""
    ps = sm.info["parts"]
    hp = next((pt for pt in ps if pt["kind"] == "hinge"), None)
    if hp:
        return hp
    ps = [pt for pt in ps if pt["kind"] != "water"]
    return max(ps, key=lambda pt: pt["t"][1] - pt["t"][0]) if ps else None


def _extend(lay, did, sm, cap=3.0, segs=None):
    """Grow domain did's lattice rect toward a seam it does not reach (at most `cap` blocks a side), so every
    line that meets the seam really reaches it (the extra lines are unnamed graph-paper slots)."""
    mp = lay.maps[did]
    x0, y0, x1, y1 = lay.rect[did]
    gv, gh = mp.loc.gv, mp.loc.gh
    main = _main_part(sm)
    if not main:
        return lay.rect[did]
    k = sm.info["parts"].index(main)
    sg = segs if segs else sm.segs[k:k + 1]
    pts = [mp.to_local(s_[0], s_[1]) for s_ in sg] + [mp.to_local(s_[2], s_[3]) for s_ in sg]
    if not pts:
        return lay.rect[did]
    lx = [p[0] for p in pts]; ly = [p[1] for p in pts]
    if min(lx) < x0 and max(lx) > x0 - cap * gv:
        x0 = max(x0 - cap * gv, math.floor(min(lx) / gv) * gv)
    if max(lx) > x1 and min(lx) < x1 + cap * gv:
        x1 = min(x1 + cap * gv, math.ceil(max(lx) / gv) * gv)
    if min(ly) < y0 and max(ly) > y0 - cap * gh:
        y0 = max(y0 - cap * gh, math.floor(min(ly) / gh) * gh)
    if max(ly) > y1 and min(ly) < y1 + cap * gh:
        y1 = min(y1 + cap * gh, math.ceil(max(ly) / gh) * gh)
    lay.rect[did] = [x0, y0, x1, y1]
    return lay.rect[did]


def _shift(lay, doms, seam_list, dx, dy):
    for did, mp in lay.maps.items():
        mp.o = (mp.o[0] + dx, mp.o[1] + dy)
        doms[did].o = mp.o
    mv = lambda p: (p[0] + dx, p[1] + dy)
    for did in list(lay.region):
        lay.region[did] = [mv(p) for p in lay.region[did]]
    for did in list(lay.subtract):
        lay.subtract[did] = [[mv(p) for p in K] for K in lay.subtract[did]]
    for sm in seam_list:
        sm.segs = [(a + dx, b + dy, c + dx, d + dy) for a, b, c, d in sm.segs]
        for pt in sm.info["parts"]:
            pg = pt.get("page")
            if pg:
                pg["c"] += _dot(pg["n"], (dx, dy))
        for h in sm.hinge:
            if isinstance(h, dict):
                h["at"] = mv(h["at"])


# ── line ends on a seam ─────────────────────────────────────────────────────
def t_join(p_in, p_end, u_s, lead=LEAD):
    """A line from p_in ending on a seam at p_end (seam direction u_s): it turns into the seam with a short lead
    toward the side that gives the smaller turn. -> [p_in, p_end, p_lead]"""
    d = (p_end[0] - p_in[0], p_end[1] - p_in[1])
    s = 1.0 if _dot(u_s, d) >= 0 else -1.0
    return [p_in, p_end, (p_end[0] + s * lead * u_s[0], p_end[1] + s * lead * u_s[1])]


def _on_seam(lay, did, p, tol=1.0):
    for sm in lay.seams:
        if did not in (sm.a, sm.b):
            continue
        for k, pt in enumerate(sm.info["parts"]):
            if "page" not in pt or k >= len(sm.segs):
                continue
            s = sm.segs[k]
            if _segd(p, (s[0], s[1]), (s[2], s[3])) <= tol + (pt.get("width", 0.0) * 0.5 if pt["kind"] == "strip" else 0):
                return sm, pt
    return None, None


def paths(lay, did, lead=LEAD):
    """Every lattice line of domain did as complete graph paper inside its page region: [{n, fam, i, p, ends}]
    where ends[k] is "hinge", "tee" or None for the two ends. Hinge ends stop exactly at the shared seam point
    (the partner line starts there); tee ends carry the LEAD along the seam."""
    mp, L = lay.maps[did], lay.lines[did]
    x0, y0, x1, y1 = lay.rect[did]
    gv, gh = mp.loc.gv, mp.loc.gh
    hset = {}
    for sm in lay.seams:
        for h in sm.hinge:
            if isinstance(h, dict):
                if sm.a == did:
                    hset[(h["fa"], h["a"])] = h["at"]
                if sm.b == did:
                    hset[(h["fb"], h["b"])] = h["at"]
    out = []
    for fam in ("v", "h"):
        g = gv if fam == "v" else gh
        lo, hi = (x0, x1) if fam == "v" else (y0, y1)
        names = {l["i"] if "i" in l else k: l.get("n") for k, l in enumerate(L[fam])}
        i0, i1 = int(math.ceil(lo / g - 1e-9)), int(math.floor(hi / g + 1e-9))
        for i in range(i0, i1 + 1):
            if fam == "v":
                a, b = mp.page(i * g, y0), mp.page(i * g, y1)
            else:
                a, b = mp.page(x0, i * g), mp.page(x1, i * g)
            for t0, t1 in lay.segment(did, a, b):
                p0 = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
                p1 = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
                ends, lead_pt = [None, None], [None, None]
                for e, (q, other) in enumerate(((p0, p1), (p1, p0))):
                    sm, pt = _on_seam(lay, did, q)
                    if not sm:
                        continue
                    hq = hset.get((fam, i))
                    if hq and math.dist(hq, q) < 2.0:
                        ends[e] = "hinge"
                        continue
                    ends[e] = "tee"
                    lead_pt[e] = t_join(other, q, pt["page"]["u"], lead)[2]
                pts = ([lead_pt[0]] if lead_pt[0] else []) + [p0, p1] + ([lead_pt[1]] if lead_pt[1] else [])
                out.append({"n": names.get(i), "fam": fam, "i": i, "p": pts, "ends": ends})
    return out


# ── S4-S6 in order ──────────────────────────────────────────────────────────
def plan(domains, avenues=None, majors=(), sigma=None, rivers=None, cw=CW, ch=CH, tol=R_TOL, aspect=True):
    """seams (roles, frames) -> per-domain line selection (keeping hinge streets and seam avenues) ->
    slot equalisation -> layout. -> (seams, lines, Layout)."""
    grid = [d for d in domains if d.kind == "grid" and d.poly]
    # every domain's page block takes its real block's shape (a row is one real block, city_lines.block_ch)
    asp = {d.id: (block_aspect(d, majors) if aspect else None) for d in grid}
    if sigma is None:
        root = max(grid, key=lambda d: area(d.poly))
        sigma = city_scale(root, majors, cw, ch=block_ch(asp[root.id], cw, ch, getattr(root, "roles", "vh") or "vh"))
    for d in grid:
        d.ch_page = None
    sl = seams(grid, None, avenues, rivers, sigma, cw, ch, aspect=asp if aspect else None, majors=majors)
    lines = {}
    for d in grid:
        chd = getattr(d, "ch_page", None) or block_ch(asp[d.id], cw, ch, getattr(d, "roles", "vh") or "vh")
        lines[d.id] = select_lines(d, avenues, majors, sigma, must_names(sl, d.id), cw, chd)
    for sm in sl:
        equalise(sm, lines[sm.a], lines[sm.b])
    lay = layout(grid, sl, lines, cw=cw, ch=ch, tol=tol, natural=bool(aspect))
    lay.sigma = sigma
    return sl, lines, lay


# ── quality numbers (for R10 / the report) ──────────────────────────────────
def _unturn(L, tx, ty):
    th = L["theta"]; cx, cy = L["center"]
    c, s = math.cos(th), math.sin(th); x, y = tx - cx, ty - cy
    return (x * c - y * s + cx, x * s + y * c + cy)


def crossings(lay, did, tol=60.0):
    """Real crossings of the domain's named lines (both spans cover the point): [(real point, page point)]."""
    L, mp, out = lay.lines[did], lay.maps[did], []
    for v in L["v"]:
        if v.get("slot") or not v.get("n"):
            continue
        for h in L["h"]:
            if h.get("slot") or not h.get("n"):
                continue
            if any(a - tol <= h["pos"] <= b + tol for a, b in v["spans"]) and \
               any(a - tol <= v["pos"] <= b + tol for a, b in h["spans"]):
                r = _unturn(L, v["pos"], h["pos"])
                out.append((r, mp(*r)))
    return out


def _similarity(pairs):
    z = [complex(*r) for r, _ in pairs]; w = [complex(*p) for _, p in pairs]
    zm, wm = sum(z) / len(z), sum(w) / len(w)
    a = sum((wi - wm) * (zi - zm).conjugate() for zi, wi in zip(z, w)) / max(1e-9, sum(abs(zi - zm) ** 2 for zi in z))
    return lambda p: a * (complex(*p) - zm) + wm


def _dstats(res, block):
    r = sorted(x / block for x in res)
    if not r:
        return None
    return {"n": len(r), "median": round(r[len(r) // 2], 2), "p90": round(r[int(0.9 * (len(r) - 1))], 2),
            "max": round(r[-1], 2)}


def domain_quality(lay, did, block=CW):
    """Displacement of the domain's real crossings from the best similarity (scale, turn, shift) of the real map
    onto its page, in blocks: how far the even lattice moves real places."""
    pr = crossings(lay, did)
    if len(pr) < 4:
        return None
    S = _similarity(pr)
    return _dstats([abs(S(r) - complex(*p)) for r, p in pr], block)


def seam_quality(lay, sm, dist=1500.0, block=CW):
    """For a hinge seam: displacement of both sides' crossings within `dist` real px of the seam and of the kink
    points from one best similarity (blocks), the order of the hinge streets along the seam (inversions against
    the real order), the drawn angle against the real one and the child's block-width ratio."""
    hp = next((pt for pt in sm.info["parts"] if pt["kind"] == "hinge"), None)
    rep = dict(lay.report.get((sm.a, sm.b), {}))
    if not hp or not sm.hinge:
        return {"kind": sm.kind, "report": rep}
    line, (t0, t1) = hp["line"], hp["t"]
    near = [(r, p) for did in (sm.a, sm.b) for r, p in crossings(lay, did)
            if _ldist(r, line) < dist and t0 - dist < _lpos(r, line) < t1 + dist]
    bend = {}
    for b in hp["bends"]:
        bend.setdefault(b["n"], (b["x"], b["y"]))
    hpairs = [(bend[h["n"]], h["at"]) for h in sm.hinge if h["n"] in bend]
    S = _similarity(near + hpairs)
    real = [h["n"] for h in sorted(sm.hinge, key=lambda h: _lpos(bend.get(h["n"], (0, 0)), line))]
    u = hp["page"]["u"]
    page = [h["n"] for h in sorted(sm.hinge, key=lambda h: _dot(u, h["at"]))]
    if page and real and page.index(real[0]) > page.index(real[-1]):
        page.reverse()
    inv = sum(1 for i in range(len(real)) for j in range(i + 1, len(real)) if page.index(real[i]) > page.index(real[j]))
    return {"kind": sm.kind, "avenue": sm.avenue, "pairs": len(sm.hinge), "names": [h["n"] for h in sm.hinge],
            "order_inversions": inv, "near_seam": _dstats([abs(S(r) - complex(*p)) for r, p in near], block),
            "kinks": _dstats([abs(S(r) - complex(*p)) for r, p in hpairs], block),
            "phi": sm.phi, "phi_true": rep.get("phi_true"), "err_true": rep.get("err_true"),
            "block_ratio": sm.ratio, "t": rep.get("t"), "tilt": sm.info.get("tilt"), "report": rep}
