"""The whole view on a phone (alto/build/phone.py): the desktop page made for a finger, the one-card view kept for timelines
and outlines, the device's last choice remembered.

A page carries only the choice and a loader; the touch layer and the bar are a hosted script. The browser parts run as an
iPhone (touch, mobile user agent) in WebKit and Chromium and are skipped when Playwright is not installed."""
import http.server
import json
import re
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import palace_assets, phone   # noqa: E402
from alto.build.builder import build_timeline, load_brief       # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None


def _build(name, **over):
    d = json.loads((ROOT / "samples" / f"{name}_brief.json").read_text(encoding="utf-8"))
    d["brief"].update(over)
    brief, nodes, conns = load_brief(d)
    return build_timeline(brief, nodes, conns)[0]


@pytest.fixture(scope="module")
def pages():
    return {"outline": _build("outline"), "system": _build("outline", layout="solar"), "lanes": _build("lanes_v2")}


def _head(page):
    return re.search(r'<script id="alto-phone-head">(.*?)</script>', page, re.S).group(1)


# ── what a page carries ─────────────────────────────────────────────────────

def test_the_page_holds_the_choice_and_a_loader_and_the_layer_is_hosted(pages):
    name, text = phone.phone_asset()
    assert phone.PATH == "/phone/" + name and ("phone", name, text) in palace_assets.assets()
    assert palace_assets.find(phone.PATH)[1] == text
    for page in pages.values():
        head = _head(page)
        assert json.dumps(phone.PATH) in head and phone.KEY in head and len(head) < 900
        assert "ph-bar" not in page and "alto-phone-css" not in page                  # none of the layer rides in the page
        # the choice is made before the engine decides what a phone is
        assert page.index('id="alto-phone-head"') < page.index("classList.add('phone-whole')") < page.index("classList.add('rw')")


def test_only_timelines_and_outlines_offer_the_one_card_view(pages):
    assert "var f=0," in _head(pages["outline"]) and "var f=0," in _head(pages["lanes"])
    assert "var f=1," in _head(pages["system"])
    assert "drawer-view-btn" in pages["outline"] and "drawer-view-btn" in pages["lanes"]
    assert "drawer-view-btn" not in pages["system"]


def test_the_hosted_layer_parses_and_keeps_its_parts():
    a = phone.ASSET
    for part in ("gesturestart", "gesturechange", "gestureend", "ph-bar", "ph-sheet", "toggleSearch", "phone-whole.rw", "#search-btn"):
        assert part in a, part
    assert "/*" not in a                                                            # comments are stripped at emit


# ── in a browser, as an iPhone ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def site(pages, tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("phonesite")
    for k, v in pages.items():
        (d / f"{k}.html").write_text(v, encoding="utf-8")
    (d / "old.html").write_text(pages["outline"].replace(phone.PATH, "/phone/alto-phone-0000000000.js"), encoding="utf-8")
    (d / "phone").mkdir()
    name, text = phone.phone_asset()
    (d / "phone" / name).write_text(text, encoding="utf-8")

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(d), **k)

        def log_message(self, *a):
            pass
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


@pytest.fixture(scope="module", params=["webkit", "chromium"])
def phone_ctx(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            try:
                if request.param != "chromium":
                    raise e
                b = p.chromium.launch(channel="chrome")
            except Exception:
                pytest.skip(f"no {request.param}: {e}")
        dev = dict(p.devices["iPhone 13"])
        dev.pop("default_browser_type", None)
        yield b, dev
        b.close()


@pytest.fixture
def pg(phone_ctx):
    b, dev = phone_ctx
    ctx = b.new_context(**dev)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    yield page
    ctx.close()
    assert not errors, errors


_STATE = "[document.documentElement.classList.contains('mobile'), document.documentElement.classList.contains('phone-whole'), localStorage.getItem('alto-phone-view')]"
_BAR = "[...document.querySelectorAll('#ph-bar>button')].map(b=>b.getAttribute('aria-label'))"
_PINCH = """([x, y, d0, d1]) => { const t = document.elementFromPoint(x, y);
  const ev = (type, d) => { const a = {identifier:1, target:t, clientX:x-d/2, clientY:y}, b = {identifier:2, target:t, clientX:x+d/2, clientY:y};
    const e = new Event(type, {bubbles:true, cancelable:true}); const ts = type === 'touchend' ? [] : [a, b];
    Object.defineProperty(e, 'touches', {value:ts}); Object.defineProperty(e, 'changedTouches', {value:[a, b]}); t.dispatchEvent(e); };
  ev('touchstart', d0); for(let i = 1; i <= 8; i++) ev('touchmove', d0 + (d1-d0)*i/8); ev('touchend', d1); }"""


def _go(pg, url):
    pg.goto(url, wait_until="load")
    pg.wait_for_timeout(1200)


def test_one_card_first_then_the_last_choice_on_this_phone(pg, site):
    _go(pg, site + "/outline.html")
    assert pg.evaluate(_STATE) == [True, False, None]
    pg.evaluate("window.openNavDrawer()")
    pg.wait_for_timeout(300)
    with pg.expect_navigation():
        pg.evaluate("document.getElementById('drawer-view-btn').click()")
    pg.wait_for_timeout(1200)
    assert pg.evaluate(_STATE) == [False, True, "whole"]
    assert pg.evaluate(_BAR)[:2] == ["Cards", "Search"]
    _go(pg, site + "/lanes.html")                                                  # one choice for every timeline on the phone
    assert pg.evaluate(_STATE) == [False, True, "whole"]
    with pg.expect_navigation():
        pg.evaluate("document.querySelector('#ph-bar>button[aria-label=Cards]').click()")
    pg.wait_for_timeout(1200)
    assert pg.evaluate(_STATE) == [True, False, "card"]


def test_a_system_is_always_whole_and_has_no_cards_button(pg, site):
    _go(pg, site + "/system.html?view=card")
    assert pg.evaluate(_STATE)[:2] == [False, True]
    assert "Cards" not in pg.evaluate(_BAR) and "Search" in pg.evaluate(_BAR)
    pg.evaluate(_PINCH, [195, 400, 250, 70])                                       # two fingers in: the whole chart
    pg.wait_for_timeout(700)
    assert pg.evaluate("document.getElementById('canvas').classList.contains('sol-ov')")


def test_a_page_without_the_hosted_file_stays_one_card(pg, site):
    _go(pg, site + "/old.html?view=whole")
    assert pg.evaluate(_STATE)[:2] == [True, False]


def test_the_board_is_fitted_and_two_fingers_scale_it(pg, site):
    _go(pg, site + "/outline.html?view=whole")
    s0 = pg.evaluate("window._altoPhone.ov.s")
    assert s0 < 1
    pg.evaluate(_PINCH, [195, 400, 100, 260])
    pg.wait_for_timeout(500)
    s1 = pg.evaluate("window._altoPhone.ov.s")
    assert s1 > s0 * 1.5
    pg.evaluate(_PINCH, [195, 400, 260, 60])
    pg.wait_for_timeout(500)
    assert abs(pg.evaluate("window._altoPhone.ov.s") - s0) < 1e-6                 # never smaller than the phone's width


def test_the_bar_opens_the_desktop_panels(pg, site):
    _go(pg, site + "/outline.html?view=whole")
    pg.evaluate("document.querySelector('#ph-bar>button[aria-label=Search]').click()")
    assert pg.evaluate("[window._searchOpen, document.activeElement && document.activeElement.id]") == [True, "search-input"]
    pg.evaluate("window._searchClose()")
    pg.evaluate("document.querySelector('#ph-bar>button[aria-label=More]').click()")
    assert pg.evaluate("!!document.querySelector('#ph-sheet.on')")
    pg.evaluate("[...document.querySelectorAll('#ph-sheet button')].find(b=>b.getAttribute('aria-label')==='Background').click()")
    pg.wait_for_timeout(500)
    assert pg.evaluate("document.getElementById('bg-panel').classList.contains('open') && !document.querySelector('#ph-sheet.on')")
    assert pg.evaluate("document.documentElement.scrollWidth") == pg.evaluate("innerWidth")   # nothing to pan sideways into
