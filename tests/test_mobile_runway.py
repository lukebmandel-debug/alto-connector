"""A mobile page opened directly runs as one surface behind Safari's status bar
and toolbar (engine_patches.py, mobile-runway-behind-bars)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alto.build.builder import build_timeline, load_brief  # noqa: E402

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "contracts_brief.json"


@pytest.fixture(scope="module")
def html():
    page, _ = build_timeline(*load_brief(json.loads(SAMPLE.read_text(encoding="utf-8"))))
    return page


def test_the_runway_is_switched_on_before_the_first_layout(html):
    # Safari keeps the flat strip it took from a fixed header on first layout,
    # so the class and the rules are both in <head>, not at the end of <body>.
    body = html.index("<body")
    assert html.index("classList.add('rw')") < body
    assert html.index('<style id="alto-runway">') < body
    assert "if((ua || qp) && window.top === window)" in html      # never inside a frame


def test_no_fixed_chrome_is_left_on_the_edges(html):
    assert "html.mobile.rw :is(#title-bar, #nav-drawer-overlay, #nav-drawer, #nav, #timeline-label-bar" in html
    assert "):not(#_), html.mobile.rw .rw-abs:not(#_){ position:absolute !important; }" in html
    # the panels' own headers are not sticky, and reach up under the clock
    assert "html.mobile.rw :is(#minimap-header, #tutorial-header):not(#_){ position:relative !important; }" in html
    assert "html.mobile.rw #ef-panel .ef-head{position:relative;flex:none;}" in html
    assert "body.className='ef-body'" in html


def test_the_page_rests_on_a_short_runway(html):
    assert "margin:80px 0 140px !important" in html
    assert "html.mobile.rw #page-bg:not(#_){ background:var(--page-grad) !important; }" in html
    assert "var r = document.documentElement, OFF = 80;" in html
    # the old flat edge colours are gone: they read as bars
    assert "--m-edge-top" not in html
