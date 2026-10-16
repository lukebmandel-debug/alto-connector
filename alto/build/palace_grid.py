"""The Mind Palace's city as an even grid (Luke's spec, 2026-10-09).

The real map (palace_map.build_map) decides only WHICH streets there are, in
what ORDER, and where each one really runs. The drawing is graph paper:

- every north–south street the city numbers (Front, 2nd … 49th) and its main
  ones (Broad) is a column; every named cross street is a row; columns and
  rows are evenly spaced, so every block is the same size;
- a street is drawn only where it really runs, but nothing starts or stops in
  the middle of nowhere: each end lands on the street it meets, and where it
  ends there it turns into it (a rounded corner, drawn by the page — the
  points carry the turn);
- the exceptions: the river is a smooth band (the streets that bridge it cross
  it, the others stop at it) and a few named diagonals (a parkway) are single
  clean lines between the intersections they join;
- railways follow the same mapping, smoothed; stations and landmarks are
  points on it.

grid(m, majors=(), diagonals=()) → a map dict the page draws (W, H, streets,
water, rails, stations, landmarks, majors) plus "grid": the tables that carry
a real point onto the grid (to_px uses them for district bounds), and the
blocks with their building lots (blocks(g)).
"""
from __future__ import annotations

import math
import re
from bisect import bisect_left

from .palace_river import rivers
from .palace_transit import snap as snap_transit

CW, CH = 240, 170          # one block, grid px: big enough that a building's number fits inside it
PAD = 110                  # margin around the grid
LEAD = 40                  # how far a turned end runs along the street it joins
SNAP_DEG = 25
# West of the Schuylkill the neighbourhood streets are residential (class 4) and the old rule
# (numbered, a main street, or class <= 2 / <= 3) left West and Southwest Philadelphia nearly
# empty. There, any named street long enough to read as a through street is a column or a row.
FILL_LON = -75.19          # the fill region: west of this longitude
FILL_MIN = 700.0           # px of street (about half a kilometre) before a residential street counts
_DIR = re.compile(r"^(North|South|East|West|N|S|E|W)\.?\s+(?=\S+\s)", re.I)
_NUM = re.compile(r"^(\d+)(st|nd|rd|th)\b", re.I)


def norm(name: str) -> str:
    """One name for one street: "South 15th Street" and "North 15th Street" are 15th Street."""
    return _DIR.sub("", str(name or "").strip())


def numbered(name: str) -> bool:
    n = norm(name)
    return bool(_NUM.match(n)) or n.lower().startswith("front ")


# ── geometry helpers ───────────────────────────────────────────────────────
def _pairs(flat):
    return [(flat[i], flat[i + 1]) for i in range(0, len(flat) - 1, 2)]


def _dp(pts, tol):
    if len(pts) < 3:
        return pts
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    best, bi = -1.0, 0
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        d = (abs(dy * (px - x0) - dx * (py - y0)) / L) if L else math.hypot(px - x0, py - y0)
        if d > best:
            best, bi = d, i
    if best <= tol:
        return [pts[0], pts[-1]]
    return _dp(pts[:bi + 1], tol)[:-1] + _dp(pts[bi:], tol)


def _chaikin(pts, n=2, closed=False):
    for _ in range(n):
        out = []
        m = len(pts)
        rng = range(m) if closed else range(m - 1)
        if not closed:
            out.append(pts[0])
        for i in rng:
            a, b = pts[i], pts[(i + 1) % m]
            out.append((a[0] * .75 + b[0] * .25, a[1] * .75 + b[1] * .25))
            out.append((a[0] * .25 + b[0] * .75, a[1] * .25 + b[1] * .75))
        if not closed:
            out.append(pts[-1])
        pts = out
    return pts


def _inside(pt, rings):
    """Even-odd point in polygon over several rings."""
    x, y = pt
    c = False
    for r in rings:
        n = len(r)
        for i in range(n):
            (x0, y0), (x1, y1) = r[i], r[(i + 1) % n]
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                c = not c
    return c


def grid_angle(m) -> float:
    sx = sy = 0.0
    for s in m.get("streets", []):
        if s.get("t") or s.get("k", 9) > 3:
            continue
        p = s["p"]
        for i in range(0, len(p) - 2, 2):
            L = math.hypot(p[i + 2] - p[i], p[i + 3] - p[i + 1])
            th = math.atan2(p[i + 3] - p[i + 1], p[i + 2] - p[i])
            sx += L * math.cos(4 * th); sy += L * math.sin(4 * th)
    return math.atan2(sy, sx) / 4 if (sx or sy) else 0.0


class Mapping:
    """Real map px → grid px: turn square to the street grid, then carry x and y
    through the columns' and rows' real positions (piecewise linear)."""

    def __init__(self, th, cx, cy, xr, xg, yr, yg):
        self.th, self.cx, self.cy = th, cx, cy
        self.xr, self.xg, self.yr, self.yg = xr, xg, yr, yg

    def turn(self, x, y):
        c, s = math.cos(-self.th), math.sin(-self.th)
        x, y = x - self.cx, y - self.cy
        return (x * c - y * s + self.cx, x * s + y * c + self.cy)

    @staticmethod
    def _interp(v, R, G, step):
        if not R:
            return v
        if v <= R[0]:
            return G[0] - (R[0] - v) / max(1e-6, (R[1] - R[0]) if len(R) > 1 else 1) * step
        if v >= R[-1]:
            return G[-1] + (v - R[-1]) / max(1e-6, (R[-1] - R[-2]) if len(R) > 1 else 1) * step
        i = bisect_left(R, v)
        r0, r1, g0, g1 = R[i - 1], R[i], G[i - 1], G[i]
        return g0 + (v - r0) / max(1e-9, r1 - r0) * (g1 - g0)

    def turned(self, tx, ty):
        return (self._interp(tx, self.xr, self.xg, CW), self._interp(ty, self.yr, self.yg, CH))

    def __call__(self, x, y):
        return self.turned(*self.turn(x, y))

    def tables(self):
        return {"t": round(self.th, 6), "cx": self.cx, "cy": self.cy,
                "xr": [round(v, 1) for v in self.xr], "xg": self.xg,
                "yr": [round(v, 1) for v in self.yr], "yg": self.yg}


def mapping_from(tables):
    return Mapping(tables["t"], tables["cx"], tables["cy"], tables["xr"], tables["xg"],
                   tables["yr"], tables["yg"])


# ── the grid ───────────────────────────────────────────────────────────────
def _lines(m, th, majors, diagonals):
    """Columns and rows from the real streets: [(norm name, position, spans,
    major?)] for each orientation, in real (turned) px; and the diagonals'
    real chains."""
    cx, cy = m["W"] / 2, m["H"] / 2
    c, s = math.cos(-th), math.sin(-th)

    def turn(x, y):
        x, y = x - cx, y - cy
        return (x * c - y * s + cx, x * s + y * c + cy)
    majors_n = {norm(x) for x in majors}
    diag_n = {norm(x) for x in diagonals}
    segs = {"v": {}, "h": {}}
    diag = {}
    dirlen: dict = {}          # each name's length running each way (h, v, d)
    bb, W0 = m.get("bbox"), m.get("W") or 1
    fill_x = ((FILL_LON - bb[1]) / (bb[3] - bb[1]) * W0) if bb and len(bb) == 4 and bb[3] > bb[1] else None
    fillonly: set = set()
    for st in m.get("streets", []):
        if st.get("t") or not st.get("n"):
            continue
        n = norm(st["n"])
        k = st.get("k", 9)
        P = _pairs(st["p"])
        fill = fill_x is not None and k <= 4 and bool(P) and sum(x for x, _ in P) / len(P) < fill_x
        pts = _dp([turn(x, y) for x, y in _pairs(st["p"])], 10)
        for a, b in zip(pts, pts[1:]):
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if L < 4:
                continue
            ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180
            kd = "h" if (ang < SNAP_DEG or ang > 180 - SNAP_DEG) else "v" if abs(ang - 90) < SNAP_DEG else "d"
            t3 = dirlen.setdefault(n, {"h": 0.0, "v": 0.0, "d": 0.0}); t3[kd] += L
            if n in diag_n:
                diag.setdefault(n, []).append((a, b))
                continue
            if kd == "v" and (numbered(n) or n in majors_n or k <= 2 or fill):
                segs["v"].setdefault(n, []).append((a, b, L, bool(st.get("b"))))
                if not (numbered(n) or n in majors_n or k <= 2):
                    fillonly.add(n)
            elif kd == "h" and (n in majors_n or k <= 3 or fill):
                segs["h"].setdefault(n, []).append((a, b, L, bool(st.get("b"))))
                if not (n in majors_n or k <= 3):
                    fillonly.add(n)
    out = {}
    for o in ("v", "h"):
        lines = []
        for n, ss in segs[o].items():
            # a street is a column (or a row) only if that is the way it mostly runs
            t3 = dirlen.get(n) or {}
            if t3.get(o, 0) < 0.6 * sum(t3.values()):
                continue
            # one line per stretch at about the same place (a name can be used twice in a city)
            items = sorted(((a[0] + b[0]) / 2 if o == "v" else (a[1] + b[1]) / 2, a, b, L, br) for a, b, L, br in ss)
            groups, cur = [], [items[0]]
            for it in items[1:]:
                if it[0] - cur[-1][0] > 700:
                    groups.append(cur); cur = []
                cur.append(it)
            groups.append(cur)
            for g in groups:
                tot = sum(it[3] for it in g)
                if tot < (FILL_MIN if n in fillonly and not numbered(n) else 380) and n not in majors_n:
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
                              "bridges": bridges})
        # two lines at (nearly) the same place are one (a divided road, two names for one street)
        lines.sort(key=lambda l: l["pos"])
        kept = []
        for l in lines:
            if kept and l["pos"] - kept[-1]["pos"] < 22:
                k = kept[-1]
                keep, drop = (k, l) if (k["major"], k["len"]) >= (l["major"], l["len"]) else (l, k)
                keep["spans"] = sorted(keep["spans"] + drop["spans"])
                keep["bridges"] += drop["bridges"]
                kept[-1] = keep
                continue
            kept.append(l)
        out[o] = kept
    return out, diag, turn


RIVER_W = 100               # the river: a very thick connecting line
LANDMARK_KEYS = ("name", "page")


def grid(m, majors=(), diagonals=(), lines=(), landmarks=(), parks=()) -> dict:
    """lines: the railways to draw, [{name, color?, stops: [station or landmark
    names]}] — straight, above ground, through their stops (they need not be
    real). landmarks: the landmark buildings, [{name, page?}] — each takes a
    whole block; `page` is what opening it shows ("index:<key>", "char:<id>",
    "node:<id>"). parks: names of parks to draw whatever their size (the
    big ones are drawn anyway) — palace_parks."""
    rail_specs, lm_specs = list(lines or ()), list(landmarks or ())
    th = grid_angle(m)
    L, diag, turn = _lines(m, th, majors, diagonals)
    cols, rows = L["v"], L["h"]
    xr = [c["pos"] for c in cols]
    yr = [r["pos"] for r in rows]
    xg = [PAD + i * CW for i in range(len(cols))]
    yg = [PAD + j * CH for j in range(len(rows))]
    mp = Mapping(th, m["W"] / 2, m["H"] / 2, xr, xg, yr, yg)
    W, H = int(xg[-1] + PAD) if xg else 800, int(yg[-1] + PAD) if yg else 600

    # the water in grid px — only to keep buildings off it; the river is drawn as a line
    water = []
    for r in m.get("water", []):
        pts = [mp(x, y) for x, y in _pairs(r)]
        a = sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(pts, pts[1:] + pts[:1])) / 2
        if abs(a) >= 3000:
            water.append(pts)

    def wet(p):
        return bool(water) and _inside(p, water)

    # spans onto the grid: each end lands on a crossing line that is there
    def g_spans(lines, o):
        res = []
        for l in lines:
            sp = []
            for lo, hi in l["spans"]:
                a = mp.turned(l["pos"], lo)[1] if o == "v" else mp.turned(lo, l["pos"])[0]
                b = mp.turned(l["pos"], hi)[1] if o == "v" else mp.turned(hi, l["pos"])[0]
                sp.append([a, b])
            br = []
            for lo, hi in l["bridges"]:
                a = mp.turned(l["pos"], lo)[1] if o == "v" else mp.turned(lo, l["pos"])[0]
                b = mp.turned(l["pos"], hi)[1] if o == "v" else mp.turned(hi, l["pos"])[0]
                br.append([min(a, b) - 20, max(a, b) + 20])
            res.append(sp); l["gbr"] = br
        return res
    csp, rsp = g_spans(cols, "v"), g_spans(rows, "h")

    def covers(spans, v, tol):
        return any(a - tol <= v <= b + tol for a, b in spans)

    def land(v, at, cross_pos, cross_spans, step):
        """The crossing line nearest v that is there at `at`: its index, or None."""
        best, bd = None, 1.7 * step
        for i, p in enumerate(cross_pos):
            d = abs(p - v)
            if d < bd and covers(cross_spans[i], at, step * .55):
                best, bd = i, d
        return best

    # ── the rivers: smooth bands (palace_river), each run off the glass at both ends ──
    river, W = rivers(m, mp, xg, yg, CW, CH, W, H)

    def river_between(o, at, a, b):
        n = max(2, int(abs(b - a) // 40))
        for k in range(n + 1):
            t = a + (b - a) * k / n
            p = (at, t) if o == "v" else (t, at)
            for rv in river:
                q = _pairs(rv["p"])
                if any(_segd(p, u, w) < rv["w"] / 2 + 8 for u, w in zip(q, q[1:])):
                    return True
        return False

    def complete(o, at, merged, cpos):
        """Graph paper: a street runs the whole grid, so no block is left open. The only breaks are the rivers
        (a street a river interrupts stays interrupted; the bridges are drawn separately)."""
        if not merged or not cpos:
            return merged
        res = [list(merged[0])]
        for seg in merged[1:]:
            prev = res[-1]
            if not river_between(o, at, prev[1], seg[0]):
                prev[1], prev[3] = seg[1], seg[3]
            else:
                res.append(list(seg))
        lo, hi = cpos[0], cpos[-1]
        if res[0][0] > lo + 1 and not river_between(o, at, lo, res[0][0]):
            res[0][0], res[0][2] = lo, 0
        if res[-1][1] < hi - 1 and not river_between(o, at, res[-1][1], hi):
            res[-1][1], res[-1][3] = hi, len(cpos) - 1
        return res

    streets = []
    ends = {"v": [], "h": []}
    for o, lines, spans, pos, cpos, cspans, step in (("v", cols, csp, xg, yg, rsp, CH), ("h", rows, rsp, yg, xg, csp, CW)):
        for li, l in enumerate(lines):
            at = pos[li]
            merged = []
            for a, b in sorted(spans[li]):
                sa = land(a, at, cpos, cspans, step)
                sb = land(b, at, cpos, cspans, step)
                ea = cpos[sa] if sa is not None else a
                eb = cpos[sb] if sb is not None else b
                if eb - ea < step * .5:
                    continue
                if merged and ea <= merged[-1][1] + 1:
                    merged[-1][1] = max(merged[-1][1], eb); merged[-1][3] = sb
                else:
                    merged.append([ea, eb, sa, sb])
            merged = complete(o, at, merged, cpos)
            spans[li] = [[a, b] for a, b, _, _ in merged]
            ends[o].append(merged)
    # draw: each span, with a turn at an end that joins a crossing line which
    # runs on past it (the turn goes the way that line runs further)
    for o, lines, pos, cpos, cspans in (("v", cols, xg, yg, rsp), ("h", rows, yg, xg, csp)):
        for li, l in enumerate(lines):
            at = pos[li]
            for a, b, sa, sb in ends[o][li]:
                def P(t, q=at):
                    return (q, t) if o == "v" else (t, q)

                def turn_at(si, t, inward):
                    if si is None:
                        return None
                    cs = cspans[si]
                    lo = min((x for x, y in cs if x - 2 <= at <= y + 2), default=at)
                    hi = max((y for x, y in cs if x - 2 <= at <= y + 2), default=at)
                    if hi - at < 1 and at - lo < 1:
                        return None
                    d = 1 if (hi - at) >= (at - lo) else -1
                    return (at + d * LEAD, t) if o == "v" else (t, at + d * LEAD)
                pts = [P(a), P(b)]
                # a turn only where the line truly ends here (not where it crosses on)
                ta = turn_at(sa, a, 1) if sa is not None else None
                tb = turn_at(sb, b, -1) if sb is not None else None
                if ta:
                    pts.insert(0, ta)
                if tb:
                    pts.append(tb)
                streets.append({"n": l["n"], "k": 0 if l["major"] else 1, "p": [round(v, 1) for q in pts for v in q]})
    # bridges: the parts of a line over the river, drawn on top of it
    over = []
    for o, lines, pos, spans in (("v", cols, xg, csp), ("h", rows, yg, rsp)):
        for li, l in enumerate(lines):
            for a, b in l.get("gbr") or []:
                for s0, s1 in spans[li]:
                    x0, x1 = max(a, s0), min(b, s1)
                    if x1 - x0 > 10:
                        p0 = (pos[li], x0) if o == "v" else (x0, pos[li])
                        p1 = (pos[li], x1) if o == "v" else (x1, pos[li])
                        over.append({"n": l["n"], "k": 0 if l["major"] else 1, "o": 1,
                                     "p": [round(v, 1) for v in p0 + p1]})
    # the diagonals: one clean line between the intersections nearest their ends
    def nearest_x(p):
        best, bd = None, 1e18
        for i, x in enumerate(xg):
            for j, y in enumerate(yg):
                if not (covers(csp[i], y, 4) and covers(rsp[j], x, 4)):
                    continue
                d = (x - p[0]) ** 2 + (y - p[1]) ** 2
                if d < bd:
                    best, bd = (x, y), d
        return best or p
    # the avenues a trolley runs on follow where they really lie (so its stops stand on them); the others are chords
    trolley_n = set()
    for ln_ in (m.get("transit") or {}).get("lines", []):
        if ln_.get("k") == "tram":
            for st_ in (m["transit"]).get("stops", []):
                trolley_n |= {norm(part) for part in st_["n"].split(" & ")}
    for n, ss in diag.items():
        ptsall = [mp.turned(*a) for a, b in ss] + [mp.turned(*b) for a, b in ss]
        if len(ptsall) < 2:
            continue
        # its two farthest-apart points are its ends
        best, bd = (ptsall[0], ptsall[1]), -1
        for i in range(len(ptsall)):
            for j in range(i + 1, len(ptsall)):
                d = (ptsall[i][0] - ptsall[j][0]) ** 2 + (ptsall[i][1] - ptsall[j][1]) ** 2
                if d > bd:
                    best, bd = (ptsall[i], ptsall[j]), d
        def chord():
            """A plain avenue: the chord between the two intersections nearest its ends."""
            a, b = nearest_x(best[0]), nearest_x(best[1])
            if a == b:
                return
            dx, dy = b[0] - a[0], b[1] - a[1]
            la = (a[0] - math.copysign(LEAD, dx), a[1]) if abs(dx) >= abs(dy) else (a[0], a[1] - math.copysign(LEAD, dy))
            lb = (b[0] + math.copysign(LEAD, dx), b[1]) if abs(dx) >= abs(dy) else (b[0], b[1] + math.copysign(LEAD, dy))
            streets.append({"n": n, "k": 0, "d": 1, "p": [round(v, 1) for q in (la, a, b, lb) for v in q]})
        if n not in trolley_n:
            chord()
            continue
        # the avenue follows where its real stretches lie (mapped onto the grid), as one clean line: a few gentle
        # bends at most. Each end lands on the nearest intersection when one is within a block and a half; an avenue
        # that runs on past the drawn streets (a trolley avenue out through the south-west) keeps its own end.
        # (what it follows: the stops of its trolleys, which stand where the trolley really runs, when there are enough)
        cpts = [mp(st_["x"], st_["y"]) for st_ in m["transit"]["stops"]
                if n in {norm(part) for part in st_["n"].split(" & ")}]
        if len(cpts) >= 3:
            ptsall = cpts
            e0, e1, bd = cpts[0], cpts[1], -1
            for i in range(len(cpts)):
                for j in range(i + 1, len(cpts)):
                    d = (cpts[i][0] - cpts[j][0]) ** 2 + (cpts[i][1] - cpts[j][1]) ** 2
                    if d > bd:
                        e0, e1, bd = cpts[i], cpts[j], d
            for q in best:                      # the street's own end carries on past the last stop (to where it meets the grid)
                d0, d1, dd = math.dist(q, e0), math.dist(q, e1), math.dist(e0, e1)
                if min(d0, d1) <= 800:
                    if d0 < d1 and d1 > dd:
                        e0 = q
                    elif d1 <= d0 and d0 > dd:
                        e1 = q
        else:
            e0, e1 = best
        ux, uy = e1[0] - e0[0], e1[1] - e0[1]
        ul = math.hypot(ux, uy) or 1.0
        ux, uy = ux / ul, uy / ul
        bins = {}
        for p_ in ptsall:
            tt = (p_[0] - e0[0]) * ux + (p_[1] - e0[1]) * uy
            oo = (p_[1] - e0[1]) * ux - (p_[0] - e0[0]) * uy
            bins.setdefault(int(tt // 260), []).append((tt, oo))
        curve = [(0.0, 0.0)] + [(sum(q[0] for q in v) / len(v), sum(q[1] for q in v) / len(v))
                                for _, v in sorted(bins.items())] + [(ul, 0.0)]
        mid = [(e0[0] + ux * tt - uy * oo, e0[1] + uy * tt + ux * oo) for tt, oo in curve]
        mid = _dp([e0] + mid[1:-1] + [e1], 55)

        def end_at(q, other):
            q = (min(max(q[0], PAD), xg[-1]), min(max(q[1], PAD), yg[-1]))
            x_ = nearest_x(q)
            return (x_, True) if math.hypot(x_[0] - q[0], x_[1] - q[1]) <= 1.5 * CW else (q, False)
        (a, ja), (b, jb) = end_at(mid[0], mid[1]), end_at(mid[-1], mid[-2])
        if a == b or not (ja or jb):             # joined to the grid at neither end: it would hang in the void
            chord()
            continue
        path = [a] + mid[1:-1] + [b]
        # it joins the grid by turning out of a street at each end (leads along the grid)
        dx, dy = path[1][0] - a[0], path[1][1] - a[1]
        ex, ey = b[0] - path[-2][0], b[1] - path[-2][1]
        la = (a[0] - math.copysign(LEAD, dx), a[1]) if abs(dx) >= abs(dy) else (a[0], a[1] - math.copysign(LEAD, dy))
        lb = (b[0] + math.copysign(LEAD, ex), b[1]) if abs(ex) >= abs(ey) else (b[0], b[1] + math.copysign(LEAD, ey))
        pts_ = ([la] if ja else []) + path + ([lb] if jb else [])
        streets.append({"n": n, "k": 0, "d": 1, "j": [int(ja), int(jb)], "p": [round(v, 1) for q in pts_ for v in q]})


    over = []
    for o, lines_, pos_, spans_ in (("v", cols, xg, csp), ("h", rows, yg, rsp)):
        for li, l in enumerate(lines_):
            for s0, s1 in spans_[li]:
                a = (pos_[li], s0) if o == "v" else (s0, pos_[li])
                b = (pos_[li], s1) if o == "v" else (s1, pos_[li])
                done = []
                for rv in river:
                    q = _pairs(rv["p"])
                    for c, d in zip(q, q[1:]):
                        hit = _xing(a, b, c, d)
                        if hit is None or any(math.dist(hit, h_) < 30 for h_ in done):
                            continue
                        done.append(hit)
                        # a river crossed on the slant is crossed over more of the street
                        rl = math.dist(c, d) or 1.0
                        sin = abs((d[0] - c[0]) / rl) if o == "v" else abs((d[1] - c[1]) / rl)
                        half = rv["w"] / 2 / max(.5, sin) + 22
                        p0 = (hit[0], hit[1] - half) if o == "v" else (hit[0] - half, hit[1])
                        p1 = (hit[0], hit[1] + half) if o == "v" else (hit[0] + half, hit[1])
                        over.append({"n": l["n"], "k": 0 if l["major"] else 1, "o": 1,
                                     "p": [round(v, 1) for v in p0 + p1]})

    # a bridge over the wide river, from the east end of the street it leaves to the far side
    bridge_names = set()
    for br in (m.get("bank") or {}).get("bridges", []):
        gx, gy = mp(*br["at"])
        best = None
        for j, y in enumerate(yg):
            if rsp[j] and abs(y - gy) < CH * 1.1:
                e = max(b_ for a_, b_ in rsp[j])
                if e >= xg[-1] - CW * 4 and (best is None or abs(y - gy) < best[0]):
                    best = (abs(y - gy), e, y)
        if best:
            over.append({"n": br["n"], "k": 0, "o": 1, "br": 1, "p": [round(best[1], 1), round(best[2], 1), W + 50, round(best[2], 1)]})
            bridge_names.add(norm(br["n"]))

    def near_river(p, extra=0):
        for rv in river:
            q = _pairs(rv["p"])
            for a, b in zip(q, q[1:]):
                if _segd(p, a, b) < rv["w"] / 2 + extra:
                    return True
        return False

    # ── the railways: straight, above ground, through their stops ──
    def find(name):
        nl = name.lower()
        for coll in (m.get("stations", []), m.get("landmarks", [])):
            for x in coll:
                if x.get("n", "").lower() == nl:
                    return x
        for coll in (m.get("stations", []), m.get("landmarks", [])):
            for x in coll:
                if nl in x.get("n", "").lower() or x.get("n", "").lower() in nl:
                    return x
        return None
    rails, stations = [], []
    for ln in rail_specs:
        stops = []
        for nm in ln.get("stops") or []:
            f = find(nm)
            if f:
                gx, gy = mp(f["x"], f["y"])
                stops.append((nm, gx, gy))
        if len(stops) < 2:
            continue
        ys_ = sorted(y for _, _, y in stops)
        my = ys_[len(ys_) // 2]
        j = max(0, min(len(yg) - 2, bisect_left(yg, my) - 1))
        y = (yg[j] + yg[j + 1]) / 2          # it runs down the middle of its blocks, between the streets
        xs_ = [x for _, x, _ in stops]
        rails.append({"n": ln.get("name") or "", "c": ln.get("color") or "", "k": "rail",
                      "p": [round(min(xs_), 1), round(y, 1), round(max(xs_), 1), round(y, 1)]})
        for nm, x, _ in stops:
            stations.append({"n": nm, "x": round(x, 1), "y": round(y, 1), "k": "rail", "hub": 1})
    rail_y = {r["p"][1] for r in rails}

    # ── landmark buildings: each takes the blocks its real footprint covers
    #    (City Hall the whole square it stands in, streets and all); one with
    #    no outline takes the block it stands in ──
    lms = []
    from .palace_towers import tower_key
    for spec in lm_specs:
        f = find(spec.get("name") or "")
        if not f:
            continue
        rings = [q for q in (f.get("r") or []) if q]
        if rings:
            P = [mp(x, y) for q in rings for x, y in _pairs(q)]
            gx0, gx1 = min(p[0] for p in P), max(p[0] for p in P)
            gy0, gy1 = min(p[1] for p in P), max(p[1] for p in P)
        else:
            gx0 = gx1 = mp(f["x"], f["y"])[0]
            gy0 = gy1 = mp(f["x"], f["y"])[1]
        # the cells it covers; a sliver under a fifth of a block does not count
        i0 = max(0, int(math.floor((gx0 - PAD) / CW + .2)))
        i1 = min(len(xg) - 1, int(math.ceil((gx1 - PAD) / CW - .2)))
        j0 = max(0, int(math.floor((gy0 - PAD) / CH + .2)))
        j1 = min(len(yg) - 1, int(math.ceil((gy1 - PAD) / CH - .2)))
        if i1 <= i0:
            i0 = max(0, min(len(xg) - 2, int((((gx0 + gx1) / 2) - PAD) // CW))); i1 = i0 + 1
        if j1 <= j0:
            j0 = max(0, min(len(yg) - 2, int((((gy0 + gy1) / 2) - PAD) // CH))); j1 = j0 + 1
        cells = {(i, j) for i in range(i0, i1) for j in range(j0, j1)}
        if any(cells & l_["cells"] for l_ in lms):
            # one cell wide and taken (two towers on one block of the grid): the free neighbour nearest its real spot
            if len(cells) == 1 and tower_key(spec.get("name") or ""):
                cx_, cy_ = (gx0 + gx1) / 2, (gy0 + gy1) / 2
                (ci, cj), = cells
                near_ = sorted(((ci + di, cj + dj) for di, dj in ((0, 1), (0, -1), (1, 0), (-1, 0))
                                if 0 <= ci + di < len(xg) - 1 and 0 <= cj + dj < len(yg) - 1),
                               key=lambda c: (cx_ - (xg[c[0]] + xg[c[0] + 1]) / 2) ** 2 + (cy_ - (yg[c[1]] + yg[c[1] + 1]) / 2) ** 2)
                free_ = [c for c in near_ if not any(c in l_["cells"] for l_ in lms)]
                if not free_:
                    continue
                i0, j0 = free_[0]; i1, j1 = i0 + 1, j0 + 1
                cells = {(i0, j0)}
            else:
                continue
        lms.append({"n": spec.get("label") or spec["name"], "page": spec.get("page") or "", "cells": cells,
                    "cell": [i0, j0], "box": [xg[i0], yg[j0], xg[i1], yg[j1]]})
    lm_all = set().union(*[l_["cells"] for l_ in lms]) if lms else set()

    def in_lm(x0, y0, x1, y1):
        """An edge strictly inside a landmark's footprint (not on its outline)."""
        for l_ in lms:
            bx0, by0, bx1, by1 = l_["box"]
            if bx0 <= min(x0, x1) and max(x0, x1) <= bx1 and by0 <= min(y0, y1) and max(y0, y1) <= by1:
                if (x0 == x1 and bx0 < x0 < bx1) or (y0 == y1 and by0 < y0 < by1):
                    return True
        return False

    # ── the drawing: every block a rounded tile (each street curves at every
    #    intersection); edges no block uses drawn on their own ──
    def has(spans, v):
        return any(a - 2 <= v <= b + 2 for a, b in spans)
    tiles, used = [], set()
    for j in range(len(yg) - 1):
        for i in range(len(xg) - 1):
            mx, my = (xg[i] + xg[i + 1]) / 2, (yg[j] + yg[j + 1]) / 2
            if (i, j) in lm_all:
                continue
            if has(csp[i], my) and has(csp[i + 1], my) and has(rsp[j], mx) and has(rsp[j + 1], mx):
                tiles.append([xg[i], yg[j], xg[i + 1], yg[j + 1]])
                used |= {("v", i, j), ("v", i + 1, j), ("h", j, i), ("h", j + 1, i)}
    edges = []
    for i in range(len(xg)):
        for j in range(len(yg) - 1):
            if ("v", i, j) not in used and has(csp[i], (yg[j] + yg[j + 1]) / 2) and not in_lm(xg[i], yg[j], xg[i], yg[j + 1]):
                edges.append([xg[i], yg[j], xg[i], yg[j + 1]])
    for j in range(len(yg)):
        for i in range(len(xg) - 1):
            if ("h", j, i) not in used and has(rsp[j], (xg[i] + xg[i + 1]) / 2) and not in_lm(xg[i], yg[j], xg[i + 1], yg[j]):
                edges.append([xg[i], yg[j], xg[i + 1], yg[j]])

    # a transit line runs along a street: wherever its track follows a grid line that no street was
    # drawn on (the real street was a diagonal avenue or a lane the grid leaves out), the line gets its
    # street, so no line crosses a void and no stop hangs in the middle of nowhere
    # (the glass the page draws is every block's outline plus these edges; the trolleys are routed along both)
    drawn = {(min(a, c), min(b, d), max(a, c), max(b, d)) for a, b, c, d in edges}
    for a, b, c, d in tiles:
        drawn |= {(a, b, c, b), (a, d, c, d), (a, b, a, d), (c, b, c, d)}
    transit = snap_transit(m.get("transit"), mp, xg, yg, W, H, streets=streets, edges_=sorted(drawn))
    have = {(round(e[0]), round(e[1]), round(e[2]), round(e[3])) for e in edges}
    new_streets = []
    for i0, j0, i1, j1 in transit.pop("ge", []):
        x0, y0, x1, y1 = xg[i0], yg[j0], xg[i1], yg[j1]
        key = ("v", i0, min(j0, j1)) if x0 == x1 else ("h", j0, min(i0, i1))
        if key in used or (round(min(x0, x1)), round(min(y0, y1)), round(max(x0, x1)), round(max(y0, y1))) in have:
            continue
        if in_lm(x0, y0, x1, y1):
            continue
        used.add(key)
        edges.append([min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)])
        new_streets.append([min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)])
        have.add((round(min(x0, x1)), round(min(y0, y1)), round(max(x0, x1)), round(max(y0, y1))))

    landmarks_out = [{"n": l_["n"], "x": round((l_["box"][0] + l_["box"][2]) / 2, 1),
                      "y": round((l_["box"][1] + l_["box"][3]) / 2, 1), "r": [], "box": l_["box"],
                      "page": l_["page"]} for l_ in lms]
    from .palace_parks import pick as pick_parks
    park_cells = pick_parks(m, mp, xg, yg, parks or (), lm_all, lambda p: near_river(p, 0))
    g = {k: v for k, v in m.items() if k not in ("streets", "water", "rivers", "rails", "trails", "stations",
                                                 "landmarks", "parks", "W", "H", "majors", "transit")}
    g.update(W=W, H=H, streets=streets + over, rails=rails, trails=[], parks=park_cells, stations=stations,
             landmarks=landmarks_out, rivers=[], river=river, water=[], tiles=tiles, edges=edges,
             majors=sorted({norm(x) for x in majors} | {norm(s_["n"]) for s_ in streets if s_["k"] == 0} | bridge_names),
             grid=mp.tables(), cols=[c["n"] for c in cols], rows=[r["n"] for r in rows])
    lm_cells = lm_all
    if transit.get("lines"):
        transit["new"] = new_streets                      # the streets drawn only because a line runs there (the audit counts them)
    g["transit"] = transit
    g["blocks"] = blocks(g, csp, rsp, xg, yg, water, lambda p: near_river(p, 6), lm_cells, rail_y)
    return g


def _xing(a, b, c, d):
    """Where segment ab crosses segment cd, or None."""
    d1 = (b[0] - a[0]) * (d[1] - c[1]) - (b[1] - a[1]) * (d[0] - c[0])
    if abs(d1) < 1e-9:
        return None
    t = ((c[0] - a[0]) * (d[1] - c[1]) - (c[1] - a[1]) * (d[0] - c[0])) / d1
    u = ((c[0] - a[0]) * (b[1] - a[1]) - (c[1] - a[1]) * (b[0] - a[0])) / d1
    if 0 <= t <= 1 and 0 <= u <= 1:
        return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
    return None


def _segd(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy or 1e-9
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(a[0] + t * dx - p[0], a[1] + t * dy - p[1])


def blocks(g, csp, rsp, xg, yg, water, wet=None, lm_cells=(), rail_y=()):
    """Every block of the grid with its lots: buildings stand along its street
    fronts, two along the top and two along the bottom, like row houses. A block
    is one with streets on at least three sides, not in the river."""
    out = []
    gap = 12
    h = (CH - 3 * gap - 30) / 2        # two fronts of row houses; the middle of the block stays open
    w = (CW - 3 * gap) / 2

    def edge(spans, v):
        return any(a - 2 <= v <= b + 2 for a, b in spans)
    for j in range(len(yg) - 1):
        for i in range(len(xg) - 1):
            x0, x1, y0, y1 = xg[i], xg[i + 1], yg[j], yg[j + 1]
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            sides = (edge(csp[i], my) + edge(csp[i + 1], my) + edge(rsp[j], mx) + edge(rsp[j + 1], mx))
            if sides < 3 or (water and _inside((mx, my), water)) or (i, j) in lm_cells:
                continue
            lots = []
            for yy in (y0 + gap + h / 2, y1 - gap - h / 2):
                for xx in (x0 + gap + w / 2, x1 - gap - w / 2):
                    if (water and _inside((xx, yy), water)) or (wet and wet((xx, yy))):
                        continue
                    lots.append([round(xx, 1), round(yy, 1), round(w, 1), h, 0])
            if lots:
                out.append({"x": round(mx, 1), "y": round(my, 1), "lots": lots})
    out.sort(key=lambda b: (b["y"], b["x"]))
    for k, b in enumerate(out):
        b["id"] = k
    return out
