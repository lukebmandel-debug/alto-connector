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


# ── the five-borough map's own names (city_boroughs.LABELS / names_page): a borough-sized name ("k": "b") and the water's
# names ("k": "w", in the rivers' blue, italic). Spliced only for Manhattan's layout with such names, so every other palace
# page is byte-identical. Each name's size on the screen is its CSS size, so the names' fit (lblFS) reads it from the text.
AREA_ANCHOR = ("t.textContent=a.n; t._g=[a.x, a.y, 0]; t._up=.35; });")
AREA_JS = ("t.textContent=a.n; t._g=[a.x, a.y, 0]; t._up=.35; if(a.k){ t.classList.add('pl-a'+a.k); t._prb=a.k==='b'?480:20;"
           " t._fs=a.k==='b'?function(z){ return Math.max(14, Math.min(24, 11+14*z)); }:function(z){ return Math.max(10, Math.min(15, 8.5+7*z)); }; } });"
           "if(!document.getElementById('pl-nyc-css')){ var nyc=document.createElement('style'); nyc.id='pl-nyc-css'; nyc.textContent="
           "'.pal-svg .pl-area.pl-ab{--afs:clamp(14px, calc(11px + 14px * var(--pz,1)), 24px);font-weight:750;letter-spacing:.32em;opacity:.8;}"
           ".pal-svg .pl-area.pl-aw{--afs:clamp(10px, calc(8.5px + 7px * var(--pz,1)), 15px);font-style:italic;font-weight:650;letter-spacing:.22em;fill:#21507f;opacity:.85;}"
           "html.dark .pal-svg .pl-area.pl-aw{fill:#d6e8fa;}'; document.head.appendChild(nyc); }")
FS_ANCHOR = "case 'pl-area': return phone?"
FS_JS = "case 'pl-area': if(t._fs) return t._fs(z); return phone?"
PR_ANCHOR = "add(t, 'pl-area', 560-40*"
PR_JS = "add(t, 'pl-area', (t._prb||0)+560-40*"


# the ground: on Manhattan's layout the glass is not painted over (Philadelphia's rule: the page's own ground), so the fill-in's
# canvas, which lies under the city's SVG, shows its levels 3-4 (Luke, 2026-10-22: "in NYC background buildings look really weird")
GROUND_JS = ANCHOR.replace("if(M.sea && M.sea.length)", "if(M.sea && M.sea.length && M.layout!=='manhattan')")


def patch_labels(js: str) -> str:
    for a, b in ((AREA_ANCHOR, AREA_JS), (FS_ANCHOR, FS_JS), (PR_ANCHOR, PR_JS), (ANCHOR, GROUND_JS)):
        if js.count(a) != 1:
            raise RuntimeError("palace_manhattan_js: label anchor not found once in PALACE_JS: " + a)
        js = js.replace(a, b, 1)
    return js
