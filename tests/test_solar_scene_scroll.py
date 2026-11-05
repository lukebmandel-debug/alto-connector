"""A wheel over a panel that scrolls (the Scene chooser, the filter) is the panel's: the chart behind it stays still.
Luke, 2026-11-01: "Scrolling on the scene chooser is not working right in system format, scrolling causes the system to
move instead of scrolling down to see more scene options." With a body enlarged the engine's window wheel listener read
the wheel as a swipe through the chart (a step, or the body let go) and the list never moved."""
import functools
import http.server
import threading

import pytest

from alto.build.builder import build_timeline, load_brief
from test_solar_draw import browser, solar_doc  # noqa: F401  (the browser fixture: chromium + webkit)

UNITS = [[[1, 0], [0, 0, 2], [], [0]], [[0, 0, 0], [0], [1, 0], []], [[0], [0, 1], [0, 0], [0]], [[1, 0], [0], [0, 0]]]
STYLES = ["system", "chart", "retro", "3d"]

STATE = """() => { var c=document.getElementById('canvas'), cam=window._altoSolar3D && window._altoSolar3D.cam ? window._altoSolar3D.cam() : null;
  return {sl:c.scrollLeft, st:c.scrollTop, foc:window._focusedNodeId||null, cam:JSON.stringify(cam)}; }"""
CENTRE = "(sel) => { var r=document.querySelector(sel).getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]; }"


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    d = tmp_path_factory.mktemp("scenescroll")
    html, _ = build_timeline(*load_brief(solar_doc(UNITS, "orbit", [("u1-p1", "u2-p2")])))
    (d / "t.html").write_text(html, encoding="utf-8")

    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    h = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(d)))
    threading.Thread(target=h.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{h.server_address[1]}/t.html"
    h.shutdown()


def _open(browser, base, style):
    pg = browser.new_page(viewport={"width": 1500, "height": 900})
    pg.goto(base)
    pg.wait_for_timeout(2200)
    pg.evaluate("s => window._altoSolarStyles.set(s)", style)
    pg.wait_for_timeout(1200)
    pg.evaluate("window.enterFocus('u1-p1')")        # a body enlarged: what the engine's wheel listener answers to
    pg.wait_for_timeout(1600)
    assert pg.evaluate(STATE)["foc"] == "u1-p1"
    return pg


def _wheel_over(pg, panel, scroller):
    """Wheel over the panel's scroll area; returns the chart state before and after, the list's scrollTop before and
    after, and whether anything prevented the wheel (a listener that took it for the chart)."""
    s0 = pg.evaluate(STATE)
    top0 = pg.evaluate(f"document.querySelector('{scroller}').scrollTop")
    pg.evaluate("window.__wp=[]; window.addEventListener('wheel', function(e){ window.__wp.push(e.defaultPrevented); }, {passive:true})")
    pg.mouse.move(*pg.evaluate(CENTRE, scroller))
    pg.mouse.wheel(0, 240)
    top1 = top0
    for _ in range(30):                              # (a software-GL page can be slow to scroll: wait for it, up to 3 s)
        pg.wait_for_timeout(100)
        top1 = pg.evaluate(f"document.querySelector('{scroller}').scrollTop")
        if top1 > top0 + 50:
            break
    pg.wait_for_timeout(300)
    assert not any(pg.evaluate("window.__wp")), "something took the wheel for the chart"
    return s0, pg.evaluate(STATE), top0, top1


@pytest.mark.parametrize("style", STYLES)
def test_the_scene_chooser_scrolls_and_the_chart_behind_it_stays_still(browser, base, style):
    pg = _open(browser, base, style)
    # a System draws its own background and offers the style picker only (Luke, 2026-11-04); the full, scrolling chooser is the one a page opened
    # from it shows (its detail-open state: the chart stays where it is behind it)
    pg.evaluate("document.documentElement.classList.add('detail-open')")
    pg.wait_for_timeout(300)
    pg.evaluate("document.getElementById('bg-toggle').click()")
    pg.wait_for_timeout(600)
    if style == "retro":          # Retro is plain black everywhere: its panel holds the style picker only, so there is no list to scroll
        assert pg.evaluate("document.getElementById('bg-panel').classList.contains('bg-only')")
        pg.close()
        return
    assert pg.evaluate("document.querySelector('#bg-panel .bg-body').scrollHeight > document.querySelector('#bg-panel .bg-body').clientHeight")
    s0, s1, top0, top1 = _wheel_over(pg, "#bg-panel", "#bg-panel .bg-body")
    assert top1 > top0 + 50, "the list did not scroll"
    assert s1 == s0, f"the chart moved under the chooser: {s0} -> {s1}"
    pg.close()


def test_the_filter_panel_is_the_same(browser, base):
    pg = _open(browser, base, "system")
    if not pg.query_selector("#filter-toggle"):
        pytest.skip("no filter tab on this page")
    pg.click("#filter-toggle")
    pg.wait_for_timeout(600)
    s0, s1, _t0, _t1 = _wheel_over(pg, "#ef-panel", "#ef-panel")
    assert s1 == s0, f"the chart moved under the filter: {s0} -> {s1}"
    pg.close()


def test_the_chart_still_answers_a_wheel_that_is_not_over_a_panel(browser, base):
    pg = _open(browser, base, "system")
    s0 = pg.evaluate(STATE)
    pg.mouse.move(300, 450)
    pg.mouse.wheel(0, 240)
    pg.wait_for_timeout(600)
    assert pg.evaluate(STATE) != s0, "a wheel over the chart itself must still drive it"
    pg.close()
