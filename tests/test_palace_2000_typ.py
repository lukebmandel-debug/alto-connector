"""2.0.0 FPV facade grammar (alto/build/palace_ride_facade.py, glued into palace_ride_street.py gatherRealG, palace_ride_gl.py glSolid, palace_ride_gl_shaders.py wallFacade).

Source assertions always run; the runtime checks run the grammar's JS and compile the world shader in WebKit (skipped without Playwright):
    ALTO_REPO=$PWD _qa/kit/py -m pytest -q tests/test_palace_2000_typ.py
"""
import gzip
import json

import pytest

from alto.build import palace_ride, palace_ride_facade as fc, palace_ride_gl, palace_ride_gl_shaders as sh, palace_ride_street

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover
    sync_playwright = None


def test_the_grammar_is_spliced_into_the_ride():
    assert fc.JS_FACADE in palace_ride_street.JS_STREET and fc.JS_FACADE in palace_ride.RIDE_JS
    assert fc.FS_FACADE in sh.FS_WORLD and sh.FS_WORLD.index("void facadeG(") < sh.FS_WORLD.index("void wallFacade(")
    assert "if(aux>1.5){ facadeG(type,uv,L,H,T,fp,dc,aux,V,N,alb,emi,refl); return; }" in sh.FS_WORLD
    g = palace_ride_gl.JS_GL
    assert "pkw=s.fg?glFacW(b,s,st,r,i,n,ax,ay,bx,by,zb,h,pk):pk" in g and "if(s.fg) st=fcStyle(s,st);" in g and "_gH=s.fg?glFacH(s,hm):hm;" in g
    st = palace_ride_street.JS_STREET
    assert "a.rec=d;" in st and "fg=fcClass(f.rec||{storefront:!!f.sf}" in st and "sol.fg=fg;" in st and "fcRoofKind(fg, f.rs" in st


def test_no_new_attribute_or_uniform_and_webgl1_only():
    src = fc.FS_FACADE
    for bad in ("attribute", "uniform ", "texture2D(", "#version", "for(", "while(", "dFdx", "fwidth"):
        assert bad not in src, bad
    assert "aMT" in sh.VS_WORLD and sh.VS_WORLD.count("attribute") == 8        # still the 8 attributes


def test_the_asset_budget():
    add = len(gzip.compress((fc.JS_FACADE + fc.FS_FACADE).encode(), 9))
    assert add <= 14000, add                                                   # well under the 40 KB the ride may grow


def _aux(role, g, er, by):
    return 2 + role + 4 * g + 128 * er + 1024 * by


def test_pk_packing_stays_exact_in_float32():
    import struct
    for role in range(4):
        for g in range(17):
            for er in range(6):
                for by in (0, 3, 15):
                    pk = 4 + 256 * _aux(role, g, er, by)
                    f = struct.unpack("f", struct.pack("f", float(pk)))[0]
                    assert f == pk
                    a = pk // 256 - 2
                    assert (a % 4, (a // 4) % 32, (a // 128) % 8, a // 1024) == (role, g, er, by)


HARN = """
var UM=1.3, RCLS={residential:[9.5,.3],primary:[17,.45]}, _gdr=1,_gdg=1,_gdb=1,_gH=0,_gL=0, OUT=[];
var ROADS=[];       /* a residential street along y = 8 (real px) */
function rlNear(x,y,maxd,any){ var d=Math.abs(y-8); return d<=maxd?[{x:x,y:8,d:d,ang:0,f:['residential']}]:[]; }
function gbox(b,cx,cy,hx,hy,z0,z1,yaw,pk,t){ b.push([cx,cy,hx,hy,z0,z1,yaw,pk,t]); }
function gquad(b){ b.push(Array.prototype.slice.call(arguments,1)); } function gtri(b){ b.push(Array.prototype.slice.call(arguments,1)); }
"""


@pytest.fixture(scope="module")
def page():
    if sync_playwright is None:
        pytest.skip("no playwright")
    with sync_playwright() as p:
        b = p.webkit.launch()
        pg = b.new_page()
        pg.set_content("<canvas id=c width=64 height=64></canvas>")
        pg.add_script_tag(content=HARN + fc.JS_FACADE)
        yield pg
        b.close()


def test_typology_is_inferred_when_the_data_has_none(page):
    r = page.evaluate("""()=>{ var ob=function(w,d){ return {u0:0,u1:d,v0:0,v1:w}; };
      return { row:fcType({k:'yes'},10,90,ob(5,18)), church:fcType({k:'church'},18,600,ob(20,40)), pow:fcType({k:'yes',po:'amenity=place_of_worship'},14,500,ob(18,30)),
        shop:fcType({k:'yes',fl:1},9,120,ob(6,20)), mixed:fcType({k:'yes',storefront:true},14,200,ob(8,25)), tower:fcType({k:'yes'},120,1500,ob(30,50)),
        school:fcType({k:'school'},14,2000,ob(30,60)), mill:fcType({k:'warehouse'},12,3000,ob(40,70)), garage:fcType({k:'parking'},15,2000,ob(30,60)),
        hotel:fcType({k:'yes',po:'tourism=hotel'},50,900,ob(25,36)), twin:fcType({k:'semidetached_house'},8,80,ob(6,13)) }; }""")
    assert r == {"row": 1, "church": 10, "pow": 10, "shop": 7, "mixed": 16, "tower": 12, "school": 14, "mill": 9, "garage": 11, "hotel": 13, "twin": 2}


def test_the_data_typology_wins_and_the_class_is_deterministic(page):
    r = page.evaluate("""()=>{ var ring=[0,0,5,0,5,-16,0,-16], ob={u0:0,u1:16,v0:0,v1:5};
      var a=fcClass({k:'yes',ty:7,er:3,by:3,st:3},ring,4,10,80,ob,.3), b=fcClass({k:'yes',ty:7,er:3,by:3,st:3},ring,4,10,80,ob,.3), c=fcClass({k:'yes'},ring,4,10,80,ob,.3);
      return {a:JSON.stringify(a), b:JSON.stringify(b), g:a.g, er:a.er, by:a.by, st:a.st, cg:c.g, cer:c.er, front:c.fe, sm:c.sm}; }""")
    assert r["a"] == r["b"] and r["g"] == 7 and r["er"] == 3 and r["by"] == 3 and r["st"] == 3
    assert r["cg"] == 1 and 1 <= r["cer"] <= 5
    assert r["front"] == 0 and r["sm"] & 1                    # the edge along the street (y = 0, facing the street at y = 8)


def test_walls_get_roles_and_the_front_gets_its_stoop(page):
    r = page.evaluate("""()=>{ var K=UM, ring=[0,0,5,0,5,-16,0,-16], wr=ring.map(function(v){return v*K;}), ob={u0:0,u1:16,v0:0,v1:5};
      var fg=fcClass({k:'yes',ty:1,er:2,by:2,st:3,pe:2|8},ring,4,10,80,ob,.3), s={fg:fg, ring:wr}, st={mat:1,aux:0,t:.42}, b=[], pks=[];
      var r=wr.slice(); for(var i=0;i<4;i++){ var j=(i+1)%4; pks.push(glFacW(b,s,st,r,i,4,r[2*i],r[2*i+1],r[2*j],r[2*j+1],0,10*K,1)); }
      var roles=pks.map(function(p){ var a=Math.floor(p/256)-2; return [p%256, a%4, Math.floor(a/4)%32, Math.floor(a/128)%8, Math.floor(a/1024)]; });
      var b2=[]; glFacW(b2,s,st,r,0,4,r[0],r[1],r[2],r[3],0,10*K,1); var b3=[]; s._fcx=null; glFacW(b3,s,st,r,0,4,r[0],r[1],r[2],r[3],0,10*K,1);
      var nan=b.some(function(q){ return q.some(function(v){ return typeof v==='number' && !isFinite(v); }); });
      return {roles:roles, extras:b.length, again:b2.length, rebuilt:b3.length, nan:nan, H:glFacH(s,10.3)}; }""")
    roles = r["roles"]
    assert roles[0][1] == 1 and roles[0][2] == 1 and roles[0][3] == 2 and roles[0][4] == 2      # main front: rowhouse, Victorian, 2 bays
    assert roles[1][1] == 2 and roles[3][1] == 2                                               # party walls (pe)
    assert roles[2][1] == 0 and roles[2][4] == 0                                               # the back
    assert all(x[0] == 1 for x in roles)
    assert r["extras"] > 4 and not r["nan"]                                                    # the stoop, railings, chimney ...
    assert r["again"] == r["extras"] and r["rebuilt"] == r["extras"]                           # per buffer: a rebuilt cell gets them again, the same
    assert abs(r["H"] - (10 + 3.5 / 64)) < 1e-9


def test_the_world_shader_compiles_and_links_in_webkit(page):
    r = page.evaluate("""([vs,fs])=>{ var gl=document.getElementById('c').getContext('webgl'); if(!gl) return 'nogl';
      function mk(t,s){ var o=gl.createShader(t); gl.shaderSource(o,s); gl.compileShader(o); return gl.getShaderParameter(o,gl.COMPILE_STATUS)?o:('ERR '+gl.getShaderInfoLog(o)); }
      var v=mk(gl.VERTEX_SHADER,vs), f=mk(gl.FRAGMENT_SHADER,fs); if(typeof v==='string') return v; if(typeof f==='string') return f;
      var p=gl.createProgram(); gl.attachShader(p,v); gl.attachShader(p,f); gl.linkProgram(p); return gl.getProgramParameter(p,gl.LINK_STATUS)?'ok':('LINK '+gl.getProgramInfoLog(p)); }""",
                    [sh.VS_WORLD, sh.SH_COMMON + sh.FS_WORLD])
    if r == "nogl":
        pytest.skip("no WebGL in this WebKit")
    assert r == "ok", r


def test_fine_iron_thins_out_beyond_24_m_and_shops_are_tinted_by_trade():
    assert "smoothstep(24.*UMc,46.*UMc,dist)) discard;" in sh.FS_WORLD and ",39);" in fc.JS_FACADE        # 2.0.1: thinned piece by piece, not gone at once at 35 m (test_palace_2001_pop.py)
    assert "hue:fcShopHue(cat,hs)" in palace_ride_street.JS_STREET


def test_bays_trust_the_data_only_within_the_frontage(page):
    r = page.evaluate("""()=>[fcBays({g:1,by:6},5), fcBays({g:1,by:3},5.5), fcBays({g:1,by:0},4.2), fcBays({g:1,by:2},7), fcBays({g:12,by:9},30), fcShopHue('amenity=cafe',.1), fcShopHue('shop=pharmacy',.1), fcShopHue('',.123)]""")
    assert r[:5] == [2, 3, 2, 3, 9]
    assert int(r[5] * 8) == 6 and int(r[5] * 7) == 6 and int(r[6] * 8) == 2 and r[7] == 0.123
