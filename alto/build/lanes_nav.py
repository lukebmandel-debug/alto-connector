"""Going round a horizontal timeline (brief.mode "lanes"): guided travel with a magnetic settle.

Luke (2026-10-16): the horizontal timeline should have "a bit more of an
automatic feeling for going around it, as opposed to a free form where you can
scroll wherever you want". The first answer (1.9.88: every gesture one event,
locked out until it landed) was, in his words, "too rigid to navigate now". So
this is the middle: the camera moves as freely and as far as the hand says, but
only ALONG the story, and when the hand stops it comes to rest on an event.

The path: the main line's events in page order (ACT_SEQS flattened), each with
the view it rests in — centred across; up and down the line kept where the main
line sat when the page opened, moved only as far as it must to keep the card
clear of the bars at the top and the rail at the bottom. Strung together they are
the path. Across is the input: wheel, trackpad, a drag (mouse, pen, touch screen)
move the camera along it one px for one; the height follows by itself, level at
every event and easing between (so it dips into a flashback's past track and back
up with the line). Up-and-down input is the same travel (a vertical wheel, a
vertical drag); nobody scrolls the height by hand. A view off the path (a
character's own event reached with ↑ / ↓, the page as it opens, a scrollbar)
is carried as an offset that fades over the next few hundred px of travel.

Inertia: a trackpad's own inertia tail is just more, smaller wheel events, so it
is more travel, never a new gesture. A mouse notch moves about a third of the gap
to the next event, chased smoothly; a fast spin adds up. A flung drag coasts and
slows. Nothing is swallowed and nothing is locked out.

The magnetic settle: SETTLE ms after the last movement the camera glides (the
engine's curve, _altoEase) on to an event: the next one in the direction of
travel once BIAS of the gap has been covered toward it (BIAS_MIN..BIAS_MAX px),
otherwise back onto the one it came from / passed. Any input interrupts the settle
where it is: a wheel takes over with the glide's speed, a hand stops it dead.
Resting is exact: the canvas's own whole-px offsets (the engine's scroll axis).

The deliberate steps stay: ← / → / Space / PageUp / PageDown / Home / End and the
rail's buttons go exactly one event (each landing before the next, up to three
waiting, like the engine's _hop). ↑ / ↓ go to the nearest event on the next line
over (lanes.py). A click on a card enlarges it; Enter enlarges the current one.

Character focus: clicking a character in the key, or its label on the page,
keeps that line (lanes.py isolate) and the path is then only that character's
events: its own and the ones it is on the page for. Click again, or Esc, for all.
A timeline with no `present` and no flashbacks (a v1 brief) has every event on
the path, in page order.

The rail: n / N (the nearest event while travelling, the one at rest when still),
the flashback's name, a thumb that moves with the camera and can be dragged along
the path, and the toggle for the whole timeline fitted to the window (clicking a
spot there comes back down to the event nearest it).

Safari: the wheel is held (non-passive) on #canvas only; every scroll write goes
through the engine's whole-px axis; the document never scrolls; #glass-slab is
never resized (the whole timeline's backdrop is a fixed layer of its own).
Phones keep the engine's card-by-card view and its swipe-peek: none of this runs
there. prefers-reduced-motion: travel follows the hand with no smoothing, steps
and settles jump.

Geometry read from window._altoLanesGeo (lanes.py): x[id], y[id] (card centre,
world px without WORLD_PAD_TOP), h[id], lines [{id, y, ev}], W, H, and at[id] =
{x, y, line, flash}: where the event sits on its line.
"""

NAV_CSS = """
  /* the rail: where you are in the story, and the way to the whole timeline (lanes_nav.py) */
  #lanes-nav{ position:fixed; z-index:305; left:50%; bottom:calc(var(--alto-row-b, 24px) - 2.5px);   /* (40px tall: centred on the 35px controls' line) */ transform:translateX(-50%); display:flex; align-items:center; gap:4px;
    height:40px; box-sizing:border-box; padding:0 6px; border-radius:20px; color:var(--muted); font-size:12px; user-select:none; -webkit-user-select:none;
    background:var(--card-glass-bg, var(--surface));
    -webkit-backdrop-filter:blur(18px) saturate(190%) brightness(var(--card-glass-bright, 1)); backdrop-filter:blur(18px) saturate(190%) brightness(var(--card-glass-bright, 1));
    border:1px solid var(--card-glass-border, var(--border)); box-shadow:0 10px 26px var(--node-rest-shadow), inset 0 0 0 0.5px var(--card-glass-rim); }
  #lanes-nav button{ all:unset; box-sizing:border-box; width:28px; height:28px; border-radius:50%; display:flex; align-items:center; justify-content:center; cursor:pointer; color:var(--muted); }
  #lanes-nav button:hover{ color:var(--text); background:color-mix(in srgb,var(--text) 8%,transparent); }
  #lanes-nav button:focus-visible{ outline:2px solid var(--accent); outline-offset:1px; }
  #lanes-nav button[aria-pressed="true"]{ color:var(--accent); }
  #lanes-nav button:disabled{ opacity:.3; cursor:default; background:none; }
  #lanes-nav{ transition:opacity .25s; }
  /* a narrow window (not a phone's whole view, which has its own rule in phone.py): the control row fills the foot, so the bar rides on the line above it,
     12px clear, never under the search, list, i and star buttons (Board B-1121-LOOK267-R2) */
  @media (max-width:900px){ html:not(.phone-whole) #lanes-nav{ bottom:calc(var(--alto-row-b, 24px) + 47px); max-width:calc(100vw - 24px); } }
  #lanes-nav.lnv-away{ opacity:0; pointer-events:none; }
  #lanes-nav .lnv-mid{ display:flex; flex-direction:column; justify-content:center; gap:4px; width:250px; padding:0 4px; }
  #lanes-nav .lnv-txt{ display:flex; align-items:baseline; gap:7px; white-space:nowrap; overflow:hidden; font-variant-numeric:tabular-nums; line-height:1; }
  #lanes-nav .lnv-txt b{ color:var(--text); font-weight:700; }
  #lanes-nav .lnv-tag{ overflow:hidden; text-overflow:ellipsis; font-weight:700; letter-spacing:.03em; }
  #lanes-nav .lnv-tag button{ display:inline-flex; width:auto; height:auto; padding:0 3px; margin-left:3px; border-radius:4px; font-size:11px; }
  #lanes-nav .lnv-rail{ position:relative; height:12px; cursor:pointer; touch-action:none; }
  #lanes-nav .lnv-rail::before{ content:''; position:absolute; left:0; right:0; top:5px; height:2px; border-radius:1px; background:color-mix(in srgb,var(--muted) 35%,transparent); }
  #lanes-nav .lnv-fb{ position:absolute; top:4px; height:4px; border-radius:2px; background:color-mix(in srgb,var(--muted) 75%,transparent); min-width:4px; }
  #lanes-nav .lnv-thumb{ position:absolute; left:0; top:1px; width:10px; height:10px; margin-left:-5px; border-radius:50%; background:var(--accent); cursor:grab;
    box-shadow:0 0 0 2px var(--surface); will-change:transform; }
  #lanes-nav .lnv-thumb:focus-visible{ outline:2px solid var(--accent); outline-offset:2px; }
  #lanes-nav.scrub .lnv-thumb{ cursor:grabbing; }
  .lnv-sr{ position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; }
  html.mobile #lanes-nav, html.detail-open #lanes-nav, html.printing #lanes-nav, html.alto-editing #lanes-nav{ display:none !important; }
  /* the camera keeps to the path: nothing pans the board by itself */
  html.alto-lanes:not(.mobile):not(.alto-editing) #canvas{ touch-action:none; overscroll-behavior:none; }
  html.alto-lanes:not(.mobile):not(.alto-editing) #canvas.ln-drag{ cursor:grabbing; }
  html.alto-lanes:not(.mobile) #world .node[data-ln] .node-card:focus{ outline:none; }
  html.alto-lanes:not(.mobile) #world .node[data-ln] .node-card:focus-visible{ outline:2px solid var(--accent); outline-offset:3px; }
  /* the event the steps are on */
  html.alto-lanes.ln-stepped:not(.mobile) #world .node.ln-cur:not(.focused) .node-card{ box-shadow:0 0 0 2px color-mix(in srgb,var(--accent) 60%,transparent), 0 10px 26px var(--node-rest-shadow); }
  /* the whole timeline, fitted to the window */
  html.alto-lanes #canvas.ln-ov{ cursor:zoom-in; }
  html.alto-lanes #canvas.ln-ov.ln-zin{ cursor:grab; }
  html.alto-lanes #canvas.ln-ov.ln-drag{ cursor:grabbing; }
  html.alto-lanes #canvas.ln-ov #world, html.alto-lanes #canvas.ln-ovanim #world{ pointer-events:none; transform-origin:0 0; will-change:transform; }
  /* the overview (ovMarks): titles only at a reading size, or cards as blocks; lines at their drawn width; unit labels at reading size */
  html.alto-lanes #canvas.ln-ovmk #world .node-card > *{ opacity:0; transition:opacity .2s ease; }
  html.alto-lanes #canvas.ln-ovtt #world .node-card > .node-title{ opacity:1; position:absolute; left:7%; right:7%; top:10%; bottom:10%; margin:0 !important; font-size:var(--ovtf,16px) !important;
    line-height:1.15 !important; white-space:normal !important; overflow:hidden; display:-webkit-box !important; -webkit-box-orient:vertical; -webkit-line-clamp:var(--ovtl,2); bottom:auto; text-overflow:ellipsis; }
  /* (Board 2026-11-27: titles were cut mid-line at the block's foot: as many whole lines as the block holds, the last one ending in an ellipsis) */
  html.alto-lanes #canvas.ln-ovmk #world .node-card{ border-width:calc(2px * var(--ovk,1)) !important; }
  html.alto-lanes #canvas.ln-ovmk #world :is(.lanes-tag,.ln-chip,.ln-otag,.lanes-past){ visibility:hidden; }
  html.alto-lanes #canvas.ln-ovmk #lanes-svg :is(path,line,polyline){ vector-effect:non-scaling-stroke; }
  html.alto-lanes #canvas.ln-ovmk #lanes-ulabels .lu-strip > .lu-chip{ position:absolute; left:0; transform:translateY(var(--lu-dy,0px)) scale(var(--ovk,1)); transform-origin:0 50%; will-change:auto; }
  html.alto-lanes #canvas.ln-ovmk #lanes-ulabels .lu-chip.lu-ovn{ width:auto !important; }
  html.alto-lanes #canvas.ln-ovmk #lanes-ulabels .lu-chip.lu-ovn span{ display:none; }
  html.alto-lanes #canvas.ln-ovmk #lanes-ulabels .lu-chip.lu-ovn b{ margin-right:0; }
  /* the minimap (Luke 2026-11-26, "instead of the view whole timeline button in the middle nav controls zooming out, make a minimap simplified where
     we usually have them that shows where the user is in the whole thing"): where every desktop minimap sits (minimap_home.py), just above the
     bottom-right buttons and as wide as they are; the main line, the cards, the event the steps are on, and the box the window shows. A phone keeps
     its whole-timeline button in the bar (no minimap there). */
  /* Luke 2026-11-27: "the back to events button on the left of the middle toggle isn't useful" (Board: (b) + (c)): the desktop has no whole-timeline
     button (the minimap, pinch, ⌘ + scroll and − reach the whole view; Esc, 0, a click and ‹ › come back); a phone keeps it, to open the whole view only */
  html:not(.phone-whole) #lanes-nav .lnv-ov{ display:none; }
  /* its on / off switch (Luke 2026-11-26, "should be able to toggle minimap on/off like usual, so bring back that button"): the map button in the
     bar, as System's and the Atlas's bars have it, remembered per page; while the minimap is off the whole-timeline button is back */
  #lanes-nav.lnv-nomm .lnv-map, html.phone-whole #lanes-nav .lnv-map{ display:none; }   /* (a window too narrow for the minimap to clear the bar keeps the button: lnv-nomm) */
  #ln-mm{ position:fixed; z-index:305; box-sizing:border-box; padding:5px 7px; border-radius:12px; cursor:pointer; touch-action:none; user-select:none; -webkit-user-select:none;
    background:var(--surface, #fff); border:1px solid var(--card-glass-border, var(--border)); box-shadow:0 10px 26px var(--node-rest-shadow);   /* (opaque: no card's text reads through it) */
    opacity:0; visibility:hidden; pointer-events:none; transition:opacity .25s ease, visibility 0s .25s; }
  #ln-mm.on{ opacity:1; visibility:visible; pointer-events:auto; transition:opacity .25s ease; }
  #ln-mm svg{ display:block; width:100%; height:100%; overflow:visible; }
  #ln-mm .mm-l{ fill:none; stroke:color-mix(in srgb, var(--accent) 62%, var(--text)); stroke-linecap:round; stroke-linejoin:round; stroke-width:2.5px; vector-effect:non-scaling-stroke; }
  #ln-mm .mm-c{ fill:var(--muted); fill-opacity:.38; }
  #ln-mm .mm-c.k{ fill-opacity:.2; }
  #ln-mm .mm-c.h{ fill:var(--accent); fill-opacity:1; }
  /* the units (Luke 2026-11-26, "Add some unit label distinction on minimap"): each unit's own colour as a faint band, a divider where it
     begins, and its numeral at the top of the band (HTML over the drawing, so the stretched drawing never distorts it) */
  #ln-mm .mm-ub{ fill:var(--uc); fill-opacity:.16; }
  #ln-mm .mm-ud{ stroke:var(--uc); stroke-opacity:.85; stroke-width:1.5px; vector-effect:non-scaling-stroke; }
  #ln-mm .mm-un{ position:absolute; top:3px; margin-left:3px; font:800 9px/1 system-ui, -apple-system, sans-serif; letter-spacing:.06em; color:var(--uc);
    pointer-events:none; white-space:nowrap; text-shadow:0 0 2px var(--surface, #fff), 0 0 2px var(--surface, #fff); }
  html.alto-retro #ln-mm .mm-un, html.alto-holo #ln-mm .mm-un{ text-shadow:0 0 2px #000, 0 0 2px #000; }
  html.alto-retro #ln-mm .mm-ub, html.alto-holo #ln-mm .mm-ub{ fill-opacity:.22; }
  #ln-mm .mm-v{ fill:var(--accent); fill-opacity:.12; stroke:var(--accent); stroke-width:1.5px; vector-effect:non-scaling-stroke; }
  #ln-mm:focus-visible{ outline:2px solid var(--accent); outline-offset:2px; }
  html.alto-retro #ln-mm{ border-radius:0; background:#000; border-color:#d9ae55; }
  html.alto-retro #ln-mm .mm-l{ stroke:#d9ae55; } html.alto-retro #ln-mm .mm-c{ fill:#efe6cf; } html.alto-retro #ln-mm .mm-c.h{ fill:#d9ae55; }
  html.alto-retro #ln-mm .mm-v{ fill:#d9ae55; fill-opacity:.1; stroke:#d9ae55; }
  html.alto-holo #ln-mm{ border-radius:0; background:#05070b; border-color:#4ff0e0; }
  html.alto-holo #ln-mm .mm-l, html.alto-holo #ln-mm .mm-v{ stroke:#4ff0e0; } html.alto-holo #ln-mm .mm-c.h, html.alto-holo #ln-mm .mm-v{ fill:#4ff0e0; }
  html.mobile #ln-mm, html.phone-whole #ln-mm, html.detail-open #ln-mm, html.printing #ln-mm, html.alto-editing #ln-mm{ display:none !important; }
  @media print{ #ln-mm{ display:none !important; } }
  @media (prefers-reduced-motion:reduce){ #ln-mm{ transition:none; } }
  /* the material's cross-references on an open board (NAV_JS): quiet at rest, full while one of their cards is hovered or enlarged */
  #lanes-svg g.ln-xrefs .ln-xline{ fill:none; stroke-width:1.5; stroke-opacity:.22; stroke-dasharray:6 5; stroke-linejoin:round; transition:stroke-opacity .2s, stroke-width .2s; }
  #lanes-svg g.ln-xrefs .ln-xdot{ opacity:.3; transition:opacity .2s; }
  #lanes-svg g.ln-xrefs .ln-xhit{ fill:none; stroke:transparent; stroke-width:10; pointer-events:stroke; }
  #lanes-svg g.ln-xrefs g.ln-xon .ln-xline{ stroke-opacity:.95; stroke-width:2.5; stroke-dasharray:none; }
  #lanes-svg g.ln-xrefs g.ln-xon .ln-xdot{ opacity:1; }
  @media print{ #lanes-svg g.ln-xrefs{ display:none; } }
  /* the enlarged card held to the room on a phone (NAV_JS): it scrolls inside, and its touch moves its text, not the board */
  /* while a card is enlarged and fitted on a phone the units' labels step away (Board 2026-11-27: "I BEFORE SUIT" showed under the ring on one path) */
  html.phone-whole.ln-fitting #lanes-ulabels .lu-chip{ visibility:hidden !important; }
  html.phone-whole #world .node.focused .node-card.ln-fit > .ln-fitw{ overflow-y:auto; overscroll-behavior:contain; -webkit-overflow-scrolling:touch; touch-action:pan-y; min-height:0; }
  html.phone-whole #world .node.focused .node-card.ln-fit > .ln-fitw.ln-more{ -webkit-mask-image:linear-gradient(to bottom,#000 calc(100% - 14px),transparent); mask-image:linear-gradient(to bottom,#000 calc(100% - 14px),transparent); }
  /* Classic's page-name pill while the board runs under it on a phone: its frost let a dimmed card's words read through it (Board 2026-11-27) */
  html.phone-whole.ln-under:not(.alto-retro):not(.alto-holo) #nav > .title:not(#_):not(#__){ background:var(--surface,#fff) !important; -webkit-backdrop-filter:none !important; backdrop-filter:none !important; box-shadow:0 0 0 4px var(--surface,#fff) !important; }
"""

NAV_JS = r"""
(function(){
var L=window._ALTO_LANES; if(!L) return;
var de=document.documentElement;
if(de.classList.contains('mobile')) return;          // phones: the engine's card-by-card view and swipe-peek
/* travel (see the docstring): the settle waits SETTLE ms of stillness; the wheel is chased
   with TAU_CHASE; a flung drag coasts as far as TAU_FLING of its speed; the settle goes on to the next event
   once BIAS of the gap (BIAS_MIN..BIAS_MAX px) is travelled toward it */
var SETTLE=170, TAU_CHASE=55, TAU_FLING=330, FLING_MIN=.12, FLING_MAX=5, COAST_PW=2.5, OFFLEN=260, MINSEG=56,
    BIAS=.12, BIAS_MIN=12, BIAS_MAX=48, NOTCH=.34, NOTCH_MIN=90, NOTCH_MAX=240, NOTCH_MS=260, SOFT=12, SFN=4.000244140625, LONE=40, GESTURE=120,
    QMAX=3, OV_MK=0.5, ZMAX=3, ZSNAP=.05, ZGAP=220;
var RM=window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
function reduced(){ return !!(RM && RM.matches); }
function cv(){ return document.getElementById('canvas'); }
function geo(){ return window._altoLanesGeo; }
function PAD(){ return typeof WORLD_PAD_TOP!=='undefined' ? WORLD_PAD_TOP : 0; }
function on(){ return !!geo() && !de.classList.contains('mobile') && !de.classList.contains('alto-editing') && !de.classList.contains('printing'); }
function busyElsewhere(){
  return de.classList.contains('detail-open') || !!window._focusedNodeId ||
    !!document.querySelector('#notes-panel.open,#summary-wrap.open,#ef-panel.open,#bg-panel.open,#note-dialog.visible,#search-btn.expanded,#share-dialog.visible');
}
/* the same curve as every other glide (the engine's _altoEase, B(1.4,2.6)); the table is only a fallback */
var _tab=(function(){ var M=1000, c=[0], s=0, i, x; for(i=0;i<M;i++){ x=(i+.5)/M; s+=Math.pow(x,.4)*Math.pow(1-x,1.6); c.push(s); } for(i=0;i<=M;i++) c[i]/=s; return c; })();
function ease(p){ if(window._altoEase) return window._altoEase(p); if(p<=0) return 0; if(p>=1) return 1; var f=p*1000, i=Math.floor(f); return _tab[i]+(_tab[i+1]-_tab[i])*(f-i); }
/* longer hops take a little longer, as a hand's do: gentle, never a rush (1.9.67) */
function glideMs(d){ return Math.round(Math.min(1100, Math.max(560, 460+.2*d))); }
/* the canvas's scroll, written through the engine's whole-px axis (Safari floors a
   written offset under the page's zoom; engine_patches fly-scrolls-in-whole-px) */
function axis(prop){
  var c=cv();
  if(window._altoScrollAxis) return window._altoScrollAxis(prop);
  return {at:function(){ return c[prop]; }, stop:function(v){ return Math.round(v); }, go:function(v){ c[prop]=v; }};
}

/* ── the stops ─────────────────────────────────────────────────────────── */
function pageOrder(){
  var G=geo(), seen={}, out=[], src=(typeof ACT_SEQS!=='undefined' ? [].concat.apply([],ACT_SEQS) : []).concat(L.order||[], Object.keys(L.ev));
  src.forEach(function(id){ if(!seen[id] && L.ev[id] && G && G.x[id]!=null){ seen[id]=1; out.push(id); } });
  return out;
}
/* v1 data (no one on the page anywhere, no flashbacks): the side lines carry the story, so every event is a stop */
function legacy(){
  if((L.flashbacks||[]).length) return false;
  for(var k in L.ev){ var p=L.ev[k].present; if(p && p.length) return false; }
  return true;
}
function hid(id){ return !!(window._altoLanesHid && window._altoLanesHid(id)); }
function live(id){ return !!document.querySelector('#node-'+id+' .node-card') && !hid(id) && (!window._altoShown || window._altoShown(id)); }
function lineDef(id){ for(var i=0;i<L.lines.length;i++) if(L.lines[i].id===id) return L.lines[i]; return null; }
/* the lines picked to show only them (lanes.py setPick): their events are the only ones left on the board */
function picks(){ return (window._altoLanesPick ? window._altoLanesPick() : []).filter(lineDef); }
function ofChar(id, c){
  var e=L.ev[id], ln=lineDef(c); if(!e) return false;
  if(e.l===c || (e.present||[]).indexOf(c)>=0) return true;
  return !!ln && ((ln.presence||[]).indexOf(id)>=0 || ln.from===id || ln.to===id);
}
var _S=null;       // cached per call chain: {ids, at}
function stops(){
  var o=pageOrder(), c=picks(), lg=legacy();
  if(!c.length && _ln && lineDef(_ln)) c=[_ln];       // a line reached with a held or pressed ↑ / ↓: the steps and the travel go along it
  var ids=o.filter(function(id){ if(!live(id)) return false; if(c.length) return c.some(function(k){ return ofChar(id,k); }); return lg || (L.ev[id].l||'main')==='main'; });
  if(!ids.length) ids=o.filter(live);
  var at={}; o.forEach(function(id,i){ at[id]=i; });
  return _S={ids:ids, at:at, ch:c.length ? c : null};
}
function neighbour(id, dir){
  var S=stops(), i=S.ids.indexOf(id);
  if(i>=0) return S.ids[i+dir]||null;
  var oi=S.at[id]; if(oi==null) return dir>0 ? S.ids[0] : S.ids[S.ids.length-1];
  /* an event off the main line: on to its page-order neighbour */
  if(dir>0){ for(var k=0;k<S.ids.length;k++) if(S.at[S.ids[k]]>oi) return S.ids[k]; return null; }
  for(var j=S.ids.length-1;j>=0;j--) if(S.at[S.ids[j]]<oi) return S.ids[j]; return null;
}
function flashOf(id){ var f=(L.ev[id]||{}).flash; if(!f) return null; var fb=(L.flashbacks||[]).filter(function(q){ return q.id===f; })[0]; return fb||null; }
function title(id){ var n=(typeof NODES_SRC!=='undefined'?NODES_SRC:[]).filter(function(q){ return q.id===id; })[0]; return n ? (n.title||'') : ''; }

/* ── the camera ─────────────────────────────────────────────────────────── */
function zk(c){ var r=c.getBoundingClientRect(); return (r.width && c.offsetWidth) ? r.width/c.offsetWidth : 1; }
function worldOff(c){ var w=document.getElementById('world'), ox=0, oy=0, q=w; while(q && q!==c){ ox+=q.offsetLeft; oy+=q.offsetTop; q=q.offsetParent; } return {x:ox, y:oy}; }
function shown(el){ if(!el) return null; var r=el.getBoundingClientRect(); return (r.width && r.height && getComputedStyle(el).display!=='none') ? r : null; }
/* the part of the canvas no chrome sits over: under the key's toggle, above the rail */
function band(c){
  var r=c.getBoundingClientRect(), k=zk(c), ch=c.clientHeight, t=16, b=ch-16, q;
  if((q=shown(document.getElementById('key-toggle'))) && q.bottom>r.top && q.top<r.top+ch/2) t=Math.max(t,(q.bottom-r.top)/k+12);
  if((q=shown(document.getElementById('lanes-nav'))) && q.top<r.bottom) b=Math.min(b,(q.top-r.top)/k-14);
  if(b-t<160){ t=16; b=ch-16; }
  return {t:t, b:b};
}
function lineY(G, id){ for(var i=0;i<G.lines.length;i++){ var l=G.lines[i]; if(l.ev && l.ev.indexOf(id)>=0) return l.y; } return G.lines[0] ? G.lines[0].y : G.y[id]; }
function anchor(id){
  var G=geo(), a=(G.at && G.at[id]) || (G.anchor && G.anchor[id]);
  if(a && a.x!=null && a.y!=null) return {x:a.x, y:a.y};
  return {x:G.x[id], y:lineY(G,id)};
}
var _home=null;    // where (canvas px from its top) the main line sat when the page opened
function home(c, B){
  if(_home==null){
    var G=geo(), my=(G.lines[0]?G.lines[0].y:0)+PAD()+worldOff(c).y-c.scrollTop;
    _home=Math.max(B.t+80, Math.min(B.b-80, my));
  }
  return Math.max(B.t, Math.min(B.b, _home));
}
/* where the main line rests: the opening height, moved (once, for every event alike) so that
   the tallest card above the line and the deepest below it both fit between the bars and the
   rail; if they cannot all fit, the middle of the misfit. The camera follows the MAIN LINE and
   nothing else: it never moves up or down to suit one event's card or a character's track
   (that was the bounce). Only a flashback's dip, which is the main line itself, moves it. */
var _fit=null;
function mainAt(id){ var G=geo(), a=anchor(id), ev=G.at && G.at[id];       // the main line's height at this event (a character's own event: the page's height beside it)
  return (ev && ev.line && ev.line!=='main' && G.mainY!=null) ? G.mainY : a.y; }
function fitHome(c, B, ids){
  var G=geo(), up=0, dn=0;
  ids.forEach(function(id){ var m=mainAt(id), h=G.h[id]||120, top=(G.y[id]!=null?G.y[id]:m)-h/2;
    up=Math.max(up, m-Math.min(m,top)); dn=Math.max(dn, Math.max(m,top+h)-m); });
  var lo=B.t+up, hi=B.b-dn, h0=home(c,B);
  return lo<=hi ? Math.max(lo,Math.min(hi,h0)) : (lo+hi)/2;
}
function phone(){ return de.classList.contains('phone-whole'); }
function lineHome(c, B){ if(_fit==null || _fit.t!==B.t || _fit.b!==B.b) _fit={t:B.t, b:B.b, y:fitHome(c,B,stops().ids)}; return _fit.y; }
/* the scroll offsets that put this event where it rests */
function camFor(id, B){
  var c=cv(), G=geo(), off=worldOff(c), P=PAD(), a=anchor(id);
  B=B||band(c);
  var cw=c.clientWidth, ch=c.clientHeight;
  var tl=a.x+off.x-cw/2;
  var tt=mainAt(id)+P+off.y-lineHome(c,B);      // the main line stays where it rests, whatever this event's card or line does
  return {l:Math.max(0,Math.min(tl, c.scrollWidth-cw)), t:Math.max(0,Math.min(tt, c.scrollHeight-ch)), ml:c.scrollWidth-cw, mt:c.scrollHeight-ch};
}

/* ── the path: the stops' resting views strung together in page order ──────
   The camera travels along it. Where it is along the path (u, px) is the only
   thing the wheel, a drag or a fling change; across and up and down follow from
   it: across moves with u one for one, up and down eases from one stop's rest
   height to the next (smoothstep, so it is level at every stop and dips into a
   flashback's past track and back up with the line). A view that is not on the
   path (a character's own event, the page as it opened, a scrollbar drag) is an
   offset (ox, oy) from the nearest point of the path, which fades out over the
   next few hundred px of travel, so nothing ever jumps back onto the path. */
var M={hv:0, u:0, uT:0, pend:[], vel:0, ox:0, oy:0, raf:0, last:0, input:-1e9, dir:1, restU:0, restId:null, gl:null, drag:null, pth:null, wr:null, near:null, stale:false, vy:null};
function buildPath(){
  var c=cv(), S=stops(), B=band(c), ids=S.ids, P=[], U=[], ml=0, mt=0;
  _fit={t:B.t, b:B.b, y:fitHome(c,B,ids)};
  for(var i=0;i<ids.length;i++){
    var t=camFor(ids[i],B); ml=t.ml; mt=t.mt; P.push([t.l,t.t]);
    /* two events resting at the very same view (the opening's first two: the camera cannot centre them, so both sit at scroll 0) are one
       stop for the hand: a gap of 1 px, so the first notch, swipe or key press goes on to a view that is visibly somewhere else */
    var same=i && Math.abs(t.l-P[i-1][0])<.5 && Math.abs(t.t-P[i-1][1])<.5 && (t.l<.5 || t.l>t.ml-.5);   // (only at an end of the board, where the camera cannot centre them)
    U.push(i ? U[i-1]+(same ? 1 : Math.max(MINSEG, Math.abs(t.l-P[i-1][0]))) : 0);
  }
  if(!ids.length){ ml=c.scrollWidth-c.clientWidth; mt=c.scrollHeight-c.clientHeight; }
  return M.pth={ids:ids, P:P, U:U, end:U.length ? U[U.length-1] : 0, ml:ml, mt:mt};
}
function seg(u){ var U=M.pth.U, lo=0, hi=U.length-2; if(hi<0) return 0; while(lo<hi){ var m=(lo+hi+1)>>1; if(U[m]<=u) lo=m; else hi=m-1; } return lo; }
function sm(f){ return f*f*(3-2*f); }
function pathAt(u){
  var p=M.pth, P=p.P; if(!P.length) return [cv().scrollLeft, cv().scrollTop]; if(P.length<2) return [P[0][0],P[0][1]];
  var i=seg(u), a=P[i], b=P[i+1], f=Math.max(0,Math.min(1,(u-p.U[i])/(p.U[i+1]-p.U[i])));
  return [a[0]+(b[0]-a[0])*f, a[1]+(b[1]-a[1])*sm(f)];
}
function fracAt(u){ var U=M.pth.U; if(U.length<2) return 0; var i=seg(u); return i+Math.max(0,Math.min(1,(u-U[i])/(U[i+1]-U[i]))); }
/* the point of the path nearest a view: across first, then height; ties go to the nearest u */
function project(L,T){
  var p=M.pth, P=p.P, U=p.U, n=P.length, best=0, bd=Infinity;
  if(n<2) return 0;
  for(var i=0;i<n-1;i++){
    var a=P[i], b=P[i+1], dl=b[0]-a[0], fs=[0,1,.5];
    if(Math.abs(dl)>.5) fs.push(Math.max(0,Math.min(1,(L-a[0])/dl)));
    for(var j=0;j<fs.length;j++){
      var u=U[i]+(U[i+1]-U[i])*fs[j], q=pathAt(u), d=Math.abs(q[0]-L)+.5*Math.abs(q[1]-T)+.001*Math.abs(u-M.u);
      if(d<bd){ bd=d; best=u; }
    }
  }
  return best;
}
function stopIx(id){ return M.pth ? M.pth.ids.indexOf(id) : -1; }
/* take the camera from wherever the view is now */
function resync(){
  var c=cv(), L=axis('scrollLeft').at(), T=axis('scrollTop').at();
  buildPath();
  var k=stopIx(_cur), u=(k>=0 && _land && !moved(c)) ? M.pth.U[k] : project(L,T), q;
  M.u=M.uT=u; q=pathAt(u); M.ox=L-q[0]; M.oy=T-q[1]; M.pend.length=0; M.vel=0;
  M.wr=[c.scrollLeft, c.scrollTop]; M.near=null;
}
function invalidate(){ _fit=null; if(M.raf) M.stale=true; else M.pth=null; }
function extMoved(){ var c=cv(); return !M.wr || Math.abs(c.scrollLeft-M.wr[0])>2 || Math.abs(c.scrollTop-M.wr[1])>2; }
/* any input: the camera is taken from where it is, with no jump. A glide in flight
   hands its speed on to the travel (grab: a hand on the board stops it dead) */
function prepare(grab){
  if(M.gl){
    var g=M.gl; M.gl=null; if(g.step){ _busy=false; _q.length=0; }
    M.uT=M.u+(grab||reduced() ? 0 : M.vel*TAU_CHASE);
  } else if(!M.raf || !M.pth || extMoved()){
    resync(); M.restU=M.u; M.restId=(_land && !moved(cv())) ? _cur : null;
  }
  if(grab){ M.pend.length=0; M.uT=M.u; }
  de.classList.add('ln-stepped');
}
function clampU(u){ return Math.max(0, Math.min(M.pth.end, u)); }
/* travel by d px; a notch's travel (soft) is let out over NOTCH_MS on a smooth (half-cosine)
   ramp, so a mouse's discrete clicks still start and stop like a glide */
function addTravel(d, soft){
  if(!on() || _ov || window._focusedNodeId) return;
  prepare(false); if(!d) return;
  var now=performance.now();
  M.dir=d>0?1:-1;
  if(soft && !reduced()) M.pend.push({a:d, t0:now, f:0}); else M.uT=clampU(M.uT+d);
  M.input=now; wake();
}
function release(now){
  for(var i=M.pend.length-1;i>=0;i--){
    var q=M.pend[i], p=Math.min(1,(now-q.t0)/NOTCH_MS), f=(1-Math.cos(Math.PI*p))/2;
    M.uT=clampU(M.uT+q.a*(f-q.f)); q.f=f; if(p>=1) M.pend.splice(i,1);
  }
}
function fade(du){ if(du){ var k=Math.exp(-Math.abs(du)/OFFLEN); M.ox*=k; M.oy*=k; if(Math.abs(M.ox)<.05) M.ox=0; if(Math.abs(M.oy)<.05) M.oy=0; } }
function setU(u){ u=clampU(u); fade(u-M.u); M.u=M.uT=u; }
function wake(){ if(!M.raf){ M.last=performance.now(); M.raf=requestAnimationFrame(tick); } }
function stopLoop(){ if(M.raf) cancelAnimationFrame(M.raf); M.raf=0; M.gl=null; M.pend.length=0; M.uT=M.u; }
/* write the view: through the engine's whole-px axis (Safari), only when it changes */
var _drawn=null;
function draw(){
  var c=cv(), q=pathAt(M.u), L=Math.max(0,Math.min(M.pth.ml,q[0]+M.ox)), T=Math.max(0,Math.min(M.pth.mt,q[1]+M.oy));
  if(M.vy!=null) T=Math.max(0,Math.min(M.pth.mt,M.vy));      // a height the hand chose (two fingers or a drag, up and down) stays
  if(_drawn && Math.abs(_drawn[0]-L)<.01 && Math.abs(_drawn[1]-T)<.01 && !extMoved()) return;
  _drawn=[L,T]; axis('scrollLeft').go(L); axis('scrollTop').go(T); M.wr=[c.scrollLeft, c.scrollTop];
  if(M.vy!=null && _land) _land[1]=c.scrollTop;               // (a height the hand chose is not the view having been moved off its event)
}
/* the rail and the ring follow the nearest event while travelling */
function follow(){
  var p=M.pth, U=p.U, n=U.length; if(!n) return;
  var i=seg(M.u), k=(n>1 && M.u-U[i]>U[i+1]-M.u) ? i+1 : i, id=p.ids[k];
  if(id!==M.near){ M.near=id; setCur(id); ui(id,0); }
}
function thumb(){ if(!R || !M.pth) return; var N=M.pth.ids.length, f=railFrac(fracAt(M.u),N); R.thumb.style.transition='none'; R.thumb.style.transform='translateX('+(f*R.rail.clientWidth).toFixed(2)+'px)'; }
function tick(now){
  M.raf=0;
  var c=cv();
  if(!c || !on() || _ov || window._focusedNodeId){ if(M.gl && M.gl.step){ _busy=false; _q.length=0; } M.gl=null; M.pend.length=0; M.hv=0; return; }
  if(M.stale && !M.drag){                                     // laid out again mid-travel: carry on from the view as it is
    M.stale=false; var g0=M.gl; M.gl=null; resync();
    if(g0){ glideTo(g0.id, {settle:g0.settle, step:g0.step}, g0.done); return; }
  }
  if(!M.pth) resync();
  var dt=Math.max(1,Math.min(50,now-M.last)), u0=M.u; M.last=now;
  if(M.gl){
    var g=M.gl, p=g.ms>0 ? Math.max(0,Math.min(1,(now-g.s0)/g.ms)) : 1, k=g.hv ? herm(p, g.hv*g.ms/(g.u1-g.u0)) : g.pw ? 1-Math.pow(1-p,g.pw) : ease(p);
    M.u=M.uT=g.u0+(g.u1-g.u0)*k; M.ox=g.ox0+(g.ox1-g.ox0)*k; M.oy=g.oy0+(g.oy1-g.oy0)*k; M.vel=(M.u-u0)/dt;
    if(p>=1){ M.gl=null; land(g); return; }
    draw(); thumb(); M.raf=requestAnimationFrame(tick); return;
  }
  {
    if(M.pend.length) release(now);
    if(M.hv){ M.uT=clampU(M.uT+M.hv*Math.min(32,dt)); M.input=now; }     // a held arrow: this frame's travel, on the same clock as the chase below
    var kk=(reduced() || M.drag) ? 1 : 1-Math.exp(-dt/TAU_CHASE), nu2=M.u+(M.uT-M.u)*kk;
    if(Math.abs(M.uT-nu2)<.05) nu2=M.uT;
    fade(nu2-M.u); M.u=nu2;
  }
  M.vel=(M.u-u0)/dt;
  draw(); follow(); thumb();
  var moving=!!M.drag || !!M.hv || M.pend.length>0 || Math.abs(M.uT-M.u)>.05;
  if(!moving && now-M.input>=SETTLE){ settle(); return; }
  M.raf=requestAnimationFrame(tick);
}
/* the magnetic settle: input has stopped, so glide on to the nearest event, leaning the
   way the travel went (BIAS of the gap, at least BIAS_MIN and at most BIAS_MAX px into it
   is enough to go on to the next one; less eases back) */
function pick(u, dir){
  var p=M.pth, U=p.U, n=U.length; if(!n) return null;
  if(u==null) u=M.u; if(dir==null) dir=M.dir;
  if(M.restId && stopIx(M.restId)<0 && Math.abs(u-M.restU)<BIAS_MIN) return M.restId;   // barely moved off a character's event
  if(n<2 || u<=U[0]) return p.ids[0]; if(u>=U[n-1]) return p.ids[n-1];
  var i=seg(u), L=U[i+1]-U[i], into=u-U[i], th=Math.min(L/2, Math.max(BIAS_MIN, Math.min(BIAS_MAX, L*BIAS)));
  if(dir>=0) return p.ids[into>=th ? i+1 : i];
  return p.ids[(L-into)>=th ? i : i+1];
}
function settle(){
  var id=pick(); if(!id){ M.raf=0; return; }
  glideTo(id, {settle:true});
}
/* a glide that starts at the camera's own speed and ends at rest (Hermite: slope m at the start, none at the end; m <= 3 keeps it from backing up) */
function herm(p, m){ m=Math.max(0,Math.min(3,m||0)); var p2=p*p, p3=p2*p; return (p3-2*p2+p)*m+(-2*p3+3*p2); }
function settleMs(d){ return Math.round(Math.min(700, Math.max(380, 340+.6*d))); }
/* glide the camera to an event along the path (on the engine's curve); done() when it rests */
function glideTo(id, opt, done){
  opt=opt||{};
  var c=cv(); if(!c || !geo() || geo().x[id]==null){ if(done) done(); return; }
  if(M.gl){ var gx=M.gl; M.gl=null; if(gx.step && !opt.step){ _busy=false; _q.length=0; } }
  if(!M.raf || !M.pth || extMoved()) resync();
  var k=stopIx(id), u1, ox1=0, oy1=0;
  if(k>=0) u1=M.pth.U[k];
  else { var t=camFor(id); u1=project(t.l,t.t); var q1=pathAt(u1); ox1=t.l-q1[0]; oy1=t.t-q1[1]; }
  var q0=pathAt(M.u), q2=pathAt(u1), dx=(q2[0]+ox1)-(q0[0]+M.ox), dy=(q2[1]+oy1)-(q0[1]+M.oy), d=Math.sqrt(dx*dx+dy*dy);
  var ms=(opt.instant || reduced() || d<.5) ? 0 : opt.ms ? opt.ms : (opt.settle ? settleMs(d) : glideMs(d));
  setCur(id); M.near=id; _trust=true; M.pend.length=0;
  var g={id:id, u0:M.u, u1:u1, ox0:M.ox, oy0:M.oy, ox1:ox1, oy1:oy1, s0:performance.now(), ms:ms, done:done, settle:!!opt.settle, step:!!opt.step, quiet:d<.5, pw:opt.pw||0, hv:opt.hv||0};
  if(!ms){ if(M.raf){ cancelAnimationFrame(M.raf); M.raf=0; } land(g); return; }
  M.gl=g; wake(); ui(id,0);
}
/* at rest: exactly on the offset the canvas can really take, in whole device px */
function land(g){
  var c=cv(), qx=axis('scrollLeft'), qy=axis('scrollTop'), q=pathAt(g.u1);
  var L=Math.max(0,Math.min(M.pth.ml,q[0]+g.ox1)), T=Math.max(0,Math.min(M.pth.mt,q[1]+g.oy1));
  if(M.vy!=null) T=Math.max(0,Math.min(M.pth.mt,M.vy));
  qx.go(qx.stop(dev(L,M.pth.ml))); qy.go(qy.stop(dev(T,M.pth.mt)));
  M.u=M.uT=g.u1; M.ox=g.ox1; M.oy=g.oy1; M.vel=0; M.raf=0; M.gl=null;
  M.wr=[c.scrollLeft, c.scrollTop]; _drawn=null;
  var was=_cur;
  setCur(g.id); M.restU=g.u1; M.restId=g.id; M.near=null;
  _land=[c.scrollLeft, c.scrollTop]; _trust=false;
  ui(g.id,0); if(!g.quiet || was!==g.id) announce(g.id);
  if(g.done) g.done();
}
function dev(v, max){ var z=zk(cv())*(window.devicePixelRatio||1); if(!(z>0)) return v; var r=Math.round(v*z)/z; if(max!=null && r>max) r=Math.floor(max*z)/z; return Math.max(0,r); }
/* ── where the camera is ──────────────────────────────────────────────────── */
var _cur=null, _land=null, _trust=false, _busy=false, _q=[];
function moved(c){ return !_land || Math.abs(c.scrollLeft-_land[0])>3 || Math.abs(c.scrollTop-_land[1])>3; }
/* the event the view is on: a glide's destination; while travelling, the nearest stop;
   at rest, the last one landed on unless the view has been moved since — then the stop
   whose resting view is nearest the view as it is (ties: the first in page order, so
   the page as it opens is on the first event) */
function current(){
  var c=cv(); if(!c || !geo()) return null;
  if(M.gl) return M.gl.id;
  if(M.raf && M.near) return M.near;
  if(_cur && geo().x[_cur]!=null && live(_cur) && (_trust || !moved(c))) return _cur;
  var S=stops().ids, B=band(c), best=null, bd=Infinity;
  for(var i=0;i<S.length;i++){ var t=camFor(S[i],B), d=Math.abs(t.l-c.scrollLeft)+Math.abs(t.t-c.scrollTop); if(d<bd-0.5){ bd=d; best=S[i]; } }
  return best;
}
function cancelAll(){ var was=!!M.raf; stopLoop(); _q.length=0; _busy=false; M.drag=null; if(was){ _land=null; _trust=false; } }
function setCur(id){
  if(_cur===id) return;
  document.querySelectorAll('#world .node.ln-cur').forEach(function(n){ n.classList.remove('ln-cur'); });
  _cur=id; var n=id && document.getElementById('node-'+id); if(n) n.classList.add('ln-cur');
}
/* the deliberate steps (← → Space PageUp PageDown Home End, the rail's buttons): one
   event each, each landing before the next starts (the engine's _hop): up to three
   wait their turn, a held key's repeat adds at most one */
function step(dir, src, repeat){
  if(on() && _ov && (src==='rail' || src==='key')){ ovLeave(null); return; }      /* (‹ › from the whole view: back down to the events) */
  if(!on() || _ov) return;
  var KK=window._altoLanesKids; if(typeof dir==='number' && KK && KK.step && KK.step(dir)) return;      // (inside a branch set out as an outline: through it, lanes.py kidStep)
  /* an enlarged card (Luke, 2026-11-13: "make sure user can enlarge nodes in horizontal timeline"): the rail and ← → hop it along the stops */
  var fid=window._focusedNodeId; if(fid && typeof dir==='number'){ var nx=neighbour(fid, dir); if(nx && window.enterFocus) window.enterFocus(nx); return; }
  if(_busy){ if(repeat ? !_q.length : _q.length<QMAX) _q.push([dir,src]); return; }
  run(dir, src);
}
function run(dir, src){
  var from=current(), nx=null;
  if(typeof dir==='string') nx=dir;
  else if(M.raf && !M.gl && M.pth && M.pth.ids.length){       // mid-travel: the next event ahead of the camera that way
    var U=M.pth.U, I=M.pth.ids, k;
    if(dir>0){ for(k=0;k<U.length && !nx;k++) if(U[k]>M.u+1) nx=I[k]; if(!nx) nx=I[I.length-1]; }
    else { for(k=U.length-1;k>=0 && !nx;k--) if(U[k]<M.u-1) nx=I[k]; if(!nx) nx=I[0]; }
  }
  else nx=from ? neighbour(from, dir) : stops().ids[dir>0?0:stops().ids.length-1];
  if(nx && from && typeof dir==='number'){                      // a step that would rest on the view it is already in goes on to the next one
    var cf=camFor(from), ct=camFor(nx), n2;
    while(Math.abs(cf.l-ct.l)<.5 && Math.abs(cf.t-ct.t)<.5 && (ct.l<.5 || ct.l>ct.ml-.5) && (n2=neighbour(nx, dir))){ nx=n2; ct=camFor(nx); }
  }
  if(!nx){ if(from && (from!==_cur || moved(cv()))) glideTo(from,{step:true}); return; }      // the end: rest on the last one
  de.classList.add('ln-stepped');
  _busy=true;
  glideTo(nx, {step:true}, function(){ _busy=false; var q=_q.shift(); if(q) run(q[0], q[1]); });
  if(src==='key') focusCard(nx);
}
window._altoLanesStep=function(d){            // (the keys that used to do these, Home and End, are gone: the arrows only)
  if(d==='first'){ lnReset(); step(stops().ids[0],'api'); return; }
  if(d==='last'){ lnReset(); var S=stops().ids; step(S[S.length-1],'api'); return; }
  step(d,'api'); };       // for tests and the rail
window._altoLanesCurrent=function(){ return current(); };
window._altoLanesTravel=function(){ return M.pth ? {u:M.u, end:M.pth.end, U:M.pth.U.slice(), ids:M.pth.ids.slice(), P:M.pth.P.map(function(q){ return [Math.round(q[0]),Math.round(q[1])]; }), moving:!!M.raf, settling:!!(M.gl && M.gl.settle)} : null; };   // for tests
function focusCard(id){
  var c=document.querySelector('#node-'+id+' .node-card'); if(!c) return;
  if(!c.hasAttribute('tabindex')) c.setAttribute('tabindex','0');
  try{ c.focus({preventScroll:true}); }catch(e){}
}

/* ── the stops in the engine's own hops (an enlarged card's ← / →) ─────────── */
var _navPrev=window._altoLanesNav;
window._altoLanesNav=function(id, dir){
  if(!geo() || de.classList.contains('mobile')) return null;
  var KK=window._altoLanesKids, kt=(KK && KK.nav) ? KK.nav(id, dir) : undefined;      /* (a branch's own rules first: lanes.py kidNav) */
  if(kt!==undefined) return kt;
  var r=(dir==='e'||dir==='w') ? neighbour(id, dir==='e'?1:-1) : (_navPrev ? _navPrev(id, dir) : null);
  if(r && window._focusedNodeId){ setCur(r); _trust=true; ui(r,0); }     // the engine is hopping the enlarged card there
  return r;
};

/* ── keys ──────────────────────────────────────────────────────────────── */
/* Luke (L-1114-focus): "I only want the arrow keys to do something on the keyboard, no other keys should come into play." On the board
   ← → step along the line, ↑ ↓ move between lanes; Esc, + / − / 0, Space, Page keys, Home / End, Enter, Shift, Ctrl / ⌘ do nothing here
   (typing in a text field, and the pop-ups' own keys, are untouched). A modified arrow, or ⌘ / Ctrl with a zoom key, is swallowed too:
   no modifier changes what a key does, and the browser's page zoom never takes it. Registered on window so it is ahead of the engine's. */
function panelsOpen(){
  return de.classList.contains('detail-open') ||
    !!document.querySelector('#notes-panel.open,#summary-wrap.open,#ef-panel.open,#bg-panel.open,#note-dialog.visible,#search-btn.expanded,#share-dialog.visible');
}
window.addEventListener('keydown', function(e){
  if(!on()) return;
  var k=e.key, ae=document.activeElement, tg=ae && ae.tagName;
  if(tg==='INPUT' || tg==='TEXTAREA' || tg==='SELECT' || (ae && ae.isContentEditable)) return;
  var arrow=(k==='ArrowRight' || k==='ArrowLeft' || k==='ArrowUp' || k==='ArrowDown'), mod=e.metaKey || e.ctrlKey || e.altKey || e.shiftKey;
  if(panelsOpen()) return;
  if(arrow && mod){ e.preventDefault(); e.stopImmediatePropagation(); return; }
  if((e.metaKey || e.ctrlKey) && (k==='+' || k==='=' || k==='-' || k==='_' || k==='0')){ e.preventDefault(); e.stopImmediatePropagation(); return; }
  return;
}, true);
document.addEventListener('keydown', function(e){
  if(!on()) return;
  var k=e.key, ae=document.activeElement, tg=ae && ae.tagName;
  if(tg==='INPUT' || tg==='TEXTAREA' || tg==='SELECT' || (ae && ae.isContentEditable)) return;
  var arrow=(k==='ArrowRight' || k==='ArrowLeft' || k==='ArrowUp' || k==='ArrowDown');
  if(panelsOpen()) return;
  if(!arrow || e.altKey) return;
  if(window._focusedNodeId) return;                                // an enlarged card: the engine's arrows step it on
  var d=null, sh=false;
  if(k==='ArrowRight') d=1; else if(k==='ArrowLeft') d=-1;
  else d=k==='ArrowUp'?'n':'s';
  if(d==null) return;
  if(_ov){ e.preventDefault(); return; }
  e.preventDefault();
  var kk=(!sh && e.isTrusted) ? KEYS[k] : null;
  if(kk){                                       // a real arrow key: a quick press steps, a held one travels (below)
    if(e.repeat) return;
    var other=K.l||K.r||K.u||K.d; K[kk]=performance.now(); holdStart();
    if(other && !KT) return;                     // the second key of a combo (↑ → …): the first one's step stands
  }
  if(d==='n'||d==='s'){ hop(d); return; }
  step(d,'key',e.repeat);
}, true);
/* held arrows (Luke, 2026-11-01: "a quick press of one of the arrow keys should navigate you to the next node in the direction you
   pressed, but a long press should smoothly navigate you along the timeline in that direction … if you long press up, down, or up and
   right … it can jump you to other lines … and smoothly navigate you that way"). A press is a step (above). Held HOLD ms, ← / →
   become travel along the line the camera is on (the wheel's own travel, ramped up to VMAX px/s, so the magnetic settle lands it on an
   event when the key goes up); ↑ / ↓ alone go on to the next line over each time the last one lands; ↑ / ↓ with ← / → hop one line
   and travel along it. Only real key events (isTrusted): a script's bare keydowns stay presses. */
var HOLD=260, VMAX=1500, RAMP=450, HOPGAP=120, KEYS={ArrowRight:'r', ArrowLeft:'l', ArrowUp:'u', ArrowDown:'d'};
var K={l:0, r:0, u:0, d:0}, KT=0, _kraf=0, _kl=0, _khop=0, _ln=null;
function lnReset(){ if(_ln){ _ln=null; _S=null; stopLoop(); M.pth=null; } }
/* the nearest event on the next line over, and that line becomes the one the travel follows */
function hop(d){
  if(_busy) return false;
  var from=current(), nx=from && _navPrev ? _navPrev(from, d) : null; if(!nx) return false;
  var lid=(L.ev[nx] && L.ev[nx].l) || 'main', nl=(lid==='main' || !lineDef(lid)) ? null : lid;
  if(nl!==_ln){ _ln=nl; _S=null; stopLoop(); M.pth=null; }
  step(nx,'key'); return true;
}
function holdStart(){ if(!_kraf){ _kl=0; _kraf=requestAnimationFrame(holdTick); } }
function holdClear(){ K.l=K.r=K.u=K.d=0; endTravel(); if(_kraf){ cancelAnimationFrame(_kraf); _kraf=0; } }
function holdTick(now){
  _kraf=0;
  if(!K.l && !K.r && !K.u && !K.d){ KT=0; return; }
  if(!on() || _ov || window._focusedNodeId || busyElsewhere()){ holdClear(); return; }
  var h=(K.r?1:0)-(K.l?1:0), v=(K.d?1:0)-(K.u?1:0), ht=h>0 ? K.r : K.l, vt=v>0 ? K.d : K.u;
  if(v && !h && now-vt>=HOLD && !_busy && now-_khop>=HOPGAP){ if(hop(v>0?'s':'n')) _khop=now; }
  if(h && now-ht>=HOLD){
    if(!KT) KT=now;
    if(!_busy){ if(!M.hv) prepare(false); M.hv=h*VMAX*Math.min(1,(now-KT)/RAMP)/1000; M.dir=h; M.input=now; wake(); } else M.hv=0;
  } else if(!h){ endTravel(); }
  _kl=now; _kraf=requestAnimationFrame(holdTick);
}
/* the key goes up: not a stop and a fresh start (a settle waits for stillness) but ONE ease-out from the speed the camera has to the
   first event at or beyond where braking would end (about 0.3 s of travel on), 0.5 to 0.7 s, speed never near 0 before it arrives (Art) */
function endTravel(){
  KT=0; if(!M.hv) return; M.hv=0;
  var v=M.vel, a=Math.abs(v), p=M.pth; if(!p || !p.ids.length || a<.2){ M.input=performance.now(); return; }       // slow: the ordinary settle
  var dir=v>0?1:-1, U=p.U, I=p.ids, goal=M.u+dir*a*300, k, id=null;
  if(dir>0){ for(k=0;k<U.length;k++) if(U[k]>=goal){ id=I[k]; break; } if(!id) id=I[I.length-1]; }
  else { for(k=U.length-1;k>=0;k--) if(U[k]<=goal){ id=I[k]; break; } if(!id) id=I[0]; }
  var D=Math.abs(U[stopIx(id)]-M.u); M.uT=M.u; M.pend.length=0;
  glideTo(id, {settle:true, ms:Math.max(500, Math.min(700, 2*D/a)), hv:D>1 ? v : 0});
  if(M.gl) M.gl.s0=M.last;            // the glide starts at the last frame, so the frame after key-up already moves (s0 = the key event's time was ahead of that frame: one frame at rest)
}
document.addEventListener('keyup', function(e){ var kk=KEYS[e.key]; if(!kk) return; K[kk]=0; if(!K.l && !K.r) endTravel(); }, true);
window.addEventListener('blur', holdClear);
/* Tab onto a card: the camera goes to it the same way (not the browser's jump) */
var _tabAt=null;
document.addEventListener('keydown', function(e){ if(e.key==='Tab'){ var c=cv(); _tabAt=c?[c.scrollLeft,c.scrollTop,performance.now()]:null; } }, true);
document.addEventListener('focusin', function(e){
  if(!on() || _ov || window._focusedNodeId) return;
  var n=e.target && e.target.closest && e.target.closest('#world .node[data-ln]'); if(!n) return;
  var id=n.id.slice(5), c=cv();
  if(id===_cur || !_tabAt || performance.now()-_tabAt[2]>500) return;    // only Tab: a click's focus is the engine's to enlarge
  c.scrollLeft=_tabAt[0]; c.scrollTop=_tabAt[1];                        // undo the browser's jump, then glide
  _tabAt=null; cancelAll(); step(id,'tab');
});

/* ── the wheel: travel ────────────────────────────────────────────────────
   Every wheel event is travel along the path, as far as it says: a trackpad's
   stream (and its inertia tail, which is only more, smaller events) moves the
   camera one for one, a mouse's notch moves a NOTCH-sized share of the gap to the
   next event, chased smoothly (TAU_CHASE). Nothing is swallowed and nothing waits
   its turn. When it all stops, the settle takes the camera to an event. A stream
   keeps the axis it started on (a horizontal swipe's wobble is not travel back),
   and up and down are the same travel as across: the camera's height is the path's. */
var WH={last:-1e9, ax:null, sx:0, sy:0, cand:null};
function notch(s){
  var p=M.pth; if(!p || p.U.length<2) return 120;
  var U=p.U, i=seg(M.uT); if(s<0 && M.uT<=U[i]+.5 && i>0) i--;
  var L=U[i+1]-U[i]; for(var j=i+1; L<MINSEG && j<U.length-1; j++) L+=U[j+1]-U[j];      // (events at one view count as one)
  return Math.min(NOTCH_MAX, Math.max(NOTCH*L, Math.min(NOTCH_MIN, .6*L)));
}
/* Safari's mouse wheel: whole multiples of 4.000244… px (a trackpad's are not) */
function sfNotch(a){ var k=Math.round(a/SFN); return k>=1 && Math.abs(a-k*SFN)<1e-4 && Math.abs(a-Math.round(a))>1e-4; }
function onWheel(e, forced){
  if(!on() || ((e.ctrlKey || e.metaKey) && !forced)) return;
  if(window._focusedNodeId) return;                         // an enlarged card: the engine's swipe hops (along the stops)
  if(_ov){ ovWheel(e); return; }
  if(busyElsewhere()) return;
  lnReset();
  e.preventDefault();                                       // the camera stays on the path: no free scroll
  if(M.drag) return;
  var m=e.deltaMode===1?40:e.deltaMode===2?800:1, dx=e.deltaX*m, dy=e.deltaY*m, now=performance.now();
  var gap=now-WH.last; WH.last=now;
  /* a trackpad's up and down moves the view up and down when the lanes do not all fit; a mouse's notch, or lanes that all fit, go along the line */
  var big=Math.max(Math.abs(dx),Math.abs(dy)), mouse=!!e.deltaMode || sfNotch(big) || (gap>=LONE && big>=40 && big===Math.round(big) && !(dx && dy));
  var mt0=cv().scrollHeight-cv().clientHeight;
  if(!phone() && !mouse && dy && mt0>1){
    var k0=zk(cv()); M.vy=Math.max(0,Math.min(mt0,(M.vy!=null ? M.vy : cv().scrollTop)+dy/k0)); dy=0;
    if(!M.pth) resync();
    M.input=now; wake(); if(!dx) return;                      // (the camera along the line is not touched by an up and down)
  }
  if(gap>GESTURE){ WH.ax=null; WH.sx=WH.sy=0; }
  WH.sx+=Math.abs(dx); WH.sy+=Math.abs(dy);
  if(!WH.ax && WH.sx+WH.sy>=4) WH.ax=WH.sx>=WH.sy ? 'x' : 'y';
  var d=WH.ax==='x' ? dx : WH.ax==='y' ? dy : (Math.abs(dx)>=Math.abs(dy) ? dx : dy);
  if(!d) return;
  prepare(false);
  var a=Math.abs(d), s=d>0?1:-1;
  var soft=false;
  if(e.deltaMode){ d=s*Math.max(a, notch(s)); soft=true; }                          // lines or pages: a notch
  else if(sfNotch(a)){ d=s*notch(s)*Math.min(3, 1+.35*(Math.round(a/SFN)-1)); soft=true; }   // Safari's notch (faster spins: bigger)
  else if(gap>=LONE){
    /* on its own (nothing within LONE ms) it was a mouse's notch: a notch's worth, however
       big its delta. Until that is known it moves at most a notch; a stream gets the rest */
    var n0=notch(s), me=WH.cand={t:now, a:a, s:s, held:Math.max(0,a-n0)};
    d=s*Math.min(a,n0); soft=a>SOFT;
    setTimeout(function(){ if(WH.cand===me && WH.last===me.t){ WH.cand=null; if(!M.pth) return; if(n0>me.a) addTravel(me.s*(n0-me.a), true); } }, LONE+5);
  } else if(WH.cand){ if(WH.cand.held && WH.cand.s===s) d+=s*WH.cand.held; WH.cand=null; }
  addTravel(d, soft);
}
/* only the canvas holds the wheel: everywhere else Safari keeps scrolling off the main thread */
function hookWheel(){ var c=cv(); if(!c || c._lnWheel) return; c._lnWheel=1; c.addEventListener('wheel', onWheel, {passive:false}); }
/* editing: the old free scroll, a mouse wheel going sideways (shift: up and down) */
document.addEventListener('wheel', function(e){
  if(!geo() || !de.classList.contains('alto-editing') || e.ctrlKey || e.metaKey || e.deltaX) return;
  var c=cv(); if(!c || !c.contains(e.target) || c.classList.contains('focus-mode')) return;
  if(e.shiftKey){ c.scrollTop+=e.deltaY; e.preventDefault(); return; }
  if(e.deltaMode===0 && Math.abs(e.deltaY)<40) return;      // a trackpad scrolls both ways by itself
  c.scrollLeft+=e.deltaY*(e.deltaMode===1?40:1); e.preventDefault();
}, {passive:false});

/* ── a drag (mouse, pen, a touch screen): the board follows the hand along the path ──
   A hand on the board stops the camera where it is. Dragging the background moves
   it along the path (the hand's across movement, or its up and down if that is how
   it set off); let go with speed and it coasts (TAU_FLING), then settles. The
   engine's own free pan never sees the drag. */
var DR=null, _noClick=0, _pn={};                             // _pn: the pointers down on the board (a second finger is a pinch, never a second drag)
function pnCount(){ var n=0; for(var k in _pn) n++; return n; }
function dragStop(){ if(!DR) return; DR=M.drag=null; var c=cv(); if(c) c.classList.remove('ln-drag'); M.input=performance.now(); if(!_ov) wake(); }   // no fling, no click-suppression: the hand became two
document.addEventListener('pointerdown', function(e){
  var c=cv(); if(c && c.contains(e.target) && e.pointerType!=='mouse'){ _pn[e.pointerId]=1; if(pnCount()>1){ dragStop(); _gzUntil=performance.now()+600; } }
  if(!c || !c.contains(e.target) || e.button>0) return;
  if(pnCount()>1 || _zg) return;                             // two fingers: the pinch's (zoom, below), not a travel drag
  if(!on() || _ov || window._focusedNodeId || busyElsewhere()) return;
  var r=c.getBoundingClientRect(), k=zk(c);
  if((e.clientX-r.left)/k>c.clientWidth || (e.clientY-r.top)/k>c.clientHeight) return;         // the scrollbars
  /* the background (a finger or a pen may set off from a card too: a tap is still a tap) */
  var bg=!(e.target.closest && e.target.closest((e.pointerType==='mouse' ? '.node-card,' : '')+'.lanes-tag,button,a,input,textarea,select,[contenteditable="true"]'));
  if(!bg){ if(M.raf){ prepare(true); M.input=performance.now(); } return; }   // a card: held still; its click enlarges it, or the settle goes on
  lnReset(); prepare(true);
  DR=M.drag={id:e.pointerId, x:e.clientX, y:e.clientY, lx:e.clientX, ly:e.clientY, moved:false, ax:null, smp:[]};
  M.input=performance.now(); wake();
}, true);
window.addEventListener('pointermove', function(e){
  if(!DR || e.pointerId!==DR.id || pnCount()>1 || _zg) return;
  var k=zk(cv()), tx=(e.clientX-DR.x)/k, ty=(e.clientY-DR.y)/k, now=performance.now();
  if(!DR.moved){ if(Math.abs(tx)+Math.abs(ty)<5) return; DR.moved=true; DR.ax=Math.abs(tx)>=.7*Math.abs(ty) ? 'x' : 'y'; cv().classList.add('ln-drag'); }
  var d, free=!phone() && M.pth && M.pth.mt>0;
  if(free){ d=-(e.clientX-DR.lx)/k; var dv=-(e.clientY-DR.ly)/k; if(dv) M.vy=Math.max(0,Math.min(M.pth.mt,(M.vy!=null ? M.vy : cv().scrollTop)+dv)); }   // free: across along the line, up and down as far as the lanes go
  else d=DR.ax==='x' ? -(e.clientX-DR.lx)/k : -(e.clientY-DR.ly)/k;
  DR.lx=e.clientX; DR.ly=e.clientY;
  if(d){ M.dir=d>0?1:-1; setU(M.u+d); }
  DR.smp.push([now, M.u]); while(DR.smp.length>2 && DR.smp[0][0]<now-90) DR.smp.shift();
  M.input=now; wake();
}, true);
function dragEnd(e, fling){
  if(!DR || e.pointerId!==DR.id) return;
  var d=DR, now=performance.now(); DR=M.drag=null; cv().classList.remove('ln-drag');
  if(d.moved){
    _noClick=now;                                            // the drag's mouseup is not a click on what is under it
    var s=d.smp, a=s[0], b=s[s.length-1];
    if(fling && !reduced() && s.length>=2 && now-b[0]<60){ var v=(b[1]-a[1])/Math.max(16,b[0]-a[0]); if(Math.abs(v)>FLING_MIN && coast(Math.max(-FLING_MAX,Math.min(FLING_MAX,v)))) return; }
  }
  M.input=now; wake();
}
/* let go with speed: coast on to the event the throw reaches (where TAU_FLING of the speed
   would carry it, leaning the throw's way), slowing from the hand's own speed to rest on it
   (an ease-out whose first frame goes as fast as the hand did) */
function coast(v){
  var dir=v>0?1:-1, id=pick(clampU(M.u+v*TAU_FLING), dir), k=stopIx(id);
  if(k<0) return false;
  var D=M.pth.U[k]-M.u; if(D*v<=0 || Math.abs(D)<2) return false;
  var ms=Math.max(260, Math.min(1100, COAST_PW*D/v));
  M.dir=dir; glideTo(id, {settle:true, ms:ms, pw:Math.max(1.6, Math.min(4, v*ms/D))});
  return true;
}
window.addEventListener('pointerup', function(e){ delete _pn[e.pointerId]; dragEnd(e, true); }, true);
window.addEventListener('pointercancel', function(e){ delete _pn[e.pointerId]; dragEnd(e, false); }, true);
/* the engine's free pan reads the mouse's moves on window: not while the path has the hand */
window.addEventListener('mousemove', function(e){ if(DR) e.stopPropagation(); }, true);
document.addEventListener('click', function(e){ if(_noClick && performance.now()-_noClick<400 && cv() && cv().contains(e.target)){ _noClick=0; e.stopImmediatePropagation(); e.preventDefault(); } }, true);

/* cards gliding under a still pointer are not pointed at (the engine's hover asks the
   same; here it keeps lanes.py from isolating whichever line slides under it) */
document.addEventListener('mouseover', function(e){
  if(on() && window._altoPointerStill && window._altoPointerStill(e) && cv() && cv().contains(e.target)) e.stopPropagation();
}, true);

/* clicking a card enlarges it (the engine, on the same curve); the steps go on from it */
document.addEventListener('click', function(e){
  if(!on() || _ov) return;
  var n=e.target.closest && e.target.closest('#world .node[data-ln]'); if(!n) return;
  cancelAll(); setCur(n.id.slice(5)); _trust=true;
}, true);
/* lines picked or let go (lanes.py setPick, after its new layout): the steps visit only what is shown — from an
   event that left the board, on to the next one still on it */
document.addEventListener('alto:lanes-pick', function(){
  if(!on()) return;
  invalidate(); var from=current(); ui(from,0);
  if(_ov || !from || live(from)) return;
  var S=stops(), oi=S.at[from], nx=null;
  for(var i=0;i<S.ids.length && !nx;i++) if(S.at[S.ids[i]]>oi) nx=S.ids[i];
  nx=nx||S.ids[S.ids.length-1];
  if(nx){ cancelAll(); step(nx,'line'); }
});
/* an enlarged card's own hops and exits move the steps along with it */
var _lastFocus=null;
var _pre=null;
function watchFocus(){
  var c=cv(); if(!c || c._lnObs || !window.MutationObserver) return; c._lnObs=1;
  new MutationObserver(function(){
    /* (an enlarged card no longer hides the rail: it steps the enlarged card, and the card keeps clear of it, engine_patches enlarge-safe-box) */
    if(c.classList.contains('focus-mode')){ if(M.raf || _busy) cancelAll(); if(window._focusedNodeId){
      if(_lastFocus && _lastFocus!==window._focusedNodeId) _pre=null;                // stepped on to another card: no "where it was" to go back to
      else if(!_lastFocus && !_pre) _pre={id:window._focusedNodeId, l:c.scrollLeft, t:c.scrollTop};
      _lastFocus=window._focusedNodeId; setCur(_lastFocus); _trust=true; ui(_lastFocus,0); } }
    else if(_lastFocus){ setCur(_cur||_lastFocus); _trust=true; _lastFocus=null;
      /* closing the card puts the line exactly where it was (the enlarging may leave it a pixel or two off) */
      if(_pre){ var q=_pre; _pre=null; if(Math.abs(c.scrollLeft-q.l)<=6 && Math.abs(c.scrollTop-q.t)<=6){ axis('scrollLeft').go(q.l); axis('scrollTop').go(q.t); _land=[c.scrollLeft,c.scrollTop]; M.pth=null; } } }
  }).observe(c,{attributes:true, attributeFilter:['class']});
}

/* ── the rail ──────────────────────────────────────────────────────────── */
var R=null, MMK='alto-lanes-mm:'+location.pathname, MMON=true;      /* (the minimap's on / off, per page: see mmSwitch) */
try{ MMON=localStorage.getItem(MMK)!=='0'; }catch(e){}
function svgI(d){ return '<svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+d+'</svg>'; }
function buildRail(){
  if(R || de.classList.contains('mobile')) return;
  var n=document.createElement('div'); n.id='lanes-nav'; n.setAttribute('role','navigation'); n.setAttribute('aria-label','Go through the timeline');
  n.innerHTML='<button type="button" class="lnv-ov" aria-pressed="false" title="'+OV_T+'" aria-label="'+OV_T+'">'
    +svgI('<rect x="2.5" y="4.5" width="15" height="11" rx="2"/><path d="M5.5 10h9M7 7.5h2M11 12.5h2"/>')+'</button>'
    +'<button type="button" class="lnv-prev" title="Previous event (←)" aria-label="Previous event">'+svgI('<path d="M12 5l-5 5 5 5"/>')+'</button>'
    +'<div class="lnv-mid"><div class="lnv-txt"><span><b class="lnv-n">1</b> / <span class="lnv-N">1</span></span><span class="lnv-tag"></span></div>'
    +'<div class="lnv-rail" title="Drag to look along the timeline"><i class="lnv-thumb" role="slider" tabindex="0" aria-label="Where you are in the story"></i></div></div>'
    +'<button type="button" class="lnv-next" title="Next event (→)" aria-label="Next event">'+svgI('<path d="M8 5l5 5-5 5"/>')+'</button>'
    +'<button type="button" class="lnv-map">'+svgI('<rect x="3" y="4.5" width="14" height="11" rx="2"/><circle cx="7.5" cy="9" r="1.2"/><circle cx="12.5" cy="11.5" r="1.2"/><path d="M8.5 9.6 11.5 11"/>')+'</button>'
    +'<span class="lnv-sr" aria-live="polite"></span>';
  document.body.appendChild(n);
  R={el:n, n:n.querySelector('.lnv-n'), N:n.querySelector('.lnv-N'), tag:n.querySelector('.lnv-tag'), rail:n.querySelector('.lnv-rail'),
     thumb:n.querySelector('.lnv-thumb'), ov:n.querySelector('.lnv-ov'), prev:n.querySelector('.lnv-prev'), next:n.querySelector('.lnv-next'), sr:n.querySelector('.lnv-sr')};
  R.prev.addEventListener('click', function(){ step(-1,'rail'); });
  R.next.addEventListener('click', function(){ step(1,'rail'); });
  R.ov.addEventListener('click', function(){ if(!_ov) ovEnter(); });      /* (opens the whole view only: Esc, a tap on the board or ‹ › come back) */
  R.map=n.querySelector('.lnv-map'); mmSwitch(); R.map.addEventListener('click', function(){ MMON=!MMON; try{ localStorage.setItem(MMK, MMON ? '1' : '0'); }catch(e){} mmSwitch(); mmDraw(); });
  R.thumb.addEventListener('keydown', function(e){
    var d=e.key==='ArrowRight'||e.key==='ArrowUp'?1:e.key==='ArrowLeft'||e.key==='ArrowDown'?-1:0;
    if(d){ e.preventDefault(); e.stopPropagation(); step(d,'rail',e.repeat); }
  });
  scrubber();
}
function railFrac(i, N){ return N>1 ? i/(N-1) : 0; }
function railMarks(){
  if(!R) return;
  R.rail.querySelectorAll('.lnv-fb').forEach(function(x){ x.remove(); });
  var S=stops(), N=S.ids.length;
  (L.flashbacks||[]).forEach(function(fb){
    var ix=(fb.nodes||[]).map(function(id){ return S.ids.indexOf(id); }).filter(function(i){ return i>=0; });
    if(!ix.length) return;
    var a=railFrac(Math.min.apply(null,ix),N), b=railFrac(Math.max.apply(null,ix),N), m=document.createElement('i');
    m.className='lnv-fb'; m.style.left=(a*100)+'%'; m.style.width='calc('+((b-a)*100)+'% + 4px)'; m.style.marginLeft='-2px'; m.title=fb.label||'';
    R.rail.insertBefore(m, R.thumb);
  });
}
/* the rail says which event the camera is on (or nearest, travelling); the thumb is where it is */
function ui(id, ms){
  if(!R) return;
  var S=stops(), N=S.ids.length, i=S.ids.indexOf(id), pos=i;
  if(i<0 && id!=null){ var oi=S.at[id]; pos=-1; for(var k=0;k<N;k++) if(S.at[S.ids[k]]<oi) pos=k; }
  R.n.textContent=i>=0 ? String(i+1) : (pos>=0 ? (pos+1)+'+' : '–'); R.N.textContent=String(N);
  var fb=id && flashOf(id), ev=id && L.ev[id], ln=ev && ev.l!=='main' ? lineDef(ev.l) : null, c=picks(), tag='';
  if(c.length){ tag=c.length<3 ? c.map(function(k){ return (lineDef(k)||{}).label||''; }).join(' + ') : c.length+' lines';
         R.tag.innerHTML=''; R.tag.textContent=tag+' only'; var x=document.createElement('button'); x.type='button'; x.textContent='✕'; x.title='Show all lines (Esc)'; x.setAttribute('aria-label','Show all lines');
         x.addEventListener('click', function(e){ e.stopPropagation(); if(window._altoLanesPick) window._altoLanesPick([]); }); R.tag.appendChild(x); }
  else { tag=fb ? fb.label : (ln ? ln.label+' · off the page' : ''); R.tag.textContent=tag; }
  R.tag.style.color=c.length===1 ? (lineDef(c[0])||{}).color||'' : (c.length ? '' : (ln ? ln.color : ''));
  R.prev.disabled=!(N && (i>0 || (i<0 && pos>=0))); R.next.disabled=!(N && (i<N-1 || (i<0 && pos<N-1)));
  var f=railFrac(Math.max(0,i>=0?i:pos+.5), N), w=R.rail.clientWidth;
  if(M.raf) return;                                          // travelling: the thumb goes with the camera (thumb())
  R.thumb.style.transition=ms ? 'transform '+ms+'ms cubic-bezier(.25,.2,.4,1)' : 'none';
  R.thumb.style.transform='translateX('+(f*w).toFixed(2)+'px)';
  R.thumb.setAttribute('aria-valuemin','1'); R.thumb.setAttribute('aria-valuemax',String(N)); R.thumb.setAttribute('aria-valuenow',String(Math.max(1,(i>=0?i:pos)+1)));
}
function announce(id){ if(!R || !id) return; var S=_S||stops(), i=S.ids.indexOf(id), ev=L.ev[id]||{}, fb=flashOf(id);
  R.sr.textContent=(i>=0?'Event '+(i+1)+' of '+S.ids.length+': ':'')+title(id)+(ev.w?', '+ev.w:'')+(fb?' — '+fb.label:''); }
/* the thumb is the grab handle: drag it to look along the timeline freely, let go to settle on the nearest event */
function scrubber(){
  var sc=null;
  function at(e){ var r=R.rail.getBoundingClientRect(); return Math.max(0,Math.min(1,(e.clientX-r.left)/(r.width||1))); }
  function look(f){                                       // along the path, as travel is
    var S=M.pth.ids, U=M.pth.U, N=S.length; if(!N) return;
    var fi=f*(N-1), a=Math.floor(fi), b=Math.min(N-1,a+1);
    setU(U[a]+(U[b]-U[a])*(fi-a)); M.input=performance.now(); wake();
    sc.f=f;
  }
  R.rail.addEventListener('pointerdown', function(e){
    if(!on() || e.button>0) return; e.preventDefault();
    if(_ov) ovLeave(null, true);
    _q.length=0; _busy=false; prepare(true); M.drag={rail:1};
    sc={S:M.pth.ids, x:e.clientX, moved:false, f:at(e), id:e.pointerId};
    try{ R.rail.setPointerCapture(e.pointerId); }catch(er){}
    if(e.target===R.thumb){ sc.moved=true; R.el.classList.add('scrub'); }
  });
  R.rail.addEventListener('pointermove', function(e){
    if(!sc || e.pointerId!==sc.id) return;
    if(!sc.moved && Math.abs(e.clientX-sc.x)<4) return;
    sc.moved=true; R.el.classList.add('scrub'); look(at(e));
  });
  function end(e){
    if(!sc || (e && e.pointerId!==sc.id)) return;
    var f=sc.moved ? sc.f : at(e), S=sc.S, i=Math.round(f*(S.length-1)); sc=null; M.drag=null; R.el.classList.remove('scrub');
    if(S[i]) step(S[i],'rail');
  }
  R.rail.addEventListener('pointerup', end);
  R.rail.addEventListener('pointercancel', function(){ sc=null; M.drag=null; M.input=performance.now(); wake(); R.el.classList.remove('scrub'); });
}

/* ── the whole timeline ─────────────────────────────────────────────────── */
var _ov=null, _ovA=null;
function ovSet(o){
  var w=document.getElementById('world'), c=cv(), off=worldOff(c);
  w.style.transform='translate('+(o.tx-off.x)+'px,'+(o.ty-off.y)+'px) scale('+o.s+')';
  ovSlab(o); ovMarks(o);
}
/* The overview (F9, 2026-11-27: "make it really show the whole line on screen ... keeping text legible (or switching to an overview treatment)").
   Shrunk until a card's title would read under ~9px: where a card is still wide enough to hold one (OV_TW px on screen) only its title stays,
   drawn at a reading size (--ovtf) and clipped to the card; narrower still, the cards become plain blocks in their places (Board, 2026-11-27:
   "keep the real cards (titles at least) whenever the scale allows"). The lines keep their drawn width; each unit keeps its label at reading
   size: its name, or its numeral where the stretch is short, and where numerals would touch they step off the line, above and below by turns
   (no unit's label is ever dropped). A tap still goes down to the event there. */
var OV_TW=56;
function ovMarks(o){
  var c=cv(), w=document.getElementById('world'); if(!c || !w) return;
  var k=o && o.s<1 ? o.s*zk(c) : 1, tt=w.querySelector('.node:not(.ln-kid) .node-card .node-title'), fs=(c.classList.contains('ln-ovtt') && w._lnFs) || (tt ? parseFloat(getComputedStyle(tt).fontSize)||16 : 16);
  if(!c.classList.contains('ln-ovtt')) w._lnFs=fs;      /* (the card's own title size: while the overview shows titles they wear its size, not theirs) */
  var cw=(w.querySelector('.node:not(.ln-kid) .node-card')||{}).offsetWidth||260;
  var mk=!!o && o.s<1 && fs*k<9, tl=mk && cw*k>=OV_TW;
  c.classList.toggle('ln-ovmk', mk); c.classList.toggle('ln-ovtt', tl);
  if(!mk){ w.style.removeProperty('--ovk'); w.style.removeProperty('--ovtf'); w.querySelectorAll('.node .node-card').forEach(function(cd){ cd._lnH=null; }); return; }      /* (measured afresh next time: the board may have changed) */
  w.style.setProperty('--ovk', (1/o.s).toFixed(5));
  if(tl){ var fw=9.5/k; w.style.setProperty('--ovtf', fw.toFixed(2)+'px');
    /* whole lines only: as many as 80% of each block's height holds at that size */
    w.querySelectorAll('.node .node-card').forEach(function(cd){ if(cd._lnH==null) cd._lnH=cd.offsetHeight; var n=Math.max(1, Math.floor(cd._lnH*0.8/(fw*1.15)));
      if(cd._lnTl!==n){ cd._lnTl=n; cd.style.setProperty('--ovtl', n); } }); }
  var put=[[],[],[]], gap=6;
  w.querySelectorAll('#lanes-ulabels .lu-strip').forEach(function(st){
    var ch=st.firstElementChild; if(!ch) return;
    if(ch._lnNat==null){ ch._lnNat=ch.offsetWidth; ch._lnH=ch.offsetHeight; var b=ch.querySelector('b'); ch._lnNum=(b ? b.offsetWidth : 0)+22; }
    var sw=(parseFloat(st.style.width)||0)*o.s, room=sw-8, n=room<ch._lnNat, cwid=n ? ch._lnNum : ch._lnNat;
    var x0=(parseFloat(st.style.left)||0)*o.s, x1=x0+cwid, row=0;
    for(var r=0;r<3;r++){ var ok=put[r].every(function(q){ return x0>=q[1]+gap || x1<=q[0]-gap; }); if(ok){ row=r; break; } row=r; }
    put[row].push([x0,x1]);
    var dy=row===0 ? 0 : (row===1 ? -1 : 1)*(ch._lnH+6);
    if(ch._lnMk!==(n?'n':'')+row){ ch._lnMk=(n?'n':'')+row; ch.classList.toggle('lu-ovn', n); }
    ch.style.setProperty('--lu-dy', (dy/o.s).toFixed(2)+'px');
  });
}
/* The glass slab is the timeline's own backdrop. Shrunk with the board it becomes a thin
   ribbon floating on the empty page. Zoomed out, a layer of the same colours covers the
   whole window instead (the slab fades out as it fades in), so the timeline reads as one
   landscape seen from above. The slab itself is never resized: the page's height follows
   its bottom edge. The layer is fixed under the canvas, so it adds nothing to what scrolls. */
var _sky=null;
function ovSkyOn(){
  var sl=document.getElementById('glass-slab'), c=cv(); if(!sl || !c || _sky) return;
  _sky=document.createElement('div'); _sky.id='lanes-ov-sky'; _sky.setAttribute('aria-hidden','true');
  _sky._a=parseFloat(getComputedStyle(sl).opacity); if(!(_sky._a>0)) _sky._a=1;
  _sky.style.cssText='position:fixed;left:0;right:0;bottom:0;top:var(--nav-bottom,112px);pointer-events:none;background-repeat:no-repeat;background-image:'+sl.style.backgroundImage+';opacity:0;'
    +(reduced()?'':'transition:opacity .62s cubic-bezier(.25,.2,.4,1);');
  c.parentNode.insertBefore(_sky, c);
  if(!reduced()) sl.style.transition='opacity .62s cubic-bezier(.25,.2,.4,1)';
  void _sky.offsetWidth; _sky.style.opacity=String(_sky._a); sl.style.opacity='0';
}
function ovSkyFade(){ var sl=document.getElementById('glass-slab'); if(_sky) _sky.style.opacity='0'; if(sl) sl.style.opacity=''; }
function ovSlab(o){
  var sl=document.getElementById('glass-slab'), c=cv();
  if(!o || o.s>=0.999){ if(_sky){ _sky.remove(); _sky=null; } if(sl){ sl.style.opacity=''; sl.style.transition=''; } return; }
  if(!sl || !c) return;
  if(!_sky) ovSkyOn();
  // a gap left or right of the board is covered by stretching the colours to the window's edge. The window's, not the canvas's: on a phone on its side the canvas
  // sits between the Dynamic Island's insets (phone_shell.py) and the layer runs under them, so the canvas's own offset in the layer is counted
  // (the slab, whose colours these are, runs on past the board through the canvas's side padding on a phone on its side: lanes.py slabX())
  var e0=-(parseFloat(sl.style.left)||0), W=(parseFloat(sl.style.width)||geo().W)*o.s, sr=_sky.getBoundingClientRect(), off=c.getBoundingClientRect().left-sr.left, x=off+o.tx-e0*o.s, gl=Math.max(0,x), gr=Math.max(0,(sr.width||c.clientWidth)-(x+W));
  _sky.style.backgroundSize=(W+gl+gr).toFixed(1)+'px 100%'; _sky.style.backgroundPositionX=Math.min(0,x).toFixed(1)+'px';
}
/* the canvas's own side padding (a phone on its side: the Dynamic Island's insets, phone_shell.py): the board is fitted and held between them, the ground and the lines run under them */
function ins(c){ var q=getComputedStyle(c); return {l:parseFloat(q.paddingLeft)||0, r:parseFloat(q.paddingRight)||0}; }
function ovFit(){
  var c=cv(), G=geo(), B=band(c), cw=c.clientWidth, P=PAD(), H=G.H+P, I=ins(c);
  var s=Math.min(1,(cw-60-I.l-I.r)/G.W,(B.b-B.t-16)/H);   /* the whole line, always (no floor: a long one on a phone ran off the edge, F9 1127); too small to read, it is drawn as the overview below */
  var tx=cw/2-(c.scrollLeft+cw/2-worldOff(c).x)*s;          // what is in the middle now stays in the middle
  var ty=H*s<=B.b-B.t ? B.t+(B.b-B.t-H*s)/2 : B.t;
  return ovClampX({s:s, tx:tx, ty:ty});
}
function ovClampX(o){ var c=cv(), cw=c.clientWidth, Wd=geo().W*o.s, I=ins(c); o.tx=Wd<=cw-I.l-I.r ? I.l+(cw-I.l-I.r-Wd)/2 : Math.max(cw-Wd-30-I.r, Math.min(30+I.l, o.tx)); return o; }
function ovAnim(from, to, done){
  if(_ovA) cancelAnimationFrame(_ovA);
  var c=cv(); c.classList.add('ln-ovanim');
  if(reduced()){ ovSet(to); _ovA=null; c.classList.remove('ln-ovanim'); done(); return; }
  var ms=620, s0=performance.now();
  function fr(now){
    var p=Math.min(1,(now-s0)/ms), k=ease(p);
    /* zoom in the log of the scale, so the shrinking reads as one even movement */
    var s=Math.exp(Math.log(from.s)+(Math.log(to.s)-Math.log(from.s))*k);
    var u=(Math.abs(to.s-from.s)>1e-6) ? (s-from.s)/(to.s-from.s) : k;
    ovSet({s:s, tx:from.tx+(to.tx-from.tx)*u, ty:from.ty+(to.ty-from.ty)*u});
    if(p<1) _ovA=requestAnimationFrame(fr); else { _ovA=null; c.classList.remove('ln-ovanim'); done(); }
  }
  _ovA=requestAnimationFrame(fr);
}
function ovEnter(){ if(MM) MM.classList.remove('on');      /* (the whole timeline shows it all: the minimap steps aside) */
  if(!on() || _ov) return;
  if(window._focusedNodeId && window.exitFocus) window.exitFocus();
  cancelAll();
  var here=current(); if(here) setCur(here);                 // Esc / the toggle come back to this one
  var c=cv(), off=worldOff(c), from={s:1, tx:off.x-c.scrollLeft, ty:off.y-c.scrollTop}, to=ovFit();
  _ov=to;
  ovHold(true); ovSet(from); c.scrollLeft=0; c.scrollTop=0; c.classList.add('ln-ov');
  if(R){ R.ov.setAttribute('aria-pressed','true'); }
  ovAnim(from, to, function(){});
}
/* back down to step mode, resting on this event (null: where the steps were) */
function ovLeave(id, instant, then){ mmLater(400);
  if(!_ov) return;
  var c=cv(), from=_ov; id=id||_cur||stops().ids[0];
  if(_ovA){ cancelAnimationFrame(_ovA); _ovA=null; c.classList.remove('ln-ovanim'); }
  ovCoastStop(); _ov=null; _zg=null; c.classList.remove('ln-ov','ln-drag','ln-zin');
  if(R){ R.ov.setAttribute('aria-pressed','false'); R.ov.title=OV_T; R.ov.setAttribute('aria-label', OV_T); }
  var w=document.getElementById('world'), off=worldOff(c);
  /* where the camera will rest, worked out as if the board were at scale 1 */
  w.style.transform='none';
  var B=band(c), t=camFor(id,B), qx=axis('scrollLeft'), qy=axis('scrollTop'), tl=qx.stop(dev(t.l,t.ml)), tt=qy.stop(dev(t.t,t.mt));
  ovSet(from); ovSkyFade();
  var fin=function(){ w.style.transform=''; ovSlab(null); ovMarks(null); ovHold(false); qx.go(tl); qy.go(tt); setCur(id); _land=[c.scrollLeft,c.scrollTop]; _trust=false; ui(id,0); announce(id); if(then) then(); };
  if(instant){ fin(); return; }
  de.classList.add('ln-stepped');
  ovAnim(from, {s:1, tx:off.x-tl, ty:off.y-tt}, fin);
}
/* The scaled board no longer overflows the canvas, so where scrollbars take room (Safari
   with a mouse plugged in, "always show scrollbars") they would vanish, the canvas would
   change size and the engine would lay the whole page out again mid-zoom. A spacer the
   board's full size holds the canvas's scroll extent as it was. */
function ovHold(on){
  var c=cv(), sp=document.getElementById('lanes-ov-hold');
  if(!on){ if(sp) sp.remove(); return; }
  if(!sp){ sp=document.createElement('div'); sp.id='lanes-ov-hold'; sp.setAttribute('aria-hidden','true');
    sp.style.cssText='position:absolute;left:0;top:0;width:1px;height:1px;visibility:hidden;pointer-events:none;'; c.appendChild(sp); }
  sp.style.width=c.scrollWidth+'px'; sp.style.height=c.scrollHeight+'px';
}
/* the board is moved by its transform there, never scrolled (a scrollbar drag is undone) */
function ovNoScroll(){ var c=cv(); if(!c || c._lnOvS) return; c._lnOvS=1; c.addEventListener('scroll', function(){ if(_ov && (c.scrollLeft || c.scrollTop)){ c.scrollLeft=0; c.scrollTop=0; } }, {passive:true}); }
/* One way of moving, zoomed or not: a wheel's vertical travel is travel ALONG the line (across), a trackpad's two fingers go where
   the fingers go, Shift sends a vertical wheel up and down. A mouse notch (lines or pages, Safari's whole multiples, or a lone whole
   100) is chased smoothly like the rest view's, never a 100 px jump; a trackpad's own stream (and its inertia tail) is applied as it comes. */
var _wz={t:-1e9}, _wc=null;
function ovChase(){
  var last=performance.now();
  (function fr(now){
    var c=_wc; if(!c || !_ov){ _wc=null; return; }
    var dt=Math.max(1,Math.min(50,now-last)); last=now; var k=1-Math.exp(-dt/TAU_CHASE), mx=c.dx*k, my=c.dy*k; c.dx-=mx; c.dy-=my;
    if(Math.abs(c.dx)<.3 && Math.abs(c.dy)<.3){ mx+=c.dx; my+=c.dy; _wc=null; }
    _ov.tx-=mx; _ov.ty-=my; ovClamp(_ov); ovSet(_ov);
    if(_wc) requestAnimationFrame(fr);
  })(last);
}
function ovWheel(e){
  e.preventDefault();
  if(_ovA) return;
  var m=e.deltaMode===1?40:e.deltaMode===2?800:1, dx=e.deltaX*m, dy=e.deltaY*m, now=performance.now(), gap=now-_wz.t; _wz.t=now;
  ovCoastStop();
  var big=Math.abs(dx)>=Math.abs(dy) ? dx : dy, a=Math.abs(big);
  var notch=!!e.deltaMode || sfNotch(a) || (gap>=LONE && a>=40 && a===Math.round(a) && !(dx && dy));
  if(notch){ dx=big; dy=0; }                                                            // along the line (no modifier changes it)
  else if(!tall(_ov)){ dx=Math.abs(dy)>Math.abs(dx) ? dy : dx; dy=0; }                 // a board no taller than the window has no up and down
  if(notch && !reduced()){ var run=!_wc; if(run) _wc={dx:0,dy:0}; _wc.dx+=dx; _wc.dy+=dy; if(run) ovChase(); return; }
  _ov.tx-=dx; _ov.ty-=dy; ovClamp(_ov); ovSet(_ov);
}
/* a drag let go with speed coasts on and slows (the rest view's fling, on the board's own pan) */
var _oc=null;
function ovCoastStop(){ _oc=null; _wc=null; }
function ovCoast(vx, vy){
  if(reduced() || !_ov || Math.hypot(vx,vy)<FLING_MIN) return;
  var me=_oc={vx:vx, vy:vy}, last=performance.now();
  (function fr(now){
    if(_oc!==me || !_ov) return; var dt=Math.max(1,Math.min(50,now-last)); last=now;
    var k=Math.exp(-dt/TAU_FLING*1.6); me.vx*=k; me.vy*=k;
    var tx=_ov.tx, ty=_ov.ty; _ov.tx+=me.vx*dt; _ov.ty+=me.vy*dt; ovClamp(_ov); ovSet(_ov);
    if((Math.abs(_ov.tx-tx)<.05 && Math.abs(_ov.ty-ty)<.05) || Math.hypot(me.vx,me.vy)<.02){ _oc=null; return; }
    requestAnimationFrame(fr);
  })(last);
}
function ovPoint(cx, cy){
  var c=cv(), r=c.getBoundingClientRect(), k=zk(c), lx=(cx-r.left)/k, ly=(cy-r.top)/k, P=PAD();
  var wx=(lx-_ov.tx)/_ov.s, wy=(ly-_ov.ty)/_ov.s-P, G=geo(), best=null, bd=Infinity;
  _ovCard=null;
  Object.keys(G.x).forEach(function(id){
    if(!live(id)) return;
    var a=anchor(id), h=G.h[id]||120, top=G.y[id]-h/2, bot=G.y[id]+h/2;
    var dyc=wy<top ? top-wy : wy>bot ? wy-bot : 0, dya=Math.abs(wy-a.y);   // on the card, or near its dot on the line
    var d=Math.abs(wx-a.x)+Math.min(dyc,dya)*1.4;
    if(d<bd){ bd=d; best=id; }
    var n=document.querySelector('#node-'+id+' .node-card');
    if(!dyc && n && Math.abs(wx-G.x[id])<=n.offsetWidth/2) _ovCard=id;
  });
  return best;
}
(function(){
  var dn=null, np=0;
  document.addEventListener('pointerdown', function(e){
    if(!_ov) return; var c=cv(); if(!c || !c.contains(e.target)) return;
    e.preventDefault(); e.stopPropagation();
    np++; if(np>1 || _zg){ if(dn) dn.moved=true; dn=null; return; }        // a second finger: a pinch, not a drag
    ovCoastStop();
    dn={x:e.clientX, y:e.clientY, tx:_ov.tx, ty:_ov.ty, moved:false, id:e.pointerId, smp:[]};
  }, true);
  document.addEventListener('pointermove', function(e){
    if(!dn || !_ov || e.pointerId!==dn.id || _zg) return;
    var k=zk(cv()), dx=(e.clientX-dn.x)/k, dy=(e.clientY-dn.y)/k;
    if(!dn.moved && Math.abs(e.clientX-dn.x)+Math.abs(e.clientY-dn.y)<5) return;
    if(_ovA){ cancelAnimationFrame(_ovA); _ovA=null; cv().classList.remove('ln-ovanim'); }
    dn.moved=true; cv().classList.add('ln-drag'); _ov.tx=dn.tx+dx; if(tall(_ov)) _ov.ty=dn.ty+dy; ovClamp(_ov); ovSet(_ov);
    var t=performance.now(); dn.smp.push([t,_ov.tx,_ov.ty]); while(dn.smp.length>2 && dn.smp[0][0]<t-90) dn.smp.shift();
  }, true);
  ['pointerup','pointercancel'].forEach(function(t){ document.addEventListener(t, function(e){ if(np>0) np--; }, true); });
  document.addEventListener('pointerup', function(e){
    if(!dn || e.pointerId!==dn.id) return;
    var d=dn; dn=null; cv().classList.remove('ln-drag');
    if(_ov && d.moved && !_zg && d.smp.length>=2){ var a0=d.smp[0], b0=d.smp[d.smp.length-1], t1=performance.now();
      if(t1-b0[0]<60){ var dt0=Math.max(16,b0[0]-a0[0]); ovCoast((b0[1]-a0[1])/dt0, (b0[2]-a0[2])/dt0); } }
    if(!_ov || d.moved || _zg || performance.now()<_gzUntil) return;
    /* a click: down to that event at the fitted size (zoomed in and right on a card: it opens as well) */
    var id=ovPoint(e.clientX, e.clientY), open=_ovCard===id;
    if(id) ovLeave(id, false, open ? function(){ if(window.enterFocus) window.enterFocus(id); } : null);
  }, true);
  /* nothing under the whole timeline is clicked through to (cards, the engine's own drag) */
  ['mousedown','click','dblclick'].forEach(function(t){ document.addEventListener(t, function(e){ var c=cv(); if(_ov && c && c.contains(e.target)){ e.preventDefault(); e.stopPropagation(); } }, true); });
})();

/* ── zoom (Luke, 2026-10-26: "Can't seem to zoom out or in"). A pinch, ctrl/⌘ + the wheel (a Chrome
   trackpad's pinch), Safari's gesture events (a Mac trackpad; a phone's two fingers, phone.py) and + / − / 0
   (with or without ⌘) all scale the board itself — the same transform as the whole timeline above — round
   the point under the pointer or the fingers, from the whole timeline (its least) to ZMAX. The page still
   opens fitted to the window; zoomed back within ZSNAP of it, or with 0 / Esc / the whole-timeline toggle,
   the board returns to the fitted view on the event nearest the middle. Zoomed in, the board pans both ways
   (wheel, drag); a click goes down to that event (right on a card: it opens). Each gesture has one owner,
   decided as it starts (the System's rule, solar_draw.py): an enlarged card's (let go) or an open panel's
   (the Overview's own zoom) stays the engine's; everything else on the board is this. ── */
var OV_T='The whole timeline (−) · zoom: pinch, ⌘ + scroll, + / −', OV_BACK='Back to the events (0 / Esc)', _ovCard=null, _zg=null, _zw=null, _zt=0;
function wsz(){ var w=document.getElementById('world'); return {w:(w && w.offsetWidth) || geo().W, h:(w && w.offsetHeight) || (geo().H+PAD())}; }
function tall(o){ var c=cv(), z=wsz(); return o.s>1.001 || z.h*o.s>c.clientHeight+2; }
/* the board never leaves the window: bigger than it, its edges stay at or past the window's (+30px); smaller, it stays inside */
function ovClamp(o){
  var c=cv(), z=wsz(), cw=c.clientWidth, ch=c.clientHeight, Wd=z.w*o.s, Hd=z.h*o.s, m=30, I=ins(c), ml=m+I.l, mr=m+I.r;
  o.tx=Wd>cw-ml-mr ? Math.max(cw-Wd-mr, Math.min(ml, o.tx)) : Math.max(ml, Math.min(cw-Wd-mr, o.tx));
  o.ty=Hd>ch ? Math.max(ch-Hd-m, Math.min(m, o.ty)) : Math.max(Math.min(0, ch-Hd), Math.min(Math.max(0, ch-Hd), o.ty));
  return o;
}
function zMin(){ var f=ovFit(); return Math.min(1, f.s); }
function zLocal(e){ var c=cv(), r=c.getBoundingClientRect(), k=zk(c);
  if(e && e.clientX!=null && (e.clientX || e.clientY)) return {x:(e.clientX-r.left)/k, y:(e.clientY-r.top)/k};
  var B=band(c); return {x:c.clientWidth/2, y:(B.t+B.b)/2}; }
/* into the scaled view at the size it is now, the board exactly where it was */
function zEnter(){
  if(_ov) return true;
  if(!on() || window._focusedNodeId || busyElsewhere()) return false;
  cancelAll(); M.vy=null; var here=current(); if(here) setCur(here);
  var c=cv(), off=worldOff(c);
  _ov={s:1, tx:off.x-c.scrollLeft, ty:off.y-c.scrollTop, hand:1};
  ovHold(true); ovSet(_ov); c.scrollLeft=0; c.scrollTop=0; c.classList.add('ln-ov'); if(MM) MM.classList.remove('on');
  if(R){ R.ov.setAttribute('aria-pressed','true'); }
  return true;
}
function zSet(s2, q, w){                     /* scale s2; world point w (default: the one under q) under q */
  var o=_ov; s2=Math.max(zMin(), Math.min(ZMAX, s2));
  if(!w) w={x:(q.x-o.tx)/o.s, y:(q.y-o.ty)/o.s};
  o.s=s2; o.tx=q.x-w.x*s2; o.ty=q.y-w.y*s2; o.hand=1; ovClamp(o); ovSet(o);
  cv().classList.toggle('ln-zin', s2>1.001);
}
function zStop(){ ovCoastStop(); if(_ovA){ cancelAnimationFrame(_ovA); _ovA=null; cv().classList.remove('ln-ovanim'); } }
/* a gesture over: back near the fitted size, the fitted view (on the event nearest the middle) */
function zSettle(){
  if(!_ov || _ovA || Math.abs(_ov.s-1)>ZSNAP) return;
  var c=cv(), B=band(c), id=ovPoint(c.getBoundingClientRect().left+c.clientWidth/2*zk(c), c.getBoundingClientRect().top+(B.t+B.b)/2*zk(c));
  ovLeave(id||null);
}
/* + / − and the keys: a step of 1.25, gliding, round the middle of the window */
function zStep(f, e){
  if(!zEnter()) return;
  zStop(); var q=zLocal(e), from={s:_ov.s, tx:_ov.tx, ty:_ov.ty}, w={x:(q.x-_ov.tx)/_ov.s, y:(q.y-_ov.ty)/_ov.s};
  var t=Math.max(zMin(), Math.min(ZMAX, from.s*f)); if(Math.abs(t-1)<ZSNAP) t=1;
  zSet(t, q, w); var to={s:_ov.s, tx:_ov.tx, ty:_ov.ty, hand:1}; ovSet(from); _ov=from; _ov.hand=1;
  ovAnim(from, to, function(){ _ov=to; ovSet(to); cv().classList.toggle('ln-zin', to.s>1.001); if(Math.abs(to.s-1)<1e-3) zSettle(); });
}
var _gzUntil=0, _eg=null, _gs=false, EGAP=260;
/* ENLARGED CARD vs ZOOM / SCROLL (Luke: "enlarging nodes vs. zooming in"). While a card is enlarged, a scroll or a pinch never zooms or moves the line
   under it: the first of a gesture closes the card (the engine's own flight back, so the line is exactly where it was) and nothing else; the rest
   of that gesture is swallowed. Phones keep the engine's pattern. */
function enlargedGate(e){
  if(phone() || panelsOpen()) return false;
  var t=performance.now();
  if(_eg && t-_eg.t<=EGAP){ _eg.t=t; return true; }                 // the rest of the gesture that closed the card
  if(!window._focusedNodeId || (window._altoWheelOwn && window._altoWheelOwn(e))) return false;
  _eg={t:t}; if(window.exitFocus) window.exitFocus(); return true;
}
window.addEventListener('wheel', function(e){
  var c=cv(); if(!on() || !c || !e.target) return;
  var inC=c.contains(e.target);
  if((inC || window._focusedNodeId || _eg) && enlargedGate(e)){ e.preventDefault(); e.stopImmediatePropagation(); return; }
  if(!inC) return;
  if(!e.ctrlKey && !e.metaKey) return;
  /* Chrome sends a trackpad pinch as wheel + ctrl (small deltas): that zooms. A real ctrl / ⌘ + mouse notch (whole 100s, lines) and any ⌘ + wheel are
     a plain notch: it travels the line and the browser's page zoom never sees it. */
  var bg=Math.max(Math.abs(e.deltaX), Math.abs(e.deltaY));
  if((e.metaKey && !e.ctrlKey) || e.deltaMode || (bg>=40 && bg===Math.round(bg) && !(e.deltaX && e.deltaY))){
    e.preventDefault(); e.stopImmediatePropagation();
    if(_ov) ovWheel(e); else if(!busyElsewhere()) onWheel(e, true);
    return; }
  var now=performance.now(); _gzUntil=now+450;
  if(!_zw || now-_zw.t>ZGAP) _zw={own:(window._focusedNodeId || busyElsewhere()) ? 'engine' : 'me'};
  _zw.t=now;
  if(_zw.own!=='me') return;                                    // an enlarged card: the engine lets it go
  e.preventDefault(); e.stopImmediatePropagation();
  if(_zg || !zEnter()) return;                                  // (Safari's own pinch is already scaling)
  zStop();
  var m=e.deltaMode===1 ? 40 : e.deltaMode===2 ? 800 : 1, d=Math.max(-60, Math.min(60, e.deltaY*m)), lone=!_zw.n;
  _zw.n=(_zw.n||0)+1;
  if(!e.deltaX && (e.deltaMode || (lone && Math.abs(e.deltaY)>=40 && Math.abs(e.deltaY)===Math.round(Math.abs(e.deltaY))))){   // a mouse's notch: one smooth step (not 1.8x in a frame)
    zStep(d<0 ? 1.25 : 1/1.25, e); clearTimeout(_zt); _zt=setTimeout(zSettle, ZGAP+700); return; }
  zSet(_ov.s*Math.exp(-d*.01), zLocal(e));
  clearTimeout(_zt); _zt=setTimeout(zSettle, ZGAP+40);
}, {passive:!!window.GestureEvent, capture:true});   /* Safari pinches with gesture events: there the wheel stays passive, so it keeps scrolling panels off the main thread (engine_patches) */
document.addEventListener('gesturestart', function(e){
  var c=cv(); _zg=null; _gs=false;
  if(on() && c && e.target && (c.contains(e.target) || window._focusedNodeId) && enlargedGate(e)){ e.preventDefault(); e.stopImmediatePropagation(); _gs=true; return; }
  if(!on() || !c || !e.target || !c.contains(e.target) || window._focusedNodeId || busyElsewhere()) return;   // the engine's
  e.preventDefault(); e.stopImmediatePropagation();
  dragStop();                                                   // a finger already travelling the line lets go of it: the pinch owns both
  if(!zEnter()) return;
  zStop(); var q=zLocal(e);
  _zg={s0:_ov.s, w:{x:(q.x-_ov.tx)/_ov.s, y:(q.y-_ov.ty)/_ov.s}};
}, {passive:false});
document.addEventListener('gesturechange', function(e){
  if(_gs){ e.preventDefault(); e.stopImmediatePropagation(); _gzUntil=performance.now()+450; return; }
  if(!_zg) return; _gzUntil=performance.now()+450; e.preventDefault(); e.stopImmediatePropagation();
  if(!_ov) return;
  zSet(_zg.s0*(e.scale||1), zLocal(e), _zg.w);                    // the point first pinched stays under the fingers (they pan it too)
}, {passive:false});
document.addEventListener('gestureend', function(e){
  if(_gs){ e.preventDefault(); e.stopImmediatePropagation(); _gs=false; _gzUntil=performance.now()+450; return; }
  if(!_zg) return; _gzUntil=performance.now()+450; e.preventDefault(); e.stopImmediatePropagation();
  _zg=null; zSettle();
}, {passive:false});
window._altoLanesZoom={s:function(){ return _ov ? _ov.s : 1; }, view:function(){ return _ov ? {s:_ov.s, tx:_ov.tx, ty:_ov.ty} : null; }, step:zStep, reset:function(){ if(_ov) ovLeave(null); },
  whole:function(){ if(_ov) ovLeave(null); else ovEnter(); }};      /* (the whole timeline, as the phone's bar button has it; the desktop reaches it by pinch / ⌘ + scroll) */

/* ── the minimap (see NAV_CSS): drawn from the board as laid out, in the board's own px; the box follows the camera ── */
var MM=null, _mmR=0, _mmG=null;
window._altoLanesMmOn=function(){ return MMON; };
function mmSwitch(){ if(!R || !R.map) return; var t=MMON ? 'Hide the minimap' : 'Show the minimap';
  R.map.setAttribute('aria-pressed', MMON ? 'true' : 'false'); R.map.title=t; R.map.setAttribute('aria-label', t); R.el.classList.toggle('lnv-mmoff', !MMON); }
function mmRow(){ return window._altoMmRow ? window._altoMmRow() : null; }
function mmMake(){ if(MM) return MM; MM=document.createElement('div'); MM.id='ln-mm'; MM.className='alto-mm'; MM.setAttribute('role','navigation'); MM.tabIndex=-1;
  MM.setAttribute('aria-label','Minimap: the whole timeline; the box is what the window shows. Click to go there.'); MM.title='Where you are in the whole timeline: click to go there';
  document.body.appendChild(MM);
  var dn=null;
  MM.addEventListener('pointerdown', function(e){ if(e.button) return; e.preventDefault(); e.stopPropagation(); dn={id:e.pointerId}; try{ MM.setPointerCapture(e.pointerId); }catch(er){} });
  MM.addEventListener('pointerup', function(e){ if(!dn || e.pointerId!==dn.id) return; dn=null; var id=mmAt(e.clientX); if(!id || !on()) return;
    if(_ov) ovLeave(null, true); if(window._focusedNodeId && window.exitFocus) try{ window.exitFocus(); }catch(er){} step(id,'rail'); });
  MM.addEventListener('pointercancel', function(){ dn=null; });
  return MM; }
/* the board in its own px: each shown card, the main line, the window's box (all read off the screen, so any fit scale or page zoom is undone alike) */
function mmGeo(){
  var c=cv(), w=document.getElementById('world'); if(!c || !w || !w.offsetWidth) return null;
  var wr=w.getBoundingClientRect(), k=wr.width/w.offsetWidth || 1, cards=[], b=[Infinity, Infinity, -Infinity, -Infinity];
  function add(r, cls, id){ var x=(r.left-wr.left)/k, y=(r.top-wr.top)/k, ww=r.width/k, hh=r.height/k; if(!ww || !hh) return;
    cards.push([x, y, ww, hh, cls, id]); b=[Math.min(b[0], x), Math.min(b[1], y), Math.max(b[2], x+ww), Math.max(b[3], y+hh)]; }
  document.querySelectorAll('#world .node').forEach(function(n){ var cd=n.querySelector('.node-card'); if(!cd || getComputedStyle(n).display==='none' || n.style.visibility==='hidden') return;
    add(cd.getBoundingClientRect(), n.classList.contains('ln-kid') ? 'k' : '', n.id.slice(5)); });
  var ln=document.querySelector('#lanes-svg path.ln-main'), lm=null;
  if(ln && ln.getScreenCTM){ var M=ln.getScreenCTM(), q=ln.getBoundingClientRect(); if(M && q.width){
    lm={d:ln.getAttribute('d'), m:[M.a/k, M.b/k, M.c/k, M.d/k, (M.e-wr.left)/k, (M.f-wr.top)/k]};
    var x0=(q.left-wr.left)/k, x1=(q.right-wr.left)/k, y0=(q.top-wr.top)/k, y1=(q.bottom-wr.top)/k; b=[Math.min(b[0], x0), Math.min(b[1], y0), Math.max(b[2], x1), Math.max(b[3], y1)]; } }
  if(!cards.length) return null;
  var us=[]; document.querySelectorAll('#world .lanes-unit').forEach(function(u){ var x=parseFloat(u.style.left), ww=parseFloat(u.style.width); if(isNaN(x) || isNaN(ww)) return;
    us.push([x, x+ww, u.style.getPropertyValue('--unit-color')]); });
  us.sort(function(p, q){ return p[0]-q[0]; });
  return {k:k, wr:wr, cards:cards, lm:lm, b:b, us:us}; }
function mmView(){ var c=cv(), w=document.getElementById('world'); if(!c || !w || !w.offsetWidth) return null; var wr=w.getBoundingClientRect(), k=wr.width/w.offsetWidth || 1, cr=c.getBoundingClientRect();
  return [(cr.left-wr.left)/k, (cr.top-wr.top)/k, cr.width/k, cr.height/k]; }
function mmAt(cx){ if(!_mmG || !MM) return null; var sv=MM.querySelector('svg'), M=sv && sv.getScreenCTM && sv.getScreenCTM(); if(!M) return null;
  var p=sv.createSVGPoint(); p.x=cx; p.y=0; var x=p.matrixTransform(M.inverse()).x, S=stops().ids, best=null, bd=Infinity;
  _mmG.cards.forEach(function(q){ if(S.indexOf(q[5])<0) return; var d=Math.abs(q[0]+q[2]/2-x); if(d<bd){ bd=d; best=q[5]; } }); return best; }
function mmEsc(v){ return String(v).replace(/[&<>"']/g, function(c){ return '&#'+c.charCodeAt(0)+';'; }); }
function mmDraw(){
  var m=mmMake(), G=mmGeo(), row=mmRow(); _mmG=G;
  if(!MMON){ m.classList.remove('on'); return; }
  if(!G || !row || !on() || _ov || phone()){ m.classList.remove('on'); if(R && !_ov) R.el.classList.toggle('lnv-nomm', !row && !phone()); return; }
  var z=parseFloat(getComputedStyle(de).zoom)||1; row=row.map(function(v){ return v/z; });      /* (a zoomed page: fixed px are its own) */
  var rw=(row[2]-row[0]), x0=G.b[0], y0=G.b[1], W=Math.max(1, G.b[2]-x0), H=Math.max(1, G.b[3]-y0);
  var cw=rw-14, ch=Math.max(30, Math.min(96, cw*H/W)), pd=W/cw*3;
  m.style.width=rw+'px'; m.style.height=(ch+10)+'px'; m.style.left=row[0]+'px'; m.style.top=(row[1]-(window._altoMmGap||12)-ch-10)+'px';
  var s='<svg viewBox="'+[x0-pd, y0-pd, W+2*pd, H+2*pd].map(function(v){ return v.toFixed(0); }).join(' ')+'" preserveAspectRatio="none" aria-hidden="true">';      /* (the whole length across its width; a tall Expanded board is drawn shallower) */
  var cur=current(), un='', VX=x0-pd, VW=W+2*pd;
  (G.us||[]).forEach(function(u, i){ var a=Math.max(u[0], VX), z=Math.min(u[1], VX+VW); if(z<=a) return; var c=' style="--uc:'+mmEsc(u[2])+'"';
    s+='<rect class="mm-ub"'+c+' x="'+a.toFixed(0)+'" y="'+(y0-pd).toFixed(0)+'" width="'+(z-a).toFixed(0)+'" height="'+(H+2*pd).toFixed(0)+'"/>';
    if(i) s+='<line class="mm-ud"'+c+' x1="'+a.toFixed(0)+'" x2="'+a.toFixed(0)+'" y1="'+(y0-pd).toFixed(0)+'" y2="'+(y0+H+pd).toFixed(0)+'"/>';
    un+='<span class="mm-un" style="--uc:'+mmEsc(u[2])+';left:calc(7px + (100% - 14px) * '+((a-VX)/VW).toFixed(4)+')">'+mmEsc(window._altoU ? window._altoU(i+1, 'roman') : String(i+1))+'</span>'; });
  G.cards.forEach(function(q){ s+='<rect class="mm-c'+(q[4] ? ' '+q[4] : '')+(q[5]===cur ? ' h' : '')+'" x="'+q[0].toFixed(0)+'" y="'+q[1].toFixed(0)+'" width="'+q[2].toFixed(0)+'" height="'+q[3].toFixed(0)+'"/>'; });
  if(G.lm) s+='<g transform="matrix('+G.lm.m.map(function(v){ return v.toFixed(4); }).join(' ')+')"><path class="mm-l" d="'+G.lm.d+'"/></g>';
  m.innerHTML=s+'<rect class="mm-v"/></svg>'+un;
  var q=m.getBoundingClientRect(), nb=R && R.el.getBoundingClientRect(), hit=!!(nb && nb.width && q.left<nb.right+8 && nb.left<q.right+8 && q.top<nb.bottom+8 && nb.top<q.bottom+8) || q.top<0;
  if(R) R.el.classList.toggle('lnv-nomm', hit);
  if(hit){ m.classList.remove('on'); return; }
  m.classList.add('on'); mmBox(); }
function mmBox(){ _mmR=0; if(!MM) return; if(_ov){ MM.classList.remove('on'); return; } if(!MM.classList.contains('on') || !_mmG){ mmLater(60); return; } var r=MM.querySelector('.mm-v'), v=mmView(); if(!r || !v) return;
  var b=_mmG.b, x0=Math.max(v[0], b[0]), y0=Math.max(v[1], b[1]), x1=Math.min(v[0]+v[2], b[2]), y1=Math.min(v[1]+v[3], b[3]);
  r.setAttribute('x', x0.toFixed(0)); r.setAttribute('y', y0.toFixed(0)); r.setAttribute('width', Math.max(0, x1-x0).toFixed(0)); r.setAttribute('height', Math.max(0, y1-y0).toFixed(0));
  var cur=current();      /* the lit card follows the steps */
  [].forEach.call(MM.querySelectorAll('.mm-c'), function(e, i){ var on1=_mmG.cards[i] && _mmG.cards[i][5]===cur; if(e.classList.contains('h')!==on1) e.classList.toggle('h', on1); }); }
function mmSoon(){ if(!_mmR) _mmR=requestAnimationFrame(mmBox); }
var _mmT=0; function mmLater(ms){ clearTimeout(_mmT); _mmT=setTimeout(mmDraw, ms||60); }
(function(){ var c=cv(); if(c) c.addEventListener('scroll', mmSoon, {passive:true}); })();
window.addEventListener('resize', function(){ mmLater(120); });
if(window.MutationObserver) new MutationObserver(function(){ mmLater(80); }).observe(de, {attributes:true, attributeFilter:['class']});
window._altoLanesMm=function(){ mmDraw(); return MM; };

/* a click is never read as part of a pinch or a drag: none for a moment after one (a second finger's pointerdown, a gesture, a zoom wheel) */
document.addEventListener('click', function(e){
  var c=cv(); if(on() && c && c.contains(e.target) && performance.now()<_gzUntil){ e.preventDefault(); e.stopImmediatePropagation(); }
}, true);

/* ── a click on a card enlarges it, as a pinch on a card does in the vertical timeline (Luke, 2026-11-13). On the
   enlarged card a click is the engine's (its page, as ⛶). Phones keep their own pattern (the card's page). ── */
var _ckd=null;
document.addEventListener('mousedown', function(e){ _ckd=[e.clientX, e.clientY]; }, true);
document.addEventListener('click', function(e){
  if(!on() || _ov || phone() || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || !window.enterFocus) return;
  var t=e.target, card=t && t.closest && t.closest('#world .node[data-ln] .node-card'); if(!card) return;
  if(t.closest('button,a,input,select,textarea,.ln-chip,.lanes-tag,[onclick]') && !t.closest('.node-title,.node-desc')) return;
  var n=card.closest('.node'), id=n && n.id.slice(5); if(!id || n.classList.contains('focused')) return;
  if(_ckd && Math.abs(e.clientX-_ckd[0])+Math.abs(e.clientY-_ckd[1])>6) return;          // a drag, not a click
  if(de.classList.contains('detail-open') || document.querySelector('#notes-panel.open,#summary-wrap.open,#ef-panel.open,#bg-panel.open,#note-dialog.visible,#share-dialog.visible')) return;
  e.preventDefault(); e.stopImmediatePropagation();
  cancelAll(); window.enterFocus(id);
}, true);

/* ── after every layout ─────────────────────────────────────────────────── */
var _vw=0;
function relaid(first){
  var turned=_vw && Math.abs(innerWidth-_vw)>=80; _vw=innerWidth;
  var G=geo(); if(!G) return;
  hookWheel(); watchFocus(); buildRail(); ovNoScroll();
  document.querySelectorAll('#world .node[data-ln] .node-card').forEach(function(c){ if(!c.hasAttribute('tabindex')) c.setAttribute('tabindex','0'); });
  if(_cur && !document.getElementById('node-'+_cur)) _cur=null;
  if(_cur){ var n=document.getElementById('node-'+_cur); if(n) n.classList.add('ln-cur'); }
  railMarks();
  mmLater(first ? 400 : 60);
  if(_ov){ var c=cv(); _ov=_ov.hand ? ovClamp(_ov) : ovFit(); ovSet(_ov); c.scrollLeft=0; c.scrollTop=0; ui(current(),0); return; }
  /* a re-layout (a resize, an edit) keeps the view on the event the steps were on */
  if(M.raf){ M.stale=true; ui(current(),0); return; }        // mid-travel: tick carries on from the view as it is
  M.pth=null; _fit=null;
  /* a phone opens on the first event, as one tap on Next would leave it: at the start of time the first card ran off the right edge of a 402 pt screen
     (x 185 to 475, audit row F1), because the camera cannot centre an event that near the start. Not when the page opened somewhere of its own (a link to a card). */
  if(first && phone() && on() && !window._focusedNodeId && !(window.__altoHash ? window.__altoHash() : location['hash']) && !cv().scrollLeft){ var f0=stops().ids[0]; if(f0){ glideTo(f0,{instant:true}); ui(f0,0); return; } }
  if(!first && _cur && de.classList.contains('ln-stepped') && on() && !window._focusedNodeId){ glideTo(_cur,{instant:true}); }
  /* a phone turned (sim1112b S6): the board is laid out again for the new box and the view was left at the start of time, the first card off the right edge
     (x 185 to 475 again). It rests on the event it was on, as a page opened this way up does. */
  else if(!first && turned && phone() && on() && !window._focusedNodeId){ var c0=current()||stops().ids[0]; if(c0){ glideTo(c0,{instant:true}); ui(c0,0); } else ui(current(),0); }
  else ui(current(),0);
}
var _lay=window._altoLanes, _laid=0;
if(_lay) window._altoLanes=function(h){
  var r=_lay.apply(this, arguments);
  if(r){ var first=!_laid++; setTimeout(function(){ relaid(first); }, first ? 140 : 0); }   // first: after lanes.py's open-at-the-start
  return r;
};
window.addEventListener('resize', function(){ invalidate(); if(R) ui(current(),0); });
})();

/* The material's cross-references (CONNECTIONS beyond the line's own spine) on a board whose branches are open (Expanded, or Outline all): each
   one drawn card edge to card edge where both its cards show (Luke 2026-11-27: "make sure the connecting lines are functional as usual in
   horizontal timeline with nested branches expanded and in outline format"). Routed on a grid around every card, so a line never crosses a
   card or its words; quiet at rest, drawn full while one of its cards is hovered or enlarged; the other end's title and the material's note
   as its tooltip. Compact and phones are as they were (a tucked card has no line). */
(function(){
  var de=document.documentElement, NS='http://www.w3.org/2000/svg', CELL=8, PAD=6, T=0, HOT='';      /* (PAD: a line keeps 6 px off every card and tab, so it never reads as a frame: Board 2026-11-27) */
  function on(){ var K=window._altoLanesKids; return !!(K && K.view && K.view()==='expanded') && !de.classList.contains('mobile') && !de.classList.contains('phone-whole')
    && !de.classList.contains('printing') && typeof CONNECTIONS!=='undefined'; }
  function shown(n){ if(!n || n.classList.contains('ln-kid-shut') || n.classList.contains('ln-hid')) return null; var c=n.querySelector('.node-card'); if(!c) return null;
    var s=getComputedStyle(n); if(s.display==='none' || s.visibility==='hidden') return null; var r=c.getBoundingClientRect(); return (r.width>2 && r.height>2) ? r : null; }
  function title(id){ var t=document.querySelector('#node-'+id+' .node-title'); return t ? t.textContent.trim() : id; }
  /* A* on a grid in the board's own px, 4 ways, a turn costs extra (clean right angles) */
  function route(a, b, boxes, X0, Y0, W, H){
    var CS=Math.max(CELL, Math.ceil(Math.sqrt(W*H/300000))), cw=Math.ceil(W/CS), ch=Math.ceil(H/CS), N=cw*ch; if(cw<2 || ch<2) return null;      /* (a finer grid where the stretch is short) */
    var blk=new Uint8Array(N);
    boxes.forEach(function(r){ var x0=Math.max(0, Math.floor((r[0]-PAD-X0)/CS)), x1=Math.min(cw-1, Math.floor((r[2]+PAD-X0)/CS)),
      y0=Math.max(0, Math.floor((r[1]-PAD-Y0)/CS)), y1=Math.min(ch-1, Math.floor((r[3]+PAD-Y0)/CS));
      for(var y=y0;y<=y1;y++) for(var x=x0;x<=x1;x++) blk[y*cw+x]=1; });
    function cell(p){ return [Math.max(0, Math.min(cw-1, Math.round((p[0]-X0)/CS))), Math.max(0, Math.min(ch-1, Math.round((p[1]-Y0)/CS)))]; }
    var s=cell(a), e=cell(b), si=s[1]*cw+s[0], ei=e[1]*cw+e[0]; blk[si]=0; blk[ei]=0;
    var g=new Float32Array(N*4).fill(1e9), from=new Int32Array(N*4).fill(-1), heap=[], DX=[1,-1,0,0], DY=[0,0,1,-1];
    function h(i){ var x=i%cw, y=(i/cw)|0; return Math.abs(x-e[0])+Math.abs(y-e[1]); }
    function push(k, f){ heap.push([f,k]); var i=heap.length-1; while(i>0){ var q=(i-1)>>1; if(heap[q][0]<=heap[i][0]) break; var t=heap[q]; heap[q]=heap[i]; heap[i]=t; i=q; } }
    function pop(){ var top=heap[0], last=heap.pop(); if(heap.length){ heap[0]=last; var i=0; for(;;){ var l=2*i+1, r=l+1, m=i; if(l<heap.length && heap[l][0]<heap[m][0]) m=l; if(r<heap.length && heap[r][0]<heap[m][0]) m=r; if(m===i) break; var t=heap[m]; heap[m]=heap[i]; heap[i]=t; i=m; } } return top; }
    for(var d=0;d<4;d++){ g[si*4+d]=0; push(si*4+d, h(si)); }
    var end=-1, steps=0;
    while(heap.length && steps++<300000){ var it=pop(), k=it[1], i=k>>2, dd=k&3; if(it[0]-h(i)>g[k]+1e-6) continue; if(i===ei){ end=k; break; }
      var x=i%cw, y=(i/cw)|0;
      for(var nd=0;nd<4;nd++){ var nx=x+DX[nd], ny=y+DY[nd]; if(nx<0||ny<0||nx>=cw||ny>=ch) continue; var j=ny*cw+nx; if(blk[j]) continue;
        var c=g[k]+1+(nd!==dd ? 4 : 0), kk=j*4+nd; if(c<g[kk]){ g[kk]=c; from[kk]=k; push(kk, c+h(j)); } } }
    if(end<0) return null;
    var pts=[]; for(var k2=end;k2>=0;k2=from[k2]){ var i2=k2>>2; pts.push([X0+(i2%cw)*CS, Y0+((i2/cw)|0)*CS]); }
    pts.reverse(); var q0=pts[0], qN=pts[pts.length-1]; pts.unshift([a[0], q0[1]]); pts.unshift(a.slice()); pts.push([b[0], qN[1]]); pts.push(b.slice());      /* (the ends joined square to the grid: a slanted end could clip a card's corner) */
    var out=[pts[0]]; for(var q=1;q<pts.length-1;q++){ var p0=out[out.length-1], p1=pts[q], p2=pts[q+1]; if((p0[0]===p1[0] && p1[0]===p2[0]) || (p0[1]===p1[1] && p1[1]===p2[1])) continue; out.push(p1); }
    out.push(pts[pts.length-1]); return out;
  }
  /* where a line leaves a card: the middle of the side facing the other card, just outside it */
  /* where a line leaves a card: the middle of a side, just outside it, the side facing the other card first, else the next clear one
     (a card in a stacked column has only a few px of gap above and below it) */
  function port(r, o, others){ var cx=(r[0]+r[2])/2, cy=(r[1]+r[3])/2, ox=(o[0]+o[2])/2, oy=(o[1]+o[3])/2, dx=ox-cx, dy=oy-cy, D=PAD+CELL+2;
    var S={r:[[r[2], cy],[r[2]+D, cy]], l:[[r[0], cy],[r[0]-D, cy]], b:[[cx, r[3]],[cx, r[3]+D]], t:[[cx, r[1]],[cx, r[1]-D]]};
    var h=dx>0 ? ['r','l'] : ['l','r'], v=dy>0 ? ['b','t'] : ['t','b'], order=Math.abs(dx)*(r[3]-r[1])>Math.abs(dy)*(r[2]-r[0]) ? [h[0], v[0], v[1], h[1]] : [v[0], h[0], h[1], v[1]];
    function free(q){ return !others.some(function(b){ return q[0]>b[0]-PAD-1 && q[0]<b[2]+PAD+1 && q[1]>b[1]-PAD-1 && q[1]<b[3]+PAD+1; }); }
    for(var k=0;k<4;k++) if(free(S[order[k]][1])) return S[order[k]];
    return S[order[0]]; }
  function draw(){
    var svg=document.getElementById('lanes-svg'), old=svg && svg.querySelector('g.ln-xrefs'); if(old) old.remove();
    if(!svg || !on()) return;
    var M=svg.getScreenCTM(); if(!M) return; var inv=M.inverse();
    function loc(r){ var p=svg.createSVGPoint(), q; p.x=r.left; p.y=r.top; q=p.matrixTransform(inv); var x0=q.x, y0=q.y; p.x=r.right; p.y=r.bottom; q=p.matrixTransform(inv); return [x0, y0, q.x, q.y]; }
    var rects={}, boxes=[];
    document.querySelectorAll('#world .node[id^="node-"]').forEach(function(n){ var r=shown(n); if(!r) return; var b=loc(r); rects[n.id.slice(5)]=b; boxes.push(b); });
    /* a card's tabs (its outline / list switch, its "inside" chip) stand on its edge: in the way too (Board 2026-11-27: a lit line ran through
       "⑂ outline") */
    var tabs=[]; document.querySelectorAll('#world .ln-otag, #world .ln-chip').forEach(function(t){ var r=t.getBoundingClientRect(); if(r.width>2 && getComputedStyle(t).visibility!=='hidden') tabs.push(loc(r)); });
    var seen={}, list=CONNECTIONS.filter(function(c){ if(!c || c[2]==='spine' || !rects[c[0]] || !rects[c[1]] || c[0]===c[1]) return false; var k=c[0]<c[1] ? c[0]+'|'+c[1] : c[1]+'|'+c[0]; if(seen[k]) return false; return (seen[k]=1); });
    if(!list.length) return;
    var g=document.createElementNS(NS,'g'); g.setAttribute('class','ln-xrefs'); svg.appendChild(g);
    list.forEach(function(c){
      var A=rects[c[0]], B=rects[c[1]], X0=Math.min(A[0], B[0])-240, X1=Math.max(A[2], B[2])+240, Y0=Math.min(A[1], B[1])-320, Y1=Math.max(A[3], B[3])+320;
      var near=boxes.concat(tabs).filter(function(r){ return r!==A && r!==B && r[2]>X0 && r[0]<X1 && r[3]>Y0 && r[1]<Y1; }), pa=port(A, B, near), pb=port(B, A, near);
      var R=route;
      /* two cards facing each other with nothing between: a short straight line from edge to edge, no detour */
      var clear=function(q){ return !near.some(function(r){ return Math.max(q[0][0], q[1][0])>r[0]-PAD && Math.min(q[0][0], q[1][0])<r[2]+PAD && Math.max(q[0][1], q[1][1])>r[1]-PAD && Math.min(q[0][1], q[1][1])<r[3]+PAD; }); }, direct=null;
      var ox=Math.max(A[0], B[0]), oxe=Math.min(A[2], B[2]), oy=Math.max(A[1], B[1]), oye=Math.min(A[3], B[3]);
      if(oxe-ox>16){ var xm=(ox+oxe)/2, up=A[1]<B[1] ? A : B, dn=up===A ? B : A; if(dn[1]>up[3]) direct=[[xm, up[3]], [xm, dn[1]]]; }
      else if(oye-oy>16){ var ym=(oy+oye)/2, lf=A[0]<B[0] ? A : B, rt=lf===A ? B : A; if(rt[0]>lf[2]) direct=[[lf[2], ym], [rt[0], ym]]; }
      if(direct && !clear(direct)) direct=null;
      var pts=direct ? null : R(pa[1], pb[1], near.concat([A, B]), X0, Y0, X1-X0, Y1-Y0);      /* (its own two cards are in the way too: it leaves and enters by their ports) */
      if(!pts && !direct){ var Yt=Math.min.apply(null, boxes.map(function(r){ return r[1]; }))-60, Yb=Math.max.apply(null, boxes.map(function(r){ return r[3]; }))+60;
        pts=R(pa[1], pb[1], near.concat(boxes.filter(function(r){ return near.indexOf(r)<0 && r!==A && r!==B; }), tabs.filter(function(r){ return near.indexOf(r)<0; }), [A, B]), X0, Yt, X1-X0, Yb-Yt); }
      if(direct) pts=direct;
      else { if(!pts) return;      /* (no clear way round: better no line than one through a card) */
        pts=[pa[0]].concat(pts, [pb[0]]); }
      var d='M'+pts.map(function(p){ return p[0].toFixed(1)+' '+p[1].toFixed(1); }).join(' L');
      var col=(typeof COLOR_MAP!=='undefined' && COLOR_MAP[c[2]]) ? COLOR_MAP[c[2]] : 'var(--accent)';
      var w=document.createElementNS(NS,'g'); w.setAttribute('class','ln-xref'); w.setAttribute('data-a', c[0]); w.setAttribute('data-b', c[1]); g.appendChild(w);
      var hit=document.createElementNS(NS,'path'); hit.setAttribute('class','ln-xhit'); hit.setAttribute('d', d); w.appendChild(hit);
      var pa2=document.createElementNS(NS,'path'); pa2.setAttribute('class','ln-xline'); pa2.setAttribute('d', d); pa2.setAttribute('stroke', col); w.appendChild(pa2);
      [pts[0], pts[pts.length-1]].forEach(function(p){ var e=document.createElementNS(NS,'circle'); e.setAttribute('class','ln-xdot'); e.setAttribute('cx', p[0]); e.setAttribute('cy', p[1]); e.setAttribute('r', 3); e.setAttribute('fill', col); w.appendChild(e); });
      var tt=document.createElementNS(NS,'title'); tt.textContent=title(c[0])+' ↔ '+title(c[1])+(c[3] ? ' — '+c[3] : ''); w.appendChild(tt);
    });
    hot(HOT);
  }
  function hot(id){ HOT=id||''; var f=window._focusedNodeId||'';
    document.querySelectorAll('#lanes-svg g.ln-xref').forEach(function(w){ var a=w.getAttribute('data-a'), b=w.getAttribute('data-b');
      w.classList.toggle('ln-xon', !!((HOT && (a===HOT || b===HOT)) || (f && (a===f || b===f)))); }); }
  function soon(){ clearTimeout(T); T=setTimeout(draw, 60); }
  var lay=window._altoLanes; if(lay) window._altoLanes=function(){ var r=lay.apply(this, arguments); soon(); return r; };
  document.addEventListener('mouseover', function(e){ var n=e.target.closest && e.target.closest('#world .node[id^="node-"]'); var id=n ? n.id.slice(5) : ''; if(id!==HOT) hot(id); }, true);
  function hookF(){ ['enterFocus','exitFocus'].forEach(function(k){ var f=window[k]; if(typeof f==='function' && !f._lnX){ var nf=function(){ var r=f.apply(this, arguments); setTimeout(function(){ hot(HOT); }, 0); return r; }; for(var q in f) nf[q]=f[q]; nf._lnX=1; window[k]=nf; } }); }
  hookF(); window.addEventListener('load', function(){ hookF(); soon(); }); window.addEventListener('resize', soon);
  window._altoLanesXrefs=draw;
})();
/* An enlarged card on a phone fits the room between the top chrome and the step bar, 20 px clear of each (Board 2026-11-27, l844: its last
   line ran under the step bar's "2 / 275"): slid into that room, and where it is taller than the room, held to it and scrolled inside.
   Let go, it is as it was. */
(function(){
  var de=document.documentElement, fit=null, T=0;
  function band(){
    var top=0, bot=window.innerHeight;
    ['#nav > .title','#nav > svg.brand-mark','#nav > svg.brand-word'].forEach(function(q){ var e=document.querySelector(q), r=e && e.getBoundingClientRect();
      if(r && r.height && r.bottom<window.innerHeight/2) top=Math.max(top, r.bottom); });
    var n=document.getElementById('lanes-nav'), q=n && n.getBoundingClientRect(); if(q && q.height && q.top>window.innerHeight/2) bot=Math.min(bot, q.top);
    return {t:top+20, b:bot-20};
  }
  function undo(){ if(!fit) return; if(fit._lnSh){ fit._lnSh.style.removeProperty('visibility'); fit._lnSh=null; }
    var w=fit.querySelector(':scope > .ln-fitw'); if(w){ while(w.firstChild) fit.insertBefore(w.firstChild, w); w.remove(); }
    fit.style.removeProperty('translate'); fit.style.removeProperty('height'); fit.style.removeProperty('scale'); fit.classList.remove('ln-fit'); de.classList.remove('ln-fitting'); fit=null; }
  /* held to the room, the card's text scrolls in a box inside its padding (Board 2026-11-27: the last line ran to the card's edge, and
     Holographic's frame crossed a line): the padding stays empty, the frame and the order number (laid on the card, not in its flow)
     stay where they are, and a short fade at the foot says there is more below */
  function holdIn(c, room, r){
    var w=document.createElement('div'); w.className='ln-fitw';
    var kids=[].filter.call(c.children, function(e){ var p=getComputedStyle(e).position; return p!=='absolute' && p!=='fixed'; });
    if(!kids.length) return r;
    c.insertBefore(w, kids[0]); kids.forEach(function(e){ w.appendChild(e); });
    /* a card of a set height (its text ran past its foot, clipped there): the box is the card's content area */
    /* measured on screen (the card's zoom and the board's scale lie between its own px and the screen's): the box runs from where the
       text starts to the card's foot less its bottom padding (at the top padding's scale) */
    var cs=getComputedStyle(c), pt=parseFloat(cs.paddingTop)||0, pb=parseFloat(cs.paddingBottom)||0, wr=w.getBoundingClientRect(),
        k=(w.offsetHeight && wr.height) ? wr.height/w.offsetHeight : 1, padB=pt ? (wr.top-r.top)*pb/pt : pb*k, want=r.bottom-padB-wr.top;
    if(wr.height>want+1){ w.style.maxHeight=Math.max(20, Math.floor(want/k))+'px'; r=c.getBoundingClientRect(); }
    var mh=w.offsetHeight||1;
    for(var it=0; it<4 && r.height>room+1; it++){ var nh=Math.max(20, mh-(r.height-room)*(mh/Math.max(1, r.height))); if(Math.abs(nh-mh)<0.5) break; mh=nh;
      w.style.maxHeight=Math.floor(mh)+'px'; r=c.getBoundingClientRect(); }
    var more=function(){ w.classList.toggle('ln-more', w.scrollTop+w.clientHeight<w.scrollHeight-2); };
    w.addEventListener('scroll', more, {passive:true}); more();
    return r;
  }
  function place(){
    var id=window._focusedNodeId, n=id && document.getElementById('node-'+id), c=n && n.querySelector('.node-card');
    if(fit && fit!==c) undo();
    if(!c || !de.classList.contains('phone-whole')) return;
    if(fit===c) undo();
    var B=band(), room=B.b-B.t; if(room<80) return;
    fit=c; c.classList.add('ln-fit'); de.classList.add('ln-fitting');
    /* its outer ring (Retro's and Holographic's rings are box-shadows and outlines past the border) 20 px from the screen's sides: the card is
       scaled down to fit where it would come closer (Board 2026-11-27, retro-p390: the gold ring 8 px from each edge) */
    var ring=0, cs0=getComputedStyle(c);
    (cs0.boxShadow||'').split(/,(?![^(]*\))/).forEach(function(sh){ if(/inset/.test(sh)) return; var n=(sh.replace(/rgba?\([^)]*\)|#[0-9a-f]+/gi,'').match(/-?[\d.]+px/g)||[]).map(parseFloat);
      if(n.length>=4 && n[2]===0) ring=Math.max(ring, n[3]+Math.max(Math.abs(n[0]), Math.abs(n[1]))); });
    if(cs0.outlineStyle!=='none') ring=Math.max(ring, (parseFloat(cs0.outlineWidth)||0)+(parseFloat(cs0.outlineOffset)||0));
    var r0=c.getBoundingClientRect(), kk=(c.offsetWidth && r0.width) ? r0.width/c.offsetWidth : 1, rg=ring*kk, ow=r0.width+2*rg, vw=window.innerWidth;
    if(ow>vw-40){ c.style.setProperty('scale', ((vw-40)/ow).toFixed(4)); r0=c.getBoundingClientRect(); rg=ring*(r0.width/(c.offsetWidth||r0.width)); }
    var dx=r0.left-rg<20 ? 20-(r0.left-rg) : (r0.right+rg>vw-20 ? (vw-20)-(r0.right+rg) : 0); c._lnRing=rg;
    /* a card of a set height whose text runs past its foot grows to hold it first (Board 2026-11-27, p390: its description was cut off with
       the room below unused); only what the room cannot hold scrolls inside */
    if(c.scrollHeight>c.clientHeight+1) c.style.setProperty('height', 'auto', 'important');
    var r=c.getBoundingClientRect();
    /* a unit's label or the line's tag beside the card bounds the room too, 20 px clear (Board 2026-11-27, Retro p390: the gold ring met
       "I BEFORE SUIT") */
    [].forEach.call(document.querySelectorAll('#lanes-ulabels .lu-chip, #world .lanes-tag'), function(e){
      var q=e.getBoundingClientRect(); if(!q.height || q.right<=r.left || q.left>=r.right || getComputedStyle(e).visibility==='hidden') return;
      if(q.top+q.height/2<r.top+r.height/2) B.t=Math.max(B.t, q.bottom+20); else B.b=Math.min(B.b, q.top-20); });
    room=B.b-B.t-2*(c._lnRing||0); if(room<80){ undo(); return; }      /* (the ring stays inside the room too) */
    if(r.height>room+1 || c.scrollHeight>c.clientHeight+1) r=holdIn(c, room, r);      /* (taller than the room, or its text past its own foot) */
    var rr=c._lnRing||0, dy=r.top-rr<B.t ? B.t-(r.top-rr) : (r.bottom+rr>B.b ? B.b-(r.bottom+rr) : 0);
    if(Math.abs(dy)>0.5 || Math.abs(dx)>0.5){ c.style.setProperty('translate', '0 100px'); var k=(c.getBoundingClientRect().top-r.top)/100 || 1;      // screen px a translate px moves
      c.style.setProperty('translate', (dx/k).toFixed(1)+'px '+(dy/k).toFixed(1)+'px'); }
    /* the enlarge's own shadow layer (engine_patches .alto-fshadow) keeps the card's full size and place: held or moved, it would hang
       below the card as a pale box, so it goes while the card is fitted */
    if((Math.abs(dy)>0.5 || c.querySelector(':scope > .ln-fitw')) && n._fsh){ n._fsh.style.setProperty('visibility','hidden'); c._lnSh=n._fsh; }
  }
  var T2=0; function soon(){ clearTimeout(T); clearTimeout(T2); T=setTimeout(place, 650); T2=setTimeout(place, 1300); }      /* (once the card's zoom ramp has settled, and again once the camera's glide has: a pinned unit label moves with it) */
  function hook(){
    var ef=window.enterFocus; if(typeof ef==='function' && !ef._lnFit){ var nf=function(){ undo(); var r=ef.apply(this, arguments); soon(); return r; }; for(var kk in ef) nf[kk]=ef[kk]; nf._lnFit=1; window.enterFocus=nf; }
    var xf=window.exitFocus; if(typeof xf==='function' && !xf._lnFit){ var nx=function(){ clearTimeout(T); clearTimeout(T2); undo(); return xf.apply(this, arguments); }; for(var kx in xf) nx[kx]=xf[kx]; nx._lnFit=1; window.exitFocus=nx; }
  }
  hook(); window.addEventListener('load', hook);      /* (the engine's focus may arrive after this script) */
  window.addEventListener('resize', function(){ if(fit || window._focusedNodeId) soon(); });
  window._altoLanesFitCard=place;
})();
"""
