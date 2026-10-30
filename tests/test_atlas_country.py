"""A Memory Atlas of one country (Art's sheet, "World or a country"; brief.world.country): its states are the places, each top card on a
state's capital, the cards under it on that state's largest cities; the page frames the country, its button and crumb are the country,
the rest of the world fades. A brief without it is the world map, unchanged. The page in Chromium and WebKit."""
import http.server
import threading

import pytest

from alto.build import palace_assets, world_plan as wp
from tests.test_world_palace import built, data_of, loaded
from tests.test_world_palace_render import browser  # noqa: F401


def test_one_country_plans_states_and_their_cities():
    b, ns, _ = loaded(world={"country": "USA"})
    p = wp.plan(b, ns)
    assert p["used"] == {"USA": 0} and p["multi"] == ["USA"] and p["country"] == "USA"
    tops = [t for u in p["units"] for t in u["tops"]]
    assert all(p["places"][t]["c"] == "USA" and p["places"][t]["k"] == "sub" for t in tops)
    assert len({p["places"][t]["label"] for t in tops}) == len(tops)                 # one state each
    assert p["places"]["pj1"]["k"] == "city"
    assert wp.plan(*loaded(world={"country": "USA"})[:2]) == p                        # deterministic
    with pytest.raises(ValueError):
        wp.validate({"country": "XXX"})
    assert "scope" not in data_of(built()[0]) and data_of(built(world={"country": "USA"})[0])["scope"] == "USA"


@pytest.fixture(scope="module")
def origin():
    html = built(world={"country": "USA"})[0]

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


def test_the_page_frames_the_country(browser, origin):  # noqa: F811
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        page.goto(origin + "/index.html")
        page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
        page.wait_for_timeout(600)
        assert page.evaluate("AltoWorld.view().k / AltoWorld.view().kW") > 2                       # the country, not the world
        assert "United States" in page.evaluate("document.querySelector('#wpal-root .wp-ctl').textContent")
        assert page.evaluate("document.querySelector('#wpal-root .wp-nav .wp-at').textContent") == "United States"
        assert page.evaluate("document.getElementById('wpal-root').classList.contains('wp-one')")
        page.evaluate("AltoWorld.select('pj')")
        page.wait_for_timeout(1800)
        page.evaluate("AltoWorld.world()")
        page.wait_for_timeout(1500)
        assert page.evaluate("AltoWorld.view().k / AltoWorld.view().kW") > 2                       # home is the country
        assert not errors, errors
    finally:
        page.close()
