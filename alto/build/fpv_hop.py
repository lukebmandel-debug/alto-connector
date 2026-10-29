"""Shared by the first-person views: the HOP and the gamepad (the figure the camera used to follow, the mayor avatar and the third-person view are gone: every first-person view is first person only).

The Memory Blueprint walk (palace_building_fpv.py, hosted /bldg/ renderer) embeds HOP_JS in its own scope. Nothing of it is on a palace page (civ-pro-palace sits at its 976 KB cap).

  AV.HOP   the hop: v0 m/s, g m/s^2, coyote and buffer seconds (one hop from the ground, none in the air)
  AV.pad() the first standard gamepad: {mx, my, lx, ly, a, run} (sticks with a dead zone, A = hop) or null
"""
from __future__ import annotations

_HOP_JS = r"""
var AV=(function(){
var HOP={v0:3.3, g:13.5, coyote:.1, buffer:.13};                               /* apex 0.40 m, 0.49 s in the air: a natural little hop */
function pad(){ var ps=null; try{ ps=navigator.getGamepads?navigator.getGamepads():null; }catch(x){ ps=null; } if(!ps) return null;
  for(var i=0;i<ps.length;i++){ var g=ps[i]; if(!g||!g.connected||!g.axes||g.axes.length<2) continue; var dz=function(v){ v=+v||0; return Math.abs(v)<.18?0:(v-(v>0?.18:-.18))/.82; };
    var b=function(n){ var q=g.buttons&&g.buttons[n]; return !!(q&&(q.pressed||q.value>.5)); };
    return {mx:dz(g.axes[0]), my:dz(g.axes[1]), lx:dz(g.axes[2]), ly:dz(g.axes[3]), a:b(0), run:b(10)||b(6)||b(7)}; }
  return null; }
return {HOP:HOP, pad:pad};
})();
"""


def hop_js() -> str:
    return _HOP_JS
