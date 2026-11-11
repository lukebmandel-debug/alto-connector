"""Focus on a branch (alto/build/focus_branch.py): an enlarged card gets a small button; pressed, the page holds that card and what
hangs from it and the rest is faded and untouchable until Exit focus (or Esc). Luke, L-1103-091725 and the rules he confirmed
(Board B-1103-091725). Skipped when Playwright or its browsers are not installed."""
import copy
import http.server
import json
import socketserver
import threading
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")

from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build import palace_assets  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
F = "window._altoFocusBranch"
FAKE = """(function(){ var store=null;
 var C={enabled:true, known:true, user:{uid:'u1'}, getEdits:function(){ return Promise.resolve(store); },
  putEdits:function(t,d){ store=JSON.parse(JSON.stringify(d)); return Promise.resolve(); }, watchEdits:function(){ return function(){}; }};
 Object.defineProperty(window,'AltoCloud',{get:function(){return C;}, set:function(){}, configurable:true}); })();"""
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
      "Version/17.0 Mobile/15E148 Safari/604.1")
ACCEPT = {"acceptance", "mirror-image", "mailbox-rule", "acceptance-by-conduct"}      # the outline sample's "Acceptance" branch


def _html(name):
    d = json.loads((ROOT / "samples" / f"{name}_brief.json").read_text(encoding="utf-8"))
    return build_timeline(*load_brief(copy.deepcopy(d)))[0]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    root = tmp_path_factory.mktemp("focus")
    for name in ("outline", "contracts", "lanes"):
        (root / f"{name}.html").write_text(_html(name), encoding="utf-8")

    class H(http.server.BaseHTTPRequestHandler):          # the pages, and the hosted phone layer a phone fetches
        def do_GET(self):
            p = self.path.split("?")[0]
            f = root / p.lstrip("/")
            if p.endswith(".html") and f.exists():
                ct, body = "text/html", f.read_bytes()
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


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:                       # no browser downloaded
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


def _open(browser, server, page, phone=False, view=None, init=None):
    if phone:
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, user_agent=UA)
    else:
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    if init:
        ctx.add_init_script(init)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.goto(f"{server}/{page}.html" + (f"?view={view}" if view else ""))
    pg.wait_for_function("typeof showDetail === 'function' && !!window._altoFocusBranch", timeout=60000)
    pg.wait_for_timeout(1800)
    return pg


def _st(pg):
    return pg.evaluate(f"({{f: window._focusedNodeId, feat: window._featuredNodeId, depth: {F}.depth(), root: {F}.root()}})")


def _btn(pg):
    return pg.evaluate("""() => { var b = document.getElementById('af-btn'); if(!b) return null; var r = b.getBoundingClientRect(), c = getComputedStyle(b);
      return {on: c.display !== 'none' && +c.opacity > 0.5, l: r.left, t: r.top, r: r.right, b: r.bottom}; }""")


def _card(pg, nid):
    return pg.evaluate("""(id) => { var r = document.querySelector('#node-' + id + ' .node-card').getBoundingClientRect(); return {l: r.left, t: r.top, r: r.right, b: r.bottom}; }""", nid)


def _enlarge(pg, nid):
    pg.evaluate("id => enterFocus(id)", nid)
    pg.wait_for_function("id => window._focusedNodeId === id", arg=nid, timeout=5000)
    pg.wait_for_function("() => { var b = document.getElementById('af-btn'); return b && b.classList.contains('in'); }", timeout=5000)
    pg.wait_for_timeout(350)                        # its fade-in


def _hold(pg, nid):
    _enlarge(pg, nid)
    pg.click("#af-btn")
    pg.wait_for_function(f"() => {F}.root() === {json.dumps(nid)}", timeout=3000)
    pg.wait_for_timeout(500)


def _out(pg):
    """The cards outside the held branch: their classes, fade and whether a pointer can reach them."""
    return pg.evaluate("""() => [...document.querySelectorAll('#world .node')].map(n => ({id: n.id.slice(5), out: n.classList.contains('af-out'),
      op: +getComputedStyle(n.querySelector('.node-card')).opacity, pe: getComputedStyle(n).pointerEvents}))""")


# ── the page ──
@pytest.mark.parametrize("page", ["outline", "contracts", "lanes"])
def test_every_timeline_format_carries_the_layer(server, page):
    import urllib.request
    text = urllib.request.urlopen(f"{server}/{page}.html").read().decode()
    assert 'id="alto-focus-branch"' in text and "_altoFocusEsc" in text


# ── the button ──
def test_the_button_shows_beside_an_enlarged_card_and_only_then(browser, server):
    pg = _open(browser, server, "outline")
    try:
        assert not _btn(pg)["on"], "a button with nothing enlarged"
        _enlarge(pg, "offer")
        b, c = _btn(pg), _card(pg, "offer")
        assert b["on"]
        assert b["l"] >= c["r"] - 1 or b["b"] <= c["t"] + 1, f"the button overlaps its card: {b} {c}"     # beside it, not over it
        assert abs(b["l"] - c["r"]) < 40, f"the button is not next to the card: {b} {c}"
        pg.keyboard.press("Escape")                    # un-enlarged: it goes
        pg.wait_for_timeout(600)
        assert not _btn(pg)["on"]
        assert pg.errors == []
    finally:
        pg.context.close()


def test_the_button_stays_while_the_pointer_travels_to_it(browser, server):
    """The edit-strip rule (L-1102-193854): the way from the card to what sits beside it never loses it."""
    pg = _open(browser, server, "outline")
    try:
        _enlarge(pg, "offer")
        c, b = _card(pg, "offer"), _btn(pg)
        pg.mouse.move((c["l"] + c["r"]) / 2, c["t"] + 20)
        for i in range(1, 13):
            pg.mouse.move((c["l"] + c["r"]) / 2 + ((b["l"] + 17) - (c["l"] + c["r"]) / 2) * i / 12, c["t"] + 20 + ((b["t"] + 17) - (c["t"] + 20)) * i / 12)
            assert _btn(pg)["on"], f"the button hid on the way, step {i}"
        pg.mouse.click(b["l"] + 17, b["t"] + 17)
        pg.wait_for_timeout(500)
        assert _st(pg)["root"] == "offer"
    finally:
        pg.context.close()


def test_the_button_holds_still_under_a_resting_pointer(browser, server):
    """Luke 2026-11-10: "focus mode runs away from the cursor". The hover grow scaled the button itself, place() read that scaled box
    to undo the page zoom, and every 110 ms tick moved the button (up to ~13 px) away from a pointer resting on its edge, and back."""
    pg = _open(browser, server, "outline")
    try:
        _enlarge(pg, "offer")
        b0 = _btn(pg)
        pg.mouse.move(b0["l"] - 120, b0["t"] + 14)
        pg.mouse.move(b0["l"] + 2, b0["t"] + 14)                     # resting on the button's left edge
        lefts = []
        for _ in range(12):
            pg.wait_for_timeout(110)
            lefts.append(_btn(pg)["l"])
        assert pg.evaluate("document.getElementById('af-btn').matches(':hover')")
        assert max(lefts) - min(lefts) < 0.5 and abs(lefts[0] - b0["l"]) < 0.5, f"the button moved under the pointer: {b0['l']} -> {lefts}"
        assert pg.evaluate("getComputedStyle(document.getElementById('af-btn')).transform") == "none", "hover scales the button itself"
    finally:
        pg.context.close()


# ── holding a branch ──
def test_outside_is_faded_untouchable_and_not_filter_dimmed(browser, server):
    pg = _open(browser, server, "outline")
    try:
        _hold(pg, "acceptance")
        pg.evaluate("exitFocus()")                      # unenlarged, the focus still held
        pg.wait_for_timeout(700)
        rows = {r["id"]: r for r in _out(pg)}
        assert {i for i, r in rows.items() if not r["out"]} == ACCEPT
        for i, r in rows.items():
            if r["out"]:
                assert r["op"] == pytest.approx(0.14, abs=0.02) and r["pe"] == "none", (i, r)
            else:
                assert r["op"] == 1 and r["pe"] != "none", (i, r)
        assert pg.evaluate("document.querySelectorAll('#world .node-card.dimmed, #world .node-card.ent-dimmed').length") == 0
        # a pointer over an outside card reaches nothing of it
        c = _card(pg, "offer")
        assert pg.evaluate("([x, y]) => { var e = document.elementFromPoint(x, y); return !(e && e.closest('#node-offer')); }", [(c["l"] + c["r"]) / 2, (c["t"] + c["b"]) / 2])
    finally:
        pg.context.close()


def test_an_enlarged_card_inside_the_branch_reads_apart_from_the_outside(browser, server):
    pg = _open(browser, server, "outline")
    try:
        _hold(pg, "acceptance")
        rows = {r["id"]: r for r in _out(pg)}
        assert rows["mailbox-rule"]["op"] > 0.3 > rows["offer"]["op"] + 0.1
        assert rows["offer"]["op"] == pytest.approx(0.14, abs=0.02)            # the enlarged card's own faded look
    finally:
        pg.context.close()


def test_arrows_never_leave_the_branch_and_up_stops_at_its_card(browser, server):
    pg = _open(browser, server, "outline")
    try:
        _hold(pg, "acceptance")
        pg.keyboard.press("ArrowUp")
        pg.wait_for_timeout(900)
        assert _st(pg)["f"] == "acceptance", "Up left the focused card"
        pg.keyboard.press("ArrowDown")
        pg.wait_for_timeout(900)
        assert _st(pg)["f"] in ACCEPT - {"acceptance"}, "Down did not go to a child"
        seen = set()
        for k in ["ArrowLeft", "ArrowRight", "ArrowDown", "ArrowUp", "ArrowRight", "ArrowDown", "ArrowDown", "ArrowLeft", "ArrowUp", "ArrowUp", "ArrowUp", "ArrowRight"]:
            pg.keyboard.press(k)
            pg.wait_for_timeout(750)
            seen.add(_st(pg)["f"])
        assert seen <= ACCEPT, f"left the branch: {seen - ACCEPT}"
        assert len(seen) > 1
    finally:
        pg.context.close()


def test_an_arrow_with_nothing_enlarged_goes_back_in(browser, server):
    pg = _open(browser, server, "outline")
    try:
        _hold(pg, "acceptance")
        pg.evaluate("exitFocus()")
        pg.wait_for_timeout(700)
        pg.keyboard.press("ArrowDown")
        pg.wait_for_timeout(900)
        assert _st(pg)["f"] == "acceptance"
    finally:
        pg.context.close()


def test_nothing_reaches_a_card_outside(browser, server):
    pg = _open(browser, server, "outline")
    try:
        _hold(pg, "acceptance")
        pg.evaluate("enterFocus('consideration')")
        pg.evaluate("showDetail('node', 'offer')")
        pg.wait_for_timeout(600)
        assert _st(pg)["f"] == "acceptance"
        assert not pg.evaluate("document.documentElement.classList.contains('detail-open')")
    finally:
        pg.context.close()


def test_exit_and_esc_step_back_one_level_each(browser, server):
    pg = _open(browser, server, "outline")
    try:
        _hold(pg, "formation")
        pg.keyboard.press("ArrowDown")
        pg.wait_for_timeout(900)
        pg.evaluate("enterFocus('acceptance')")
        _hold_inner = pg.wait_for_function("() => document.getElementById('af-btn').classList.contains('in')", timeout=4000)  # noqa: F841
        pg.click("#af-btn")
        pg.wait_for_timeout(500)
        st = _st(pg)
        assert st["depth"] == 2 and st["root"] == "acceptance"
        assert set(pg.evaluate(f"{F}.members()")) == ACCEPT
        pg.click("#af-exit")                                             # the button: one level
        pg.wait_for_timeout(500)
        st = _st(pg)
        assert st["depth"] == 1 and st["root"] == "formation" and st["f"] == "acceptance"
        pg.keyboard.press("Escape")                                      # Esc: the last level, the card stays enlarged
        pg.wait_for_timeout(500)
        st = _st(pg)
        assert st["depth"] == 0 and st["f"] == "acceptance"
        assert not any(r["out"] for r in _out(pg))
        assert pg.evaluate("!document.documentElement.classList.contains('af-on')")
        pg.keyboard.press("Escape")                                      # and now the card's own Esc
        pg.wait_for_timeout(500)
        assert _st(pg)["f"] is None
    finally:
        pg.context.close()


def test_leaving_the_focus_puts_every_answer_back(browser, server):
    pg = _open(browser, server, "outline")
    try:
        pg.evaluate("window._t0 = [window._altoShown, window._altoFilterOn]")
        _hold(pg, "acceptance")
        assert not pg.evaluate("window._altoShown('offer')") and pg.evaluate("window._altoShown('mailbox-rule')")
        pg.click("#af-exit")
        pg.wait_for_timeout(400)
        assert pg.evaluate("window._altoShown === window._t0[0] && window._altoFilterOn === window._t0[1]")
        assert pg.evaluate("window._altoShown('offer') && !window._altoFilterOn()")
    finally:
        pg.context.close()


def test_a_filter_works_inside_the_branch_only(browser, server):
    pg = _open(browser, server, "outline")
    try:
        _hold(pg, "acceptance")
        pg.evaluate("""() => { var c = document.querySelector('#node-mailbox-rule .node-card'); c.classList.add('ent-dimmed'); }""")   # what a filter does to a card
        assert not pg.evaluate("window._altoShown('mailbox-rule')")
        assert pg.evaluate("window._altoShown('mirror-image')")
        assert not pg.evaluate("window._altoShown('offer')")              # outside stays out whatever the filter says
        pg.evaluate("exitFocus()")
        pg.wait_for_timeout(600)
        pg.evaluate("enterFocus('acceptance')")
        pg.wait_for_timeout(900)
        seen = set()
        for _ in range(6):
            pg.keyboard.press("ArrowDown")
            pg.wait_for_timeout(700)
            seen.add(_st(pg)["f"])
        assert "mailbox-rule" not in seen
    finally:
        pg.context.close()


def test_search_finds_only_the_branch(browser, server):
    pg = _open(browser, server, "outline")
    try:
        _hold(pg, "acceptance")
        pg.click("#search-btn")
        pg.fill("#search-input", "revocation")
        pg.wait_for_timeout(900)
        titles = pg.evaluate("[...document.querySelectorAll('#search-results .search-result')].map(e => e.innerText)")
        assert titles and all("Revocation" not in t.split("\n")[0] and "Offer" not in t.split("\n")[0] for t in titles), titles
        pg.fill("#search-input", "mailbox")
        pg.wait_for_timeout(900)
        assert pg.evaluate("[...document.querySelectorAll('#search-results .search-result')].some(e => /Mailbox Rule/.test(e.innerText))")
    finally:
        pg.context.close()


# ── the other formats ──
@pytest.mark.parametrize("page", ["contracts", "lanes"])
def test_a_plain_and_a_horizontal_timeline_hold_their_card(browser, server, page):
    pg = _open(browser, server, page)
    try:
        nid = pg.evaluate("NODE_ORDER[2]")
        _hold(pg, nid)
        assert _st(pg)["root"] == nid and pg.evaluate("document.documentElement.classList.contains('af-on')")
        for k in ("ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"):
            pg.keyboard.press(k)
            pg.wait_for_timeout(700)
            assert _st(pg)["f"] == nid, f"{k} left the held card on a page with no children"
        pg.click("#af-exit")
        pg.wait_for_timeout(400)
        assert _st(pg)["depth"] == 0 and not any(r["out"] for r in _out(pg))
        assert pg.errors == []
    finally:
        pg.context.close()


def test_children_a_format_declares_are_in_the_branch(browser, server):
    """The horizontal timeline's nested cards (E3) set window._altoBranchKids; the branch follows it."""
    pg = _open(browser, server, "lanes")
    try:
        ids = pg.evaluate("NODE_ORDER.slice(0, 3)")
        pg.evaluate("([a, b]) => { window._altoBranchKids = id => id === a ? [b] : []; }", [ids[0], ids[1]])
        _hold(pg, ids[0])
        assert set(pg.evaluate(f"{F}.members()")) == {ids[0], ids[1]}
        assert pg.evaluate("id => window._altoShown(id)", ids[1]) and not pg.evaluate("id => window._altoShown(id)", ids[2])
    finally:
        pg.context.close()


def test_the_edit_strip_and_the_button_do_not_collide(browser, server):
    pg = _open(browser, server, "outline", init=FAKE)
    try:
        pg.click("#alto-edit-pill .aep-manual")
        pg.wait_for_selector("html.alto-editing", timeout=10000)
        pg.wait_for_timeout(500)
        _enlarge(pg, "offer")
        c = _card(pg, "offer")
        pg.mouse.move((c["l"] + c["r"]) / 2, c["t"] + 30)
        pg.wait_for_timeout(450)
        s = pg.evaluate("""() => { var e = document.querySelector('#node-offer .aed-cc'); if(!e) return null; var r = e.getBoundingClientRect(); return {l: r.left, t: r.top, r: r.right, b: r.bottom, on: getComputedStyle(e).display !== 'none'}; }""")
        b = _btn(pg)
        assert b["on"]
        if s and s["on"]:
            assert b["l"] >= s["r"] or b["r"] <= s["l"] or b["t"] >= s["b"] or b["b"] <= s["t"], f"the strip {s} and the button {b} overlap"
    finally:
        pg.context.close()


# ── a phone ──
def test_a_phone_card_gets_the_button_and_walks_only_the_branch(browser, server):
    pg = _open(browser, server, "outline", phone=True, view="card")
    try:
        pg.evaluate("featureNode('acceptance', false)")
        pg.wait_for_function("() => document.getElementById('af-btn').classList.contains('in')", timeout=6000)
        # settled, not slept on: the button has finished fading in and neither it nor the card has moved for several frames (a tap that lands
        # while the phone card is still easing into place misses the button and hits the page: 1 run in 3 on a loaded machine)
        pg.wait_for_function("""() => new Promise(done => { var el = document.getElementById('af-btn'), c = document.querySelector('#node-acceptance .node-card'), last = '', n = 0;
            (function look() { var r = el.getBoundingClientRect(), q = c.getBoundingClientRect(), k = [r.left, r.top, q.left, q.top, getComputedStyle(el).opacity].join();
              n = k === last ? n + 1 : 0; last = k; if (n >= 8 && getComputedStyle(el).opacity === '1') done(true); else requestAnimationFrame(look); })(); })""", timeout=8000)
        b, c = _btn(pg), _card(pg, "acceptance")
        assert b["on"] and b["b"] <= c["t"] + 1 and b["r"] <= 390
        bx, by = (b["l"] + b["r"]) / 2, (b["t"] + b["b"]) / 2
        pg.touchscreen.tap(bx, by)
        pg.wait_for_function(f"() => {F}.root() === 'acceptance'", timeout=4000)
        assert _st(pg)["root"] == "acceptance"
        assert pg.evaluate("window._filteredOrder()") == ["acceptance", "mirror-image", "mailbox-rule", "acceptance-by-conduct"]
        pg.evaluate("document.getElementById('nav-next-btn').click()")
        pg.wait_for_timeout(800)
        assert _st(pg)["feat"] == "mirror-image"
        pg.evaluate("featureNode('formation', false)")                       # nothing outside can be featured
        pg.wait_for_timeout(300)
        assert _st(pg)["feat"] == "mirror-image"
        assert pg.evaluate("[...document.querySelectorAll('#tlb-prev, #tlb-next')].every(e => !/Unilateral|Formation|Preliminary/.test(e.innerText))")
        ex = pg.evaluate("(() => { var r = document.getElementById('af-exit').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2, r.width, getComputedStyle(document.getElementById('af-exit')).display]; })()")
        assert ex[3] != "none" and ex[2] >= 44
        pg.touchscreen.tap(ex[0], ex[1])
        pg.wait_for_timeout(600)
        assert _st(pg)["depth"] == 0
        assert len(pg.evaluate("window._filteredOrder()")) > 10
        assert pg.errors == []
    finally:
        pg.context.close()


def test_a_phone_whole_view_holds_a_branch_too(browser, server):
    pg = _open(browser, server, "outline", phone=True, view="whole")
    try:
        _hold(pg, "acceptance")
        rows = {r["id"]: r for r in _out(pg)}
        assert {i for i, r in rows.items() if not r["out"]} == ACCEPT
        assert pg.evaluate("getComputedStyle(document.getElementById('af-exit')).display") != "none"
        pg.tap("#af-exit")
        pg.wait_for_timeout(500)
        assert _st(pg)["depth"] == 0
    finally:
        pg.context.close()


# ── Art, 2026-11-05: the Exit pill reads in every style (dark ink on the accent fill, 4.5:1) and Holographic's plates are square ──
_EXIT_INK = """() => { var lum = m => { var a = m.map(v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }); return .2126 * a[0] + .7152 * a[1] + .0722 * a[2]; };
  var rgb = c => c.match(/[\\d.]+/g).map(Number).slice(0, 3);
  var cr = (f, b) => { var x = lum(f), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
  var ex = document.getElementById('af-exit'), cs = getComputedStyle(ex), bg = rgb(cs.backgroundColor), fg = rgb(cs.color), r = {label: cr(fg, bg), radius: cs.borderTopLeftRadius,
    btn: getComputedStyle(document.getElementById('af-btn')).borderTopLeftRadius};
  ['.af-who', '.af-esc'].forEach(q => { var o = +getComputedStyle(ex.querySelector(q)).opacity; r[q] = cr(fg.map((v, i) => v * o + bg[i] * (1 - o)), bg); });
  return r; }"""


@pytest.mark.parametrize("page", ["outline", "lanes"])
@pytest.mark.parametrize("style,dark", [("classic", False), ("classic", True), ("retro", False), ("holo", False), ("holo", True)])
def test_the_exit_pill_reads_in_every_style(browser, server, page, style, dark):
    pg = _open(browser, server, page)
    try:
        if style != "classic":
            pg.evaluate(f"window._altoStyle.set('{style}')")
            pg.wait_for_timeout(900)
        if style != "retro":
            pg.evaluate(f"document.documentElement.classList.toggle('dark', {str(dark).lower()})")
            pg.wait_for_timeout(300)
        nid = "formation" if page == "outline" else pg.evaluate("document.querySelector('#world .node').id.slice(5)")
        _hold(pg, nid)
        r = pg.evaluate(_EXIT_INK)
        assert r["label"] >= 4.5, r
        assert r[".af-who"] >= 4.5 and r[".af-esc"] >= 4.5, r
        if style == "holo":
            assert r["radius"] == "0px" and r["btn"] == "0px", r
        elif style == "retro":
            assert r["radius"] == "0px" and r["btn"] == "0px", r
        else:
            assert r["radius"] != "0px" and r["btn"] != "0px", r
    finally:
        pg.context.close()
