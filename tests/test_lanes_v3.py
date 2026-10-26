"""The horizontal timeline, round 3 (Luke, 2026-10-26): "Should be able to select multiple lines at once to only
show. Also its too reactive to hovering right now. Can't seem to zoom out or in."

* several lines picked at once (the key's rows, a line's label) show only them, their events and the main-line
  events where they are on the page; the board is laid out again to fit; the pick is remembered per timeline on the
  device; the steps skip what is hidden; Esc / "Show all" / the rail's ✕ bring every line back;
* a calm hover: a pointer crossing the board lights nothing, one resting on a line lights it after its delay;
* zoom: ctrl/⌘ + the wheel, Safari's gesture events, a phone's two fingers and + / − / 0 scale the board round the
  pointer, and back at the fitted size (or 0 / Esc) it is the fitted view again.
Checked in Chromium and WebKit."""
import functools
import http.server
import socketserver
import threading

import pytest

from alto.build import phone, retro
from alto.build.builder import build_timeline, load_brief

from test_lanes_fit import IPHONE, _doc

try:
    import playwright.sync_api as pw
except ImportError:          # pragma: no cover
    pw = None


@pytest.fixture(params=["chromium", "webkit"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            try:
                if request.param != "chromium":
                    raise e
                b = p.chromium.launch(channel="chrome")
            except Exception:
                pytest.skip(f"no {request.param}: {e}")
        b._alto_engine = request.param
        yield b
        b.close()


@pytest.fixture
def site(tmp_path):
    name, body = phone.phone_asset()
    (tmp_path / "phone").mkdir()
    (tmp_path / "phone" / name).write_text(body, encoding="utf-8")
    name, body = retro.retro_asset()
    (tmp_path / "retro").mkdir()
    (tmp_path / "retro" / name).write_text(body, encoding="utf-8")
    (tmp_path / "fit.html").write_text(build_timeline(*load_brief(_doc()))[0], encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    h.log_message = lambda *a: None
    srv = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/fit.html"
    srv.shutdown()
    srv.server_close()


def _open(browser, url, **kw):
    ctx = browser.new_context(**(kw or dict(viewport={"width": 1440, "height": 900})))
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url)
    pg.wait_for_timeout(2600)
    return ctx, pg, errs


STATE = r"""() => {
  var shown=[].filter.call(document.querySelectorAll('#world .node[id^="node-"]'), function(n){ return getComputedStyle(n).display!=='none'; })
    .map(function(n){ return n.id.slice(5); });
  var lines=[].map.call(document.querySelectorAll('#lanes-svg g[data-ln] path.ln-br'), function(p){ return p.parentNode.getAttribute('data-ln'); });
  var c=document.getElementById('canvas'), r=c.getBoundingClientRect(), bad=[];
  document.querySelectorAll('#world .node[id^="node-"] .node-card').forEach(function(e){ var b=e.getBoundingClientRect();
    if(b.height && (b.top<r.top-1 || b.bottom>r.bottom+1)) bad.push(e.parentNode.id); });
  return {shown:shown, lines:Array.from(new Set(lines)), pick:window._altoLanesPick(), tag:(document.querySelector('#lanes-nav .lnv-tag')||{}).textContent||'',
          scroll:[c.scrollHeight, c.clientHeight], bad:bad, W:window._altoLanesGeo.W}; }"""


def _expected(ids):
    """What a pick of these lines leaves on the board: their own events, and the main-line events with any of them on the page."""
    d = _doc()
    of = {"l-ada": "ada", "l-ben": "ben", "cy": "cy", "dora": "dora", "eli": "eli", "fay": "fay", "gus": "gus", "hal": "hal"}
    out = set()
    for n in d["nodes"]:
        if n.get("line"):
            if n["line"] in ids:
                out.add(n["id"])
        elif any(of[i] in n["entity_ids"] for i in ids):
            out.add(n["id"])
    return out


def test_several_lines_picked_show_only_them_and_are_remembered(browser, site):
    ctx, pg, errs = _open(browser, site)
    all0 = pg.evaluate(STATE)
    assert len(all0["shown"]) == 33 and len(all0["lines"]) == 8
    pg.click("#key-toggle")
    pg.click('#lanes-key .lk-row[data-k="l-ada"]')
    pg.click('#lanes-key .lk-row[data-k="cy"]')
    pg.wait_for_timeout(900)
    s = pg.evaluate(STATE)
    assert s["pick"] == ["l-ada", "cy"]
    assert set(s["shown"]) == _expected(["l-ada", "cy"]), sorted(set(s["shown"]) ^ _expected(["l-ada", "cy"]))
    assert sorted(s["lines"]) == ["cy", "l-ada"]
    assert "Ada + Cy only" in s["tag"]
    assert pg.evaluate("document.querySelector('#lanes-key .lk-pickbar span').textContent") == "Showing 2 of 8 lines"
    assert pg.evaluate("document.querySelectorAll('#lanes-key .lk-row.lk-pick').length") == 2
    assert s["bad"] == [] and s["scroll"][0] <= s["scroll"][1] + 1          # laid out again, still inside the window
    assert s["W"] < all0["W"]                                               # and narrower: the hidden events left the board
    # the steps visit only what is shown
    pg.click("#key-toggle")
    pg.evaluate("document.activeElement && document.activeElement.blur()")
    pg.keyboard.press("Home")
    pg.wait_for_timeout(1300)
    seen = []
    for _ in range(5):
        pg.keyboard.press("ArrowRight")
        pg.wait_for_timeout(1250)
        seen.append(pg.evaluate("(document.querySelector('.node.ln-cur')||{}).id||''")[5:])
    assert seen and all(i in _expected(["l-ada", "cy"]) for i in seen), seen
    # remembered on this device, for this timeline
    pg.reload()
    pg.wait_for_timeout(2600)
    assert pg.evaluate(STATE)["pick"] == ["l-ada", "cy"]
    # a row again takes its line off; Show all brings every line back
    pg.click("#key-toggle")
    pg.click('#lanes-key .lk-row[data-k="cy"]')
    pg.wait_for_timeout(700)
    assert pg.evaluate(STATE)["pick"] == ["l-ada"]
    pg.click("#lanes-key .lk-all")
    pg.wait_for_timeout(700)
    s = pg.evaluate(STATE)
    assert s["pick"] == [] and len(s["shown"]) == 33 and "only" not in s["tag"]
    # a label on the board: only that line; again: all of them; Esc too
    pg.click("#key-toggle")
    pg.click('.lanes-tag[data-ln-tag="gus"]')
    pg.wait_for_timeout(700)
    assert pg.evaluate(STATE)["pick"] == ["gus"]
    pg.click('.lanes-tag[data-ln-tag="gus"]')
    pg.wait_for_timeout(700)
    assert pg.evaluate(STATE)["pick"] == []
    pg.click('.lanes-tag[data-ln-tag="gus"]')
    pg.wait_for_timeout(700)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(700)
    assert pg.evaluate(STATE)["pick"] == []
    assert pg.evaluate("localStorage.getItem('alto-lanes-pick-fit')") is None
    # the nav bar's character chips: ⇧-click picks lines (a plain click is still the character's page)
    pg.click("#nav .nav-btn:has-text('Eli')", modifiers=["Shift"])
    pg.click("#nav .nav-btn:has-text('Fay Lin')", modifiers=["Shift"])
    pg.wait_for_timeout(700)
    assert pg.evaluate(STATE)["pick"] == ["eli", "fay"]
    assert pg.evaluate("document.querySelectorAll('#nav .nav-btn.ln-chip-on').length") == 2
    assert not pg.evaluate("document.documentElement.classList.contains('detail-open')")
    pg.click("#nav .nav-btn:has-text('Eli')", modifiers=["Shift"])
    pg.wait_for_timeout(700)
    assert pg.evaluate(STATE)["pick"] == ["fay"]
    ctx.close()
    assert not errs, errs


def test_picked_lines_in_retro_and_on_a_phone(browser, site):
    """The pick works the same in Retro and on a phone held sideways (its whole view)."""
    ctx, pg, errs = _open(browser, site + "?view=whole", viewport={"width": 844, "height": 390}, user_agent=IPHONE, has_touch=True)
    assert pg.evaluate("document.documentElement.classList.contains('phone-whole')")
    pg.evaluate("window._altoLanesPick(['l-ben','eli'])")
    pg.wait_for_timeout(900)
    s = pg.evaluate(STATE)
    assert set(s["shown"]) == _expected(["l-ben", "eli"]) and sorted(s["lines"]) == ["eli", "l-ben"]
    assert s["bad"] == [], s["bad"]
    ctx.close()
    ctx, pg, errs2 = _open(browser, site)
    pg.evaluate("window._altoStyle.set('retro')")
    pg.wait_for_timeout(600)
    assert pg.evaluate("document.documentElement.classList.contains('alto-retro')")
    pg.click("#key-toggle")
    pg.click('#lanes-key .lk-row[data-k="hal"]')
    pg.wait_for_timeout(800)
    s = pg.evaluate(STATE)
    assert s["pick"] == ["hal"] and set(s["shown"]) == _expected(["hal"])
    ctx.close()
    assert not errs and not errs2, errs + errs2


DIM = r"""() => { window._dl=[]; var c=document.getElementById('canvas');
  new MutationObserver(function(){ window._dl.push(c.classList.contains('ln-dimline')); }).observe(c, {attributes:true, attributeFilter:['class']}); }"""


def test_the_hover_is_calm(browser, site):
    ctx, pg, errs = _open(browser, site)
    pg.evaluate(DIM)
    pg.mouse.move(60, 450)
    for x in range(60, 1400, 22):                       # a pointer crossing the board: cards, lines, labels, gaps
        pg.mouse.move(x, 250 + (x * 7) % 420)
        pg.wait_for_timeout(16)
    pg.wait_for_timeout(60)
    assert pg.evaluate("window._dl") == []
    # resting on a line's label lights it, not at once
    c = pg.evaluate("""() => { var r=document.querySelector('.lanes-tag[data-ln-tag="l-ada"]').getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]; }""")
    pg.mouse.move(*c)
    pg.wait_for_timeout(100)
    assert not pg.evaluate("document.getElementById('canvas').classList.contains('ln-dimline')")
    pg.wait_for_timeout(300)
    assert pg.evaluate("document.querySelector('.lanes-tag[data-ln-tag=\"l-ada\"]').classList.contains('ln-on')")
    # straight on to another line's label: a swap, never a moment with nothing lit
    pg.evaluate(DIM)
    c2 = pg.evaluate("""() => { var r=document.querySelector('.lanes-tag[data-ln-tag="cy"]').getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]; }""")
    pg.mouse.move(*c2, steps=4)
    pg.wait_for_timeout(500)
    assert False not in pg.evaluate("window._dl")
    assert pg.evaluate("document.querySelector('.lanes-tag[data-ln-tag=\"cy\"]').classList.contains('ln-on')")
    # off the board: it stays a moment (its grace), then goes
    pg.mouse.move(720, 20)
    pg.wait_for_timeout(150)
    assert pg.evaluate("document.getElementById('canvas').classList.contains('ln-dimline')")
    pg.wait_for_timeout(450)
    assert not pg.evaluate("document.getElementById('canvas').classList.contains('ln-dimline')")
    ctx.close()
    assert not errs, errs


Z = r"""() => { var w=document.getElementById('world'), c=document.getElementById('canvas');
  return {s:window._altoLanesZoom.s(), ov:c.classList.contains('ln-ov'), tf:w.style.transform, f:window._focusedNodeId||null}; }"""
UNDER = r"""p => { var c=document.getElementById('canvas'), r=c.getBoundingClientRect(), v=window._altoLanesZoom.view(); if(!v) return null;
  var k=r.width/c.offsetWidth; return [((p[0]-r.left)/k-v.tx)/v.s, ((p[1]-r.top)/k-v.ty)/v.s]; }"""


def test_zoom_with_the_wheel_the_keys_and_a_pinch(browser, site):
    ctx, pg, errs = _open(browser, site)
    assert pg.evaluate(Z)["s"] == 1
    for _ in range(12):                                   # into the middle of the story, clear of the board's ends
        pg.keyboard.press("ArrowRight")
        pg.wait_for_timeout(150)
    pg.wait_for_timeout(1400)
    # ctrl + the wheel (Chrome's trackpad pinch): out, round the pointer
    pg.mouse.move(800, 480)
    pg.keyboard.down("Control")
    for _ in range(4):
        pg.mouse.wheel(0, 8)
        pg.wait_for_timeout(20)
    w0 = pg.evaluate(UNDER, [800, 480])
    for _ in range(4):
        pg.mouse.wheel(0, 8)
        pg.wait_for_timeout(20)
    pg.keyboard.up("Control")
    z = pg.evaluate(Z)
    assert z["ov"] and 0.4 < z["s"] < 0.95 and not z["f"], z
    w1 = pg.evaluate(UNDER, [800, 480])
    assert abs(w0[0] - w1[0]) < 3 and abs(w0[1] - w1[1]) < 30, (w0, w1)         # the point under the pointer stays there (up and down, the board is kept inside the window)
    # and in, past the fitted size: the board itself grows (no card is enlarged)
    pg.keyboard.down("Control")
    for _ in range(14):
        pg.mouse.wheel(0, -8)
        pg.wait_for_timeout(20)
    pg.keyboard.up("Control")
    pg.wait_for_timeout(500)
    z = pg.evaluate(Z)
    assert z["s"] > 1.2 and not z["f"], z
    # 0 is the fitted view again
    pg.keyboard.press("0")
    pg.wait_for_timeout(1200)
    z = pg.evaluate(Z)
    assert z["s"] == 1 and not z["ov"] and z["tf"] == "", z
    # the keys: − twice, + twice is the fitted view (it snaps back to it)
    for k in ["-", "-"]:
        pg.keyboard.press(k)
        pg.wait_for_timeout(750)
    assert abs(pg.evaluate(Z)["s"] - 0.64) < 0.01
    for k in ["+", "+"]:
        pg.keyboard.press(k)
        pg.wait_for_timeout(750)
    pg.wait_for_timeout(900)
    z = pg.evaluate(Z)
    assert z["s"] == 1 and not z["ov"], z
    pg.keyboard.press("Meta+Minus")
    pg.wait_for_timeout(800)
    assert pg.evaluate(Z)["s"] < 1
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(1200)
    assert pg.evaluate(Z)["s"] == 1
    # Safari's trackpad pinch: gesture events, the board scaled with the fingers, settling back near 1 to the fitted view
    G = r"""a => { var x=a[0], y=a[1]; function g(t, s){ var e=new Event(t, {bubbles:true, cancelable:true}); [['scale',s],['clientX',x],['clientY',y]].forEach(function(p){ Object.defineProperty(e, p[0], {value:p[1]}); });
      document.elementFromPoint(x, y).dispatchEvent(e); }
      g('gesturestart', 1); a[2].forEach(function(s){ g('gesturechange', s); }); if(a[3]) g('gestureend', a[2][a[2].length-1]); }"""
    pg.evaluate(G, [700, 450, [0.9, 0.75, 0.6], True])
    pg.wait_for_timeout(300)
    assert abs(pg.evaluate(Z)["s"] - 0.6) < 0.01
    pg.evaluate(G, [700, 450, [1.2, 1.6, 1.66], True])                           # 0.6 x 1.66 = 1.0: back to the fitted view
    pg.wait_for_timeout(1200)
    z = pg.evaluate(Z)
    assert z["s"] == 1 and not z["ov"], z
    # a card enlarged: a pinch out is still the engine's (it lets the card go)
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(1200)
    if pg.evaluate("!!window._focusedNodeId"):
        pg.keyboard.down("Control")
        for _ in range(4):
            pg.mouse.wheel(0, 20)
            pg.wait_for_timeout(20)
        pg.keyboard.up("Control")
        pg.wait_for_timeout(900)
        z = pg.evaluate(Z)
        assert not z["f"] and z["s"] == 1, z
    ctx.close()
    assert not errs, errs


def test_a_phone_pinches_the_board(browser, site):
    """A phone held sideways (the whole view): two fingers become the trackpad's gesture events (phone.py) and the board scales."""
    ctx, pg, errs = _open(browser, site + "?view=whole", viewport={"width": 844, "height": 390}, user_agent=IPHONE, has_touch=True)
    assert pg.evaluate("document.documentElement.classList.contains('phone-whole')")
    can = pg.evaluate("typeof Touch==='function' && (function(){ try{ new Touch({identifier:1, target:document.body, clientX:0, clientY:0}); return true; }catch(e){ return false; } })()")
    if not can:
        ctx.close()
        pytest.skip("no Touch constructor in this engine")
    PINCH = r"""a => { var c=document.getElementById('canvas'), t=document.elementFromPoint(420, 200);
      function T(id, x){ return new Touch({identifier:id, target:t, clientX:x, clientY:200}); }
      function ev(type, d){ var ts=d==null ? [] : [T(1, 420-d), T(2, 420+d)];
        t.dispatchEvent(new TouchEvent(type, {bubbles:true, cancelable:true, touches:ts, targetTouches:ts, changedTouches:ts.length?ts:[T(1,300),T(2,540)]})); }
      ev('touchstart', a[0]); a.slice(1).forEach(function(d){ ev('touchmove', d); }); ev('touchend', null); }"""
    pg.evaluate(PINCH, [120, 100, 80, 60])
    pg.wait_for_timeout(400)
    s = pg.evaluate(Z)["s"]
    assert 0.4 < s < 0.6, s
    ctx.close()
    assert not errs, errs
