"""1.9.103 gfx tiers (alto/build/palace_ride_gfx.py + the GFX blocks of palace_ride_gl_shaders.py): the legacy tier is 1.9.102's renderer word for word, the
governor and the tier picker are pure functions (run in node), the shaders compile on WebGL2 (both GFX tiers) and on WebGL1 (legacy), the MSAA target is
complete, a missing texture keeps the procedural look, and the budgets hold."""
import gzip
import os
import shutil
import struct
import subprocess
from pathlib import Path

import pytest

from alto.build import palace_ride, palace_ride_gfx, palace_ride_gl, palace_ride_gl_shaders as sh

NODE = shutil.which("node") or str(Path.home() / ".local/node/bin/node")
HAVE_NODE = os.path.exists(NODE)


def _strip(src, keep_gfx):
    """The shader text with the #ifdef GFX blocks resolved (only GFX / GFX_HI are used, never nested in another #if)."""
    out, stack = [], []
    for line in src.split("\n"):
        t = line.strip()
        if t.startswith("#ifdef GFX"):
            stack.append([keep_gfx, False]); continue
        if t == "#else" and stack:
            stack[-1][1] = True; continue
        if t == "#endif" and stack:
            stack.pop(); continue
        if all((k if not e else not k) for k, e in stack):
            out.append(line)
    return "\n".join(out)


# ───────────────────────────── source contract ─────────────────────────────
def test_the_legacy_tier_compiles_1_9_102s_shaders():
    legacy = _strip(sh.SH_COMMON + sh.FS_WORLD, False)
    assert "#ifdef" not in legacy and "envAt" not in legacy and "uTx0" not in legacy
    assert "return clamp(mix(vec3(l),c,1.14),0.,1.); }" in legacy                         # the old tone curve, saturation boost and all
    assert "vec3 sr=mix(uHor*.30+vec3(.02),skyAt(vec3(R.xy,max(R.z,0.))),smoothstep(-.12,.16,R.z));" in legacy
    assert "vec3 amb=mix(uGndA,uSkyA,N.z*.5+.5);" in legacy
    g = palace_ride_gfx._JS_GFX
    assert "function gfxDefs(){ var F=gfxFx(); return (GFX.tier==='high'?" in g and ":'')" in g and "if(t==='legacy'||" in g            # legacy: no defines at all
    assert "if(GFX.tier==='legacy' || L.dk) return L;" in g                               # and 1.9.102's light


def test_the_gfx_tier_drops_the_saturation_boost_and_adds_the_environment():
    hi = _strip(sh.SH_COMMON + sh.FS_WORLD, True)
    assert "mix(vec3(l),c,1.14)" not in hi and "mix(vec3(l),c,.94)" in hi
    assert "vec3 envAt(vec3 R)" in hi and "envAt(R)" in hi and "uTx0" in hi
    assert "gl_FragCoord" not in hi                                                       # still no screen-space dither


def test_the_renderer_calls_the_gfx_hooks_at_its_fenced_places():
    g = palace_ride_gl.JS_GL
    for hook in ("gl=gfxContext(cv)", "gfxShim(gl);", "var dfs=gfxDefs();", "gfxInit(gl); }", "return gfxLight(L); }", "gfxUni(gl,pg);",
                 "var sz=gfxSize(), cw=sz[0], ch=sz[1];", "gfxBegin(gl,cw,ch); gl.depthMask(true);", "glDrawWorld(gl,Wd,L,tm,vp); gfxEnd(gl,cw,ch);",
                 "var ext=GFX.wgl2||gl.getExtension('WEBGL_depth_texture')", "GFX.wgl2?gl.DEPTH_COMPONENT24:gl.DEPTH_COMPONENT"):
        assert hook in g, hook
    j = palace_ride_gfx._JS_GFX
    for need in ("getContext('webgl2'", "renderbufferStorageMultisample", "blitFramebuffer", "palgl==='1'", "palperf==='1'", "createImageBitmap",
                 "LINEAR_MIPMAP_LINEAR", "Math.min(1,(performance.now()-GFX.txT0)/1000)"):
        assert need in j, need


# ───────────────────────────── pure functions (node) ─────────────────────────────
HARNESS = """
var window={}, navigator={}, location={search:''}, GLX={st:{}}, R={w:1280,h:800}, innerWidth=1280, innerHeight=800, performance={now:function(){return 0;}};
%s
%s
"""


def _node(body):
    p = subprocess.run([NODE, "-"], input=HARNESS % (palace_ride_gfx._JS_GFX.replace("__GFX_TEX__", "[]"), body), capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-1500:]
    return p.stdout.strip()


@pytest.mark.skipif(not HAVE_NODE, reason="node not installed")
def test_the_governor_climbs_on_fast_frames_and_holds_on_slow_ones():
    out = _node("""
      function run(g, ms, secs, t0){ var t=t0||0, acts=[]; while(t<(t0||0)+secs*1000){ var dt=typeof ms==='function'?ms(t,g):ms; t+=dt; var r=gfxGov(g,dt,t); if(r) acts.push(r+'@'+g.s); } return {t:t, acts:acts}; }
      var g=gfxGovNew(1,2,1.25), a=run(g, function(t){ return 16+((t*7)%3); }, 20);          // a 60 Hz display, Safari's coarse clock (16-18 ms)
      console.log(JSON.stringify({s:g.s, acts:a.acts}));
      var h=gfxGovNew(1,2,2), b=run(h, 26, 5); console.log(JSON.stringify({s:h.s, acts:b.acts}));
      // the device holds 60 fps at 1.5 but not at 1.75: one bounce, then a ceiling and no more tries
      var k=gfxGovNew(1,2,1.5), c=run(k, function(t,g){ return g.s>1.5?24:16.7; }, 60); console.log(JSON.stringify({s:k.s, ceil:k.ceil, acts:c.acts}));
      var p=gfxGovNew(1,2,1.5); p.pin=1; var d=run(p, 30, 5); console.log(JSON.stringify({s:p.s, acts:d.acts}));
      var q=gfxGovNew(1,2,1.5); var e=run(q, 250, 5); console.log(JSON.stringify({s:q.s, acts:e.acts}));   // a paused tab: not frames
    """).split("\n")
    import json
    up, down, bounce, pin, pause = (json.loads(x) for x in out)
    assert up["s"] == 2 and all(a.startswith("up") for a in up["acts"]) and len(up["acts"]) == 3          # 1.25 -> 2.0, one step at a time
    assert down["s"] == 1 and down["acts"][-1].startswith("floor")                                          # down to 1.0, then it asks for a lower tier
    assert bounce["s"] == 1.5 and bounce["ceil"] == 1.5 and bounce["acts"] == ["up@1.75", "down@1.5"]       # no oscillation
    assert pin["acts"] == [] and pin["s"] == 1.5 and pause["acts"] == [] and pause["s"] == 1.5


@pytest.mark.skipif(not HAVE_NODE, reason="node not installed")
def test_the_tier_follows_the_probe():
    out = _node("""
      var c=[{wgl2:true,msaa:true,samples:4,renderer:'Apple M2'}, {wgl2:true,msaa:true,samples:4,renderer:'ANGLE (Intel(R) HD Graphics 520 Direct3D11)'},
        {wgl2:true,msaa:true,samples:2,renderer:'Apple GPU'}, {wgl2:false}, {wgl2:true,msaa:false,samples:0}, {wgl2:true,msaa:true,samples:4,renderer:'Google SwiftShader'},
        {wgl2:true,msaa:true,samples:4,gl1:true}, {wgl2:true,msaa:true,samples:4,force:'medium'}, {wgl2:false,force:'high'}];
      console.log(c.map(gfxPickTier).join(','));""")
    assert out == "high,medium,medium,legacy,legacy,legacy,legacy,medium,legacy"


# ───────────────────────────── browser ─────────────────────────────
def _browser(p):
    try:
        return p.webkit.launch()
    except Exception:
        pytest.skip("no browser installed")


def test_shaders_compile_on_webgl2_and_on_webgl1_and_the_msaa_target_is_complete():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        b = _browser(p)
        pg = b.new_page()
        pg.set_content("<canvas id=a width=16 height=16></canvas><canvas id=b width=16 height=16></canvas>")
        res = pg.evaluate("""([gls,gfx])=>{ eval(gls); var GLX={st:{}}, R={w:16,h:16}; eval(gfx.replace('__GFX_TEX__','[]'));
          function prog(gl,vs,fs){ function mk(t,s){ var h=gl.createShader(t); gl.shaderSource(h,s); gl.compileShader(h); if(!gl.getShaderParameter(h,gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(h)); return h; }
            try{ var p=gl.createProgram(); gl.attachShader(p,mk(gl.VERTEX_SHADER,vs)); gl.attachShader(p,mk(gl.FRAGMENT_SHADER,fs)); gl.linkProgram(p); return gl.getProgramParameter(p,gl.LINK_STATUS)?'ok':gl.getProgramInfoLog(p); }catch(e){ return String(e.message); } }
          var o={}, g2=document.getElementById('a').getContext('webgl2',{antialias:false}), g1=document.getElementById('b').getContext('webgl');
          if(g2){ ['high','medium'].forEach(function(t){ GFX.tier=t; var d=gfxDefs(); o[t]=[prog(g2,GLS.vsw,d+GLS.fsw),prog(g2,GLS.vss,d+GLS.fss),prog(g2,GLS.vsh,GLS.fsh)]; });
            GFX.probe={msaa:true,samples:Math.min(4,g2.getParameter(g2.MAX_SAMPLES))}; var t=gfxTarget(g2,64,48,GFX.probe.samples,null); o.fbo=!!t; o.samples=GFX.probe.samples;
            if(t){ g2.bindFramebuffer(g2.FRAMEBUFFER,t.fb); g2.clearColor(1,0,0,1); g2.clear(g2.COLOR_BUFFER_BIT); g2.bindFramebuffer(g2.FRAMEBUFFER,null); GFX.wgl2=true; GFX.fb=t; gfxEnd(g2,64,48); o.err=g2.getError(); } }
          if(g1){ GFX.tier='legacy'; o.legacy=[prog(g1,GLS.vsw,gfxDefs()+GLS.fsw),prog(g1,GLS.vss,gfxDefs()+GLS.fss)]; }
          return o; }""", [palace_ride_gl._GLS, palace_ride_gfx.JS_GFX])           # the full part: with fpv_gfx's FXG the tiers compile the graphics pass's variants too
        b.close()
    if "high" not in res:
        pytest.skip("no WebGL2 in this browser")
    assert res["high"] == ["ok"] * 3 and res["medium"] == ["ok"] * 3, res
    assert res["fbo"] and res["samples"] >= 2 and res["err"] == 0, res
    assert res.get("legacy") == ["ok", "ok"], res


def test_a_texture_that_is_not_there_keeps_the_procedural_look():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        b = _browser(p)
        pg = b.new_page()
        pg.route("http://alto.test/**", lambda r: r.fulfill(status=404, body="") if "/tex/" in r.request.url else r.fulfill(status=200, content_type="text/html", body="<canvas id=a width=8 height=8></canvas>"))
        pg.goto("http://alto.test/pv/x/")
        r = pg.evaluate("""async (gfx)=>{ var GLX={st:{}, gen:1, on:true}, R={w:8,h:8}; function glOk(){ return true; } eval(gfx.replace('__GFX_TEX__','["/tex/alto-tex0-0000000000.png","/tex/alto-tex1-0000000000.png"]'));
          var gl=document.getElementById('a').getContext('webgl2')||document.getElementById('a').getContext('webgl'); GLX.gl=gl; GFX.tier='high'; gfxTexLoad(gl);
          await new Promise(function(ok){ setTimeout(ok,600); }); var set={}; var pg={u:{uTx0:1,uTx1:1,uTxA:1}}; gl.uniform1f=function(u,v){ set.a=v; }; gl.uniform1i=function(){}; gfxUni(gl,pg);
          return {err:GFX.txErr, tx:[!!GFX.tx[0],!!GFX.tx[1]], a:set.a}; }""", palace_ride_gfx._JS_GFX)
        b.close()
    assert r["tx"] == [False, False] and r["a"] == 0 and r["err"], r


# ───────────────────────────── budgets and hosting ─────────────────────────────
def test_budgets():
    gz = lambda s: len(gzip.compress(s.encode(), 9))
    gfx_shader = sum(len(blk) for blk in (_strip(sh.SH_COMMON + sh.FS_WORLD, True),)) - len(_strip(sh.SH_COMMON + sh.FS_WORLD, False))
    assert gz(palace_ride_gfx._JS_GFX) + max(gfx_shader, 0) // 3 < 40_000                       # the hosted ride grows by far less than 40 KB gzipped
    files = palace_ride_gfx.tex_files()
    assert len(files) == 2 and sum(len(b) for _n, b in files) <= 4_000_000
    for name, b in files:
        assert palace_ride_gfx.TEX_RE.match(name) and b[:8] == b"\x89PNG\r\n\x1a\n"
        w, h = struct.unpack(">II", b[16:24])
        assert (w, h) == (512, 512)
    assert all(n in palace_ride.RIDE_ASSET for n, _b in files)                                      # the ride names exactly the files that are published
    notice = (palace_ride_gfx.TEX_DIR / "NOTICE").read_text()
    assert "palace_tex_bake.py" in notice


def test_the_textures_are_kept_a_year_one_literal_rule_each():
    from alto.publish_static import _headers, _tex_rules
    names = [n for n, _b in palace_ride_gfx.tex_files()]
    rules = [x for x in _headers("c", "c", [], names) if x["source"].startswith("/tex/")]
    assert [r["source"] for r in rules] == ["/tex/" + n for n in names]
    assert all(r["headers"][0]["value"] == "public, max-age=31536000, immutable" for r in rules)
    assert _tex_rules(["../evil.png", "alto-tex0-zz.png"]) == []
