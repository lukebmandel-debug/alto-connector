"""System, the controls after the button audit (Luke approved, 2026-10-25):

- Spokes only is gone (its switch, its mode and its arrows); a choice kept from it opens the page as ever;
- Flights and Ship are one picker, "Ship: Off" or the craft: off goes straight to each body, a craft chosen flies;
- Orbit is hidden while a body is enlarged (the orbits wait there anyway) and comes back on zooming out;
- a move (the Tour bar's Next, a name in the panel) still flies its flight path when there is a ship.

Browser checks run in Chromium and WebKit (Playwright; skipped without them)."""
import copy
import re
import sys
from pathlib import Path

import pytest

from alto.build.builder import build_timeline, load_brief
from alto.build.solar_draw import SOLAR_CSS, SOLAR_JS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_solar_draw import _open, browser, solar_doc  # noqa: E402,F401
from test_solar_pool import SMALL, SMALL_LINKS  # noqa: E402


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    html, _ = build_timeline(*load_brief(copy.deepcopy(solar_doc(SMALL, "orbit", SMALL_LINKS))))
    f = tmp_path_factory.mktemp("controls") / "ct.html"
    f.write_text(html, encoding="utf-8")
    return f


def test_spokes_only_is_gone_from_the_script():
    for gone in ("sol-lock", "sol-arw", "Spokes only:", "setLock"):
        assert gone not in SOLAR_JS + SOLAR_CSS, gone
    assert not re.search(r"#sol-fly(?![\w-])|'sol-fly'", SOLAR_JS + SOLAR_CSS)          # (the Flights switch; html.sol-flying is the flight's own)


FLYING = """() => { var p=document.querySelector('#solar-fly-svg .fly-path'), s=p && p.closest('svg');
  return {flight:!!window._altoSolarFlight(), ride:!!window._altoSolarLock.riding(),
    path:!!p && (p.getAttribute('d')||'').length>20 && !s.classList.contains('fly-out') && getComputedStyle(s).display!=='none'}; }"""
CTL = "() => [].map.call(document.querySelectorAll('#sol-ctl>button'), function(b){ return b.id+(b.hidden || !b.getClientRects().length ? ':hidden' : ''); })"


def test_an_old_spokes_only_choice_opens_as_ever(browser, page):
    pg, errs = _open(browser, page, wait=300)
    pg.evaluate("() => { for(var i=0;i<localStorage.length;i++){} Object.keys(localStorage).forEach(function(k){ if(/alto-solar/.test(k)) localStorage.removeItem(k); }); }")
    pg.evaluate("() => localStorage.setItem('alto-solar-lock:solar-draw', '1')")
    pg.evaluate("() => localStorage.setItem('alto-solar-lock', '1')")
    pg.reload()
    pg.wait_for_timeout(1600)
    assert pg.evaluate("() => [window._altoSolarLock.get(), !!document.querySelector('#sol-lock,#sol-arw')]") == [False, False]
    pg.evaluate("() => window._altoSolarLock.set(true)")                       # (an old caller: ignored)
    assert pg.evaluate("() => window._altoSolarLock.get()") is False
    pg.context.close()
    assert not errs, errs


@pytest.mark.parametrize("style", ["chart", "retro"])
def test_the_ship_picker_has_off_and_a_craft_flies(browser, page, style):
    pg, errs = _open(browser, page, wait=1400)
    pg.evaluate("s => { window._altoSolarStyles.set(s); window.enterFocus('u1-p3'); }", style)
    pg.wait_for_timeout(2500)
    pg.mouse.move(2, 600)
    ship = "() => [document.querySelector('#sol-craft .sol-st').textContent, document.getElementById('sol-craft').classList.contains('on'), !!window._altoFlyOff]"
    pg.click("#sol-craft")
    pg.wait_for_selector("#sol-craft-pop .sol-shipoff")
    assert pg.evaluate("() => document.querySelector('#sol-craft-pop .cr-row .cr-t').classList.contains('sol-shipoff')")   # Off is first
    pg.click("#sol-craft-pop .sol-shipoff")
    assert pg.evaluate(ship) == ["Off", False, True]
    assert not pg.is_visible("#sol-craft-pop")
    pg.click("#nvo-a [data-n=next]")                                               # off: straight there, no flight
    pg.wait_for_timeout(400)
    assert not pg.evaluate(FLYING)["flight"]
    pg.wait_for_timeout(1500)
    pg.click("#sol-craft")
    pg.wait_for_selector("#sol-craft-pop .sol-shipoff.on")
    craft = pg.evaluate("() => { var b=document.querySelector('#sol-craft-pop [data-craft]'); return [b.getAttribute('data-craft'), b.title]; }")
    pg.click('#sol-craft-pop [data-craft="%s"]' % craft[0])
    assert pg.evaluate(ship) == [craft[1], True, False]
    pg.evaluate("() => window.enterFocus('u1-p3')")
    pg.wait_for_function("() => !window._altoSolarFlight() && window._focusedNodeId==='u1-p3'", timeout=12000)
    pg.wait_for_timeout(800)
    pg.click("#nvo-a [data-n=next]")                                               # a ship: its flight path again
    pg.wait_for_timeout(400)
    st = pg.evaluate(FLYING)
    assert st == {"flight": True, "ride": False, "path": True}, st
    pg.context.close()
    assert not errs, errs


@pytest.mark.parametrize("style", ["system", "retro", "3d"])
def test_orbit_hides_while_a_body_is_enlarged(browser, page, style):
    pg, errs = _open(browser, page, wait=1400)
    pg.evaluate("s => window._altoSolarStyles.set(s)", style)
    pg.wait_for_timeout(1200)
    assert "sol-motion" in pg.evaluate(CTL)
    pg.evaluate("() => window.enterFocus('u1-p2')")
    pg.wait_for_timeout(1500)
    assert "sol-motion:hidden" in pg.evaluate(CTL)
    assert not any(b.startswith(("sol-lock", "sol-fly")) for b in pg.evaluate(CTL))
    pg.keyboard.press("Escape")                                                  # zoomed out: back
    pg.wait_for_timeout(1500)
    if pg.evaluate("() => !!window._focusedNodeId"):
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(1500)
    assert "sol-motion" in pg.evaluate(CTL)
    pg.context.close()
    assert not errs, errs
