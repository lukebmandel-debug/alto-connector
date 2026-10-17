"""1.9.100 FPV phase 1 (alto/build/palace_ride_door.py, palace_ride_e.py, palace_ride_a/b/d/gl): entering the node buildings from roam, and human scale.

Source assertions always run. The runtime checks put the real RIDE_JS / RIDE_CSS in a bare page over the 1.9.95 roam tests' synthetic city (a lattice of blocks, a river, a
bridge) with two NODE buildings (P.at / lot) and a stub of the page's showDetail / detail-open class, and run in WebKit and Chromium (skipped without Playwright):
    ALTO_REPO=$PWD _qa/kit/py -m pytest -q tests/test_palace_2000_fpv.py
"""
import json
import math
import os
import sys

import pytest

from alto.build import palace_ride, palace_ride_a, palace_ride_b, palace_ride_d, palace_ride_door, palace_ride_e, palace_ride_gl, palace_ride_gl_shaders

sys.path.insert(0, os.path.dirname(__file__))
import test_palace_1995_ride_roam as base  # noqa: E402  (the synthetic city)

JSE = palace_ride_e.JS_E


# ───────────────────────────── source contract ─────────────────────────────
def test_the_door_part_is_assembled_into_the_ride():
    assert palace_ride_door.JS_DOOR_GEO in palace_ride.RIDE_JS and palace_ride_door.JS_DOORS in palace_ride.RIDE_JS
    assert palace_ride_door.CSS_DOOR in palace_ride.RIDE_CSS
    assert "/*@DOORS@*/" not in palace_ride.RIDE_JS                                         # the splice happened
    for f in ("function nodeDoor(L, id)", "function glDoor(b,s)", "function findDoor()", "function openDoor()", "function comeBack()", "function doorKey(e)"):
        assert f in palace_ride.RIDE_JS


def test_a_node_building_gets_its_door_in_the_gatherer_and_the_renderer():
    assert "s.door=nodeDoor(L,id)" in palace_ride_b.JS_B
    assert "if(s.door) glDoor(b,s);" in palace_ride_gl._JS_GL_BUILD
    fs = palace_ride_gl_shaders.FS_WORLD
    assert "the glass leaves of a node building's door" in fs and "the soft light under a canopy" in fs        # materials 25 and 26
    assert "bx(-1.3,-.03,.03,.07,.4,2.55,25)" in palace_ride_door.JS_DOOR_GEO and "gflat(b,[q0[0],q0[1]" in palace_ride_door.JS_DOOR_GEO


def test_the_prompt_is_quiet():
    j = palace_ride_door.JS_DOORS
    assert "DOOR_IN=12" in j and "DOOR_OUT=15" in j                                           # ~12 units, held to 15 so it does not flicker
    assert "H.pn.textContent=d.name" in j and "Press E to go in." in j                         # the real name, announced politely
    css = palace_ride_door.CSS_DOOR
    assert ".rm-pin" in css and "rm-left" in css and "prefers-reduced-motion" in css
    for gamey in ("bounce", "@keyframes", "pulse", "infinite"):
        assert gamey not in css and gamey not in j
    assert "<kbd aria-hidden=\"true\">E</kbd>" in JSE                                          # a very small key cap, hidden from a screen reader (the pin has its own label)


def test_roam_is_left_before_the_page_opens_and_entered_again_when_it_closes():
    j = palace_ride_door.JS_DOORS
    assert j.index("exitCore(false);") < j.index("window.showDetail('node', mem.id)")           # roam's key capture is off before the page's typing starts
    assert "attributeFilter:['class']" in j and "detail-open" in j and "comeBack" in j
    assert "{view:mem.view" in j                                                              # leaving roam afterwards still gives the map back as it was before the first entry
    assert "reduced()" in j and "FADE_MS" in j                                                # a plain cross-fade, no dolly, under reduced motion
    assert "function exit(stay){ exitCore(stay); }" in JSE and "doorReset(); S.on=false;" in JSE


def test_human_scale_constants():
    for k in ("walk:1.95", "brisk:5.2", "jog:9.1", "eye:2.15", "PRGL:1.3", "bob:.03"):
        assert k in JSE
    assert abs(1.95 / 1.3 - 1.5) < 0.01 and abs(5.2 / 1.3 - 4) < 0.01 and abs(9.1 / 1.3 - 7) < 0.01 and abs(2.15 / 1.3 - 1.65) < 0.01      # m/s and m at 1.3 units a metre
    assert "stepHz(S.speed/UM)" in JSE and "function stepHz(v)" in palace_ride_b.JS_B
    assert "var GL_NEAR=.5" in palace_ride_gl._JS_GL_MAIN
    assert "fpFoc(W,H)" in JSE and "fpFoc(W,H)" in palace_ride_d.JS_D
    assert "var FOV_H=90" in palace_ride_b.JS_B
    assert "var WALK_V=6.5, WALK_FULL=130;" in palace_ride_a.JS_A                               # 5 m/s


def test_a_ride_to_a_node_building_offers_its_page_on_arrival():
    d = palace_ride_d.JS_D
    assert "function canOpen(id)" in d and "function openArrived(id)" in d and "Press E to open its page." in d
    assert "window._palTr.clear()" in d and "window.showDetail('node', nid)" in d


# ───────────────────────────── runtime ─────────────────────────────
pw = base.pw
WW, HH = base.WW, base.HH
# two node lots in empty blocks: n1 in block (14,5) (x 3960..4200, y 2000..2320), centred, so its door is on the east face (the tie goes to the first of the two long faces);
# n2 in block (15,5) hugging the west street x = 4200, so its door is on its west face
LOTS = {"k1": [4080, 2160, 100, 140, 0], "k2": [4262, 2160, 100, 140, 0]}
AT = {"n1": "k1", "n2": "k2"}
NAMES = {"n1": "1.1 The Civil Action", "n2": "1.2 Selecting the Proper Court"}
DOOR1 = (4130, 2160, 1, 0)
DOOR2 = (4212, 2160, -1, 0)


def _city():
    M, P, fg = base._city()
    ring = fg["1"]["k"]["u"]["null"]
    ring[:] = [r for r in ring if not (r["n"].endswith(("14,5,0", "14,5,1", "14,5,2", "15,5,0", "15,5,1", "15,5,2")) or r["n"].startswith("L 14,5") or r["n"].startswith("L 15,5"))]
    P["at"] = AT
    return M, P, fg


STUB = r"""
(function(){
  var D=%s, M=D.M, P=D.P, FG=D.fg, LOTS=D.lots, NAMES=D.names; window.__put=[]; window.__view={z:.5,x:123,y:456}; window.__detail=[]; window.__cleared=0; window.__keys=[];
  window._palTr={state:function(){ return {}; }, clear:function(){ window.__cleared++; }};
  window._palDir={legPlan:function(a,b,m){ return {legs:[{k:'walk', pts:[[3940,2160],[4040,2160]]}], lines:[]}; }};
  /* the page's showDetail, in short: it opens a page over the map and says so with the class on <html> (engine/timeline_template.html); the page closes by taking the class off */
  window.showDetail=function(type,id){ window.__detail.push([type,id]); document.documentElement.classList.add('detail-open'); };
  window.closeDetail=function(){ document.documentElement.classList.remove('detail-open'); };
  window.addEventListener('keydown', function(e){ window.__keys.push(e.key); });
  window._palRide.init({M:M, P:P, lot:function(k){ return LOTS[k]||null; }, bOf:function(id){ return id; }, ucol:function(){ return null; }, dcol:function(){ return null; },
    tubeCol:function(c){ return c||'#889'; }, NEUTRAL:function(){ return '#889'; }, nbH:function(){ return 30; }, name:function(id){ return NAMES[id]||id; },
    fillGroups:function(){ return {1:FG['1'], 2:{}, 3:{}, 4:{}}; },
    curView:function(){ return {z:window.__view.z, x:window.__view.x, y:window.__view.y}; }, putView:function(v){ window.__put.push(v); }});
})();
"""


def _html():
    M, P, fg = _city()
    return ("<!doctype html><html class=\"alto-palace\"><head><meta charset=\"utf-8\"><style>html,body{margin:0;background:#cdd}#canvas{position:fixed;left:0;top:0;width:1400px;height:900px}"
            + palace_ride.RIDE_CSS + "</style></head><body><div id=\"canvas\"></div><script>" + palace_ride.RIDE_JS + "</script><script>"
            + STUB % json.dumps({"M": M, "P": P, "fg": fg, "lots": LOTS, "names": NAMES}) + "</script></body></html>")


@pytest.fixture(scope="module", params=["webkit", "chromium"])
def page(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch() if request.param == "webkit" else p.chromium.launch()
        except Exception:
            try:
                if request.param != "chromium":
                    raise
                b = p.chromium.launch(channel="chrome")
            except Exception as e:
                pytest.skip("no %s: %s" % (request.param, e))
        ctx = b.new_context(viewport={"width": 1400, "height": 900})
        pg = ctx.new_page()
        pg.errs = []
        pg.on("pageerror", lambda e: pg.errs.append(str(e)))
        pg.set_content(_html())
        pg.wait_for_function("() => window._palRide && window._palRide.roam")
        yield pg
        assert pg.errs == []
        b.close()


@pytest.fixture
def roam(page):
    page.evaluate("""() => { var r=window._palRide.roam; if(r.active()) r.exit(false); window.closeDetail(); window.__put.length=0; window.__detail.length=0; window.__keys.length=0; window.__cleared=0;
      window.__view={z:.5,x:123,y:456}; }""")
    page.wait_for_timeout(60)
    page.evaluate("() => { var v=document.getElementById('pal-fpv-veil'); if(v){ v.style.transition='none'; v.style.opacity='0'; } }")
    page.emulate_media(reduced_motion="no-preference")
    yield page
    page.evaluate("() => { var r=window._palRide.roam; if(r.active()) r.exit(false); window.closeDetail(); }")
    page.wait_for_timeout(60)


def stand(pg, dx, yaw, dy=0, door=DOOR1, hold=True):
    """Enter roam (frame loop held: the tests drive time) and stand dx units out from the door along its normal, facing `yaw`."""
    pg.evaluate("([x,y,yaw,hold]) => { var R=window._palRide.roam; if(!R.active()) R.enter(x,y,yaw,{hold:hold}); R.place(x,y,yaw); R.look(yaw,0); R.settle(); }",
                [door[0] + door[2] * dx, door[1] + dy, yaw, hold])


def tickdoor(pg, n=30, dt=0.05):
    pg.evaluate("([n,dt]) => { var R=window._palRide.roam; for(var i=0;i<n;i++) R.door.frame(dt); R.draw(); }", [n, dt])


def test_each_node_building_has_a_door_on_the_street_side(roam):
    pg = roam
    stand(pg, 9, math.pi)
    doors = pg.evaluate("() => window._palRide.roam.door.near().map(function(s){ return [s.id, s.door.x, s.door.y, s.door.nx, s.door.ny, s.door.name]; })")
    by = {d[0]: d for d in doors}
    assert "n1" in by                                                                           # the ones in the cells round me
    stand(pg, 9, math.pi, door=DOOR2)
    doors = pg.evaluate("() => window._palRide.roam.door.near().map(function(s){ return [s.id, s.door.x, s.door.y, s.door.nx, s.door.ny, s.door.name]; })")
    by = {d[0]: d for d in doors}
    assert by["n1"][1:5] == pytest.approx(list(DOOR1), abs=1e-6) and by["n1"][5] == NAMES["n1"]
    assert by["n2"][1:5] == pytest.approx(list(DOOR2), abs=1e-6) and by["n2"][5] == NAMES["n2"]       # n2 hugs the west street: its west face


def test_the_prompt_shows_the_real_name_only_when_facing_a_door_closely(roam):
    pg = roam
    cur = "() => { var c=window._palRide.roam.door.cur(); return c&&c.name; }"
    pin = "() => { var p=document.querySelector('.rm-pin'); var cs=getComputedStyle(p); return {on:p.classList.contains('on'), vis:cs.visibility, name:p.querySelector('.rm-pn').textContent, label:p.getAttribute('aria-label'), live:document.querySelector('.rm-live').textContent, tab:p.tabIndex, inLeft:!!p.closest('.rm-left'), key:p.querySelector('kbd').textContent}; }"
    stand(pg, 30, math.pi)                                                                      # too far
    tickdoor(pg)
    assert pg.evaluate(cur) is None and not pg.evaluate(pin)["on"]
    stand(pg, 9, math.pi)                                                                       # close and facing it
    tickdoor(pg, 4)
    assert pg.evaluate(cur) is None                                                             # not at once: a quarter of a second (no flicker while passing)
    tickdoor(pg, 30)
    assert pg.evaluate(cur) == NAMES["n1"]
    p = pg.evaluate(pin)
    assert p["on"] and p["name"] == NAMES["n1"] and p["label"] == "Enter %s (E)" % NAMES["n1"] and p["tab"] == 0 and p["inLeft"] and p["key"] == "E"
    assert NAMES["n1"] in p["live"] and "Press E" in p["live"]
    assert pg.evaluate("() => window._palRide.roam.door.state().glow") == pytest.approx(1, abs=1e-6)
    stand(pg, 9, 0)                                                                             # turned away from it
    tickdoor(pg, 40)
    assert pg.evaluate(cur) is None and not pg.evaluate(pin)["on"]
    stand(pg, 9, math.pi, dy=40)                                                                # 40 units along the wall: not within the 12
    tickdoor(pg, 30)
    assert pg.evaluate(cur) is None


def test_no_prompt_over_the_hint_text_and_the_street_card_keeps_working(roam):
    pg = roam
    stand(pg, 9, math.pi)
    tickdoor(pg, 30)
    t = pg.evaluate("() => ({st: document.querySelector('.rm-st').textContent, ar: document.querySelector('.rm-ar').textContent, hint: document.querySelector('.rm-hint').textContent, where: !!document.querySelector('.rm-left > .rm-where')})")
    assert t["st"] and t["where"] and "Shift" in t["hint"] and "Esc" in t["hint"]
    assert "Press" not in t["hint"] and " E " not in t["hint"]                                  # the prompt is not a standing instruction


def test_e_goes_in_a_dolly_toward_the_door_then_the_page_opens_over_the_map(roam):
    pg = roam
    stand(pg, 9, math.pi, hold=False)
    pg.wait_for_timeout(500)
    pg.evaluate("() => window._palRide.roam.place(%r, %r, Math.PI)" % (DOOR1[0] + 9, DOOR1[1]))
    pg.wait_for_timeout(500)
    assert pg.evaluate("() => (window._palRide.roam.door.cur()||{}).name") == NAMES["n1"]
    before = pg.evaluate("() => window._palRide.roam.state()")
    pg.keyboard.press("e")
    pg.wait_for_timeout(200)
    mid = pg.evaluate("() => ({s: window._palRide.roam.state(), d: window._palRide.roam.door.state()})")
    assert mid["d"]["busy"] == 1 and mid["d"]["cine"] and 0 < mid["d"]["veil"] <= 1             # the dark veil is coming in
    assert mid["s"]["x"] < before["x"] and mid["s"]["x"] > DOOR1[0] + 1.3 - 0.01                 # the camera walks toward the door ... never through the wall (no nearer than the player radius)
    assert pg.evaluate("() => window.__detail") == []
    pg.wait_for_timeout(700)
    end = pg.evaluate("() => ({a: window._palRide.roam.active(), ride: window._palRide.active(), d: window.__detail, cls: document.documentElement.classList.contains('detail-open'), put: window.__put, st: window._palRide.roam.door.state(), fp: document.documentElement.classList.contains('pal-fp')})")
    assert end["a"] is False and end["ride"] is False and end["fp"] is False                    # roam is off (its key capture with it)
    assert end["d"] == [["node", "n1"]] and end["cls"] is True
    assert end["put"] == [{"z": 0.5, "x": 123, "y": 456}]                                       # the aerial map went back under the veil (the page remembers it)
    assert end["st"]["mem"]["x"] == pytest.approx(before["x"], abs=0.5) and end["st"]["ret"] and end["st"]["opened"]
    pg.wait_for_timeout(500)
    assert pg.evaluate("() => +document.getElementById('pal-fpv-veil').style.opacity") == 0     # and the veil is gone from the page
    # the page's own typing works: nothing swallows keys any more
    pg.evaluate("() => { window.__keys.length=0; }")
    pg.keyboard.press("x")
    pg.keyboard.press("e")
    assert pg.evaluate("() => window.__keys") == ["x", "e"]
    assert pg.evaluate("() => window.__detail.length") == 1                                     # (the E on the page did not open another)


def test_closing_the_page_returns_to_the_same_spot_yaw_and_pitch(roam):
    pg = roam
    stand(pg, 9, math.pi, hold=False)
    pg.evaluate("() => window._palRide.roam.place(%r, %r, Math.PI)" % (DOOR1[0] + 9, DOOR1[1] + 1.5))
    pg.evaluate("() => window._palRide.roam.look(Math.PI+.12, .09)")
    pg.wait_for_timeout(600)
    assert pg.evaluate("() => (window._palRide.roam.door.cur()||{}).name") == NAMES["n1"]
    spot = pg.evaluate("() => window._palRide.roam.state()")
    pg.keyboard.press("e")
    pg.wait_for_timeout(900)
    assert pg.evaluate("() => window._palRide.roam.active()") is False
    pg.evaluate("() => window.closeDetail()")
    pg.wait_for_timeout(60)
    early = pg.evaluate("() => ({a: window._palRide.roam.active(), op: +document.getElementById('pal-fpv-veil').style.opacity, d: window._palRide.roam.door.state()})")
    assert early["a"] is True and early["d"]["busy"] == 3                                       # back in roam at once, under the veil, backing out
    pg.wait_for_timeout(700)
    back = pg.evaluate("() => ({s: window._palRide.roam.state(), d: window._palRide.roam.door.state(), op: +document.getElementById('pal-fpv-veil').style.opacity, put: window.__put.length})")
    assert back["s"]["x"] == pytest.approx(spot["x"], abs=1e-6) and back["s"]["y"] == pytest.approx(spot["y"], abs=1e-6)
    assert back["s"]["yaw"] == pytest.approx(spot["yaw"], abs=1e-6) and back["s"]["pitch"] == pytest.approx(spot["pitch"], abs=1e-6)
    assert back["d"]["busy"] == 0 and back["d"]["ret"] is False and back["op"] == 0
    # walking and Esc work again; leaving gives the map back as it was before the FIRST entry
    pg.evaluate("() => { window.__put.length=0; window.__view={z:9,x:9,y:9}; }")                 # (the page's current view must not be what is restored)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(100)
    assert pg.evaluate("() => ({a: window._palRide.roam.active(), put: window.__put})") == {"a": False, "put": [{"z": 0.5, "x": 123, "y": 456}]}


def test_reduced_motion_has_no_dolly_only_a_crossfade(roam):
    pg = roam
    stand(pg, 9, math.pi, hold=False)
    pg.evaluate("() => window._palRide.roam.place(%r, %r, Math.PI)" % (DOOR1[0] + 9, DOOR1[1]))
    pg.wait_for_timeout(600)
    spot = pg.evaluate("() => window._palRide.roam.state()")
    pg.emulate_media(reduced_motion="reduce")
    pg.keyboard.press("e")
    xs = []
    for _ in range(4):
        pg.wait_for_timeout(50)
        xs.append(pg.evaluate("() => window._palRide.roam.state().x"))
    assert all(x == pytest.approx(spot["x"], abs=1e-6) for x in xs)                              # the camera does not move
    pg.wait_for_timeout(500)
    assert pg.evaluate("() => window.__detail") == [["node", "n1"]]
    pg.evaluate("() => window.closeDetail()")
    pg.wait_for_timeout(500)
    s = pg.evaluate("() => window._palRide.roam.state()")
    assert pg.evaluate("() => window._palRide.roam.active()") and s["x"] == pytest.approx(spot["x"], abs=1e-6) and s["yaw"] == pytest.approx(spot["yaw"], abs=1e-6)


def test_esc_during_the_dolly_cancels_it_and_esc_otherwise_still_leaves(roam):
    pg = roam
    stand(pg, 9, math.pi, hold=False)
    pg.evaluate("() => window._palRide.roam.place(%r, %r, Math.PI)" % (DOOR1[0] + 9, DOOR1[1]))
    pg.wait_for_timeout(600)
    pg.keyboard.press("e")
    pg.wait_for_timeout(90)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(500)
    r = pg.evaluate("() => ({a: window._palRide.roam.active(), d: window._palRide.roam.door.state(), detail: window.__detail, op: +document.getElementById('pal-fpv-veil').style.opacity})")
    assert r["a"] is True and r["d"]["busy"] == 0 and r["detail"] == [] and r["op"] == 0
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(100)
    assert pg.evaluate("() => window._palRide.roam.active()") is False


def test_a_click_on_the_door_or_the_pin_or_enter_on_the_focused_pin_goes_in_but_a_drag_only_looks(roam):
    pg = roam
    stand(pg, 9, math.pi, hold=False)
    pg.evaluate("() => window._palRide.roam.place(%r, %r, Math.PI)" % (DOOR1[0] + 9, DOOR1[1]))
    pg.wait_for_timeout(700)
    hit = pg.evaluate("() => window._palRide.roam.door.hit()")
    assert hit and hit[2] > hit[0] + 40
    cx, cy = (hit[0] + hit[2]) / 2, (hit[1] + hit[3]) / 2
    pg.mouse.move(cx, cy)
    pg.wait_for_timeout(60)
    assert pg.evaluate("() => document.getElementById('pal-ride').classList.contains('rm-dh')")      # the pointer says "this is clickable"
    yaw0 = pg.evaluate("() => window._palRide.roam.state().yaw")
    pg.mouse.down()
    pg.mouse.move(cx + 80, cy, steps=5)                                                               # a drag across the door: looks around, does not open it
    pg.mouse.up()
    pg.wait_for_timeout(100)
    assert pg.evaluate("() => window._palRide.roam.state().yaw") != yaw0 and pg.evaluate("() => window.__detail") == []
    hit = pg.evaluate("() => window._palRide.roam.door.hit()")
    pg.evaluate("() => window._palRide.roam.look(Math.PI, 0)")
    pg.wait_for_timeout(300)
    hit = pg.evaluate("() => window._palRide.roam.door.hit()")
    pg.mouse.click((hit[0] + hit[2]) / 2, (hit[1] + hit[3]) / 2)
    pg.wait_for_timeout(1000)
    assert pg.evaluate("() => window.__detail") == [["node", "n1"]]
    # the pin: Tab reaches it, Enter on it opens
    pg.evaluate("() => { window.closeDetail(); window.__detail.length=0; }")
    pg.wait_for_timeout(900)
    assert pg.evaluate("() => window._palRide.roam.active()")
    pg.wait_for_timeout(300)
    assert pg.evaluate("() => (window._palRide.roam.door.cur()||{}).name") == NAMES["n1"]
    pg.keyboard.press("Tab")
    assert pg.evaluate("() => document.activeElement && document.activeElement.className") == "rm-pin on"
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(1000)
    assert pg.evaluate("() => window.__detail") == [["node", "n1"]]


def test_e_does_nothing_away_from_a_door_and_other_keys_are_unchanged(roam):
    pg = roam
    stand(pg, 40, math.pi, hold=False)
    pg.wait_for_timeout(300)
    pg.keyboard.press("e")
    pg.wait_for_timeout(200)
    assert pg.evaluate("() => ({a: window._palRide.roam.active(), d: window.__detail, k: window.__keys})") == {"a": True, "d": [], "k": []}      # swallowed like every roam key
    pg.evaluate("() => window._palRide.roam.exit(false)")


# ── human scale ──
def test_the_pace_is_a_person_s(roam):
    pg = roam
    pg.evaluate("() => window._palRide.roam.enter(1320, 1900, -Math.PI/2, {hold: true})")
    mps = pg.evaluate("""() => { var R=window._palRide.roam, v=function(keys,secs,run){ R.place(1320,1900,-Math.PI/2); var d=1/60, n=Math.round(secs/d); R.tick(d, keys, run); for(var i=0;i<n;i++) R.tick(d, keys, run); return R.state().speed/1.3; }; return {walk:v('f',3,false), brisk:v('f',1.5,true), jog:v('f',9,true)}; }""")
    assert 1.3 <= mps["walk"] <= 1.6                                                              # 1.5 m/s
    assert 3.6 <= mps["brisk"] <= 4.2                                                             # holding Shift: a brisk 4 m/s
    assert 6.5 <= mps["jog"] <= 7.2                                                               # held for seconds: a 7 m/s jog, the most you ever get
    pg.evaluate("() => window._palRide.roam.exit(false)")


def test_eye_height_is_165_m_the_bob_is_one_per_footfall_and_only_while_walking(roam):
    pg = roam
    pg.evaluate("() => window._palRide.roam.enter(1320, 1900, -Math.PI/2, {hold: true})")
    z = pg.evaluate("""() => { var R=window._palRide.roam, o={}; R.draw(); o.rest=R.state().camZ; var lo=1e9, hi=-1e9, ph=[]; R.tick(1/60,'f',false);
      for(var i=0;i<240;i++){ R.tick(1/60,'f',false); R.draw(); var c=R.state().camZ; if(i>60){ lo=Math.min(lo,c); hi=Math.max(hi,c); ph.push(c); } }
      o.lo=lo; o.hi=hi; var up=0; for(var k=2;k<ph.length;k++) if(ph[k-1]>ph[k-2] && ph[k-1]>=ph[k]) up++; o.bobs=up; o.secs=ph.length/60;
      R.tick(1/60,'x',false); for(var j=0;j<120;j++){ R.tick(1/60,'x',false); } R.draw(); o.stop=R.state().camZ; return o; }""")
    assert z["rest"] == pytest.approx(2.15) and 2.15 / 1.3 == pytest.approx(1.65, abs=0.01)
    assert 0.04 <= z["hi"] - z["lo"] <= 0.09                                                      # a few centimetres, not the old 14 cm
    assert 1.6 <= z["bobs"] / z["secs"] <= 2.4                                                    # about two footfalls a second at a walk
    assert z["stop"] == pytest.approx(2.15, abs=1e-6)                                             # standing still: no bob
    pg.evaluate("() => window._palRide.roam.exit(false)")


@pytest.mark.parametrize("size,hfov,vfov", [((1920, 1080), 90, 58.7), ((1400, 900), 90, 65), ((1000, 800), 82.2, 70), ((2400, 1000), 90, None)])
def test_the_view_is_street_views_ninety_degrees_across(roam, size, hfov, vfov):
    pg = roam
    pg.set_viewport_size({"width": size[0], "height": size[1]})
    pg.wait_for_timeout(100)
    pg.evaluate("() => window._palRide.roam.enter(1320, 1900, -Math.PI/2, {hold: true})")
    pg.evaluate("() => window._palRide.roam.draw()")
    s = pg.evaluate("() => window._palRide.roam.state()")
    assert s["hfov"] == pytest.approx(hfov, abs=0.6)
    if vfov:
        assert s["vfov"] == pytest.approx(vfov, abs=0.8)
    assert 40 - 0.5 <= s["vfov"] <= 70 + 0.5 and s["hfov"] <= 110 + 0.5                           # never a fisheye, never a letterbox
    pg.evaluate("() => window._palRide.roam.exit(false)")
    pg.set_viewport_size({"width": 1400, "height": 900})


def test_pitch_limits_are_kept(roam):
    pg = roam
    pg.evaluate("() => window._palRide.roam.enter(1320, 1900, 0, {hold: true})")
    p = pg.evaluate("() => { var R=window._palRide.roam; R.look(null, 5); var a=R.state().pitch; R.look(null, -5); return [a, R.state().pitch]; }")
    assert p == [pytest.approx(0.42), pytest.approx(-0.42)]
    pg.evaluate("() => window._palRide.roam.exit(false)")


def test_walking_legs_play_at_a_person_s_pace_when_the_30_seconds_allow(roam):
    """The model's own timeline (a ride along a plain path), read in the page."""
    pg = roam
    js = """(p) => { var M=window._palRide.build({opt:{legs:[{k:'walk', pts:p}], lines:[]}}, false, 'walk'); var mv=M.ev.filter(function(e){ return e.k==='move'; })[0]; return {T:M.T, L:M.L, v:Math.abs(mv.s1-mv.s0)/(mv.t1-mv.t0), D:Math.abs(mv.s1-mv.s0), t:mv.t1-mv.t0}; }"""
    short = pg.evaluate(js, [[1000, 1000], [1100, 1000]])                                         # ~100 units = 77 m
    mid = pg.evaluate(js, [[1000, 1000], [1160, 1000]])
    long = pg.evaluate(js, [[1000, 1000], [1000, 6000]])
    assert short["v"] / 1.3 <= 6.5                                                                # at most a brisk walk (5 m/s) plus the soft start and stop of the ride's ease
    assert mid["T"] <= 30 and mid["v"] / 1.3 < 12                                                 # a 125 m walk still plays about as long as it takes
    assert long["T"] == pytest.approx(30, abs=0.01) and long["v"] / 1.3 > 40                       # a very long walk is still compressed into the 30 s


def test_a_ride_to_a_node_building_ends_with_its_page_on_e(roam):
    pg = roam
    pg.evaluate("() => window._palRide.setPref('fp')")
    assert pg.evaluate("() => window._palRide.demo('n1', 'n2', 'walk')") is True
    pg.evaluate("() => window._palRide.simTo(window._palRide.model().T)")
    pg.wait_for_timeout(200)
    chip = pg.evaluate("() => ({t: document.querySelector('.pr-chip').textContent, k: !!document.querySelector('.pr-chip kbd'), live: document.querySelector('#pal-ride .pr-live').textContent})")
    assert NAMES["n2"] in chip["t"] and chip["k"] and "Press E" in chip["live"]
    pg.keyboard.press("e")
    pg.wait_for_timeout(400)
    assert pg.evaluate("() => ({d: window.__detail, c: window.__cleared})") == {"d": [["node", "n2"]], "c": 1}
    pg.evaluate("() => { window._palRide.exit(); window.closeDetail(); }")
    pg.wait_for_timeout(100)
