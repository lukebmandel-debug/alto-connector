"""The third-person avatar in both first-person views (alto/build/fpv_avatar.py): the camera follows behind and a little above a visible figure
after the city's current mayor (a neutral generic figure by setting, or without mayor data), T switches to pure first person and back, the
camera is pulled in before walls, the city's hop rises and lands once per press. The city part runs on test_palace_2000_fpv's synthetic city,
the Museum part on the test building (Chromium, as the other building tests).

Skipped without Playwright."""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from alto.build import palace_building_fpv, palace_ride, palace_ride_e  # noqa: E402
from test_palace_2000_fpv import DOOR1, page, roam  # noqa: E402,F401  (the synthetic city, both engines)

R = "window._palRide.roam"


def test_both_views_carry_the_shared_avatar_and_the_hop():
    for js in (palace_ride.RIDE_JS, palace_building_fpv.FPV_ASSET):
        assert "var AV=(function(){" in js and "__AV_TABLE__" not in js and "Cherelle Parker" in js and "Zohran Mamdani" in js
        assert "HOP={v0:3.3, g:13.5, coyote:.1, buffer:.13}" in js
    assert "/*@AVATAR@*/" not in palace_ride.RIDE_JS and "Space:'hop'" in palace_ride_e.JS_E and "e.code==='KeyT'" in palace_ride_e.JS_E
    assert "k===' '||c==='Space') n='hop'" in palace_building_fpv.FPV_ASSET and "(k==='t'||k==='T')" in palace_building_fpv.FPV_ASSET


def _enter(pg, place, view="third"):
    pg.evaluate("([p, v]) => { window._altoFpv = {view: v}; window._palRide.roam.dbg().P.place = p; }", [place, view])
    pg.evaluate("([x,y,yaw]) => { var R=window._palRide.roam; R.enter(x,y,yaw,{hold:true, real:false}); R.place(x,y,yaw); R.look(yaw,-.05); R.settle(); R.draw(); }",
                [DOOR1[0] + DOOR1[2] * 30, DOOR1[1], math.pi])


def test_city_third_person_follows_the_mayor_figure_and_t_switches(roam):
    pg = roam
    _enter(pg, "Philadelphia, Pennsylvania")
    a = pg.evaluate(f"() => {R}.avatar.set()")
    assert a["mayor"] and a["city"] == "philadelphia" and a["tag"]["text"] == "Mayor Cherelle Parker" and "Wikidata" in a["tag"]["title"]
    st = pg.evaluate(f"() => {R}.avatar.state()")
    s0 = pg.evaluate(f"() => {R}.state()")
    assert st["third"] and st["drawn"] and 2.0 < st["camD"] <= 3.5 and st["pr"] == pytest.approx(0.346, abs=0.01)
    cam = st["cam"]
    back = (cam[0] - s0["x"]) * math.cos(s0["yaw"]) + (cam[1] - s0["y"]) * math.sin(s0["yaw"])
    assert back < -2.0                                                                     # behind the walker
    tag = pg.evaluate("() => { var t=document.querySelector('#pal-ride .rm-tag'); return {txt:t.textContent, op:+getComputedStyle(t).opacity}; }")
    assert tag["txt"] == "Mayor Cherelle Parker" and tag["op"] > 0.5
    pg.keyboard.press("t"); pg.evaluate(f"() => {R}.draw()")
    st = pg.evaluate(f"() => {R}.avatar.state()")
    assert st["view"] == "first" and not st["drawn"] and st["pr"] == pytest.approx(0.654, abs=0.01)
    assert pg.evaluate(f"() => {R}.state().camZ") == pytest.approx(2.15, abs=0.1)        # the walker's own eye again
    pg.keyboard.press("t"); pg.evaluate(f"() => {R}.draw()")
    assert pg.evaluate(f"() => {R}.avatar.state().view") == "third"
    assert pg.evaluate(f"() => {R}.avatar.set('generic').mayor") is False
    assert pg.evaluate(f"() => {R}.avatar.set('mayor').mayor") is True
    pg.evaluate(f"() => {R}.exit(false)")


def test_city_without_mayor_data_uses_the_generic_figure(roam):
    _enter(roam, "Springfield, Illinois")
    a = roam.evaluate(f"() => {R}.avatar.set()")
    assert a["mayor"] is False and a["tag"]["text"] == "" and a["city"] is None
    roam.evaluate(f"() => {R}.exit(false)")


def test_city_hop_is_one_per_press_and_lands(roam):
    pg = roam
    _enter(pg, "New York, New York")
    assert pg.evaluate(f"() => {R}.avatar.set().tag.text") == "Mayor Zohran Mamdani"
    zs = pg.evaluate(f"() => {{ var o=[]; for(var i=0;i<60;i++){{ {R}.tick(1/60,'hop'); o.push({R}.avatar.state().jz); }} return o; }}")
    assert 0.3 < max(zs) < 0.5 and zs[-1] == 0 and pg.evaluate(f"() => {R}.avatar.state().hops") == 1     # held for a second: one hop
    pg.evaluate(f"() => {{ for(var i=0;i<5;i++) {R}.tick(1/60,''); {R}.tick(1/60,'hop'); for(var j=0;j<40;j++) {R}.tick(1/60,''); }}")
    assert pg.evaluate(f"() => {R}.avatar.state().hops") == 2
    pg.evaluate(f"() => {R}.exit(false)")


def test_city_camera_is_pulled_in_before_a_building(roam):
    pg = roam
    _enter(pg, "Philadelphia, Pennsylvania")
    # stand just out from the node building's door, facing the street: the building is right behind
    pg.evaluate("([x,y]) => { var R=window._palRide.roam; R.place(x,y,0); R.look(0,-.05); R.settle(); R.draw(); }", [DOOR1[0] + DOOR1[2] * 2.5, DOOR1[1]])
    st = pg.evaluate(f"() => {R}.avatar.state()")
    assert st["camD"] < 2.6 and not pg.evaluate(f"([x,y]) => {R}.blocked(x,y)", st["cam"][:2])
    pg.evaluate(f"() => {R}.exit(false)")


# ── the Museum Palace walk ──
from alto.build import building_schema as bs  # noqa: E402
from tests.building_fpv_support import Server, launch, open_view  # noqa: E402
from tests.test_building_palace_tools import built  # noqa: E402

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
        pg, errors = open_view(b, srv, built()[0], bs.fixture(), room="hall", view="third")
        yield pg, errors
        pg.close(); b.close()
    srv.close()


def test_museum_third_person_draws_the_figure_inside_the_room(museum):
    pg, errors = museum
    pg.evaluate("AltoBuildingFPV.settle()")
    st = pg.evaluate("AltoBuildingFPV.state()")
    assert st["view"] == "third" and st["avatar"] and st["camD"] is not None and st["cam"]
    assert pg.evaluate("AltoBuildingFPV._debug().camRoom !== null || AltoBuildingFPV._debug().room === null")
    assert pg.evaluate("AltoBuildingFPV.stats().draws") > 0
    pg.keyboard.press("t")
    assert pg.evaluate("AltoBuildingFPV.state().view") == "first"
    pg.keyboard.press("t")
    assert pg.evaluate("AltoBuildingFPV.state().view") == "third"
    assert not errors


def test_museum_space_hops(museum):
    pg, _ = museum
    pg.evaluate("AltoBuildingFPV.place(5, 6, 0, 0, 0)")
    h0 = pg.evaluate("AltoBuildingFPV.state().hops")
    pg.keyboard.down(" "); pg.wait_for_timeout(120); pg.keyboard.up(" "); pg.wait_for_timeout(900)
    st = pg.evaluate("AltoBuildingFPV.state()")
    assert st["hops"] == h0 + 1 and not st["air"] and st["z"] == pytest.approx(0, abs=0.01)
