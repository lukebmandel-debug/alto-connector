"""An INVENTED Memory Palace city, built from scratch (rules doc section 14): the user's lists, not OpenStreetMap, make the
map dict `m` that palace_map.build_map would have made (1 px = 1 m), so everything after build_map (palace_grid.grid and
the rest) runs unchanged. Pure: no network, no clock, no randomness beyond a seeded generator.

    m = invent_city(spec)                 # raises InventError (a list of plain-words problems) for a bad spec
    rep = check(spec)                     # build + the gate: {"pass", "score", "checks": [eight plain checks], ...}
    spec2 = apply_fix(spec, rep["checks"][k]["fix"])     # the one-tap fix for a failing check

Who builds it (Luke's pick "Both"): Claude (Bass, or the user's own Claude through the invent_city tool) drafts a spec from
a description; the free manual editor tunes the same spec with templates and one-tap fixes, so a city never needs Claude.
The picker order (TEMPLATES): Grid (the default), Grid + diagonals, Organic + grid, River city, Radial, and Blank last.
A city can't be finished until it passes the gate: no fail, score >= 85 (city_gate.PASS_SCORE), on the eight checks.

spec (every field optional but a Blank city needs one district):
    {"name": "Alto Bay", "template": "grid",
     "districts": [{"name", "kind": "grid"|"organic"|"radial", "center": [x, y] m, "size_km": 2.0 | [w, h], "angle": deg,
                    "block": [w, h] m}],
     "streets":   [{"name", "class": "main"|"minor", "from": district | landmark | [x, y], "to": ..., "diagonal": bool}],
     "water":     [{"name", "kind": "river"|"coast"|"lake", "course": [[x, y], ...] | "north"|"south"|"east"|"west",
                    "width": "narrow"|"wide", "at": [x, y], "size_km": lake diameter}],
     "landmarks": [{"name", "at": district | street | [x, y], "kind": "tower"|"civic"|"station"|"park", "floors"}],
     "transit":   [{"name", "colour": "#rrggbb", "kind": "rail"|"subway"|"tram", "stops": [landmark or station names]}]}
Coordinates are metres from the city's north-west corner, x east, y south (the page's own axes).
"""
from __future__ import annotations

import copy
import math
import re

TEMPLATES = ("grid", "grid_diagonals", "organic_grid", "river", "radial", "blank")
TEMPLATE_NAMES = {"grid": "Grid", "grid_diagonals": "Grid + diagonals", "organic_grid": "Organic + grid",
                  "river": "River city", "radial": "Radial", "blank": "Blank"}
DEFAULT_TEMPLATE = "grid"
KINDS = ("grid", "organic", "radial")
BLOCK = (130.0, 110.0)          # m: a block of a grid district (Philadelphia-like)
MARGIN = 160.0                  # m: glass round the outermost street
MIN_KM2, MAX_KM = 0.6, 7.0      # a district covers at least this (rules 14.3 district fit); a side at most this
MAX_DISTRICTS, MAX_LANDMARKS = 6, 24
WIDTH = {"narrow": 70.0, "wide": 170.0}
COLOURS = ("#e5484d", "#3e8ef7", "#2fb36d", "#f5a524", "#8e6cf0", "#14a3b8")
_COLS = ("Street", "Avenue", "Place", "Way", "Court", "Row")
_ROWS = ("Oak", "Elm", "Maple", "Cedar", "Birch", "Walnut", "Chestnut", "Spruce", "Pine", "Locust", "Willow", "Aspen",
         "Hazel", "Laurel", "Juniper", "Magnolia", "Poplar", "Sycamore", "Hawthorn", "Linden", "Alder", "Holly", "Rowan",
         "Cypress", "Larch", "Myrtle", "Olive", "Palm", "Quince", "Sage", "Tamarind", "Yew", "Acacia", "Bay", "Clover",
         "Daisy", "Fern", "Heather", "Iris", "Jasmine", "Lilac", "Marigold", "Orchid", "Peony", "Rose", "Tulip", "Violet")
_LANDMARKS = ("City Hall", "Central Library", "Museum of Art", "Opera House", "Court House", "Observatory", "Clock Tower",
              "Grand Hotel", "Market Hall", "University Hall", "Science Museum", "Concert Hall")
ORD = {1: "st", 2: "nd", 3: "rd"}
# an invented landmark's look: Alto's generic buildings only, never a real one (the page matches art by NAME, so an
# invented "City Hall" or "Museum of Art" would otherwise be drawn as Philadelphia's). look -> art key.
LOOKS = {"dome": "g-dome", "spire": "g-spire", "gable": "g-gable", "pyramid": "g-pyramid", "angled": "g-angled",
         "flat": "g-flat", "classical": "ct-classical-city", "modern": "ct-modern-city", "tall": "ct-tower-city"}
_LOOK_BY = [(r"hall|capitol|parliament|council|senate", ("dome", "classical", "spire", "gable")),
            (r"court|justice", ("classical", "modern", "tall")),
            (r"tower|clock|observatory|lighthouse|spire", ("spire", "pyramid", "tall")),
            (r"museum|gallery|library|archive|university|college|school", ("classical", "dome", "gable", "angled")),
            (r"opera|theat|concert|music|arena", ("angled", "dome", "pyramid")),
            (r"hotel|bank|exchange|trade|office|plaza|centre|center", ("angled", "flat", "tall", "spire")),
            (r"market|station|hall|church|temple|cathedral", ("gable", "pyramid", "spire"))]


class InventError(ValueError):
    """A spec that cannot be built: .problems is the list of plain-words reasons (what the editor shows)."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


def _look(city, name, kind, used=()):
    """A landmark's look when the spec names none: from what its name says it is, varied by the city and the name
    (seeded, so the same city always looks the same), avoiding looks the city has already used where it can."""
    opts = next((o for rx, o in _LOOK_BY if re.search(rx, name, re.I)), None)
    if opts is None:
        opts = ("spire", "tall", "angled") if kind == "tower" else tuple(LOOKS)
    fresh = [o for o in opts if o not in used] or list(opts)
    return fresh[_seed(city + "|" + name) % len(fresh)]


def _ord(i):
    return "%d%s" % (i, "th" if 10 <= i % 100 <= 20 else ORD.get(i % 10, "th"))


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip()).lower()


# ── templates ──────────────────────────────────────────────────────────────
def template(kind=DEFAULT_TEMPLATE, name="") -> dict:
    """The spec a template starts from (the picker's choices, TEMPLATES): every field filled, so the city passes the gate
    as it comes; the user (or Claude) changes what they like. 'blank' is an empty spec the user fills."""
    if kind not in TEMPLATES:
        raise InventError(["there is no template called %r: pick one of %s" % (kind, ", ".join(TEMPLATE_NAMES.values()))])
    nm = name or {"grid": "Gridton", "grid_diagonals": "Diagonal City", "organic_grid": "Oldport", "river": "Rivermouth",
                  "radial": "Ringford", "blank": "New City"}[kind]
    if kind == "blank":
        return {"name": nm, "template": "blank", "districts": [], "streets": [], "water": [], "landmarks": [], "transit": []}
    pool = sorted(_LANDMARKS, key=lambda x: _seed(nm + "|" + x))          # each city its own eight, in its own order
    lm = pool[:8]
    if kind == "grid":
        ds = [{"name": "Downtown", "kind": "grid", "center": [1400, 1200], "size_km": [2.6, 2.2], "angle": 0}]
        streets, water = [], []
    elif kind == "grid_diagonals":
        ds = [{"name": "Downtown", "kind": "grid", "center": [1400, 1200], "size_km": [2.6, 2.2], "angle": 0}]
        streets = [{"name": "Liberty Avenue", "class": "main", "from": [300, 300], "to": [2500, 2100], "diagonal": True},
                   {"name": "Union Avenue", "class": "main", "from": [300, 2100], "to": [2500, 300], "diagonal": True}]
        water = []
    elif kind == "organic_grid":
        ds = [{"name": "Old Town", "kind": "organic", "center": [1200, 1200], "size_km": 2.0},
              {"name": "New Town", "kind": "grid", "center": [3000, 1200], "size_km": [1.4, 2.0], "angle": 0}]
        streets = [{"name": "Harbour Road", "class": "main", "from": "Old Town", "to": "New Town"}]
        water = []
    elif kind == "river":
        ds = [{"name": "North Bank", "kind": "grid", "center": [1400, 850], "size_km": [2.6, 1.3], "angle": 0},
              {"name": "South Bank", "kind": "grid", "center": [1400, 2050], "size_km": [2.6, 0.9], "angle": 0}]
        streets = [{"name": "King Street Bridge", "class": "main", "from": [700, 1450], "to": [700, 1700]},
                   {"name": "Queen Street Bridge", "class": "main", "from": [2100, 1450], "to": [2100, 1700]}]
        water = [{"name": "Silver River", "kind": "river", "course": [[0, 1560], [2900, 1560]], "width": "wide"}]
    else:                                                   # radial
        ds = [{"name": "Centre", "kind": "radial", "center": [1200, 1200], "size_km": 2.0},
              {"name": "Newtown", "kind": "grid", "center": [3000, 1200], "size_km": [1.4, 2.0], "angle": 0}]
        streets = [{"name": "Crown Road", "class": "main", "from": "Centre", "to": "Newtown"}]
        water = []
    spots = [d["name"] for d in ds]
    lms = [{"name": n, "at": spots[i % len(spots)], "kind": "tower" if re.search(r"tower|observatory|hotel", n, re.I) else "civic"}
           for i, n in enumerate(lm)]
    lms += [{"name": "Central Park" if kind != "radial" else "Ring Gardens", "at": spots[0], "kind": "park"},
            {"name": "Central Station", "at": spots[0], "kind": "station"},
            {"name": "Market Station", "at": spots[0], "kind": "station"},
            {"name": "East Station", "at": spots[-1] if kind != "river" else spots[0], "kind": "station"}]
    tr = [{"name": "Red Line", "colour": COLOURS[0], "kind": "rail",
           "stops": ["Central Station", "Market Station", "East Station"]}]
    return {"name": nm, "template": kind, "districts": ds, "streets": streets, "water": water, "landmarks": lms,
            "transit": tr}


def picker() -> list:
    """The template picker's rows in Luke's order: Grid (default) first, Blank last."""
    return [{"id": k, "name": TEMPLATE_NAMES[k], "default": k == DEFAULT_TEMPLATE} for k in TEMPLATES]


# ── validation (like check_transit: every name resolves) ───────────────────
def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _pt(v):
    return isinstance(v, (list, tuple)) and len(v) == 2 and all(_num(c) for c in v)


def _size(d):
    s = d.get("size_km", 2.0)
    if _num(s):
        return float(s), float(s)
    if isinstance(s, (list, tuple)) and len(s) == 2 and all(_num(c) for c in s):
        return float(s[0]), float(s[1])
    return None


def validate(spec) -> list:
    """Every problem with the spec, in plain words ([] = buildable)."""
    P = []
    if not isinstance(spec, dict):
        return ["the city description must be a set of fields (districts, streets, water, landmarks, transit)"]
    for k in ("districts", "streets", "water", "landmarks", "transit"):
        if spec.get(k) is not None and not isinstance(spec.get(k), list):
            P.append("%s must be a list" % k)
    if P:
        return P
    ds = spec.get("districts") or []
    if not ds:
        P.append("a city needs at least one district: add one (a grid district is the usual start)")
    if ds and all(isinstance(d, dict) and (d.get("kind") or "grid") != "grid" for d in ds):
        P.append("a city needs at least one grid district: an organic or radial district sits beside a grid one")
    if len(ds) > MAX_DISTRICTS:
        P.append("%d districts is too many: at most %d" % (len(ds), MAX_DISTRICTS))
    seen = {}
    boxes = []
    for i, d in enumerate(ds):
        if not isinstance(d, dict):
            P.append("district %d is not a set of fields" % (i + 1))
            continue
        n = str(d.get("name") or "").strip()
        if not n:
            P.append("district %d has no name" % (i + 1))
        elif _norm(n) in seen:
            P.append("two districts are called %r: give each its own name" % n)
        seen[_norm(n)] = "district"
        if (d.get("kind") or "grid") not in KINDS:
            P.append("district %r is a %r: a district is a grid, organic or radial" % (n, d.get("kind")))
        sz = _size(d)
        if not sz:
            P.append("district %r needs a size in km (one number, or width and height)" % n)
            continue
        if sz[0] * sz[1] < MIN_KM2 or min(sz) < 0.5:
            P.append("district %r is too small (%.1f km²): make it at least %.1f km² so it holds whole blocks" % (n, sz[0] * sz[1], MIN_KM2))
        if max(sz) > MAX_KM:
            P.append("district %r is too big (%.1f km a side): at most %d km" % (n, max(sz), MAX_KM))
        c = d.get("center")
        if c is not None and not _pt(c):
            P.append("district %r: its centre is two numbers, metres east and south" % n)
        if d.get("angle") is not None and not _num(d.get("angle")):
            P.append("district %r: its angle is a number of degrees" % n)
        blk = d.get("block")
        if blk is not None and not (isinstance(blk, (list, tuple)) and len(blk) == 2 and all(_num(v) and 60 <= v <= 300 for v in blk)):
            P.append("district %r: a block is two lengths between 60 and 300 m" % n)
        if _pt(c or [0, 0]):
            cx, cy = (c or [0, 0])
            boxes.append((n, cx - sz[0] * 500, cy - sz[1] * 500, cx + sz[0] * 500, cy + sz[1] * 500))
    if len(boxes) > 1 and all(_pt(d.get("center")) for d in ds if isinstance(d, dict)):
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                ox, oy = min(a[3], b[3]) - max(a[1], b[1]), min(a[4], b[4]) - max(a[2], b[2])
                if ox > BLOCK[0] and oy > BLOCK[1]:
                    P.append("districts %r and %r overlap by more than a block: move one or make it smaller" % (a[0], b[0]))
    for i, lm in enumerate(spec.get("landmarks") or []):
        if not isinstance(lm, dict) or not str(lm.get("name") or "").strip():
            P.append("landmark %d has no name" % (i + 1))
            continue
        n = lm["name"].strip()
        if _norm(n) in seen:
            P.append("the name %r is used twice: every district, landmark and station needs its own name" % n)
        seen[_norm(n)] = lm.get("kind") or "civic"
        if (lm.get("kind") or "civic") not in ("tower", "civic", "station", "park"):
            P.append("landmark %r is a %r: a landmark is a tower, civic building, station or park" % (n, lm.get("kind")))
        if lm.get("look") is not None and lm["look"] not in LOOKS:
            P.append("landmark %r: a look is one of %s" % (n, ", ".join(LOOKS)))
        if lm.get("floors") is not None and not (_num(lm["floors"]) and 1 <= lm["floors"] <= 160):
            P.append("landmark %r: floors is a number from 1 to 160" % n)
    n_lm = sum(1 for lm in spec.get("landmarks") or [] if isinstance(lm, dict) and lm.get("kind") not in ("park", "station"))
    if n_lm > MAX_LANDMARKS:
        P.append("%d landmarks is too many for one city: at most %d" % (n_lm, MAX_LANDMARKS))
    streets = {}
    for i, s in enumerate(spec.get("streets") or []):
        if not isinstance(s, dict) or not str(s.get("name") or "").strip():
            P.append("street %d has no name" % (i + 1))
            continue
        streets[_norm(s["name"])] = s
        if (s.get("class") or "main") not in ("main", "minor"):
            P.append("street %r: its class is main or minor" % s["name"])
    names = {**seen, **{k: "street" for k in streets}}
    for s in spec.get("streets") or []:
        if not isinstance(s, dict) or not s.get("name"):
            continue
        for end in ("from", "to"):
            v = s.get(end)
            if v is None:
                P.append("street %r needs a %s: a district, a landmark or a point" % (s["name"], end))
            elif not _pt(v) and _norm(v) not in seen:
                P.append("street %r goes %s %r, which is not a district or landmark of this city" % (s["name"], end, v))
    for lm in spec.get("landmarks") or []:
        if not isinstance(lm, dict) or not lm.get("name"):
            continue
        at = lm.get("at")
        if at is not None and not _pt(at) and _norm(at) not in names:
            P.append("landmark %r stands at %r, which is not a district or street of this city" % (lm["name"], at))
    for i, w in enumerate(spec.get("water") or []):
        if not isinstance(w, dict):
            P.append("water %d is not a set of fields" % (i + 1))
            continue
        n = w.get("name") or "water %d" % (i + 1)
        k = w.get("kind") or "river"
        if k not in ("river", "coast", "lake"):
            P.append("%s is a %r: water is a river, coast or lake" % (n, k))
        if (w.get("width") or "narrow") not in WIDTH:
            P.append("%s: a width is narrow or wide" % n)
        co = w.get("course")
        if k == "river" and co is not None and not (isinstance(co, list) and len(co) >= 2 and all(_pt(p) for p in co)):
            P.append("river %s: its course is two or more points" % n)
        if k == "coast" and (co or "east") not in ("north", "south", "east", "west"):
            P.append("coast %s: say which side of the city the sea is on (north, south, east or west)" % n)
        if k == "lake" and not _pt(w.get("at")):
            P.append("lake %s: give its middle as a point" % n)
    stops_ok = {k for k, v in seen.items() if v == "station"}
    others = {k for k, v in seen.items() if v not in ("station", "district")}
    for i, ln in enumerate(spec.get("transit") or []):
        if not isinstance(ln, dict):
            P.append("transit line %d is not a set of fields" % (i + 1))
            continue
        n = ln.get("name") or "line %d" % (i + 1)
        st = ln.get("stops") or []
        if len(st) < 2:
            P.append("%s needs at least two stops" % n)
        for s in st:
            if _norm(s) in others:
                P.append("%s stops at %r, which is a landmark: a line stops at stations, so add a station beside it" % (n, s))
            elif _norm(s) not in stops_ok:
                P.append("%s stops at %r, which is not a station or landmark of this city: add it, or take it off the line" % (n, s))
        if len({_norm(s) for s in st}) < len(st):
            P.append("%s stops at the same place twice" % n)
    return P


# ── geometry helpers ───────────────────────────────────────────────────────
def _rot(x, y, cx, cy, a):
    c, s = math.cos(a), math.sin(a)
    return cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c


def _flat(pts):
    return [round(v, 1) for q in pts for v in q]


def _poly_dist(pts, x, y):
    best = 1e18
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        dx, dy = x1 - x0, y1 - y0
        L = dx * dx + dy * dy
        t = 0 if L == 0 else max(0, min(1, ((x - x0) * dx + (y - y0) * dy) / L))
        best = min(best, math.hypot(x - x0 - t * dx, y - y0 - t * dy))
    return best


class _Rng:
    def __init__(self, seed):
        self.s = seed & 0x7fffffff or 1

    def __call__(self):
        self.s = (self.s * 1103515245 + 12345) % (1 << 31)
        return self.s / float(1 << 31)


def _seed(text):
    h = 2166136261
    for ch in str(text).encode():
        h = ((h ^ ch) * 16777619) & 0xffffffff
    return h


# ── the districts ──────────────────────────────────────────────────────────
class _D:
    """A district's streets and its blocks (cell centres, for landmarks and parks)."""

    def __init__(self, d, idx, row_pool):
        self.name = d["name"].strip()
        self.kind = d.get("kind") or "grid"
        self.cx, self.cy = (float(v) for v in d.get("center") or (0, 0))
        self.w, self.h = (v * 1000 for v in _size(d))
        self.a = math.radians(float(d.get("angle") or 0))
        self.bw, self.bh = (float(v) for v in d.get("block") or BLOCK)
        self.idx = idx
        self.streets, self.cells, self.nodes = [], [], []
        getattr(self, "_" + self.kind)(row_pool)

    def _grid(self, pool):
        nc = max(2, int(round(self.w / self.bw)) + 1)
        nr = max(2, int(round(self.h / self.bh)) + 1)
        x0, y0 = self.cx - (nc - 1) * self.bw / 2, self.cy - (nr - 1) * self.bh / 2
        x1, y1 = x0 + (nc - 1) * self.bw, y0 + (nr - 1) * self.bh
        R = lambda x, y: _rot(x, y, self.cx, self.cy, self.a)  # noqa: E731
        suf = _COLS[self.idx % len(_COLS)]
        for i in range(nc):
            x = x0 + i * self.bw
            self.streets.append({"n": "%s %s" % (_ord(i + 1), suf), "k": 2 if i % 4 == 0 else 3,
                                 "p": _flat([R(x, y0), R(x, y1)])})
        for j in range(nr):
            y = y0 + j * self.bh
            self.streets.append({"n": "%s Street" % pool.pop(0) if pool else "Row %d Street" % j,
                                 "k": 2 if j % 4 == 0 else 3, "p": _flat([R(x0, y), R(x1, y)])})
        for i in range(nc - 1):
            for j in range(nr - 1):
                self.cells.append((R(x0 + (i + .5) * self.bw, y0 + (j + .5) * self.bh), (i, j)))
        self.nodes = [R(x0 + i * self.bw, y0 + j * self.bh) for i in range(nc) for j in range(nr)]
        self.lat = (x0, y0, nc, nr)
        self.ring = [R(x0, y0), R(x1, y0), R(x1, y1), R(x0, y1)]

    def _organic(self, pool):
        """An old town: a crooked ring-and-lane web (the radial district's bones, every ring and lane bent, uneven and seeded
        by the district's name), so each lane ends on a ring; the engine reads it as a free domain beside the grid and
        draws it as smoothed geometry, not graph paper."""
        self._radial(pool, crooked=_Rng(_seed(self.name)))

    def _radial(self, pool, crooked=None):
        """Three rings and ten straight spokes from the inner ring to the outer one (every spoke ends on a ring). crooked
        (an organic old town): the rings wobble. (The spokes stay straight, evenly turned, inner ring to outer, with 4
        points: bent, uneven or shorter ones are no longer read as a free domain by the engine, which keeps a free street's
        points inside its domain.)"""
        R = min(self.w, self.h) / 2
        rings = [R * f for f in (.3, .62, .95)]
        wob = [(crooked() * 2 * math.pi, .06 + .06 * crooked()) for _ in rings] if crooked else [(0, 0)] * len(rings)
        rad = lambda j, a: rings[j] * (1 + wob[j][1] * math.sin(3 * a + wob[j][0]))  # noqa: E731 — a: the absolute angle
        at = lambda j, a: (self.cx + rad(j, a) * math.cos(a), self.cy + rad(j, a) * math.sin(a))  # noqa: E731
        kind = ("Lane", "Ring") if crooked else ("Road", "Circle")
        for j in range(len(rings)):
            self.streets.append({"n": "%s %s" % (pool.pop(0) if pool else "Ring %d" % j, kind[1]), "k": 2 if j == 1 else 3,
                                 "p": _flat([at(j, 2 * math.pi * t / 64) for t in range(65)])})
        n = 10
        for i in range(n):
            a = 2 * math.pi * i / n + self.a
            p0, p1 = at(0, a), at(len(rings) - 1, a)
            self.streets.append({"n": "%s %s" % (pool.pop(0) if pool else "Spoke %d" % i, kind[0]), "k": 2 if i % 5 == 0 else 3,
                                 "p": _flat([(p0[0] + (p1[0] - p0[0]) * t / 3, p0[1] + (p1[1] - p0[1]) * t / 3) for t in range(4)])})
        for j in range(len(rings) - 1):
            for i in range(n):
                a = 2 * math.pi * (i + .5) / n + self.a
                (xa, ya), (xb, yb) = at(j, a), at(j + 1, a)
                self.cells.append((((xa + xb) / 2, (ya + yb) / 2), (i, j)))
        self.nodes = [at(j, 2 * math.pi * i / n + self.a) for j in range(len(rings)) for i in range(n)]
        self.ring = [at(len(rings) - 1, 2 * math.pi * t / 32) for t in range(32)]

    def diagonal(self, A, B):
        """A diagonal avenue of a grid district from the node nearest A toward B, one block across for every block down
        (the engine draws it octilinear, so it crosses its streets in the same order as planned)."""
        x0, y0, nc, nr = self.lat
        loc = lambda p: _rot(p[0], p[1], self.cx, self.cy, -self.a)  # noqa: E731
        ax, ay = loc(A)
        bx, by = loc(B)
        i0, j0 = (min(nc - 1, max(0, round((ax - x0) / self.bw))), min(nr - 1, max(0, round((ay - y0) / self.bh))))
        si, sj = (1 if bx >= ax else -1), (1 if by >= ay else -1)
        k = min((nc - 1 - i0) if si > 0 else i0, (nr - 1 - j0) if sj > 0 else j0,
                max(abs(round((bx - ax) / self.bw)), abs(round((by - ay) / self.bh))))
        # the page draws every block CW x CH and a diagonal at 45 degrees there, so the planned one runs CW/CH blocks down
        # for every block across: the drawing is then the plan's exact image and crosses its streets in the same order.
        # It starts half a block off a crossing and ends on a row street (no end lands on nothing).
        from .palace_grid import CW, CH
        r = CW / CH
        i0 = min(i0, nc - 2) if si > 0 else max(i0, 1)
        room_i = ((nc - 1.5 - i0) if si > 0 else i0 - .5)
        room_j = (nr - 1 - j0) if sj > 0 else j0
        n = int(min(room_j, room_i * r, max(1, k * r)))
        if n < 2:
            return A, A
        R = lambda i, j: _rot(x0 + i * self.bw, y0 + j * self.bh, self.cx, self.cy, self.a)  # noqa: E731
        return R(i0 + .5 * si, j0), R(i0 + .5 * si + si * n / r, j0 + sj * n)

    def nearest_node(self, x, y):
        return min(self.nodes, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)


def _block_ring(cx, cy, w, h, pad=10.0):
    return [cx - w / 2 + pad, cy - h / 2 + pad, cx + w / 2 - pad, cy - h / 2 + pad,
            cx + w / 2 - pad, cy + h / 2 - pad, cx - w / 2 + pad, cy + h / 2 - pad]


# ── the map ────────────────────────────────────────────────────────────────
def invent_city(spec) -> dict:
    """The map dict m of an invented city (rules doc 14.1), in the same px space build_map uses. m["plan"] carries what
    palace_grid.grid takes besides m (majors, diagonals, landmarks, parks, lines). Raises InventError on a bad spec."""
    probs = validate(spec)
    if probs:
        raise InventError(probs)
    spec = copy.deepcopy(spec)
    # districts without a centre are laid out west to east
    x = MARGIN
    for d in spec["districts"]:
        w, h = _size(d)
        if d.get("center") is None:
            d["center"] = [x + w * 500, MARGIN + h * 500]
            x += w * 1000 + 2 * BLOCK[0]
    pool = list(_ROWS)
    D = [_D(d, i, pool) for i, d in enumerate(spec["districts"])]
    streets = [s for d in D for s in d.streets]
    byname = {_norm(d.name): d for d in D}
    used, taken = set(), set()
    landmarks, stations, parks, lm_specs, park_names = [], [], [], [], []

    def free_cell(d, near=None, gap=2):
        """A block of district d no landmark holds, at least `gap` blocks from every taken one (fewer when it is full)."""
        cand = [c for c in d.cells if (d.name, c[1]) not in taken and
                not (abs(c[0][0] - d.cx) < 1.6 * d.bw and abs(c[0][1] - d.cy) < 1.2 * d.bh) and   # its name stands there
                not any(_poly_dist(dl, *c[0]) < .8 * max(d.bw, d.bh) for dl in diag_lines) and   # no avenue runs through it
                not any(-1.6 * d.bh < c[0][1] - y < 1.6 * d.bh and x0 - d.bw < c[0][0] < x1 + d.bw   # nor a line (nor the row
                        for y, x0, x1 in rail_rows)]          # below, whose art rises; nor above, whose name meets the stations')
        if near is not None:
            cand.sort(key=lambda c: (c[0][0] - near[0]) ** 2 + (c[0][1] - near[1]) ** 2)
        else:                                           # spread: the middle first, then outwards in a fixed order
            cand.sort(key=lambda c: ((c[0][0] - d.cx) ** 2 + (c[0][1] - d.cy) ** 2) * (1 + .3 * ((c[1][0] * 7 + c[1][1] * 3) % 5)))
        for g in range(gap, -1, -1):
            for c in cand:
                if all(max(abs(c[1][0] - t[1][0]), abs(c[1][1] - t[1][1])) > g for t in taken if t[0] == d.name):
                    return c
        return None

    # the spine: main streets between districts / points (they end on a district's street, so nothing starts from nowhere)
    lm_pos, notes, used_looks = {}, [], []
    pend = []
    for s in spec.get("streets") or []:
        pend.append(s)
    majors, diagonals = [], []
    land_ends = {}

    def place(v):
        if _pt(v):
            p = (float(v[0]), float(v[1]))
            d = min(D, key=lambda d_: (d_.cx - p[0]) ** 2 + (d_.cy - p[1]) ** 2)
            return d.nearest_node(*p)
        d = byname.get(_norm(v))
        if d:
            return d.nearest_node(d.cx, d.cy) if d.kind == "grid" else d.nodes[len(d.nodes) // 2]   # (a ring-and-lane district: from its middle ring)
        return None
    # the diagonals that do not run to a landmark are planned first, so no landmark or park block lies under one
    diag_lines, rail_rows = [], []
    lmn = {_norm(l.get("name")) for l in spec.get("landmarks") or []}
    for s in spec.get("streets") or []:
        if s.get("diagonal") and not ({_norm(s["from"]) if not _pt(s["from"]) else "", _norm(s["to"]) if not _pt(s["to"]) else ""} & lmn):
            A, B = place(s["from"]), place(s["to"])
            dd = min(D, key=lambda d_: (d_.cx - A[0]) ** 2 + (d_.cy - A[1]) ** 2) if A else None
            if A and B and dd.kind == "grid":
                diag_lines.append(list(dd.diagonal(A, B)))
    # landmarks first (a street may go to one)
    for lm in spec.get("landmarks") or []:
        at = lm.get("at")
        kind = lm.get("kind") or "civic"
        if _pt(at):
            d = min(D, key=lambda d_: (d_.cx - at[0]) ** 2 + (d_.cy - at[1]) ** 2)
            near = (float(at[0]), float(at[1]))
        elif at is not None and _norm(at) in byname:
            d, near = byname[_norm(at)], None
        elif at is not None:                            # a street: the free block nearest its middle
            ss = [s for s in streets if _norm(s["n"]) == _norm(at)]
            sp = next((s for s in spec.get("streets") or [] if _norm(s.get("name")) == _norm(at)), None)
            if ss:
                p = ss[0]["p"]
                near = (p[len(p) // 2 // 2 * 2], p[len(p) // 2 // 2 * 2 + 1])
            elif sp:
                a, b = place(sp["from"]), place(sp["to"])
                near = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) if a and b else (D[0].cx, D[0].cy)
            else:
                near = (D[0].cx, D[0].cy)
            d = min(D, key=lambda d_: (d_.cx - near[0]) ** 2 + (d_.cy - near[1]) ** 2)
        else:
            d, near = D[len(landmarks) % len(D)], None
        if d.kind != "grid":                            # the engine stands every landmark on a lattice block: the grid
            gd = [d_ for d_ in D if d_.kind == "grid"]  # block nearest the organic / radial district it names
            near = near or (d.cx, d.cy)
            d = min(gd, key=lambda d_: min((c[0][0] - near[0]) ** 2 + (c[0][1] - near[1]) ** 2 for c in d_.cells))
            notes.append("%s stands on the grid block nearest %s (landmarks stand on grid blocks)" % (lm["name"].strip(), at))
        c = free_cell(d, near, gap=1 if kind == "park" else 2)
        if c is None:
            continue
        taken.add((d.name, c[1]))
        (cx, cy), _ij = c
        nm = lm["name"].strip()
        bw, bh = (d.bw, d.bh) if d.kind == "grid" else (100.0, 90.0)
        if kind == "park":
            parks.append({"n": nm, "r": [_block_ring(cx, cy, bw, bh, 4.0)]})
            park_names.append(nm)
        elif kind == "station":
            stations.append({"n": nm, "x": round(cx, 1), "y": round(cy, 1), "k": "rail", "l": []})   # (the line draws it)
        else:
            landmarks.append({"n": nm, "x": round(cx, 1), "y": round(cy, 1), "r": [_block_ring(cx, cy, bw, bh, 14.0)]})
            look = lm.get("look") or _look(spec.get("name") or "", nm, kind, used_looks)
            used_looks.append(look)
            hs = _seed((spec.get("name") or "") + "|h|" + nm)
            hm = float(lm["floors"]) * 4.0 if lm.get("floors") else (90 + hs % 120 if kind == "tower" else 28 + hs % 35)
            fw = (40 + (hs >> 8) % 25) if kind == "tower" else (70 + (hs >> 8) % 35)     # m: a hall fills its block's front
            lm_specs.append({"name": nm, "art": LOOKS[look], "height_m": round(hm, 1), "width_m": fw,
                             **({"floors": int(lm["floors"])} if lm.get("floors") else {})})
        lm_pos[_norm(nm)] = (cx, cy)
    cells_of = {}
    for d in D:
        if d.kind == "grid":
            for c in d.cells:
                cells_of[(d.name, c[1])] = (d, c)
    where = {}
    for (dn, ij) in taken:
        d, c = cells_of.get((dn, ij), (None, None))
        if c:
            where[(round(c[0][0], 1), round(c[0][1], 1))] = (dn, ij)
    for ln in spec.get("transit") or []:
        st = [_norm(n) for n in ln.get("stops") or []]
        if not st or st[0] not in lm_pos:
            continue
        y0 = lm_pos[st[0]][1]
        prev, sign = lm_pos[st[0]][0], 0
        for n in st[1:]:
            if n not in lm_pos:
                continue
            x0 = lm_pos[n][0]
            sign = sign or (1 if x0 >= prev else -1)    # the line keeps one direction: each stop beyond the last
            if abs(lm_pos[n][1] - y0) < 1 and (x0 - prev) * sign > 2.5 * BLOCK[0]:
                prev = x0
                continue
            free = [(d, c) for (dn, ij), (d, c) in cells_of.items() if (dn, ij) not in taken and (c[0][0] - prev) * sign > 2.5 * d.bw]
            if not free:
                continue
            d, c = min(free, key=lambda dc: (round(abs(dc[1][0][1] - y0)), abs(dc[1][0][0] - x0)))
            if abs(c[0][1] - y0) > BLOCK[1]:
                notes.append("%s could not join its line's row" % n)
                continue
            old = (round(lm_pos[n][0], 1), round(lm_pos[n][1], 1))
            taken.discard(where.pop(old, (None, None)))
            taken.add((d.name, c[1]))
            (cx, cy) = c[0]
            for coll in (stations, landmarks):
                for l_ in coll:
                    if _norm(l_["n"]) == n:
                        l_["x"], l_["y"] = round(cx, 1), round(cy, 1)
                        if "r" in l_:
                            l_["r"] = [_block_ring(cx, cy, d.bw, d.bh, 18.0)]
            lm_pos[n] = (cx, cy)
            prev = cx
        xs_ = [lm_pos[n][0] for n in st if n in lm_pos and abs(lm_pos[n][1] - y0) < 1]
        if len(xs_) >= 2:
            rail_rows.append((y0, min(xs_), max(xs_)))
    # the line runs straight along its row: a landmark or park standing on it between its ends moves off it
    stn = {_norm(s_["n"]) for s_ in stations}
    for coll in (landmarks, parks):
        for l_ in coll:
            if _norm(l_["n"]) in stn:
                continue
            x_, y_ = lm_pos.get(_norm(l_["n"]), (None, None))
            if x_ is None or not any(-1.6 * BLOCK[1] < y_ - y < 1.6 * BLOCK[1] and x0 - BLOCK[0] < x_ < x1 + BLOCK[0]
                                     for y, x0, x1 in rail_rows):
                continue
            d = min((d_ for d_ in D if d_.kind == "grid"), key=lambda d_: (d_.cx - x_) ** 2 + (d_.cy - y_) ** 2)
            c = free_cell(d, (x_, y_), gap=1)
            if c is None:
                continue
            taken.discard(where.pop((round(x_, 1), round(y_, 1)), (None, None)))
            taken.add((d.name, c[1]))
            (cx, cy) = c[0]
            pad = 4.0 if coll is parks else 14.0
            if coll is landmarks:
                l_["x"], l_["y"] = round(cx, 1), round(cy, 1)
            l_["r"] = [_block_ring(cx, cy, d.bw, d.bh, pad)]
            lm_pos[_norm(l_["n"])] = (cx, cy)
    for s in pend:
        a, b = s["from"], s["to"]
        pa = lm_pos.get(_norm(a)) if not _pt(a) else None
        pb = lm_pos.get(_norm(b)) if not _pt(b) else None
        A = place(a) if pa is None else min(D, key=lambda d_: (d_.cx - pa[0]) ** 2 + (d_.cy - pa[1]) ** 2).nearest_node(*pa)
        B = place(b) if pb is None else min(D, key=lambda d_: (d_.cx - pb[0]) ** 2 + (d_.cy - pb[1]) ** 2).nearest_node(*pb)
        if not A or not B or A == B:
            continue
        nm = s["name"].strip()
        k = 1 if (s.get("class") or "main") == "main" else 3
        if s.get("diagonal"):
            dd = min(D, key=lambda d_: (d_.cx - A[0]) ** 2 + (d_.cy - A[1]) ** 2)
            if dd.kind == "grid":
                A, B = dd.diagonal(A, B)
                if A == B:
                    continue
            diagonals.append(nm)
        if k == 1:
            majors.append(nm)
        streets.append({"n": nm, "k": k, "p": _flat([A, B])})
        land_ends[nm] = (A, B)
    # extents
    xs = [v for s in streets for v in s["p"][0::2]] + [l["x"] for l in landmarks]
    ys = [v for s in streets for v in s["p"][1::2]] + [l["y"] for l in landmarks]
    ox, oy = min(xs) - MARGIN, min(ys) - MARGIN
    W, H = max(xs) - ox + MARGIN, max(ys) - oy + MARGIN
    water, rivers = [], []
    for i, w in enumerate(spec.get("water") or []):
        kind = w.get("kind") or "river"
        wid = WIDTH[w.get("width") or "narrow"]
        nm = w.get("name") or ("River" if kind == "river" else "Sea")
        if kind == "river":
            co = [(float(p[0]), float(p[1])) for p in (w.get("course") or [[ox, oy + H / 2], [ox + W, oy + H / 2]])]
            rivers.append({"n": nm, "p": _flat(co)})
            # the band: the course offset half a width each way (a straight course: an exact strip)
            L, R_ = [], []
            for k_, (px, py) in enumerate(co):
                qx, qy = co[min(k_ + 1, len(co) - 1)] if k_ < len(co) - 1 else co[k_]
                rx_, ry_ = co[max(k_ - 1, 0)] if k_ else co[0]
                dx, dy = (qx - rx_), (qy - ry_)
                if k_ == 0:
                    dx, dy = co[1][0] - px, co[1][1] - py
                if k_ == len(co) - 1:
                    dx, dy = px - co[-2][0], py - co[-2][1]
                n_ = math.hypot(dx, dy) or 1
                nx, ny = -dy / n_ * wid / 2, dx / n_ * wid / 2
                L.append((px + nx, py + ny))
                R_.append((px - nx, py - ny))
            water.append(_flat(L + R_[::-1]))
            # a street the band cuts stays two streets; every third one (a main street first) is a bridge
            out = []
            for s in streets:
                pts = list(zip(s["p"][0::2], s["p"][1::2]))
                if len(pts) != 2:
                    out.append(s)
                    continue
                (x0, y0), (x1, y1) = pts
                hit = [t / 40 for t in range(41) if _poly_dist(co, x0 + (x1 - x0) * t / 40, y0 + (y1 - y0) * t / 40) < wid / 2]
                if not hit:
                    out.append(s)
                    continue
                out.append(s)
                s["_x"] = (min(hit), max(hit))
            cross = [s for s in out if s.get("_x")]
            cross.sort(key=lambda s: (s["k"], s["p"][0]))
            for k_, s in enumerate(cross):
                t0, t1 = s.pop("_x")
                if s["k"] <= 2 or k_ % 3 == 0:
                    s["b"] = 1                                  # a bridge
                    continue
                (x0, y0), (x1, y1) = list(zip(s["p"][0::2], s["p"][1::2]))
                a_ = (x0 + (x1 - x0) * max(0, t0 - .03), y0 + (y1 - y0) * max(0, t0 - .03))
                b_ = (x0 + (x1 - x0) * min(1, t1 + .03), y0 + (y1 - y0) * min(1, t1 + .03))
                s["p"] = _flat([(x0, y0), a_])
                out.append({"n": s["n"], "k": s["k"], "p": _flat([b_, (x1, y1)])})
            streets = [s for s in out if math.hypot(s["p"][-2] - s["p"][0], s["p"][-1] - s["p"][1]) > 30]
        elif kind == "coast":
            side = w.get("course") or "east"
            band = wid * 3
            if side == "east":
                water.append(_flat([(ox + W, oy), (ox + W + band, oy), (ox + W + band, oy + H), (ox + W, oy + H)]))
                W += band
            elif side == "west":
                water.append(_flat([(ox - band, oy), (ox, oy), (ox, oy + H), (ox - band, oy + H)]))
                ox -= band
                W += band
            elif side == "north":
                water.append(_flat([(ox, oy - band), (ox + W, oy - band), (ox + W, oy), (ox, oy)]))
                oy -= band
                H += band
            else:
                water.append(_flat([(ox, oy + H), (ox + W, oy + H), (ox + W, oy + H + band), (ox, oy + H + band)]))
                H += band
        else:                                                   # a lake: a ring of water, streets stop at a shore road
            cx, cy = (float(v) for v in w["at"])
            r = float(w.get("size_km") or .5) * 500
            water.append(_flat([(cx + r * math.cos(2 * math.pi * t / 32), cy + r * math.sin(2 * math.pi * t / 32)) for t in range(32)]))
            out = []
            for s in streets:
                pts = list(zip(s["p"][0::2], s["p"][1::2]))
                keep, cur = [], []
                for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                    for t in range(0, 21):
                        px, py = x0 + (x1 - x0) * t / 20, y0 + (y1 - y0) * t / 20
                        if math.hypot(px - cx, py - cy) < r + 25:
                            if len(cur) >= 2:
                                keep.append(cur)
                            cur = []
                        else:
                            cur.append((px, py))
                if len(cur) >= 2:
                    keep.append(cur)
                for c in keep:
                    if math.dist(c[0], c[-1]) > 30:
                        out.append({**s, "p": _flat([c[0], c[-1]] if len(pts) == 2 else c)})
            ring = [(cx + (r + 30) * math.cos(2 * math.pi * t / 40), cy + (r + 30) * math.sin(2 * math.pi * t / 40)) for t in range(41)]
            out.append({"n": "%s Shore Drive" % nm, "k": 2, "p": _flat(ring)})
            streets = out
    shift = lambda p: [round(v - (ox if i % 2 == 0 else oy), 1) for i, v in enumerate(p)]  # noqa: E731
    for s in streets:
        s["p"] = shift(s["p"])
    for coll in (landmarks, stations):
        for l_ in coll:
            l_["x"], l_["y"] = round(l_["x"] - ox, 1), round(l_["y"] - oy, 1)
            l_["r"] = [shift(r) for r in l_.get("r") or []] if "r" in l_ else l_.get("r")
    for p_ in parks:
        p_["r"] = [shift(r) for r in p_["r"]]
    water = [shift(r) for r in water]
    for r in rivers:
        r["p"] = shift(r["p"])
    W, H = int(math.ceil(W)), int(math.ceil(H))
    lines = []
    for i, ln in enumerate(spec.get("transit") or []):
        lines.append({"name": ln.get("name") or "Line %d" % (i + 1), "color": ln.get("colour") or COLOURS[i % len(COLOURS)],
                      "stops": list(ln.get("stops") or [])})
    for st in stations:
        st["l"] = [ln["name"] for ln in lines if any(_norm(s) == _norm(st["n"]) for s in ln["stops"])]
    # the box in degrees, on the equator (no real place: an invented city never ships under a real place's name)
    bbox = [0.0, 0.0, round(H / 110574.0, 6), round(W / 111320.0, 6)]
    majors += sorted({s["n"] for s in streets if s["k"] <= 2})
    areas = [{"name": d.name, "lat": round(bbox[2] * (1 - (d.cy - oy) / H), 6), "lon": round(bbox[3] * (d.cx - ox) / W, 6),
              "rank": 1} for d in D]
    if spec.get("quiet_names") and areas:                   # the one-tap fix for crowded names: the biggest district's
        big = max(D, key=lambda d: d.w * d.h).name          # name at the whole-city zoom, the others up close
        for a in areas:
            a["rank"] = 1 if a["name"] == big else 3
    return {"v": 1, "place": spec.get("name") or "New City", "preset": "invented", "bbox": bbox, "scale": 1.0, "W": W, "H": H,
            "streets": streets, "trails": [], "rails": [], "parks": parks, "water": water, "rivers": rivers,
            "majors": list(dict.fromkeys(majors)), "stations": stations, "landmarks": landmarks,
            "plan": {"majors": list(dict.fromkeys(majors)), "diagonals": diagonals, "landmarks": lm_specs,
                     "parks": park_names, "lines": lines, "areas": areas, "notes": notes,
                     "districts": [{"name": d.name, "kind": d.kind, "x": round(d.cx - ox, 1), "y": round(d.cy - oy, 1),
                                    "w": round(d.w), "h": round(d.h), "ring": shift(_flat(d.ring))} for d in D]}}


def build(spec):
    """invent_city then palace_grid.grid, the way palace.set_up draws a real map: (m, g)."""
    from .palace_grid import grid
    m = invent_city(spec)
    pl = m["plan"]
    g = grid(copy.deepcopy({k: v for k, v in m.items() if k != "plan"}), majors=pl["majors"], diagonals=pl["diagonals"],
             lines=pl["lines"], landmarks=pl["landmarks"], parks=pl["parks"])
    return m, g


# ── the gate for a city with no real map (rules doc 14.3) ──────────────────
# The plan (m) is the reference, so city_gate's rows read plan-vs-drawn; the rows that need a real map or a fetch drop out
# (their weight goes to the rows that ran). The new invented-city rows are I1-I6. The user sees EIGHT checks in plain
# words, each with a one-tap fix (apply_fix); no raw check codes.
DROP = ("G10", "G21")
IROWS = [("I1", "lattice regularity", 3), ("I2", "street closure", 4), ("I3", "landmark spacing", 3),
         ("I4", "district fit", 4), ("I5", "name uniqueness", 2), ("I6", "transit stops in order", 3),
         ("I7", "districts drawn as planned", 2)]
CHECKS = [   # (id, what the user reads, rows)
    ("streets", "Streets join up", ("G7", "I2", "I4")),
    ("blocks", "Blocks are even and whole", ("G1", "G2", "G11", "G12", "G13", "I1", "I7")),
    ("avenues", "Main streets run clean", ("G4", "G6", "G8")),
    ("water", "Everything stands on dry land", ("G5", "G15")),
    ("parks", "Parks sit whole in their blocks", ("G16",)),
    ("landmarks", "Landmarks stand apart, where you put them", ("G3", "G14", "G17", "I3")),
    ("transit", "Lines run through their stations in order", ("G9", "I6")),
    ("names", "Names read clearly", ("G18", "I5")),
]
ZERO_TOL = ("G7", "G15")


def _ends_on(m, x, y, tol=3.0, skip=None):
    if x <= tol or y <= tol or x >= m["W"] - tol or y >= m["H"] - tol:
        return True
    from .city_gate import _inside, _line_d
    for s in m["streets"]:
        if s is skip:
            continue
        p = s["p"]
        if min(p[0::2]) - tol <= x <= max(p[0::2]) + tol and min(p[1::2]) - tol <= y <= max(p[1::2]) + tol and _line_d(p, x, y) <= tol:
            return True
    for r in m.get("water") or []:
        if _inside(r, x, y) or _line_d(r + r[:2], x, y) <= 40:
            return True
    for rv in m.get("rivers") or []:
        if _line_d(rv["p"], x, y) <= max(WIDTH.values()) / 2 + 40:
            return True
    return False


def i_rows(m, g) -> dict:
    """The invented-city rows (rules 14.3 NEW): (status, msg, data) each."""
    rows = {}
    gr = g.get("grid") or {}
    bad = []
    for key, step in (("xg", 240.0), ("yg", 170.0)):
        v = gr.get(key) or []
        bad += [round(b - a) for a, b in zip(v, v[1:]) if abs((b - a) - step) > .1 * step]
    rows["I1"] = ("warn" if bad else "ok", "%d uneven block widths in the page lattice" % len(bad), {"uneven": bad[:20]})
    loose = []
    for s in m["streets"]:
        p = s["p"]
        if len(p) >= 4 and (p[0], p[1]) == (p[-2], p[-1]):
            continue                                            # a ring road
        for x, y in ((p[0], p[1]), (p[-2], p[-1])):
            if not _ends_on(m, x, y, skip=s):
                loose.append(s["n"])
    loose = sorted(set(loose))
    rows["I2"] = ("fail" if loose else "ok", "%d streets end on nothing" % len(loose), {"streets": loose})
    sta = {_norm(s["n"]) for s in m.get("stations") or []}
    L = [l for l in g.get("landmarks") or [] if l.get("box") and _norm(l.get("n")) not in sta]
    close = []
    for i in range(len(L)):
        for b in L[i + 1:]:
            a = L[i]
            if math.hypot(a["x"] - b["x"], a["y"] - b["y"]) < 240 * .99:
                close.append((a["n"], b["n"]))
    rows["I3"] = ("warn" if close else "ok", "%d landmark pairs closer than a block" % len(close), {"close": close[:20]})
    ds = (m.get("plan") or {}).get("districts") or []
    orphans = []
    if len(ds) > 1:
        from .city_gate import _inside, _line_d
        own = {}
        for s in m["streets"]:
            p = s["p"]
            for d in ds:
                ring = d["ring"]
                if any(_inside(ring, x, y) or _line_d(ring + ring[:2], x, y) < 5 for x, y in zip(p[0::2], p[1::2])):
                    own.setdefault(s["n"], set()).add(d["name"])
        link = {d["name"]: set() for d in ds}
        for n, dd in own.items():
            for a in dd:
                link[a] |= dd - {a}
        seen, todo = set(), [ds[0]["name"]]
        while todo:
            n = todo.pop()
            if n not in seen:
                seen.add(n)
                todo += list(link.get(n, ()))
        orphans = [d["name"] for d in ds if d["name"] not in seen]
    rows["I4"] = ("fail" if orphans else "ok", "%d districts no street reaches" % len(orphans), {"orphans": orphans})
    fam = {}
    for s in m["streets"]:
        p = s["p"]
        ang = round(math.degrees(math.atan2(p[-1] - p[1], p[-2] - p[0])) % 180 / 15) % 12
        fam.setdefault(s["n"], set()).add(ang)
    dup = sorted(n for n, a in fam.items() if len(a) > 1 and not any(t in n for t in ("Ring", "Circle", "Lane", "Shore")))
    rows["I5"] = ("warn" if dup else "ok", "%d names used by streets that are not one line" % len(dup), {"names": dup})
    drawn = {_norm(s.get("n")): s for s in g.get("stations") or []}
    back = []
    for ln in (m.get("plan") or {}).get("lines") or []:
        xs = [drawn[_norm(n)]["x"] for n in ln["stops"] if _norm(n) in drawn]
        if len(xs) < 2 or not (xs == sorted(xs) or xs == sorted(xs, reverse=True)):
            back.append(ln["name"])
    free = [d["name"] for d in ds if d["kind"] != "grid"]
    drawn_free = len((g.get("engine") or {}).get("free") or [])
    lost = free if free and drawn_free < len(free) else []
    rows["I7"] = ("warn" if lost else "ok", "%d organic or radial districts drawn as grid" % len(lost) if lost else
                  "every district drawn as its kind", {"districts": lost})
    through = []
    for r in g.get("rails") or []:                          # a line drawn through a landmark's block
        p = r.get("p") or []
        through += [(r.get("n"), l["n"]) for l in g.get("landmarks") or [] if l.get("box") and len(p) == 4 and
                    l["box"][1] < p[1] < l["box"][3] and min(p[0], p[2]) < l["box"][2] and max(p[0], p[2]) > l["box"][0]]
    rows["I6"] = ("warn" if back or through else "ok", "%d lines double back or lost a station; %d run through a landmark" % (
        len(back), len({t[0] for t in through})), {"lines": back, "through": through})
    return rows


def _plain(cid, rows, spec):
    """What the user reads for one check, and its one-tap fix (None when it passes)."""
    d = {r: (rows[r][2] or {}) for r in rows}
    st = {r: rows[r][0] for r in rows}
    bad = lambda *rs: [r for r in rs if st.get(r) in ("fail", "warn")]  # noqa: E731
    lms = [l for l in spec.get("landmarks") or [] if (l.get("kind") or "civic") not in ("park", "station")]
    if cid == "streets":
        if bad("I4"):
            o = d["I4"].get("orphans") or []
            other = next((x["name"] for x in spec["districts"] if x["name"] not in o), None)
            return ("No street reaches %s." % ", ".join(o), {"label": "Join %s to %s with a main street" % (o[0], other),
                                                              "op": "join", "a": o[0], "b": other})
        if bad("I2", "G7"):
            ss = d.get("I2", {}).get("streets") or []
            mine = [x["name"] for x in spec.get("streets") or [] if x["name"] in ss]
            return ("%s in the middle of nowhere." % ((", ".join(ss[:4]) + (" stops" if len(ss) == 1 else " stop")) if ss
                                                     else "Some streets stop"),
                    {"label": "Take off the loose streets", "op": "drop_streets", "names": mine or ss})
    elif cid == "blocks":
        if bad("G13", "G11", "G1"):
            return ("Districts sit on top of each other, so some blocks are cut.",
                    {"label": "Spread the districts out", "op": "spread_districts"})
        if bad("I7") and not bad("I1", "G2", "G12"):
            return ("%s is drawn as a grid, not as you planned it." % ", ".join(d["I7"].get("districts") or []),
                    {"label": "Make it a grid district", "op": "grid_districts", "names": d["I7"].get("districts") or []})
        if bad("I1", "G2", "G12"):
            return ("Some blocks are not the same size.", {"label": "Even out the blocks", "op": "even_blocks"})
    elif cid == "avenues":
        if bad("G4", "G8", "G6"):
            av = [a[0] for a in (d.get("G4", {}).get("order") or {}).get("avenues") or []]
            av += [x["name"] for x in spec.get("streets") or [] if x.get("diagonal") and x["name"] not in av and bad("G8")]
            return ("%s cross%s the grid out of step." % (", ".join(av) or "A main street", "es" if len(av) <= 1 else ""),
                    {"label": "Straighten %s" % (", ".join(av) or "the main streets"), "op": "drop_streets", "names": av})
    elif cid == "water":
        if bad("G15", "G5"):
            wet = sorted({w[1] for w in d.get("G15", {}).get("wet") or [] if w[1]} |
                         {b.split(": ", 1)[-1] for b in (d.get("G5", {}).get("side") or {}).get("bad") or []})
            return ("%s %s in the water or across it." % (", ".join(wet) or "Something", "is" if len(wet) == 1 else "are"),
                    {"label": "Move them onto dry land", "op": "unpin", "names": wet})
    elif cid == "parks":
        if bad("G16"):
            return ("A street runs through a park, or a park is missing.", {"label": "Give the parks their own blocks",
                                                                          "op": "unpin", "kinds": ["park"]})
    elif cid == "landmarks":
        if st.get("G17") == "fail" and (d.get("G17", {}).get("overlaps")):
            return ("Some landmarks overlap.", {"label": "Space the landmarks out", "op": "unpin", "kinds": ["tower", "civic"]})
        n = sum(1 for l in g_landmarks_of(rows))
        if st.get("G17") == "fail" and n < 8:
            return ("A city needs at least 8 landmarks; this one has %d." % n,
                    {"label": "Add %d landmarks" % (8 - n), "op": "add_landmarks", "n": 8 - n})
        if st.get("G17") == "fail":
            extra = [l["name"] for l in lms][24:]
            return ("Too many landmarks to read (at most 24).", {"label": "Keep the first 24", "op": "drop_landmarks",
                                                                "names": extra})
        if bad("G3", "G14", "I3"):
            return ("Some landmarks are crowded or drawn away from where you put them.",
                    {"label": "Space the landmarks out", "op": "unpin", "kinds": ["tower", "civic", "station"]})
    elif cid == "transit":
        thr = d.get("I6", {}).get("through") or []
        if thr and not d["I6"].get("lines"):
            return ("%s runs through %s." % (thr[0][0], ", ".join(sorted({t[1] for t in thr}))),
                    {"label": "Move the landmarks off the line", "op": "unpin", "names": sorted({t[1] for t in thr})})
        if bad("I6", "G9"):
            ls = d.get("I6", {}).get("lines") or []
            return ("%s double%s back or lost a station." % (", ".join(ls) or "A line", "s" if len(ls) <= 1 else ""),
                    {"label": "Put the stations in order", "op": "order_stops", "lines": ls})
    elif cid == "names":
        if bad("G18", "I5"):
            return ("Some names sit on top of each other.", {"label": "Show only the biggest district name up close",
                                                            "op": "quiet_names"})
    return ("", None)


def g_landmarks_of(rows):
    msg = rows.get("G17", ("", "", {}))[1] or ""
    m_ = re.match(r"(\d+) landmarks", msg)
    return range(int(m_.group(1)) if m_ else 0)


def check(spec, m=None, g=None) -> dict:
    """Build the spec and run the invented-city gate: {"pass", "score", "checks": [the eight, each {id, title, ok, status,
    why, fix}], "rows": {row: {...}}, "notes", "problems"}. A spec that cannot be built: pass False, its problems."""
    from . import city_gate
    if m is None or g is None:
        try:
            m, g = build(spec)
        except InventError as e:
            return {"pass": False, "score": 0.0, "problems": e.problems, "checks": [], "rows": {}, "notes": []}
    mm = {k: v for k, v in m.items() if k != "plan"}
    try:                                                    # the district names where the page lays them out (the names row)
        from .palace_areas import layout as area_layout
        areas = area_layout(g, (m.get("plan") or {}).get("areas") or [], [])
    except Exception:                                       # noqa: BLE001 — a city with nothing to name
        areas = []
    rep = city_gate.gate(g, mm, preset={"parks": (m.get("plan") or {}).get("parks") or ()}, areas=areas)
    rows = {r: (c["status"], c["msg"], c.get("data") or {}) for r, c in rep["checks"].items() if r not in DROP}
    rows.update(i_rows(m, g))
    weight = {r: w for r, _n, w in city_gate.ROWS}
    weight.update({r: w for r, _n, w in IROWS})
    tot = sum(weight[r] for r in rows)
    got = sum(weight[r] * {"ok": 1.0, "warn": .5}.get(rows[r][0], 0.0) for r in rows)
    score = round(100.0 * got / tot, 1) if tot else 0.0
    fails = [r for r in rows if rows[r][0] == "fail"]
    ok = not fails and score >= city_gate.PASS_SCORE and all(r in rows for r in ZERO_TOL)
    checks = []
    for cid, title, rs in CHECKS:
        sts = [rows[r][0] for r in rs if r in rows]
        stt = "fail" if "fail" in sts else ("warn" if "warn" in sts else "ok")
        why, fix = _plain(cid, rows, spec) if stt != "ok" else ("", None)
        checks.append({"id": cid, "title": title, "ok": stt == "ok", "status": stt, "why": why, "fix": fix})
    names = dict(city_gate.ROWS and [(r, n) for r, n, _w in city_gate.ROWS] + [(r, n) for r, n, _w in IROWS])
    return {"pass": ok, "score": score, "checks": checks, "problems": [],
            "rows": {r: {"rule": names.get(r, r), "status": rows[r][0], "msg": rows[r][1]} for r in rows},
            "notes": (m.get("plan") or {}).get("notes") or []}


def apply_fix(spec, fix) -> dict:
    """The one-tap fix: a new spec (the old one is not changed). fix is a check's `fix` from check()."""
    sp = copy.deepcopy(spec)
    op = (fix or {}).get("op")
    if op == "join":
        sp.setdefault("streets", []).append({"name": "%s Road" % fix["a"].split()[0], "class": "main", "from": fix["a"],
                                             "to": fix["b"]})
    elif op == "drop_streets":
        names = {_norm(n) for n in fix.get("names") or []}
        sp["streets"] = [s for s in sp.get("streets") or [] if _norm(s.get("name")) not in names]
    elif op == "spread_districts":
        for d in sp.get("districts") or []:
            d.pop("center", None)                           # laid out again west to east, a block apart
    elif op == "grid_districts":
        names = {_norm(n) for n in fix.get("names") or []}
        for d in sp.get("districts") or []:
            if _norm(d.get("name")) in names:
                d["kind"] = "grid"
    elif op == "even_blocks":
        for d in sp.get("districts") or []:
            d.pop("block", None)
    elif op == "unpin":
        names = {_norm(n) for n in fix.get("names") or []}
        kinds = set(fix.get("kinds") or ())
        grid_d = next((d["name"] for d in sp.get("districts") or [] if (d.get("kind") or "grid") == "grid"), None)
        for lm in sp.get("landmarks") or []:
            if _norm(lm.get("name")) in names or (lm.get("kind") or "civic") in kinds:
                if _pt(lm.get("at")) or lm.get("at") is None:
                    ds = sp.get("districts") or []
                    p = lm.get("at") or [0, 0]
                    lm["at"] = min(ds, key=lambda d: (d["center"][0] - p[0]) ** 2 + (d["center"][1] - p[1]) ** 2)["name"] \
                        if ds and all(d.get("center") for d in ds) else grid_d
    elif op == "add_landmarks":
        have = {_norm(l.get("name")) for l in sp.get("landmarks") or []}
        pool = [n for n in _LANDMARKS if _norm(n) not in have]
        ds = [d["name"] for d in sp.get("districts") or []] or [None]
        for i, n in enumerate(pool[:int(fix.get("n") or 1)]):
            sp.setdefault("landmarks", []).append({"name": n, "at": ds[i % len(ds)], "kind": "civic"})
    elif op == "drop_landmarks":
        names = {_norm(n) for n in fix.get("names") or []}
        sp["landmarks"] = [l for l in sp.get("landmarks") or [] if _norm(l.get("name")) not in names]
    elif op == "order_stops":
        m = invent_city(sp)
        pos = {_norm(s["n"]): s["x"] for s in m["stations"]}
        for ln in sp.get("transit") or []:
            if not fix.get("lines") or ln.get("name") in fix["lines"]:
                ln["stops"] = sorted(ln.get("stops") or [], key=lambda n: pos.get(_norm(n), 0))
    elif op == "quiet_names":
        sp["quiet_names"] = True
    else:
        raise InventError(["there is no fix called %r" % op])
    return sp


def set_up(spec, districts=None, buildings=None, check_first=True) -> tuple:
    """The brief.palace dict of an invented city (palace.set_up on the plan: nothing fetched, no fill-in, no tiles: there
    are no real footprints), and its gate report. districts: the timeline's sections [{unit, name, bounds}] (omitted:
    one per plan district, as the user named them). buildings: the timeline's own landmark buildings [{name, page?, unit?,
    floors?}] (they take the plan's landmarks of the same name; the rest stay plain landmarks).
    -> (pal, rep). pal["gate"] = {"pass", "score", "draft": not passed, "failing": [plain words]}."""
    from . import palace
    m, g = build(spec)
    rep = check(spec, m, g)
    pl = m["plan"]
    mine = {_norm(b.get("name")): b for b in buildings or [] if b.get("name")}
    blds = [{**lm, **mine.get(_norm(lm["name"]), {})} for lm in pl["landmarks"]]
    if not districts:
        bb = m["bbox"]
        districts = [{"unit": i, "name": d["name"],
                      "bounds": [bb[2] * (1 - (d["y"] + d["h"] / 2) / m["H"]), bb[3] * (d["x"] - d["w"] / 2) / m["W"],
                                 bb[2] * (1 - (d["y"] - d["h"] / 2) / m["H"]), bb[3] * (d["x"] + d["w"] / 2) / m["W"]]}
                     for i, d in enumerate(pl["districts"])]
    pal = palace.set_up(m["place"], list(m["bbox"]), districts=districts, majors=pl["majors"],
                        landmarks=[b["name"] for b in blds], diagonals=pl["diagonals"], lines=pl["lines"], buildings=blds,
                        parks=pl["parks"], areas=pl["areas"], offline=True, preset="invented", fill=False,
                        city_tiles=False, plan=m)
    pal["invented"] = copy.deepcopy(spec)
    pal["gate"] = {"pass": rep["pass"], "score": rep["score"], "draft": not rep["pass"],
                   "failing": [c["why"] or c["title"] for c in rep["checks"] if c["status"] == "fail"]}
    return pal, rep
