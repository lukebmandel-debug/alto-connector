"""System: the Orbit button stays put while you move about the system (Luke, L-1102-110829: "make sure orbit button isn't
constantly disappearing and reappearing while moving throughout system"). It used to be hidden while a body was enlarged,
so every move (a flight leaves one body and enlarges the next, a zoom out, Esc) blinked it away and back.

Each style (System, Star chart, Retro, 3D): sample the button every frame through flights, enlarge / leave and a zoom, and
assert its hidden flag, display, visibility and box never change. Browser checks run in Chromium (Playwright; skipped without)."""
import copy
import sys
from pathlib import Path

import pytest

from alto.build.builder import build_timeline, load_brief

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_solar_draw import _open, browser, solar_doc  # noqa: E402,F401
from test_solar_pool import SMALL, SMALL_LINKS  # noqa: E402


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    html, _ = build_timeline(*load_brief(copy.deepcopy(solar_doc(SMALL, "orbit", SMALL_LINKS))))
    f = tmp_path_factory.mktemp("orbsteady") / "os.html"
    f.write_text(html, encoding="utf-8")
    return f


# every animation frame: the button's visible state (and its box, so a vanish-and-return shows as a change)
START = """() => { window.__ob = {n:0, seen:new Set(), foc:0, last:null, flips:0, on:true};
  (function f(){ if(!window.__ob.on) return; var m=document.getElementById('sol-motion'), cs=m && getComputedStyle(m), r=m && m.getBoundingClientRect();
    var k=m ? [m.hidden, cs.display, cs.visibility, r.width>0 && r.height>0, Math.round(r.top)].join() : 'gone';
    var o=window.__ob; o.n++; if(window._focusedNodeId) o.foc++; o.seen.add(k); if(o.last!==null && o.last!==k) o.flips++; o.last=k;
    requestAnimationFrame(f); })(); }"""
STOP = "() => { var o=window.__ob; o.on=false; return {n:o.n, foc:o.foc, flips:o.flips, seen:Array.from(o.seen)}; }"


@pytest.mark.parametrize("style", ["system", "chart", "retro", "3d"])
def test_orbit_button_never_toggles_while_moving(browser, page, style):
    pg, errs = _open(browser, page, wait=1400)
    pg.evaluate("s => window._altoSolarStyles.set(s)", style)
    pg.wait_for_timeout(1200)
    pg.evaluate(START)
    pg.evaluate("() => window.enterFocus('u1-p2')")                 # enlarge a body
    pg.wait_for_timeout(1500)
    for _ in range(3):                                               # flights (or hops) onward, the nav's Next
        pg.click("#nvo-a [data-n=next]")
        pg.wait_for_timeout(2200)
    pg.click("#nvo-a [data-n=up]")
    pg.wait_for_timeout(2200)
    pg.keyboard.press("Escape")                                      # home, then the whole system, then in again
    pg.wait_for_timeout(1500)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(1500)
    pg.evaluate("() => window.enterFocus('u1-p3')")
    pg.wait_for_timeout(1500)
    o = pg.evaluate(STOP)
    assert o["n"] > 100 and o["foc"] > 20, o                         # many samples, a good share with a body enlarged
    assert o["flips"] == 0 and len(o["seen"]) == 1, o
    assert "false,flex,visible,true" in o["seen"][0], o
    pg.context.close()
    assert not errs, errs


@pytest.mark.parametrize("style", ["system", "chart", "retro", "3d"])
def test_orbit_button_stays_while_a_body_is_enlarged_and_says_paused(browser, page, style):
    pg, errs = _open(browser, page, wait=1400)
    pg.evaluate("s => window._altoSolarStyles.set(s)", style)
    pg.wait_for_timeout(1200)
    pg.evaluate("() => window.enterFocus('u1-p2')")
    pg.wait_for_timeout(1500)
    st = pg.evaluate("() => { var m=document.getElementById('sol-motion'); return [m.hidden, m.getClientRects().length>0, m.disabled, m.querySelector('.sol-ow').textContent]; }")
    assert st[0] is False and st[1] is True and st[2] is False and st[3].endswith("paused"), st
    pg.context.close()
    assert not errs, errs
