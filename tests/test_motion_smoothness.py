"""Desktop motion that read as '10% glitchy' (1.9.3).

  * scrolling restyled the whole page every frame: the era tint of the top
    bars was a custom property written on <html>;
  * cards (and lines) sliding under a still pointer during a scroll or an
    arrow hop's glide took the hover and pulsed past it;
  * Safari floors a written scrollTop twice under the page's CSS zoom, so each
    hop began with the canvas stepping 1px backwards, then glided unevenly.
"""
import json
import pytest
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import load_brief, build_timeline  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"


def _html():
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    html, _ = build_timeline(*load_brief(d))
    return html


def _script(html, sid):
    return html.split(f'<script id="{sid}">', 1)[1].split("</script>", 1)[0]


def test_scroll_tint_is_written_on_the_bars_not_the_root():
    js = _script(_html(), "glass-header-tint")
    assert "root.style.setProperty('--header-tint'" not in js
    assert "['title-bar','nav','node-nav-bar']" in js
    # unchanged colour → no write
    assert "el.style.getPropertyValue('--header-tint')===v" in js


def test_hover_ignores_content_moving_under_a_still_pointer():
    html = _html()
    js = _script(html, "d-grid-quantize")
    assert "window._altoPointerStill=function(e)" in js
    over = js.split("document.addEventListener('mouseover'", 1)[1].split("});", 1)[0]
    assert "_altoPointerStill(e)) return;" in over
    # the line dwell asks the same question
    assert "window._altoPointerStill(e)" in html.split("var DWELL=300", 1)[1].split("document.addEventListener('mouseout'", 1)[0]


def test_fly_writes_scroll_through_the_whole_px_axis():
    js = _script(_html(), "alto-focus-mode")
    fly = js.split("function flyTo(el){", 1)[1].split("function flyBack", 1)[0]
    assert "qx.go(" in fly and "qy.go(" in fly
    assert not re.search(r"canvas\.scroll(Top|Left)\s*=", fly)
    assert "function _scrollAxis(prop)" in js


def test_the_enlarged_card_moves_by_margins_never_a_transform():
    html = _html()
    js = _script(html, "alto-focus-mode")
    fly = js.split("function flyTo(el){", 1)[1].split("function flyBack", 1)[0]
    back = js.split("function flyBack(el){", 1)[1].split("\n  }", 1)[0]
    rel = js.split("function _release(p){", 1)[1].split("\n  }", 1)[0]
    for body in (fly, back, rel):
        assert "style.transform" not in body and "_place(" in body
    assert "window._altoSettle" not in html and "window._altoUnsettle" not in html
    assert "calc(var(--mx,0px) + var(--fx,0px))" in html
    # the line cutter treats an offset card as on the move
    assert "!n.style.getPropertyValue('--fx')" in html


def test_ramps_start_with_the_css_fades():
    """The held first frame is gone: with minimum-jerk it saved nothing, and it
    put the card behind the CSS fades that start at once (two beats)."""
    js = _script(_html(), "alto-focus-mode")
    assert "warm=true" not in js


def test_safari_wheel_listener_is_passive_unless_needed():
    js = _script(_html(), "alto-focus-mode")
    assert "window.addEventListener('wheel', function(e){" not in js
    assert "window.addEventListener('wheel', _onWheel, {passive:!hold, capture:true});" in js
    assert "var hold=!_wk || !!window._focusedNodeId" in js
    assert js.count("_wheelSync();") >= 3               # load, enter, exit


def test_an_enlarged_card_is_centred_even_if_it_was_hovered():
    """A pinch enlarges the card under the pointer, which was mid hover-grow:
    its hover rest height kept it ~50px low and its shadow showed above it."""
    q = _script(_html(), "d-grid-quantize")
    assert "var hov=n._hov!=null && !n.classList.contains('focused');" in q
    js = _script(_html(), "alto-focus-mode")
    assert "el._hov=null;" in js.split("function enterFocus(id){", 1)[1].split("\n  }", 1)[0]


def test_enlarging_and_hopping_move_as_one_body():
    """The glide, the new card's growth and the old card's return share one
    curve and one clock, so nothing arrives before the view does."""
    js = _script(_html(), "alto-focus-mode")
    assert "function _altoEase(p){" in js and "var FOCUS_MS=400, UNFOCUS_MS=320;" in js
    assert "return p*p*p*(10+p*(-15+6*p));" in js                   # minimum-jerk
    assert "FOCUS_MS=window._altoFlyMs=_flyMs(" in js               # duration follows distance
    assert "function ez(p){ return _altoEase(p); }" in js          # glide + glide back
    assert "e=_altoEase(p);" in js                                  # zoom ramp
    assert "e=_altoEase(t);" in js and "(ts-s0)/FOCUS_MS" in js     # release
    enter = js[js.index("function enterFocus(id){", js.index("function _shadowSync")):]
    enter = enter[:enter.index("\n  }")]
    assert enter.index("flyTo(el);") < enter.index("_zoomRamp(el,FOCUS_K,FOCUS_MS);") < enter.index("if(p) _release(p);")
    assert "_animate(FOCUS_MS," in js and "_zoomRamp(el,1,UNFOCUS_MS);" in js and "_animate(UNFOCUS_MS," in js
    assert "(window._altoFlyMs||400)+40" in js                      # held arrows wait for the glide
    assert "1-(1-p)*(1-p)" not in js and "1-(1-t)*(1-t)" not in js


def test_the_shared_curve_is_minimum_jerk():
    """Zero speed and zero acceleration at both ends, peak speed at the middle,
    and a short tail: the profile of natural human movement."""
    import subprocess, shutil
    node = shutil.which("node") or str(Path.home() / ".local/node/bin/node")
    if not Path(node).is_file():
        pytest.skip("needs node")
    js = _script(_html(), "alto-focus-mode")
    fn = js[js.index("function _altoEase(p){"):]
    fn = fn[:fn.index("\n  }\n") + 4]
    fly = js[js.index("function _flyMs(dist)"):].split("\n", 1)[0]
    prog = fn + fly + """
      var N=1000, y=[], v=[], a=[];
      for(var i=0;i<=N;i++) y.push(_altoEase(i/N));
      for(i=0;i<N;i++) v.push((y[i+1]-y[i])*N);
      for(i=0;i<N-1;i++) a.push((v[i+1]-v[i])*N);
      var vmax=Math.max.apply(null,v), at=v.indexOf(vmax)/N;
      var t95=y.findIndex(function(q){ return q>=0.95; })/N;
      console.log(JSON.stringify({v0:v[0], v1:v[N-1], a0:Math.abs(a[0]), vmax:vmax, at:at,
        amax:Math.max.apply(null,a.map(Math.abs)), tail:1-t95,
        ms:[_flyMs(0), _flyMs(300), _flyMs(3000)]}));"""
    r = __import__("json").loads(subprocess.run([node, "-e", prog], capture_output=True,
                                               text=True, check=True).stdout)
    assert r["v0"] < 0.01 and r["v1"] < 0.01 and r["a0"] < 0.1
    assert 0.45 < r["at"] < 0.55 and r["vmax"] < 1.9
    assert r["amax"] < 6 and r["tail"] < 0.2
    assert r["ms"] == [400, 410, 580]


def test_the_board_moves_as_one_piece():
    """Luke (1.9.16): the card felt dragged by two separate drags — it slid
    across the board on its own while the board scrolled under it. Now what
    scrolling cannot cover is a pan of the whole board (a camera); the card
    only grows where it sits, and the full-bleed glass holds still sideways
    so the pan never shows bare page."""
    html = _html()
    js = _script(html, "alto-focus-mode")
    fly = js.split("function flyTo(el){", 1)[1].split("function flyBack", 1)[0]
    assert "_setPan(px0+(px-px0)*k, py0+(py-py0)*k);" in fly
    assert "_place(el, fx0+(-rx-fx0)*k" not in fly            # no solo slide any more
    back = js.split("function flyBack(el){", 1)[1].split("\n  }", 1)[0]
    assert "_setPan(px0*(1-k), py0*(1-k));" in back and "_setPan(0,0);" in back
    assert "html:not(.mobile) #world{ translate:var(--pan-x,0px) var(--pan-y,0px); }" in html
    assert "#world #glass-slab{ translate:calc(-1 * var(--pan-x,0px)) 0; }" in html
    # on the device-pixel grid, so a transform stays as crisp as layout
    assert "return Math.round(v*z)/z;" in js and "x=_devPx(x); y=_devPx(y);" in js


def test_the_fades_ride_the_growths_clock():
    """Luke (1.9.17): "the Netflix boom boom" — the scene dimmed on CSS's own
    .25-.3s ease (half done by ~85ms) and THEN the card grew (half at ~270ms).
    Every fade now takes the glide's duration and a minimum-jerk curve, is
    timed before the classes change, and the ramps count from the change."""
    html = _html()
    js = _script(html, "alto-focus-mode")
    assert "html:not(.mobile) #canvas{ --alto-fly:250ms; --alto-ease:cubic-bezier(.5,0,.5,1); }" in html
    assert "transition: opacity var(--alto-fly) var(--alto-ease), box-shadow .28s" in html
    assert "#canvas #river-svg{ transition: opacity var(--alto-fly) var(--alto-ease) !important; }" in html
    assert "transition:opacity var(--alto-fly,.25s) var(--alto-ease), border-color .2s !important" in html
    enter = js[js.index("function enterFocus(id){", js.index("function _flyPlanMs")):]
    enter = enter[:enter.index("\n  }")]
    assert enter.index("_fadeClock(FOCUS_MS=window._altoFlyMs=_flyPlanMs(el));") < enter.index("el.classList.add('focused');")
    ex = js[js.index("function exitFocus(){"):]
    assert ex.index("_fadeClock(UNFOCUS_MS);") < ex.index("canvas.classList.remove('focus-mode');")
    assert "card.style.transition='opacity '+ms+'ms cubic-bezier(.5,0,.5,1), border-color .2s';" in js
    assert js.count("=performance.now(), warm=false;") == 3
