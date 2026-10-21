"""The PMA blueprint in a real browser (Chromium): every level draws without errors, estimated rooms are blurred, overlays dotted, areas tinted, the footer carries the credits.

Skipped without Playwright (the repo venv has none). Set ALTO_SHOT_DIR to also write a screenshot of each level there. Served from a fake origin: the page, /bldg/<renderer>, /bldg/plan-<hash>.json, /bart/<images>."""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import buildings  # noqa: E402
from alto.build import building_schema as bs, palace_assets  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.buildings import pma_art  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

ORIGIN = "http://alto.test"
PLAN = buildings.load("pma")
ACTS = [{"label": f"Part {i}", "color": c} for i, c in enumerate(("#7c5cff", "#e0813f", "#2f9e6b", "#d4509a"))]


def _html(mode="room"):
    nodes = []
    for i in range(30):
        nodes.append({"id": f"n{i}", "act": i * 4 // 30, "title": f"Concept {i + 1}", "tag": "", "desc": "d"})
    b = {"title": "Walk", "timeline_id": "walk", "mode": "palace", "palace_view": "building", "columns": 5, "node_noun": "Room", "period_noun": "Wing", "acts": ACTS,
         "building": {"plan_z": bs.pack(PLAN), "plan_h": bs.plan_hash(PLAN), "mode": mode, "assign": {}}}
    br, ns, cs = load_brief({"brief": b, "nodes": nodes})
    return build_timeline(br, ns, cs)[0]


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


def _open(browser, html, width=1400, height=950):
    pname, ptext = bs.hosted_json(PLAN)
    art = dict(pma_art.files())
    page = browser.new_page(viewport={"width": width, "height": height})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    def route(r):
        path = r.request.url[len(ORIGIN):].split("?")[0]
        if path in ("/", "/index.html"):
            return r.fulfill(status=200, content_type="text/html", body=html)
        if path == "/alto-cloud.js":
            return r.fulfill(status=200, content_type="text/javascript", body="")
        if path.startswith("/bart/") and path[6:] in art:
            return r.fulfill(status=200, content_type="image/jpeg", body=art[path[6:]])
        hit = palace_assets.find(path, building_plans={pname: ptext}) if path.startswith("/bldg/") else None
        if hit:
            return r.fulfill(status=200, content_type=hit[0], body=hit[1])
        return r.fulfill(status=404, body="no")

    page.route(ORIGIN + "/**", route)
    page.goto(ORIGIN + "/index.html")
    page.wait_for_selector("#bldg-root .bl-tab")
    return page, errors


def test_every_level_draws_and_the_uncertainty_shows(browser):
    page, errors = _open(browser, _html())
    shots = os.environ.get("ALTO_SHOT_DIR")
    try:
        page.wait_for_function("window.AltoBuilding && AltoBuilding.plan")
        tabs = page.eval_on_selector_all("#bldg-root .bl-tab", "els => els.map(e => e.textContent)")
        assert sorted(tabs) == ["1", "2", "3", "G", "Outside"]
        want = {lv: sum(1 for r in PLAN["rm"] if r["l"] == lv) for lv in ("g", "l1", "l2", "l3")}
        for lv, n in want.items():
            page.evaluate(f"AltoBuilding.selectLevel('{lv}')")
            assert page.locator("#bldg-root .bl-room").count() == n, lv
            assert page.locator("#bldg-root .bl-tube").count() > 5
            if shots:
                Path(shots).mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(Path(shots) / f"{lv}.png"))
        page.evaluate("AltoBuilding.selectLevel('l1')")
        assert page.locator("#bldg-root .bl-room.bl-est").count() == 3                       # the three confidence-0 lobby bays: blurred
        assert page.evaluate("document.querySelector('#bldg-root .bl-room.bl-est').getAttribute('filter')") == "url(#bl-feather)"
        assert page.locator("#bldg-root .bl-room.bl-ov").count() == 1                         # Lenfest Hall: a dotted overlay
        page.evaluate("AltoBuilding.selectLevel('l3')")
        assert page.locator("#bldg-root .bl-room.bl-area").count() >= 40                      # collection-area tints
        assert page.locator("#bldg-root .bl-room.bl-guess").count() >= 10
        page.evaluate("AltoBuilding.selectLevel('outside')")
        assert page.locator("#bldg-root .bl-shell").count() == 1 and page.locator("#bldg-root .bl-terr").count() >= 13
        assert errors == []
    finally:
        page.close()


def test_the_footer_carries_the_credits_and_the_key(browser):
    page, errors = _open(browser, _html())
    try:
        page.wait_for_function("window.AltoBuilding && AltoBuilding.plan")
        foot = page.inner_text("#bldg-root .bl-foot")
        assert "OpenStreetMap contributors" in foot and "Architectural Forum" in foot and "ODbL" in foot
        assert page.locator("#bldg-root .bl-credits").is_hidden()
        page.click("#bldg-root .bl-foot")
        box = page.inner_text("#bldg-root .bl-credits")
        for want in ("Key", "Credits", "Wikimedia Commons", "PMA visitor map", "American Art 1650-1850", "basement = level 1"):
            assert want in box, want
        page.evaluate("AltoBuilding.selectRoom('l3-n-italian')")
        info = page.inner_text("#bldg-root .bl-info")
        assert "Italian Renaissance Gallery" in info and "European Art 1500-1850" in info and "350" in info and "re-partitioned" in info
        page.evaluate("AltoBuilding.selectRoom('l3-s-24')")
        assert "Galleries here today (unresolved): 307" in page.inner_text("#bldg-root .bl-info")
        assert errors == []
    finally:
        page.close()


def test_the_phone_layout_keeps_the_footer_and_tabs(browser):
    page, errors = _open(browser, _html(), width=390, height=780)
    try:
        page.wait_for_function("window.AltoBuilding && AltoBuilding.plan")
        assert page.locator("#bldg-root .bl-foot").is_visible() and page.locator("#bldg-root .bl-tab").count() == 5
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        assert errors == []
    finally:
        page.close()
