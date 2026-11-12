"""Holographic: the "Alto" wordmark traced by light on a loop (Luke, 2026-11-05: "in holo, Alto logo didn't get an animation, just the glyph. Alto logo should sort of
be traced by a holo on loop as opposed to spinning"; Art's look, ORG/notes-art/holo-wordmark-trace.md).

Once every 7 s a short cyan-white bead runs along the OUTLINES of the letters A, l, t, o, left to right, a wider magenta ghost just behind it (the corner clef's own
magenta); then the wordmark rests, lit and still, for 4.2 s. No spin, no scale, nothing on the letters' fill or glow. The clef keeps its 3D turn.

How: a second, empty `<svg class="ho-trace">` is set right after each `svg.brand-word`, in the same place, and holds two stroked copies of the wordmark's contours
(the hosted script reads the wordmark's own `d` at run time: the page holds nothing). Two clones are stroked with a short dash that slides along each contour
(`stroke-dashoffset`), the ghost 0.12 s behind. The overlay is a separate element, never inside the wordmark: that svg carries `filter:drop-shadow`, and anything moving
inside a filtered element re-runs the filter every frame. No filter, blur, shadow, mask or gradient on the moving part; the glow is the ghost's wider stroke.
A contour is dashed from its own start, so the wordmark's six contours (A, A's counter, l, t, o, o's counter) are separate paths, each with its own start time in the 7 s
loop, laid end to end in proportion to their length (the bead runs at one speed on every letter).

Where it is: every page that shows the wordmark in Holographic (the homepage, a timeline, the reports page), a phone's too (in its header, top right). Not drawn when
the wordmark is not (the reports page hides it at phone width), when Reduce Motion is on (and removed live if it comes on), or in print.
"""
from __future__ import annotations

import json as _json

COLOURS = {   # (Art) dark core / ghost; the light theme (a phone in light mode) has a deep teal pair so a white bead does not vanish on a pale page
    "dark": ("#e8fffd", "rgb(255,95,210)", ".95", ".45"),
    "light": ("#12b5d6", "rgb(214,40,170)", ".95", ".35"),
}
LOOP = 7           # seconds
SWEEP = 40         # percent of the loop the bead is moving (2.8 s)
CORE = 0.06        # bead length, share of the whole outline
GHOST = 0.10
DELAY = 0.12       # seconds the ghost trails

CSS = (
    ".ho-trace{display:block;overflow:visible;position:absolute;grid-row:1/2;align-self:center;justify-self:end;width:auto;margin:0;will-change:transform}"   # (its own layer: a pass repaints only the wordmark's own box, not the blurred bar)
    ".ho-trace,.ho-trace *{pointer-events:none !important}"
    ".ho-trace path{fill:none;stroke-linecap:butt;stroke-linejoin:round}"
    ".ho-trace .tg{stroke:%s;stroke-opacity:%s;stroke-width:5}"
    ".ho-trace .tc{stroke:%s;stroke-opacity:%s;stroke-width:3.5}"
    "html.dark .ho-trace .tg{stroke:%s;stroke-opacity:%s}"
    "html.dark .ho-trace .tc{stroke:%s;stroke-opacity:%s}"
    "@media (prefers-reduced-motion:reduce){.ho-trace{display:none !important}}"
    "@media print{.ho-trace{display:none !important}}html.printing .ho-trace{display:none !important}"
) % (COLOURS["light"][1], COLOURS["light"][3], COLOURS["light"][0], COLOURS["light"][2],
     COLOURS["dark"][1], COLOURS["dark"][3], COLOURS["dark"][0], COLOURS["dark"][2])

# Part 2 (Luke, 2026-11-05: "can we make the holo animation i described do the same thing for nodes along their borders?"): the same trace on a card's border, the same
# cyan-white bead and magenta ghost, the same 7 s loop with its 2.8 s pass, each card at its own point of the loop (--p) so they never pulse in unison.
# Measured (headed WebKit): an animated stroke (stroke-dashoffset) on a card costs the page a fixed ~6 points of one core per frame whether it is one card or forty-four
# (it repaints the board's connector layer under it), and 30 points when it is not on its own layer. So the card's bead is four thin strips on its border, each carrying
# one bead that slides by `transform` alone (the compositor's, no repaint, no main-thread frame): one root per card, four moving children.
NODE_MODE = "full"     # full: every card, always | view: only cards on screen | walk: the hovered and chosen card, plus one idle pass walking from card to card
CAP = 80               # cards traced at most (a board of hundreds keeps the first 80 in page order); measured +3 points of a core for 44 cards
LEAD = 130             # px of painted bead and ghost behind the head (the element is this much longer than its edge, so one translate walks the bead on and off)
NODE_CSS = (
    ".ho-nt{position:absolute;left:-3px;top:-4px;right:-3px;bottom:-3px;overflow:hidden;z-index:2;--hn-c:#12b5d6;--hn-g:rgba(214,40,170,.4)}"
    "html.dark .ho-nt{--hn-c:#e8fffd;--hn-g:rgba(255,95,210,.55)}"
    ".ho-nt,.ho-nt *{pointer-events:none !important}"
    ".ho-nt i{position:absolute;display:block;will-change:transform}"
    ".ho-nt .t,.ho-nt .b{height:5px;width:calc(100%% + %dpx);"
    "background:linear-gradient(var(--hn-c),var(--hn-c)) var(--hn-d) top 50%% / 64px 2px no-repeat,linear-gradient(var(--hn-g),var(--hn-g)) var(--hn-d2) top 50%% / 104px 4px no-repeat}"
    ".ho-nt .l,.ho-nt .r{width:5px;height:calc(100%% + %dpx);"
    "background:linear-gradient(var(--hn-c),var(--hn-c)) left 50%% var(--hn-d) / 2px 64px no-repeat,linear-gradient(var(--hn-g),var(--hn-g)) left 50%% var(--hn-d2) / 4px 104px no-repeat}"
    ".ho-nt .t{top:.5px;left:0;--hn-d:right 0px;--hn-d2:right 24px}.ho-nt .b{bottom:0;left:-%dpx;--hn-d:left 0px;--hn-d2:left 24px}"
    ".ho-nt .r{right:0;top:0;--hn-d:bottom 0px;--hn-d2:bottom 24px}.ho-nt .l{left:0;top:-%dpx;--hn-d:top 0px;--hn-d2:top 24px}"
    # (rel-223 study_plan, phone on its side with Safari's tab strip up): there the one card is a scroller (engine_patches _LS_NEW: overflow-y:auto, capped
    # height) and the root's -3/-4 px overhang gave it 3 px of scroll. In that card the root sits on the padding box (inset 0) and each strip moves out by the
    # same overhang and grows by it, so every strip and bead stays where it was on the screen; the card's own clip at the padding box was the clip already.
    "@media (orientation:landscape) and (max-height:340px){html.mobile.focus-mode .node.mobile-featured .node-card>.ho-nt{left:0;top:0;right:0;bottom:0}"
    "html.mobile.focus-mode .node.mobile-featured .node-card>.ho-nt .t,html.mobile.focus-mode .node.mobile-featured .node-card>.ho-nt .b{width:calc(100%% + %dpx)}"
    "html.mobile.focus-mode .node.mobile-featured .node-card>.ho-nt .l,html.mobile.focus-mode .node.mobile-featured .node-card>.ho-nt .r{height:calc(100%% + %dpx)}"
    "html.mobile.focus-mode .node.mobile-featured .node-card>.ho-nt .t{top:-3.5px;left:-3px}html.mobile.focus-mode .node.mobile-featured .node-card>.ho-nt .b{bottom:-3px;left:-%dpx}"
    "html.mobile.focus-mode .node.mobile-featured .node-card>.ho-nt .r{right:-3px;top:-4px}html.mobile.focus-mode .node.mobile-featured .node-card>.ho-nt .l{left:-3px;top:-%dpx}}"
    ".node.dimmed .ho-nt,.compass-mini-node .ho-nt{display:none}"
    "html.hp-hid .ho-nt{visibility:hidden}"
    "@media (prefers-reduced-motion:reduce){.ho-nt{display:none !important}}"
    "@media print{.ho-nt{display:none !important}}html.printing .ho-nt{display:none !important}"
) % (LEAD, LEAD, LEAD, LEAD, LEAD + 6, LEAD + 7, LEAD + 3, LEAD + 4)

NODE_JS = r"""
var NT={on:null,mo:null,io:null,n:0,walk:0,wcur:null,raf:0}, NTM='__NTMODE__', NTL=__NTLEAD__;
function ntHas(c){ return c.querySelector(':scope > .ho-nt'); }
function ntAdd(c,once){
  var s=ntHas(c); if(s) return s;
  var W=c.offsetWidth, H=c.offsetHeight; if(!W||!H) return null;
  s=document.createElement('div'); s.className='ho-nt'; s.setAttribute('aria-hidden','true');
  var E=[['t',W,'translateX(-100%)','translateX(0)'],['r',H,'translateY(-100%)','translateY(0)'],['b',W,'translateX(100%)','translateX(0)'],['l',H,'translateY(100%)','translateY(0)']];
  var per=2*(W+H), v=per/2.8/1000, ph=((NT.n++)*0.6180339887)%1, loop=7000, S=0, last=null;
  c.appendChild(s);
  E.forEach(function(e){
    var i=document.createElement('i'); i.className=e[0]; s.appendChild(i);
    var dur=(e[1]+NTL)/v, a;
    if(once) a=i.animate([{transform:e[2]},{transform:e[3]}], {duration:dur, delay:S/v, easing:'linear', fill:'both'});
    else { var o0=S/v/loop, o1=Math.min(.999,(S/v+dur)/loop);
      a=i.animate([{offset:0,transform:e[2]},{offset:o0,transform:e[2]},{offset:o1,transform:e[3]},{offset:1,transform:e[3]}], {duration:loop, delay:-ph*loop, iterations:Infinity, easing:'linear'}); }
    S+=e[1]; last=a;
  });
  if(once && last) last.onfinish=function(){ if(s.parentNode) s.parentNode.removeChild(s); if(NT.on && NTM==='walk') NT.walk=setTimeout(ntWalk, 1500); };
  return s;
}
function ntDrop(c){ var s=ntHas(c); if(s) s.parentNode.removeChild(s); }
function ntCards(){ return [].slice.call(document.querySelectorAll('.node-card')).filter(function(c){ return !c.closest('.compass-mini-node'); }).slice(0,__NTCAP__); }
function ntOnscreen(c){ var b=c.getBoundingClientRect(); return b.width>0 && b.bottom>60 && b.top<innerHeight && b.right>0 && b.left<innerWidth; }
function ntScan(){
  NT.raf=0; if(!NT.on) return;
  if(NTM==='full') ntCards().forEach(function(c){ ntAdd(c); });
  else if(NTM==='view' && NT.io) ntCards().forEach(function(c){ if(!c._hoV){ c._hoV=1; NT.io.observe(c); } });
}
function ntWalk(){
  NT.walk=0; if(!NT.on || NTM!=='walk') return;
  var keep=[].slice.call(document.querySelectorAll('.node.focused .node-card, .node-card:hover'));
  [].forEach.call(document.querySelectorAll('.ho-nt'), function(s){ if(keep.indexOf(s.parentNode)<0 && !s._once) s.parentNode.removeChild(s); });
  keep.forEach(function(c){ ntAdd(c); });
  var all=ntCards().filter(ntOnscreen), c=null, i;
  if(all.length){ i=NT.wcur ? all.indexOf(NT.wcur) : -1; c=all[(i+1)%all.length]; }
  if(c && !ntHas(c)){ NT.wcur=c; var s=ntAdd(c,true); if(s) s._once=1; else NT.walk=setTimeout(ntWalk, 1500); }
  else NT.walk=setTimeout(ntWalk, 1500);
}
function ntHover(){ if(NT.on && NTM==='walk' && !NT.walk) NT.walk=setTimeout(ntWalk, 0); }
function ntSync(on){
  NT.on=on;
  if(on) return;
  [].forEach.call(document.querySelectorAll('.ho-nt'), function(s){ s.parentNode.removeChild(s); });
  if(NT.mo){ NT.mo.disconnect(); NT.mo=null; } if(NT.io){ NT.io.disconnect(); NT.io=null; } if(NT.walk){ clearTimeout(NT.walk); NT.walk=0; }
  [].forEach.call(document.querySelectorAll('.node-card'), function(c){ c._hoV=0; }); document.removeEventListener('pointerover', ntHover, true);
}
function ntStart(){
  if(!NT.on) return;
  var w=document.getElementById('world');
  if(!w || !w.querySelector('.node-card')) return;
  if(NTM==='view' && !NT.io && typeof IntersectionObserver==='function')
    NT.io=new IntersectionObserver(function(es){ es.forEach(function(e){ if(e.isIntersecting) ntAdd(e.target); else ntDrop(e.target); }); }, {rootMargin:'120px'});
  if(NTM!=='walk' && !NT.mo && typeof MutationObserver==='function'){
    NT.mo=new MutationObserver(function(ms){ if(NT.raf) return; for(var i=0;i<ms.length;i++) if(ms[i].addedNodes.length && !(ms[i].target.closest && ms[i].target.closest('.ho-nt'))){ NT.raf=requestAnimationFrame(ntScan); return; } });
    NT.mo.observe(w,{childList:true,subtree:true});
  }
  if(NTM==='walk'){ document.addEventListener('pointerover', ntHover, true); if(!NT.walk) NT.walk=setTimeout(ntWalk, 600); }
  ntScan();
}
"""

# Part 3 (Luke, 2026-11-05: "can you make the alto glyph in holo a little more 3d as it rotates, making it tubular"): the corner glyph is a tube. A flat cut-out turned in
# CSS thins to nothing edge-on, because its strokes squash with it; a round tube keeps its thickness from every side. So the glyph is built as a stack of thin slices
# (the page's own clef, read at run time, drawn again for each slice) standing at different depths inside one turning box (CSS 3D, preserve-3d): each slice is the clef
# stroked at the width a round pipe has at that depth, w*sqrt(1 - (z/r)^2) (every stroke gets the same depth, so the thin stem and the curls shade alike), the middle slice the widest and darkest (the rim), the outer ones narrow and bright (the core
# and the gloss). Seen face-on the stack is a round neon pipe; turning, the narrow bright slices slide across the dark ones (the highlight moves with the turn) and the
# stack's depth shows as the glyph goes edge-on, a bar of the pipe's own thickness. The turn is one transform on one box (the compositor's, as the old turn was): no
# script runs per frame. A dark back slice and a magenta one carry the glow and the ghost the old glyph had. Reduce Motion: the box stands at the old 24 degrees, shaded
# the same; print: face-on.
TUBE_RHO = 3.6                                  # glyph units: half the widest stroke (7.2)
TUBE_T = (-.9, -.675, -.45, -.225, 0, .225, .45, .675, .9)     # the slices, as shares of the radius (the outermost just inside the widest stroke's own radius)
TUBE_C = {   # |t| 0 .. 1 : the rim, the body, the core, the gloss (dark page / pale page)
    "dark": ("#0b6a70", "#27d2c4", "#8ffcf2", "#f2fffe"),
    "light": ("#04485a", "#0a7a96", "#2aa5c4", "#d8f7ff"),
}


def _lerp(a: str, b: str, k: float) -> str:
    x = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    y = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join("%02x" % round(p + (q - p) * k) for p, q in zip(x, y))


def _tone(theme: str, m: float) -> str:
    c = TUBE_C[theme]
    return _lerp(c[0], c[1], m / .5) if m < .5 else _lerp(c[1], c[2], (m - .5) / .3) if m < .8 else _lerp(c[2], c[3], (m - .8) / .2)


_Q = sorted({abs(t) for t in TUBE_T})
TUBE_CSS = (
    ".ho-tube{display:block;position:absolute;margin:0;pointer-events:none !important;grid-row:1/2;align-self:center;justify-self:start;--u:.43px}"
    ".ho-tube *{pointer-events:none !important}"
    ".ho-tube .sp{position:absolute;left:0;top:0;width:100%;height:100%;transform-style:preserve-3d;animation:ho-tube 10s ease-in-out -2.5s infinite;will-change:transform}"
    "@keyframes ho-tube{0%,100%{transform:perspective(260px) rotateY(-55deg)}50%{transform:perspective(260px) rotateY(55deg)}}"      # the clef's swing (holo.py ho-logo): never edge-on
    ".ho-tube svg{position:absolute;left:0;top:0;width:100%;height:100%;overflow:visible}"
    ".ho-tube g{fill:none;stroke-linecap:round;stroke-linejoin:round}"
    ".ho-tube .gl g{stroke:rgba(79,240,224,.2)}.ho-tube .gh g{stroke:rgba(255,95,210,.5)}"
    "html:not(.dark) .ho-tube .gl g{stroke:rgba(10,111,140,.18)}html:not(.dark) .ho-tube .gh g{stroke:rgba(214,40,170,.4)}"
    + "".join(".ho-tube .q%d g{stroke:%s}.ho-tube .q%d .hd{fill:%s}html:not(.dark) .ho-tube .q%d g{stroke:%s}html:not(.dark) .ho-tube .q%d .hd{fill:%s}" %
              (i, _tone("dark", m / _Q[-1]), i, _tone("dark", m / _Q[-1]), i, _tone("light", m / _Q[-1]), i, _tone("light", m / _Q[-1])) for i, m in enumerate(_Q))
    + "html.hp-hid .ho-tube .sp{animation-play-state:paused}"
    "@media (prefers-reduced-motion:reduce){.ho-tube .sp{animation:none;transform:perspective(260px) rotateY(24deg)}}"
    "@media print{.ho-tube .sp{animation:none;transform:none}}"
)

TUBE_JS = r"""
var TBT=__TBT__, TBR=__TBR__, TBE=TBR/0.95;
function tbRead(mark){
  var ink=mark.querySelector('.alto-ink'), head=mark.querySelector('.alto-head'), out=[], tx=0;
  if(!ink) return null;
  var tr=ink.parentNode.getAttribute('transform')||'', m=tr.match(/translate\(\s*(-?[\d.]+)[ ,]+(-?[\d.]+)/); if(m) tx=+m[1];
  [].forEach.call(ink.querySelectorAll('path'), function(p){
    var wEl=p.closest('[stroke-width]'); out.push({d:p.getAttribute('d'), w:+(p.getAttribute('stroke-width') || (wEl && wEl.getAttribute('stroke-width')) || 6)});
  });
  if(head) out.push({d:head.getAttribute('d'), w:+(head.getAttribute('stroke-width')||2.9), head:true});
  return {paths:out, tx:tx};
}
function tbSlice(geo, cls, zu, wf, extra){
  var s=document.createElementNS(TRNS,'svg'), g=document.createElementNS(TRNS,'g'), n=0;
  s.setAttribute('class',cls); s.setAttribute('viewBox', geo.vb); s.style.transform='translateZ(calc(var(--u) * '+zu+'))';
  g.setAttribute('transform','translate('+(geo.tx+(extra||0))+' 0)');
  geo.paths.forEach(function(o){
    var w=wf(o.w); if(!(w>0.05)) return;
    var p=document.createElementNS(TRNS,'path'); p.setAttribute('d',o.d); p.setAttribute('stroke-width', w.toFixed(2)); if(o.head) p.setAttribute('class','hd'); g.appendChild(p); n++;
  });
  s.appendChild(g); return n ? s : null;
}
function tbMake(mark){
  var geo=tbRead(mark); if(!geo) return null; geo.vb=mark.getAttribute('viewBox')||'26 15 78 98';
  var s=document.createElement('div'), sp=document.createElement('div'), Q=[];
  TBT.forEach(function(t){ if(Q.indexOf(Math.abs(t))<0) Q.push(Math.abs(t)); }); Q.sort(function(a,b){ return a-b; });
  s.className='ho-tube'; s.setAttribute('aria-hidden','true'); sp.className='sp'; s.appendChild(sp);
  var add=function(x){ if(x) sp.appendChild(x); };
  add(tbSlice(geo,'gl',-TBR*1.5,function(w){ return w*1.9; }));
  add(tbSlice(geo,'gh',-TBR*1.2,function(w){ return w; },-3.2));
  TBT.forEach(function(t){
    add(tbSlice(geo,'q'+Q.indexOf(Math.abs(t)), t*TBR, function(w){ var q=Math.abs(t)*TBR/TBE; return w*Math.sqrt(1-q*q); }));
  });
  return s;
}
function tbSync(on){
  var marks=[].slice.call(document.querySelectorAll('svg.brand-mark'));
  if(!on){
    [].forEach.call(document.querySelectorAll('.ho-tube'), function(n){ n.parentNode.removeChild(n); });
    marks.forEach(function(m){ m._hoK=null; ['opacity','animation','will-change','filter'].forEach(function(p){ m.style.removeProperty(p); }); });
    return;
  }
  marks.forEach(function(m){
    var s=m._hoK;
    if(getComputedStyle(m).display==='none' || !m.getClientRects().length){ if(s && s.parentNode) s.parentNode.removeChild(s); m._hoK=null; return; }
    if(s && (s.previousSibling!==m || !s.parentNode)){ if(s.parentNode) s.parentNode.removeChild(s); s=m._hoK=null; }
    if(!s){ s=tbMake(m); if(!s) return; m.parentNode.insertBefore(s, m.nextSibling); m._hoK=s; }
    var abs=getComputedStyle(m).position==='absolute';
    trPlace(m,s); s.style.width=getComputedStyle(m).width; s.style.transform=abs ? 'translateY(-50%)' : '';
    s.style.setProperty('--u', (parseFloat(s.style.height)/98)+'px');
    ['opacity:0','animation:none','will-change:auto','filter:none'].forEach(function(a){ var k=a.split(':'); m.style.setProperty(k[0],k[1],'important'); });
  });
}
"""

WORD_JS = r"""
var TR={on:null,h:null,css:null,kf:false,mo:null,rz:0,t:0,plan:null,anims:[]}, TRNS='http://www.w3.org/2000/svg';
function trLive(){ return r.classList.contains('alto-holo') && !(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches); }
function trMake(word){
  var src=word.querySelector('.alto-word'), parts=src ? (src.getAttribute('d')||'').match(/M[^M]*/g) : null;
  if(!parts || !parts.length) return null;
  var s=document.createElementNS(TRNS,'svg'); s.setAttribute('class','ho-trace'); s.setAttribute('aria-hidden','true'); s.setAttribute('focusable','false'); s.setAttribute('viewBox', word.getAttribute('viewBox')||'');
  ['tg','tc'].forEach(function(k){ parts.forEach(function(d,i){ var p=document.createElementNS(TRNS,'path'); p.setAttribute('class',k+' c'+i); p.setAttribute('d',d); s.appendChild(p); }); });
  return s;
}
function trKeys(s){
  var P=[].slice.call(s.querySelectorAll('.tc')), L=P.map(function(p){ return p.getTotalLength(); }), tot=0, i;
  for(i=0;i<L.length;i++) tot+=L[i];
  if(!(tot>0)) return false;
  var dc=tot*__CORE__, dg=tot*__GHOST__, S=0, cum=0, css='', f=function(x){ return +x.toFixed(3); }, loop=__LOOP__, sweep=loop*__SWEEP__/100, plan=[];
  for(i=0;i<L.length;i++) S+=L[i]+dc;
  for(i=0;i<L.length;i++){
    var s0=sweep*cum/S, s1, k;
    cum+=L[i]+dc; s1=sweep*cum/S; k=(s1-s0)/(L[i]+dc);
    plan.push({i:i, s:s0, d:s1-s0, g:Math.min(loop-s0-200,(L[i]+dg)*k), from:f(dc+1), gfrom:f(dg+1), to:f(-L[i]*1.08-Math.max(dc,dg)-1)});
    css+='.ho-trace .tc.c'+i+'{stroke-dasharray:'+f(dc)+' 9999;stroke-dashoffset:'+f(dc+1)+'}'
       + '.ho-trace .tg.c'+i+'{stroke-dasharray:'+f(dg)+' 9999;stroke-dashoffset:'+f(dg+1)+'}';
  }
  TR.plan=plan; TR.css.appendChild(document.createTextNode(css)); TR.kf=true; return true;
}
function trStop(){ if(TR.t){ clearTimeout(TR.t); TR.t=0; } TR.anims.forEach(function(a){ try{ a.cancel(); }catch(e){} }); TR.anims=[]; }
function trPass(){
  TR.t=0; TR.anims.forEach(function(a){ try{ a.cancel(); }catch(e){} }); TR.anims=[];
  if(!TR.on || !TR.plan) return;
  if(!document.hidden && !r.classList.contains('hp-hid')){
    [].forEach.call(document.querySelectorAll('svg.ho-trace'), function(s){
      if(!s.parentNode || s.style.display==='none') return;
      TR.plan.forEach(function(q){
        var c=s.querySelector('.tc.c'+q.i), g=s.querySelector('.tg.c'+q.i);
        if(c) TR.anims.push(c.animate([{strokeDashoffset:String(q.from)},{strokeDashoffset:String(q.to)}], {delay:q.s, duration:q.d, easing:'steps('+Math.max(1,Math.round(q.d/50))+',end)', fill:'backwards'}));
        if(g) TR.anims.push(g.animate([{strokeDashoffset:String(q.gfrom)},{strokeDashoffset:String(q.to)}], {delay:q.s+__DELAY__, duration:q.g, easing:'steps('+Math.max(1,Math.round(q.g/50))+',end)', fill:'backwards'}));
      });
    });
  }
  TR.t=setTimeout(trPass, __LOOP__);
}
function trPlace(word,s){
  var cs=getComputedStyle(word), st=s.style, i, n=0, kids, k, ck;
  if(cs.display==='none' || !word.getClientRects().length){ st.display='none'; return false; }
  st.display=''; st.height=cs.height;
  if(cs.position==='absolute' || cs.position==='fixed'){
    ['top','right','bottom','left','transform','zIndex'].forEach(function(p){ st[p]=cs[p]; });
    st.gridColumn=''; st.gridRow='';
  } else {
    kids=word.parentNode.children;
    for(i=0;i<kids.length;i++){ if(kids[i]===word) break; ck=getComputedStyle(kids[i]); if(kids[i]!==s && ck.display!=='none' && ck.position!=='absolute' && ck.position!=='fixed') n++; }
    st.gridColumn=(n+1)+' / '+(n+2); st.gridRow='1 / 2'; st.justifySelf=cs.justifySelf; st.alignSelf=cs.alignSelf;
    ['top','right','bottom','left','transform'].forEach(function(p){ st[p]=''; });
  }
  return true;
}
function trSync(){
  var hol=r.classList.contains('alto-holo'), on=trLive(), words=[].slice.call(document.querySelectorAll('svg.brand-word'));
  TR.on=on; TR.h=hol;
  if(!hol){ [].forEach.call(document.querySelectorAll('svg.ho-trace'), function(n){ n.parentNode.removeChild(n); }); words.forEach(function(w){ w._hoT=null; }); trStop(); ntSync(false); tbSync(false); return; }
  if(!TR.css){ TR.css=document.createElement('style'); TR.css.id='alto-holo-trace'; TR.css.appendChild(document.createTextNode(__TRCSS__)); (document.head||r).appendChild(TR.css); }
  if(!on){ [].forEach.call(document.querySelectorAll('svg.ho-trace'), function(n){ n.parentNode.removeChild(n); }); words.forEach(function(w){ w._hoT=null; }); trStop(); ntSync(false); tbSync(true); return; }
  var fresh=false;
  words.forEach(function(w){
    var s=w._hoT;
    if(getComputedStyle(w).display==='none' || !w.getClientRects().length){ if(s && s.parentNode) s.parentNode.removeChild(s); w._hoT=null; return; }
    if(s && (s.previousSibling!==w || !s.parentNode)){ if(s.parentNode) s.parentNode.removeChild(s); s=w._hoT=null; }
    if(!s){ s=trMake(w); if(!s) return; w.parentNode.insertBefore(s, w.nextSibling); w._hoT=s; fresh=true; }
    if(trPlace(w,s) && !TR.kf) trKeys(s);
  });
  if(fresh){ trStop(); trPass(); }
  ntSync(true); ntStart(); tbSync(true);
}
function trWatch(){
  if(TR.mo || typeof MutationObserver!=='function') return;
  TR.mo=new MutationObserver(function(){ if(TR.on!==trLive() || TR.h!==r.classList.contains('alto-holo')) trSync(); });
  TR.mo.observe(r,{attributes:true,attributeFilter:['class']});
  var late=function(){ if(r.classList.contains('alto-holo')) trSync(); };
  window.addEventListener('resize', function(){ if(TR.rz) return; TR.rz=setTimeout(function(){ TR.rz=0; late(); }, 150); });
  window.addEventListener('load', function(){ setTimeout(late, 300); });
  window.addEventListener('pageshow', late);
  try{ var mq=matchMedia('(prefers-reduced-motion: reduce)'); if(mq.addEventListener) mq.addEventListener('change', trSync); else if(mq.addListener) mq.addListener(trSync); }catch(e){}
  if(r.classList.contains('alto-holo')){ trSync(); TR.t=setTimeout(late, 1200); }
}
document.addEventListener('visibilitychange', function(){ if(r.classList.contains('alto-holo')) TR.anims.forEach(function(a){ try{ if(document.hidden) a.pause(); else a.play(); }catch(e){} }); });
trWatch();
document.addEventListener('DOMContentLoaded', function(){ if(r.classList.contains('alto-holo')) trSync(); });
"""


def build_js(mode: str = NODE_MODE) -> str:
    return (NODE_JS + TUBE_JS + WORD_JS).replace("__TRCSS__", _json.dumps(CSS + NODE_CSS + TUBE_CSS)).replace("__TBT__", _json.dumps(list(TUBE_T))).replace("__TBR__", repr(TUBE_RHO)).replace("__NTMODE__", mode).replace("__NTLEAD__", str(LEAD)).replace("__NTCAP__", str(CAP)).replace("__LOOP__", str(LOOP * 1000)).replace("__DELAY__", str(int(DELAY * 1000))).replace("__CORE__", repr(CORE)).replace("__GHOST__", repr(GHOST)).replace("__SWEEP__", repr(SWEEP))


JS = build_js()
