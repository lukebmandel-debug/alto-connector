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

def test_relation_chips_sit_with_the_filter_groups():
    html, _ = _build()
    assert 'nav-group-label">Filter · Lines</span>' in _nav(html)


def test_relation_chips_do_not_wear_the_engines_filter_class():
    """`.filter-btn` is swept by the engine's own _applyActiveFilters and its
    clear-all, keyed off data-axis/data-value these chips do not have. Wearing
    it made a slot-filter click light a relation chip too."""
    html, _ = _build()
    for chip in _nav(html).split("<button")[1:]:
        if "data-rel-key=" in chip:
            assert "filter-btn" not in chip


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
    assert 'data-rel-key="spine"' not in html


def test_a_partitioning_relation_survives():
    html, report = _build()
    assert 'data-rel-key="cites"' in html
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
    assert 'data-value="heavy"' not in html
    assert 'data-value="light"' not in html


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
    assert 'data-rel-key="spine"' not in html          # Contains — every node
    assert 'data-rel-key="limits"' in html
    assert 'data-rel-key="substitutes"' in html
    assert any("Contains" in w and "matches every node" in w
               for w in report["warnings"])
