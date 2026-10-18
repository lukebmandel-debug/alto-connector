"""Water in the real-geometry ride (2.0.1): the rivers, ponds, docks, fountains, pools, piers and bridges of the street data (palace_street_water.py) drawn and walked.

Loading: REAL.fromStreet / REAL.load are wrapped so the water keys (q v o k) of the loaded cells ride along with the blob (RWT, in WORLD units = metres x K).
Gather: realWater(W, cx, cy, R) (called by gatherRealG after the landmarks) puts the pieces near the camera on W.rw and drops one MARKER per GL cell they touch into
W.water ({rw:1, x0=x1=cx, w:0}: a zero-length piece, so the lattice-world users of W.water — the 2D fallback, the scenery's obstacle grid, riverRails — ignore it; glBase
skips it) so glPlan makes and hashes that cell.
Ground: realWaterBase(b, cell, W) replaces the cell's paving slab where water lies: a SCANLINE split of the cell (every vertex y, every crossing with the cell's sides and
between edges) into trapezoids, each land or water by the NON-ZERO winding of the oriented pieces (union of overlapping water, islands as clockwise holes) — exact,
watertight, no triangulation of the river. Land is paving at z 0 (as before), river water lies D below it (river / dock / canal 2.8 m, ponds 0.6 m) with quay walls
(a dark wet line at the foot), a coping, a grass verge and, along rivers, an iron railing. Fountains and pools stand on the ground (a rim and a raised basin, jets).
Bridges: a road way flagged bridge gets fascia, railings and piers in the water (realBridgeSeg, called from glBase's road loop). Piers / quays: decks over the water.
Walking: realWaterHit(x, y, W, pr) — in the water (any probe of the player circle) and not on a bridge deck or a pier is blocked (palace_ride_e.py blockedAt).
No blending, no screen-space dither: the water is the opaque id-10 material of the world shader (Fresnel sky, filtered ripples, glint).
"""
from __future__ import annotations

JS_WATER = r"""
/* ── water (palace_ride_water.py) ── */
var RWT={pcs:[], strips:[], fo:[], piers:[], gen:0};
function rwDepth(k,area){ if(k==='fountain'||k==='pool') return 0; if(k==='river'||k==='dock'||k==='canal') return 2.8; if(k==='water'&&area>20000) return 2.8; return .6; }
function rwArea(r){ var a=0, n=r.length/2; for(var i=0,j=n-1;i<n;j=i++) a+=r[2*j]*r[2*i+1]-r[2*i]*r[2*j+1]; return a/2; }
function rwBB(r){ var x0=1e9,y0=1e9,x1=-1e9,y1=-1e9; for(var i=0;i<r.length;i+=2){ if(r[i]<x0)x0=r[i]; if(r[i]>x1)x1=r[i]; if(r[i+1]<y0)y0=r[i+1]; if(r[i+1]>y1)y1=r[i+1]; } return [x0,y0,x1,y1]; }
(function(){ var fs=REAL.fromStreet, ld=REAL.load;
  REAL.fromStreet=function(pts,r){ var o=fs(pts,r); try{ var S=window._palStreet, seen=new Set(), q=[], vv=[], fo=[], kk=[], Hm=S.toMap(0,0,1)[1];
      function mp(a){ var g=[]; for(var i=0;i<a.length;i++){ var m=S.toMap(a[i][0],a[i][1],1); g.push(m[0],m[1]); } return g; }
      pts.forEach(function(p){ var N=S.near(p[0],Hm-p[1],(r||520)+250,'qvok');
        (N.q||[]).forEach(function(d){ if(seen.has(d)||!d.ring||d.ring.length<3) return; seen.add(d); var cb=d.cb, t=.15, n=d.ring.length, e=[];
          for(var i=0;i<n;i++){ var a=d.ring[i], b=d.ring[(i+1)%n];       /* an edge along the 500 m cell border is where the river was cut, not a bank */
            e.push(cb&&((Math.abs(a[0]-cb[0])<t&&Math.abs(b[0]-cb[0])<t)||(Math.abs(a[0]-cb[2])<t&&Math.abs(b[0]-cb[2])<t)||(Math.abs(a[1]-cb[1])<t&&Math.abs(b[1]-cb[1])<t)||(Math.abs(a[1]-cb[3])<t&&Math.abs(b[1]-cb[3])<t))?1:0); }
          q.push({k:d.k||'water', nm:d.nm||'', h:d.h||0, ring:mp(d.ring), cut:e}); });
        (N.v||[]).forEach(function(d){ if(seen.has(d)||d.k==='river') return; seen.add(d); vv.push({k:d.k, w:d.wd||(d.k==='canal'?6:d.k==='stream'?2.5:1.2), line:mp(d.line)}); });
        (N.o||[]).forEach(function(d){ if(seen.has(d)) return; seen.add(d); var m=S.toMap(d.x,d.y,1); fo.push([m[0],m[1],d.kind]); });
        (N.k||[]).forEach(function(d){ if(seen.has(d)||d.k==='bridge'||d.k==='breakwater') return; seen.add(d); kk.push({k:d.k, c:d.c, w:d.wd||(d.k==='pier'?4:0), g:mp(d.ring||d.line)}); }); });
      o.wq=q; o.wv=vv; o.wo=fo; o.wk=kk; }catch(x){ if(window.console) console.warn('water', x); } return o; };
  REAL.load=function(blob){ var res=ld(blob); RWT.pcs=[]; RWT.strips=[]; RWT.fo=[]; RWT.piers=[]; RWT.gen++;
    (blob.wq||[]).forEach(function(p){ var wr=p.ring.map(function(v){ return v*K; }), am=Math.abs(rwArea(p.ring)), D=rwDepth(p.k,am);
      RWT.pcs.push({k:p.k, nm:p.nm, h:p.h, r:wr, cut:p.cut, bb:rwBB(wr), D:D*K, sunk:D>0, raise:p.k==='fountain'?.38*K:p.k==='pool'?.08*K:0, am:am}); });
    (blob.wv||[]).forEach(function(v){ RWT.strips.push({w:v.w*K, g:v.line.map(function(x){ return x*K; })}); });
    (blob.wo||[]).forEach(function(f){ RWT.fo.push([f[0]*K,f[1]*K,f[2]]); });
    (blob.wk||[]).forEach(function(s){ var g=s.g.map(function(x){ return x*K; }); RWT.piers.push({k:s.k, c:s.c, w:s.w*K, g:g, bb:rwBB(g)}); });
    return res; };
})();
/* the water near the camera (map metres cx, cy; R metres) onto W.rw, and a marker per GL cell it touches */
function realWater(W,cx,cy,R){
  if(!RWT.pcs.length && !RWT.fo.length && !RWT.strips.length) return;
  var X0=(cx-R)*K, X1=(cx+R)*K, Y0=(cy-R)*K, Y1=(cy+R)*K, pcs=[], mk={};
  function mark(bb,h){ for(var ci=Math.floor(Math.max(bb[0],X0)/CELL); ci<=Math.floor(Math.min(bb[2],X1)/CELL); ci++) for(var cj=Math.floor(Math.max(bb[1],Y0)/CELL); cj<=Math.floor(Math.min(bb[3],Y1)/CELL); cj++){ var k=ci+','+cj; mk[k]=(mk[k]||0)+h; } }
  RWT.pcs.forEach(function(p,i){ var bb=p.bb; if(bb[2]<X0-200||bb[0]>X1+200||bb[3]<Y0-200||bb[1]>Y1+200) return; pcs.push(p); mark(bb,(p.r.length*7+Math.round(p.r[0]*3)+Math.round(p.r[1]))%100003); });
  var fo=RWT.fo.filter(function(f){ return f[0]>X0&&f[0]<X1&&f[1]>Y0&&f[1]<Y1; }); fo.forEach(function(f){ mark([f[0],f[1],f[0],f[1]],11); });
  var st=RWT.strips.filter(function(s){ var bb=rwBB(s.g); s.bb=bb; return !(bb[2]<X0||bb[0]>X1||bb[3]<Y0||bb[1]>Y1); }); st.forEach(function(s){ mark(s.bb,s.g.length); });
  var pr=RWT.piers.filter(function(s){ var bb=s.bb; return !(bb[2]<X0||bb[0]>X1||bb[3]<Y0||bb[1]>Y1); }); pr.forEach(function(s){ mark(s.bb,s.g.length*3); });
  W.rw=W.real.rw={pcs:pcs, fo:fo, strips:st, piers:pr, idx:null, br:null};      /* on W.real too: the roam's world swap (palace_ride_e.py realFinish) carries W.real over */
  Object.keys(mk).forEach(function(k){ var q=k.split(','), x=(+q[0]+.5)*CELL, y=(+q[1]+.5)*CELL; W.water.push({rw:1, x0:x, y0:y, x1:x, y1:y, w:0, cx:x, cy:y, r:0, h:mk[k]}); });
  /* no grass park drawn over a river: a park whose middle lies in sunk water is dropped */
  if(pcs.length && W.parks.length) W.parks=W.parks.filter(function(p){ return !rwIn(W,p.cx,p.cy); });
}
/* the winding number of the SUNK water at (x,y) (world units): a row index of edges, built once per world */
function rwInR(x,y,r){ var c=false, n=r.length/2; for(var i=0,j=n-1;i<n;j=i++){ var xi=r[2*i], yi=r[2*i+1], xj=r[2*j], yj=r[2*j+1]; if((yi>y)!==(yj>y) && x<(xj-xi)*(y-yi)/(yj-yi)+xi) c=!c; } return c; }
function rwSegD(x,y,ax,ay,bx,by){ var dx=bx-ax, dy=by-ay, L2=dx*dx+dy*dy, t=L2>1e-9?((x-ax)*dx+(y-ay)*dy)/L2:0; t=t<0?0:t>1?1:t; return Math.hypot(ax+t*dx-x,ay+t*dy-y); }
function rwOf(W){ return W&&(W.rw||(W.real&&W.real.rw))||null; }
function rwIndex(W){ var R=rwOf(W); if(R.idx) return R.idx; var I={}, G=8;
  R.pcs.forEach(function(p){ if(!p.sunk) return; var r=p.r, n=r.length/2; for(var i=0;i<n;i++){ var j=(i+1)%n, ay=r[2*i+1], by=r[2*j+1]; if(ay===by) continue; var e=[r[2*i],ay,r[2*j],by];
    for(var g=Math.floor(Math.min(ay,by)/G); g<=Math.floor(Math.max(ay,by)/G); g++) (I[g]||(I[g]=[])).push(e); } });
  R.idx=I; return I; }
function rwIn(W,x,y){ var R0=rwOf(W); if(!R0||!R0.pcs.length) return false; var L=rwIndex(W)[Math.floor(y/8)], w=0; if(!L) return false;
  for(var i=0;i<L.length;i++){ var e=L[i]; if((e[1]>y)===(e[3]>y)) continue; var xc=e[0]+(e[2]-e[0])*(y-e[1])/(e[3]-e[1]); if(xc>x) w+=e[3]>e[1]?1:-1; } return w!==0; }
function rwOnDeck(W,x,y){ var R=rwOf(W);
  if(!R.br){ R.br=(W.roads||[]).filter(function(o){ return o.br; }); }
  for(var i=0;i<R.br.length;i++){ var o=R.br[i], hw=o.w/2+3.4*K; if(rwSegD(x,y,o.x0,o.y0,o.x1,o.y1)<hw) return true; }
  for(i=0;i<R.piers.length;i++){ var s=R.piers[i]; if(x<s.bb[0]-s.w||x>s.bb[2]+s.w||y<s.bb[1]-s.w||y>s.bb[3]+s.w) continue;
    if(s.c){ if(rwInR(x,y,s.g)) return true; } else for(var k=0;k+3<s.g.length;k+=2) if(rwSegD(x,y,s.g[k],s.g[k+1],s.g[k+2],s.g[k+3])<s.w/2) return true; }
  return false; }
/* the walker: blocked in the water (any of five probes of his circle) unless on a bridge deck or a pier; a fountain basin is blocked too */
function realWaterHit(x,y,W,pr){ var R=rwOf(W); if(!R) return false; var m=(pr||.6)*.8;
  var hit=rwIn(W,x,y)||rwIn(W,x+m,y)||rwIn(W,x-m,y)||rwIn(W,x,y+m)||rwIn(W,x,y-m);
  if(!hit){ for(var i=0;i<R.pcs.length;i++){ var p=R.pcs[i]; if(p.sunk||p.k!=='fountain') continue; if(x<p.bb[0]-m||x>p.bb[2]+m||y<p.bb[1]-m||y>p.bb[3]+m) continue; if(rwInR(x,y,p.r)) return true; }
    for(i=0;i<R.fo.length;i++) if(Math.hypot(x-R.fo[i][0],y-R.fo[i][1])<3.2*K+m) return true; return false; }
  return !rwOnDeck(W,x,y); }
/* a railing along A->B, set back `off` on the side (sx,sy): posts every 2.4 m, a top and a middle rail (thin double-faced bars), dark iron */
function rwRail(b,ax,ay,bx,by,z,h){ var dx=bx-ax, dy=by-ay, L=Math.hypot(dx,dy); if(L<.3) return; var ux=dx/L, uy=dy/L, nx=-uy, ny=ux, P=2.4*K, k;
  [[h-.06*K,h],[h*.48,h*.48+.05*K]].forEach(function(r){ gquad(b,[ax,ay,z+r[0]],[bx,by,z+r[0]],[bx,by,z+r[1]],[ax,ay,z+r[1]],nx,ny,0,0,L/UM,0,.1,6,.2); gquad(b,[bx,by,z+r[0]],[ax,ay,z+r[0]],[ax,ay,z+r[1]],[bx,by,z+r[1]],-nx,-ny,0,0,L/UM,0,.1,6,.2); });
  for(k=P*.5;k<L;k+=P) gbox(b,ax+ux*k,ay+uy*k,.035*K,.035*K,z,z+h,Math.atan2(uy,ux),6,.2,false); }
/* the ground of a cell with water: land (paving) and sunk water by a scanline split, then banks, verges and railings; raised basins; streams; piers */
function realWaterBase(b,cell,W){
  var R=rwOf(W); if(!R) return false; var x0=cell.ci*CELL, y0=cell.cj*CELL, x1=x0+CELL, y1=y0+CELL, E=[], D=0, river=false, P=[], i, j;
  R.pcs.forEach(function(p){ var bb=p.bb; if(bb[2]<x0||bb[0]>x1||bb[3]<y0||bb[1]>y1) return; P.push(p); if(!p.sunk) return; if(p.D>D) D=p.D; if(p.D>1.5*K) river=true;
    var r=p.r, n=r.length/2; for(var a=0;a<n;a++){ var c=(a+1)%n, ay=r[2*a+1], by=r[2*c+1]; if(ay===by||Math.max(ay,by)<y0||Math.min(ay,by)>y1) continue; E.push({ax:r[2*a],ay:ay,bx:r[2*c],by:by,d:by>ay?1:-1}); } });
  var sunk=E.length>0;
  if(!sunk) gflat(b,[x0,y0,x1,y0,x1,y1,x0,y1],0,12,0,true);
  else {
    var ys=[y0,y1], k;
    function addY(y){ if(y>y0&&y<y1) ys.push(y); }
    for(i=0;i<E.length;i++){ var e=E[i]; addY(e.ay); addY(e.by); [x0,x1].forEach(function(X){ if((e.ax-X)*(e.bx-X)<0) addY(e.ay+(e.by-e.ay)*(X-e.ax)/(e.bx-e.ax)); }); }
    if(E.length<900) for(i=0;i<E.length;i++) for(j=i+1;j<E.length;j++){ var p=E[i], q=E[j];
      if(Math.max(p.ax,p.bx)<Math.min(q.ax,q.bx)||Math.max(q.ax,q.bx)<Math.min(p.ax,p.bx)||Math.max(p.ay,p.by)<Math.min(q.ay,q.by)||Math.max(q.ay,q.by)<Math.min(p.ay,p.by)) continue;
      var rx=p.bx-p.ax, ry=p.by-p.ay, sx=q.bx-q.ax, sy=q.by-q.ay, den=rx*sy-ry*sx; if(Math.abs(den)<1e-9) continue; var t=((q.ax-p.ax)*sy-(q.ay-p.ay)*sx)/den, u=((q.ax-p.ax)*ry-(q.ay-p.ay)*rx)/den;
      if(t>1e-6&&t<1-1e-6&&u>1e-6&&u<1-1e-6) addY(p.ay+ry*t); }
    ys.sort(function(a,c){ return a-c; });
    var zW=-D;
    function trap(lxa,lxb,rxa,rxb,ya,yb,wet){ if(rxa-lxa<1e-4&&rxb-lxb<1e-4) return; var z=wet?zW:0, pk=wet?10:12;
      gtri(b,[lxa,ya,z],[rxa,ya,z],[rxb,yb,z],0,0,1,0,0,0,0,0,0,pk,0); gtri(b,[lxa,ya,z],[rxb,yb,z],[lxb,yb,z],0,0,1,0,0,0,0,0,0,pk,0); }
    function cl(x){ return x<x0?x0:x>x1?x1:x; }
    for(k=0;k+1<ys.length;k++){ var ya=ys[k], yb=ys[k+1]; if(yb-ya<1e-4) continue; var act=[];
      for(i=0;i<E.length;i++){ var e2=E[i], lo=Math.min(e2.ay,e2.by), hi=Math.max(e2.ay,e2.by); if(lo>ya+1e-6||hi<yb-1e-6) continue;
        var xa=e2.ax+(e2.bx-e2.ax)*(ya-e2.ay)/(e2.by-e2.ay), xb=e2.ax+(e2.bx-e2.ax)*(yb-e2.ay)/(e2.by-e2.ay); act.push([xa+xb,xa,xb,e2.d]); }
      act.sort(function(p2,q2){ return p2[0]-q2[0]; });
      var w=0, la=x0, lb=x0;
      for(i=0;i<act.length;i++){ var ra=cl(act[i][1]), rb=cl(act[i][2]); trap(la,lb,ra,rb,ya,yb,w!==0); w+=act[i][3]; la=ra; lb=rb; }
      trap(la,lb,x1,x1,ya,yb,w!==0); }
    /* the banks: every real edge (not a cut) whose middle is in this cell: a quay wall down to the water facing it (a dark wet line at the foot), a coping,
       a grass verge on the land and, along a river, a railing */
    P.forEach(function(p){ if(!p.sunk) return; var r=p.r, n=r.length/2, Dp=D, rv=p.D>1.5*K;
      for(var a=0;a<n;a++){ if(p.cut[a]) continue; var c=(a+1)%n, ax=r[2*a], ay=r[2*a+1], bx=r[2*c], by=r[2*c+1], mx=(ax+bx)/2, my=(ay+by)/2;
        if(mx<x0||mx>=x1||my<y0||my>=y1) continue; var dx=bx-ax, dy=by-ay, L=Math.hypot(dx,dy); if(L<.05) continue; var wx=dy/L, wy=-dx/L;   /* toward the water */
        if(rwIn(W,mx-wx*.6*K,my-wy*.6*K)) continue;                                   /* water both sides (two overlapping pieces): no bank here */
        var wet=Math.min(.55*K,Dp*.4);
        gquad(b,[ax,ay,-Dp],[bx,by,-Dp],[bx,by,-Dp+wet],[ax,ay,-Dp+wet],wx,wy,0,0,L/UM,0,wet/UM,11,0);
        gquad(b,[ax,ay,-Dp+wet],[bx,by,-Dp+wet],[bx,by,.12],[ax,ay,.12],wx,wy,0,0,L/UM,0,(Dp+.12)/UM,12,0);
        var cw=.45*K, gw=rv?2.6*K:1.4*K;
        gquad(b,[ax,ay,.12],[bx,by,.12],[bx-wx*cw,by-wy*cw,.12],[ax-wx*cw,ay-wy*cw,.12],0,0,1,0,1,0,1,12,0);
        gquad(b,[ax-wx*cw,ay-wy*cw,.12],[bx-wx*cw,by-wy*cw,.12],[bx-wx*cw,by-wy*cw,0],[ax-wx*cw,ay-wy*cw,0],-wx,-wy,0,0,L/UM,0,.1,12,0);
        gquad(b,[ax-wx*cw,ay-wy*cw,.03],[bx-wx*cw,by-wy*cw,.03],[bx-wx*(cw+gw),by-wy*(cw+gw),.03],[ax-wx*(cw+gw),ay-wy*(cw+gw),.03],0,0,1,0,1,0,1,13+128,0);
        if(rv) rwRail(b,ax-wx*.2*K,ay-wy*.2*K,bx-wx*.2*K,by-wy*.2*K,.12,1.08*K); } }); }
  /* raised water: fountain basins and pools (a rim and the water a little above the ground; a jet in a fountain) */
  P.forEach(function(p){ if(p.sunk) return; var r=p.r, n=r.length/2, cxp=0, cyp=0; for(var a=0;a<n;a++){ cxp+=r[2*a]/n; cyp+=r[2*a+1]/n; } if(cxp<x0||cxp>=x1||cyp<y0||cyp>=y1) return;
    var rim=p.k==='fountain'?.5*K:.14*K; for(var a2=0;a2<n;a2++){ if(p.cut[a2]) continue; var c2=(a2+1)%n, ax=r[2*a2], ay=r[2*a2+1], bx=r[2*c2], by=r[2*c2+1], L=Math.hypot(bx-ax,by-ay); if(L<.05) continue; var ox=-(by-ay)/L, oy=(bx-ax)/L;
      gquad(b,[ax,ay,0],[bx,by,0],[bx,by,rim],[ax,ay,rim],ox,oy,0,0,L/UM,0,rim/UM,2,0); gquad(b,[ax,ay,0],[bx,by,0],[bx,by,rim],[ax,ay,rim],-ox,-oy,0,0,L/UM,0,rim/UM,2,0); }
    gflat(b,r,p.raise,10,0,true);
    if(p.k==='fountain') rwJet(b,cxp,cyp,Math.min(3.2*K,Math.sqrt(p.am)*.35*K)); });
  R.fo.forEach(function(f){ if(f[0]<x0||f[0]>=x1||f[1]<y0||f[1]>=y1) return; var rr=2.6*K, g=[]; for(var a=0;a<16;a++) g.push(f[0]+Math.cos(a/16*6.2832)*rr,f[1]+Math.sin(a/16*6.2832)*rr);
    for(a=0;a<16;a++){ var c=(a+1)%16, ox=Math.cos((a+.5)/16*6.2832), oy=Math.sin((a+.5)/16*6.2832); gquad(b,[g[2*a],g[2*a+1],0],[g[2*c],g[2*c+1],0],[g[2*c],g[2*c+1],.5*K],[g[2*a],g[2*a+1],.5*K],ox,oy,0,0,1,0,.4,2,0); }
    gflat(b,g,.38*K,10,0,true); rwJet(b,f[0],f[1],2.4*K); });
  /* streams and small canals: a water ribbon on the ground */
  R.strips.forEach(function(s){ var g=s.g; for(var a=0;a+3<g.length;a+=2){ var mx=(g[a]+g[a+2])/2, my=(g[a+1]+g[a+3])/2; if(mx<x0||mx>=x1||my<y0||my>=y1) continue; if(sunk&&rwIn(W,mx,my)) continue; gflat(b,glStrip(g[a],g[a+1],g[a+2],g[a+3],s.w,.5),.025,10+64,0,true); } });
  /* piers and quays: a deck just above the ground over the water, its sides down to the water */
  R.piers.forEach(function(s){ var g=s.g, z=.22*K, Dp=Math.max(D,1.2*K);
    if(s.c){ var n=g.length/2, cxp=0, cyp=0; for(var a=0;a<n;a++){ cxp+=g[2*a]/n; cyp+=g[2*a+1]/n; } if(cxp<x0||cxp>=x1||cyp<y0||cyp>=y1) return; gflat(b,g,z,9,0,true);
      for(a=0;a<n;a++){ var c=(a+1)%n, L=Math.hypot(g[2*c]-g[2*a],g[2*c+1]-g[2*a+1]); if(L<.05) continue; var ox=-(g[2*c+1]-g[2*a+1])/L, oy=(g[2*c]-g[2*a])/L;
        gquad(b,[g[2*a],g[2*a+1],-Dp],[g[2*c],g[2*c+1],-Dp],[g[2*c],g[2*c+1],z],[g[2*a],g[2*a+1],z],ox,oy,0,0,L/UM,0,1,12,0); gquad(b,[g[2*a],g[2*a+1],-Dp],[g[2*c],g[2*c+1],-Dp],[g[2*c],g[2*c+1],z],[g[2*a],g[2*a+1],z],-ox,-oy,0,0,L/UM,0,1,12,0); } }
    else for(var a3=0;a3+3<g.length;a3+=2){ var mx=(g[a3]+g[a3+2])/2, my=(g[a3+1]+g[a3+3])/2; if(mx<x0||mx>=x1||my<y0||my>=y1) continue; var q=glStrip(g[a3],g[a3+1],g[a3+2],g[a3+3],Math.max(s.w,1.5*K),0); gflat(b,q,z,9,0,true);
      for(var e3=0;e3<4;e3++){ var c3=(e3+1)%4, L3=Math.hypot(q[2*c3]-q[2*e3],q[2*c3+1]-q[2*e3+1]); if(L3<.05) continue; var nx3=-(q[2*c3+1]-q[2*e3+1])/L3, ny3=(q[2*c3]-q[2*e3])/L3; gquad(b,[q[2*e3],q[2*e3+1],-Dp],[q[2*c3],q[2*c3+1],-Dp],[q[2*c3],q[2*c3+1],z],[q[2*e3],q[2*e3+1],z],nx3,ny3,0,0,L3/UM,0,1,12,0); gquad(b,[q[2*e3],q[2*e3+1],-Dp],[q[2*c3],q[2*c3+1],-Dp],[q[2*c3],q[2*c3+1],z],[q[2*e3],q[2*e3+1],z],-nx3,-ny3,0,0,L3/UM,0,1,12,0); } } });
  return true; }
/* a fountain jet: a slim column of water rising h and a wider crown of spray (the water material: its ripples move with time) */
function rwJet(b,x,y,h){ var s=6, a, r0=.12*K, r1=.05*K;
  for(a=0;a<s;a++){ var t0=a/s*6.2832, t1=(a+1)/s*6.2832, c0=Math.cos(t0), s0=Math.sin(t0), c1=Math.cos(t1), s1=Math.sin(t1), nx=Math.cos((t0+t1)/2), ny=Math.sin((t0+t1)/2);
    gquad(b,[x+c0*r0,y+s0*r0,.3*K],[x+c1*r0,y+s1*r0,.3*K],[x+c1*r1,y+s1*r1,h],[x+c0*r1,y+s0*r1,h],nx,ny,0,0,1,0,h/UM,10,0);
    var R0=.06*K, R1=.42*K, z0=h, z1=h*.82;                                         /* the crown falls back outward */
    gquad(b,[x+c0*R0,y+s0*R0,z0+.15*K],[x+c1*R0,y+s1*R0,z0+.15*K],[x+c1*R1,y+s1*R1,z1],[x+c0*R1,y+s0*R1,z1],nx,ny,.6,0,1,0,1,10,0); } }
/* a bridge way's deck edges: fascia under the sidewalks, railings on both edges, piers down into the water every ~38 m */
function realBridgeSeg(b,o,W){
  /* only where the deck's edge has water beyond it (and no other deck): a dual carriageway, its footways and ramps would otherwise fence each other in */
  var dx=o.x1-o.x0, dy=o.y1-o.y0, L=Math.hypot(dx,dy); if(L<.5||!rwOf(W)) return; var ux=dx/L, uy=dy/L, nx=-uy, ny=ux, hw=o.w/2+3.4*K, th=1.3*K, P=2.4*K, k;
  function open(x,y){ return rwIn(W,x,y) && !rwOnDeck(W,x,y); }
  [-1,1].forEach(function(s){ var run=-1;
    for(k=0;k<=L+1e-6;k+=Math.min(P,L)){ var t=Math.min(k,L), ok=k<L && open(o.x0+ux*(t+P/2)+nx*s*(hw+1.2*K),o.y0+uy*(t+P/2)+ny*s*(hw+1.2*K));
      if(ok&&run<0) run=t; if((!ok||k+P>L)&&run>=0){ var t1=ok?L:t, ax=o.x0+ux*run+nx*hw*s, ay=o.y0+uy*run+ny*hw*s, bx=o.x0+ux*t1+nx*hw*s, by=o.y0+uy*t1+ny*hw*s, Lr=Math.hypot(bx-ax,by-ay);
        if(Lr>.2){ gquad(b,[ax,ay,-th],[bx,by,-th],[bx,by,GZ_SIDE+.02],[ax,ay,GZ_SIDE+.02],nx*s,ny*s,0,0,Lr/UM,0,1,12,0);
          var ix=ax-nx*s*.25*K, iy=ay-ny*s*.25*K, jx=bx-nx*s*.25*K, jy=by-ny*s*.25*K; rwRail(b,ix,iy,jx,jy,GZ_SIDE,1.1*K);
          gquad(b,[ax,ay,GZ_SIDE+.02],[bx,by,GZ_SIDE+.02],[jx,jy,GZ_SIDE+.02],[ix,iy,GZ_SIDE+.02],0,0,1,0,1,0,1,12+64,0); }
        run=-1; } } });
  if(!rwIn(W,(o.x0+o.x1)/2,(o.y0+o.y1)/2)&&!rwIn(W,o.x0,o.y0)&&!rwIn(W,o.x1,o.y1)) return;
  gquad(b,[o.x0-nx*hw,o.y0-ny*hw,-th],[o.x1-nx*hw,o.y1-ny*hw,-th],[o.x1+nx*hw,o.y1+ny*hw,-th],[o.x0+nx*hw,o.y0+ny*hw,-th],0,0,-1,0,1,0,1,12,0);
  var PP=38*K;
  for(k=Math.ceil((o.x0*ux+o.y0*uy)/PP)*PP-(o.x0*ux+o.y0*uy); k<L; k+=PP){ var px=o.x0+ux*k, py=o.y0+uy*k; if(!rwIn(W,px,py)) continue; gbox(b,px,py,1.1*K,hw*.8,-4*K,-th,Math.atan2(uy,ux),12,0,false); } }
REAL.waterAt=function(W,x,y){ return rwIn(W,x,y); }; REAL.waterHit=function(W,x,y,pr){ return realWaterHit(x,y,W,pr); };       /* (tests, the views harness) world units */
"""
