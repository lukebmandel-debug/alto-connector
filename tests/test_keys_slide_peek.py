"""1.9.67: the detail-page swipe preview is clear over a chosen Scene; a horizontal timeline's lines look like the
New-timeline preview (smooth S branches, solid, a ruler along the bottom); arrows with nothing enlarged slide to the next
event instead of scrolling freely; and the key of the lines / of a Memory Palace is a round toggle floating at the top left
under the bars (key_toggle.py), closed until asked for.

The browser tests are skipped without Playwright's browsers.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import key_toggle, lanes, palace  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.engine_patches import PATCHES  # noqa: E402

LANES = ROOT / "samples" / "lanes_brief.json"
CONTRACTS = ROOT / "samples" / "contracts_brief.json"
PHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")


def _build(path):
    html, _ = build_timeline(*load_brief(json.loads(Path(path).read_text(encoding="utf-8"))))
    return html


# ── what the pages carry ────────────────────────────────────────────────────

def test_the_swipe_preview_is_clear_when_a_scene_is_chosen():
    new = next(p["new"] for p in PATCHES if p["name"] == "detail-peek-matches-page")
    assert "classList.contains('alto-bg')" in new
    assert "el.style.background = 'none'" in new


def test_both_keys_are_a_toggle_not_a_fixed_panel():
    for mod, js, css in ((lanes, lanes.LANES_JS, lanes.LANES_CSS), (palace, palace.PALACE_JS, palace.PALACE_CSS)):
        assert key_toggle.KEY_JS.strip() in js and key_toggle.KEY_CSS.strip() in css
        assert "_altoKeyToggle(k," in js
    assert "#lanes-key{position:fixed" not in lanes.LANES_CSS
    assert "#pal-key{padding" not in palace.PALACE_CSS and 'id="pal-key"><h5>' not in palace.PALACE_JS
    # under the bars, top left, glass like the round buttons
    assert "top:calc(var(--nav-bottom, 100px) + 14px)" in key_toggle.KEY_CSS
    assert "border-radius:50%" in key_toggle.KEY_CSS and "backdrop-filter:blur(18px)" in key_toggle.KEY_CSS


def test_horizontal_lines_are_solid_with_curves_and_a_ruler():
    js, css = lanes.LANES_JS, lanes.LANES_CSS
    assert "ln-wait" not in js and "ln-wait" not in css            # no dashed "waiting" stretches
    assert "ln-fb" not in js and "ln-fb" not in css                 # lanes v2: a flashback is a solid detour of the main line, never dashed
    assert "ln-rule" in js                                          # the time ruler
    assert "ay=H+P-52" in js


def test_arrows_slide_instead_of_scrolling():
    js = lanes.LANES_JS
    # lanes_nav.py: arrows step event to event on the engine's glide (see test_lanes_nav.py)
    assert "function glideTo(" in js and "window._altoLanesNav=function(id, dir)" in js and "window.enterFocus(cur)" in js


# ── in a browser ────────────────────────────────────────────────────────────

pw = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:                              # no browser downloaded
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


@pytest.fixture(scope="module")
def lanes_page(tmp_path_factory):
    f = tmp_path_factory.mktemp("lanes") / "page.html"
    f.write_text(_build(LANES), encoding="utf-8")
    return f


@pytest.fixture(scope="module")
def phone_page(tmp_path_factory):
    f = tmp_path_factory.mktemp("peek") / "page.html"
    f.write_text(_build(CONTRACTS), encoding="utf-8")
    return f


def _desk(browser, f):
    pg = browser.new_context(viewport={"width": 1500, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f.as_uri())
    pg.wait_for_timeout(1500)
    return pg, errs


def test_the_key_is_a_closed_round_toggle_at_the_top_left_under_the_bars(browser, lanes_page):
    pg, errs = _desk(browser, lanes_page)
    r = pg.evaluate("""() => { const b = document.getElementById('key-toggle'), k = document.getElementById('lanes-key'),
        nav = document.getElementById('nav').getBoundingClientRect(), br = b.getBoundingClientRect();
      return { navBottom: nav.bottom, top: br.top, left: br.left, w: br.width, round: getComputedStyle(b).borderRadius,
               open: k.classList.contains('open'), shown: getComputedStyle(k).display, fixed: getComputedStyle(b).position }; }""")
    assert r["fixed"] == "fixed" and r["shown"] == "none" and not r["open"]        # closed until asked for
    assert r["top"] >= r["navBottom"] and r["left"] < 60 and r["round"] in ("50%", f"{r['w'] / 2}px")
    pg.click("#key-toggle")
    o = pg.evaluate("""() => { const k = document.getElementById('lanes-key'), kr = k.getBoundingClientRect(),
        br = document.getElementById('key-toggle').getBoundingClientRect();
      return { shown: getComputedStyle(k).display, below: kr.top >= br.bottom, rows: k.querySelectorAll('.lk-row').length }; }""")
    assert o["shown"] == "block" and o["below"] and o["rows"] >= 3
    pg.keyboard.press("Escape")
    assert pg.evaluate("getComputedStyle(document.getElementById('lanes-key')).display") == "none"
    assert not errs


def test_an_arrow_slides_to_the_next_event_and_comes_to_rest_on_it(browser, lanes_page):
    pg, errs = _desk(browser, lanes_page)
    pg.evaluate("""() => { window._rec = []; const cv = document.getElementById('canvas');
      (function f() { window._rec.push(cv.scrollLeft); requestAnimationFrame(f); })(); }""")
    first = pg.evaluate("() => window._altoLanesNav(window._altoLanesCurrent(), 'e')")    # the event the step from where the view is will reach
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(2200)
    s = pg.evaluate("""() => { const cv = document.getElementById('canvas'), G = window._altoLanesGeo;
      return { left: cv.scrollLeft, want: G.x[%s] - cv.clientWidth / 2, focused: !!window._focusedNodeId, rec: window._rec }; }""" % json.dumps(first))
    assert first and not s["focused"]                                      # nothing was enlarged
    assert abs(s["left"] - max(0, s["want"])) <= 2                          # rested on that event, centred
    steps = [round(b - a, 2) for a, b in zip(s["rec"], s["rec"][1:]) if b != a]
    assert len(steps) >= 12, steps                                          # it travelled over many frames (a slide, not a jump)
    assert max(steps) < 0.4 * (s["left"] - s["rec"][0] or 1) or len(steps) > 30
    assert not errs


def test_enter_enlarges_the_event_the_arrows_reached(browser, lanes_page):
    pg, _ = _desk(browser, lanes_page)
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(1800)
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(600)
    assert pg.evaluate("!!window._focusedNodeId")


def test_the_swipe_preview_shows_the_scene_not_a_flat_page(browser, phone_page):
    if browser.browser_type.name != "chromium":
        pytest.skip("WebKit has no Touch constructor to drive a drag with")
    ctx = browser.new_context(viewport={"width": 390, "height": 664}, device_scale_factor=2, is_mobile=True,
                              has_touch=True, user_agent=PHONE_UA)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    # a Scene is drawn on web pages only: serve the page from a made-up address
    pg.route("http://alto.test/**", lambda r: r.fulfill(body=phone_page.read_text(encoding="utf-8"), content_type="text/html")
             if r.request.url.endswith("/page.html") else r.abort())
    pg.goto("http://alto.test/page.html")
    pg.wait_for_timeout(1500)
    pg.evaluate("window._altoBg.choose('cosmic-cliffs'); 0")                  # a Scene is on
    pg.wait_for_timeout(300)
    assert pg.evaluate("document.documentElement.classList.contains('alto-bg')")
    pg.evaluate("showDetail('node', NODE_ORDER[1]); 0")
    pg.wait_for_timeout(900)
    # the peek is made inside the engine's closure: drive it with a real touch drag instead
    pg.evaluate("""() => { window._peekSeen = null; new MutationObserver(() => { const p = document.querySelector('.det-peek');
      if (p && !window._peekSeen) { const cs = getComputedStyle(p); window._peekSeen = { bg: cs.backgroundColor, img: cs.backgroundImage }; } })
      .observe(document.body, { childList: true }); }""")
    pg.evaluate("""() => { const dp = document.getElementById('detail-page');
      const mk = (type, x) => { const t = new Touch({ identifier: 1, target: dp, clientX: x, clientY: 300 });
        dp.dispatchEvent(new TouchEvent(type, { touches: type === 'touchend' ? [] : [t], changedTouches: [t], bubbles: true, cancelable: true })); };
      mk('touchstart', 300); mk('touchmove', 280); mk('touchmove', 200); }""")
    pg.wait_for_timeout(200)
    seen = pg.evaluate("window._peekSeen")
    assert seen is not None, "no preview appeared"
    assert seen["bg"] in ("rgba(0, 0, 0, 0)", "transparent") and seen["img"] == "none"
    assert not errs
    ctx.close()
