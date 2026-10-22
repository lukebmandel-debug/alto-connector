"""The whole view on a phone: the desktop page, made for a finger (Luke, 2026-10-22).

Luke: "make it so that the viewer can actually see systems and timelines and outlines sort of like they do on desktop.
In fact, all of them. But also that they, for timelines and outlines specifically, that they can still view it in the
current format of just one card on the page." His interview: every format (vertical and horizontal timeline, outline,
the System in all its styles, the Mind Palace's city map, the Building / Museum blueprint) can be seen whole on a phone,
pinch-zoomed and panned, a card opened with a tap, with the filters, search and the style and background pickers; a
timeline or an outline keeps the one-card view as the other choice, a clear toggle switches, and the phone remembers
the last choice.

How a page decides. One class has always made a phone a phone: html.mobile, set from the user agent before the
engine lays anything out, and every format draws its desktop view only under :not(.mobile). So the whole view is the
desktop page itself (html.phone-whole, no .mobile; the runway that keeps Safari's bars clear, html.rw, stays), and
everything the desktop has comes with it. HEAD_JS runs ahead of the engine's own head script and says which:

  * a System, a Mind Palace (city or building): always whole on a phone (the CEO's call: no one-card toggle there);
  * a timeline, horizontal timeline or outline: the device's last choice (localStorage `alto-phone-view`, one choice
    for every timeline on that phone), one card until the viewer picks whole. ?view=whole / ?view=card overrides it.

Whole means the hosted script below (/phone/alto-phone-<hash>.js, palace_assets.ASSETS) is fetched in <head>,
synchronously like Retro's, so its rules are in before Safari first lays the page out (the bars latch then). A page
whose file cannot be had (an exported copy, an Artifact preview) stays the one-card phone page it always was.

What the hosted script adds to the desktop page:

  * a finger's gestures. Two fingers become the trackpad pinch each format already understands: they are turned
    into the gesturestart / gesturechange / gestureend events Safari sends for a Mac trackpad (scale since the start,
    the point between the fingers), so the city zooms with zoomTo, the System with its whole-chart zoom, the vertical
    timeline enlarges a card the desktop way. The real iOS gesture events are stopped first, so nothing is heard
    twice. A vertical timeline or outline has no zoom-out on the desktop (a window shows it whole), so here the board
    opens fitted to the phone's width and two fingers scale it (#world's transform, the canvas still scrolls it);
    pinched back to full size it is the desktop board again and a further pinch enlarges a card as on a Mac. The
    horizontal timeline's own "whole timeline" (lanes_nav.py) is its zoom-out. One finger pans (the canvas's own
    scroll, so it coasts as iOS does); a double tap zooms in, a two-finger tap zooms out (Mind Palace's phone map).
  * no hover from a finger. iOS turns the first tap on something whose hover changes the page into a hover and
    eats the click; the hover events a touch makes are stopped before the page hears them. What hover showed (a
    chip's name, a planet's name, a building's label) shows on a long press instead.
  * the controls in reach. The desktop toggles around the window's edges are hidden and stand in one glass bar at
    the bottom (44px targets, above the home indicator): Cards (timelines and outlines), Search, Filter, Notes, and
    More, a bottom sheet with the rest (overview, scene and background, light / dark, style, info, key ...). Each
    button clicks the desktop toggle it stands for, so nothing behaves differently. The panels open as sheets from
    the bottom.

Editing stays on a computer (detail_extras' edit tile already skips a phone).
"""
from __future__ import annotations

import hashlib as _hashlib
import json as _json
import re as _re

FOLDER = "phone"
KEY = "alto-phone-view"
GUARD = "_altoPhone"

# ── in every page's <head> (a few hundred bytes): the choice, and the hosted script when it is "whole" ──
HEAD_JS = r"""(function(){var q=location.search,u=/Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent)||/[?&]mobile/.test(q);if(!u)return;
var f=__FORCE__,m=/[?&]view=(card|whole)/.exec(q),v=null;try{v=localStorage.getItem('__KEY__')}catch(e){}
window._altoPhoneCan=!f;if(!(f||(m?m[1]==='whole':v==='whole')))return;__LOAD__;if(window.__GUARD__)window._altoPhoneWhole=1;})();"""

# ── in a one-card timeline / outline page: "Whole view" in the MENU drawer (under Dark / Light and Scene) ──
CARD_JS = r"""(function(){var de=document.documentElement;if(!window._altoPhoneCan||!de.classList.contains('mobile'))return;
function go(){var b=document.getElementById('nav-drawer-body');if(!b)return;var x=document.getElementById('drawer-view-btn');
if(!x){x=document.createElement('button');x.id='drawer-view-btn';x.type='button';x.className='drawer-btn';
x.innerHTML='<span class="drawer-icon"><svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="2.5" y="3" width="6" height="5" rx="1.2"/><rect x="11.5" y="3" width="6" height="5" rx="1.2"/><rect x="7" y="12" width="6" height="5" rx="1.2"/><path d="M5.5 8v2h9V8M10 10v2"/></svg></span><span class="drawer-label">Whole view</span>';
x.onclick=function(){try{localStorage.setItem('__KEY__','whole')}catch(e){}location.reload()};}
var a=document.getElementById('drawer-scene-btn')||document.getElementById('drawer-mode-btn');
if(a&&a.parentNode){if(a.nextSibling!==x)a.parentNode.insertBefore(x,a.nextSibling);}else if(x.parentNode!==b)b.insertBefore(x,b.firstChild);}
go();document.addEventListener('DOMContentLoaded',go);window.addEventListener('load',function(){go();setTimeout(go,800)});
var b=document.getElementById('nav-drawer-body');if(b)new MutationObserver(go).observe(b,{childList:true,subtree:true});})();"""

# ── the hosted script: its rules, then its gestures and its bar ──
CSS = r"""
/* the page is laid out at the phone's own size: no desktop page zoom (html{zoom:.8}), so a px is a px for a finger */
html.phone-whole{zoom:1 !important;}
/* the runway (runway.py, engine_patches mobile-runway-*): the body is the screen, the page rests 80px down it, pinned */
html.phone-whole.rw{overflow-y:scroll !important;overflow-x:hidden !important;height:auto !important;overscroll-behavior:none;touch-action:none;}
html.phone-whole.rw body *{overscroll-behavior:contain;}
html.phone-whole.rw body:not(#_){position:relative !important;width:100% !important;height:100dvh !important;min-height:0 !important;margin:80px 0 140px !important;
  overflow-x:clip !important;overflow-y:visible !important;overscroll-behavior:none;touch-action:none;}
html.phone-whole.rw #app:not(#_){height:100dvh !important;}
html.phone-whole.rw :is(#page-bg,#page-glass):not(#_){position:absolute !important;top:-80px !important;bottom:auto !important;left:0 !important;right:0 !important;height:calc(100dvh + 220px) !important;}
html.phone-whole.rw :is(__FIXED__):not(#_),html.phone-whole.rw .rw-abs:not(#_){position:absolute !important;}
html.phone-whole #canvas{touch-action:pan-x pan-y;-webkit-touch-callout:none;-webkit-user-select:none;user-select:none;}
html.phone-whole.alto-lanes #canvas{touch-action:none;}
/* the desktop toggles the bar stands in for */
html.phone-whole .ph-hide:not(.expanded):not(#_){opacity:0 !important;pointer-events:none !important;}
html.phone-whole #search-btn.expanded:not(#_){width:auto !important;height:44px;transform:none !important;}
html.phone-whole #search-btn.expanded #search-results:not(#_){left:0;right:0;width:auto;max-height:52dvh;}
/* iOS zooms the page into any field under 16px when it takes the focus */
html.phone-whole :is(input,textarea,select):not(#_){font-size:16px !important;}
html.phone-whole #info-btn.expanded:not(#_){max-width:calc(100vw - 16px) !important;max-height:62dvh !important;}
html.phone-whole:not(.ph-ready) :is(#search-btn,#info-icon,#search-toggle,#filter-toggle,#notes-toggle,#overview-toggle,#bg-toggle,#mode-toggle,#info-btn,#key-toggle):not(#_){opacity:0 !important;}
/* the bar */
#ph-bar{position:absolute;z-index:100000;opacity:1 !important;filter:none !important;left:50%;transform:translateX(-50%);bottom:calc(10px + env(safe-area-inset-bottom,0px));display:flex;gap:2px;padding:4px;border-radius:26px;
  background:var(--card-glass-bg,var(--surface));border:1px solid var(--card-glass-border,var(--border));-webkit-backdrop-filter:blur(18px) saturate(190%);backdrop-filter:blur(18px) saturate(190%);
  box-shadow:0 10px 26px var(--node-rest-shadow,rgba(0,0,0,.25)),inset 0 0 0 .5px var(--card-glass-rim,transparent);font-family:system-ui,-apple-system,sans-serif;}
html.detail-open #ph-bar,html.printing #ph-bar{display:none;}
#ph-bar button,#ph-sheet button{-webkit-tap-highlight-color:transparent;font:inherit;color:var(--text);background:none;border:0;margin:0;cursor:pointer;}
#ph-bar>button{min-width:52px;height:48px;border-radius:22px;padding:2px 6px 0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;font-size:10px;letter-spacing:.02em;color:var(--muted);}
#ph-bar>button.on,#ph-bar>button:active{color:var(--text);background:color-mix(in srgb,var(--text) 10%,transparent);}
#ph-bar svg{display:block;width:22px;height:22px;}
/* More: a bottom sheet */
#ph-scrim{position:absolute;z-index:3001;inset:-80px 0 -140px;background:rgba(0,0,0,.28);opacity:0;pointer-events:none;transition:opacity .2s;}
#ph-scrim.on{opacity:1;pointer-events:auto;}
#ph-sheet{position:absolute;z-index:3002;left:0;right:0;bottom:-140px;padding:8px 12px calc(150px + env(safe-area-inset-bottom,0px));border-radius:18px 18px 0 0;
  background:color-mix(in srgb,var(--surface,#fff) 88%,transparent);-webkit-backdrop-filter:blur(22px) saturate(180%);backdrop-filter:blur(22px) saturate(180%);
  box-shadow:0 -10px 30px rgba(0,0,0,.25);transform:translateY(100%);transition:transform .28s cubic-bezier(.2,.8,.2,1);font-family:system-ui,-apple-system,sans-serif;}
#ph-sheet.on{transform:none;}
#ph-sheet .ph-grab{width:36px;height:5px;border-radius:3px;margin:0 auto 10px;background:color-mix(in srgb,var(--muted) 60%,transparent);}
#ph-sheet .ph-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;}
#ph-sheet .ph-grid button{min-height:68px;border-radius:14px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;font-size:11.5px;color:var(--text);
  background:color-mix(in srgb,var(--text) 6%,transparent);}
#ph-sheet .ph-grid button:active{background:color-mix(in srgb,var(--text) 14%,transparent);}
#ph-sheet .ph-grid svg{width:24px;height:24px;}
/* what a hover showed, on a long press */
html.phone-whole .node-card :is(.csym-btn,.esym-btn,.tsym-btn).ph-hover ~ .chip-tip{opacity:1;transform:translateX(-50%) translateY(0);}
html.phone-whole.alto-solar #world .node[data-solar].ph-hover>.sol-lbl{opacity:1;z-index:9;max-width:none;}
/* the top: the name clear of the clef and the wordmark, the chips one row that a finger scrolls */
html.phone-whole #title-text:not(#_){max-width:calc(100vw - 196px);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:20px;}
html.phone-whole #nav:not(#_){flex-wrap:nowrap !important;height:46px !important;max-height:46px;overflow-x:auto !important;overflow-y:hidden !important;justify-content:flex-start !important;
  pointer-events:auto !important;scrollbar-width:none;-webkit-overflow-scrolling:touch;}
html.phone-whole #nav::-webkit-scrollbar{display:none;}
html.phone-whole #nav>*{flex:none !important;}
/* each format's own row of controls rides above the bar, a finger's width from the edges, and scrolls if it is wide */
html.phone-whole :is(#sol-ctl,#pal-ctl,#lanes-nav):not(#_){bottom:calc(74px + env(safe-area-inset-bottom,0px)) !important;max-width:calc(100vw - 16px);}
html.phone-whole :is(#sol-ctl,#pal-ctl):not(#_){left:8px !important;right:auto !important;transform:none !important;overflow-x:auto;scrollbar-width:none;}
html.phone-whole :is(#sol-ctl,#pal-ctl)::-webkit-scrollbar{display:none;}
/* the panels: full width, from the bottom */
html.phone-whole :is(#ef-panel,#bg-panel,#notes-panel):not(#_){left:0 !important;right:0 !important;width:auto !important;max-width:none !important;}
html.phone-whole #notes-panel:not(#_){padding-bottom:calc(76px + env(safe-area-inset-bottom,0px)) !important;}
html.phone-whole #summary-wrap:not(#_){padding-bottom:calc(76px + env(safe-area-inset-bottom,0px)) !important;}
/* an open search or INFO stands where the format's row was */
html.phone-whole:has(:is(#search-btn,#info-btn).expanded) :is(#sol-ctl,#pal-ctl,#lanes-nav):not(#_){visibility:hidden !important;}
"""

JS = r"""(function(){
if(window._altoPhone) return;
var de=document.documentElement, KEY=__KEY__, CAN=!!window._altoPhoneCan;
var st=document.createElement('style'); st.id='alto-phone-css'; st.textContent=__CSS__; (document.head||de).appendChild(st);
function on(){ return de.classList.contains('phone-whole'); }
function fmt(){ return document.getElementById('bldg-root') ? 'bldg' : de.classList.contains('alto-palace') ? 'palace' : de.classList.contains('alto-solar') ? 'solar' : de.classList.contains('alto-lanes') ? 'lanes' : 'tl'; }
function cv(){ return document.getElementById('canvas'); }
function detail(){ return de.classList.contains('detail-open'); }
function now(){ return performance.now(); }
function reduced(){ return window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches; }

/* ── a finger never hovers: the hover events a touch makes are stopped before the page hears them ── */
var lastTouch=-1e9;
window.addEventListener('touchstart', function(){ lastTouch=now(); }, {capture:true, passive:true});
['mouseover','mouseenter','mousemove'].forEach(function(t){ window.addEventListener(t, function(e){
  if(on() && !e._alto && now()-lastTouch<1000) e.stopImmediatePropagation(); }, true); });
['pointerover','pointerenter'].forEach(function(t){ window.addEventListener(t, function(e){
  if(on() && !e._alto && e.pointerType==='touch') e.stopImmediatePropagation(); }, true); });
/* iOS's own pinch events: ours stand in for them */
['gesturestart','gesturechange','gestureend'].forEach(function(t){ window.addEventListener(t, function(e){
  if(on() && e.isTrusted){ e.preventDefault(); e.stopImmediatePropagation(); } }, {capture:true, passive:false}); });

/* a trackpad pinch, as Safari sends it, where the fingers are */
function gev(type, scale, x, y){
  var t=document.elementFromPoint(x, y)||document.body, e=new Event(type, {bubbles:true, cancelable:true});
  e._alto=1; [['scale',scale],['rotation',0],['clientX',x],['clientY',y],['pageX',x],['pageY',y]].forEach(function(p){ Object.defineProperty(e, p[0], {value:p[1]}); });
  t.dispatchEvent(e);
}

/* ── the vertical timeline / outline: the board fitted to the phone, scaled by two fingers ── */
/* the board's own zoom (CSS zoom, not a transform: WebKit keeps a transformed board's full-size scroll extent) */
var OV={s:1, w:0}, ovA=0;
function world(){ return document.getElementById('world'); }
function fitS(){ var c=cv(), w=world(); if(!c || !w) return 1; if(OV.s>=.999 || !OV.w) OV.w=w.offsetWidth||1; return Math.min(1, (c.clientWidth-8)/OV.w); }
function ovSet(s, px, py){                       /* scale s, the board point under (px, py) on screen staying there */
  var c=cv(), w=world(); if(!c || !w) return;
  var smin=fitS(); s=Math.max(smin, Math.min(1, s));
  var r=c.getBoundingClientRect(); px=(px==null ? r.left+c.clientWidth/2 : px); py=(py==null ? r.top+c.clientHeight/2 : py);
  var a=w.getBoundingClientRect(), wx=(px-a.left)/OV.s, wy=(py-a.top)/OV.s;
  OV.s=s;
  if(s>=.999){ OV.s=1; w.style.zoom=''; de.classList.remove('ph-ov'); }
  else { w.style.zoom=s.toFixed(4); de.classList.add('ph-ov'); }
  var b=w.getBoundingClientRect(); c.scrollLeft+=b.left+wx*OV.s-px; c.scrollTop+=b.top+wy*OV.s-py;
}
function ovAnim(s1, x, y, done){
  cancelAnimationFrame(ovA); var s0=OV.s, t0=now(), ms=reduced() ? 1 : 320;
  (function fr(t){ var k=Math.min(1, (t-t0)/ms), e=1-Math.pow(1-k, 3);
    ovSet(Math.exp(Math.log(s0)+(Math.log(s1)-Math.log(s0))*e), x, y);
    if(k<1) ovA=requestAnimationFrame(fr); else if(done) done(); })(t0);
}
/* a tap on a card while the board is small: back to full size round it, then the desktop's own click */
document.addEventListener('click', function(e){
  if(!on() || fmt()!=='tl' || OV.s>=.999 || e._alto) return;
  var n=e.target.closest && e.target.closest('#world .node'); if(!n) return;
  e.preventDefault(); e.stopImmediatePropagation();
  var r=n.getBoundingClientRect(), x=r.left+r.width/2, y=r.top+r.height/2, card=n.querySelector('.node-card')||n;
  ovAnim(1, x, y, function(){ var c=cv(), rr=n.getBoundingClientRect(), cr=c.getBoundingClientRect();
    c.scrollLeft+=rr.left+rr.width/2-(cr.left+cr.width/2); c.scrollTop+=rr.top+rr.height/2-(cr.top+cr.height/2);
    var ev=new MouseEvent('click', {bubbles:true, cancelable:true, clientX:x, clientY:y}); ev._alto=1; card.dispatchEvent(ev); });
}, true);

/* ── the horizontal timeline: its own "whole timeline" is the zoom-out ── */
function lanesOv(){ var c=cv(); return !!(c && c.classList.contains('ln-ov')); }
function lanesToggle(){ var b=document.querySelector('#lanes-nav .lnv-ov'); if(b) b.click(); }

/* ── touches on the board ── */
var G=null, T=null, lastTap=null, LP=null, hov=[];
function mine(e){ var c=cv(), t=e.target; return on() && !detail() && c && t && c.contains(t) && !(t.closest && t.closest('input,textarea,select,[contenteditable]')); }
function mid(e){ var a=e.touches[0], b=e.touches[1]; return [(a.clientX+b.clientX)/2, (a.clientY+b.clientY)/2]; }
function dist(e){ var a=e.touches[0], b=e.touches[1]; return Math.hypot(a.clientX-b.clientX, a.clientY-b.clientY)||1; }
function unhover(){ hov.forEach(function(el){ el.classList.remove('ph-hover');
  ['mouseout','mouseleave','pointerout','pointerleave'].forEach(function(t){ var e=new Event(t, {bubbles:t.indexOf('leave')<0}); e._alto=1; el.dispatchEvent(e); }); }); hov=[]; }
function hover(el, x, y){                          /* a long press: what the pointer resting there would show */
  unhover(); var stop=el.closest && el.closest('.node');
  for(var p=el; p && p!==document.body; p=p.parentNode){ p.classList.add('ph-hover'); hov.push(p); if(p===stop) break; }
  ['pointerover','pointerenter','mouseover','mouseenter','mousemove'].forEach(function(t){
    var e=t.indexOf('pointer')===0 ? new PointerEvent(t, {bubbles:t.indexOf('enter')<0, clientX:x, clientY:y, pointerType:'mouse'}) : new MouseEvent(t, {bubbles:t.indexOf('enter')<0, clientX:x, clientY:y});
    e._alto=1; el.dispatchEvent(e); });
  if(navigator.vibrate) try{ navigator.vibrate(8); }catch(_){}
}
var eatClick=0;
document.addEventListener('click', function(e){ if(eatClick && now()<eatClick){ eatClick=0; e.preventDefault(); e.stopImmediatePropagation(); } }, true);

function pinchStart(e){
  var m=mid(e), f=fmt(); clearTimeout(LP && LP.t); LP=null;
  G={d0:dist(e), m0:m, m:m, f:f, own:null, s:1, t0:now(), moved:false, ov0:OV.s};
  if(f==='palace' || f==='solar'){ G.own='engine'; gev('gesturestart', 1, m[0], m[1]); }
  else if(f==='tl'){ G.own=OV.s<.999 ? 'me' : '?'; }
  else G.own='lanes';
}
function pinchMove(e){
  var m=mid(e), s=dist(e)/G.d0, c=cv(), dx=m[0]-G.m[0], dy=m[1]-G.m[1]; G.m=m; G.s=s;
  if(Math.abs(s-1)>.04 || Math.hypot(m[0]-G.m0[0], m[1]-G.m0[1])>12) G.moved=true;
  if(G.own==='?'){ if(s<.97) G.own='me'; else if(s>1.03){ G.own='engine'; gev('gesturestart', 1, G.m0[0], G.m0[1]); } }
  if(G.own==='engine'){ if(c && G.f!=='solar'){ c.scrollLeft-=dx; c.scrollTop-=dy; } gev('gesturechange', s, m[0], m[1]); }
  else if(G.own==='me'){ if(c){ c.scrollLeft-=dx; c.scrollTop-=dy; } ovSet(G.ov0*s, m[0], m[1]); }
  else if(G.own==='lanes' && !G.done){
    if(!lanesOv() && s<.8){ G.done=1; lanesToggle(); }
    else if(lanesOv() && s>1.25){ G.done=1; var t=document.elementFromPoint(m[0], m[1]); if(t) t.click(); }
  }
}
function pinchEnd(){
  var g=G; G=null; if(!g) return;
  if(g.own==='engine') gev('gestureend', g.s, g.m[0], g.m[1]);
  if(g.own==='me' && OV.s>.94 && OV.s<1) ovAnim(1, g.m[0], g.m[1]);
  if(!g.moved && now()-g.t0<260) zoomBy(.5, g.m[0], g.m[1]);          /* a two-finger tap: out */
}
function zoomBy(f, x, y){                          /* a double tap (in) or a two-finger tap (out), gliding */
  var k=fmt();
  if(k==='tl'){ if(f<1 || OV.s<.999) ovAnim(Math.max(fitS(), Math.min(1, OV.s*f)), x, y); return; }
  if(k==='lanes'){ if((f<1)!==lanesOv()) lanesToggle(); return; }
  var t0=now(), ms=reduced() ? 1 : 300; gev('gesturestart', 1, x, y);
  (function fr(t){ var p=Math.min(1, (t-t0)/ms), e=1-Math.pow(1-p, 3); gev('gesturechange', Math.exp(Math.log(f)*e), x, y);
    if(p<1) requestAnimationFrame(fr); else gev('gestureend', f, x, y); })(t0);
}
document.addEventListener('touchstart', function(e){
  if(!mine(e)) { if(hov.length && !(e.target.closest && e.target.closest('.ph-hover'))) unhover(); return; }
  if(hov.length) unhover();
  if(e.touches.length===2){ e.preventDefault(); pinchStart(e); return; }
  if(e.touches.length>2 || G) return;
  var t=e.touches[0]; T={x:t.clientX, y:t.clientY, t0:now(), moved:false};
  var el=e.target; LP={t:setTimeout(function(){ if(T && !T.moved){ T.long=true; eatClick=now()+800; hover(el, T.x, T.y); } }, 480)};
}, {capture:true, passive:false});
document.addEventListener('touchmove', function(e){
  if(G){ if(e.touches.length>=2){ e.preventDefault(); pinchMove(e); } return; }
  if(T && e.touches.length===1){ var t=e.touches[0]; if(Math.hypot(t.clientX-T.x, t.clientY-T.y)>10){ T.moved=true; clearTimeout(LP && LP.t); } }
}, {capture:true, passive:false});
document.addEventListener('touchend', function(e){
  if(G){ if(e.touches.length<2) pinchEnd(); return; }
  clearTimeout(LP && LP.t); var t=T; T=null; if(!t || t.moved || t.long || now()-t.t0>300) return;
  var empty=!(e.target.closest && e.target.closest('.node,button,a,[role=button],.pal-hit,.sol-hit,.b-tag'));
  if(lastTap && now()-lastTap.t<320 && Math.hypot(t.x-lastTap.x, t.y-lastTap.y)<30 && empty){ lastTap=null; e.preventDefault(); zoomBy(2, t.x, t.y); return; }
  lastTap={t:now(), x:t.x, y:t.y};
}, {capture:true, passive:false});
document.addEventListener('touchcancel', function(){ if(G) pinchEnd(); T=null; clearTimeout(LP && LP.t); }, true);

/* ── the bar ── */
var IC={
  cards:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><rect x="5" y="3" width="14" height="18" rx="2.5"/><path d="M8.5 8h7M8.5 12h7M8.5 16h4"/></svg>',
  whole:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><rect x="2.5" y="3.5" width="7" height="6" rx="1.4"/><rect x="14.5" y="3.5" width="7" height="6" rx="1.4"/><rect x="8.5" y="14.5" width="7" height="6" rx="1.4"/><path d="M6 9.5v2.5h12V9.5M12 12v2.5"/></svg>',
  search:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="10.5" cy="10.5" r="6"/><path d="M15 15l5.5 5.5"/></svg>',
  filter:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M3.5 5h17l-6.5 8v6l-4-2v-4z"/></svg>',
  notes:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M6 3.5h9l4 4v13H6z"/><path d="M15 3.5v4h4M9 12h7M9 16h5"/></svg>',
  more:'<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="5.5" cy="12" r="1.9"/><circle cx="12" cy="12" r="1.9"/><circle cx="18.5" cy="12" r="1.9"/></svg>',
  info:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5"/><circle cx="12" cy="7.8" r=".6" fill="currentColor"/></svg>',
  dot:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="7"/></svg>'
};
/* [desktop toggle, label, icon key or null (its own icon), in the bar] — the first found of a group stands for it */
var SLOTS=[['search-btn','Search','search',1],['search-toggle','Search','search',1],['filter-toggle','Filter','filter',1],['notes-toggle','Notes','notes',1],
  ['overview-toggle','Overview',null,0],['bg-toggle','Scene',null,0],['mode-toggle','Light / Dark',null,0],['key-toggle','Key',null,0],
  ['minimap-toggle','Map',null,0],['info-icon','Info','info',0],['info-btn','Info','info',0],['account-btn','Account',null,0]];
function label(el, d){ return (el.getAttribute('aria-label')||el.getAttribute('title')||d||el.textContent||'').trim().split('\n')[0].slice(0,22); }
function icon(el, k){ if(k && IC[k]) return IC[k]; var s=el.querySelector('svg'); return s ? s.outerHTML : IC.dot; }
function mk(tag, cls, html){ var e=document.createElement(tag); if(cls) e.className=cls; if(html!=null) e.innerHTML=html; return e; }
var bar=null, sheet=null, scrim=null;
function sheetOn(v){ if(!sheet) return; sheet.classList.toggle('on', v); scrim.classList.toggle('on', v); }
function swap(v){ try{ localStorage.setItem(KEY, v); }catch(e){} location.reload(); }
function build(){
  if(!on() || !document.body) return;
  if(bar) bar.remove(); if(sheet){ sheet.remove(); scrim.remove(); }
  bar=mk('div'); bar.id='ph-bar'; bar.setAttribute('role','toolbar'); bar.setAttribute('aria-label','Controls');
  scrim=mk('div'); scrim.id='ph-scrim'; scrim.onclick=function(){ sheetOn(false); };
  sheet=mk('div', null, '<div class="ph-grab"></div><div class="ph-grid"></div>'); sheet.id='ph-sheet'; sheet.setAttribute('role','dialog'); sheet.setAttribute('aria-label','More');
  var grid=sheet.querySelector('.ph-grid');
  function btn(where, html, txt, fn){ var b=mk('button', null, html+(where===bar ? '<span>'+txt+'</span>' : '<span>'+txt+'</span>')); b.type='button'; b.setAttribute('aria-label', txt); b.onclick=fn; where.appendChild(b); return b; }
  if(CAN) btn(bar, IC.cards, 'Cards', function(){ swap('card'); });
  var had={};
  SLOTS.forEach(function(s){
    var el=document.getElementById(s[0]); if(!el || getComputedStyle(el).display==='none') return;
    el.classList.add('ph-hide'); if(had[s[1]]) return; had[s[1]]=1;
    var go=function(){ sheetOn(false);
      /* search: opened and focused inside this tap, or iOS raises no keyboard (its own focus waits 60ms) */
      if(s[0]==='search-btn' && window.toggleSearch){ window.toggleSearch(); var i=document.getElementById('search-input'); if(i && window._searchOpen) i.focus(); return; }
      setTimeout(function(){ el.click(); }, 0); };   /* the rest after this tap is done: a panel's own "a click outside closes me" must not hear it */
    if(s[3]) btn(bar, icon(el, s[2]), s[1], go); else btn(grid, icon(el, s[2]), label(el, s[1]), go);
  });
  if(CAN) btn(grid, IC.cards, 'One card at a time', function(){ swap('card'); });
  if(grid.children.length) btn(bar, IC.more, 'More', function(){ sheetOn(!sheet.classList.contains('on')); });
  document.body.appendChild(scrim); document.body.appendChild(sheet); document.body.appendChild(bar);
  de.classList.add('ph-ready');
  help(); pin('search-btn', {left:'8px', right:'8px', bottom:ABOVE}); pin('info-btn', {left:'auto', right:'8px', bottom:ABOVE, top:'auto'});
}
/* the engine pins search and INFO by the desktop's bottom row (alignInfo: inline !important, rewritten on every scroll);
   on a phone they stand above the bar, the search the bar's width */
function pin(id, props){
  var el=document.getElementById(id); if(!el || el._phPin) return; el._phPin={};
  var go=function(){ for(var k in props){ var v=el.style.getPropertyValue(k);
    if(v!==el._phPin[k] || el.style.getPropertyPriority(k)!=='important'){ el.style.setProperty(k, props[k], 'important'); el._phPin[k]=el.style.getPropertyValue(k); } } };
  new MutationObserver(go).observe(el, {attributes:true, attributeFilter:['style']}); go();
}
var ABOVE='calc(74px + env(safe-area-inset-bottom, 0px))';
/* INFO speaks of a finger here: the first two paragraphs stay (how it is made; which pages a card opens), the rest say how this view is used */
var HELP=[['Zoom &amp; move','pinch to zoom, drag to move; a double tap zooms in, a two-finger tap zooms out.'],
  ['Names','press and hold a chip, a planet or a building to see what the pointer would show on a computer.'],
  ['The bar','at the bottom: <em>Cards</em> (one card at a time, where there is that view), <em>Search</em>, <em>Filter</em>, <em>Notes</em> and <em>More</em>: the overview, the background, light or dark, your account.'],
  ['Groups &amp; filters','the chips along the top (swipe them sideways) open group pages; <em>Filter</em> narrows the cards.'],
  ['Highlight &amp; note','on a detail page, press and drag over text to highlight it; tap a highlight to add a note. <em>Notes</em> holds them, makes reports, shares and prints.'],
  ['Alto home','the Alto clef or the wordmark at the top opens your homepage. Editing is on a computer.']];
function help(){
  var c=document.getElementById('info-content'); if(!c || c._ph) return; c._ph=1;
  var ps=[].slice.call(c.querySelectorAll('p')), open=null;
  ps.forEach(function(p, i){ var t=(p.querySelector('strong')||{}).textContent||'';
    if(/^Open a card/.test(t)){ open=p; p.innerHTML=p.innerHTML.replace(/click/gi, 'tap').replace(/\.\s*<em>[^]*$/, '. The names along the top of a detail page step between pages; &#8592; goes back.'); }
    else if(!/^Making it/.test(t)) p.remove(); });
  HELP.forEach(function(h){ var p=mk('p', 'info-desktop', '<strong>'+h[0]+'</strong> &#8212; '+h[1]); p.style.margin='5px 0'; c.appendChild(p); });
}
function fit(){ if(on() && fmt()==='tl' && !detail()){ var s=fitS(), c=cv(); if(s<.999 && c){ var r=c.getBoundingClientRect(); ovSet(s, r.left, r.top); c.scrollLeft=0; c.scrollTop=0; } } }
document.addEventListener('DOMContentLoaded', function(){ build(); });
window.addEventListener('load', function(){ build(); fit(); setTimeout(build, 900); });
window.addEventListener('resize', function(){ if(OV.s<1) ovSet(OV.s); });
window._altoPhone={on:on, fmt:fmt, ov:OV, ovSet:ovSet, zoomBy:zoomBy, build:build, swap:swap};
})();"""


def _slim(src: str) -> str:
    src = _re.sub(r"/\*.*?\*/", "", src, flags=_re.S)
    return "\n".join(t for t in (ln.strip() for ln in src.split("\n")) if t and not t.startswith("//"))


def _fixed() -> str:
    from .engine_patches import _RW_FIXED
    return _RW_FIXED


ASSET = _slim(JS.replace("__KEY__", _json.dumps(KEY))
              .replace("__CSS__", _json.dumps(_slim(CSS.replace("__FIXED__", _fixed())))))
V = _hashlib.sha256(ASSET.encode("utf-8")).hexdigest()[:10]
PATH = f"/{FOLDER}/alto-phone-{V}.js"


def phone_asset() -> tuple[str, str]:
    """(file name under /phone/, the script) for the site (palace_assets.ASSETS)."""
    return PATH.rsplit("/", 1)[1], ASSET


def head_block(force: bool) -> str:
    """The <script> for <head>, ahead of the engine's own: `force` for a System or a Mind Palace (whole on every phone)."""
    from .palace_assets import loader
    js = (HEAD_JS.replace("__FORCE__", "1" if force else "0").replace("__KEY__", KEY)
          .replace("__GUARD__", GUARD).replace("__LOAD__", loader(PATH, GUARD)))
    return '<script id="alto-phone-head">' + js + "</script>"


def card_block(force: bool) -> str:
    """The MENU drawer's "Whole view" (a timeline, horizontal timeline or outline only)."""
    return "" if force else "<script>" + CARD_JS.replace("__KEY__", KEY) + "</script>\n"
