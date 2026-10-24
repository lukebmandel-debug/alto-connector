"""Four ways of moving round a System page, to try side by side (Luke, 2026-10-23:
"develop a number of options for user-friendly navigation in system mode, which
i will test live").

  A  Breadcrumb + neighbours: "You are in: Sun › Planet › Moon", then named buttons
     for Up, the siblings in orbit order and the children. No direction to decode.
  B  Radial ring: a tap on the enlarged body (or R / Space) rings it with its
     neighbours — the parent above, the children below, the siblings left and right.
  C  Minimap: the whole system in a corner, you ringed; a tap flies there, the
     route lit in the main view on the way.
  D  Guided: one Next / Back pair in reading order (the outline, depth first),
     "3 of 42 · Next: …", and the whole system.

The choice: ?nav=a|b|c|d|current in the address, or the Nav chooser beside the
style switch (and in the ? card); kept per device (localStorage alto-solar-nav).
Current = the Tour bar as before, and nothing here draws. Every move goes through
solar_draw.py's own ride / flight (window._altoSolarNavApi); an option on sets
html.navx, which hides the Tour bar and hands the keys to the option."""

from .solar_draw import _slim

NAVOPT_CSS = r"""
  .nvo{position:fixed;z-index:312;font-size:13px;color:var(--text);background:var(--card-glass-bg, var(--surface));-webkit-backdrop-filter:blur(18px) saturate(190%);backdrop-filter:blur(18px) saturate(190%);
    border:1px solid var(--card-glass-border, var(--border));box-shadow:0 10px 26px var(--node-rest-shadow), inset 0 0 0 0.5px var(--card-glass-rim);border-radius:16px;box-sizing:border-box;}
  .nvo button{font:inherit;font-weight:600;color:var(--text);background:transparent;border:1px solid var(--border);border-radius:999px;padding:0 13px;min-height:44px;cursor:pointer;
    white-space:nowrap;max-width:240px;overflow:hidden;text-overflow:ellipsis;line-height:1.2;}
  .nvo button:hover{border-color:var(--accent,#6d5bd0);} .nvo button:focus-visible{outline:2px solid var(--accent,#6d5bd0);outline-offset:2px;}
  .nvo button.on,.nvo .nv-go{color:#fff;background:var(--accent,#6d5bd0);border-color:transparent;}
  .nvo .nv-l{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:2px 2px 0;}
  .nvo .nv-r{display:flex;gap:6px;overflow-x:auto;scrollbar-width:none;padding:2px;} .nvo .nv-r::-webkit-scrollbar{display:none;}
  .nvo .nv-ov{color:var(--muted);}
  #nvo-a,#nvo-d{left:50%;bottom:calc(41px + var(--sol-ctl-h, 35px));transform:translateX(-50%);width:min(620px, calc(100vw - 24px));padding:8px 10px;display:flex;flex-direction:column;gap:4px;}
  #nvo-a .nv-at{font-size:13px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  #nvo-a .nv-at a{color:var(--text);cursor:pointer;text-decoration:none;font-weight:600;} #nvo-a .nv-at b{color:var(--text);font-weight:800;}
  #nvo-d{flex-direction:row;align-items:center;justify-content:space-between;gap:10px;}
  #nvo-d button{min-height:52px;font-size:15px;} #nvo-d .nv-go{flex:1 1 auto;max-width:none;}
  #nvo-d .nv-at{text-align:center;color:var(--muted);font-size:12px;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;} #nvo-d .nv-at b{display:block;color:var(--text);font-size:14px;}
  #nvo-b{left:0;top:0;background:none;border:0;box-shadow:none;-webkit-backdrop-filter:none;backdrop-filter:none;pointer-events:none;width:0;height:0;}
  #nvo-b button{position:absolute;transform:translate(-50%,-50%);pointer-events:auto;background:var(--card-glass-bg, var(--surface));-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);box-shadow:0 6px 16px var(--node-rest-shadow);max-width:180px;animation:nvpop .18s ease-out both;}
  #nvo-b button i{font-style:normal;color:var(--muted);margin-right:5px;}
  @keyframes nvpop{from{opacity:0;transform:translate(-50%,-50%) scale(.6);}}
  #nvo-bh{left:50%;bottom:calc(41px + var(--sol-ctl-h, 35px));transform:translateX(-50%);padding:6px 14px;color:var(--muted);border-radius:999px;pointer-events:none;}
  #nvo-c{right:58px;bottom:calc(41px + var(--sol-ctl-h, 35px));width:min(280px, 46vw);padding:6px;}
  #nvo-c svg{display:block;width:100%;height:auto;touch-action:manipulation;}
  #nvo-c circle{fill:var(--muted);fill-opacity:.55;cursor:pointer;} #nvo-c circle.s{fill:#f0b542;fill-opacity:1;}
  #nvo-c circle.h{fill:var(--accent,#6d5bd0);fill-opacity:1;stroke:var(--text);stroke-width:2.4px;vector-effect:non-scaling-stroke;}
  #nvo-c circle.t{fill-opacity:.0001;}
  #nvo-c line{stroke:var(--text);stroke-opacity:.22;stroke-width:1px;vector-effect:non-scaling-stroke;} #nvo-c line.r{stroke:#f0b542;stroke-opacity:1;stroke-width:2.5px;}
  #nvo-c .nv-at{font-size:12px;color:var(--muted);padding:2px 4px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;} #nvo-c .nv-at b{color:var(--text);}
  .nvpk{display:inline-flex;align-items:center;gap:2px;padding:2px;border-radius:999px;background:var(--card-glass-bg, var(--surface));border:1px solid var(--card-glass-border, var(--border));font-size:12px;}
  .nvpk span{color:var(--muted);font-weight:700;padding:0 5px;}
  .nvpk button{font:inherit;font-weight:700;color:var(--muted);background:none;border:0;border-radius:999px;min-width:30px;min-height:30px;padding:0 7px;cursor:pointer;}
  .nvpk button.on{color:#fff;background:var(--accent,#6d5bd0);}
  #nvo-help{right:58px;top:84px;width:min(330px, calc(100vw - 24px));padding:12px 14px;line-height:1.45;}
  #nvo-help kbd{font:inherit;font-weight:700;border:1px solid var(--border);border-radius:5px;padding:0 5px;}
  #nvo-help .nvpk{margin-top:8px;}
  html.phone-whole .nvpk button{min-width:44px;min-height:44px;}
  html.phone-whole :is(#nvo-a,#nvo-d,#nvo-bh){bottom:96px;} html.phone-whole #nvo-c{right:8px;bottom:96px;} html.phone-whole #nvo-help{right:8px;}
  html.mobile .nvo,html.alto-editing .nvo{display:none !important;}
  @media print{ .nvo{display:none !important;} }
"""

NAVOPT_JS = r"""
(function(){
if(!window._altoSolarNavApi) return;
var A=window._altoSolarNavApi, de=document.documentElement, OPTS=['a', 'b', 'c', 'd', 'current'];
var NAMES={a:'Breadcrumb + neighbours', b:'Radial ring', c:'Minimap', d:'Guided Next / Back', current:'Current (the Tour bar)'};
var KEYS={a:[['↑ or U', 'up to the parent'], ['← →', 'the siblings, in orbit order'], ['↓', 'the first child'], ['1 – 9', 'that child'], ['O or Esc', 'the whole system']],
  b:[['R or Space', 'ring the body with its neighbours'], ['↑ ↓ ← →', 'with the ring: parent, first child, siblings'], ['Esc', 'close the ring, then the whole system']],
  c:[['tap the map', 'fly there; the route lights up'], ['M', 'show or hide the map'], ['O or Esc', 'the whole system']],
  d:[['→ or Space', 'Next, in reading order'], ['←', 'Back'], ['O or Esc', 'the whole system']],
  current:[['→ ←', 'the tour'], ['Shift + → ←', 'the siblings'], ['↑ ↓', 'a level'], ['O or Esc', 'the whole system']]};
function get(){ try{ return localStorage.getItem('alto-solar-nav'); }catch(e){ return null; } }
function put(v){ try{ localStorage.setItem('alto-solar-nav', v); }catch(e){} }
var q=(location.search.match(/[?&]nav=(a|b|c|d|current)\b/i) || [])[1], NV=q ? q.toLowerCase() : get();
if(OPTS.indexOf(NV)<0) NV='current'; if(q) put(NV);
function mk(t, id, cls, h){ var e=document.createElement(t); if(id) e.id=id; if(cls) e.className=cls; if(h!=null) e.innerHTML=h; return e; }
function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;'}[c]; }); }
function nm(id){ return esc(A.name(id)); }
function btn(id, txt, tip, cls){ return '<button type="button" data-go="'+esc(id)+'"'+(cls ? ' class="'+cls+'"' : '')+' title="'+esc(tip || '')+'">'+txt+'</button>'; }
function go(id){ if(!id) return; ring(false); if(A.ov() && id===A.home()) A.step('ov'); else A.go(id); }
function chain(h){ var c=[h], p=A.up(h); while(p && c.length<12){ c.unshift(p); p=A.up(p); } return c; }
function sib(h, d){ var s=A.sibs(h), i=s.indexOf(h); return s[i+d] || null; }
function live(){ return A.ok() && !document.querySelector('#detail-page.visible'); }
var W={}, K='';
function drop(){ Object.keys(W).forEach(function(k){ if(W[k]) W[k].remove(); }); W={}; K=''; ring(false); }
/* ── A: where you are, and every neighbour by name ── */
function drawA(h){ var w=W.a || (W.a=mk('div', 'nvo-a', 'nvo')), c=chain(h), up=A.up(h), s=A.sibs(h), k=A.kids(h);
  w.innerHTML='<div class="nv-at">You are in: '+c.map(function(i, j){ return j===c.length-1 ? '<b>'+nm(i)+'</b>' : '<a data-go="'+esc(i)+'">'+nm(i)+'</a>'; }).join(' › ')+'</div>'+
    '<div class="nv-r">'+(up ? btn(up, '↑ Up: '+nm(up), 'The body this one orbits (↑)') : '')+btn('', '◎ Overview', 'The whole system (O)', 'nv-ov')+'</div>'+
    (s.length>1 ? '<div class="nv-l">'+(up ? 'Siblings' : 'Suns')+' · in orbit order</div><div class="nv-r">'+s.map(function(i){ return btn(i, nm(i), i===h ? 'You are here' : 'A sibling (← →)', i===h ? 'on' : ''); }).join('')+'</div>' : '')+
    (k.length ? '<div class="nv-l">Children</div><div class="nv-r">'+k.map(function(i, j){ return btn(i, (j<9 ? (j+1)+' · ' : '')+nm(i), 'A child ('+(j<9 ? j+1 : '↓')+')'); }).join('')+'</div>' : '');
  var on=w.querySelector('.on'); if(on) on.scrollIntoView({block:'nearest', inline:'center'}); return w; }
/* ── D: the outline in reading order ── */
function drawD(h){ var w=W.d || (W.d=mk('div', 'nvo-d', 'nvo')), T=A.order(), i=T.indexOf(h), pv=T[i-1], nx=T[i+1];
  w.innerHTML=(pv ? btn(pv, '‹ Back', 'Back: '+A.name(pv)+' (←)') : '<button type="button" disabled>‹ Back</button>')+
    '<div class="nv-at"><b>'+nm(h)+'</b>'+(i+1)+' of '+T.length+(nx ? ' · Next: '+nm(nx) : ' · the end')+'</div>'+
    btn(nx || '', nx ? 'Next ›' : 'Whole system ›', nx ? 'Next: '+A.name(nx)+' (→ or Space)' : 'The whole system', 'nv-go')+btn('', '◎', 'The whole system (O)', 'nv-ov');
  return w; }
/* ── B: the ring round the enlarged body ── */
var RG=null;
function bodyBox(id){ var n=document.getElementById('node-'+id); return n && n.getBoundingClientRect(); }
function ring(on){ if(!on){ if(RG){ RG.remove(); RG=null; } return; }
  var h=A.home(), r=h && bodyBox(h); if(!r || !r.width) return; ring(false);
  var cx=r.left+r.width/2, cy=r.top+r.height/2, R=Math.max(r.width, r.height)/2+46, up=A.up(h), k=A.kids(h).slice(0, 7), a=sib(h, -1), b=sib(h, 1), s='';
  function at(id, x, y, ic, tip){ s+='<button type="button" data-go="'+esc(id)+'" title="'+esc(tip)+'" style="left:'+Math.max(70, Math.min(innerWidth-70, x)).toFixed(0)+'px;top:'+Math.max(30, Math.min(innerHeight-30, y)).toFixed(0)+'px"><i>'+ic+'</i>'+nm(id)+'</button>'; }
  if(up) at(up, cx, cy-R, '↑', 'Up: the parent (↑)');
  if(a) at(a, cx-R-40, cy, '←', 'The sibling before (←)'); if(b) at(b, cx+R+40, cy, '→', 'The sibling after (→)');
  k.forEach(function(id, j){ var t=k.length===1 ? Math.PI/2 : Math.PI*(.2+.6*j/(k.length-1)); at(id, cx+Math.cos(t)*(R+30)*1.15, cy+Math.sin(t)*(R+18)+18*(j%2), '↓', 'A child'+(j ? '' : ' (↓)')); });
  s+='<button type="button" data-open="1" title="Open its page" style="left:'+cx.toFixed(0)+'px;top:'+cy.toFixed(0)+'px">Open page</button>';
  RG=mk('div', 'nvo-b', 'nvo', s); RG._h=h; RG._k={n:up, s:k[0], w:a, e:b}; document.body.appendChild(RG); }
function drawB(h){ var w=W.b || (W.b=mk('div', 'nvo-bh', 'nvo')); w.textContent=A.name(h)+' · tap it (or R) for its neighbours'; if(RG && RG._h!==h) ring(false); return w; }
/* ── C: the minimap ── */
var CG=null, CB=null, SH=true;
function mapGeo(){ var g=A.geo(), ids=Object.keys(g), x0=1/0, y0=1/0, x1=-1/0, y1=-1/0;
  ids.forEach(function(i){ var b=g[i], r=b.d/2; x0=Math.min(x0, b.x-r); y0=Math.min(y0, b.y-r); x1=Math.max(x1, b.x+r); y1=Math.max(y1, b.y+r); });
  var p=(x1-x0)*.04, s='<svg viewBox="'+[x0-p, y0-p, x1-x0+2*p, y1-y0+2*p].map(function(v){ return v.toFixed(0); }).join(' ')+'" role="img" aria-label="The whole system: tap a body to fly there">';
  ids.forEach(function(i){ var b=g[i]; if(b.p && g[b.p]) s+='<line data-a="'+esc(i)+'" x1="'+g[b.p].x.toFixed(0)+'" y1="'+g[b.p].y.toFixed(0)+'" x2="'+b.x.toFixed(0)+'" y2="'+b.y.toFixed(0)+'"/>'; });
  var m=(x1-x0)/90;
  ids.forEach(function(i){ var b=g[i]; s+='<circle data-id="'+esc(i)+'" class="'+(b.role==='sun' ? 's' : '')+'" cx="'+b.x.toFixed(0)+'" cy="'+b.y.toFixed(0)+'" r="'+Math.max(b.d/2, m).toFixed(0)+'"><title>'+nm(i)+'</title></circle>'; });
  ids.forEach(function(i){ var b=g[i]; s+='<circle data-id="'+esc(i)+'" class="t" cx="'+b.x.toFixed(0)+'" cy="'+b.y.toFixed(0)+'" r="'+Math.max(b.d/2, m*3).toFixed(0)+'"/>'; });   /* (wide, clear targets for a finger) */
  return s+'</svg>'; }
function lit(to){ if(!W.c) return; var c=to ? chain(to) : [], h=A.home(), hc=h ? chain(h) : [];
  W.c.querySelectorAll('line').forEach(function(l){ var a=l.getAttribute('data-a'); l.classList.toggle('r', !!to && (c.indexOf(a)>=0) !== (hc.indexOf(a)>=0)); });
  A.show(to); }
function drawC(h){ var w=W.c; if(!w){ w=W.c=mk('div', 'nvo-c', 'nvo', mapGeo()+'<div class="nv-at"></div>');
    w.addEventListener('pointerover', function(e){ var t=e.target.getAttribute && e.target.getAttribute('data-id'); if(t) lit(t); });
    w.addEventListener('pointerleave', function(){ lit(null); }); }
  w.hidden=!SH; w.querySelectorAll('circle.h').forEach(function(c){ c.classList.remove('h'); });
  var me=w.querySelector('circle[data-id="'+(window.CSS && CSS.escape ? CSS.escape(h) : h)+'"]:not(.t)'); if(me) me.classList.add('h');
  w.querySelector('.nv-at').innerHTML='You are here: <b>'+nm(h)+'</b>'; return w; }
/* ── the chooser and the ? card ── */
function pick(){ return '<span>Nav</span>'+OPTS.map(function(o){ return '<button type="button" data-nav="'+o+'" title="'+NAMES[o]+'" class="'+(o===NV ? 'on' : '')+'">'+(o==='current' ? 'Current' : o.toUpperCase())+'</button>'; }).join('')+
  '<button type="button" data-nav="?" title="How to move (?)" aria-haspopup="dialog">?</button>'; }
function chooser(){ var c=document.getElementById('sol-ctl'), p=document.getElementById('nvo-pick');
  if(c && c.offsetParent!==null){ if(!p || p.parentNode!==c){ if(p) p.remove(); p=mk('div', 'nvo-pick', 'nvpk', pick()); p.setAttribute('role', 'group'); p.setAttribute('aria-label', 'Navigation option'); c.appendChild(p); } }
  else if(!p || p.parentNode===c){ if(p) p.remove(); p=mk('div', 'nvo-pick', 'nvo nvpk', pick()); p.style.cssText='left:12px;top:84px;'; document.body.appendChild(p); }
  p.querySelectorAll('[data-nav]').forEach(function(b){ b.classList.toggle('on', b.getAttribute('data-nav')===NV); }); }
var HP=null;
function help(on){ if(HP){ HP.remove(); HP=null; } if(!on) return;
  HP=mk('div', 'nvo-help', 'nvo', '<b>'+NAMES[NV]+'</b><br>'+KEYS[NV].map(function(k){ return '<kbd>'+k[0]+'</kbd> '+k[1]; }).join('<br>')+'<div class="nvpk" style="margin-top:8px">'+pick()+'</div>');
  HP.setAttribute('role', 'dialog'); HP.setAttribute('aria-label', 'How to move'); document.body.appendChild(HP); }
function set(v){ if(OPTS.indexOf(v)<0) return; NV=v; put(v); drop(); if(HP) help(true); tick(true); }
/* ── keeping it current: what is drawn follows where you are ── */
function tick(force){
  chooser(); de.classList.toggle('navx', NV!=='current' && A.ok());
  if(NV==='current' || !live()){ if(Object.keys(W).length) drop(); return; }
  var h=A.home(); if(!h) return; var k=NV+'|'+h+'|'+A.ov()+'|'+A.order().length+'|'+SH; if(k===K && !force) return; K=k;
  var w=NV==='a' ? drawA(h) : NV==='b' ? drawB(h) : NV==='c' ? drawC(h) : drawD(h); if(!w.isConnected) document.body.appendChild(w);
}
setInterval(tick, 250); tick(true);
window._altoNavOpt={get:function(){ return NV; }, set:set, ring:ring};
var BY=false;
document.addEventListener('click', function(e){ var t=e.target, b=t.closest && t.closest('[data-nav],[data-go],[data-open]');
  if(b && b.hasAttribute('data-open')){ e.preventDefault(); e.stopPropagation(); var n=RG && document.getElementById('node-'+RG._h); ring(false); if(n){ BY=true; n.click(); BY=false; } return; }
  if(b && b.closest('.nvo,.nvpk')){ e.preventDefault(); e.stopPropagation(); var v=b.getAttribute('data-nav');
    if(v) return v==='?' ? help(!HP) : set(v);
    var id=b.getAttribute('data-go'); if(id) go(id); else A.step('ov'); return; }
  if(HP && !(t.closest && t.closest('#nvo-help'))) help(false);
}, true);
/* B: a tap on the enlarged body rings it (its own click, the full page, is the ring's middle: a second tap) */
window.addEventListener('click', function(e){ if(NV!=='b' || BY || !live() || e.button) return;
  var n=e.target.closest && e.target.closest('#world .node[data-solar]'); if(!n || n.id.slice(5)!==window._focusedNodeId) { if(RG && !(e.target.closest && e.target.closest('#nvo-b'))) ring(false); return; }
  if(RG && RG._h===n.id.slice(5)) { ring(false); return; }
  e.preventDefault(); e.stopImmediatePropagation(); ring(true); }, true);
/* C: a tap on the map lights the route, then flies it */
document.addEventListener('pointerup', function(e){ if(NV!=='c' || !W.c || !W.c.contains(e.target)) return; var id=e.target.getAttribute('data-id'); if(!id) return;
  lit(id); setTimeout(function(){ go(id); }, 380); }, true);
window.addEventListener('keydown', function(e){
  if(NV==='current' || !live() || e.metaKey || e.ctrlKey || e.altKey) return;
  var ae=document.activeElement; if(ae && (ae.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(ae.tagName))) return;
  if(document.querySelector('#summary-wrap.open,#sol-craft-pop')) return;
  var k=e.key, h=A.home(), to=null, c=null, f=window._focusedNodeId;
  if(k==='?'){ help(!HP); } else if(k==='o' || k==='O'){ c='ov'; }
  else if(k==='Escape'){ if(HP) help(false); else if(RG) ring(false); else c=(f && !A.ov()) ? 'let' : 'ov'; }
  else if(NV==='a'){ to=k==='ArrowUp' || k==='u' || k==='U' ? A.up(h) : k==='ArrowDown' ? A.kids(h)[0] : k==='ArrowLeft' ? sib(h, -1) : k==='ArrowRight' ? sib(h, 1) : /^[1-9]$/.test(k) ? A.kids(h)[k-1] : null;
    if(to===null && !/^Arrow|^[1-9uU]$/.test(k)) return; }
  else if(NV==='b'){ if(k==='r' || k==='R' || k===' '){ ring(!RG); } else if(RG && /^Arrow/.test(k)){ to=RG._k[{ArrowUp:'n', ArrowDown:'s', ArrowLeft:'w', ArrowRight:'e'}[k]]; } else return; }
  else if(NV==='c'){ if(k==='m' || k==='M'){ SH=!SH; } else if(/^Arrow/.test(k)) c={ArrowRight:'next', ArrowLeft:'prev', ArrowUp:'up', ArrowDown:'down'}[k]; else return; }
  else if(NV==='d'){ if(k==='ArrowRight' || k===' ') c='next'; else if(k==='ArrowLeft') c='prev'; else if(/^Arrow/.test(k)) c=null; else return; }
  e.preventDefault(); e.stopImmediatePropagation(); if(e.repeat) return;
  if(to) go(to); else if(c) A.step(c); tick(true);
}, true);
})();
"""

NAVOPT_JS = _slim(NAVOPT_JS)
NAVOPT_CSS = _slim(NAVOPT_CSS)
