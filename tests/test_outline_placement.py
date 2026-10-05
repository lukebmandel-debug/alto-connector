"""Placement hints: the author places cards one at a time (brief.placement) and
the tree follows. Defaults are untouched without hints (test_outline_tree_layout
holds that); here each hint does what it says, a bad one fails loudly, and the
page's program interpreter agrees with the builder's."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.brief import (Act, Brief, BriefError, Node, PLACE_WORLD_W,  # noqa: E402
                              validate_brief)
from alto.build import detail_extras as dx  # noqa: E402
from alto.build.builder import build_timeline, load_brief, place, run_layout  # noqa: E402
from alto.build.layout import (TREE, WORLD_W, outline_flanks, outline_kids,  # noqa: E402
                               outline_plan, outline_tree, placement_check, plan_js,
                               run_plan)

NODE = shutil.which("node") or str(Path.home() / ".local/node/bin/node")
needs_node = pytest.mark.skipif(not Path(NODE).is_file(), reason="needs node")
SAMPLE = ROOT / "samples" / "outline_brief.json"


def _n(i, parent=None, act=0, desc="d " * 20, tag="Concept"):
    return Node(id=i, act=act, tag=tag, title=i, desc=desc, parent=parent)


def _negligence():
    """A hub with six children, as Torts' Negligence unit has: two plain
    leaves, two concepts with outcomes, and two sections."""
    ns = [_n("hub")]
    ns += [_n("std", "hub"), _n("duty", "hub"), _n("duty-l", "duty"), _n("duty-nl", "duty")]
    ns += [_n("breach", "hub")]
    for c in ("risks", "custom", "per-se"):
        ns += [_n(c, "breach"), _n(c + "-l", c), _n(c + "-nl", c)]
    ns += [_n("cause", "hub"), _n("cause-l", "cause"), _n("cause-nl", "cause"),
           _n("alt", "cause"), _n("alt-l", "alt"), _n("alt-nl", "alt")]
    ns += [_n("prox", "hub"), _n("dam", "hub")]
    return ns


def _heights(ns, h=150):
    return {n.id: h for n in ns}


def _run(ns, placement=None, h=150, acts=1):
    plan = outline_plan(ns, acts, placement)
    y, x, world = run_plan(plan, ns, _heights(ns, h))
    return plan, y, x, world


def _box(plan, y, x, h, i):
    w = plan["w"].get(i, TREE["CARD_W"])
    return (x[i] - w / 2, y[i] - h / 2, x[i] + w / 2, y[i] + h / 2)


def _two_units():
    return _negligence() + [_n("r2", act=1), _n("k2", "r2", 1)]


def _brief(**kw):
    return Brief(title="t", subject="t", mode=kw.pop("mode", "outline"), columns=5,
                 acts=[Act(label="I"), Act(label="II")], timeline_id="t", **kw)


def test_without_hints_the_plan_is_the_trees_own_layout():
    ns = _negligence()
    plan, y, x, _ = _run(ns)
    assert {i for i, w in plan["w"].items() if w != TREE["CARD_W"]} == outline_flanks(ns)
    assert plan["warnings"] == []
    # the hub's four shallow children make one branch, sorted by its first
    # member; it pairs with breach, and cause (the odd one out) sits alone at
    # the centre: the arrangement the Negligence report complained about
    assert x["std"] == x["duty"] == x["prox"] == x["dam"] == TREE["BRANCH_X"][0]
    assert x["breach"] == TREE["BRANCH_X"][1] and x["cause"] == TREE["CX"]


def test_a_hub_sets_its_children_as_a_band_and_their_progeny_hang_below_it():
    ns = _negligence()
    plan, y, x, _ = _run(ns, {"hub": {"arrange": "row"}})
    ks = outline_kids(ns)["hub"]
    assert len(ks) == 6
    xs = [x[k] for k in ks]
    assert xs == sorted(xs) and len({round(b - a, 1) for a, b in zip(xs, xs[1:])}) == 1
    assert x["hub"] == pytest.approx(sum(xs) / 6)                # centred under the hub
    # six full-width cards do not fit one row, so they stagger into two:
    # neighbours alternate, a row's own cards share a top
    assert {plan["w"][k] for k in ks} == {TREE["CARD_W"]}
    tops = {k: y[k] - 75 for k in ks}
    assert len(set(tops.values())) == 2
    assert [tops[k] == tops[ks[0]] for k in ks] == [True, False] * 3
    lower = max(tops.values())
    assert lower == pytest.approx(min(tops.values()) + 150 + TREE["STAGGER_GAP"])
    assert min(xs) - 135 >= TREE["MARGIN"] and max(xs) + 135 <= WORLD_W - TREE["MARGIN"]
    # the band has priority: its cards are placed first, and what hangs from them
    # packs in beneath, straight under each parent and narrow enough to clear the
    # cards of the other row, so it never has to wait for a neighbour
    for parent, child in (("duty", "duty-l"), ("cause", "cause-l"), ("breach", "risks")):
        assert y[child] - 75 >= y[parent] + 75 + TREE["GROUP_GAP"] - 1
    assert y["duty-l"] - 75 >= (lower + 150 if y["duty"] > min(tops.values()) + 75
                                else y["duty"] + 75 + TREE["GROUP_GAP"]) - 1
    assert x["duty-l"] == x["duty-nl"] == x["duty"] and x["alt"] == x["cause"]
    assert plan["w"]["duty-l"] < TREE["CARD_W"] and y["duty-l"] < y["duty-nl"]
    check = placement_check(ns, plan, y, x, _heights(ns))
    assert check["overlaps"] == [] and check["off_margin"] == []


@pytest.mark.parametrize("k, rows, below_w", [(3, 1, 270), (4, 1, 270), (5, 1, 270),
                                              (6, 2, 180), (7, 2, 180)])
def test_a_band_keeps_its_cards_whole_and_staggers_before_it_squeezes(k, rows, below_w):
    ns = [_n("r")]
    for i in range(k):
        ns += [_n(f"k{i}", "r"), _n(f"k{i}-a", f"k{i}")]
    plan, y, x, _ = _run(ns, {"r": {"arrange": "row"}})
    assert {plan["w"][f"k{i}"] for i in range(k)} == {TREE["CARD_W"]}
    assert len({y[f"k{i}"] for i in range(k)}) == rows
    assert {plan["w"][f"k{i}-a"] for i in range(k)} == {below_w}
    lo = min(x[f"k{i}"] for i in range(k)) - 135
    hi = max(x[f"k{i}"] for i in range(k)) + 135
    assert lo >= TREE["MARGIN"] and hi <= WORLD_W - TREE["MARGIN"]
    assert placement_check(ns, plan, y, x, _heights(ns))["overlaps"] == []


def test_two_in_a_row_take_the_branch_spacing_and_keep_their_flanks():
    ns = [_n("r"), _n("a", "r"), _n("a1", "a"), _n("a1-l", "a1"), _n("b", "r")]
    plan, y, x, _ = _run(ns, {"r": {"arrange": "row"}})
    assert (x["a"], x["b"]) == tuple(TREE["BRANCH_X"])
    assert x["a1-l"] == x["a1"] - TREE["FLANK_DX"]               # room for flanks


def test_a_long_row_wraps_into_balanced_bands():
    ns = [_n("r")] + [_n(f"k{i}", "r") for i in range(8)]
    plan, y, x, _ = _run(ns, {"r": {"arrange": "row"}})
    # 8 > 7: two bands of four, one below the other, each a single row
    tops = sorted({y[f"k{i}"] for i in range(8)})
    assert len(tops) == 2
    assert [sum(1 for i in range(8) if y[f"k{i}"] == t) for t in tops] == [4, 4]
    assert placement_check(ns, plan, y, x, _heights(ns))["overlaps"] == []


def test_column_stacks_every_child_down_the_spine_sections_and_all():
    ns = _negligence()
    plan, y, x, _ = _run(ns, {"hub": {"arrange": "column"}})
    ks = outline_kids(ns)["hub"]
    assert {x[k] for k in ks} == {TREE["CX"]}
    assert [y[k] for k in ks] == sorted(y[k] for k in ks)         # in outline order
    assert y["breach"] < y["risks"] < y["cause"]                  # breach's progeny between


def test_x_moves_a_card_and_its_progeny_hang_from_it():
    ns = _negligence()
    base, _, bx, _ = _run(ns)
    plan, y, x, _ = _run(ns, {"duty": {"x": 600}})
    assert x["duty"] == 600 and bx["duty"] == TREE["BRANCH_X"][0]
    assert x["duty-l"] == 600 - TREE["FLANK_DX"] and x["duty-nl"] == 600 + TREE["FLANK_DX"]
    assert x["std"] == bx["std"]                                  # a sibling stays put


def test_dx_nudges_and_a_card_that_would_leave_the_page_is_held_and_reported():
    ns = _negligence()
    _, _, base, _ = _run(ns)
    plan, y, x, _ = _run(ns, {"std": {"dx": 40}})
    assert x["std"] == base["std"] + 40 and plan["warnings"] == []
    plan, y, x, _ = _run(ns, {"std": {"x": 1650}})
    assert x["std"] == WORLD_W - TREE["MARGIN"] - TREE["CARD_W"] / 2
    assert any("std" in w and "page edge" in w for w in plan["warnings"])


def test_dy_adds_room_above_a_card_and_everything_after_it_moves():
    ns = _negligence()
    _, y0, _, w0 = _run(ns, {"hub": {"arrange": "column"}})
    _, y1, _, w1 = _run(ns, {"hub": {"arrange": "column"}, "duty": {"dy": 100}})
    assert y1["std"] == y0["std"]
    assert y1["duty"] == y0["duty"] + 100
    assert y1["prox"] == y0["prox"] + 100 and w1 == w0 + 100


def test_a_floated_card_takes_no_room_in_the_flow():
    ns = _negligence()
    _, y0, _, _ = _run(ns, {"hub": {"arrange": "column"}})
    plan, y1, x1, _ = _run(ns, {"hub": {"arrange": "column"},
                                "duty": {"float": True, "x": 500}})
    ks = outline_kids(ns)["hub"]
    after = ks[ks.index("duty") + 1]
    # the card after Duty slides up into the room Duty and its outcomes left,
    # Duty keeps its place on the page, and its outcomes still flank it
    assert y1[after] < y0[after]
    assert y1["duty"] == y0["duty"] and x1["duty"] == 500
    assert x1["duty-l"] == 500 - TREE["FLANK_DX"] and y1["duty-l"] == y1["duty"]


def test_overlaps_and_edge_violations_are_reported():
    ns = _negligence()
    plan, y, x, _ = _run(ns, {"hub": {"arrange": "column"},
                              "duty": {"float": True}})             # lies over what follows
    check = placement_check(ns, plan, y, x, _heights(ns))
    assert check["overlap_count"] > 0 and any("duty" in p for p in check["overlaps"])
    ns = [_n("r"), _n("a", "r")]
    plan = outline_plan(ns, 1, {"a": {"x": 100}})
    plan["x"]["a"] = 100                                           # as if forced past the margin
    y, x, _ = run_plan(plan, ns, _heights(ns))
    assert placement_check(ns, plan, y, x, _heights(ns))["off_margin"] == ["a"]


def test_order_sets_a_cards_place_among_its_siblings_and_the_numerals_follow():
    ns = _negligence()
    b = _brief(placement={"cause": {"order": 2}, "dam": {"order": 1}})
    place(b, ns)
    assert outline_kids(ns)["hub"] == ["dam", "cause", "std", "duty", "breach", "prox"]
    # idempotent: a second pass over the reordered nodes changes nothing
    place(b, ns)
    assert outline_kids(ns)["hub"] == ["dam", "cause", "std", "duty", "breach", "prox"]
    b = _brief(placement={"hub": {"arrange": "row"}, "cause": {"order": 3}})
    html, _ = build_timeline(b, _two_units(), [])
    num = json.loads(html.split("window._ALTO_OUTLINE={num:", 1)[1].split(",label:", 1)[0])
    assert num["cause"] == "I.C." and num["breach"] == "I.D." and num["duty"] == "I.B."


def test_hints_for_one_unit_leave_the_others_alone():
    ns = _negligence() + [_n("r2", act=1), _n("a2", "r2", 1), _n("b2", "r2", 1)]
    plain = outline_plan(ns, 2)
    hinted = outline_plan(ns, 2, {"hub": {"arrange": "row"}})
    for i in ("r2", "a2", "b2"):
        assert plain["x"][i] == hinted["x"][i]
    assert plain["acts"][1] == hinted["acts"][1]


def test_placing_cards_makes_auto_choose_the_tree_and_reports_the_result():
    ns = [_n("r")] + [_n(f"k{i}", "r") for i in range(6)]          # flat: auto would flow
    assert run_layout(_brief(), ns, [])[5]["layout"] == "flow"
    b = _brief(placement={"r": {"arrange": "row"}})
    rep = run_layout(b, ns, [])[5]
    assert rep["layout"] == "tree"
    assert rep["placement"]["hinted"] == 1 and rep["placement"]["overlap_count"] == 0
    # `order` alone is not a reason to leave flow
    assert run_layout(_brief(placement={"k1": {"order": 1}}), ns, [])[5]["layout"] == "flow"


def test_the_built_page_runs_the_plan_and_narrows_the_progeny_of_a_staggered_band():
    b = _brief(placement={"hub": {"arrange": "row"}})
    html, report = build_timeline(b, _two_units(), [])
    assert report["layout"]["layout"] == "tree"
    assert "window._ALTO_TREE_PLAN=" in html and "window._ALTO_TREE_C" not in html
    assert "html:not(.mobile) #node-duty-l .node-card" in html
    assert "{width:180px;}" in html and '["band",' in html


@needs_node
def test_the_browser_runs_a_hinted_plan_exactly_as_the_builder_does(tmp_path):
    ns = _negligence() + [_n("r2", act=1), _n("a2", "r2", 1), _n("a2-l", "a2", 1)]
    hints = {"hub": {"arrange": "row"}, "breach": {"arrange": "column"},
             "per-se": {"float": True, "x": 900, "dy": 30},
             "duty": {"dy": 25}, "r2": {"dx": -40}, "dam": {"order": 1},
             "cause": {"tier": 2}, "alt": {"y": 2600, "w": 240},
             "duty-nl": {"y": 3100, "x": 300}, "duty-l": {"float": True, "x": 260, "dy": -40}}
    b = _brief(placement=hints)
    place(b, ns)
    plan = outline_plan(ns, 2, hints)
    h = {n.id: 110 + (len(n.id) % 5) * 23 for n in ns}
    y, x, world = run_plan(plan, ns, h)
    kids = outline_kids(ns)
    js = ("var window=globalThis; var document={documentElement:{classList:{contains:function(){return false;}}},"
          "getElementById:function(){return null;}};\n"
          f"var NODES={json.dumps([{'id': n.id} for n in ns])};\n"
          "window._ALTO_OUTLINE={kids:" + json.dumps(kids) + ",parent:"
          + json.dumps({n.id: n.parent for n in ns if n.parent}) + "};\n"
          + dx.tree_glue(plan_js(plan)) + "\n"
          f"var pos={{}}, h={json.dumps(h)}; window._altoTree(pos,h);\n"
          "console.log(JSON.stringify({y:pos, etx:window._altoEdgeTX, x:Object.fromEntries(NODES.map(function(n){return [n.id,n.displayX];}))}));")
    f = tmp_path / "plan.js"
    f.write_text(js, encoding="utf-8")
    out = json.loads(subprocess.check_output([NODE, str(f)], timeout=60))
    for n in ns:
        assert out["y"][n.id] == pytest.approx(y[n.id]), n.id
        assert out["x"][n.id] == pytest.approx(x[n.id]), n.id
    assert out["etx"] == plan["etx"]


def test_a_bad_hint_fails_loudly_and_a_stale_one_only_warns():
    for bad, why in (
            ({"a": {"arrage": "row"}}, "unknown hint"),
            ({"a": {"arrange": "diagonal"}}, "arrange"),
            ({"a": {"x": "left"}}, "number"),
            ({"a": {"x": 5000}}, "number"),
            ({"a": {"dx": True}}, "number"),
            ({"a": {"float": "yes"}}, "float"),
            ({"a": {"order": 0}}, "order"),
            ({"a": {"order": 1.5}}, "order"),
            ({"a": "row"}, "object of hints"),
            (["a"], "object")):
        with pytest.raises(BriefError, match=why):
            validate_brief(_brief(placement=bad))
    with pytest.raises(BriefError, match="needs mode 'outline'"):
        validate_brief(_brief(mode="linear", placement={"a": {"dx": 1}}))
    ok = validate_brief(_brief(placement={"a": {"arrange": "row", "x": 700, "dy": -20,
                                               "float": False, "order": 2}}))
    assert not [w for w in ok if "placement" in w]
    flow = validate_brief(_brief(layout="flow", placement={"a": {"dx": 10}}))
    assert any("flow" in w for w in flow)
    assert not any("flow" in w for w in validate_brief(
        _brief(layout="flow", placement={"a": {"order": 2}})))
    from alto.build.brief import _validate_outline_tree
    ns = [_n("r"), _n("k", "r")]
    warns = _validate_outline_tree(_brief(placement={"ghost": {"dx": 1}}), ns)
    assert any("ghost" in w and "ignored" in w for w in warns)


def test_the_hint_limits_match_the_layouts_world():
    assert PLACE_WORLD_W == WORLD_W


def test_a_placed_build_says_what_overlaps():
    b = _brief(placement={"hub": {"arrange": "column"}, "duty": {"float": True}})
    _, report = build_timeline(b, _two_units(), [])
    assert any("placement:" in w and "overlap" in w for w in report["warnings"])


# ── "however they please" ────────────────────────────────────────────────────
# The promise the hints make: any card can be put anywhere on the page. Held to
# it on random outlines, with every card pinned to a random spot.

def _random_outline(seed, acts=2, outcomes=False):
    import random
    r = random.Random(seed)
    ns, n = [], 0

    def mk(parent, depth, act):
        nonlocal n
        n += 1
        i = f"n{n}"
        node = _n(i, parent, act, desc="d " * r.randint(5, 60))
        ns.append(node)
        if depth < 4 and r.random() < (0.95 if depth == 0 else 0.55):
            for _ in range(r.randint(1, 7)):
                mk(i, depth + 1, act)
        elif outcomes and depth and r.random() < 0.6:
            node.tag = "Outcome"                      # a leaf of a different kind

    for a in range(acts):
        mk(None, 0, a)
    return ns


def _pinned_everywhere(ns, seed):
    import random
    r = random.Random(seed)
    kids = outline_kids(ns)
    by_id = {n.id: n for n in ns}
    flank = outline_flanks(ns)
    hints, want = {}, {}
    for n in ns:
        # a card with outcomes beside it needs 355px each side; a narrow one 90
        reach = (TREE["FLANK_DX"] + TREE["FLANK_W"] / 2
                 if kids.get(n.id) and all(not kids.get(k) for k in kids[n.id])
                 and any(True for _ in [0]) else
                 (TREE["FLANK_W"] if n.id in flank else TREE["CARD_W"]) / 2)
        pinned = [k for k in kids.get(n.id, []) if k in flank]
        # every outcome of a concept is pinned too, so its row holds only itself
        if pinned:
            reach = TREE["CARD_W"] / 2
        lo, hi = TREE["MARGIN"] + reach, WORLD_W - TREE["MARGIN"] - reach
        px, py = round(r.uniform(lo, hi), 1), round(r.uniform(150, 9000), 1)
        hints[n.id] = {"x": px, "y": py}
        want[n.id] = (px, py)
    return hints, want


@pytest.mark.parametrize("seed", range(40))
def test_every_card_can_be_pinned_to_any_spot_on_the_page(seed):
    ns = _random_outline(seed)
    hints, want = _pinned_everywhere(ns, seed)
    plan = outline_plan(ns, 2, hints)
    import random
    r = random.Random(seed)
    h = {n.id: r.choice([100, 130, 160, 190, 240]) for n in ns}
    y, x, world = run_plan(plan, ns, h)
    for n in ns:
        px, py = want[n.id]
        assert x[n.id] == pytest.approx(px), (seed, n.id, "x")
        assert y[n.id] - h[n.id] / 2 == pytest.approx(py), (seed, n.id, "top")
    assert plan["warnings"] == []
    assert world >= max(y[i] + h[i] / 2 for i in y)


def test_a_cards_width_is_its_own_to_set():
    ns = _negligence()
    plan, y, x, _ = _run(ns, {"std": {"w": 380}, "hub": {"w": 200}})
    assert plan["w"]["std"] == 380 and plan["w"]["hub"] == 200
    # held clear of the page edge by its own width
    plan, y, x, _ = _run(ns, {"std": {"w": 380, "x": 150}})
    assert x["std"] == TREE["MARGIN"] + 190 and plan["warnings"]


def test_a_y_pins_the_top_and_the_progeny_flow_from_it():
    ns = _negligence()
    plan, y, x, _ = _run(ns, {"breach": {"y": 5000}})
    assert y["breach"] - 75 == 5000
    assert y["risks"] > y["breach"] and x["risks"] == x["breach"]
    _, y0, _, _ = _run(ns)
    assert y["std"] == y0["std"]                            # what is above is untouched
    assert y["cause"] <= y0["cause"]                        # what was below closes up


def test_an_outcome_can_leave_its_concept_and_go_where_it_is_told():
    ns = _negligence()
    plan, y, x, _ = _run(ns, {"duty-nl": {"y": 3000, "x": 300}})
    assert (x["duty-nl"], y["duty-nl"] - 75) == (300, 3000)
    assert x["duty-l"] == x["duty"] - TREE["FLANK_DX"] and y["duty-l"] == y["duty"]
    # with both outcomes gone the concept is free of the flank margins
    plan, y, x, _ = _run(ns, {"duty-l": {"float": True, "x": 250}, "duty-nl": {"y": 3000},
                              "duty": {"x": 300}})
    assert x["duty"] == 300 and not plan["warnings"]


def test_tiers_choose_a_cards_row_in_the_band_and_leave_the_notes_order_alone():
    ns = _negligence()
    hints = {"hub": {"arrange": "row"}, **{k: {"tier": 2} for k in ("duty", "cause", "dam")}}
    plan, y, x, _ = _run(ns, hints)
    ks = outline_kids(ns)["hub"]
    upper = [k for k in ks if k not in ("duty", "cause", "dam")]
    lower = ["duty", "cause", "dam"]
    assert len({y[k] for k in upper}) == 1 and len({y[k] for k in lower}) == 1
    assert y[lower[0]] > y[upper[0]] and plan["warnings"] == []
    # a tier that leaves neighbours on one line says so, and still overlaps nothing
    plan2, y2, x2, _ = _run(ns, {"hub": {"arrange": "row"}, "breach": {"tier": 2}})
    assert any("overlap sideways" in w for w in plan2["warnings"])
    assert placement_check(ns, plan2, y2, x2, _heights(ns))["overlaps"] == []
    xs = [x[k] for k in ks]
    assert xs == sorted(xs)                                      # left to right is still the notes' order
    b = _brief(placement=hints)
    place(b, ns)
    assert outline_kids(ns)["hub"] == ks
    with pytest.raises(BriefError):
        validate_brief(_brief(placement={"breach": {"tier": 0}}))


def test_the_band_staggers_so_a_tall_card_does_not_push_its_neighbour_down():
    ns = _negligence()
    plan = outline_plan(ns, 1, {"hub": {"arrange": "row"}})
    short = _heights(ns)
    tall = {**short, "std": 900}
    y1, _, _ = run_plan(plan, ns, short)
    y2, _, _ = run_plan(plan, ns, tall)
    # evenly tall: the first card is on the upper row. With a tall first card the
    # band flips, so it sits on the lower row beside its neighbour instead of
    # holding the whole band down
    assert y1["std"] < y1["duty"] and y2["std"] > y2["duty"]
    assert y2["duty"] - 75 == y2["hub"] + 75 + TREE["ROOT_GAP"]


def test_a_wide_block_settles_below_its_neighbours_and_nothing_overlaps():
    ns = _negligence()
    plan, y, x, _ = _run(ns, {"hub": {"arrange": "row"}, "breach": {"arrange": "row"}})
    # breach's three children are a band of their own, wider than breach's column,
    # so the whole block sits under what hangs from breach's neighbours
    neighbour_bottom = max(y[i] + 75 for i in ("duty-l", "duty-nl", "cause-nl", "alt-nl"))
    assert min(y[i] - 75 for i in ("risks", "custom", "per-se")) >= neighbour_bottom + TREE["GROUP_GAP"] - 1
    assert placement_check(ns, plan, y, x, _heights(ns))["overlaps"] == []




def _js_plan(ns, plan, h, tmp_path):
    kids = outline_kids(ns)
    js = ("var window=globalThis; var document={documentElement:{classList:{contains:function(){return false;}}},"
          "getElementById:function(){return null;}};\n"
          f"var NODES={json.dumps([{'id': n.id} for n in ns])};\n"
          "window._ALTO_OUTLINE={kids:" + json.dumps(kids) + ",parent:"
          + json.dumps({n.id: n.parent for n in ns if n.parent}) + "};\n"
          + dx.tree_glue(plan_js(plan)) + "\n"
          f"var pos={{}}, h={json.dumps(h)}; window._altoTree(pos,h);\n"
          "console.log(JSON.stringify({y:pos, x:Object.fromEntries(NODES.map(function(n){return [n.id,n.displayX];}))}));")
    f = tmp_path / "plan.js"
    f.write_text(js, encoding="utf-8")
    return json.loads(subprocess.check_output([NODE, str(f)], timeout=60))


@needs_node
@pytest.mark.parametrize("tall", [None, "std", "duty", "dam"])
def test_the_browser_lays_out_nested_staggered_bands_as_the_builder_does(tmp_path, tall):
    ns = _negligence()
    hints = {"hub": {"arrange": "row"}, "breach": {"arrange": "row"},
             "custom": {"arrange": "row"}, "per-se": {"arrange": "row"}}
    plan = outline_plan(ns, 1, hints)
    h = {n.id: 110 + (len(n.id) % 5) * 23 for n in ns}
    if tall:
        h[tall] = 900
    y, x, _ = run_plan(plan, ns, h)
    out = _js_plan(ns, plan, h, tmp_path)
    for n in ns:
        assert out["y"][n.id] == pytest.approx(y[n.id]), n.id
        assert out["x"][n.id] == pytest.approx(x[n.id]), n.id
    boxes = [(x[i] - plan["w"].get(i, 270) / 2, y[i] - h[i] / 2, x[i] + plan["w"].get(i, 270) / 2,
              y[i] + h[i] / 2, i) for i in y]
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            assert not (min(a[2], b[2]) - max(a[0], b[0]) > 1 and min(a[3], b[3]) - max(a[1], b[1]) > 1), (a[4], b[4])


def _random_flow_hints(ns, seed):
    import random
    r = random.Random(seed * 7 + 1)
    kids = outline_kids(ns)
    return {n.id: {"arrange": r.choice(["row", "column", "branches", "auto"])}
            for n in ns if kids.get(n.id) and r.random() < 0.5}


@pytest.mark.parametrize("seed", range(150))
def test_arrangement_hints_never_make_cards_overlap_or_leave_the_margin(seed):
    """However the arrangements are mixed down a tree, the layout packs: a wide
    block settles below its neighbours instead of across them."""
    import random
    ns = _random_outline(seed)
    plan = outline_plan(ns, 2, _random_flow_hints(ns, seed))
    r = random.Random(seed)
    h = {n.id: r.choice([100, 130, 160, 190, 240, 400]) for n in ns}
    y, x, _ = run_plan(plan, ns, h)
    check = placement_check(ns, plan, y, x, h)
    assert check["overlaps"] == [] and check["off_margin"] == [], (seed, check)


@needs_node
@pytest.mark.parametrize("seed", range(0, 150, 15))
def test_the_browser_agrees_with_the_builder_on_random_arrangements(tmp_path, seed):
    import random
    ns = _random_outline(seed)
    plan = outline_plan(ns, 2, _random_flow_hints(ns, seed))
    r = random.Random(seed)
    h = {n.id: r.choice([100, 130, 160, 190, 240, 400]) for n in ns}
    y, x, _ = run_plan(plan, ns, h)
    out = _js_plan(ns, plan, h, tmp_path)
    for n in ns:
        assert out["y"][n.id] == pytest.approx(y[n.id]), (seed, n.id)
        assert out["x"][n.id] == pytest.approx(x[n.id]), (seed, n.id)



# ── outcomes: Liable / Not Liable beside their parent, or side by side under it ──

def _torts_negligence():
    """A hub of five concepts, two of which have outcomes (and one of those also a
    sub-concept), as Torts' Negligence unit does."""
    ns = [_n("hub")]
    for c in ("std", "duty", "cause", "prox", "dam"):
        ns.append(_n(c, "hub"))
    for p in ("duty", "cause"):
        ns += [_n(p + "-l", p, tag="Outcome"), _n(p + "-nl", p, tag="Outcome")]
    ns += [_n("alt", "cause"), _n("alt-l", "alt", tag="Outcome"), _n("alt-nl", "alt", tag="Outcome")]
    return ns


def test_outcomes_stay_in_the_stack_unless_asked():
    ns = _torts_negligence()
    stacked = outline_plan(ns, 1, {"hub": {"arrange": "row"}})
    assert stacked["x"]["cause-l"] == stacked["x"]["cause-nl"] == stacked["x"]["cause"]
    plain = outline_plan(ns, 1, {"hub": {"arrange": "row"}}, "fan", "stack")
    assert plain["acts"] == stacked["acts"]


def test_outcomes_sit_side_by_side_directly_under_a_parent_with_no_room_beside_it():
    ns = _torts_negligence()
    hints = {"hub": {"arrange": "row"}}
    plan = outline_plan(ns, 1, hints, "fan", "beside")
    y, x, _ = run_plan(plan, ns, _heights(ns))
    for parent in ("duty", "cause", "alt"):
        l, nl = parent + "-l", parent + "-nl"
        assert y[l] == y[nl] > y[parent]                         # a pair, below the parent
        assert plan["w"][l] == plan["w"][nl] <= TREE["FLANK_W"]
        assert x[nl] - x[l] == plan["w"][l] + TREE["OUT_GAP"]
        # centred on the parent, give or take the slide that keeps neighbouring
        # parents' pairs apart
        assert abs((x[l] + x[nl]) / 2 - x[parent]) <= 100
    # two parents side by side: their pairs are kept clear of each other
    assert x["duty-nl"] + 90 <= x["cause-l"] - 90
    assert placement_check(ns, plan, y, x, _heights(ns))["overlaps"] == []
    assert placement_check(ns, plan, y, x, _heights(ns))["off_margin"] == []


def test_outcomes_are_equals_of_the_sub_concepts_beside_them():
    """Cause in Fact has Liable, Not Liable and a sub-concept: the three are one
    row under it, level and side by side, not a pair with the sub-concept hung
    below. A concept with outcomes only keeps its pair."""
    ns = _torts_negligence()
    plan = outline_plan(ns, 1, {"hub": {"arrange": "row"}}, "fan", "beside")
    h = _heights(ns)
    y, x, _ = run_plan(plan, ns, h)
    row = ["cause-l", "cause-nl", "alt"]
    assert len({round(y[i] - h[i] / 2, 3) for i in row}) == 1       # one top
    xs = [x[i] for i in row]
    assert xs == sorted(xs) and all(plan["w"][i] == plan["w"]["cause-l"] for i in row)
    assert x["alt"] - x["cause-nl"] == plan["w"]["alt"] + TREE["OUT_GAP"]
    below = y["cause"] + h["cause"] / 2
    assert 0 < y["cause-l"] - h["cause-l"] / 2 - below <= 100        # directly under
    assert y["alt-l"] > y["alt"]                                     # its own pair follows
    assert y["duty-l"] - h["duty-l"] / 2 - (y["duty"] + h["duty"] / 2) <= 100


@needs_node
@pytest.mark.parametrize("tall", [None, "std", "cause", "alt"])
def test_the_browser_lays_out_a_row_of_equals_as_the_builder_does(tmp_path, tall):
    ns = _torts_negligence()
    plan = outline_plan(ns, 1, {"hub": {"arrange": "row"}, "std": {"tier": 2}}, "fan", "beside")
    h = {n.id: 110 + (len(n.id) % 5) * 23 for n in ns}
    if tall:
        h[tall] = 800
    y, x, _ = run_plan(plan, ns, h)
    out = _js_plan(ns, plan, h, tmp_path)
    for n in ns:
        assert out["y"][n.id] == pytest.approx(y[n.id]), n.id
        assert out["x"][n.id] == pytest.approx(x[n.id]), n.id


def test_a_pair_of_outcomes_is_held_inside_the_margin_as_a_pair():
    ns = [_n("hub")] + [_n(f"c{i}", "hub") for i in range(5)]
    ns += [_n("c0-l", "c0", tag="Outcome"), _n("c0-nl", "c0", tag="Outcome")]
    plan = outline_plan(ns, 1, {"hub": {"arrange": "row"}}, "fan", "beside")
    y, x, _ = run_plan(plan, ns, _heights(ns))
    assert x["c0"] < TREE["MARGIN"] + 190                        # the leftmost column: no room for a centred pair
    assert x["c0-l"] - 90 >= TREE["MARGIN"] and x["c0-nl"] - x["c0-l"] == 200
    assert placement_check(ns, plan, y, x, _heights(ns))["overlaps"] == []


def test_a_third_outcome_sits_alone_under_the_pair():
    ns = [_n("hub")] + [_n(f"c{i}", "hub") for i in range(3)]
    ns += [_n(f"c1-o{k}", "c1", tag="Outcome") for k in range(3)]
    plan = outline_plan(ns, 1, {"hub": {"arrange": "row"}}, "fan", "beside")
    y, x, _ = run_plan(plan, ns, _heights(ns))
    assert y["c1-o0"] == y["c1-o1"] < y["c1-o2"] and x["c1-o2"] == x["c1"]


def test_outcomes_flank_a_section_that_has_only_outcomes_and_others_join_its_row():
    ns = [_n("root"), _n("sec", "root"), _n("sec-l", "sec", tag="Outcome"),
          _n("sec-nl", "sec", tag="Outcome"), _n("sub", "sec"), _n("sub-a", "sub"),
          _n("other", "root"), _n("other-a", "other"), _n("other-b", "other")]
    plan = outline_plan(ns, 1, {}, "fan", "beside")
    y, x, _ = run_plan(plan, ns, _heights(ns))
    # a section with outcomes AND a sub-concept: the three are equals, one row under it
    assert y["sec-l"] == y["sec-nl"] == y["sub"] > y["sec"]
    assert x["sec-l"] < x["sec-nl"] < x["sub"]
    # one with outcomes only keeps them beside it
    only = outline_plan([n for n in ns if n.id not in ("sub", "sub-a")], 1, {}, "fan", "beside")
    y1, x1, _ = run_plan(only, [n for n in ns if n.id not in ("sub", "sub-a")], _heights(ns))
    assert y1["sec-l"] == y1["sec"] == y1["sec-nl"]
    assert x1["sec-l"] == x1["sec"] - TREE["FLANK_DX"] and x1["sec-nl"] == x1["sec"] + TREE["FLANK_DX"]
    # and the same outline left alone stacks them down the spine, as before
    plain = outline_plan(ns, 1, {})
    y0, x0, _ = run_plan(plain, ns, _heights(ns))
    assert x0["sec-l"] == x0["sec"] and y0["sec-l"] > y0["sec"]


def test_child_w_shrinks_a_band_so_more_fit_one_row_and_tier_2_is_visibly_staggered():
    ns = [_n("hub")] + [_n(f"c{i}", "hub") for i in range(6)]
    wide = outline_plan(ns, 1, {"hub": {"arrange": "row"}})
    y, x, _ = run_plan(wide, ns, _heights(ns))
    assert len({y[f"c{i}"] for i in range(6)}) == 2             # 6 x 270 will not fit: two rows
    hints = {"hub": {"arrange": "row", "child_w": 210}, "c0": {"tier": 2}}
    plan = outline_plan(ns, 1, hints)
    y, x, _ = run_plan(plan, ns, _heights(ns))
    assert {plan["w"][f"c{i}"] for i in range(6)} == {210}
    row = [y[f"c{i}"] for i in range(1, 6)]
    assert len(set(row)) == 1                                    # five in the same row
    assert y["c0"] - row[0] == TREE["STAGGER_DROP"]              # the staggered one sits lower
    gaps = {round(x[f"c{i + 1}"] - x[f"c{i}"], 1) for i in range(5)}
    assert len(gaps) == 1 and min(gaps) >= 210 + TREE["BAND_GAP"]
    assert placement_check(ns, plan, y, x, _heights(ns))["overlaps"] == []


def test_outcomes_and_child_w_are_validated():
    with pytest.raises(BriefError, match="outcomes"):
        validate_brief(_brief(outcomes="sideways"))
    with pytest.raises(BriefError, match="needs mode 'outline'"):
        validate_brief(_brief(mode="linear", outcomes="beside"))
    assert not [w for w in validate_brief(_brief(outcomes="beside")) if "outcomes" in w]
    for bad in (50, 900, "wide", True):
        with pytest.raises(BriefError, match="child_w"):
            validate_brief(_brief(placement={"hub": {"child_w": bad}}))


def test_beside_makes_auto_choose_the_tree_and_the_page_carries_the_pairs():
    flat = [_n("r")] + [_n(f"k{i}", "r", tag="Outcome") for i in range(4)]   # a flat list
    assert run_layout(_brief(), flat, [])[5]["layout"] == "flow"
    assert run_layout(_brief(outcomes="beside"), flat, [])[5]["layout"] == "tree"
    html, report = build_timeline(_brief(outcomes="beside", placement={"hub": {"arrange": "row"}}),
                                  _two_units() + [_n("duty-o", "duty", tag="Outcome")], [])
    assert report["layout"]["layout"] == "tree" and "#node-duty-o .node-card" in html


@pytest.mark.parametrize("seed", range(150))
def test_outcomes_beside_never_make_cards_overlap_or_leave_the_margin(seed):
    import random
    ns = _random_outline(seed, outcomes=True)
    plan = outline_plan(ns, 2, _random_flow_hints(ns, seed), "fan", "beside")
    r = random.Random(seed)
    h = {n.id: r.choice([100, 130, 160, 190, 240, 400]) for n in ns}
    y, x, _ = run_plan(plan, ns, h)
    check = placement_check(ns, plan, y, x, h)
    assert check["overlaps"] == [] and check["off_margin"] == [], (seed, check)


@needs_node
@pytest.mark.parametrize("seed", range(0, 150, 15))
def test_the_browser_agrees_with_the_builder_on_outcomes_and_staggered_bands(tmp_path, seed):
    import random
    ns = _random_outline(seed, outcomes=True)
    hints = _random_flow_hints(ns, seed)
    kids = outline_kids(ns)
    for k, v in list(hints.items()):
        if v["arrange"] == "row":
            v["child_w"] = 210
            for c in kids[k][:1]:
                hints[c] = {**hints.get(c, {}), "tier": 2}
    plan = outline_plan(ns, 2, hints, "fan", "beside")
    r = random.Random(seed)
    h = {n.id: r.choice([100, 130, 160, 190, 240, 400]) for n in ns}
    y, x, _ = run_plan(plan, ns, h)
    out = _js_plan(ns, plan, h, tmp_path)
    for n in ns:
        assert out["y"][n.id] == pytest.approx(y[n.id]), (seed, n.id)
        assert out["x"][n.id] == pytest.approx(x[n.id]), (seed, n.id)


def test_an_outcome_pair_slides_clear_of_a_staggered_card_instead_of_waiting_for_it():
    """Torts: Negligence Standard is the staggered (tier 2) card at the left and a
    tall one. Duty's pair is wider than Duty's column, so its left card would hit
    Standard's right edge and have to wait for the whole tall card to end, leaving
    Duty's outcomes far below Duty. The pair leans away instead."""
    ns = _torts_negligence()
    hints = {"hub": {"arrange": "row", "child_w": 210}, "std": {"tier": 2}}
    plan = outline_plan(ns, 1, hints, "fan", "beside")
    h = {**_heights(ns), "std": 900}
    y, x, _ = run_plan(plan, ns, h)
    assert x["duty-l"] - 90 >= x["std"] + 105 + TREE["BAND_GAP"] / 2 - 1     # clear of Standard
    assert x["duty-nl"] - x["duty-l"] == TREE["FLANK_W"] + TREE["OUT_GAP"]   # still a pair
    duty_bottom = y["duty"] + 75
    assert y["duty-l"] - 75 == pytest.approx(duty_bottom + TREE["GROUP_GAP"])  # directly under Duty
    assert y["duty-l"] < y["std"] + 450                                       # not waiting for Standard
    assert placement_check(ns, plan, y, x, h)["overlaps"] == []
    # a pair with a lower-row neighbour on BOTH sides cannot clear them: it stays
    # centred and waits (an auto-staggered band of six)
    ns2 = [_n("hub")] + [_n(f"c{i}", "hub") for i in range(6)]
    ns2 += [_n("c2-l", "c2", tag="Outcome"), _n("c2-nl", "c2", tag="Outcome")]
    p2 = outline_plan(ns2, 1, {"hub": {"arrange": "row"}}, "fan", "beside")
    assert p2["x"]["c2-l"] == p2["x"]["c2"] - 100 and p2["x"]["c2-nl"] == p2["x"]["c2"] + 100


def _breach_like():
    """Four children of a band, each with a Liable / Not Liable pair; one of them
    (custom) also has a sub-concept whose own row is as wide as the page."""
    ns = [_n("b")]
    for c in ("risks", "custom", "perse", "res"):
        ns += [_n(c, "b"), _n(c + "-l", c, tag="Outcome"), _n(c + "-nl", c, tag="Outcome")]
    ns += [_n("mal", "custom"), _n("nat", "mal"), _n("loc", "mal"),
           _n("nat-l", "nat", tag="Outcome"), _n("nat-nl", "nat", tag="Outcome"),
           _n("loc-l", "loc", tag="Outcome"), _n("loc-nl", "loc", tag="Outcome")]
    return ns


def test_the_pairs_of_a_wide_band_narrow_to_fit_across_the_page_and_share_a_level():
    ns = _breach_like()
    plan = outline_plan(ns, 1, {"b": {"arrange": "row"}, "mal": {"arrange": "row"}}, "fan", "beside")
    y, x, _ = run_plan(plan, ns, _heights(ns))
    pairs = [c + s for c in ("risks", "custom", "perse", "res") for s in ("-l", "-nl")]
    # four 380px pairs cannot sit across 1470px, so the cards narrow (not below the minimum)
    ow = {plan["w"][i] for i in pairs}
    assert len(ow) == 1 and TREE["MIN_OUT_W"] <= ow.pop() < TREE["FLANK_W"]
    # and so they all hang at the same level, none held down by a neighbour
    assert len({y[i] for i in pairs}) == 1
    spans = sorted((x[c + "-l"] - plan["w"][c + "-l"] / 2, x[c + "-nl"] + plan["w"][c + "-nl"] / 2)
                   for c in ("risks", "custom", "perse", "res"))
    assert all(b[0] >= a[1] for a, b in zip(spans, spans[1:]))               # side by side, no overlap
    assert spans[0][0] >= TREE["MARGIN"] and spans[-1][1] <= WORLD_W - TREE["MARGIN"]
    # custom's sub-concept is one of three equals in its row, level with the others'
    # pairs; what hangs from it (a row across the whole page) sits below, and did
    # not pull that row down with it
    assert y["mal"] == y["custom-l"] == y["custom-nl"]
    assert y["nat"] > y["mal"]
    assert placement_check(ns, plan, y, x, _heights(ns))["overlaps"] == []


def test_concepts_with_progeny_go_in_a_row_under_their_parent_clear_of_a_wide_rows_line():
    """The Negligence Standard case: a band card whose three sub-concepts each
    have a Liable / Not Liable pair. They sit in one row right under it (not a tall
    column), over their pairs, and leave the connector of the wide row hanging
    from the card to their right clear."""
    ns = [_n("hub"), _n("std", "hub"), _n("duty", "hub"), _n("breach", "hub"), _n("cause", "hub"),
          _n("prox", "hub"), _n("dam", "hub")]
    for c in ("mental", "phys", "age"):
        ns += [_n(c, "std"), _n(c + "-l", c, tag="Outcome"), _n(c + "-nl", c, tag="Outcome")]
    for c in ("risks", "custom", "perse", "res"):
        ns += [_n(c, "breach"), _n(c + "-l", c, tag="Outcome"), _n(c + "-nl", c, tag="Outcome")]
    hints = {"hub": {"arrange": "row", "child_w": 210}, "std": {}, "breach": {"arrange": "row"}}
    hints_t = {**hints, "std": {}}
    plan = outline_plan(ns, 1, {"hub": hints["hub"], "breach": hints["breach"]}, "fan", "beside")
    h = _heights(ns)
    y, x, _ = run_plan(plan, ns, h)
    row = ["mental", "phys", "age"]
    assert len({round(y[i] - h[i] / 2, 3) for i in row}) == 1                # one row
    top = y["mental"] - h["mental"] / 2
    assert top - (y["std"] + h["std"] / 2) <= 150                           # directly under std
    for c in row:                                                           # over its own pair
        assert x[c + "-l"] < x[c] < x[c + "-nl"] or abs(x[c] - (x[c + "-l"] + x[c + "-nl"]) / 2) < 1
    lane = x["breach"]                                                      # breach's line
    assert all(not (x[i] - plan["w"][i] / 2 < lane < x[i] + plan["w"][i] / 2)
               for i in row + [c + s for c in row for s in ("-l", "-nl")])
    check = placement_check(ns, plan, y, x, h)
    assert check["overlaps"] == [] and check["off_margin"] == []


# ── shift: a card dragged in manual edit mode ────────────────────────────────

def _shift_case():
    ns = _negligence() + [_n("r2", act=1), _n("a2", "r2", 1), _n("a2-l", "a2", 1)]
    hints = {"hub": {"arrange": "row"}, "breach": {"shift": [120, 340]},
             "custom": {"shift": [-30, 15]}, "a2": {"shift": [-200, -20]}}
    b = _brief(placement=hints)
    place(b, ns)
    return ns, hints


def _under(par, i, top):
    while i:
        if i == top:
            return True
        i = par.get(i)
    return False


def _clash(y, x, h, w, a, b, gap=40):
    """Two cards closer than the room make_room keeps between them."""
    from alto.build.layout import ROOM_HGAP
    return (abs(x[a] - x[b]) < (w[a] + w[b]) / 2 + ROOM_HGAP
            and y[a] - h[a] / 2 < y[b] + h[b] / 2 + gap
            and y[a] + h[a] / 2 + gap > y[b] - h[b] / 2)


def test_a_shift_moves_the_card_and_its_progeny_and_the_rest_make_room():
    ns, hints = _shift_case()
    h = {n.id: 110 + (len(n.id) % 5) * 23 for n in ns}
    base = {k: {kk: vv for kk, vv in v.items() if kk != "shift"} for k, v in hints.items()}
    y0, x0, _ = run_plan(outline_plan(ns, 2, base), ns, h)
    plan = outline_plan(ns, 2, hints)
    y1, x1, _ = run_plan(plan, ns, h)
    par = {n.id: n.parent for n in ns}
    act0 = [n.id for n in ns if n.act == 0]
    moved = [i for i in act0 if _under(par, i, "breach") or _under(par, i, "custom")]
    for i in moved:
        dx = (120 if _under(par, i, "breach") else 0) + (-30 if _under(par, i, "custom") else 0)
        dy = (340 if _under(par, i, "breach") else 0) + (15 if _under(par, i, "custom") else 0)
        assert x1[i] == pytest.approx(x0[i] + dx), i
        assert y1[i] == pytest.approx(y0[i] + dy), i
    # every other card is where it was, or out of the dragged cards' way
    for i in act0:
        if i in moved:
            continue
        assert x1[i] == pytest.approx(x0[i]), i
        for j in moved:
            assert not _clash(y1, x1, h, plan["w"], i, j), (i, j)
    assert any(y1[i] != pytest.approx(y0[i]) for i in act0 if i not in moved)
    # the next unit starts below whatever the shift pushed lower
    low0 = max(y1[i] + h[i] / 2 for i in act0)
    assert min(y1[i] - h[i] / 2 for i in ("r2", "a2", "a2-l")) > low0
    assert x1["a2-l"] == pytest.approx(x0["a2-l"] - 200)


def test_cards_that_made_room_go_back_once_the_card_moves_on():
    ns, hints = _shift_case()
    h = {n.id: 110 + (len(n.id) % 5) * 23 for n in ns}
    plain = {"hub": {"arrange": "row"}}
    y0, x0, _ = run_plan(outline_plan(ns, 2, plain), ns, h)
    # dragged far down, past everything: nothing is in its way, nothing moves
    far = dict(plain, custom={"shift": [0, 4000]})
    y1, x1, _ = run_plan(outline_plan(ns, 2, far), ns, h)
    par = {n.id: n.parent for n in ns}
    for n in ns:
        if n.act == 0 and not _under(par, n.id, "custom"):
            assert y1[n.id] == pytest.approx(y0[n.id]), n.id
    # dropped onto another card: that card moves; dragged on again, it is back
    on = dict(plain, custom={"shift": [x0["risks"] - x0["custom"], y0["risks"] - y0["custom"] + 10]})
    y2, _, _ = run_plan(outline_plan(ns, 2, on), ns, h)
    assert y2["risks"] != pytest.approx(y0["risks"])


def test_a_card_dropped_on_the_lower_half_of_another_lifts_it_if_there_is_room():
    from alto.build.layout import make_room
    y = {"a": 300.0, "b": 600.0, "m": 340.0}
    x = {"a": 850.0, "b": 850.0, "m": 850.0}
    h = {"a": 100.0, "b": 100.0, "m": 100.0}
    w = {"a": 270, "b": 270, "m": 270}
    make_room(y, x, h, w, ["a", "b", "m"], {"m"}, {}, 40, 0)
    assert y["a"] == pytest.approx(340 - 50 - 40 - 50)           # lifted over it
    assert y["b"] == pytest.approx(600)                          # never in the way
    y = {"a": 300.0, "m": 340.0}
    make_room(y, x, h, w, ["a", "m"], {"m"}, {}, 40, 260)          # no room above
    assert y["a"] == pytest.approx(340 + 50 + 40 + 50)


def test_no_shift_leaves_the_plan_as_it_was():
    ns, hints = _shift_case()
    base = {k: {kk: vv for kk, vv in v.items() if kk != "shift"} for k, v in hints.items()}
    plan = outline_plan(ns, 2, base)
    assert "shift" not in plan and "shift" not in plan_js(plan)


SHIFTS = [None, {"risks": [240, 0]}, {"cause": [-240, -200], "dam": [-600, 40]},
          {"alt": [-120, -500]}, {"breach": [0, -260], "prox": [-360, 300]}]


@needs_node
@pytest.mark.parametrize("extra", SHIFTS)
def test_the_browser_shifts_exactly_as_the_builder_does(tmp_path, extra):
    ns, hints = _shift_case()
    if extra:
        hints = {**hints, **{k: {**hints.get(k, {}), "shift": v} for k, v in extra.items()}}
    plan = outline_plan(ns, 2, hints)
    h = {n.id: 110 + (len(n.id) % 5) * 23 for n in ns}
    y, x, _ = run_plan(plan, ns, h)
    kids = outline_kids(ns)
    js = ("var window=globalThis; var document={documentElement:{classList:{contains:function(){return false;}}},"
          "getElementById:function(){return null;}};\n"
          f"var NODES={json.dumps([{'id': n.id} for n in ns])};\n"
          f"var NODE_ACT={json.dumps({n.id: n.act for n in ns})};\n"
          "window._ALTO_OUTLINE={kids:" + json.dumps(kids) + ",parent:"
          + json.dumps({n.id: n.parent for n in ns if n.parent}) + "};\n"
          + dx.tree_glue(plan_js(plan)) + "\n"
          f"var pos={{}}, h={json.dumps(h)}; window._altoTree(pos,h);\n"
          "console.log(JSON.stringify({y:pos, etx:window._altoEdgeTX, x:Object.fromEntries(NODES.map(function(n){return [n.id,n.displayX];}))}));")
    f = tmp_path / "plan.js"
    f.write_text(js, encoding="utf-8")
    out = json.loads(subprocess.check_output([NODE, str(f)], timeout=60))
    for n in ns:
        assert out["y"][n.id] == pytest.approx(y[n.id]), n.id
        assert out["x"][n.id] == pytest.approx(x[n.id]), n.id
    from alto.build.layout import shift_offsets
    off = shift_offsets(plan["shift"], {n.id: n.parent for n in ns})
    for k, v in plan["etx"].items():
        assert out["etx"][k] == pytest.approx(v + off.get(k.split("|")[1], (0, 0))[0]), k


def test_a_bad_shift_is_refused():
    for bad in ([1], "up", [1, "x"], [5000, 0], [0, 99999], {"dx": 1}):
        with pytest.raises(BriefError, match="shift"):
            validate_brief(_brief(placement={"a": {"shift": bad}}))
    validate_brief(_brief(placement={"a": {"shift": [-40, 300.5]}}))
