"""The whole view on a phone: the desktop page, made for a finger (Luke, 2026-10-22).

Luke: "make it so that the viewer can actually see systems and timelines and outlines sort of like they do on desktop.
In fact, all of them. But also that they, for timelines and outlines specifically, that they can still view it in the
current format of just one card on the page." His interview: every format (vertical and horizontal timeline, outline,
the System in all its styles, the Memory Palace's city map, the Building / Museum blueprint) can be seen whole on a phone,
pinch-zoomed and panned, a card opened with a tap, with the filters, search and the style and background pickers; a
timeline or an outline keeps the one-card view as the other choice, a clear toggle switches, and the phone remembers
the last choice.

How a page decides (Luke, 2026-10-23, after v1.9.153 had put the desktop page with a new bar on phones: "look at how
it was before you started mobile parity and build up from there"; "timeline and outline start in phone design default.
Other modes don't have that default option at all"). One class has always made a phone a phone: html.mobile, set from
the user agent before the engine lays anything out; the phone design (the engine's phone script and every html.mobile
rule) and every format's desktop view hang on it. builder.phone_mode picks, and HEAD_JS runs ahead of the engine's
own head script:

  * a timeline or an outline ("card"): the phone design, one card, every time it is opened; MENU's "Whole view" shows
    it whole for this tab (sessionStorage `alto-phone-view:<path>`); ?view=whole / ?view=card overrides it;
  * a System or a horizontal timeline ("whole"): always whole;
  * a Memory Palace ("phone"): nothing of this file, the phone page it has always been (palace_mobile.py's map page,
    the Blueprint and the Atlas drawn under the phone tiles).

Whole means the desktop page (html.phone-whole, no .mobile; the runway that keeps Safari's bars clear, html.rw, stays)
under the phone design: phone_scripts lets the engine's phone scripts run in a window where the page is html.mobile, so
they build its tiles, MENU drawer, MAP list and search pill themselves, and the hosted script below gives those pieces
their phone rules. The hosted script (/phone/alto-phone-<hash>.js, palace_assets.ASSETS) is fetched in <head>,
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
    horizontal timeline scales its board with the same events (lanes_nav.py's zoom). One finger pans (the canvas's own
    scroll, so it coasts as iOS does); a double tap zooms in, a two-finger tap zooms out (Memory Palace's phone map).
  * no hover from a finger. iOS turns the first tap on something whose hover changes the page into a hover and
    eats the click; the hover events a touch makes are stopped before the page hears them. What hover showed (a
    chip's name, a planet's name, a building's label) shows on a long press instead.
  * the phone design's chrome. remap() copies each html.mobile rule of the chrome (header, MAP, MENU and its drawer,
    the search pill, INFO, FILTER, MARK, NOTES and their panels) to html.phone-whole and stands the desktop's rules for
    the same pieces down; the board's own rules (canvas, cards, detail page, a format's layers) stay the desktop's.

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
var f=__FORCE__,m=/[?&]view=(card|whole)/.exec(q),v=null;try{localStorage.removeItem('__KEY__');v=sessionStorage.getItem('__KEY__:'+location.pathname)}catch(e){}
window._altoPhoneCan=!f;if(!(f||(m?m[1]==='whole':v==='whole')))return;__LOAD__;if(window.__GUARD__)window._altoPhoneWhole=1;})();"""

# ── in a one-card timeline / outline page: "Whole view" in the MENU drawer (under Dark / Light and Scene) ──
CARD_JS = r"""(function(){var de=document.documentElement;if(!window._altoPhoneCan||!de.classList.contains('mobile'))return;
function go(){var b=document.getElementById('nav-drawer-body');if(!b)return;var x=document.getElementById('drawer-view-btn');
if(!x){x=document.createElement('button');x.id='drawer-view-btn';x.type='button';x.className='drawer-btn';
x.innerHTML='<span class="drawer-icon"><svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="2.5" y="3" width="6" height="5" rx="1.2"/><rect x="11.5" y="3" width="6" height="5" rx="1.2"/><rect x="7" y="12" width="6" height="5" rx="1.2"/><path d="M5.5 8v2h9V8M10 10v2"/></svg></span><span class="drawer-label">Whole view</span>';
x.onclick=function(){try{sessionStorage.setItem('__KEY__:'+location.pathname,'whole')}catch(e){}location.reload()};}
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
/* iOS zooms the page into any field under 16px when it takes the focus */
html.phone-whole :is(input,textarea,select):not(#_){font-size:16px !important;}
/* nothing of the desktop's corner toggles before the phone design's rules are in (remap) */
html.phone-whole:not(.ph-ready) :is(#search-btn,#info-btn,#overview-toggle,#bg-toggle,#mode-toggle,#key-toggle,#account-btn):not(#_){opacity:0 !important;}
/* the phone detail page's BACK tile belongs to a detail page only (it showed on the whole view itself) */
html.phone-whole:not(.detail-open) #detail-back-fixed:not(#_){display:none !important;}
/* the previous / next page's name on a detail page (the desktop's pill rule is off here): room inside the pill, and 8px clear of the screen edge (Art, 2026-10-28) */
html.phone-whole :is(#nav-prev-label,#nav-next-label) .wrap-pill:not(#_){display:inline-block;box-sizing:border-box;max-width:calc(100% - 12px);margin-top:3px;margin-bottom:3px;padding:5px 10px;white-space:normal;}
html.phone-whole #nav-prev-label .wrap-pill:not(#_){margin-left:8px;}
html.phone-whole #nav-next-label .wrap-pill:not(#_){margin-right:8px;}
/* a detail page's Back, whole view: the same chevron-only round button beside the clef as the phone design's (item 12; the desktop's #desk-back is off here) */
html.phone-whole.detail-open #detail-back-fixed:not(#_){display:flex !important;position:fixed !important;top:calc((51px + env(safe-area-inset-top,0px)) / 2 - 17px);bottom:auto;left:48px;width:34px;height:34px;padding:0;align-items:center;justify-content:center;
  background:var(--card-glass-bg);border:1px solid var(--card-glass-border);border-radius:17px;color:var(--muted);font-size:0;gap:0;z-index:296;}
/* a timeline or an outline seen whole: a card shows its name alone until it is enlarged (Luke, 2026-10-24: "just have node
   titles/label unless enlarged, cause the text is falling outside the borders") */
html.phone-whole:not(.alto-solar):not(.alto-lanes) #world .node:not(.focused) .node-card :is(.node-desc,.node-summary,.node-footer,.node-tag,.node-order):not(#_){display:none !important;}
html.phone-whole:not(.alto-solar):not(.alto-lanes) #world .node:not(.focused) .node-title:not(#_){line-height:1.2 !important;overflow-wrap:normal;word-break:normal;hyphens:manual;-webkit-hyphens:manual;}
/* a card's name stays 12px on the glass at the readable scales (the board's own size shrinks with the zoom): bigger on the board, never past 22px, never under its own 16px */
html.phone-whole.ph-ov:not(.alto-solar):not(.alto-lanes) #world .node:not(.focused) .node-title:not(#_){font-size:max(16.25px, min(22px, calc(12px / var(--ph-os,1))));}
/* the glass has no edge at the sides of the screen (Art A4: no seam) */
html.phone-whole:not(.alto-lanes):not(.alto-solar) #glass-slab:not(#_){box-shadow:none !important;border-left-color:transparent !important;border-right-color:transparent !important;}
/* an enlarged card is the desktop's 1.7x (the engine zooms it) unless that is wider than the phone: then a little less, as large as leaves 16px each side (--ph-fk, set by the script below) */
html.phone-whole .node.focused .node-card:not(#_){transform:scale(var(--ph-fk,1)) !important;}
/* an enlarged card has the screen: the unit numerals (they ride the right edge) and the Alto wordmark do not sit on it */
html.phone-whole #canvas.focus-mode .phase-numeral:not(#_){opacity:0 !important;pointer-events:none !important;}
/* what a hover showed, on a long press */
html.phone-whole .node-card :is(.csym-btn,.esym-btn,.tsym-btn).ph-hover ~ .chip-tip{opacity:1;transform:translateX(-50%) translateY(0);}
html.phone-whole.alto-solar #world .node[data-solar].ph-hover>.sol-lbl{opacity:1;z-index:9;max-width:none;}
/* the one-card view's pieces: the swipe hint and the chips that step a card at a time */
html.phone-whole :is(#tab-rail,#scroll-hint,#timeline-label-bar,#compass-rose,#nav-prev-btn,#nav-next-btn):not(#_){display:none !important;}
/* each format's own row of controls sits at the bottom between the phone design's corner tiles (INFO / FILTER left,
   MARK / NOTES right), and scrolls sideways if it is wide */
html.phone-whole :is(#sol-ctl,#pal-ctl,#lanes-nav):not(#_){bottom:calc(8px + env(safe-area-inset-bottom,0px)) !important;max-width:calc(100vw - 112px);}
html.phone-whole :is(#sol-ctl,#pal-ctl):not(#_){left:56px !important;right:auto !important;transform:none !important;overflow-x:auto;scrollbar-width:none;}
html.phone-whole :is(#sol-ctl,#pal-ctl)::-webkit-scrollbar{display:none;}
html.phone-whole #lanes-nav:not(#_){left:56px !important;right:56px !important;width:auto !important;transform:none !important;}
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
var OV={s:1, w:0}, ovA=0, START=.6;     /* (the board opens readable: a card's name 12px on the glass at least, two columns across; pinch out for all of it) */
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
  de.style.setProperty('--ph-os', OV.s.toFixed(3));
  slabFit();
  var b=w.getBoundingClientRect(); c.scrollLeft+=b.left+wx*OV.s-px; c.scrollTop+=b.top+wy*OV.s-py;
}
/* the timeline's glass slab ends where its last unit does: seen small, a short board left the page's plain gradient under it (a hard edge mid-screen).
   Its height grows to the window's foot (the last unit's tint carrying on), so the glass runs the full height at any scale. */
function slabFit(){ var sl=document.getElementById('glass-slab'), c=cv(); if(!sl || !c) return;
  if(sl._h0==null){ sl._h0=parseFloat(sl.style.height)||sl.offsetHeight; var m=/(#[0-9a-fA-F]{6,8}|rgba?\([^)]*\))\s+100%\)\s*$/.exec(sl.style.backgroundImage||''); sl._last=m ? m[1] : ''; }
  var top=parseFloat(sl.style.top)||0, h=Math.max(sl._h0, c.clientHeight/OV.s-top);
  sl.style.height=h+'px';
  if(h>sl._h0+1 && sl._last){ sl.style.backgroundSize='100% '+sl._h0+'px'; sl.style.backgroundRepeat='no-repeat'; sl.style.backgroundColor=sl._last; }
  else { sl.style.backgroundSize=''; sl.style.backgroundRepeat=''; sl.style.backgroundColor=''; } }
function ovAnim(s1, x, y, done){
  cancelAnimationFrame(ovA); var s0=OV.s, t0=now(), ms=reduced() ? 1 : 320;
  (function fr(t){ var k=Math.min(1, (t-t0)/ms), e=1-Math.pow(1-k, 3);
    ovSet(Math.exp(Math.log(s0)+(Math.log(s1)-Math.log(s0))*e), x, y);
    if(k<1) ovA=requestAnimationFrame(fr); else if(done) done(); })(t0);
}
function fsSet(){ de.style.setProperty('--ph-fk', Math.min(1, (innerWidth-32)/(290*1.7)).toFixed(3)); }
fsSet(); window.addEventListener('resize', fsSet); window.addEventListener('orientationchange', function(){ setTimeout(fsSet, 150); });
/* a tap on a card enlarges it where it is (the desktop's focus mode: Luke, 2026-11-01, "you cannot enlarge a node without
   going into it"); a tap on the enlarged card goes in (its own click), a tap on the board leaves (the engine's own click
   rule). A board still small first returns to full size round the card. */
document.addEventListener('click', function(e){
  if(!on() || fmt()!=='tl' || e._alto || detail() || !window.enterFocus) return;
  var n=e.target.closest && e.target.closest('#world .node'); if(!n) return;
  var id=n.id.slice(5); if(window._focusedNodeId===id) return;
  e.preventDefault(); e.stopImmediatePropagation();
  enterFocus(id);
}, true);
/* enlarging a card (a tap, MAP's list, a search result) from a board still small: full size round the card first, then the engine's own enlarge
   (its scroll sums are for a board at full size) */
function wrapFocus(){ var o=window.enterFocus; if(typeof o!=='function' || o._ph) return;
  var w=function(id){ var a=arguments, me=this, el=id && document.getElementById('node-'+id);
    if(!(on() && fmt()==='tl' && OV.s<.999 && el)) return o.apply(me, a);
    var r=el.getBoundingClientRect(); ovAnim(1, r.left+r.width/2, r.top+r.height/2, function(){ o.apply(me, a); }); };
  w._ph=1; window.enterFocus=w; }

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
  if(f==='palace' || f==='solar' || f==='lanes'){ G.own='engine'; gev('gesturestart', 1, m[0], m[1]); }
  else G.own=OV.s<.999 ? 'me' : '?';
}
function pinchMove(e){
  var m=mid(e), s=dist(e)/G.d0, c=cv(), dx=m[0]-G.m[0], dy=m[1]-G.m[1]; G.m=m; G.s=s;
  if(Math.abs(s-1)>.04 || Math.hypot(m[0]-G.m0[0], m[1]-G.m0[1])>12) G.moved=true;
  if(G.own==='?'){ if(s<.97){ G.own='me'; if(window._focusedNodeId && window.exitFocus) exitFocus(); } else if(s>1.03){ G.own='engine'; gev('gesturestart', 1, G.m0[0], G.m0[1]); } }
  if(G.own==='engine'){ if(c && G.f!=='solar' && G.f!=='lanes'){ c.scrollLeft-=dx; c.scrollTop-=dy; } gev('gesturechange', s, m[0], m[1]); }   /* (the horizontal timeline's zoom keeps the pinched point under the fingers itself) */
  else if(G.own==='me'){ if(c){ c.scrollLeft-=dx; c.scrollTop-=dy; } ovSet(G.ov0*s, m[0], m[1]); }
}
function pinchEnd(){
  var g=G; G=null; if(!g) return;
  if(g.own==='engine') gev('gestureend', g.s, g.m[0], g.m[1]);
  if(g.own==='me' && OV.s>.94 && OV.s<1) ovAnim(1, g.m[0], g.m[1]);
  if(!g.moved && now()-g.t0<260) zoomBy(.5, g.m[0], g.m[1]);          /* a two-finger tap: out */
}
function zoomBy(f, x, y){                          /* a double tap (in) or a two-finger tap (out), gliding */
  var k=fmt();
  if(k==='tl'){ if(f<1 && window._focusedNodeId && window.exitFocus) exitFocus(); if(f<1 || OV.s<.999) ovAnim(Math.max(fitS(), Math.min(1, OV.s*f)), x, y); return; }
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

/* ── the phone design over the whole view (Luke, 2026-10-23: "look at how it was before you started mobile parity and
   build up from there"). The engine's phone scripts ran inside a window where the page was html.mobile (phone_scripts:
   the tiles, the MENU drawer, MAP's list, the search pill, INFO, MARK and NOTES are theirs, built by their own code);
   their rules are written for html.mobile, so here the ones for that chrome are copied for html.phone-whole and the
   desktop rules for the same pieces stand down. A board's own rules (the cards, the canvas, a detail page) are left
   to the desktop. ── */
var BOARD=/#(canvas|world|river-svg|solar-svg|glass-slab|detail-page|detail-content|detail-[\w-]+|sol-[\w-]+|sk3d(?:-[\w-]+)?|lanes-[\w-]+|pal-[\w-]+|bldg-[\w-]+|wpal-[\w-]+)(?![\w-])|\.(node|node-[\w-]+|unit-bar|phase-[\w-]+|edge[\w-]*|detail-[\w-]+|mobile-featured)(?![\w-])|(^|[\s>+~])mark(?![\w-])/;
var done=typeof WeakSet==='function' ? new WeakSet() : null, extra=[];
function parts(s){ var o=[], d=0, b=0; for(var i=0;i<s.length;i++){ var c=s[i]; if(c==='('||c==='[') d++; else if(c===')'||c===']') d--; else if(c===','&&!d){ o.push(s.slice(b,i)); b=i+1; } } o.push(s.slice(b)); return o; }
function rules(list, wrap){
  for(var i=0;i<list.length;i++){ var r=list[i];
    if(r.cssRules && r.selectorText==null){ var c=r.media ? '@media '+r.media.mediaText : r.conditionText!=null ? '@supports '+r.conditionText : null;
      if(c) rules(r.cssRules, (wrap||'')+c+'{'); continue; }
    if(r.selectorText==null || r.selectorText.indexOf('mobile')<0) continue;
    var ps=parts(r.selectorText), copy=[], off=false;
    for(var k=0;k<ps.length;k++){ var s=ps[k];
      if(BOARD.test(s)) continue;
      if(/:not\(\.mobile\)/.test(s)){ ps[k]=s.replace(/:not\(\.mobile\)/g, ':not(.mobile):not(.phone-whole)'); off=true; }
      else if(/\.mobile(?![\w-])/.test(s)) copy.push(s.replace(/\.mobile(?![\w-])/g, '.phone-whole')); }
    if(off) try{ r.selectorText=ps.join(','); }catch(e){}
    if(copy.length){ var css=copy.join(',')+'{'+r.style.cssText+'}'; if(wrap) css=wrap+css+new Array(wrap.split('{').length).join('}'); extra.push(css); }
  }
}
function remap(){
  [].forEach.call(document.styleSheets, function(sh){ if(done && done.has(sh)) return; var n=sh.ownerNode; if(n && n.id==='alto-phone-chrome') return;
    var list; try{ list=sh.cssRules; }catch(e){ return; } if(done) done.add(sh); rules(list, ''); });
  if(!extra.length) return;
  var st=document.getElementById('alto-phone-chrome'); if(!st){ st=document.createElement('style'); st.id='alto-phone-chrome'; }
  st.textContent+=extra.join('\n')+'\n'; extra=[]; document.head.appendChild(st);           /* last in <head>: after the phone design's own */
}
function swap(v){ try{ sessionStorage.setItem(KEY+':'+location.pathname, v); }catch(e){} location.reload(); }
/* a timeline or an outline seen whole: "One card" in the MENU drawer, where "Whole view" stood (phone.py CARD_JS) */
function cardsBtn(){
  var b=document.getElementById('nav-drawer-body'); if(!CAN || !b) return; var x=document.getElementById('drawer-view-btn');
  if(!x){ x=document.createElement('button'); x.id='drawer-view-btn'; x.type='button'; x.className='drawer-btn';
    x.innerHTML='<span class="drawer-icon"><svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="4.5" y="2.5" width="11" height="15" rx="2"/><path d="M7.5 7h5M7.5 10h5M7.5 13h3"/></svg></span><span class="drawer-label">One card</span>';
    x.onclick=function(){ swap('card'); }; }
  var a=document.getElementById('drawer-scene-btn')||document.getElementById('drawer-mode-btn');
  if(a && a.parentNode){ if(a.nextSibling!==x) a.parentNode.insertBefore(x, a.nextSibling); } else if(x.parentNode!==b) b.appendChild(x);
}
/* the desktop gathers NOTES and FILTER into its side rail (filter_panel.RAIL_GLUE); on a phone they are corner tiles */
function unrail(){
  var r=document.getElementById('tab-rail'), app=document.getElementById('app')||document.body; if(!r) return;
  ['notes-toggle','filter-toggle'].forEach(function(id){ var b=document.getElementById(id); if(b && b.parentNode===r) (id==='notes-toggle' ? app : document.body).appendChild(b); });
}
/* the MENU drawer as a phone has it: Dark / Light straight under Overview, no "Appearance" label (the engine's
   upgradeDrawer, in a phone-only script), and Scene under Dark / Light (backgrounds.py adds it only to html.mobile) */
function drawer(){
  var b=document.getElementById('nav-drawer-body'); if(!b) return;
  var ov=null; [].forEach.call(b.querySelectorAll('.drawer-btn'), function(x){ if((x.getAttribute('onclick')||'').indexOf('toggleSummary')>=0) ov=x; });
  [].forEach.call(b.querySelectorAll('.drawer-section-label'), function(l){ if((l.textContent||'').trim()==='Appearance') l.remove(); });
  var dm=document.getElementById('drawer-mode-btn'); if(dm && ov && ov.nextSibling!==dm) ov.parentNode.insertBefore(dm, ov.nextSibling);
  var bg=document.getElementById('bg-toggle'), sb=document.getElementById('drawer-scene-btn');
  if(bg && dm && !sb){ sb=document.createElement('button'); sb.id='drawer-scene-btn'; sb.type='button'; sb.className='drawer-btn';
    var ic=bg.querySelector('svg'); sb.innerHTML='<span class="drawer-icon">'+(ic ? ic.outerHTML.replace(/width="\d+" height="\d+"/, 'width="20" height="20"') : '')+'</span><span class="drawer-label">Scene</span>';
    sb.addEventListener('click', function(e){ e.stopPropagation(); if(window.closeNavDrawer) window.closeNavDrawer(); setTimeout(function(){ bg.click(); }, 0); }); }
  if(sb && dm && sb.previousElementSibling!==dm) dm.parentNode.insertBefore(sb, dm.nextSibling);
}
function build(){
  if(!on() || !document.body) return;
  remap(); unrail(); drawer(); cardsBtn(); wrapFocus(); de.classList.add('ph-ready');
}
function fit(){ if(on() && fmt()==='tl' && !detail()){ var s=fitS(), c=cv(); if(s<.999 && c){ var r=c.getBoundingClientRect(); ovSet(Math.max(s, START), r.left, r.top); c.scrollLeft=0; c.scrollTop=0; } } }
document.addEventListener('DOMContentLoaded', function(){ build(); });
window.addEventListener('load', function(){ build(); fit(); setTimeout(build, 900); });
window.addEventListener('resize', function(){ if(OV.s<1) ovSet(OV.s); });
window._altoPhone={on:on, fmt:fmt, ov:OV, ovSet:ovSet, zoomBy:zoomBy, build:build, swap:swap, remap:remap};
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


def head_block(mode: str) -> str:
    """The <script> for <head>, ahead of the engine's own (builder.phone_mode): "whole" for a System or a horizontal
    timeline (whole on every phone), "card" for a timeline or an outline (the phone design, the whole view on request),
    nothing for a Memory Palace (the phone design as it always was)."""
    if mode == "phone":
        return ""
    from .palace_assets import loader
    js = (HEAD_JS.replace("__FORCE__", "1" if mode == "whole" else "0").replace("__KEY__", KEY)
          .replace("__GUARD__", GUARD).replace("__LOAD__", loader(PATH, GUARD)))
    return '<script id="alto-phone-head">' + js + "</script>"


# The engine's phone scripts (the phone design: its tiles, MENU drawer, MAP list, search pill, header brand). On a page
# seen whole they run inside a window where the page is html.mobile, so they build what they always built; the class
# is gone again before the desktop's own scripts run. Every other script sees the page as it is.
PHONE_SCRIPTS = ("<script>\n(function(){\n  if(!document.documentElement.classList.contains('mobile')) return;\n  // ── Inject mobile",
                 '<script id="alto-mobile-brand">', '<script id="alto-search-mobile">')
_ON = "<script>window._altoPhoneWhole&&document.documentElement.classList.add('mobile');</script>"
_OFF = "<script>window._altoPhoneWhole&&document.documentElement.classList.remove('mobile');</script>"


# The engine's phone script also lays the cards out for one-card reading and steps between them; on a page seen whole the
# board is the desktop's, so those parts stand aside there (and only there): the one-card layout (MAP's list keeps its
# names and colours), the "always start in focus" class, and featuring a card, which becomes the desktop's own landing on it (window._altoSearch.land, the way
# search goes to a card) when a tap asks for it (MAP's list, the chips; a swipe or the page's own start asks nothing).
_CARD_PARTS = (
    ("    if(_origInitLayout) _origInitLayout.apply(this, arguments);\n",
     "    if(_origInitLayout) _origInitLayout.apply(this, arguments);\n"
     "    if(window._altoPhoneWhole){ if(typeof NODES !== 'undefined') window._minimapNodeData = NODES.map(function(n){\n"
     "      return {id: n.id, color: (typeof hex === 'function') ? hex(n.color) : '#a78bfa', title: n.title || n.id}; }); return; }\n"),
    ("  function featureNode(nodeId, animate){\n",
     "  function featureNode(nodeId, animate){\n"
     "    if(window._altoPhoneWhole){ if(animate===true && window._altoSearch && window._altoSearch.land) window._altoSearch.land(nodeId); return; }\n"),
    ("    var ok = !!window._featuredNodeId;\n",
     "    var ok = !!window._featuredNodeId || !!window._altoPhoneWhole;   // (the whole view features no card)\n"),
    ("    _focusMode = true;\n    document.documentElement.classList.add('focus-mode');",
     "    _focusMode = !window._altoPhoneWhole;\n    if(_focusMode) document.documentElement.classList.add('focus-mode');"),
)


def phone_scripts(html: str) -> str:
    """Each of PHONE_SCRIPTS between _ON and _OFF (a page whose phone opens the whole view or offers it), with the
    engine phone script's card parts standing aside on the whole view (_CARD_PARTS)."""
    for mark in PHONE_SCRIPTS:
        i = html.find(mark)
        if i < 0:
            if mark is PHONE_SCRIPTS[0]:
                raise ValueError("phone.phone_scripts: the engine's phone script is not in the page")
            continue
        j = html.index("</script>", i) + len("</script>")
        body = html[i:j]
        if mark is PHONE_SCRIPTS[0]:
            for old, new in _CARD_PARTS:
                if body.count(old) != 1:
                    raise ValueError("phone.phone_scripts: the engine phone script changed near " + old.strip()[:40])
                body = body.replace(old, new)
        html = html[:i] + _ON + body + _OFF + html[j:]
    return html


def card_block(mode: str) -> str:
    """The MENU drawer's "Whole view" (a timeline or an outline only)."""
    return "<script>" + CARD_JS.replace("__KEY__", KEY) + "</script>\n" if mode == "card" else ""
