"""Part GL of the first-person ride: the WebGL renderer for the city (owner: the gl agent).

The overlay gets a second canvas, `.pr-gl`, UNDER the transparent 2D canvas `.pr-cv`.  drawCity() (palace_ride_d.py) draws the city into it when WebGL works
(sky dome with sun/moon, clouds and stars; ground chunks - asphalt with lane lines and crosswalks, kerbs and sidewalks, grass, water; the buildings extruded from
W.solids with real roofs, cornices and a facade shader by material and height; W.meshes (landmarks, scenery); W.movers instanced; the ride's own way: track, road,
bridges, viaducts, tunnel mouths) and falls back to the old Canvas-2D painter when it does not (no WebGL, context creation failed, context lost).

One WebGL1 program draws every surface (palace_ride_gl_shaders.py): the material is picked per vertex (palace_ride_mesh.py MAT + a few GL-only ids), so the facades
are procedural (brick bond, window grid per ~3.4 m floor, mullions, storefronts, cornice, night windows from the per-building tint, sky reflection in glass).

Static geometry is merged per 300-unit cell into one VBO (ground + buildings), built a few milliseconds a frame, nearest first, and cached by the cell's contents so a
world that is re-gathered (roaming) reuses what it already built; bounding spheres cull what is out of view.

Hooks other parts may use
  GLX.on / glOk()      true while the GL view is in use (false: no WebGL, context lost - the 2D painter then draws the city and sceneryDraw/lmSolids stay in use)
  drawCity(..., way)   `way` is called with the GL api `g` (g.way(M) = the ride model's static way mesh); with no argument it paints the 2D ground (fallback)
  setCam(..., hz, pitch) / C.pitch / C.foc   the camera: pitch in radians (up positive), C.foc = focal length in px (the field of view); C.shk={x,y,r,s} = screen shake
  W.meshes=[{a:Float32Array(10-float mesh format), id}]   static models, uploaded once (reused by id+size when a world is re-gathered); `lm` stand-in solids are skipped when a
                                                          mesh of the same id exists; drawn without face culling, normals flipped toward the eye
  W.movers=[{a, x, y, z, yaw, tint?}]   instanced by `a` (ANGLE_instanced_arrays, else one draw each); sceneryUpdate(W,tm,C) runs every GL frame
  GLX.crosswalks=false  turn the grid crosswalks off (when the scenery part draws its own);   GLX.newWorld()  mark a new world (the next frame builds its nearest cells whole)
  window._palRideNoGL / _palRideNoShadow = true  before the overlay is made: force the 2D fallback / no shadows
QA: GLX.look(x,y,z,yawDeg,pitchDeg,cellsRadius,dark) draws a free camera over a world gathered round (x,y); GLX.lookRide(...) over the current ride; GLX.tAtS(s) time at path position s
"""
import json

from .palace_ride_gl_shaders import FS_SHADOW, FS_SKY, FS_WORLD, SH_COMMON, VS_SHADOW, VS_SKY, VS_WORLD

_GLS = ("var GLS={vsw:" + json.dumps(VS_WORLD) + ", fsw:" + json.dumps(SH_COMMON + FS_WORLD) + ", vsh:" + json.dumps(VS_SHADOW) + ", fsh:" + json.dumps(FS_SHADOW) + ", vss:" + json.dumps(VS_SKY) + ", fss:" + json.dumps(SH_COMMON + FS_SKY) + "};\n")

CSS_GL = r"""
  #pal-ride .pr-gl{position:absolute;left:0;top:0;width:100%;height:100%;display:block;}
  #pal-ride.pr-glon .pr-cv{background:transparent;}
"""

_JS_GL_MAIN = r"""
/* ── WebGL city renderer: infrastructure ── */
var GLX={uid:0, ident:new Float32Array([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]), on:false, gl:null, cv:null, lost:false, gen:0, err:'', renderer:'', ext:null, prog:null, sky:null, noise:null, quad:null, cache:{}, prev:{}, prevM:{}, nCache:0, mc:null, queue:[], wayq:[], frame:0,
  st:{draws:0, tris:0, built:0, pending:0, ms:0, chunks:0}, ready:false, fresh:true, inst:null, instBuf:null, ibuf:null};
var GL_NEAR=.5, GL_FAR=2000, GL_MAXCACHE=260;
function glAttach(ov){
  var cv=document.createElement('canvas'); cv.className='pr-gl'; cv.setAttribute('aria-hidden','true'); var c2=ov.querySelector('.pr-cv'); ov.insertBefore(cv,c2); GLX.cv=cv;
  cv.addEventListener('webglcontextlost', function(e){ e.preventDefault(); GLX.lost=true; GLX.on=false; ov.classList.remove('pr-glon'); GLX.err='context lost'; });
  cv.addEventListener('webglcontextrestored', function(){ glSetup(true); });
  glSetup(false); }
function glSetup(restore){
  var cv=GLX.cv, gl=null;
  if(!cv) return false; if(window._palRideNoGL){ GLX.err='disabled'; return glFail(); }
  var opt={alpha:false, antialias:true, depth:true, stencil:false, powerPreference:'high-performance', preserveDrawingBuffer:false};
  try{ gl=cv.getContext('webgl',opt)||cv.getContext('experimental-webgl',opt); }catch(x){ gl=null; }
  if(!gl || gl.isContextLost()){ GLX.err='no webgl'; return glFail(true); }
  GLX.gl=gl; GLX.gen++; GLX.cache={}; GLX.prev={}; GLX.prevM={}; GLX.nCache=0; GLX.mc=(typeof WeakMap!=='undefined')?new WeakMap():null; GLX.queue=[]; GLX.wayq=[];
  var fp=gl.getShaderPrecisionFormat&&gl.getShaderPrecisionFormat(gl.FRAGMENT_SHADER,gl.HIGH_FLOAT); if(!fp || !fp.precision){ GLX.err='no highp fragment precision'; return glFail(true); }
  if(gl.getParameter(gl.MAX_VERTEX_ATTRIBS)<8){ GLX.err='too few vertex attributes'; return glFail(true); }
  var dbg=gl.getExtension('WEBGL_debug_renderer_info'); GLX.renderer=dbg?String(gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL)):'';
  GLX.inst=gl.getExtension('ANGLE_instanced_arrays');
  try{
    GLX.prog=glProgram(gl, GLS.vsw, GLS.fsw, ['aP','aN','aUV','aMT','aDC','aHA','aI','aT2'], ['uVP','uEye','uInst','uSun','uSunCol','uSkyA','uGndA','uZen','uHor','uFog','uFogD','uNight','uTime','uPix','uExp','uNz','uLP','uLQ','uNOff','uSh','uSq','uShP','uShQ','uPal','uAtl','uAtlS','uLamp','uLampC','uIn']);
    GLX.shp=glProgram(gl, GLS.vsh, GLS.fsh, ['aP'], ['uLP']);
    GLX.sky=glProgram(gl, GLS.vss, GLS.fss, ['aQ'], ['uF','uR','uU','uPrj','uUn','uUt','uGnd','uEye','uSun','uSunCol','uZen','uHor','uFog','uFogD','uNight','uTime','uExp','uNz']);
  }catch(x){ GLX.err=String(x&&x.message||x); if(window.console) console.warn('ride GL', GLX.err); return glFail(true); }
  /* the noise texture: random bytes, filtered and mip-mapped, read for value noise in the shaders */
  var N=128, px=new Uint8Array(N*N*4), i, s=12345;
  for(i=0;i<px.length;i++){ s=(Math.imul(s,1664525)+1013904223)|0; px[i]=(s>>>16)&255; }
  var tx=gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D,tx); gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,N,N,0,gl.RGBA,gl.UNSIGNED_BYTE,px);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.REPEAT); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.REPEAT);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR_MIPMAP_LINEAR); gl.generateMipmap(gl.TEXTURE_2D); GLX.noise=tx;
  var q=gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER,q); gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1, 3,-1, -1,3]),gl.STATIC_DRAW); GLX.quad=q;
  glShadowSetup(gl);
  GLX.palTex=glTex1(gl,new Uint8Array([128,128,128,255]),1,1,false); GLX.atlTex=glTex1(gl,new Uint8Array([255,255,255,255]),1,1,false); GLX.palRef=null; GLX.palN=-1; GLX.atlRef=null; GLX.lampBuf=new Float32Array(48);
  GLX.ibuf=gl.createBuffer(); GLX.instBuf=new Float32Array(6*600);
  gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL); gl.enable(gl.CULL_FACE); gl.cullFace(gl.BACK); gl.frontFace(gl.CCW); gl.clearColor(.5,.55,.6,1);
  GLX.on=true; GLX.lost=false; GLX.ready=true; GLX.err=''; GLX.fresh=true; if(GLX.cv&&GLX.cv.parentNode) GLX.cv.parentNode.classList.add('pr-glon');
  return true; }
function glTex1(gl,px,w,h,mip){ var tx=gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D,tx); gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,w,h,0,gl.RGBA,gl.UNSIGNED_BYTE,px);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,mip?gl.LINEAR:gl.NEAREST); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,mip?gl.LINEAR:gl.NEAREST); return tx; }
function glFail(drop){ GLX.on=false; GLX.ready=false; var cv=GLX.cv; if(cv&&cv.parentNode){ cv.parentNode.classList.remove('pr-glon'); if(drop||!GLX.gl) { cv.parentNode.removeChild(cv); } } return false; }
function glProgram(gl, vs, fs, attrs, unis){
  function mk(t,src){ var s=gl.createShader(t); gl.shaderSource(s,src); gl.compileShader(s); if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)){ var l=gl.getShaderInfoLog(s); gl.deleteShader(s); throw new Error((t===gl.VERTEX_SHADER?'vertex: ':'fragment: ')+l); } return s; }
  var p=gl.createProgram(); gl.attachShader(p,mk(gl.VERTEX_SHADER,vs)); gl.attachShader(p,mk(gl.FRAGMENT_SHADER,fs)); gl.linkProgram(p);
  if(!gl.getProgramParameter(p,gl.LINK_STATUS)) throw new Error('link: '+gl.getProgramInfoLog(p));
  var o={p:p,a:{},u:{}}; attrs.forEach(function(a){ o.a[a]=gl.getAttribLocation(p,a); }); unis.forEach(function(u){ o.u[u]=gl.getUniformLocation(p,u); }); return o; }
function glOk(){ return GLX.on && GLX.gl && !GLX.lost; }
function glSize(w,h){ var cv=GLX.cv; if(cv && (cv.width!==w || cv.height!==h)){ cv.width=w; cv.height=h; } }

/* ── mesh builder for the GL vertex layout (15 floats): x y z nx ny nz u v pk tint dr dg db H L ── */
function GBuf(){ this.a=new Float32Array(1<<15); this.n=0; this.x0=1e9; this.x1=-1e9; this.y0=1e9; this.y1=-1e9; this.z0=1e9; this.z1=-1e9; }
function gGrow(b){ var na=new Float32Array(b.a.length*2); na.set(b.a); b.a=na; }
var _gdr=1, _gdg=1, _gdb=1, _gH=0, _gL=0;
function gv(b,x,y,z,nx,ny,nz,u,v,pk,t){ var n=b.n; if(n+15>b.a.length) gGrow(b); var a=b.a; a[n]=x; a[n+1]=y; a[n+2]=z; a[n+3]=nx; a[n+4]=ny; a[n+5]=nz; a[n+6]=u; a[n+7]=v; a[n+8]=pk; a[n+9]=t; a[n+10]=_gdr; a[n+11]=_gdg; a[n+12]=_gdb; a[n+13]=_gH; a[n+14]=_gL; b.n=n+15;
  if(x<b.x0) b.x0=x; if(x>b.x1) b.x1=x; if(y<b.y0) b.y0=y; if(y>b.y1) b.y1=y; if(z<b.z0) b.z0=z; if(z>b.z1) b.z1=z; }
/* a wall A->B of a ring that runs clockwise (MB.ringOut): outward normal on the left; winding as the shared builder (clockwise seen from outside) */
function gwall(b,ax,ay,bx,by,z0,z1,nx,ny,zb,pk,t){
  var L=Math.hypot(bx-ax,by-ay)/UM, va=(z0-zb)/UM, vb=(z1-zb)/UM; _gL=L;
  gv(b,ax,ay,z0,nx,ny,0,0,va,pk,t); gv(b,bx,by,z0,nx,ny,0,L,va,pk,t); gv(b,bx,by,z1,nx,ny,0,L,vb,pk,t);
  gv(b,ax,ay,z0,nx,ny,0,0,va,pk,t); gv(b,bx,by,z1,nx,ny,0,L,vb,pk,t); gv(b,ax,ay,z1,nx,ny,0,0,vb,pk,t); }
/* the part t0..t1 (0..1) of a wall A->B, uv as on the whole wall (u runs from t0*L to t1*L, L stays the whole wall's length) */
function gwallP(b,ax,ay,bx,by,z0,z1,nx,ny,zb,pk,t,t0,t1){
  var L=Math.hypot(bx-ax,by-ay)/UM, va=(z0-zb)/UM, vb=(z1-zb)/UM, dx=bx-ax, dy=by-ay, px=ax+dx*t0, py=ay+dy*t0, qx=ax+dx*t1, qy=ay+dy*t1, u0=L*t0, u1=L*t1; _gL=L;
  gv(b,px,py,z0,nx,ny,0,u0,va,pk,t); gv(b,qx,qy,z0,nx,ny,0,u1,va,pk,t); gv(b,qx,qy,z1,nx,ny,0,u1,vb,pk,t);
  gv(b,px,py,z0,nx,ny,0,u0,va,pk,t); gv(b,qx,qy,z1,nx,ny,0,u1,vb,pk,t); gv(b,px,py,z1,nx,ny,0,u0,vb,pk,t); }
/* the stretches of the wall A->B that are NOT hidden by `hide` ([x0,y0,x1,y1, ...] lying on this wall's line): null when none is (draw it whole), else [t0,t1, t0,t1, ...] in 0..1 (empty: all of it is hidden) */
function glVis(hide,ax,ay,bx,by){
  var l=Math.hypot(bx-ax,by-ay); if(l<1e-6) return null; var ux=(bx-ax)/l, uy=(by-ay)/l, cut=[], k;
  for(k=0;k<hide.length;k+=4){ var p0x=hide[k], p0y=hide[k+1], p1x=hide[k+2], p1y=hide[k+3];
    if(Math.abs((p0x-ax)*uy-(p0y-ay)*ux)>.08||Math.abs((p1x-ax)*uy-(p1y-ay)*ux)>.08) continue;
    var t0=((p0x-ax)*ux+(p0y-ay)*uy)/l, t1=((p1x-ax)*ux+(p1y-ay)*uy)/l; if(t0>t1){ var q=t0; t0=t1; t1=q; } t0=Math.max(0,t0); t1=Math.min(1,t1); if(t1-t0>.002) cut.push([t0,t1]); }
  if(!cut.length) return null;
  cut.sort(function(p,q){ return p[0]-q[0]; }); var out=[], at=0;
  for(k=0;k<cut.length;k++){ if(cut[k][0]>at+.002) out.push(at,cut[k][0]); if(cut[k][1]>at) at=cut[k][1]; }
  if(at<.998) out.push(at,1); return out; }
/* any triangle: the winding is fixed so that it faces along n (shared convention: the right-hand cross points against the normal) */
function gtri(b,A,B,C,nx,ny,nz,ua,va,ub,vb,uc,vc,pk,t){
  var cx=(B[1]-A[1])*(C[2]-A[2])-(B[2]-A[2])*(C[1]-A[1]), cy=(B[2]-A[2])*(C[0]-A[0])-(B[0]-A[0])*(C[2]-A[2]), cz=(B[0]-A[0])*(C[1]-A[1])-(B[1]-A[1])*(C[0]-A[0]);
  if(cx*nx+cy*ny+cz*nz>0){ var q=B; B=C; C=q; var u=ub, v=vb; ub=uc; vb=vc; uc=u; vc=v; }
  gv(b,A[0],A[1],A[2],nx,ny,nz,ua,va,pk,t); gv(b,B[0],B[1],B[2],nx,ny,nz,ub,vb,pk,t); gv(b,C[0],C[1],C[2],nx,ny,nz,uc,vc,pk,t); }
/* a quad A B C D (in order round it), uv u0..u1 along A->B, v0..v1 along A->D; normal given or from the corners */
function gquad(b,A,B,C,D,nx,ny,nz,u0,u1,v0,v1,pk,t){
  if(nx==null){ var ux=B[0]-A[0], uy=B[1]-A[1], uz=B[2]-A[2], vx=D[0]-A[0], vy=D[1]-A[1], vz=D[2]-A[2]; nx=uy*vz-uz*vy; ny=uz*vx-ux*vz; nz=ux*vy-uy*vx; var l=Math.sqrt(nx*nx+ny*ny+nz*nz)||1; nx/=l; ny/=l; nz/=l; }
  gtri(b,A,B,C,nx,ny,nz,u0,v0,u1,v0,u1,v1,pk,t); gtri(b,A,C,D,nx,ny,nz,u0,v0,u1,v1,u0,v1,pk,t); }
/* a flat polygon (ring x,y,x,y..) at height z facing up or down, uv = world metres */
function gflat(b,ring,z,pk,t,up){
  var tr=MB.tris(ring), s=up?1:-1; _gL=0;
  for(var i=0;i<tr.length;i+=3){ var a=tr[i], c=tr[i+1], d=tr[i+2], ax=ring[2*a], ay=ring[2*a+1], bx=ring[2*c], by=ring[2*c+1], cx=ring[2*d], cy=ring[2*d+1];
    var cr=(bx-ax)*(cy-ay)-(by-ay)*(cx-ax); if((cr<0)!==up){ var qx=bx, qy=by; bx=cx; by=cy; cx=qx; cy=qy; }
    gv(b,ax,ay,z,0,0,s,ax/UM,ay/UM,pk,t); gv(b,bx,by,z,0,0,s,bx/UM,by/UM,pk,t); gv(b,cx,cy,z,0,0,s,cx/UM,cy/UM,pk,t); } }
/* a box x0..x1, y0..y1, z0..z1 turned by yaw about (cx,cy) */
function gbox(b,cx,cy,hx,hy,z0,z1,yaw,pk,t,roof){
  var c=Math.cos(yaw), s=Math.sin(yaw), px=[], i, q=[[-hx,-hy],[hx,-hy],[hx,hy],[-hx,hy]];
  for(i=0;i<4;i++) px.push([cx+q[i][0]*c-q[i][1]*s, cy+q[i][0]*s+q[i][1]*c]);
  for(i=0;i<4;i++){ var A=px[i], B=px[(i+1)%4], dx=B[0]-A[0], dy=B[1]-A[1], l=Math.hypot(dx,dy)||1, nx=dy/l, ny=-dx/l;       /* ring runs counter-clockwise: outward is on the right */
    var cc=(B[0]-A[0])*(px[(i+2)%4][1]-A[1])-(B[1]-A[1])*(px[(i+2)%4][0]-A[0]); if(cc>0){ /* ccw in math */ }
    gquad(b,[A[0],A[1],z0],[B[0],B[1],z0],[B[0],B[1],z1],[A[0],A[1],z1],nx,ny,0,0,l/UM,0,(z1-z0)/UM,pk,t); }
  if(roof!==false) gflat(b,[px[0][0],px[0][1],px[1][0],px[1][1],px[2][0],px[2][1],px[3][0],px[3][1]],z1,pk,t,true); }

/* ear-clipping triangulation (replaces MB.tris, which is cubic): indices of triangles of a simple ring */
function glTris(r){
  var n=r.length/2, out=[], i; if(n<3) return out; if(n===3) return [0,1,2];
  var nx=new Int32Array(n), pv=new Int32Array(n), ar=0;
  for(i=0;i<n;i++){ var j=(i+1)%n; ar+=r[2*i]*r[2*j+1]-r[2*j]*r[2*i+1]; nx[i]=j; pv[i]=(i+n-1)%n; } var sg=ar>=0?1:-1;
  function cr(a,b,c){ return ((r[2*b]-r[2*a])*(r[2*c+1]-r[2*a+1])-(r[2*b+1]-r[2*a+1])*(r[2*c]-r[2*a]))*sg; }
  var left=n, cur=0, fails=0, guard=0, lim=n*n+200;
  while(left>3 && guard++<lim){
    var p=pv[cur], q=nx[cur], c=cr(p,cur,q), ear=false;
    if(c>1e-9){ ear=true; var ax=r[2*p], ay=r[2*p+1], bx=r[2*cur], by=r[2*cur+1], cx=r[2*q], cy=r[2*q+1], k=nx[q];
      while(k!==p){ var px=r[2*k], py=r[2*k+1];
        if(!((px===ax&&py===ay)||(px===bx&&py===by)||(px===cx&&py===cy))){ if(cr(p,cur,k)>=0 && cr(cur,q,k)>=0 && cr(q,p,k)>=0){ ear=false; break; } }
        k=nx[k]; } }
    if(ear){ out.push(p,cur,q); nx[p]=q; pv[q]=p; left--; cur=q; fails=0; }
    else { cur=nx[cur]; fails++; if(fails>left){ var pp=pv[cur], qq=nx[cur]; if(cr(pp,cur,qq)>1e-9) out.push(pp,cur,qq); nx[pp]=qq; pv[qq]=pp; left--; cur=qq; fails=0; } } }
  if(left===3){ var a0=cur, a1=nx[a0], a2=nx[a1]; if(cr(a0,a1,a2)>1e-9) out.push(a0,a1,a2); }
  return out; }
MB.tris=glTris;

/* ── a mesh from another part (the 10-float shared format) into a GL buffer; bounds from its vertices ── */
function glExpand(a){
  var nv=(a.length/10)|0, o=new Float32Array(nv*15), i, j, x0=1e9,x1=-1e9,y0=1e9,y1=-1e9,z0=1e9,z1=-1e9;
  for(i=0;i<nv;i++){ var s=i*10, d=i*15; for(j=0;j<10;j++) o[d+j]=a[s+j]; o[d+10]=1; o[d+11]=1; o[d+12]=1; o[d+13]=0; o[d+14]=0;
    var x=a[s], y=a[s+1], z=a[s+2]; if(x<x0)x0=x; if(x>x1)x1=x; if(y<y0)y0=y; if(y>y1)y1=y; if(z<z0)z0=z; if(z>z1)z1=z; }
  return {a:o, n:nv, x0:x0,x1:x1,y0:y0,y1:y1,z0:z0,z1:z1}; }
/* a scenery mesh (10-float format) appended to a cell chunk; flat paint laid on the ground gets the decal depth bias */
function glAppend(b,a){
  glDC(null); _gH=0; _gL=0; var i, n=a.length, sm=null;
  /* foliage and trunks are shaded smooth: the normals of vertices at one place are averaged (the scenery part writes flat faces) */
  for(i=0;i+9<n;i+=10){ var mt=a[i+8]; if(mt===18||mt===17){ if(!sm) sm=new Map(); var k=(Math.round(a[i]*6)*73856093)^(Math.round(a[i+1]*6)*19349663)^(Math.round(a[i+2]*6)*83492791)^(mt*7919), e=sm.get(k);
      if(!e){ e=[0,0,0]; sm.set(k,e); } e[0]+=a[i+3]; e[1]+=a[i+4]; e[2]+=a[i+5]; } }
  for(i=0;i+9<n;i+=10){ var z=a[i+2], nx=a[i+3], ny=a[i+4], nz=a[i+5], mt2=a[i+8];
    if(sm && (mt2===18||mt2===17)){ var k2=(Math.round(a[i]*6)*73856093)^(Math.round(a[i+1]*6)*19349663)^(Math.round(a[i+2]*6)*83492791)^(mt2*7919), q=sm.get(k2), l=Math.sqrt(q[0]*q[0]+q[1]*q[1]+q[2]*q[2]); if(l>1e-4){ nx=q[0]/l; ny=q[1]/l; nz=q[2]/l; } }
    var bias=(nz>.9&&z<.45)?2:0; gv(b,a[i],a[i+1],z,nx,ny,nz,a[i+6],a[i+7],mt2+64*bias,a[i+9]); } }
function glUpload(b){
  var gl=GLX.gl; var buf=gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER,buf); var arr=b.a.length===b.n?b.a:b.a.subarray(0,b.n); gl.bufferData(gl.ARRAY_BUFFER,arr,gl.STATIC_DRAW);
  var n=b.n/15|0; var cx=(b.x0+b.x1)/2, cy=(b.y0+b.y1)/2, cz=(b.z0+b.z1)/2, r=Math.sqrt(Math.pow(b.x1-b.x0,2)+Math.pow(b.y1-b.y0,2)+Math.pow(b.z1-b.z0,2))/2;
  return {buf:buf, n:n, cx:cx, cy:cy, cz:cz, r:r, gen:GLX.gen, use:GLX.frame}; }
function glFree(o){ if(o && o.buf && GLX.gl && o.gen===GLX.gen){ try{ GLX.gl.deleteBuffer(o.buf); }catch(x){} } o.buf=null; }
"""

_JS_GL_BUILD = r"""
/* ── what the buildings, ground and way are made of ── */
var GZ_SIDE=.14, GZ_PARK=.1;
function glDC(col){ if(!col){ _gdr=_gdg=_gdb=1; return; } var m=(col[0]+col[1]+col[2])/3||1; _gdr=clamp(col[0]/m,.45,1.7); _gdg=clamp(col[1]/m,.45,1.7); _gdb=clamp(col[2]/m,.45,1.7); }
var GL_MATS={brick:1,brownstone:2,stone:2,tile:2,stucco:4,painted:4,plaster:4,concrete:4,cladding:4,metal:4,wood:4,glass:3};
function glStyle(s){
  var hm=(s.h-(s.z0||0))/UM, hh=hashXY(s.cx,s.cy), t=hashXY(s.cx*1.31+7,s.cy*.77+3), k=s.kind, st={mat:1, aux:0, t:t, roof:5, dc:s.col, hm:hm};
  if(k==='node'){ st.mat=3; st.aux=1; return st; }
  if(k==='plat'){ st.mat=47; st.roof=12; st.dc=null; return st; }
  if(k==='canopy'){ st.mat=6; st.roof=6; st.dc=null; return st; }
  if(k==='pole'){ st.mat=6; st.roof=6; st.dc=null; return st; }
  if(k==='sign'){ st.mat=22; st.roof=22; st.dc=s.col2?rgbOf(s.col2):null; if(st.dc) st.dc=[st.dc[0]*.7,st.dc[1]*.7,st.dc[2]*.7]; return st; }
  if(k==='lm'){ st.mat=hm>70?3:2; st.aux=0; return st; }
  /* the street data's material (palace_street_style.MATERIALS) -> the shader's facade: brick 1, stone 2, glass 3, concrete 4 (stucco, painted, plaster, cladding, metal, wood are pale/painted walls: 4, tinted by the real colour) */
  var mc=s.mat; if(mc && GL_MATS[mc]){ st.mat=GL_MATS[mc]; if(mc==='brownstone') st.dc=mixC(s.col||[160,120,96],[118,80,62],.55); else if(mc==='tile') st.dc=mixC(s.col||[190,170,150],[150,110,92],.35); return st; }
  if(hm<9) st.mat=1;
  else if(hm<28) st.mat=hh<.55?1:hh<.8?2:4;
  else if(hm<70) st.mat=hh<.28?2:hh<.62?4:3;
  else st.mat=hh<.82?3:4;
  return st; }
function glCenterOf(r){ var n=r.length/2, cx=0, cy=0, i; for(i=0;i<n;i++){ cx+=r[2*i]; cy+=r[2*i+1]; } return [cx/n,cy/n]; }
function glScaleRing(r,cx,cy,k){ var o=[]; for(var i=0;i<r.length;i+=2) o.push(cx+(r[i]-cx)*k, cy+(r[i+1]-cy)*k); return o; }
/* one building: walls with facade uv, a cornice on brick/stone/concrete, a flat roof, a stepped crown on towers */
function glSolid(b,s){
  if(s.nodraw) return;                                                     /* an outline its building:parts cover (palace_ride_street.py realDedupe) */
  var ring0=s.ring, n=ring0.length/2; if(n<3) return; var zb=s.z0||0, h=s.h+(s.roofDz||0); if(!(h>zb+.3)) return;     /* roofDz: the later of two roofs on one plane sits a little lower */
  if(n>90){ var kk=Math.ceil(n/90), q=[]; for(var ii=0;ii<n;ii+=kk) q.push(ring0[2*ii],ring0[2*ii+1]); ring0=q; n=q.length/2; }
  var r=MB.ringOut(ring0), st=glStyle(s), pk=st.mat+256*st.aux, T=st.t, hm=st.hm, i, ax, ay, bx, by, dx, dy, l;
  glDC(st.dc); _gH=hm;
  var cornice=(st.mat===1||st.mat===2||st.mat===4)&&hm>=5.5&&n<=30&&s.kind!=='plat'&&s.kind!=='canopy', top=r, co=null;
  if(cornice){ var off=.3, ch=.9*UM; co=[]; var nn=[]; for(i=0;i<n;i++){ var p=(i+n-1)%n, q2=(i+1)%n; var d1x=r[2*i]-r[2*p], d1y=r[2*i+1]-r[2*p+1], l1=Math.hypot(d1x,d1y)||1, d2x=r[2*q2]-r[2*i], d2y=r[2*q2+1]-r[2*i+1], l2=Math.hypot(d2x,d2y)||1;
      var n1x=-d1y/l1, n1y=d1x/l1, n2x=-d2y/l2, n2y=d2x/l2, dd=1+n1x*n2x+n1y*n2y, k=dd>.25?1/dd:4; co.push(r[2*i]+(n1x+n2x)*k*off, r[2*i+1]+(n1y+n2y)*k*off); }
    top=co; }
  var vis=null; if(s.hide){ vis=new Array(n); for(i=0;i<n;i++){ var j0=(i+1)%n; vis[i]=glVis(s.hide,r[2*i],r[2*i+1],r[2*j0],r[2*j0+1]); } }     /* the stretches of a wall that lie on a taller wall's plane are not drawn */
  for(i=0;i<n;i++){ var j=(i+1)%n; ax=r[2*i]; ay=r[2*i+1]; bx=r[2*j]; by=r[2*j+1]; dx=bx-ax; dy=by-ay; l=Math.hypot(dx,dy); if(l<.25) continue;
    var vi=vis?vis[i]:null; if(!vi) gwall(b,ax,ay,bx,by,zb,h,-dy/l,dx/l,zb,pk,T); else for(var qa=0;qa<vi.length;qa+=2) gwallP(b,ax,ay,bx,by,zb,h,-dy/l,dx/l,zb,pk,T,vi[qa],vi[qa+1]); }
  if(cornice){ var cz0=h-.9*UM; _gL=0;
    for(i=0;i<n;i++){ var j2=(i+1)%n; ax=co[2*i]; ay=co[2*i+1]; bx=co[2*j2]; by=co[2*j2+1]; dx=bx-ax; dy=by-ay; l=Math.hypot(dx,dy); if(l<.25) continue;
      var vc=vis?vis[i]:null; if(vc && !vc.length) continue;
      if(!vc) gwall(b,ax,ay,bx,by,cz0,h,-dy/l,dx/l,zb,pk,T); else for(var q2=0;q2<vc.length;q2+=2) gwallP(b,ax,ay,bx,by,cz0,h,-dy/l,dx/l,zb,pk,T,vc[q2],vc[q2+1]);
      var A=[r[2*i],r[2*i+1],cz0], B=[r[2*j2],r[2*j2+1],cz0], B2=[bx,by,cz0], A2=[ax,ay,cz0];
      gtri(b,A,B,B2,0,0,-1,A[0]/UM,A[1]/UM,B[0]/UM,B[1]/UM,B2[0]/UM,B2[1]/UM,pk,T); gtri(b,A,B2,A2,0,0,-1,A[0]/UM,A[1]/UM,B2[0]/UM,B2[1]/UM,A2[0]/UM,A2[1]/UM,pk,T); } }
  _gL=0; gflat(b,top,h,st.roof,T,true); if(hm>6) gflat(b,top,h-.03,47,T,false);                /* and its underside, so looking up from the street is not looking through the roof */
  /* a stepped crown on a glass tower, a thin mast on the tallest */
  if(st.mat===3 && hm>46 && n<=14 && s.kind!=='lm'){ var c=glCenterOf(r), tH=Math.min(hm*.07,16)*UM; var tier=glScaleRing(r,c[0],c[1],.8), zt=h;
    glDC(st.dc); _gH=tH/UM; var rr=MB.ringOut(tier), m=rr.length/2;
    for(i=0;i<m;i++){ var j3=(i+1)%m; ax=rr[2*i]; ay=rr[2*i+1]; bx=rr[2*j3]; by=rr[2*j3+1]; dx=bx-ax; dy=by-ay; l=Math.hypot(dx,dy); if(l<.25) continue; gwall(b,ax,ay,bx,by,zt,zt+tH,-dy/l,dx/l,zt,pk,T); }
    _gL=0; gflat(b,rr,zt+tH,st.roof,T,true); gflat(b,rr,zt+tH-.03,47,T,false);
    if(hm>110){ var t2=glScaleRing(r,c[0],c[1],.5), zt2=zt+tH, h2=Math.min(hm*.06,14)*UM, r2=MB.ringOut(t2), m2=r2.length/2; _gH=h2/UM;
      for(i=0;i<m2;i++){ var j4=(i+1)%m2; ax=r2[2*i]; ay=r2[2*i+1]; bx=r2[2*j4]; by=r2[2*j4+1]; dx=bx-ax; dy=by-ay; l=Math.hypot(dx,dy); if(l<.25) continue; gwall(b,ax,ay,bx,by,zt2,zt2+h2,-dy/l,dx/l,zt2,pk,T); }
      _gL=0; gflat(b,r2,zt2+h2,st.roof,T,true); gflat(b,r2,zt2+h2-.03,47,T,false);
      if(hm>180){ _gH=0; gbox(b,c[0],c[1],.5,.5,zt2+h2,zt2+h2+32*UM,0,6,T,true); } } }
  _gH=0;
  if(s.door) glDoor(b,s);
  if(s.shop) glShop(b,s); }

/* a shopfront on the street-facing wall of a storefront building (the street data's flag): a dark bulkhead, lit shop glass (material 25) in mullions, a fascia the name is painted on
   (palace_ride_g.py shopFront draws the lettering on the atlas), and an awning in a hue taken from the name. Metres, as glDoor. */
var AWN=[[.20,.34,.24],[.17,.22,.38],[.40,.14,.17],[.22,.23,.25],[.66,.62,.52],[.46,.24,.15],[.34,.42,.32]];      /* albedo: muted forest, navy, burgundy, charcoal, cream, rust, sage */
function glShop(b,s){
  var d=s.shop; if(!d) return; var nx=d.nx, ny=d.ny, tx=ny, ty=-nx, yaw=Math.atan2(ty,tx), K=UM, hw=Math.min(d.len/K/2-.35, 7.5); if(hw<1.4) return;
  glDC(null); _gH=0; _gL=0;
  function bx(a0,a1,d0,d1,z0,z1,pk,roof){ gbox(b, d.x+(tx*(a0+a1)+nx*(d0+d1))/2*K, d.y+(ty*(a0+a1)+ny*(d0+d1))/2*K, (a1-a0)/2*K, (d1-d0)/2*K, z0*K, z1*K, yaw, pk, 0, roof); }
  bx(-hw,hw,.02,.14,0,.5,15); bx(-hw,hw,.02,.07,.5,2.9,25);
  for(var a=-hw; a<=hw+.01; a+=Math.max(1.6,hw*2/Math.ceil(hw*2/2.6))) bx(a-.05,a+.05,.02,.14,.5,2.9,15);
  bx(-hw,hw,.02,.45,2.9,3.55,15);
  var col=AWN[Math.floor(d.hue*AWN.length)%AWN.length]; glDC(null); _gdr=col[0]; _gdg=col[1]; _gdb=col[2];
  var pt=function(a,dd,z){ return [d.x+(tx*a+nx*dd)*K, d.y+(ty*a+ny*dd)*K, z*K]; }, A0=pt(-hw+.2,.5,2.85), A1=pt(hw-.2,.5,2.85), B1=pt(hw-.2,1.7,2.35), B0=pt(-hw+.2,1.7,2.35), sl=Math.atan2(.5,1.2), sn=Math.sin(sl), cs=Math.cos(sl);
  gtri(b,A0,A1,B1,nx*sn,ny*sn,cs,0,0,1,0,1,1,22,0); gtri(b,A0,B1,B0,nx*sn,ny*sn,cs,0,0,1,1,0,1,22,0);
  var F0=pt(-hw+.2,1.7,2.35), F1=pt(hw-.2,1.7,2.35), F2=pt(hw-.2,1.7,2.1), F3=pt(-hw+.2,1.7,2.1);                               /* the valance */
  gtri(b,F0,F1,F2,nx,ny,0,0,0,1,0,1,1,22,0); gtri(b,F0,F2,F3,nx,ny,0,0,0,1,1,0,1,22,0);
  glDC(null); }

/* the ground of a cell: asphalt under everything, kerbed sidewalks with their yards, parks, water with quays, highway ribbons, lane dashes, crosswalks */
function glBase(b,cell,W){
  var G=W._gl, x0=cell.ci*CELL, y0=cell.cj*CELL, x1=x0+CELL, y1=y0+CELL, i, o;
  glDC(null); _gH=0; _gL=0;
  gflat(b,[x0,y0,x1,y0,x1,y1,x0,y1],0,(typeof REAL!=='undefined'&&REAL.isOn&&REAL.isOn())?12:11,0,true);        /* the base is paving in the real street world (asphalt is only what a road ribbon lays on it), asphalt in the page's own city */
  for(i=0;i<cell.til.length;i++){ o=cell.til[i]; var rg=MB.ringOut(o.ring), n=rg.length/2, k;
    for(k=0;k<n;k++){ var j=(k+1)%n, ax=rg[2*k], ay=rg[2*k+1], bx=rg[2*j], by=rg[2*j+1], dx=bx-ax, dy=by-ay, l=Math.hypot(dx,dy); if(l<.2) continue; gwall(b,ax,ay,bx,by,0,GZ_SIDE,-dy/l,dx/l,0,45,0); }
    gflat(b,rg,GZ_SIDE,12,0,true);
    if(o.inner) gflat(b,MB.ringOut(o.inner),GZ_SIDE,46+64,0,true); }
  for(i=0;i<cell.par.length;i++){ o=cell.par[i]; var pr=o.ring; if(pr.length>2400){ var kk=Math.ceil(pr.length/2400), q=[]; for(var ii=0;ii<pr.length/2;ii+=kk) q.push(pr[2*ii],pr[2*ii+1]); pr=q; } gflat(b,pr,o.mat?.02:GZ_SIDE+.05,(o.mat||13)+128,0,true); }                 /* o.mat: a real-street area (parking, park, pitch) lies below the roads, paint and kerbs; the page's own parks sit on the sidewalk level */
  for(i=0;i<cell.wat.length;i++){ o=cell.wat[i]; var sw=glStrip(o.x0,o.y0,o.x1,o.y1,o.w+3.5,3), sv=glStrip(o.x0,o.y0,o.x1,o.y1,o.w,3); gflat(b,sw,.06,12+64,0,true); gflat(b,sv,.12,10+128,0,true); }
  for(i=0;i<cell.rod.length;i++){ o=cell.rod[i]; glRoadSeg(b,o); }
  for(i=0;i<cell.das.length;i++){ o=cell.das[i]; glQuad4(b,o.ring,.1,40+128,0); }
  for(i=0;i<cell.xs.length;i++) glCrosswalk(b,cell.xs[i]); }
function glStrip(ax,ay,bx,by,w,ext){ var dx=bx-ax, dy=by-ay, l=Math.hypot(dx,dy)||1, ux=dx/l, uy=dy/l, nx=-uy*w/2, ny=ux*w/2; ax-=ux*ext; ay-=uy*ext; bx+=ux*ext; by+=uy*ext; return [ax+nx,ay+ny, bx+nx,by+ny, bx-nx,by-ny, ax-nx,ay-ny]; }
function glQuad4(b,q,z,pk,t){ var A=[q[0],q[1],z], B=[q[2],q[3],z], C=[q[4],q[5],z], D=[q[6],q[7],z]; var l=Math.hypot(q[2]-q[0],q[3]-q[1])/UM, w=Math.hypot(q[6]-q[0],q[7]-q[1])/UM; gquad(b,A,B,C,D,0,0,1,0,l,0,w,pk,t); }
function glRoadSeg(b,o){
  var dx=o.x1-o.x0, dy=o.y1-o.y0, l=Math.hypot(dx,dy)||1, ux=dx/l, uy=dy/l, nx=-uy, ny=ux, w=o.w+4, ext=2, hw=w/2;
  _gdr=1; _gdg=(o.w/2/UM)-.45; var v0=(o.x0*ux+o.y0*uy-ext)/UM, v1=(o.x1*ux+o.y1*uy+ext)/UM;
  var A=[o.x0-ux*ext-nx*hw,o.y0-uy*ext-ny*hw,.04], B=[o.x0-ux*ext+nx*hw,o.y0-uy*ext+ny*hw,.04], C=[o.x1+ux*ext+nx*hw,o.y1+uy*ext+ny*hw,.04], D=[o.x1+ux*ext-nx*hw,o.y1+uy*ext-ny*hw,.04];
  gquad(b,A,B,C,D,0,0,1,-hw/UM,hw/UM,v0,v1,43+64,o.rk==null?.47:(o.rk+.5)/32); _gdr=1; _gdg=1; }      /* o.rk: palace_ride_street.py realRoadRanks (a depth rank for overlapping ribbons) */
var _xwA=[[1,0],[-1,0],[0,1],[0,-1]];
function glCrosswalk(b,x){
  var X=x.x, Y=x.y, SW=STREET_HW, arms=x.arms, a, k; glDC(null);
  for(a=0;a<4;a++){ if(!(arms&(1<<a))) continue; var ax=_xwA[a][0], ay=_xwA[a][1], px=-ay, py=ax;
    var d0=SW+1.2, d1=SW+4.3, half=SW-1.6, pitch=1.62, bw=.82, nb=Math.floor(half*2/pitch);
    for(k=0;k<nb;k++){ var c=-half+pitch*(k+.5)+(half*2-pitch*nb)/2; var cxm=X+px*c, cym=Y+py*c;
      var A=[cxm+ax*d0-px*bw/2,cym+ay*d0-py*bw/2,.12], B=[cxm+ax*d1-px*bw/2,cym+ay*d1-py*bw/2,.12], C=[cxm+ax*d1+px*bw/2,cym+ay*d1+py*bw/2,.12], D=[cxm+ax*d0+px*bw/2,cym+ay*d0+py*bw/2,.12];
      gquad(b,A,B,C,D,0,0,1,0,1,0,1,40+192,0); }
    /* the stop line */
    var s0=d1+2.2, s1=s0+.8; gquad(b,[X+ax*s0-px*half*.98,Y+ay*s0-py*half*.98,.12],[X+ax*s1-px*half*.98,Y+ay*s1-py*half*.98,.12],[X+ax*s1+px*half*.98,Y+ay*s1+py*half*.98,.12],[X+ax*s0+px*half*.98,Y+ay*s0+py*half*.98,.12],0,0,1,0,1,0,1,40+192,0); } }
"""

_JS_GL_CHUNKS = r"""
/* ── chunks: the world W grouped by cell, built a few milliseconds a frame, nearest first, cached by content ── */
function glHashStr(h,v){ return (Math.imul(h,31)+(v|0))|0; }
function glPlan(W){
  var cnt=(W.solids?W.solids.length:0)+(W.tiles?W.tiles.length:0)+(W.parks?W.parks.length:0)+(W.water?W.water.length:0)+(W.roads?W.roads.length:0);
  if(W._gl && W._gl.gen===GLX.gen && W._gl.cnt===cnt && W._gl.ver===W.ver) return W._gl;
  var G={gen:GLX.gen, cnt:cnt, ver:W.ver, cells:{}, keys:[], xs:[], meshes:[], sig:0}, lmMesh={}, i;
  (W.meshes||[]).forEach(function(m){ if(m && m.id) lmMesh[m.id]=1; });
  function cell(x,y){ var ci=Math.floor(x/CELL), cj=Math.floor(y/CELL), k=ci+','+cj, c=G.cells[k]; if(!c){ c=G.cells[k]={ci:ci,cj:cj,key:k,msh:[],sol:[],til:[],par:[],wat:[],rod:[],das:[],xs:[],h:0,rad:0,state:0,job:null}; G.keys.push(k); } return c; }
  (W.meshes||[]).forEach(function(m){ if(!m||!m.a||!m.a.length||m.tex||typeof m.id!=='string'||m.id.indexOf('scn:')!==0) return; var q=m.id.slice(4).split(','), ci=+q[0], cj=+q[1]; if(!isFinite(ci)||!isFinite(cj)) return;
    var c=cell((ci+.5)*CELL,(cj+.5)*CELL), n=m.a.length, hh=n; for(var u=0;u<8;u++) hh=glHashStr(hh,Math.round(m.a[Math.floor(u*(n-1)/7)]*50)); c.msh.push(m); m._gm=1; c.h=glHashStr(c.h,hh); });
  (W.solids||[]).forEach(function(s){ if(s.kind==='lm' && lmMesh[s.name]) return; var c=cell(s.cx,s.cy); c.sol.push(s); c.h=glHashStr(c.h,Math.round(s.cx*8)+Math.round(s.cy*8)*7+Math.round(s.h*8)*13+s.n*3+(s.kind==='lm'?5:0)+(s.z0?Math.round(s.z0*9):0)+(s.hide?s.hide.length*17:0)+(s.nodraw?29:0)+(s.roofDz?41:0)); c.rad=Math.max(c.rad,s.r||0); });
  (W.tiles||[]).forEach(function(t){ var c=cell(t.cx,t.cy); c.til.push(t); c.h=glHashStr(c.h,Math.round(t.cx*5)+Math.round(t.cy*3)+t.ring.length); c.rad=Math.max(c.rad,t.r||0); });
  (W.parks||[]).forEach(function(p){ var c=cell(p.cx,p.cy); c.par.push(p); c.h=glHashStr(c.h,Math.round(p.cx*5)+Math.round(p.cy*3)+p.ring.length*11); c.rad=Math.max(c.rad,p.r||0); });
  (W.water||[]).forEach(function(w){ var c=cell(w.cx,w.cy); c.wat.push(w); c.h=glHashStr(c.h,Math.round(w.cx*5)+Math.round(w.cy*3)+Math.round(w.w)); c.rad=Math.max(c.rad,w.r||0); });
  (W.roads||[]).forEach(function(w){ var c=cell(w.cx,w.cy); c.rod.push(w); c.h=glHashStr(c.h,Math.round(w.cx*5)+Math.round(w.cy*3)+7+(w.rk|0)*131); c.rad=Math.max(c.rad,w.r||0); });
  (W.dashes||[]).forEach(function(w){ var c=cell(w.cx,w.cy); c.das.push(w); c.h=glHashStr(c.h,Math.round(w.cx*3)+Math.round(w.cy*5)+1); });
  /* intersections of the street grid, from the rectangular blocks: a crosswalk on every arm that has a block either side.
     quadrant bits of an intersection: 1 block to the east+south, 2 west+south, 4 east+north, 8 west+north (y grows southward) */
  if(GLX.crosswalks!==false && !W.pal){ var SW=STREET_HW, X={};
    (W.tiles||[]).forEach(function(t){ var r=t.ring; if(r.length!==8) return;
      if(!((Math.abs(r[0]-r[6])<.01 && Math.abs(r[1]-r[3])<.01 && Math.abs(r[2]-r[4])<.01 && Math.abs(r[5]-r[7])<.01) || (Math.abs(r[1]-r[7])<.01 && Math.abs(r[0]-r[2])<.01 && Math.abs(r[3]-r[5])<.01 && Math.abs(r[4]-r[6])<.01))) return;
      var x0=Math.min(r[0],r[2],r[4],r[6]), x1=Math.max(r[0],r[2],r[4],r[6]), y0=Math.min(r[1],r[3],r[5],r[7]), y1=Math.max(r[1],r[3],r[5],r[7]);
      [[x0-SW,y0-SW,1],[x1+SW,y0-SW,2],[x0-SW,y1+SW,4],[x1+SW,y1+SW,8]].forEach(function(q){ var key=Math.round(q[0])+','+Math.round(q[1]), e=X[key]; if(!e) e=X[key]={x:q[0],y:q[1],q:0}; e.q|=q[2]; }); });
    Object.keys(X).forEach(function(k){ var e=X[k], q=e.q;
      e.arms=((q&1)&&(q&4)?1:0)|((q&2)&&(q&8)?2:0)|((q&1)&&(q&2)?4:0)|((q&4)&&(q&8)?8:0);       /* east, west, south, north */
      if(e.arms){ var c=cell(e.x,e.y); c.xs.push(e); c.h=glHashStr(c.h,Math.round(e.x*3)+Math.round(e.y*7)+e.arms); } }); }
  G.keys.forEach(function(k){ var c=G.cells[k]; c.cx=(c.ci+.5)*CELL; c.cy=(c.cj+.5)*CELL; c.ck=k+'|'+c.h+'|'+c.sol.length+','+c.til.length+','+c.par.length+','+c.wat.length+','+c.xs.length+','+c.msh.length; });
  W._gl=G; return G; }
/* a cell's build state machine: stage 0 the ground, stage 1 the buildings (a few at a time), then upload */
function glCellStep(W,c,deadline){
  if(!c.job){ c.job={b:new GBuf(), i:0, stage:0}; }
  var j=c.job, b=j.b;
  if(j.stage===0){ var tb=performance.now(); glBase(b,c,W); j.stage=1; var db=performance.now()-tb; if(db>(GLX.st.slowBase||0)){ GLX.st.slowBase=db; GLX.st.slowCell=c.key+' til'+c.til.length+' par'+c.par.length+' wat'+c.wat.length+' das'+c.das.length+' xs'+c.xs.length; } }
  if(j.stage===1){ var sol=c.sol, n=sol.length;
    while(j.i<n){ glSolid(b,sol[j.i++]); if((j.i&3)===0 && performance.now()>deadline) return false; }
    j.stage=2; }
  for(var mi=0; mi<c.msh.length; mi++) glAppend(b,c.msh[mi].a);
  var o=glUpload(b); o.rad=c.rad; GLX.cache[c.ck]=o; GLX.nCache++; GLX.st.built++; c.job=null; c.state=2; return true; }
/* the buffer to draw for a planned cell: the one built for its present content, else the one it last had (a regathered world rebuilds the cells whose content moved a little; until then the old one stays,
   so a world swap is never seen as holes) */
function glCellObj(G,k){ var c=G.cells[k], o=GLX.cache[c.ck]; if(o){ GLX.prev[k]=o; return o; } o=GLX.prev[k]; return (o && o.buf && o.gen===GLX.gen)?o:null; }
function glEvict(){
  if(GLX.nCache<=GL_MAXCACHE) return; var ks=Object.keys(GLX.cache).sort(function(p,q){ return GLX.cache[p].use-GLX.cache[q].use; });
  for(var i=0; i<ks.length && GLX.nCache>GL_MAXCACHE-12; i++){ var o=GLX.cache[ks[i]]; if(o.use>=GLX.frame-90) break; glFree(o); delete GLX.cache[ks[i]]; GLX.nCache--; } }
function glPending(W){ var G=glPlan(W), out=[]; G.keys.forEach(function(k){ var c=G.cells[k]; if(GLX.cache[c.ck]){ c.state=2; return; } out.push(c); }); return out; }
function glWork(W,budget){
  var G=glPlan(W), t0=performance.now(), deadline=t0+budget, left=0;
  var pend=glPending(W); if(pend.length){
    pend.forEach(function(c){ c.d=Math.max(0,Math.hypot(c.cx-C.x,c.cy-C.y)-c.rad-CELL*.5); });
    pend.sort(function(p,q){ return p.d-q.d; });
    for(var i=0;i<pend.length;i++){ if(performance.now()>deadline && !(GLX.fresh&&pend[i].d<CELL*1.2)) break; if(glCellStep(W,pend[i],GLX.fresh&&pend[i].d<CELL*1.2?t0+400:deadline)) continue; break; }
    left=glPending(W).length; }
  /* meshes from other parts (landmarks, scenery) and the ride's way, as time allows */
  (W.meshes||[]).forEach(function(m){ if(!m||!m.a||!m.a.length||m._gm||(m.tex&&!W.atlas)) return; var fo=glMeshFind(m); if(fo){ fo.use=GLX.frame; return; } if(performance.now()>deadline && !GLX.fresh) return; glMeshGet(m.a,m.id,m.tex); });
  GLX.st.pending=left; return left; }
/* a mesh from another part (landmarks, scenery, a mover's model) as a GL buffer: by array identity, else by id + size + a few sampled values, so a world that is
   re-gathered with identical scenery reuses the buffers it already has */
function glMeshPeek(a){ var o=GLX.mc?GLX.mc.get(a):null; return (o && o.gen===GLX.gen && o.buf)?o:null; }
/* a mesh's buffer if one already exists for it - by array identity, else by the id + size + sampled values key (a regathered world makes new arrays of the same scenery) - and never a build: this is what the
   frame draws with, so a world swap does not make every tree, lamp and car vanish until each has been looked up again */
function glMeshFind(m){
  var a=m.a, o=glMeshPeek(a); if(o) return o; if(m.tex||typeof m.id!=='string') return null;
  var n=a.length, key='m:'+(m.id||'')+'|'+n+'|'; for(var i=0;i<8;i++) key+=a[Math.floor(i*(n-1)/7)].toFixed(2)+',';
  var c=GLX.cache[key]; if(c && c.gen===GLX.gen && c.buf){ c.use=GLX.frame; if(GLX.mc) GLX.mc.set(a,c); GLX.prevM[m.id]=c; return c; }
  c=GLX.prevM[m.id]; if(c && c.gen===GLX.gen && c.buf){ c.use=GLX.frame; return c; } return null; }       /* not uploaded yet: the last one of this id stays up (palace_ride_g.py ids are per 300-unit cell) */
function glMeshGet(a,id,nokey){
  var o=glMeshPeek(a); if(o){ o.use=GLX.frame; return o; }
  if(nokey){ var e0=glExpand(a); o=glUpload({a:e0.a, n:e0.a.length, x0:e0.x0,x1:e0.x1,y0:e0.y0,y1:e0.y1,z0:e0.z0,z1:e0.z1}); o.use=GLX.frame; GLX.cache['u:'+(++GLX.uid)]=o; GLX.nCache++; if(GLX.mc) GLX.mc.set(a,o); return o; }
  var n=a.length, key='m:'+(id||'')+'|'+n+'|'; for(var i=0;i<8;i++) key+=a[Math.floor(i*(n-1)/7)].toFixed(2)+',';
  var c=GLX.cache[key]; if(c && c.gen===GLX.gen && c.buf){ c.use=GLX.frame; if(GLX.mc) GLX.mc.set(a,c); return c; }
  var e=glExpand(a); var b={a:e.a, n:e.a.length, x0:e.x0,x1:e.x1,y0:e.y0,y1:e.y1,z0:e.z0,z1:e.z1}; o=glUpload(b); GLX.cache[key]=o; GLX.nCache++; if(GLX.mc) GLX.mc.set(a,o); if(id) GLX.prevM[id]=o; return o; }
"""

_JS_GL_WAY = r"""
/* ── the ride's own way as one static mesh per model, built across frames: track and road ribbons, rails, bridges, viaducts, tunnel mouths ── */
var WAY_SEG=260;
function glWayGet(M,W){
  var g=M._gw; if(g && g.gen===GLX.gen) return g;
  g={gen:GLX.gen, segs:[], done:false, si:0, s:0, b:null, segN:-1, prev:null, M:M, ug:M._ug||[], pi:0, portals:false, el:null}; M._gw=g; return g; }
function glFreeWay(M){ var g=M&&M._gw; if(g){ (g.segs||[]).forEach(glFree); g.segs=[]; M._gw=null; } }
function glInUg(M,sec,s){ for(var i=0;i<sec.ug.length;i++){ var g=sec.ug[i]; if(s>g[0]+16 && s<g[1]-16) return true; } return false; }
function glInBr(M,s){ var br=M._br||[]; for(var i=0;i<br.length;i++) if(s>=br[i][0]&&s<=br[i][1]) return br[i]; return null; }
function glRibbon(b,p,q,off,w,zo,pk,t,uc){      /* p,q = frames {x,y,nx,ny,z,s}: a ribbon w wide at offset off between them, u across (m, centred), v along (m) */
  var hw=w/2, A=[p.x+p.nx*(off-hw),p.y+p.ny*(off-hw),p.z+zo], B=[p.x+p.nx*(off+hw),p.y+p.ny*(off+hw),p.z+zo], C=[q.x+q.nx*(off+hw),q.y+q.ny*(off+hw),q.z+zo], D=[q.x+q.nx*(off-hw),q.y+q.ny*(off-hw),q.z+zo];
  gquad(b,A,B,C,D,0,0,1,-hw/UM,hw/UM,p.s/UM,q.s/UM,pk,t); }
function glSide(b,p,q,off,z0a,z0b,z1a,z1b,pk,t,sd){        /* a vertical strip along the path at offset off (sd = +1 outward to the right, -1 to the left) */
  var A=[p.x+p.nx*off,p.y+p.ny*off,z0a], B=[q.x+q.nx*off,q.y+q.ny*off,z0b], C=[q.x+q.nx*off,q.y+q.ny*off,z1b], D=[p.x+p.nx*off,p.y+p.ny*off,z1a];
  gquad(b,A,B,C,D,p.nx*sd,p.ny*sd,0,p.s/UM,q.s/UM,0,(z1a-z0a)/UM,pk,t); }
function glWF(M,s,o){ pathAt(M.D,s,_pa); var h=headAt(M.D,s,8); o.x=_pa.x; o.y=_pa.y; o.nx=-Math.sin(h); o.ny=Math.cos(h); o.fx=Math.cos(h); o.fy=Math.sin(h); o.z=lift(M,s); o.s=s; o.h=h; return o; }
function glWayStep(g,deadline){
  var M=g.M, D=M.D, b, gr=g;
  while(gr.si<M.secs.length){
    var sec=M.secs[gr.si], v=sec.veh, step=v==='walk'?7:5, s=gr.s||sec.s0;
    if(!gr.prev) gr.prev=glWF(M,s,{});
    var cnt=0;
    for(; s<sec.s1; ){
      var s2=Math.min(sec.s1,s+step), cur=glWF(M,s2,{}), segN=Math.floor(s2/WAY_SEG);
      if(!gr.b||segN!==gr.segN){ if(gr.b&&gr.b.n) gr.segs.push(glUpload(gr.b)); gr.b=new GBuf(); gr.segN=segN; }
      b=gr.b; var p=gr.prev; _gH=0; _gL=0; glDC(null);
      if(!glInUg(M,sec,(s+s2)/2)) glWayPiece(b,M,sec,v,p,cur,s,s2);
      gr.prev=cur; s=s2; if(((++cnt)&15)===0 && performance.now()>deadline){ gr.s=s; return false; } }
    gr.si++; gr.s=0; gr.prev=null; }
  if(!gr.portals){ gr.portals=true; if(!gr.b) gr.b=new GBuf(); glPortals(gr.b,M); }
  if(gr.b&&gr.b.n) gr.segs.push(glUpload(gr.b)); gr.b=null; gr.done=true; return true; }
function glWayPiece(b,M,sec,v,p,q,s,s2){
  var br=glInBr(M,s2), lf=q.z>.5;
  if(v==='metro'||v==='rail'){
    var bw=v==='rail'?10:8.5; glDC(null);
    if(!lf){ glRibbon(b,p,q,0,bw,.18,41+64,0);
      [-1,1].forEach(function(sd){ var o=sd*(bw/2); var A=[p.x+p.nx*o,p.y+p.ny*o,p.z+.18], B=[q.x+q.nx*o,q.y+q.ny*o,q.z+.18], C=[q.x+q.nx*(o+sd*1.4),q.y+q.ny*(o+sd*1.4),q.z], D=[p.x+p.nx*(o+sd*1.4),p.y+p.ny*(o+sd*1.4),p.z];
        gquad(b,A,B,C,D,0,0,1,0,1,0,1,41+64,0); }); }
    else glRibbon(b,p,q,0,bw,.18,41+64,0);
    var gauge=.93; [-1,1].forEach(function(sd){ glRail(b,p,q,sd*gauge); });
    if(lf&&!br){ glViaduct(b,p,q,s,s2); } }
  else if(v==='tram'){
    glRibbon(b,p,q,0,6.5,.12,47+64,0); [-1,1].forEach(function(sd){ glRail(b,p,q,sd*.85); });
    if(lf&&!br) glViaduct(b,p,q,s,s2); }
  else if(v==='bus'||v==='car'){
    var rw=sec.hw?30:22; _gdr=sec.hw?1:0; _gdg=sec.hw?(rw/2/UM-.55):0; glRibbon(b,p,q,0,rw,.1,43+64,0); _gdr=1; _gdg=1; }
  if(br){ glBridge(b,p,q,v); }
  else if(v==='walk'&&lf){ glRibbon(b,p,q,VEH.walk.off,6,.1,12+64,0); } }
function glRail(b,p,q,o){
  var w=.22, z0=.18, z1=.46, hw=w/2, A=[p.x+p.nx*(o-hw),p.y+p.ny*(o-hw),p.z+z1], B=[p.x+p.nx*(o+hw),p.y+p.ny*(o+hw),p.z+z1], C=[q.x+q.nx*(o+hw),q.y+q.ny*(o+hw),q.z+z1], D=[q.x+q.nx*(o-hw),q.y+q.ny*(o-hw),q.z+z1];
  gquad(b,A,B,C,D,0,0,1,0,.2,p.s/UM,q.s/UM,42+64,0);
  [-1,1].forEach(function(sd){ var oo=o+sd*hw; var a=[p.x+p.nx*oo,p.y+p.ny*oo,p.z+z0], bb=[q.x+q.nx*oo,q.y+q.ny*oo,q.z+z0], c=[q.x+q.nx*oo,q.y+q.ny*oo,q.z+z1], d=[p.x+p.nx*oo,p.y+p.ny*oo,p.z+z1]; gquad(b,a,bb,c,d,p.nx*sd,p.ny*sd,0,p.s/UM,q.s/UM,0,.2,42+64,0); }); }
function glViaduct(b,p,q,s,s2){
  [-1,1].forEach(function(sd){ glSide(b,p,q,sd*5.2,p.z-2.6,q.z-2.6,p.z+.2,q.z+.2,47,0,sd); });
  var k0=Math.floor(s/40), k1=Math.floor(s2/40); if(k1!==k0){ var f=q; gbox(b,f.x,f.y,2.4,1.2,0,q.z-2.6,Math.atan2(q.fy,q.fx)+0,47,0,false); }
  var A=[p.x-p.nx*5.2,p.y-p.ny*5.2,p.z-2.6], B=[p.x+p.nx*5.2,p.y+p.ny*5.2,p.z-2.6], C=[q.x+q.nx*5.2,q.y+q.ny*5.2,q.z-2.6], D=[q.x-q.nx*5.2,q.y-q.ny*5.2,q.z-2.6]; gquad(b,A,B,C,D,0,0,-1,0,1,0,1,47,0); }
function glBridge(b,p,q,v){
  var hw=17; var A=[p.x-p.nx*hw,p.y-p.ny*hw,p.z-.1], B=[p.x+p.nx*hw,p.y+p.ny*hw,p.z-.1], C=[q.x+q.nx*hw,q.y+q.ny*hw,q.z-.1], D=[q.x-q.nx*hw,q.y-q.ny*hw,q.z-.1];
  gquad(b,A,B,C,D,0,0,1,-hw/UM,hw/UM,p.s/UM,q.s/UM,v==='bus'||v==='car'?43+64:47+64,0);
  [-1,1].forEach(function(sd){ glSide(b,p,q,sd*hw,p.z-2.6,q.z-2.6,p.z+1.5,q.z+1.5,47,0,sd); glSide(b,p,q,sd*(hw-.5),p.z+.0,q.z+.0,p.z+1.3,q.z+1.3,47,0,-sd); });
  var k0=Math.floor(p.s/70), k1=Math.floor(q.s/70); if(k1!==k0){ gbox(b,q.x,q.y,3,1.4,-3,q.z-2.6,Math.atan2(q.fy,q.fx),47,0,false); } }
function glPortals(b,M){
  M.secs.forEach(function(sec){ if(!sec.line) return; var col=rgbOf(sec.color||'#6a5acd'); sec.ug.forEach(function(g){ if(g[0]>sec.s0+.5) glPortal(b,M,sec,g[0],col,false); if(g[1]<sec.s1-.5) glPortal(b,M,sec,g[1],col,true); }); }); }
function glPortal(b,M,sec,s,col,exit){          /* exit: the same mouth turned round, its tunnel behind the camera as it leaves (seen from the other side by the way back) */
  var f=glWF(M,s,{}), v=sec.veh, w=v==='tram'?5.5:7.5, ho=v==='tram'?10.5:12, WW=28, HH=26, sg=exit?-1:1, fx=f.fx*sg, fy=f.fy*sg, nx=-fy, ny=fx, z=f.z;
  glDC(null); _gH=0; _gL=0;
  function P(l,zz,ds){ return [f.x+nx*l+fx*(ds||0), f.y+ny*l+fy*(ds||0), z+zz]; }
  function face(l0,l1,z0,z1,pk){ gquad(b,P(l0,z0),P(l1,z0),P(l1,z1),P(l0,z1),-fx,-fy,0,l0/UM,l1/UM,z0/UM,z1/UM,pk,0); }
  face(-WW,-w,0,HH,47); face(w,WW,0,HH,47); face(-w,w,ho,HH,47);
  [-1,1].forEach(function(sd){ var l=sd*w; gquad(b,P(l,0,0),P(l,0,16),P(l,ho,16),P(l,ho,0),-nx*sd,-ny*sd,0,0,1,0,1,15,0); });
  gquad(b,P(-w,ho,0),P(w,ho,0),P(w,ho,16),P(-w,ho,16),0,0,-1,0,1,0,1,15,0);
  var back=[P(-w,0,16),P(w,0,16),P(w,ho,16),P(-w,ho,16)]; _gdr=col[0]/255; _gdg=col[1]/255; _gdb=col[2]/255;
  gquad(b,back[0],back[1],back[2],back[3],-fx,-fy,0,-w/UM,w/UM,0,ho/UM,44,0); glDC(null);
  /* the walls of the cutting that lead in */
  [-1,1].forEach(function(sd){ for(var q=0;q<5;q++){ var a0=-90+q*18, a1=a0+18, h0=q*3.4+2, h1=(q+1)*3.4+2; var l=sd*(WW-1);
    gquad(b,P(l,0,a0),P(l,0,a1),P(l,h1,a1),P(l,h0,a0),-nx*sd,-ny*sd,0,0,1,0,h1/UM,47,0); } }); }
"""

_JS_GL_FRAME = r"""
/* ── the camera, the light, one frame ── */
var _gm=new Float32Array(16);
function glCamera(){
  var W=C.W, H=C.H, y=C.yaw, p=C.pitch||0, cy=Math.cos(y), sy=Math.sin(y), cp=Math.cos(p), sp=Math.sin(p), foc=C.foc, n=GL_NEAR, f=GL_FAR;
  var F=[cy*cp, sy*cp, sp], Rv=[-sy, cy, 0], U=[-sp*cy, -sp*sy, cp];
  var ax=2*foc/W, ox=1-2*C.hx/W, ay=2*foc/H, oy=1-2*C.hy/H, A=(f+n)/(f-n), B=-2*f*n/(f-n);
  var fe=0, re=0, ue=0;       /* camera-relative: the vertex shader subtracts uEye first. The city's world coordinates are ~1e4 units, so a matrix that carries the camera's translation loses ~1e-3 units of depth in float32 and coplanar surfaces flicker */
  var r0=[ax*Rv[0]+ox*F[0], ax*Rv[1]+ox*F[1], ax*Rv[2]+ox*F[2], -(ax*re+ox*fe)];
  var r1=[ay*U[0]+oy*F[0], ay*U[1]+oy*F[1], ay*U[2]+oy*F[2], -(ay*ue+oy*fe)];
  var r2=[A*F[0], A*F[1], A*F[2], B-A*fe];
  var r3=[F[0],F[1],F[2],-fe];
  var k=C.shk, sc=1, cs=1, sn=0, tx=0, ty=0;
  if(k){ sc=k.s||1; cs=Math.cos(k.r||0); sn=Math.sin(k.r||0); tx=2*(k.x||0)/W; ty=-2*(k.y||0)/H; }
  var a=[], b2=[], i;
  for(i=0;i<4;i++){ a.push(sc*(cs*r0[i]+(H/W)*sn*r1[i])+tx*r3[i]); b2.push(sc*(cs*r1[i]-(W/H)*sn*r0[i])+ty*r3[i]); }
  var rows=[a,b2,r2,r3], m=_gm; for(var rr=0;rr<4;rr++) for(var cc=0;cc<4;cc++) m[cc*4+rr]=rows[rr][cc];
  GLX.cam={F:F,R:Rv,U:U,ax:ax,ox:ox,ay:ay,oy:oy,sc:sc,cs:cs,sn:sn,tx:tx,ty:ty};
  return m; }
function glLin(c){ return [Math.pow(c[0]/255,2.2), Math.pow(c[1]/255,2.2), Math.pow(c[2]/255,2.2)]; }
function glLight(P){
  var dk=P.dk, L={dk:dk};
  if(dk){ L.sun=[-.5,-.42,.76]; L.sunCol=[.14,.19,.42]; L.skyA=[.055,.07,.13]; L.gndA=[.028,.03,.045]; L.exp=1.35; }
  else { L.sun=[-.55,-.66,.62]; L.sunCol=[2.9,2.55,2.05]; L.skyA=[.42,.49,.60]; L.gndA=[.28,.265,.24]; L.exp=1.0; }
  var l=Math.hypot(L.sun[0],L.sun[1],L.sun[2]); L.sun=[L.sun[0]/l,L.sun[1]/l,L.sun[2]/l];
  L.zen=glLin(P.zen); L.hor=glLin(P.hor); L.fog=glLin(P.fog); L.gnd=dk?[.016,.017,.022]:[.12,.115,.11];
  return L; }
function glUni(gl,pg,L,tm,vp){
  var u=pg.u;
  if(u.uVP) gl.uniformMatrix4fv(u.uVP,false,vp);
  gl.uniform3f(u.uEye,C.x,C.y,C.z); gl.uniform3fv(u.uSun,L.sun); gl.uniform3fv(u.uSunCol,L.sunCol); gl.uniform3fv(u.uSkyA,L.skyA); gl.uniform3fv(u.uGndA,L.gndA);
  gl.uniform3fv(u.uZen,L.zen); gl.uniform3fv(u.uHor,L.hor); gl.uniform3fv(u.uFog,L.fog); gl.uniform1f(u.uFogD,FOGD*1.2/(1+6*(GLX.edge||0))); gl.uniform1f(u.uNight,L.dk?1:0); gl.uniform1f(u.uTime,tm||0);
  if(u.uPix) gl.uniform1f(u.uPix,1/C.foc); gl.uniform1f(u.uExp,L.exp); gl.uniform1i(u.uNz,0); if(u.uSh) gl.uniform1i(u.uSh,1); if(u.uSq) gl.uniform1i(u.uSq,2); }
function glSphVis(cx,cy,cz,r){
  var cm=GLX.cam, dx=cx-C.x, dy=cy-C.y, dz=cz-C.z, d=dx*cm.F[0]+dy*cm.F[1]+dz*cm.F[2]; if(d+r<GL_NEAR || d-r>FARZ) return false;
  var xc=dx*cm.R[0]+dy*cm.R[1], yc=dx*cm.U[0]+dy*cm.U[1]+dz*cm.U[2], tx=C.W*.5/C.foc*1.08+.05, ty=Math.max(C.hy,C.H-C.hy)/C.foc*1.08+.05;
  return Math.abs(xc)-r*1.05 < Math.max(d+r,0)*tx && Math.abs(yc)-r*1.05 < Math.max(d+r,0)*ty; }
function glBind(gl,pg,o){
  var a=pg.a, S=60; gl.bindBuffer(gl.ARRAY_BUFFER,o.buf);
  gl.vertexAttribPointer(a.aP,3,gl.FLOAT,false,S,0); gl.vertexAttribPointer(a.aN,3,gl.FLOAT,false,S,12); gl.vertexAttribPointer(a.aUV,2,gl.FLOAT,false,S,24);
  gl.vertexAttribPointer(a.aMT,2,gl.FLOAT,false,S,32); gl.vertexAttribPointer(a.aDC,3,gl.FLOAT,false,S,40); gl.vertexAttribPointer(a.aHA,2,gl.FLOAT,false,S,52); }
function glDrawSky(gl,L,tm,vp){
  var pg=GLX.sky, cm=GLX.cam; gl.useProgram(pg.p); gl.disable(gl.DEPTH_TEST); gl.disable(gl.CULL_FACE);
  glUni(gl,pg,L,tm,null);
  gl.uniform3fv(pg.u.uF,cm.F); gl.uniform3fv(pg.u.uR,cm.R); gl.uniform3fv(pg.u.uU,cm.U); gl.uniform4f(pg.u.uPrj,1/cm.ax,cm.ox,1/cm.ay,cm.oy);
  var s=cm.sc, c=cm.cs, sn=cm.sn, W=C.W, H=C.H;
  gl.uniformMatrix2fv(pg.u.uUn,false,[c/s, (W/H)*sn/s, -(H/W)*sn/s, c/s]); gl.uniform2f(pg.u.uUt,cm.tx,cm.ty); gl.uniform3fv(pg.u.uGnd,L.gnd);
  gl.bindBuffer(gl.ARRAY_BUFFER,GLX.quad); gl.enableVertexAttribArray(pg.a.aQ); gl.vertexAttribPointer(pg.a.aQ,2,gl.FLOAT,false,0,0);
  gl.drawArrays(gl.TRIANGLES,0,3); gl.disableVertexAttribArray(pg.a.aQ); gl.enable(gl.DEPTH_TEST); gl.enable(gl.CULL_FACE); }
var _gvis=[];
function glDrawWorld(gl,Wd,L,tm,vp){
  var pg=GLX.prog, a=pg.a, i, st=GLX.st; gl.useProgram(pg.p); glUni(gl,pg,L,tm,vp); gl.uniform1f(pg.u.uInst,0);
  var names=['aP','aN','aUV','aMT','aDC','aHA']; names.forEach(function(n){ gl.enableVertexAttribArray(a[n]); });
  gl.disableVertexAttribArray(a.aI); gl.disableVertexAttribArray(a.aT2); gl.vertexAttrib4f(a.aI,0,0,0,0); gl.vertexAttrib2f(a.aT2,-1,0);
  glSceneryUni(gl,pg,Wd,L);
  gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D,GLX.noise);
  var sd=GLX.shd; if(sd&&sd.ok&&sd.on){ var cf=sd.c[0], cq=sd.c[1]; gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D,cf.tex); gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_2D,cq.tex); gl.activeTexture(gl.TEXTURE0);
    gl.uniformMatrix4fv(pg.u.uLP,false,cf.lp); gl.uniformMatrix4fv(pg.u.uLQ,false,cq.lp); gl.uniform4f(pg.u.uShP,1,1/cf.S,cf.biasD,cq.biasD); gl.uniform2f(pg.u.uShQ,1/cq.S,0); gl.uniform2f(pg.u.uNOff,cf.texel*cf.cfg.noff,cq.texel*cq.cfg.noff); }
  else { gl.uniformMatrix4fv(pg.u.uLP,false,GLX.ident); gl.uniformMatrix4fv(pg.u.uLQ,false,GLX.ident); gl.uniform4f(pg.u.uShP,0,0,0,0); gl.uniform2f(pg.u.uShQ,0,0); gl.uniform2f(pg.u.uNOff,0,0); }
  var G=glPlan(Wd), draws=0, tris=0; _gvis.length=0;
  G.keys.forEach(function(k){ var o=glCellObj(G,k); if(!o) return; o.use=GLX.frame; if(glSphVis(o.cx,o.cy,o.cz,o.r)) _gvis.push(o); });
  _gvis.sort(function(p,q){ return (Math.pow(p.cx-C.x,2)+Math.pow(p.cy-C.y,2))-(Math.pow(q.cx-C.x,2)+Math.pow(q.cy-C.y,2)); });
  gl.enable(gl.CULL_FACE);
  for(i=0;i<_gvis.length;i++){ var o=_gvis[i]; glBind(gl,pg,o); gl.drawArrays(gl.TRIANGLES,0,o.n); draws++; tris+=o.n/3; }
  /* the inside of a node building (palace_ride_inside.py): its own buffer, both faces, not in the shadow pass */
  if(GLX.inside && GLX.inside.buf){ var bt=GLX.insideTex; if(bt){ gl.activeTexture(gl.TEXTURE4); gl.bindTexture(gl.TEXTURE_2D,bt); gl.uniform2f(pg.u.uAtlS,1,1); gl.activeTexture(gl.TEXTURE0); }   /* the directory board's canvas stands in for the street-name atlas during this draw */
    gl.disable(gl.CULL_FACE); glBind(gl,pg,GLX.inside); gl.drawArrays(gl.TRIANGLES,0,GLX.inside.n); draws++; tris+=GLX.inside.n/3; gl.enable(gl.CULL_FACE);
    if(bt){ gl.activeTexture(gl.TEXTURE4); gl.bindTexture(gl.TEXTURE_2D,GLX.atlTex); var as2=GLX.atlS||[1,1]; gl.uniform2f(pg.u.uAtlS,as2[0],as2[1]); gl.activeTexture(gl.TEXTURE0); } }
  /* the ride's way */
  var wy=GLX.curWay; if(wy && wy.segs){ for(i=0;i<wy.segs.length;i++){ var s=wy.segs[i]; if(!glSphVis(s.cx,s.cy,s.cz,s.r)) continue; glBind(gl,pg,s); gl.drawArrays(gl.TRIANGLES,0,s.n); draws++; tris+=s.n/3; } }
  /* meshes from the landmark and scenery parts: no culling (their winding is not ours to trust) */
  gl.disable(gl.CULL_FACE);
  (Wd.meshes||[]).forEach(function(m){ if(!m||!m.a||!m.a.length||m._gm||(m.tex&&!Wd.atlas)) return; var mc=glMeshFind(m); if(!mc) return; if(!glSphVis(mc.cx,mc.cy,mc.cz,mc.r)) return; glBind(gl,pg,mc); gl.drawArrays(gl.TRIANGLES,0,mc.n); draws++; tris+=mc.n/3; });
  draws+=glDrawMovers(gl,pg,Wd); gl.enable(gl.CULL_FACE);
  st.draws=draws; st.tris=tris|0; st.chunks=_gvis.length;
  names.forEach(function(n){ gl.disableVertexAttribArray(a[n]); }); }
/* the scenery part drops movers beyond a distance per kind (cars 460, people 230, birds 380, signal lamps 160): fade them out before that with a dither, so nothing pops */
function glFadeOf(m){ var k=m.kind; return k===0?460:k===1?230:k===2?380:k==null?0:160; }
/* the scenery's colours (W.pal), its street-name atlas, and the nearest lit lamps for light pools at night */
/* a roamed world is one merged world plus its per-cell worlds (W.cells): the palette, the lit lamps and the movers live in the cells */
function glCellsNear(Wd,rad){ var o=[], cs=Wd.cells; if(!cs) return o; var ci=Math.floor(C.x/CELL), cj=Math.floor(C.y/CELL); for(var i=-rad;i<=rad;i++) for(var j=-rad;j<=rad;j++){ var c=cs[(ci+i)+','+(cj+j)]; if(c) o.push(c); } return o; }
function glPalOf(Wd){ if(Wd.pal) return Wd.pal; if(Wd._palc) return Wd._palc; var cs=Wd.cells; if(cs) for(var k in cs){ if(cs[k].pal){ Wd._palc=cs[k].pal; return Wd._palc; } } return null; }
function glMoversOf(Wd,tm){
  if(Wd._mv || !Wd.cells) { if(typeof sceneryUpdate==='function') sceneryUpdate(Wd,tm,C); return Wd.movers; }
  var out=Wd._gmv||(Wd._gmv=[]); out.length=0; glCellsNear(Wd,1).forEach(function(c){ if(typeof sceneryUpdate==='function') sceneryUpdate(c,tm,C); if(c.movers) for(var i=0;i<c.movers.length;i++) out.push(c.movers[i]); }); return out; }
function glSceneryUni(gl,pg,Wd,L){
  var pal=glPalOf(Wd); if(pal && (GLX.palRef!==pal || GLX.palN!==pal.length)){ var px=new Uint8Array(1024), i; for(i=0;i<pal.length&&i<256;i++){ px[4*i]=pal[i][0]; px[4*i+1]=pal[i][1]; px[4*i+2]=pal[i][2]; px[4*i+3]=255; }
    gl.bindTexture(gl.TEXTURE_2D,GLX.palTex); gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,256,1,0,gl.RGBA,gl.UNSIGNED_BYTE,px); GLX.palRef=pal; GLX.palN=pal.length; }
  var at=Wd.atlas; if(at && at.canvas && (GLX.atlRef!==at.canvas || GLX.atlH!==at.h || at.dirty)){ var h=at.canvas.height, w=at.canvas.width, H2=1; while(H2<h) H2*=2;
    var cv=document.createElement('canvas'); cv.width=w; cv.height=H2; cv.getContext('2d').drawImage(at.canvas,0,0); gl.bindTexture(gl.TEXTURE_2D,GLX.atlTex);
    gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,cv); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR_MIPMAP_LINEAR); gl.generateMipmap(gl.TEXTURE_2D);
    GLX.atlRef=at.canvas; GLX.atlH=at.h; GLX.atlS=[1,h/H2]; at.dirty=false; }
  gl.activeTexture(gl.TEXTURE3); gl.bindTexture(gl.TEXTURE_2D,GLX.palTex); gl.activeTexture(gl.TEXTURE4); gl.bindTexture(gl.TEXTURE_2D,GLX.atlTex); gl.activeTexture(gl.TEXTURE0);
  gl.uniform1i(pg.u.uPal,3); gl.uniform1i(pg.u.uAtl,4); var as=GLX.atlS||[1,1]; gl.uniform2f(pg.u.uAtlS,as[0],as[1]);
  var lb=GLX.lampBuf, n=0; lb.fill(0);
  var lsets=Wd.lamps?[Wd.lamps]:glCellsNear(Wd,1).map(function(c){ return c.lamps; }).filter(function(q){ return q&&q.length; });
  if(L.dk && lsets.length){ var best=[], li, la;
    for(li=0;li<lsets.length;li++){ la=lsets[li]; for(i=0;i+2<la.length;i+=3){ var dx=la[i]-C.x, dy=la[i+1]-C.y, d2=dx*dx+dy*dy; if(d2>200*200) continue;
      if(best.length<12 || d2<best[best.length-1].d){ var at2=best.length; while(at2>0 && best[at2-1].d>d2) at2--; best.splice(at2,0,{x:la[i],y:la[i+1],z:la[i+2],d:d2}); if(best.length>12) best.pop(); } } }
    for(var j=0;j<best.length;j++){ lb[4*j]=best[j].x; lb[4*j+1]=best[j].y; lb[4*j+2]=best[j].z; lb[4*j+3]=1; } }
  gl.uniform4fv(pg.u.uLamp,lb); gl.uniform3f(pg.u.uLampC,1.0,.72,.38); if(pg.u.uIn) gl.uniform1f(pg.u.uIn,GLX.inside?1.:0.); }
/* movers: grouped by mesh, instanced where the browser has ANGLE_instanced_arrays, else one draw each */
var _gmg=[];
function glDrawMovers(gl,pg,Wd){
  var mv=Wd._gmv&&!Wd._mv?Wd._gmv:Wd.movers; if(!mv||!mv.length) return 0; var a=pg.a, ext=GLX.inst, groups=[], map=GLX.mc, i, draws=0, lim2=Math.pow(FARZ*.42,2);
  for(i=0;i<mv.length;i++){ var m=mv[i]; if(!m||!m.a||!m.a.length) continue; var dx=m.x-C.x, dy=m.y-C.y; if(dx*dx+dy*dy>lim2) continue; var o=glMeshGet(m.a,'mv',true); if(!glSphVis(m.x,m.y,(m.z||0)+o.cz,o.r+2)) continue;
    var gr=null; for(var q=0;q<groups.length;q++) if(groups[q].o===o){ gr=groups[q]; break; } if(!gr){ gr={o:o,l:[]}; groups.push(gr); } gr.l.push(m); }
  gl.uniform1f(pg.u.uInst,1);
  groups.forEach(function(gr){ var l=gr.l, o=gr.o; glBind(gl,pg,o);
    if(ext && l.length>1){ var n=Math.min(l.length,600), ib=GLX.instBuf, k; for(k=0;k<n;k++){ var m=l[k]; ib[6*k]=m.x; ib[6*k+1]=m.y; ib[6*k+2]=m.z||0; ib[6*k+3]=m.yaw||0; ib[6*k+4]=m.tint==null?-1:m.tint; ib[6*k+5]=glFadeOf(m); }
      gl.bindBuffer(gl.ARRAY_BUFFER,GLX.ibuf); gl.bufferData(gl.ARRAY_BUFFER,ib.subarray(0,6*n),gl.DYNAMIC_DRAW);
      gl.enableVertexAttribArray(a.aI); gl.enableVertexAttribArray(a.aT2); gl.vertexAttribPointer(a.aI,4,gl.FLOAT,false,24,0); gl.vertexAttribPointer(a.aT2,2,gl.FLOAT,false,24,16);
      ext.vertexAttribDivisorANGLE(a.aI,1); ext.vertexAttribDivisorANGLE(a.aT2,1); ext.drawArraysInstancedANGLE(gl.TRIANGLES,0,o.n,n); ext.vertexAttribDivisorANGLE(a.aI,0); ext.vertexAttribDivisorANGLE(a.aT2,0);
      gl.disableVertexAttribArray(a.aI); gl.disableVertexAttribArray(a.aT2); draws++; }
    else { l.forEach(function(m){ gl.vertexAttrib4f(a.aI,m.x,m.y,m.z||0,m.yaw||0); gl.vertexAttrib2f(a.aT2,m.tint==null?-1:m.tint,glFadeOf(m)); gl.drawArrays(gl.TRIANGLES,0,o.n); draws++; }); } });
  gl.uniform1f(pg.u.uInst,0); return draws; }
var GLAPI={ cur:null, way:function(M){ GLX.curWay=M?glWayGet(M):null; return GLX.curWay; } };
/* the whole city for camera C into the GL canvas; returns false when GL is not usable (the caller then paints with the 2D fallback) */
function glFrame(ctx,W,H,P,Wd,yaw,tm,way){
  if(!glOk()) return false; var gl=GLX.gl, t0=performance.now();
  GLX.frame++; var cw=R.cv.width, ch=R.cv.height; glSize(cw,ch); gl.viewport(0,0,cw,ch);
  var vp=glCamera(), L=glLight(P);
  GLX.curWay=null; if(way){ way(GLAPI); }
  var mvs=glMoversOf(Wd,tm);
  /* build: a few ms a frame (the first frame of a new world takes the nearest cells whole) */
  var tA=performance.now(), wk=GLX.curWay; if(wk && !wk.done){ var dl=performance.now()+(GLX.fresh?30:1.6); glWayStep(wk,dl); }
  var tB=performance.now(); glWork(Wd, GLX.fresh?40:2.8); GLX.fresh=false;
  glEvict();
  var tC=performance.now(); glShadowPass(gl,Wd,L,cw,ch);
  var tD=performance.now(); gl.depthMask(true); gl.clear(gl.DEPTH_BUFFER_BIT);
  glDrawSky(gl,L,tm,vp);
  glDrawWorld(gl,Wd,L,tm,vp);
  var tE=performance.now(), pk=GLX.st.pk||(GLX.st.pk={way:0,work:0,shadow:0,draw:0});
  pk.way=Math.max(pk.way,tB-tA); pk.work=Math.max(pk.work,tC-tB); pk.shadow=Math.max(pk.shadow,tD-tC); pk.draw=Math.max(pk.draw,tE-tD);
  /* a still frame (reduced motion, a held arrival) has no loop to finish the chunks still being built: ask for one more render */
  if(GLX.st.pending>0 && !GLX.retry && R.M && !R.playing && !R.quiet){ GLX.retry=setTimeout(function(){ GLX.retry=0; if(R.active && R.M && !R.raf && !R.playing){ R.last=0; R.raf=requestAnimationFrame(loop); } },30); }
  GLX.st.ms=performance.now()-t0; return true; }
GLX.flush=function(){ var gl=GLX.gl; if(gl && GLX.on){ var px=new Uint8Array(4); gl.readPixels(0,0,1,1,gl.RGBA,gl.UNSIGNED_BYTE,px); } };
GLX.newWorld=function(){ GLX.fresh=true; };
/* QA: free camera over a world gathered around (x,y): GLX.look(x,y,eyeZ,yawDeg,pitchDeg,rad cells) draws one frame (the kit uses it for screenshots) */
GLX.look=function(x,y,z,yawDeg,pitchDeg,rad,dk){
  if(!E) return false; ensureOverlay(); if(!R.active){ R.active=true; document.documentElement.classList.add('pal-fp'); } if(dk!=null){ document.documentElement.classList.toggle('dark',!!dk); }
  R.PAL=palette(); sizeCheck(); R.ov.classList.add('on');
  var key=[x,y,rad].join(','); if(GLX._lw!==key){ var set={}, ci=Math.floor(x/CELL), cj=Math.floor(y/CELL); for(var a=-rad;a<=rad;a++) for(var b=-rad;b<=rad;b++) set[(ci+a)+','+(cj+b)]=1; GLX._lwW=gatherWorld(set,null); GLX._lw=key; GLX.fresh=true; }
  R.W=GLX._lwW; setCam(x,y,z,yawDeg*Math.PI/180,R.w,R.h,.5,pitchDeg*Math.PI/180); var ctx=R.ctx; ctx.setTransform(1,0,0,1,0,0); ctx.clearRect(0,0,R.cv.width,R.cv.height); ctx.setTransform(R.dpr,0,0,R.dpr,0,0);
  var t=performance.now(); drawCity(ctx,R.w,R.h,R.PAL,R.W,C.yaw,(GLX._tm||0),null); GLX.flush(); return performance.now()-t; };
/* QA: free camera over the CURRENT ride's world and way */
GLX.lookRide=function(x,y,z,yawDeg,pitchDeg){ if(!R.M||!R.W) return false; R.PAL=palette(); sizeCheck(); R.ov.classList.add('on'); setCam(x,y,z,yawDeg*Math.PI/180,R.w,R.h,.5,pitchDeg*Math.PI/180);
  var ctx=R.ctx; ctx.setTransform(1,0,0,1,0,0); ctx.clearRect(0,0,R.cv.width,R.cv.height); ctx.setTransform(R.dpr,0,0,R.dpr,0,0); var M=R.M;
  for(var i=0;i<3;i++) drawCity(ctx,R.w,R.h,R.PAL,R.W,C.yaw,0,function(g){ if(g) g.way(M); }); GLX.flush(); return GLX.st; };
GLX.E=function(){ return E; };
GLX.tAtS=function(sT){ var M=R.M; if(!M) return -1; var lo=0, hi=M.T; for(var i=0;i<40;i++){ var mid=(lo+hi)/2; if(evalAt(M,mid).s<sT) lo=mid; else hi=mid; } return (lo+hi)/2; };
GLX.settle=function(n){ for(var i=0;i<(n||60);i++){ drawCity(R.ctx,R.w,R.h,R.PAL,R.W,C.yaw,GLX._tm||0,null); } GLX.flush(); return GLX.st; };
window._palRideGL=GLX;
"""

_JS_GL_SHADOW = r"""
/* ── sun shadows: two maps (WEBGL_depth_texture), 2048^2 each - a near one over ~100 units round the camera (soft, 7 cm texels) and a far one over ~420 units - snapped
   to texel steps so nothing crawls, each redrawn only when its snapped centre or the set of built chunks changes ── */
var GL_CASC=[{R:420, S:2048, ahead:190, snap:128, bias:.55, noff:1.3}, {R:100, S:2048, ahead:34, snap:64, bias:.22, noff:1.4}];
function glShadowSetup(gl){
  GLX.shd={ok:false}; if(window._palRideNoShadow) return;
  var ext=gl.getExtension('WEBGL_depth_texture')||gl.getExtension('WEBKIT_WEBGL_depth_texture'); if(!ext) return;
  try{ var cs=[], ok=true;
    GL_CASC.forEach(function(c){ var S=c.S, tex=gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D,tex); gl.texImage2D(gl.TEXTURE_2D,0,gl.DEPTH_COMPONENT,S,S,0,gl.DEPTH_COMPONENT,gl.UNSIGNED_INT,null);
      gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.NEAREST); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.NEAREST); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
      var rb=gl.createRenderbuffer(); gl.bindRenderbuffer(gl.RENDERBUFFER,rb); gl.renderbufferStorage(gl.RENDERBUFFER,gl.RGBA4,S,S);
      var fb=gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER,fb); gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.DEPTH_ATTACHMENT,gl.TEXTURE_2D,tex,0); gl.framebufferRenderbuffer(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.RENDERBUFFER,rb);
      if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE) ok=false;
      cs.push({tex:tex, fb:fb, rb:rb, S:S, R:c.R, texel:2*c.R/S, key:'', lp:new Float32Array(16), cfg:c}); });
    gl.bindFramebuffer(gl.FRAMEBUFFER,null); GLX.shd={ok:ok, c:cs, on:0}; }catch(x){ GLX.shd={ok:false}; } }
function glShadowPass(gl,Wd,L,cw,ch){
  var sd=GLX.shd; if(!sd||!sd.ok||L.dk){ if(sd) sd.on=0; return; }
  var Ls=L.sun, h=Math.hypot(Ls[0],Ls[1]), a=[-Ls[1]/h, Ls[0]/h, 0], b=[-Ls[2]*Ls[0]/h, -Ls[2]*Ls[1]/h, h], G=glPlan(Wd), n=GLX.st.built, nm=(Wd.meshes||[]).length, i, drawn=0;
  sd.on=1; var pg=GLX.shp, ap=pg.a.aP, prepared=false;
  for(var ci=0; ci<sd.c.length; ci++){ var c=sd.c[ci], cf=c.cfg, Rs=c.R, S=c.S, texel=c.texel, snap=texel*cf.snap;
    var ox=C.x+Math.cos(C.yaw)*cf.ahead, oy=C.y+Math.sin(C.yaw)*cf.ahead, oa=Math.round((a[0]*ox+a[1]*oy)/snap)*snap, ob=Math.round((b[0]*ox+b[1]*oy)/snap)*snap;
    var cb=Ls[0]*ox+Ls[1]*oy, cMin=cb-500, cMax=cb+440, k=2/(cMax-cMin), m=c.lp;
    m[0]=a[0]/Rs; m[4]=a[1]/Rs; m[8]=a[2]/Rs; m[12]=-oa/Rs; m[1]=b[0]/Rs; m[5]=b[1]/Rs; m[9]=b[2]/Rs; m[13]=-ob/Rs; m[2]=-Ls[0]*k; m[6]=-Ls[1]*k; m[10]=-Ls[2]*k; m[14]=cMax*k-1; m[3]=0; m[7]=0; m[11]=0; m[15]=1;
    c.biasD=cf.bias/(cMax-cMin);
    var key=oa+'|'+ob+'|'+n+'|'+GLX.gen+'|'+nm+'|'+G.keys.length+'|'+Ls[0]+'|'+(ci?'':'');
    if(key===c.key) continue; c.key=key;
    if(!prepared){ prepared=true; gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D,null); gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_2D,null); gl.activeTexture(gl.TEXTURE0);
      gl.colorMask(false,false,false,false); gl.depthMask(true); gl.useProgram(pg.p); gl.disable(gl.CULL_FACE); gl.enable(gl.POLYGON_OFFSET_FILL); gl.polygonOffset(2,4);
      for(i=0;i<8;i++) gl.disableVertexAttribArray(i); gl.enableVertexAttribArray(ap); }
    gl.bindFramebuffer(gl.FRAMEBUFFER,c.fb); gl.viewport(0,0,S,S); gl.clear(gl.DEPTH_BUFFER_BIT); gl.uniformMatrix4fv(pg.u.uLP,false,m);
    var lat=function(o){ var ca=a[0]*o.cx+a[1]*o.cy-oa, cbb=b[0]*o.cx+b[1]*o.cy+b[2]*o.cz-ob; return Math.abs(ca)-o.r<Rs && Math.abs(cbb)-o.r<Rs; };
    var draw=function(o){ gl.bindBuffer(gl.ARRAY_BUFFER,o.buf); gl.vertexAttribPointer(ap,3,gl.FLOAT,false,60,0); gl.drawArrays(gl.TRIANGLES,0,o.n); drawn++; };
    G.keys.forEach(function(kk){ var o=glCellObj(G,kk); if(o && lat(o)) draw(o); });
    (Wd.meshes||[]).forEach(function(mm){ if(!mm||!mm.a||mm._gm||mm.tex) return; var o=glMeshFind(mm); if(o && lat(o)) draw(o); });
    GLX.st.shadowPasses=(GLX.st.shadowPasses||0)+1; }
  if(prepared){ gl.disableVertexAttribArray(ap); gl.disable(gl.POLYGON_OFFSET_FILL); gl.colorMask(true,true,true,true); gl.bindFramebuffer(gl.FRAMEBUFFER,null); gl.viewport(0,0,cw,ch); GLX.st.shadowDraws=drawn; } }
"""

JS_GL = _GLS + _JS_GL_MAIN + _JS_GL_BUILD + _JS_GL_CHUNKS + _JS_GL_WAY + _JS_GL_SHADOW + _JS_GL_FRAME
