"""Memory Blueprint direction B, "One dock" (Luke 2026-10-29: "I agree on memory blueprint that it should be B, just build in safeguards ... the blueprint the user
chooses would be in that space normally"; "make sure memory blueprint doesn't have the bar at the top of the screen").

On a computer (a window of any width from 1440 down to 360) the controls are one glass capsule at the bottom centre; the plan runs to the very top edge (no band: the clef,
name and wordmark float over it); and the plan is never under the dock: at rest and after Fit it stands wholly above it, a room picked (from the plan or from the card list)
is brought clear of the dock and the room card. A phone (html.mobile / html.pmin) keeps the v1.9.152 layout until Luke has seen the dock on it.

Chromium and WebKit, over a fake origin (the page, the hosted renderer, the Retro layer). Skipped without Playwright."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import building_schema as bs, palace_assets  # noqa: E402
from test_building_pma_render import ORIGIN, PLAN, _html  # noqa: E402,F401

try:
    import playwright.sync_api as pw      # noqa: F401
except ImportError:
    pw = None


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):                                                                    # (as test_building_blueprint_live: both engines, WebKit skipped where it is not installed)
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch() if request.param == "webkit" else p.chromium.launch()
        except Exception as e:
            try:
                b = p.chromium.launch(channel="chrome") if request.param == "chromium" else None
            except Exception:
                b = None
            if b is None:
                pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


WIDTHS = [1440, 1180, 1024, 768, 600, 520, 420, 360]

# the plan's rooms and chips against the dock and the card: nothing of the plan stands under them
GEO = """(() => {
  const b = e => e.getBoundingClientRect(), root = document.getElementById('bldg-root'), dock = b(root.querySelector('.bl-dock')), r = b(root);
  const rooms = [...root.querySelectorAll('.bl-room:not(.bl-ov)')].map(b).filter(q => q.width > 1 && q.height > 1);
  const u = rooms.reduce((a, q) => ({l: Math.min(a.l, q.left), t: Math.min(a.t, q.top), r: Math.max(a.r, q.right), b: Math.max(a.b, q.bottom)}), {l: 1e9, t: 1e9, r: -1e9, b: -1e9});
  const chips = [...root.querySelectorAll('.bl-pill')].map(b).filter(q => q.width > 1);
  const hit = (q, d) => q.left < d.right && q.right > d.left && q.top < d.bottom && q.bottom > d.top;
  const card = root.querySelector('.bl-info') && !root.querySelector('.bl-info').hidden ? b(root.querySelector('.bl-info')) : null;
  return {cls: document.documentElement.className, W: innerWidth, H: innerHeight, rootTop: r.top, dock: {l: dock.left, r: dock.right, t: dock.top, b: dock.bottom}, plan: u, nrooms: rooms.length,
          chipUnderDock: chips.filter(q => hit(q, dock)).length,
          clipped: [...root.querySelectorAll('.bl-dock button')].filter(e => { const q = b(e); return q.width > 1 && (q.left < dock.left - 1 || q.right > dock.right + 1 || q.bottom > dock.bottom + 1 || q.top < dock.top - 1); }).length,
          ctlUnderDock: ['mode-toggle', 'info-btn', 'search-btn', 'edit-toggle', 'alto-edit-pill', 'account-btn', 'sk-mark'].map(i => document.getElementById(i)).filter(e => e && e.getBoundingClientRect().width > 1).filter(e => hit(b(e), dock)).length, roomUnderDock: rooms.filter(q => hit(q, dock)).length,
          roomUnderCard: card ? rooms.filter(q => hit(q, card)).length : 0, card: card && {t: card.top, b: card.bottom}}; })()"""


def _page(browser, w, h=900, dark=False, style=None):
    from test_building_pma_render import PLAN as P
    pname, ptext = bs.hosted_json(P)
    page = browser.new_page(viewport={"width": w, "height": h})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    html = _html()

    def route(r):
        path = r.request.url[len(ORIGIN):].split("?")[0]
        if path in ("/", "/index.html"):
            return r.fulfill(status=200, content_type="text/html", body=html)
        if path == "/alto-cloud.js":
            return r.fulfill(status=200, content_type="text/javascript", body="")
        hit = palace_assets.find(path, building_plans={pname: ptext})
        if hit:
            return r.fulfill(status=200, content_type=hit[0], body=hit[1])
        return r.fulfill(status=404, body="no")
    page.route(ORIGIN + "/**", route)
    page.goto(ORIGIN + "/index.html")
    page.wait_for_selector("#bldg-root .bl-tab")
    page.wait_for_function("window.AltoBuilding && AltoBuilding.plan")
    page.evaluate("localStorage.clear()")
    if style:
        page.evaluate("window._altoStyle && window._altoStyle.set(%r)" % style)
    page.evaluate("document.documentElement.classList.toggle('dark', %s)" % ("true" if dark else "false"))
    page.wait_for_timeout(900)
    return page, errors


def _fit(page):
    page.keyboard.press("0")
    page.wait_for_timeout(250)


@pytest.mark.parametrize("w", WIDTHS)
@pytest.mark.parametrize("dark", [False, True])
def test_the_plan_stands_above_the_dock_and_runs_to_the_top_edge(browser, w, dark):
    page, errors = _page(browser, w, dark=dark)
    try:
        for _ in range(2):
            page.wait_for_timeout(700)                                                   # (the lifted circles glide: measure them once they have)
            g = page.evaluate(GEO)
            assert "mobile" not in g["cls"].split() and "pmin" not in g["cls"].split(), g["cls"]
            assert g["nrooms"] > 5, g
            assert g["rootTop"] == 0, g                                                  # the plan's ground starts at the very top: no band
            assert g["dock"]["l"] >= 0 and g["dock"]["r"] <= g["W"] and g["dock"]["b"] <= g["H"], g
            assert g["plan"]["b"] <= g["dock"]["t"] + 1, g                               # the whole plan above the dock, not under it
            assert g["plan"]["l"] >= -1 and g["plan"]["r"] <= g["W"] + 1 and g["plan"]["t"] >= -1, g
            assert g["chipUnderDock"] == 0 and g["roomUnderDock"] == 0 and g["ctlUnderDock"] == 0 and g["clipped"] == 0, g   # nor the page's light/dark, INFO, search circles
            _fit(page)                                                                   # Fit leaves it the same
        bars = page.evaluate("""['title-bar','nav'].map(id => { const e = document.getElementById(id); if (!e) return 0; const c = getComputedStyle(e).backgroundColor;
            const m = c.match(/rgba?\\(([^)]+)\\)/); if (!m) return 0; const p = m[1].split(',').map(parseFloat); return p.length > 3 ? p[3] : 1; })""")
        assert bars == [0, 0] or all(a < .05 for a in bars), bars                      # the bars at the top are clear (no opaque band)
        assert errors == []
    finally:
        page.close()


@pytest.mark.parametrize("w", [1440, 768, 360])
def test_retro_has_the_same_dock_square_and_the_plan_clear_of_it(browser, w):
    page, errors = _page(browser, w, style="retro")
    try:
        page.wait_for_function("document.documentElement.classList.contains('alto-retro')")
        page.wait_for_timeout(600)
        _fit(page)
        g = page.evaluate(GEO)
        assert g["rootTop"] == 0 and g["plan"]["b"] <= g["dock"]["t"] + 1 and g["chipUnderDock"] == 0, g
        assert page.evaluate("getComputedStyle(document.querySelector('#bldg-root .bl-dock')).borderTopLeftRadius") == "0px"
        assert errors == []
    finally:
        page.close()


@pytest.mark.parametrize("w", [1440, 520, 360])
def test_a_card_picked_from_the_list_lands_clear_of_the_dock_and_the_room_card(browser, w):
    page, errors = _page(browser, w)
    try:
        page.click("#bldg-root .bl-dock [aria-label^='Cards, in order']")
        assert page.locator("#bldg-root .bl-cards button").count() >= 20
        page.locator("#bldg-root .bl-cards button").nth(12).click()
        page.wait_for_timeout(500)
        assert page.locator("#bldg-root .bl-cards").is_hidden() and page.locator("#bldg-root .bl-info").is_visible()
        g = page.evaluate(GEO)
        sel = page.evaluate("""(() => { const q = document.querySelector('#bldg-root .bl-room.bl-sel'); if (!q) return null; const b = q.getBoundingClientRect(), d = document.querySelector('#bldg-root .bl-dock').getBoundingClientRect(),
            c = document.querySelector('#bldg-root .bl-info').getBoundingClientRect(); const x = (a, z) => a.left < z.right && a.right > z.left && a.top < z.bottom && a.bottom > z.top; return {dock: x(b, d), card: x(b, c), on: b.width > 4 && b.top < innerHeight}; })()""")
        assert sel and sel["on"] and not sel["dock"] and not sel["card"], (sel, g)
        assert errors == []
    finally:
        page.close()


def test_the_dock_has_a_name_for_every_control_and_the_keyboard_works(browser):
    page, errors = _page(browser, 1440)
    try:
        names = page.eval_on_selector_all("#bldg-root .bl-dock button", "els => els.map(e => e.getAttribute('aria-label') || e.textContent)")
        for want in ("Zoom in", "Zoom out", "Fit to screen", "Cards, in order", "Key and credits", "Walk in"):
            assert any(n.startswith(want) for n in names), (want, names)
        vbw = lambda: page.evaluate("+document.querySelector('#bldg-root svg.bl-svg').getAttribute('viewBox').split(' ')[2]")
        w0 = vbw()
        page.keyboard.press("+"); page.wait_for_timeout(500)
        assert vbw() < w0 - 1
        page.keyboard.press("-"); page.wait_for_timeout(500)
        page.keyboard.press("0"); page.wait_for_timeout(300)
        assert abs(vbw() - w0) < 1
        page.keyboard.press("1"); page.wait_for_timeout(200)
        assert page.evaluate("document.querySelectorAll('#bldg-root .bl-tab.on').length") == 1
        page.keyboard.press("k"); page.wait_for_timeout(200)
        box = page.inner_text("#bldg-root .bl-credits")
        assert "chip colours" in box.lower() and "Part 0" in box and "credits" in box.lower()   # (the headings are set in capitals)
        page.keyboard.press("Escape"); page.wait_for_timeout(100)
        assert page.locator("#bldg-root .bl-credits").is_hidden()
        page.keyboard.press("c"); page.wait_for_timeout(100)
        assert page.locator("#bldg-root .bl-cards").is_visible()
        page.keyboard.press("Escape"); page.wait_for_timeout(100)
        assert page.locator("#bldg-root .bl-cards").is_hidden()
        assert errors == []
    finally:
        page.close()


def test_the_name_chip_is_small_and_the_old_stacks_are_gone(browser):
    page, errors = _page(browser, 1440)
    try:
        r = page.evaluate("""(() => { const b = e => e.getBoundingClientRect(), h = b(document.querySelector('#bldg-root .bl-head')), t = b(document.querySelector('#bldg-root .bl-tabs'));
            const foot = document.querySelector('#bldg-root .bl-foot'); return {hh: h.height, hw: h.width, top: h.top, tabsBottom: t.bottom, foot: foot ? getComputedStyle(foot).display : 'none',
            walkText: !!document.querySelector('#bldg-root .bl-head .bl-walk') && getComputedStyle(document.querySelector('#bldg-root .bl-head .bl-walk')).display}; })()""")
        assert r["hh"] < 70 and r["hw"] < 400 and r["foot"] == "none" and r["walkText"] in (False, "none"), r
        assert errors == []
    finally:
        page.close()


# Luke 2026-10-30: "the dock must never cover the user's blueprint", on a phone too. A phone keeps the v1.9.152 layout (the dock is display:contents, its tabs and zoom where
# they always sat) until Luke has seen the dock there; html.bl-dock-phone is how he tries it. Either way, after Fit no room or chip of the plan is under a dock control.
PHONE = """(() => {
  const b = e => e.getBoundingClientRect(), root = document.getElementById('bldg-root');
  const hit = (q, d) => q.left < d.right && q.right > d.left && q.top < d.bottom && q.bottom > d.top;
  const rooms = [...root.querySelectorAll('.bl-room:not(.bl-ov)')].map(b).filter(q => q.width > 1 && q.height > 1);
  const chips = [...root.querySelectorAll('.bl-pill')].map(b).filter(q => q.width > 1);
  const dk = root.querySelector('.bl-dock'), shown = getComputedStyle(dk).display !== 'contents';
  const ctl = shown ? [b(dk)] : [...dk.querySelectorAll('button')].filter(e => getComputedStyle(e).display !== 'none' && b(e).width > 1).map(b);
  return {cls: document.documentElement.className, shown, nctl: ctl.length, nrooms: rooms.length, docW: document.documentElement.scrollWidth, W: innerWidth,
          under: rooms.concat(chips).filter(q => ctl.some(d => hit(q, d))).length}; })()"""


@pytest.mark.parametrize("w,h", [(390, 844), (360, 740)])
@pytest.mark.parametrize("preview", [False, True])
def test_on_a_phone_the_plan_is_never_under_the_dock(browser, w, h, preview):
    page, errors = _page(browser, w, h=h)
    try:
        page.evaluate("document.documentElement.classList.add('mobile'%s); dispatchEvent(new Event('resize'))" % (", 'bl-dock-phone'" if preview else ""))
        page.wait_for_timeout(400)
        for _ in range(2):
            _fit(page)
            page.wait_for_timeout(300)
            g = page.evaluate(PHONE)
            assert g["shown"] == preview and g["nctl"] >= 1 and g["nrooms"] > 5, g
            assert g["under"] == 0 and g["docW"] <= g["W"] + 1, g
            page.evaluate("AltoBuilding.selectLevel([...document.querySelectorAll('#bldg-root .bl-tab:not(.on)')].pop().dataset.level)")   # and on another floor
        assert errors == []
    finally:
        page.close()
