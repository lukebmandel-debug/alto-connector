"""The Memory Atlas globe draws the map's zoomed-in detail (Luke, 2026-11-04: "I'm not happy with the quality level of the map in memory atlas globe
version. Its clearly higher quality geography/borders in flat map"; F2): zoomed in as far as the flat map swaps in a continent at 1:50m and a country's
state lines, the globe fetches the same hosted tiers and draws them sharp (a ring that runs round the back is cut at the limb, not left to the blurry
surface); at the whole globe nothing extra is fetched; the flat map is as it was; turning and zooming stay cheap.

WebKit only (headless WebGL), served from 127.0.0.1 like test_atlas_flags.py (a WebKit page.close() can hang at teardown, so a page is never closed on its
own and the browser's own close is given 15 s by an alarm). Skipped without Playwright."""
import http.server
import math
import signal
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import palace_assets, world_plan as wp  # noqa: E402
from alto.build.world_geo import project  # noqa: E402
from tests.test_world_palace import built  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

PAN = """([x, y]) => { var r = document.getElementById('wpal-root'), v = AltoWorld.view();
  r.dispatchEvent(new WheelEvent('wheel', {bubbles: true, cancelable: true, deltaX: (x - v.cx) * v.k, deltaY: (y - v.cy) * v.k, clientX: 640, clientY: 400})); }"""
ZOOM = """(dy) => document.getElementById('wpal-root').dispatchEvent(new WheelEvent('wheel',
  {bubbles: true, cancelable: true, ctrlKey: true, deltaY: dy, clientX: 640, clientY: 400}))"""
LAND = "[].reduce.call(document.querySelectorAll('#wpal-root path.wp-c'), (n, p) => n + (p.getAttribute('d') || '').length, 0)"
STATES = "document.querySelectorAll('#wpal-root path.wp-a1').length"


@pytest.fixture(scope="module")
def origin():
    html = built(world={"places": {"erie": wp.resolve("Oregon"), "hanna": wp.resolve("Texas"), "byrd": wp.resolve("France")}})[0]
    log = []

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            log.append(path)
            hit = (("text/html", html) if path in ("/", "/index.html") else ("text/javascript", "") if path == "/alto-cloud.js" else palace_assets.find(path))
            body = (hit[1] if hit else "no").encode("utf-8")
            self.send_response(200 if hit else 404)
            self.send_header("Content-Type", hit[0] if hit else "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", log
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    if pw is None:
        pytest.skip("Playwright is not installed")
    p = pw.sync_playwright().start()
    try:
        b = p.webkit.launch()
    except Exception as e:
        p.stop()
        pytest.skip(f"no webkit: {e}")
    yield b
    signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError("browser close hung")))
    signal.alarm(15)
    try:
        b.close()
        p.stop()
    except Exception:
        pass
    finally:
        signal.alarm(0)


def _open(browser, origin, globe=True):
    url, log = origin
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(url + "/index.html")
    page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=30000)
    if globe and not page.evaluate("AltoWorld.globe(true)"):
        pytest.skip("no WebGL here")
    page.wait_for_timeout(900)
    del log[:]
    return page, errors, log


def _go(page, lon, lat, rel):
    """Pan to (lon, lat) and zoom to `rel` times the view it opened at, as a reader's wheel does."""
    page.evaluate(PAN, list(project(lon, lat)))
    page.wait_for_timeout(100)
    for _ in range(60):
        k, k0 = page.evaluate("AltoWorld.view().k"), _go.k0
        if abs(k / (k0 * rel) - 1) < .03:
            break
        page.evaluate(ZOOM, -math.log(min(max(k0 * rel / k, 1 / 1.3), 1.3)) * 100)
        page.wait_for_timeout(20)
    page.wait_for_timeout(2200)


def _tiles(log):
    return sorted({p.rsplit("/", 1)[1] for p in log if "/world/cont-" in p or "/world/a1-" in p})


def test_the_whole_globe_fetches_no_detail(browser, origin):
    page, errors, log = _open(browser, origin)
    _go.k0 = page.evaluate("AltoWorld.view().k")
    page.evaluate(ZOOM, 0)                                      # (a settle, nothing moved)
    page.wait_for_timeout(1200)
    assert page.evaluate("AltoWorld.globe()") and not _tiles(log), _tiles(log)
    assert page.evaluate("AltoWorld.view().g") is None          # (the sharp land is not even on yet)
    _go(page, 0, 20, 1.5)                                       # a little in, the surface still does it
    assert not _tiles(log), _tiles(log)
    assert not errors, errors


def test_close_in_the_globe_loads_the_continent_and_the_state_lines_and_draws_more(browser, origin):
    page, errors, log = _open(browser, origin)
    _go.k0 = page.evaluate("AltoWorld.view().k")
    land0, states0 = page.evaluate(LAND), page.evaluate(STATES)
    page.route("**/world/cont-*", lambda r: r.abort())
    page.route("**/world/a1-*", lambda r: r.abort())
    _go(page, -100, 40, 5)                                      # the USA close: the tiers are asked for, and (held back here) the base rings draw
    held = page.evaluate("AltoWorld.view().g")
    assert held and held[0] > 3 and held[1] > 50, held
    assert any(t.startswith("cont-north-america") for t in _tiles(log)) and any(t.startswith("a1-USA") for t in _tiles(log)), _tiles(log)
    page.unroute("**/world/cont-*")
    page.unroute("**/world/a1-*")
    page.evaluate(ZOOM, 1)                                      # (a nudge: the page asks again once the view settles)
    page.wait_for_timeout(2500)
    grown = page.evaluate("AltoWorld.view().g")
    assert grown[1] > held[1] * 1.5, (held, grown)              # more points, from the 1:50m rings and the state lines
    assert page.evaluate(LAND) > land0 and page.evaluate(STATES) > states0 >= 0
    pixels = page.evaluate("""() => { var c = document.querySelector('#wpal-root canvas.wp-globe.v'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data, n = 0;
      for (var i = 3; i < d.length; i += 16) if (d[i]) n++; return n; }""")
    assert pixels > 2000                                        # (and the land is on the canvas)
    assert not errors, errors


def test_a_continent_that_runs_round_the_back_is_drawn_not_left_to_the_surface(browser, origin):
    page, errors, log = _open(browser, origin)
    _go.k0 = page.evaluate("AltoWorld.view().k")
    _go(page, 105, 35, 2.6)                                     # Asia filling the screen, its ring well round the limb
    assert any(t.startswith("cont-asia") for t in _tiles(log)), _tiles(log)
    ringed = page.evaluate("AltoWorld.view().g")
    assert ringed[0] >= 5 and ringed[1] > 300, ringed
    assert not errors, errors


def test_the_flat_map_still_loads_its_own_detail_and_the_switch_works(browser, origin):
    page, errors, log = _open(browser, origin, globe=False)
    assert not page.evaluate("AltoWorld.globe()")
    k0 = page.evaluate("AltoWorld.view().k")
    land0 = page.evaluate(LAND)
    page.evaluate(PAN, list(project(-100, 40)))
    for _ in range(40):
        if page.evaluate("AltoWorld.view().k") >= k0 * 4.5:
            break
        page.evaluate(ZOOM, -26)
        page.wait_for_timeout(20)
    page.wait_for_timeout(2500)
    assert any(t.startswith("cont-north-america") for t in _tiles(log)) and any(t.startswith("a1-USA") for t in _tiles(log)), _tiles(log)
    assert page.evaluate(LAND) > land0 and page.evaluate(STATES) > 0
    assert page.evaluate("AltoWorld.view().g") is None          # (the flat map has no globe canvas to count)
    assert page.evaluate("AltoWorld.globe(true)")               # flat -> globe at this zoom: the detail already in is drawn
    page.wait_for_timeout(1500)
    assert page.evaluate("AltoWorld.view().g")[1] > 300
    assert not page.evaluate("AltoWorld.globe(false)")
    page.wait_for_timeout(600)
    assert page.evaluate("document.querySelectorAll('#wpal-root path.wp-c').length") > 150
    assert not errors, errors


def test_turning_the_globe_close_in_stays_cheap(browser, origin):
    page, errors, log = _open(browser, origin)
    _go.k0 = page.evaluate("AltoWorld.view().k")
    _go(page, -100, 40, 5)
    r = page.evaluate("""async () => { var root = document.getElementById('wpal-root'), fr = [], js = [], last = performance.now();
      for (var i = 0; i < 70; i++) { await new Promise(f => requestAnimationFrame(f)); var t = performance.now(); fr.push(t - last); last = t;
        root.dispatchEvent(new WheelEvent('wheel', {bubbles: true, cancelable: true, deltaX: 6, clientX: 640, clientY: 400})); js.push(performance.now() - t); }
      fr = fr.slice(3).sort((a, b) => a - b); js = js.slice(3).sort((a, b) => a - b); return {frame: fr[fr.length >> 1], js: js[js.length >> 1]}; }""")
    assert r["js"] < 30 and r["frame"] < 80, r                    # (generous: a loaded Mac; the measured medians are a fraction of this)
    assert not errors, errors
