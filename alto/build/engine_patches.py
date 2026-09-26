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
# ── compass hop ignores relation-filtered nodes ──────────────────────────────
# focusNeighbor (the 8-way arrow/swipe hop between focused cards) deliberately
# skips nodes an era/weight filter has dimmed, so hopping only visits nodes that
# meet the active filter. Relation filters dim with their own `rel-dimmed` class
# — a separate class on purpose, so the engine's slot filters and the relation
# filters never write to the same one — which left the hop walking into cards
# the user had just filtered out. Teach the guard about both.
_HOP_DIM_OLD = ("      var _c=n.querySelector('.node-card'); "
                "if(_c&&_c.classList.contains('dimmed')) return;")
_HOP_DIM_NEW = ("      var _c=n.querySelector('.node-card'); "
                "if(_c&&(_c.classList.contains('dimmed')||"
                "_c.classList.contains('rel-dimmed')||"
                "_c.classList.contains('ent-dimmed'))) return;")

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
  transform:scale(1) !important; transform-origin:center !important;
  opacity:1 !important; box-shadow:0 38px 84px var(--node-hover-shadow) !important;
  /* The magnification is CSS zoom, applied inline per frame by enterFocus. A
     zoomed element can lose its backdrop-filter, so — as the .crisp rule this
     replaces already did — legibility must not depend on the frost. Raise the
     FALLBACK, not the value: --node-glass-bg is Blink-only and already opaque
     enough there (0.90, set so the card occludes the connector lines Chrome's
     dead backdrop-filter can't hide). Only Safari, where it is undefined and
     the card falls back to --card-glass-bg at 0.54, needs the floor lifted. */
  background:var(--node-glass-bg, var(--panel-glass-bg));
}
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
  function _cardOf(el){ return (el && el.querySelector) ? el.querySelector('.node-card') : null; }
  function _setZoom(card,k){ if(card) card.style.zoom = (k>1.0005) ? String(k) : ''; }
  function _zoomRamp(el,to,dur){
    var card=_cardOf(el); if(!card) return;
    if(_zw){
      cancelAnimationFrame(_zw); _zw=null;
      // never strand a half-ramped card when focus moves before the ramp lands
      if(_zwCard && _zwCard!==card) _setZoom(_zwCard,_zwTo);
    }
    _zwCard=card; _zwTo=to;
    var from=parseFloat(card.style.zoom)||1, s=null;
    if(Math.abs(to-from)<0.002){ _setZoom(card,to); return; }
    function step(ts){
      if(s===null) s=ts;
      var p=Math.min(1,(ts-s)/dur), e=1-(1-p)*(1-p);  // ease-out, as the card's own transition was
      _setZoom(card, from+(to-from)*e);
      if(p<1) _zw=requestAnimationFrame(step); else { _zw=null; _setZoom(card,to); }
    }
    _zw=requestAnimationFrame(step);
  }

  function enterFocus(id){
    if(!id) return; var el=nodeEl(id); if(!el) return;
    if(window._focusedNodeId && window._focusedNodeId!==id){ var p=nodeEl(window._focusedNodeId); if(p){ p.classList.remove('crisp'); p.classList.remove('focused'); p.style.transform=''; p._fx=p._fy=0; _setZoom(_cardOf(p),1); } }
    window._focusedNodeId=id;
    canvas.classList.add('focus-mode');
    el.classList.add('focused');
    _zoomRamp(el,FOCUS_K,240);
    flyTo(el);
  }"""

_FOCUS_EXIT_OLD = """      el.classList.remove('focused');
      flyBack(el);"""
_FOCUS_EXIT_NEW = """      el.classList.remove('focused');
      _zoomRamp(el,1,220);
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


PATCHES = [
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
        "name": "compass-hop-skips-relation-filtered",
        "old": _HOP_DIM_OLD,
        "new": _HOP_DIM_NEW,
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
             "html:not(.mobile) #search-btn{ z-index:310 !important; }")
PATCHES += [
    {"name": "desktop-controls-above-nodes", "old": _CTRL_OLD, "new": _CTRL_NEW, "count": 1},
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
             "#filter-toggle")
_RW_HEAD_OLD = '<meta name="theme-color" id="meta-theme" content="#ffc59e">'
_RW_HEAD_NEW = _RW_HEAD_OLD + """
<style id="alto-runway">
html.mobile.rw{ overflow-y:scroll !important; overflow-x:hidden !important; height:auto !important;
  overscroll-behavior:none; touch-action:none; }
html.mobile.rw body:not(#_){ position:relative !important; height:100dvh !important; min-height:0 !important;
  margin:80px 0 140px !important; overflow:visible !important; overscroll-behavior:none; touch-action:none; }
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
  #ef-panel, #account-scrim):not(#_){ top:-80px !important; bottom:-140px !important; height:auto !important;
  padding-bottom:140px !important; }
html.mobile.rw #ef-panel:not(#_){ padding-bottom:0 !important; }
html.mobile.rw :is(#minimap-header, #tutorial-header):not(#_){ position:relative !important; }
html.mobile.rw #msp:not(#_){ padding-top:80px !important; }
html.mobile.rw :is(#notes-header, #minimap-header, #tutorial-header, #ef-panel > .ef-head):not(#_){
  padding-top:96px !important; height:auto !important; }
html.mobile.rw #nav-drawer-header:not(#_){ padding-top:98px !important; height:auto !important; }
html.mobile.rw #detail-page:not(#_){ bottom:-140px !important; padding-bottom:240px !important; }
</style>"""

_RW_ANCHOR = '<script id="layout-settle">'
_RW_NEW = """<script id="alto-runway-js">
(function(){
  var r = document.documentElement, OFF = 80;
  if(!r.classList.contains('rw')) return;
  // Any other fixed piece at the level of <body> / #app (one added by a later
  // script, say) goes absolute too. Fixed pieces inside a positioned parent
  // are left alone: absolute would move them.
  function loose(e){
    for(var p = e.parentElement; p && p !== document.body; p = p.parentElement){
      if(p.id === 'app') continue;
      var c = getComputedStyle(p);
      if(c.position !== 'static' || c.transform !== 'none' || c.filter !== 'none') return false;
    }
    return true;
  }
  function sweep(root){
    var all = [root].concat([].slice.call(root.querySelectorAll('*')));
    for(var i = 0; i < all.length; i++){
      var e = all[i];
      if(e.nodeType !== 1 || e.classList.contains('rw-abs')) continue;
      var pos = getComputedStyle(e).position;
      if((pos === 'fixed' || pos === 'sticky') && e.parentElement && loose(e)) e.classList.add('rw-abs');
    }
  }
  sweep(document.body);
  new MutationObserver(function(ms){
    ms.forEach(function(m){ [].forEach.call(m.addedNodes, function(n){ if(n.nodeType === 1) sweep(n); }); });
  }).observe(document.body, {childList: true, subtree: true});
  // Rest 80px down the runway, and stay there: no touch scrolling, and a
  // snap-back if anything (a focused field, a hash jump) moves the page.
  var busy = false;
  function typing(){ var a = document.activeElement; return !!a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName); }
  function pin(){
    if(busy || typing() || Math.abs((window.pageYOffset || 0) - OFF) <= 1) return;
    busy = true;
    requestAnimationFrame(function(){ busy = false; window.scrollTo(0, OFF); });
  }
  function settle(){ window.scrollTo(0, OFF); setTimeout(pin, 100); setTimeout(pin, 400); setTimeout(pin, 1000); }
  window.addEventListener('scroll', pin, {passive: true});
  window.addEventListener('load', settle);
  window.addEventListener('pageshow', settle);
  window.addEventListener('orientationchange', settle);
  window.addEventListener('resize', pin);
  document.addEventListener('focusout', function(){ setTimeout(pin, 50); });
  settle();
})();
</script>
""" + _RW_ANCHOR
PATCHES += [
    {"name": "mobile-runway-class-in-head", "old": _RW_CLASS_OLD, "new": _RW_CLASS_NEW, "count": 1},
    {"name": "mobile-runway-behind-bars", "old": _RW_HEAD_OLD, "new": _RW_HEAD_NEW, "count": 1},
    {"name": "mobile-runway-pin", "old": _RW_ANCHOR, "new": _RW_NEW, "count": 1},
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

