"""What the browser draws and does for a solar outline (brief.layout "solar").

solar.py plans the systems (window._ALTO_SOLAR: every circle's t = 0 centre,
its role, diameter and orbit period); the page puts the centres where the plan
says through the tree's own plan runner. This module is the rest, on desktop
only (a phone keeps the engine's column of cards):

* Circles. A resting .node-card is a disc of the plan's diameter showing the
  path number and the title, clamped (.sol-face). Enlarged (the engine's own
  focus fly and zoom ramp) it is the ordinary card again, description and
  chips and all: while the card grows it is clipped from its disc out to the
  card (clip-path inset() from a centred circle to the whole card, taken from
  the card's own zoom on every frame), and back down to the disc as it
  shrinks, so neither end of the ramp jumps. The engine's .alto-fshadow is a
  card's, which is right: the enlarged thing is a card.
* #solar-svg, under the cards: faint orbit rings (one per planet round its
  sun, one shared by a planet's moons, one by a moon's satellites), a short
  spoke from each body to what it orbits, a faint dashed link between suns, a
  soft glow behind each sun. The "spoke" style has no rings and draws its
  spokes as Alto's own tubes; nothing moves. The engine's unit bands, labels
  and bars go (as on a horizontal timeline); a chip names each system.
* Motion ("orbit"). One rAF loop turns every body round what it orbits by
  2π·t/period from its plan centre (solar.py periods and spin) and, with
  several systems, each system slowly as a whole about its own sun (inside its
  R, never toward a neighbour). Bodies move by their own left/top — the D-GRID
  margin centring keeps them centred; never a transform (engine_patches,
  1.8.28) — rounded to device px so text stays crisp. It stops at once on
  hover (a card or a line), focus, a search ring, dimmed cards, the detail
  page, edit mode (where it also turns back to t = 0, the plan's layout),
  print, a hidden tab and prefers-reduced-motion, and eases back in. The
  connections are drawn as straight Alto tubes edge to edge between circles
  and kept on them every frame, with their data-edge-hit paths and the Blink
  card mask's holes.
* Arrow keys pick the nearest body that way from where the bodies are now
  (focusing freezes the orbit, so the fly lands where the card is).

* Edit mode: window._altoSolarSync(tables) plans the systems again from the
  live outline (SOLAR_PLAN_JS, solar_plan in JS) before the page lays out.

The engine hooks (engine_patches.py): solar-layout-hook (end of initLayout),
solar-lines-hook (the base redraw), solar-card-mask-round/-follows, and lines added to the
D-GRID script (a circle grows from its centre; content moving under a still
pointer is not a hover) and to focusNeighbor (window._altoSolarNav).
"""
from __future__ import annotations

import json

from .solar import GOLDEN, LOOK_FLAGS, SOLAR, SPIN

SOLAR_CSS = r"""
  html.alto-solar:not(.mobile) #world .phase-band,html.alto-solar:not(.mobile) #world .phase-label-float,html.alto-solar:not(.mobile) #world .unit-bar{display:none !important;}
  #solar-svg{position:absolute;left:0;top:0;z-index:5;pointer-events:none;overflow:visible;}
  html.mobile #solar-svg,html.mobile .sol-unit,html.mobile .sol-face{display:none !important;}
  #solar-svg .sol-ring{fill:none;stroke:color-mix(in srgb,var(--u,var(--text)) 45%,var(--text));stroke-opacity:.2;stroke-width:1.25;}
  #solar-svg .sol-ring.sol-m{stroke-opacity:.15;stroke-width:1;}
  #solar-svg .sol-spoke{stroke:color-mix(in srgb,var(--u,var(--text)) 40%,var(--text));stroke-opacity:.34;stroke-width:1.6;stroke-linecap:round;}
  #solar-svg .sol-link{fill:none;stroke:var(--text);stroke-opacity:.2;stroke-width:1.6;stroke-dasharray:1.5 7;stroke-linecap:round;}
  #solar-svg .sol-tube{fill:none;stroke:rgb(60,64,84);stroke-opacity:.92;stroke-width:4.2;stroke-linecap:round;}
  #solar-svg .sol-sheen{fill:none;stroke:rgba(255,255,255,.72);stroke-width:1.43;stroke-linecap:round;}
  #solar-svg .sol-tube.sol-l{stroke-opacity:.3;stroke-width:3;}
  #solar-svg .sol-sheen.sol-l{stroke-opacity:.5;stroke-width:1;}
  html.dark #solar-svg .sol-tube{stroke:rgb(208,212,226);}
  html.dark #solar-svg .sol-sheen{stroke:rgba(255,255,255,.5);}
  html:not(.mobile) #canvas #solar-svg{transition:opacity var(--alto-fly,.25s) var(--alto-ease,ease);}
  html:not(.mobile) #canvas.focus-mode #solar-svg{opacity:.1;}
  html:not(.mobile) #canvas.edge-hover #solar-svg{opacity:.35;}
  .sol-unit{position:absolute;z-index:6;white-space:nowrap;pointer-events:none;font-size:12.5px;font-weight:800;letter-spacing:.12em;
    text-transform:uppercase;color:var(--u);padding:6.25px 12.5px;border-radius:10px;background:color-mix(in srgb,var(--surface) 80%,transparent);
    border:1.5px solid color-mix(in srgb,var(--u) 45%,transparent);}
  .sol-unit b{font-weight:800;opacity:.6;margin-right:7.5px;}
  html.dark .sol-unit{color:color-mix(in srgb,var(--u) 55%,#fff);}
  /* the whole chart (zoomed out to fit): its toggle is the key toggle's round glass, under the bars */
  #sol-fit{position:fixed;z-index:310;left:30px;top:calc(var(--nav-bottom, 100px) + 14px);width:35px;height:35px;box-sizing:border-box;padding:0;
    border-radius:50%;display:flex;align-items:center;justify-content:center;cursor:pointer;color:var(--muted);
    background:var(--card-glass-bg, var(--surface));-webkit-backdrop-filter:blur(18px) saturate(190%);backdrop-filter:blur(18px) saturate(190%);
    border:1px solid var(--card-glass-border, var(--border));box-shadow:0 10px 26px var(--node-rest-shadow), inset 0 0 0 0.5px var(--card-glass-rim);}
  #sol-fit:hover{color:var(--text);border-color:var(--muted);}
  #sol-fit.active{color:var(--accent, #6d5bd0);border-color:var(--accent, #6d5bd0);}
  html.mobile #sol-fit,html.alto-editing #sol-fit{display:none !important;}
  @media print{ #sol-fit{display:none !important;} }
  #canvas.sol-ov{cursor:zoom-in;}
  #canvas.sol-ov #world,#canvas.sol-ovanim #world{pointer-events:none;transform-origin:0 0;will-change:transform;}
  .sol-face{display:none;}
  /* enlarged: on top at once (the engine holds a node's z-index change back .34s,
     for a card shrinking home; a moon beside its planet would cover the card) */
  html.alto-solar:not(.mobile) #world .node[data-solar].focused{transition:z-index 0s !important;}
  html.alto-solar:not(.mobile) #world .node[data-solar]:not(.focused):not(.sol-closing) .node-card{width:var(--sd) !important;height:var(--sd) !important;
    min-height:0 !important;padding:0 !important;border-radius:50% !important;border-top-width:1.5px;overflow:hidden;box-sizing:border-box;}
  html.alto-solar:not(.mobile) #world .node[data-solar]:not(.focused):not(.sol-closing) .node-card>:not(.sol-face){display:none !important;}
  html.alto-solar:not(.mobile) #world .node[data-solar]:not(.focused):not(.sol-closing) .node-card::before{left:0;right:0;top:0;height:100%;border-radius:50%;
    background:radial-gradient(ellipse 72% 52% at 50% 14%,var(--card-glass-sheen) 0%,rgba(255,255,255,.08) 58%,rgba(255,255,255,0) 100%);}
  html.alto-solar:not(.mobile) #world .node[data-solar] .sol-face{display:flex;position:absolute;left:50%;top:50%;width:var(--sd);height:var(--sd);
    margin:calc(var(--sd) / -2) 0 0 calc(var(--sd) / -2);flex-direction:column;align-items:center;justify-content:center;gap:2.5px;
    text-align:center;box-sizing:border-box;padding:0 calc(var(--sd) * .15);pointer-events:none;color:var(--text);}
  html.alto-solar:not(.mobile) #world .node[data-solar].focused:not(.sol-clip) .sol-face{display:none;}
  .sol-face b{font-weight:600;font-variant-numeric:tabular-nums;opacity:.72;font-size:10px;line-height:12.5px;letter-spacing:.02em;}
  .sol-face span{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;line-clamp:3;overflow:hidden;
    overflow-wrap:break-word;hyphens:auto;-webkit-hyphens:auto;font-size:12.5px;line-height:15px;max-width:100%;}
  .node[data-solar=sun] .sol-face b{font-size:12.5px;line-height:15px;}
  .node[data-solar=sun] .sol-face span{font-size:16.25px;line-height:20px;-webkit-line-clamp:4;line-clamp:4;}
  .node[data-solar=moon] .sol-face{gap:1.25px;}
  .node[data-solar=moon] .sol-face b{font-size:8.75px;line-height:10px;}
  .node[data-solar=moon] .sol-face span{font-size:8.75px;line-height:10px;-webkit-line-clamp:2;line-clamp:2;}
  .node[data-solar=sat] .sol-face span{display:none;}
  .node[data-solar=sat] .sol-face b{font-size:10px;opacity:.85;}
  html.alto-solar:not(.mobile) #world .node[data-solar].focused .node-card,html.alto-solar:not(.mobile) #world .node[data-solar].sol-closing .node-card{min-height:var(--sd);}
  html.alto-solar:not(.mobile) #world .node.sol-clip .node-card{clip-path:inset(var(--scy,0px) var(--scx,0px) round var(--scr,14px));
    -webkit-clip-path:inset(var(--scy,0px) var(--scx,0px) round var(--scr,14px));-webkit-backdrop-filter:none !important;backdrop-filter:none !important;
    background:var(--node-glass-bg,var(--panel-glass-bg)) !important;}
  html.alto-solar:not(.mobile) #world .node.sol-clip .node-card>:not(.sol-face){opacity:var(--sbo,1);}
  html.alto-solar:not(.mobile) #world .node.sol-clip .sol-face{opacity:var(--sfo,0);}
"""

SOLAR_JS = r"""
/* The renderer: a function of the plan (window._ALTO_SOLAR's shape) mounted on
   the engine's #world; opt.orbit (default: plan.style !== 'spoke') says whether
   it moves. One mount per page (its engine hooks are page globals). */
window._altoSolarMount=function(S, opt){
opt=opt||{}; if(!S || !S.nodes || window._altoSolarMounted) return false; window._altoSolarMounted=true;
var de=document.documentElement, NS='http://www.w3.org/2000/svg', TAU=Math.PI*2, K=1.7;
var ORBIT, SPIN, DEF=S.sizes||{sun:184, planet:108, moon:62, sat:34}, NUM=null;
function desk(){ return !de.classList.contains('mobile'); }
if(desk()) de.classList.add('alto-solar');
/* the bodies, each after what it orbits */
var B={}, ORD=[], SY=[], MOVES=false;
function q(v){ return Math.round(v/2.5)*2.5; }      /* D-GRID: half a diameter on the 1.25px grid */
function body(id, role, p, per, si){
  var n=S.nodes[id]||{}; B[id]={id:id, role:role, p:p, per:ORBIT ? (+per||0) : 0, si:si, d:q(n.d||DEF[role])}; ORD.push(id); }
function bodies(){
  ORBIT=opt.orbit!=null ? !!opt.orbit : S.style!=='spoke'; SPIN=S.spin||-1; B={}; ORD=[]; SY=S.systems||[];
  SY.forEach(function(s, si){ body(s.sun, 'sun', null, 0, si);
    (s.planets||[]).forEach(function(pl){ body(pl.id, 'planet', s.sun, pl.period, si);
      (pl.moons||[]).forEach(function(m){ body(m.id, 'moon', pl.id, m.period, si);
        (m.sats||[]).forEach(function(t){ body(t.id, 'sat', m.id, t.period, si); }); }); }); });
  MOVES=ORBIT && ORD.some(function(i){ return B[i].per>0; });
}
bodies();
var world=null, svg=null, PAD=0, zq=1, links=[], spokes=[], rings=[], sunl=[], chips=[], ready=false;
function el(t, a, p){ var e=document.createElementNS(NS, t); for(var k in a) e.setAttribute(k, a[k]); if(p) p.appendChild(e); return e; }
function f2(v){ return Math.round(v*100)/100; }
function rd(v){ return Math.round(v*zq)/zq; }
function unitColor(si){ var pm=(typeof PHASE_META!=='undefined') ? PHASE_META[(SY[si]||{}).unit] : null; return pm ? pm.colorRaw : ''; }
/* the face a resting circle shows: its path number and title */
function face(n, id){
  var c=n.querySelector('.node-card'); if(!c) return;
  var f=c.querySelector('.sol-face'); if(!f){ f=document.createElement('div'); f.className='sol-face'; f.innerHTML='<b></b><span></span>'; c.appendChild(f); }
  var num=(NUM && NUM[id]) || (typeof NODE_ORDER_MAP!=='undefined' && NODE_ORDER_MAP[id]) || '', t=c.querySelector('.node-title'), tt=t ? t.textContent : '';
  var b=B[id];
  f.querySelector('b').textContent=b.role==='sat' ? (num.split(/[.\-]/).pop()||num) : num;
  var sp=f.querySelector('span'), base={sun:16.25, planet:12.5, moon:8.75}[b.role], L=Math.max.apply(null, tt.split(/\s+/).map(function(w){ return w.length; }).concat([1]));
  sp.textContent=tt; sp.style.fontSize=sp.style.lineHeight='';
  /* a word too long for the disc: the type steps down (to 72%) before a word is broken */
  var fs=base ? Math.max(base*.72, Math.min(base, b.d*.68/(L*.55))) : 0;
  if(fs && fs<base){ fs=Math.round(fs*4)/4; sp.style.fontSize=fs+'px'; sp.style.lineHeight=Math.round(fs*1.2*4)/4+'px'; }
  f.setAttribute('aria-hidden', 'true');
  if(b.role==='sat') c.setAttribute('title', (num ? num+'  ' : '')+tt);
}

/* ── the layout: at the end of initLayout (engine patch solar-layout-hook),
   before the lines are drawn. Every body's home is its plan centre. */
window._altoSolarLayout=function(pos){
  if(!desk()) return;
  world=document.getElementById('world'); if(!world) return;
  de.classList.add('alto-solar');
  PAD=(typeof WORLD_PAD_TOP!=='undefined') ? WORLD_PAD_TOP : 0;
  zq=(parseFloat(getComputedStyle(de).zoom)||1)*(window.devicePixelRatio||1);
  var NM={};
  if(typeof NODES!=='undefined') NODES.forEach(function(n){ NM[n.id]=n; });
  ORD.forEach(function(id){
    var b=B[id], n=document.getElementById('node-'+id), P=S.nodes[id]||{};
    b.n=n; b.c=n ? n.querySelector('.node-card') : null; if(!n) return;
    /* the plan's centre: circles are never dragged, and whatever the page's
       plan runner did (edit mode lays a tree out with its own; initLayout's
       numeral check nudges cards at the right edge) the orbit is the plan's */
    b.hx=P.x; b.hy=P.y+PAD;
    if(pos) pos[id]=P.y;
    n.setAttribute('data-solar', b.role); n.style.setProperty('--sd', b.d+'px');
    b.rx=b.ry=null; b.x=b.hx; b.y=b.hy;
    if(NM[id]){ NM[id].displayX=b.hx; NM[id].y=b.hy-PAD; }
    face(n, id);
  });
  var W=Math.max(1700, (S.world||{}).w||0), H=((S.world||{}).h||0)+PAD;
  ORD.forEach(function(id){ var b=B[id]; if(b.n) H=Math.max(H, b.hy+b.d/2+115); });
  slab(W, H);
  var rv=document.getElementById('river-svg'); if(rv){ rv.setAttribute('height', H); if(W>1700) rv.setAttribute('width', W); }
  draw(W, H);
  ready=true; hov=0;
  apply(true);
  if(MOVES) go();
  if(OV){ ovHold(true); clampO(OV); ovSet(OV); }
  fitBtn();
};
/* the board is the plan's size: the glass behind it (whose end the page's
   height follows), tinted down the page by the systems' unit colours */
function slab(W, H){
  var sl=document.getElementById('glass-slab');
  if(W>1700){ world.style.setProperty('width', W+'px', 'important'); if(sl) sl.style.setProperty('width', W+'px', 'important'); }
  world.style.minHeight=H+'px';
  if(!sl) return;
  var cs=getComputedStyle(world), pads=(parseFloat(cs.paddingTop)||0)+(parseFloat(cs.paddingBottom)||0);
  var t0=parseFloat(sl.style.top)||0, sh=Math.max(1, H+pads-t0), st=[], seen={};   /* the page fits #world's min-height to the glass's end, less its padding */
  sl.style.height=sh+'px';
  SY.forEach(function(s, si){ var b=B[s.sun], c=unitColor(si); if(!b || !c || seen[Math.round(b.hy)]) return; seen[Math.round(b.hy)]=1;
    st.push({p:Math.max(0, Math.min(100, (b.hy-t0)/sh*100)), c:c}); });
  st.sort(function(a, b){ return a.p-b.p; });
  if(!st.length) return;
  sl.style.backgroundImage='linear-gradient(180deg, '+st[0].c+'b3 0%, '+st.map(function(q){ return q.c+'b3 '+q.p.toFixed(1)+'%'; }).join(', ')+', '+st[st.length-1].c+'b3 100%)';
  window._headerTint={slabTop:t0, slabH:sh, stops:[{p:0, c:st[0].c}].concat(st, [{p:100, c:st[st.length-1].c}])};
  if(window.updateHeaderTint) try{ window.updateHeaderTint(); }catch(e){}
}
/* rings, spokes, sun links, glows, the systems' chips */
function draw(W, H){
  var old=document.getElementById('solar-svg'); if(old) old.remove();
  world.querySelectorAll('.sol-unit').forEach(function(e){ e.remove(); });
  svg=el('svg', {id:'solar-svg', width:W, height:H, 'aria-hidden':'true'});
  var rv=document.getElementById('river-svg');
  world.insertBefore(svg, rv && rv.parentNode===world ? rv : world.firstChild);
  var defs=el('defs', {}, svg); spokes=[]; rings=[]; sunl=[]; chips=[];
  SY.forEach(function(s, si){
    var sun=B[s.sun]; if(!sun || !sun.n) return;
    var u=unitColor(si), g=el('g', {'data-sys':si}, svg);
    if(u) g.style.setProperty('--u', u);
    if(u){ var gr=el('radialGradient', {id:'sol-glow-'+si}, defs);
      el('stop', {offset:'0', 'stop-color':u, 'stop-opacity':'.42'}, gr); el('stop', {offset:'1', 'stop-color':u, 'stop-opacity':'0'}, gr);
      sun.glow=el('circle', {r:f2(sun.d*1.15), fill:'url(#sol-glow-'+si+')'}, g); }
    /* rings: each planet's round the sun; a planet's moons share one, a moon's satellites one */
    var seen={};
    ORD.forEach(function(id){
      var b=B[id]; if(b.si!==si || !b.p || !b.n) return;
      var p=B[b.p]; if(!p.n) return;
      if(ORBIT){ var r=Math.hypot(b.hx-p.hx, b.hy-p.hy), k=b.p+'|'+Math.round(r/2);
        if(!seen[k]){ seen[k]=1; rings.push({c:b.p, e:el('circle', {'class':'sol-ring'+(b.role==='planet' ? '' : ' sol-m'), r:f2(r)}, g)}); } }
      spokes.push(ORBIT ? {a:b.p, b:id, e:[el('line', {'class':'sol-spoke'}, g)]}
                        : {a:b.p, b:id, e:[el('path', {'class':'sol-tube'}, g), el('path', {'class':'sol-sheen'}, g)]});
    });
    /* one chip per unit (a district of several systems: over all of them) */
    var U=null; (S.units||[]).forEach(function(q){ if(q.suns && q.suns[0]===s.sun) U=q; });
    var pm=(typeof PHASE_META!=='undefined') ? PHASE_META[s.unit] : null, lbl=(U && U.label) || s.label || (pm ? pm.label : ''), bb=(U && U.bbox) || s.bbox;
    lbl=String(lbl).split(' — ').pop();
    if(lbl && (U || !S.units)){ var ch=document.createElement('div'); ch.className='sol-unit'; if(u) ch.style.setProperty('--u', u);
      ch.innerHTML='<b></b><span></span>'; ch.querySelector('b').textContent=pm ? pm.numeral : ''; ch.querySelector('span').textContent=lbl;
      world.appendChild(ch);
      var top=Math.max(PAD+24, (bb ? bb[1]+PAD : sun.hy-(s.R||sun.d))-44);
      ch.style.left=Math.round((U ? (bb[0]+bb[2])/2 : sun.hx)-ch.offsetWidth/2)+'px'; ch.style.top=Math.round(top)+'px'; chips.push(ch); }
  });
  var lg=el('g', {'class':'sol-links'}, svg);
  (S.sun_links||[]).forEach(function(l){ if(!B[l[0]] || !B[l[1]] || !B[l[0]].n || !B[l[1]].n) return;
    sunl.push({a:l[0], b:l[1], e:ORBIT ? [el('path', {'class':'sol-link'}, lg)] : [el('path', {'class':'sol-tube sol-l'}, lg), el('path', {'class':'sol-sheen sol-l'}, lg)]}); });
}
/* the connections, edge to edge between circles: drawn in place of the router
   (engine patch solar-lines-hook); a parent's line to its child is the spoke */
window._altoSolarLines=function(){
  if(!ready || !desk()) return false;
  var rv=document.getElementById('river-svg'); if(!rv) return false;
  rv.innerHTML=''; links=[];
  var dark=de.classList.contains('dark'), sheen=dark ? 'rgba(255,255,255,0.50)' : 'rgba(255,255,255,0.72)', pairs={};
  (typeof CONNECTIONS!=='undefined' ? CONNECTIONS : []).forEach(function(c){
    var a=B[c[0]], b=B[c[1]]; if(!a || !b || !a.n || !b.n || a.p===b.id || b.p===a.id) return;
    var k=c[0]<c[1] ? c[0]+'|'+c[1] : c[1]+'|'+c[0]; if(pairs[k]) return; pairs[k]=1;
    var spine=c[2]==='spine', col=COLOR_MAP[c[2]] || 'var(--line-flow)';
    if(spine) col=dark ? 'rgb(208,212,226)' : 'rgb(60,64,84)';
    else try{ var pm=PHASE_META[NODE_ACT[c[0]]||0], era=pm ? _lineToRgb(pm.colorRaw) : null, base=dark ? [12,13,20] : [240,239,234];
      var bg=era ? [0,1,2].map(function(i){ return Math.round(era[i]*.7+base[i]*.3); }) : base;
      var ad=_lineAdapt(_lineToRgb(_lineResolveVar(col)), bg); if(ad) col='rgb('+ad.join(',')+')'; }catch(e){}
    var w=spine ? 4.2 : 5, t=el('path', {fill:'none', stroke:col, 'stroke-width':w, 'stroke-linecap':'round', 'stroke-linejoin':'round',
      'data-edge':c[0]+'|'+c[1], 'stroke-opacity':spine ? .92 : .96}, rv);
    var s=el('path', {fill:'none', stroke:sheen, 'stroke-width':Math.max(1.3, w*.34), 'stroke-linecap':'round'}, rv);
    links.push({a:c[0], b:c[1], k:c[0]+'|'+c[1], e:[t, s]});
  });
  apply(true);
  return true;
};

/* ── motion ──────────────────────────────────────────────────────────────── */
var T=0, rk=1, back=1, sp=0, last=null, raf=0, slT=0, hov=0, hovT=0, printing=0, mq=null, reduced=false;
try{ mq=matchMedia('(prefers-reduced-motion: reduce)'); reduced=mq.matches;
  var mqf=function(){ reduced=mq.matches; go(); }; if(mq.addEventListener) mq.addEventListener('change', mqf); else mq.addListener(mqf); }catch(e){}
function wrap(a){ a%=TAU; if(a>Math.PI) a-=TAU; if(a<-Math.PI) a+=TAU; return a; }
/* where every body is at time T (rk < 1: on the way back to T = 0) */
function place(){
  var many=SY.length>1;
  ORD.forEach(function(id){
    var b=B[id]; if(!b.n) return;
    if(!b.p){ b.x=b.hx; b.y=b.hy; return; }
    /* with several systems each also turns slowly as a whole about its own sun
       (within its R, so never toward a neighbour) */
    var p=B[b.p], dx=b.hx-p.hx, dy=b.hy-p.hy, a=b.per>0 ? wrap(SPIN*TAU*T/b.per+(many ? SPIN*TAU*T/(540+60*b.si) : 0))*rk : 0, cs=Math.cos(a), sn=Math.sin(a);
    b.x=p.x+dx*cs-dy*sn; b.y=p.y+dx*sn+dy*cs;
  });
}
function seg(a, b, ga, gb){
  var dx=b.rx-a.rx, dy=b.ry-a.ry, L=Math.hypot(dx, dy)||1, ux=dx/L, uy=dy/L, ra=a.d/2+ga, rb=b.d/2+gb;
  if(L<=ra+rb) return null;
  return [f2(a.rx+ux*ra), f2(a.ry+uy*ra), f2(b.rx-ux*rb), f2(b.ry-uy*rb)];
}
function setD(p, d){ if(p.hasAttribute('data-d0')) p.setAttribute('data-d0', d); else p.setAttribute('d', d); }
/* write the bodies and everything drawn with them; all = also what did not move */
function apply(all){
  if(!ready) return;
  place();
  var moved={}, any=false;
  ORD.forEach(function(id){
    var b=B[id]; if(!b.n) return;
    var x=rd(b.x), y=rd(b.y);
    if(x!==b.rx || y!==b.ry || all){
      if(x!==b.rx) b.n.style.left=x+'px'; if(y!==b.ry) b.n.style.top=y+'px';
      if(b.rx!=null && (x!==b.rx || y!==b.ry)) any=true;
      b.rx=x; b.ry=y; moved[id]=1;
      if(b.glow){ b.glow.setAttribute('cx', x); b.glow.setAttribute('cy', y); }
      if(b.mk && b.mk.isConnected){ var w=b.mk._w; b.mk.setAttribute('x', f2(x-w/2+1)); b.mk.setAttribute('y', f2(y-w/2+1)); }
    }
  });
  if(!all && !any) return;
  rings.forEach(function(r){ if(moved[r.c]){ r.e.setAttribute('cx', B[r.c].rx); r.e.setAttribute('cy', B[r.c].ry); } });
  spokes.concat(sunl).forEach(function(s){
    if(!moved[s.a] && !moved[s.b]) return;
    var g=seg(B[s.a], B[s.b], 3, 3);
    if(s.e[0].tagName==='line'){ var e=s.e[0]; if(!g){ e.setAttribute('x2', e.getAttribute('x1')||0); return; }
      e.setAttribute('x1', g[0]); e.setAttribute('y1', g[1]); e.setAttribute('x2', g[2]); e.setAttribute('y2', g[3]); }
    else { var d=g ? 'M'+g[0]+' '+g[1]+' L'+g[2]+' '+g[3] : 'M0 0'; s.e.forEach(function(p){ p.setAttribute('d', d); }); }
  });
  links.forEach(function(l){
    if(!moved[l.a] && !moved[l.b]) return;
    var g=seg(B[l.a], B[l.b], 1, 1), d=g ? 'M '+g[0]+' '+g[1]+' L '+g[2]+' '+g[3] : 'M0 0';
    if(!l.h || !l.h.isConnected) l.h=svgHit(l.k);
    l.e.forEach(function(p){ setD(p, d); }); if(l.h) l.h.setAttribute('d', d);
  });
  if(any && window._altoContentMoved) window._altoContentMoved();
}
function svgHit(k){ var rv=document.getElementById('river-svg'), r=null;
  if(rv) [].some.call(rv.querySelectorAll('[data-edge-hit]'), function(h){ if(h.getAttribute('data-edge-hit')===k){ r=h; return true; } });
  return r; }
/* the Blink mask's holes follow their circles (engine patch solar-card-mask-round) */
window._altoSolarMask=function(){ ORD.forEach(function(id){ var b=B[id]; b.mk=null; });
  [].forEach.call(document.querySelectorAll('#alto-card-mask [data-mk]'), function(r){
    var b=B[r.getAttribute('data-mk').slice(5)]; if(b){ b.mk=r; r._w=parseFloat(r.getAttribute('width'))+2; } }); };
function hold(){
  if(!MOVES || reduced || !desk() || document.hidden || hov) return true;
  if(window._focusedNodeId || document.querySelector('#canvas.focus-mode,#canvas.edge-hover,#detail-page.visible')) return true;
  return !!document.querySelector('#world .node.alto-found,#world .node.sol-closing,#world .node-card.dimmed,#world .node-card.rel-dimmed,#world .node-card.ent-dimmed');
}
function tick(ts){
  raf=0; if(!ready) return;
  var dt=last==null ? 0 : Math.min(.1, (ts-last)/1000); last=ts;
  if(OV && (de.classList.contains('alto-editing') || window._focusedNodeId)) ovLeave(null, true);
  if(de.classList.contains('alto-editing') || printing){          /* the plan's own layout, turned back to */
    sp=0; if(T){ back=printing ? 0 : Math.max(0, back-dt/.45); rk=back*back*(3-2*back); apply(); if(back) return go(); T=0; back=rk=1; }
    return sleep(); }
  if(back<1){ T=0; back=rk=1; apply(); }
  if(hold()){ sp=0; return sleep(); }
  sp=Math.min(1, sp+dt/1.2); T+=dt*sp*sp*(3-2*sp); apply(); go();
}
function go(){ clearTimeout(slT); if(!raf && MOVES) raf=requestAnimationFrame(tick); }
function sleep(){ last=null; clearTimeout(slT); slT=setTimeout(go, 180); }
window.addEventListener('beforeprint', function(){ printing=1; ovLeave(null, true); if(T){ T=0; rk=1; apply(); } });
window.addEventListener('afterprint', function(){ printing=0; go(); });
document.addEventListener('visibilitychange', function(){ last=null; go(); });
/* a hover is the pointer moving onto a circle or a line, not one sliding under a still pointer */
function hot(t){ return t && t.closest && t.closest('#world .node[data-solar],#river-svg [data-edge-hit]'); }
function over(e){ if(!hot(e.target) || (window._altoPointerStill && window._altoPointerStill(e))) return; clearTimeout(hovT); hov=1; }
document.addEventListener('mouseover', over); document.addEventListener('mousemove', over, {passive:true});
document.addEventListener('mouseout', function(e){ if(hot(e.relatedTarget)) return; clearTimeout(hovT); hovT=setTimeout(function(){ hov=0; }, 320); });

/* ── an enlarged circle is the card: clipped from its disc out to the card as
   it grows, and back as it shrinks — the clip read off the card's own zoom on
   every frame, so it cannot run ahead of or behind the engine's ramps ───── */
var zmo=(typeof MutationObserver==='function') ? new MutationObserver(function(ms){ ms.forEach(function(m){ var n=m.target.closest && m.target.closest('.node'); if(n) clip(n); }); }) : null, morphing=[];
function clip(n){
  var c=n.querySelector('.node-card'), b=B[(n.id||'').slice(5)]; if(!c || !b) return;
  var z=parseFloat(c.style.zoom)||1, f=n.classList.contains('focused');
  if(!f && z<=1.0005){                                         /* home: a circle again */
    n.classList.remove('sol-closing'); n.classList.remove('sol-clip');
    ['--scx','--scy','--scr','--sfo','--sbo'].forEach(function(v){ n.style.removeProperty(v); });
    var i=morphing.indexOf(c); if(i>=0){ morphing.splice(i, 1); if(zmo){ zmo.disconnect(); morphing.forEach(function(x){ zmo.observe(x, {attributes:true, attributeFilter:['style']}); }); } }
    if(!morphing.length) go();
    return; }
  var p=Math.max(0, Math.min(1, (z-1)/(K-1)*1.5)), s=p*p*(3-2*p);
  if(f && s>=1){ n.classList.remove('sol-clip'); return; }
  n.classList.add('sol-clip');
  var d=b.d, w=n._sw||d, h=n._sh||d;
  n.style.setProperty('--scx', f2((1-s)*Math.max(0, w-d)/2)+'px'); n.style.setProperty('--scy', f2((1-s)*Math.max(0, h-d)/2)+'px');
  n.style.setProperty('--scr', f2(d/2+(14-d/2)*s)+'px');
  n.style.setProperty('--sfo', String(Math.max(0, 1-s*2.2))); n.style.setProperty('--sbo', String(Math.min(1, s*1.6)));
}
function morph(n, open){
  var c=n.querySelector('.node-card'); if(!c) return;
  if(!open) n.classList.add('sol-closing');
  n.classList.add('sol-clip');
  n._sw=c.offsetWidth; n._sh=c.offsetHeight;                   /* the card's own box, unzoomed */
  if(morphing.indexOf(c)<0){ morphing.push(c); if(zmo) zmo.observe(c, {attributes:true, attributeFilter:['style']}); }
  clip(n);
}
function watch(){
  var w=document.getElementById('world'); if(!w || typeof MutationObserver!=='function') return;
  new MutationObserver(function(ms){ ms.forEach(function(m){
    var n=m.target; if(!n.classList || !n.classList.contains('node') || !n.hasAttribute('data-solar') || !desk()) return;
    var f=n.classList.contains('focused'); if(f===!!n._solF) return; n._solF=f; if(f && OV) ovLeave(null, true); morph(n, f);
  }); }).observe(w, {attributes:true, subtree:true, attributeFilter:['class']});
  /* edit mode wants the board at full size and still */
  new MutationObserver(function(){ if(de.classList.contains('alto-editing')){ if(OV) ovLeave(null, true); go(); } }).observe(de, {attributes:true, attributeFilter:['class']});
}
if(document.readyState!=='loading') watch(); else document.addEventListener('DOMContentLoaded', watch);

/* ── arrow keys: the nearest body that way, from where the bodies are now;
   one it orbits, orbits it, or shares an orbit with counts as nearer ──── */
window._altoSolarNav=function(id, dir){
  var a=B[id], ta={e:0, se:45, s:90, sw:135, w:180, nw:-135, n:-90, ne:-45}[dir]; if(!a || !a.n || ta==null || !desk()) return null;
  var best=null, bc=Infinity;
  ORD.forEach(function(j){
    var b=B[j]; if(j===id || !b.n || !b.c || /(^| )(dimmed|rel-dimmed|ent-dimmed)( |$)/.test(b.c.className)) return;
    var dx=b.rx-a.rx, dy=b.ry-a.ry, L=Math.hypot(dx, dy); if(L<1) return;
    var df=Math.atan2(dy, dx)*180/Math.PI-ta; while(df>180) df-=360; while(df<-180) df+=360;
    if(Math.abs(df)>65) return;
    var c=L/Math.max(.25, Math.cos(df*Math.PI/180));
    if(b.p===id || a.p===j || (a.p && a.p===b.p)) c*=.6;
    if(c<bc){ bc=c; best=j; }
  });
  return best;
};
/* ── edit mode changed the outline (manual_edit.py calls this before it lays
   the page out again with the live tables {kids, parent, num, seqs, act}): the
   systems are planned again here — SOLAR_PLAN_JS, solar.py's solar_plan in
   JS — and the circles go where the tree's plan runner puts them ──────── */
window._altoSolarSync=function(t){
  t=t||{};
  var P=window._altoSolarPlan(t, S); if(!P) return false;
  ['style','spin','world','sizes','systems','units','nodes','sun_links'].forEach(function(k){ S[k]=P[k]; });
  NUM=t.num||NUM; bodies(); T=0; back=rk=1;
  var TP=window._ALTO_TREE_PLAN;
  if(TP){ TP.x={}; TP.w={}; TP.acts=[]; TP.cx=P.world.w/2; TP.shift=null; TP.slide=null;
    (t.seqs||[]).forEach(function(ids, a){ TP.acts[a]=[];
      ids.forEach(function(id){ var n=P.nodes[id]; if(!n) return; TP.x[id]=n.x; TP.w[id]=n.d; TP.acts[a].push(['float', ['card', id, 0], n.y, 'mid']); }); }); }
  return true;
};
/* ── the whole chart: the board zoomed out to fit the window ─────────────────
   Pinch out (ctrl+wheel; Safari's gesture), ⌘− / ctrl+−, or the toggle under the
   bars. As on a horizontal timeline's whole view (lanes_nav.py) the board is
   scaled by a transform about its corner, the canvas held at 0,0 (a spacer
   keeps its scroll extent, so scrollbars never come and go) and moved by its
   own translate: wheel or drag pans, pinch zooms about the pointer, the orbits
   go on. A click (or ⌘+ / ⌘0 / Esc / an arrow) comes back down to full size —
   on the body clicked, which is then enlarged. Only layout px are used: where
   a body is comes from its own left/top, the pointer from the canvas's rect. */
var OV=null, ovA=0, OVMIN=.03;
function cvs(){ return document.getElementById('canvas'); }
function zk(c){ var r=c.getBoundingClientRect(); return (r.width && c.offsetWidth) ? r.width/c.offsetWidth : 1; }
function woff(c){ var ox=0, oy=0, q=world; while(q && q!==c){ ox+=q.offsetLeft; oy+=q.offsetTop; q=q.offsetParent; } return {x:ox, y:oy}; }
/* the board's height: the world, or the glass under it where that runs on (its padding) */
function wh(){ var sl=document.getElementById('glass-slab'); return Math.max(world.offsetHeight, sl ? sl.offsetTop+sl.offsetHeight : 0); }
function fitS(){ var c=cvs(); return Math.max(OVMIN, Math.min(1, (c.clientWidth-60)/world.offsetWidth, (c.clientHeight-60)/wh())); }
function clampO(o){ var c=cvs(), cw=c.clientWidth, ch=c.clientHeight, w, h;
  o.s=Math.max(Math.min(fitS(), 1), Math.min(1, o.s));
  w=world.offsetWidth*o.s; h=wh()*o.s;
  o.tx=w<=cw ? (cw-w)/2 : Math.max(cw-w-30, Math.min(30, o.tx)); o.ty=h<=ch ? (ch-h)/2 : Math.max(ch-h-30, Math.min(30, o.ty)); return o; }
function ovSet(o){ var off=woff(cvs()); world.style.transform='translate('+f2(o.tx-off.x)+'px,'+f2(o.ty-off.y)+'px) scale('+o.s+')'; }
function ovHold(on){
  var c=cvs(), sp=document.getElementById('sol-ov-hold');
  if(!on){ if(sp) sp.remove(); return; }
  if(!sp){ sp=document.createElement('div'); sp.id='sol-ov-hold'; sp.setAttribute('aria-hidden', 'true');
    sp.style.cssText='position:absolute;left:0;top:0;width:1px;height:1px;visibility:hidden;pointer-events:none;'; c.appendChild(sp); }
  sp.style.width=c.scrollWidth+'px'; sp.style.height=c.scrollHeight+'px';
}
function ease(p){ return window._altoEase ? window._altoEase(p) : p*p*(3-2*p); }
function ovAnim(from, to, done){
  cancelAnimationFrame(ovA); var c=cvs(); c.classList.add('sol-ovanim');
  if(reduced){ ovSet(to); c.classList.remove('sol-ovanim'); return done(); }
  var t0=performance.now();
  (function fr(now){ var p=Math.min(1, (now-t0)/560), k=ease(p), sc=Math.exp(Math.log(from.s)+(Math.log(to.s)-Math.log(from.s))*k),
      u=Math.abs(to.s-from.s)>1e-6 ? (sc-from.s)/(to.s-from.s) : k;
    ovSet({s:sc, tx:from.tx+(to.tx-from.tx)*u, ty:from.ty+(to.ty-from.ty)*u});
    if(p<1) ovA=requestAnimationFrame(fr); else { ovA=0; c.classList.remove('sol-ovanim'); done(); } })(t0);
}
/* to scale s about (fx, fy) in the canvas's px (default: its middle) */
function ovZoom(s, fx, fy, anim){
  var c=cvs(); if(!c || !ready || !desk()) return;
  if(fx==null){ fx=c.clientWidth/2; fy=c.clientHeight/2; }
  if(!OV){
    if(window._focusedNodeId && window.exitFocus) window.exitFocus();
    var off=woff(c); OV={s:1, tx:off.x-c.scrollLeft, ty:off.y-c.scrollTop};
    ovHold(true); ovSet(OV); c.scrollLeft=0; c.scrollTop=0; c.classList.add('sol-ov'); fitBtn();
  }
  var from={s:OV.s, tx:OV.tx, ty:OV.ty}, to=clampO({s:s, tx:fx-(fx-OV.tx)*s/OV.s, ty:fy-(fy-OV.ty)*s/OV.s});
  if(to.s>=.999 && from.s>=.999) return ovLeave(null, true);
  OV=to;
  if(anim) ovAnim(from, to, function(){}); else ovSet(to);
}
/* back to full size, the world point p (default: what is in the middle) in the middle */
function ovLeave(p, instant, then){
  if(!OV) return; var c=cvs(), o=OV, off=woff(c), cw=c.clientWidth, ch=c.clientHeight;
  if(!p) p={x:(cw/2-o.tx)/o.s, y:(ch/2-o.ty)/o.s};
  OV=null; cancelAnimationFrame(ovA); c.classList.remove('sol-ov'); fitBtn();
  var sl=Math.max(0, Math.min(c.scrollWidth-cw, p.x+off.x-cw/2)), st=Math.max(0, Math.min(c.scrollHeight-ch, p.y+off.y-ch/2));
  var fin=function(){ world.style.transform=''; ovHold(false);
    var ax=window._altoScrollAxis; if(ax){ ax('scrollLeft').go(sl); ax('scrollTop').go(st); } else { c.scrollLeft=sl; c.scrollTop=st; }
    if(then) then(); };
  if(instant) return fin();
  ovAnim(o, {s:1, tx:off.x-sl, ty:off.y-st}, fin);
}
function local(e){ var c=cvs(), r=c.getBoundingClientRect(), k=zk(c); return {x:(e.clientX-r.left)/k, y:(e.clientY-r.top)/k}; }
function nearest(wx, wy){ var best=null, bd=Infinity;
  ORD.forEach(function(id){ var b=B[id]; if(!b.n) return; var d=Math.hypot(b.rx-wx, b.ry-wy)-b.d/2; if(d<bd){ bd=d; best=id; } });
  return best; }
/* the toggle under the bars (the round glass of the key toggle, key_toggle.py) */
function fitBtn(){
  var t=document.getElementById('sol-fit');
  if(!desk() || !ready){ if(t) t.remove(); return; }
  if(!t){ t=document.createElement('button'); t.id='sol-fit'; t.type='button';
    t.innerHTML='<svg viewBox="0 0 20 20" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="10" cy="10" r="2.6"/><circle cx="10" cy="10" r="6.6" stroke-opacity=".55"/><path d="M2 6.5V2h4.5M18 6.5V2h-4.5M2 13.5V18h4.5M18 13.5V18h-4.5"/></svg>';
    t.addEventListener('click', function(e){ e.stopPropagation(); if(OV) ovLeave(); else ovZoom(fitS(), null, null, true); });
    document.body.appendChild(t); }
  t.classList.toggle('active', !!OV);
  t.title=OV ? 'Back to full size' : 'The whole chart (or pinch out, ⌘−)'; t.setAttribute('aria-label', t.title); t.setAttribute('aria-pressed', OV ? 'true' : 'false');
}
function mine(e){ var c=cvs(); return c && e.target && c.contains(e.target); }
window.addEventListener('wheel', function(e){
  if(!ready || !desk() || !mine(e)) return;
  if(!OV && !(e.ctrlKey && e.deltaY>0 && !window._focusedNodeId)) return;
  e.preventDefault(); e.stopImmediatePropagation();
  var m=e.deltaMode===1 ? 40 : e.deltaMode===2 ? 800 : 1, q=local(e);
  if(e.ctrlKey){ var s2=(OV ? OV.s : 1)*Math.max(.5, Math.min(2, Math.exp(-e.deltaY*m*.012)));
    if(OV && s2>=.999) return ovLeave({x:(q.x-OV.tx)/OV.s, y:(q.y-OV.ty)/OV.s}, true);
    return ovZoom(s2, q.x, q.y, false); }
  OV.tx-=e.deltaX*m; OV.ty-=e.deltaY*m; if(e.shiftKey && !e.deltaX){ OV.ty+=e.deltaY*m; OV.tx-=e.deltaY*m; }
  clampO(OV); ovSet(OV);
}, {passive:false, capture:true});
var g0=null;
document.addEventListener('gesturestart', function(e){ g0=(ready && desk() && mine(e) && !window._focusedNodeId) ? (OV ? OV.s : 1) : null; if(g0!=null) e.stopImmediatePropagation(); }, {passive:false});
document.addEventListener('gesturechange', function(e){
  if(g0==null) return; e.preventDefault(); e.stopImmediatePropagation();
  if(!OV && e.scale>=1) return;
  var q=local(e), s2=Math.min(1, g0*e.scale);
  if(OV && s2>=.999) return; ovZoom(s2, q.x, q.y, false);
}, {passive:false});
document.addEventListener('gestureend', function(e){
  if(g0==null) return; e.preventDefault(); e.stopImmediatePropagation(); g0=null;
  if(OV && OV.s>=.97) ovLeave(null, true);
}, {passive:false});
window.addEventListener('keydown', function(e){
  if(!ready || !desk() || (document.activeElement && (document.activeElement.isContentEditable || /^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName)))) return;
  var k=e.key, mod=e.metaKey || e.ctrlKey, hit=false;
  if(mod && k==='-' && !window._focusedNodeId && !document.querySelector('#summary-wrap.open,#detail-page.visible')){ ovZoom(OV ? OV.s/1.6 : Math.max(fitS(), .55), null, null, true); hit=true; }
  else if(OV && mod && (k==='=' || k==='+')){ if(OV.s*1.6>=.97) ovLeave(); else ovZoom(OV.s*1.6, null, null, true); hit=true; }
  else if(OV && ((mod && k==='0') || k==='Escape' || /^Arrow/.test(k))){ ovLeave(); hit=true; }
  if(hit){ e.preventDefault(); e.stopImmediatePropagation(); }
}, true);
(function(){
  var dn=null;
  document.addEventListener('pointerdown', function(e){ if(!OV || !mine(e)) return; e.preventDefault(); e.stopPropagation();
    dn={x:e.clientX, y:e.clientY, tx:OV.tx, ty:OV.ty, moved:false, id:e.pointerId}; }, true);
  document.addEventListener('pointermove', function(e){ if(!dn || !OV || e.pointerId!==dn.id) return; var k=zk(cvs());
    if(!dn.moved && Math.abs(e.clientX-dn.x)+Math.abs(e.clientY-dn.y)<5) return;
    dn.moved=true; OV.tx=dn.tx+(e.clientX-dn.x)/k; OV.ty=dn.ty+(e.clientY-dn.y)/k; clampO(OV); ovSet(OV); }, true);
  document.addEventListener('pointerup', function(e){ if(!dn || e.pointerId!==dn.id) return; var d=dn; dn=null;
    if(!OV || d.moved) return;
    var q=local(e), wx=(q.x-OV.tx)/OV.s, wy=(q.y-OV.ty)/OV.s, id=nearest(wx, wy), b=id && B[id];
    ovLeave(b ? {x:b.rx, y:b.ry} : {x:wx, y:wy}, false, function(){ if(b && window.enterFocus) window.enterFocus(id); }); }, true);
  /* nothing under the whole chart is clicked through to */
  ['mousedown', 'click', 'dblclick'].forEach(function(t){ document.addEventListener(t, function(e){ if(OV && mine(e)){ e.preventDefault(); e.stopPropagation(); } }, true); });
  document.addEventListener('scroll', function(e){ var c=cvs(); if(OV && e.target===c && (c.scrollLeft || c.scrollTop)){ c.scrollLeft=0; c.scrollTop=0; } }, true);
  window.addEventListener('resize', function(){ if(OV){ ovHold(true); clampO(OV); ovSet(OV); } });
})();
window._altoSolarZoom=function(s){ if(s==null) return OV ? OV.s : 1; if(s>=1) ovLeave(null, true); else ovZoom(s, null, null, false); return OV ? OV.s : 1; };
window._altoSolarGeo=function(){ var o={}; ORD.forEach(function(id){ var b=B[id]; if(b.n) o[id]={x:b.rx, y:b.ry, hx:b.hx, hy:b.hy, d:b.d, role:b.role, p:b.p}; });
  return {T:T, moving:!!raf, bodies:o}; };
return true;
};
if(window._ALTO_SOLAR) window._altoSolarMount(window._ALTO_SOLAR);
else document.addEventListener('DOMContentLoaded', function(){ if(window._ALTO_SOLAR) window._altoSolarMount(window._ALTO_SOLAR); });
"""


# ── solar.py's solar_plan, in the page ──────────────────────────────────────
# Edit mode reshapes the outline in the browser (a card added, moved under
# another, removed) and the page lays itself out again at once, so the plan is
# worked out here too, line for line as solar.py does it (same constants,
# emitted from solar.SOLAR; tests/test_solar_draw.py holds the two equal under
# node). Input: the live tables {kids, parent, seqs}; the circles' sizes and the
# units' labels come from the plan the page was built with.
SOLAR_PLAN_JS = r"""
window._altoSolarPlan=(function(){
var C=__SOLAR__, GOLD=__GOLDEN__, LOOKS=__LOOKS__, D=C.D, PI=Math.PI;
function r2(v){ return Math.round(v*100)/100; }
function r4(v){ return Math.round(v*1e4)/1e4; }
function mx(a){ return a.length ? Math.max.apply(null, a) : 0; }
function ringFor(n, ext, gap, inner){ if(!n) return 0; var r=inner+gap+ext;
  if(n>=2) r=Math.max(r, (2*ext+Math.max(gap, 2*C.SPOKE_CLEAR))/(2*Math.sin(PI/n))); return r; }
function even(n, out){ var off=n%2===0 ? PI/n : 0, o=[]; for(var j=0;j<n;j++) o.push(out+off+2*PI*j/n); return o; }
/* a body's diameter: the sun's fixed, a planet / moon a tier up per two children, a bump one more (solar.body_d) */
function bodyD(role, n, bump){ if(role==='sun') return D.sun; var L=C.TIERS[role], t=role!=='sat' ? Math.min(Math.ceil(n/2), L.length-2) : 0;
  return L[Math.min(t+(bump ? 1 : 0), L.length-1)]; }
/* the looks' arithmetic (solar.hash01 … orbit_offset): FNV-1a, a comet's ellipse, an asteroid's tumble */
function h01(s){ var h=2166136261; for(var i=0;i<s.length;i++){ h^=s.charCodeAt(i); h=Math.imul(h, 16777619)>>>0; } return h/4294967296; }
function cshape(id){ return [r4(C.ECC[0]+(C.ECC[1]-C.ECC[0])*h01('ecc:'+id)), r4(2*PI*h01('rot:'+id))]; }
function eslack(e){ var q=Math.sqrt(Math.max(0, 1-e*e)); return (1-q)/(1+q); }
function secc(c){ var q=(1-c)/(1+c); return Math.sqrt(Math.max(0, 1-q*q)); }
function tumble(id){ var v=C.TUMBLE[0]+(C.TUMBLE[1]-C.TUMBLE[0])*h01('tumble:'+id); return r4(h01('spin:'+id)<.5 ? v : -v); }
function kepler(m, e){ var p=m; for(var i=0;i<12;i++) p-=(p-e*Math.sin(p)-m)/(1-e*Math.cos(p)); return p; }
function at(r, a, o){ if(!o) return [r*Math.cos(a), r*Math.sin(a)];
  var c=eslack(o.e), A=r*(1+c), B=r*(1-c), m=a-o.rot, p=o.k ? kepler(m, o.e) : m, x=A*Math.cos(p), y=B*Math.sin(p);
  return [x*Math.cos(o.rot)-y*Math.sin(o.rot), x*Math.sin(o.rot)+y*Math.cos(o.rot)]; }
/* a shared ring of [id, reach, comet slack] (solar._ring_fix): a comet strays c·r from its circle */
function ringFix(items, gap, inner){
  var n=items.length; if(!n) return [0, 0, {}];
  var cap=n>=2 ? .5*Math.sin(PI/n) : .5, cs={};
  items.forEach(function(it){ if(it[2]>0) cs[it[0]]=Math.min(it[2], cap); });
  var me=function(r){ return mx(items.map(function(it){ return it[1]+(cs[it[0]]||0)*r; })); };
  var r=ringFor(n, mx(items.map(function(it){ return it[1]; })), gap, inner);
  for(var i=0;i<200;i++){ var r_=ringFor(n, me(r), gap, inner); if(r_-r<1e-9){ r=r_; break; } r=r_; }
  return [r, me(r), cs];
}
function pbody(pid, moons, size, slack){
  var dp=size(pid, 'planet', moons.length), Rp=dp/2, orb={};
  var ms=moons.map(function(m){ var dm=size(m[0], 'moon', m[1].length), Rm=dm/2, sd={};
    m[1].forEach(function(q){ sd[q]=size(q, 'sat', 0); });
    var F=ringFix(m[1].map(function(q){ return [q, sd[q]/2, slack[q]||0]; }), C.SAT_GAP, Rm);
    Object.keys(F[2]).forEach(function(q){ orb[q]={e:r4(secc(F[2][q])), rot:cshape(q)[1], k:0}; });
    return {id:m[0], d:dm, sats:m[1], sd:sd, sat_r:F[0], ext:m[1].length ? F[0]+F[1] : Rm}; });
  var F=ringFix(ms.map(function(m){ return [m.id, m.ext, slack[m.id]||0]; }), C.MOON_GAP, Rp);
  Object.keys(F[2]).forEach(function(q){ orb[q]={e:r4(secc(F[2][q])), rot:cshape(q)[1], k:0}; });
  var e=ms.length ? F[0]+F[1] : Rp;
  return {id:pid, d:dp, moons:ms, moon_r:F[0], e:Math.max(e, Rp), orb:orb};
}
function local(b, th, r, orbs){
  orbs=orbs||{};
  var P=at(r, th, orbs[b.id]), px=P[0], py=P[1], cs=[[b.id, px, py, b.d/2, null]], sg=[], ma=even(b.moons.length, th);
  b.moons.forEach(function(m, k){ var o=at(b.moon_r, ma[k], orbs[m.id]), x=px+o[0], y=py+o[1], sa=even(m.sats.length, ma[k]);
    cs.push([m.id, x, y, m.d/2, b.id]); sg.push([m.id, b.id, x, y, px, py]);
    m.sats.forEach(function(si, j){ var o2=at(m.sat_r, sa[j], orbs[si]), sx=x+o2[0], sy=y+o2[1];
      cs.push([si, sx, sy, m.sd[si]/2, m.id]); sg.push([si, m.id, sx, sy, x, y]); }); });
  return [cs, sg];
}
function sd(cx, cy, x1, y1, x2, y2){ var dx=x2-x1, dy=y2-y1, L=dx*dx+dy*dy, t=L===0 ? 0 : Math.max(0, Math.min(1, ((cx-x1)*dx+(cy-y1)*dy)/L));
  return Math.hypot(cx-(x1+t*dx), cy-(y1+t*dy)); }
function fits(cs, sg, spoke, e, placed, psegs){
  var g=C.SPOKE_GAP, cl=C.SPOKE_CLEAR, px=cs[0][1], py=cs[0][2], i, j, k;
  var near=placed.filter(function(c){ return Math.hypot(px-c[1], py-c[2]) < e+c[3]+Math.max(g, C.RING_GAP, cl); });
  for(i=0;i<cs.length;i++) for(j=0;j<near.length;j++){ var gp=near[j][4]==='sun' ? C.RING_GAP : g;
    if(Math.hypot(cs[i][1]-near[j][1], cs[i][2]-near[j][2]) < cs[i][3]+near[j][3]+gp) return false; }
  for(k=0;k<psegs.length;k++){ var s=psegs[k]; if(sd(px, py, s[2], s[3], s[4], s[5]) >= e+cl) continue;
    for(i=0;i<cs.length;i++) if(sd(cs[i][1], cs[i][2], s[2], s[3], s[4], s[5]) < cs[i][3]+cl) return false; }
  for(k=0;k<sg.length;k++){ s=sg[k]; for(j=0;j<near.length;j++){ var c=near[j];
    if(c[0]!==s[0] && c[0]!==s[1] && sd(c[1], c[2], s[2], s[3], s[4], s[5]) < c[3]+cl) return false; } }
  for(k=0;k<spoke.length;k++){ s=spoke[k]; for(j=0;j<placed.length;j++){ c=placed[j];
    if(c[0]!==s[0] && c[0]!==s[1] && sd(c[1], c[2], s[2], s[3], s[4], s[5]) < c[3]+cl) return false; } }
  return true;
}
function period(lh, k, n){ return r2(lh[0]+(lh[1]-lh[0])*(n>1 ? k/(n-1) : .5)); }
function system(unit, sun, planets, style, size, looks){
  var mov=style==='orbit', slack={};
  if(mov) Object.keys(looks).forEach(function(i){ if(looks[i]==='comet') slack[i]=eslack(cshape(i)[0]); });
  var Rs=D.sun/2, bs=planets.map(function(p){ return pbody(p[0], p[1], size, slack); }), P=bs.length, rings=[], ang=[], orbs={}, belt=null, k;
  bs.forEach(function(b){ Object.keys(b.orb).forEach(function(i){ orbs[i]=b.orb[i]; }); });
  if(mov){ var edge=Rs, split=P>=C.BELT_MIN ? Math.floor(P/2) : -1;
    bs.forEach(function(b, k){
      if(k===split){ belt={r:edge+C.RING_GAP+C.BELT_W/2, w:C.BELT_W}; edge+=C.RING_GAP+C.BELT_W; }
      var c=slack[b.id]||0, r=(edge+C.RING_GAP+b.e)/(1-c)+(c ? .05 : 0);
      if(c){ var sh=cshape(b.id); orbs[b.id]={e:sh[0], rot:sh[1], k:1}; }
      rings.push(r); ang.push(-PI/2+k*GOLD); b.band=[r-c*r-b.e, r+c*r+b.e]; edge=b.band[1]; }); }
  else { var placed=[[sun, 0, 0, Rs, 'sun']], psegs=[], rp2=0, st=C.A_STEP_DEG*PI/180, tries=[0];
    for(var j=1;j<=Math.round(PI/st);j++){ tries.push(j*st); tries.push(-j*st); }
    bs.forEach(function(b, k){
      var pref=-PI/2+k*GOLD, r0=Math.max(Rs+C.RING_GAP+b.d/2, k ? rp2+C.MIN_STEP : 0), hit=null;
      [[true, C.SPOKE_BUDGET], [false, null]].some(function(mode){
        var r=r0;
        while(!hit && (mode[1]===null || r<=r0+mode[1])){
          for(var q=0;q<tries.length;q++){ var th=pref+tries[q], L=local(b, th, r), sp=[[b.id, sun, L[0][0][1], L[0][0][2], 0, 0]];
            if(fits(L[0], L[1], mode[0] ? sp : [], b.e, placed, psegs)){ hit=[th, L[0], L[1].concat(sp)]; break; } }
          if(!hit) r+=C.R_STEP;
        }
        if(hit){ placed=placed.concat(hit[1]); psegs=psegs.concat(hit[2]); rings.push(r); ang.push(hit[0]); rp2=r; return true; }
        return false;
      });
    });
  }
  var outP=[], loc={}; loc[sun]=[0, 0, D.sun, 'sun', ''];
  bs.forEach(function(b, k){
    var r=rings[k], th=ang[k], L=local(b, th, r, orbs), ma=even(b.moons.length, th);
    L[0].forEach(function(c){ loc[c[0]]=[c[1], c[2], Math.round(c[3]*2), c[4]===null ? 'planet' : (c[4]===b.id ? 'moon' : 'sat'), c[4]||sun]; });
    var md=function(a){ a%=2*PI; if(a<0) a+=2*PI; return Math.round(a*1e7)/1e7; };
    outP.push({id:b.id, ring:k+1, r:r2(r), a0:md(th), d:b.d, period:mov ? period(C.P_PLANET, k, P) : 0, e:r2(b.e), moon_r:r2(b.moon_r),
      moons:b.moons.map(function(m, i){ var sa=even(m.sats.length, ma[i]);
        return {id:m.id, r:r2(b.moon_r), a0:md(ma[i]), d:m.d, period:mov ? period(C.P_MOON, k, P) : 0, sat_r:r2(m.sat_r),
          sats:m.sats.map(function(si, j){ return {id:si, r:r2(m.sat_r), a0:md(sa[j]), d:m.sd[si], period:mov ? C.P_SAT : 0}; })}; })});
  });
  var R, box, v=Object.keys(loc).map(function(i){ return loc[i]; });
  if(mov){ R=bs.length ? bs[bs.length-1].band[1] : Rs; box=[-R, -R, R, R]; }
  else { box=[Math.min.apply(null, v.map(function(c){ return c[0]-c[2]/2; })), Math.min.apply(null, v.map(function(c){ return c[1]-c[2]/2; })),
              Math.max.apply(null, v.map(function(c){ return c[0]+c[2]/2; })), Math.max.apply(null, v.map(function(c){ return c[1]+c[2]/2; }))];
    R=Math.max.apply(null, v.map(function(c){ return Math.hypot(c[0], c[1])+c[2]/2; })); }
  return {unit:unit, sun:sun, r_sun:Rs, R:R, box:box, planets:outP, local:loc, orbs:orbs, belt:belt};
}
/* the galactic core (solar._core) and the drifting comets (solar._drifters) */
function core(sys, W, H, bottom){
  if(sys.length<2) return [null, H];
  var need=C.CORE_R+C.CORE_GAP, gx=0, gy=0, best=null, st=C.CORE_STEP;
  sys.forEach(function(s){ gx+=s.cx; gy+=s.cy; }); gx/=sys.length; gy/=sys.length;
  var lx=C.MARGIN+C.CORE_R, hx=W-C.MARGIN-C.CORE_R, ly=C.MARGIN+C.CORE_R, hy=H-C.MARGIN-C.CORE_R, nx=Math.floor((hx-lx)/st), ny=Math.floor((hy-ly)/st);
  for(var j=0;j<=ny;j++){ var y=ly+j*st;
    for(var i=0;i<=nx;i++){ var x=lx+i*st, ok=true;
      for(var q=0;q<sys.length;q++) if(Math.hypot(x-sys[q].cx, y-sys[q].cy) < sys[q].R+need){ ok=false; break; }
      if(ok){ var d=(x-gx)*(x-gx)+(y-gy)*(y-gy); if(!best || d<best[0]-1e-9) best=[d, x, y]; } } }
  if(best) return [{x:r2(best[1]), y:r2(best[2]), r:C.CORE_R}, H];
  var yy=Math.max.apply(null, [bottom].concat(sys.map(function(s){ return s.cy+s.R; })))+C.CORE_GAP+C.CORE_R;
  return [{x:r2(W/2), y:r2(yy), r:C.CORE_R}, Math.ceil(Math.max(H, yy+C.CORE_R+C.BOTTOM))];
}
function drifters(sys, co, W, H){
  var ys=[], out=[];
  if(sys.length){
    ys.push(Math.min.apply(null, sys.map(function(s){ return s.cy-s.R; }))/2);
    ys.push((Math.max.apply(null, sys.map(function(s){ return s.cy+s.R; }))+H)/2);
    var bands=sys.map(function(s){ return [s.cy-s.R, s.cy+s.R]; }).sort(function(a, b){ return a[0]-b[0] || a[1]-b[1]; }), reach=bands[0][1];
    bands.slice(1).forEach(function(b){ if(b[0]-reach >= 2*C.DRIFT_CLEAR+10) ys.push((b[0]+reach)/2); reach=Math.max(reach, b[1]); });
  }
  function clear(pts){ for(var i=0;i+1<pts.length;i++){ var a=pts[i], b=pts[i+1];
      for(var q=0;q<sys.length;q++) if(sd(sys[q].cx, sys[q].cy, a[0], a[1], b[0], b[1]) < sys[q].R+C.DRIFT_CLEAR) return false;
      if(co && sd(co.x, co.y, a[0], a[1], b[0], b[1]) < co.r+C.DRIFT_CLEAR) return false; } return true; }
  ys.slice(0, 4).forEach(function(y, k){
    var seed=Math.floor(h01('drift:'+k+':'+Math.trunc(y))*1e9), bend=(h01('bend:'+seed)-.5)*2*C.DRIFT_CLEAR*.5;
    var pts=[[0, y], [W/2, y+bend], [W, y]]; if(h01('dir:'+seed)<.5) pts.reverse();
    if(clear(pts)) out.push({seed:seed, path:pts.map(function(p){ return [r2(p[0]), r2(p[1])]; })});
  });
  return out;
}
/* t: {kids, parent, seqs, flags?}; old: the plan the page has (style, sizes, labels, look flags); style: 'orbit' | 'spoke' (default old's) */
function plan(t, old, style){
  var K=t.kids||{}, Par=t.parent||{}, seqs=t.seqs||[], ids={};
  style=style||(old && old.style)||'orbit';
  seqs.forEach(function(q){ q.forEach(function(i){ ids[i]=1; }); });
  function kids(i){ return (K[i]||[]).filter(function(k){ return ids[k] && Par[k]===i; }); }
  var labels={}; ((old && old.systems)||[]).forEach(function(s){ labels[s.unit]=s.label; });
  var units=[];
  /* every root a sun (a unit may hold several); loose cards orbit the unit's first */
  seqs.forEach(function(mine, a){
    if(!mine.length) return;
    var tops=mine.filter(function(i){ return !Par[i]; }); if(!tops.length) tops=[mine[0]];
    var loose=mine.filter(function(i){ return tops.indexOf(i)<0 && (!Par[i] || !ids[Par[i]]); });
    tops.forEach(function(sun, k){
      units.push([a, sun, kids(sun).concat(k ? [] : loose).map(function(p){ return [p, kids(p).map(function(m){ return [m, kids(m)]; })]; })]); });
  });
  /* the flags on each node: t.flags {id: [flag ids]}, else the page's NODES_SRC; which bump (plan.sizes.bump), which make a look (plan.look_flags) */
  var bump=((old && old.sizes && old.sizes.bump)||[]), LF=(old && old.look_flags)||{}, FL=t.flags||{};
  if(!t.flags && typeof NODES_SRC!=='undefined') NODES_SRC.forEach(function(n){ if(n.flags) FL[n.id]=n.flags; });
  var size=function(i, role, n){ return bodyD(role, n, (FL[i]||[]).some(function(f){ return bump.indexOf(f)>=0; })); };
  var looks={};
  Object.keys(ids).forEach(function(i){ var got=(FL[i]||[]).map(function(f){ return LF[f]; }).filter(function(x){ return x; });
    if(got.length) looks[i]=got.sort(function(a, b){ return LOOKS.indexOf(a)-LOOKS.indexOf(b); })[0]; });
  var sy=units.map(function(u){ return system(u[0], u[1], u[2], style, size, looks); });
  var ws=sy.map(function(s){ return s.box[2]-s.box[0]; }), W=Math.ceil(Math.max.apply(null, [C.WORLD_W].concat(ws.map(function(w){ return w+2*C.MARGIN; }))));
  var inner=W-2*C.MARGIN, rows=[], row=[], span=0, us={};
  sy.forEach(function(s){ us[s.unit]=1; });
  var grouped=Object.keys(us).length<sy.length;      /* a unit of several systems starts a row of its own */
  sy.forEach(function(s, i){ if(row.length && (span+C.SYS_GAP+ws[i] > inner+1e-6 || (grouped && s.unit!==row[row.length-1].unit))){ rows.push(row); row=[]; span=0; }
    span+=(row.length ? C.SYS_GAP : 0)+ws[i]; row.push(s); });
  if(row.length) rows.push(row);
  var nodes={}, systems=[], belts=[], top=C.TOP;
  rows.forEach(function(row){
    var up=mx(row.map(function(s){ return -s.box[1]; })), down=mx(row.map(function(s){ return s.box[3]; }));
    var total=row.reduce(function(a, s){ return a+s.box[2]-s.box[0]; }, 0)+C.SYS_GAP*(row.length-1), left=(W-total)/2, cy=top+up;
    row.forEach(function(s){
      var cx=left-s.box[0]; left+=(s.box[2]-s.box[0])+C.SYS_GAP;
      var pm=(typeof PHASE_META!=='undefined') ? PHASE_META[s.unit] : null;
      systems.push({unit:s.unit, label:labels[s.unit]!=null ? labels[s.unit] : (pm ? pm.label : ''), sun:s.sun, cx:r2(cx), cy:r2(cy), r_sun:s.r_sun, R:r2(s.R),
        bbox:[r2(cx+s.box[0]), r2(cy+s.box[1]), r2(cx+s.box[2]), r2(cy+s.box[3])], planets:s.planets});
      Object.keys(s.local).forEach(function(i){ var c=s.local[i], n={x:r2(cx+c[0]), y:r2(cy+c[1]), d:c[2], role:c[3], unit:s.unit, parent:c[4]};
        if(looks[i]) n.look=looks[i];
        if(s.orbs[i]) n.orbit={e:s.orbs[i].e, rot:s.orbs[i].rot, k:s.orbs[i].k};
        if(style==='orbit' && looks[i]==='asteroid') n.tumble=tumble(i);
        nodes[i]=n; });
      if(s.belt) belts.push({sun:s.sun, cx:r2(cx), cy:r2(cy), r:r2(s.belt.r), w:s.belt.w,
        n:Math.floor(Math.min(400, Math.max(40, 2*PI*s.belt.r/18))), seed:Math.floor(h01('belt:'+s.sun)*1e9)});
    });
    top=cy+down+C.SYS_GAP;
  });
  var H=rows.length ? Math.ceil(top-C.SYS_GAP+C.BOTTOM) : C.TOP+C.BOTTOM, CO=core(systems, W, H, top-C.SYS_GAP);
  H=CO[1];
  var order=systems.map(function(s){ return s.sun; }), uo=[], lk={};
  systems.forEach(function(s){ var u=uo[uo.length-1];
    if(!u || u.unit!==s.unit){ u={unit:s.unit, label:s.label, suns:[], bbox:s.bbox.slice()}; uo.push(u); }
    u.suns.push(s.sun); u.bbox=[Math.min(u.bbox[0], s.bbox[0]), Math.min(u.bbox[1], s.bbox[1]), Math.max(u.bbox[2], s.bbox[2]), Math.max(u.bbox[3], s.bbox[3])]; });
  LOOKS.forEach(function(l){ var a=Object.keys(looks).filter(function(i){ return looks[i]===l; }).sort(); if(a.length) lk[l]=a; });
  var out={style:style, spin:__SPIN__, world:{w:W, h:H}, sizes:(function(){ var z=JSON.parse(JSON.stringify(D)); z.planet_big=C.TIERS.planet[C.TIERS.planet.length-1]; z.tiers=JSON.parse(JSON.stringify(C.TIERS)); z.bump=bump.slice().sort(); return z; })(),
    systems:systems, units:uo, nodes:nodes, sun_links:order.slice(1).map(function(b, i){ return [order[i], b]; }), warnings:[],
    looks:lk, look_flags:JSON.parse(JSON.stringify(LF)), belts:belts, drifters:style==='orbit' ? drifters(systems, CO[0], W, H) : []};
  if(CO[0]) out.core=CO[0];
  return out;
}
/* both looks at once (what the page carries): {look, looks: {stars, plain}} */
window._altoSolarPlans=function(t, old){
  return {look:(old && old.look)||'stars', looks:{stars:plan(t, old, 'orbit'), plain:plan(t, old, 'spoke')}};
};
return plan;
})();
""".replace("__SOLAR__", json.dumps(SOLAR, separators=(",", ":"))).replace("__GOLDEN__", repr(GOLDEN)).replace("__SPIN__", str(SPIN)).replace(
    "__LOOKS__", json.dumps([lk for lk, _ in LOOK_FLAGS]))



def _slim(src: str) -> str:
    """The page copy without its comments and indentation (the source keeps
    them): no string or regex in these scripts holds a slash-star."""
    import re
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(l.strip() for l in src.splitlines() if l.strip()) + "\n"


SOLAR_JS = _slim(SOLAR_PLAN_JS + SOLAR_JS)
SOLAR_CSS = _slim(SOLAR_CSS)
