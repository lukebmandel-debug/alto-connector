"""The floor bar keeps its divider between the last floor button and the zoom group (- fit +), in Classic, Retro and Holo (Board B-1121-LOOK-ALLFLOORS-R5)."""
import pytest
from tests.test_blueprint_enlarge import site, browser, _open, STYLES, needs_all  # noqa: F401

JS = """()=>{ const d=document.querySelector('#bldg-root .bl-dock'), tabs=[...d.querySelectorAll('.bl-tab')], z=d.querySelector('.bl-zoom'),
  seps=[...d.querySelectorAll('.bl-sep')].map(s=>{const r=s.getBoundingClientRect(),cs=getComputedStyle(s);return {x:r.left,w:r.width,h:r.height,disp:cs.display,bw:cs.borderLeftWidth,bs:cs.borderLeftStyle,vis:cs.visibility,op:cs.opacity};});
  const lt=tabs[tabs.length-1].getBoundingClientRect(), zr=z.getBoundingClientRect(); return {lastRight:lt.right, zoomLeft:zr.left, seps}; }"""


@needs_all
@pytest.mark.parametrize("style", STYLES)
def test_a_divider_sits_between_the_last_floor_and_the_zoom_group(browser, site, style):
    ctx, pg, errors = _open(browser, site, style, {"viewport": {"width": 1440, "height": 900}})
    pg.wait_for_timeout(1200)
    m = pg.evaluate(JS)
    ctx.close()
    ok = [s for s in m["seps"] if s["disp"] != "none" and s["h"] >= 10 and s["vis"] != "hidden" and m["lastRight"] <= s["x"] + 0.5 and s["x"] + s["w"] <= m["zoomLeft"] + 0.5]
    assert ok, (style, m)
    assert ok[0]["bs"] == "solid" and float(ok[0]["bw"][:-2]) > 0, (style, m)   # drawn as a border, which WebKit never rounds away (a bare 1px box can)
