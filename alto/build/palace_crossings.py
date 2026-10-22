"""Water crossings that are not bridges (1.9.145): road tunnels under a river, drawn on across the water as a dashed line between its two
mouths (the audit's "tunnels stop at the water": the Holland, Lincoln, Queens-Midtown and Brooklyn-Battery tunnels), and ferry routes
as a dashed line in the water with the route's name along it (the Staten Island Ferry, NYC Ferry, the East River boats).

The map carries m["tun"] = [{n, p}] and m["fy"] = [{n, p}] (page px, flat), city_manhattan's layout fills them from city_boroughs.
patch_js() adds the drawing to drawCity (into the bridges' group, under the bridge decks' names) only for a map that has either.
"""
from __future__ import annotations

CROSS_CSS = r"""
  .pal-svg .pl-tun{fill:none;stroke:var(--pal-br-edge);stroke-width:calc(3.6px / var(--pz,1));stroke-dasharray:calc(10px / var(--pz,1)) calc(7px / var(--pz,1));
    stroke-linecap:round;opacity:.78;}
  .pal-svg .pl-tun-c{fill:none;stroke:var(--pal-casing);stroke-width:calc(6.4px / var(--pz,1));opacity:.55;}
  .pal-svg .pl-fy{fill:none;stroke:var(--pal-br-text);stroke-width:calc(2.2px / var(--pz,1));stroke-dasharray:calc(2px / var(--pz,1)) calc(7px / var(--pz,1));
    stroke-linecap:round;opacity:.55;}
  .pal-svg .pl-fyn{font-size:calc(8.5px / var(--pz,1));font-style:italic;font-weight:650;letter-spacing:.06em;fill:var(--pal-br-text);opacity:.8;}
  .pal-svg.far .pl-fyn{display:none;}
"""

CROSS_JS = r"""
  /* tunnels (dashed, on across the water between their mouths) and ferry routes (dotted, named) — palace_crossings.py */
  (M.tun||[]).forEach(function(t){ var d=pts(t.p); el('path',{'class':'pl-tun-c', d:d},bridges); var h=el('path',{'class':'pl-tun', d:d},bridges); if(t.n){ h._n=t.n; h.setAttribute('data-n', t.n); } });
  (M.fy||[]).forEach(function(f,i){ var d=pts(f.p), h=el('path',{'class':'pl-fy', d:d},bridges); if(f.n){ h._n=f.n; h.setAttribute('data-n', f.n); } if(!f.n || !f.k) return;
    var q=f.p.slice(), n=q.length; if(q[n-2]<q[0]){ var r=[]; for(var k=n-2;k>=0;k-=2) r.push(q[k],q[k+1]); q=r; }
    var id='plfy'+(svg._sid||'')+'-'+i; el('path',{id:id, d:pts(q)},defs);
    var t=el('text',{'class':'pl-fyn', dy:'-.6em'},labels0), tp=el('textPath',{href:'#'+id, startOffset:'50%', 'text-anchor':'middle'},t);
    tp.setAttributeNS('http://www.w3.org/1999/xlink','xlink:href','#'+id); tp.textContent=f.n; });
"""

ANCHOR = "  var lg=el('g',{'class':'pl-lms'},svg);"


def patch_js(js: str) -> str:
    if js.count(ANCHOR) != 1:
        raise ValueError("palace_crossings.patch_js: anchor not found")
    return js.replace(ANCHOR, CROSS_JS + ANCHOR)
