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
        page.evaluate("document.documentElement.classList.add('alto-editing')")
        _settle(page, 200)
        assert not page.evaluate("document.getElementById('wpal-root').hidden")                         # editing stays on the map (2026-10-29)
        page.evaluate("document.documentElement.classList.remove('alto-editing')")
        _settle(page, 400)
        assert not page.evaluate("document.getElementById('wpal-root').hidden")
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
