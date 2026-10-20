"""The page side of Manhattan's layout (city_manhattan.py): the far banks' faint grid. New Jersey, Brooklyn and Queens are
not drawn street by street; beyond each river band a grid of the island's own block size fades out in five steps, so the
city plainly goes on across the water without a floating half-drawn island.

Spliced into PALACE_JS only for a map that has M.ghost (palace.palace_js), so every other palace page is byte-identical.
No mask (Safari re-renders masked paths every frame): five strips of falling opacity, each filled with one pattern."""
from __future__ import annotations

ANCHOR = "if(M.sea && M.sea.length) el('rect',{'class':'pl-land', x:-MX-BL, y:-MY-BL, width:VW+2*BL, height:VH+2*BL, rx:34},svg);"

GHOST_JS = r"""
  /* the far banks (city_manhattan.py): the island's grid going on faintly beyond each river, fading out */
  if(M.ghost){ (function(G){ var gg=el('g',{'class':'pl-ghost'},svg), id='plgh'+(svg._sid||''), cw=G.c[0], ch=G.c[1];
    var pt=el('pattern',{id:id, patternUnits:'userSpaceOnUse', width:cw, height:ch, x:G.o[0], y:G.o[1]},defs);
    el('path',{d:'M0 0H'+cw+'M0 0V'+ch, fill:'none', style:'stroke:var(--pal-text);stroke-opacity:.5;stroke-width:5'},pt);
    ['w','e'].forEach(function(s){ var p=G[s], n=p.length>>1, sg=s==='w'?-1:1, K=5, k, i;
      for(k=0;k<K;k++){ var a=G.d*k/K, b=G.d*(k+1)/K, d='';
        for(i=0;i<n;i++) d+=(i?'L':'M')+(p[2*i]+sg*a)+' '+p[2*i+1];
        for(i=n-1;i>=0;i--) d+='L'+(p[2*i]+sg*b)+' '+p[2*i+1];
        el('path',{d:d+'Z', fill:'url(#'+id+')', opacity:(.5*(1-k/K)).toFixed(2)},gg); } }); })(M.ghost); }"""


def patch_js(js: str) -> str:
    if ANCHOR not in js:
        raise RuntimeError("palace_manhattan_js: anchor not found in PALACE_JS")
    return js.replace(ANCHOR, ANCHOR + GHOST_JS, 1)
