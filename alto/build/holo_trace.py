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

# Part 2 (Luke, 2026-11-05: "can we make the holo animation i described do the same thing for nodes along their borders?"): a trace on a card's border, each card at
# its own point of the loop so they never pulse in unison.
# Measured (headed WebKit): an animated stroke (stroke-dashoffset) on a card costs the page a fixed ~6 points of one core per frame whether it is one card or forty-four
# (it repaints the board's connector layer under it), and 30 points when it is not on its own layer. So the card's runner is four thin strips on its border, each carrying
# one runner that slides by `transform` alone (the compositor's, no repaint, no main-thread frame): one root per card, four moving children.
# Luke, 2026-11-12: "the running outline of nodes is a bit much, make it one color of light, just like the border of it is actually lighting up in one small runner".
# So: ONE runner a card, in ONE colour, the border's own light at full strength (Holographic's --ho-ac2, the brighter pair of the cyan the border is drawn in; a pale
# page gets its deep teal), no white bead, no magenta ghost, no second trail. It is a short stretch of the border line itself, 2 px on the 1 px border, at full strength over
# the quarter behind its head and fading to nothing along the line at both ends, inside a faint halo of the same colour and the same length. Calmer: a lap of the card takes 4.5 s
# (it was 2.8) and comes once every 12 s (it was 7): the runner moves at about 60% of the old speed and a card rests longer between laps.
# Cheaper or equal: the same four strips moved the same way, each 56 px shorter than before.
NODE_MODE = "full"     # full: every card, always | view: only cards on screen | walk: the hovered and chosen card, plus one idle pass walking from card to card
CAP = 80               # cards traced at most (a board of hundreds keeps the first 80 in page order); measured +3 points of a core for 44 cards
LEAD = 74              # px a strip is longer than its edge: the runner's own length and a little, so one translate walks it on and off
RUNNER = 64            # px, the lit stretch from its faint tail to its head
NODE_LOOP = 12         # seconds between a card's laps
NODE_PASS = 4.5        # seconds a lap takes
NODE_RGB = {"dark": "143,252,242", "light": "6,96,124"}      # --ho-ac2 (holo.TOKENS), as r,g,b for the fade to nothing

def _run(alpha: str) -> str:      # the runner's light along its line: nothing, full just behind the head, nothing
    return "linear-gradient(var(--hn-a),rgba(var(--hn-c),0),rgba(var(--hn-c),%s) 55%%,rgba(var(--hn-c),%s) 82%%,rgba(var(--hn-c),0))" % (alpha, alpha)


NODE_CSS = (
    ".ho-nt{position:absolute;left:-3px;top:-4px;right:-3px;bottom:-3px;overflow:hidden;z-index:2;--hn-c:%s}" % NODE_RGB["light"]
    + "html.dark .ho-nt{--hn-c:%s}" % NODE_RGB["dark"]
    + ".ho-nt,.ho-nt *{pointer-events:none !important}"
    ".ho-nt i{position:absolute;display:block;will-change:transform}"
    + ".ho-nt .t,.ho-nt .b{height:5px;width:calc(100%% + %dpx);" % LEAD
    + "background:%s var(--hn-d) top 50%% / %dpx 2px no-repeat,%s var(--hn-d) top 50%% / %dpx 4px no-repeat}" % (_run("1"), RUNNER, _run(".4"), RUNNER)
    + ".ho-nt .l,.ho-nt .r{width:5px;height:calc(100%% + %dpx);" % LEAD
    + "background:%s left 50%% var(--hn-d) / 2px %dpx no-repeat,%s left 50%% var(--hn-d) / 4px %dpx no-repeat}" % (_run("1"), RUNNER, _run(".4"), RUNNER)
    + ".ho-nt .t{top:.5px;left:0;--hn-d:right 0px;--hn-a:90deg}.ho-nt .b{bottom:0;left:-%dpx;--hn-d:left 0px;--hn-a:270deg}" % LEAD
    + ".ho-nt .r{right:0;top:0;--hn-d:bottom 0px;--hn-a:180deg}.ho-nt .l{left:0;top:-%dpx;--hn-d:top 0px;--hn-a:0deg}" % LEAD
    # (rel-223 study_plan, phone on its side with Safari's tab strip up): there the one card is a scroller (engine_patches _LS_NEW: overflow-y:auto, capped
    # height) and the root's -3/-4 px overhang gave it 3 px of scroll. In that card the root sits on the padding box (inset 0) and each strip moves out by the
    # same overhang and grows by it, so every strip and bead stays where it was on the screen; the card's own clip at the padding box was the clip already.
    + ((    "@media (orientation:landscape) and (max-height:340px){html.mobile.focus-mode .node.mobile-featured .node-card>.ho-nt{left:0;top:0;right:0;bottom:0}"
    + "html.mobile.focus-mode .node.mobile-featured .node-card>.ho-nt .t,html.mobile.focus-mode .node.mobile-featured .node-card>.ho-nt .b{width:calc(100%% + %dpx)}"
    + "html.mobile.focus-mode .node.mobile-featured .node-card>.ho-nt .l,html.mobile.focus-mode .node.mobile-featured .node-card>.ho-nt .r{height:calc(100%% + %dpx)}"
    + "html.mobile.focus-mode .node.mobile-featured .node-card>.ho-nt .t{top:-3.5px;left:-3px}html.mobile.focus-mode .node.mobile-featured .node-card>.ho-nt .b{bottom:-3px;left:-%dpx}"
    + "html.mobile.focus-mode .node.mobile-featured .node-card>.ho-nt .r{right:-3px;top:-4px}html.mobile.focus-mode .node.mobile-featured .node-card>.ho-nt .l{left:-3px;top:-%dpx}}"
) % (LEAD + 6, LEAD + 7, LEAD + 3, LEAD + 4))
    + ".node.dimmed .ho-nt,.compass-mini-node .ho-nt{display:none}"
    "html.hp-hid .ho-nt{visibility:hidden}"
    "@media (prefers-reduced-motion:reduce){.ho-nt{display:none !important}}"
    "@media print{.ho-nt{display:none !important}}html.printing .ho-nt{display:none !important}"
)

NODE_JS = r"""
var NT={on:null,mo:null,io:null,n:0,walk:0,wcur:null,raf:0}, NTM='__NTMODE__', NTL=__NTLEAD__;
function ntHas(c){ return c.querySelector(':scope > .ho-nt'); }
function ntAdd(c,once){
  var s=ntHas(c); if(s) return s;
  var W=c.offsetWidth, H=c.offsetHeight; if(!W||!H) return null;
  s=document.createElement('div'); s.className='ho-nt'; s.setAttribute('aria-hidden','true');
  var E=[['t',W,'translateX(-100%)','translateX(0)'],['r',H,'translateY(-100%)','translateY(0)'],['b',W,'translateX(100%)','translateX(0)'],['l',H,'translateY(100%)','translateY(0)']];
  var per=2*(W+H), v=per/__NTPASS__/1000, ph=((NT.n++)*0.6180339887)%1, loop=__NTLOOP__, S=0, last=null;
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

# Tube 2 (Luke, 2026-11-12: "tubular glyph isn't quite there yet, make it actually tubular as it spins"): the stacked slices read as a thick flat cut-out, because every
# slice is still a flat drawing and nothing on it is lit. So the glyph is now a real pipe: the clef's own strokes (read from the page at run time, sampled along their
# length) are swept into round tubes of each stroke's own radius, with a ball at every end and corner and a cone for the arrow head, and rendered with WebGL. The light
# stands still in the room (upper left, in front) while the pipe turns under it, so the shading across the pipe's width and its white glint slide round it with the
# turn; a depth buffer puts the nearer stroke over the farther one where they cross; seen from the side a pipe is as thick as from the front. Same size, place,
# colours, 10 s swing of 55 degrees to each side (a full turn would show the clef mirrored half the time) and perspective (260 px) as before.
# Cost. Drawing it live (a WebGL frame 30 times a second) measured +10 points of one core in WebKit over the slices, so it is NOT drawn live: when the glyph is made, the
# 89 frames of the swing (every 1.25 degrees) are rendered once, a few per animation frame over about a third of a second, into one sheet (a 2D canvas, 12 x 8 cells),
# the WebGL context is given back, and the swing is a CSS animation that steps the sheet behind a cell-sized window (`transform` only, percentages of the sheet, so the
# keyframes are the same at every size). Nothing runs per frame and one small layer moves where eleven turned. The steps come when the swing's cosine crosses each
# frame's angle: about 28 a second through the middle, fewer as it slows at the ends. Reduce Motion: the frame nearest the old 24 degrees, still, shaded the same (and
# only that frame and the face-on one are rendered). A hidden tab or a glyph off screen pauses the animation. Without WebGL (or if the context is lost while the sheet
# is made) the slices, which are still built, show and swing as they did; paper gets the slices face-on.
TUBE_SWING = 55        # degrees to each side
TUBE_PERIOD = 10       # seconds
TUBE_STILL = 24        # degrees, Reduce Motion
TUBE_FRAMES = 89       # the swing's frames, -55 .. 55 by 1.25 degrees
TUBE_COLS, TUBE_ROWS = 12, 8
TUBE_FLAT = {   # the glow behind and the magenta ghost, premultiplied rgba (the slices' own .gl / .gh colours)
    "dark": ((79, 240, 224, .2), (255, 95, 210, .5)),
    "light": ((10, 111, 140, .18), (214, 40, 170, .4)),
}


def _tube_pal() -> dict:
    rgb = lambda h: [round(int(h[i:i + 2], 16) / 255, 4) for i in (1, 3, 5)]
    pre = lambda c: [round(c[0] / 255 * c[3], 4), round(c[1] / 255 * c[3], 4), round(c[2] / 255 * c[3], 4), c[3]]
    return {k: {"c": [rgb(x) for x in TUBE_C[k]], "f": [pre(x) for x in TUBE_FLAT[k]]} for k in TUBE_C}


def tube_angle(i: int) -> float:
    return -TUBE_SWING + i * 2 * TUBE_SWING / (TUBE_FRAMES - 1)


def tube_frame(deg: float) -> int:
    return round((deg + TUBE_SWING) * (TUBE_FRAMES - 1) / (2 * TUBE_SWING))


def _cell(i: int) -> str:
    f = lambda v: ("%.4f" % v).rstrip("0").rstrip(".")
    return "translate(-%s%%,-%s%%)" % (f(100 * (i % TUBE_COLS) / TUBE_COLS), f(100 * (i // TUBE_COLS) / TUBE_ROWS))


def tube_keyframes() -> str:
    """the swing, -55cos(2 pi t / 10), as steps of the sheet: frame i shows from the moment the angle passes midway between frames i-1 and i"""
    import math
    cross = [100 * math.acos(-(tube_angle(i) + tube_angle(i + 1)) / 2 / TUBE_SWING) / (2 * math.pi) for i in range(TUBE_FRAMES - 1)]     # % of the period, going up
    k = ["0%%,100%%{transform:%s}" % _cell(0)]
    k += ["%.3f%%{transform:%s}" % (p, _cell(i + 1)) for i, p in enumerate(cross)]
    k += ["%.3f%%{transform:%s}" % (100 - p, _cell(i)) for i, p in reversed(list(enumerate(cross)))]
    return "@keyframes ho-pipe{" + "".join(k) + "}"


TUBE_PIPE_CSS = (
    # the window on the sheet, and the sheet: face-on until every frame is in (.go), then the swing; the slices stay in the box, not displayed, for a browser without
    # WebGL and for paper. Nothing here turns in 3D, is filtered, shadowed or promoted ahead of time (iOS composites the fixed header).
    ".ho-tube .cl{position:absolute;overflow:hidden;margin:0;padding:0}"
    ".ho-tube canvas{position:absolute;left:0;top:0;display:block;margin:0;padding:0;border:0;background:none;max-width:none;max-height:none;transform:%s}" % _cell(tube_frame(0))
    + ".ho-tube.go canvas{animation:ho-pipe %ds step-end -%ss infinite}" % (TUBE_PERIOD, ("%.2f" % (TUBE_PERIOD / 4)).rstrip("0").rstrip("."))
    + "html.hp-hid .ho-tube canvas,.ho-tube.off canvas{animation-play-state:paused}"
    + "@media (prefers-reduced-motion:reduce){.ho-tube:not(#_) canvas{animation:none;transform:%s}}" % _cell(tube_frame(TUBE_STILL))
    + "@media screen{.ho-tube.g3 .sp{display:none}}"
    "@media print{.ho-tube .cl{display:none !important}}html.printing .ho-tube .cl{display:none !important}html.printing .ho-tube.g3 .sp{display:block;animation:none;transform:none}"
)

TUBE_GL_JS = r"""
var TB={list:[],io:null}, TBP=__TBPAL__, TBN=__TBN__, TBC=__TBCOLS__, TBW=__TBROWS__, TBSW=__TBSW__, TBF0=__TBF0__, TBFS=__TBFS__;
var TBVS='attribute vec3 p;attribute vec3 n;uniform vec2 cs;uniform vec4 k;uniform vec3 off;uniform vec2 o;varying vec3 vn;'
 +'void main(){vec3 q=p+n*off.y+vec3(off.x,0.,off.z);float x=q.x*cs.x+q.z*cs.y,z=q.z*cs.x-q.x*cs.y,s=k.z/(k.z-z);'
 +'vn=vec3(n.x*cs.x+n.z*cs.y,-n.y,n.z*cs.x-n.x*cs.y);gl_Position=vec4(x*s*k.x+o.x,-q.y*s*k.y+o.y,-z/90.,1.);}';
var TBFG='precision mediump float;varying vec3 vn;uniform vec4 fl;uniform vec3 c0;uniform vec3 c1;uniform vec3 c2;uniform vec3 c3;'
 +'void main(){if(fl.a>0.){gl_FragColor=fl;return;}vec3 N=normalize(vn);vec3 L=normalize(vec3(-.55,.6,.58));'
 +'float d=max(dot(N,L),0.),f=clamp(N.z,0.,1.),s=pow(max(dot(N,normalize(L+vec3(0.,0.,1.))),0.),42.),b=max(dot(N,normalize(vec3(.7,-.5,.3))),0.);'
 +'vec3 c=mix(c0,c1,smoothstep(0.,.45,f));c=mix(c,c2,smoothstep(.3,.95,f)*.8);c*=.66+.5*d;c+=c1*b*b*.16;c=mix(c,c3,clamp(d*d*d*.5+s*1.3,0.,1.));gl_FragColor=vec4(min(c,vec3(1.)),1.);}';
function tbMesh(geo){
  var V=[], I=[], K=10, vb=(geo.vb||'').split(/[ ,]+/).map(Number), cx=vb[0]+vb[2]/2-geo.tx, cy=vb[1]+vb[3]/2;
  function vert(x,y,z,nx,ny,nz){ V.push(x-cx,y-cy,z,nx,ny,nz); }
  function ball(x,y,q){
    var A=6,B=10,a,b,base=V.length/6;
    for(a=0;a<=A;a++){ var ph=Math.PI*a/A, sp=Math.sin(ph), cp=Math.cos(ph); for(b=0;b<=B;b++){ var th=2*Math.PI*b/B, nx=sp*Math.cos(th), nz=sp*Math.sin(th); vert(x+q*nx,y+q*cp,q*nz,nx,cp,nz); } }
    for(a=0;a<A;a++) for(b=0;b<B;b++){ var i=base+a*(B+1)+b; I.push(i,i+1,i+B+1,i+1,i+B+2,i+B+1); }
  }
  function ring(x,y,ax,ay,q,ns,nr){   // a circle of radius q round the axis (ax,ay) at (x,y); its normals lean ns along the axis
    var base=V.length/6, j; if(nr===undefined){ ns=0; nr=1; }
    for(j=0;j<=K;j++){ var th=2*Math.PI*j/K, c=Math.cos(th), s=Math.sin(th); vert(x-q*c*ay,y+q*c*ax,q*s,ax*ns-nr*c*ay,ay*ns+nr*c*ax,nr*s); }
    return base;
  }
  function link(a,b){ for(var j=0;j<K;j++) I.push(a+j,a+j+1,b+j,a+j+1,b+j+1,b+j); }
  geo.paths.forEach(function(o){
    var q=o.w/2, i;
    if(o.head){
      var m=(o.d.match(/-?[\d.]+/g)||[]).map(Number); if(m.length<6) return;
      var P=[[m[0],m[1]],[m[2],m[3]],[m[4],m[5]]], D=function(a,b){ return Math.hypot(a[0]-b[0],a[1]-b[1]); }, best=0, bd=1e9;
      for(i=0;i<3;i++){ var e=Math.abs(D(P[i],P[(i+1)%3])-D(P[i],P[(i+2)%3])); if(e<bd){ bd=e; best=i; } }
      var T=P[best], B1=P[(best+1)%3], B2=P[(best+2)%3], M=[(B1[0]+B2[0])/2,(B1[1]+B2[1])/2], len=D(T,M), ax=(T[0]-M[0])/len, ay=(T[1]-M[1])/len, R=D(B1,B2)/2+q*.7;
      var prof=[[-q,0.01],[-q,R*.7],[-q*.4,R],[len*.33,R+(q-R)*.33],[len*.66,R+(q-R)*.66],[len,q*.9],[len+q*.7,0.01]], prev=-1;
      for(i=0;i<prof.length;i++){
        var a=prof[Math.max(0,i-1)], b=prof[Math.min(prof.length-1,i+1)], ds=b[0]-a[0], dr=b[1]-a[1], l=Math.hypot(ds,dr)||1;
        var rg=ring(M[0]+ax*prof[i][0],M[1]+ay*prof[i][0],ax,ay,prof[i][1],-dr/l,ds/l); if(prev>=0) link(prev,rg); prev=rg;
      }
      return;
    }
    var L=o.el.getTotalLength(), n=Math.max(1,Math.ceil(L/1.4)), pts=[], prev=-1;
    for(i=0;i<=n;i++){ var pt=o.el.getPointAtLength(L*i/n); pts.push([pt.x,pt.y]); }
    for(i=0;i<=n;i++){
      var a=pts[Math.max(0,i-1)], b=pts[Math.min(n,i+1)], tx=b[0]-a[0], ty=b[1]-a[1], l=Math.hypot(tx,ty)||1;
      var rg=ring(pts[i][0],pts[i][1],tx/l,ty/l,q); if(prev>=0) link(prev,rg); prev=rg;
      if(i===0 || i===n) ball(pts[i][0],pts[i][1],q);
      else { var u=[pts[i][0]-a[0],pts[i][1]-a[1]], v=[b[0]-pts[i][0],b[1]-pts[i][1]]; if((u[0]*v[0]+u[1]*v[1])/((Math.hypot(u[0],u[1])*Math.hypot(v[0],v[1]))||1)<.9) ball(pts[i][0],pts[i][1],q); }
    }
  });
  return {v:new Float32Array(V), i:new Uint16Array(I)};
}
function tbRender(s){      // a WebGL context holding the pipe; used to fill the sheet, then given back
  var cv=document.createElement('canvas'), gl=null, m=s._hoM;
  try{ gl=cv.getContext('webgl',{alpha:true,antialias:true,depth:true,premultipliedAlpha:true,powerPreference:'low-power'}); }catch(e){}
  if(!gl) return null;
  try{
    if(!m){ m=s._hoM=tbMesh(s._hoGeo); if(!m.i.length || m.v.length/6>65535) return null; }
    var sh=function(t,src){ var x=gl.createShader(t); gl.shaderSource(x,src); gl.compileShader(x); if(!gl.getShaderParameter(x,gl.COMPILE_STATUS)) throw 0; return x; };
    var pr=gl.createProgram(); gl.attachShader(pr,sh(gl.VERTEX_SHADER,TBVS)); gl.attachShader(pr,sh(gl.FRAGMENT_SHADER,TBFG)); gl.linkProgram(pr);
    if(!gl.getProgramParameter(pr,gl.LINK_STATUS)) throw 0;
    gl.useProgram(pr);
    gl.bindBuffer(gl.ARRAY_BUFFER,gl.createBuffer()); gl.bufferData(gl.ARRAY_BUFFER,m.v,gl.STATIC_DRAW);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,gl.createBuffer()); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,m.i,gl.STATIC_DRAW);
    var ap=gl.getAttribLocation(pr,'p'), an=gl.getAttribLocation(pr,'n');
    gl.enableVertexAttribArray(ap); gl.vertexAttribPointer(ap,3,gl.FLOAT,false,24,0); gl.enableVertexAttribArray(an); gl.vertexAttribPointer(an,3,gl.FLOAT,false,24,12);
    gl.disable(gl.BLEND); gl.clearColor(0,0,0,0);
    var U={}; ['cs','k','off','o','fl','c0','c1','c2','c3'].forEach(function(u){ U[u]=gl.getUniformLocation(pr,u); });
    return {gl:gl,cv:cv,U:U,n:m.i.length};
  }catch(e){ return null; }
}
function tbQuit(R){ if(R) try{ var x=R.gl.getExtension('WEBGL_lose_context'); if(x) x.loseContext(); }catch(e){} }
function tbDraw(R,g,deg,P){      // one frame of the pipe at `deg`, the size of one cell
  var gl=R.gl, U=R.U, a=deg*Math.PI/180;
  if(R.cv.width!==g.fw || R.cv.height!==g.fh){ R.cv.width=g.fw; R.cv.height=g.fh; }
  gl.viewport(0,0,g.fw,g.fh); gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
  gl.uniform2f(U.cs,Math.cos(a),Math.sin(a)); gl.uniform4f(U.k,g.kx,g.ky,260/g.u,0); gl.uniform2f(U.o,g.ox,g.oy);
  gl.disable(gl.DEPTH_TEST);
  gl.uniform4fv(U.fl,P.f[0]); gl.uniform3f(U.off,0,TBR*.85,-TBR*1.5); gl.drawElements(gl.TRIANGLES,R.n,gl.UNSIGNED_SHORT,0);     // the glow, a wider pipe behind
  gl.uniform4fv(U.fl,P.f[1]); gl.uniform3f(U.off,-3.2,0,-TBR*1.2); gl.drawElements(gl.TRIANGLES,R.n,gl.UNSIGNED_SHORT,0);       // the magenta ghost
  gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL);
  gl.uniform4f(U.fl,0,0,0,0); gl.uniform3f(U.off,0,0,0);
  gl.uniform3fv(U.c0,P.c[0]); gl.uniform3fv(U.c1,P.c[1]); gl.uniform3fv(U.c2,P.c[2]); gl.uniform3fv(U.c3,P.c[3]);
  gl.drawElements(gl.TRIANGLES,R.n,gl.UNSIGNED_SHORT,0);
}
function tbGL(s){
  var R=tbRender(s); if(!R) return false;
  var cl=document.createElement('div'), cv=document.createElement('canvas'), x=cv.getContext('2d'); if(!x){ tbQuit(R); return false; }
  cl.className='cl'; cv.setAttribute('aria-hidden','true'); cl.appendChild(cv); s.appendChild(cl);
  s._hoG={cl:cl,cv:cv,x:x,R:R,have:{},key:'',raf:0,n:0}; TB.list.push(s);
  s._hoShot=function(deg){      // (for the tests and the look sheets) one frame at any angle, as a canvas of its own
    var g=s._hoG, T=tbRender(s), o=document.createElement('canvas'); if(!g || !T || !g.fw) return null;
    tbDraw(T,g,deg,TBP[r.classList.contains('dark') ? 'dark' : 'light']); o.width=g.fw; o.height=g.fh; o.getContext('2d').drawImage(T.cv,0,0); o._depth=T.gl.getParameter(T.gl.DEPTH_BITS); tbQuit(T); return o;
  };
  if(typeof IntersectionObserver==='function'){
    if(!TB.io) TB.io=new IntersectionObserver(function(es){ es.forEach(function(e){ e.target.classList.toggle('off', !e.isIntersecting); }); });
    TB.io.observe(s);
  }
  return true;
}
function tbFree(s){      // back to the slices
  var g=s._hoG, i=TB.list.indexOf(s); if(i>=0) TB.list.splice(i,1);
  if(TB.io) try{ TB.io.unobserve(s); }catch(e){}
  if(!g) return; s._hoG=null; s._hoShot=null; s.classList.remove('g3','go','off');
  if(g.raf) cancelAnimationFrame(g.raf); tbQuit(g.R); g.R=null;
  if(g.cl.parentNode) g.cl.parentNode.removeChild(g.cl);
}
function tbSize(s){
  var g=s._hoG; if(!g) return;
  var W=parseFloat(s.style.width)||0, H=parseFloat(s.style.height)||0; if(!(W>0 && H>0)) return;
  var pad=H*.15, cw=Math.ceil(W+2*pad), ch=Math.ceil(H+2*pad), q=Math.min(3,Math.max(2,Math.round(window.devicePixelRatio||1))), l=Math.round((W-cw)/2), t=Math.round((H-ch)/2);
  g.cl.style.cssText='left:'+l+'px;top:'+t+'px;width:'+cw+'px;height:'+ch+'px';
  g.cv.style.width=(cw*TBC)+'px'; g.cv.style.height=(ch*TBW)+'px';
  g.dim=cw+'x'+ch+'x'+q+'x'+W+'x'+H; g.fw=cw*q; g.fh=ch*q; g.u=H/98; g.kx=2*g.u/cw; g.ky=2*g.u/ch; g.ox=2*(W/2-l)/cw-1; g.oy=1-2*(H/2-t)/ch;
}
function tbBuild(s){      // fill the sheet: the face-on frame and the still one at once, the rest a few per animation frame; then the swing starts
  var g=s._hoG; if(!g || !g.fw) return;
  var dark=r.classList.contains('dark'), P=TBP[dark ? 'dark' : 'light'], key=g.dim+(dark ? 'd' : 'l'), still=!!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
  if(g.key!==key){
    g.key=key; g.have={}; g.n=0; s.classList.remove('go');
    if(g.cv.width!==g.fw*TBC || g.cv.height!==g.fh*TBW){ g.cv.width=g.fw*TBC; g.cv.height=g.fh*TBW; } else g.x.clearRect(0,0,g.cv.width,g.cv.height);
  }
  var todo=[TBF0,TBFS], i; if(!still) for(i=0;i<TBN;i++) todo.push(i);
  todo=todo.filter(function(f,j){ return !g.have[f] && todo.indexOf(f)===j; });
  if(g.raf){ cancelAnimationFrame(g.raf); g.raf=0; }
  if(!todo.length){ if(g.n>=TBN) s.classList.add('go'); return; }
  var step=function(first){
    g.raf=0; if(s._hoG!==g || g.key!==key) return;
    if(!g.R) g.R=tbRender(s);
    if(!g.R || g.R.gl.isContextLost()){ tbFree(s); return; }
    var t0=performance.now(), k=0;
    while(todo.length && (first ? k<2 : (k<8 && performance.now()-t0<7))){
      var f=todo.shift(); tbDraw(g.R,g,-TBSW+f*2*TBSW/(TBN-1),P);
      if(g.R.gl.isContextLost()){ tbFree(s); return; }
      g.x.clearRect((f%TBC)*g.fw,Math.floor(f/TBC)*g.fh,g.fw,g.fh); g.x.drawImage(g.R.cv,(f%TBC)*g.fw,Math.floor(f/TBC)*g.fh);
      g.have[f]=1; g.n++; k++;
    }
    s.classList.add('g3');
    if(todo.length) g.raf=requestAnimationFrame(function(){ step(false); });
    else { tbQuit(g.R); g.R=null; if(g.n>=TBN) s.classList.add('go'); }
  };
  step(true);
}
function tbKick(){ TB.list.slice().forEach(tbBuild); }
"""

TUBE_JS = r"""
var TBT=__TBT__, TBR=__TBR__, TBE=TBR/0.95;
function tbRead(mark){
  var ink=mark.querySelector('.alto-ink'), head=mark.querySelector('.alto-head'), out=[], tx=0;
  if(!ink) return null;
  var tr=ink.parentNode.getAttribute('transform')||'', m=tr.match(/translate\(\s*(-?[\d.]+)[ ,]+(-?[\d.]+)/); if(m) tx=+m[1];
  [].forEach.call(ink.querySelectorAll('path'), function(p){
    var wEl=p.closest('[stroke-width]'); out.push({el:p, d:p.getAttribute('d'), w:+(p.getAttribute('stroke-width') || (wEl && wEl.getAttribute('stroke-width')) || 6)});
  });
  if(head) out.push({el:head, d:head.getAttribute('d'), w:+(head.getAttribute('stroke-width')||2.9), head:true});
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
  s._hoGeo=geo; tbGL(s);
  return s;
}
function tbSync(on){
  var marks=[].slice.call(document.querySelectorAll('svg.brand-mark'));
  if(!on){
    [].forEach.call(document.querySelectorAll('.ho-tube'), function(n){ tbFree(n); n.parentNode.removeChild(n); });
    marks.forEach(function(m){ m._hoK=null; ['opacity','animation','will-change','filter'].forEach(function(p){ m.style.removeProperty(p); }); });
    return;
  }
  marks.forEach(function(m){
    var s=m._hoK;
    if(getComputedStyle(m).display==='none' || !m.getClientRects().length){ if(s){ tbFree(s); if(s.parentNode) s.parentNode.removeChild(s); } m._hoK=null; return; }
    if(s && (s.previousSibling!==m || !s.parentNode)){ tbFree(s); if(s.parentNode) s.parentNode.removeChild(s); s=m._hoK=null; }
    if(!s){ s=tbMake(m); if(!s) return; m.parentNode.insertBefore(s, m.nextSibling); m._hoK=s; }
    var abs=getComputedStyle(m).position==='absolute';
    trPlace(m,s); s.style.width=getComputedStyle(m).width; s.style.transform=abs ? 'translateY(-50%)' : '';
    s.style.setProperty('--u', (parseFloat(s.style.height)/98)+'px');
    ['opacity:0','animation:none','will-change:auto','filter:none'].forEach(function(a){ var k=a.split(':'); m.style.setProperty(k[0],k[1],'important'); });
    tbSize(s);
  });
  tbKick();
}
""" + TUBE_GL_JS

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
  TR.mo=new MutationObserver(function(){ if(TR.on!==trLive() || TR.h!==r.classList.contains('alto-holo')) trSync(); else tbKick(); });
  TR.mo.observe(r,{attributes:true,attributeFilter:['class']});
  var late=function(){ if(r.classList.contains('alto-holo')) trSync(); };
  window.addEventListener('resize', function(){ if(TR.rz) return; TR.rz=setTimeout(function(){ TR.rz=0; late(); }, 150); });
  window.addEventListener('load', function(){ setTimeout(late, 300); });
  window.addEventListener('pageshow', late);
  try{ var mq=matchMedia('(prefers-reduced-motion: reduce)'); if(mq.addEventListener) mq.addEventListener('change', trSync); else if(mq.addListener) mq.addListener(trSync); }catch(e){}
  if(r.classList.contains('alto-holo')){ trSync(); TR.t=setTimeout(late, 1200); }
}
document.addEventListener('visibilitychange', function(){ if(r.classList.contains('alto-holo')) TR.anims.forEach(function(a){ try{ if(document.hidden) a.pause(); else a.play(); }catch(e){} }); tbKick(); });
trWatch();
document.addEventListener('DOMContentLoaded', function(){ if(r.classList.contains('alto-holo')) trSync(); });
"""


def build_js(mode: str = NODE_MODE) -> str:
    return (NODE_JS + TUBE_JS + WORD_JS).replace("__TRCSS__", _json.dumps(CSS + NODE_CSS + TUBE_CSS + TUBE_PIPE_CSS + tube_keyframes())).replace("__TBT__", _json.dumps(list(TUBE_T))).replace("__TBPAL__", _json.dumps(_tube_pal(), separators=(",", ":"))).replace("__TBN__", str(TUBE_FRAMES)).replace("__TBCOLS__", str(TUBE_COLS)).replace("__TBROWS__", str(TUBE_ROWS)).replace("__TBSW__", str(TUBE_SWING)).replace("__TBF0__", str(tube_frame(0))).replace("__TBFS__", str(tube_frame(TUBE_STILL))).replace("__TBR__", repr(TUBE_RHO)).replace("__NTMODE__", mode).replace("__NTLEAD__", str(LEAD)).replace("__NTPASS__", repr(NODE_PASS)).replace("__NTLOOP__", str(int(NODE_LOOP * 1000))).replace("__NTCAP__", str(CAP)).replace("__LOOP__", str(LOOP * 1000)).replace("__DELAY__", str(int(DELAY * 1000))).replace("__CORE__", repr(CORE)).replace("__GHOST__", repr(GHOST)).replace("__SWEEP__", repr(SWEEP))


JS = build_js()
