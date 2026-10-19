"""Part GFX of the first-person ride (1.9.103, owner: the gfx agent): quality tiers, the WebGL2 context with a 4x MSAA render target, the
dynamic-resolution governor, the hosted material textures and the ?palperf=1 overlay.  The renderer itself stays in palace_ride_gl.py; it calls
the hooks below at five fenced places (context, programs, frame size, frame begin/end, world uniforms).

Tiers (GFX.tier)
  high     WebGL2 + 4x MSAA renderbuffer resolved by a blit; render scale governed between 1.0 and the native device pixel ratio; the GFX shader path
           (golden-hour light, sky/ground ambient with canyon occlusion, environment reflections, neutral tone curve) with the material textures
  medium   the same with 2x MSAA, the scale capped at 1.5, one texture tap per material instead of two
  legacy   exactly 1.9.102: a WebGL1 context with the browser's own antialias, the 1.9.102 shaders, the 2.3 MP canvas cap.  Chosen when WebGL2 or its
           multisampled target is missing, on a software renderer, or forced with ?palgl=1 (tests) / ?paltier=legacy
  Chosen from a probe on a throwaway canvas (WebGL2? MSAA? which renderer?) before the real context exists, then a warm-up: frames slower than ~18 ms
  with the scale already at its floor step the tier down (high -> medium -> legacy shaders, same context).

Governor (gfxGov, a pure function of its state and the frame interval): the scale moves in 0.25 steps.  Down when a ~0.4 s window (24 frames) has its
75th percentile over 19.5 ms or its mean over 19 ms (frames are missing vsync); up only after 3 s of windows whose 90th percentile is within 18.2 ms
(Safari's clock is coarse: a 60 Hz frame reads 16-18 ms); a step up that is followed by a step down within 4 s sets a ceiling at the lower
level, so it never oscillates (at most one bounce per tier).  A changed scale resizes the GL canvas and its render targets between two frames; nothing is
dithered or blended in time.

Textures (GFX_TEX): two 512 px PNGs under /tex/ (content-hashed names, alto/assets/tex), each channel one material's grey detail (normalised to mean .5):
  tex0 R asphalt  G concrete  B roof gravel;  tex1 R brick face  G limestone  B wall grime streaks.
Fetched after the first frames (never before the city is on screen), decoded with createImageBitmap (else an <img> on a blob URL), mip-mapped, and faded in
over ~1 s (uTxA).  A 404 or a decode error leaves uTxA at 0: the procedural look of 1.9.102 stays exactly as it was.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

TEX_DIR = Path(__file__).resolve().parent.parent / "assets" / "tex"
TEX_FOLDER = "tex"
TEX_SRC = ("alto-tex0.png", "alto-tex1.png")
TEX_RE = re.compile(r"^alto-tex[01]-[0-9a-f]{10}\.png$")


def tex_files() -> list:
    """[(published name, bytes)]: each texture under a name carrying the hash of its bytes (it never changes under that name). Missing sources are skipped
    (the ride then keeps the procedural look)."""
    out = []
    for src in TEX_SRC:
        p = TEX_DIR / src
        if p.is_file():
            b = p.read_bytes()
            out.append((src[:-4] + "-" + hashlib.sha256(b).hexdigest()[:10] + ".png", b))
    return out


def _tex_paths() -> list:
    return ["/" + TEX_FOLDER + "/" + n for n, _b in tex_files()]


CSS_GFX = r"""
  #pal-ride .pr-perf{position:absolute;left:12px;bottom:12px;z-index:3;padding:6px 9px;border-radius:8px;font:600 11px/1.35 ui-monospace,Menlo,monospace;color:#e8f0ff;
    background:rgba(8,10,18,.72);white-space:pre;pointer-events:none;}
"""

_JS_GFX = r"""
/* ── gfx tiers, MSAA target, resolution governor, material textures (palace_ride_gfx.py) ── */
var GFX={tier:'legacy', wgl2:false, probe:null, q:null, fb:null, rs:1, gov:null, tx:[null,null], txT0:0, txReq:0, txErr:'', last:0, iv:[], perf:null, down:0};
function gfxQ(){ if(GFX.q) return GFX.q; var q={}; try{ String(location.search||'').replace(/^\?/,'').split('&').forEach(function(kv){ var p=kv.split('='); if(p[0]) q[decodeURIComponent(p[0])]=decodeURIComponent(p[1]||'1'); }); }catch(x){} GFX.q=q; return q; }
/* the tier from what the probe found: a pure function (tests) */
function gfxPickTier(o){ var f=o.force; if(f==='high'||f==='medium'||f==='legacy') return (f!=='legacy'&&!o.msaa)?'legacy':f;
  if(o.gl1 || !o.wgl2 || !o.msaa) return 'legacy';
  var r=String(o.renderer||'').toLowerCase(); if(/swiftshader|llvmpipe|softpipe|software|microsoft basic/.test(r)) return 'legacy';
  if(/mali-[gt][0-9]{2}\b|adreno \(tm\) [3-5][0-9]{2}|powervr|intel\(r\) hd graphics [2-5][0-9]{2,3}\b|intel hd graphics [2-5]/.test(r) || (o.samples||0)<4) return 'medium';
  return 'high'; }
/* WebGL2 + a multisampled target on a throwaway canvas: is it there, how many samples, which renderer */
function gfxProbe(){
  if(GFX.probe) return GFX.probe; var q=gfxQ(), o={wgl2:false, msaa:false, samples:0, renderer:'', gl1:q.palgl==='1', force:q.paltier||''}; GFX.probe=o;
  if(o.gl1 || window._palRideNoGL2) return o;
  try{ var cv=document.createElement('canvas'); cv.width=8; cv.height=8; var gl=cv.getContext('webgl2',{alpha:false, antialias:false, depth:true, stencil:false});
    if(!gl) return o; o.wgl2=true; var dbg=gl.getExtension('WEBGL_debug_renderer_info'); o.renderer=dbg?String(gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL)):'';
    o.samples=Math.min(4, gl.getParameter(gl.MAX_SAMPLES)|0);
    if(o.samples>=2){ var t=gfxTarget(gl,8,8,o.samples,null); if(t){ o.msaa=true; gfxFreeTarget(gl,t); } }
    var lx=gl.getExtension('WEBGL_lose_context'); if(lx) lx.loseContext(); }catch(x){ o.msaa=false; }
  return o; }
/* the real context: WebGL2 without the browser's antialias (the MSAA target does it) for high/medium, else null and the caller makes the WebGL1 one */
function gfxContext(cv){ var o=gfxProbe(); GFX.tier=gfxPickTier(o); if(GFX.tier==='legacy') return null;
  var gl=null; try{ gl=cv.getContext('webgl2',{alpha:false, antialias:false, depth:true, stencil:false, powerPreference:'high-performance', preserveDrawingBuffer:false}); }catch(x){ gl=null; }
  if(!gl){ GFX.tier='legacy'; return null; } GFX.wgl2=true; return gl; }
/* the shader defines for the tier (legacy: none: the 1.9.102 shaders word for word) */
function gfxDefs(){ return GFX.tier==='high'?'#define GFX 1\n#define GFX_HI 1\n':GFX.tier==='medium'?'#define GFX 1\n':''; }
/* WebGL2 has these in core: the shims the renderer's WebGL1 calls expect */
function gfxShim(gl){ if(!GFX.wgl2) return; GLX.inst={vertexAttribDivisorANGLE:function(i,d){ gl.vertexAttribDivisor(i,d); }, drawArraysInstancedANGLE:function(m,f,c,n){ gl.drawArraysInstanced(m,f,c,n); }}; }
function gfxTarget(gl,w,h,samples,old){ if(old) gfxFreeTarget(gl,old);
  var fb=gl.createFramebuffer(), rc=gl.createRenderbuffer(), rd=gl.createRenderbuffer();
  gl.bindRenderbuffer(gl.RENDERBUFFER,rc); gl.renderbufferStorageMultisample(gl.RENDERBUFFER,samples,gl.RGBA8,w,h);
  gl.bindRenderbuffer(gl.RENDERBUFFER,rd); gl.renderbufferStorageMultisample(gl.RENDERBUFFER,samples,gl.DEPTH_COMPONENT24,w,h);
  gl.bindFramebuffer(gl.FRAMEBUFFER,fb); gl.framebufferRenderbuffer(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.RENDERBUFFER,rc); gl.framebufferRenderbuffer(gl.FRAMEBUFFER,gl.DEPTH_ATTACHMENT,gl.RENDERBUFFER,rd);
  var ok=gl.checkFramebufferStatus(gl.FRAMEBUFFER)===gl.FRAMEBUFFER_COMPLETE; var t={fb:fb, rc:rc, rd:rd, w:w, h:h, s:samples, rfb:null, rt:null};
  if(ok){ /* the resolve goes through a plain RGBA8 target, then a plain blit to the canvas (WebKit refuses a multisampled blit straight to an alpha:false canvas) */
    var rfb=gl.createFramebuffer(), rt=gl.createRenderbuffer(); gl.bindRenderbuffer(gl.RENDERBUFFER,rt); gl.renderbufferStorage(gl.RENDERBUFFER,gl.RGBA8,w,h);
    gl.bindFramebuffer(gl.FRAMEBUFFER,rfb); gl.framebufferRenderbuffer(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.RENDERBUFFER,rt); ok=gl.checkFramebufferStatus(gl.FRAMEBUFFER)===gl.FRAMEBUFFER_COMPLETE; t.rfb=rfb; t.rt=rt; }
  gl.bindFramebuffer(gl.FRAMEBUFFER,null); gl.bindRenderbuffer(gl.RENDERBUFFER,null);
  if(!ok){ gfxFreeTarget(gl,t); return null; } return t; }
function gfxFreeTarget(gl,t){ if(!t) return; try{ gl.deleteFramebuffer(t.fb); gl.deleteRenderbuffer(t.rc); gl.deleteRenderbuffer(t.rd); if(t.rfb){ gl.deleteFramebuffer(t.rfb); gl.deleteRenderbuffer(t.rt); } }catch(x){} }
/* called by glSetup once the programs are made (and again after a context restore) */
function gfxInit(gl){ GLX.gfx=GFX; GFX.fb=null; GFX.tx=[null,null]; GFX.txT0=0; GFX.txReq=0; GFX.txErr=''; GFX.iv=[]; GFX.last=0;
  var n=window.devicePixelRatio||1, hi=GFX.tier==='high'?n:Math.min(n,1.5);
  if(!GFX.gov || GFX.gov.tier!==GFX.tier){ var s0=Math.max(1,Math.min(hi,Math.sqrt(2.3e6/Math.max(1,(R.w||innerWidth)*(R.h||innerHeight))))); s0=Math.max(1,Math.round(s0*4)/4); GFX.gov=gfxGovNew(Math.min(1,n),Math.max(Math.min(1,n),hi),s0); GFX.gov.tier=GFX.tier; }
  if(navigator.webdriver && gfxQ().palgov!=='1') GFX.gov.pin=1;      /* under automation the scale holds still (pixel tests compare frames) unless ?palgov=1 */
  var pin=+gfxQ().palscale; if(pin>0){ GFX.gov.s=GFX.gov.lo=GFX.gov.hi=Math.max(.5,Math.min(n,pin)); GFX.gov.pin=1; }     /* ?palscale=x pins the scale (QA, the owner's check) */
  if(gfxQ().palperf==='1' && !GFX.perf && R.ov){ GFX.perf=document.createElement('div'); GFX.perf.className='pr-perf'; R.ov.appendChild(GFX.perf); } }
/* ── the governor: pure (state, frame interval ms, now ms) -> 'up' | 'down' | '' ; the caller applies g.s ── */
function gfxGovNew(lo,hi,s){ return {lo:lo, hi:hi, s:Math.min(hi,Math.max(lo,s)), ceil:hi, buf:[], tChange:-1e9, tUp:-1e9, good:0, step:.25}; }
function gfxGov(g,dt,now){ if(g.pin) return '';
  if(!(dt>3) || dt>100){ g.buf.length=0; g.good=now; return ''; }         /* a pause, a QA burst: not a frame interval */
  g.buf.push(dt); if(g.buf.length<24) return '';
  var a=g.buf.slice().sort(function(p,q){ return p-q; }), p75=a[Math.floor(a.length*.75)], p90=a[Math.floor(a.length*.9)], mean=0; a.forEach(function(v){ mean+=v/a.length; }); g.buf.length=0;
  if(p75>19.5 || mean>19){ g.good=now; if(g.s<=g.lo+1e-6) return 'floor';
    if(now-g.tUp<4000) g.ceil=Math.max(g.lo,g.s-g.step);                  /* the step up did not hold: never try that level again */
    g.s=Math.max(g.lo,g.s-g.step); g.tChange=now; return 'down'; }
  if(p90>18.2){ g.good=now; return ''; }
  if(now-g.good>=3000 && now-g.tChange>=3000 && g.s+g.step<=Math.min(g.hi,g.ceil)+1e-6){ g.s=Math.min(g.hi,g.ceil,g.s+g.step); g.tChange=now; g.tUp=now; g.good=now; return 'up'; }
  return ''; }
/* the size the GL canvas draws at: legacy keeps 1.9.102's (the 2D canvas's size) */
function gfxSize(){ if(GFX.tier==='legacy' || !GFX.gov) return [R.cv.width,R.cv.height]; var s=GFX.gov.s; return [Math.max(1,Math.round(R.w*s)),Math.max(1,Math.round(R.h*s))]; }
function gfxTierDown(){ var gl=GLX.gl; if(!gl || GFX.tier==='legacy') return;
  GFX.tier=GFX.tier==='high'?'medium':'legacy'; GFX.down++;
  try{ glPrograms(gl); }catch(x){ GLX.err=String(x&&x.message||x); }
  var n=window.devicePixelRatio||1, keep=GFX.gov; GFX.gov=gfxGovNew(keep.lo,GFX.tier==='medium'?Math.max(keep.lo,Math.min(n,1.5)):keep.lo,keep.lo); GFX.gov.tier=GFX.tier;
  if(GFX.fb){ gfxFreeTarget(gl,GFX.fb); GFX.fb=null; } }
/* the frame: begin binds the MSAA target at the frame's size (re-made when the size changes), end resolves it to the canvas */
function gfxBegin(gl,cw,ch){ if(!GFX.wgl2) return;
  var smp=GFX.tier==='high'?GFX.probe.samples:Math.min(2,GFX.probe.samples);
  if(!GFX.fb || GFX.fb.w!==cw || GFX.fb.h!==ch || GFX.fb.s!==smp){ var t=gfxTarget(gl,cw,ch,smp,GFX.fb); GFX.fb=t; if(!t){ GFX.wgl2fail=1; } }
  if(GFX.fb){ gl.bindFramebuffer(gl.FRAMEBUFFER,GFX.fb.fb); } gl.viewport(0,0,cw,ch); }
function gfxEnd(gl,cw,ch){ var now=performance.now();
  if(GFX.wgl2 && GFX.fb){ var t=GFX.fb; gl.bindFramebuffer(gl.READ_FRAMEBUFFER,t.fb);
    if(t.rfb){ gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,t.rfb); gl.blitFramebuffer(0,0,cw,ch,0,0,cw,ch,gl.COLOR_BUFFER_BIT,gl.NEAREST); gl.bindFramebuffer(gl.READ_FRAMEBUFFER,t.rfb); }
    gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,null); gl.blitFramebuffer(0,0,cw,ch,0,0,cw,ch,gl.COLOR_BUFFER_BIT,gl.NEAREST); gl.bindFramebuffer(gl.FRAMEBUFFER,null); }
  /* the governor and the warm-up see the interval between frames */
  var dt=GFX.last?now-GFX.last:0; GFX.last=now; var gdt=GLX.st.pending>0?0:dt;      /* frames that build streamed cells are not the resolution's fault */
  if(dt>0 && dt<1000){ GFX.iv.push(dt); if(GFX.iv.length>240) GFX.iv.shift(); }
  if(GFX.gov && GFX.tier!=='legacy'){ var r=gfxGov(GFX.gov,gdt,now); if(r==='floor'){ gfxTierDown(); } }
  if(GLX.frame>2 && !GFX.txReq) gfxTexLoad(gl);
  if(GFX.perf && (!GFX.perfT || now-GFX.perfT>500)){ GFX.perfT=now; var a=GFX.iv.slice().sort(function(p,q){ return p-q; }), n=a.length;
    GFX.perf.textContent='tier '+GFX.tier+(GFX.wgl2?' webgl2 msaa'+(GFX.fb?GFX.fb.s:0):' webgl1')+'\nscale '+(GFX.gov?GFX.gov.s.toFixed(2):'-')+' '+cw+'x'+ch+'\nframe p50 '+(n?a[n>>1].toFixed(1):'-')+' p95 '+(n?a[Math.min(n-1,Math.floor(n*.95))].toFixed(1):'-')+' ms\ntextures '+(GFX.tx[0]&&GFX.tx[1]?'on':GFX.txErr||'loading'); } }
/* ── the material textures: hosted, lazy, faded in; any failure keeps the procedural look ── */
var GFX_TEX=__GFX_TEX__;
function gfxTexLoad(gl){ GFX.txReq=1; if(GFX.tier==='legacy' || GFX_TEX.length<2 || typeof fetch!=='function'){ GFX.txErr='off'; return; } var gen=GLX.gen;
  GFX_TEX.forEach(function(u,i){
    fetch(u,{credentials:'same-origin'}).then(function(r){ if(!r.ok) throw new Error('http '+r.status); return r.blob(); })
      .then(function(b){ if(typeof createImageBitmap==='function') return createImageBitmap(b);
        return new Promise(function(ok,no){ var im=new Image(), url=URL.createObjectURL(b); im.onload=function(){ URL.revokeObjectURL(url); ok(im); }; im.onerror=function(){ URL.revokeObjectURL(url); no(new Error('decode')); }; im.src=url; }); })
      .then(function(img){ if(gen!==GLX.gen || !glOk()) return; var g=GLX.gl, tx=g.createTexture(); g.bindTexture(g.TEXTURE_2D,tx);
        g.texImage2D(g.TEXTURE_2D,0,g.RGBA,g.RGBA,g.UNSIGNED_BYTE,img); g.texParameteri(g.TEXTURE_2D,g.TEXTURE_WRAP_S,g.REPEAT); g.texParameteri(g.TEXTURE_2D,g.TEXTURE_WRAP_T,g.REPEAT);
        g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MAG_FILTER,g.LINEAR); g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MIN_FILTER,g.LINEAR_MIPMAP_LINEAR); g.generateMipmap(g.TEXTURE_2D);
        var ax=g.getExtension('EXT_texture_filter_anisotropic'); if(ax) g.texParameterf(g.TEXTURE_2D,ax.TEXTURE_MAX_ANISOTROPY_EXT,8);
        g.bindTexture(g.TEXTURE_2D,null); GFX.tx[i]=tx; if(GFX.tx[0]&&GFX.tx[1]) GFX.txT0=performance.now(); })
      .then(null,function(e){ GFX.txErr=String(e&&e.message||e||'error'); }); }); }
/* the world program's extra uniforms: the two textures on units 5 and 6 and their fade (0 until both are in) */
function gfxUni(gl,pg){ if(GFX.tier==='legacy' || !pg.u.uTx0) return; var on=GFX.tx[0]&&GFX.tx[1], a=0;
  if(on){ a=Math.min(1,(performance.now()-GFX.txT0)/1000); a=a*a*(3-2*a); if(GFX.q&&GFX.q.paltexnow==='1') a=1; }
  gl.activeTexture(gl.TEXTURE5); gl.bindTexture(gl.TEXTURE_2D,on?GFX.tx[0]:null); gl.activeTexture(gl.TEXTURE6); gl.bindTexture(gl.TEXTURE_2D,on?GFX.tx[1]:null); gl.activeTexture(gl.TEXTURE0);
  gl.uniform1i(pg.u.uTx0,5); gl.uniform1i(pg.u.uTx1,6); gl.uniform1f(pg.u.uTxA,on?a:0); }
/* the light for the GFX tiers: a soft golden-hour sun (~28 degrees up, warm), a cool sky fill and a warm ground bounce; night stays 1.9.102's */
function gfxLight(L){ if(GFX.tier==='legacy' || L.dk) return L;
  var el=28*Math.PI/180, az=Math.atan2(-.66,-.55); L.sun=[Math.cos(el)*Math.cos(az), Math.cos(el)*Math.sin(az), Math.sin(el)];
  L.sunCol=[2.35,1.96,1.45]; L.skyA=[.62,.72,.90]; L.gndA=[.30,.26,.21]; L.exp=1.0; return L; }
GFX.pick=gfxPickTier; GFX.govNew=gfxGovNew; GFX.govStep=gfxGov;
"""


def js_gfx() -> str:
    return _JS_GFX.replace("__GFX_TEX__", json.dumps(_tex_paths()))


JS_GFX = js_gfx()
