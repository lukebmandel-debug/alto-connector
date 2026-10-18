"""2.0.1 FPV flashing (palace_ride_street.py realDedupe / realRoadRanks / gatherRealG, palace_ride_gl.py glSolid / glCamera, palace_ride_gl_shaders.py): the real-geometry world must not flicker.

What flashed in 1.9.100: OpenStreetMap draws a building as an outline AND its building:parts, parts share walls, so two solids had a wall on the very same plane (a facade fought itself in the depth buffer and
the winner changed with every step); roadway ribbons that cross lie on one plane with different lane lines; and the view-projection matrix carried the camera's translation (the world is ~1e4 units
across) so even real separations of a millimetre were lost in float32.  These tests build a small real street with each of those cases in it, draw it in the ride's own WebGL renderer in WebKit and
Chromium (skipped without Playwright) and read the pixels back:
  * a still camera draws the same pixels, frame after frame;
  * no two surfaces tie in the depth buffer (the image does not change when the depth test is LESS instead of LEQUAL) - the control, with the dedupe switched off, does;
  * walking: almost no pixel flips to another colour and straight back (a z-fight does, motion does not), and no frame changes the picture as a whole more than its neighbours;
  * the world swap (a regather) does not change the buffer.
    ALTO_REPO=$PWD _qa/kit/py -m pytest -q tests/test_palace_2000_flash.py
"""
import math
import os
import sys

import pytest

from alto.build import palace_ride, palace_ride_e, palace_ride_gl, palace_ride_gl_shaders, palace_ride_street

sys.path.insert(0, os.path.dirname(__file__))
from test_palace_2000_fpv import page, roam, LOTS  # noqa: E402,F401  (fixtures)

K = 1.3


# ───────────────────────────── source contract ─────────────────────────────
def test_the_causes_are_closed_in_the_source():
    st = palace_ride_street.JS_STREET
    for f in ("function realDedupe(W)", "function realRoadRanks(roads)", "function* gatherRealG(", "REAL.gatherG=gatherRealG", "realDedupe(W); yield; realRoadRanks(W.roads); yield;", "sol.part=!!f.part"):
        assert f in st, f
    gl = palace_ride_gl.JS_GL
    assert "function glVis(hide,ax,ay,bx,by)" in gl and "function gwallP(" in gl and "if(s.nodraw) return;" in gl and "(s.roofDz||0)" in gl      # hidden wall stretches, outlines not drawn, a lowered roof
    assert "var fe=0, re=0, ue=0;" in gl                                                                                                     # camera-relative projection
    assert "o.rk==null?.47:(o.rk+.5)/32" in gl and "(w.rk|0)*131" in gl                                                                     # the rank is geometry, so part of a cell's cache key
    vs, fs = palace_ride_gl_shaders.VS_WORLD, palace_ride_gl_shaders.FS_WORLD
    assert "gl_Position=uVP*vec4(q-uEye,1.);" in vs and "(tint-.5)*.0034" in vs
    assert "gl_FragCoord" not in fs                                                          # no dither fixed to the screen: it crawls over a moving world
    assert "vFade<vFT" in fs and "vFT=fract(sin(dot(aI.xy" in vs                              # a fade is one threshold per instance
    e = palace_ride_e.JS_E
    assert "REAL.gatherG(0,0,RW.R," in e and "performance.now()-t0<CFG.budget" in e and "function realFinish(" in e and "RW.gen=null;" in e


# ───────────────────────────── a small real street with the cases in it ─────────────────────────────
def _ring(x0, y0, x1, y1):
    return [x0, y0, x1, y0, x1, y1, x0, y1]


# (real px = page px = metres) a street along y = 2000, a wider one across it at x = 3960, and on the north side
TOWER = (3975, 1940, 4015, 1980)       # 60 m tower ...
PODIUM = (3955, 1940, 4035, 1980)      # ... whose 10 m podium has a wall on the same plane (the south one, y = 1980)
OUTLINE = (4060, 1940, 4100, 1980)     # a building outline (14 m) and its building:part (14 m): the same footprint
ROOF1 = (4120, 1940, 4160, 1980)       # two 9 m buildings that overlap: one roof plane
ROOF2 = (4140, 1950, 4180, 1990)


def _blob():
    b = [[60.0] + _ring(*TOWER), [10.0] + _ring(*PODIUM), [14.0] + _ring(*OUTLINE), [14.0] + _ring(*OUTLINE), [9.0] + _ring(*ROOF1), [9.0] + _ring(*ROOF2)]
    r = [["residential", 3700, 2000, 4700, 2000], ["tertiary", 3960, 1700, 3960, 2300]]
    return {"b": b, "r": r, "rn": ["A St", "B St"]}


SETUP = """(blob)=>{ var R=window._palRide, E=R.roam.dbg(); var T={t:0,cx:0,cy:0,xr:[0,100000],xg:[0,100000],yr:[0,100000],yg:[0,100000]}; E.M.grid=T; E.M.doms=null;
  R.real.load(blob);
  var tag=0; Object.keys(R.real.chunks).forEach(function(k){ R.real.chunks[k].b.forEach(function(f){ if(f[0]===14 && (tag++)%2===1) f.part=true; }); });      /* the second 14 m footprint is the building:part */
  return true; }"""

PIX = """(args)=>{ var cv=document.querySelector('#pal-ride .pr-gl'), gl=cv.getContext('webgl'), W=cv.width, H=cv.height, R=window._palRide.roam;
  function warm(){ for(var i=0;i<90;i++){ R.tick(0,'x',false); R.draw(); } }
  function grab(){ var a=new Uint8Array(W*H*4); gl.readPixels(0,0,W,H,gl.RGBA,gl.UNSIGNED_BYTE,a); return a; }
  function diff(a,b,thr){ var n=0, s=0; for(var i=0;i<a.length;i+=4){ var d=Math.abs(a[i]-b[i])+Math.abs(a[i+1]-b[i+1])+Math.abs(a[i+2]-b[i+2]); s+=d; if(d>thr) n++; } return {n:n, mean:s/(a.length/4)/3}; }
  window.__t={warm:warm, grab:grab, diff:diff, gl:gl, R:R}; return [W,H]; }"""


def _enter(pg, x, y, yaw, nodedupe=False):
    pg.evaluate("(f)=>{ window._palRideNoDedupe=f; }", nodedupe)
    pg.evaluate(SETUP, _blob())
    pg.evaluate("([x,y,yaw])=>{ var R=window._palRide.roam; if(R.active()) R.exit(false); R.enter(x,y,yaw,{hold:true}); }", [x, y, yaw])
    pg.evaluate("()=>window._palRide.roam.real.upgrade()")
    assert pg.evaluate("()=>window._palRide.roam.state().real") is True
    pg.evaluate("([x,y,yaw])=>{ var R=window._palRide.roam; R.place(x,y,yaw); R.look(yaw,-.02); R.settle(); }", [x * K, y * K, yaw])       # the real world's units are metres x 1.3
    assert pg.evaluate("()=>!!document.querySelector('#pal-ride .pr-gl')"), "no WebGL canvas"
    pg.evaluate(PIX, None)


def _warm(pg):
    pg.evaluate("()=>{ var T=window.__t; for(var i=0;i<60;i++){ T.R.tick(0,'x',false); T.R.draw(); } }")


STAND = (4030, 2012, -math.pi / 2)         # on the street, looking north at the tower, the podium's wall and the outline


def test_the_world_the_gatherer_makes_has_no_coplanar_walls(roam):
    pg = roam
    _enter(pg, *STAND)
    w = pg.evaluate("""()=>{ var S=window._palRide.roam.world().solids.filter(function(s){ return s.kind==='b'; }); var UM=1.3;
      return S.map(function(s){ return {h:Math.round(s.h/UM*10)/10, part:!!s.part, nodraw:!!s.nodraw, hide:s.hide?s.hide.slice():null, roofDz:s.roofDz||0, cx:s.cx/UM}; }); }""")
    pod = [s for s in w if s["h"] == 10.0][0]
    hid = sum(math.hypot(pod["hide"][i + 2] - pod["hide"][i], pod["hide"][i + 3] - pod["hide"][i + 1]) for i in range(0, len(pod["hide"] or []), 4))
    assert hid >= 40 * K - 3, pod                                                   # the podium's wall under the tower (40 m) is cut
    tower = [s for s in w if s["h"] == 60.0][0]
    assert not tower["hide"] and not tower["nodraw"], tower                       # the tall one is never cut
    fourteen = [s for s in w if s["h"] == 14.0]
    assert len(fourteen) == 2 and sorted(s["nodraw"] for s in fourteen) == [False, True], fourteen    # an outline its part covers is not drawn (the part is)
    assert [s for s in fourteen if s["part"]][0]["nodraw"] is False
    nine = [s for s in w if s["h"] == 9.0]
    assert len(nine) == 2 and sorted(s["roofDz"] < 0 for s in nine) == [False, True], nine         # of two equal roofs one sits lower


def test_crossing_ribbons_get_different_ranks_and_the_wider_road_wins(roam):
    pg = roam
    _enter(pg, *STAND)
    rk = pg.evaluate("""()=>{ var R=window._palRide.roam.world().roads, UM=1.3, out=[];
      R.forEach(function(a,i){ out.push({w:a.w/UM, rk:a.rk, vert:Math.abs(a.x1-a.x0)<Math.abs(a.y1-a.y0), cx:a.cx/UM, cy:a.cy/UM, x0:a.x0/UM,y0:a.y0/UM,x1:a.x1/UM,y1:a.y1/UM}); }); return out; }""")
    assert rk and all(isinstance(r["rk"], int) and 0 <= r["rk"] < 32 for r in rk), rk
    # every pair of ribbons that overlap has two ranks; where a wide road crosses a narrow one the wide one is higher
    def box(r, ext=2 / K):
        hw = (r["w"] + 4 / K) / 2
        return (min(r["x0"], r["x1"]) - (ext if not r["vert"] else hw), max(r["x0"], r["x1"]) + (ext if not r["vert"] else hw),
                min(r["y0"], r["y1"]) - (ext if r["vert"] else hw), max(r["y0"], r["y1"]) + (ext if r["vert"] else hw))
    pairs = crossing = 0
    for i, a in enumerate(rk):
        for b in rk[i + 1:]:
            ba, bb = box(a), box(b)
            if ba[1] > bb[0] and bb[1] > ba[0] and ba[3] > bb[2] and bb[3] > ba[2] and a["vert"] != b["vert"]:
                pairs += 1
                assert a["rk"] != b["rk"], (a, b)
                wide, nar = (a, b) if a["w"] > b["w"] else (b, a)
                if wide["w"] > nar["w"] + .1:
                    crossing += 1
                    assert wide["rk"] > nar["rk"], (wide, nar)
    assert pairs >= 1 and crossing >= 1, (pairs, crossing)


def test_a_still_camera_draws_the_same_pixels(roam):
    pg = roam
    _enter(pg, *STAND)
    r = pg.evaluate("""()=>{ var T=window.__t; T.warm(); var a=T.grab(), out=[]; for(var i=0;i<5;i++){ T.R.tick(1/60,'x',false); T.R.draw(); out.push(T.diff(T.grab(),a,4).n); } return out; }""")
    assert r == [0, 0, 0, 0, 0], r


ZF = """()=>{ var T=window.__t, gl=T.gl; T.warm(); gl.depthFunc(gl.LEQUAL); T.R.draw(); var a=T.grab(); gl.depthFunc(gl.LESS); T.R.draw(); var b=T.grab(); gl.depthFunc(gl.LEQUAL); T.R.draw(); return T.diff(a,b,30).n; }"""


def test_no_two_surfaces_tie_in_the_depth_buffer(roam):
    pg = roam
    _enter(pg, *STAND, nodedupe=True)
    control = pg.evaluate(ZF)                           # the street data as it is: the podium's wall, the duplicate footprint, the equal roofs and the junction all tie
    _enter(pg, *STAND)
    fixed = pg.evaluate(ZF)
    px = pg.evaluate("()=>{ var c=document.querySelector('#pal-ride .pr-gl'); return c.width*c.height; }")
    assert control > 2000, control                      # the test can see a z-fight
    assert fixed < control * 0.08, (fixed, control)               # what is left is the thin line along a roof edge (cornice and roof meet)
    assert fixed < px * 0.002, (fixed, px)


TIES = """([n,keys,run,every])=>{ var T=window.__t, R=T.R, gl=T.gl; T.warm(); var out=[], means=[], prev=null;
  for(var f=0;f<n;f++){ R.tick(1/60,keys,run); gl.depthFunc(gl.LEQUAL); R.draw(); var a=T.grab(); if(prev) means.push(T.diff(a,prev,0).mean); prev=a;
    if(f%every===0){ gl.depthFunc(gl.LESS); R.draw(); var b=T.grab(); gl.depthFunc(gl.LEQUAL); out.push(T.diff(a,b,30).n); } }
  R.tick(0,'x',false); return {ties:out, means:means}; }"""


def test_walking_does_not_flicker(roam):
    pg = roam
    # sideways along the street, facing north: the tower, the podium's wall, the footprint pair and the roofs slide past, the junction at x = 3960 is under the feet.
    # A z-fight is a tie in the depth buffer, so at every few steps of the walk the picture is drawn with LESS as well as LEQUAL and must not change; motion alone never makes that differ.
    for run in (False, True):
        _enter(pg, 3945, 2012, -math.pi / 2)
        r = pg.evaluate(TIES, [210, "r", run, 6])
        px = pg.evaluate("()=>{ var c=document.querySelector('#pal-ride .pr-gl'); return c.width*c.height; }")
        moved = pg.evaluate("()=>window._palRide.roam.state().x")
        assert moved > 3945 * K + (2.5 if not run else 8), moved
        assert max(r["ties"]) < px * 0.002, (max(r["ties"]), px)
        means = sorted(r["means"])
        med = means[len(means) // 2]
        assert means[-1] < max(4.0, med * 3), (means[-5:], med)                                 # no frame changes the whole picture more than its neighbours do
    _enter(pg, 3945, 2012, -math.pi / 2, nodedupe=True)
    c = pg.evaluate(TIES, [210, "r", True, 6])
    assert max(c["ties"]) > px * 0.01, (max(c["ties"]), px)                                     # the same walk on the street data as OpenStreetMap has it does tie (the control)


def test_the_world_swap_does_not_change_the_buffer(roam):
    pg = roam
    _enter(pg, 4030, 2012, -math.pi / 2)
    r = pg.evaluate("""()=>{ var T=window.__t, R=T.R; T.warm(); var a=T.grab(), v0=R.state().ver; R.real.gather(); R.draw(); var b=T.grab(); var d0=T.diff(a,b,30); T.warm(); var c=T.grab(); var d1=T.diff(a,c,30); return {ver:R.state().ver-v0, first:d0, settled:d1}; }""")
    assert r["ver"] == 1, r                                          # a new world really replaced the old one
    assert r["first"]["n"] < 200 and r["first"]["mean"] < .05, r     # in the very frame of the swap the picture is the same ...
    assert r["settled"]["n"] < 200 and r["settled"]["mean"] < .05, r  # ... and after the renderer has caught up


def test_the_regather_runs_in_slices_and_ends_in_one_swap(roam):
    pg = roam
    _enter(pg, 3925, 2012, 0.0)
    r = pg.evaluate("""()=>{ var R=window._palRide.roam, v0=R.state().ver, f=0, gath=0, keep=R.cfg.budget; R.cfg.budget=0;      /* no time per frame: one step of the generator each */
      for(f=0; f<2400 && R.state().ver===v0; f++){ R.tick(1/60,'f',true,true); if(R.state().gathering) gath++; }
      R.cfg.budget=keep; return {frames:f, ver:R.state().ver-v0, gathering:gath, x:R.state().x}; }""")
    assert r["ver"] == 1, r                                    # one swap
    assert r["gathering"] >= 2, r                              # and the gather took more than one frame (it is done a few milliseconds at a time)


def test_a_regathered_world_names_its_meshes_by_cell_not_by_where_it_was_gathered(roam):
    pg = roam
    _enter(pg, 3945, 2012, 0.0)
    a = pg.evaluate("()=>window._palRide.roam.world().meshes.map(function(m){ return m.id; })")
    pg.evaluate("()=>{ var R=window._palRide.roam; R.place(R.state().x+150*1.3, R.state().y, 0); R.settle(); }")          # a regather 150 m on
    b = pg.evaluate("()=>window._palRide.roam.world().meshes.map(function(m){ return m.id; })")
    import re
    for ids in (a, b):
        assert ids and all(re.fullmatch(r"(scn-real(-txt)?:-?\d+,-?\d+|real:roof:-?\d+,-?\d+)", i) for i in ids), ids     # no gather centre in an id: the renderer reuses the buffers it has
    assert set(a) & set(b), (a, b)
    g = palace_ride_gl.JS_GL
    assert "function glMeshFind(m)" in g and "GLX.prevM[m.id]" in g and "function glCellObj(G,k)" in g          # an old buffer stays up until its replacement is built


def test_trees_are_full_models_out_to_215_m_nearest_first():
    st = palace_ride_street.JS_STREET
    assert "var FULL_R=215, FULL_N=320" in st and "dtl.sort(function(p,q){ return p[0]-q[0]; })" in st and "RT=Math.max(R,720)" in st
