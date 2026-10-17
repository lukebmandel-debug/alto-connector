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


# ── the in-bounds region (2.0.0 scope rule) ─────────────────────────────────
# The first-person view only has to work where something is active: a district that holds a node, an active fleet element (a boat, a base) or the user's own background
# buildings, and the ride's landmarks. Everywhere else is OUT OF BOUNDS. The region is the union of: every district's box (real lat/lon), a disc of the element's size round
# each boat / base, a LANDMARK_M disc round each landmark, buffered BUFFER_M. Build time: this module (Scope) decides which Overpass tiles are fetched and which street cells are
# written (palace_street), and records the extent in the manifest ("ib"). Run time: the JS below (REAL.bounds) computes the same thing from E.M / E.P (it also sees the user's
# node lots and claimed footprints, which only exist on the page).
BUFFER_M = 150.0
LANDMARK_M = 120.0
BOAT_M = 60.0                    # a boat or base is a disc this big at least (its toy is drawn at the page's px size; real size is added when known)


class Scope:
    """The in-bounds region in the street frame (metres east/north of the box's south-west corner; palace_street.Frame): rects and discs plus BUFFER_M."""

    def __init__(self, bbox, rects=(), discs=(), buffer: float = BUFFER_M):
        self.s, self.w, self.n, self.e = (float(v) for v in bbox)
        self.kx = math.cos(math.radians((self.s + self.n) / 2)) * 111320
        self.ky = 110574.0
        self.buffer = float(buffer)
        self.rects = [tuple(float(v) for v in r) for r in rects]
        self.discs = [tuple(float(v) for v in d) for d in discs]

    def __bool__(self):
        return bool(self.rects or self.discs)

    # frames
    def metres(self, lat, lon):
        return (lon - self.w) * self.kx, (lat - self.s) * self.ky

    def from_real(self, x, y, scale: float = 1.0):
        """real px of the map (palace_map.project: y down, `scale` px per metre) -> street metres."""
        return x / scale, (self.n - self.s) * self.ky - y / scale

    def hits(self, x0, y0, x1, y1, grow: float = None):
        """True when the metre rectangle (with `grow` more, default the buffer) touches the region."""
        g = self.buffer if grow is None else grow
        for a, b, c, d in self.rects:
            if x0 <= c + g and x1 >= a - g and y0 <= d + g and y1 >= b - g:
                return True
        for cx, cy, r in self.discs:
            dx = max(x0 - cx, 0.0, cx - x1)
            dy = max(y0 - cy, 0.0, cy - y1)
            if dx * dx + dy * dy <= (r + g) ** 2:
                return True
        return False

    def contains(self, x, y, grow: float = None) -> bool:
        g = self.buffer if grow is None else grow
        return self.hits(x, y, x, y, g)

    def cells(self, cs_m: float, nx: int, ny: int):
        """The street cells (ix, iy) of size cs_m metres the region touches."""
        out = set()
        for ix in range(nx):
            for iy in range(ny):
                if self.hits(ix * cs_m, iy * cs_m, (ix + 1) * cs_m, (iy + 1) * cs_m):
                    out.add((ix, iy))
        return out

    def tile_ok(self, tb) -> bool:
        """A tile box (south, west, north, east in degrees) that touches the region (a little extra so a feature on a tile edge is not cut)."""
        x0, y0 = self.metres(tb[0], tb[1])
        x1, y1 = self.metres(tb[2], tb[3])
        return self.hits(x0, y0, x1, y1, self.buffer + 60.0)


def scope_for(m, districts, bbox, nodes_in=None):
    """The Scope of a palace being set up: m = the page map (landmarks, boats, bases in page px; doms), districts = brief.palace.districts [{unit, name, bounds}],
    nodes_in = optional set of district units that hold at least one node (default: every listed district does). None when there is nothing to scope to (the whole box stays)."""
    bb = m.get("bbox") or bbox
    sc = float(m.get("scale") or 1.0)
    sp = Scope(bb)
    for d in districts or ():
        b = d.get("bounds") if isinstance(d, dict) else None
        if not b or len(b) != 4 or (nodes_in is not None and d.get("unit") not in nodes_in):
            continue
        x0, y0 = sp.metres(b[0], b[1])
        x1, y1 = sp.metres(b[2], b[3])
        sp.rects.append((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
    try:
        rm = RealMap(m)
    except Exception:                                       # noqa: BLE001 — a map without lattices: page px are real px
        rm = None

    def real(X, Y):
        if rm is None:
            return X, Y
        x, y, _k = rm.to_real(X, Y)
        return x, y

    def disc(X, Y, r):
        x, y = real(X, Y)
        mx, my = sp.from_real(x, y, sc)
        sp.discs.append((mx, my, r))
    for l in m.get("landmarks") or ():
        if "x" in l and "y" in l:
            disc(l["x"], l["y"], LANDMARK_M)
    for b in m.get("boats") or ():
        disc(b["x"], b["y"], max(BOAT_M, float(b.get("len") or 0) / 2))
    for b in m.get("bases") or ():
        disc(b["x"], b["y"], max(BOAT_M, float(b.get("r") or 0)))
    return sp if sp else None


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

/* ── the in-bounds region (scope rule): the first-person view only has to work where something is active. In real px (metres), a 40 m grid of the CORE (districts that hold a node,
   every node's lot, claimed footprints = the user's background buildings, boats, bases, a 120 m disc round each landmark) and its chamfer distance field; in bounds = within
   REAL.BUFFER (150 m) of the core. The roam / ride owner's hooks:
     REAL.inBounds(x,y)       real px -> true inside the region (and, with a street manifest, where street data was written)
     REAL.edgeDist(x,y)       metres to the edge, positive inside / negative outside, smooth (bilinear): fade fog and slow down as it nears 0
     REAL.clamp(x,y,o)        the nearest in-bounds point {x,y,moved,d} (o is reused); a walker is stopped there
     REAL.legInBounds(D)      the ride leg D (page path) stays in bounds -> {ok, n, out}; REAL.match(D) only matches such a leg, the rest keep the lattice world
     REAL.bounds()            {ready, cell, x0, y0, w, h, core, items, ...}   REAL.boundsReset() after the user moves a node ── */
REAL.BUFFER=150; REAL.LANDMARK=120; REAL.CELL=40;
var RB={ready:false, c:40, x0:0, y0:0, w:0, h:0, D:null, core:0, items:0, why:null};
function rbMark(items){ var c=RB.c, i, x0=1e30,y0=1e30,x1=-1e30,y1=-1e30, pad=REAL.BUFFER+c*3;
  for(i=0;i<items.length;i++){ var q=items[i]; x0=Math.min(x0,q[0]-q[2]); y0=Math.min(y0,q[1]-q[2]); x1=Math.max(x1,q[0]+q[2]); y1=Math.max(y1,q[1]+q[2]); }
  RB.x0=Math.floor((x0-pad)/c)*c; RB.y0=Math.floor((y0-pad)/c)*c; RB.w=Math.ceil((x1+pad-RB.x0)/c)+1; RB.h=Math.ceil((y1+pad-RB.y0)/c)+1;
  var w=RB.w, h=RB.h, D=new Uint16Array(w*h), INF=60000, n=0; D.fill(INF);
  for(i=0;i<items.length;i++){ var q2=items[i], r=q2[2], ci0=Math.max(0,Math.floor((q2[0]-r-RB.x0)/c)), ci1=Math.min(w-1,Math.floor((q2[0]+r-RB.x0)/c)), cj0=Math.max(0,Math.floor((q2[1]-r-RB.y0)/c)), cj1=Math.min(h-1,Math.floor((q2[1]+r-RB.y0)/c));
    for(var cj=cj0;cj<=cj1;cj++) for(var ci=ci0;ci<=ci1;ci++){ var dx=RB.x0+(ci+.5)*c-q2[0], dy=RB.y0+(cj+.5)*c-q2[1]; if(dx*dx+dy*dy<=(r+c*.5)*(r+c*.5) && D[cj*w+ci]!==0){ D[cj*w+ci]=0; n++; } } }
  /* the chamfer 3-4 distance field (units of c/3 m) */
  var a, b, k, x, y;
  for(y=0;y<h;y++) for(x=0;x<w;x++){ k=y*w+x; a=D[k]; if(x>0) a=Math.min(a,D[k-1]+3); if(y>0){ a=Math.min(a,D[k-w]+3); if(x>0) a=Math.min(a,D[k-w-1]+4); if(x<w-1) a=Math.min(a,D[k-w+1]+4); } D[k]=a; }
  for(y=h-1;y>=0;y--) for(x=w-1;x>=0;x--){ k=y*w+x; a=D[k]; if(x<w-1) a=Math.min(a,D[k+1]+3); if(y<h-1){ a=Math.min(a,D[k+w]+3); if(x<w-1) a=Math.min(a,D[k+w+1]+4); if(x>0) a=Math.min(a,D[k+w-1]+4); } D[k]=a; }
  RB.D=D; RB.core=n; RB.items=items.length; }
function rbInit(){
  if(RB.ready) return true; var Mp=E&&E.M, P=E&&E.P; if(!Mp||!P||!rlInit()) return false;
  var items=[], o={x:0,y:0,k:0}, i, S=30, nd=0;
  function disc(X,Y,r){ realOf(X,Y,o); items.push([o.x,o.y,r]); }
  var hasNode=function(d){ var ids=(P.units||[])[d.u]||[]; for(var j=0;j<ids.length;j++) if(P.at&&P.at[ids[j]]&&E.lot(P.at[ids[j]])) return true; return false; };
  (P.d||[]).forEach(function(d){ if(!d.box||!hasNode(d)) return; nd++; var b=d.box;
    for(var X=b[0];X<=b[2]+S*.5;X+=S) for(var Y=b[1];Y<=b[3]+S*.5;Y+=S) disc(Math.min(X,b[2]),Math.min(Y,b[3]),S*.75); });
  var seen={}; Object.keys(P.at||{}).forEach(function(id){ var key=P.at[id]; if(seen[key]) return; seen[key]=1; var L=E.lot(key); if(!L) return; disc(L[0],L[1],Math.max(L[2],L[3])*.75+20); });
  var sh=P.sh||{}; Object.keys(P.pl0||{}).forEach(function(k){ var s=(P.pl0[k]||{}).shape; if(s&&!sh[k]) sh[k]=s; });
  Object.keys(sh).forEach(function(k){ var s=sh[k]; if(s&&s.x!=null) disc(s.x,s.y,Math.max(+s.w||0,+s.h||0)*.6+20); });
  (Mp.landmarks||[]).forEach(function(l){ if(l&&l.x!=null) disc(l.x,l.y,REAL.LANDMARK); });
  (Mp.boats||[]).forEach(function(b){ disc(b.x,b.y,Math.max(60,(+b.len||0)/2)); });
  (Mp.bases||[]).forEach(function(b){ disc(b.x,b.y,Math.max(60,+b.r||0)); });
  if(!items.length){ RB.ready=false; RB.why='nothing active'; return false; }
  rbMark(items); RB.nd=nd; RB.ready=true; return true; }
REAL.boundsReset=function(){ RB.ready=false; RB.D=null; };
REAL.bounds=function(){ rbInit(); return {ready:RB.ready, cell:RB.c, x0:RB.x0, y0:RB.y0, w:RB.w, h:RB.h, core:RB.core, items:RB.items, districts:RB.nd, buffer:REAL.BUFFER}; };
/* metres from the region's core (chamfer, bilinear); 1e4 outside the grid */
function rbDist(x,y){ if(!rbInit()) return 0; var c=RB.c, fx=(x-RB.x0)/c-.5, fy=(y-RB.y0)/c-.5, i=Math.floor(fx), j=Math.floor(fy), tx=fx-i, ty=fy-j, w=RB.w, h=RB.h, D=RB.D;
  if(i<0||j<0||i+1>=w||j+1>=h) return 1e4; var d00=D[j*w+i], d10=D[j*w+i+1], d01=D[(j+1)*w+i], d11=D[(j+1)*w+i+1];
  return ((d00*(1-tx)+d10*tx)*(1-ty)+(d01*(1-tx)+d11*tx)*ty)*c/3; }
REAL.edgeDist=function(x,y){ if(!rbInit()) return 1e4; var d=rbDist(x,y); return d>=1e4?-1e4:REAL.BUFFER-d; };
REAL.dataOk=function(x,y){ var S=window._palStreet; if(!S||!S.ready||!S.ready()||!S.inScope) return true; var Hm=S.toMap(0,0,1)[1]; return S.inScope(x,Hm-y); };
REAL.inBounds=function(x,y){ if(!rbInit()) return true; return rbDist(x,y)<=REAL.BUFFER && REAL.dataOk(x,y); };
REAL.clamp=function(x,y,o){ o=o||{}; o.x=x; o.y=y; o.moved=false; o.d=0; if(!rbInit()||REAL.inBounds(x,y)) return o;
  var c=RB.c, w=RB.w, h=RB.h, D=RB.D, ci=Math.floor((x-RB.x0)/c), cj=Math.floor((y-RB.y0)/c), best=1e30, bx=0, by=0, R=Math.min(80,Math.max(w,h));
  ci=Math.max(0,Math.min(w-1,ci)); cj=Math.max(0,Math.min(h-1,cj));
  for(var r=0;r<=R;r++){ var found=false; for(var j=cj-r;j<=cj+r;j++) for(var i=ci-r;i<=ci+r;i++){ if(Math.max(Math.abs(i-ci),Math.abs(j-cj))!==r||i<0||j<0||i>=w||j>=h||D[j*w+i]!==0) continue;
      var px=RB.x0+(i+.5)*c, py=RB.y0+(j+.5)*c, d2=(px-x)*(px-x)+(py-y)*(py-y); if(d2<best){ best=d2; bx=px; by=py; found=true; } } if(found && r>=2) break; }
  if(best>=1e30) return o; var L=Math.sqrt(best), n=Math.max(1,Math.ceil(L/4)), t, qx=bx, qy=by;      /* walk from the nearest core cell out toward the point until the edge */
  for(t=1;t<=n;t++){ var u=t/n, ax=bx+(x-bx)*u, ay=by+(y-by)*u; if(!REAL.inBounds(ax,ay)) break; qx=ax; qy=ay; }
  o.x=qx; o.y=qy; o.moved=true; o.d=Math.hypot(qx-x,qy-y); return o; };
/* does the whole page path of a leg stay in bounds (a sample every 30 page px, and its ends)? */
REAL.legInBounds=function(D,step){ if(!D||!D.L) return {ok:false,n:0,out:0}; step=step||30; var p={x:0,y:0}, o={x:0,y:0,k:0}, n=0, out=0, first=-1;
  for(var s=0;s<=D.L+step;s+=step){ pathAt(D,Math.min(s,D.L),p); realOf(p.x,p.y,o); n++; if(!REAL.inBounds(o.x,o.y)){ out++; if(first<0) first=s; } if(s>=D.L) break; }
  return {ok:out===0, n:n, out:out, first:first}; };
"""
