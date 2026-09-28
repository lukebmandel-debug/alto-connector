"""Desktop motion that read as '10% glitchy' (1.9.3).

  * scrolling restyled the whole page every frame: the era tint of the top
    bars was a custom property written on <html>;
  * cards (and lines) sliding under a still pointer during a scroll or an
    arrow hop's glide took the hover and pulsed past it;
  * Safari floors a written scrollTop twice under the page's CSS zoom, so each
    hop began with the canvas stepping 1px backwards, then glided unevenly.
"""
import json
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
