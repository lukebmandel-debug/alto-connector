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


def test_ramps_start_their_clock_after_the_state_frame():
    js = _script(_html(), "alto-focus-mode")
    assert js.count("if(warm){ warm=false;") == 3     # fly/flyBack, zoom ramp, release glide


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
    """Luke: smoother, not slower, not faster. The glide, the new card's growth
    and the old card's return share one curve and one duration, so nothing
    arrives before the view does and nothing starts with a kick."""
    js = _script(_html(), "alto-focus-mode")
    assert "function _altoEase(p){" in js and "var FOCUS_MS=460, UNFOCUS_MS=330;" in js
    assert "function ez(p){ return _altoEase(p); }" in js          # glide + glide back
    assert "e=_altoEase(p);" in js                                  # zoom ramp
    assert "e=_altoEase(t);" in js and "(ts-s0)/FOCUS_MS" in js     # release
    assert "_zoomRamp(el,FOCUS_K,FOCUS_MS);" in js and "_animate(FOCUS_MS," in js
    assert "_zoomRamp(el,1,UNFOCUS_MS);" in js and "_animate(UNFOCUS_MS," in js
    assert "1-(1-p)*(1-p)" not in js and "1-(1-t)*(1-t)" not in js


def test_the_shared_curve_starts_from_rest_and_lands_on_time():
    import subprocess, shutil
    node = shutil.which("node") or str(Path.home() / ".local/node/bin/node")
    if not Path(node).is_file():
        pytest.skip("needs node")
    js = _script(_html(), "alto-focus-mode")
    fn = js[js.index("function _altoEase(p){"):]
    fn = fn[:fn.index("\n  }\n") + 4]
    out = subprocess.run([node, "-e", fn + "console.log(JSON.stringify([0,.01,100/460,.5,1].map(_altoEase)))"],
                         capture_output=True, text=True, check=True).stdout
    v = __import__("json").loads(out)
    assert v[0] == 0 and v[-1] == 1
    assert v[1] < 0.01                       # from rest: no jump on the first frame
    assert 0.45 < v[2] < 0.65                # ~half way at 100ms of 460
    assert 0.8 < v[3] < 0.9                  # ~85% by the middle, gentler than (.2,0,0,1)
