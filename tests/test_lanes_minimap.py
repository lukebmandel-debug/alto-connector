"""The horizontal timeline's minimap (Luke 2026-11-26: "instead of the view whole timeline button in the middle nav controls zooming out,
make a minimap simplified where we usually have them that shows where the user is in the whole thing"). On a computer the bar loses its
whole-timeline button and a minimap sits where every desktop minimap does (minimap_home.py): just above the bottom-right buttons, as wide
as they are. It draws the board (cards, main line), lights the event the steps are on, boxes what the window shows, and a click goes to the
nearest event. A phone keeps its bar as it was (the button, no minimap). WebKit."""
import pytest

from tests.test_lanes_extend_1125 import _open, site  # noqa: F401  (the fixture)

MM = """() => { const m = document.getElementById('ln-mm'), cs = m && getComputedStyle(m), r = m && m.getBoundingClientRect(), ov = document.querySelector('#lanes-nav .lnv-ov');
  const row = window._altoMmRow && window._altoMmRow(), v = m && m.querySelector('.mm-v'), vr = v && v.getBoundingClientRect(), h = m && m.querySelector('.mm-c.h');
  return {on: !!(m && m.classList.contains('on') && cs.display !== 'none' && +cs.opacity > .9), r: r && [r.left, r.top, r.right, r.bottom], row,
    ovShown: !!(ov && getComputedStyle(ov).display !== 'none'), box: vr && [vr.left, vr.width], lit: !!h, cards: m ? m.querySelectorAll('.mm-c').length : 0,
    line: !!(m && m.querySelector('.mm-l')), cur: window._altoLanesCurrent && window._altoLanesCurrent(), W: innerWidth, H: innerHeight}; }"""


@pytest.mark.parametrize("name", ["on", "plain"])
def test_the_minimap_sits_over_the_bottom_right_buttons_and_the_bar_loses_its_zoom_out(site, name):
    ctx, pg = _open(site, name)
    s = pg.evaluate(MM)
    assert s["on"] and not s["ovShown"], s
    assert abs(s["r"][0] - s["row"][0]) < 1.5 and abs(s["r"][2] - s["row"][2]) < 1.5, s          # as wide as the row, edge on edge
    assert 4 <= s["row"][1] - s["r"][3] <= 20, s                                                    # just above it
    assert s["r"][2] <= s["W"] - 19.5 and s["r"][1] >= 0, s                                          # 20 px from the edge
    assert s["line"] and s["cards"] >= 5 and s["lit"] and s["box"][1] > 2, s
    assert not pg._errs, pg._errs
    ctx.close()


def test_the_box_follows_the_steps_and_a_click_goes_there(site):
    ctx, pg = _open(site, "on")
    a = pg.evaluate(MM)
    pg.keyboard.press("ArrowRight")
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(1800)
    b = pg.evaluate(MM)
    assert b["cur"] != a["cur"] and b["box"][0] > a["box"][0] + 1, (a, b)                       # the box went along with the camera
    x, y = b["r"][0] + 10, (b["r"][1] + b["r"][3]) / 2                                            # the start of the map: the first events
    pg.mouse.click(x, y)
    pg.wait_for_timeout(1800)
    c = pg.evaluate(MM)
    assert c["cur"] == a["cur"] and c["box"][0] < b["box"][0] - 1, (a, b, c)
    assert not pg._errs, pg._errs
    ctx.close()


def test_the_whole_timeline_hides_it_and_it_comes_back(site):
    ctx, pg = _open(site, "on")
    pg.evaluate("() => window._altoLanesZoom.whole()")
    pg.wait_for_timeout(1200)
    assert not pg.evaluate(MM)["on"]
    pg.evaluate("() => window._altoLanesZoom.whole()")
    pg.wait_for_timeout(1500)
    assert pg.evaluate(MM)["on"]
    ctx.close()


@pytest.mark.parametrize("w,h", [(390, 844), (844, 390)])
def test_a_phone_keeps_its_bar_and_has_no_minimap(site, w, h):
    ctx, pg = _open(site, "on", w=w, h=h, phone=True, q="?view=whole")
    s = pg.evaluate(MM)
    assert not s["on"] and s["ovShown"], s
    ctx.close()


def test_a_window_too_narrow_for_it_keeps_the_bars_button(site):
    ctx, pg = _open(site, "on", w=768, h=1024)
    s = pg.evaluate(MM)
    assert not s["on"] and s["ovShown"], s                                                       # never over the bar: the bar keeps its way to the whole timeline
    ctx.close()
