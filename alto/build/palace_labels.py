"""Where a landmark's NAME hangs on the Memory Palace map (1.9.95).

The names of the landmark buildings (towers, courthouses, stations, City Hall, the stadiums, the Convention Center, every
generic building the palace draws) keep one size on the screen, while the buildings shrink with the zoom. The declutter in
palace.py (lblFit) used to give a name exactly TWO places, under its card and over it, and dropped it when either touched
another name, another landmark's card, or one of the numbered buildings on the board. So two neighbouring towers (One and
Two Liberty Place) both showed their names zoomed in, and one zoom step out the one whose spots a numbered building or a
neighbour had taken simply vanished: nothing slid aside to make room.

Now `lmSpots()` gives the name a whole ladder of places, nearest to its home first: under the card, over it, a second and
third row under it, the same shifted left and right by a third, two thirds and nine tenths of its width, then beside the
card on either side. lblFit takes the first one that is free (a name keeps the spot it had unless a nearer one opened:
no hopping while zooming). A name sent off its card gets a thin leader line (`.lm-lead`) back to it. Only when nothing
nearby is free in a first pass that respects every other name, card, chip and numbered building does a second pass let the
name lie over a NEIGHBOURING LANDMARK'S card (never over a name, a chip or a numbered building): a name is dropped only when
there is truly no room. A name that was showing at the last zoom also gets a thinner margin (hysteresis), so it does not
blink at the edge of a zoom step.

Everything here is in map units in the landmark's own (un-turned) frame, as the names are laid out; lblFit turns the spot
to the board for its collision test.
"""
from __future__ import annotations

LABELS_CSS = r"""
  /* a name moved off its card: a thin leader back to the card, the same weight on the screen at every zoom */
  .pal-svg .pl-lmn .lm-name,.pal-svg .pl-lmn .lm-lead{transition:opacity .22s ease;}
  @media (prefers-reduced-motion:reduce){ .pal-svg .pl-lmn .lm-name,.pal-svg .pl-lmn .lm-lead{transition:none;} }
  .pal-svg .pl-lmn .lm-lead{fill:none;stroke:var(--pal-text);stroke-width:calc(1.2px / var(--pz,1));stroke-opacity:.5;stroke-linecap:round;pointer-events:none;}
"""

LABELS_JS = r"""
/* ── landmark names: the places a name may hang (palace_labels.py) ──
   card {x,y,w,h}; nat: the baseline under the card [x,y]; alt: the baseline over it [x,y] or null; fs: the name's size on the
   screen (px); W: its width on the screen (px); z: screen px per map unit; prev: the id of the spot it had. Returns spots
   [{id, x, y, c}] nearest home first; c is the distance from home in screen px (a nearer spot is always tried first, but
   the one the name already had comes first of all so it does not hop). */
var LM_DX=[0, -.3, .3, -.6, .6, -.9, .9, -1.2, 1.2];
function lmSpots(card, nat, alt, fs, W, z, prev){
  var u=1/z, L=fs*1.2+9, out=[];   /* a row's step clears the name above it (its box is .6 fs + a 4px margin each side) */
  function add(id, x, y, c){ out.push({id:id, x:x, y:y, c:c}); }
  LM_DX.forEach(function(f, i){ var dp=f*W, ax=Math.abs(dp);
    for(var r=0;r<3;r++) add('b'+r+i, nat[0]+dp*u, nat[1]+r*L*u, ax*.6+r*L);                    /* under the card, then a second and a third row */
    if(alt) for(var s=0;s<2;s++) add('a'+s+i, alt[0]+dp*u, alt[1]-s*L*u, ax*.6+s*L+9); });          /* over it */
  var my=card.y+card.h/2+.35*fs*u, gap=(6+W/2)*u;
  add('sr', card.x+card.w+gap, my, W*.5+card.w*z*.5+14);                                         /* beside it */
  add('sl', card.x-gap, my, W*.5+card.w*z*.5+14);
  out.sort(function(a, b){ return a.c-b.c; });
  if(prev) for(var i=1;i<out.length;i++) if(out[i].id===prev){ out.unshift(out.splice(i, 1)[0]); break; }
  return out; }
/* the leader from a card to a name hanging at baseline spot (x,y): the closest points of the card and of the name's box;
   null when they nearly touch (the name is at home) */
function lmLead(card, x, y, fs, W, z){
  var u=1/z, hw=W/2*u, hh=.62*fs*u, cy=y-.3*fs*u;
  function cl(v, a, b){ return Math.max(a, Math.min(b, v)); }
  var px=cl(x, card.x, card.x+card.w), py=cl(cy, card.y, card.y+card.h), qx=cl(px, x-hw, x+hw), qy=cl(py, cy-hh, cy+hh);
  return Math.hypot(qx-px, qy-py)*z>7 ? [px, py, qx, qy] : null; }
/* a name (or its leader) comes and goes by a short fade, never a pop: display stays the switch for the layout (nbOcclude reads the
   wrapper's box) and follows the fade out */
function lmFade(e, on){ if(!!e._on2===on && e._on2!==undefined) return; e._on2=on; clearTimeout(e._ft);
  if(on){ if(e.style.display==='none'){ e.style.opacity='0'; e.style.display=''; (window.requestAnimationFrame||setTimeout)(function(){ if(e._on2) e.style.opacity=''; }); } else e.style.opacity=''; }
  else { e.style.opacity='0'; e._ft=setTimeout(function(){ if(!e._on2){ e.style.display='none'; } }, 240); } }
/* a point of the name's own frame on the board: the wrapper's translate (a tilted district's upright building) and turn */
function lmToBoard(q, tf){ var x=q[0], y=q[1], a=0;
  var tr=tf&&/translate\(([-\d.e]+)[ ,]+([-\d.e]+)\)/.exec(tf), mm=tf&&/rotate\(([-\d.e]+) ([-\d.e]+) ([-\d.e]+)\)/.exec(tf);
  if(mm){ a=mm[1]*Math.PI/180; var rx=+mm[2], ry=+mm[3], dx=x-rx, dy=y-ry; x=rx+dx*Math.cos(a)-dy*Math.sin(a); y=ry+dx*Math.sin(a)+dy*Math.cos(a); }
  if(tr){ x+=+tr[1]; y+=+tr[2]; }
  return [x, y, a]; }
"""
