"""Landmark buildings of the Mind Palace: a little 3D detail from real life, and a
clear sign when one has reference material inside.

Everything about a landmark building lives here; palace.py has four small hooks
(`LANDMARK_CSS`, `LANDMARK_JS`, `window._palLm.draw / relayout / tip / keyRow`).

- The art. Independence Hall, City Hall, the Museum of Art, the Franklin
  Institute, the Convention Center, 30th Street Station, the towers and a tidy
  default are drawn by the building generator (palace_skyline.py) from parts in
  real metres, in Alto's glass look: a frosted front face lit from the top left,
  a darker side and a lighter top where the building steps back, one line weight
  in the landmark's own (district) colour, one sheen, a soft shadow. ONE SCALE:
  every building is shown at palace_skyline.SCALE map px per real metre whatever
  the size of its card, so heights compare truly across the whole city. They are
  static `<symbol>`s, built once from Python and instanced with `<use>`.
  Not a copy of any map or photograph: the real silhouette, simplified.
- The way in. A landmark whose `page` is an Index list (the Cases, a code, the
  Federal Rules …) is marked: a glass tag on its corner with the page's icon
  and its real count ("20 rules"), a glow in the page's colour, a lit doorway in
  the art, an "Open" cue on hover, a legend row, and a keyboard / screen reader
  label ("Independence Hall — inside: Federal Rules of Civil Procedure, 20
  rules. Open"). The counts are read from the page's own Index chips.
"""
from __future__ import annotations

import json

# ── materials ───────────────────────────────────────────────────────────────
# name: (front a, front b, side, top) for light mode, then for dark mode
_MATS = {
    "stone": (("#f7f5ef", "#dcd8cb", "#c2bdae", "#fdfcf8"), ("#5d627c", "#3f4459", "#2c2f41", "#70769230")),
    "trim": (("#ffffff", "#ecebe5", "#d3d0c6", "#ffffff"), ("#8a8fa9", "#62677f", "#464a5f", "#9a9fba")),
    "brick": (("#de9279", "#bd5a43", "#9a4838", "#e8a891"), ("#a65a49", "#82402f", "#5e2d22", "#b96c5a")),
    "slate": (("#8b95a9", "#5e6980", "#485166", "#a4adbf"), ("#454c62", "#2b3042", "#1f2331", "#555d78")),
    "glass": (("#dbf1fb", "#8cc2e4", "#6aa3c8", "#eaf8fe"), ("#4b80a7", "#2c5779", "#224867", "#5b94bc")),
    "bronze": (("#e0bb74", "#a97e38", "#876229", "#ecd093"), ("#d9b36a", "#a37a35", "#7f5d27", "#e6c98a")),
    "sand": (("#f2e1b8", "#d8bd86", "#bf9f66", "#f9edcf"), ("#8a7a58", "#665a3f", "#4a412d", "#9b8b69")),
    "marble": (("#f8f7f4", "#dedcd6", "#c4c2bc", "#fdfcfa"), ("#6a7090", "#4a5070", "#363b55", "#7c82a2")),
    "granite": (("#cdd0d8", "#9ea3b0", "#838998", "#dadde4"), ("#4c5068", "#383c52", "#2a2d40", "#5b607a")),
    "teal": (("#7fc1b8", "#3f8f88", "#2f726c", "#9dd3cb"), ("#3e7d78", "#2a5c58", "#1f4744", "#4e8f89")),
    "green": (("#cfe3dc", "#8fb8ac", "#74a094", "#e0f0ea"), ("#4f7d70", "#33574d", "#26433b", "#5f8f81")),
    # the skyscrapers' own skins (palace_towers.py): sapphire glass, silver metal, red granite, aqua and steel-blue glass
    "sapphire": (("#d6e6f7", "#86a9dc", "#6489bf", "#e6f0fb"), ("#4a6d9f", "#2f4d7a", "#243c61", "#5c82b6")),
    "silver": (("#f1f4f6", "#c3ccd4", "#a4afba", "#fafcfd"), ("#7a8696", "#576273", "#434c5b", "#8b98a9")),
    "garnet": (("#cf9684", "#96503f", "#783d30", "#dca796"), ("#8f5a4c", "#6c3d32", "#512b23", "#a06b5c")),
    "aqua": (("#d4f6f1", "#72cdc6", "#4fb0ac", "#e6faf7"), ("#3f8f8d", "#2a6d6c", "#1f5252", "#52a3a1")),
    "steel": (("#dbe8f0", "#8eb0c8", "#7095af", "#e8f1f7"), ("#4d7391", "#315069", "#263f55", "#5f87a8")),
}
# City Hall's mansards: the marble's own cool grey, a shade darker (one material story, no separate roof colour)
_MATS["mansard"] = (("#d6dae1", "#b9bec8", "#a5abb7", "#e1e4ea"), ("#5c627e", "#444962", "#32364d", "#6a7090"))
_MATS["stone"] = (_MATS["stone"][0], ("#5d627c", "#3f4459", "#2c2f41", "#70768f"))


def landmark_css() -> str:
    """The landmark rules: materials, the card, the tag, the glow, the focus ring."""
    lines = []
    for mode in (0, 1):
        v = []
        for m, cols in _MATS.items():
            a, b, s, t = cols[mode]
            v.append(f"--lz-{m}-a:{a};--lz-{m}-b:{b};--lz-{m}-s:{s};--lz-{m}-t:{t};")
        v.append("--lz-win:rgba(34,40,66,.34);--lz-mu:rgba(255,255,255,.72);--lz-sl:#f1efe8;--lz-hi:rgba(255,255,255,.55);--lz-gs:rgba(20,26,55,.20);"
                 if mode == 0 else
                 "--lz-win:rgba(8,10,20,.52);--lz-mu:rgba(255,255,255,.30);--lz-sl:#8d92ac;--lz-hi:rgba(255,255,255,.20);--lz-gs:rgba(0,0,0,.40);")
        sel = ".pal-svg" if mode == 0 else "html.dark .pal-svg"
        lines.append(f"  {sel}{{{''.join(v)}}}")
    mats = []
    for m in _MATS:
        mats.append(f"  .lz-s-{m}{{fill:var(--lz-{m}-s);}} .lz-t-{m}{{fill:var(--lz-{m}-t);}}")
    return "\n".join(lines) + "\n" + "\n".join(mats) + r"""
  .lz-f,.lz-sd,.lz-tp{stroke:var(--lz-line,#667);stroke-width:1;stroke-opacity:.62;stroke-linejoin:round;vector-effect:non-scaling-stroke;}
  .lz-ln{fill:none;stroke:var(--lz-line,#667);stroke-width:1;stroke-opacity:.55;stroke-linecap:round;vector-effect:non-scaling-stroke;}
  .lz-win{fill:var(--lz-win);stroke:none;}
  .lz-mu{fill:none;stroke:var(--lz-mu);stroke-width:.8px;vector-effect:non-scaling-stroke;}
  .lz-mu2{stroke-width:1.3px;}
  .lz-gl{fill-opacity:.88;}
  .lz-col-l{fill:none;stroke:var(--lz-mu);stroke-width:1.6px;stroke-linecap:round;vector-effect:non-scaling-stroke;}
  .lz-sl{fill:var(--lz-sl);stroke:none;}
  .lz-hi{fill:none;stroke:var(--lz-hi);stroke-width:1.2;stroke-linecap:round;vector-effect:non-scaling-stroke;}
  .lz-gs{fill:var(--lz-gs);stroke:none;}
  .lz-col{stroke:none;}
  /* (the art is instanced with <use>, whose clones cannot match an ancestor selector: these rules stand alone, and the lit door is a variable set on the building's group) */
  .lz-door{fill:var(--lz-door,var(--lz-win));stroke:none;}
  /* a courthouse's level: a small calm seal (federal blue, state green, city terracotta) */
  .lz-seal{stroke:rgba(255,255,255,.9);stroke-width:1;vector-effect:non-scaling-stroke;}
  .lz-seal-federal{fill:#4a67a8;} .lz-seal-state{fill:#3f8a6e;} .lz-seal-city{fill:#b0703c;}
  .lz-seal-g{fill:#fff;stroke:none;}
  /* the card the building stands on: glass with a thickness, a soft shadow, and the district's edge */
  .pal-svg .pl-lmb .lm-shadow{fill:rgba(20,26,55,.14);}
  .pal-svg .pl-lmb .lm-slab{stroke:none;fill-opacity:.38;}
  .pal-svg .pl-lmb .lm-card{fill:rgba(255,255,255,.90);}
  html.dark .pal-svg .pl-lmb .lm-card{fill:rgba(30,33,46,.92);}
  .pal-svg .pl-lmb .lm-sheen{fill:none;stroke:rgba(255,255,255,.85);stroke-width:1;vector-effect:non-scaling-stroke;}
  html.dark .pal-svg .pl-lmb .lm-sheen{stroke:rgba(255,255,255,.18);}
  /* (the art takes no pointer: a tower rising over the blocks behind it never takes their clicks; its card and its block are the hover box) */
  /* the lift on hover: the individual translate property, which every engine resolves in map units — never px inside a CSS
     transform on SVG content, which Safari multiplies by the page's CSS zoom (palace.py .pl-sc) */
  .pal-svg .pl-lmb .lm-art{transition:translate .25s ease;pointer-events:none;}
  .pal-svg .pl-lmb.has-page:hover .lm-art,.pal-svg .pl-lmb.has-page:focus-visible .lm-art{translate:0 -3px;}
  .pal-svg .pl-lmb .lm-strip{fill:var(--lm-edge,#667);fill-opacity:.10;stroke:none;}
  .pal-svg .pl-lmb .lm-name{font-size:min(max(calc(11.5px / var(--pz,1)), var(--lm-nat,12px)), calc(21px / var(--pz,1)));font-weight:780;letter-spacing:.01em;stroke:var(--pal-halo);stroke-width:calc(3px / var(--pz,1));paint-order:stroke;stroke-linejoin:round;}
  .pal-svg .pl-lmb .lm-name.in{stroke:none;}
  .pal-svg .pl-lmb .lm-sub{font-size:calc(10px / var(--pz,1));font-weight:600;letter-spacing:.02em;stroke:none;fill:var(--lm-col,var(--pal-text));}
  .pal-svg.mid .pl-lmb .lm-sub{display:none;}
  /* "there is something inside": a glow in the page's colour. Still, not animated: three infinite stroke-opacity animations kept WebKit repainting the whole city every frame (idle 50 ms vs 17 ms) and heated laptops. */
  .pal-svg .pl-lmb .lm-glow{fill:none;stroke:var(--lm-col);stroke-width:10px;stroke-opacity:.30;vector-effect:non-scaling-stroke;pointer-events:none;}
  .pal-svg .pl-lmb .lm-glow2{fill:none;stroke:var(--lm-col);stroke-width:2.5px;stroke-opacity:.85;vector-effect:non-scaling-stroke;pointer-events:none;}
  .pal-svg .pl-lmb.has-page:hover .lm-glow,.pal-svg .pl-lmb.has-page:focus-visible .lm-glow{stroke-width:14px;stroke-opacity:.45;}
  .pal-svg .pl-lmb.has-page:hover .lm-card,.pal-svg .pl-lmb.has-page:focus-visible .lm-card{stroke-width:3.5;}
  @media (prefers-reduced-motion:reduce){ .pal-svg .pl-lmb .lm-art{transition:none;} }
  /* the tag: a glass door on the building's corner, the same size on screen at every zoom */
  .pal-svg .pl-lmb .lm-tagz{transform:scale(calc(1 / var(--pz,1)));}
  .pal-svg .lm-tag-sh{fill:rgba(20,26,55,.20);stroke:none;}
  .pal-svg .lm-tag-bg{fill:var(--lm-col);stroke:var(--lm-glass,rgba(255,255,255,.95));stroke-width:1.6;transition:fill .15s;}
  html.dark .pal-svg .lm-tag-bg{--lm-glass:rgba(24,26,38,.9);}
  .pal-svg .lm-tag-ic{fill:none;stroke:#fff;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round;}
  .pal-svg .lm-tag text{font-size:11px;font-weight:800;letter-spacing:.01em;fill:#fff;stroke:none;}
  .pal-svg .lm-tag .t-open{display:none;}
  .pal-svg .pl-lmb.has-page:hover .lm-tag-bg,.pal-svg .pl-lmb.has-page:focus-visible .lm-tag-bg{fill:#fff;stroke:var(--lm-col);}
  .pal-svg .pl-lmb.has-page:hover .lm-tag-ic,.pal-svg .pl-lmb.has-page:focus-visible .lm-tag-ic{stroke:var(--lm-col);}
  .pal-svg .pl-lmb.has-page:hover .lm-tag text,.pal-svg .pl-lmb.has-page:focus-visible .lm-tag text{fill:var(--lm-col);}
  .pal-svg .pl-lmb.has-page:hover .lm-tag .t-n,.pal-svg .pl-lmb.has-page:focus-visible .lm-tag .t-n{display:none;}
  .pal-svg .pl-lmb.has-page:hover .lm-tag .t-open,.pal-svg .pl-lmb.has-page:focus-visible .lm-tag .t-open{display:inline;}
  .pal-svg.far .lm-tag .t-u{display:none;}
  .pal-svg .pl-lmb:focus{outline:none;}
  .pal-svg .pl-lmb:focus-visible .lm-card{stroke-width:4;}
  .pal-svg .pl-lmb:focus-visible .lm-focus{display:inline;}
  .pal-svg .pl-lmb .lm-focus{display:none;fill:none;stroke:var(--lm-col,var(--accent,#6d5bd0));stroke-width:2.5px;stroke-dasharray:6 4;vector-effect:non-scaling-stroke;}
  .pal-svg .pl-lmb.is-tower{cursor:pointer;}
  .pal-svg .pl-lmb.is-tower:hover .lm-card{stroke-width:4;}
  /* the key's row for them */
"""


# ── the art ─────────────────────────────────────────────────────────────────
def _f(n: float) -> str:
    s = f"{n:.1f}"
    return s[:-2] if s.endswith(".0") else s


from . import palace_towers as _towers      # (the skyscrapers: palace_towers.py)
from . import palace_skyline as _sky        # (every building's art: the generator, one scale)
ART = _sky.build_all()
# which landmark names get which art (the page's own label, case-insensitive)
MATCH = [["usch", r"byrne|601 market|united states court ?house.*philadelphia"], ["nix", r"\bnix\b|900 market"],
         ["cjc", r"criminal justice center|1301 filbert"], ["ind", r"independence hall"], ["city", r"city hall"], ["art", r"art museum|museum of art|philadelphia museum"],
         ["frank", r"franklin institute"], ["conv", r"convention cent(er|re)"], ["stn", r"(30th|thirtieth) street station"]] + _towers.MATCH


COURT_RX = r"court ?house|courts? building|justice cent(er|re)|hall of justice|palace of justice|supreme court|court of appeals"


def art_key(l: dict) -> str:
    """The art a map landmark record gets (the page's keyOf): its name's art, else for a mapped building with a real
    height (hm m, rs roof shape) the generic building of its roof shape, else the tidy default."""
    import re
    n = str(l.get("n") or "")
    for k, p in MATCH:
        if re.search(p, n, re.I):
            return k
    try:
        hm = float(l.get("hm") or 0)
    except (TypeError, ValueError):
        hm = 0
    if str(l.get("kind") or "").lower() == "courthouse" or re.search(COURT_RX, n, re.I):
        from .palace_skyline import court_level, court_style
        return f"ct-{court_style(hm, 0, l.get('cs'))}-{court_level(n, l.get('lv'))}"
    if hm > 0:
        k = "g-" + str(l.get("rs") or "flat")
        return k if k in ART else "g-flat"
    return "gen"


def landmark_gradients() -> str:
    """The <defs> every instance shares, with {s} the svg's own id suffix (the JS fills it in)."""
    g = []
    for m in _MATS:
        g.append(f'<linearGradient id="lzg-{m}-{{s}}" x1="0" y1="0" x2="1" y2="1">'
                 f'<stop offset="0" style="stop-color:var(--lz-{m}-a)"/><stop offset="1" style="stop-color:var(--lz-{m}-b)"/></linearGradient>')
    # columns: a round shaft, lit from the left
    g.append('<linearGradient id="lzc-{s}" x1="0" y1="0" x2="1" y2="0">'
             '<stop offset="0" style="stop-color:var(--lz-trim-a)"/><stop offset=".55" style="stop-color:var(--lz-trim-b)"/>'
             '<stop offset="1" style="stop-color:var(--lz-trim-s)"/></linearGradient>')
    # the wall coursing: Flemish-bond brick (headers dark, alternating with stretchers) and ashlar blocks
    g.append('<pattern id="lzp-brick-{s}" width="8.4" height="6" patternUnits="userSpaceOnUse">'
             '<path d="M0 3H8.4M0 6H8.4M6 0V3M3 3V6M5.4 3V6" stroke="#fff" stroke-opacity=".22" stroke-width=".35" fill="none"/>'
             '<rect x="6" y="0" width="2.4" height="3" fill="#3a0c00" opacity=".24"/><rect x="3" y="3" width="2.4" height="3" fill="#3a0c00" opacity=".24"/></pattern>')
    g.append('<pattern id="lzp-ashlar-{s}" width="16" height="5.6" patternUnits="userSpaceOnUse">'
             '<path d="M0 5.6H16M8 0V5.6M0 2.8" stroke="#000" stroke-opacity=".13" stroke-width=".4" fill="none"/></pattern>')
    return "".join(g)


LANDMARK_CSS = landmark_css()


# ── the page side ───────────────────────────────────────────────────────────
_JS = r"""
(function(){
var NS='http://www.w3.org/2000/svg', XL='http://www.w3.org/1999/xlink';
var ART=__ART__, GRAD='__GRAD__';
var TALL=__TALL__, S=__SCALE__;   /* S: map px per real metre, every building (palace_skyline.SCALE) */
var MATCH=__MATCH__.map(function(m){ return [m[0], new RegExp(m[1],'i')]; });
function E(tag,attrs,parent){ var e=document.createElementNS(NS,tag); for(var k in attrs) e.setAttribute(k,attrs[k]); if(parent) parent.appendChild(e); return e; }
function artKey(n){ for(var i=0;i<MATCH.length;i++) if(MATCH[i][1].test(n)) return MATCH[i][0]; return 'gen'; }
/* a mapped building with no art of its own but a real height (l.hm m, l.fw m wide, l.rs roof shape: OSM tags) takes the
   generic building of its roof shape, stretched to its own height and width at the same scale */
/* a courthouse (kind: courthouse from the city preset, or its name) with no art of its own: the court of its type and level
   (palace_skyline.court_style / court_level, mirrored) */
var COURT=new RegExp(__COURT__,'i');
function courtLevel(n, h){ h=String(h||'').toLowerCase(); if(h==='federal'||h==='state'||h==='city') return h; n=String(n||'').toLowerCase();
  if(/united states|\bu\.? ?s\.?\b|federal|supreme court of the united states/.test(n)) return 'federal';
  if(/county|city|municipal|criminal justice|traffic|family court|housing court|magistrate/.test(n)) return 'city'; return 'state'; }
function courtStyle(hm, h){ h=String(h||'').toLowerCase(); if(h==='classical'||h==='modern'||h==='tower') return h; hm=+hm||0;
  return hm>=60?'tower':(hm && hm<=32)?'classical':hm?'modern':'classical'; }
function keyOf(l){ var n=String(l.n), k=artKey(n);
  if(k==='gen' && (String(l.kind||'').toLowerCase()==='courthouse' || COURT.test(n))) return 'ct-'+courtStyle(l.hm, l.cs)+'-'+courtLevel(n, l.lv);
  if(k==='gen' && +l.hm>0) k='g-'+(ART['g-'+(l.rs||'flat')]?(l.rs||'flat'):'flat'); return k; }
function isTall(l){ var k=keyOf(l); return TALL.indexOf(k)>=0 || (/^(g|ct)-/.test(k) && +l.hm>=60); }
/* map px per canvas metre (across, up): S both ways; a generic building stretched to the record's own height and width */
function scaleOf(l, key, a){ if(/^(g|ct)-/.test(key) && +l.hm>0){ var sy=S*(+l.hm)/a.hm; return [(+l.fw>0)?S*(+l.fw)/a.fw:sy, sy]; } return [S, S]; }
/* a landmark's card: its footprint's projected bounding box (a.fp) at the one scale — from the footprint's metres, never the
   cell count — centred across its block, standing on the block's front edge (palace_skyline.card, exactly) */
function cardBase(l){ var key=keyOf(l), a=ART[key]||ART.gen, b=l.box, k=scaleOf(l, key, a), w=(a.fp[2]-a.fp[0])*k[0], h=(a.fp[3]-a.fp[1])*k[1];
  return [(b[0]+b[2])/2-w/2, b[3]-14-h, w, h]; }
/* {name: dx}: a tower in front of / behind another in the same column slides to one side of its block (palace_skyline.stagger, exactly) */
function plan(lms){ if(lms._lzPlan) return lms._lzPlan; var out={}, placed=[];
  var ts=lms.filter(function(l){ return l.box && isTall(l); }).sort(function(p,q){ return p.box[3]-q.box[3] || p.box[0]-q.box[0] || (String(p.n)<String(q.n)?-1:String(p.n)>String(q.n)?1:0); });
  ts.forEach(function(l){ var a=ART[keyOf(l)]||ART.gen, b=l.box, C=cardBase(l), x=C[0], y=C[1], w=C[2], h=C[3];
    var room=Math.max(0, (b[2]-b[0]-28-w)/2), bw=w*.7, top=(a.hm||100)*S, gy=y+h, best=0, bo=null;
    [0, -room, room].forEach(function(dx){ var cx=x+w/2+dx, o=0;
      placed.forEach(function(q){ o+=Math.max(0, Math.min(cx+bw/2, q[1])-Math.max(cx-bw/2, q[0]))*Math.max(0, Math.min(gy, q[3])-Math.max(gy-top, q[2])); });
      if(bo===null || o<bo-1e-6){ best=dx; bo=o; } });
    var cx=x+w/2+best; placed.push([cx-bw/2, cx+bw/2, gy-top, gy]); out[l.n]=best; });
  try{ Object.defineProperty(lms, '_lzPlan', {value:out, enumerable:false, configurable:true}); }catch(e){}
  return out; }
function dxOf(lms, name){ return lms?(plan(lms)[name]||0):0; }
function cardOf(l, lms){ var C=cardBase(l); if(isTall(l)) C[0]+=dxOf(lms, l.n); return C; }
/* the shared gradients, and the building's <symbol>, in this svg's own <defs> (once each) */
function ensure(defs, sid, key){
  if(!defs._lz){ defs._lz={}; var d=E('defs',{},defs); d.innerHTML=GRAD.replace(/\{s\}/g, sid); }
  if(!defs._lz[key]){ defs._lz[key]=1; var a=ART[key];
    var s=E('symbol',{id:'lz-'+key+'-'+sid, viewBox:'-6 -8 '+(a.w+12)+' '+(a.h+14), preserveAspectRatio:'none', overflow:'visible'},defs);
    s.innerHTML=a.svg.replace(/\{s\}/g, sid); }
}
/* what is inside a landmark's page, read from the page's own Index chips (the counts those show) */
function pageInfo(pg, pn){
  var q=String(pg||'').split(':'), k=q.slice(1).join(':'), o={name:pn?pn(pg):k, count:0, unit:'', kind:'page', col:'var(--accent,#6d5bd0)'};
  if(q[0]==='index'){
    var chip=document.querySelector('[data-axis-index="'+k+'"]'), A=(window._ALTO_AXES||{})[k]||{}, c=chip&&chip.querySelector('.nav-chip-count');
    o.count=c?(parseInt(c.textContent,10)||0):(A.ids?A.ids.length:0);
    var env=chip?chip.classList.contains('env-btn'):/^env/.test(k), lab=String(A.label||o.name||'');
    o.col=env?'var(--env-color,#8a6000)':'var(--theme-color,#6d28d9)';
    o.kind=env?'cases':(/rule|procedure/i.test(lab)?'rules':'code');
    o.unit=env?(/case/i.test(lab)?'cases':(A.unit||'items')):(/rule|procedure/i.test(lab)?'rules':(A.unit||'sections'));
    if(o.count===1) o.unit=o.unit.replace(/s$/,'');
  }
  return o;
}
/* the page's icon (16 x 16): scales for cases, an open book for rules, a leaf with a section line for a code */
var ICON={cases:'M8 2.2v11.3M5 13.6h6M2.4 4.6h11.2M2.4 4.6 .9 9.2h3zM13.6 4.6l-1.5 4.6h3z', rules:'M8 4.2C6.4 3 4.4 2.8 2 3v9.2c2.4-.2 4.4 0 6 1.2 1.6-1.2 3.6-1.4 6-1.2V3c-2.4-.2-4.4 0-6 1.2zM8 4.2v9.2',
  code:'M4 1.8h5.6l3 3.2v9.2H4zM9.6 1.8V5h3M6.2 8.4h4.4M6.2 10.8h4.4', page:'M4 1.8h5.6l3 3.2v9.2H4zM9.6 1.8V5h3M6.2 8.4h4.4M6.2 10.8h4.4'};
function label(name, i){ return name+(i?' — inside: '+i.name+(i.count?', '+i.count+' '+i.unit:'')+'. Open':''); }

function draw(g, l, o){
  var b=l.box, ins=o.ins, x=b[0]+ins, y=b[1]+ins, w=b[2]-b[0]-2*ins, h=b[3]-b[1]-2*ins, c=o.color, nm=String(l.n), key=keyOf(l);
  /* a skyscraper (or any mapped building of 60 m and up) stands on a plot of one size, its card, centred on its block however
     many cells its outline covers (its building chip stands to the left of it); the tower rises above the card to its real height */
  /* the card is the building's own footprint at the one scale (the building fills it, standing on it in a 3/4 view); whatever is tall
     (a tower, City Hall's tower) rises above it as far as it really does; a tower in a column of towers slides aside (plan) */
  var tall=isTall(l), C=cardOf(l, o.all); x=C[0]; y=C[1]; w=C[2]; h=C[3];
  /* a block of a turned (tilted) district: the card turns with its streets (an SVG transform attribute, never CSS), the building stays upright */
  var base=g; if(+l.a){ base=E('g',{'class':'lm-base', transform:'rotate('+(+l.a)+' '+((b[0]+b[2])/2)+' '+((b[1]+b[3])/2)+')'},g); }
  var info=l.page?pageInfo(l.page, o.pageName):null;
  g.style.setProperty('--lm-edge', c); g.style.setProperty('--lz-line', c); g.style.setProperty('--lm-col', info?info.col:c); if(info) g.style.setProperty('--lz-door', info.col);
  /* the card: a glass slab with a thickness, lit from the top left, a soft shadow to the lower right */
  E('rect',{'class':'lm-shadow', x:x+7, y:y+10, width:w, height:h, rx:9},base);
  E('rect',{'class':'lm-slab', x:x+3, y:y+5, width:w, height:h, rx:9, fill:c},base);
  if(info){ E('rect',{'class':'lm-glow', x:x-3, y:y-3, width:w+6, height:h+6, rx:12},base); E('rect',{'class':'lm-glow2', x:x-1, y:y-1, width:w+2, height:h+2, rx:10},base); }
  E('rect',{'class':'lm-card', x:x, y:y, width:w, height:h, rx:9, stroke:c},base);
  E('path',{'class':'lm-sheen', d:'M'+(x+11)+' '+(y+2.5)+'H'+(x+w-11)},base);
  var strip=E('rect',{'class':'lm-strip', rx:5},base);
  /* the building */
  ensure(o.defs, o.sid, key);
  var art=E('g',{'class':'lm-art'},g), use=E('use',{href:'#lz-'+key+'-'+o.sid},art); use.setAttributeNS(XL,'xlink:href','#lz-'+key+'-'+o.sid);
  var name=E('text',{'class':'lm-name','text-anchor':'middle'},g), sub=info?E('text',{'class':'lm-sub','text-anchor':'middle'},g):null;
  /* the tag (a page's way in): a glass door on the corner, drawn in screen pixels */
  var tag=null, tbg=null, tn=null, tu=null, to=null;
  if(info){
    var tp=E('g',{'class':'lm-tagp'},g), tz=E('g',{'class':'lm-tagz'},tp); tag=E('g',{'class':'lm-tag'},tz);
    E('rect',{'class':'lm-tag-sh', rx:10, height:20, y:-7},tag); tbg=E('rect',{'class':'lm-tag-bg', rx:10, height:20, y:-10},tag);
    E('path',{'class':'lm-tag-ic', d:ICON[info.kind]||ICON.page, transform:'translate(6 -8) scale(1)'},tag);
    tn=E('text',{'class':'t-n', x:24, y:4},tag); var tc=E('tspan',{'class':'t-c'},tn); tc.textContent=info.count?String(info.count):'';
    tu=E('tspan',{'class':'t-u'},tn); tu.textContent=info.count?' '+info.unit:'Inside';
    if(!info.count) tc.textContent='';
    to=E('text',{'class':'t-open', x:24, y:4},tag); to.textContent='Open ›';
    tag._p=tp;
  }
  E('rect',{'class':'lm-focus', x:x-6, y:y-6, width:w+12, height:h+12, rx:14},g);
  g._lm={tall:tall,key:key,l:l,tower:o.tower||null,x:x,y:y,w:w,h:h,name:nm,info:info,page:l.page,strip:strip,art:art,use:use,nameT:name,sub:sub,tag:tag,tbg:tbg,tn:tn,to:to,pn:o.pageName};
  /* keyboard and screen readers */
  g.setAttribute('aria-label', label(nm, info));
  if(info){ g.setAttribute('role','link'); g.setAttribute('tabindex','0');
    g.addEventListener('keydown', function(e){ if(e.key==='Enter' || e.key===' '){ e.preventDefault(); e.stopPropagation(); o.open(l.page); } }); }
  else if(o.tower){ g.classList.add('is-tower'); g.setAttribute('role','img'); g.setAttribute('aria-label', nm+' — tower of '+o.tower.num+' '+o.tower.title+', '+o.tower.top+' floors'); }
  else g.setAttribute('role','img');
}
/* the layout that depends on the zoom: names and tags keep a size on the screen, so where they would not
   fit inside a small card the name hangs under it; the building takes what is left */
function relayout(svg, Z){
  Z=Z||1; var u=1/Z, far=Z<.42, near=Z>=.8;
  svg.querySelectorAll('.pl-lmb').forEach(function(g){ var L=g._lm; if(!L) return;
    if(L.page && L.info && !L.info.count){ L.info=pageInfo(L.page, L.pn); g.setAttribute('aria-label', label(L.name, L.info)); }
    var x=L.x, y=L.y, w=L.w, h=L.h, n=L.name.length, fit=Math.min(26, (L.tall?200:w)*.94/(Math.max(n,3)*.6));
    g.style.setProperty('--lm-nat', fit.toFixed(1)+'px');
    var fn=Math.min(Math.max(11.5*u, fit), 21*u), words=L.name.split(' '), lines=[L.name];
    if(n*.6*fn>w*.98 && words.length>1){ var half=Math.ceil(words.length/2); lines=[words.slice(0,half).join(' '), words.slice(half).join(' ')]; }
    var wide=Math.max.apply(null, lines.map(function(s){ return s.length; }))*.6*fn;
    var subH=(L.sub && near)?13*u:0, stripH=lines.length*fn*1.22+fn*.42+subH, hang=true;   /* the card hugs the building: its name hangs under it */
    var cx=x+w/2, top=y-h*.22, bottom;
    while(L.nameT.firstChild) L.nameT.removeChild(L.nameT.firstChild);
    if(hang){
      lines=[L.name]; L.nameT.setAttribute('class','lm-name'); L.nameT.setAttribute('x',cx);
      var ts=document.createElementNS(NS,'tspan'); ts.setAttribute('x',cx); ts.setAttribute('dy','0'); ts.textContent=L.name; L.nameT.appendChild(ts);
      L.nameT.setAttribute('y', y+h+fn*1.02+2*u); L.strip.setAttribute('width',0); L.strip.setAttribute('height',0); bottom=y+h-5;
      if(L.sub) L.sub.setAttribute('display','none');
    } else {
      L.nameT.setAttribute('class','lm-name in'); var y0=y+h-stripH+fn*.42*.5+fn*.88;
      lines.forEach(function(s,i){ var ts=document.createElementNS(NS,'tspan'); ts.setAttribute('x',cx); ts.setAttribute('y', y0+i*fn*1.22); ts.textContent=s; L.nameT.appendChild(ts); });
      L.strip.setAttribute('x',x+3); L.strip.setAttribute('y',y+h-stripH-1); L.strip.setAttribute('width',w-6); L.strip.setAttribute('height',stripH-2);
      bottom=y+h-stripH-3*u;
      if(L.sub){ if(near){ L.sub.removeAttribute('display'); L.sub.setAttribute('x',cx); L.sub.setAttribute('y', y+h-6*u-1);
        var t1='Inside: '+L.info.name, t2=L.info.count?L.info.count+' '+L.info.unit+' inside':'', fitC=w/(5.7*u);
        t1=t1.length<=fitC?t1:(t2.length<=fitC?t2:''); L.sub.textContent=t1; } else L.sub.setAttribute('display','none'); }
    }
    /* the building at the ONE scale: its footprint (a.fp in the symbol) laid exactly on its card */
    var a=ART[L.key], k=scaleOf(L.l, L.key, a), fp=a.fp;
    L.use.setAttribute('x', L.x-(fp[0]+6)*k[0]); L.use.setAttribute('y', L.y-(fp[1]+8)*k[1]); L.use.setAttribute('width', (a.w+12)*k[0]); L.use.setAttribute('height', (a.h+14)*k[1]);
    if(L.tag){ var full=L.info.count?(String(L.info.count).length+(far?0:L.info.unit.length+1)):6, tw=Math.max(full,6)*6.6+34;
      L.tbg.setAttribute('width',tw); L.tag.querySelector('.lm-tag-sh').setAttribute('width',tw);
      L.tag.querySelector('.lm-tag-sh').setAttribute('x',2); L.tag.querySelector('.lm-tag-sh').setAttribute('y',-5);
      L.tag._p.setAttribute('transform','translate('+(x+w)+' '+y+')'); L.tag.setAttribute('transform','translate('+(-tw-3)+' 0)'); }
  });
}
function tip(g, esc, pn){
  var L=g._lm, nm=g.getAttribute('data-name'), pg=g.getAttribute('data-page'), i=L&&L.info;
  if(L && L.tower && !pg) return '<b>'+esc(nm)+'</b><small>Tower of '+esc(L.tower.num+' '+L.tower.title)+' · '+L.tower.top+' floors</small><small><b>Click to ride the elevator ›</b></small>';
  if(!pg) return '<b>'+esc(nm)+'</b>';
  if(!i) i=pageInfo(pg, pn);
  return '<b>'+esc(nm)+'</b><small>Inside: '+esc(i.name)+(i.count?' · '+i.count+' '+esc(i.unit):'')+'</small><small><b>Click to open ›</b></small>';
}
function keyRow(){
  var sw='<svg width="26" height="14" viewBox="0 0 34 18" aria-hidden="true" style="flex:none"><rect x="2" y="2" width="30" height="14" rx="7" fill="rgba(255,255,255,.95)" stroke="var(--theme-color,#6d28d9)" stroke-width="1.6"/>'
    +'<g transform="translate(5 1) scale(.95)" fill="none" stroke="var(--theme-color,#6d28d9)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="'+ICON.rules+'"/></g>'
    +'<rect x="21" y="6" width="8" height="2" rx="1" fill="var(--theme-color,#6d28d9)"/><rect x="21" y="10" width="6" height="2" rx="1" fill="var(--theme-color,#6d28d9)" opacity=".6"/></svg>';
  return '<div class="pk-row">'+sw+'<div>Landmark with reference material inside <small>A glowing tag on a building says what is inside and how many (20 rules, 193 cases). Point at it for Open; click to go in. Tab to a tag and press Enter.</small></div></div>';
}
window._palLm={draw:draw, relayout:relayout, tip:tip, keyRow:keyRow, pageInfo:pageInfo, artKey:artKey, cardOf:cardOf, dx:dxOf, S:S};
})();
"""


def landmark_js() -> str:
    return (_JS.replace("__ART__", json.dumps(ART, separators=(",", ":")))
            .replace("__GRAD__", landmark_gradients())
            .replace("__MATCH__", json.dumps(MATCH))
            .replace("__TALL__", json.dumps(sorted(_towers.FLOORS)))
            .replace("__SCALE__", json.dumps(_sky.SCALE))
            .replace("__COURT__", json.dumps(COURT_RX)))


LANDMARK_JS = landmark_js()
