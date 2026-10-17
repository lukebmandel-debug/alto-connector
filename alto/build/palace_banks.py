"""The rivers' banks: where the streets meet the water, and the trail that runs along it.

The drawn city is an even grid; a river is a smooth band laid over it. A street that is not a bridge must not run through that band — it
ends at the bank (a real street that is not a bridge does not cross a river). And a river has banks: a green margin on either side and, along
it, the trail people walk (the Schuylkill River Trail, the Delaware River Trail), which the grid drawing dropped with every other path.

  clip_streets(m)                -> n   cuts every non-bridge street where it meets a river's band (m["streets"] changes in place), then tidy_streets
  tidy_streets(m)                -> {}  takes out what no real river has (ticks, slivers, thin cells open to the water, loops, scraps) and ends a street
                                        that stopped short of the water at the bank
  trails_on_page(m, real_trails) -> [{n, p}]   the named river trails, carried onto the page and laid along their river's bank
"""
from __future__ import annotations

import math
import re

BLOCK = 240.0           # px: one block of the page lattice (240 wide, 320 tall); the tidy-up thresholds are fractions of it
BANK_GAP = 34.0         # px: a street stops this far from the water's edge: just past the green bank (the strip is 32 px wide)


class _Riv:
    def __init__(self, m, reach: float = 60.0):
        """reach: how far past the band a cell still lists the river (near() answers None beyond it)."""
        self.rs = []
        for r in m.get("river") or []:
            p = r.get("p") or []
            if len(p) >= 4:
                self.rs.append((r, float(r.get("w") or 100) / 2))
        self.cell = 400.0
        self.idx = {}
        for ri, (r, hw) in enumerate(self.rs):
            p = r["p"]
            for k in range(0, len(p) - 3, 2):
                for gx in range(int((min(p[k], p[k + 2]) - hw - reach) // self.cell), int((max(p[k], p[k + 2]) + hw + reach) // self.cell) + 1):
                    for gy in range(int((min(p[k + 1], p[k + 3]) - hw - reach) // self.cell), int((max(p[k + 1], p[k + 3]) + hw + reach) // self.cell) + 1):
                        self.idx.setdefault((gx, gy), []).append((ri, k))

    def near(self, x, y):
        """(slack, river index, nearest point, unit tangent, s along): slack = distance to the course - half width; smallest over rivers."""
        best = None
        seen = set()
        for it in self.idx.get((int(x // self.cell), int(y // self.cell)), ()):
            if it in seen:
                continue
            seen.add(it)
            ri, k = it
            r, hw = self.rs[ri]
            p = r["p"]
            ax, ay, bx, by = p[k], p[k + 1], p[k + 2], p[k + 3]
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy or 1e-9
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
            qx, qy = ax + t * dx, ay + t * dy
            d = math.hypot(qx - x, qy - y)
            slack = d - hw
            if best is None or slack < best[0]:
                L = math.sqrt(L2)
                best = (slack, ri, (qx, qy), (dx / L, dy / L), k // 2 + t)
        return best


def _inside(R, x, y):
    n = R.near(x, y)
    return n is not None and n[0] < BANK_GAP


def clip_streets(m: dict) -> int:
    """Every street that is not a bridge (or a trail) stops at a river's band. A street the river cuts in two stays two streets."""
    R = _Riv(m)
    if not R.rs:
        return 0
    out, cut = [], 0
    for s in m.get("streets") or []:
        p = s.get("p") or []
        if s.get("o") or s.get("t") or len(p) < 4:
            out.append(s)
            continue
        pieces, cur, touched = [], [], False
        samples = [(p[0], p[1])]
        for k in range(0, len(p) - 3, 2):
            ax, ay, bx, by = p[k], p[k + 1], p[k + 2], p[k + 3]
            n = max(1, int(math.hypot(bx - ax, by - ay) // 8))
            samples.extend((ax + (bx - ax) * t / n, ay + (by - ay) * t / n) for t in range(1, n + 1))
        for x, y in samples:
            if _inside(R, x, y):
                touched = True
                if len(cur) >= 4:
                    pieces.append(cur)
                cur = []
            else:
                cur.extend((round(x, 1), round(y, 1)))
        if len(cur) >= 4:
            pieces.append(cur)
        if not touched:
            out.append(s)
            continue
        cut += 1
        for pc in pieces:
            if len(pc) < 4:
                continue
            ln = sum(math.hypot(pc[i + 2] - pc[i], pc[i + 3] - pc[i + 1]) for i in range(0, len(pc) - 3, 2))
            if ln < 24:
                continue
            ns = dict(s)
            ns["p"] = _thin(pc)
            out.append(ns)
    m["streets"] = out
    try:
        tidy_streets(m)
    except Exception:                                       # noqa: BLE001 — the clipped streets stand as they are
        pass
    return cut


def _thin(pc):
    """Sampled points back to the straight runs: drop a point that lies on the line through its neighbours."""
    pts = [(pc[i], pc[i + 1]) for i in range(0, len(pc) - 1, 2)]
    keep = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = keep[-1], pts[i], pts[i + 1]
        cross = abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
        if cross > 1.2 * math.hypot(c[0] - a[0], c[1] - a[1]) / 10:
            keep.append(b)
    keep.append(pts[-1])
    return [round(v, 1) for q in keep for v in q]


# ── the tidy-up: what is left of the lattice beside the water ──────────────────────────────────────────────────────────────────────────────
# Clipping alone leaves what no real river has: a block cut thin by the band (outlined on three sides, a U open to the water), a tick of a
# street a few px long, a street run that grazes the bank without arriving, a chord that meets the water at both ends within a block or two, a
# few cells cut off the lattice that touch nothing. tidy_streets takes those out and carries a street that stops short of the water on to the bank.
ZONE = 760.0            # px past the band: only streets this close are looked at; nothing farther away is touched
STUB = 100.0            # a street piece shorter than this that hangs from the water or from nothing is a tick
DANGLE = 190.0          # a piece that ends in nowhere at one end and is shorter than this is a stump
SLIVER = 120.0          # px past the green strip: a piece that never leaves this margin runs along the bank, not to it
HUG_LONG = 3.0 * BLOCK  # ...unless it is a real riverfront street (this long)
CHORD = 2.0 * BLOCK     # a piece that meets the water at both ends within this is a loop of the lattice round a bend
ISLAND = 1.25 * BLOCK   # lattice left in the zone that touches nothing else and has less street than this is a scrap
EXTEND = 1.5 * BLOCK    # a street that stops in the open this far from the water (heading for it) goes on to the bank
RUNG = 1.2 * BLOCK      # px past the strip: a cross street this near the water that joins two streets running on to the bank closes a thin cell (a U)
ARRIVE = 0.5            # sin of the least angle a street may meet the bank at to be carried on (30 degrees)

LAST_STATS: dict = {}


def tidy_streets(m: dict) -> dict:
    """Take the formations no real river has out of the clipped streets, and end a street that stopped short of the water AT the bank.
    Bridges are never touched. Returns (and keeps in LAST_STATS) the counts: cut, dropped (street pieces) / px, extended."""
    R = _Riv(m, reach=ZONE + 2 * BLOCK)
    stats = {"edges": 0, "dropped": 0, "dropped_px": 0, "extended": 0, "pieces_before": len(m.get("streets") or [])}
    LAST_STATS.clear()
    LAST_STATS.update(stats)
    if not R.rs:
        return stats
    streets = m.get("streets") or []
    T = 4.0                                                          # px: two points this close are one junction

    def slack(x, y):
        n = R.near(x, y)
        return n[0] if n is not None else 1e9

    prot = [bool(s.get("o") or s.get("t")) or len(s.get("p") or []) < 4 for s in streets]
    cums = []
    for s in streets:
        p = s.get("p") or []
        c = [0.0]
        for i in range(0, len(p) - 3, 2):
            c.append(c[-1] + math.hypot(p[i + 2] - p[i], p[i + 3] - p[i + 1]))
        cums.append(c)
    # the segments in the zone, hashed
    CELL = 300.0
    H: dict = {}
    segs = []
    for si, s in enumerate(streets):
        p = s.get("p") or []
        for j in range(0, len(p) - 3, 2):
            ax, ay, bx, by = p[j], p[j + 1], p[j + 2], p[j + 3]
            L = math.hypot(bx - ax, by - ay)
            k = max(1, int(L // 120))
            if min(slack(ax + (bx - ax) * t / k, ay + (by - ay) * t / k) for t in range(k + 1)) > ZONE + BLOCK:
                continue
            idx = len(segs)
            segs.append((si, j // 2, ax, ay, bx, by))
            for gx in range(int(min(ax, bx) // CELL), int(max(ax, bx) // CELL) + 1):
                for gy in range(int(min(ay, by) // CELL), int(max(ay, by) // CELL) + 1):
                    H.setdefault((gx, gy), []).append(idx)
    # nodes: junctions, street ends
    nodes = []                                                       # [x, y, anchored]
    NH: dict = {}

    def node_at(x, y):
        gx, gy = int(x // 12), int(y // 12)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for ni in NH.get((gx + dx, gy + dy), ()):
                    if math.hypot(nodes[ni][0] - x, nodes[ni][1] - y) <= T:
                        return ni
        nodes.append([x, y, False])
        NH.setdefault((gx, gy), []).append(len(nodes) - 1)
        return len(nodes) - 1

    cuts = {}                                                        # street -> [(u, node)]

    def put(si, u, ni):
        cuts.setdefault(si, []).append((u, ni))

    def seg_u(si, j, t):
        c = cums[si]
        return c[j] + (c[j + 1] - c[j]) * t

    for si, s in enumerate(streets):
        if prot[si]:
            continue
        L = cums[si][-1]
        p = s["p"]
        put(si, 0.0, node_at(p[0], p[1]))
        put(si, L, node_at(p[-2], p[-1]))
    seen = set()
    for cell, lst in H.items():
        for a in range(len(lst)):
            for b in range(a + 1, len(lst)):
                ia, ib = lst[a], lst[b]
                if (ia, ib) in seen:
                    continue
                seen.add((ia, ib))
                sa, ja, ax, ay, bx, by = segs[ia]
                sb, jb, cx, cy, dx, dy = segs[ib]
                if sa == sb or (prot[sa] and prot[sb]):
                    continue
                hits = []
                den = (bx - ax) * (dy - cy) - (by - ay) * (dx - cx)
                if abs(den) > 1e-9:
                    t = ((cx - ax) * (dy - cy) - (cy - ay) * (dx - cx)) / den
                    u2 = ((cx - ax) * (by - ay) - (cy - ay) * (bx - ax)) / den
                    if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u2 <= 1 + 1e-9:
                        hits.append((t, u2))
                for (px, py, ta) in ((ax, ay, 0.0), (bx, by, 1.0)):   # an end of A resting on B
                    L2 = (dx - cx) ** 2 + (dy - cy) ** 2 or 1e-9
                    u2 = max(0.0, min(1.0, ((px - cx) * (dx - cx) + (py - cy) * (dy - cy)) / L2))
                    if math.hypot(cx + (dx - cx) * u2 - px, cy + (dy - cy) * u2 - py) <= T:
                        hits.append((ta, u2))
                for (px, py, ub) in ((cx, cy, 0.0), (dx, dy, 1.0)):   # an end of B resting on A
                    L2 = (bx - ax) ** 2 + (by - ay) ** 2 or 1e-9
                    t = max(0.0, min(1.0, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / L2))
                    if math.hypot(ax + (bx - ax) * t - px, ay + (by - ay) * t - py) <= T:
                        hits.append((t, ub))
                for t, u2 in hits:
                    x, y = ax + (bx - ax) * t, ay + (by - ay) * t
                    ni = node_at(x, y)
                    if prot[sa] or prot[sb]:
                        nodes[ni][2] = True
                    if not prot[sa]:
                        put(sa, seg_u(sa, ja, t), ni)
                    if not prot[sb]:
                        put(sb, seg_u(sb, jb, u2), ni)
    # edges
    edges = []                                                       # dict(si, u0, u1, n0, n1, len, pts, minsl, maxsl, wet0, wet1)
    by_street = {}
    for si, lst in cuts.items():
        lst.sort()
        keep = []
        for u, ni in lst:
            if keep and abs(u - keep[-1][0]) < 1.0:
                continue
            keep.append((u, ni))
        for (u0, n0), (u1, n1) in zip(keep, keep[1:]):
            if n0 == n1 or u1 - u0 < 1.0:
                continue
            pts = _slice(streets[si]["p"], cums[si], u0, u1)
            sl = [slack(x, y) for x, y in _dense(pts, 40)]
            e = {"si": si, "u0": u0, "u1": u1, "n0": n0, "n1": n1, "len": u1 - u0, "pts": pts, "min": min(sl), "max": max(sl),
                 "w0": sl[0] < BANK_GAP + 10, "w1": sl[-1] < BANK_GAP + 10, "live": True}
            e["zone"] = e["max"] <= ZONE
            by_street.setdefault(si, []).append(len(edges))
            edges.append(e)
    stats["edges"] = len(edges)
    for eis in by_street.values():                                   # a street's unbroken run along the bank: a long one is a riverfront street
        run = []
        for ei in sorted(eis, key=lambda i: edges[i]["u0"]) + [None]:
            if ei is not None and edges[ei]["max"] < BANK_GAP + SLIVER and (not run or abs(edges[run[-1]]["u1"] - edges[ei]["u0"]) < 1.0):
                run.append(ei)
                continue
            for r in run:
                edges[r]["hug"] = sum(edges[q]["len"] for q in run)
            run = [ei] if ei is not None and edges[ei]["max"] < BANK_GAP + SLIVER else []
    for si, eis in by_street.items():                                # a whole piece that meets the water at both ends within a block or two
        es = sorted(eis, key=lambda i: edges[i]["u0"])
        if edges[es[0]]["w0"] and edges[es[-1]]["w1"] and cums[si][-1] < CHORD and all(edges[i]["zone"] for i in es):
            for i in es:
                edges[i]["live"] = False
                edges[i]["why"] = "chord"
    inc = {}
    for ei, e in enumerate(edges):
        inc.setdefault(e["n0"], set()).add(ei)
        inc.setdefault(e["n1"], set()).add(ei)

    def deg(ni):
        return sum(1 for ei in inc.get(ni, ()) if edges[ei]["live"]) + (2 if nodes[ni][2] else 0)

    def drop(ei):
        edges[ei]["live"] = False

    def rails(ni, e):
        """Edges at node ni (not e, not e's street) that run on to the water at their far end."""
        out = []
        for fi in inc.get(ni, ()):
            f = edges[fi]
            if f["live"] and f is not e and f["si"] != e["si"] and (f["w1"] if f["n0"] == ni else f["w0"]):
                out.append(f)
        return out

    def goes_on(ni, e):
        """Does e's own street carry on past node ni?"""
        return any(edges[fi]["live"] and edges[fi] is not e and edges[fi]["si"] == e["si"] for fi in inc.get(ni, ()))

    changed = True
    while changed:
        changed = False
        for ei, e in enumerate(edges):
            if not e["live"] or not e["zone"]:
                continue
            if (e["max"] < BANK_GAP + RUNG and not (goes_on(e["n0"], e) and goes_on(e["n1"], e)) and not e["w0"] and not e["w1"] and e.get("hug", 0) < HUG_LONG and rails(e["n0"], e) and rails(e["n1"], e)):
                drop(ei)                                                                  # a thin cell open to the water: its closing street goes
                e["why"] = "rung"
                changed = True
                continue
            d0, d1 = deg(e["n0"]), deg(e["n1"])
            dead0, dead1 = d0 <= 1 and not e["w0"], d1 <= 1 and not e["w1"]
            L = e["len"]
            bad = ((L < STUB and (dead0 or dead1 or e["w0"] or e["w1"]))                    # a tick
                   or (L < DANGLE and (dead0 or dead1))                                   # a stump (or a floating bit)
                   or (e["max"] < BANK_GAP + SLIVER and e.get("hug", L) < HUG_LONG)       # runs along the bank, never leaves its margin
                   or (e["w0"] and e["w1"] and L < CHORD))                                # meets the water twice in a short run
            if bad:
                drop(ei)
                e["why"] = "tick" if L < STUB else "stump" if L < DANGLE and (dead0 or dead1) else "hug" if e["max"] < BANK_GAP + SLIVER else "chord"
                changed = True
        # islands: lattice left in the zone that touches nothing and is small
        parent = list(range(len(nodes)))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        for e in edges:
            if e["live"]:
                parent[find(e["n0"])] = find(e["n1"])
        comp = {}
        for e in edges:
            if e["live"]:
                c = comp.setdefault(find(e["n0"]), {"len": 0.0, "zone": True, "anchor": False, "edges": []})
                c["len"] += e["len"]
                c["zone"] = c["zone"] and e["zone"]
                c["edges"].append(e)
        for c in comp.values():
            c["anchor"] = any(nodes[n][2] for e in c["edges"] for n in (e["n0"], e["n1"]))
            if c["zone"] and not c["anchor"] and c["len"] < ISLAND:
                for e in c["edges"]:
                    e["live"] = False
                    e["why"] = "island"
                changed = True
    # rebuild the streets that lost an edge; the rest are kept as they were
    out = []
    log = []
    dropped = dropped_px = 0
    for si, s in enumerate(streets):
        eis = by_street.get(si)
        if not eis or all(edges[ei]["live"] for ei in eis):
            out.append(s)
            continue
        run = []
        runs = []
        for ei in sorted(eis, key=lambda i: edges[i]["u0"]):
            e = edges[ei]
            if e["live"]:
                if run and abs(run[-1]["u1"] - e["u0"]) < 1.0:
                    run.append(e)
                else:
                    if run:
                        runs.append(run)
                    run = [e]
            else:
                dropped_px += e["len"]
                log.append(("drop:" + e.get("why", "?"), round(e["pts"][len(e["pts"]) // 2][0]), round(e["pts"][len(e["pts"]) // 2][1]), round(e["len"]), s.get("n")))
                if run:
                    runs.append(run)
                run = []
        if run:
            runs.append(run)
        dropped += 1
        for rn in runs:
            pts = []
            for e in rn:
                pts.extend(e["pts"] if not pts else e["pts"][1:])
            pc = [round(v, 1) for q in pts for v in q]
            if len(pc) >= 4 and sum(e["len"] for e in rn) >= 24:
                ns = dict(s)
                ns["p"] = _thin(pc)
                out.append(ns)
    # the streets that stop in the open short of the water, heading for it, go on to the bank
    ext = 0
    for ns in out:
        if ns.get("o") or ns.get("t") or len(ns.get("p") or []) < 4:
            continue
        p = ns["p"]
        for end in (0, 1):
            if end == 0:
                x, y, qx, qy = p[0], p[1], p[2], p[3]
            else:
                x, y, qx, qy = p[-2], p[-1], p[-4], p[-3]
            if slack(x, y) < BANK_GAP + 10 or slack(x, y) > ZONE:
                continue
            if _touches(out, ns, x, y, T + 2):
                continue
            hx, hy = x - qx, y - qy
            hl = math.hypot(hx, hy)
            if hl < 1e-6:
                continue
            hx, hy = hx / hl, hy / hl
            hit = None
            step = 6.0
            d = step
            while d <= EXTEND:
                if slack(x + hx * d, y + hy * d) <= BANK_GAP:
                    hit = d
                    break
                d += step
            if hit is None:
                continue
            lo, hi = hit - step, hit
            for _ in range(8):
                mid = (lo + hi) / 2
                if slack(x + hx * mid, y + hy * mid) <= BANK_GAP:
                    hi = mid
                else:
                    lo = mid
            n = R.near(x + hx * hi, y + hy * hi)
            if n is None or abs(hx * n[3][1] - hy * n[3][0]) < ARRIVE:
                continue
            ex, ey = round(x + hx * lo, 1), round(y + hy * lo, 1)
            if end == 0:
                p[0:0] = [ex, ey]
            else:
                p.extend([ex, ey])
            ext += 1
            log.append(("ext", ex, ey, round(hi)))
    m["streets"] = out
    stats.update({"dropped": dropped, "dropped_px": round(dropped_px), "extended": ext, "log": log})
    LAST_STATS.update(stats)
    return stats


def _touches(streets, me, x, y, tol):
    """Does the point rest on a street other than `me`?"""
    for s in streets:
        if s is me:
            continue
        p = s.get("p") or []
        for i in range(0, len(p) - 3, 2):
            ax, ay, bx, by = p[i], p[i + 1], p[i + 2], p[i + 3]
            if x < min(ax, bx) - tol or x > max(ax, bx) + tol or y < min(ay, by) - tol or y > max(ay, by) + tol:
                continue
            L2 = (bx - ax) ** 2 + (by - ay) ** 2 or 1e-9
            t = max(0.0, min(1.0, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / L2))
            if math.hypot(ax + (bx - ax) * t - x, ay + (by - ay) * t - y) <= tol:
                return True
    return False


def _slice(p, cum, u0, u1):
    """The polyline p (flat) between arc lengths u0 and u1, as [(x, y)]."""
    def at(u):
        j = 0
        while j < len(cum) - 2 and cum[j + 1] < u:
            j += 1
        d = (cum[j + 1] - cum[j]) or 1e-9
        t = max(0.0, min(1.0, (u - cum[j]) / d))
        return p[2 * j] + (p[2 * j + 2] - p[2 * j]) * t, p[2 * j + 1] + (p[2 * j + 3] - p[2 * j + 1]) * t
    pts = [at(u0)]
    for j in range(1, len(cum) - 1):
        if u0 + 0.5 < cum[j] < u1 - 0.5:
            pts.append((p[2 * j], p[2 * j + 1]))
    pts.append(at(u1))
    return pts


def _dense(pts, step):
    out = [pts[0]]
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        k = max(1, int(math.hypot(bx - ax, by - ay) // step))
        out.extend((ax + (bx - ax) * t / k, ay + (by - ay) * t / k) for t in range(1, k + 1))
    return out


def _page(m):
    if m.get("doms"):
        from .palace_place import page_of
        return lambda x, y: page_of(m, x, y)
    from .palace_grid import mapping_from
    mp = mapping_from(m["grid"])
    return lambda x, y: mp(x, y)


def _along(R, ri, s, side, off):
    """The point at s (a fractional vertex index) along river ri, off metres out on `side` (+1 / -1 of its direction), and the unit tangent."""
    r, hw = R.rs[ri]
    pr = r["p"]
    npts = len(pr) // 2
    j = max(0, min(npts - 2, int(math.floor(s))))
    t = max(0.0, min(1.0, s - j))
    ax, ay, bx, by = pr[2 * j], pr[2 * j + 1], pr[2 * j + 2], pr[2 * j + 3]
    x, y = ax + (bx - ax) * t, ay + (by - ay) * t
    # the tangent: the river's own course around this point (a few vertices each way), so a kinked polyline does not kink the trail
    k0, k1 = max(0, j - 2), min(npts - 1, j + 3)
    tx, ty = pr[2 * k1] - pr[2 * k0], pr[2 * k1 + 1] - pr[2 * k0 + 1]
    L = math.hypot(tx, ty) or 1.0
    tx, ty = tx / L, ty / L
    return x + (-ty) * side * off, y + tx * side * off


def _real_side(real_rivers, name, vertices):
    """+1 / -1 / 0: which side of the REAL river (its direction as drawn in real px) the real trail vertices lie on, by majority. The page's
    drawing warps the land, so the side is read before the page touches it."""
    best = None
    for r in real_rivers or []:
        p = r.get("p") or []
        if str(r.get("n") or "").lower() == name.lower() and len(p) >= 30 and (best is None or len(p) > len(best)):
            best = p
    if best is None:
        return 0, None
    segs = [(best[i], best[i + 1], best[i + 2], best[i + 3]) for i in range(0, len(best) - 3, 2)]
    tally = 0
    for X, Y in vertices:
        bd, bs = 1e18, 0
        for ax, ay, bx, by in segs:
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy or 1e-9
            t = max(0.0, min(1.0, ((X - ax) * dx + (Y - ay) * dy) / L2))
            qx, qy = ax + t * dx, ay + t * dy
            d = math.hypot(qx - X, qy - Y)
            if d < bd:
                L = math.sqrt(L2)
                bd, bs = d, 1 if ((X - qx) * -dy / L + (Y - qy) * dx / L) >= 0 else -1
        if bd <= 320:
            tally += bs
    npt = len(best) // 2
    ia, ib = npt // 4, (3 * npt) // 4
    mid = (best[2 * ia], best[2 * ia + 1]), (best[2 * ib], best[2 * ib + 1])
    return (1 if tally > 0 else -1 if tally < 0 else 0), mid


GAP_PX = 2600.0         # page px along the river: a gap in the real trail shorter than this is bridged (about a kilometre)


def trails_on_page(m: dict, real_trails, real_rivers=None) -> list:
    """Each river's trail as ONE line along its bank: the real trail's named pieces (Schuylkill River Trail, Schuylkill Banks Boardwalk,
    'Christian to Crescent', Delaware River Trail) chained from where the real trail starts to where it ends, the small gaps between pieces
    bridged, on the single bank the real trail keeps (the Schuylkill River Trail runs on the city side only; read from the real geometry, since
    the page's warped land can flip a short piece to the far bank). A gap longer than ~1 km starts a new run."""
    R = _Riv(m)
    if not R.rs or not real_trails:
        return []
    page = _page(m)
    out = []
    for ri, (r, hw) in enumerate(R.rs):
        rn = str(r.get("n") or "")
        first = rn.split()[0].lower() if rn.split() else ""
        if not first:
            continue
        fam = [t for t in real_trails if first in str(t.get("n") or "").lower() and "connector" not in str(t.get("n") or "").lower()
               and len(t.get("p") or []) >= 4]
        if not fam:
            continue
        names = {}
        for t in fam:
            names[t["n"]] = names.get(t["n"], 0) + len(t["p"])
        label = max(names, key=lambda k: (("river trail" in k.lower()), names[k]))
        verts = [(t["p"][i], t["p"][i + 1]) for t in fam for i in range(0, len(t["p"]) - 1, 2)]
        ss = []                                                          # (s along this river) for every trail vertex that lies by it
        pg = []
        for X0, Y0 in verts:
            try:
                X, Y = page(X0, Y0)
            except Exception:                                           # noqa: BLE001
                continue
            n = R.near(X, Y)
            if n is None or n[1] != ri or n[0] > 420:
                continue
            slack, _ri, (qx, qy), (tx, ty), sj = n
            ss.append(sj)
            pg.append(1 if ((X - qx) * -ty + (Y - qy) * tx) >= 0 else -1)
        if len(ss) < 4:
            continue
        side, mid = _real_side(real_rivers, rn, verts)
        if side and mid:
            try:                                                        # the real river's direction against the drawn river's
                s_a = R.near(*page(*mid[0]))[4]
                s_b = R.near(*page(*mid[1]))[4]
                if s_a > s_b:
                    side = -side
            except Exception:                                           # noqa: BLE001
                side = 0
        if not side:
            side = 1 if sum(pg) >= 0 else -1                            # no real river to read: the page's own majority
        ss.sort()
        runs, cur = [], [ss[0], ss[0]]
        npts = len(r["p"]) // 2
        for v in ss[1:]:
            if v - cur[1] > 1 and _span(r["p"], cur[1], v) > GAP_PX:
                runs.append(cur)
                cur = [v, v]
            else:
                cur[1] = v
        runs.append(cur)
        off = hw + BANK_GAP / 2 + 6
        for lo, hi in runs:
            if _span(r["p"], lo, hi) < 120:
                continue
            pts, s = [], lo
            step = 0.5
            while s < hi:
                x, y = _along(R, ri, s, side, off)
                pts.extend((round(x, 1), round(y, 1)))
                s += step
            x, y = _along(R, ri, hi, side, off)
            pts.extend((round(x, 1), round(y, 1)))
            if len(pts) >= 8:
                out.append({"n": label, "p": _thin(pts)})
    return out


def _span(pr, a, b):
    """Page px along a river's polyline between vertex indices a and b."""
    if b <= a:
        return 0.0
    tot, j = 0.0, int(math.floor(a))
    while j < b and 2 * j + 3 < len(pr):
        x0, y0, x1, y1 = pr[2 * j], pr[2 * j + 1], pr[2 * j + 2], pr[2 * j + 3]
        lo, hi = max(a, j), min(b, j + 1)
        tot += math.hypot(x1 - x0, y1 - y0) * max(0.0, hi - lo)
        j += 1
    return tot
