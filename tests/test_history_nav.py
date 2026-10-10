"""The browser's Back and Forward move through a timeline's pages like Alto's own controls do (history_nav.py).

Browser tests, skipped without Playwright's Chromium; the pages are the sample outline built here.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build import history_nav  # noqa: E402

OUTLINE = ROOT / "samples" / "outline_brief.json"


def test_every_page_carries_the_history_module_and_it_is_the_last_wrapper():
    html, _ = build_timeline(*load_brief(json.loads(OUTLINE.read_text(encoding="utf-8"))))
    assert 'id="alto-history-nav"' in html
    # after the wrapper that must be outermost for showDetail (back-to-previous), and after printing's
    assert html.index('id="alto-history-nav"') > html.index('id="alto-back-prev-js"') > 0
    assert html.index('id="alto-history-nav"') > html.index('id="alto-print-views-js"')


pw = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    html, _ = build_timeline(*load_brief(json.loads(OUTLINE.read_text(encoding="utf-8"))))
    f = tmp_path_factory.mktemp("hist") / "page.html"
    f.write_text(html, encoding="utf-8")
    return f


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:                          # no browser downloaded
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


def _open(browser, f, from_page=True):
    """A page the person came from (the homepage, say), then the timeline."""
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    if from_page:
        pg.goto("data:text/html,<title>home</title>home")
    pg.goto(f.as_uri())
    pg.wait_for_timeout(1200)
    return pg


VIEW = """() => { const dp = document.getElementById('detail-page');
  return dp && dp.classList.contains('visible') ? 'd:' + window._currentDetailId : 'tl'; }"""


def _ids(pg):
    return pg.evaluate("NODE_ORDER.slice(0, 4)")


def test_back_and_forward_walk_the_pages_like_alto_does(browser, built):
    pg = _open(browser, built)
    a, b, c = _ids(pg)[:3]
    assert pg.evaluate(VIEW) == "tl"
    pg.evaluate(f"showDetail('node', '{a}'); 0")
    pg.evaluate(f"showDetail('node', '{b}'); 0")
    assert pg.evaluate(VIEW) == f"d:{b}"
    pg.go_back(); pg.wait_for_timeout(300)
    assert pg.evaluate(VIEW) == f"d:{a}"                      # the previous page
    pg.go_back(); pg.wait_for_timeout(300)
    assert pg.evaluate(VIEW) == "tl"                           # then the timeline
    pg.go_forward(); pg.wait_for_timeout(300)
    assert pg.evaluate(VIEW) == f"d:{a}"                      # and Forward does the same the other way
    pg.go_forward(); pg.wait_for_timeout(300)
    assert pg.evaluate(VIEW) == f"d:{b}"


def test_back_from_the_timeline_goes_to_where_the_person_came_from_and_forward_returns(browser, built):
    pg = _open(browser, built)
    a = _ids(pg)[0]
    pg.evaluate(f"showDetail('node', '{a}'); 0")
    pg.go_back(); pg.wait_for_timeout(300)
    assert pg.evaluate(VIEW) == "tl" and pg.url.startswith("file:")
    pg.go_back(); pg.wait_for_timeout(500)
    assert pg.url.startswith("data:")                          # the page they came from
    pg.go_forward(); pg.wait_for_timeout(1500)
    assert pg.url.startswith("file:")                          # and Forward comes back to the timeline


def test_alto_s_own_back_is_the_browser_s_back(browser, built):
    pg = _open(browser, built)
    a, b = _ids(pg)[:2]
    n0 = pg.evaluate("history.length")
    pg.evaluate(f"showDetail('node', '{a}'); 0")
    assert pg.evaluate("history.length") == n0 + 1
    pg.evaluate("showTimeline(); 0")                          # Back to the timeline / Back to Overview
    pg.wait_for_timeout(300)
    assert pg.evaluate(VIEW) == "tl"
    assert pg.evaluate("history.length") == n0 + 1             # it stepped back, it did not add another entry
    pg.go_forward(); pg.wait_for_timeout(300)
    assert pg.evaluate(VIEW) == f"d:{a}"                      # so the browser's Forward is the page just left
    # the same from page to page (the "Back to <previous page>" control)
    pg.evaluate(f"showDetail('node', '{b}'); 0")
    pg.evaluate(f"showDetail('node', '{a}'); 0")
    pg.wait_for_timeout(300)
    assert pg.evaluate(VIEW) == f"d:{a}"
    pg.go_forward(); pg.wait_for_timeout(300)
    assert pg.evaluate(VIEW) == f"d:{b}"


def test_opening_the_page_already_open_adds_nothing(browser, built):
    pg = _open(browser, built)
    a = _ids(pg)[0]
    pg.evaluate(f"showDetail('node', '{a}'); 0")
    n = pg.evaluate("history.length")
    pg.evaluate(f"showDetail('node', '{a}'); showTimeline(); showTimeline(); 0")
    pg.wait_for_timeout(300)
    assert pg.evaluate("history.length") <= n + 1


def test_printing_does_not_touch_the_history(browser, built):
    pg = _open(browser, built)
    a = _ids(pg)[0]
    pg.evaluate("window.print = function(){}; 0")
    pg.evaluate(f"showDetail('node', '{a}'); 0")
    n = pg.evaluate("history.length"); i = pg.evaluate("history.state.i")
    pg.evaluate("window._altoInkStage(); 0")
    pg.evaluate("window._altoInkUnstage(); 0")
    pg.wait_for_timeout(300)
    assert pg.evaluate("history.length") == n and pg.evaluate("history.state.i") == i
    assert pg.evaluate(VIEW) == f"d:{a}"                       # and it is back on the page it was on


def test_a_reload_opens_on_the_page_its_entry_holds(browser, built):
    pg = _open(browser, built)
    a = _ids(pg)[0]
    pg.evaluate(f"showDetail('node', '{a}'); 0")
    pg.reload(); pg.wait_for_timeout(2500)
    assert pg.evaluate(VIEW) == f"d:{a}", pg.evaluate("JSON.stringify([history.state, window._altoNav && window._altoNav.state().cur, window._currentDetailId, document.readyState])")


def test_the_url_is_never_changed(browser, built):
    pg = _open(browser, built)
    url = pg.url
    a, b = _ids(pg)[:2]
    pg.evaluate(f"showDetail('node', '{a}'); showDetail('node', '{b}'); 0")
    assert pg.url == url


def test_a_newer_copy_written_over_the_page_is_wrapped_again(browser, built):
    """The private shell can write a newer copy of the page into the same window: the page's functions are new, the history module's
    state is not, so it wraps the new ones and the copy starts up on the timeline without adding an entry."""
    pg = _open(browser, built)
    a, b = _ids(pg)[:2]
    pg.evaluate(f"showDetail('node', '{a}'); 0")
    n = pg.evaluate("history.length")
    html = built.read_text(encoding="utf-8")
    pg.evaluate("(h) => { document.open(); document.write(h); document.close(); }", html)
    pg.wait_for_timeout(2500)
    assert pg.evaluate("history.length") == n and pg.evaluate(VIEW) == "tl"
    pg.evaluate(f"showDetail('node', '{b}'); 0")
    assert pg.evaluate("history.length") == n + 1               # the new copy's showDetail is wrapped
    pg.go_back(); pg.wait_for_timeout(400)
    assert pg.evaluate(VIEW) == "tl"


# ── a card enlarged while the cards are drawn again (an edit saved) ─────────

def test_drawing_the_cards_again_while_one_is_enlarged_leaves_nothing_stale(browser, built):
    """The screenshot: every card faded to 14%, the enlarged card's shadow standing alone and the card itself faded too."""
    pg = _open(browser, built)
    a = _ids(pg)[0]
    pg.evaluate(f"window.enterFocus('{a}'); 0")
    pg.wait_for_timeout(900)
    assert pg.evaluate("document.getElementById('canvas').classList.contains('focus-mode')")
    pg.evaluate("initLayout(); 0")                       # what saving an edit does (manual_edit relayout)
    pg.wait_for_timeout(900)
    got = pg.evaluate("""() => ({fm: document.getElementById('canvas').classList.contains('focus-mode'), fid: window._focusedNodeId || null,
      fsh: document.querySelectorAll('.alto-fshadow').length,
      dim: [...document.querySelectorAll('#world .node-card')].filter(c => parseFloat(getComputedStyle(c).opacity) < 0.5).length})""")
    assert got == {"fm": False, "fid": None, "fsh": 0, "dim": 0}
