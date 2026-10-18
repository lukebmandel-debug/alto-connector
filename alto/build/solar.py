"""Solar layouts: Hub & spoke (an outline with layout "solar", still, style
"spoke") and the Star chart (a Mind Palace with palace_view "stars", moving,
style "orbit"); brief.solar_style says which a brief is.

Every ROOT node (Node.parent "") is a SUN — an outline has one per unit, a Mind
Palace one per building, so a district may hold several systems. A sun's children are PLANETS,
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
   "units": [{"unit", "label", "suns": [sun ids], "bbox"}],   # a district's systems together
   "nodes": {id: {"x", "y", "d", "role", "unit", "parent"}},
   "sun_links": [[sun id, sun id]], "warnings": [...]}

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
}
# A brief flag whose id or name, lower-cased with spaces and underscores as
# hyphens, is one of these marks extreme importance: the nodes carrying it are
# drawn one tier up. An explicit list, not a guess at what a name means.
BUMP_FLAGS = ("pivotal", "critical", "extreme-importance")
GOLDEN = math.pi * (3 - math.sqrt(5))          # 137.5°: neighbouring planets never line up
SPIN = -1


def _r2(v: float) -> float:
    return round(v, 2)


def _bump_flags(brief) -> set:
    out = set()
    for fl in getattr(brief, "flags", None) or []:
        if not isinstance(fl, dict):
            continue
        names = {str(fl.get(k) or "").strip().lower().replace(" ", "-").replace("_", "-")
                 for k in ("id", "name")}
        if names & set(BUMP_FLAGS):
            out.add(fl.get("id"))
    return out


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
                    way_out = ("keep the palace as a city (palace_view 'city')"
                               if getattr(brief, "mode", "") == "palace" else "use layout 'tree'")
                    raise BriefError(
                        f"node {kids[s][0]} is deeper than a satellite ({sun} → {p} → {m} → "
                        f"{s} → {kids[s][0]}): a solar layout has four levels — "
                        f"restructure it or {way_out}")
            moons.append((m, list(sats)))
        planets.append((p, moons))
    return planets


def _planet_body(pid, moons, size, S):
    """A planet's own geometry round its centre: its and its family's
    diameters (size(id, role, children)), moon ring, satellite rings, reach.
    Independent of where the planet is."""
    d_p = size(pid, "planet", len(moons))
    R_p = d_p / 2
    ms = []
    for mid, sats in moons:
        d_m = size(mid, "moon", len(sats))
        R_m = d_m / 2
        sd = {q: size(q, "sat", 0) for q in sats}
        R_s = max(sd.values()) / 2 if sats else 0.0
        sat_r = _ring_for(len(sats), R_s, S["SAT_GAP"], R_m)
        ms.append({"id": mid, "d": d_m, "sats": sats, "sd": sd, "sat_r": sat_r,
                   "ext": (sat_r + R_s) if sats else R_m})
    me = max([m["ext"] for m in ms] or [0.0])
    moon_r = _ring_for(len(ms), me, S["MOON_GAP"], R_p)
    e = (moon_r + me) if ms else R_p
    return {"id": pid, "d": d_p, "moons": ms, "moon_r": moon_r, "e": max(e, R_p)}


def _local_circles(body, theta, r):
    """Every circle of a planet's family as (id, x, y, radius, parent id) round
    the SUN, the planet at angle theta on ring r, and its spokes as segments
    (child id, parent id, x1, y1, x2, y2)."""
    px, py = r * math.cos(theta), r * math.sin(theta)
    circles = [(body["id"], px, py, body["d"] / 2, None)]
    segs = []
    for m, ma in zip(body["moons"], _even(len(body["moons"]), theta)):
        mx, my = px + body["moon_r"] * math.cos(ma), py + body["moon_r"] * math.sin(ma)
        circles.append((m["id"], mx, my, m["d"] / 2, body["id"]))
        segs.append((m["id"], body["id"], mx, my, px, py))
        for s, sa in zip(m["sats"], _even(len(m["sats"]), ma)):
            sx, sy = mx + m["sat_r"] * math.cos(sa), my + m["sat_r"] * math.sin(sa)
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


def _system(unit, sun, planets, style, bumped, brief_nodes):
    """One system round its sun at (0, 0): its planets with their rings and
    angles, every circle's local centre, and its bounding box."""
    S, D = SOLAR, SOLAR["D"]
    R_sun = D["sun"] / 2
    flags = {n.id: set(n.flags or []) for n in brief_nodes}

    def size(i, role, children):
        return body_d(role, children, bool(flags.get(i, set()) & bumped))
    bodies = [_planet_body(p, moons, size, S) for p, moons in planets]
    P = len(bodies)
    rings, angles, warns = [], [], []
    if style == "orbit":
        r_prev, e_prev = 0.0, R_sun
        for k, b in enumerate(bodies):
            r = (R_sun + S["RING_GAP"] + b["e"]) if k == 0 else (r_prev + e_prev + S["RING_GAP"] + b["e"])
            rings.append(r)
            angles.append(-math.pi / 2 + k * GOLDEN)
            r_prev, e_prev = r, b["e"]
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
        moving = style == "orbit"
        cs, _ = _local_circles(b, th, r)
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
        R = (rings[-1] + bodies[-1]["e"]) if bodies else R_sun
        box = (-R, -R, R, R)
    else:
        xs0 = [x - d / 2 for x, y, d, _, _ in local.values()]
        xs1 = [x + d / 2 for x, y, d, _, _ in local.values()]
        ys0 = [y - d / 2 for x, y, d, _, _ in local.values()]
        ys1 = [y + d / 2 for x, y, d, _, _ in local.values()]
        box = (min(xs0), min(ys0), max(xs1), max(ys1))
        R = max(math.hypot(x, y) + d / 2 for x, y, d, _, _ in local.values())
    return {"unit": unit, "sun": sun, "r_sun": R_sun, "R": R, "box": box,
            "planets": out_planets, "local": local, "warnings": warns}


def solar_plan(brief, nodes, style: str = "") -> dict:
    """The whole solar layout (module docstring). Pure: reads the brief and
    the nodes (in outline order — builder.place has run) and changes neither.
    `style` overrides the brief's own (brief.solar_style; "spoke" if none)."""
    S = SOLAR
    style = style or solar_style(brief) or "spoke"
    bumped = _bump_flags(brief)
    systems = [_system(a, sun, planets, style, bumped, nodes)
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

    out_nodes, out_systems = {}, []
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
        top = cy + down + S["SYS_GAP"]
    world_h = int(math.ceil((top - S["SYS_GAP"]) + S["BOTTOM"])) if rows else S["TOP"] + S["BOTTOM"]
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
    }


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
