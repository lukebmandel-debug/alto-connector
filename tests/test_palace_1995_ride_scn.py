"""1.9.95 first-person ride, part G (scenery): street trees, lamps, signals, signs, crosswalks, parked cars, furniture, rooftops, park trees and paths,
river railings, trolley wires (static meshes) and cars, people, birds (movers).

Source assertions on palace_ride_g.py plus a runtime check in node: the real JS of parts A, MB, B, C, D, G, H is run against a small synthetic city
(a grid of blocks, a park, a river, fill-in buildings) and the world's meshes and movers are checked: deterministic, bounded, nothing inside a
building, nothing on the water, lane-correct and conflict-free signals."""
import json
import os
import shutil
import subprocess
import tempfile

import pytest

from alto.build import palace_ride, palace_ride_g
from alto.build.palace_ride_a import JS_A
from alto.build.palace_ride_b import JS_B
from alto.build.palace_ride_c import JS_C
from alto.build.palace_ride_d import JS_D
from alto.build.palace_ride_h import JS_H
from alto.build.palace_ride_mesh import JS_MB

G = palace_ride_g.JS_G


# ── the source ──
def test_the_three_hooks_exist_and_the_ride_is_assembled_with_them():
    for sig in ("function sceneryGather(W, set){", "function sceneryUpdate(W, tm, Cam){", "function sceneryDraw(ctx, W, P, Cam, tm){"):
        assert sig in G
    assert palace_ride.JS_G is palace_ride_g.JS_G and G in palace_ride.RIDE_JS
    assert "sceneryGather(W, set);" in JS_B and "sceneryDraw(ctx, Wd, P, C, tm)" in JS_D      # the hooks the lead wired: not edited here


def test_no_random_numbers_only_hashes_of_coordinates():
    assert "Math.random" not in G and "Date.now" not in G and "new Date" not in G
    assert "function hk(x,y,k)" in G and "hash(" in G


def test_the_renderer_contract_is_written_down():
    for needle in ("W.pal", "W.atlas", "W.meshes entries", "W.movers entries", "tex:'atlas'", "emissive", "z=0.07", "z=0.12"):
        assert needle in G


def test_every_kind_of_scenery_the_brief_names_is_built():
    for fn in ("function treeAt(", "function lampAt(", "function signalAt(", "function signPoleAt(", "function cornerItems(", "function carParked(", "function benchAt(",
               "function hydrantAt(", "function mailboxAt(", "function shelterAt(", "function roofItems(", "function parkItems(", "function riverRails(", "function tramWires(",
               "function personMesh(", "function birdMesh(", "function carBody(", "function busBody("):
        assert fn in G, fn
    assert "CAR_T=[" in G and G.count("{n:'") >= 6                      # several car body types
    assert "street names white on green" in G or "STREET" in G.upper()


def test_budgets_are_in_the_source():
    assert "CAP_FULL=" in G and "CAP_LOW=" in G
    assert "MAXM=72" in G                                              # at most 72 movers in W.movers
    assert "cell.cap" in G or "c.cap" in G


# ── the runtime: the real JS in node ──
def _node():
    for c in (shutil.which("node"), os.path.expanduser("~/.local/node/bin/node"), "/usr/local/bin/node", "/opt/homebrew/bin/node"):
        if c and os.path.exists(c):
            return c
    return None


NODE_HARNESS = r"""
const vm=require('vm'), fs=require('fs');
const src=fs.readFileSync(process.argv[2],'utf8');
const stub=()=>({getContext:()=>null,style:{},querySelector:()=>null,querySelectorAll:()=>[],appendChild(){},classList:{add(){},remove(){},contains:()=>false},setAttribute(){},addEventListener(){},width:0,height:0});
const win={addEventListener(){},matchMedia:()=>({matches:false}),innerWidth:1400,innerHeight:900,devicePixelRatio:1,localStorage:{getItem:()=>null,setItem(){}},performance,console};
const doc=Object.assign(stub(),{documentElement:stub(),body:stub(),createElement:stub});
const ctx={window:win,document:doc,console,performance,localStorage:win.localStorage,matchMedia:win.matchMedia,getComputedStyle:()=>({getPropertyValue:()=>''}),requestAnimationFrame(){},cancelAnimationFrame(){},setTimeout,clearTimeout,Float32Array,Float64Array,Uint8Array,Uint16Array,Uint32Array,Math,Object,Array,JSON,String,Number,navigator:{}};
win.window=win; vm.createContext(ctx); vm.runInContext(src,ctx);
const out=vm.runInContext('('+process.argv[3]+')()',ctx);
console.log(JSON.stringify(out));
"""

# a 4 x 3 grid of blocks (240 x 320, streets 22 wide between their rings), a park on one block, a river along the south, buildings on most blocks
SETUP = r"""
var X0=3000, Y0=3000, TW=240, TH=320, tiles=[], fill=[], parks=[], i, j;
for(i=0;i<4;i++) for(j=0;j<3;j++) tiles.push([X0+i*TW, Y0+j*TH, X0+(i+1)*TW, Y0+(j+1)*TH]);
function rect(x0,y0,x1,y1){ return [x0,y0,x1,y0,x1,y1,x0,y1]; }
var u={}; u['null']=[];
tiles.forEach(function(t,k){ if(k===5) return;       /* tile 5 is the park */
  var x0=t[0]+16, y0=t[1]+16, x1=t[2]-16, y1=t[3]-16, w=(x1-x0), n=1+(k%3);
  for(var q=0;q<n;q++){ var bx0=x0+w*q/n+(q?3:0), bx1=x0+w*(q+1)/n; u['null'].push({b:[bx0,y0,bx1,y1],p:rect(bx0,y0,bx1,y1),h:(k%4)*1.3+.4,n:'b'+k+'.'+q}); } });
var t5=tiles[5]; parks.push({n:'Test Park', r:[rect(t5[0]+11,t5[1]+11,t5[2]-11,t5[3]-11)]});
var FG=[null,{},{},{},{}]; FG[4]['0,0']={ci:0,cj:0,u:u};
var M={tiles:tiles, tq:[], parks:parks, landmarks:[], hw:{roads:[]}, river:[{p:[X0-200,Y0+3*TH+90, X0+4*TW+200,Y0+3*TH+90], w:60}],
  streets:[]};
for(i=0;i<=4;i++) M.streets.push({n:(i+1)+'th St',k:1,p:[X0+i*TW,Y0,X0+i*TW,Y0+3*TH]});
for(j=0;j<=3;j++) M.streets.push({n:['Walnut St','Chestnut St','Market St','Arch St'][j],k:1,p:[X0,Y0+j*TH,X0+4*TW,Y0+j*TH]});
var E0={M:M,P:{at:{}},lot:function(){ return null; },bOf:function(i){ return i; },ucol:function(){ return '#889'; },dcol:function(){ return '#889'; },tubeCol:function(c){ return c||'#889'; },NEUTRAL:function(){ return '#888'; },nbH:function(){ return 10; },name:function(i){ return String(i); },fillGroups:function(){ return FG; }};
window._palRide.init(E0);
var set={}; for(i=Math.floor(X0/300);i<=Math.floor((X0+4*TW)/300);i++) for(j=Math.floor(Y0/300);j<=Math.floor((Y0+3*TH+200)/300);j++) set[i+','+j]=1;
function ptIn(x,y,r){ var c=false, n=r.length/2; for(var a=0,b=n-1;a<n;b=a++){ var xi=r[2*a], yi=r[2*a+1], xj=r[2*b], yj=r[2*b+1]; if((yi>y)!==(yj>y) && x<(xj-xi)*(y-yi)/(yj-yi)+xi) c=!c; } return c; }
function world(){ return window._palScn.gather(set); }
function sum(a){ var s=0; for(var k=0;k<a.length;k+=37) s+=a[k]*((k%7)+1); return s; }
"""


def _run(tmp_path, body):
    node = _node()
    if not node:
        pytest.skip("node is not installed")
    js = "\n(function(){\nif(window._palRide) return;\n" + JS_A + JS_MB + JS_B + JS_C + JS_D + G + JS_H + \
        "\nwindow._palRide={init:function(e){ E=e; RIDE_M=null; }};\n})();\n"
    f = tmp_path / "ride.js"
    f.write_text(js)
    h = tmp_path / "h.js"
    h.write_text(NODE_HARNESS)
    r = subprocess.run([node, str(h), str(f), "function(){\n" + SETUP + body + "\n}"], capture_output=True, text=True, timeout=240)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_a_world_is_generated_and_is_the_same_every_time(tmp_path):
    out = _run(tmp_path, r"""
      var W1=world(), W2=world(); var s1=W1.meshes.map(function(m){ return m.id+':'+m.a.length+':'+sum(m.a); }).join('|'), s2=W2.meshes.map(function(m){ return m.id+':'+m.a.length+':'+sum(m.a); }).join('|');
      var C={x:X0+400,y:Y0+300}; window._palScn.update(W1,12.3,C); window._palScn.update(W2,12.3,C);
      var m1=W1.movers.map(function(m){ return m.k+':'+m.x.toFixed(4)+','+m.y.toFixed(4)+','+m.yaw.toFixed(4); }).join('|'), m2=W2.movers.map(function(m){ return m.k+':'+m.x.toFixed(4)+','+m.y.toFixed(4)+','+m.yaw.toFixed(4); }).join('|');
      return {same:s1===s2, nmesh:W1.meshes.length, sameMovers:m1===m2, nmov:W1.movers.length, pal:W1.pal.length, stat:window._palScn.SCN.stats.stat};""")
    assert out["same"] and out["sameMovers"]
    assert out["nmesh"] >= 4 and out["nmov"] > 0
    assert out["pal"] <= 256
    st = out["stat"]
    for k in ("trees", "lamps", "cars", "signals", "paint", "roofs", "park", "rail"):
        assert st[k] > 0, k
    assert st["signs"] > 0                                  # street names from M.streets


def test_vertex_budget_per_cell_and_the_format(tmp_path):
    out = _run(tmp_path, r"""
      var W=world(), verts=0, bad=0, tex=0, cells=Object.keys(set).length; W.meshes.forEach(function(m){ verts+=m.a.length/10; if(m.a.length%30) bad++; if(m.tex) tex++;
        for(var k=0;k<m.a.length;k+=10){ var n=Math.hypot(m.a[k+3],m.a[k+4],m.a[k+5]); if(!(m.tex) && Math.abs(n-1)>.01) bad++; if(!isFinite(m.a[k])||!isFinite(m.a[k+2])) bad++; } });
      var cells4=cells/4; return {verts:verts, cells:cells, bad:bad, per4:verts/cells4, meshes:W.meshes.length, tex:tex, entry:W.meshes.every(function(m){ return typeof m.cx==='number' && m.r>0 && m.a instanceof Float32Array; })};""")
    assert out["bad"] == 0                                  # triangles, unit normals, finite
    assert out["per4"] <= 60000, out                        # <= 60k static vertices per 4 cells
    assert out["entry"] and out["verts"] > 5000


def test_nothing_low_stands_inside_a_building(tmp_path):
    out = _run(tmp_path, r"""
      var W=world(), inside=0, onWater=0, n=0, rings=W.solids.filter(function(s){ return s.kind!=='pole'&&s.kind!=='sign'; }).map(function(s){ return s.ring; });
      W.meshes.forEach(function(m){ if(m.tex) return; for(var k=0;k<m.a.length;k+=10){ if(m.a[k+2]>2.0) continue; n++; var x=m.a[k], y=m.a[k+1]; for(var r=0;r<rings.length;r++) if(ptIn(x,y,rings[r])){ inside++; break; } } });
      var wt=W.scenery.t, ti=0; for(var k=0;k<wt.length;k+=5){ for(var r=0;r<rings.length;r++) if(ptIn(wt[k],wt[k+1],rings[r])){ ti++; break; } }
      var river=M.river[0], ry=river.p[1], hw=river.w/2+17, wat=0; W.meshes.forEach(function(m){ if(m.tex) return; for(var k=0;k<m.a.length;k+=10){ if(m.a[k+2]>2.0) continue; if(Math.abs(m.a[k+1]-ry)<hw-3) wat++; } });
      return {inside:inside, n:n, treesInside:ti, ntrees:wt.length/5, water:wat};""")
    assert out["n"] > 5000 and out["ntrees"] > 50
    assert out["inside"] == 0 and out["treesInside"] == 0
    assert out["water"] == 0                                # no post, tree or car on the river's strip


def test_the_movers_follow_the_lanes_and_never_enter_a_building_or_the_water(tmp_path):
    out = _run(tmp_path, r"""
      var W=world(), rings=W.solids.map(function(s){ return s.ring; }), tr=W.tiles.map(function(t){ return t.ring; }), bad={bld:0,water:0,carInBlock:0,n:0,cars:0,people:0,birds:0,heads:0};
      var river=M.river[0], ry=river.p[1], hw=river.w/2+17; var first=null, reuse=true, arr=W.movers, objs=null;
      for(var t=0;t<=240;t+=2){ var C={x:X0+(t*7)%900,y:Y0+(t*5)%700}; window._palScn.update(W,t,C); if(W.movers!==arr) reuse=false;
        W.movers.forEach(function(m){ bad.n++; if(m.kind===0) bad.cars++; else if(m.kind===1) bad.people++; else if(m.kind===2) bad.birds++; else bad.heads++;
          if(m.kind===2) return; for(var r=0;r<rings.length;r++) if(ptIn(m.x,m.y,rings[r])){ bad.bld++; break; }
          if(Math.abs(m.y-ry)<hw-3 && m.kind<2) bad.water++;
          if(m.kind===0){ for(var q=0;q<tr.length;q++) if(ptIn(m.x,m.y,tr[q])){ bad.carInBlock++; break; } } }); }
      return {bad:bad, reuse:reuse, max:Math.max.apply(null,[0].concat([1])), loops:W._mv.loops.length};""")
    b = out["bad"]
    assert b["cars"] > 0 and b["people"] > 0 and b["heads"] > 0
    assert b["bld"] == 0 and b["water"] == 0
    assert b["carInBlock"] == 0                             # cars stay on the roads, outside every block
    assert out["reuse"]                                     # W.movers is one array for ever: no allocation per frame


def test_movers_are_bounded_and_cheap_and_the_signals_never_clash(tmp_path):
    out = _run(tmp_path, r"""
      var W=world(), mx=0, C={x:X0+480,y:Y0+480}; var t0=performance.now(), n=3000; for(var i=0;i<n;i++){ window._palScn.update(W,i/60,C); if(W.movers.length>mx) mx=W.movers.length; } var ms=(performance.now()-t0)/n;
      var clash=0, greens=0; for(var t=0;t<400;t+=.25) for(var a=0;a<4;a++){ var x=X0+a*TW, y=Y0+a*TH; var h=window._palScn.sig(true,x,y,t), v=window._palScn.sig(false,x,y,t); if(h===1&&v===1) clash++; if(h===1) greens++; }
      var cw=0, loops=W._mv.loops.filter(function(L){ return !L.dead; }); loops.forEach(function(L){ var a=0; for(var k=0;k<L.n;k++){ var j=(k+1)%L.n; a+=L.x[2*k]*L.x[2*j+1]-L.x[2*j]*L.x[2*k+1]; } if(a>0) cw++; });
      return {max:mx, ms:ms, clash:clash, greens:greens, loops:loops.length, clockwise:cw};""")
    assert out["max"] <= 72
    assert out["ms"] < 2.0                                  # the brief: at most 2 ms a frame (node is slower than WebKit here, it is ~0.01 ms)
    assert out["clash"] == 0 and out["greens"] > 100       # the two axes are never both green
    assert out["loops"] > 0 and out["clockwise"] == out["loops"]      # right-hand traffic: every lane loop runs clockwise round its block


def test_street_names_come_from_the_streets_and_go_to_the_atlas(tmp_path):
    out = _run(tmp_path, r"""
      var W=world(); var names=W.atlas?W.atlas.list.map(function(e){ return e.name; }):[]; var texMeshes=W.meshes.filter(function(m){ return m.tex==='atlas'; }).length;
      var uvOk=true; W.meshes.forEach(function(m){ if(m.tex!=='atlas') return; for(var k=0;k<m.a.length;k+=10){ if(m.a[k+6]<0||m.a[k+6]>1||m.a[k+7]<0||m.a[k+7]>1||m.a[k+8]!==24) uvOk=false; } });
      return {names:names, tex:texMeshes, uvOk:uvOk};""")
    assert out["tex"] > 0 and out["uvOk"]
    assert any(n.endswith("th St") for n in out["names"]) and any(n in ("Walnut St", "Chestnut St", "Market St", "Arch St") for n in out["names"])


def test_the_river_gets_railings_and_a_ride_keeps_its_own_path_clear(tmp_path):
    out = _run(tmp_path, r"""
      var W=world(); var rails=window._palScn.SCN.stats.stat.rail;
      /* a ride along the first street: nothing but the road under the camera */
      var D={X:[],Y:[],S:[],L:0}; var x0=X0+240, y0=Y0+20, y1=Y0+3*TH-20; for(var s=0;s<=y1-y0;s+=5){ D.X.push(x0+14); D.Y.push(y0+s); D.S.push(s); D.L=s; }
      var Mo={D:D,secs:[{veh:'walk',s0:0,s1:D.L,stops:[],ug:[]}]}; var keep=window._palScn.setRide(Mo); var W2=world(); window._palScn.setRide(keep);
      var near=0, k0=0; W2.meshes.forEach(function(m){ if(m.tex) return; for(var k=0;k<m.a.length;k+=10){ var z=m.a[k+2]; if(z>2.0||z<.4) continue; var x=m.a[k], y=m.a[k+1]; if(y<y0||y>y1) continue; /* inside the walker's 1-unit corridor (the path point and the camera, 14 to its right), above the ground paint and the paths */ if((Math.abs(x-(x0+14))<.9 || Math.abs(x-x0)<.9) && m.a[k+8]!==14) near++; } });
      var cars=0; W2._mv.loops.forEach(function(L){ if(L.dead) cars++; });
      return {rails:rails, near:near, deadLoops:cars, noRideLoops:W._mv.loops.filter(function(L){ return L.dead; }).length};""")
    assert out["rails"] > 0
    assert out["near"] == 0                                 # no trunk, pole or hydrant stands in the walker's corridor
    assert out["noRideLoops"] == 0


def test_cars_wait_at_red_never_overlap_and_never_cross_each_others_lanes(tmp_path):
    out = _run(tmp_path, r"""
      var W=world(), mv=W._mv, cars=mv.cars.filter(function(c){ return !c.loop.dead; }), o={x:0,y:0,h:0}, minX=1e9, minSame=1e9, stopped=0, samples=0, C={x:X0+480,y:Y0+480}, ran=0;
      for(var tt=0;tt<400;tt+=.5){ window._palScn.update(W,tt,C); for(var i=0;i<cars.length;i++){ window._palScn.pos(cars[i],o); cars[i]._x=o.x; cars[i]._y=o.y; }
        for(var i=0;i<cars.length;i++){ samples++; if(cars[i].v<.2) stopped++; else ran++;
          for(var j=i+1;j<cars.length;j++){ var d=Math.hypot(cars[i]._x-cars[j]._x,cars[i]._y-cars[j]._y), sl=(cars[i].len+cars[j].len)/2; if(cars[i].loop===cars[j].loop){ if(d-sl<minSame) minSame=d-sl; } else if(d<minX) minX=d; } } }
      return {n:cars.length, minX:minX, minSame:minSame, stopFrac:stopped/samples};""")
    assert out["n"] > 5
    assert out["minX"] > 8                                  # cars of two loops are never closer than a lane's width (signals keep the axes apart)
    assert out["minSame"] > 0.5                             # car-following: a queue never overlaps
    assert 0.02 < out["stopFrac"] < 0.6                     # and they do wait at the lights
