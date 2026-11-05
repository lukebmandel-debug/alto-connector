"""A Memory Atlas country the Tour is in never paints black (Art, 2026-11-05): a country whose cards were all placed by hand under another card (the US in
the Contracts sample) had no unit colour, and `.wp-c.wp-on` mixed a colour from the unset --u, which computes to solid black on the flat map and the globe,
in every style. Now such a country takes its unit's colour like its siblings, and the focused-country fill only applies to a coloured country.

The data tests need no browser; the browser test is WebKit, served from 127.0.0.1 like test_atlas_flags.py (a page is never closed on its own and the
browser's own close is given 15 s by an alarm). Skipped without Playwright."""
import http.server
import re
import signal
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import palace_assets, palace_world, world_plan as wp  # noqa: E402
from tests.test_world_palace import built, loaded  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

HAND = {"pj": wp.resolve("France"), "pj1": wp.resolve("Texas")}     # pj1 (a floor under pj) is given the US by hand; no top card is there


def test_a_country_with_only_hand_placed_cards_takes_its_units_colour():
    b, ns, _ = loaded(world={"places": HAND})
    p = wp.plan(b, ns)
    assert p["places"]["pj1"]["c"] == "USA"
    assert p["used"].get("USA") == p["used"]["FRA"] == 0            # (pj1 hangs under pj, in unit 0)


def test_every_country_a_card_stands_in_has_a_unit_colour():
    b, ns, _ = loaded(world={"places": HAND})
    p = wp.plan(b, ns)
    assert {v["c"] for v in p["places"].values()} <= set(p["used"])


def test_the_focused_country_fill_needs_a_unit_colour():
    css = palace_world.CSS if hasattr(palace_world, "CSS") else open(ROOT / "alto/build/palace_world.py", encoding="utf-8").read()
    assert ".wp-c.wp-u.wp-on{fill:color-mix" in css and not re.search(r"\.wp-c\.wp-on\{fill:color-mix", css)


@pytest.fixture(scope="module")
def origin():
    html = built(world={"places": HAND})[0]

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            hit = (("text/html", html) if path in ("/", "/index.html") else ("text/javascript", "") if path == "/alto-cloud.js" else palace_assets.find(path))
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


BLACK = """() => [].filter.call(document.querySelectorAll('#wpal-root path.wp-c'), p => {
  var f = getComputedStyle(p).fill; return /^rgba?\\(0, 0, 0(, 1)?\\)$/.test(f) && (p.classList.contains('wp-on') || p.classList.contains('wp-u')); }).length"""


@pytest.mark.parametrize("cls", ["", "alto-retro", "alto-holo"])
@pytest.mark.parametrize("globe", [False, True])
def test_no_tour_country_renders_black(browser, origin, cls, globe):
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(origin + "/index.html")
    page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=30000)
    if cls:
        page.evaluate("c => document.documentElement.classList.add(c)", cls)
    if globe and not page.evaluate("AltoWorld.globe(true)"):
        pytest.skip("no WebGL here")
    page.evaluate("AltoWorld.select('pj1')")                       # the Tour stop in the US
    page.wait_for_timeout(1500)
    assert page.evaluate("document.querySelectorAll('#wpal-root path.wp-c.wp-on').length") >= 1
    assert page.evaluate(BLACK) == 0
    # and a focused country with no unit colour at all keeps the land colour, never black
    assert page.evaluate("""() => { var p = document.querySelector('#wpal-root path.wp-c:not(.wp-u)'); p.classList.add('wp-on');
      var f = getComputedStyle(p).fill; p.classList.remove('wp-on'); return f; }""") != "rgb(0, 0, 0)"
    assert not errors
