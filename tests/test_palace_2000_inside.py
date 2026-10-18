"""FPV phase 2 (alto/build/palace_ride_inside.py): looking up and down to 85 degrees, and going INSIDE a node building.

Source assertions always run. The runtime checks reuse the page of test_palace_2000_fpv.py (the real RIDE_JS / RIDE_CSS over the synthetic city with two node buildings and a stub of
showDetail) in WebKit and Chromium (skipped without Playwright):
    ALTO_REPO=$PWD _qa/kit/py -m pytest -q tests/test_palace_2000_inside.py
Nothing here reads a cloud environment.
"""
import math
import os
import sys

import pytest

from alto.build import palace_ride, palace_ride_door, palace_ride_e, palace_ride_gl, palace_ride_gl_shaders, palace_ride_inside

sys.path.insert(0, os.path.dirname(__file__))
from test_palace_2000_fpv import DOOR1, NAMES, open_from_lobby, page, roam, stand  # noqa: E402,F401  (fixtures: the page and a clean roam)


# ───────────────────────────── source contract ─────────────────────────────
def test_the_inside_part_is_assembled_into_the_ride():
    assert palace_ride_inside.JS_INSIDE_GL in palace_ride.RIDE_JS and palace_ride_inside.JS_INSIDE in palace_ride.RIDE_JS
    assert palace_ride_inside.CSS_INSIDE in palace_ride.RIDE_CSS
    assert "/*@INSIDE@*/" not in palace_ride.RIDE_JS
    for f in ("function insideEnter(mem)", "function insideGo(df)", "function insideLeave()", "function insideOpen()", "function glInside(b,d)", "function insideWindows(ring,sg,win)", "function inSpans(Lm,dpar)"):
        assert f in palace_ride.RIDE_JS


def test_pitch_is_85_degrees_and_the_door_part_hands_over_to_the_inside_part():
    assert "pitchMax:1.4835" in palace_ride_e.JS_E and abs(1.4835 - math.radians(85)) < 1e-3
    j = palace_ride_door.JS_DOORS
    assert "if(insideEnter(mem)){ DR.busy=0; return; }" in j and "function openDetail(mem)" in j      # the page is opened from the directory (insideOpen -> openDetail), the same flow as before
    assert "if(IN.on) return insideKey(e);" in j and "insideReset();" in j
    assert j.index("exitCore(false);") < j.index("window.showDetail('node', mem.id)")                      # unchanged: roam is left before the page's typing starts


def test_the_shell_has_windows_a_door_and_the_interior_materials():
    j = palace_ride_inside.JS_INSIDE_GL
    assert "Q(it.a,it.b,0,.9); Q(it.a,it.b,2.7,CH)" in j and "Q(it.a,it.b,2.75,CH)" in j                  # sill 0.9 m, head 2.7 m, a doorway with a header
    assert "IN_FH=3.4" in j
    assert "GLX.inside" in palace_ride_gl._JS_GL_FRAME and "gl.disable(gl.CULL_FACE); glBind(gl,pg,GLX.inside)" in palace_ride_gl._JS_GL_FRAME
    fs = palace_ride_gl_shaders.FS_WORLD
    assert "the inside of a node building" in fs and "id>26.5&&id<31.5" in fs and "if(uIn>.5) discard;" in fs
    assert "'uIn'" in palace_ride_gl._JS_GL_MAIN or "'uIn'" in palace_ride_gl.JS_GL


def test_roofs_have_an_underside_so_looking_up_does_not_look_through_them():
    g = palace_ride_gl._JS_GL_BUILD
    assert "gflat(b,top,h-.03,47,T,false)" in g and "gflat(b,rr,zt+tH-.03,47,T,false)" in g and "gflat(b,r2,zt2+h2-.03,47,T,false)" in g


def test_the_floor_indicator_and_leave_are_quiet():
    c = palace_ride_inside.CSS_INSIDE
    assert ".rm-fl" in c and ".rm-lv" in c and ".rm-dir" in c and "prefers-reduced-motion" in c
    for gamey in ("bounce", "@keyframes", "pulse", "infinite"):
        assert gamey not in c and gamey not in palace_ride_inside.JS_INSIDE
    j = palace_ride_inside.JS_INSIDE
    assert "'[' " not in j and "k==='['||c==='BracketLeft'||k==='PageDown'" in j and "k===']'||c==='BracketRight'||k==='PageUp'" in j
    assert "dur:600" in j and "(IN.f+1)+' / '+IN.nf" in j


# ───────────────────────────── runtime ─────────────────────────────
PX = """([x,y,w,h]) => { var R=window._palRide.roam; R.draw(); var cs=document.querySelectorAll('#pal-ride canvas'), o=document.createElement('canvas');
  o.width=cs[0].width; o.height=cs[0].height; var g=o.getContext('2d'); cs.forEach(function(c){ g.drawImage(c,0,0); });
  var k=o.width/innerWidth, d=g.getImageData(Math.round(x*k),Math.round(y*k),Math.round(w*k),Math.round(h*k)).data, s=[0,0,0], q=0, N=d.length/4, i;
  for(i=0;i<d.length;i+=4){ s[0]+=d[i]; s[1]+=d[i+1]; s[2]+=d[i+2]; } var m=[s[0]/N,s[1]/N,s[2]/N]; for(i=0;i<d.length;i+=4){ q+=Math.pow(d[i]-m[0],2)+Math.pow(d[i+1]-m[1],2)+Math.pow(d[i+2]-m[2],2); }
  return {mean:m, sd:Math.sqrt(q/N/3)}; }"""
INS = "() => window._palRide.roam.inside.state()"


def go_inside(pg):
    stand(pg, 9, math.pi, hold=False)
    pg.wait_for_timeout(300)
    pg.evaluate("() => window._palRide.roam.place(%r, %r, Math.PI)" % (DOOR1[0] + 9, DOOR1[1]))
    pg.wait_for_timeout(500)
    assert pg.evaluate("() => (window._palRide.roam.door.cur()||{}).name") == NAMES["n1"]
    pg.keyboard.press("e")
    pg.wait_for_timeout(1300)
    st = pg.evaluate(INS)
    assert st["on"], st
    return st


def test_pitch_goes_to_85_degrees_both_ways_with_the_mouse_the_api_and_stays_level(roam):
    pg = roam
    stand(pg, 12, math.pi, dy=8, hold=True)
    r = pg.evaluate("() => { var R=window._palRide.roam; R.look(null, 9); var up=R.state().pitch; R.look(null,-9); var dn=R.state().pitch; R.draw(); var s=R.state(); return [up,dn,s.vfov,s.hfov]; }")
    assert r[0] == pytest.approx(math.radians(85), abs=2e-3) and r[1] == pytest.approx(-math.radians(85), abs=2e-3)
    assert r[2] == pytest.approx(65, abs=1.5) and r[3] == pytest.approx(90, abs=0.6)                    # the view's angles do not change with the tilt
    # the mouse: a long vertical drag lands on the same limit (the scene follows the pointer: dragging down looks up)
    pg.evaluate("() => window._palRide.roam.look(null, 0)")
    pg.mouse.move(700, 300)
    pg.mouse.down()
    pg.mouse.move(700, 880, steps=8)
    pg.mouse.up()
    up = pg.evaluate("() => window._palRide.roam.state().pitch")
    pg.mouse.move(700, 880)
    pg.mouse.down()
    pg.mouse.move(700, 10, steps=8)
    pg.mouse.up()
    dn = pg.evaluate("() => window._palRide.roam.state().pitch")
    assert up == pytest.approx(math.radians(85), abs=0.02) and dn == pytest.approx(-math.radians(85), abs=0.02)
    # the camera has no roll: its right-hand axis is horizontal at every pitch (glCamera: R=[-sy,cy,0]) and the sky is drawn from the same basis
    assert "Rv=[-sy, cy, 0]" in palace_ride_gl._JS_GL_FRAME and "U=[-sp*cy, -sp*sy, cp]" in palace_ride_gl._JS_GL_FRAME


def test_looking_straight_up_is_sky_and_the_roof_is_not_see_through(roam):
    pg = roam
    stand(pg, 12, math.pi, dy=8, hold=True)
    pg.evaluate("() => window._palRide.roam.look(Math.PI, 1.48)")
    sky = pg.evaluate(PX, [500, 150, 400, 200])
    assert sky["mean"][2] > sky["mean"][0] + 25 and sky["mean"][2] > 150                               # straight up: blue sky, not black or a stretched smear
    pg.evaluate("() => window._palRide.roam.look(Math.PI, 0)")
    street = pg.evaluate(PX, [500, 150, 400, 200])
    assert street["sd"] > 6 and street["mean"] != sky["mean"]                                          # level: the facade, with detail
    pg.evaluate("() => window._palRide.roam.look(Math.PI, -1.48)")
    down = pg.evaluate(PX, [500, 150, 400, 200])
    assert down["mean"][2] < 200 and down["sd"] > 1                                                    # straight down: the ground under the feet, drawn


def test_e_at_the_door_goes_inside_the_lobby_with_a_floor_indicator_and_a_directory(roam):
    pg = roam
    st = go_inside(pg)
    assert st["floor"] == 0 and st["floors"] >= 5 and st["label"] == "1 / %d" % st["floors"] and st["name"] == NAMES["n1"]
    assert st["shell"] and st["shell"]["n"] > 1000                                                      # the interior shell is in the GL buffer
    assert pg.evaluate("() => window._palRide.roam.active()") and pg.evaluate("() => window.__detail") == []     # inside is still roam, and no page yet
    ui = pg.evaluate("""() => { var f=document.querySelector('.rm-fl'), d=document.querySelector('.rm-dir'); return {fl:getComputedStyle(f).display, n:f.querySelector('.rm-fln').textContent,
      leave:!!document.querySelector('.rm-lv'), dir:getComputedStyle(d).display, hint:getComputedStyle(document.querySelector('.rm-hint')).display}; }""")
    assert ui["fl"] == "flex" and ui["n"] == st["label"] and ui["leave"] and ui["dir"] == "block" and ui["hint"] == "none"
    # the lobby is lit by the room, not by the sun: the ceiling over my head is not the sky
    pg.evaluate("() => window._palRide.roam.look(null, 1.1)")
    ceil = pg.evaluate(PX, [500, 120, 400, 160])
    assert not (ceil["mean"][2] > ceil["mean"][0] + 25), ceil                                           # warm white, not sky blue
    # I am inside the footprint, and the walls hold me: walking at a wall for ten seconds never gets out
    pg.evaluate("() => window._palRide.roam.look(Math.PI, 0)")                                          # towards the street wall behind the door: walk west-to-east? any direction
    for yaw in (0, math.pi / 2, math.pi, -math.pi / 2):
        pg.evaluate("(y) => window._palRide.roam.look(y, 0)", yaw)
        r = pg.evaluate("(y) => { var R=window._palRide.roam; R.look(y,0); var o=R.sim('f', 14, 1/30, true); var s=R.state(); return {x:s.x, y:s.y, bl:R.inside.blocked(s.x,s.y), on:R.inside.on()}; }", yaw)
        if r["on"]:
            assert r["bl"] is False
            assert 3980 < r["x"] < 4132 and 2085 < r["y"] < 2235                                          # the 100 x 140 lot: x 4030..4130, y 2090..2230 (inside, or just left by the door)
    pg.evaluate("() => window._palRide.roam.exit(false)")


def test_floors_glide_in_600_ms_and_stop_at_the_ends(roam):
    pg = roam
    st = go_inside(pg)
    n, z0 = st["floors"], st["z"]
    fh = 3.4 * 1.3
    pg.keyboard.press("]")
    pg.wait_for_timeout(250)
    mid = pg.evaluate(INS)
    assert mid["gliding"] and mid["floor"] == 1 and z0 < mid["z"] < z0 + fh and mid["label"] == "2 / %d" % n          # the eye is on its way, the indicator already says where it is going
    pg.wait_for_timeout(600)
    one = pg.evaluate(INS)
    assert not one["gliding"] and one["z"] == pytest.approx(z0 + fh, abs=1e-6)                              # one floor = 3.4 m
    assert pg.evaluate("() => window._palRide.roam.state().camZ") == pytest.approx(z0 + fh + 2.15, abs=0.2)
    pg.keyboard.press("PageUp")
    pg.wait_for_timeout(900)
    assert pg.evaluate(INS)["floor"] == 2
    pg.keyboard.press("[")
    pg.wait_for_timeout(900)
    pg.keyboard.press("PageDown")
    pg.wait_for_timeout(900)
    assert pg.evaluate(INS)["floor"] == 0
    pg.keyboard.press("[")
    pg.wait_for_timeout(300)
    assert pg.evaluate(INS)["floor"] == 0                                                                    # nothing below the lobby
    for _ in range(n + 3):
        pg.keyboard.press("]")
        pg.wait_for_timeout(40)
    pg.wait_for_timeout(1000)
    top = pg.evaluate(INS)
    assert top["floor"] == n - 1 and top["label"] == "%d / %d" % (n, n)                                      # as high as the building's real height allows (and no higher)
    assert top["z"] == pytest.approx(z0 + (n - 1) * fh, abs=1e-6) and top["z"] + 2.15 < 30 * 1.0 + 4.5       # the node is 30 units tall: the top floor is under its roof
    assert pg.evaluate("() => document.querySelector('.rm-fl [data-in=up]').disabled")
    pg.evaluate("() => window._palRide.roam.exit(false)")


def test_reduced_motion_changes_floor_without_a_glide(roam):
    pg = roam
    st = go_inside(pg)
    pg.emulate_media(reduced_motion="reduce")
    pg.keyboard.press("]")
    pg.wait_for_timeout(50)
    s = pg.evaluate(INS)
    assert s["floor"] == 1 and not s["gliding"] and s["z"] == pytest.approx(st["z"] + 3.4 * 1.3, abs=1e-6)
    pg.evaluate("() => window._palRide.roam.exit(false)")


def test_a_window_view_exists_and_from_an_upper_floor_it_looks_down_on_the_street(roam):
    pg = roam
    go_inside(pg)
    wins = pg.evaluate("() => window._palRide.roam.inside.windows()")
    assert len(wins) >= 6 and all(w["len"] == pytest.approx(1.9, abs=0.01) for w in wins)                  # openings on the walls
    w = sorted((w for w in wins if w["nx"] < -0.9), key=lambda w: abs(w["y"] - 2168))[0]                  # one on the street wall (the door's)
    pg.evaluate("([x,y]) => { var R=window._palRide.roam; R.place(x,y,0); R.look(0,0); }", [w["x"] + w["nx"] * 1.0, w["y"]])
    pg.wait_for_timeout(300)
    ground = pg.evaluate(PX, [450, 250, 500, 350])                                                          # standing at it, level: the street world is in the opening (detail), not a flat wall
    assert ground["sd"] > 12
    pg.keyboard.press("]")
    pg.keyboard.press("]")
    pg.keyboard.press("]")
    pg.wait_for_timeout(1300)
    pg.evaluate("() => window._palRide.roam.look(0, -0.5)")
    pg.wait_for_timeout(300)
    s = pg.evaluate("() => window._palRide.roam.state()")
    assert s["camZ"] > 3 * 3.4 * 1.3 and pg.evaluate(INS)["floor"] == 3                                       # ten metres up, looking down...
    low = pg.evaluate(PX, [450, 450, 500, 250])
    assert low["sd"] > 12 and low["mean"] != ground["mean"]                                                  # ...at the street: kerb, lawn, cars, not the plaster or the floor
    wall = pg.evaluate("() => { var R=window._palRide.roam; R.look(Math.PI,-0.2); return 1; }")
    flat = pg.evaluate(PX, [500, 150, 400, 200])
    assert flat["sd"] < low["sd"]                                                                            # the inside walls and floor are plain next to the street
    pg.evaluate("() => window._palRide.roam.exit(false)")


def test_the_directory_names_the_building_and_open_opens_its_page_and_closing_it_restores(roam):
    pg = roam
    go_inside(pg)
    open_from_lobby(pg, "click")
    pg.wait_for_timeout(1000)
    r = pg.evaluate("() => ({a: window._palRide.roam.active(), i: window._palRide.roam.inside.on(), d: window.__detail, cls: document.documentElement.classList.contains('detail-open'), put: window.__put, sh: !!window._palRide.roam.inside.shell()})")
    assert r["a"] is False and r["i"] is False and r["d"] == [["node", "n1"]] and r["cls"] and r["put"] == [{"z": 0.5, "x": 123, "y": 456}] and r["sh"] is False
    pg.evaluate("() => window.closeDetail()")
    pg.wait_for_timeout(1200)
    b = pg.evaluate("() => ({a: window._palRide.roam.active(), i: window._palRide.roam.inside.on(), d: window._palRide.roam.door.state(), s: window._palRide.roam.state()})")
    assert b["a"] is True and b["i"] is False and b["d"]["busy"] == 0 and b["d"]["ret"] is False        # the same return as the door's: roam again, on the street, where I was when I pressed E
    assert b["s"]["x"] == pytest.approx(DOOR1[0] + 9, abs=1e-6)
    pg.evaluate("() => window._palRide.roam.exit(false)")


def test_the_directory_card_says_open_the_building_and_e_opens_it_only_in_front_of_the_board(roam):
    pg = roam
    st = go_inside(pg)
    b = st["board"]
    # far from the board and facing away: no card, and E does nothing
    pg.evaluate("([x,y]) => window._palRide.roam.place(x,y,0)", [b["x"] - 40, b["y"] + 30])
    pg.wait_for_timeout(300)
    assert pg.evaluate("() => document.querySelector('.rm-dir').classList.contains('on')") is False
    pg.keyboard.press("e")
    pg.wait_for_timeout(500)
    assert pg.evaluate("() => ({i: window._palRide.roam.inside.on(), d: window.__detail})") == {"i": True, "d": []}
    # in front of it: the building's name, an Open button naming it, a small E
    pg.evaluate("([x,y,yaw]) => window._palRide.roam.place(x,y,yaw)", [b["x"] + 4, b["y"], math.pi])
    pg.wait_for_timeout(400)
    c = pg.evaluate("""() => { var d=document.querySelector('.rm-dir'), g=d.querySelector('.rm-dgo'); return {on:d.classList.contains('on'), nm:d.querySelector('.rm-dnm').textContent, tx:d.querySelector('.rm-dtx').textContent, label:g.getAttribute('aria-label'),
      key:g.querySelector('kbd').textContent, vis:getComputedStyle(d).visibility}; }""")
    assert c["on"] and c["vis"] == "visible" and c["nm"] == NAMES["n1"] and c["tx"] == "Open " + NAMES["n1"] and c["label"] == "Open %s (E)" % NAMES["n1"] and c["key"] == "E"
    pg.keyboard.press("e")
    pg.wait_for_timeout(900)
    assert pg.evaluate("() => window.__detail") == [["node", "n1"]]


def test_the_board_is_solid(roam):
    pg = roam
    st = go_inside(pg)
    b = st["board"]
    assert pg.evaluate("([x,y]) => window._palRide.roam.inside.blocked(x,y)", [b["x"], b["y"]]) is True
    assert pg.evaluate("([x,y]) => window._palRide.roam.inside.blocked(x,y)", [b["x"] + 4, b["y"]]) is False
    pg.evaluate("() => window._palRide.roam.exit(false)")


def test_esc_leaves_the_building_first_then_roam_and_leave_and_the_doorway_do_the_same(roam):
    pg = roam
    st = go_inside(pg)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(1000)
    r = pg.evaluate("() => ({a: window._palRide.roam.active(), i: window._palRide.roam.inside.on(), s: window._palRide.roam.state(), sh: !!window._palRide.roam.inside.shell(), op: +document.getElementById('pal-fpv-veil').style.opacity, d: window.__detail})")
    assert r["a"] is True and r["i"] is False and r["sh"] is False and r["d"] == [] and r["op"] == 0
    assert DOOR1[0] < r["s"]["x"] < DOOR1[0] + 6 and math.cos(r["s"]["yaw"]) > 0.999                    # on the doorstep, facing the street
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(150)
    assert pg.evaluate("() => window._palRide.roam.active()") is False                                    # a second Esc leaves roam as ever
    # the quiet Leave button, then walking into the doorway
    pg.evaluate("() => window._palRide.roam.enter(%r, %r, Math.PI, {hold:false})" % (DOOR1[0] + 9, DOOR1[1]))
    pg.wait_for_timeout(300)
    pg.evaluate("() => window._palRide.roam.place(%r, %r, Math.PI)" % (DOOR1[0] + 9, DOOR1[1]))
    pg.wait_for_timeout(600)
    pg.keyboard.press("e")
    pg.wait_for_timeout(1300)
    assert pg.evaluate(INS)["on"]
    pg.click(".rm-lv")
    pg.wait_for_timeout(900)
    assert pg.evaluate("() => ({a: window._palRide.roam.active(), i: window._palRide.roam.inside.on()})") == {"a": True, "i": False}
    pg.evaluate("() => window._palRide.roam.place(%r, %r, Math.PI)" % (DOOR1[0] + 9, DOOR1[1]))                  # turn round to the door and go in again
    pg.wait_for_timeout(600)
    pg.keyboard.press("e")
    pg.wait_for_timeout(1300)
    assert pg.evaluate(INS)["on"]
    d = pg.evaluate("() => window._palRide.roam.inside.state().door")
    pg.evaluate("([x,y,yaw]) => window._palRide.roam.place(x,y,yaw)", [d["x"] - 6, d["y"], 0])           # 6 units in, facing the door
    pg.wait_for_timeout(100)
    pg.keyboard.down("w")
    pg.wait_for_timeout(1600)
    pg.keyboard.up("w")
    pg.wait_for_timeout(900)
    assert pg.evaluate("() => ({a: window._palRide.roam.active(), i: window._palRide.roam.inside.on()})") == {"a": True, "i": False}
    pg.evaluate("() => window._palRide.roam.exit(false)")


def test_leaving_roam_by_the_back_to_the_map_button_tears_the_building_down(roam):
    pg = roam
    go_inside(pg)
    pg.click("[data-roam=exit]")
    pg.wait_for_timeout(300)
    r = pg.evaluate("() => ({a: window._palRide.roam.active(), i: window._palRide.roam.inside.on(), sh: !!window._palRide.roam.inside.shell(), cls: document.getElementById('pal-ride').classList.contains('rm-in')})")
    assert r == {"a": False, "i": False, "sh": False, "cls": False}
    pg.evaluate("() => window._palRide.roam.enter(%r, %r, Math.PI, {hold:true})" % (DOOR1[0] + 40, DOOR1[1]))            # and the next roam is a street again
    assert pg.evaluate("() => window._palRide.roam.inside.blocked(1,1)") is None
    pg.evaluate("() => window._palRide.roam.exit(false)")
