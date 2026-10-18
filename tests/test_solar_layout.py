"""The solar outline layout (brief.layout == "solar", alto/build/solar.py):
every unit a solar system — its top concept the sun, its children planets one
to a ring in outline order, theirs moons round them, theirs satellites.

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

from alto.build.brief import Act, Brief, BriefError, Node, validate_brief, validate_nodes  # noqa: E402
from alto.build.builder import build_timeline, load_brief, place, run_layout  # noqa: E402
from alto.build import detail_extras as dx  # noqa: E402
from alto.build.layout import plan_js, run_plan  # noqa: E402
from alto.build.solar import SOLAR, body_d, solar_heights, solar_plan, solar_tree_plan  # noqa: E402

NODE = shutil.which("node") or str(Path.home() / ".local/node/bin/node")
needs_node = pytest.mark.skipif(not Path(NODE).is_file(), reason="needs node")
OUTLINE = ROOT / "samples" / "outline_brief.json"
GAP_MIN = min(SOLAR["MOON_GAP"], SOLAR["SAT_GAP"], SOLAR["RING_GAP"], SOLAR["SPOKE_GAP"]) - 0.5


# ── synthetic outlines ─────────────────────────────────────────────────────
# A unit is a list of planets; a planet a list of moons; a moon its number of
# satellites. Ids spell where a node sits: u1-p2-m3-s1.

def _outline(units, style="orbit", flags=None):
    acts = [Act(label=f"UNIT {a + 1}", short=f"Unit {a + 1}") for a in range(len(units))]
    b = Brief(title="Solar test", subject="s", mode="outline", layout="solar", hub_style=style,
              columns=5, acts=acts, timeline_id="solar-test", flags=flags or [])
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


def civpro_shape(style="orbit"):
    return _outline(CIVPRO, style)


def torts_shape(style="orbit"):
    return _outline(TORTS, style)


# ── geometry helpers ───────────────────────────────────────────────────────

def _circles_at(plan, t):
    """{id: (x, y, radius)} of every circle at time t (seconds)."""
    out, spin = {}, plan["spin"]

    def ang(body):
        return body["a0"] + (spin * 2 * math.pi * t / body["period"] if body["period"] else 0.0)
    for s in plan["systems"]:
        cx, cy = s["cx"], s["cy"]
        out[s["sun"]] = (cx, cy, s["r_sun"])
        for p in s["planets"]:
            a = ang(p)
            px, py = cx + p["r"] * math.cos(a), cy + p["r"] * math.sin(a)
            out[p["id"]] = (px, py, p["d"] / 2)
            for m in p["moons"]:
                a = ang(m)
                mx, my = px + m["r"] * math.cos(a), py + m["r"] * math.sin(a)
                out[m["id"]] = (mx, my, m["d"] / 2)
                for q in m["sats"]:
                    a = ang(q)
                    out[q["id"]] = (mx + q["r"] * math.cos(a), my + q["r"] * math.sin(a), q["d"] / 2)
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
    """Orbit: each planet's family stays within `e` of the planet, and the
    annuli [r - e, r + e] are disjoint, clear of the sun and of each other —
    so no circle of one ring can ever meet one of another, at any speed."""
    for s in plan["systems"]:
        inner = s["r_sun"]
        for p in s["planets"]:
            reach = p["d"] / 2
            for m in p["moons"]:
                mr = max([m["d"] / 2] + [q["r"] + q["d"] / 2 for q in m["sats"]])
                reach = max(reach, m["r"] + mr)
                # a moon clears its planet whatever its satellites do
                assert m["r"] - mr >= p["d"] / 2 + SOLAR["MOON_GAP"] - 0.01, (p["id"], m["id"])
                for q in m["sats"]:
                    assert q["r"] - q["d"] / 2 >= m["d"] / 2 + SOLAR["SAT_GAP"] - 0.01
            assert reach <= p["e"] + 0.01, (p["id"], reach, p["e"])
            assert p["r"] - p["e"] >= inner + SOLAR["RING_GAP"] - 0.01, (s["sun"], p["id"])
            inner = p["r"] + p["e"]
        assert inner <= s["R"] + 0.01


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


def test_solar_needs_an_outline_and_a_known_style():
    b, _ = _outline([[[0]], [[0]]])
    b.hub_style = "comet"
    with pytest.raises(BriefError, match="hub_style"):
        validate_brief(b)
    b.hub_style = "spoke"
    validate_brief(b)
    b.mode = "linear"
    with pytest.raises(BriefError, match="solar"):
        validate_brief(b)


def test_one_system_for_the_whole_outline_is_one_unit():
    b, nodes = _outline([[[1, 0], [0]]])
    assert len(b.acts) == 1
    plan = solar_plan(b, nodes)
    assert len(plan["systems"]) == 1 and plan["sun_links"] == []
    b.layout = "tree"
    with pytest.raises(BriefError, match="at least 2"):
        validate_brief(b)


def test_one_root_per_unit_still_holds():
    b, nodes = _outline([[[0]], [[0]]])
    nodes.append(Node(id="second-sun", act=0, tag="Unit", title="x", desc="d"))
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

def _sample(style="orbit"):
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    d["brief"]["layout"] = "solar"
    d["brief"]["hub_style"] = style
    return d


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
def test_build_embeds_the_plan_and_the_positions(style):
    html, report = build_timeline(*load_brief(_sample(style)))
    assert report["layout"]["layout"] == "solar"
    assert html.count("window._ALTO_SOLAR=") == 1
    at = html.index("window._ALTO_SOLAR=") + len("window._ALTO_SOLAR=")
    plan, _ = json.JSONDecoder().raw_decode(html[at:])
    assert plan["style"] == style and len(plan["systems"]) == 5
    assert "window._ALTO_TREE_PLAN=" in html and '"mid"]' in html
    assert "window._altoTreeCalc" in html


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


def test_build_and_preview_through_the_tools_on_a_scratch_store(tmp_path):
    from alto import mcp_server as srv
    from alto.store.local import LocalStore
    srv.set_store(LocalStore(tmp_path))
    try:
        d = _sample("orbit")
        pid = srv.create_project("Law School", "1L", "studying")["project_id"]
        tid = srv.create_timeline(pid, d["brief"])["timeline_id"]
        srv.record_materials_consent(tid, [{"name": "notes.pdf", "kind": "notes"}], True)
        srv.set_entities(tid, d["brief"].get("entities") or [])
        assert "error" not in srv.add_nodes(tid, d["nodes"])
        pre = srv.run_layout_preview(tid, layout="solar")
        assert pre.get("layout") == "solar", pre
        pre = srv.run_layout_preview(tid, layout="tree")
        assert pre.get("layout") == "tree", pre
        out = srv.build_timeline(tid)
        assert "error" not in out, out
        html = srv.get_store().get_artifact(srv.uid(), tid, "timeline.html")
        assert "window._ALTO_SOLAR=" in html
    finally:
        srv.set_store(None)
