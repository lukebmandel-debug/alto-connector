"""A city on a coast (Chicago on Lake Michigan; Boston harbour, Los Angeles later): the open water past the coastline as ONE
sea body at the glass edge (rules doc 2.3), never a river band. The street query never asks for the coastline, and the
Great Lakes and the sea are no water polygon there, so a coast city had no lake at all: its blocks simply stopped.

    raw   = fetch(bbox, cache_dir)            # way[natural=coastline] in the box (the repo's Overpass code, mirror fallback)
    rings = sea_rings(raw, bbox, W, H, scale) # [flat ring] real map px: each coastline piece closed along the box on its water side
    attach(m, raw)                            # m["water"] += rings (detect and the lots keep off it); m["coast"] = rings

OSM draws a coastline with the land on its left, so the water is on its right; a piece that crosses the box is closed along
the box's edge on that side. A closed coastline inside the box is an island (land): left alone. Pure but for fetch().
"""
from __future__ import annotations

import json
import math
from pathlib import Path


BIG = 3.0                         # a lake / sea / bay relation this many times the box's size (either way) is open water


def _b(bbox):
    return "(%r,%r,%r,%r)" % tuple(float(v) for v in bbox)


def query(bbox, timeout=90) -> str:
    """Step 1: the coastline ways, and the tags and bounds of every lake / sea / bay relation crossing the box."""
    b = _b(bbox)
    return ("[out:json][timeout:%d];(way[natural=coastline]%s;);out geom qt;"
            "(rel[natural=water][water~\"^(lake|sea|lagoon)$\"]%s;rel[natural=bay]%s;);out tags bb;" % (timeout, b, b, b))


def big_waters(raw, bbox) -> list:
    """The ids of the relations far bigger than the box: a Great Lake, the sea (not a pond or a harbour basin)."""
    s, w, n, e = (float(v) for v in bbox)
    out = []
    for el in (raw or {}).get("elements", []):
        bb = el.get("bounds") or {}
        if el.get("type") == "relation" and bb and (bb["maxlat"] - bb["minlat"] >= BIG * (n - s) or bb["maxlon"] - bb["minlon"] >= BIG * (e - w)):
            out.append(el["id"])
    return out


def fetch(bbox, cache_dir=None, offline=False, timeout=90, log=None) -> dict:
    """The shore of the open water crossing the box: the coastline ways, and the member ways of a big lake / sea / bay
    relation that cross the box (Lake Michigan is a water relation, not a coastline), cached as coast-<bbox>.json."""
    path = Path(cache_dir) / ("coast-%.4f_%.4f_%.4f_%.4f.json" % tuple(float(v) for v in bbox)) if cache_dir else None
    if path is not None and path.exists():
        return json.loads(path.read_text("utf-8"))
    if offline:
        raise RuntimeError("coastline not cached for %s" % (tuple(bbox),))
    from .city_setup import post_retry, _store
    raw = post_retry(query(bbox, timeout), timeout, log)
    els = [e for e in raw.get("elements", []) if e.get("type") == "way"]
    ids = big_waters(raw, bbox)
    if ids:
        q = "[out:json][timeout:%d];rel(id:%s);way(r)%s;out geom qt;" % (timeout, ",".join(map(str, ids)), _b(bbox))
        for e in post_retry(q, timeout, log).get("elements", []):
            if e.get("type") == "way":
                e.setdefault("tags", {})["_shore"] = "lake"
                els.append(e)
    out = {"elements": els, "big": ids}
    if path is not None:
        _store(path, out)
    return out


def _chains(raw, bbox, scale):
    """The coastline ways joined end to end (OSM splits a coast into many ways), as real map px polylines."""
    from .. import palace_map as pm
    ways = []
    for e in (raw or {}).get("elements", []):
        g = e.get("geometry") or []
        t = e.get("tags") or {}
        if e.get("type") == "way" and (t.get("natural") == "coastline" or t.get("_shore")) and len(g) >= 2:
            ways.append([pm.project(q["lat"], q["lon"], bbox, scale) for q in g])
    key = lambda p: (round(p[0], 2), round(p[1], 2))         # noqa: E731
    out = []
    while ways:
        ch = ways.pop(0)
        grew = True
        while grew:
            grew = False
            for k, w in enumerate(ways):                     # (a lake's member ways may run either way)
                if key(w[0]) == key(ch[-1]):
                    ch += w[1:]
                elif key(w[-1]) == key(ch[0]):
                    ch = w[:-1] + ch
                elif key(w[-1]) == key(ch[-1]):
                    ch += w[::-1][1:]
                elif key(w[0]) == key(ch[0]):
                    ch = w[::-1][:-1] + ch
                else:
                    continue
                ways.pop(k)
                grew = True
                break
        out.append(ch)
    return out


def _clip(chain, W, H):
    """The pieces of a polyline inside the box [0, W] x [0, H] (Liang-Barsky on each segment, so a segment that crosses the
    whole box with both ends outside counts too), joined where they touch."""
    pieces, cur = [], None
    for a, b in zip(chain, chain[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        t0, t1, ok = 0.0, 1.0, True
        for p_, q_ in ((-dx, a[0]), (dx, W - a[0]), (-dy, a[1]), (dy, H - a[1])):
            if p_ == 0:
                if q_ < 0:
                    ok = False
                continue
            t = q_ / p_
            if p_ < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
        if not ok or t0 > t1:
            if cur:
                pieces.append(cur)
            cur = None
            continue
        p0 = (a[0] + t0 * dx, a[1] + t0 * dy)
        p1 = (a[0] + t1 * dx, a[1] + t1 * dy)
        if cur and math.dist(cur[-1], p0) < 1e-6:
            cur.append(p1)
        else:
            if cur:
                pieces.append(cur)
            cur = [p0, p1]
        if t1 < 1.0:
            pieces.append(cur)
            cur = None
    if cur:
        pieces.append(cur)
    return pieces


def _perim(p, W, H):
    """A point on the box's edge as its distance along the edge, clockwise on the page (y down) from the top-left corner."""
    x, y = p
    e = 1e-6
    if abs(y) < e:
        return x
    if abs(x - W) < e:
        return W + y
    if abs(y - H) < e:
        return W + H + (W - x)
    return 2 * W + H + (H - y)


def _walk(a, b, W, H, cw=True):
    """The box's corners met going from edge point a to edge point b (clockwise or not)."""
    P = 2 * (W + H)
    corners = [(0.0, (0.0, 0.0)), (W, (W, 0.0)), (W + H, (W, H)), (2 * W + H, (0.0, H))]
    ta, tb = _perim(a, W, H), _perim(b, W, H)
    out = []
    if cw:
        span = (tb - ta) % P
        for t, c in sorted(((t - ta) % P, c) for t, c in corners):
            if 0 < t < span:
                out.append(c)
    else:
        span = (ta - tb) % P
        for t, c in sorted(((ta - t) % P, c) for t, c in corners):
            if 0 < t < span:
                out.append(c)
    return out


def _inside(ring, x, y):
    c = False
    for (x0, y0), (x1, y1) in zip(ring, ring[-1:] + ring[:-1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


def sea_rings(raw, bbox, W, H, scale=1.0, streets=None) -> list:
    """[flat ring] of real map px: the water side of every shore piece crossing the box, closed along the box's edge. The
    water side is the one holding (almost) none of the city's streets when they are given, else the coastline's right."""
    pts = []
    for s_ in streets or ():
        p = s_.get("p") or []
        pts += [((p[i] + p[i + 2]) / 2, (p[i + 1] + p[i + 3]) / 2) for i in range(0, len(p) - 3, 2)]
    pts = pts[::max(1, len(pts) // 4000)]
    rings = []
    for ch in _chains(raw, bbox, scale):
        for pc in _clip(ch, W, H):
            if len(pc) < 2:
                continue
            a, b = pc[0], pc[-1]
            on_edge = lambda p: min(abs(p[0]), abs(p[0] - W), abs(p[1]), abs(p[1] - H)) < 1e-6   # noqa: E731
            if not (on_edge(a) and on_edge(b)) or math.dist(a, b) < 1.0:
                continue                                     # an island inside the box (land), or a sliver at a corner
            both = [pc + _walk(b, a, W, H, cw) for cw in (True, False)]
            if pts:
                wet = [sum(1 for q in pts if _inside(r, *q)) for r in both]
                ring = both[0] if wet[0] <= wet[1] else both[1]
            else:                                            # OSM keeps the land on a coastline's left: the water is right
                k = max(range(len(pc) - 1), key=lambda i: math.dist(pc[i], pc[i + 1]))
                (x0, y0), (x1, y1) = pc[k], pc[k + 1]
                L = math.dist(pc[k], pc[k + 1]) or 1.0
                probe = ((x0 + x1) / 2 - (y1 - y0) / L * 5.0, (y0 + y1) / 2 + (x1 - x0) / L * 5.0)
                ring = both[0] if _inside(both[0], *probe) else both[1]
            rings.append([round(v, 1) for p in ring for v in p])
    return rings


def attach(m, raw) -> list:
    """Add the sea to the real map: m["water"] (so detect, the lots and the dry-land test keep off it) and m["coast"]
    (the engine draws it as g["sea"]). Returns the rings."""
    rings = sea_rings(raw, m["bbox"], m["W"], m["H"], m.get("scale") or 1.0, m.get("streets"))
    if rings:
        m["water"] = list(m.get("water") or []) + rings
        m["coast"] = rings
    return rings
