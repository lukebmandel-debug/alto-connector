"""The Memory Atlas in a real browser (Luke, 2026-10-23: "World palace is missing things that we've rolled out alto-wide. Also it should
still have the ability to enlarge nodes"): a pin enlarges the timeline's own card where it stands and gives it back, the arrow keys hop
card by card past the ones a filter hides, a search hit and the engine's own enlarging reach the map, and a card's page or editing by hand
puts the map aside.

Skipped without Playwright (the repo venv has none; see the 1.9.62 notes). Served from 127.0.0.1 (the page and /world/<renderer + map>):
WebKit's page.route misses the renderer's synchronous load, so a fake origin would leave the map unmounted there. Chromium and WebKit."""
import http.server
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import palace_assets, world_plan as wp  # noqa: E402
from tests.test_world_palace import built  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

ENL = "(() => { var e = document.querySelector('#wpal-root .wp-enl'); return e && e.getAttribute('data-id'); })()"


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch() if request.param == "webkit" else p.chromium.launch()
        except Exception as e:
            try:
                if request.param == "webkit":
                    raise
                b = p.chromium.launch(channel="chrome")
            except Exception:
                pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


@pytest.fixture(scope="module")
def html():
    return built(world={"places": {"erie": wp.resolve("Peru")}})[0]


@pytest.fixture(scope="module")
def origin(html):
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            hit = (("text/html", html) if path in ("/", "/index.html") else ("text/javascript", "") if path == "/alto-cloud.js"
                   else palace_assets.find(path))
            body = (hit[1] if hit else "no").encode("utf-8")
            self.send_response(200 if hit else 404)
            self.send_header("Content-Type", hit[0] if hit else "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _open(browser, origin):
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(origin + "/index.html")
    page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
    return page, errors


def _settle(page, ms=1700):
    page.wait_for_timeout(ms)


def test_a_card_is_enlarged_where_it_stands_and_given_back(browser, origin):
    page, errors = _open(browser, origin)
    try:
        page.evaluate("AltoWorld.select('erie')")
        _settle(page)
        assert page.evaluate(ENL) == "erie"
        # the timeline's own card, borrowed from the board: its title and its page with it
        assert page.evaluate("!!document.querySelector('#wpal-root .wp-enl #node-erie .node-title') && !document.querySelector('#world #node-erie')")
        assert "Peru" in page.evaluate("document.querySelector('#wpal-root .wp-tour .c').textContent")
        page.keyboard.press("Escape")
        _settle(page, 400)
        assert page.evaluate(ENL) is None and page.evaluate("!!document.querySelector('#world #node-erie')")
        assert not errors
    finally:
        page.close()


def test_the_arrows_hop_card_by_card_past_a_filtered_card(browser, origin):
    page, errors = _open(browser, origin)
    try:
        page.evaluate("AltoWorld.select('erie')")
        _settle(page)
        page.keyboard.press("ArrowRight")
        _settle(page, 2800)                                                     # (a Tour leg may fly the paper plane: ~2.4 s)
        assert page.evaluate(ENL) == "erie1"                                    # Arequipa, the card under Erie
        page.evaluate("document.querySelector('#world #node-hanna .node-card').classList.add('dimmed')")      # a filter hides Hanna
        _settle(page, 300)
        assert page.evaluate("document.querySelector('#wpal-root .wp-pin.wp-dim') !== null")
        page.evaluate("AltoWorld.select('erie1')")
        _settle(page)
        page.keyboard.press("ArrowRight")
        _settle(page, 2800)
        assert page.evaluate(ENL) == "byrd"
        assert not errors
    finally:
        page.close()


def test_the_engine_reaches_the_map_and_a_page_puts_it_aside(browser, origin):
    page, errors = _open(browser, origin)
    try:
        page.evaluate("document.querySelector('#world #node-hanna').classList.add('search-flash')")          # a search hit
        _settle(page)
        assert page.evaluate(ENL) == "hanna"
        page.evaluate("document.documentElement.classList.add('detail-open')")
        _settle(page, 200)
        assert page.evaluate("getComputedStyle(document.getElementById('wpal-root')).visibility") == "hidden"
        assert page.evaluate("!!document.querySelector('#world #node-hanna')")                               # its card back on the board
        page.evaluate("document.documentElement.classList.remove('detail-open')")
        _settle(page, 400)
        assert page.evaluate(ENL) == "hanna"                                                                 # and back on the map after
        page.evaluate("document.documentElement.classList.add('alto-editing')")                              # editing by hand stays on the map (Luke, 2026-10-29)
        _settle(page, 400)
        assert not page.evaluate("document.getElementById('wpal-root').hidden")
        assert page.evaluate(ENL) == "hanna"                                                                 # the card is still enlarged on it
        page.evaluate("document.documentElement.classList.add('detail-open')")                               # ...and a page still puts the map aside while editing
        _settle(page, 200)
        assert page.evaluate("getComputedStyle(document.getElementById('wpal-root')).visibility") == "hidden"
        page.evaluate("document.documentElement.classList.remove('detail-open')")
        _settle(page, 400)
        assert page.evaluate(ENL) == "hanna"
        page.evaluate("document.documentElement.classList.remove('alto-editing')")
        _settle(page, 400)
        assert not page.evaluate("document.getElementById('wpal-root').hidden") and page.evaluate(ENL) == "hanna"
        assert not errors
    finally:
        page.close()


def test_the_key_is_alto_s_floating_toggle_and_a_link_rides_to_its_card(browser, origin):
    page, errors = _open(browser, origin)
    try:
        page.click("#key-toggle")
        assert page.evaluate("document.querySelectorAll('.key-pop.wk.open button.u').length") == 2
        page.click(".key-pop.wk button.u >> nth=1")
        _settle(page)
        assert page.evaluate("document.querySelector('#wpal-root .wp-c.wp-on') === null")      # a unit, not a country, is shown
        page.evaluate("document.getElementById('key-toggle').click()")
        # a link (one of the cards' cross links) drawn from the enlarged card; a click on it flies to the card at its end
        page.evaluate("CONNECTIONS.push(['erie', 'gj', 'lim'])")
        page.evaluate("AltoWorld.select('erie')")
        _settle(page)
        at = page.evaluate("""(() => { var e = document.querySelector('#wpal-root .wp-relh[data-to="gj"]'); if (!e) return null;
            var L = e.getTotalLength(), m = e.getScreenCTM();
            for (var t = .3; t < .97; t += .05) { var q = e.getPointAtLength(L * t), x = q.x*m.a + q.y*m.c + m.e, y = q.x*m.b + q.y*m.d + m.f;
              if (document.elementFromPoint(x, y) === e) return [x, y]; }                         // (where no card or pin lies over it)
            return null; })()""")
        assert at, "no link drawn"
        page.mouse.click(at[0], at[1])
        _settle(page)
        assert page.evaluate(ENL) == "gj"
        assert not errors
    finally:
        page.close()


VIEW = "AltoWorld.view()"
BAR = "!document.querySelector('#wpal-root .wp-tour').hidden"


def test_the_tour_switch_turns_off_and_the_map_roams_free_then_on_again(browser, origin):
    # Luke, 2026-10-26: "it seems i can't turn tour mode off and freely go around the world"
    page, errors = _open(browser, origin)
    try:
        _settle(page, 600)
        assert page.evaluate("AltoWorld.tourMode()") is True and page.evaluate(BAR)          # on: as before, its bar ready to start
        page.evaluate("AltoWorld.select('erie')")
        _settle(page)
        assert page.evaluate(BAR) and page.evaluate(ENL) == "erie"
        page.click("#wpal-root .wp-tour .x")                                                    # the bar's ✕ ends the Tour
        _settle(page, 500)
        assert page.evaluate("AltoWorld.tourMode()") is False
        assert not page.evaluate(BAR) and page.evaluate(ENL) is None
        assert not page.evaluate("document.getElementById('wpal-root').classList.contains('wp-focus')")      # nothing left dimmed
        assert page.evaluate("document.querySelector('#wpal-root .wp-tt').getAttribute('aria-pressed')") == "false"
        # free: a drag (from a pin too), the arrow keys, the zoom keys, and the map stays where it is put
        v0 = page.evaluate(VIEW)
        pin = page.evaluate("""(() => { var ps = document.querySelectorAll('#wpal-root .wp-pin');       // a pin in sight, nothing over it
            for (var i = 0; i < ps.length; i++) { var r = ps[i].getBoundingClientRect(), x = r.x + r.width/2, y = r.y + r.height/2;
              if (x > 40 && x < innerWidth - 320 && y > 120 && y < innerHeight - 160 && ps[i].contains(document.elementFromPoint(x, y))) return [x, y]; }
            return null; })()""")
        assert pin, "no pin in sight"
        page.mouse.move(*pin)
        page.mouse.down()
        page.mouse.move(pin[0] + 260, pin[1] + 90, steps=8)
        page.mouse.up()
        _settle(page, 400)
        v1 = page.evaluate(VIEW)
        assert v1["cx"] < v0["cx"] - 20 and page.evaluate(ENL) is None                         # panned, and the pin was not opened
        page.keyboard.press("ArrowRight")
        page.keyboard.press("ArrowDown")
        _settle(page, 300)
        v2 = page.evaluate(VIEW)
        assert v2["cx"] > v1["cx"] and v2["cy"] > v1["cy"] and page.evaluate(ENL) is None      # the arrows pan, not hop
        page.keyboard.press("-")
        _settle(page, 1500)
        v3 = page.evaluate(VIEW)
        assert v3["k"] < v2["k"] and abs(v3["cx"] - v2["cx"]) < 1e-6 and abs(v3["cy"] - v2["cy"]) < 1e-6        # no snapping back
        # remembered on this device; on again, the Tour starts
        page.reload()
        page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
        _settle(page, 600)
        assert page.evaluate("AltoWorld.tourMode()") is False and not page.evaluate(BAR)
        page.click("#wpal-root .wp-tt")
        _settle(page)
        assert page.evaluate("AltoWorld.tourMode()") is True and page.evaluate(BAR) and page.evaluate(ENL) is not None
        assert "Tour 1 /" in page.evaluate("document.querySelector('#wpal-root .wp-tour .c').textContent")
        assert not errors
    finally:
        page.close()


def test_a_card_says_where_it_stands_enlarged_and_on_its_page(browser, origin):
    page, errors = _open(browser, origin)
    try:
        where = "[].map.call(document.querySelectorAll('#wpal-root .wp-enl .wp-where'), function(e){ return e.textContent; })"
        page.evaluate("AltoWorld.select('erie')")
        _settle(page)
        assert page.evaluate(where) == ["Peru"]                                                 # a country's own card: the country
        page.evaluate("AltoWorld.select('erie1')")
        _settle(page)
        assert page.evaluate(where) == ["Arequipa, Peru"]                                       # a card on a city: city, country
        page.evaluate("showDetail('node', 'erie1')")
        _settle(page, 400)
        assert page.evaluate("document.querySelector('#detail-content .detail-role + .wp-where-d').textContent") == "Arequipa, Peru"
        page.evaluate("showDetail('node', 'erie')")                                             # the engine writes each page afresh
        _settle(page, 400)
        assert page.evaluate("document.querySelectorAll('#detail-content .wp-where-d').length") == 1
        assert page.evaluate("document.querySelector('#detail-content .wp-where-d').textContent") == "Peru"
        assert not errors
    finally:
        page.close()


@pytest.mark.parametrize("tour", [True, False])
def test_a_zoom_in_holds_where_the_reader_leaves_it(browser, origin, tour):
    # Luke, 2026-10-26: "it keeps bouncing back when i try to zoom in, regardless of whether tour is on or not" — the engine's focus mode
    # heard the pinch too and enlarged the card nearest it, and the map flew to that card
    page, errors = _open(browser, origin)
    try:
        _settle(page, 600)
        page.evaluate(f"AltoWorld.tourMode({'true' if tour else 'false'})")
        _settle(page, 300)
        k = lambda: page.evaluate("AltoWorld.view().k")
        held = lambda: page.evaluate("[AltoWorld.view().k, AltoWorld.view().cx, AltoWorld.view().cy]")
        for how in ("gesture", "wheel", "button"):
            k0 = k()
            if how == "gesture":                                                                  # Safari's trackpad pinch
                page.evaluate("""(() => { var r = document.getElementById('wpal-root');
                    function g(t, s) { var e = new Event(t, {bubbles: true, cancelable: true}); e.scale = s; e.clientX = 640; e.clientY = 380; r.dispatchEvent(e); }
                    g('gesturestart', 1); [1.1, 1.3, 1.6].forEach(function (s) { g('gesturechange', s); }); g('gestureend', 1.6); })()""")
            elif how == "wheel":                                                                  # Chrome's: ctrl + wheel
                page.mouse.move(640, 380)
                page.keyboard.down("Control")
                for _ in range(6):
                    page.mouse.wheel(0, -25)
                page.keyboard.up("Control")
            else:
                page.click("#wpal-root .wp-ctl button[aria-label='Zoom in']")
            _settle(page, 200)
            v = held()
            assert v[0] > k0 * 1.15, how
            _settle(page, 2000)
            assert held() == v, how                                                               # no bounce back, no fly to a card
            assert page.evaluate(ENL) is None and not page.evaluate("window._focusedNodeId"), how
        # the engine enlarging a card for any other reason still reaches the map
        page.evaluate("document.querySelector('#world #node-hanna').classList.add('focused')")
        _settle(page)
        assert page.evaluate(ENL) == "hanna"
        assert not errors
    finally:
        page.close()


@pytest.mark.parametrize("size", [(1440, 900, False), (900, 1200, False), (390, 664, True), (750, 342, True)])
def test_the_world_opens_centred(browser, origin, size):
    # Luke, 2026-10-26: "have the map centered when opening from homepage" — the engine scales the page (CSS zoom on <html>) and the map
    # had measured itself in the window's px, so its fit sat to one side; a phone on its side also got a desktop's margins
    w, hgt, phone = size
    ua = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
          if phone else None)
    ctx = browser.new_context(viewport={"width": w, "height": hgt}, **({"user_agent": ua, "has_touch": True} if phone else {}))
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        page.goto(origin + "/index.html")
        page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
        _settle(page, 900)
        r = page.evaluate("""(() => { var s = document.querySelector('#wpal-root .wp-sphere').getBoundingClientRect(),
            m = document.getElementById('wpal-root').getBoundingClientRect();
            return [(s.left + s.right) / 2 - (m.left + m.right) / 2, (s.top + s.bottom) / 2 - (m.top + m.bottom) / 2,
                    Math.max(s.width / m.width, s.height / m.height)]; })()""")
        assert abs(r[0]) <= 2 and abs(r[1]) <= 2, r                                             # the world's middle is the map's middle
        assert r[2] > .7, r                                                                     # and it fills the map's width or height
        assert page.evaluate("!document.querySelector('.wk:not(.key-pop)') || !!document.querySelector('.key-pop.wk')")    # no stray key
        assert not [e for e in errors if "ResizeObserver loop" not in e]                        # (WebKit's notice for the engine's card observer)
    finally:
        ctx.close()


@pytest.mark.parametrize("size", [(750, 342, 0), (874, 292, 62), (812, 250, 48)])
def test_the_world_on_a_phone_on_its_side_is_centred_below_the_header_row(browser, origin, size):
    # 11 Nov (5-C's F5 + #19 merged): the first F5 fit put the world in the box between the header row and the Tour bar, 7 px off the map's middle and 0.669 of a 750 x 342
    # map's height. It is the map's middle again, its top below the 44 pt row, its sides clear of the island's insets (the shell's --sh-left / --sh-right).
    w, hgt, isl = size
    ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ctx = browser.new_context(viewport={"width": w, "height": hgt}, user_agent=ua, has_touch=True)
    if isl:
        ctx.add_init_script("document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');"
                            "s.textContent='#sh-probe{padding-left:%dpx!important;padding-right:%dpx!important}';document.head.appendChild(s);});" % (isl, isl))
    page = ctx.new_page()
    try:
        page.goto(origin + "/index.html")
        page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
        _settle(page, 1500)
        r = page.evaluate("""(() => { var s = document.querySelector('#wpal-root .wp-sphere').getBoundingClientRect(), m = document.getElementById('wpal-root').getBoundingClientRect(),
            n = document.getElementById('nav').getBoundingClientRect(), L = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--sh-left')) || 0;
            return {dx: (s.left + s.right) / 2 - (m.left + m.right) / 2, dy: (s.top + s.bottom) / 2 - (m.top + m.bottom) / 2, top: s.top, left: s.left, right: m.right - s.right,
                    nav: Math.max(n.bottom, 44), isl: L, fill: s.height / m.height}; })()""")
        assert abs(r["dx"]) <= 2 and abs(r["dy"]) <= 2, r
        assert r["top"] >= r["nav"] + 4, r                                                      # nothing of the world under the header row
        assert r["isl"] == isl and r["left"] >= isl + 12 and r["right"] >= isl + 12, r          # nor under the island
        assert r["fill"] > (.7 if hgt >= 342 else .55), r
    finally:
        ctx.close()


@pytest.mark.parametrize("vp,mobile", [({"width": 1440, "height": 900}, False), ({"width": 390, "height": 844}, True)], ids=["d1440", "p390"])
@pytest.mark.parametrize("style", ["classic", "dark", "retro", "holo"])
def test_the_world_dropdown_pill_is_gone_and_the_bottom_chip_still_navigates(browser, origin, vp, mobile, style):
    """Luke 18 Nov (L-1118-WORLDTOG): no 'World' dropdown pill under the title, on desktop or phone, in any style. The pill held no region list (it only
    opened the homepage scope set-up), so the bottom 'Whole world' chip and its arrows are the whole of region navigation, and must keep working."""
    ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
    cx = browser.new_context(viewport=vp, **({"is_mobile": True, "has_touch": True, "user_agent": ua} if mobile else {}))      # (a phone is built as one at load: its MENU drawer exists then)
    page = cx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        page.goto(origin + "/index.html")
        page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
        cls = {"classic": "", "dark": "dark", "retro": "alto-retro", "holo": "alto-holo"}[style]
        page.evaluate("(c) => { if (c) document.documentElement.classList.add(c); }", cls)
        _settle(page, 500)
        assert page.evaluate("document.querySelectorAll('#wpal-root .wp-scope').length") == 0
        assert page.evaluate("[...document.querySelectorAll('#wpal-root button')].filter(b => /^\\s*World\\s*$/.test(b.textContent) && b.getAttribute('aria-haspopup')).length") == 0
        page.evaluate("document.title = 'Civ Pro'; window.__go = null; window.__altoGo = function(u){ window.__go = u; }")
        if mobile:
            # a phone has no chip (its nav bar is hidden): the entry is one row in the page's own MENU drawer, >= 44 px, same action
            page.evaluate("window.openNavDrawer()")
            row = "#nav-drawer-body #drawer-changemap-btn"
            assert page.evaluate(f"document.querySelector('{row}').textContent.trim()") == "Change map…"
            assert page.evaluate(f"document.querySelector('{row}').getBoundingClientRect().height") >= 44
            page.evaluate(f"document.querySelector('{row}').click()")
        else:
            at = "#wpal-root .wp-nav .wp-at"
            assert "Whole world" in page.evaluate(f"document.querySelector('{at}').textContent")
            page.evaluate("AltoWorld.select('erie')")
            _settle(page, 1700)
            assert "Whole world" not in page.evaluate(f"document.querySelector('{at}').textContent")      # the chip names where the map now is
            for _ in range(6):                                                                             # the arrow back up reaches the whole world again (bounded)
                if "Whole world" in page.evaluate(f"document.querySelector('{at}').textContent"):
                    break
                page.evaluate("document.querySelector('#wpal-root .wp-nav .wp-up').click()")
                _settle(page, 900)
            assert "Whole world" in page.evaluate(f"document.querySelector('{at}').textContent")
            # the scope set-up lives in the chip's open state: one 'Change map…' row, >= 44 px, reachable by keyboard
            page.evaluate(f"document.querySelector('{at}').click()")
            assert page.evaluate("!document.querySelector('#wpal-root .wp-mapm').hidden")
            row = "#wpal-root .wp-mapm button"
            assert page.evaluate(f"document.querySelector('{row}').textContent") == "Change map…"
            assert page.evaluate(f"parseFloat(getComputedStyle(document.querySelector('{row}')).minHeight)") >= 44      # (css px: the desktop page is zoomed a little under 1, so the box measures less)
            assert page.evaluate(f"document.activeElement === document.querySelector('{row}')")            # keyboard: focus lands on the row
            page.keyboard.press("Escape")
            assert page.evaluate("document.querySelector('#wpal-root .wp-mapm').hidden")
            page.evaluate(f"document.querySelector('{at}').click()")
            page.evaluate(f"document.querySelector('{row}').click()")
        assert page.evaluate("window.__go") == "index.html?rescope=world&tl=Civ%20Pro"                    # the same URL the pill opened
        assert "&amp;" not in page.evaluate("window.__go")                                               # a real '&', never the literal entity the homepage cannot read
        assert page.evaluate("(() => { var q = new URL(window.__go, location.href).searchParams; return [q.get('rescope'), q.get('tl')]; })()") == ["world", "Civ Pro"]
        assert not errors, errors
    finally:
        cx.close()


@pytest.mark.parametrize("style", ["classic", "classic-dark", "retro", "holo"])
def test_the_phone_menu_drawer_has_no_map_text_through_it(browser, origin, style):
    """Luke/CEO 2026-11-18 (p390): the MENU drawer was see-through, so the map's labels read through its tiles. Opaque in every style: every page text
    under the drawer is covered by the drawer itself (elementFromPoint lands inside it)."""
    ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
    cx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, user_agent=ua)
    page = cx.new_page()
    try:
        page.goto(origin + "/index.html")
        page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
        if style in ("retro", "holo"):
            page.evaluate("(s) => (window._altoStyle || window._altoStyleC).set(s)", style)
            page.reload()
            page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
            page.wait_for_timeout(2000)
        elif style == "classic-dark":
            page.evaluate("document.documentElement.classList.add('dark')")
        page.evaluate("window.openNavDrawer()")
        page.wait_for_timeout(800)
        r = page.evaluate("""() => { var d = document.getElementById('nav-drawer'), dr = d.getBoundingClientRect(), bad = [], n0 = 0;
          var w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
          while (w.nextNode()) { var n = w.currentNode, e = n.parentElement; if (!e || !n.nodeValue.trim() || e.closest('#nav-drawer')) continue;
            var rg = document.createRange(); rg.selectNodeContents(n); [...rg.getClientRects()].forEach(q => {
              if (q.width < 2 || q.height < 2 || q.right < dr.left || q.left > dr.right || q.bottom < dr.top || q.top > dr.bottom) return; n0++;
              var cx = Math.min(Math.max((q.left + q.right) / 2, dr.left + 1), dr.right - 1), cy = Math.min(Math.max((q.top + q.bottom) / 2, dr.top + 1), dr.bottom - 1);
              var hit = document.elementFromPoint(cx, cy); if (!hit || !hit.closest('#nav-drawer')) bad.push(n.nodeValue.trim().slice(0, 30)); }); }
          var bg = getComputedStyle(d).backgroundColor, al = (bg.match(/rgba\(.*,\s*([\d.]+)\)$/) || [0, 1])[1];
          return {alpha: parseFloat(al), bad: bad, under: n0}; }""")
        assert r["alpha"] >= .95 and r["bad"] == [], r
    finally:
        cx.close()
