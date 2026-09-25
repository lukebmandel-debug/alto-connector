"""The Filter toggle: every filter a timeline has, in one panel.

Desktop and mobile share it — a tab in the right-edge rail on desktop, a tile in
the account toggle's old corner on a phone. Nothing filter-shaped is a chip row
in the nav bar or a section in the mobile drawer any more.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from alto.build.brief import BriefError, validate_brief  # noqa: E402
from alto.build.builder import load_brief, build_timeline  # noqa: E402
from panel import item_ids, nodes as panel_nodes, sections  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"


def _build(**flags):
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    d["brief"].update(flags)
    return build_timeline(*load_brief(d))


def _nav(html):
    return html.split('<div id="nav">', 1)[1].split("\n  </div>", 1)[0]


def test_every_kind_of_sub_chip_gets_a_section():
    html, _ = _build()
    keys = [s["key"] for s in sections(html)]
    assert "entity" in keys and "axis1" in keys
    entity = next(s for s in sections(html) if s["key"] == "entity")
    assert entity["kind"] == "chips" and entity["label"] == "Doctrine"
    assert all(0 < i["count"] for i in entity["items"])


def test_the_chips_are_not_in_the_nav_bar_or_the_drawer():
    html, _ = _build()
    assert "ent-filter-btn" not in html
    assert "Filter ·" not in _nav(html) and "Filter &middot;" not in html
    assert "drawer-btn filter-btn" not in html


def test_only_chips_that_divide_the_nodes_are_offered():
    html, _ = _build()
    mapped = panel_nodes(html)
    for s in sections(html):
        if s["kind"] != "chips":
            continue
        for i in s["items"]:
            assert i["count"] == len(mapped[s["key"]][i["id"]])
            assert i["count"] < 6            # an all-nodes chip changes nothing


def test_chip_filters_can_be_switched_off():
    html, _ = _build(chip_filters=False)
    assert not [s for s in sections(html) if s["kind"] == "chips"]


def test_a_mirrored_axis_is_not_offered_twice():
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    d["brief"]["filters"] = [{"id": "court", "label": "Court", "source": "axis1"}]
    html, _ = build_timeline(*load_brief(d))
    keys = [s["key"] for s in sections(html)]
    assert "axis1" not in keys and "slot-era" in keys


def test_the_filter_tab_comes_with_a_mobile_tile_and_no_account_toggle():
    html, _ = _build()
    assert "html.mobile #filter-toggle" in html
    assert "html.mobile #account-btn{display:none !important;}" in html
    assert "has-filter-tab" in html


def test_a_timeline_with_nothing_to_filter_has_no_panel():
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    d["brief"]["chip_filters"] = False
    d["brief"]["line_filter"] = False
    html, _ = build_timeline(*load_brief(d))
    assert "var FILTER_SECTIONS=" not in html and "panel.id='ef-panel'" not in html


def test_the_right_edge_tabs_share_one_rail_in_a_fixed_order():
    html, _ = _build()
    assert "#tab-rail" in html
    glue = html.split("_altoRailBound", 1)[1].split("})();", 1)[0]
    assert glue.index("appendChild(ov)") < glue.index("appendChild(nt)")


def test_stepping_through_the_timeline_skips_what_the_filter_hid():
    html, _ = _build()
    assert "window._altoChipKeep" in html
    assert "_altoChipOn" in html
    assert "contains('ent-dimmed')" in html          # compass hop


def test_line_filter_defaults_on_and_can_be_switched_off():
    on, _ = _build()
    off, _ = _build(line_filter=False)
    assert "lines" in [s["key"] for s in sections(on)]
    assert "lines" not in [s["key"] for s in sections(off)]
    assert "REL_NODES" not in off


def test_flags_must_be_booleans():
    b, _, _ = load_brief({"brief": {**json.loads(SAMPLE.read_text())["brief"],
                                    "chip_filters": "yes"}})
    with pytest.raises(BriefError, match="chip_filters"):
        validate_brief(b)


def test_mobile_search_sits_in_the_top_row_and_stays_put():
    html, _ = _build()
    assert "position:fixed; top:104px; bottom:auto; left:50%" in html
    assert "html.mobile.msearch-open #m-search{" not in html      # no docking
    assert "input.focus({preventScroll:true})" in html


def test_mobile_detail_pages_search_from_a_side_panel_not_the_pill():
    html, _ = _build()
    assert "html.mobile.detail-open #m-search" in html          # pill hidden there
    assert "html.mobile.detail-open #search-toggle{display:flex;}" in html
    assert "bottom:calc(66px + env(safe-area-inset-bottom, 0px));z-index:295" in html
    assert "window._mSearchNavigate=navigate" in html            # reuses the pill's navigation
    assert "transform:translateX(-100%)" in html.split("html.mobile #msp{", 1)[1].split("}", 1)[0]


def test_mobile_filter_opens_as_a_full_page_like_info():
    html, _ = _build()
    css = html.split("html.mobile #ef-panel{", 1)[1].split("}", 1)[0]
    assert "inset:0" in css and "z-index:401" in css and "translateX(-100%)" in css
    assert "ef-close" in html


def test_mobile_filter_count_badge_sits_on_the_right_of_the_tile():
    html, _ = _build()
    assert 'html.mobile #filter-toggle[data-n]:not([data-n=""])::after{left:auto;right:-7px;}' in html


def test_desktop_bottom_controls_sit_above_every_node():
    html, _ = _build()
    rule = "html:not(.mobile) #search-btn{ z-index:310 !important; }"
    assert rule in html
    # a focused node is 300 and a hovered one 200: the controls must beat both
    assert "html:not(.mobile) .node.focused{ z-index:300 !important; }" in html
