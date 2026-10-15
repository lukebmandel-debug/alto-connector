"""An audit of the palace's drawn transit (the `map.transit` of a palace bundle, grid px).

    audit(m) -> {"lines": {id: report}, "problems": [str]}

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
BRANCH_STREETS = ("Lancaster", "Woodland", "Chester", "Baltimore", "Elmwood")
TUNNEL = ["33rd", "30th", "22nd", "19th", "15th", "13th"]
ONE_PIECE = ("mfl", "bsl", "pat", "rr")          # lines that must be one connected track


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


def _subseq(want, names):
    i = 0
    for n in names:
        if i < len(want) and want[i].lower() in n.lower():
            i += 1
    return i


def audit(m) -> dict:
    tr = m.get("transit") or {}
    stops = tr.get("stops", [])
    rivers = m.get("river") or []
    problems, lines = [], {}
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
        if lid in ONE_PIECE and len(pieces) > 1:
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
        # rivers
        for rv, cnt in _river_crossings(polys, rivers).items():
            ok = RIVER_OK.get(lid, {}).get(rv, 0)
            if cnt > ok:
                iss.append("crosses the %s %d time(s) (a tunnel or bridge allows %d)" % (rv, cnt, ok))
        # the real route
        want = ROUTE.get(lid)
        if want:
            got = max(_subseq(want, names), _subseq(want, names[::-1]))
            if got < len(want):
                iss.append("the ride %s does not run the real route's stops in order (stopped at %r)"
                           % ([n for n in names], want[got]))
        if lid == "trl":
            seen = set()
            for br in ln.get("b") or []:
                nm = [stops[i]["n"] for i in br]
                for st in BRANCH_STREETS:
                    if sum(st in n for n in nm) >= 5:
                        seen.add(st)
                        if max(_subseq(TUNNEL, nm), _subseq(TUNNEL, nm[::-1])) < len(TUNNEL):
                            iss.append("the %s branch does not run the Market Street tunnel stops in order" % st)
            for st in BRANCH_STREETS:
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
