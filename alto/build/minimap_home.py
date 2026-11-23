"""Where every desktop minimap sits by default (Luke, 2026-11-13, his Torts System in Star chart: "please default the
minimap to this location and size ... make it the same width as the bottom toggles it sits on top of. The user can
change it if they want, and move it, but it always stays there otherwise").

The default: bottom-right, just above the bottom-right toggle group (search / key / info / light-dark / the edit
pill), GAP CSS px over it, exactly as wide as the group (measured live, not a constant) and right edge on the group's
right edge; the height is the map's own aspect. The minimaps (solar_navopt.py: System 2D and 3D; palace_world.py: the
Atlas) call window._altoMmRow() for the group and window._altoMmGap for the gap. A user's drag (move) or corner pull
(size) is kept per viewer by each map; a double-click on the corner handle brings the default back.

The enlarge-safe-box (engine_patches.py) counts every visible .alto-mm as chrome, so an enlarged card is fitted round
the minimap and the minimap never moves for a card. Phones keep their own maps (MENU's map page, the phone row)."""

# The row's members, right to left; an expanded search counts as its resting circle (it grows leftward over the page).
MM_HOME_JS = r"""
(function(){
if(window._altoMmRow) return;
var IDS=['alto-edit-pill','mode-toggle','info-btn','key-toggle','search-btn'];
window._altoMmGap=12;
window._altoMmRow=function(){
  var R=null, ref=null;
  IDS.forEach(function(id){ var e=document.getElementById(id); if(!e) return; var cs=getComputedStyle(e);
    if(cs.display==='none' || cs.visibility==='hidden' || +cs.opacity<.05 || cs.position!=='fixed') return;
    var r=e.getBoundingClientRect(); if(r.width<2 || r.height<2 || r.bottom<innerHeight*.6) return;
    if(ref && (r.bottom<ref.top || r.top>ref.bottom)) return; if(!ref) ref=r;          /* (the one row: on the first member's line) */
    var l=(id==='search-btn' && r.width>r.height*1.5) ? r.right-r.height : r.left;
    R=R ? [Math.min(R[0], l), Math.min(R[1], r.top), Math.max(R[2], r.right), Math.max(R[3], r.bottom)] : [l, r.top, r.right, r.bottom]; });
  var q=document.getElementById('tab-rail'); q=q&&q.getBoundingClientRect();                 /* (the right rail stands on the row: the minimap clears it) */
  if(R&&q&&q.height>2&&q.bottom>innerHeight*.5) R[1]=Math.min(R[1],q.top);
  return R; };
})();
"""

