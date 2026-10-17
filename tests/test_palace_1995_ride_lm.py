"""1.9.95 first-person city, the landmarks part (alto/build/palace_ride_h.py + the builders added to palace_ride_mesh.py).

Source assertions (every landmark of the 2D art has a model, the stand-ins stay for the 2D fallback, the mesh format rules are stated) and a cheap runtime check
that needs no browser: node builds every landmark of the sandbox (boxes below, read from the civ-pro palace) and the meshes are checked for the format
(10 floats a vertex, finite, unit normals, one winding convention, bounded triangle counts, inside their block, true heights).
The browser run (WebKit, the real page) is optional: it is skipped when the QA kit or Playwright is not installed.
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from alto.build import palace_ride, palace_ride_h, palace_ride_mesh, palace_skyline, palace_landmarks

# the landmarks of the civ-pro palace (name, box in map units), as the page's M.landmarks has them
LANDMARKS = [
    ("Art Museum", [10968.8, 11966.2, 11448.8, 12606.2]), ("City Hall", [14088.8, 14526.2, 14568.8, 15166.2]),
    ("Independence Hall", [16488.8, 15166.2, 16728.8, 15486.2]), ("Convention Center", [14328.8, 13886.2, 15288.8, 14206.2]),
    ("Franklin Institute", [12648.8, 13566.2, 12888.8, 13886.2]), ("One Liberty Place", [13608.8, 14846.2, 13848.8, 15166.2]),
    ("Two Liberty Place", [13848.8, 14846.2, 14088.8, 15166.2]), ("Comcast Center", [13368.8, 14206.2, 13608.8, 14526.2]),
    ("Comcast Technology Center", [13128.8, 14206.2, 13368.8, 14526.2]), ("BNY Mellon Center", [13368.8, 14526.2, 13608.8, 14846.2]),
    ("Three Logan Square", [13368.8, 13886.2, 13608.8, 14206.2]), ("Cira Centre", [10728.8, 14066.2, 10968.8, 14326.2]),
    ("FMC Tower", [10728.8, 15106.2, 10968.8, 15366.2]), ("Byrne U.S. Courthouse", [16248.8, 14526.2, 16488.8, 14846.2]),
    ("Nix Federal Courthouse", [15528.8, 14846.2, 15768.8, 15166.2]), ("Criminal Justice Center", [14568.8, 14206.2, 14808.8, 14526.2]),
    ("Family Court", [13848.8, 13886.2, 14088.8, 14206.2]), ("William H. Gray III 30th Street Station", [10728.8, 14326.2, 10968.8, 14586.2]),
    ("Penn Center Suburban Station", [13608.8, 14206.2, 13848.8, 14526.2]), ("Jefferson Station", [15288.8, 14206.2, 15528.8, 14526.2]),
    ("Xfinity Mobile Arena", [14568.8, 26046.2, 15048.8, 26366.2]), ("Lincoln Financial Field", [15288.8, 26046.2, 15768.8, 26366.2]),
    ("Citizens Bank Park", [15528.8, 25726.2, 15768.8, 26046.2]),
]
# the true height of each (the lead's 2D art, palace_skyline.py), in metres; None = a ground scaled to fit its block
KEYS = {"Art Museum": "art", "City Hall": "city", "Independence Hall": "ind", "Convention Center": "conv", "Franklin Institute": "frank",
        "One Liberty Place": "lib1", "Two Liberty Place": "lib2", "Comcast Center": "ccc", "Comcast Technology Center": "ctc", "BNY Mellon Center": "bny",
        "Three Logan Square": "tls", "Cira Centre": "cira", "FMC Tower": "fmc", "Byrne U.S. Courthouse": "usch", "Nix Federal Courthouse": "nix",
        "Criminal Justice Center": "cjc", "Penn Center Suburban Station": "sub", "Jefferson Station": "jef"}

NODE = shutil.which("node") or str(Path.home() / ".local/node/bin/node")

_RUN = r"""
var window={}; var console={warn:function(){}};
function hash(n){ n=n|0; n=(n^61)^(n>>>16); n=(n+(n<<3))|0; n^=n>>>4; n=Math.imul(n,0x27d4eb2d); n^=n>>>15; return (n>>>0)/4294967296; }
function hashXY(x,y){ return hash(Math.round(x*7.13)*31+Math.round(y*3.77)); }
var LMH=[[/city hall/i,167],[/one liberty/i,288],[/two liberty/i,258],[/comcast tech/i,342],[/comcast center/i,297],[/bny|mellon/i,241],[/three logan/i,200],[/cira/i,128],[/fmc/i,181],
  [/independence/i,41],[/art museum/i,28],[/convention/i,34],[/franklin inst/i,34],[/courthouse|justice|family court/i,55],[/30th street|suburban|jefferson/i,32],[/arena|center\b|centre\b/i,42],[/field|ballpark|bank park/i,46]];
function lmHeightM(n, floors){ for(var i=0;i<LMH.length;i++) if(LMH[i][0].test(n)) return LMH[i][1]; return floors>=40?floors*4.1:34; }
function lmSolids(l, out, floors){ if(!l.box) return; out.push({kind:'lm', name:l.n}); out.push({kind:'lm', name:l.n}); }
%(MB)s
%(H)s
var GROUND={0:1,10:1,11:1,12:1,13:1};
function stats(l){ var W={solids:[],meshes:[]}; landmarkMeshes(l,30,W); var a=W.meshes.length?W.meshes[0].a:new Float32Array(0), n=a.length, bad=0, nb=0, wb=0, fin=true, tris=0, i;
  var mn=[1e9,1e9,1e9], mx=[-1e9,-1e9,-1e9], matBad=0;
  for(i=0;i<n;i+=10){ for(var k=0;k<10;k++) if(!isFinite(a[i+k])) fin=false; var nl=Math.hypot(a[i+3],a[i+4],a[i+5]); if(Math.abs(nl-1)>1e-3) nb++; if(!(a[i+8]>=0&&a[i+8]<=23&&a[i+8]===Math.floor(a[i+8]))) matBad++;
    if(!GROUND[a[i+8]]){ for(k=0;k<3;k++){ mn[k]=Math.min(mn[k],a[i+k]); mx[k]=Math.max(mx[k],a[i+k]); } } }
  for(i=0;i+30<=n;i+=30){ var P=[0,1,2].map(function(q){ return [a[i+q*10],a[i+q*10+1],a[i+q*10+2]]; }), N=[a[i+3],a[i+4],a[i+5]];
    var e1=[P[1][0]-P[0][0],P[1][1]-P[0][1],P[1][2]-P[0][2]], e2=[P[2][0]-P[0][0],P[2][1]-P[0][1],P[2][2]-P[0][2]], g=[e1[1]*e2[2]-e1[2]*e2[1],e1[2]*e2[0]-e1[0]*e2[2],e1[0]*e2[1]-e1[1]*e2[0]], gl=Math.hypot(g[0],g[1],g[2]);
    if(gl<1e-9) continue; tris++; if((g[0]*N[0]+g[1]*N[1]+g[2]*N[2])/gl>-0.1) wb++; }
  return {n:l.n, floats:n, verts:n/10, tris:tris, finite:fin, badNormals:nb, badWinding:wb, badMat:matBad, mn:mn, mx:mx, id:W.meshes.length?W.meshes[0].id:null, meshes:W.meshes.length, solids:W.solids.length, marked:W.solids.filter(function(s){ return s.mesh===1; }).length}; }
var LMS=%(LMS)s, out=LMS.map(function(l){ return stats({n:l[0],box:l[1]}); });
var gen=stats({n:'Some Unknown Hall', box:[0,0,240,320]}); var nobox=(function(){ var W={solids:[],meshes:[]}; landmarkMeshes({n:'City Hall'},30,W); return {m:W.meshes.length,s:W.solids.length}; })();
var again=stats({n:LMS[1][0],box:LMS[1][1]});
console=null; process.stdout.write(JSON.stringify({out:out,gen:gen,nobox:nobox,again:again.floats}));
"""


def _node_run():
    if not Path(NODE).exists():
        pytest.skip("node is not installed")
    js = _RUN % {"MB": palace_ride_mesh.JS_MB, "H": palace_ride_h.JS_H, "LMS": json.dumps(LANDMARKS)}
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "lm.js"
        f.write_text(js)
        r = subprocess.run([NODE, str(f)], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout)


@pytest.fixture(scope="module")
def built():
    return _node_run()


# ── source ──────────────────────────────────────────────────────────────────
def test_every_art_key_has_a_model_and_the_standins_stay():
    src = palace_ride_h.JS_H
    for k in [k for k, _ in palace_landmarks.MATCH] + ["gen", "fam", "court"]:
        assert f"LMT.{k}=" in src, k                                    # one builder per art key of the 2D art
    assert "function landmarkMeshes(l, floors, W)" in src
    assert "lmSolids(l, W.solids, floors)" in src                       # the 2D fallback keeps its extruded stand-in
    assert "W.meshes.push({a:a, id:l.n})" in src and ".mesh=1" in src   # the model, and the stand-ins marked so the GL renderer skips them
    assert "try{ a=lmBuild(l,floors); }catch" in src                    # a failing builder never takes the world down
    assert "palace_ride_h" in Path(palace_ride.__file__).read_text() and palace_ride.JS_H in palace_ride.RIDE_JS


def test_mesh_builders_are_added_and_the_winding_is_stated():
    js = palace_ride_mesh.JS_MB
    for fn in ("MB.trin=", "MB.face=", "MB.slab=", "MB.cap=", "MB.loft=", "MB.band=", "MB.roofTiers=", "MB.lathe=", "MB.col=", "MB.decal=", "MB.pediment=", "MB.steps="):
        assert fn in js, fn
    assert "WINDING" in palace_ride_mesh.__doc__ and "counter-clockwise for a viewer standing OUTSIDE" in palace_ride_mesh.__doc__
    assert "l=-(Math.sqrt(nx*nx+ny*ny+nz*nz)||1)" in js                 # quad(): the normal points OUT (the old one pointed into the building)
    for sig in ("mk:function(){", "v:function(m,x,y,z,nx,ny,nz,u,v,mat,tint)", "quad:function(m,A,B,C,D,mat,tint,uv)", "prism:function(m,ring,z0,z1,wallMat,roofMat,tint)",
                "box:function(m,x0,y0,z0,x1,y1,z1,wallMat,roofMat,tint)", "cyl:function(m,cx,cy,z0,z1,r,seg,mat,roofMat,tint)", "dome:function(m,cx,cy,z,r,rings,seg,mat,tint)"):
        assert sig in js, sig                                           # no existing signature changed


def test_heights_match_the_2d_art_specs():
    for name, k in KEYS.items():
        spec = palace_skyline.LANDMARKS[k]() if k in palace_skyline.LANDMARKS else None
        assert spec and spec["h"] > 0, name


# ── runtime (node, no browser) ──────────────────────────────────────────────
def test_every_landmark_yields_a_clean_mesh(built):
    assert len(built["out"]) == len(LANDMARKS)
    for o in built["out"]:
        assert o["meshes"] == 1 and o["id"] == o["n"], o["n"]
        assert o["floats"] % 30 == 0 and o["verts"] > 150, o                         # whole triangles, 10 floats a vertex, not empty
        assert o["finite"] and o["badMat"] == 0, o["n"]
        assert o["badNormals"] == 0, o["n"]                                          # unit normals
        assert o["badWinding"] <= 0.002 * o["tris"], (o["n"], o["badWinding"], o["tris"])   # one winding for all: against the normal (see the mesh header)
        assert 50 <= o["tris"] <= 6000, (o["n"], o["tris"])                          # cheap: a few thousand vertices each
        assert o["solids"] == o["marked"] == 2, o["n"]                               # the stand-ins are kept and marked for the renderer to skip
    assert sum(o["verts"] for o in built["out"]) < 120000


def test_models_stand_in_their_blocks_at_their_true_heights(built):
    boxes = dict(LANDMARKS)
    for o in built["out"]:
        b = boxes[o["n"]]
        assert o["mn"][0] >= b[0] - 1 and o["mx"][0] <= b[2] + 1 and o["mn"][1] >= b[1] - 1 and o["mx"][1] <= b[3] + 1, (o["n"], o["mn"], o["mx"], b)   # inside its own block
        assert o["mn"][2] >= -0.01, (o["n"], o["mn"])
        k = KEYS.get(o["n"])
        if k:                                                                        # a true-scale building: its tip is the 2D art's height
            h = palace_skyline.LANDMARKS[k]()["h"]
            assert abs(o["mx"][2] / 1.3 - h) <= max(1.5, .03 * h), (o["n"], o["mx"][2] / 1.3, h)
        else:
            assert 20 <= o["mx"][2] / 1.3 <= 90, o["n"]                              # the station, the arena and the grounds (scaled uniformly to fit their block)


def test_unknown_landmarks_get_a_plain_model_and_a_missing_box_gets_none(built):
    g = built["gen"]
    assert g["meshes"] == 1 and g["tris"] > 40 and g["finite"] and g["badNormals"] == 0 and g["marked"] == 2
    assert built["nobox"]["m"] == 0 and built["nobox"]["s"] == 0                     # no box: nothing (lmSolids returns before it too in the page)


def test_models_are_deterministic(built):
    assert built["again"] == [o for o in built["out"] if o["n"] == "City Hall"][0]["floats"]


# ── optional: the real page in WebKit (needs the QA kit, Playwright and the ride95lm sandbox) ──
KIT = Path.home() / "Desktop/Alto Development/_qa"
_PAGE = r'''
import sys, json, os
sys.path.insert(0, %(kit)r)
from qa_kit import Sandbox
sb = Sandbox("ride95lm"); sb.rebuild()
with sb.browser(engine="webkit", wait=3000) as pg:
    r = pg.evaluate("""() => { var M = window._ALTO_PALACE.m, out = []; (M.landmarks || []).forEach(function(l){ if(!l.box) return; var W = {solids: [], meshes: []}; window._palRideLm.mesh(l, 30, W);
        out.push({n: l.n, meshes: W.meshes.length, verts: W.meshes.length ? W.meshes[0].a.length / 10 : 0, marked: W.solids.filter(function(s){ return s.mesh === 1; }).length}); }); return out; }""")
    ok = pg.evaluate("() => window._palRide.demo('p-trad', 'n-service', 'transit')")
    pg.wait_for_timeout(600)
    print(json.dumps({"r": r, "demo": ok, "errs": pg.errs}))
'''


def test_the_real_page_builds_every_landmark_in_webkit():
    kit = KIT / "kit"
    sb = KIT / "sandboxes" / "ride95lm"
    if not (kit / "py").exists() or not sb.exists():
        pytest.skip("the QA kit or the ride95lm sandbox is not here")
    repo = str(Path(__file__).resolve().parents[1])
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "page.py"
        f.write_text(_PAGE % {"kit": str(kit)})
        env = {"HOME": str(Path.home()), "PATH": os.environ.get("PATH", ""), "ALTO_REPO": repo}
        r = subprocess.run([str(kit / "py"), str(f)], capture_output=True, text=True, timeout=300, env=env)
    if r.returncode != 0 and "playwright" in (r.stderr or "").lower():
        pytest.skip("Playwright is not installed")
    assert r.returncode == 0, r.stderr[-1500:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert not out["errs"], out["errs"]
    assert len(out["r"]) >= 20
    for o in out["r"]:
        assert o["meshes"] == 1 and o["verts"] > 100 and o["marked"] > 0, o
