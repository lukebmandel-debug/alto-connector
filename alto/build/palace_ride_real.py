"""Real-geometry first-person ride, phase 0 spike: the exact map between the page's lattice-warped world and the real street frame.

The page world (palace_grid.Mapping) is a rotation, then separate strictly increasing piecewise-linear x and y tables (per domain, see
palace_fillin.domains: a Dom's own `page` turn/shift on top; a free domain is the same tables with two entries). The ride used to walk that
warped world; the real-geometry ride walks the REAL street frame (metres: real px, scale 1.0) and only asks the page where things are.

    to_real(X, Y)  page px  -> real px   domain by clip ring (a child lattice), else the root;  Dom.to_local, then city_report.unmap
    to_page(x, y)  real px  -> page px   domain by real ring (poly) else the nearest;           Mapping.__call__, then Dom.page

Python mirror (RealMap, used by the tests) and JS (JS_REAL, run inside the ride's closure, exposed as window._palRide.real) are the same
arithmetic. Nothing here adds to the page: the page already carries m["doms"]; the street data is hosted (window._ALTO_STREET).
"""
from __future__ import annotations

import math

from . import palace_fillin as _pf
from .city_report import unmap
from .palace_grid import CW, CH


class RealMap:
    """Python mirror of the JS: built from the page map m (needs m["doms"] or m["grid"])."""

    def __init__(self, m):
        self.doms = _pf.domains(m)
        self.by_page, self.by_real = _pf._owners(self.doms)

    def to_real(self, X, Y):
        d = self.by_page(X, Y)
        lx, ly = d.to_local(X, Y)
        t = d.mp
        x, y = unmap({"t": t.th, "cx": t.cx, "cy": t.cy, "xr": t.xr, "xg": t.xg, "yr": t.yr, "yg": t.yg}, lx, ly)
        return x, y, d.k

    def to_page(self, x, y):
        d = self.by_real(x, y)
        lx, ly = d.mp(x, y)
        X, Y = d.page(lx, ly)
        return X, Y, d.k


JS_REAL = r"""
/* ── real geometry: page px <-> real px (metres), the exact inverse of the page lattice (see palace_ride_real.py) ── */
var REAL={ready:false, on:false, doms:null, root:null, kids:null, CWX:240, CHY:170, chunks:null, cell:400, nB:0, nR:0};
function rlRing(r){ var o=[]; if(!r||!r.length) return null; for(var i=0;i<r.length;i++) o.push([r[i][0],r[i][1]]); return o; }
function rlIn(r,x,y){ var c=false, n=r.length; for(var i=0;i<n;i++){ var a=r[i], b=r[(i+1)%n]; if((a[1]>y)!==(b[1]>y) && x<a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1])) c=!c; } return c; }
function rlD2(r,x,y){ if(!r) return 1e30; var m=1e30; for(var i=0;i<r.length;i++){ var dx=r[i][0]-x, dy=r[i][1]-y; m=Math.min(m,dx*dx+dy*dy); } return m; }
function rlInit(){
  if(REAL.doms) return REAL.doms.length>0;
  var Mp=E&&E.M; var raw=(Mp&&Mp.doms&&Mp.doms.length)?Mp.doms:(Mp&&Mp.grid?[{id:0,kind:'grid',a:0,o:[0,0],mapping:Mp.grid,clip:null,poly:null}]:null);
  if(!raw){ REAL.doms=[]; return false; }
  REAL.doms=raw.map(function(d,k){ var a=(+d.a||0)*Math.PI/180; return {k:k, tb:d.mapping||d.grid, c:Math.cos(a), s:Math.sin(a), ox:(d.o||[0,0])[0], oy:(d.o||[0,0])[1], clip:rlRing(d.clip), poly:rlRing(d.poly), free:d.kind==='free'||!d.mapping}; });
  REAL.kids=REAL.doms.filter(function(d){ return d.clip; });
  REAL.root=REAL.doms.filter(function(d){ return !d.clip && !d.free; })[0]||REAL.doms[0];
  REAL.ready=true; return true; }
/* the inverse of one axis' table (city_report.unmap.inv): grid px -> real px, extended past the ends at the end spacing */
function rlInv(v,R,G,step){
  if(!G||!G.length) return v;
  if(v<=G[0]) return R[0]-(G[0]-v)*Math.max(1e-6,(R.length>1?R[1]-R[0]:1))/step;
  var n=G.length; if(v>=G[n-1]) return R[n-1]+(v-G[n-1])*Math.max(1e-6,(R.length>1?R[n-1]-R[n-2]:1))/step;
  var lo=0, hi=n-1; while(hi-lo>1){ var mid=(lo+hi)>>1; if(G[mid]<=v) lo=mid; else hi=mid; }
  return R[lo]+(v-G[lo])/Math.max(1e-9,G[hi]-G[lo])*(R[hi]-R[lo]); }
function rlFwd(v,R,G,step){
  if(!R||!R.length) return v;
  var n=R.length; if(v<=R[0]) return G[0]-(R[0]-v)/Math.max(1e-6,(n>1?R[1]-R[0]:1))*step;
  if(v>=R[n-1]) return G[n-1]+(v-R[n-1])/Math.max(1e-6,(n>1?R[n-1]-R[n-2]:1))*step;
  var lo=0, hi=n-1; while(hi-lo>1){ var mid=(lo+hi)>>1; if(R[mid]<=v) lo=mid; else hi=mid; }
  return G[lo]+(v-R[lo])/Math.max(1e-9,R[hi]-R[lo])*(G[hi]-G[lo]); }
var _rl={x:0,y:0,k:0};
function realOf(X,Y,o){
  o=o||_rl; if(!rlInit()){ o.x=X; o.y=Y; o.k=-1; return o; }
  var d=REAL.root; for(var i=0;i<REAL.kids.length;i++) if(rlIn(REAL.kids[i].clip,X,Y)){ d=REAL.kids[i]; break; }
  var x=X-d.ox, y=Y-d.oy, lx=x*d.c+y*d.s, ly=-x*d.s+y*d.c, T=d.tb;
  var tx=rlInv(lx,T.xr,T.xg,REAL.CWX), ty=rlInv(ly,T.yr,T.yg,REAL.CHY), c=Math.cos(T.t), s=Math.sin(T.t);
  tx-=T.cx; ty-=T.cy; o.x=tx*c-ty*s+T.cx; o.y=tx*s+ty*c+T.cy; o.k=d.k; return o; }
function pageOf(x,y,o){
  o=o||_rl; if(!rlInit()){ o.x=x; o.y=y; o.k=-1; return o; }
  var D=REAL.doms, d=null, best=1e30, i;
  if(D.length===1) d=D[0]; else { for(i=0;i<D.length;i++) if(D[i].poly && rlIn(D[i].poly,x,y)){ d=D[i]; break; }
    if(!d) for(i=0;i<D.length;i++){ var dd=rlD2(D[i].poly,x,y); if(dd<best){ best=dd; d=D[i]; } } if(!d) d=REAL.root; }
  var T=d.tb, c=Math.cos(-T.t), s=Math.sin(-T.t), tx=x-T.cx, ty=y-T.cy, ux=tx*c-ty*s+T.cx, uy=tx*s+ty*c+T.cy;
  var lx=rlFwd(ux,T.xr,T.xg,REAL.CWX), ly=rlFwd(uy,T.yr,T.yg,REAL.CHY);
  o.x=lx*d.c-ly*d.s+d.ox; o.y=lx*d.s+ly*d.c+d.oy; o.k=d.k; return o; }
/* the page heading (radians) at a page point, as a real heading */
function realHeading(X,Y,h){ var a=realOf(X,Y,{x:0,y:0,k:0}), b=realOf(X+Math.cos(h)*12,Y+Math.sin(h)*12,{x:0,y:0,k:0}); return Math.atan2(b.y-a.y,b.x-a.x); }
"""
