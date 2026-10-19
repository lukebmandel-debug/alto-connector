"""Water of the street data (2.0.1): rivers, ponds, docks, fountains, pools, piers and the green land along the banks — so the real-geometry ride draws the
Schuylkill beside 30th Street Station and the Delaware at Penn's Landing instead of paving over them.

FETCH   one Overpass question per box (water-<box>.json in the street cache dir, asked once, polite, never fatal; offline = the cache only). Water relations come with
        their FULL geometry (`out geom`): the Delaware / Schuylkill riverbank multipolygons are a few hundred KB, and whole rings are what lets them be stitched.
RINGS   multipolygon members (outer / inner) are joined end to end into closed rings (palace_map.assemble_rings: any order, any direction, open ways joined); every
        ring is then oriented (outer counter-clockwise, inner clockwise, Y north) and CUT to each 500 m cell it crosses (Sutherland-Hodgman on the cell box): a
        client reading a cell and its 8 neighbours sees every piece of water near it, and a water edge that lies along a cell border is an artefact of the cut
        (the renderer draws no bank there). Union of overlapping water (a riverbank relation plus a natural=water way of one river) is the NON-ZERO rule of the
        oriented pieces, holes (islands) being clockwise.
CELL KEYS (appended; an old client ignores them — every one is an array, which is all okShard asks of an unknown key):
  q  water pieces [ring, props]   props (QFIELDS, trailing zeros dropped): k kind ("river" "pond" "lake" "basin" "reservoir" "canal" "dock" "fountain" "pool"
     "water")  nm name  h 1 when this piece is a hole (an island: clockwise)
  v  waterways [line, props]      (VFIELDS): k waterway=river|stream|canal|drain|ditch  wd width in units (0 unknown)   — cut at cell borders like highways
  o  water points, flat 3-tuples x, y, kind ("fountain")
  k  shore structures [ring or line, props]  (KFIELDS): k man_made=pier|quay|breakwater|bridge  c 1 closed (an area), 0 a line  wd width in units (lines)
The green land along the water (natural=wood|scrub|grassland|wetland|heath, landuse=meadow|forest) joins the areas `a` (an old client draws no area kind it does not know).
SCOPE   water is kept in the in-bounds cells AND the cells within WATER_REACH_M of them (the river beside an in-bounds district is seen from it).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .. import palace_map as pmap

QFIELDS = ("k", "nm", "h")
VFIELDS = ("k", "wd")
KFIELDS = ("k", "c", "wd")
KEYS = ("q", "v", "o", "k")
WATER_REACH_M = 600.0
GREEN = {"wood", "scrub", "grassland", "wetland", "heath", "meadow", "forest"}
_WATER_KINDS = {"river", "pond", "lake", "basin", "reservoir", "canal", "dock", "fountain", "pool", "oxbow", "lagoon", "moat", "stream_pool", "reflecting_pool"}
_WAYS = {"river", "stream", "canal", "drain", "ditch"}
_SHORE = {"pier", "quay", "breakwater", "bridge"}


def water_query(bbox, timeout: int = 170) -> str:
    b = "(%r,%r,%r,%r)" % tuple(float(v) for v in bbox)
    return "\n".join([
        "[out:json][timeout:%d];" % timeout, "(",
        "  nwr[natural=water]%s;" % b, '  nwr[waterway~"^(riverbank|dock)$"]%s;' % b,
        '  way[waterway~"^(river|stream|canal|drain|ditch)$"]%s;' % b,
        "  nwr[amenity=fountain]%s;" % b, "  nwr[leisure=swimming_pool]%s;" % b,
        '  nwr[man_made~"^(pier|quay|breakwater|bridge)$"]%s;' % b,
        '  nwr[natural~"^(wood|scrub|grassland|wetland|heath)$"]%s;' % b, '  nwr[landuse~"^(meadow|forest)$"]%s;' % b,
        ");", "out geom;"])


def _path(cache_dir, bbox):
    return Path(cache_dir) / ("water-%.4f_%.4f_%.4f_%.4f.json" % tuple(float(v) for v in bbox)) if cache_dir else None


def fetch(bbox, cache_dir=None, offline: bool = False, log=None) -> dict:
    """The water answer of the box (cached as water-<box>.json, asked once). Never raises: a failure is {"elements": [], "missing": True}."""
    p = _path(cache_dir, bbox)
    if p is not None and p.exists():
        try:
            return json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            pass
    if offline:
        return {"elements": [], "missing": True}
    try:
        raw = pmap._post_overpass(water_query(bbox), 190)
    except Exception as e:                                   # noqa: BLE001 — water is a bonus, never a failure
        if log:
            log("water FAIL %s" % str(e)[:80])
        return {"elements": [], "missing": True}
    if p is not None:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps(raw, separators=(",", ":")), "utf-8")
            os.replace(tmp, p)
        except OSError:
            pass
    return raw


def water_kind(t) -> str:
    """The kind of a water AREA's tags ('' = not water)."""
    if t.get("amenity") == "fountain":
        return "fountain"
    if t.get("leisure") == "swimming_pool":
        if str(t.get("indoor") or "no") != "no" or t.get("location") in ("indoor", "underground", "roof", "rooftop") or str(t.get("covered") or "no") != "no":
            return ""
        return "pool"
    if t.get("waterway") == "riverbank":
        return "river"
    if t.get("waterway") == "dock":
        return "dock"
    if t.get("natural") == "water":
        w = str(t.get("water") or "")
        return w if w in _WATER_KINDS else ("river" if t.get("waterway") == "river" else "water")
    return ""


def _rings(e):
    """[(ring [(lat, lon)], inner)] of a way or a multipolygon relation: member ways stitched end to end into closed rings."""
    if e.get("type") == "relation":
        outer, inner = [], []
        for m in e.get("members") or ():
            if m.get("type") != "way":
                continue
            p = pmap._pts(m.get("geometry"))
            if len(p) >= 2:
                (inner if m.get("role") == "inner" else outer).append(p)
        return [(r, False) for r in pmap.assemble_rings(outer)] + [(r, True) for r in pmap.assemble_rings(inner)]
    return pmap._rings_of(e) if e.get("type") == "way" else []


def parse(raw: dict) -> dict:
    """{"polys": [(kind, name, ring, hole?)], "lines": [(kind, pts, width m)], "points": [(lat, lon, kind)], "shore": [(kind, pts, closed, width m)],
    "green": [(id, ring, holes, tags)]} of a water answer (rings in (lat, lon), no repeated end point)."""
    polys, lines, points, shore, green = [], [], [], [], []
    els = sorted((raw or {}).get("elements") or [], key=lambda e: (e.get("type", ""), e.get("id", 0)))
    seen = set()
    for e in els:
        k = (e.get("type"), e.get("id"))
        if k in seen:
            continue
        seen.add(k)
        t = e.get("tags") or {}
        ty = e.get("type")
        wk = water_kind(t)
        if wk and ty in ("way", "relation"):
            for r, inner in _rings(e):
                if len(r) >= 3:
                    polys.append((wk, str(t.get("name") or t.get("waterway:name") or ""), r, inner))
            continue
        if wk == "fountain" and ty == "node":
            points.append((e["lat"], e["lon"], "fountain"))
            continue
        if ty == "way" and t.get("waterway") in _WAYS and e.get("geometry"):
            lines.append((t["waterway"], pmap._pts(e["geometry"]), _width(t.get("width"))))
            continue
        if t.get("man_made") in _SHORE and ty in ("way", "relation"):
            rr = [r for r, inner in _rings(e) if not inner and len(r) >= 3]
            if rr:
                for r in rr:
                    shore.append((t["man_made"], r, 1, 0.0))
            elif ty == "way" and e.get("geometry"):
                shore.append((t["man_made"], pmap._pts(e["geometry"]), 0, _width(t.get("width")) or (4.0 if t["man_made"] == "pier" else 0.0)))
            continue
        gk = t.get("natural") if t.get("natural") in GREEN else t.get("landuse") if t.get("landuse") in GREEN else ""
        if gk and ty in ("way", "relation"):
            rings = _rings(e)
            inners = [r for r, inner in rings if inner]
            for r in [r for r, inner in rings if not inner and len(r) >= 3]:
                from .palace_street import _in_ring
                green.append((e.get("id", 0), r, [h for h in inners if _in_ring(h[0][0], h[0][1], r)], dict(t, _kind=gk)))
    return {"polys": polys, "lines": lines, "points": points, "shore": shore, "green": green}


def _width(v):
    from .palace_street import _metres
    w = _metres(v)
    return w if w and 0 < w < 2000 else 0.0


# ── geometry ────────────────────────────────────────────────────────────────
def signed_area(pts) -> float:
    a = 0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def orient(pts, ccw: bool):
    """The ring turned counter-clockwise (ccw) or clockwise, in a Y-north frame."""
    return list(pts) if (signed_area(pts) > 0) == ccw else list(pts)[::-1]


def clip_ring(pts, x0, y0, x1, y1):
    """Sutherland-Hodgman: the ring clipped to the box (integer units; the orientation is kept). [] when nothing of it is inside."""
    def clip(poly, inside, cross):
        out = []
        n = len(poly)
        for i in range(n):
            a, b = poly[i - 1], poly[i]
            ia, ib = inside(a), inside(b)
            if ib:
                if not ia:
                    out.append(cross(a, b))
                out.append(b)
            elif ia:
                out.append(cross(a, b))
        return out

    def at_x(X):
        return lambda a, b: (X, int(round(a[1] + (b[1] - a[1]) * (X - a[0]) / ((b[0] - a[0]) or 1))))

    def at_y(Y):
        return lambda a, b: (int(round(a[0] + (b[0] - a[0]) * (Y - a[1]) / ((b[1] - a[1]) or 1))), Y)

    p = list(pts)
    for inside, cross in ((lambda q: q[0] >= x0, at_x(x0)), (lambda q: q[0] <= x1, at_x(x1)), (lambda q: q[1] >= y0, at_y(y0)), (lambda q: q[1] <= y1, at_y(y1))):
        if not p:
            return []
        p = clip(p, inside, cross)
    o = []
    for q in p:
        if not o or q != o[-1]:
            o.append(q)
    if len(o) > 1 and o[0] == o[-1]:
        o.pop()
    return o if len(o) >= 3 and abs(signed_area(o)) > 4 else []


def simplify(pts, tol=3):
    """Drops vertices closer than tol units (0.3 m) to the line of their neighbours (a ring; cheap one pass)."""
    if len(pts) <= 4:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = out[-1], pts[i], pts[i + 1]
        dx, dy = c[0] - a[0], c[1] - a[1]
        L2 = dx * dx + dy * dy
        if L2 and ((b[0] - a[0]) * dy - (b[1] - a[1]) * dx) ** 2 / L2 <= tol * tol:
            continue
        out.append(b)
    out.append(pts[-1])
    return out if len(out) >= 3 else pts


# ── encoding into the cells of palace_street.build ──────────────────────────
def add(fr, parsed, put, flat, cut, quant):
    """Writes the water of `parsed` into the cells through palace_street.build's helpers (put(cell, key, rec), flat(cell, key, items), cut(latlon line, rec_of)
    -> [(cell, rec)], quant(latlon ring) -> [(X, Y)])."""
    from .palace_street import CS, _delta, _trim, _area_kind  # noqa: F401
    n = 0
    for kind, name, ring, inner in sorted(parsed["polys"], key=lambda p: (p[0], p[1], round(p[2][0][0], 7), round(p[2][0][1], 7), p[3])):
        pts = quant(ring)
        if len(pts) < 3:
            continue
        pts = simplify(orient(pts, not inner))
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        for ix in range(max(0, min(xs) // CS), min(fr.nx - 1, max(xs) // CS) + 1):
            for iy in range(max(0, min(ys) // CS), min(fr.ny - 1, max(ys) // CS) + 1):
                piece = clip_ring(pts, ix * CS, iy * CS, (ix + 1) * CS, (iy + 1) * CS)
                if piece:
                    put((ix, iy), "q", [_delta([(x - ix * CS, y - iy * CS) for x, y in piece]), _trim([kind, name, 1 if inner else 0])])
                    n += 1
    for kind, pts, w in parsed["lines"]:
        for k, rec in cut(pts, [_trim([kind, int(round(w / 0.1)) if w else 0])]):
            put(k, "v", rec)
    for la, lo, kind in sorted(parsed["points"]):
        X, Y = fr.xy(la, lo)
        if fr.inside(X, Y):
            k = fr.cell(X, Y)
            flat(k, "o", [X - k[0] * CS, Y - k[1] * CS, kind])
    for kind, pts, closed, w in sorted(parsed["shore"], key=lambda s: (s[0], round(s[1][0][0], 7), round(s[1][0][1], 7))):
        if closed:
            q = quant(pts)
            if len(q) < 3:
                continue
            cx, cy = sum(p[0] for p in q) // len(q), sum(p[1] for p in q) // len(q)
            if not fr.inside(cx, cy):
                continue
            k = fr.cell(cx, cy)
            put(k, "k", [_delta([(x - k[0] * CS, y - k[1] * CS) for x, y in q]), _trim([kind, 1, 0])])
        else:
            for k, rec in cut(pts, [_trim([kind, 0, int(round(w / 0.1)) if w else 0])]):
                put(k, "k", rec)
    return n


def reach(scope, keep, nx, ny, cs_m):
    """The cells water is written to: the in-bounds ones and those within WATER_REACH_M of the region (or one cell round the kept ones when the scope cannot say)."""
    out = set(keep)
    hits = getattr(scope, "hits", None)
    for ix in range(nx):
        for iy in range(ny):
            if (ix, iy) in out:
                continue
            if hits is not None:
                try:
                    if hits(ix * cs_m, iy * cs_m, (ix + 1) * cs_m, (iy + 1) * cs_m, WATER_REACH_M):
                        out.add((ix, iy))
                    continue
                except TypeError:
                    pass
            if any((ix + a, iy + b) in keep for a in (-1, 0, 1) for b in (-1, 0, 1)):
                out.add((ix, iy))
    return out


# ── reference decoder of the water keys (tests; the ride uses palace_street_js.py) ──
def decode(c: dict, S: list, ox: int, oy: int, q: float, line) -> dict:
    out = {"q": [], "v": [], "o": [], "k": []}
    for rec in c.get("q", []):
        p = rec[1]
        out["q"].append({"k": S[p[0]] if len(p) > 0 else "", "nm": S[p[1]] if len(p) > 1 else "", "h": p[2] if len(p) > 2 else 0, "ring": line(rec[0])})
    for rec in c.get("v", []):
        p = rec[1]
        out["v"].append({"k": S[p[0]] if p else "", "wd": (p[1] if len(p) > 1 else 0) * q, "line": line(rec[0])})
    a = c.get("o", [])
    for i in range(0, len(a), 3):
        out["o"].append({"x": (a[i] + ox) * q, "y": (a[i + 1] + oy) * q, "kind": S[a[i + 2]]})
    for rec in c.get("k", []):
        p = rec[1]
        d = {"k": S[p[0]] if p else "", "c": p[1] if len(p) > 1 else 0, "wd": (p[2] if len(p) > 2 else 0) * q}
        d["ring" if d["c"] else "line"] = line(rec[0])
        out["k"].append(d)
    return out
