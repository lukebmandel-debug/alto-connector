"""Moving round a System page: Luke's own design (dictated 2026-10-26, after the Nav A card was "obnoxiously large and
placed, and kind of confusing").

One small control in the bottom bar, just right of the Ship picker, in that bar's style: Back (up to the parent),
where you are (a short crumb: a click goes back to it), Next (the next concept at the same level), and the minimap's
switch. Up and parallel are those two buttons; down is the bodies that come up beside an enlarged one (its moons),
bigger than they were and titled, each a click away. With a body enlarged, the arrow keys and a scroll only go round
what is beside it (a planet's three moons: round those three; a body with nothing beside it: round the ones beside
its parent). No arrows are drawn on the page. The minimap (the whole system, you ringed) names the body under the
pointer and goes there on a click. O / Esc: the whole system; ?: the keys.

The minimap (Luke, 2026-10-26, twice) shows only while a body is enlarged (it fades in and out), as big as the free
room allows: it is placed by measuring what is on the screen (the enlarged card, the bodies beside it, the nav row,
Ship, the corner controls) and never covers any of it. It can be dragged anywhere that is free (its place kept per
device, as fractions of the room, and used again while it still fits there). A box on it is what the window
shows, live: drag the box to pan, pull a corner or an edge to zoom. The box is always exactly the view, so a bigger
box shows more of the system (the window zooms out) and a smaller one less (it zooms in, down to the 1x view).

On a phone the control waits in MENU ("Where you are") and opens as a row above the corner controls. Every move goes
through solar_draw.py's own ride / flight (window._altoSolarNavApi); ?nav= and a kept alto-solar-nav are ignored."""

from .solar_draw import _slim

NAVOPT_CSS = r"""
  /* the control: one row in the bottom bar (#sol-ctl, its .sol-seg look in every style) */
  #nvo-a{display:inline-flex;align-items:center;gap:0;padding:2.5px;max-width:min(460px, calc(100vw - 32px));}
  #nvo-a button{font:inherit;color:var(--muted);background:transparent;border:0;border-radius:999px;display:inline-flex;align-items:center;cursor:pointer;height:30px;padding:0;width:30px;justify-content:center;flex:none;}
  #nvo-a button:hover:not(:disabled){color:var(--text);}
  #nvo-a button:disabled{opacity:.35;cursor:default;}
  #nvo-a button.on{color:var(--accent,#6d5bd0);}
  #nvo-a .nv-at{flex:0 1 auto;min-width:0;max-width:300px;padding:0 6px;font-size:12.5px;font-weight:500;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer;line-height:30px;}
  #nvo-a .nv-at b{color:var(--text);font-weight:650;} #nvo-a .nv-at:hover b{text-decoration:underline;text-underline-offset:3px;}
  #nvo-a .nv-at:focus-visible{outline:2px solid var(--accent,#6d5bd0);border-radius:6px;}
  html.alto-stars:not(.sk-retro) #nvo-a .nv-at b{color:#eef2ff;}
  html.sk-retro #nvo-a .nv-at{color:rgba(239,230,207,.6);font-family:var(--rt-f, inherit);} html.sk-retro #nvo-a .nv-at b{color:#efe6cf;}
  html.sk-retro #nvo-a button{border-radius:0 !important;color:#d9ae55;} html.sk-retro #nvo-a button.on{background:#d9ae55 !important;color:#000 !important;}
  /* the minimap: the whole system above the control, you ringed */
  .nvo{position:fixed;z-index:305;color:var(--text);background:var(--card-glass-bg, var(--surface));-webkit-backdrop-filter:blur(18px) saturate(180%);backdrop-filter:blur(18px) saturate(180%);
    border:1px solid var(--card-glass-border, var(--border));box-shadow:0 10px 26px var(--node-rest-shadow, rgba(20,24,60,.18));border-radius:12px;box-sizing:border-box;font-size:13px;}
  #nvo-map{right:16px;bottom:70px;padding:6px;cursor:grab;user-select:none;-webkit-user-select:none;touch-action:none;opacity:0;visibility:hidden;pointer-events:none;transition:opacity .28s ease,visibility 0s .28s;}
  #nvo-map.on{opacity:1;visibility:visible;pointer-events:auto;transition:opacity .28s ease;} #nvo-map.dr{cursor:grabbing;}
  #nvo-map svg{display:block;height:104px;width:auto;touch-action:manipulation;}
  #nvo-map circle.hr.hr{fill:none !important;stroke:var(--accent,#6d5bd0) !important;stroke-width:2px;vector-effect:non-scaling-stroke;pointer-events:none;}
  html.alto-stars:not(.sk-retro) #nvo-map circle.hr.hr{stroke:#fff !important;} html.sk-retro #nvo-map circle.hr.hr{stroke:#efe6cf !important;}
  #nvo-map .vb{fill:var(--accent,#6d5bd0);fill-opacity:.1;stroke:var(--accent,#6d5bd0);stroke-width:1.5px;vector-effect:non-scaling-stroke;}
  #nvo-map .vh{fill:var(--surface,#fff);stroke:var(--accent,#6d5bd0);stroke-width:1.2px;vector-effect:non-scaling-stroke;}
  html.alto-stars:not(.sk-retro) #nvo-map .vb{fill:#9fc0ff;stroke:#bcd2ff;} html.alto-stars:not(.sk-retro) #nvo-map .vh{fill:#0b1430;stroke:#bcd2ff;}
  html.sk-retro #nvo-map .vb{fill:#d9ae55;fill-opacity:.08;stroke:#d9ae55;} html.sk-retro #nvo-map .vh{fill:#000;stroke:#d9ae55;}
  html.phone-whole #nvo-map :is(.vb,.vh){display:none;}
  #nvo-map circle{fill:var(--muted);fill-opacity:.6;} #nvo-map circle.s{fill:#f0b542;fill-opacity:1;}
  #nvo-map circle.h{fill:var(--accent,#6d5bd0);fill-opacity:1;stroke:var(--text);stroke-width:2px;vector-effect:non-scaling-stroke;}
  #nvo-map circle.o{fill:var(--text);fill-opacity:1;}
  #nvo-map line{stroke:var(--text);stroke-opacity:.2;stroke-width:1px;vector-effect:non-scaling-stroke;}
  #nvo-tip{position:fixed;z-index:340;display:none;pointer-events:none;}
  html.alto-stars:not(.sk-retro) .nvo{background:rgba(6,10,26,.72);border-color:rgba(170,198,255,.18);box-shadow:0 10px 30px rgba(0,0,0,.35);}
  html.alto-stars:not(.sk-retro) #nvo-map :is(circle:not(.s):not(.h):not(.o),line){fill:#cfd8ff;stroke:#cfd8ff;}
  html.alto-stars:not(.sk-retro) #nvo-map circle.o{fill:#fff;}
  html.sk-retro .nvo{background:rgba(3,4,7,.94);color:#efe6cf;border-radius:0;border-color:rgba(217,174,85,.55);box-shadow:none;-webkit-backdrop-filter:none;backdrop-filter:none;font-family:var(--rt-f, inherit);}
  html.sk-retro #nvo-map :is(circle:not(.s):not(.h):not(.o),line){fill:#efe6cf;stroke:#d9ae55;} html.sk-retro #nvo-map circle.h{fill:#d9ae55;stroke:#efe6cf;}
  #nvo-help{right:58px;top:84px;width:min(330px, calc(100vw - 24px));padding:12px 14px;line-height:1.45;}
  #nvo-help kbd{font:inherit;font-weight:700;border:1px solid var(--border);border-radius:5px;padding:0 5px;}
  /* the bodies beside an enlarged one: bigger, titled, a click away; nothing else named on the map, no arrows */
  html.navx :is(.sol-nh,#sol-way,#sol-here,#sol-tour){display:none !important;}
  html.navx.alto-solar:not(.mobile):not(.sk-3d) #world .node.sol-flank .node-card{transform:scale(var(--fk));transform-origin:50% 50%;transition:transform .25s cubic-bezier(.2,.7,.2,1);}
  html.navx #world .node.sol-flank{--fk:min(2.6, max(1, calc(54 / var(--dn,20))));--ovs:var(--fk);cursor:pointer;}
  html.navx.alto-solar:not(.mobile):not(.sk-3d) #world .node.sol-flank>.sol-lbl{opacity:1 !important;visibility:visible !important;font-size:13px;line-height:16px;font-weight:600;white-space:normal;width:max-content;max-width:170px;text-align:center;pointer-events:auto;cursor:pointer;}
  html.navx.alto-solar:not(.mobile):not(.sk-3d) #world .node.sol-flank:hover>.sol-lbl{text-decoration:underline;text-underline-offset:3px;}
  html.navx #world .node.sol-flank.nv-pick .node-card{box-shadow:0 0 0 3px var(--accent,#6d5bd0) !important;}
  html.navx #sk3d-l i{pointer-events:auto;cursor:pointer;font-size:13px;} html.navx #sk3d-l i :is(kbd,em){display:none;}
  #nvo-where{display:none !important;}                                   /* (MENU's way in, on a phone only) */
  /* a phone seen whole: the control and the map wait in MENU, then sit above the corner controls */
  html.phone-whole :is(#nvo-a,#nvo-map){display:none;} html.phone-whole #nvo-map.fit{display:block;}
  html.phone-whole.nvo-open #nvo-a{display:flex;position:fixed;z-index:330;left:8px;right:8px;max-width:none;height:44px;bottom:calc(68px + env(safe-area-inset-bottom,0px));box-sizing:border-box;border-radius:22px;
    background:var(--card-glass-bg, var(--surface));-webkit-backdrop-filter:blur(18px) saturate(190%);backdrop-filter:blur(18px) saturate(190%);border:1px solid var(--card-glass-border, var(--border));}
  html.phone-whole.nvo-open #nvo-a button{width:44px;height:38px;} html.phone-whole.nvo-open #nvo-a .nv-at{flex:1 1 auto;max-width:none;text-align:center;font-size:13.5px;}
  html.phone-whole.nvo-open.alto-stars:not(.sk-retro) #nvo-a{background:rgba(6,10,26,.8);border-color:rgba(170,198,255,.18);color:#eef2ff;}
  html.phone-whole.nvo-open.sk-retro #nvo-a{background:#000;border-radius:0;border-color:rgba(217,174,85,.55);}
  html.phone-whole.nvo-open.nvo-map #nvo-map{display:block;left:auto;right:8px;bottom:calc(120px + env(safe-area-inset-bottom,0px));}
  html.mobile:not(.phone-whole) :is(#nvo-a,.nvo),html.alto-editing :is(#nvo-a,.nvo){display:none !important;}   /* (phone.py copies html.mobile rules to phone-whole) */
  @media print{ #nvo-a,.nvo{display:none !important;} }
"""

NAVOPT_JS = r"""
(function(){
if(!window._altoSolarNavApi) return;
var A=window._altoSolarNavApi, de=document.documentElement;
var KEYS=[['Back', 'up to the one it belongs to'], ['Next', 'the next one at the same level'], ['Left / Right arrows, or scroll', 'round the ones beside the enlarged one'], ['1 – 9', 'that one beside it'], ['O or Esc', 'see the whole system']];
function mk(t, id, cls, h){ var e=document.createElement(t); if(id) e.id=id; if(cls) e.className=cls; if(h!=null) e.innerHTML=h; return e; }
function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;'}[c]; }); }
function nm(id){ return esc(A.name(id)); }
function sv(d){ return '<svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'+d+'</svg>'; }   /* (Alto's glyph style: format_symbols.py) */
function phone(){ return de.classList.contains('phone-whole'); }
function sheet(on){ de.classList.toggle('nvo-open', !!on); }
function go(id){ if(!id) return; if(A.ov() && id===A.home()) A.step('ov'); else A.go(id); }
function live(){ return A.ok() && !document.querySelector('#detail-page.visible'); }
function lsGet(k){ try{ return localStorage.getItem(k); }catch(e){ return null; } }
function lsSet(k, v){ try{ localStorage.setItem(k, v); }catch(e){} }
var MAP=lsGet('alto-solar-map')!=='0';
/* the moves: Back (up), Next (the next at this level), and the scope the arrows and a scroll go round */
function up(h){ return A.up(h) || ''; }                                   /* ('' the whole system) */
function next(h){ var L=window._altoSolarLevelNav, s=A.sibs(h), i=s.indexOf(h), to=s[i+1] || (L ? L(h, 'e') : null); return to && to!==h ? to : null; }
function scope(h){ var k=A.kids(h); return k.length ? k : A.sibs(h); }  /* what is beside it, else what is beside its parent */
function round(h, d){ var s=scope(h), i=s.indexOf(h); if(!s.length || (s.length===1 && i===0)) return null; return i<0 ? s[d>0 ? 0 : s.length-1] : s[(i+d+s.length)%s.length]; }
var W=null, K='';
function draw(h){
  if(!W){ W=mk('div', 'nvo-a', 'sol-seg', '<button type="button" data-n="up">'+sv('<path d="M8 4.5 4 8.5l4 4"/><path d="M4 8.5h7a5 5 0 0 1 5 5v2"/>')+'</button>'+
      '<span class="nv-at" role="button" tabindex="0"></span>'+
      '<button type="button" data-n="next">'+sv('<path d="M8 4.5 13.5 10 8 15.5"/>')+'</button>'+
      '<button type="button" data-n="map">'+sv('<rect x="3" y="4.5" width="14" height="11" rx="2"/><circle cx="7.5" cy="9" r="1.2"/><circle cx="12.5" cy="11.5" r="1.2"/><path d="M8.5 9.6 11.5 11"/>')+'</button>');
    W.setAttribute('role', 'navigation'); W.setAttribute('aria-label', 'Where you are'); }
  var ov=A.ov(), u=up(h), n=next(h), p=A.up(h), b=W.querySelector('[data-n=up]'), x=W.querySelector('[data-n=next]'), m=W.querySelector('[data-n=map]'), at=W.querySelector('.nv-at');
  function lab(e, t){ e.title=t; e.setAttribute('aria-label', t); }
  b.disabled=ov; b.setAttribute('data-go', u); lab(b, ov ? 'Back' : 'Back to '+(u ? A.name(u) : 'the whole system'));
  x.disabled=!ov && !n; x.setAttribute('data-go', ov ? h : n || ''); lab(x, ov ? 'Back to '+A.name(h) : n ? 'Next: '+A.name(n) : 'Nothing after this one');
  m.classList.toggle('on', MAP); m.setAttribute('aria-pressed', MAP ? 'true' : 'false'); lab(m, MAP ? 'Hide the minimap' : 'Show the minimap');
  at.setAttribute('data-go', h); at.innerHTML=ov ? '<b>Whole system</b>' : (p ? nm(p)+' › ' : '')+'<b>'+nm(h)+'</b>';
  lab(at, ov ? 'The whole system: back to '+A.name(h) : 'You are at '+A.name(h)+(p ? ', in '+A.name(p) : ''));
  return W; }
/* ── the minimap ── */
var MP=null, TIP=null;
function mapSvg(){ var g=A.geo(), ids=Object.keys(g), x0=1/0, y0=1/0, x1=-1/0, y1=-1/0;
  ids.forEach(function(i){ var b=g[i], r=b.d/2; x0=Math.min(x0, b.x-r); y0=Math.min(y0, b.y-r); x1=Math.max(x1, b.x+r); y1=Math.max(y1, b.y+r); });
  if(!ids.length) return ''; var p=(x1-x0)*.04, m=(x1-x0)/70, s='<svg viewBox="'+[x0-p, y0-p, x1-x0+2*p, y1-y0+2*p].map(function(v){ return v.toFixed(0); }).join(' ')+'" role="img" aria-label="The whole system: point at a body for its name, click to go there">';
  ids.forEach(function(i){ var b=g[i]; if(b.p && g[b.p]) s+='<line x1="'+g[b.p].x.toFixed(0)+'" y1="'+g[b.p].y.toFixed(0)+'" x2="'+b.x.toFixed(0)+'" y2="'+b.y.toFixed(0)+'"/>'; });
  ids.forEach(function(i){ var b=g[i]; s+='<circle data-b="'+esc(i)+'" class="'+(b.role==='sun' ? 's' : '')+'" cx="'+b.x.toFixed(0)+'" cy="'+b.y.toFixed(0)+'" r="'+Math.max(b.d/2, m).toFixed(0)+'"/>'; });
  MG={m:m, a:(x1-x0+2*p)/Math.max(1, y1-y0+2*p), b:ids.map(function(i){ var b=g[i]; return [i, b.x, b.y, Math.max(b.d/2, m)]; })};
  return s+'</svg>'; }
/* the body nearest the point (a wide, clear target: within three dots of it) */
var MG=null;
function near(x, y){ var sv=MP && MP.querySelector('svg'), M=sv && sv.getScreenCTM && sv.getScreenCTM(); if(!M || !MG) return null;
  var p=sv.createSVGPoint(); p.x=x; p.y=y; p=p.matrixTransform(M.inverse()); var best=null, bd=1/0;
  MG.b.forEach(function(b){ var d=Math.hypot(b[1]-p.x, b[2]-p.y)-b[3]; if(d<bd){ bd=d; best=b[0]; } }); return bd<=MG.m*3 ? best : null; }
function tip(id, x, y){ if(!TIP){ TIP=mk('div', 'nvo-tip', 'line-tip'); document.body.appendChild(TIP); }
  var mp=MP && MP.querySelector('circle.o'); if(mp) mp.classList.remove('o');
  if(!id){ TIP.style.display='none'; return; } var c=MP && MP.querySelector('circle[data-b="'+(window.CSS && CSS.escape ? CSS.escape(id) : id)+'"]'); if(c && !c.classList.contains('h')) c.classList.add('o');
  TIP.textContent=A.name(id)+(id===A.home() ? ' · you are here' : ''); TIP.style.display='block';
  var z=parseFloat(getComputedStyle(de).zoom)||1, w=TIP.offsetWidth; x/=z; y/=z; TIP.style.left=Math.max(6, Math.min(innerWidth/z-w-6, x-w/2))+'px'; TIP.style.top=Math.max(6, y-34)+'px'; }   /* (a zoomed page: fixed px are its own) */
function mapDraw(h){
  if(!MP){ MP=mk('div', 'nvo-map', 'nvo'); MP.setAttribute('role', 'group'); MP.setAttribute('aria-label', 'Minimap');
    MP.addEventListener('pointermove', function(e){ if(DG) return; var E=edges(e.clientX, e.clientY); if(E && E.any){ tip(null); MP.style.cursor=cur(E); return; } var t=near(e.clientX, e.clientY); tip(t, e.clientX, e.clientY); MP.style.cursor=t ? 'pointer' : E && E.in ? 'move' : ''; });
    MP.addEventListener('pointerleave', function(){ if(!DG) tip(null); });
    MP.addEventListener('pointerdown', grab); }
  MP.innerHTML=mapSvg().replace('</svg>', '<rect class="vb"/>'+'<rect class="vh"/>'.repeat(4)+'</svg>'); var me=MP.querySelector('circle[data-b="'+(window.CSS && CSS.escape ? CSS.escape(h) : h)+'"]'); if(me){ me.classList.add('h');   /* (you: ringed as well, to be found at a glance) */
    var hr=document.createElementNS('http://www.w3.org/2000/svg', 'circle'); hr.setAttribute('class', 'hr'); ['cx', 'cy'].forEach(function(a){ hr.setAttribute(a, me.getAttribute(a)); });
    hr.setAttribute('r', Math.max(+me.getAttribute('r')*1.9, MG.m*3.2).toFixed(0)); me.parentNode.insertBefore(hr, me.nextSibling); }
  SZ=0; return MP; }
/* ── where you are looking: the box (the window's view, in the map's own units: world px) ── */
var HOLD=0, CAM=window._altoSolarCam, PY=(typeof WORLD_PAD_TOP!=='undefined') ? WORLD_PAD_TOP : 0, DG=null, SUP=0, MIN=.03;
function cnv(){ return document.getElementById('canvas'); }
function zm(){ return parseFloat(getComputedStyle(de).zoom)||1; }
function vbox(){ var g=CAM && CAM.get(), c=cnv(); if(!g || !c || !c.clientWidth) return null; var w=c.clientWidth/g.scale, h=c.clientHeight/g.scale;
  return {x:g.cx-w/2, y:g.cy+PY-h/2, w:w, h:h, s:g.scale, cw:c.clientWidth, ch:c.clientHeight}; }
function vbDraw(){ var sv=MP && MP.isConnected && MP.querySelector('svg'), r=sv && sv.querySelector('.vb'); if(!r) return; var b=vbox(), M=sv.getScreenCTM();
  if(!b || !M || phone()){ r.style.display='none'; r._k=''; return; }
  var V=sv.viewBox.baseVal, x0=Math.max(b.x, V.x), y0=Math.max(b.y, V.y), x1=Math.min(b.x+b.w, V.x+V.width), y1=Math.min(b.y+b.h, V.y+V.height);   /* (the part of the system in view) */
  if(x1<=x0 || y1<=y0){ r.style.display='none'; r._k=''; [].forEach.call(sv.querySelectorAll('.vh'), function(q){ q.setAttribute('width', 0); }); return; } b={x:x0, y:y0, w:x1-x0, h:y1-y0};
  var k=8/M.a, a=[b.x, b.y, b.w, b.h, k].map(function(v){ return +v.toFixed(1); }), key=a.join(); if(r._k===key) return; r._k=key; r.style.display='';
  r.setAttribute('x', a[0]); r.setAttribute('y', a[1]); r.setAttribute('width', a[2]); r.setAttribute('height', a[3]);
  [].forEach.call(sv.querySelectorAll('.vh'), function(q, i){ q.setAttribute('x', ((i&1 ? b.x+b.w : b.x)-k/2).toFixed(1)); q.setAttribute('y', ((i&2 ? b.y+b.h : b.y)-k/2).toFixed(1)); q.setAttribute('width', a[4]); q.setAttribute('height', a[4]); }); }
function svPt(x, y){ var sv=MP.querySelector('svg'), M=sv && sv.getScreenCTM(); if(!M) return null; var p=sv.createSVGPoint(); p.x=x; p.y=y; return p.matrixTransform(M.inverse()); }
/* the box's edges under the pointer (6 px either side of them), or inside it */
function edges(x, y){ var r=MP && MP.querySelector('.vb'); if(!r || r.style.display==='none' || phone()) return null; var q=r.getBoundingClientRect(), t=6;
  if(x<q.left-t || x>q.right+t || y<q.top-t || y>q.bottom+t) return null;
  var l=x-q.left, rr=q.right-x, tp=y-q.top, bt=q.bottom-y, E={l:Math.abs(l)<=t && Math.abs(l)<=Math.abs(rr), r:Math.abs(rr)<=t && Math.abs(rr)<Math.abs(l), t:Math.abs(tp)<=t && Math.abs(tp)<=Math.abs(bt), b:Math.abs(bt)<=t && Math.abs(bt)<Math.abs(tp)};
  E.any=E.l || E.r || E.t || E.b; E.in=l>0 && rr>0 && tp>0 && bt>0; return E; }
function cur(E){ return (E.l && E.t) || (E.r && E.b) ? 'nwse-resize' : (E.r && E.t) || (E.l && E.b) ? 'nesw-resize' : E.l || E.r ? 'ew-resize' : 'ns-resize'; }
/* a press: on an edge pulls it (zoom), in the box drags it (pan), elsewhere drags the map; a press that does not move is a click (go there) */
function grab(e){ if(phone() || e.button || !MP) return; var E=edges(e.clientX, e.clientY);
  DG={x:e.clientX, y:e.clientY, m:E && E.any ? 'rs' : E && E.in ? 'pan' : 'mv', E:E, p:svPt(e.clientX, e.clientY), b:vbox(), r:MP.getBoundingClientRect(), on:0, id:e.pointerId}; }
function drag(e){ if(!DG) return; e.stopPropagation(); var dx=e.clientX-DG.x, dy=e.clientY-DG.y;
  if(!DG.on){ if(Math.abs(dx)+Math.abs(dy)<4) return; DG.on=1; tip(null); MP.classList.add('dr'); try{ MP.setPointerCapture(DG.id); }catch(_){} }
  var b=DG.b, p=svPt(e.clientX, e.clientY);
  if(DG.m==='mv'){ var z=zm(), w=MP.offsetWidth, h=MP.offsetHeight, W=innerWidth/z, H=innerHeight/z;
    POS={x:Math.max(0, Math.min(1, ((DG.r.left+dx)/z)/Math.max(1, W-w))), y:Math.max(0, Math.min(1, ((DG.r.top+dy)/z)/Math.max(1, H-h)))}; dragTo(); return; }
  if(!b || !p || !DG.p || !CAM) return; HOLD=1;   /* (a pan or zoom from the box lets the body go: the map stays till you are done with it) */
  if(DG.m==='pan'){ CAM.set(b.x+b.w/2+p.x-DG.p.x, b.y+b.h/2-PY+p.y-DG.p.y, b.s); vbDraw(); return; }
  var E=DG.E, ex=p.x-DG.p.x, ey=p.y-DG.p.y, x0=b.x+(E.l ? ex : 0), x1=b.x+b.w+(E.r ? ex : 0), y0=b.y+(E.t ? ey : 0), y1=b.y+b.h+(E.b ? ey : 0), W2=Math.abs(x1-x0), H2=Math.abs(y1-y0);
  var s=(E.l || E.r) && (E.t || E.b) ? Math.min(b.cw/W2, b.ch/H2) : E.l || E.r ? b.cw/W2 : b.ch/H2;   /* (a corner: the bigger of the two pulls) */
  s=Math.max(MIN, Math.min(1, s || 1)); var w=b.cw/s, h=b.ch/s;
  var cx=E.l ? b.x+b.w-w/2 : E.r ? b.x+w/2 : b.x+b.w/2, cy=E.t ? b.y+b.h-h/2 : E.b ? b.y+h/2 : b.y+b.h/2;   /* (the far side stays put) */
  CAM.set(cx, cy-PY, s); vbDraw(); }
function drop(){ if(!DG) return; var on=DG.on, mv=DG.m==='mv'; DG=null; MP && MP.classList.remove('dr'); if(!on) return;
  SUP=performance.now(); if(mv){ SK=''; SP=null; } if(mv) lsSet('alto-solar-map-at', JSON.stringify({x:+POS.x.toFixed(4), y:+POS.y.toFixed(4)})); }
/* its place: the biggest that fits in the free room, first where you last put it, else down the right side then the
   left, from the bottom; never over the enlarged card, what is beside it, the nav row, Ship or the corner controls */
var POS=(function(){ try{ var p=JSON.parse(lsGet('alto-solar-map-at')||'null'); return p && isFinite(p.x) && isFinite(p.y) ? p : null; }catch(e){ return null; } })();
var SZ=0, SP=null, SK='', SIZES=[300, 264, 232, 204, 180, 158, 138, 120, 104];
function obst(){ var W=innerWidth, H=innerHeight, o=[];
  function add(e, g){ var r=e && e.getBoundingClientRect(); if(!r || r.width<1 || r.height<1 || r.bottom<0 || r.top>H || r.right<0 || r.left>W) return; var cs=getComputedStyle(e);
    if(cs.visibility==='hidden' || cs.display==='none' || +cs.opacity<.05) return; o.push([r.left-g, r.top-g, r.right+g, r.bottom+g]); }
  [].forEach.call(document.querySelectorAll('body>*,#app>*'), function(e){ if(e===MP || e===TIP || e===HP || e.id==='canvas' || getComputedStyle(e).position!=='fixed') return;
    var r=e.getBoundingClientRect(); if(!(r.width>W*.6 && r.height>H*.6)) add(e, 8); });
  [].forEach.call(document.querySelectorAll('#nvo-a,#sol-ctl,#sol-craft'), function(e){ add(e, 8); });
  [].forEach.call(document.querySelectorAll('#world .node.focused .node-card,#world .node.sol-flank .node-card,#world .node.sol-flank>.sol-lbl,#sk3d-l i'), function(e){ add(e, 14); });
  var c=window._altoSolar3dFocus && window._altoSolar3dFocus(); if(c) o.push([c[0]-14, c[1]-14, c[2]+14, c[3]+14]);   /* (3D: the enlarged globe) */
  return o; }
function free(q, O){ if(q[0]<4 || q[1]<4 || q[2]>innerWidth-4 || q[3]>innerHeight-4) return false;
  for(var i=0;i<O.length;i++){ var b=O[i]; if(q[0]<b[2] && b[0]<q[2] && q[1]<b[3] && b[1]<q[3]) return false; } return true; }
function dims(h){ var a=(MG && MG.a) || 1.5, w=h*a; if(w>h*1.9){ w=h*1.9; h=w/a; } return [w, h]; }   /* (the map's own px: its svg) */
function spot(){ if(!MG) return null; var z=zm(), W=innerWidth, H=innerHeight, O=obst(), m=12*z, mw=phone() ? W*.45 : 0, i, d, bw, bh, x, y;   /* (a phone: legible or not at all, MENU has it) */
  function box(x, y){ return [x, y, x+bw, y+bh]; }
  function sz(h){ d=dims(h); bw=(d[0]+14)*z; bh=(d[1]+14)*z; }
  if(POS) for(i=0;i<SIZES.length;i++){ sz(SIZES[i]); if(bw<mw) break; x=POS.x*(W-bw); y=POS.y*(H-bh); if(free(box(x, y), O)) return [x/z, y/z, d]; }
  for(i=0;i<SIZES.length;i++){ sz(SIZES[i]); if(bw<mw) break;
    for(var c=0;c<2;c++){ x=c ? m : W-m-bw; for(y=H-m-bh; y>=m; y-=10*z) if(free(box(x, y), O)) return [x/z, y/z, d]; } }
  return null; }
function size(d){ var sv=MP && MP.querySelector('svg'); if(!sv || SZ===d[1]) return; SZ=d[1]; sv.style.width=d[0].toFixed(0)+'px'; sv.style.height=d[1].toFixed(0)+'px'; var r=MP.querySelector('.vb'); if(r) r._k=''; }
function put(x, y){ var st=MP.style, l=Math.round(x)+'px', t=Math.round(y)+'px'; if(st.left!==l) st.left=l; if(st.top!==t) st.top=t; if(st.right!=='auto'){ st.right='auto'; st.bottom='auto'; } }
/* placed once per enlarged body (and window, style), checked again every tick: moved only when something comes over it */
function place(key){ if(!MP || !MP.isConnected) return false;
  if(SP && SK===key){ var r=MP.getBoundingClientRect(); if(r.width && free([r.left, r.top, r.right, r.bottom], obst())) return true; }
  SK=key; SP=spot(); if(!SP) return false; size(SP[2]); put(SP[0], SP[1]); return true; }
function dragTo(){ var z=zm(), W=innerWidth/z, H=innerHeight/z, w=MP.offsetWidth, h=MP.offsetHeight;
  put(Math.max(4, Math.min(W-w-4, POS.x*(W-w))), Math.max(4, Math.min(H-h-4, POS.y*(H-h)))); }
var HP=null;
function help(on){ if(HP){ HP.remove(); HP=null; } if(!on) return;
  HP=mk('div', 'nvo-help', 'nvo', '<b>How to move</b><br>'+KEYS.map(function(k){ return '<kbd>'+k[0]+'</kbd> '+k[1]; }).join('<br>'));
  HP.setAttribute('role', 'dialog'); HP.setAttribute('aria-label', 'How to move'); document.body.appendChild(HP); }
/* the phone's way in: a button in the System's controls, which MENU lists under View (phone_minimal.py) */
function where(){ var c=document.getElementById('sol-ctl'); if(!c || document.getElementById('nvo-where')) return;
  var b=mk('button', 'nvo-where', 'sol-opt', '<span>Where you are</span>'); b.type='button'; b.title='Where you are: back, next and the minimap';
  b.addEventListener('click', function(e){ e.stopPropagation(); sheet(!de.classList.contains('nvo-open')); }); c.appendChild(b); }
/* ── keeping it current: what is drawn follows where you are ── */
function tick(force){
  where(); var c=document.getElementById('sol-ctl'), cr=document.getElementById('sol-craft');
  de.classList.toggle('navx', A.ok()); de.classList.toggle('nvo-map', MAP);
  if(!live()){ if(W){ W.remove(); W=null; } if(MP){ MP.remove(); MP=null; } tip(null); K=''; sheet(false); return; }
  var h=A.home(); if(!h) return; var k=h+'|'+A.ov()+'|'+A.order().length+'|'+MAP; if(k!==K || force){ K=k; draw(h); if(MAP && !A.ov()) mapDraw(h); }
  if(phone()){ if(W.parentNode!==document.body) document.body.appendChild(W); }
  else if(c){ var at=cr && cr.parentNode===c ? cr : null; if(at ? W.previousElementSibling!==at : W.parentNode!==c) at ? at.after(W) : c.appendChild(W); }   /* (just right of Ship) */
  if(!MAP){ if(MP && MP.isConnected) MP.remove(); tip(null); return; }
  if(A.ov()){ HOLD=0; if(MP) MP.classList.remove('on', 'fit'); tip(null); return; }   /* (the whole system: it fades out) */
  if(!MP) mapDraw(h); if(!MP.isConnected) document.body.appendChild(MP);
  /* shown only while a body is enlarged (kept through the ride to the next one; placed again on landing) */
  var en=enl(); if(en) HOLD=0; var was=MP.classList.contains('on'), sh=phone() && de.classList.contains('nvo-open'), fit=false;
  if(sh){ if(MP.style.left){ var st=MP.style; st.left=st.top=st.right=st.bottom=''; } size(dims(104)); SK=''; SP=null; }
  else if(DG) fit=true;
  else if(HOLD && !en) fit=!!SP;
  else if(en && !busy()) fit=place([en, innerWidth, innerHeight, de.className].join('|'));
  else fit=was && (!!en || busy()) && !!SP;
  MP.classList.toggle('fit', fit && phone()); MP.classList.toggle('on', sh || fit);
  if(!(sh || fit)) tip(null); vbDraw();
}
setInterval(function(){ tick(); later(); }, 250); tick(true);
/* the box follows every pan and zoom: redrawn on the camera's own news and a scroll, one frame each, nothing at rest */
var VQ=0; function vbSoon(){ if(VQ || !MP || !MP.isConnected) return; VQ=requestAnimationFrame(function(){ VQ=0; vbDraw(); }); }
if(CAM && CAM.onChange) CAM.onChange(vbSoon); document.addEventListener('scroll', vbSoon, {capture:true, passive:true});
addEventListener('resize', function(){ SK=''; });
addEventListener('pointerdown', function(e){ if(HOLD && !(MP && MP.contains(e.target))) HOLD=0; }, true);
addEventListener('pointermove', drag, true); ['pointerup', 'pointercancel'].forEach(function(t){ addEventListener(t, drop, true); });   /* (a drag goes on outside the map) */
function act(b){ var n=b.getAttribute('data-n');
  if(n==='map'){ MAP=!MAP; lsSet('alto-solar-map', MAP ? '1' : '0'); tick(true); return; }
  var id=b.getAttribute('data-go'); if(b.disabled) return;
  if(id) go(id); else A.step('ov'); setTimeout(function(){ tick(true); }, 30); }
/* a finger acts on touchend (as the phone's own controls do: its touch layer keeps a tap's click from coming) */
var T0=null, HIT='#nvo-a [data-n],#nvo-a .nv-at,#nvo-map,#sk3d-l [data-go]';
document.addEventListener('touchstart', function(e){ var t=e.touches[0]; T0=t && e.target.closest && e.target.closest(HIT) ? [t.clientX, t.clientY] : null; }, {capture:true, passive:true});
document.addEventListener('touchend', function(e){ var b=T0 && e.target.closest && e.target.closest(HIT), t=e.changedTouches && e.changedTouches[0];
  if(!b || (t && Math.abs(t.clientX-T0[0])+Math.abs(t.clientY-T0[1])>12)){ T0=null; return; } T0=null; e.preventDefault(); e.stopPropagation(); hit(b, t); }, {capture:true, passive:false});
function hit(b, t, e){ var q=t || e, mp=b.closest('#nvo-map'), id=mp ? (q && near(q.clientX, q.clientY)) : b.closest('#sk3d-l') && b.getAttribute('data-go');
  if(mp){ if(performance.now()-SUP<400) return; if(id && t){ tip(id, t.clientX, t.clientY); setTimeout(function(){ tip(null); }, 900); } if(id) go(id); return; }
  if(id){ go(id); return; } act(b); }
document.addEventListener('click', function(e){ var t=e.target, b=t.closest && t.closest(HIT);
  if(b){ e.preventDefault(); e.stopPropagation(); hit(b, null, e); return; }
  if(HP && !(t.closest && t.closest('#nvo-help'))) help(false);
  if(phone() && de.classList.contains('nvo-open') && !(t.closest && t.closest('#nvo-a,#nvo-map,#nvo-where,#hamburger-tab,#nav-drawer'))) sheet(false);
}, true);
document.addEventListener('keydown', function(e){ var t=e.target; if((e.key==='Enter' || e.key===' ') && t && t.classList && t.classList.contains('nv-at')){ e.preventDefault(); e.stopPropagation(); act(t); } }, true);
/* the keys: with a body enlarged, the arrows go round what is beside it (no arrow takes you up or along: Back and Next do) */
function enl(){ var f=window._focusedNodeId; return f && !A.ov() && f===A.home() ? f : null; }
/* (pressed on the way: it waits for the landing, then goes on from there) */
var PD=0; function busy(){ return !!((window._altoSolarFlight && window._altoSolarFlight()) || (window._altoSolarLock && window._altoSolarLock.riding())); }
function later(){ if(!PD || busy() || !enl()) return; var d=PD; PD=0; step(d); }
function step(d){ var h=enl(); if(!h) return false; var to=round(h, d); if(to) go(to); return true; }
window.addEventListener('keydown', function(e){
  if(!live() || e.metaKey || e.ctrlKey || e.altKey) return;
  var ae=document.activeElement; if(ae && (ae.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(ae.tagName))) return;
  if(document.querySelector('#summary-wrap.open,#sol-craft-pop')) return;
  var k=e.key, h=A.home(), f=window._focusedNodeId, ar=/^Arrow/.test(k);
  if(k==='?'){ help(!HP); } else if(k==='o' || k==='O'){ if(!e.repeat) A.step('ov'); }
  else if(k==='Escape'){ if(HP) help(false); else if(!e.repeat) A.step((f && !A.ov()) ? 'let' : 'ov'); }
  else if(ar || /^[1-9]$/.test(k)){
    if(e.repeat){ e.preventDefault(); e.stopImmediatePropagation(); return; }
    if(busy()){ if(ar) PD=k==='ArrowRight' || k==='ArrowDown' ? 1 : -1; }
    else if(enl()){ if(ar) step(k==='ArrowRight' || k==='ArrowDown' ? 1 : -1); else { var s=scope(h), to=s[k-1]; if(to && to!==h) go(to); } }
    else if(A.ov()){ if(ar) A.step('ov'); }                           /* (the whole system: an arrow is back where you were) */
    else if(ar && h) go(h);                                         /* (panned away: back to your place) */
  } else return;
  e.preventDefault(); e.stopImmediatePropagation(); setTimeout(function(){ tick(true); }, 30);
}, true);
/* a scroll with a body enlarged: one step round what is beside it per flick (it waits for the wheel to rest) */
var WQ=0, WA=0, WT=0;
window.addEventListener('wheel', function(e){
  if(!live() || e.ctrlKey || !enl()) return; var c=document.getElementById('canvas'); if(!c || !c.contains(e.target)) return;
  if(e.target.closest && e.target.closest('#notes-panel,#summary-wrap,#info-btn,#note-dialog,input,textarea')) return;
  e.preventDefault(); e.stopImmediatePropagation(); clearTimeout(WT); WT=setTimeout(function(){ WQ=0; WA=0; }, 260);
  if(WQ) return; WA+=(Math.abs(e.deltaY)>=Math.abs(e.deltaX) ? e.deltaY : e.deltaX)*(e.deltaMode ? 40 : 1);
  if(Math.abs(WA)>=24){ WQ=1; step(WA>0 ? 1 : -1); setTimeout(function(){ tick(true); }, 30); }
}, {capture:true, passive:false});
window._altoNavOpt={get:function(){ return 'final'; }, sheet:sheet, scope:function(h){ return scope(h || A.home()); }, next:function(h){ return next(h || A.home()); }, up:function(h){ return up(h || A.home()); }};
})();
"""

NAVOPT_JS = _slim(NAVOPT_JS)
NAVOPT_CSS = _slim(NAVOPT_CSS)
