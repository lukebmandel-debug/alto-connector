"""The Compact | Expanded glyph (lanes.py, #ln-view), item 8 of Luke's 2026-11-05 picks: one glyph, bottom right, only on a board
that has something nested; a vanishing toggle (invisible until the pointer is over its corner or the board, fades in, fades out
again after the pointer leaves, always reachable by keyboard); Alto's one-time offer when entries are tucked inside others, after
which the glyph stays. No settings switch; a phone is unchanged. Browser tests only (WebKit and Chromium; skipped without Playwright)."""
import pytest

from alto.build.lanes import LANES_CSS, LANES_JS
from tests.test_lanes_children import _d, _open, browser  # noqa: F401  (the fixture)

OPACITY = "()=>parseFloat(getComputedStyle(document.getElementById('ln-view')).opacity)"
KEEP = "try{ localStorage.setItem('alto-compact-offer','1'); }catch(e){}"          # the offer already made: the glyph on its own


def _quiet(browser, tmp_path, **kw):
    """the board with the offer already made (a page that opened before): only the vanishing toggle is under test"""
    pg, errs = _open(browser, _d(), tmp_path, settle=300, **kw)
    pg.context.add_init_script(KEEP)
    pg.reload()
    pg.wait_for_timeout(3600)
    return pg, errs


def _away(pg):
    """a point off the board: over the title or the rail, which sit above the canvas (the canvas fills the window)"""
    return pg.evaluate("""()=>{ for(let y=2; y<innerHeight; y+=4) for(let x=40; x<innerWidth-40; x+=80){ const e=document.elementFromPoint(x,y);
        if(e && !e.closest('#canvas') && e.id!=='ln-view' && !e.closest('#ln-offer')) return [x,y]; } return null; }""")


def test_the_static_page_carries_no_switch_and_the_toggle_is_css():
    assert "#ln-view{opacity:0;" in LANES_CSS and "#ln-view.ln-show,#ln-view:hover,#ln-view:focus-visible{opacity:1;}" in LANES_CSS
    assert "prefers-reduced-motion:reduce){#ln-view,#ln-offer{transition:none;}" in LANES_CSS
    assert "alto-compact-offer" in LANES_JS and "settings" not in LANES_JS.split("function offerSoon", 1)[1].split("function closeOffer", 1)[0].lower()


def test_the_glyph_is_invisible_at_rest_fades_in_on_the_board_and_out_after_leaving(browser, tmp_path):
    pg, errs = _quiet(browser, tmp_path)
    assert pg.evaluate("!!document.getElementById('ln-view')") and pg.evaluate(OPACITY) == 0
    cx, cy = pg.evaluate("()=>{ const c=document.getElementById('canvas').getBoundingClientRect(); return [c.left+c.width/2, c.top+c.height/3]; }")
    pg.mouse.move(cx, cy)
    pg.mouse.move(cx + 6, cy + 4)
    pg.wait_for_timeout(500)
    assert pg.evaluate(OPACITY) == 1                                             # the pointer is on the board: it fades in
    x, y = _away(pg)
    pg.mouse.move(x, y)
    pg.wait_for_timeout(500)
    assert pg.evaluate(OPACITY) > 0                                              # not at once: it lingers a moment
    pg.wait_for_timeout(1300)
    assert pg.evaluate(OPACITY) == 0                                             # then it fades out again
    box = pg.evaluate("()=>{ const r=document.getElementById('ln-view').getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]; }")
    pg.mouse.move(*box)                                                          # its own corner brings it back
    pg.wait_for_timeout(500)
    assert pg.evaluate(OPACITY) == 1
    pg.mouse.click(*box)                                                         # and it works as it is: Expanded
    pg.wait_for_timeout(500)
    assert pg.evaluate("document.getElementById('ln-view').getAttribute('aria-pressed')") == "true"
    assert not errs, errs


def test_the_keyboard_reaches_it_and_sees_it(browser, tmp_path):
    pg, errs = _quiet(browser, tmp_path)
    x, y = _away(pg)
    pg.mouse.move(x, y)
    pg.wait_for_timeout(1600)
    assert pg.evaluate(OPACITY) == 0
    for _ in range(120):
        pg.keyboard.press("Tab")
        if pg.evaluate("document.activeElement && document.activeElement.id") == "ln-view":
            break
    assert pg.evaluate("document.activeElement.id") == "ln-view", "Tab never reached the glyph"
    pg.wait_for_timeout(500)
    assert pg.evaluate(OPACITY) == 1                                             # focus-visible shows it, the pointer far away
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(500)
    assert pg.evaluate("document.getElementById('ln-view').getAttribute('aria-pressed')") == "true"
    assert not errs, errs


def test_alto_offers_it_once_and_the_glyph_stays_afterwards(browser, tmp_path):
    pg, errs = _open(browser, _d(), tmp_path, settle=3600)
    o = pg.evaluate("()=>{ const e=document.getElementById('ln-offer'); return e && {t:e.querySelector('p').textContent, show:document.getElementById('ln-view').classList.contains('ln-show'), op:parseFloat(getComputedStyle(e).opacity)}; }")
    assert o and "tucked inside other cards" in o["t"] and o["show"] and o["op"] == 1, o
    assert pg.evaluate("document.getElementById('ln-view').getAttribute('aria-pressed')") == "false"
    pg.click("#ln-offer button[data-a=c]")                                       # "Keep Compact": the end of it
    pg.wait_for_timeout(700)
    assert pg.evaluate("!document.getElementById('ln-offer')")
    assert pg.evaluate("document.getElementById('ln-view').getAttribute('aria-pressed')") == "false"
    assert pg.evaluate("!!document.getElementById('ln-view')")                   # the glyph stays
    pg.reload()
    pg.wait_for_timeout(3600)
    if pg.evaluate("(()=>{ try{ return !!localStorage.getItem('alto-compact-offer'); }catch(e){ return null; } })()"):   # (where storage works) once only
        assert pg.evaluate("!document.getElementById('ln-offer')")
    assert not errs, errs


def test_the_offers_yes_opens_the_expanded_view(browser, tmp_path):
    pg, errs = _open(browser, _d(), tmp_path, settle=3600)
    pg.click("#ln-offer button[data-a=x]")
    pg.wait_for_timeout(900)
    assert pg.evaluate("!document.getElementById('ln-offer')")
    assert pg.evaluate("document.getElementById('ln-view').getAttribute('aria-pressed')") == "true"
    assert pg.evaluate("document.querySelectorAll('.ln-kid-shut').length") == 0
    assert not errs, errs


def test_a_phone_is_unchanged_no_glyph_no_offer(browser, tmp_path):
    pg, errs = _open(browser, _d(), tmp_path, phone=True, settle=3600)
    assert pg.evaluate("!document.getElementById('ln-view') && !document.getElementById('ln-offer')")
    assert not errs, errs


# ── Retro and Holographic: the unpressed glyph wears the card rim, 1px, same box (Art, 2026-11-05) ──

RIM = """()=>{ const e=document.getElementById('ln-view'), c=getComputedStyle(e), r=e.getBoundingClientRect();
  return {w:r.width, h:r.height, l:r.left, t:r.top, bw:c.borderTopWidth, bs:c.borderTopStyle, bc:c.borderTopColor, bg:c.backgroundColor, op:c.opacity, box:c.boxSizing, pr:e.getAttribute('aria-pressed')}; }"""


def _styled(browser, tmp_path, style):
    """the board served over a real http server (the style scripts are fetched by a synchronous request, which a file:// page cannot make
    and WebKit does not let a route answer), in one style, the offer already made"""
    import copy
    import http.server
    import socketserver
    import threading
    from alto.build import holo, retro
    from alto.build.builder import build_timeline, load_brief
    html, _ = build_timeline(*load_brief(copy.deepcopy(_d())))
    mod = {"retro": retro, "holo": holo}[style]
    name, text = getattr(mod, style + "_asset")()
    files = {"/t.html": ("text/html", html), mod.PATH: ("text/javascript", text)}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            ct, body = files.get(self.path.split("?")[0], ("text/javascript", ""))
            b = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", ct + "; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def log_message(self, *a):
            pass
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
    ctx.add_init_script(KEEP)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"http://127.0.0.1:{srv.server_address[1]}/t.html")
    pg.wait_for_timeout(900)
    pg.evaluate(f"window._altoStyle.set('{style}')")
    pg.wait_for_timeout(1800)
    pg._srv = srv
    return pg, errs


@pytest.mark.parametrize("style,rim", [("retro", "rgb(217, 174, 85)"), ("holo", "rgb(79, 240, 224)")])
def test_the_unpressed_glyph_wears_a_one_pixel_rim_in_retro_and_holo_and_keeps_its_size(browser, tmp_path, style, rim):
    pg, errs = _styled(browser, tmp_path, style)
    assert pg.evaluate("document.documentElement.classList.contains('alto-%s')" % style)
    cx, cy = pg.evaluate("()=>{ const c=document.getElementById('canvas').getBoundingClientRect(); return [c.left+c.width/2, c.top+c.height/3]; }")
    pg.mouse.move(cx, cy)
    pg.mouse.move(cx + 6, cy + 4)
    pg.wait_for_timeout(500)
    a = pg.evaluate(RIM)
    assert a["pr"] == "false" and a["op"] == "1" and (a["bs"], a["bc"], a["box"]) == ("solid", rim, "border-box") and 0.9 <= float(a["bw"][:-2]) <= 1.2, a   # 1px (the page's own zoom may scale it a hair)
    x, y = _away(pg)
    pg.mouse.move(x, y)
    pg.wait_for_timeout(1900)
    assert pg.evaluate(RIM)["op"] == "0"                                         # the rim fades with the glyph: it is the element's own opacity
    box = pg.evaluate("()=>{ const r=document.getElementById('ln-view').getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]; }")
    pg.mouse.click(*box)
    pg.mouse.move(box[0] - 3, box[1] - 3)
    pg.wait_for_timeout(500)
    b = pg.evaluate(RIM)
    assert b["pr"] == "true" and b["bc"] == b["bg"], b                           # pressed: the rim is its fill, as before
    assert (b["w"], b["h"], b["l"], b["t"]) == (a["w"], a["h"], a["l"], a["t"]), (a, b)   # same size and place in both states
    assert not errs, errs
