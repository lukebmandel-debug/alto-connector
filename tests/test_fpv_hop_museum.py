"""The hop and trips to cards in the Memory Blueprint walk (the test building, Chromium as the other building tests).
Its own module: the city tests hold a sync Playwright session of their own.

Skipped without Playwright."""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from alto.build import building_schema as bs  # noqa: E402
from tests.building_fpv_support import Server, launch, needs_fpv, open_view  # noqa: E402
from tests.test_building_palace_tools import built  # noqa: E402

pytestmark = needs_fpv      # the Blueprint first-person walk is off for users (palace_building_asset.BLUEPRINT_FPV)

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None


@pytest.fixture(scope="module")
def museum():
    if pw is None:
        pytest.skip("Playwright is not installed")
    srv = Server()
    with pw.sync_playwright() as p:
        try:
            b = launch(p, "chromium")
        except Exception as e:
            srv.close()
            pytest.skip(f"no chromium: {e}")
        pg, errors = open_view(b, srv, built()[0], bs.fixture(), room="hall")
        yield pg, errors
        pg.close(); b.close()
    srv.close()


def test_museum_space_hops(museum):
    pg, _ = museum
    pg.evaluate("AltoBuildingFPV.place(5, 6, 0, 0, 0)")
    h0 = pg.evaluate("AltoBuildingFPV.state().hops")
    pg.keyboard.down(" "); pg.wait_for_timeout(120); pg.keyboard.up(" ")
    pg.wait_for_function("AltoBuildingFPV.state().hops > %d" % h0, timeout=20000)
    pg.wait_for_function("!AltoBuildingFPV.state().air", timeout=40000)          # a hop is ~0.65 s of game time; under a loaded machine frames (and so game time) run slow
    st = pg.evaluate("AltoBuildingFPV.state()")
    assert st["hops"] == h0 + 1 and not st["air"] and st["z"] == pytest.approx(0, abs=0.01)


def test_museum_trip_to_a_card_walks_and_arrives_facing_it(museum):
    pg, _ = museum
    pg.evaluate("AltoBuildingFPV.place(2, 2, 0, 0, 0)")
    ids = pg.evaluate("Object.keys(AltoBuildingFPV._debug().data.nodes||{}).filter(function(id){ return AltoBuildingFPV._debug().G.slots['card-'+id]; })")
    assert ids
    pg.evaluate("(() => { var S=AltoBuildingFPV._debug(); S.paused=true; cancelAnimationFrame(S.raf); })()")
    pg.evaluate("id => AltoBuildingFPV.go(id)", ids[-1])
    pg.evaluate("(() => { for (var i=0; i<60*30 && AltoBuildingFPV.nav().on; i++) AltoBuildingFPV.step(1/60, {}, 1); })()")
    pg.wait_for_function("(() => { var n=AltoBuildingFPV.nav(); return n.last && n.last.arrived; })()", timeout=5000)          # a fade arrives a moment later
    nv = pg.evaluate("AltoBuildingFPV.nav()")
    st = pg.evaluate("AltoBuildingFPV.state()")
    to = pg.evaluate("id => AltoBuildingFPV.arrival('card-'+id)", ids[-1])
    assert nv["last"].get("arrived") and nv["hi"], (nv, st, to) and math.hypot(st["x"] - to["x"], st["y"] - to["y"]) < 0.5
    assert abs(math.remainder(st["yaw"] - to["yaw"], 2 * math.pi)) < 0.2
    pg.evaluate("(() => { var S=AltoBuildingFPV._debug(); S.paused=false; S.last=0; S.raf=requestAnimationFrame(function(){}); })()")
