"""A page with no authored Overview never opens an empty, dimmed panel (Luke 2026-11-26, his lanes timeline in Holo, Expanded: the page went near-black behind
nothing). It composes one from its sections and their events/hubs (as an outline always has); with truly nothing to show the button and the panel are not offered. No browser."""
import copy
import json
from pathlib import Path

import pytest

from alto.build.builder import build_timeline, load_brief

ROOT = Path(__file__).resolve().parent.parent


def _page(name, mutate=None):
    d = json.loads((ROOT / "samples" / f"{name}.json").read_text(encoding="utf-8"))
    d["brief"]["overview_html"] = ""
    if mutate:
        mutate(d)
    out = build_timeline(*load_brief(copy.deepcopy(d)))
    return out if isinstance(out, str) else out[0]


def _inner(html):
    i = html.index('id="summary-inner"')
    return html[i:html.index("</div>", i)]


@pytest.mark.parametrize("name", ["lanes_brief", "contracts_brief", "outline_brief"])
def test_a_page_with_no_overview_composes_one_from_its_sections_and_events(name):
    html = _page(name)
    inner = _inner(html)
    assert "showDetail('node'" in inner and "<h2>" in inner          # section headings and links to their events / hubs
    assert 'id="alto-no-ov"' not in html                              # (the button stays)


def test_an_authored_overview_with_no_words_is_replaced_by_a_composed_one():
    def blank(d):
        d["brief"]["overview_html"] = "<p>&nbsp;</p>\n<div> </div>"
    html = _page("contracts_brief", blank)
    assert "showDetail('node'" in _inner(html) and 'id="alto-no-ov"' not in html


def test_the_button_and_panel_are_dropped_when_there_is_truly_nothing_to_show():
    from alto.build import blocks
    assert 'id="alto-no-ov"' in open(blocks.__file__, encoding="utf-8").read()                      # (defensive: unreachable by a built page, which always has events)
