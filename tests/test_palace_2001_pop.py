"""2.0.1 FPV pops (1.9.102 owner report: "buildings seem to redraw themselves as I walk past them").

What popped: the facade grammar switched from its near look to a flat far look at ONE pixel-footprint threshold (fp.x > .12, the footprint along the wall, large at grazing angles), so the switch line
swept across every facade you walked past and the windows, signs and brick courses on one side of it were redrawn; the fine iron vanished at once at 35 m; the shadow cascades' near/far blend band sat on
the SNAPPED maps and jumped ~5 m with each snap; and the world depended on the way you came: a building classified at the edge of the loaded roads kept that class (cached on its record), and the
solids came in shard-load order, which decided the dedupe's ties (which of two coplanar walls is drawn) and the roof drop.
  * the facade is a continuous function of the pixel footprint (rendered in WebKit: a column per footprint, adjacent columns may not jump);
  * a class made where the roads are not loaded is not cached;
  * the same pose renders the same pixels whatever order the shards came in;
  * the source keeps the blends (iron, cascades) and the cell key carries the class.
"""
import math
import os
import sys

import pytest

from alto.build import palace_ride_facade as fc, palace_ride_gl, palace_ride_gl_shaders as sh, palace_ride_street

sys.path.insert(0, os.path.dirname(__file__))
from test_palace_2000_fpv import page, roam  # noqa: E402,F401  (fixtures)

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover
    sync_playwright = None

K = 1.3


# ───────────────────────────── source contract ─────────────────────────────
def test_no_distance_switch_is_left_in_the_source():
    f = fc.FS_FACADE
    assert "bool far=fp.x>.12" not in f and "fp.x>.12?0." not in f                                  # the old switch and the blind that flipped with it
    assert "float kf=(rel||isGlass)?0.:smoothstep(.09,.2,fp.x);" in f and "alb=mix(alb,fA,kf);" in f     # a blend over a band
    assert "w=mix(w,cov,ka);" in f                                                                  # far windows are box-filtered to their area share
    fs = sh.FS_WORLD
    assert "if(dist>35.*UMc) discard;" not in fs and "smoothstep(24.*UMc,46.*UMc,dist)" in fs        # fine iron thins out, piece by piece, anchored in the world
    assert "uniform vec4 uShO;" in fs and "vec2 qn=vSQ.xy-uShO.zw;" in fs and "vec2 qf=vSL.xy-uShO.xy;" in fs
    g = palace_ride_gl.JS_GL
    assert "'uShO'" in g and "c.off=[(a[0]*ox+a[1]*oy-oa)/Rs,(b[0]*ox+b[1]*oy-ob)/Rs];" in g        # the cascade blend follows the unsnapped centre
    assert "if(s.fg) c.h=glHashStr(c.h,s.fg.g*7+(s.fg.fe+1)*131" in g                               # a cell rebuilds when a building's class changes
    st = palace_ride_street.JS_STREET
    assert "W.solids.sort(function(p,q){ return (p.cx-q.cx)||(p.cy-q.cy)||(p.h-q.h)" in st
    assert st.index("W.solids.sort(") < st.index("realLandmarks(W);") < st.index("realDedupe(W); yield;")
    assert "if(fcCovered(ring,n)) rec._fg=fg;" in fc.JS_FACADE


# ───────────────────────────── the facade is continuous in the pixel footprint ─────────────────────────────
VS = """attribute vec2 aQ; varying vec3 vP; varying vec3 vN; varying vec2 vUV; varying vec4 vM; varying vec3 vDC; varying vec2 vHA; varying vec3 vSL; varying vec3 vSQ; varying float vFade; varying float vFT;
void main(){ vP=vec3(0.); vN=vec3(0.,-1.,0.); vUV=vec2(0.); vM=vec4(0.); vDC=vec3(1.); vHA=vec2(0.); vSL=vec3(0.); vSQ=vec3(0.); vFade=1.; vFT=0.; gl_Position=vec4(aQ,0.,1.); }"""
FS_MAIN = """
uniform vec2 uRes;
void main(){
  float t=floor(gl_FragCoord.x)/(uRes.x-1.); float row=floor(gl_FragCoord.y);
  float g=mod(row,8.); float kind=floor(row/8.);
  vec2 fp=vec2(mix(.02,.5,t)); fp.y*=.4+.5*fract(row*.37);
  vec2 uv=vec2(.35+fract(row*.618)*14.,.4+fract(row*.271)*15.);
  float role=kind<.5?1.:(kind<1.5?3.:0.); float gg=g<.5?1.:(g<1.5?7.:(g<2.5?12.:(g<3.5?4.:(g<4.5?16.:(g<5.5?9.:(g<6.5?14.:5.))))));
  float er=1.+mod(row,5.); float aux=2.+role+4.*gg+128.*er+1024.*(role>.5&&role<1.5?3.:0.);
  vec3 alb; vec3 emi; float refl; vec3 N=vec3(0.,-1.,0.); vec3 V=normalize(vec3(.3,-1.,.1));
  facadeG(1.+mod(row,4.),uv,15.,18.+(3.+.5)/64.,fract(row*.13),fp,vec3(1.),aux,V,N,alb,emi,refl);
  gl_FragColor=vec4(clamp(alb+emi*.2+vec3(refl*.3),0.,1.),1.);
}"""


@pytest.fixture
def wk():
    """A bare WebKit (function scope: the roam fixtures run their own Playwright after these tests)."""
    if sync_playwright is None:
        pytest.skip("no playwright")
    with sync_playwright() as p:
        b = p.webkit.launch()
        yield b
        b.close()


@pytest.fixture
def glpage(wk):
    pg = wk.new_page()
    pg.set_content("<canvas id=c width=256 height=96></canvas>")
    return pg


def test_the_facade_is_continuous_in_the_pixel_footprint(glpage):
    """Each column is one pixel footprint (2 cm .. 50 cm), each row one wall point of one grammar (rowhouse, shop, office, apartment, mixed use, mill, school, tower; front / side street / back).
    Adjacent columns differ by 0.19 cm of footprint: no colour may jump between them (the old switch at 12 cm jumped by up to the whole range)."""
    fs = sh.SH_COMMON + sh.FS_WORLD[:sh.FS_WORLD.index("void main(){")] + FS_MAIN
    r = glpage.evaluate("""([vs,fs])=>{ var c=document.getElementById('c'), gl=c.getContext('webgl'); if(!gl) return 'nogl';
      function sh(t,s){ var o=gl.createShader(t); gl.shaderSource(o,s); gl.compileShader(o); if(!gl.getShaderParameter(o,gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(o)); return o; }
      var p=gl.createProgram(); gl.attachShader(p,sh(gl.VERTEX_SHADER,vs)); gl.attachShader(p,sh(gl.FRAGMENT_SHADER,fs)); gl.linkProgram(p); if(!gl.getProgramParameter(p,gl.LINK_STATUS)) return 'LINK '+gl.getProgramInfoLog(p);
      gl.useProgram(p); var b=gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER,b); gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);
      var a=gl.getAttribLocation(p,'aQ'); gl.enableVertexAttribArray(a); gl.vertexAttribPointer(a,2,gl.FLOAT,false,0,0);
      var tx=gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D,tx); var nz=new Uint8Array(64*64*4); for(var i=0;i<nz.length;i++) nz[i]=(i*2654435761>>>24)&255; gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,64,64,0,gl.RGBA,gl.UNSIGNED_BYTE,nz);
      gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.REPEAT); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.REPEAT);
      gl.uniform2f(gl.getUniformLocation(p,'uRes'),c.width,c.height); gl.uniform1f(gl.getUniformLocation(p,'uNight'),0.); gl.uniform3f(gl.getUniformLocation(p,'uHor'),.6,.7,.8); gl.uniform3f(gl.getUniformLocation(p,'uZen'),.3,.5,.8);
      gl.uniform3f(gl.getUniformLocation(p,'uSun'),.3,.4,.86); gl.uniform3f(gl.getUniformLocation(p,'uSunCol'),1,1,1);
      gl.viewport(0,0,c.width,c.height); gl.drawArrays(gl.TRIANGLES,0,6); var px=new Uint8Array(c.width*c.height*4); gl.readPixels(0,0,c.width,c.height,gl.RGBA,gl.UNSIGNED_BYTE,px);
      var W=c.width, worst=0, at=null, rowsMax=[];
      for(var y=0;y<c.height;y++){ var m=0; for(var x=0;x+1<W;x++){ var i=(y*W+x)*4, j=i+4, d=Math.max(Math.abs(px[i]-px[j]),Math.abs(px[i+1]-px[j+1]),Math.abs(px[i+2]-px[j+2])); if(d>m) m=d; if(d>worst){ worst=d; at=[x,y,(.02+.48*x/(W-1)).toFixed(3)]; } } rowsMax.push(m); }
      rowsMax.sort(function(p,q){ return p-q; }); return {worst:worst, at:at, p90:rowsMax[Math.floor(rowsMax.length*.9)]}; }""", [VS, fs])
    if r == "nogl":
        pytest.skip("no WebGL in this WebKit")
    assert isinstance(r, dict), r
    print("facade continuity", r)
    assert r["worst"] <= 16, r            # 1.9.102: ~150 levels at fp = .12
    assert r["p90"] <= 8, r


# ───────────────────────────── the class is not cached at the edge of the loaded roads ─────────────────────────────
def test_a_class_made_without_the_roads_round_it_is_not_cached(wk):
    st = palace_ride_street.JS_STREET
    harn = """var UM=1.3; function rlNear(x,y,maxd,any){ var d=Math.abs(y-8); return d<=maxd?[{x:x,y:8,d:d,ang:0,f:['residential']}]:[]; } var RCLS={residential:[9.5,.3]};"""
    if True:
        pg = wk.new_page()
        pg.add_script_tag(content=harn + fc.JS_FACADE)
        r = pg.evaluate("""()=>{ var ring=[0,0,5,0,5,-16,0,-16], ob={u0:0,u1:16,v0:0,v1:5}, out={};
          window.REAL={have:[[900,900,720]]}; var a={k:'yes'}; fcClass(a,ring,4,10,80,ob,.3); out.edge=!!a._fg;
          window.REAL={have:[[100,0,720]]}; var b={k:'yes'}; var fb=fcClass(b,ring,4,10,80,ob,.3); out.inside=!!b._fg; out.same=fcClass(b,ring,4,10,80,ob,.3)===fb;
          window.REAL={}; var c={k:'yes'}; fcClass(c,ring,4,10,80,ob,.3); out.blob=!!c._fg; return out; }""")
    assert r == {"edge": False, "inside": True, "same": True, "blob": True}, r
    assert "fcClass(f.rec||{storefront:!!f.sf}" in st


# ───────────────────────────── the same pose renders the same, whatever order the data came in ─────────────────────────────
def _ring(x0, y0, x1, y1):
    return [x0, y0, x1, y0, x1, y1, x0, y1]


def _blob():
    # two 12 m buildings whose street walls (y = 1980) overlap on one plane for 20 m, a red one and a blue one; a 12 m pair with equal roofs; a street along y = 2000
    b = [[12.0] + _ring(4200, 1950, 4240, 1980), [12.0] + _ring(4220, 1955, 4262, 1980), [9.0] + _ring(4280, 1950, 4310, 1980), [9.0] + _ring(4295, 1960, 4325, 1985)]
    return {"b": b, "r": [["residential", 3900, 2000, 4700, 2000]], "rn": ["A St"]}


LOAD = """([blob,rev])=>{ var R=window._palRide, E=R.roam.dbg(); var T={t:0,cx:0,cy:0,xr:[0,100000],xg:[0,100000],yr:[0,100000],yg:[0,100000]}; E.M.grid=T; E.M.doms=null;
  R.real.load(blob); var cols=['#b0402c','#2c48b0','#9a8a70','#5a7a50'], i=0;
  Object.keys(R.real.chunks).forEach(function(k){ var L=R.real.chunks[k].b; L.forEach(function(f){ f.col=cols[(i++)%4]; }); if(rev) L.reverse(); }); return true; }"""
GRAB = """()=>{ var R=window._palRide.roam, cv=document.querySelector('#pal-ride .pr-gl'), gl=(window._palRideGL.gl||cv.getContext('webgl')); for(var i=0;i<90;i++){ R.tick(0,'x',false); R.draw(); }
  var a=new Uint8Array(cv.width*cv.height*4); gl.readPixels(0,0,cv.width,cv.height,gl.RGBA,gl.UNSIGNED_BYTE,a); window.__shots=(window.__shots||[]); window.__shots.push(a); return window.__shots.length-1; }"""


def _stand(pg, rev, x=4245, y=2010, yaw=-math.pi / 2 + .35):
    pg.evaluate(LOAD, [_blob(), rev])
    pg.evaluate("([x,y,yaw])=>{ var R=window._palRide.roam; if(R.active()) R.exit(false); R.enter(x,y,yaw,{hold:true}); }", [x, y, yaw])
    pg.evaluate("()=>window._palRide.roam.real.upgrade()")
    assert pg.evaluate("()=>window._palRide.roam.state().real") is True
    pg.evaluate("([x,y,yaw])=>{ var R=window._palRide.roam; R.place(x,y,yaw); R.look(yaw,.02); R.settle(); }", [x * K, y * K, yaw])
    return pg.evaluate(GRAB)


def test_the_same_pose_renders_the_same_whatever_order_the_shards_came_in(roam):
    pg = roam
    a = _stand(pg, False)
    b = _stand(pg, True)
    d = pg.evaluate("""([i,j])=>{ var A=window.__shots[i], B=window.__shots[j], n=0; for(var k=0;k<A.length;k+=4){ if(Math.abs(A[k]-B[k])+Math.abs(A[k+1]-B[k+1])+Math.abs(A[k+2]-B[k+2])>30) n++; } return [n, A.length/4]; }""", [a, b])
    assert d[0] < d[1] * 0.0005, d
    w = pg.evaluate("""()=>window._palRide.roam.world().solids.filter(function(s){ return s.kind==='b'; }).map(function(s){ return [Math.round(s.cx), !!s.hide, s.roofDz||0]; })""")
    assert any(h for _, h, _ in w) and any(r for _, _, r in w), w                 # the cases are in the world (a wall cut, a roof lowered)
