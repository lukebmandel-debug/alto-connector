"""Outline mode as a real mode: the brief declares a containment tree, and the
build derives everything else from it.

`Node.parent` is the single source of truth. Placement (which concept is a hub,
which column a leaf takes), the parent→child spokes, the outline numbering and
the depth filter are all derived — never authored twice, so nothing can drift
out of agreement with the tree.
"""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import load_brief, build_timeline, place  # noqa: E402
from alto.build.brief import BriefError  # noqa: E402
from alto.build.layout import outline_spokes  # noqa: E402
from alto.build.verify import VerifyError  # noqa: E402

OUTLINE = ROOT / "samples" / "outline_brief.json"
pytestmark = pytest.mark.skipif(not OUTLINE.exists(),
                                reason="outline sample not present")


def _brief(mutate=None):
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    if mutate:
        mutate(d)
    return d


def _node(d, nid):
    return next(n for n in d["nodes"] if n["id"] == nid)


# ── the tree is rejected when it cannot describe a page ─────────────────────

@pytest.mark.parametrize("label,mutate,expect", [
    ("self-parent",
     lambda d: _node(d, "offer").__setitem__("parent", "offer"), "itself"),
    ("cycle",
     lambda d: _node(d, "formation").__setitem__("parent", "offer"),
     "loops back"),
    ("parent in another band",
     lambda d: _node(d, "offer").__setitem__("parent", "defenses"),
     "same unit"),
    ("two hubs in one band",
     lambda d: _node(d, "offer").__setitem__("parent", ""), "top-level"),
    ("parent that is not a node",
     lambda d: _node(d, "offer").__setitem__("parent", "ghost"),
     "not a node"),
])
def test_a_broken_tree_is_refused(label, mutate, expect):
    with pytest.raises((BriefError, VerifyError), match=expect):
        build_timeline(*load_brief(_brief(mutate)))


def test_a_missing_parent_only_warns_while_nodes_are_still_arriving():
    """add_nodes is a batch upsert, so a child legitimately lands before its
    parent mid-interview. It becomes fatal only once the set is final."""
    from alto.build.brief import validate_nodes
    brief, nodes, _ = load_brief(_brief(
        lambda d: _node(d, "offer").__setitem__("parent", "not-yet")))
    warnings = validate_nodes(brief, nodes)
    assert any("not a node yet" in w for w in warnings)


# ── everything else is derived from it ──────────────────────────────────────

def test_placement_comes_from_the_tree_not_the_brief():
    d = _brief()
    assert not any("col" in n for n in d["nodes"])
    brief, nodes, _ = load_brief(d)
    place(brief, nodes)
    kids = {n.parent for n in nodes if n.parent}
    for n in nodes:
        assert (n.col == "center") == (n.id in kids), n.id


def test_an_authored_column_is_ignored_in_outline_mode():
    """The radial shape is structural, not editorial — a brief must not be able
    to pin a hub off-centre."""
    brief, nodes, _ = load_brief(_brief(
        lambda d: _node(d, "offer").__setitem__("col", "far-left")))
    place(brief, nodes)
    assert next(n for n in nodes if n.id == "offer").col == "center"


def test_spokes_are_generated_one_per_child():
    brief, nodes, conns = load_brief(_brief())
    place(brief, nodes)
    spokes = outline_spokes(nodes, conns)
    derived = [c for c in spokes if c[2] == "spine"]
    assert len(derived) == sum(1 for n in nodes if n.parent)
    assert {(c[0], c[1]) for c in derived} == \
        {(n.parent, n.id) for n in nodes if n.parent}


def test_an_authored_edge_wins_over_the_generated_one():
    """A student who gives a parent→child edge its own meaning keeps it."""
    brief, nodes, conns = load_brief(_brief())
    place(brief, nodes)
    authored = conns + [["formation", "offer", "limits"]]
    spokes = outline_spokes(nodes, authored)
    pairs = [(c[0], c[1]) for c in spokes]
    assert pairs.count(("formation", "offer")) == 1
    assert ["formation", "offer", "limits"] in spokes


def test_the_dfs_puts_each_bands_hub_first():
    brief, nodes, _ = load_brief(_brief())
    place(brief, nodes)
    for act_i in range(len(brief.acts)):
        assert next(n for n in nodes if n.act == act_i).parent == ""


# ── the outline detail page ─────────────────────────────────────────────────

def test_outline_numbering_is_derived_and_nests():
    html, _ = build_timeline(*load_brief(_brief()))
    num = json.loads(html.split("window._ALTO_OUTLINE={num:", 1)[1]
                     .split(",label:", 1)[0])
    assert num["formation"] == "I."
    assert num["offer"].startswith("I.")          # a child of the first band
    assert num["revocation"].startswith(num["offer"])   # and its own child


def test_the_detail_page_builder_and_data_ship():
    html, _ = build_timeline(*load_brief(_brief()))
    assert "_altoOutlineHead" in html and "_altoOutlineTail" in html
    assert "window._ALTO_OUTLINE=" in html
    assert ".ol-row{display:grid" in html


def test_outline_mode_always_ships_the_link_handler():
    """Child links are built at runtime, so they never appear in the emitted
    section text the usual scan looks at."""
    def strip_links(d):
        for n in d["nodes"]:
            n["sections"] = [s for s in n.get("sections", [])
                             if "<a " not in s["t"]]
        d["brief"]["overview_html"] = ""
    html, _ = build_timeline(*load_brief(_brief(strip_links)))
    assert "_altoLinkBound" in html
    assert ".alto-link{display:inline" in html


def test_a_linear_brief_gets_none_of_it():
    d = _brief(lambda d: d["brief"].__setitem__("mode", "linear"))
    # a linear brief ignores `parent`, so give it real spine edges to lay out
    d["connections"] = [["formation", "offer", "spine"]] + d["connections"]
    html, _ = build_timeline(*load_brief(d))
    # The data, the page builders and the styling are all conditional...
    for marker in ("window._ALTO_OUTLINE={", "_altoOutlineHead",
                   ".ol-row{display:grid", "_altoPrintOutline = function"):
        assert marker not in html
    # ...while the two engine hooks that reach them are permanent guards,
    # applied to every build and simply never satisfied here.
    assert "if(window._ALTO_OUTLINE && window._altoPrintOutline)" in html


def test_mode_must_be_one_of_the_two():
    with pytest.raises(BriefError, match="mode"):
        build_timeline(*load_brief(
            _brief(lambda d: d["brief"].__setitem__("mode", "radial"))))
