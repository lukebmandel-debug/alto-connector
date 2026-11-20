"""The Memory Blueprint's floating name card can be dragged by its grip and collapsed to a pill (Luke, 2026-11-12). It stays in the safe area and clear of
the fixed chrome, remembers its place per timeline in this browser only, survives storage that throws, and re-clamps on rotation.
Real HTTP, Chromium and WebKit; skipped without Playwright."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.test_building_blueprint_live import _html, PLAN  # noqa: E402,F401
from alto.build import building_schema as bs  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

SIZES = [(402, 874, True), (874, 292, True), (1440, 900, False)]
IDS = ["phone-402x874", "phone-874x292", "desktop-1440x900"]


@pytest.fixture(scope="module")
def site():
    if pw is None:
        pytest.skip("Playwright is not installed")
    from tests.building_fpv_support import Server
    srv = Server()
    srv.html, srv.plan = _html(), bs.hosted_json(PLAN)[1]
    yield srv
    srv.close()


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch() if request.param == "webkit" else p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


def _open(browser, site, w, h, phone, init=None, clear=True):
    page = browser.new_page(viewport={"width": w, "height": h})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e) + " | " + str(getattr(e, "stack", ""))[:400]))
    if init:
        page.add_init_script(init)
    page.goto(site.origin + "/index.html")
    page.wait_for_function("window.AltoBuilding && AltoBuilding.plan", timeout=30000)
    if clear:
        page.evaluate("try{localStorage.clear()}catch(e){}")
    if phone:
        page.evaluate("document.documentElement.classList.add('mobile'); dispatchEvent(new Event('resize'))")
    page.wait_for_timeout(900)
    return page, errors


GEO = """() => { const q = s => document.querySelector(s), b = e => { const r = e.getBoundingClientRect(); return {l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height}; };
  const obs = [...document.querySelectorAll('#bldg-root .bl-tabs,#bldg-root .bl-zoom,#bldg-root .bl-dock,#bldg-root .bl-dock .bl-btn,#bldg-root .bl-dock .bl-go,#bldg-root .bl-dock .bl-tab,#search-btn,#info-btn,#mode-toggle,#edit-toggle,#account-btn,#nav button,#nav .nav-group-label,#title-bar>*')]
    .map(e => ({id: e.id || e.className, ...b(e), vis: getComputedStyle(e).visibility !== 'hidden' && getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().width > 1}))
    .filter(o => o.vis);
  const hb = b(q('#bldg-root .bl-head')), hit = obs.filter(o => hb.l < o.r && hb.r > o.l && hb.t < o.b && hb.b > o.t).map(o => o.id);
  return {head: hb, hit, vw: innerWidth, vh: innerHeight, vb: document.querySelector('#bldg-root svg.bl-svg').getAttribute('viewBox')}; }"""


def _drag(page, to):
    g = page.locator("#bldg-root .bl-grip").bounding_box()
    sx, sy = g["x"] + g["width"] / 2, g["y"] + g["height"] / 2
    page.mouse.move(sx, sy)
    page.mouse.down()
    page.mouse.move((sx + to[0]) / 2, (sy + to[1]) / 2, steps=4)
    page.mouse.move(to[0], to[1], steps=6)
    page.mouse.up()
    page.wait_for_timeout(250)


def test_default_has_grip_and_toggle_at_44pt(browser, site):
    page, errors = _open(browser, site, 402, 874, True)
    try:
        for sel in ("#bldg-root .bl-grip", "#bldg-root .bl-hmin"):
            bb = page.locator(sel).bounding_box()
            assert bb["width"] >= 43.9 and bb["height"] >= 43.9, (sel, bb)
        assert page.get_attribute("#bldg-root .bl-hmin", "aria-expanded") == "true"
        assert page.evaluate("getComputedStyle(document.querySelector('#bldg-root .bl-grip')).touchAction") == "none"
        assert errors == []
    finally:
        page.close()


@pytest.mark.parametrize("w,h,phone", SIZES, ids=IDS)
def test_drag_moves_the_card_and_the_plan_does_not_pan(browser, site, w, h, phone):
    page, errors = _open(browser, site, w, h, phone)
    try:
        before = page.evaluate(GEO)
        _drag(page, (w * .55, h * .5))
        after = page.evaluate(GEO)
        assert abs(after["head"]["l"] - before["head"]["l"]) > 20 or abs(after["head"]["t"] - before["head"]["t"]) > 20
        assert after["vb"] == before["vb"]
        assert after["hit"] == []
        assert errors == []
    finally:
        page.close()


@pytest.mark.parametrize("w,h,phone", SIZES, ids=IDS)
@pytest.mark.parametrize("corner", [(1, 1), (0, 1), (1, 0), (0, 0), (.5, 1)])
def test_clamp_keeps_it_in_the_safe_area_and_clear_of_the_chrome(browser, site, w, h, phone, corner):
    page, errors = _open(browser, site, w, h, phone)
    try:
        _drag(page, (corner[0] * w, corner[1] * h))
        g = page.evaluate(GEO)
        hd = g["head"]
        assert hd["l"] >= 0 and hd["t"] >= 0 and hd["r"] <= w + .5 and hd["b"] <= h + .5, hd
        assert g["hit"] == [], g
        page.reload()
        page.wait_for_function("window.AltoBuilding && AltoBuilding.plan", timeout=30000)
        if phone:
            page.evaluate("document.documentElement.classList.add('mobile'); dispatchEvent(new Event('resize'))")
        page.wait_for_timeout(1500)
        assert page.evaluate(GEO)["hit"] == []
        assert errors == []
    finally:
        page.close()


def test_collapse_to_a_pill_and_reopen(browser, site):
    page, errors = _open(browser, site, 402, 874, True)
    try:
        full = page.evaluate(GEO)["head"]
        page.click("#bldg-root .bl-hmin")
        page.wait_for_timeout(200)
        pill = page.evaluate(GEO)["head"]
        assert page.get_attribute("#bldg-root .bl-hmin", "aria-expanded") == "false"
        assert pill["h"] < full["h"] and pill["w"] <= full["w"] + 1 and pill["h"] <= 60
        assert page.locator("#bldg-root .bl-hmn").inner_text().strip() != ""
        assert page.locator("#bldg-root .bl-head h2").is_hidden()
        page.click("#bldg-root .bl-hmin")
        page.wait_for_timeout(200)
        assert page.get_attribute("#bldg-root .bl-hmin", "aria-expanded") == "true"
        assert page.locator("#bldg-root .bl-head h2").is_visible()
        page.focus("#bldg-root .bl-hmin")
        page.keyboard.press("Enter")
        page.wait_for_timeout(150)
        assert page.get_attribute("#bldg-root .bl-hmin", "aria-expanded") == "false"
        page.keyboard.press("Space")
        page.wait_for_timeout(150)
        assert page.get_attribute("#bldg-root .bl-hmin", "aria-expanded") == "true"
        assert errors == []
    finally:
        page.close()


def test_arrow_keys_nudge_from_the_grip(browser, site):
    page, errors = _open(browser, site, 1440, 900, False)
    try:
        page.focus("#bldg-root .bl-grip")
        a = page.evaluate(GEO)
        page.keyboard.press("ArrowRight")
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(150)
        b = page.evaluate(GEO)
        assert b["head"]["l"] > a["head"]["l"] + 5 and b["head"]["t"] > a["head"]["t"] + 5
        assert b["vb"] == a["vb"] and b["hit"] == []
        assert errors == []
    finally:
        page.close()


def test_position_and_collapse_persist_per_timeline_across_a_reload(browser, site):
    page, errors = _open(browser, site, 1440, 900, False)
    try:
        _drag(page, (700, 420))
        page.click("#bldg-root .bl-hmin")
        page.wait_for_timeout(200)
        moved = page.evaluate(GEO)["head"]
        keys = page.evaluate("Object.keys(localStorage).filter(k => k.indexOf('alto-bl-head:') === 0)")
        assert len(keys) == 1 and "Civil Procedure" in keys[0] or "|" in keys[0]
        page.reload()
        page.wait_for_function("window.AltoBuilding && AltoBuilding.plan", timeout=30000)
        page.wait_for_timeout(1500)
        again = page.evaluate(GEO)["head"]
        assert abs(again["l"] - moved["l"]) < 3 and abs(again["t"] - moved["t"]) < 3
        assert page.get_attribute("#bldg-root .bl-hmin", "aria-expanded") == "false"
        # another timeline (another key) does not inherit it
        page.evaluate("(k) => { const v = localStorage.getItem(k); localStorage.removeItem(k); localStorage.setItem(k.replace('|', '|other-'), v); }", keys[0])
        page.reload()
        page.wait_for_function("window.AltoBuilding && AltoBuilding.plan", timeout=30000)
        page.wait_for_timeout(1200)
        assert page.get_attribute("#bldg-root .bl-hmin", "aria-expanded") == "true"
        assert errors == []
    finally:
        page.close()


def test_it_survives_storage_that_throws(browser, site):
    boom = "Storage.prototype.getItem = function(){ throw new Error('no storage') }; Storage.prototype.setItem = function(){ throw new Error('no storage') };"
    page, errors = _open(browser, site, 1440, 900, False, init=boom, clear=False)
    try:
        g = page.evaluate(GEO)
        assert g["head"]["w"] > 50 and g["hit"] == []
        _drag(page, (600, 400))
        page.click("#bldg-root .bl-hmin")
        assert page.get_attribute("#bldg-root .bl-hmin", "aria-expanded") == "false"
        # the page's own edit-layer script reads localStorage unguarded (index.html, OPS, pre-existing): only the blueprint's errors count here
        assert [e for e in errors if "/bldg/" in e] == []
    finally:
        page.close()


def test_rotation_reclamps_it(browser, site):
    page, errors = _open(browser, site, 402, 874, True)
    try:
        _drag(page, (390, 860))
        page.set_viewport_size({"width": 874, "height": 292})
        page.evaluate("dispatchEvent(new Event('resize'))")
        page.wait_for_timeout(1200)
        g = page.evaluate(GEO)
        hd = g["head"]
        assert hd["l"] >= 0 and hd["t"] >= 0 and hd["r"] <= 874.5 and hd["b"] <= 292.5, hd
        assert g["hit"] == []
        page.set_viewport_size({"width": 402, "height": 874})
        page.evaluate("dispatchEvent(new Event('resize'))")
        page.wait_for_timeout(1200)
        g = page.evaluate(GEO)
        assert g["head"]["r"] <= 402.5 and g["head"]["b"] <= 874.5 and g["hit"] == []
        assert errors == []
    finally:
        page.close()


def _desk_geo(page):
    return page.evaluate("""() => { const b = e => { const r = e.getBoundingClientRect(); return {l: r.left, t: r.top, r: r.right, b: r.bottom}; };
      return {head: b(document.querySelector('#bldg-root .bl-head')), acct: b(document.getElementById('account-btn')), vw: innerWidth, vh: innerHeight}; }""")


@pytest.mark.parametrize("w,h", [(1440, 900), (1100, 760)], ids=["d1440", "d1100"])
def test_default_spot_is_bottom_left_beside_the_avatar(browser, site, w, h):
    page, errors = _open(browser, site, w, h, False)
    try:
        g = _desk_geo(page)
        hd, ac = g["head"], g["acct"]
        assert hd["l"] >= ac["r"] and hd["l"] - ac["r"] <= 30, (hd, ac)         # right of the avatar, close to it
        assert abs(hd["b"] - ac["b"]) <= 4 and hd["t"] > h / 2, (hd, ac)        # on the foot line, the lower half
        assert g["vh"] - hd["b"] >= 19 and hd["l"] >= 19                       # 20px from the edges (the page zoom is .8)
        assert page.evaluate(GEO)["hit"] == []                                 # clear of the avatar, the dock and the corner buttons
        assert errors == []
    finally:
        page.close()


def test_a_saved_position_beats_the_new_default(browser, site):
    page, errors = _open(browser, site, 1440, 900, False)
    try:
        key = page.evaluate("Object.keys(localStorage).filter(k => k.indexOf('alto-bl-head:') === 0)[0] || ('alto-bl-head:' + location.pathname + '|' + AltoBuilding.data.name)")
        page.evaluate("(k) => localStorage.setItem(k, JSON.stringify({x: 300, y: 120, c: 0}))", key)
        page.reload()
        page.wait_for_function("window.AltoBuilding && AltoBuilding.plan", timeout=30000)
        page.wait_for_timeout(1500)
        hd = _desk_geo(page)["head"]
        assert hd["t"] < 300 and hd["l"] > 150, hd
        assert errors == []
    finally:
        page.close()


def test_default_spot_still_drags_and_collapses(browser, site):
    page, errors = _open(browser, site, 1440, 900, False)
    try:
        a = _desk_geo(page)["head"]
        page.click("#bldg-root .bl-hmin")
        page.wait_for_timeout(200)
        pill = _desk_geo(page)["head"]
        assert pill["b"] >= a["b"] - 2 and pill["t"] > a["t"] and abs(pill["l"] - a["l"]) < 2, (a, pill)   # collapses upward-anchored: stays on the foot line
        page.click("#bldg-root .bl-hmin")
        page.wait_for_timeout(200)
        _drag(page, (700, 420))
        d = _desk_geo(page)["head"]
        assert d["t"] < a["t"] - 100 and page.evaluate(GEO)["hit"] == []
        assert errors == []
    finally:
        page.close()


@pytest.mark.parametrize("w,h", [(390, 844), (874, 292)], ids=["p390", "phone-landscape"])
def test_a_phone_keeps_its_top_left_default(browser, site, w, h):
    """Phone rule (1.9.268): the phone dock/account tab/corner buttons own the foot, so the phone's default stays top-left under MAP/Search/MENU."""
    page, errors = _open(browser, site, w, h, True)
    try:
        g = page.evaluate(GEO)
        assert g["head"]["t"] < h / 2 and g["head"]["l"] < 40 and g["hit"] == [], g
        assert errors == []
    finally:
        page.close()
