"""Bus routes on the Mind Palace: the main bus routes drawn along ITS streets and ridden like any transit line.

The rail and tram lines come from OSM track (palace_transit.py). A bus runs on the streets, and on this page the streets are the even grid. So a
route is taken from what is real about it — the path of its OSM route relation (route=bus: the ways it runs along, in order) — carried onto the
page through the city's own mapping and laid on the page's street graph (palace_place.graph, the shortest street way from point to point), so it
lies ON the streets. Its stops are the real bus stops (highway=bus_stop, named) that stand on that real path, in the order the route meets them.

  fetch(bbox, cache_dir, offline) -> raw     the route relations with their ways, and the bus stops, cached as bus-<bbox>.json
  attach(m, raw)                  -> n       adds the main routes to m["transit"]: lines {id, n, c, k: "bus", p, s, b, to}, stops {n, x, y, l}

One route per ref (its longest run), at most MAX_ROUTES: the ones that run through the middle of the city first.
"""
from __future__ import annotations

import heapq
import json
import math
import os
import re
from pathlib import Path

from .. import palace_map as pmap

MAX_ROUTES = 36
SNAP = 200.0         # px: how far a point may be from the street graph
STOP_M = 22.0        # a real stop within this many metres of a route's real path is on it
PALETTE = ["#3f7f9b", "#7a6aa8", "#4c8c6b", "#a8693f", "#9b4f6c", "#5a7fb0", "#7f8f3f", "#a0526a", "#3f8f8f", "#8f6f3f"]


def _query(bbox):
    s, w, n, e = bbox
    b = "%f,%f,%f,%f" % (s, w, n, e)
    return ('[out:json][timeout:170];relation["route"="bus"](%s)->.r;.r out body;way(r.r)(%s);out geom;'
            'node["highway"="bus_stop"]["name"](%s);out body;' % (b, b, b))


def fetch(bbox, cache_dir=None, offline: bool = False) -> dict:
    path = Path(cache_dir) / ("bus2-%.4f_%.4f_%.4f_%.4f.json" % tuple(bbox)) if cache_dir else None
    if path is not None and path.exists():
        try:
            return json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            pass
    if offline:
        return {"elements": []}
    raw = pmap._post_overpass(_query(tuple(bbox)), 190)
    if path is not None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(raw, separators=(",", ":")), "utf-8")
            os.replace(tmp, path)
        except OSError:
            pass
    return raw


def routes(raw) -> list:
    """[{ref, name, to, colour, path: [(lat, lon)]}]: each relation's ways chained in member order into one path."""
    ways = {e["id"]: e for e in (raw or {}).get("elements") or [] if e.get("type") == "way" and e.get("geometry")}
    out = []
    for e in (raw or {}).get("elements") or []:
        t = e.get("tags") or {}
        if e.get("type") != "relation" or t.get("route") != "bus" or not t.get("ref"):
            continue
        path = []
        for mm in e.get("members") or []:
            if mm.get("type") != "way" or mm.get("role") in ("platform", "backward") or mm["ref"] not in ways:
                continue
            g = [(p["lat"], p["lon"]) for p in ways[mm["ref"]]["geometry"] if p]
            if len(g) < 2:
                continue
            if path:
                d_end = math.hypot(g[0][0] - path[-1][0], g[0][1] - path[-1][1])
                d_rev = math.hypot(g[-1][0] - path[-1][0], g[-1][1] - path[-1][1])
                if d_rev < d_end:
                    g = g[::-1]
                if min(d_end, d_rev) > 0.003:                         # a gap of more than ~300 m: a separate run — keep the longer one
                    if len(g) > len(path):
                        path = []
            path.extend(g if not path else g[1:])
        if len(path) >= 8:
            out.append({"ref": str(t["ref"]), "name": t.get("name") or "", "to": t.get("to") or "", "colour": t.get("colour") or "", "path": path})
    return out


def _stops(raw):
    return [(e["lat"], e["lon"], (e.get("tags") or {}).get("name") or "") for e in (raw or {}).get("elements") or []
            if e.get("type") == "node" and (e.get("tags") or {}).get("highway") == "bus_stop" and re.search(r"[A-Za-z]{3}", (e.get("tags") or {}).get("name") or "")]


class _G:
    def __init__(self, m):
        from .palace_place import graph
        g = graph(m)
        c = g["n"]
        self.X, self.Y = c[0::2], c[1::2]
        self.adj = [[] for _ in self.X]
        e = g["e"]
        for i in range(0, len(e), 3):
            a, b = e[i], e[i + 1]
            L = math.hypot(self.X[a] - self.X[b], self.Y[a] - self.Y[b])
            self.adj[a].append((b, L))
            self.adj[b].append((a, L))
        self.cell = {}
        for i, (x, y) in enumerate(zip(self.X, self.Y)):
            self.cell.setdefault((int(x // 120), int(y // 120)), []).append(i)

    def nearest(self, x, y, maxd=SNAP):
        best, bd = -1, maxd * maxd
        r = int(maxd // 120) + 1
        cx, cy = int(x // 120), int(y // 120)
        for gx in range(cx - r, cx + r + 1):
            for gy in range(cy - r, cy + r + 1):
                for i in self.cell.get((gx, gy), ()):
                    d = (self.X[i] - x) ** 2 + (self.Y[i] - y) ** 2
                    if d < bd:
                        best, bd = i, d
        return best

    def path(self, a, b, cap):
        if a == b:
            return [a]
        dist, prev, H = {a: 0.0}, {}, [(0.0, a)]
        while H:
            d, u = heapq.heappop(H)
            if d > dist.get(u, 1e18):
                continue
            if u == b:
                out = [b]
                while out[-1] != a:
                    out.append(prev[out[-1]])
                return out[::-1]
            if d > cap:
                break
            for v, w in self.adj[u]:
                nd = d + w
                if nd < dist.get(v, 1e18):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(H, (nd, v))
        return None


def _to_page(m):
    """real px -> page px, on a v2 map (m["doms"]) or the v1 grid."""
    if m.get("doms"):
        from .palace_place import page_of
        return lambda x, y: page_of(m, x, y)
    from .palace_grid import mapping_from
    mp = mapping_from(m["grid"])
    return lambda x, y: mp(x, y)


def _metres(lat, lon, lat0):
    return (lon * 111320 * math.cos(math.radians(lat0)), lat * 110574)


def attach(m: dict, raw) -> int:
    rts = routes(raw)
    if not rts or not m.get("streets"):
        return 0
    bbox, scale = m["bbox"], m.get("scale", 1.0)
    page = _to_page(m)
    G = _G(m)
    # the middle of the city: where the user's buildings and landmarks stand
    cs = [(l["x"], l["y"]) for l in m.get("landmarks", []) if l.get("x") is not None] or [(m["W"] / 2, m["H"] / 2)]
    cx, cy = sum(c[0] for c in cs) / len(cs), sum(c[1] for c in cs) / len(cs)
    cand = {}
    for r in rts:
        step = max(1, len(r["path"]) // 400)
        pts = []
        for la, lo in r["path"][::step] + [r["path"][-1]]:
            try:
                X, Y = page(*pmap.project(la, lo, bbox, scale))
            except Exception:                                # noqa: BLE001 — a point the mapping cannot take
                continue
            if 0 <= X <= m["W"] and 0 <= Y <= m["H"]:
                n = G.nearest(X, Y)
                if n >= 0 and (not pts or pts[-1] != n):
                    pts.append(n)
        poly = []
        for n in pts:
            if not poly:
                poly.append(n)
                continue
            p = G.path(poly[-1], n, cap=700.0)
            if p:
                poly.extend(p[1:])
        if len(poly) < 6:
            continue
        L = sum(math.hypot(G.X[a] - G.X[b], G.Y[a] - G.Y[b]) for a, b in zip(poly, poly[1:]))
        near = sum(math.hypot(G.X[a] - G.X[b], G.Y[a] - G.Y[b]) for a, b in zip(poly, poly[1:])
                   if math.hypot(G.X[a] - cx, G.Y[a] - cy) < 5200)
        if L < 800 or near < 600:
            continue
        r.update(poly=poly, len=L, near=near)
        if r["ref"] not in cand or near > cand[r["ref"]]["near"]:
            cand[r["ref"]] = r
    chosen = sorted(cand.values(), key=lambda r: -r["near"])[:MAX_ROUTES]
    if not chosen:
        return 0
    # the real stops that stand on each chosen route's real path, in the order it meets them
    stops_all = _stops(raw)
    lat0 = (bbox[0] + bbox[2]) / 2
    cell = {}
    for si, (la, lo, nm) in enumerate(stops_all):
        x, y = _metres(la, lo, lat0)
        cell.setdefault((int(x // 60), int(y // 60)), []).append((si, x, y))
    tr = m.get("transit") or {"lines": [], "stops": [], "new": []}
    stops = tr.setdefault("stops", [])
    lines = tr.setdefault("lines", [])
    used = {l["id"] for l in lines}
    at = {}
    for k, r in enumerate(sorted(chosen, key=lambda r: r["ref"])):
        pm_ = [_metres(la, lo, lat0) for la, lo in r["path"]]
        hits = {}
        for j in range(len(pm_) - 1):
            ax, ay = pm_[j]
            bx, by = pm_[j + 1]
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy or 1e-9
            for gx in range(int(min(ax, bx) // 60) - 1, int(max(ax, bx) // 60) + 2):
                for gy in range(int(min(ay, by) // 60) - 1, int(max(ay, by) // 60) + 2):
                    for si, sx, sy in cell.get((gx, gy), ()):
                        t = max(0.0, min(1.0, ((sx - ax) * dx + (sy - ay) * dy) / L2))
                        d = math.hypot(ax + t * dx - sx, ay + t * dy - sy)
                        if d <= STOP_M and (si not in hits or d < hits[si][0]):
                            hits[si] = (d, j + t)
        order = sorted(hits.items(), key=lambda kv: kv[1][1])
        poly = r["poly"]
        pset = set(poly)
        spec, seen = [], set()
        for si, (_d, _pos) in order:
            la, lo, nm = stops_all[si]
            try:
                X, Y = page(*pmap.project(la, lo, bbox, scale))
            except Exception:                                # noqa: BLE001
                continue
            n = G.nearest(X, Y)
            if n < 0 or n not in pset:
                n = min(poly, key=lambda q: (G.X[q] - X) ** 2 + (G.Y[q] - Y) ** 2)      # a stop a street over: the route's own vertex nearest it
                if (G.X[n] - X) ** 2 + (G.Y[n] - Y) ** 2 > 260 ** 2:
                    continue
            key = (nm.lower(), round(G.X[n] / 40), round(G.Y[n] / 40))
            if key in seen:
                continue
            seen.add(key)
            spec.append((key, nm, n))
        if len(spec) < 4:
            continue
        out = []
        for key, nm, n in spec:
            if key not in at:
                at[key] = len(stops)
                stops.append({"n": nm, "x": round(G.X[n], 1), "y": round(G.Y[n], 1), "l": []})
            out.append(at[key])
        lid = "bus" + re.sub(r"[^a-z0-9]", "", r["ref"].lower())
        while lid in used:
            lid += "x"
        used.add(lid)
        for i in out:
            if lid not in stops[i]["l"]:
                stops[i]["l"].append(lid)
        flat = []
        for n in poly:
            flat.extend((round(G.X[n], 1), round(G.Y[n], 1)))
        col = r["colour"] if re.match(r"^#[0-9a-fA-F]{6}$", r["colour"] or "") else PALETTE[k % len(PALETTE)]
        lines.append({"id": lid, "n": "Route " + r["ref"], "c": col, "k": "bus", "p": [flat], "s": out, "b": [out], "to": r["to"]})
    m["transit"] = tr
    return sum(1 for l in lines if l.get("k") == "bus")
