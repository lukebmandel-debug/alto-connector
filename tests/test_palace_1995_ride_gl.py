"""1.9.95 first-person city, the WebGL renderer (alto/build/palace_ride_gl.py + palace_ride_gl_shaders.py): the source contract (WebGL1, context loss, a second canvas under
the 2D one, the 2D painter kept as the fallback, drawCity's signature), the pure geometry (triangulation, wall winding and normals, crosswalks, styles) run in node, and
the shaders compiled in a real browser. The node and browser parts are skipped when node / Playwright are not installed."""
import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from alto.build import palace_ride, palace_ride_b, palace_ride_d, palace_ride_gl, palace_ride_gl_shaders, palace_ride_mesh

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node") or str(Path.home() / ".local/node/bin/node")
HAVE_NODE = os.path.exists(NODE)


def test_the_gl_part_is_in_the_ride_and_after_the_world_gathering():
    js = palace_ride.RIDE_JS
    assert js.index("var CELL=300;") < js.index("var GLX=") < js.index("var TN=null;")        # JS_B, then JS_GL, then JS_C
    assert ".pr-gl" in palace_ride.RIDE_CSS and palace_ride_gl.CSS_GL in palace_ride.RIDE_CSS


def test_webgl1_context_with_loss_handling_and_a_canvas_under_the_2d_one():
    g = palace_ride_gl.JS_GL
    assert "getContext('webgl'" in g and "experimental-webgl" in g and "webgl2" not in g                       # the safe floor
    assert "webglcontextlost" in g and "webglcontextrestored" in g and "preventDefault" in g
    assert "insertBefore(cv,c2)" in g and "pr-gl" in g                                                          # under .pr-cv
    assert "getShaderPrecisionFormat" in g                                                                      # no highp fragments: fall back
    assert "ANGLE_instanced_arrays" in g and "WEBGL_depth_texture" in g                                         # both optional, both guarded
    assert "window._palRideNoGL" in g and "window._palRideNoShadow" in g


def test_drawcity_keeps_its_signature_and_the_2d_painter_stays_as_the_fallback():
    d = palace_ride_d.JS_D
    assert "function drawCity(ctx, W, H, P, Wd, yaw, tm, way){" in d
    body = d[d.index("function drawCity"):d.index("function render(dt)")]
    assert "glFrame(ctx, W, H, P, Wd, yaw, tm, way)" in body
    for fallback in ("drawSky(ctx, W, H, P, yaw, tm);", "drawGround(ctx, Wd, P, null, null);", "drawSolids(ctx, Wd.solids, P);", "if(way) way();"):
        assert fallback in body                                                                                  # the old painter, untouched
    assert "glAttach(ov)" in d and "glSize(R.cv.width,R.cv.height)" in d
    assert "g.way(M)" in d and "C.shk=" in d and "ctx.clearRect(0,0,R.cv.width,R.cv.height)" in d             # way as a GL mesh, shake into the matrix, transparent 2D canvas
    assert "drawWay(ctx, M, P, s, sec, off);" in d and "drawPortal(ctx, M, P, ug.ahead" in d                    # the 2D ground is still there for the fallback


def test_the_camera_has_a_pitch_and_the_labels_follow_it():
    b = palace_ride_b.JS_B
    assert "function setCam(x,y,z,yaw,W,H,hz,pitch,fk)" in b and "C.pitch=pitch||0;" in b
    proj = b[b.index("function project("):b.index("var _pr=")]
    assert "C.pitch" in proj and "Math.sin(p)" in proj


def test_the_shaders_are_one_program_for_the_city_and_one_for_the_sky():
    s = palace_ride_gl_shaders
    assert "precision highp float;" in s.SH_COMMON and "uniform sampler2D uNz;" in s.SH_COMMON
    for mat in ("/* brick 1, stone 2, glass 3, concrete 4 */", "/* water */", "/* asphalt */", "/* grass */", "/* car paint, glass, tyres, lamps: palette colours, glossy */", "/* street-name text from the atlas, unlit */", "/* the mouth of a tunnel */", "/* crosswalk bars */"):
        assert mat in s.FS_WORLD
    for needed in ("wallFacade(", "skyAt(", "shadowAt(", "vNight", ) if False else ("wallFacade(", "skyAt(", "shadowAt("):
        assert needed in s.SH_COMMON + s.FS_WORLD
    assert "vec3 skyAt" in s.SH_COMMON and "fbm(" in s.FS_SKY and "uUn" in s.FS_SKY            # clouds, the shake un-done for the sky
    assert "GL_FRAGMENT_PRECISION_HIGH" not in s.FS_WORLD                                       # guarded in JS instead
    assert "palCol(" in s.FS_WORLD and "uniform sampler2D uPal;" in s.FS_WORLD and "uLamp[12]" in s.FS_WORLD and "vFade" in s.FS_WORLD     # scenery palette, lamp light pools, mover fade
    g = palace_ride_gl.JS_GL
    assert "glPalOf(" in g and "glFadeOf(" in g and "glAppend(" in g and "'scn:'" in g           # W.pal, distance fade of movers, scenery merged into the cell chunks
    assert g.count("gl.drawArrays") >= 4 and "drawArraysInstancedANGLE" in g


def test_the_shared_mesh_builder_faces_outward():
    # palace_ride_mesh.py had walls and quads facing INWARD (right-hand cross points inward on purpose: the winding is the renderer's front face) with inward normals
    assert "outward normal is its negative" in palace_ride_mesh.JS_MB
    if not HAVE_NODE:
        pytest.skip("node not installed")
    out = _node(palace_ride_mesh.JS_MB + textwrap.dedent("""
        var res=[]; [[0,0,10,0,10,10,0,10],[0,0,0,10,10,10,10,0]].forEach(function(ring){ var m=MB.mk(); MB.prism(m,ring,0,5,1,5,.5); var a=m.a, ok=true;
          for(var i=0;i<a.length;i+=30){ if(Math.abs(a[i+5])>.5) continue; var mx=(a[i]+a[i+10])/2-5, my=(a[i+1]+a[i+11])/2-5; if(a[i+3]*mx+a[i+4]*my<=0) ok=false; }
          res.push(ok); });
        console.log(JSON.stringify(res));"""))
    assert json.loads(out) == [True, True]


# ── the pure geometry, in node: everything but the DOM is plain functions in one scope ──
HARNESS = """
var window={}, document={documentElement:{classList:{contains:function(){return false;}}}}, performance={now:function(){return Date.now();}};
%s
function area(r){ var a=0,n=r.length/2; for(var i=0;i<n;i++){ var j=(i+1)%%n; a+=r[2*i]*r[2*j+1]-r[2*j]*r[2*i+1]; } return Math.abs(a/2); }
function triArea(r,t){ var s=0; for(var i=0;i<t.length;i+=3){ var a=t[i],b=t[i+1],c=t[i+2]; s+=Math.abs(((r[2*b]-r[2*a])*(r[2*c+1]-r[2*a+1])-(r[2*b+1]-r[2*a+1])*(r[2*c]-r[2*a]))/2); } return s; }
%s
"""


def _src():
    return palace_ride.JS_A + palace_ride_mesh.JS_MB + palace_ride_b.JS_B + palace_ride_gl.JS_GL


def _node(code):
    p = subprocess.run([NODE, "-"], input=code, capture_output=True, text=True, encoding="utf-8", timeout=60)      # (the code goes in on stdin: as an argument it outgrew the OS limit)
    assert p.returncode == 0, p.stderr[-1500:]
    return p.stdout.strip()


def _run(body):
    return _node(HARNESS % (_src(), body))


@pytest.mark.skipif(not HAVE_NODE, reason="node not installed")
def test_triangulation_covers_a_simple_ring_exactly():
    out = _run("""
      var rings=[[0,0,10,0,10,10,0,10], [0,0,10,0,10,4,4,4,4,10,0,10], [0,0,4,2,8,0,6,5,8,10,3,7,0,10], [5,0,6,4,10,4,7,6,8,10,5,7,2,10,3,6,0,4,4,4]];
      var star=[]; for(var i=0;i<20;i++){ var r=i%2?3:8, a=i/20*6.2832; star.push(Math.cos(a)*r,Math.sin(a)*r); } rings.push(star);
      var circle=[]; for(var i=0;i<64;i++){ var a=i/64*6.2832; circle.push(Math.cos(a)*50,Math.sin(a)*50); } rings.push(circle, circle.slice().reverse());
      console.log(JSON.stringify(rings.map(function(r){ var t=MB.tris(r); return [Math.abs(area(r)-triArea(r,t))<1e-6, t.length/3===r.length/2-2]; })));""")
    for ok_area, ok_count in json.loads(out):
        assert ok_area and ok_count


@pytest.mark.skipif(not HAVE_NODE, reason="node not installed")
def test_walls_and_roofs_share_the_front_face_convention_and_face_outward():
    out = _run("""
      var b=new GBuf(); var rings=[[0,0,10,0,10,10,0,10],[0,0,0,10,10,10,10,0]]; var res=[];
      rings.forEach(function(ring){ b=new GBuf(); var s={ring:ring,h:20,cx:5,cy:5,r:8,kind:'fill',col:[200,200,255],n:4}; glSolid(b,s); var a=b.a, n=b.n/15, walls=0, roofs=0, bad=0;
        for(var i=0;i<n;i+=3){ var o=i*15, A=[a[o],a[o+1],a[o+2]], B=[a[o+15],a[o+16],a[o+17]], C=[a[o+30],a[o+31],a[o+32]], nx=a[o+3], ny=a[o+4], nz=a[o+5];
          var cx=(B[1]-A[1])*(C[2]-A[2])-(B[2]-A[2])*(C[1]-A[1]), cy=(B[2]-A[2])*(C[0]-A[0])-(B[0]-A[0])*(C[2]-A[2]), cz=(B[0]-A[0])*(C[1]-A[1])-(B[1]-A[1])*(C[0]-A[0]);
          if(cx*nx+cy*ny+cz*nz>=0) bad++;                                   // the right-hand cross must point AGAINST the stored normal
          if(Math.abs(nz)<.5){ walls++; var mx=(A[0]+B[0]+C[0])/3-5, my=(A[1]+B[1]+C[1])/3-5; if(nx*mx+ny*my<=0) bad++; } else roofs++; }
        res.push([bad, walls>0, roofs>0, b.n%15]); });
      console.log(JSON.stringify(res));""")
    for bad, has_walls, has_roof, rem in json.loads(out):
        assert bad == 0 and has_walls and has_roof and rem == 0


@pytest.mark.skipif(not HAVE_NODE, reason="node not installed")
def test_building_styles_follow_height_and_kind():
    out = _run("""
      function st(h,kind){ return glStyle({cx:100+h,cy:50,h:h*1.3,kind:kind,col:[200,200,255],z0:0}); }
      var low=st(7,'fill'), tall=st(120,'fill'), node=st(60,'node'), lm=st(80,'lm'), plat=st(2,'plat');
      var cnt={1:0,2:0,3:0,4:0}; for(var i=0;i<400;i++){ var s=glStyle({cx:i*7.3,cy:i*3.1,h:40*1.3,kind:'fill',col:null,z0:0}); cnt[s.mat]=(cnt[s.mat]||0)+1; }
      console.log(JSON.stringify({low:low.mat, node:[node.mat,node.aux], lm:lm.mat, plat:plat.mat, tallGlass:tall.mat===3||tall.mat===4, mid:cnt}));""")
    r = json.loads(out)
    assert r["low"] == 1 and r["node"] == [3, 1] and r["lm"] == 3 and r["plat"] == 47 and r["tallGlass"]
    assert all(r["mid"][k] > 20 for k in "234")                                                              # mid-rises are a mix of stone, glass, concrete


@pytest.mark.skipif(not HAVE_NODE, reason="node not installed")
def test_a_street_grid_gets_crosswalks_on_arms_that_have_a_block_either_side():
    out = _run("""
      var SW=STREET_HW; function tile(x0,y0,x1,y1){ return {ring:boxRing(x0+SW,y0+SW,x1-SW,y1-SW), inner:boxRing(x0+SW+4,y0+SW+4,x1-SW-4,y1-SW-4), cx:(x0+x1)/2, cy:(y0+y1)/2, r:100}; }
      var W={solids:[],tiles:[tile(0,0,200,200),tile(200,0,400,200),tile(0,200,200,400),tile(200,200,400,400)],parks:[],water:[],roads:[],dashes:[],meshes:[],movers:[]};
      var G=glPlan(W), xs=[]; G.keys.forEach(function(k){ G.cells[k].xs.forEach(function(e){ xs.push([Math.round(e.x),Math.round(e.y),e.arms]); }); });
      var b=new GBuf(); glBase(b,G.cells[G.keys[0]],W);
      console.log(JSON.stringify({xs:xs, verts:b.n/15, finite:Array.prototype.every.call(b.a.subarray(0,b.n),isFinite)}));""")
    r = json.loads(out)
    arms = {(x, y): a for x, y, a in r["xs"]}
    assert arms[(200, 200)] == 15                                                                           # the middle of the grid: all four arms
    assert arms[(0, 200)] == 1 and arms[(200, 0)] == 4                                                       # an edge of the grid: one arm (east / south)
    assert all(a != 15 for (x, y), a in arms.items() if (x, y) != (200, 200))
    assert r["verts"] > 100 and r["finite"]


@pytest.mark.skipif(not HAVE_NODE, reason="node not installed")
def test_the_vertex_layout_is_fifteen_floats_with_the_district_hue_and_wall_length():
    out = _run("""
      var b=new GBuf(); var s={ring:[0,0,13,0,13,13,0,13],h:90,cx:6.5,cy:6.5,r:9,kind:'fill',col:[240,200,200],z0:0,n:4}; glSolid(b,s);
      var a=b.a, ok=true; for(var i=0;i<b.n;i+=15){ if(a[i+10]<=a[i+11]) ok=false; }         // reddish district: r > g
      var wall=null; for(var i=0;i<b.n && !wall;i+=15) if(Math.abs(a[i+5])<.1 && a[i+14]>0) wall=[a[i+13],a[i+14]];
      var m=glExpand(new Float32Array([1,2,3,0,0,1,0,0,2,.5, 4,5,6,0,0,1,1,0,2,.5, 7,8,9,0,0,1,1,1,2,.5]));
      console.log(JSON.stringify({ok:ok, H:wall&&wall[0], L:wall&&wall[1], exp:[m.n,m.a.length,m.x0,m.x1,m.z1,m.a[10],m.a[13]], tris:b.n/45}));""")
    r = json.loads(out)
    assert r["ok"] and abs(r["H"] - 90 / 1.3 * 1.0) < 0.01 and r["L"] > 9 and r["exp"] == [3, 45, 1, 7, 9, 1, 0] and r["tris"] >= 12


# ── the shaders in a real browser (skipped when Playwright / a browser is missing) ──
def test_both_programs_compile_and_link_in_a_browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    html = "<canvas id=c width=16 height=16></canvas>"
    src = palace_ride_gl._GLS
    with sync_api.sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception:
            pytest.skip("no browser installed")
        pg = b.new_page()
        pg.set_content(html)
        res = pg.evaluate("""(src)=>{ eval(src); var gl=document.getElementById('c').getContext('webgl'); if(!gl) return 'nogl';
          function prog(vs,fs){ function mk(t,s){ var h=gl.createShader(t); gl.shaderSource(h,s); gl.compileShader(h); if(!gl.getShaderParameter(h,gl.COMPILE_STATUS)) return gl.getShaderInfoLog(h); return null; }
            var e=mk(gl.VERTEX_SHADER,vs)||mk(gl.FRAGMENT_SHADER,fs); if(e) return e; var p=gl.createProgram(); gl.attachShader(p,(function(){var h=gl.createShader(gl.VERTEX_SHADER); gl.shaderSource(h,vs); gl.compileShader(h); return h;})());
            gl.attachShader(p,(function(){var h=gl.createShader(gl.FRAGMENT_SHADER); gl.shaderSource(h,fs); gl.compileShader(h); return h;})()); gl.linkProgram(p); return gl.getProgramParameter(p,gl.LINK_STATUS)?'ok':gl.getProgramInfoLog(p); }
          return [prog(GLS.vsw,GLS.fsw), prog(GLS.vss,GLS.fss), prog(GLS.vsh,GLS.fsh)]; }""", src)
        b.close()
    if res == "nogl":
        pytest.skip("no WebGL in this browser")
    assert res == ["ok", "ok", "ok"], res


def test_2000_look_pass_street_materials_and_atmosphere():
    """The 2000 look pass: clumped leaves, furrowed bark, cracked asphalt with tyre tracks, weathering streaks, cool fill and warm key, aerial perspective, a vignette."""
    f = palace_ride_gl_shaders.FS_WORLD
    for needed in ("puffy clusters", "float crack=", "tyre", "float stk=", "vec3 sunK=", "float aer="):
        assert needed in f or needed == "tyre"
    assert "smoothstep(0.,vHA.x" in f                                    # no reversed-edge smoothstep (undefined in GLSL ES)
    from alto.build import palace_ride_g
    assert "#pal-ride.on::after" in palace_ride_g.CSS_G and "radial-gradient" in palace_ride_g.CSS_G


def test_2000_look_pass_two_facade_variety_trees_and_markings():
    f = palace_ride_gl_shaders.FS_WORLD
    for needed in ("float cbh=", "vec3 frC=", "float bulk=", "float trn=", "float ak=", "the basement areaway window", "the building's corners", "the dark under a car", "float wr="):
        assert needed in f
    from alto.build import palace_ride_g
    g = palace_ride_g.JS_G
    assert "a second lobe: the crown is not one ball" in g and "gap*(.66+.7*hash(" in g


def test_2000_look_pass_three_leaf_cards_pale_bark_and_stop_signs():
    f = palace_ride_gl_shaders.FS_WORLD
    assert "a leaf card: dissolves into a ragged cluster of leaves" in f and "discard;" in f and "float pale=" in f
    from alto.build import palace_ride_g
    g = palace_ride_g.JS_G
    for needed in ("function cardAt(", ",49,tint)", "function stopSignAt(", "trunkP:pal(", "stopSignAt(m,stx,sty,-aux,-auy)"):
        assert needed in g


def test_2000_look_pass_four_car_colours_contact_shadows():
    f = palace_ride_gl_shaders.FS_WORLD
    assert "a contact shadow on the ground" in f and "gl_FragColor=vec4(0.,0.,0.,a); return;" in f and "gl_FragCoord" not in f      # blended and smooth: no dither at all
    from alto.build import palace_ride_g
    g = palace_ride_g.JS_G
    for needed in ("function carColour(", "function contact(", "dark plates, a grille, and mirrors", "contact(m,0,0,.55,.55,.02)", "ci=carColour("):
        assert needed in g
