"""Memory Palace neighbourhood names: label-only area names drawn over the city (no tint, no hover, no click) beside the
section districts. brief.palace.areas = [{name, lat, lon, rank}]: rank 1 is a major name (shown at the whole-city zoom),
2 appears a little closer, 3 closer still, 4 only up close; the page hides any name that would overlap a district's name,
a landmark, a building or a name of higher rank. A name a district already carries is not drawn twice."""
from __future__ import annotations

import re

from .brief import BriefError

MAX_AREAS = 160

# Philadelphia's named neighbourhoods inside the Civ Pro map box (lat 39.895-40.005, lon -75.245 to -75.085).
# [name, lat, lon, rank]; Fairmount Park is not here (the park draws its own name); positions are each neighbourhood's middle (a name outside the box, or off the drawn city, is dropped).
PHILADELPHIA = [
    ["South Philadelphia", 39.9215, -75.1700, 1], ["North Philadelphia", 39.9945, -75.1560, 1],
    ["West Philadelphia", 39.9585, -75.2300, 1], ["Fishtown", 39.9715, -75.1300, 1], ["Kensington", 39.9910, -75.1245, 1],
    ["Northern Liberties", 39.9650, -75.1415, 1], ["Fairmount", 39.9675, -75.1750, 1], ["Society Hill", 39.9432, -75.1470, 1],
    ["Chinatown", 39.9555, -75.1560, 2], ["Spring Garden", 39.9625, -75.1650, 1],
    ["Port Richmond", 39.9855, -75.1100, 1], ["Sports Complex", 39.9060, -75.1720, 1],
    ["Queen Village", 39.9385, -75.1495, 2], ["Graduate Hospital", 39.9420, -75.1790, 2], ["Point Breeze", 39.9335, -75.1795, 2],
    ["East Passyunk", 39.9285, -75.1625, 2], ["Brewerytown", 39.9760, -75.1855, 2], ["Strawberry Mansion", 39.9845, -75.1850, 2],
    ["Temple", 39.9812, -75.1550, 2], ["Powelton Village", 39.9605, -75.1985, 2], ["Spruce Hill", 39.9525, -75.2125, 2],
    ["Wynnefield", 39.9890, -75.2250, 2], ["Penn's Landing", 39.9460, -75.1405, 2], ["Kingsessing", 39.9370, -75.2280, 2],
    ["Francisville", 39.9722, -75.1700, 3], ["Callowhill", 39.9605, -75.1575, 3], ["Poplar", 39.9668, -75.1485, 3],
    ["Midtown Village", 39.9487, -75.1597, 3], ["Bella Vista", 39.9395, -75.1585, 3], ["Passyunk Square", 39.9365, -75.1610, 3],
    ["Pennsport", 39.9290, -75.1495, 3], ["Cedar Park", 39.9445, -75.2220, 3], ["Walnut Hill", 39.9560, -75.2230, 3],
    ["Mill Creek", 39.9635, -75.2095, 3], ["Parkside", 39.9777, -75.2230, 3], ["Cobbs Creek", 39.9500, -75.2370, 3],
    ["Elmwood", 39.9230, -75.2140, 3], ["Grays Ferry", 39.9400, -75.1940, 3], ["Olde Kensington", 39.9780, -75.1330, 3],
    ["Fairhill", 39.9930, -75.1370, 3], ["Ludlow", 39.9740, -75.1500, 3], ["Sharswood", 39.9770, -75.1730, 3],
    ["Eastwick", 39.8990, -75.2230, 3], ["Navy Yard", 39.8900, -75.1750, 3],
    ["Garden Court", 39.9490, -75.2090, 4], ["Squirrel Hill", 39.9433, -75.2120, 4], ["Belmont", 39.9700, -75.2130, 4],
    ["Overbrook", 39.9830, -75.2500, 4], ["Norris Square", 39.9810, -75.1330, 4], ["Yorktown", 39.9790, -75.1620, 4],
    ["Harrowgate", 39.9960, -75.1050, 4], ["Newbold", 39.9330, -75.1640, 4], ["Girard Estate", 39.9195, -75.1760, 4],
    ["Whitman", 39.9215, -75.1565, 4], ["Packer Park", 39.9115, -75.1630, 4], ["Allegheny West", 40.0010, -75.1650, 4],
]


def default_areas(place: str, bbox) -> list[dict]:
    """The built-in neighbourhood names for a city that has them (Philadelphia), those inside the box."""
    if not re.search(r"philadelphia", str(place or ""), re.I):
        return []
    s, w, n, e = bbox
    return [{"name": nm, "lat": la, "lon": lo, "rank": r} for nm, la, lo, r in PHILADELPHIA
            if s <= la <= n and w <= lo <= e]


def check_areas(areas) -> None:
    if areas in (None, []):
        return
    if not isinstance(areas, list) or len(areas) > MAX_AREAS:
        raise BriefError(f"palace.areas: a list of at most {MAX_AREAS} neighbourhood names")
    for i, a in enumerate(areas):
        if not isinstance(a, dict) or not isinstance(a.get("name"), str) or not a["name"].strip() or len(a["name"]) > 60:
            raise BriefError(f"palace.areas[{i}]: needs a name (up to 60 characters)")
        for k in ("lat", "lon"):
            if isinstance(a.get(k), bool) or not isinstance(a.get(k), (int, float)):
                raise BriefError(f"palace.areas[{i}] ({a['name']}): {k} must be a number in degrees")
        if not (-90 <= a["lat"] <= 90 and -180 <= a["lon"] <= 180):
            raise BriefError(f"palace.areas[{i}] ({a['name']}): lat/lon out of range")
        if a.get("rank") is not None and (isinstance(a["rank"], bool) or a["rank"] not in (1, 2, 3, 4)):
            raise BriefError(f"palace.areas[{i}] ({a['name']}): rank must be 1 (major) to 4 (minor)")
        if set(a) - {"name", "lat", "lon", "rank"}:
            raise BriefError(f"palace.areas[{i}]: only name, lat, lon, rank")


def layout(m, areas, district_names) -> list[dict]:
    """The names on the drawn city: [{n, x, y, r}] in map px, in rank order; a name a district carries, or one
    standing off the drawn city, is left out."""
    from .palace_place import to_px
    skip = {re.sub(r"\W+", "", str(d or "")).lower() for d in district_names}
    out, seen = [], set()
    for a in areas or []:
        key = re.sub(r"\W+", "", a["name"]).lower()
        if key in skip or key in seen:
            continue
        x, y = to_px(m, a["lat"], a["lon"])
        if not (0 <= x <= m["W"] and 0 <= y <= m["H"]):
            continue
        if m.get("far") is not None and m.get("land") and not _on_land(m["land"][0], x, y):
            continue                                    # Manhattan's layout (city_manhattan): a far-bank name is not on the island
        seen.add(key)
        out.append({"n": a["name"], "x": round(x), "y": round(y), "r": a.get("rank") or 2})
    out += [dict(f) for f in m.get("far") or ()]        # ... the boroughs across the water are named once each, on their banks
    return sorted(out, key=lambda q: q["r"])


def _on_land(ring, x, y):
    c = False
    n = len(ring) // 2
    for i in range(n):
        x0, y0, x1, y1 = ring[2 * i], ring[2 * i + 1], ring[2 * (i - 1) % (2 * n)], ring[(2 * (i - 1) + 1) % (2 * n)]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


# ── banners: a giant word across a river (e.g. the far bank of the Delaware) ────────────────────────
def check_banners(banners) -> None:
    if banners in (None, []):
        return
    if not isinstance(banners, list) or len(banners) > 8:
        raise BriefError("palace.banners: a list of at most 8 banners")
    for i, b in enumerate(banners):
        if not isinstance(b, dict) or not isinstance(b.get("name"), str) or not b["name"].strip() or len(b["name"]) > 40:
            raise BriefError(f"palace.banners[{i}]: needs a name (up to 40 characters)")
        if not isinstance(b.get("river"), str) or not b["river"].strip():
            raise BriefError(f"palace.banners[{i}] ({b['name']}): river names the river it lies across, e.g. \"Delaware\"")
        if set(b) - {"name", "river", "size", "lat", "lon", "x", "y"}:
            raise BriefError(f"palace.banners[{i}]: only name, river, size, lat, lon, x, y")


# the word's width in em (a heavy serif face: H .78, e .56, l .3 ...); the box is a little roomy so a label placed clear of it is clear of the glyphs
_EM = {"H": .8, "e": .58, "l": .32}


def banner_box(b) -> list:
    """[x0, y0, x1, y1] in map px: the room the word's letters take (cap height ~.76 of the font size, centred on x)."""
    s = float(b["s"])
    w = sum(_EM.get(c, .6) for c in b["n"]) * s * 1.06
    return [round(b["x"] - w / 2), round(b["y"] - s * .8), round(b["x"] + w / 2), round(b["y"] + s * .12)]


def banners_layout(m, banners) -> list:
    """[{n, x, y, s, box}] in map px: each word stands on the far bank of its river — across it from the middle of the drawn city — in letters
    `size` px tall (default 1400: it fills the far bank). A banner with lat/lon stands centred on that point instead (New York's Hell
    across the Hudson, whose far bank is a whole state wide)."""
    import math
    if not banners:
        return []
    rivers = m.get("river") or []
    cs = [(l["x"], l["y"]) for l in m.get("landmarks", []) if l.get("x") is not None]
    cx, cy = (sum(c[0] for c in cs) / len(cs), sum(c[1] for c in cs) / len(cs)) if cs else (m.get("W", 0) / 2, m.get("H", 0) / 2)
    out = []
    for b in banners:
        if b.get("x") is not None and b.get("y") is not None or b.get("lat") is not None and b.get("lon") is not None:
            if b.get("x") is not None:
                px, py = float(b["x"]), float(b["y"])
            else:
                from .palace_place import to_px
                px, py = to_px(m, b["lat"], b["lon"])
            size = float(b.get("size") or 1400)
            q = {"n": b["name"], "x": round(px, 1), "y": round(py + size * .32, 1), "s": round(size)}
            out.append(dict(q, box=banner_box(q)))
            continue
        rv = next((r for r in rivers if b["river"].lower() in str(r.get("n", "")).lower()), None)
        if not rv:
            continue
        p = rv.get("p") or []
        best = None
        for k in range(0, len(p) - 3, 2):
            ax, ay, bx, by = p[k], p[k + 1], p[k + 2], p[k + 3]
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy or 1e-9
            t = max(0.0, min(1.0, ((cx - ax) * dx + (cy - ay) * dy) / L2))
            qx, qy = ax + t * dx, ay + t * dy
            d = math.hypot(qx - cx, qy - cy)
            if best is None or d < best[0]:
                best = (d, qx, qy)
        d, qx, qy = best
        ux, uy = ((qx - cx) / (d or 1), (qy - cy) / (d or 1))
        size = float(b.get("size") or 1400)
        hw = float(rv.get("w") or 100) / 2
        w = len(b["name"]) * size * .56
        reach = hw + max(size * .4, w * .5) + 120
        q = {"n": b["name"], "x": round(qx + ux * reach, 1), "y": round(qy + uy * reach + size * .32, 1), "s": round(size)}
        out.append(dict(q, box=banner_box(q)))
    return out


# ── New York's NJ: the state is named "Hell", in the giant letters Philadelphia's far bank has ───────────
NJ_NAME = "New Jersey"
HELL_MAX = 2000                  # page px: the letters' height at most (Philadelphia's are 1400 on a 230 px river; the Hudson's band is 330)


def _wet(sea, x, y):
    return any(_on_land(r, x, y) for r in sea)                     # the ring test: inside a sea ring is water


def _hudson_x(m, y):
    rv = next((r for r in m.get("river") or [] if "hudson" in str(r.get("n", "")).lower()), None)
    p = (rv or {}).get("p") or []
    if len(p) < 4:
        return None
    k = min(range(0, len(p) - 1, 2), key=lambda i: abs(p[i + 1] - y))
    return p[k]


def _land_run(m, y):
    """(x0, x1): the dry strip of the far shore at page row y, from the first water west of the Hudson's own shore to that shore, or None."""
    hx = _hudson_x(m, y)
    sea = m.get("sea") or []
    if hx is None or not sea:
        return None
    x = hx
    while x > 0 and _wet(sea, x, y):                               # west out of the Hudson's water ...
        x -= 40
    x1 = x
    while x > 0 and not _wet(sea, x, y):                           # ... then across the land, to the next water (an inlet) or the page edge
        x -= 40
    return max(0.0, x), x1


def hell_for(m, banners):
    """(far, banners) for New York's Manhattan layout: the small "New Jersey" name is dropped (the state is called Hell, across the whole far
    shore) and, when the map names no banners of its own, one giant "Hell" stands on the shore beside the Hudson, near where the name stood,
    sized to fit the dry land there (clear of every other name and of the water). Any other map is returned as it came."""
    far = list(m.get("far") or ())
    nj = next((f for f in far if f.get("n") == NJ_NAME), None)
    if m.get("layout") != "manhattan" or nj is None:
        return m.get("far"), banners
    far = [f for f in far if f is not nj]
    if banners:
        return far, banners
    names = [(a["x"], a["y"]) for a in far]
    for dy in (0, -2500, 2500, -5000, 5000, -7500, 7500):
        y = nj["y"] + dy
        run = _land_run(m, y)
        if not run or run[1] - run[0] < 900:
            continue
        avail = run[1] - run[0] - 900
        size = min(HELL_MAX, .95 * avail / 2.14)
        w = 2.14 * size
        cx = run[1] - 450 - w / 2
        q = {"n": "Hell", "x": cx, "y": y + size * .32, "s": size}
        box = banner_box(q)
        sea = m.get("sea") or []
        pts = [(box[0] + (box[2] - box[0]) * i / 12, box[1] + (box[3] - box[1]) * j / 5) for i in range(13) for j in range(6)]
        if box[0] < 0 or box[1] < 0 or box[3] > m.get("H", 1e9) or any(_wet(sea, px, py) for px, py in pts):
            continue
        if any(box[0] - 600 <= nx <= box[2] + 600 and box[1] - 300 <= ny <= box[3] + 300 for nx, ny in names):
            continue
        return far, [{"name": "Hell", "river": "Hudson", "size": round(size), "x": round(cx), "y": round(y)}]
    return far, banners


def clear_of_banners(blocks, banners):
    """The blocks a building may stand on: none whose lots reach a banner's letters (a pin's dot and its line would run through them)."""
    if not banners:
        return blocks
    m_ = 40

    def inside(x, y):
        return any(b["box"][0] - m_ <= x <= b["box"][2] + m_ and b["box"][1] - m_ <= y <= b["box"][3] + m_ for b in banners)
    return [bl for bl in blocks if not inside(bl.get("x", 0), bl.get("y", 0)) and not any(inside(l[0] + l[2] / 2, l[1] + l[3] / 2) for l in bl.get("lots") or ())]
