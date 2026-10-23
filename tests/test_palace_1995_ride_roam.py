"""1.9.95 first-person city, ROAM (alto/build/palace_ride_e.py): walking anywhere at street level.

Source assertions always run. The runtime checks build a small SYNTHETIC city (a lattice of blocks with buildings, one concave, a landmark, a river with one
bridge) and put the real RIDE_JS / RIDE_CSS in a bare page with stubs for the palace's own parts, so they need no Philadelphia data; they run in WebKit and
Chromium and are skipped when Playwright (or a browser) is missing. Run them with the QA kit's python:  ALTO_REPO=$PWD _qa/kit/py -m pytest -q tests/test_palace_1995_ride_roam.py
"""
import json
import math
import re

import pytest

from alto.build import palace_ride, palace_ride_e

JS = palace_ride_e.JS_E


def test_roam_is_assembled_into_the_ride_and_exported():
    assert palace_ride_e.JS_E in palace_ride.RIDE_JS and palace_ride_e.CSS_E in palace_ride.RIDE_CSS
    assert "roam:(typeof ROAM!=='undefined'?ROAM:null)" in palace_ride.RIDE_JS
    for api in ("enter:enter", "exit:exit", "active:function(){ return S.on; }"):
        assert api in JS
    assert "function enter(x,y,heading,opts)" in JS and "function exit(stay)" in JS


def test_collision_is_a_free_circle_test_with_a_wall_slide_and_a_near_plane_margin():
    assert "PR:2.4" in JS and "PRGL:.85" in JS and "PR3:.45" in JS                                              # a little more than the renderer's NEARZ (1.8), so a wall never clips away
    assert "function blockedAt(x,y)" in JS and "function ringHit(" in JS and "function moveStep(dx,dy)" in JS
    assert "function normalAt(" in JS and "function cut(" in JS          # contact by binary search, normal by sampling, then the rest of the move slides
    assert "QUAL=['b','node','fill','lm']" in JS and "s.collide" in JS
    assert "function freeNear(" in JS                                  # a spawn inside a building / the river is moved out
    assert "x>E.M.W-CFG.edge" in JS                                    # the city's edge


def test_water_is_closed_except_on_a_bridge_deck():
    assert "function inWaterZone(" in JS and "function onDeck(" in JS
    assert "(s.o||s.br)" in JS                                         # a bridge = a street the data marks as crossing water
    assert "inWaterZone(x,y,0) && !onDeck(x,y)" in JS
    assert "'plat'" in JS                                              # a deck and its parapets are drawn as low solids


def test_the_world_is_streamed_cell_by_cell_without_flash():
    assert "gatherWorld(set,null)" in JS and "function plan(force)" in JS and "function stream(sync)" in JS
    assert "CFG.budget" in JS                                          # a few ms of building per frame
    assert "load:1450" in JS and "keep:1900" in JS                     # cells appear beyond most of the fog and go only once well behind
    assert "Wd.cells=S.cells" in JS and "Wd.ver=++S.ver" in JS         # one persistent world, per-cell worlds for a renderer that caches by cell
    assert "_pa.x=-1e9" in JS                                          # gatherWorld's path-near big-park rule is the roamer's own business
    assert "drawCity(ctx, W, H, R.PAL, S.W, S.yaw, S.tm, null)" in JS  # the shared renderer, `way` = null
    assert "sceneryUpdate(S.W, S.tm, C)" in JS


def test_keys_are_swallowed_in_capture_and_esc_leaves():
    assert "window.addEventListener('keydown', onKey, true)" in JS and "window.addEventListener('keyup', onKey, true)" in JS
    assert "e.stopImmediatePropagation()" in JS and "e.key==='Escape'" in JS
    assert "e.metaKey||e.ctrlKey||e.altKey" in JS                      # browser shortcuts stay the browser's
    assert "passive:false" in JS                                       # the wheel does not zoom the map under the overlay


def test_exit_restores_the_aerial_view_or_stays_where_you_stood():
    assert "R.saved=view" in JS and "closeNow(true,false)" in JS       # the same restore as a ride (palace.py putView / restoreView)
    assert "function viewFor(x,y,z)" in JS and "MXC=90" in JS
    assert "(x+MXC)*z+gx-cw/2" in JS                                   # palace.py center() / flyMap()
    assert "stayZoom" in JS


def test_hud_has_compass_street_cross_street_district_hint_and_buttons():
    for part in ("rm-compass", "rm-where", "rm-st", "rm-cx", "rm-ar", "rm-hint", 'data-roam="exit"', 'data-roam="stay"', "aria-live"):
        assert part in JS
    assert "between " in JS and "'at '" in JS and "'near '" in JS
    assert "E.P.d" in JS and "M.areas" in JS
    css = palace_ride_e.CSS_E
    assert "#pal-ride.rm .pr-chip" in css and "prefers-reduced-motion" in css
    assert "reduced()?0:Math.sin(S.phase)" in JS                       # no footstep bob under reduced motion


def test_palace_ride_d_is_untouched_by_roam():
    # roam reuses ensureOverlay / openOv / closeNow / drawCity as they are
    src = open(palace_ride.__file__.replace("palace_ride.py", "palace_ride_d.py"), encoding="utf-8").read()
    assert "ROAM" not in src


# ───────────────────────────── runtime: a synthetic city ─────────────────────────────
try:
    import playwright.sync_api as pw
except ImportError:                                                    # pragma: no cover
    pw = None

WW, HH = 6000, 4000
RIVER_X = 3120
BRIDGE_Y = 2000


def _city():
    """Lattice blocks 240 x 320 from (600, 400); a river down x = 3120; one bridge street at y = 2000; buildings in the blocks (one concave L)."""
    xs = [600 + 240 * i for i in range(21)]
    ys = [400 + 320 * j for j in range(11)]
    tiles, ring_list, streets = [], [], []
    for i in range(20):
        for j in range(10):
            x0, x1, y0, y1 = xs[i], xs[i + 1], ys[j], ys[j + 1]
            tiles.append([x0, y0, x1, y1])
            if abs((x0 + x1) / 2 - RIVER_X) < 150:
                continue
            if (i, j) == (5, 3):
                continue                                                 # the landmark's block
            if (i + j) % 4 == 0:                                         # a concave L
                p = [x0 + 30, y0 + 30, x1 - 30, y0 + 30, x1 - 30, y0 + 120, x0 + 110, y0 + 120, x0 + 110, y1 - 30, x0 + 30, y1 - 30]
                ring_list.append({"p": p, "b": [x0 + 30, y0 + 30, x1 - 30, y1 - 30], "h": 0, "n": "L %d,%d" % (i, j)})
            else:
                for k, b in enumerate(([x0 + 30, y0 + 30, x0 + 110, y1 - 30], [x0 + 130, y0 + 30, x1 - 30, y0 + 140], [x0 + 130, y0 + 170, x1 - 30, y1 - 30])):
                    ring_list.append({"p": [b[0], b[1], b[2], b[1], b[2], b[3], b[0], b[3]], "b": b, "h": 0, "n": "B %d,%d,%d" % (i, j, k)})
    for i, x in enumerate(xs):
        streets.append({"n": "%dth St" % (i + 1), "k": 1, "p": [x, ys[0], x, ys[-1]]})
    for j, y in enumerate(ys):
        name = "%s St" % "ABCDEFGHIJK"[j]
        streets.append({"n": name, "k": 1, "p": [xs[0], y, 3000, y]})
        streets.append({"n": name, "k": 1, "p": [3240, y, xs[-1], y]})
    streets.append({"n": "Bridge St", "k": 1, "o": 1, "p": [3000, BRIDGE_Y, 3240, BRIDGE_Y]})
    river = {"n": "Test River", "w": 100, "p": [v for k in range(41) for v in (RIVER_X, 100 * k)]}
    M = {"W": WW, "H": HH, "tiles": tiles, "tq": [], "parks": [{"n": "Test Park", "k": "park", "z": 4, "r": [[xs[12] + 30, ys[2] + 30, xs[13] - 30, ys[2] + 30, xs[13] - 30, ys[3] - 30, xs[12] + 30, ys[3] - 30]], "p": [], "o": [], "t": [xs[12] + 100, ys[2] + 100]}],
         "river": [river], "streets": streets, "landmarks": [{"n": "Test Hall", "x": 1920, "y": 1520, "r": [], "box": [1830, 1390, 2010, 1650], "page": "x"}],
         "hw": {"roads": []}, "areas": [{"n": "Testville", "x": 3000, "y": 2000, "r": 1}], "rivers": [], "bank": {}}
    P = {"at": {}, "d": [{"u": 0, "n": "Test District", "box": [600, 400, 3000, 2000]}], "lmtop": {}, "tw": {}}
    fg = {"1": {"k": {"ci": 0, "cj": 0, "u": {"null": ring_list}}}}
    return M, P, fg


STUB = r"""
(function(){
  var D=%s, M=D.M, P=D.P, FG=D.fg; window.__put=[]; window.__view={z:.5,x:123,y:456};
  window._palTr={state:function(){ return {}; }, clear:function(){}};
  var cv=document.getElementById('canvas');
  window._palRide.init({M:M, P:P, lot:function(){ return null; }, bOf:function(id){ return id; }, ucol:function(){ return null; }, dcol:function(){ return null; },
    tubeCol:function(c){ return c||'#889'; }, NEUTRAL:function(){ return '#889'; }, nbH:function(){ return 30; }, name:function(id){ return id; },
    fillGroups:function(){ return {1:FG['1'], 2:{}, 3:{}, 4:{}}; },
    curView:function(){ return {z:window.__view.z, x:window.__view.x, y:window.__view.y}; }, putView:function(v){ window.__put.push(v); }});
})();
"""


def _html():
    M, P, fg = _city()
    return ("<!doctype html><html class=\"alto-palace\"><head><meta charset=\"utf-8\"><style>html,body{margin:0;background:#cdd}#canvas{position:fixed;left:0;top:0;width:1400px;height:900px}"
            + palace_ride.RIDE_CSS + "</style></head><body><div id=\"canvas\"></div><script>window._altoFpv={view:'first'};</script><script>" + palace_ride.RIDE_JS + "</script><script>"
            + STUB % json.dumps({"M": M, "P": P, "fg": fg}) + "</script></body></html>")


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
        pg.add_style_tag(content="#pal-ride{transition:none !important}")
        pg.wait_for_function("() => window._palRide && window._palRide.roam")
        yield pg
        assert pg.errs == []
        b.close()


@pytest.fixture
def roam(page):
    page.evaluate("() => { var r=window._palRide.roam; if(r.active()) r.exit(false); window.__put.length=0; window.__view={z:.5,x:123,y:456}; }")
    page.emulate_media(reduced_motion="no-preference")
    yield page


@pytest.fixture
def fast(roam):
    """The collision, water and streaming checks were written for the 1.9.95 pace (14 and 40 units a second): they keep it so they stay short (the 1.9.100 pace is tested in test_palace_2000_fpv.py)."""
    roam.evaluate("() => { var c=window._palRide.roam.cfg; window.__cfg0=[c.walk,c.brisk,c.jog]; c.walk=14; c.brisk=40; c.jog=40; }")
    yield roam
    roam.evaluate("() => { var c=window._palRide.roam.cfg, o=window.__cfg0; c.walk=o[0]; c.brisk=o[1]; c.jog=o[2]; }")


# an independent point-in-ring / distance-to-ring, used to judge the page's own collision
CHECK = """
function ringInfo(r, x, y){ var n=r.length/2, ins=false, d2=1e18, j=n-1;
  for(var i=0;i<n;i++){ var ax=r[2*i], ay=r[2*i+1], bx=r[2*j], by=r[2*j+1];
    if(((ay>y)!=(by>y)) && x < (bx-ax)*(y-ay)/(by-ay)+ax) ins=!ins;
    var ex=bx-ax, ey=by-ay, l2=ex*ex+ey*ey, t=l2?((x-ax)*ex+(y-ay)*ey)/l2:0; t=Math.max(0,Math.min(1,t)); var qx=ax+t*ex-x, qy=ay+t*ey-y; d2=Math.min(d2,qx*qx+qy*qy); j=i; }
  return {inside:ins, d:Math.sqrt(d2)}; }
function worst(R){ var s=R.state(), w={inside:0, min:1e9}; R.rings(s.x,s.y,60).forEach(function(o){ var q=ringInfo(o.ring,s.x,s.y); if(q.inside) w.inside++; if(q.d<w.min) w.min=q.d; }); return w; }
return {worst: worst};
"""


def test_enter_exit_restores_the_aerial_view_and_stay_recentres(roam):
    pg = roam
    assert pg.evaluate("() => window._palRide.roam.enter(1500, 1200, 0, {})") is True
    st = pg.evaluate("() => ({active: window._palRide.roam.active(), fp: document.documentElement.classList.contains('pal-fp'), rm: document.getElementById('pal-ride').classList.contains('rm'), ride: window._palRide.active()})")
    assert st == {"active": True, "fp": True, "rm": True, "ride": True}
    pg.wait_for_timeout(120)
    assert pg.evaluate("() => document.getElementById('pal-ride').classList.contains('on')")
    assert pg.evaluate("() => window._palRide.roam.enter(1600, 1200, 0, {})") is False                       # already roaming
    pg.evaluate("() => window._palRide.roam.exit(false)")
    pg.wait_for_timeout(100)
    out = pg.evaluate("() => ({put: window.__put, active: window._palRide.roam.active(), fp: document.documentElement.classList.contains('pal-fp'), on: document.getElementById('pal-ride').classList.contains('on'), ride: window._palRide.active()})")
    assert out["put"] == [{"z": 0.5, "x": 123, "y": 456}] and out["active"] is False and out["fp"] is False and out["on"] is False and out["ride"] is False
    # stay here: the map centres on the point where I stood, at (at least) the saved zoom
    pg.evaluate("() => window._palRide.roam.enter(1500, 1200, 0, {hold: true})")
    pg.evaluate("() => window._palRide.roam.place(2400, 1700, 0)")
    s = pg.evaluate("() => window._palRide.roam.state()")
    pg.evaluate("() => window._palRide.roam.exit(true)")
    pg.wait_for_timeout(100)
    v = pg.evaluate("() => window.__put")[-1]
    z = v["z"]
    assert z >= 0.5
    VW, VH = WW + 180, HH + 180
    gx, gy = max(0, (1400 - VW * z) / 2), max(0, round((900 - VH * z) / 2))
    cx, cy = (v["x"] + 700 - gx) / z - 90, (v["y"] + 450 - gy) / z - 90
    assert abs(cx - s["x"]) < 1.5 and abs(cy - s["y"]) < 1.5
    assert pg.evaluate("() => window._palRide.active()") is False


def test_an_aerial_view_may_be_given_to_restore_and_a_spawn_inside_a_building_is_moved_out(roam):
    pg = roam
    # (1500+, 1100+) is inside block (4,2)'s left building; the player appears on free ground next to it
    pg.evaluate("() => window._palRide.roam.enter(1700, 1000, null, {hold: true, view: {z: 1.25, x: 9, y: 8}})")
    r = pg.evaluate("(CHECK) => { var C=new Function(CHECK)(), R=window._palRide.roam, s=R.state(); return {sp:s.spawned, w:C.worst(R), blocked:R.blocked(s.x,s.y)}; }", CHECK)
    assert r["blocked"] is False and r["w"]["inside"] == 0
    assert r["w"]["min"] >= pg.evaluate("() => window._palRide.roam.state().pr") - 1e-6
    pg.evaluate("() => window._palRide.roam.exit(false)")
    pg.wait_for_timeout(50)
    assert pg.evaluate("() => window.__put")[-1] == {"z": 1.25, "x": 9, "y": 8}


def test_collision_never_ends_inside_a_ring_and_slides_along_walls(fast):
    pg = fast
    pg.evaluate("() => window._palRide.roam.enter(1500, 1200, 0, {hold: true})")
    res = pg.evaluate("""(CHECK) => { var C=new Function(CHECK)(), R=window._palRide.roam, seed=777, bad=0, inside=0, steps=0, minD=1e9;
      function rnd(){ seed=(seed*1664525+1013904223)>>>0; return seed/4294967296; }
      var starts=[[1500,1000],[2000,1500],[1200,2300],[3500,900],[4400,3000],[1000,600],[5000,2000],[2300,2800]];
      starts.forEach(function(p){ R.place(p[0],p[1],rnd()*6.28);
        for(var k=0;k<150;k++){ var keys=['f'], q=rnd(); if(q<.2) keys.push('l'); else if(q<.4) keys.push('r'); if(rnd()<.08) keys=['b']; if(rnd()<.3) keys.push(rnd()<.5?'tl':'tr');
          for(var m=0;m<12;m++){ R.tick(1/30, keys.join(','), rnd()<.5); steps++; var w=C.worst(R), s=R.state(); if(w.inside) inside++; if(w.min<minD) minD=w.min; if(R.blocked(s.x,s.y)) bad++; } } });
      return {steps:steps, inside:inside, bad:bad, minD:minD, PR:R.state().pr}; }""", CHECK)
    assert res["steps"] > 12000 and res["inside"] == 0 and res["bad"] == 0
    assert res["minD"] >= res["PR"] - 1e-6                                      # never closer to a wall than the player's radius
    # run straight at a wall, slightly slanted: the player stops at the wall but keeps sliding along it
    r = pg.evaluate("""() => { var R=window._palRide.roam; R.place(1700, 1150, 0.0);   /* east along y=1150 towards block (5,2)'s buildings */
      var a=R.state(); R.look(0.35, 0); R.sim('f', 6, 1/60, true); var b=R.state(); return {ax:a.x, ay:a.y, bx:b.x, by:b.y, blocked:R.blocked(b.x,b.y)}; }""")
    assert r["blocked"] is False and r["by"] > r["ay"] + 5                      # slid sideways (south) along the face


def test_the_city_edge_holds(fast):
    pg = fast
    pg.evaluate("() => window._palRide.roam.enter(700, 500, 0, {hold: true})")
    r = pg.evaluate("""() => { var R=window._palRide.roam; var out=[]; [[700,500,Math.PI],[700,500,-Math.PI/2],[5300,3500,0],[5300,3500,Math.PI/2]].forEach(function(p){ R.place(p[0],p[1],p[2]); R.sim('f',60,1/30,true); var s=R.state(); out.push([s.x,s.y]); });
      R.place(20,20,Math.PI); R.sim('f',5,1/30,true); var s=R.state(); out.push([s.x,s.y]); return out; }""")
    for x, y in r:
        assert 8 - 1e-6 <= x <= WW - 8 + 1e-6 and 8 - 1e-6 <= y <= HH - 8 + 1e-6


def test_water_is_blocked_except_on_the_bridge(fast):
    pg = fast
    pg.evaluate("() => window._palRide.roam.enter(2000, 1000, 0, {hold: true})")
    lim = 50 + 17 + 8 + pg.evaluate("() => window._palRide.roam.state().pr")
    # along the street row y=1040 (no bridge): stops on the west bank, never in the water, however long you push
    r = pg.evaluate("""() => { var R=window._palRide.roam; R.place(2900, 1040, 0); var o=R.sim('f', 30, 1/30, true); var s=R.state(); return {x:s.x, y:s.y, water:R.inWater(s.x,s.y), bad:o.bad}; }""")
    assert r["bad"] == 0 and r["water"] is False and r["x"] <= RIVER_X - lim + 1e-6 and r["x"] > RIVER_X - lim - 8
    # from the far (east) side the same
    r = pg.evaluate("""() => { var R=window._palRide.roam; R.place(3400, 1040, Math.PI); var o=R.sim('f', 30, 1/30, true); var s=R.state(); return {x:s.x, water:R.inWater(s.x,s.y), bad:o.bad}; }""")
    assert r["bad"] == 0 and r["x"] >= RIVER_X + lim - 1e-6
    # the bridge: walk from the west bank to the east bank along its street; every step either on land or on the deck
    r = pg.evaluate("""() => { var R=window._palRide.roam; R.place(2900, 2000, 0); var onDeckInWater=0, inWaterNotDeck=0, xs=[]; for(var i=0;i<400;i++){ R.tick(1/30,'f',true); var s=R.state(); if(R.inWater(s.x,s.y)){ if(R.onDeck(s.x,s.y)) onDeckInWater++; else inWaterNotDeck++; } xs.push(s.x); }
      var s=R.state(); return {x:s.x, y:s.y, deck:onDeckInWater, bad:inWaterNotDeck}; }""")
    assert r["bad"] == 0 and r["deck"] > 10 and r["x"] > RIVER_X + lim                # across, over the water on the deck
    # the deck's edges are walls: strafe off the side in mid-river and stay inside the corridor
    r = pg.evaluate("""() => { var R=window._palRide.roam; R.place(RIVER_X_, 2000, Math.PI); var a=R.sim('l', 6, 1/30, false), s=R.state(), up=Math.abs(s.y-2000); R.sim('r', 12, 1/30, false); var t=R.state(); return {l:up, r:Math.abs(t.y-2000), onDeck:R.onDeck(t.x,t.y)}; }""".replace("RIVER_X_", str(RIVER_X)))
    assert r["onDeck"] and 8 < r["l"] <= 9.5 + 0.2 and 8 < r["r"] <= 9.5 + 0.2
    # the deck is in the world as low solids
    n = pg.evaluate("() => window._palRide.roam.world().solids.filter(function(s){ return s.kind==='plat' && s.name==='Bridge St'; }).length")
    assert n == 3                                                                      # the slab and two parapets


def test_streaming_loads_the_cells_ahead_once_and_drops_the_ones_behind(fast):
    pg = fast
    pg.evaluate("() => window._palRide.roam.enter(700, 2000, 0, {hold: true})")
    r = pg.evaluate("""() => { var R=window._palRide.roam, CELL=300, CF=R.cfg; R.settle(); var s0=R.stats(); var seen={}, rebuilt=0, missing=0, ver0=R.world().ver;
      function check(){ var s=R.state(), W=R.world(); var keys=Object.keys(W.cells); keys.forEach(function(k){ if(!seen[k]) seen[k]=0; });
        var c0=Math.floor(s.x/CELL), r0=Math.floor(s.y/CELL); for(var i=-6;i<=6;i++) for(var j=-6;j<=6;j++){ var ci=c0+i, cj=r0+j; if(ci<0||cj<0||ci*CELL>6000||cj*CELL>4000) continue;
          var dx=Math.max(ci*CELL-s.x,0,s.x-(ci+1)*CELL), dy=Math.max(cj*CELL-s.y,0,s.y-(cj+1)*CELL); if(Math.hypot(dx,dy)<=CF.load-45 && !W.cells[ci+','+cj] && s.queue===0) missing++; } }
      var steps=0; for(var t=0;t<2600;t++){ R.tick(1/30,'f',true); steps++; if(t%20===0) check(); }
      var s=R.state(), st=R.stats(), W=R.world();
      return {x:s.x, built:st.built, evicted:st.evicted, cells:st.cells, merges:st.merges, plans:st.plans, missing:missing, ver:W.ver, steps:steps, maxCells:Object.keys(W.cells).length, solids:W.solids.length, buildMax:st.buildMax}; }""")
    assert r["x"] > 3500                                                                # walked well across the city, over the bridge on the way (row y = 2000)
    assert r["missing"] == 0                                                            # every cell in range was loaded by the time it was within reach
    assert r["built"] == r["cells"] + r["evicted"] and r["evicted"] > 20                # nothing built twice, old cells dropped
    assert r["cells"] < 140 and r["merges"] < r["steps"] / 4 and r["plans"] < r["steps"] / 10    # a handful of rebuilds, not one per frame
    assert r["solids"] > 100


def test_a_real_time_walk_is_smooth_while_the_world_streams(roam):
    pg = roam
    pg.evaluate("() => { var R=window._palRide.roam; R.cfg.brisk=320; R.enter(700, 2000, 0, {}); }")
    pg.wait_for_timeout(400)
    pg.evaluate("""() => { window.__gaps=[]; var last=performance.now(); function f(t){ window.__gaps.push(t-last); last=t; if(window._palRide.roam.active()) requestAnimationFrame(f); } requestAnimationFrame(f); }""")
    pg.keyboard.down("Shift")
    pg.keyboard.down("w")
    pg.wait_for_timeout(2500)
    pg.keyboard.up("w")
    pg.keyboard.up("Shift")
    r = pg.evaluate("""() => { var g=window.__gaps.slice(4).sort(function(a,b){ return a-b; }), n=g.length, st=window._palRide.roam.stats(); window._palRide.roam.cfg.brisk=5.2;
      return {n:n, p50:g[n>>1], max:g[n-1], stats:st, x:window._palRide.roam.state().x}; }""")
    assert r["n"] > 40
    assert r["x"] > 1300                                                                # it moved (fast, to make the world stream)
    assert r["max"] < 100 and r["p50"] < 40                                             # no hitch (generous: CI machines)
    assert r["stats"]["streamMax"] < 20                                                 # a cell never takes long to build while walking
    pg.evaluate("() => window._palRide.roam.exit(false)")


def test_keys_never_reach_the_page_while_roaming_and_esc_exits(roam):
    pg = roam
    pg.evaluate("() => { window.__k=[]; ['keydown','keyup'].forEach(function(t){ document.addEventListener(t,function(e){ window.__k.push(e.key); }); document.addEventListener(t,function(e){ window.__k.push(e.key); },true); }); }")
    pg.evaluate("() => window._palRide.roam.enter(1500, 1000, 0, {})")
    pg.wait_for_timeout(100)
    for key in ("w", "a", "s", "d", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space", "v", "f", "Shift+w", "PageDown", "Home", "Enter"):
        pg.keyboard.press(key)
    assert pg.evaluate("() => window.__k") == []                                         # nothing leaked, in capture or bubble
    # Cmd/Ctrl shortcuts stay the browser's
    pg.keyboard.press("Control+a")
    assert pg.evaluate("() => window.__k.length") > 0
    pg.evaluate("() => { window.__k=[]; }")
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(80)
    assert pg.evaluate("() => window._palRide.roam.active()") is False
    assert pg.evaluate("() => window.__k") == []                                         # the Esc that left was swallowed too
    pg.keyboard.press("Escape")
    assert pg.evaluate("() => window.__k.length") > 0                                    # roaming over: the page gets its keys again
    assert pg.evaluate("() => window.__put.length") == 1


def test_wasd_arrows_drag_and_shift_move_and_look(roam):
    pg = roam
    pg.evaluate("() => window._palRide.roam.enter(1500, 1000, 0, {})")
    pg.wait_for_timeout(100)
    S = "() => window._palRide.roam.state()"
    a = pg.evaluate(S)
    pg.keyboard.down("w")
    pg.wait_for_timeout(700)
    w = pg.evaluate(S)
    pg.keyboard.up("w")
    pg.wait_for_timeout(300)
    assert w["x"] > a["x"] + 0.8 and abs(w["y"] - a["y"]) < 1                            # forward = where it faces (east); a walk is 1.95 units a second
    pg.keyboard.down("Shift")
    pg.keyboard.down("ArrowUp")
    pg.wait_for_timeout(1200)
    sp = pg.evaluate(S)["speed"]
    pg.keyboard.up("ArrowUp")
    pg.keyboard.up("Shift")
    assert sp > 4.5                                                                      # Shift hurries (a brisk walk, 5.2 units a second)
    b = pg.evaluate(S)
    pg.keyboard.down("ArrowRight")
    pg.wait_for_timeout(400)
    pg.keyboard.up("ArrowRight")
    c = pg.evaluate(S)
    assert c["yaw"] > b["yaw"] + 0.3                                                     # the arrows turn
    pg.mouse.move(700, 450)
    pg.mouse.down()
    pg.mouse.move(760, 420, steps=4)
    pg.mouse.up()
    d = pg.evaluate(S)
    assert d["yaw"] < c["yaw"] - 0.2 and d["pitch"] < c["pitch"] - 0.05                  # the scene follows the pointer (drag right turns left, drag up looks down)
    for _ in range(40):
        pg.mouse.move(700, 450)
        pg.mouse.down()
        pg.mouse.move(700, 900, steps=2)
        pg.mouse.up()
    assert abs(pg.evaluate(S)["pitch"]) <= 1.4835 + 1e-9                                 # pitch is clamped at 85 degrees either way (FPV phase 2; it was +-0.42)
    pg.evaluate("() => window._palRide.roam.exit(false)")


def test_hud_names_the_street_cross_street_district_and_a_compass(roam):
    pg = roam
    # on 4th St (x = 1320), between C St and D St, in the test district, facing north
    pg.evaluate("() => window._palRide.roam.enter(1320, 1200, -Math.PI/2, {hold: true})")
    pg.evaluate("() => window._palRide.roam.draw()")
    t = pg.evaluate("() => ({st: document.querySelector('.rm-st').textContent, cx: document.querySelector('.rm-cx').textContent, ar: document.querySelector('.rm-ar').textContent, hint: document.querySelector('.rm-hint').textContent, b: window._palRide.roam.state().bearing})")
    assert t["st"] == "4th St" and t["cx"].startswith("between ") and "C St" in t["cx"] and "D St" in t["cx"]
    assert t["ar"] == "Test District" and min(t["b"], 360 - t["b"]) < 1e-6              # facing north
    assert "Esc" in t["hint"] and "drag" in t["hint"] and "Shift" in t["hint"]
    # at an intersection
    pg.evaluate("() => window._palRide.roam.place(1320, 1362, -Math.PI/2)")
    pg.evaluate("() => window._palRide.roam.draw()")
    assert pg.evaluate("() => document.querySelector('.rm-cx').textContent").startswith("at ")
    # the compass turns with the player: facing east is 90 degrees
    pg.evaluate("() => { window._palRide.roam.look(0, 0); window._palRide.roam.draw(); }")
    assert abs(pg.evaluate("() => window._palRide.roam.state().bearing") - 90) < 1e-6
    tape = pg.evaluate("() => document.querySelector('.rm-tape').style.transform")
    assert "translate3d(" in tape
    # the two buttons
    assert pg.evaluate("() => [].map.call(document.querySelectorAll('.rm-btns button'), function(b){ return b.getAttribute('data-roam'); })") == ["view", "avatar", "exit", "stay"]
    pg.evaluate("() => window._palRide.roam.exit(false)")


def test_the_buttons_exit_and_stay(roam):
    pg = roam
    pg.evaluate("() => window._palRide.roam.enter(1500, 1000, 0, {})")
    pg.wait_for_timeout(100)
    pg.click(".rm-btns [data-roam=stay]")
    pg.wait_for_timeout(80)
    assert pg.evaluate("() => window._palRide.roam.active()") is False and pg.evaluate("() => window.__put")[0]["z"] >= 0.5 and pg.evaluate("() => window.__put")[0]["x"] != 123
    pg.evaluate("() => { window.__put.length=0; window._palRide.roam.enter(1500, 1000, 0, {}); }")
    pg.wait_for_timeout(100)
    pg.click(".rm-btns [data-roam=exit]")
    pg.wait_for_timeout(80)
    assert pg.evaluate("() => window.__put") == [{"z": 0.5, "x": 123, "y": 456}]


def test_no_footstep_bob_under_reduced_motion(roam):
    pg = roam
    pg.evaluate("() => window._palRide.roam.enter(1500, 1000, 0, {})")
    pg.wait_for_timeout(100)
    pg.keyboard.down("w")
    pg.wait_for_timeout(300)
    walk = pg.evaluate("""() => new Promise(function(res){ var R=window._palRide.roam, z=[], n=0; function f(){ z.push(R.state().camZ); if(++n<70) requestAnimationFrame(f); else res([Math.min.apply(null,z), Math.max.apply(null,z)]); } requestAnimationFrame(f); })""")
    pg.emulate_media(reduced_motion="reduce")
    pg.wait_for_timeout(100)
    still = pg.evaluate("""() => new Promise(function(res){ var R=window._palRide.roam, z=[], n=0; function f(){ z.push(R.state().camZ); if(++n<70) requestAnimationFrame(f); else res([Math.min.apply(null,z), Math.max.apply(null,z)]); } requestAnimationFrame(f); })""")
    pg.keyboard.up("w")
    assert walk[1] - walk[0] > 0.04                                                      # a visible bob when walking
    assert still[0] == still[1] == 2.15                                                  # none under reduced motion: eye height 2.15 units
    pg.evaluate("() => window._palRide.roam.exit(false)")


def test_works_in_the_dark_and_resizes(roam):
    pg = roam
    pg.evaluate("() => document.documentElement.classList.add('dark')")
    pg.evaluate("() => window._palRide.roam.enter(1500, 1000, 0, {})")
    pg.wait_for_timeout(150)
    pg.set_viewport_size({"width": 1000, "height": 700})
    pg.wait_for_timeout(150)
    assert pg.evaluate("() => { var c=document.querySelector('#pal-ride .pr-cv'); return c.width>0 && c.height>0; }")
    pg.set_viewport_size({"width": 1400, "height": 900})
    pg.evaluate("() => { window._palRide.roam.exit(false); document.documentElement.classList.remove('dark'); }")


def test_nothing_on_a_phone_a_ride_on_screen_or_without_a_heading_it_faces_along_the_street(roam):
    pg = roam
    pg.evaluate("() => document.documentElement.classList.add('mobile')")
    assert pg.evaluate("() => window._palRide.roam.enter(1500, 1000, 0, {})") is False
    pg.evaluate("() => document.documentElement.classList.remove('mobile')")
    # no heading: along the nearest street (on 4th St, x = 1320, a vertical street: facing north or south)
    assert pg.evaluate("() => window._palRide.roam.enter(1320, 1200, null, {hold: true})") is True
    yaw = pg.evaluate("() => window._palRide.roam.state().yaw")
    assert abs(abs(math.sin(yaw)) - 1) < 1e-6
    pg.evaluate("() => window._palRide.roam.exit(false)")
    assert pg.evaluate("() => window._palRide.roam.streetHeading(1320, 1200, 0)") in (pytest.approx(math.pi / 2), pytest.approx(-math.pi / 2), pytest.approx(3 * math.pi / 2))
