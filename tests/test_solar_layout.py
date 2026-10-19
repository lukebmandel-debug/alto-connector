"""Hub & spoke (brief.layout == "solar", alto/build/solar.py): every root a
solar system — its children planets one to a ring in outline order, theirs
moons round them, theirs satellites — in two looks, the Star chart (style
"orbit", moving; comets on ellipses, belts, a galactic core) and plain
(style "spoke", still). A 1.9.105 Star chart palace loads as one.

The geometry is held to its promises here with plain circle arithmetic: in the
orbit style no two circles of a system ever touch at ANY moment (each planet's
family sweeps an annulus of its own), in the spoke style none touch and every
spoke runs clear; systems never touch each other; nothing comes within the
margin of the world's edge. Then the build: the page carries the plan as
window._ALTO_SOLAR and puts every circle's centre where the plan says, through
the tree's own plan runner (Python and the page's TREE_GLUE, held equal under
node)."""
import copy
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.brief import Act, Brief, BriefError, Node, solar_style, validate_brief, validate_nodes  # noqa: E402
from alto.build.builder import build_timeline, load_brief, place, run_layout  # noqa: E402
from alto.build import detail_extras as dx  # noqa: E402
from alto.build.layout import plan_js, run_plan  # noqa: E402
from alto.build.solar import (SOLAR, body_d, solar_heights, solar_plan,  # noqa: E402
                              solar_tree_plan)

NODE = shutil.which("node") or str(Path.home() / ".local/node/bin/node")
needs_node = pytest.mark.skipif(not Path(NODE).is_file(), reason="needs node")
OUTLINE = ROOT / "samples" / "outline_brief.json"
GAP_MIN = min(SOLAR["MOON_GAP"], SOLAR["SAT_GAP"], SOLAR["RING_GAP"], SOLAR["SPOKE_GAP"]) - 0.5


# ── synthetic outlines ─────────────────────────────────────────────────────
# A unit is a list of planets; a planet a list of moons; a moon its number of
# satellites. Ids spell where a node sits: u1-p2-m3-s1.

def _brief(n_units, style, flags=None):
    """A Hub & spoke opening in the plain look ("spoke") or the Star chart
    look ("orbit")."""
    acts = [Act(label=f"UNIT {a + 1}", short=f"Unit {a + 1}") for a in range(n_units)]
    return Brief(title="Solar test", subject="s", columns=5, acts=acts, timeline_id="solar-test",
                 flags=flags or [], mode="outline", layout="solar",
                 hub_look="plain" if style == "spoke" else "stars")


def _outline(units, style="spoke", flags=None):
    b = _brief(len(units), style, flags)
    nodes = []

    def add(i, act, parent="", tag="Concept"):
        nodes.append(Node(id=i, act=act, tag=tag, title=i.replace("-", " "),
                          desc="From the notes: " + i, parent=parent))
    for a, planets in enumerate(units):
        sun = f"u{a + 1}"
        add(sun, a, tag="Unit")
        for p, moons in enumerate(planets):
            pid = f"{sun}-p{p + 1}"
            add(pid, a, sun)
            for m, sats in enumerate(moons):
                mid = f"{pid}-m{m + 1}"
                add(mid, a, pid)
                for s in range(sats):
                    add(f"{mid}-s{s + 1}", a, mid, tag="Outcome")
    validate_brief(b)
    validate_nodes(b, nodes)
    place(b, nodes)
    return b, nodes


# Civ Pro: nine units — PJ, SMJ, Venue, Erie, Pleading, Joinder, Discovery,
# Summary Judgment, Preclusion — of three to six doctrines, each with its cases
# (moons) and some cases' holdings or prongs (satellites).
CIVPRO = [
    [[0, 0, 0], [2, 0, 0, 2], [0, 0], [0], []],
    [[0, 1, 0], [0, 0], [0, 0, 0], [0, 0, 0]],
    [[0, 0, 0], [0, 0], [0, 0]],
    [[0, 0], [0], [0], [0, 2], [], [0]],
    [[0, 0, 0], [0], [0, 0, 0], [7, 0, 0], [0, 0]],
    [[0, 0], [0], [0, 0, 0], [], [0], [0, 0]],
    [[0, 0, 0, 0], [0, 0], [0, 0, 0], [0, 0]],
    [[0, 0], [0, 0, 0], [0]],
    [[2, 2, 0, 0], [0, 0, 0, 0]],
]
# Torts: intentional torts (battery, assault, false imprisonment, trespass…)
# whose elements are moons and whose Liable / Not Liable outcomes are
# satellites; defenses; negligence's four elements; strict liability.
TORTS = [
    [[2, 2, 2], [2, 2], [2, 2, 2], [2], [2, 2], [2, 2], [2, 2]],
    [[2, 2], [2, 2, 2], [2], [2]],
    [[2, 2, 2, 2], [2, 2, 2], [2, 2, 2, 2], [2, 2]],
    [[0, 0], [0, 0, 0]],
]


def civpro_shape(style="spoke"):
    return _outline(CIVPRO, style)


def torts_shape(style="spoke"):
    return _outline(TORTS, style)


def _stars(districts, flags=None):
    """A Hub & spoke (Star chart look) with several roots (suns) per unit:
    districts is [[root]], a root [planet], a planet [satellites per moon]."""
    b = _brief(len(districts), "orbit", flags)
    nodes = []

    def add(i, act, parent=""):
        nodes.append(Node(id=i, act=act, tag="Floor" if parent else "Building", title=i,
                          desc="From the notes: " + i, parent=parent))
    for a, buildings in enumerate(districts):
        for k, planets in enumerate(buildings):
            sun = f"d{a + 1}b{k + 1}"
            add(sun, a)
            for p, moons in enumerate(planets):
                pid = f"{sun}-p{p + 1}"
                add(pid, a, sun)
                for m, sats in enumerate(moons):
                    mid = f"{pid}-m{m + 1}"
                    add(mid, a, pid)
                    for q in range(sats):
                        add(f"{mid}-s{q + 1}", a, mid)
    validate_brief(b)
    validate_nodes(b, nodes)
    place(b, nodes)
    return b, nodes


# ── geometry helpers ───────────────────────────────────────────────────────

def _slack(orb):
    """c of a comet orbit (its ellipse's semi-axes are r(1 ± c)); 0 for a circle."""
    if not orb:
        return 0.0
    q = math.sqrt(1 - orb["e"] ** 2)
    return (1 - q) / (1 + q)


def _off(r, a, orb):
    """Where a body sits round what it orbits at mean angle a — written out
    here from the plan's documented formula, not imported."""
    if not orb:
        return r * math.cos(a), r * math.sin(a)
    c, e, rot = _slack(orb), orb["e"], orb["rot"]
    m = a - rot
    psi = m
    if orb.get("k"):
        for _ in range(30):
            psi -= (psi - e * math.sin(psi) - m) / (1 - e * math.cos(psi))
    x, y = r * (1 + c) * math.cos(psi), r * (1 - c) * math.sin(psi)
    return x * math.cos(rot) - y * math.sin(rot), x * math.sin(rot) + y * math.cos(rot)


def _circles_at(plan, t):
    """{id: (x, y, radius)} of every circle at time t (seconds)."""
    out, spin, N = {}, plan["spin"], plan["nodes"]

    def ang(body):
        return body["a0"] + (spin * 2 * math.pi * t / body["period"] if body["period"] else 0.0)

    def at(x, y, body):
        dx, dy = _off(body["r"], ang(body), N[body["id"]].get("orbit"))
        return x + dx, y + dy
    for s in plan["systems"]:
        cx, cy = s["cx"], s["cy"]
        out[s["sun"]] = (cx, cy, s["r_sun"])
        for p in s["planets"]:
            px, py = at(cx, cy, p)
            out[p["id"]] = (px, py, p["d"] / 2)
            for m in p["moons"]:
                mx, my = at(px, py, m)
                out[m["id"]] = (mx, my, m["d"] / 2)
                for q in m["sats"]:
                    qx, qy = at(mx, my, q)
                    out[q["id"]] = (qx, qy, q["d"] / 2)
    return out


def _overlaps(circ, gap=GAP_MIN):
    ids = sorted(circ)
    bad = []
    for i, a in enumerate(ids):
        ax, ay, ar = circ[a]
        for b in ids[i + 1:]:
            bx, by, br = circ[b]
            if math.hypot(ax - bx, ay - by) < ar + br + gap:
                bad.append((a, b, round(math.hypot(ax - bx, ay - by) - ar - br, 1)))
    return bad


def _seg_dist(cx, cy, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L = dx * dx + dy * dy
    t = 0.0 if not L else max(0.0, min(1.0, ((cx - x1) * dx + (cy - y1) * dy) / L))
    return math.hypot(cx - x1 - t * dx, cy - y1 - t * dy)


def _assert_annuli(plan):
    """Star chart look: each planet's family stays within `e` of where its
    planet would be on a circle (a comet's ellipse strays at most c·r from
    it), so each family sweeps the annulus [r − c r − e, r + c r + e]; the
    annuli are disjoint and clear of the sun, and an asteroid belt runs in a
    gap of its own between two of them — so nothing ever meets, at any speed.
    (Proved here from the plan's numbers, independently of solar.py.)"""
    N = plan["nodes"]
    belts = {b["sun"]: b for b in plan["belts"]}
    for s in plan["systems"]:
        inner, gaps = s["r_sun"], []
        for p in s["planets"]:
            reach = p["d"] / 2
            for m in p["moons"]:
                cm = _slack(N[m["id"]].get("orbit"))
                sr = max([m["d"] / 2] + [q["r"] * (1 + _slack(N[q["id"]].get("orbit"))) + q["d"] / 2
                                         for q in m["sats"]])
                # the moon's own reach round where it would be on its circle
                mreach = cm * m["r"] + sr
                reach = max(reach, m["r"] + mreach)
                # a moon clears its planet whatever it and its satellites do
                assert m["r"] - mreach >= p["d"] / 2 + SOLAR["MOON_GAP"] - 0.01, (p["id"], m["id"])
                for q in m["sats"]:
                    cq = _slack(N[q["id"]].get("orbit"))
                    assert q["r"] * (1 - cq) - q["d"] / 2 >= m["d"] / 2 + SOLAR["SAT_GAP"] - 0.01
            assert reach <= p["e"] + 0.05, (p["id"], reach, p["e"])
            sp = _slack(N[p["id"]].get("orbit")) * p["r"]
            gaps.append((inner, p["r"] - sp - p["e"]))
            assert p["r"] - sp - p["e"] >= inner + SOLAR["RING_GAP"] - 0.05, (s["sun"], p["id"])
            inner = p["r"] + sp + p["e"]
        assert inner <= s["R"] + 0.05
        if s["sun"] in belts:
            bl = belts[s["sun"]]
            assert len(s["planets"]) >= SOLAR["BELT_MIN"]
            assert any(lo + SOLAR["RING_GAP"] - 0.1 <= bl["r"] - bl["w"] / 2 and bl["r"] + bl["w"] / 2 + SOLAR["RING_GAP"] - 0.1 <= hi
                       for lo, hi in gaps), (s["sun"], bl, gaps)
            assert (bl["cx"], bl["cy"]) == (s["cx"], s["cy"])
        else:
            assert len(s["planets"]) < SOLAR["BELT_MIN"]


def _assert_core_and_drifters(plan, times):
    """The galactic core (2+ systems) clears every body at every sampled
    moment and every system's disc, and keeps the world-edge margin; a
    drifting comet's path keeps clear of every system and the core."""
    W, H, M = plan["world"]["w"], plan["world"]["h"], SOLAR["MARGIN"]
    core = plan.get("core")
    assert (core is None) == (len(plan["systems"]) < 2)
    if core:
        r = core["r"]
        assert M <= core["x"] - r and core["x"] + r <= W - M and M <= core["y"] - r and core["y"] + r <= H - M
        for s in plan["systems"]:
            assert math.hypot(core["x"] - s["cx"], core["y"] - s["cy"]) >= s["R"] + r + SOLAR["CORE_GAP"] - 0.5
        for t in times:
            for i, (x, y, rad) in _circles_at(plan, t).items():
                assert math.hypot(core["x"] - x, core["y"] - y) >= rad + r + SOLAR["CORE_GAP"] - 0.5, (t, i)
    for d in plan["drifters"]:
        pts = d["path"]
        assert len(pts) >= 2 and isinstance(d["seed"], int)
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            for s in plan["systems"]:
                assert _seg_dist(s["cx"], s["cy"], x1, y1, x2, y2) >= s["R"] + SOLAR["DRIFT_CLEAR"] - 0.5
            if core:
                assert _seg_dist(core["x"], core["y"], x1, y1, x2, y2) >= core["r"] + SOLAR["DRIFT_CLEAR"] - 0.5


def _assert_systems_apart(plan):
    ss = plan["systems"]
    for i, a in enumerate(ss):
        for b in ss[i + 1:]:
            if plan["style"] == "orbit":
                # a whole system may turn about its sun: its disc is what it needs
                assert math.hypot(a["cx"] - b["cx"], a["cy"] - b["cy"]) >= a["R"] + b["R"] + SOLAR["SYS_GAP"] - 0.5
            else:
                ax0, ay0, ax1, ay1 = a["bbox"]
                bx0, by0, bx1, by1 = b["bbox"]
                sep = max(bx0 - ax1, ax0 - bx1, by0 - ay1, ay0 - by1)
                assert sep >= SOLAR["SYS_GAP"] - 0.5, (a["sun"], b["sun"], sep)


def _assert_margins(plan):
    W, H, M = plan["world"]["w"], plan["world"]["h"], SOLAR["MARGIN"]
    for i, n in plan["nodes"].items():
        r = n["d"] / 2
        assert M - 0.01 <= n["x"] - r and n["x"] + r <= W - M + 0.01, i
        assert n["y"] - r >= SOLAR["TOP"] - 0.01 and n["y"] + r <= H - M, i
    if plan["style"] == "orbit":
        for s in plan["systems"]:
            assert s["cx"] - s["R"] >= M - 0.01 and s["cx"] + s["R"] <= W - M + 0.01
            assert s["cy"] - s["R"] >= SOLAR["TOP"] - 0.01 and s["cy"] + s["R"] <= H - M


def _assert_spokes_clear(plan):
    """Spoke style: every spoke (child → what it orbits) clear of every other
    circle, unless the plan says it could not be."""
    N = plan["nodes"]
    excused = {w.split(": no clear line from ")[1].split(" ")[0]
               for w in plan["warnings"] if ": no clear line from " in w}
    for i, n in N.items():
        if n["role"] == "sun" or i in excused:
            continue
        par = N[n["parent"]]
        for j, o in N.items():
            if j in (i, n["parent"]):
                continue
            d = _seg_dist(o["x"], o["y"], n["x"], n["y"], par["x"], par["y"])
            assert d >= o["d"] / 2 + SOLAR["SPOKE_CLEAR"] - 0.5, (i, n["parent"], j, d)


def _assert_t0_matches(plan):
    c = _circles_at(plan, 0)
    for i, n in plan["nodes"].items():
        assert c[i][0] == pytest.approx(n["x"], abs=0.02) and c[i][1] == pytest.approx(n["y"], abs=0.02), i


def _check(plan, times=(0, 7.3, 21.0, 44.4, 63.1, 97.7, 140.2, 333.3)):
    _assert_t0_matches(plan)
    _assert_systems_apart(plan)
    _assert_margins(plan)
    if plan["style"] == "orbit":
        _assert_annuli(plan)
        for t in times:
            assert not _overlaps(_circles_at(plan, t)), t
    else:
        assert not _overlaps(_circles_at(plan, 0))
        _assert_spokes_clear(plan)
        assert plan["belts"] == [] and plan["drifters"] == []
    _assert_core_and_drifters(plan, times[:3])


# ── geometry ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("style", ["orbit", "spoke"])
@pytest.mark.parametrize("shape", [civpro_shape, torts_shape])
def test_law_outlines_have_no_overlaps_and_keep_the_margins(shape, style):
    b, nodes = shape(style)
    plan = solar_plan(b, nodes)
    _check(plan)
    assert set(plan["nodes"]) == {n.id for n in nodes}
    assert len(plan["systems"]) == len(b.acts)


@pytest.mark.parametrize("style", ["orbit", "spoke"])
@pytest.mark.parametrize("planets", [1, 2, 3, 5, 8, 12])
@pytest.mark.parametrize("moons", [0, 1, 2, 3, 5, 8])
def test_any_count_of_planets_and_moons_fits(planets, moons, style):
    b, nodes = _outline([[[0] * moons for _ in range(planets)]], style)
    plan = solar_plan(b, nodes)
    _check(plan, times=(0, 13.7, 55.5, 120.9))


@pytest.mark.parametrize("style", ["orbit", "spoke"])
def test_uneven_families_with_satellites(style):
    units = [[[3, 0, 1], [], [0] * 8, [2, 2, 2, 2, 2], [1], [0, 0, 0, 0, 0, 0, 0, 0], [4], [0, 6]],
             [[1]], [], [[0, 0], [8]]]
    b, nodes = _outline(units, style)
    _check(solar_plan(b, nodes))


def test_planets_take_the_rings_in_outline_order_and_moons_share_one_ring():
    b, nodes = civpro_shape()
    plan = solar_plan(b, nodes)
    for a, s in enumerate(plan["systems"]):
        assert s["unit"] == a and s["sun"] == f"u{a + 1}"
        assert [p["id"] for p in s["planets"]] == [f"u{a + 1}-p{k + 1}" for k in range(len(CIVPRO[a]))]
        assert [p["ring"] for p in s["planets"]] == list(range(1, len(s["planets"]) + 1))
        rs = [p["r"] for p in s["planets"]]
        assert rs == sorted(rs) and len(set(rs)) == len(rs)
        for p in s["planets"]:
            assert len({m["r"] for m in p["moons"]}) <= 1
            # evenly spaced round the planet
            angs = sorted(m["a0"] for m in p["moons"])
            if len(angs) > 1:
                steps = [b_ - a_ for a_, b_ in zip(angs, angs[1:])] + [angs[0] + 2 * math.pi - angs[-1]]
                assert max(steps) - min(steps) < 1e-3


def test_an_order_hint_reorders_the_rings():
    b, nodes = civpro_shape()
    b.placement = {"u1-p3": {"order": 1}}
    place(b, nodes)
    plan = solar_plan(b, nodes)
    assert plan["systems"][0]["planets"][0]["id"] == "u1-p3"


def test_a_body_grows_with_its_children_and_the_tiers_keep_their_order():
    T = SOLAR["TIERS"]
    # a tier per two children, clamped below the bump-only top of each ladder
    assert [body_d("planet", m) for m in range(10)] == [96, 110, 110, 124, 124, 138, 138, 152, 152, 152]
    assert [body_d("moon", k) for k in range(8)] == [50, 58, 58, 66, 66, 74, 74, 74]
    assert body_d("sat", 0) == 34 and body_d("sat", 0, True) == 40
    assert body_d("planet", 99, True) == T["planet"][-1] == 166
    assert body_d("moon", 99, True) == T["moon"][-1] == 82
    # sun > every planet > every moon > every satellite, bumps included
    assert SOLAR["D"]["sun"] > max(T["planet"]) and min(T["planet"]) > max(T["moon"]) > max(T["sat"])


def test_sizes_follow_child_counts_and_an_extreme_flag_bumps_one_tier():
    b, nodes = _outline([[[0] * 7, [0], [], [5, 0, 1]], [[2]]],
                        flags=[{"id": "pivotal", "name": "Pivotal"},
                               {"id": "imp", "name": "Extreme importance"},
                               {"id": "key-case", "name": "Key case"}])
    by = {n.id: n for n in nodes}
    by["u1-p2"].flags = ["pivotal"]
    by["u1-p3"].flags = ["key-case"]                   # not an extreme flag: no bump
    by["u1-p4-m1"].flags = ["imp"]
    by["u2-p1-m1-s1"].flags = ["pivotal"]
    plan = solar_plan(b, nodes)
    d = {i: n["d"] for i, n in plan["nodes"].items()}
    assert d["u1"] == d["u2"] == SOLAR["D"]["sun"]
    assert d["u1-p1"] == 152                           # 7 moons
    assert d["u1-p2"] == 124                           # 1 moon (110) + pivotal
    assert d["u1-p3"] == 96                            # no moons; "key case" is no bump
    assert d["u1-p4"] == 124                           # 3 moons
    assert d["u1-p4-m1"] == 82                         # 5 satellites (74) + extreme importance
    assert d["u1-p4-m2"] == 50 and d["u1-p4-m3"] == 58
    assert d["u2-p1-m1-s1"] == 40 and d["u2-p1-m1-s2"] == 34
    assert plan["sizes"]["bump"] == ["imp", "pivotal"]
    # the systems' bodies carry the same diameters as the nodes
    for s in plan["systems"]:
        for p in s["planets"]:
            assert p["d"] == d[p["id"]]
            for m in p["moons"]:
                assert m["d"] == d[m["id"]] and all(q["d"] == d[q["id"]] for q in m["sats"])
    _check(plan)


@pytest.mark.parametrize("style", ["orbit", "spoke"])
def test_twelve_planets_of_eight_moons_all_at_the_largest_sizes(style):
    """The heaviest case: every planet at the top of its ladder (bumped), every
    moon too, satellites bumped — still no overlap anywhere."""
    units = [[[5, 0, 6, 1, 2, 0, 3, 4] for _ in range(12)]]
    flags = [{"id": "pivotal", "name": "Pivotal"}]
    b, nodes = _outline(units, style, flags=flags)
    for n in nodes:
        if n.parent:
            n.flags = ["pivotal"]
    plan = solar_plan(b, nodes)
    assert {n["d"] for n in plan["nodes"].values() if n["role"] == "planet"} == {166}
    assert max(n["d"] for n in plan["nodes"].values() if n["role"] == "moon") == 82
    _check(plan, times=(0, 31.0, 77.7))


def test_orbit_periods_inner_faster_and_spoke_still():
    b, nodes = civpro_shape("orbit")
    plan = solar_plan(b, nodes)
    for s in plan["systems"]:
        ps = [p["period"] for p in s["planets"]]
        assert ps == sorted(ps) and all(90 <= p <= 150 for p in ps)
        for p in s["planets"]:
            for m in p["moons"]:
                assert 30 <= m["period"] <= 50
                assert all(q["period"] > 0 for q in m["sats"])
    b, nodes = civpro_shape("spoke")
    plan = solar_plan(b, nodes)
    bodies = [x for s in plan["systems"] for p in s["planets"]
              for x in [p] + p["moons"] + [q for m in p["moons"] for q in m["sats"]]]
    assert bodies and all(x["period"] == 0 for x in bodies)
    assert plan["style"] == "spoke"


def test_spoke_is_more_compact_than_orbit():
    for shape in (civpro_shape, torts_shape):
        o = solar_plan(*shape("orbit"))
        s = solar_plan(*shape("spoke"))
        assert sum(x["R"] for x in s["systems"]) < sum(x["R"] for x in o["systems"])
        assert s["world"]["h"] < o["world"]["h"]


def test_small_systems_sit_side_by_side_and_wrap_to_rows():
    b, nodes = _outline([[[]] for _ in range(5)], "orbit")
    plan = solar_plan(b, nodes)
    rows = {}
    for s in plan["systems"]:
        rows.setdefault(s["cy"], []).append(s)
    assert plan["world"]["w"] == SOLAR["WORLD_W"]
    assert len(rows) >= 2 and max(len(r) for r in rows.values()) >= 2
    # left to right, then down, in unit order
    order = sorted(plan["systems"], key=lambda s: (s["cy"], s["cx"]))
    assert [s["unit"] for s in order] == list(range(5))
    assert plan["sun_links"] == [[f"u{a}", f"u{a + 1}"] for a in range(1, 5)]
    _check(plan)


def test_a_system_too_wide_for_the_world_widens_it_and_keeps_the_margin():
    b, nodes = _outline([[[0, 0, 0]] * 9, [[0]]], "orbit")
    plan = solar_plan(b, nodes)
    assert plan["world"]["w"] > SOLAR["WORLD_W"]
    _check(plan)


def test_the_plan_is_pure_and_deterministic():
    b, nodes = torts_shape("spoke")
    before = copy.deepcopy([vars(n) for n in nodes])
    p1 = json.dumps(solar_plan(b, nodes), sort_keys=True)
    p2 = json.dumps(solar_plan(copy.deepcopy(b), copy.deepcopy(nodes)), sort_keys=True)
    assert p1 == p2
    assert [vars(n) for n in nodes] == before


def test_the_contract_shape():
    b, nodes = _outline([[[1, 0], []], [[0]]])
    plan = solar_plan(b, nodes)
    assert plan["style"] in ("orbit", "spoke") and set(plan["world"]) == {"w", "h"}
    s = plan["systems"][0]
    assert {"unit", "sun", "cx", "cy", "r_sun", "planets"} <= set(s)
    p = s["planets"][0]
    assert {"id", "ring", "r", "a0", "d", "period", "moons"} <= set(p)
    m = p["moons"][0]
    assert {"id", "r", "a0", "d", "period", "sats"} <= set(m)
    q = m["sats"][0]
    assert {"id", "r", "a0", "d", "period"} <= set(q)
    assert {plan["nodes"][i]["role"] for i in plan["nodes"]} == {"sun", "planet", "moon", "sat"}
    assert all({"x", "y", "d", "role"} <= set(v) for v in plan["nodes"].values())
    assert plan["sun_links"] == [["u1", "u2"]]
    json.dumps(plan)


# ── validation ─────────────────────────────────────────────────────────────

def test_a_fifth_level_is_an_error_that_says_how_to_fix_it():
    b, nodes = _outline([[[1]], [[0]]])
    nodes.append(Node(id="too-deep", act=0, tag="Concept", title="Too deep", desc="d",
                      parent="u1-p1-m1-s1"))
    with pytest.raises(BriefError) as e:
        validate_nodes(b, nodes)
    msg = str(e.value)
    assert "too-deep" in msg and "u1 → u1-p1 → u1-p1-m1 → u1-p1-m1-s1 → too-deep" in msg
    assert "four" in msg and "satellites" in msg and "Restructure" in msg
    # the same outline as a tree is fine: only solar has four levels
    b.layout = "tree"
    validate_nodes(b, nodes)


def test_hub_and_spoke_is_an_outline_with_a_first_look():
    b, _ = _outline([[[0]], [[0]]])
    validate_brief(b)
    assert b.hub_look == "plain" and solar_style(b) == "spoke"
    b.hub_look = "stars"
    assert solar_style(b) == "orbit"
    b.hub_look = "galaxy"
    with pytest.raises(BriefError, match="hub_look"):
        validate_brief(b)
    b.hub_look = "stars"
    b.mode = "linear"
    with pytest.raises(BriefError, match="solar"):
        validate_brief(b)
    b.mode = "palace"
    with pytest.raises(BriefError, match="layout 'solar' needs mode 'outline'"):
        validate_brief(b)
    assert Brief(title="t").hub_look == "stars"           # the Star chart look is the default
    assert Brief(title="t").palace_view == "city" and "stash" not in Brief.__dataclass_fields__   # (palace_view: city | building)


def test_one_system_for_the_whole_outline_is_one_unit():
    b, nodes = _outline([[[1, 0], [0]]])
    assert len(b.acts) == 1
    plan = solar_plan(b, nodes)
    assert len(plan["systems"]) == 1 and plan["sun_links"] == []
    b.layout = "tree"
    with pytest.raises(BriefError, match="at least 2"):
        validate_brief(b)


def test_one_root_per_unit_still_holds_for_a_tree_but_a_hub_may_have_several_suns():
    b, nodes = _outline([[[0]], [[0]]])
    nodes.append(Node(id="second-sun", act=0, tag="Unit", title="x", desc="d"))
    validate_nodes(b, nodes)                       # Hub & spoke: a second system in unit 1
    b.layout = "tree"
    with pytest.raises(BriefError, match="one hub"):
        validate_nodes(b, nodes)


def test_auto_never_picks_solar():
    for shape in (civpro_shape, torts_shape):
        b, nodes = shape()
        for lay in ("auto", "tree", "flow"):
            b.layout = lay
            assert run_layout(b, nodes, [])[5]["layout"] in ("tree", "flow")


def test_placement_other_than_order_is_warned_about():
    b, nodes = _outline([[[0]], [[0]]])
    b.placement = {"u1-p1": {"x": 400}}
    assert any("solar" in w and "order" in w for w in validate_brief(b))


# ── the build ──────────────────────────────────────────────────────────────

def _sample(style="spoke"):
    """The sample outline as a Hub & spoke opening plain ("spoke") or in the
    Star chart look ("orbit")."""
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    d["brief"]["layout"] = "solar"
    d["brief"]["hub_look"] = "plain" if style == "spoke" else "stars"
    return d


def _solar(html):
    """window._ALTO_SOLAR as the page has it: {look, looks}, with the first
    look's plan spread over the top level (as the page's spread does)."""
    at = html.index("window._ALTO_SOLAR=") + len("window._ALTO_SOLAR=")
    assert html[at:].startswith("(function(S){")
    at = html.index(")(", at) + 2
    S, _ = json.JSONDecoder().raw_decode(html[at:])
    out = dict(S)
    for k, v in S["looks"][S["look"]].items():
        out.setdefault(k, v)
    return out


def test_run_layout_puts_every_centre_where_the_plan_says():
    b, nodes = civpro_shape()
    positions, heights, world_h, mgrid, mobile_h, rep = run_layout(b, nodes, [])
    plan = solar_plan(b, nodes)
    assert rep["layout"] == "solar" and world_h == plan["world"]["h"]
    assert rep["solar"]["systems"][0]["planets"] == len(CIVPRO[0])
    for i, n in plan["nodes"].items():
        assert positions[i] == pytest.approx(n["y"]) and heights[i] == n["d"]
    tp = solar_tree_plan(plan, nodes)
    # through the float ops, whatever height the page measures
    tall = {i: h + 37 for i, h in solar_heights(plan).items()}
    y, x, _ = run_plan(tp, nodes, tall)
    for i, n in plan["nodes"].items():
        assert y[i] == pytest.approx(n["y"]) and x[i] == pytest.approx(n["x"])
    assert set(mgrid) == {n.id for n in nodes}          # phones keep their column of cards


@pytest.mark.parametrize("style", ["orbit", "spoke"])
def test_build_embeds_both_looks_and_the_first_looks_positions(style):
    b, nodes, conns = load_brief(_sample(style))
    html, report = build_timeline(b, nodes, conns)
    assert report["layout"]["layout"] == "solar" and report["layout"]["solar"]["style"] == style
    assert report["layout"]["solar"]["other_look"]["style"] == ("spoke" if style == "orbit" else "orbit")
    assert html.count("window._ALTO_SOLAR=") == 1
    S = _solar(html)
    look = "plain" if style == "spoke" else "stars"
    assert S["look"] == look and set(S["looks"]) == {"stars", "plain"}
    assert S["looks"]["stars"]["style"] == "orbit" and S["looks"]["plain"]["style"] == "spoke"
    # the single-plan keys, readable as before: the first look's
    assert S["style"] == style and len(S["systems"]) == 5 and S["nodes"] == S["looks"][look]["nodes"]
    # both looks are the plans solar.py makes, to 0.1 px
    for lk, st in (("stars", "orbit"), ("plain", "spoke")):
        want = solar_plan(b, nodes, st)
        for i, n in want["nodes"].items():
            got = S["looks"][lk]["nodes"][i]
            assert abs(got["x"] - n["x"]) <= 0.051 and abs(got["y"] - n["y"]) <= 0.051 and got["d"] == n["d"]
    assert "window._ALTO_TREE_PLAN=" in html and '"mid"]' in html
    assert "window._altoTreeCalc" in html
    assert "window._ALTO_OUTLINE=" in html and "window._ALTO_PALACE=" not in html     # path numbers


def test_a_tree_page_has_no_solar_plan():
    d = _sample()
    d["brief"]["layout"] = "tree"
    html, _ = build_timeline(*load_brief(d))
    assert "window._ALTO_SOLAR=" not in html


@needs_node
def test_the_page_puts_each_centre_where_the_plan_says(tmp_path):
    b, nodes = torts_shape("spoke")
    plan = solar_plan(b, nodes)
    tp = solar_tree_plan(plan, nodes)
    h = {i: d + (len(i) % 5) * 9 for i, d in solar_heights(plan).items()}   # measured ≠ diameter
    acts = [[n.id for n in nodes if n.act == a] for a in range(len(b.acts))]
    js = ("var window=globalThis; var document={documentElement:{classList:{contains:function(){return false;}}},"
          "getElementById:function(){return null;}};\n"
          f"var ACT_SEQS={json.dumps(acts)}; var NODES={json.dumps([{'id': n.id} for n in nodes])};\n"
          f"var NODE_ACT={json.dumps({n.id: n.act for n in nodes})};\n"
          "window._ALTO_OUTLINE={kids:{},parent:" + json.dumps({n.id: n.parent for n in nodes if n.parent}) + "};\n"
          + dx.tree_glue(plan_js(tp)) + "\n"
          f"var pos={{}}, h={json.dumps(h)}; window._altoTree(pos,h);\n"
          "console.log(JSON.stringify({y:pos, x:Object.fromEntries(NODES.map(function(n){return [n.id,n.displayX];}))}));")
    f = tmp_path / "solar.js"
    f.write_text(js, encoding="utf-8")
    out = json.loads(subprocess.check_output([NODE, str(f)], timeout=60))
    for i, n in plan["nodes"].items():
        assert out["y"][i] == pytest.approx(n["y"]) and out["x"][i] == pytest.approx(n["x"]), i


@pytest.fixture
def store(tmp_path):
    from alto import mcp_server as srv
    from alto.store.local import LocalStore
    srv.set_store(LocalStore(tmp_path))
    yield srv
    srv.set_store(None)


def _draft(srv, d):
    pid = srv.create_project("Law School", "1L", "studying")["project_id"]
    tid = srv.create_timeline(pid, d["brief"])["timeline_id"]
    srv.record_materials_consent(tid, [{"name": "notes.pdf", "kind": "notes", "id": "notes"}], True)
    srv.set_entities(tid, d["brief"].get("entities") or [])
    assert "error" not in srv.add_nodes(tid, d["nodes"])
    if d.get("connections"):
        assert "error" not in srv.add_connections(tid, d["connections"])
    return tid


def test_build_and_preview_through_the_tools_on_a_scratch_store(store):
    srv = store
    tid = _draft(srv, _sample("spoke"))
    pre = srv.run_layout_preview(tid)
    assert pre.get("layout") == "solar" and pre["solar"]["style"] == "spoke", pre
    pre = srv.run_layout_preview(tid, layout="tree")
    assert pre.get("layout") == "tree", pre
    out = srv.build_timeline(tid)
    assert "error" not in out, out
    html = srv.get_store().get_artifact(srv.uid(), tid, "timeline.html")
    assert "window._ALTO_SOLAR=" in html


# ── several suns in a unit ───────────────────────────────────────────────────

@pytest.mark.parametrize("districts", [
    [[[[0, 0], [1]], [[2, 2]]], [[[0]], [[0, 0, 0]], [[]]]],                 # 2 + 3 roots
    [[[[0] * 8] * 12, [[3]]], [[[0]]]],                                         # a 12×8 system beside a small one
    [[[[]] for _ in range(7)]],                                                 # one unit of seven small systems
    [[[[2, 2, 2]] * 3] * 3, [[[1, 0]] * 2] * 2],                               # many mid-size systems
])
def test_every_root_is_a_sun_and_no_two_bodies_ever_touch(districts):
    b, nodes = _stars(districts)
    for style in ("orbit", "spoke"):
        plan = solar_plan(b, nodes, style)
        assert plan["style"] == style
        suns = [s["sun"] for s in plan["systems"]]
        assert suns == [n.id for n in nodes if not n.parent]
        assert len(plan["systems"]) == sum(len(d) for d in districts)
        _check(plan, times=(0, 19.9, 66.6, 123.4))
        # a unit's systems stay together: each unit its own rows, in order
        by_unit = {}
        for s in plan["systems"]:
            by_unit.setdefault(s["unit"], []).append(s)
        lows = [max(s["bbox"][3] for s in by_unit[u]) for u in sorted(by_unit)]
        highs = [min(s["bbox"][1] for s in by_unit[u]) for u in sorted(by_unit)]
        assert all(lows[i] < highs[i + 1] for i in range(len(lows) - 1))
        assert [u["suns"] for u in plan["units"]] == [[s["sun"] for s in by_unit[u]] for u in sorted(by_unit)]


def test_an_outline_with_one_root_per_unit_keeps_its_plan():
    b, nodes = civpro_shape("spoke")
    plan = solar_plan(b, nodes)
    assert [s["sun"] for s in plan["systems"]] == [f"u{a + 1}" for a in range(len(CIVPRO))]
    assert [u["suns"] for u in plan["units"]] == [[f"u{a + 1}"] for a in range(len(CIVPRO))]


# ── black holes, comets, asteroids, belts, the core ─────────────────────────

CIVPRO_FLAGS = [{"id": "pivotal", "name": "Pivotal"}, {"id": "not-tested", "name": "Not tested"},
                {"id": "background", "name": "Background"}, {"id": "overruled", "name": "Overruled"},
                {"id": "revisit", "name": "Revisit"}]


def _flagged(units, style, every=("pivotal", "not-tested", "background", "overruled", "revisit", "")):
    """units with the user's flags dealt round the nodes (one each, in turn)."""
    b, nodes = _outline(units, style, flags=CIVPRO_FLAGS)
    for k, n in enumerate(nodes):
        f = every[k % len(every)]
        n.flags = [f] if f else []
    return b, nodes


def test_flags_make_black_holes_comets_and_asteroids_first_match_wins():
    from alto.build.solar import LOOK_FLAGS, look_flags, node_looks
    flags = [{"id": "x1", "name": "Dead_Letter"}, {"id": "bh", "name": "Black Hole"}, {"id": "oq", "name": "Open_Question"},
             {"id": "minor", "name": "Aside"}, {"id": "pivotal", "name": "Pivotal"}, {"id": "keycase", "name": "Key case"}]
    b, nodes = _outline([[[0, 0], [0]], [[0]]], flags=flags)
    assert look_flags(b) == {"x1": "blackhole", "bh": "blackhole", "oq": "comet", "minor": "asteroid"}
    assert [lk for lk, _ in LOOK_FLAGS] == ["blackhole", "comet", "asteroid"]
    by = {n.id: n for n in nodes}
    by["u1-p1"].flags = ["minor", "oq", "x1"]                   # all three: the black hole wins
    by["u1-p2"].flags = ["minor", "oq"]                         # comet over asteroid
    by["u1-p1-m1"].flags = ["keycase", "pivotal"]               # no look; pivotal bumps the size
    assert node_looks(b, nodes) == {"u1-p1": "blackhole", "u1-p2": "comet"}
    for style in ("orbit", "spoke"):
        plan = solar_plan(b, nodes, style)
        N = plan["nodes"]
        assert N["u1-p1"]["look"] == "blackhole" and N["u1-p2"]["look"] == "comet" and "look" not in N["u1-p1-m1"]
        assert N["u1-p1"]["role"] == "planet" and N["u1-p1-m1"]["parent"] == "u1-p1"   # children still orbit it
        assert N["u1-p1-m1"]["d"] == body_d("moon", 0, True)
        assert plan["looks"] == {"blackhole": ["u1-p1"], "comet": ["u1-p2"]}
        assert ("orbit" in N["u1-p2"]) == (style == "orbit")         # only the moving look has an ellipse


def test_comets_have_fixed_eccentric_orbits_and_asteroids_tumble():
    b, nodes = _flagged(CIVPRO, "orbit")
    plan = solar_plan(b, nodes)
    N = plan["nodes"]
    comets = [i for i, n in N.items() if n.get("look") == "comet" and n["role"] != "sun"]   # (a sun has no orbit)
    rocks = [i for i, n in N.items() if n.get("look") == "asteroid"]
    assert comets and rocks
    for i in comets:
        o = N[i]["orbit"]
        assert set(o) == {"e", "rot", "k"} and 0 <= o["rot"] < 2 * math.pi + 1e-9
        assert o["k"] == (1 if N[i]["role"] == "planet" else 0)
        if N[i]["role"] == "planet":
            assert SOLAR["ECC"][0] - 1e-9 <= o["e"] <= SOLAR["ECC"][1] + 1e-9
        else:
            assert 0 < o["e"] <= SOLAR["ECC"][1] + 1e-9     # a crowded ring may flatten it
    for i in rocks:
        assert SOLAR["TUMBLE"][0] - 1e-9 <= abs(N[i]["tumble"]) <= SOLAR["TUMBLE"][1] + 1e-9
    assert all("tumble" not in n for i, n in N.items() if i not in rocks)
    # fixed per node: the same id gives the same orbit in another outline
    b2, nodes2 = _flagged(CIVPRO[:3], "orbit")
    p2 = solar_plan(b2, nodes2)
    same = [i for i in comets if i in p2["nodes"] and p2["nodes"][i].get("orbit")]
    assert same and all(p2["nodes"][i]["orbit"] == N[i]["orbit"] for i in same)


@pytest.mark.parametrize("units", [CIVPRO, TORTS, [[[0] * 8] * 12], [[[2] * 8] * 12, [[1]]],
                                   [[[0]] * 4, [[3, 3]] * 5, [[]] * 9]])
def test_flagged_charts_keep_every_proof_at_every_moment(units):
    for style in ("orbit", "spoke"):
        for every in (("revisit",), ("revisit", "not-tested", "overruled", ""), ("pivotal", "revisit")):
            b, nodes = _flagged(units, style, every)
            _check(solar_plan(b, nodes), times=(0, 11.1, 37.7, 71.3, 140.9, 260.0))


def test_a_belt_runs_between_the_inner_and_outer_planets_of_a_big_system():
    b, nodes = _outline([[[0]] * 6, [[0]] * 3], "orbit")
    plan = solar_plan(b, nodes)
    assert [bl["sun"] for bl in plan["belts"]] == ["u1"]
    bl = plan["belts"][0]
    s = plan["systems"][0]
    # between planet 3's band and planet 4's (6 planets: the belt after the first half)
    p3, p4 = s["planets"][2], s["planets"][3]
    assert p3["r"] + p3["e"] < bl["r"] - bl["w"] / 2 and bl["r"] + bl["w"] / 2 < p4["r"] - p4["e"]
    assert 40 <= bl["n"] <= 400 and isinstance(bl["seed"], int)
    assert solar_plan(b, nodes, "spoke")["belts"] == []


def test_the_core_sits_among_the_suns_and_a_single_system_has_none():
    b, nodes = _outline([[[0]], [[0]], [[0]], [[0]]], "orbit")
    plan = solar_plan(b, nodes)
    core = plan["core"]
    ys = [s["cy"] for s in plan["systems"]]
    assert min(ys) <= core["y"] <= max(ys) and core["r"] == SOLAR["CORE_R"]     # among the suns, not below them
    _assert_core_and_drifters(plan, (0, 33.3))
    one = solar_plan(*_outline([[[0], [1]]], "orbit"))
    assert "core" not in one
    # two systems side by side with no room between: the world grows for it
    b, nodes = _outline([[[0] * 3] * 3, [[0] * 3] * 3], "orbit")
    plan = solar_plan(b, nodes)
    _assert_core_and_drifters(plan, (0, 50.0))
    assert plan["drifters"]


def test_flagged_plans_are_deterministic():
    b, nodes = _flagged(TORTS, "orbit")
    assert json.dumps(solar_plan(b, nodes), sort_keys=True) == json.dumps(
        solar_plan(copy.deepcopy(b), copy.deepcopy(nodes)), sort_keys=True)


# ── the page ─────────────────────────────────────────────────────────────────

def _civpro_page(look="stars"):
    from alto.build.builder import load_brief as lb
    b, nodes = _flagged(CIVPRO, "orbit" if look == "stars" else "spoke")
    d = {"brief": {"title": "Civ Pro", "timeline_id": "civ-pro", "mode": "outline", "layout": "solar",
                   "hub_look": look, "columns": 5, "flags": CIVPRO_FLAGS,
                   "acts": [{"label": a.label, "short": a.short} for a in b.acts],
                   "relations": [{"key": "spine", "label": "Contains"}]},
         "nodes": [{"id": n.id, "act": n.act, "tag": n.tag, "title": n.title,
                    "desc": "What the notes say about " + n.title + ": the rule, the test and the cases.",
                    "parent": n.parent, "flags": n.flags} for n in nodes]}
    return build_timeline(*lb(d))


def test_a_civ_pro_page_with_both_looks_is_far_under_the_stored_page_cap():
    from alto.build.private_shell import MAX_PAGE_BYTES, stored_bytes
    from alto.build.single_file import private_page
    html, report = _civpro_page()
    at = html.index("window._ALTO_SOLAR=")
    blob = html[at:html.index(";\n", at)]
    import gzip
    assert len(gzip.compress(blob.encode())) < 60_000, len(gzip.compress(blob.encode()))
    b = load_brief({"brief": {"title": "Civ Pro", "timeline_id": "civ-pro", "acts": [{"label": "x"}]}})[0]
    stored = stored_bytes(private_page(b, html))
    assert stored < MAX_PAGE_BYTES * 0.6, stored
    S = _solar(html)
    assert S["looks"]["stars"].get("core") and S["looks"]["stars"]["belts"]
    assert any(n.get("look") == "comet" and n.get("orbit") for n in S["looks"]["stars"]["nodes"].values())


# ── a 1.9.105 Star chart (a Mind Palace in its stars view) loads as Hub & spoke ─

def _palace_star_chart():
    """A stored 1.9.105 Star chart: the shape of Luke's torts-star-chart —
    mode palace + palace_view stars, districts of buildings (two in one),
    floors and parts as planets / moons / satellites, flags, sections, chips,
    sources, a city kept aside, palace placement (a floor's order), and the
    stash convert_timeline left."""
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    br = d["brief"]
    br.update({"mode": "palace", "palace_view": "stars", "node_noun": "Building", "period_noun": "District",
               "flags": [{"id": "pivotal", "name": "Pivotal"}, {"id": "overruled", "name": "Overruled"}],
               "palace": {"place": "Philadelphia", "data_z": "xz2:CITY"},
               "stash": {"outline": {"tree_lines": "trunk", "outcomes": "beside"},
                         "palace": {"palace_view": "city"}}})
    root0 = next(n["id"] for n in d["nodes"] if n["act"] == 0 and not n.get("parent"))
    kid = next(n["id"] for n in d["nodes"] if n.get("parent") == root0)
    br["placement"] = {kid: {"order": 1, "lot": "12.3"}}
    d["nodes"].insert(1, {"id": "second-building", "act": 0, "tag": "Building", "title": "Second building",
                          "desc": "Another building in the first district.", "flags": ["overruled"],
                          "sections": [{"h": "From your notes", "t": "Kept word for word.", "prov": "notes"}]})
    d["nodes"].insert(2, {"id": "second-floor", "act": 0, "tag": "Floor", "title": "A floor",
                          "desc": "On the second building.", "parent": "second-building", "flags": ["pivotal"]})
    return d


def test_a_palace_star_chart_loads_as_hub_and_spoke_with_everything_kept():
    from alto.build.brief import migrate_brief
    d = _palace_star_chart()
    before = copy.deepcopy(d)
    b, nodes, conns = load_brief(d)
    assert d == before                                       # the stored bundle is not touched
    assert (b.mode, b.layout, b.hub_look) == ("outline", "solar", "stars")
    assert b.palace == {} and b.tree_lines == "trunk" and b.outcomes == "beside"
    assert b.placement == {next(iter(before["brief"]["placement"])): {"order": 1}}
    # every node exactly as stored: ids, parents, flags, sections, chips, sources
    want = {n["id"]: n for n in before["nodes"]}
    assert [n.id for n in nodes] == [n["id"] for n in before["nodes"]]
    for n in nodes:
        w = want[n.id]
        assert (n.act, n.parent, n.title, n.desc, n.tag) == (w["act"], w.get("parent", ""), w["title"], w["desc"], w["tag"])
        assert n.flags == w.get("flags", []) and n.entity_ids == w.get("entity_ids", [])
        assert n.axis1_values == w.get("axis1_values", []) and n.axis2_values == w.get("axis2_values", [])
        assert n.sources == w.get("sources", [])
        assert [(x.h, x.t, x.prov) for x in n.sections] == [(x["h"], x["t"], x.get("prov", "")) for x in w.get("sections", [])]
    assert [e.id for e in b.entities] == [e["id"] for e in before["brief"]["entities"]]
    assert [len(a.values) for a in b.axes] == [len(a["values"]) for a in before["brief"]["axes"]]
    # what an outline cannot hold is handed back, not dropped
    _, aside = migrate_brief(before["brief"])
    assert aside["palace"] == {"place": "Philadelphia", "data_z": "xz2:CITY"}
    assert aside["placement"] == {next(iter(before["brief"]["placement"])): {"lot": "12.3"}}
    assert aside["stash_palace"] == {"palace_view": "city"}
    # it builds, path-numbered, both looks, two suns in district 1
    html, report = build_timeline(b, nodes, conns)
    assert report["layout"]["layout"] == "solar" and "window._ALTO_PALACE=" not in html
    S = _solar(html)
    assert S["look"] == "stars" and S["units"][0]["suns"][:2] == [nodes[0].id, "second-building"]
    at = html.index("window._ALTO_OUTLINE={num:") + len("window._ALTO_OUTLINE={num:")
    num, _ = json.JSONDecoder().raw_decode(html[at:])
    assert num[nodes[0].id] == "1.a" and num["second-building"] == "1.b" and num["second-floor"].startswith("1.b.")
    assert S["nodes"]["second-building"]["look"] == "blackhole"


def test_legacy_keys_are_accepted_and_ignored():
    for extra in ({"hub_style": "spoke"}, {"hub_style": "orbit"}, {"stash": {}}, {"palace_view": "city"}):
        d = _sample("spoke")
        d["brief"].update(extra)
        b, nodes, conns = load_brief(d)
        assert b.mode == "outline"
        build_timeline(b, nodes, conns)
    d = _sample("spoke")
    d["brief"].pop("hub_look")
    d["brief"]["hub_style"] = "spoke"
    assert load_brief(d)[0].hub_look == "plain"             # the old still style opens plain
    # a city palace keeps everything, its view included (1.9.107: palace_view 'city' | 'building')
    from alto.build.brief import migrate_brief
    city = {"mode": "palace", "palace_view": "city", "palace": {"data_z": "z"}, "placement": {"a": {"lot": "1.2"}}}
    got, aside = migrate_brief(city)
    assert got == city and aside == {}


def test_the_tools_see_a_stored_star_chart_as_hub_and_spoke_and_keep_its_city(store):
    srv = store
    d = _palace_star_chart()
    st = srv.get_store()
    tid = "torts-star-chart"
    pid = srv.create_project("Law School", "1L", "studying")["project_id"]
    # stored as 1.9.105 left it (written straight to the store: create_timeline no longer makes one)
    st.put_timeline(srv.uid(), tid, {"timeline_id": tid, "project_id": pid, "brief": {**d["brief"], "timeline_id": tid},
                                      "consent": {"granted": True, "sources": [{"name": "notes.pdf", "id": "notes"}]},
                                      "status": "draft", "visibility": "private", "created": "2026-10-18"})
    st.put_nodes(srv.uid(), tid, copy.deepcopy(d["nodes"]))
    st.put_connections(srv.uid(), tid, d.get("connections") or [])
    got = srv.get_timeline(tid)
    assert got["brief"]["mode"] == "outline" and got["brief"]["layout"] == "solar"
    out = srv.build_timeline(tid)
    assert "error" not in out, out
    html = st.get_artifact(srv.uid(), tid, "timeline.html")
    assert "window._ALTO_SOLAR=" in html and "window._ALTO_PALACE=" not in html
    # a tool that saves the doc keeps what the outline cannot hold beside it
    assert "error" not in srv.set_flags(tid, d["brief"]["flags"] + [{"id": "revisit", "name": "Revisit"}])
    doc = st.get_timeline(srv.uid(), tid)
    assert doc["brief"]["mode"] == "outline" and doc["legacy"]["palace"]["data_z"] == "xz2:CITY"
    nodes_now = sorted(st.list_nodes(srv.uid(), tid), key=lambda n: n["id"])
    assert [n["id"] for n in nodes_now] == sorted(n["id"] for n in d["nodes"])
