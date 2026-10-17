"""The rivers' banks: where the streets meet the water, and the trail that runs along it.

The drawn city is an even grid; a river is a smooth band laid over it. A street that is not a bridge must not run through that band — it
ends at the bank (a real street that is not a bridge does not cross a river). And a river has banks: a green margin on either side and, along
it, the trail people walk (the Schuylkill River Trail, the Delaware River Trail), which the grid drawing dropped with every other path.

  clip_streets(m)                -> n   cuts every non-bridge street where it meets a river's band (m["streets"] changes in place)
  trails_on_page(m, real_trails) -> [{n, p}]   the named river trails, carried onto the page and laid along their river's bank
"""
from __future__ import annotations

import math
import re

BANK_GAP = 34.0         # px: a street stops this far from the water's edge: just past the green bank (the strip is 32 px wide)


class _Riv:
    def __init__(self, m):
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
                for gx in range(int((min(p[k], p[k + 2]) - hw - 60) // self.cell), int((max(p[k], p[k + 2]) + hw + 60) // self.cell) + 1):
                    for gy in range(int((min(p[k + 1], p[k + 3]) - hw - 60) // self.cell), int((max(p[k + 1], p[k + 3]) + hw + 60) // self.cell) + 1):
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
