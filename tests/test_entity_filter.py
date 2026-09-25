"""The character filter is a toggle, not another row of chips in the nav bar,
and the relation "Lines" filter is a choice the author makes."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.brief import BriefError  # noqa: E402
from alto.build.builder import load_brief, build_timeline  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"


def _build(**flags):
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    d["brief"].update(flags)
    return build_timeline(*load_brief(d))


def _nav(html):
    return html.split('<div id="nav">', 1)[1].split("\n  </div>", 1)[0]


def test_entity_filter_is_off_unless_asked_for():
    html, _ = _build()
    assert "ENT_ITEMS" not in html
    assert "ef-panel" not in html


def test_entity_filter_puts_chips_in_a_panel_not_the_nav():
    html, _ = _build(entity_filter=True)
    assert "var ENT_ITEMS=" in html and "var ENT_NODES=" in html
    assert "filter-toggle" in html and "ef-panel" in html
    # the nav still lists each entity once, as a link — no second row of them
    assert "ent-filter-btn" not in _nav(html)
    assert "Filter by" not in _nav(html)


def test_entity_filter_offers_only_entities_that_divide_the_nodes():
    html, warnings = _build(entity_filter=True)
    items = json.loads(html.split("var ENT_ITEMS=", 1)[1].split(";\nvar ENT_NODES", 1)[0])
    nodes = json.loads(html.split("var ENT_NODES=", 1)[1].split(";", 1)[0])
    assert items and all(0 < i["count"] < 6 for i in items)
    assert all(len(nodes[i["id"]]) == i["count"] for i in items)


def test_entity_filter_is_in_the_mobile_drawer_too():
    html, _ = _build(entity_filter=True)
    assert 'drawer-btn ent-filter-btn' in html
    assert "html.mobile #filter-toggle" in html


def test_compass_hop_skips_entity_dimmed_cards():
    html, _ = _build(entity_filter=True)
    assert "contains('ent-dimmed')" in html


def test_line_filter_defaults_on_and_can_be_switched_off():
    on, _ = _build()
    off, _ = _build(line_filter=False)
    assert "Filter · Lines" in _nav(on)
    assert "Filter · Lines" not in _nav(off)
    assert "line-key-btn" not in _nav(off)
    assert "REL_NODES" not in off


def test_flags_must_be_booleans():
    with pytest.raises(BriefError, match="entity_filter"):
        from alto.build.brief import validate_brief
        b, _, _ = load_brief({"brief": {**json.loads(SAMPLE.read_text())["brief"],
                                        "entity_filter": "yes"}})
        validate_brief(b)
