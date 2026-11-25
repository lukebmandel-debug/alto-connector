"""Edit mode on a page whose units scroll sideways on their own (row-subtrees round 5): a card dragged in a PANNED unit
lands where it is held (the scroll offset is accounted for), and the Extend switch turns the board's own sideways
scroll on and off with the per-unit scroll coming back."""
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

FAKE = """(function(){ var store=null;
 var C={enabled:true, known:true, user:{uid:'u1'}, getEdits:function(){ return Promise.resolve(store); },
  putEdits:function(t,d){ store=JSON.parse(JSON.stringify(d)); return Promise.resolve(); }, watchEdits:function(){ return function(){}; }};
 Object.defineProperty(window,'AltoCloud',{get:function(){return C;}, set:function(){}, configurable:true}); })();"""
BOX = "(i) => { var c = document.querySelector('#node-' + i + ' .node-card'), r = c.getBoundingClientRect(); return [r.left, r.top, r.width / c.offsetWidth]; }"
LEFT = "(i) => parseFloat(document.getElementById('node-' + i).style.left)"
UNITS = "() => (window._altoUnits || []).map(u => ({min: u.min, max: u.max, ox: u.ox}))"
XWIDE = "() => document.documentElement.classList.contains('alto-xwide')"


@pytest.fixture
def page():
    s = pm.serve({"neg": tf.page(data=tf.negligence_brief(190, ("breach", "defenses")))}, {}, {})
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception as e:
            s.shutdown()
            pytest.skip(f"no WebKit: {e}")
        ctx = b.new_context(viewport={"width": 1440, "height": 2200}, color_scheme="dark")
        ctx.add_init_script(FAKE)
        pg = ctx.new_page()
        pg.goto(f"http://127.0.0.1:{s.server_address[1]}/neg.html?style=classic", wait_until="load")
        pg.wait_for_timeout(3500)
        pg.click("#alto-edit-pill .aep-manual")
        pg.wait_for_timeout(900)
        yield pg
        b.close()
    s.shutdown()


def _pan_right(pg):
    pg.mouse.move(700, 700)
    pg.mouse.wheel(9000, 0)
    pg.wait_for_timeout(500)


def test_a_card_dragged_in_a_panned_unit_lands_where_it_is_held(page):
    pg = page
    _pan_right(pg)
    u = pg.evaluate(UNITS)
    assert u[0]["ox"] == u[0]["max"] > 1000                    # unit one is panned to its far end
    card = "defenses-assumption-of-risk-barred"
    x, y, k = pg.evaluate(BOX, card)
    assert 0 < x < 1440 and k < 1
    l0 = pg.evaluate(LEFT, card)
    pg.mouse.move(x + 3, y + 56)
    pg.wait_for_timeout(400)
    pg.mouse.down()
    for s in range(1, 9):
        pg.mouse.move(x + 3 + 100 * s / 8, y + 56 - 570 * s / 8)
        pg.wait_for_timeout(120)
    pg.wait_for_timeout(700)
    held = pg.evaluate(BOX, card)
    pg.mouse.up()
    pg.wait_for_timeout(1000)
    after = pg.evaluate(BOX, card)
    assert abs(after[0] - held[0]) <= 2 and abs(after[1] - held[1]) <= 2, (held, after)      # where it is held is where it lands
    assert abs((after[0] - x) - 100) <= 8                                                    # it moved by what the pointer moved (the held card is drawn a little larger)
    assert abs((pg.evaluate(LEFT, card) - l0) * k - 100) <= 3                                # and the layout agrees, scroll offset accounted for
    assert pg.evaluate(UNITS)[0]["ox"] == u[0]["ox"]                                         # the unit is still panned where it was


def test_the_owners_extend_switch_folds_the_units_back_and_saves_the_page_setting(page):
    # (replaces the old Extend test: the board-wide side room is gone, Luke 2026-11-24/25; the editing bar's switch
    # is now the page's own setting, saved as the edit `pg|extend` and folded into brief.extend)
    pg = page
    assert not pg.evaluate(XWIDE) and len(pg.evaluate(UNITS)) == 2
    assert pg.evaluate("() => getComputedStyle(document.querySelector('#alto-edit-exit .ee-ext')).display") != "none"
    assert pg.evaluate("() => document.querySelector('#alto-edit-exit .ee-ext').classList.contains('on')")
    assert pg.evaluate("() => getComputedStyle(document.getElementById('ext-view-btn')).display") == "none"   # (no reader switch while editing)
    pg.click("#alto-edit-exit .ee-ext")
    pg.wait_for_timeout(1200)
    assert pg.evaluate(UNITS) == [] and not pg.evaluate(XWIDE)                                 # Extend off: each unit fits the page
    assert pg.evaluate("() => document.documentElement.classList.contains('alto-ext-off')")
    assert pg.evaluate("() => document.getElementById('canvas').scrollWidth - document.getElementById('canvas').clientWidth") <= 2
    pg.click("#alto-edit-exit .ee-ext")
    pg.wait_for_timeout(1400)
    u = pg.evaluate(UNITS)
    assert len(u) == 2 and u[0]["max"] > u[0]["min"], u                                       # on again: each unit scrolls on its own
    assert pg.evaluate("() => document.getElementById('canvas').scrollLeft") == 0
