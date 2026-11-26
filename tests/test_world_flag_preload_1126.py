"""The Memory Atlas's flag fill and card place (Luke 2026-11-26: "flag didn't load in france, recurring issue. Also try to not have nodes block the
countries generally"). A card's country flag (and the next Tour stops') is fetched the moment the card is chosen, not when the camera has rested, so
the Tour's fill never waits on the network (a slow first visit); the fill waits again if the camera moves when its wait ends; the place's own card
stands where it covers the least of its own country. Real WebKit and Chromium, a server that makes every flag file take 600 ms; skipped without Playwright."""
import http.server
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import palace_assets, world_plan as wp  # noqa: E402
from tests.test_world_palace import built  # noqa: E402
from tests.test_world_palace_render import browser  # noqa: E402,F401

LOG = []


@pytest.fixture(scope="module")
def origin():
    html = built(world={"places": {"erie": wp.resolve("France"), "hanna": wp.resolve("Peru")}})[0]

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            if "/flag-" in path:
                LOG.append((path.split("/")[-1][:8], time.time()))
                time.sleep(.6)
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


SIZES = {"d1440": dict(viewport={"width": 1440, "height": 900}),
         "p390": dict(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True, has_touch=True),
         "l844": dict(viewport={"width": 844, "height": 390}, device_scale_factor=3, is_mobile=True, has_touch=True)}


@pytest.mark.parametrize("name", list(SIZES))
def test_the_flag_is_fetched_when_the_card_is_chosen_and_the_fill_comes(browser, origin, name):
    LOG.clear()
    cx = browser.new_context(**SIZES[name])
    pg = cx.new_page()
    try:
        pg.goto(origin + "/index.html")
        pg.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=30000)
        pg.evaluate("AltoWorld.tourMode(true)")
        t0 = time.time()
        pg.evaluate("AltoWorld.select('erie',{})")
        pg.wait_for_timeout(350)
        asked = {n: t - t0 for n, t in LOG}
        assert "flag-FRA" in asked and asked["flag-FRA"] < .3, asked                  # (before the camera has rested)
        assert len(asked) >= 2, asked                                                 # (and the next stops' flags with it)
        pg.wait_for_timeout(4500)
        assert pg.evaluate("!!document.querySelector('#wpal-root .wp-ff.on')")
    finally:
        cx.close()
