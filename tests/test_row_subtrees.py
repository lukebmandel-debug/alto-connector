"""In a row band every child's sub-cards hang straight below THAT child, side by side with its
neighbours' (never one subtree stacked beneath another), and the world widens (the page's Extend
room, plan["extend"]) only when the subtrees together are wider than the page."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import torts_fixture as tf  # noqa: E402
from alto.build.builder import load_brief  # noqa: E402
from alto.build.layout import (TREE, WORLD_W, line_crossings, outline_kids, outline_plan,  # noqa: E402
                               placement_check, run_plan)

H = 150
BRANCHES = list(tf._BRANCHES)


def _plan(child_w=190, nested=("breach", "defenses"), h=H):
    d = tf.negligence_brief(child_w, nested)
    brief, nodes, _ = load_brief(d)
    plan = outline_plan(nodes, len(brief.acts), brief.placement)
    heights = {n.id: h for n in nodes}
    y, x, world = run_plan(plan, nodes, heights)
    return nodes, plan, y, x, heights


def _boxes(plan, y, x, heights):
    return {i: (x[i] - plan["w"].get(i, TREE["CARD_W"]) / 2, y[i] - heights[i] / 2,
                x[i] + plan["w"].get(i, TREE["CARD_W"]) / 2, y[i] + heights[i] / 2) for i in y}


def _desc(nodes, i):
    kids = outline_kids(nodes)
    out, q = [], list(kids.get(i, []))
    while q:
        c = q.pop()
        out.append(c)
        q += kids.get(c, [])
    return out


@pytest.mark.parametrize("nested", [(), ("breach", "defenses"), tuple(BRANCHES)])
def test_each_branchs_first_sub_cards_sit_straight_under_it(nested):
    nodes, plan, y, x, heights = _plan(nested=nested)
    for br in BRANCHES:
        first = min(y[k.id] - H / 2 for k in nodes if k.parent == br)
        # column rule: the first sub-card top is at most one band gap under the branch's bottom
        assert first <= y[br] + H / 2 + TREE["GROUP_GAP"] + 1, (br, first, y[br])


@pytest.mark.parametrize("nested", [(), ("breach", "defenses"), tuple(BRANCHES)])
def test_sibling_subtrees_sit_side_by_side_each_under_its_own_parent(nested):
    nodes, plan, y, x, heights = _plan(nested=nested)
    bx = _boxes(plan, y, x, heights)
    span = {}
    for br in BRANCHES:
        ids = _desc(nodes, br)
        span[br] = (min(bx[i][0] for i in ids), max(bx[i][2] for i in ids))
        # the subtree is centred on, or at least hangs across, its own branch's column
        assert span[br][0] - 1 <= x[br] <= span[br][1] + 1, br
    order = sorted(BRANCHES, key=lambda b: x[b])
    for a, b in zip(order, order[1:]):
        assert span[a][1] <= span[b][0] + 1, (a, b, span[a], span[b])   # no two subtrees share any width
    assert order == BRANCHES or sorted(order) == sorted(BRANCHES)


@pytest.mark.parametrize("nested", [(), ("breach", "defenses"), tuple(BRANCHES)])
def test_no_overlaps_and_no_line_crosses_a_card(nested):
    nodes, plan, y, x, heights = _plan(nested=nested)
    check = placement_check(nodes, plan, y, x, heights)
    assert check["overlaps"] == [] and check["off_margin"] == []
    edges = [(n.parent, n.id) for n in nodes if n.parent]
    base = line_crossings(edges, x, y, heights, True)
    assert base == 0, base


def test_the_world_widens_only_when_the_subtrees_need_more_than_the_page():
    # plain columns: one sub-card column per branch fits the page, nothing is widened
    nodes, plan, y, x, heights = _plan(nested=())
    assert plan["extend"] == 0
    assert all(TREE["MARGIN"] - 1 <= v - plan["w"].get(i, 270) / 2 and v + plan["w"].get(i, 270) / 2 <= WORLD_W - TREE["MARGIN"] + 1
               for i, v in x.items())
    # rows of their own: wider than the page, so the room opens (half each side)
    nodes, plan, y, x, heights = _plan(nested=tuple(BRANCHES))
    assert plan["extend"] > 0
    lo = min(x[i] - plan["w"].get(i, 270) / 2 for i in x)
    hi = max(x[i] + plan["w"].get(i, 270) / 2 for i in x)
    assert lo < TREE["MARGIN"] and hi > WORLD_W - TREE["MARGIN"]
    assert lo >= TREE["MARGIN"] - plan["extend"] / 2 - 1 and hi <= WORLD_W - TREE["MARGIN"] + plan["extend"] / 2 + 1
    # the page's own room: the root stays on the centre line
    assert x["negligence"] == pytest.approx(TREE["CX"])


def test_a_widened_unit_leaves_the_others_as_they_were():
    d = tf.negligence_brief(nested=tuple(BRANCHES))
    brief, nodes, _ = load_brief(d)
    plan = outline_plan(nodes, 2, brief.placement)
    assert plan["x"]["strict"] == TREE["CX"] and plan["extend"] > 0
    for k in ("strict-animals", "strict-abnormally", "strict-products"):
        assert TREE["MARGIN"] <= plan["x"][k] - plan["w"][k] / 2 + 1
        assert plan["x"][k] + plan["w"][k] / 2 <= WORLD_W - TREE["MARGIN"] + 1


def test_hints_keep_working_inside_a_band():
    d = tf.negligence_brief()
    d["brief"]["placement"]["duty"] = {"order": 1, "shift": [0, 0]}
    brief, nodes, _ = load_brief(d)
    plan = outline_plan(nodes, len(brief.acts), brief.placement)
    assert plan["x"]["negligence"] == TREE["CX"] and "duty" in plan["x"]
