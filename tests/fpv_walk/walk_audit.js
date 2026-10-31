/* The first-person walk audit (node, no browser, no GL): the Memory Blueprint renderer's own walking code (palace_building_fpv.py, API.sim / API.step)
   walks a capsule through EVERY passable opening of a plan (both ways, at a walk and a run) and up and down EVERY stair flight, and hops in every
   room it passes. It reports doors narrower or lower than the capsule, any fall into another floor, any place the walker gets stuck and every
   time the safety net had to catch it.

   node walk_audit.js <renderer.js> <plan.json> [cards]     ->  one JSON line: {doors, stairs, hops, fails:[...], ...}
   cards: put a card sign in every room (as a timeline's nodes would stand), so the signs are part of what must not block a door. */
global.window=global; global.document=null; global.navigator={};
var fs=require('fs');
eval(fs.readFileSync(process.argv[2],'utf8'));
var plan=JSON.parse(fs.readFileSync(process.argv[3],'utf8')), withCards=process.argv[4]==='cards';
var A=window.AltoBuildingFPV, CFG=A.CFG, S=A._debug(), data=null;
if(withCards){ data={nodes:{}, order:[]}; (plan.rm||[]).forEach(function(r,i){ if(r.gp||r.k==='void') return; var id='n'+i; data.nodes[id]={n:'Card '+i, t:'Card '+i, r:r.id, a:0}; data.order.push(id); }); }
var G=A.sim(plan,data), DT=1/60, fails=[], out={doors:0, doorWalks:0, widened:0, stairs:0, stairWalks:0, hops:0, skipped:[]};
function g(){ return A.geom; }
function place(x,y,z,yaw){ S.x=x; S.y=y; S.fz=z; S.ez=z+CFG.eye; S.vx=S.vy=S.vz=0; S.air=false; S.grounded=true; S.glide=null; S.safe=null; S.yaw=yaw; S.dip=0; S.stuckN=0; S.room=null; }
function sup(x,y,z){ return A.geom.support(x,y,z); }
function freeAt(x,y,z){ return !A.geom.blocked(x,y,z); }
/* walk from p0 toward p1 (steering at it), run or walk; done when past p1's plane; returns {ok, why, minZ, maxZ} */
function walk(p0,p1,z0,run,maxT,expectZ,tolZ){
  place(p0[0],p0[1],z0,Math.atan2(p1[1]-p0[1],p1[0]-p0[0])); var nets0=S.nets, res0=S.rescues, dx=p1[0]-p0[0], dy=p1[1]-p0[1], L=Math.hypot(dx,dy), ux=dx/L, uy=dy/L, best=-1e9, bestT=0, t=0, minZ=1e9, maxZ=-1e9;
  while(t<maxT){ S.yaw=Math.atan2(p1[1]-S.y,p1[0]-S.x); A.step(DT,{f:1,run:run?1:0},1); t+=DT; minZ=Math.min(minZ,S.fz); maxZ=Math.max(maxZ,S.fz);
    var along=(S.x-p0[0])*ux+(S.y-p0[1])*uy; if(along>best+.02){ best=along; bestT=t; }
    if(along>=L-.15) break; if(t-bestT>1.2) return {ok:false, why:'stuck', at:[+S.x.toFixed(2),+S.y.toFixed(2),+S.fz.toFixed(2)], along:+best.toFixed(2), L:+L.toFixed(2)}; }
  if(best<L-.15) return {ok:false, why:"slow", along:+best.toFixed(2), L:+L.toFixed(2)};
  if(S.nets>nets0) return {ok:false, why:'fell (the safety net caught it)', at:[+S.x.toFixed(2),+S.y.toFixed(2)]};
  if(S.rescues>res0) return {ok:false, why:'stuck in geometry (rescued)', at:[+S.x.toFixed(2),+S.y.toFixed(2)]};
  if(expectZ!=null&&Math.abs(S.fz-expectZ)>tolZ&&!A.geom.onStair(S.x,S.y)) return {ok:false, why:'wrong floor', z:+S.fz.toFixed(2), want:expectZ};
  return {ok:true, minZ:minZ, maxZ:maxZ}; }
/* a free standing spot near p at floor z: p itself or nudged up to 1 m along the given direction (furniture by a door) */
/* a free standing spot in front of a door (c + dir * off): 0.75 m clear of the wall face, else nearer (a corridor), else further (furniture by the door) */
function spot(c,dir,z,face,hw){ var ds=[.75,.65,.55,.45,.9,1.1,1.3,1.5], ls=[0]; for(var q=.25;q<(hw||.3)-.2;q+=.25) ls.push(q,-q); for(var k=0;k<ds.length;k++) for(var j=0;j<ls.length;j++){ var cx=c[0]-dir[1]*ls[j], cy=c[1]+dir[0]*ls[j], o=face+ds[k], x=cx+dir[0]*o, y=cy+dir[1]*o, s=sup(x,y,z+.3); if(s!=null&&Math.abs(s-z)<.15&&freeAt(x,y,z)&&freeAt(cx,cy,z)&&reach([cx,cy],[x,y],z)) return [x,y]; } return null; }
/* the capsule can slide straight there from the doorway's middle: free and floored all the way */
function reach(P,Q,z){ var L=Math.hypot(Q[0]-P[0],Q[1]-P[1]), n=Math.max(1,Math.ceil(L/.1)); for(var i=0;i<=n;i++){ var x=P[0]+(Q[0]-P[0])*i/n, y=P[1]+(Q[1]-P[1])*i/n, s=sup(x,y,z+.3); if(s==null||Math.abs(s-z)>.3||!freeAt(x,y,z)) return false; } return true; }
/* ── doors ── */
G.walls.forEach(function(W){ W.ops.forEach(function(op){ if(op.k==='window') return;
  var w=op.a1-op.a0, h=op.z1-op.z0, id=W.w.id+'@'+(op.o.a).toFixed(1); if(op.widened) out.widened++;
  if(op.plug) return;                                                   /* closed by the renderer (listed in `closed`) */
  if(op.o.st||G.st.some(function(o){ return o.k!=='elevator'&&o.fl.some(function(fl){ return A.geom.segD(op.c?op.c[0]:0,op.c?op.c[1]:0,fl.a[0],fl.a[1],fl.b[0],fl.b[1])<fl.w/2+1.2; }); })){ out.stairDoors=(out.stairDoors||0)+1; return; }     /* a stair's way on or off: walked by the stair walks below */
  if(!op.pass){ if((op.o.z||0)<=CFG.knee) fails.push({kind:'door', id:id, why:'not passable: '+h.toFixed(2)+' m high (capsule '+CFG.head+' m)'}); return; }
  out.doors++;
  if(w<2*CFG.pr+.08) fails.push({kind:'door', id:id, why:'narrower than the capsule: '+w.toFixed(2)+' m'});
  if(h<CFG.head+.05) fails.push({kind:'door', id:id, why:'lower than the capsule: '+h.toFixed(2)+' m'});
  if(!op.sg||!op.ra||!op.rb||op.ra.isVoid||op.rb.isVoid){ out.skipped.push(id+' (one side has no room)'); return; }
  var sg=op.sg, c=op.c, n=sg.n, z=W.lv.e, hw=(op.a1-op.a0)/2, la=op.passAt||0, cc=[c[0]+sg.d[0]*la,c[1]+sg.d[1]*la], pa=spot(cc,n,z,W.ht,.3), pb=spot(cc,[-n[0],-n[1]],z,W.ht,.3);          /* where the renderer found the straight way through */
  if(!pa||!pb){ fails.push({kind:'door', id:id, why:'no free floor in front of it on '+(pa?'one':'either')+' side'}); return; }
  [[pa,pb],[pb,pa]].forEach(function(pp){ [false,true].forEach(function(run){ out.doorWalks++; var r=walk(pp[0],pp[1],z,run,6,z,.6); if(!r.ok) fails.push({kind:'door', id:id, run:run, why:r.why, detail:r}); }); });
  /* and a hop in the doorway: it lands back on the same floor */
  place(c[0],c[1],z,0); if(freeAt(c[0],c[1],z)){ A.step(DT,{hop:1},1); for(var i=0;i<70;i++) A.step(DT,{},1); out.hops++; if(Math.abs(S.fz-z)>.05||S.air) fails.push({kind:'hop', id:id, why:'did not land back on the floor', z:S.fz}); }
}); });
/* ── stairs: every flight up and down, walking and running, and a hop half way ── */
G.st.forEach(function(o,si){ if(o.k==='elevator') return; o.fl.forEach(function(fl,fi){ out.stairs++; var id=(o.s.id||('st'+si))+'#'+fi, d=fl.d;
  /* where to start and stop: the farthest free floor up to 0.9 m beyond each end, at that end's height (a landing, the floor, the turn of a switchback) */
  var end=function(P,z,dir){ for(var k=9;k>=1;k--){ var x=P[0]+dir[0]*k*.1, y=P[1]+dir[1]*k*.1, s=sup(x,y,z+.3); if(s!=null&&Math.abs(s-z)<.12&&freeAt(x,y,z)) return [x,y]; } return null; };
  var bot=end(fl.a,fl.a[2],[-d[0],-d[1]]), top=end(fl.b,fl.b[2],d), zb=fl.a[2], zt=fl.b[2];
  if(!bot){ bot=[fl.a[0]+d[0]*.1,fl.a[1]+d[1]*.1]; zb=sup(bot[0],bot[1],fl.a[2]+.3); } if(!top){ top=[fl.b[0]-d[0]*.1,fl.b[1]-d[1]*.1]; zt=sup(top[0],top[1],fl.b[2]+.3); }
  if(zb==null||zt==null){ fails.push({kind:'stair', id:id, why:'no floor at an end of the flight'}); return; }
  [false,true].forEach(function(run){ out.stairWalks+=2; var up=walk(bot,top,zb,run,4+fl.L,zt,.35); if(!up.ok) fails.push({kind:'stair', id:id, dir:'up', run:run, why:up.why, detail:up});
    var dn=walk(top,bot,zt,run,4+fl.L,zb,.35); if(!dn.ok) fails.push({kind:'stair', id:id, dir:'down', run:run, why:dn.why, detail:dn}); });
  var mid=[(fl.a[0]+fl.b[0])/2,(fl.a[1]+fl.b[1])/2], zm=(fl.a[2]+fl.b[2])/2; place(mid[0],mid[1],sup(mid[0],mid[1],zm+.3)||zm,Math.atan2(d[1],d[0])); for(var q=0;q<10;q++) A.step(DT,{},1); var z0=S.fz;
  A.step(DT,{hop:1},1); for(var i=0;i<70;i++) A.step(DT,{},1); out.hops++; if(Math.abs(S.fz-z0)>.3||S.air||S.nets) fails.push({kind:'hop', id:id, why:'a hop on the stair did not land on it', z:S.fz, z0:z0});
}); });
/* ── entrances: from the street side in through the door, and back out (Luke's fall was walking in) ── */
(plan.en||[]).forEach(function(en,i){ if(!en.p) return; var id='entrance '+(en.n||en.id||i), fc=(en.fc||0)*Math.PI/180, ux=Math.cos(fc), uy=Math.sin(fc), lv=G.lv[en.l]||null, zin=lv?lv.e:null;
  var outP=null, zo=null; for(var k=30;k>=8;k--){ var x=en.p[0]+ux*k*.25, y=en.p[1]+uy*k*.25, z=sup(x,y,(zin==null?50:zin)+.4); if(z!=null&&freeAt(x,y,z)){ outP=[x,y]; zo=z; break; } }
  var inP=null; for(var k2=4;k2<=14;k2++){ var x2=en.p[0]-ux*k2*.25, y2=en.p[1]-uy*k2*.25, z2=sup(x2,y2,(zin==null?50:zin)+.4); if(z2!=null&&(zin==null||Math.abs(z2-zin)<.3)&&freeAt(x2,y2,z2)){ inP=[x2,y2]; break; } }
  if(!outP||!inP){ (out.noTerrace=out.noTerrace||[]).push(id+': no ground traced '+(outP?'inside':'outside')); return; }
  if(zin!=null&&Math.abs(zo-zin)>CFG.drop){ (out.noTerrace=out.noTerrace||[]).push(id+': the sill is '+(zin-zo).toFixed(1)+' m above the traced ground outside (no terrace or steps in the plan); from inside you stop at the threshold'); return; }
  out.entrances=(out.entrances||0)+1;
  var r1=walk(outP,inP,zo,false,10,zin,.35); if(!r1.ok) fails.push({kind:'entrance', id:id, dir:'in', why:r1.why, detail:r1});
  var r2=walk(inP,outP,zin,false,10,zo,.6); if(!r2.ok) fails.push({kind:'entrance', id:id, dir:'out', why:r2.why, detail:r2}); });
/* ── trips to cards (cards mode): N cards picked from the menu at random, each from a random free spot; arrive at the pose in front of the sign, on its floor, facing it, never stuck ── */
if(withCards){ var seed=7, rnd=function(){ seed=(seed*16807)%2147483647; return seed/2147483647; }, ids=data.order.filter(function(id){ return G.slots['card-'+id]; }), N=Math.min(+(process.env.TRIPS||40),ids.length), starts=G.rooms.filter(function(r){ return !r.isVoid&&!r.r.gp; });
  out.trips=0; out.tripWalk=0; out.tripFade=0; out.tripStuckFade=0; out.tripMaxS=0;
  for(var ti=0;ti<N;ti++){ var id=ids[Math.floor(rnd()*ids.length)], it=G.slots['card-'+id], r0=starts[Math.floor(rnd()*starts.length)], c0=[r0.ctr[0],r0.ctr[1]], f0=null;
    for(var rr=0;rr<4&&!f0;rr+=.4) for(var aa=0;aa<12;aa++){ var x=c0[0]+Math.cos(aa/12*6.283)*rr, y=c0[1]+Math.sin(aa/12*6.283)*rr, z=sup(x,y,r0.l.e+.3); if(z!=null&&Math.abs(z-r0.l.e)<.15&&freeAt(x,y,z)){ f0=[x,y,z]; break; } }
    if(!f0) continue; place(f0[0],f0[1],f0[2],rnd()*6.283); var nets0=S.nets, res0=S.rescues; A.go(id); var t=0; while(A.nav().on&&t<90){ A.step(DT,{},1); t+=DT; }
    var L=A.nav().last||{}, to=A.arrival('card-'+id), d=Math.hypot(S.x-to.x,S.y-to.y), face=Math.atan2(it.s.p[1]-S.y,it.s.p[0]-S.x)-S.yaw; while(face>Math.PI) face-=2*Math.PI; while(face<-Math.PI) face+=2*Math.PI;
    out.trips++; if(L.mode==='walk') out.tripWalk++; else out.tripFade++; if(L.stuckFade) out.tripStuckFade++; out.tripMaxS=Math.max(out.tripMaxS,+t.toFixed(1));
    var why=!L.arrived?'never arrived ('+(L.mode||'?')+(L.why?', '+L.why:'')+')':d>.5?'stopped '+d.toFixed(2)+' m from the spot':Math.abs(S.fz-it.room.l.e)>.2?'wrong floor':Math.abs(face)>.21?'not facing the sign ('+(face*57.3).toFixed(0)+' deg)':S.nets>nets0?'fell':S.rescues>res0?'stuck in geometry':'';
    if(why) fails.push({kind:'trip', id:id, why:why, from:f0.map(function(v){ return +v.toFixed(1); }), mode:L.mode, len:+(L.len||0).toFixed(1)}); } }
/* ── low obstacles (Luke, 2026-10-29: "low obstacles, realistic height"): a hop clears a bench or a rope barrier (top <= 1.0 m, knee to waist) and a walker that hops lands past it;
   it never clears a wall, a rail or a display case (nor the 1.1 m plinth). Each obstacle is approached from 8 directions, at a walk and a run, hopping at three distances;
   "cleared" = ends beyond the far side, never rescued, never netted. ── */
out.obst={low:{n:0,cleared:0,byWalk:0,byRun:0}, high:{n:0,cleared:0}, wall:{n:0,cleared:0}, bench:{n:0,cleared:0}, rope:{n:0,cleared:0}, boxed:[]}; var obFails=[];
/* walk from `st` along `dir`, hopping once the capsule is `hopAt` m short of the obstacle's near face (tIn, metres along the line from `st`); cleared = the centre is past its far face (tOut), on the ground again, still on the line */
function hopRun(dir,st,z,run,hopAt,tIn,tOut,maxT){ place(st[0],st[1],z,Math.atan2(dir[1],dir[0])); var nets0=S.nets, res0=S.rescues, t=0, hopped=false, lat=0;
  while(t<maxT){ var d=(S.x-st[0])*dir[0]+(S.y-st[1])*dir[1], k={f:1,run:run?1:0}; if(!hopped&&d>=tIn-CFG.pr-hopAt){ k.hop=1; hopped=true; } A.step(DT,k,1); t+=DT;
    lat=Math.max(lat,Math.abs((S.x-st[0])*dir[1]-(S.y-st[1])*dir[0])); d=(S.x-st[0])*dir[0]+(S.y-st[1])*dir[1];
    if(d>tOut+.08&&hopped&&!S.air) return {ok:lat<.2&&S.rescues===res0&&S.nets===nets0, d:d, lat:lat}; }
  return {ok:false}; }
function spotOk(x,y,z){ var s=sup(x,y,z+.3); return s!=null&&Math.abs(s-z)<.15&&freeAt(x,y,z); }
/* where the line st + t*dir enters and leaves a box prim (slab test in the box's own axes) */
function slab(pr,st,dir){ var ox=st[0]-pr.x, oy=st[1]-pr.y, o=[ox*pr.c+oy*pr.s,-ox*pr.s+oy*pr.c], d=[dir[0]*pr.c+dir[1]*pr.s,-dir[0]*pr.s+dir[1]*pr.c], h=[pr.hx,pr.hy], t0=-1e9, t1=1e9;
  for(var i=0;i<2;i++){ if(Math.abs(d[i])<1e-9){ if(Math.abs(o[i])>h[i]) return null; continue; } var a=(-h[i]-o[i])/d[i], b=(h[i]-o[i])/d[i]; t0=Math.max(t0,Math.min(a,b)); t1=Math.min(t1,Math.max(a,b)); } return t0<t1?[t0,t1]:null; }
Object.keys(G.fxs).forEach(function(id){ var F=G.fxs[id], f=F.f, pr=G.prims.filter(function(q){ return q.tag===id&&q.k==='box'; })[0]; if(!pr) return;
  var h=pr.z1-pr.z0, kind=h<=1.0?'low':'high'; if(h<.3) return; var z=F.l.e, cleared=false, tried=0, wk=false, rn=false, DIRS=[[pr.c,pr.s],[-pr.s,pr.c],[-pr.c,-pr.s],[pr.s,-pr.c]];
  for(var a0=0;a0<8;a0++) DIRS.push([Math.cos(a0*Math.PI/4),Math.sin(a0*Math.PI/4)]);
  for(var a=0;a<DIRS.length;a++){ var dir=DIRS[a], st=[pr.x-dir[0]*(pr.R+2.6),pr.y-dir[1]*(pr.R+2.6)], sl=slab(pr,st,dir); if(!sl) continue; var tIn=sl[0], tOut=sl[1], en=[st[0]+dir[0]*(tOut+1.0),st[1]+dir[1]*(tOut+1.0)],
      pre=[st[0]+dir[0]*(tIn-.4),st[1]+dir[1]*(tIn-.4)], post=[st[0]+dir[0]*(tOut+.4),st[1]+dir[1]*(tOut+.4)];
    if(!spotOk(st[0],st[1],z)||!spotOk(en[0],en[1],z)||!reach(st,pre,z)||!reach(post,en,z)) continue; tried++;          /* a clear run-up to it and a clear landing beyond it */
    [false,true].forEach(function(run){ var ats=run?[1.6,2.2,2.8]:[.5,.8,1.1]; for(var q=0;q<ats.length;q++){ var r=hopRun(dir,st,z,run,ats[q],tIn,tOut,7); if(r.ok){ cleared=true; if(run) rn=true; else wk=true; return; } } }); }
  if(!tried) return; var B=out.obst[kind]; B.n++; if(cleared) B.cleared++; if(kind==='low'){ if(wk) B.byWalk++; if(rn) B.byRun++; var C=out.obst[/^rope/.test(id)?'rope':'bench']; C.n++; if(cleared) C.cleared++; else out.obst.boxed.push(id); }          /* not cleared: boxed in by furniture or a wall on every line */
  if(kind==='high'&&cleared) obFails.push({kind:'obstacle', id:id, what:f.k, h:+h.toFixed(2), why:'a hop CLEARED a tall obstacle (case or plinth)'}); });
/* walls and rails: sampled mid-wall, perpendicular, only where plain walking is stopped (not a door); a hop must not get through */
var wi=0; G.prims.forEach(function(q,i){ if(!q.wall||q.k!=='seg'||wi>=80||(i%7)) return; var L=Math.hypot(q.bx-q.ax,q.by-q.ay); if(L<1.2) return; var mx=(q.ax+q.bx)/2, my=(q.ay+q.by)/2, nx=-(q.by-q.ay)/L, ny=(q.bx-q.ax)/L, z=q.z0;
  var lv=G.lvs.filter(function(l){ return Math.abs(l.e-z)<.05; })[0]; if(!lv) return; var st=[mx-nx*2,my-ny*2], en=[mx+nx*2,my+ny*2]; if(!spotOk(st[0],st[1],z)||!spotOk(en[0],en[1],z)) return;
  place(st[0],st[1],z,Math.atan2(ny,nx)); for(var s=0;s<150;s++){ A.step(DT,{f:1},1); } if(((S.x-st[0])*nx+(S.y-st[1])*ny)>3.2) return; wi++; out.obst.wall.n++;
  var got=false; [false,true].forEach(function(run){ [.5,1.1,1.8,2.6].forEach(function(at){ var r=hopRun([nx,ny],st,z,run,at,2-(q.r||.1),2+(q.r||.1),3); if(r.ok) got=true; }); });
  if(got){ out.obst.wall.cleared++; obFails.push({kind:'obstacle', id:q.tag||('wall#'+i), what:'wall', h:+(q.z1-q.z0).toFixed(2), why:'a hop got through a wall'}); } });
fails.push.apply(fails,obFails);
out.cuts=G.cuts.length; out.stairCuts=(G.scuts||[]).length; out.closed=G.dead.map(function(d){ return d.w+'@'+d.a.toFixed(1)+' (onto '+d.by+')'; }); out.clipped=G.clipped||0; out.fails=fails; out.nets=S.nets; out.capsule={r:CFG.pr, h:CFG.head, minDoor:CFG.minDoor};
console.log(JSON.stringify(out));
