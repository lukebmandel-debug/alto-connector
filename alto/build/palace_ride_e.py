"""Part E of the first-person ride: ROAM - walk anywhere in the city at street level (owner: the roam agent).

window._palRide.roam = { enter(x, y, heading, opts), exit(stay), active(), ... }

  enter(x, y, heading, opts)   x, y in map units; heading = a yaw in the renderer's convention (atan2(fy, fx), map y points south, so 0 = east,
                               -PI/2 = north) or null to face along the nearest street. opts: {view: the aerial view to restore on exit (default:
                               E.curView() now), hold: true to not start the frame loop (tests drive it with tick/sim)}. Returns true when started
                               (false when a ride is on screen, the page has no palace, or the page is a phone).
  exit(stay)                   stay falsy: the aerial map goes back exactly as it was (E.putView of the view saved at enter, like a ride);
                               stay truthy: the map recentres on where you stood (same zoom), the pattern of palace.py flyMap/center.
  active()

Controls: W A S D / Up Down move (A D strafe), Left Right turn, drag the mouse to look (the scene follows the pointer, like Street View; yaw + a little pitch), Esc leaves.
  Pace (1.9.100 / FPV phase 1; 1 m = UM = 1.3 map units): a walk is 14 units/s (about 11 m/s: a city is too big for a person's real pace, 1.9.100 shipped 1.5 m/s and was unusable), holding Shift is 40 units/s, and holding Shift for a few seconds eases into 60;
  the eye is 1.65 m up (2.15 units) and bobs only while walking, one bob per footfall; the view is Street View's (90 degrees across, palace_ride_b fpFoc).
  E (or a click on the door, or the place pin) goes in through the door of a node building you are facing within ~12 units: palace_ride_door.py (JS_DOORS, spliced in below).
Every key except browser shortcuts (Cmd/Ctrl/Alt combinations) and Tab is swallowed in the capture phase while roaming (stopImmediatePropagation),
so the page under the overlay never sees it; the listeners are installed at load, ahead of every other window-level capture handler.

Where you can walk (documented choices):
  * everywhere that is not inside a building footprint ring (W.solids kinds b / node / fill / lm, or any solid flagged .collide), kept PR (2.4 units, a
    little more than the renderer's near plane) away from the wall; streets, sidewalks, parks and empty lots are all open;
  * not in the water: a river (M.river polyline, drawn with w + 34 units) is closed to within 8 + PR units of its drawn edge (you stop on the bank, not at the water line); a BRIDGE is a street that the
    data marks as crossing water (M.streets o / br - today the five Schuylkill bridges), and a corridor of DECK_HW (9.5) either side of its centre line is
    open over the water, so you can walk across with the deck's edges acting as walls. M.bank.bridges (Ben Franklin Bridge) has no street geometry in
    the current data and highway decks are not walkable, so neither crosses the water;
  * not outside the city rectangle (M.W x M.H).
Collision is a signed test of the whole player circle at the new position (never partial): a step is committed only if the circle at its end is free,
else the step is cut back to the contact point (binary search) and the rest of the move slides along the wall (normal found by sampling the free
circle around the contact), so the position can never end inside a ring.

Streaming: the world is built cell by cell (gatherWorld on a one-cell set, nearest cells first, at most a few ms per frame) for every 300-unit cell whose
box is within LOAD units of the camera, merged into ONE persistent world object that is handed to drawCity (arrays replaced in place, `ver` bumped, per-cell
worlds in `cells` for a renderer that caches by cell). Cells far behind are dropped beyond KEEP, so nothing pops inside the fog. Nothing is rebuilt
for a cell that stays loaded.
"""

from .palace_ride_door import CSS_DOOR, JS_DOORS
from .palace_ride_inside import CSS_INSIDE, JS_INSIDE, JS_INSIDE_GL      # FPV phase 2: looking up / down, going inside a node building

_JS_E = r"""
var ROAM=(function(){
var CFG={ eye:2.15, PR:2.4, PRGL:1.3, walk:14, brisk:40, jog:60, hurryAfter:2.2, hurryRamp:1.6, tau:.16, turn:1.9, load:1450, keep:1900, sync:520, budget:3.2, grab:true, lookX:.0042, lookY:.0034, pitchMax:1.4835, pitch0:-.03, edge:8,
  waterGap:17, waterOff:8, deckHW:9.5, bob:.03, crossAt:34, gridC:160, stayZoom:.6 };
var MXC=90;                                     /* palace.py MX = MY = 90: the margin round the drawn city; scroll = (x + MX) * zoom + gap - viewport / 2 */
var S={ on:false, hold:false, x:0, y:0, yaw:0, pitch:0, vx:0, vy:0, run:false, hurry:0, keys:{}, tm:0, last:0, raf:0, phase:0, walked:0, speed:0, drag:null, cells:{}, queue:[], bigs:[],
  W:null, real:null, plan:{x:-1e9,y:-1e9}, dirty:false, built:0, evicted:0, merges:0, plans:0, bms:[], lbms:[], mms:[], fr:[], view:null, hud:null, hudAt:0, hint:0, lastDark:null, spawned:null, sync:false, ver:0, loc:null, said:'' };
var QUAL=['b','node','fill','lm'], BIGR=CELL*.4;
/* the player circle: 1.3 units (1 m) with the GL renderer, whose near plane is .5 (palace_ride_gl.py GL_NEAR) so a wall can be walked right up to; 2.4 for the 2D fallback (near plane 1.8) */
function PRX(){ return S.pr||CFG.PR; }

/* \u2500\u2500 the page's data indexes, built once on first use \u2500\u2500 */
var IDX=null;
function cellOf(v){ return Math.floor(v/CFG.gridC); }
function buildIdx(){
  var M=E.M, I={ riv:{}, decks:[], st:{}, stN:0 }, i, k;
  /* rivers: each segment under the cells it can reach (its drawn half width + the gap + the player radius) */
  (M.river||[]).forEach(function(rv, ri){ var p=rv.p||[], lim=(rv.w||100)/2+CFG.waterGap+CFG.waterOff+PRX();
    for(i=0;i+3<p.length;i+=2){ var x0=p[i], y0=p[i+1], x1=p[i+2], y1=p[i+3], seg={x0:x0,y0:y0,x1:x1,y1:y1,lim:lim,l2:Math.max(1e-9,(x1-x0)*(x1-x0)+(y1-y0)*(y1-y0))};
      for(var cx=cellOf(Math.min(x0,x1)-lim); cx<=cellOf(Math.max(x0,x1)+lim); cx++) for(var cy=cellOf(Math.min(y0,y1)-lim); cy<=cellOf(Math.max(y0,y1)+lim); cy++){ k=cx+','+cy; (I.riv[k]=I.riv[k]||[]).push(seg); } } });
  /* bridges: streets the data marks as crossing water */
  (M.streets||[]).forEach(function(s){ if(!(s.o||s.br)) return; var p=s.p||[]; for(i=0;i+3<p.length;i+=2) I.decks.push({x0:p[i],y0:p[i+1],x1:p[i+2],y1:p[i+3],n:s.n||''}); });
  /* streets by name: every segment in the cells it passes (sampled every 60 units) */
  var segs=[]; (M.streets||[]).forEach(function(s){ if(!s.n) return; var p=s.p||[];
    for(i=0;i+3<p.length;i+=2){ var g={x0:p[i],y0:p[i+1],x1:p[i+2],y1:p[i+3],n:s.n,k:s.k}; g.dx=g.x1-g.x0; g.dy=g.y1-g.y0; g.l=Math.hypot(g.dx,g.dy); if(g.l<1) continue; segs.push(g);
      var steps=Math.max(1,Math.ceil(g.l/60)), seen={};
      for(var q=0;q<=steps;q++){ var kk=cellOf(g.x0+g.dx*q/steps)+','+cellOf(g.y0+g.dy*q/steps); if(seen[kk]) continue; seen[kk]=1; (I.st[kk]=I.st[kk]||[]).push(g); } } });
  I.stN=segs.length; return I; }
function idx(){ if(!IDX) IDX=buildIdx(); return IDX; }
function segDist2(x,y,x0,y0,dx,dy,l2){ var t=((x-x0)*dx+(y-y0)*dy)/l2; t=t<0?0:t>1?1:t; var qx=x0+dx*t-x, qy=y0+dy*t-y; return qx*qx+qy*qy; }
/* is (x,y) inside the closed zone round a river (drawn edge + gap + player radius)? `pad` widens it (used to size a deck) */
function inWaterZone(x,y,pad){ var list=idx().riv[cellOf(x)+','+cellOf(y)]; if(!list) return false; pad=pad||0;
  for(var i=0;i<list.length;i++){ var s=list[i], l=s.lim+pad; if(segDist2(x,y,s.x0,s.y0,s.x1-s.x0,s.y1-s.y0,s.l2)<l*l) return true; } return false; }
function onDeck(x,y){ var D=idx().decks, h=CFG.deckHW; for(var i=0;i<D.length;i++){ var d=D[i], dx=d.x1-d.x0, dy=d.y1-d.y0; if(segDist2(x,y,d.x0,d.y0,dx,dy,Math.max(1e-9,dx*dx+dy*dy))<h*h) return true; } return false; }

/* \u2500\u2500 collision \u2500\u2500 */
function ringHit(s,x,y,pr2){ var ring=s.ring, n=s.n, inside=false, j=n-1;
  for(var i=0;i<n;i++){ var ax=ring[2*i], ay=ring[2*i+1], bx=ring[2*j], by=ring[2*j+1];
    if((ay>y)!==(by>y) && x<(bx-ax)*(y-ay)/(by-ay)+ax) inside=!inside;
    var ex=bx-ax, ey=by-ay, l2=ex*ex+ey*ey, t=l2>0?((x-ax)*ex+(y-ay)*ey)/l2:0; t=t<0?0:t>1?1:t; var qx=ax+t*ex-x, qy=ay+t*ey-y; if(qx*qx+qy*qy<pr2) return true;
    j=i; }
  return inside; }
function listHit(l,x,y,PR,pr2){ for(var i=0;i<l.length;i++){ var s=l[i], dx=x-s.cx, dy=y-s.cy, rr=s.r+PR; if(dx*dx+dy*dy>rr*rr) continue; if(ringHit(s,x,y,pr2)) return true; } return false; }
function buildingHit(x,y){ var PR=PRX(), pr2=PR*PR, ci=Math.floor(x/CELL), cj=Math.floor(y/CELL), a, b, c;
  for(a=-1;a<=1;a++) for(b=-1;b<=1;b++){ c=S.cells[(ci+a)+','+(cj+b)]; if(c && listHit(c.small,x,y,PR,pr2)) return true; }
  return listHit(S.bigs,x,y,PR,pr2); }
/* the player circle at (x,y) overlaps a building, the water (off a deck) or the city's edge */
function blockedAt(x,y){
  if(IN.on) return insideBlocked(x,y);                             /* inside a building: its footprint is the room (palace_ride_inside.py) */
  if(S.real) return buildingHit(x,y);
  if(x<CFG.edge || y<CFG.edge || x>E.M.W-CFG.edge || y>E.M.H-CFG.edge) return true;
  if(inWaterZone(x,y,0) && !onDeck(x,y)) return true;
  return buildingHit(x,y); }
function normalAt(x,y){                          /* away from the obstacle touching the free circle at (x,y) */
  for(var rad=.7; rad<=3.4; rad+=.9){ var sx=0, sy=0, n=0; for(var k=0;k<16;k++){ var a=k*.3926991, cx=Math.cos(a), cy=Math.sin(a); if(blockedAt(x+cx*rad,y+cy*rad)){ sx+=cx; sy+=cy; n++; } }
    if(n){ var l=Math.hypot(sx,sy); if(l>1e-6) return [-sx/l,-sy/l]; } }
  return null; }
function cut(x,y,dx,dy){ var lo=0, hi=1; for(var i=0;i<7;i++){ var m=(lo+hi)/2; if(blockedAt(x+dx*m,y+dy*m)) hi=m; else lo=m; } return lo; }
function moveStep(dx,dy){
  var x=S.x, y=S.y;
  if(!blockedAt(x+dx,y+dy)){ S.x=x+dx; S.y=y+dy; return; }
  var t=cut(x,y,dx,dy); x+=dx*t; y+=dy*t; var rx=dx*(1-t), ry=dy*(1-t), n=normalAt(x,y);
  if(n){ var dot=rx*n[0]+ry*n[1]; if(dot<0){ rx-=dot*n[0]; ry-=dot*n[1]; }
    if(rx*rx+ry*ry>1e-8){ if(!blockedAt(x+rx,y+ry)){ x+=rx; y+=ry; } else { var t2=cut(x,y,rx,ry); x+=rx*t2; y+=ry*t2; } } }
  S.x=x; S.y=y; }
function moveBy(dx,dy){ var l=Math.hypot(dx,dy); if(l<1e-9) return; var n=Math.max(1,Math.ceil(l/1.1)); for(var i=0;i<n;i++) moveStep(dx/n,dy/n); }
/* the nearest free spot to (x,y): the point itself when it is free, else rings of growing radius round it */
function freeNear(x,y){
  if(!blockedAt(x,y)) return [x,y];
  for(var r=2; r<=900; r+=r<60?2:6){ var n=Math.max(12,Math.round(r*.9)), best=null, bd=1e18; for(var k=0;k<n;k++){ var a=k/n*6.2831853, px=x+Math.cos(a)*r, py=y+Math.sin(a)*r; if(!blockedAt(px,py)){ var d=Math.abs(Math.sin(a*2.7)); if(d<bd){ bd=d; best=[px,py]; } } }
    if(best) return best; }
  return [x,y]; }

/* \u2500\u2500 streaming: the world, cell by cell \u2500\u2500 */
function cellBoxDist(ci,cj,x,y){ var dx=Math.max(ci*CELL-x,0,x-(ci+1)*CELL), dy=Math.max(cj*CELL-y,0,y-(cj+1)*CELL); return Math.hypot(dx,dy); }
function buildCell(ci,cj){
  var key=ci+','+cj, set={}; set[key]=1; var t0=performance.now(), Wc=null, kx=_pa.x, ky=_pa.y;
  _pa.x=-1e9; _pa.y=-1e9;                            /* gatherWorld adds a big park to whatever cell it is in when the path is near: the roamer manages those itself */
  try{ Wc=gatherWorld(set,null); }catch(x){ if(window.console) console.warn('roam cell', key, x); }
  _pa.x=kx; _pa.y=ky;
  if(!Wc) Wc={solids:[],tiles:[],parks:[],water:[],roads:[],props:[],poles:[],labels:[],dashes:[],meshes:[],movers:[],set:set,scenery:null,rivers:[]};
  addBridges(Wc, ci, cj);
  var col=[]; Wc.solids.forEach(function(s){ if(QUAL.indexOf(s.kind)>=0 || s.collide) col.push(s); });
  Wc.doors=Wc.solids.filter(function(s){ return s.door; }); Wc.col=col; Wc.small=col.filter(function(s){ return s.r<=BIGR; }); Wc.big=col.filter(function(s){ return s.r>BIGR; }); Wc.ci=ci; Wc.cj=cj; Wc.key=key; Wc.ms=performance.now()-t0; Wc.late=!!S.on&&!S.entering;
  S.cells[key]=Wc; S.built++; if(Wc.late){ S.lbms.push(Wc.ms); if(S.lbms.length>400) S.lbms.shift(); } S.bms.push(Wc.ms); if(S.bms.length>400) S.bms.shift(); S.dirty=true; return Wc; }
/* a bridge deck and its two parapets as low solids, over the water only, in the cell that holds the middle of the deck */
function addBridges(Wc, ci, cj){
  idx().decks.forEach(function(d){ var mx=(d.x0+d.x1)/2, my=(d.y0+d.y1)/2; if(Math.floor(mx/CELL)!==ci || Math.floor(my/CELL)!==cj) return;
    var L=Math.hypot(d.x1-d.x0,d.y1-d.y0), ux=(d.x1-d.x0)/L, uy=(d.y1-d.y0)/L, a=-1, b=-1;
    for(var s=0;s<=L;s+=3){ if(inWaterZone(d.x0+ux*s,d.y0+uy*s,6)){ if(a<0) a=s; b=s; } }
    if(a<0) return; a=Math.max(0,a-4); b=Math.min(L,b+4);
    var ax=d.x0+ux*a, ay=d.y0+uy*a, bx=d.x0+ux*b, by=d.y0+uy*b, dk=dark(), hw=CFG.deckHW+2.9;
    Wc.solids.push(solid(strip(ax,ay,bx,by,hw*2,0), .45, dk?[74,78,92]:[150,152,160], 'plat', d.n));
    [-1,1].forEach(function(sd){ var ox=-uy*sd*(hw-.8), oy=ux*sd*(hw-.8); Wc.solids.push(solid(strip(ax+ox,ay+oy,bx+ox,by+oy,.8,0), 1.7, dk?[96,102,120]:[196,198,206], 'plat', d.n)); }); }); }
function plan(force){
  if(S.real) return;
  var x=S.x, y=S.y, p=S.plan; if(!force && Math.hypot(x-p.x,y-p.y)<40) return; p.x=x; p.y=y; S.plans++;
  var c0=Math.floor(x/CELL), r0=Math.floor(y/CELL), R_=Math.ceil(CFG.keep/CELL)+1, MW=E.M.W, MH=E.M.H, i, j, k, want=[];
  for(i=-R_;i<=R_;i++) for(j=-R_;j<=R_;j++){ var ci=c0+i, cj=r0+j; if(ci<0||cj<0||ci*CELL>MW||cj*CELL>MH) continue; var d=cellBoxDist(ci,cj,x,y);
    if(d<=CFG.load && !S.cells[ci+','+cj]) want.push([d,ci,cj]); }
  want.sort(function(a,b){ return a[0]-b[0]; }); S.queue=want;
  Object.keys(S.cells).forEach(function(key){ var c=S.cells[key]; if(cellBoxDist(c.ci,c.cj,x,y)>CFG.keep){ delete S.cells[key]; S.evicted++; S.dirty=true; } }); }
function stream(sync){
  if(S.real){ if(!IN.on) realStream(sync); return; }
  var t0=performance.now(), n=0;
  while(S.queue.length){ var q=S.queue[0]; if(!sync && n>0 && performance.now()-t0>CFG.budget) break;
    S.queue.shift(); if(S.cells[q[1]+','+q[2]]) continue; buildCell(q[1],q[2]); n++; }
  if(S.dirty) merge(); }
function bigParks(){ var B=[], x=S.x, y=S.y; E.M.parks.forEach(function(pk){ (pk.r||[]).forEach(function(r){ var n=r.length/2, cx=0, cy=0, i; for(i=0;i<n;i++){ cx+=r[2*i]; cy+=r[2*i+1]; } cx/=n; cy/=n; var rr=0; for(i=0;i<n;i++) rr=Math.max(rr,Math.hypot(r[2*i]-cx,r[2*i+1]-cy));
    if(rr>600 && Math.hypot(cx-x,cy-y)<rr+900) B.push({ring:r,cx:cx,cy:cy,r:rr,name:pk.n}); }); }); return B; }
function mergeScenery(dst, src){ if(!src) return dst; dst=dst||{};
  Object.keys(src).forEach(function(k){ var v=src[k]; if(Array.isArray(v)) dst[k]=(dst[k]||[]).concat(v); else if(dst[k]==null) dst[k]=v; }); return dst; }
function merge(){
  var t0=performance.now(), Wd=S.W, keys=Object.keys(S.cells), L=['tiles','parks','water','roads','dashes','props','poles','labels','solids','meshes','movers'], out={}, set={}, seenD={}, seenP={}, i, scn=null;
  L.forEach(function(f){ out[f]=[]; });
  keys.forEach(function(key){ var c=S.cells[key]; set[key]=1;
    L.forEach(function(f){ var a=c[f]; if(!a||!a.length) return;
      if(f==='dashes'){ a.forEach(function(d){ var k=Math.round(d.cx)+','+Math.round(d.cy); if(!seenD[k]){ seenD[k]=1; out.dashes.push(d); } }); }
      else if(f==='parks'){ a.forEach(function(p){ if(!seenP[p.name+p.cx]){ seenP[p.name+p.cx]=1; out.parks.push(p); } }); }
      else out[f]=out[f].concat(a); });
    if(c.scenery) scn=mergeScenery(scn,c.scenery); });
  bigParks().forEach(function(p){ if(!seenP[p.name+p.cx]){ seenP[p.name+p.cx]=1; out.parks.push(p); } });
  L.forEach(function(f){ Wd[f]=out[f]; }); Wd.scenery=scn; Wd.set=set; Wd.cells=S.cells; Wd.ver=++S.ver; Wd.rivers=E.M.river||[]; Wd.tunn=false; Wd.stopLabels=null;
  /* a small building is found through its own cell and the eight round it; the big ones (reaching further) are kept in one list */
  S.bigs=[]; keys.forEach(function(key){ S.bigs=S.bigs.concat(S.cells[key].big); });
  S.merges++; S.dirty=false; var ms=performance.now()-t0; S.mms.push(ms); if(S.mms.length>200) S.mms.shift(); }

/* \u2500\u2500 where am I: streets, cross streets, district \u2500\u2500 */
function nearSegs(x,y,rad){ var I=idx(), c0=cellOf(x), r0=cellOf(y), out=[], seen=[], i, j, k, l; for(i=-rad;i<=rad;i++) for(j=-rad;j<=rad;j++){ l=I.st[(c0+i)+','+(r0+j)]; if(!l) continue; for(k=0;k<l.length;k++) if(seen.indexOf(l[k])<0){ seen.push(l[k]); out.push(l[k]); } } return out; }
function locate(x,y){
  if(S.real) return locateReal(x,y);
  var segs=nearSegs(x,y,1), best=null, bd=1e18, i; if(!segs.length) segs=nearSegs(x,y,3);
  for(i=0;i<segs.length;i++){ var g=segs[i], d=segDist2(x,y,g.x0,g.y0,g.dx,g.dy,g.l*g.l); if(d<bd){ bd=d; best=g; } }
  var o={street:null, dist:Math.sqrt(bd), at:null, before:null, after:null, area:areaAt(x,y), head:null};
  if(!best) return o; o.street=best.n; var ux=best.dx/best.l, uy=best.dy/best.l; o.head=Math.atan2(uy,ux);
  /* the cross streets on this street: intersections of its line with the other named segments nearby, nearest behind and ahead of my place along it */
  var along=(x-best.x0)*ux+(y-best.y0)*uy, nb=nearSegs(x,y,3), bs=1e9, as=1e9, bn=null, an=null;
  for(i=0;i<nb.length;i++){ var h=nb[i]; if(h.n===best.n) continue; var hx=h.dx, hy=h.dy, den=ux*hy-uy*hx; if(Math.abs(den)<1e-6*h.l) continue;
    var wx=h.x0-best.x0, wy=h.y0-best.y0, tH=(wx*uy-wy*ux)/den;          /* where along h the line of `best` crosses it (0..1 = inside h) */
    var gap=tH<0?-tH*h.l:tH>1?(tH-1)*h.l:0; if(gap>30) continue;
    var sA=(wx*hy-wy*hx)/den; var rel=sA-along;                           /* distance along `best` from me */
    if(rel>=0 && rel<as){ as=rel; an=h.n; } if(rel<0 && -rel<bs){ bs=-rel; bn=h.n; } }
  if(an && as<CFG.crossAt && as<=bs) o.at=an; else if(bn && bs<CFG.crossAt) o.at=bn;
  if(!o.at){ o.before=bn; o.after=an; if(bn===an) o.after=null; }
  return o; }
var AREAR=[0,4600,2600,1500,900];
function areaAt(x,y){ var D=E.P.d||[], i; for(i=0;i<D.length;i++){ var b=D[i].box; if(b && x>=b[0]&&x<=b[2]&&y>=b[1]&&y<=b[3]) return D[i].n; }
  var best=null, bd=1e9; (E.M.areas||[]).forEach(function(a){ var d=Math.hypot(a.x-x,a.y-y)/(AREAR[a.r]||1200); if(d<bd){ bd=d; best=a; } }); return best&&bd<1.6?best.n:''; }
function streetHeading(x,y,prefer){ var o=locate(x,y); if(o.head==null) return prefer==null?0:prefer;
  if(prefer==null) return o.head; var d=Math.cos(o.head-prefer); return d>=0?o.head:o.head+Math.PI; }
function whereText(o){ if(!o.street) return {a:'',b:''}; var b=''; if(o.at) b='at '+o.at; else if(o.before&&o.after) b='between '+o.before+' & '+o.after; else if(o.before||o.after) b='near '+(o.before||o.after); return {a:o.street, b:b}; }


/* ── REAL mode (2.0.0 FPV): the walk happens in the real street frame (palace_ride_real.py / palace_ride_street.py) where the street data covers the place and the place is
   in bounds (REAL.inBounds); S.x / S.y are then world units = real metres x UM. The lattice walk above stays as the fallback (real off, data not loaded, out of bounds):
   it starts first and the real world takes over once the shards under the walker arrive (a cross-fade), so nothing is ever glitchy while loading. ── */
var RW={R:380, regather:105, have:null, busy:false, gen:null, gx:0, gy:0, gms:0, fade:null, edge:0, k:0, cx:0, cy:0, n:0, ms:0, maxMs:0};
function realCan(){ return typeof REAL!=='undefined' && REAL && typeof rlInit==='function' && rlInit() && (REAL.on || (REAL.street&&REAL.street())); }
function realNear(rx,ry){ if(REAL.street && REAL.street()){ var H=REAL.have||[]; if(!(REAL.on&&REAL.chunks)) return false; for(var i=0;i<H.length;i++) if(Math.hypot(rx-H[i][0],ry-H[i][1])<H[i][2]-RW.R*.55) return true; return false; } return !!(REAL.on && REAL.chunks && REAL.ways); }
/* load the data under (rx,ry) real px; resolves true when the real world can be gathered there */
function realLoad(rx,ry){
  if(!REAL.street || !REAL.street()) return Promise.resolve(!!(REAL.on && REAL.chunks && REAL.ways));
  if(realNear(rx,ry)) return Promise.resolve(true);
  return REAL.prepare([[rx,ry]],520).then(function(ok){ return !!ok; }, function(){ return false; }); }
function realBuckets(Wn){
  var cg={}; Wn.solids.forEach(function(sd){ if(!(QUAL.indexOf(sd.kind)>=0 || sd.collide)) return; var ci=Math.floor(sd.cx/CELL), cj=Math.floor(sd.cy/CELL), k=ci+','+cj, c=cg[k]||(cg[k]={small:[],big:[],doors:[],col:[],ci:ci,cj:cj,key:k});
    c.col.push(sd); (sd.r<=BIGR?c.small:c.big).push(sd); if(sd.door) c.doors.push(sd); });
  S.bigs=[]; Object.keys(cg).forEach(function(k){ S.bigs=S.bigs.concat(cg[k].big); }); S.cells=cg; }
/* the new world replaces the old one's arrays in ONE step (Wd.ver bumps once): the renderer keeps every cell it already built (cached by content) and builds the new ones behind it, so nothing in view changes */
function realFinish(Wn,cx,cy,ms){
  realBuckets(Wn); var Wd=S.W; ['tiles','parks','water','roads','dashes','props','poles','labels','solids','meshes','movers'].forEach(function(f){ Wd[f]=Wn[f]||[]; });
  Wd.scenery=Wn.scenery||null; Wd.set=Wn.set||{}; Wd.real=Wn.real; Wd.pal=Wn.pal; Wd.atlas=Wn.atlas||null; Wd.lamps=Wn.lamps||null; Wd.cells=null; Wd.rivers=[]; Wd.tunn=false; Wd.stopLabels=null; Wd.ver=++S.ver; Wd._gl=null; Wd._mv=null;
  RW.cx=cx; RW.cy=cy; RW.n++; RW.ms=ms; RW.maxMs=Math.max(RW.maxMs,ms); S.merges++; S.dirty=false; }
function realGather(){                                                  /* the whole world now (entering, tests) */
  var t0=performance.now(); RW.gen=null; realFinish(REAL.gather(0,0,RW.R,{x:S.x/UM,y:S.y/UM,k:RW.k}),S.x,S.y,performance.now()-t0); }
/* the world ahead, a few milliseconds a frame: the generator (palace_ride_street.py gatherRealG) yields between 400 m chunks and steps, the frame loop gives it CFG.budget ms each frame, and the swap happens once, when it is done.
   A 105 m walk used to stop for the whole gather (30-45 ms, two or three dropped frames). */
function realGatherStep(sync){
  if(!RW.gen){ RW.gx=S.x; RW.gy=S.y; RW.gms=0; RW.gen=REAL.gatherG(0,0,RW.R,{x:S.x/UM,y:S.y/UM,k:RW.k}); }
  var t0=performance.now(), r; do{ r=RW.gen.next(); }while(!r.done && (sync || performance.now()-t0<CFG.budget));
  RW.gms+=performance.now()-t0; if(r.done){ RW.gen=null; realFinish(r.value,RW.gx,RW.gy,RW.gms); } }
/* every step in real mode: keep the world centred near the walker, fetch the shards ahead; hold the walker inside the in-bounds region */
function realStream(sync){
  if(RW.gen){ realGatherStep(sync); return; }
  if(RW.busy || Math.hypot(S.x-RW.cx,S.y-RW.cy)<RW.regather*UM) return;
  var rx=S.x/UM, ry=S.y/UM;
  if(sync || !(REAL.street&&REAL.street()) || realNear(rx,ry)){ if(!sync && REAL.street&&REAL.street()&&!realNear(rx,ry)) return; if(sync) realGather(); else realGatherStep(false); return; }
  RW.busy=true; realLoad(rx,ry).then(function(ok){ RW.busy=false; if(ok && S.on && S.real) realGatherStep(false); }, function(){ RW.busy=false; }); }
function realBound(dt){
  var rx=S.x/UM, ry=S.y/UM, ed=REAL.edgeDist(rx,ry), e=1-clamp(ed/60,0,1);
  RW.edge+=(e-RW.edge)*(1-Math.exp(-dt/.35)); if(RW.edge<.002) RW.edge=0;
  if(e>0 && ed>0){ var sl=1-.55*e; S.vx*=sl+(1-sl)*Math.exp(-dt*4); S.vy*=sl+(1-sl)*Math.exp(-dt*4); }
  if(!REAL.inBounds(rx,ry)){ var o=REAL.clamp(rx,ry,{}); if(o.moved){ var nx=o.x*UM, ny=o.y*UM; if(!blockedAt(nx,ny)){ S.x=nx; S.y=ny; } S.vx*=.3; S.vy*=.3; RW.edge=Math.max(RW.edge,.95); } } }
function locateReal(x,y){
  var cs=rlNear(x/UM,y/UM,60,true), c=cs[0], i; for(i=0;i<cs.length;i++){ var cl=RCLS[cs[i].f[0]]; if(cs[i].f.n && cl && cl[0]>=7 && cs[i].d<cs[0].d+14){ c=cs[i]; break; } }
  var pg=REAL.toPage(x/UM,y/UM), o={street:null, dist:c?c.d*UM:1e9, at:null, before:null, after:null, area:areaAt(pg[0],pg[1]), head:null};
  if(c){ o.head=c.ang; var nm=c.f&&c.f.n; if(nm) o.street=nm; } return o; }
/* make the walk real: (x, y) in world units. Data must be loaded around it. */
function goReal(x,y,k){
  S.real=RW; RW.k=k||0; RW.cx=RW.cy=1e12; RW.edge=0; S.cells={}; S.queue=[]; S.bigs=[]; S.x=x; S.y=y; S.vx=S.vy=0; S.W.ver=S.ver; realGather();
  if(blockedAt(S.x,S.y)){ var fr=freeNear(S.x,S.y); S.x=fr[0]; S.y=fr[1]; } S.dirty=false; try{ GLX.newWorld(); }catch(e){} }
function snapOver(){
  try{ var ov=R.ov, c=document.createElement('canvas'), cv=R.cv; c.width=cv.width; c.height=cv.height; c.className='rm-xf'; var g=c.getContext('2d');
    if(typeof GLX!=='undefined' && GLX.cv && GLX.on) g.drawImage(GLX.cv,0,0,c.width,c.height); g.drawImage(cv,0,0); ov.appendChild(c); return c; }catch(e){ return null; } }
function fadeSnap(c){ if(!c) return; void c.offsetHeight; c.style.opacity='0'; setTimeout(function(){ if(c.parentNode) c.parentNode.removeChild(c); }, 900); }
/* the upgrade from the lattice walk the moment the data is there; at = {x,y} world units to land on exactly (the way back from a detail page) */
function realUpgrade(xp,yp,hp,at){
  if(!realCan()) return null;
  var r=realOf(xp,yp,{x:0,y:0,k:0}); if(!REAL.inBounds(r.x,r.y)) { S.realWhy='out of bounds'; return null; }
  var fin=function(ok){
    if(!ok || !S.on || S.real) return false;
    var pos; if(at) pos={x:at.x,y:at.y,h:at.h}; else { var e=REAL.enter(xp,yp,hp,40); pos={x:e.x,y:e.y,h:e.h}; sidewalk(pos,r.x,r.y); if(!REAL.inBounds(pos.x/UM,pos.y/UM)) { S.realWhy='snap out of bounds'; return false; } }
    S.pendingReal={x:pos.x,y:pos.y,k:r.k,at:!!at};
    if(S.hold||at||reduced()){ doSwitch(); } else S.xf=1;                       /* the frame loop snapshots the old world, then switches */
    return true; };
  if((at||S.hold) && realNear(r.x,r.y)) return Promise.resolve(fin(true));       /* the data is already here: no wait */
  return realLoad(r.x,r.y).then(fin); }
/* stand on the pavement beside the road the walk was snapped to, on the side the asker was on */
function sidewalk(pos,ox,oy){ var rx=pos.x/UM, ry=pos.y/UM, c=rlNear(rx,ry,6,true)[0]; if(!c) return; var cl=RCLS[c.f[0]], w=cl?cl[0]:0; if(!cl||w<7||cl[1]<.2) return;
  var nx=-Math.sin(c.ang), ny=Math.cos(c.ang), side=((ox-rx)*nx+(oy-ry)*ny)>=0?1:-1, off=w/2+1.7; pos.x=(rx+nx*side*off)*UM; pos.y=(ry+ny*side*off)*UM; }
function doSwitch(){ var q=S.pendingReal; S.pendingReal=null; if(!q||!S.on||S.real) return; goReal(q.x,q.y,q.k); if(S.autoYaw && !q.at) S.yaw=q.h; S.spawned2={x:q.x,y:q.y}; hudFrame(true); }

/* \u2500\u2500 the HUD \u2500\u2500 */
var DIRS=['N','NE','E','SE','S','SW','W','NW'];
function ensureHud(){
  if(S.hud) return S.hud; ensureOverlay();
  var h=document.createElement('div'); h.className='rm-hud'; h.setAttribute('role','group'); h.setAttribute('aria-label','Street-level view');
  var tape='<div class="rm-tape">'; for(var d=-180; d<=540; d+=15){ var m=((d%360)+360)%360, nm=m%45===0?DIRS[m/45]:''; tape+='<i class="'+(nm?'m':'')+(m%90===0?' c':'')+'" style="left:'+(d*3)+'px">'+(nm?'<s>'+nm+'</s>':'')+'</i>'; } tape+='</div>';
  h.innerHTML='<div class="rm-compass" aria-hidden="true"><div class="rm-win">'+tape+'</div><u></u></div>'
    +'<div class="rm-left"><div class="rm-where" aria-hidden="true"><b class="rm-st"></b><span class="rm-cx"></span><em class="rm-ar"></em></div>'
    +'<button type="button" class="rm-pin" data-roam="door" aria-hidden="true" tabindex="-1"><svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 18s5.6-4.9 5.6-9.3a5.6 5.6 0 0 0-11.2 0C4.4 13.1 10 18 10 18z"/><circle cx="10" cy="8.6" r="2"/></svg><b class="rm-pn"></b><kbd aria-hidden="true">E</kbd></button></div>'
    +'<div class="rm-btns"><button type="button" data-roam="exit">Back to the map \u00b7 Esc</button><button type="button" data-roam="stay">Stay here</button></div>'
    +'<div class="rm-edge" aria-hidden="true">edge of the palace</div>'
    +'<div class="rm-hint" aria-hidden="true">W A S D move \u00b7 \u2190 \u2192 turn \u00b7 drag to look \u00b7 Shift to walk faster \u00b7 Esc to leave</div>'
    +'<div class="pr-live rm-live" aria-live="polite"></div>';
  R.ov.appendChild(h); S.hud={root:h, pin:h.querySelector('.rm-pin'), pn:h.querySelector('.rm-pn'), tape:h.querySelector('.rm-tape'), st:h.querySelector('.rm-st'), cx:h.querySelector('.rm-cx'), ar:h.querySelector('.rm-ar'), hint:h.querySelector('.rm-hint'), edge:h.querySelector('.rm-edge'), live:h.querySelector('.rm-live')};
  h.addEventListener('click', function(e){ var b=e.target.closest&&e.target.closest('[data-roam]'); if(!b) return; e.preventDefault(); e.stopPropagation(); if(b.getAttribute('data-roam')==='door'){ openDoor(); return; } ROAMAPI.exit(b.getAttribute('data-roam')==='stay'); });
  ['click','dblclick','contextmenu','mousedown','mouseup'].forEach(function(t){ R.ov.addEventListener(t, function(e){ if(S.on){ e.stopPropagation(); if(t==='contextmenu') e.preventDefault(); } }); });
  var cv=R.cv; cv.addEventListener('pointerdown', function(e){ if(!S.on||e.button>0||DR.busy) return; S.drag={id:e.pointerId,x:e.clientX,y:e.clientY,mv:0}; try{ cv.setPointerCapture(e.pointerId); }catch(x){} R.ov.classList.add('drag'); e.preventDefault(); });
  cv.addEventListener('pointermove', function(e){ var d=S.drag; if(!d||d.id!==e.pointerId){ doorHover(e); return; } d.mv+=Math.abs(e.clientX-d.x)+Math.abs(e.clientY-d.y); var g=CFG.grab?-1:1; S.yaw+=g*(e.clientX-d.x)*CFG.lookX; S.pitch=clamp(S.pitch-g*(e.clientY-d.y)*CFG.lookY,-CFG.pitchMax,CFG.pitchMax); d.x=e.clientX; d.y=e.clientY; });
  var up=function(e){ if(S.drag&&S.drag.id===e.pointerId){ var mv=S.drag.mv||0; S.drag=null; if(e.type==='pointerup' && mv<6) doorClick(e); R.ov.classList.remove('drag'); try{ cv.releasePointerCapture(e.pointerId); }catch(x){} } };
  cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
  return S.hud; }
function bearing(){ var b=Math.atan2(Math.cos(S.yaw), -Math.sin(S.yaw))*180/Math.PI; return (b+360)%360; }
function hudFrame(force){
  var H=S.hud; if(!H) return; var b=bearing(); var off=-(b*3); H.tape.style.transform='translate3d('+(off+130).toFixed(1)+'px,0,0)';
  var now=performance.now(); if(!force && now-S.hudAt<160) return; S.hudAt=now;
  var o=locate(S.x,S.y); var w=whereText(o), area=o.area; S.loc=o;
  var sig=w.a+'|'+w.b+'|'+area; if(sig!==S.hud._sig){ S.hud._sig=sig; H.st.textContent=w.a||'Open ground'; H.cx.textContent=w.b; H.ar.textContent=area; H.ar.style.display=area?'':'none'; H.cx.style.display=w.b?'':'none';
    if(w.a!==S.said){ S.said=w.a; if(w.a) H.live.textContent=w.a+(w.b?', '+w.b:'')+(area?'. '+area:''); } }
}

/* \u2500\u2500 the frame \u2500\u2500 */
var KEYS={KeyW:'f',ArrowUp:'f',KeyS:'b',ArrowDown:'b',KeyA:'l',KeyD:'r',ArrowLeft:'tl',ArrowRight:'tr',w:'f',s:'b',a:'l',d:'r',W:'f',S:'b',A:'l',D:'r'};
function keyName(e){ return KEYS[e.code]||KEYS[e.key]||null; }
function setKey(name, down){ if(name) S.keys[name]=down?1:0; }
function clearKeys(){ S.keys={}; S.run=false; }
var DN={};                                       /* keys swallowed on the way down: their keyup is swallowed too, even when the roam ended in between (Esc) */
function onKey(e){
  if(!S.on){ if(e.type==='keyup' && DN[e.key]){ delete DN[e.key]; e.preventDefault(); e.stopImmediatePropagation(); } return; }
  if(e.metaKey||e.ctrlKey||e.altKey) return;                       /* browser shortcuts stay the browser's */
  var t=e.target, inHud=t&&t.closest&&t.closest('.rm-hud');
  if(e.key==='Tab'){ if(e.type==='keydown'){ e.preventDefault(); e.stopImmediatePropagation(); var bs=[].slice.call(S.hud.root.querySelectorAll('button')).filter(function(b){ return getComputedStyle(b).visibility!=='hidden'; }), i=bs.indexOf(document.activeElement); bs[(i+(e.shiftKey?bs.length-1:1))%bs.length].focus(); } return; }
  if(inHud && t.tagName==='BUTTON' && (e.key==='Enter'||e.key===' ') ){ e.stopImmediatePropagation(); return; }     /* a focused button keeps its own Enter / Space */
  e.preventDefault(); e.stopImmediatePropagation();
  if(e.type==='keydown') DN[e.key]=1; else delete DN[e.key];
  if(e.type==='keydown' && doorKey(e)) return;
  if(e.type==='keydown' && e.key==='Escape'){ ROAMAPI.exit(false); return; }
  S.run=!!e.shiftKey;
  setKey(keyName(e), e.type==='keydown'); }
function onWheel(e){ if(!S.on) return; var t=e.target; if(t && R.ov && R.ov.contains(t)){ e.preventDefault(); e.stopImmediatePropagation(); } }
window.addEventListener('keydown', onKey, true); window.addEventListener('keyup', onKey, true);
window.addEventListener('wheel', onWheel, {capture:true, passive:false});
window.addEventListener('blur', function(){ clearKeys(); S.drag=null; });
document.addEventListener('visibilitychange', function(){ if(document.hidden) clearKeys(); });

function tick(dt, sync){
  var k=S.keys, fx=Math.cos(S.yaw), fy=Math.sin(S.yaw), rx=-fy, ry=fx, ax=(k.f?1:0)-(k.b?1:0), ay=(k.r?1:0)-(k.l?1:0), l=Math.hypot(ax,ay);
  if(k.tl||k.tr) S.yaw+=((k.tr?1:0)-(k.tl?1:0))*CFG.turn*dt*(S.run?1.4:1);
  S.hurry=(S.run&&l>0)?Math.min(S.hurry+dt,CFG.hurryAfter+CFG.hurryRamp):Math.max(0,S.hurry-dt*2);
  var sp=S.run?mix(CFG.brisk,CFG.jog,sstep(CFG.hurryAfter,CFG.hurryAfter+CFG.hurryRamp,S.hurry)):CFG.walk, tx=0, ty=0; if(l>0){ tx=(fx*ax+rx*ay)/l*sp; ty=(fy*ax+ry*ay)/l*sp; }
  var a=1-Math.exp(-dt/CFG.tau); S.vx+=(tx-S.vx)*a; S.vy+=(ty-S.vy)*a;
  if(blockedAt(S.x,S.y)){ var fr=freeNear(S.x,S.y); S.x=fr[0]; S.y=fr[1]; S.vx=S.vy=0; }                  /* never stand inside anything (a safety net: moves are only ever committed free) */
  var x0=S.x, y0=S.y; if(Math.abs(S.vx)>.01||Math.abs(S.vy)>.01) moveBy(S.vx*dt,S.vy*dt);
  var mv=Math.hypot(S.x-x0,S.y-y0); S.speed=dt>0?mv/dt:0;
  if(dt>0 && mv<Math.hypot(S.vx,S.vy)*dt*.5){ S.vx=(S.x-x0)/dt; S.vy=(S.y-y0)/dt; }       /* pressed against a wall: no speed stored up */
  if(S.real && !IN.on) realBound(dt); else if(IN.on) RW.edge=0;       /* inside a building the footprint is the room: no edge fog, no clamp */
  S.phase+=Math.min(stepHz(S.speed/UM),2.1)*6.2832*dt; S.walked+=mv; S.tm+=dt;
  plan(false); stream(!!sync); }
function draw(){
  var t0=performance.now(); sizeCheck(); var ctx=R.ctx, W=R.w, H=R.h, dpr=R.dpr; if(!ctx||!S.W) return;
  var dk=dark(); if(dk!==S.lastDark){ S.lastDark=dk; R.PAL=palette(); }
  ctx.setTransform(dpr,0,0,dpr,0,0);
  var a=clamp(S.speed/CFG.walk,0,1.4), a1=Math.min(a,1), bob=reduced()?0:Math.sin(S.phase)*CFG.bob*a, sway=reduced()?0:Math.sin(S.phase*.5)*.004*a1;
  var pitch=S.pitch+(reduced()?0:Math.abs(Math.sin(S.phase))*.004*a);
  var ee=(S.real&&!IN.on)?RW.edge:0; if(typeof GLX!=='undefined') GLX.edge=ee; if(S.hud&&S.hud.edge){ var eo=ee<.12?0:Math.min(.9,(ee-.12)*1.4); if(S._eo!==eo){ S._eo=eo; S.hud.edge.style.opacity=String(eo); } }
  S.camZ=CFG.eye+(IN.on?IN.z:0)+bob; camSet(S.x,S.y,S.camZ,S.yaw+sway,glOk()?pitch:clamp(pitch,-.42,.42),W,H);
  sceneryUpdate(S.W, S.tm, C);
  drawCity(ctx, W, H, R.PAL, S.W, S.yaw, S.tm, null);
  ctx.setTransform(dpr,0,0,dpr,0,0); doorGlow(ctx);
  var ms=performance.now()-t0; S.fr.push(ms); if(S.fr.length>600) S.fr.shift(); }
/* the one place the camera is set: setCam's 8th argument is the real pitch (the GL renderer tilts the view; the 2D fallback has no pitch of its own, so it keeps the old horizon shift) */
function camSet(x,y,z,yaw,pitch,W,H){ setCam(x,y,z,yaw,W,H,.5,pitch,fpFoc(W,H)); }
function frame(now){
  S.raf=0; if(!S.on) return;
  if(!R.active){ shutdown(); return; }                          /* something else closed the overlay (a trip started) */
  var dt=Math.min(.05, S.last?(now-S.last)/1000:.016); S.last=now;
  if(DR.cine){ cineStep(dt*1000); if(!S.on) return; } else if(!DR.busy) tick(dt,false);
  hudFrame(false); if(IN.on) insideFrame(dt); else doorFrame(dt); draw(); showNow();
  if(S.xf && S.pendingReal){ S.xf=0; var sn=snapOver(); doSwitch(); draw(); showNow(); fadeSnap(sn); }
  if(S.on) S.raf=requestAnimationFrame(frame); }

/*@DOORS@*/
/*@INSIDE@*/
/* \u2500\u2500 enter / exit \u2500\u2500 */
function shutdown(){
  if(S.raf){ cancelAnimationFrame(S.raf); S.raf=0; }
  doorReset(); S.on=false; clearKeys(); S.drag=null; S.cells={}; S.queue=[]; S.bigs=[]; S.W=null; S.vx=S.vy=0; S.real=null; S.xf=0; S.pendingReal=null; RW.busy=false; RW.gen=null; RW.edge=0; if(typeof GLX!=='undefined') GLX.edge=0;
  if(R.ov){ R.ov.classList.remove('rm','drag'); } }
function enter(x,y,heading,opts){
  opts=opts||{};
  if(!E || R.active || S.on || !E.M || !E.P) return false;
  if(document.documentElement.classList.contains('mobile')) return false;
  x=+x; y=+y; if(!isFinite(x)||!isFinite(y)) return false;
  var view=opts.view||(E.curView?E.curView():null);
  ensureOverlay(); ensureHud(); openOv();
  var pr=glOk()?CFG.PRGL:CFG.PR; if(pr!==S.pr){ S.pr=pr; IDX=null; }
  var cs=document.activeElement; if(cs&&cs.blur&&cs!==document.body) cs.blur();
  R.saved=view; R.M=null; R.W=null; R.hold=false; R.shown=false; R.playing=false; R.line=null;
  R.ov.classList.add('rm'); S.W={solids:[],tiles:[],parks:[],water:[],roads:[],props:[],poles:[],labels:[],dashes:[],meshes:[],movers:[],set:{},cells:S.cells,scenery:null,rivers:E.M.river||[],tunn:false,ver:0};
  S.cells={}; S.W.cells=S.cells; S.queue=[]; S.bigs=[]; S.dirty=false; S.plan={x:-1e9,y:-1e9}; S.real=null; S.xf=0; S.pendingReal=null; S.realWhy=''; S.tm=0; S.phase=0; S.walked=0; S.speed=0; S.hurry=0; S.vx=S.vy=0; S.pitch=CFG.pitch0; S.hud._sig=''; S.said=''; S.lastDark=null; S.built=0; S.evicted=0; S.merges=0; S.plans=0; S.bms=[]; S.lbms=[]; S.mms=[]; S.fr=[]; S.view=view; S.entering=true;
  /* the first cells round the spawn point are built before the first frame (nearest first), the rest stream in */
  S.x=clamp(x,CFG.edge+1,E.M.W-CFG.edge-1); S.y=clamp(y,CFG.edge+1,E.M.H-CFG.edge-1);
  plan(true); var near=S.queue.filter(function(q){ return q[0]<=CFG.sync; }); S.queue=S.queue.filter(function(q){ return q[0]>CFG.sync; }); near.forEach(function(q){ if(!S.cells[q[1]+','+q[2]]) buildCell(q[1],q[2]); }); merge();
  var f=freeNear(S.x,S.y); S.spawned={asked:[x,y],x:f[0],y:f[1]}; S.x=f[0]; S.y=f[1];
  S.entering=false; S.yaw=(heading==null||!isFinite(+heading))?streetHeading(S.x,S.y,null):+heading; S.on=true; S.hold=!!opts.hold; S.last=0; S.hint=1;
  R.PAL=palette(); S.lastDark=dark();
  hudFrame(true); draw(); showNow();
  S.autoYaw=(heading==null||!isFinite(+heading));
  if(opts.real!==false){ try{ S.upgrade=realUpgrade(S.x,S.y,S.yaw,opts.at||null); }catch(err){ S.upgrade=null; if(window.console) console.warn('roam real',err); } }
  S.hud.hint.classList.remove('gone'); clearTimeout(S.hintT); S.hintT=setTimeout(function(){ if(S.hud) S.hud.hint.classList.add('gone'); }, 9000);
  if(!S.hold) S.raf=requestAnimationFrame(frame);
  try{ R.ov.setAttribute('tabindex','-1'); R.ov.focus({preventScroll:true}); }catch(e){}
  return true; }
/* the aerial view that has map point (x,y) in the middle of the window, at zoom z (palace.py flyMap / center) */
function viewFor(x,y,z){ var cv=document.getElementById('canvas'); if(!cv) return null; var VW=E.M.W+2*MXC, VH=E.M.H+2*MXC, cw=cv.clientWidth, ch=cv.clientHeight;
  var gx=Math.max(0,(cw-VW*z)/2), gy=Math.max(0,Math.round((ch-VH*z)/2));
  return {z:z, x:Math.max(0,(x+MXC)*z+gx-cw/2), y:Math.max(0,(y+MXC)*z+gy-ch/2)}; }
function exit(stay){ exitCore(stay); }
function exitCore(stay){
  if(!S.on) return; clearTimeout(S.hintT);
  var x=S.x, y=S.y, v=S.view; if(S.real){ var pg=REAL.exit(S.x,S.y); x=pg[0]; y=pg[1]; }
  if(stay){ var z=Math.max(v&&v.z||0, CFG.stayZoom); var sv=viewFor(x,y,z); if(sv) R.saved=sv; }
  else R.saved=v;
  shutdown(); closeNow(true,false); }
var ROAMAPI={ enter:enter, exit:exit, active:function(){ return S.on; }, streetHeading:streetHeading, locate:locate, viewFor:viewFor, cfg:CFG,
  state:function(){ return {x:S.x, y:S.y, yaw:S.yaw, pitch:S.pitch, speed:S.speed, walked:S.walked, bearing:bearing(), camZ:S.camZ, pr:PRX(), foc:C.foc, hfov:C.W?2*Math.atan(C.W/2/C.foc)*180/Math.PI:0, vfov:C.H?2*Math.atan(C.H/2/C.foc)*180/Math.PI:0, hurry:S.hurry, spawned:S.spawned, real:!!S.real, gathering:!!RW.gen, realWhy:S.realWhy||'', edge:RW.edge, cells:Object.keys(S.cells).length, queue:S.queue.length, ver:S.ver, saved:S.view}; },
  stats:function(){ var f=S.fr.slice().sort(function(p,q){ return p-q; }), n=f.length, b=S.bms.slice().sort(function(p,q){ return p-q; }), m=S.mms.slice().sort(function(p,q){ return p-q; });
    return {built:S.built, evicted:S.evicted, merges:S.merges, plans:S.plans, cells:Object.keys(S.cells).length, queue:S.queue.length, buildAvg:b.length?b.reduce(function(p,q){ return p+q; },0)/b.length:0, buildMax:b.length?b[b.length-1]:0, streamMax:S.lbms.length?Math.max.apply(null,S.lbms):0, streamN:S.lbms.length, buildP95:b.length?b[Math.floor(b.length*.95)]:0, mergeMax:m.length?m[m.length-1]:0, mergeAvg:m.length?m.reduce(function(p,q){ return p+q; },0)/m.length:0,
      drawAvg:n?f.reduce(function(p,q){ return p+q; },0)/n:0, drawP95:n?f[Math.floor(n*.95)]:0, drawMax:n?f[n-1]:0, frames:n}; },
  /* the doors (palace_ride_door.py): tests drive the dolly with step(ms) and the prompt with frame(dt) */
  inside:INSIDEAPI,
  door:{ cur:function(){ return DR.cur; }, find:findDoor, frame:doorFrame, open:openDoor, step:cineStep, near:doorsAround, back:comeBack, hit:function(){ return DR.hit; },
    state:function(){ return {busy:DR.busy, ret:!!DR.ret, opened:!!(DR.ret&&DR.ret.opened), mem:DR.mem, glow:DR.glow, t:DR.t, cine:!!DR.cine, veil:DR.veil?+DR.veil.style.opacity:0}; } },
  /* tests and the QA kit */
  tick:function(dt, keys, run, slice){ if(keys) { S.keys={}; String(keys).split(',').forEach(function(q){ if(q) S.keys[q]=1; }); } S.run=!!run; tick(dt,!slice); },      /* slice: as the frame loop does (the streaming gets its few milliseconds), not all at once */
  sim:function(keys, seconds, dt, run){ S.keys={}; String(keys||'').split(',').forEach(function(q){ if(q) S.keys[q]=1; }); S.run=!!run; dt=dt||1/60; var n=Math.round(seconds/dt), bad=0; for(var i=0;i<n;i++){ tick(dt,true); if(blockedAt(S.x,S.y)) bad++; } S.keys={}; S.run=false; return {x:S.x,y:S.y,bad:bad,n:n}; },
  place:function(x,y,yaw){ S.x=x; S.y=y; if(yaw!=null) S.yaw=yaw; S.vx=S.vy=0; plan(true); stream(true); var f=freeNear(S.x,S.y); S.x=f[0]; S.y=f[1]; },
  look:function(yaw,pitch){ if(yaw!=null) S.yaw=yaw; if(pitch!=null) S.pitch=clamp(pitch,-CFG.pitchMax,CFG.pitchMax); },
  real:{ on:function(){ return !!S.real; }, upgrade:function(){ return S.upgrade||Promise.resolve(false); }, stats:function(){ return {n:RW.n, ms:RW.ms, maxMs:RW.maxMs, edge:RW.edge, R:RW.R, solids:S.W?S.W.solids.length:0}; }, gather:realGather, bound:realBound, toPage:function(){ return S.real?REAL.exit(S.x,S.y):[S.x,S.y]; } },
  settle:function(){ var g=0; while(S.queue.length && g++<500) stream(true); stream(true); },
  draw:function(){ hudFrame(true); draw(); showNow(); },
  blocked:blockedAt, free:freeNear, world:function(){ return S.W; }, dbg:function(){ return E; }, deckSegs:function(){ return idx().decks; },
  rings:function(x,y,rad){ var o=[]; Object.keys(S.cells).forEach(function(k){ S.cells[k].col.forEach(function(s){ if(Math.hypot(s.cx-x,s.cy-y)<=rad+s.r) o.push({ring:s.ring,kind:s.kind,name:s.name,h:s.h}); }); }); return o; },
  inWater:function(x,y){ return inWaterZone(x,y,0); }, onDeck:onDeck };
return ROAMAPI; })();
"""

JS_E = JS_INSIDE_GL + _JS_E.replace("/*@DOORS@*/", JS_DOORS).replace("/*@INSIDE@*/", JS_INSIDE)

_CSS_E = r"""
  #pal-ride.rm .pr-chip,#pal-ride.rm .pr-btns{display:none;}
  #pal-ride.rm:focus{outline:none;}
  #pal-ride.rm .pr-cv{cursor:grab;touch-action:none;-webkit-user-select:none;user-select:none;}
  #pal-ride.rm.drag .pr-cv{cursor:grabbing;}
  #pal-ride .rm-hud{display:none;}
  #pal-ride.rm .rm-hud{display:block;position:absolute;left:0;top:0;right:0;bottom:0;pointer-events:none;font:600 13px/1.25 system-ui,-apple-system,"Segoe UI",sans-serif;color:#fff;-webkit-user-select:none;user-select:none;}
  #pal-ride .rm-compass{position:absolute;left:50%;top:16px;width:260px;height:40px;margin-left:-130px;border-radius:999px;background:rgba(14,16,26,.62);border:1px solid rgba(255,255,255,.16);overflow:hidden;}
  #pal-ride .rm-win{position:absolute;left:0;top:0;right:0;bottom:0;overflow:hidden;-webkit-mask-image:linear-gradient(90deg,transparent 0,#000 20%,#000 80%,transparent 100%);mask-image:linear-gradient(90deg,transparent 0,#000 20%,#000 80%,transparent 100%);}
  #pal-ride .rm-tape{position:absolute;left:0;top:0;width:1px;height:100%;will-change:transform;}
  #pal-ride .rm-tape i{position:absolute;top:28px;width:1px;height:6px;background:rgba(255,255,255,.4);font-style:normal;}
  #pal-ride .rm-tape i.m{top:25px;height:9px;background:rgba(255,255,255,.75);}
  #pal-ride .rm-tape i s{position:absolute;left:-14px;width:29px;top:-19px;text-align:center;text-decoration:none;font-size:11px;font-weight:700;line-height:14px;color:#fff;}
  #pal-ride .rm-tape i.c s{color:#ffd166;font-size:13px;top:-20px;}
  #pal-ride .rm-compass u{position:absolute;left:50%;top:25px;width:2px;height:12px;margin-left:-1px;border-radius:1px;background:#ffd166;}
  #pal-ride .rm-where{max-width:100%;box-sizing:border-box;padding:9px 16px 9px 15px;border-radius:16px;background:rgba(14,16,26,.62);border:1px solid rgba(255,255,255,.16);}
  #pal-ride .rm-where b{display:block;font-size:15px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  #pal-ride .rm-where span{display:block;opacity:.85;font-weight:500;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  #pal-ride .rm-where em{display:block;font-style:normal;opacity:.6;font-weight:500;font-size:12px;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  #pal-ride .rm-btns{position:absolute;right:20px;top:18px;display:flex;gap:8px;pointer-events:auto;}
  #pal-ride .rm-btns button{cursor:pointer;border-radius:999px;padding:7px 14px;font:700 12px system-ui,-apple-system,"Segoe UI",sans-serif;color:#fff;background:rgba(14,16,26,.62);border:1px solid rgba(255,255,255,.2);}
  #pal-ride .rm-btns button:hover{background:rgba(44,48,72,.82);}
  #pal-ride .rm-btns button:focus-visible{outline:2px solid #ffd166;outline-offset:2px;}
  #pal-ride .rm-hint{position:absolute;left:50%;bottom:22px;transform:translateX(-50%);padding:7px 15px;border-radius:999px;background:rgba(14,16,26,.55);border:1px solid rgba(255,255,255,.14);font-weight:500;font-size:12px;white-space:nowrap;opacity:.9;transition:opacity .9s ease;}
  #pal-ride .rm-hint.gone{opacity:0;}
  #pal-ride .rm-edge{position:absolute;left:50%;bottom:64px;transform:translateX(-50%);padding:6px 14px;border-radius:999px;background:rgba(14,16,26,.5);border:1px solid rgba(255,255,255,.12);font-weight:500;font-size:12px;letter-spacing:.02em;opacity:0;transition:opacity .5s ease;pointer-events:none;white-space:nowrap;}
  #pal-ride .rm-xf{position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;opacity:1;transition:opacity .7s ease;z-index:1;}
  @media (max-width:900px){ #pal-ride .rm-compass{top:12px;} #pal-ride .rm-hint{white-space:normal;text-align:center;width:calc(100vw - 48px);} }
  @media (prefers-reduced-motion: reduce){ #pal-ride .rm-hint{transition:none;} }
"""
CSS_E = _CSS_E + CSS_DOOR + CSS_INSIDE
