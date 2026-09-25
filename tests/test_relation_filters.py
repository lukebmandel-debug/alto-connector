"""Relation chips are filters now: they sit with the filter groups, dim the
cards a relation never touches, and stack with the slot filters.

Two rules drive this:

  * a chip has to divide the set. One matching every node changes nothing when
    clicked; one matching none is dead. Both are dropped, with a warning — which
    is what removes a structural spine ("Contains" touches every node in its
    band) without special-casing it.
  * relation state is deliberately NOT one of the engine's two filter slots. A
    slot is single-valued per node, and a concept legitimately sits in several
    relations at once, so a slot would silently keep only the first.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import load_brief, build_timeline  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"
OUTLINE = ROOT / "samples" / "outline_brief.json"


def _build(path=SAMPLE, mutate=None):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if mutate:
        mutate(d)
    return build_timeline(*load_brief(d))


def _nav(html):
    return html.split('<div id="nav">', 1)[1].split("\n  </div>", 1)[0]


# ── placement ───────────────────────────────────────────────────────────────

def test_relation_chips_live_in_the_filter_panel_not_the_nav():
    html, _ = _build()
    from panel import item_ids
    assert item_ids(html, "lines")
    assert 'Filter · Lines' not in _nav(html)
    assert "line-key-btn" not in _nav(html)


def test_relation_chips_do_not_wear_the_engines_filter_class():
    """`.filter-btn` is swept by the engine's own _applyActiveFilters and its
    clear-all, keyed off data-axis/data-value these chips do not have. Wearing
    it made a slot-filter click light a relation chip too. The panel builds the
    chips with `line-key-btn` and never `filter-btn`."""
    html, _ = _build()
    build = html.split("if(s.kind==='lines'){", 1)[1].split("}", 1)[0]
    assert "line-key-btn" in build and "filter-btn" not in build


# ── the no-op rule ──────────────────────────────────────────────────────────

def test_a_relation_touching_every_node_is_dropped_with_a_warning():
    """Every node in the sample is on the spine, so a spine chip would light
    everything."""
    def mutate(d):
        # All but one edge on the spine, so the spine touches every node. The
        # lone coloured relation has to stay: the spine only joins the key when
        # there is a coloured relation to tell it apart from (blocks.py), and a
        # chip that never renders cannot be dropped.
        d["connections"] = [[c[0], c[1], "spine"] for c in d["connections"]]
        d["connections"].append(["lucy-v-zehmer", "hamer", "cites"])
        d["brief"]["relations"] = [{"key": "spine", "label": "Contains"},
                                   {"key": "cites", "label": "Cites",
                                    "color": "#a78bfa"}]
    html, report = _build(mutate=mutate)
    assert any("matches every node" in w and "Contains" in w
               for w in report["warnings"])
    from panel import item_ids
    assert "spine" not in item_ids(html, "lines")


def test_a_partitioning_relation_survives():
    html, report = _build()
    from panel import item_ids
    assert "cites" in item_ids(html, "lines")
    assert not any("cites" in w.lower() and "dropped" in w
                   for w in report["warnings"])


def test_a_slot_filter_value_matching_everything_is_dropped():
    """The rule is general, not a spine special case: give every node the same
    custom value and the whole filter stops partitioning."""
    def mutate(d):
        d["brief"]["filters"] = [{
            "id": "imp", "label": "Importance", "source": "custom",
            "values": [{"id": "heavy", "name": "Heavy"},
                       {"id": "light", "name": "Light"}]}]
        for n in d["nodes"]:
            n["filters"] = {"imp": "heavy"}
    html, report = _build(mutate=mutate)
    assert any("matches every node" in w for w in report["warnings"])
    assert any("matches no nodes" in w for w in report["warnings"])
    from panel import slot_ids
    assert slot_ids(html, "era") == [] and slot_ids(html, "weight") == []


# ── the runtime half ────────────────────────────────────────────────────────

def test_the_node_map_and_glue_ship_when_there_are_relation_chips():
    html, _ = _build()
    assert "var REL_NODES=" in html
    assert "_altoRelFilterBound" in html
    assert "rel-dimmed" in html


def test_relation_dimming_uses_its_own_class():
    """Two writers on the engine's `dimmed` class is the fight LINES_GLUE's
    comment warned about. Separate classes compose instead."""
    html, _ = _build()
    assert ".node-card.rel-dimmed > *{opacity:0.15;}" in html
    # ...and the compass hop knows about both, so arrow-hopping skips them
    assert "_c.classList.contains('rel-dimmed')" in html


def test_the_node_map_lists_only_nodes_the_relation_touches():
    html, _ = _build()
    rel = html.split("var REL_NODES=", 1)[1].split("};", 1)[0]
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    expected = {c[0] for c in d["connections"] if c[2] == "cites"} | \
               {c[1] for c in d["connections"] if c[2] == "cites"}
    for nid in expected:
        assert nid in rel


def test_no_relation_chips_means_no_relation_machinery():
    """A brief with nothing to filter by pays nothing for the feature."""
    def mutate(d):
        d["brief"]["relations"] = []
        d["connections"] = []          # else verify rejects the orphan keys
    html, _ = _build(mutate=mutate)
    for marker in ("REL_NODES", "_altoRelFilterBound",
                   ".node-card.rel-dimmed"):
        assert marker not in html
    # The compass-hop guard is an engine patch, not a feature toggle — it is
    # applied to every build and simply never sees the class.
    assert "_c.classList.contains('rel-dimmed')" in html


@pytest.mark.skipif(not OUTLINE.exists(), reason="outline sample not present")
def test_the_outline_sample_keeps_only_relations_that_partition():
    html, report = _build(OUTLINE)
    from panel import item_ids
    assert "spine" not in item_ids(html, "lines")          # Contains — every node
    assert "limits" in item_ids(html, "lines")
    assert "substitutes" in item_ids(html, "lines")
    assert any("Contains" in w and "matches every node" in w
               for w in report["warnings"])


# ── the derived depth source ────────────────────────────────────────────────

def _depth_build(path=OUTLINE):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    d["brief"]["filters"] = [{"id": "depth", "label": "Depth",
                              "source": "depth"}]
    return build_timeline(*load_brief(d))


@pytest.mark.skipif(not OUTLINE.exists(), reason="outline sample not present")
def test_depth_puts_each_band_root_at_level_one():
    from alto.build.blocks import resolve_filters
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    d["brief"]["filters"] = [{"id": "depth", "label": "Depth",
                              "source": "depth"}]
    brief, nodes, conns = load_brief(d)
    rf = resolve_filters(brief, nodes, conns)[0]
    roots = {nid for nid, v in rf["node_value"].items() if v == "d1"}
    # In outline mode the tree is authored on the nodes; the spine edges are
    # generated from it later, so depth must read `parent` rather than depend
    # on when in the build it is called.
    assert roots == {n.id for n in nodes if not n.parent}
    assert len(roots) == len(brief.acts)          # one family root per band


@pytest.mark.skipif(not OUTLINE.exists(), reason="outline sample not present")
def test_depth_labels_and_covers_every_node():
    from alto.build.blocks import resolve_filters
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    d["brief"]["filters"] = [{"id": "depth", "label": "Depth",
                              "source": "depth"}]
    brief, nodes, conns = load_brief(d)
    rf = resolve_filters(brief, nodes, conns)[0]
    assert [v for _, v in rf["values"]] == ["Level 1", "Level 2", "Level 3+"]
    assert set(rf["node_value"]) == {n.id for n in nodes}


def test_depth_collapses_to_two_levels_when_nothing_is_deeper():
    """The Level 3+ chip only exists if something reaches it — otherwise it
    would match no nodes and the no-op rule would drop it anyway."""
    from alto.build.blocks import resolve_filters
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    d["brief"]["filters"] = [{"id": "depth", "label": "Depth",
                              "source": "depth"}]
    brief, nodes, conns = load_brief(d)
    conns = [["lucy-v-zehmer", "carbolic", "spine"]]
    rf = resolve_filters(brief, nodes, conns)[0]
    assert [v for _, v in rf["values"]] == ["Level 1", "Level 2"]


def test_depth_survives_an_authored_cycle():
    """A cycle in the connections must not hang the build."""
    from alto.build.blocks import resolve_filters
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    d["brief"]["filters"] = [{"id": "depth", "label": "Depth",
                              "source": "depth"}]
    brief, nodes, _ = load_brief(d)
    cyclic = [["hamer", "kirksey", "spine"], ["kirksey", "hamer", "spine"]]
    rf = resolve_filters(brief, nodes, cyclic)[0]
    assert set(rf["node_value"]) == {n.id for n in nodes}
