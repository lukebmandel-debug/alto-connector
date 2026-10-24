"""The Memory Blueprint's plan: one building, measured, as data (brief.palace_view "building").

A Memory Blueprint is a Memory Palace in ONE building: a blueprint map (the hosted renderer, palace_building_asset.py) and a first-person view
inside it (a later phase). Both read the same plan, so the plan carries what either needs and says how sure it is of each part. The plan is
authored by Claude from public sources (official floor plans, HABS drawings, visitor maps, photos, known dimensions) or by the user, checked
here, stored with the timeline (brief.building) and published as one content-hashed JSON file the page loads (/bldg/plan-<hash>.json).

Plan format, version 1 (JSON; short keys because the file is hosted and read by phones)
=====================================================================================
Units are METRES. x runs east, y runs north (the renderer flips y for the screen), z up. Angles are degrees, 0 = +x (east), counter-clockwise
(90 = north). A "point" is [x, y]; a "polygon" is a list of points, not closed (the last joins the first), at least 3. Coordinates are
rounded to the centimetre. Every element id is a short lowercase token ([a-z][a-z0-9-]{0,31}), unique within its kind.

Every element may carry  c  (confidence 0-3) and  s  (source ids, a list into `src`). Confidence: 0 a placeholder/guess (a room box sketched
from a visitor map), 1 estimated from photographs or a schematic, 2 drawn from an official plan or stated dimensions, 3 measured/surveyed.
An element without c has the plan's default `c`. The renderer shades c<=1 geometry as approximate and the guide has Claude say so.

top level
  v        1 (format version)                         id, name      the building's token and its name
  kind     "museum"|"courthouse"|"library"|"school"|"house"|"church"|"civic"|"hall"|"other"
  geo      {lat, lon, north}  optional: where the plan origin stands; north = compass bearing of +y (0 = plan north is true north)
  src      [{id, t: title, u: url, k: "official-plan"|"survey"|"archive"|"visitor-map"|"photo"|"open-data"|"estimate"|"user",
             lic: licence/terms in a few words, n: note}]
  c        default confidence (0-3; default 1)
  tour     optional [room ids]: the walking order Alto uses to hand rooms to nodes (default: the entrance level, then up, by room number)
  lv       LEVELS [{id, n: name, lb: short label ("1", "G", "Mezz"), e: finished-floor elevation m, h: floor-to-floor height m}]
  wl       WALLS  [{id, l: level, p: polyline [[x,y]...] along the wall's centre line (>=2 points), loop: true closes it, t: thickness m,
                    m: material, h: height m (default the level's h), k: "ext"|"int"|"party"|"screen"|"rail" (rail: a balustrade, ~1 m),
                    o: OPENINGS [{k: "door"|"window"|"arch"|"gap"|"gate", a: metres along the polyline to the opening's CENTRE, w: width,
                    h: height, z: sill height (a door's is 0), m: leaf/frame material, d: "single"|"double"|"none"}]}]
  rm       ROOMS  [{id, l: level, n: name, no: room/gallery number as signed ("171"), ty: type, p: polygon (the floor outline), ch: ceiling
                    height m, fm/wm/cm: floor/wall/ceiling material, li: lighting {k: "sky"|"day"|"art"|"dim"|"mixed", lx: lux (optional)}}]
           types: gallery hall lobby stair-hall court auditorium reading-room office classroom chamber library shop cafe corridor service
           restroom stair lift other — corridor, service, restroom, stair, lift are circulation: Alto never hands them a node.
  st       VERTICAL LINKS [{id, k: "stair"|"elevator"|"ramp"|"escalator", from: level id, to: level id, fp: footprint polygon on `from`,
                    w: clear width m, n: step count (stairs), up: direction of ascent in degrees (stairs/ramps),
                    fl: FLIGHTS [{a: [x,y,z], b: [x,y,z], w}] (optional, exact runs for the first-person view; z is absolute elevation),
                    ld: LANDINGS [{p: polygon, z}] (optional)}]   a stair that crosses several levels is one entry per pair of levels
  cols     COLUMNS [{id, l, p: point, r: radius m (round) or sz: [w, d] (square), h: height (default the level's h), o: order ("doric"...),
                    m: material}]
  fx       FIXTURES [{id, l, k: "bench"|"case"|"plinth"|"table"|"desk"|"shelf"|"fountain"|"statue"|"counter"|"stove"|"other",
                    p: point, rot: degrees, sz: [w, d, h], m: material, n: name}]   case, plinth, table, desk, shelf, statue and stove are
           ANCHORS: an object can stand on or in them
  sl       ART SLOTS [{id, rm: room id, w: wall id (optional), p: point on the wall face, z: height of the centre m, sz: [w, h] m, fc: facing
                    (the direction the work faces, degrees), al: allowed ["painting"|"drawing"|"print"|"relief"|"tapestry"|"textile"|
                    "sculpture"|"object"|"text"|"any"]}]   a place a work can hang or stand
  ex       EXTERIOR {sh: SHELL [{id, p: footprint polygon, h: eave height, rf: {k: "flat"|"gable"|"hip"|"dome"|"vault"|"none", h: rise m},
                    m: material, z: base elevation (default 0)}],
                    stp: STEPS [{id, p: polygon, z0, z1, n: step count, up: direction of ascent}],
                    tr: TERRACES [{id, p: polygon, z, m, n: name}], gz: ground elevation m at the entrance front}
  en       ENTRANCES [{id, n: name, l: level, p: point, fc: facing out (degrees), w: width m, k: "main"|"side"|"service"|"accessible",
                    wall: wall id (optional)}]

Optional extension keys (carried and hosted, never validated; the blueprint reads the starred ones, curated plans such as buildings/pma.py write them all)
  top level  n   a note (plan.n, shown in the blueprint's credits box)*;  ca  AREA LEGEND [{id, n: name, c: colour}]* — the sections (collection areas) rooms belong to
  src[]      cr  the credit line the blueprint footer shows*
  rooms      ca  area id*;  x28 "no"|"partly"|"likely"|"yes"|"new": changed since the source plan (1928 for the PMA; "new" = a modern space not on it)*;  nt  a note*;
             ov  1 = a measured overlay drawn dotted*;  no/n28/gm/cand  the gallery number, the source plan's own label, how the number was matched (or why left off), candidate numbers;
             hb/hc  basis and confidence 0-3 of the ceiling height;  mb  basis of the finishes;  bs  basis text;  pd  published dimensions {ns, ew, ...};  c 0 is drawn blurred* ("estimated")
  levels     eb/ec  basis and confidence of the floor elevation
  st[]       tp  the footprint on the `to` level (the stitched upper end), tb its basis, dz the rise
  sl[]       work {title, artist, date, credit, pma_url, img} the work the slot holds (img: a hosted /bart/... URL only for a clean public-domain image), gl the gallery number
             the work hangs in, pc "room"|"cand" (the room is that gallery, or only contains its label point), sr/sb size source and basis
Validation (validate_plan) raises PlanError with every problem, each naming its element ("rm[3] 'g171': polygon crosses itself"), and returns
warnings (approximate rooms, a slot floating off its wall, an unused source). Materials are a closed vocabulary (MATERIALS) plus "x:<name>" for
a one-off. `normalize` rounds, drops empty fields and orders keys so the same plan always hashes to the same 12 hex (plan_hash); `pack`/`unpack`
store it with the timeline (gzip+base64, like the palace's city); `hosted_json` is the file the site serves. `assign_nodes` hands nodes to
rooms or anchors by outline order, with the caller's overrides on top. `fixture()` is a tiny FAKE building for tests and demos (not real data).
"""
from __future__ import annotations

import base64
import copy
import gzip
import hashlib
import json
import math
import re

VERSION = 1
ID_RE = re.compile(r"[a-z][a-z0-9-]{0,31}")
KINDS = ("museum", "courthouse", "library", "school", "house", "church", "civic", "hall", "other")
SRC_KINDS = ("official-plan", "survey", "archive", "visitor-map", "photo", "open-data", "estimate", "user")
MATERIALS = ("marble", "limestone", "sandstone", "granite", "stone", "brick", "plaster", "paint", "wood", "parquet", "plank", "tile", "terrazzo",
             "concrete", "carpet", "glass", "metal", "bronze", "gilt", "fabric", "leather", "slate", "copper", "terracotta", "lath", "none")
ROOM_TYPES = ("gallery", "hall", "lobby", "stair-hall", "court", "auditorium", "reading-room", "office", "classroom", "chamber", "library",
              "shop", "cafe", "corridor", "service", "restroom", "stair", "lift", "other")
CIRCULATION = ("corridor", "service", "restroom", "stair", "lift")
WALL_KINDS = ("ext", "int", "party", "screen", "rail")
OPENING_KINDS = ("door", "window", "arch", "gap", "gate")
DOOR_LEAVES = ("single", "double", "none")
LIGHT_KINDS = ("sky", "day", "art", "dim", "mixed")
LINK_KINDS = ("stair", "elevator", "ramp", "escalator")
FIXTURE_KINDS = ("bench", "case", "plinth", "table", "desk", "shelf", "fountain", "statue", "counter", "stove", "other")
ANCHOR_FIXTURES = ("case", "plinth", "table", "desk", "shelf", "statue", "stove")
WORKS = ("painting", "drawing", "print", "relief", "tapestry", "textile", "sculpture", "object", "text", "any")
ROOFS = ("flat", "gable", "hip", "dome", "vault", "none")
ENTRANCE_KINDS = ("main", "side", "service", "accessible")
ASSIGN_MODES = ("room", "anchor")
ART_IMG_RE = re.compile(r"/bart/[a-z0-9][a-z0-9-]{0,80}\.(jpg|jpeg|png|webp)")      # a work's image: only a file the site itself hosts
MAX_PLAN_BYTES = 1_500_000          # the JSON text, before gzip: far above any real building, a guard against a runaway generator


class PlanError(ValueError):
    """A building plan that cannot be used; `.problems` lists every reason, each naming its element."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems[:12]) + (f"; and {len(self.problems) - 12} more" if len(self.problems) > 12 else ""))


# ── geometry ────────────────────────────────────────────────────────────────

def _pt(p):
    return (isinstance(p, (list, tuple)) and len(p) == 2 and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in p))


def area(poly) -> float:
    """Signed shoelace area (m²): positive for a counter-clockwise polygon."""
    s = 0.0
    for i, (x0, y0) in enumerate(poly):
        x1, y1 = poly[(i + 1) % len(poly)]
        s += x0 * y1 - x1 * y0
    return s / 2


def length(line, loop=False) -> float:
    pts = list(line) + ([line[0]] if loop and line else [])
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _seg_cross(a, b, c, d) -> bool:
    """True when segment ab properly crosses segment cd (touching ends do not count)."""
    d1, d2, d3, d4 = _cross(c, d, a), _cross(c, d, b), _cross(a, b, c), _cross(a, b, d)
    return ((d1 > 1e-9 and d2 < -1e-9) or (d1 < -1e-9 and d2 > 1e-9)) and ((d3 > 1e-9 and d4 < -1e-9) or (d3 < -1e-9 and d4 > 1e-9))


def self_crossing(poly) -> bool:
    n = len(poly)
    for i in range(n):
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or (i + 1) % n == j:
                continue
            if _seg_cross(poly[i], poly[(i + 1) % n], poly[j], poly[(j + 1) % n]):
                return True
    return False


def inside(poly, p) -> bool:
    x, y = p
    c = False
    for i, (x0, y0) in enumerate(poly):
        x1, y1 = poly[(i + 1) % len(poly)]
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            c = not c
    return c


def dist_to_edge(poly, p) -> float:
    best = 1e18
    for i, a in enumerate(poly):
        b = poly[(i + 1) % len(poly)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        l2 = dx * dx + dy * dy
        t = 0 if l2 == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
        best = min(best, math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy))
    return best


def bounds(plan, level=None):
    """[x0, y0, x1, y1] of the walls, rooms and shell (of one level's, when given); None for an empty plan."""
    xs, ys = [], []
    def take(pts):
        for p in pts:
            xs.append(p[0]); ys.append(p[1])
    for w in plan.get("wl") or []:
        if level is None or w.get("l") == level:
            take(w.get("p") or [])
    for r in plan.get("rm") or []:
        if level is None or r.get("l") == level:
            take(r.get("p") or [])
    for s in (plan.get("ex") or {}).get("sh") or []:
        take(s.get("p") or [])
    return [min(xs), min(ys), max(xs), max(ys)] if xs else None


# ── validation ──────────────────────────────────────────────────────────────

def _num(v, lo=None, hi=None) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and (lo is None or v >= lo) and (hi is None or v <= hi)


def _mat(m) -> bool:
    return m in MATERIALS or (isinstance(m, str) and re.fullmatch(r"x:[A-Za-z0-9 _-]{1,24}", m) is not None)


def validate_plan(plan) -> list:
    """Check a building plan; raise PlanError listing every problem, else return warnings (a list of strings)."""
    errs, warns = [], []
    if not isinstance(plan, dict):
        raise PlanError(["plan: must be an object"])
    if plan.get("v") != VERSION:
        errs.append(f"v: must be {VERSION}")
    allowed = {"v", "id", "name", "kind", "geo", "src", "c", "tour", "lv", "wl", "rm", "st", "cols", "fx", "sl", "ex", "en", "n", "ca", "sp"}
    for k in sorted(set(plan) - allowed):
        errs.append(f"plan: unknown key {k!r}")
    if not (isinstance(plan.get("id"), str) and ID_RE.fullmatch(plan["id"])):
        errs.append("id: a short lowercase token (a-z, 0-9, -), e.g. 'pma'")
    if not (isinstance(plan.get("name"), str) and plan["name"].strip() and len(plan["name"]) <= 120):
        errs.append("name: the building's name (up to 120 characters)")
    if plan.get("kind", "other") not in KINDS:
        errs.append(f"kind {plan.get('kind')!r}: must be one of {KINDS}")
    dc = plan.get("c", 1)
    if not (isinstance(dc, int) and not isinstance(dc, bool) and 0 <= dc <= 3):
        errs.append("c: default confidence is a whole number 0-3")
    geo = plan.get("geo")
    if geo is not None and not (isinstance(geo, dict) and _num(geo.get("lat"), -90, 90) and _num(geo.get("lon"), -180, 180)
                                and (geo.get("north") is None or _num(geo.get("north"), -360, 360))):
        errs.append("geo: {lat, lon, north?} in degrees")

    # sources
    srcs = {}
    for i, s in enumerate(plan.get("src") or []):
        w = f"src[{i}]"
        if not isinstance(s, dict) or not (isinstance(s.get("id"), str) and ID_RE.fullmatch(s["id"])):
            errs.append(f"{w}: needs an id token"); continue
        if s["id"] in srcs:
            errs.append(f"{w} {s['id']!r}: duplicate id")
        srcs[s["id"]] = 0
        if not (isinstance(s.get("t"), str) and s["t"].strip()):
            errs.append(f"{w} {s['id']!r}: t (the source's title) is needed")
        if s.get("k") not in SRC_KINDS:
            errs.append(f"{w} {s['id']!r}: k must be one of {SRC_KINDS}")
        if s.get("u") is not None and not (isinstance(s["u"], str) and re.match(r"https?://", s["u"])):
            errs.append(f"{w} {s['id']!r}: u must be an http(s) link")

    def common(elem, w):
        c = elem.get("c")
        if c is not None and not (isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 3):
            errs.append(f"{w}: c is a whole number 0-3")
        ss = elem.get("s")
        if ss is not None:
            if not isinstance(ss, list):
                errs.append(f"{w}: s is a list of source ids"); return
            for x in ss:
                if x not in srcs:
                    errs.append(f"{w}: source {x!r} is not in src")
                else:
                    srcs[x] += 1

    def ident(e, w, seen):
        if not isinstance(e, dict):
            errs.append(f"{w}: must be an object"); return None
        i = e.get("id")
        if not (isinstance(i, str) and ID_RE.fullmatch(i)):
            errs.append(f"{w}: needs an id token (a-z, 0-9, -)"); return None
        if i in seen:
            errs.append(f"{w} {i!r}: duplicate id")
        seen.add(i)
        common(e, f"{w} {i!r}")
        return i

    def poly_ok(p, w, minpts=3, want_area=True):
        if not (isinstance(p, list) and len(p) >= minpts and all(_pt(q) for q in p)):
            errs.append(f"{w}: needs a polygon of at least {minpts} [x, y] points in metres"); return False
        if want_area:
            if self_crossing(p):
                errs.append(f"{w}: polygon crosses itself"); return False
            if abs(area(p)) < 0.05:
                errs.append(f"{w}: the polygon has no area"); return False
        return True

    # levels
    levels, seen = {}, set()
    for i, lv in enumerate(plan.get("lv") or []):
        w = f"lv[{i}]"
        k = ident(lv, w, seen)
        if k is None:
            continue
        if not _num(lv.get("e")):
            errs.append(f"{w} {k!r}: e (floor elevation, metres) is needed")
        if not _num(lv.get("h"), 1.8, 40):
            errs.append(f"{w} {k!r}: h (floor-to-floor height, 1.8-40 m) is needed")
        if not (isinstance(lv.get("n"), str) and lv["n"].strip()):
            errs.append(f"{w} {k!r}: n (name) is needed")
        levels[k] = lv
    if not levels:
        errs.append("lv: a plan needs at least one level")
    elev = sorted(lv["e"] for lv in levels.values() if _num(lv.get("e")))
    if len(set(elev)) != len(elev):
        errs.append("lv: two levels share an elevation")

    def lvl(e, w):
        l = e.get("l")
        if l not in levels:
            errs.append(f"{w}: level {l!r} is not in lv")
            return None
        return levels[l]

    def lh(l):
        return levels[l]["h"] if l in levels and _num(levels[l].get("h")) else 4.0

    # walls
    walls, seen = {}, set()
    for i, wl in enumerate(plan.get("wl") or []):
        w = f"wl[{i}]"
        k = ident(wl, w, seen)
        if k is None:
            continue
        w = f"wl[{i}] {k!r}"
        walls[k] = wl
        lvl(wl, w)
        if not poly_ok(wl.get("p"), w, 2, want_area=False):
            continue
        if not _num(wl.get("t"), 0.02, 4):
            errs.append(f"{w}: t (thickness, 0.02-4 m) is needed")
        if not _mat(wl.get("m", "plaster")):
            errs.append(f"{w}: material {wl.get('m')!r} is not in the vocabulary (use one of MATERIALS or 'x:<name>')")
        if wl.get("k", "int") not in WALL_KINDS:
            errs.append(f"{w}: k must be one of {WALL_KINDS}")
        if wl.get("h") is not None and not _num(wl["h"], 0.3, 40):
            errs.append(f"{w}: h must be 0.3-40 m")
        total = length(wl["p"], bool(wl.get("loop")))
        if total < 0.05:
            errs.append(f"{w}: the wall has no length")
        height = wl["h"] if _num(wl.get("h")) else lh(wl.get("l"))
        spans = []
        for j, o in enumerate(wl.get("o") or []):
            ow = f"{w} opening {j}"
            if not isinstance(o, dict) or o.get("k") not in OPENING_KINDS:
                errs.append(f"{ow}: k must be one of {OPENING_KINDS}"); continue
            if not (_num(o.get("a"), 0) and _num(o.get("w"), 0.2, 30) and _num(o.get("h"), 0.2, 40)):
                errs.append(f"{ow}: a (metres along the wall), w and h are needed"); continue
            z = o.get("z", 0)
            if not _num(z, 0):
                errs.append(f"{ow}: z (sill height) must be 0 or more"); continue
            if o["a"] - o["w"] / 2 < -0.01 or o["a"] + o["w"] / 2 > total + 0.01:
                errs.append(f"{ow}: runs off the wall ({total:.2f} m long; centre {o['a']}, width {o['w']})")
            if z + o["h"] > height + 0.01:
                errs.append(f"{ow}: reaches {z + o['h']:.2f} m, above the wall's {height:.2f} m")
            if o.get("m") is not None and not _mat(o["m"]):
                errs.append(f"{ow}: material {o['m']!r} is not in the vocabulary")
            if o.get("d") is not None and o["d"] not in DOOR_LEAVES:
                errs.append(f"{ow}: d must be one of {DOOR_LEAVES}")
            spans.append((o["a"] - o["w"] / 2, o["a"] + o["w"] / 2, j))
        spans.sort()
        for (a0, a1, j0), (b0, b1, j1) in zip(spans, spans[1:]):
            if b0 < a1 - 0.01:
                errs.append(f"{w}: openings {j0} and {j1} overlap")

    # rooms
    rooms, seen = {}, set()
    for i, r in enumerate(plan.get("rm") or []):
        w = f"rm[{i}]"
        k = ident(r, w, seen)
        if k is None:
            continue
        w = f"rm[{i}] {k!r}"
        rooms[k] = r
        lvl(r, w)
        if not (isinstance(r.get("n"), str) and r["n"].strip()):
            errs.append(f"{w}: n (the room's name) is needed")
        if r.get("no") is not None and not (isinstance(r["no"], str) and len(r["no"]) <= 16):
            errs.append(f"{w}: no is the room number as a short string")
        if r.get("ty", "other") not in ROOM_TYPES:
            errs.append(f"{w}: ty must be one of {ROOM_TYPES}")
        if poly_ok(r.get("p"), w) and abs(area(r["p"])) < 1.0:
            warns.append(f"{w}: only {abs(area(r['p'])):.1f} m²")
        ch = r.get("ch")
        if not _num(ch, 1.8, 40):
            errs.append(f"{w}: ch (ceiling height, 1.8-40 m) is needed")
        elif r.get("l") in levels and ch > lh(r["l"]) * 2 + 0.01:
            warns.append(f"{w}: ceiling {ch} m is more than twice its level's {lh(r['l'])} m (a double-height hall?)")
        for key in ("fm", "wm", "cm"):
            if r.get(key) is not None and not _mat(r[key]):
                errs.append(f"{w}: {key} {r[key]!r} is not in the material vocabulary")
        li = r.get("li")
        if li is not None and not (isinstance(li, dict) and li.get("k") in LIGHT_KINDS and (li.get("lx") is None or _num(li["lx"], 0, 200000))):
            errs.append(f"{w}: li is {{k: one of {LIGHT_KINDS}, lx?: lux}}")
        if (r.get("c", dc) if isinstance(r.get("c", dc), int) else dc) <= 0:
            warns.append(f"{w}: a placeholder (confidence 0) — it shows as approximate")

    # stairs, lifts, ramps
    seen = set()
    for i, s in enumerate(plan.get("st") or []):
        w = f"st[{i}]"
        k = ident(s, w, seen)
        if k is None:
            continue
        w = f"st[{i}] {k!r}"
        if s.get("k") not in LINK_KINDS:
            errs.append(f"{w}: k must be one of {LINK_KINDS}")
        a, b = s.get("from"), s.get("to")
        for nm, v in (("from", a), ("to", b)):
            if v not in levels:
                errs.append(f"{w}: {nm} level {v!r} is not in lv")
        if a in levels and b in levels and a == b:
            errs.append(f"{w}: from and to are the same level")
        poly_ok(s.get("fp"), f"{w} fp")
        if s.get("w") is not None and not _num(s["w"], 0.4, 30):
            errs.append(f"{w}: w (clear width) must be 0.4-30 m")
        if s.get("n") is not None and not (isinstance(s["n"], int) and 1 <= s["n"] <= 400):
            errs.append(f"{w}: n (steps) must be a whole number 1-400")
        if s.get("up") is not None and not _num(s["up"], -360, 360):
            errs.append(f"{w}: up is a direction in degrees")
        for j, f in enumerate(s.get("fl") or []):
            if not (isinstance(f, dict) and isinstance(f.get("a"), list) and len(f["a"]) == 3 and isinstance(f.get("b"), list) and len(f["b"]) == 3
                    and all(_num(v) for v in f["a"] + f["b"]) and _num(f.get("w", 1), 0.3, 30)):
                errs.append(f"{w} flight {j}: {{a: [x,y,z], b: [x,y,z], w}}")
        for j, ld in enumerate(s.get("ld") or []):
            if not (isinstance(ld, dict) and _num(ld.get("z"))):
                errs.append(f"{w} landing {j}: needs z")
            else:
                poly_ok(ld.get("p"), f"{w} landing {j}")
        if s.get("k") == "stair" and a in levels and b in levels and _num(levels[a].get("e")) and _num(levels[b].get("e")):
            rise = abs(levels[b]["e"] - levels[a]["e"])
            if s.get("n") and rise / s["n"] > 0.25:
                warns.append(f"{w}: {s['n']} steps over {rise:.2f} m is a {rise / s['n'] * 100:.0f} cm riser — too steep, or n is short")

    # columns
    seen = set()
    for i, c in enumerate(plan.get("cols") or []):
        w = f"cols[{i}]"
        k = ident(c, w, seen)
        if k is None:
            continue
        w = f"cols[{i}] {k!r}"
        lvl(c, w)
        if not _pt(c.get("p")):
            errs.append(f"{w}: p is [x, y]")
        if (c.get("r") is None) == (c.get("sz") is None):
            errs.append(f"{w}: give r (round) or sz [w, d] (square), not both or neither")
        elif c.get("r") is not None and not _num(c["r"], 0.03, 5):
            errs.append(f"{w}: r (radius) must be 0.03-5 m")
        elif c.get("sz") is not None and not (isinstance(c["sz"], list) and len(c["sz"]) == 2 and all(_num(v, 0.05, 10) for v in c["sz"])):
            errs.append(f"{w}: sz is [w, d] in metres")
        if c.get("h") is not None and not _num(c["h"], 0.3, 40):
            errs.append(f"{w}: h must be 0.3-40 m")
        if c.get("m") is not None and not _mat(c["m"]):
            errs.append(f"{w}: material {c['m']!r} is not in the vocabulary")

    # fixtures
    fixtures, seen = {}, set()
    for i, f in enumerate(plan.get("fx") or []):
        w = f"fx[{i}]"
        k = ident(f, w, seen)
        if k is None:
            continue
        w = f"fx[{i}] {k!r}"
        fixtures[k] = f
        lvl(f, w)
        if f.get("k") not in FIXTURE_KINDS:
            errs.append(f"{w}: k must be one of {FIXTURE_KINDS}")
        if not _pt(f.get("p")):
            errs.append(f"{w}: p is [x, y]")
        if not (isinstance(f.get("sz"), list) and len(f["sz"]) == 3 and all(_num(v, 0.02, 40) for v in f["sz"])):
            errs.append(f"{w}: sz is [w, d, h] in metres")
        if f.get("rot") is not None and not _num(f["rot"], -360, 360):
            errs.append(f"{w}: rot is degrees")
        if f.get("m") is not None and not _mat(f["m"]):
            errs.append(f"{w}: material {f['m']!r} is not in the vocabulary")

    # art slots
    slots, seen = {}, set()
    for i, sl in enumerate(plan.get("sl") or []):
        w = f"sl[{i}]"
        k = ident(sl, w, seen)
        if k is None:
            continue
        w = f"sl[{i}] {k!r}"
        slots[k] = sl
        room = rooms.get(sl.get("rm"))
        if room is None:
            errs.append(f"{w}: room {sl.get('rm')!r} is not in rm")
        if sl.get("w") is not None:
            wall = walls.get(sl["w"])
            if wall is None:
                errs.append(f"{w}: wall {sl['w']!r} is not in wl")
            elif room is not None and wall.get("l") != room.get("l"):
                errs.append(f"{w}: wall {sl['w']!r} is on another level than room {sl['rm']!r}")
        if not _pt(sl.get("p")):
            errs.append(f"{w}: p is [x, y]")
        elif room is not None and isinstance(room.get("p"), list) and len(room["p"]) >= 3 and all(_pt(q) for q in room["p"]):
            if not inside(room["p"], sl["p"]) and dist_to_edge(room["p"], sl["p"]) > 0.6:
                warns.append(f"{w}: stands {dist_to_edge(room['p'], sl['p']):.1f} m outside room {sl['rm']!r}")
            elif sl.get("w") is None and dist_to_edge(room["p"], sl["p"]) > 1.5 and sl.get("al", ["any"]) and "sculpture" not in (sl.get("al") or []):
                warns.append(f"{w}: hangs {dist_to_edge(room['p'], sl['p']):.1f} m from the room's edge (give it a wall, or allow sculpture)")
        if not _num(sl.get("z"), 0, 40):
            errs.append(f"{w}: z (height of the slot's centre) is needed")
        if not (isinstance(sl.get("sz"), list) and len(sl["sz"]) == 2 and all(_num(v, 0.05, 40) for v in sl["sz"])):
            errs.append(f"{w}: sz is [w, h] in metres")
        if not _num(sl.get("fc"), -360, 360):
            errs.append(f"{w}: fc (the direction the work faces, degrees) is needed")
        wk = sl.get("work")
        if wk is not None:
            if not isinstance(wk, dict):
                errs.append(f"{w}: work is an object {{title, artist, date, credit, pma_url, img}}")
            elif wk.get("img") not in (None, "") and not (isinstance(wk["img"], str) and ART_IMG_RE.fullmatch(wk["img"])):
                errs.append(f"{w}: work.img must be a hosted /bart/<name>.jpg|png|webp image on the site (never an outside URL), or empty")
        al = sl.get("al", ["any"])
        if not (isinstance(al, list) and al and all(a in WORKS for a in al)):
            errs.append(f"{w}: al is a non-empty list drawn from {WORKS}")

    # exterior
    ex = plan.get("ex")
    if ex is not None:
        if not isinstance(ex, dict):
            errs.append("ex: must be an object")
        else:
            for k in sorted(set(ex) - {"sh", "stp", "tr", "gz"}):
                errs.append(f"ex: unknown key {k!r}")
            if ex.get("gz") is not None and not _num(ex["gz"]):
                errs.append("ex: gz is the ground elevation in metres")
            seen = set()
            for i, sh in enumerate(ex.get("sh") or []):
                w = f"ex.sh[{i}]"
                k = ident(sh, w, seen)
                if k is None:
                    continue
                poly_ok(sh.get("p"), f"{w} {k!r}")
                if not _num(sh.get("h"), 0.5, 200):
                    errs.append(f"{w} {k!r}: h (eave height) is needed")
                rf = sh.get("rf")
                if rf is not None and not (isinstance(rf, dict) and rf.get("k") in ROOFS and (rf.get("h") is None or _num(rf["h"], 0, 100))):
                    errs.append(f"{w} {k!r}: rf is {{k: one of {ROOFS}, h?: rise}}")
                if sh.get("m") is not None and not _mat(sh["m"]):
                    errs.append(f"{w} {k!r}: material {sh['m']!r} is not in the vocabulary")
            seen = set()
            for i, st in enumerate(ex.get("stp") or []):
                w = f"ex.stp[{i}]"
                k = ident(st, w, seen)
                if k is None:
                    continue
                poly_ok(st.get("p"), f"{w} {k!r}")
                if not (_num(st.get("z0")) and _num(st.get("z1"))):
                    errs.append(f"{w} {k!r}: z0 and z1 (the foot and the top, metres) are needed")
            seen = set()
            for i, t in enumerate(ex.get("tr") or []):
                w = f"ex.tr[{i}]"
                k = ident(t, w, seen)
                if k is None:
                    continue
                poly_ok(t.get("p"), f"{w} {k!r}")
                if not _num(t.get("z")):
                    errs.append(f"{w} {k!r}: z (elevation) is needed")

    # the area legend
    ca = plan.get("ca")
    if ca is not None:
        if not isinstance(ca, list):
            errs.append("ca: a list of {id, n, c}")
        else:
            for i, a_ in enumerate(ca):
                if not (isinstance(a_, dict) and isinstance(a_.get("id"), str) and ID_RE.fullmatch(a_["id"])):
                    errs.append(f"ca[{i}]: needs an id token")
                elif a_.get("c") is not None and not (isinstance(a_["c"], str) and re.fullmatch(r"#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3}", a_["c"])):
                    errs.append(f"ca[{i}] {a_['id']!r}: c must be a #hex colour")

    # entrances
    seen = set()
    n_main = 0
    for i, e in enumerate(plan.get("en") or []):
        w = f"en[{i}]"
        k = ident(e, w, seen)
        if k is None:
            continue
        w = f"en[{i}] {k!r}"
        lvl(e, w)
        if not _pt(e.get("p")):
            errs.append(f"{w}: p is [x, y]")
        if not _num(e.get("fc"), -360, 360):
            errs.append(f"{w}: fc (facing out, degrees) is needed")
        if e.get("k", "main") not in ENTRANCE_KINDS:
            errs.append(f"{w}: k must be one of {ENTRANCE_KINDS}")
        n_main += e.get("k", "main") == "main"
        if e.get("wall") is not None and e["wall"] not in walls:
            errs.append(f"{w}: wall {e['wall']!r} is not in wl")
    if not plan.get("en"):
        warns.append("en: no entrance — Alto cannot say where the walk begins")
    elif not n_main:
        warns.append("en: no main entrance")

    tour = plan.get("tour")
    if tour is not None:
        if not isinstance(tour, list):
            errs.append("tour: a list of room ids")
        else:
            for t in tour:
                if t not in rooms:
                    errs.append(f"tour: {t!r} is not a room")
            if len(set(tour)) != len(tour):
                errs.append("tour: a room appears twice")

    for sid, used in srcs.items():
        if not used:
            warns.append(f"src {sid!r}: no element cites it")
    if len(json.dumps(plan, separators=(",", ":"))) > MAX_PLAN_BYTES:
        errs.append(f"plan: more than {MAX_PLAN_BYTES:,} bytes of JSON — split the building or drop detail that cannot be sourced")
    if errs:
        raise PlanError(errs)
    return warns


# ── normal form, hash, storage ──────────────────────────────────────────────

def _round(v):
    if isinstance(v, float):
        r = round(v, 2)
        return int(r) if r == int(r) else r
    if isinstance(v, list):
        return [_round(x) for x in v]
    if isinstance(v, dict):
        return {k: _round(x) for k, x in v.items()}
    return v


def _strip(v):
    if isinstance(v, dict):
        return {k: _strip(x) for k, x in v.items() if x not in (None, "", [], {})}
    if isinstance(v, list):
        return [_strip(x) for x in v]
    return v


def normalize(plan: dict) -> dict:
    """The plan with coordinates to the centimetre and empty fields dropped. Key order is fixed at serialisation (sort_keys), so the hash is stable."""
    return _round(_strip(copy.deepcopy(plan)))


def canonical(plan: dict) -> str:
    return json.dumps(normalize(plan), separators=(",", ":"), ensure_ascii=False, sort_keys=True)


def plan_hash(plan: dict) -> str:
    return hashlib.sha256(canonical(plan).encode("utf-8")).hexdigest()[:12]


def pack(plan: dict) -> str:
    return base64.b64encode(gzip.compress(canonical(plan).encode("utf-8"), 9, mtime=0)).decode("ascii")


def unpack(z: str) -> dict:
    return json.loads(gzip.decompress(base64.b64decode(z)).decode("utf-8"))


def file_name(h: str) -> str:
    return f"plan-{h}.json"


def hosted_json(plan: dict) -> tuple:
    """(file name, JSON text) of the hosted plan: /bldg/plan-<hash>.json."""
    return file_name(plan_hash(plan)), canonical(plan)


def summary(plan: dict) -> dict:
    """What a tool tells the user about a plan (never the geometry)."""
    rooms = plan.get("rm") or []
    conf = {0: 0, 1: 0, 2: 0, 3: 0}
    dc = plan.get("c", 1)
    for r in rooms:
        c = r.get("c", dc)
        conf[c if c in conf else dc] += 1
    return {"id": plan.get("id"), "name": plan.get("name"), "kind": plan.get("kind", "other"),
            "levels": [lv.get("n") for lv in plan.get("lv") or []], "rooms": len(rooms),
            "walls": len(plan.get("wl") or []), "stairs": len(plan.get("st") or []), "slots": len(plan.get("sl") or []),
            "columns": len(plan.get("cols") or []), "fixtures": len(plan.get("fx") or []),
            "entrances": len(plan.get("en") or []), "sources": len(plan.get("src") or []),
            "rooms_by_confidence": {str(k): v for k, v in conf.items() if v},
            "bytes_json": len(canonical(plan)), "bytes_gzip": len(gzip.compress(canonical(plan).encode("utf-8"), 9, mtime=0))}


# ── brief.building ──────────────────────────────────────────────────────────

BUILDING_KEYS = {"name", "plan_z", "plan_h", "mode", "assign", "made"}


def check_building(b, warnings: list) -> None:
    """Validate brief.building (called from validate_brief): the stored plan, its hash, the assignment mode and the caller's overrides."""
    from .brief import BriefError
    bd = getattr(b, "building", None)
    if not isinstance(bd, dict):
        raise BriefError("building: must be an object")
    view = getattr(b, "palace_view", "city") == "building"
    if bd and not (b.mode == "palace" and view):
        raise BriefError("building needs mode 'palace' and palace_view 'building': it is the Memory Blueprint's plan")
    if not view:
        return
    unknown = set(bd) - BUILDING_KEYS
    if unknown:
        raise BriefError(f"building: unknown keys {sorted(unknown)}")
    if not bd.get("plan_z"):
        warnings.append("building: no plan yet — run set_up_building(timeline_id, plan) before building; the page has no blueprint until then")
        return
    try:
        plan = unpack(bd["plan_z"])
    except Exception as e:                                  # noqa: BLE001
        raise BriefError(f"building.plan_z: cannot be read ({e}) — run set_up_building again")
    try:
        warnings += [f"building plan: {w}" for w in validate_plan(plan)]
    except PlanError as e:
        raise BriefError("building plan: " + str(e))
    if bd.get("plan_h") != plan_hash(plan):
        raise BriefError("building.plan_h does not match the stored plan — run set_up_building again")
    if bd.get("mode", "room") not in ASSIGN_MODES:
        raise BriefError(f"building.mode {bd.get('mode')!r}: must be one of {ASSIGN_MODES}")
    elements = {r["id"] for r in plan.get("rm") or []} | {s["id"] for s in plan.get("sl") or []} | {f["id"] for f in plan.get("fx") or []}
    for nid, el in (bd.get("assign") or {}).items():
        if not (isinstance(nid, str) and isinstance(el, str)):
            raise BriefError("building.assign: {node id: room / art slot / fixture id}")
        if el not in elements:
            raise BriefError(f"building.assign: {nid!r} → {el!r} is not a room, art slot or fixture of the plan")


def plan_of(b):
    """The unpacked plan of a brief (or None)."""
    z = (getattr(b, "building", None) or {}).get("plan_z")
    return unpack(z) if z else None


# ── node → room / anchor ────────────────────────────────────────────────────

def _nat(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(s or ""))]


def room_order(plan: dict) -> list:
    """Room ids in the order Alto walks them: plan.tour if given, else the entrance level first, then the other levels from the bottom up,
    each by room number (natural order) then listing order. Circulation rooms are left out."""
    rooms = {r["id"]: r for r in plan.get("rm") or []}
    if plan.get("tour"):
        return [i for i in plan["tour"] if rooms[i].get("ty", "other") not in CIRCULATION]
    elev = {lv["id"]: lv["e"] for lv in plan.get("lv") or []}
    ent = [e.get("l") for e in plan.get("en") or [] if e.get("k", "main") == "main"] or [e.get("l") for e in plan.get("en") or []]
    first = ent[0] if ent else None
    lv_order = ([first] if first in elev else []) + [l for l in sorted(elev, key=elev.get) if l != first]
    pos = {r["id"]: i for i, r in enumerate(plan.get("rm") or [])}
    out = []
    for l in lv_order:
        ids = [r["id"] for r in plan.get("rm") or [] if r.get("l") == l and r.get("ty", "other") not in CIRCULATION]
        out += sorted(ids, key=lambda i: (0 if rooms[i].get("no") else 1, _nat(rooms[i].get("no")), pos[i]))
    return out


def anchors_in(plan: dict, room_id: str) -> list:
    """Art slots then anchor fixtures standing in a room, in listing order."""
    room = next((r for r in plan.get("rm") or [] if r["id"] == room_id), None)
    if room is None:
        return []
    out = [s["id"] for s in plan.get("sl") or [] if s.get("rm") == room_id]
    for f in plan.get("fx") or []:
        if f.get("k") in ANCHOR_FIXTURES and f.get("l") == room.get("l") and room.get("p") and inside(room["p"], f["p"]):
            out.append(f["id"])
    return out


def element_room(plan: dict, el: str):
    """The room an element id (room, slot or fixture) belongs to, else None."""
    for r in plan.get("rm") or []:
        if r["id"] == el:
            return r["id"]
    for s in plan.get("sl") or []:
        if s["id"] == el:
            return s.get("rm")
    for f in plan.get("fx") or []:
        if f["id"] == el:
            for r in plan.get("rm") or []:
                if r.get("l") == f.get("l") and r.get("p") and inside(r["p"], f["p"]):
                    return r["id"]
    return None


def assign_nodes(plan: dict, nodes, mode: str = "room", overrides: dict | None = None) -> dict:
    """Hand the outline's nodes to the building. `nodes`: objects with id and parent, in outline order. Returns
    {"assign": {node id: {"r": room id, "a": anchor id or None}}, "unplaced": [node ids], "notes": [str]}.

    mode "room": each ROOT node takes the next room on the walk; its descendants stand in that room, each on the next free art slot / anchor
    fixture there (or just in the room when none is left). mode "anchor": every node, whatever its depth, takes the next art slot / anchor fixture
    on the walk (rooms without any are skipped). `overrides` {node id: room / slot / fixture id} win over the proposal, whatever the mode;
    a room taken by an override is not handed out again."""
    if mode not in ASSIGN_MODES:
        raise PlanError([f"mode {mode!r}: must be one of {ASSIGN_MODES}"])
    nodes = list(nodes)
    ids = {n.id for n in nodes}
    parent = {n.id: n.parent for n in nodes if n.parent}
    notes, out = [], {}
    over = {k: v for k, v in (overrides or {}).items() if k in ids}
    used_anchor, used_room = set(), set()

    def root_of(i):
        seen = set()
        while parent.get(i) in ids and i not in seen:
            seen.add(i); i = parent[i]
        return i

    for nid, el in over.items():
        r = element_room(plan, el)
        if r is None:
            raise PlanError([f"assignment {nid!r} → {el!r}: not a room, art slot or fixture of the plan"])
        is_room = any(x["id"] == el for x in plan.get("rm") or [])
        out[nid] = {"r": r, "a": None if is_room else el}
        (used_room.add(r) if is_room else used_anchor.add(el))
    order = room_order(plan)
    if mode == "room":
        free = [r for r in order if r not in used_room]
        for n in nodes:
            if n.id in out or n.parent in ids:
                continue
            if not free:
                continue
            r = free.pop(0)
            out[n.id] = {"r": r, "a": None}
        for n in nodes:
            if n.id in out or n.parent not in ids:
                continue
            host = out.get(root_of(n.id)) or out.get(n.parent)
            if host is None:
                continue
            room = host["r"]
            spare = [a for a in anchors_in(plan, room) if a not in used_anchor]
            a = spare[0] if spare else None
            if a:
                used_anchor.add(a)
            out[n.id] = {"r": room, "a": a}
    else:
        pool, seen_a = [], set(used_anchor)
        for r in order:                                  # an anchor standing in two overlapping rooms is handed out once
            for a in anchors_in(plan, r):
                if a not in seen_a:
                    seen_a.add(a); pool.append((r, a))
        for n in nodes:
            if n.id in out:
                continue
            if not pool:
                break
            r, a = pool.pop(0)
            out[n.id] = {"r": r, "a": a}
    unplaced = [n.id for n in nodes if n.id not in out]
    if unplaced:
        what = "rooms to walk" if mode == "room" else "art slots / anchors"
        notes.append(f"{len(unplaced)} of {len(nodes)} nodes found no place: the plan has too few {what} "
                     "(add rooms or slots to the plan, move to mode 'anchor'/'room', or assign them by hand)")
    return {"assign": out, "unplaced": unplaced, "notes": notes}


# ── a tiny fake building for tests and demos ────────────────────────────────

def fixture() -> dict:
    """"Alto Test Pavilion": an invented two-level hall (not any real building, no real data): 20 x 12 m, an entrance hall and a gallery on
    the ground level, a stair, an upper gallery under a skylight, columns, a plinth, art slots and a terrace with steps. Passes validate_plan."""
    def rect(x0, y0, x1, y1):
        return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
    return {
        "v": 1, "id": "test-pavilion", "name": "Alto Test Pavilion", "kind": "museum", "c": 2,
        "geo": {"lat": 0.0, "lon": 0.0, "north": 0},
        "src": [{"id": "inv", "t": "Invented for tests (not a real building)", "k": "estimate", "lic": "CC0"}],
        "lv": [{"id": "g", "n": "Ground floor", "lb": "G", "e": 0, "h": 5.0},
               {"id": "u", "n": "Upper floor", "lb": "1", "e": 5.5, "h": 4.5}],
        "wl": [
            {"id": "g-out", "l": "g", "p": rect(0, 0, 20, 12), "loop": True, "t": 0.6, "m": "limestone", "k": "ext", "s": ["inv"],
             "o": [{"k": "door", "a": 10, "w": 2.4, "h": 3.2, "m": "bronze", "d": "double"},
                   {"k": "window", "a": 4, "w": 1.6, "h": 2.2, "z": 1.0}, {"k": "window", "a": 16, "w": 1.6, "h": 2.2, "z": 1.0}]},
            {"id": "g-mid", "l": "g", "p": [[8, 0], [8, 12]], "t": 0.3, "m": "plaster", "k": "int",
             "o": [{"k": "arch", "a": 6, "w": 2.0, "h": 3.4}]},
            {"id": "u-out", "l": "u", "p": rect(0, 0, 20, 12), "loop": True, "t": 0.5, "m": "limestone", "k": "ext",
             "o": [{"k": "window", "a": 10, "w": 2.0, "h": 2.0, "z": 1.2}]},
            {"id": "u-rail", "l": "u", "p": [[2, 6], [6, 6], [6, 10]], "t": 0.1, "m": "metal", "k": "rail", "h": 1.0},
        ],
        "rm": [
            {"id": "hall", "l": "g", "n": "Entrance Hall", "no": "100", "ty": "lobby", "p": rect(0, 0, 8, 12), "ch": 5.0,
             "fm": "terrazzo", "wm": "plaster", "cm": "plaster", "li": {"k": "day"}},
            {"id": "g101", "l": "g", "n": "Gallery 101", "no": "101", "ty": "gallery", "p": rect(8, 0, 20, 12), "ch": 4.6,
             "fm": "parquet", "wm": "paint", "cm": "plaster", "li": {"k": "art", "lx": 200}},
            {"id": "u201", "l": "u", "n": "Skylit Gallery", "no": "201", "ty": "gallery", "p": rect(0, 0, 14, 12), "ch": 4.2,
             "fm": "wood", "wm": "paint", "cm": "glass", "li": {"k": "sky", "lx": 400}, "c": 1},
            {"id": "u202", "l": "u", "n": "Print Room", "no": "202", "ty": "gallery", "p": rect(14, 0, 20, 12), "ch": 3.4,
             "fm": "carpet", "wm": "paint", "cm": "plaster", "li": {"k": "dim", "lx": 50}, "c": 0},
        ],
        "st": [{"id": "stair-a", "k": "stair", "from": "g", "to": "u", "fp": rect(1, 1, 4, 5), "w": 2.6, "n": 30, "up": 90,
                "fl": [{"a": [2.5, 1, 0], "b": [2.5, 5, 5.5], "w": 2.6}]}],
        "cols": [{"id": "c1", "l": "g", "p": [4, 3], "r": 0.35, "h": 5.0, "o": "doric", "m": "marble"},
                 {"id": "c2", "l": "g", "p": [4, 9], "r": 0.35, "h": 5.0, "o": "doric", "m": "marble"}],
        "fx": [{"id": "plinth-a", "l": "g", "k": "plinth", "p": [14, 6], "rot": 0, "sz": [0.8, 0.8, 1.1], "m": "marble", "n": "Central plinth"},
               {"id": "bench-a", "l": "u", "k": "bench", "p": [7, 6], "rot": 90, "sz": [2.0, 0.5, 0.45], "m": "wood"}],
        "sl": [{"id": "sl-101a", "rm": "g101", "w": "g-out", "p": [14, 0.3], "z": 1.6, "sz": [1.4, 1.0], "fc": 90, "al": ["painting", "drawing"]},
               {"id": "sl-101b", "rm": "g101", "w": "g-out", "p": [19.7, 6], "z": 1.6, "sz": [2.0, 1.4], "fc": 180, "al": ["painting", "tapestry"]},
               {"id": "sl-201a", "rm": "u201", "w": "u-out", "p": [0.3, 6], "z": 1.7, "sz": [1.2, 1.6], "fc": 0, "al": ["painting"]},
               {"id": "sl-202a", "rm": "u202", "w": "u-out", "p": [19.7, 6], "z": 1.5, "sz": [0.6, 0.8], "fc": 180, "al": ["print", "drawing"]}],
        "ex": {"gz": -0.4,
               "sh": [{"id": "body", "p": rect(0, 0, 20, 12), "h": 9.8, "rf": {"k": "hip", "h": 2.0}, "m": "limestone"}],
               "stp": [{"id": "front-steps", "p": rect(8, -3, 12, 0), "z0": -0.4, "z1": 0.0, "n": 3, "up": 90}],
               "tr": [{"id": "terrace", "p": rect(6, -6, 14, -3), "z": -0.4, "m": "granite", "n": "Front terrace"}]},
        "en": [{"id": "main", "n": "Main entrance", "l": "g", "p": [10, 0], "fc": -90, "w": 2.4, "k": "main", "wall": "g-out"}],
    }
