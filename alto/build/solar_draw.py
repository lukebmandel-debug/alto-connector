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
  2π·t/period (solar.py periods, its spin) and, when there are several
  systems, turns each slowly as a whole about its own sun; the bodies are moved by their own left/top (the
  D-GRID margin centring keeps them centred: never a transform, see
  engine_patches 1.8.28), rounded to device px so text stays crisp. Positions
  are offsets from where initLayout put each circle, so a moved card keeps its
  own ring. It stops at once on hover (a card or a line), focus, a search ring,
  dimmed cards, the detail page, edit mode (where it also turns back to t = 0,
  the plan's layout), print, a hidden tab and prefers-reduced-motion, and eases
  back in. The connections are redrawn as straight Alto tubes edge to edge
  between circles, kept on their circles every frame together with their
  data-edge-hit paths and the Blink card mask's holes.
* Arrow keys pick the nearest body that way from where the bodies are now
  (focusing freezes the orbit, so the fly lands where the card is).

The engine hooks (engine_patches.py): solar-layout-hook (end of initLayout),
solar-lines-hook (the router), solar-card-mask-round, and lines added to the
D-GRID script (a circle grows from its centre; content moving under a still
pointer is not a hover) and to focusNeighbor (window._altoSolarNav).
"""
from __future__ import annotations

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
(function(){
var S=window._ALTO_SOLAR; if(!S || !S.nodes) return;
var de=document.documentElement, NS='http://www.w3.org/2000/svg', TAU=Math.PI*2, K=1.7;
var ORBIT=S.style!=='spoke', SPIN=S.spin||-1, DEF={sun:184, planet:108, moon:62, sat:34};
function desk(){ return !de.classList.contains('mobile'); }
if(desk()) de.classList.add('alto-solar');
/* the bodies, each after what it orbits */
var B={}, ORD=[], SY=S.systems||[];
function q(v){ return Math.round(v/2.5)*2.5; }      /* D-GRID: half a diameter on the 1.25px grid */
function body(id, role, p, per, si){
  var n=S.nodes[id]||{}; B[id]={id:id, role:role, p:p, per:ORBIT ? (+per||0) : 0, si:si, d:q(n.d||DEF[role])}; ORD.push(id); }
SY.forEach(function(s, si){ body(s.sun, 'sun', null, 0, si);
  (s.planets||[]).forEach(function(pl){ body(pl.id, 'planet', s.sun, pl.period, si);
    (pl.moons||[]).forEach(function(m){ body(m.id, 'moon', pl.id, m.period, si);
      (m.sats||[]).forEach(function(t){ body(t.id, 'sat', m.id, t.period, si); }); }); }); });
var MOVES=ORBIT && ORD.some(function(i){ return B[i].per>0; });
var world=null, svg=null, PAD=0, zq=1, links=[], spokes=[], rings=[], sunl=[], chips=[], ready=false;
function el(t, a, p){ var e=document.createElementNS(NS, t); for(var k in a) e.setAttribute(k, a[k]); if(p) p.appendChild(e); return e; }
function f2(v){ return Math.round(v*100)/100; }
function rd(v){ return Math.round(v*zq)/zq; }
function unitColor(si){ var pm=(typeof PHASE_META!=='undefined') ? PHASE_META[(SY[si]||{}).unit] : null; return pm ? pm.colorRaw : ''; }
/* the face a resting circle shows: its path number and title */
function face(n, id){
  var c=n.querySelector('.node-card'); if(!c) return;
  var f=c.querySelector('.sol-face'); if(!f){ f=document.createElement('div'); f.className='sol-face'; f.innerHTML='<b></b><span></span>'; c.appendChild(f); }
  var num=(typeof NODE_ORDER_MAP!=='undefined' && NODE_ORDER_MAP[id]) || '', t=c.querySelector('.node-title'), tt=t ? t.textContent : '';
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
   before the lines are drawn. Every body's home is where initLayout put it. */
window._altoSolarLayout=function(pos){
  if(!desk()) return;
  world=document.getElementById('world'); if(!world) return;
  de.classList.add('alto-solar');
  PAD=(typeof WORLD_PAD_TOP!=='undefined') ? WORLD_PAD_TOP : 0;
  zq=(parseFloat(getComputedStyle(de).zoom)||1)*(window.devicePixelRatio||1);
  var G=window._altoTreeGeo, TP=window._ALTO_TREE_PLAN, NM={};
  if(typeof NODES!=='undefined') NODES.forEach(function(n){ NM[n.id]=n; });
  ORD.forEach(function(id){
    var b=B[id], n=document.getElementById('node-'+id), P=S.nodes[id]||{};
    b.n=n; b.c=n ? n.querySelector('.node-card') : null; if(!n) return;
    /* the tree's own x (initLayout's numeral check may have nudged style.left);
       the plan's when the page's tree plan is not the solar one */
    var wired=TP && TP.x && TP.x[id]!=null && Math.abs(TP.x[id]-P.x)<1;
    b.hx=(wired && G && G.x[id]!=null) ? G.x[id] : P.x;
    b.hy=((wired && pos && pos[id]!=null) ? pos[id] : P.y)+PAD;
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
    var pm=(typeof PHASE_META!=='undefined') ? PHASE_META[s.unit] : null, lbl=s.label || (pm ? pm.label : '');
    lbl=String(lbl).split(' — ').pop();
    if(lbl){ var ch=document.createElement('div'); ch.className='sol-unit'; if(u) ch.style.setProperty('--u', u);
      ch.innerHTML='<b></b><span></span>'; ch.querySelector('b').textContent=pm ? pm.numeral : ''; ch.querySelector('span').textContent=lbl;
      world.appendChild(ch);
      var top=Math.max(PAD+24, (s.bbox ? s.bbox[1]+PAD : sun.hy-(s.R||sun.d))-44);
      ch.style.left=Math.round(sun.hx-ch.offsetWidth/2)+'px'; ch.style.top=Math.round(top)+'px'; chips.push(ch); }
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
  if(de.classList.contains('alto-editing') || printing){          /* the plan's own layout, turned back to */
    sp=0; if(T){ back=printing ? 0 : Math.max(0, back-dt/.45); rk=back*back*(3-2*back); apply(); if(back) return go(); T=0; back=rk=1; }
    return sleep(); }
  if(back<1){ T=0; back=rk=1; apply(); }
  if(hold()){ sp=0; return sleep(); }
  sp=Math.min(1, sp+dt/1.2); T+=dt*sp*sp*(3-2*sp); apply(); go();
}
function go(){ clearTimeout(slT); if(!raf && MOVES) raf=requestAnimationFrame(tick); }
function sleep(){ last=null; clearTimeout(slT); slT=setTimeout(go, 180); }
window.addEventListener('beforeprint', function(){ printing=1; if(T){ T=0; rk=1; apply(); } });
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
    var f=n.classList.contains('focused'); if(f===!!n._solF) return; n._solF=f; morph(n, f);
  }); }).observe(w, {attributes:true, subtree:true, attributeFilter:['class']});
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
window._altoSolarGeo=function(){ var o={}; ORD.forEach(function(id){ var b=B[id]; if(b.n) o[id]={x:b.rx, y:b.ry, hx:b.hx, hy:b.hy, d:b.d, role:b.role, p:b.p}; });
  return {T:T, moving:!!raf, bodies:o}; };
})();
"""
