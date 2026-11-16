"""The Memory Blueprint's trackpad and wheel (Luke, 2026-11-13: "also make memory blueprint two finger zoom in, and two finger scroll moves around").

A pinch (a ctrl-wheel in WebKit and Chromium, Safari's gesture events) and a ctrl/cmd mouse wheel zoom round the pointer: the point under it stays
put. A two-finger scroll or a plain wheel pans, both ways, and never zooms; the page itself never scrolls. A gesture and a ctrl-wheel are never both
applied. Over an enlarged card the wheel scrolls the card. Synthetic events, real browsers (WebKit first). Skipped without Playwright."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.test_blueprint_enlarge import CARD, DESKTOP, _open, browser, site  # noqa: E402,F401

STATE = r"""()=>{const s=document.querySelector('#bldg-root svg.bl-svg'), v=s.getAttribute('viewBox').split(' ').map(Number), r=s.getBoundingClientRect();
 return {vb:v, r:{l:r.left,t:r.top,w:r.width,h:r.height}, sy:scrollY, sx:scrollX, k:v[2]/r.width};}"""

# the plan point under (x, y), from a viewBox state (preserveAspectRatio meet: the root keeps the viewBox's aspect)
def _at(st, x, y):
    v, r = st["vb"], st["r"]
    return v[0] + (x - r["l"]) / r["w"] * v[2], v[1] + (y - r["t"]) / r["h"] * v[3]


WHEEL = """([x,y,dx,dy,ctrl,meta,n])=>{ const t=document.elementFromPoint(x,y);
  for(let i=0;i<n;i++) t.dispatchEvent(new WheelEvent('wheel',{deltaX:dx,deltaY:dy,clientX:x,clientY:y,ctrlKey:ctrl,metaKey:meta,bubbles:true,cancelable:true}));
  return t.closest('#bldg-root')?(t.className.baseVal!==undefined?'svg':t.className):'outside'; }"""


def _spot(pg):
    """A point on the plan away from every chip and bar."""
    return pg.evaluate("""()=>{ for(let y=260;y<640;y+=37) for(let x=420;x<1020;x+=41){ const e=document.elementFromPoint(x,y);
      if(e&&e.closest('svg.bl-svg')&&!e.closest('.bl-pill')) return [x,y]; } return [700,450]; }""")


def test_a_pinch_zooms_round_the_pointer(browser, site):
    ctx, pg, errors = _open(browser, site)
    try:
        x, y = _spot(pg)
        a = pg.evaluate(STATE)
        p0 = _at(a, x, y)
        pg.evaluate(WHEEL, [x, y, 0, -6, True, False, 10])                              # a trackpad pinch out: small ctrl-wheel steps
        pg.wait_for_timeout(200)
        b = pg.evaluate(STATE)
        assert b["k"] < a["k"] * .8, (a["k"], b["k"])                                  # zoomed in
        p1 = _at(b, x, y)
        assert abs(p1[0] - p0[0]) / b["k"] <= 2 and abs(p1[1] - p0[1]) / b["k"] <= 2, (p0, p1)   # the point under the pointer stayed put (2 px)
        pg.evaluate(WHEEL, [x, y, 0, 100, False, True, 2])                              # cmd + a mouse wheel zooms too
        pg.wait_for_timeout(200)
        c = pg.evaluate(STATE)
        assert c["k"] > b["k"] * 1.2
        p2 = _at(c, x, y)
        assert abs(p2[0] - p0[0]) / c["k"] <= 2 and abs(p2[1] - p0[1]) / c["k"] <= 2
        assert (a["sx"], a["sy"]) == (c["sx"], c["sy"]) == (0, 0)
        for _ in range(60):                                                             # held to the existing limits
            pg.evaluate(WHEEL, [x, y, 0, -40, True, False, 5])
        lo = pg.evaluate(STATE)
        assert lo["vb"][2] >= 4 - 1e-6
    finally:
        ctx.close()
    assert not errors, errors


def test_safari_gesture_events_zoom_once(browser, site):
    ctx, pg, errors = _open(browser, site)
    try:
        x, y = _spot(pg)
        a = pg.evaluate(STATE)
        pg.evaluate("""([x,y])=>{ const t=document.elementFromPoint(x,y), ev=(n,s)=>{ const e=new Event(n,{bubbles:true,cancelable:true}); e.scale=s; e.clientX=x; e.clientY=y; t.dispatchEvent(e); };
          ev('gesturestart',1); ev('gesturechange',1.5);
          t.dispatchEvent(new WheelEvent('wheel',{deltaY:-30,clientX:x,clientY:y,ctrlKey:true,bubbles:true,cancelable:true}));   // the same pinch as a ctrl-wheel: not applied again
          ev('gesturechange',2); ev('gestureend',2); }""", [x, y])
        pg.wait_for_timeout(200)
        b = pg.evaluate(STATE)
        assert abs(a["k"] / b["k"] - 2) < 0.02, (a["k"], b["k"])                        # exactly the gesture's 2x
        p0, p1 = _at(a, x, y), _at(b, x, y)
        assert abs(p1[0] - p0[0]) / b["k"] <= 2 and abs(p1[1] - p0[1]) / b["k"] <= 2
    finally:
        ctx.close()
    assert not errors, errors


def test_a_two_finger_scroll_pans_and_never_zooms(browser, site):
    ctx, pg, errors = _open(browser, site)
    try:
        x, y = _spot(pg)
        pg.evaluate(WHEEL, [x, y, 0, -6, True, False, 12])                              # in a little first, so a pan has room
        a = pg.evaluate(STATE)
        pg.evaluate(WHEEL, [x, y, 30, 0, False, False, 3])                              # sideways
        b = pg.evaluate(STATE)
        assert abs(b["k"] - a["k"]) < 1e-9 and b["vb"][2] == a["vb"][2]                # not a zoom
        assert abs((b["vb"][0] - a["vb"][0]) / a["k"] - 90) < 1.5 and abs(b["vb"][1] - a["vb"][1]) < 1e-6, (a["vb"], b["vb"])
        pg.evaluate(WHEEL, [x, y, 0, 25, False, False, 3])                              # down
        c = pg.evaluate(STATE)
        assert abs((c["vb"][1] - b["vb"][1]) / a["k"] - 75) < 1.5 and abs(c["vb"][0] - b["vb"][0]) < 1e-6
        assert c["vb"][2] == a["vb"][2] and (c["sx"], c["sy"]) == (0, 0)
        assert pg.evaluate("scrollY") == 0 and pg.evaluate("document.scrollingElement.scrollTop") == 0
    finally:
        ctx.close()
    assert not errors, errors


def test_a_wheel_over_an_enlarged_card_scrolls_the_card(browser, site):
    ctx, pg, errors = _open(browser, site, ctx_kw={"viewport": DESKTOP["d1280"]})
    try:
        pg.evaluate("AltoBuilding.enlarge('n1')")                                      # the long card: fitted, its text scrolls
        pg.wait_for_timeout(900)
        m = pg.evaluate(CARD)
        assert m["sf"], m
        a = pg.evaluate(STATE)
        cx, cy = (m["l"] + m["r"]) / 2, (m["t"] + m["b"]) / 2
        pg.mouse.move(cx, cy)
        pg.mouse.wheel(0, 300)
        pg.wait_for_timeout(500)
        assert pg.evaluate("document.querySelector('#bldg-root .bl-enl .node-card').scrollTop") > 0
        b = pg.evaluate(STATE)
        assert b["vb"] == a["vb"] and (b["sx"], b["sy"]) == (0, 0)                     # the plan did not move, nor the page
        pg.evaluate(WHEEL, [cx, cy, 0, -6, True, False, 5])                             # a pinch over the card zooms nothing (and not the browser)
        assert pg.evaluate(STATE)["vb"] == a["vb"]
        assert pg.evaluate("AltoBuilding.enlarged()") == "n1"
    finally:
        ctx.close()
    assert not errors, errors
