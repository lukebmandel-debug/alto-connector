"""Part D of the first-person ride: the overlay, the frame loop, the camera, and the hooks the transit panel calls."""

JS_D = r"""
/* ── the overlay and the frame loop ── */
var R={ov:null, cv:null, ctx:null, chip:null, live:null, M:null, W:null, PAL:null, t:0, last:0, raf:0, playing:false, cb:null, saved:null, pend:0, active:false,
  w:0, h:0, dpr:1, yaw:null, ms:0, frames:0, worst:0, lastEv:null, hold:false, fade:0, sig:'', mode:'transit', rate:1, line:null, snd:null, ac:null, tun:0, shown:false};
function lift(M, s){ var l=0; (M._lifts||[]).forEach(function(g){ var v=g[2]*sstep(g[0]-g[3],g[0]+g[3],s)*sstep(g[1]+g[3],g[1]-g[3],s); if(v>l) l=v; }); return l; }
function ugAlpha(M, s){ var a=0, ahead=-1, exit=-1; (M._ug||[]).forEach(function(g){ var sec=M.secs[g[2]], inS=g[0]<=sec.s0+.5, outS=g[1]>=sec.s1-.5;
    var v=(inS&&s>=g[0]?1:sstep(g[0]-14,g[0]+2,s))*(outS?(s<=g[1]+.01?1:0):(1-sstep(g[1]-6,g[1]+10,s))); if(v>a) a=v; if(g[0]>s+.5 && !inS && (ahead<0||g[0]<ahead)) ahead=g[0]; if(s>=g[0]-14 && s<g[1] && !outS) exit=g[1]; });
  return {a:a, ahead:ahead, exit:exit}; }
function pullAt(sec, s){ var p=0; (sec.stops||[]).forEach(function(st){ var d=Math.abs(s-st.s); p=Math.max(p, 1-sstep(8,120,d)); }); return p; }
function angLerp(a,b,t){ var d=Math.atan2(Math.sin(b-a),Math.cos(b-a)); return a+d*t; }
function finishModel(M){
  M._ug=[]; M._lifts=[];
  M.secs.forEach(function(sec,si){ sec.ug.forEach(function(g){ M._ug.push([g[0],g[1],si]); });
    if(sec.veh==='metro'){ var cur=sec.s0; sec.ug.concat([[sec.s1,sec.s1]]).forEach(function(g){ if(g[0]-cur>=40) M._lifts.push([cur,g[0],15,80]); cur=Math.max(cur,g[1]); }); } });
  return M; }
function sizeCheck(){ var vw=window.innerWidth||document.documentElement.clientWidth, vh=window.innerHeight||document.documentElement.clientHeight;
  var dpr=Math.min(window.devicePixelRatio||1, Math.sqrt((glOk()?2.3e6:1.9e6)/(vw*vh))); dpr=Math.max(.7, dpr);
  if(vw!==R.w || vh!==R.h || Math.abs(dpr-R.dpr)>.02){ R.w=vw; R.h=vh; R.dpr=dpr; R.cv.width=Math.round(vw*dpr); R.cv.height=Math.round(vh*dpr); glSize(R.cv.width,R.cv.height); } }
function ensureOverlay(){
  if(R.ov) return;
  var ov=document.createElement('div'); ov.id='pal-ride'; ov.setAttribute('role','region'); ov.setAttribute('aria-label','First-person ride');
  ov.innerHTML='<canvas class="pr-cv" aria-hidden="true"></canvas><div class="pr-chip" aria-hidden="true"></div><div class="pr-btns"><button type="button" data-ride="view"></button><button type="button" data-ride="snd"></button><button type="button" data-ride="exit">Exit ride · Esc</button></div><div class="pr-live" aria-live="polite"></div>';
  document.body.appendChild(ov); R.ov=ov; R.cv=ov.querySelector('canvas'); R.ctx=R.cv.getContext('2d'); R.chip=ov.querySelector('.pr-chip'); R.live=ov.querySelector('.pr-live'); glAttach(ov); labelBtns(); }
function labelBtns(){ var fp=pref()==='fp';
  [].forEach.call(document.querySelectorAll('[data-ride=view]'), function(b){ b.textContent=fp?'Map view · V':'Ride view · V'; b.setAttribute('aria-pressed', String(fp)); });
  [].forEach.call(document.querySelectorAll('[data-ride=snd]'), function(b){ b.textContent=sndOn()?'Sound on':'Sound off'; }); }
function openOv(){ ensureOverlay(); if(R.active) return; R.active=true; document.documentElement.classList.add('pal-fp'); R.PAL=palette(); R.fresh=true; labelBtns(); }
function showNow(){ if(!R.shown){ R.shown=true; requestAnimationFrame(function(){ if(R.ov && R.active) R.ov.classList.add('on'); }); } }
function closeNow(restore, keep){
  if(R.raf){ cancelAnimationFrame(R.raf); R.raf=0; }
  var ov=R.ov, view=R.saved; if(R.M) glFreeWay(R.M); R.playing=false; R.cb=null; R.M=null; R.W=null; R.hold=false; R.shown=false; R.yaw=null; R.line=null; TN=null; R.lastEv=null;
  document.documentElement.classList.remove('pal-fp'); R.active=false; if(!keep) R.saved=null;
  if(restore && view && E.putView) E.putView(view);                       /* the map as it was when the ride began; the overlay fades out over it */
  if(ov){ ov.classList.remove('on'); }
}
function chime(){ if(!sndOn()||reduced()) return;
  try{ var AC=window.AudioContext||window.webkitAudioContext; if(!AC) return; R.ac=R.ac||new AC(); var ac=R.ac; if(ac.state==='suspended') ac.resume(); var t=ac.currentTime;
    [[880,0],[659,.24]].forEach(function(n){ var o=ac.createOscillator(), g=ac.createGain(); o.type='sine'; o.frequency.value=n[0]; g.gain.setValueAtTime(0,t+n[1]); g.gain.linearRampToValueAtTime(.045,t+n[1]+.03); g.gain.exponentialRampToValueAtTime(.0008,t+n[1]+.6); o.connect(g); g.connect(ac.destination); o.start(t+n[1]); o.stop(t+n[1]+.65); }); }catch(x){} }

/* ── one frame ── */
function drawPortal(ctx, M, P, aS, veh, color){
  var o={x:0,y:0}; pathAt(M.D, aS, o); var h=headAt(M.D, aS, 6), fx=Math.cos(h), fy=Math.sin(h), nx=-fy, ny=fx, w=veh==='tram'?5.5:7.5, ho=veh==='tram'?10.5:12, WW=28, HH=26;
  function pt(l,z,ds){ var sx=o.x+nx*l+fx*(ds||0), sy=o.y+ny*l+fy*(ds||0); return project(sx,sy,z,{x:0,y:0,k:0,d:0})?_pt(sx,sy,z):null; }
  var tmp={x:0,y:0,k:0,d:0}; function _pt(x,y,z){ project(x,y,z,tmp); return [tmp.x,tmp.y]; }
  var d=Math.hypot(o.x-C.x,o.y-C.y); if(d<4) return;
  var conc=fogMix(P.dk?[92,96,108]:[164,166,172], d, P), c1=pt(-WW,0), c2=pt(WW,0), c3=pt(WW,HH), c4=pt(-WW,HH); if(!c1||!c2||!c3||!c4) return;
  /* the cutting's walls leading in */
  [-1,1].forEach(function(sd){ for(var q=0;q<5;q++){ var a0=-90+q*18, a1=a0+18, h0=Math.max(0,(q)*3.2), h1=(q+1)*3.2; var ax=o.x+nx*sd*(WW-1)+fx*a0, ay=o.y+ny*sd*(WW-1)+fy*a0, bx=o.x+nx*sd*(WW-1)+fx*a1, by=o.y+ny*sd*(WW-1)+fy*a1;
      if(wallPath(ctx, ax,ay,bx,by, 0, (h0+h1)/2+3)){ ctx.fillStyle=css(mixC(conc,[0,0,0],.18)); ctx.fill(); } } });
  ctx.fillStyle=css(conc); ctx.beginPath(); ctx.moveTo(c1[0],c1[1]); ctx.lineTo(c2[0],c2[1]); ctx.lineTo(c3[0],c3[1]); ctx.lineTo(c4[0],c4[1]); ctx.closePath(); ctx.fill();
  var o1=pt(-w,0), o2=pt(w,0), o3=pt(w,ho*.7), o4=pt(w*.7,ho), o5=pt(-w*.7,ho), o6=pt(-w,ho*.7), mc=pt(0,ho*.45); if(!o1||!o2||!o3||!o4||!o5||!o6||!mc) return;
  var rad=Math.max(8,Math.abs(o2[0]-o1[0])), g=ctx.createRadialGradient(mc[0],mc[1],0,mc[0],mc[1],rad*.9); var hc=rgbOf(color||'#6a5acd');
  g.addColorStop(0,css(mixC(hc,[255,255,255],.35),.75)); g.addColorStop(.45,css(mixC(hc,[10,6,24],.6),.9)); g.addColorStop(1,'#07050f');
  ctx.fillStyle=g; ctx.beginPath(); ctx.moveTo(o1[0],o1[1]); ctx.lineTo(o2[0],o2[1]); ctx.lineTo(o3[0],o3[1]); ctx.lineTo(o4[0],o4[1]); ctx.lineTo(o5[0],o5[1]); ctx.lineTo(o6[0],o6[1]); ctx.closePath(); ctx.fill();
  ctx.strokeStyle=css(mixC(conc,[255,255,255],.3)); ctx.lineWidth=Math.max(1.5,rad*.04); ctx.stroke(); }
function drawEl(ctx, M, P, s){        /* the viaduct under an elevated stretch: its sides, and pillars to the ground */
  (M._lifts||[]).forEach(function(g){ if(g[1]<s-30 || g[0]>s+900) return; var o={x:0,y:0}, prev=null, prevL=0;
    for(var q=Math.max(g[0],s-40); q<=Math.min(g[1],s+700); q+=10){ pathAt(M.D,q,o); var h=headAt(M.D,q,8), l=lift(M,q), tmp=[]; [-1,1].forEach(function(sd){ tmp.push([o.x-Math.sin(h)*sd*5.2, o.y+Math.cos(h)*sd*5.2]); });
      if(prev){ [0,1].forEach(function(i){ if(wallPath(ctx, prev[i][0],prev[i][1], tmp[i][0],tmp[i][1], Math.min(prevL,l)-2.6, Math.max(prevL,l)+.2)){ ctx.fillStyle=P.dk?'#2b3040':'#8d93a2'; ctx.fill(); } });
        if(Math.floor(q/40)!==Math.floor((q-10)/40)){ var x=o.x, y=o.y; if(wallPath(ctx, x-Math.sin(h)*2.4, y+Math.cos(h)*2.4, x+Math.sin(h)*2.4, y-Math.cos(h)*2.4, 0, l-2.6)){ ctx.fillStyle=P.dk?'#232736':'#757b8a'; ctx.fill(); } } }
      prev=tmp; prevL=l; } }); }
/* the city around the camera (C, set by setCam): sky, ground, whatever `way` draws on the ground (track, road, nothing), buildings, labels.
   Used by the rides (palace_ride_d.py render) and by free roaming. W is a world from gather()/the roamer's streaming. */
function drawCity(ctx, W, H, P, Wd, yaw, tm, way){
  /* WebGL when the overlay has it (the city goes to the .pr-gl canvas under this one; `way` is then called with the GL api, `g`, instead of nothing);
     the 2D painter below stays as the fallback (no WebGL, context lost) */
  if(ctx===R.ctx && glFrame(ctx, W, H, P, Wd, yaw, tm, way)){
    drawLabels(ctx, Wd.labels, P, H/900);
    if(Wd.stopLabels) drawLabels(ctx, Wd.stopLabels, P, H/900);
    return; }
  drawSky(ctx, W, H, P, yaw, tm);
  drawGround(ctx, Wd, P, null, null);
  if(way) way();
  if(Wd.scenery) sceneryDraw(ctx, Wd, P, C, tm);
  drawSolids(ctx, Wd.solids, P);
  drawLabels(ctx, Wd.labels, P, H/900);
  if(Wd.stopLabels) drawLabels(ctx, Wd.stopLabels, P, H/900);
}
function render(dt){
  var M=R.M; if(!M || !R.ctx) return; var t0=performance.now(); sizeCheck(); RIDE_M=M;
  var ctx=R.ctx, W=R.w, H=R.h, dpr=R.dpr, P=R.PAL, st=evalAt(M, R.t), D=M.D, ev=st.ev;
  var secI=st.sec, sec=M.secs[secI]||M.secs[0], veh=(st.dwell?(M.secs[st.dwell.sec]||sec).veh:st.veh)||sec.veh, spec=VEH[veh]||VEH.walk, s=st.s;
  if(glOk()){ ctx.setTransform(1,0,0,1,0,0); ctx.clearRect(0,0,R.cv.width,R.cv.height); }          /* the 2D canvas is transparent over the GL city */
  ctx.setTransform(dpr,0,0,dpr,0,0);
  /* camera */
  var hT=headAt(D, s, 14+(spec.fil>60?30:6));
  if(R.yaw==null) R.yaw=hT; else R.yaw=angLerp(R.yaw, hT, dt>0?1-Math.exp(-dt*(veh==='walk'?7:10)):0);
  pathAt(D, s, _pa); var off=spec.off+(veh==='bus'?pullAt(sec,s)*8:0), L=lift(M,s), spd=clamp(st.v/((spec.vmax||100)*1.1),0,1);
  var px=_pa.x-Math.sin(hT)*off, py=_pa.y+Math.cos(hT)*off, tm=R.t, bob=0, swx=0, swy=0, roll=0;
  if(veh==='walk'){ var ph=s/6.3*6.2832, a=clamp(st.v/60,0,1); bob=Math.sin(ph)*.085*a; swx=Math.sin(ph*.5)*H*.004*a; swy=Math.abs(Math.sin(ph))*H*.006*a; roll=Math.sin(ph*.5)*.0035*a; }
  else if(veh==='car'||veh==='bus'){ swy=Math.sin(tm*13.1+s*.01)*H*.0012*spd; roll=Math.sin(tm*3.7)*.0007*spd; }
  else { swy=(Math.sin(tm*18.3)*.5+Math.sin(tm*6.1)*.5)*H*.0016*spd; roll=Math.sin(tm*2.3)*.0016*spd; if(veh==='tram') swx=Math.sin(tm*9.7)*H*.0012*spd; }
  if(reduced()){ swx=swy=roll=bob=0; }
  var ug=ugAlpha(M, s), alpha=ug.a, camZ=spec.eye+L+bob;
  setCam(px, py, camZ, R.yaw, W, H, veh==='bus'?.43:.455);
  ctx.save(); ctx.translate(W/2+swx,H/2+swy); ctx.rotate(roll); ctx.scale(1.012,1.012); ctx.translate(-W/2,-H/2);
  if(alpha<.999){
    if(!R.W){ R.W=gather(M); GLX.newWorld(); }
    C.shk={x:swx, y:swy, r:roll, s:1.012};
    drawCity(ctx, W, H, P, R.W, R.yaw, tm, function(g){
      if(g){ g.way(M); return; }                    /* GL: the way is a static mesh of the model (palace_ride_gl.py) */
      drawWay(ctx, M, P, s, sec, off);
      if(M._br) drawBridges(ctx, M, P, s);
      if(M._lifts.length) drawEl(ctx, M, P, s);
      if(ug.ahead>=0 && ug.ahead-s<520 && ug.ahead-s>2 && sec.line) drawPortal(ctx, M, P, ug.ahead, sec.veh, sec.color); });
    C.shk=null;
  }
  if(alpha>.001){
    var calm=0; if(veh!=='walk'&&veh!=='car') calm=1-sstep(.03,.4,spd);
    var tl={dt:dt, vis:spd, calm:calm, mouth:ug.exit>=0?sstep(900,40,ug.exit-s):0, reduce:reduced(), lineHue:hueOf(sec.color||'#6a5acd'), sway:swy, lamp:1};
    if(R.tun!==1){ R.tun=1; if(!reduced()) tunnelReset(); }
    ctx.globalAlpha=alpha; tunnelFrame(ctx, W, H, tl); ctx.globalAlpha=1;
  } else if(R.tun===1){ R.tun=0; TN=null; }
  ctx.restore();
  /* the vehicle itself */
  var nxt=null; (sec.stops||[]).forEach(function(q){ if(!nxt && q.s>s+2) nxt=q; });
  var F={dk:P.dk, color:sec.color||'#888', sign:signText(sec, M), speed:spd, stopReq:veh==='bus' && nxt && (nxt.s-s)<150 && (nxt.s-s)>6 && !st.dwell};
  var fr=FRAMES[veh]||frameWalk; ctx.save(); ctx.translate(swx*.4,swy*.4); fr(ctx,W,H,F); ctx.restore();
  if(st.dwell && (st.dwell.kind==='board'||st.dwell.kind==='stop'||st.dwell.kind==='alight') && st.dwell.name){
    var u=st.u, a=sstep(0,.14,u)*(1-sstep(.82,1,u)), nm=st.dwell.name, k=st.dwell.kind;
    drawBoard(ctx, W, H, nm, sec.color, a, '', k==='board'?'Boarding here':k==='alight'?'Doors open · your stop':'Doors open'); }
  /* dip to black where the kind of travel changes, and from black at the start */
  var dip=0; if(!reduced()){ (M._cuts||[]).forEach(function(b){ var d=1-clamp(Math.abs(R.t-b)/.3,0,1); if(d>dip) dip=d; }); if(R.fresh && !M._noFade){ dip=Math.max(dip, 1-clamp(R.t/.35,0,1)); } }
  if(dip>.001){ ctx.fillStyle='rgba(6,6,12,'+(dip*dip*(3-2*dip)).toFixed(3)+')'; ctx.fillRect(0,0,W,H); }
  /* sound and words */
  if(st.dwell && st.dwell!==R.lastEv && st.u>.08 && st.u<.5 && (st.dwell.kind==='board'||st.dwell.kind==='stop'||st.dwell.kind==='alight')){ R.lastEv=st.dwell; if(!R.quiet) chime(); }
  chipUpdate(M, sec, veh, s, st, nxt);
  if(R.quiet && glOk()) GLX.flush();                                    /* tests and bench(): make the GPU finish before the clock stops */
  var ms=performance.now()-t0; R.ms=R.ms?R.ms*.9+ms*.1:ms; R.frames++; if(ms>R.worst) R.worst=ms; (R.samples=R.samples||[]).push(ms); if(R.samples.length>600) R.samples.shift();
}
function signText(sec, M){ var last=sec.stops&&sec.stops.length?sec.stops[sec.stops.length-1].n:''; var nm=sec.line?sec.line.n:'';
  if(sec.veh==='bus') return (nm.replace(/^Route\s*/i,'')+' '+(last||'')).trim().toUpperCase().slice(0,26);
  return (last?'TO '+last:nm).toUpperCase().slice(0,28); }
function chipUpdate(M, sec, veh, s, st, nxt){
  var title, sub;
  var lead=sec.line?sec.line.n:(veh==='car'?'Driving':'On foot'), toward='';
  if(st.dwell && st.dwell.kind==='end'){ title='Arrived'; sub=M.b!=null?E.name(M.b):''; if(M.line) { sub=M.line.stopName||''; } }
  else if(sec.line){ title=lead; sub=nxt?('Next stop · '+nxt.n):(sec.stops.length?'Last stop · '+sec.stops[sec.stops.length-1].n:''); if(st.dwell&&st.dwell.name) sub=(st.dwell.kind==='stop'?'Stopped · ':'')+st.dwell.name; }
  else { var nsec=M.secs[st.sec+1]; title=veh==='car'?'Driving':'Walking'; sub=nsec&&nsec.line?('To '+((nsec.stops[0]||{}).n||'the station')):(M.b!=null?('To '+E.name(M.b)):''); }
  var sig=title+'|'+sub+'|'+(sec.color||''); if(sig===R.sig) return; R.sig=sig;
  R.chip.style.setProperty('--lc', sec.color||'#888'); R.chip.innerHTML='<i></i><b>'+esc(title)+'</b>'+(sub?'<span>'+esc(sub)+'</span>':''); R.live.textContent=title+(sub?'. '+sub:''); }
function esc(v){ return String(v==null?'':v).replace(/[&<>"]/g,function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
function loop(now){
  R.raf=0; if(!R.M) return; var dt=Math.min(.05, R.last?(now-R.last)/1000:.016); R.last=now;
  if(R.playing){ R.t+=dt*R.rate; if(R.t>=R.M.T){ R.t=R.M.T; render(dt); finish(); return; } }
  render(dt); showNow();
  if(R.playing) R.raf=requestAnimationFrame(loop);
}
function kick(){ if(!R.raf && R.M){ R.last=0; R.raf=requestAnimationFrame(loop); } }
function finish(){
  R.playing=false; R.fresh=false; var cb=R.cb; R.cb=null; R.hold=true; showNow();
  var D=R.M.D; var x=D.X[D.X.length-1], y=D.Y[D.Y.length-1]; if(cb) cb(x,y); }
function prepare(M){ M._br=null; if(!M._prep){ M._prep=1; }
  /* where the way crosses the river (a bridge: water either side) is found once, with the world */
  return M; }
function startModel(M, cb, opts){
  opts=opts||{}; openOv(); finishModel(M);
  M._cuts=[]; M.ev.forEach(function(e,i){ if(e.k==='dwell' && e.kind==='board') M._cuts.push(e.t0); if(e.k==='dwell' && e.kind==='alight') M._cuts.push(e.t1); });
  var cont=R.active && R.hold && R.M && R.shown && opts.continueFrom && Math.hypot(R.M.D.X[R.M.D.X.length-1]-M.D.X[0], R.M.D.Y[R.M.D.Y.length-1]-M.D.Y[0])<3;
  if(R.M && R.M!==M) glFreeWay(R.M);
  M._noFade=!!cont; R.fresh=!cont; R.M=M; R.W=null; R.t=opts.t0||0; R.cb=cb||null; R.sig=''; R.lastEv=null; R.yaw=null; R.hold=false; R.line=opts.line||null;
  var W=gather(M); R.W=W; GLX.newWorld(); M._br=bridgeSpans(M, W); if(M._br.length){ M._br.forEach(function(g){ M._lifts.push([g[0],g[1],5,40]); }); }
  W.stopLabels=[]; M.secs.forEach(function(sec){ if(!sec.line||sec.veh==='walk') return; sec.stops.forEach(function(q,qi){ if(sec.ug.some(function(g){ return q.s>=g[0]&&q.s<=g[1]; })) return; var o={x:0,y:0}; pathAt(M.D,q.s,o); W.stopLabels.push({x:o.x,y:o.y,z:12,text:q.n,col:sec.color}); }); });
  if(reduced()){ R.t=M.T; R.playing=false; R.hold=true; R.fresh=false; render(0); showNow(); if(cb){ R.cb=null; var D=M.D; setTimeout(function(){ cb(D.X[D.X.length-1], D.Y[D.Y.length-1]); }, 700); } return; }
  R.playing=opts.hold?false:true; kick(); }

/* ── from a trip's leg, and from a line's own ride ── */
function leg(legObj, rev, cb){
  if(!E || pref()!=='fp') return false;
  var S=window._palTr.state(), mode=S.mode||'transit', M=null;
  try{ M=buildModel(legObj, rev, mode); }catch(x){ if(window.console) console.warn('ride model', x); }
  if(!M) return false;
  M.a=rev?legObj.b:legObj.a; M.b=rev?legObj.a:legObj.b; R.mode=mode;
  startModel(M, cb, {continueFrom:true}); return true; }
function lineSub(l, i0, i1){
  var stops=stopsAll(), a=stops[l.s[i0]], b=stops[l.s[i1]]; if(!a||!b) return null;
  var best=null;
  (l.p||[]).forEach(function(poly){ if(!poly||poly.length<4) return; var qa=projPoly(poly,a.x,a.y), qb=projPoly(poly,b.x,b.y); var sc=qa.d+qb.d; if(!best||sc<best.sc) best={sc:sc, poly:poly, qa:qa, qb:qb}; });
  if(!best||best.sc>600) return [[a.x,a.y],[b.x,b.y]];
  var p=best.poly, A=best.qa, B=best.qb, fwd=(A.pos<=B.pos), pts=[];
  var nodes=[]; var acc=0; for(var k=0;k+1<p.length;k+=2){ nodes.push({x:p[k],y:p[k+1],pos:acc}); if(k+3<p.length) acc+=Math.hypot(p[k+2]-p[k],p[k+3]-p[k+1]); }
  var lo=Math.min(A.pos,B.pos), hi=Math.max(A.pos,B.pos), mid=nodes.filter(function(n){ return n.pos>lo+1 && n.pos<hi-1; });
  pts=[[A.x,A.y]].concat(fwd?mid.map(function(n){ return [n.x,n.y]; }):mid.slice().reverse().map(function(n){ return [n.x,n.y]; }), [[B.x,B.y]]);
  return pts; }
function projPoly(poly, x, y){ var best={d:1e18,pos:0,x:poly[0],y:poly[1]}, acc=0;
  for(var k=0;k+3<poly.length;k+=2){ var ax=poly[k], ay=poly[k+1], bx=poly[k+2], by=poly[k+3], dx=bx-ax, dy=by-ay, L=Math.hypot(dx,dy)||1e-9, t=clamp(((x-ax)*dx+(y-ay)*dy)/(L*L),0,1), qx=ax+t*dx, qy=ay+t*dy, d=Math.hypot(qx-x,qy-y);
    if(d<best.d) best={d:d,pos:acc+t*L,x:qx,y:qy}; acc+=L; }
  return best; }
function lineModel(l, i0, i1){
  var pts=lineSub(l, i0, i1); if(!pts) return null; var stops=stopsAll(), a=stops[l.s[i0]], b=stops[l.s[i1]], ln=l;
  var veh=ln.k==='metro'?'metro':ln.k==='tram'?'tram':ln.k==='bus'?'bus':'rail', col=colOf(ln);
  var raw=[{veh:veh, line:ln, color:col, pts:pts, board:{n:a.n,x:a.x,y:a.y}, alight:{n:b.n,x:b.x,y:b.y}}];
  var M=modelFromRaw(raw, {leg:{}, rev:false, mode:'transit', a:null, b:null}); if(M){ M.minT=3.5; timeline(M); M.line={id:l.id, i:i1, stopName:b.n}; }
  return M; }
function lineEnter(id, i){
  if(!E || pref()!=='fp' || reduced()) { return false; }
  var l=lineOf(id); if(!l || !l.s.length) return false;
  var j=i<l.s.length-1?i+1:i-1; if(j<0) return false;
  var M=lineModel(l, i, j); if(!M) return false;
  cancelPend(); var first=M.ev.filter(function(e){ return e.k==='dwell'&&e.kind==='board'; })[0];
  startModel(M, null, {hold:true, t0:first?first.t1-.02:0, line:id}); R.line={id:id,i:i}; M._noFade=false; return true; }
function lineStep(id, i0, i1, cb){
  if(!E || !R.active || pref()!=='fp') return false;
  var l=lineOf(id); if(!l) return false; var M=lineModel(l, i0, i1); if(!M) return false;
  var first=M.ev.filter(function(e){ return e.k==='dwell'&&e.kind==='board'; })[0];
  M.skipBoard=true; startModel(M, function(){ if(cb) cb(); }, {continueFrom:true, t0:first?first.t1:0, line:id});
  if(reduced()){ return true; } return true; }
function cancelPend(){ if(R.pend){ clearTimeout(R.pend); R.pend=0; } }
function exit(){ if(!R.active) { return; }
  cancelPend(); R.pend=setTimeout(function(){ R.pend=0; closeNow(true); }, 0); }
function mark(){ if(!R.active && E && E.curView) R.saved=E.curView(); }
function toggle(){
  var to=pref()==='fp'?'map':'fp'; setPref(to); labelBtns();
  var S=window._palTr&&window._palTr.state?window._palTr.state():null;
  if(to==='map'){ if(R.active){ var cb=R.cb; if(R.playing){ R.cb=null; R.playing=false; var D=R.M.D; closeNow(false, true); if(cb) cb(D.X[D.X.length-1], D.Y[D.Y.length-1]); } else closeNow(false, true); } }
  else if(S && S.ride && !S.trip){ lineEnter(S.ride.l, S.ride.i); }
}
function switchHtml(){ var fp=pref()==='fp'; return '<div class="tr-btns pr-sw"><button class="tr-b" type="button" data-ride="view" aria-pressed="'+fp+'">'+(fp?'Map view · V':'Ride view · V')+'</button><button class="tr-b pr-ex" type="button" data-ride="exit">Exit ride</button></div>'; }
function bind(){
  document.addEventListener('click', function(e){ var b=e.target.closest&&e.target.closest('[data-ride]'); if(!b) return; e.preventDefault(); e.stopPropagation(); var a=b.getAttribute('data-ride');
    if(a==='view') toggle(); else if(a==='exit'){ if(window._palTr) window._palTr.clear(); } else if(a==='snd'){ try{ localStorage.setItem(LS_SND, sndOn()?'off':'on'); }catch(x){} labelBtns(); if(sndOn()) chime(); } }, true);
  window.addEventListener('keydown', function(e){ if(e.metaKey||e.ctrlKey||e.altKey) return; var t=e.target; if(t && (t.tagName==='INPUT'||t.tagName==='TEXTAREA'||t.isContentEditable)) return;
    if(e.key!=='v' && e.key!=='V') return; var S=window._palTr&&window._palTr.state?window._palTr.state():null; if(!S || (!S.trip && !S.ride)) return; e.preventDefault(); e.stopImmediatePropagation(); toggle(); }, true);
  window.addEventListener('resize', function(){ if(R.active && R.M){ kick(); } });
}
"""
