"""A card dragged past the page's edge in edit mode stays out there, Extend on or off (Luke 2026-11-25, Torts:
"I could not drag a node beyond the canvass with extend mode on or off").

Off: the board opens that way (_altoSides, alto-xwide) and the dropped card is scrolled into view.
On: the held card's unit row scrolls while it is held at the window's edge (no limit), the row reaches the
dropped card and shows it. Either way the drop is saved and survives a reload."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import torts_fixture as tf  # noqa: E402

try:
    from playwright import sync_api as pw
    import phone_matrix as pm
    pm._playwright()
except Exception:                                   # CI has no Playwright
    pw = None

pytestmark = pytest.mark.skipif(pw is None, reason="no Playwright")

# the edits store kept in localStorage, so a reload reads back what the drop saved
FAKE = """(function(){ var K='alto-test-edits';
 var C={enabled:true, known:true, user:{uid:'u1'},
  getEdits:function(){ var v=localStorage.getItem(K); return Promise.resolve(v?JSON.parse(v):null); },
  putEdits:function(t,d){ localStorage.setItem(K, JSON.stringify(d)); return Promise.resolve(); }, watchEdits:function(){ return function(){}; }};
 Object.defineProperty(window,'AltoCloud',{get:function(){return C;}, set:function(){}, configurable:true}); })();"""
LEFT = "(i) => parseFloat(document.getElementById('node-' + i).style.left)"
RIGHTMOST = """() => { let best = null, bx = -1; document.querySelectorAll('#world .node').forEach(n => { const c = n.querySelector('.node-card'); if (!c) return;
  const r = c.getBoundingClientRect(); if (r.top > 150 && r.bottom < 820 && r.right < 1400 && r.left > 0 && r.right > bx) { bx = r.right; best = n.id.slice(5); } }); return best; }"""
SEEN = """(i) => { const r = document.querySelector('#node-' + i + ' .node-card').getBoundingClientRect();
  return {l: r.left, r: r.right, xwide: document.documentElement.classList.contains('alto-xwide'), units: (window._altoUnits || []).length}; }"""


def _drag_past_right_edge(pg, card):
    r = pg.evaluate("(i) => { const r = document.querySelector('#node-' + i + ' .node-card').getBoundingClientRect(); return [r.left + r.width / 2, r.top + 30]; }", card)
    pg.mouse.move(*r)
    pg.wait_for_timeout(300)
    pg.mouse.down()
    pg.keyboard.down("Shift")                       # (a free move: the row scrolling under the pointer never makes it a drop onto another card)
    for s in range(1, 13):
        pg.mouse.move(r[0] + (1430 - r[0]) * s / 12, r[1])
        pg.wait_for_timeout(80)
    pg.wait_for_timeout(2500)                       # held at the window's edge: the board (off) or the unit row (on) goes that way
    pg.mouse.up()
    pg.keyboard.up("Shift")
    pg.wait_for_timeout(1800)


@pytest.mark.parametrize("extend", [False, True], ids=["extend-off", "extend-on"])
def test_a_card_dragged_past_the_edge_stays_out_there_and_survives_a_reload(extend):
    s = pm.serve({"neg": tf.page(data=tf.negligence_brief(extend=extend))}, {}, {})
    try:
        with pw.sync_playwright() as p:
            try:
                b = p.webkit.launch()
            except Exception as e:
                pytest.skip(f"no WebKit: {e}")
            ctx = b.new_context(viewport={"width": 1440, "height": 900})
            ctx.add_init_script(FAKE)
            pg = ctx.new_page()
            url = f"http://127.0.0.1:{s.server_address[1]}/neg.html"
            pg.goto(url, wait_until="load")
            pg.wait_for_timeout(3500)
            pg.click("#alto-edit-pill .aep-manual")
            pg.wait_for_timeout(900)
            card = pg.evaluate(RIGHTMOST)
            l0 = pg.evaluate(LEFT, card)
            _drag_past_right_edge(pg, card)
            l1 = pg.evaluate(LEFT, card)
            assert l1 - l0 > 500, (card, l0, l1)                                  # well past where the window's edge was
            seen = pg.evaluate(SEEN, card)
            assert 0 <= seen["l"] and seen["r"] <= 1420, seen                     # and shown after the drop, not left under the rail
            if extend:
                assert seen["units"] and not seen["xwide"], seen                 # its unit row reaches it; the board stays the window's width
            else:
                assert seen["xwide"], seen                                       # the board opened that way
                assert l1 + 145 > 1700                                           # past the page's own 1,700 px
            pg.reload(wait_until="load")
            pg.wait_for_timeout(3500)
            assert abs(pg.evaluate(LEFT, card) - l1) <= 2                         # the drop was saved
            b.close()
    finally:
        s.shutdown()
