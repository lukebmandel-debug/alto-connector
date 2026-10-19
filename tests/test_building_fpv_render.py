"""The first-person view drawn by real engines: Chromium and WebKit (Playwright WebKit is NOT Safari; see the module's notes), the fixture
building and a 216-room stress building. Screenshots go to /private/tmp/claude-501/bldg/shots/ for a person to look at; the asserts check
that frames are drawn (not blank, no errors), that culling keeps an interior view to a fraction of the building, the lazy load from the
blueprint, and a frame-time ceiling far above the target (the timings are reported, not judged, on headless machines).

Skipped without Playwright."""
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import building_schema as bs  # noqa: E402
from tests.building_fpv_plans import stress_plan  # noqa: E402
from tests.building_fpv_support import PIXELS, Server, launch, open_view, shot  # noqa: E402
from tests.test_building_palace_tools import built  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

FIXTURE_VIEWS = {"outside": None, "hall": [5, 9, 0, -1.2, 0.1], "gallery-art": [14, 4.2, 0, -1.5708, 0], "gallery": [18, 2, 0, 2.6, 0],
                 "stair": [6, 3, 0, 3.3, 0.25], "upper-skylit": [11, 8, 5.5, -2.5, 0.1], "upper-art": [3.5, 6, 5.5, 3.1416, 0]}
STRESS_VIEWS = {"outside": None, "enfilade": [22.5, 4, 0, 1.5708, 0], "long": [4.5, 36, 0, 0, 0], "stair": [13, 4, 0, 1.5708, 0.2], "level2": [40, 30, 6, 0.7, 0]}


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def engine(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    srv = Server()
    with pw.sync_playwright() as p:
        try:
            b = launch(p, request.param)
        except Exception as e:
            srv.close()
            pytest.skip(f"no {request.param}: {e}")
        yield request.param, b, srv
        b.close()
    srv.close()


def test_the_fixture_building_renders_from_outside_and_inside(engine):
    which, b, srv = engine
    page, errors = open_view(b, srv, built()[0], bs.fixture())
    try:
        st = page.evaluate("AltoBuildingFPV.state()")
        assert st["room"] is None and st["y"] < -3 and st["tier"] in ("high", "medium", "low")      # outside, before the main entrance
        for name, place in FIXTURE_VIEWS.items():
            stats = shot(page, f"{which}_fixture_{name}", place)
            px = page.evaluate(PIXELS)
            assert stats["draws"] > 5 and px["sd"] > 0.03 and 0.08 < px["mean"] < 0.95, (name, stats, px)
        assert errors == []
    finally:
        page.close()


def test_a_216_room_building_is_culled_and_stays_fast(engine):
    which, b, srv = engine
    plan = stress_plan()
    t0 = time.time()
    page, errors = open_view(b, srv, built()[0], plan)
    try:
        enter_s = time.time() - t0
        out = []
        for name, place in STRESS_VIEWS.items():
            stats = shot(page, f"{which}_stress_{name}", place)
            ms = page.evaluate("AltoBuildingFPV.timeFrames(20)")
            out.append((name, stats["batches"], stats["draws"], round(stats["tris"]), round(ms, 2)))
            if name != "outside":
                assert stats["batches"] < stats["total"] / 2, (name, stats)               # an interior view draws a fraction of the building
            assert ms < 60, (name, ms)
        mem = page.evaluate("AltoBuildingFPV.stats()")
        print(f"\n{which} stress: enter {enter_s:.1f}s, built {mem['built']}/{mem['total']}, {mem['mb']:.1f} MB geometry, {mem['texMb']:.0f} MB textures")
        for row in out:
            print("  %-9s batches %3d draws %4d tris %6d  %.2f ms/frame (CPU+GPU, synchronous)" % row)
        assert errors == []
    finally:
        page.close()


def test_the_blueprint_fetches_the_view_on_the_first_walk_in(engine):
    which, b, srv = engine
    page, errors = open_view(b, srv, built()[0], bs.fixture(), enter=False)
    try:
        assert page.evaluate("typeof window.AltoBuildingFPV") == "undefined"                     # nothing loaded until someone walks in
        page.evaluate("AltoBuilding.selectRoom('g101')")
        page.click("#bldg-root .bl-info .bl-go")
        page.wait_for_function("window.AltoBuildingFPV && AltoBuildingFPV.state() && AltoBuildingFPV.state().on")
        assert page.evaluate("AltoBuildingFPV.state().room") == "g101"
        assert page.evaluate("getComputedStyle(document.getElementById('bf-root')).zIndex") == "2147483000"
        assert errors == []
    finally:
        page.close()


def test_a_phone_gets_joysticks_and_the_view_fits(engine):
    which, b, srv = engine
    srv.html, srv.plan = built()[0], bs.hosted_json(bs.fixture())[1]
    ctx = b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=which == "chromium", device_scale_factor=2)
    page = ctx.new_page()
    try:
        page.goto(srv.origin + "/index.html")
        page.wait_for_function("window.AltoBuilding && AltoBuilding.plan")
        page.evaluate("AltoBuilding.enterFPV('hall', {from: 'plan'})")
        page.wait_for_function("window.AltoBuildingFPV && AltoBuildingFPV.state() && AltoBuildingFPV.state().on")
        shot(page, f"{which}_phone_hall", [5, 9, 0, -1.2, 0.05])
        if page.evaluate("matchMedia('(pointer:coarse)').matches"):
            assert page.evaluate("getComputedStyle(document.querySelector('#bf-root .bf-jl')).display") == "block"
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
    finally:
        ctx.close()
