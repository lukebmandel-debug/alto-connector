"""Boats on the Memory Palace: a ship (OSM historic=ship / building=ship — USS Olympia, Moshulu, USS Constitution ...) is not a building on a
block. It is found by its tags, taken out of the fill-in and out of the landmark list, and put IN THE WATER: where the river's own line passes
nearest to where the real ship lies, on the bank side, turned along the river. The page draws it (palace.py drawBoats): a hull, its deck, a
glass superstructure, and a name above it.

  find(raw, bbox, scale)      -> [{n, rx, ry, len_m, wid_m, ang, k}] real-px centre, metres, the hull's angle in the real frame, k = weapon class (palace_fleet.vessel_class)
  place(m, ships, doms)       -> [{n, x, y, a, len, wid, k?}]       on the page: centre, angle (deg), px; k (bb|cv|dd|sub) only for a warship
"""
from __future__ import annotations

import math

from .. import palace_map as pmap

SCALE = 1.3          # px per metre, as every building (palace_skyline.SCALE)


def is_ship(tags: dict) -> bool:
    t = tags or {}
    return t.get("building") == "ship" or t.get("historic") == "ship" or bool(t.get("ship:type") and t.get("name"))


def _metres(ring):
    lat0 = ring[0][0]
    kx, ky = 111320 * math.cos(math.radians(lat0)), 110574
    return [(lon * kx, lat * ky) for lat, lon in ring]


def _box(pts):
    """The smallest rectangle round pts: (length, width, angle of the long side in degrees, y up)."""
    best = None
    for k in range(0, 180, 5):
        r = math.radians(k)
        c, s = math.cos(r), math.sin(r)
        us = [p[0] * c + p[1] * s for p in pts]
        vs = [-p[0] * s + p[1] * c for p in pts]
        a, b = max(us) - min(us), max(vs) - min(vs)
        if best is None or a * b < best[0]:
            best = (a * b, max(a, b), min(a, b), k if a >= b else (k + 90) % 180)
    return best[1], best[2], best[3]


def find(raw, bbox, scale: float = 1.0, names=()) -> list:
    """The ships in an Overpass answer (any with a name in `names` too, if its element is there): real-px centre and size."""
    from .palace_fillin import _rings
    out, seen = [], set()
    for e in (raw or {}).get("elements") or []:
        t = e.get("tags") or {}
        if not (is_ship(t) or (t.get("name") and t.get("name") in names and t.get("historic") in ("ship", "maritime"))):
            continue
        for ring in _rings(e):
            if len(ring) < 3:
                continue
            key = (e.get("type"), e.get("id"))
            if key in seen:
                continue
            seen.add(key)
            pts = _metres(ring)
            ln, wd, ang = _box(pts)
            if ln < 12:
                continue
            real = [pmap.project(la, lo, bbox, scale) for la, lo in ring]
            rx, ry = sum(p[0] for p in real) / len(real), sum(p[1] for p in real) / len(real)
            from .palace_fleet import vessel_class
            out.append({"n": str(t.get("name") or ""), "rx": rx, "ry": ry, "len_m": round(ln, 1), "wid_m": round(wd, 1), "ang": ang, "k": vessel_class(t, str(t.get("name") or ""), ln) or ""})
    return out


def _nearest(river, x, y):
    """(distance, point, unit tangent, half width) of the river line nearest (x, y)."""
    best = None
    for r in river or []:
        p = r.get("p") or []
        for k in range(0, len(p) - 3, 2):
            ax, ay, bx, by = p[k], p[k + 1], p[k + 2], p[k + 3]
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy or 1e-9
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
            qx, qy = ax + t * dx, ay + t * dy
            d = math.hypot(qx - x, qy - y)
            if best is None or d < best[0]:
                L = math.sqrt(L2)
                best = (d, (qx, qy), (dx / L, dy / L), float(r.get("w") or 100) / 2)
    return best


def place(m: dict, ships: list, doms=None) -> list:
    """Each ship into the river's water. The page position comes through the domain that owns the real spot (palace_fillin.domains);
    the river line nearest it is where the water is."""
    from .palace_fillin import domains, _owners
    river = m.get("river") or []
    if not river or not ships:
        return []
    doms = doms or domains(m)
    by_page, by_real = _owners(doms)
    out = []
    for s in ships:
        d = by_real(s["rx"], s["ry"])
        if d is not None and not d.free and d.mp:
            lx, ly = d.mp(s["rx"], s["ry"])
            X, Y = d.page(lx, ly)
        else:
            X, Y = s["rx"], s["ry"]
        near = _nearest(river, X, Y)
        if not near or near[0] > 2500:
            continue
        dist, (qx, qy), (tx, ty), hw = near
        ln = max(46.0, min(330.0, s["len_m"] * SCALE))
        wd = max(16.0, min(max(18.0, hw * 1.2), s["wid_m"] * SCALE * 1.15, ln * .42))
        if dist <= hw * .8:                       # already in the water: stay where it is
            cx, cy = X, Y
        else:                                     # moored on the bank side of the river's own line, inside the water
            nx_, ny_ = (X - qx) / (dist or 1), (Y - qy) / (dist or 1)
            off = max(0.0, hw - wd / 2 - 6)
            cx, cy = qx + nx_ * off, qy + ny_ * off
        a = math.degrees(math.atan2(ty, tx))
        if a > 90:
            a -= 180
        elif a < -90:
            a += 180
        out.append({"n": s["n"], "x": round(cx, 1), "y": round(cy, 1), "a": round(a, 1), "len": round(ln, 1), "wid": round(wd, 1), **({"k": s["k"]} if s.get("k") else {})})
    # boats along one bank sit side by side, not on one another: each slides along the river from the ones placed before it
    placed = []
    for b in out:
        ca, sa = math.cos(math.radians(b["a"])), math.sin(math.radians(b["a"]))
        for _ in range(12):
            hit = next((q for q in placed if math.hypot(q["x"] - b["x"], q["y"] - b["y"]) < (q["len"] + b["len"]) / 2 * .78 and
                        abs((b["x"] - q["x"]) * -sa + (b["y"] - q["y"]) * ca) < (q["wid"] + b["wid"]) / 2 * .9), None)
            if not hit:
                break
            step = (hit["len"] + b["len"]) / 2 * .85
            b["x"] = round(b["x"] + ca * step, 1)
            b["y"] = round(b["y"] + sa * step, 1)
        placed.append(b)
    return out
