"""Part A of the first-person ride (palace_ride.py): utilities, preferences, and the model of a leg (path, sections, stops, tunnels, timeline)."""

JS_A = r"""
var E=null, NS='http://www.w3.org/2000/svg';
var LS_VIEW='alto-palace-ride-view', LS_SND='alto-palace-ride-sound';
var STEP=5;                         /* map units between the samples of a ride's path */
var NEARZ=1.8, FARZ=1500, VEX=1.15, FOGD=950;
/* walking legs: as before 1.9.100 (WALK_V = the old fast pace; 1.9.100 shipped a person's 5 m/s and a ride crawled) up to WALK_FULL units; only the part of a longer walk beyond that is compressed (the whole ride is still held to
   6-30 s below, so a long walk, or a transit ride with a walk in it, still plays faster than a person walks - a ride is a summary, free roaming is the real pace) */
var WALK_V=150, WALK_FULL=130;
var RING_HZ=2.4, MAX_FLASH_HZ=3, BAR_HZ=.9, HUE_DPS=38;     /* photosensitivity: rings never pass faster than RING_HZ, nothing pulses faster than 1 Hz */
var VEH={
  walk :{vmax:150,  eye:2.15, off:14,  fil:22,  ease:.18},     /* eye 2.15 units = 1.65 m at UM=1.3 units a metre; vmax is only the ceiling of a very long walk, see WALK_V */
  metro:{vmax:1500, eye:2.5,  off:0,   fil:110, ease:1},
  rail :{vmax:1700, eye:3.0,  off:0,   fil:120, ease:1},
  tram :{vmax:760,  eye:2.7,  off:0,   fil:46,  ease:1},
  bus  :{vmax:560,  eye:3.6,  off:5.5, fil:46,  ease:1},
  car  :{vmax:900,  eye:2.5,  off:5.5, fil:50,  ease:1}
};
/* the underground part of each known line, by its stops (the data marks no metro line's tunnel; the trolley's own tunnel pieces are line.u) */
var UGS={
  mfl:{names:['2nd Street','5th Street','8th Street','11th Street','13th Street','15th Street','30th Street','34th Street','40th Street','Spring Garden'], frac:.4},
  bsl:{all:1, frac:.5}, brs:{all:1, frac:.5},
  pat:{names:['15th-16th & Locust','12th-13th & Locust','9th-10th & Locust','8th & Market','Franklin Square'], frac:.35},
  trl:{names:['13th Street','15th Street','19th Street','22nd Street','30th Street','33rd Street','36th Street','37th Street','36th Street Portal','40th Street Portal'], frac:.5},
  rr :{names:['Jefferson Station','Suburban Station'], frac:.6}
};
function clamp(v,a,b){ return v<a?a:v>b?b:v; }
function mix(a,b,t){ return a+(b-a)*t; }
function sstep(a,b,v){ var t=clamp((v-a)/(b-a),0,1); return t*t*(3-2*t); }
function hash(n){ n=n|0; n=(n^61)^(n>>>16); n=(n+(n<<3))|0; n^=n>>>4; n=Math.imul(n,0x27d4eb2d); n^=n>>>15; return (n>>>0)/4294967296; }
function hashXY(x,y){ return hash(Math.round(x*7.13)*31+Math.round(y*3.77)); }
function rgbOf(c){ c=String(c||'').trim(); var m;
  if(c[0]==='#'){ var h=c.slice(1); if(h.length===3) h=h[0]+h[0]+h[1]+h[1]+h[2]+h[2]; return [parseInt(h.slice(0,2),16)||0, parseInt(h.slice(2,4),16)||0, parseInt(h.slice(4,6),16)||0]; }
  m=/rgba?\(([^)]+)\)/.exec(c); if(m){ var a=m[1].split(','); return [parseFloat(a[0])|0, parseFloat(a[1])|0, parseFloat(a[2])|0]; }
  return [128,128,140]; }
function lumOf(r){ return (.2126*r[0]+.7152*r[1]+.0722*r[2])/255; }
function css(r,a){ return a==null||a>=1?'rgb('+(r[0]|0)+','+(r[1]|0)+','+(r[2]|0)+')':'rgba('+(r[0]|0)+','+(r[1]|0)+','+(r[2]|0)+','+a.toFixed(3)+')'; }
function mixC(a,b,t){ return [a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t, a[2]+(b[2]-a[2])*t]; }
function hsl(h,s,l,a){ h=((h%360)+360)%360; var c=(1-Math.abs(2*l-1))*s, x=c*(1-Math.abs((h/60)%2-1)), m=l-c/2, r=0,g=0,b=0;
  if(h<60){r=c;g=x;}else if(h<120){r=x;g=c;}else if(h<180){g=c;b=x;}else if(h<240){g=x;b=c;}else if(h<300){r=x;b=c;}else{r=c;b=x;}
  return css([(r+m)*255,(g+m)*255,(b+m)*255], a); }
function hueOf(c){ var r=rgbOf(c), mx=Math.max(r[0],r[1],r[2]), mn=Math.min(r[0],r[1],r[2]), d=mx-mn; if(!d) return 210; var h;
  if(mx===r[0]) h=((r[1]-r[2])/d)%6; else if(mx===r[1]) h=(r[2]-r[0])/d+2; else h=(r[0]-r[1])/d+4; return (h*60+360)%360; }
function pref(){ try{ var v=localStorage.getItem(LS_VIEW); if(v==='map'||v==='fp') return v; }catch(x){} return 'fp'; }
function setPref(v){ try{ localStorage.setItem(LS_VIEW, v); }catch(x){} }
function sndOn(){ try{ return localStorage.getItem(LS_SND)!=='off'; }catch(x){ return true; } }
function reduced(){ return !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches); }
function dark(){ return document.documentElement.classList.contains('dark'); }
function TXok(){ return window._palTRx && window._palTRx.has && window._palTRx.has(); }
function lineOf(id){ return TXok()?window._palTRx.lineOf(id):null; }
function stopsAll(){ return TXok()?window._palTRx.stops():[]; }

/* ── a path: corners rounded, sampled every STEP ── */
function parseD(d){ var v=String(d||'').match(/-?\d*\.?\d+(?:e-?\d+)?/g)||[], pts=[]; for(var i=0;i+1<v.length;i+=2) pts.push([parseFloat(v[i]), parseFloat(v[i+1])]); return pts; }
function tidy(pts){ var o=[];
  pts.forEach(function(p){ var q=o[o.length-1]; if(q && Math.hypot(p[0]-q[0],p[1]-q[1])<1.2) return;
    var r=o[o.length-2]; if(r && q){ var ax=q[0]-r[0], ay=q[1]-r[1], bx=p[0]-q[0], by=p[1]-q[1], la=Math.hypot(ax,ay), lb=Math.hypot(bx,by);
      if(la>0 && lb>0 && (ax*bx+ay*by)/(la*lb)<-.98){ o.pop(); } }              /* a spike back along itself */
    o.push(p); });
  return o; }
function fillet(pts, R){
  if(pts.length<3) return pts.map(function(p){ return [p[0],p[1]]; });
  var o=[[pts[0][0],pts[0][1]]];
  for(var i=1;i<pts.length-1;i++){ var P0=pts[i-1], P1=pts[i], P2=pts[i+1], a=Math.hypot(P0[0]-P1[0],P0[1]-P1[1]), b=Math.hypot(P2[0]-P1[0],P2[1]-P1[1]), r=Math.min(R, a*.5, b*.5);
    if(r<2){ o.push([P1[0],P1[1]]); continue; }
    var ax=P1[0]+(P0[0]-P1[0])/a*r, ay=P1[1]+(P0[1]-P1[1])/a*r, bx=P1[0]+(P2[0]-P1[0])/b*r, by=P1[1]+(P2[1]-P1[1])/b*r;
    for(var k=0;k<=7;k++){ var t=k/7, u=1-t; o.push([u*u*ax+2*u*t*P1[0]+t*t*bx, u*u*ay+2*u*t*P1[1]+t*t*by]); } }
  o.push([pts[pts.length-1][0], pts[pts.length-1][1]]); return o; }
/* append a rounded section to the dense path (X,Y,S arrays), resampled every STEP; returns [s0,s1] */
function appendDense(D, pts){
  var s0=D.L, first=D.X.length===0;
  var acc=0, i, segs=[];
  for(i=0;i+1<pts.length;i++){ var l=Math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1]); if(l>1e-6) segs.push([pts[i],pts[i+1],l]); }
  var tot=0; segs.forEach(function(g){ tot+=g[2]; });
  if(first){ D.X.push(pts[0][0]); D.Y.push(pts[0][1]); D.S.push(0); }
  var n=Math.max(1, Math.round(tot/STEP)), si=0, base=0;
  for(var k=1;k<=n;k++){ var d=tot*k/n; while(si<segs.length-1 && base+segs[si][2]<d){ base+=segs[si][2]; si++; }
    var g=segs[si], t=g? (d-base)/g[2] : 0; if(!g) break;
    D.X.push(g[0][0]+(g[1][0]-g[0][0])*t); D.Y.push(g[0][1]+(g[1][1]-g[0][1])*t); D.L+=tot/n; D.S.push(D.L); }
  return [s0, D.L]; }
function pathAt(D, s, out){ s=clamp(s,0,D.L); var i=Math.min(D.X.length-2, Math.max(0, Math.floor(s/((D.L||1)/(D.X.length-1)))));
  while(i>0 && D.S[i]>s) i--; while(i<D.X.length-2 && D.S[i+1]<s) i++;
  var t=(s-D.S[i])/((D.S[i+1]-D.S[i])||1); out.x=D.X[i]+(D.X[i+1]-D.X[i])*t; out.y=D.Y[i]+(D.Y[i+1]-D.Y[i])*t; return out; }
var _pa={x:0,y:0}, _pb={x:0,y:0};
function headAt(D, s, la){ pathAt(D, s-la, _pa); pathAt(D, s+la, _pb); if(Math.hypot(_pb.x-_pa.x,_pb.y-_pa.y)<1e-6){ pathAt(D, s, _pa); pathAt(D, s+STEP*3, _pb); if(Math.hypot(_pb.x-_pa.x,_pb.y-_pa.y)<1e-6){ pathAt(D, s-STEP*3, _pa); pathAt(D, s, _pb); } }
  return Math.atan2(_pb.y-_pa.y, _pb.x-_pa.x); }
function nearestS(D, x, y, lo, hi){ var best=1e18, bs=0; for(var i=0;i<D.X.length;i++){ var s=D.S[i]; if(s<lo||s>hi) continue; var d=(D.X[i]-x)*(D.X[i]-x)+(D.Y[i]-y)*(D.Y[i]-y); if(d<best){ best=d; bs=s; } } return {s:bs, d:Math.sqrt(best)}; }

/* ── which stretches of a ride section run underground ── */
function ugNear(line, x, y, r){ var u=line&&line.u; if(!u) return false; for(var i=0;i<u.length;i++){ var a=u[i]; for(var k=0;k+3<a.length;k+=2){ var ax=a[k], ay=a[k+1], bx=a[k+2], by=a[k+3], dx=bx-ax, dy=by-ay, L2=dx*dx+dy*dy||1e-9, t=clamp(((x-ax)*dx+(y-ay)*dy)/L2,0,1);
  if(Math.hypot(ax+t*dx-x, ay+t*dy-y)<r) return true; } } return false; }
function ugStop(line, st, idx, ls){
  if(!line||!st) return false; var T=UGS[line.id];
  if(T){ if(T.all) return true; return (T.names||[]).indexOf(st.n)>=0; }
  if(line.u && line.u.length) return ugNear(line, st.x, st.y, 70);
  if(line.k==='metro'){ var ord=line.s||[], pos=ord.indexOf(idx); return ord.length>=6 && pos>=2 && pos<=ord.length-3; }     /* an unknown metro: tunnel through the middle, open at the ends */
  return false; }
/* spans [a,b] of the section's dense path [s0,s1] that are underground; stops = [{s,n,idx}] on it (board and alight included) */
function ugSpans(sec, D){
  var line=sec.line; if(!line||sec.veh==='bus'||sec.veh==='walk'||sec.veh==='car') return [];
  var spans=[], st=sec.stops, T=UGS[line.id], frac=T&&T.frac!=null?T.frac:.5, all=stopsAll();
  if(line.u && line.u.length && !T){                                  /* the trolley: its own tunnel pieces, sampled along the path */
    var on=null; for(var s=sec.s0; s<=sec.s1; s+=10){ pathAt(D,s,_pa); var u=ugNear(line,_pa.x,_pa.y,26);
      if(u && on==null) on=s; if(!u && on!=null){ if(s-on>=60) spans.push([on,s]); on=null; } }
    if(on!=null && sec.s1-on>=60) spans.push([on,sec.s1]);
    return spans; }
  var f=st.map(function(q){ return ugStop(line, all[q.idx]||{n:q.n}, q.idx); });
  for(var i=0;i<st.length;i++){ var a=st[i], b=st[i+1];
    if(i===0 && f[0]) spans.push([sec.s0, a.s+ (b? 0:0)]);
    if(!b){ if(f[i]) spans.push([a.s, sec.s1]); continue; }
    if(f[i]&&f[i+1]) spans.push([a.s,b.s]); else if(f[i]) spans.push([a.s, a.s+(b.s-a.s)*(/portal/i.test(a.n)?0:frac)]); else if(f[i+1]) spans.push([b.s-(b.s-a.s)*(/portal/i.test(b.n)?0:frac), b.s]); }
  /* merge */
  spans.sort(function(p,q){ return p[0]-q[0]; }); var m=[];
  spans.forEach(function(p){ var l=m[m.length-1]; if(l && p[0]<=l[1]+2) l[1]=Math.max(l[1],p[1]); else m.push([p[0],p[1]]); });
  return m.filter(function(p){ return p[1]-p[0]>=30; }); }

/* ── a leg into a model: sections of one kind of travel each on one dense path ── */
function colOf(l){ try{ return E.tubeCol(l.c); }catch(x){ return l.c||'#888'; } }
function planFor(leg, mode){ if(leg.opt && leg.opt.legs && leg.opt.legs.length) return leg.opt;
  try{ var p=window._palDir&&window._palDir.legPlan?window._palDir.legPlan(leg.a, leg.b, mode):null; if(p&&p.legs&&p.legs.length) return p; }catch(x){} return null; }
function rawSections(leg, rev, mode){
  var secs=[], opt=planFor(leg, mode);
  if(opt){ opt.legs.forEach(function(l){ var pts=(l.pts||[]).slice(); if(pts.length<2) return;
      var veh='walk', ln=null;
      if(mode==='drive') veh='car';
      else if(l.k==='ride' && l.l){ ln=lineOf(l.l); veh=ln?(ln.k==='metro'?'metro':ln.k==='tram'?'tram':ln.k==='bus'?'bus':'rail'):'walk'; }
      secs.push({veh:veh, line:ln, color:l.color||(ln?colOf(ln):'#888'), pts:pts, hw:mode==='drive'&&!!l.l, board:l.board, alight:l.alight, hwName:(l.line&&l.line.n)||''}); }); }
  if(!secs.length){ var pts2=parseD(leg.d); if(pts2.length>=2){ var ln2=null, veh2=mode==='drive'?'car':mode==='walk'?'walk':'walk';
      if(mode==='transit' && leg.lines && leg.lines.length){ ln2=lineOf(leg.lines[0]); if(ln2) veh2=ln2.k==='metro'?'metro':ln2.k==='tram'?'tram':ln2.k==='bus'?'bus':'rail'; }
      secs.push({veh:veh2, line:ln2, color:(ln2?colOf(ln2):leg.color)||'#888', pts:pts2, board:null, alight:null}); } }
  if(rev){ secs.reverse(); secs.forEach(function(s){ s.pts=s.pts.slice().reverse(); var b=s.board; s.board=s.alight; s.alight=b; }); }
  return secs; }
function stopNameNear(x, y){ var best=null, bd=90*90; stopsAll().forEach(function(s,i){ var d=(s.x-x)*(s.x-x)+(s.y-y)*(s.y-y); if(d<bd){ bd=d; best={n:s.n, idx:i}; } }); return best; }
function buildModel(leg, rev, mode){
  var raw=rawSections(leg, rev, mode); if(!raw.length) return null;
  return modelFromRaw(raw, {leg:leg, rev:rev, mode:mode, a:rev?leg.b:leg.a, b:rev?leg.a:leg.b}); }
function modelFromRaw(raw, meta){
  var D={X:[],Y:[],S:[],L:0}, last=null, secs=[];
  raw.forEach(function(sec){
    var pts=tidy(sec.pts); if(last && pts.length){ var g=Math.hypot(pts[0][0]-last[0], pts[0][1]-last[1]); if(g>1.5) pts.unshift([last[0],last[1]]); }
    if(pts.length<2) return;
    var v=VEH[sec.veh]||VEH.walk, rr=appendDense(D, fillet(pts, v.fil)); last=[pts[pts.length-1][0], pts[pts.length-1][1]];
    sec.s0=rr[0]; sec.s1=rr[1]; if(sec.s1-sec.s0<6 && secs.length) { return; }
    sec.stops=[]; secs.push(sec); });
  if(!secs.length || D.L<8) return null;
  /* the stops each ride section calls at, in order along its path */
  var all=stopsAll();
  secs.forEach(function(sec){
    if(!sec.line || sec.veh==='walk' || sec.veh==='car') { if(sec.hw){ sec.stops=[{s:sec.s0,n:sec.board&&sec.board.n||'',idx:-1,end:1},{s:sec.s1,n:sec.alight&&sec.alight.n||'',idx:-1,end:1}]; } return; }
    var L=sec.line, cand=[];
    all.forEach(function(st,i){ if(st.l.indexOf(L.id)<0) return; var q=nearestS(D, st.x, st.y, sec.s0, sec.s1); if(q.d<300) cand.push({s:q.s, n:st.n, idx:i}); });
    cand.sort(function(a,b){ return a.s-b.s; });
    var o=[{s:sec.s0, n:(sec.board&&sec.board.n)||(cand[0]&&cand[0].n)||'', idx:cand[0]?cand[0].idx:-1, end:1}];
    cand.forEach(function(c){ if(c.s>sec.s0+40 && c.s<sec.s1-40 && c.s>o[o.length-1].s+40) o.push(c); });
    o.push({s:sec.s1, n:(sec.alight&&sec.alight.n)||(cand.length&&cand[cand.length-1].n)||'', idx:cand.length?cand[cand.length-1].idx:-1, end:1});
    /* the first and last take the name/index of the stop at the board/alight point when the plan knows it */
    if(sec.board&&sec.board.x!=null){ var b=stopNameNear(sec.board.x, sec.board.y); if(b){ o[0].n=sec.board.n||b.n; o[0].idx=b.idx; } }
    if(sec.alight&&sec.alight.x!=null){ var a=stopNameNear(sec.alight.x, sec.alight.y); if(a){ o[o.length-1].n=sec.alight.n||a.n; o[o.length-1].idx=a.idx; } }
    sec.stops=o; });
  secs.forEach(function(sec){ sec.ug=ugSpans(sec, D); });
  trimEnds(secs, D, meta);
  var M={D:D, secs:secs, rev:!!meta.rev, mode:meta.mode, leg:meta.leg, L:D.L, a:meta.a, b:meta.b};
  timeline(M); return M; }

/* the ride starts at the door of the first building and ends at the door of the last, not in the middle of its lot */
function inRing(x,y,r){ var c=false, n=r.length/2; for(var i=0,j=n-1;i<n;j=i++){ var xi=r[2*i], yi=r[2*i+1], xj=r[2*j], yj=r[2*j+1]; if((yi>y)!==(yj>y) && x<(xj-xi)*(y-yi)/(yj-yi)+xi) c=!c; } return c; }
function lotRing(id, grow){ try{ var L=id!=null?E.lot(E.P.at[E.bOf(id)]):null; if(!L) return null; var G=grow||0; return turnedRing([L[0],L[1],L[2]+2*G,L[3]+2*G,L[4]]); }catch(x){ return null; } }
function trimEnds(secs, D, meta){
  var ra=lotRing(meta.a, 24), rb=lotRing(meta.b, 30), first=secs[0], last=secs[secs.length-1], s, o={x:0,y:0};
  if(ra){ for(s=first.s0; s<first.s1-12; s+=STEP){ pathAt(D,s,o); if(!inRing(o.x,o.y,ra)) break; } if(s>first.s0 && s<first.s1-12) first.s0=s; }
  if(rb){ for(s=last.s1; s>last.s0+12; s-=STEP){ pathAt(D,s,o); if(!inRing(o.x,o.y,rb)) break; } if(s<last.s1 && s>last.s0+12) last.s1=s; } }

/* ── time: stop-to-stop spans with soft starts and stops, a dwell at every stop; the whole ride 6-30 s ── */
function timeline(M){
  var ev=[], t=0;
  function span(s0,s1,veh){ var v=VEH[veh]||VEH.walk, D=Math.abs(s1-s0), T=Math.max(.45, D/(v.vmax*(v.ease>=1?.72:.95)));
    var tf=T, ts=0; if(veh==='walk'){ ts=Math.max(.45, Math.min(D,WALK_FULL)/(WALK_V*.95)+Math.max(0,D-WALK_FULL)/(v.vmax*.95)); T=ts; }
    ev.push({k:'move',t0:t,t1:t+T,s0:s0,s1:s1,veh:veh,ease:v.ease,vmax:v.vmax,tf:tf,ts:ts}); t+=T; }
  function dwell(s,kind,T,name,idx,si){ ev.push({k:'dwell',t0:t,t1:t+T,s0:s,s1:s,kind:kind,name:name,idx:idx,sec:si}); t+=T; }
  var si0=0;
  M.secs.forEach(function(sec,si){
    var ride=!!sec.line && sec.veh!=='walk' && sec.veh!=='car';
    if(ride){ dwell(sec.s0,'board',1.15,(sec.stops[0]||{}).n||'',(sec.stops[0]||{}).idx,si);
      for(var i=0;i+1<sec.stops.length;i++){ span(sec.stops[i].s, sec.stops[i+1].s, sec.veh);
        if(i+2<sec.stops.length) dwell(sec.stops[i+1].s,'stop',1.05,sec.stops[i+1].n,sec.stops[i+1].idx,si);
        else dwell(sec.s1,'alight',.95,sec.stops[i+1].n,sec.stops[i+1].idx,si); } }
    else span(sec.s0, sec.s1, sec.veh);
    if(si===0 && ev.length && ev[0].k==='move') { /* a breath at the start */ ev.unshift({k:'dwell',t0:0,t1:.35,s0:sec.s0,s1:sec.s0,kind:'start',name:'',sec:0}); for(var q=1;q<ev.length;q++){ ev[q].t0+=.35; ev[q].t1+=.35; } t+=.35; } });
  var sEnd=M.secs[M.secs.length-1].s1; ev.push({k:'dwell',t0:t,t1:t+.5,s0:sEnd,s1:sEnd,kind:'end',name:'',sec:M.secs.length-1}); t+=.5;
  /* a person's pace on foot where the 30 s allow it: only when the walking would push the ride past 30 s are its walks (and only they) sped up, no further than the old fast pace (tf) -
     so a transit ride with a long walk in it keeps its vehicles at their pace instead of squeezing everything, and a short walk is a real walk */
  var sS=0, sF=0; ev.forEach(function(e){ if(e.k==='move' && e.ts){ sS+=e.ts; sF+=e.tf; } });
  if(t>30 && sS>0){ var f=clamp(30-(t-sS), sF, sS)/sS, tt=0;
    ev.forEach(function(e){ var d=e.t1-e.t0; if(e.k==='move' && e.ts) d=Math.max(e.tf, e.ts*f); e.t0=tt; tt+=d; e.t1=tt; }); t=tt; }
  var k=clamp(t,M.minT||6,30)/t; if(Math.abs(k-1)>1e-3){ ev.forEach(function(e){ e.t0*=k; e.t1*=k; }); t*=k; }
  M.ev=ev; M.T=t; M._i=0; }
function evalAt(M, t){
  var ev=M.ev, i=M._i; if(i>=ev.length || ev[i].t0>t) i=0; while(i<ev.length-1 && ev[i].t1<=t) i++; M._i=i;
  var e=ev[i], o=M._st||(M._st={}); o.ev=e; o.done=t>=M.T;
  if(e.k==='dwell'){ o.s=e.s0; o.v=0; o.u=clamp((t-e.t0)/((e.t1-e.t0)||1),0,1); o.dwell=e; o.sec=e.sec; o.veh=null; o.vmax=0; return o; }
  var u=clamp((t-e.t0)/((e.t1-e.t0)||1),0,1), T=e.t1-e.t0, f, df;
  if(e.ease>=1){ f=u*u*u*(u*(6*u-15)+10); df=30*u*u*(u-1)*(u-1); }
  else { var a=e.ease, F, v; if(u<a){ F=u*u/(2*a); v=u/a; } else if(u>1-a){ F=1-1.5*a+a/2-(1-u)*(1-u)/(2*a); v=(1-u)/a; } else { F=a/2+(u-a); v=1; } f=F/(1-a); df=v/(1-a); }
  o.s=e.s0+(e.s1-e.s0)*f; o.v=Math.abs(e.s1-e.s0)*df/T; o.u=u; o.dwell=null; o.veh=e.veh; o.vmax=e.vmax;
  var sec=0; for(var q=0;q<M.secs.length;q++){ if(o.s>=M.secs[q].s0-.01) sec=q; } o.sec=sec; return o; }
"""
