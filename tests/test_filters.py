"""Canvas-filter feature: brief → emitted chips/fields, and validation."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import load_brief, build_timeline  # noqa: E402
from alto.build.brief import BriefError, validate_brief, validate_nodes  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"


def _sample(filters=None, node_patch=None):
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    if filters is not None:
        d["brief"]["filters"] = filters
    if node_patch:
        for n in d["nodes"]:
            n.update(node_patch(n))
    return d


def _build(d):
    brief, nodes, conns = load_brief(d)
    return build_timeline(brief, nodes, conns)


def test_no_filters_no_artifacts():
    html, _ = _build(_sample())
    assert 'class="nav-btn filter-btn"' not in html
    assert "var ERA_LABELS" not in html
    assert 'data-sd-axis="era" data-sd-id=' not in html
    assert "era:'" not in html


def test_axis1_filter_emits_chips_fields_labels():
    html, report = _build(_sample(filters=[
        {"id": "court", "label": "Filter by Court", "source": "axis1"}]))
    # nav chips on the era slot
    from panel import sections
    slot = next(s for s in sections(html) if s["kind"] == "slot")
    assert slot["slot"] == "era" and slot["label"] == "Filter by Court"
    assert slot["items"][0] == {"id": "ny", "name": "New York"}
    assert 'class="nav-btn filter-btn"' not in html      # not a nav row any more
    # node fields (first axis1 value)
    assert "era:'ny'" in html
    # label globals + glue
    assert "var ERA_LABELS={'ny':'New York','eng':'England'};" in html
    assert "var WEIGHT_LABELS={};" in html
    assert "_updateDesktopFilterBar" in html
    # and not a drawer section either: the Filter tile opens the same panel
    assert 'data-sd-axis="era" data-sd-id="ny"' not in html
    # nav axis group still present (replace_nav not set)
    assert "'env','ny'" in html


def test_mobile_filter_repatches_the_prev_next_labels():
    """A filter change does not navigate, so the engine never re-runs its
    label patch: without this wrap the mobile prev/next strip goes on naming
    — and linking to — the neighbours the filter just hid."""
    html, _ = _build(_sample(filters=[
        {"id": "court", "label": "Filter by Court", "source": "axis1"}]))
    assert "window.setMobileFilter = function()" in html
    assert "window._patchTimelineLabels()" in html


def test_replace_nav_makes_axis_filter_only():
    html, _ = _build(_sample(filters=[
        {"id": "court", "label": "Court", "source": "axis1",
         "replace_nav": True}]))
    from panel import slot_ids
    assert "ny" in slot_ids(html, "era")                   # filter chips in
    assert "'env','ny'" not in html                        # nav buttons out
    assert 'data-sd-type="env"' not in html                # drawer nav out
    assert "envs:[]" in html and 'envs:["ny"]' not in html  # card chips out
    assert "era:'ny'" in html                              # filtering intact
    assert "background:var(--env-color)" not in html       # legend dot out


def test_non_replaced_filter_keeps_axis_surfaces():
    html, _ = _build(_sample(filters=[
        {"id": "court", "label": "Court", "source": "axis1"}]))
    assert 'envs:["ny"]' in html                           # card chips stay
    assert "background:var(--env-color)" in html           # legend dot stays


def test_entity_and_custom_filters_both_slots():
    d = _sample(
        filters=[
            {"id": "doctrine", "label": "Doctrine", "source": "entity"},
            {"id": "importance", "label": "Importance", "source": "custom",
             "values": [{"id": "heavy", "name": "Heavy"},
                        {"id": "background", "name": "Background"}]}],
        # Split the nodes across both values. Giving every node the same value
        # made this a filter that never partitioned, which the build now drops
        # as a no-op — and then it was testing nothing.
        node_patch=lambda n: {"filters": {
            "importance": "heavy" if n["id"] in ("lucy-v-zehmer", "carbolic")
            else "background"}})
    html, report = _build(d)
    assert "era:'offer'" in html                # entity-derived, era slot
    assert "examWeight:'heavy'" in html         # custom, weight slot
    assert "'heavy':'Heavy'" in html            # WEIGHT_LABELS
    from panel import slot_ids
    assert "background" in slot_ids(html, "weight")


def test_acts_filter_derives_from_act_index():
    html, _ = _build(_sample(filters=[
        {"id": "unit", "label": "Unit", "source": "acts"}]))
    assert "era:'act-1'" in html
    assert "'act-2':'Unit Two" in html          # ERA_LABELS from act.short


def test_custom_unassigned_node_warns():
    d = _sample(filters=[
        {"id": "importance", "label": "Importance", "source": "custom",
         "values": [{"id": "heavy", "name": "Heavy"},
                    {"id": "light", "name": "Light"}]}])
    _, report = _build(d)
    assert any("unassigned" in w for w in report["warnings"])


def test_validation_rejects_bad_filters():
    brief, nodes, _ = load_brief(_sample(filters=[
        {"id": "a", "label": "A", "source": "custom",
         "values": [{"id": "x", "name": "X"}, {"id": "y", "name": "Y"}]},
        {"id": "b", "label": "B", "source": "acts"},
        {"id": "c", "label": "C", "source": "acts"}]))
    with pytest.raises(BriefError, match="at most 2 filters"):
        validate_brief(brief)

    brief, nodes, _ = load_brief(_sample(filters=[
        {"id": "a", "label": "A", "source": "axis2"}]))
    with pytest.raises(BriefError, match="needs two extra axes"):
        validate_brief(brief)

    brief, nodes, _ = load_brief(_sample(filters=[
        {"id": "a", "label": "A", "source": "custom",
         "values": [{"id": "x", "name": "X"}]}]))
    with pytest.raises(BriefError, match="2-10 values"):
        validate_brief(brief)

    d = _sample(
        filters=[{"id": "a", "label": "A", "source": "custom",
                  "values": [{"id": "x", "name": "X"},
                             {"id": "y", "name": "Y"}]}],
        node_patch=lambda n: {"filters": {"a": "nope"}})
    brief, nodes, _ = load_brief(d)
    validate_brief(brief)
    with pytest.raises(BriefError, match="unknown value"):
        validate_nodes(brief, nodes)


def test_symbol_style_stripped_and_context_css_emitted():
    """Regression: a symbol_svg root style (old §C1 wrapper margin) skewed
    glyph centring in flex-centred card chips."""
    d = _sample()
    d["brief"]["entities"][0]["symbol_svg"] = (
        '<svg viewBox="0 0 20 20" width="14" height="14" '
        'style="vertical-align:-2px;margin-right:5px" fill="none" '
        'stroke="currentColor" stroke-width="1.5"><path d="M4 6 H16"/></svg>')
    html, _ = _build(d)
    assert 'style="vertical-align:-2px;margin-right:5px"' not in html
    assert ".csym-btn svg" in html and "width:1em" in html


def test_non_spine_relations_get_default_colors():
    d = _sample()
    d["brief"]["relations"].append({"key": "responds-to", "label": "Responds"})
    html, _ = _build(d)
    assert "'responds-to': 'var(--rel-responds-to)'" in html   # COLOR_MAP
    assert "'var(--rel-responds-to)':'#" in html               # CSS_HEX
    # spine stays neutral
    assert "spine:  'var(--line-flow)'" in html


def test_hyphenated_entity_ids_emit_parseable_chars():
    """Regression: unquoted hyphenated CHARS keys were a page-killing
    SyntaxError (criminal-law-101 external test, 2026-08-12)."""
    d = _sample()
    for e in d["brief"]["entities"]:
        if e["id"] == "offer":
            e["id"] = "offer-rule"
    for n in d["nodes"]:
        n["entity_ids"] = ["offer-rule" if i == "offer" else i
                          for i in n.get("entity_ids", [])]
    html, _ = _build(d)
    assert "\n  'offer-rule': {name:" in html
    assert "\n  offer-rule: {" not in html
