"""The black hole (Luke, 2026-10-28, item 7): on the Star chart and the 3D Star chart, a quiz taken on a detail page that
ends under the pass mark (study.py: QUIZ_FAIL_PCT) sends the page back to the chart and the player's ship off to a
black hole far from every system. It falls in; the ship comes back to the very spot it left, with a "Try again" offer
that reopens the quiz. Playful, never punishing; every beat skippable (Esc, the chevron, a click). Art's look:
ORG/notes-system-blackhole-look.md.

study.py only says so: it fires `alto-quiz-fail` {key, p, s, n} on window after a failing grade (never on a pass, never
on the first open). This file listens. Nothing moves on the chart: a layer (#bh) above it plays the whole sequence,
the chart's own ship hidden under it, and gives it back where it was. Beats (seconds): 0.4 the chart and the score as
pips; the ship's own wind-up and leaving (solar_craft.py travel: the Enterprise's warp, the Halo's jump, the rocket's
burn); 0.7 the stars streak; 0.8 the hole ahead, its disc turning; 2.4 the fall, a spiral that stretches the ship and
ends in a white-gold flash; 0.9 the ship back at its spot, a small bob, the hole dissolving. Then the chip. At most one
fall in 30 s. Reduced motion: a fade to the hole, a dim, a fade back, the chip.

Not on the System look or Retro (nothing of this runs there), not in edit mode, not on a phone's card view.
"""
from __future__ import annotations

HOLE_JS = r"""
(function(){
var de=document.documentElement, NS='http://www.w3.org/2000/svg', COOL=30000, LEAVE=.8, T1=.4, TR=.7, TA=.8, TF=2.4, TB=.9;
var last=-1e9, R=null, chip=null, raf=0, dpObs=null;
function A(){ return window._altoCraft; }
function ss(x){ x=Math.min(Math.max(x, 0), 1); return x*x*(3-2*x); }
function el(t, a, p){ var e=document.createElementNS(NS, t); for(var k in a) e.setAttribute(k, a[k]); if(p) p.appendChild(e); return e; }
function f1(v){ return Math.round(v*10)/10; }
function stars(){ var L=window._altoSolarLook; return !!window._ALTO_SOLAR && (L && L.get ? L.get()==='stars' : window._ALTO_SOLAR.look!=='hub'); }
function eligible(){ return !!window._ALTO_SOLAR && stars() && de.classList.contains('alto-solar') && !de.classList.contains('sk-retro') && !de.classList.contains('alto-editing') && (!de.classList.contains('mobile') || de.classList.contains('phone-whole')) && !!A(); }
function reduced(){ try{ return matchMedia('(prefers-reduced-motion: reduce)').matches; }catch(e){ return false; } }
function threeD(){ return de.classList.contains('sk-3d'); }

/* where the ship is now, in the layer's px: the chart's own ship (the 3D scene's projected), else the enlarged body, else the middle */
function where(ov, W, H){
  var z=(ov.getBoundingClientRect().width/ov.clientWidth)||1, p=null, q;
  try{ if(threeD() && window._altoSolar3D && window._altoSolar3D.ship){ q=window._altoSolar3D.ship(); if(q && q.sx!=null) p=[q.sx, q.sy]; } }catch(e){}
  if(!p){ q=document.querySelector('#world .sol-ship, #solar-svg .sol-ship, #solar-fly-svg .fly-craft'); var r=q && q.getBoundingClientRect();
    if(r && r.width) p=[(r.left+r.width/2)/z, (r.top+r.height/2)/z]; }
  if(!p && window._focusedNodeId){ q=document.getElementById('node-'+window._focusedNodeId); var r2=q && q.getBoundingClientRect(); if(r2 && r2.width) p=[(r2.left+r2.width/2)/z, (r2.top+r2.height/2)/z]; }
  if(!p) p=[W/2, H*.55];
  return [Math.min(W-40, Math.max(40, p[0])), Math.min(H-40, Math.max(40, p[1]))];
}

function build(d){
  var ov=document.createElement('div'); ov.id='bh'; ov.setAttribute('aria-hidden', 'true'); document.body.appendChild(ov);
  var W=ov.clientWidth, H=ov.clientHeight, ph=W<600, d3=threeD(), r=Math.min(H*(ph?.125:.14), W*.19), hx=W*(ph?.5:.58), hy=H*(ph?.42:.46);
  var svg=el('svg', {width:W, height:H, viewBox:'0 0 '+W+' '+H}, ov), df=el('defs', {}, svg);
  var fg=el('radialGradient', {id:'bh-fl'}, df); el('stop', {offset:'0', 'class':'bh-f0'}, fg); el('stop', {offset:'.35', 'class':'bh-f1'}, fg); el('stop', {offset:'1', 'class':'bh-f2'}, fg);
  var dg=el('linearGradient', {id:'bh-disc', x1:'0', y1:'0', x2:'1', y2:'0'}, df);        /* the approaching side (left) brighter: the Doppler */
  el('stop', {offset:'0', 'class':'bh-d0'}, dg); el('stop', {offset:'.55', 'class':'bh-d1'}, dg); el('stop', {offset:'1', 'class':'bh-d2'}, dg);
  var sp=el('radialGradient', {id:'bh-sp', cx:'50%', cy:'50%', r:'50%'}, df); el('stop', {offset:'.3', 'class':'bh-s0'}, sp); el('stop', {offset:'1', 'class':'bh-s1'}, sp);
  var veil=el('rect', {width:W, height:H, 'class':'bh-veil', opacity:0}, svg);
  var scene=el('g', {opacity:0}, svg);
  var bgs=el('path', {'class':'bh-stars'}, scene), arcs=el('path', {'class':'bh-sarc'}, scene);       /* stars (streaking in transit) and the few bent round the hole */
  var halo=el('circle', {cx:hx, cy:hy, r:r*5, fill:'url(#bh-sp)'}, scene);
  var hole=el('g', {transform:'translate('+hx+' '+hy+')'}, scene), rx=r*2.35, ry=rx*.28;
  el('ellipse', {rx:rx*1.02, ry:ry*1.02, 'class':'bh-out', fill:'none', 'stroke-width':r*.4}, hole);             /* the outer band, violet -> clear */
  var inn=el('ellipse', {rx:rx*.72, ry:ry*.72, 'class':'bh-in', fill:'none', 'stroke-width':r*.3, stroke:'url(#bh-disc)'}, hole);     /* the inner band, gold -> orange */
  var tur=el('ellipse', {rx:rx*.86, ry:ry*.86, 'class':'bh-turn', fill:'none', 'stroke-width':r*.12}, hole);    /* its turning light: dashes that go round */
  var back=el('g', {}, hole);                                                                                    /* behind the hole: the ship on the far side of it */
  el('circle', {r:r*1.16, fill:'none', 'class':'bh-ring', 'stroke-width':3}, hole);                              /* the photon ring */
  el('path', {d:'M'+(-r*1.28)+' 0A'+(r*1.28)+' '+(r*1.28)+' 0 0 1 '+(r*1.28)+' 0', 'class':'bh-lens', fill:'none', 'stroke-width':r*.16, transform:'translate(0 '+(-r*.1)+')'}, hole);   /* the disc's light bent over the top ... */
  el('path', {d:'M'+(-r*1.22)+' 0A'+(r*1.22)+' '+(r*1.22)+' 0 0 0 '+(r*1.22)+' 0', 'class':'bh-lens', fill:'none', 'stroke-width':r*.11, transform:'translate(0 '+(r*.1)+')'}, hole);    /* ... and under it */
  el('circle', {r:r, 'class':'bh-core'}, hole);
  el('circle', {r:r, 'class':'bh-rim', fill:'none', 'stroke-width':2}, hole);
  var near=el('path', {d:'M'+(-rx*1.02)+' 0A'+(rx*1.02)+' '+(ry*1.02)+' 0 0 0 '+(rx*1.02)+' 0', 'class':'bh-out', fill:'none', 'stroke-width':r*.4}, hole);       /* the disc's near half, over the hole */
  var near2=el('path', {d:'M'+(-rx*.72)+' 0A'+(rx*.72)+' '+(ry*.72)+' 0 0 0 '+(rx*.72)+' 0', 'class':'bh-in', fill:'none', 'stroke-width':r*.3, stroke:'url(#bh-disc)'}, hole);
  var front=el('g', {}, hole);                                                                                   /* in front of it: the ship on the near side */
  var ship=el('g', {'class':'fly-craft', opacity:0}, svg), pr=el('g', {'class':'fly-ship'}, ship), wp=el('path', {'class':'fly-warp'}, ship);
  pr.innerHTML=(A().get().svg||'')+(A().flames ? A().flames() : '');
  var fls=[0, 1].map(function(){ return el('circle', {r:1, fill:'url(#bh-fl)', opacity:0}, svg); });
  var wash=el('rect', {width:W, height:H, 'class':'bh-wash', opacity:0}, svg);
  return {svg:svg, ov:ov, W:W, H:H, r:r, hx:hx, hy:hy, rx:rx, ry:ry, veil:veil, scene:scene, bgs:bgs, arcs:arcs, halo:halo, hole:hole, inn:inn, tur:tur, back:back, front:front,
    near:near, near2:near2, ship:ship, pr:pr, wp:wp, fls:fls, wash:wash, d3:d3, ph:ph};
}
/* a fixed sky: x, y in 0-1, a size, a pace */
var SKY=(function(){ var a=[], i, s=7; function rnd(){ s=(s*16807)%2147483647; return s/2147483647; } for(i=0;i<84;i++) a.push([rnd(), rnd(), .4+rnd()*1.1, .3+rnd()]); return a; })();

function pips(d){
  var c=document.createElement('div'); c.id='bh-score'; var n=10, on=Math.round(Math.max(0, Math.min(100, d.p||0))/10), i, b;
  c.setAttribute('role', 'img'); c.setAttribute('aria-label', 'Score '+(d.s||0)+' of '+(d.n||0));
  for(i=0;i<n;i++){ b=document.createElement('i'); if(i<on) b.className='on'; c.appendChild(b); }
  document.body.appendChild(c); return c;
}
function start(d){
  var T=window._currentDetailType, I=window._currentDetailId, dp=document.getElementById('detail-page');
  R={d:d, type:T, id:I, st:dp ? dp.scrollTop : 0, t0:performance.now(), skip:-1};
  if(typeof showTimeline==='function') showTimeline();
  de.classList.add('bh-on');
  var v=build(d); R.v=v; R.score=pips(d); R.rd=reduced();
  R.P0=where(v.ov, v.W, v.H);
  var c=A().get(), cx=v.W/2-R.P0[0], cy=v.H/2-R.P0[1], l=Math.hypot(cx, cy)||1;
  R.dir=l<24 ? [1, 0] : [-cx/l, -cy/l];                      /* out and away: off the nearest edge */
  R.tv=A().travel ? A().travel(c.id, true) : null;
  R.DL=R.tv ? R.tv.S(LEAVE) : 1.8;
  R.tL=T1; R.tT=R.tL+R.DL; R.tA=R.tT+TR; R.tF=R.tA+TA; R.tB=R.tF+TF; R.tE=R.tB+TB;
  R.st2={hs:null, bk:0}; R.fin=false;
  if(R.rd){ R.tB=1; R.tE=1.4; }
  if(!dpObs && dp && typeof MutationObserver==='function'){ dpObs=new MutationObserver(function(){ if(chip && dp.classList.contains('visible')) gone(); }); dpObs.observe(dp, {attributes:true, attributeFilter:['class']}); }
  v.ov.addEventListener('click', function(){ if(performance.now()-R.t0>900) skip(); });
  setTimeout(function(){ if(R && !R.fin && !R.sk){ var b=document.createElement('button'); b.type='button'; b.id='bh-skip'; b.setAttribute('aria-label', 'Skip'); b.title='Skip';
    b.innerHTML='<svg viewBox="0 0 24 24" width="18" height="18"><path d="M6 6l6 6-6 6M13 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    b.onclick=function(e){ e.stopPropagation(); skip(); }; R.sk=b; v.ov.appendChild(b); } }, 900);
  cancelAnimationFrame(raf); raf=requestAnimationFrame(frame);
}
function key(e){
  if(R && !R.fin){ if(e.key==='Escape' || e.key==='Enter' || e.key===' '){ e.preventDefault(); e.stopPropagation(); if(e.key==='Escape') skip(); } return; }
  if(chip){ if(e.key==='Escape'){ e.preventDefault(); e.stopPropagation(); gone(); } else if(e.key==='Enter'){ e.preventDefault(); e.stopPropagation(); again(); } }
}
function skip(){ if(!R || R.fin) return; var now=performance.now(), t=(now-R.t0)/1000; if(t<R.tB) R.t0=now-R.tB*1000; }

function frame(now){
  raf=0; if(!R) return; var v=R.v, t=(now-R.t0)/1000;
  if(t>=R.tE) return finish();
  draw(v, t, now);
  raf=requestAnimationFrame(frame);
}
function to(v, g, before){ if(v.ship.parentNode!==g) g.insertBefore(v.ship, before || null); }
function pathAt(x){ var m=R.tv ? R.tv.map(x) : x*x, L=1.15*Math.max(R.v.W, R.v.H); return [R.P0[0]+R.dir[0]*L*m, R.P0[1]+R.dir[1]*L*m]; }
function flash(c, p, k, rad){ if(k<.01 || !p){ c.setAttribute('opacity', 0); return; } c.setAttribute('cx', f1(p[0])); c.setAttribute('cy', f1(p[1])); c.setAttribute('r', f1(rad)); c.setAttribute('opacity', f1(Math.min(1, k)*100)/100); }
function setShip(v, p, h, bk, k, now, o){
  var a=A(), c=a.get(); o=o||{};
  v.ship.setAttribute('transform', a.xf(p, h, bk, k)); v.ship.setAttribute('opacity', o.vis==null ? 1 : Math.round(o.vis*100)/100);
  var sx=o.sx||0, e={m:o.m||0, r:0, f:0}, S=v.ph ? .6 : .8;
  v.pr.setAttribute('transform', 'scale('+Math.round(S*(1+1.2*sx+(o.st||0))*100)/100+' '+Math.round(S*(1-.25*sx-.35*(o.st||0))*100)/100+')');
  if(a.burn && e.m>.02) a.burn(v.pr, e, now); else if(a.burn && v.pr._fl) a.burn(v.pr, {m:0, r:0, f:0}, now);
  v.wp.setAttribute('d', sx>.02 && a.streaks ? a.streaks(sx, now) : '');
  if(c.spin){ var spn=v.ship.querySelector('.sh-spin'); if(spn) spn.setAttribute('transform', 'rotate('+f1(now/1000*c.spin*57.3%360)+')'); }
}
function draw(v, t, now){
  var P0=R.P0, tv=R.tv, W=v.W, H=v.H, x, p, fx, h=Math.atan2(R.dir[1], R.dir[0]), sc=ss(t/.35);
  if(R.rd){                                         /* reduced motion: a fade to the hole, a dim, a fade back; the disc static */
    var o=t<.4 ? ss(t/.4) : t<R.tB ? 1 : 1-ss((t-R.tB)/.4);
    v.veil.setAttribute('opacity', f1(100*o)/100); v.scene.setAttribute('opacity', f1(100*o)/100); v.ship.setAttribute('opacity', 0); v.halo.setAttribute('opacity', 1);
    v.hole.setAttribute('opacity', 1); sky(v, 0, 0, 1); R.score.style.opacity=1-o*.6; return;
  }
  R.score.style.opacity=Math.min(ss(t/.3), 1-ss((t-R.tT)/.4));
  /* the hole's turn and the sky (their own slow clocks) */
  v.tur.setAttribute('stroke-dasharray', f1(v.r*.9)+' '+f1(v.r*1.4)); v.tur.setAttribute('stroke-dashoffset', f1(-(now/6000)*(v.r*2.3)*6.28));
  if(t<R.tL){                                       /* 1  the chart, the score; the ship waits where it is */
    v.veil.setAttribute('opacity', 0); v.scene.setAttribute('opacity', 0);
    setShip(v, P0, h, 0, 1, now, {vis:sc}); return;
  }
  if(t<R.tT){                                       /* 2-3  the wind-up and the leaving */
    x=Math.min(1, (t-R.tL)/R.DL); fx=tv ? tv.fx(x) : {vis:1, warp:0, fa:0, fb:0, fw:0, wu:ss(x*3), ws:0, cg:0, gr:0};
    p=pathAt(x); var m=Math.max(fx.wu||0, tv ? 0 : ss(x*2)), sx=Math.max(fx.warp||0, fx.ws||0);
    setShip(v, p, h, 0, 1, now, {vis:fx.vis, sx:sx, m:m});
    flash(v.fls[0], fx.fa || fx.fw ? P0 : null, Math.max(fx.fa||0, fx.fw||0), 16+40*Math.max(fx.fa||0, fx.fw||0));
    flash(v.fls[1], fx.cg>.01 ? p : null, fx.cg||0, fx.gr||16+40*(fx.cg||0));
    v.veil.setAttribute('opacity', f1(100*ss((x-.5)/.5))/100); v.scene.setAttribute('opacity', f1(100*ss((x-.5)/.5))/100); v.hole.setAttribute('opacity', 0); v.halo.setAttribute('opacity', 0); sky(v, 0, now, 0);
    return;
  }
  v.veil.setAttribute('opacity', 1); v.fls[0].setAttribute('opacity', 0);
  if(t<R.tA){                                       /* 3  the stars streak, then settle */
    var q=(t-R.tT)/TR; v.scene.setAttribute('opacity', 1); v.ship.setAttribute('opacity', 0); v.hole.setAttribute('opacity', 0); v.halo.setAttribute('opacity', 0);
    sky(v, Math.sin(Math.PI*q), now, q); v.fls[1].setAttribute('opacity', 0); return;
  }
  var a=Math.min(1, (t-R.tA)/TA), u=Math.max(0, Math.min(1, (t-R.tF)/TF)), k=ss(a);
  v.hole.setAttribute('opacity', 1); v.halo.setAttribute('opacity', f1(100*k)/100);
  v.hole.setAttribute('transform', 'translate('+v.hx+' '+v.hy+') scale('+f1(100*(.6+.4*k))/100+')');
  sky(v, 0, now, 1);
  var r0=v.r*3.4, rE=v.r*.3;
  if(R.rd){ v.ship.setAttribute('opacity', 0); }
  else if(t<R.tF){                                  /* 4  it comes out ahead: a flash, or in at speed */
    var S0=[v.hx-r0, v.hy], mode=tv ? tv.mode : null, vis=mode==='jump' ? ss((a-.25)/.15) : 1, E=[S0[0]-.55*W*(1-ss(a)), S0[1]];
    var pos=mode==='jump' ? S0 : [E[0], E[1]], st=mode==='warp' ? 1-ss(a/.8) : 0;
    setShip(v, pos, -0.3, 0, 1, now, {vis:vis, sx:st, m:mode==='jump' ? 0 : .6*(1-a)});
    flash(v.fls[1], mode==='jump' ? S0 : null, mode==='jump' ? Math.sin(Math.PI*Math.min(1, a/.6))*.9 : 0, mode==='jump' ? 16+50*Math.sin(Math.PI*Math.min(1, a/.6)) : 0);
    to(v, v.svg, v.fls[0]);
  } else if(t<R.tB){                                /* 5  the fall */
    var th=Math.PI+5.4*Math.PI*Math.pow(u, 1.35), rr=r0*Math.pow(rE/r0, Math.pow(u, 1.4)), sq=.3;
    var xy=function(uu){ var tt=Math.PI+5.4*Math.PI*Math.pow(uu, 1.35), r2=r0*Math.pow(rE/r0, Math.pow(uu, 1.4)); return [r2*Math.cos(tt), r2*Math.sin(tt)*sq]; };
    var c0=xy(u), c1=xy(Math.min(1, u+.004)), hd=Math.atan2(c1[1]-c0[1], c1[0]-c0[0]), s1=Math.sin(th)>0;      /* (sin > 0: the near side) */
    to(v, s1 ? v.front : v.back);
    var depth=.55+.45*(rr/r0);
    setShip(v, [c0[0], c0[1]], hd, 0, depth, now, {vis:1-ss((u-.9)/.1), st:ss(u)*.6, m:.3*(1-u)});
    flash(v.fls[1], null, 0, 0);
    if(v.d3){ var ln=''; for(var i=0;i<26;i++){ var an=i*.2417+u, ra=v.r*(2.6+((i*37)%11)/3), l2=ra*(.25+.5*u*u); ln+='M'+f1(v.hx+Math.cos(an)*ra)+' '+f1(v.hy+Math.sin(an)*ra*.8)+'L'+f1(v.hx+Math.cos(an)*(ra-l2*u))+' '+f1(v.hy+Math.sin(an)*(ra-l2*u)*.8); } v.arcs.setAttribute('d', ln); }
    var w=ss((u-.88)/.12); v.wash.setAttribute('opacity', f1(100*w)/100);
    v.near.setAttribute('opacity', 1); v.near2.setAttribute('opacity', 1);
    var fr=Math.max(0, (u-.82)/.18); flash(v.fls[0], u>.8 ? [v.hx, v.hy] : null, Math.sin(Math.PI*Math.min(1, fr))*.95, 30+v.H*.5*fr);
  } else {                                          /* 6  home: the ship where it left, the hole dissolving */
    var b=(t-R.tB)/TB, e=ss(b);
    to(v, v.svg, v.fls[0]);
    v.wash.setAttribute('opacity', f1(100*(1-ss(b/.5)))/100); v.veil.setAttribute('opacity', f1(100*(1-e))/100); v.scene.setAttribute('opacity', f1(100*(1-e))/100);
    flash(v.fls[0], null, 0, 0);
    var bob=-7*Math.sin(Math.PI*Math.min(1, b*1.3))*(1-b), sc2=.55+.45*ss(b/.7);
    setShip(v, [P0[0], P0[1]+bob], h, 0, sc2, now, {vis:ss(b/.25), m:.4*(1-b)});
  }
}
/* the sky: stars that streak out from the middle in transit (q 0-1), settled after; and a few bent round the hole once it is there */
function sky(v, str, now, q){
  var d='', i, a, W=v.W, H=v.H, cx=W/2, cy=H/2, s, x, y, L, dx, dy, n=SKY.length;
  for(i=0;i<n;i++){ a=SKY[i]; x=a[0]*W; y=a[1]*H; dx=x-cx; dy=y-cy; L=Math.hypot(dx, dy)||1;
    var ln=str*(40+a[3]*220)*(1+L/W), tw=.5+.5*Math.sin(now/700*a[3]+i);
    if(str>.01){ d+='M'+f1(x)+' '+f1(y)+'l'+f1(dx/L*(ln+a[2]))+' '+f1(dy/L*(ln+a[2])); } else d+='M'+f1(x)+' '+f1(y)+'h'+f1(a[2]*(1+tw)); }
  v.bgs.setAttribute('d', d); v.bgs.setAttribute('stroke-width', 1.2);
  if(q>=1 && !v.d3){ var s2='', j; for(j=0;j<14;j++){ var aa=SKY[j], ang=j*.45, rr2=v.r*(3.1+(j%5)*.55); s2+='M'+f1(v.hx+Math.cos(ang)*rr2)+' '+f1(v.hy+Math.sin(ang)*rr2*.9)+'a'+f1(rr2)+' '+f1(rr2*.9)+' 0 0 1 '+f1(8+aa[2]*7)+' '+f1(2+aa[2]*3); } v.arcs.setAttribute('d', s2); }
  else if(q<1 && !v.d3) v.arcs.setAttribute('d', '');
}

function finish(){
  if(!R) return; var v=R.v, d=R.d; R.fin=true;
  var P0=R.P0; if(v.ov.parentNode) v.ov.parentNode.removeChild(v.ov); if(R.score.parentNode) R.score.parentNode.removeChild(R.score);
  de.classList.remove('bh-on');
  offer(P0, d); R=null;
}
function offer(P0, d){
  gone(); var z=1, c=document.createElement('div'); c.id='bh-chip'; c.setAttribute('role', 'group');
  var go=document.createElement('button'); go.type='button'; go.className='bh-go'; go.title='Try again'; go.setAttribute('aria-label', 'Try again');
  go.innerHTML='<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M20 12a8 8 0 1 1-2.6-5.9M20 4v5h-5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg><span>Try again</span>';
  var x=document.createElement('button'); x.type='button'; x.className='bh-x'; x.title='Dismiss'; x.setAttribute('aria-label', 'Dismiss');
  x.innerHTML='<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>';
  go.onclick=again; x.onclick=gone; c.appendChild(go); c.appendChild(x); document.body.appendChild(c); chip=c;
  last=performance.now();
  /* beside the ship, never near the page edge */
  var W=c.parentNode.clientWidth || innerWidth, H=c.parentNode.clientHeight || innerHeight, w=c.offsetWidth, h=c.offsetHeight;
  var l=P0[0]+34, tp=P0[1]-h/2; if(l+w>W-16) l=P0[0]-34-w; l=Math.max(16, Math.min(W-w-16, l)); tp=Math.max(70, Math.min(H-h-16, tp));
  c.style.left=Math.round(l)+'px'; c.style.top=Math.round(tp)+'px'; chip._d=d;
  setTimeout(function(){ try{ go.focus({preventScroll:true}); }catch(e){} }, 30);
}
function gone(){ if(chip){ if(chip.parentNode) chip.parentNode.removeChild(chip); chip=null; } }
/* "Try again": the same page the quiz was on, the quiz fresh and in view */
var BACK=null;
function again(){
  var b=BACK; if(!chip || !b) return; gone();
  try{ if(typeof showDetail==='function' && b.type && b.id) showDetail(b.type, b.id); }catch(e){}
  var dp=document.getElementById('detail-page'), n=0;
  (function go(){ var box=document.querySelector('.ast-quiz[data-ast-key="'+b.key+'"]');
    if(box){ if(box._retake) box._retake(); try{ box.scrollIntoView({block:'start'}); }catch(e){} return; }
    if(dp && n++<30) setTimeout(go, 50); else if(dp) dp.scrollTop=b.st||0; })();
}
/* (registered here, at load, ahead of the flight's own Esc, which would end a flight and swallow the key: this one answers first) */
window.addEventListener('keydown', key, true);
window.addEventListener('alto-quiz-fail', function(e){
  var d=(e && e.detail) || {}; if(R || !eligible() || performance.now()-last<COOL) return;
  BACK={type:window._currentDetailType, id:window._currentDetailId, st:(document.getElementById('detail-page')||{}).scrollTop||0, key:d.key};
  last=performance.now(); try{ start(d); }catch(x){ R=null; de.classList.remove('bh-on'); if(window.console) console.warn('alto black hole', x); }
});
window._altoHole={state:function(){ return R ? {t:(performance.now()-R.t0)/1000, end:R.tE, mode:R.tv ? R.tv.mode : null, rd:R.rd, skipBtn:!!R.sk} : (chip ? {chip:true} : null); }, skip:skip, again:again, dismiss:gone, reset:function(){ last=-1e9; }};
})();
"""

HOLE_CSS = r"""
  #bh{position:fixed;left:0;top:0;right:0;bottom:0;z-index:900;overflow:hidden;cursor:default;}
  #bh svg{position:absolute;left:0;top:0;width:100%;height:100%;display:block;}
  html.bh-on :is(.sol-ship,#solar-fly-svg){visibility:hidden !important;}
  #bh .bh-veil{fill:#07061a;} html.sk-3d #bh .bh-veil{fill:#02030a;}
  #bh .bh-stars{fill:none;stroke:#e9e4ff;stroke-linecap:round;stroke-opacity:.85;} #bh .bh-sarc{fill:none;stroke:#e9e4ff;stroke-opacity:.5;stroke-width:1.2;stroke-linecap:round;}
  #bh .bh-s0{stop-color:#000;stop-opacity:.85;} #bh .bh-s1{stop-color:#000;stop-opacity:0;}
  #bh .bh-core{fill:#000;} #bh .bh-rim{stroke:#d9c7ff;stroke-opacity:.9;}
  #bh .bh-ring{stroke:#fff4d6;stroke-opacity:.9;}
  #bh .bh-out{stroke:#b36bff;stroke-opacity:.38;} html.sk-3d #bh .bh-out{stroke:#8f5bff;stroke-opacity:.45;}
  #bh .bh-d0{stop-color:#ffe6a8;} #bh .bh-d1{stop-color:#ffd27a;} #bh .bh-d2{stop-color:#ff8a3d;}
  html.sk-3d #bh .bh-d0{stop-color:#ffd9a0;} html.sk-3d #bh .bh-d1{stop-color:#ffb347;} html.sk-3d #bh .bh-d2{stop-color:#ff5a1f;}
  #bh .bh-in{stroke-opacity:.92;} #bh .bh-turn{stroke:#fff4d6;stroke-opacity:.28;}
  #bh .bh-lens{stroke:#ffd27a;stroke-opacity:.22;}
  #bh .bh-f0{stop-color:#fff;stop-opacity:1;} #bh .bh-f1{stop-color:#ffe9b0;stop-opacity:.6;} #bh .bh-f2{stop-color:#ffd27a;stop-opacity:0;}
  #bh .bh-wash{fill:#fff4d6;}
  #bh .fly-warp{fill:none;stroke:#cfe6ff;stroke-opacity:.75;stroke-width:1.1;stroke-linecap:round;}
  #bh-score{position:fixed;left:50%;top:76px;transform:translateX(-50%);z-index:901;display:flex;gap:5px;padding:7px 11px;border-radius:14px;
    background:rgba(10,13,28,.72);border:1px solid rgba(170,190,255,.28);opacity:0;pointer-events:none;}
  #bh-score i{width:9px;height:9px;border-radius:50%;border:1.5px solid #a78bfa;background:transparent;display:block;} #bh-score i.on{background:#a78bfa;}
  #bh-skip{position:absolute;right:18px;bottom:22px;width:38px;height:38px;border-radius:50%;border:1px solid rgba(255,255,255,.35);background:rgba(10,13,28,.6);color:#eef2ff;
    cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0;}
  #bh-skip:hover{background:rgba(255,255,255,.18);}
  #bh-chip{position:fixed;z-index:901;display:flex;align-items:center;gap:4px;padding:5px 6px 5px 5px;border-radius:999px;background:rgba(10,13,28,.9);
    border:1px solid rgba(167,139,250,.6);box-shadow:0 8px 28px rgba(0,0,0,.45);color:#eef2ff;font:600 12px/1 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}
  #bh-chip button{display:inline-flex;align-items:center;gap:6px;border:0;background:transparent;color:inherit;font:inherit;cursor:pointer;border-radius:999px;padding:7px 10px;}
  #bh-chip .bh-go{background:#a78bfa;color:#120c2a;} #bh-chip .bh-go:hover{background:#c4b0ff;} #bh-chip .bh-x{padding:7px;opacity:.75;} #bh-chip .bh-x:hover{opacity:1;background:rgba(255,255,255,.12);}
  @media print{ #bh,#bh-score,#bh-chip{display:none !important;} }
"""

from .solar_draw import _slim  # noqa: E402

HOLE_JS = _slim(HOLE_JS)
HOLE_CSS = _slim(HOLE_CSS)
