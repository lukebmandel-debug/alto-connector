"""One gesture model for the horizontal timeline (Luke, L-1114-focus: "the spanning of nodes is not working well on horizontal timeline
because you can scroll, you can zoom in as well. And so the two are conflicting with each other").

The model, the same zoomed in or not, on a trackpad, a mouse, a pen and a finger:

  * wheel and two fingers PAN along the line: a vertical wheel is travel across, Shift sends it up and down, a trackpad goes where the
    fingers go once the board is bigger than the window;
  * a pinch (Safari's gesture events, a phone's two fingers) or ctrl / cmd + wheel ZOOMS around the pointer; a mouse's ctrl + notch is one
    smooth step, never 1.8x in a frame;
  * a drag pans, and a drag let go with speed coasts, zoomed in as well as at rest;
  * a second finger is a pinch: the finger already travelling the line lets go of it, so the two never fight;
  * the page never scrolls, and the browser's own page zoom never takes a gesture.

Per input, in WebKit and Chromium; the phone's own touches in Chromium (CDP touch points: WebKit's headless build has no multi-touch).
Skipped without Playwright's browsers."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import build_timeline, load_brief  # noqa: E402

LANES_V2 = ROOT / "samples" / "lanes_v2_brief.json"
PHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Mobile/15E148 Safari/604.1")

pw = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            pytest.skip(f"no {request.param}: {e}")
        b.engine = request.param
        yield b
        b.close()


@pytest.fixture(scope="module")
def page_file(tmp_path_factory):
    f = tmp_path_factory.mktemp("lanesgest") / "page.html"
    f.write_text(build_timeline(*load_brief(json.loads(LANES_V2.read_text(encoding="utf-8"))))[0], encoding="utf-8")
    return f


VIEW = """() => { const c=document.getElementById('canvas'), z=window._altoLanesZoom, v=z.view();
  return {sl:c.scrollLeft, st:c.scrollTop, s:z.s(), tx:v?v.tx:null, ty:v?v.ty:null, psx:scrollX, psy:scrollY, vz:visualViewport?visualViewport.scale:1}; }"""
WHEEL = """([dx,dy,ctrl,shift,x,y]) => { const e=new WheelEvent('wheel',{deltaX:dx,deltaY:dy,ctrlKey:!!ctrl,shiftKey:!!shift,clientX:x,clientY:y,bubbles:true,cancelable:true});
  document.getElementById('canvas').dispatchEvent(e); return e.defaultPrevented; }"""
GEST = """([t,sc,x,y]) => { const el=document.elementFromPoint(x,y)||document.body, e=new Event(t,{bubbles:true,cancelable:true});
  [['scale',sc],['rotation',0],['clientX',x],['clientY',y]].forEach(p=>Object.defineProperty(e,p[0],{value:p[1]})); el.dispatchEvent(e); return e.defaultPrevented; }"""
PTR = """([t,id,x,y]) => { const el=document.elementFromPoint(x,y)||document.body;
  el.dispatchEvent(new PointerEvent(t,{pointerId:id,pointerType:'touch',isPrimary:id===1,clientX:x,clientY:y,button:0,buttons:t==='pointerup'?0:1,bubbles:true,cancelable:true})); }"""
# the scale of the board's transform and where a board point sits on screen: the point under the pointer must stay put while zooming
UNDER = """([x,y]) => { const v=window._altoLanesZoom.view(), c=document.getElementById('canvas'), r=c.getBoundingClientRect();
  return v ? [(x-r.left-v.tx)/v.s, (y-r.top-v.ty)/v.s] : null; }"""
FRAMES = """(ms) => new Promise(res => { const z=window._altoLanesZoom, a=[], t0=performance.now();
  (function f(){ const v=z.view(); a.push(v ? v.tx : null); if (performance.now()-t0<ms) requestAnimationFrame(f); else res(a); })(); })"""

CX, CY = 720, 450


@pytest.fixture(scope="module")
def server(page_file):
    import http.server
    import socketserver
    import threading
    from alto.build import palace_assets
    html = page_file.read_bytes()

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            p = self.path.split("?")[0]
            if p.endswith(".html"):
                ct, body = "text/html", html
            else:
                hit = palace_assets.find(p)
                if not hit:
                    self.send_response(404)
                    self.end_headers()
                    return
                ct, body = hit[0], hit[1]
                body = body.encode() if isinstance(body, str) else body
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    class S(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    srv = S(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _desk(browser, f, w=1440, h=900, **kw):
    ctx = browser.new_context(viewport={"width": w, "height": h}, **kw)
    pg = ctx.new_page()
    pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.goto(f if isinstance(f, str) else f.as_uri())
    pg.wait_for_function("typeof showDetail === 'function' && !!window._altoLanesZoom", timeout=60000)
    pg.wait_for_timeout(1800)
    pg.mouse.move(CX, min(CY, h // 2))
    return pg


def _mid(pg):
    """off the page's opening: its first two events both rest at scroll 0 (the camera cannot centre them), so a first notch there moves nothing to see"""
    for _ in range(2):
        pg.evaluate("window._altoLanesStep(1)")
        pg.wait_for_timeout(1300)
    return _v(pg)


def _v(pg):
    return pg.evaluate(VIEW)


def _wheel(pg, dx, dy, n=1, gap=16, ctrl=False, shift=False):
    for _ in range(n):
        if ctrl or shift:
            pg.evaluate(WHEEL, [dx, dy, ctrl, shift, CX, CY])
        else:
            pg.mouse.wheel(dx, dy)
        pg.wait_for_timeout(gap)


def _pinch(pg, end, n=12):
    pg.evaluate(GEST, ["gesturestart", 1, CX, CY])
    for k in range(1, n + 1):
        pg.evaluate(GEST, ["gesturechange", 1 + (end - 1) * k / n, CX, CY])
        pg.wait_for_timeout(16)
    pg.evaluate(GEST, ["gestureend", end, CX, CY])
    pg.wait_for_timeout(500)


def _zoomed(pg, s=1.8):
    _pinch(pg, s)
    v = _v(pg)
    assert v["s"] > 1.5 and v["tx"] is not None, v
    return v


# ── at rest: wheel, two fingers, a drag, the keys ──
def test_a_wheel_notch_travels_along_the_line_whichever_way_it_turns(browser, page_file):
    """the vertical wheel is travel across (Shift changes nothing at rest: the line has no up and down)"""
    pg = _desk(browser, page_file)
    _mid(pg)
    try:
        for dx, dy in ((0, 100), (100, 0)):
            a = _v(pg)
            pg.mouse.wheel(dx, dy)
            pg.wait_for_timeout(1100)
            b = _v(pg)
            assert b["sl"] - a["sl"] > 40 and abs(b["st"] - a["st"]) < 2, (dx, dy, a, b)
            assert b["psy"] == 0 and b["psx"] == 0
        a = _v(pg)
        pg.mouse.wheel(0, -100)
        pg.wait_for_timeout(1100)
        assert _v(pg)["sl"] < a["sl"] - 40                      # and back
        assert pg.errs == []
    finally:
        pg.context.close()


@pytest.mark.parametrize("d", [(0, 6), (8, 0), (8, 6)], ids=["vertical", "horizontal", "diagonal"])
def test_a_trackpad_stream_travels_the_line_and_the_page_never_scrolls(browser, page_file, d):
    pg = _desk(browser, page_file)
    _mid(pg)
    try:
        a = _v(pg)
        _wheel(pg, d[0], d[1], 30)
        pg.wait_for_timeout(1100)
        b = _v(pg)
        assert b["sl"] - a["sl"] > 120 and b["psy"] == 0 and b["psx"] == 0, (a, b)
        assert b["s"] == 1 and b["vz"] == 1
    finally:
        pg.context.close()


def test_a_drag_travels_and_a_fling_goes_on(browser, page_file):
    pg = _desk(browser, page_file)
    _mid(pg)
    try:
        a = _v(pg)
        pg.mouse.down()
        for i in range(1, 11):
            pg.mouse.move(CX - i * 30, CY)
            pg.wait_for_timeout(8)
        pg.mouse.up()
        pg.wait_for_timeout(1500)
        assert _v(pg)["sl"] - a["sl"] > 250
    finally:
        pg.context.close()


# ── the first input after the page loads must visibly move (the opening's first two events share scroll 0) ──
@pytest.mark.parametrize("how", ["notch", "key", "swipe"])
def test_the_first_input_after_load_visibly_moves(browser, page_file, how):
    pg = _desk(browser, page_file)
    try:
        assert _v(pg)["sl"] == 0
        if how == "notch":
            pg.mouse.wheel(0, 100)
        elif how == "key":
            pg.keyboard.press("ArrowRight")
        else:
            _wheel(pg, 6, 0, 8)
        pg.wait_for_timeout(1400)
        assert _v(pg)["sl"] > 20, _v(pg)
        assert pg.errs == []
    finally:
        pg.context.close()


# ── zoom: a pinch, ctrl / cmd + wheel, the keys ──
def test_a_pinch_zooms_around_the_pointer_in_and_out(browser, page_file):
    pg = _desk(browser, page_file)
    try:
        _pinch(pg, 1.8)
        v = _v(pg)
        assert 1.7 < v["s"] < 1.9 and v["vz"] == 1
        p0 = pg.evaluate(UNDER, [CX, CY])
        _pinch(pg, 1.3)
        v2 = _v(pg)
        assert v2["s"] > v["s"] * 1.15
        # (a second pinch starts over wherever the board is, so the point under the fingers is what stays put within it)
        _pinch(pg, .6)
        assert _v(pg)["s"] < v2["s"] * .8
        assert p0 is not None and pg.errs == []
    finally:
        pg.context.close()


def test_ctrl_wheel_zooms_around_the_pointer_and_never_the_browser(browser, page_file):
    pg = _desk(browser, page_file)
    try:
        taken = pg.evaluate(WHEEL, [0, -5, True, False, CX, CY])
        if browser.engine == "chromium":
            assert taken is True            # the browser's own page zoom never sees it (Safari pinches with gesture events, which are taken, and keeps its wheel passive)
        _wheel(pg, 0, -5, 11, ctrl=True)
        pg.wait_for_timeout(300)
        v = _v(pg)
        assert v["s"] > 1.3 and v["vz"] == 1 and v["psy"] == 0
        under = pg.evaluate(UNDER, [CX, CY])
        _wheel(pg, 0, 5, 6, ctrl=True)
        pg.wait_for_timeout(300)
        assert _v(pg)["s"] < v["s"] and under is not None
    finally:
        pg.context.close()


def test_only_the_arrow_keys_act(browser, page_file):
    """Luke: "I only want the arrow keys to do something on the keyboard, no other keys should come into play." (Typing in a field is untouched.)"""
    pg = _desk(browser, page_file)
    try:
        _mid(pg)
        a = _v(pg)
        for k in ["Space", "PageDown", "PageUp", "Home", "End", "Escape", "=", "-", "0", "+", "Enter", "Shift", "Control+=", "Control+-", "Meta+Minus", "Meta+=",
                  "Shift+ArrowRight", "Control+ArrowRight", "Meta+ArrowLeft", "Alt+ArrowRight"]:
            pg.keyboard.press(k)
            pg.wait_for_timeout(350)
            b = _v(pg)
            assert abs(b["sl"] - a["sl"]) < 1 and b["s"] == 1 and not pg.evaluate("window._focusedNodeId"), (k, a, b)
        assert pg.evaluate("document.activeElement && document.activeElement.tagName") != "INPUT"
        pg.keyboard.press("ArrowRight")                                    # and the arrow does step
        pg.wait_for_timeout(1300)
        assert _v(pg)["sl"] - a["sl"] > 100
        # an enlarged card: nothing but the arrows moves it either
        nid = pg.evaluate("window._altoLanesCurrent()")
        pg.evaluate("id => window.enterFocus(id)", nid)
        pg.wait_for_timeout(1500)
        for k in ["Escape", "=", "-", "0", "Space", "Enter", "Control+=", "Meta+-", "Shift+ArrowRight"]:
            pg.keyboard.press(k)
            pg.wait_for_timeout(300)
            assert pg.evaluate("window._focusedNodeId") == nid, k
        pg.keyboard.press("ArrowRight")
        pg.wait_for_timeout(1500)
        nxt = pg.evaluate("window._focusedNodeId")
        assert nxt and nxt != nid                                         # Left / Right step to the next card, which stays enlarged
        assert pg.errs == []
    finally:
        pg.context.close()


def test_typing_in_a_text_field_still_works(browser, page_file):
    pg = _desk(browser, page_file)
    try:
        pg.evaluate("() => { const i=document.createElement('input'); i.id='tt'; document.body.appendChild(i); i.focus(); }")
        pg.keyboard.type("0=- ")
        assert pg.evaluate("document.getElementById('tt').value") == "0=- "
        assert _v(pg)["s"] == 1
    finally:
        pg.context.close()


def test_modifiers_do_not_change_what_a_wheel_does(browser, page_file):
    pg = _desk(browser, page_file)
    try:
        _mid(pg)
        for kw in ({"shift": True}, {"ctrl": True}):
            a = _v(pg)
            prevented = pg.evaluate(WHEEL, [0, 100, kw.get("ctrl", False), kw.get("shift", False), CX, CY])
            pg.wait_for_timeout(1100)
            b = _v(pg)
            assert b["sl"] - a["sl"] > 40 and b["s"] == 1 and abs(b["st"] - a["st"]) < 2, (kw, a, b)          # a notch along the line, never a zoom
            if kw.get("ctrl") and browser.engine == "chromium":
                assert prevented is True                                   # the browser's page zoom never takes it
        a = _v(pg)
        pg.evaluate("""([x,y]) => { document.getElementById('canvas').dispatchEvent(new WheelEvent('wheel', {deltaY:100, metaKey:true, clientX:x, clientY:y, bubbles:true, cancelable:true})); }""", [CX, CY])
        pg.wait_for_timeout(1100)
        assert _v(pg)["sl"] - a["sl"] > 40 and _v(pg)["s"] == 1
        # a trackpad pinch in Chrome (ctrl + small deltas) is still the zoom
        _wheel(pg, 0, -5, 11, ctrl=True)
        pg.wait_for_timeout(300)
        assert _v(pg)["s"] > 1.3
    finally:
        pg.context.close()


@pytest.mark.parametrize("fits", [True, False], ids=["lanes-fit", "lanes-taller"])
def test_a_trackpads_up_and_down_goes_up_and_down_unless_the_lanes_fit(browser, page_file, fits):
    pg = _desk(browser, page_file, 1440, 900 if fits else 300)
    try:
        _mid(pg)
        room = pg.evaluate("() => { const c=document.getElementById('canvas'); return c.scrollHeight-c.clientHeight; }")
        if not fits and room <= 5:
            pytest.skip("these lanes fit even this window")
        a = _v(pg)
        pg.mouse.wheel(0, 100)                                                     # a mouse's notch is always along the line
        pg.wait_for_timeout(2200)
        b = _v(pg)
        assert b["sl"] - a["sl"] > 40 and abs(b["st"] - a["st"]) < 5, (a, b)           # (the path's own height from one event to the next: a few px)
        a = b
        _wheel(pg, 0, -6 if a["st"] > room / 2 else 6, 10)
        pg.wait_for_timeout(1200)
        b = _v(pg)
        if room > 5:
            assert abs(b["st"] - a["st"]) > 1 and abs(b["sl"] - a["sl"]) < 2, (room, a, b)           # up and down
            a = b
            _wheel(pg, 8, 0, 10)
            pg.wait_for_timeout(1200)
            assert _v(pg)["sl"] - a["sl"] > 40 and abs(_v(pg)["st"] - a["st"]) < 2                 # sideways: along the line, the height kept
        else:
            assert fits and b["sl"] - a["sl"] > 20, (a, b)                                          # the lanes fit: vertical goes along the line
    finally:
        pg.context.close()


def test_a_drag_pans_freely_when_the_lanes_are_taller_than_the_window(browser, page_file):
    pg = _desk(browser, page_file, 1440, 300)
    try:
        _mid(pg)
        if pg.evaluate("() => { const c=document.getElementById('canvas'); return c.scrollHeight-c.clientHeight; }") <= 5:
            pytest.skip("these lanes fit this window")
        a = _v(pg)
        pg.mouse.down()
        for i in range(1, 9):
            pg.mouse.move(CX - i * 20, 150 + i * 6)
            pg.wait_for_timeout(10)
        pg.mouse.up()
        pg.wait_for_timeout(1200)
        b = _v(pg)
        assert b["sl"] - a["sl"] > 60 and a["st"] - b["st"] > 2, (a, b)                  # along the line and (dragged down) the view up
    finally:
        pg.context.close()


# ── ENLARGING vs ZOOMING (Luke: "Did you fix the problem of enlarging nodes vs. zooming in?") ──
def _enlarge_current(pg):
    nid = pg.evaluate("window._altoLanesCurrent()")
    pg.click(f"#node-{nid} .node-card")
    pg.wait_for_function("id => window._focusedNodeId === id", arg=nid, timeout=5000)
    pg.wait_for_timeout(1400)
    return nid


def _card_w(pg, nid):
    return pg.evaluate("id => document.querySelector('#node-' + id + ' .node-card').getBoundingClientRect().width", nid)


@pytest.mark.parametrize("closer", ["notch", "trackpad", "pinch-gesture", "pinch-ctrl-wheel"])
def test_the_first_scroll_or_pinch_on_an_enlarged_card_closes_it_and_nothing_else(browser, page_file, closer):
    """no zoom, no hop to a neighbour, and the line is exactly where it was"""
    pg = _desk(browser, page_file)
    try:
        _mid(pg)
        a = _v(pg)
        _enlarge_current(pg)
        if closer == "notch":
            pg.mouse.wheel(0, 100)
        elif closer == "trackpad":
            for _ in range(14):
                pg.evaluate(WHEEL, [5, 4, False, False, CX, CY])
                pg.wait_for_timeout(16)
        elif closer == "pinch-gesture":
            _pinch(pg, 1.6)
        else:
            _wheel(pg, 0, -6, 12, ctrl=True)
        pg.wait_for_timeout(1500)
        b = _v(pg)
        assert not pg.evaluate("window._focusedNodeId"), "the card is closed"
        assert abs(b["sl"] - a["sl"]) < 2 and abs(b["st"] - a["st"]) < 2 and b["s"] == 1, (closer, a, b)
        assert pg.evaluate("window._altoLanesZoom.view()") is None
        assert pg.errs == []
    finally:
        pg.context.close()


def test_enlarging_while_zoomed_gives_the_same_size_card(browser, page_file):
    pg = _desk(browser, page_file)
    pg2 = _desk(browser, page_file)
    try:
        _zoomed(pg, 1.8)
        pt = pg.evaluate("""() => { let best = null, bd = 1e9; for (const n of document.querySelectorAll('#world .node')) { const r = n.querySelector('.node-card').getBoundingClientRect();
            const l = Math.max(r.left, 120), rt = Math.min(r.right, 1320), tp = Math.max(r.top, 150), bt = Math.min(r.bottom, 860);
            if (rt - l < 40 || bt - tp < 30) continue;
            const cx = (l + rt) / 2, cy = (tp + bt) / 2, d = Math.hypot(cx - 720, cy - 450);
            if (d < bd) { bd = d; best = [n.id.slice(5), cx, cy]; } } return best; }""")
        assert pt, "a card in view"
        pg.mouse.click(pt[1], pt[2])
        pg.wait_for_function("id => window._focusedNodeId === id", arg=pt[0], timeout=6000)
        pg.wait_for_timeout(1500)
        w1 = _card_w(pg, pt[0])
        pg2.evaluate("id => window.enterFocus(id)", pt[0])
        pg2.wait_for_function("id => window._focusedNodeId === id", arg=pt[0], timeout=6000)
        pg2.wait_for_timeout(1500)
        assert abs(w1 - _card_w(pg2, pt[0])) < 3, (w1, _card_w(pg2, pt[0]))
        assert _v(pg)["s"] == 1 and pg.errs == []
    finally:
        pg.context.close()
        pg2.context.close()


def test_enlarging_after_a_zoom_back_to_the_fitted_view_works(browser, page_file):
    pg = _desk(browser, page_file)
    try:
        _mid(pg)
        _pinch(pg, 1.5)
        _pinch(pg, 1 / 1.5)
        pg.wait_for_timeout(1300)
        assert _v(pg)["s"] == 1
        nid = _enlarge_current(pg)
        assert pg.evaluate("window._focusedNodeId") == nid
    finally:
        pg.context.close()


def test_a_click_is_never_read_as_part_of_a_pinch(browser, page_file):
    pg = _desk(browser, page_file)
    try:
        _mid(pg)
        nid = pg.evaluate("window._altoLanesCurrent()")
        sel = f"#node-{nid} .node-card"
        box = pg.locator(sel).bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        pg.mouse.move(x, y)
        for scale_to in (1.0,):                                              # a pinch that ends right on the card, a click arriving as the fingers lift
            pg.evaluate(GEST, ["gesturestart", 1, x, y])
            pg.evaluate(GEST, ["gesturechange", 1.04, x, y])
            pg.evaluate(GEST, ["gestureend", 1.04, x, y])
        pg.evaluate("sel => document.querySelector(sel).dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}))", sel)
        pg.wait_for_timeout(500)
        assert not pg.evaluate("window._focusedNodeId"), "the click after a pinch is not a tap"
        # two fingers down, then lifted with a click on the card: still not a tap
        pg.evaluate(PTR, ["pointerdown", 1, x - 30, y])
        pg.evaluate(PTR, ["pointerdown", 2, x + 30, y])
        pg.evaluate(PTR, ["pointerup", 2, x + 30, y])
        pg.evaluate(PTR, ["pointerup", 1, x - 30, y])
        pg.evaluate("sel => document.querySelector(sel).dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}))", sel)
        pg.wait_for_timeout(500)
        assert not pg.evaluate("window._focusedNodeId")
        pg.wait_for_timeout(900)                                             # and a real click a moment later is a tap
        pg.click(sel)
        pg.wait_for_timeout(1200)
        assert pg.evaluate("window._focusedNodeId") == nid
    finally:
        pg.context.close()


# ── zoomed in: the same moves pan ──
def test_zoomed_a_vertical_notch_pans_along_the_line(browser, page_file):
    pg = _desk(browser, page_file)
    try:
        _zoomed(pg)
        a = _v(pg)
        pg.mouse.wheel(0, 100)
        pg.wait_for_timeout(900)
        b = _v(pg)
        assert abs(b["tx"] - a["tx"]) > 40 and abs(b["ty"] - a["ty"]) < 2, (a, b)       # across, as at rest
        assert b["psy"] == 0
    finally:
        pg.context.close()


def test_zoomed_two_fingers_go_where_the_fingers_go(browser, page_file):
    pg = _desk(browser, page_file)
    try:
        _zoomed(pg)
        a = _v(pg)
        _wheel(pg, 8, 6, 30)
        pg.wait_for_timeout(500)
        b = _v(pg)
        assert abs(b["tx"] - a["tx"]) > 100 and abs(b["ty"] - a["ty"]) > 10, (a, b)        # (the board is only a little taller than the window: its up and down is short)
        assert b["s"] == a["s"] and b["psy"] == 0
    finally:
        pg.context.close()


def test_zoomed_a_notch_is_chased_smoothly(browser, page_file):
    pg = _desk(browser, page_file)
    try:
        _zoomed(pg)
        a = _v(pg)["tx"]
        pg.mouse.wheel(100, 0)
        fr = pg.evaluate(FRAMES, 400)
        total = abs(fr[-1] - a)
        assert total > 60
        steps = [abs(y - x) for x, y in zip([a] + fr, fr)]
        assert max(steps) < .6 * total, (max(steps), total)       # no 100 px jump in one frame
    finally:
        pg.context.close()


def test_zoomed_a_drag_pans_and_a_fling_coasts_on(browser, page_file):
    pg = _desk(browser, page_file)
    try:
        _zoomed(pg)
        a = _v(pg)
        pg.mouse.down()
        for i in range(1, 11):
            pg.mouse.move(CX - i * 30, CY)
            pg.wait_for_timeout(8)
        pg.mouse.up()
        pg.wait_for_timeout(60)
        early = _v(pg)["tx"]
        pg.wait_for_timeout(900)
        late = _v(pg)["tx"]
        assert a["tx"] - early > 200 and early - late > 8, (a["tx"], early, late)           # it kept going after the hand left
    finally:
        pg.context.close()


# ── two hands never fight ──
def test_a_second_finger_takes_the_first_off_the_line(browser, page_file):
    """a finger travelling the line, a second lands on the background: the first lets go (nothing flings, nothing travels on the moves of
    either) and the pinch has the board"""
    pg = _desk(browser, page_file)
    try:
        _mid(pg)
        bg = pg.evaluate("""() => { const out = []; for (let y = 140; y < 880 && out.length < 2; y += 30) for (let x = 100; x < 1340 && out.length < 2; x += 40) {
            const e = document.elementFromPoint(x, y); if (e && e.closest && e.closest('#canvas') && !e.closest('.node,.lanes-tag,button,a,#lanes-nav') && (!out.length || Math.abs(out[0][0] - x) > 150)) out.push([x, y]); } return out; }""")
        assert len(bg) == 2, bg
        (x1, y1), (x2, y2) = bg
        pg.evaluate(PTR, ["pointerdown", 1, x1, y1])
        for i in range(1, 5):
            pg.evaluate(PTR, ["pointermove", 1, x1 - i * 8, y1])
            pg.wait_for_timeout(16)
        a = _v(pg)
        pg.evaluate(PTR, ["pointerdown", 2, x2, y2])
        for i in range(1, 8):
            pg.evaluate(PTR, ["pointermove", 2, x2 + i * 25, y2])
            pg.evaluate(PTR, ["pointermove", 1, x1 - 32 - i * 25, y1])
            pg.wait_for_timeout(16)
        pg.wait_for_timeout(120)
        b = _v(pg)
        assert abs(b["sl"] - a["sl"]) < 100, (a, b)                 # the two fingers' 175 px of moves are not travel (the settle on the nearest event may still shift it a little)
        pg.evaluate(PTR, ["pointerup", 2, x2 + 175, y2])
        pg.evaluate(PTR, ["pointerup", 1, x1 - 207, y1])
        pg.wait_for_timeout(1300)
        assert pg.errs == []
    finally:
        pg.context.close()


# ── the lanes features that live beside it ──
def test_click_enlarge_and_a_step_still_work(browser, page_file):
    pg = _desk(browser, page_file)
    try:
        pg.keyboard.press("ArrowRight")
        pg.wait_for_timeout(1300)
        card = pg.locator("#world .node.ln-cur .node-card").first
        card.click()
        pg.wait_for_timeout(1500)
        assert pg.evaluate("!!window._focusedNodeId")
        pg.mouse.wheel(0, 100)                                       # (Esc does nothing here: the first scroll closes the card)
        pg.wait_for_timeout(1400)
        assert not pg.evaluate("window._focusedNodeId")
        assert pg.errs == []
    finally:
        pg.context.close()


# ── a phone: one finger pans, two pinch, Safari's page zoom never takes it (Chromium's touch points) ──
def test_a_phone_one_finger_pans_two_fingers_pinch(browser, server):
    if browser.engine != "chromium":
        pytest.skip("headless WebKit has no multi-touch input")
    pg = _desk(browser, server + "/lanes.html?view=whole", 390, 844, has_touch=True, is_mobile=True, user_agent=PHONE_UA)
    try:
        assert pg.evaluate("document.documentElement.classList.contains('phone-whole')")
        cdp = pg.context.new_cdp_session(pg)

        def touch(t, pts):
            cdp.send("Input.dispatchTouchEvent", {"type": t, "touchPoints": [{"x": x, "y": y, "id": i + 1} for i, (x, y) in enumerate(pts)]})
        a = _v(pg)
        touch("touchStart", [(300, 420)])
        for i in range(1, 9):
            touch("touchMove", [(300 - i * 20, 420)])
            pg.wait_for_timeout(16)
        touch("touchEnd", [])
        pg.wait_for_timeout(1300)
        b = _v(pg)
        assert b["sl"] - a["sl"] > 100 and b["vz"] == 1
        touch("touchStart", [(120, 420), (270, 420)])
        for i in range(1, 11):
            touch("touchMove", [(120 - i * 8, 420), (270 + i * 8, 420)])
            pg.wait_for_timeout(16)
        touch("touchEnd", [])
        pg.wait_for_timeout(700)
        c = _v(pg)
        assert c["s"] > 1.5 and c["vz"] == 1, c
        d = c["tx"]
        touch("touchStart", [(300, 420)])
        for i in range(1, 9):
            touch("touchMove", [(300 - i * 15, 420)])
            pg.wait_for_timeout(16)
        touch("touchEnd", [])
        pg.wait_for_timeout(700)
        assert _v(pg)["tx"] < d - 60                                # one finger pans the zoomed board
        assert pg.errs == []
    finally:
        pg.context.close()
