"""Moving round a System page: Luke's own design (dictated 2026-10-26, after the Nav A card was "obnoxiously large and
placed, and kind of confusing").

One small control in the bottom bar, just right of the Ship picker, in that bar's style: Back (up to the parent),
where you are (a short crumb: a click goes back to it), Next (the next concept at the same level), and the minimap's
switch. Up and parallel are those two buttons; down is the bodies that come up beside an enlarged one (its moons),
bigger than they were and titled, each a click away. With a body enlarged, the arrow keys and a scroll only go round
what is beside it (a planet's three moons: round those three; a body with nothing beside it: round the ones beside
its parent). No arrows are drawn on the page. The minimap (the whole system, you ringed) names the body under the
pointer and goes there on a click. O / Esc: the whole system; ?: the keys.

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
  #nvo-map{left:var(--nvo-l, 400px);bottom:var(--nvo-bot, 70px);padding:5px;}
  #nvo-map svg{display:block;height:104px;width:auto;max-width:190px;touch-action:manipulation;}
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
  html.phone-whole :is(#nvo-a,#nvo-map){display:none;}
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
  MG={m:m, b:ids.map(function(i){ var b=g[i]; return [i, b.x, b.y, Math.max(b.d/2, m)]; })};
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
    MP.addEventListener('pointermove', function(e){ var t=near(e.clientX, e.clientY); tip(t, e.clientX, e.clientY); MP.style.cursor=t ? 'pointer' : ''; });
    MP.addEventListener('pointerleave', function(){ tip(null); }); }
  MP.innerHTML=mapSvg(); var me=MP.querySelector('circle[data-b="'+(window.CSS && CSS.escape ? CSS.escape(h) : h)+'"]'); if(me) me.classList.add('h');
  return MP; }
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
  var on=MAP && !A.ov(); if(!on){ if(MP && MP.isConnected) MP.remove(); tip(null); }
  else { if(!MP) mapDraw(h); if(!MP.isConnected) document.body.appendChild(MP);
    if(!phone()){ var z=parseFloat(getComputedStyle(de).zoom)||1, r=W.getBoundingClientRect(), l=Math.round(r.left/z)+'px', bt=Math.round((innerHeight-r.top)/z+8)+'px';   /* (above the control, its left edge) */
      if(de.style.getPropertyValue('--nvo-l')!==l) de.style.setProperty('--nvo-l', l); if(de.style.getPropertyValue('--nvo-bot')!==bt) de.style.setProperty('--nvo-bot', bt); } }
}
setInterval(function(){ tick(); later(); }, 250); tick(true);
function act(b){ var n=b.getAttribute('data-n');
  if(n==='map'){ MAP=!MAP; lsSet('alto-solar-map', MAP ? '1' : '0'); tick(true); return; }
  var id=b.getAttribute('data-go'); if(b.disabled) return;
  if(id) go(id); else A.step('ov'); setTimeout(function(){ tick(true); }, 30); }
/* a finger acts on touchend (as the phone's own controls do: its touch layer keeps a tap's click from coming) */
var T0=null, HIT='#nvo-a [data-n],#nvo-a .nv-at,#nvo-map svg,#sk3d-l [data-go]';
document.addEventListener('touchstart', function(e){ var t=e.touches[0]; T0=t && e.target.closest && e.target.closest(HIT) ? [t.clientX, t.clientY] : null; }, {capture:true, passive:true});
document.addEventListener('touchend', function(e){ var b=T0 && e.target.closest && e.target.closest(HIT), t=e.changedTouches && e.changedTouches[0];
  if(!b || (t && Math.abs(t.clientX-T0[0])+Math.abs(t.clientY-T0[1])>12)){ T0=null; return; } T0=null; e.preventDefault(); e.stopPropagation(); hit(b, t); }, {capture:true, passive:false});
function hit(b, t, e){ var q=t || e, mp=b.closest('#nvo-map'), id=mp ? (q && near(q.clientX, q.clientY)) : b.closest('#sk3d-l') && b.getAttribute('data-go');
  if(mp){ if(id && t){ tip(id, t.clientX, t.clientY); setTimeout(function(){ tip(null); }, 900); } if(id) go(id); return; }
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
