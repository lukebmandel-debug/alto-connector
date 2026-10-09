"""Recorded fixes applied to the emitted engine HTML.

`engine/timeline_template.html` and `engine/FROZEN/` stay byte-faithful to the
pinned upstream engine — that is what tests/test_roundtrip.py proves, and the
proof is worth keeping. Engine bugs found downstream are therefore fixed here:
one explicit old→new string per bug, applied to the emitted page, each with an
expected hit count so a future engine refresh that moves the anchor fails the
build loudly instead of silently dropping the fix.

Same discipline as hosted.py's `_rep`. Each entry carries the symptom, so a
patch can be retired the moment upstream fixes it.
"""
from __future__ import annotations

from .runway import runway_script


class PatchError(RuntimeError):
    pass


# ── merge-flag overshoot ─────────────────────────────────────────────────────
# When a connection has no clear corridor, the router lets it *ride* another
# line's horizontal (tryMerge), then paints the host's colour back onto the
# bottom half of the guest's tube so both are readable. That overlay spans
# `mergedRide.x1..x2`, which come from corner CENTRES, while the tube it
# overlays runs straight only between the corner ARCS (inset by `r`). The
# difference draws as a bare stub jutting past the curve into open space —
# visible on any timeline where two relations of different colours share a
# lane. Clamp the overlay to the straight run both tubes actually share.
_MERGE_FLAG_OLD = """        if(mergedRide && mergedRide.host.color && mergedRide.host.color !== tubeColor && (mergedRide.x2 - mergedRide.x1) > 8){
          var flag = document.createElementNS(NS,'path');
          flag.setAttribute('d', 'M ' + mergedRide.x1 + ' ' + (midY + tubeW/4) +
                                 ' L ' + mergedRide.x2 + ' ' + (midY + tubeW/4));"""

_MERGE_FLAG_NEW = """        var _mfLo = mergedRide ? mergedRide.x1 : 0, _mfHi = mergedRide ? mergedRide.x2 : 0;
        if(mergedRide){
          // Ends that sit on a corner centre (either tube's) are inside an arc,
          // where neither tube runs straight — pull them in by the arc radius so
          // the overlay stops with the curve instead of jutting past it.
          var _mfCorners = [sx, tx, mergedRide.host.x1, mergedRide.host.x2];
          var _mfAtCorner = function(x){
            for(var _ci = 0; _ci < _mfCorners.length; _ci++){
              if(typeof _mfCorners[_ci] === 'number' && Math.abs(x - _mfCorners[_ci]) < 1) return true;
            }
            return false;
          };
          if(_mfAtCorner(_mfLo)) _mfLo += r;
          if(_mfAtCorner(_mfHi)) _mfHi -= r;
        }
        if(mergedRide && mergedRide.host.color && mergedRide.host.color !== tubeColor && (_mfHi - _mfLo) > 8){
          var flag = document.createElementNS(NS,'path');
          flag.setAttribute('d', 'M ' + _mfLo + ' ' + (midY + tubeW/4) +
                                 ' L ' + _mfHi + ' ' + (midY + tubeW/4));"""
# ── an outline prints as an outline ─────────────────────────────────────────
# The engine's "main timeline" print renders every node as a card on a vertical
# spine, which is right for a sequence and wrong for a containment tree: on
# paper a concept outline wants nesting, real outline numerals, and the
# authority beside each rule. ACT_SEQS / NODES / PHASE_META / ENVS are all
# module-scoped, so a builder-side override is impossible without this hook.
# Two lines: when the page carries outline data, hand it to the builder's own
# renderer; otherwise fall through to the engine's, untouched.
_PRINT_OUTLINE_OLD = (
    "function _buildPrintTimelineHTML(){\n"
    "  if(typeof ACT_SEQS === 'undefined' || typeof NODES === 'undefined') return '';")
_PRINT_OUTLINE_NEW = (
    "function _buildPrintTimelineHTML(){\n"
    "  if(typeof ACT_SEQS === 'undefined' || typeof NODES === 'undefined') return '';\n"
    "  if(window._ALTO_OUTLINE && window._altoPrintOutline)\n"
    "    return window._altoPrintOutline(ACT_SEQS, NODES,\n"
    "      (typeof PHASE_META!=='undefined')?PHASE_META:[],\n"
    "      (typeof ENVS!=='undefined')?ENVS:{});")

# ── the search box says "Search", everywhere ────────────────────────────────
# Three surfaces had three different placeholders, and the desktop timeline's
# still named the reference build's own subject matter — "scenes, characters,
# themes" — which is wrong on a law outline and wrong on anything else that
# isn't a novel. Worse, it LOOKS configurable, so it invites a hunt for the
# setting that would fix it; there isn't one, the strings are frozen literals
# inside a JS concatenation. One word, the same on every surface.
_SEARCH_DESKTOP_OLD = "'placeholder=\"Search scenes, characters, themes\u2026\">'+"
_SEARCH_DESKTOP_NEW = "'placeholder=\"Search\">'+"
_SEARCH_MOBILE_OLD = "'placeholder=\"Search\u2026\">';"
_SEARCH_MOBILE_NEW = "'placeholder=\"Search\">';"

# ── focused card is blurry when enlarged ────────────────────────────────────
# The focus magnifier grew the card with `transform:scale(1.7)`, which magnifies
# the card's existing 1x raster instead of re-rendering it — at 1.7x the text is
# a blown-up bitmap. Safari shows it worst, because `.node-card` carries a
# backdrop-filter and the frosted layer is rasterised once and then stretched.
#
# The engine already knew: the `.crisp` rule swaps to `zoom:1.7` precisely to
# "re-raster the text", and its kill switch reads "flip to true if focused text
# looks blurry on Safari". It shipped OFF because the swap itself was visible —
# scaling to 1.7 and *then* re-laying the text out snaps every glyph advance in
# one frame, the "text jumps" glitch.
#
# There is no swap if the card is never scaled in the first place. Grow it with
# `zoom` from the start, ramped per frame, so the text is laid out at its final
# size on every frame and no frame re-flows. `.node-card` is a fixed 270px wide,
# so zoom changes no wrapping — only the device pixels per glyph. `.node` is
# `translate(-50%,-50%)` around its own box, which the zoom grows, so the card
# still grows about its centre exactly as the transform did.
_FOCUS_CSS_OLD = """html:not(.mobile) .node.focused .node-card{
  transform:scale(1.7) !important; transform-origin:center !important;
  opacity:1 !important; box-shadow:0 38px 84px var(--node-hover-shadow) !important;
}
"""
_FOCUS_CSS_NEW = """html:not(.mobile) .node.focused .node-card{
  /* No transform (scale(1) was a leftover of the scale era: identical on
     screen, but it started a transform transition and a new layer in Safari
     on every enlarge). The big shadow is drawn once on its own layer
     (.alto-fshadow, enterFocus) and faded: on the card it was re-blurred on
     every frame of the zoom ramp — Safari frames of 25-60ms. So the card's
     own shadow goes, at once, not animated. */
  transform:none !important; transform-origin:center !important;
  opacity:1 !important; box-shadow:none !important;
  transition:opacity var(--alto-fly,.25s) var(--alto-ease), border-color .2s !important;
  /* The magnification is CSS zoom, applied inline per frame by enterFocus. A
     zoomed element can lose its backdrop-filter, so — as the .crisp rule this
     replaces already did — legibility must not depend on the frost. Raise the
     FALLBACK, not the value: --node-glass-bg is Blink-only and already opaque
     enough there (0.90, set so the card occludes the connector lines Chrome's
     dead backdrop-filter can't hide). Only Safari, where it is undefined and
     the card falls back to --card-glass-bg at 0.54, needs the floor lifted. */
  background:var(--node-glass-bg, var(--panel-glass-bg));
}
html:not(.mobile) #world{ translate:var(--pan-x,0px) var(--pan-y,0px); }
/* Every fade that comes with a focus change rides the growth's clock and curve
   (motion-one-body): the other cards dimming, the new card brightening, the
   headers and lines fading. They ran on CSS's own 'ease' over .25-.3s, done
   in ~150ms while the card was 12% grown — the scene dimmed, THEN the card
   grew: two beats (Luke: "the Netflix boom boom"). cubic-bezier(.25,.2,.4,1)
   follows the shared curve (_altoEase) to within ~1%; --alto-fly is the glide's duration, written
   once per focus change (flyTo, exitFocus) and 250ms the rest of the time,
   so a hover fade keeps its pace. */
html:not(.mobile) #canvas{ --alto-fly:250ms; --alto-ease:cubic-bezier(.25,.2,.4,1); }
html:not(.mobile) #canvas .node-card{
  transition: opacity var(--alto-fly) var(--alto-ease), box-shadow .28s, border-color .2s,
              transform .24s cubic-bezier(.22,.61,.36,1);
}
html:not(.mobile) #canvas .phase-label, html:not(.mobile) #canvas .phase-label-float,
html:not(.mobile) #canvas .unit-bar, html:not(.mobile) #canvas .phase-numeral,
html:not(.mobile) #canvas #river-svg{ transition: opacity var(--alto-fly) var(--alto-ease) !important; }
/* The glass is full-bleed and only changes colour top to bottom, so it holds
   still sideways while the board pans across it: panning never shows bare
   page past its edge. */
html:not(.mobile) #world #glass-slab{ translate:calc(-1 * var(--pan-x,0px)) 0; }
html:not(.mobile) #world .alto-fshadow{
  position:absolute; pointer-events:none; z-index:299; opacity:0; will-change:opacity, transform;
  border-radius:calc(14px * 1.7); box-shadow:0 calc(38px * 1.7) calc(84px * 1.7) var(--node-hover-shadow);
}
@media print{ #world .alto-fshadow{ display:none !important; } }
"""

_FOCUS_JS_OLD = """  function enterFocus(id){
    if(!id) return; var el=nodeEl(id); if(!el) return;
    if(window._focusedNodeId && window._focusedNodeId!==id){ var p=nodeEl(window._focusedNodeId); if(p){ p.classList.remove('crisp'); p.classList.remove('focused'); p.style.transform=''; p._fx=p._fy=0; } }
    window._focusedNodeId=id;
    canvas.classList.add('focus-mode');
    el.classList.add('focused');
    flyTo(el);
  }"""

_FOCUS_JS_NEW = """  /* ── focus magnification: CSS zoom, ramped per frame ──────────────────────
     transform:scale() magnifies the card's 1x raster (blurry text at 1.7x, worst
     in Safari where the backdrop-filter layer is rasterised once). zoom re-lays
     the card out, so every glyph renders at its final resolution. Ramped rather
     than scaled-then-swapped: the swap frame is what jumped the text, and is why
     ALTO_CRISP_SWAP ships off. The card is a fixed 270px wide, so nothing
     re-wraps at any point on the ramp. */
  var FOCUS_K=1.7, _zw=null, _zwCard=null, _zwTo=1;
  /* ── one curve, one clock (motion-one-body) ───────────────────────────────
     Enlarging or hopping is one movement: the view glides, the new card grows
     into place and the old one settles home, all on this curve and starting
     on the same frame.

     The curve launches quickly and lands decisively: speed rises from rest
     to its peak within the first fifth of the time, then falls away to a
     clean stop — the regularized incomplete beta B(1.4, 2.6), whose speed
     profile is t^0.4 (1-t)^1.6. Luke picked it (2026-09-29, from a
     side-by-side of four curves) as "F". History: 1.9.13 had three motions on
     three curves; 1.9.14/15 used ease-out beziers (a kick off the mark and a
     third of the time crawling the last 5%); 1.9.16-18 used minimum-jerk,
     10t^3-15t^4+6t^5, which is symmetric — ~75ms with nothing visible, then
     90% in the next ~200ms at nearly twice the average speed ("too slow AND
     too fast"). A critically damped spring felt best at the start but never
     truly arrives: its last 3% took ~160ms ("it has to think about the final
     position"). This curve keeps the spring's launch (10% at ~9% of the
     time) and covers its last 3% in ~a fifth of the time, ending at rest.

     No frame is held back any more (motion-starts-after-the-state-frame):
     that wait kept a 40ms first frame from jumping an ease-out ramp ~30%,
     but it also put the card a
     frame or two behind the CSS fades, which start at once (a lead of ~80ms
     in WebKit: the second beat again). And each ramp's clock starts at the
     change itself (performance.now()), as a CSS transition's does, not at its
     first frame: WebKit's first frame after a focus change takes ~40ms, which
     the ramps used to lose and the fades did not.

     Duration follows distance, as a hand's does (Fitts): ~430-460ms for a
     neighbour, up to 560ms across the outline (_flyMs, set by flyTo). */
  var _altoCurve=(function(){                       // B(1.4,2.6) as a cumulative table
    var M=1000, c=[0], s=0, i, x;
    for(i=0;i<M;i++){ x=(i+0.5)/M; s+=Math.pow(x,0.4)*Math.pow(1-x,1.6); c.push(s); }
    for(i=0;i<=M;i++) c[i]/=s;
    return c;
  })();
  function _altoEase(p){
    if(p<=0) return 0; if(p>=1) return 1;
    var f=p*1000, i=Math.floor(f);
    return _altoCurve[i]+(_altoCurve[i+1]-_altoCurve[i])*(f-i);
  }
  /* The board's pan (flyTo): the CSS translate property on #world through
     --pan-x/--pan-y. A layout offset (left/top) re-laid the whole board every
     frame — WebKit frames of 48-68ms. A transform is the compositor's, but
     one between device pixels softens text in Safari (1.8.28), so the pan is
     rounded to whole DEVICE pixels (CSS px x page zoom x dpr): the board
     lands on the pixel grid on every frame, as crisp as a layout offset. */
  var _pan={x:0,y:0};
  function _devPx(v){
    var z=(parseFloat(getComputedStyle(document.documentElement).zoom)||1)*(window.devicePixelRatio||1);
    return Math.round(v*z)/z;
  }
  function _setPan(x,y){
    var w=document.getElementById('world'); if(!w) return;
    x=_devPx(x); y=_devPx(y);
    if(x===_pan.x && y===_pan.y) return;
    _pan.x=x; _pan.y=y;
    if(!x && !y){ w.style.removeProperty('--pan-x'); w.style.removeProperty('--pan-y'); return; }
    w.style.setProperty('--pan-x',x+'px'); w.style.setProperty('--pan-y',y+'px');
  }
  window._altoPan=function(){ return {x:_pan.x, y:_pan.y}; };
  /* The fades' duration (see the --alto-fly CSS): set for this focus change,
     back to 250ms once it has landed. Running transitions keep the duration
     they started with, so resetting early never cuts one short. */
  var _flyT=null;
  function _fadeClock(ms){
    canvas.style.setProperty('--alto-fly', ms+'ms');
    clearTimeout(_flyT);
    _flyT=setTimeout(function(){ canvas.style.removeProperty('--alto-fly'); }, ms+60);
  }
  function _flyMs(dist){ return Math.round(Math.max(420, Math.min(560, 400+0.1*dist))); }
  var FOCUS_MS=420, UNFOCUS_MS=340;
  function _cardOf(el){ return (el && el.querySelector) ? el.querySelector('.node-card') : null; }
  function _setZoom(card,k){ if(!card) return; card.style.zoom = (k>1.0005) ? String(k) : ''; _shadowSync(card.parentNode); }
  function _zoomRamp(el,to,dur){
    var card=_cardOf(el); if(!card) return;
    if(_zw){
      cancelAnimationFrame(_zw); _zw=null;
      // never strand a half-ramped card when focus moves before the ramp lands
      if(_zwCard && _zwCard!==card) _setZoom(_zwCard,_zwTo);
    }
    _zwCard=card; _zwTo=to;
    var from=parseFloat(card.style.zoom)||1, s=performance.now(), warm=false;
    if(Math.abs(to-from)<0.002){ _setZoom(card,to); return; }
    function step(ts){
      if(warm){ warm=false; _zw=requestAnimationFrame(step); return; }   // see motion-starts-after-the-state-frame
      if(s===null) s=ts;
      var p=Math.min(1,(ts-s)/dur), e=_altoEase(p);   // the shared curve (motion-one-body)
      _setZoom(card, from+(to-from)*e);
      if(p<1) _zw=requestAnimationFrame(step); else { _zw=null; _setZoom(card,to); }
    }
    _zw=requestAnimationFrame(step);
  }

  /* The card focus leaves (an arrow hop, a swipe, a click on another) glides
     home — shrinking and sliding back with the glide — instead of snapping, which
     read as a glitch on every hop. */
  function _release(p){
    var card=_cardOf(p), z0=parseFloat(card&&card.style.zoom)||1, fx=p._fx||0, fy=p._fy||0, s0=performance.now(), warm=false;
    if(p._rel) cancelAnimationFrame(p._rel);
    _quietShadow(card,FOCUS_MS); _focusShadow(p,null);
    function step(ts){
      if(p.classList.contains('focused')){ p._rel=null; return; }   // focused again mid-way
      if(warm){ warm=false; p._rel=requestAnimationFrame(step); return; }
      if(s0===null) s0=ts;
      var t=Math.min(1,(ts-s0)/FOCUS_MS), e=_altoEase(t);   // in step with the glide
      _setZoom(card, z0+(1-z0)*e);
      _place(p, fx*(1-e), fy*(1-e));
      if(t<1) p._rel=requestAnimationFrame(step);
      else { p._rel=null; _place(p,0,0); _setZoom(card,1); }
    }
    p._rel=requestAnimationFrame(step);
  }
  function _place(el,x,y){ if(window._altoPlace) window._altoPlace(el,x,y); _shadowSync(el); }
  /* The card's resting shadow comes back at once as it leaves focus, not by
     its .28s transition: animated on a card that is shrinking, it re-blurred
     every frame. */
  function _quietShadow(card,ms){
    if(!card) return; clearTimeout(card._qs);
    card.style.transition='opacity '+ms+'ms cubic-bezier(.25,.2,.4,1), border-color .2s';
    card._qs=setTimeout(function(){ card.style.transition=''; },ms+40);
  }
  /* The enlarged card's shadow: one element per focused card, the size the
     card will be at FOCUS_K (its unzoomed box x FOCUS_K), drawn once and then
     only faded, scaled and moved — all on the compositor, so Safari never
     re-blurs it. at: truthy to show, null to let it follow the card down and
     go when the card is back to 1x. */
  function _focusShadow(el,at){
    var sh=el._fsh;
    if(!at){ if(sh){ sh._leaving=true; _shadowSync(el); } return; }
    var world=document.getElementById('world'), card=_cardOf(el);
    if(!world || !card) return;
    /* Measure the card AT the enlarged zoom, not at 1x: a description that sits
       on a line-wrap boundary re-wraps as the zoom grows (glyph advances round
       differently), so its 1x height can be a line taller than its enlarged one.
       Sized from the 1x box the shadow ran ~30px past the card, above and below,
       until the landing re-sized it (Civ Pro "The Erie Doctrine"). Style writes
       + one layout read, restored before any paint. */
    var z0=card.style.zoom; card.style.zoom=String(FOCUS_K);
    var w=card.offsetWidth, h=card.offsetHeight;        // the card's own box at FOCUS_K
    card.style.zoom=z0;
    if(!w || !h) return;
    var ax=parseFloat(el.style.left), ay=parseFloat(el.style.top); if(isNaN(ax)||isNaN(ay)) return;
    if(!sh){ sh=document.createElement('div'); sh.className='alto-fshadow'; world.appendChild(sh); el._fsh=sh; }
    sh._leaving=false;
    var W=w*FOCUS_K, H=h*FOCUS_K, key=[W,H,ax,ay].join();
    if(sh._key!==key){                                // unchanged: never re-drawn
      sh._key=key; sh._g=[ax-W/2, ay-H/2];
      sh.style.width=W+'px'; sh.style.height=H+'px';
    }
    _shadowSync(el);
  }
  /* The shadow never has a clock of its own: every frame it takes the card's
     own zoom (its size and strength) and offset (where it is), so it cannot
     arrive before the card does — a shadow on its own timeline, full-size
     round a card that had not grown yet, showed as a phantom frame (1.9.4). */
  function _shadowSync(n){
    var sh=n && n._fsh; if(!sh) return;
    var card=_cardOf(n), z=parseFloat(card&&card.style.zoom)||1, t=Math.max(0,Math.min(1,(z-1)/(FOCUS_K-1)));
    if(sh._leaving && z<=1.0005){ sh.remove(); n._fsh=null; return; }
    sh.style.opacity=String(t);
    /* at full size it is placed by layout, snapped like the card (a fractional
       translate left a faint seam along the card's lower edge); growing or
       shrinking, by a transform off its full-size spot */
    var g=sh._g, fx=n._fx||0, fy=n._fy||0, full=Math.abs(z-FOCUS_K)<1e-4;
    sh.style.left=(g[0]+(full?fx:0))+'px'; sh.style.top=(g[1]+(full?fy:0))+'px';
    sh.style.transform=full?'none':'translate('+fx+'px,'+fy+'px) scale('+(z/FOCUS_K)+')';
  }


  /* flyTo's duration, planned BEFORE any class changes: the classes start the
     fades, and flyTo's own layout reads would start them before it could say
     how long they should take (they ran at 250ms while the card grew over
     ~420ms — the two beats again). Same arithmetic as flyTo. */
  function _flyPlanMs(el){
    var cw=canvas.clientWidth, ch=canvas.clientHeight, a=_canvasXY(el);
    var qx=_scrollAxis('scrollLeft'), qy=_scrollAxis('scrollTop');
    var tl=qx.stop(_clamp(Math.round(a.x-cw/2),0,Math.max(0,canvas.scrollWidth-cw)));
    var tt=qy.stop(_clamp(Math.round(a.y-ch/2),0,Math.max(0,canvas.scrollHeight-ch)));
    var px=-(a.x-(tl+cw/2)), py=-(a.y-(tt+ch/2));
    var dx=(tl-qx.at())-(px-_pan.x), dy=(tt-qy.at())-(py-_pan.y);
    return _flyMs(Math.sqrt(dx*dx+dy*dy));
  }
  function enterFocus(id){
    if(!id) return; var el=nodeEl(id); if(!el) return;
    _fadeClock(FOCUS_MS=window._altoFlyMs=_flyPlanMs(el));
    if(el._rel){ cancelAnimationFrame(el._rel); el._rel=null; }
    el._hov=null;                                       // enlarged: centred, not grown from its top
    var p=null;
    if(window._focusedNodeId && window._focusedNodeId!==id){ p=nodeEl(window._focusedNodeId); if(p){ p.classList.remove('crisp'); p.classList.remove('focused'); } }
    window._focusedNodeId=id;
    canvas.classList.add('focus-mode');
    el.classList.add('focused');
    _wheelSync();
    // flyTo first: it sets FOCUS_MS from the distance. All three start on the
    // same (next) frame whatever their order here — each waits a frame (warm).
    flyTo(el);
    _zoomRamp(el,FOCUS_K,FOCUS_MS);
    if(p) _release(p);
  }"""

_FOCUS_EXIT_OLD = """      el.classList.remove('focused');
      flyBack(el);"""
_FOCUS_EXIT_NEW = """      el.classList.remove('focused');
      _quietShadow(_cardOf(el),UNFOCUS_MS); _focusShadow(el,null);
      _zoomRamp(el,1,UNFOCUS_MS);
      flyBack(el);"""

# ── the world fits the window instead of being pinned at 0.8 ────────────────
# #world is authored 1700px wide (five columns), and html{zoom:0.8} shrank it to
# 1360 so it would fit a 1512px laptop. That pinned every reader to 0.8 — a
# 1920px monitor with 220px of slack included, where Alto's Georgia body text
# lands at 10 device pixels and reads as blurry on a 1x display.
#
# Scale to fit: clamp(innerWidth / 1700, 0.8, 1.0). The floor is the 0.8 the
# stylesheet already sets, so no window is worse off than today; the ceiling is
# the design's own native size. Three parts:
#   1. the rule keeps 0.8 and gains --alto-zoom, so a JS-off page is unchanged;
#   2. a <head> script picks the scale before any layout exists;
#   3. Blink's viewport-fill compensations divide by the chosen scale, not 0.8.
#
# (3) is the one that would have broken quietly. Chrome computes 100vw/100vh
# against the DEVICE viewport and ignores the root zoom, so the engine divides
# by 0.8 to recover CSS px. Left hardcoded, a zoom of 1.0 makes <body> 125% of
# the window in Chrome — a quarter of the canvas pushed out of reach and the
# open Overview panel overflowing the bottom. Safari 18 and earlier zoom-adjust
# vw/vh and never had the bug; Safari 26+ implements standardized zoom and has
# it exactly like Chrome — see the safari-standard-zoom patch below, which
# gives it the same compensation via html.vw-unzoomed.
_FIT_RULE_OLD = "  html{zoom:0.8;}\n"
_FIT_RULE_NEW = (
    "  /* A floor, not a fixed size: #alto-fit (end of <head>) raises this toward\n"
    "     1.0 when the window can hold the world's full 1700px, and publishes its\n"
    "     choice as --alto-zoom. With JS off both stay at 0.8 — today's page. */\n"
    "  html{zoom:0.8; --alto-zoom:0.8;}\n")

_FIT_SCRIPT_OLD = "</head>\n<body>"
_FIT_SCRIPT_NEW = """<script id="alto-fit">
/* Pick the root zoom from the window, before any layout exists.

   Measures at zoom 1 rather than trusting window.innerWidth to be
   zoom-invariant. It is in Blink, but if a browser ever divides it by the root
   zoom instead, inferring from a zoomed reading would let the scale oscillate
   between two values on every resize. Measuring at a known scale cannot.

   Mobile is skipped outright: it already forces zoom:1 !important and lays out
   on its own single-column grid, where 1700 means nothing. */
(function(){
  var d = document.documentElement;
  if (d.classList.contains('mobile')) return;
  var NEED = 1700, MIN = 0.8, MAX = 1;
  function fit(){
    d.style.zoom = '1';
    void d.offsetWidth;                       // flush, so innerWidth is read at scale 1
    var k = Math.min(MAX, Math.max(MIN, window.innerWidth / NEED));
    d.style.setProperty('--alto-zoom', String(k));
    d.style.zoom = (k > MIN) ? String(k) : '';   // '' falls back to the stylesheet's 0.8
  }
  fit();
  var t = null;
  window.addEventListener('resize', function(){
    if (t) clearTimeout(t);
    // ahead of centreWorld (120ms) and the d-grid quantizer (160ms), both of
    // which measure the scale themselves and so re-settle onto the new one.
    t = setTimeout(fit, 100);
  });
})();
</script>
</head>
<body>"""

_FIT_BLINK_OLD = """html.is-blink:not(.mobile) body{
  width:calc(100vw / 0.8) !important;
  height:calc(100vh / 0.8) !important;
}"""
_FIT_BLINK_NEW = """html.is-blink:not(.mobile) body,
html.vw-unzoomed:not(.mobile) body{
  width:calc(100vw / var(--alto-zoom, 0.8)) !important;
  height:calc(100vh / var(--alto-zoom, 0.8)) !important;
}"""

_FIT_SLAB_OLD = (
    "html.is-blink:not(.mobile) #glass-slab{ width:max(1700px, calc(100vw / 0.8)) !important; }\n"
    "html.is-blink:not(.mobile) #summary-wrap.open{\n"
    "  max-height:calc(100vh / 0.8 - 104px) !important;\n"
    "  height:calc(100vh / 0.8 - 104px) !important;\n"
    "}")
_FIT_SLAB_NEW = (
    "html.is-blink:not(.mobile) #glass-slab,\n"
    "html.vw-unzoomed:not(.mobile) #glass-slab{ width:max(1700px, calc(100vw / var(--alto-zoom, 0.8))) !important; }\n"
    "html.is-blink:not(.mobile) #summary-wrap.open,\n"
    "html.vw-unzoomed:not(.mobile) #summary-wrap.open{\n"
    "  max-height:calc(100vh / var(--alto-zoom, 0.8) - 104px) !important;\n"
    "  height:calc(100vh / var(--alto-zoom, 0.8) - 104px) !important;\n"
    "}")

# ── Safari 26+ renders the timeline at 80% of the window ────────────────────
# Safari 26 adopted standardized CSS zoom, the model Chrome moved to earlier:
# 100vw/100vh resolve against the unzoomed viewport, so under the root zoom
# <body> covers only zoom×window — a blank strip down the right and across the
# bottom, the canvas cut short. The engine gates its viewport-fill compensation
# on .is-blink (a UA sniff), so Safari never received it.
#
# Detected by behaviour, not UA — Safari 18 and earlier zoom-adjust vw and must
# NOT be compensated. Compare a 100vw probe with a fixed left:0/right:0 probe
# (the true viewport) under a forced zoom of 0.5: standardized engines measure
# 0.5, legacy ones 1.0 or more, whatever zoom the stylesheet or #alto-fit
# picked. Blink keeps its own class and is skipped. The fit-blink patches above
# give html.vw-unzoomed the same rules; Safari's glass rules are untouched.
_SAFARI_ZOOM_OLD = (
    "  if(/Chrome\\//.test(navigator.userAgent)) "
    "document.documentElement.classList.add('is-blink');\n")
_SAFARI_ZOOM_NEW = _SAFARI_ZOOM_OLD + """  // Safari 26+: standardized zoom, same vw/vh behaviour as Blink (see
  // engine_patches.py, safari-standard-zoom). Measured, not sniffed.
  (function(){
    var de = document.documentElement;
    if(de.classList.contains('mobile') || de.classList.contains('is-blink')) return;
    function probe(){
      var z = de.style.zoom;
      var a = document.createElement('div'), b = document.createElement('div');
      a.style.cssText = 'position:fixed;left:0;top:0;width:100vw;height:0;visibility:hidden;pointer-events:none;';
      b.style.cssText = 'position:fixed;left:0;right:0;top:0;height:0;visibility:hidden;pointer-events:none;';
      de.style.zoom = '0.5';
      de.appendChild(a); de.appendChild(b);
      var va = a.offsetWidth, vb = b.offsetWidth;
      de.removeChild(a); de.removeChild(b);
      de.style.zoom = z;
      if(!va || !vb) return false;          // 0x0 viewport (hidden) — try again later
      if(va / vb < 0.75) de.classList.add('vw-unzoomed');
      return true;
    }
    var done = probe();
    function retry(){ if(!done) done = probe(); }
    if(!done){
      document.addEventListener('DOMContentLoaded', retry);
      window.addEventListener('load', retry);
      window.addEventListener('resize', retry);
    }
  })();
"""

# ── D-GRID: desktop nodes are centred by layout, not by a transform ─────────
# Every node was centred on its (left, top) point by translate(-50%,-50%). A
# transform is applied on top of layout WITHOUT being snapped to device pixels,
# so at any fit zoom between 0.8 and 1 — every window from 1366 to 1700px wide —
# half a card's size lands a node between device pixels. Two visible results:
#   * Safari: a card is its own GPU layer (its backdrop-filter), and WebKit
#     bilinear-resamples an off-grid layer, softening all its text. Chrome
#     drops backdrop-filter under the root zoom, so it was Safari-only.
#   * both engines: a 1px chip outline straddling two device rows reads as a
#     frame half hidden behind the card.
# The old quantize pass nudged Y by measuring getBoundingClientRect, on Blink
# only (Safari "unverified"; 1.8.27 widened it to Safari 26+). Measuring is the
# wrong model: the engines combine layout and transform fractions differently,
# and on painted pixels no rect-based or transform-based nudge was crisp in
# both (Playwright WebKit 26.6 + Chromium, 1x and 2x, 1366..1920px).
#
# Centring by margins instead (-w/2, -h/2) makes the offset part of layout,
# which both engines snap to device pixels themselves: in the same test every
# chip border and card edge painted on-grid, at every width, dpr and scroll.
# A ResizeObserver keeps the margins current (fonts, relayout, the focus zoom
# ramp). A node with an inline transform — the focus fly — drops the margins
# and uses its transform exactly as before, so enlarged cards are unchanged.
# The engine functions that read offsetLeft/offsetTop as a node's centre
# (focus fly, search scroll) subtract the margin back out (dgrid-centre-*),
# which is also correct on mobile, where there is none; arrow-key navigation
# reads style.left/top (arrows-follow-the-layout).
_DGRID_SCRIPT_OLD = """<script id="d-grid-quantize">
/* D-GRID quantize (2026-07-25, desktop only): translate(-50%) of a fractional
   card height leaves the card top on a fractional device pixel — every glyph in
   the card then rasters off-grid (visible smear on 1× displays under zoom:.8).
   Snap each node's Y onto the device grid via --qy. getBoundingClientRect is
   post-zoom here, so rect coords ARE device-visual px. */
(function(){
  if(document.documentElement.classList.contains('mobile')) return;
  if(!document.documentElement.classList.contains('is-blink')) return;  /* Safari: unverified geometry */
  var Z=0.8;
  function q(){
    /* effective visual scale, MEASURED (survives html-zoom or browser-zoom changes) */
    var c=document.querySelector('.node-card');
    if(c&&c.offsetWidth){ var rr=c.getBoundingClientRect().width/c.offsetWidth; if(rr>0.1&&rr<10) Z=rr; }
    var nodes=document.querySelectorAll('.node');
    for(var i=0;i<nodes.length;i++){ var n=nodes[i];
      if(n.style.transform) continue;                 /* mid-fly/focused: leave alone */
      n.style.setProperty('--qy','0px');
      var r=n.getBoundingClientRect();
      var d=(Math.round(r.top)-r.top)/Z;
      if(d>0.005||d<-0.005) n.style.setProperty('--qy',d.toFixed(3)+'px');
    }
  }
  function qq(){ q(); requestAnimationFrame(function(){ requestAnimationFrame(q); }); }
  /* background-tab loads: rAF is paused until the tab fronts — the sync q() above
     covers the hidden case; the double-rAF re-snaps after any pending layout. */
  document.addEventListener('visibilitychange',function(){ if(!document.hidden) qq(); });
  window.__altoQuantize=qq;
  window.addEventListener('load',qq);
  window.addEventListener('resize',function(){ clearTimeout(window.__qt); window.__qt=setTimeout(qq,160); });
  if(document.fonts&&document.fonts.ready&&document.fonts.ready.then) document.fonts.ready.then(qq);
  var _ef=window.exitFocus;
  if(typeof _ef==='function') window.exitFocus=function(){ var r=_ef.apply(this,arguments); setTimeout(qq,400); return r; };
  qq();
})();
</script>"""
_DGRID_SCRIPT_NEW = """<style id="d-grid-centre">
html:not(.mobile) #world .node.dg:not([style*="transform"]){
  transform:none; margin:calc(var(--my,0px) + var(--fy,0px)) 0 0 calc(var(--mx,0px) + var(--fx,0px));
}
</style>
<script id="d-grid-quantize">
/* D-GRID (1.8.28): centre desktop nodes with margins so layout, which every
   engine snaps to device pixels, places them. See engine_patches.py. */
(function(){
  var de=document.documentElement;
  if(de.classList.contains('mobile')) return;
  var world=document.getElementById('world'); if(!world) return;
  function centre(n){
    if(!n.offsetWidth) return;
    n.style.setProperty('--mx',(-n.offsetWidth/2)+'px');
    /* a hovered card grows downward from its resting top (n._hov: rest height);
       an enlarged one is centred whatever hover it was caught in (a pinch on
       the card under the pointer left it 50px low, its shadow showing above) */
    var hov=n._hov!=null && !n.classList.contains('focused');
    n.style.setProperty('--my',(-(hov?n._hov:n.offsetHeight)/2)+'px');
  }
  var ro=(typeof ResizeObserver==='function')
    ? new ResizeObserver(function(es){ es.forEach(function(e){ centre(e.target); }); }) : null;
  function adopt(n){
    if(!n.classList || !n.classList.contains('node') || n._dg) return;
    n._dg=1; centre(n); n.classList.add('dg'); if(ro) ro.observe(n);
  }
  function sweep(){
    if(de.classList.contains('mobile')) return;
    [].forEach.call(world.querySelectorAll('.node'),function(n){ if(n._dg) centre(n); else adopt(n); });
  }
  /* renderTimeline rebuilds every .node; adopt them as they arrive */
  if(typeof MutationObserver==='function')
    new MutationObserver(function(ms){ ms.forEach(function(m){ [].forEach.call(m.addedNodes,adopt); }); })
      .observe(world,{childList:true});
  /* The enlarged node is moved off its anchor — only where the canvas can't
     scroll far enough to centre it — by --fx/--fy, which the margins above add
     in. It stays in layout the whole way, snapped like every other node, and
     never takes a transform: that made Safari build a new layer for it at the
     start of every hop (a 15-30ms first frame) and snap by a fraction as it
     switched to margins on landing and back on leaving (1.8.29-1.9.3). */
  window._altoPlace=function(el,fx,fy){
    if(!el) return;
    if(Math.abs(fx)<0.005 && Math.abs(fy)<0.005){
      el._fx=el._fy=0; el.style.removeProperty('--fx'); el.style.removeProperty('--fy'); return;
    }
    el._fx=fx; el._fy=fy;
    el.style.setProperty('--fx',fx+'px'); el.style.setProperty('--fy',fy+'px');
  };
  /* Hover enlarge by CSS zoom, ramped, not transform:scale — a scaled card is
     a transform again (off-grid, soft text), a zoomed one is laid out at its
     new size and lands on the grid like any other. The card is a fixed width,
     so nothing re-wraps. Its top stays put (centre() above), so it grows down
     into the gap below as the scale always did. A focused card is left to the
     focus ramp, which starts from whatever zoom this left it at. */
  var HK=1.08, HMS=160;
  function hoverRamp(n,c,to){
    if(n._hr) cancelAnimationFrame(n._hr);
    var from=parseFloat(c.style.zoom)||1, t0=null;
    function step(ts){
      if(n.classList.contains('focused')){ n._hr=null; n._hov=null; return; }
      if(t0===null) t0=ts;
      var p=Math.min(1,(ts-t0)/HMS), e=1-(1-p)*(1-p), z=from+(to-from)*e;
      c.style.zoom=(Math.abs(z-1)<0.0005)?'':String(z);
      if(p<1) n._hr=requestAnimationFrame(step);
      else { n._hr=null; if(to===1){ n._hov=null; centre(n); } }
    }
    n._hr=requestAnimationFrame(step);
  }
  function cardOf(t){ return t&&t.closest ? t.closest('#world .node-card') : null; }
  function grow(c){
    var n=c.closest('.node'); if(!n || n._hovOn || n.classList.contains('focused')) return;
    n._hovOn=1; if(n._hov==null) n._hov=n.offsetHeight;
    hoverRamp(n,c,HK);
  }
  /* Only the pointer moving grows a card. When the canvas moves under a still
     pointer (a scroll, an arrow hop's glide) the browser reports each card
     that slides beneath it as hovered, and they pulsed past the pointer one
     after another. Such a hover is content moving: same pointer position,
     canvas moved since. A card the pointer is resting on when the canvas stops
     grows on the pointer's next move. window._altoPointerStill(e) tells the
     line hover the same thing. */
  var px=null, py=null, still=false;
  function moved(){ still=true; }
  var cv=document.getElementById('canvas');
  if(cv) cv.addEventListener('scroll',moved,{passive:true});
  window.addEventListener('wheel',moved,{passive:true,capture:true});
  window.addEventListener('keydown',moved,true);
  window._altoPointerStill=function(e){ return still && e.clientX===px && e.clientY===py; };
  function track(e){
    if(e.clientX===px && e.clientY===py) return false;
    px=e.clientX; py=e.clientY; var was=still; still=false; return was;
  }
  document.addEventListener('mouseover',function(e){
    if(de.classList.contains('mobile') || window._altoPointerStill(e)) return;
    track(e);
    var c=cardOf(e.target); if(c) grow(c);
  });
  document.addEventListener('mousemove',function(e){
    if(!track(e) || de.classList.contains('mobile')) return;
    var c=cardOf(e.target); if(c) grow(c);    /* first move after the canvas stopped */
  });
  document.addEventListener('mouseout',function(e){
    var c=cardOf(e.target); if(!c || c.contains(e.relatedTarget)) return;
    var n=c.closest('.node'); if(!n || !n._hovOn) return;
    n._hovOn=0; if(!n.classList.contains('focused')) hoverRamp(n,c,1);
  });
  window.__altoQuantize=sweep;
  window.addEventListener('load',sweep);
  if(document.fonts&&document.fonts.ready&&document.fonts.ready.then) document.fonts.ready.then(sweep);
  sweep();
})();
</script>"""

# The hover rule's transform:scale(1.08) is replaced by the zoom ramp above.
_DGRID_HOVER_OLD = ("html:not(.mobile) .node:not(.focused) .node-card:hover{\n"
                    "  transform: scale(1.08);\n}")
_DGRID_HOVER_NEW = ("html:not(.mobile) .node:not(.focused) .node-card:hover{\n"
                    "  transform: none;   /* D-GRID: enlarged by a zoom ramp, see d-grid-quantize */\n}")

# ── the fly scrolls in steps the canvas can actually take ──────────────────
# Safari keeps a scroll offset in whole layout px and, under the page's CSS
# zoom, floors a written scrollTop twice: 14 reads back 13, 100 reads 99. Every
# enlarge or arrow hop therefore started with the whole canvas stepping 1px
# BACKWARDS, then glided in uneven steps (up to ~1.8px off the curve) — the
# neighbours twitched as a new card came to the centre. Measured in Safari
# 26.6 (zoom 0.8647, dpr 2) and Playwright WebKit (zoom 0.8) alike. Each frame
# now writes the value that lands on the whole layout px nearest the curve,
# the start is read back exactly, and the fly ends where the canvas can stop,
# so the enlarged card's residual centres it on the real final offset. Blink
# scrolls fractionally and is written as before.
_FLY_SCROLL_OLD = """    var tl=_clamp(Math.round(a.x-cw/2),0,Math.max(0,canvas.scrollWidth-cw));
    var tt=_clamp(Math.round(a.y-ch/2),0,Math.max(0,canvas.scrollHeight-ch));
    var rx=a.x-(tl+cw/2), ry=a.y-(tt+ch/2);   // residual to truly centre
    el._fx=-rx; el._fy=-ry;
    var l0=canvas.scrollLeft,t0=canvas.scrollTop;
    _animate(420,function(k){
      canvas.scrollLeft=l0+(tl-l0)*k; canvas.scrollTop=t0+(tt-t0)*k;
      el.style.transform='translate(-50%,-50%) translate('+(-rx*k)+'px,'+(-ry*k)+'px)';"""
_FLY_SCROLL_NEW = """    // Where the card sits on the board at rest (_canvasXY reads layout, which
    // the pan's transform does not change).
    var ax=a.x, ay=a.y;
    var qx=_scrollAxis('scrollLeft'), qy=_scrollAxis('scrollTop');
    var tl=qx.stop(_clamp(Math.round(ax-cw/2),0,Math.max(0,canvas.scrollWidth-cw)));
    var tt=qy.stop(_clamp(Math.round(ay-ch/2),0,Math.max(0,canvas.scrollHeight-ch)));
    // What scrolling cannot cover (the board fits the window's width, and
    // stops at its ends) the board is PANNED by (_setPan): the whole scene
    // moves as one piece, like a camera, and the card only grows where it
    // sits. It used to slide across the board by itself (--fx/--fy) while the
    // board scrolled under it — two drags at once (Luke, 1.9.16).
    var px=-(ax-(tl+cw/2)), py=-(ay-(tt+ch/2));
    var fx0=el._fx||0, fy0=el._fy||0, px0=_pan.x, py0=_pan.y;
    _focusShadow(el,true);
    var l0=qx.at(),t0=qy.at();
    // how far the eye travels: the board, scrolled and panned
    var dx=(tl-l0)-(px-px0), dy=(tt-t0)-(py-py0);
    FOCUS_MS=window._altoFlyMs=_flyMs(Math.sqrt(dx*dx+dy*dy));
    _fadeClock(FOCUS_MS);
    _animate(FOCUS_MS,function(k){
      qx.go(l0+(tl-l0)*k); qy.go(t0+(tt-t0)*k);
      _setPan(px0+(px-px0)*k, py0+(py-py0)*k);
      if(fx0||fy0) _place(el, fx0*(1-k), fy0*(1-k));"""
# On landing, the shadow is checked against the card as it now is.
_FLY_LAND_OLD = "      // settle: optionally swap the transform scale for a CSS-zoom re-raster\n"
_FLY_LAND_NEW = ("      if(window._focusedNodeId && el.id==='node-'+window._focusedNodeId) _focusShadow(el,true);\n"
                 + _FLY_LAND_OLD)
_FLY_BACK_OLD = """    if(!fx&&!fy){ el.style.transform=''; return; }
    _animate(300,function(k){ el.style.transform='translate(-50%,-50%) translate('+(fx*(1-k))+'px,'+(fy*(1-k))+'px)'; },
      function(){ el.style.transform=''; el._fx=el._fy=0; });"""
_FLY_BACK_NEW = """    var px0=_pan.x, py0=_pan.y;
    if(!fx&&!fy&&!px0&&!py0){ _place(el,0,0); return; }
    // the board glides back to rest, as one piece (see flyTo)
    _animate(UNFOCUS_MS,function(k){ _place(el, fx*(1-k), fy*(1-k)); _setPan(px0*(1-k), py0*(1-k)); },
      function(){ _place(el,0,0); _setPan(0,0); });"""
_FLY_AXIS_OLD = "  function flyTo(el){\n"
_FLY_AXIS_NEW = """  /* Safari stores the canvas offset in whole layout px and turns a written
     value v into floor(floor(v)*z) of them (z = the page's CSS zoom), so it
     reads back short and uneven. pos(n) is where writing the integer n really
     puts the canvas, in CSS px. (engine_patches.py, fly-scrolls-in-whole-px) */
  var _wk=/AppleWebKit/.test(navigator.userAgent) && !document.documentElement.classList.contains('is-blink');
  function _scrollAxis(prop){
    if(!_wk) return { at:function(){ return canvas[prop]; }, stop:function(v){ return v; },
                      go:function(v){ canvas[prop]=v; } };
    var de=document.documentElement, z=(parseFloat(getComputedStyle(de).zoom)||1)*(parseFloat(getComputedStyle(document.body).zoom)||1);
    function pos(n){ return Math.floor(n*z+1e-6)/z; }
    function near(v){                      // the write whose landing is nearest v
      var best=Math.floor(v), bd=Infinity;
      for(var n=Math.floor(v)-1;n<=Math.ceil(v)+1;n++){ var d=Math.abs(pos(n)-v); if(d<bd-1e-9){ bd=d; best=n; } }
      return best;
    }
    var c=canvas['_q'+prop];
    return {
      at:function(){                       // the exact offset the canvas is at now
        var r=canvas[prop];
        if(c && c.r===r) return c.p;
        if(z<1){ var P=Math.ceil(r*z-1e-6); if(Math.floor(P/z+1e-6)===r) return P/z; }
        return r;
      },
      stop:function(v){ return pos(near(v)); },
      go:function(v){
        var n=near(v); canvas[prop]=n;
        c=canvas['_q'+prop]={p:pos(n), r:Math.floor(pos(n)+1e-6)};
      }
    };
  }
  function flyTo(el){
"""

# ── the scroll tint restyles the bars, not the whole page ───────────────────
# The desktop top bars take the era colour under them as the canvas scrolls,
# by a custom property written on <html> every scroll frame. A custom property
# on the root is inherited by every element, so each write restyled the whole
# page: 52 full restyles (~4.3ms each) in a two-second scroll in Chromium, the
# same on every frame of an arrow hop's glide. Only #title-bar, #nav and
# #node-nav-bar read it on desktop, so it is set on those three, and only
# when the colour actually changes.
_TINT_SCOPE_OLD = """    if(!rgb){ root.style.removeProperty('--header-tint'); _setBrandTone(null,0); return; }
    var a=root.classList.contains('dark')?ALPHA_DARK:ALPHA_LIGHT;
    root.style.setProperty('--header-tint','rgba('+rgb[0]+','+rgb[1]+','+rgb[2]+','+a+')');
    _setBrandTone(rgb,a);
  }
  window.updateHeaderTint=updateHeaderTint;"""
_TINT_SCOPE_NEW = """    if(!rgb){ _tint(''); _setBrandTone(null,0); return; }
    var a=root.classList.contains('dark')?ALPHA_DARK:ALPHA_LIGHT;
    _tint('rgba('+rgb[0]+','+rgb[1]+','+rgb[2]+','+a+')');
    _setBrandTone(rgb,a);
  }
  /* on the three bars that read it, not <html> (engine_patches.py,
     scroll-tint-on-the-bars): a root custom property restyles every element */
  function _tint(v){
    if(root.style.getPropertyValue('--header-tint')) root.style.removeProperty('--header-tint');
    ['title-bar','nav','node-nav-bar'].forEach(function(id){
      var el=document.getElementById(id); if(!el || el.style.getPropertyValue('--header-tint')===v) return;
      if(v) el.style.setProperty('--header-tint',v); else el.style.removeProperty('--header-tint');
    });
  }
  window.updateHeaderTint=updateHeaderTint;"""

# ── Safari scrolls the canvas off the main thread again ────────────────────
# One non-passive wheel listener on window (focus-mode nav, the Notes swipe,
# and Chrome's ctrl+wheel pinch) made every scroll wait for the main thread:
# while anything ran there — a hop, a ramp, a restyle — the canvas stalled.
# Safari pinches with gesture events, blocked separately, so there the
# listener only has to be able to cancel while a card is enlarged or Notes is
# open; the rest of the time it is passive and Safari scrolls on its own
# thread. Blink keeps it non-passive (ctrl+wheel), and only its first wheel
# event in a gesture waits anyway.
# ── motion starts after the frame that changes state ────────────────────────
# Enlarging a card or hopping restyles two cards, re-cuts the lines under the
# faded ones and swaps the shadow: a first frame of 30-45ms in Safari, which
# no single piece accounts for (measured 2026-09-28). Every ramp took its
# clock from that frame, so the next frame drew 40ms of progress at once —
# with ease-out ramps, ~30% of the card's growth in one step. Each ramp now
# lets that frame pass (warm), starts its clock on the next, and moves from
# the one after: the stall happens before anything moves.
_ANIM_WARM_OLD = """    var s=null;
    function ez(p){ return p<0.5?2*p*p:1-Math.pow(-2*p+2,2)/2; }
    function step(ts){ if(s===null)s=ts; var p=Math.min(1,(ts-s)/dur),k=ez(p); cb(k); if(p<1)_tw=requestAnimationFrame(step); else if(done)done(); }"""
_ANIM_WARM_NEW = """    var s=performance.now(), warm=false;   // clock from the change, as CSS's: see motion-one-body
    function ez(p){ return _altoEase(p); }
    function step(ts){ if(warm){ warm=false; _tw=requestAnimationFrame(step); return; }
      if(s===null)s=ts; var p=Math.min(1,(ts-s)/dur),k=ez(p); cb(k); if(p<1)_tw=requestAnimationFrame(step); else if(done)done(); }"""
_WHEEL_EXIT_OLD = "    canvas.classList.remove('focus-mode');\n"
_WHEEL_EXIT_NEW = "    _fadeClock(UNFOCUS_MS);   // before the class change starts the fades\n    canvas.classList.remove('focus-mode');\n    _wheelSync();\n"
_WHEEL_OPEN_OLD = "  window.addEventListener('wheel', function(e){\n"
_WHEEL_OPEN_NEW = "  function _onWheel(e){\n"
_WHEEL_CLOSE_OLD = "  }, {passive:false, capture:true});\n"
_WHEEL_CLOSE_NEW = """  }
  var _wheelHold=null;                    // null: not yet registered
  function _wheelSync(){
    var np=document.getElementById('notes-panel');
    var hold=!_wk || !!window._focusedNodeId || !!(np && np.classList.contains('open'));
    if(hold===_wheelHold) return;
    if(_wheelHold!==null) window.removeEventListener('wheel', _onWheel, true);
    _wheelHold=hold;
    window.addEventListener('wheel', _onWheel, {passive:!hold, capture:true});
  }
  _wheelSync();
  (function(){ var np=document.getElementById('notes-panel');
    if(np && window.MutationObserver) new MutationObserver(_wheelSync).observe(np,{attributes:true,attributeFilter:['class']}); })();
"""

# Readers of a node's centre: offsetLeft/Top include the centring margin now.
_DGRID_CXY_OLD = "    return {x:el.offsetLeft+ox, y:el.offsetTop+oy};"
_DGRID_CXY_NEW = ("    var _cs=getComputedStyle(el);\n"
                  "    return {x:el.offsetLeft-(parseFloat(_cs.marginLeft)||0)+ox, y:el.offsetTop-(parseFloat(_cs.marginTop)||0)+oy};")
_DGRID_SRCH_OLD = ("      var top=(world?world.offsetTop:0)+node.offsetTop - cv.clientHeight/2;\n"
                   "      var left=(world?world.offsetLeft:0)+node.offsetLeft - cv.clientWidth/2;")
_DGRID_SRCH_NEW = ("      var _ns=getComputedStyle(node);\n"
                   "      var top=(world?world.offsetTop:0)+node.offsetTop-(parseFloat(_ns.marginTop)||0) - cv.clientHeight/2;\n"
                   "      var left=(world?world.offsetLeft:0)+node.offsetLeft-(parseFloat(_ns.marginLeft)||0) - cv.clientWidth/2;")



# ── chip outlines are real borders, one device pixel wide ──────────────────
# The square entity chips drew their outline as `box-shadow: inset 0 0 0 1px`,
# the tag pills the same way. A box-shadow is not snapped to device pixels, so
# at a fit zoom of 0.8..0.95 the 1px ring is 0.8..0.95 of a device pixel,
# smeared unevenly across the edge pixels: part of the frame reads as hidden
# behind the card. It looked right only at zoom 1 (a wide window) and in an
# enlarged card (zoom 1.7), which is exactly the reported pattern. Borders ARE
# snapped, in WebKit and Blink, and never drawn thinner than one device pixel.
# The width has to survive two different snaps: Blink floors width x zoom x dpr
# to device pixels, WebKit floors the width to 1/dpr BEFORE the zoom and then
# floors again when painting. round(up, 1px/zoom, 0.5px) — 1px at zoom 1, 1.5px
# below it — lands on exactly one visual pixel (1 device px at 1x, 2 at 2x) in
# both, measured in Playwright WebKit 26.6 and Chromium. Engines without CSS
# round() get 1.02px/zoom, right in Blink at any dpr and in WebKit at 1x.
# box-sizing is already border-box, so no chip changes size. Mobile untouched.
_CHIP_RULE_OLD = ("html:not(.mobile) .csym-btn{ background:var(--chip-plate) !important; "
                  "opacity:1 !important; box-shadow:inset 0 0 0 1px currentColor; }")
_CHIP_RULE_NEW = (
    "html:not(.mobile){ --chip-rule:calc(1.02px / var(--alto-zoom, 0.8)); }\n"
    "@supports (width: round(up, 1.3px, 0.5px)){\n"
    "  html:not(.mobile){ --chip-rule:round(up, calc(1px / var(--alto-zoom, 0.8) - 0.001px), 0.5px); }\n"
    "}\n"
    "html:not(.mobile) .csym-btn{ background:var(--chip-plate) !important; "
    "opacity:1 !important; border:var(--chip-rule) solid currentColor; box-sizing:border-box; }\n"
    "html:not(.mobile) .tsym-btn{ box-shadow:none; border:var(--chip-rule) solid rgba(192,132,252,.6); box-sizing:border-box; }\n"
    "html:not(.mobile) .tsym-btn:hover{ box-shadow:none; border-color:var(--theme-color); }\n"
    "html:not(.mobile) .esym-btn{ border-width:var(--chip-rule); }")


# ── mobile glyphs: Overview should carry the same mark as desktop ────────────
# Desktop's Overview control (#overview-toggle) is the four-point sparkle; the
# mobile drawer gave that sparkle to Timeline and drew Overview as a globe, so
# the same mark meant two different things depending on the device. Swap the
# drawer pair — Overview takes desktop's exact sparkle path, Timeline takes the
# globe — and move the mobile back-to-timeline button (detail pages) onto the
# globe too, since a sparkle that now means Overview cannot also mean "back to
# the timeline". Desktop chrome is untouched.
_DRAWER_TIMELINE_OLD = (
    '<button class="drawer-btn" id="drawer-timeline-btn" onclick="showTimeline();closeNavDrawer()">'
    '<span class="drawer-icon">'
    '<svg viewBox="0 0 100 100" width="22" height="22" style="display:inline-block;pointer-events:none">'
    '<polygon points="50,2 63,37 98,50 63,63 50,98 37,63 2,50 37,37" fill="currentColor"/>'
    '</svg></span><span class="drawer-label">Timeline</span></button>')
_DRAWER_TIMELINE_NEW = (
    '<button class="drawer-btn" id="drawer-timeline-btn" onclick="showTimeline();closeNavDrawer()">'
    '<span class="drawer-icon">'
    '<svg viewBox="0 0 100 100" width="22" height="22" style="display:inline-block;pointer-events:none">'
    '<circle cx="50" cy="50" r="44" fill="none" stroke="currentColor" stroke-width="7"/><ellipse cx="50" cy="50" rx="22" ry="44" fill="none" stroke="currentColor" stroke-width="6"/><line x1="6" y1="50" x2="94" y2="50" stroke="currentColor" stroke-width="6"/><path d="M14,27 Q50,18 86,27" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round"/><path d="M14,73 Q50,82 86,73" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round"/>'
    '</svg></span><span class="drawer-label">Timeline</span></button>')

_DRAWER_OVERVIEW_OLD = (
    '<button class="drawer-btn" onclick="toggleSummary();closeNavDrawer()">'
    '<span class="drawer-icon">'
    '<svg viewBox="0 0 100 100" width="20" height="20" style="display:inline-block;pointer-events:none;vertical-align:middle">'
    '<circle cx="50" cy="50" r="44" fill="none" stroke="currentColor" stroke-width="7"/><ellipse cx="50" cy="50" rx="22" ry="44" fill="none" stroke="currentColor" stroke-width="6"/><line x1="6" y1="50" x2="94" y2="50" stroke="currentColor" stroke-width="6"/><path d="M14,27 Q50,18 86,27" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round"/><path d="M14,73 Q50,82 86,73" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round"/>'
    '</svg></span><span class="drawer-label">Overview</span></button>')
_DRAWER_OVERVIEW_NEW = (
    '<button class="drawer-btn" onclick="toggleSummary();closeNavDrawer()">'
    '<span class="drawer-icon">'
    '<svg viewBox="0 0 20 20" width="20" height="20" style="display:inline-block;pointer-events:none;vertical-align:middle" fill="currentColor">'
    '<path d="M10 1.6 C10.9 6.2 13.8 9.1 18.4 10 C13.8 10.9 10.9 13.8 10 18.4 C9.1 13.8 6.2 10.9 1.6 10 C6.2 9.1 9.1 6.2 10 1.6 Z"/>'
    '</svg></span><span class="drawer-label">Overview</span></button>')

_BACK_PILL_OLD = (
    '<svg viewBox="0 0 100 100" width="16" height="16" style="display:block;pointer-events:none">'
    '<polygon points="50,2 63,37 98,50 63,63 50,98 37,63 2,50 37,37" fill="currentColor"/>'
    '</svg><span>BACK</span>')
_BACK_PILL_NEW = (
    '<svg viewBox="0 0 100 100" width="16" height="16" style="display:block;pointer-events:none">'
    '<circle cx="50" cy="50" r="44" fill="none" stroke="currentColor" stroke-width="7"/><ellipse cx="50" cy="50" rx="22" ry="44" fill="none" stroke="currentColor" stroke-width="6"/><line x1="6" y1="50" x2="94" y2="50" stroke="currentColor" stroke-width="6"/><path d="M14,27 Q50,18 86,27" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round"/><path d="M14,73 Q50,82 86,73" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round"/>'
    '</svg><span>BACK</span>')


# ── outline card numbers say whose child a card is ─────────────────────────
# The engine numbers every card unit.place-in-reading-order (1.13), which on an
# outline says nothing about where a card hangs. An outline's cards take their
# path number from the builder (numbering.py: 2, 2.e, 2.e.6, 2.e.6.2-1c…);
# timelines keep the engine's.
_ORDER_MAP_OLD = "    NODE_ORDER_MAP[id] = `${actIdx+1}.${seqIdx+1}`;"
_ORDER_MAP_NEW = ("    NODE_ORDER_MAP[id] = (window._ALTO_OUTLINE && window._ALTO_OUTLINE.num && window._ALTO_OUTLINE.num[id])"
                  " || `${actIdx+1}.${seqIdx+1}`;")

# ── the horizontal timeline takes over the layout (lanes.py) ───────────────
# Once every card is measured, a lanes page lays its cards along its lines in
# time instead of down the engine's columns; nothing else in initLayout runs.
_LANES_HOOK_OLD = "    nodeHeights[n.id] = h > 0 ? h : 260;\n  });\n"
_LANES_CENTRE_OLD = "  function centreWorld(){\n    var cv=document.getElementById('canvas'); if(!cv) return;"
_LANES_CENTRE_NEW = ("  function centreWorld(){\n    var cv=document.getElementById('canvas'); if(!cv) return;\n"
                     "    if(window._altoLanesGeo) return;   // a horizontal timeline opens at its start")
_LANES_HOOK_NEW = ("    nodeHeights[n.id] = h > 0 ? h : 260;\n  });\n"
                   "  if(window._altoLanes && window._altoLanes(nodeHeights)) return;\n")

PATCHES = [
    {
        "name": "lanes-open-at-the-start",
        "old": _LANES_CENTRE_OLD,
        "new": _LANES_CENTRE_NEW,
        "count": 1,
    },
    {
        "name": "lanes-layout-hook",
        "old": _LANES_HOOK_OLD,
        "new": _LANES_HOOK_NEW,
        "count": 1,
    },
    {
        "name": "outline-path-numbers",
        "old": _ORDER_MAP_OLD,
        "new": _ORDER_MAP_NEW,
        "count": 1,
    },
    {
        "name": "drawer-timeline-glyph-globe",
        "old": _DRAWER_TIMELINE_OLD,
        "new": _DRAWER_TIMELINE_NEW,
        "count": 1,
    },
    {
        "name": "drawer-overview-glyph-desktop-sparkle",
        "old": _DRAWER_OVERVIEW_OLD,
        "new": _DRAWER_OVERVIEW_NEW,
        "count": 1,
    },
    {
        "name": "mobile-back-pill-glyph-globe",
        "old": _BACK_PILL_OLD,
        "new": _BACK_PILL_NEW,
        "count": 1,
    },
    {
        "name": "merge-flag-overshoot",
        "old": _MERGE_FLAG_OLD,
        "new": _MERGE_FLAG_NEW,
        "count": 1,
    },
    {
        "name": "outline-prints-as-an-outline",
        "old": _PRINT_OUTLINE_OLD,
        "new": _PRINT_OUTLINE_NEW,
        "count": 1,
    },
    {
        "name": "search-placeholder-desktop",
        "old": _SEARCH_DESKTOP_OLD,
        "new": _SEARCH_DESKTOP_NEW,
        "count": 1,
    },
    {
        "name": "search-placeholder-mobile",
        "old": _SEARCH_MOBILE_OLD,
        "new": _SEARCH_MOBILE_NEW,
        "count": 1,
    },
    {
        "name": "focus-magnifies-by-zoom-not-transform",
        "old": _FOCUS_CSS_OLD,
        "new": _FOCUS_CSS_NEW,
        "count": 1,
    },
    {
        "name": "focus-zoom-ramp-enter",
        "old": _FOCUS_JS_OLD,
        "new": _FOCUS_JS_NEW,
        "count": 1,
    },
    {
        "name": "focus-zoom-ramp-exit",
        "old": _FOCUS_EXIT_OLD,
        "new": _FOCUS_EXIT_NEW,
        "count": 1,
    },
    {
        "name": "fit-world-to-window-rule",
        "old": _FIT_RULE_OLD,
        "new": _FIT_RULE_NEW,
        "count": 1,
    },
    {
        "name": "fit-world-to-window-script",
        "old": _FIT_SCRIPT_OLD,
        "new": _FIT_SCRIPT_NEW,
        "count": 1,
    },
    {
        "name": "fit-blink-viewport-fill-tracks-the-zoom",
        "old": _FIT_BLINK_OLD,
        "new": _FIT_BLINK_NEW,
        "count": 1,
    },
    {
        "name": "fit-blink-slab-and-overview-track-the-zoom",
        "old": _FIT_SLAB_OLD,
        "new": _FIT_SLAB_NEW,
        "count": 1,
    },
    {
        "name": "safari-standard-zoom-gets-the-viewport-fill",
        "old": _SAFARI_ZOOM_OLD,
        "new": _SAFARI_ZOOM_NEW,
        "count": 1,
    },
    {"name": "dgrid-nodes-centred-by-layout", "old": _DGRID_SCRIPT_OLD,
     "new": _DGRID_SCRIPT_NEW, "count": 1},
    {"name": "dgrid-centre-fly", "old": _DGRID_CXY_OLD, "new": _DGRID_CXY_NEW, "count": 1},
    {"name": "dgrid-hover-by-zoom", "old": _DGRID_HOVER_OLD, "new": _DGRID_HOVER_NEW, "count": 1},
    {"name": "dgrid-centre-search", "old": _DGRID_SRCH_OLD, "new": _DGRID_SRCH_NEW, "count": 1},
    {"name": "fly-scrolls-in-whole-px", "old": _FLY_SCROLL_OLD, "new": _FLY_SCROLL_NEW, "count": 1},
    {"name": "fly-refits-focus-shadow", "old": _FLY_LAND_OLD, "new": _FLY_LAND_NEW, "count": 1},
    {"name": "fly-back-by-margins", "old": _FLY_BACK_OLD, "new": _FLY_BACK_NEW, "count": 1},
    {"name": "wheel-passive-in-safari-open", "old": _WHEEL_OPEN_OLD, "new": _WHEEL_OPEN_NEW, "count": 1},
    {"name": "motion-starts-after-the-state-frame", "old": _ANIM_WARM_OLD, "new": _ANIM_WARM_NEW, "count": 1},
    {"name": "wheel-passive-in-safari-exit", "old": _WHEEL_EXIT_OLD, "new": _WHEEL_EXIT_NEW, "count": 1},
    {"name": "wheel-passive-in-safari-close", "old": _WHEEL_CLOSE_OLD, "new": _WHEEL_CLOSE_NEW, "count": 1},
    {"name": "fly-scroll-axis", "old": _FLY_AXIS_OLD, "new": _FLY_AXIS_NEW, "count": 1},
    {"name": "scroll-tint-on-the-bars", "old": _TINT_SCOPE_OLD, "new": _TINT_SCOPE_NEW, "count": 1},
    {"name": "chip-outlines-are-borders", "old": _CHIP_RULE_OLD, "new": _CHIP_RULE_NEW, "count": 1},
]


# ── the Overview can be pinch-zoomed on its own ─────────────────────────────
# The focus-mode script owns every zoom gesture — ctrl+wheel (a trackpad pinch
# in Chrome), Safari's gesture* events, and ⌘± — and turns it into card focus,
# because native page zoom breaks the liquid glass. That left the open
# Overview, the one long read in the app, impossible to enlarge. Over the open
# Overview — and on a detail page — the same gestures now magnify that panel's
# content alone, like a browser pinch: transform:scale toward the fingers, so
# the text is never re-laid out, and the panel pans freely in both directions
# while zoomed (its stylesheet hides sideways overflow, so that is forced on).
# Nothing behind the glass moves. Phones (focus mode off) get a two-finger
# pinch on either panel. A panel resets when it closes or changes item.
_OVERVIEW_ZOOM_SCRIPT = """<script id="alto-overview-zoom">
/* ── Alto: pinch-zoom a reading panel on its own (engine_patches.py,
   overview-zooms-alone). Works on the open Overview and on detail pages.
   Magnifies like a browser pinch — the text is scaled, never re-laid out —
   toward the point under the fingers, and the panel pans freely in both
   directions while zoomed; the glass and timeline behind it stay put.
   Desktop gestures are routed here by the focus-mode handlers; phones use the
   two-finger pinch below. A panel resets when it closes or changes item. ── */
(function(){
  var MIN=1, MAX=4;
  var PANELS=[{wrap:'summary-wrap', inner:'summary-inner', open:'open', k:1},
              {wrap:'detail-page', inner:'detail-content', open:'visible', k:1}];
  var g=null, g0=1, tp=null, d0=0, t0=1;
  function byId(id){ return document.getElementById(id); }
  function isOpen(p){ var w=byId(p.wrap); return !!(w && w.classList.contains(p.open)); }
  function panelAt(t){
    for(var i=0;i<PANELS.length;i++){ var p=PANELS[i];
      if(isOpen(p) && t && t.closest && t.closest('#'+p.wrap)) return p; }
    return null;
  }
  function activePanel(){ for(var i=0;i<PANELS.length;i++) if(isOpen(PANELS[i])) return PANELS[i]; return null; }
  // While zoomed, the scaled box spans the panel's full width, like a page: the
  // centred column's side margins become equal padding, so every line of text
  // keeps its exact width and place (no re-wrap) but the margins magnify too —
  // otherwise there is no room to pan out to the right-hand side of the text.
  function widen(p, el, w){
    if(p.wide) return;
    var cs=getComputedStyle(el), L=el.offsetLeft, Wd=el.offsetWidth, full=w.clientWidth;
    var pl=parseFloat(cs.paddingLeft)||0, pr=parseFloat(cs.paddingRight)||0, ml=parseFloat(cs.marginLeft)||0;
    var s=el.style;
    s.setProperty('box-sizing','border-box'); s.setProperty('max-width','none');
    s.setProperty('width',Math.max(full,Wd)+'px');
    s.setProperty('margin-left',(ml-L)+'px'); s.setProperty('margin-right','0px');
    s.setProperty('padding-left',(pl+L)+'px'); s.setProperty('padding-right',(Math.max(0,full-L-Wd)+pr)+'px');
    p.wide=true;
  }
  function unwiden(p, el){
    if(!p.wide) return;
    ['box-sizing','max-width','width','margin-left','margin-right','padding-left','padding-right']
      .forEach(function(k){ el.style.removeProperty(k); });
    p.wide=false;
  }
  function reset(p){
    var el=byId(p.inner), w=byId(p.wrap);
    if(el){ el.style.transform=''; unwiden(p, el); }
    if(w) w.style.removeProperty('overflow-x');
    p.k=1;
  }
  // Where the text starts on screen, and the screen px per content px. Measured
  // on the content itself: the Overview slides in with a transform, so its own
  // reported edge is unreliable while open.
  function textBox(el){
    var r=el.getBoundingClientRect(), cs=getComputedStyle(el), vs=r.width/el.offsetWidth||1;
    return {x:r.left+(parseFloat(cs.paddingLeft)||0)*vs, y:r.top+(parseFloat(cs.paddingTop)||0)*vs, vs:vs};
  }
  function set(p, nk, cx, cy){
    var w=byId(p.wrap), el=byId(p.inner); if(!w||!el||!el.offsetWidth) return;
    nk=Math.max(MIN,Math.min(MAX,nk)); if(Math.abs(nk-p.k)<0.002) return;
    if(cx==null){ cx=window.innerWidth/2; cy=window.innerHeight/2; }   // keyboard: middle of the screen
    var on=nk>1.002;
    if(on) widen(p, el, w);
    var b=textBox(el), lx=(cx-b.x)/b.vs, ly=(cy-b.y)/b.vs;           // text px under the fingers
    p.k=nk;
    el.style.transformOrigin='0 0';
    el.style.transform=on?'scale('+p.k+')':'';
    if(on) w.style.setProperty('overflow-x','auto','important');      // pan sideways, not just up and down
    else { w.style.removeProperty('overflow-x'); unwiden(p, el); }
    var b2=textBox(el), z=b2.vs/p.k;
    w.scrollLeft+=(b2.x+lx*b2.vs-cx)/z;                               // put those words back under the fingers
    w.scrollTop+=(b2.y+ly*b2.vs-cy)/z;
  }
  window._altoOverviewZoom={
    wheel:function(e){ var p=panelAt(e.target); if(!p) return false; e.preventDefault(); set(p, p.k*Math.exp(-e.deltaY*0.01), e.clientX, e.clientY); return true; },
    gesture:function(e){
      if(e.type==='gesturestart'){ g=panelAt(e.target); g0=g?g.k:1; return !!g; }
      if(!g) return false; set(g, g0*e.scale, e.clientX, e.clientY); return true;
    },
    gestureEnd:function(){ var was=!!g; g=null; return was; },
    key:function(e){ var p=activePanel(); if(!p) return false; set(p, e.key==='0'?1:(e.key==='-'?p.k/1.25:p.k*1.25)); return true; }
  };
  // reset on close, and when the detail page moves to another item
  PANELS.forEach(function(p){
    var w=byId(p.wrap), el=byId(p.inner); if(!w||!window.MutationObserver) return;
    new MutationObserver(function(){ if(!isOpen(p) && p.k!==1) reset(p); }).observe(w,{attributes:true,attributeFilter:['class']});
    if(el && p.wrap==='detail-page') new MutationObserver(function(){ if(p.k!==1) reset(p); }).observe(el,{childList:true});
  });
  if(!document.documentElement.classList.contains('mobile')) return;
  function dist(t){ return Math.hypot(t[0].clientX-t[1].clientX, t[0].clientY-t[1].clientY); }
  document.addEventListener('touchstart',function(e){ if(e.touches.length===2){ tp=panelAt(e.target); if(tp){ d0=dist(e.touches); t0=tp.k; } } },{passive:true});
  document.addEventListener('touchmove',function(e){
    if(!tp||!d0||e.touches.length!==2) return;
    e.preventDefault();
    set(tp, t0*dist(e.touches)/d0, (e.touches[0].clientX+e.touches[1].clientX)/2, (e.touches[0].clientY+e.touches[1].clientY)/2);
  },{passive:false});
  document.addEventListener('touchend',function(e){ if(e.touches.length<2){ d0=0; tp=null; } },{passive:true});
  ['gesturestart','gesturechange'].forEach(function(ev){
    document.addEventListener(ev,function(e){ if(panelAt(e.target)) e.preventDefault(); },{passive:false});
  });
})();
</script>
"""
_OVZ_SCRIPT_OLD = '<script id="alto-focus-mode">'
_OVZ_SCRIPT_NEW = _OVERVIEW_ZOOM_SCRIPT + _OVZ_SCRIPT_OLD

_OVZ_WHEEL_OLD = ("    e.preventDefault();                       "
                  "// ← stop native browser zoom (the Safari bug)\n")
_OVZ_WHEEL_NEW = ("    if(window._altoOverviewZoom && window._altoOverviewZoom.wheel(e)) return;"
                  "  // pinch over the Overview zooms it alone\n" + _OVZ_WHEEL_OLD)

_OVZ_GESTURE_OLD = ("document.addEventListener(ev,function(e){ e.preventDefault(); "
                    "},{passive:false});")
_OVZ_GESTURE_NEW = ("document.addEventListener(ev,function(e){ e.preventDefault(); "
                    "if(window._altoOverviewZoom) window._altoOverviewZoom.gesture(e); "
                    "},{passive:false});")

_OVZ_GEND_OLD = "    e.preventDefault(); if(!cooled()) return;\n"
_OVZ_GEND_NEW = ("    e.preventDefault(); if(window._altoOverviewZoom && "
                 "window._altoOverviewZoom.gestureEnd(e)) return;\n"
                 "    if(!cooled()) return;\n")

_OVZ_KEY_OLD = ("      e.preventDefault();\n"
                "      if(e.key==='-'||e.key==='0') exitFocus();\n")
_OVZ_KEY_NEW = ("      e.preventDefault();\n"
                "      if(window._altoOverviewZoom && window._altoOverviewZoom.key(e)) return;"
                "  // ⌘± with the Overview open\n"
                "      if(e.key==='-'||e.key==='0') exitFocus();\n")

# ── stale "course" wording on the timeline ──────────────────────────────────
# The reference build was a law course, and three strings still say so on every
# timeline — a novel, a project, anything. Alto's unit is the timeline.
_COPY_OVERVIEW_TITLE_OLD = 'title="Course overview" aria-label="Course overview"'
_COPY_OVERVIEW_TITLE_NEW = 'title="Overview" aria-label="Overview"'
_COPY_OVERVIEW_SECTION_OLD = "var cur='Course Overview';"
_COPY_OVERVIEW_SECTION_NEW = "var cur='Overview';"
_COPY_ACCT_SUB_OLD = "Sign in to keep your courses, reports, and highlights with you."
_COPY_ACCT_SUB_NEW = "Sign in to keep your highlights, notes, and reports with you on every device."

PATCHES += [
    {"name": "overview-zooms-alone-script", "old": _OVZ_SCRIPT_OLD,
     "new": _OVZ_SCRIPT_NEW, "count": 1},
    {"name": "overview-zooms-alone-wheel", "old": _OVZ_WHEEL_OLD,
     "new": _OVZ_WHEEL_NEW, "count": 1},
    {"name": "overview-zooms-alone-gesture", "old": _OVZ_GESTURE_OLD,
     "new": _OVZ_GESTURE_NEW, "count": 1},
    {"name": "overview-zooms-alone-gesture-end", "old": _OVZ_GEND_OLD,
     "new": _OVZ_GEND_NEW, "count": 1},
    {"name": "overview-zooms-alone-keyboard", "old": _OVZ_KEY_OLD,
     "new": _OVZ_KEY_NEW, "count": 1},
    {"name": "copy-overview-toggle-label", "old": _COPY_OVERVIEW_TITLE_OLD,
     "new": _COPY_OVERVIEW_TITLE_NEW, "count": 1},
    {"name": "copy-overview-default-section", "old": _COPY_OVERVIEW_SECTION_OLD,
     "new": _COPY_OVERVIEW_SECTION_NEW, "count": 1},
    {"name": "copy-account-blurb", "old": _COPY_ACCT_SUB_OLD,
     "new": _COPY_ACCT_SUB_NEW, "count": 1},
]


# ── a failed sign-in says why ───────────────────────────────────────────────
# AltoCloud.signIn() failures only reached the console, so "Continue with
# Google" simply did nothing — most often because the site's domain is not in
# the Firebase project's Authorized domains. Say so in the account modal.
_SIGNIN_FAIL_OLD = ".catch(function(e){ console.warn('sign-in failed', e); })"
_SIGNIN_FAIL_NEW = (
    ".catch(function(e){ console.warn('sign-in failed', e);"
    " var s=document.querySelector('#acct-signed-out .acct-sub');"
    " if(s && !(e && e.code==='auth/popup-closed-by-user'))"
    " s.textContent=(e && e.code==='auth/unauthorized-domain')"
    " ? 'Sign-in is not enabled for this address yet. The site owner needs to add it"
    " in Firebase under Authentication, Settings, Authorized domains.'"
    " : 'Sign-in did not complete. Please try again.'; })")

PATCHES += [
    {"name": "copy-sign-in-failure-is-explained", "old": _SIGNIN_FAIL_OLD,
     "new": _SIGNIN_FAIL_NEW, "count": 1},
]


# ── section headers: room either side, a chip that fits its name, legible ink ─
# The unit-divider tube ran edge to edge, so every section header sat hard
# against both sides of the window. Pull the tube in by TUBE_INSET and move
# both chips with it — they are laid out TUBE_M inside the tube, which is what
# keeps their corners concentric with its corners.
#
# The name chip was a fixed 56px box capped at 208px wide, so a long name
# ("Discovery, Summary Judgment & Preclusion") wrapped to four lines and spilled
# out of it. The height stays fixed (the tube geometry is built on it) but the
# WIDTH is now fitted to the name: widen until it sets in at most two lines,
# and only if even the widest chip cannot hold it, step the type down.
#
# The ink was the unit colour on a glass tinted the same unit colour, which read
# soft and, for mid-tone units, failed contrast outright. Both chips now sit on
# a near-opaque surface and the ink is the unit colour pulled toward black
# (light) or white (dark) until it clears WCAG 4.5:1 against that surface. The
# unit colour still rings the chip.
_TUBE_INSET = 20
_HDR_TUBE_OLD = "bar.style.left='0px'; bar.style.right='0px';"
_HDR_TUBE_NEW = f"bar.style.left='{_TUBE_INSET}px'; bar.style.right='{_TUBE_INSET}px';"
_HDR_NAME_OLD = "    lbl.style.left='9px';"
_HDR_NAME_NEW = f"    lbl.style.left='{9 + _TUBE_INSET}px';"
_HDR_NUM_OLD = "  top:38px !important; right:9px !important; transform:none !important;"
_HDR_NUM_NEW = f"  top:38px !important; right:{9 + _TUBE_INSET}px !important; transform:none !important;"

_HDR_BOX_OLD = "  box-sizing:border-box; height:56px; max-width:208px;"
_HDR_BOX_NEW = "  box-sizing:border-box; height:56px; max-width:none;"
_HDR_TEXT_OLD = ("  white-space:normal; font-size:12.5px; line-height:1.2; letter-spacing:.085em;\n"
                 "  font-weight:600; text-transform:uppercase;\n"
                 "  padding:6px 16px; border-radius:15px;\n"
                 "  background:var(--card-glass-bg);")
_HDR_TEXT_NEW = ("  white-space:normal; font-size:13.5px; line-height:1.2; letter-spacing:.06em;\n"
                 "  font-weight:700; text-transform:uppercase; text-rendering:optimizeLegibility;\n"
                 "  padding:6px 18px; border-radius:15px;\n"
                 "  color:var(--unit-ink, #1d1d2b);\n"
                 "  background:rgba(255,255,255,0.92);")
_HDR_NUMBG_OLD = ("  padding:0 17px; border-radius:15px;\n"
                  "  background:var(--card-glass-bg);")
_HDR_NUMBG_NEW = ("  padding:0 17px; border-radius:15px;\n"
                  "  color:var(--unit-ink, #1d1d2b);\n"
                  "  background:rgba(255,255,255,0.92);")
_HDR_DARK_OLD = "html.dark:not(.mobile) .unit-bar{"
_HDR_DARK_NEW = ("html.dark:not(.mobile) .phase-label-float,\n"
                 "html.dark:not(.mobile) .phase-numeral{\n"
                 "  color:var(--unit-ink-dark, #f2f4fb);\n"
                 "  background:rgba(20,24,38,0.90);\n"
                 "}\n"
                 "html.dark:not(.mobile) .unit-bar{")

_HDR_NUMINK_OLD = "num.className='phase-numeral';num.style.color=pm.colorRaw;"
_HDR_NUMINK_NEW = ("num.className='phase-numeral';"
                   "_altoUnitInk(num,pm.colorRaw);")
_HDR_LBLINK_OLD = "    lbl.style.color=pm.colorRaw;\n"
_HDR_LBLINK_NEW = "    _altoUnitInk(lbl,pm.colorRaw);\n"
_HDR_FIT_OLD = ("    lbl.textContent=(pm.label.split(' — ')[1]||pm.label);\n"
                "    world.appendChild(lbl);")
_HDR_FIT_NEW = ("    lbl.textContent=(pm.label.split(' — ')[1]||pm.label);\n"
                "    world.appendChild(lbl);\n"
                "    _altoFitUnitChip(lbl);")
_HDR_FN_OLD = "  const _dots='<g class=\"ud-base\">"
_HDR_FN_NEW = r"""  // Ink for a header chip: the unit colour darkened (light) / lightened (dark)
  // until it clears 4.5:1 against the chip surface. Sets --unit-ink[-dark].
  function _altoUnitInk(el, hex){
    let m=/^#?([0-9a-f]{3}|[0-9a-f]{6})/i.exec(hex||''), h=m?m[1]:'';
    if(h.length===3) h=h.replace(/./g,'$&$&');
    const base=h?[0,2,4].map(i=>parseInt(h.slice(i,i+2),16)):null;
    const lum=c=>{ const f=v=>{ v/=255; return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4); };
                   return .2126*f(c[0])+.7152*f(c[1])+.0722*f(c[2]); };
    const ratio=(a,b)=>{ const x=lum(a), y=lum(b); return (Math.max(x,y)+.05)/(Math.min(x,y)+.05); };
    function pull(surface, toward){
      if(!base) return null;
      let c=base, t=0;
      while(ratio(c,surface)<5 && t<1){ t+=.04; c=base.map((v,i)=>Math.round(v+(toward[i]-v)*t)); }
      return 'rgb('+c.join(',')+')';
    }
    const li=pull([255,255,255],[0,0,0]), di=pull([20,24,38],[255,255,255]);
    if(li) el.style.setProperty('--unit-ink',li);
    if(di) el.style.setProperty('--unit-ink-dark',di);
  }
  // Fit the name chip to its name: widen (up to MAXW) until the text sets in the
  // fixed-height box, then shrink the type only if it still will not.
  function _altoFitUnitChip(el){
    if(document.documentElement.classList.contains('mobile')) return;
    const text=el.textContent;
    el.textContent='';
    const span=document.createElement('span');
    span.style.display='block';
    span.textContent=text;
    el.appendChild(span);
    const cs=getComputedStyle(el);
    const room=()=>el.clientHeight-parseFloat(cs.paddingTop)-parseFloat(cs.paddingBottom);
    const MAXW=560, WIDTHS=[208,260,320,400,480,MAXW];
    function fitted(){
      return span.offsetHeight<=room()+0.5 && span.scrollWidth<=span.clientWidth+0.5;
    }
    function run(){
      for(let fs=13.5; fs>=10; fs-=0.5){
        el.style.fontSize=fs+'px';
        for(const w of WIDTHS){
          el.style.width=w+'px';
          if(fitted()) return;
        }
      }
    }
    run();
    if(document.fonts && document.fonts.ready) document.fonts.ready.then(run);
  }
  const _dots='<g class="ud-base">"""

PATCHES += [
    {"name": "section-header-tube-inset", "old": _HDR_TUBE_OLD,
     "new": _HDR_TUBE_NEW, "count": 1},
    {"name": "section-header-name-inset", "old": _HDR_NAME_OLD,
     "new": _HDR_NAME_NEW, "count": 1},
    {"name": "section-header-numeral-inset", "old": _HDR_NUM_OLD,
     "new": _HDR_NUM_NEW, "count": 1},
    {"name": "section-header-chip-can-widen", "old": _HDR_BOX_OLD,
     "new": _HDR_BOX_NEW, "count": 1},
    {"name": "section-header-crisper-text", "old": _HDR_TEXT_OLD,
     "new": _HDR_TEXT_NEW, "count": 1},
    {"name": "section-header-numeral-surface", "old": _HDR_NUMBG_OLD,
     "new": _HDR_NUMBG_NEW, "count": 1},
    {"name": "section-header-dark-surface", "old": _HDR_DARK_OLD,
     "new": _HDR_DARK_NEW, "count": 1},
    {"name": "section-header-numeral-ink", "old": _HDR_NUMINK_OLD,
     "new": _HDR_NUMINK_NEW, "count": 1},
    {"name": "section-header-name-ink", "old": _HDR_LBLINK_OLD,
     "new": _HDR_LBLINK_NEW, "count": 1},
    {"name": "section-header-name-fits", "old": _HDR_FIT_OLD,
     "new": _HDR_FIT_NEW, "count": 1},
    {"name": "section-header-helpers", "old": _HDR_FN_OLD,
     "new": _HDR_FN_NEW, "count": 1},
]


# ── homepage search lands on phones too ─────────────────────────────────────
# A homepage search hit opens the timeline at #find=<node>. The reader for it
# lives in the desktop search block, after that block's mobile early-return, so
# on a phone the link opened the timeline at the top and the hit was lost.
_MFIND_OLD = ("  var glyph=wrap.querySelector('#m-search-glyph'),\n"
              "      input=wrap.querySelector('#m-search-input'),")
_MFIND_NEW = ("  (function(){\n"
              "    var m=/[#&]find=([\\w-]+)/.exec(location.hash||'');\n"
              "    if(!m) return;\n"
              "    var id=m[1], done=false, tries=0;\n"
              "    function go(){\n"
              "      if(done) return;\n"
              "      if(!document.getElementById('node-'+id) || typeof window.featureNode!=='function'){\n"
              "        if(++tries<80) setTimeout(go,100); return; }\n"
              "      done=true;\n"
              "      window.featureNode(id,true);\n"
              "      try{ history.replaceState(null,'',location.pathname+location.search); }catch(e){}\n"
              "    }\n"
              "    window.addEventListener('load', function(){ setTimeout(go,400); });\n"
              "    setTimeout(go,900);\n"
              "  })();\n"
              + _MFIND_OLD)

PATCHES += [
    {"name": "mobile-find-deep-link", "old": _MFIND_OLD,
     "new": _MFIND_NEW, "count": 1},
]


# ── signed in: the photo is the account control ─────────────────────────────
# The signed-in state was an initial on a gradient, 25px inside the same 35px
# glass bubble as the signed-out glyph. Show the Google photo (initial if there
# is none or it fails) filling the whole slot, with no glass around it — the
# same treatment as the homepage and reports page.
_AV_JS = ("function _altoAvatar(el, photo, initial){ if(!el) return;"
          " var img=el.querySelector('img');"
          " if(photo && /^https:\\/\\//.test(photo)){"
          " if(img && img.getAttribute('src')===photo) return;"
          " var im=document.createElement('img'); im.alt=''; im.referrerPolicy='no-referrer';"
          " im.onerror=function(){ el.textContent=initial; }; im.src=photo;"
          " el.textContent=''; el.appendChild(im);"
          " } else { el.textContent=initial; } }")
_AV_IN_OLD = ("      glyph.style.display='none'; mini.style.display='flex';\n"
              "      mini.textContent = (s.name || 'A')[0].toUpperCase();")
_AV_IN_NEW = ("      glyph.style.display='none'; mini.style.display='flex';\n"
              "      " + _AV_JS + "\n"
              "      _altoAvatar(mini, s.photo, (s.name || 'A')[0].toUpperCase());\n"
              "      var _ab=document.getElementById('account-btn'); if(_ab) _ab.classList.add('signed-in');")
_AV_MODAL_OLD = "      document.getElementById('acct-avatar').textContent = (s.name || 'A')[0].toUpperCase();"
_AV_MODAL_NEW = "      _altoAvatar(document.getElementById('acct-avatar'), s.photo, (s.name || 'A')[0].toUpperCase());"
_AV_OUT_OLD = ("      glyph.style.display='flex'; mini.style.display='none';\n"
               "      out.style.display='block'; inn.style.display='none';")
_AV_OUT_NEW = (_AV_OUT_OLD + "\n"
               "      var _ab2=document.getElementById('account-btn'); if(_ab2) _ab2.classList.remove('signed-in');")
_AV_CSS_OLD = "html.mobile #account-btn #acct-avatar-mini{ width:20px; height:20px; font-size:10px; }"
_AV_CSS_NEW = (_AV_CSS_OLD + "\n"
               "html #account-btn.signed-in{ background:transparent !important; border-color:transparent !important;"
               " box-shadow:none !important; -webkit-backdrop-filter:none !important; backdrop-filter:none !important; }\n"
               "html:not(.mobile) #account-btn.signed-in #acct-avatar-mini{ width:100%; height:100%; font-size:14px; overflow:hidden; }\n"
               "html.mobile #account-btn.signed-in #acct-avatar-mini{ width:32px; height:32px; font-size:13px; overflow:hidden; }\n"
               "#acct-avatar-mini img, #acct-avatar img{ width:100%; height:100%; object-fit:cover; border-radius:50%; display:block; }\n"
               "#acct-avatar{ overflow:hidden; }")

PATCHES += [
    {"name": "account-photo-signed-in", "old": _AV_IN_OLD, "new": _AV_IN_NEW, "count": 1},
    {"name": "account-photo-modal", "old": _AV_MODAL_OLD, "new": _AV_MODAL_NEW, "count": 1},
    {"name": "account-photo-signed-out", "old": _AV_OUT_OLD, "new": _AV_OUT_NEW, "count": 1},
    {"name": "account-photo-css", "old": _AV_CSS_OLD, "new": _AV_CSS_NEW, "count": 1},
]


# ── homepage search jump survives the page's own load-time scroll ──────────
# The desktop #find reader tried to jump from 300ms after the script ran, which
# on a large timeline is before `load` — and the load-time centring then put
# the canvas back at the top. The hash was already cleared and `done` set, so
# the hit was silently lost. Wait for load, then check the card really is on
# screen and jump once more if something moved it.
_DFIND_OLD = ("    window.addEventListener('load', function(){ setTimeout(go,200); });\n"
              "    [300,900,1600].forEach(function(ms){ setTimeout(go,ms); });")
_DFIND_NEW = ("    function start(){\n"
              "      setTimeout(go,350);\n"
              "      setTimeout(function(){\n"
              "        var cv=document.getElementById('canvas'), n=document.getElementById('node-'+id);\n"
              "        if(!done || !cv || !n) return;\n"
              "        var r=n.getBoundingClientRect();\n"
              "        if(r.top < 0 || r.bottom > cv.getBoundingClientRect().bottom) searchGoToNode(id);\n"
              "      },1800);\n"
              "    }\n"
              "    if(document.readyState==='complete') start(); else window.addEventListener('load', start);")

PATCHES += [
    {"name": "desktop-find-waits-for-load", "old": _DFIND_OLD,
     "new": _DFIND_NEW, "count": 1},
]

# ── filters that hide cards also steer the timeline ─────────────────────────
# Stepping through the timeline (swipe, the edge buttons, next/previous on a
# detail page) walks only the cards an era/weight filter left, through the
# engine's `_filteredOrder`. The Filter panel's sub-chip filters (characters,
# themes…) hide cards too and have to steer the same way, or a swipe lands on a
# card the reader just filtered out. They report through two hooks the panel
# defines, `_altoChipOn` and `_altoChipKeep`; a timeline with no panel has
# neither, and every check below falls through to what it was.
_CHIP_ON = "(window._altoChipOn&&window._altoChipOn())"
_CHIP_KEEP = "(!window._altoChipKeep||window._altoChipKeep(id))"
PATCHES += [
    {"name": "filtered-order-preview", "old": "(_pF.era||_pF.weight)",
     "new": f"(_pF.era||_pF.weight||{_CHIP_ON})", "count": 1},
    {"name": "filtered-order-empty",
     "old": "if(!f.era && !f.weight) return NODE_ORDER.slice();",
     "new": f"if(!f.era && !f.weight && !{_CHIP_ON}) return NODE_ORDER.slice();", "count": 1},
    {"name": "filtered-order-keep",
     "old": "return (!f.era || n.era===f.era) && (!f.weight || n.examWeight===f.weight);",
     "new": ("return (!f.era || n.era===f.era) && (!f.weight || n.examWeight===f.weight)"
             f" && {_CHIP_KEEP};"), "count": 1},
    {"name": "filtered-order-swipe",
     "old": "var order = (f.era || f.weight) ? _filteredOrder() : NODE_ORDER;",
     "new": f"var order = (f.era || f.weight || {_CHIP_ON}) ? _filteredOrder() : NODE_ORDER;",
     "count": 1},
    {"name": "filtered-order-edge-buttons",
     "old": "var ord = (f.era || f.weight) ? _filteredOrder() : NODE_ORDER;",
     "new": f"var ord = (f.era || f.weight || {_CHIP_ON}) ? _filteredOrder() : NODE_ORDER;",
     "count": 2},
    {"name": "filtered-order-detail-a",
     "old": "if(t === 'node' && (f.era || f.weight)){",
     "new": f"if(t === 'node' && (f.era || f.weight || {_CHIP_ON})){{", "count": 1},
    {"name": "filtered-order-detail-b",
     "old": "if(type === 'node' && (f.era || f.weight) && typeof window._filteredOrder === 'function'){",
     "new": ("if(type === 'node' && (f.era || f.weight || " + _CHIP_ON +
             ") && typeof window._filteredOrder === 'function'){"), "count": 1},
    {"name": "filtered-order-detail-c",
     "old": "if(type === 'node' && (f.era || f.weight)){",
     "new": f"if(type === 'node' && (f.era || f.weight || {_CHIP_ON})){{", "count": 1},
    {"name": "filtered-order-desktop-empty",
     "old": "      if(!f.era && !f.weight) return null;",
     "new": f"      if(!f.era && !f.weight && !{_CHIP_ON}) return null;", "count": 1},
    {"name": "filtered-order-desktop-keep",
     "old": "        if(f.weight && n.examWeight !== f.weight) return false;",
     "new": ("        if(f.weight && n.examWeight !== f.weight) return false;\n"
             f"        if(!{_CHIP_KEEP}) return false;"), "count": 1},
]

# ── mobile: the INFO tile only rises when a Filter tile sits under it ──────
# The account toggle used to hold the bottom-left corner, with INFO lifted above
# it. Inside a timeline the account toggle is gone and the Filter tile takes the
# corner — when the timeline has one. Without it INFO drops to the corner.
_INFO_OLD = "html.mobile #tutorial-toggle{ bottom:calc(66px + env(safe-area-inset-bottom, 0px)); }"
_INFO_NEW = ("html.mobile #tutorial-toggle{ bottom:calc(8px + env(safe-area-inset-bottom, 0px)); }\n"
             "html.mobile.has-filter-tab #tutorial-toggle{ bottom:calc(66px + env(safe-area-inset-bottom, 0px)); }")

# ── mobile search: top row, between MAP and MENU, and it stays put ─────────
# It sat at the bottom centre and, when tapped, jumped to the top to dodge the
# keyboard. It now lives at the top from the start, level with the tops of the
# MAP and MENU tabs (104px) and centred between them, and expands sideways in
# place — so there is nothing for the keyboard to push, and nothing to jump.
# 16px type in the field already stops iOS zooming the page on focus; focusing
# without scrolling stops it nudging the page as well.
_MS_OLD = ("html.mobile #m-search{\n"
           "  position:fixed; bottom:calc(10px + env(safe-area-inset-bottom,0px)); left:50%; transform:translateX(-50%);\n"
           "  z-index:298;\n"
           "  height:38px; border-radius:19px;")
_MS_NEW = ("html.mobile #m-search{\n"
           "  position:fixed; top:104px; bottom:auto; left:50%; transform:translateX(-50%);\n"
           "  z-index:298; box-sizing:border-box; width:98px;\n"
           "  height:38px; border-radius:19px;")
_MS_EXP_OLD = "html.mobile #m-search.expanded{ width:min(360px, calc(100vw - 168px)); padding:0 10px 0 14px; cursor:text; }"
_MS_EXP_NEW = "html.mobile #m-search.expanded{ width:calc(100vw - 112px); padding:0 10px 0 14px; cursor:text; }"
_MS_RES_OLD = ("html.mobile #m-search-results{\n"
               "  display:none; position:fixed; bottom:calc(56px + env(safe-area-inset-bottom,0px));")
_MS_RES_NEW = ("html.mobile #m-search-results{\n"
               "  display:none; position:fixed; top:150px; bottom:auto;")
_MS_DOCK_OLD = ("html.mobile.msearch-open #m-search{\n"
                "  top:calc(10px + env(safe-area-inset-top,0px)); bottom:auto;\n"
                "}\n"
                "html.mobile.msearch-open #m-search-results{\n"
                "  top:calc(56px + env(safe-area-inset-top,0px)); bottom:auto;\n")
_MS_DOCK_NEW = ("html.mobile.msearch-open #m-search-results{\n")
_MS_FOCUS_A_OLD = ("try{ input.focus(); }catch(e){}                              "
                   "// focus inside the tap gesture → iOS shows the keyboard")
_MS_FOCUS_A_NEW = ("try{ input.focus({preventScroll:true}); }catch(e){}   "
                   "// focus inside the tap gesture → iOS shows the keyboard")
_MS_FOCUS_B_OLD = "setTimeout(function(){ try{ input.focus(); }catch(e){} },60);"
_MS_FOCUS_B_NEW = "setTimeout(function(){ try{ input.focus({preventScroll:true}); }catch(e){} },60);"

PATCHES += [
    {"name": "mobile-info-tile-position", "old": _INFO_OLD, "new": _INFO_NEW, "count": 1},
    {"name": "mobile-search-top-row", "old": _MS_OLD, "new": _MS_NEW, "count": 1},
    {"name": "mobile-search-expands-in-place", "old": _MS_EXP_OLD, "new": _MS_EXP_NEW, "count": 1},
    {"name": "mobile-search-results-below", "old": _MS_RES_OLD, "new": _MS_RES_NEW, "count": 1},
    {"name": "mobile-search-no-docking", "old": _MS_DOCK_OLD, "new": _MS_DOCK_NEW, "count": 1},
    {"name": "mobile-search-focus-in-tap", "old": _MS_FOCUS_A_OLD, "new": _MS_FOCUS_A_NEW, "count": 1},
    {"name": "mobile-search-focus-fallback", "old": _MS_FOCUS_B_OLD, "new": _MS_FOCUS_B_NEW, "count": 1},
]

# ── mobile search: the detail-page panel reuses the timeline search ────────
# The panel needs the pill's own navigation (leave a detail page, feature a
# card, open a detail), so the pill's closure hands it out.
_MS_NAV_OLD = "window._mSearchClose=closeSearch;"
_MS_NAV_NEW = "window._mSearchClose=closeSearch; window._mSearchNavigate=navigate;"
# A swipe that starts on either full-page panel must not step the timeline.
_SWIPE_OLD = "#summary-wrap,#tutorial-wrap,#notes-panel"
_SWIPE_NEW = "#summary-wrap,#tutorial-wrap,#ef-panel,#msp,#notes-panel"
PATCHES += [
    {"name": "mobile-search-navigate-exposed", "old": _MS_NAV_OLD, "new": _MS_NAV_NEW, "count": 1},
    {"name": "mobile-swipe-ignores-new-panels", "old": _SWIPE_OLD, "new": _SWIPE_NEW, "count": 2},
]

# ── mobile search collapses reliably, and never leaves the card faded ─────
# The pill closed only on a tap or click landing elsewhere, which is not the only
# way focus leaves it: dismissing the keyboard, or a tap that iOS delivers to
# nothing, left it expanded. Now it also closes when the field loses focus (unless
# the reader is on the results), and on the very start of a touch elsewhere.
# It also no longer animates its width: that transition ran on a backdrop-filter
# layer beside the featured card's own, and WebKit can leave the neighbour drawn
# faded. Closing also clears anything that could still be dimming the card.
_MS_TRANS_OLD = "  transition:width .18s ease;\n}"
_MS_TRANS_NEW = "  /* width is set, not animated */\n}"
_MS_CLOSE_OLD = "    input.value=''; input.blur();\n    resultsEl.innerHTML='';"
_MS_CLOSE_NEW = ("    input.value=''; input.blur(); setTimeout(_altoRestoreFeatured,0);\n"
                 "    resultsEl.innerHTML='';")
_MS_OUTSIDE_OLD = ("  document.addEventListener('touchend',outside,true);\n"
                   "  document.addEventListener('click',outside,true);\n"
                   "})();")
_MS_OUTSIDE_NEW = (
    "  var resultsTouched=false;\n"
    "  resultsEl.addEventListener('touchstart',function(){ resultsTouched=true; },{passive:true});\n"
    "  resultsEl.addEventListener('touchend',function(){ setTimeout(function(){ resultsTouched=false; },500); },{passive:true});\n"
    "  function _altoRestoreFeatured(){\n"
    "    var f=document.querySelector('.node.mobile-featured'); if(!f) return;\n"
    "    f.style.opacity=''; var c=f.querySelector('.node-card');\n"
    "    if(c){ c.style.opacity=''; c.style.visibility=''; }\n"
    "  }\n"
    "  document.addEventListener('touchstart',outside,true);\n"
    "  document.addEventListener('touchend',outside,true);\n"
    "  document.addEventListener('click',outside,true);\n"
    "  document.addEventListener('pointerdown',outside,true);\n"
    "  input.addEventListener('blur',function(){\n"
    "    setTimeout(function(){ if(isOpen && document.activeElement!==input && !resultsTouched) closeSearch(); },220);\n"
    "  });\n"
    "})();")
# ── the shared swipe-to-close helper is handed out ─────────────────────────
_SWIPE_HELPER_OLD = "    // MAP — swipe left to close\n    var _mm=document.getElementById('minimap-wrap');"
_SWIPE_HELPER_NEW = ("    window._altoPanelSwipe=_makePanelSwipeDismiss;   // the Filter and Search panels use it too\n"
                     "    // MAP — swipe left to close\n    var _mm=document.getElementById('minimap-wrap');")
PATCHES += [
    {"name": "mobile-search-no-width-transition", "old": _MS_TRANS_OLD, "new": _MS_TRANS_NEW, "count": 1},
    {"name": "mobile-search-close-restores-card", "old": _MS_CLOSE_OLD, "new": _MS_CLOSE_NEW, "count": 1},
    {"name": "mobile-search-collapses-on-blur", "old": _MS_OUTSIDE_OLD, "new": _MS_OUTSIDE_NEW, "count": 1},
    {"name": "panel-swipe-helper-exposed", "old": _SWIPE_HELPER_OLD, "new": _SWIPE_HELPER_NEW, "count": 1},
]

# ── a node's page carries every kind of sub-chip it has ─────────────────────
# The node page listed the entity chips ("Characters Present") and stopped, though
# a node carries environment and theme chips too — which have pages of their own.
# Each kind present now gets a section, with chips that open that page.
_NC_DESK_OLD = ("    document.getElementById('detail-content').innerHTML = html;\n"
                "    document.getElementById('detail-page').scrollTop = 0;\n"
                "    return;")
_NC_DESK_NEW = ("    html += _altoAxisChips(n, true);\n"
                "    document.getElementById('detail-content').innerHTML = html;\n"
                "    document.getElementById('detail-page').scrollTop = 0;\n"
                "    return;")
_NC_PEEK_OLD = ("        }\n"
                "      } else if(type==='char'&&typeof CHARS!=='undefined'){")
_NC_PEEK_NEW = ("          inner += _altoAxisChips(nd, false);\n"
                "        }\n"
                "      } else if(type==='char'&&typeof CHARS!=='undefined'){")
PATCHES += [
    {"name": "node-page-axis-chips", "old": _NC_DESK_OLD, "new": _NC_DESK_NEW, "count": 1},
    {"name": "node-peek-axis-chips", "old": _NC_PEEK_OLD, "new": _NC_PEEK_NEW, "count": 1},
]

# ── desktop: the bottom-right controls stay above the nodes ────────────────
# The light/dark toggle and INFO sat at z-index 200 — the same as a hovered node,
# which comes later in the page and so won the tie — and a focused node (300)
# tied the search bubble. Scrolling a card under the cursor slipped the toggle
# behind it. All three now sit above any node (panels and the rail are 395+).
_CTRL_OLD = "html:not(.mobile) #notes-toggle:hover{ border-color:var(--muted) !important; }"
_CTRL_NEW = (_CTRL_OLD + "\n"
             "html:not(.mobile) #mode-toggle, html:not(.mobile) #info-btn,\n"
             "html:not(.mobile) #search-btn{ z-index:310 !important; }\n"
             # light/dark is just its glyph in a circle, the same 35px as INFO and
             # search; the edit toggle (manual_edit) takes the rightmost slot and
             # alignInfo lines the three circles up to its left.
             "html:not(.mobile) #mode-toggle{ width:35px; height:35px; padding:0; border-radius:50% !important; }\n"
             "html:not(.mobile) #mode-toggle .mode-glyph{ display:none; width:18px; height:18px; flex:none; }\n"
             "html:not(.mobile):not(.dark) #mode-toggle .mode-moon{ display:block; }\n"
             "html:not(.mobile).dark #mode-toggle .mode-sun{ display:block; }\n"
             # the way back to the timeline from a detail page, left of the title in
             # the title bar (a phone's BACK tile; the green pill is "back to the
             # previous page"). Glass like the other floating controls; below
             # 1100px it keeps only its arrow so a long title is never crowded.
             # It sits on the clef's centre line (the bar is 52px: centre 26, so top =
             # 26 - 35/2) and 80px in, ~20px clear of the clef's 59px right edge; it
             # zooms with the page, so the gap and the alignment hold at every width.
             "html.mobile #desk-back{ display:none !important; }\n"
             "html:not(.mobile) #desk-back{ display:none; position:fixed; left:80px; top:8.5px; z-index:103; height:35px;\n"
             "  align-items:center; justify-content:center; gap:7px; padding:0 15px 0 12px; border-radius:17.5px; cursor:pointer;\n"
             "  font-family:inherit; font-size:14px; letter-spacing:.05em; white-space:nowrap; color:var(--muted);\n"
             "  background:var(--card-glass-bg); border:1px solid var(--card-glass-border);\n"
             "  -webkit-backdrop-filter:blur(18px) saturate(190%) brightness(var(--card-glass-bright));\n"
             "  backdrop-filter:blur(18px) saturate(190%) brightness(var(--card-glass-bright));\n"
             "  box-shadow:0 10px 26px var(--node-rest-shadow), inset 0 0 0 0.5px var(--card-glass-rim); }\n"
             "html:not(.mobile).detail-open #desk-back{ display:inline-flex; }\n"
             "html:not(.mobile) #desk-back:hover{ border-color:var(--muted); color:var(--text); }\n"
             "html:not(.mobile) #desk-back svg{ display:block; flex:none; }\n"
             "@media (max-width:1100px){ html:not(.mobile) #desk-back{ width:35px; padding:0; }\n"
             "  html:not(.mobile) #desk-back .db-label{ display:none; } }\n"
             "html.printing #desk-back{ display:none !important; }\n"
             # The overview star was the one right-edge tab with no hover line: its glass
             # border is !important, so the plain :hover rule never showed (the same trap as
             # light/dark and Notes above). The clef, the wordmark and the timeline's name
             # have theirs in hover_lines.py.
             "html:not(.mobile) #overview-toggle:hover{ border-color:var(--muted) !important; }")
_MODE_BTN_OLD = '<button id="mode-toggle" onclick="toggleMode()">\u263d Dark</button>'
_MODE_BTN_NEW = (
    '<button id="mode-toggle" type="button" onclick="toggleMode()" aria-label="Light or dark" title="Light or dark">'
    '<svg class="mode-glyph mode-moon" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">'
    '<path d="M16 12.2A6.4 6.4 0 1 1 8.6 3.2 5 5 0 0 0 16 12.2Z" fill="currentColor"/></svg>'
    '<svg class="mode-glyph mode-sun" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">'
    '<circle cx="10" cy="10" r="3.4" fill="currentColor"/><g stroke="currentColor" stroke-width="1.5" stroke-linecap="round">'
    '<line x1="10" y1="1.6" x2="10" y2="3.8"/><line x1="10" y1="16.2" x2="10" y2="18.4"/><line x1="1.6" y1="10" x2="3.8" y2="10"/>'
    '<line x1="16.2" y1="10" x2="18.4" y2="10"/><line x1="4.05" y1="4.05" x2="5.6" y2="5.6"/><line x1="14.4" y1="14.4" x2="15.95" y2="15.95"/>'
    '<line x1="4.05" y1="15.95" x2="5.6" y2="14.4"/><line x1="14.4" y1="5.6" x2="15.95" y2="4.05"/></g></svg></button>\n'
    '  <button id="desk-back" type="button" onclick="showTimeline()" aria-label="Back to the timeline" title="Back to the timeline">'
    '<svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true"><path d="M16.5 10H3.8M9 4.6 3.6 10 9 15.4"/></svg><span class="db-label">Timeline</span></button>')
_MODE_TXT_OLD = "  document.getElementById('mode-toggle').textContent = isDark ? '\u2600 Light' : '\u263d Dark';\n"
_MODE_TXT_NEW = "  document.getElementById('mode-toggle').title = isDark ? 'Switch to light' : 'Switch to dark';\n"
_MODE_EARLY_OLD = "if(m)m.textContent='\u2600 Light';"
_MODE_EARLY_NEW = "if(m)m.title='Switch to light';"
_ALIGN_OLD = (
    "    var dwCSS = mt.offsetWidth, dhCSS = mt.offsetHeight;\n"
    "    if(dwCSS === 0) return;\n"
    "    var MARGIN = 12.5;        // gap (10px VISUAL after zoom) \u2014 matches homepage rhythm\n"
    "    var COLLAPSED_H = 35;     // the \"i\" circle diameter (28px VISUAL)\n"
    "    var rightCSS  = 30 + dwCSS + MARGIN;             // 30 = toggle's right inset (24px VISUAL)\n"
    "    var bottomCSS = 30 + (dhCSS - COLLAPSED_H) / 2;  // centre INFO on the toggle\n"
    "    if(bottomCSS < 0) bottomCSS = 30;\n")
_ALIGN_NEW = (
    "    if(mt.offsetWidth === 0) return;\n"
    "    var MARGIN = 12.5;        // gap (10px VISUAL after zoom) \u2014 matches homepage rhythm\n"
    "    var COLLAPSED_H = 35;     // every circle's diameter (28px VISUAL)\n"
    "    // The row, right to left: the edit toggle (manual_edit's #alto-edit-pill, when\n"
    "    // the page has one on screen) in the corner, then light/dark, INFO, search.\n"
    "    // With no edit toggle (a share, a copy, while editing) they sit flush right.\n"
    "    var ep = document.getElementById('alto-edit-pill');\n"
    "    var epW = (ep && ep.offsetWidth) ? Math.ceil((ep.offsetWidth + MARGIN) / 1.25) * 1.25 : 0;   // whole VISUAL px under zoom .8\n"
    "    // While the Notes / Freewrite panel is open (freewrite.py sets --np-dock, its CSS width) the whole\n"
    "    // row sits left of it, the same 30 off its edge as it is off the corner.\n"
    "    var dock = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--np-dock')) || 0;\n"
    "    var modeR = 30 + epW + dock;                    // 30 = the corner inset (24px VISUAL)\n"
    "    var rightCSS  = modeR + COLLAPSED_H + MARGIN;\n"
    "    var bottomCSS = 30;\n"
    "    mt.style.setProperty('right',  modeR + 'px', 'important');\n"
    "    mt.style.setProperty('bottom', bottomCSS + 'px', 'important');\n"
    "    if(ep) ep.style.setProperty('right', (30 + dock) + 'px', 'important');\n")
_ALIGN_HOOK_OLD = "  // Retry until mode-toggle has dimensions AND alignInfo successfully commits."
_ALIGN_HOOK_NEW = (
    "  window._altoAlignInfo = alignInfo;   // manual_edit calls it once the edit toggle exists\n"
    "  new MutationObserver(alignInfo).observe(document.documentElement, {attributes:true, attributeFilter:['class']});\n"
    + _ALIGN_HOOK_OLD)
_INFO_FB_OLD = "html:not(.mobile) #info-btn{ bottom:24px !important; right:96px !important; top:auto !important; }"
_INFO_FB_NEW = "html:not(.mobile) #info-btn{ bottom:30px !important; right:78px !important; top:auto !important; }"
_SB_FB_OLD = "position:fixed; bottom:24px; right:144px; z-index:300;"
_SB_FB_NEW = "position:fixed; bottom:30px; right:125px; z-index:300;"
# The magnifier is the homepage's, exactly: the same 20-unit drawing at the same
# 1.8 stroke (the engine's own 2.25 was a heavier line, and a 0.3/-0.3 view-box nudge
# that the homepage never had). Drawn 20px in the 35px circle, centred by
# `position:absolute; inset:0; margin:auto`, it is the homepage's 16px-in-28px at 1.25x.
_SG_OLD = ("'<svg viewBox=\"0 0 20 20\" width=\"20\" height=\"20\" fill=\"none\" stroke=\"currentColor\" '+\n"
           "           'stroke-width=\"2.25\" stroke-linecap=\"round\"")
_SG_NEW = ("'<svg viewBox=\"0 0 20 20\" width=\"20\" height=\"20\" fill=\"none\" stroke=\"currentColor\" '+\n"
           "           'stroke-width=\"1.8\" stroke-linecap=\"round\"")
PATCHES += [
    {"name": "desktop-search-glyph-matches-home", "old": _SG_OLD, "new": _SG_NEW, "count": 1},
    {"name": "desktop-controls-above-nodes", "old": _CTRL_OLD, "new": _CTRL_NEW, "count": 1},
    {"name": "desktop-mode-toggle-glyph", "old": _MODE_BTN_OLD, "new": _MODE_BTN_NEW, "count": 1},
    {"name": "desktop-mode-toggle-no-text", "old": _MODE_TXT_OLD, "new": _MODE_TXT_NEW, "count": 1},
    {"name": "desktop-mode-toggle-no-text-early", "old": _MODE_EARLY_OLD, "new": _MODE_EARLY_NEW, "count": 1},
    {"name": "desktop-controls-row", "old": _ALIGN_OLD, "new": _ALIGN_NEW, "count": 1},
    {"name": "desktop-controls-row-hook", "old": _ALIGN_HOOK_OLD, "new": _ALIGN_HOOK_NEW, "count": 1},
    {"name": "desktop-info-fallback", "old": _INFO_FB_OLD, "new": _INFO_FB_NEW, "count": 1},
    {"name": "desktop-search-fallback", "old": _SB_FB_OLD, "new": _SB_FB_NEW, "count": 1},
]

# ── mobile, opened directly: the page runs behind Safari's bars ────────────
# Safari (iOS 26 on) paints the strip behind the clock and the strip around the
# toolbar with ONE flat colour when a position:fixed (or sticky) element sits
# on that edge, and otherwise shows the page's real pixels there — but only
# pixels that are part of the document above and below the visible area.
# Measured in the iOS 27 simulator:
#   * a fixed header at the top, with or without a background, with its glass
#     on a child, or 1px down from the edge, gives the flat strip; the same
#     header position:absolute does not;
#   * Safari takes that colour when it first lays the page out and keeps it:
#     turning the header absolute afterwards (the 1.8.16 runway did it from a
#     script at the end of <body>) leaves the flat strip in place. So the rules
#     below live in <head> and the class that switches them on is set there.
# The recipe, for a mobile page that is the top-level document:
#   * the document scrolls a short runway: the body starts 80px down, is
#     exactly one screen tall, and 140px more runs below it; the page rests
#     80px down and is pinned there, so the body box IS the screen;
#   * every piece of fixed chrome becomes position:absolute inside the body —
#     the same place on screen, but no longer "fixed" to Safari;
#   * the wallpaper and its veil run past both ends of the body, and the
#     header's frosted glass (on a child) reaches up under the clock.
# Inside a frame (window.top !== window) nothing changes.
_RW_CLASS_OLD = "  if(ua || qp) document.documentElement.classList.add('mobile');"
_RW_CLASS_NEW = (_RW_CLASS_OLD + "\n"
                 "  // Before first layout — see engine_patches.py, mobile-runway-behind-bars.\n"
                 "  if((ua || qp) && window.top === window) document.documentElement.classList.add('rw');")

# Everything the engine positions fixed at the level of <body> / #app. A piece
# missed here is still caught by the sweep below, but only after Safari has
# looked, which is too late if it sits on the top or bottom edge.
_RW_FIXED = ("#title-bar, #nav-drawer-overlay, #nav-drawer, #nav, #timeline-label-bar, "
             "#back-to-overview-bar, #mode-toggle, #legend, #summary-wrap, #notes-toggle, "
             "#overview-toggle, #notes-panel, #hl-dot-desktop, #hl-palette-desktop, #note-dialog, "
             "#node-nav-bar, #detail-page, #hamburger-tab, #minimap-toggle, #minimap-wrap, "
             "#compass-rose, #nav-prev-btn, #nav-next-btn, #detail-back-fixed, #hl-mode-btn, "
             "#hl-color-palette, #hl-dot-btn, #tutorial-toggle, #tutorial-wrap, #info-btn, "
             "#timeline-return-pill, #wrap-warn-bar, #alto-icon-tip, #m-search, #m-search-results, "
             "#share-dialog, #account-btn, #account-scrim, #msp, #search-toggle, #ef-panel, "
             "#filter-toggle, #bg-panel, #bg-toggle")
# body overflow-x:clip: the closed panels wait just off the right edge, and as
# part of the page they made it twice the screen's width, which an iPhone pans
# into (overflow-x:hidden on the root does not stop a finger in iOS Safari).
# body * overscroll-behavior:contain: a panel's scroll never carries on into
# the page. (Kept here, not in the CSS: comments cost bytes in every page.)
_RW_HEAD_OLD = '<meta name="theme-color" id="meta-theme" content="#ffc59e">'
_RW_HEAD_NEW = _RW_HEAD_OLD + """
<style id="alto-runway">
html.mobile.rw{ overflow-y:scroll !important; overflow-x:hidden !important; height:auto !important;
  overscroll-behavior:none; touch-action:none; }
html.mobile.rw body *{ overscroll-behavior:contain; }
html.mobile.rw body:not(#_){ position:relative !important; height:100dvh !important; min-height:0 !important;
  margin:80px 0 140px !important; overflow-x:clip !important; overflow-y:visible !important;
  overscroll-behavior:none; touch-action:none; }
html.mobile.rw #app:not(#_){ height:100dvh !important; margin-top:0 !important; }
html.mobile.rw #page-bg:not(#_), html.mobile.rw #page-glass:not(#_){ position:absolute !important;
  top:-80px !important; bottom:auto !important; left:0 !important; right:0 !important;
  height:calc(100dvh + 220px) !important; }
html.mobile.rw #page-bg:not(#_){ background:var(--page-grad) !important; }
html.mobile.rw #nav:not(#_){ background:transparent !important; -webkit-backdrop-filter:none !important;
  backdrop-filter:none !important; }
html.mobile.rw #nav:not(#_)::before{ content:''; position:absolute; left:0; right:0; top:-80px; bottom:0;
  z-index:-1; pointer-events:none; background:var(--header-tint, var(--header-glass-bg));
  -webkit-backdrop-filter:blur(18px) saturate(180%); backdrop-filter:blur(18px) saturate(180%); }
html.mobile.rw :is(""" + _RW_FIXED + """):not(#_), html.mobile.rw .rw-abs:not(#_){ position:absolute !important; }
html.mobile.rw :is(#nav-drawer, #nav-drawer-overlay, #notes-panel, #minimap-wrap, #tutorial-wrap, #msp,
  #ef-panel, #bg-panel, #account-scrim):not(#_){ top:-80px !important; bottom:-140px !important; height:auto !important;
  padding-bottom:140px !important; }
html.mobile.rw :is(#ef-panel, #bg-panel):not(#_){ padding-bottom:0 !important; }
html.mobile.rw :is(#minimap-header, #tutorial-header):not(#_){ position:relative !important; }
html.mobile.rw #msp:not(#_){ padding-top:80px !important; }
html.mobile.rw :is(#notes-header, #minimap-header, #tutorial-header, #ef-panel > .ef-head, #bg-panel > .bg-head):not(#_){
  padding-top:96px !important; height:auto !important; }
html.mobile.rw #nav-drawer-header:not(#_){ padding-top:98px !important; height:auto !important; }
html.mobile.rw #detail-page:not(#_){ bottom:-140px !important; padding-bottom:240px !important; }
</style>"""

_RW_ANCHOR = '<script id="layout-settle">'
_RW_NEW = runway_script() + _RW_ANCHOR
PATCHES += [
    {"name": "mobile-runway-class-in-head", "old": _RW_CLASS_OLD, "new": _RW_CLASS_NEW, "count": 1},
    {"name": "mobile-runway-behind-bars", "old": _RW_HEAD_OLD, "new": _RW_HEAD_NEW, "count": 1},
    {"name": "mobile-runway-pin", "old": _RW_ANCHOR, "new": _RW_NEW, "count": 1},
]

# ── outline: a hub sits above its own children (ALTO-001) ───────────────────
# initLayout's Pass A only pushes a card down when it collides with one in a
# horizontally overlapping column. An outline hub lives in `center`, so the
# tall hubs before it push it down; its leaves live in `left`/`right`, collide
# with nothing, and stay where the cascade left them — beside or above the hub.
# Every spoke then has to double back (Torts: all 40 Liable / Not Liable
# pairs sat above their hub). Pass C restores the tree's order on an outline laid out as flow (a tree
# layout has it by construction);
# layout.resolve() carries the same pass so the baseY hints already satisfy
# it. The pass itself (blocks.HUBS_ABOVE_GLUE) is emitted on outline pages
# only; everywhere else this is a no-op guard, kept to one line because
# Terrarium's private page sits within a kilobyte of the 1,000,000-byte cap.
_HUB_ABOVE_OLD = "    // ── Pass B: act boundary enforcement ──\n"
_HUB_ABOVE_NEW = ("    if(window._altoHubsAbove&&_altoHubsAbove(positions,nodeHeights))"
                  "outerChanged=true;\n" + _HUB_ABOVE_OLD)
PATCHES += [
    {"name": "outline-hub-above-children", "old": _HUB_ABOVE_OLD,
     "new": _HUB_ABOVE_NEW, "count": 1},
]

# ── arrow keys follow the layout ────────────────────────────────────────────
# Arrows (and swipes) while a card is enlarged used to take the nearest node
# within 60 degrees of the direction, so on a tree "down" from a root could land
# on an outcome card two branches over. The rule now, everywhere:
#   * up/down on a TREE stays inside the branch the card belongs to (the subtree
#     of its nearest ancestor above it): down goes into the card's children,
#     else to the nearest card lined up below in the branch; up goes to the
#     nearest card lined up above in the branch, else to the branch's head —
#     so up from an outcome beside the first concept reaches its section;
#   * up/down on a FLOWING page: into the children / back to the parent on an
#     outline, else the previous / next card in the page's reading order
#     (ACT_SEQS), so no event is skipped;
#   * then (and for left/right) straight ahead: the nearest card lined up with
#     this one, same row or same column;
#   * only then the old nearest-within-60-degrees pick (and for diagonals).
# Arrow presses take one hop at a time (_hop, arrows-one-hop-at-a-time).
# Cards dimmed by any filter (slot `dimmed`, relation `rel-dimmed`, entity
# `ent-dimmed`) are skipped, as the retired compass-hop patch did.
_ARROWS_OLD = """  function focusNeighbor(dir){
    var cur=window._focusedNodeId&&nodeEl(window._focusedNodeId); if(!cur) return;
    var ta=_DIRANG[dir]; if(ta===undefined) return;
    var cx=cur.offsetLeft,cy=cur.offsetTop,best=null,bc=Infinity;
    allNodes().forEach(function(n){
      if(n===cur) return;
      // Filter-aware: when an era/weight filter dims a node, skip it so swipe/arrows
      // only hop between nodes that meet the active filter criteria.
      var _c=n.querySelector('.node-card'); if(_c&&_c.classList.contains('dimmed')) return;
      var dx=n.offsetLeft-cx,dy=n.offsetTop-cy;
      var dist=Math.sqrt(dx*dx+dy*dy); if(dist<1) return;
      var diff=Math.atan2(dy,dx)*180/Math.PI-ta;
      while(diff>180)diff-=360; while(diff<-180)diff+=360;
      if(Math.abs(diff)>60) return;                 // not in this compass sector
      var c=dist/Math.max(Math.cos(diff*Math.PI/180),0.2);
      if(c<bc){bc=c;best=n.id.slice(5);}
    });
    if(best) enterFocus(best);
  }"""
_ARROWS_NEW = """  function focusNeighbor(dir){
    var cur=window._focusedNodeId&&nodeEl(window._focusedNodeId); if(!cur) return;
    var ta=_DIRANG[dir]; if(ta===undefined) return;
    var O=window._ALTO_OUTLINE||{}, P=O.parent||{}, K=O.kids||{}, id=cur.id.slice(5);
    if(window._altoLanesNav){ var _ln=window._altoLanesNav(id, dir); if(_ln){ enterFocus(_ln); return; } }   // a horizontal timeline: along its lines
    // Every node's resting box in world px: style.left/top is its centre however
    // it is placed (margins, fly transform, tree), the card its size unzoomed.
    function g(n){
      if(!n) return null;
      var c=n.querySelector('.node-card'), z=c?(parseFloat(c.style.zoom)||1):1;
      var w=(c?c.offsetWidth:n.offsetWidth)/z, h=(c?c.offsetHeight:n.offsetHeight)/z;
      var x=parseFloat(n.style.left), y=parseFloat(n.style.top);
      if(isNaN(x)) x=n.offsetLeft; if(isNaN(y)) y=n.offsetTop;
      return {id:n.id.slice(5), x:x, y:y, l:x-w/2, r:x+w/2, t:y-h/2, b:y+h/2,
              dim:!!(c&&(c.classList.contains('dimmed')||c.classList.contains('rel-dimmed')||
                          c.classList.contains('ent-dimmed')))};
    }
    var C=g(cur), all=allNodes().filter(function(n){ return n!==cur; }).map(g)
                         .filter(function(q){ return !q.dim; });
    function byId(i){ for(var k=0;k<all.length;k++) if(all[k].id===i) return all[k]; return null; }
    function anc(i){ var a=[]; while(P[i]){ i=P[i]; a.push(i); } return a; }
    // the nearest card lined up with this one, ahead in the direction, from `pool`
    function aligned(pool,vert,sg){
      var best=null, bc=Infinity;
      pool.forEach(function(q){
        var along=(vert?q.y-C.y:q.x-C.x)*sg; if(along<=1) return;
        var ov=vert?Math.min(C.r,q.r)-Math.max(C.l,q.l):Math.min(C.b,q.b)-Math.max(C.t,q.t);
        if(ov<=0) return;
        if(along<bc){ bc=along; best=q.id; }
      });
      return best;
    }
    function kidsBelow(){
      var ks=(K[id]||[]).map(byId).filter(function(q){ return q && q.t>=C.b-1; });
      ks.sort(function(a,b){ return (Math.abs(a.x-C.x)-Math.abs(b.x-C.x)) || (a.t-b.t); });
      // none straight under it (a root whose children are split over two spines):
      // the first in the notes' order, not whichever spine happens to be nearer
      if(ks.length && Math.abs(ks[0].x-C.x)>=40){
        var kk=(K[id]||[]), first=null;
        for(var q2=0;q2<kk.length && !first;q2++) first=ks.filter(function(z){ return z.id===kk[q2]; })[0]||null;
        if(first) return first.id;
      }
      return ks.length ? ks[0].id : null;
    }
    var best=null, tree=!!window._altoTreeOn;
    if(dir==='n'||dir==='s'||dir==='e'||dir==='w'){
      var vert=(dir==='n'||dir==='s'), sg=(dir==='s'||dir==='e')?1:-1;
      if(vert && tree){
        // A tree: move within the branch this card belongs to — the subtree of
        // its nearest ancestor ABOVE it (for an outcome beside its concept, the
        // section over that concept) — before leaving it.
        var sc=null, as=anc(id);
        for(var k=0;k<as.length;k++){ var aq=byId(as[k]); if(aq && aq.b<=C.t+1){ sc=aq; break; } }
        var inScope=function(q){ return !!sc && (q.id===sc.id || anc(q.id).indexOf(sc.id)>=0); };
        // Outline reading order, for when the straight line misses: the next
        // sibling of this card (or of the nearest ancestor that has one) that
        // lies below it in the branch. A third leaf stacked in a flank lane has
        // nothing straight below it but ANOTHER concept's flank, which skipped
        // that concept altogether.
        var nextOutline=function(){
          for(var q=id; P[q]; q=P[q]){
            var sibs=K[P[q]]||[], at=sibs.indexOf(q);
            for(var j=at+1;j<sibs.length;j++){ var c=byId(sibs[j]); if(c && c.y>C.y+1) return c.id; }
            // the last of a spine: on to the next sibling, even when it begins the
            // other spine (a long list of concepts is split across two columns)
            for(var j2=at+1;j2<sibs.length;j2++){ var c2=byId(sibs[j2]); if(c2) return c2.id; }
          }
          // the last card of its unit: on to the head of the next unit
          if(typeof ACT_SEQS!=='undefined'){
            for(var a=0;a<ACT_SEQS.length;a++){ if(ACT_SEQS[a].indexOf(id)<0) continue;
              for(var b=a+1;b<ACT_SEQS.length;b++){ var f=ACT_SEQS[b][0]; if(f && byId(f)) return f; }
              break; }
          }
          return null;
        };
        // …and back the same way: from a spine card, the last card stacked under
        // its previous sibling (the third leaf), else that sibling itself.
        var prevOutline=function(){
          if((((window._ALTO_TREE_PLAN||{}).w||{})[id]||0)<250 || !P[id]) return null;   // a flank keeps its straight lane
          var sibs=K[P[id]]||[], at=sibs.indexOf(id);
          for(var j=at-1;j>=0;j--){
            var c=byId(sibs[j]); if(!c || !inScope(c) || c.y>=C.y-1) continue;
            var low=(K[c.id]||[]).map(byId).filter(function(q){ return q && q.t>=c.b-1 && q.y<C.y-1; });
            low.sort(function(a,b){ return b.y-a.y; });
            return low.length ? low[0].id : c.id;
          }
          return null;
        };
        if(dir==='s'){
          best=kidsBelow() || aligned(all.filter(inScope),true,1) || nextOutline();
        } else {
          best=prevOutline() || aligned(all.filter(inScope),true,-1);
          if(!best && sc) best=sc.id;                   // up to the branch's head
        }
      } else if(vert){
        // A flowing page: an outline's own structure first, then the page's
        // reading order (ACT_SEQS), so no event in between is skipped.
        if(dir==='s') best=kidsBelow();
        else if(P[id]){ var pq=byId(P[id]); if(pq && pq.b<=C.t+1) best=pq.id; }
        if(!best && typeof ACT_SEQS!=='undefined'){
          var seq=[].concat.apply([],ACT_SEQS), at=seq.indexOf(id);
          for(var i=at+sg; at>=0 && i>=0 && i<seq.length; i+=sg){ if(byId(seq[i])){ best=seq[i]; break; } }
        }
      }
      // straight ahead anywhere: same row for left/right, same column up/down
      if(!best) best=aligned(all,vert,sg);
    }
    // otherwise the nearest node within 60 degrees of the direction
    if(!best){
      var bc2=Infinity;
      all.forEach(function(q){
        var dx=q.x-C.x, dy=q.y-C.y, dist=Math.sqrt(dx*dx+dy*dy); if(dist<1) return;
        var diff=Math.atan2(dy,dx)*180/Math.PI-ta;
        while(diff>180)diff-=360; while(diff<-180)diff+=360;
        if(Math.abs(diff)>60) return;
        var c=dist/Math.max(Math.cos(diff*Math.PI/180),0.2);
        if(c<bc2){ bc2=c; best=q.id; }
      });
    }
    if(best) enterFocus(best);
  }
  // One hop at a time, each landing before the next starts: presses made during
  // a hop wait their turn (up to three), and a held key's auto-repeat adds at
  // most one, so holding a key walks at a readable pace instead of flickering.
  var _hopBusy=0, _hopQ=[];
  function _hop(dir,repeat){
    if(_hopBusy){ if(repeat ? !_hopQ.length : _hopQ.length<3) _hopQ.push(dir); return; }
    _hopBusy=1; focusNeighbor(dir);
    setTimeout(function(){ _hopBusy=0; if(_hopQ.length) _hop(_hopQ.shift()); },
               (window._altoFlyMs||420)+40);   // the next hop waits for this glide
  }"""
_HOP_KEY_OLD = "    if(!d) return; e.preventDefault(); focusNeighbor(d);"
_HOP_KEY_NEW = "    if(!d) return; e.preventDefault(); _hop(d, e.repeat);"
PATCHES += [
    {"name": "arrows-follow-the-layout", "old": _ARROWS_OLD, "new": _ARROWS_NEW, "count": 1},
    {"name": "arrows-one-hop-at-a-time", "old": _HOP_KEY_OLD, "new": _HOP_KEY_NEW, "count": 1},
]

# ── outline: the desktop tree replaces the resolver's positions ─────────────
# detail_extras.TREE_GLUE lays an outline out as a tree (layout.outline_tree)
# over the measured heights and sets each node's displayX; the numeral check
# must then read that x, not the column's.
_TREE_HOOK_OLD = "  runResolver();\n"
_TREE_HOOK_NEW = ("  runResolver();\n"
                  "  if(window._altoTree) window._altoTree(positions, nodeHeights);\n")
_TREE_NUM_OLD = "      const nodeX    = COL_X[n.col];\n"
_TREE_NUM_NEW = "      const nodeX    = (n.displayX !== undefined) ? n.displayX : COL_X[n.col];\n"
# A tree's spine is one straight trunk: the lines from a section to each card
# down its spine run behind the cards in between, as the drawing of a tree
# does. The router would otherwise look for a clear lane beside them and send
# some out into the gap between branches and back.
_TREE_LANE_OLD = "          try { _lane = laneRoute(sx, sy, tx, ty, srcNode.id, tgtNode.id); }\n"
_TREE_LANE_NEW = ("          try { _lane = window._altoTreeOn ? null"
                  " : laneRoute(sx, sy, tx, ty, srcNode.id, tgtNode.id); }\n")
# A parent's lines to the children below it leave on ONE shared horizontal,
# halfway down the gap under it, so a root reads as a clean T into its
# branches and a fan off one card is a single trunk (the router's own
# forced-midY mechanism, which its trunk merge already uses).
_TREE_MID_OLD = "        try { computeTrunks(); } catch(e){\n"
_TREE_MID_NEW = ("        try { computeTrunks(); if(window._altoTreeMid) window._altoTreeMid(forcedMid); }"
                 " catch(e){\n")
_TREE_LANE2_OLD = "              try { _lr = laneRoute(sx0, _sy0, tx0, _ty0, c[0], c[1]); } catch(e){}\n"
_TREE_LANE2_NEW = ("              try { _lr = window._altoTreeOn ? null"
                   " : laneRoute(sx0, _sy0, tx0, _ty0, c[0], c[1]); } catch(e){}\n")
# Fanned tree lines (brief.tree_lines="fan"): each child down a spine gets its
# own line, which meets the top of the spine's first card at its own point and
# drops from there. TREE_GLUE records those end points in _altoEdgeTX; the
# router's three readers of a line's end x take them.
_FAN_TX = "(window._altoEdgeTX&&window._altoEdgeTX[{s}+'|'+{t}]!=null?window._altoEdgeTX[{s}+'|'+{t}]:({x}))"
_FAN_DRAW_OLD = "        var tx = tgtNode.displayX !== undefined ? tgtNode.displayX : COL_X[tgtNode.col];\n"
_FAN_DRAW_NEW = ("        var tx = " + _FAN_TX.format(s="srcNode.id", t="tgtNode.id",
                 x="tgtNode.displayX !== undefined ? tgtNode.displayX : COL_X[tgtNode.col]") + ";\n")
_FAN_REG_OLD = "              var tx0 = t.displayX !== undefined ? t.displayX : COL_X[t.col];\n"
_FAN_REG_NEW = ("              var tx0 = " + _FAN_TX.format(s="c[0]", t="c[1]",
                x="t.displayX !== undefined ? t.displayX : COL_X[t.col]") + ";\n")
_FAN_TRUNK_OLD = "          var tx = tgt.displayX !== undefined ? tgt.displayX : COL_X[tgt.col];\n"
_FAN_TRUNK_NEW = ("          var tx = " + _FAN_TX.format(s="c[0]", t="c[1]",
                  x="tgt.displayX !== undefined ? tgt.displayX : COL_X[tgt.col]") + ";\n")
PATCHES += [
    {"name": "outline-tree-layout", "old": _TREE_HOOK_OLD, "new": _TREE_HOOK_NEW, "count": 1},
    {"name": "tree-fan-draw", "old": _FAN_DRAW_OLD, "new": _FAN_DRAW_NEW, "count": 1},
    {"name": "tree-fan-registry", "old": _FAN_REG_OLD, "new": _FAN_REG_NEW, "count": 1},
    {"name": "tree-fan-trunks", "old": _FAN_TRUNK_OLD, "new": _FAN_TRUNK_NEW, "count": 1},
    {"name": "outline-tree-spine-registry", "old": _TREE_LANE2_OLD, "new": _TREE_LANE2_NEW, "count": 1},
    {"name": "outline-tree-shared-elbow", "old": _TREE_MID_OLD, "new": _TREE_MID_NEW, "count": 1},
    {"name": "outline-tree-spine-is-straight", "old": _TREE_LANE_OLD, "new": _TREE_LANE_NEW, "count": 1},
    {"name": "numeral-check-reads-display-x", "old": _TREE_NUM_OLD, "new": _TREE_NUM_NEW, "count": 1},
]

# ── node-card chip label sits above the hovered chip's row (ALTO-007) ───────
# The label was pinned with bottom:calc(100% + 8px) of the footer, so in a
# footer whose chips wrap onto several rows it always rose above the first
# row. Anchor it to the chip's own offsetTop instead and lift it by its height.
_TIP_POS_OLD = "  position:absolute; left:0; bottom:calc(100% + 8px); z-index:5;"
_TIP_POS_NEW = "  position:absolute; left:0; top:0; z-index:5;"
_TIP_REST_OLD = "  transform:translateX(-50%) translateY(3px);"
_TIP_REST_NEW = "  translate:-50% -100%;"
_TIP_ON_OLD = "  opacity:1; transform:translateX(-50%) translateY(0);"
_TIP_ON_NEW = "  opacity:1; /* label shown once placed */"
_TIP_JS_OLD = "    tip.style.left=(chip.offsetLeft + chip.offsetWidth/2)+'px';"
_TIP_JS_NEW = _TIP_JS_OLD + "\n    window._altoTipShow(chip,tip);"

# ── index pages and node names route through showDetail (ALTO-004/006) ──────
# Both hooks are guards that do nothing unless the page defines the function
# (detail_extras: outline pages / pages with an index axis).
_INDEX_OLD = "function showDetail(type,id){\n  window._currentDetailType = type;"
_INDEX_NEW = ("function showDetail(type,id){\n"
              "  if(type==='index'&&window._altoAxisIndex) return _altoAxisIndex(id);\n"
              "  window._currentDetailType = type;")
_NAME_D_OLD = "    name = n.title;\n"
_NAME_D_NEW = "    name = window._altoNodeName ? _altoNodeName(n) : n.title;\n"
_NAME_M_OLD = "+nd.title+'</div>'"
_NAME_M_NEW = "+(window._altoNodeName?_altoNodeName(nd):nd.title)+'</div>'"
PATCHES += [
    {"name": "chip-tip-row-top", "old": _TIP_POS_OLD, "new": _TIP_POS_NEW, "count": 1},
    {"name": "chip-tip-row-rest", "old": _TIP_REST_OLD, "new": _TIP_REST_NEW, "count": 1},
    {"name": "chip-tip-row-on", "old": _TIP_ON_OLD, "new": _TIP_ON_NEW, "count": 1},
    {"name": "chip-tip-row-js", "old": _TIP_JS_OLD, "new": _TIP_JS_NEW, "count": 1},
    {"name": "show-detail-index-route", "old": _INDEX_OLD, "new": _INDEX_NEW, "count": 1},
    {"name": "node-name-desktop", "old": _NAME_D_OLD, "new": _NAME_D_NEW, "count": 1},
    {"name": "node-name-mobile-peek", "old": _NAME_M_OLD, "new": _NAME_M_NEW, "count": 1},
]

# ── help: the INFO panel (desktop) and the HOW TO USE sheet (phone) ────────
# The engine's help described the source novel (scenes, a story, Characters /
# Environments / Themes, a plot summary, "5 acts") and the controls as they were
# before the edit toggle, the back button and the top-row search. It is rewritten
# for any material and for the page as it is now. Each text keeps the one
# sentence the builder fills in (blocks.py help_sections_*: the names of this
# timeline's own page sections) between a static head and a static tail, so each
# half is anchored on the engine's own words. The panel's phone paragraphs were
# never shown (a phone has the sheet instead) and go.
# The recommended route is said once in each: build with Claude from the user's
# own material, then adjust by hand (the Edit toggle's two halves say the rest).
_HELP_D_HEAD_OLD = (
    '    <div id="info-content">\n'
    '      <p class="info-desktop" style="margin:0 0 8px"><strong>Overview</strong> &#8212; click the &#10022; tab on the right edge for an act-by-act plot summary. Click any highlighted phrase to open that scene.</p>\n'
    '      <p class="info-desktop" style="margin:5px 0"><strong>Navigate</strong> &#8212; ')
_HELP_D_HEAD_NEW = (
    '    <div id="info-content">\n'
    '      <p class="info-desktop" style="margin:0 0 8px"><strong>Making it</strong> &#8212; build by hand if you like. The suggested route: have Claude build it from your own notes or readings, then make small adjustments yourself.</p>\n'
    '      <p class="info-desktop" style="margin:5px 0"><strong>Open a card</strong> &#8212; ')
_HELP_D_TAIL_OLD = (
    '. On a detail page, &#8592; &#8594; arrows step prev/next; Escape returns to the timeline.</p>\n'
    '      <p class="info-desktop" style="margin:5px 0"><strong>Characters &#183; Environments &#183; Themes</strong> &#8212; chips in the nav open their detail pages. The symbols in each card&#8217;s footer do the same.</p>\n'
    '      <p class="info-desktop" style="margin:5px 0"><strong>Search</strong> &#8212; click the magnifier bubble at bottom-right (beside the &#9432;) to search scenes, detail pages, and the overview. Click a result to jump straight there.</p>\n'
    '      <p class="info-desktop" style="margin:5px 0"><strong>Highlight text</strong> &#8212; click and drag over any text on a card or detail page. The color dot at center-bottom changes highlight color.</p>\n'
    '      <p class="info-desktop" style="margin:5px 0"><strong>Add a note</strong> &#8212; click a highlighted passage to open a note dialog. Or click the <em>+</em> in the Notes panel for a freeform note.</p>\n'
    '      <p class="info-desktop" style="margin:5px 0"><strong>Notes panel</strong> &#8212; click the <em>Notes</em> tab on the right edge to see all highlights and notes.</p>\n'
    '      <p class="info-desktop" style="margin:5px 0"><strong>Notes report</strong> &#8212; click <em>Generate Report</em> at the bottom of the Notes panel for a printable report of your highlights and notes. It also saves to your report repository.</p>\n'
    '      <p class="info-desktop" style="margin:5px 0"><strong>Share &amp; print</strong> &#8212; open the <em>Notes</em> panel and click the share arrow in its header to send a copy of this timeline (with or without your notes), or print.</p>\n'
    '      <p class="info-desktop" style="margin:5px 0"><strong>Account</strong> &#8212; the person bubble at the bottom left signs you in so your work can follow you.</p>\n'
    '      <p class="info-desktop" style="margin:5px 0"><strong>Alto home</strong> &#8212; click the Alto clef (top-left) or the Alto wordmark (top-right) to open your Alto homepage.</p>\n'
    '      <p class="info-mobile" style="margin:0 0 8px"><strong>Swipe</strong> a card left or right to move through scenes.</p>\n'
    '      <p class="info-mobile" style="margin:5px 0"><strong>Tap a card</strong> to open its detail page. Tap <em>Back</em> (top-left) to return.</p>\n'
    '      <p class="info-mobile" style="margin:5px 0"><strong>MENU</strong> (top-right) opens Character / Environment / Theme chips &#8212; tap one for its detail page.</p>\n'
    '      <p class="info-mobile" style="margin:5px 0"><strong>MAP</strong> (top-left) shows all 5 acts. From a detail page, tap any node to jump straight to its scene.</p>\n'
    '      <p class="info-mobile" style="margin:5px 0"><strong>NOTES / MARK</strong> live on each node. In NOTES, tap a highlighted passage to add a note, or tap the <em>+</em> for a freeform note.</p>\n'
    '      <p class="info-mobile" style="margin:5px 0"><strong>Overview</strong> &#8212; tap a phrase in MENU&rsquo;s Overview to jump to that scene.</p>\n'
    '    </div>\n')
_HELP_D_TAIL_NEW = (
    '. <em>&#8592; &#8594;</em> step between pages; <em>&#8592; Timeline</em> or Escape goes back.</p>\n'
    '      <p class="info-desktop" style="margin:5px 0"><strong>Overview</strong> &#8212; the &#10022; tab on the right edge summarizes the timeline; click a phrase to jump to its card.</p>\n'
    '      <p class="info-desktop" style="margin:5px 0"><strong>Groups &amp; filters</strong> &#8212; the chips along the top open group pages. The <em>Filter</em> tab narrows the cards; double-click it to switch every filter off, and again to bring them back.</p>\n'
    '      <p class="info-desktop" style="margin:5px 0"><strong>Background</strong> &#8212; the picture tab under Filter puts a colour, a pattern or a photograph of space, nature or a city behind this timeline (a bright picture in the light theme, a dim one in the dark). Each timeline keeps its own.</p>\n'
    '      <p class="info-desktop" style="margin:5px 0"><strong>Highlight &amp; note</strong> &#8212; drag over text to highlight it (the dot at bottom center sets the color); click a highlight to add a note.</p>\n'
    '      <p class="info-desktop" style="margin:5px 0"><strong>Notes</strong> &#8212; the <em>Notes</em> tab holds your highlights and reports, and shares or prints. Its <em>Freewrite</em> mode is for writing an outline or answer as you browse; tick <em>Attach my Freewrite</em> above <em>Generate Report</em> to put it in a report too.</p>\n'
    '      <p class="info-desktop" style="margin:5px 0"><strong>Edit</strong> &#8212; <em>Edit with Claude</em>: bigger changes. <em>Edit manually</em>: small ones. Click words, drag, swap or move cards, add list entries. &#8984;Z undoes.</p>\n'
    '      <p class="info-desktop" style="margin:5px 0"><strong>Controls</strong> &#8212; bottom right: search, this &#9432;, light or dark, Edit. Bottom left signs you in; the Alto clef or wordmark opens your homepage.</p>\n'
    '    </div>\n')

_HELP_M_HEAD_OLD = (
    "    '    <h3>Moving between scenes</h3>',\n"
    "    '    <p>Swipe a card left or right to step through the story in order.</p>',\n"
    "    '    <h3>Open a scene</h3>',\n"
    "    '    <p>")
_HELP_M_HEAD_NEW = (
    "    '    <h3>Moving between cards</h3>',\n"
    "    '    <p>Swipe a card left or right to step through the timeline in order.</p>',\n"
    "    '    <h3>Open a card</h3>',\n"
    "    '    <p>")
_HELP_M_TAIL_OLD = (
    " Tap <strong>Back</strong> (top-left) to return.</p>',\n"
    "    '    <h3>MENU</h3>',\n"
    "    '    <p>Tap <strong>MENU</strong> (top-right) for Characters, Environments, and Themes. Tap one to open its detail page.</p>',\n"
    "    '    <h3>MAP</h3>',\n"
    "    '    <p>Tap <strong>MAP</strong> (top-left) to see all 5 acts. From the main timeline, tapping a node features it. From a detail page, tapping a node jumps to that scene.</p>',\n"
    "    '    <h3>Overview</h3>',\n"
    "    '    <p>Tap <strong>Overview</strong> in <strong>MENU</strong> to read the plot summary. Tap a phrase there to jump to its scene.</p>',\n"
    "    '    <h3>MARK and NOTES</h3>',\n"
    "    '    <p>Tap <strong>MARK</strong> (bottom-right) to highlight text &#8212; a color palette appears above the Search pill; drag over text to highlight it. Tap <strong>NOTES</strong> to see everything you&#8217;ve saved; tap a highlight there to add a note.</p>',\n"
    "    '    <h3>Search</h3>',\n"
    "    '    <p>Tap the <strong>Search</strong> pill at the bottom center to search scenes, detail pages, and the overview. Tap a result to jump straight there.</p>',\n"
    "    '    <h3>Share &amp; Print</h3>',\n"
    "    '    <p>Open <strong>NOTES</strong> and tap the share arrow in the panel header. <strong>Create Link</strong> builds your link; then <strong>Copy Link</strong> copies it. Print options live in the same dialog.</p>',\n")
_HELP_M_TAIL_NEW = (
    " Tap <strong>BACK</strong> (bottom-left) to return.</p>',\n"
    "    '    <h3>MENU</h3>',\n"
    "    '    <p>Tap <strong>MENU</strong> (top-right) for the timeline&#8217;s groups and index pages. Tap one to open its page.</p>',\n"
    "    '    <h3>MAP</h3>',\n"
    "    '    <p>Tap <strong>MAP</strong> (top-left) to see every card, grouped by section. Tap one to feature it, or, from a detail page, to jump to it.</p>',\n"
    "    '    <h3>Overview</h3>',\n"
    "    '    <p>Tap <strong>Overview</strong> in <strong>MENU</strong> to read the summary. Tap a phrase there to jump to its card.</p>',\n"
    "    '    <h3>Search and filter</h3>',\n"
    "    '    <p>Tap <strong>Search</strong> at the top to find a card, page or phrase (on a detail page it is <strong>FIND</strong>, bottom-left). <strong>FILTER</strong> narrows the cards; double-tap it to switch every filter off, and again to bring them back.</p>',\n"
    "    '    <h3>Background</h3>',\n"
    "    '    <p>Tap <strong>SCENE</strong> (left edge, above INFO) to put a colour, a pattern or a photograph behind this timeline. Each timeline keeps its own.</p>',\n"
    "    '    <h3>MARK and NOTES</h3>',\n"
    "    '    <p>Tap <strong>MARK</strong> (bottom-right), then drag over text to highlight it; the dot at the bottom sets the color. Tap <strong>NOTES</strong> to see everything you&#8217;ve saved; tap a highlight there to add a note. Its <strong>Freewrite</strong> switch opens a page for writing an outline or answer as you move around; tick <strong>Attach my Freewrite</strong> above <strong>Generate Report</strong> to put it in a report too.</p>',\n"
    "    '    <h3>Share &amp; Print</h3>',\n"
    "    '    <p>Open <strong>NOTES</strong> and tap the share arrow in its header to send a copy of this timeline or print it.</p>',\n"
    "    '    <h3>Making and editing</h3>',\n"
    "    '    <p>You can build a timeline entirely by hand on a computer, but the suggested route is to have Claude build it from your own notes, outlines or readings, then make small adjustments and revisions yourself. On your own timeline, <strong>Edit this page</strong> (at the foot of a page) changes its words right here.</p>',\n")

# ── detail-page swipe preview matches the page it becomes ──────────────────
# The page sliding in under the finger was painted a flat var(--bg) (near-black
# in dark mode), while the real detail page is frosted glass over the
# gradient — so every swipe showed a flat page that then "flashed" into the
# glass one on landing. Give the preview the detail page's own computed
# background, blur and box (absolute under the runway, reaching under the
# bottom bar), so the page that lands is the page you saw sliding in.
_PEEK_BG_OLD = "      var inner = '';\n      var actNames = "
_PEEK_BG_NEW = (
    "      var _dcs = getComputedStyle(detailPage);\n"
    "      if(_dcs.backgroundColor !== 'rgba(0, 0, 0, 0)'){ el.style.background = _dcs.backgroundColor;\n"
    "        el.style.webkitBackdropFilter = el.style.backdropFilter = _dcs.backdropFilter || _dcs.webkitBackdropFilter || ''; }\n"
    "      el.style.position = _dcs.position; el.style.bottom = _dcs.bottom;\n"
    + _PEEK_BG_OLD)
PATCHES += [
    {"name": "help-info-head", "old": _HELP_D_HEAD_OLD, "new": _HELP_D_HEAD_NEW, "count": 1},
    {"name": "help-info-tail", "old": _HELP_D_TAIL_OLD, "new": _HELP_D_TAIL_NEW, "count": 1},
    {"name": "help-sheet-head", "old": _HELP_M_HEAD_OLD, "new": _HELP_M_HEAD_NEW, "count": 1},
    {"name": "help-sheet-tail", "old": _HELP_M_TAIL_OLD, "new": _HELP_M_TAIL_NEW, "count": 1},
    {"name": "detail-peek-matches-page", "old": _PEEK_BG_OLD, "new": _PEEK_BG_NEW, "count": 1},
]

# ── no pop-up bar of active filters ─────────────────────────────────────────
# The engine showed what was filtered as a bar across the top of the page, a
# segment per filter with an ✕ to clear it (a desktop banner beside "Back to
# Overview", a docked bar on a phone). Filters live in the Filter toggle now:
# its count says what is on, its panel changes it, a double-click turns every
# filter off and on again (filter_panel.py). The segments are never shown, and
# the phone's `filter-active` class, which moved the search pill and the detail
# page down to make room for the bar, is never set. Back to Overview and Back to
# <previous page> share the desktop row and are untouched.
_NOBAR_D_OLD = ("    window._updateDesktopFilterBar = function(){\n"
                "      var s = _ensureSegments();\n"
                "      var f = _activeFilters || {};\n")
_NOBAR_D_NEW = ("    window._updateDesktopFilterBar = function(){\n"
                "      var s = _ensureSegments();\n"
                "      var f = {};   // active filters are shown by the Filter toggle, never as a bar\n")
_NOBAR_M_OLD = r"""  // ── Mobile filter bar (Patch 4) ─────────────────────────────────────────
  function _ensureFilterBar(){
    if(document.getElementById('mobile-filter-bar')) return;
    var bar = document.createElement('div');
    bar.id = 'mobile-filter-bar';
    bar.innerHTML = '<button class="mfb-zone mfb-era" hidden></button><button class="mfb-zone mfb-weight" hidden></button>';
    document.body.appendChild(bar);
    bar.querySelector('.mfb-era').addEventListener('click', function(e){
      e.stopPropagation();
      var era = window._mobileFilter.era;
      if(era) window.setMobileFilter('era', era); // toggle off
    });
    bar.querySelector('.mfb-weight').addEventListener('click', function(e){
      e.stopPropagation();
      var w = window._mobileFilter.weight;
      if(w) window.setMobileFilter('weight', w); // toggle off
    });
  }
  window._updateMobileFilterBar = function(){
    _ensureFilterBar();
    var bar = document.getElementById('mobile-filter-bar'); if(!bar) return;
    var f = window._mobileFilter;
    var era = bar.querySelector('.mfb-era');
    var w   = bar.querySelector('.mfb-weight');
    if(f.era){ era.removeAttribute('hidden'); era.textContent = '\u2715 ' + (ERA_LABELS[f.era]||f.era); }
    else { era.setAttribute('hidden',''); }
    if(f.weight){ w.removeAttribute('hidden'); w.textContent = '\u2715 ' + (WEIGHT_LABELS[f.weight]||f.weight); }
    else { w.setAttribute('hidden',''); }
    var anyActive = !!(f.era || f.weight);
    bar.classList.toggle('active', anyActive);
    document.documentElement.classList.toggle('filter-active', anyActive);
  };
"""
_NOBAR_M_NEW = ("  // Active filters are shown by the Filter tile (its count), never as a bar.\n"
                "  window._updateMobileFilterBar = function(){\n"
                "    document.documentElement.classList.remove('filter-active');\n"
                "  };\n")
PATCHES += [
    {"name": "filters-never-show-a-bar-desktop", "old": _NOBAR_D_OLD, "new": _NOBAR_D_NEW, "count": 1},
    {"name": "filters-never-show-a-bar-mobile", "old": _NOBAR_M_OLD, "new": _NOBAR_M_NEW, "count": 1},
]


def apply_patches(html: str) -> str:
    for p in PATCHES:
        found = html.count(p["old"])
        if found != p["count"]:
            raise PatchError(
                f"engine patch {p['name']!r}: anchor matched {found} times, "
                f"expected {p['count']} — the engine moved under it; re-derive "
                "the patch against the current template or retire it")
        html = html.replace(p["old"], p["new"])
    return html


# ── search: one index, one ranking, every surface (alto/build/search.py) ────
# The desktop box, the mobile pill and the detail page's FIND panel all ran a
# verbatim indexOf over node text: no prefixes, no typos, no case or
# restatement pages, twelve rows at most, and a 1.7s flash on the card. Each
# now hands its query to window._altoSearch (emitted on every page by the
# builder's tail) and keeps its own look; the old code stays as the fallback.
_SR_SEARCH_OLD = "  function search(q){\n    q=(q||'').trim().toLowerCase();"
_SR_SEARCH_NEW = ("  function search(q){\n    if(window._altoSearch) return window._altoSearch.search(q);\n"
                  "    q=(q||'').trim().toLowerCase();")
_SR_SNIP_OLD = "  function snippet(text, q){\n    text=text||'';"
_SR_SNIP_NEW = ("  function snippet(text, q){\n    if(window._altoSearch) return window._altoSearch.snippet(text,q);\n"
                "    text=text||'';")
_SR_RENDER_OLD = "  function render(q){\n    var res=search(q); resultsEl.innerHTML='';"
_SR_RENDER_NEW = (
    "  function render(q){\n"
    "    if(window._altoSearch){\n"
    "      var S=window._altoSearch; resultsEl.innerHTML='';\n"
    "      if((q||'').trim().length<2){ resultsEl.classList.remove('has-results'); return; }\n"
    "      var rs=S.search(q);\n"
    "      resultsEl.innerHTML=rs.length?S.rowsHtml(rs,'data-i'):'<div class=\"search-empty\">No matches.</div>';\n"
    "      Array.prototype.forEach.call(resultsEl.querySelectorAll('.search-result'), function(b){\n"
    "        b.addEventListener('click', function(){ var o=rs[+b.getAttribute('data-i')]; closeSearch(); if(o) S.go(o); });\n"
    "      });\n"
    "      resultsEl.classList.add('has-results'); resultsEl.scrollTop=0; return;\n"
    "    }\n"
    "    var res=search(q); resultsEl.innerHTML='';")
_SR_LAND_OLD = "  function searchGoToNode(id){\n    var dp=document.getElementById('detail-page');"
_SR_LAND_NEW = ("  function searchGoToNode(id){\n    if(window._altoSearch){ window._altoSearch.land(id); return; }\n"
                "    var dp=document.getElementById('detail-page');")
_SR_M_ROWS_OLD = ("    var ql=q.toLowerCase();\n    res.forEach(function(o,i){\n"
                  "      var b=document.createElement('button');")
_SR_M_ROWS_NEW = ("    if(window._altoSearch){ resultsEl.innerHTML=window._altoSearch.rowsHtml(res,'data-i');"
                  " resultsEl.classList.add('has-results'); resultsEl.scrollTop=0; return; }\n"
                  + _SR_M_ROWS_OLD)
_SR_M_NAV_OLD = "  function navigate(r){\n    closeSearch();\n    var sw=document.getElementById('summary-wrap');"
_SR_M_NAV_NEW = ("  function navigate(r){\n    closeSearch();\n"
                 "    if(window._altoSearch && r && r.fields){ window._altoSearch.go({r:r, q:r._q||''}); return; }\n"
                 "    var sw=document.getElementById('summary-wrap');")
PATCHES += [
    {"name": "search-core-ranked", "old": _SR_SEARCH_OLD, "new": _SR_SEARCH_NEW, "count": 1},
    {"name": "search-core-snippet", "old": _SR_SNIP_OLD, "new": _SR_SNIP_NEW, "count": 1},
    {"name": "search-desktop-grouped-rows", "old": _SR_RENDER_OLD, "new": _SR_RENDER_NEW, "count": 1},
    {"name": "search-lands-enlarged-ringed", "old": _SR_LAND_OLD, "new": _SR_LAND_NEW, "count": 1},
    {"name": "search-mobile-grouped-rows", "old": _SR_M_ROWS_OLD, "new": _SR_M_ROWS_NEW, "count": 1},
    {"name": "search-mobile-lands", "old": _SR_M_NAV_OLD, "new": _SR_M_NAV_NEW, "count": 1},
]

# The desktop box can grow into a large panel (search.py, SX_*): the expand
# control re-renders the rows in place, and Esc shrinks it before it closes.
_SX_RENDER_OLD = "  window._searchClose=closeSearch;\n"
_SX_RENDER_NEW = _SX_RENDER_OLD + "  window._altoSearchRender=render;\n"
_SX_ESC_OLD = "    var fn=window[TOGGLES[open[0]]];\n"
_SX_ESC_NEW = ("    if(open[0]==='search' && window._altoSXCollapse && window._altoSXCollapse()) return true;\n"
               + _SX_ESC_OLD)
PATCHES += [
    {"name": "search-expose-render", "old": _SX_RENDER_OLD, "new": _SX_RENDER_NEW, "count": 1},
    {"name": "search-esc-shrinks-first", "old": _SX_ESC_OLD, "new": _SX_ESC_NEW, "count": 1},
]


# ── the ✎ Edit timeline tile sits inside the timeline's own background ──────
# detail_extras.EDIT_TILE hangs the tile after the last unit. Below the glass
# slab it read as a separate bar on the bare page gradient (Luke: extend the
# background instead). The slab, its per-unit tint and the bands are all drawn
# from computeActBands, so the last band grows by the tile's row — set by the
# tile's script (window._altoEditRoom) only where the tile shows; a share or a
# phone adds nothing.
_EDIT_ROOM_OLD = "    bands[bands.length-1].endY += 100; // canvas breathing room"
_EDIT_ROOM_NEW = ("    bands[bands.length-1].endY += 100 + (window._altoEditRoom || 0); "
                  "// canvas breathing room (+ the Edit timeline tile's row)")

PATCHES += [
    {"name": "edit-tile-inside-the-last-band", "old": _EDIT_ROOM_OLD,
     "new": _EDIT_ROOM_NEW, "count": 1},
]


# ── a chip that already shows its name gets no hover label ──────────────────
# A named chip (a hide_nav axis value, drawn as text) says what it is on its
# face, so the popup only repeated it. Glyph chips and letter/symbol chips
# (the letter stands for something) keep the label, and so does a named chip
# whose text is cut off by its max-width ellipsis: only then is the label news.
# The label stays directly over the hovered chip (ALTO-007 above). Desktop
# hover is pure CSS, so the JS flags the chip (data-notip) on mouseover and the
# rule skips flagged chips; the phone long-press asks the same helper.
_NOTIP_CSS_OLD = ("html:not(.mobile) .node-card .csym-btn:hover ~ .chip-tip,\n"
                  "html:not(.mobile) .node-card .esym-btn:hover ~ .chip-tip,\n"
                  "html:not(.mobile) .node-card .tsym-btn:hover ~ .chip-tip{")
_NOTIP_CSS_NEW = "html:not(.mobile) .node-card .chip-tip.on{"
_NOTIP_JS_OLD = "    if(!label) return;\n    var tip=foot.querySelector(':scope > .chip-tip');"
_NOTIP_JS_NEW = (
    "    if(!label) return;\n"
    "    if(window._altoChipNoTip(chip,label)){ chip.setAttribute('data-notip',''); return; }\n"
    "    chip.removeAttribute('data-notip');\n"
    "    var tip=foot.querySelector(':scope > .chip-tip');")
_NOTIP_FN_OLD = "  var SEL='.csym-btn,.esym-btn,.tsym-btn';\n  document.addEventListener('mouseover', function(e){"
_NOTIP_FN_NEW = (
    "  var SEL='.csym-btn,.esym-btn,.tsym-btn';\n"
    "  // The label is placed by what is on screen (offsetTop/offsetLeft are in another unit\n"
    "  // once page, card hover-grow and chip are zoomed or scaled, and it differs per\n"
    "  // engine): probe how far one style px moves it, then put its box on the chip's top\n"
    "  // edge, 3px clear. It stays hidden while the card finishes growing, follows the\n"
    "  // chip frame by frame, and only then fades in (opacity only, nothing to jump).\n"
    "  var _tt=0, _raf=0;\n"
    "  function tipFit(chip,tip){\n"
    "    var y0=chip.offsetTop, x0=chip.offsetLeft+chip.offsetWidth/2;\n"
    "    tip.style.top=y0+'px'; tip.style.left=x0+'px';\n"
    "    var a=tip.getBoundingClientRect();\n"
    "    tip.style.top=(y0+50)+'px'; tip.style.left=(x0+50)+'px';\n"
    "    var b=tip.getBoundingClientRect();\n"
    "    var ky=(b.top-a.top)/50, kx=(b.left-a.left)/50, c=chip.getBoundingClientRect();\n"
    "    if(ky>0.05 && kx>0.05){\n"
    "      tip.style.top=(y0+(c.top-3-a.bottom)/ky)+'px';\n"
    "      tip.style.left=(x0+(c.left+c.width/2-(a.left+a.width/2))/kx)+'px';\n"
    "    } else { tip.style.top=y0+'px'; tip.style.left=x0+'px'; }\n"
    "  }\n"
    "  function tipHide(tip){\n"
    "    clearTimeout(_tt); cancelAnimationFrame(_raf); tip._chip=null; tip.classList.remove('on');\n"
    "  }\n"
    "  window._altoTipShow=function(chip,tip){\n"
    "    if(tip._chip===chip) return;\n"
    "    tipHide(tip);\n"
    "    tip.style.transition='none'; tip.classList.remove('on'); void tip.offsetWidth; tip.style.transition='';\n"
    "    tip._chip=chip;\n"
    "    var t0=performance.now();\n"
    "    (function frame(){\n"
    "      if(tip._chip!==chip) return;\n"
    "      tipFit(chip,tip);\n"
    "      if(performance.now()-t0<700) _raf=requestAnimationFrame(frame);\n"
    "    })();\n"
    "    _tt=setTimeout(function(){ if(tip._chip===chip) tip.classList.add('on'); },120);\n"
    "  };\n"
    "  document.addEventListener('mouseout', function(e){\n"
    "    var chip=e.target && e.target.closest && e.target.closest(SEL);\n"
    "    if(!chip || (e.relatedTarget && chip.contains(e.relatedTarget))) return;\n"
    "    var foot=chip.closest('.node-footer'), tip=foot && foot.querySelector(':scope > .chip-tip');\n"
    "    if(tip && tip._chip===chip) tipHide(tip);\n"
    "  }, true);\n"
    "  window._altoChipNoTip=function(chip,label){\n"
    "    var norm=function(s){ return String(s||'').replace(/\\s+/g,' ').trim().toLowerCase(); };\n"
    "    if(!norm(chip.textContent) || norm(chip.textContent).indexOf(norm(label))<0) return false;\n"
    "    return chip.scrollWidth<=chip.clientWidth+1;   // name fully visible\n"
    "  };\n"
    "  document.addEventListener('mouseover', function(e){")
_NOTIP_M_OLD = "      if(!title) return;\n      // Stash and remove `title`"
_NOTIP_M_NEW = ("      if(!title) return;\n"
                "      if(window._altoChipNoTip && window._altoChipNoTip(target,title)) return;\n"
                "      // Stash and remove `title`")
PATCHES += [
    {"name": "chip-tip-skips-named-chips-css", "old": _NOTIP_CSS_OLD, "new": _NOTIP_CSS_NEW, "count": 1},
    {"name": "chip-tip-skips-named-chips-fn", "old": _NOTIP_FN_OLD, "new": _NOTIP_FN_NEW, "count": 1},
    {"name": "chip-tip-skips-named-chips-js", "old": _NOTIP_JS_OLD, "new": _NOTIP_JS_NEW, "count": 1},
    {"name": "chip-tip-skips-named-chips-mobile", "old": _NOTIP_M_OLD, "new": _NOTIP_M_NEW, "count": 1},
]


# ── a connector's corners fit the runs they turn on ─────────────────────────
# Every corner was drawn with a fixed 20px radius. On a jog under 40px (a card
# only a little off its parent's x, e.g. a band shifted to stay inside the page
# margin) the first arc already lands on the target's x and the next segment
# walks back to start the second arc — M 650 y L 650 b Q 650 b+20 670 b+20
# L 650 .. — a visible kink where the line looks broken. Shrink the radius to
# fit (half the sideways run, and the room above and below the bus), in the
# router's own elbow and in orthPath, which draws its alternative routes.
_CORNER_MAIN_OLD = """        var r = 20;
        var hDir = tx > sx ? 1 : -1;
"""
_CORNER_MAIN_NEW = """        // The corner radius fits the run it turns on: two 20px arcs on a jog under
        // 40px overshoot the target's x and walk back (a visible kink), and an
        // end closer than 20px to the bus cannot hold its arc either.
        var r = Math.min(20, Math.abs(tx - sx) / 2,
                         Math.abs(sy - midY) < 1 ? 20 : Math.abs(sy - midY),
                         Math.abs(ty - midY) < 1 ? 20 : Math.abs(ty - midY));
        var hDir = tx > sx ? 1 : -1;
"""
_CORNER_ORTH_OLD = """      function orthPath(pts, r){
        var _vG = (typeof vSegWithGaps === 'function') ? vSegWithGaps
                  : function(x, y1, y2){ return ' L ' + x + ' ' + y2; };
        var d = 'M ' + pts[0].x + ' ' + pts[0].y;
        for(var i=1;i<pts.length;i++){
          var a = pts[i-1], b = pts[i];
          var hasNext = i < pts.length - 1;
          if(a.x === b.x){                                    // vertical segment
            var dirY = b.y > a.y ? 1 : -1;
            var yEnd = hasNext ? b.y - dirY*r : b.y;
            d += _vG(a.x, a.y, yEnd);
            if(hasNext){
              var outX = pts[i+1].x > b.x ? 1 : -1;
              d += ' Q ' + b.x + ' ' + b.y + ' ' + (b.x + outX*r) + ' ' + b.y;
            }
          } else {                                            // horizontal segment
            var dirX = b.x > a.x ? 1 : -1;
            var xEnd = hasNext ? b.x - dirX*r : b.x;
            d += ' L ' + xEnd + ' ' + b.y;
            if(hasNext){
              var outY = pts[i+1].y > b.y ? 1 : -1;
              d += ' Q ' + b.x + ' ' + b.y + ' ' + b.x + ' ' + (b.y + outY*r);
            }
          }
        }
        return d;
      }
"""
_CORNER_ORTH_NEW = """      function orthPath(pts, r){
        var _vG = (typeof vSegWithGaps === 'function') ? vSegWithGaps
                  : function(x, y1, y2){ return ' L ' + x + ' ' + y2; };
        // Each corner's radius fits the runs it joins (half of a run it shares
        // with the next corner), so a short segment cannot make the path overshoot
        // and double back.
        var _len = function(i){ return Math.abs(pts[i].x - pts[i-1].x) + Math.abs(pts[i].y - pts[i-1].y); };
        var _rc = function(i){
          return Math.min(r, i === 1 ? _len(i) : _len(i) / 2,
                          i === pts.length - 2 ? _len(i + 1) : _len(i + 1) / 2);
        };
        var d = 'M ' + pts[0].x + ' ' + pts[0].y;
        for(var i=1;i<pts.length;i++){
          var a = pts[i-1], b = pts[i];
          var hasNext = i < pts.length - 1;
          if(a.x === b.x){                                    // vertical segment
            var dirY = b.y > a.y ? 1 : -1;
            var yEnd = hasNext ? b.y - dirY*_rc(i) : b.y;
            d += _vG(a.x, a.y, yEnd);
            if(hasNext){
              var outX = pts[i+1].x > b.x ? 1 : -1;
              d += ' Q ' + b.x + ' ' + b.y + ' ' + (b.x + outX*_rc(i)) + ' ' + b.y;
            }
          } else {                                            // horizontal segment
            var dirX = b.x > a.x ? 1 : -1;
            var xEnd = hasNext ? b.x - dirX*_rc(i) : b.x;
            d += ' L ' + xEnd + ' ' + b.y;
            if(hasNext){
              var outY = pts[i+1].y > b.y ? 1 : -1;
              d += ' Q ' + b.x + ' ' + b.y + ' ' + b.x + ' ' + (b.y + outY*_rc(i));
            }
          }
        }
        return d;
      }
"""
PATCHES += [
    {"name": "router-corner-fits-the-jog", "old": _CORNER_MAIN_OLD,
     "new": _CORNER_MAIN_NEW, "count": 1},
    {"name": "router-orthpath-corner-fits-the-segment", "old": _CORNER_ORTH_OLD,
     "new": _CORNER_ORTH_NEW, "count": 1},
]


# ── print: the outline with every detail page, and the picture, ink-saver ───
# `_stagePrint` knows 'timeline' (the outline), 'current' and 'all'. 'full' puts
# the outline in front of the detail pages (one run, a sheet break between), and
# 'ink' hands over to the picture builder in print_views.py. The same two modes
# are asked for by the share dialog's PRINT list (below) and by the homepage's
# Print... dialog, through #altoprint=<mode> (print_views.py), so there is one
# printing code path. The detail pages are built BEFORE any print class is set:
# showDetail needs the live page.
_PV_STAGE_OLD = ("function _stagePrint(mode){\n"
                 "  var root = document.documentElement;\n"
                 "  root.classList.remove('printing','print-timeline','print-current','print-all');\n")
_PV_STAGE_NEW = (
    "function _stagePrint(mode){\n"
    "  var root = document.documentElement;\n"
    "  root.classList.remove('printing','print-timeline','print-current','print-all','print-full','print-ink');\n"
    "  if(window._altoInkUnstage) window._altoInkUnstage();\n"
    "  if(mode === 'ink'){\n"
    "    if(window._altoInkStage && window._altoInkStage()){ root.classList.add('print-ink','printing'); return; }\n"
    "    mode = 'timeline';   // no canvas to draw: the outline is the fallback\n"
    "  }\n"
    "  if(mode === 'full'){\n"
    "    var pa = document.getElementById('print-all');\n"
    "    if(!pa){ pa = document.createElement('div'); pa.id = 'print-all'; document.body.appendChild(pa); }\n"
    "    var pt = document.getElementById('print-timeline-host');\n"
    "    if(!pt){ pt = document.createElement('div'); pt.id = 'print-timeline-host'; document.body.appendChild(pt); }\n"
    "    pa.innerHTML = _buildAllDetailsHTML();\n"
    "    pt.innerHTML = _buildPrintTimelineHTML();\n"
    "    document.body.appendChild(pt); document.body.appendChild(pa);   // the outline first\n"
    "    root.classList.add('print-timeline','print-all','print-full','printing');\n"
    "    return;\n"
    "  }\n")
_PV_UNSTAGE_OLD = ("function _unstagePrint(){\n"
                   "  document.documentElement.classList.remove('printing','print-timeline','print-current','print-all');\n")
_PV_UNSTAGE_NEW = ("function _unstagePrint(){\n"
                   "  document.documentElement.classList.remove('printing','print-timeline','print-current','print-all','print-full','print-ink');\n"
                   "  if(window._altoInkUnstage) window._altoInkUnstage();\n")
_PV_BTN_OLD = "      '<button class=\"print-opt\" data-print=\"all\">All detail pages</button>' +\n"
_PV_BTN_NEW = (_PV_BTN_OLD +
               "      '<button class=\"print-opt\" data-print=\"ink\">Timeline picture, ink-saver</button>' +\n")

PATCHES += [
    {"name": "print-views-stage", "old": _PV_STAGE_OLD, "new": _PV_STAGE_NEW, "count": 1},
    {"name": "print-views-unstage", "old": _PV_UNSTAGE_OLD, "new": _PV_UNSTAGE_NEW, "count": 1},
    {"name": "print-views-dialog-button", "old": _PV_BTN_OLD, "new": _PV_BTN_NEW, "count": 1},
]


# ── Freewrite (alto/build/freewrite.py): the notes panel's writing mode stays put ──
# Freewrite is a rich-text box in the Notes panel. While it is the open mode the
# panel must outlast everything that used to close it, and no page shortcut may
# fire under the writer's fingers. toggleNotes itself is guarded by freewrite.py
# (a close that is not the panel's own x is swallowed); these patches cover the
# keys and the gestures that act before toggleNotes is ever called.
_FW_ARROWS_OLD = ("    if(tag === 'INPUT' || tag === 'TEXTAREA') return;\n"
                  "    if(e.key === 'ArrowLeft' || e.keyCode === 37){")
_FW_ARROWS_NEW = ("    if(tag === 'INPUT' || tag === 'TEXTAREA' || (document.activeElement && document.activeElement.isContentEditable)) return;\n"
                  "    if(e.key === 'ArrowLeft' || e.keyCode === 37){")
_FW_FOCUSKEYS_OLD = ("  window.addEventListener('keydown', function(e){\n"
                     "    if((e.metaKey||e.ctrlKey)&&(e.key==='-'||e.key==='='")
_FW_FOCUSKEYS_NEW = ("  window.addEventListener('keydown', function(e){\n"
                     "    if(document.activeElement && document.activeElement.isContentEditable) return;   // typing: no page shortcut\n"
                     "    if((e.metaKey||e.ctrlKey)&&(e.key==='-'||e.key==='='")
_FW_ESC_OLD = ("    if(e.key!=='Escape' && e.keyCode!==27) return;\n"
               "    // 1) close the most-recently-opened pop-up, if any.")
_FW_ESC_NEW = ("    if(e.key!=='Escape' && e.keyCode!==27) return;\n"
               "    var _fwa=document.activeElement;     // Escape in the Freewrite box only leaves the box\n"
               "    if(_fwa && _fwa.id==='fw-editor'){ _fwa.blur(); e.preventDefault(); e.stopImmediatePropagation(); return; }\n"
               "    // 1) close the most-recently-opened pop-up, if any.")
_FW_ISOPEN_OLD = "    if(key==='notes')    return typeof notesOpen!=='undefined'   && !!notesOpen;"
_FW_ISOPEN_NEW = ("    if(key==='notes')    return typeof notesOpen!=='undefined'   && !!notesOpen"
                  " && !(window._altoFw && window._altoFw.pinned());   // Freewrite is not an Escape-able pop-up")
_FW_WHEEL_OLD = ("      if(typeof notesOpen!=='undefined' && notesOpen){\n"
                 "        if(_notesDismiss(e))")
_FW_WHEEL_NEW = ("      if(typeof notesOpen!=='undefined' && notesOpen && !(window._altoFw && window._altoFw.pinned())){\n"
                 "        if(_notesDismiss(e))")
_FW_SWIPE_OLD = "isOpen:function(){return _np.classList.contains('open');},"
_FW_SWIPE_NEW = "isOpen:function(){return _np.classList.contains('open') && !(window._altoFw && window._altoFw.pinned());},"
PATCHES += [
    {"name": "freewrite-arrows-not-while-typing", "old": _FW_ARROWS_OLD, "new": _FW_ARROWS_NEW, "count": 1},
    {"name": "freewrite-focus-keys-not-while-typing", "old": _FW_FOCUSKEYS_OLD, "new": _FW_FOCUSKEYS_NEW, "count": 1},
    {"name": "freewrite-escape-leaves-the-box", "old": _FW_ESC_OLD, "new": _FW_ESC_NEW, "count": 1},
    {"name": "freewrite-escape-spares-the-panel", "old": _FW_ISOPEN_OLD, "new": _FW_ISOPEN_NEW, "count": 1},
    {"name": "freewrite-wheel-swipe-spares-the-panel", "old": _FW_WHEEL_OLD, "new": _FW_WHEEL_NEW, "count": 1},
    {"name": "freewrite-phone-swipe-spares-the-panel", "old": _FW_SWIPE_OLD, "new": _FW_SWIPE_NEW, "count": 1},
]


# ── a report can carry the Freewrite (alto/build/freewrite.py) ─────────────────
# generateNotesReport asks window._altoFwReport() for the writer's Freewrite: it
# answers only when the reader ticked "Attach my Freewrite" in the Notes panel (or
# pressed Report in the Freewrite pane itself) and something is written, and what
# it returns is already rebuilt from the whitelist (b i u s h1 h2 p div br ul ol
# li, no attributes). A report may now hold the Freewrite alone.
_FWR_GUARD_OLD = ("  if(highlights.length === 0){\n"
                  "    alert('Nothing to export yet. Add a note or highlight first.');\n"
                  "    return;\n"
                  "  }\n")
_FWR_GUARD_NEW = ("  var _fw = null; try{ _fw = window._altoFwReport ? window._altoFwReport() : null; }catch(_e){}   // the Freewrite, when attached\n"
                  "  if(highlights.length === 0 && !_fw){\n"
                  "    alert('Nothing to export yet. Add a note or highlight first' + (window._altoFwReport ? ', or write something in Freewrite.' : '.'));\n"
                  "    return;\n"
                  "  }\n")
_FWR_CSS_OLD = "  .footer{font-size:10px;color:#bbb;margin-top:60px;"
_FWR_CSS_NEW = ("  .fw-body{font-size:15px;line-height:1.7;}\n"
                "  .fw-body p,.fw-body div{margin:0 0 6px;}\n"
                "  .fw-body h1{font-size:18px;margin:22px 0 6px;} .fw-body h2{font-size:16px;margin:18px 0 5px;}\n"
                "  .fw-body ul,.fw-body ol{margin:4px 0 10px;padding-left:26px;} .fw-body li{margin:2px 0;}\n"
                "  .fw-body ul{list-style:disc;} .fw-body ul ul{list-style:circle;} .fw-body ul ul ul{list-style:square;}\n"
                "  .fw-body ol{list-style:decimal;} .fw-body ol ol{list-style:lower-alpha;} .fw-body ol ol ol{list-style:lower-roman;}\n"
                "  @media print{.fw-body h1,.fw-body h2{break-after:avoid;} .fw-body li{break-inside:avoid;}}\n"
                + _FWR_CSS_OLD)
_FWR_TEXT_OLD = ("      'HIGHLIGHTS & NOTES:',\n"
                 "      highlights.map(function(h){ return '\"' + h.quote + '\"' + (h.note ? ', ' + h.note : ''); }).join('\\n\\n')\n"
                 "    ];\n")
_FWR_TEXT_NEW = ("      (highlights.length ? 'HIGHLIGHTS & NOTES:' : ''),\n"
                 "      highlights.map(function(h){ return '\"' + h.quote + '\"' + (h.note ? ', ' + h.note : ''); }).join('\\n\\n')\n"
                 "    ].concat(_fw ? ['', 'FREEWRITE:', _fw.text] : []);\n")
_FWR_BODY_OLD = ("<div class=\"section-header\">Your Highlights &amp; Notes</div>\n"
                 "${hlHtml}\n")
_FWR_BODY_NEW = ("${highlights.length ? '<div class=\"section-header\">Your Highlights &amp; Notes</div>\\n' : ''}${hlHtml}\n"
                 "${_fw ? '<div class=\"section-header\">Your Freewrite' + (_fw.words ? ' &middot; ' + _fw.words + (_fw.words === 1 ? ' word' : ' words') : '') + '</div><div class=\"fw-body\">' + _fw.html + '</div>\\n' : ''}")
PATCHES += [
    {"name": "freewrite-report-guard", "old": _FWR_GUARD_OLD, "new": _FWR_GUARD_NEW, "count": 1},
    {"name": "freewrite-report-css", "old": _FWR_CSS_OLD, "new": _FWR_CSS_NEW, "count": 1},
    {"name": "freewrite-report-mail-text", "old": _FWR_TEXT_OLD, "new": _FWR_TEXT_NEW, "count": 1},
    {"name": "freewrite-report-section", "old": _FWR_BODY_OLD, "new": _FWR_BODY_NEW, "count": 1},
]
