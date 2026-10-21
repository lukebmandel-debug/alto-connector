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
PI = 3.14159265
PMA_VIEWS = {"gsh-stair": [-16.5, 2.65, 12.5, PI, 0.18], "gsh-ceiling": [-12, -8, 12.5, 2.5, 0.75], "gsh-balcony": [-39.2, -7.5, 19.1, 0.35, -0.22],
             "gsh-diana": [-26.5, 2.65, None, PI, 0.3], "gallery-enfilade": [-26, 20.4, 19.1, PI / 2, 0], "period-room": [17.6, 77, 19.1, 0, -0.02],
             "upper-gallery": [-56.5, -10, 19.1, 1.15, 0.05], "east-entrance": [36.2, 2.7, 11.2, PI, 0.06], "rocky-steps": [127, 2.6, None, PI, 0.1]}
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


def test_the_philadelphia_museum_of_art_renders_its_great_stair_hall_and_galleries(engine):
    from alto.buildings import pma
    which, b, srv = engine
    page, errors = open_view(b, srv, built()[0], pma.plan())
    try:
        assert page.evaluate("AltoBuildingFPV.state().room") == "l2-gsh"                               # 'Walk in' starts inside, at the foot of the Great Stair Hall stairs
        rows = []
        for name, place in PMA_VIEWS.items():
            stats = shot(page, f"{which}_pma_{name}", place)
            px = page.evaluate(PIXELS)
            ms = page.evaluate("AltoBuildingFPV.timeFrames(10)")
            rows.append((name, page.evaluate("AltoBuildingFPV.state().room"), stats["draws"], round(stats["tris"]), round(ms, 2)))
            assert stats["draws"] > 5 and px["sd"] > 0.03 and 0.08 < px["mean"] < 0.95, (name, stats, px)
        rooms = {r[0]: r[1] for r in rows}
        assert rooms["gsh-stair"] == "l2-gsh" and rooms["gsh-balcony"] == "l3-gsh-balcony" and rooms["period-room"] == "l3-nw-2"
        # the hall is open to its coffered, skylit ceiling: no other room's ceiling crosses it, and the landing under Diana is floor
        assert page.evaluate("AltoBuildingFPV.geom.covered(-22, 4, 24, [0, 0, 1], 5.3)") == []
        assert page.evaluate("AltoBuildingFPV.geom.covered(-22, 4, 29.495, [0, 0, 1], .004)") == ["lay"]
        assert page.evaluate("AltoBuildingFPV.geom.support(-36, 7.5, 19.1)") == pytest.approx(19.1)
        print(f"\n{which} PMA:")
        for row in rows:
            print("  %-16s %-16s draws %4d tris %6d  %.2f ms/frame" % row)
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


def test_a_second_walk_in_draws_again(engine):
    """Regression: exit() loses the GL context, whose 'lost' event arrives after the next enter() and used to blank it (S.lost stayed set)."""
    which, b, srv = engine
    page, errors = open_view(b, srv, built()[0], bs.fixture(), room="g101")
    try:
        first = page.evaluate(PIXELS)
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        assert page.evaluate("!!document.getElementById('bf-root')") is False
        page.evaluate("AltoBuilding.enterFPV('hall', {from: 'plan'})")
        page.wait_for_function("window.AltoBuildingFPV && AltoBuildingFPV.state() && AltoBuildingFPV.state().on")
        page.wait_for_timeout(500)                                       # let the old canvas's context-lost event arrive
        again = page.evaluate(PIXELS)
        shot(page, f"{which}_fixture_reenter")
        assert first["mean"] > 0.08 and again["mean"] > 0.08 and again["sd"] > 0.03, (first, again)
        assert page.evaluate("AltoBuildingFPV.state().room") == "hall" and errors == []
    finally:
        page.close()


def test_the_plan_credits_are_on_screen(engine):
    which, b, srv = engine
    from alto.buildings import pma
    page, errors = open_view(b, srv, built()[0], pma.plan())
    try:
        t = page.evaluate("document.querySelector('#bf-root .bf-credit').textContent")
        assert "OpenStreetMap" in t and "Architectural Forum" in t and "Wikimedia Commons" in t
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


def test_walking_out_through_the_front_door_never_drops_you(engine):
    """Luke fell through the floor walking in: the vestibule stopped short of the hall. Every interior gap now has a floor."""
    from alto.buildings import pma
    which, b, srv = engine
    page, errors = open_view(b, srv, built()[0], pma.plan())
    try:
        page.evaluate("AltoBuildingFPV.place(-13.5, 2.65, 12.5, 0, 0)")                  # in the Great Stair Hall, facing the East Entrance
        low, x = 99.0, -99.0
        for _ in range(14):
            page.evaluate("AltoBuildingFPV.step(1/60, {f: 1}, 60)")
            st = page.evaluate("AltoBuildingFPV.state()")
            low, x = min(low, st["z"]), st["x"]
        assert low > 10.9, low                                                             # level 2 (12.5) or the terrace (11.2): never the lobby below (6.2)
        assert x > -3, x                                                                   # it walked out of the building
        page.evaluate("AltoBuildingFPV.place(-5, 2.65, 12.5, 0, 0)")                      # standing in the doorway strip itself
        assert abs(page.evaluate("AltoBuildingFPV.geom.support(-5, 2.65, 12.5)") - 12.5) < 0.05
        assert errors == []
    finally:
        page.close()


def test_every_card_stands_in_its_room_and_n_walks_to_the_next(engine):
    from alto.buildings import pma
    from tests.test_building_pma_render import _html
    which, b, srv = engine
    page, errors = open_view(b, srv, _html(), pma.plan())
    try:
        dbg = page.evaluate("(() => { const G = AltoBuildingFPV._debug().G; return [G.cards.length, Object.keys(G.slots).filter(k => k.indexOf('card-') === 0).length]; })()")
        assert dbg[0] >= 1 and dbg[0] == dbg[1]
        before = page.evaluate("AltoBuildingFPV.state()")
        page.keyboard.press("n")
        page.wait_for_timeout(1200)
        after = page.evaluate("AltoBuildingFPV.state()")
        assert (before["x"], before["y"]) != (after["x"], after["y"])
        page.keyboard.press("c")                                                           # the card list opens, with one button per card
        page.wait_for_selector("#bf-root .bf-clist button")
        assert page.locator("#bf-root .bf-clist button").count() >= 1
        assert errors == []
    finally:
        page.close()
