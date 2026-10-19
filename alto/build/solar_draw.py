"""What the browser draws and does for a solar outline (brief.layout "solar").

solar.py plans the systems (window._ALTO_SOLAR: every circle's t = 0 centre,
its role, diameter and orbit period); the page puts the centres where the plan
says through the tree's own plan runner. This module is the rest, on desktop
only (a phone keeps the engine's column of cards):

* Circles. A resting .node-card is a disc of the plan's diameter showing the
  path number and the title, clamped (.sol-face). Enlarged (the engine's own
  focus fly and zoom ramp) it is the ordinary card again, description and
  chips and all: while the card grows it is clipped from its disc out to the
  card (a real disc whose diameter, --scd, follows the card's own zoom on
  every frame; never a clip-path: Safari resolved one in the wrong box under
  page zoom), and back down to the disc as it shrinks, so neither end of
  the ramp jumps. The engine's .alto-fshadow is a
  card's, which is right: the enlarged thing is a card.
* #solar-svg, under the cards: faint orbit rings (one per body round what it
  orbits: no two bodies share one), a short spoke from each body to what it
  orbits, a faint dashed link between suns, a soft glow behind each sun —
  the same in both looks (the Star chart adds its skin over them). The
  engine's unit bands, labels and bars go (as on a horizontal timeline); a
  chip names each system.
* Motion ("orbit", both looks). One rAF loop turns every body round what it orbits by
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
  html:not(.mobile) #canvas #solar-svg{transition:opacity var(--alto-fly,.25s) var(--alto-ease,ease);}
  html:not(.mobile) #canvas.focus-mode #solar-svg{opacity:.1;}
  html:not(.mobile) #canvas.edge-hover #solar-svg{opacity:.35;}
  .sol-unit{position:absolute;z-index:6;white-space:nowrap;pointer-events:none;font-size:12.5px;font-weight:800;letter-spacing:.12em;
    text-transform:uppercase;color:var(--u);padding:6.25px 12.5px;border-radius:10px;background:color-mix(in srgb,var(--surface) 80%,transparent);
    border:1.5px solid color-mix(in srgb,var(--u) 45%,transparent);}
  .sol-unit b{font-weight:800;opacity:.6;margin-right:7.5px;}
  html.dark .sol-unit{color:color-mix(in srgb,var(--u) 55%,#fff);}
  /* the whole chart (zoomed out to fit): its toggle is the key toggle's round glass, under the bars */
  /* the look switch (Hub & spoke | Star chart) and the orbit switch: glass, under the bars at the top left */
  #sol-ctl{position:fixed;z-index:310;left:30px;top:calc(var(--nav-bottom, 100px) + 14px);display:flex;gap:8px;align-items:center;font-family:inherit;}
  #sol-ctl button{font:inherit;font-size:12.5px;font-weight:600;letter-spacing:.02em;display:inline-flex;align-items:center;gap:6px;cursor:pointer;
    color:var(--muted);background:transparent;border:0;padding:6.25px 11.25px;border-radius:999px;line-height:1;}
  #sol-ctl .sol-seg,#sol-ctl #sol-motion{background:var(--card-glass-bg, var(--surface));-webkit-backdrop-filter:blur(18px) saturate(190%);backdrop-filter:blur(18px) saturate(190%);
    border:1px solid var(--card-glass-border, var(--border));box-shadow:0 10px 26px var(--node-rest-shadow), inset 0 0 0 0.5px var(--card-glass-rim);border-radius:999px;}
  #sol-ctl .sol-seg{display:inline-flex;padding:2.5px;}
  #sol-ctl button:hover:not(:disabled){color:var(--text);}
  #sol-ctl .sol-seg button.on{color:var(--text);background:color-mix(in srgb,var(--accent,#6d5bd0) 16%,transparent);}
  #sol-ctl #sol-motion{padding:8.75px 12.5px;}
  #sol-ctl #sol-motion.on{color:var(--accent,#6d5bd0);}
  #sol-ctl #sol-motion:disabled{opacity:.42;cursor:default;}
  #sol-ctl #sol-motion .sol-ic-play,#sol-ctl #sol-motion.on .sol-ic-pause{display:block;}
  #sol-ctl #sol-motion .sol-ic-pause,#sol-ctl #sol-motion.on .sol-ic-play{display:none;}
  #sol-ctl button:focus-visible{outline:2px solid var(--accent,#6d5bd0);outline-offset:2px;}
  html.mobile #sol-ctl{display:none !important;}
  @media print{ #sol-ctl{display:none !important;} }
  /* no rectangle at any zoom (Luke): the board's own glass is not drawn on a solar page; the page's
     background (Hub & spoke) or the star chart's sky (a fixed, window-filling layer) shows everywhere */
  html.alto-solar:not(.mobile) #world #glass-slab{visibility:hidden !important;}
  #canvas.sol-ov{cursor:zoom-in;}
  #canvas.sol-ov #world,#canvas.sol-ovanim #world{pointer-events:none;transform-origin:0 0;will-change:transform;}
  .sol-face{display:none;}
  /* enlarged: on top at once (the engine holds a node's z-index change back .34s,
     for a card shrinking home; a moon beside its planet would cover the card) */
  html.alto-solar:not(.mobile) #world .node[data-solar].focused{transition:z-index 0s !important;}
  /* a body is a disc at rest (--sd) and a bigger disc enlarged (--sD): never a rectangle. Inside its
     .node-card, bottom to top: a skin (VIS, solar_stars.py: z-index <= 1), .sol-scrim (z 2, enlarged
     only), then .sol-face / .sol-body / .sol-open (z 3). The round clip is the card's own. */
  html.alto-solar:not(.mobile) #world .node[data-solar] .node-card{min-height:0 !important;padding:0 !important;border-radius:50% !important;
    overflow:hidden;box-sizing:border-box;}
  html.alto-solar:not(.mobile) #world .node[data-solar]:not(.focused):not(.sol-closing) .node-card{width:var(--sd) !important;height:var(--sd) !important;border-top-width:1.5px;}
  html.alto-solar:not(.mobile) #world .node[data-solar].focused .node-card,html.alto-solar:not(.mobile) #world .node[data-solar].sol-closing .node-card{
    width:var(--scd,var(--sD)) !important;height:var(--scd,var(--sD)) !important;}
  html.alto-solar:not(.mobile) #world .node[data-solar] .node-card::before{left:0;right:0;top:0;height:100%;border-radius:50%;
    background:radial-gradient(ellipse 72% 52% at 50% 14%,var(--card-glass-sheen) 0%,rgba(255,255,255,.08) 58%,rgba(255,255,255,0) 100%);}
  html.alto-solar #world .alto-fshadow{border-radius:50% !important;}
  html.alto-solar:not(.mobile) #world .node[data-solar] .sol-face{display:flex;position:absolute;z-index:3;left:50%;top:50%;width:var(--sd);height:var(--sd);
    margin:calc(var(--sd) / -2) 0 0 calc(var(--sd) / -2);flex-direction:column;align-items:center;justify-content:center;gap:2.5px;
    text-align:center;box-sizing:border-box;padding:0 calc(var(--sd) * .15);pointer-events:none;color:var(--text);}
  html.alto-solar:not(.mobile) #world .node[data-solar].focused:not(.sol-clip) .sol-face{display:none;}
  .sol-face b{font-weight:600;font-variant-numeric:tabular-nums;opacity:.72;font-size:10px;line-height:12.5px;letter-spacing:.02em;}
  .sol-face span{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;line-clamp:3;overflow:hidden;
    overflow-wrap:break-word;hyphens:auto;-webkit-hyphens:auto;font-size:12.5px;line-height:15px;max-width:100%;}
  .node[data-solar=sun] .sol-face b{font-size:12.5px;line-height:15px;}
  .node[data-solar=sun] .sol-face span{font-size:16.25px;line-height:20px;-webkit-line-clamp:4;line-clamp:4;}
  /* moons and satellites are small (real-ratio sizes, round 7): a moon shows its own number only, a
     satellite nothing; their number and title are the card's tooltip and accessible name, and the
     enlarged disc's */
  .node[data-solar=moon] .sol-face{padding:0;}
  .node[data-solar=moon] .sol-face b{font-size:10px;line-height:12.5px;opacity:.9;}
  .node[data-solar=moon] .sol-face span,.node[data-solar=sat] .sol-face span,.node[data-solar=sat] .sol-face b{display:none;}
  /* enlarged: the content, in a square inscribed in the disc (corners inside the circle), scrolling
     inside it when long, faded at its top and bottom edges; "Open full page" under it */
  .sol-body,.sol-scrim,.sol-open{display:none;}
  html.alto-solar:not(.mobile) #world .node[data-solar].focused .sol-body,html.alto-solar:not(.mobile) #world .node[data-solar].sol-closing .sol-body{
    display:block;position:absolute;z-index:3;left:calc(50% - var(--sD) * .33);width:calc(var(--sD) * .66);top:calc(50% - var(--sD) * .36);height:calc(var(--sD) * .65);overflow-x:hidden;overflow-y:auto;overscroll-behavior:contain;
    text-align:center;box-sizing:border-box;padding:12px 4px 16px;scrollbar-width:thin;opacity:var(--sbo,1);
    -webkit-mask-image:linear-gradient(transparent,#000 12px,#000 calc(100% - 16px),transparent);mask-image:linear-gradient(transparent,#000 12px,#000 calc(100% - 16px),transparent);}
  html.alto-solar:not(.mobile) #world .node[data-solar].focused .sol-scrim,html.alto-solar:not(.mobile) #world .node[data-solar].sol-closing .sol-scrim{
    display:block;position:absolute;z-index:2;inset:0;border-radius:50%;pointer-events:none;opacity:var(--sbo,1);
    background:radial-gradient(circle,color-mix(in srgb,var(--surface) 84%,transparent) 0 64%,color-mix(in srgb,var(--surface) 52%,transparent) 100%);}
  html.alto-solar:not(.mobile) #world .node[data-solar].focused .sol-open,html.alto-solar:not(.mobile) #world .node[data-solar].sol-closing .sol-open{
    display:block;position:absolute;z-index:3;left:0;right:0;top:calc(50% + var(--sD) * .315);margin:0 auto;width:max-content;max-width:calc(var(--sD) * .5);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;box-sizing:border-box;opacity:var(--sbo,1);cursor:pointer;
    font:600 11.25px/1 inherit;font-family:inherit;letter-spacing:.04em;color:var(--accent,#6d5bd0);padding:6px 12.5px;border-radius:999px;
    background:color-mix(in srgb,var(--surface) 90%,transparent);border:1px solid color-mix(in srgb,var(--accent,#6d5bd0) 45%,transparent);}
  .sol-open:hover{background:var(--surface);}
  .sol-body .node-order{position:static !important;float:none !important;display:block;margin:0 0 4px !important;text-align:center;}
  .sol-body .node-tag,.sol-body .node-title,.sol-body .node-desc{text-align:center;}
  html.alto-solar:not(.mobile) #world .node[data-solar] .sol-body .node-tag{padding-left:0 !important;padding-right:0 !important;}   /* (a card's tag leaves room for its number; the disc's is above it) */
  .sol-body .node-desc{-webkit-line-clamp:unset !important;display:block !important;overflow:visible !important;}
  .sol-body .node-footer{justify-content:center;flex-wrap:wrap;margin-top:8px;}
  .sol-sec{margin-top:10px;text-align:left;font-size:12.5px;line-height:18.75px;color:var(--card-desc-color,var(--muted));}
  .sol-sec h6{margin:0 0 2px;font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:700;text-align:center;}
  /* growing / shrinking (--scd): no frost on the moving disc (a zoomed element can lose it anyway), never a clip-path */
  html.alto-solar:not(.mobile) #world .node.sol-clip .node-card{-webkit-backdrop-filter:none !important;backdrop-filter:none !important;background:var(--node-glass-bg,var(--panel-glass-bg)) !important;}
  html.alto-solar:not(.mobile) #world .node.sol-clip .sol-face{opacity:var(--sfo,0);}
"""

SOLAR_JS = r"""
/* The renderer: a function of the plan (window._ALTO_SOLAR, solar.page_plans: the plan and
   look:'stars'|'hub', the look a viewer sees first) mounted on the engine's #world. One Hub &
   spoke page, ONE plan, two looks (Luke, round 7): Hub & spoke (rings, spokes, glass circles)
   and the Star chart (the same, plus the skin, solar_stars.py, and flights, solar_fly.py); both
   orbit. One mount per page (its engine hooks are page globals). */
window._altoSolarMount=function(R, opt){
opt=opt||{}; if(!R || window._altoSolarMounted) return false;
var de=document.documentElement, NS='http://www.w3.org/2000/svg', TAU=Math.PI*2, K=1.7;
/* the viewer's choices, per timeline (look, motion) */
var KEY=(typeof COURSE_ID!=='undefined' && COURSE_ID) || 'page';
function pref(k){ try{ return localStorage.getItem('alto-solar-'+k+':'+KEY); }catch(e){ return null; } }
function keep(k, v){ try{ localStorage.setItem('alto-solar-'+k+':'+KEY, String(v)); }catch(e){} }
function lk(v){ return v==='hub' || v==='plain' ? 'hub' : v==='stars' ? 'stars' : null; }   /* ('plain': 1.9.108's still look, now Hub & spoke) */
var LOOK=lk(pref('look')) || lk(R.look) || 'stars';
var S=R;
if(!S || !S.nodes) return false; window._altoSolarMounted=true;
window._altoSolarView=1;          /* the opening view is this script's (openView), not the engine's centreWorld */
var ORBIT, SPIN, DEF=S.sizes||{sun:184, planet:96, moon:50, sat:20}, NUM=null;
function desk(){ return !de.classList.contains('mobile'); }
if(desk()) de.classList.add('alto-solar');
/* the bodies, each after what it orbits */
var B={}, ORD=[], SY=[], MOVES=false;
function q(v){ return Math.round(v/2.5)*2.5; }      /* D-GRID: half a diameter on the 1.25px grid */
function body(id, role, p, per, si, o){
  var n=S.nodes[id]||{}; B[id]={id:id, role:role, p:p, per:ORBIT ? (+per||0) : 0, si:si, d:q(n.d||DEF[role]),
    orb:(ORBIT && n.orbit && n.orbit.e>0 && o) ? n.orbit : null, r:o ? +o.r : 0, a0:o ? +o.a0 : 0,
    look:n.look||'', tumble:ORBIT ? (+n.tumble||0) : 0}; ORD.push(id); }
function bodies(){
  ORBIT=S.style!=='spoke'; SPIN=S.spin||-1; B={}; ORD=[]; SY=S.systems||[];
  SY.forEach(function(s, si){ body(s.sun, 'sun', null, 0, si);
    (s.planets||[]).forEach(function(pl){ body(pl.id, 'planet', s.sun, pl.period, si, pl);
      (pl.moons||[]).forEach(function(m){ body(m.id, 'moon', pl.id, m.period, si, m);
        (m.sats||[]).forEach(function(t){ body(t.id, 'sat', m.id, t.period, si, t); }); }); }); });
  MOVES=ORBIT && ORD.some(function(i){ return B[i].per>0; });
}
bodies();
looks();
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
  var small=b.role==='moon' || b.role==='sat';
  f.querySelector('b').textContent=small ? (num.split(/[.\-]/).pop()||num) : num;
  var sp=f.querySelector('span'), base={sun:16.25, planet:12.5, moon:8.75}[b.role], L=Math.max.apply(null, tt.split(/\s+/).map(function(w){ return w.length; }).concat([1]));
  sp.textContent=tt; sp.style.fontSize=sp.style.lineHeight='';
  /* a word too long for the disc: the type steps down (to 72%) before a word is broken */
  var fs=base ? Math.max(base*.72, Math.min(base, b.d*.68/(L*.55))) : 0;
  if(fs && fs<base){ fs=Math.round(fs*4)/4; sp.style.fontSize=fs+'px'; sp.style.lineHeight=Math.round(fs*1.2*4)/4+'px'; }
  f.setAttribute('aria-hidden', 'true');
  if(small){ c.setAttribute('title', (num ? num+'  ' : '')+tt); c.setAttribute('aria-label', (num ? num+' ' : '')+tt); }
  disc(n, c, id, b);
}
/* the enlarged disc's layers: the card's own number / tag / title / description / chips go into
   .sol-body (the same elements, so edit mode edits them in place), a .sol-scrim under it, the
   "Open full page" control; and --sD, the enlarged diameter, by how much there is to read */
function disc(n, c, id, b){
  var body=c.querySelector(':scope > .sol-body');
  if(!body){ body=document.createElement('div'); body.className='sol-body';
    [].slice.call(c.children).forEach(function(k){ if(/(^| )(node-order|node-tag|node-title|node-desc|node-footer)( |$)/.test(k.className)) body.appendChild(k); });
    var sc=document.createElement('div'); sc.className='sol-scrim'; sc.setAttribute('aria-hidden', 'true');
    c.insertBefore(sc, c.firstChild); c.appendChild(body);
    var op=document.createElement('button'); op.type='button'; op.className='sol-open'; op.textContent='Open full page';
    op.addEventListener('click', function(e){ e.stopPropagation(); e.preventDefault(); if(typeof showDetail==='function') showDetail('node', id); });
    c.appendChild(op);
    /* an enlarged disc is for reading: a click on it does not open the detail page (the control does) */
    c.addEventListener('click', function(e){ if(n.classList.contains('focused') && !de.classList.contains('alto-editing') && !(e.target.closest && e.target.closest('a,button,[onclick],.alto-link'))) e.stopPropagation(); }, true);
  }
  var nd=(typeof NODE_DETAILS!=='undefined' && NODE_DETAILS[id]) || {}, L=(c.textContent||'').length;
  (nd.sections||[]).forEach(function(q){ if(q && q.t) L+=String(q.h||'').length+String(q.t).replace(/<[^>]*>/g, '').length; });
  var D=L<260 ? 300 : L<600 ? 340 : L<1100 ? 380 : 420;
  n.style.setProperty('--sD', Math.max(D, q(b.d+40))+'px');
}
/* the sections (the detail page's, NODE_DETAILS), built the first time a disc is enlarged */
function sections(c, id){
  var body=c.querySelector('.sol-body'); if(!body || body.querySelector('.sol-sec')) return;
  var nd=(typeof NODE_DETAILS!=='undefined' && NODE_DETAILS[id]) || {}, ft=body.querySelector('.node-footer');
  (nd.sections||[]).filter(function(q){ return q && q.t; }).forEach(function(q){
    var d=document.createElement('div'); d.className='sol-sec';
    if(q.h){ var h=document.createElement('h6'); h.textContent=q.h; d.appendChild(h); }
    var t=document.createElement('div'); t.innerHTML=String(q.t); d.appendChild(t);       /* the build's sanitized markup, as the detail page shows it */
    body.insertBefore(d, ft||null);
  });
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
    if(!n.classList.contains('focused')){ n.style.setProperty('--mx', (-b.d/2)+'px'); n.style.setProperty('--my', (-b.d/2)+'px'); }   /* centred at once (D-GRID's ResizeObserver would only catch up at the next frame) */
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
  apply(true); skin();
  if(MOVES) go();
  ctl();
  if(OV){ ovHold(true); clampO(OV); ovSet(OV); }
  fitBtn();
  if(!opened) setTimeout(openView, 0);
};
/* ── where the page opens (once, on the first layout) ──────────────────────
   A chart bigger than the window opened on the top of the board — a district
   chip over empty space, the first sun below the fold (Luke, Torts, 1.9.105).
   It opens on the first sun (the plan's first system) at full size, in the
   middle of the window; a chart small enough to read whole (the whole-chart
   fit at 0.6 or more) opens zoomed out to all of it. Hub & spoke keeps the
   engine's opening (centred across, at the top) while its first sun is in
   view there. A view something else asked for wins: a #find= link, an
   enlarged card, the detail page, a canvas already scrolled down. */
var opened=false;
function openView(){
  var c=cvs(); if(opened || !c || !c.clientWidth || !ready || !desk()) return;
  opened=true;
  var over=c.scrollWidth-c.clientWidth, dl=over>1 ? Math.round(over/2) : 0;   /* the engine's centreWorld */
  if(/[#&]find=/.test(String(document.URL).split('#')[1]||'') || window._focusedNodeId || c.scrollTop>1 || document.querySelector('#detail-page.visible')) return;
  var b=SY[0] && B[SY[0].sun];
  if(!b || !b.n){ c.scrollLeft=dl; return; }
  var off=woff(c), cw=c.clientWidth, ch=c.clientHeight, x=b.hx+off.x, y=b.hy+off.y, r=b.d/2;
  var f=fitS();
  if(f>=1){ c.scrollLeft=dl; return; }                                        /* all of it in view as it is */
  if(f>=.6){ ovZoom(f, null, null, false); return; }
  var sl=Math.max(0, Math.min(c.scrollWidth-cw, x-cw/2)), st=Math.max(0, Math.min(c.scrollHeight-ch, y-ch/2)), ax=window._altoScrollAxis;
  if(ax){ ax('scrollLeft').go(sl); ax('scrollTop').go(st); } else { c.scrollLeft=sl; c.scrollTop=st; }
}
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
    /* rings: each planet's round the sun, each moon's round its planet, each satellite's round its moon */
    var seen={};
    ORD.forEach(function(id){
      var b=B[id]; if(b.si!==si || !b.p || !b.n) return;
      var p=B[b.p]; if(!p.n) return;
      if(b.orb && window._altoSolarAt){                 /* a comet's path: its ellipse about what it orbits */
        var c0=window._altoSolarAt(b.r, b.a0, b.orb), qq=(function(e){ var q=Math.sqrt(Math.max(0, 1-e*e)); return (1-q)/(1+q); })(b.orb.e);
        rings.push({c:b.p, ox:b.hx-p.hx-c0[0], oy:b.hy-p.hy-c0[1], rot:b.orb.rot*180/Math.PI,
          e:el('ellipse', {'class':'sol-ring sol-comet'+(b.role==='planet' ? '' : ' sol-m'), rx:f2(b.r*(1+qq)), ry:f2(b.r*(1-qq))}, g)});
      } else { var r=Math.hypot(b.hx-p.hx, b.hy-p.hy), k=b.p+'|'+Math.round(r/2);
        if(!seen[k]){ seen[k]=1; rings.push({c:b.p, e:el('circle', {'class':'sol-ring'+(b.role==='planet' ? '' : ' sol-m'), r:f2(r)}, g)}); } }
      spokes.push({a:b.p, b:id, e:[el('line', {'class':'sol-spoke'}, g)]});
    });
    /* one chip per unit (a district of several systems: over all of them) */
    var U=null; (S.units||[]).forEach(function(q){ if(q.suns && q.suns[0]===s.sun) U=q; });
    var pm=(typeof PHASE_META!=='undefined') ? PHASE_META[s.unit] : null, lbl=(U && U.label) || s.label || (pm ? pm.label : ''), bb=(U && U.bbox) || s.bbox;
    lbl=String(lbl).split(' — ').pop();
    if(lbl && (U || !S.units)){ var ch=document.createElement('div'); ch.className='sol-unit'; if(u) ch.style.setProperty('--u', u);
      ch.setAttribute('data-unit', s.unit); ch.innerHTML='<b></b><span></span>'; ch.querySelector('b').textContent=pm ? pm.numeral : ''; ch.querySelector('span').textContent=lbl;
      world.appendChild(ch);
      var top=Math.max(PAD+24, (bb ? bb[1]+PAD : sun.hy-(s.R||sun.d))-44);
      ch.style.left=Math.round((U ? (bb[0]+bb[2])/2 : sun.hx)-ch.offsetWidth/2)+'px'; ch.style.top=Math.round(top)+'px'; chips.push(ch); }
  });
  var lg=el('g', {'class':'sol-links'}, svg);
  (S.sun_links||[]).forEach(function(l){ if(!B[l[0]] || !B[l[1]] || !B[l[0]].n || !B[l[1]].n) return;
    sunl.push({a:l[0], b:l[1], e:[el('path', {'class':'sol-link'}, lg)]}); });
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
  var mqf=function(){ reduced=mq.matches; if(pref('motion')==null){ MOTION=!reduced; ctl(); } go(); }; if(mq.addEventListener) mq.addEventListener('change', mqf); else mq.addListener(mqf); }catch(e){}
/* the orbit switch (both looks): on by default, off by default for reduced motion, the viewer's choice kept */
var MOTION=pref('motion')==null ? !reduced : pref('motion')==='1', RAMP=1.2;
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
    if(b.orb && window._altoSolarAt){ var o=window._altoSolarAt(b.r, b.a0+a, b.orb), o0=window._altoSolarAt(b.r, b.a0, b.orb);   /* a comet: its ellipse (solar.orbit_offset), anchored at its plan home */
      b.x=p.x+dx+(o[0]-o0[0]); b.y=p.y+dy+(o[1]-o0[1]); return; }
    b.x=p.x+dx*cs-dy*sn; b.y=p.y+dx*sn+dy*cs;
  });
}
function seg(a, b, ga, gb){
  var dx=b.rx-a.rx, dy=b.ry-a.ry, L=Math.hypot(dx, dy)||1, ux=dx/L, uy=dy/L, ra=a.d/2+ga, rb=b.d/2+gb;
  if(L<=ra+rb) return null;
  return [f2(a.rx+ux*ra), f2(a.ry+uy*ra), f2(b.rx-ux*rb), f2(b.ry-uy*rb)];
}
/* ── seams for the star chart's skin (solar_stars.py) and its travel (solar_fly.py) ──
   window._altoSolarT: the orbit clock in seconds — a body's angle is a0 + spin*2*pi*T/period
     about what it orbits (plus, with several systems, spin*2*pi*T/(540+60*system index) for the
     whole system about its sun): solar.py's formula, as place() runs it.
   window._altoSkinTick(plan, bodies, T), if defined, is called after every frame that moved the
     bodies, and once after each layout. bodies: {id: {id, role, p (what it orbits), per, si
     (system index), d (diameter), n (.node), c (.node-card), hx, hy (home), x, y (now, float),
     rx, ry (now, as written to left/top), r, a0 (its orbit's radius and t = 0 angle), orb (a comet's
     ellipse {e, rot, k}, else null), look ('blackhole' | 'comet' | 'asteroid' | ''), tumble (an
     asteroid's spin, rad/s: its angle is tumble * T)}} — world px (WORLD_PAD_TOP included). Read-only.
     A comet's place: the plan's formula (solar.orbit_offset, window._altoSolarAt(r, angle, orb)) at
     angle a0 + spin*2*pi*T/period (+ the system's turn), about what it orbits.
     Not called while the orbit is held (hover, focus, edit mode...): a skin that animates on its
     own runs its own frames. A skin's layers go inside .node-card under .sol-scrim (z-index <= 1). */
function skin(){ window._altoSolarT=T; if(window._altoSkinTick) try{ window._altoSkinTick(S, B, T); }catch(e){} }
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
  rings.forEach(function(r){ if(!moved[r.c]) return; var cx=f2(B[r.c].rx+(r.ox||0)), cy=f2(B[r.c].ry+(r.oy||0));
    r.e.setAttribute('cx', cx); r.e.setAttribute('cy', cy); if(r.rot!=null) r.e.setAttribute('transform', 'rotate('+f2(r.rot)+' '+cx+' '+cy+')'); });
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
  if(!MOVES || !MOTION || !desk() || document.hidden || hov) return true;
  if(window._focusedNodeId || document.querySelector('#canvas.focus-mode,#canvas.edge-hover,#detail-page.visible')) return true;
  return !!document.querySelector('#world .node.alto-found,#world .node.sol-closing,#world .node-card.dimmed,#world .node-card.rel-dimmed,#world .node-card.ent-dimmed');
}
function tick(ts){
  raf=0; if(!ready || DRV) return;
  var dt=last==null ? 0 : Math.min(.1, (ts-last)/1000); last=ts;
  if(OV && (de.classList.contains('alto-editing') || window._focusedNodeId)) ovLeave(null, true);
  if(de.classList.contains('alto-editing') || printing){          /* the plan's own layout, turned back to */
    sp=0; if(T){ back=printing ? 0 : Math.max(0, back-dt/.45); rk=back*back*(3-2*back); apply(); skin(); if(back) return go(); T=0; back=rk=1; }
    return sleep(); }
  if(back<1){ T=0; back=rk=1; apply(); }
  if(hold()){ sp=0; return sleep(); }
  sp=Math.min(1, sp+dt/RAMP); if(sp>=1) RAMP=1.2; T+=dt*sp*sp*(3-2*sp); apply(); skin(); go();
}
function go(){ clearTimeout(slT); if(!raf && MOVES && (MOTION || (T && (printing || de.classList.contains('alto-editing'))))) raf=requestAnimationFrame(tick); }   /* Orbit off: no frames at all (but edit mode / print still turn it home) */
function sleep(){ last=null; clearTimeout(slT); slT=setTimeout(go, 180); }
/* a flight (solar_fly.py) drives the clock: while it flies T is its own, set every
   frame, and the loop here waits; let go, the orbits run on from the rate it hands
   back (0: still, 1: full speed), easing as ever. _altoSolarRate: the rate now. */
var DRV=0;
window._altoSolarDrive=function(t, r){
  if(t==null){ if(DRV){ DRV=0; r=Math.max(0, Math.min(1, +r||0)); sp=r>0 ? .5-Math.sin(Math.asin(1-2*r)/3) : 0; last=null; go(); } return T; }
  if(!DRV){ DRV=1; cancelAnimationFrame(raf); raf=0; clearTimeout(slT); }
  T=t; back=rk=1; apply(); skin(); return T;
};
window._altoSolarRate=function(){ return {T:T, r:(DRV || !MOVES || hold() || de.classList.contains('alto-editing') || printing) ? 0 : sp*sp*(3-2*sp)}; };
window.addEventListener('beforeprint', function(){ printing=1; ovLeave(null, true); if(T){ T=0; rk=1; apply(); } });
window.addEventListener('afterprint', function(){ printing=0; go(); });
document.addEventListener('visibilitychange', function(){ last=null; go(); });
/* a hover is the pointer moving onto a circle or a line, not one sliding under a still pointer */
function hot(t){ return t && t.closest && t.closest('#world .node[data-solar],#river-svg [data-edge-hit]'); }
function over(e){ if(!hot(e.target) || (window._altoPointerStill && window._altoPointerStill(e))) return; clearTimeout(hovT); hov=1; }
document.addEventListener('mouseover', over); document.addEventListener('mousemove', over, {passive:true});
document.addEventListener('mouseout', function(e){ if(hot(e.relatedTarget)) return; clearTimeout(hovT); hovT=setTimeout(function(){ hov=0; }, 320); });

/* ── an enlarged circle stays a circle (Luke, rounds 4 and 7): no clip-path. Under Safari's page zoom a
   clip-path circle() on a zoomed card was resolved in another box than the one painted (Luke's Torts
   copy, Safari 27, html zoom 0.86: a smaller circle up-left of the card, the text running out of its
   bottom, the card's own edge showing as an arc and its shadow a bigger circle down-right). So the
   card is a REAL disc at every frame: border-radius 50% and overflow hidden on a box whose diameter
   (--scd) goes from the resting disc's to the enlarged one's (--sD) with the engine's zoom ramp, read
   off the card's own zoom on every frame. The content sits at fixed px about the centre (sized by
   --sD), so it never re-wraps and the growing disc reveals it; the engine's .alto-fshadow is kept the
   same circle (its scale set from the card's real diameter). The face fades out, the content
   (.sol-body, .sol-scrim, .sol-open) fades in. ───── */
var zmo=(typeof MutationObserver==='function') ? new MutationObserver(function(ms){ ms.forEach(function(m){ var n=m.target.closest && m.target.closest('.node'); if(n) clip(n); }); }) : null, morphing=[], mraf=0;
function sDof(n, b){ return parseFloat(n.style.getPropertyValue('--sD'))||b.d; }
/* the focus shadow: the card's circle, whatever size the engine measured it at */
function shade(n, w, z){
  var sh=n._fsh, g=sh && sh._g, W=sh ? parseFloat(sh.style.width)||0 : 0; if(!W || !g) return;
  var want=w*z;                                                 /* the disc's diameter in the board's px */
  if(Math.abs(z-K)<1e-4 && Math.abs(want-W)<0.5) return;        /* full size: the engine's own placement is this circle */
  sh.style.left=g[0]+'px'; sh.style.top=g[1]+'px';
  sh.style.transform='translate('+(n._fx||0)+'px,'+(n._fy||0)+'px) scale('+f2(want/W*1e4)/1e4+')';
}
function clip(n){
  var c=n.querySelector('.node-card'), b=B[(n.id||'').slice(5)]; if(!c || !b) return;
  var z=parseFloat(c.style.zoom)||1, f=n.classList.contains('focused'), i=morphing.indexOf(c);
  if(i<0 && !f) return;
  if(!f && z<=1.0005){                                         /* home: a circle again */
    n.classList.remove('sol-closing'); n.classList.remove('sol-clip');
    ['--scd','--sfo','--sbo'].forEach(function(v){ n.style.removeProperty(v); });
    if(i>=0) morphing.splice(i, 1);
    if(!morphing.length) go();
    return; }
  var p=Math.max(0, Math.min(1, (z-1)/(K-1)*1.5)), s=p*p*(3-2*p), d=b.d, D=sDof(n, b);
  if(f && s>=1){ n.classList.remove('sol-clip'); ['--scd','--sfo','--sbo'].forEach(function(v){ n.style.removeProperty(v); });
    if(i>=0) morphing.splice(i, 1); shade(n, D, z); return; }
  n.classList.add('sol-clip');
  var w=f2(d+(D-d)*s);                                          /* the disc's own diameter, from the resting one to the enlarged one */
  n.style.setProperty('--scd', w+'px');
  n.style.setProperty('--sfo', String(Math.max(0, 1-s*2.2))); n.style.setProperty('--sbo', String(Math.min(1, s*1.6)));
  shade(n, w, z);
}
/* a backstop to the observer: every morphing disc is looked at once a frame until it has settled */
function msweep(){ mraf=0; morphing.slice().forEach(function(c){ var n=c.closest && c.closest('.node'); if(n) clip(n); }); if(morphing.length) mraf=requestAnimationFrame(msweep); }
function morph(n, open){
  var c=n.querySelector('.node-card'); if(!c) return;
  if(!open) n.classList.add('sol-closing');
  if(open) sections(c, (n.id||'').slice(5));
  var bd=c.querySelector('.sol-body'); if(open && bd) bd.scrollTop=0;
  if(morphing.indexOf(c)<0) morphing.push(c);
  if(zmo && !c._zmo){ c._zmo=1; zmo.observe(c, {attributes:true, attributeFilter:['style']}); }
  clip(n);
  if(!mraf && morphing.length) mraf=requestAnimationFrame(msweep);
}
function watch(){
  var w=document.getElementById('world'); if(!w || typeof MutationObserver!=='function') return;
  var cv=document.getElementById('canvas'); if(cv) cv.addEventListener('scroll', camTell, {passive:true});
  new MutationObserver(camTell).observe(w, {attributes:true, attributeFilter:['style']});   /* the board's pan (focus fly) and transform */
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
  usePlan(P);
  NUM=t.num||NUM; bodies(); T=0; back=rk=1;
  treePlan(P, t.seqs||[]);
  return true;
};
/* the page's tree plan (layout float ops) follows the plan, so initLayout puts every circle there */
function treePlan(P, seqs){
  var TP=window._ALTO_TREE_PLAN;
  if(TP){ TP.x={}; TP.w={}; TP.acts=[]; TP.cx=P.world.w/2; TP.shift=null; TP.slide=null;
    seqs.forEach(function(ids, a){ TP.acts[a]=[];
      ids.forEach(function(id){ var n=P.nodes[id]; if(!n) return; TP.x[id]=n.x; TP.w[id]=n.d; TP.acts[a].push(['float', ['card', id, 0], n.y, 'mid']); }); }); }
}
/* the plan now drawn: S, mirrored on window._ALTO_SOLAR (what FLY / VIS read) */
function usePlan(P){
  S=P;
  for(var k0 in R) if(k0!=='look' && !(k0 in P)) delete R[k0];
  for(var k in P) if(k!=='look') R[k]=P[k];
}
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
/* the zoomed-out board: any scale from OVMIN to natural size; moved freely, only held so that at
   least KEEP px of the chart stay in the window (it can be pushed aside, never lost) */
var KEEP=160;
function clampO(o){ var c=cvs(), cw=c.clientWidth, ch=c.clientHeight, w, h;
  o.s=Math.max(OVMIN, Math.min(1, o.s));
  w=world.offsetWidth*o.s; h=wh()*o.s;
  o.tx=Math.max(Math.min(KEEP, w)-w, Math.min(cw-Math.min(KEEP, w), o.tx)); o.ty=Math.max(Math.min(KEEP, h)-h, Math.min(ch-Math.min(KEEP, h), o.ty)); return o; }
function ovSet(o){ var off=woff(cvs()); world.style.transform='translate('+rd(o.tx-off.x)+'px,'+rd(o.ty-off.y)+'px) scale('+o.s+')'; camTell(); }
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
    if(window._focusedNodeId && window.exitFocus){ window.exitFocus(); setTimeout(function(){ ovZoom(s, null, null, anim); }, UNF); return; }
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
function fitBtn(){ var t=document.getElementById('sol-fit'); if(t) t.remove(); }   /* (the whole-chart button is gone: zoom is continuous) */
function mine(e){ var c=cvs(); return c && e.target && c.contains(e.target); }
/* ── pinch / ctrl+wheel: one gesture, one owner ──────────────────────────────
   Luke, 1.9.105: "If I zoom in and try to zoom back out, it basically doesn't
   work." Three faults, all here: (1) a pinch at rest let Safari's own page zoom
   start — gesturestart was stopped before the engine's preventDefault and never
   prevented here; (2) gestureend was swallowed even when this script had done
   nothing, so a pinch IN at rest never enlarged a card in Safari, and from the
   whole chart a pinch in stalled short of full size; (3) one ctrl+wheel stream
   did two things — left the whole chart and then enlarged whatever was under
   the pointer, or (from a card) let it go and dropped straight on.
   Now every gesture event is prevented (no native zoom, ever), and each gesture
   (a pinch, or a ctrl+wheel stream: events < 220 ms apart) has ONE owner,
   decided at its start: zooming out at rest or anything on the whole chart is
   this script's (the board's scale); zooming in at rest, or anything while a
   card is enlarged, is the engine's (enlarge / let go). A gesture stops at full
   size (a new one enlarges a card). Zooming out of an enlarged card lets it go
   at once and, once the engine's glide home is over (UNF ms), carries on into
   the whole chart in the same movement. */
var ZS=null, UNF=380;
function gpt(e){ var c=cvs(); return (e.clientX!=null && mine(e)) ? local(e) : {x:c.clientWidth/2, y:c.clientHeight/2}; }
/* enlarge (the engine's focus) the body under the event's point, else the nearest to it */
function enlargeAt(e){
  var el=document.elementFromPoint(e.clientX||0, e.clientY||0), n=el && el.closest && el.closest('#world .node[data-solar]'), id=n ? n.id.slice(5) : null;
  if(!id){ var c=cvs(), q=local(e), off=woff(c); id=nearest(c.scrollLeft+q.x-off.x, c.scrollTop+q.y-off.y); }
  if(id && window.enterFocus) window.enterFocus(id);
}
function ovStep(s2, q){                                   /* this gesture's scale; false once it has come back to full size */
  if(s2>=.999){ if(!OV) return true; ovLeave({x:(q.x-OV.tx)/OV.s, y:(q.y-OV.ty)/OV.s}, true); return false; }
  ovZoom(s2, q.x, q.y, false); return true;
}
window.addEventListener('wheel', function(e){
  if(!ready || !desk()) return;
  if(e.ctrlKey) e.preventDefault();                        /* never the browser's own zoom, wherever the pointer is (the engine's own
                                                              wheel listener is passive at rest in Safari, so its preventDefault is not heard) */
  if(!mine(e)) return;
  if(!e.ctrlKey){
    var sb=e.target.closest && e.target.closest('#world .node.focused .sol-body');
    if(sb && !OV && sb.scrollHeight>sb.clientHeight+1 && (e.deltaY<0 ? sb.scrollTop>0 : sb.scrollTop+sb.clientHeight<sb.scrollHeight-1)){ e.stopImmediatePropagation(); return; }   /* the enlarged disc's own text scrolls */
    if(!OV) return;
    e.preventDefault(); e.stopImmediatePropagation();
    var mm=e.deltaMode===1 ? 40 : e.deltaMode===2 ? 800 : 1;
    OV.tx-=e.deltaX*mm; OV.ty-=e.deltaY*mm; if(e.shiftKey && !e.deltaX){ OV.ty+=e.deltaY*mm; OV.tx-=e.deltaY*mm; }
    clampO(OV); ovSet(OV); return;
  }
  var now=performance.now(), f=!!window._focusedNodeId;
  if(!ZS || ZS.k!=='w' || now-ZS.t>220) ZS={k:'w', own:(f || (!OV && e.deltaY<0)) ? 'engine' : 'me', f0:f, ex:0, done:false};
  ZS.t=now;
  if(ZS.own==='engine'){
    if(f===ZS.f0) return;                                  /* the engine's, until it has acted */
    e.stopImmediatePropagation();
    if(!(ZS.f0 && e.deltaY>0)) return;                     /* it enlarged a card: the rest of this gesture is spent */
    if(!ZS.ex) ZS.ex=now; if(now-ZS.ex<UNF) return;        /* let go: on into the whole chart once it is home */
    ZS.own='me';
  }
  e.stopImmediatePropagation();
  if(ZS.done) return;
  var m=e.deltaMode===1 ? 40 : e.deltaMode===2 ? 800 : 1;
  if(!OV){                                                 /* at natural size: zooming on in enlarges the body under the pointer */
    if(e.deltaY<0){ ZS.acc=(ZS.acc||0)-e.deltaY*m; if(ZS.acc>48){ ZS.done=true; enlargeAt(e); } }
    else ZS.acc=0;
    if(e.deltaY<=0) return;
  }
  ovStep((OV ? OV.s : 1)*Math.max(.5, Math.min(2, Math.exp(-e.deltaY*m*.012))), local(e));
}, {passive:false, capture:true});
/* Safari: a trackpad pinch is gesturestart / gesturechange / gestureend */
document.addEventListener('gesturestart', function(e){
  e.preventDefault();
  if(!ready || !desk()){ ZS=null; return; }
  var f=!!window._focusedNodeId;
  ZS={k:'g', own:f ? 'engine' : (OV ? 'me' : '?'), f0:f, base:OV ? OV.s : 1, sx:1, ex:0, done:false};
  if(ZS.own==='me') e.stopImmediatePropagation();
}, {passive:false});
document.addEventListener('gesturechange', function(e){
  e.preventDefault();
  if(!ZS || ZS.k!=='g') return;
  if(ZS.own==='?'){ if(e.scale<.97) ZS.own='me'; else if(e.scale>1.03){ ZS.own='engine'; return; } else return; }
  if(ZS.own==='engine'){
    if(!ZS.f0 || e.scale>=.88) return;                     /* the engine's: pinch in at rest, or a card held */
    e.stopImmediatePropagation();
    if(!ZS.ex){ ZS.ex=performance.now(); if(window.exitFocus) window.exitFocus(); return; }
    if(performance.now()-ZS.ex<UNF || window._focusedNodeId) return;
    ZS.own='me'; ZS.base=1; ZS.sx=e.scale; return;          /* from here the pinch is the board's */
  }
  e.stopImmediatePropagation();
  if(ZS.done) return;
  var s2=ZS.base*e.scale/ZS.sx;
  if(!OV && s2>=1){ if(s2>1.1){ ZS.done=true; enlargeAt(e); } return; }   /* past natural size: enlarge the body under the pinch */
  if(!ovStep(Math.min(1, s2), gpt(e))){ ZS.base=1; ZS.sx=e.scale; }       /* came back to natural size: carry on from here */
}, {passive:false});
document.addEventListener('gestureend', function(e){
  e.preventDefault();
  var z=ZS; ZS=null; if(!z || z.k!=='g') return;
  if(z.own==='me' || z.ex){ e.stopImmediatePropagation(); if(OV && OV.s>=.97) ovLeave(null, true); }
}, {passive:false});
window.addEventListener('keydown', function(e){
  if(!ready || !desk() || (document.activeElement && (document.activeElement.isContentEditable || /^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName)))) return;
  var k=e.key, mod=e.metaKey || e.ctrlKey, hit=false;
  if(mod && k==='-' && !window._focusedNodeId && !document.querySelector('#summary-wrap.open,#detail-page.visible')){ ovZoom((OV ? OV.s : 1)/1.6, null, null, true); hit=true; }
  else if(OV && mod && (k==='=' || k==='+')){ if(OV.s*1.6>=.97) ovLeave(); else ovZoom(OV.s*1.6, null, null, true); hit=true; }
  else if(OV && mod && k==='0'){ ovLeave(); hit=true; }
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
    if(!b || Math.hypot(b.rx-wx, b.ry-wy)>b.d/2+10/OV.s) return;
    ovLeave({x:b.rx, y:b.ry}, false, function(){ if(window.enterFocus) window.enterFocus(id); }); }, true);
  /* nothing under the whole chart is clicked through to */
  ['mousedown', 'click', 'dblclick'].forEach(function(t){ document.addEventListener(t, function(e){ if(OV && mine(e)){ e.preventDefault(); e.stopPropagation(); } }, true); });
  document.addEventListener('scroll', function(e){ var c=cvs(); if(OV && e.target===c && (c.scrollLeft || c.scrollTop)){ c.scrollLeft=0; c.scrollTop=0; } }, true);
  window.addEventListener('resize', function(){ if(OV){ ovHold(true); clampO(OV); ovSet(OV); } });
})();
/* ── the camera: window._altoSolarCam (solar_fly.py and anything else that moves the view) ──
     get()   -> {cx, cy, scale}: the PLAN point (plan.nodes coordinates: x, y without
                WORLD_PAD_TOP) at the middle of the canvas, and the board's scale
                (1 = natural size, < 1 = the whole-chart view). Includes the board pan of
                an enlarged card's fly (window._altoPan).
     set(cx, cy, scale) -> puts that plan point in the middle at that scale, at once, and
                returns get(): scale >= 1 through the canvas's own scroll (the engine's
                whole-px axis, _altoScrollAxis), < 1 through the whole-chart transform
                (translate rounded to device px). scale is kept within [the floor .03, 1];
                the translation is not clamped, so set(get()) changes nothing. An enlarged
                card is let go first (exitFocus; its glide home then runs — let go and wait
                UNF ms yourself before a set() that must be exact).
     onChange(fn) -> fn(get()) after the view moves (scroll, board pan, zoom), at most once
                a frame; returns a function that unsubscribes.
   The whole-chart toggle, pinch and cmd-minus move the same OV state, so get() reads them. */
var camFns=[], camRaf=0;
function camGet(){
  var c=cvs(); if(!c || !world) return null; var cw=c.clientWidth, ch=c.clientHeight;
  if(OV) return {cx:(cw/2-OV.tx)/OV.s, cy:(ch/2-OV.ty)/OV.s-PAD, scale:OV.s};
  var off=woff(c), pn=window._altoPan ? window._altoPan() : {x:0, y:0};
  return {cx:c.scrollLeft+cw/2-off.x-pn.x, cy:c.scrollTop+ch/2-off.y-pn.y-PAD, scale:1};
}
function camTell(){ if(!camFns.length || camRaf) return;
  camRaf=requestAnimationFrame(function(){ camRaf=0; var g=camGet(); camFns.slice().forEach(function(f){ try{ f(g); }catch(e){} }); }); }
window._altoSolarCam={
  get:camGet,
  set:function(cx, cy, scale){
    var c=cvs(); if(!c || !ready || !desk()) return null;
    scale=Math.min(1, Math.max(OVMIN, scale==null ? 1 : +scale));
    if(window._focusedNodeId && window.exitFocus) window.exitFocus();
    var cw=c.clientWidth, ch=c.clientHeight, wx=+cx, wy=+cy+PAD;
    if(scale<.999){
      if(!OV){ var o0=woff(c); OV={s:1, tx:o0.x-c.scrollLeft, ty:o0.y-c.scrollTop}; ovHold(true); c.scrollLeft=0; c.scrollTop=0; c.classList.add('sol-ov'); fitBtn(); }
      cancelAnimationFrame(ovA); OV.s=scale; OV.tx=cw/2-wx*scale; OV.ty=ch/2-wy*scale; ovSet(OV);
    } else {
      if(OV) ovLeave(null, true);
      var off=woff(c), ax=window._altoScrollAxis, sl=wx+off.x-cw/2, st=wy+off.y-ch/2;
      if(ax){ ax('scrollLeft').go(sl); ax('scrollTop').go(st); } else { c.scrollLeft=Math.round(sl); c.scrollTop=Math.round(st); }
      camTell();
    }
    return camGet();
  },
  onChange:function(fn){ camFns.push(fn); return function(){ var i=camFns.indexOf(fn); if(i>=0) camFns.splice(i, 1); }; }
};
window._altoSolarZoom=function(s){ if(s==null) return OV ? OV.s : 1; if(s>=1) ovLeave(null, true); else ovZoom(s, null, null, false); return OV ? OV.s : 1; };
/* ── the two looks and the orbit switch ──────────────────────────────────────
   window._altoSolarLook   = {get() -> 'stars'|'hub', set(look), onChange(fn), plan() -> the plan drawn}
   window._altoSolarMotion = {get() -> the orbit clock runs (switched on, in either look), set(on), onChange(fn)}
   <html> carries .alto-solar-stars or .alto-solar-hub. Both looks draw the SAME plan, so a change
   of look moves nothing: the Star chart's skin and flights come or go (solar_stars.py,
   solar_fly.py, through onChange); an enlarged body, the zoom, the orbit clock, edit mode and
   the viewer's choices carry over. Orbit off: the bodies stop where they are, _altoSolarT
   stops; on again: the clock eases back in over ~400 ms from where it stopped. Both choices are
   kept per timeline per viewer (localStorage alto-solar-look:<id>, alto-solar-motion:<id>; an
   old 'plain' reads as 'hub'). */
var lookFns=[], motFns=[];
function tell(fns, v){ fns.slice().forEach(function(f){ try{ f(v); }catch(e){} }); }
function looks(){ var d=desk(); de.classList.toggle('alto-solar-stars', d && LOOK==='stars'); de.classList.toggle('alto-solar-hub', d && LOOK==='hub'); }   /* desktop only: a phone shows the engine's cards */
function setLook(look){
  look=lk(look); if(!look || look===LOOK) return LOOK;
  LOOK=look; keep('look', look); looks();
  if(ready){ ctl(); apply(true); skin(); }
  tell(lookFns, look); tell(motFns, MOTION && MOVES);
  return LOOK;
}
window._altoSolarLook={get:function(){ return LOOK; }, set:setLook, plan:function(){ return S; },
  onChange:function(fn){ lookFns.push(fn); return function(){ var i=lookFns.indexOf(fn); if(i>=0) lookFns.splice(i, 1); }; }};
window._altoSolarMotion={get:function(){ return !!MOTION && MOVES; },
  set:function(on){ on=!!on; if(on===!!MOTION) return MOTION; MOTION=on; keep('motion', on ? 1 : 0); if(on){ sp=0; RAMP=.4; last=null; } ctl(); tell(motFns, MOTION && MOVES); go(); return MOTION; },
  onChange:function(fn){ motFns.push(fn); return function(){ var i=motFns.indexOf(fn); if(i>=0) motFns.splice(i, 1); }; }};
/* the controls, under the bars at the top left: Hub & spoke | Star chart, and Orbit */
var IC={stars:'<svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><circle cx="10" cy="10" r="4.4" fill="currentColor"/><ellipse cx="10" cy="10" rx="8.6" ry="3" fill="none" stroke="currentColor" stroke-width="1.4" transform="rotate(-22 10 10)"/></svg>',
  hub:'<svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.4"><circle cx="10" cy="10" r="2.6"/><circle cx="10" cy="10" r="5.6" stroke-opacity=".55"/><circle cx="10" cy="10" r="8.4" stroke-opacity=".55"/><circle cx="15.6" cy="10" r="1.6" fill="currentColor"/><circle cx="5" cy="3.6" r="1.4" fill="currentColor"/></svg>',
  pause:'<svg class="sol-ic-pause" viewBox="0 0 20 20" width="14" height="14" aria-hidden="true" fill="currentColor"><rect x="5" y="4" width="3.4" height="12" rx="1"/><rect x="11.6" y="4" width="3.4" height="12" rx="1"/></svg>',
  play:'<svg class="sol-ic-play" viewBox="0 0 20 20" width="14" height="14" aria-hidden="true" fill="currentColor"><path d="M6 4.2v11.6c0 .6.7 1 1.2.6l8.6-5.8c.4-.3.4-1 0-1.2L7.2 3.6C6.7 3.3 6 3.6 6 4.2z"/></svg>'};
function ctl(){
  var w=document.getElementById('sol-ctl');
  if(!desk() || !ready){ if(w) w.remove(); return; }
  if(!w){ w=document.createElement('div'); w.id='sol-ctl'; w.setAttribute('role', 'group'); w.setAttribute('aria-label', 'How the chart looks');
    w.innerHTML='<div class="sol-seg" role="radiogroup" aria-label="Look">'+
      '<button type="button" data-look="hub" role="radio" title="Hub &amp; spoke: the orbits in Alto\'s own look">'+IC.hub+'<span>Hub &amp; spoke</span></button>'+
      '<button type="button" data-look="stars" role="radio" title="Star chart: the same orbits as a space scene, with flights between bodies">'+IC.stars+'<span>Star chart</span></button></div>'+
      '<button type="button" id="sol-motion">'+IC.pause+IC.play+'<span>Orbit</span></button>';
    w.addEventListener('click', function(e){ var b=e.target.closest && e.target.closest('button'); if(!b) return; e.stopPropagation();
      if(b.getAttribute('data-look')) setLook(b.getAttribute('data-look'));
      else if(b.id==='sol-motion' && !b.disabled) window._altoSolarMotion.set(!MOTION); });
    document.body.appendChild(w); }
  [].forEach.call(w.querySelectorAll('[data-look]'), function(b){ var on=b.getAttribute('data-look')===LOOK; b.classList.toggle('on', on); b.setAttribute('aria-checked', on ? 'true' : 'false'); });
  var m=w.querySelector('#sol-motion'), run=!!MOTION && MOVES;
  m.disabled=!MOVES; m.classList.toggle('on', run); m.setAttribute('aria-pressed', run ? 'true' : 'false');
  m.title=!MOVES ? 'Orbit: nothing here orbits' : run ? 'Orbit is on: click to stop the planets where they are' : 'Orbit is off: click to set the planets moving again';
  m.setAttribute('aria-label', m.title);
}
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
function even(n, out){ var off=n%2===0 ? PI/n : 0, o=[]; for(var j=0;j<n;j++) o.push(out+off+2*PI*j/n); return o; }
/* a body's diameter: the sun's fixed, a planet / moon a tier up per two children, a bump one more (solar.body_d) */
function bodyD(role, n, bump, pd, st){ if(role==='sun') return D.sun; if(role==='sat' && st) return C.STATION;
  var L=C.TIERS[role], t=role!=='sat' ? Math.min(Math.ceil(n/2), L.length-2) : 0, d=L[Math.min(t+(bump ? 1 : 0), L.length-1)];
  return role==='moon' && pd ? Math.min(d, Math.floor(C.MOON_MAX*pd)) : d; }
/* the looks' arithmetic (solar.hash01 … orbit_offset): FNV-1a, a comet's ellipse, an asteroid's tumble */
function h01(s){ var h=2166136261; for(var i=0;i<s.length;i++){ h^=s.charCodeAt(i); h=Math.imul(h, 16777619)>>>0; } return h/4294967296; }
function cshape(id){ return [r4(C.ECC[0]+(C.ECC[1]-C.ECC[0])*h01('ecc:'+id)), r4(2*PI*h01('rot:'+id))]; }
function eslack(e){ var q=Math.sqrt(Math.max(0, 1-e*e)); return (1-q)/(1+q); }
function tumble(id){ var v=C.TUMBLE[0]+(C.TUMBLE[1]-C.TUMBLE[0])*h01('tumble:'+id); return r4(h01('spin:'+id)<.5 ? v : -v); }
function kepler(m, e){ var p=m; for(var i=0;i<12;i++) p-=(p-e*Math.sin(p)-m)/(1-e*Math.cos(p)); return p; }
function at(r, a, o){ if(!o) return [r*Math.cos(a), r*Math.sin(a)];
  var c=eslack(o.e), A=r*(1+c), B=r*(1-c), m=a-o.rot, p=o.k ? kepler(m, o.e) : m, x=A*Math.cos(p), y=B*Math.sin(p);
  return [x*Math.cos(o.rot)-y*Math.sin(o.rot), x*Math.sin(o.rot)+y*Math.cos(o.rot)]; }
/* concentric rings, one per body, the first innermost (solar._rings): items [id, reach] round a
   centre of radius inner, each annulus gap past the one inside it; a comet's (slack c) pushed out
   to (edge+gap+reach)/(1-c); its orbit into orb. -> [[ring per item], outer edge] */
function secc(c){ var q=(1-c)/(1+c); return Math.sqrt(Math.max(0, 1-q*q)); }
function rings(items, gap, inner, slack, orb){
  var edge=inner, out=[];
  items.forEach(function(it){ var c=slack[it[0]]||0, r=edge+gap+it[1];
    if(c){ var a=Math.min(c*r/(1-c), C.COMET_PX), e; r+=a; e=r4(secc(a/r)); c=eslack(e); r=(edge+gap+it[1])/(1-c)+.05;
      orb[it[0]]={e:e, rot:cshape(it[0])[1], k:0}; }
    out.push(r); edge=r+c*r+it[1]; });
  return [out, edge];
}
function pbody(pid, moons, size, slack){
  var dp=size(pid, 'planet', moons.length, 0), Rp=dp/2, orb={};
  var ms=moons.map(function(m){ var dm=size(m[0], 'moon', m[1].length, dp), Rm=dm/2, sd={}, srs={};
    m[1].forEach(function(q){ sd[q]=size(q, 'sat', 0, dm); });
    var F=rings(m[1].map(function(q){ return [q, sd[q]/2]; }), C.SAT_GAP, Rm, slack, orb);
    m[1].forEach(function(q, j){ srs[q]=F[0][j]; });
    return {id:m[0], d:dm, sats:m[1], sd:sd, srs:srs, sat_r:F[0].length ? F[0][0] : 0, ext:m[1].length ? F[1] : Rm}; });
  var F=rings(ms.map(function(m){ return [m.id, m.ext]; }), C.MOON_GAP, Rp, slack, orb);
  ms.forEach(function(m, j){ m.r=F[0][j]; });
  return {id:pid, d:dp, moons:ms, moon_r:F[0].length ? F[0][0] : 0, e:Math.max(ms.length ? F[1] : Rp, Rp), orb:orb};
}
function local(b, th, r, orbs){
  orbs=orbs||{};
  var P=at(r, th, orbs[b.id]), px=P[0], py=P[1], cs=[[b.id, px, py, b.d/2, null]], ma=even(b.moons.length, th);
  b.moons.forEach(function(m, k){ var o=at(m.r, ma[k], orbs[m.id]), x=px+o[0], y=py+o[1], sa=even(m.sats.length, ma[k]);
    cs.push([m.id, x, y, m.d/2, b.id]);
    m.sats.forEach(function(si, j){ var o2=at(m.srs[si], sa[j], orbs[si]); cs.push([si, x+o2[0], y+o2[1], m.sd[si]/2, m.id]); }); });
  return cs;
}
function sd(cx, cy, x1, y1, x2, y2){ var dx=x2-x1, dy=y2-y1, L=dx*dx+dy*dy, t=L===0 ? 0 : Math.max(0, Math.min(1, ((cx-x1)*dx+(cy-y1)*dy)/L));
  return Math.hypot(cx-(x1+t*dx), cy-(y1+t*dy)); }
function period(lh, k, n){ return r2(lh[0]+(lh[1]-lh[0])*(n>1 ? k/(n-1) : .5)); }
function system(unit, sun, planets, size, looks){
  var slack={};
  Object.keys(looks).forEach(function(i){ if(looks[i]==='comet') slack[i]=eslack(cshape(i)[0]); });
  var Rs=D.sun/2, bs=planets.map(function(p){ return pbody(p[0], p[1], size, slack); }), P=bs.length, rg=[], ang=[], orbs={}, belt=null;
  bs.forEach(function(b){ Object.keys(b.orb).forEach(function(i){ orbs[i]=b.orb[i]; }); });
  var edge=Rs, split=P>=C.BELT_MIN ? Math.floor(P/2) : -1;
  bs.forEach(function(b, k){
    if(k===split){ belt={r:edge+C.RING_GAP+C.BELT_W/2, w:C.BELT_W}; edge+=C.RING_GAP+C.BELT_W; }
    var c=slack[b.id]||0, r=edge+C.RING_GAP+b.e;
    if(c){ var a=Math.min(c*r/(1-c), C.COMET_PX_PLANET), e=r4(secc(a/(r+a))); c=eslack(e); r=r/(1-c)+.05;
      orbs[b.id]={e:e, rot:cshape(b.id)[1], k:1}; }
    rg.push(r); ang.push(-PI/2+k*GOLD); b.band=[r-c*r-b.e, r+c*r+b.e]; edge=b.band[1]; });
  var outP=[], loc={}; loc[sun]=[0, 0, D.sun, 'sun', ''];
  var md=function(a){ a%=2*PI; if(a<0) a+=2*PI; return Math.round(a*1e7)/1e7; };
  bs.forEach(function(b, k){
    var r=rg[k], th=ang[k], ma=even(b.moons.length, th), nm=b.moons.length;
    local(b, th, r, orbs).forEach(function(c){ loc[c[0]]=[c[1], c[2], Math.round(c[3]*2), c[4]===null ? 'planet' : (c[4]===b.id ? 'moon' : 'sat'), c[4]||sun]; });
    outP.push({id:b.id, ring:k+1, r:r2(r), a0:md(th), d:b.d, period:period(C.P_PLANET, k, P), e:r2(b.e), moon_r:r2(b.moon_r),
      moons:b.moons.map(function(m, i){ var sa=even(m.sats.length, ma[i]), ns=m.sats.length;
        return {id:m.id, r:r2(m.r), a0:md(ma[i]), d:m.d, period:period(C.P_MOON, i, nm), ext:r2(m.ext), sat_r:r2(m.sat_r),
          sats:m.sats.map(function(si, j){ return {id:si, r:r2(m.srs[si]), a0:md(sa[j]), d:m.sd[si], period:period(C.P_SAT, j, ns)}; })}; })});
  });
  var R=bs.length ? bs[bs.length-1].band[1] : Rs;
  return {unit:unit, sun:sun, r_sun:Rs, R:R, box:[-R, -R, R, R], planets:outP, local:loc, orbs:orbs, belt:belt};
}
/* the galactic core (solar._core) and the drifting comets (solar._drifters) */
function core(sys, W, H, bottom){
  if(sys.length<2) return [null, H];
  var need=C.CORE_R+C.CORE_GAP, gx=0, gy=0, best=null, st=Math.max(C.CORE_STEP, Math.ceil(Math.max(W, H)/300));
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
/* t: {kids, parent, seqs, flags?}; old: the plan the page has (sizes, labels, look flags) */
function plan(t, old){
  var K=t.kids||{}, Par=t.parent||{}, seqs=t.seqs||[], ids={};
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
  /* the space stations: the page's own plan's (solar.stations reads the content, which the live tables do not carry) */
  var ST={}; Object.keys((old && old.nodes)||{}).forEach(function(i){ if(old.nodes[i].station && ids[i]) ST[i]=1; });
  var size=function(i, role, n, pd){ return bodyD(role, n, (FL[i]||[]).some(function(f){ return bump.indexOf(f)>=0; }), pd, ST[i]); };
  var looks={};
  Object.keys(ids).forEach(function(i){ var got=(FL[i]||[]).map(function(f){ return LF[f]; }).filter(function(x){ return x; });
    if(got.length) looks[i]=got.sort(function(a, b){ return LOOKS.indexOf(a)-LOOKS.indexOf(b); })[0]; });
  var sy=units.map(function(u){ return system(u[0], u[1], u[2], size, looks); });
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
        if(looks[i]==='asteroid') n.tumble=tumble(i);
        if(ST[i]) n.station=1;
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
  var out={style:'orbit', spin:__SPIN__, world:{w:W, h:H}, sizes:(function(){ var z=JSON.parse(JSON.stringify(D)); z.planet_big=C.TIERS.planet[C.TIERS.planet.length-1]; z.station=C.STATION; z.tiers=JSON.parse(JSON.stringify(C.TIERS)); z.bump=bump.slice().sort(); return z; })(),
    systems:systems, units:uo, nodes:nodes, sun_links:order.slice(1).map(function(b, i){ return [order[i], b]; }), warnings:[],
    looks:lk, look_flags:JSON.parse(JSON.stringify(LF)), belts:belts, drifters:drifters(systems, CO[0], W, H)};
  if(CO[0]) out.core=CO[0];
  return out;
}
window._altoSolarAt=at;          /* where a body is on its orbit (r, angle, orbit {e, rot, k}) — solar_draw places comets with it */
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
