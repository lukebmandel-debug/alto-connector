"""City engine v2, quality report R10 (design section 7.1).

    report(g, m, doms=None, seams=None, aliases=None, blocks=None) -> {"checks": {...}, "fail": [...], "warn": [...]}

g is what palace_grid.grid() returns (the page map; it still carries "blocks" unless set_up popped them, else pass
`blocks`); m is the real map build_map made (before grid). The report runs on today's one-lattice output (1.9.78) and on
the v2 output: v2 data adds g["doms"] (city_types.Domain or dicts: id, kind, theta, poly (real ring), a, o, mapping or
"grid" tables, clip (page ring)) and g["seams"] (city_types.Seam or dicts); they may also be passed as arguments.
A city ships only with no "fail". Thresholds are in TH.

Pure: no network; the only imports are the engine's own pure helpers.
"""
from __future__ import annotations

import math

from .palace_grid import CW, CH, PAD, LEAD, norm, mapping_from, Mapping, _inside
from .city_avenues import (chains, poly_d, segd, plen, resample, _pairs, _dget, area, dom_finder)

BLOCK = (CW + CH) / 2
TH = {
    "dom_min_km2": 0.6, "free_warn": 0.30,
    "phantom_cov": 0.25, "phantom_warn": 0.30, "phantom_fail": 0.50,
    "disp_warn": 1.0, "disp_fail": 1.5,
    "seam_err_warn": 6.0, "seam_err_fail": 12.0, "seam_r_warn": .1, "seam_r_fail": .2,
    "tjoin_warn": 1.0, "tjoin_fail": 1.5,
    "bends_max": 2,
    "cut_warn": .05, "cut_fail": .10,
    "size_warn": 1.5, "size_fail": 3.0,
    "overlap_blocks": .1,
}
# Philadelphia 1.9.78 (measured by this report on the release data): packed kB of {"map", "blocks"} and its real bbox km²
BASE_KB, BASE_KM2 = 162.0, 166.1


# ── helpers ────────────────────────────────────────────────────────────────
def unmap(tables, x, y):
    """The inverse of palace_grid.Mapping (page px -> real px), from its tables."""
    def inv(v, R, G, step):
        if not G:
            return v
        if v <= G[0]:
            return R[0] - (G[0] - v) * max(1e-6, (R[1] - R[0]) if len(R) > 1 else 1) / step
        if v >= G[-1]:
            return R[-1] + (v - G[-1]) * max(1e-6, (R[-1] - R[-2]) if len(R) > 1 else 1) / step
        lo, hi = 0, len(G) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if G[mid] <= v:
                lo = mid
            else:
                hi = mid
        return R[lo] + (v - G[lo]) / max(1e-9, G[hi] - G[lo]) * (R[hi] - R[lo])
    tx, ty = inv(x, tables["xr"], tables["xg"], CW), inv(y, tables["yr"], tables["yg"], CH)
    th, cx, cy = tables["t"], tables["cx"], tables["cy"]
    c, s = math.cos(th), math.sin(th)
    tx, ty = tx - cx, ty - cy
    return (tx * c - ty * s + cx, tx * s + ty * c + cy)


def _mapping(d):
    mp = _dget(d, "mapping")
    if isinstance(mp, dict):
        return mapping_from(mp)
    return mp


def _page(d, p):
    a = math.radians(_dget(d, "a", 0.0) or 0.0)
    ox, oy = _dget(d, "o", (0.0, 0.0)) or (0.0, 0.0)
    c, s = math.cos(a), math.sin(a)
    return (ox + p[0] * c - p[1] * s, oy + p[0] * s + p[1] * c)


def _rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _side(p, line):
    """+1/-1: which side of a polyline (extended far beyond its ends) p lies on; 0 on it."""
    if len(line) < 2:
        return 0
    (ax, ay), (bx, by) = line[0], line[1]
    L = math.hypot(bx - ax, by - ay) or 1
    ext0 = (ax - (bx - ax) / L * 1e6, ay - (by - ay) / L * 1e6)
    (cx_, cy_), (dx_, dy_) = line[-2], line[-1]
    L = math.hypot(dx_ - cx_, dy_ - cy_) or 1
    ext1 = (dx_ + (dx_ - cx_) / L * 1e6, dy_ + (dy_ - cy_) / L * 1e6)
    pts = [ext0] + list(line) + [ext1]
    best, bs, bi = 1e18, 0, 0
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        d = segd(p, a, b)
        if d < best:
            cr = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
            best, bs, bi = d, (1 if cr > 0 else -1 if cr < 0 else 0), i
    if bi == 0 or bi == len(pts) - 2:
        return 0           # beyond an end of the line: 'which side' is not defined there
    return bs


def _xing(a, b, c, d):
    d1 = (b[0] - a[0]) * (d[1] - c[1]) - (b[1] - a[1]) * (d[0] - c[0])
    if abs(d1) < 1e-9:
        return None
    t = ((c[0] - a[0]) * (d[1] - c[1]) - (c[1] - a[1]) * (d[0] - c[0])) / d1
    u = ((c[0] - a[0]) * (b[1] - a[1]) - (c[1] - a[1]) * (b[0] - a[0])) / d1
    if 0 <= t <= 1 and 0 <= u <= 1:
        return t, u
    return None


def _octi(a, b, base=0.0, tol=1.0):
    ang = (math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) - base) % 45
    return min(ang, 45 - ang) <= tol


class _Segs:
    """A bucket index of page segments for 'is this point on a drawn street' queries."""
    def __init__(self, polys, B=120):
        self.B, self.b, self.s = B, {}, []
        for pi, P in enumerate(polys):
            for a, c in zip(P, P[1:]):
                k = len(self.s)
                self.s.append((a, c, pi))
                for bx in range(int(min(a[0], c[0]) // B) - 1, int(max(a[0], c[0]) // B) + 2):
                    for by in range(int(min(a[1], c[1]) // B) - 1, int(max(a[1], c[1]) // B) + 2):
                        self.b.setdefault((bx, by), []).append(k)

    def near(self, p, tol, skip=None):
        for k in self.b.get((int(p[0] // self.B), int(p[1] // self.B)), []):
            a, c, pi = self.s[k]
            if pi != skip and segd(p, a, c) <= tol:
                return True
        return False


# ── the model of g the checks read (v1 and v2 alike) ──────────────────────
def _model(g, m, doms, seams):
    doms = list(doms if doms is not None else (g.get("doms") or []))
    seams = list(seams if seams is not None else (g.get("seams") or []))
    root_t = g.get("grid")
    legacy = []
    streets = [s for s in g.get("streets", []) if not s.get("o")]
    sc = m.get("scale") or 1.0
    if not doms:
        # v1: one root lattice; 1.9.78's tilted district (straight unbent 'd' lines at a non-octilinear angle) is
        # reported as a second domain drawn in the root's page frame
        xg, yg = root_t["xg"], root_t["yg"]
        doms = [{"id": 0, "kind": "grid", "theta": root_t["t"], "a": 0.0, "o": (0.0, 0.0), "mapping": root_t,
                 "clip": _rect(xg[0], yg[0], xg[-1], yg[-1]), "poly": _rect(0, 0, m["W"], m["H"])}]
        tl = [s for s in streets if s.get("d") and len(s["p"]) == 4 and not _octi(*_pairs(s["p"]))]
        if tl:
            xs = [v for s in tl for v in s["p"][0::2]]; ys = [v for s in tl for v in s["p"][1::2]]
            clip = _rect(min(xs), min(ys), max(xs), max(ys))
            angs = [math.degrees(math.atan2(s["p"][3] - s["p"][1], s["p"][2] - s["p"][0])) % 90 for s in tl]
            a = sorted(angs)[len(angs) // 2]
            poly = [unmap(root_t, *q) for q in clip]
            doms.append({"id": 1, "kind": "grid", "theta": root_t["t"] + math.radians(a), "a": a, "o": (0.0, 0.0),
                         "mapping": root_t, "clip": clip, "poly": poly, "legacy": True})
            legacy = tl
    for d in doms:
        if _dget(d, "mapping") is None and _dget(d, "kind", "grid") == "grid":
            if isinstance(d, dict):
                d["mapping"] = root_t
    finder = dom_finder(doms)
    by_id = {_dget(d, "id"): d for d in doms}
    maps = {i: _mapping(d) for i, d in by_id.items()}

    def to_page(x, y):
        """Real px -> page px through the domain the point is in (the root's mapping when in none)."""
        i = finder(x, y)
        d = by_id.get(i) or by_id.get(0) or doms[0]
        if _dget(d, "legacy"):
            d = by_id[0]
        mp = maps.get(_dget(d, "id"))
        if mp is None:
            return None
        return _page(d, mp(x, y))
    return {"doms": doms, "seams": seams, "streets": streets, "legacy": legacy, "to_page": to_page, "sc": sc,
            "finder": finder, "by_id": by_id}


# ── checks ─────────────────────────────────────────────────────────────────
def c_domains(g, m, M):
    sc = M["sc"]
    rows, total = [], 0.0
    for d in M["doms"]:
        km2 = area(list(map(tuple, _dget(d, "poly") or []))) / 1e6 / (sc * sc)
        rows.append({"id": _dget(d, "id"), "kind": _dget(d, "kind", "grid"), "km2": round(km2, 2),
                     "theta": round(math.degrees(_dget(d, "theta", 0.0) or 0.0), 1), "a": round(_dget(d, "a", 0.0) or 0.0, 1),
                     "legacy": bool(_dget(d, "legacy"))})
    root = rows[0]["km2"] if rows else 0
    for r in rows[1:]:
        if r["kind"] == "grid" or True:
            pass
    total = max(1e-9, m["W"] * m["H"] / 1e6 / (sc * sc))
    free = sum(r["km2"] for r in rows if r["kind"] == "free")
    small = [r for r in rows if r["kind"] == "grid" and r["km2"] < TH["dom_min_km2"]]
    grid_city = any(r["kind"] == "grid" for r in rows)
    st = "fail" if small else "warn" if grid_city and free / total > TH["free_warn"] else "ok"
    msg = "%d domains (%s)" % (len(rows), ", ".join("%s%s %.1f° %.1f km²" % (r["kind"], "*" if r["legacy"] else "",
                                                                           r["theta"], r["km2"]) for r in rows))
    return st, msg, {"domains": rows, "free_share": round(free / total, 3), "root_km2": root}


def _lines_of(M):
    """The lattice lines on the page: straight runs of non-avenue streets grouped by (angle, offset)."""
    groups = {}
    leg = {id(s) for s in M["legacy"]}
    for s in M["streets"]:
        if s.get("d") and id(s) not in leg:
            continue
        P = _pairs(s["p"])
        for i, (a, b) in enumerate(zip(P, P[1:])):
            L = math.dist(a, b)
            if L < 1:
                continue
            if (i == 0 or i == len(P) - 2) and L <= LEAD + .5 and len(P) > 2:
                continue                     # a turn into the next street, not the line itself
            ang = math.atan2(b[1] - a[1], b[0] - a[0]) % math.pi
            nx, ny = -math.sin(ang), math.cos(ang)
            off = a[0] * nx + a[1] * ny
            key = (round(math.degrees(ang)) % 180, round(off / 3))
            gr = groups.setdefault(key, {"ang": ang, "off": off, "names": {}, "segs": []})
            gr["segs"].append((a, b))
            gr["names"][s.get("n") or ""] = gr["names"].get(s.get("n") or "", 0) + L
    return list(groups.values())


def c_phantom(g, m, M):
    """Per lattice line: the share of its drawn length where its real street (same name) really runs."""
    lines = _lines_of(M)
    names = {norm(n) for gr in lines for n in gr["names"] if n}
    real = {}
    for st in m.get("streets", []):
        if st.get("t") or not st.get("n"):
            continue
        n = norm(st["n"])
        if n not in names:
            continue
        P = [M["to_page"](x, y) for x, y in _pairs(st["p"])]
        real.setdefault(n, []).append([q for q in P if q])
    res, low = [], []
    for gr in lines:
        nm = max(gr["names"], key=gr["names"].get)
        nn = norm(nm)
        ux, uy = math.cos(gr["ang"]), math.sin(gr["ang"])
        drawn = sum(math.dist(a, b) for a, b in gr["segs"])
        if drawn < BLOCK:
            continue
        iv = []
        for P in real.get(nn, []) if nn else []:
            for a, b in zip(P, P[1:]):
                L = math.dist(a, b)
                if L < 1:
                    continue
                if abs(((b[0] - a[0]) * uy - (b[1] - a[1]) * ux) / L) > math.sin(math.radians(25)):
                    continue
                mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                if abs(mid[0] * -uy + mid[1] * ux - gr["off"]) > .5 * BLOCK:
                    continue
                t0, t1 = sorted((a[0] * ux + a[1] * uy, b[0] * ux + b[1] * uy))
                iv.append((t0, t1))
        iv.sort()
        un = []
        for t0, t1 in iv:
            if un and t0 <= un[-1][1]:
                un[-1][1] = max(un[-1][1], t1)
            else:
                un.append([t0, t1])
        cov = 0.0
        for a, b in gr["segs"]:
            s0, s1 = sorted((a[0] * ux + a[1] * uy, b[0] * ux + b[1] * uy))
            for t0, t1 in un:
                cov += max(0.0, min(s1, t1) - max(s0, t0))
        r = min(1.0, cov / drawn)
        res.append((round(r, 3), nm, round(drawn)))
        gr["cov"] = r
        if r < TH["phantom_cov"]:
            low.append((round(r, 2), nm or "(unnamed)", round(drawn / BLOCK, 1)))
    share = len(low) / max(1, len(res))
    st = "fail" if share > TH["phantom_fail"] else "warn" if share > TH["phantom_warn"] else "ok"
    covs = sorted(r for r, _, _ in res)
    med = covs[len(covs) // 2] if covs else 0
    low.sort()
    return st, "%d of %d lattice lines (%.0f%%) are under %.0f%% real (median coverage %.2f)" % (
        len(low), len(res), 100 * share, 100 * TH["phantom_cov"], med), \
        {"lines": len(res), "low": len(low), "share": round(share, 3), "median": med,
         "worst": low[:15], "unnamed": sum(1 for _, n, _ in low if n == "(unnamed)")}


def _match_landmarks(g, m, aliases):
    al = {k.lower(): v.lower() for k, v in (aliases or {}).items()}
    real = m.get("landmarks", []) + m.get("stations", [])
    out, miss = [], []
    for l in g.get("landmarks", []):
        n = (l.get("n") or "").lower()
        want = al.get(n, n)
        f = next((r for r in real if r.get("n", "").lower() == want), None) or \
            next((r for r in real if want and (want in r.get("n", "").lower() or r.get("n", "").lower() in want)), None)
        if f:
            out.append((l["n"], (f["x"], f["y"]), (l["x"], l["y"]), "landmark"))
        else:
            miss.append(l["n"])
    return out, miss


def _match_stops(g, m, M):
    out = []
    rs = (m.get("transit") or {}).get("stops", []) + m.get("stations", [])
    for s in (g.get("transit") or {}).get("stops", []):
        cands = [r for r in rs if r.get("n", "").lower() == s["n"].lower()]
        if not cands:
            continue
        best = min(cands, key=lambda r: math.dist(M["to_page"](r["x"], r["y"]) or (1e9, 1e9), (s["x"], s["y"])))
        out.append((s["n"], (best["x"], best["y"]), (s["x"], s["y"]), "stop"))
    for s in g.get("stations", []):
        cands = [r for r in rs if r.get("n", "").lower() == s["n"].lower()]
        if cands:
            out.append((s["n"], (cands[0]["x"], cands[0]["y"]), (s["x"], s["y"]), "station"))
    return out


def c_displacement(g, m, M, aliases):
    """Each landmark and stop: its page position against where its real position maps (the lattice of streets around
    it predicts it), in blocks; and, for information, against the local affine fit of its 4 nearest neighbours."""
    lm, miss = _match_landmarks(g, m, aliases)
    pts = lm + _match_stops(g, m, M)
    rows = []
    for n, r, p, kind in pts:
        q = M["to_page"](*r)
        if q is None:
            continue
        d = math.hypot((p[0] - q[0]) / CW, (p[1] - q[1]) / CH)
        rows.append((round(d, 2), n, kind))
    # neighbour-relative (information): affine from the 4 nearest other points, real -> page
    rel = []
    for i, (n, r, p, kind) in enumerate(pts):
        nb = sorted((math.dist(r, o[1]), j) for j, o in enumerate(pts) if j != i and math.dist(r, o[1]) > 30)[:4]
        if len(nb) < 3:
            continue
        A = [pts[j] for _, j in nb]
        fit = _affine([a[1] for a in A], [a[2] for a in A])
        if fit is None:
            continue
        q = (fit[0] * r[0] + fit[1] * r[1] + fit[2], fit[3] * r[0] + fit[4] * r[1] + fit[5])
        rel.append(math.hypot((p[0] - q[0]) / CW, (p[1] - q[1]) / CH))
    rows.sort(reverse=True)
    worst = rows[0][0] if rows else 0.0
    nf = sum(1 for d, _, _ in rows if d > TH["disp_fail"])
    st = "fail" if nf else "warn" if worst > TH["disp_warn"] or miss else "ok"
    return st, "%d points; %d over %.1f blocks, worst %.2f (%s)%s" % (
        len(rows), nf, TH["disp_fail"], worst, rows[0][1] if rows else "-",
        "; unmatched landmarks: " + ", ".join(miss) if miss else ""), \
        {"n": len(rows), "over": nf, "worst": rows[:12], "unmatched": miss,
         "rel_median": round(sorted(rel)[len(rel) // 2], 2) if rel else None}


def _affine(src, dst):
    """Least-squares affine src -> dst (3+ points): (a, b, c, d, e, f) or None."""
    n = len(src)
    if n < 3:
        return None
    sx = sum(p[0] for p in src) / n; sy = sum(p[1] for p in src) / n
    ux = sum(p[0] for p in dst) / n; uy = sum(p[1] for p in dst) / n
    xx = sum((p[0] - sx) ** 2 for p in src); yy = sum((p[1] - sy) ** 2 for p in src)
    xy = sum((p[0] - sx) * (p[1] - sy) for p in src)
    det = xx * yy - xy * xy
    if abs(det) < 1e-6 * max(1.0, xx * yy):
        return None
    def solve(k):
        bx = sum((p[0] - sx) * (q[k] - (ux, uy)[k]) for p, q in zip(src, dst))
        by = sum((p[1] - sy) * (q[k] - (ux, uy)[k]) for p, q in zip(src, dst))
        a = (bx * yy - by * xy) / det; b = (by * xx - bx * xy) / det
        return a, b, (ux, uy)[k] - a * sx - b * sy
    a, b, c = solve(0); d, e, f = solve(1)
    return (a, b, c, d, e, f)


def _inversions(seq):
    return sum(1 for i in range(len(seq)) for j in range(i + 1, len(seq)) if seq[i] > seq[j])


def c_order(g, m, M):
    """Order swaps: (1) along each transit branch, the stops' order along the drawn track; (2) along each avenue, the
    order of the named streets it crosses on the page against the order it crosses them in reality."""
    from .palace_transit_audit import _near
    tr = g.get("transit") or {}
    stops = tr.get("stops", [])
    swaps = []
    for ln in tr.get("lines", []):
        polys = ln.get("p") or []
        if not polys:
            continue
        for br in ln.get("b") or [ln.get("s") or []]:
            near = [(_near(polys, stops[i]["x"], stops[i]["y"]), stops[i]["n"]) for i in br if i < len(stops)]
            runs, cur = [], []
            for (d, pi, arc), n in near:
                if d > 20:
                    continue
                if cur and cur[-1][0] != pi:
                    runs.append(cur); cur = []
                cur.append((pi, arc, n))
            if cur:
                runs.append(cur)
            for r in runs:
                diffs = [(b[1] - a[1], a[2], b[2]) for a, b in zip(r, r[1:]) if abs(b[1] - a[1]) > 5]
                if not diffs:
                    continue
                sgn = 1 if sum(1 for d, _, _ in diffs if d > 0) >= len(diffs) / 2 else -1
                for d, a, b in diffs:
                    if d * sgn < 0:
                        swaps.append("%s: %s / %s" % (ln.get("n"), a, b))
    # avenues: crossings on the page vs in reality
    avs = {}
    for s in M["streets"]:
        if s.get("d") and s.get("n") and len(s["p"]) > 4:
            avs.setdefault(norm(s["n"]), []).append(_pairs(s["p"]))
    lines = [(norm(s.get("n") or ""), _pairs(s["p"])) for s in M["streets"] if not s.get("d") and s.get("n")]
    av_sw, checked = [], 0
    ch = chains(m, set(avs)) if avs else {}
    real_by = {}
    for st in m.get("streets", []):
        if not st.get("t") and st.get("n"):
            real_by.setdefault(norm(st["n"]), []).append(_pairs(st["p"]))
    for n, polys in avs.items():
        for P in polys:
            page_x = []
            acc = 0.0
            for a, b in zip(P, P[1:]):
                for ln_, Q in lines:
                    if ln_ == n:
                        continue
                    for c, d in zip(Q, Q[1:]):
                        h = _xing(a, b, c, d)
                        if h and 0.01 < h[0] < .99:
                            page_x.append((acc + h[0] * math.dist(a, b), ln_))
                acc += math.dist(a, b)
            page_x.sort()
            seen, order_p, at_p = set(), [], {}
            for t_, ln_ in page_x:
                if ln_ not in seen:
                    seen.add(ln_); order_p.append(ln_); at_p[ln_] = t_
            if len(order_p) < 3 or not ch.get(n):
                continue
            R = ch[n][0]
            real_x = {}
            acc = 0.0
            for a, b in zip(R, R[1:]):
                bb = (min(a[0], b[0]) - 1, min(a[1], b[1]) - 1, max(a[0], b[0]) + 1, max(a[1], b[1]) + 1)
                for ln_ in order_p:
                    for Q in real_by.get(ln_, []):
                        for c, d in zip(Q, Q[1:]):
                            if max(c[0], d[0]) < bb[0] or min(c[0], d[0]) > bb[2] or max(c[1], d[1]) < bb[1] or min(c[1], d[1]) > bb[3]:
                                continue
                            h = _xing(a, b, c, d)
                            if h and ln_ not in real_x:
                                real_x[ln_] = acc + h[0] * math.dist(a, b)
                acc += math.dist(a, b)
            common = [x for x in order_p if x in real_x]
            if len(common) < 3:
                continue
            checked += 1
            seq = [real_x[x] for x in common]
            sgn = 1 if _inversions(seq) <= _inversions(seq[::-1]) else -1
            inv = sum(1 for i in range(len(common)) for j in range(i + 1, len(common))
                      if (seq[j] - seq[i]) * sgn < 0 and at_p[common[j]] - at_p[common[i]] > BLOCK / 2)
            if inv:
                av_sw.append((n, inv, len(common)))
    st = "fail" if swaps or av_sw else "ok"
    return st, "%d stop-order swaps; %d of %d avenues cross streets out of order%s" % (
        len(swaps), len(av_sw), checked, (" (" + ", ".join("%s %d/%d" % a for a in av_sw[:6]) + ")") if av_sw else ""), \
        {"stops": swaps[:12], "avenues": av_sw}


def c_side(g, m, M, blocks):
    """Every landmark, stop and lot centre on the same side of every river (and seam) as in reality."""
    pairs = []          # (name, real line, page line)
    rr = {}
    for r in m.get("rivers", []):
        rr.setdefault(r.get("n"), []).append(_pairs(r["p"]))
    from .palace_river import _main_piece
    for rv in g.get("river", []):
        R = _main_piece(m.get("rivers", []), rv.get("n"))      # the piece the page river is drawn from
        if not R:
            continue
        pairs.append((rv.get("n"), R, _pairs(rv["p"]), rv.get("w", 0)))
    for s in M["seams"]:
        real = [tuple(q) for q in (_dget(s, "real") or [])]
        segs = _dget(s, "segs") or []
        if real and segs:
            page = [(segs[0][0], segs[0][1])] + [(q[2], q[3]) for q in segs]
            pairs.append(("seam %s|%s" % (_dget(s, "a"), _dget(s, "b")), real, page, 0))
    if not pairs:
        return "ok", "no rivers or seams", {}
    from .palace_grid import _dp
    pairs = [(n, _dp(R, 15), _dp(P, 15), w) for n, R, P, w in pairs]
    lm, _ = _match_landmarks(g, m, None)
    pts = [(n, r, p) for n, r, p, _ in lm + _match_stops(g, m, M)]
    t = g.get("grid")
    nlots = 0
    for bl in blocks or []:
        for L in bl.get("lots", []):
            rp = tuple(bl["r"]) if bl.get("r") and len(bl.get("lots")) == 1 else (unmap(t, L[0], L[1]) if t else None)
            if rp:
                pts.append(("lot %s" % bl.get("id"), rp, (L[0], L[1]))); nlots += 1
    bad = []
    for name, R, P, w in pairs:
        for n, r, p in pts:
            # only within 4 blocks of the river or seam, where 'which side' is what a reader sees
            if poly_d(p, P) > w / 2 + 4 * BLOCK:
                continue
            a, b = _side(r, R), _side(p, P)
            if a and b and a != b:
                bad.append("%s: %s" % (name, n))
    st = "fail" if bad else "ok"
    return st, "%d of %d points on the wrong side (%d lots checked)" % (len(bad), len(pts), nlots), \
        {"bad": bad[:20], "n_bad": len(bad)}


def c_seam_fidelity(g, m, M):
    rows = []
    for s in M["seams"]:
        segs = _dget(s, "segs") or []
        real = [tuple(q) for q in (_dget(s, "real") or [])]
        err = _dget(s, "err", None)
        if real and segs:
            a_dom = M["by_id"].get(_dget(s, "a"))
            mp = _mapping(a_dom) if a_dom is not None else None
            if mp is not None:
                Q = [_page(a_dom, mp(x, y)) for x, y in real]
                ang_r = math.degrees(math.atan2(Q[-1][1] - Q[0][1], Q[-1][0] - Q[0][0]))
                L = sum(math.hypot(q[2] - q[0], q[3] - q[1]) for q in segs) or 1
                ang_p = math.degrees(math.atan2(sum(q[3] - q[1] for q in segs), sum(q[2] - q[0] for q in segs)))
                e = abs((ang_r - ang_p + 90) % 180 - 90)
                err = e if err in (None, 0.0) else err
        r = _dget(s, "ratio", 1.0) or 1.0
        rows.append({"a": _dget(s, "a"), "b": _dget(s, "b"), "kind": _dget(s, "kind"), "avenue": _dget(s, "avenue"),
                     "err": round(err or 0.0, 1), "r": round(r, 3)})
    if not rows:
        return "ok", "no seams", {"seams": []}
    worst_e = max(r["err"] for r in rows); worst_r = max(abs(r["r"] - 1) for r in rows)
    st = "fail" if worst_e > TH["seam_err_fail"] or worst_r > TH["seam_r_fail"] else \
        "warn" if worst_e > TH["seam_err_warn"] or worst_r > TH["seam_r_warn"] else "ok"
    return st, "%d seams; worst angle error %.1f°, worst |r-1| %.2f" % (len(rows), worst_e, worst_r), {"seams": rows}


def c_tjoin(g, m, M):
    """Each line that ends on a seam: where it ends along the seam vs where its real street meets the real seam."""
    rows = []
    real_by = {}
    for st in m.get("streets", []):
        if not st.get("t") and st.get("n"):
            real_by.setdefault(norm(st["n"]), []).append(_pairs(st["p"]))
    for s in M["seams"]:
        segs = _dget(s, "segs") or []
        real = [tuple(q) for q in (_dget(s, "real") or [])]
        if not segs or not real:
            continue
        seg_pts = [((q[0], q[1]), (q[2], q[3])) for q in segs]
        for st in M["streets"]:
            if not st.get("n"):
                continue
            P = _pairs(st["p"])
            for e in (P[0], P[-1]) if len(P) == 2 else (P[1] if len(P) > 2 else P[0], P[-2] if len(P) > 2 else P[-1]):
                if min(segd(e, a, b) for a, b in seg_pts) > 3:
                    continue
                nb = P[1] if e == P[0] else P[-2]
                sa, sb = seg_pts[0]
                cosang = abs((nb[0] - e[0]) * (sb[0] - sa[0]) + (nb[1] - e[1]) * (sb[1] - sa[1])) / (
                    (math.dist(nb, e) * math.dist(sa, sb)) or 1)
                if cosang > math.cos(math.radians(20)):
                    continue
                hits = []
                for Q in real_by.get(norm(st["n"]), []):
                    for c, d in zip(Q, Q[1:]):
                        for a, b in zip(real, real[1:]):
                            h = _xing(c, d, a, b)
                            if h:
                                hits.append((c[0] + h[0] * (d[0] - c[0]), c[1] + h[0] * (d[1] - c[1])))
                if not hits:
                    continue
                pp = [M["to_page"](*h) for h in hits]
                off = min(math.hypot((q[0] - e[0]) / CW, (q[1] - e[1]) / CH) for q in pp if q)
                rows.append((round(off, 2), st["n"]))
    if not rows:
        return "ok", "no lines end on a seam", {}
    rows.sort(reverse=True)
    st = "fail" if rows[0][0] > TH["tjoin_fail"] else "warn" if rows[0][0] > TH["tjoin_warn"] else "ok"
    return st, "%d lines end on seams; worst %.2f blocks off (%s)" % (len(rows), rows[0][0], rows[0][1]), {"worst": rows[:10]}


def c_ends(g, m, M):
    """Line ends that land on nothing: not on another drawn street, a seam, the river, a domain's edge."""
    polys = [_pairs(s["p"]) for s in M["streets"]]
    idx = _Segs(polys)
    rivers = [(_pairs(r["p"]), r.get("w", 0)) for r in g.get("river", [])]
    edges = []
    for d in M["doms"]:
        c = _dget(d, "clip")
        if c:
            c = [tuple(q) for q in c]
            edges += [(c[i], c[(i + 1) % len(c)]) for i in range(len(c))]
    for s in M["seams"]:
        edges += [((q[0], q[1]), (q[2], q[3])) for q in (_dget(s, "segs") or [])]
    lms = [l["box"] for l in g.get("landmarks", []) if l.get("box")]
    clips = [[tuple(q) for q in _dget(d, "clip")] for d in M["doms"] if _dget(d, "clip")]
    bad, over = [], []
    for pi, P in enumerate(polys):
        if len(P) < 2:
            continue
        for e in (P[0], P[-1]):
            if idx.near(e, 3.0, skip=pi):
                continue
            if any(segd(e, a, b) <= 3.0 for a, b in edges):
                continue
            if any(poly_d(e, R) <= w / 2 + 30 for R, w in rivers):
                continue
            if any(b[0] - 3 <= e[0] <= b[2] + 3 and b[1] - 3 <= e[1] <= b[3] + 3 for b in lms):
                continue
            row = (M["streets"][pi].get("n") or "(unnamed)", round(e[0]), round(e[1]))
            (bad if any(_inside(e, [c]) for c in clips) else over).append(row)
    st = "fail" if bad else "warn" if over else "ok"
    return st, "%d line ends land on nothing inside the grid; %d run past its edge" % (len(bad), len(over)), \
        {"n": len(bad), "examples": bad[:15], "overhang": len(over), "overhang_examples": over[:8]}


def c_cross_seam(g, m, M):
    bad = []
    for s in M["seams"]:
        segs = [((q[0], q[1]), (q[2], q[3])) for q in (_dget(s, "segs") or [])]
        hinge_names = set()
        for h in _dget(s, "hinge") or []:
            for x in (h if isinstance(h, (list, tuple)) else [h]):
                if isinstance(x, str):
                    hinge_names.add(norm(x))
        for st in M["streets"]:
            if norm(st.get("n") or "") in hinge_names or st.get("d"):
                continue
            P = _pairs(st["p"])
            for a, b in zip(P, P[1:]):
                for c, d in segs:
                    h = _xing(a, b, c, d)
                    if h and .02 < h[0] < .98 and .001 < h[1] < .999:
                        bad.append(st.get("n") or "(unnamed)")
    st = "fail" if bad else "ok"
    return st, "%d non-hinge lines cross a seam" % len(bad), {"bad": sorted(set(bad))[:15]}


def c_avenues(g, m, M):
    """Avenues ('d' streets other than 1.9.78's tilted lattice lines): pieces, bends per piece, octilinear runs,
    joined ends."""
    polys = [_pairs(s["p"]) for s in M["streets"]]
    idx = _Segs(polys)
    leg = {id(s) for s in M["legacy"]}
    clips = [[tuple(q) for q in _dget(d, "clip")] for d in M["doms"] if _dget(d, "clip")]

    def _in_clips(e):        # an end past every domain's page region ends on the edge, not mid-block
        return any(_inside(e, [c]) and min(segd(e, c[i], c[(i + 1) % len(c)]) for i in range(len(c))) > 3
                   for c in clips)
    rows, bad = {}, []
    for pi, s in enumerate(M["streets"]):
        if not s.get("d") or id(s) in leg:
            continue
        P = polys[pi]
        d = M["by_id"].get(s.get("dom", 0)) or M["doms"][0]
        base = _dget(d, "a", 0.0) or 0.0
        core = P[1:-1] if len(P) > 3 and math.dist(P[0], P[1]) <= LEAD + .5 and math.dist(P[-1], P[-2]) <= LEAD + .5 else P
        nb = 0
        for a, b, c in zip(core, core[1:], core[2:]):
            t1 = math.atan2(b[1] - a[1], b[0] - a[0]); t2 = math.atan2(c[1] - b[1], c[0] - b[0])
            if abs((t2 - t1 + math.pi) % (2 * math.pi) - math.pi) > math.radians(1):
                nb += 1
        bends = s.get("bends") or [nb]
        non_octi = sum(1 for a, b in zip(core, core[1:]) if math.dist(a, b) > 1 and not _octi(a, b, base))
        dangling = sum(1 for e in (P[0], P[-1]) if not idx.near(e, 3.0, skip=pi) and _in_clips(e))
        n = s.get("n") or "(unnamed)"
        r = rows.setdefault(n, {"pieces": 0, "bends": [], "non_octi": 0, "dangling": 0, "len": 0})
        r["pieces"] += 1; r["bends"] += list(bends); r["non_octi"] += non_octi; r["dangling"] += dangling
        r["len"] += round(plen(P))
        if max(bends) > TH["bends_max"] or non_octi or dangling:
            bad.append("%s (bends %s, %d off-angle runs, %d dangling ends)" % (n, bends, non_octi, dangling))
    # two avenues on one run (one drawn on top of the other)
    from .city_avenues import shared
    avs = [(s.get("n"), polys[i]) for i, s in enumerate(M["streets"]) if s.get("d") and id(s) not in leg]
    for i in range(len(avs)):
        for j in range(i + 1, len(avs)):
            if avs[i][0] == avs[j][0]:
                continue
            sh = shared(avs[i][1], list(zip(avs[j][1], avs[j][1][1:])))
            if sh > BLOCK:
                bad.append("%s and %s share %.1f blocks" % (avs[i][0], avs[j][0], sh / BLOCK))
    st = "fail" if bad else "ok"
    return st, "%d avenues; %d break the rules%s" % (len(rows), len(bad), (": " + "; ".join(bad[:5])) if bad else ""), \
        {"avenues": rows, "bad": bad}


def c_transit(g, m, M):
    if not (g.get("transit") or {}).get("lines"):
        return "ok", "no transit", {}
    from .palace_transit_audit import audit, measure
    a = audit(g)
    probs = a.get("problems") or []
    st = measure(g, real=m.get("transit"), to_page=M["to_page"])      # turns per line, max stray from the real track
    num = ", ".join("%s %d turns%s" % (lid, r["turns"], " stray %.1f" % r["stray"] if "stray" in r else "")
                    for lid, r in st.items())
    return ("fail" if probs else "ok"), "%d transit problems (%s)" % (len(probs), num), {"problems": probs[:12], "lines": st}


def c_cut(g, m, M, blocks):
    tiles = g.get("tiles") or []
    tq = g.get("tq") or []
    if tq:
        cut, tot = sum(1 for q in tq if len(q) != 8), len(tq) + len(tiles)
    else:
        full = {(round((t[0] + t[2]) / 2), round((t[1] + t[3]) / 2)) for t in tiles}
        bl = blocks or []
        tot = len(bl)
        cut = sum(1 for b in bl if (round(b["x"]), round(b["y"])) not in full)
    sh = cut / max(1, tot)
    st = "fail" if sh > TH["cut_fail"] else "warn" if sh > TH["cut_warn"] else "ok"
    return st, "%d of %d blocks cut or open (%.1f%%)" % (cut, tot, 100 * sh), {"cut": cut, "total": tot, "share": round(sh, 3)}


def c_size(g, m, M, blocks):
    from .palace import pack
    kb = len(pack({"map": {k: v for k, v in g.items() if k not in ("blocks", "report", "doms", "seams")},
                   "blocks": blocks or []})) / 1024
    sc = M["sc"]
    km2 = m["W"] * m["H"] / 1e6 / (sc * sc)
    ratio = (kb / km2) / (BASE_KB / BASE_KM2)
    st = "fail" if ratio > TH["size_fail"] else "warn" if ratio > TH["size_warn"] else "ok"
    return st, "%dx%d px, %d streets, %.0f kB packed (%.2fx Philadelphia 1.9.78 per km²)" % (
        g["W"], g["H"], len(g.get("streets", [])), kb, ratio), {"W": g["W"], "H": g["H"], "kb": round(kb, 1),
                                                                 "ratio": round(ratio, 2)}


def c_overlap(g, m, M):
    clips = [(_dget(d, "id"), [tuple(q) for q in _dget(d, "clip")]) for d in M["doms"]
             if _dget(d, "clip") and not _dget(d, "legacy")]
    if len(clips) < 2:
        return "ok", "one page region", {}
    step = min(CW, CH) / 6
    bad = []
    for i in range(len(clips)):
        for j in range(i + 1, len(clips)):
            A, B = clips[i][1], clips[j][1]
            x0 = max(min(p[0] for p in A), min(p[0] for p in B)); x1 = min(max(p[0] for p in A), max(p[0] for p in B))
            y0 = max(min(p[1] for p in A), min(p[1] for p in B)); y1 = min(max(p[1] for p in A), max(p[1] for p in B))
            if x1 <= x0 or y1 <= y0:
                continue
            n = 0
            y = y0 + step / 2
            while y < y1:
                x = x0 + step / 2
                while x < x1:
                    if _inside((x, y), [A]) and _inside((x, y), [B]):
                        n += 1
                    x += step
                y += step
            ov = n * step * step / (CW * CH)
            if ov > TH["overlap_blocks"]:
                bad.append((clips[i][0], clips[j][0], round(ov, 2)))
    return ("fail" if bad else "ok"), "%d overlapping domain pairs" % len(bad), {"bad": bad}


def report(g, m, doms=None, seams=None, aliases=None, blocks=None) -> dict:
    """R10. aliases: {page landmark label: real name} (the brief's buildings), for matching landmarks."""
    blocks = blocks if blocks is not None else g.get("blocks")
    M = _model(g, m, doms, seams)
    checks, fail, warn = {}, [], []
    plan = [("domains", lambda: c_domains(g, m, M)), ("phantom", lambda: c_phantom(g, m, M)),
            ("displacement", lambda: c_displacement(g, m, M, aliases)), ("order", lambda: c_order(g, m, M)),
            ("side", lambda: c_side(g, m, M, blocks)), ("seam_fidelity", lambda: c_seam_fidelity(g, m, M)),
            ("tjoin", lambda: c_tjoin(g, m, M)), ("ends", lambda: c_ends(g, m, M)),
            ("cross_seam", lambda: c_cross_seam(g, m, M)), ("avenues", lambda: c_avenues(g, m, M)),
            ("transit", lambda: c_transit(g, m, M)), ("cut", lambda: c_cut(g, m, M, blocks)),
            ("size", lambda: c_size(g, m, M, blocks)), ("overlap", lambda: c_overlap(g, m, M))]
    for name, fn in plan:
        try:
            st, msg, data = fn()
        except Exception as e:          # a check that cannot run is itself a finding, never a crash of the build
            st, msg, data = "warn", "check could not run: %s: %s" % (type(e).__name__, e), {}
        checks[name] = {"status": st, "msg": msg, **({"data": data} if data else {})}
        if st == "fail":
            fail.append("%s: %s" % (name, msg))
        elif st == "warn":
            warn.append("%s: %s" % (name, msg))
    return {"checks": checks, "fail": fail, "warn": warn}


def summary(rep) -> str:
    """One line per check, for the QA scripts."""
    return "\n".join("%-14s %-4s %s" % (k, v["status"], v["msg"]) for k, v in rep["checks"].items())
