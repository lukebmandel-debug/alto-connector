"""The hosted blueprint in a real browser: the page loads the renderer and the plan, draws the fixture, and keeps its seams (window.AltoBuilding).

Skipped without Playwright (the repo venv has none; see the 1.9.62 notes). Served from a fake origin: the page, /bldg/<renderer> and /bldg/plan-<hash>.json."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import building_schema as bs, palace_assets  # noqa: E402
from tests.test_building_palace_tools import built  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

ORIGIN = "http://alto.test"


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
    return built()[0]


def _open(browser, html, *, plan=True, script=True, fpv=True, width=1280, height=800):
    pname, ptext = bs.hosted_json(bs.fixture())
    page = browser.new_page(viewport={"width": width, "height": height})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    def route(r):
        path = r.request.url[len(ORIGIN):].split("?")[0]
        if path in ("/", "/index.html"):
            return r.fulfill(status=200, content_type="text/html", body=html)
        if path == "/alto-cloud.js":
            return r.fulfill(status=200, content_type="text/javascript", body="")
        hit = palace_assets.find(path, building_plans={pname: ptext}) if path.startswith("/bldg/") else None
        if hit and not fpv and "palace-building-fpv" in path:
            return r.fulfill(status=404, body="no")
        if hit and (plan or "plan-" not in path) and (script or "plan-" in path):
            return r.fulfill(status=200, content_type=hit[0], body=hit[1])
        return r.fulfill(status=404, body="no")

    page.route(ORIGIN + "/**", route)
    page.goto(ORIGIN + "/index.html")
    return page, errors


def test_the_blueprint_draws_the_plan_with_its_tabs_rooms_and_pills(browser, html):
    page, errors = _open(browser, html)
    try:
        page.wait_for_selector("#bldg-root .bl-tab")
        assert page.evaluate("AltoBuilding.ready.then(p => p.id)") == "test-pavilion"
        tabs = page.eval_on_selector_all("#bldg-root .bl-tab", "els => els.map(e => e.textContent)")
        assert sorted(tabs) == ["1", "G", "Outside"]
        assert page.evaluate("document.querySelector('#bldg-root .bl-tab.on').textContent") == "Outside"
        page.click("#bldg-root .bl-tab[data-level=g]")
        assert page.locator("#bldg-root .bl-room").count() == 2
        assert sorted(page.eval_on_selector_all("#bldg-root .bl-pill b", "els => els.map(e => e.textContent)")) == ["1.1", "1.1-1", "1.2"]
        # every wall one weight: a tube and a sheen per solid stretch, none with a width of its own
        assert page.evaluate("[...document.querySelectorAll('#bldg-root .bl-tube:not(.bl-rail)')].every(e => getComputedStyle(e).strokeWidth === '4.2px')")
        assert page.locator("#bldg-root .bl-tube").count() == page.locator("#bldg-root .bl-sheen").count()
        page.click("#bldg-root .bl-tab[data-level=u]")
        assert page.locator("#bldg-root .bl-room.bl-guess").count() == 2            # the confidence 1 and 0 rooms are dashed
        assert page.evaluate("[...document.querySelectorAll('#bldg-root .bl-room')].map(e => e.style.getPropertyValue('--bl-tint')).join()") == "#e0813f,#e0813f"
        assert errors == []
    finally:
        page.close()


def test_the_seams_for_the_first_person_view_and_the_data_agent(browser, html):
    page, errors = _open(browser, html, fpv=False)                  # the first-person script missing (an old site): the event, and a note
    try:
        page.wait_for_function("window.AltoBuilding && AltoBuilding.plan")
        assert page.evaluate("[AltoBuilding.plan.name, AltoBuilding.data.h, AltoBuilding.version, typeof AltoBuilding.geometry.wallSegments, typeof AltoBuilding.load]") \
            == ["Alto Test Pavilion", bs.plan_hash(bs.fixture()), 1, "function", "function"]
        assert page.evaluate("AltoBuilding.roomOf('c')") == {"room": "u201", "slot": None}
        assert page.evaluate("AltoBuilding.nodesIn('hall')") == ["a", "a1"]
        # no implementation yet: an event, and the panel says so
        page.evaluate("window.__fpv = null; addEventListener('alto-building-fpv', e => window.__fpv = e.detail)")
        page.evaluate("AltoBuilding.selectRoom('g101')")
        page.click("#bldg-root .bl-info .bl-go")
        page.wait_for_function("window.__fpv")
        assert page.evaluate("window.__fpv") == {"room": "g101", "opts": {"from": "plan"}}
        assert "not available yet" in page.inner_text("#bldg-root .bl-info")
        # a later module registers itself
        page.evaluate("window.__got = []; AltoBuilding.registerFPV({enter: (id, ctx) => { window.__got.push([id, ctx.from, ctx.plan.id, ctx.data.h]); return true; }, exit() {}})")
        assert page.evaluate("AltoBuilding.enterFPV('u201', {from: 'link', slot: 'sl-201a'})") is True
        assert page.evaluate("window.__got") == [["u201", "link", "test-pavilion", bs.plan_hash(bs.fixture())]]
        assert errors == []
    finally:
        page.close()


def test_wall_segments_break_at_doors_and_keep_windows(browser, html):
    page, errors = _open(browser, html)
    try:
        page.wait_for_function("window.AltoBuilding && AltoBuilding.plan")
        r = page.evaluate("""(() => { const w = AltoBuilding.plan.wl.find(x => x.id === 'g-out'), g = AltoBuilding.geometry.wallSegments(w);
          return {len: g.length, solid: g.solid.length, windows: g.windows.length, doors: g.doors.length}; })()""")
        assert r == {"len": 64, "solid": 2, "windows": 2, "doors": 1}                  # a closed 20 x 12 loop, cut by the one door
        c = page.evaluate("AltoBuilding.geometry.centroid([[0,0],[10,0],[10,4],[0,4]])")
        assert c == [5, 2]
        assert page.evaluate("AltoBuilding.geometry.bounds(AltoBuilding.plan, 'u')") == [0, 0, 20, 12]
    finally:
        page.close()


def test_pills_open_the_nodes_page_and_closing_it_brings_the_blueprint_back(browser, html):
    page, errors = _open(browser, html)
    try:
        page.wait_for_function("window.AltoBuilding && AltoBuilding.plan")
        page.click("#bldg-root .bl-tab[data-level=g]")
        page.click("#bldg-root .bl-pill >> nth=0")
        assert page.evaluate("document.getElementById('bldg-root').hidden") is True
        assert page.evaluate("document.documentElement.classList.contains('detail-open')")    # the engine's own detail page took over
        assert page.evaluate("document.getElementById('bldg-toggle')") is None              # blueprint and walk only: no switch to the card board
        page.evaluate("showTimeline()")
        page.wait_for_function("!document.getElementById('bldg-root').hidden && document.documentElement.classList.contains('bldg-open')")
        assert errors == []
    finally:
        page.close()


def test_pan_and_zoom_move_the_view_not_the_plan(browser, html):
    page, errors = _open(browser, html)
    try:
        page.wait_for_function("window.AltoBuilding && AltoBuilding.plan")
        vb0 = page.evaluate("document.querySelector('#bldg-root svg.bl-svg').getAttribute('viewBox')")
        page.click("#bldg-root .bl-zoom .bl-btn >> nth=0")
        vb1 = page.evaluate("document.querySelector('#bldg-root svg.bl-svg').getAttribute('viewBox')")
        assert float(vb1.split()[2]) < float(vb0.split()[2])
        page.click("#bldg-root .bl-zoom .bl-btn >> nth=2")                                 # fit
        assert page.evaluate("document.querySelector('#bldg-root svg.bl-svg').getAttribute('viewBox')") == vb0
        # a real drag pans (and selects nothing); a real click on a room selects it
        page.click("#bldg-root .bl-tab[data-level=g]")
        box = page.locator("#bldg-root svg.bl-svg").bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] - 120
        page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x + 90, y + 10, steps=6); page.mouse.up()
        assert page.evaluate("document.querySelector('#bldg-root svg.bl-svg').getAttribute('viewBox')") != vb0
        assert page.evaluate("document.querySelector('#bldg-root .bl-info').hidden") is True
        page.locator("#bldg-root .bl-room >> nth=1").click(position={"x": 30, "y": 20})
        assert "Gallery 101" in page.inner_text("#bldg-root .bl-info")
        assert errors == []
    finally:
        page.close()


def test_a_missing_plan_or_renderer_leaves_the_cards_alone(browser, html):
    page, errors = _open(browser, html, plan=False)
    try:
        page.wait_for_function("document.getElementById('bldg-root') && document.getElementById('bldg-root').hidden")
        assert page.evaluate("document.documentElement.classList.contains('bldg-open')") is False          # the cards are there
    finally:
        page.close()
    page, errors = _open(browser, html, script=False)
    try:
        page.wait_for_timeout(300)
        assert page.evaluate("typeof window.AltoBuilding") == "undefined" and page.evaluate("!!document.getElementById('bldg-root')") is False
        assert errors == []
    finally:
        page.close()


def test_the_blueprint_fits_a_phone(browser, html):
    page, errors = _open(browser, html, width=390, height=800)
    try:
        page.wait_for_function("window.AltoBuilding && AltoBuilding.plan")
        r = page.evaluate("""(() => { const b = e => e.getBoundingClientRect(), root = b(document.getElementById('bldg-root'));
          return {docW: document.documentElement.scrollWidth, tabs: [...document.querySelectorAll('#bldg-root .bl-tab')].every(e => b(e).right <= innerWidth && b(e).left >= 0),
                  head: b(document.querySelector('#bldg-root .bl-head')).right <= b(document.querySelector('#bldg-root .bl-tabs')).left, rootW: root.width}; })()""")
        assert r["docW"] <= 390 and r["tabs"] and r["head"] and r["rootW"] == 390
        assert errors == []
    finally:
        page.close()
