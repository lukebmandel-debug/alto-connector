"""An outline's desktop layout is a tree (layout.outline_tree): each band's root
on top, its sections side by side as branches, every concept down its branch's
spine with its first two leaves flanking it. The browser re-runs the same
algorithm over measured heights (detail_extras.TREE_GLUE); a test here runs
that JS under node and holds it to the Python."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.brief import Brief, Node  # noqa: E402
from alto.build.builder import load_brief, build_timeline, place  # noqa: E402
from alto.build import detail_extras as dx  # noqa: E402
from alto.build.layout import (TREE, outline_flanks, outline_kids,  # noqa: E402
                               outline_tree)

NODE = shutil.which("node") or str(Path.home() / ".local/node/bin/node")
needs_node = pytest.mark.skipif(not Path(NODE).is_file(), reason="needs node")
OUTLINE = ROOT / "samples" / "outline_brief.json"


def _n(i, parent=None, act=0):
    return Node(id=i, act=act, tag="Concept", title=i, desc="d " * 20,
                parent=parent)


def _torts_shape():
    """The Torts band I: two sections side by side, concepts with L/NL, and a
    leaf (Trespass to Chattels) directly under a section."""
    ns = [_n("it")]
    for sec, concepts in (("battery", ["intent", "minreq", "consent"]),
                          ("trespass", ["land", "chattels", "conversion"])):
        ns.append(_n(sec, "it"))
        for c in concepts:
            ns.append(_n(c, sec))
            if c != "chattels":
                ns += [_n(c + "-l", c), _n(c + "-nl", c)]
    return ns


def _heights(ns, h=150):
    return {n.id: h for n in ns}


def _box(n, y, x, h, flanks):
    w = TREE["FLANK_W"] if n.id in flanks else 270
    return (x[n.id] - w / 2, y[n.id] - h[n.id] / 2, x[n.id] + w / 2, y[n.id] + h[n.id] / 2)


def test_sections_become_side_by_side_branches_with_flanking_outcomes():
    ns = _torts_shape()
    h = _heights(ns)
    y, x, _ = outline_tree(ns, 1, h)
    T = TREE
    assert x["it"] == T["CX"]
    assert (x["battery"], x["trespass"]) == tuple(T["BRANCH_X"])
    assert y["battery"] == y["trespass"]                   # side by side
    for c in ("intent", "minreq", "consent"):
        assert x[c] == x["battery"]                        # one spine
        assert x[c + "-l"] == x[c] - T["FLANK_DX"]         # Liable left
        assert x[c + "-nl"] == x[c] + T["FLANK_DX"]        # Not Liable right
        assert y[c + "-l"] == y[c] == y[c + "-nl"]         # one row: straight lines
    assert x["chattels"] == x["trespass"]                  # a leaf under a section: spine
    assert y["intent"] < y["minreq"] < y["consent"]        # authored order, down
    assert y["land"] < y["chattels"] < y["conversion"]


def test_no_two_cards_overlap_and_every_hub_is_above_its_children():
    ns = _torts_shape()
    h = _heights(ns)
    y, x, _ = outline_tree(ns, 1, h)
    fl = outline_flanks(ns)
    boxes = {n.id: _box(n, y, x, h, fl) for n in ns}
    ids = list(boxes)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            A, B = boxes[a], boxes[b]
            assert not (A[0] < B[2] and B[0] < A[2] and A[1] < B[3] and B[1] < A[3]), (a, b)
    for n in ns:
        if n.parent and n.id not in fl:
            assert boxes[n.id][1] > boxes[n.parent][3], n.id
    assert all(0 <= boxes[i][0] and boxes[i][2] <= 1700 for i in ids)


def test_a_third_branch_starts_a_new_row_and_direct_concepts_form_a_branch():
    ns = [_n("root")]
    for s in ("a", "b", "c"):
        ns += [_n(s, "root"), _n(s + "1", s), _n(s + "1-l", s + "1")]
    ns += [_n("direct", "root"), _n("direct-l", "direct")]
    h = _heights(ns)
    y, x, _ = outline_tree(ns, 1, h)
    assert (x["a"], x["b"]) == tuple(TREE["BRANCH_X"]) and y["a"] == y["b"]
    # c and the root's own concept pair up on the next row
    assert (x["c"], x["direct"]) == tuple(TREE["BRANCH_X"])
    assert y["c"] - h["c"] / 2 > y["a1"] + h["a1"] / 2


def test_bands_stack_with_the_act_gap():
    ns = [_n("r0"), _n("k0", "r0"), _n("r1", act=1), _n("k1", "r1", act=1)]
    h = _heights(ns)
    y, _, _ = outline_tree(ns, 2, h)
    bottom0 = max(y[i] + h[i] / 2 for i in ("r0", "k0"))
    assert y["r1"] - h["r1"] / 2 == pytest.approx(bottom0 + TREE["ACT_GAP"])


def test_children_keep_the_order_the_material_gives_them():
    """Leaves used to be pulled ahead of sibling concepts, which renumbered
    Torts' Trespass to Chattels (a leaf) ahead of Trespass to Land."""
    ns = _torts_shape()
    b = Brief(title="t", subject="t", mode="outline", columns=5,
              acts=[{"label": "I"}], timeline_id="t")
    place(b, ns)
    assert outline_kids(ns)["trespass"] == ["land", "chattels", "conversion"]


@needs_node
def test_the_browser_tree_matches_the_builder(tmp_path):
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    b, nodes, _ = load_brief(d)
    place(b, nodes)
    h = {n.id: 100 + (len(n.desc) % 7) * 20 for n in nodes}
    y, x, _ = outline_tree(nodes, len(b.acts), h)
    kids = outline_kids(nodes)
    acts = [[n.id for n in nodes if n.act == a] for a in range(len(b.acts))]
    js = ("var window=globalThis; var document={documentElement:{classList:{contains:function(){return false;}}},"
          "getElementById:function(){return null;}};\n"
          f"var ACT_SEQS={json.dumps(acts)}; var NODES={json.dumps([{'id': n.id} for n in nodes])};\n"
          "window._ALTO_OUTLINE={kids:" + json.dumps(kids) + ",parent:"
          + json.dumps({n.id: n.parent for n in nodes if n.parent}) + "};\n"
          + dx.tree_glue(TREE, "fan") + "\n"
          f"var pos={{}}, h={json.dumps(h)}; window._altoTree(pos,h);\n"
          "console.log(JSON.stringify({y:pos, etx:window._altoEdgeTX, x:Object.fromEntries(NODES.map(function(n){return [n.id,n.displayX];}))}));")
    f = tmp_path / "tree.js"
    f.write_text(js, encoding="utf-8")
    out = json.loads(subprocess.check_output([NODE, str(f)], timeout=60))
    for n in nodes:
        assert out["y"][n.id] == pytest.approx(y[n.id]), n.id
        assert out["x"][n.id] == pytest.approx(x[n.id]), n.id
    # fan: offer's spine children would be its leaves' — pick a real spine,
    # the root's children: first at the centre, then left, right, …
    root = next(n.id for n in nodes if not n.parent)
    ks = kids[root]
    bx = x[ks[0]]
    offs = [out["etx"].get(root + "|" + k, bx) - bx for k in ks]
    assert offs[0] == 0 and offs[1] < 0 < offs[2]
    assert offs[1] == -offs[2] and abs(offs[3]) == 2 * abs(offs[1])


def test_flank_cards_are_narrower_on_desktop_only():
    html, _ = build_timeline(*load_brief(json.loads(OUTLINE.read_text(encoding="utf-8"))))
    assert f"{{width:{TREE['FLANK_W']}px;}}" in html
    assert "html:not(.mobile) #node-revocation .node-card" in html


def test_a_tree_spine_is_one_straight_trunk_in_the_router():
    html, _ = build_timeline(*load_brief(json.loads(OUTLINE.read_text(encoding="utf-8"))))
    assert "_lane = window._altoTreeOn ? null" in html
    assert "_lr = window._altoTreeOn ? null" in html
    assert "if(window._altoTreeMid) window._altoTreeMid(forcedMid);" in html
    assert "(n.displayX !== undefined) ? n.displayX : COL_X[n.col]" in html


def _brief(**kw):
    return Brief(title="t", subject="t", mode=kw.pop("mode", "outline"), columns=5,
                 acts=[{"label": "I"}, {"label": "II"}], timeline_id="t", **kw)


def test_layout_options_are_validated():
    from alto.build.brief import BriefError, validate_brief
    for bad in ({"layout": "grid"}, {"tree_lines": "curvy"}):
        with pytest.raises(BriefError):
            validate_brief(_brief(**bad))
    with pytest.raises(BriefError):
        validate_brief(_brief(mode="linear", layout="tree"))


def test_auto_takes_the_tree_only_when_the_outline_has_categories():
    from alto.build.builder import run_layout
    # Torts-shaped: concepts with outcomes → tree
    ns = _torts_shape()
    rep = run_layout(_brief(), ns, [])[5]
    assert rep["layout"] == "tree" and rep["categories"]
    # a flat list under one root: nothing for a tree to show → flow
    flat = [_n("r")] + [_n(f"k{i}", "r") for i in range(6)]
    rep = run_layout(_brief(), flat, [])[5]
    assert rep["layout"] == "flow" and not rep["categories"]
    # forced either way
    assert run_layout(_brief(layout="tree"), [_n("r")] + [_n(f"k{i}", "r") for i in range(6)], [])[5]["layout"] == "tree"
    assert run_layout(_brief(layout="flow"), _torts_shape(), [])[5]["layout"] == "flow"


def test_line_crossings_counts_a_crossing_and_ignores_shared_ends():
    from alto.build.layout import line_crossings
    xs = {"a": 0, "b": 100, "c": 50, "d": 50}
    ys = {"a": 0, "b": 200, "c": -100, "d": 300}
    h = {k: 10 for k in xs}
    # a→b turns across at y=100; c→d runs straight down x=50 through it
    assert line_crossings([("a", "b"), ("c", "d")], xs, ys, h, False) == 1
    assert line_crossings([("a", "b"), ("a", "d")], xs, ys, h, False) == 0


def test_side_by_side_branches_keep_a_clear_margin_at_both_edges():
    """Two branches side by side, each with a concept of five leaves: every
    card, including the leaves on rows below the concept, stays well inside
    the 1700px world (clear of the page's right-edge rail), and the leaves
    below the first row are narrow flank cards too, not full-width ones."""
    ns = [_n("root")]
    for s in ("a", "b"):
        ns += [_n(s, "root"), _n(s + "c", s)]
        ns += [_n(f"{s}c{k}", s + "c") for k in range(5)]
    h = _heights(ns)
    y, x, _ = outline_tree(ns, 1, h)
    fl = outline_flanks(ns)
    assert {f"ac{k}" for k in range(5)} <= fl
    boxes = {n.id: _box(n, y, x, h, fl) for n in ns}
    assert all(b[0] >= 100 and b[2] <= 1600 for b in boxes.values()), boxes
    ids = list(boxes)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            A, B = boxes[a], boxes[b]
            assert not (A[0] < B[2] and B[0] < A[2] and A[1] < B[3] and B[1] < A[3]), (a, b)
