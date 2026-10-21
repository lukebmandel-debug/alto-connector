"""System (an outline with layout "solar") and its two looks of ONE plan
(Luke, round 7): System (orbit rings, spokes, circles in Alto's own glass
styling) and the Star chart (the same rings and geometry plus the space skin,
solar_stars.py, and flights between bodies, solar_fly.py; the default). Both
looks orbit (the page's Orbit switch, on by default, stops them). The page
carries the one plan (page_plans); brief.hub_look ('stars' | 'hub') says which
look a viewer sees first.

Every ROOT node (Node.parent "") is a SUN — usually one per unit; a unit with
several roots holds several systems, kept together. A sun's children are PLANETS,
one to a ring, the first on the innermost ring and the rest outward in outline
order; their children are MOONS, likewise each on its OWN ring round their
planet (the first innermost, outline order outward: no two moons share an
orbit); one level deeper are SATELLITES, each on its own ring round their moon. A fifth level is a
validation error (brief._check_solar_depth), never flattened.

solar_plan(brief, nodes) is pure and deterministic: the same outline always
gives the same plan, and nothing here needs a browser — every circle has a
diameter fixed by the outline alone (sizes below), so no card is measured.

Sizes (Luke, rounds 2 and 7): from real ratios, compressed (SOLAR["D"]). The
sun is the largest body whatever it holds. A planet's diameter goes up a tier
with every two moons it has, a moon's with every two satellites
(SOLAR["TIERS"], clamped at the last tier) and never past MOON_MAX of its
planet's; a satellite is the smallest, but for the space station of its
system (stations). A node carrying an extreme-importance flag (BUMP_FLAGS: a
brief flag whose id or name is exactly "pivotal", "critical" or "extreme
importance") is one tier larger, past the clamp if need be. The tiers keep a
strict order — sun > every planet > every moon > every satellite — and every
gap and ring radius below is computed from the actual diameters, so the
no-overlap guarantees hold for any mix.

Geometry. Each planet carries its moons (and their satellites) inside a disc of
radius `e` round its own centre. The rings are spaced so those discs sweep
DISJOINT annuli [r - e, r + e] round the sun; in the same way each moon's
family (the moon and its satellites, reach `ext`) sweeps its own annulus round
its planet, MOON_GAP clear of the planet and of the next moon's, and each
satellite its own annulus round its moon, SAT_GAP apart. So every body can
turn at any speed (inner ones faster), and no two circles ever touch. At
t = 0 moons sit evenly round their planet with the direction of the sun
halfway between two of them (likewise satellites round their moon).

Systems sit side by side in unit order, suns on one line, centred in the
1700px world; a row that would come nearer the edge than SOLAR["MARGIN"] wraps,
and a single system wider than the world widens it (plan["world"]["w"]).

The plan (the contract with solar_draw.py, which reads window._ALTO_SOLAR):

  {"style": "orbit", "spin": -1,
   "world": {"w", "h"},
   "sizes": {"sun", "planet", "planet_big", "moon", "sat", "station", "tiers", "bump"},
            # per-ROLE reference only: sun / planet / moon / sat are the base
            # (childless, unflagged) diameters, planet_big the largest a planet
            # can be, tiers the per-role ladders, bump the flag ids that bump.
            # The diameter to draw is always the node's own `d`.
   "systems": [{"unit": act index, "label", "sun", "cx", "cy", "r_sun", "R",
                "bbox": [x0, y0, x1, y1],
                "planets": [{"id", "ring", "r", "a0", "d", "period", "e",
                             "moon_r", "moons": [{"id", "r", "a0", "d", "period", "ext",
                                                  "sat_r", "sats": [{"id", "r", "a0", "d", "period"}]}]}]}],
   "units": [{"unit", "label", "suns": [sun ids], "bbox"}],   # a unit's systems together
   "nodes": {id: {"x", "y", "d", "role", "unit", "parent",
                  "look"?: "blackhole"|"comet"|"asteroid",        # by the user's flags (LOOK_FLAGS)
                  "orbit"?: {"e", "rot", "k"},                    # a comet (both looks orbit; the Star chart draws it as one)
                  "tumble"?: rad/s,                               # an asteroid (drawn tumbling in the Star chart look)
                  "station"?: 1}},                                # the satellite drawn as a space station (stations)
   "sun_links": [[sun id, sun id]], "warnings": [...],
   "looks": {look: [node ids]}, "look_flags": {brief flag id: look},
   "belts": [{"sun", "cx", "cy", "r", "w", "n", "seed"}],       # drawn in the Star chart look only
   "core"?: {"x", "y", "r", "p"},                                # 2+ systems: the galaxy's centre, its turn period
   "drifters": []}                                               # (none since the spiral galaxy: kept for old skins)

Comets. A comet keeps its ring, period and a0 but moves on
an ellipse centred on what it orbits, semi-axes A = r(1 + c), B = r(1 − c)
with c = (1 − q)/(1 + q), q = √(1 − e²), its major axis at angle `rot`. At
time t its mean angle is M = a0 + spin·2πt/period (as for every body); with
m = M − rot, ψ = m when k = 0, and when k = 1 (a planet) ψ solves
ψ − e·sin ψ = m (Newton from ψ = m, 12 steps); its offset from what it
orbits is R(rot)·(A cos ψ, B sin ψ). It is never farther than c·r from where a
circular body at M would be (k = 0) and always between r − c·r and r + c·r
from what it orbits, and its own annulus counts that in (its ring is pushed
out to (edge + gap + reach) / (1 − c)), so the no-overlap guarantees still
hold. e and rot are fixed per node from its id (comet_shape). An asteroid
tumbles at `tumble` rad/s; a black hole is only a look.

Belts and the core (decoration, never a node). A system of BELT_MIN
planets or more gets an asteroid belt of width w at radius r round its sun,
in a gap of its own between its inner and outer planets' bands (n rocks,
scattered from `seed`). Two systems or more make a spiral galaxy (_galaxy):
the suns on its arms in outline order round a supermassive black hole, the
core, at its centre; the Star chart look turns the whole galaxy rigidly about
the core (period core.p) — rigid, so no two systems ever meet. One system is
centred, with no core.

Angles are radians in page coordinates (x right, y DOWN), measured from +x: a
body at angle a sits at (cx + r cos a, cy + r sin a) round what it orbits. A
planet's `r`/`a0` are round its sun, a moon's round its planet, a satellite's
round its moon. A body's angle at time t (seconds) is
a0 + spin * 2π t / period; spin -1 turns everything counter-clockwise on
screen; inner rings turn faster (P_PLANET, P_MOON, P_SAT run inner → outer).
`R` is the system's bounding radius round its sun (every body stays inside
it at all times, so a system may be turned as a whole about its sun without
touching its neighbour), `e` a planet's own reach (planet + moons +
satellites), a moon's `ext` its family's reach; `moon_r` / `sat_r` the
innermost moon's / satellite's ring (0 when there is none). nodes[*].x/y are the
t = 0 centres; the builder writes them into the page as ordinary positions
(solar_tree_plan → run_plan / TREE_GLUE "float" ops anchored at the centre).
"""
from __future__ import annotations

import math

from .brief import BriefError, SOLAR_ROLES

SOLAR = {
    # base diameters per role (no children, no flag)
    # (round 7, Luke: "based on real comparative sizes of celestial bodies"):
    # Earth 1, the Moon 0.27, Ganymede / Titan ~0.4, Jupiter 11, the Sun 109
    # Earths across, compressed log-like so the sun is still the largest and
    # text and hit targets work: a moonless (rocky) planet ~64, mid planets
    # 84-96, the giants (most moons) 110-134; moons 24-36 and never more than
    # MOON_MAX of their planet's diameter; satellites 14-18, a space station
    # (STATION: the satellite with the most to read in its system) 21.
    "D": {"sun": 200, "planet": 64, "moon": 24, "sat": 14},
    # the size ladders: a planet's tier is ceil(moons / 2) (clamped to the
    # ladder), a moon's ceil(satellites / 2); the last entry of each ladder is
    # reachable only by a bump (BUMP_FLAGS) from the tier below it
    "TIERS": {"planet": (64, 84, 96, 110, 122, 134),
              "moon": (24, 27, 30, 33, 36),
              "sat": (14, 18)},
    "MOON_MAX": 0.4, "STATION": 21,
    # a comet moon / satellite strays at most this far from its circle (_rings)
    "COMET_PX": 24, "COMET_PX_PLANET": 80,
    # clear space: between one planet's reach and the next ring's (and the
    # sun's), between a planet and its moons, a moon and its satellites
    "RING_GAP": 26, "MOON_GAP": 10, "SAT_GAP": 6,
    # between systems, from the world's side edges, above the first row (the
    # engine's band-label reserve, layout.LABEL_RESERVE) and under the last
    "SYS_GAP": 90, "MARGIN": 115, "TOP": 184, "BOTTOM": 160, "WORLD_W": 1700,
    # orbit periods in seconds, inner ring → outer (inner faster): planets
    # round their sun, moons round their planet, satellites round their moon
    "P_PLANET": (112.5, 187.5), "P_MOON": (37.5, 62.5), "P_SAT": (17.5, 30.0),   # (all x1.25 = 20% slower, 1.9.117)
    # the Star chart look's extras: a comet's eccentricity range; an asteroid's
    # tumble (rad/s, either way); an asteroid belt's width (a system of
    # BELT_MIN planets or more gets one, between its inner and outer planets);
    # the galactic core's radius and clear space (a chart of 2+ systems); how
    # far a drifting comet's path keeps from every system
    "ECC": (0.5, 0.7), "TUMBLE": (0.12, 0.48), "BELT_W": 70, "BELT_MIN": 4,
    "CORE_R": 60, "CORE_GAP": 40,
    # the spiral galaxy of 2+ systems (_galaxy): its arms, the search step along an
    # arm (px of arc), the whole galaxy's turn about the core (s, Orbit on)
    "ARMS": 2, "GAL_STEP": 8, "P_GALAXY": 1125.0,
}
# What a node is drawn as, by the user's own flags (brief.flags): a flag whose
# id or name, lower-cased with spaces and underscores as hyphens, is in a row
# makes its nodes that kind of body. First match wins, in this order. The
# node keeps its role (planet / moon / satellite by depth), its size and its
# children; only the body changes. The plan carries nodes[id].look; the Hub &
# spoke look ignores it.
#   blackhole  a dark, light-bending body: what no longer holds
#   comet      a visitor on an eccentric orbit: what is unsettled or apart
#   asteroid   a small irregular tumbling rock: what is minor or untested
LOOK_FLAGS = (
    ("blackhole", ("overruled", "abrogated", "superseded", "collapsed", "dead-letter",
                   "blackhole", "black-hole")),
    ("comet", ("revisit", "exception", "dissent", "minority", "open-question")),
    ("asteroid", ("not-tested", "background", "minor", "aside")),
)
# A brief flag whose id or name, lower-cased with spaces and underscores as
# hyphens, is one of these marks extreme importance: the nodes carrying it are
# drawn one tier up. An explicit list, not a guess at what a name means.
BUMP_FLAGS = ("pivotal", "critical", "extreme-importance")
GOLDEN = math.pi * (3 - math.sqrt(5))          # 137.5°: neighbouring planets never line up
SPIN = -1


def _r2(v: float) -> float:
    return round(v, 2)


def _flag_names(fl) -> set:
    return {str(fl.get(k) or "").strip().lower().replace(" ", "-").replace("_", "-")
            for k in ("id", "name")}


def _bump_flags(brief) -> set:
    out = set()
    for fl in getattr(brief, "flags", None) or []:
        if isinstance(fl, dict) and _flag_names(fl) & set(BUMP_FLAGS):
            out.add(fl.get("id"))
    return out


def look_flags(brief) -> dict:
    """{brief flag id: look} for the flags LOOK_FLAGS names."""
    out = {}
    for fl in getattr(brief, "flags", None) or []:
        if not isinstance(fl, dict):
            continue
        names = _flag_names(fl)
        for look, words in LOOK_FLAGS:
            if names & set(words):
                out[fl.get("id")] = look
                break
    return out


def node_looks(brief, nodes) -> dict:
    """{node id: "blackhole" | "comet" | "asteroid"} for the nodes a look flag marks."""
    by_flag = look_flags(brief)
    rank = {look: k for k, (look, _) in enumerate(LOOK_FLAGS)}
    out = {}
    for n in nodes:
        got = [by_flag[f] for f in (n.flags or []) if f in by_flag]
        if got:
            out[n.id] = min(got, key=lambda lk: rank[lk])
    return out


def hash01(text: str) -> float:
    """A number in [0, 1) from text: 32-bit FNV-1a over its characters (ids
    are ASCII slugs; the page's twin computes the same with Math.imul)."""
    h = 2166136261
    for ch in text:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h / 4294967296.0


def comet_shape(node_id: str) -> tuple[float, float]:
    """(eccentricity, rot) of a comet's orbit: fixed per node from its id."""
    lo, hi = SOLAR["ECC"]
    return (round(lo + (hi - lo) * hash01("ecc:" + node_id), 4),
            round(2 * math.pi * hash01("rot:" + node_id), 4))


def ecc_slack(ecc: float) -> float:
    """c = (1 - q) / (1 + q), q = √(1 − ecc²): the ellipse with semi-axes
    r(1 + c) and r(1 − c) round a circle of radius r has that eccentricity."""
    q = math.sqrt(max(0.0, 1 - ecc * ecc))
    return (1 - q) / (1 + q)


def slack_ecc(c: float) -> float:
    """The eccentricity whose ellipse round a circle of radius r has semi-axes r(1 ± c)."""
    q = (1 - c) / (1 + c)
    return math.sqrt(max(0.0, 1 - q * q))


def tumble(node_id: str) -> float:
    lo, hi = SOLAR["TUMBLE"]
    v = lo + (hi - lo) * hash01("tumble:" + node_id)
    return round(v if hash01("spin:" + node_id) < 0.5 else -v, 4)


def kepler(m: float, ecc: float) -> float:
    """ψ with ψ − ecc·sin ψ = m (Newton, 12 steps from ψ = m)."""
    psi = m
    for _ in range(12):
        psi -= (psi - ecc * math.sin(psi) - m) / (1 - ecc * math.cos(psi))
    return psi


def orbit_offset(r: float, ang: float, orb: dict) -> tuple[float, float]:
    """Where a body on a comet orbit sits round what it orbits when its mean
    angle is `ang` (module docstring, Comets): R(rot)·(A cos ψ, B sin ψ)."""
    c = ecc_slack(orb["e"])
    A, B = r * (1 + c), r * (1 - c)
    m = ang - orb["rot"]
    psi = kepler(m, orb["e"]) if orb.get("k") else m
    x, y = A * math.cos(psi), B * math.sin(psi)
    cr, sr = math.cos(orb["rot"]), math.sin(orb["rot"])
    return x * cr - y * sr, x * sr + y * cr


def body_d(role: str, children: int, bumped: bool = False, parent_d: float = 0,
           station: bool = False) -> int:
    """A body's diameter (module docstring, Sizes): the sun's is fixed; a
    planet / moon climbs a tier per two children, clamped below the ladder's
    bump-only top; a bump adds one tier. A moon is never more than MOON_MAX
    of its planet (parent_d); a station satellite is STATION."""
    if role == "sun":
        return SOLAR["D"]["sun"]
    if role == "sat" and station:
        return SOLAR["STATION"]
    ladder = SOLAR["TIERS"][role]
    tier = min(-(-children // 2), len(ladder) - 2) if role != "sat" else 0
    d = ladder[min(tier + (1 if bumped else 0), len(ladder) - 1)]
    if role == "moon" and parent_d:
        d = min(d, int(SOLAR["MOON_MAX"] * parent_d))
    return d


def _content(n) -> int:
    """How much a node has to read: its description and its sections' text."""
    return len(n.desc or "") + sum(len(getattr(q, "t", "") or "") for q in (n.sections or []))


def stations(units, nodes) -> set:
    """The space stations: in each system the satellite with the most to read
    (_content; the first in outline order on a tie), if it has satellites."""
    by = {n.id: n for n in nodes}
    out = set()
    for _a, _sun, planets in units:
        sats = [q for _p, moons in planets for _m, qs in moons for q in qs]
        if sats:
            out.add(max(sats, key=lambda q: (_content(by[q]) if q in by else 0, -sats.index(q))))
    return out


def _even(n: int, out: float) -> list:
    """n angles evenly round a circle with `out` (the direction away from what
    the centre orbits) at or beside the first, and the opposite direction —
    the spoke's — exactly halfway between two of them."""
    if not n:
        return []
    off = math.pi / n if n % 2 == 0 else 0.0
    return [out + off + 2 * math.pi * j / n for j in range(n)]


def _tree(brief, nodes):
    """Every system, unit by unit and each unit's roots in order: (unit, sun
    id, [(planet, [(moon, [sat])])]). Raises BriefError on a fifth level. A
    node whose parent is not a node (an interview still filling in) orbits its
    unit's first sun, so a preview never drops a card."""
    ids = {n.id for n in nodes}
    kids: dict = {}
    for n in nodes:
        if n.parent and n.parent in ids:
            kids.setdefault(n.parent, []).append(n.id)
    units = []
    for a in range(len(brief.acts)):
        mine = [n for n in nodes if n.act == a]
        if not mine:
            continue
        tops = [n.id for n in mine if not n.parent] or [mine[0].id]
        loose = [n.id for n in mine if n.id not in tops and (not n.parent or n.parent not in ids)]
        for k, sun in enumerate(tops):
            units.append((a, sun, _family(sun, kids.get(sun, []) + (loose if k == 0 else []), kids, brief)))
    return units


def _family(sun, planet_ids, kids, brief):
    """[(planet, [(moon, [sat])])] under one sun."""
    planets = []
    for p in planet_ids:
        moons = []
        for m in kids.get(p, []):
            sats = kids.get(m, [])
            for s in sats:
                if kids.get(s):
                    way_out = "use layout 'tree'"
                    raise BriefError(
                        f"node {kids[s][0]} is deeper than a satellite ({sun} → {p} → {m} → "
                        f"{s} → {kids[s][0]}): a solar layout has four levels — "
                        f"restructure it or {way_out}")
            moons.append((m, list(sats)))
        planets.append((p, moons))
    return planets


def _rings(items, gap, inner, slack, orb):
    """Concentric rings, one per body, the first innermost (outline order
    outward): items [(id, reach)] round a centre body of radius `inner`. Each
    body's annulus [r(1 − c) − reach, r(1 + c) + reach] (c: its comet slack,
    else 0) starts `gap` past the one inside it. A comet moon / satellite
    strays at most COMET_PX from its circle (c·r; its eccentricity flattened
    to fit), so the rings of a family of comets grow by that much each, not
    by a factor. Its orbit {e, rot, k: 0} goes into `orb`. Returns ([ring
    radius per item], outer edge)."""
    edge, out = inner, []
    for i, x in items:
        c = slack.get(i, 0.0)
        r = edge + gap + x
        if c:
            a = min(c * r / (1 - c), SOLAR["COMET_PX"])
            r += a
            e = round(slack_ecc(a / r), 4)
            c = ecc_slack(e)
            r = (edge + gap + x) / (1 - c) + 0.05                  # (a hair over: r is written to 0.01)
            orb[i] = {"e": e, "rot": comet_shape(i)[1], "k": 0}
        out.append(r)
        edge = r + c * r + x
    return out, edge


def _planet_body(pid, moons, size, S, slack=None):
    """A planet's own geometry round its centre: its and its family's
    diameters (size(id, role, children)), each moon's ring and each
    satellite's (_rings), its reach. Independent of where the planet is.
    slack: {id: c} for the comets (comet_shape / ecc_slack); body["orb"]
    then holds each comet moon's / satellite's orbit {e, rot, k: 0}."""
    slack = slack or {}
    d_p = size(pid, "planet", len(moons), 0)
    R_p = d_p / 2
    ms, orb = [], {}
    for mid, sats in moons:
        d_m = size(mid, "moon", len(sats), d_p)
        R_m = d_m / 2
        sd = {q: size(q, "sat", 0, d_m) for q in sats}
        srs, ext = _rings([(q, sd[q] / 2) for q in sats], S["SAT_GAP"], R_m, slack, orb)
        ms.append({"id": mid, "d": d_m, "sats": sats, "sd": sd, "srs": dict(zip(sats, srs)),
                   "sat_r": srs[0] if srs else 0.0, "ext": ext if sats else R_m})
    mrs, e = _rings([(m["id"], m["ext"]) for m in ms], S["MOON_GAP"], R_p, slack, orb)
    for m, r in zip(ms, mrs):
        m["r"] = r
    return {"id": pid, "d": d_p, "moons": ms, "moon_r": mrs[0] if mrs else 0.0, "e": max(e, R_p), "orb": orb}


def _at(r, ang, orb):
    """A body's offset from what it orbits at mean angle `ang`: on its circle,
    or on its comet ellipse (orbit_offset)."""
    if orb:
        return orbit_offset(r, ang, orb)
    return r * math.cos(ang), r * math.sin(ang)


def _local_circles(body, theta, r, orbs=None):
    """Every circle of a planet's family as (id, x, y, radius, parent id) round
    the SUN, the planet at angle theta on ring r, and its spokes as segments
    (child id, parent id, x1, y1, x2, y2). orbs: {id: orbit} — comets sit on
    their ellipses (the Star chart look at t = 0)."""
    orbs = orbs or {}
    px, py = _at(r, theta, orbs.get(body["id"]))
    circles = [(body["id"], px, py, body["d"] / 2, None)]
    segs = []
    for m, ma in zip(body["moons"], _even(len(body["moons"]), theta)):
        ox, oy = _at(m["r"], ma, orbs.get(m["id"]))
        mx, my = px + ox, py + oy
        circles.append((m["id"], mx, my, m["d"] / 2, body["id"]))
        segs.append((m["id"], body["id"], mx, my, px, py))
        for s, sa in zip(m["sats"], _even(len(m["sats"]), ma)):
            ox, oy = _at(m["srs"][s], sa, orbs.get(s))
            sx, sy = mx + ox, my + oy
            circles.append((s, sx, sy, m["sd"][s] / 2, m["id"]))
            segs.append((s, m["id"], sx, sy, mx, my))
    return circles, segs


def _seg_dist(cx, cy, x1, y1, x2, y2) -> float:
    dx, dy = x2 - x1, y2 - y1
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((cx - x1) * dx + (cy - y1) * dy) / L))
    return math.hypot(cx - (x1 + t * dx), cy - (y1 + t * dy))


def _system(unit, sun, planets, bumped, brief_nodes, looks=None, station=()):
    """One system round its sun at (0, 0): its planets with their rings and
    angles, every circle's local centre, and its bounding box. looks: {node
    id: look} (node_looks) — a comet gets an ellipse and room for it, and a
    system of BELT_MIN planets or more an asteroid belt."""
    S, D = SOLAR, SOLAR["D"]
    R_sun = D["sun"] / 2
    flags = {n.id: set(n.flags or []) for n in brief_nodes}
    looks = looks or {}
    slack = {i: ecc_slack(comet_shape(i)[0]) for i, lk in looks.items() if lk == "comet"}

    def size(i, role, children, parent_d):
        return body_d(role, children, bool(flags.get(i, set()) & bumped), parent_d, i in station)
    bodies = [_planet_body(p, moons, size, S, slack) for p, moons in planets]
    P = len(bodies)
    rings, angles, warns, belt = [], [], [], None
    orbs = {}
    for b in bodies:
        orbs.update(b["orb"])
    # Each planet's family sweeps the annulus [r − s − e, r + s + e] (s:
    # its comet slack, else 0); the annuli are disjoint, RING_GAP apart.
    edge = R_sun
    split = P // 2 if P >= S["BELT_MIN"] else -1
    for k, b in enumerate(bodies):
        if k == split:
            belt = {"r": edge + S["RING_GAP"] + S["BELT_W"] / 2, "w": S["BELT_W"]}
            edge += S["RING_GAP"] + S["BELT_W"]
        c = slack.get(b["id"], 0.0)
        r = edge + S["RING_GAP"] + b["e"]
        if c:
            # a comet planet strays at most COMET_PX_PLANET from its circle (its eccentricity
            # flattened to fit), so a system of comets grows by that much a ring, not by a factor
            a = min(c * r / (1 - c), S["COMET_PX_PLANET"])
            e = round(slack_ecc(a / (r + a)), 4)
            c = ecc_slack(e)
            r = r / (1 - c) + 0.05                                    # (a hair over: r is written to 0.01)
            orbs[b["id"]] = {"e": e, "rot": comet_shape(b["id"])[1], "k": 1}
        rings.append(r)
        angles.append(-math.pi / 2 + k * GOLDEN)
        b["band"] = (r - c * r - b["e"], r + c * r + b["e"])
        edge = b["band"][1]

    def period(lo_hi, k, n):
        lo, hi = lo_hi
        return _r2(lo + (hi - lo) * (k / (n - 1) if n > 1 else 0.5))

    out_planets, local = [], {sun: (0.0, 0.0, D["sun"], "sun", "")}
    for k, (b, r, th) in enumerate(zip(bodies, rings, angles)):
        cs, _ = _local_circles(b, th, r, orbs)
        for (i, x, y, rad, par) in cs:
            role = "planet" if par is None else ("moon" if par == b["id"] else "sat")
            local[i] = (x, y, int(round(rad * 2)), role, par or sun)
        moons = []
        nm = len(b["moons"])
        for j, (m, ma) in enumerate(zip(b["moons"], _even(nm, th))):
            ns = len(m["sats"])
            sats = [{"id": s, "r": _r2(m["srs"][s]), "a0": round(sa % (2 * math.pi), 7), "d": m["sd"][s],
                     "period": period(S["P_SAT"], q, ns)}
                    for q, (s, sa) in enumerate(zip(m["sats"], _even(ns, ma)))]
            moons.append({"id": m["id"], "r": _r2(m["r"]), "a0": round(ma % (2 * math.pi), 7),
                          "d": m["d"], "period": period(S["P_MOON"], j, nm), "ext": _r2(m["ext"]),
                          "sat_r": _r2(m["sat_r"]), "sats": sats})
        out_planets.append({"id": b["id"], "ring": k + 1, "r": _r2(r), "a0": round(th % (2 * math.pi), 7),
                            "d": b["d"], "period": period(S["P_PLANET"], k, P),
                            "e": _r2(b["e"]), "moon_r": _r2(b["moon_r"]), "moons": moons})
    R = bodies[-1]["band"][1] if bodies else R_sun
    box = (-R, -R, R, R)
    return {"unit": unit, "sun": sun, "r_sun": R_sun, "R": R, "box": box,
            "planets": out_planets, "local": local, "warnings": warns,
            "orbs": orbs, "belt": belt,
            "bands": [list(b["band"]) for b in bodies]}


def solar_plan(brief, nodes) -> dict:
    """The whole solar layout (module docstring): the one plan both looks
    draw. Pure: reads the brief and the nodes (in outline order —
    builder.place has run) and changes neither."""
    S = SOLAR
    bumped = _bump_flags(brief)
    looks = node_looks(brief, nodes)
    tree = _tree(brief, nodes)
    station = stations(tree, nodes)
    systems = [_system(a, sun, planets, bumped, nodes, looks, station)
               for a, sun, planets in tree]
    centres, world_w, world_h, core = _galaxy([s["R"] for s in systems])
    out_nodes, out_systems, belts = {}, [], []
    for s, (cx, cy) in zip(systems, centres):
        act = brief.acts[s["unit"]]
        out_systems.append({
            "unit": s["unit"], "label": getattr(act, "short", "") or getattr(act, "label", ""),
            "sun": s["sun"], "cx": _r2(cx), "cy": _r2(cy), "r_sun": s["r_sun"], "R": _r2(s["R"]),
            "bbox": [_r2(cx + s["box"][0]), _r2(cy + s["box"][1]),
                     _r2(cx + s["box"][2]), _r2(cy + s["box"][3])],
            "planets": s["planets"]})
        for i, (x, y, d, role, par) in s["local"].items():
            out_nodes[i] = {"x": _r2(cx + x), "y": _r2(cy + y), "d": d, "role": role,
                            "unit": s["unit"], "parent": par}
            if i in looks:
                out_nodes[i]["look"] = looks[i]
            if i in s["orbs"]:
                out_nodes[i]["orbit"] = dict(s["orbs"][i])
            if looks.get(i) == "asteroid":
                out_nodes[i]["tumble"] = tumble(i)
            if i in station:
                out_nodes[i]["station"] = 1
        if s["belt"]:
            bl = s["belt"]
            belts.append({"sun": s["sun"], "cx": _r2(cx), "cy": _r2(cy), "r": _r2(bl["r"]), "w": bl["w"],
                          "n": int(min(400, max(40, 2 * math.pi * bl["r"] / 18))),
                          "seed": int(hash01("belt:" + s["sun"]) * 1e9)})
    order = [s["sun"] for s in out_systems]
    units = []
    for s in out_systems:
        if not units or units[-1]["unit"] != s["unit"]:
            units.append({"unit": s["unit"], "label": s["label"], "suns": [], "bbox": list(s["bbox"])})
        u = units[-1]
        u["suns"].append(s["sun"])
        u["bbox"] = [min(u["bbox"][0], s["bbox"][0]), min(u["bbox"][1], s["bbox"][1]),
                     max(u["bbox"][2], s["bbox"][2]), max(u["bbox"][3], s["bbox"][3])]
    return {
        "style": "orbit", "spin": SPIN,
        "world": {"w": world_w, "h": world_h},
        "sizes": {**S["D"], "planet_big": S["TIERS"]["planet"][-1], "station": S["STATION"],
                  "tiers": {k: list(v) for k, v in S["TIERS"].items()}, "bump": sorted(bumped)},
        "systems": out_systems,
        "units": units,
        "nodes": out_nodes,
        "sun_links": [[a, b] for a, b in zip(order, order[1:])],
        "warnings": [w for s in systems for w in s["warnings"]],
        "looks": {lk: sorted(i for i, v in looks.items() if v == lk) for lk, _ in LOOK_FLAGS
                  if any(v == lk for v in looks.values())},
        "look_flags": look_flags(brief),
        "belts": belts,
        **({"core": core} if core else {}),
        "drifters": [],
    }


def _galaxy(Rs):
    """Where each system's sun goes: ([(cx, cy)], world w, world h, core or None).
    One system: centred across, under TOP. Two or more: a spiral galaxy round
    the core (CORE_R) — ARMS arms of an Archimedean spiral rho = a + b*theta,
    arm k turned k*2pi/ARMS, the systems dealt to the arms in outline order and
    each pushed out along its arm (in GAL_STEP px steps of arc) to the first
    spot clearing the core by CORE_GAP and every system placed so far by
    SYS_GAP. The world is the square round the galaxy's reach G (the farthest
    system edge from the core) plus MARGIN at the sides, TOP above and BOTTOM
    under, so the whole galaxy may turn rigidly about the core (period
    core.p) and still keep every edge rule."""
    S = SOLAR
    if not Rs:
        return [], S["WORLD_W"], S["TOP"] + S["BOTTOM"], None
    if len(Rs) == 1:
        R = Rs[0]
        W = int(math.ceil(max(S["WORLD_W"], 2 * R + 2 * S["MARGIN"])))
        return [(W / 2, S["TOP"] + R)], W, int(math.ceil(S["TOP"] + 2 * R + S["BOTTOM"])), None
    arms, gap, cg = S["ARMS"], S["SYS_GAP"], S["CORE_R"] + S["CORE_GAP"]
    b = (sum(2 * r for r in Rs) / len(Rs) + gap) * arms / (2 * math.pi)
    a = cg + Rs[0]
    cur = [0.0] * arms
    out = []
    for k, R in enumerate(Rs):
        arm = k % arms
        th = cur[arm]
        for _ in range(200000):
            rho = a + b * th
            ang = SPIN * (th + arm * 2 * math.pi / arms)
            x, y = rho * math.cos(ang), rho * math.sin(ang)
            if rho >= R + cg - 1e-6 and all(math.hypot(x - px, y - py) >= R + pr + gap - 1e-6 for px, py, pr in out):
                break
            th += min(0.05, S["GAL_STEP"] / rho)
        cur[arm] = th
        out.append((x, y, R))
    G = max(math.hypot(x, y) + r for x, y, r in out)
    W = int(math.ceil(max(S["WORLD_W"], 2 * G + 2 * S["MARGIN"])))
    ox, oy = W / 2, S["TOP"] + G
    H = int(math.ceil(S["TOP"] + 2 * G + S["BOTTOM"]))
    return ([(ox + x, oy + y) for x, y, _ in out], W, H,
            {"x": _r2(ox), "y": _r2(oy), "r": S["CORE_R"], "p": S["P_GALAXY"]})


_ONE_DP = {"x", "y", "cx", "cy", "r", "R", "e", "ext", "moon_r", "sat_r", "r_sun", "bbox"}


def _num(v, dp):
    v = round(v, dp)
    return int(v) if v == int(v) else v


def compact(plan, key=None):
    """The plan as the page carries it: page coordinates and radii to 0.1 px
    (whole numbers written without a point), angles to 1e-4 rad (well under
    a pixel even 6000 px out), everything else as it is. (A comet's orbit
    {e, rot, k} is already rounded and kept whole.)"""
    if isinstance(plan, dict):
        return {k: (v if k == "orbit" else compact(v, k)) for k, v in plan.items()}
    if isinstance(plan, list):
        return [compact(v, key) for v in plan]
    if isinstance(plan, float) and key in _ONE_DP:
        return _num(plan, 1)
    if isinstance(plan, float) and key == "a0":
        return _num(plan, 4)
    if isinstance(plan, float) and plan == int(plan):
        return int(plan)
    return plan


def page_plans(brief, nodes) -> dict:
    """What a System page carries (window._ALTO_SOLAR): the one plan both
    looks draw, compacted, with the look a viewer sees first (brief.hub_look,
    'stars' | 'hub') as its "look"."""
    out = {**compact(solar_plan(brief, nodes)), "look": getattr(brief, "hub_look", "stars") or "stars"}
    if getattr(brief, "wallpaper_top", False):
        out["wp_top"] = 1
    return out


def solar_tree_plan(plan: dict, nodes) -> dict:
    """The solar plan as a tree plan (layout.outline_plan's shape), so the
    page's own machinery — run_plan here, TREE_GLUE's _altoTree in the page —
    puts every circle at its centre as an ordinary position: each node one
    ["float", ["card", id, 0], cy, "mid"] op (its CENTRE at cy whatever height
    the page measures), its x the plan's. No shift / slide: a solar circle's
    place is its orbit."""
    P = plan["nodes"]
    acts: list = []
    for n in nodes:
        while len(acts) <= n.act:
            acts.append([])
        if n.id in P:
            acts[n.act].append(["float", ["card", n.id, 0], P[n.id]["y"], "mid"])
    return {"x": {i: v["x"] for i, v in P.items()}, "w": {i: v["d"] for i, v in P.items()},
            "acts": acts, "etx": {}, "top": SOLAR["TOP"], "act_gap": 0, "row_gap": 40,
            "cx": plan["world"]["w"] / 2, "bus_span": 160, "bus_above": 50, "warnings": []}


def solar_heights(plan: dict) -> dict:
    """Each circle's height (its diameter): the builder's heights for run_plan."""
    return {i: float(v["d"]) for i, v in plan["nodes"].items()}


def solar_summary(plan: dict) -> dict:
    """What run_layout reports about a solar layout (the plan itself is in the
    page as window._ALTO_SOLAR)."""
    return {"style": plan["style"], "world": plan["world"],
            "systems": [{"unit": s["unit"], "sun": s["sun"], "planets": len(s["planets"]),
                         "moons": sum(len(p["moons"]) for p in s["planets"]),
                         "sats": sum(len(m["sats"]) for p in s["planets"] for m in p["moons"]),
                         "R": s["R"], "cx": s["cx"], "cy": s["cy"]} for s in plan["systems"]],
            "rows": len({s["cy"] for s in plan["systems"]}),
            "wide": plan["world"]["w"] > SOLAR["WORLD_W"]}


assert SOLAR_ROLES == ("sun", "planet", "moon", "sat")
