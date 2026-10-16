"""City engine v2, step S4: the lattice lines of ONE domain (design section 4.1).

`palace_grid._lines` chose the columns and rows of the whole city at once, so a street in one
neighbourhood made a column slot in every other one (the phantom lines). Here the same grouping
rules run on a domain's OWN streets only, in the domain's own turned frame, and then a
spacing-targeted selection keeps, per family, the lines that make the real blocks about
`CW/sigma x CH/sigma` everywhere ("differences in real block size show up as more or fewer lines").

Pure functions, no global state:

    candidates(streets, theta, center, majors=(), must=())      -> {"v": [line], "h": [line]}
    select(domain, avenues=None, majors=(), sigma=1.0, must=(), cw=CW, ch=CH, theta=None, center=None)
                                                                -> {"v", "h", "theta", "center", "gv", "gh", "stats"}
    scale(domain, majors=(), cw=CW, theta=None)                  -> sigma (page px per real px)
    mapping(lines, gv, gh)                                       -> palace_grid.Mapping (local frame, lines at i*gv / j*gh)

A line is the dict `_lines` makes: {"n", "pos", "spans", "major", "len", "bridges"} plus "k" (best class),
"must" (never dropped) and, after selection, "i" (its index in the family). Positions and spans are in the
domain's turned frame (real px turned by -theta about `center`), exactly what palace_grid.Mapping expects.
"""
from __future__ import annotations

import math

from .palace_grid import CW, CH, SNAP_DEG, _dp, _pairs, norm, numbered, Mapping

MIN_LEN = 380.0          # px of street before a line counts (palace_grid's rule)
MIN_LEN_MINOR = 700.0    # a residential (k = 4) street must be about half a kilometre long
GROUP_GAP = 700.0        # one name used twice in a city: pieces farther apart than this are two lines
SAME_LINE = 22.0         # two lines this close are one (a divided road)
MIN_GAP = 0.35           # never keep an optional line closer than this many target gaps to its neighbour
# what skipping an optional line costs, by street class (multiplied by min(1, length / (6 target gaps)))
SKIP_COST = {0: 4.0, 1: 4.0, 2: 1.0, 3: 0.5, 4: 0.15}
SKIP_COST_DEFAULT = 0.05


def _turner(theta, center):
    cx, cy = center
    c, s = math.cos(-theta), math.sin(-theta)

    def turn(x, y):
        x, y = x - cx, y - cy
        return (x * c - y * s + cx, x * s + y * c + cy)
    return turn


def centroid(poly):
    """Area centroid of a ring [(x, y), ...] (the vertex mean for a degenerate ring)."""
    if not poly:
        return (0.0, 0.0)
    a = cx = cy = 0.0
    n = len(poly)
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        f = x0 * y1 - x1 * y0
        a += f; cx += (x0 + x1) * f; cy += (y0 + y1) * f
    if abs(a) < 1e-9:
        return (sum(p[0] for p in poly) / n, sum(p[1] for p in poly) / n)
    return (cx / (3 * a), cy / (3 * a))


def candidates(streets, theta, center, majors=(), must=()):
    """Every street of the domain that could be a column ("v") or a row ("h") in the frame turned by theta.
    Same grouping, span and merge rules as palace_grid._lines, but no city-specific fill region: a
    residential street (k = 4) is a candidate if it is MIN_LEN_MINOR long; the selection decides."""
    turn = _turner(theta, center)
    majors_n = {norm(x) for x in majors}
    must_n = {norm(x) for x in must}
    segs = {"v": {}, "h": {}}
    dirlen: dict = {}
    kbest: dict = {}
    for st in streets or ():
        if st.get("t") or not st.get("n"):
            continue
        k = st.get("k", 9)
        if k == 0 and norm(st["n"]) not in majors_n and norm(st["n"]) not in must_n:
            continue                    # a motorway is no grid line (Chicago's Kennedy Expressway), unless the brief says so
        if k > 4:
            continue
        n = norm(st["n"])
        kbest[n] = min(kbest.get(n, 9), k)
        pts = _dp([turn(x, y) for x, y in _pairs(st["p"])], 10)
        for a, b in zip(pts, pts[1:]):
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if L < 4:
                continue
            ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180
            kd = "h" if (ang < SNAP_DEG or ang > 180 - SNAP_DEG) else "v" if abs(ang - 90) < SNAP_DEG else "d"
            t3 = dirlen.setdefault(n, {"h": 0.0, "v": 0.0, "d": 0.0}); t3[kd] += L
            if kd in ("v", "h"):
                segs[kd].setdefault(n, []).append((a, b, L, bool(st.get("b"))))
    out = {}
    for o in ("v", "h"):
        lines = []
        for n, ss in segs[o].items():
            t3 = dirlen.get(n) or {}
            if t3.get(o, 0) < 0.6 * sum(t3.values()):
                continue
            imp = n in majors_n or n in must_n
            items = sorted(((a[0] + b[0]) / 2 if o == "v" else (a[1] + b[1]) / 2, a, b, L, br) for a, b, L, br in ss)
            groups, cur = [], [items[0]]
            for it in items[1:]:
                if it[0] - cur[-1][0] > GROUP_GAP:
                    groups.append(cur); cur = []
                cur.append(it)
            groups.append(cur)
            k = kbest.get(n, 9)
            for g in groups:
                tot = sum(it[3] for it in g)
                need = MIN_LEN if (k <= 3 or numbered(n)) else MIN_LEN_MINOR
                if tot < need and not imp:
                    continue
                pos = sum(it[0] * it[3] for it in g) / tot
                iv = sorted(tuple(sorted((it[1][1], it[2][1]) if o == "v" else (it[1][0], it[2][0]))) + (it[4],) for it in g)
                spans, bridges = [], []
                lo, hi = iv[0][0], iv[0][1]
                for a0, a1, br in iv:
                    if br:
                        bridges.append((a0, a1))
                    if a0 <= hi + 90:
                        hi = max(hi, a1)
                    else:
                        spans.append([lo, hi]); lo, hi = a0, a1
                spans.append([lo, hi])
                lines.append({"n": n, "pos": pos, "spans": spans, "major": n in majors_n, "len": tot,
                              "bridges": bridges, "k": k,
                              "must": bool(imp or numbered(n) or k <= 1)})
        lines.sort(key=lambda l: l["pos"])
        kept = []
        for l in lines:
            if kept and l["pos"] - kept[-1]["pos"] < SAME_LINE:
                q = kept[-1]
                keep, drop = (q, l) if (q["must"], q["major"], q["len"]) >= (l["must"], l["major"], l["len"]) else (l, q)
                keep["spans"] = sorted(keep["spans"] + drop["spans"])
                keep["bridges"] += drop["bridges"]
                keep["must"] = keep["must"] or drop["must"]
                kept[-1] = keep
                continue
            kept.append(l)
        out[o] = kept
    return out


def _skip_cost(l, g):
    w = SKIP_COST.get(l.get("k", 9), SKIP_COST_DEFAULT)
    return w * min(1.0, l.get("len", 0.0) / (6.0 * g))


def thin(lines, g):
    """The spacing-targeted DP over one family (sorted by pos). Minimises sum((gap/g - 1)^2) over the kept
    gaps plus the skip cost of every dropped optional line; "must" lines are always kept; an optional
    line is never kept closer than MIN_GAP*g to a kept neighbour. Returns the kept lines (same dicts)."""
    n = len(lines)
    if n <= 1 or g <= 0:
        return list(lines)
    pos = [l["pos"] for l in lines]
    must = [bool(l.get("must")) for l in lines]
    sc = [0.0 if must[i] else _skip_cost(lines[i], g) for i in range(n)]
    pre = [0.0]
    for v in sc:
        pre.append(pre[-1] + v)
    INF = float("inf")
    best = [INF] * n
    back = [-1] * n
    for i in range(n):
        # i is the first kept line: every line before it is skipped (allowed only if none is a must)
        if not any(must[:i]):
            best[i] = pre[i]
        for j in range(i - 1, -1, -1):
            d = pos[i] - pos[j]
            if best[j] < INF and not (d < MIN_GAP * g and not (must[i] and must[j])):
                c = best[j] + (d / g - 1.0) ** 2 + (pre[i] - pre[j + 1])
                if c < best[i]:
                    best[i], back[i] = c, j
            if must[j]:
                break               # a must line between j-1 and i cannot be skipped
    end, ec = -1, INF
    for i in range(n):
        if best[i] < INF and not any(must[i + 1:]):
            c = best[i] + (pre[n] - pre[i + 1])
            if c < ec:
                end, ec = i, c
    keep = []
    while end >= 0:
        keep.append(end); end = back[end]
    return [lines[i] for i in reversed(keep)]


def _stats(kept, g, total):
    gaps = [(b["pos"] - a["pos"]) / g for a, b in zip(kept, kept[1:])]
    real = sum(1 for l in kept if not l.get("slot"))
    if not gaps:
        return {"lines": len(kept), "dropped": total - real}
    return {"lines": real, "slots": len(kept) - real, "dropped": total - real, "gap_min": round(min(gaps), 3),
            "gap_max": round(max(gaps), 3), "gap_median": round(sorted(gaps)[len(gaps) // 2], 3),
            "gap_dev": round(sum(abs(x - 1) for x in gaps) / len(gaps), 3)}


def _must_names(domain, avenues, must):
    out = {norm(x) for x in must}
    for av in avenues or ():
        if isinstance(av, str):
            out.add(norm(av))
        elif isinstance(av, dict):
            dom = av.get("dom", av.get("domain"))
            if av.get("kind", "lattice") in ("lattice", "seam") and (dom is None or dom == getattr(domain, "id", None)):
                if av.get("n") or av.get("name"):
                    out.add(norm(av.get("n") or av.get("name")))
    return out


FILL_AT = 1.6           # a kept gap this many targets wide is filled with unnamed slots (see fill)
ISO_SLACK = 1.10        # a family whose median kept gap exceeds this many targets sets the domain's own (smaller) scale


def _must_gap(lines):
    ps = [l["pos"] for l in lines if l["must"]]
    gaps = sorted(b - a for a, b in zip(ps, ps[1:]) if b - a > SAME_LINE)
    if len(gaps) < 3:
        return None
    med = gaps[len(gaps) // 2]
    gaps = [x for x in gaps if x <= 3 * med]
    return gaps[len(gaps) // 2]


ASPECT_MAX = 2.0        # a page block is at most this many CH in its long family (a city of very long blocks keeps 2 rows)


ASPECT_MIN_GAPS = 6     # a family needs this many gaps between its block streets before its block size is trusted


def _block_gap(lines):
    """The real block of one family: the median gap between consecutive must lines, after a must line closer than
    0.45 of the median to the last kept one is dropped (a diagonal avenue's median position between two rows is not a
    row); gaps over 3x the median are breaks, not blocks. -> (gap or None, number of gaps)."""
    ps = sorted(l["pos"] for l in lines if l["must"])
    gaps = sorted(b - a for a, b in zip(ps, ps[1:]) if b - a > SAME_LINE)
    if len(gaps) < 3:
        return None, len(gaps)
    md = gaps[len(gaps) // 2]
    kept = ps[:1]
    for p in ps[1:]:
        if p - kept[-1] >= 0.45 * md:
            kept.append(p)
    gaps = sorted(b - a for a, b in zip(kept, kept[1:]))
    if not gaps:
        return None, 0
    md = gaps[len(gaps) // 2]
    gaps = [x for x in gaps if x <= 3 * md]
    return gaps[len(gaps) // 2], len(gaps)


def real_gaps(domain, majors=(), theta=None, center=None, min_gaps=3):
    """The domain's real block: (the column family's block gap, the row family's), real px, in the domain's own frame
    (_block_gap); a family with fewer than min_gaps gaps gives None."""
    th = domain.theta if theta is None else theta
    cand = candidates(domain.streets or [], th, center or centroid(domain.poly), majors)
    out = []
    for o in ("v", "h"):
        g, n = _block_gap(cand[o])
        out.append(g if g and n >= min_gaps else None)
    return tuple(out)


def block_aspect(domain, majors=(), theta=None, center=None, min_gaps=ASPECT_MIN_GAPS):
    """The real block's height over its width in the domain's frame (rows' block-street gap / columns'), or None
    when either family has too few block streets to say (a tilted district whose one family is all minor streets).
    Philadelphia's main grid: 1.27 (173 x 136 m blocks, taller than wide)."""
    rv, rh = real_gaps(domain, majors, theta, center, min_gaps)
    return rh / rv if rv and rh else None


def block_ch(aspect, cw=CW, ch=CH, roles="vh"):
    """The page size of the family that does not get cw, so that one page block is one real block of the domain's
    shape (design rule: a row is one real block; the half-block alleys then thin out by themselves). roles "vh": the
    rows take it (cw x cw*aspect), "hv": the columns (cw/aspect). Never below ch, never above ASPECT_MAX * ch."""
    if not aspect:
        return ch
    a = aspect if (roles or "vh")[0] == "v" else 1.0 / aspect
    return float(max(ch, min(ASPECT_MAX * ch, round(cw * a / 10.0) * 10.0)))


def fill(kept, g, at=FILL_AT):
    """A gap of at least `at` targets gets round(gap / g) - 1 unnamed slots ({"slot": True, "spans": []}), so
    the page keeps real distance across a park or a void instead of folding it into one block. Slots carry the
    mapping only; they are drawn only where something (graph-paper completion inside the domain) asks."""
    out = []
    for a, b in zip(kept, kept[1:] + [None]):
        out.append(a)
        if b is None:
            continue
        gap = b["pos"] - a["pos"]
        n = int(round(gap / g)) - 1 if gap >= at * g else 0
        for k in range(1, n + 1):
            out.append({"n": None, "pos": a["pos"] + gap * k / (n + 1), "spans": [], "major": False, "len": 0.0,
                        "bridges": [], "k": 9, "must": False, "slot": True})
    return out


def select(domain, avenues=None, majors=(), sigma=1.0, must=(), cw=CW, ch=CH, theta=None, center=None, iso=True,
           slots=True):
    """The lines of one domain from its own streets. roles "vh": columns get cw, rows ch; "hv": swapped.
    sigma: page px per real px (one per city, see scale()); the target real gaps are page spacing / sigma.
    iso: when a family cannot reach the target density (its median kept gap is over ISO_SLACK targets), the
    whole domain takes the scale that family imposes, so its page stays isotropic (angles on the page = real
    angles) instead of squeezing one axis; the domain's sigma is in the result."""
    th = domain.theta if theta is None else theta
    ctr = center or centroid(domain.poly)
    mn = _must_names(domain, avenues, must)
    cand = candidates(domain.streets, th, ctr, majors, mn)
    roles = getattr(domain, "roles", "vh") or "vh"
    gv = (cw if roles[0] == "v" else ch)
    gh = (ch if roles[0] == "v" else cw)
    sig = sigma
    if iso:
        # one family may be unable to reach the target density (West Philadelphia's numbered streets are 178 m
        # apart and nothing runs between them; Manhattan's avenues are 3 streets apart): the domain then takes
        # the scale that keeps the page most nearly isotropic, min over s of max(|log rho_v(s)|, |log rho_h(s)|)
        # with rho = median kept gap / target (optional lines re-thin at every s; must lines cannot)
        def rho(sg):
            out = []
            for o, g in (("v", gv), ("h", gh)):
                kept = thin(cand[o], g / sg)
                gaps = sorted((b["pos"] - a["pos"]) * sg / g for a, b in zip(kept, kept[1:]))
                out.append(gaps[len(gaps) // 2] if len(gaps) >= 4 else 1.0)
            return out
        r0 = rho(sigma)
        if max(r0) > ISO_SLACK:
            best = (max(abs(math.log(x)) for x in r0), sigma)
            for k in range(1, 31):
                sg = sigma / (max(r0) ** (k / 30.0))
                e = max(abs(math.log(x)) for x in rho(sg))
                if e < best[0] - 1e-9:
                    best = (e, sg)
            sig = best[1]
    tg = {"v": gv / sig, "h": gh / sig}
    out = {"theta": th, "center": ctr, "gv": gv, "gh": gh, "sigma": sig, "sigma_city": sigma, "stats": {}}
    for o in ("v", "h"):
        kept = fill(thin(cand[o], tg[o]), tg[o]) if slots else thin(cand[o], tg[o])
        for i, l in enumerate(kept):
            l["i"] = i
        out[o] = kept
        out["stats"][o] = _stats(kept, tg[o], len(cand[o]))
    return out


def scale(domain, majors=(), cw=CW, theta=None, center=None, ch=CH):
    """sigma = the family's block size (cw for columns, ch for rows) / the median real gap between its consecutive
    must lines (numbered/major streets), for the family with the most of them (gaps over 3x the median are breaks,
    not blocks). 1.0 when the domain has too few."""
    th = domain.theta if theta is None else theta
    cand = candidates(domain.streets, th, center or centroid(domain.poly), majors)
    best = None
    roles = getattr(domain, "roles", "vh") or "vh"
    for o in ("v", "h"):
        ps = [l["pos"] for l in cand[o] if l["must"]]
        gaps = sorted(b - a for a, b in zip(ps, ps[1:]) if b - a > SAME_LINE)
        if len(gaps) >= 3:
            med = gaps[len(gaps) // 2]
            gaps = [x for x in gaps if x <= 3 * med]
            med = gaps[len(gaps) // 2]
            nominal = cw if (o == "v") == (roles[0] == "v") else ch
            if best is None or len(gaps) > best[1]:
                best = (nominal / med, len(gaps))
    return best[0] if best else 1.0


class LocalMapping(Mapping):
    """palace_grid.Mapping whose extrapolation past the last line uses the domain's own spacing."""

    def __init__(self, th, cx, cy, xr, xg, yr, yg, gv=CW, gh=CH):
        super().__init__(th, cx, cy, xr, xg, yr, yg)
        self.gv, self.gh = gv, gh

    def turned(self, tx, ty):
        return (self._interp(tx, self.xr, self.xg, self.gv), self._interp(ty, self.yr, self.yg, self.gh))

    def tables(self):
        t = super().tables()
        t.update(gv=self.gv, gh=self.gh)
        return t


def mapping(lines, gv=None, gh=None):
    """The domain's local Mapping: real px -> local lattice px, column i at x = i*gv, row j at y = j*gh."""
    gv = gv or lines.get("gv", CW)
    gh = gh or lines.get("gh", CH)
    xr = [l["pos"] for l in lines["v"]]
    yr = [l["pos"] for l in lines["h"]]
    cx, cy = lines["center"]
    return LocalMapping(lines["theta"], cx, cy, xr, [i * gv for i in range(len(xr))],
                        yr, [j * gh for j in range(len(yr))], gv, gh)
