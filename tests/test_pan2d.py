"""Two-finger scrolling pans on both axes at once (alto/build/pan2d.py): the Mind Palace city map and Hub & spoke / Star chart.

Safari's own scroll of an overflow box keeps to the predominant axis of a trackpad gesture (WebKit's
WheelEventDeltaFilterMac); the page now scrolls the map from the wheel events' two deltas itself. Synthetic events cannot
show Safari's filter (scratch/safari/pan2d probe is the real-Safari check); these hold what the page does with the events:
both axes, the browser's own distances, Shift, line mode, momentum, and nothing taken from zoom, focus or panels.
Offline; Chromium and WebKit through Playwright (skipped without them); no sound, fleet or ride pages."""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.pan2d import PAN2D_JS, SOLAR_PAN2D_JS  # noqa: E402
import test_palace as tp  # noqa: E402
import test_solar_draw as sd  # noqa: E402

BIG = [[[2, 2, 2], [2, 2], [2, 2, 2], [2], [2, 2]], [[0, 0], [0, 0, 0]], [[1, 1], [1], [2]]]
API = {"palace": "_altoPalacePan2d", "solar": "_altoSolarPan2d"}


@pytest.fixture(scope="module")
def htmls():
    pal, _ = build_timeline(*load_brief(copy.deepcopy(tp.bundle())))
    return {"palace": pal, "solar": sd._page(BIG, suns={0: 1})}


def test_both_pages_carry_it_once_and_a_plain_outline_does_not(htmls):
    for name, h in htmls.items():
        assert h.count("window._altoPan2d=function") == 1, name
        assert ("window._altoPalacePan2d=" in h) == (name == "palace")
        assert (SOLAR_PAN2D_JS in h) == (name == "solar")
    doc = sd.solar_doc(BIG)
    for k in ("layout", "hub_look"):
        doc["brief"].pop(k)
    other, _ = build_timeline(*load_brief(doc))
    assert "_altoPan2d" not in other


def test_the_listener_is_on_the_canvas_not_window_and_small():
    assert "c.addEventListener('wheel', onWheel, {passive:false})" in PAN2D_JS
    assert "window.addEventListener('wheel'" not in PAN2D_JS
    import gzip
    assert len(gzip.compress((PAN2D_JS + SOLAR_PAN2D_JS).encode())) < 1300


# ── in a browser ────────────────────────────────────────────────────────────
pw = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            try:
                if request.param != "chromium":
                    raise e
                b = p.chromium.launch(channel="chrome")
            except Exception:
                pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


@pytest.fixture(scope="module")
def files(tmp_path_factory, htmls):
    d = tmp_path_factory.mktemp("pan2d")
    out = {}
    for k, h in htmls.items():
        (d / f"{k}.html").write_text(h, encoding="utf-8")
        out[k] = d / f"{k}.html"
    return out


X, Y = 700, 600


def _open(browser, files, name):
    pg = browser.new_context(viewport={"width": 1500, "height": 950}).new_page()
    pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.goto(files[name].as_uri())
    pg.wait_for_timeout(1800)
    pg.mouse.move(X, Y)
    if name == "palace":                       # the test city fits the window: zoom in so it has room to pan
        for _ in range(3):
            pg.keyboard.press("Control+=")
            pg.wait_for_timeout(650)
        pg.wait_for_timeout(400)
    pg.api = API[name]
    _at(pg, 200, 200)
    return pg


def _at(pg, x, y):
    pg.evaluate("([x,y])=>{var c=document.getElementById('canvas'); c.scrollLeft=x; c.scrollTop=y;}", [x, y])
    pg.wait_for_timeout(250)


def _pos(pg):
    return pg.evaluate("()=>{var c=document.getElementById('canvas'), r=c.getBoundingClientRect();"
                       "return {x:c.scrollLeft, y:c.scrollTop, z:r.width/c.offsetWidth, n:window['" + pg.api + "'].n}}")


def _wheels(pg, evs):
    """dispatch WheelEvents ({dx, dy, mode, shift, ctrl, gap ms}) at the pointer, then the frame; the events prevented"""
    return pg.evaluate("""async ([evs, api])=>{
      var t=document.elementFromPoint(%d, %d), p=0;
      for(var e of evs){ if(e.gap) await new Promise(r=>setTimeout(r, e.gap));
        var w=new WheelEvent('wheel', {deltaX:e.dx||0, deltaY:e.dy||0, deltaMode:e.mode||0, shiftKey:!!e.shift, ctrlKey:!!e.ctrl,
          clientX:%d, clientY:%d, bubbles:true, cancelable:true});
        t.dispatchEvent(w); if(w.defaultPrevented) p++; }
      window[api].flush(); await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))); return p; }""" % (X, Y, X, Y),
                       [evs, pg.api])


def _errs(pg):
    """script errors, less file:// refusing the hosted scripts (ride, cloud: never loaded here)"""
    skip = ("access control", "palace-ride", "Cross origin", "CORS", "local resource")
    return [e for e in pg.errs if not any(k in e for k in skip)]


@pytest.mark.parametrize("name", ["palace", "solar"])
def test_a_diagonal_trackpad_scroll_moves_both_axes_as_far_as_the_browser_would(browser, files, name):
    pg = _open(browser, files, name)
    a = _pos(pg)
    assert pg.evaluate("document.getElementById('canvas').contains(document.elementFromPoint(%d,%d))" % (X, Y))
    for _ in range(10):
        pg.mouse.wheel(30, 20)
        pg.wait_for_timeout(25)
    pg.wait_for_timeout(300)
    b = _pos(pg)
    assert b["n"] - a["n"] == 10, "every plain wheel over the map is the page's"
    assert abs((b["x"] - a["x"]) - 300 / a["z"]) <= 2 and abs((b["y"] - a["y"]) - 200 / a["z"]) <= 2, (a, b)
    # pure vertical, pure horizontal: the other axis stays put
    _at(pg, 200, 200); a = _pos(pg)
    assert _wheels(pg, [{"dy": 40}] * 5) == 5
    b = _pos(pg)
    assert abs(b["x"] - a["x"]) < 1 and abs((b["y"] - a["y"]) - 200 / a["z"]) <= 2, (a, b)
    _at(pg, 400, 400); a = _pos(pg)
    _wheels(pg, [{"dx": -40, "gap": 200}] + [{"dx": -40}] * 4)
    b = _pos(pg)
    assert abs((b["x"] - a["x"]) + 200 / a["z"]) <= 2 and abs(b["y"] - a["y"]) < 1, (a, b)
    assert not _errs(pg), pg.errs
    pg.context.close()


@pytest.mark.parametrize("name", ["palace", "solar"])
def test_shift_line_mode_and_a_momentum_tail(browser, files, name):
    pg = _open(browser, files, name)
    a = _pos(pg)
    _wheels(pg, [{"dy": 30, "shift": True, "gap": 200}] * 1 + [{"dy": 30, "shift": True}] * 3)   # a mouse wheel with Shift
    b = _pos(pg)
    assert abs((b["x"] - a["x"]) - 120 / a["z"]) <= 2 and abs(b["y"] - a["y"]) < 1, (a, b)
    _at(pg, 200, 200); a = _pos(pg)
    _wheels(pg, [{"dx": 1, "dy": 3, "mode": 1, "gap": 200}])                       # lines: 16 px each
    b = _pos(pg)
    assert abs((b["x"] - a["x"]) - 16 / a["z"]) <= 2 and abs((b["y"] - a["y"]) - 48 / a["z"]) <= 2, (a, b)
    # a flick and its momentum: decaying events, some under a pixel, summed (fractions carried, not lost)
    _at(pg, 200, 200); a = _pos(pg)
    evs = [{"dx": 24 * .85 ** i, "dy": -18 * .85 ** i, "gap": 16 if i else 200} for i in range(40)]
    _wheels(pg, evs)
    b = _pos(pg)
    sx, sy = sum(e["dx"] for e in evs) / a["z"], sum(e["dy"] for e in evs) / a["z"]
    assert abs((b["x"] - a["x"]) - sx) <= 2 and abs((b["y"] - a["y"]) - sy) <= 2, (a, b, sx, sy)
    assert not _errs(pg), pg.errs
    pg.context.close()


@pytest.mark.parametrize("name", ["palace", "solar"])
def test_a_pinch_still_zooms_and_is_not_a_pan(browser, files, name):
    pg = _open(browser, files, name)
    a = _pos(pg)
    zoom = ("window._altoPalaceGeo.Z" if name == "palace" else "window._altoSolarZoom()")
    z0 = pg.evaluate(zoom)
    _wheels(pg, [{"dy": 12, "ctrl": True, "gap": 300}] + [{"dy": 12, "ctrl": True, "gap": 16}] * 5)
    pg.wait_for_timeout(500)
    assert _pos(pg)["n"] == a["n"], "ctrl+wheel (a pinch) is the zoom code's alone"
    assert pg.evaluate(zoom) < z0, "and it still zooms out"
    assert not _errs(pg), pg.errs
    pg.context.close()


@pytest.mark.parametrize("name", ["palace", "solar"])
def test_panels_detail_pages_an_enlarged_card_and_inner_scrollers_are_left_alone(browser, files, name):
    pg = _open(browser, files, name)
    a = _pos(pg)
    # outside the canvas (the bars, the detail page, the notes panel): never the map's
    outside = pg.evaluate("""()=>['detail-page','notes-panel','title-bar','nav'].map(function(id){ var e=document.getElementById(id);
      if(!e) return null; var c=document.getElementById('canvas'); if(c.contains(e)) return 'inside:'+id;
      var w=new WheelEvent('wheel',{deltaX:30,deltaY:30,bubbles:true,cancelable:true}); e.dispatchEvent(w); return w.defaultPrevented; })""")
    assert all(v in (None, False) for v in outside), outside
    assert _pos(pg)["n"] == a["n"]
    # a box inside the map that can scroll: a real (trusted) wheel over it scrolls it, not the map
    pg.evaluate("""()=>{var b=document.createElement('div'); b.id='t-inner';
      b.style.cssText='position:fixed;left:600px;top:500px;width:200px;height:200px;overflow:auto;z-index:99999;background:#fff';
      b.innerHTML='<div style="height:2000px;width:10px"></div>'; document.getElementById('canvas').appendChild(b);}""")
    pg.wait_for_timeout(100)
    pg.mouse.move(700, 600)
    pg.wait_for_timeout(250)
    a = _pos(pg)
    for _ in range(4):
        pg.mouse.wheel(0, 40)
        pg.wait_for_timeout(25)
    pg.wait_for_timeout(300)
    b = _pos(pg)
    assert b["n"] == a["n"] and abs(b["y"] - a["y"]) < 1 and abs(b["x"] - a["x"]) < 1, (a, b)
    assert pg.evaluate("document.getElementById('t-inner').scrollTop") > 0
    # Safari begins a gesture with an event of no delta: over the box that is still the box's gesture
    assert _wheels(pg, [{"gap": 300}, {"dy": 30}, {"dx": 20, "dy": 30}]) == 0
    assert _pos(pg)["n"] == a["n"]
    pg.evaluate("document.getElementById('t-inner').remove()")
    # an enlarged card: focus mode's navigation owns the wheel
    pg.evaluate("""()=>{ var n=document.querySelector('#world .node'); window.enterFocus(n.id.slice(5)); }""")
    pg.wait_for_timeout(900)
    a = _pos(pg)
    _wheels(pg, [{"dx": 30, "dy": 30, "gap": 300}] * 2)
    assert _pos(pg)["n"] == a["n"]
    assert not _errs(pg), pg.errs
    pg.context.close()


def test_the_whole_star_chart_keeps_its_own_two_axis_pan(browser, files):
    pg = _open(browser, files, "solar")
    pg.evaluate("window._altoSolarZoom(.4)")
    pg.wait_for_timeout(300)
    a = pg.evaluate("window._altoSolarCam.get()")
    n0 = _pos(pg)["n"]
    _wheels(pg, [{"dx": 40, "dy": 30, "gap": 300}] + [{"dx": 40, "dy": 30}] * 3)
    b = pg.evaluate("window._altoSolarCam.get()")
    assert _pos(pg)["n"] == n0, "the whole chart's board translate is its own"
    assert b["cx"] - a["cx"] > 50 and b["cy"] - a["cy"] > 40, (a, b)
    assert not _errs(pg), pg.errs
    pg.context.close()
