"""1.9.95 diagonal navigation ("cannot navigate diagonally"): arrows hop between buildings on the 8 compass ways (two arrows
together are the diagonal), a diagonal asks for a building that is really on that diagonal, and the arrow keys pan the city map
(they did nothing at all) in any direction. Street routing already used the diagonal streets: checked, locked below.

The browser tests run the real shipped JS in a stub page and are skipped without Playwright's browsers."""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import engine_patches, palace, palace_pan  # noqa: E402

try:
    import playwright.sync_api as pw
except Exception:  # pragma: no cover
    pw = None

NEW = next(p["new"] for p in engine_patches.PATCHES if p["name"] == "arrows-follow-the-layout")
HOP = NEW[NEW.index("  var _hopBusy=0, _hopQ=[];"):]                  # the hop queue and the two-key diagonal
NAV = palace.PALACE_JS[palace.PALACE_JS.index("window._altoPalaceNav=function"):]
NAV = NAV[:NAV.index("\n};\n") + 4]


# ── source ───────────────────────────────────────────────────────────

def test_two_arrows_together_hop_the_diagonal():
    assert "var _HOP_PAIR_MS=" in HOP and "_arrDn" in HOP
    assert "_hopNow(vert ? dir+pr : pr+dir, repeat)" in HOP               # n+e = 'ne', e+s = 'se' …
    assert "_pendT=setTimeout(_flushPend, _HOP_PAIR_MS)" in HOP           # a lone press waits a few ms for a partner
    assert 60 <= int(re.search(r"_HOP_PAIR_MS=(\d+)", HOP).group(1)) <= 120
    assert "window.addEventListener('keyup'" in HOP and "window.addEventListener('blur'" in HOP   # held keys are forgotten
    assert "(window._altoFlyMs||420)+40" in HOP                           # still one hop per glide
    keydown = next(p for p in engine_patches.PATCHES if p["name"] == "arrows-one-hop-at-a-time")
    assert "_hop(d, e.repeat)" in keydown["new"]


def test_palace_nav_takes_the_nearest_building_on_the_diagonal():
    assert ".7071" in NAV and "across<=along*.7" in NAV and "return near||best;" in NAV


def test_the_arrow_keys_pan_the_map_and_are_spliced_into_the_palace():
    assert "+ PAN_JS + " in Path(palace.__file__).read_text()
    js = palace_pan.PAN_JS
    assert "tx/=m; ty/=m;" in js                                         # two held arrows: the diagonal, not faster
    assert "window.addEventListener('keyup'" in js and "typing(e.target)" in js
    assert "PV.tx+dx" in js and "pvSet(" in js                            # while a zoom preview is up, the preview moves
    assert palace_pan.PAN_JS in palace.PALACE_JS


def test_street_routing_keeps_the_diagonal_streets():
    """Every street piece joins the routing graph at each crossing, whatever its angle (checked on the real city: 11% of
    the walking routes' length runs on non-axis streets, no building's entrance sits in a cut-off fragment)."""
    js = palace.PALACE_JS
    g = js[js.index("function graph(){"):js.index("function nearest(")]
    assert "atan2" not in g and "Math.abs(dx)" not in g                   # nothing in the graph favours an axis
    assert "var d=(A[3]-A[1])*(C[4]-C[2])-(A[4]-A[2])*(C[3]-C[1])" in g   # a general segment-segment crossing


# ── the real JS, run ─────────────────────────────────────────────────

@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
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


def _page(browser, html):
    pg = browser.new_context(viewport={"width": 900, "height": 700}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.set_content(html)
    pg.errs = errs
    return pg


HOP_PAGE = """<!doctype html><body><script>
var calls=[], t0=performance.now(); window._altoFlyMs=30;
function focusNeighbor(d){ calls.push([d, Math.round(performance.now()-t0)]); }
%s
window.addEventListener('keydown', function(e){
  var d=e.key==='ArrowLeft'?'w':e.key==='ArrowRight'?'e':e.key==='ArrowUp'?'n':e.key==='ArrowDown'?'s':null;
  if(!d) return; e.preventDefault(); _hop(d, e.repeat); }, true);
</script></body>"""


def _names(pg):
    return [c[0] for c in pg.evaluate("calls")]


def test_two_arrows_together_are_a_diagonal_and_one_arrow_is_not(browser):
    pg = _page(browser, HOP_PAGE % HOP)
    kb = pg.keyboard

    def run(keys, gap=25, hold=60):
        pg.evaluate("calls.length=0; t0=performance.now()")
        for k in keys:
            kb.down(k); pg.wait_for_timeout(gap)
        pg.wait_for_timeout(hold)
        for k in keys:
            kb.up(k)
        pg.wait_for_timeout(400)
        return _names(pg)

    assert run(["ArrowUp", "ArrowRight"]) == ["ne"]
    assert run(["ArrowRight", "ArrowUp"]) == ["ne"]                       # either key first
    assert run(["ArrowUp", "ArrowLeft"]) == ["nw"]
    assert run(["ArrowDown", "ArrowRight"]) == ["se"]
    assert run(["ArrowDown", "ArrowLeft"]) == ["sw"]
    assert run(["ArrowLeft", "ArrowRight"]) == ["w", "e"]                 # opposite arrows are not a diagonal
    assert run(["ArrowUp"]) == ["n"] and run(["ArrowLeft"]) == ["w"]
    # hold Up (a hop), then press Right while it is down: the diagonal from there, at once
    pg.evaluate("calls.length=0")
    kb.down("ArrowUp"); pg.wait_for_timeout(150); kb.down("ArrowRight"); pg.wait_for_timeout(300)
    kb.up("ArrowRight"); kb.up("ArrowUp"); pg.wait_for_timeout(300)
    assert _names(pg)[:2] == ["n", "ne"]
    # two taps one after the other (the first released) stay two hops
    pg.evaluate("calls.length=0")
    kb.press("ArrowUp"); pg.wait_for_timeout(150); kb.press("ArrowRight"); pg.wait_for_timeout(400)
    assert _names(pg) == ["n", "e"]
    assert pg.errs == []


def test_a_single_press_still_lands_at_once(browser):
    pg = _page(browser, HOP_PAGE % HOP)
    pg.evaluate("calls.length=0")
    t = pg.evaluate("""new Promise(function(r){ var t=performance.now();
      window.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true}));
      window.dispatchEvent(new KeyboardEvent('keyup',{key:'ArrowDown',bubbles:true}));
      (function f(){ if(calls.length) r(performance.now()-t); else requestAnimationFrame(f); })(); })""")
    assert t < 130, t


PAN_PAGE = """<!doctype html><body style="margin:0"><div id="canvas" style="width:800px;height:600px;overflow:auto">
<div style="width:6000px;height:6000px"></div></div><script>
var PV=null, Z=1, de=document.documentElement;
function palaceOn(){ return true; } function focused(){ return false; } function pvSet(){}
%s
</script></body>"""


def test_the_arrow_keys_pan_the_map_diagonally(browser):
    pg = _page(browser, PAN_PAGE % palace_pan.PAN_JS)
    pos = lambda: pg.evaluate("[canvas.scrollLeft, canvas.scrollTop]")  # noqa: E731

    def hold(keys, ms=500):
        a = pos()
        for k in keys:
            pg.keyboard.down(k)
        pg.wait_for_timeout(ms)
        for k in keys:
            pg.keyboard.up(k)
        pg.wait_for_timeout(500)
        b = pos()
        return b[0] - a[0], b[1] - a[1]

    dx, dy = hold(["ArrowRight"])
    assert dx > 150 and abs(dy) < 3
    dx, dy = hold(["ArrowDown"])
    assert dy > 150 and abs(dx) < 3
    dx, dy = hold(["ArrowDown", "ArrowRight"])
    assert dx > 100 and dy > 100 and 0.6 < dx / dy < 1.6                  # the diagonal
    dx2, dy2 = hold(["ArrowUp", "ArrowLeft"])
    assert dx2 < -100 and dy2 < -100 and 0.6 < dx2 / dy2 < 1.6
    sp = (dx * dx + dy * dy) ** .5
    one, _ = hold(["ArrowRight"])
    assert sp < one * 1.5                                                 # two keys are not faster than one
    assert pg.evaluate("Object.keys(window._altoPalacePanKeys).length") == 0   # released keys are forgotten
    assert pg.errs == []


NAV_PAGE = """<!doctype html><body><script>
var P={at:{o:'0.0',n:'1.0',e:'2.0',ne:'3.0',far:'4.0'}, units:[['o','n','e','ne','far']],
  b:[[[0,0]],[[0,-100]],[[100,0]],[[80,-90]],[[-3000,0]]]};
function mob(){ return false; } function lot(k){ var p=String(k).split('.'); return P.b[+p[0]][+p[1]]; } function bOf(i){ return i; }
%s
</script></body>"""


def test_palace_nav_picks_a_building_on_the_diagonal(browser):
    pg = _page(browser, NAV_PAGE % NAV)
    nav = lambda d, o="o": pg.evaluate(f"window._altoPalaceNav('{o}','{d}')")  # noqa: E731
    assert nav("n") == "n" and nav("e") == "e"
    assert nav("ne") == "ne"                                              # the one on the diagonal, though n and e are nearer
    assert nav("sw") in ("n", "e", "ne", "far")                           # nothing on that diagonal: the best of what lies that way
    assert pg.errs == []
