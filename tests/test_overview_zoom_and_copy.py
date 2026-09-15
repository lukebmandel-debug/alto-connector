"""Overview pinch-zoom, the static sign-in glyph, sign-in errors, and wording.

1. Every zoom gesture belongs to focus mode, so the open Overview could not be
   enlarged. Over the Overview the same gestures now zoom #summary-inner alone.
2. INFO's expansion slid the account glyph 324px left, off the screen from its
   bottom-left slot. The glyph is a fixed point now.
3. A failed Google sign-in only reached the console; the modal now says why.
4. The reference build was a law course with "coming soon" tiles; Alto has
   neither, so that wording is gone from every page.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import load_brief, build_timeline  # noqa: E402
from alto.build.engine_patches import PATCHES  # noqa: E402
from alto.build.pages import build_home, build_reports  # noqa: E402
from alto.engine import template as engine_template  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"


@pytest.fixture(scope="module")
def html():
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    return build_timeline(*load_brief(d))[0]


@pytest.fixture(scope="module")
def home():
    return build_home([{"name": "P", "courses": []}])


@pytest.fixture(scope="module")
def reports():
    return build_reports([], "")


def test_overview_zoom_script_loads_before_focus_mode(html):
    assert html.index('<script id="alto-overview-zoom">') < html.index('<script id="alto-focus-mode">')


@pytest.mark.parametrize("hook", [
    "window._altoOverviewZoom.wheel(e)) return;",
    "window._altoOverviewZoom.gesture(e);",
    "window._altoOverviewZoom.gestureEnd(e)) return;",
    "window._altoOverviewZoom.key(e)) return;",
])
def test_every_zoom_gesture_asks_the_overview_first(html, hook):
    assert hook in html


def test_the_overview_zooms_its_own_content_not_the_page(html):
    i = html.index('<script id="alto-overview-zoom">')
    body = html[i:html.index("</script>", i)]
    # both reading panels: the Overview and the detail page
    assert "inner:'summary-inner'" in body and "inner:'detail-content'" in body
    # magnified like a browser pinch: scaled, never re-laid out
    assert "el.style.transform=" in body
    assert "style.zoom" not in body
    # the column's margins become padding while zoomed, so lines never re-wrap
    assert "s.setProperty('padding-left',(pl+L)+'px')" in body
    assert "documentElement.style" not in body
    # while zoomed the panel must pan sideways too (its CSS hides overflow-x)
    assert "setProperty('overflow-x','auto','important')" in body


@pytest.mark.parametrize("name", [p["name"] for p in PATCHES
                                  if p["name"].startswith(("overview-zooms-alone", "copy-"))])
def test_new_anchors_match_the_engine_exactly_once(name):
    p = next(x for x in PATCHES if x["name"] == name)
    assert engine_template("timeline_template.html").count(p["old"]) == 1


def test_the_account_glyph_no_longer_slides_with_info(home):
    assert "slideAside('account-btn'" not in home
    assert "slideAside('search-btn', expanded);" in home


def test_a_failed_sign_in_is_explained_in_the_modal(home):
    assert "_altoSignInFailed(e);" in home
    assert "function _altoSignInFailed(e){" in home
    assert "auth/unauthorized-domain" in home


@pytest.mark.parametrize("stale", [
    "Dimmed tiles are coming soon",
    "report you generate inside a course",
    "keep your courses",
    "kind:'Course'",
    "(scenes, characters, themes)",
])
def test_home_has_no_stale_wording(home, stale):
    assert stale not in home


@pytest.mark.parametrize("stale", ["'← Course'", "inside the course"])
def test_reports_have_no_stale_wording(reports, stale):
    assert stale not in reports


@pytest.mark.parametrize("stale", ["Course overview", "Course Overview", "keep your courses"])
def test_timeline_has_no_stale_wording(html, stale):
    assert stale not in html


def test_timeline_sign_in_failure_is_explained(html):
    assert "e.code==='auth/unauthorized-domain'" in html
