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


@pytest.mark.parametrize("nested", [()])
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
    from test_outline_placement import _n
    # three branches with a short stack each fit the page: nothing is widened
    ns = [_n("hub")] + [_n("b%d" % i, "hub") for i in range(3)]
    for i in range(3):
        ns += [_n("b%d-l" % i, "b%d" % i, tag="Outcome"), _n("b%d-nl" % i, "b%d" % i, tag="Outcome")]
    small = outline_plan(ns, 1, {"hub": {"arrange": "row"}})
    assert small["wide"] == 0
    # Negligence side by side at every level is wider than the page, so the board opens to the right
    nodes, plan, y, x, heights = _plan()
    assert plan["wide"] > 0
    hi = max(x[i] + plan["w"].get(i, 270) / 2 for i in x)
    assert hi > WORLD_W - TREE["MARGIN"]


def test_siblings_sit_side_by_side_at_every_level_one_y_no_overlap():
    # (rule chosen: a card's own outcomes, leaves with nothing under them, stay a short stack under it;
    # every other group of siblings, at every level of a branch, is one row)
    nodes, plan, y, x, heights = _plan()
    kids = outline_kids(nodes)
    checked = 0
    for p, ks in kids.items():
        if p == "strict" or p.startswith("strict-") or len(ks) < 2:
            continue
        if all(not kids.get(k) for k in ks) and p != "negligence":
            continue                                   # an outcome stack
        tops = [y[k] - heights[k] / 2 for k in ks]
        assert max(tops) - min(tops) <= 2, (p, tops)
        bx = _boxes(plan, y, x, heights)
        order = sorted(ks, key=lambda k: x[k])
        for a, b in zip(order, order[1:]):
            assert bx[a][2] <= bx[b][0] + 1, (p, a, b)
        checked += 1
    assert checked >= 5


def test_no_card_is_narrower_than_its_normal_width():
    nodes, plan, y, x, heights = _plan()
    assert all(plan["w"].get(i, 270) >= 190 for i in y)


@pytest.mark.parametrize("nested", [(), ("breach", "defenses"), tuple(BRANCHES)])
def test_no_card_left_of_the_margin_or_under_the_right_rail(nested):
    nodes, plan, y, x, heights = _plan(nested=nested)
    world = WORLD_W + plan["wide"]
    for i in y:
        lo, hi = x[i] - plan["w"].get(i, 270) / 2, x[i] + plan["w"].get(i, 270) / 2
        assert lo >= TREE["MARGIN"] - 1, (i, lo)
        assert hi <= world - TREE["MARGIN"] + 1, (i, hi, world)   # rail (about 50 px) + 20 stays clear


@pytest.mark.parametrize("nested", [(), ("breach", "defenses"), tuple(BRANCHES)])
def test_each_branch_is_centred_over_its_own_subtree(nested):
    nodes, plan, y, x, heights = _plan(nested=nested)
    bx = _boxes(plan, y, x, heights)
    for br in BRANCHES:
        ids = _desc(nodes, br)
        centre = (min(bx[i][0] for i in ids) + max(bx[i][2] for i in ids)) / 2
        if len(ids) > 0 and any(plan["w"].get(i, 270) for i in ids):
            assert abs(x[br] - centre) <= 2, (br, x[br], centre)


@pytest.mark.parametrize("nested", [(), ("breach", "defenses"), tuple(BRANCHES)])
def test_the_hub_is_centred_over_its_branch_row(nested):
    nodes, plan, y, x, heights = _plan(nested=nested)
    xs = [x[b] for b in BRANCHES]
    assert abs(x["negligence"] - (min(xs) + max(xs)) / 2) <= 2


def test_child_w_carries_down_so_a_level_has_one_width():
    nodes, plan, y, x, heights = _plan(nested=("breach", "defenses"))
    for n in nodes:
        if n.id.startswith("strict") or n.id == "negligence":
            continue
        if n.tag != "Outcome":
            assert plan["w"].get(n.id, 270) <= 190, (n.id, plan["w"].get(n.id))
    d = tf.negligence_brief(190, ("breach",))
    d["brief"]["placement"]["breach"] = {"arrange": "row", "child_w": 210}
    brief, nodes2, _ = load_brief(d)
    p2 = outline_plan(nodes2, len(brief.acts), brief.placement)
    assert p2["w"]["breach-custom"] == 210            # the nearest band's width wins
    d["brief"]["placement"]["breach-custom"] = {"w": 200}
    brief, nodes2, _ = load_brief(d)
    assert outline_plan(nodes2, len(brief.acts), brief.placement)["w"]["breach-custom"] == 200   # its own hint wins


def test_a_widened_unit_leaves_the_others_as_they_were():
    d = tf.negligence_brief(nested=tuple(BRANCHES))
    brief, nodes, _ = load_brief(d)
    plan = outline_plan(nodes, 2, brief.placement)
    assert plan["x"]["strict"] == TREE["CX"] and plan["wide"] > 0
    for k in ("strict-animals", "strict-abnormally", "strict-products"):
        assert TREE["MARGIN"] <= plan["x"][k] - plan["w"][k] / 2 + 1
        assert plan["x"][k] + plan["w"][k] / 2 <= WORLD_W - TREE["MARGIN"] + 1


def test_hints_keep_working_inside_a_band():
    d = tf.negligence_brief()
    d["brief"]["placement"]["duty"] = {"order": 1, "shift": [0, 0]}
    brief, nodes, _ = load_brief(d)
    plan = outline_plan(nodes, len(brief.acts), brief.placement)
    assert "duty" in plan["x"]


def _browser(pages, steps):
    """Run steps(page) on each named page in headless WebKit, 1440x900, offline."""
    import asyncio
    import phone_matrix as pm
    try:
        pw = pm._playwright()
    except ImportError:
        pytest.skip("Playwright is not installed")
    s = pm.serve(pages, {}, {})

    async def go():
        out = {}
        async with pw.async_playwright() as p:
            b = await p.webkit.launch()
            for name in pages:
                ctx = await b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark")
                pg = await ctx.new_page()
                await pg.goto(f"http://127.0.0.1:{s.server_address[1]}/{name}.html?style=classic", wait_until="load", timeout=45000)
                await pg.wait_for_timeout(3000)
                out[name] = await steps(pg)
                await ctx.close()
            await b.close()
        return out
    try:
        return asyncio.run(go())
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            pytest.skip(f"no WebKit: {e}")
        raise
    finally:
        s.shutdown()


def test_shift_wheel_pans_sideways_and_the_edge_cue_shows_only_where_there_is_more():
    async def steps(pg):
        info = "() => { const c = document.getElementById('canvas'), l = document.getElementById('alto-edge-l'), r = document.getElementById('alto-edge-r');" \
               " return {sl: c.scrollLeft, max: c.scrollWidth - c.clientWidth, l: !!l && l.classList.contains('on'), r: !!r && r.classList.contains('on'), has: !!l}; }"
        out = {"open": await pg.evaluate(info)}
        await pg.evaluate("() => { document.getElementById('canvas').scrollLeft = 0; }")
        await pg.mouse.move(700, 450)
        await pg.keyboard.down("Shift")
        await pg.mouse.wheel(0, 600)
        await pg.keyboard.up("Shift")
        await pg.wait_for_timeout(500)
        out["shift"] = await pg.evaluate(info)
        await pg.evaluate("() => { const c = document.getElementById('canvas'); c.scrollLeft = c.scrollWidth; }")
        await pg.wait_for_timeout(400)
        out["end"] = await pg.evaluate(info)
        await pg.evaluate("() => { document.getElementById('canvas').scrollLeft = 0; }")
        await pg.wait_for_timeout(400)
        out["start"] = await pg.evaluate(info)
        return out
    res = _browser({"wide": tf.page(data=tf.negligence_brief()), "plain": tf.page()}, steps)
    w = res["wide"]
    assert w["open"]["max"] > 500 and w["open"]["sl"] < 5, w["open"]       # opens at the left, with room to the right
    assert w["shift"]["sl"] > 100, w["shift"]                               # shift+wheel pans
    assert w["start"]["r"] and not w["start"]["l"], w["start"]              # cue on the side that has more
    assert w["end"]["l"] and not w["end"]["r"], w["end"]
    assert not res["plain"]["start"]["has"], "a page that fits has no cue"
