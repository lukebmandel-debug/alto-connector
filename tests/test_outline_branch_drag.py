"""Outline branch drag (Luke L-1104-112908): dragging a card moves the whole branch, in any direction, straight
down its line included; Option held, the card slides alone. Arrow keys nudge the picked card (10 px, Shift 40),
Option+arrows the whole branch, in edit mode only and never while typing; a burst of presses is one undo step.
Make-room never lifts a dragged card's own progeny. Skipped when Playwright or its browsers are not installed."""
import functools
import http.server
import json
import socketserver
import threading
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")

from alto.build.builder import build_timeline, load_brief  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FAKE = """(function(){ var store=null;
 var C={enabled:true, known:true, user:{uid:'u1'}, getEdits:function(){ return Promise.resolve(store); },
  putEdits:function(t,d){ store=JSON.parse(JSON.stringify(d)); return Promise.resolve(); }, watchEdits:function(){ return function(){}; }};
 Object.defineProperty(window,'AltoCloud',{get:function(){return C;}, set:function(){}, configurable:true}); })();"""
GEO = """() => { var out={}; document.querySelectorAll('#world .node').forEach(function(el){
  var c=el.querySelector('.node-card'); if(!c||!el.offsetWidth) return;
  out[el.id.slice(5)]={l:el.offsetLeft+c.offsetLeft, t:el.offsetTop+c.offsetTop, w:c.offsetWidth, h:c.offsetHeight}; }); return out; }"""
KIDS = ("revocation", "option-contracts", "unilateral-offers")


def _touching(g, gap=8):
    ks = sorted(g)
    return [(a, b) for i, a in enumerate(ks) for b in ks[i + 1:]
            if g[a]["l"] < g[b]["l"] + g[b]["w"] + gap and g[b]["l"] < g[a]["l"] + g[a]["w"] + gap
            and g[a]["t"] < g[b]["t"] + g[b]["h"] + gap and g[b]["t"] < g[a]["t"] + g[a]["h"] + gap]


@pytest.fixture(scope="module")
def url(tmp_path_factory):
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    root = tmp_path_factory.mktemp("branchdrag")
    (root / "page.html").write_text(build_timeline(*load_brief(d))[0], encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    h.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/page.html"
    srv.shutdown()


@pytest.fixture(params=["chromium", "webkit"])
def fresh(request, url):
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:                       # no browser downloaded
            pytest.skip(f"no {request.param}: {e}")
        ctx = b.new_context(viewport={"width": 1400, "height": 900})
        ctx.add_init_script(FAKE)
        pg = ctx.new_page()
        pg.goto(url)
        pg.wait_for_timeout(1500)
        yield pg
        b.close()


@pytest.fixture
def page(fresh):
    fresh.click("#alto-edit-pill .aep-manual")
    fresh.wait_for_timeout(400)
    return fresh


def _ops(pg):
    return pg.evaluate("(()=>{var k=Object.keys(localStorage).filter(k=>k.indexOf('alto-ed-')===0)[0]; return k ? JSON.parse(localStorage.getItem(k)).ops : {};})()")


def _val(pg, key):
    o = _ops(pg).get(key)
    return o["v"] if o else None


def _card_xy(pg, i, bare=False):
    pg.evaluate(f"document.getElementById('node-{i}').scrollIntoView({{block:'center'}})")
    pg.wait_for_timeout(250)
    return pg.evaluate(f"(()=>{{var r=document.querySelector('#node-{i} .node-card').getBoundingClientRect(); return {'[r.left+3, r.top+r.height/2]' if bare else '[r.left+r.width/2, r.top+18]'};}})()")


def _drag(pg, i, dx, dy, alt=False):
    x, y = _card_xy(pg, i)
    pg.mouse.move(x, y)
    if alt:
        pg.keyboard.down("Alt")
    pg.mouse.down()
    for k in range(1, 13):
        pg.mouse.move(x + dx * k / 12, y + dy * k / 12)
        pg.wait_for_timeout(16)
    pg.wait_for_timeout(120)
    tip = pg.evaluate("(document.getElementById('aed-rztip')||{}).textContent")
    pg.mouse.up()
    if alt:
        pg.keyboard.up("Alt")
    pg.mouse.move(5, 450)
    pg.wait_for_timeout(600)
    return tip


def _select(pg, i):
    """Press on the card's bare edge: it is picked, and no text field starts."""
    x, y = _card_xy(pg, i, bare=True)
    pg.mouse.click(x, y)
    pg.mouse.move(5, 450)
    pg.wait_for_timeout(250)


def _dy(g1, g0, k):
    return g1[k]["t"] - g0[k]["t"]


def test_a_default_drag_carries_the_descendants_straight_down_too(page):
    g0 = page.evaluate(GEO)
    assert "hold Option" in _drag(page, "offer", 0, 170)
    g1 = page.evaluate(GEO)
    assert _dy(g1, g0, "offer") > 120
    for k in KIDS:
        assert abs(_dy(g1, g0, k) - _dy(g1, g0, "offer")) <= 3 and g1[k]["l"] == g0[k]["l"], k
    ops = _ops(page)
    assert "p|offer|shift" in ops and "p|offer|slide" not in ops and _touching(g1) == []


def test_an_option_drag_moves_the_card_alone_and_make_room_keeps_the_progeny_down(page):
    g0 = page.evaluate(GEO)
    assert "alone" in _drag(page, "offer", 0, 170, alt=True)
    g1 = page.evaluate(GEO)
    assert _dy(g1, g0, "offer") > 120
    for k in KIDS:                      # never lifted past the card they hang from
        assert g1[k]["l"] == g0[k]["l"] and g1[k]["t"] >= g0[k]["t"], k
    ops = _ops(page)
    assert "p|offer|slide" in ops and "p|offer|shift" not in ops and _touching(g1) == []


def test_make_room_does_not_lift_a_dragged_cards_own_progeny():
    from alto.build.layout import make_room
    x = {"m": 850.0, "c": 850.0}
    h = {"m": 100.0, "c": 100.0}
    w = {"m": 270, "c": 270}
    y = {"m": 300.0, "c": 200.0}                 # m slid down onto its child c, which sat above m's centre
    make_room(y, x, h, w, ["m", "c"], {"m"}, {"c": "m"}, 40, 0)
    assert y["c"] == pytest.approx(300 + 50 + 40 + 50)           # down below it, not up
    y = {"m": 300.0, "c": 200.0}
    make_room(y, x, h, w, ["m", "c"], {"m"}, {}, 40, 0)          # an unrelated card is still lifted
    assert y["c"] < 200


def test_make_room_js_matches_the_progeny_rule():
    src = (ROOT / "alto" / "build" / "detail_extras.py").read_text(encoding="utf-8")
    assert "grp.some(under)" in src and "if(moved[c]) return true" in src


def test_arrows_nudge_the_card_alone_shift_is_bigger_option_takes_the_branch(page):
    g0 = page.evaluate(GEO)
    _select(page, "offer")
    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(700)
    g1 = page.evaluate(GEO)
    assert _val(page, "p|offer|slide") == [0, 10]
    assert 8 <= _dy(g1, g0, "offer") <= 12 and all(_dy(g1, g0, k) >= 0 and _dy(g1, g0, k) <= 12 for k in KIDS)
    page.keyboard.press("Shift+ArrowDown")
    page.wait_for_timeout(700)
    assert _val(page, "p|offer|slide") == [0, 50]
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(700)
    assert _val(page, "p|offer|slide") == [10, 50]
    g2 = page.evaluate(GEO)
    page.keyboard.press("Alt+ArrowDown")
    page.wait_for_timeout(700)
    assert _val(page, "p|offer|shift") == [0, 10]
    g3 = page.evaluate(GEO)
    for k in ("offer",) + KIDS:         # the whole branch moved together
        assert 8 <= _dy(g3, g2, k) <= 12, k
    page.keyboard.press("Alt+Shift+ArrowUp")
    page.wait_for_timeout(700)
    assert _val(page, "p|offer|shift") == [0, -30]
    assert _touching(page.evaluate(GEO)) == []


def test_arrows_do_nothing_with_no_card_picked_outside_edit_mode_or_while_typing(fresh):
    fresh.keyboard.press("ArrowDown")                                   # not editing
    assert not [k for k in _ops(fresh) if k.startswith("p|")]
    fresh.click("#alto-edit-pill .aep-manual")
    fresh.wait_for_timeout(400)
    fresh.keyboard.press("ArrowDown")                                   # editing, nothing picked
    fresh.keyboard.press("Alt+ArrowDown")
    fresh.wait_for_timeout(500)
    assert not [k for k in _ops(fresh) if k.startswith("p|")]
    x, y = _card_xy(fresh, "offer")                                    # a click on the title starts its field
    fresh.mouse.click(x, y)
    fresh.wait_for_timeout(300)
    assert fresh.evaluate("!!document.activeElement && document.activeElement.isContentEditable")
    fresh.keyboard.press("ArrowDown")
    fresh.keyboard.press("Alt+ArrowDown")
    fresh.wait_for_timeout(500)
    assert not [k for k in _ops(fresh) if k.startswith("p|")]
    fresh.keyboard.press("Escape")                                      # the field cancelled, the card still picked
    fresh.wait_for_timeout(300)
    _select(fresh, "offer")
    fresh.keyboard.press("ArrowDown")
    fresh.wait_for_timeout(500)
    assert _val(fresh, "p|offer|slide") == [0, 10]
    fresh.click("#alto-edit-exit .ee-done")                            # out of edit mode: the keys are the page's again
    fresh.wait_for_timeout(500)
    before = _ops(fresh)
    fresh.keyboard.press("ArrowDown")
    fresh.wait_for_timeout(500)
    assert _ops(fresh) == before


def test_a_burst_of_presses_is_one_step_of_undo(page):
    g0 = page.evaluate(GEO)
    _select(page, "offer")
    for _ in range(3):
        page.keyboard.press("ArrowDown")
    page.wait_for_timeout(700)
    assert _val(page, "p|offer|slide") == [0, 30]
    page.wait_for_timeout(800)                                         # a pause: the next press is its own step
    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(700)
    assert _val(page, "p|offer|slide") == [0, 40]
    page.keyboard.press("Control+z")
    page.wait_for_timeout(500)
    assert _val(page, "p|offer|slide") == [0, 30]                      # the lone press went; the burst is still whole
    page.keyboard.press("Control+z")
    page.wait_for_timeout(700)
    g1 = page.evaluate(GEO)
    assert not _val(page, "p|offer|slide")
    assert abs(_dy(g1, g0, "offer")) <= 1
    page.keyboard.press("Control+Shift+z")
    page.wait_for_timeout(500)
    assert _val(page, "p|offer|slide") == [0, 30]
