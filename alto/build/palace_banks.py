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

BANK_GAP = 7.0          # px: a street stops this far from the water's edge (the rim stroke)
TRAIL_OFF = 15.0        # px: the trail runs this far outside the band's edge


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


def trails_on_page(m: dict, real_trails) -> list:
    """The named trails that follow a river (their name has the river's name, or 'river'), as thin lines along that river's bank on the side
    they lie. Real vertices are carried onto the page, then laid at the bank: the course keeps the trail's own length along the river."""
    R = _Riv(m)
    if not R.rs or not real_trails:
        return []
    page = _page(m)
    groups = {}
    for t in real_trails:
        nm = t.get("n") or ""
        if not nm:
            continue
        key = nm.lower()
        groups.setdefault(key, {"n": nm, "pts": []})["pts"].append(t.get("p") or [])
    out = []
    for key, g in groups.items():
        rname = None
        for r, hw in R.rs:
            first = str(r.get("n") or "").split()[0].lower()
            if first and first in key:
                rname = first
        if rname is None and "river" not in key:
            continue
        samples = []                                                    # (s along the river, side, river index)
        for p in g["pts"]:
            for i in range(0, len(p) - 1, 2):
                try:
                    X, Y = page(p[i], p[i + 1])
                except Exception:                                       # noqa: BLE001
                    continue
                n = R.near(X, Y)
                if n is None or n[0] > 420:
                    continue
                slack, ri, (qx, qy), (tx, ty), s = n
                side = 1 if ((X - qx) * -ty + (Y - qy) * tx) >= 0 else -1
                samples.append((s, side, ri))
        if len(samples) < 6:
            continue
        ri = max(set(s_[2] for s_ in samples), key=lambda v: sum(1 for s_ in samples if s_[2] == v))
        samples = [s_ for s_ in samples if s_[2] == ri]
        side = 1 if sum(s_[1] for s_ in samples) >= 0 else -1
        lo, hi = min(s_[0] for s_ in samples), max(s_[0] for s_ in samples)
        r, hw = R.rs[ri]
        pr = r["p"]
        pts = []
        npts = len(pr) // 2
        for j in range(int(math.floor(lo)), min(npts - 1, int(math.ceil(hi))) + 1):
            x, y = pr[2 * j], pr[2 * j + 1]
            a = (pr[2 * max(j - 1, 0)], pr[2 * max(j - 1, 0) + 1])
            b = (pr[2 * min(j + 1, npts - 1)], pr[2 * min(j + 1, npts - 1) + 1])
            tx, ty = b[0] - a[0], b[1] - a[1]
            L = math.hypot(tx, ty) or 1
            nx, ny = -ty / L * side, tx / L * side                      # the normal on the trail's side
            off = hw + BANK_GAP + TRAIL_OFF
            pts.extend((round(x + nx * off, 1), round(y + ny * off, 1)))
        if len(pts) >= 8:
            out.append({"n": g["n"], "p": _thin(pts)})
    return out
