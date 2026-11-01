"""A phone (alto/build/phone.py, builder.phone_mode): a timeline or an outline opens in the phone design (one card) every
time, the whole view a switch in its MENU drawer for this tab only; a System or a horizontal timeline opens whole under the
phone design's own tiles and drawer; a Memory Palace is the phone page it always was, the Memory Map opening on its map.

A page carries only the choice and a loader; the touch layer and the bar are a hosted script. The browser parts run as an
iPhone (touch, mobile user agent) in WebKit and Chromium and are skipped when Playwright is not installed."""
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
    sys.path.insert(0, str(ROOT / "tests"))
    import test_palace_transit as tt
    city = build_timeline(*load_brief(copy.deepcopy(tt._bundle())))[0]
    return {"outline": _build("outline"), "timeline": _build("contracts"), "system": _build("outline", layout="solar"), "lanes": _build("lanes_v2"), "city": city}


def _head(page):
    m = re.search(r'<script id="alto-phone-head">(.*?)</script>', page, re.S)
    return m and m.group(1)


# ── what a page carries ─────────────────────────────────────────────────────

def test_the_page_holds_the_choice_and_a_loader_and_the_layer_is_hosted(pages):
    name, text = phone.phone_asset()
    assert phone.PATH == "/phone/" + name and ("phone", name, text) in palace_assets.assets()
    assert palace_assets.find(phone.PATH)[1] == text
    for k in ("outline", "system", "lanes"):
        page, head = pages[k], _head(pages[k])
        assert json.dumps(phone.PATH) in head and phone.KEY in head and len(head) < 900
        assert "ph-bar" not in page and "alto-phone-css" not in page                  # none of the layer rides in the page
        # the choice is made before the engine decides what a phone is
        assert page.index('id="alto-phone-head"') < page.index("classList.add('phone-whole')") < page.index("classList.add('rw')")


def test_each_format_opens_its_own_way(pages):
    assert "var f=0," in _head(pages["outline"]) and "drawer-view-btn" in pages["outline"]       # one card, whole on request
    for k in ("system", "lanes"):                                                                   # whole, no one-card switch
        assert "var f=1," in _head(pages[k]) and "drawer-view-btn" not in pages[k]
    assert _head(pages["city"]) is None and phone.PATH not in pages["city"]                        # the phone page as it was
    assert "_altoPhoneWhole&&document.documentElement.classList.add('mobile')" not in pages["city"]


def test_the_phone_design_scripts_run_inside_the_mobile_window(pages):
    for k in ("outline", "system", "lanes"):
        page = pages[k]
        for mark in phone.PHONE_SCRIPTS:
            i = page.index(mark)
            assert page[:i].endswith(phone._ON) and page.index(phone._OFF, i) < page.index("</script>", i) + len("</script>") + len(phone._OFF) + 1
        for _, new in phone._CARD_PARTS:
            assert page.count(new) == 1


def test_the_hosted_layer_parses_and_keeps_its_parts():
    a = phone.ASSET
    for part in ("gesturestart", "gesturechange", "gestureend", "alto-phone-chrome", "nav-drawer-body", "phone-whole.rw", "One card"):
        assert part in a, part
    assert "ph-bar" not in a and "ph-sheet" not in a                                 # the v1.9.153 bar is gone
    assert "/*" not in a                                                            # comments are stripped at emit


# ── in a browser, as an iPhone ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def site(pages):
    if pw is None:
        pytest.skip("Playwright is not installed")
    served = {f"/{k}.html": v for k, v in pages.items()}
    served["/old.html"] = pages["outline"].replace(phone.PATH, "/phone/alto-phone-0000000000.js")

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


_STATE = "[document.documentElement.classList.contains('mobile'), document.documentElement.classList.contains('phone-whole')]"
# the phone design's tiles, shown: MAP, MENU, the search pill, INFO, MARK, NOTES
_TILES = """['minimap-toggle','hamburger-tab','pmin-find','m-search','tutorial-toggle','hl-mode-btn','notes-toggle'].filter(i => {
  const e = document.getElementById(i); if(!e) return false; const r = e.getBoundingClientRect(), c = getComputedStyle(e);
  return c.display !== 'none' && c.visibility !== 'hidden' && +c.opacity > .05 && r.width > 0 && r.bottom > 0 && r.top < innerHeight; })"""
# at rest only MENU and FIND are on the page (phone_minimal.py, Luke 2026-10-24: "A + fade"); the rest is in the MENU grid
_ALL = ['hamburger-tab', 'pmin-find']
# a page that is not the System shows the old v1.9.152 edge tabs by default (?pm=1 opts into the corner tiles)
_TABS = ['minimap-toggle', 'hamburger-tab', 'm-search', 'tutorial-toggle', 'hl-mode-btn', 'notes-toggle']
_PINCH = """([x, y, d0, d1]) => { const t = document.elementFromPoint(x, y);
  const ev = (type, d) => { const a = {identifier:1, target:t, clientX:x-d/2, clientY:y}, b = {identifier:2, target:t, clientX:x+d/2, clientY:y};
    const e = new Event(type, {bubbles:true, cancelable:true}); const ts = type === 'touchend' ? [] : [a, b];
    Object.defineProperty(e, 'touches', {value:ts}); Object.defineProperty(e, 'changedTouches', {value:[a, b]}); t.dispatchEvent(e); };
  ev('touchstart', d0); for(let i = 1; i <= 8; i++) ev('touchmove', d0 + (d1-d0)*i/8); ev('touchend', d1); }"""


def _go(pg, url):
    pg.goto(url, wait_until="load")
    pg.wait_for_timeout(1200)
    pg.evaluate("window._altoPhoneMinApi && window._altoPhoneMinApi.wake()")     # the controls awake (they fade at rest)


def test_an_outline_opens_one_card_every_time_and_whole_only_on_request(pg, site):
    pg.goto(site + "/outline.html")
    pg.evaluate("localStorage.setItem('alto-phone-view', 'whole')")              # v1.9.153's remembered choice: ignored, cleared
    _go(pg, site + "/outline.html")
    assert pg.evaluate(_STATE) == [True, False] and pg.evaluate("localStorage.getItem('alto-phone-view')") is None
    assert pg.evaluate(_TILES) == _TABS
    pg.evaluate("window.openNavDrawer()")
    pg.wait_for_timeout(300)
    with pg.expect_navigation():
        pg.evaluate("document.getElementById('drawer-view-btn').click()")
    pg.wait_for_timeout(1200)
    assert pg.evaluate(_STATE) == [False, True]
    assert pg.evaluate(_TILES) == _TABS and not pg.evaluate("!!document.getElementById('ph-bar')")
    _go(pg, site + "/outline.html")                                               # this tab keeps it on a reload
    assert pg.evaluate(_STATE) == [False, True]
    _go(pg, site + "/lanes.html")
    _go(pg, site + "/old.html")                                                   # another timeline opens one card
    assert pg.evaluate(_STATE) == [True, False]
    _go(pg, site + "/outline.html")
    pg.evaluate("window.openNavDrawer()")
    pg.wait_for_timeout(300)
    assert pg.evaluate("document.querySelector('#drawer-view-btn .drawer-label').textContent") == "One card"
    with pg.expect_navigation():
        pg.evaluate("document.getElementById('drawer-view-btn').click()")
    pg.wait_for_timeout(1200)
    assert pg.evaluate(_STATE) == [True, False]


def test_a_system_opens_whole_under_the_phone_design(pg, site):
    _go(pg, site + "/system.html?view=card")
    assert pg.evaluate(_STATE) == [False, True]
    assert pg.evaluate(_TILES) == _ALL and pg.evaluate("!!document.getElementById('filter-toggle')")
    assert pg.evaluate("!document.getElementById('drawer-view-btn')")
    pg.evaluate("window.openNavDrawer()")
    pg.wait_for_timeout(400)
    labels = pg.evaluate("[...document.querySelectorAll('#nav-drawer-body .drawer-label')].map(e=>e.textContent.trim())")
    assert labels[1:4] == ["Overview", "Dark / Light", "Scene"]
    pg.evaluate("window.closeNavDrawer()")
    pg.wait_for_timeout(400)
    pg.evaluate("window._altoPhoneMinApi.wake()")
    assert pg.evaluate(_TILES) == _ALL                                           # the tiles come back with the drawer shut
    pg.evaluate(_PINCH, [195, 400, 250, 70])                                       # two fingers in: the whole chart
    pg.wait_for_timeout(700)
    assert pg.evaluate("document.getElementById('canvas').classList.contains('sol-ov')")


def test_map_lands_on_the_card_in_the_whole_view(pg, site):
    _go(pg, site + "/system.html")
    pg.evaluate("window.openNavDrawer()")                                          # MAP is a square in the MENU grid now
    pg.wait_for_timeout(400)
    pg.tap("#pmin-minimap-toggle")
    pg.wait_for_timeout(700)
    pg.tap("#minimap-nav-panel .mnp-node-btn >> nth=3")
    pg.wait_for_timeout(2500)
    assert pg.evaluate("!document.getElementById('minimap-wrap').classList.contains('expanded')")
    assert pg.evaluate("(document.querySelector('#world .node.focused')||{}).id") == "node-offer"


def test_the_tiles_open_the_phone_panels(pg, site):
    _go(pg, site + "/lanes.html?pm=1")
    assert pg.evaluate(_STATE) == [False, True] and pg.evaluate(_TILES) == _ALL
    pg.tap("#pmin-find")                                                           # FIND opens the phone's search as a sheet
    pg.wait_for_timeout(500)
    assert pg.evaluate("[document.getElementById('m-search').classList.contains('expanded'), document.activeElement.id]") == [True, "m-search-input"]
    assert pg.evaluate("document.documentElement.scrollWidth") == pg.evaluate("innerWidth")   # nothing to pan sideways into


def test_a_page_without_the_hosted_file_stays_one_card(pg, site):
    _go(pg, site + "/old.html?view=whole")
    assert pg.evaluate(_STATE) == [True, False]


def test_the_memory_map_opens_on_its_map_page(pg, site):
    _go(pg, site + "/city.html")
    assert pg.evaluate(_STATE) == [True, False]
    assert pg.evaluate("document.documentElement.classList.contains('pm-open') && document.getElementById('pal-mmap').classList.contains('on')")
    pg.evaluate("window._palMob.close()")                                          # its Close shows the card page under it
    assert pg.evaluate("!document.documentElement.classList.contains('pm-open')")


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
    assert 0.2 < pg.evaluate("window._altoPhone.ov.s") < 0.25 and s0 > 0.5       # never smaller than the phone's width (it opens readable, 0.6, above that)


def test_a_detail_page_of_a_whole_lanes_timeline_has_a_chevron_back_beside_the_clef(pg, site):
    _go(pg, site + "/lanes.html")
    pg.evaluate("() => { var id=(window.NODE_ORDER||NODES_SRC.map(n=>n.id))[0]; window.showDetail('node', id); }")
    pg.wait_for_timeout(1200)
    r = pg.evaluate("""() => { var b=document.getElementById('detail-back-fixed').getBoundingClientRect(), m=document.querySelector('.brand-mark').getBoundingClientRect();
      return {bc:b.top+b.height/2, mc:m.top+m.height/2, w:b.width, left:b.left, pos:getComputedStyle(document.getElementById('detail-back-fixed')).position}; }""")
    assert abs(r["bc"] - r["mc"]) <= 0.5 and r["w"] == 34 and r["left"] > 40 and r["pos"] == "fixed", r       # item 12: centred on the clef, not a stray square at the edge
    pill = pg.evaluate("() => { var p=document.querySelector('#nav-prev-label .wrap-pill'); if(!p) return null; var r=p.getBoundingClientRect(); return [r.left, parseFloat(getComputedStyle(p).paddingLeft)]; }")
    assert pill is None or (pill[0] >= 8 and pill[1] >= 6), pill      # Art: the first page's 'back around' chip is 8px clear of the edge with 6px of padding
    pg.tap("#detail-back-fixed")
    pg.wait_for_timeout(1000)
    assert not pg.evaluate("document.documentElement.classList.contains('detail-open')")


def test_the_3d_star_chart_canvas_shows_on_a_phone(pg, site):
    """The phone remap turned `html.sk-3d:not(.mobile) #sk3d` into `...:not(.phone-whole)`, so on a phone the canvas stayed
    display:none (0x0), the DOM bodies were hidden by the 3D rules and only the stars showed (Luke's iPhone, 2026-11-01)."""
    _go(pg, site + "/system.html?view=card")
    pg.evaluate("window._altoSolarStyles.set('3d')")
    pg.wait_for_timeout(1800)
    box = pg.evaluate("""(() => { const c = document.getElementById('sk3d'), r = c.getBoundingClientRect(), s = getComputedStyle(c);
      const G = window._altoSolarGeo(), n = Object.keys(G.bodies).filter(id => { const q = window._altoSolar3D.project(id); return q && isFinite(q.x) && isFinite(q.y); }).length;
      return [s.display, s.position, Math.round(r.width), Math.round(r.height), innerWidth, innerHeight, n > 0]; })()""")
    assert box[:2] == ["block", "fixed"] and box[2:4] == box[4:6] and box[6]


# ── a tap enlarges a card where it is (Luke, 2026-11-01: "you cannot enlarge a node without going into it") ──
_CARDS = """() => [...document.querySelectorAll('#world .node')].map(n => { const r = n.querySelector('.node-card').getBoundingClientRect();
  return [n.id, r.left + r.width/2, r.top + r.height/2]; }).filter(a => a[1] > 20 && a[1] < innerWidth - 20 && a[2] > 130 && a[2] < innerHeight - 130)"""
_FOCUS = """() => { const f = document.querySelector('#world .node.focused'), c = f && f.querySelector('.node-card'), r = c && c.getBoundingClientRect();
  return {foc: window._focusedNodeId || null, det: document.documentElement.classList.contains('detail-open'), s: window._altoPhone.ov.s, W: innerWidth,
    box: r && [r.left, r.right, r.top, r.bottom],
    num: [...document.querySelectorAll('#world .phase-numeral')].map(e => +getComputedStyle(e).opacity)}; }"""


@pytest.mark.parametrize("name", ["outline", "timeline"])
def test_a_tap_enlarges_a_whole_card_in_place_then_goes_in_and_a_tap_on_the_board_leaves(pg, site, name):
    _go(pg, f"{site}/{name}.html?view=whole")
    cards = pg.evaluate(_CARDS)
    assert cards
    nid, x, y = cards[0]
    pg.touchscreen.tap(x, y)
    pg.wait_for_timeout(1600)
    f = pg.evaluate(_FOCUS)
    assert f["foc"] == nid[5:] and not f["det"] and f["s"] == 1, f                  # enlarged, not opened; the board back at full size
    left, right, top, bottom = f["box"]
    assert left >= 15.5 and right <= f["W"] - 15.5 and abs((left + right) / 2 - f["W"] / 2) <= 2, f   # Art: centred, 16px clear each side
    assert top > 0 and bottom < pg.evaluate("innerHeight") and all(o == 0 for o in f["num"]), f       # the unit numerals are out of its way
    pg.touchscreen.tap(sum(f["box"][:2]) / 2, sum(f["box"][2:]) / 2)                 # a tap on the enlarged card goes in
    pg.wait_for_timeout(1200)
    assert pg.evaluate("document.documentElement.classList.contains('detail-open')")
    pg.tap("#detail-back-fixed")
    pg.wait_for_timeout(1200)
    cards = pg.evaluate(_CARDS)
    pg.touchscreen.tap(cards[0][1], cards[0][2])
    pg.wait_for_timeout(1600)
    assert pg.evaluate("window._focusedNodeId")
    empty = pg.evaluate("""() => { for (let y = 120; y < innerHeight - 100; y += 18) for (let x = 6; x < innerWidth - 6; x += 18) {
      const e = document.elementFromPoint(x, y); if (e && e.closest('#canvas') && !e.closest('.node')) return [x, y]; } return null; }""")
    assert empty
    pg.touchscreen.tap(*empty)                                                         # a tap on the board leaves
    pg.wait_for_timeout(900)
    assert not pg.evaluate("window._focusedNodeId")


def test_a_card_name_in_the_whole_view_wraps_at_spaces_only(pg, site):
    _go(pg, site + "/outline.html?view=whole")
    h = pg.evaluate("""() => [...document.querySelectorAll('#world .node:not(.focused) .node-title')].map(t => { const c = getComputedStyle(t);
      return [c.webkitHyphens || c.hyphens, c.overflowWrap]; })""")
    assert h and all(x[0] == "manual" and x[1] == "normal" for x in h), h[:3]


def test_the_whole_board_opens_readable_and_maps_list_lands_on_a_card_in_view(pg, site):
    """A3 (Luke's 'text ~3 px, unreadable'): the board opens at ~0.6 (two columns across) with a card's name 12 px on the glass at least,
    and MAP's list (a board still small) enlarges the card where it can be seen: the engine's scroll sums are for a board at full size."""
    _go(pg, site + "/outline.html?view=whole")
    s, px = pg.evaluate("""() => { const t = document.querySelector('#world .node:not(.focused) .node-title'), s = window._altoPhone.ov.s;
      return [s, parseFloat(getComputedStyle(t).fontSize) * s]; }""")
    assert 0.55 <= s <= 0.65 and px >= 11.9, (s, px)
    pg.evaluate("""() => { const m = document.getElementById('minimap-toggle'), e = new Event('touchend', {bubbles: true, cancelable: true});
      Object.defineProperty(e, 'changedTouches', {value: []}); Object.defineProperty(e, 'touches', {value: []}); m.dispatchEvent(e); }""")
    pg.wait_for_timeout(700)
    pg.tap("#minimap-nav-panel .mnp-node-btn >> nth=8")
    pg.wait_for_timeout(2500)
    f = pg.evaluate(_FOCUS)
    assert f["foc"] and f["s"] == 1 and f["box"], f
    left, right, top, bottom = f["box"]
    assert left >= 15.5 and right <= f["W"] - 15.5 and top > 0 and bottom < pg.evaluate("innerHeight"), f


def test_the_glass_slab_runs_to_the_foot_of_the_window_when_the_timeline_is_seen_small(pg, site):
    """A4 (Art: extend the tint to the full height, no seam): a short board left the page's plain gradient under the slab."""
    _go(pg, site + "/timeline.html?view=whole")
    pg.evaluate(_PINCH, [195, 400, 260, 60])                                       # all the way out
    pg.wait_for_timeout(600)
    r = pg.evaluate("""() => { const s = document.getElementById('glass-slab'), q = s.getBoundingClientRect(), w = document.getElementById('world').getBoundingClientRect(), c = getComputedStyle(s);
      return {bottom: q.bottom, worldBottom: w.bottom, H: innerHeight, shadow: c.boxShadow, os: window._altoPhone.ov.s}; }""")
    assert r["worldBottom"] < r["H"] - 40, r                                        # (the board itself is shorter than the window here)
    assert r["bottom"] >= r["H"] - 2 and r["shadow"] == "none", r
