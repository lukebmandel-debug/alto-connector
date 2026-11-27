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
    assert not pg.evaluate("() => { const b = document.querySelector('#lanes-nav .lnv-map'); return !!b && getComputedStyle(b).display !== 'none'; }")   # (no map switch on a phone)
    ctx.close()


def test_a_window_too_narrow_for_it_has_no_minimap_over_the_bar(site):
    ctx, pg = _open(site, "on", w=768, h=1024)
    s = pg.evaluate(MM)
    assert not s["on"] and not s["ovShown"], s      # never over the bar; no whole-timeline button on a desktop (Luke 2026-11-27, Board (b)): pinch, ⌘ + scroll, − reach it
    ctx.close()


def test_its_button_in_the_bar_turns_it_off_and_on_and_the_page_remembers(site):
    """Luke 2026-11-26: "should be able to toggle minimap on/off like usual, so bring back that button"."""
    ctx, pg = _open(site, "on")
    btn = "#lanes-nav .lnv-map"
    assert pg.get_attribute(btn, "aria-pressed") == "true" and pg.get_attribute(btn, "aria-label") == "Hide the minimap"
    pg.click(btn)
    pg.wait_for_timeout(600)
    s = pg.evaluate(MM)
    assert not s["on"] and not s["ovShown"], s                                                   # off (the desktop has no whole-timeline button since 2026-11-27)
    assert pg.get_attribute(btn, "aria-pressed") == "false"
    pg.reload(wait_until="load")
    pg.wait_for_timeout(3000)
    assert not pg.evaluate(MM)["on"]                                                              # remembered for this page
    pg.click(btn)
    pg.wait_for_timeout(800)
    s = pg.evaluate(MM)
    assert s["on"] and not s["ovShown"], s
def test_each_unit_has_its_band_divider_and_numeral_on_the_map(site):
    """Luke 2026-11-26: "Add some unit label distinction on minimap"."""
    ctx, pg = _open(site, "on")
    u = pg.evaluate("""() => { const m = document.getElementById('ln-mm'), r = m.getBoundingClientRect();
      const n = [...m.querySelectorAll('.mm-un')].map(e => { const q = e.getBoundingClientRect(); return {x: q.left, t: e.textContent, c: getComputedStyle(e).color, in: q.left >= r.left && q.right <= r.right && q.top >= r.top && q.bottom <= r.bottom}; });
      return {units: document.querySelectorAll('#world .lanes-unit').length, bands: m.querySelectorAll('.mm-ub').length, divs: m.querySelectorAll('.mm-ud').length, n}; }""")
    assert u["units"] >= 2 and u["bands"] == u["units"] and u["divs"] == u["units"] - 1 and len(u["n"]) == u["units"], u
    xs = [q["x"] for q in u["n"]]
    assert xs == sorted(xs) and all(q["in"] and q["t"] for q in u["n"]) and len({q["c"] for q in u["n"]}) > 1, u   # in order, inside the map, each its unit's colour
    assert not pg._errs, pg._errs
    ctx.close()


def test_a_phone_bar_button_opens_the_whole_view_only_and_prev_next_come_back(site):
    """Luke 2026-11-27: "the back to events button on the left of the middle toggle isn't useful": a phone's button opens the whole
    timeline and keeps its name (no "Back to the events"); ‹ › (or Esc, a tap) come back."""
    ctx, pg = _open(site, "on", w=390, h=844, phone=True, q="?view=whole")
    b = "#lanes-nav .lnv-ov"
    lab = pg.get_attribute(b, "aria-label")
    pg.click(b)
    pg.wait_for_timeout(1200)
    assert pg.evaluate("window._altoLanesZoom.s()") < 1 and pg.get_attribute(b, "aria-label") == lab and "Back" not in lab
    pg.click(b)                                                                                    # pressed again: still the whole view
    pg.wait_for_timeout(900)
    assert pg.evaluate("window._altoLanesZoom.s()") < 1
    pg.click("#lanes-nav .lnv-next")                                                               # › : back to the events
    pg.wait_for_timeout(1400)
    assert pg.evaluate("window._altoLanesZoom.s()") == 1
    assert not pg._errs, pg._errs
    ctx.close()
