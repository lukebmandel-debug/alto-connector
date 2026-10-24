"""The FPV graphics pass of the museum walk (palace_building_fpv.py, hosted /bldg/), once shared with the city roam
(retired to _cold-storage/memory-map-fpv). GFX_JS defines `FXG` inside each renderer's closure, the way fpv_avatar.py's AVATAR_JS does; nothing
here reaches a page, so page bytes and the page fingerprint stay as they are.

Assets (alto/assets/gfx, every one CC0; sources and licences in alto/assets/gfx/NOTICE): hosted under /gfx/ with the hash of their bytes in the
name (immutable, a year in the browser), fetched lazily, and never by the low tier:
  <material>-a1024 / -a512 / -b512 .ktx2   real PBR sets (Poly Haven, ambientCG) packed the renderers' way: A = albedo (sRGB) + roughness
                                           (ETC1S), B = normal X/Y + height + cavity (UASTC, RDO, Zstandard). high: a1024 + b512, medium: a512 + b512
  env-2048 / env-1024 .ktx2                the HDRI sky (Poly Haven kloofendal_48d_partly_cloudy_puresky): sun painted out (the renderers draw their
                                           own sun and its light), exposure matched to their analytic sky, Reinhard-encoded c/(c+K), ETC1S, mips =
                                           rough reflections; its 9 irradiance SH coefficients and the sun's place in the image ride in GFX_JS
  basis_transcoder .js/.wasm               Binomial's Basis Universal transcoder as three.js ships it (Apache-2.0), run on the main thread, a few ms
                                           of transcoding a frame (FXG.pump); WebAssembly needs 'wasm-unsafe-eval' in the site CSP (publish_static)
Without WebAssembly, or when a file is missing, every feature that needs it is simply absent: the procedural look stays.

FXG.post(gl): the post chain after a renderer's 4x/2x MSAA pass: one blit resolves colour AND depth into textures, then half-resolution SSAO
(normals from depth, 6..12 hemisphere taps, bilateral blur), a bloom (bright pass at 1/2, dual-filter down to 1/16 and back) and one composite
draw to the canvas. A target that is not complete, or a GL error on the first frame, sets .ok = false and the renderer keeps its plain blit.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

GFX_DIR = Path(__file__).resolve().parent.parent / "assets" / "gfx"
FOLDER = "gfx"
NAME_RE = re.compile(r"^[a-z0-9_]+(-[a-z0-9]+)*-[0-9a-f]{10}\.(ktx2|wasm|js|glb)$")
_SRC_RE = re.compile(r"^[a-z0-9_]+(-[a-z0-9]+)*\.(ktx2|wasm|js|glb)$")


def _hashed(p: Path) -> str:
    b = p.read_bytes()
    return p.stem + "-" + hashlib.sha256(b).hexdigest()[:10] + p.suffix


def files() -> list:
    """[(published name, bytes)] of every hosted graphics file (alto/assets/gfx and its tex/ and mdl/ folders)."""
    out = []
    if GFX_DIR.is_dir():
        for p in sorted(GFX_DIR.rglob("*")):
            if p.is_file() and _SRC_RE.match(p.name):
                out.append((_hashed(p), p.read_bytes()))
    return out


def _manifest() -> dict:
    """What GFX_JS needs to know: the hashed paths and the small metadata (tile sizes, the sky's SH and sun)."""
    def path(rel):
        p = GFX_DIR / rel
        return "/" + FOLDER + "/" + _hashed(p) if p.is_file() else None
    m = {"basis": None, "meshopt": path("meshopt_decoder.js"), "env": None, "tex": {}, "mdl": {}}
    js, wasm = path("basis_transcoder.js"), path("basis_transcoder.wasm")
    if js and wasm:
        m["basis"] = {"js": js, "wasm": wasm}
    ej = GFX_DIR / "env.json"
    if ej.is_file():
        e = json.loads(ej.read_text())
        # env.json's coefficients reconstruct E(n) with E(up) = pi; the shaders read E/pi (radiance-like, 1 at the zenith)
        m["env"] = {"az": round(e["sun_az"], 4), "el": round(e["sun_el"], 4), "K": e["K"], "sh": [[round(c / math.pi, 5) for c in r] for r in e["sh"]], "hor": e["hor"],
                    "px": {k: path(f"env-{k}.ktx2") for k in ("2048", "1024") if path(f"env-{k}.ktx2")}}
    tj = GFX_DIR / "tex" / "meta.json"
    if tj.is_file():
        for name, t in sorted(json.loads(tj.read_text()).items()):
            f = {k: path(f"tex/{name}-{k}.ktx2") for k in ("a1024", "a512", "b512")}
            if all(f.values()):
                m["tex"][name] = dict(f, tile=t["tile"], mean=t.get("mean"))
    mj = GFX_DIR / "mdl" / "meta.json"
    if mj.is_file():
        for name, t in sorted(json.loads(mj.read_text()).items()):
            g = path(f"mdl/{name}.glb")
            if g:
                m["mdl"][name] = dict(t, glb=g)
    return m


IBL_GLSL = r"""
#ifdef IBL
uniform vec3 uSH[9]; uniform vec4 uEnvP; uniform vec4 uIbl; uniform vec3 uShH;
vec3 envDir(vec3 d){ return vec3(d.x*uEnvP.x-d.y*uEnvP.y,d.x*uEnvP.y+d.y*uEnvP.x,d.z); }
vec3 shIrr(vec3 n){ n=envDir(n); return max(vec3(0.),uSH[0]*.282095+uSH[1]*(.488603*n.y)+uSH[2]*(.488603*n.z)+uSH[3]*(.488603*n.x)+uSH[4]*(1.092548*n.x*n.y)
  +uSH[5]*(1.092548*n.y*n.z)+uSH[6]*(.315392*(3.*n.z*n.z-1.))+uSH[7]*(1.092548*n.x*n.z)+uSH[8]*(.546274*(n.x*n.x-n.y*n.y))); }
#ifdef ENV
uniform sampler2D uEnv;
vec3 hdrAt(vec3 d, float lod){ d=envDir(d); vec2 q=vec2(atan(d.y,d.x)*.1591549+.5,.5-asin(clamp(d.z,-1.,1.))*.3183099);
#ifdef ENV_LOD
  vec3 c=min(textureLod(uEnv,q,lod).rgb,vec3(.996));
#else
  vec3 c=min(texture2D(uEnv,q,-16.).rgb,vec3(.996));            /* GLSL ES 1.00 (the city): the top level only, no seam where the longitude wraps */
#endif
  return uEnvP.z*c/(1.-c); }
#endif
#endif
"""


# the city's copy (GLSL ES 1.00): no textureLod branch, guards named GFX_* so its legacy tier strips them with its own #ifdef GFX blocks
IBL_GLSL_CITY = re.sub(r"#ifdef ENV_LOD\n.*?#else\n(.*?)#endif\n", r"\1", IBL_GLSL, flags=re.S).replace("#ifdef IBL", "#ifdef GFX_IBL").replace("#ifdef ENV", "#ifdef GFX_ENV")
GFX_JS = r"""
/* ── FXG: the FPV graphics pass (fpv_gfx.py), shared by the museum walk and the city roam ── */
var FXG=(function(){
var A=__FXG_ASSETS__, X={A:A, err:'', loads:0, bytes:0, cache:{}, cacheBytes:0}, D=typeof document!=='undefined'?document:null;
function txt(r){ if(!r.ok) throw new Error(r.status+' '+r.url); return r.text(); }
function bin(r){ if(!r.ok) throw new Error(r.status+' '+r.url); return r.arrayBuffer(); }
/* the Basis transcoder: fetched once (immutable), run on the main thread; a CSP without 'wasm-unsafe-eval' or no WebAssembly rejects it, and the
   textures and the sky simply stay procedural */
var bp=null;
X.basis=function(){ if(bp) return bp;
  bp=new Promise(function(ok,no){ if(typeof WebAssembly!=='object'||!A.basis||typeof fetch!=='function'){ no(new Error('no wasm')); return; }
    Promise.all([fetch(A.basis.js).then(txt),fetch(A.basis.wasm).then(bin)]).then(function(v){
      if(typeof window.BASIS!=='function'){ var s=D.createElement('script'); s.text=v[0]+'\n;window.BASIS=BASIS;'; (D.head||D.documentElement).appendChild(s); if(s.parentNode) s.parentNode.removeChild(s); }
      if(typeof window.BASIS!=='function') throw new Error('transcoder script');
      return window.BASIS({wasmBinary:v[1]}); }).then(function(M){ M.initializeBasis(); ok(M); }).catch(function(e){ X.err='basis: '+(e&&e.message||e); no(e); }); });
  bp.catch(function(){}); return bp; };
/* the GPU format the transcoder writes: ASTC (Apple GPUs), BC7 (desktop), ETC2 (Android), BC3, else plain RGBA */
X.fmt=function(gl){ if(gl._fxgF) return gl._fxgF; var e, f={t:13, gl:0, n:'rgba'};
  if((e=gl.getExtension('WEBGL_compressed_texture_astc'))&&e.COMPRESSED_RGBA_ASTC_4x4_KHR) f={t:10, gl:e.COMPRESSED_RGBA_ASTC_4x4_KHR, n:'astc'};
  else if((e=gl.getExtension('EXT_texture_compression_bptc'))) f={t:6, gl:e.COMPRESSED_RGBA_BPTC_UNORM_EXT, n:'bc7'};
  else if((e=gl.getExtension('WEBGL_compressed_texture_etc'))) f={t:1, gl:e.COMPRESSED_RGBA8_ETC2_EAC, n:'etc2'};
  else if((e=gl.getExtension('WEBGL_compressed_texture_s3tc')||gl.getExtension('WEBKIT_WEBGL_compressed_texture_s3tc'))) f={t:3, gl:e.COMPRESSED_RGBA_S3TC_DXT5_EXT, n:'bc3'};
  gl._fxgF=f; return f; };
var Q=[];
/* fetch a .ktx2, transcode it (queued: FXG.pump spends a few ms a frame on the queue) and hand cb a mip-mapped texture {tx, w, h, bytes} or null;
   opt: {clampT: true for the equirect sky, aniso: the extension object, an: its level} */
X.ktx2=function(gl,url,opt,cb){ if(!url){ cb(null); return; } X.loads++; var f=X.fmt(gl), key=url+'|'+f.n, c=X.cache[key];
  if(c){ Q.push({gl:gl, lv:c, opt:opt||{}, cb:cb}); return; }
  fetch(url).then(bin).then(function(buf){ return X.basis().then(function(M){ Q.push({M:M, gl:gl, buf:buf, key:key, opt:opt||{}, cb:cb}); }); })
    .catch(function(e){ X.err=String(e&&e.message||e); cb(null); }); };
X.pending=function(){ return Q.length; };
X.pump=function(ms){ var t0=performance.now(); while(Q.length){ var j=Q.shift(), r=null; if(j.gl.isContextLost&&j.gl.isContextLost()) continue;
    try{ r=up(j); }catch(e){ X.err='ktx2: '+(e&&e.message||e); r=null; } j.cb(r); if(performance.now()-t0>ms) break; } };
function levels(j){ var M=j.M, K=new M.KTX2File(new Uint8Array(j.buf)), f=X.fmt(j.gl), out=[], bytes=0;
  try{ if(!K.isValid()||!K.startTranscoding()) throw new Error('not a KTX2 the transcoder takes');
    var w=K.getWidth(), h=K.getHeight(), n=K.getLevels();
    for(var lv=0;lv<n;lv++){ var d=new Uint8Array(K.getImageTranscodedSizeInBytes(lv,0,0,f.t)); if(!K.transcodeImage(d,lv,0,0,f.t,0,-1,-1)) throw new Error('transcode level '+lv);
      out.push({w:Math.max(1,w>>lv), h:Math.max(1,h>>lv), d:d}); bytes+=d.length; } }
  finally{ K.close(); K.delete(); }
  out.bytes=bytes; if(X.cacheBytes+bytes<48e6){ X.cache[j.key]=out; X.cacheBytes+=bytes; } return out; }
function up(j){ var gl=j.gl, f=X.fmt(gl), L=j.lv||levels(j), tx=gl.createTexture(), o=j.opt;
  gl.bindTexture(gl.TEXTURE_2D,tx); gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,false);
  for(var i=0;i<L.length;i++){ var l=L[i]; if(f.gl) gl.compressedTexImage2D(gl.TEXTURE_2D,i,f.gl,l.w,l.h,0,l.d); else gl.texImage2D(gl.TEXTURE_2D,i,gl.RGBA,l.w,l.h,0,gl.RGBA,gl.UNSIGNED_BYTE,l.d); }
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.REPEAT); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,o.clampT?gl.CLAMP_TO_EDGE:gl.REPEAT);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,L.length>1?gl.LINEAR_MIPMAP_LINEAR:gl.LINEAR);
  if(o.aniso) gl.texParameterf(gl.TEXTURE_2D,o.aniso.TEXTURE_MAX_ANISOTROPY_EXT,o.an||4);
  X.bytes+=L.bytes; return {tx:tx, w:L[0].w, h:L[0].h, bytes:L.bytes}; }

/* ── props: a .glb of ONE primitive (POSITION, NORMAL, indices; EXT_meshopt_compression, zeux's decoder fetched once) -> {p, n, i} typed arrays ── */
var mp=null;
X.meshopt=function(){ if(mp) return mp;
  mp=new Promise(function(ok,no){ if(typeof WebAssembly!=='object'||!A.meshopt||typeof fetch!=='function'){ no(new Error('no wasm')); return; }
    fetch(A.meshopt).then(txt).then(function(code){ if(!window.MeshoptDecoder){ var s=D.createElement('script'); s.text='(function(){ var module={exports:{}}, exports=module.exports;\n'+code+'\n;window.MeshoptDecoder=module.exports; })();'; (D.head||D.documentElement).appendChild(s); if(s.parentNode) s.parentNode.removeChild(s); }
      var M=window.MeshoptDecoder; if(!M||!M.ready) throw new Error('meshopt script'); return M.ready.then(function(){ ok(M); }); }).catch(function(e){ X.err='meshopt: '+(e&&e.message||e); no(e); }); });
  mp.catch(function(){}); return mp; };
X.glb=function(url,cb){ if(!url){ cb(null); return; } X.loads++;
  Promise.all([fetch(url).then(bin),X.meshopt()]).then(function(v){ var b=v[0], M=v[1], dv=new DataView(b), jl=dv.getUint32(12,true), g=JSON.parse(new TextDecoder().decode(new Uint8Array(b,20,jl))), bo=20+jl+8, BIN=new Uint8Array(b,bo,dv.getUint32(20+jl,true));
    var views=g.bufferViews.map(function(bv){ var e=bv.extensions&&bv.extensions.EXT_meshopt_compression; if(!e) return BIN.subarray(bv.byteOffset||0,(bv.byteOffset||0)+bv.byteLength);
      var t=new Uint8Array(e.count*e.byteStride); M.decodeGltfBuffer(t,e.count,e.byteStride,BIN.subarray(e.byteOffset||0,(e.byteOffset||0)+e.byteLength),e.mode,e.filter||'NONE'); return t; });
    var get=function(i){ var a=g.accessors[i], v=views[a.bufferView], o=(a.byteOffset||0)+v.byteOffset, n=a.count*({SCALAR:1,VEC2:2,VEC3:3,VEC4:4})[a.type];
      return a.componentType===5126?new Float32Array(v.buffer.slice(o,o+n*4)):a.componentType===5125?new Uint32Array(v.buffer.slice(o,o+n*4)):new Uint16Array(v.buffer.slice(o,o+n*2)); };
    var pr=g.meshes[0].primitives[0]; cb({p:get(pr.attributes.POSITION), n:get(pr.attributes.NORMAL), i:get(pr.indices)}); }).catch(function(e){ X.err='glb: '+(e&&e.message||e); cb(null); }); };

/* ── the sky as light: SH irradiance (normalised: the zenith's E/pi = 1) and the equirect for reflections and the background ── */
X.env=A.env;
X.envRot=function(sun){ var E=A.env; if(!E) return [1,0]; var r=Math.atan2(sun[1],sun[0])-E.az; return [Math.cos(-r),Math.sin(-r)]; };
X.sh=function(k){ var E=A.env, o=new Float32Array(27); if(!E) return o; for(var i=0;i<9;i++) for(var c=0;c<3;c++) o[i*3+c]=E.sh[i][c]*k; return o; };
X.shH=function(k){ var E=A.env; if(!E) return [1,1,1]; var o=[0,0,0]; for(var c=0;c<3;c++) o[c]=(E.sh[0][c]*.282095-E.sh[6][c]*.315392)*k; return o; };
X.hor=function(k){ var h=A.env?A.env.hor:[1,1,1]; return [h[0]*k,h[1]*k,h[2]*k]; };
/* GLSL (IBL_GLSL): define IBL for the SH ambient, ENV (WebGL2) for the sky texture; uEnvP = (cos, sin of the sky's turn, K, env on), uIbl = the renderer's (ambient k, reflection k, sky blend, -) */
X.GLSL=__IBL_GLSL__;
X.uni=function(gl,u,sun,k,envTx,unit){ if(u.uSH) gl.uniform3fv(u.uSH,X.sh(k)); if(u.uShH) gl.uniform3fv(u.uShH,X.shH(k)); if(u.uEnvP){ var r=X.envRot(sun); gl.uniform4fv(u.uEnvP,[r[0],r[1],A.env?A.env.K:2,envTx?1:0]); }
  if(u.uEnv){ gl.activeTexture(gl.TEXTURE0+unit); gl.bindTexture(gl.TEXTURE_2D,envTx||null); gl.uniform1i(u.uEnv,unit); gl.activeTexture(gl.TEXTURE0); } };

/* ── the post chain (WebGL2): resolve colour + depth, SSAO at half size, bloom, composite ── */
var VS="#version 300 es\nin vec2 aQ; out vec2 vQ; void main(){ vQ=aQ*.5+.5; gl_Position=vec4(aQ,0.,1.); }";
var H="#version 300 es\nprecision highp float; precision highp sampler2D; in vec2 vQ; out vec4 o;\nuniform vec4 uPr; uniform vec2 uPx; uniform vec2 uPo;\n"+
  "float lz(float d){ float z=d*2.-1.; return 2.*uPr.x*uPr.y/(uPr.y+uPr.x-z*(uPr.y-uPr.x)); }\n";
var FS={
  ao:H+"uniform sampler2D uD; uniform vec3 uK[16]; uniform vec2 uN;\n"+
    "vec3 vp(vec2 q){ float z=lz(texture(uD,q).r); return vec3((q*2.-1.-uPo)*uPr.zw*z,-z); }\n"+
    "void main(){ float d=texture(uD,vQ).r; if(d>=.99999){ o=vec4(1.); return; }\n"+
    " vec3 P=vp(vQ), l=vp(vQ-vec2(uPx.x,0.)), r=vp(vQ+vec2(uPx.x,0.)), b=vp(vQ-vec2(0.,uPx.y)), t=vp(vQ+vec2(0.,uPx.y));\n"+
    " vec3 dx=abs(r.z-P.z)<abs(P.z-l.z)?r-P:P-l, dy=abs(t.z-P.z)<abs(P.z-b.z)?t-P:P-b, N=normalize(cross(dx,dy));\n"+
    " float a=fract(52.9829189*fract(dot(gl_FragCoord.xy,vec2(.06711056,.00583715))))*6.2832; vec3 rv=vec3(cos(a),sin(a),0.), T=normalize(rv-N*dot(rv,N)), B=cross(N,T);\n"+
    " float R=uN.y*(1.+min(-P.z/uN.y,60.)*.011), occ=0., gb=.02*R+.01+2.*max(abs(dx.z),abs(dy.z));\n"+     /* slope-scaled: a wall seen edge-on changes depth fast from texel to texel */
    " for(int i=0;i<16;i++){ if(float(i)>=uN.x) break; vec3 s=P+(T*uK[i].x+B*uK[i].y+N*uK[i].z)*R; vec2 q=((s.xy/(-s.z))/uPr.zw+uPo)*.5+.5;\n"+
    "   if(q.x<0.||q.y<0.||q.x>1.||q.y>1.) continue; float sz=-lz(texture(uD,q).r); occ+=step(s.z+gb,sz)*smoothstep(0.,1.,R/abs(P.z-sz)); }\n"+
    " o=vec4(1.-occ/uN.x*(1.-smoothstep(uN.y*60.,uN.y*160.,-P.z)),0.,0.,1.); }",
  blur:H+"uniform sampler2D uA; uniform sampler2D uD;\n"+
    "void main(){ float c=lz(texture(uD,vQ).r), zl=lz(texture(uD,vQ-uPx).r), zr=lz(texture(uD,vQ+uPx).r), g=abs(zr-c)<abs(c-zl)?zr-c:c-zl, s=0., w=0.;\n"+     /* the depth a plane through here would have: a wall seen edge-on still blurs along itself (else the noise streaks) */
    " for(int i=-4;i<=4;i++){ vec2 q=vQ+uPx*float(i); float z=lz(texture(uD,q).r), k=exp(-float(i*i)*.1)*max(0.,1.-abs(z-c-g*float(i))/(c*.02+.03)); s+=texture(uA,q).r*k; w+=k; }\n"+
    " o=vec4(w>1e-4?s/w:1.,0.,0.,1.); }",
  bright:H+"uniform sampler2D uC; uniform float uTh;\n"+
    "void main(){ vec3 c=texture(uC,vQ).rgb; float m=max(c.r,max(c.g,c.b)); o=vec4(c*smoothstep(uTh,uTh+.18,m),1.); }",
  down:H+"uniform sampler2D uC;\n"+
    "void main(){ vec2 h=uPx*.5; o=vec4((texture(uC,vQ).rgb*4.+texture(uC,vQ-h).rgb+texture(uC,vQ+h).rgb+texture(uC,vQ+vec2(h.x,-h.y)).rgb+texture(uC,vQ-vec2(h.x,-h.y)).rgb)/8.,1.); }",
  up:H+"uniform sampler2D uC;\n"+
    "void main(){ vec2 h=uPx*.5; vec3 s=texture(uC,vQ+vec2(-h.x*2.,0.)).rgb+texture(uC,vQ+vec2(0.,h.y*2.)).rgb+texture(uC,vQ+vec2(h.x*2.,0.)).rgb+texture(uC,vQ+vec2(0.,-h.y*2.)).rgb\n"+
    " +2.*(texture(uC,vQ+vec2(-h.x,h.y)).rgb+texture(uC,vQ+vec2(h.x,h.y)).rgb+texture(uC,vQ+vec2(h.x,-h.y)).rgb+texture(uC,vQ+vec2(-h.x,-h.y)).rgb); o=vec4(s/12.,1.); }",
  comp:H+"uniform sampler2D uC; uniform sampler2D uAO; uniform sampler2D uB; uniform vec4 uK;\n"+
    "void main(){ vec3 c=texture(uC,vQ).rgb; if(uK.z>.5) c*=mix(1.,texture(uAO,vQ).r,uK.x); if(uK.w>.5) c+=texture(uB,vQ).rgb*uK.y; o=vec4(c,1.); }"
};
function prog(gl,fs){ var sh=function(t,s){ var x=gl.createShader(t); gl.shaderSource(x,s); gl.compileShader(x); if(!gl.getShaderParameter(x,gl.COMPILE_STATUS)) throw new Error('fxg shader: '+gl.getShaderInfoLog(x)); return x; };
  var p=gl.createProgram(); gl.attachShader(p,sh(gl.VERTEX_SHADER,VS)); gl.attachShader(p,sh(gl.FRAGMENT_SHADER,fs)); gl.bindAttribLocation(p,0,'aQ'); gl.linkProgram(p);
  if(!gl.getProgramParameter(p,gl.LINK_STATUS)) throw new Error('fxg link: '+gl.getProgramInfoLog(p)); var u={}, n=gl.getProgramParameter(p,gl.ACTIVE_UNIFORMS);
  for(var i=0;i<n;i++){ var inf=gl.getActiveUniform(p,i); u[inf.name.replace(/\[0\]$/,'')]=gl.getUniformLocation(p,inf.name); } return {p:p, u:u}; }
function tex(gl,w,h,fmt){ var t=gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D,t);
  if(fmt==='d') gl.texImage2D(gl.TEXTURE_2D,0,gl.DEPTH_COMPONENT24,w,h,0,gl.DEPTH_COMPONENT,gl.UNSIGNED_INT,null); else gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA8,w,h,0,gl.RGBA,gl.UNSIGNED_BYTE,null);
  var f=fmt==='d'?gl.NEAREST:gl.LINEAR; gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,f); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,f);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE); return t; }
function fbo(gl,c,d){ var f=gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER,f); if(c) gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_2D,c,0);
  if(d) gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.DEPTH_ATTACHMENT,gl.TEXTURE_2D,d,0); var ok=gl.checkFramebufferStatus(gl.FRAMEBUFFER)===gl.FRAMEBUFFER_COMPLETE; gl.bindFramebuffer(gl.FRAMEBUFFER,null); return ok?f:null; }
function kernel(){ var k=[], s=7; function r(){ s=(s*16807)%2147483647; return s/2147483647; }
  for(var i=0;i<16;i++){ var a=r()*6.2832, z=.15+.85*r(), q=Math.sqrt(1-z*z), l=.12+.88*Math.pow((i+.5)/16,2); k.push(Math.cos(a)*q*l,Math.sin(a)*q*l,z*l); } return new Float32Array(k); }
function Post(gl){ this.gl=gl; this.ok=true; this.w=0; this.h=0; this.o={ao:0, aoK:.6, aoR:.55, bloom:0, bloomK:.05, th:.9};      /* bloomK: the up chain sums four levels, so ~4x the bright pass reaches the composite */ this.first=1; this.t=[]; this.f=[];
  try{ this.pr={}; for(var k in FS) this.pr[k]=prog(gl,FS[k]); }catch(e){ X.err=String(e.message||e); this.ok=false; }
  this.q=gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER,this.q); gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW); this.K=kernel(); }
Post.prototype.free=function(){ var gl=this.gl; this.t.forEach(function(t){ gl.deleteTexture(t); }); this.f.forEach(function(f){ gl.deleteFramebuffer(f); }); this.t=[]; this.f=[]; this.w=this.h=0; };
Post.prototype.size=function(w,h){ if(this.w===w&&this.h===h) return this.ok; this.free(); var gl=this.gl, P=this, mk=function(W,H,fm){ var t=tex(gl,W,H,fm); P.t.push(t); return t; };
  this.w=w; this.h=h; this.c=mk(w,h); this.d=mk(w,h,'d'); this.cf=fbo(gl,this.c,this.d); if(!this.cf){ this.ok=false; return false; } this.f.push(this.cf);
  var hw=Math.max(1,w>>1), hh=Math.max(1,h>>1); this.hw=hw; this.hh=hh; this.a0=mk(hw,hh); this.a1=mk(hw,hh); this.af0=fbo(gl,this.a0); this.af1=fbo(gl,this.a1); this.f.push(this.af0,this.af1);
  this.bl=[]; for(var i=1;i<=4;i++){ var W=Math.max(1,w>>i), Hh=Math.max(1,h>>i), t=mk(W,Hh), f=fbo(gl,t); this.f.push(f); this.bl.push({t:t, f:f, w:W, h:Hh}); }
  if(!this.af0||!this.af1||this.bl.some(function(b){ return !b.f; })){ this.ok=false; return false; } return true; };
Post.prototype.pass=function(name,fb,w,h,bind){ var gl=this.gl, p=this.pr[name]; gl.bindFramebuffer(gl.FRAMEBUFFER,fb); gl.viewport(0,0,w,h); gl.useProgram(p.p); bind(p.u,gl);
  gl.bindBuffer(gl.ARRAY_BUFFER,this.q); gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0,2,gl.FLOAT,false,8,0); for(var a=1;a<8;a++) gl.disableVertexAttribArray(a); gl.drawArrays(gl.TRIANGLES,0,6); };
function bindT(gl,unit,t,loc){ gl.activeTexture(gl.TEXTURE0+unit); gl.bindTexture(gl.TEXTURE_2D,t); gl.uniform1i(loc,unit); }
/* src: the multisampled framebuffer the frame was drawn in; cam: {near, far, tx, ty} (tangents of the half fields of view) */
Post.prototype.end=function(src,w,h,cam){ var gl=this.gl, o=this.o, P=this; if(!this.ok||!this.size(w,h)) return false;
  if(this.first) while(gl.getError()){}
  gl.disable(gl.DEPTH_TEST); gl.disable(gl.CULL_FACE); gl.disable(gl.BLEND); gl.depthMask(false);
  gl.bindFramebuffer(gl.READ_FRAMEBUFFER,src); gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,this.cf); gl.blitFramebuffer(0,0,w,h,0,0,w,h,gl.COLOR_BUFFER_BIT|(o.ao?gl.DEPTH_BUFFER_BIT:0),gl.NEAREST);
  gl.bindFramebuffer(gl.READ_FRAMEBUFFER,null); gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,null);
  var pr=[cam.near,cam.far,cam.tx,cam.ty], po=[cam.ox||0,cam.oy||0];
  if(o.ao){ this.pass('ao',this.af0,this.hw,this.hh,function(u){ bindT(gl,0,P.d,u.uD); gl.uniform4fv(u.uPr,pr); gl.uniform2fv(u.uPo,po); gl.uniform2fv(u.uPx,[1/w,1/h]); gl.uniform3fv(u.uK,P.K); gl.uniform2fv(u.uN,[o.ao,o.aoR]); });
    this.pass('blur',this.af1,this.hw,this.hh,function(u){ bindT(gl,0,P.a0,u.uA); bindT(gl,1,P.d,u.uD); gl.uniform4fv(u.uPr,pr); gl.uniform2fv(u.uPx,[1/P.hw,0]); });
    this.pass('blur',this.af0,this.hw,this.hh,function(u){ bindT(gl,0,P.a1,u.uA); bindT(gl,1,P.d,u.uD); gl.uniform4fv(u.uPr,pr); gl.uniform2fv(u.uPx,[0,1/P.hh]); }); }
  if(o.bloom){ var B=this.bl; this.pass('bright',B[0].f,B[0].w,B[0].h,function(u){ bindT(gl,0,P.c,u.uC); gl.uniform1f(u.uTh,o.th); });
    for(var i=1;i<B.length;i++){ (function(s,d){ P.pass('down',d.f,d.w,d.h,function(u){ bindT(gl,0,s.t,u.uC); gl.uniform2fv(u.uPx,[1/s.w,1/s.h]); }); })(B[i-1],B[i]); }
    gl.enable(gl.BLEND); gl.blendFunc(gl.ONE,gl.ONE);
    for(var j=B.length-1;j>0;j--){ (function(s,d){ P.pass('up',d.f,d.w,d.h,function(u){ bindT(gl,0,s.t,u.uC); gl.uniform2fv(u.uPx,[1/s.w,1/s.h]); }); })(B[j],B[j-1]); }
    gl.disable(gl.BLEND); }
  this.pass('comp',null,w,h,function(u){ bindT(gl,0,P.c,u.uC); bindT(gl,1,P.a0,u.uAO); bindT(gl,2,P.bl[0].t,u.uB); gl.uniform4fv(u.uK,[o.aoK,o.bloomK,o.ao?1:0,o.bloom?1:0]); });
  gl.activeTexture(gl.TEXTURE0); gl.depthMask(true);
  if(this.first){ this.first=0; var e=gl.getError(); if(e){ X.err='post: gl error '+e; this.ok=false; return false; } }
  return true; };
X.post=function(gl){ if(typeof WebGL2RenderingContext==='undefined'||!(gl instanceof WebGL2RenderingContext)) return null; var p=new Post(gl); return p.ok?p:null; };
return X; })();
"""


def gfx_js() -> str:
    return GFX_JS.replace("__FXG_ASSETS__", json.dumps(_manifest(), separators=(",", ":"))).replace("__IBL_GLSL__", json.dumps(IBL_GLSL))
