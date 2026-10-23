"""The World Palace in a real browser (Luke, 2026-10-23: "World palace is missing things that we've rolled out alto-wide. Also it should
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
        _settle(page)
        assert page.evaluate(ENL) == "erie1"                                    # Arequipa, the card under Erie
        page.evaluate("document.querySelector('#world #node-hanna .node-card').classList.add('dimmed')")      # a filter hides Hanna
        _settle(page, 300)
        assert page.evaluate("document.querySelector('#wpal-root .wp-pin.wp-dim') !== null")
        page.evaluate("AltoWorld.select('erie1')")
        _settle(page)
        page.keyboard.press("ArrowRight")
        _settle(page)
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
        assert page.evaluate("document.getElementById('wpal-root').hidden")
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
