"""2.0.0 first-person REAL world: the landmark models carried onto their real OSM footprints (alto/build/palace_ride_street_lm.py) and the rebuilt
30th Street Station (palace_ride_h.py bStation, from the OSM footprint and photos).

Node runs the real code on the OSM rings of the station (way 32272623, its parts 749651799 / 749651800) and Cira Centre (way 333367697), in metres east /
south of 30th & Market: the station's model goes on its 8-storey part (not the 2-storey annex), turned to the true axis (the west front faces ~279 deg), at true
size, the plain extrusions hidden (still solids for the walker), the annex still drawn; the box fit and the transform are checked on their own; every one of
the 23 landmark keys builds a clean real-frame model. No browser needed.
"""
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from alto.build import palace_ride, palace_ride_h, palace_ride_mesh, palace_ride_street, palace_ride_street_lm

NODE = shutil.which("node") or str(Path.home() / ".local/node/bin/node")
RINGS = json.loads('''{"32272623": [[-117.7, -92.8], [-110.7, -135.5], [-23.4, -121.7], [-22.7, -125.6], [-22.4, -127.5], [-17.3, -126.8], [-14.2, -126.4], [-7.3, -125.1], [74.2, -111.4], [73.8, -108.8], [66.8, -65.1], [66.0, -60.0], [59.1, -16.6], [65.0, -15.7], [70.0, -15.1], [80.9, -13.3], [77.7, 6.6], [73.8, 30.7], [63.1, 29.1], [58.2, 28.4], [51.1, 27.4], [42.7, 79.5], [-0.8, 72.4], [-52.2, 63.9], [-44.7, 13.0], [-48.2, 12.3], [-54.9, 11.0], [-65.7, 8.9], [-61.8, -14.3], [-58.2, -36.4], [-46.9, -34.8], [-40.6, -33.9], [-37.1, -33.4], [-30.3, -79.5]], "333367697": [[-78.1, -168.3], [-75.8, -182.6], [-62.5, -203.0], [-56.5, -203.0], [-55.6, -202.8], [-4.9, -195.3], [0.0, -193.2], [1.7, -181.0], [-7.5, -157.5], [-10.9, -157.4]], "749651799": [[-30.3, -79.5], [-37.1, -33.4], [-40.6, -33.9], [-46.9, -34.8], [-58.2, -36.4], [-61.8, -14.3], [-65.7, 8.9], [-54.9, 11.0], [-48.2, 12.3], [-44.7, 13.0], [-52.2, 63.9], [-0.8, 72.4], [42.7, 79.5], [51.1, 27.4], [58.2, 28.4], [63.1, 29.1], [73.8, 30.7], [77.7, 6.6], [80.9, -13.3], [70.0, -15.1], [65.0, -15.7], [59.1, -16.6], [66.0, -60.0], [66.8, -65.1]], "749651800": [[-30.3, -79.5], [-117.7, -92.8], [-110.7, -135.5], [-23.4, -121.7], [-22.7, -125.6], [-22.4, -127.5], [-17.3, -126.8], [-14.2, -126.4], [-7.3, -125.1], [74.2, -111.4], [73.8, -108.8], [66.8, -65.1]]}''')

_RUN = r"""
var window={}; var console={warn:function(){}};
function hash(n){ n=n|0; n=(n^61)^(n>>>16); n=(n+(n<<3))|0; n^=n>>>4; n=Math.imul(n,0x27d4eb2d); n^=n>>>15; return (n>>>0)/4294967296; }
function hashXY(x,y){ return hash(Math.round(x*7.13)*31+Math.round(y*3.77)); }
function lmHeightM(n, floors){ return 34; }
function lmSolids(l, out, floors){}
function solid(ring, h, col, kind, nm){ var n=ring.length/2, cx=0, cy=0; for(var i=0;i<n;i++){ cx+=ring[2*i]/n; cy+=ring[2*i+1]/n; } return {ring:ring, n:n, h:h, cx:cx, cy:cy, kind:kind||'b', name:nm||''}; }
%(MB)s
%(H)s
var K=1.3, REAL={}, RCLS={}, E={M:{landmarks:%(LMS)s}};
function realOf(x,y,o){ o.x=x; o.y=y; o.k=0; return o; }
function rlNear(){ return []; }
%(LM)s
var RG=%(RINGS)s;
function W_(ring){ var r=[]; ring.forEach(function(p){ r.push(p[0]*K,p[1]*K); }); return r; }
function mk(id,h,nm,part,wd){ var s=solid(W_(RG[id]),h*K,[0,0,0],'b',''); s.nm=nm||''; s.part=!!part; s.wd=wd||''; s.osm=id; return s; }
var W={solids:[mk('32272623',35.4,'William H. Gray III 30th Street Station',false,'Q224214'), mk('749651799',35.4,'',true), mk('749651800',8,'',true), mk('333367697',133,'Cira Centre',false,'Q5121334'),
  solid([0,-400*K,30*K,-400*K,30*K,-380*K,0,-380*K],20*K,[0,0,0],'b','')], meshes:[], real:{}};
W.solids[4].nm='Convention Center Parking'; W.solids[4].part=false;
realLandmarks(W);
function stat(a){ var x0=1e9,y0=1e9,x1=-1e9,y1=-1e9,z1=-1e9,bad=0,nb=0; for(var i=0;i<a.length;i+=10){ for(var k=0;k<10;k++) if(!isFinite(a[i+k])) bad++; var nl=Math.hypot(a[i+3],a[i+4],a[i+5]); if(Math.abs(nl-1)>1e-3) nb++;
    if(a[i+8]===12||a[i+8]===13) continue; x0=Math.min(x0,a[i]); x1=Math.max(x1,a[i]); y0=Math.min(y0,a[i+1]); y1=Math.max(y1,a[i+1]); z1=Math.max(z1,a[i+2]); } return {bad:bad, nb:nb, bb:[x0/K,y0/K,x1/K,y1/K], top:z1/K, tris:a.length/30}; }
var st=W.meshes.map(function(m){ var o=stat(m.a); o.id=m.id; return o; });
/* box fit on its own: a 100 x 40 rectangle turned 30 deg */
var th=30*Math.PI/180, rr=[], P=[[-50,-20],[50,-20],[50,20],[-50,20]]; P.forEach(function(p){ rr.push(10+p[0]*Math.cos(th)-p[1]*Math.sin(th), 5+p[0]*Math.sin(th)+p[1]*Math.cos(th)); });
var ob=rlmOBB(rr);
/* every key builds in the real frame */
var keys={}; Object.keys(LMT).forEach(function(k){ if(k==='gen') return; var r=lmBuildReal({n:k,x:0,y:0,box:[0,0,300,300]},k); keys[k]=r?{s:stat(r.a), fp:r.fp.length, bb:r.bb}:null; });
var fNix=rlmFit([-61,-60,61,0],{th:Math.PI/2,a:140,b:51,cx:0,cy:0},'nix',null), fCira=rlmFit([-26,-36,26,0],{th:0,a:77,b:38,cx:0,cy:0},'cira',null);
var conv=lmBuildReal({n:'Convention Center',x:0,y:0},'conv',{span:430,spanD:186});
process.stdout.write(JSON.stringify({fNix:{fx:-Math.sin(fNix.phi),fy:Math.cos(fNix.phi),sx:fNix.sx,sy:fNix.sy}, fCira:{sx:fCira.sx,sy:fCira.sy}, convW:(conv.bb[2]-conv.bb[0])/K, lbc:lmKey('Liberty Bell Center'), lm:W.real.lm, st:st, nodraw:W.solids.map(function(s){ return [s.osm||s.nm, !!s.nodraw]; }), ob:ob, keys:keys}));
"""


def _run():
    if not Path(NODE).exists():
        pytest.skip("node is not installed")
    lms = [{"n": "William H. Gray III 30th Street Station", "x": 5, "y": 0}, {"n": "Cira Centre", "x": -40, "y": -180}, {"n": "Convention Center", "x": 10, "y": -390}]
    js = _RUN % {"MB": palace_ride_mesh.JS_MB, "H": palace_ride_h.JS_H, "LM": palace_ride_street_lm.JS_STREET_LM, "LMS": json.dumps(lms), "RINGS": json.dumps(RINGS)}
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "lmr.js"
        f.write_text(js)
        r = subprocess.run([NODE, str(f)], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout)


@pytest.fixture(scope="module")
def res():
    return _run()


def test_the_real_world_carries_the_landmark_code():
    assert "JS_STREET_LM" in Path(palace_ride.__file__).read_text() and "realLandmarks" in palace_ride.RIDE_JS
    src = palace_ride_street.JS_STREET
    assert "realLandmarks(W)" in src and src.index("realLandmarks(W)") < src.index("realDedupe(W); yield;")       # before the roofs and parapets are made
    assert "sol.nm=f.nm" in src and "a.nm=d.nm" in src                                                          # the OSM names reach the solids
    assert "id<32.5" in Path(palace_ride_h.__file__).with_name("palace_ride_gl_shaders.py").read_text()          # the plain limestone material


def test_box_fit_of_a_turned_rectangle(res):
    ob = res["ob"]
    assert abs(ob["a"] * ob["b"] - 4000) < 1 and {round(ob["a"]), round(ob["b"])} == {100, 40}
    assert abs(ob["cx"] - 10) < 1e-6 and abs(ob["cy"] - 5) < 1e-6
    ang = math.degrees(ob["th"]) % 90
    assert min(abs(ang - 30), abs(ang - 30 + 90), abs(ang - 30 - 90)) < 1e-6 or min(abs(ang - 60), abs(ang + 30)) < 1e-6


def test_station_goes_on_its_main_part_turned_to_the_true_axis(res):
    lm = {q["key"]: q for q in res["lm"]}
    assert "stn" in lm and lm["stn"]["part"] is True                      # the 8-storey part, not the outline with the annex
    s = lm["stn"]
    assert 274 <= s["deg"] <= 284, s                                       # the 30th Street front faces west, the street grid's ~9 deg turn
    assert 0.9 <= s["sx"] <= 1.12 and 0.9 <= s["sy"] <= 1.12, s          # true size: the model was built from this footprint
    assert 135 <= s["w"] <= 160 and 135 <= s["d"] <= 160, s
    nd = dict((str(k), v) for k, v in res["nodraw"])
    assert nd["32272623"] and nd["749651799"] and not nd["749651800"]      # outline and main part hidden (still solids), the 2-storey annex still drawn
    assert not nd["Convention Center Parking"]                              # a parking garage never takes a landmark's model


def test_placed_meshes_are_clean_and_where_the_footprint_is(res):
    st = {m["id"]: m for m in res["st"]}
    s = st["rlm:William H. Gray III 30th Street Station"]
    assert s["bad"] == 0 and s["nb"] == 0 and 1500 <= s["tris"] <= 8000
    assert abs(s["top"] - 35.4) < 0.6                                      # OSM height 35.4 m
    xs = [p[0] for p in RINGS["749651799"]]; ys = [p[1] for p in RINGS["749651799"]]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    bb = s["bb"]
    assert abs((bb[0] + bb[2]) / 2 - cx) < 12 and abs((bb[1] + bb[3]) / 2 - cy) < 12
    assert bb[0] > min(xs) - 12 and bb[2] < max(xs) + 12 and bb[1] > min(ys) - 12 and bb[3] < max(ys) + 12
    c = st["rlm:Cira Centre"]
    assert c["bad"] == 0 and c["nb"] == 0 and 120 <= c["top"] <= 140


def test_every_model_builds_in_the_real_frame(res):
    assert len(res["keys"]) >= 23
    for k, r in res["keys"].items():
        assert r and r["s"]["bad"] == 0 and r["s"]["nb"] == 0 and r["s"]["tris"] >= 20, k
        assert r["fp"] >= 1 and r["bb"][2] > r["bb"][0] and r["bb"][3] > r["bb"][1], k
    stn = res["keys"]["stn"]
    assert abs((stn["bb"][2] - stn["bb"][0]) / 1.3 - 145) < 1 and abs((stn["bb"][3] - stn["bb"][1]) / 1.3 - 137) < 2     # 145 m along 30th Street, 97 m + two 20 m porticos


def test_station_model_is_the_researched_building():
    src = palace_ride_h.JS_H
    i = src.index("function bStation(F)"); body = src[src.index("function stnPortico"):src.index("/* ── Penn Center Suburban Station")]
    assert "var xs=[-14,-8.4,-2.8,2.8,8.4,14]" in body and "cap(x,vc+s*5.6); cap(x,vc+s*11.2)" in body     # six across + two down each side = ten a portico
    assert "stnPortico(F,'s'); stnPortico(F,'n');" in src[i:]                                              # one on 30th Street, one toward the river
    assert "lflute(" in body and "MAT.lime=32" in src


def test_fit_rules_front_wins_towers_keep_shape_spans_extend(res):
    assert res["fNix"]["fx"] > 0.9                                                   # a compass front (east, 9th Street) wins over proportions
    assert res["fCira"]["sx"] == res["fCira"]["sy"] and 0.7 <= res["fCira"]["sx"] <= 1.2  # a tower is scaled the same both ways, never stretched 1.5x
    assert 425 <= res["convW"] <= 440                                                 # the Convention Center is built to its real 430 m, bays added
    assert res["lbc"] == "lbc"                                                        # the Liberty Bell Center has a model (matched by its OSM name alone)
    src = palace_ride_street_lm.JS_STREET_LM
    assert "RLM_REALPARTS={usch:1,cjc:1,fam:1}" in src and "model:false" in src         # modern courthouses keep their real OSM building:parts
