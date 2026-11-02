"""System: the digit keys fly to a neighbour and Esc / Backspace climb a level at a time (Luke, 2026-10-28:
"pressing 1, 2 or 3 should take you to those moons ... an easier way to go back up from a moon to a planet").
Browser checks run in Chromium and WebKit (Playwright; skipped without them)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_solar_navopt import AT, _arrive, _at, _hood, page  # noqa: E402,F401
from test_solar_draw import _open, browser  # noqa: E402,F401

STYLES = ["system", "chart", "retro", "3d"]


@pytest.mark.parametrize("style", STYLES)
def test_a_digit_flies_to_that_neighbour(browser, page, style):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    _at(pg, style=style)
    k = _hood(pg)["kids"]
    pg.keyboard.press("2")
    _arrive(pg, k[1])                                       # a planet: its second moon
    pg.keyboard.press("1")
    _arrive(pg, k[0])                                       # then, from a moon, the first of the moons beside it
    pg.context.close()
    assert not errs, errs


@pytest.mark.parametrize("style", STYLES)
def test_a_digit_is_the_number_a_body_shows(browser, page, style):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    _at(pg, style=style)
    k = _hood(pg)["kids"]
    num = pg.evaluate("id => window._altoSolarNavApi.num(id)", k[1])
    assert num.isdigit(), num                                # (a moon's face: the last part of its path number)
    pg.keyboard.press(num)
    _arrive(pg, k[1])
    pg.context.close()
    assert not errs, errs


@pytest.mark.parametrize("key", ["Escape", "Backspace"])
@pytest.mark.parametrize("style", STYLES)
def test_up_a_level_climbs_moon_to_planet_then_lets_go_then_the_whole_system(browser, page, style, key):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    moon = _hood(pg)["kids"][0]
    _at(pg, at=moon, style=style)
    h = _hood(pg, moon)
    assert h["up"] == AT and len(h["sibs"]) == 2
    pg.keyboard.press(key)
    _arrive(pg, AT)                                          # a moon: its planet (not the other moon)
    pg.keyboard.press(key)                                   # a planet lets go, as Esc always did (no ride to its sun)
    pg.wait_for_function("() => !window._focusedNodeId && !window._altoSolarLock.riding()", timeout=9000)
    pg.keyboard.press(key)                                   # nothing enlarged: the whole system
    pg.wait_for_function("() => window._altoSolarNavApi.ov()", timeout=9000)
    pg.context.close()
    assert not errs, errs


# ── Luke, 2026-10-28: "the overall box [of the minimap] changes size" and "the bottom toggles ... are changing when you
#    move around within it ... they should remain as static as possible" ──
ROWS = """() => { var out={};
  ['sol-ctl', 'nvo-a'].forEach(function(id){ var e=document.getElementById(id); if(!e) return;
    [e].concat([].slice.call(e.children)).forEach(function(c, i){ var r=c.getBoundingClientRect(); if(!r.width || getComputedStyle(c).display==='none') return;
      out[id+'/'+(i ? (c.id || c.getAttribute('data-n') || c.className.split(' ')[0] || c.tagName) : '')]=[r.left, r.top, r.width, r.height].map(function(v){ return Math.round(v*2)/2; }); }); });
  return out; }"""
FRAME = """() => { var m=document.getElementById('nvo-map'); if(!m || !m.classList.contains('on')) return null; var r=m.getBoundingClientRect(); return [Math.round(r.width*2)/2, Math.round(r.height*2)/2]; }"""


def _ids(pg):
    return pg.evaluate("() => Object.keys(window._altoSolarGeo().bodies)")


@pytest.mark.parametrize("style", STYLES)
def test_the_bottom_row_and_the_minimap_frame_never_change_as_you_move(browser, page, style):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    pg.evaluate("() => { localStorage.removeItem('alto-solar-map'); localStorage.removeItem('alto-solar-map-at'); }")
    ids = _ids(pg)
    assert len(ids) >= 8, ids
    seen, frames = [], []
    for i in ids * 2 if len(ids) < 10 else ids:
        _at(pg, at=i, style=style)
        seen.append((i, pg.evaluate(ROWS)))
        f = pg.evaluate(FRAME)
        if f:
            frames.append((i, f))
    pg.context.close()
    assert not errs, errs
    base = seen[0][1]
    for i, rows in seen:
        assert rows == base, (i, {k: (rows.get(k), base.get(k)) for k in set(rows) | set(base) if rows.get(k) != base.get(k)})
    assert len(frames) >= 4, frames
    assert all(f == frames[0][1] for _, f in frames), [(i, f) for i, f in frames if f != frames[0][1]]


@pytest.mark.parametrize("style", STYLES)
def test_the_minimap_keeps_its_size_and_only_goes_faint_while_flying(browser, page, style):
    pg, errs = _open(browser, page, reduced=False, wait=1400)
    pg.evaluate("() => { localStorage.removeItem('alto-solar-map'); localStorage.removeItem('alto-solar-map-at'); }")
    k = _hood(pg)["kids"]
    _at(pg, style=style)
    pg.wait_for_selector("#nvo-map.on", timeout=4000)
    SAMPLE = "() => { var m=document.getElementById('nvo-map'); if(!m) return null; var r=m.getBoundingClientRect(); return r.width ? [Math.round(r.width*2)/2, Math.round(r.height*2)/2, +getComputedStyle(m).opacity] : null; }"
    pg.wait_for_function("() => { var m=document.getElementById('nvo-map'); return m && +getComputedStyle(m).opacity===1; }", timeout=4000)
    want = pg.evaluate(SAMPLE)
    pg.keyboard.press("2")
    sizes, ops = set(), []
    for _ in range(40):
        pg.wait_for_timeout(100)
        f = pg.evaluate(SAMPLE)
        if f:
            sizes.add(tuple(f[:2]))
            ops.append(f[2])
    _arrive(pg, k[1])
    pg.wait_for_timeout(900)
    end = pg.evaluate(SAMPLE)
    pg.context.close()
    assert not errs, errs
    assert sizes <= {tuple(want[:2])}, (want, sizes)
    assert min(ops) < 0.9, ops
    assert end and end[2] == 1 and tuple(end[:2]) == tuple(want[:2]), (want, end)


def test_on_a_phone_the_bottom_row_stays_put_too(browser, page):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=browser.browser_type.name == "chromium")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(page.as_uri())
    pg.wait_for_timeout(1500)
    pg.evaluate("() => document.documentElement.classList.add('phone-whole')")
    ids = _ids(pg)
    seen = []
    for n, i in enumerate(ids):
        pg.evaluate("i => window.enterFocus(i)", i)
        _arrive(pg, i)
        if not n:
            pg.evaluate("() => document.getElementById('nvo-where').click()")
            pg.wait_for_timeout(400)
        seen.append((i, pg.evaluate(ROWS)))
    ctx.close()
    assert not errs, errs
    base = seen[0][1]
    for i, rows in seen:
        assert rows == base, (i, {k: (rows.get(k), base.get(k)) for k in set(rows) | set(base) if rows.get(k) != base.get(k)})


# ── Luke, 2026-10-28: "minimap in 3D system isn't quite expanding to the whole system" ──
WHOLE3D = """() => { var G=window._altoSolarGeo(), S=window._altoSolar3D, c=document.getElementById('canvas'), r=c.getBoundingClientRect(), xs=[], ys=[];
  Object.keys(G.bodies).forEach(function(i){ var q=S.project(i); if(q){ xs.push(q.x-r.left); ys.push(q.y-r.top); } });
  return {w:r.width, h:r.height, n:xs.length, x0:Math.min.apply(0, xs), x1:Math.max.apply(0, xs), y0:Math.min.apply(0, ys), y1:Math.max.apply(0, ys), d:S.cam().d}; }"""


@pytest.mark.parametrize("vw,vh", [(1500, 950), (900, 900), (1200, 640)])
def test_in_3d_the_whole_system_view_frames_every_body_at_any_aspect(browser, page, vw, vh):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    pg.set_viewport_size({"width": vw, "height": vh})
    pg.wait_for_timeout(500)
    pg.evaluate("() => window._altoSolarStyles.set('3d')")
    pg.wait_for_timeout(1500)
    home = pg.evaluate(WHOLE3D)
    pg.evaluate("() => window._altoSolarNavApi.step('ov')")
    pg.wait_for_function("() => window._altoSolarNavApi.ov()", timeout=6000)
    last = [0]

    def settled():
        d = pg.evaluate("() => window._altoSolar3D.cam().d")
        ok = abs(d - last[0]) < 0.5
        last[0] = d
        return ok
    for _ in range(40):
        pg.wait_for_timeout(250)
        if settled():
            break
    w = pg.evaluate(WHOLE3D)
    pg.context.close()
    assert not errs, errs
    assert w["n"] >= 8, w
    mx, my = w["w"] * 0.03, w["h"] * 0.03
    assert w["x0"] >= mx and w["x1"] <= w["w"] - mx and w["y0"] >= my and w["y1"] <= w["h"] - my, w          # every body in, with a margin
    assert (w["x1"] - w["x0"]) > 0.3 * w["w"] or (w["y1"] - w["y0"]) > 0.3 * w["h"], w                         # and not a speck in the middle
    assert w["d"] > home["d"], (home, w)


# ── Luke, 2026-11-01: "Still can't change the size of the minimap, and it should not still be up if overview or a detail
#    page is present on screen. It shouldn't be jumping around so much either" (drag a corner handle; kept per viewer) ──
GEO = """() => { var m=document.getElementById('nvo-map'); if(!m) return null; var r=m.getBoundingClientRect(), c=getComputedStyle(m);
  return {l:Math.round(r.left), t:Math.round(r.top), r:Math.round(r.right), b:Math.round(r.bottom), w:Math.round(r.width), h:Math.round(r.height), on:m.classList.contains('on'),
          shown:c.visibility!=='hidden' && +c.opacity>0.5, saved:localStorage.getItem('alto-solar-map-h')}; }"""
CLEAR = "() => { ['alto-solar-map', 'alto-solar-map-at', 'alto-solar-map-h'].forEach(function(k){ localStorage.removeItem(k); }); }"


def _shown(pg):
    pg.wait_for_function("() => { var m=document.getElementById('nvo-map'); return m && m.classList.contains('on') && +getComputedStyle(m).opacity===1; }", timeout=6000)
    return pg.evaluate(GEO)


def _drag_handle(pg, dx, dy):
    b = pg.evaluate("() => { var r=document.querySelector('#nvo-map .rz').getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]; }")
    pg.mouse.move(b[0], b[1])
    pg.mouse.down()
    for i in range(1, 9):
        pg.mouse.move(b[0] + dx * i / 8, b[1] + dy * i / 8)
    pg.mouse.up()
    pg.wait_for_timeout(500)


@pytest.mark.parametrize("style", ["system", "chart", "retro", "3d"])
def test_dragging_the_corner_handle_sets_the_minimaps_size_and_it_is_kept(browser, page, style):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    pg.evaluate(CLEAR)
    _at(pg, style=style)
    g0 = _shown(pg)
    assert g0["saved"] is None, g0
    _drag_handle(pg, -80, -60)
    g1 = pg.evaluate(GEO)
    assert g1["h"] > g0["h"] + 20 and g1["w"] > g0["w"] + 20, (g0, g1)                    # bigger
    assert abs(g1["r"] - g0["r"]) <= 2 and abs(g1["b"] - g0["b"]) <= 2, (g0, g1)            # grown into the free room from the opposite corner
    assert g1["saved"] and int(g1["saved"]) > 230, g1
    _drag_handle(pg, 160, 120)                                                              # and smaller again (never under a floor)
    g2 = pg.evaluate(GEO)
    assert 100 <= int(g2["saved"]) < int(g1["saved"]) and g2["h"] < g1["h"], (g1, g2)
    _drag_handle(pg, -60, -45)
    want = pg.evaluate(GEO)
    k = _hood(pg)["kids"]
    _at(pg, at=k[0], style=style)                                                            # another body, same style: the size stays
    assert pg.evaluate(GEO)["h"] == want["h"], (want, pg.evaluate(GEO))
    pg.reload()
    pg.wait_for_timeout(1400)
    _at(pg, style=style)
    again = _shown(pg)
    assert again["h"] == want["h"] and again["saved"] == want["saved"], (want, again)        # kept per viewer, across a reload
    pg.dblclick("#nvo-map .rz")
    pg.wait_for_timeout(500)
    rst = pg.evaluate(GEO)
    assert rst["saved"] is None and abs(rst["h"] - g0["h"]) <= 2, (g0, rst)                  # double-click: the usual size
    pg.context.close()
    assert not errs, errs


@pytest.mark.parametrize("style", STYLES)
def test_the_minimap_hides_under_the_overview_and_a_detail_page_and_comes_back_where_it_was(browser, page, style):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    pg.evaluate(CLEAR)
    _at(pg, style=style)
    g0 = _shown(pg)
    pg.evaluate("() => document.getElementById('summary-wrap').classList.add('open')")      # the Overview panel
    pg.wait_for_function("() => { var m=document.getElementById('nvo-map'); return !m || !m.classList.contains('on'); }", timeout=4000)
    pg.wait_for_timeout(500)
    g = pg.evaluate(GEO)
    assert g and not g["shown"], g
    pg.evaluate("() => document.getElementById('summary-wrap').classList.remove('open')")
    assert pg.evaluate(GEO) is not None and _shown(pg) == g0, g0
    pg.evaluate("() => document.getElementById('detail-page').classList.add('visible')")    # a detail page
    pg.wait_for_function("() => !document.getElementById('nvo-map')", timeout=4000)
    pg.evaluate("() => document.getElementById('detail-page').classList.remove('visible')")
    pg.wait_for_function("() => { var m=document.getElementById('nvo-map'); return m && m.classList.contains('on'); }", timeout=6000)
    back = _shown(pg)
    assert (back["l"], back["t"], back["w"], back["h"]) == (g0["l"], g0["t"], g0["w"], g0["h"]), (g0, back)   # not left at a CSS corner
    pg.context.close()
    assert not errs, errs


@pytest.mark.parametrize("style", STYLES)
def test_the_minimap_stays_put_across_bodies_and_style_switches(browser, page, style):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    pg.evaluate(CLEAR)
    ids = _ids(pg)
    spots = []
    for i in ids[:8]:
        _at(pg, at=i, style=style)
        g = _shown(pg)
        spots.append((i, g["l"], g["t"], g["w"], g["h"]))
    for other in [s for s in STYLES if s != style]:
        pg.evaluate("s => window._altoSolarStyles.set(s)", other)
        pg.wait_for_timeout(500)
        g = pg.evaluate(GEO)
        assert g and g["on"], (other, g)
        spots.append((other, g["l"], g["t"], g["w"], g["h"]))
    pg.context.close()
    assert not errs, errs
    assert all(s[1:] == spots[0][1:] for s in spots), spots
