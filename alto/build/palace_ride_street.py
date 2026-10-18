"""Real-geometry first-person ride, phase 0 spike: the world around the camera built from REAL footprints and streets.

gatherReal(Xp, Yp) takes a camera in PAGE px, unmaps it to the real frame (palace_ride_real.py), and builds a W like palace_ride_b.gatherWorld:
W.solids (OSM buildings extruded to height, flat roofs; the user's node lots unmapped corner by corner, any real footprint overlapping a lot
cleared), W.tiles (a ground slab and the sidewalks), W.roads (OSM highway ways as ribbons by class), W.dashes (centre lines). Data comes from
window._ALTO_STREET (hosted, 400 m chunks in the real-px frame, by the data agent) or, until it lands, a test blob via _palRide.real.load(blob).
Without either, REAL.on() is false and the ride keeps today's lattice world.

Blob (test and, to be agreed, hosted): {"b": [[h, x0,y0,x1,y1,...], ...], "r": [[cls, x0,y0,x1,y1,...], ...]} in real px (metres).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

JS_STREET = r"""
/* ── the real street world. Coordinates in the WORLD are real metres x K (K = 1.3 map units per metre, UM in palace_ride_mesh.py), so the
   renderer's own constants (eye height, near/far, fog, mesh builders, vehicle speeds) mean what they always meant ── */
var K=UM; REAL.K=K; REAL.metersPerUnit=1/K;
var RCLS={motorway:[26,.5],motorway_link:[12,.5],trunk:[22,.5],trunk_link:[11,.5],primary:[17,.45],primary_link:[10,.4],secondary:[14,.4],secondary_link:[9,.4],tertiary:[12,.35],tertiary_link:[8,.3],
  residential:[9.5,.3],unclassified:[9,.3],living_street:[8,.2],service:[5,.1],pedestrian:[6,0],footway:[2.4,0],path:[2,0],cycleway:[2.6,0],steps:[2,0],track:[4,0]};
/* blob: {b:[[h, x0,y0,...]], r:[[cls, x0,y0,...]], rn:[name per r]} in real px (metres). A road way is indexed by every 400 m cell it touches. */
REAL.load=function(blob){ var C=REAL.cell, ch={}; REAL.nB=0; REAL.nR=0; REAL.ways=[];
  function cellOf(kind,f,x,y){ var k=Math.floor(x/C)+','+Math.floor(y/C); var c=ch[k]||(ch[k]={b:[],r:[]}); if(c[kind].indexOf(f)<0) c[kind].push(f); }
  (blob.b||[]).forEach(function(f){ cellOf('b',f,f[1],f[2]); REAL.nB++; });
  (blob.r||[]).forEach(function(f,wi){ f.n=(blob.rn&&blob.rn[wi])||''; f.wid=wi; REAL.ways.push(f); for(var i=1;i+1<f.length;i+=2) cellOf('r',f,f[i],f[i+1]); REAL.nR++; });
  REAL.trees=blob.t||[]; REAL.furn=blob.f||[]; REAL.pois=blob.p||[]; REAL.poiG=null; REAL.tf=null;
  REAL.chunks=ch; REAL.on=true; REAL.segIdx=null; return {b:REAL.nB, r:REAL.nR, t:REAL.trees.length, f:REAL.furn.length}; };
/* ── the hosted street data (window._palStreet, palace_street_js.py) -> the blob above, in real px (map px, y down). Needs the shards under the points loaded:
   REAL.prepare(points, r) fetches them (a Promise) and loads the blob; without _palStreet (or a manifest) it resolves false and the ride keeps today's world. ── */
REAL.street=function(){ return !!(window._palStreet && window._palStreet.ready && window._palStreet.ready()); };
REAL.fromStreet=function(pts, r){ var S=window._palStreet, seenO=new Set(), b=[], rr=[], rn=[], t=[], f=[], po=[];
  function mp(a){ var o=[]; for(var i=0;i<a.length;i++){ var m=S.toMap(a[i][0],a[i][1],1); o.push(m[0],m[1]); } return o; }
  pts.forEach(function(q){ var Hm=S.toMap(0,0,1)[1], X=q[0], Y=Hm-q[1], N=S.near(X,Y,r,'brtfp');
    N.b.forEach(function(d){ if(seenO.has(d)) return; seenO.add(d); var g=mp(d.ring); var a=[d.hm||0].concat(g); a.col=d.colour; a.mat=d.material; a.sf=d.storefront; a.rs=d.rs; a.rc=d.rc; a.mh=d.mhm||0; a.part=(d.k||'').indexOf('p:')===0; b.push(a); });
    N.r.forEach(function(d){ if(seenO.has(d)) return; seenO.add(d); var g=mp(d.line), a=[d.hw||'residential'].concat(g); a.wd=d.wd?d.wd*.1:0; a.br=d.br; a.tn=d.tn; rr.push(a); rn.push(d.nm||''); });
    N.t.forEach(function(d){ if(seenO.has(d)) return; seenO.add(d); var m=S.toMap(d.x,d.y,1); t.push([m[0],m[1],d.sp||'',d.lf||'']); });
    N.f.forEach(function(d){ if(seenO.has(d)) return; seenO.add(d); var m=S.toMap(d.x,d.y,1); f.push([m[0],m[1],d.kind||'',d.dir==null?-1:d.dir]); });
    (N.p||[]).forEach(function(d){ if(seenO.has(d)||!d.name) return; seenO.add(d); var m=S.toMap(d.x,d.y,1); po.push([m[0],m[1],d.name,d.cat||'']); }); });
  return {b:b, r:rr, rn:rn, t:t, f:f, p:po}; };
REAL.prepare=function(pts, r){ r=r||520; if(!REAL.street()) return Promise.resolve(false); var S=window._palStreet, Hm=S.toMap(0,0,1)[1];
  return Promise.all(pts.map(function(q){ return S.need(q[0],Hm-q[1],r); })).then(function(){ REAL.load(REAL.fromStreet(pts,r)); REAL.src='street'; REAL.have=pts.map(function(q){ return [q[0],q[1],r]; }); return true; }); };
REAL.prepareLeg=function(D){ var pts=[], o={x:0,y:0,k:0}, p={x:0,y:0}, last=null; for(var s=0;s<=D.L+1;s+=60){ pathAt(D,Math.min(s,D.L),p); realOf(p.x,p.y,o); if(!last||Math.hypot(o.x-last[0],o.y-last[1])>350){ pts.push([o.x,o.y]); last=[o.x,o.y]; } } return REAL.prepare(pts,520); };
REAL.isOn=function(){ return !!(REAL.on && rlInit() && REAL.chunks); };
REAL.legOn=function(D){ return !!(REAL.isOn() && D && (D.real || (D.real===undefined && REAL.match(D)))); };    /* this leg is walked in the real frame (matched and in bounds) */
function rlNorm(n){ if(!n) return ''; n=String(n).toLowerCase().replace(/\b(north|south|east|west|n|s|e|w)\b\.?/g,' ').replace(/\b(street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|place|pl|lane|ln|way|court|ct|terrace|ter|parkway|pkwy)\b\.?/g,' ').replace(/(\d+)(st|nd|rd|th)\b/g,'$1').replace(/[^a-z0-9]+/g,' ').trim(); return n; }
/* a spatial index of every road segment (50 m cells) */
function rlSegs(){ if(REAL.segIdx) return REAL.segIdx; var I={}, G=50; REAL.ways.forEach(function(f){ var nn=rlNorm(f.n);
  for(var a=1;a+3<f.length;a+=2){ var sg={ax:f[a],ay:f[a+1],bx:f[a+2],by:f[a+3],f:f,nn:nn}; var x0=Math.min(sg.ax,sg.bx), x1=Math.max(sg.ax,sg.bx), y0=Math.min(sg.ay,sg.by), y1=Math.max(sg.ay,sg.by);
    for(var i=Math.floor(x0/G);i<=Math.floor(x1/G);i++) for(var j=Math.floor(y0/G);j<=Math.floor(y1/G);j++){ var k=i+','+j; (I[k]||(I[k]=[])).push(sg); } } }); REAL.segIdx=I; return I; }
function rlNear(x,y,maxd,any){ var I=rlSegs(), G=50, ci=Math.floor(x/G), cj=Math.floor(y/G), rr=Math.ceil(maxd/G), out=[], seen=[], m2=maxd*maxd;
  for(var i=ci-rr;i<=ci+rr;i++) for(var j=cj-rr;j<=cj+rr;j++){ var L=I[i+','+j]; if(!L) continue; for(var q=0;q<L.length;q++){ var sg=L[q]; if(seen.indexOf(sg)>=0) continue; seen.push(sg);
    var c=RCLS[sg.f[0]]; if(!any && (!c||c[0]<8)) continue; var dx=sg.bx-sg.ax, dy=sg.by-sg.ay, L2=dx*dx+dy*dy||1, t=Math.max(0,Math.min(1,((x-sg.ax)*dx+(y-sg.ay)*dy)/L2)), px=sg.ax+t*dx, py=sg.ay+t*dy, d2=(px-x)*(px-x)+(py-y)*(py-y);
    if(d2<=m2) out.push({x:px,y:py,d:Math.sqrt(d2),ang:Math.atan2(dy,dx),f:sg.f,nn:sg.nn,wid:sg.f.wid,sg:sg}); } }
  out.sort(function(a,b){ return a.d-b.d; }); return out; }
/* the nearest road (or, with `any`, footpath too) centre line within maxd m of a real point, heading on its side */
REAL.snap=function(x,y,h,maxd,any){ var c=rlNear(x,y,maxd||40,any); if(!c.length) return null; var b=c[0], a=b.ang; if(h!=null && Math.cos(a-h)<0) a+=Math.PI; return {x:b.x,y:b.y,h:a,d:b.d,cls:b.f[0],name:b.f.n}; };
/* roam: where a free walk starts (page point -> real, snapped to a road or sidewalk) and what page point a real position is (the exact forward map) */
REAL.enter=function(X,Y,hp,maxd){ var r=realOf(X,Y,{x:0,y:0,k:0}), yaw=(hp==null)?null:realHeading(X,Y,hp), s=REAL.snap(r.x,r.y,yaw,maxd||40,true), x=s?s.x:r.x, y=s?s.y:r.y, h=s?s.h:(yaw==null?0:yaw), pg=pageOf(x,y,{x:0,y:0,k:0});
  return {x:x*K, y:y*K, h:h, X:pg.x, Y:pg.y, dom:r.k, snapped:!!s, d:s?s.d:0, cls:s&&s.cls, name:s&&s.name}; };
REAL.exit=function(wx,wy){ var p=pageOf(wx/K,wy/K,{x:0,y:0,k:0}); return [p.x,p.y,p.k]; };
REAL.toReal=function(X,Y){ var o=realOf(X,Y,{x:0,y:0,k:0}); return [o.x,o.y,o.k]; };
REAL.toPage=function(x,y){ var o=pageOf(x,y,{x:0,y:0,k:0}); return [o.x,o.y,o.k]; };

/* ── the real-frame route of a ride/roam path: D.real. Each page sample is unmapped, then map-matched (Viterbi) onto real street segments.
   Seams: where two consecutive unmapped samples are > CUT m apart (a domain seam, the lattices disagree by 150-1900 m) the route is CUT: each piece is matched on its own,
   D.real.cuts lists the sample indices, and the ride dissolves across a cut (the existing dissolve) instead of teleporting along an invented path. ── */
var PGRID=null;
function pageNameAt(X,Y){ if(!PGRID){ PGRID={}; var G=120; (E.M.streets||[]).forEach(function(st){ if(st.t||!st.n) return; var p=st.p||[], nn=rlNorm(st.n);
    for(var i=0;i+3<p.length;i+=2){ var sg=[p[i],p[i+1],p[i+2],p[i+3],nn]; var x0=Math.min(sg[0],sg[2]), x1=Math.max(sg[0],sg[2]), y0=Math.min(sg[1],sg[3]), y1=Math.max(sg[1],sg[3]);
      for(var a=Math.floor(x0/G);a<=Math.floor(x1/G);a++) for(var b=Math.floor(y0/G);b<=Math.floor(y1/G);b++){ (PGRID[a+','+b]||(PGRID[a+','+b]=[])).push(sg); } } }); }
  var G2=120, best=1e9, nm='', ci=Math.floor(X/G2), cj=Math.floor(Y/G2); for(var a=ci-1;a<=ci+1;a++) for(var b=cj-1;b<=cj+1;b++){ var L=PGRID[a+','+b]; if(!L) continue; for(var q=0;q<L.length;q++){ var g=L[q], dx=g[2]-g[0], dy=g[3]-g[1], L2=dx*dx+dy*dy||1,
      t=Math.max(0,Math.min(1,((X-g[0])*dx+(Y-g[1])*dy)/L2)), d=Math.hypot(g[0]+t*dx-X,g[1]+t*dy-Y); if(d<best){ best=d; nm=g[4]; } } }
  return best<30?nm:''; }
REAL.CUT=80; REAL.SPACING=30; REAL.SNAP=40;
REAL.match=function(D){
  if(!REAL.isOn()||!D||!D.L) return null; if(REAL.legInBounds && !REAL.legInBounds(D).ok){ D.real=null; D.oob=true; return null; }    /* a leg that leaves the region keeps today's lattice world */
  var sp=REAL.SPACING, n=Math.max(2,Math.round(D.L/sp)+1), o={x:0,y:0,k:0}, raw=[], i, p={x:0,y:0}, ps=[];
  for(i=0;i<n;i++){ var s=Math.min(D.L,i*D.L/(n-1)); pathAt(D,s,p); realOf(p.x,p.y,o); raw.push({x:o.x,y:o.y,k:o.k,s:s,nm:pageNameAt(p.x,p.y)}); }
  for(i=0;i<n;i++){ var a=raw[Math.max(0,i-1)], b=raw[Math.min(n-1,i+1)]; raw[i].h=Math.atan2(b.y-a.y,b.x-a.x); }
  var steps=[]; for(i=1;i<n;i++) steps.push(Math.hypot(raw[i].x-raw[i-1].x,raw[i].y-raw[i-1].y)); steps.sort(function(a,b){ return a-b; }); var med=steps[steps.length>>1]||10, cuts=[];
  for(i=1;i<n;i++) if(Math.hypot(raw[i].x-raw[i-1].x,raw[i].y-raw[i-1].y)>Math.max(REAL.CUT,6*med)) cuts.push(i);
  var cand=raw.map(function(r){ var c=rlNear(r.x,r.y,REAL.SNAP,true).slice(0,6), seenW={}, out=[]; c.forEach(function(q){ if(seenW[q.wid]) return; seenW[q.wid]=1;
      var hd=Math.abs(Math.cos(q.ang-r.h)), nmOK=r.nm&&q.nn?(r.nm===q.nn?-.8:.25):0; out.push({x:q.x,y:q.y,wid:q.wid,cost:q.d/30+nmOK+.7*(1-hd)+(RCLS[q.f[0]]&&RCLS[q.f[0]][0]<4?.35:0),raw:0}); });
    out.push({x:r.x,y:r.y,wid:-1,cost:1.3,raw:1}); return out; });
  var bounds=[0].concat(cuts, [n]), pick=new Array(n);
  for(var pi=0;pi+1<bounds.length;pi++){ var a0=bounds[pi], a1=bounds[pi+1], V=[], B=[];
    for(i=a0;i<a1;i++){ var cs=cand[i], v=[], bp=[]; for(var c=0;c<cs.length;c++){ if(i===a0){ v.push(cs[c].cost); bp.push(-1); continue; }
        var best=1e18, bi=0, st=Math.hypot(raw[i].x-raw[i-1].x,raw[i].y-raw[i-1].y); for(var q=0;q<cand[i-1].length;q++){ var pc=cand[i-1][q], dp=Math.hypot(cs[c].x-pc.x,cs[c].y-pc.y);
          var t=V[V.length-1][q]+.8*Math.abs(dp-st)/Math.max(st,5)+(pc.wid!==cs[c].wid?.25:0)+(pc.raw||cs[c].raw?.3:0); if(t<best){ best=t; bi=q; } } v.push(best+cs[c].cost); bp.push(bi); }
      V.push(v); B.push(bp); }
    var last=V[V.length-1], bj=0; for(var z=1;z<last.length;z++) if(last[z]<last[bj]) bj=z;
    for(i=a1-1;i>=a0;i--){ pick[i]=cand[i][bj]; bj=B[i-a0][bj]; if(bj<0) bj=0; } }
  /* smooth ~60 m inside each piece, then heading from the tangent */
  var X=[],Y=[]; for(i=0;i<n;i++){ X.push(pick[i].x); Y.push(pick[i].y); }
  var half=Math.max(1,Math.round(30/Math.max(med,6))), SX=[],SY=[];
  for(var pj=0;pj+1<bounds.length;pj++){ for(i=bounds[pj];i<bounds[pj+1];i++){ var lo=Math.max(bounds[pj],i-half), hi=Math.min(bounds[pj+1]-1,i+half), sx=0,sy=0,sw=0; for(var u=lo;u<=hi;u++){ var w=1-Math.abs(u-i)/(half+1); sx+=X[u]*w; sy+=Y[u]*w; sw+=w; } SX[i]=sx/sw; SY[i]=sy/sw; } }
  var R_={X:[],Y:[],H:[],S:[],n:n,cuts:cuts,Lp:D.L,Lr:0,dev:[],raw:raw.length,rawMed:med,matched:0,names:0}, Lr=0, dev=[];
  for(i=0;i<n;i++){ R_.X.push(SX[i]*K); R_.Y.push(SY[i]*K); R_.S.push(raw[i].s); if(pick[i].raw===0) R_.matched++; if(raw[i].nm&&cand[i][0]) R_.names++; dev.push(Math.hypot(SX[i]-raw[i].x,SY[i]-raw[i].y)); }
  for(i=0;i<n;i++){ var cutBefore=cuts.indexOf(i)>=0, lo2=i, hi2=i; for(var w2=1;w2<=2;w2++){ if(hi2+1<n && cuts.indexOf(hi2+1)<0) hi2++; if(lo2>0 && cuts.indexOf(lo2)<0) lo2--; }
    R_.H.push(hi2>lo2?Math.atan2(SY[hi2]-SY[lo2],SX[hi2]-SX[lo2]):raw[i].h); if(i>0 && !cutBefore) Lr+=Math.hypot(R_.X[i]-R_.X[i-1],R_.Y[i]-R_.Y[i-1]); }
  R_.Lr=Lr; dev.sort(function(a,b){ return a-b; }); R_.devMed=dev[dev.length>>1]; R_.devMax=dev[dev.length-1]; R_.scale=Lr/Math.max(1,D.L);    /* world units of real route per page px: vmax*scale is what the viewer sees */
  D.real=R_; return R_; };
/* the real position / heading at the page arclength s (the ride's own parameter); across a cut it jumps to the nearer side (the caller dissolves) */
REAL.pathAt=function(D,s,out){ var R_=D.real; if(!R_) return null; var n=R_.n, f=Math.max(0,Math.min(n-1,s/R_.Lp*(n-1))), i=Math.min(n-2,Math.floor(f)), t=f-i; if(R_.cuts.indexOf(i+1)>=0) t=t<.5?0:1;
  out.x=R_.X[i]+(R_.X[i+1]-R_.X[i])*t; out.y=R_.Y[i]+(R_.Y[i+1]-R_.Y[i])*t; var h0=R_.H[i], h1=R_.H[i+1], dh=Math.atan2(Math.sin(h1-h0),Math.cos(h1-h0)); out.h=h0+dh*t; return out; };

/* ── roofs: gable / hip / flat with a parapet, from the footprint's oriented box ── */
function obb(ring){ var n=ring.length/2, bi=0, bl=-1, i; for(i=0;i<n;i++){ var j=(i+1)%n, l=Math.hypot(ring[2*j]-ring[2*i],ring[2*j+1]-ring[2*i+1]); if(l>bl){ bl=l; bi=i; } }
  var j2=(bi+1)%n, th=Math.atan2(ring[2*j2+1]-ring[2*bi+1],ring[2*j2]-ring[2*bi]), c=Math.cos(th), s=Math.sin(th), u0=1e9,u1=-1e9,v0=1e9,v1=-1e9;
  for(i=0;i<n;i++){ var u=ring[2*i]*c+ring[2*i+1]*s, v=-ring[2*i]*s+ring[2*i+1]*c; u0=Math.min(u0,u); u1=Math.max(u1,u); v0=Math.min(v0,v); v1=Math.max(v1,v); }
  return {c:c,s:s,u0:u0,u1:u1,v0:v0,v1:v1,area:(u1-u0)*(v1-v0)}; }
function ringArea(ring){ var n=ring.length/2, a=0; for(var i=0;i<n;i++){ var j=(i+1)%n; a+=ring[2*i]*ring[2*j+1]-ring[2*j]*ring[2*i+1]; } return Math.abs(a)/2; }
function triOut(m,A,B,C,hint,mat,tint){ var ux=B[0]-A[0],uy=B[1]-A[1],uz=B[2]-A[2],vx=C[0]-A[0],vy=C[1]-A[1],vz=C[2]-A[2], nx=uy*vz-uz*vy, ny=uz*vx-ux*vz, nz=ux*vy-uy*vx;   /* right-hand cross must point INTO the surface (mesh format) */
  if(nx*hint[0]+ny*hint[1]+nz*hint[2]>0){ var T=B; B=C; C=T; nx=-nx; ny=-ny; nz=-nz; } var l=Math.sqrt(nx*nx+ny*ny+nz*nz)||1;
  MB.tri(m,A,B,C,-nx/l,-ny/l,-nz/l,mat,tint,[A[0]/K,A[1]/K],[B[0]/K,B[1]/K],[C[0]/K,C[1]/K]); }
function quadOut(m,A,B,C,D_,hint,mat,tint){ triOut(m,A,B,C,hint,mat,tint); triOut(m,A,C,D_,hint,mat,tint); }
/* ring in world units, eave height z (units). kind: 0 flat+parapet, 1 gable, 2 hip. Appends to mesh m. */
function roofOf(m, ring, z, kind, tint){
  var ob=obb(ring), n=ring.length/2, i, c=ob.c, s=ob.s;
  function W3(u,v,zz){ return [u*c-v*s, u*s+v*c, zz]; }
  if(kind===0){ var par=.7*K, o=MB.ringOut(ring), no=o.length/2; for(i=0;i<no;i++){ var j=(i+1)%no; MB.wall(m,o[2*i],o[2*i+1],o[2*j],o[2*j+1],z,z+par,MAT.concrete,tint,0); MB.wall(m,o[2*j],o[2*j+1],o[2*i],o[2*i+1],z,z+par,MAT.concrete,tint,0); } return; }
  var w=ob.u1-ob.u0, d=ob.v1-ob.v0, along=w>=d, ridgeZ=z+Math.max(1.0*K,Math.min(w,d)*.3), mat=(tint>.5?MAT.tile:MAT.roof), um=(ob.u0+ob.u1)/2, vm=(ob.v0+ob.v1)/2, ctr=W3(um,vm,z);
  var P=[W3(ob.u0,ob.v0,z),W3(ob.u1,ob.v0,z),W3(ob.u1,ob.v1,z),W3(ob.u0,ob.v1,z)], R1,R2, e=kind===2?Math.min(w,d)*.4:0;
  if(along){ R1=W3(ob.u0+e,vm,ridgeZ); R2=W3(ob.u1-e,vm,ridgeZ); } else { R1=W3(um,ob.v0+e,ridgeZ); R2=W3(um,ob.v1-e,ridgeZ); }
  function hint(F){ return [F[0]-ctr[0],F[1]-ctr[1],.6*K+ (F[2]-z)*0+1]; }
  if(along){ quadOut(m,P[0],P[1],R2,R1,[ (P[0][0]+P[1][0])/2-ctr[0], (P[0][1]+P[1][1])/2-ctr[1], 1*K ],mat,tint); quadOut(m,P[3],P[2],R2,R1,[ (P[3][0]+P[2][0])/2-ctr[0], (P[3][1]+P[2][1])/2-ctr[1], 1*K ],mat,tint);
    triOut(m,P[0],P[3],R1,[P[0][0]-ctr[0],P[0][1]-ctr[1],kind===2?1*K:0],kind===2?mat:MAT.brick,tint); triOut(m,P[1],P[2],R2,[P[1][0]-ctr[0],P[1][1]-ctr[1],kind===2?1*K:0],kind===2?mat:MAT.brick,tint); }
  else { quadOut(m,P[0],P[3],R2,R1,[ (P[0][0]+P[3][0])/2-ctr[0], (P[0][1]+P[3][1])/2-ctr[1], 1*K ],mat,tint); quadOut(m,P[1],P[2],R2,R1,[ (P[1][0]+P[2][0])/2-ctr[0], (P[1][1]+P[2][1])/2-ctr[1], 1*K ],mat,tint);
    triOut(m,P[0],P[1],R1,[ (P[0][0]+P[1][0])/2-ctr[0], (P[0][1]+P[1][1])/2-ctr[1], kind===2?1*K:0],kind===2?mat:MAT.brick,tint); triOut(m,P[3],P[2],R2,[ (P[3][0]+P[2][0])/2-ctr[0], (P[3][1]+P[2][1])/2-ctr[1], kind===2?1*K:0],kind===2?mat:MAT.brick,tint); }
  if(kind===2){ /* hip: the two end faces are the hip triangles already; with e>0 they are trapezoid ends: close them with the triangles above (ridge ends at R1/R2) */ } }
function rlPolyHit(q, ring, x0,y0,x1,y1){          /* a real footprint against a lot's corner polygon q (metres): centre, a vertex of it inside q, or a lot corner inside it */
  var n=ring.length/2, i;
  if(x1<q.x0||x0>q.x1||y1<q.y0||y0>q.y1) return false;
  var cx=(x0+x1)/2, cy=(y0+y1)/2; if(rlIn(q.p,cx,cy)) return true;
  for(i=0;i<n;i++) if(rlIn(q.p,ring[2*i],ring[2*i+1])) return true;
  var rr=[]; for(i=0;i<n;i++) rr.push([ring[2*i],ring[2*i+1]]); for(i=0;i<q.p.length;i++) if(rlIn(rr,q.p[i][0],q.p[i][1])) return true;
  return false; }
function rlInF(ring,x,y){ var c=false, n=ring.length/2; for(var i=0,j=n-1;i<n;j=i++){ var ax=ring[2*i], ay=ring[2*i+1], bx=ring[2*j], by=ring[2*j+1]; if((ay>y)!==(by>y) && x<ax+(y-ay)*(bx-ax)/(by-ay)) c=!c; } return c; }
/* a point grid for "is there one of these within r m" */
function rlPG(pts,G){ var g={}; pts.forEach(function(p){ var k=Math.floor(p[0]/G)+','+Math.floor(p[1]/G); (g[k]||(g[k]=[])).push(p); }); g.G=G; return g; }
function rlPGnear(g,x,y,r){ var G=g.G, i0=Math.floor((x-r)/G), i1=Math.floor((x+r)/G), j0=Math.floor((y-r)/G), j1=Math.floor((y+r)/G); for(var i=i0;i<=i1;i++) for(var j=j0;j<=j1;j++){ var l=g[i+','+j]; if(l) for(var q=0;q<l.length;q++) if(Math.hypot(l[q][0]-x,l[q][1]-y)<=r) return true; } return false; }
/* a lot's ring in page px: a claimed footprint (palace_claim L[5], offsets from the centre) when there is one, else the turned rectangle */
function rlLotRing(L){ if(L[5]&&L[5].length>=3){ var o=[]; L[5].forEach(function(q){ o.push(L[0]+q[0], L[1]+q[1]); }); return o; } return turnedRing(L); }
/* the door of a node building in the real world: the face of the lot (ring in world units) whose front, 14 units out, is nearest a real street */
function rlDoor(ring, id){ var n=ring.length/2, cx=0, cy=0, i, best=null; for(i=0;i<n;i++){ cx+=ring[2*i]/n; cy+=ring[2*i+1]/n; }
  for(i=0;i<n;i++){ var j=(i+1)%n, ax=ring[2*i], ay=ring[2*i+1], bx=ring[2*j], by=ring[2*j+1], ex=bx-ax, ey=by-ay, l=Math.hypot(ex,ey); if(l<8) continue;
    var mx=(ax+bx)/2, my=(ay+by)/2, nx=ey/l, ny=-ex/l; if(nx*(mx-cx)+ny*(my-cy)<0){ nx=-nx; ny=-ny; }
    var nr=rlNear((mx+nx*14)/UM,(my+ny*14)/UM,80,true)[0], sc=(nr?nr.d*UM:1e4)-l*.02; if(!best||sc<best.sc) best={sc:sc,x:mx,y:my,nx:nx,ny:ny,w:l}; }
  return best?{x:best.x,y:best.y,nx:best.nx,ny:best.ny,w:best.w,id:id,name:E.name(id)}:null; }
/* where a named shop is: the POI nearest the building's street-facing wall within 22 m (real px) */
function rlPoiNear(x,y,r){ var P=REAL.pois||[], b=null, bd=r*r; for(var i=0;i<P.length;i++){ var dx=P[i][0]-x, dy=P[i][1]-y, d=dx*dx+dy*dy; if(d<bd){ bd=d; b=P[i]; } } return b; }
/* the street-facing wall of a storefront building (ring in real px, n points): the shopfront {x,y,nx,ny,len (world units), name, hue} on its middle */
var RL_CIVIC=/worship|school|college|university|parking|hospital|library|townhall|courthouse|grave|monastery|kindergarten|place_of|community_centre|police|fire_station|post_office|bank=|public_building|museum|theatre|arts_centre|clinic|doctors|dentist|social_facility|shelter|toilets|bus_station|fuel|charging/;
function rlShopFace(ring,n){ var cx=0, cy=0, i, best=null; for(i=0;i<n;i++){ cx+=ring[2*i]/n; cy+=ring[2*i+1]/n; }
  for(i=0;i<n;i++){ var j=(i+1)%n, ax=ring[2*i], ay=ring[2*i+1], bx=ring[2*j], by=ring[2*j+1], ex=bx-ax, ey=by-ay, l=Math.hypot(ex,ey); if(l<4.5) continue;
    var mx=(ax+bx)/2, my=(ay+by)/2, nx=ey/l, ny=-ex/l; if(nx*(mx-cx)+ny*(my-cy)<0){ nx=-nx; ny=-ny; }
    var nr=rlNear(mx+nx*6,my+ny*6,40,true)[0], sc=(nr?nr.d:99)-l*.03; if(nr && nr.d<30 && (!best||sc<best.sc)) best={sc:sc,x:mx,y:my,nx:nx,ny:ny,l:l}; }
  if(!best) return null; var po=rlPoiNear(best.x,best.y,22), hs=hashXY(best.x*3.1,best.y*1.7);
  if(po && RL_CIVIC.test(po[3]||'')) return null;                                  /* a church, school, library... is not a shop: no shop glass, no awning */
  var cat=po?po[3]:'', civic=false;
  return {x:best.x*K, y:best.y*K, nx:best.nx, ny:best.ny, len:best.l*K, name:po&&!civic?po[2]:'', cat:cat, hue:hs}; }
/* ── z-fighting walls. OpenStreetMap draws a building as its outline AND its building:parts, parts share walls, ways are doubled: two solids with a wall on the very same plane facing the same way fight in the
   depth buffer, and the winner changes with every step you take (the whole facade flashes). The street data cannot be fixed here (it is hosted), so the world is made before it is drawn:
     1. an outline that its parts cover (>= 85 % of its footprint, sampled) is not drawn (s.nodraw; it still stops the walker);
     2. where a wall lies on the plane of another solid's wall that faces the same way and is at least as tall (the taller one wins, a tie goes to the earlier one), that stretch of the lower one is not
        drawn (s.hide = [x0,y0,x1,y1, ...], world units; palace_ride_gl.py glSolid cuts the wall there);
     3. two solids of the same height whose footprints overlap would also share a roof plane: the later one's roof is dropped by 12 cm (s.roofDz). ── */
var DD_TOL=.4, DD_MINL=.6, DD_PAR=.06, DD_DROP=.16;
function realDedupe(W){
  var S=W.solids, n=S.length, i, j, k, CG=64, GE={}, GP={}, E=[], t0=performance.now(), nHide=0, nSkip=0, nDrop=0;
  function put(G,key,v){ (G[key]||(G[key]=[])).push(v); }
  function box(s){ if(s._bx) return s._bx; var r=s.ring, x0=1e9,y0=1e9,x1=-1e9,y1=-1e9; for(var q=0;q<r.length;q+=2){ if(r[q]<x0) x0=r[q]; if(r[q]>x1) x1=r[q]; if(r[q+1]<y0) y0=r[q+1]; if(r[q+1]>y1) y1=r[q+1]; } return s._bx=[x0,y0,x1,y1]; }
  function cells(bx,fn){ for(var a=Math.floor(bx[0]/CG);a<=Math.floor(bx[2]/CG);a++) for(var c=Math.floor(bx[1]/CG);c<=Math.floor(bx[3]/CG);c++) fn(a+','+c); }
  var sol=[]; for(i=0;i<n;i++){ var s=S[i]; if(s.kind==='b' && s.ring && s.n>=3) sol.push(i); }
  /* 1: outlines covered by their parts */
  sol.forEach(function(si){ var s=S[si]; if(s.part) return; cells(box(s),function(c){ put(GP,c,si); }); });
  var partsOf=[]; sol.forEach(function(si){ var s=S[si]; if(!s.part) return; partsOf.push(si); });
  if(partsOf.length){ var GQ={}; partsOf.forEach(function(si){ cells(box(S[si]),function(c){ put(GQ,c,si); }); });
    sol.forEach(function(si){ var s=S[si]; if(s.part||s.nodraw) return; var b=box(s), st=Math.max(2.2,Math.min(b[2]-b[0],b[3]-b[1])/10), inn=0, cov=0, x, y;
      for(x=b[0]+st/2;x<b[2];x+=st) for(y=b[1]+st/2;y<b[3];y+=st){ if(!rlInF(s.ring,x,y)) continue; inn++; var L=GQ[Math.floor(x/CG)+','+Math.floor(y/CG)]; if(!L) continue; for(var q=0;q<L.length;q++){ var p=S[L[q]]; if(rlInF(p.ring,x,y)){ cov++; break; } } }
      if(inn>=4 && cov>=inn*.85){ s.nodraw=true; nSkip++; } }); }
  /* 2: coplanar walls (the solids still drawn) */
  sol=sol.filter(function(si){ return !S[si].nodraw; });
  sol.forEach(function(si){ var s=S[si], r=s.ring, m=s.n; for(k=0;k<m;k++){ var l2=(k+1)%m, ax=r[2*k], ay=r[2*k+1], bx=r[2*l2], by=r[2*l2+1], l=Math.hypot(bx-ax,by-ay); if(l<DD_MINL) continue;
      var e={s:si,k:k,ax:ax,ay:ay,bx:bx,by:by,l:l,ux:(bx-ax)/l,uy:(by-ay)/l,nx:s.nx[k],ny:s.ny[k]}; E.push(e);
      for(var gx=Math.floor(Math.min(ax,bx)/CG);gx<=Math.floor(Math.max(ax,bx)/CG);gx++) for(var gy=Math.floor(Math.min(ay,by)/CG);gy<=Math.floor(Math.max(ay,by)/CG);gy++) put(GE,gx+','+gy,e); } });
  E.forEach(function(e){ var si=e.s, a=S[si], seen=[], hz=a.z0||0;
    for(var gx=Math.floor(Math.min(e.ax,e.bx)/CG);gx<=Math.floor(Math.max(e.ax,e.bx)/CG);gx++) for(var gy=Math.floor(Math.min(e.ay,e.by)/CG);gy<=Math.floor(Math.max(e.ay,e.by)/CG);gy++){ var L=GE[gx+','+gy]; if(!L) continue;
      for(var q=0;q<L.length;q++){ var f=L[q]; if(f.s===si||seen.indexOf(f)>=0) continue; seen.push(f); var b=S[f.s];
        if(!((b.h>a.h+.1) || (Math.abs(b.h-a.h)<=.1 && f.s<si))) continue;               /* b covers a: taller, or the same and earlier */
        if((b.z0||0)>hz+.1) continue;
        if(f.nx*e.nx+f.ny*e.ny<.9 || Math.abs(f.ux*e.uy-f.uy*e.ux)>DD_PAR) continue;     /* the same way, parallel */
        var d1=Math.abs((f.ax-e.ax)*e.uy-(f.ay-e.ay)*e.ux), d2=Math.abs((f.bx-e.ax)*e.uy-(f.by-e.ay)*e.ux); if(d1>DD_TOL||d2>DD_TOL) continue;
        var s0=(f.ax-e.ax)*e.ux+(f.ay-e.ay)*e.uy, s1=(f.bx-e.ax)*e.ux+(f.by-e.ay)*e.uy, lo=Math.max(0,Math.min(s0,s1)), hi=Math.min(e.l,Math.max(s0,s1)); if(hi-lo<DD_MINL) continue;
        (a.hide||(a.hide=[])).push(e.ax+e.ux*lo,e.ay+e.uy*lo,e.ax+e.ux*hi,e.ay+e.uy*hi); nHide++; } } });
  /* 3: equal heights over overlapping footprints share a roof plane */
  var GA={}; sol.forEach(function(si){ cells(box(S[si]),function(c){ put(GA,c,si); }); });
  sol.forEach(function(si){ var a=S[si], ba=box(a), seen={}, drop=false; cells(ba,function(c){ if(drop) return; var L=GA[c]; for(var q=0;q<L.length&&!drop;q++){ var sj=L[q]; if(sj>=si||seen[sj]) continue; seen[sj]=1; var b=S[sj]; if(Math.abs(b.h-a.h)>.1) continue;
        var bb=box(b); if(bb[2]<ba[0]||bb[0]>ba[2]||bb[3]<ba[1]||bb[1]>ba[3]) continue; if(rlInF(b.ring,a.cx,a.cy)||rlInF(a.ring,b.cx,b.cy)) drop=true; } });
    if(drop){ a.roofDz=-DD_DROP; nDrop++; } });
  W.real&&(W.real.dedupe={skip:nSkip,hide:nHide,drop:nDrop,ms:performance.now()-t0}); }
function gatherReal(Xp, Yp, R, at){
  R=R||480; var o0=at?{x:at.x,y:at.y,k:at.k||0}:realOf(Xp,Yp,{x:0,y:0,k:0}), cx=o0.x, cy=o0.y, C=REAL.cell, P=E.P, i, k, ci0=Math.floor((cx-R)/C), ci1=Math.floor((cx+R)/C), cj0=Math.floor((cy-R)/C), cj1=Math.floor((cy+R)/C);
  var W={solids:[], tiles:[], parks:[], water:[], roads:[], props:[], poles:[], labels:[], tunn:false, set:{}, scenery:null, meshes:[], movers:[], dashes:[], rivers:[], real:{cx:cx*K,cy:cy*K,dom:o0.k}};
  var lots=[], seen={};
  Object.keys(P.at||{}).forEach(function(id){ if(E.bOf(id)!==id) return; var key=P.at[id]; if(seen[key]) return; seen[key]=1; var L=E.lot(key); if(!L) return;
    var pr=rlLotRing(L), q=[], tmp={x:0,y:0,k:0}, nq=pr.length/2; for(i=0;i<nq;i++){ realOf(pr[2*i],pr[2*i+1],tmp); q.push([tmp.x,tmp.y]); }
    var mx=0,my=0; q.forEach(function(p){ mx+=p[0]/nq; my+=p[1]/nq; }); if(Math.hypot(mx-cx,my-cy)>R+80) return;
    var xs=q.map(function(p){ return p[0]; }), ys=q.map(function(p){ return p[1]; });
    lots.push({id:id, p:q, x0:Math.min.apply(null,xs), x1:Math.max.apply(null,xs), y0:Math.min.apply(null,ys), y1:Math.max.apply(null,ys)}); });
  var cleared=0, kept=0, dk=dark(), roofM=MB.mk(), roofs=[0,0,0];
  if(!glOk()) W.tiles.push({ring:[(cx-R)*K,(cy-R)*K,(cx+R)*K,(cy-R)*K,(cx+R)*K,(cy+R)*K,(cx-R)*K,(cy+R)*K], cx:cx*K, cy:cy*K, r:R*1.5*K});
  var seenR={}, seenB={}, bq=[], procW=[], shops=[];
  for(var ci=ci0-1; ci<=ci1+1; ci++) for(var cj=cj0-1; cj<=cj1+1; cj++){ var ch=REAL.chunks[ci+','+cj]; if(!ch) continue;
    ch.r.forEach(function(f){ if(seenR[f.wid]) return; seenR[f.wid]=1; var w=((f.wd>0?f.wd:(RCLS[f[0]]||[7,.2])[0]))*K, sw=(RCLS[f[0]]||[7,.2])[1];
      for(var a=1;a+3<f.length;a+=2){ var x0=f[a]*K, y0=f[a+1]*K, x1=f[a+2]*K, y1=f[a+3]*K, mx=(x0+x1)/2, my=(y0+y1)/2; if(Math.abs(mx/K-cx)>R||Math.abs(my/K-cy)>R) continue; var l=Math.hypot(x1-x0,y1-y0); if(l<.5) continue;
        if(sw>0){ var nx=-(y1-y0)/l, ny=(x1-x0)/l, off=w/2+1.6*K; [-1,1].forEach(function(sd){ W.tiles.push({ring:strip(x0+nx*off*sd,y0+ny*off*sd,x1+nx*off*sd,y1+ny*off*sd,3.2*K,w*.18), cx:mx+nx*off*sd, cy:my+ny*off*sd, r:l/2+w, sw:1}); }); }
        W.roads.push({x0:x0,y0:y0,x1:x1,y1:y1,w:w,cx:mx,cy:my,r:l/2+w, cls:f[0]});
        if(a===1 && sw>0 && w>=7*K) procW.push(f);
        if(sw>=.3 && w>=9*K && l>30*K){ var ux=(x1-x0)/l, uy=(y1-y0)/l; for(var p=8*K;p<l-8*K;p+=22*K){ var ax=x0+ux*p, ay=y0+uy*p; W.dashes.push({ring:strip(ax,ay,ax+ux*9*K,ay+uy*9*K,.35*K,0), cx:ax, cy:ay}); } } } });
    ch.b.forEach(function(f){ if(seenB[f.bid||(f.bid=f[1]+','+f[2])]) return; seenB[f.bid]=1; var n=(f.length-1)/2, ring=new Array(n*2), x0=1e9,y0=1e9,x1=-1e9,y1=-1e9, sx=0, sy=0; for(k=0;k<n;k++){ var x=f[1+2*k], y=f[2+2*k]; ring[2*k]=x; ring[2*k+1]=y; sx+=x; sy+=y; x0=Math.min(x0,x); x1=Math.max(x1,x); y0=Math.min(y0,y); y1=Math.max(y1,y); }
      var bx=sx/n, by=sy/n; if(Math.abs(bx-cx)>R||Math.abs(by-cy)>R) return; if(n>1 && ring[0]===ring[2*n-2] && ring[1]===ring[2*n-1]){ n--; ring.length=n*2; } if(n<3) return;
      for(var q=0;q<lots.length;q++) if(rlPolyHit(lots[q], ring, x0,y0,x1,y1)){ cleared++; return; }
      var area=ringArea(ring), hs=hashXY(bx,by), h=f[0]>0?f[0]:3.3*(hs<.2?2:hs>.85?4:3), tone=dk?[96,100,122]:[198,184,168], col=mixC(tone, dk?[120,130,170]:[222,206,190], hashXY(bx*5,by*3)); if(f.col){ var cc=rgbOf(f.col); col=dk?mixC(cc,[120,130,170],.25):cc; }
      var wr=new Array(n*2); for(k=0;k<n*2;k++) wr[k]=ring[k]*K;
      var ob=obb(ring), rect=ob.area>0&&area/ob.area>.8, kind=(rect&&area<260&&h<=13)?(hs<.25?1:hs<.4?2:0):(h<=40?0:-1), eave=h*K;
      var sol=solid(wr, eave, col, 'b', ''); sol.part=!!f.part; if(f.mat){ sol.mat=f.mat; sol.sf=!!f.sf; if(sol.sf && h<=40){ var sh=rlShopFace(ring,n); if(sh){ sol.shop=sh; shops.push(sh); } } } if(f.mh>0) sol.z0=f.mh*K; bq.push({x0:x0,y0:y0,x1:x1,y1:y1,ring:ring}); W.solids.push(sol); if(kind>=0){ roofOf(roofM, wr, eave, kind, hashXY(bx*3,by*7)); roofs[kind]++; } kept++; }); }
  realDedupe(W);
  /* street trees, lamps, signals, stop signs, crossings and furniture: the scenery's own models (palace_ride_g.py sceneryPlace) at the points of the street data; where the data
     has no tree / lamp along a street with sidewalks, a jittered row is added (a tree every 14-26 m, a lamp every 36-52 m, never inside a building or near another one) */
  try{ var it={trees:[],lamps:[],signals:[],stops:[],benches:[],hydrants:[],bins:[],boxes:[],shops:shops,id:Math.round(cx)+','+Math.round(cy)}, nT=0, nTf=0, inR=function(x,y,r){ return Math.abs(x-cx)<=r&&Math.abs(y-cy)<=r; },
      hasB=function(x,y){ for(var q=0;q<bq.length;q++){ var b=bq[q]; if(x>=b.x0-1&&x<=b.x1+1&&y>=b.y0-1&&y<=b.y1+1 && rlInF(b.ring,x,y)) return true; } return false; },
      bearing=function(d){ var a=(d||0)*Math.PI/180; return [Math.sin(a),-Math.cos(a)]; },
      toRoad=function(x,y,any){ var nr=rlNear(x,y,40,any)[0]; if(!nr) return null; var d=Math.max(.1,nr.d); return {ox:(nr.x-x)/d, oy:(nr.y-y)/d, tx:Math.cos(nr.ang), ty:Math.sin(nr.ang), w:((RCLS[nr.f[0]]||[7])[0]), d:nr.d, x:nr.x, y:nr.y}; };
    var dt=REAL.trees||[], df=REAL.furn||[];
    var haveT=rlPG(dt.map(function(t){ return [t[0],t[1]]; }),20), haveL=rlPG(df.filter(function(q){ return q[2]==='street_lamp'; }).map(function(q){ return [q[0],q[1]]; }),30);
    dt.forEach(function(t){ if(!inR(t[0],t[1],R)) return; if(it.trees.length>=700) return; var d=Math.hypot(t[0]-cx,t[1]-cy), sp=/needle/i.test(t[3])?3:/platan|sycamore/i.test(t[2])?0:/quercus|oak/i.test(t[2])?2:/prunus|pyrus|cherry|pear/i.test(t[2])?4:/zelkova|gleditsia|honey|ginkgo/i.test(t[2])?1:sceneryTreeAt(t[0],t[1]);
      var lod=d>110||nTf>=140; if(!lod) nTf++; it.trees.push([t[0]*K,t[1]*K,sp,null,null,null,lod]); nT++; });
    df.forEach(function(q){ if(!inR(q[0],q[1],R)) return; var k=q[2], rd=toRoad(q[0],q[1],true), br=q[3]>=0?bearing(q[3]):null, X=q[0]*K, Y=q[1]*K;
      if(k==='street_lamp'){ if(it.lamps.length<400) it.lamps.push([X,Y,rd?rd.ox:1,rd?rd.oy:0]); }
      else if(k==='traffic_signals'&&rd){ if(it.signals.length<60){ var f=br||[rd.tx,rd.ty]; it.signals.push([X,Y,rd.ox,rd.oy,f[0],f[1]]); } }
      else if(k==='stop'&&rd){ if(it.stops.length<60){ var f2=br||[rd.tx,rd.ty]; it.stops.push([X,Y,f2[0],f2[1]]); } }
      else if(k==='crossing'&&rd&&rd.d<rd.w*.6){ var nx=-rd.ty, ny=rd.tx, hw=Math.min(rd.w,14)/2; for(var b=-3;b<=3;b++){ var ax=rd.x+rd.tx*b*.9, ay=rd.y+rd.ty*b*.9; W.dashes.push({ring:strip((ax-nx*hw)*K,(ay-ny*hw)*K,(ax+nx*hw)*K,(ay+ny*hw)*K,.5*K,0), cx:ax*K, cy:ay*K}); } }
      else if(k==='bench'&&rd){ it.benches.push([X,Y,rd.ox,rd.oy]); } else if(k==='fire_hydrant'&&rd){ it.hydrants.push([X,Y,rd.ox,rd.oy]); }
      else if(k==='waste_basket'){ it.bins.push([X,Y]); } else if(k==='post_box'&&rd){ it.boxes.push([X,Y,rd.ox,rd.oy]); } });
    /* the jittered rows */
    var nP=0, nL=0;
    procW.sort(function(p,q){ return Math.hypot(p[1]-cx,p[2]-cy)-Math.hypot(q[1]-cx,q[2]-cy); });     /* the streets nearest the camera first: the caps spend on them */
    procW.forEach(function(f){ var acc=0, gapT=(14+12*hashXY(f[1],f[2]))*K, gapL=(36+16*hashXY(f[2],f[1]))*K*.5, accL=gapL*hashXY(f[1]*3,f[2]), side=hashXY(f[1],f[2]*5)<.5?1:-1, w=((f.wd>0?f.wd:(RCLS[f[0]]||[7,.2])[0]))*K;
      for(var a=1;a+3<f.length;a+=2){ var x0=f[a]*K, y0=f[a+1]*K, x1=f[a+2]*K, y1=f[a+3]*K, l=Math.hypot(x1-x0,y1-y0); if(l<1) continue; var ux=(x1-x0)/l, uy=(y1-y0)/l, nx=-uy, ny=ux;
        for(var s=0;s<l;s+=1){ acc+=1; accL+=1;
          if(acc>=gapT){ acc=0; gapT=(14+12*hashXY(x0+s,y0))*K; [1,-1].forEach(function(sd){ var px=(x0+ux*s+nx*(w/2+1.0*K)*sd)/K, py=(y0+uy*s+ny*(w/2+1.0*K)*sd)/K; if(!inR(px,py,R)||nP>=300) return;
              if(rlPGnear(haveT,px,py,9)||hasB(px,py)) return; var nr=rlNear(px,py,w/K/2+1.2,true)[0]; if(nr&&nr.f!==f) return;
              var d=Math.hypot(px-cx,py-cy), lod=d>110||nTf>=140; if(!lod) nTf++; it.trees.push([px*K,py*K,sceneryTreeAt(px,py),null,null,null,lod]); nP++; }); }
          if(accL>=gapL){ accL=0; gapL=(36+16*hashXY(x0,y0+s))*K*.5; side=-side; var lx=(x0+ux*s+nx*(w/2+.75*K)*side)/K, ly=(y0+uy*s+ny*(w/2+.75*K)*side)/K; if(!inR(lx,ly,R*.8)||nL>=240||it.lamps.length>=400) continue;
            if(rlPGnear(haveL,lx,ly,20)||hasB(lx,ly)) continue; it.lamps.push([lx*K,ly*K,-nx*side,-ny*side]); nL++; } } } });
    var cn=sceneryPlace(W,it); if(cn){ W.real.trees=cn.trees; W.real.lamps=cn.lamps; W.real.signals=cn.signals; W.real.stops=cn.stops; W.real.furn=cn.furn; W.real.procTrees=nP; W.real.procLamps=nL; }
  }catch(e){ if(window.console) console.warn('real street furniture',e); }
  if(roofM.a.length) W.meshes.push({a:MB.done(roofM), id:'real:roof:'+Math.round(cx)+','+Math.round(cy)});
  lots.forEach(function(L){ var id=L.id, tw=(P.tw||{})[id], h=(tw?Math.min(220,60+tw*1):E.nbH(id))*.42, col=rgbOf(E.tubeCol(E.ucol(id))), gc=mixC(col, dk?[150,162,200]:[255,255,255], dk?.30:.5), ring=[]; L.p.forEach(function(p){ ring.push(p[0]*K,p[1]*K); });
    var s=solid(ring, Math.max(h,14)*K, gc, 'node', E.name(id)); s.id=id; s.col2=E.ucol(id); try{ s.door=rlDoor(ring,id); }catch(x){ s.door=null; } W.solids.push(s); });
  W.real.cleared=cleared; W.real.kept=kept; W.real.lots=lots.length; W.real.roads=W.roads.length; W.real.roofs={flat:roofs[0],gable:roofs[1],hip:roofs[2]};
  return W; }
REAL.gather=gatherReal;
/* a still frame at eye level. o.gl: through the ride's own GL path (the overlay must be open: _palRide.demo opens it), else the 2D painter on a canvas of its own */
REAL.shot=function(Xp, Yp, hp, o){
  o=o||{}; if(!REAL.isOn()) return null; var W=gatherReal(Xp,Yp,o.R), yaw=realHeading(Xp,Yp,hp), P=palette(), r=realOf(Xp,Yp,{x:0,y:0,k:0}), sn=o.snap?REAL.snap(r.x,r.y,yaw,o.snap):null;
  if(sn){ r={x:sn.x,y:sn.y,k:r.k}; yaw=sn.h; } if(o.yaw!=null) yaw=o.yaw;
  var cvs=null, ctx, w, h;
  if(o.gl){ if(!R.ctx||!glOk()) return {err:'no GL context (open the overlay with _palRide.demo first)'}; if(R.raf){ cancelAnimationFrame(R.raf); R.raf=0; } R.playing=false; sizeCheck(); ctx=R.ctx; w=R.w; h=R.h; ctx.setTransform(R.dpr,0,0,R.dpr,0,0); }
  else { cvs=document.getElementById('pal-real-cv'); if(!cvs){ cvs=document.createElement('canvas'); cvs.id='pal-real-cv'; cvs.style.cssText='position:fixed;left:0;top:0;width:100vw;height:100vh;z-index:99999;background:#000'; document.body.appendChild(cvs); }
    w=window.innerWidth; h=window.innerHeight; cvs.width=w; cvs.height=h; ctx=cvs.getContext('2d'); }
  setCam(r.x*K, r.y*K, o.z||2.1, yaw+(o.dyaw||0), w, h, .5, o.pitch||0);
  if(o.gl){ var n=o.frames||24; for(var f=0;f<n;f++){ drawCity(ctx,w,h,P,W,yaw,f*.05,null); } }
  else { drawSky(ctx,w,h,P,yaw,0); drawGround(ctx,W,P,null,null); drawSolids(ctx,W.solids,P); }
  return {real:[r.x,r.y], dom:r.k, yaw:yaw, snap:sn&&{d:sn.d,cls:sn.cls}, stats:W.real, solids:W.solids.length, meshes:W.meshes.length, gl:!!o.gl}; };
REAL.leg=function(step){ var M=R.M; if(!M) return null; var out=[], o={x:0,y:0,k:0}; step=step||40;
  for(var s=0;s<=M.D.L;s+=step){ pathAt(M.D,s,_pa); var h=headAt(M.D,s,14); realOf(_pa.x,_pa.y,o); out.push([s,_pa.x,_pa.y,h,o.x,o.y,o.k]); } return out; };
/* the model's route in the real frame and a still frame at page arclength s along it */
REAL.legShot=function(s,o){ var M=R.M||REAL._M; if(!M) return null; if(R.M){ REAL._M=R.M; R.M=null; }   /* the ride's own frames stop (render() needs R.M) so only this world is drawn */
  if(!M.D.real) REAL.match(M.D); var q={x:0,y:0,h:0}; REAL.pathAt(M.D,s,q); pathAt(M.D,s,_pa); o=o||{};
  var W=gatherReal(_pa.x,_pa.y,o.R), P=palette(), ctx, w, h; if(!R.ctx||!glOk()||!o.gl){ return {err:'GL only'}; }
  if(R.raf){ cancelAnimationFrame(R.raf); R.raf=0; } R.playing=false; sizeCheck(); ctx=R.ctx; w=R.w; h=R.h; ctx.setTransform(R.dpr,0,0,R.dpr,0,0); setCam(q.x,q.y,o.z||2.1,q.h,w,h,.5,0);
  for(var f=0;f<(o.frames||24);f++) drawCity(ctx,w,h,P,W,q.h,f*.05,null); return {x:q.x/K,y:q.y/K,h:q.h,stats:W.real}; };
"""


def test_blob(bbox, region, bld_dir, osm_glob_dir, scale: float = 1.0) -> dict:
    """TEST ONLY (until the hosted street blob lands): buildings from the cached OSM bld-*.json and highways from the cached osm-*.json,
    projected to real px (palace_map.project), kept inside `region` = (x0, y0, x1, y1) real px."""
    from .. import palace_map as pmap
    x0, y0, x1, y1 = region
    b, r, rn = [], [], []
    seen = set()

    def pr(g):
        return [pmap.project(p["lat"], p["lon"], bbox, scale) for p in g]
    for f in sorted(Path(bld_dir).glob("bld-*.json")):
        for e in json.loads(f.read_text()).get("elements", []):
            if e.get("type") != "way" or not e.get("geometry") or e["id"] in seen or "building" not in (e.get("tags") or {}):
                continue
            bb = e.get("bounds")
            if not bb:
                continue
            ax, ay = pmap.project(bb["maxlat"], bb["minlon"], bbox, scale)
            bx, by = pmap.project(bb["minlat"], bb["maxlon"], bbox, scale)
            if bx < x0 or ax > x1 or by < y0 or ay > y1:
                continue
            seen.add(e["id"])
            t = e["tags"]
            h = 0.0
            try:
                h = float(str(t.get("height", "")).split()[0]) if t.get("height") else (float(t["building:levels"]) * 3.3 if t.get("building:levels") else 0.0)
            except Exception:
                h = 0.0
            pts = pr(e["geometry"])
            b.append([round(h, 1)] + [round(v, 1) for p in pts for v in p])
    for f in sorted(Path(osm_glob_dir).glob("osm-*.json")):
        for e in json.loads(f.read_text()).get("elements", []):
            t = e.get("tags") or {}
            if e.get("type") != "way" or "highway" not in t or not e.get("geometry") or e["id"] in seen:
                continue
            pts = pr(e["geometry"])
            if not any(x0 <= p[0] <= x1 and y0 <= p[1] <= y1 for p in pts):
                continue
            seen.add(e["id"])
            r.append([t["highway"]] + [round(v, 1) for p in pts for v in p])
            rn.append(t.get("name", ""))
    return {"b": b, "r": r, "rn": rn}
