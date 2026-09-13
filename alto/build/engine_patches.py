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
                "_c.classList.contains('rel-dimmed'))) return;")

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
