"""The toy fleet, part 2 (1.9.99): arming a toy and what each weapon does. Hosted with the rest (palace_fleet_asset.py), never in the page.

A click on a toy arms it (an orange glow, a bar "USS Midway — click a building to launch the air strike · Esc to stand down", crosshair cursors), a click
on a node building or a landmark attacks THAT point, Esc / the × / the toy again stands down; another toy clicked while one is armed arms the other.
Every attack ends the same way: fxBoom at the impact, then fxRuin (the building pancakes and is rebuilt over 20 s: palace_construct.py, and the people
run out of it: palace_panic.py).

  WP table (class -> verb for the bar, attack):
    bb    a battleship: its mounts turn and fire, shells arc to the target (USS New Jersey, unchanged from 1.9.97)
    army  a shore battery: its three howitzers fire twice, the shells climb high and land together
    dd    a cruiser / destroyer: four missiles climb out of the launch cells and curve in on the target on smoke trails
    cv    an aircraft carrier: 4 jets run down the deck, climb away in an echelon, fly over the map to the target and drop their bombs
          (the bomb whistles down), then bank off the map
    air   a military airfield: 3 fighters take off down the runway and make the same bombing run
    sub   a submarine: a sonar ping goes out, a torpedo and its wake run through the water to the target

All sizes are measured on the SCREEN (pin(): an SVG translate in map units, a unitless scale) so they hold at every zoom in Safari too; no CSS px in
transforms, no filters, no mask. One requestAnimationFrame loop drives the flights from the elapsed time (`_palFleet.freeze(ms)` shows any instant exactly: QA).
"""
from __future__ import annotations

FLEET_B = r"""
/* ── arming ── */
function fxLayer(){ var s=H.svg, g=s&&s._fx; if(!g || g.parentNode!==s){ g=s._fx=el('g',{'class':'pl-fx'},s); } s.appendChild(g); return g; }
function fxBar(on, toy){ var b=document.getElementById('pal-fxbar'), de=H.de; if(!b){ b=document.createElement('div'); b.id='pal-fxbar'; b.setAttribute('role','status'); document.body.appendChild(b);
    b.innerHTML='<span class="fx-t"></span><button type="button" class="fx-x" aria-label="Stand the guns down" title="Stand down (Esc)">\u00d7</button>';
    b.addEventListener('click', function(e){ if(e.target.closest('.fx-x')){ e.stopPropagation(); e.preventDefault(); fxBar(false); } }); }
  [].forEach.call(document.querySelectorAll('.wp.armed'), function(x){ x.classList.remove('armed'); });
  ARM=on?toy:null; if(on) toy.classList.add('armed');
  var w=on?toy._w:'bb', d=on&&toy._b; b.querySelector('.fx-t').textContent=((d&&d.n)||DEF[w])+' \u2014 click a building to '+WP[w].verb+' \u00b7 Esc to stand down'; de.classList.toggle('fx-armed', on);
  SND.bar(b, on, WP[w].snd); if(!on && window._palPanic) window._palPanic.stop(); }
function fxTween(ms, fn, done){ var t0=performance.now(); (function f(t){ var k=Math.min(1,(t-t0)/ms); fn(k); if(k<1) requestAnimationFrame(f); else if(done) done(); })(t0); }
function fxPin(x, y, cls){ var g=pin(fxLayer(), cls, x, y, {}); return g; }
function fxBoom(x, y){
  SND.b(x, y); var Z=H.Z;
  var g=fxPin(x, y, 'fx-boom'), o=g.parentNode;
  [['#ffd34a',14,520],['#ff7a3c',22,760],['#6b6f7a',30,1500]].forEach(function(c,i){ var k=el('circle',{r:c[1], fill:c[0], 'fill-opacity':i===2?.55:.9},g); k.style.transformBox='fill-box'; k.style.transformOrigin='center';
    k.animate([{transform:'scale(.15)',opacity:1},{transform:'scale('+(i===2?2.6:1.9)+')',opacity:0}],{duration:c[2],easing:'ease-out',fill:'forwards'}); });
  var parts=[]; for(var i=0;i<9;i++){ var a=Math.random()*Math.PI*2, v=40+Math.random()*90; parts.push({e:el('rect',{x:-3,y:-3,width:6,height:6,fill:'#44404a'},fxLayer()), vx:Math.cos(a)*v, vy:Math.sin(a)*v-80, x:x, y:y}); }
  fxTween(1100, function(k){ parts.forEach(function(p){ var t=k*1.1, px=p.x+p.vx*t/Z*.6, py=p.y+(p.vy*t+260*t*t)/Z*.6; p.e.setAttribute('transform','translate('+px.toFixed(1)+' '+py.toFixed(1)+') scale('+(Math.max(.1,1-k)/Z*.9).toFixed(3)+')'); p.e.setAttribute('opacity', (1-k).toFixed(2)); }); },
    function(){ parts.forEach(function(p){ p.e.remove(); }); setTimeout(function(){ o.remove(); }, 900); });
}
function fxShell(x0, y0, x1, y1, ms, hit, hf){
  var g=fxPin(x0, y0, 'fx-shell'), o=g.parentNode; el('circle',{r:4.2,fill:'#2b2f3b',stroke:'#fff','stroke-width':1.2},g);
  var d=Math.hypot(x1-x0, y1-y0), h=Math.min(260*(hf||1), d*.28*(hf||1));
  fxTween(ms, function(k){ o.setAttribute('transform','translate('+(x0+(x1-x0)*k).toFixed(1)+' '+(y0+(y1-y0)*k-4*h*k*(1-k)).toFixed(1)+')'); }, function(){ o.remove(); if(hit) hit(); });
}
/* a building struck: it pancakes into rubble and is rebuilt as a construction site over 20 s (palace_construct.py): foundation, crane, steel frame,
   scaffold, glass hung storey by storey, roof last. A node building is its own svg; a landmark is its group. */
function fxRuin(el_, tagEl){ if(el_ && window._palCon) window._palCon.run(el_, tagEl); }
/* the people in it run for their lives (palace_panic.py) */
var fxRuin0=fxRuin; fxRuin=function(el_, tagEl){ fxRuin0(el_, tagEl); if(window._palPanic) window._palPanic.go({svg:H.svg, el:el, pin:pin, Z:H.Z, graph:H.graph, nearest:H.nearest, route:H.route, dk:H.dk()}, el_, tagEl); };
function fxTarget(t){
  var n=t.closest&&t.closest('#world .node[id^="node-"]'); if(n && n._nbS && !n.classList.contains('pal-floor')){ var S_=n._nbS; return {x:(S_[0]+S_[2])/2, y:S_[3]-(S_[3]-S_[1])*.35, ruin:function(){ var b=n.querySelector(':scope > .nb3d'); if(b) fxRuin(b, n); }}; }
  var lm=t.closest&&t.closest('#palace-svg .pl-lmb'); if(lm && lm._lm){ var L=lm._lm; return {x:L.x+L.w/2, y:L.y+L.h/2, ruin:function(){ fxRuin(lm, null); }}; }
  return null;
}
/* ── the flights: one frame loop, each flight a function of the time since it started (ms), returning false when it is over ── */
var RUNS=[], RAF=0, FORCE=null;
function run(fn){ var r={t0:performance.now(), fn:fn}; RUNS.push(r); if(!RAF) RAF=requestAnimationFrame(tick); return r; }
function tick(now){ RAF=0; for(var i=RUNS.length-1;i>=0;i--){ var r=RUNS[i], t=(FORCE!=null)?FORCE:(now-r.t0); if(!r.fn(t)) RUNS.splice(i,1); } if(RUNS.length) RAF=requestAnimationFrame(tick); }
function trk(p){ var c=[0], i; for(i=1;i<p.length;i++) c.push(c[i-1]+Math.hypot(p[i][0]-p[i-1][0], p[i][1]-p[i-1][1])); return {p:p, c:c, L:c[c.length-1]}; }
function at(T, s){ var c=T.c, i=1; s=Math.max(0, Math.min(T.L, s)); while(i<c.length-1 && c[i]<s) i++; var a=T.p[i-1], b=T.p[i], u=cl((s-c[i-1])/((c[i]-c[i-1])||1)); return [a[0]+(b[0]-a[0])*u, a[1]+(b[1]-a[1])*u, Math.atan2(b[1]-a[1], b[0]-a[0])]; }
/* the distance along a track (map units) at each 1/60 s, from a speed (screen px/s) that depends on the screen distance already flown */
function prof(T, v, Z){ var s=0, o=[0]; while(s<T.L && o.length<2400){ s+=v(s*Z)/Z/60; o.push(Math.min(s, T.L)); } return o; }
function sAt(tab, t){ var f=Math.max(0,t)*.06, i=Math.floor(f); if(i>=tab.length-1) return tab[tab.length-1]; return tab[i]+(tab[i+1]-tab[i])*(f-i); }
function tOf(tab, s){ for(var i=0;i<tab.length;i++) if(tab[i]>=s) return i*1000/60; return (tab.length-1)*1000/60; }
function pts(arr){ return arr.map(function(p){ return f1(p[0])+' '+f1(p[1]); }).join('L'); }
function sprite(cls, build){ var g=fxPin(0, 0, cls), o=g.parentNode, k=el('g',{},g); build(k); o.setAttribute('display','none'); return {o:o, k:k}; }
function put(sp, x, y, rot, sc, op){ sp.o.removeAttribute('display'); sp.o.setAttribute('transform','translate('+f1(x)+' '+f1(y)+')'); sp.k.setAttribute('transform','rotate('+(rot*180/PI).toFixed(1)+') scale('+sc.toFixed(2)+')'); if(op!=null) sp.o.setAttribute('opacity', op.toFixed(2)); }
function trail(col, w){ return el('path',{fill:'none', stroke:col, 'stroke-width':w, 'stroke-linecap':'round', 'stroke-linejoin':'round', 'vector-effect':'non-scaling-stroke'}, fxLayer()); }
function puff(x, y, r, ms, col){ var sm_=fxPin(x, y, 'fx-smoke'), sq=sm_.parentNode, sc=el('circle',{r:r, fill:col||'#7b7f8a', 'fill-opacity':.5},sm_); sc.style.transformBox='fill-box'; sc.style.transformOrigin='center';
  sc.animate([{transform:'scale(.4)',opacity:.8},{transform:'scale(3.2)',opacity:0}],{duration:ms||1500,easing:'ease-out'}).onfinish=function(){ sq.remove(); }; }
function flash(x, y){ var f=fxPin(x, y, 'fx-flash'), q=f.parentNode; el('circle',{r:16,fill:'#ff8a3c','fill-opacity':.55},f); el('circle',{r:11,fill:'#ffe08a'},f); el('circle',{r:5.5,fill:'#fff'},f); setTimeout(function(){ q.remove(); }, 210); }
function ring(x, y, r, ms, col){ var f=fxPin(x, y, 'fx-ring'), k=el('circle',{r:r, fill:'none', stroke:col||'#fff', 'stroke-width':2, 'vector-effect':'non-scaling-stroke'},f); k.style.transformBox='fill-box'; k.style.transformOrigin='center';
  k.animate([{transform:'scale(.08)',opacity:.95},{transform:'scale(1)',opacity:0}],{duration:ms,easing:'ease-out',fill:'forwards'}).onfinish=function(){ f.parentNode.remove(); }; }
/* where a flight's last hit lands: the first goes exactly to the target and brings it down, the rest hit round it */
function impact(tg, first, ix, iy){ if(first){ fxBoom(tg.x, tg.y); tg.ruin(); } else fxBoom(ix, iy); }

/* ── the guns (a battleship, a shore battery): the mounts turn, flash and recoil, shells arc to the target ── */
function fireGuns(tg, toy, rounds, hf){
  var b=toy._b, a=(b.a||0)*PI/180, Z0;
  function volley(rd){ b._tur.forEach(function(t, i){ var Z=H.Z, wx=t.abs?t.abs[0]:b.x+Math.cos(a)*t.x, wy=t.abs?t.abs[1]:b.y+Math.sin(a)*t.x, th=Math.atan2(tg.y-wy, tg.x-wx);
    t.bar.setAttribute('transform', t.abs ? 'translate('+t.abs[0].toFixed(1)+' '+t.abs[1].toFixed(1)+') rotate('+(th*180/PI).toFixed(1)+')' : 'rotate('+(th*180/PI-b.a).toFixed(1)+')');
    var reach=(t.r&&t.len)?t.r*t.len:b.wid*.62, mx=wx+Math.cos(th)*reach, my=wy+Math.sin(th)*reach;
    setTimeout(function(){ flash(mx, my); puff(mx, my, 14);
      (t.bl||[]).forEach(function(ln){ var r0=t.r*(t.len||3.1); fxTween(380, function(k){ var rc=k<.2?k/.2:(1-k)/.8; ln.setAttribute('x2', (r0-rc*t.r*.7).toFixed(1)); ln.setAttribute('x1', (t.r*.5-rc*t.r*.7).toFixed(1)); }); });
      var j=(i-1)*26/Z, d=Math.hypot(tg.x-mx, tg.y-my), ms=Math.max(700, Math.min(1500, 500+d*.6)); SND.f(ms);
      fxShell(mx, my, tg.x+j, tg.y+j*.4, ms, (i===0&&rd===0) ? function(){ fxBoom(tg.x, tg.y); tg.ruin(); } : function(){ fxBoom(tg.x+j, tg.y+j*.4); }, hf); }, 140*i); }); }
  for(var rd=0; rd<(rounds||1); rd++) (function(rd){ if(rd) setTimeout(function(){ volley(rd); }, 1250*rd); else volley(0); })(rd);
}

/* ── missiles: out of the launch cells, up (a puff), then a curve in on the target on a smoke trail ── */
function fireMissiles(tg, toy){
  var b=toy._b, Z=H.Z, ms=[], T=[tg.x, tg.y], SPACE=190, WAIT=230;
  (b._cells||[[b.x, b.y]]).forEach(function(c, j){ var dx=T[0]-c[0], dy=T[1]-c[1], d=Math.hypot(dx, dy)||1, nx=-dy/d, ny=dx/d, sd=(j%2?1:-1)*(1+(j>>1)*.55)*d*.2, P=[];
    for(var i=0;i<=40;i++){ var u=i/40, bx=(1-u)*(1-u)*c[0]+2*u*(1-u)*(c[0]+dx*.4+nx*sd)+u*u*T[0], by=(1-u)*(1-u)*c[1]+2*u*(1-u)*(c[1]+dy*.4+ny*sd)+u*u*T[1]; P.push([bx, by]); }
    var tk=trk(P), tab=prof(tk, function(sc){ return 160+620*sm(sc/260); }, Z), tl=el('path',{fill:'none', stroke:'#fff', 'stroke-width':2.6, 'stroke-linecap':'round', 'vector-effect':'non-scaling-stroke', opacity:.8}, fxLayer()), tr=[];
    ms.push({c:c, j:j, tk:tk, tab:tab, tl:tl, tr:tr, d0:j*SPACE+WAIT, tEnd:tOf(tab, tk.L), sp:sprite('fx-msl', function(k){
      el('path',{d:'M-9-1.7L1-1.7Q5 0 1 1.7L-9 1.7Z', fill:'#e9ecf1', stroke:'#4a5262', 'stroke-width':.9},k); el('path',{d:'M-9 0L-14.5-2.4L-14.5 2.4Z', fill:'#ff9a3c'},k); el('rect',{x:-7, y:-3.4, width:2.6, height:6.8, fill:'#c4c9d2'},k); }), go:false, done:false}); });
  SND.rocket(900);
  run(function(t){ var alive=false;
    ms.forEach(function(m){ var tj=t-m.d0;
      if(!m.go && t>=m.j*SPACE){ m.go=true; flash(m.c[0], m.c[1]); puff(m.c[0], m.c[1], 10, 1200, '#aab0bd'); }
      if(m.done){ var k=cl((t-m.tEnd-m.d0)/700); m.tl.setAttribute('opacity', (.8*(1-k)).toFixed(2)); if(k<1) alive=true; else { m.tl.remove(); } return; }
      alive=true; if(tj<0) return;
      var s=sAt(m.tab, tj), p=at(m.tk, s); m.tr.push([p[0], p[1], tj]); while(m.tr.length>1 && tj-m.tr[0][2]>900) m.tr.shift();
      m.tl.setAttribute('d', 'M'+pts(m.tr)); put(m.sp, p[0], p[1], p[2], 1.1+.5*sm(tj/500));
      if(s>=m.tk.L-.01){ m.done=true; m.sp.o.remove(); var jx=(m.j%2?1:-1)*(m.j>>1)*16/Z; impact(tg, m.j===0, tg.x+jx, tg.y-jx*.6); } });
    return alive || ms.some(function(m){ return !m.done; }); });
}

/* ── the bombing run (a carrier, an airfield): jets run down their deck / runway, climb, fly to the target in an echelon, drop bombs and bank off the map ── */
function flightPath(P0, h0, T, Z, roll, side){
  var p=[P0], ux=Math.cos(h0), uy=Math.sin(h0), P1=[P0[0]+ux*roll, P0[1]+uy*roll], i;
  for(i=1;i<=6;i++) p.push([P0[0]+ux*roll*i/6, P0[1]+uy*roll*i/6]);
  var dx=T[0]-P1[0], dy=T[1]-P1[1], dist=Math.hypot(dx, dy)||1, ut=[dx/dist, dy/dist], A=Math.min(dist*.42, 300/Z), Q=[T[0]-ut[0]*A, T[1]-ut[1]*A];
  var dq=Math.hypot(Q[0]-P1[0], Q[1]-P1[1]), kk=Math.max(80/Z, dq*.5), c1=[P1[0]+ux*kk, P1[1]+uy*kk], c2=[Q[0]-ut[0]*kk, Q[1]-ut[1]*kk];
  for(i=1;i<=44;i++){ var u=i/44, w=1-u; p.push([w*w*w*P1[0]+3*w*w*u*c1[0]+3*w*u*u*c2[0]+u*u*u*Q[0], w*w*w*P1[1]+3*w*w*u*c1[1]+3*w*u*u*c2[1]+u*u*u*Q[1]]); }
  for(i=1;i<=8;i++) p.push([Q[0]+(T[0]-Q[0])*i/8, Q[1]+(T[1]-Q[1])*i/8]);
  var sT=trk(p).L, hT=Math.atan2(ut[1], ut[0]), cur=[T[0], T[1]], N=70;
  for(i=1;i<=N;i++){ var hh=hT+side*1.0*Math.pow(i/N, 1.5); cur=[cur[0]+Math.cos(hh)*24/Z, cur[1]+Math.sin(hh)*24/Z]; p.push(cur); }
  var tk=trk(p); tk.sT=sT; tk.roll=roll; tk.ut=ut; return tk;
}
function fireStrike(tg, toy){
  var b=toy._b, Z=H.Z, air=toy._w==='air', n=air?3:4, T=[tg.x, tg.y], DLY=air?520:430, jets=[], bombs=[], i, st=null;
  if(air){ var A=b._rw[0], B=b._rw[1], dir=(B[0]-A[0])*(T[0]-b.x)+(B[1]-A[1])*(T[1]-b.y)>=0; st=dir?[A, B]:[B, A]; }
  for(i=0;i<n;i++) (function(j){
    var P0, h0, roll;
    if(air){ var rx=st[1][0]-st[0][0], ry=st[1][1]-st[0][1], rl=Math.hypot(rx, ry); h0=Math.atan2(ry, rx); P0=[st[0][0]-ry/rl*((j%2)?3:-3)/Z, st[0][1]+rx/rl*((j%2)?3:-3)/Z]; roll=rl; }
    else { P0=b._launch[j]; h0=b.a*PI/180; roll=Math.max(50/Z, b.len/2-((P0[0]-b.x)*Math.cos(h0)+(P0[1]-b.y)*Math.sin(h0))); }
    var tk=flightPath(P0, h0, T, Z, roll, j%2?1:-1), sR=roll*Z, sTs=tk.sT*Z;
    var tab=prof(tk, function(sc){ return sc<sR?70+250*sc/Math.max(sR, 1):(sc<sTs?320+300*sm((sc-sR)/380):620+340*sm((sc-sTs)/700)); }, Z);
    var sd=Math.max(sR+30, sTs-170)/Z, md=((j+1)>>1)*(j%2?1:-1)*26;
    jets.push({j:j, tk:tk, tab:tab, d0:j*DLY, sR:sR, sd:sd, md:md, tl:trail('#fff', 2.2), tr:[], bombed:false, tEnd:tOf(tab, tk.L),
      sh:sprite('fx-jet fx-jsh', function(k){ el('path',{d:JET, transform:'scale(30)', fill:'#1b2233', 'fill-opacity':.3},k); }),
      sp:sprite('fx-jet', function(k){ el('path',{d:JET, transform:'scale(30)', fill:'#a3adbf', stroke:'#2e3648', 'stroke-width':1.3, 'vector-effect':'non-scaling-stroke'},k); el('path',{d:'M.1-.07L.22 0L.1.07Z', transform:'scale(30)', fill:'#5b88c4'},k); })});
    SND.jet(j*DLY/1000, (tOf(tab, tk.sT)+1100)/1000);
  })(i);
  run(function(t){ var alive=false;
    jets.forEach(function(J){ var tj=t-J.d0;
      if(J.dead) return; alive=true; if(tj<0) return;
      var s=sAt(J.tab, tj), p=at(J.tk, s), sc=s*Z, h=p[2], off=J.md*sm((sc-J.sR)/450)/Z, x=p[0]-Math.sin(h)*off, y=p[1]+Math.cos(h)*off, z=.55+.65*sm(sc/(J.sR+500)), fade=1-sm((tj-J.tEnd+700)/700);
      if(tj===0 || !J.t0done){ J.t0done=true; if(J.j<1||air) puff(x, y, 9, 1100, '#b8bdc8'); }
      J.tr.push([x, y, tj]); while(J.tr.length>1 && tj-J.tr[0][2]>(sc<J.sR?150:800)) J.tr.shift();
      J.tl.setAttribute('d', 'M'+pts(J.tr)); J.tl.setAttribute('opacity', (.75*Math.max(0, fade)).toFixed(2));
      put(J.sh, x+7/Z*z, y+11/Z*z, h, z*.95, .9*fade); put(J.sp, x, y, h, z, fade);
      if(!J.bombed && s>=J.sd){ J.bombed=true; var lead=170/Z, ix=J.j===0?T[0]:x+Math.cos(h)*lead, iy=J.j===0?T[1]:y+Math.sin(h)*lead; SND.whistle(840);
        bombs.push({t0:tj+J.d0, j:J.j, x:x, y:y, h:h, ix:ix, iy:iy, sp:sprite('fx-bomb', function(k){ el('path',{d:'M-5-1.5L2-1.5Q5 0 2 1.5L-5 1.5L-7 3L-7-3L-5-1.5Z', fill:'#3a4150', stroke:'#10141f', 'stroke-width':.8},k); })}); }
      if(s>=J.tk.L-.001 || tj>J.tEnd+300){ J.dead=true; J.tl.remove(); J.sh.o.remove(); J.sp.o.remove(); } });
    bombs.forEach(function(B){ if(B.done) return; alive=true; var k=cl((t-B.t0)/840), u=1-(1-k)*(1-k);
      put(B.sp, B.x+(B.ix-B.x)*u, B.y+(B.iy-B.y)*u, B.h+k*.9, 1.25-.45*k);
      if(k>=1){ B.done=true; B.sp.o.remove(); impact(tg, B.j===0, B.ix, B.iy); } });
    return alive; });
}

/* ── the torpedo: a ping goes out from the hull, then a torpedo and its wake run the straight line through the water to the target ── */
function fireTorpedo(tg, toy){
  var b=toy._b, Z=H.Z, P0=b._muzzle, T=[tg.x, tg.y], d=Math.hypot(T[0]-P0[0], T[1]-P0[1])||1, ms=Math.max(1700, Math.min(4300, d*Z/330*1000)), ux=(T[0]-P0[0])/d, uy=(T[1]-P0[1])/d, hd=Math.atan2(uy, ux);
  ring(P0[0], P0[1], 150, 1500); setTimeout(function(){ ring(P0[0], P0[1], 150, 1500); }, 360); SND.ping(); SND.torpedo(ms/1000+.4);
  var w1=trail('rgba(255,255,255,.7)', 5), w2=trail('#fff', 3), done=false, fade0=0;
  w2.setAttribute('stroke-dasharray', '1 8'); w2.setAttribute('opacity', .95);
  var sp=sprite('fx-tor', function(k){ el('path',{d:'M-9-1.8L3-1.8Q8 0 3 1.8L-9 1.8Z', fill:'#39424f', stroke:'#0f1420', 'stroke-width':.9},k); el('path',{d:'M-9-1.8L-12-4.4L-10-.2ZM-9 1.8L-12 4.4L-10 .2Z', fill:'#59627a'},k);
    el('path',{d:'M-13-4.5L-27-9M-13 4.5L-27 9', fill:'none', stroke:'rgba(255,255,255,.8)', 'stroke-width':1.4, 'stroke-linecap':'round'},k); });
  run(function(t){ var k=cl((t-260)/ms);
    if(k<1){ if(t<260) return true; var x=P0[0]+(T[0]-P0[0])*k, y=P0[1]+(T[1]-P0[1])*k; w1.setAttribute('d','M'+f1(P0[0])+' '+f1(P0[1])+'L'+f1(x)+' '+f1(y)); w2.setAttribute('d', w1.getAttribute('d')); put(sp, x, y, hd, 1.5); return true; }
    if(!done){ done=true; fade0=t; sp.o.remove(); ring(T[0], T[1], 70, 900, '#fff'); fxBoom(T[0], T[1]); tg.ruin(); }
    var f=cl((t-fade0)/1300); w1.setAttribute('opacity', (1-f).toFixed(2)); w2.setAttribute('opacity', (.95*(1-f)).toFixed(2)); if(f>=1){ w1.remove(); w2.remove(); return false; } return true; });
}

/* ── what each class does ── */
WP.bb={verb:'fire', snd:'battleship', fire:function(tg, toy){ fireGuns(tg, toy, 1, 1); }};
WP.army={verb:'shell it', snd:'battery', fire:function(tg, toy){ fireGuns(tg, toy, 2, 1.8); }};
WP.dd={verb:'launch the missile salvo', snd:'warship', fire:fireMissiles};
WP.cv={verb:'launch the air strike', snd:'carrier', fire:fireStrike};
WP.air={verb:'scramble the fighters', snd:'air base', fire:fireStrike};
WP.sub={verb:'fire a torpedo', snd:'submarine', fire:fireTorpedo};
function fire(tg, toy){ var now=performance.now(); if(now-LAST<1100) return; LAST=now; var b=toy._b; SND.u(b.x, b.y); WP[toy._w].fire(tg, toy); }

function bind(){ if(bound) return; bound=true;
  window.addEventListener('click', function(e){
    if(H.mob() || !H.palaceOn()) return;
    var wp=e.target.closest&&e.target.closest('#palace-svg .wp');
    if(wp){ e.stopImmediatePropagation(); e.preventDefault(); fxBar(ARM!==wp, wp); return; }
    if(!ARM) return;
    var tg=fxTarget(e.target); if(!tg){ return; }
    var cp=H.svgPt(H.svg, e); tg.x=cp[0]; tg.y=cp[1];                                     /* the shells go where the aimer was clicked, not to the building's middle */
    e.stopImmediatePropagation(); e.preventDefault(); if(ARM._b) fire(tg, ARM);
  }, true);
  window.addEventListener('keydown', function(e){ if(ARM && e.key==='Escape'){ e.stopImmediatePropagation(); e.preventDefault(); fxBar(false); } }, true);
}
function draw(lg, M, host){ H=host; el=host.el; pin=host.pin; (M.boats||[]).forEach(function(b, bi){ drawBoat(lg, b, bi); }); (M.bases||[]).forEach(function(s, bi){ drawBase(lg, s, bi); }); bind(); }
return {draw:draw, WP:WP, arm:function(toy, on){ fxBar(on!==false, toy); }, armed:function(){ return ARM; }, fire:fire, fx:{boom:fxBoom, flightPath:flightPath, trk:trk, at:at},
  freeze:function(ms){ FORCE=(ms==null)?null:+ms; if(!RAF && RUNS.length) RAF=requestAnimationFrame(tick); }, active:function(){ return RUNS.length; }, last:function(v){ LAST=v; }};
})();
"""
