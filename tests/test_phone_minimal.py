"""The phone at rest (alto/build/phone_minimal.py; Luke, 2026-10-24: "A + fade, but its a little too minimal right now and
looks unbalanced"): FIND bottom-left and MENU bottom-right, one size and one look; everything else in the MENU grid or on an
enlarged card; the two fade a few seconds after the last touch and any touch brings them back (never while something is
in hand, never with reduced motion); search is a full-screen sheet with its field pinned at the top.

The layer is a hosted script every page fetches on a phone. The browser parts run as an iPhone (touch, mobile user agent)
in WebKit and Chromium and are skipped when Playwright is not installed."""
import copy
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

from alto.build import palace_assets, phone_minimal as pm   # noqa: E402
from alto.build.builder import build_timeline, load_brief    # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None


def _build(name, **over):
    d = json.loads((ROOT / "samples" / f"{name}_brief.json").read_text(encoding="utf-8"))
    d["brief"].update(over)
    return build_timeline(*load_brief(d))[0]


@pytest.fixture(scope="module")
def pages():
    sys.path.insert(0, str(ROOT / "tests"))
    import test_palace_transit as tt
    city = build_timeline(*load_brief(copy.deepcopy(tt._bundle())))[0]
    return {"outline": _build("outline"), "timeline": _build("contracts"), "system": _build("outline", layout="solar"),
            "lanes": _build("lanes_v2"), "city": city}


# ── what a page carries ─────────────────────────────────────────────────────

def test_every_page_asks_for_the_layer_and_the_layer_is_hosted(pages):
    name, text = pm.phone_min_asset()
    assert pm.PATH == "/phone/" + name and ("phone", name, text) in palace_assets.assets()
    assert palace_assets.find(pm.PATH)[1] == text
    for k, page in pages.items():
        m = re.search(r'<script id="alto-phone-min-head">(.*?)</script>', page, re.S)
        assert m and json.dumps(pm.PATH) in m.group(1) and len(m.group(1)) < 600, k
        assert "pmin-find" not in page and "alto-phone-min'" not in page, k                 # none of the layer rides in the page
        assert page.index('id="alto-phone-min-head"') < page.index("<body"), k


def test_the_layer_keeps_its_parts():
    a = pm.ASSET
    for part in ("pmin-find", "pmin-done", "pmin-idle", "prefers-reduced-motion", "msearch-open", "nav-drawer-body", "How to use"):
        assert part in a, part
    assert "/*" not in a and " X{" not in a and "WH " not in a and ":is(C" not in a    # comments stripped, shorthand expanded


# ── in a browser, as an iPhone ──────────────────────────────────────────────

_RETRO = "(function(){var g=Storage.prototype.getItem;Storage.prototype.getItem=function(k){return /-style$/.test(k)?'retro':g.call(this,k)};})();"


@pytest.fixture(scope="module")
def site(pages):
    if pw is None:
        pytest.skip("Playwright is not installed")
    served = {f"/{k}.html": v for k, v in pages.items()}
    served["/old.html"] = pages["outline"].replace(pm.PATH, "/phone/alto-phone-min-0000000000.js")
    i = pages["timeline"].index("<head>") + len("<head>")
    served["/retro.html"] = pages["timeline"][:i] + "<script>" + _RETRO + "</script>" + pages["timeline"][i:]

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            hit = (("text/html", served[path]) if path in served else ("text/javascript", "") if path == "/alto-cloud.js"
                   else palace_assets.find(path))
            body = (hit[1] if hit else "no").encode("utf-8")
            self.send_response(200 if hit else 404)
            self.send_header("Content-Type", hit[0] if hit else "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
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


def _page(phone_ctx, **extra):
    b, dev = phone_ctx
    ctx = b.new_context(**{**dev, **extra})
    page = ctx.new_page()
    page._errors = []
    page.on("pageerror", lambda e: page._errors.append(str(e)))
    return ctx, page


@pytest.fixture
def pg(phone_ctx):
    ctx, page = _page(phone_ctx)
    yield page
    ctx.close()
    assert not page._errors, page._errors


def _go(pg, url, raw=False):
    if not raw and "pm=" not in url and "/system.html" not in url:          # the tiles are the default of the System only; every other page opts in with ?pm=1
        url += ("&" if "?" in url else "?") + "pm=1"
    pg.goto(url, wait_until="load")
    pg.wait_for_timeout(1500)
    pg.evaluate("window._altoPhoneMinApi && window._altoPhoneMinApi.wake()")


# what shows: every control a phone page can carry, the visible ones
_SHOWN = """['minimap-toggle','hamburger-tab','pmin-find','m-search','tutorial-toggle','filter-toggle','hl-mode-btn','notes-toggle','sol-ctl','lanes-nav'].filter(i => {
  const e = document.getElementById(i); if(!e) return false; const r = e.getBoundingClientRect(), c = getComputedStyle(e);
  return c.display !== 'none' && c.visibility !== 'hidden' && +c.opacity > .05 && r.width > 0 && r.bottom > 0 && r.top < innerHeight; })"""
_BOX = "(id => { const r = document.getElementById(id).getBoundingClientRect(); return [r.left, innerWidth - r.right, innerHeight - r.bottom, r.width, r.height]; })"
_IDLE = "document.documentElement.classList.contains('pmin-idle')"
_TOUCH = """(type) => { const t = document.elementFromPoint(200, 420); const a = {identifier:1, target:t, clientX:200, clientY:420};
  const e = new Event(type, {bubbles:true, cancelable:true}); Object.defineProperty(e, 'touches', {value: type === 'touchend' ? [] : [a]});
  Object.defineProperty(e, 'changedTouches', {value:[a]}); t.dispatchEvent(e); }"""


@pytest.mark.parametrize("fmt, extra", [("outline", []), ("timeline", []), ("system", []), ("lanes", ["lanes-nav"])])
def test_at_rest_find_and_menu_sit_in_the_bottom_corners_alike(pg, site, fmt, extra):
    _go(pg, f"{site}/{fmt}.html")
    assert pg.evaluate(_SHOWN) == ["hamburger-tab", "pmin-find"] + extra
    find, menu = pg.evaluate(_BOX, "pmin-find"), pg.evaluate(_BOX, "hamburger-tab")
    assert abs(find[0] - menu[1]) < 1.5 and abs(find[2] - menu[2]) < 1.5          # mirrored: same inset from its side, same height
    assert find[3:] == menu[3:] == [44, 44]
    look = "(id => { const c = getComputedStyle(document.getElementById(id)); return [c.backgroundColor, c.color, c.borderRadius]; })"
    assert pg.evaluate(look, "pmin-find") == pg.evaluate(look, "hamburger-tab")


def test_retro_makes_them_square(pg, site):
    _go(pg, site + "/retro.html")
    assert pg.evaluate("document.documentElement.classList.contains('alto-retro')")
    for i in ("pmin-find", "hamburger-tab"):
        assert pg.evaluate(f"getComputedStyle(document.getElementById('{i}')).borderTopLeftRadius") == "0px"


def test_they_fade_without_a_touch_and_a_touch_brings_them_back(pg, site):
    _go(pg, site + "/system.html")
    assert not pg.evaluate(_IDLE)
    pg.wait_for_timeout(4200)
    assert pg.evaluate(_IDLE)
    pg.wait_for_timeout(800)
    assert pg.evaluate("+getComputedStyle(document.getElementById('hamburger-tab')).opacity") < .05
    pg.evaluate(_TOUCH, "touchstart")                                               # a finger down: back, and kept while it stays
    assert not pg.evaluate(_IDLE)
    pg.wait_for_timeout(4200)
    assert not pg.evaluate(_IDLE)
    pg.evaluate(_TOUCH, "touchend")
    pg.wait_for_timeout(4200)
    assert pg.evaluate(_IDLE)
    pg.tap("#hamburger-tab")                                                        # a faded MENU still answers its first tap
    pg.wait_for_timeout(500)
    assert pg.evaluate("document.getElementById('nav-drawer').classList.contains('open')") and not pg.evaluate(_IDLE)


def test_nothing_fades_while_something_is_in_hand(pg, site):
    _go(pg, site + "/outline.html")
    pg.evaluate("window.openNavDrawer()")                                           # the drawer open
    pg.wait_for_timeout(4500)
    assert not pg.evaluate(_IDLE)
    pg.evaluate("window.closeNavDrawer()")
    pg.wait_for_timeout(400)
    pg.tap("#pmin-find")                                                            # the search sheet open, its field in hand
    pg.wait_for_timeout(4500)
    assert not pg.evaluate(_IDLE)


def test_reduced_motion_keeps_them_put(phone_ctx, site):
    ctx, page = _page(phone_ctx, reduced_motion="reduce")
    try:
        _go(page, site + "/system.html")
        page.wait_for_timeout(5000)
        assert not page.evaluate(_IDLE) and page.evaluate(_SHOWN) == ["hamburger-tab", "pmin-find"]
        assert not page._errors, page._errors
    finally:
        ctx.close()


def test_find_opens_a_full_screen_sheet_and_done_closes_it(pg, site):
    _go(pg, site + "/outline.html")
    pg.tap("#pmin-find")
    pg.wait_for_timeout(500)
    assert pg.evaluate("[document.documentElement.classList.contains('msearch-open'), document.activeElement.id]") == [True, "m-search-input"]
    bar = pg.evaluate("(() => { const r = document.getElementById('m-search').getBoundingClientRect(); return [r.top, r.left, Math.round(innerWidth - r.right)]; })()")
    assert bar == [0, 0, 0]                                                         # the field pinned across the top
    pg.keyboard.type("Formation")
    pg.wait_for_timeout(600)
    res = pg.evaluate("(() => { const r = document.getElementById('m-search-results').getBoundingClientRect(); return [r.left, Math.round(innerHeight - r.bottom), document.querySelectorAll('#m-search-results .msr-item, #m-search-results [data-id], #m-search-results button').length]; })()")
    assert res[0] == 0 and res[1] <= 1 and res[2] > 0                                # results fill the screen under it
    assert pg.evaluate(_SHOWN) == ["m-search"]                                    # the sheet alone: no control of the page over it
    pg.tap("#pmin-done")
    pg.wait_for_timeout(500)
    assert not pg.evaluate("document.documentElement.classList.contains('msearch-open')")
    pg.evaluate("window._altoPhoneMinApi.wake()")
    assert pg.evaluate(_SHOWN) == ["hamburger-tab", "pmin-find"]


def test_menu_holds_what_left_the_page(pg, site):
    _go(pg, site + "/system.html")
    pg.evaluate("window.openNavDrawer()")
    pg.wait_for_timeout(400)
    labels = pg.evaluate("[...document.querySelectorAll('#nav-drawer-body .drawer-label')].map(e => e.textContent.trim())")
    for want in ("Overview", "Dark / Light", "Scene", "Map", "Notes", "Filter", "How to use"):
        assert want in labels, (want, labels)
    assert pg.evaluate("[...document.querySelectorAll('#nav-drawer-body .drawer-section-label')].some(e => e.textContent.trim() === 'View')")
    sq = pg.evaluate("(() => { const r = document.getElementById('pmin-minimap-toggle').getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; })()")
    assert sq[0] == sq[1] and sq[0] > 60                                            # a square button
    pg.tap("#pmin-minimap-toggle")                                                  # the Map square opens the MAP list
    pg.wait_for_timeout(700)
    assert pg.evaluate("document.getElementById('minimap-wrap').classList.contains('expanded')")


def test_an_enlarged_card_brings_mark_and_notes(pg, site):
    _go(pg, site + "/timeline.html")
    pg.evaluate("document.querySelector('#world .node .node-card').click()")
    pg.wait_for_timeout(1200)
    assert pg.evaluate("document.documentElement.classList.contains('detail-open')")
    shown = pg.evaluate(_SHOWN)
    assert "hl-mode-btn" in shown and "notes-toggle" in shown and "hamburger-tab" not in shown and "pmin-find" not in shown


def test_without_the_layer_the_page_keeps_its_tiles(pg, site):
    for url in ("/old.html?pm=1", "/outline.html?pm=0", "/system.html?pm=0"):                                 # the file missing, or switched off for QA
        _go(pg, site + url)
        assert not pg.evaluate("document.documentElement.classList.contains('pmin')")
        assert "minimap-toggle" in pg.evaluate(_SHOWN) and "pmin-find" not in pg.evaluate(_SHOWN)


def test_the_memory_map_keeps_its_page_without_the_zoom_pill(pg, site):
    _go(pg, site + "/city.html")
    assert pg.evaluate("document.documentElement.classList.contains('pm-open') && document.getElementById('pal-mmap').classList.contains('on')")
    assert pg.evaluate("[...document.querySelectorAll('#pal-mmap .pm-zoom')].every(e => getComputedStyle(e).display === 'none')")
    assert pg.evaluate("getComputedStyle(document.querySelector('#pal-mmap .pm-sheet')).display") != "none"


# ── the default: the v1.9.152 tabs everywhere but the System (Luke, 2026-11-01: "I want my old toggles back except for the formats
#    we were explicitly trying to make the toggles not overwhelm the page like star chart") ──

def test_the_tiles_are_the_default_of_the_system_alone(pages):
    for k, page in pages.items():
        head = re.search(r'<script id="alto-phone-min-head">(.*?)</script>', page, re.S).group(1)
        assert ("if(!(true||" in head) == (k == "system"), (k, head[:160])
    assert pm.TILE_LAYOUTS == ("solar",)


@pytest.mark.parametrize("fmt", ["outline", "timeline", "lanes"])
def test_other_formats_keep_the_old_tabs_and_pm1_opts_in(pg, site, fmt):
    _go(pg, f"{site}/{fmt}.html", raw=True)                  # (no pm=1: the page's own default)
    shown = pg.evaluate(_SHOWN)
    assert not pg.evaluate("document.documentElement.classList.contains('pmin')") and "pmin-find" not in shown, (fmt, shown)
    assert "hamburger-tab" in shown and "minimap-toggle" in shown, (fmt, shown)       # MAP and MENU edge tabs, never faded
    pg.wait_for_timeout(4500)
    assert not pg.evaluate(_IDLE) and "hamburger-tab" in pg.evaluate(_SHOWN)
    _go(pg, f"{site}/{fmt}.html?pm=1")
    assert pg.evaluate("document.documentElement.classList.contains('pmin')") and "pmin-find" in pg.evaluate(_SHOWN)


def test_the_system_keeps_the_tiles_and_pm0_turns_them_off(pg, site):
    _go(pg, site + "/system.html", raw=True)
    assert pg.evaluate("document.documentElement.classList.contains('pmin')") and "pmin-find" in pg.evaluate(_SHOWN)
    _go(pg, site + "/system.html?pm=0")
    assert not pg.evaluate("document.documentElement.classList.contains('pmin')")


# ── what the old tabs bring back, and what never reaches a phone (bench-mobile-2's render proof, 2026-11-01) ──

_RENDERED = "(id => { const e = document.querySelector(id); if (!e) return false; const r = e.getBoundingClientRect(), c = getComputedStyle(e); return c.display !== 'none' && c.visibility !== 'hidden' && r.width > 0 && r.height > 0; })"


@pytest.mark.parametrize("url", ["/timeline.html?view=whole", "/lanes.html", "/retro.html?view=whole"])
def test_desktop_only_chrome_stays_off_a_whole_view_phone(pg, site, url):
    _go(pg, site + url, raw=True)
    assert pg.evaluate("document.documentElement.classList.contains('phone-whole')")
    for sel in ("#key-toggle", ".key-pop", "#sk-frame", "#sk-mark"):                 # the key, the Retro frame and crown
        assert not pg.evaluate(_RENDERED, sel), (url, sel)
    pg.evaluate("document.querySelector('#world .node .node-card') && document.querySelector('#world .node .node-card').click()")
    pg.wait_for_timeout(1000)
    assert "1.25px" not in pg.evaluate("(() => { const e = document.getElementById('node-nav-bar'); return e ? getComputedStyle(e).boxShadow : ''; })()")   # the desktop's hairline


def test_a_detail_page_shows_map_and_menu_again_on_the_old_tabs(pg, site):
    _go(pg, site + "/timeline.html", raw=True)
    pg.evaluate("document.querySelector('#world .node .node-card').click()")
    pg.wait_for_timeout(1200)
    assert pg.evaluate("document.documentElement.classList.contains('detail-open')")
    shown = pg.evaluate(_SHOWN)
    assert "minimap-toggle" in shown and "hamburger-tab" in shown and "pmin-find" not in shown, shown


def test_a_closed_overview_leaves_no_line_on_the_page(pg, site):
    for url in ("/outline.html", "/retro.html", "/system.html"):
        _go(pg, site + url)
        assert pg.evaluate("getComputedStyle(document.getElementById('summary-wrap')).borderBottomColor") == "rgba(0, 0, 0, 0)", url
