"""Real-geometry first-person world, the landmarks part: the hand-built landmark models (palace_ride_h.py) placed on their REAL footprints.

The real world (palace_ride_street.py gatherReal) draws every OSM building as its footprint extruded. A landmark the user knows (30th Street Station, City Hall...)
came out as a flat-topped slab and nobody recognised it. Here, once a gather has its solids and before the dedupe builds roofs and parapets:

  match   a street-data building whose OSM name gives the same model key (lmKey) as one of the page's landmarks (E.M.landmarks), not a parking garage or hotel
          ("Convention Center Parking"), the one with a wikidata id first, then the nearest to the landmark's own point (unmapped from the page); keys that only
          say what KIND of thing it is (arena, stadium, court) must be within RLM_NEAR metres of it
  target  the outline, or for keys in RLM_PART (the station: its 8-storey building:part, not the 2-storey annex north of it) its largest part
  fit     the target's minimum-area oriented box; the model's x axis goes along the box side that matches the model's own aspect, its front (local +y) toward the
          front bearing of RLM_FRONT (compass degrees the front faces) or else toward the widest road; the model is stretched in plan to the box (each axis
          clamped to RLM_CLAMP), heights stay true; normals and the facade u are corrected for the stretch
  hide    the matched outline, the parts inside the target and any other footprint whose centre falls inside the placed model's own footprint are s.nodraw
          (no walls, roof or parapet; they still stop the walker: palace_ride_e.py collides with every solid), doors none
W.real.lm lists what was placed: [{n, key, osm, part, deg, sx, sy, w, d}]. The model arrays are cached per landmark and footprint (one GPU buffer).
"""
from __future__ import annotations

JS_STREET_LM = r"""
/* ══ real-mode landmarks (palace_ride_street_lm.py) ══ */
var RLM={on:true, cache:{}, L:null};
var RLM_BAD=/\b(parking|garage|autopark|hotel|inn|suites|hampton|days inn|annex|perelman)\b/i;
var RLM_NEAR={arena:200, stad:250, court:150, fam:250};
var RLM_PART={stn:1};
var RLM_FRONT={stn:270, city:180, ind:180, art:120, frank:90, sub:180, conv:180, usch:180, nix:180, fam:180, jef:180};
var RLM_CLAMP=[.6,1.6];
var RLM_ALIAS=[[/^philadelphia justice cent/i,'cjc']];                 /* OSM names the 2D art's key does not know */
function rlmLandmarks(){ if(RLM.L) return RLM.L; var o=[]; ((E&&E.M&&E.M.landmarks)||[]).forEach(function(l){ if(!l||!l.n||l.x==null) return; var k=lmKey(l.n); if(k==='gen'||!LMT[k]) return;
    var r=realOf(l.x,l.y,{x:0,y:0,k:0}); o.push({l:l, key:k, x:r.x, y:r.y}); }); return RLM.L=o; }
/* the minimum-area box of a ring (flat x,y in any unit): {cx, cy, th (angle of axis a), a, b (full lengths along th and th+90)} */
function rlmOBB(r){ var n=r.length/2, best=null, i, j;
  for(i=0;i<n;i++){ j=(i+1)%n; var dx=r[2*j]-r[2*i], dy=r[2*j+1]-r[2*i+1]; if(dx*dx+dy*dy<1e-6) continue; var th=Math.atan2(dy,dx), c=Math.cos(th), s=Math.sin(th), u0=1e18,u1=-1e18,v0=1e18,v1=-1e18;
    for(var q=0;q<n;q++){ var u=r[2*q]*c+r[2*q+1]*s, v=-r[2*q]*s+r[2*q+1]*c; if(u<u0)u0=u; if(u>u1)u1=u; if(v<v0)v0=v; if(v>v1)v1=v; }
    var ar=(u1-u0)*(v1-v0); if(!best||ar<best.ar-1e-9){ var um=(u0+u1)/2, vm=(v0+v1)/2; best={ar:ar, th:th, a:u1-u0, b:v1-v0, cx:um*c-vm*s, cy:um*s+vm*c}; } }
  return best; }
function rlmIn(ring,x,y){ var c=false, n=ring.length/2; for(var i=0,j=n-1;i<n;j=i++){ var ax=ring[2*i], ay=ring[2*i+1], bx=ring[2*j], by=ring[2*j+1]; if((ay>y)!==(by>y) && x<ax+(y-ay)*(bx-ax)/(by-ay)) c=!c; } return c; }
function rlmArea(r){ var a=0, n=r.length/2; for(var i=0;i<n;i++){ var j=(i+1)%n; a+=r[2*i]*r[2*j+1]-r[2*j]*r[2*i+1]; } return Math.abs(a)/2; }
/* how a model of plan bb (local units, x across, y = -v: the front is +y) sits on a box: {phi (rotation), sx, sy} - x along the side that matches its aspect, front toward bearing / road */
function rlmFit(bb, o, key, roadW){
  var mw=bb[2]-bb[0], md=bb[3]-bb[1], mA=mw/Math.max(md,1e-6), cands=[], i;
  [o.th, o.th+Math.PI/2].forEach(function(t,k){ var along=k===0?o.a:o.b, across=k===0?o.b:o.a; cands.push({phi:t, w:along, d:across}); cands.push({phi:t+Math.PI, w:along, d:across}); });
  cands.forEach(function(c){ var fx=-Math.sin(c.phi), fy=Math.cos(c.phi), bA=c.w/Math.max(c.d,1e-6);                     /* the front normal: R(phi)(0,1) */
    c.sx=c.w/mw; c.sy=c.d/md; c.score=-Math.abs(Math.log(bA/mA))*3;                                                         /* plan aspect first */
    var fb=RLM_FRONT[key]; if(fb!=null){ var bx=Math.sin(fb*Math.PI/180), by=-Math.cos(fb*Math.PI/180); c.score+=(fx*bx+fy*by)*1.2; }    /* compass: east +x, south +y */
    else if(roadW) c.score+=roadW(fx,fy,c.d/2)*.06;
    c.sx=Math.max(RLM_CLAMP[0],Math.min(RLM_CLAMP[1],c.sx)); c.sy=Math.max(RLM_CLAMP[0],Math.min(RLM_CLAMP[1],c.sy)); });
  cands.sort(function(p,q){ return q.score-p.score; }); return cands[0]; }
/* the local model array placed: about the plan centre, stretched (sx, sy), turned by phi, moved to (cx, cy) (all world units) */
function rlmXform(a, bb, f, cx, cy){
  var n=a.length, o=new Float32Array(n), mx=(bb[0]+bb[2])/2, my=(bb[1]+bb[3])/2, c=Math.cos(f.phi), s=Math.sin(f.phi), sx=f.sx, sy=f.sy, i;
  for(i=0;i<n;i+=10){ var lx=(a[i]-mx)*sx, ly=(a[i+1]-my)*sy, nx=a[i+3]/sx, ny=a[i+4]/sy, nz=a[i+5], nl=Math.sqrt(nx*nx+ny*ny+nz*nz)||1; nx/=nl; ny/=nl; nz/=nl;
    o[i]=cx+lx*c-ly*s; o[i+1]=cy+lx*s+ly*c; o[i+2]=a[i+2]; o[i+3]=nx*c-ny*s; o[i+4]=nx*s+ny*c; o[i+5]=nz;
    var u=a[i+6]; if(Math.abs(a[i+5])<.6){ var hx=Math.abs(a[i+4]), hy=Math.abs(a[i+3]), hl=(hx+hy)||1; u*=(hx*sx+hy*sy)/hl; }        /* a wall's u runs along its face: stretched with it */
    o[i+6]=u; o[i+7]=a[i+7]; o[i+8]=a[i+8]; o[i+9]=a[i+9]; }
  return o; }
function rlmRoadW(cx, cy){ return function(fx,fy,half){ var x=cx/K+fx*(half/K+14), y=cy/K+fy*(half/K+14), nr=(typeof rlNear==='function')?rlNear(x,y,30,false):[]; if(!nr.length) return 0; var c=RCLS[nr[0].f[0]]; return (c?c[0]:6)*(1-nr[0].d/40); }; }
function realLandmarks(W){
  if(!RLM.on || typeof lmBuildReal!=='function') return; var L=rlmLandmarks(); if(!L.length) return; var S=W.solids, byKey={}, used={}, out=[];
  S.forEach(function(s){ if(s.kind!=='b'||!s.nm||s.part) return; var k=s._lk; if(k==null){ k=lmKey(s.nm); RLM_ALIAS.forEach(function(a){ if(a[0].test(s.nm)) k=a[1]; }); s._lk=k; } if(k==='gen'||!LMT[k]||RLM_BAD.test(s.nm)) return; (byKey[k]||(byKey[k]=[])).push(s); });
  L.forEach(function(q){ var c=byKey[q.key]; if(!c) return; var best=null, bs=1e18, lim=RLM_NEAR[q.key]||900;
    c.forEach(function(s){ if(used[s.cx+','+s.cy]) return; var d=Math.hypot(s.cx/K-q.x,s.cy/K-q.y); if(d>lim) return; var sc=d-(s.wd?400:0)-(String(s.nm).toLowerCase()===String(q.l.n).toLowerCase()?600:0); if(sc<bs){ bs=sc; best=s; } });
    if(!best) return; used[best.cx+','+best.cy]=1;
    try{ var rec=rlmPlace(W, q, best); if(rec) out.push(rec); }catch(e){ if(window.console&&console.warn) console.warn('real landmark',q.l.n,e&&e.message); } });
  W.real.lm=out; }
function rlmPlace(W, q, s){
  var S=W.solids, ring=s.ring, tgt=s, parts=[], i;
  S.forEach(function(p){ if(p.kind==='b' && p.part && rlmIn(ring,p.cx,p.cy)) parts.push(p); });
  if(RLM_PART[q.key] && parts.length){ var big=null, ba=0; parts.forEach(function(p){ var a=rlmArea(p.ring); if(a>ba){ ba=a; big=p; } }); if(big && ba>=rlmArea(ring)*.4) tgt=big; }
  var ob=rlmOBB(tgt.ring); if(!ob || ob.a<4 || ob.b<4) return null;
  var ck=q.l.n+'|'+Math.round(ob.cx)+','+Math.round(ob.cy)+','+Math.round(ob.a)+','+Math.round(ob.b), rec=RLM.cache[ck];
  if(rec===undefined){ rec=null; var m=lmBuildReal(q.l, q.key);
    if(m && m.a.length){ var f=rlmFit(m.bb, ob, q.key, rlmRoadW(ob.cx,ob.cy)), a=rlmXform(m.a, m.bb, f, ob.cx, ob.cy), c=Math.cos(f.phi), sn=Math.sin(f.phi), mx=(m.bb[0]+m.bb[2])/2, my=(m.bb[1]+m.bb[3])/2;
      var fps=m.fp.map(function(fp){ var r=[]; for(var j=0;j<fp.r.length;j+=2){ var lx=(fp.r[j]-mx)*f.sx, ly=(fp.r[j+1]-my)*f.sy; r.push(ob.cx+lx*c-ly*sn, ob.cy+lx*sn+ly*c); } return r; });
      rec={a:a, fps:fps, f:f}; }
    RLM.cache[ck]=rec; }
  if(!rec) return null;
  /* the plain extrusions go: the outline, the parts in the target, anything standing inside the model's own footprint */
  s.nodraw=true; s.lmReal=q.l.n; var nh=1;
  S.forEach(function(p){ if(p===s||p.kind!=='b'||p.nodraw) return; var hit=(tgt===s)?(p.part&&rlmIn(ring,p.cx,p.cy)):(p===tgt||(p.part&&rlmIn(tgt.ring,p.cx,p.cy)));
    if(!hit) for(i=0;i<rec.fps.length&&!hit;i++) if(rlmIn(rec.fps[i],p.cx,p.cy)) hit=true;
    if(hit){ p.nodraw=true; p.lmReal=q.l.n; p.door=null; nh++; } });
  W.meshes.push({a:rec.a, id:'rlm:'+q.l.n});
  return {n:q.l.n, key:q.key, osm:s.nm, part:tgt!==s, deg:Math.round((Math.atan2(-Math.sin(rec.f.phi),-Math.cos(rec.f.phi))*180/Math.PI+360)%360), sx:+rec.f.sx.toFixed(2), sy:+rec.f.sy.toFixed(2), w:Math.round(ob.a/K), d:Math.round(ob.b/K), hidden:nh}; }
REAL.lm={place:realLandmarks, obb:rlmOBB, fit:rlmFit, xform:rlmXform, cfg:RLM, front:RLM_FRONT};
"""
