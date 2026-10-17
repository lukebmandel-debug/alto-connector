"""Part G of the first-person ride: scenery (owner: the scenery agent).

Street trees (species, size and season by hash), cobra-head lamps, traffic signals (the lit lamp is a mover that follows the real cycle), street-name
blades (text from M.streets in a canvas atlas), crosswalks / stop lines / lane arrows as ground paint, benches, hydrants, mailboxes, bus shelters,
parked cars of six body types, rooftop details (HVAC, tanks, bulkheads, antennas, parapets), park trees and paths, river railings and trolley wires:
all merged static meshes in W.meshes, one per 300-unit cell. Cars driving loops around the blocks (right-hand lanes, signals, car-following),
people walking the sidewalks and a few birds are W.movers, moved every frame by sceneryUpdate (only those near the camera are in W.movers).
Everything comes from coordinates (hash, never Math.random). The contract with the renderer is written at the head of JS_G.
"""

JS_G = r"""
/* The scenery lives in its own function scope, so none of its many small helpers can collide with the names of the other parts of the ride (one shared scope).
   Only the three hooks the other parts call are public; _palScn at the end is a read-only door for the QA kit and the tests. */
var _scn=null;
function sceneryGather(W, set){ return _scn?_scn.gather(W,set):null; }
function sceneryUpdate(W, tm, Cam){ return _scn?_scn.update(W,tm,Cam):0; }
function sceneryDraw(ctx, W, P, Cam, tm){ if(_scn) _scn.draw(ctx,W,P,Cam,tm); }
(function(){
/* ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════
   SCENERY (palace_ride_g.py): street trees, lamps, signals, signs, crosswalks, parked cars, furniture, rooftops, park trees and paths,
   river railings, tram wires (static meshes -> W.meshes) and cars, people, birds (W.movers, moved every frame by sceneryUpdate).
   Everything is generated from coordinates (a hash of x and y, never a random number generator), so the same world gives the same city.

   Contract with the renderer (in addition to the mesh format of palace_ride_mesh.py):
   - W.pal = [[r,g,b]...] (<=256). For vertices of material trunk(17) leaf(18) car(19) skin(20) lamp(21) sign(22) the colour is
     W.pal[Math.round(tint*255)] (tint is the palette index / 255). lamp(21) is emissive (always unlit: it glows at night), sign(22) is paint/plates.
   - W.meshes entries: {a, id, cx, cy, r}  (cx,cy,r: bounding circle of the chunk, for culling). An entry with tex:'atlas' is text: its
     vertices use u,v = 0..1 coordinates into the canvas W.atlas.canvas (street names white on green), drawn unlit; a renderer that has no
     atlas support just skips entries with tex.
   - W.movers entries: {a, x, y, z, yaw, k}  a = shared local mesh (x forward, z up, around 0,0,0), yaw about +z (radians, x towards +y at yaw pi/2).
     sceneryUpdate keeps W.movers = the movers near the camera (<= 72), reusing the array and the objects (no allocation per frame).
   - W.lamps = Float32Array [x,y,z, x,y,z ...]: the lit head of every street and park lamp (map units), for light pools or glow sprites at night.
   - ground paint (crosswalks, stop lines, arrows) sits at z=0.07 above the road (z=0); sidewalk furniture stands at z=0.12.
   ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════ */
var MAT_TEXT=24, SZ_SW=.12, SZ_RD=.07, SCN_CELL=300;
var SCN={parapets:true, trees:true, cars:true, people:true, birds:true, signs:true, roofs:true, wires:true, debug:null, stats:{}};
function hk(x,y,k){ return hash((Math.round(x*7.13)*31+Math.round(y*3.77))*61+(k|0)*977+13); }
function hn(n,k){ return hash((n|0)*1327+(k|0)*7919+5); }

/* ── the palette (colour of the scenery materials: index/255 is the vertex tint) ── */
var PAL=[];
function pal(r,g,b){ for(var i=0;i<PAL.length;i++){ var q=PAL[i]; if(q[0]===r&&q[1]===g&&q[2]===b) return i/255; } PAL.push([r,g,b]); return (PAL.length-1)/255; }
var PC={
  leaf:[[pal(44,84,40),pal(68,118,54),pal(100,150,66)],[pal(52,92,46),pal(84,132,58),pal(116,158,72)],[pal(40,78,44),pal(58,104,50),pal(88,134,62)],[pal(54,96,52),pal(98,142,64),pal(130,168,78)],[pal(48,88,56),pal(74,128,72),pal(104,152,84)],[pal(38,74,48),pal(52,98,62),pal(76,126,80)],[pal(62,100,44),pal(110,150,70),pal(146,176,86)]],
  leafY:[[pal(96,108,40),pal(138,152,58),pal(176,180,80)],[pal(110,112,38),pal(160,156,52),pal(204,190,76)]], leafA:[[pal(170,122,30),pal(216,170,50),pal(240,208,90)],[pal(160,84,28),pal(206,124,40),pal(236,160,70)],[pal(120,38,32),pal(178,66,42),pal(214,100,60)],[pal(140,60,30),pal(198,92,44),pal(230,128,66)]],
  leafB:[[pal(206,150,170),pal(232,184,200),pal(250,214,224)],[pal(218,196,204),pal(246,226,232),pal(255,244,246)]], leafP:[[pal(24,58,42),pal(36,82,58),pal(52,108,76)],[pal(30,68,50),pal(46,94,66),pal(62,120,84)],[pal(22,54,40),pal(30,70,52),pal(44,92,66)]],
  trunkP:pal(172,164,146), stopR:pal(192,30,34), stopW:pal(236,236,230), trunk:[pal(84,66,50),pal(104,82,60),pal(70,58,48),pal(128,112,92),pal(96,88,80)],
  car:[pal(228,228,224),pal(182,186,192),pal(30,32,36),pal(72,76,82),pal(150,30,36),pal(42,72,132),pal(26,38,74),pal(38,90,66),pal(202,186,152),pal(98,30,42),pal(120,120,126),pal(176,150,110)],
  taxi:pal(240,186,26), glass:pal(30,40,54), tyre:pal(20,20,22), chrome:pal(190,194,200), head:pal(255,244,214), tail:pal(210,28,28), rubber:pal(34,34,38),
  skin:[pal(244,208,176),pal(226,178,138),pal(184,130,96),pal(132,90,66),pal(92,62,46)],
  hair:[pal(30,24,20),pal(72,50,32),pal(150,110,62),pal(176,176,178),pal(200,152,62),pal(110,36,26)],
  cloth:[pal(150,40,44),pal(40,60,110),pal(110,112,118),pal(86,96,62),pal(206,160,52),pal(52,120,124),pal(236,236,232),pal(36,36,40),pal(120,84,56),pal(110,60,130),pal(210,110,70),pal(70,110,170)],
  pants:[pal(36,44,70),pal(30,30,34),pal(170,150,110),pal(70,96,140),pal(90,92,98),pal(80,84,60),pal(120,100,86)],
  signG:pal(14,92,70), signB:pal(24,70,130), signR:pal(190,34,34), signY:pal(236,198,40), signW:pal(240,240,236), signK:pal(24,26,30), signBr:pal(120,84,52),
  lampW:pal(255,236,190), lampR:pal(255,50,40), lampRd:pal(70,16,14), lampY:pal(255,196,40), lampYd:pal(70,52,10), lampG:pal(60,255,120), lampGd:pal(14,60,28), lampOr:pal(255,168,70),
  hyd:[pal(190,36,32),pal(220,190,40)], mail:pal(28,56,120), metal:.5, rail:pal(52,58,66), bird:[pal(150,152,160),pal(226,226,226),pal(96,92,100)],
  bench:pal(110,76,48), trash:pal(40,78,60), manh:pal(46,48,52), shelter:pal(70,80,92), tank:pal(120,84,52), roofW:pal(210,212,214), hvac:pal(170,174,178), hvacD:pal(120,124,130), tar:pal(44,44,48)
};
var _rec=null, _lamps=null;      /* when set, trees and lamps are also noted here (x,y,height,radius,kind) for the 2D fallback */

/* ── a growable mesh (Float32Array backed, 10 floats a vertex) ── */
function sb(cap){ return {a:new Float32Array(cap||2048), n:0}; }
function sv(m,x,y,z,nx,ny,nz,u,v,mat,tint){ var n=m.n; if(n+10>m.a.length){ var b=new Float32Array(m.a.length*2); b.set(m.a); m.a=b; } var a=m.a; a[n]=x; a[n+1]=y; a[n+2]=z; a[n+3]=nx; a[n+4]=ny; a[n+5]=nz; a[n+6]=u; a[n+7]=v; a[n+8]=mat; a[n+9]=tint; m.n=n+10; }
function sfin(m){ return m.a.slice(0,m.n); }
function svc(m){ return m.n/10; }
/* a triangle; the normal comes from the winding; with a hint point (inside the solid) the winding is turned to face away from it */
function tr(m, ax,ay,az, bx,by,bz, cx,cy,cz, mat,tint, hx,hy,hz, u0,v0,u1,v1,u2,v2){
  var ux=bx-ax,uy=by-ay,uz=bz-az, vx=cx-ax,vy=cy-ay,vz=cz-az, nx=uy*vz-uz*vy, ny=uz*vx-ux*vz, nz=ux*vy-uy*vx, l=Math.sqrt(nx*nx+ny*ny+nz*nz); if(l<1e-9) return; nx/=l; ny/=l; nz/=l;
  var q;
  if(hx!==undefined && hx!==null){ if(nx*((ax+bx+cx)/3-hx)+ny*((ay+by+cy)/3-hy)+nz*((az+bz+cz)/3-hz)<0){ q=bx; bx=cx; cx=q; q=by; by=cy; cy=q; q=bz; bz=cz; cz=q; nx=-nx; ny=-ny; nz=-nz; q=u1; u1=u2; u2=q; q=v1; v1=v2; v2=q; } }
  sv(m,ax,ay,az,nx,ny,nz,u0||0,v0||0,mat,tint); sv(m,bx,by,bz,nx,ny,nz,u1||0,v1||0,mat,tint); sv(m,cx,cy,cz,nx,ny,nz,u2||0,v2||0,mat,tint); }
/* a quad A B C D (a convex loop), same rules */
function qd(m, ax,ay,az, bx,by,bz, cx,cy,cz, dx,dy,dz, mat,tint, hx,hy,hz){ tr(m,ax,ay,az,bx,by,bz,cx,cy,cz,mat,tint,hx,hy,hz); tr(m,ax,ay,az,cx,cy,cz,dx,dy,dz,mat,tint,hx,hy,hz); }
/* a flat quad on the ground (or any horizontal plane) facing up: a b c d are corners in order */
function gq(m, z, ax,ay, bx,by, cx,cy, dx,dy, mat,tint){ qd(m,ax,ay,z,bx,by,z,cx,cy,z,dx,dy,z,mat,tint,(ax+cx)/2,(ay+cy)/2,z-1); }

/* ── a local frame: models are authored in METRES (x forward, y lateral, z up) around (x,y,z) turned by (ca,sa) ── */
var FR={x:0,y:0,z:0,ca:1,sa:0,s:UM};
function frame(x,y,z,yaw,s){ FR.x=x; FR.y=y; FR.z=z; FR.ca=Math.cos(yaw); FR.sa=Math.sin(yaw); FR.s=s||UM; }
function frameV(x,y,z,ux,uy,s){ FR.x=x; FR.y=y; FR.z=z; FR.ca=ux; FR.sa=uy; FR.s=s||UM; }
function WX(lx,ly){ return FR.x+(lx*FR.ca-ly*FR.sa)*FR.s; }
function WY(lx,ly){ return FR.y+(lx*FR.sa+ly*FR.ca)*FR.s; }
function WZ(lz){ return FR.z+lz*FR.s; }
var _bx=new Float64Array(24);
/* a frustum between two rectangles (local x0,y0,x1,y1 at heights z0,z1): sides in (mat,tint), top in (matT,tintT); a box when the rectangles are equal */
function ffr(m, bx0,by0,bx1,by1,bz, tx0,ty0,tx1,ty1,tz, mat,tint, matT,tintT, bottom){
  var c=_bx, i;
  c[0]=WX(bx0,by0); c[1]=WY(bx0,by0); c[2]=WZ(bz);   c[3]=WX(bx1,by0); c[4]=WY(bx1,by0); c[5]=WZ(bz);
  c[6]=WX(bx1,by1); c[7]=WY(bx1,by1); c[8]=WZ(bz);   c[9]=WX(bx0,by1); c[10]=WY(bx0,by1); c[11]=WZ(bz);
  c[12]=WX(tx0,ty0); c[13]=WY(tx0,ty0); c[14]=WZ(tz); c[15]=WX(tx1,ty0); c[16]=WY(tx1,ty0); c[17]=WZ(tz);
  c[18]=WX(tx1,ty1); c[19]=WY(tx1,ty1); c[20]=WZ(tz); c[21]=WX(tx0,ty1); c[22]=WY(tx0,ty1); c[23]=WZ(tz);
  var hx=0,hy=0,hz=0; for(i=0;i<8;i++){ hx+=c[3*i]; hy+=c[3*i+1]; hz+=c[3*i+2]; } hx/=8; hy/=8; hz/=8;
  var F=[[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]], k, f;
  for(k=0;k<4;k++){ f=F[k]; qd(m,c[3*f[0]],c[3*f[0]+1],c[3*f[0]+2],c[3*f[1]],c[3*f[1]+1],c[3*f[1]+2],c[3*f[2]],c[3*f[2]+1],c[3*f[2]+2],c[3*f[3]],c[3*f[3]+1],c[3*f[3]+2],mat,tint,hx,hy,hz); }
  if(matT==null){ matT=mat; tintT=tint; }
  qd(m,c[12],c[13],c[14],c[15],c[16],c[17],c[18],c[19],c[20],c[21],c[22],c[23],matT,tintT,hx,hy,hz);
  if(bottom) qd(m,c[9],c[10],c[11],c[6],c[7],c[8],c[3],c[4],c[5],c[0],c[1],c[2],mat,tint,hx,hy,hz); }
function fbox(m, x0,y0,z0, x1,y1,z1, mat,tint, matT,tintT, bottom){ ffr(m,x0,y0,x1,y1,z0, x0,y0,x1,y1,z1, mat,tint, matT,tintT, bottom); }
/* a tapered vertical prism (tree trunk, pole, tank): centre (cx,cy), radii r0 at z0 and r1 at z1, seg sides; cap: close the top with a fan */
function fcyl(m, cx,cy,z0,z1,r0,r1,seg,mat,tint, cap, matC,tintC, bottom){
  var i, a0, a1, px0,py0,px1,py1,qx0,qy0,qx1,qy1, hx=WX(cx,cy), hy=WY(cx,cy), hz=WZ((z0+z1)/2);
  for(i=0;i<seg;i++){ a0=i/seg*6.28318; a1=(i+1)/seg*6.28318;
    var c0=Math.cos(a0), s0=Math.sin(a0), c1=Math.cos(a1), s1=Math.sin(a1);
    px0=WX(cx+c0*r0,cy+s0*r0); py0=WY(cx+c0*r0,cy+s0*r0); px1=WX(cx+c1*r0,cy+s1*r0); py1=WY(cx+c1*r0,cy+s1*r0);
    qx0=WX(cx+c0*r1,cy+s0*r1); qy0=WY(cx+c0*r1,cy+s0*r1); qx1=WX(cx+c1*r1,cy+s1*r1); qy1=WY(cx+c1*r1,cy+s1*r1);
    qd(m,px0,py0,WZ(z0),px1,py1,WZ(z0),qx1,qy1,WZ(z1),qx0,qy0,WZ(z1),mat,tint,hx,hy,hz);
    if(cap && r1>0) tr(m,qx0,qy0,WZ(z1),qx1,qy1,WZ(z1),hx,hy,WZ(z1),matC==null?mat:matC,matC==null?tint:tintC,hx,hy,hz-9);
    if(bottom) tr(m,px0,py0,WZ(z0),px1,py1,WZ(z0),hx,hy,WZ(z0),mat,tint,hx,hy,hz+9); } }
/* a cylinder lying along local y (a wheel): centre (cx,cy,cz), radius r, half-length hl, as a flat disc on each side only (cheap) */
function fdisc(m, cx,cy,cz, r, seg, sideY, mat,tint){ var i, a0,a1, ox=WX(cx,cy), oy=WY(cx,cy), oz=WZ(cz);
  for(i=0;i<seg;i++){ a0=i/seg*6.28318; a1=(i+1)/seg*6.28318;
    var x0=cx+Math.cos(a0)*r, z0=cz+Math.sin(a0)*r, x1=cx+Math.cos(a1)*r, z1=cz+Math.sin(a1)*r;
    tr(m,ox,oy,oz,WX(x0,cy),WY(x0,cy),WZ(z0),WX(x1,cy),WY(x1,cy),WZ(z1),mat,tint,WX(cx,cy-sideY),WY(cx,cy-sideY),oz); } }
/* a ribbon (flat strip) along a polyline at height z, w wide, with mitred corners: pts = [x,y,x,y...] */
function ribbon(m, pts, z, w, mat, tint){
  var n=pts.length/2, i, hw=w/2, L=[], R=[];
  for(i=0;i<n;i++){ var ax=i>0?pts[2*i]-pts[2*i-2]:pts[2*i+2]-pts[2*i], ay=i>0?pts[2*i+1]-pts[2*i-1]:pts[2*i+3]-pts[2*i+1], bx=i<n-1?pts[2*i+2]-pts[2*i]:ax, by=i<n-1?pts[2*i+3]-pts[2*i+1]:ay, la=Math.hypot(ax,ay)||1, lb=Math.hypot(bx,by)||1;
    var n1x=-ay/la, n1y=ax/la, n2x=-by/lb, n2y=bx/lb, mx=n1x+n2x, my=n1y+n2y, dd=1+n1x*n2x+n1y*n2y; if(dd<.35) dd=.35; mx=mx/dd*hw; my=my/dd*hw; L.push(pts[2*i]+mx,pts[2*i+1]+my); R.push(pts[2*i]-mx,pts[2*i+1]-my); }
  for(i=0;i+1<n;i++) gq(m,z,L[2*i],L[2*i+1],L[2*i+2],L[2*i+3],R[2*i+2],R[2*i+3],R[2*i],R[2*i+1],mat,tint); }

/* ── obstacles: a grid of building rings (and water pieces) to test points against ── */
function obNew(){ return {g:{}, cs:32}; }
function obAddRing(O, ring, pad, h){ var n=ring.length/2, x0=1e18,y0=1e18,x1=-1e18,y1=-1e18, i; for(i=0;i<n;i++){ var x=ring[2*i], y=ring[2*i+1]; if(x<x0)x0=x; if(x>x1)x1=x; if(y<y0)y0=y; if(y>y1)y1=y; }
  var it={r:ring,x0:x0-pad,y0:y0-pad,x1:x1+pad,y1:y1+pad,t:0,h:h||40}, cs=O.cs, i0=Math.floor(it.x0/cs), i1=Math.floor(it.x1/cs), j0=Math.floor(it.y0/cs), j1=Math.floor(it.y1/cs);
  if((i1-i0+1)*(j1-j0+1)>400) return; for(var a=i0;a<=i1;a++) for(var b=j0;b<=j1;b++){ var k=a+','+b; (O.g[k]||(O.g[k]=[])).push(it); } }
function obAddSeg(O, x0,y0,x1,y1, hw){ var it={x0:Math.min(x0,x1)-hw,y0:Math.min(y0,y1)-hw,x1:Math.max(x0,x1)+hw,y1:Math.max(y0,y1)+hw,t:1,ax:x0,ay:y0,bx:x1,by:y1,w:hw}, cs=O.cs, i0=Math.floor(it.x0/cs), i1=Math.floor(it.x1/cs), j0=Math.floor(it.y0/cs), j1=Math.floor(it.y1/cs);
  if((i1-i0+1)*(j1-j0+1)>400) return; for(var a=i0;a<=i1;a++) for(var b=j0;b<=j1;b++){ var k=a+','+b; (O.g[k]||(O.g[k]=[])).push(it); } }
function inRingP(x,y,r){ var c=false, n=r.length/2; for(var i=0,j=n-1;i<n;j=i++){ var xi=r[2*i], yi=r[2*i+1], xj=r[2*j], yj=r[2*j+1]; if((yi>y)!==(yj>y) && x<(xj-xi)*(y-yi)/(yj-yi)+xi) c=!c; } return c; }
function segD(x,y,ax,ay,bx,by){ var dx=bx-ax, dy=by-ay, L2=dx*dx+dy*dy, t=L2>1e-9?((x-ax)*dx+(y-ay)*dy)/L2:0; if(t<0)t=0; else if(t>1)t=1; var ex=ax+t*dx-x, ey=ay+t*dy-y; return Math.sqrt(ex*ex+ey*ey); }
function ringD(x,y,r){ var n=r.length/2, d=1e18; for(var i=0,j=n-1;i<n;j=i++){ var e=segD(x,y,r[2*j],r[2*j+1],r[2*i],r[2*i+1]); if(e<d) d=e; } return d; }
/* is (x,y) inside a ring of the grid, or within m of one (rings), or within hw+m of a segment (water) */
function obHit(O, x, y, m, kind){ var l=O.g[Math.floor(x/O.cs)+','+Math.floor(y/O.cs)]; if(!l) return false;
  for(var i=0;i<l.length;i++){ var it=l[i]; if(kind!=null && it.t!==kind) continue; if(x<it.x0-m||x>it.x1+m||y<it.y0-m||y>it.y1+m) continue;
    if(it.t===1){ if(segD(x,y,it.ax,it.ay,it.bx,it.by)<it.w+m) return true; continue; }
    if(inRingP(x,y,it.r)) return true; if(m>0 && ringD(x,y,it.r)<m) return true; }
  return false; }

/* the tallest building whose box touches the box x0,y0,x1,y1 */
function obMaxH(O, x0,y0,x1,y1){ var best=0, cs=O.cs, i0=Math.floor(x0/cs), i1=Math.floor(x1/cs), j0=Math.floor(y0/cs), j1=Math.floor(y1/cs);
  for(var a=i0;a<=i1;a++) for(var b=j0;b<=j1;b++){ var l=O.g[a+','+b]; if(!l) continue; for(var i=0;i<l.length;i++){ var it=l[i]; if(it.t===0 && it.h>best && it.x0<x1 && it.x1>x0 && it.y0<y1 && it.y1>y0) best=it.h; } }
  return best; }

/* ── models (metres in a local frame, see frame()) ── */
/* a lumpy ellipsoid canopy: prof = [[zf,rf]...] bottom to top (zf*rz above cz, rf*r radius; rf=0 is a point), seg sides, leaf tints t0/t1 alternate over the faces */
var _rg=new Float64Array(64*3), _rn=new Float64Array(64*3);
function trw(m, ax,ay,az,a0,a1,a2, bx,by,bz,b0,b1,b2, cx,cy,cz,c0,c1,c2, mat,tint){
  var ux=bx-ax,uy=by-ay,uz=bz-az, vx=cx-ax,vy=cy-ay,vz=cz-az, nx=uy*vz-uz*vy, ny=uz*vx-ux*vz, nz=ux*vy-uy*vx, q;
  if(nx*(a0+b0+c0)+ny*(a1+b1+c1)+nz*(a2+b2+c2)<0){ q=bx;bx=cx;cx=q; q=by;by=cy;cy=q; q=bz;bz=cz;cz=q; q=b0;b0=c0;c0=q; q=b1;b1=c1;c1=q; q=b2;b2=c2;c2=q; }
  sv(m,ax,ay,az,a0,a1,a2,0,0,mat,tint); sv(m,bx,by,bz,b0,b1,b2,0,0,mat,tint); sv(m,cx,cy,cz,c0,c1,c2,0,0,mat,tint); }
var _ringP=[], _ringN=[];
/* a leaf card: a square of side 2*sd at local (cx,cy,cz), facing along (nx,ny,nz) (outward from the crown: its normal is the crown's, so it shades as part of a volume), turned by rt;
   material 49 dissolves it into a leafy cluster in the shader. One winding: it is seen from outside the crown. */
function cardAt(m, cx,cy,cz, nx,ny,nz, sd, rt, tint){
  var tx=-ny, ty=nx, tz=0, tl=Math.hypot(tx,ty); if(tl<.01){ tx=1; ty=0; tl=1; } tx/=tl; ty/=tl;
  var bx=ny*tz-nz*ty, by=nz*tx-nx*tz, bz=nx*ty-ny*tx, co=Math.cos(rt), si=Math.sin(rt);
  var ax=tx*co+bx*si, ay=ty*co+by*si, az=tz*co+bz*si, ex=-tx*si+bx*co, ey=-ty*si+by*co, ez=-tz*si+bz*co, k;
  var px=[],py=[],pz=[]; var sg=[[-1,-1],[1,-1],[1,1],[-1,1]];
  for(k=0;k<4;k++){ var a=sg[k][0]*sd, b=sg[k][1]*sd, lx=cx+ax*a+ex*b, ly=cy+ay*a+ey*b, lz=cz+az*a+ez*b; px.push(WX(lx,ly)); py.push(WY(lx,ly)); pz.push(WZ(lz)); }
  var wnx=nx*FR.ca-ny*FR.sa, wny=nx*FR.sa+ny*FR.ca, wnz=nz;
  var ux=px[1]-px[0], uy=py[1]-py[0], uz=pz[1]-pz[0], vx=px[2]-px[0], vy=py[2]-py[0], vz=pz[2]-pz[0];
  var flip=((uy*vz-uz*vy)*wnx+(uz*vx-ux*vz)*wny+(ux*vy-uy*vx)*wnz)<0, id=flip?[0,3,2,1]:[0,1,2,3], uv=[[0,0],[1,0],[1,1],[0,1]];
  var tri=[[0,1,2],[0,2,3]], j;
  for(j=0;j<2;j++) for(k=0;k<3;k++){ var q=id[tri[j][k]]; sv(m,px[q],py[q],pz[q],wnx,wny,wnz,uv[q][0],uv[q][1],49,tint); } }
function fblob(m, cx,cy,cz, rx,ry,rz, prof, seg, mat, fam, jit, seed){
  var K=prof.length, k, i, nrg=[], ca=FR.ca, sa=FR.sa;
  var P=[], N=[];
  for(k=0;k<K;k++){ var zf=prof[k][0], rf=prof[k][1], z=cz+rz*zf, pk=[], nk=[];
    if(rf<=0){ pk.push([cx,cy,z]); nk.push([0,0,zf>=0?1:-1]); }
    else for(i=0;i<seg;i++){ var a=(i+.5*(k&1))/seg*6.28318, j=1+jit*(2*hash(seed*131+k*17+i*7+3)-1), lx=Math.cos(a)*rx*rf*j, ly=Math.sin(a)*ry*rf*j, lz=z+(jit*.5*rz*(hash(seed*71+k*5+i*3+9)-.5));
      var nx0=lx/(rx*rx), ny0=ly/(ry*ry), nz0=(lz-cz)/(rz*rz), nl=Math.sqrt(nx0*nx0+ny0*ny0+nz0*nz0)||1; nx0/=nl; ny0/=nl; nz0/=nl;
      pk.push([cx+lx,cy+ly,lz]); nk.push([nx0,ny0,nz0]); }
    P.push(pk); N.push(nk); }
  function W3(p){ return [WX(p[0],p[1]), WY(p[0],p[1]), WZ(p[2])]; }
  function WN(n){ return [n[0]*ca-n[1]*sa, n[0]*sa+n[1]*ca, n[2]]; }
  var isF=(typeof fam==='object'), K1=Math.max(1,K-1);
  function pick(k,i){ if(!isF) return fam; var v=k/K1+(hash(seed*37+k*11+i*3)-.5)*.55; return v<.22?fam[0]:v<.84?fam[1]:fam[2]; }
  function emit(p0,n0,p1,n1,p2,n2,tt){ var a=W3(p0), b=W3(p1), c=W3(p2), na=WN(n0), nb=WN(n1), nc=WN(n2); trw(m,a[0],a[1],a[2],na[0],na[1],na[2],b[0],b[1],b[2],nb[0],nb[1],nb[2],c[0],c[1],c[2],nc[0],nc[1],nc[2],mat,tt); }
  /* the underside: a fan to the centre of the first ring */
  if(P[0].length>1){ var ctr=[cx,cy,cz+rz*prof[0][0]], nd=[0,0,-1]; for(i=0;i<seg;i++){ emit(P[0][i],nd,P[0][(i+1)%seg],nd,ctr,nd, pick(0,i)); } }
  for(k=0;k+1<K;k++){ var A=P[k], B=P[k+1], NA=N[k], NB=N[k+1];
    if(A.length===1){ for(i=0;i<seg;i++) emit(A[0],NA[0],B[i],NB[i],B[(i+1)%seg],NB[(i+1)%seg], pick(k+.5,i)); }
    else if(B.length===1){ for(i=0;i<seg;i++) emit(A[i],NA[i],A[(i+1)%seg],NA[(i+1)%seg],B[0],NB[0], pick(k+.5,i)); }
    else for(i=0;i<seg;i++){ var i1=(i+1)%seg; emit(A[i],NA[i],A[i1],NA[i1],B[i1],NB[i1], pick(k+.3,i)); emit(A[i],NA[i],B[i1],NB[i1],B[i],NB[i], pick(k+.6,i)); } } }
/* one tree at (x,y) on the ground: sp species, sz scale (1 = ordinary), h = a hash 0..1 for the variants, season: 0 summer 1 olive 2 autumn 3 bare 4 blossom */
function treeAt(m, x, y, sp, sz, h, season, lod, lobe){
  frame(x, y, SZ_SW, h*6.28, UM*sz); var g=hash(Math.round(x*3)+Math.round(y*5)*977), seed=Math.round(x*5+y*3), ttr=PC.trunk[(g*5)|0], fam;
  if(season===0) fam=PC.leaf[(g*PC.leaf.length*3.1|0)%PC.leaf.length]; else if(season===1) fam=PC.leafY[(g*2)|0]; else if(season===2) fam=PC.leafA[(g*4)|0]; else if(season===4) fam=PC.leafB[(g*2)|0]; else fam=PC.leaf[0];
  if(sp===3){                                            /* conifer: three tiers */
    var H=7+g*4; fcyl(m,0,0,0,H*.35,.2,.14,5,MAT.trunk,ttr,false); fam=PC.leafP[(g*3)|0];
    fblob(m,0,0,H*.34,2.4,2.4,H*.3,[[0,.0],[0,1],[.5,.75],[1,0]],7,MAT.leaf,fam,.1,seed);
    fblob(m,0,0,H*.52,1.9,1.9,H*.26,[[0,.0],[0,1],[.5,.75],[1,0]],7,MAT.leaf,fam,.1,seed+1);
    fblob(m,0,0,H*.7,1.3,1.3,H*.3,[[0,.0],[0,1],[.5,.7],[1,0]],6,MAT.leaf,fam,.1,seed+2);
    if(_rec) _rec.push(x,y,H*UM*sz,2.4*UM*sz,2); return; }
  if(season===3){                                        /* bare in winter: a trunk and three limbs */
    fcyl(m,0,0,0,4,.3,.16,5,MAT.trunk,ttr,true);
    for(var b=0;b<3;b++){ var a=b*2.09+g*6; fblob(m,Math.cos(a)*1.1,Math.sin(a)*1.1,5.0,.3,.3,1.8,[[-1,0],[-.2,1],[1,0]],4,MAT.trunk,ttr,.2,seed+b); }
    if(_rec) _rec.push(x,y,6*UM*sz,1.4*UM*sz,3); return; }
  var th, R, rz, prof, seg=7; if(sp===0) ttr=PC.trunkP;
  if(sp===0){ th=3.8+g*1.4; R=4.4+g*1.5; rz=R*.82; prof=[[-.5,.6],[-.05,1],[.5,.82],[1,0]]; }               /* plane tree: broad */
  else if(sp===1){ th=3.4+g*1.2; R=3.2+g*.8; rz=R*1.5; prof=[[-.6,.5],[-.2,.95],[.45,.9],[1,.45],[1.25,0]]; seg=6; }   /* oval (zelkova, honey locust) */
  else if(sp===2){ th=3+g*1; R=5.6+g*1.6; rz=R*.72; prof=[[-.5,.7],[0,1],[.45,.85],[.9,0]]; }                    /* oak: wide */
  else if(sp===4){ th=2.1+g*.5; R=2.5+g*.6; rz=R*.8; prof=[[-.5,.6],[0,1],[.5,.8],[1,0]]; seg=6; }               /* ornamental cherry: small */
  else { th=2.4; R=1.5+g*.3; rz=R*3.4; prof=[[-.4,.5],[.1,1],[.8,.8],[1.2,.35],[1.4,0]]; seg=6; }                /* columnar */
  fcyl(m,0,0,0,th+.6,.30*(1+g*.2),.2,5,MAT.trunk,ttr,true);
  var cz=th+rz*.45;
  if(_rec) _rec.push(x,y,(cz+rz)*UM*sz,R*UM*sz,season===2?3:2);
  if(!lod && sp!==5){                                    /* a dark core of leaves with clusters of leaf cards over it */
    fblob(m,0,0,cz,R*.62,R*.62,rz*.62,prof,5,MAT.leaf,fam[1],.1,seed);
    var nc=sp===4?18:32, ci;
    for(ci=0;ci<nc;ci++){ var ha=hash(seed*13+ci*7+1)*6.2832, hz=-.3+1.28*hash(seed*17+ci*11+2), hr=Math.sqrt(Math.max(0,1-hz*hz)), dx=Math.cos(ha)*hr, dy=Math.sin(ha)*hr, dz=hz, rr=.7+.3*hash(seed*43+ci);
      var qx=dx*R*rr, qy=dy*R*rr, qz=cz+dz*rz*rr, nx0=dx/R, ny0=dy/R, nz0=dz/rz, nl0=Math.hypot(nx0,ny0,nz0)||1;
      var pk3=hash(seed*19+ci*5+3), tn=pk3<.2?fam[0]:pk3<.75?fam[1]:fam[2];
      cardAt(m,qx,qy,qz,nx0/nl0+(hash(seed*31+ci)-.5)*.7,ny0/nl0+(hash(seed*37+ci)-.5)*.7,nz0/nl0+.25+(hash(seed*41+ci)-.5)*.6,R*(.38+.24*hash(seed*23+ci)),hash(seed*29+ci)*6.28,tn); } }
  else fblob(m,0,0,cz,R,R,rz,prof,seg,MAT.leaf,fam,.16,seed);
  if(!lod && sp!==5 && sp!==4 && g>.12){ var a4=g*29+1.3, d4=R*(.5+.25*hash(seed+4)); fblob(m,Math.cos(a4)*d4,Math.sin(a4)*d4,cz-rz*(.1+.3*hash(seed+5)),R*.55,R*.55,rz*.58,[[-.5,.6],[0,1],[1,0]],5,MAT.leaf,fam,.24,seed+7); }      /* a second lobe: the crown is not one ball */

  if(!lod && lobe && (sp===0||sp===2) && g>.35){ var a3=g*17;
    fblob(m,Math.cos(a3)*R*.62,Math.sin(a3)*R*.62,cz+rz*.12,R*.62,R*.62,rz*.7,[[-.4,.6],[0,1],[.5,.7],[1,0]],6,MAT.leaf,fam,.18,seed+9); } }

/* a cobra-head street lamp: the pole at the origin, arm and head out along +x (toward the street) */
function lampAt(m, x, y, ox, oy, h){   /* (ox,oy) unit vector toward the street */
  frameV(x,y,SZ_SW,ox,oy,UM); var ph=7.6; if(_rec) _rec.push(x,y,ph*UM,1,1); if(_lamps) _lamps.push(x+ox*2.1*UM,y+oy*2.1*UM,SZ_SW+(ph-.3)*UM);
  fcyl(m,0,0,0,ph,.13,.085,5,MAT.metal,PC.rail,false);
  fbox(m,0,-.045,ph-.12,2.3,.045,ph+.06,MAT.metal,PC.rail);                    /* the arm */
  fbox(m,1.55,-.2,ph-.22,2.7,.2,ph-.04,MAT.metal,PC.rail,MAT.metal,PC.rail);   /* the head */
  var hx=WX(2.1,0), hy=WY(2.1,0);
  qd(m,WX(1.58,-.17),WY(1.58,-.17),WZ(ph-.225),WX(2.65,-.17),WY(2.65,-.17),WZ(ph-.225),WX(2.65,.17),WY(2.65,.17),WZ(ph-.225),WX(1.58,.17),WY(1.58,.17),WZ(ph-.225),MAT.lamp,PC.lampW,hx,hy,WZ(ph+2)); }
/* a post-top lamp for park paths and plazas */
function lampPark(m, x, y){
  frame(x,y,SZ_SW,0,UM); if(_rec) _rec.push(x,y,4*UM,1,0); if(_lamps) _lamps.push(x,y,SZ_SW+3.8*UM); fcyl(m,0,0,0,3.4,.1,.07,5,MAT.metal,PC.rail,false); fcyl(m,0,0,3.4,3.55,.2,.2,6,MAT.metal,PC.rail,false);
  fcyl(m,0,0,3.55,4.0,.22,.16,6,MAT.lamp,PC.lampW,true); }
function benchAt(m, x, y, ox, oy){          /* seat facing (ox,oy) */
  frameV(x,y,SZ_SW,ox,oy,UM);
  fbox(m,-.1,-.8,.42,.36,.8,.47,MAT.wood,PC.bench,MAT.wood,PC.bench);
  fbox(m,-.18,-.8,.47,-.12,.8,.92,MAT.wood,PC.bench);
  fbox(m,-.05,-.72,0,.05,-.62,.42,MAT.metal,PC.rail); fbox(m,-.05,.62,0,.05,.72,.42,MAT.metal,PC.rail); }
function hydrantAt(m, x, y, ox, oy, h){
  frameV(x,y,SZ_SW,ox,oy,UM); var c=PC.hyd[h<.7?0:1];
  fcyl(m,0,0,0,.62,.17,.15,6,MAT.sign,c,true,MAT.sign,c); fbox(m,-.26,-.045,.34,.26,.045,.44,MAT.sign,c); fcyl(m,0,0,.62,.74,.09,.05,6,MAT.sign,c,true); }
function trashAt(m, x, y){
  frame(x,y,SZ_SW,0,UM); fcyl(m,0,0,0,.92,.27,.3,6,MAT.sign,PC.trash,true,MAT.sign,PC.rubber); }
function manholeAt(m, x, y){ var n=8, i, r=.5*UM; for(i=0;i<n;i++){ var a0=i/n*6.28318, a1=(i+1)/n*6.28318; tr(m,x,y,SZ_RD+.01,x+Math.cos(a0)*r,y+Math.sin(a0)*r,SZ_RD+.01,x+Math.cos(a1)*r,y+Math.sin(a1)*r,SZ_RD+.01,MAT.sign,PC.manh,x,y,-1); } }
function mailboxAt(m, x, y, ox, oy){
  frameV(x,y,SZ_SW,ox,oy,UM); fbox(m,-.26,-.28,0,.26,.28,.15,MAT.metal,PC.rail);
  ffr(m,-.26,-.28,.26,.28,.15,-.2,-.28,.2,.28,1.05,MAT.sign,PC.mail,MAT.sign,PC.mail); }
/* a traffic signal pole with a mast arm over the lane and a head facing back along (fx,fy) (the way the traffic comes from) */
/* a stop sign on its pole at (x,y), the face turned along (fx,fy): a white octagon with a red one set in it and a white bar for the word */
function stopSignAt(m, x, y, fx, fy){
  frameV(x,y,SZ_SW,fx,fy,UM); var zc=2.45, k, a0, a1, hxw=WX(-.6,0), hyw=WY(-.6,0), hzw=WZ(zc);
  fcyl(m,0,0,0,zc,.05,.05,5,MAT.metal,PC.rail,true);
  /* the local y axis is across the face: points are (xl, yl, z) */
  function oct(xl,r,tint){ for(k=0;k<8;k++){ a0=(k+.5)/8*6.28318; a1=(k+1.5)/8*6.28318;
    var y0=r*Math.cos(a0), z0=r*Math.sin(a0), y1=r*Math.cos(a1), z1=r*Math.sin(a1);
    tr(m,WX(xl,0),WY(xl,0),WZ(zc),WX(xl,y0),WY(xl,y0),WZ(zc+z0),WX(xl,y1),WY(xl,y1),WZ(zc+z1),MAT.sign,tint,hxw,hyw,hzw); } }
  oct(.07,.4,PC.stopW); oct(.09,.33,PC.stopR);
  qd(m,WX(.1,-.2),WY(.1,-.2),WZ(zc-.045),WX(.1,.2),WY(.1,.2),WZ(zc-.045),WX(.1,.2),WY(.1,.2),WZ(zc+.045),WX(.1,-.2),WY(.1,-.2),WZ(zc+.045),MAT.sign,PC.stopW,hxw,hyw,hzw); }
function signalAt(m, x, y, ax, ay, fx, fy, st){      /* (ax,ay): unit toward the lane (over the road); (fx,fy): the head faces this way */
  frameV(x,y,SZ_SW,ax,ay,UM); var ph=5.5;
  fcyl(m,0,0,0,ph,.14,.1,6,MAT.metal,PC.rail,false);
  fbox(m,0,-.05,ph-.1,5.8,.05,ph+.05,MAT.metal,PC.rail);
  /* head hung at the end of the arm, facing along (fx,fy) = local (fx*ax+fy*ay, ...) */
  var lx=fx*ax+fy*ay, ly=-fx*ay+fy*ax;   /* the facing in local coordinates (rotation by -yaw) */
  var cx=5.0, cy=0, zt=ph-.1; var hl=Math.atan2(ly,lx); var cs=Math.cos(hl), sn=Math.sin(hl);
  /* local box of the head: depth along the facing .3, width .34 across, 1.0 tall; corners via rotation by hl */
  var d=.15, w=.17, z0=zt-1.15, z1=zt-.05;
  function P(u,v){ return [cx+u*cs-v*sn, cy+u*sn+v*cs]; }
  var c0=P(-d,-w), c1=P(d,-w), c2=P(d,w), c3=P(-d,w), hxw=WX(cx,cy), hyw=WY(cx,cy), hzw=WZ((z0+z1)/2);
  var cc=[c0,c1,c2,c3], k, a, b;
  for(k=0;k<4;k++){ a=cc[k]; b=cc[(k+1)%4]; qd(m,WX(a[0],a[1]),WY(a[0],a[1]),WZ(z0),WX(b[0],b[1]),WY(b[0],b[1]),WZ(z0),WX(b[0],b[1]),WY(b[0],b[1]),WZ(z1),WX(a[0],a[1]),WY(a[0],a[1]),WZ(z1),MAT.metal,PC.signK,hxw,hyw,hzw); }
  qd(m,WX(c0[0],c0[1]),WY(c0[0],c0[1]),WZ(z1),WX(c1[0],c1[1]),WY(c1[0],c1[1]),WZ(z1),WX(c2[0],c2[1]),WY(c2[0],c2[1]),WZ(z1),WX(c3[0],c3[1]),WY(c3[0],c3[1]),WZ(z1),MAT.metal,PC.signK,hxw,hyw,hzw);
  /* the three lamps on the facing side: red, yellow, green; st = 0 red, 1 green, 2 yellow */
  var cols=[[PC.lampR,PC.lampRd],[PC.lampY,PC.lampYd],[PC.lampG,PC.lampGd]], on=st<0?-1:st===0?0:st===2?1:2, zz;
  for(k=0;k<3;k++){ zz=z1-.22-k*.33; var p0=P(d+.015,-.1), p1=P(d+.015,.1), tc=cols[k][k===on?0:1];
    qd(m,WX(p0[0],p0[1]),WY(p0[0],p0[1]),WZ(zz-.1),WX(p1[0],p1[1]),WY(p1[0],p1[1]),WZ(zz-.1),WX(p1[0],p1[1]),WY(p1[0],p1[1]),WZ(zz+.1),WX(p0[0],p0[1]),WY(p0[0],p0[1]),WZ(zz+.1),MAT.lamp,tc,hxw,hyw,hzw); }
  return [hxw,hyw]; }
/* a bus shelter: back panel to (-x), open toward +x */
function shelterAt(m, x, y, ox, oy){
  frameV(x,y,SZ_SW,ox,oy,UM); var w=2.2;
  fbox(m,-1.0,-w,2.35,.6,w,2.5,MAT.metal,PC.shelter,MAT.metal,PC.shelter);                   /* roof */
  fbox(m,-1.0,-w,.2,-.95,w,2.35,MAT.glass,0);                                                /* back glass */
  fbox(m,-1.0,-w,.2,.2,-w+.06,2.35,MAT.glass,0); fbox(m,-1.0,w-.06,.2,.2,w,2.35,MAT.glass,0);  /* sides */
  fbox(m,-.9,-w+.1,.45,-.4,w-.1,.52,MAT.wood,PC.bench);                                      /* bench */
  fbox(m,-1.0,-.9,.9,-.9+.02,.9,2.0,MAT.lamp,PC.lampW);                                     /* the lit advertising panel */
  fbox(m,.5,-w,0,.6,-w+.08,2.35,MAT.metal,PC.shelter); fbox(m,.5,w-.08,0,.6,w,2.35,MAT.metal,PC.shelter); }
/* a street name blade pair at the top of a pole. Text goes to the atlas mesh tm (u,v 0..1 in the atlas): rectH / rectV = [u0,v0,u1,v1] of the name along (ux,uy) and across */
function quv(m, P, mat, tint, hx,hy,hz, uv){ tr(m,P[0],P[1],P[2],P[3],P[4],P[5],P[6],P[7],P[8],mat,tint,hx,hy,hz,uv[0],uv[1],uv[2],uv[3],uv[4],uv[5]); tr(m,P[0],P[1],P[2],P[6],P[7],P[8],P[9],P[10],P[11],mat,tint,hx,hy,hz,uv[0],uv[1],uv[4],uv[5],uv[6],uv[7]); }
function signPoleAt(m, tm, x, y, ux, uy, rectH, rectV){
  frameV(x,y,SZ_SW,ux,uy,UM); fcyl(m,0,0,0,5.3,.07,.06,5,MAT.metal,PC.rail,false);
  var P=[0,0,0,0,0,0,0,0,0,0,0,0];
  function blade(rot, rect, zc){ if(!rect) return; var c=Math.cos(rot), s=Math.sin(rot), hw=.62, hh=.14, nx=-s, ny=c;
    for(var side=-1; side<=1; side+=2){
      var o=.02*side, ax=-hw*c+nx*o, ay=-hw*s+ny*o, bx=hw*c+nx*o, by=hw*s+ny*o;
      var hx=WX(nx*side*-1,ny*side*-1), hy=WY(nx*side*-1,ny*side*-1), hz=WZ(zc);   /* a point behind the face */
      P[0]=WX(ax,ay); P[1]=WY(ax,ay); P[2]=WZ(zc-hh); P[3]=WX(bx,by); P[4]=WY(bx,by); P[5]=WZ(zc-hh); P[6]=WX(bx,by); P[7]=WY(bx,by); P[8]=WZ(zc+hh); P[9]=WX(ax,ay); P[10]=WY(ax,ay); P[11]=WZ(zc+hh);
      quv(m,P,MAT.sign,PC.signG,hx,hy,hz,[0,0,0,0,0,0,0,0]);
      var o2=.035*side; ax=-hw*c+nx*o2; ay=-hw*s+ny*o2; bx=hw*c+nx*o2; by=hw*s+ny*o2;
      /* text readable from the +n side runs along +dir; from the -n side along -dir */
      var uA=side>0?rect[0]:rect[2], uB=side>0?rect[2]:rect[0];
      P[0]=WX(ax,ay); P[1]=WY(ax,ay); P[2]=WZ(zc-hh); P[3]=WX(bx,by); P[4]=WY(bx,by); P[5]=WZ(zc-hh); P[6]=WX(bx,by); P[7]=WY(bx,by); P[8]=WZ(zc+hh); P[9]=WX(ax,ay); P[10]=WY(ax,ay); P[11]=WZ(zc+hh);
      quv(tm,P,MAT_TEXT,0,hx,hy,hz,[uA,rect[3],uB,rect[3],uB,rect[1],uA,rect[1]]); } }
  blade(0, rectH, 5.35); blade(1.5708, rectV, 5.7); }

/* ── cars ── */
var CAR_T=[   /* L, W, ls = lower body stations [x, top z, half width], cs = cabin stations [x, z, half width] (belt, roof, roof, belt) */
  {n:'sedan',  L:4.6, W:1.82, ls:[[0,.62,.78],[.45,.92,.9],[3.75,.9,.9],[4.6,.64,.8]],     cs:[[1.0,.92,.78],[1.75,1.42,.66],[2.95,1.42,.66],[3.55,.9,.78]]},
  {n:'suv',    L:4.7, W:1.92, ls:[[0,.75,.82],[.35,1.06,.93],[4.1,1.04,.93],[4.7,.8,.84]], cs:[[.75,1.05,.83],[1.1,1.72,.78],[3.55,1.72,.78],[4.1,1.04,.83]]},
  {n:'hatch',  L:3.9, W:1.74, ls:[[0,.64,.76],[.3,.9,.86],[3.3,.88,.86],[3.9,.62,.76]],   cs:[[.5,.9,.75],[1.15,1.46,.66],[2.45,1.46,.66],[3.05,.88,.76]]},
  {n:'pickup', L:5.4, W:2.0,  ls:[[0,.82,.9],[.2,1.04,.95],[4.6,1.04,.95],[5.4,.8,.88]],  cs:[[2.35,1.05,.88],[2.75,1.78,.8],[3.6,1.78,.8],[4.2,1.04,.88]]},
  {n:'van',    L:5.2, W:2.0,  ls:[[0,.8,.9],[.25,1.02,.98],[4.7,1.0,.98],[5.2,.78,.9]],   cs:[[.3,1.02,.93],[.45,2.12,.89],[4.35,2.12,.89],[4.75,1.3,.9]]},
  {n:'coupe',  L:4.4, W:1.8,  ls:[[0,.6,.76],[.4,.88,.9],[3.6,.86,.9],[4.4,.62,.78]],     cs:[[1.25,.88,.76],[2.0,1.32,.66],[2.75,1.32,.66],[3.3,.86,.76]]}
];
/* a car at its frame (the caller sets frame(): x forward, rear bumper at 0); detail adds wheels and lights */
function lowTop(ls,x){ for(var i=0;i+1<ls.length;i++){ if(x<=ls[i+1][0]){ var t=(x-ls[i][0])/((ls[i+1][0]-ls[i][0])||1); return ls[i][1]+(ls[i+1][1]-ls[i][1])*t; } } return ls[ls.length-1][1]; }
function carBody(m, T, tint, detail, taxi){
  var L=T.L, ls=T.ls, cs=T.cs, i, zb=.27, zs=.46, hx=WX(L/2,0), hy=WY(L/2,0), hz=WZ(.7), hw=T.W/2, sd, nl=ls.length;
  function P(x,y,z){ return [WX(x,y),WY(x,y),WZ(z)]; }
  function Q(a,b,c,d,mat,t){ qd(m,a[0],a[1],a[2],b[0],b[1],b[2],c[0],c[1],c[2],d[0],d[1],d[2],mat,t,hx,hy,hz); }
  function Tri(a,b,c,mat,t){ tr(m,a[0],a[1],a[2],b[0],b[1],b[2],c[0],c[1],c[2],mat,t,hx,hy,hz); }
  for(sd=-1;sd<=1;sd+=2){
    /* the dark skirt, and the flank as one painted fan (bottom edge at the skirt's top, top edge the line of hood, deck and trunk) */
    Q(P(0,sd*ls[0][2]*.93,zb),P(L,sd*ls[nl-1][2]*.93,zb),P(L,sd*ls[nl-1][2]*.94,zs),P(0,sd*ls[0][2]*.94,zs),MAT.car,PC.rubber);
    var pr=[P(0,sd*ls[0][2]*.94,zs)]; for(i=0;i<nl;i++) pr.push(P(ls[i][0],sd*ls[i][2],ls[i][1])); pr.push(P(L,sd*ls[nl-1][2]*.94,zs));
    for(i=1;i+1<pr.length;i++) Tri(pr[0],pr[i],pr[i+1],MAT.car,tint);
    /* the cabin's side glass: one trapezoid from the rear base to the front base over the roof line */
    var bA=lowTop(ls,cs[0][0]), bB=lowTop(ls,cs[3][0]);
    Q(P(cs[0][0],sd*(cs[0][2]+.1),bA),P(cs[3][0],sd*(cs[3][2]+.1),bB),P(cs[2][0],sd*cs[2][2],cs[2][1]),P(cs[1][0],sd*cs[1][2],cs[1][1]),MAT.car,PC.glass); }
  /* the top: hood, deck and trunk; the ends; the cabin's rear glass, roof and windshield */
  for(i=0;i+1<nl;i++) Q(P(ls[i][0],-ls[i][2],ls[i][1]),P(ls[i+1][0],-ls[i+1][2],ls[i+1][1]),P(ls[i+1][0],ls[i+1][2],ls[i+1][1]),P(ls[i][0],ls[i][2],ls[i][1]),MAT.car,tint);
  [ls[0],ls[nl-1]].forEach(function(S){ Q(P(S[0],-S[2]*.93,zb),P(S[0],S[2]*.93,zb),P(S[0],S[2],S[1]),P(S[0],-S[2],S[1]),MAT.car,tint); });
  for(i=0;i+1<cs.length;i++) Q(P(cs[i][0],-cs[i][2],cs[i][1]),P(cs[i+1][0],-cs[i+1][2],cs[i+1][1]),P(cs[i+1][0],cs[i+1][2],cs[i+1][1]),P(cs[i][0],cs[i][2],cs[i][1]),MAT.car,i===1?tint:PC.glass);
  if(taxi){ var rz2=cs[1][1]; fbox(m,cs[1][0]+.5,-.22,rz2,cs[1][0]+.95,.22,rz2+.2,MAT.car,PC.signW,MAT.lamp,PC.lampOr); }
  if(detail){
    var wz=.33, wx0=.85, wx1=L-.85;
    [[wx0,1],[wx0,-1],[wx1,1],[wx1,-1]].forEach(function(w){ fdisc(m,w[0],w[1]*(hw*.94+.005),wz,.33,8,w[1],MAT.car,PC.tyre); fdisc(m,w[0],w[1]*(hw*.94+.012),wz,.19,6,w[1],MAT.car,PC.chrome); });
    var zl=ls[nl-1][1], zr=ls[0][1];
    function lamp(x,y0,y1,z0,z1,t){ Q(P(x,y0,z0),P(x,y1,z0),P(x,y1,z1),P(x,y0,z1),MAT.lamp,t); }
    lamp(L+.01,-hw*.8,-hw*.45,zl-.2,zl-.08,PC.head); lamp(L+.01,hw*.45,hw*.8,zl-.2,zl-.08,PC.head);
    lamp(-.01,-hw*.8,-hw*.45,zr-.22,zr-.1,PC.tail); lamp(-.01,hw*.45,hw*.8,zr-.22,zr-.1,PC.tail); }
  else { [.9,L-.85].forEach(function(wx){ for(sd=-1;sd<=1;sd+=2){ var y=sd*(hw*.94+.012); Q(P(wx-.3,y,.05),P(wx+.3,y,.05),P(wx+.3,y,.62),P(wx-.3,y,.62),MAT.car,PC.tyre); } }); } }
/* a parked car at (x,y) heading (ux,uy), model type ti, colour index ci */
function carParked(m, x, y, ux, uy, ti, ci, taxi){
  var T=CAR_T[ti]; frameV(x-ux*T.L*.5*UM,y-uy*T.L*.5*UM,SZ_SW,ux,uy,UM); carBody(m,T,taxi?PC.taxi:PC.car[ci],false,taxi); }
/* a city bus (movers) */
function busBody(m, tint){
  var L=11.6, hw=1.28;
  ffr(m,0,-hw,L,hw,.55, .1,-hw*.98,L-.1,hw*.98,3.25, MAT.car,tint, MAT.car,PC.roofW);
  fbox(m,.3,-hw*1.0,.95,L-.3,hw*1.0,1.5,MAT.car,tint);
  ffr(m,.05,-hw*1.001,L-.05,hw*1.001,1.55,.05,-hw*1.001,L-.05,hw*1.001,2.8,MAT.car,PC.glass);          /* the window band (a touch proud of the body) */
  fbox(m,.02,-hw*.98,.2,L-.02,hw*.98,.6,MAT.car,PC.rubber);
  [[1.5,1],[1.5,-1],[8.8,1],[8.8,-1]].forEach(function(w){ fdisc(m,w[0],w[1]*(hw+.005),.5,.5,8,w[1],MAT.car,PC.tyre); fdisc(m,w[0],w[1]*(hw+.012),.5,.28,6,w[1],MAT.car,PC.chrome); });
  qd(m,WX(L,-.9),WY(L,-.9),WZ(2.8),WX(L,.9),WY(L,.9),WZ(2.8),WX(L,.9),WY(L,.9),WZ(3.1),WX(L,-.9),WY(L,-.9),WZ(3.1),MAT.lamp,PC.lampOr,WX(L-1,0),WY(L-1,0),WZ(3)); }

/* ── people: a low-poly figure with pose angle a (radians of leg swing) ── */
function frot(m, px,py,pz, ang, x0,y0,z0, x1,y1,z1, mat,tint, matT,tintT, tp){   /* a (tapered) box about a pivot, turned about the lateral axis by ang; tp = the rectangle at z1 */
  var c=Math.cos(ang), s=Math.sin(ang), k, t=tp||[x0,y0,x1,y1], cx=[x0,x1,x1,x0,t[0],t[2],t[2],t[0]], cy=[y0,y0,y1,y1,t[1],t[1],t[3],t[3]], cz=[z0,z0,z0,z0,z1,z1,z1,z1], P=[];
  for(k=0;k<8;k++){ var lx=px+cx[k]*c+cz[k]*s, lz=pz-cx[k]*s+cz[k]*c; P.push(WX(lx,py+cy[k]), WY(lx,py+cy[k]), WZ(lz)); }
  var hx=0,hy=0,hz=0; for(k=0;k<8;k++){ hx+=P[3*k]; hy+=P[3*k+1]; hz+=P[3*k+2]; } hx/=8; hy/=8; hz/=8;
  var F=[[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]], f;
  for(k=0;k<4;k++){ f=F[k]; qd(m,P[3*f[0]],P[3*f[0]+1],P[3*f[0]+2],P[3*f[1]],P[3*f[1]+1],P[3*f[1]+2],P[3*f[2]],P[3*f[2]+1],P[3*f[2]+2],P[3*f[3]],P[3*f[3]+1],P[3*f[3]+2],mat,tint,hx,hy,hz); }
  qd(m,P[12],P[13],P[14],P[15],P[16],P[17],P[18],P[19],P[20],P[21],P[22],P[23],matT==null?mat:matT,matT==null?tint:tintT,hx,hy,hz);
  qd(m,P[9],P[10],P[11],P[6],P[7],P[8],P[3],P[4],P[5],P[0],P[1],P[2],mat,tint,hx,hy,hz); }
/* type 0 man, 1 woman (long coat), 2 child; look = {skin,hair,top,bot}; pose 0..5 */
function personMesh(type, look, pose){
  var m=sb(8192), sc=type===2?.64:1, sw=Math.sin(pose/6*6.28318)*.55, sk=PC.skin[look.skin], hr=PC.hair[look.hair], top=PC.cloth[look.top], bot=PC.pants[look.bot], shoe=PC.rubber;
  frame(0,0,0,0,UM*sc);
  /* legs: tapered, with a shoe (a skirt coat hides the thigh) */
  [-1,1].forEach(function(sd){ var a=sd*sw;
    frot(m,0,sd*.1,.93,a,-.075,-.07,-.86,.075,.07,0,MAT.car,bot,MAT.car,bot,[-.05,-.05,.05,.05]);
    frot(m,0,sd*.1,.93,a,-.06,-.055,-.92,.15,.055,-.86,MAT.car,shoe,MAT.car,shoe); });
  /* torso, a coat flares to the knee */
  if(type===1) ffr(m,-.15,-.26,.15,.26,.55,-.1,-.22,.1,.22,1.46,MAT.car,top,MAT.car,top);
  else ffr(m,-.12,-.21,.12,.21,.93,-.1,-.25,.1,.25,1.46,MAT.car,top,MAT.car,top);
  /* arms (the sleeve runs to the hand), head (a hexagon) with a hair cap */
  [-1,1].forEach(function(sd){ var a=-sd*sw*.9; frot(m,0,sd*.3,1.42,a,-.055,-.05,-.68,.055,.05,0,MAT.car,top,MAT.car,sk,[-.04,-.035,.04,.035]); });
  fcyl(m,0,0,1.5,1.74,.098,.09,6,MAT.skin,sk,false);
  fcyl(m,0,0,1.64,1.79,.108,.1,6,MAT.skin,hr,true,MAT.skin,hr);
  if(type===1) fbox(m,-.17,-.1,1.36,-.08,.1,1.7,MAT.skin,hr);
  return sfin(m); }
function birdMesh(kind, wing){   /* wing -1 down, 0 level, 1 up */
  var m=sb(512), col=PC.bird[kind], dk=PC.bird[2]; frame(0,0,0,0,UM);
  ffr(m,-.12,-.05,.14,.05,-.04,-.1,-.03,.1,.03,.05,MAT.skin,col,MAT.skin,col);               /* body */
  fbox(m,.14,-.025,.0,.2,.025,.07,MAT.skin,dk);                                              /* head */
  fbox(m,-.26,-.03,-.01,-.12,.03,.01,MAT.skin,dk);                                           /* tail */
  var a=wing*.7, c=Math.cos(a), s=Math.sin(a);
  [-1,1].forEach(function(sd){ var x0=-.05, x1=.1, y0=sd*.05, y1=sd*(.05+.34*c), z1=.34*s*sd*sd; var hx=WX(0,0), hy=WY(0,0), hz=WZ(0);
    qd(m,WX(x0,y0),WY(x0,y0),WZ(0),WX(x1,y0),WY(x1,y0),WZ(0),WX(x1+.04,y1),WY(x1+.04,y1),WZ(z1),WX(x0-.06,y1),WY(x0-.06,y1),WZ(z1),MAT.skin,col,hx,hy,hz-1);
    qd(m,WX(x0,y0),WY(x0,y0),WZ(0),WX(x0-.06,y1),WY(x0-.06,y1),WZ(z1),WX(x1+.04,y1),WY(x1+.04,y1),WZ(z1),WX(x1,y0),WY(x1,y0),WZ(0),MAT.skin,col,hx,hy,hz+1); });
  return sfin(m); }

/* ── the street index (names and ranks for signs, shelters, lamps) ── */
var _SI=null, _SIm=null;
function streetIndex(){
  var Mp=E&&E.M; if(!Mp||!Mp.streets) return {g:{},cs:64,names:[]}; if(_SI && _SIm===Mp) return _SI;
  var SI={g:{}, cs:64, names:[], nid:{}}, cs=SI.cs;
  Mp.streets.forEach(function(s){ if(s.t||!s.n) return; var id=SI.nid[s.n]; if(id==null){ id=SI.names.length; SI.names.push(s.n); SI.nid[s.n]=id; } var p=s.p;
    for(var i=0;i+3<p.length;i+=2){ var ax=p[i], ay=p[i+1], bx=p[i+2], by=p[i+3], l=Math.hypot(bx-ax,by-ay); if(l<1) continue; var seg={ax:ax,ay:ay,bx:bx,by:by,ux:(bx-ax)/l,uy:(by-ay)/l,id:id,k:s.k==null?4:s.k,o:s.o?1:0};
      var i0=Math.floor((Math.min(ax,bx)-12)/cs), i1=Math.floor((Math.max(ax,bx)+12)/cs), j0=Math.floor((Math.min(ay,by)-12)/cs), j1=Math.floor((Math.max(ay,by)+12)/cs);
      for(var a=i0;a<=i1;a++) for(var b=j0;b<=j1;b++){ var key=a+','+b; (SI.g[key]||(SI.g[key]=[])).push(seg); } } });
  _SI=SI; _SIm=Mp; return SI; }
/* the street whose line runs within r of (x,y) and parallel to (ux,uy) (|cos|>=cmin): {id,k,o} or null */
function streetAt(SI, x, y, ux, uy, r, cmin){ var l=SI.g[Math.floor(x/SI.cs)+','+Math.floor(y/SI.cs)]; if(!l) return null; var best=null, bd=r;
  for(var i=0;i<l.length;i++){ var s=l[i]; if(ux!==null && Math.abs(s.ux*ux+s.uy*uy)<cmin) continue; var d=segD(x,y,s.ax,s.ay,s.bx,s.by); if(d<bd){ bd=d; best=s; } }
  return best; }
function nearStreet(SI,x,y,r){ var l=SI.g[Math.floor(x/SI.cs)+','+Math.floor(y/SI.cs)]; if(!l) return false; for(var i=0;i<l.length;i++){ var s=l[i]; if(segD(x,y,s.ax,s.ay,s.bx,s.by)<r) return true; } return false; }

/* ── the atlas of street names ── */
function atlasNew(){ var A={names:{}, list:[], w:1024, h:1024, cw:256, ch:40, canvas:null, n:0, dirty:true}; return A; }
function atlasRect(A, name){ var r=A.names[name]; if(r) return r; var cols=Math.floor(A.w/A.cw), rows=Math.floor(A.h/A.ch); if(A.n>=cols*rows) return null;
  var i=A.n++, cx=(i%cols)*A.cw, cy=Math.floor(i/cols)*A.ch; r=A.names[name]=[(cx+2)/A.w,(cy+2)/A.h,(cx+A.cw-2)/A.w,(cy+A.ch-2)/A.h]; A.list.push({name:name,x:cx,y:cy}); return r; }
function atlasPaint(A){ if(typeof document==='undefined') return; var c=document.createElement('canvas'); c.width=A.w; c.height=A.hf||A.h; var g=c.getContext('2d'); if(!g) return;
  g.fillStyle='#0e5c46'; g.fillRect(0,0,A.w,A.hf||A.h);
  A.list.forEach(function(e){ g.fillStyle='#0e5c46'; g.fillRect(e.x,e.y,A.cw,A.ch); g.strokeStyle='#f4f4ee'; g.lineWidth=2; g.strokeRect(e.x+3,e.y+3,A.cw-6,A.ch-6);
    var t=String(e.name).toUpperCase(), fs=22; g.font='700 '+fs+'px "Helvetica Neue",Helvetica,Arial,sans-serif'; while(g.measureText(t).width>A.cw-24 && fs>10){ fs-=1; g.font='700 '+fs+'px "Helvetica Neue",Helvetica,Arial,sans-serif'; }
    g.fillStyle='#f6f6f0'; g.textAlign='center'; g.textBaseline='middle'; g.fillText(t,e.x+A.cw/2,e.y+A.ch/2+1); });
  A.canvas=c; A.dirty=false; }

/* ── cells: one static mesh per cell (and one text mesh) so the renderer can cull ── */
var CAP_FULL=14500, CAP_LOW=5600;
SCN.budget={trees:6200, cars:4600, roofs:1500, vTree:340, vCar:140, vRoof:170};     /* vertices a cell may spend on each, and what one costs on average (to thin evenly) */
function cellOf(S, x, y){ var ci=Math.floor(x/SCN_CELL), cj=Math.floor(y/SCN_CELL), k=ci+','+cj, c=S.cells[k];
  if(!c){ c=S.cells[k]={m:sb(4096), t:sb(256), ci:ci, cj:cj, lod:S.lodOf(ci,cj), cap:0}; c.cap=c.lod?CAP_LOW:CAP_FULL; }
  return c; }
function room(c, n, lim){ return c.m.n/10+n<=(lim||c.cap); }

/* a candidate of category P (a plan record): note it, and say whether the budget still has room for it, thinning so what is left is spread evenly */
function bcand(P){ P.rem--; P.seen++; }
function bpass(P, h){ P.ok++; var okr=(P.ok+1)/(P.seen+2), exp=Math.max(0,P.rem)*okr+1, p=(P.B-P.used)/(exp*P.v); return p>=1 || h<p; }
function bspent(P, f){ var n=f/10; P.used+=n; P.n++; P.v=(P.v*3+n)/4; }     /* f: floats written (10 a vertex) */

/* ── tile edges: the curb of every block, in clockwise order so that the block is on the right of the way ── */
function cwRing(r){ if(MB.area(r)>0) return r; var o=[]; for(var i=r.length-2;i>=0;i-=2) o.push(r[i],r[i+1]); return o; }

/* buildings that lie outside the cells of this world but reach into them (a block's buildings may belong to the next cell): from the fill-in and the nodes' lots */
var _GI=null, _GIfg=null, _GEN=0;
function extraObstacles(O, set){
  var FG=E&&E.fillGroups?E.fillGroups():null; if(FG){ if(_GIfg!==FG){ _GIfg=FG; _GI={}; for(var lv=1;lv<=4;lv++){ var G=FG[lv]||{}; Object.keys(G).forEach(function(k){ var C=G[k]; Object.keys(C.u).forEach(function(u){ C.u[u].forEach(function(s){ var b=s.b; if(!b||!s.p) return;
              for(var a=Math.floor(b[0]/SCN_CELL);a<=Math.floor(b[2]/SCN_CELL);a++) for(var c=Math.floor(b[1]/SCN_CELL);c<=Math.floor(b[3]/SCN_CELL);c++){ var kk=a+','+c; (_GI[kk]||(_GI[kk]=[])).push(s); } }); }); }); } }
    _GEN++; var seen=_GEN, cells={}; Object.keys(set).forEach(function(k){ var p=k.split(','), ci=+p[0], cj=+p[1]; for(var i=-1;i<=1;i++) for(var j=-1;j<=1;j++) cells[(ci+i)+','+(cj+j)]=1; });
    Object.keys(cells).forEach(function(k){ if(set[k]) return; var l=_GI[k]; if(!l) return; l.forEach(function(s){ if(s._g===seen) return; s._g=seen; var b=s.b, cx=(b[0]+b[2])/2, cy=(b[1]+b[3])/2; if(inSet(set,cx,cy)) return; obAddRing(O,s.p,0); }); }); }
  var P=E&&E.P, Mp=E&&E.M, seenK={};
  if(P&&P.at) Object.keys(P.at).forEach(function(id){ var key=P.at[id]; if(seenK[key]) return; seenK[key]=1; var L=E.lot(key); if(!L) return; if(inSet(set,L[0],L[1])) return; var ci=Math.floor(L[0]/SCN_CELL), cj=Math.floor(L[1]/SCN_CELL), near=false; for(var i=-1;i<=1&&!near;i++) for(var j=-1;j<=1;j++) if(set[(ci+i)+','+(cj+j)]){ near=true; break; } if(near) obAddRing(O,turnedRing(L),0); });
  if(Mp&&Mp.landmarks) Mp.landmarks.forEach(function(l){ if(!l.box) return; var cx=(l.box[0]+l.box[2])/2, cy=(l.box[1]+l.box[3])/2; if(inSet(set,cx,cy)) return; var ci=Math.floor(cx/SCN_CELL), cj=Math.floor(cy/SCN_CELL), near=false; for(var i=-1;i<=1&&!near;i++) for(var j=-1;j<=1;j++) if(set[(ci+i)+','+(cj+j)]){ near=true; break; } if(near) obAddRing(O,boxRing(l.box[0],l.box[1],l.box[2],l.box[3]),0); }); }

function gatherSafe(W, set){ try{ return gatherMain(W, set); }catch(x){ _rec=null; _lamps=null; if(window.console) console.warn('scenery', x); if(!W.movers) W.movers=[]; return null; } }
function gatherMain(W, set){
  var t0=performance.now(), M=(typeof R!=='undefined'&&R)?R.M:null, S={cells:{}, W:W, set:set, track:null, heads:[], tscale:M?2.2:1}, SI=streetIndex(), A=atlasNew(); _rec=[]; _lamps=[];
  W.pal=PAL; W.atlas=null; var stat={trees:0,lamps:0,cars:0,signals:0,signs:0,roofs:0,furn:0,paint:0,park:0,rail:0,wire:0};
  /* the ride's own camera track: nothing stands on it */
  var TR={g:{},cs:16}, trN=0;
  function trAdd(x,y){ var k=Math.floor(x/16)+','+Math.floor(y/16); (TR.g[k]||(TR.g[k]=[])).push(x,y); trN++; }
  var trSamp=[];
  if(M && M.D){ var D=M.D, o={x:0,y:0}, sec;
    for(var s=0, cnt=0;s<=D.L;s+=1.6, cnt++){ pathAt(D,s,o); var h=headAt(D,s,6), sc=null; for(var q=0;q<M.secs.length;q++){ if(s>=M.secs[q].s0-.5 && s<=M.secs[q].s1+.5){ sc=M.secs[q]; break; } }
      var off=sc?(VEH[sc.veh]||VEH.walk).off:0, px=o.x-Math.sin(h)*off, py=o.y+Math.cos(h)*off; trAdd(px,py); trAdd(o.x,o.y); if(sc&&sc.veh==='bus'){ trAdd(o.x-Math.sin(h)*(off+8),o.y+Math.cos(h)*(off+8)); }
      if(cnt%22===0){ var under=false; if(sc&&sc.ug) for(var u=0;u<sc.ug.length;u++){ if(s>=sc.ug[u][0]-10 && s<=sc.ug[u][1]+10){ under=true; break; } } if(!under) trSamp.push(px,py); } } }
  S.TR=TR;
  function trackNear(x,y,m){ if(!trN) return false; var i0=Math.floor((x-m)/16), i1=Math.floor((x+m)/16), j0=Math.floor((y-m)/16), j1=Math.floor((y+m)/16), m2=m*m;
    for(var a=i0;a<=i1;a++) for(var b=j0;b<=j1;b++){ var l=TR.g[a+','+b]; if(!l) continue; for(var i=0;i<l.length;i+=2){ var dx=l[i]-x, dy=l[i+1]-y; if(dx*dx+dy*dy<m2) return true; } } return false; }
  S.trackNear=trackNear;
  S.lodOf=function(ci,cj){ if(!trSamp.length) return M?1:0; var cx=(ci+.5)*SCN_CELL, cy=(cj+.5)*SCN_CELL, best=1e18; for(var i=0;i<trSamp.length;i+=2){ var dx=trSamp[i]-cx, dy=trSamp[i+1]-cy, d=dx*dx+dy*dy; if(d<best) best=d; } return best<460*460?0:1; };
  /* obstacles */
  var O=obNew(); S.O=O;
  W.solids.forEach(function(s){ if(s.kind==='pole'||s.kind==='sign'||s.kind==='canopy') return; obAddRing(O,s.ring,0,s.h); });
  extraObstacles(O,set);
  W.water.forEach(function(w){ obAddSeg(O,w.x0,w.y0,w.x1,w.y1,w.w/2); });
  var PO=obNew(); W.parks.forEach(function(p){ obAddRing(PO,p.ring,0); });
  S.inPark=function(x,y){ return obHit(PO,x,y,0,0); };
  S.onWater=function(x,y,m){ return obHit(O,x,y,m,1); };
  S.blocked=function(x,y,m){ return obHit(O,x,y,m,0); };
  var Sd=SCN.stats; Sd.cells=0;
  var tilesGathered=W.tiles.length;
  /* the plan: how many trees, parked cars and roofs each cell could take, against what it may spend, so they are thinned EVENLY (not first come first served) */
  var PLAN={}, BUD=SCN.budget;
  function rec(k){ var p=PLAN[k]; if(!p) p=PLAN[k]={t:{rem:0,seen:0,ok:0,used:0,n:0,B:BUD.trees,v:BUD.vTree},c:{rem:0,seen:0,ok:0,used:0,n:0,B:BUD.cars,v:BUD.vCar},r:{rem:0,seen:0,ok:0,used:0,n:0,B:BUD.roofs,v:BUD.vRoof}}; return p; }
  W.tiles.forEach(function(T){ var rg=cwRing(T.ring), nn=rg.length/2; for(var e=0;e<nn;e++){ var ax=rg[2*e], ay=rg[2*e+1], bx=rg[2*((e+1)%nn)], by=rg[2*((e+1)%nn)+1], l=Math.hypot(bx-ax,by-ay); if(l<30) continue; var p=rec(Math.floor((ax+bx)/2/SCN_CELL)+','+Math.floor((ay+by)/2/SCN_CELL)); p.t.rem+=Math.max(0,(l-33)/18+1); p.c.rem+=Math.max(0,(l-38)/9.5); } });
  W.solids.forEach(function(s){ if((s.kind==='fill'||s.kind==='node') && s.h>=14) rec(Math.floor(s.cx/SCN_CELL)+','+Math.floor(s.cy/SCN_CELL)).r.rem++; });
  S.bud=function(x,y){ return rec(Math.floor(x/SCN_CELL)+','+Math.floor(y/SCN_CELL)); };
  /* ── parks ── */
  if(SCN.trees) W.parks.forEach(function(pk){ parkItems(S, W, SI, pk, set, stat, trackNear); });
  /* ── the blocks ── */
  var jdone={}, cwdone={};
  var SW=STREET_HW, nm_;
  W.tiles.forEach(function(T,ti){ var ring=cwRing(T.ring), n=ring.length/2, i, j;
    var cen=cellOf(S,T.cx,T.cy);
    for(i=0;i<n;i++){ var P=ring.slice(2*((i+n-1)%n),2*((i+n-1)%n)+2), V=[ring[2*i],ring[2*i+1]], Nx=[ring[2*((i+1)%n)],ring[2*((i+1)%n)+1]];
      var ax=V[0]-P[0], ay=V[1]-P[1], la=Math.hypot(ax,ay), bx=Nx[0]-V[0], by=Nx[1]-V[1], lb=Math.hypot(bx,by); if(la<2||lb<2) continue;
      var aux=ax/la, auy=ay/la, bux=bx/lb, buy=by/lb;
      /* ── the edge from V to Nx: street furniture ── */
      if(lb>=30){ edgeItems(S, SI, W, ring, V[0],V[1], bux,buy, lb, stat, ti, i, M, trackNear); }
      /* ── a corner of the block (a right turn of the clockwise ring between two long edges) ── */
      if(la>=30 && lb>=30 && Math.abs(aux*bux+auy*buy)<.3 && aux*buy-auy*bux>0){ cornerItems(S, SI, W, V[0],V[1], aux,auy, bux,buy, jdone, cwdone, A, stat, trackNear); } } });
  /* ── rooftops ── */
  if(SCN.roofs) W.solids.forEach(function(s){ roofItems(S, s, stat); });
  /* ── river railings, tram wires ── */
  riverRails(S, W, SI, stat);
  if(M && SCN.wires) tramWires(S, W, M, stat);
  /* ── done: one mesh per cell, text apart ── */
  /* the atlas only as tall as its rows need (a power of two): the text's v coordinates were laid out for the full height, so they are rescaled */
  if(A.n){ var rowsN=Math.ceil(A.n/Math.floor(A.w/A.cw)), hf=64; while(hf<rowsN*A.ch) hf*=2; if(hf>A.h) hf=A.h; A.hf=hf;
    if(hf!==A.h) Object.keys(S.cells).forEach(function(k){ var t=S.cells[k].t, a=t.a; for(var q=0;q+9<t.n;q+=10) a[q+7]*=A.h/hf; }); }
  atlasPaint(A); if(A.n){ A.h=A.hf||A.h; W.atlas=A; }
  var keys=Object.keys(S.cells), tv=0;
  keys.forEach(function(k){ var c=S.cells[k]; var cx=(c.ci+.5)*SCN_CELL, cy=(c.cj+.5)*SCN_CELL, r=SCN_CELL*.75;
    if(c.m.n) { W.meshes.push({a:sfin(c.m), id:'scn:'+k, cx:cx, cy:cy, r:r}); tv+=c.m.n/10; }
    if(c.t.n && W.atlas) W.meshes.push({a:sfin(c.t), id:'scn-txt:'+k, cx:cx, cy:cy, r:r, tex:'atlas'}); });
  Sd.verts=tv; Sd.cellsN=keys.length; Sd.ms=performance.now()-t0; Sd.stat=stat;
  S.plan=PLAN; S.stat=stat; W._scn=S; W.scenery={t:new Float32Array(_rec)}; W.lamps=new Float32Array(_lamps); _rec=null; _lamps=null;
  moversGather(S, W, M, stat, SI);
  Sd.msAll=performance.now()-t0; S.cells=null; S.O=null; S.TR=null; S.trackNear=null; S.blocked=null; S.onWater=null; S.inPark=null; S.lodOf=null;
  return S; }

/* ── species of a street, season and size of a tree ── */
function vc(stat,k,n){ var o=stat.vc||(stat.vc={}); o[k]=(o[k]||0)+n/10; }
function pickSpecies(sid, rank, h){ var q=sid>=0?hn(sid,3):h; if(rank<=1){ return q<.5?0:q<.8?1:q<.9?2:q<.95?4:3; } return q<.3?0:q<.5?1:q<.62?2:q<.8?4:q<.9?5:3; }
function pickSeason(g, sp){ if(sp===3) return 0; if(sp===4 && g<.5) return 4; return g<.74?0:g<.85?1:g<.97?2:g<.975?3:0; }

/* ── the furniture along one edge of a block (a curb, clockwise: the block is on the right, the street on the left) ── */
function edgeItems(S, SI, W, ring, vx, vy, ux, uy, L, stat, ti, ei, M, trackNear){
  var ix=-uy, iy=ux, ox=uy, oy=-ux, mx=vx+ux*L/2, my=vy+uy*L/2;
  var st=streetAt(SI, mx+ox*11, my+oy*11, ux, uy, 16, .9), rank=st?st.k:3, sid=st?st.id:-1, eh=hk(mx,my,7), cc=15, busy=[], i, s;
  function free(s,w){ for(var q=0;q<busy.length;q+=2) if(s+w>busy[q] && s-w<busy[q+1]) return false; return true; }
  function use(s,w){ busy.push(s-w,s+w); }
  function px(s,off){ return vx+ux*s+ix*off; } function py(s,off){ return vy+uy*s+iy*off; }
  var c0=cellOf(S,mx,my), low=!!c0.lod, bp=S.bud(mx,my);
  /* trees (also in the cells away from the ride: sparser) */
  if(SCN.trees){
    var sp=pickSpecies(sid,rank,hk(mx,my,3)), gap=low?36:17.5, eseason=pickSeason(hn((sid>=0?sid:7)*31+Math.floor((mx+my)/700),5),sp);
    for(s=cc+hk(mx,my,4)*6; s<L-cc; s+=gap*(.66+.7*hash(Math.round(s*3)+ei*131))){
      if(!low) bcand(bp.t); var x=px(s,2.4), y=py(s,2.4), g=hash(Math.round(x*3)*7+Math.round(y*3)); if(g<.1) continue; var cell=cellOf(S,x,y); if(!room(cell,200)) continue;
      if(S.blocked(x,y,1.7)||trackNear(x,y,1.15)) continue; if(!low && !bpass(bp.t,hk(x,y,91))) continue;
      var sp2=g>.93?(sp+1)%6:sp, sz=.76+.26*hash(Math.round(x*5)+Math.round(y*11)), season=(sp2===sp && hash(Math.round(x*9)+Math.round(y*13)+3)>.14)?eseason:pickSeason(hash(Math.round(x*9)+Math.round(y*13)+3), sp2); if(sp2===4&&season===0&&eseason===4) season=4;
      var n0=cell.m.n; treeAt(cell.m,x,y,sp2,sz,hash(Math.round(x)+Math.round(y)*31),season,low,false); use(s,3.2); stat.trees++; vc(stat,'trees',cell.m.n-n0); if(!low) bspent(bp.t,cell.m.n-n0); } }
  if(low) return;
  /* hydrants */
  if(hk(mx,my,8)<.62){ s=cc+6+hk(mx,my,9)*(L-2*cc-12), x=px(s,.95), y=py(s,.95); var cl=cellOf(S,x,y);
    if(free(s,3) && room(cl,120) && !S.blocked(x,y,1) && !trackNear(x,y,1.3)){ hydrantAt(cl.m,x,y,ox,oy,hk(mx,my,10)); use(s,3.5); stat.furn++; busy.hy=s; } }
  /* a mailbox near a corner */
  if(hk(mx,my,11)<.3){ s=hk(mx,my,12)<.5?cc+3:L-cc-3; x=px(s,1.0); y=py(s,1.0); cl=cellOf(S,x,y);
    if(free(s,2.5) && room(cl,100) && !S.blocked(x,y,.9) && !trackNear(x,y,1.3)){ mailboxAt(cl.m,x,y,ox,oy); use(s,2.5); stat.furn++; } }
  /* a litter bin near a corner, a manhole cover in the lane */
  if(hk(mx,my,17)<.55){ s=hk(mx,my,18)<.5?cc+9:L-cc-9; x=px(s,1.1); y=py(s,1.1); cl=cellOf(S,x,y);
    if(free(s,2) && room(cl,80) && !S.blocked(x,y,.8) && !trackNear(x,y,1.2)){ trashAt(cl.m,x,y); use(s,2); stat.furn++; } }
  if(hk(mx,my,19)<.7){ s=L*(.2+.6*hk(mx,my,24)); x=px(s,-5.8); y=py(s,-5.8); cl=cellOf(S,x,y); if(room(cl,40) && !S.inPark(x,y)){ manholeAt(cl.m,x,y); stat.paint++; } }
  /* a bus shelter on the main streets, a bench elsewhere */
  if(rank<=1 && hk(mx,my,13)<.3){ s=L*(.3+.4*hk(mx,my,14)); x=px(s,2.2); y=py(s,2.2); cl=cellOf(S,x,y);
    if(free(s,7) && room(cl,300) && !S.blocked(x,y,2.2) && !S.blocked(px(s-4,1.6),py(s-4,1.6),.8) && !S.blocked(px(s+4,1.6),py(s+4,1.6),.8) && !trackNear(x,y,2.6)){ shelterAt(cl.m,x,y,ox,oy); use(s,7); stat.furn++; } }
  else if(eh<.14){ s=L*(.25+.5*hk(mx,my,15)); x=px(s,1.9); y=py(s,1.9); cl=cellOf(S,x,y);
    if(free(s,3) && room(cl,160) && !S.blocked(x,y,1.5) && !trackNear(x,y,1.6)){ benchAt(cl.m,x,y,ox,oy); use(s,3); stat.furn++; } }
  /* street lamps: both sides, about every 45 units */
  for(s=cc+5+hk(mx,my,16)*10; s<L-cc; s+=44*(.9+.2*hash(Math.round(s)+ei*17))){ x=px(s,.75); y=py(s,.75); cl=cellOf(S,x,y);
    if(!free(s,2.4) || !room(cl,90) || S.blocked(x,y,.8) || trackNear(x,y,1.2)) continue; var n1=cl.m.n; lampAt(cl.m,x,y,ox,oy); use(s,2.4); stat.lamps++; vc(stat,'lamps',cl.m.n-n1); }
  /* parked cars in the parking lane */
  if(SCN.cars){ var fill=rank<=1?.5:.38, pk=[];
    for(s=cc+1.5; s<L-cc-6; ){ var ti2=(hash(Math.round(s*7)+ei*37+Math.round(mx))*6)|0, T=CAR_T[ti2], len=T.L*UM, h1=hash(Math.round(s*11)+ei*53+Math.round(my));
      if(h1<fill && free(s+len/2,len/2+.3)){ bcand(bp.c); var cx2=px(s+len/2,-1.8), cy2=py(s+len/2,-1.8), cl2=cellOf(S,cx2,cy2);
        if(room(cl2,200) && !S.inPark(cx2,cy2) && !trackNear(cx2,cy2,2.5) && !trackNear(cx2+ux*len*.35,cy2+uy*len*.35,2.1) && !trackNear(cx2-ux*len*.35,cy2-uy*len*.35,2.1) && bpass(bp.c,hk(cx2,cy2,92))){
          var ci=(hash(Math.round(cx2*3)+Math.round(cy2*5))*PC.car.length)|0, taxi=(rank<=1 && hash(Math.round(cx2)+Math.round(cy2*7))<.07);
          var n2=cl2.m.n; carParked(cl2.m,cx2,cy2,ux,uy,ti2,ci,taxi); stat.cars++; vc(stat,'cars',cl2.m.n-n2); bspent(bp.c,cl2.m.n-n2); } }
      s+=len+.9+hash(Math.round(s*5)+ei)*2.4+(h1<fill?0:5); } } }

/* ── a corner: crosswalks, the stop line and an arrow on the approach, a signal pole and a street-name pole ── */
function cornerItems(S, SI, W, vx, vy, aux, auy, bux, buy, jdone, cwdone, A, stat, trackNear){
  var oax=auy, oay=-aux, obx=buy, oby=-bux, kx=vx+STREET_HW*(aux-bux), ky=vy+STREET_HW*(auy-buy);
  var c=cellOf(S,vx+oax*8,vy+oay*8); if(c.lod) return; var m=c.m, z=SZ_RD;
  function gP(ux_,uy_,ox_,oy_,al,ac){ _gp[0]=vx+ux_*al+ox_*ac; _gp[1]=vy+uy_*al+oy_*ac; return _gp; }
  var _gp=[0,0];
  /* a crosswalk across the road whose curb is edge (du, od): along from al0..al1 (positive along du), across 0..22 */
  function cross(du0,du1,odx,ody,al0,al1){
    var mxk=vx+du0*(al0+al1)/2+odx*11, myk=vy+du1*(al0+al1)/2+ody*11, key=Math.round(mxk)+','+Math.round(myk); if(cwdone[key]) return; cwdone[key]=1;
    for(var t=.9;t<21.4;t+=1.45){ var ax_=vx+du0*al0+odx*(t-.33), ay_=vy+du1*al0+ody*(t-.33), bx_=vx+du0*al1+odx*(t-.33), by_=vy+du1*al1+ody*(t-.33), cx_=vx+du0*al1+odx*(t+.33), cy_=vy+du1*al1+ody*(t+.33), dx_=vx+du0*al0+odx*(t+.33), dy_=vy+du1*al0+ody*(t+.33);
      if(S.onWater(ax_,ay_,0)) continue; gq(m,z,ax_,ay_,bx_,by_,cx_,cy_,dx_,dy_,MAT.white,.5); stat.paint++; } }
  if(room(c,260)) cross(aux,auy,oax,oay,-5.6,-1.7);
  if(room(c,260)) cross(bux,buy,obx,oby,1.7,5.6);
  /* stop line on the approach lane (curb + 3.3 .. 8.3 out), and an arrow further back */
  if(room(c,60)){ var sl=-7.6, sw=.7; gq(m,z,vx+aux*sl+oax*3.3,vy+auy*sl+oay*3.3,vx+aux*(sl+sw)+oax*3.3,vy+auy*(sl+sw)+oay*3.3,vx+aux*(sl+sw)+oax*8.3,vy+auy*(sl+sw)+oay*8.3,vx+aux*sl+oax*8.3,vy+auy*sl+oay*8.3,MAT.white,.5); stat.paint++; }
  if(hk(vx,vy,20)<.7 && room(c,60)){ var al=-27, ac=5.8, h0=-24.4, tip=-21.8;
    gq(m,z,vx+aux*al+oax*(ac-.16),vy+auy*al+oay*(ac-.16),vx+aux*h0+oax*(ac-.16),vy+auy*h0+oay*(ac-.16),vx+aux*h0+oax*(ac+.16),vy+auy*h0+oay*(ac+.16),vx+aux*al+oax*(ac+.16),vy+auy*al+oay*(ac+.16),MAT.white,.5);
    tr(m,vx+aux*h0+oax*(ac-.75),vy+auy*h0+oay*(ac-.75),z,vx+aux*tip+oax*ac,vy+auy*tip+oay*ac,z,vx+aux*h0+oax*(ac+.75),vy+auy*h0+oay*(ac+.75),z,MAT.white,.5,vx,vy,z-1); stat.paint+=2; }
  /* a signal pole at the corner, its head facing the traffic that arrives along edge a (the lit lamp is a mover, see sigTpl) */
  var dgx=(aux-bux), dgy=(auy-buy), dl=Math.hypot(dgx,dgy)||1; dgx/=dl; dgy/=dl;
  if(hk(vx,vy,21)<.78 && room(c,300)){ var px=vx-dgx*1.0, py=vy-dgy*1.0;
    if(!S.blocked(px,py,.8) && !trackNear(px,py,1.2)){ var hc=signalAt(m,px,py,oax,oay,-aux,-auy,-1); stat.signals++;
      S.heads.push({x:hc[0],y:hc[1],yaw:Math.atan2(-auy,-aux),axisH:Math.abs(aux)>Math.abs(auy),jx:kx,jy:ky}); } }
  if(hk(vx,vy,24)<.55 && room(c,140)){ var stx=vx-aux*8.4-oax*1.7, sty=vy-auy*8.4-oay*1.7;
    if(!S.blocked(stx,sty,.6) && !trackNear(stx,sty,1.2) && !S.onWater(stx,sty,.5)){ stopSignAt(m,stx,sty,-aux,-auy); stat.signs++; } }
  /* a pole with the two street names, a few units back from the corner on the block side */
  if(SCN.signs && hk(vx,vy,23)<.55 && room(c,200)){ var spx=vx-aux*3.4-oax*1.1, spy=vy-auy*3.4-oay*1.1;
    var nA=streetAt(SI,kx,ky,aux,auy,14,.9), nB=streetAt(SI,kx,ky,bux,buy,14,.9);
    if(nA||nB){ var rA=nA?atlasRect(A,SI.names[nA.id]):null, rB=nB?atlasRect(A,SI.names[nB.id]):null;
      if((rA||rB) && !S.blocked(spx,spy,.8) && !trackNear(spx,spy,1.2)){ signPoleAt(m,c.t,spx,spy,aux,auy,rA,rB); stat.signs++; } } } }

/* ── a park: trees in clumps round a lawn, paths with lamps and benches ── */
function vnoise(x,y){ var xi=Math.floor(x), yi=Math.floor(y), xf=x-xi, yf=y-yi, u=xf*xf*(3-2*xf), v=yf*yf*(3-2*yf);
  var a=hash(xi*73+yi*1291), b=hash((xi+1)*73+yi*1291), c=hash(xi*73+(yi+1)*1291), d=hash((xi+1)*73+(yi+1)*1291); return a+(b-a)*u+(c-a)*v+(a-b-c+d)*u*v; }
function parkItems(S, W, SI, pk, set, stat, trackNear){
  var ring=pk.ring, n=ring.length/2, i, x0=1e18,y0=1e18,x1=-1e18,y1=-1e18, k, PK=9500;
  for(i=0;i<n;i++){ var x=ring[2*i], y=ring[2*i+1]; if(x<x0)x0=x; if(x>x1)x1=x; if(y<y0)y0=y; if(y>y1)y1=y; }
  if(n<3) return; var cs=SCN_CELL, paths=[], cxp=pk.cx, cyp=pk.cy, area=Math.abs(MB.area(ring)), side=Math.sqrt(area), ph=hk(cxp,cyp,31);
  function inside(px,py){ return inRingP(px,py,ring); }
  function addPath(q){ for(var b=0;b<q.length;b+=2) if(!inside(q[b],q[b+1])) return false; paths.push(q); return true; }
  function curve(ex,ey,tx,ty,bendk){ var dx=tx-ex, dy=ty-ey, dl=Math.hypot(dx,dy)||1, bend=bendk*dl, mx=(ex+tx)/2-dy/dl*bend, my=(ey+ty)/2+dx/dl*bend, pts=[ex,ey,mx,my,tx,ty], q=[pts[0],pts[1]];
    for(var a=0;a+3<pts.length;a+=2) q.push(pts[a]*.75+pts[a+2]*.25,pts[a+1]*.75+pts[a+3]*.25,pts[a]*.25+pts[a+2]*.75,pts[a+1]*.25+pts[a+3]*.75); q.push(pts[4],pts[5]); return q; }
  if(side>45){
    /* entries spread along the boundary; paths cross the park between opposite entries, bending a little, and a loop inside the edge */
    var np=side>150?4:side>90?3:2, ent=[], per=0, cum=[0]; for(i=0;i<n;i++){ per+=Math.hypot(ring[2*((i+1)%n)]-ring[2*i],ring[2*((i+1)%n)+1]-ring[2*i+1]); cum.push(per); }
    for(k=0;k<np;k++){ var tpos=((k+ph)/np%1)*per, e=0; while(e<n-1 && cum[e+1]<tpos) e++; var tt=(tpos-cum[e])/((cum[e+1]-cum[e])||1), ax=ring[2*e], ay=ring[2*e+1], bx=ring[2*((e+1)%n)], by=ring[2*((e+1)%n)+1], ex=ax+(bx-ax)*tt, ey=ay+(by-ay)*tt, ll=Math.hypot(bx-ax,by-ay)||1;
      /* a step inward from the edge */ var sgn=inside(ex+(-(by-ay)/ll)*3,ey+((bx-ax)/ll)*3)?1:-1; ent.push([ex+sgn*(-(by-ay)/ll)*2.5, ey+sgn*((bx-ax)/ll)*2.5]); }
    for(k=0;k<np;k++){ var o=ent[(k+(np>2?2:1))%np], e0=ent[k]; if(np>2 && k>=2) continue; addPath(curve(e0[0],e0[1],o[0],o[1],(hk(cxp,cyp,38+k)-.5)*.3)); }
    if(side>110){ var inset=offsetRing(cwRing(ring),12), q2=[]; for(i=0;i<inset.length;i+=2) q2.push(inset[i],inset[i+1]); q2.push(inset[0],inset[1]); if(inset.length>=8) addPath(q2); } }
  function onPath(x,y,r){ for(var p=0;p<paths.length;p++){ var q=paths[p]; for(var a=0;a+3<q.length;a+=2) if(segD(x,y,q[a],q[a+1],q[a+2],q[a+3])<r) return true; } return false; }
  /* paths as ribbons; lamps and benches along them */
  paths.forEach(function(q,pi){ var mid=(q.length/2)>>1;
    var run=[], rcell=null; function flush(){ if(run.length>=4 && rcell) ribbon(rcell.m,run,.3,3.8,MAT.paving,.5); run=[]; }
    for(var a=0;a+3<q.length;a+=2){ var mxs=(q[a]+q[a+2])/2, mys=(q[a+1]+q[a+3])/2; if(!inSet(set,mxs,mys)){ flush(); continue; } var cl=cellOf(S,mxs,mys); if(cl.lod || !room(cl,70,cl.cap) || S.blocked(mxs,mys,2.5)||S.onWater(mxs,mys,2.5)){ flush(); continue; }
      if(rcell!==cl){ flush(); rcell=cl; } if(!run.length) run.push(q[a],q[a+1]); run.push(q[a+2],q[a+3]); } flush();
    var nl=hk(cxp,cyp,40+pi), carry=nl*40; for(var b=0;b+3<q.length;b+=2){ var sx=q[b], sy=q[b+1], ex2=q[b+2], ey2=q[b+3], sl=Math.hypot(ex2-sx,ey2-sy), uxp=(ex2-sx)/(sl||1), uyp=(ey2-sy)/(sl||1);
      for(var t=carry; t<sl; t+=38){ var lx=sx+uxp*t-uyp*3, ly=sy+uyp*t+uxp*3, cl2=cellOf(S,lx,ly); if(cl2.lod||!room(cl2,110)||!inSet(set,lx,ly)||S.blocked(lx,ly,1.5)||trackNear(lx,ly,1.2)||!inside(lx,ly)) continue;
        lampPark(cl2.m,lx,ly); stat.lamps++; if(hash(Math.round(lx*3)+Math.round(ly))<.55){ var bx2=sx+uxp*(t+13)+uyp*3, by2=sy+uyp*(t+13)-uxp*3, cl3=cellOf(S,bx2,by2); if(!cl3.lod && room(cl3,170) && inSet(set,bx2,by2) && inside(bx2,by2) && !S.blocked(bx2,by2,1.6) && !trackNear(bx2,by2,1.6)){ benchAt(cl3.m,bx2,by2,-uyp,uxp); stat.furn++; } } }
      carry=Math.max(0,carry+38*Math.ceil((sl-carry)/38)-sl); } });
  /* trees: thick near the edge and in clumps, a lawn left open in the middle */
  var sp=14, count=0, keys=Object.keys(set), rr=Math.max(10,side*.5);
  for(var kk=0;kk<keys.length;kk++){ var cellN=0; var kc=keys[kk].split(','), ci=+kc[0], cj=+kc[1], bx0=Math.max(ci*cs,x0), by0=Math.max(cj*cs,y0), bx1=Math.min((ci+1)*cs,x1), by1=Math.min((cj+1)*cs,y1); if(bx1<=bx0||by1<=by0) continue;
    var cl4=cellOf(S,(bx0+bx1)/2,(by0+by1)/2), spc=cl4.lod?sp*1.9:sp, g0=Math.floor(bx0/spc), g1=Math.ceil(bx1/spc), h0=Math.floor(by0/spc), h1=Math.ceil(by1/spc);
    for(var gi=g0;gi<=g1;gi++) for(var gj=h0;gj<=h1;gj++){ if(cellN>380) break; var x=(gi+.15+.7*hash(gi*37+gj*911+5))*spc, y=(gj+.15+.7*hash(gi*53+gj*313+7))*spc;
      if(x<bx0||x>=bx1||y<by0||y>=by1) continue; if(!inside(x,y)) continue;
      var de=ringD(x,y,ring), edge=Math.max(0,1-de/26), cl=vnoise(x/85+3,y/85)*.62+vnoise(x/30+9,y/30)*.38, dens=.05+.95*Math.min(1,Math.max(0,(cl-.38)/.34))+.32*edge; if(hash(gi*17+gj*131+11)>dens) continue;
      var cl5=cellOf(S,x,y); if(!room(cl5,230,cl5.cap)) continue;
      if(S.blocked(x,y,2.6)||S.onWater(x,y,2.2)||trackNear(x,y,1.3)||onPath(x,y,3.6)) continue;
      var nz=vnoise(x/140+11,y/140+5), g=hash(gi*7+gj*19+3), spp=nz>.72?3:g<.45?2:g<.78?0:g<.92?1:4, sz=.8+.5*hash(gi*5+gj*23+2), season=pickSeason(hash(gi*3+gj*29+8),spp);
      treeAt(cl5.m,x,y,spp,sz,hash(gi*11+gj*13),season,!!cl5.lod,true); count++; cellN++; stat.park++; } } }

/* ── rooftops ── */
function roofItems(S, s, stat){
  if(s.kind!=='fill' && s.kind!=='node') return; var h=s.h; if(h<14 || s.n<3) return; var cell=cellOf(S,s.cx,s.cy); if(cell.lod || !room(cell,320)) return; var rp=S.bud(s.cx,s.cy).r; bcand(rp); if(!bpass(rp,hk(s.cx,s.cy,93))) return;
  var m=cell.m, r=s.ring, n=s.n, area=Math.abs(MB.area(r)), g=hk(s.cx,s.cy,21), nr0=m.n; if(area<80) return; var done=function(){ vc(stat,'roofs',m.n-nr0); bspent(rp,m.n-nr0); };
  var x0=1e18,y0=1e18,x1=-1e18,y1=-1e18,i; for(i=0;i<n;i++){ var x=r[2*i], y=r[2*i+1]; if(x<x0)x0=x; if(x>x1)x1=x; if(y<y0)y0=y; if(y>y1)y1=y; }
  function spot(seed, mg){ for(var a=0;a<7;a++){ var px=x0+(x1-x0)*hk(s.cx,s.cy,seed+a*3), py=y0+(y1-y0)*hk(s.cx,s.cy,seed+a*3+1); if(inRingP(px,py,r) && ringD(px,py,r)>mg) return [px,py]; } return null; }
  var nh=Math.min(4,1+Math.floor(area/700)), k, q;
  for(k=0;k<nh;k++){ if(hk(s.cx,s.cy,60+k)>.8) continue; q=spot(100+k*11,2.6); if(!q) continue; frame(q[0],q[1],h,hk(q[0],q[1],5)*6.28,UM);
    fbox(m,-1.1,-.7,0,1.1,.7,.95,MAT.metal,PC.hvac,MAT.metal,PC.hvacD); fcyl(m,.4,0,.95,1.0,.42,.42,6,MAT.dark,0,true); stat.roofs++; }
  if(h>=20 && g<.3){ q=spot(200,4); if(q){ frame(q[0],q[1],h,hk(q[0],q[1],6)*6.28,UM); fbox(m,-1.5,-1.2,0,1.5,1.2,2.5,MAT.white,0,MAT.roof,0); fbox(m,1.5,-.45,0,1.55,.45,2.0,MAT.dark,0); stat.roofs++; } }
  if(h>=22 && hk(s.cx,s.cy,22)<.14){ q=spot(300,4.2); if(q){ frame(q[0],q[1],h,0,UM); var tz=1.3; [[-1.3,-1.3],[1.3,-1.3],[1.3,1.3],[-1.3,1.3]].forEach(function(p){ fbox(m,p[0]-.07,p[1]-.07,0,p[0]+.07,p[1]+.07,tz,MAT.metal,PC.rail); });
      fcyl(m,0,0,tz,tz+2.6,1.7,1.7,8,MAT.wood,PC.tank,false); fcyl(m,0,0,tz+2.6,tz+3.6,1.7,.15,8,MAT.wood,PC.tank,false); stat.roofs++; } }
  if(h>=45 && hk(s.cx,s.cy,23)<.4){ q=spot(400,2.5); if(q){ frame(q[0],q[1],h,0,UM); var ah=3.5+hk(s.cx,s.cy,24)*5; fcyl(m,0,0,0,ah,.05,.03,4,MAT.metal,PC.rail,false); fbox(m,-.7,-.015,ah*.7,.7,.015,ah*.7+.04,MAT.metal,PC.rail); fbox(m,-.45,-.015,ah*.85,.45,.015,ah*.85+.04,MAT.metal,PC.rail);
      if(h>=120){ fbox(m,-.1,-.1,ah,.1,.1,ah+.2,MAT.lamp,PC.lampR); } stat.roofs++; } }
  /* a parapet: a thin rim along the edge of the roof, on the simple outlines */
  if(SCN.parapets && s.kind==='fill' && n<=12 && hk(s.cx,s.cy,25)<.75 && room(cell,200)){
    var rg=cwRing(r), cx=s.cx, cy=s.cy, rin=shrinkRing(rg,cx,cy,.55), ph=1.0, nn=rg.length/2;
    for(i=0;i<nn;i++){ var j=(i+1)%nn, ax=rg[2*i], ay=rg[2*i+1], bx=rg[2*j], by=rg[2*j+1], cx2=rin[2*j], cy2=rin[2*j+1], dx2=rin[2*i], dy2=rin[2*i+1];
      qd(m,ax,ay,h,bx,by,h,bx,by,h+ph,ax,ay,h+ph,MAT.roof,.5,(ax+bx)/2+(cx-(ax+bx)/2)*.5,(ay+by)/2+(cy-(ay+by)/2)*.5,h+ph/2);
      qd(m,dx2,dy2,h,cx2,cy2,h,cx2,cy2,h+ph,dx2,dy2,h+ph,MAT.roof,.5,(ax+bx)/2+((ax+bx)/2-cx)*.5,(ay+by)/2+((ay+by)/2-cy)*.5,h+ph/2);
      qd(m,ax,ay,h+ph,bx,by,h+ph,cx2,cy2,h+ph,dx2,dy2,h+ph,MAT.roof,.5,(ax+bx)/2,(ay+by)/2,h); } stat.roofs++; } done(); }

/* ── railings along the river banks ── */
function riverRails(S, W, SI, stat){
  W.water.forEach(function(w){ var dx=w.x1-w.x0, dy=w.y1-w.y0, L=Math.hypot(dx,dy); if(L<20) return; var ux=dx/L, uy=dy/L, nx=-uy, ny=ux, hw=w.w/2+.8;
    [1,-1].forEach(function(sd){ var pen=null;
      for(var s=3;s<L-1;s+=8){ var x=w.x0+ux*s+nx*hw*sd, y=w.y0+uy*s+ny*hw*sd, x2=x+ux*8, y2=y+uy*8, cl=cellOf(S,x,y); var ok=!cl.lod && room(cl,120) && !S.onWater(x,y,.6) && !S.onWater(x2,y2,.6) && !S.blocked(x,y,2) && !S.blocked(x2,y2,2) && !nearStreet(SI,x,y,16) && !nearStreet(SI,x2,y2,16) && !S.trackNear(x,y,1.2);
        if(!ok) continue; frameV(x,y,SZ_SW,ux,uy,UM); var rl=8/UM;
        fbox(cl.m,-.04,-.04,0,.04,.04,1.12,MAT.metal,PC.rail); fbox(cl.m,0,-.03,1.04,rl,.03,1.1,MAT.metal,PC.rail); fbox(cl.m,0,-.02,.55,rl,.02,.6,MAT.metal,PC.rail); stat.rail++; } }); }); }

/* ── trolley wires: a contact wire over the track and a sagging messenger, with arms from the poles ── */
function tramWires(S, W, M, stat){
  var D=M.D, o={x:0,y:0}, ZC=7.0, ZM=8.3;
  function zm(s){ var ph=(s%80)/80; return ZM-1.0*4*ph*(1-ph); }
  M.secs.forEach(function(sec){ if(sec.veh!=='tram') return;
    function under(s){ for(var i=0;i<sec.ug.length;i++) if(s>=sec.ug[i][0]-3 && s<=sec.ug[i][1]+3) return true; return false; }
    var prev=null;
    for(var s=sec.s0; s<=sec.s1; s+=7){ if(under(s)){ prev=null; continue; } pathAt(D,s,o); var x=o.x, y=o.y, cl=cellOf(S,x,y);
      if(prev && !cl.lod && room(cl,120)){ var dx=x-prev.x, dy=y-prev.y, l=Math.hypot(dx,dy)||1, nx=-dy/l*.025, ny=dx/l*.025;
        for(var k=0;k<2;k++){ var za=k?zm(prev.s):ZC, zb=k?zm(s):ZC;
          qd(cl.m,prev.x+nx,prev.y+ny,za,x+nx,y+ny,zb,x-nx,y-ny,zb,prev.x-nx,prev.y-ny,za,MAT.metal,.5,prev.x,prev.y,za+5);
          qd(cl.m,prev.x-nx,prev.y-ny,za,x-nx,y-ny,zb,x+nx,y+ny,zb,prev.x+nx,prev.y+ny,za,MAT.metal,.5,prev.x,prev.y,za-5);
          qd(cl.m,prev.x,prev.y,za-.025,x,y,zb-.025,x,y,zb+.025,prev.x,prev.y,za+.025,MAT.metal,.5,prev.x+nx*40,prev.y+ny*40,za);
          qd(cl.m,prev.x,prev.y,za-.025,x,y,zb-.025,x,y,zb+.025,prev.x,prev.y,za+.025,MAT.metal,.5,prev.x-nx*40,prev.y-ny*40,za); } stat.wire++; }
      if(!prev){ (S.wireDbg||(S.wireDbg=[])).push([x,y,headAt(D,s,6),s]); } prev={x:x,y:y,s:s}; } });
  (W.poles||[]).forEach(function(p){ var cl=cellOf(S,p[0],p[1]); if(cl.lod||!room(cl,60)) return; pathAt(D,p[2],o); var dx=o.x-p[0], dy=o.y-p[1], l=Math.hypot(dx,dy)||1;
    frameV(p[0],p[1],0,dx/l,dy/l,UM); fbox(cl.m,0,-.05,6.2,l/UM,.05,6.45,MAT.metal,PC.rail); fbox(cl.m,l/UM-.1,-.08,5.4,l/UM+.1,.08,6.5,MAT.metal,PC.rail); }); }

/* ═══ MOVERS ═══ cars on loops around the blocks (right-hand traffic, signals, car-following), people on the sidewalks, birds, signal lamps */
var TCY=36, GFR=.42, YFR=.04, CAR_B=3.2, CAR_A=2.4;
function jphase(x,y){ return hash(Math.round(x/8)*71+Math.round(y/8)*1013+17)*TCY; }
/* 1 green, 2 yellow, 0 red for the axis (H: east-west) of the crossing at (jx,jy) at time t */
function sigState(axisH, jx, jy, t){ var f=((t+jphase(jx,jy))%TCY)/TCY; if(f<0) f+=1; if(!axisH){ f+=.5; if(f>=1) f-=1; } return f<GFR?1:f<GFR+YFR?2:0; }

var _TPL={};      /* meshes shared by every world: car colours, figures, birds, signal lamps */
function carTpl(ti, ci, taxi, bus){ var k=bus?'bus':ti+'.'+ci+(taxi?'t':''); var a=_TPL[k]; if(a) return a;
  var m=sb(4096); if(bus){ frame(-5.8*UM,0,0,0,UM); busBody(m,PC.car[5]); } else { var T=CAR_T[ti]; frame(-T.L*.5*UM,0,0,0,UM); carBody(m,T,taxi?PC.taxi:PC.car[ci],true,taxi); }
  return (_TPL[k]=sfin(m)); }
function personTpl(type, look, pose){ var k='p'+type+'.'+look.skin+look.hair+look.top+look.bot+'.'+pose; var a=_TPL[k]; if(a) return a; return (_TPL[k]=personMesh(type,look,pose)); }
function birdTpl(kind, w){ var k='b'+kind+w; return _TPL[k]||(_TPL[k]=birdMesh(kind,w)); }
function sigTpl(st){ var k='s'+st; var a=_TPL[k]; if(a) return a; var m=sb(128), col=st===0?PC.lampR:st===1?PC.lampG:PC.lampY, zz=[5.13,4.8,4.47][st===0?0:st===2?1:2];
  var x=.2*UM, y=.1*UM, z0=SZ_SW+(zz-.1)*UM, z1=SZ_SW+(zz+.1)*UM; qd(m,x,-y,z0,x,y,z0,x,y,z1,x,-y,z1,MAT.lamp,col,0,0,(z0+z1)/2); return (_TPL[k]=sfin(m)); }

/* a loop: a rounded rectangle one lane inside the outline of a group of blocks, clockwise on the screen; with its arcs and the stop lines of the crossings it passes */
function makeLoop(gx0,gy0,gx1,gy1,nxs,nys){
  var d=5.2, rc=7, x0=gx0+d, y0=gy0+d, x1=gx1-d, y1=gy1-d, pts=[], cum=[], arcs=[], i;
  function arc(cx,cy,a0,a1){ var s0=pts.length/2; for(var k=0;k<=6;k++){ var a=a0+(a1-a0)*k/6; pts.push(cx+Math.cos(a)*rc,cy+Math.sin(a)*rc); } arcs.push([s0,s0+6]); }
  pts.push(x0+rc,y0);
  arc(x1-rc,y0+rc,-1.5708,0); arc(x1-rc,y1-rc,0,1.5708); arc(x0+rc,y1-rc,1.5708,3.14159); arc(x0+rc,y0+rc,3.14159,4.71239);
  var n=pts.length/2; cum.push(0); for(i=1;i<n;i++) cum.push(cum[i-1]+Math.hypot(pts[2*i]-pts[2*i-2],pts[2*i+1]-pts[2*i-1]));
  var Lp=cum[n-1]+Math.hypot(pts[0]-pts[2*n-2],pts[1]-pts[2*n-1]);
  var L={x:pts, cum:cum, n:n, Lp:Lp, arcs:arcs.map(function(a){ return [cum[a[0]],cum[a[1]]]; }), juns:[], gx0:gx0,gy0:gy0,gx1:gx1,gy1:gy1, cars:[], dead:false};
  /* where a straight side starts (cum) and its origin coordinate: top starts at index 0 (x0+rc), right at arc0 end, bottom at arc1 end, left at arc2 end */
  var sTop=0, sRight=cum[arcs[0][1]], sBot=cum[arcs[1][1]], sLeft=cum[arcs[2][1]], so=11+7.15+3.0, ex=11+2;
  function J(s,exit,axisH,jx,jy){ L.juns.push({sStop:s,sExit:exit,axisH:axisH,jx:jx,jy:jy}); }
  nxs.forEach(function(xi){ if(xi>gx0+1) J(sTop+(xi-so-(x0+rc)), sTop+(xi+ex-(x0+rc)), true, xi, gy0); });                    /* top, eastbound: interior nodes and the NE corner */
  nys.forEach(function(yj){ if(yj>gy0+1) J(sRight+(yj-so-(y0+rc)), sRight+(yj+ex-(y0+rc)), false, gx1, yj); });                /* right, southbound */
  nxs.forEach(function(xi){ if(xi<gx1-1) J(sBot+((x1-rc)-(xi+so)), sBot+((x1-rc)-(xi-ex)), true, xi, gy1); });                  /* bottom, westbound */
  nys.forEach(function(yj){ if(yj<gy1-1) J(sLeft+((y1-rc)-(yj+so)), sLeft+((y1-rc)-(yj-ex)), false, gx0, yj); });              /* left, northbound */
  /* a corner junction's exit is the end of its arc */
  L.juns.sort(function(a,b){ return a.sStop-b.sStop; });
  /* the interior crossings on the top side belong to the top side's axis: fix the corner nodes' coordinates */
  return L; }
function loopAt(L, s, o){ s=((s%L.Lp)+L.Lp)%L.Lp; var lo=0, hi=L.n-1, c=L.cum, p=L.x;
  if(s>=c[hi]){ var t=(s-c[hi])/((L.Lp-c[hi])||1); o.x=p[2*hi]+(p[0]-p[2*hi])*t; o.y=p[2*hi+1]+(p[1]-p[2*hi+1])*t; o.h=Math.atan2(p[1]-p[2*hi+1],p[0]-p[2*hi]); return o; }
  while(hi-lo>1){ var mid=(lo+hi)>>1; if(c[mid]<=s) lo=mid; else hi=mid; }
  var t2=(s-c[lo])/((c[lo+1]-c[lo])||1); o.x=p[2*lo]+(p[2*lo+2]-p[2*lo])*t2; o.y=p[2*lo+1]+(p[2*lo+3]-p[2*lo+1])*t2; o.h=Math.atan2(p[2*lo+3]-p[2*lo+1],p[2*lo+2]-p[2*lo]); return o; }
function walkAt(L, s, o){ if(L.closed) return loopAt(L,s,o); if(s<0) s=0; else if(s>L.Lp) s=L.Lp; var lo=0, hi=L.n-1, c=L.cum, p=L.x; while(hi-lo>1){ var mid=(lo+hi)>>1; if(c[mid]<=s) lo=mid; else hi=mid; } var t=(s-c[lo])/((c[lo+1]-c[lo])||1); o.x=p[2*lo]+(p[2*lo+2]-p[2*lo])*t; o.y=p[2*lo+1]+(p[2*lo+3]-p[2*lo+1])*t; return o; }
function offsetRing(ring, off){      /* a clockwise ring moved inward by off (mitred) */
  var n=ring.length/2, o=[], i; for(i=0;i<n;i++){ var p=(i+n-1)%n, q=(i+1)%n, ax=ring[2*i]-ring[2*p], ay=ring[2*i+1]-ring[2*p+1], bx=ring[2*q]-ring[2*i], by=ring[2*q+1]-ring[2*i+1], la=Math.hypot(ax,ay)||1, lb=Math.hypot(bx,by)||1;
    var n1x=-ay/la, n1y=ax/la, n2x=-by/lb, n2y=bx/lb, dd=1+n1x*n2x+n1y*n2y; if(dd<.2) dd=.2; o.push(ring[2*i]+(n1x+n2x)/dd*off, ring[2*i+1]+(n1y+n2y)/dd*off); }
  return o; }
var LOOKS=[]; (function(){ for(var i=0;i<10;i++) LOOKS.push({skin:(hash(i*7+1)*5)|0, hair:(hash(i*11+2)*6)|0, top:(hash(i*13+3)*PC.cloth.length)|0, bot:(hash(i*17+4)*PC.pants.length)|0}); })();

function moversGather(S, W, M, stat, SI){
  var mv={cars:[], walk:[], birds:[], heads:S.heads||[], cell:{}, t:-1, act:[], loops:[], nc:0}; W._mv=mv; var O=S.O, i, j, k;
  function put(ob){ var key=Math.floor(ob.cx/SCN_CELL)+','+Math.floor(ob.cy/SCN_CELL); (mv.cell[key]||(mv.cell[key]=[])).push(ob); }
  /* ── car loops around groups of rectangular blocks ── */
  if(SCN.cars){
    var rects={}, list=[];
    W.tiles.forEach(function(T){ var r=T.ring; if(r.length!==8) return; for(var e=0;e<4;e++){ if(Math.abs(r[2*e]-r[2*((e+1)%4)])>.5 && Math.abs(r[2*e+1]-r[2*((e+1)%4)+1])>.5) return; } var x0=Math.min(r[0],r[2],r[4],r[6]), x1=Math.max(r[0],r[2],r[4],r[6]), y0=Math.min(r[1],r[3],r[5],r[7]), y1=Math.max(r[1],r[3],r[5],r[7]);
      if(Math.abs((x1-x0)-(r[0]===r[2]?Math.abs(r[0]-r[4]):Math.abs(r[0]-r[2])))>400) return; var t={x0:x0-STREET_HW,y0:y0-STREET_HW,x1:x1+STREET_HW,y1:y1+STREET_HW,used:false}; rects[Math.round(t.x0)+','+Math.round(t.y0)]=t; list.push(t); });
    list.sort(function(a,b){ return a.x0-b.x0||a.y0-b.y0; });
    function near(t,dx,dy){ var key=Math.round(dx)+','+Math.round(dy); var q=rects[key]; return q&&!q.used&&Math.abs(q.x1-q.x0-(t.x1-t.x0))<2&&Math.abs(q.y1-q.y0-(t.y1-t.y0))<2?q:null; }
    list.forEach(function(t){ if(t.used) return; var g=hk(t.x0,t.y0,50), grp=[t], gx1=t.x1, gy1=t.y1, nxs=[t.x0,t.x1], nys=[t.y0,t.y1];
      var e=near(t,t.x1,t.y0), s2=near(t,t.x0,t.y1), d2=e&&s2?near(e,e.x0,e.y1):null;
      if(g<.12 && e && s2 && d2 && d2===near(s2,s2.x1,s2.y0)){ grp=[t,e,s2,d2]; gx1=e.x1; gy1=s2.y1; nxs=[t.x0,t.x1,e.x1]; nys=[t.y0,t.y1,s2.y1]; }
      else if(g<.4 && e){ grp=[t,e]; gx1=e.x1; nxs=[t.x0,t.x1,e.x1]; }
      else if(g<.65 && s2){ grp=[t,s2]; gy1=s2.y1; nys=[t.y0,t.y1,s2.y1]; }
      grp.forEach(function(q){ q.used=true; });
      var L=makeLoop(t.x0,t.y0,gx1,gy1,nxs,nys); L.cx=(t.x0+gx1)/2; L.cy=(t.y0+gy1)/2; L.rank=SI?(function(){ var st=streetAt(SI,t.x0,t.y0+(gy1-t.y0)/2,0,1,16,.5); return st?st.k:3; })():3;
      var c=cellOf(S,L.cx,L.cy); if(c.lod) return; mv.loops.push(L); });
    /* cars on every loop: spacing, kind, colour; loops that run along the ride's own lane carry none */
    var o={x:0,y:0,h:0};
    mv.loops.forEach(function(L){ var lh=hk(L.cx,L.cy,51);
      for(var s=0;s<L.Lp;s+=6){ loopAt(L,s,o); if(S.trackNear(o.x,o.y,3.9)||S.inPark(o.x,o.y)||S.onWater(o.x,o.y,1)){ L.dead=true; break; } }
      if(L.dead) return;
      var nC=Math.max(1,Math.min(4,Math.round(L.Lp/380))), v=(L.rank<=1?12.5:10.5)+3*lh; L.v=v; L.vc=5.2;
      for(var q=0;q<nC;q++){ var h=hk(L.cx+q*17,L.cy,52+q), bus=(L.rank<=1 && h<.12), ti=(hk(L.cx,L.cy+q*13,53)*6)|0, ci=(hk(L.cx*3,L.cy,54+q)*PC.car.length)|0, taxi=(L.rank<=1 && h>.88);
        var car={kind:0, a:carTpl(ti,ci,taxi,bus), x:0,y:0,z:0,yaw:0, loop:L, len:bus?11.6*UM:CAR_T[ti].L*UM, s0:(q+.2+.6*hk(L.cx,L.cy,55+q))/nC*L.Lp, s:0, v:v, nj:0, vs:v*(.9+.2*hk(L.cx,L.cy+q,56)), cx:L.cx, cy:L.cy};
        L.cars.push(car); mv.cars.push(car); } });
  }
  /* ── people on the sidewalks: loops where the whole curb is free, else open runs they walk up and down ── */
  if(SCN.people){
    var offs=[1.1,.8,.5];
    function roundPoly(p, closed){ var m=p.length/2, o=[], q; for(q=0;q<m;q++){ var edge=(!closed&&(q===0||q===m-1)); if(edge){ o.push(p[2*q],p[2*q+1]); continue; }
        var p0=(q+m-1)%m, p1=(q+1)%m, px=p[2*q], py=p[2*q+1], ax=p[2*p0]-px, ay=p[2*p0+1]-py, bx=p[2*p1]-px, by=p[2*p1+1]-py, la=Math.hypot(ax,ay)||1, lb=Math.hypot(bx,by)||1, c=Math.min(2.4,la*.3,lb*.3);
        o.push(px+ax/la*c,py+ay/la*c, px+bx/lb*c,py+by/lb*c); } return o; }
    function mkLoop(p, closed){ var m=p.length/2, cum=[0], q; for(q=1;q<(closed?m+1:m);q++) cum.push(cum[q-1]+Math.hypot(p[2*(q%m)]-p[2*(q-1)],p[2*(q%m)+1]-p[2*(q-1)+1])); return {x:p,cum:cum,n:m,Lp:cum[cum.length-1],closed:closed}; }
    W.tiles.forEach(function(T){ var cl=cellOf(S,T.cx,T.cy); if(cl.lod) return; var ring=cwRing(T.ring), n=ring.length/2; if(n<4||n>16) return; var th=hk(T.cx,T.cy,60); if(th<.1) return;
      var rings=offs.map(function(o){ return offsetRing(ring,o); }), ev=[], e, oi, t;
      for(e=0;e<n;e++){ ev.push(-1); for(oi=0;oi<3;oi++){ var rr=rings[oi], ax=rr[2*e], ay=rr[2*e+1], bx=rr[2*((e+1)%n)], by=rr[2*((e+1)%n)+1], l=Math.hypot(bx-ax,by-ay), ok=l>6;
          for(t=0;t<=l&&ok;t+=5){ var x=ax+(bx-ax)*t/l, y=ay+(by-ay)*t/l; if(S.blocked(x,y,.8)||S.onWater(x,y,1)||S.trackNear(x,y,1.5)) ok=false; } if(ok){ ev[e]=oi; break; } } }
      var chains=[], all=ev.every(function(v){ return v>=0 && v===ev[0]; });
      if(all){ chains.push(mkLoop(roundPoly(rings[ev[0]],true),true)); }
      else { var st=-1; for(e=0;e<n;e++){ if(ev[e]>=0 && (ev[(e+n-1)%n]!==ev[e])){ st=e; break; } } if(st<0) return;
        var i=0; while(i<n){ var e0=(st+i)%n; if(ev[e0]<0){ i++; continue; } var j=i; while(j+1<n && ev[(st+j+1)%n]===ev[e0]) j++;
          var rr2=rings[ev[e0]], pts=[]; for(var q=i;q<=j+1;q++){ var vi=(st+q)%n; pts.push(rr2[2*vi],rr2[2*vi+1]); }
          var len=0; for(q=0;q+3<pts.length;q+=2) len+=Math.hypot(pts[q+2]-pts[q],pts[q+3]-pts[q+1]); if(len>=70) chains.push(mkLoop(roundPoly(pts,false),false)); i=j+1; } }
      chains.forEach(function(LP,ci){ var np=LP.closed?(th<.4?1:th<.75?2:3):(LP.Lp>200?2:1);
        for(var w=0;w<np;w++){ var hh=hk(T.cx+w*7+ci*3,T.cy,61+w), type=hh<.12?2:hh<.58?0:1, look=LOOKS[(hk(T.cx,T.cy+w*5+ci,62+w)*LOOKS.length)|0];
          var pp=LP.x, ox=LP.closed?pp[0]:(pp[0]+pp[pp.length-2])/2, oy=LP.closed?pp[1]:(pp[1]+pp[pp.length-1])/2;
          var po={kind:1, loop:LP, type:type, look:look, poses:[0,1,2,3,4,5].map(function(p){ return personTpl(type,look,p); }), a:personTpl(type,look,0), x:ox,y:oy,z:SZ_SW,yaw:0, dir:hk(T.cx,T.cy,63+w+ci)<.5?1:-1, spd:(1.5+.5*hk(T.cx,T.cy,64+w+ci))*(type===2?.8:1), ph:hk(T.cx+w,T.cy+ci,65)*LP.Lp*(LP.closed?1:2), cx:ox, cy:oy, pose:-1, stride:type===2?1.4:1.9};
          mv.walk.push(po); put(po); } }); });
  }
  /* ── birds ── */
  if(SCN.birds){ var keys=Object.keys(S.cells); keys.forEach(function(k){ var c=S.cells[k]; if(c.lod) return; var h=hn(c.ci*977+c.cj*131,70); if(h>.55) return; var nb=1+((hn(c.ci*31+c.cj*17,71)*3)|0);
      for(var b=0;b<nb;b++){ var kind=hn(c.ci+b*9+c.cj*5,72)<.7?0:1, bo={kind:2, bk:kind, bw:[birdTpl(kind,-1),birdTpl(kind,0),birdTpl(kind,1)], a:birdTpl(kind,0), x:0,y:0,z:0,yaw:0, ox:(c.ci+.15+.7*hn(c.ci*7+b,73))*SCN_CELL, oy:(c.cj+.15+.7*hn(c.cj*7+b,74))*SCN_CELL, R:40+60*hn(c.ci*3+c.cj*5+b,75), w:(.22+.2*hn(c.ci*13+c.cj+b*3,76))*(hn(c.ci+c.cj*3+b,77)<.5?1:-1), p0:hn(c.ci*5+b,78)*6.283, zc:0, zr:28+30*hn(c.ci+c.cj*9+b,79), cx:(c.ci+.5)*SCN_CELL, cy:(c.cj+.5)*SCN_CELL, wing:0};
        bo.zc=Math.max(bo.zr, obMaxH(O,bo.ox-bo.R,bo.oy-bo.R,bo.ox+bo.R,bo.oy+bo.R)+6+8*hn(c.ci+b*3+c.cj,80)); mv.birds.push(bo); put(bo); } }); }
  /* ── signal lamps (the three states) as movers on the poles that cornerItems recorded ── */
  var SIGT=[sigTpl(0),sigTpl(1),sigTpl(2)]; mv.sigt=SIGT; mv.heads.forEach(function(hd){ hd.kind=3; hd.a=SIGT[1]; hd.cx=hd.x; hd.cy=hd.y; hd.z=0; hd.st=1; hd.x=hd.x; put(hd); });
  mv.cars.forEach(function(c){ put(c); });
  W.movers=[]; mv.t=-1; mv.nc=mv.cars.length; resetCars(mv); stat.cars+=0; stat.movers=mv.cars.length+mv.walk.length+mv.birds.length+mv.heads.length; }
function resetCars(mv){ mv.t=0; var o={x:0,y:0,h:0}; mv.cars.forEach(function(c){ var L=c.loop; c.s=c.s0; c.v=c.vs*.8; c.nj=0; var bd=1e18; for(var j=0;j<L.juns.length;j++){ var d=((L.juns[j].sStop-c.s)%L.Lp+L.Lp)%L.Lp; if(d<bd){ bd=d; c.nj=j; } } c.lead=null; });
  mv.loops.forEach(function(L){ var n=L.cars.length; for(var i=0;i<n;i++) L.cars[i].lead=n>1?L.cars[(i+1)%n]:null; }); }
function stepCars(mv, dt, t){
  var cars=mv.cars, n=cars.length, i;
  for(i=0;i<n;i++){ var c=cars[i], L=c.loop; if(L.dead) continue; var s=c.s, v=c.v, vd=c.vs, Lp=L.Lp, a, dA=1e9;
    for(a=0;a<L.arcs.length;a++){ var A=L.arcs[a], d; if(s>=A[0]&&s<=A[1]) d=0; else { d=A[0]-s; if(d<0) d+=Lp; var d2=s-A[1]; if(d2<0) d2+=Lp; if(d2<d) d=d2; } if(d<dA) dA=d; }
    var lim=L.vc+.2*dA; if(lim<vd) vd=lim;
    var jn=L.juns[c.nj]; if(jn){ var ds=jn.sStop-s; if(ds<0) ds+=Lp;
      if(ds>Lp-8){ c.nj=(c.nj+1)%L.juns.length; jn=L.juns[c.nj]; ds=jn.sStop-s; if(ds<0) ds+=Lp; }
      if(ds<90){ var st=sigState(jn.axisH,jn.jx,jn.jy,t); if(st===0 || (st===2 && ds>v*v/(2*CAR_B*1.3)+2)){ var ls=Math.sqrt(2*CAR_B*Math.max(ds-.2,0)); if(ls<vd) vd=ls; } } }
    var ld=c.lead; if(ld){ var gap=ld.s-s; if(gap<0) gap+=Lp; gap-=(c.len+ld.len)*.5; var lf=Math.sqrt(2*CAR_B*Math.max(gap-2.2,0)); if(lf<vd) vd=lf; }
    if(v<vd){ v+=CAR_A*dt; if(v>vd) v=vd; } else { v-=CAR_B*1.6*dt; if(v<vd) v=vd; }
    if(v<0) v=0; s+=v*dt; if(s>=Lp) s-=Lp; c.s=s; c.v=v; } }

var _lo={x:0,y:0,h:0}, _lo2={x:0,y:0,h:0};
function updateSafe(W, tm, Cam){ try{ return updateMain(W, tm, Cam); }catch(x){ if(!updateSafe.warned){ updateSafe.warned=1; if(window.console) console.warn('scenery update', x); } if(W&&W.movers) W.movers.length=0; return 0; } }
function updateMain(W, tm, Cam){
  var mv=W&&W._mv; if(!mv||!Cam) return; var out=W.movers, i, j, k;
  /* the cars live in the world's own time: fixed steps of 1/30 s up to tm */
  var tt=tm>0?tm*(W._scn&&W._scn.tscale||1):0; if(mv.t<0||tt<mv.t-1e-6){ resetCars(mv); } if(tt-mv.t>20) mv.t=tt-20;
  while(mv.t+1/30<=tt+1e-9){ stepCars(mv,1/30,mv.t); mv.t+=1/30; }
  var cx=Cam.x, cy=Cam.y, ci=Math.floor(cx/SCN_CELL), cj=Math.floor(cy/SCN_CELL), n=0, MAXM=72;
  out.length=0;
  for(i=-1;i<=1;i++) for(j=-1;j<=1;j++){ var l=mv.cell[(ci+i)+','+(cj+j)]; if(!l) continue;
    for(k=0;k<l.length && n<MAXM;k++){ var ob=l[k], dx, dy, d2;
      if(ob.kind===0){ if(ob.loop.dead) continue; loopAt(ob.loop,ob.s,_lo); ob.x=_lo.x; ob.y=_lo.y; ob.yaw=_lo.h; ob.z=0; dx=ob.x-cx; dy=ob.y-cy; d2=dx*dx+dy*dy; if(d2>460*460) continue; }
      else if(ob.kind===1){ var LP=ob.loop, u, dd=ob.dir; if(LP.closed) u=ob.ph+dd*ob.spd*tt; else { var w2=(ob.ph+ob.spd*tt)%(2*LP.Lp); if(w2<LP.Lp){ u=w2; dd=1; } else { u=2*LP.Lp-w2; dd=-1; } }
        walkAt(LP,u,_lo); ob.x=_lo.x; ob.y=_lo.y; dx=ob.x-cx; dy=ob.y-cy; d2=dx*dx+dy*dy; if(d2>230*230) continue;
        walkAt(LP,u+dd*1.3,_lo2); ob.yaw=Math.atan2(_lo2.y-_lo.y,_lo2.x-_lo.x); var ps=Math.floor((((u*dd)/ob.stride)%1+1)%1*6)%6; if(ps!==ob.pose){ ob.pose=ps; ob.a=ob.poses[ps]; } }
      else if(ob.kind===2){ var ang=ob.p0+ob.w*tt; ob.x=ob.ox+Math.cos(ang)*ob.R; ob.y=ob.oy+Math.sin(ang)*ob.R; ob.z=ob.zc+3*Math.sin(tt*1.3+ob.p0); ob.yaw=ang+(ob.w>0?1.5708:-1.5708); dx=ob.x-cx; dy=ob.y-cy; d2=dx*dx+dy*dy; if(d2>380*380) continue;
        var wp=Math.floor(tt*5+ob.p0)&3, w=wp===0?1:wp===2?-1:0; if(w!==ob.wing){ ob.wing=w; ob.a=ob.bw[w+1]; } }
      else { dx=ob.x-cx; dy=ob.y-cy; d2=dx*dx+dy*dy; if(d2>160*160) continue; var st=sigState(ob.axisH,ob.jx,ob.jy,tt); if(st!==ob.st){ ob.st=st; ob.a=mv.sigt[st]; } }
      out[n++]=ob; } }
  return n; }

/* ── the 2D fallback (no WebGL): trees, lamps and the movers as small shapes; skipped when the GL renderer draws the meshes ── */
var _glc=null;
function glActive(W){ if(W.glOn!=null) return !!W.glOn; if(!_glc||!_glc.isConnected) _glc=(typeof document!=='undefined')?document.querySelector('#pal-ride .pr-gl'):null; return !!(_glc && _glc.style.display!=='none'); }
function drawFallback(ctx, W, P, Cam, tm){
  if(!W||!W.scenery||glActive(W)) return; var sc=W.scenery, o={x:0,y:0,k:0,d:0}, i, t=sc.t, fog=P.fog||[200,210,220];
  ctx.lineWidth=1; var drawn=0;
  for(i=0;i<t.length && drawn<150;i+=5){ var x=t[i], y=t[i+1], dx=x-Cam.x, dy=y-Cam.y, zc=dx*Cam.fx+dy*Cam.fy; if(zc<NEARZ||zc>520) continue; if(Math.abs(dx*Cam.rx+dy*Cam.ry)>zc*Cam.tan*1.3+10) continue;
    var h=t[i+2], r=t[i+3], kind=t[i+4]; if(!project(x,y,0,o)) continue; drawn++; var k=o.k, ox=o.x, oy=o.y; var f=1-Math.exp(-zc/FOGD);
    if(kind>=2){ ctx.fillStyle='rgb(70,56,44)'; ctx.fillRect(ox-.18*k,oy-h*.5*k,.36*k,h*.5*k); ctx.fillStyle=css(mixC(kind===3?[190,120,60]:[78,126,60],fog,f)); ctx.beginPath(); ctx.ellipse(ox,oy-h*.72*k,r*k,r*.8*k,0,0,6.2832); ctx.fill(); }
    else { ctx.fillStyle='rgb(60,64,72)'; ctx.fillRect(ox-.08*k,oy-h*k,.16*k,h*k); if(kind===1){ ctx.fillStyle='rgb(255,236,170)'; ctx.fillRect(ox-.3*k,oy-h*k,.9*k,.2*k); } } }
  var mvl=W.movers||[]; for(i=0;i<mvl.length;i++){ var mo=mvl[i]; if(!project(mo.x,mo.y,0,o)) continue; var kk=o.k;
    if(mo.kind===0){ ctx.fillStyle='rgb(150,40,40)'; ctx.fillRect(o.x-1.4*kk,o.y-1.5*kk,2.8*kk,1.5*kk); } else if(mo.kind===1){ ctx.fillStyle='rgb(60,70,110)'; ctx.fillRect(o.x-.35*kk,o.y-1.9*kk,.7*kk,1.9*kk); } } }

/* a read-only door for the QA kit and the tests (window._palScn): the world of the ride, a world gathered by hand, the movers' update, the options */
window._palScn={world:function(){ return R.W; }, E:function(){ return E; }, gather:function(set){ return gatherWorld(set, null); }, cam:function(){ return C; }, hash:hash, SCN:SCN, update:updateSafe, PAL:PAL, CAR_T:CAR_T, tpl:function(){ return _TPL; }, sig:sigState, pos:function(c,o){ return loopAt(c.loop,c.s,o); }, S:function(){ return R.W&&R.W._scn; }, SW:function(W){ return W._scn; }, obHit:obHit, cwRing:cwRing, noRide:function(f){ var m=R.M; R.M=null; try{ return f(); } finally{ R.M=m; } }, setRide:function(M){ var o=R.M; R.M=M; return o; }};

_scn={gather:gatherSafe, update:updateSafe, draw:drawFallback};
})();
"""
CSS_G = """
  #pal-ride.on::after{content:"";position:absolute;left:0;top:0;right:0;bottom:0;pointer-events:none;background:radial-gradient(ellipse 78% 74% at 50% 52%,rgba(0,0,0,0) 58%,rgba(8,10,18,.30) 100%);}
  #pal-ride .pr-chip,#pal-ride .pr-btns{z-index:2;}
"""
