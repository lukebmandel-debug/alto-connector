"""Manual edit mode in a real browser (1.9.53): a card slid along its line
moves alone, off it its progeny come along; cards swap with a sibling or
their parent from the ⇅ menu or by typing a number; nothing ends up touching.
Skipped when Playwright or its browsers are not installed."""
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


def _touching(g, gap=8):
    ks = sorted(g)
    return [(a, b) for i, a in enumerate(ks) for b in ks[i + 1:]
            if g[a]["l"] < g[b]["l"] + g[b]["w"] + gap and g[b]["l"] < g[a]["l"] + g[a]["w"] + gap
            and g[a]["t"] < g[b]["t"] + g[b]["h"] + gap and g[b]["t"] < g[a]["t"] + g[a]["h"] + gap]


@pytest.fixture(scope="module")
def url(tmp_path_factory):
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    root = tmp_path_factory.mktemp("drag")
    (root / "page.html").write_text(build_timeline(*load_brief(d))[0], encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    h.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/page.html"
    srv.shutdown()


@pytest.fixture(params=["chromium", "webkit"])
def page(request, url):
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
        pg.click("#alto-edit-pill .aep-manual")
        pg.wait_for_timeout(400)
        yield pg
        b.close()


def _drag(pg, i, dx, dy):
    pg.evaluate(f"document.getElementById('node-{i}').scrollIntoView({{block:'center'}})")
    pg.wait_for_timeout(250)
    x, y = pg.evaluate(f"(()=>{{var r=document.querySelector('#node-{i} .node-card').getBoundingClientRect(); return [r.left+r.width/2, r.top+18];}})()")
    pg.mouse.move(x, y)
    pg.mouse.down()
    for k in range(1, 13):
        pg.mouse.move(x + dx * k / 12, y + dy * k / 12)
        pg.wait_for_timeout(16)
    pg.wait_for_timeout(120)
    tip = pg.evaluate("(document.getElementById('aed-rztip')||{}).textContent")
    pg.mouse.up()
    pg.mouse.move(5, 450)
    pg.wait_for_timeout(600)
    return tip


def _ops(pg):
    return pg.evaluate("JSON.parse(localStorage.getItem(Object.keys(localStorage).filter(k=>k.indexOf('alto-ed-')===0)[0])).ops")


def test_along_its_line_a_card_slides_alone_and_off_it_takes_its_progeny(page):
    g0 = page.evaluate(GEO)
    assert "stay" in _drag(page, "offer", 10, 160)
    g1 = page.evaluate(GEO)
    assert g1["offer"]["t"] > g0["offer"]["t"] + 100 and g1["offer"]["l"] == g0["offer"]["l"]
    for k in ("revocation", "option-contracts", "unilateral-offers"):
        assert g1[k]["l"] == g0[k]["l"] and g1[k]["t"] >= g0[k]["t"], k
    assert "p|offer|slide" in _ops(page) and _touching(g1) == []
    assert "Moving with" in _drag(page, "offer", 220, 30)
    g2 = page.evaluate(GEO)
    for k in ("offer", "revocation", "option-contracts", "unilateral-offers"):
        assert abs((g2[k]["l"] - g1[k]["l"]) - (g2["offer"]["l"] - g1["offer"]["l"])) <= 3, k
    assert "p|offer|shift" in _ops(page) and _touching(g2) == []


def _menu(pg, i):
    pg.evaluate(f"document.getElementById('node-{i}').scrollIntoView({{block:'center'}})")
    pg.wait_for_timeout(200)
    pg.hover(f"#node-{i} .node-title")
    pg.click(f'#node-{i} .aed-cc button[data-x="swapc"]')
    pg.wait_for_timeout(200)


def _pick(pg, start):
    pg.evaluate("s=>Array.from(document.querySelectorAll('#aed-ask button')).filter(b=>b.textContent.indexOf(s)===0)[0].click()", start)
    pg.wait_for_timeout(700)


def test_cards_swap_with_a_sibling_or_their_parent_and_by_number(page):
    num = lambda: page.evaluate("JSON.parse(JSON.stringify(NODE_ORDER_MAP))")
    n0 = num()
    _menu(page, "definiteness")
    _pick(page, "Swap with " + n0["preliminary-negotiations"])
    n1 = num()
    assert (n1["definiteness"], n1["preliminary-negotiations"]) == (n0["preliminary-negotiations"], n0["definiteness"])
    _menu(page, "revocation")
    _pick(page, "Trade places")
    assert page.evaluate("_ALTO_OUTLINE.parent['offer']") == "revocation"
    assert page.evaluate("_ALTO_OUTLINE.parent['revocation']") == "formation"
    assert page.evaluate("_ALTO_OUTLINE.kids['formation']")[2] == "revocation"      # in offer's turn
    assert num()["revocation"] == n0["offer"]
    # typed: the last of acceptance's cards takes the first's number; asked
    # first, it goes there and the others move along one
    kids = page.evaluate("_ALTO_OUTLINE.kids['acceptance']")
    n2 = num()
    page.click(f"#node-{kids[-1]} .node-order")
    page.fill("#aed-name input", n2[kids[0]])
    page.keyboard.press("Enter")
    page.wait_for_timeout(250)
    assert page.evaluate("document.querySelector('#aed-ask h4').textContent").startswith("Move ")
    _pick(page, "Yes, make it")
    assert page.evaluate("_ALTO_OUTLINE.kids['acceptance']") == [kids[-1]] + kids[:-1]
    assert num()[kids[-1]] == n2[kids[0]]
    ops = _ops(page)
    assert {"so|formation", "sx|revocation", "so|acceptance"} <= set(ops)
    assert _touching(page.evaluate(GEO)) == []
    # a reload lays the same page out again
    g = page.evaluate(GEO)
    page.reload()
    page.wait_for_timeout(1600)
    g2 = page.evaluate(GEO)
    assert all(abs(g[k]["t"] - g2[k]["t"]) <= 1 and abs(g[k]["l"] - g2[k]["l"]) <= 1 for k in g)
