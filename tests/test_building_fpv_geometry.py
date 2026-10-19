"""The first-person view's geometry and walking, measured in a real browser (Chromium) through window.AltoBuildingFPV: openings really cut
through walls, collision follows the walls and leaves doors open, the stair carries the walker smoothly to the next floor, picking and the way back.

Skipped without Playwright (run with the QA venv's site-packages on PYTHONPATH)."""
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import building_schema as bs  # noqa: E402
from tests.building_fpv_support import Server, launch, open_view  # noqa: E402
from tests.test_building_palace_tools import built  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None


@pytest.fixture(scope="module")
def env():
    if pw is None:
        pytest.skip("Playwright is not installed")
    srv = Server()
    with pw.sync_playwright() as p:
        try:
            b = launch(p, "chromium")
        except Exception as e:
            srv.close()
            pytest.skip(f"no chromium: {e}")
        page, errors = open_view(b, srv, built()[0], bs.fixture(), room="hall")
        yield page, errors
        page.close()
        b.close()
    srv.close()


def test_openings_are_cut_through_the_wall_faces(env):
    page, errors = env
    # the main door (south wall, x 8.8..11.2, 3.2 m high): no opaque wall face across its middle, on either face, but solid beside it
    for y in (-0.3, 0.3):
        assert page.evaluate("AltoBuildingFPV.geom.covered(10, %s, 1.5, [0, 1, 0])" % y) == []
        assert page.evaluate("AltoBuildingFPV.geom.covered(7, %s, 1.5, [0, 1, 0])" % y) != []
    # a window (a=4: x 3.2..4.8, sill 1.0, head 3.2): open in the middle, wall under the sill
    assert page.evaluate("AltoBuildingFPV.geom.covered(4, 0.3, 2.0, [0, 1, 0])") == []
    assert page.evaluate("AltoBuildingFPV.geom.covered(4, 0.3, 0.5, [0, 1, 0])") != []
    # the arch in the middle wall (y 5..7, 3.4 m to the crown): open at the springing height, solid above the crown, and its soffit is curved
    assert page.evaluate("AltoBuildingFPV.geom.covered(8.15, 6, 2.0, [1, 0, 0])") == []
    assert page.evaluate("AltoBuildingFPV.geom.covered(8.15, 6, 3.8, [1, 0, 0])") != []
    assert page.evaluate("AltoBuildingFPV.geom.covered(8.15, 5.12, 3.3, [1, 0, 0])") != []              # the arch's haunch is wall, not opening
    # reveals: the door's jamb exists across the wall's thickness
    assert page.evaluate("AltoBuildingFPV.geom.covered(8.8, 0, 1.5, [1, 0, 0])") != []
    assert errors == []


def test_wall_faces_split_by_the_room_they_face(env):
    page, _ = env
    r = page.evaluate("(() => { const G = AltoBuildingFPV.geom.index(AltoBuilding.plan); return AltoBuildingFPV.geom.wallPieces(G, 'g-out'); })()")
    inner = [f for f in r["faces"] if f["room"]]
    assert {f["room"] for f in inner} == {"hall", "g101"}
    hall = [f for f in inner if f["room"] == "hall" and f["u0"] < 1]
    assert hall and abs(hall[0]["u1"] - 8.0) < 0.35                      # the south face changes rooms where the middle wall meets it (x = 8, less half its 0.3 m)
    assert all(f["ft"] == pytest.approx(5.0 if f["room"] == "hall" else 4.6) for f in inner)      # each face stops at its room's ceiling
    ops = {o["k"]: o for o in r["ops"]}
    assert ops["door"]["pass"] is True and ops["window"]["pass"] is False


def test_collision_keeps_walls_and_leaves_doorways_open(env):
    page, _ = env
    blocked = lambda x, y, z=0: page.evaluate("AltoBuildingFPV.geom.blocked(%s, %s, %s)" % (x, y, z))
    assert blocked(5, 0.1) and blocked(4, 0.2)                            # a wall, a window
    assert not blocked(10, 0.0)                                           # the main doorway
    assert not blocked(8.0, 6.0) and blocked(8.0, 3.0)                    # the arch, the wall beside it
    assert blocked(4, 3.15)                                               # the column c1
    assert blocked(14, 6.1) and not blocked(15.5, 6)                      # the plinth, beside it
    # walking straight at a wall slides along it and never passes it
    page.evaluate("AltoBuildingFPV.place(5, 6, 0, Math.PI, 0)")
    page.evaluate("AltoBuildingFPV.step(1/60, {f: 1}, 300)")
    st = page.evaluate("AltoBuildingFPV.state()")
    assert 0.3 < st["x"] < 1.0 and st["room"] == "hall"
    page.evaluate("AltoBuildingFPV.place(5, 6, 0, Math.PI * 0.9, 0)")
    page.evaluate("AltoBuildingFPV.step(1/60, {f: 1}, 240)")
    st2 = page.evaluate("AltoBuildingFPV.state()")
    assert st2["x"] < 1.0 and st2["y"] > 6.4                              # slid along the wall instead of stopping dead


def test_the_stair_carries_the_walker_smoothly_up_and_down(env):
    page, _ = env
    sup = lambda x, y, z: page.evaluate("AltoBuildingFPV.geom.support(%s, %s, %s)" % (x, y, z))
    assert sup(2.5, 3.0, 2.8) == pytest.approx(2.75, abs=0.02)            # half way up the 4 m flight that rises 5.5 m
    assert sup(10, 8, 5.5) == 5.5 and sup(10, 8, 0) == 0                  # the upper floor from above, the ground floor from below it
    assert sup(1.4, 2.0, 5.5) < 5.0                                       # the stairwell has no floor
    page.evaluate("AltoBuildingFPV.place(2.5, 0.75, 0, Math.PI / 2, 0)")
    zs = page.evaluate("(() => { const o = []; for (let i = 0; i < 420; i++) { AltoBuildingFPV.step(1/60, {f: 1}); o.push(AltoBuildingFPV.state().eye); } return o; })()")
    st = page.evaluate("AltoBuildingFPV.state()")
    assert st["level"] == "u" and st["z"] == pytest.approx(5.5, abs=0.01) and st["eye"] == pytest.approx(7.15, abs=0.05)
    steps = [b - a for a, b in zip(zs, zs[1:])]
    assert max(steps) < 0.06 and min(steps) > -0.01                       # no jumps: the eye follows the pitch line
    zs = page.evaluate("(() => { AltoBuildingFPV.place(2.5, 5.6, 5.5, -Math.PI / 2, 0); const o = []; for (let i = 0; i < 420; i++) { AltoBuildingFPV.step(1/60, {f: 1}); o.push(AltoBuildingFPV.state().eye); } return o; })()")
    assert page.evaluate("AltoBuildingFPV.state().z") < 0.3 and max(abs(b - a) for a, b in zip(zs, zs[1:])) < 0.08


def test_floors_change_with_the_bracket_keys_and_the_room_follows(env):
    page, _ = env
    page.evaluate("AltoBuildingFPV.place(10, 8, 0, 0, 0)")
    assert page.evaluate("AltoBuildingFPV.level(1)") is True
    page.evaluate("AltoBuildingFPV.step(1/60, {}, 60)")
    st = page.evaluate("AltoBuildingFPV.state()")
    assert st["level"] == "u" and st["room"] == "u201"
    assert page.evaluate("AltoBuildingFPV.level(1)") is False             # there is no floor above
    page.evaluate("AltoBuildingFPV.level(-1)"); page.evaluate("AltoBuildingFPV.step(1/60, {}, 60)")
    assert page.evaluate("AltoBuildingFPV.state().room") == "g101"


def test_the_reticle_picks_art_rooms_and_nodes(env):
    page, _ = env
    page.evaluate("AltoBuildingFPV.place(14, 3.2, 0, -Math.PI / 2, 0)")                  # facing the south wall's painting slot
    pk = page.evaluate("AltoBuildingFPV.pick()")
    assert pk["kind"] == "slot"
    page.evaluate("AltoBuildingFPV.place(14, 3.5, 0, 0, -0.35)")                          # facing the plinth in the gallery
    pk = page.evaluate("AltoBuildingFPV.pick()")
    assert pk and pk["kind"] in ("fx", "room")
    page.evaluate("AltoBuildingFPV.place(5, 6, 0, 0, 0)")                                 # in the hall, looking through the arch at a node's room
    pk = page.evaluate("AltoBuildingFPV.pick()")
    assert pk and pk["node"] in ("a", "a1", "b") and pk["text"].startswith("Open")


def test_leaving_tells_the_blueprint_where_the_walker_stood(env):
    page, errors = env
    page.evaluate("window.__ev = null; addEventListener('alto-building-fpv-exit', e => window.__ev = e.detail)")
    page.evaluate("AltoBuildingFPV.place(15, 7, 0, 1.0, 0)")
    page.keyboard.press("Escape")
    ev = page.evaluate("window.__ev")
    assert ev["l"] == "g" and ev["room"] == "g101" and math.isclose(ev["x"], 15, abs_tol=0.01) and ev["yaw"] == 57
    assert page.evaluate("!!document.getElementById('bf-root')") is False
    assert page.evaluate("document.querySelector('#bldg-root .bl-walker') !== null && !document.getElementById('bldg-root').hidden")
    assert page.evaluate("document.querySelector('#bldg-root .bl-tab.on').getAttribute('data-level')") == "g"
    assert errors == []
