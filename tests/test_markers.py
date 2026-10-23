"""1.9.145 markers (markers.py): Luke — "When you're zooming in on the museum palace, in the blueprint mode, all the little buttons for
nodes are shifting so much and changing size that it looks like it's really glitchy." Map markers stay pinned and one size while a
zoom runs; layout and level of detail are decided once it settles, held, and glide.

The browser tests run the real hosted blueprint (Chromium, as test_building_palace_render) and are skipped without Playwright."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import markers, palace_building_asset as pba  # noqa: E402
from tests.test_building_palace_render import _open, browser, html, pw  # noqa: E402,F401


def test_the_blueprint_carries_the_shared_markers_module():
    assert pba.BUILDING_ASSET.startswith(markers.MARKERS_JS)
    assert ".alto-mk-glide .alto-mk{" in pba.BUILDING_ASSET              # its CSS rides in the blueprint's stylesheet
    js = pba.BUILDING_JS
    assert "function placePills" not in js                               # the per-frame collision pass is gone
    vb = js[js.index("function applyVB(){"):js.index("// ── panel ──")]
    assert "S.mkSet.poke(); movePills();" in vb                          # a zoom frame only moves the chips; layout waits for the settle
    assert "AltoMarkers.settle(function(){ layoutPills(true); }" in js
    assert "AltoMarkers.band(S.near" in js                               # the title threshold is a band
    assert "'gesturechange'" in js                                       # Safari's trackpad pinch zooms the blueprint


def test_viewbox_is_not_rounded_to_centimetres():
    # f2 (0.01 m) on the viewBox moved the whole drawing in ~3 px steps at a close zoom
    assert "S.svg.setAttribute('viewBox',vb.map(f2)" not in pba.BUILDING_JS


@pytest.fixture()
def blank(browser):  # noqa: F811
    page = browser.new_page()
    page.set_content("<!doctype html><body><script>" + markers.MARKERS_JS + "</script></body>")
    yield page
    page.close()


def test_place_keeps_a_place_while_it_is_free_and_band_holds(blank):
    r = blank.evaluate("""() => { const M = AltoMarkers, st = {}, c = [[0, 0], [0, 30], [0, -30]];
      const a = M.place([{id: 'a', x: 0, y: 0, w: 40, h: 20, c}, {id: 'b', x: 10, y: 0, w: 40, h: 20, c}], st);
      const b = M.place([{id: 'a', x: 0, y: 0, w: 40, h: 20, c}, {id: 'b', x: 41, y: 0, w: 40, h: 20, c}], st);   // home just free: b stays put
      const d = M.place([{id: 'a', x: 0, y: 0, w: 40, h: 20, c}, {id: 'b', x: 60, y: 0, w: 40, h: 20, c}], st);   // clearly free: b goes home
      return [a.b.dy, b.b.dy, d.b.dy, M.band(false, .5, .4, .6), M.band(true, .5, .4, .6), M.band(true, .3, .4, .6)]; }""")
    assert r == [30, 30, 0, False, True, False]


def _chips(page):
    return page.evaluate("AltoMarkers.debug('bldg')")


def test_chips_stay_pinned_and_one_size_while_the_wheel_zooms(browser, html):  # noqa: F811
    page, errors = _open(browser, html)
    try:
        page.wait_for_function("window.AltoBuilding && AltoBuilding.plan")
        page.click("#bldg-root .bl-tab[data-level=g]")
        page.wait_for_timeout(400)
        frames = page.evaluate("""async () => { const svg = document.querySelector('#bldg-root svg.bl-svg'), r = svg.getBoundingClientRect(), out = [];
          for (let i = 0; i < 24; i++) { svg.dispatchEvent(new WheelEvent('wheel', {deltaY: i < 12 ? -40 : 40, clientX: r.left + r.width * .4, clientY: r.top + r.height * .6, bubbles: true, cancelable: true}));
            await new Promise(f => requestAnimationFrame(f)); out.push(AltoMarkers.debug('bldg')); } return out; }""")
        assert len(frames[0]) == 3
        for a, b in zip(frames, frames[1:]):
            for p, q in zip(a, b):
                assert abs((q["x"] - q["ax"]) - (p["x"] - p["ax"])) < .6 and abs((q["y"] - q["ay"]) - (p["y"] - p["ay"])) < .6
                assert abs(q["w"] - p["w"]) < .1 and abs(q["h"] - p["h"]) < .1
        page.wait_for_timeout(600)                                        # settled: laid out once, then still
        a = _chips(page); page.wait_for_timeout(200); b = _chips(page)
        assert [(m["x"], m["y"]) for m in a] == [(m["x"], m["y"]) for m in b]
        assert errors == []
    finally:
        page.close()


def test_a_safari_pinch_zooms_the_blueprint(browser, html):  # noqa: F811
    page, errors = _open(browser, html)
    try:
        page.wait_for_function("window.AltoBuilding && AltoBuilding.plan")
        w0 = page.evaluate("document.querySelector('#bldg-root svg.bl-svg').viewBox.baseVal.width")
        page.evaluate("""() => { const svg = document.querySelector('#bldg-root svg.bl-svg');
          const ev = (t, s) => { const e = new Event(t, {bubbles: true, cancelable: true}); Object.defineProperty(e, 'scale', {value: s});
            Object.defineProperty(e, 'clientX', {value: 600}); Object.defineProperty(e, 'clientY', {value: 400}); svg.dispatchEvent(e); return e.defaultPrevented; };
          ev('gesturestart', 1); ev('gesturechange', 1.5); ev('gesturechange', 2); ev('gestureend', 2); }""")
        w1 = page.evaluate("document.querySelector('#bldg-root svg.bl-svg').viewBox.baseVal.width")
        assert abs(w1 / w0 - .5) < .01
        assert errors == []
    finally:
        page.close()


# ── the city Mind Palace (palace.py): a zoom preview is a transform of the whole board ──

def _palace_js():
    from alto.build import palace
    return palace.PALACE_JS, palace.PALACE_CSS


def test_city_tags_keep_their_size_while_the_board_is_scaled():
    js, css = _palace_js()
    pv = js[js.index("function pvSet(z, sxT, syT){"):js.index("function placeAll(){")]
    assert "c.style.scale=k" in pv and "pfz(z)/pfz(PV.zc)*PV.zc/z" in pv       # each tag scaled back by itself ...
    assert "setProperty('--pvk'" not in pv and "setProperty('--pz'" not in pv  # ... never a variable on #world / the drawing (restyles the whole city: ~140-300 ms a frame in WebKit)
    assert "requestAnimationFrame(function(){ if(PV && PV.n===n) placeAll(); })" in pv   # settled = no input up to the next frame, not a bare timer


def test_city_names_come_back_by_a_fade_and_tags_are_held():
    js, css = _palace_js()
    assert "if(Math.abs(Math.log(Z/p.zc))>.12) pvIn(svgD);" in js and "g.animate([{opacity:0}, {opacity:1}]" in js
    assert "t.e._nbP=[t.dx, t.dy]" in js and "!clash(t.ax+pv[0], t.ay+pv[1], t.w-6, t.h-4)" in js   # a tag sent aside keeps its place while free
    assert ".node.nb-gl:not(.focused) .node-card{transition:translate" in css                  # and glides there
    assert "if(s<.55 || s>1.8){ pvIn(MM.svg); pmCommit(z); s=1; }" in js                       # the phone's commits fade the names too
    assert "function pmCommit(z){ var sv=MM.svg; MM.z=z;" in js                                # (palace_fillin's anchor)


# ── System (solar_draw.py): markers.py's rules inline ──

def test_system_labels_are_decided_once_a_zoom_settles_held_and_faded():
    from alto.build import solar_draw
    js, css = solar_draw.SOLAR_JS, solar_draw.SOLAR_CSS
    assert "bnd(c,'sol-lo',sc,.5)" in js.replace(" ", "") and "function bnd(" in js          # thresholds are bands
    assert "DSP=1" in js and "||DSP)return" in js.replace(" ", "")                            # no re-placing while a zoom runs
    assert "pv=b.lb._x?-1:b.lb._p||0" in js.replace(" ", "") and "e=b.lb._x&&i!==pv?-2*k:0" in js.replace(" ", "")   # a label keeps its side while free, a hidden one returns only when clearly free
    assert "#canvas.sol-glide #world .node[data-solar]>.sol-lbl{transition:" in css
    assert "sol-lm #world .node[data-solar=moon]>.sol-lbl{display:none" not in css            # level of detail fades
