"""The one behaviour for the little things pinned on a map (1.9.145): node chips, room pills, names, tags.

Luke (2026-10-22), on the Memory Blueprint blueprint: "When you're zooming in ... all the little buttons for nodes are shifting so
much and changing size that it looks like it's really glitchy." The blueprint laid its chips out again on EVERY wheel event
(a greedy collision pass whose winners changed from one frame to the next, so chips hopped sideways), switched them from a
number to a number-and-title at a hard zoom threshold (their width jumped), and rounded their counter-scale to 0.001 (their
size wobbled). The System chart's labels had the same flaw (four places re-chosen every frame, level-of-detail by display).

Every map-like format follows these rules, and the helpers below are what they share:
  1. A marker is pinned to its anchor and keeps one size on the screen. While a zoom or pan runs, the only thing that changes
     per frame is its transform (translate3d to the anchor's place on screen + the offset it was given); nothing is measured,
     re-laid out or re-chosen.
  2. Layout (which place beside its anchor a marker takes when it would cover another, and level of detail such as a title
     after the number) is decided ONCE, when the gesture settles (`settle`), and the change glides (`glide`: eased frame by frame in JS, never a CSS transition).
  3. Decisions are held: a marker keeps the place it had while it is still free (`place` tests it with a slack, and a nearer
     place must be clearly free to win it back); a zoom threshold is a band (`band`), so nothing flips at its edge.
  4. Level of detail fades (`.alto-mk-off`: opacity, then visibility), never pops by display.
The Memory Atlas adopts the same module (see docs/markers.md).
"""
from __future__ import annotations

MARKERS_CSS = r"""
.alto-mk.alto-mk-off{opacity:0;visibility:hidden;pointer-events:none;transition:opacity .22s ease,visibility 0s linear .22s;}
"""

MARKERS_JS = r"""
(function(){ if(window.AltoMarkers) return;
var M=window.AltoMarkers={}, REG={};
/* a threshold held as a band: on above hi, off below lo, between them it stays as it was */
M.band=function(was, v, lo, hi){ return was ? v>lo : v>hi; };
/* a gesture (wheel, pinch, drag, glide): poke() on every input; done() runs once, ms after the last, confirmed a frame later (input
   queued behind a long frame is handled before that frame, and pokes again). A test may hold it with window._altoMkHold. */
M.settle=function(done, ms){ ms=ms||170; var t=0, n=0, s={busy:false};
  function fire(){ var k=n; if(window._altoMkHold){ t=setTimeout(fire, ms); return; }
    requestAnimationFrame(function(){ if(k===n && s.busy){ s.busy=false; done(); } }); }
  s.poke=function(){ n++; s.busy=true; clearTimeout(t); t=setTimeout(fire, ms); };
  s.now=function(){ clearTimeout(t); s.busy=false; done(); };
  return s; };
/* where each marker sits beside its anchor, decided once a gesture settles. items: [{id, x, y, w, h, c:[[dx,dy],..]}] in screen px,
   most important first; c: the places it may take, nearest home first. st: the layer's memory (the place each one had).
   A nearer place wins only when clearly free (slack px to spare), the place it had is kept while free within the slack, else
   the first free one; with none free it stays where it was (o.hide: it is hidden). o.ok(x,y,w,h): may it stand there at all.
   Returns {id: {dx, dy, on}}. */
M.place=function(items, st, o){ o=o||{}; var sl=o.slack==null ? 3 : o.slack, gap=o.gap||0, box=[], out={};
  function free(x, y, w, h, s){ if(o.ok && !o.ok(x, y, w, h)) return false;
    for(var i=0;i<box.length;i++){ var b=box[i]; if(Math.abs(x-b[0])<(w+b[2])/2+gap-s && Math.abs(y-b[1])<(h+b[3])/2+gap-s) return false; } return true; }
  items.forEach(function(m){ var p=st[m.id]||(st[m.id]={i:0}), c=m.c||[[0, 0]], k=Math.min(p.i, c.length-1), pick=-1, i;
    for(i=0;i<k && pick<0;i++) if(free(m.x+c[i][0], m.y+c[i][1], m.w, m.h, -sl)) pick=i;
    if(pick<0 && free(m.x+c[k][0], m.y+c[k][1], m.w, m.h, sl)) pick=k;
    for(i=0;i<c.length && pick<0;i++) if(free(m.x+c[i][0], m.y+c[i][1], m.w, m.h, 0)) pick=i;
    var on=pick>=0 || !o.hide; if(pick<0) pick=k; p.i=pick;
    if(on) box.push([m.x+c[pick][0], m.y+c[pick][1], m.w, m.h]);
    out[m.id]={dx:c[pick][0], dy:c[pick][1], on:on}; });
  return out; };
/* a layer's re-layout glides, driven here frame by frame: step(k) with k eased 0..1, the caller placing each marker between where it
   was and where it goes. Not a CSS transition: WebKit lets a running transform transition go on after its class is removed, so at the
   next zoom the chips flew on beside their anchors and then snapped (up to 380 px, measured). stop() at the next input freezes the
   markers where they are; the following settle glides on from there. */
M.glide=function(layer, step, ms){ if(!layer) return; M.stop(layer); ms=window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches ? 1 : (ms||320);
  var t0=performance.now();
  (function f(t){ var u=Math.min(1, Math.max(0, (t-t0)/ms)); step(1-Math.pow(1-u, 3)); if(u<1) layer._mkG=requestAnimationFrame(f); else layer._mkG=0; })(t0); };
M.stop=function(layer){ if(layer && layer._mkG){ cancelAnimationFrame(layer._mkG); layer._mkG=0; } };
/* a marker's place on screen: transform only (the compositor moves it) */
M.at=function(e, x, y){ e.style.transform='translate3d('+x.toFixed(2)+'px,'+y.toFixed(2)+'px,0)'; };
M.show=function(e, on){ e.classList.toggle('alto-mk-off', !on); };
/* tests: each format registers what its markers are, [{id, x, y, w, h, ax, ay, op}] in client px (ax/ay: the anchor) */
M.reg=function(k, f){ REG[k]=f; };
M.debug=function(k){ return REG[k] ? REG[k]() : null; };
})();
"""
