"""Two-finger scrolling moves the map the way the fingers go — diagonally too (Mind Palace city map, Hub & spoke / Star chart).

Luke, 1.9.110: "diagonal scrolling ... the view only moves along one axis at a time". Both views pan at rest by the browser's
own scroll of #canvas (one overflow:auto box, nothing clipped on either axis), and a synthetic diagonal wheel moves it on both
axes in Chromium and in Playwright's WebKit. What does not show there is Safari on a Mac trackpad: WebKit filters the deltas
it SCROLLS with through AppKit's predominant-axis filter (WheelEventDeltaFilterMac, _NSScrollingPredominantAxisFilter, in the
scrolling thread and on the main thread alike), so a native scroller follows one axis of a two-finger gesture; the wheel
EVENTS the page receives carry both deltas, unfiltered. So the page scrolls the map itself: one non-passive wheel listener on
#canvas (not window — over panels, notes, the filter, a detail page nothing changes and Safari still scrolls them on its own
thread) takes each plain wheel (no ctrl: that is a pinch, owned by the zoom code), prevents the browser's scroll and adds
BOTH deltas to the view on the next frame:

* deltas in screen px (lines x16, pages x the canvas), divided by the page's CSS zoom — exactly what the browser's own scroll
  moves for them, so the speed is unchanged; Shift with a vertical-only wheel (a mouse) goes sideways;
* the fractions are carried (the engine's whole-px _altoScrollAxis under Safari's zoom), so a slow drift does not stall;
* macOS momentum arrives as more, decaying wheel events: they are summed like the rest (no inertia of our own);
* a gesture that starts over something inside the canvas that can scroll that way (an enlarged card's text) is left to it
  for the whole gesture, as the browser latches (and one the browser already scrolls, its events no longer cancelable, is
  never applied twice); anything that already took the event (preventDefault: focus mode's
  navigation, the elevator; or stopped it: the whole-chart pan, a flight's stop) is left alone;
* it pans only while the host says so (on()): desktop, no card enlarged, no detail page; a phone's touch is not a wheel.

window._altoPan2d({on, pan}) installs it: on() -> pan now?; pan(dx, dy) -> true if the host moved the view itself (the palace
during a zoom preview) — else the canvas is scrolled. Returns {n: wheels panned, flush()} for the tests. Other formats (timeline, outline) can adopt
it with the same one call.
"""

PAN2D_JS = r"""
window._altoPan2d=function(host){
  var cv=null, acc=[0,0], raf=0, fx=null, last=null, g={t:-1e9, inner:false, z:1, w:0, h:0}, api={n:0};
  function canvas(){ return cv||(cv=document.getElementById('canvas')); }
  /* an element between the target and the canvas that can still scroll the way this delta goes (a first event with no delta
     yet, as Safari's gesture begins: one that can scroll at all — the browser decides a gesture on its first event) */
  function innerScroll(t, dx, dy){
    var any=!dx && !dy; if(any){ dx=dy=1; }
    for(var n=t; n && n!==cv && n.nodeType===1; n=n.parentElement){
      if(any && /auto|scroll/.test(getComputedStyle(n).overflow) && (n.scrollHeight>n.clientHeight+1 || n.scrollWidth>n.clientWidth+1)) return true;
      var s=getComputedStyle(n), oy=/auto|scroll/.test(s.overflowY), ox=/auto|scroll/.test(s.overflowX);
      if(oy && dy && n.scrollHeight>n.clientHeight+1 && (dy<0 ? n.scrollTop>0 : n.scrollTop+n.clientHeight<n.scrollHeight-1)) return true;
      if(ox && dx && n.scrollWidth>n.clientWidth+1 && (dx<0 ? n.scrollLeft>0 : n.scrollLeft+n.clientWidth<n.scrollWidth-1)) return true; }
    return false; }
  function axis(p){ var a=window._altoScrollAxis; return a ? a(p) : {at:function(){ return cv[p]; }, go:function(v){ cv[p]=v; }}; }
  function frame(){
    raf=0; var dx=acc[0], dy=acc[1]; acc=[0,0]; var c=canvas(); if(!c || (!dx && !dy)) return;
    if(host.pan && host.pan(dx, dy)){ fx=null; return; }
    var ax=axis('scrollLeft'), ay=axis('scrollTop'), x=ax.at(), y=ay.at();
    /* carry the fractions while nothing else has moved the canvas since our last write */
    if(fx && last && Math.abs(x-last[0])<1.5 && Math.abs(y-last[1])<1.5){ x=fx[0]; y=fx[1]; }
    x=Math.max(0, Math.min(c.scrollWidth-c.clientWidth, x+dx)); y=Math.max(0, Math.min(c.scrollHeight-c.clientHeight, y+dy));
    ax.go(x); ay.go(y); fx=[x, y]; last=[ax.at(), ay.at()]; }
  function onWheel(e){
    if(e.ctrlKey || e.defaultPrevented || !e.cancelable || !host.on()) return;   /* uncancelable: the browser has this gesture already */
    var c=canvas(), m=e.deltaMode, dx=e.deltaX, dy=e.deltaY;
    if(e.shiftKey && !dx){ dx=dy; dy=0; }                     /* a mouse wheel with Shift: sideways */
    if(e.timeStamp-g.t>180){                                   /* a new gesture: what it is over is read once */
      var r=c.getBoundingClientRect();
      g={inner:innerScroll(e.target, dx, dy), z:(r.width && c.offsetWidth) ? r.width/c.offsetWidth : 1, w:c.clientWidth, h:c.clientHeight}; }
    g.t=e.timeStamp;
    if(g.inner) return;
    var kx=m===1 ? 16 : m===2 ? g.w : 1, ky=m===1 ? 16 : m===2 ? g.h : 1;
    e.preventDefault();
    api.n++; acc[0]+=dx*kx/g.z; acc[1]+=dy*ky/g.z;
    if(!raf) raf=requestAnimationFrame(frame); }
  function wire(){ var c=canvas(); if(c && !c._pan2d){ c._pan2d=1; c.addEventListener('wheel', onWheel, {passive:false}); } }
  if(document.getElementById('canvas')) wire(); else document.addEventListener('DOMContentLoaded', wire);
  api.flush=function(){ if(raf){ cancelAnimationFrame(raf); frame(); } };
  return api;
};
"""

# the Hub & spoke / Star chart hook: only through what solar_draw.py already publishes (its whole-chart view keeps its own
# both-axes pan, and stops the event before it reaches the canvas)
SOLAR_PAN2D_JS = r"""
window._altoSolarPan2d=window._altoPan2d({on:function(){ var de=document.documentElement;
  return de.classList.contains('alto-solar') && !de.classList.contains('mobile') && !de.classList.contains('detail-open') && !window._focusedNodeId
    && !(window._altoSolarZoom && window._altoSolarZoom()<.999); }});
"""


def _slim(src: str) -> str:
    """The page copy without comments and indentation (no string or regex here holds a slash-star)."""
    import re
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(l.strip() for l in src.splitlines() if l.strip()) + "\n"


PAN2D_JS = _slim(PAN2D_JS)
SOLAR_PAN2D_JS = _slim(SOLAR_PAN2D_JS)
