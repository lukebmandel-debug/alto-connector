"""Hub & spoke (an outline with layout "solar") and its two looks: the Star
chart (style "orbit": rings, moving bodies; the default) and plain (style
"spoke": still circles on straight spokes). The page carries both plans
(page_plans); brief.hub_look says which a viewer sees first.

Every ROOT node (Node.parent "") is a SUN — usually one per unit; a unit with
several roots holds several systems, kept together. A sun's children are PLANETS,
one to a ring, the first on the innermost ring and the rest outward in outline
order; their children are MOONS, spaced evenly on one small ring round their
planet; one level deeper are SATELLITES, round their moon. A fifth level is a
validation error (brief._check_solar_depth), never flattened.

solar_plan(brief, nodes) is pure and deterministic: the same outline always
gives the same plan, and nothing here needs a browser — every circle has a
diameter fixed by the outline alone (sizes below), so no card is measured.

Sizes (Luke, round 2): the sun is the largest body whatever it holds. A
planet's diameter goes up a tier with every two moons it has, a moon's with
every two satellites (SOLAR["TIERS"], clamped at the last tier); a satellite
is the smallest. A node carrying an extreme-importance flag (BUMP_FLAGS: a
brief flag whose id or name is exactly "pivotal", "critical" or "extreme
importance") is one tier larger, past the clamp if need be. The tiers keep a
strict order — sun > every planet > every moon > every satellite — and every
gap and ring radius below is computed from the actual diameters, so the
no-overlap guarantees hold for any mix.

Geometry. Each planet carries its moons (and their satellites) inside a disc of
radius `e` round its own centre. In the orbit style the rings are spaced so
those discs sweep DISJOINT annuli [r - e, r + e] round the sun: the planets can
turn at any speed, their moons round them, and no two circles ever touch. The
spoke style stands still, so it packs tighter: each planet takes the smallest
ring (still outside the one before it) and the nearest angle to its preferred
one at which none of its circles touch a circle already placed and none of its
spokes cross one. Moons sit evenly round their planet with the direction of
the sun halfway between two of them, so the planet's own spoke to the sun is
always clear (likewise satellites and their moon's spoke).

Systems sit side by side in unit order, suns on one line, centred in the
1700px world; a row that would come nearer the edge than SOLAR["MARGIN"] wraps,
and a single system wider than the world widens it (plan["world"]["w"]).

The plan (the contract with solar_draw.py, which reads window._ALTO_SOLAR):

  {"style": "orbit"|"spoke", "spin": -1,
   "world": {"w", "h"},
   "sizes": {"sun", "planet", "planet_big", "moon", "sat", "tiers", "bump"},
            # per-ROLE reference only: sun / planet / moon / sat are the base
            # (childless, unflagged) diameters, planet_big the largest a planet
            # can be, tiers the per-role ladders, bump the flag ids that bump.
            # The diameter to draw is always the node's own `d`.
   "systems": [{"unit": act index, "label", "sun", "cx", "cy", "r_sun", "R",
                "bbox": [x0, y0, x1, y1],
                "planets": [{"id", "ring", "r", "a0", "d", "period", "e",
                             "moon_r", "moons": [{"id", "r", "a0", "d", "period",
                                                  "sat_r", "sats": [{"id", "r", "a0", "d", "period"}]}]}]}],
   "units": [{"unit", "label", "suns": [sun ids], "bbox"}],   # a unit's systems together
   "nodes": {id: {"x", "y", "d", "role", "unit", "parent",
                  "look"?: "blackhole"|"comet"|"asteroid",        # by the user's flags (LOOK_FLAGS)
                  "orbit"?: {"e", "rot", "k"},                    # a comet, Star chart look only
                  "tumble"?: rad/s}},                             # an asteroid, Star chart look only
   "sun_links": [[sun id, sun id]], "warnings": [...],
   "looks": {look: [node ids]}, "look_flags": {brief flag id: look},
   "belts": [{"sun", "cx", "cy", "r", "w", "n", "seed"}],       # Star chart look only
   "core"?: {"x", "y", "r"},                                     # 2+ systems
   "drifters": [{"seed", "path": [[x, y], [x, y], [x, y]]}]}    # Star chart look only

Comets (Star chart look). A comet keeps its ring, period and a0 but moves on
an ellipse centred on what it orbits, semi-axes A = r(1 + c), B = r(1 − c)
with c = (1 − q)/(1 + q), q = √(1 − e²), its major axis at angle `rot`. At
time t its mean angle is M = a0 + spin·2πt/period (as for every body); with
m = M − rot, ψ = m when k = 0, and when k = 1 (a planet) ψ solves
ψ − e·sin ψ = m (Newton from ψ = m, 12 steps); its offset from what it
orbits is R(rot)·(A cos ψ, B sin ψ). It is never farther than c·r from where a
circular body at M would be (k = 0) and always between r − c·r and r + c·r
from what it orbits, and its family's reach and its ring's room count that
in, so the no-overlap guarantees still hold. e and rot are fixed per node
from its id (comet_shape; a crowded ring of moons may flatten e). An
asteroid tumbles at `tumble` rad/s; a black hole is only a look.

Belts, the core, drifters (decoration, never a node). A system of BELT_MIN
planets or more gets an asteroid belt of width w at radius r round its sun,
in a gap of its own between its inner and outer planets' bands (n rocks,
scattered from `seed`). A chart of two systems or more gets a galactic core:
a circle of CORE_R at the free spot nearest the suns' centroid, clear of
every system's disc by CORE_GAP and of the world edge by MARGIN (the world
grows downward for it when there is none). Drifting comets cross the chart
along paths at least DRIFT_CLEAR from every system and the core.

Systems come unit by unit, each unit's roots in order. When a unit holds
several (a Mind Palace district of several buildings) every unit starts a row
of its own; one system per unit flows side by side.

Angles are radians in page coordinates (x right, y DOWN), measured from +x: a
body at angle a sits at (cx + r cos a, cy + r sin a) round what it orbits. A
planet's `r`/`a0` are round its sun, a moon's round its planet, a satellite's
round its moon. In the orbit style a body's angle at time t (seconds) is
a0 + spin * 2π t / period; spin -1 turns everything counter-clockwise on
screen. `period` is 0 in the spoke style. `R` is the system's bounding radius
round its sun (orbit: every body stays inside it at all times, so a system may
be turned as a whole about its sun without touching its neighbour), `e` a
planet's own reach (planet + moons + satellites), `moon_r` / `sat_r` the ring
radius its moons / satellites share (0 when it has none). nodes[*].x/y are the
t = 0 centres; the builder writes them into the page as ordinary positions
(solar_tree_plan → run_plan / TREE_GLUE "float" ops anchored at the centre).
"""
from __future__ import annotations

import math

from .brief import BriefError, SOLAR_ROLES, solar_style

SOLAR = {
    # base diameters per role (no children, no flag)
    "D": {"sun": 184, "planet": 96, "moon": 50, "sat": 34},
    # the size ladders: a planet's tier is ceil(moons / 2) (clamped to the
    # ladder), a moon's ceil(satellites / 2); the last entry of each ladder is
    # reachable only by a bump (BUMP_FLAGS) from the tier below it
    "TIERS": {"planet": (96, 110, 124, 138, 152, 166),
              "moon": (50, 58, 66, 74, 82),
              "sat": (34, 40)},
    # clear space: between one planet's reach and the next ring's (and the
    # sun's), between a planet and its moons, a moon and its satellites
    "RING_GAP": 26, "MOON_GAP": 14, "SAT_GAP": 8,
    # spoke style: circles of different planets, and a spoke and a circle it
    # passes, keep at least this apart; consecutive rings at least MIN_STEP
    "SPOKE_GAP": 18, "SPOKE_CLEAR": 8, "MIN_STEP": 40, "R_STEP": 6, "A_STEP_DEG": 10,
    "SPOKE_BUDGET": 480,
    # between systems, from the world's side edges, above the first row (the
    # engine's band-label reserve, layout.LABEL_RESERVE) and under the last
    "SYS_GAP": 90, "MARGIN": 115, "TOP": 184, "BOTTOM": 160, "WORLD_W": 1700,
    # orbit periods in seconds: planets inner→outer, moons by planet, satellites
    "P_PLANET": (90.0, 150.0), "P_MOON": (30.0, 50.0), "P_SAT": 18.0,
    # the Star chart look's extras: a comet's eccentricity range; an asteroid's
    # tumble (rad/s, either way); an asteroid belt's width (a system of
    # BELT_MIN planets or more gets one, between its inner and outer planets);
    # the galactic core's radius and clear space (a chart of 2+ systems); how
    # far a drifting comet's path keeps from every system
    "ECC": (0.5, 0.7), "TUMBLE": (0.15, 0.6), "BELT_W": 70, "BELT_MIN": 4,
    "CORE_R": 60, "CORE_GAP": 40, "CORE_STEP": 20, "DRIFT_CLEAR": 40,
}
# What a node is drawn as, by the user's own flags (brief.flags): a flag whose
# id or name, lower-cased with spaces and underscores as hyphens, is in a row
# makes its nodes that kind of body. First match wins, in this order. The
# node keeps its role (planet / moon / satellite by depth), its size and its
# children; only the body changes. Both looks carry nodes[id].look; the plain
# look may ignore it.
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


def body_d(role: str, children: int, bumped: bool = False) -> int:
    """A body's diameter (module docstring, Sizes): the sun's is fixed; a
    planet / moon climbs a tier per two children, clamped below the ladder's
    bump-only top; a bump adds one tier."""
    if role == "sun":
        return SOLAR["D"]["sun"]
    ladder = SOLAR["TIERS"][role]
    tier = min(-(-children // 2), len(ladder) - 2) if role != "sat" else 0
    return ladder[min(tier + (1 if bumped else 0), len(ladder) - 1)]


def _ring_for(n: int, ext: float, gap: float, inner: float) -> float:
    """The radius of a ring of n bodies of reach `ext`, evenly spaced round a
    centre body of radius `inner`: clear of the centre and of each other, and
    far enough apart that the centre's own spoke (which runs out between two
    of them, _even) passes SPOKE_CLEAR clear of both."""
    if not n:
        return 0.0
    r = inner + gap + ext
    if n >= 2:
        r = max(r, (2 * ext + max(gap, 2 * SOLAR["SPOKE_CLEAR"])) / (2 * math.sin(math.pi / n)))
    return r


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


def _ring_fix(items, gap, inner):
    """A shared ring (_ring_for) for bodies [(id, reach, comet slack c)]: a
    comet on it (c > 0) strays up to c·r from where a circle would put it, so
    its reach grows by that, and the ring by as much as that needs (a fixed
    point, met from below). A comet's c is capped at sin(π/n)/2 on a ring of
    n, which keeps that a contraction. Returns (radius, reach used, {id: c})."""
    n = len(items)
    if not n:
        return 0.0, 0.0, {}
    cap = 0.5 * math.sin(math.pi / n) if n >= 2 else 0.5
    cs = {i: min(c, cap) for i, _, c in items if c > 0}
    r = _ring_for(n, max(x for _, x, _ in items), gap, inner)
    for _ in range(200):
        me = max(x + cs.get(i, 0.0) * r for i, x, _ in items)
        r2 = _ring_for(n, me, gap, inner)
        if r2 - r < 1e-9:
            r = r2
            break
        r = r2
    me = max(x + cs.get(i, 0.0) * r for i, x, _ in items)
    return r, me, cs


def _planet_body(pid, moons, size, S, slack=None):
    """A planet's own geometry round its centre: its and its family's
    diameters (size(id, role, children)), moon ring, satellite rings, reach.
    Independent of where the planet is. slack: {id: c} for the comets of a
    Star chart look (comet_shape / ecc_slack); body["orb"] then holds each
    comet moon's / satellite's orbit {e, rot, k: 0} as it is drawn."""
    slack = slack or {}
    d_p = size(pid, "planet", len(moons))
    R_p = d_p / 2
    ms, orb = [], {}
    for mid, sats in moons:
        d_m = size(mid, "moon", len(sats))
        R_m = d_m / 2
        sd = {q: size(q, "sat", 0) for q in sats}
        sat_r, R_s, cs = _ring_fix([(q, sd[q] / 2, slack.get(q, 0.0)) for q in sats], S["SAT_GAP"], R_m)
        for q, c in cs.items():
            orb[q] = {"e": round(slack_ecc(c), 4), "rot": comet_shape(q)[1], "k": 0}
        ms.append({"id": mid, "d": d_m, "sats": sats, "sd": sd, "sat_r": sat_r,
                   "ext": (sat_r + R_s) if sats else R_m})
    moon_r, me, cs = _ring_fix([(m["id"], m["ext"], slack.get(m["id"], 0.0)) for m in ms], S["MOON_GAP"], R_p)
    for q, c in cs.items():
        orb[q] = {"e": round(slack_ecc(c), 4), "rot": comet_shape(q)[1], "k": 0}
    e = (moon_r + me) if ms else R_p
    return {"id": pid, "d": d_p, "moons": ms, "moon_r": moon_r, "e": max(e, R_p), "orb": orb}


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
        ox, oy = _at(body["moon_r"], ma, orbs.get(m["id"]))
        mx, my = px + ox, py + oy
        circles.append((m["id"], mx, my, m["d"] / 2, body["id"]))
        segs.append((m["id"], body["id"], mx, my, px, py))
        for s, sa in zip(m["sats"], _even(len(m["sats"]), ma)):
            ox, oy = _at(m["sat_r"], sa, orbs.get(s))
            sx, sy = mx + ox, my + oy
            circles.append((s, sx, sy, m["sd"][s] / 2, m["id"]))
            segs.append((s, m["id"], sx, sy, mx, my))
    return circles, segs


def _seg_dist(cx, cy, x1, y1, x2, y2) -> float:
    dx, dy = x2 - x1, y2 - y1
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((cx - x1) * dx + (cy - y1) * dy) / L))
    return math.hypot(cx - (x1 + t * dx), cy - (y1 + t * dy))


def _fits(circles, segs, spoke, e, placed, placed_segs, S) -> bool:
    """A spoke-style planet family (its circles, its moons' and satellites'
    spokes, and — when given — its own spoke to the sun) against everything
    already placed. The family lies within `e` of the planet (circles[0]), so
    whatever is farther than that from it is passed over whole."""
    g, clear = S["SPOKE_GAP"], S["SPOKE_CLEAR"]
    px, py = circles[0][1], circles[0][2]
    near = [c for c in placed
            if math.hypot(px - c[1], py - c[2]) < e + c[3] + max(g, S["RING_GAP"], clear)]
    for (i, x, y, rad, _p) in circles:
        for (j, x2, y2, r2, _q) in near:
            gap = S["RING_GAP"] if _q == "sun" else g
            if math.hypot(x - x2, y - y2) < rad + r2 + gap:
                return False
    for (a, b, x1, y1, x2, y2) in placed_segs:
        if _seg_dist(px, py, x1, y1, x2, y2) >= e + clear:
            continue
        for (i, x, y, rad, _p) in circles:
            if _seg_dist(x, y, x1, y1, x2, y2) < rad + clear:
                return False
    for (a, b, x1, y1, x2, y2) in segs:
        for (j, cx, cy, rad, _q) in near:
            if j not in (a, b) and _seg_dist(cx, cy, x1, y1, x2, y2) < rad + clear:
                return False
    for (a, b, x1, y1, x2, y2) in spoke:
        for (j, cx, cy, rad, _q) in placed:
            if j not in (a, b) and _seg_dist(cx, cy, x1, y1, x2, y2) < rad + clear:
                return False
    return True


def _system(unit, sun, planets, style, bumped, brief_nodes, looks=None):
    """One system round its sun at (0, 0): its planets with their rings and
    angles, every circle's local centre, and its bounding box. looks: {node
    id: look} (node_looks) — in the orbit style a comet gets an ellipse and
    room for it, and a system of BELT_MIN planets or more an asteroid belt."""
    S, D = SOLAR, SOLAR["D"]
    R_sun = D["sun"] / 2
    flags = {n.id: set(n.flags or []) for n in brief_nodes}
    looks = looks or {}
    moving = style == "orbit"
    slack = ({i: ecc_slack(comet_shape(i)[0]) for i, lk in looks.items() if lk == "comet"}
             if moving else {})

    def size(i, role, children):
        return body_d(role, children, bool(flags.get(i, set()) & bumped))
    bodies = [_planet_body(p, moons, size, S, slack) for p, moons in planets]
    P = len(bodies)
    rings, angles, warns, belt = [], [], [], None
    orbs = {}
    for b in bodies:
        orbs.update(b["orb"])
    if style == "orbit":
        # Each planet's family sweeps the annulus [r − s − e, r + s + e] (s:
        # its comet slack, else 0); the annuli are disjoint, RING_GAP apart.
        edge = R_sun
        split = P // 2 if P >= S["BELT_MIN"] else -1
        for k, b in enumerate(bodies):
            if k == split:
                belt = {"r": edge + S["RING_GAP"] + S["BELT_W"] / 2, "w": S["BELT_W"]}
                edge += S["RING_GAP"] + S["BELT_W"]
            c = slack.get(b["id"], 0.0)
            r = (edge + S["RING_GAP"] + b["e"]) / (1 - c) + (0.05 if c else 0.0)   # (a hair over: r is written to 0.01)
            if c:
                orbs[b["id"]] = {"e": comet_shape(b["id"])[0], "rot": comet_shape(b["id"])[1], "k": 1}
            rings.append(r)
            angles.append(-math.pi / 2 + k * GOLDEN)
            b["band"] = (r - c * r - b["e"], r + c * r + b["e"])
            edge = b["band"][1]
    else:
        placed = [(sun, 0.0, 0.0, R_sun, "sun")]
        placed_segs = []
        r_prev = 0.0
        step = math.radians(S["A_STEP_DEG"])
        tries = [0.0] + [s * j * step for j in range(1, int(round(math.pi / step)) + 1) for s in (1, -1)]
        for k, b in enumerate(bodies):
            pref = -math.pi / 2 + k * GOLDEN
            r0 = max(R_sun + S["RING_GAP"] + b["d"] / 2,
                     (r_prev + S["MIN_STEP"]) if k else 0.0)
            hit = None
            # First the nearest ring at which some angle keeps the planet's
            # spoke to the sun clear of every inner circle. Inner families can
            # close every angle (a spoke always crosses the inner rings at its
            # own angle, however far out the planet goes), so that search has
            # a budget; past it the spoke may pass behind an inner circle
            # (plan["warnings"] names it) and only the circles must clear,
            # which a far enough ring always gives.
            for spoke_clear, budget in ((True, S["SPOKE_BUDGET"]), (False, None)):
                r = r0
                while hit is None and (budget is None or r <= r0 + budget):
                    for dt in tries:
                        th = pref + dt
                        cs, sg = _local_circles(b, th, r)
                        spoke = [(b["id"], sun, cs[0][1], cs[0][2], 0.0, 0.0)]
                        if _fits(cs, sg, spoke if spoke_clear else [], b["e"], placed, placed_segs, S):
                            hit = (th, cs, sg + spoke)
                            break
                    else:
                        r += S["R_STEP"]
                if hit:
                    if not spoke_clear:
                        warns.append(f"unit {unit + 1}: no clear line from {b['id']} to its sun "
                                     f"{sun} — its spoke passes behind an inner planet's family")
                    break
            th, cs, sg = hit
            placed += cs
            placed_segs += sg
            rings.append(r)
            angles.append(th)
            r_prev = r

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
        for m, ma in zip(b["moons"], _even(len(b["moons"]), th)):
            sats = [{"id": s, "r": _r2(m["sat_r"]), "a0": round(sa % (2 * math.pi), 7), "d": m["sd"][s],
                     "period": S["P_SAT"] if moving else 0}
                    for s, sa in zip(m["sats"], _even(len(m["sats"]), ma))]
            moons.append({"id": m["id"], "r": _r2(b["moon_r"]), "a0": round(ma % (2 * math.pi), 7),
                          "d": m["d"], "period": period(S["P_MOON"], k, P) if moving else 0,
                          "sat_r": _r2(m["sat_r"]), "sats": sats})
        out_planets.append({"id": b["id"], "ring": k + 1, "r": _r2(r), "a0": round(th % (2 * math.pi), 7),
                            "d": b["d"], "period": period(S["P_PLANET"], k, P) if moving else 0,
                            "e": _r2(b["e"]), "moon_r": _r2(b["moon_r"]), "moons": moons})
    if style == "orbit":
        R = bodies[-1]["band"][1] if bodies else R_sun
        box = (-R, -R, R, R)
    else:
        xs0 = [x - d / 2 for x, y, d, _, _ in local.values()]
        xs1 = [x + d / 2 for x, y, d, _, _ in local.values()]
        ys0 = [y - d / 2 for x, y, d, _, _ in local.values()]
        ys1 = [y + d / 2 for x, y, d, _, _ in local.values()]
        box = (min(xs0), min(ys0), max(xs1), max(ys1))
        R = max(math.hypot(x, y) + d / 2 for x, y, d, _, _ in local.values())
    return {"unit": unit, "sun": sun, "r_sun": R_sun, "R": R, "box": box,
            "planets": out_planets, "local": local, "warnings": warns,
            "orbs": orbs, "belt": belt,
            "bands": [list(b["band"]) for b in bodies] if style == "orbit" else []}


def solar_plan(brief, nodes, style: str = "") -> dict:
    """The whole solar layout (module docstring). Pure: reads the brief and
    the nodes (in outline order — builder.place has run) and changes neither.
    `style` overrides the brief's own (brief.solar_style; "spoke" if none)."""
    S = SOLAR
    style = style or solar_style(brief) or "spoke"
    bumped = _bump_flags(brief)
    looks = node_looks(brief, nodes)
    systems = [_system(a, sun, planets, style, bumped, nodes, looks)
               for a, sun, planets in _tree(brief, nodes)]
    widths = [s["box"][2] - s["box"][0] for s in systems]
    world_w = int(math.ceil(max([S["WORLD_W"]] + [w + 2 * S["MARGIN"] for w in widths])))
    inner = world_w - 2 * S["MARGIN"]
    # A unit (district) holding several systems keeps them together: each
    # unit then starts a row of its own. One system per unit (any outline)
    # simply flows, side by side.
    grouped = len({s["unit"] for s in systems}) < len(systems)
    rows, row, span = [], [], 0.0
    for s, w in zip(systems, widths):
        if row and (span + S["SYS_GAP"] + w > inner + 1e-6
                    or (grouped and s["unit"] != row[-1]["unit"])):
            rows.append(row)
            row, span = [], 0.0
        span += (S["SYS_GAP"] if row else 0.0) + w
        row.append(s)
    if row:
        rows.append(row)

    out_nodes, out_systems, belts = {}, [], []
    top = float(S["TOP"])
    for row in rows:
        up = max(-s["box"][1] for s in row)
        down = max(s["box"][3] for s in row)
        total = sum(s["box"][2] - s["box"][0] for s in row) + S["SYS_GAP"] * (len(row) - 1)
        left = (world_w - total) / 2
        cy = top + up
        for s in row:
            cx = left - s["box"][0]
            left += (s["box"][2] - s["box"][0]) + S["SYS_GAP"]
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
                if style == "orbit" and looks.get(i) == "asteroid":
                    out_nodes[i]["tumble"] = tumble(i)
            if s["belt"]:
                bl = s["belt"]
                belts.append({"sun": s["sun"], "cx": _r2(cx), "cy": _r2(cy), "r": _r2(bl["r"]), "w": bl["w"],
                              "n": int(min(400, max(40, 2 * math.pi * bl["r"] / 18))),
                              "seed": int(hash01("belt:" + s["sun"]) * 1e9)})
        top = cy + down + S["SYS_GAP"]
    world_h = int(math.ceil((top - S["SYS_GAP"]) + S["BOTTOM"])) if rows else S["TOP"] + S["BOTTOM"]
    core, world_h = _core(out_systems, world_w, world_h, top - S["SYS_GAP"])
    drifters = _drifters(out_systems, core, world_w, world_h) if style == "orbit" else []
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
        "style": style, "spin": SPIN,
        "world": {"w": world_w, "h": world_h},
        "sizes": {**S["D"], "planet_big": S["TIERS"]["planet"][-1],
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
        "drifters": drifters,
    }


def _core(systems, W, H, bottom):
    """The galactic core of a chart of two systems or more: the free spot
    nearest the suns' centroid (CORE_STEP grid) whose circle of CORE_R clears
    every system's disc (R round its sun) by CORE_GAP and the world's edges by
    MARGIN. None for one system. With no such spot a band is added under the
    last row and the core sits in it: (core, world height)."""
    S = SOLAR
    if len(systems) < 2:
        return None, H
    need = S["CORE_R"] + S["CORE_GAP"]
    gx = sum(s["cx"] for s in systems) / len(systems)
    gy = sum(s["cy"] for s in systems) / len(systems)
    lo_x, hi_x = S["MARGIN"] + S["CORE_R"], W - S["MARGIN"] - S["CORE_R"]
    lo_y, hi_y = S["MARGIN"] + S["CORE_R"], H - S["MARGIN"] - S["CORE_R"]
    best = None
    step = S["CORE_STEP"]
    nx, ny = int((hi_x - lo_x) // step), int((hi_y - lo_y) // step)
    for j in range(ny + 1):
        y = lo_y + j * step
        for i in range(nx + 1):
            x = lo_x + i * step
            if all(math.hypot(x - s["cx"], y - s["cy"]) >= s["R"] + need for s in systems):
                d = (x - gx) ** 2 + (y - gy) ** 2
                if best is None or d < best[0] - 1e-9:
                    best = (d, x, y)
    if best:
        return {"x": _r2(best[1]), "y": _r2(best[2]), "r": S["CORE_R"]}, H
    y = max([bottom] + [s["cy"] + s["R"] for s in systems]) + S["CORE_GAP"] + S["CORE_R"]
    H2 = int(math.ceil(max(H, y + S["CORE_R"] + S["BOTTOM"])))
    return {"x": _r2(W / 2), "y": _r2(y), "r": S["CORE_R"]}, H2


def _drifters(systems, core, W, H):
    """A few decorative comets crossing the chart where nothing is: a path
    (three points: start, bend, end) along the band above the first row,
    below the last, and through each gap between rows wide enough, every one
    at least DRIFT_CLEAR from every system's disc and the core."""
    S = SOLAR
    ys = []
    if systems:
        ys.append(min(s["cy"] - s["R"] for s in systems) / 2)
        ys.append((max(s["cy"] + s["R"] for s in systems) + H) / 2)
        # gaps between consecutive rows
        bands = sorted(((s["cy"] - s["R"], s["cy"] + s["R"]) for s in systems))
        reach = bands[0][1]
        for a, b in bands[1:]:
            if a - reach >= 2 * S["DRIFT_CLEAR"] + 10:
                ys.append((a + reach) / 2)
            reach = max(reach, b)
    out = []

    def clear(pts):
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            for s in systems:
                if _seg_dist(s["cx"], s["cy"], x1, y1, x2, y2) < s["R"] + S["DRIFT_CLEAR"]:
                    return False
            if core and _seg_dist(core["x"], core["y"], x1, y1, x2, y2) < core["r"] + S["DRIFT_CLEAR"]:
                return False
        return True
    for k, y in enumerate(ys[:4]):
        seed = int(hash01(f"drift:{k}:{int(y)}") * 1e9)
        bend = (hash01(f"bend:{seed}") - 0.5) * 2 * S["DRIFT_CLEAR"] * 0.5
        flip = hash01(f"dir:{seed}") < 0.5
        pts = [[0.0, y], [W / 2, y + bend], [float(W), y]]
        if flip:
            pts.reverse()
        if clear(pts):
            out.append({"seed": seed, "path": [[_r2(x), _r2(yy)] for x, yy in pts]})
    return out


_ONE_DP = {"x", "y", "cx", "cy", "r", "R", "e", "moon_r", "sat_r", "r_sun", "bbox"}


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
    """What a Hub & spoke page carries (window._ALTO_SOLAR): both looks'
    plans, compacted, and the look a viewer sees first —
    {"look": "stars"|"plain", "looks": {"stars": <orbit plan>, "plain": <spoke plan>}}.
    (blocks.py also spreads the first look's plan over the top level, so a
    reader of the single-plan shape still finds style / world / systems /
    nodes / sun_links there.)"""
    from .brief import LOOK_STYLE
    look = getattr(brief, "hub_look", "stars") or "stars"
    return {"look": look,
            "looks": {lk: compact(solar_plan(brief, nodes, st)) for lk, st in LOOK_STYLE.items()}}


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
