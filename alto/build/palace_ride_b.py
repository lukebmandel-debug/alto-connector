"""Part B of the first-person ride: what stands along the way (gathered once per leg) and the 3D drawing of it."""

JS_B = r"""
/* ── the world along a ride: everything within ~900 map units of the path, from the page's own data ── */
var CELL=300;
function nearCells(D, rad){
  var set={}, add=function(x,y){ var ci=Math.floor(x/CELL), cj=Math.floor(y/CELL); for(var di=-rad;di<=rad;di++) for(var dj=-rad;dj<=rad;dj++) set[(ci+di)+','+(cj+dj)]=1; };
  for(var s=0;s<D.L;s+=80){ pathAt(D,s,_pa); add(_pa.x,_pa.y); } pathAt(D,D.L,_pa); add(_pa.x,_pa.y); return set; }
function inSet(set,x,y){ return !!set[Math.floor(x/CELL)+','+Math.floor(y/CELL)]; }
var LMH=[[/city hall/i,167],[/one liberty/i,288],[/two liberty/i,258],[/comcast tech/i,342],[/comcast center/i,297],[/bny|mellon/i,241],[/three logan/i,200],[/cira/i,128],[/fmc/i,181],
  [/independence/i,41],[/art museum/i,28],[/convention/i,34],[/franklin inst/i,34],[/courthouse|justice|family court/i,55],[/30th street|suburban|jefferson/i,32],[/arena|center\b|centre\b/i,42],[/field|ballpark|bank park/i,46]];
function lmHeightM(n, floors){ for(var i=0;i<LMH.length;i++) if(LMH[i][0].test(n)) return LMH[i][1]; return floors>=40?floors*4.1:34; }
function solid(ring, h, col, kind, nm){
  var n=ring.length/2, a2=0, cx=0, cy=0, i, x0, y0, x1, y1;
  for(i=0;i<n;i++){ x0=ring[2*i]; y0=ring[2*i+1]; x1=ring[2*((i+1)%n)]; y1=ring[2*((i+1)%n)+1]; a2+=x0*y1-x1*y0; cx+=x0; cy+=y0; }
  cx/=n; cy/=n; var r=0; for(i=0;i<n;i++) r=Math.max(r, Math.hypot(ring[2*i]-cx, ring[2*i+1]-cy));
  var nx=new Float32Array(n), ny=new Float32Array(n), sh=new Float32Array(n), sg=a2>0?1:-1;
  for(i=0;i<n;i++){ x0=ring[2*i]; y0=ring[2*i+1]; x1=ring[2*((i+1)%n)]; y1=ring[2*((i+1)%n)+1]; var dx=x1-x0, dy=y1-y0, l=Math.hypot(dx,dy)||1;
    nx[i]=sg*dy/l; ny[i]=-sg*dx/l; var dot=nx[i]*-.55+ny[i]*-.83; sh[i]=.66+.34*dot; }
  var v=.93+.14*hashXY(cx,cy); col=[col[0]*v,col[1]*v,col[2]*v];
  return {cx:cx, cy:cy, r:r, ring:ring, n:n, nx:nx, ny:ny, sh:sh, h:h, col:col, kind:kind||'b', name:nm||'', d2:0};
}
var STREET_HW=11;
function shrinkRing(q,cx,cy,d){ var o=[], n=q.length/2; for(var i=0;i<n;i++){ var vx=q[2*i]-cx, vy=q[2*i+1]-cy, l=Math.hypot(vx,vy)||1, k=l>d*2?(l-d)/l:.5; o.push(cx+vx*k, cy+vy*k); } return o; }
function boxRing(x0,y0,x1,y1){ return [x0,y0,x1,y0,x1,y1,x0,y1]; }
function turnedRing(L){ var w=L[2]/2, h=L[3]/2, a=(+L[4]||0)*Math.PI/180, c=Math.cos(a), s=Math.sin(a), o=[];
  [[-w,-h],[w,-h],[w,h],[-w,h]].forEach(function(q){ o.push(L[0]+q[0]*c-q[1]*s, L[1]+q[0]*s+q[1]*c); }); return o; }
function glassCol(c, k){ var r=rgbOf(E.tubeCol?E.tubeCol(c||E.NEUTRAL()):c), dk=dark(); return mixC(r, dk?[150,162,200]:[255,255,255], k==null?(dk?.30:.52):k); }
function insetBox(b, f){ var w=b[2]-b[0], d=b[3]-b[1]; return [b[0]+w*f, b[1]+d*f, b[2]-w*f, b[3]-d*f]; }
function lmSolids(l, out, floors){
  var b=l.box; if(!b) return; var Hm=lmHeightM(l.n||'', floors)*1.3, w=b[2]-b[0], d=b[3]-b[1], base=glassCol(null, dark()?.2:.62), nm=l.n;
  var inb=insetBox(b,.08);
  if(/city hall/i.test(nm)){ out.push(solid(boxRing.apply(null,inb), 62, base, 'lm', nm)); var t=insetBox(b,.37); out.push(solid(boxRing.apply(null,t), Hm*.8, mixC(base,[170,160,140],.3), 'lm', nm));
    var t2=insetBox(b,.42); out.push(solid(boxRing.apply(null,t2), Hm*.94, mixC(base,[190,175,140],.3), 'lm', nm)); var t3=insetBox(b,.465); out.push(solid(boxRing.apply(null,t3), Hm*1.12, [200,180,120], 'lm', nm)); return; }
  if(Hm>=140){ out.push(solid(boxRing.apply(null,insetBox(b,.1)), Math.max(48,Hm*.12), base, 'lm', nm)); out.push(solid(boxRing.apply(null,insetBox(b,.22)), Hm*.86, base, 'lm', nm));
    out.push(solid(boxRing.apply(null,insetBox(b,.3)), Hm*.97, mixC(base,[255,255,255],.25), 'lm', nm)); out.push(solid(boxRing.apply(null,insetBox(b,.4)), Hm, mixC(base,[255,255,255],.45), 'lm', nm)); return; }
  if(Hm>=70){ out.push(solid(boxRing.apply(null,insetBox(b,.12)), Hm*.55, base, 'lm', nm)); out.push(solid(boxRing.apply(null,insetBox(b,.26)), Hm, mixC(base,[255,255,255],.2), 'lm', nm)); return; }
  out.push(solid(boxRing.apply(null,inb), Hm, base, 'lm', nm));
  if(/arena|field|ballpark|bank park/i.test(nm)){ var c=insetBox(b,.24); out.push(solid(boxRing.apply(null,c), Hm*.5, mixC(base,[40,150,60],.5), 'lm', nm)); }
}
/* the road furniture and stops along a model */
function addProps(M, props, polesOf){
  var D=M.D, tmp={x:0,y:0};
  M.secs.forEach(function(sec,si){
    var v=sec.veh;
    sec.stops.forEach(function(st,k){ if(!st) return;
      var h=headAt(D, st.s, 14); pathAt(D, st.s, tmp); var fx=Math.cos(h), fy=Math.sin(h), rx=-fy, ry=fx, side=(v==='bus'||v==='tram')?1:(hashXY(tmp.x,tmp.y)<.5?1:-1);
      if(v==='metro'||v==='rail'||v==='tram'){
        var ug=sec.ug.some(function(g){ return st.s>=g[0]-1 && st.s<=g[1]+1; }); if(ug) return;
        var len=v==='tram'?46:80, o0=v==='tram'?6:7.5, o1=v==='tram'?14:18, ring=[];
        [[-len/2,o0],[len/2,o0],[len/2,o1],[-len/2,o1]].forEach(function(q){ ring.push(tmp.x+fx*q[0]+rx*q[1]*side, tmp.y+fy*q[0]+ry*q[1]*side); });
        props.push(solid(ring, 1.5, [168,170,178], 'plat', st.n));
        var mid=(o0+o1)/2; var cr=[]; [[-len/2,o0+1],[len/2,o0+1],[len/2,o1],[-len/2,o1]].forEach(function(q){ cr.push(tmp.x+fx*q[0]+rx*q[1]*side, tmp.y+fy*q[0]+ry*q[1]*side); });
        var cs=solid(cr, 8.4, mixC(rgbOf(sec.color),[232,234,240],.62), 'canopy', st.n); cs.z0=7.6; props.push(cs);
        [-len/2+3, 0, len/2-3].forEach(function(a){ var px=tmp.x+fx*a+rx*(o1-1.5)*side, py=tmp.y+fy*a+ry*(o1-1.5)*side; var ps=solid(boxRing(px-.5,py-.5,px+.5,py+.5), 7.6, [90,94,104], 'pole'); props.push(ps); });
        var sx=tmp.x+fx*(len/2-6)+rx*(o0+1)*side, sy=tmp.y+fy*(len/2-6)+ry*(o0+1)*side, sg=solid(boxRing(sx-.6,sy-.6,sx+.6,sy+.6), 6.4, [70,74,86], 'sign', st.n); sg.sign=1; sg.col2=sec.color; props.push(sg); }
      else if(v==='bus'){ var bx=tmp.x+rx*14*side, by=tmp.y+ry*14*side;
        props.push(solid(boxRing(bx-.5,by-.5,bx+.5,by+.5), 8, [80,86,100], 'pole')); var sg2=solid(boxRing(bx-1.2,by-1.2,bx+1.2,by+1.2), 8.4, [60,120,150], 'sign', st.n); sg2.z0=6.6; sg2.sign=1; sg2.col2=sec.color; props.push(sg2);
        var shr=[]; [[-14,12],[14,12],[14,16],[-14,16]].forEach(function(q){ shr.push(tmp.x+fx*q[0]+rx*q[1]*side, tmp.y+fy*q[0]+ry*q[1]*side); }); var ss=solid(shr, 7, [150,190,205], 'canopy', st.n); ss.z0=0; props.push(ss); }
    });
    if(v==='tram' && sec.line){                                  /* overhead wire: poles every 80 units on the right */
      for(var s=sec.s0; s<sec.s1; s+=80){ pathAt(D,s,tmp); var h2=headAt(D,s,14), px=tmp.x-Math.sin(h2)*9, py=tmp.y+Math.cos(h2)*9; props.push(solid(boxRing(px-.45,py-.45,px+.45,py+.45), 9, [72,76,88], 'pole')); polesOf.push([tmp.x,tmp.y,s]); } }
  });
}
function gather(M){ return gatherWorld(nearCells(M.D, 3), M); }
/* the world inside the cells of `set` ("cx,cy" of CELL units): M is the ride's model (its path, ends and stops) or null for free roaming */
function gatherWorld(set, M){
  var W={solids:[], tiles:[], parks:[], water:[], roads:[], props:[], poles:[], labels:[], tunn:M?M.secs.some(function(s){ return s.ug.length; }):false, set:set, scenery:null, meshes:[], movers:[]};
  var P=E.P, Mp=E.M, i, k;
  /* tiles: the blocks the streets run between (the gaps are the roads) */
  var SW=STREET_HW, edgeSeen={}; W.dashes=[];
  function dashEdge(x0,y0,x1,y1){ var k=Math.round(x0)+','+Math.round(y0)+','+Math.round(x1)+','+Math.round(y1); if(edgeSeen[k]) return; edgeSeen[k]=1; var l=Math.hypot(x1-x0,y1-y0), ux=(x1-x0)/l, uy=(y1-y0)/l;
    for(var p=34;p<l-34;p+=26){ var ax=x0+ux*p, ay=y0+uy*p, bx=ax+ux*11, by=ay+uy*11; W.dashes.push({ring:strip(ax,ay,bx,by,.9,0), cx:(ax+bx)/2, cy:(ay+by)/2}); } }
  (Mp.tiles||[]).forEach(function(t){ var cx=(t[0]+t[2])/2, cy=(t[1]+t[3])/2; if(inSet(set,cx,cy)){ dashEdge(t[0],t[1],t[2],t[1]); dashEdge(t[0],t[3],t[2],t[3]); dashEdge(t[0],t[1],t[0],t[3]); dashEdge(t[2],t[1],t[2],t[3]); } if(inSet(set,cx,cy)) W.tiles.push({ring:boxRing(t[0]+SW,t[1]+SW,t[2]-SW,t[3]-SW), inner:boxRing(t[0]+SW+4,t[1]+SW+4,t[2]-SW-4,t[3]-SW-4), cx:cx, cy:cy, r:Math.hypot(t[2]-t[0],t[3]-t[1])/2}); });
  (Mp.tq||[]).forEach(function(q){ var cx=0, cy=0, n=q.length/2; for(i=0;i<n;i++){ cx+=q[2*i]; cy+=q[2*i+1]; } cx/=n; cy/=n; if(!inSet(set,cx,cy)) return; var r=0; for(i=0;i<n;i++) r=Math.max(r,Math.hypot(q[2*i]-cx,q[2*i+1]-cy)); var sr=shrinkRing(q,cx,cy,SW*1.3); W.tiles.push({ring:sr, inner:shrinkRing(sr,cx,cy,4), cx:cx, cy:cy, r:r}); });
  (Mp.parks||[]).forEach(function(pk){ (pk.r||[]).forEach(function(r){ var n=r.length/2, cx=0, cy=0; for(i=0;i<n;i++){ cx+=r[2*i]; cy+=r[2*i+1]; } cx/=n; cy/=n; var rr=0; for(i=0;i<n;i++) rr=Math.max(rr,Math.hypot(r[2*i]-cx,r[2*i+1]-cy)); if(inSet(set,cx,cy)||rr>600&&Math.hypot(cx-_pa.x,cy-_pa.y)<rr+900) W.parks.push({ring:r, cx:cx, cy:cy, r:rr, name:pk.n}); }); });
  (Mp.river||[]).forEach(function(rv){ var p=rv.p||[], w=rv.w||100; for(i=0;i+3<p.length;i+=2){ var mx=(p[i]+p[i+2])/2, my=(p[i+1]+p[i+3])/2; if(inSet(set,mx,my)) W.water.push({x0:p[i],y0:p[i+1],x1:p[i+2],y1:p[i+3],w:w+34,cx:mx,cy:my,r:Math.hypot(p[i+2]-p[i],p[i+3]-p[i+1])/2+w}); } });
  W.rivers=(Mp.river||[]);
  var hw=Mp.hw&&Mp.hw.roads||[]; hw.forEach(function(r){ var p=r.p||[]; for(i=0;i+3<p.length;i+=2){ var mx=(p[i]+p[i+2])/2, my=(p[i+1]+p[i+3])/2; if(inSet(set,mx,my)) W.roads.push({x0:p[i],y0:p[i+1],x1:p[i+2],y1:p[i+3],w:30,cx:mx,cy:my,r:Math.hypot(p[i+2]-p[i],p[i+3]-p[i+1])/2+15}); } });
  /* buildings: the user's own, as glass blocks on their lots; landmarks; the fill-in */
  var seen={}, hot={}; if(M&&M.a!=null) hot[E.bOf(M.a)]=1; if(M&&M.b!=null) hot[E.bOf(M.b)]=1;
  Object.keys(P.at||{}).forEach(function(id){ if(E.bOf(id)!==id) return; var key=P.at[id]; if(seen[key]) return; seen[key]=1; var L=E.lot(key); if(!L) return; if(!inSet(set,L[0],L[1])) return;
    var tw=(P.tw||{})[id], h=(tw?Math.min(220,60+tw*1):E.nbH(id))*VEX, col=rgbOf(E.tubeCol(E.ucol(id))), gc=mixC(col, dark()?[150,162,200]:[255,255,255], dark()?.30:.5), s=solid(turnedRing(L), h, gc, 'node', E.name(id));
    s.hot=!!hot[id]; s.id=id; s.col2=E.ucol(id); try{ s.door=nodeDoor(L,id); }catch(x){ s.door=null; } W.solids.push(s); });
  (Mp.landmarks||[]).forEach(function(l){ if(!l.box) return; var cx=(l.box[0]+l.box[2])/2, cy=(l.box[1]+l.box[3])/2; if(!inSet(set,cx,cy)) return; landmarkMeshes(l, (P.lmtop||{})[l.n]||30, W); });
  var FG=E.fillGroups?E.fillGroups():null, cnt=0, CAP=2600;
  if(FG){ for(var lv=4;lv>=1;lv--){ var G=FG[lv]||{}; Object.keys(G).forEach(function(key){ var C=G[key]; Object.keys(C.u).forEach(function(u){ var base=rgbOf(E.tubeCol(E.dcol(u==='null'?null:+u)||E.NEUTRAL()));
      var gc=mixC(base, dark()?[150,162,200]:[255,255,255], dark()?.34:.58);
      C.u[u].forEach(function(s){ if(cnt>=CAP) return; var b=s.b; var cx=(b[0]+b[2])/2, cy=(b[1]+b[3])/2; if(!inSet(set,cx,cy)) return;
        var hh=s.h>0?s.h*22+8:(lv>=4?16+hashXY(cx,cy)*14:lv===3?24+hashXY(cx,cy)*30:40+hashXY(cx,cy)*50); var o=solid(s.p, hh*1.25, gc, 'fill', s.n); W.solids.push(o); cnt++; }); }); }); } }
  /* the targets of a leg: a name floating over each end */
  if(M) [M.a, M.b].forEach(function(id,ix){ if(id==null) return; var L=E.lot(P.at[E.bOf(id)]); if(L) W.labels.push({x:L[0], y:L[1], z:(E.nbH(E.bOf(id))*VEX)+14, text:E.name(id), col:E.ucol(E.bOf(id)), end:ix}); });
  if(M) addProps(M, W.props, W.poles);
  W.solids=W.solids.concat(W.props);
  sceneryGather(W, set);
  return W; }

/* ── the camera and the 3D drawing ── */
var C={x:0,y:0,z:2,fx:1,fy:0,rx:0,ry:1,foc:800,hx:0,hy:0,W:0,H:0,tan:1,yaw:0,pitch:0,shk:null};
/* pitch (radians, up positive) tilts the GL view; the 2D fallback ignores it */
/* fk: the focal length as a multiple of the window height (default .98: the vehicles' ~55 degree vertical view); on foot fpFoc() gives the Street-View one */
function setCam(x,y,z,yaw,W,H,hz,pitch,fk){ fk=fk||.98; C.x=x; C.y=y; C.z=z; C.yaw=yaw; C.pitch=pitch||0; if(C.pitch && !glOk()){ hz+=fk*Math.tan(C.pitch); C.pitch=0; } C.fx=Math.cos(yaw); C.fy=Math.sin(yaw); C.rx=-C.fy; C.ry=C.fx; C.W=W; C.H=H; C.foc=H*fk; C.hx=W/2; C.hy=H*hz; C.tan=(W/2)/C.foc; }
/* on foot (roaming and walking legs): a Street-View field of view - 90 degrees across, which is 58.7 degrees up and down at 16:9 - kept between 40 and 70 degrees vertically
   (a tall window gets a bit less than 90 across, a very wide one a bit more up and down than 40) and never wider than 110 across: no fisheye stretch at the edges */
/* footfalls per second of a person moving v metres a second: the step grows with the pace (0.7 m at a stroll, 1.3 m at 4 m/s, 1.9 m at a jog), so 2 Hz walking, 3 Hz hurrying */
function stepHz(v){ return v>.01?v/(.5+.2*v):0; }
var FOV_H=90, FOV_VMIN=40, FOV_VMAX=70, FOV_HMAX=110;
function fpFoc(W,H){ var t=Math.PI/180, foc=W/2/Math.tan(FOV_H/2*t), lo=H/2/Math.tan(FOV_VMAX/2*t), hi=H/2/Math.tan(FOV_VMIN/2*t), top=W/2/Math.tan(FOV_HMAX/2*t); foc=Math.max(lo, Math.min(hi, foc)); return Math.max(foc, top)/H; }
function vis(cx,cy,r){ var dx=cx-C.x, dy=cy-C.y, zc=dx*C.fx+dy*C.fy; if(zc+r<NEARZ || zc-r>FARZ) return false; var xc=dx*C.rx+dy*C.ry; return Math.abs(xc)-r < (zc+r)*C.tan*1.18+r*.2; }
var _wx=new Float64Array(1024), _wz=new Float64Array(1024), _wy=new Float64Array(1024), _ox=new Float64Array(1024), _oz=new Float64Array(1024), _oy=new Float64Array(1024);
/* a flat polygon (ring x,y,x,y…) at height zh (or the per-vertex heights zs), clipped at the near plane; leaves the path on ctx, false when nothing shows */
function flatPath(ctx, ring, zh, zs){
  var n=ring.length/2, i; if(n>500) n=500;
  for(i=0;i<n;i++){ var dx=ring[2*i]-C.x, dy=ring[2*i+1]-C.y; _wx[i]=dx*C.rx+dy*C.ry; _wz[i]=dx*C.fx+dy*C.fy; _wy[i]=zs?zs[i]:zh; }
  var allIn=true, anyIn=false; for(i=0;i<n;i++){ if(_wz[i]<NEARZ) allIn=false; else anyIn=true; } if(!anyIn) return false;
  var X=_wx, Z=_wz, Y=_wy, cnt=n;
  if(!allIn){ cnt=0; for(i=0;i<n;i++){ var j=(i+1)%n, ai=_wz[i]>=NEARZ, aj=_wz[j]>=NEARZ;
      if(ai){ _ox[cnt]=_wx[i]; _oz[cnt]=_wz[i]; _oy[cnt]=_wy[i]; cnt++; }
      if(ai!==aj){ var t=(NEARZ-_wz[i])/(_wz[j]-_wz[i]); _ox[cnt]=_wx[i]+(_wx[j]-_wx[i])*t; _oz[cnt]=NEARZ; _oy[cnt]=_wy[i]+(_wy[j]-_wy[i])*t; cnt++; } }
    X=_ox; Z=_oz; Y=_oy; if(cnt<3) return false; }
  ctx.beginPath();
  for(i=0;i<cnt;i++){ var k=C.foc/Z[i], sx=C.hx+X[i]*k, sy=C.hy-(Y[i]-C.z)*k; if(i) ctx.lineTo(sx,sy); else ctx.moveTo(sx,sy); }
  ctx.closePath(); return true; }
function wallPath(ctx, ax,ay,bx,by,z0,z1){
  var dax=ax-C.x, day=ay-C.y, dbx=bx-C.x, dby=by-C.y, xa=dax*C.rx+day*C.ry, za=dax*C.fx+day*C.fy, xb=dbx*C.rx+dby*C.ry, zb=dbx*C.fx+dby*C.fy, t;
  if(za<NEARZ && zb<NEARZ) return false;
  if(za<NEARZ){ t=(NEARZ-za)/(zb-za); xa+=(xb-xa)*t; za=NEARZ; } else if(zb<NEARZ){ t=(NEARZ-zb)/(za-zb); xb+=(xa-xb)*t; zb=NEARZ; }
  var ka=C.foc/za, kb=C.foc/zb, sa=C.hx+xa*ka, sb=C.hx+xb*kb;
  ctx.beginPath(); ctx.moveTo(sa, C.hy-(z0-C.z)*ka); ctx.lineTo(sb, C.hy-(z0-C.z)*kb); ctx.lineTo(sb, C.hy-(z1-C.z)*kb); ctx.lineTo(sa, C.hy-(z1-C.z)*ka); ctx.closePath(); return true; }
function project(x,y,z,o){ var dx=x-C.x, dy=y-C.y, zc, yc, p=C.pitch;
  if(p){ var cp=Math.cos(p), sp=Math.sin(p), dz=z-C.z, fd=dx*C.fx+dy*C.fy; zc=fd*cp+dz*sp; yc=dz*cp-fd*sp; } else { zc=dx*C.fx+dy*C.fy; yc=z-C.z; }
  if(zc<NEARZ) return false; var xc=dx*C.rx+dy*C.ry, k=C.foc/zc; o.x=C.hx+xc*k; o.y=C.hy-yc*k; o.k=k; o.d=zc; return true; }
var _pr={x:0,y:0,k:0,d:0};
function strip(ax,ay,bx,by,w,ext){ var dx=bx-ax, dy=by-ay, l=Math.hypot(dx,dy)||1, ux=dx/l, uy=dy/l, nx=-uy*w/2, ny=ux*w/2; ax-=ux*(ext||0); ay-=uy*(ext||0); bx+=ux*(ext||0); by+=uy*(ext||0);
  return [ax+nx,ay+ny, bx+nx,by+ny, bx-nx,by-ny, ax-nx,ay-ny]; }
/* the ride's own ribbon: the path from sA to sB, w wide, off to the right of the centre line, at height zh */
var _rib=[], _ribz=[];
function ribbonPath(ctx, D, sA, sB, w, off, zh, stride){
  sA=clamp(sA,0,D.L); sB=clamp(sB,0,D.L); if(sB-sA<STEP) return false; var L=[], R_=[], Lz=[], s=sA, o={x:0,y:0}, M=RIDE_M, hw=w/2, lf=M&&M._lifts&&M._lifts.length;
  for(;;){ pathAt(D,s,o); var h=headAt(D,s,10), nx=-Math.sin(h), ny=Math.cos(h), c=off, z=zh+(lf?lift(M,s):0); L.push(o.x+nx*(c-hw), o.y+ny*(c-hw)); R_.push(o.x+nx*(c+hw), o.y+ny*(c+hw)); Lz.push(z); if(s>=sB) break; var d=Math.hypot(o.x-C.x,o.y-C.y); s=Math.min(sB, s+STEP*(d<120?1:d<400?2:4)); }
  _rib.length=0; _ribz.length=0; var i;
  for(i=0;i<L.length;i+=2){ _rib.push(L[i],L[i+1]); _ribz.push(Lz[i/2]); }
  for(i=R_.length-2;i>=0;i-=2){ _rib.push(R_[i],R_[i+1]); _ribz.push(Lz[i/2]); }
  return flatPath(ctx, _rib, zh, _ribz); }
var RIDE_M=null;
/* ── the sky and ground colours, from the page's own theme ── */
function palette(){
  var dk=dark(), g=null; try{ var v=getComputedStyle(document.documentElement).getPropertyValue('--pal-ground').trim(); if(v) g=v.split(',').map(function(q){ return parseFloat(q)||0; }); }catch(x){} if(!g||g.length<3) g=dk?[28,30,40]:[238,238,242];
  var P={dk:dk, ground:g};
  if(dk){ P.zen=mixC([8,12,34],g,.12); P.hor=mixC([46,56,96],g,.2); P.fog=P.hor; P.street=mixC([22,24,32],g,.06); P.block=mixC([64,68,88],g,.18); P.park=[40,84,56]; P.water=[24,52,92]; P.sun=[210,220,255]; P.glow=[120,140,220]; P.line=[200,205,225]; }
  else { P.zen=mixC([112,168,232],g,.1); P.hor=mixC([228,236,246],g,.22); P.fog=P.hor; P.street=mixC([78,82,94],g,.06); P.block=mixC([192,192,196],g,.25); P.park=[126,176,116]; P.water=[96,152,198]; P.sun=[255,246,214]; P.glow=[255,226,160]; P.line=[255,255,255]; }
  return P; }
function fogMix(c, d, P){ var f=1-Math.exp(-d/FOGD); return [c[0]+(P.fog[0]-c[0])*f, c[1]+(P.fog[1]-c[1])*f, c[2]+(P.fog[2]-c[2])*f]; }
function drawSky(ctx, W, H, P, yaw, t){
  var hy=C.hy, g=ctx.createLinearGradient(0,0,0,hy); g.addColorStop(0, css(P.zen)); g.addColorStop(1, css(P.hor)); ctx.fillStyle=g; ctx.fillRect(0,0,W,hy+1);
  /* sun (or moon) fixed in the world, up and to the north-west, so it slides across the window as the ride turns */
  var az=Math.atan2(-.8,-.6), da=Math.atan2(Math.sin(az-yaw), Math.cos(az-yaw)), sx=C.hx+Math.tan(da)*C.foc;
  if(Math.abs(da)<1.2){ var sy=hy-C.foc*.46, rad=C.H*(P.dk?.028:.04), gr=ctx.createRadialGradient(sx,sy,0,sx,sy,rad*7);
    gr.addColorStop(0, css(P.glow,.55)); gr.addColorStop(.35, css(P.glow,.16)); gr.addColorStop(1, css(P.glow,0)); ctx.fillStyle=gr; ctx.fillRect(sx-rad*7,sy-rad*7,rad*14,rad*14);
    ctx.fillStyle=css(P.sun); ctx.beginPath(); ctx.arc(sx,sy,rad,0,6.2832); ctx.fill();
    if(P.dk){ ctx.fillStyle=css(P.zen,.9); ctx.beginPath(); ctx.arc(sx+rad*.4,sy-rad*.2,rad*.86,0,6.2832); ctx.fill(); } }
  if(P.dk){ ctx.fillStyle='rgba(235,240,255,.7)'; for(var i=0;i<70;i++){ var a=hash(i*17+3)*6.2832, h=hash(i*29+5)*.9; var d=Math.atan2(Math.sin(a-yaw),Math.cos(a-yaw)); if(Math.abs(d)>1.2) continue; var x=C.hx+Math.tan(d)*C.foc, y=hy-h*C.foc*.7; ctx.fillRect(x,y,1.6,1.6); } }
  else { ctx.fillStyle='rgba(255,255,255,.55)'; for(var j=0;j<7;j++){ var a2=hash(j*41+9)*6.2832, d2=Math.atan2(Math.sin(a2-yaw),Math.cos(a2-yaw)); if(Math.abs(d2)>1.3) continue; var cx=C.hx+Math.tan(d2)*C.foc, cy=hy-(.12+hash(j*13+2)*.4)*C.foc*.7, w=C.W*(.07+hash(j*7+1)*.08);
      ctx.beginPath(); ctx.ellipse(cx,cy,w,w*.2,0,0,6.2832); ctx.ellipse(cx+w*.5,cy+w*.05,w*.6,w*.16,0,0,6.2832); ctx.fill(); } }
  /* the ground, fading to the haze at the horizon */
  var g2=ctx.createLinearGradient(0,hy,0,H); g2.addColorStop(0, css(P.fog)); g2.addColorStop(.12, css(mixC(P.street,P.fog,.55))); g2.addColorStop(1, css(P.street)); ctx.fillStyle=g2; ctx.fillRect(0,hy,W,H-hy);
}
function drawGround(ctx, Wd, P, M, cur){
  var i, o, d;
  ctx.lineWidth=1; ctx.lineJoin='round';
  for(i=0;i<Wd.tiles.length;i++){ o=Wd.tiles[i]; if(!vis(o.cx,o.cy,o.r)) continue; d=Math.hypot(o.cx-C.x,o.cy-C.y); if(!flatPath(ctx,o.ring,.05)) continue; var tv=.96+.08*hashXY(o.cx,o.cy); ctx.fillStyle=css(fogMix([P.block[0]*tv,P.block[1]*tv,P.block[2]*tv],d,P)); ctx.fill();
    if(d<650){ ctx.strokeStyle=P.dk?'rgba(0,0,0,.35)':'rgba(40,44,60,.22)'; ctx.stroke(); if(d<420 && o.inner && flatPath(ctx,o.inner,.07)){ ctx.fillStyle=css(fogMix(mixC([P.block[0]*tv,P.block[1]*tv,P.block[2]*tv],P.dk?[40,50,44]:[120,134,118],.14),d,P)); ctx.fill(); } } }
  ctx.fillStyle=P.dk?'rgba(235,225,170,.42)':'rgba(255,255,255,.62)';
  for(i=0;i<Wd.dashes.length;i++){ o=Wd.dashes[i]; var dx0=o.cx-C.x, dy0=o.cy-C.y, zc0=dx0*C.fx+dy0*C.fy; if(zc0<2||zc0>320||Math.abs(dx0*C.rx+dy0*C.ry)>zc0*C.tan*1.3+10) continue; if(flatPath(ctx,o.ring,.09)) ctx.fill(); }
  for(i=0;i<Wd.parks.length;i++){ o=Wd.parks[i]; if(!vis(o.cx,o.cy,o.r)) continue; d=Math.hypot(o.cx-C.x,o.cy-C.y); if(!flatPath(ctx,o.ring,.12)) continue; ctx.fillStyle=css(fogMix(P.park,d,P)); ctx.fill(); }
  for(i=0;i<Wd.roads.length;i++){ o=Wd.roads[i]; if(!vis(o.cx,o.cy,o.r)) continue; d=Math.hypot(o.cx-C.x,o.cy-C.y); if(!flatPath(ctx,strip(o.x0,o.y0,o.x1,o.y1,o.w,2),.1)) continue; ctx.fillStyle=css(fogMix(mixC(P.street,[20,22,28],.25),d,P)); ctx.fill(); }
  for(i=0;i<Wd.water.length;i++){ o=Wd.water[i]; if(!vis(o.cx,o.cy,o.r)) continue; d=Math.hypot(o.cx-C.x,o.cy-C.y); if(!flatPath(ctx,strip(o.x0,o.y0,o.x1,o.y1,o.w,3),.15)) continue; ctx.fillStyle=css(fogMix(P.water,d,P)); ctx.fill(); }
}
/* solids, far to near; a wall is drawn when it faces the camera */
var _vis=[];
function faceLines(ctx, ax,ay,bx,by,z0,z1, fl, mu){
  var dax=ax-C.x, day=ay-C.y, dbx=bx-C.x, dby=by-C.y, za=dax*C.fx+day*C.fy, zb=dbx*C.fx+dby*C.fy; if(za<NEARZ||zb<NEARZ) return;
  var xa=dax*C.rx+day*C.ry, xb=dbx*C.rx+dby*C.ry, ka=C.foc/za, kb=C.foc/zb, sa=C.hx+xa*ka, sb=C.hx+xb*kb, q;
  if(Math.abs(sb-sa)<26) return;
  ctx.beginPath();
  for(q=1;q<fl;q++){ var zz=z0+(z1-z0)*q/fl; ctx.moveTo(sa, C.hy-(zz-C.z)*ka); ctx.lineTo(sb, C.hy-(zz-C.z)*kb); }
  for(q=1;q<mu;q++){ var t=q/mu, k=1/mix(1/ka,1/kb,t)>0?0:0, zc=mix(za,zb,t), sx=C.hx+mix(xa,xb,t)*C.foc/zc; ctx.moveTo(sx, C.hy-(z0-C.z)*C.foc/zc); ctx.lineTo(sx, C.hy-(z1-C.z)*C.foc/zc); }
  ctx.stroke(); }
function drawSolids(ctx, list, P){
  _vis.length=0; var i, s;
  for(i=0;i<list.length;i++){ s=list[i]; if(!vis(s.cx,s.cy,s.r)) continue; var dx=s.cx-C.x, dy=s.cy-C.y; s.d2=dx*dx+dy*dy; _vis.push(s); }
  _vis.sort(function(a,b){ return b.d2-a.d2; });
  var nv=_vis.length, lineN=70; ctx.lineWidth=1;
  for(i=0;i<nv;i++){ s=_vis[i]; var d=Math.sqrt(s.d2), ring=s.ring, n=s.n, z0=s.z0||0, h=s.h, k;
    if(h*C.foc/Math.max(d,1)<.9) continue;
    var fc=fogMix(s.col,d,P), near=(nv-i)<=lineN && d<700 && s.kind!=='pole' && s.kind!=='sign' && (h-z0)>10, fl=near?Math.max(2,Math.round((h-z0)/8)):0;
    for(k=0;k<n;k++){ var ax=ring[2*k], ay=ring[2*k+1], j=(k+1)%n, bx=ring[2*j], by=ring[2*j+1];
      if(s.nx[k]*(C.x-ax)+s.ny[k]*(C.y-ay)<=0) continue;
      if(!wallPath(ctx, ax,ay,bx,by, z0,h)) continue; var sh=s.sh[k]; ctx.fillStyle=css([fc[0]*sh, fc[1]*sh, fc[2]*sh]); ctx.fill();
      if((nv-i)<=40 && d<520){ ctx.strokeStyle=P.dk?'rgba(0,0,0,.35)':'rgba(30,34,56,.16)'; ctx.stroke(); }
      if((nv-i)<=24 && d<520 && h>14){ var gt=C.hy-(h-C.z)*C.foc/Math.max(d,2), gb=C.hy+C.z*C.foc/Math.max(d,2); gt=Math.max(gt,-C.H); var gg=ctx.createLinearGradient(0,gt,0,gb); gg.addColorStop(0,P.dk?'rgba(190,205,255,.20)':'rgba(255,255,255,.26)'); gg.addColorStop(.62,'rgba(255,255,255,0)'); gg.addColorStop(1,'rgba(0,0,0,.20)'); ctx.fillStyle=gg; ctx.fill(); }
      if(near){ ctx.strokeStyle=P.dk?'rgba(190,205,255,.16)':'rgba(255,255,255,.34)'; faceLines(ctx, ax,ay,bx,by,z0,h, fl, d<330?Math.max(2,Math.round(Math.hypot(bx-ax,by-ay)/20)):0); } }
    if(C.z>h && s.kind!=='pole'){ if(flatPath(ctx, ring, h)){ ctx.fillStyle=css(mixC(fc,[255,255,255],.25)); ctx.fill(); } }
    else if(s.kind==='canopy' || s.kind==='plat'){ if(flatPath(ctx, ring, h)){ ctx.fillStyle=css(mixC(fc,[255,255,255],.1)); ctx.fill(); } }
  }
}
/* text floating over a place, same size at a given distance */
function drawLabels(ctx, labs, P, k0){
  var o={x:0,y:0,k:0,d:0};
  labs.forEach(function(l){ if(!project(l.x,l.y,l.z,o)) return; if(o.d>900) return; if(Math.abs(o.x-C.hx)>C.W) return;
    var fs=clamp(12*k0*(C.foc/800)*(1.0+ (300/Math.max(o.d,120))*.6), 11*k0, 22*k0); ctx.font='700 '+fs.toFixed(1)+'px system-ui,-apple-system,Segoe UI,sans-serif'; var tw=ctx.measureText(l.text).width, pw=fs*.7, ph=fs*.62, bw=tw+pw*2, bh=fs+ph;
    var x=o.x-bw/2, y=o.y-bh-fs*.5; ctx.globalAlpha=clamp(1.3-o.d/800,.25,1);
    ctx.fillStyle=P.dk?'rgba(18,20,30,.78)':'rgba(255,255,255,.88)'; rr(ctx,x,y,bw,bh,bh/2); ctx.fill();
    ctx.fillStyle=l.col||'#888'; ctx.beginPath(); ctx.arc(x+pw*.8,y+bh/2,fs*.22,0,6.2832); ctx.fill();
    ctx.fillStyle=P.dk?'#f2f3f8':'#23273a'; ctx.textBaseline='middle'; ctx.textAlign='left'; ctx.fillText(l.text, x+pw*1.35, y+bh/2+.5);
    ctx.strokeStyle=l.col||'#888'; ctx.lineWidth=1.5; ctx.beginPath(); ctx.moveTo(o.x,y+bh); ctx.lineTo(o.x,o.y); ctx.stroke(); ctx.globalAlpha=1; });
}
function rr(ctx,x,y,w,h,r){ r=Math.min(r,w/2,h/2); ctx.beginPath(); ctx.moveTo(x+r,y); ctx.lineTo(x+w-r,y); ctx.arcTo(x+w,y,x+w,y+r,r); ctx.lineTo(x+w,y+h-r); ctx.arcTo(x+w,y+h,x+w-r,y+h,r); ctx.lineTo(x+r,y+h); ctx.arcTo(x,y+h,x,y+h-r,r); ctx.lineTo(x,y+r); ctx.arcTo(x,y,x+r,y,r); ctx.closePath(); }
/* the way itself: track, road or walk, drawn under the solids */
function drawWay(ctx, M, P, s, sec, camOff){
  var D=M.D, v=sec?sec.veh:'walk', a=s-24, b=s+FARZ*.9, hw=sec&&sec.hw;
  if(v==='metro'||v==='rail'||v==='tram'){
    var bw=v==='rail'?10:v==='metro'?8.5:6.5;
    if(ribbonPath(ctx,D,a,b,bw,0,.18,1)){ ctx.fillStyle=css(P.dk?[70,72,84]:[120,118,114]); ctx.fill(); }
    var gap=v==='tram'?1.4:2.2; [-1,1].forEach(function(sd){ if(ribbonPath(ctx,D,a,b,.55,sd*gap*1.0,.28,1)){ ctx.fillStyle=P.dk?'#b8bccb':'#d6d8e0'; ctx.fill(); } });
    var o={x:0,y:0}; ctx.fillStyle=P.dk?'rgba(40,36,34,.9)':'rgba(70,58,46,.85)';
    for(var q=Math.ceil(a/5.5)*5.5;q<Math.min(b,s+170);q+=5.5){ pathAt(D,q,o); var h=headAt(D,q,6), ux=Math.cos(h), uy=Math.sin(h); var ring=strip(o.x-ux*.5,o.y-uy*.5,o.x+ux*.5,o.y+uy*.5,bw*.9,0); if(flatPath(ctx,ring,.22)) ctx.fill(); } }
  else if(v==='bus'||v==='car'){
    var rw=hw?30:22;
    if(ribbonPath(ctx,D,a,b,rw,0,.16,1)){ ctx.fillStyle=css(mixC(P.street,[18,20,26],P.dk?.1:.3)); ctx.fill(); }
    var o2={x:0,y:0}; ctx.fillStyle=P.dk?'rgba(240,240,225,.8)':'rgba(255,255,240,.95)';
    for(var q2=Math.ceil(a/16)*16;q2<Math.min(b,s+220);q2+=16){ pathAt(D,q2,o2); var h2=headAt(D,q2,6), ux2=Math.cos(h2), uy2=Math.sin(h2); var rg=strip(o2.x,o2.y,o2.x+ux2*6,o2.y+uy2*6,.6,0); if(flatPath(ctx,rg,.2)) ctx.fill(); }
    if(hw){ [-1,1].forEach(function(sd){ if(ribbonPath(ctx,D,a,b,.7,sd*rw*.5,.22,2)){ ctx.fillStyle='#f0e6a0'; ctx.fill(); } }); } }
  else { if(ribbonPath(ctx,D,a,b,16,VEH.walk.off,.14,2)){ ctx.fillStyle=css(mixC(P.block,[255,255,255],P.dk?.04:.25)); ctx.fill(); } }
}
function drawBridges(ctx, M, P, s){
  var D=M.D; if(!M._br) return; M._br.forEach(function(g){ if(g[1]<s-30 || g[0]>s+FARZ) return;
    [-1,1].forEach(function(sd){ var o={x:0,y:0}, prev=null; for(var q=Math.max(g[0],s-30);q<=Math.min(g[1],s+700);q+=14){ pathAt(D,q,o); var h=headAt(D,q,8), px=o.x-Math.sin(h)*sd*16, py=o.y+Math.cos(h)*sd*16;
      if(prev && wallPath(ctx,prev[0],prev[1],px,py,.2,2.6)){ ctx.fillStyle=P.dk?'#3a4054':'#a7acb8'; ctx.fill(); } prev=[px,py]; } }); }); }
function bridgeSpans(M, W){
  var D=M.D, spans=[], on=null, o={x:0,y:0}; if(!W.rivers.length) return spans;
  for(var s=0;s<=D.L;s+=10){ pathAt(D,s,o); var inb=false;
    for(var r=0;r<W.rivers.length && !inb;r++){ var p=W.rivers[r].p, hw=(W.rivers[r].w||100)/2+10; for(var i=0;i+3<p.length;i+=2){ if(Math.abs(p[i]-o.x)>hw+80 && Math.abs(p[i+2]-o.x)>hw+80) continue;
        var ax=p[i], ay=p[i+1], bx=p[i+2], by=p[i+3], dx=bx-ax, dy=by-ay, L2=dx*dx+dy*dy||1, t=clamp(((o.x-ax)*dx+(o.y-ay)*dy)/L2,0,1); if(Math.hypot(ax+t*dx-o.x, ay+t*dy-o.y)<hw){ inb=true; break; } } }
    if(inb && on==null) on=s; if(!inb && on!=null){ spans.push([on,s]); on=null; } }
  if(on!=null) spans.push([on,D.L]); return spans.filter(function(g){ return g[1]-g[0]>=25; }); }
"""
