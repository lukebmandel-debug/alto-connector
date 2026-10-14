"""OpenStreetMap -> a compact street map for Alto's Mind Palace mode.

A Mind Palace draws a user's outline as buildings on a real city's streets. The
page draws the map as SVG, so this module turns a bounding box of OpenStreetMap
data into a small, projected, simplified JSON-able dict (streets, water, parks,
trails, rail lines, stations, landmarks). Pure standard library (urllib), no
shapely or numpy. Map data (c) OpenStreetMap contributors, ODbL: the dict
carries the attribution string and the page must show it.

  fetch_osm(bbox, cache_dir=None, timeout=180, landmarks=None)
        one Overpass query for the box (cached on disk when cache_dir is
        given); returns the raw Overpass JSON. bbox = (south, west, north, east)
  build_map(raw, bbox, place="", scale=1.0, majors=None, landmarks=None)
        raw Overpass JSON -> the map dict (see _build for the shape)
  geocode(query, timeout=30)
        Nominatim: {"lat", "lon", "bbox": [s, w, n, e], "name"} or None

Coordinates: equirectangular around the box centre, x east, y SOUTH (origin
top-left), units = map px, scale = px per metre, rounded to 1 decimal. Every
polyline/ring is clipped to the box, then Douglas-Peucker simplified.

Rings (water, parks, landmark outlines) are lists of points WITHOUT a repeated
closing point. Water rings are wound so that an outer ring has positive and a
hole negative shoelace area: fill them with fill-rule nonzero and overlapping
water polygons (a riverbank relation plus a natural=water way of the same
river) union instead of cancelling; for non-overlapping water even-odd gives
the same picture.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = "Alto-MindPalace/1.0 (+https://alto-connector.web.app)"
OVERPASS = "https://overpass-api.de/api/interpreter"
OVERPASS_FALLBACK = "https://overpass.kumi.systems/api/interpreter"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
ATTRIBUTION = "© OpenStreetMap contributors"

_BACKOFF = (5, 15, 30)            # seconds slept between attempts on one server
_RETRY_CODES = (429, 502, 503, 504)
_sleep = time.sleep               # tests replace this
SIZE_TARGET = 600_000             # bytes of compact JSON; above it k=4/5 streets are simplified harder

TOL = 0.8                         # Douglas-Peucker tolerance, px
TOL_MINOR = 1.2                   # k=4/5 streets when the output is too big
MIN_RING_AREA = 4.0               # px^2
MIN_LINE_LEN = 2.0                # px
MAJOR_LEN = 1500.0                # px of one secondary street name to be a "major"
STATION_DIST = 120.0              # px: same-named stations closer than this are one

_HIGHWAY_K = {
    "motorway": 0, "motorway_link": 0, "trunk": 0, "trunk_link": 0,
    "primary": 1, "primary_link": 1, "secondary": 2, "secondary_link": 2,
    "tertiary": 3, "tertiary_link": 3,
    "residential": 4, "unclassified": 4, "living_street": 4, "pedestrian": 4,
    "service": 5,
}
_TRAIL_HW = ("footway", "cycleway", "path")
_RAIL_KINDS = ("rail", "subway", "light_rail", "tram", "narrow_gauge", "monorail")
_RAIL_SKIP_SERVICE = ("yard", "siding", "spur", "crossover")
_ROUTE_KINDS = ("subway", "train", "light_rail", "tram", "railway")
_COLOURS = {
    "red": "#ff0000", "blue": "#0000ff", "green": "#008000", "orange": "#ffa500",
    "yellow": "#ffff00", "purple": "#800080", "black": "#000000", "white": "#ffffff",
    "grey": "#808080", "gray": "#808080", "brown": "#a52a2a", "pink": "#ffc0cb",
    "cyan": "#00ffff", "magenta": "#ff00ff", "gold": "#ffd700", "silver": "#c0c0c0",
    "navy": "#000080", "teal": "#008080", "maroon": "#800000", "lime": "#00ff00",
}


# --------------------------------------------------------------------------- HTTP

def _post_overpass(query: str, timeout: int) -> dict:
    """POST the query; retry 3x with backoff on 429/5xx/timeouts, then try the
    fallback server the same way. Raises RuntimeError when both give up."""
    body = urllib.parse.urlencode({"data": query}).encode()
    errors = []
    for url in (OVERPASS, OVERPASS_FALLBACK):
        for attempt in range(len(_BACKOFF)):
            try:
                req = urllib.request.Request(
                    url, data=body,
                    headers={"User-Agent": UA, "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    data = json.loads(r.read().decode("utf-8"))
                remark = str(data.get("remark", ""))
                if "runtime error" in remark or "out of memory" in remark:
                    raise TimeoutError(remark)          # a partial answer is worse than none
                return data
            except urllib.error.HTTPError as e:
                if e.code not in _RETRY_CODES:
                    raise RuntimeError("Overpass HTTP %s from %s" % (e.code, url)) from e
                errors.append("%s HTTP %s" % (url, e.code))
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                errors.append("%s %s" % (url, e))
            if attempt < len(_BACKOFF) - 1:
                _sleep(_BACKOFF[attempt])
    raise RuntimeError("Overpass failed: " + "; ".join(errors[-4:]))


def _ql_regex(name: str) -> str:
    """name as an exact regex literal inside an Overpass QL string."""
    out = []
    for ch in name:
        if ch in "\\.^$*+?()[]{}|":
            out.append("\\\\" + ch)       # QL unescapes \\ to \, so the regex sees \.
        elif ch == '"':
            out.append('\\"')
        else:
            out.append(ch)
    return "".join(out)


def build_query(bbox, landmarks=None, timeout: int = 180) -> str:
    b = "(%r,%r,%r,%r)" % tuple(float(v) for v in bbox)
    hw = "|".join(k for k in _HIGHWAY_K if k != "service")
    q = [
        "[out:json][timeout:%d];" % timeout,
        # streets and named trails
        "(",
        '  way[highway~"^(%s)$"][area!=yes]%s;' % (hw, b),
        "  way[highway=service][name][area!=yes]%s;" % b,
        '  way[highway~"^(footway|cycleway|path)$"][name][area!=yes]%s;' % b,
        ");", "out geom;",
        # rail ways
        "(",
        '  way[railway~"^(%s)$"][service!~"^(%s)$"]%s;'
        % ("|".join(_RAIL_KINDS), "|".join(_RAIL_SKIP_SERVICE), b),
        ");", "out geom;",
        # route relations: members only (names/refs/colours, stops); the stop nodes in the box
        'rel[route~"^(%s)$"]%s->.routes;' % ("|".join(_ROUTE_KINDS), b),
        ".routes out body;",
        "node(r.routes)%s;" % b, "out body;",
        # stations
        "(",
        "  node[railway=station]%s;" % b, "  node[public_transport=station]%s;" % b,
        "  way[railway=station]%s;" % b, "  rel[railway=station]%s;" % b,
        ");", "out center;",
        # water
        "(",
    ]
    for t in ("way", "rel"):
        for f in ("[natural=water]", "[waterway=riverbank]", "[water=river]"):
            q.append("  %s%s%s;" % (t, f, b))
    q += ["  way[waterway=river]%s;" % b, ");", "out geom;", "("]
    for t in ("way", "rel"):
        q.append('  %s[leisure~"^(park|garden)$"]%s;' % (t, b))
        q.append('  %s[landuse~"^(grass|recreation_ground|cemetery)$"]%s;' % (t, b))
    q += [");", "out geom;"]
    names = [n for n in (landmarks or []) if n]
    if names:
        q.append("(")
        for n in names:
            q.append('  nwr["name"~"^%s$",i]%s;' % (_ql_regex(n), b))
        q += [");", "out geom;"]
    return "\n".join(q)


def fetch_osm(bbox, cache_dir=None, timeout=180, landmarks=None) -> dict:
    """Raw Overpass JSON for bbox = (south, west, north, east). With cache_dir the
    answer is stored as osm-<rounded bbox>[-<landmark hash>].json and reused."""
    bbox = tuple(float(v) for v in bbox)
    path = None
    if cache_dir:
        tag = "osm-%.4f_%.4f_%.4f_%.4f" % bbox
        if landmarks:
            tag += "-" + hashlib.sha1("\n".join(sorted(landmarks)).encode()).hexdigest()[:8]
        path = Path(cache_dir) / (tag + ".json")
        if path.exists():
            try:
                return json.loads(path.read_text("utf-8"))
            except (OSError, ValueError):
                pass
    raw = _post_overpass(build_query(bbox, landmarks, timeout), timeout)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(raw, separators=(",", ":")), "utf-8")
        os.replace(tmp, path)
    return raw


def geocode(query: str, timeout: int = 30):
    """Nominatim lookup of one place: {"lat", "lon", "bbox": [s, w, n, e], "name"} or None."""
    url = NOMINATIM + "?" + urllib.parse.urlencode({"format": "json", "limit": 1, "q": query})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        rows = json.loads(r.read().decode("utf-8"))
    if not rows:
        return None
    r0 = rows[0]
    bb = r0.get("boundingbox") or []           # Nominatim: [south, north, west, east]
    lat, lon = float(r0["lat"]), float(r0["lon"])
    if len(bb) == 4:
        s, n, w, e = (float(v) for v in bb)
    else:
        s = n = lat
        w = e = lon
    return {"lat": lat, "lon": lon, "bbox": [s, w, n, e], "name": r0.get("display_name", "")}


# ------------------------------------------------------------------- geometry

def project(lat: float, lon: float, bbox, scale: float = 1.0):
    """(x, y) map px for a lat/lon: equirectangular around the box centre."""
    s, w, n, _e = bbox
    kx = math.cos(math.radians((s + n) / 2)) * 111320 * scale
    return ((lon - w) * kx, (n - lat) * 110574 * scale)


def _projector(bbox, scale):
    s, w, n, e = bbox
    kx = math.cos(math.radians((s + n) / 2)) * 111320 * scale
    ky = 110574 * scale
    return (lambda p: ((p[1] - w) * kx, (n - p[0]) * ky)), (e - w) * kx, (n - s) * ky


def _seg_d2(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return (px - ax) ** 2 + (py - ay) ** 2
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    cx, cy = ax + t * dx, ay + t * dy
    return (px - cx) ** 2 + (py - cy) ** 2


def douglas_peucker(pts, tol: float):
    """Open polyline simplified so no dropped point is farther than tol from the result."""
    n = len(pts)
    if n < 3:
        return list(pts)
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    t2 = tol * tol
    while stack:
        i, j = stack.pop()
        ax, ay = pts[i]
        bx, by = pts[j]
        best, bd = -1, t2
        for m in range(i + 1, j):
            d = _seg_d2(pts[m][0], pts[m][1], ax, ay, bx, by)
            if d > bd:
                best, bd = m, d
        if best >= 0:
            keep[best] = True
            stack.append((i, best))
            stack.append((best, j))
    return [p for p, k in zip(pts, keep) if k]


def simplify_ring(ring, tol: float):
    """Douglas-Peucker for a closed ring (no repeated closing point): split at the
    point farthest from the first so the ring stays closed."""
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    n = len(ring)
    if n <= 3:
        return list(ring)
    x0, y0 = ring[0]
    far = max(range(1, n), key=lambda i: (ring[i][0] - x0) ** 2 + (ring[i][1] - y0) ** 2)
    a = douglas_peucker(ring[:far + 1], tol)
    b = douglas_peucker(ring[far:] + [ring[0]], tol)
    return a[:-1] + b[:-1]


def ring_area(ring) -> float:
    """Signed shoelace area (positive = clockwise on screen, y down)."""
    a = 0.0
    n = len(ring)
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        a += x0 * y1 - x1 * y0
    return a / 2


def _clip_edge(poly, axis: int, val: float, keep_ge: bool):
    out = []
    n = len(poly)
    if not n:
        return out

    def inside(p):
        return p[axis] >= val if keep_ge else p[axis] <= val

    def cross(p, q):
        t = (val - p[axis]) / (q[axis] - p[axis])
        pt = [p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])]
        pt[axis] = val
        return (pt[0], pt[1])

    prev = poly[-1]
    for cur in poly:
        if inside(cur):
            if not inside(prev):
                out.append(cross(prev, cur))
            out.append(cur)
        elif inside(prev):
            out.append(cross(prev, cur))
        prev = cur
    return out


def clip_polygon(ring, w: float, h: float):
    """Sutherland-Hodgman clip of a ring to the rectangle [0,w] x [0,h]; [] if nothing is left."""
    poly = [tuple(p) for p in ring]
    for axis, val, ge in ((0, 0.0, True), (0, w, False), (1, 0.0, True), (1, h, False)):
        poly = _clip_edge(poly, axis, val, ge)
        if not poly:
            return []
    return poly if len(poly) >= 3 else []


def _liang_barsky(x0, y0, x1, y1, w, h):
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0), (dx, w - x0), (-dy, y0), (dy, h - y0)):
        if p == 0:
            if q < 0:
                return None
        else:
            r = q / p
            if p < 0:
                if r > t1:
                    return None
                t0 = max(t0, r)
            else:
                if r < t0:
                    return None
                t1 = min(t1, r)
    return t0, t1


def clip_polyline(pts, w: float, h: float):
    """Pieces of a polyline inside [0,w] x [0,h]; a line that leaves and re-enters is split."""
    pieces, cur = [], None
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        r = _liang_barsky(x0, y0, x1, y1, w, h)
        if r is None:
            if cur is not None:
                pieces.append(cur)
                cur = None
            continue
        t0, t1 = r
        a = (x0 + t0 * (x1 - x0), y0 + t0 * (y1 - y0))
        b = (x0 + t1 * (x1 - x0), y0 + t1 * (y1 - y0))
        if cur is not None and t0 > 1e-12:
            pieces.append(cur)
            cur = None
        if cur is None:
            cur = [a]
        cur.append(b)
        if t1 < 1.0:
            pieces.append(cur)
            cur = None
    if cur is not None:
        pieces.append(cur)
    out = []
    for p in pieces:
        q = [p[0]]
        for pt in p[1:]:
            if pt != q[-1]:
                q.append(pt)
        if len(q) >= 2:
            out.append(q)
    return out


def poly_len(pts) -> float:
    return sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
               for i in range(len(pts) - 1))


def assemble_rings(ways):
    """Join member ways (lists of (lat, lon), any order, any direction) end to end into
    closed rings. A chain that never closes is dropped. Rings have no repeated end point."""
    segs = [list(w) for w in ways if len(w) >= 2]
    ends: dict = {}
    for i, s in enumerate(segs):
        ends.setdefault(s[0], []).append(i)
        ends.setdefault(s[-1], []).append(i)
    used = [False] * len(segs)
    rings = []
    for i in range(len(segs)):
        if used[i]:
            continue
        used[i] = True
        chain = list(segs[i])
        while chain[0] != chain[-1]:
            nxt = next((j for j in ends.get(chain[-1], ()) if not used[j]), None)
            if nxt is None:
                break
            used[nxt] = True
            s = segs[nxt]
            if s[0] != chain[-1]:
                s = s[::-1]
            chain.extend(s[1:])
        if chain[0] == chain[-1] and len(chain) >= 4:
            rings.append(chain[:-1])
    return rings


def merge_ways(items):
    """Join ways that share an endpoint and a key into longer polylines. items are
    {"key": hashable, "pts": [(lat, lon), ...], optional "min_cos"}; ways merge only if
    their keys are equal. At a junction the way that continues most straight is taken
    (and, when item["min_cos"] is set, only if its turn is gentler than that cosine).
    The merged item keeps the first way's other fields."""
    n = len(items)
    idx: dict = {}
    for i, it in enumerate(items):
        k = it["key"]
        idx.setdefault((k, it["pts"][0]), []).append(i)
        idx.setdefault((k, it["pts"][-1]), []).append(i)
    used = [False] * n

    def direction(a, b):
        return (b[1] - a[1]) * 0.77, b[0] - a[0]     # roughly equal-scale; only angles matter

    def extend(chain, key, min_cos):
        while True:
            end = chain[-1]
            best, best_c, best_pts = None, None, None
            for j in idx.get((key, end), ()):
                if used[j]:
                    continue
                p = items[j]["pts"]
                if p[0] != end:
                    p = p[::-1]
                if len(chain) >= 2 and len(p) >= 2:
                    d0, d1 = direction(chain[-2], chain[-1]), direction(p[0], p[1])
                    m = math.hypot(*d0) * math.hypot(*d1)
                    c = (d0[0] * d1[0] + d0[1] * d1[1]) / m if m else 1.0
                else:
                    c = 1.0
                if best is None or c > best_c:
                    best, best_c, best_pts = j, c, p
            if best is None or (min_cos is not None and best_c < min_cos):
                return
            used[best] = True
            chain.extend(best_pts[1:])

    out = []
    for i in range(n):
        if used[i]:
            continue
        used[i] = True
        it = items[i]
        chain = list(it["pts"])
        mc = it.get("min_cos")
        extend(chain, it["key"], mc)
        chain.reverse()
        extend(chain, it["key"], mc)
        m = dict(it)
        m["pts"] = chain
        out.append(m)
    return out


def dedupe_stations(stations, dist: float = STATION_DIST):
    """Stations ({"n","x","y","k","l"}) with the same name (any case) closer than dist px
    become one (first position wins, line lists are united)."""
    out = []
    for s in stations:
        for o in out:
            if (o["n"].lower() == s["n"].lower()
                    and math.hypot(o["x"] - s["x"], o["y"] - s["y"]) < dist):
                for line in s.get("l", []):
                    if line not in o["l"]:
                        o["l"].append(line)
                break
        else:
            out.append({**s, "l": list(s.get("l", []))})
    return out


def pick_majors(streets, majors=None):
    """Names that get an always-on label. `streets` = [{"n","k","len"}] (merged lengths in
    px). With `majors`, those names that occur (spelled as in the data); otherwise every
    named street with k <= 1 and k == 2 streets whose total length >= 1500 px."""
    spelled: dict = {}
    total2: dict = {}
    for s in streets:
        n = s.get("n") or ""
        if not n:
            continue
        spelled.setdefault(n.lower(), n)
        if s["k"] == 2:
            total2[n.lower()] = total2.get(n.lower(), 0.0) + s.get("len", 0.0)
    if majors is not None:
        seen, out = set(), []
        for m in majors:
            lo = str(m).lower()
            if lo in spelled and lo not in seen:
                seen.add(lo)
                out.append(spelled[lo])
        return out
    keys = {(s["n"]).lower() for s in streets if s.get("n") and s["k"] <= 1}
    keys |= {k for k, v in total2.items() if v >= MAJOR_LEN}
    return sorted((spelled[k] for k in keys), key=str.lower)


# ------------------------------------------------------------------ OSM parsing

def _pts(geom):
    """[(lat, lon)] of an Overpass `geometry` list (nodes outside an `out geom(bbox)` are null)."""
    return [(g["lat"], g["lon"]) for g in (geom or ()) if g]


def _is_set(v) -> bool:
    return v not in (None, "", "no")


def _colour(v) -> str:
    v = (v or "").strip().lower()
    if re.fullmatch(r"#[0-9a-f]{6}", v):
        return v
    if re.fullmatch(r"#[0-9a-f]{3}", v):
        return "#" + "".join(c * 2 for c in v[1:])
    return _COLOURS.get(v, "")


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def _line_name(tags: dict) -> str:
    """A route relation's line name without its 'A => B' direction suffix."""
    name = (tags.get("name") or "").strip()
    if re.search(r"=>|→|->|⇒|\bto\b", name) and ":" in name:
        name = name.split(":", 1)[0].strip()
    if not name:
        name = (tags.get("ref") or "").strip()
    return name


def _center(el):
    """(lat, lon) of a node, or of an element's center / geometry average."""
    if "lat" in el and "lon" in el:
        return el["lat"], el["lon"]
    c = el.get("center")
    if c:
        return c["lat"], c["lon"]
    pts = _pts(el.get("geometry"))
    for m in el.get("members") or ():
        pts += _pts(m.get("geometry"))
    if pts:
        return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
    return None


def _rings_of(el):
    """[(ring, inner)] of a way (closed ways only) or a multipolygon relation."""
    if el["type"] == "way":
        p = _pts(el.get("geometry"))
        return [(p[:-1], False)] if len(p) >= 4 and p[0] == p[-1] else []
    if el["type"] == "relation":
        outer, inner = [], []
        for m in el.get("members") or ():
            if m.get("type") != "way":
                continue
            p = _pts(m.get("geometry"))
            (inner if m.get("role") == "inner" else outer).append(p)
        return ([(r, False) for r in assemble_rings(outer)]
                + [(r, True) for r in assemble_rings(inner)])
    return []


def _merge_elements(raw: dict) -> dict:
    """{(type, id): element}: duplicates (an element fetched by two clauses, once with a
    center and once with geometry) are united, keeping the geometry-bearing version."""
    els: dict = {}
    for el in raw.get("elements", ()):
        if "type" not in el or "id" not in el:
            continue
        k = (el["type"], el["id"])
        old = els.get(k)
        if old is None:
            els[k] = el
        else:
            if "geometry" in el or "members" in el and "members" not in old:
                old, el = el, old
            old = dict(old)
            for f in ("center", "lat", "lon"):
                if f not in old and f in el:
                    old[f] = el[f]
            old["tags"] = {**el.get("tags", {}), **old.get("tags", {})}
            els[k] = old
    return els


def _fnum(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _r1(v: float):
    v = round(v, 1)
    return int(v) if v == int(v) else v


def _flat(pts):
    out = []
    for x, y in pts:
        out += [_r1(x), _r1(y)]
    return out


def _dedup_consecutive(pts):
    out = []
    for p in pts:
        p = (round(p[0], 1), round(p[1], 1))
        if not out or p != out[-1]:
            out.append(p)
    return out


def _lines(items, proj, W, H, tol_of, sink):
    """merge -> project -> clip -> simplify; sink(item, simplified points, raw length)."""
    for it in merge_ways(items):
        pts = [proj(p) for p in it["pts"]]
        for piece in clip_polyline(pts, W, H):
            raw_len = poly_len(piece)
            s = _dedup_consecutive(douglas_peucker(piece, tol_of(it)))
            if len(s) >= 2 and poly_len(s) >= MIN_LINE_LEN:
                sink(it, s, raw_len)


def _ring_out(ring, inner, proj, W, H, tol):
    """lat/lon ring -> clipped, simplified, wound [x,y,...] list or None."""
    return _ring_out_xy([proj(p) for p in ring], inner, W, H, tol)


def _ring_out_xy(pts, inner, W, H, tol):
    """Projected ring -> wound, clipped, simplified point list or None."""
    if len(pts) < 3:
        return None
    a = ring_area(pts)
    if (a < 0) != inner:                       # outer: positive area, hole: negative
        pts.reverse()
    pts = clip_polygon(pts, W, H)
    if len(pts) < 3:
        return None
    pts = _dedup_consecutive(simplify_ring(pts, tol))
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    if len(pts) < 3 or abs(ring_area(pts)) < MIN_RING_AREA:
        return None
    return pts


# --------------------------------------------------------------------------- a wide river

WIDE_RIVER_M = 350.0              # metres across: a river this wide is the edge of a city, not a street to cross
FAR_BANK_SHARE = 0.4              # the dropped bank holds at most this share of the streets


def _main_piece(rivers, name):
    """The longest piece of a named river: [(x, y), ...] real px, with its length."""
    best, bl = None, 0.0
    for r in rivers:
        if r.get("n") != name:
            continue
        p = [(r["p"][i], r["p"][i + 1]) for i in range(0, len(r["p"]) - 1, 2)]
        L = poly_len(p)
        if L > bl:
            best, bl = p, L
    return best, bl


def _in_ring(pt, ring):
    x, y = pt
    c = False
    n = len(ring)
    for i in range(n):
        (x0, y0), (x1, y1) = ring[i], ring[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


def _side_of(line):
    """f(x, y) -> signed distance-ish side of a polyline (positive on its left in screen
    coordinates, by the nearest piece of the line, which is extended past its ends)."""
    segs = list(zip(line, line[1:]))

    def f(x, y):
        best, bd = 0.0, 1e30
        for (ax, ay), (bx, by) in segs:
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy or 1e-9
            t = ((x - ax) * dx + (y - ay) * dy) / L2
            tc = max(0.0, min(1.0, t))
            d = (ax + tc * dx - x) ** 2 + (ay + tc * dy - y) ** 2
            if d < bd:
                best, bd = ((x - ax) * dy - (y - ay) * dx) / math.sqrt(L2), d
        return best
    return f


def _keep_side(pts, f, keep):
    """The parts of a polyline on the kept side of f (keep = +1 / -1), cut where it crosses."""
    out, cur = [], []
    prev, pv = None, None
    for q in pts:
        v = f(*q) * keep
        if prev is not None and (pv > 0) != (v > 0):
            lo, hi = 0.0, 1.0                                  # where it crosses: bisect
            for _ in range(14):
                mid = (lo + hi) / 2
                x, y = prev[0] + (q[0] - prev[0]) * mid, prev[1] + (q[1] - prev[1]) * mid
                if (f(x, y) * keep > 0) == (pv > 0):
                    lo = mid
                else:
                    hi = mid
            c = (prev[0] + (q[0] - prev[0]) * hi, prev[1] + (q[1] - prev[1]) * hi)
            if pv > 0:
                cur.append(c)
                out.append(cur)
                cur = []
            else:
                cur = [c]
        if v > 0:
            cur.append(q)
        prev, pv = q, v
    if len(cur) >= 2:
        out.append(cur)
    return [c for c in out if len(c) >= 2 and poly_len(c) >= MIN_LINE_LEN]


def _across_wide_river(out, scale):
    """A wide named river that runs across the box (the Delaware at Philadelphia) is the
    edge of the city: the land across it is cut away (it would otherwise add a second
    city's streets to the grid) and out["bank"] = {n, w, side} says which edge it is.
    Only when the far bank holds a minority of the streets; otherwise the box is left alone."""
    W, H = out["W"], out["H"]
    best = None
    for name in {r.get("n") for r in out["rivers"] if r.get("n")}:
        line, L = _main_piece(out["rivers"], name)
        if not line or L < 0.6 * min(W, H):
            continue
        # how wide: the area of the water polygon it runs in, over its length
        mids = [line[len(line) // 4], line[len(line) // 2], line[3 * len(line) // 4]]
        area = 0.0
        for ring in out["water"]:
            rp = [(ring[i], ring[i + 1]) for i in range(0, len(ring) - 1, 2)]
            if sum(_in_ring(q, rp) for q in mids) >= 2:
                area = max(area, abs(ring_area(rp)))
        width = area / L if L else 0.0
        if width >= WIDE_RIVER_M * scale and (best is None or width > best[0]):
            best = (width, name, line)
    if not best:
        return out
    width, name, line = best
    f = _side_of(line)
    side_len = [0.0, 0.0]
    for s in out["streets"]:
        p = s["p"]
        for i in range(0, len(p) - 2, 2):
            mx, my = (p[i] + p[i + 2]) / 2, (p[i + 1] + p[i + 3]) / 2
            side_len[1 if f(mx, my) > 0 else 0] += math.hypot(p[i + 2] - p[i], p[i + 3] - p[i + 1])
    tot = sum(side_len)
    if not tot:
        return out
    minor = 1 if side_len[1] < side_len[0] else 0
    if side_len[minor] / tot > FAR_BANK_SHARE:
        return out
    keep = -1 if minor == 1 else 1

    def kept(x, y):
        return f(x, y) * keep > 0

    def lines_of(items, key="p"):
        res = []
        for it in items:
            p = it[key]
            pts = [(p[i], p[i + 1]) for i in range(0, len(p) - 1, 2)]
            for c in _keep_side(pts, f, keep):
                res.append({**it, key: _flat(c)})
        return res
    # the bridges across it (a street or walkway named ... Bridge that is cut by the river's line):
    # the name and where it leaves the kept bank, for the grid to draw across the river
    bridges, seen_b = [], set()
    for it in out["streets"] + out["trails"]:
        nm = re.sub(r"\s*(\(.*?\)|walkway.*|pedestrian.*|path.*)$", "", it.get("n") or "", flags=re.I).strip()
        if not re.search(r"\bbridge\b", nm, re.I) or nm.lower() in seen_b:
            continue
        pts = [(it["p"][i], it["p"][i + 1]) for i in range(0, len(it["p"]) - 1, 2)]
        sides = {f(*q) * keep > 0 for q in pts}
        if len(sides) < 2:
            continue                                          # it does not reach across
        kp = max((c for c in _keep_side(pts, f, keep)), key=poly_len, default=None)
        if kp:
            seen_b.add(nm.lower())
            far = max(kp, key=lambda q: abs(f(*q)))           # the end farthest from the river's line
            bridges.append({"n": nm, "at": [round(far[0], 1), round(far[1], 1)]})
    out["streets"] = lines_of(out["streets"])
    out["trails"] = lines_of(out["trails"])
    out["rails"] = lines_of(out["rails"])
    out["parks"] = [pk for pk in out["parks"] if pk["r"] and kept(*_ring_mid(pk["r"][0]))]
    out["stations"] = [s for s in out["stations"] if kept(s["x"], s["y"])]
    out["landmarks"] = [l for l in out["landmarks"] if kept(l["x"], l["y"])]
    keep_rings = []
    for ring in out["water"]:
        rp = [(ring[i], ring[i + 1]) for i in range(0, len(ring) - 1, 2)]
        if abs(ring_area(rp)) > 100000 * scale * scale or kept(*_ring_mid(ring)):
            keep_rings.append(ring)
    out["water"] = keep_rings
    # which edge of the box the river is: where it lies from the middle of the kept streets
    kx = ky = n_ = 0.0
    for s in out["streets"]:
        for i in range(0, len(s["p"]) - 1, 2):
            kx += s["p"][i]; ky += s["p"][i + 1]; n_ += 1
    kx, ky = kx / max(1, n_), ky / max(1, n_)
    mx, my = min(_dense(line), key=lambda q: (q[0] - kx) ** 2 + (q[1] - ky) ** 2)
    dx, dy = (mx - kx) / max(1.0, W), (my - ky) / max(1.0, H)
    edge = ("e" if dx > 0 else "w") if abs(dx) >= abs(dy) else ("s" if dy > 0 else "n")
    out["bank"] = {"n": name, "w": round(width), "side": edge, "bridges": bridges}
    return out


def _dense(line, step=50.0):
    """Points along a polyline about `step` apart."""
    out = []
    for a, b in zip(line, line[1:]):
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) // step))
        out += [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n)]
    return out + [line[-1]]


def _ring_mid(ring):
    xs, ys = ring[0::2], ring[1::2]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _build(raw, bbox, place, scale, majors, landmarks, tol_minor):
    bbox = tuple(float(v) for v in bbox)
    proj, Wf, Hf = _projector(bbox, scale)
    els = _merge_elements(raw)

    # route relations: which lines a rail way / a station belongs to
    node_name = {i: (e.get("tags") or {}).get("name", "")
                 for (t, i), e in els.items() if t == "node"}
    routes = []
    way_routes: dict = {}
    for (t, i), e in sorted(els.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        tg = e.get("tags") or {}
        if t != "relation" or tg.get("type") != "route" or tg.get("route") not in _ROUTE_KINDS:
            continue
        r = {"n": _line_name(tg), "r": (tg.get("ref") or "").strip(), "c": _colour(tg.get("colour")),
             "stops": set(), "names": set()}
        for m in e.get("members") or ():
            if m.get("type") == "way":
                way_routes.setdefault(m["ref"], []).append(r)
            elif m.get("role", "").split("_")[0] in ("stop", "station", "platform", ""):
                r["stops"].add((m.get("type"), m.get("ref")))
                if m.get("type") == "node" and node_name.get(m.get("ref")):
                    r["names"].add(_norm(node_name[m["ref"]]))
        routes.append(r)

    lm_names = {n.lower() for n in (landmarks or []) if n}
    streets_in, trails_in, rivers_in, rails_in = [], [], [], []
    water_in, parks_in, stations_in, lm_cand = [], [], [], {}

    for (t, i), e in els.items():
        tg = e.get("tags") or {}
        if t == "way":
            pts = _pts(e.get("geometry"))
            hw = tg.get("highway")
            rw = tg.get("railway")
            if hw and len(pts) >= 2 and tg.get("area") != "yes":
                name = tg.get("name", "")
                if hw in _TRAIL_HW:
                    if name and tg.get("footway") not in ("sidewalk", "crossing"):
                        trails_in.append({"key": (name,), "pts": pts, "n": name, "min_cos": 0.0})
                elif hw in _HIGHWAY_K:
                    k = _HIGHWAY_K[hw]
                    if k == 5 and not name:
                        continue
                    b = 1 if _is_set(tg.get("bridge")) else 0
                    tn = 1 if _is_set(tg.get("tunnel")) else 0
                    it = {"key": (name, k, b, tn), "pts": pts, "n": name, "k": k, "b": b, "t": tn}
                    if not name:
                        it["min_cos"] = 0.5
                    streets_in.append(it)
            elif rw in _RAIL_KINDS and len(pts) >= 2:
                if tg.get("service") in _RAIL_SKIP_SERVICE or tg.get("abandoned") == "yes" \
                        or tg.get("disused") == "yes":
                    continue
                layer = int(_fnum(tg.get("layer")))
                bridge, tunnel = _is_set(tg.get("bridge")), _is_set(tg.get("tunnel"))
                el_ = bridge or (layer > 0 and not tunnel)
                ug = tunnel or (layer < 0 and not bridge) or (rw == "subway" and not bridge)
                if el_:
                    ug = bool(tunnel)
                rs = sorted(way_routes.get(i, ()), key=lambda r: (not r["c"], r["n"], r["r"]))
                if rs:
                    n = rs[0]["n"]
                    c = rs[0]["c"] or next((r["c"] for r in rs if r["c"]), "")
                    refs = []
                    for r in rs:
                        if r["r"] and r["r"] not in refs:
                            refs.append(r["r"])
                    ref = "/".join(refs)
                else:
                    n, ref, c = tg.get("name", ""), tg.get("ref", ""), _colour(tg.get("colour"))
                rails_in.append({"key": (n, ref, c, rw, int(ug), int(el_)), "pts": pts, "n": n,
                                 "r": ref, "c": c, "k": rw, "u": int(ug), "e": int(el_),
                                 "min_cos": 0.0})
            if tg.get("waterway") == "river" and tg.get("name") and len(pts) >= 2:
                rivers_in.append({"key": (tg["name"],), "pts": pts, "n": tg["name"]})
        if (tg.get("natural") == "water" or tg.get("waterway") == "riverbank"
                or tg.get("water") == "river") and t in ("way", "relation"):
            water_in.append(e)
        if (tg.get("leisure") in ("park", "garden")
                or tg.get("landuse") in ("grass", "recreation_ground", "cemetery")) \
                and t in ("way", "relation"):
            parks_in.append(e)
        rail_station = tg.get("railway") == "station" or (
            tg.get("public_transport") == "station"
            and any(tg.get(m) == "yes" for m in ("train", "subway", "light_rail", "tram")))
        if rail_station and tg.get("name"):
            stations_in.append((t, i, e))
        nm = tg.get("name", "").lower()
        if nm in lm_names and not (tg.get("highway") or tg.get("waterway")
                                   or tg.get("railway") in _RAIL_KINDS
                                   or tg.get("type") == "route"):
            lm_cand.setdefault(nm, []).append((t, i, e))

    # -- streets / trails / rivers / rails
    def tol_street(it):
        return tol_minor if it["k"] >= 4 else TOL

    streets, trails, rivers, rails = [], [], [], []
    merged_street_len = []

    def add_street(it, s, raw_len):
        d = {"n": it["n"], "k": it["k"], "p": _flat(s)}
        if it["b"]:
            d["b"] = 1
        if it["t"]:
            d["t"] = 1
        streets.append(d)
        merged_street_len.append({"n": it["n"], "k": it["k"], "len": raw_len})

    _lines(streets_in, proj, Wf, Hf, tol_street, add_street)
    _lines(trails_in, proj, Wf, Hf, lambda it: TOL,
           lambda it, s, ln: trails.append({"n": it["n"], "p": _flat(s)}))
    _lines(rivers_in, proj, Wf, Hf, lambda it: TOL,
           lambda it, s, ln: rivers.append({"n": it["n"], "p": _flat(s)}))

    def add_rail(it, s, ln):
        d = {"n": it["n"], "r": it["r"], "c": it["c"], "k": it["k"]}
        if it["u"]:
            d["u"] = 1
        if it["e"]:
            d["e"] = 1
        d["p"] = _flat(s)
        rails.append(d)

    _lines(rails_in, proj, Wf, Hf, lambda it: TOL, add_rail)
    streets.sort(key=lambda d: -d["k"])

    # -- water and parks
    water, seen = [], set()
    for e in water_in:
        for ring, inner in _rings_of(e):
            r = _ring_out(ring, inner, proj, Wf, Hf, TOL)
            if r:
                key = tuple(sorted(r))
                if key not in seen:
                    seen.add(key)
                    water.append(_flat(r))
    parks = []
    for e in parks_in:
        rs = [r for r in (_ring_out(ring, inner, proj, Wf, Hf, TOL)
                          for ring, inner in _rings_of(e)) if r]
        if rs:
            parks.append({"n": (e.get("tags") or {}).get("name", ""), "r": [_flat(r) for r in rs]})

    # -- stations
    stations = []
    for t, i, e in stations_in:
        c = _center(e)
        if not c:
            continue
        x, y = proj(c)
        if not (0 <= x <= Wf and 0 <= y <= Hf):
            continue
        tg = e.get("tags") or {}
        kind = tg.get("station") or ("subway" if tg.get("subway") == "yes" else
                                     "light_rail" if tg.get("light_rail") == "yes" else
                                     "tram" if tg.get("tram") == "yes" else "rail")
        nn = _norm(tg["name"])
        lines = []
        for r in routes:
            if ((t, i) in r["stops"] or nn in r["names"]) and (r["n"] or r["r"]):
                lab = r["n"] or r["r"]
                if lab not in lines:
                    lines.append(lab)
        stations.append({"n": tg["name"], "x": round(x, 1), "y": round(y, 1), "k": kind, "l": lines})
    stations = [{**s, "x": _r1(s["x"]), "y": _r1(s["y"])} for s in dedupe_stations(stations)]

    # -- landmarks: one per requested name; an outline beats a point, the biggest outline wins
    landmark_out, taken = [], set()
    for want in (landmarks or []):
        best = None
        for t, i, e in lm_cand.get(want.lower(), []):
            c = _center(e)
            if not c:
                continue
            rings = [[proj(p) for p in ring] for ring, inner in _rings_of(e) if not inner]
            area = max((abs(ring_area(r)) for r in rings), default=0.0)
            score = (1 if rings else 0, area)
            if best is None or score > best[0]:
                best = (score, t, i, e, rings, c)
        if best is None or best[1:3] in taken:
            continue
        _s, t, i, e, rings, c = best
        outs = [r for r in (_ring_out_xy(r, False, Wf, Hf, 0.5) for r in rings) if r]
        if outs:
            big = max(outs, key=lambda r: abs(ring_area(r)))
            cx = sum(p[0] for p in big) / len(big)
            cy = sum(p[1] for p in big) / len(big)
        elif rings:
            continue                                   # outline entirely outside the box
        else:
            cx, cy = proj(c)
            if not (0 <= cx <= Wf and 0 <= cy <= Hf):
                continue
        taken.add((t, i))
        landmark_out.append({"n": (e.get("tags") or {}).get("name", want),
                             "x": _r1(cx), "y": _r1(cy), "r": [_flat(r) for r in outs]})

    out = {
        "v": 1, "place": place, "bbox": [bbox[0], bbox[1], bbox[2], bbox[3]], "scale": scale,
        "W": int(math.ceil(Wf)), "H": int(math.ceil(Hf)),
        "attribution": ATTRIBUTION,
        "water": water, "rivers": rivers, "parks": parks, "streets": streets,
        "trails": trails, "rails": rails, "stations": stations, "landmarks": landmark_out,
        "majors": pick_majors(merged_street_len, majors),
    }
    return _across_wide_river(out, scale)


def build_map(raw, bbox, place="", scale=1.0, majors=None, landmarks=None) -> dict:
    """Raw Overpass JSON -> the compact map dict:

      v, place, bbox [s,w,n,e], scale, W, H (px), attribution,
      water   [[x,y,...] closed rings, outer and hole],
      rivers  [{n, p}]            named river centre-lines (labels only),
      parks   [{n, r: [ring,...]}],
      streets [{n, k, p, b?, t?}] k 0 motorway .. 4 residential, 5 named service,
      trails  [{n, p}],
      rails   [{n, r, c, k, p, u?, e?}],
      stations [{n, x, y, k, l: [line names]}],
      landmarks [{n, x, y, r: [ring,...]}],
      majors  [street names that are always labelled].
    """
    out = _build(raw, bbox, place, scale, majors, landmarks, TOL)
    if len(json.dumps(out, separators=(",", ":"), ensure_ascii=False).encode()) > SIZE_TARGET:
        out = _build(raw, bbox, place, scale, majors, landmarks, TOL_MINOR)
    return out
