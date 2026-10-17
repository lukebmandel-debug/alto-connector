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
/* ── the real street world ── */
var RCLS={motorway:[26,.5],motorway_link:[12,.5],trunk:[22,.5],trunk_link:[11,.5],primary:[17,.45],primary_link:[10,.4],secondary:[14,.4],secondary_link:[9,.4],tertiary:[12,.35],tertiary_link:[8,.3],
  residential:[9.5,.3],unclassified:[9,.3],living_street:[8,.2],service:[5,.1],pedestrian:[6,0],footway:[2.4,0],path:[2,0],cycleway:[2.6,0],steps:[2,0],track:[4,0]};
REAL.load=function(blob){ var C=REAL.cell, ch={}; REAL.nB=0; REAL.nR=0;
  function put(kind,f,x,y){ var k=Math.floor(x/C)+','+Math.floor(y/C); var c=ch[k]||(ch[k]={b:[],r:[]}); c[kind].push(f); }
  (blob.b||[]).forEach(function(f){ put('b',f,f[1],f[2]); REAL.nB++; });
  (blob.r||[]).forEach(function(f){ for(var i=1;i+1<f.length;i+=2){ put('r',f,f[i],f[i+1]); break; } REAL.nR++; });   /* a way is indexed by its first vertex; gather reaches +1 cell */
  REAL.chunks=ch; REAL.on=true; return {b:REAL.nB, r:REAL.nR}; };
REAL.isOn=function(){ return !!(REAL.on && rlInit() && REAL.chunks); };
function rlPolyHit(q, ring, x0,y0,x1,y1){          /* a real footprint (ring, bbox) against a lot's corner polygon q: any vertex or the centre inside, or a lot corner inside */
  var n=ring.length/2, i;
  if(x1<q.x0||x0>q.x1||y1<q.y0||y0>q.y1) return false;
  var cx=(x0+x1)/2, cy=(y0+y1)/2; if(rlIn(q.p,cx,cy)) return true;
  for(i=0;i<n;i++) if(rlIn(q.p,ring[2*i],ring[2*i+1])) return true;
  for(i=0;i<q.p.length;i++) if(x0<=q.p[i][0]&&q.p[i][0]<=x1&&y0<=q.p[i][1]&&q.p[i][1]<=y1){ var inside=false, j, m=n; for(j=0,inside=false;j<m;j++){ var ax=ring[2*j], ay=ring[2*j+1], bx=ring[2*((j+1)%m)], by=ring[2*((j+1)%m)+1];
      if((ay>q.p[i][1])!==(by>q.p[i][1]) && q.p[i][0]<ax+(q.p[i][1]-ay)*(bx-ax)/(by-ay)) inside=!inside; } if(inside) return true; }
  return false; }
function gatherReal(Xp, Yp, R){
  R=R||480; var o0=realOf(Xp,Yp,{x:0,y:0,k:0}), cx=o0.x, cy=o0.y, C=REAL.cell, P=E.P, i, k, ci0=Math.floor((cx-R)/C), ci1=Math.floor((cx+R)/C), cj0=Math.floor((cy-R)/C), cj1=Math.floor((cy+R)/C);
  var W={solids:[], tiles:[], parks:[], water:[], roads:[], props:[], poles:[], labels:[], tunn:false, set:{}, scenery:null, meshes:[], movers:[], dashes:[], rivers:[], real:{cx:cx,cy:cy,dom:o0.k}};
  /* the user's node lots, unmapped corner by corner (a lot is a page rectangle: it comes out a skewed quad where the lattice is stretched) */
  var lots=[], seen={};
  Object.keys(P.at||{}).forEach(function(id){ if(E.bOf(id)!==id) return; var key=P.at[id]; if(seen[key]) return; seen[key]=1; var L=E.lot(key); if(!L) return;
    var pr=turnedRing(L), q=[], tmp={x:0,y:0,k:0}; for(i=0;i<4;i++){ realOf(pr[2*i],pr[2*i+1],tmp); q.push([tmp.x,tmp.y]); }
    var mx=0,my=0; q.forEach(function(p){ mx+=p[0]/4; my+=p[1]/4; }); if(Math.hypot(mx-cx,my-cy)>R+80) return;
    var xs=q.map(function(p){ return p[0]; }), ys=q.map(function(p){ return p[1]; });
    lots.push({id:id, p:q, x0:Math.min.apply(null,xs), x1:Math.max.apply(null,xs), y0:Math.min.apply(null,ys), y1:Math.max.apply(null,ys)}); });
  var cleared=0, kept=0, dk=dark();
  var ground=[cx-R,cy-R,cx+R,cy-R,cx+R,cy+R,cx-R,cy+R]; W.tiles.push({ring:ground, cx:cx, cy:cy, r:R*1.5});
  var seenW=[];
  for(var ci=ci0-1; ci<=ci1+1; ci++) for(var cj=cj0-1; cj<=cj1+1; cj++){ var ch=REAL.chunks[ci+','+cj]; if(!ch) continue;
    ch.r.forEach(function(f){ if(f._g===cx+','+cy) return; f._g=cx+','+cy; var w=(RCLS[f[0]]||[7,.2])[0], sw=(RCLS[f[0]]||[7,.2])[1];
      for(var a=1;a+3<f.length;a+=2){ var x0=f[a], y0=f[a+1], x1=f[a+2], y1=f[a+3], mx=(x0+x1)/2, my=(y0+y1)/2; if(Math.abs(mx-cx)>R||Math.abs(my-cy)>R) continue; var l=Math.hypot(x1-x0,y1-y0); if(l<.5) continue;
        if(sw>0){ var sr=strip(x0,y0,x1,y1,w+2*3.2,w*.18); W.tiles.push({ring:sr, cx:mx, cy:my, r:l/2+w, sw:1}); }
        W.roads.push({x0:x0,y0:y0,x1:x1,y1:y1,w:w,cx:mx,cy:my,r:l/2+w, cls:f[0]});
        if(sw>=.3 && w>=9 && l>30){ var ux=(x1-x0)/l, uy=(y1-y0)/l; for(var p=8;p<l-8;p+=22){ var ax=x0+ux*p, ay=y0+uy*p; W.dashes.push({ring:strip(ax,ay,ax+ux*9,ay+uy*9,.35,0), cx:ax, cy:ay}); } } } });
    ch.b.forEach(function(f){ var n=(f.length-1)/2, ring=new Array(n*2), x0=1e9,y0=1e9,x1=-1e9,y1=-1e9, sx=0, sy=0; for(k=0;k<n;k++){ var x=f[1+2*k], y=f[2+2*k]; ring[2*k]=x; ring[2*k+1]=y; sx+=x; sy+=y; x0=Math.min(x0,x); x1=Math.max(x1,x); y0=Math.min(y0,y); y1=Math.max(y1,y); }
      var bx=sx/n, by=sy/n; if(Math.abs(bx-cx)>R||Math.abs(by-cy)>R) return; if(n>1 && ring[0]===ring[2*n-2] && ring[1]===ring[2*n-1]){ n--; ring.length=n*2; } if(n<3) return;
      for(var q=0;q<lots.length;q++) if(rlPolyHit(lots[q], ring, x0,y0,x1,y1)){ cleared++; return; }
      var h=f[0]>0?f[0]:(6+hashXY(bx,by)*7), hv=.9+.2*hashXY(bx*3,by*7), tone=dk?[96,100,122]:[198,184,168], tint=hashXY(bx*5,by*3), col=mixC(tone, dk?[120,130,170]:[222,206,190], tint);
      W.solids.push(solid(ring, h*1.0, col, 'b', '')); kept++; }); }
  /* the lots, in glass, at the node height */
  lots.forEach(function(L){ var id=L.id, tw=(P.tw||{})[id], h=(tw?Math.min(220,60+tw*1):E.nbH(id))*.42, col=rgbOf(E.tubeCol(E.ucol(id))), gc=mixC(col, dk?[150,162,200]:[255,255,255], dk?.30:.5), ring=[]; L.p.forEach(function(p){ ring.push(p[0],p[1]); });
    var s=solid(ring, Math.max(h,14), gc, 'node', E.name(id)); s.id=id; s.col2=E.ucol(id); W.solids.push(s); });
  W.real.cleared=cleared; W.real.kept=kept; W.real.lots=lots.length; W.real.roads=W.roads.length;
  return W; }
/* the unmapped lattice street is within a block-width of the real one: snap a real point to the nearest road centre line (within `maxd` m), keeping the heading's side */
REAL.snap=function(x,y,h,maxd){ maxd=maxd||40; var C=REAL.cell, ci=Math.floor(x/C), cj=Math.floor(y/C), best=null, bd=maxd*maxd;
  for(var i=ci-1;i<=ci+1;i++) for(var j=cj-1;j<=cj+1;j++){ var ch=REAL.chunks&&REAL.chunks[i+','+j]; if(!ch) continue; ch.r.forEach(function(f){ var c=RCLS[f[0]]; if(!c||c[0]<8) return;
    for(var a=1;a+3<f.length;a+=2){ var ax=f[a], ay=f[a+1], bx=f[a+2], by=f[a+3], dx=bx-ax, dy=by-ay, L2=dx*dx+dy*dy||1, t=Math.max(0,Math.min(1,((x-ax)*dx+(y-ay)*dy)/L2)), px=ax+t*dx, py=ay+t*dy, d=(px-x)*(px-x)+(py-y)*(py-y);
      if(d<bd){ bd=d; var ang=Math.atan2(dy,dx); if(Math.cos(ang-h)<0) ang+=Math.PI; best={x:px,y:py,h:ang,d:Math.sqrt(d),cls:f[0]}; } } }); }
  return best; };
/* a still frame at eye level, drawn with the 2D painter on its own canvas (the spike's demo; the ride's GL path takes the same W) */
REAL.shot=function(Xp, Yp, hp, o){
  o=o||{}; if(!REAL.isOn()) return null; var W=gatherReal(Xp,Yp,o.R), yaw=realHeading(Xp,Yp,hp), P=palette(), cv=document.getElementById('pal-real-cv');
  if(!cv){ cv=document.createElement('canvas'); cv.id='pal-real-cv'; cv.style.cssText='position:fixed;left:0;top:0;width:100vw;height:100vh;z-index:99999;background:#000'; document.body.appendChild(cv); }
  var w=o.w||window.innerWidth, h=o.h||window.innerHeight; cv.width=w; cv.height=h; var ctx=cv.getContext('2d'); var r=realOf(Xp,Yp,{x:0,y:0,k:0}), sn=o.snap?REAL.snap(r.x,r.y,yaw,o.snap):null; if(sn){ r={x:sn.x,y:sn.y,k:r.k}; yaw=sn.h; }
  setCam(r.x, r.y, o.z||1.7, yaw+(o.dyaw||0), w, h, .5);
  drawSky(ctx,w,h,P,yaw,0); drawGround(ctx,W,P,null,null); drawSolids(ctx,W.solids,P);
  return {real:[r.x,r.y], dom:r.k, snap:sn&&{d:sn.d,cls:sn.cls}, yaw:yaw, stats:W.real, solids:W.solids.length}; };
REAL.toReal=function(X,Y){ var o=realOf(X,Y,{x:0,y:0,k:0}); return [o.x,o.y,o.k]; };
REAL.toPage=function(x,y){ var o=pageOf(x,y,{x:0,y:0,k:0}); return [o.x,o.y,o.k]; };
REAL.gather=gatherReal;
/* one ride leg (R.M after _palRide.demo): its page path unmapped to the real frame: [[s, X, Y, heading, x, y, dom]...] every `step` page px */
REAL.leg=function(step){ var M=R.M; if(!M) return null; var out=[], o={x:0,y:0,k:0}; step=step||40;
  for(var s=0;s<=M.D.L;s+=step){ pathAt(M.D,s,_pa); var h=headAt(M.D,s,14); realOf(_pa.x,_pa.y,o); out.push([s,_pa.x,_pa.y,h,o.x,o.y,o.k]); } return out; };
"""


def test_blob(bbox, region, bld_dir, osm_glob_dir, scale: float = 1.0) -> dict:
    """TEST ONLY (until the hosted street blob lands): buildings from the cached OSM bld-*.json and highways from the cached osm-*.json,
    projected to real px (palace_map.project), kept inside `region` = (x0, y0, x1, y1) real px."""
    from .. import palace_map as pmap
    x0, y0, x1, y1 = region
    b, r = [], []
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
    return {"b": b, "r": r}
