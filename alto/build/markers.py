"""The one behaviour for the little things pinned on a map (1.9.145): node chips, room pills, names, tags.

Luke (2026-10-22), on the Museum Palace blueprint: "When you're zooming in ... all the little buttons for nodes are shifting so
much and changing size that it looks like it's really glitchy." The blueprint laid its chips out again on EVERY wheel event
(a greedy collision pass whose winners changed from one frame to the next, so chips hopped sideways), switched them from a
number to a number-and-title at a hard zoom threshold (their width jumped), and rounded their counter-scale to 0.001 (their
size wobbled). The System chart's labels had the same flaw (four places re-chosen every frame, level-of-detail by display).

Every map-like format follows these rules, and the helpers below are what they share:
  1. A marker is pinned to its anchor and keeps one size on the screen. While a zoom or pan runs, the only thing that changes
     per frame is its transform (translate3d to the anchor's place on screen + the offset it was given); nothing is measured,
     re-laid out or re-chosen.
  2. Layout (which place beside its anchor a marker takes when it would cover another, and level of detail such as a title
     after the number) is decided ONCE, when the gesture settles (`settle`), and the change glides (`.alto-mk-glide`).
  3. Decisions are held: a marker keeps the place it had while it is still free (`place` tests it with a slack, and a nearer
     place must be clearly free to win it back); a zoom threshold is a band (`band`), so nothing flips at its edge.
  4. Level of detail fades (`.alto-mk-off`: opacity, then visibility), never pops by display.
The World Palace adopts the same module (see docs/markers.md).
"""
from __future__ import annotations

MARKERS_CSS = r"""
.alto-mk-glide .alto-mk{transition:transform .32s cubic-bezier(.2,.7,.2,1),width .32s cubic-bezier(.2,.7,.2,1),opacity .22s ease;}
.alto-mk.alto-mk-off{opacity:0;visibility:hidden;pointer-events:none;transition:opacity .22s ease,visibility 0s linear .22s;}
@media (prefers-reduced-motion:reduce){.alto-mk-glide .alto-mk{transition:none;}}
"""

MARKERS_JS = r"""
(function(){ if(window.AltoMarkers) return;
var M=window.AltoMarkers={}, REG={};
/* a threshold held as a band: on above hi, off below lo, between them it stays as it was */
M.band=function(was, v, lo, hi){ return was ? v>lo : v>hi; };
/* a gesture (wheel, pinch, drag, glide): poke() on every input; done() runs once, ms after the last (a test may hold it with window._altoMkHold) */
M.settle=function(done, ms){ ms=ms||170; var t=0, s={busy:false};
  function fire(){ if(window._altoMkHold){ t=setTimeout(fire, ms); return; } s.busy=false; done(); }
  s.poke=function(){ s.busy=true; clearTimeout(t); t=setTimeout(fire, ms); };
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
/* a layer's re-layout glides: the class for one transition's length, then off (so following the anchor stays instant) */
M.glide=function(layer, ms){ if(!layer) return; clearTimeout(layer._mkG); layer.classList.add('alto-mk-glide');
  layer._mkG=setTimeout(function(){ layer.classList.remove('alto-mk-glide'); }, ms||360); };
M.stop=function(layer){ if(layer){ clearTimeout(layer._mkG); layer.classList.remove('alto-mk-glide'); } };
/* a marker's place on screen: transform only (the compositor moves it) */
M.at=function(e, x, y){ e.style.transform='translate3d('+x.toFixed(2)+'px,'+y.toFixed(2)+'px,0)'; };
M.show=function(e, on){ e.classList.toggle('alto-mk-off', !on); };
/* tests: each format registers what its markers are, [{id, x, y, w, h, ax, ay, op}] in client px (ax/ay: the anchor) */
M.reg=function(k, f){ REG[k]=f; };
M.debug=function(k){ return REG[k] ? REG[k]() : null; };
})();
"""
