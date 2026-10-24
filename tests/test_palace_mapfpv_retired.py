"""The city palace's first-person view is retired (cold storage: ~/Desktop/Alto Development/_cold-storage/memory-map-fpv, git tag
cold/memory-map-fpv): a Memory Map page has no way into it and asks for none of its hosted files, even when its stored map still names
street data from before. The Memory Blueprint keeps its own first-person view (tests/test_building_fpv_*.py).
Offline; Chromium and WebKit through Playwright (skipped without them)."""
import copy
import functools
import http.server
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import palace, palace_assets  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
import test_palace as tp  # noqa: E402

RETIRED = ("/ride/", "/street/", "/tex/")


def _bundle():
    d = tp.bundle()
    m = tp.city_map()
    m["street"] = {"h": "0123456789ab"}                 # a map set up before the retirement still names its street data
    d["brief"]["palace"]["data_z"] = palace.pack({"map": m, "blocks": tp.pp.lots(m)})
    return d


@pytest.fixture(scope="module")
def html():
    page, _ = build_timeline(*load_brief(copy.deepcopy(_bundle())))
    return page


def test_the_page_carries_no_ride_and_no_street_data(html):
    assert "palace-ride-" not in html and "/street/palace-street-" not in html and "0123456789ab" not in html
    assert "_palRide.init(" not in html and "#pal-ride" not in html
    assert not set(palace_assets.folders()) & set(palace_assets.RETIRED_FOLDERS)
    assert not any(f in RETIRED for f in ("/%s/" % a[0] for a in palace_assets.ASSETS))


pw = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:                          # noqa: BLE001
            pytest.skip(f"{request.param}: {e}")
        yield b
        b.close()


@pytest.fixture(scope="module")
def site(html, tmp_path_factory):
    d = tmp_path_factory.mktemp("mapfpv-site")
    (d / "timeline.html").write_text(html, encoding="utf-8")
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(d)))
    srv.RequestHandlerClass.log_message = lambda *a: None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/timeline.html"
    srv.shutdown()


def test_a_memory_map_page_asks_for_no_ride_or_street_file_and_offers_no_first_person_view(browser, site):
    pg = browser.new_page(viewport={"width": 1400, "height": 900})
    urls = []
    pg.on("request", lambda r: urls.append(r.url))
    pg.goto(site)
    pg.wait_for_timeout(1500)
    assert pg.evaluate("document.documentElement.classList.contains('alto-palace') || !!document.querySelector('.pal-svg')")
    bad = [u for u in urls if any(f in u for f in RETIRED)]
    assert not bad, bad
    st = pg.evaluate("""() => ({ride: typeof window._palRide, street: typeof window._palStreet, layer: !!document.getElementById('pal-ride'),
        sw: !!document.querySelector('.pr-sw, .pr-tk, .pr-ex'), txt: /first-person/i.test(document.body.innerText)})""")
    assert st == {"ride": "undefined", "street": "undefined", "layer": False, "sw": False, "txt": False}
    pg.close()
