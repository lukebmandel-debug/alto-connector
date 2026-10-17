"""2.0.0 integration: real-geometry FPV wired into roam, doors, glStyle and rides (palace_ride_e / _door / _gl / _g / _d / _street).

Source assertions always run; the runtime checks reuse the FPV tests' synthetic city (identity real <-> page map, a small real street blob around the two node lots) in WebKit and
Chromium (skipped without Playwright):  ALTO_REPO=$PWD _qa/kit/py -m pytest -q tests/test_palace_2000_int.py
"""
import math
import os
import sys

import pytest

from alto.build import palace_ride, palace_ride_d, palace_ride_e, palace_ride_g, palace_ride_gl, palace_ride_street

sys.path.insert(0, os.path.dirname(__file__))
from test_palace_2000_fpv import page, roam, DOOR1, LOTS  # noqa: E402,F401  (fixtures)

K = 1.3


def test_source_contract():
    e = palace_ride_e.JS_E
    for f in ("function realUpgrade(", "function goReal(", "function realBound(", "REAL.clamp(", "REAL.edgeDist(", "REAL.exit(", "edge of the palace", "function sidewalk(", "function locateReal("):
        assert f in e, f
    assert "REAL.prepare([[rx,ry]],520)" in e                                   # shards stream in while the old world stays up
    assert "GLX.edge" in e and "GLX.edge||0" in palace_ride.RIDE_JS               # the fog thickens at the edge
    assert "real:!!S.real" in palace_ride.RIDE_JS                               # doors remember the world they left from
    assert "rideRealPrep(M)" in palace_ride_d.JS_D and "REAL.legInBounds(M.D)" in palace_ride_d.JS_D and "REAL.pathAt(D,s,_rq)" in palace_ride_d.JS_D
    assert "rlDoor(ring,id)" in palace_ride_street.JS_STREET and "rlLotRing(L)" in palace_ride_street.JS_STREET
    gl = palace_ride_gl._JS_GL_BUILD
    assert "var GL_MATS=" in gl and "function glShop(b,s)" in gl and "if(s.shop) glShop(b,s);" in gl
    tbl = gl.split("var GL_MATS=")[1].split("}")[0]
    for m in ("brick", "stone", "stucco", "painted", "concrete", "glass", "metal", "wood", "brownstone", "cladding", "tile", "plaster"):
        assert (m + ":") in tbl, m
    assert "function shopFront(" in palace_ride_g.JS_G and "'\\u0001'" in palace_ride_g.JS_G
    assert "window._palStreet.load('/street/palace-street-'" in palace_ride.RIDE_JS


SETUP = """(blob)=>{ var R=window._palRide, E=R.roam.dbg(); var T={t:0,cx:0,cy:0,xr:[0,100000],xg:[0,100000],yr:[0,100000],yg:[0,100000]}; E.M.grid=T; E.M.doms=null;
  R.real.load(blob); return true; }"""


def _blob():
    b, r = [], []
    for k, L in LOTS.items():
        pass
    # a street on x = 4200 and one on y = 2000 (real px = page px), buildings around the two node lots
    r.append(["residential", 4200, 1700, 4200, 2700]); r.append(["residential", 3700, 2000, 4700, 2000]); r.append(["footway", 4170, 1700, 4170, 2700])
    for (x0, y0, x1, y1) in ((4220, 1740, 4300, 1900), (4220, 2300, 4300, 2420), (3900, 2020, 3980, 2120), (3900, 2400, 3990, 2500)):
        b.append([12.0, x0, y0, x1, y0, x1, y1, x0, y1])
    return {"b": b, "r": r, "rn": ["4th St", "A St", ""]}


def test_roam_goes_real_keeps_inside_and_doors_work(roam):
    pg = roam
    pg.evaluate(SETUP, _blob())
    x, y = DOOR1[0] + 14, DOOR1[1]
    pg.evaluate("([x,y])=>{ var R=window._palRide.roam; R.enter(x,y,Math.PI,{hold:true}); }", [x, y])
    pg.evaluate("()=>window._palRide.roam.real.upgrade()")
    st = pg.evaluate("()=>window._palRide.roam.state()")
    assert st["real"] is True, st
    w = pg.evaluate("()=>{ var s=window._palRide.roam.world().solids; return {b:s.filter(function(q){return q.kind==='b';}).length, n:s.filter(function(q){return q.kind==='node'&&q.door;}).length}; }")
    assert w["b"] >= 3 and w["n"] >= 1, w                                      # real footprints kept, the node lots carry doors
    # in the real world the door still prompts and E goes in and back
    d = pg.evaluate("()=>{ var s=window._palRide.roam.world().solids.filter(function(q){return q.door;})[0]; return [s.door.x,s.door.y,s.door.nx,s.door.ny]; }")
    yaw = math.atan2(-d[3], -d[2])
    pg.evaluate("([x,y,yaw])=>{ var R=window._palRide.roam; R.place(x,y,yaw); R.look(yaw,0); R.settle(); for(var i=0;i<30;i++) R.door.frame(.05); R.draw(); }", [d[0] + d[2] * 8, d[1] + d[3] * 8, yaw])
    assert pg.evaluate("()=>!!window._palRide.roam.door.cur()")
    pg.evaluate("()=>window._palRide.roam.door.open()")
    pg.evaluate("()=>{ var R=window._palRide.roam; for(var i=0;i<20;i++) R.door.step(60); }")
    pg.wait_for_timeout(500)
    assert pg.evaluate("()=>window.__detail.length") == 1
    pg.evaluate("()=>window.closeDetail()")
    pg.wait_for_timeout(900)
    pg.evaluate("()=>{ var R=window._palRide.roam; for(var i=0;i<20;i++) R.door.step(60); }")
    pg.wait_for_timeout(500)
    st = pg.evaluate("()=>window._palRide.roam.state()")
    assert st["real"] is True                                                    # back in the real world after the detail page


def test_roam_is_held_in_bounds_and_fog_rises(roam):
    pg = roam
    pg.evaluate(SETUP, _blob())
    pg.evaluate("([x,y])=>{ var R=window._palRide.roam; R.enter(x,y,Math.PI,{hold:true}); }", [DOOR1[0] + 14, DOOR1[1]])
    pg.evaluate("()=>window._palRide.roam.real.upgrade()")
    r = pg.evaluate("""()=>{ var R=window._palRide.roam, RL=window._palRide.real, s=R.state(), bad=0, maxEdge=0, ex=0;
      for(var a=0;a<8;a++){ R.place(s.x,s.y,a*.785); R.look(a*.785,0); for(var i=0;i<40;i++){ R.sim('f',2,1/30,true); var q=R.state(); maxEdge=Math.max(maxEdge,q.edge); if(!RL.inBounds(q.x/1.3,q.y/1.3)) bad++; } }
      return {bad:bad, maxEdge:maxEdge, edgeAtEnd:R.real.stats().edge}; }""")
    assert r["bad"] == 0, r


def test_lattice_fallback_without_data(roam):
    pg = roam
    pg.evaluate("()=>{ var R=window._palRide; R.real.on=false; R.real.chunks=null; }")
    pg.evaluate("([x,y])=>{ var R=window._palRide.roam; R.enter(x,y,Math.PI,{hold:true}); }", [DOOR1[0] + 14, DOOR1[1]])
    st = pg.evaluate("()=>window._palRide.roam.state()")
    assert st["real"] is False and st["cells"] > 0
