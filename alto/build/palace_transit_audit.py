"""An audit of the palace's drawn transit (the `map.transit` of a palace bundle, grid px).

    audit(m, table=None, real=None, to_page=None) -> {"lines": {id: report}, "problems": [str]}
    picture(m) -> {"stops": [...], "runs": [...], "track": px, "ok": bool}     the finished picture, any city

It is city-generic: what a line's real route is comes from data (the stop order of the OSM route relations: the drawn
line's own branches `b`, and, when the raw transit `real` of palace_map is passed, its branches before snapping), and
the Philadelphia tables below (ROUTE, BRANCH_STREETS, RIVER_OK, ONE_PIECE) are one city's extra checks (`table`,
PHILADELPHIA by default for a Philadelphia bundle, `{}` for none).

It reads what the page will draw and says what is wrong with it: a stop with no
track under it, a stop its line does not list (or the other way round), track
with no stop on it (a stub past the last stop, a floating piece), a line that
falls into several pieces, a line that crosses a river it has no business
crossing (only a tunnel or a bridge may), consecutive stops too far apart, and
a line that does not run the stops of its real route in order. The test and
$KIT/audit_transit.py both run it on the Civil Procedure bundle; the build
itself (palace_transit.snap) is made to pass it.
"""
from __future__ import annotations

import math

TOL = 3.6                # px: a stop is on its line when it is within this of its track (a dot shared by two lanes 7 px apart sits between them)
BLOCK = 205.0            # px: about one block of the grid (a column step is 240, a row step 170)
STUB_BLOCKS = 3.0        # track left standing past a line's last stop, in blocks
GAP_PX = {"default": 7000.0, "rr": 14000.0, "trl": 4000.0}   # consecutive stops of a ride, |dx| + |dy| in grid px (a mile is about 4000)
# the rivers a line may cross (a tunnel or a bridge), and how many times at most
RIVER_OK = {"mfl": {"Schuylkill": 1}, "rr": {"Schuylkill": 1}, "trl": {"Schuylkill": 1}, "pat": {"Delaware": 1}}
# the stops of each line's real route, in order from one end (a subsequence of the drawn ride, either way round)
ROUTE = {
    "mfl": ["Allegheny", "Huntingdon", "Girard", "Spring Garden", "2nd", "5th", "8th", "11th", "13th", "15th",
            "30th", "34th", "40th", "46th", "52nd", "56th", "60th"],
    "bsl": ["NRG", "Oregon", "Snyder", "Tasker", "Ellsworth", "Lombard", "Walnut", "City Hall", "Race",
            "Spring Garden", "Fairmount", "Girard", "Cecil", "Susquehanna", "North Philadelphia", "Allegheny"],
    "pat": ["15th", "12th", "9th", "8th", "Franklin Square", "City Hall", "Broadway"],       # Ferry Avenue and beyond lie off the drawn city
    "rr": ["Jefferson", "Suburban", "30th Street", "49th", "Angora"],
}
# the trolleys (10 Lancaster, 11 Woodland, 13 Chester, 34 Baltimore, 36 Elmwood): five branches, each runs its own street
# out to the subway-surface portal and then the Market Street tunnel in order, and no branch is another's stops
BRANCH_STREETS = ("Lancaster", "Woodland", "Chester", "Baltimore")   # (the Elmwood trolley runs out the Woodland stops; its own street has no drawn street to join)
TUNNEL = ["33rd", "30th", "22nd", "19th", "15th", "13th"]
ONE_PIECE = ("mfl", "bsl", "pat", "rr")          # lines that must be one connected track
STREET_TOL = 8.0         # px: a surface line's track (and its stops) must lie on a drawn street this close (two lanes sit 3.5 px either side of one street)
STREET_STEP = 20.0       # px: the track is sampled this often
INVENTED_MAX = 60.0      # px of surface track that may lie on a street the grid drew only for the line (none, bar a lane jog)
RUN_MIN = 40.0           # px: an uncovered run shorter than this (a lane jog at a corner) is not reported
SURFACE = ("tram",)      # kinds of line that run ON streets (a subway, an el, PATCO and Regional Rail are grade separated)
PHILADELPHIA = {"route": ROUTE, "branch_streets": BRANCH_STREETS, "tunnel": TUNNEL, "river_ok": RIVER_OK,
                "one_piece": ONE_PIECE, "branch_line": "trl"}
PIC_STEP = 10.0          # px: the finished picture's track is sampled this often
ANG_TOL = 1.5            # degrees: a grade-separated run is on its domain's axes or diagonals to within this
CW_, CH_ = 240.0, 170.0  # the page block (palace_grid.CW, CH) when a domain does not say


def _seg_d(x, y, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy or 1e-9
    t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
    return math.hypot(ax + t * dx - x, ay + t * dy - y), t


def _near(polys, x, y):
    """(distance, polyline index, arclength) of the point on the track nearest (x, y)."""
    best = (1e18, -1, 0.0)
    for pi, f in enumerate(polys):
        run = 0.0
        for k in range(0, len(f) - 3, 2):
            d, t = _seg_d(x, y, f[k], f[k + 1], f[k + 2], f[k + 3])
            L = math.hypot(f[k + 2] - f[k], f[k + 3] - f[k + 1])
            if d < best[0]:
                best = (d, pi, run + t * L)
            run += L
    return best


def _length(f):
    return sum(math.hypot(f[k + 2] - f[k], f[k + 3] - f[k + 1]) for k in range(0, len(f) - 3, 2))


def _pieces(polys):
    """Connected pieces of a line's track: a list of sets of polyline indexes."""
    par = list(range(len(polys)))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    for i, f in enumerate(polys):
        for j, g in enumerate(polys):
            if i == j:
                continue
            for e in ((f[0], f[1]), (f[-2], f[-1])):
                if _near([g], e[0], e[1])[0] <= 1.5:
                    par[find(i)] = find(j)
    out = {}
    for i in range(len(polys)):
        out.setdefault(find(i), set()).add(i)
    return list(out.values())


def _cross(a, b, c, d):
    def o(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return o(a, b, c) * o(a, b, d) < 0 and o(c, d, a) * o(c, d, b) < 0


def _river_crossings(polys, rivers):
    """{river name: number of places the line's track crosses the river's centre line}."""
    out = {}
    for rv in rivers:
        rp = rv["p"]
        hits = []
        for f in polys:
            for k in range(0, len(f) - 3, 2):
                a, b = (f[k], f[k + 1]), (f[k + 2], f[k + 3])
                for q in range(0, len(rp) - 3, 2):
                    if _cross(a, b, (rp[q], rp[q + 1]), (rp[q + 2], rp[q + 3])):
                        hits.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
        merged = []
        for h in hits:
            if not any(math.hypot(h[0] - g[0], h[1] - g[1]) < 150 for g in merged):
                merged.append(h)
        key = rv["n"].replace(" River", "")
        out[key] = out.get(key, 0) + len(merged)
    return out


def drawn_segments(m, invented=True):
    """Every street piece the page draws: each block's outline (tiles), the loose edges, the diagonal avenues and the
    bridges over the river. The named `streets` that are not diagonals or bridges are not drawn (only the tiles and edges are)."""
    segs = []
    for a, b, c, d in m.get("tiles", []):
        segs += [(a, b, c, b), (a, d, c, d), (a, b, a, d), (c, b, c, d)]
    segs += [tuple(e) for e in m.get("edges", [])]
    if not invented:                                    # only the streets the grid has of itself
        new = {tuple(e) for e in (m.get("transit") or {}).get("new", [])}
        segs = [sg for sg in segs if tuple(sg) not in new]
    for st in m.get("streets", []):
        if st.get("d") or st.get("o") or st.get("L") or st.get("sm"):
            p = st["p"]
            segs += [(p[k], p[k + 1], p[k + 2], p[k + 3]) for k in range(0, len(p) - 3, 2)]
    for f in m.get("tq", []):                           # engine v2: polygon tiles (a tilted domain's blocks, cut blocks)
        r = [(f[k], f[k + 1]) for k in range(0, len(f) - 1, 2)]
        segs += [(a[0], a[1], b[0], b[1]) for a, b in zip(r, r[1:] + r[:1]) if a != b]
    for f in m.get("te", []):                           # engine v2: loose edges of tilted domains
        segs += [(f[k], f[k + 1], f[k + 2], f[k + 3]) for k in range(0, len(f) - 3, 2)]
    return segs


class _Streets:
    def __init__(self, segs, cell=120.0):
        self.cell, self.grid = cell, {}
        for sg in segs:
            x0, x1 = sorted((sg[0], sg[2]))
            y0, y1 = sorted((sg[1], sg[3]))
            for i in range(int(x0 // cell) - 1, int(x1 // cell) + 2):
                for j in range(int(y0 // cell) - 1, int(y1 // cell) + 2):
                    self.grid.setdefault((i, j), []).append(sg)

    def dist(self, x, y):
        best = 1e18
        for ax, ay, bx, by in self.grid.get((int(x // self.cell), int(y // self.cell)), ()):
            d, _ = _seg_d(x, y, ax, ay, bx, by)
            if d < best:
                best = d
        return best


def _invented(m):
    """Segments of streets the grid drew only because a line ran there (palace_grid records them in transit['new'])."""
    return [tuple(e) for e in (m.get("transit") or {}).get("new", [])]


def street_cover(m, tol=STREET_TOL, step=STREET_STEP):
    """For every surface line: the runs of its track with no drawn street under them and the stops with none under them.
    -> {line id: {"track": px, "runs": [(length, x0, y0, x1, y1)], "stops": [(name, x, y, distance)]}}"""
    tr = m.get("transit") or {}
    st = _Streets(drawn_segments(m))
    inv = _Streets(_invented(m))
    own = _Streets(drawn_segments(m, invented=False))
    out = {}
    stops_ = tr.get("stops", [])
    for ln in tr.get("lines", []):
        if ln.get("k") not in SURFACE:
            continue
        runs, total, borrowed = [], 0.0, 0.0
        tun = _Streets([(u[0], u[1], u[2], u[3]) for u in ln.get("u", [])])    # a tunnel runs under no street
        under = {si for si in ln["s"] if " & " not in stops_[si]["n"]} if ln.get("u") else set()
        for f in ln["p"]:
            cur = None                                  # [start point, end point, length]
            for k in range(0, len(f) - 3, 2):
                ax, ay, bx, by = f[k:k + 4]
                L = math.hypot(bx - ax, by - ay)
                total += L
                n = max(1, int(L // step))
                for i in range(n + 1):
                    x, y = ax + (bx - ax) * i / n, ay + (by - ay) * i / n
                    if inv.grid and inv.dist(x, y) <= tol and own.dist(x, y) > tol:
                        borrowed += L / n               # a street invented for the trolley: not a street
                    if st.dist(x, y) > tol and not (tun.grid and tun.dist(x, y) <= 1.5):
                        if cur is None:
                            cur = [(x, y), (x, y), 0.0]
                        else:
                            cur[2] += math.hypot(x - cur[1][0], y - cur[1][1])
                            cur[1] = (x, y)
                    elif cur is not None:
                        runs.append(cur); cur = None
            if cur is not None:
                runs.append(cur)
        bad = []
        for si in ln["s"]:
            s = tr["stops"][si]
            d = st.dist(s["x"], s["y"])
            if d > tol and si not in under:
                bad.append((s["n"], round(s["x"]), round(s["y"]), round(d, 1)))
        out[ln["id"]] = {"track": round(total),
                         "runs": [(round(r[2]), round(r[0][0]), round(r[0][1]), round(r[1][0]), round(r[1][1]))
                                  for r in runs if r[2] >= RUN_MIN],
                         "stops": bad, "invented": round(borrowed),
                         "all_runs": len(runs)}
    return out


def _subseq(want, names):
    i = 0
    for n in names:
        if i < len(want) and want[i].lower() in n.lower():
            i += 1
    return i


def _philly(m):
    pl = m.get("place")
    return not pl or "philadelphia" in str(pl).lower()


def audit(m, table=None, real=None, to_page=None) -> dict:
    """table: one city's extra checks (PHILADELPHIA, or {}); None picks PHILADELPHIA for a Philadelphia bundle (or one
    that names no place). real: palace_map's raw transit ({lines: [{id, w, s, b}], stops}) for the checks against the
    real routes (order, lost branches, river crossings); to_page: real px -> page px (default: the bundle's grid tables)."""
    if table is None:
        table = PHILADELPHIA if _philly(m) else {}
    ROUTE_, RIVER_OK_, ONE_PIECE_ = table.get("route", {}), table.get("river_ok", {}), table.get("one_piece", ())
    tr = m.get("transit") or {}
    stops = tr.get("stops", [])
    rivers = m.get("river") or []
    problems, lines = [], {}
    cover = street_cover(m)
    pic = picture(m)
    raw = {ln["id"]: ln for ln in (real or {}).get("lines", [])}
    if real and to_page is None and m.get("grid"):
        from .palace_grid import mapping_from
        to_page = mapping_from(m["grid"])
    in_line = {i: [] for i in range(len(stops))}
    for ln in tr.get("lines", []):
        lid = ln["id"]
        polys = ln["p"]
        rep = {"n": ln["n"], "polys": len(polys), "length": round(sum(_length(f) for f in polys)),
               "span": None, "stops": [], "issues": []}
        lines[lid] = rep
        iss = rep["issues"]
        if not polys:
            iss.append("no track drawn")
            continue
        xs = [v for f in polys for v in f[0::2]]
        ys = [v for f in polys for v in f[1::2]]
        rep["span"] = [round(min(xs)), round(min(ys)), round(max(xs)), round(max(ys))]
        order = ln["s"]
        names = []
        near = []                                   # per listed stop: (distance, polyline, arclength)
        for si in order:
            s = stops[si]
            in_line[si].append(lid)
            d, pi, arc = _near(polys, s["x"], s["y"])
            near.append((d, pi, arc))
            names.append(s["n"])
            rep["stops"].append((s["n"], round(s["x"]), round(s["y"]), round(d, 1)))
            if lid not in s["l"]:
                iss.append("stop %r is in the line's ride but does not list the line" % s["n"])
            if d > TOL:
                iss.append("stop %r is %.1f px from the line's track" % (s["n"], d))
        # the stops that list this line must be in its ride
        for si, s in enumerate(stops):
            if lid in s["l"] and si not in order:
                iss.append("stop %r lists the line but is not in its ride" % s["n"])
        # pieces: one connected track (some lines), none without a stop on it
        pieces = _pieces(polys)
        on_piece = [set() for _ in pieces]
        for k, (d, pi, arc) in enumerate(near):
            if d <= TOL:
                for q, pc in enumerate(pieces):
                    if pi in pc:
                        on_piece[q].add(k)
        rl = raw.get(lid)
        one = lid in ONE_PIECE_ or (rl is not None and ln.get("k") not in SURFACE and len(rl.get("b") or [rl["s"]]) <= 1)
        if one and len(pieces) > 1:
            iss.append("the track falls into %d pieces" % len(pieces))
        for q, pc in enumerate(pieces):
            if len(on_piece[q]) == 0:
                iss.append("a piece of track (%d px) has no stop on it" % sum(_length(polys[i]) for i in pc))
        # stubs past the last stop; long stretches with no stop
        for pi, f in enumerate(polys):
            L = _length(f)
            if L <= 0:
                continue
            arcs = sorted(arc for (d, p_, arc) in near if p_ == pi and d <= TOL)
            free = []
            for e, at in (((f[0], f[1]), 0.0), ((f[-2], f[-1]), L)):
                joined = any(_near([g], e[0], e[1])[0] <= 1.5 for gi, g in enumerate(polys) if gi != pi)
                if not joined:
                    free.append(at)
            if not arcs:
                continue
            for at in free:
                gap = min(abs(at - a) for a in arcs)
                if gap > STUB_BLOCKS * BLOCK:
                    iss.append("%d px of track past the last stop at an end near (%d, %d)"
                               % (gap, f[0] if at == 0.0 else f[-2], f[1] if at == 0.0 else f[-1]))
            for a0, a1 in zip(arcs, arcs[1:]):
                if a1 - a0 > GAP_PX.get(lid, GAP_PX["default"]):
                    iss.append("%d px of track between two stops with none on it" % (a1 - a0))
        # consecutive stops of a branch: close enough, and on one connected piece of the track
        mx = GAP_PX.get(lid, GAP_PX["default"])
        piece_of = {}
        for q, pc in enumerate(pieces):
            for pi in pc:
                piece_of[pi] = q
        for br in ln.get("b") or [order]:
            for a, b in zip(br, br[1:]):
                sa, sb = stops[a], stops[b]
                gap = abs(sa["x"] - sb["x"]) + abs(sa["y"] - sb["y"])
                if gap > mx:
                    iss.append("stops %r and %r are %d px apart" % (sa["n"], sb["n"], gap))
                pa, pb = _near(polys, sa["x"], sa["y"])[1], _near(polys, sb["x"], sb["y"])[1]
                if piece_of.get(pa) != piece_of.get(pb):
                    iss.append("stops %r and %r are joined by no track" % (sa["n"], sb["n"]))
        # a surface line runs ON a street: every stretch of its track and every one of its stops has a drawn street under it
        if ln.get("k") in SURFACE:
            cov = cover.get(lid) or {}
            for r in cov.get("runs", []):
                iss.append("%d px of the track has no street under it, from (%d, %d) to (%d, %d)" % r)
            for sn in cov.get("stops", []):
                iss.append("stop %r at (%d, %d) has no street under it (%.1f px from the nearest)" % sn)
            if cov.get("invented", 0) > INVENTED_MAX:
                iss.append("%d px of the track runs on streets drawn only for it (the real street is not in the grid)" % cov["invented"])
            rep["no_street_px"] = sum(r[0] for r in cov.get("runs", []))
            rep["no_street_stops"] = len(cov.get("stops", []))
        # rivers
        for rv, cnt in _river_crossings(polys, rivers).items():
            ok = RIVER_OK_.get(lid, {}).get(rv, 0)
            if rl is not None and to_page is not None:      # the real track's own crossings (a bridge or a tunnel)
                ok = max(ok, _real_crossings(rl, to_page, rivers).get(rv, 0))
            if cnt > ok:
                iss.append("crosses the %s %d time(s) (a tunnel or bridge allows %d)" % (rv, cnt, ok))
        # the real route
        want = ROUTE_.get(lid)
        if want:
            got = max(_subseq(want, names), _subseq(want, names[::-1]))
            if got < len(want):
                iss.append("the ride %s does not run the real route's stops in order (stopped at %r)"
                           % ([n for n in names], want[got]))
        iss += _order(ln, stops)                     # each branch's stops lie along its track in ride order
        if rl is not None:
            iss += _vs_real(ln, stops, rl, real["stops"])
        if ln.get("k") not in SURFACE:              # the finished picture: track on a street or on its domain's axes
            for r in pic["runs"]:
                if r[0] == lid:
                    iss.append("%d px of the track is on no street and off its domain's axes and diagonals, from (%d, %d) to (%d, %d)" % r[1:])
        if lid == table.get("branch_line"):
            seen = set()
            BS_, TUN_ = table.get("branch_streets", ()), table.get("tunnel", [])
            for br in ln.get("b") or []:
                nm = [stops[i]["n"] for i in br]
                for st in BS_:
                    if sum(st in n for n in nm) >= 5:
                        seen.add(st)
                        if max(_subseq(TUN_, nm), _subseq(TUN_, nm[::-1])) < len(TUN_):
                            iss.append("the %s branch does not run the Market Street tunnel stops in order" % st)
            for st in BS_:
                if st not in seen:
                    iss.append("no branch runs the %s trolley" % st)
        for i in iss:
            problems.append("%s: %s" % (lid, i))
    for si, s in enumerate(stops):
        if not s.get("l"):
            problems.append("stop %r lists no line" % s["n"])
        elif not in_line[si]:
            problems.append("stop %r (%s) is in no line's ride: a dot with no line under it" % (s["n"], ",".join(s["l"])))
        for lid in s.get("l", []):
            ln = lines.get(lid)
            if ln is None:
                problems.append("stop %r lists the unknown line %r" % (s["n"], lid))
    return {"lines": lines, "problems": problems}


# ── city-generic checks ────────────────────────────────────────────────────────────────────────────────────────────
def _order(ln, stops):
    """Each branch's stops, where they stand on one polyline of the track, come along it in ride order (either way)."""
    out = []
    polys = ln["p"]
    for br in ln.get("b") or [ln["s"]]:
        at = {}
        for k, si in enumerate(br):
            d, pi, arc = _near(polys, stops[si]["x"], stops[si]["y"])
            if d <= TOL:
                at.setdefault(pi, []).append((k, arc, stops[si]["n"]))
        for pi, lst in at.items():
            arcs = [a for _, a, _ in sorted(lst)]
            up = all(b >= a - 1 for a, b in zip(arcs, arcs[1:]))
            dn = all(b <= a + 1 for a, b in zip(arcs, arcs[1:]))
            if not (up or dn):
                names = [n for _, _, n in sorted(lst)]
                out.append("the stops %s are not in ride order along the track" % names)
                break
    return out


def _vs_real(ln, stops, rl, rstops):
    """The drawn line against its real route relations: no stop out of the real order, no real branch lost."""
    out = []
    drawn = [[stops[i]["n"] for i in br] for br in ln.get("b") or [ln["s"]]]
    for rb in rl.get("b") or [rl["s"]]:
        names = [rstops[i]["n"] for i in rb]
        if len(names) < 3:
            continue
        pos = {n: k for k, n in enumerate(names)}
        best = max(drawn, key=lambda d: sum(1 for n in d if n in pos), default=[])
        got = [pos[n] for n in best if n in pos]
        if len(got) < max(2, len(names) // 2):
            out.append("the real branch %s .. %s is not drawn (%d of its %d stops)" % (names[0], names[-1], len(got), len(names)))
            continue
        if not (all(b > a for a, b in zip(got, got[1:])) or all(b < a for a, b in zip(got, got[1:]))):
            out.append("the branch %s .. %s does not run its real stops in order" % (names[0], names[-1]))
    return out


def _real_crossings(rl, to_page, rivers):
    polys = []
    for w in rl.get("w", []):
        pts = [to_page(w[k], w[k + 1]) for k in range(0, len(w) - 1, 2)]
        polys.append([v for p in pts for v in p])
    return _river_crossings(polys, rivers)


def _octi_angles(m):
    """[(page clip ring or None, [allowed run angles mod 180])] per domain (bundle `doms`, else the square grid)."""
    out = []
    for d in m.get("doms") or [{"a": 0.0}]:
        a = float(d.get("a", 0.0))
        cw, ch = (d.get("cwch") or (CW_, CH_))[:2]
        dg = math.degrees(math.atan2(ch, cw))
        ring = d.get("clip")
        if ring and isinstance(ring[0], (int, float)):
            ring = [(ring[k], ring[k + 1]) for k in range(0, len(ring) - 1, 2)]
        out.append((ring, [(a + v) % 180.0 for v in (0.0, 90.0, dg, -dg, 45.0, -45.0)]))
    return out


def _in_ring(r, x, y):
    ins = False
    for k in range(len(r)):
        (ax, ay), (bx, by) = r[k], r[(k + 1) % len(r)]
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            ins = not ins
    return ins


def picture(m, step=PIC_STEP, tol=STREET_TOL) -> dict:
    """The finished picture, for any city: every stop dot within TOL px of the drawn track of a line it lists, and every
    track sample (every `step` px) over a drawn street (within `tol` px), over the line's own tunnel, or, for a
    grade-separated line, on a straight run along its domain's axes or diagonals (a legal rail corridor through blocks).
    -> {"stops": [(name, x, y, px)], "runs": [(line id, px, x0, y0, x1, y1)], "track": px, "ok": bool}"""
    tr = m.get("transit") or {}
    st = _Streets(drawn_segments(m))
    doms = _octi_angles(m)
    lines = {ln["id"]: ln for ln in tr.get("lines", [])}

    def legal(x, y, ang):
        allowed = doms[-1][1]
        for ring, al in doms:
            if ring and _in_ring(ring, x, y):
                allowed = al
                break
        else:
            allowed = next((al for ring, al in doms if not ring), allowed)
        return any(abs(((ang - a) + 90.0) % 180.0 - 90.0) <= ANG_TOL for a in allowed)
    bad_stops, runs, total = [], [], 0.0
    for s in tr.get("stops", []):
        ds = [_near(lines[l]["p"], s["x"], s["y"])[0] for l in s.get("l", []) if l in lines and lines[l]["p"]]
        if not ds or min(ds) > TOL:
            bad_stops.append((s["n"], round(s["x"]), round(s["y"]), round(min(ds), 1) if ds else None))
    for ln in tr.get("lines", []):
        tun = _Streets([(u[0], u[1], u[2], u[3]) for u in ln.get("u", [])])
        grade = ln.get("k") not in SURFACE
        cur = None                                       # an uncovered run: [x0, y0, x1, y1, length]

        def close():
            if cur is not None:
                runs.append((ln["id"], round(cur[4]), round(cur[0]), round(cur[1]), round(cur[2]), round(cur[3])))
        for f in ln["p"]:
            for k in range(0, len(f) - 3, 2):
                ax, ay, bx, by = f[k:k + 4]
                L = math.hypot(bx - ax, by - ay)
                total += L
                ang = math.degrees(math.atan2(by - ay, bx - ax)) % 180.0
                n = max(1, int(L // step))
                for i in range(n + 1):
                    x, y = ax + (bx - ax) * i / n, ay + (by - ay) * i / n
                    ok = st.dist(x, y) <= tol or (tun.grid and tun.dist(x, y) <= 1.5) or (grade and legal(x, y, ang))
                    if ok:
                        close()
                        cur = None
                    elif cur is None:
                        cur = [x, y, x, y, 0.0]
                    else:
                        cur[4] += math.hypot(x - cur[2], y - cur[3])
                        cur[2], cur[3] = x, y
            close()
            cur = None
    runs = [tuple(r) for r in runs if r[1] >= RUN_MIN]
    return {"stops": bad_stops, "runs": runs, "track": round(total), "ok": not bad_stops and not runs}
