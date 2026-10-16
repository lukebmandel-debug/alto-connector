"""Fill-in (PROTOTYPE, off by default): the rest of the city as simulated buildings, on a slider.

The Mind Palace draws only the user's own buildings (numbered cards on lots), the landmark
art and the towers. Fill-in adds the city's real building footprints (OpenStreetMap
building=* ways), carried onto the graph-paper grid by the same piecewise-linear Mapping
the streets go through, clipped inside their block, and drawn as calm frosted glass that
never looks like (and never stands on) one of the user's buildings.

  Level 0  Landmarks       nothing added (today's page)
  Level 1  Skyline         towers: height >= 60 m (or >= 18 storeys)
  Level 2  Notable         + tall (>= 25 m), named non-houses, big civic / large footprints
  Level 3  Most            + every footprint >= 300 m2 or >= 14 m
  Level 4  Every building  + every footprint >= 20 m2 (row houses)

Data: fill_data(raw_buildings, map) -> {"v", "ins", "ch", "s": [[tier, h, x0, y0, dx, dy, ...]], "n": {i: name}}
(grid px, ints, deltas), packed with the city as brief.palace.fill_z. Nothing is emitted unless
fill_z is present, so a page without it is byte-identical to before.
"""
from __future__ import annotations

import math
from bisect import bisect_right

from .. import palace_map as pmap
from .palace_grid import mapping_from          # read-only use: the grid's own Mapping

TIER_NAMES = ["Landmarks", "Skyline", "Notable", "Most", "Every building"]
CIVIC = {"cathedral", "church", "hospital", "university", "college", "school", "stadium", "train_station",
         "museum", "civic", "government", "public", "hotel", "office", "commercial", "retail", "transportation"}
HOUSES = {"house", "terrace", "semidetached_house", "detached", "garage", "garages", "shed", "roof", "hut"}


def _num(v):
    try:
        return float(str(v).replace(",", ".").split()[0])
    except (TypeError, ValueError, IndexError):
        return None


def height_of(tags) -> float:
    h = _num(tags.get("height"))
    lv = _num(tags.get("building:levels"))
    return max(h or 0.0, (lv or 0.0) * 3.3)


def tier_of(tags, area_m2: float, h: float):
    """1..4 (the lowest level that shows it), or None (too small to draw)."""
    if area_m2 < 20:
        return None
    b = str(tags.get("building") or tags.get("building:part") or "yes")
    if h >= 60:
        return 1
    if h >= 25 or area_m2 >= 2500 or (b in CIVIC and area_m2 >= 600) or (tags.get("name") and b not in HOUSES and area_m2 >= 150):
        return 2
    if area_m2 >= 300 or h >= 14:
        return 3
    return 4


def _rings(e):
    if e.get("type") == "way":
        g = e.get("geometry") or []
        return [[(p["lat"], p["lon"]) for p in g if p]] if len(g) >= 3 else []
    out = []
    for m in e.get("members") or ():
        if m.get("role") == "outer" and len(m.get("geometry") or []) >= 3:
            out.append([(p["lat"], p["lon"]) for p in m["geometry"] if p])
    return out


def _area_m2(ring):
    lat0 = ring[0][0]
    kx, ky = 111320 * math.cos(math.radians(lat0)), 110574
    pts = [(lon * kx, lat * ky) for lat, lon in ring]
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))) / 2


def buildings(raw):
    """[(ring [(lat, lon)], tags, area m2, height m)] — a building:part's height lifts the building it stands in."""
    els = raw.get("elements") or []
    parts, out = [], []
    for e in els:
        t = e.get("tags") or {}
        rings = _rings(e)
        if not rings:
            continue
        if "building" not in t:
            if "building:part" in t:
                r = rings[0]
                parts.append((sum(p[0] for p in r) / len(r), sum(p[1] for p in r) / len(r), height_of(t)))
            continue
        for r in rings:
            out.append([r, t, _area_m2(r), height_of(t)])
    # parts: lift the building whose box holds the part's centre (towers keep their height in their parts)
    if parts:
        idx = {}
        for k, (r, *_x) in enumerate(out):
            la, lo = [p[0] for p in r], [p[1] for p in r]
            idx[k] = (min(la), min(lo), max(la), max(lo))
        cell: dict = {}
        for k, (a, b, c, d) in idx.items():
            cell.setdefault((int(a * 500), int(b * 500)), []).append(k)
        for la, lo, h in parts:
            for k in cell.get((int(la * 500), int(lo * 500)), []):
                a, b, c, d = idx[k]
                if a <= la <= c and b <= lo <= d and h > out[k][3]:
                    out[k][3] = h
    return out


def _clip(poly, x0, y0, x1, y1):
    for axis, val, ge in ((0, x0, True), (0, x1, False), (1, y0, True), (1, y1, False)):
        poly = pmap._clip_edge(poly, axis, val, ge)
        if not poly:
            return []
    return poly if len(poly) >= 3 else []


def fill_data(raw, m, blocks=None, ins: float = 12.0, chunk: int = 4) -> dict:
    """Footprints on the grid: each building carried by the grid's Mapping into the block (grid cell)
    its centre falls in, clipped `ins` px inside the block's streets; none in a landmark's block,
    none in a cell that is not a block (a drawn tile, or a block that has lots: streets on three sides)."""
    bbox, scale = m["bbox"], m.get("scale", 1.0)
    mp = mapping_from(m["grid"])
    xg, yg = m["grid"]["xg"], m["grid"]["yg"]
    tiles = {(round(t[0]), round(t[1])) for t in m.get("tiles") or []}
    for bl in blocks or ():
        i, j = bisect_right(xg, bl["x"]) - 1, bisect_right(yg, bl["y"]) - 1
        if 0 <= i < len(xg) - 1 and 0 <= j < len(yg) - 1:
            tiles.add((round(xg[i]), round(yg[j])))
    lmb = [l["box"] for l in m.get("landmarks") or [] if l.get("box")]
    shapes, names = [], {}
    for ring, tags, area, h in buildings(raw):
        t = tier_of(tags, area, h)
        if t is None:
            continue
        g = [mp(*pmap.project(la, lo, bbox, scale)) for la, lo in ring]
        if len(g) > 3 and g[0] == g[-1]:
            g = g[:-1]
        cx, cy = sum(p[0] for p in g) / len(g), sum(p[1] for p in g) / len(g)
        i, j = bisect_right(xg, cx) - 1, bisect_right(yg, cy) - 1
        if not (0 <= i < len(xg) - 1 and 0 <= j < len(yg) - 1) or (round(xg[i]), round(yg[j])) not in tiles:
            continue
        x0, y0, x1, y1 = xg[i], yg[j], xg[i + 1], yg[j + 1]
        if any(b[0] < x1 and b[2] > x0 and b[1] < y1 and b[3] > y0 for b in lmb):
            continue
        g = _clip(g, x0 + ins, y0 + ins, x1 - ins, y1 - ins)
        if not g:
            continue
        g = pmap.simplify_ring(g, 1.0) if len(g) > 4 else g
        q = []
        for x, y in g:
            p = (int(round(x)), int(round(y)))
            if not q or p != q[-1]:
                q.append(p)
        if len(q) > 2 and q[0] == q[-1]:
            q.pop()
        if len(q) < 3 or abs(pmap.ring_area(q)) < 6:
            continue
        flat = [q[0][0], q[0][1]]
        for (ax, ay), (bx, by) in zip(q, q[1:]):
            flat += [bx - ax, by - ay]
        if t <= 2 and tags.get("name"):
            names[len(shapes)] = str(tags["name"])[:60]
        shapes.append([t, int(round(min(h, 400))), *flat])
    order = sorted(range(len(shapes)), key=lambda k: (shapes[k][0], shapes[k][3], shapes[k][2]))
    remap = {o: n for n, o in enumerate(order)}
    return {"v": 1, "ins": ins, "ch": [chunk * (xg[1] - xg[0]) if len(xg) > 1 else 960, chunk * (yg[1] - yg[0]) if len(yg) > 1 else 680],
            "s": [shapes[o] for o in order], "n": {str(remap[k]): v for k, v in names.items()}}


def counts(fill) -> list:
    """Shapes each level adds: [L1, L2, L3, L4]."""
    c = [0, 0, 0, 0]
    for s in fill.get("s") or []:
        c[s[0] - 1] += 1
    return c


# ── the page (only when the palace has fill_z) ─────────────────────────────
FILL_CSS = r"""
  .pal-svg .pl-fill{pointer-events:none;}
  .pal-svg .pl-fill .f-body{fill:rgba(255,255,255,.58);stroke-linejoin:round;stroke-width:calc(var(--tw,1) * 1.15px);stroke-opacity:.62;}
  .pal-svg .pl-fill .f-side{fill:rgba(28,34,62,.13);stroke:none;}
  .pal-svg .pl-fill .ft1 .f-body,.pal-svg .pl-fill .ft2 .f-body{fill:rgba(255,255,255,.72);stroke-opacity:.78;}
  .pal-svg .pl-fill .ft3 .f-body,.pal-svg .pl-fill .ft4 .f-body{fill:rgba(255,255,255,.46);stroke-opacity:.5;}
  html.dark .pal-svg .pl-fill .f-body{fill:rgba(60,64,84,.5);}
  html.dark .pal-svg .pl-fill .f-side{fill:rgba(0,0,0,.28);}
  html.alto-editing .pal-svg .pl-fill{opacity:.45;}
  #pal-key .pk-fill{display:block;padding:6px 3px 4px;}
  #pal-key .pk-fill .pkf-h{display:flex;justify-content:space-between;align-items:baseline;gap:8px;}
  #pal-key .pk-fill .pkf-h b{font-weight:650;}
  #pal-key .pk-fill .pkf-h small{opacity:.7;}
  #pal-key .pk-fill input[type=range]{width:100%;margin:6px 0 2px;accent-color:var(--accent,#5b6cff);}
  #pal-key .pk-fill .pkf-ticks{display:flex;justify-content:space-between;font-size:10px;opacity:.6;}
"""

# function definitions, spliced inside the palace page's closure (palace_js below)
FILL_FUNCS = r"""
/* ── fill-in (palace_fillin.py): the rest of the city as simulated buildings, by level ── */
var FILL=window._ALTO_FILL||null, FILL_KEY='alto-palace-fill:'+location.pathname, FILL_NAMES=['Landmarks','Skyline','Notable','Most','Every building'];
var fillLevel=(function(){ var v=null; try{ v=localStorage.getItem(FILL_KEY); }catch(e){} v=v==null?(FILL&&FILL.lvl)||0:+v; return Math.max(0,Math.min(4,v|0)); })();
/* a building of the user's stands on its lot; nothing simulated touches it (8 px of clear glass round it) */
function fillTaken(){ var r=[]; Object.keys(P.at||{}).forEach(function(id){ var L=lot(P.at[id]); if(L) r.push([L[0]-L[2]/2-8, L[1]-L[3]/2-8, L[0]+L[2]/2+8, L[1]+L[3]/2+8]); }); return r; }
function fillSig(){ return JSON.stringify(P.at||{}); }
function fillDraw(svg){ var t0=performance.now(); try{ fillDraw0(svg); } finally { window._fillMs=performance.now()-t0; } }
function fillDraw0(svg){
  var old=svg.querySelector(':scope > .pl-fill'); if(!FILL || !FILL.s){ if(old) old.remove(); return; }
  var g=el('g',{'class':'pl-fill'}), CH=FILL.ch, taken=fillTaken(), grid={};
  taken.forEach(function(b,k){ for(var i=Math.floor(b[0]/CH[0]);i<=Math.floor(b[2]/CH[0]);i++) for(var j=Math.floor(b[1]/CH[1]);j<=Math.floor(b[3]/CH[1]);j++) (grid[i+','+j]=grid[i+','+j]||[]).push(b); });
  var tiers=[null,{},{},{},{}];
  FILL.s.forEach(function(s){ var t=s[0], h=s[1], x=s[2], y=s[3], xs=[x], ys=[y], x0=x, y0=y, x1=x, y1=y;
    for(var i=4;i<s.length;i+=2){ x+=s[i]; y+=s[i+1]; xs.push(x); ys.push(y); if(x<x0)x0=x; if(x>x1)x1=x; if(y<y0)y0=y; if(y>y1)y1=y; }
    var ci=Math.floor((x0+x1)/2/CH[0]), cj=Math.floor((y0+y1)/2/CH[1]), key=ci+','+cj;
    var tk=grid[key]; if(tk) for(var q=0;q<tk.length;q++){ var b=tk[q]; if(x0<b[2] && x1>b[0] && y0<b[3] && y1>b[1]) return; }
    var u=distAt((x0+x1)/2,(y0+y1)/2), ck=key+'|'+u, c=tiers[t][ck]||(tiers[t][ck]={u:u, b:'', s:'', ci:ci, cj:cj});
    var d='M'+xs[0]+' '+ys[0]; for(var k=1;k<xs.length;k++) d+='L'+xs[k]+' '+ys[k]; d+='Z'; c.b+=d;
    if(t<=2 && h>0){ var o=Math.max(1.5,Math.min(9,h/22)), e='M'+(xs[0]+o)+' '+(ys[0]+o); for(k=1;k<xs.length;k++) e+='L'+(xs[k]+o)+' '+(ys[k]+o); c.s+=e+'Z'; } });
  for(var t=1;t<=4;t++){ var tg=el('g',{'class':'ft ft'+t},g), ch={};
    Object.keys(tiers[t]).forEach(function(k){ var c=tiers[t][k], ck=c.ci+','+c.cj, cg=ch[ck]||(ch[ck]=el('g',{'data-c':ck},tg));
      var col=tubeCol(dcol(c.u==null?null:c.u)||NEUTRAL());
      if(c.s) el('path',{'class':'f-side', d:c.s},cg);
      el('path',{'class':'f-body', d:c.b, stroke:col},cg); }); }
  var anchor=svg.querySelector(':scope > .pl-river-g');
  if(old) old.remove(); svg.insertBefore(g, anchor||null); svg._fill=g; svg._fillSig=fillSig(); fillLOD(svg);
}
/* level of detail: a level shows only from the zoom its smallest buildings are a few px across; only the chunks near the window are drawn */
var FILL_ZMIN=[0, 0, 0, .07, .15];
function fillLOD(svg){ svg=svg||svgD; var g=svg&&svg._fill; if(!g) return;
  var z=svg===svgD?(Z||1):(MM.z||1), cv=svg===svgD?document.getElementById('canvas'):null, vis=null;
  if(cv && z && !window._fillNoCull){ var m=.6, vx0=cv.scrollLeft/z-MX, vy0=(cv.scrollTop)/z-MY, vw=cv.clientWidth/z, vh=cv.clientHeight/z; vis=[vx0-vw*m, vy0-vh*m, vx0+vw*(1+m), vy0+vh*(1+m)]; }
  var CH=FILL.ch;
  [].forEach.call(g.children, function(tg, k){ var t=k+1, on=t<=fillLevel && z>=FILL_ZMIN[t]; tg.style.display=on?'':'none'; if(!on || !vis) return;
    [].forEach.call(tg.children, function(c){ var p=c.getAttribute('data-c').split(','), x0=+p[0]*CH[0], y0=+p[1]*CH[1];
      var inV=x0<vis[2] && x0+CH[0]>vis[0] && y0<vis[3] && y0+CH[1]>vis[1]; c.style.display=inV?'':'none'; }); }); }
var fillScrollT=null;
function fillWire(k){
  if(!FILL) return;
  var cv=document.getElementById('canvas'); if(cv) cv.addEventListener('scroll', function(){ if(PV) return; clearTimeout(fillScrollT); fillScrollT=setTimeout(function(){ fillLOD(svgD); }, 90); }, {passive:true});
  var r=k.querySelector('.pk-fill input'), lab=k.querySelector('.pk-fill .pkf-v'); if(!r) return;
  r.addEventListener('input', function(){ fillLevel=+r.value; if(lab) lab.textContent=FILL_NAMES[fillLevel]; try{ localStorage.setItem(FILL_KEY, String(fillLevel)); }catch(e){}
    fillLOD(svgD); if(MM.svg) fillLOD(MM.svg); }); }
function fillKeyRow(){ if(!FILL) return '';
  return '<div class="pk-sep"></div><label class="pk-fill"><span class="pkf-h"><b>Fill in the city</b><small class="pkf-v">'+FILL_NAMES[fillLevel]+'</small></span>'
    +'<input type="range" min="0" max="4" step="1" value="'+fillLevel+'" aria-label="How much of the city to fill in with buildings">'
    +'<span class="pkf-ticks"><span>Landmarks</span><span>Every building</span></span></label>'; }
"""

# where the hooks go in PALACE_JS (each anchor must be found exactly once)
_HOOKS = [
    ("/* ── the board: the city under the cards, at the current zoom ── */", FILL_FUNCS + "\n/* ── the board: the city under the cards, at the current zoom ── */"),
    ("  drawBuildings(svg);\n  sizeChips(svg);", "  fillDraw(svg);\n  drawBuildings(svg);\n  sizeChips(svg);"),
    ("function drawBuildings(svg){\n  var g=svg._b; if(!g) return; g.innerHTML='';",
     "function drawBuildings(svg){\n  var g=svg._b; if(!g) return; g.innerHTML=''; if(svg._fill && svg._fillSig!==fillSig()) fillDraw(svg);"),
    ("  setClasses(); if(svgD) sizeChips(svgD);", "  setClasses(); if(svgD) sizeChips(svgD); if(svgD) fillLOD(svgD);"),
    ("  h+=window._palLm.keyRow();", "  h+=window._palLm.keyRow();\n  h+=fillKeyRow();"),
    ("  window._altoKeyToggle(k, 'alto-palace-key', 'Key to the city');", "  window._altoKeyToggle(k, 'alto-palace-key', 'Key to the city'); fillWire(k);"),
]


def patch_js(js: str) -> str:
    for a, b in _HOOKS:
        if js.count(a) != 1:
            raise RuntimeError("palace_fillin: hook anchor not found once: " + a[:60])
        js = js.replace(a, b)
    return js
