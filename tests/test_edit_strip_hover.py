"""Manual edit mode: a card's tool strip shows on hover only, and the way from the card to its strip must
never lose the hover (L-1102-193854). The pointer leaves the card at its top edge, beside the strip, and
crosses bare page before it reaches the strip: the strip has to stay, and stay clickable.
Skipped when Playwright or its browsers are not installed."""
import copy
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
TL = {"label": "Road to the Charter", "layout": "timeline", "nodes": [
    {"id": "john", "title": "John crowned", "when": "1199", "text": "Succeeds Richard.", "tag": "Crown"},
    {"id": "normandy", "title": "Normandy lost", "when": "1204", "text": "Philip II takes the duchy."},
    {"id": "bouvines", "title": "Bouvines", "when": "1214"},
    {"id": "runnymede", "title": "Runnymede", "when": "June 1215", "tone": "green"}]}


def _mini():
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    d["nodes"][0]["sections"].append({"h": "Timeline", "t": "Follow the years.", "tree": TL})
    return build_timeline(*load_brief(d))[0]


RECTS = """([host, strip]) => { var h = document.querySelector(host), s = h && h.querySelector(strip); if(!h) return null;
  var a = h.getBoundingClientRect(), q = s && s.getBoundingClientRect();
  return {host: [a.left, a.top, a.right, a.bottom], strip: q && [q.left, q.top, q.right, q.bottom]}; }"""
SHOWN = """([host, strip, tc]) => { var s = document.querySelector(host + ' ' + strip); if(!s) return false;
  var c = getComputedStyle(s); return tc ? +c.opacity > 0.5 : c.display !== 'none'; }"""

# format, brief, host selector, strip selector, strip fades (opacity) instead of display
CASES = [("timeline", "contracts", "#node-lucy-v-zehmer .node-card", ".aed-cc", False),
         ("outline", "outline", "#node-definiteness .node-card", ".aed-cc", False),
         ("lanes", "lanes", "#node-letter .node-card", ".aed-cc", False),
         ("mini-timeline", None, '.amt-ev[data-i="normandy"]', ".aed-tc", True),
         ("mini-timeline-linked", None, '.amt-ev[data-i="bouvines"]', ".aed-tc", True)]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    root = tmp_path_factory.mktemp("strip")
    for name in ("contracts", "outline", "lanes"):
        d = json.loads((ROOT / "samples" / f"{name}_brief.json").read_text(encoding="utf-8"))
        (root / f"{name}.html").write_text(build_timeline(*load_brief(copy.deepcopy(d)))[0], encoding="utf-8")
    (root / "mini.html").write_text(_mini(), encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    h.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:                       # no browser downloaded
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


def _open(browser, server, brief):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script(FAKE)
    pg = ctx.new_page()
    pg.goto(f"{server}/{'mini' if brief is None else brief}.html", wait_until="domcontentloaded")
    pg.wait_for_function("typeof showDetail === 'function'", timeout=30000)
    pg.wait_for_timeout(1500)
    if brief is None:
        pg.evaluate("showDetail('node','formation')")
        pg.wait_for_selector(".amt .amt-i", timeout=10000)
    pg.click("#alto-edit-pill .aep-manual")
    pg.wait_for_selector("html.alto-editing", timeout=10000)
    pg.wait_for_timeout(600)
    return pg


def _walk(pg, pts, host, strip, tc):
    for x, y in pts:
        pg.mouse.move(x, y, steps=1)
        assert pg.evaluate(SHOWN, [host, strip, tc]), f"the strip hid at {round(x)},{round(y)}"


@pytest.mark.parametrize("fmt,brief,host,strip,tc", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("dwell", [0, 800], ids=["quick", "slow"])
def test_the_strip_stays_on_the_way_from_its_card(browser, server, fmt, brief, host, strip, tc, dwell):
    pg = _open(browser, server, brief)
    try:
        pg.evaluate("s => document.querySelector(s).scrollIntoView({block: 'center'})", host)
        pg.wait_for_timeout(250)
        pg.mouse.move(5, 5)
        r = pg.evaluate(RECTS, [host, strip])
        a = r["host"]
        pg.mouse.move((a[0] + a[2]) / 2, a[1] + 14)                       # on the card: the strip comes up
        pg.wait_for_timeout(350)
        r = pg.evaluate(RECTS, [host, strip])
        s = r["strip"]
        assert s and pg.evaluate(SHOWN, [host, strip, tc]), "the strip did not appear on hover"
        cy = (s[1] + s[3]) / 2
        # a spot just outside the strip, on bare page beside it (not the card), that the strip's bridge covers
        spot = pg.evaluate("""([strip, host, s, a]) => { var h = document.querySelector(host), st = h.querySelector(strip);
          for (var dx of [-8, -4]) for (var y of [a[1] - 4, s[1] + 6, s[1] - 6, s[3] - 2]) {
            var x = s[0] + dx, e = document.elementFromPoint(x, y);
            if (e && st.contains(e)) return [x, y]; }
          return null; }""", [strip, host, s, a])
        assert spot, "no bare page beside the strip is covered by its bridge"
        sx, gap_y = spot
        # out of the card's top edge beside the strip (bare page, not the card, not the strip), then in
        _walk(pg, [(sx - 40, a[1] + 6), (sx - 40, gap_y)], host, strip, tc)
        _walk(pg, [(sx, gap_y)], host, strip, tc)
        if dwell:                                   # lingering beside the strip, long after the grace is over
            pg.wait_for_timeout(dwell)
            assert pg.evaluate(SHOWN, [host, strip, tc]), "the strip hid while the pointer was between card and strip"
        _walk(pg, [(sx + 12, cy)], host, strip, tc)
        pg.wait_for_timeout(400)
        assert pg.evaluate(SHOWN, [host, strip, tc])
        # and it is clickable: the pointer's target at the strip's centre is one of its buttons
        btn = pg.locator(f"{host} {strip} button").first
        btn.click(trial=True, timeout=3000)
        # leaving for good hides it again: strips are not permanent
        pg.mouse.move(5, 5)
        pg.wait_for_timeout(900)
        assert not pg.evaluate(SHOWN, [host, strip, tc]), "the strip stayed after the pointer left for good"
    finally:
        pg.context.close()
