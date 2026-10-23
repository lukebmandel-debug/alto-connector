"""System, Luke's report of 2026-10-22: "Ship switching doesn't work, sometimes orbiting doesn't work, sometimes map is
stuck. In system format generally, it seems to be a little glitchy in movement. its still terribly confusing how to
navigate where you want to, regardless of whether its in spoke only mode or normal" — the root causes found by the
WebKit stress and per-frame camera probes, and the one way of moving (the Tour in both modes; Spokes only takes the
free camera away).

Browser checks run in Chromium and WebKit (Playwright; skipped without them)."""
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
    f = tmp_path_factory.mktemp("round12") / "r12.html"
    f.write_text(html, encoding="utf-8")
    return f


def _arrive(pg, want, timeout=6000):
    pg.wait_for_function("id => window._focusedNodeId===id && !window._altoSolarLock.riding()", arg=want, timeout=timeout)
    pg.wait_for_timeout(250)


def test_a_zoom_glide_cut_short_leaves_the_board_clickable(browser, page):
    """The map "stuck": a zoom glide cut short (a click, a ride, the camera) kept #canvas.sol-ovanim, whose rule takes
    the board's pointer events away; nothing on it could be clicked until the next zoom."""
    pg, errs = _open(browser, page, wait=1400)
    pg.evaluate("() => window._altoSolarStyles.set('system')")
    pg.evaluate("() => window._altoSolarZoom(.4)")
    pg.wait_for_timeout(300)
    pg.evaluate("() => { document.dispatchEvent(new KeyboardEvent('keydown', {key:'=', metaKey:true, bubbles:true})); }")   # a glide in ...
    pg.wait_for_timeout(120)
    pg.evaluate("() => window._altoSolarZoom(1)")                                     # ... cut short
    pg.wait_for_timeout(300)
    st = pg.evaluate("() => [document.getElementById('canvas').classList.contains('sol-ovanim'), getComputedStyle(document.getElementById('world')).pointerEvents]")
    assert st == [False, "auto"], st
    pg.context.close()
    assert not errs, errs


def test_the_camera_reports_the_frame_on_the_window_while_it_glides(browser, page):
    """Glitchy movement: during a zoom glide the camera (window._altoSolarCam, which the 3D scene, the labels and the
    flights follow) reported where the glide would END, and leaving the whole system reported a scroll not yet made:
    everything that follows it jumped while the board glided."""
    pg, errs = _open(browser, page, wait=1400)
    pg.evaluate("() => { window._altoSolarStyles.set('chart'); window._altoSolarMotion.set(false); }")
    pg.evaluate("""() => { window.__s=[]; (function f(){ var g=window._altoSolarCam.get(); if(g) window.__s.push(g.scale); if(window.__s.length<90) requestAnimationFrame(f); })(); }""")
    pg.keyboard.press("o")                                                             # the whole system, in a glide
    pg.wait_for_timeout(1600)
    s = pg.evaluate("() => window.__s")
    mids = [v for v in s if .3 < v < .95]
    assert s[-1] < .3 and len(mids) >= 4, s                                           # it went through the frames between
    worst = max(abs(a - b) for a, b in zip(s, s[1:]))
    assert worst < .35, (worst, s)                                                    # never all of it in one frame
    pg.context.close()
    assert not errs, errs


def test_the_orbits_say_why_they_wait_and_come_back_after_a_hover_or_an_enlarged_card(browser, page):
    """Orbiting "sometimes doesn't work": window._altoSolarHold() names what holds the orbits ('' when nothing does);
    after a hover and after an enlarged card is let go they turn again."""
    pg, errs = _open(browser, page, wait=1400)
    pg.evaluate("() => window._altoSolarStyles.set('system')")
    assert pg.evaluate("() => window._altoSolarMotion.get()")
    pg.mouse.move(2, 940); pg.wait_for_timeout(600)
    assert pg.evaluate("() => window._altoSolarHold()") == ""
    x, y = pg.evaluate("() => { var b=document.querySelector('#node-u1 .node-card').getBoundingClientRect(); return [b.left+b.width/2, b.top+b.height/2]; }")
    pg.mouse.move(x, y); pg.wait_for_timeout(200)
    assert pg.evaluate("() => window._altoSolarHold()") == "hover"
    pg.mouse.move(2, 940); pg.wait_for_timeout(700)
    assert pg.evaluate("() => window._altoSolarHold()") == ""
    pg.evaluate("() => window.enterFocus('u1-p1')"); pg.wait_for_timeout(900)
    assert pg.evaluate("() => window._altoSolarHold()") == "focus"
    pg.wait_for_timeout(400)                                                           # the button says it is on but waiting, and why
    b = pg.evaluate("() => { var m=document.getElementById('sol-motion'); return [m.classList.contains('sol-wait'), m.querySelector('.sol-ow').textContent, m.title]; }")
    assert b[0] and b[1].endswith("paused") and "while a body is enlarged" in b[2], b
    pg.keyboard.press("Escape"); pg.wait_for_timeout(1300)                            # Esc: the card goes home first
    assert pg.evaluate("() => [window._focusedNodeId, window._altoSolarHold()]") == [None, ""]
    t0 = pg.evaluate("() => window._altoSolarT"); pg.wait_for_timeout(500)
    assert pg.evaluate("() => window._altoSolarT") != t0                              # and the orbits turn again
    pg.context.close()
    assert not errs, errs


def test_a_ship_chosen_while_the_rider_shows_is_drawn_at_once(browser, page):
    """Ship switching: the rider (on a ride, or orbiting as it fades after one) kept the ship it set off with."""
    pg, errs = _open(browser, page, wait=1400)
    pg.evaluate("() => { window._altoSolarStyles.set('chart'); window._altoSolarLock.set(true); window.enterFocus('u1-p1'); }")
    pg.wait_for_timeout(900)
    other = pg.evaluate("() => window._altoCraft.list.map(function(c){ return c.id; }).filter(function(i){ return i!==window._altoCraft.id(); })[0]")
    pg.click("#sol-tour .tb-next"); pg.wait_for_timeout(250)
    assert pg.evaluate("() => !!window._altoSolarLock.riding()")
    pg.evaluate("id => window._altoCraft.set(id)", other)
    assert pg.evaluate("""id => { var t=document.createElementNS('http://www.w3.org/2000/svg', 'g'); t.innerHTML=window._altoCraft.svg(id);
      return document.querySelector('#solar-svg .sol-rider .sol-ship').innerHTML===t.innerHTML; }""", other)
    pg.evaluate("() => window._altoSolarLock.set(false)")
    pg.context.close()
    assert not errs, errs


def test_normal_mode_moves_the_same_way_with_the_free_camera_besides(browser, page):
    """One way of moving (Luke, 2026-10-22: "Approve"): the Tour's bar, named buttons, → / ← / ↑ / ↓ and the whole
    system in normal mode too; Esc lets an enlarged card go first, then shows the whole system; panned away, the
    bar offers the way back. The switch is "Spokes only" again (off: the free camera besides)."""
    pg, errs = _open(browser, page, wait=1400)
    pg.evaluate("() => { window._altoSolarStyles.set('system'); window._altoSolarMotion.set(false); window.enterFocus('u1-p1'); }")
    pg.wait_for_timeout(1200)
    assert pg.evaluate("() => [window._altoSolarLock.get(), document.querySelector('#sol-lock span').textContent]") == [False, "Spokes only"]
    T = pg.evaluate("() => window._altoSolarLock.order()")
    bar = pg.evaluate("() => document.querySelector('#sol-tour .tb-next').textContent")
    assert bar.startswith("Next: "), bar
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(120)
    assert pg.evaluate("() => window._altoSolarLock.riding()")["to"] == T[T.index("u1-p1") + 1]   # a ride along the spokes, as in Spokes only
    _arrive(pg, T[T.index("u1-p1") + 1])
    up = pg.evaluate("id => window._altoSolarGeo().bodies[id].p", T[T.index("u1-p1") + 1])
    pg.keyboard.press("ArrowUp"); _arrive(pg, up)                                      # ↑ the parent
    # a wheel pans freely (no step); a free click still flies straight there
    s0 = pg.evaluate("() => document.getElementById('canvas').scrollTop")
    pg.mouse.move(700, 500); pg.mouse.wheel(0, 260); pg.wait_for_timeout(500)
    assert pg.evaluate("() => [document.getElementById('canvas').scrollTop!==" + str(s0) + ", window._altoSolarLock.riding(), window._focusedNodeId]") == [True, None, None]
    # (the scroll let the card go home); Esc: an enlarged card goes home first, then the whole system with your place ringed, then back
    pg.evaluate("id => window.enterFocus(id)", up); pg.wait_for_timeout(900)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(700)
    assert pg.evaluate("() => [window._focusedNodeId, window._altoSolarZoom()]") == [None, 1]
    pg.keyboard.press("Escape"); pg.wait_for_timeout(1400)
    assert pg.evaluate("() => [window._altoSolarZoom()<.9, !!document.getElementById('sol-here')]") == [True, True]
    pg.keyboard.press("Escape"); pg.wait_for_timeout(1400)
    assert pg.evaluate("() => [window._altoSolarZoom(), window._focusedNodeId]") == [1, up]
    # panned away from your place: the bar offers the way back
    pg.keyboard.press("Escape"); pg.wait_for_timeout(700)
    pg.evaluate("() => { var c=document.getElementById('canvas'); c.scrollTop+=2600; c.scrollLeft+=2600; }"); pg.wait_for_timeout(600)
    hb = pg.evaluate("() => { var b=document.querySelector('#sol-tour .tb-home'); return [b.hidden, b.textContent]; }")
    assert hb[0] is False and hb[1].startswith("↩ Back to "), hb
    pg.click("#sol-tour .tb-home")
    pg.wait_for_function("id => window._focusedNodeId===id", arg=up, timeout=6000)
    pg.context.close()
    assert not errs, errs
