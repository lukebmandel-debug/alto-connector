"""Moving round a System page: where you are, and every neighbour by name (Luke, 2026-10-23 tried four options side by
side; 2026-10-25 he chose this one, the old "A", as the one way, beside the Tour bar's Back / Next / Overview).

A panel over the Tour bar: "Whole system › Sun › Planet" (each crumb goes there), then one row: Up to the parent · Same
level: the siblings in orbit order (you highlighted), and an Inside: row of the children. Keys: ↑ / U up, ← → the
siblings, ↓ the first child, 1 – 9 that child, O / Esc the whole system, ? the keys. No direction to decode, nothing on
the map (the named pills and drawn ways are hidden while it shows). The Tour bar stays for the reading order, its
crumb dropped (the panel has it). On a phone the panel waits in MENU ("Where you are") and opens as a sheet over the
corner controls; a tap on a name goes there and closes it.

The other options (B ring, C minimap, D guided) and their chooser are gone; ?nav= and a choice kept from them are
ignored. Every move goes through solar_draw.py's own ride / flight (window._altoSolarNavApi)."""

from .solar_draw import _slim

NAVOPT_CSS = r"""
  .nvo{position:fixed;z-index:305;font-size:13px;color:var(--text);background:var(--card-glass-bg, var(--surface));-webkit-backdrop-filter:blur(18px) saturate(190%);backdrop-filter:blur(18px) saturate(190%);
    border:1px solid var(--card-glass-border, var(--border));box-shadow:0 10px 26px var(--node-rest-shadow), inset 0 0 0 0.5px var(--card-glass-rim);border-radius:16px;box-sizing:border-box;}
  .nvo button{font:inherit;font-weight:600;color:var(--text);background:transparent;border:0;border-radius:999px;padding:0 11px;min-height:34px;cursor:pointer;
    white-space:nowrap;max-width:240px;overflow:hidden;text-overflow:ellipsis;line-height:1.2;}
  .nvo button:hover{background:color-mix(in srgb,var(--accent,#6d5bd0) 12%,transparent);} .nvo button:focus-visible{outline:2px solid var(--accent,#6d5bd0);outline-offset:2px;}
  .nvo button.on{color:#fff;background:var(--accent,#6d5bd0);border-color:transparent;}
  .nvo .nv-r>button{flex:0 0 auto;}
  .nvo .nv-r>i{font-style:normal;color:var(--muted);align-self:center;padding:0 2px 0 6px;}
  .nvo .nv-r{display:flex;gap:6px;overflow-x:auto;scrollbar-width:none;padding:2px;} .nvo .nv-r::-webkit-scrollbar{display:none;}
  #nvo-a{left:50%;bottom:var(--nvo-bot, calc(90px + var(--sol-ctl-h, 35px)));transform:translateX(-50%);width:fit-content;max-width:calc(100vw - 24px);padding:6px 8px;display:flex;flex-direction:column;gap:2px;}
  #nvo-a .nv-at{font-size:12px;padding:2px 6px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  #nvo-a .nv-at a{color:var(--text);cursor:pointer;text-decoration:none;font-weight:600;} #nvo-a .nv-at b{color:var(--text);font-weight:800;}
  #nvo-help{right:58px;top:84px;width:min(330px, calc(100vw - 24px));padding:12px 14px;line-height:1.45;}
  #nvo-help kbd{font:inherit;font-weight:700;border:1px solid var(--border);border-radius:5px;padding:0 5px;}
  html.navx :is(.sol-nh,#sol-way,#sol-here,#sk3d-l i){display:none !important;}   /* (the panel names every way: nothing on the map, nor on the 3D scene) */
  html.navx #sol-tour .tb-at>i:first-child{display:none;}                /* (the panel has the crumb) */
  #nvo-where{display:none !important;}                                   /* (MENU's way to the panel, on a phone only) */
  html.phone-whole #nvo-a{display:none;left:8px;right:8px;width:auto;transform:none;max-width:none;max-height:58vh;overflow-y:auto;bottom:calc(70px + env(safe-area-inset-bottom,0px));padding:8px;}
  html.phone-whole.nvo-open #nvo-a{display:flex;}
  html.phone-whole .nvo button{min-width:44px;min-height:44px;}
  html.phone-whole #nvo-a .nv-at{font-size:13px;white-space:normal;} html.phone-whole #nvo-a .nv-r{flex-wrap:wrap;overflow:visible;}
  html.mobile:not(.phone-whole) .nvo,html.alto-editing .nvo{display:none !important;}   /* (the phone's card view; seen whole a phone has the sheet: phone.py copies html.mobile rules to it) */
  html.alto-stars:not(.sk-retro) .nvo{background:rgba(5,10,28,.86);color:#eef2ff;border-color:rgba(170,198,255,.3);}   /* (the Star charts' dark glass, as their Tour bar) */
  html.alto-stars:not(.sk-retro) .nvo button{color:#eef2ff;} html.alto-stars:not(.sk-retro) .nvo .nv-r>i,html.alto-stars:not(.sk-retro) #nvo-a .nv-at{color:rgba(220,230,255,.62);}
  html.alto-stars:not(.sk-retro) #nvo-a .nv-at :is(a,b){color:#eef2ff;}
  html.sk-retro .nvo{background:rgba(3,4,7,.95);color:#efe6cf;border-radius:0;border-color:rgba(217,174,85,.55);box-shadow:none;}
  html.sk-retro .nvo button{border-radius:0;color:#d9ae55;} html.sk-retro .nvo button.on{background:#d9ae55;color:#000;}
  html.sk-retro #nvo-a .nv-at a,html.sk-retro #nvo-a .nv-at b{color:#efe6cf;}
  @media print{ .nvo{display:none !important;} }
"""

NAVOPT_JS = r"""
(function(){
if(!window._altoSolarNavApi) return;
var A=window._altoSolarNavApi, de=document.documentElement;
var KEYS=[['Up arrow or U', 'up a level'], ['Left / Right arrows', 'the one before / after, same level'], ['Down arrow', 'inside: the first one'], ['1 – 9', 'inside: that one'], ['O or Esc', 'see the whole system'], ['Back / Next', 'the tour, in reading order']];
function mk(t, id, cls, h){ var e=document.createElement(t); if(id) e.id=id; if(cls) e.className=cls; if(h!=null) e.innerHTML=h; return e; }
function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;'}[c]; }); }
function nm(id){ return esc(A.name(id)); }
function btn(id, txt, tip, cls){ return '<button type="button" data-go="'+esc(id)+'"'+(cls ? ' class="'+cls+'"' : '')+' title="'+esc(tip || '')+'">'+txt+'</button>'; }
function phone(){ return de.classList.contains('phone-whole'); }
function sheet(on){ de.classList.toggle('nvo-open', !!on); }
function go(id){ sheet(false); if(!id) return; if(A.ov() && id===A.home()) A.step('ov'); else A.go(id); }
function chain(h){ var c=[h], p=A.up(h); while(p && c.length<12){ c.unshift(p); p=A.up(p); } return c; }
function sib(h, d){ var s=A.sibs(h), i=s.indexOf(h); return s[i+d] || null; }
function live(){ return A.ok() && !document.querySelector('#detail-page.visible'); }
var W=null, K='';
function draw(h){ var w=W || (W=mk('div', 'nvo-a', 'nvo')), c=chain(h), up=A.up(h), s=A.sibs(h), k=A.kids(h);
  w.innerHTML='<div class="nv-at"><a data-go="" title="The whole system (O)">Whole system</a> › '+c.map(function(i, j){ return j===c.length-1 ? '<b>'+nm(i)+'</b>' : '<a data-go="'+esc(i)+'">'+nm(i)+'</a>'; }).join(' › ')+'</div>'+
    '<div class="nv-r">'+(up ? btn(up, 'Up to '+nm(up), 'The body this one orbits (↑)') : '')+
    (s.length>1 ? '<i title="In orbit order (← →)">Same level:</i>'+s.map(function(i){ return btn(i, nm(i), i===h ? 'You are here' : 'A sibling (← →)', i===h ? 'on' : ''); }).join('') : '')+'</div>'+
    (k.length ? '<div class="nv-r"><i title="Its children (↓, or 1 – 9)">Inside:</i>'+k.map(function(i, j){ return btn(i, nm(i), 'Child '+(j+1)+' ('+(j<9 ? j+1 : '↓')+')'); }).join('')+'</div>' : '');
  var on=w.querySelector('.on'); if(on) on.scrollIntoView({block:'nearest', inline:'center'}); return w; }
var HP=null;
function help(on){ if(HP){ HP.remove(); HP=null; } if(!on) return;
  HP=mk('div', 'nvo-help', 'nvo', '<b>How to move</b><br>'+KEYS.map(function(k){ return '<kbd>'+k[0]+'</kbd> '+k[1]; }).join('<br>'));
  HP.setAttribute('role', 'dialog'); HP.setAttribute('aria-label', 'How to move'); document.body.appendChild(HP); }
/* the phone's way in: a button in the System's controls, which MENU lists under View (phone_minimal.py) */
function where(){ var c=document.getElementById('sol-ctl'); if(!c || document.getElementById('nvo-where')) return;
  var b=mk('button', 'nvo-where', 'sol-opt', '<span>Where you are</span>'); b.type='button'; b.title='Where you are, and every way from here, by name';
  b.addEventListener('click', function(e){ e.stopPropagation(); sheet(!de.classList.contains('nvo-open')); }); c.appendChild(b); }
/* ── keeping it current: what is drawn follows where you are ── */
function tick(force){
  where(); var tb=document.getElementById('sol-tour'), sc=document.getElementById('sol-ctl'), z=parseFloat(getComputedStyle(de).zoom)||1,
    r=tb && tb.getClientRects().length ? tb.getBoundingClientRect() : sc && sc.getClientRects().length ? sc.getBoundingClientRect() : null,
    bt=r ? Math.round((innerHeight-r.top)/z+8)+'px' : '';   /* (just above the Tour bar, else the style row) */
  if(de.style.getPropertyValue('--nvo-bot')!==bt) de.style.setProperty('--nvo-bot', bt); de.classList.toggle('navx', A.ok());
  if(!live()){ if(W){ W.remove(); W=null; K=''; } sheet(false); return; }
  var h=A.home(); if(!h) return; var k=h+'|'+A.ov()+'|'+A.order().length; if(k===K && !force) return; K=k;
  var w=draw(h); if(!w.isConnected) document.body.appendChild(w);
}
setInterval(tick, 250); tick(true);
function act(b){ var id=b.getAttribute('data-go'); if(id) go(id); else { sheet(false); A.step('ov'); } }
/* a finger acts on touchend (as the phone's own controls do: its touch layer keeps a tap's click from coming) */
var T0=null;
document.addEventListener('touchstart', function(e){ var t=e.touches[0]; T0=t && e.target.closest && e.target.closest('.nvo [data-go]') ? [t.clientX, t.clientY] : null; }, {capture:true, passive:true});
document.addEventListener('touchend', function(e){ var b=T0 && e.target.closest && e.target.closest('.nvo [data-go]'), t=e.changedTouches && e.changedTouches[0];
  if(!b || (t && Math.abs(t.clientX-T0[0])+Math.abs(t.clientY-T0[1])>12)){ T0=null; return; } T0=null; e.preventDefault(); e.stopPropagation(); act(b); }, {capture:true, passive:false});
document.addEventListener('click', function(e){ var t=e.target, b=t.closest && t.closest('.nvo [data-go]');
  if(b){ e.preventDefault(); e.stopPropagation(); act(b); return; }
  if(HP && !(t.closest && t.closest('#nvo-help'))) help(false);
  if(phone() && de.classList.contains('nvo-open') && !(t.closest && t.closest('#nvo-a,#nvo-where,#hamburger-tab,#nav-drawer'))) sheet(false);
}, true);
window.addEventListener('keydown', function(e){
  if(!live() || e.metaKey || e.ctrlKey || e.altKey) return;
  var ae=document.activeElement; if(ae && (ae.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(ae.tagName))) return;
  if(document.querySelector('#summary-wrap.open,#sol-craft-pop')) return;
  var k=e.key, h=A.home(), to=null, c=null, f=window._focusedNodeId;
  if(k==='?'){ help(!HP); } else if(k==='o' || k==='O'){ c='ov'; }
  else if(k==='Escape'){ if(HP) help(false); else c=(f && !A.ov()) ? 'let' : 'ov'; }
  else { to=k==='ArrowUp' || k==='u' || k==='U' ? A.up(h) : k==='ArrowDown' ? A.kids(h)[0] : k==='ArrowLeft' ? sib(h, -1) : k==='ArrowRight' ? sib(h, 1) : /^[1-9]$/.test(k) ? A.kids(h)[k-1] : null;
    if(to===null && !/^Arrow|^[1-9uU]$/.test(k)) return; }
  e.preventDefault(); e.stopImmediatePropagation(); if(e.repeat) return;
  if(to) go(to); else if(c) A.step(c); tick(true);
}, true);
window._altoNavOpt={get:function(){ return 'a'; }, sheet:sheet};
})();
"""

NAVOPT_JS = _slim(NAVOPT_JS)
NAVOPT_CSS = _slim(NAVOPT_CSS)
