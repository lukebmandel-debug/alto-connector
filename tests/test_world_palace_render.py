"""The World Palace in a real browser (Luke, 2026-10-23: "World palace is missing things that we've rolled out alto-wide. Also it should
still have the ability to enlarge nodes"): a pin enlarges the timeline's own card where it stands and gives it back, the arrow keys hop
card by card past the ones a filter hides, a search hit and the engine's own enlarging reach the map, and a card's page or editing by hand
puts the map aside.

Skipped without Playwright (the repo venv has none; see the 1.9.62 notes). Served from a fake origin: the page and /world/<renderer + map>."""
import sys
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

ORIGIN = "http://alto.test"
ENL = "(() => { var e = document.querySelector('#wpal-root .wp-enl'); return e && e.getAttribute('data-id'); })()"


@pytest.fixture(scope="module")
def browser():
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            try:
                b = p.chromium.launch(channel="chrome")
            except Exception:
                pytest.skip(f"no chromium: {e}")
        yield b
        b.close()


@pytest.fixture(scope="module")
def html():
    return built(world={"places": {"erie": wp.resolve("Peru")}})[0]


def _open(browser, html):
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    def route(r):
        path = r.request.url[len(ORIGIN):].split("?")[0]
        if path in ("/", "/index.html"):
            return r.fulfill(status=200, content_type="text/html", body=html)
        if path == "/alto-cloud.js":
            return r.fulfill(status=200, content_type="text/javascript", body="")
        hit = palace_assets.find(path)
        if hit:
            return r.fulfill(status=200, content_type=hit[0], body=hit[1])
        return r.fulfill(status=404, body="no")

    page.route(ORIGIN + "/**", route)
    page.goto(ORIGIN + "/index.html")
    page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
    return page, errors


def _settle(page, ms=1700):
    page.wait_for_timeout(ms)


def test_a_card_is_enlarged_where_it_stands_and_given_back(browser, html):
    page, errors = _open(browser, html)
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


def test_the_arrows_hop_card_by_card_past_a_filtered_card(browser, html):
    page, errors = _open(browser, html)
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


def test_the_engine_reaches_the_map_and_a_page_puts_it_aside(browser, html):
    page, errors = _open(browser, html)
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
