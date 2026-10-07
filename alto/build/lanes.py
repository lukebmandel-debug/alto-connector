"""The horizontal timeline (brief.mode "lanes"): time runs left to right.

One main line runs through the middle of a page that scrolls sideways. Every
other line is an off-branch of it: a storyline (a character, a place, a
thread) that runs alongside the main line at the same time, branching off it
at an event (`from`) and/or converging back into it at a later one (`to`).
A flashback is a line whose events are far back in time that converges into
the main line where the story brings it up.

Data:
  brief.lines  [{id, label, color?, side?: "above"|"below", from?: node id,
                 to?: node id}] — the main line is implicit (id "main",
                 label brief.main_line).
  node.line    the line it is on ("" / "main" = the main line).
  node.when    when it happened, as the material says it: "1842",
               "1842-03-15", "March 1842", "500 BC", "Year 3", "Day 12".

Time is drawn to scale wherever events are dated; a long empty stretch is
squeezed and marked ≈ so a flashback 40 years back does not leave metres of
nothing. Undated events are spaced evenly by their order between the dated
ones around them. Cards hang off their line on a short stem at their exact
time, stacked in tiers when they would overlap, so the scale never bends.

The page side (LANES_JS) runs inside the engine's initLayout once every card
has been measured (engine patch lanes-layout-hook) and replaces the engine's
vertical layout on desktop; phones keep the engine's card-by-card view, in
the same order. Everything shown is the material's own words.
"""
from __future__ import annotations

import re

from .brief import BriefError
from .sanitize import js_json

MAIN = "main"
SIDES = ("above", "below")

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_DAYS_IN = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def parse_when(s) -> "float | None":
    """A sortable number for a `when`, or None when it names no time.

    ISO-ish dates and "March 1842" / "15 March 1842" become fractional years;
    "500 BC" / "500 BCE" is -500; otherwise the first number in it ("Year 3",
    "Day 12", "Ch. 4" → 3, 12, 4). Mixing kinds (years with days) in one
    timeline is the author's call — the scale just follows the numbers."""
    if s is None:
        return None
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        return float(s)
    t = str(s).strip().lower()
    if not t:
        return None
    bc = re.search(r"(\d+)\s*b\.?\s?c\.?(?:e\.?)?(?![a-z])", t)
    if bc:
        return -float(bc.group(1))
    m = re.match(r"^(-?\d{1,6})(?:-(\d{1,2}))?(?:-(\d{1,2}))?(?:[t ].*)?$", t)
    if m:
        y = int(m.group(1))
        mo = int(m.group(2)) if m.group(2) else 0
        d = int(m.group(3)) if m.group(3) else 0
        return _frac(y, mo, d)
    mon = re.search(r"\b(" + "|".join(_MONTHS) + r")[a-z]*\.?\b", t)
    yr = re.search(r"\b(\d{3,4})\b", t)
    if mon and yr:
        day = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\b", t.replace(yr.group(1), ""))
        return _frac(int(yr.group(1)), _MONTHS[mon.group(1)], int(day.group(1)) if day else 0)
    n = re.search(r"-?\d+(?:\.\d+)?", t)
    return float(n.group(0)) if n else None


def _frac(y: int, mo: int, d: int) -> float:
    if not mo:
        return float(y)
    mo = max(1, min(12, mo))
    days = sum(_DAYS_IN[:mo - 1]) + max(0, min(31, d) - 1 if d else 0)
    return y + days / 365.0


def check_lines(b, warnings: list) -> None:
    """The brief's lines: shape, ids, sides. Which nodes they name is checked
    with the nodes (check_nodes)."""
    lines = b.lines
    if not isinstance(lines, list):
        raise BriefError("lines: must be a list of {id, label, color?, side?, from?, to?}")
    if lines and b.mode != "lanes":
        raise BriefError("lines need mode 'lanes': they are the horizontal timeline's storylines")
    seen = set()
    for i, ln in enumerate(lines):
        if not isinstance(ln, dict):
            raise BriefError(f"lines[{i}]: must be an object")
        lid = str(ln.get("id") or "").strip()
        if not lid or not re.match(r"^[a-z0-9][a-z0-9_-]{0,40}$", lid):
            raise BriefError(f"lines[{i}]: id {lid!r} must be a short lowercase slug")
        if lid == MAIN:
            raise BriefError("lines: 'main' is the main line itself — don't list it")
        if lid in seen:
            raise BriefError(f"lines: id {lid!r} is used twice")
        seen.add(lid)
        if not str(ln.get("label") or "").strip():
            raise BriefError(f"line {lid}: needs a label (what the line follows)")
        unknown = set(ln) - {"id", "label", "color", "side", "from", "to"}
        if unknown:
            raise BriefError(f"line {lid}: unknown keys {sorted(unknown)}")
        if ln.get("side") not in (None, "") + SIDES:
            raise BriefError(f"line {lid}: side must be 'above' or 'below'")
        c = ln.get("color")
        if c and not re.match(r"^#[0-9a-fA-F]{6}$", str(c)):
            raise BriefError(f"line {lid}: color must be #rrggbb")


def check_nodes(b, nodes, warnings: list) -> None:
    """Each event is on a known line, a line's from/to name events on another
    line, and its convergence comes after where it branched off."""
    if b.mode != "lanes":
        for n in nodes:
            if n.line or n.when:
                raise BriefError(f"node {n.id}: line / when need mode 'lanes'")
        return
    by = {n.id: n for n in nodes}
    lids = {ln["id"] for ln in b.lines}
    on = {}
    undated = []
    for n in nodes:
        ln = n.line or MAIN
        if ln != MAIN and ln not in lids:
            raise BriefError(f"node {n.id}: line {n.line!r} is not one of the brief's lines "
                             f"({', '.join(sorted(lids)) or 'none yet — add it with lines'})")
        on.setdefault(ln, []).append(n)
        if n.when and parse_when(n.when) is None:
            warnings.append(f"node {n.id}: when {n.when!r} names no time it can place — "
                            "it is spaced by its order instead")
        if not n.when:
            undated.append(n.id)
    for ln in b.lines:
        lid = ln["id"]
        for k in ("from", "to"):
            v = ln.get(k)
            if not v:
                continue
            if v not in by:
                raise BriefError(f"line {lid}: {k} {v!r} is not a node")
            if (by[v].line or MAIN) == lid:
                raise BriefError(f"line {lid}: {k} {v!r} is on the line itself — it must be an "
                                 "event on the line it branches from / converges into")
        if not on.get(lid) and not (ln.get("from") and ln.get("to")):
            warnings.append(f"line {lid}: has no events yet")
        f, t = parse_when(by[ln["from"]].when) if ln.get("from") else None, \
            parse_when(by[ln["to"]].when) if ln.get("to") else None
        if f is not None and t is not None and t < f:
            raise BriefError(f"line {lid}: converges ({ln['to']}) before it branches off ({ln['from']})")
    if undated and len(undated) < len(nodes):
        warnings.append(f"{len(undated)} event(s) have no `when` and are spaced by their order "
                        f"between the dated ones: {', '.join(undated[:8])}"
                        + ("…" if len(undated) > 8 else ""))


_PALETTE = ["#e07a5f", "#3d9a8b", "#8a6fd1", "#d4a017", "#4a90d9", "#c2577a", "#5a9e4b", "#b8763e"]


def norm_line(ln: dict, i: int) -> dict:
    """A line as the page shows it: every key, defaults filled (manual edit
    mode compares and stores lines in this form)."""
    return {"id": ln["id"], "label": ln.get("label") or "",
            "color": ln.get("color") or _PALETTE[i % len(_PALETTE)],
            "side": ln.get("side") or SIDES[i % 2],
            "from": ln.get("from") or "", "to": ln.get("to") or ""}


def lanes_data(b, nodes) -> str:
    """window._ALTO_LANES — what the page needs to lay the lines out."""
    lines = [norm_line(ln, i) for i, ln in enumerate(b.lines)]
    ev = {}
    for n in nodes:
        ev[n.id] = {"l": n.line or MAIN, "w": n.when or "", "t": parse_when(n.when)}
    return ("\nwindow._ALTO_LANES=" + js_json({"main": b.main_line or "", "lines": lines, "ev": ev},
                                               separators=(",", ":")) + ";")


LANES_CSS = """
  html.alto-lanes:not(.mobile) #world{margin:0 !important;}
  html.alto-lanes:not(.mobile) #glass-slab{left:0 !important;transform:none !important;width:var(--lanes-w,1700px) !important;}
  html.alto-lanes:not(.mobile) #world .phase-band,html.alto-lanes:not(.mobile) #world .phase-label-float,html.alto-lanes:not(.mobile) #world .unit-bar{display:none !important;}
  html.alto-lanes:not(.mobile) #river-svg{display:none !important;}
  #lanes-svg{position:absolute;left:0;top:0;z-index:6;pointer-events:none;overflow:visible;}
  html.mobile #lanes-svg,html.mobile .lanes-unit,html.mobile .lanes-tag{display:none !important;}
  #lanes-svg .ln-main{stroke:var(--accent);stroke-width:6;fill:none;stroke-linecap:round;}
  #lanes-svg .ln-br{stroke-width:4;fill:none;stroke-linecap:round;}
  #lanes-svg .ln-wait{stroke-dasharray:9 7;stroke-width:3.5;}
  #lanes-svg .ln-hit{stroke:transparent;stroke-width:22;fill:none;pointer-events:stroke;cursor:pointer;}
  #lanes-svg g{transition:opacity .2s;}
  .node[data-ln] .node-card{transition:opacity .2s;}
  #lanes-key{position:fixed;left:16px;bottom:64px;z-index:310;max-width:290px;max-height:44vh;overflow:auto;padding:10px 12px;border-radius:14px;
    background:color-mix(in srgb,var(--surface) 90%,transparent);border:1px solid var(--border);box-shadow:0 10px 30px rgba(0,0,0,.18);
    -webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);font-size:12px;line-height:1.35;color:var(--text);}
  #lanes-key h5{margin:0;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);cursor:pointer;display:flex;justify-content:space-between;gap:12px;}
  #lanes-key.shut .lk-body{display:none;}
  #lanes-key .lk-row{display:flex;gap:9px;align-items:flex-start;padding:5px 4px;border-radius:8px;cursor:pointer;}
  #lanes-key .lk-row:hover,#lanes-key .lk-row.ln-on{background:color-mix(in srgb,var(--text) 7%,transparent);}
  #lanes-key svg{flex:none;margin-top:3px;}
  #lanes-key small{display:block;color:var(--muted);font-size:11px;}
  #lanes-key .lk-sep{border-top:1px solid var(--border);margin:6px 0 4px;}
  html.mobile #lanes-key,html.printing #lanes-key,html.detail-open #lanes-key{display:none !important;}
  #lanes-svg .ln-stem{stroke-width:1.5;opacity:.55;}
  #lanes-svg .ln-dot{stroke:var(--surface);stroke-width:2.5;}
  #lanes-svg .ln-tick{stroke:var(--muted);stroke-width:1;opacity:.6;}
  #lanes-svg .ln-ticklbl{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums;}
  #lanes-svg .ln-break{stroke:var(--muted);stroke-width:1.6;fill:none;opacity:.8;}
  #lanes-svg .ln-rel{fill:none;stroke-width:2.2;stroke-dasharray:7 5;opacity:.85;}
  #lanes-svg .ln-merge{stroke:var(--surface);stroke-width:2.5;}
  .lanes-tag{position:absolute;z-index:7;transform:translate(0,-50%);white-space:nowrap;
    font-size:12px;font-weight:700;letter-spacing:.04em;padding:4px 11px;border-radius:999px;
    background:color-mix(in srgb,var(--surface) 88%,transparent);border:1.5px solid currentColor;
    pointer-events:auto;cursor:pointer;-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);}
  .lanes-tag:hover{background:var(--surface);}
  .lanes-tag.ln-main-tag{color:var(--accent);}
  .lanes-unit{position:absolute;z-index:6;top:0;border-left:1.5px dashed color-mix(in srgb,var(--unit-color) 55%,transparent);pointer-events:none;}
  .lanes-unit:first-child{border-left:0;}
  .lanes-unit .lu-chip{position:absolute;left:14px;top:22px;white-space:nowrap;font-size:12px;font-weight:800;
    letter-spacing:.12em;text-transform:uppercase;color:var(--unit-color);padding:6px 12px;border-radius:9px;
    background:color-mix(in srgb,var(--surface) 80%,transparent);border:1.5px solid color-mix(in srgb,var(--unit-color) 45%,transparent);}
  .lanes-unit .lu-chip b{font-weight:800;opacity:.6;margin-right:7px;}
  html.alto-lanes:not(.mobile) #world .node-card:not(.focused) .node-desc{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;line-clamp:3;overflow:hidden;}
  .node-card .lanes-when:empty{display:none;}
  html.alto-editing .node-card .lanes-when:empty{display:block;}
  html.alto-editing .node-card .lanes-when:empty::before{content:'+ When';opacity:.7;}
  html.alto-editing:not(.mobile) .node-card .lanes-when{pointer-events:auto;cursor:text;border-radius:4px;}
  html.alto-editing:not(.mobile) .node-card .lanes-when:hover{background:color-mix(in srgb,var(--accent) 16%,transparent);color:var(--text);}
  html.alto-editing .lanes-tag{cursor:context-menu;}
  .node-card .lanes-when{display:block;font-size:10.5px;font-weight:700;letter-spacing:.06em;color:var(--muted);
    margin:-2px 0 4px;font-variant-numeric:tabular-nums;}
  html.alto-lanes #canvas.ln-dimline .node[data-ln]:not(.ln-on) .node-card{opacity:.16 !important;}
  html.alto-lanes #canvas.ln-dimline #lanes-svg g[data-ln]:not(.ln-on){opacity:.1;}
  html.alto-lanes #canvas.ln-dimline .lanes-tag:not(.ln-on){opacity:.3;}
"""


LANES_JS = r"""
(function(){
var L=window._ALTO_LANES; if(!L) return;
var de=document.documentElement;
if(!de.classList.contains('mobile')) de.classList.add('alto-lanes');
var NS='http://www.w3.org/2000/svg';
var STEM=30, TIER_GAP=10, CARD_PAD=12, TRACK_GAP=30, LEFT=330, RIGHT=420, TOP=96, BOTTOM=110;
var SPAN=250, MAXPX=1000, BREAK=190;
window._altoLanesGeo=null;
function med(a){ if(!a.length) return 0; a=a.slice().sort(function(x,y){ return x-y; }); var m=a.length>>1; return a.length%2?a[m]:(a[m-1]+a[m])/2; }
/* every event's time: dated as dated; undated spread evenly between the dated
   events around it in reading order (lanes.py) */
function times(order){
  var t={}, dated=[];
  order.forEach(function(id,i){ var e=L.ev[id]; if(e && e.t!=null){ t[id]=e.t; dated.push(i); } });
  var gaps=[]; for(var k=1;k<dated.length;k++){ var g=t[order[dated[k]]]-t[order[dated[k-1]]]; if(g>0) gaps.push(g); }
  var step=med(gaps)||1;
  if(!dated.length){ order.forEach(function(id,i){ t[id]=i; }); return t; }
  order.forEach(function(id,i){
    if(t[id]!=null) return;
    var a=-1,b=-1; for(var k=0;k<dated.length;k++){ if(dated[k]<i) a=dated[k]; else { b=dated[k]; break; } }
    if(a<0) t[id]=t[order[b]]-(b-i)*step/2;
    else if(b<0) t[id]=t[order[a]]+(i-a)*step/2;
    else { var ta=t[order[a]], tb=t[order[b]]; t[id]=ta+(tb-ta)*(i-a)/(b-a); if(tb<=ta) t[id]=ta; }
  });
  return t;
}
/* time → x: to scale, a long empty stretch squeezed to BREAK and marked */
function scale(tv){
  var T=Object.keys(tv).map(function(k){ return tv[k]; }).sort(function(a,b){ return a-b; }).filter(function(v,i,a){ return !i || v>a[i-1]+1e-9; });
  var g=[]; for(var i=1;i<T.length;i++) g.push(T[i]-T[i-1]);
  var undated=!Object.keys(L.ev).some(function(k){ return L.ev[k].t!=null; });
  var s=(undated?310:SPAN)/(med(g)||1), X={}, breaks=[], x=LEFT, segs=[{t0:T[0], x0:LEFT}];
  T.forEach(function(v,i){
    if(i){ var px=(v-T[i-1])*s;
      if(px>MAXPX){ breaks.push(x+BREAK/2); x+=BREAK; segs[segs.length-1].t1=T[i-1]; segs[segs.length-1].x1=X[T[i-1]]; segs.push({t0:v, x0:x}); }
      else x+=px; }
    X[v]=x;
  });
  if(T.length){ segs[segs.length-1].t1=T[T.length-1]; segs[segs.length-1].x1=x; }
  return {x:function(v){ return X[v]; }, s:s, breaks:breaks, segs:segs, end:x};
}
function nice(span){ var p=Math.pow(10,Math.floor(Math.log(span)/Math.LN10)), m=span/p; return (m<1.5?1:m<3.5?2:m<7.5?5:10)*p; }
function el(tag,attrs,parent){ var e=document.createElementNS(NS,tag); for(var k in attrs) e.setAttribute(k,attrs[k]); if(parent) parent.appendChild(e); return e; }

window._altoLanes=function(h){
  if(de.classList.contains('mobile')) return false;
  var world=document.getElementById('world'); if(!world) return false;
  var order=[].concat.apply([],ACT_SEQS).filter(function(id){ return !!L.ev[id] && document.getElementById('node-'+id); });
  NODES.forEach(function(n){ if(order.indexOf(n.id)<0 && L.ev[n.id] && document.getElementById('node-'+n.id)) order.push(n.id); });
  var tv=times(order), S=scale(tv), w={};
  order.forEach(function(id){ var c=document.querySelector('#node-'+id+' .node-card'); w[id]=c?c.offsetWidth:270; });
  var lines=[{id:'main', label:L.main, color:'', side:'both'}].concat(L.lines), LB={};
  lines.forEach(function(l){ LB[l.id]=l; l.ev=[]; });
  order.forEach(function(id){ var l=LB[L.ev[id].l]||LB.main; l.ev.push(id); });
  var X={}; order.forEach(function(id){ X[id]=S.x(tv[id]); });
  /* tiers: each card hangs off its line at its own time, in the first tier it fits */
  var tierOf={}, sideOf={};
  lines.forEach(function(l){
    l.ev.sort(function(a,b){ return X[a]-X[b] || order.indexOf(a)-order.indexOf(b); });
    var sides=l.id==='main'?[-1,1]:[l.side==='below'?1:-1], tiers={'-1':[], '1':[]}, alt=0;
    l.ev.forEach(function(id){
      var lo=X[id]-w[id]/2-CARD_PAD, hi=X[id]+w[id]/2+CARD_PAD, best=null;
      sides.forEach(function(sd, si){
        var tr=tiers[sd], k=0; while(k<tr.length && tr[k]>lo) k++;
        if(!best || k<best.k || (k===best.k && si===alt)) best={sd:sd, k:k};
      });
      tiers[best.sd][best.k]=hi; tierOf[id]=best.k; sideOf[id]=best.sd; alt=1-alt;
    });
    l.th={'-1':[], '1':[]};
    l.ev.forEach(function(id){ var a=l.th[sideOf[id]]; a[tierOf[id]]=Math.max(a[tierOf[id]]||0, h[id]||120); });
    l.ext={'-1':0, '1':0};
    ['-1','1'].forEach(function(sd){ var a=l.th[sd]; if(a.length) l.ext[sd]=STEM+a.reduce(function(s,v){ return s+(v||0)+TIER_GAP; },0); });
    /* where the line runs: from its branch point (or just before its first
       event) to where it converges (or just after its last) */
    if(l.id==='main'){
      /* the main line runs from its first event (or the first branch off it) to its last */
      var xs=l.ev.map(function(i){ return X[i]; });
      L.lines.forEach(function(q){ [q.from,q.to].forEach(function(f){ if(f && X[f]!=null && (L.ev[f]||{}).l==='main') xs.push(X[f]); }); });
      if(!xs.length) xs=order.map(function(i){ return X[i]; });
      l.x0=Math.min.apply(null,xs)-200; l.x1=Math.max.apply(null,xs)+200; }
    else {
      var fx=l.from&&X[l.from]!=null?X[l.from]:null, tx=l.to&&X[l.to]!=null?X[l.to]:null;
      var e0=l.ev.length?X[l.ev[0]]:(fx!=null?fx+120:tx-120), e1=l.ev.length?X[l.ev[l.ev.length-1]]:(tx!=null?tx-120:fx+120);
      l.x0=fx!=null?Math.min(fx,e0-60):e0-110; l.x1=tx!=null?Math.max(tx,e1+60):e1+110;
      l.fx=fx; l.tx=tx; l.e0=e0; l.e1=e1;
    }
  });
  /* tracks: lines on each side of the main line, nearest first, sharing a
     track when they never run at the same time */
  var main=LB.main, track={'-1':[], '1':[]};
  L.lines.forEach(function(l){
    var sd=l.side==='below'?'1':'-1', T=track[sd], k=0;
    for(;k<T.length;k++){ if(T[k].every(function(o){ return l.x1+90<o.x0 || o.x1+90<l.x0; })) break; }
    (T[k]=T[k]||[]).push(l); l.track=k; l.sd=+sd;
  });
  /* y: the main line at 0; each track's line beyond the previous track's cards */
  main.y=0;
  ['-1','1'].forEach(function(sd){
    var edge=main.ext[sd], s=+sd;
    track[sd].forEach(function(T){
      var ext=Math.max.apply(null,T.map(function(l){ return l.ext[sd]; }));
      var y=s*(edge+TRACK_GAP); T.forEach(function(l){ l.y=y; }); edge=edge+TRACK_GAP+Math.max(ext,40);
    });
  });
  var cy={}; lines.forEach(function(l){
    l.ev.forEach(function(id){ var sd=String(sideOf[id]), a=l.th[sd], off=STEM;
      for(var k=0;k<tierOf[id];k++) off+=(a[k]||0)+TIER_GAP;
      cy[id]=l.y+sideOf[id]*(off+(h[id]||120)/2); });
  });
  var ys=[]; lines.forEach(function(l){ ys.push(l.y); }); order.forEach(function(id){ ys.push(cy[id]-(h[id]||120)/2, cy[id]+(h[id]||120)/2); });
  var y0=Math.min.apply(null,ys), y1=Math.max.apply(null,ys), dy=TOP-y0;
  var W=Math.max(S.end, main.x1)+RIGHT, H=y1+dy+BOTTOM;
  lines.forEach(function(l){ l.y+=dy; });
  /* the cards */
  var pos={};
  order.forEach(function(id){
    var n=NODES.filter(function(q){ return q.id===id; })[0], y=cy[id]+dy;
    pos[id]=y; if(n){ n.displayX=X[id]; n.y=y; }
    var e=document.getElementById('node-'+id); if(!e) return;
    e.style.left=X[id]+'px'; e.style.top=(y+WORLD_PAD_TOP)+'px'; e.setAttribute('data-ln', L.ev[id].l);
    whenChip(e.querySelector('.node-card'), id);
  });
  world.style.setProperty('width',W+'px','important'); world.style.minHeight=(H+WORLD_PAD_TOP)+'px';
  de.style.setProperty('--lanes-w',W+'px');
  draw(world, lines, order, X, pos, h, S, W, H);
  units(world, order, X, w, H, W);
  window._altoLanesGeo={x:X, y:pos, h:h, lines:lines, W:W, H:H};
  _actBands=ACT_SEQS.map(function(){ return {startY:0, endY:H}; });
  /* the first time: open at the start of time, not the engine's centre */
  if(!window._altoLanesOpened){ window._altoLanesOpened=1; var cv=document.getElementById('canvas'); if(cv){ cv.scrollLeft=0; setTimeout(function(){ if(!window._focusedNodeId) cv.scrollLeft=0; }, 60); } }
  var svgR=document.getElementById('river-svg'); if(svgR) svgR.innerHTML='';
  return true;
};
function draw(world, lines, order, X, pos, h, S, W, H){
  var old=document.getElementById('lanes-svg'); if(old) old.remove();
  world.querySelectorAll('.lanes-tag').forEach(function(e){ e.remove(); });
  var P=WORLD_PAD_TOP, svg=el('svg',{id:'lanes-svg', width:W, height:H+P}), main=lines[0];
  world.insertBefore(svg, world.firstChild.nextSibling);
  var col=function(l){ return l.id==='main'?'var(--accent)':l.color; };
  /* the time axis along the main line: ticks where the numbers are round */
  var my=main.y+P, tk=el('g',{'class':'ln-axis'},svg);
  var nums=order.every(function(id){ var w=L.ev[id].w; return !w || /^-?\d{1,6}(-\d{1,2}){0,2}$/.test(String(w).trim()); })
  if(!order.some(function(id){ return L.ev[id].t!=null; })) nums=false;   // nothing dated: no clock to show
  S.segs.forEach(function(sg){
    if(sg.t1==null || sg.t1<=sg.t0 || !nums) return;
    var step=nice(220/S.s); if(step<1) step=1;
    for(var v=Math.ceil(sg.t0/step)*step; v<=sg.t1+1e-9; v+=step){
      var x=sg.x0+(v-sg.t0)*S.s; if(x<main.x0+30 || x>main.x1-30) continue;
      el('line',{'class':'ln-tick', x1:x, x2:x, y1:my-7, y2:my+7},tk);
      var tl=el('text',{'class':'ln-ticklbl', x:x+5, y:my+19},tk); tl.textContent=String(Math.round(v*100)/100);
    }
  });
  /* each side line: branching off, its run, converging */
  lines.slice(1).forEach(function(l){
    var y=l.y+P, g=el('g',{'data-ln':l.id},svg), c=col(l), R=110;
    var py=main.y+P, d='';
    var a=l.fx!=null?l.fx:l.x0, b=l.tx!=null?l.tx:l.x1;
    if(l.fx!=null) d+='M'+l.fx+' '+py+' C'+(l.fx+R*.6)+' '+py+' '+(l.fx+R*.4)+' '+y+' '+(l.fx+R)+' '+y;
    else d+='M'+l.x0+' '+y;
    var runEnd=l.tx!=null?l.tx-R:l.x1;
    d+=' L'+runEnd+' '+y;
    if(l.tx!=null) d+=' C'+(l.tx-R*.4)+' '+y+' '+(l.tx-R*.6)+' '+py+' '+l.tx+' '+py;
    var e0=l.ev.length?l.e0:null, e1=l.ev.length?l.e1:null, sx=l.fx!=null?l.fx+R:l.x0;
    /* solid where it has events of its own (and its branch / join curves); dashed where it only waits */
    el('path',{'class':'ln-hit', d:d},g);
    el('path',{'class':'ln-br ln-wait', d:'M'+sx+' '+y+' L'+runEnd+' '+y, stroke:c},g);
    if(l.fx!=null) el('path',{'class':'ln-br', d:'M'+l.fx+' '+py+' C'+(l.fx+R*.6)+' '+py+' '+(l.fx+R*.4)+' '+y+' '+(l.fx+R)+' '+y, stroke:c},g);
    if(l.tx!=null) el('path',{'class':'ln-br', d:'M'+runEnd+' '+y+' C'+(l.tx-R*.4)+' '+y+' '+(l.tx-R*.6)+' '+py+' '+l.tx+' '+py, stroke:c},g);
    if(e0!=null) el('path',{'class':'ln-br', d:'M'+Math.max(sx,e0)+' '+y+' L'+Math.min(runEnd,e1)+' '+y, stroke:c},g);
    if(l.tx!=null) el('circle',{'class':'ln-merge', cx:l.tx, cy:py, r:6, fill:c},g);
    if(l.fx==null) el('circle',{cx:l.x0, cy:y, r:4.5, fill:c},g);
    if(l.tx==null){ el('path',{d:'M'+(l.x1-2)+' '+(y-7)+' L'+(l.x1+9)+' '+y+' L'+(l.x1-2)+' '+(y+7)+' Z', fill:c},g); }
    tag(world, l, (l.fx!=null?l.fx+R:l.x0)+16, y-l.sd*22, c, 0);
  });
  /* the main line on top of the branches' ends */
  var mg=el('g',{'data-ln':'main'},svg);
  el('path',{'class':'ln-main', d:'M'+main.x0+' '+my+' L'+main.x1+' '+my},mg);
  el('path',{d:'M'+(main.x1-3)+' '+(my-10)+' L'+(main.x1+13)+' '+my+' L'+(main.x1-3)+' '+(my+10)+' Z', fill:'var(--accent)'},mg);
  if(main.label) tag(world, main, main.x0-14, my, 'var(--accent)', 1);
  /* squeezed stretches: a ≈ across every line that runs through them */
  S.breaks.forEach(function(bx){
    lines.forEach(function(l){
      /* only where the line has something on both sides of the squeeze */
      var pts=l.ev.map(function(i){ return X[i]; }).concat([l.fx,l.tx].filter(function(v){ return v!=null; }));
      if(l.id==='main') L.lines.forEach(function(q){ [q.from,q.to].forEach(function(f){ if(f && X[f]!=null) pts.push(X[f]); }); });
      if(!pts.some(function(v){ return v<bx; }) || !pts.some(function(v){ return v>bx; })) return;
      var y=l.y+P;
      el('path',{'class':'ln-break', d:'M'+(bx-9)+' '+(y-9)+' q4.5 -5 9 0 t9 0 M'+(bx-9)+' '+(y+1)+' q4.5 -5 9 0 t9 0'},svg); });
  });
  /* stems + dots at each event's exact time */
  order.forEach(function(id){
    var l=null; lines.forEach(function(q){ if(q.ev.indexOf(id)>=0) l=q; }); if(!l) return;
    var x=X[id], ly=l.y+P, cyy=pos[id]+P, hh=(h[id]||120)/2, edge=cyy+(cyy<ly?hh:-hh), c=col(l);
    var g=el('g',{'data-ln':l.id},svg);
    el('line',{'class':'ln-stem', x1:x, x2:x, y1:ly, y2:edge, stroke:c},g);
    el('circle',{'class':'ln-dot', cx:x, cy:ly, r:6.5, fill:c},g);
  });
  /* connections the material draws between events (not the lines themselves) */
  (typeof CONNECTIONS!=='undefined'?CONNECTIONS:[]).forEach(function(cn){
    if(!cn || cn[2]==='spine' || X[cn[0]]==null || X[cn[1]]==null) return;
    var la=lineOf(lines,cn[0]), lb=lineOf(lines,cn[1]); if(!la||!lb || la===lb) return;   // the line itself already joins them
    var ax=X[cn[0]], ay=la.y+P, bx=X[cn[1]], by=lb.y+P, mx=(ax+bx)/2, bow=Math.min(160, Math.abs(bx-ax)/3+30);
    var c=(typeof COLOR_MAP!=='undefined' && COLOR_MAP[cn[2]]) ? COLOR_MAP[cn[2]] : 'var(--muted)';
    var rg=el('g',{'data-ln':la.id+' '+lb.id},svg);
    el('path',{'class':'ln-rel', d:'M'+ax+' '+ay+' Q'+mx+' '+(Math.min(ay,by)-bow)+' '+bx+' '+by, stroke:c},rg);
  });
}
/* the card says when (and, on a phone, which line it is on) */
function whenChip(c, id){
  var ev=L.ev[id]; if(!c || !ev || c.querySelector('.lanes-when')) return;
  var ln=null; L.lines.forEach(function(q){ if(q.id===ev.l) ln=q; });
  var txt=ev.w || '', mob=de.classList.contains('mobile');
  if(mob && ev.l!=='main' && ln) txt=(txt ? txt+' · ' : '')+ln.label;
  else if(mob && L.main && !txt) txt=L.main;
  if(!txt && mob) return;
  var d=document.createElement('div'); d.className='lanes-when'; d.textContent=txt;
  var tg=c.querySelector('.node-tag'); c.insertBefore(d, tg||c.firstChild);
}
function phoneChips(){ if(!de.classList.contains('mobile')) return;
  document.querySelectorAll('.node[id^="node-"]').forEach(function(n){ whenChip(n.querySelector('.node-card'), n.id.slice(5)); }); }
['DOMContentLoaded','load'].forEach(function(ev){ window.addEventListener(ev, function(){ phoneChips(); setTimeout(phoneChips, 400); }); });
function lineOf(lines,id){ for(var i=0;i<lines.length;i++) if(lines[i].ev.indexOf(id)>=0) return lines[i]; return null; }
function tag(world, l, x, y, c, before){
  var t=document.createElement('div'); t.className='lanes-tag'+(l.id==='main'?' ln-main-tag':''); t.style.left=x+'px'; t.style.top=y+'px';
  if(before) t.style.transform='translate(-100%,-50%)';
  t.style.color=c; t.textContent=l.label||''; t.setAttribute('data-ln-tag', l.id);
  t.title='Show only this line — click again for all';
  world.appendChild(t);
}
/* the units: columns of time, each from its first event to its last */
function units(world, order, X, w, H, W){
  world.querySelectorAll('.lanes-unit').forEach(function(e){ e.remove(); });
  var R=ACT_SEQS.map(function(ids){ var xs=ids.filter(function(i){ return X[i]!=null; }); if(!xs.length) return null;
    return [Math.min.apply(null,xs.map(function(i){ return X[i]-w[i]/2; })), Math.max.apply(null,xs.map(function(i){ return X[i]+w[i]/2; }))]; });
  var cuts=[0], last=0;
  for(var a=0;a<R.length;a++){
    if(!R[a]) { cuts.push(last); continue; }
    var nx=null; for(var b=a+1;b<R.length;b++) if(R[b]){ nx=R[b]; break; }
    var cut=nx ? Math.max(last+40, (R[a][1]+nx[0])/2) : W;
    cuts.push(cut); last=cut;
  }
  var stops=[];
  ACT_SEQS.forEach(function(ids,a){
    var pm=PHASE_META[a]; if(!pm || !R[a]) return;
    var u=document.createElement('div'); u.className='lanes-unit';
    u.style.left=cuts[a]+'px'; u.style.width=(cuts[a+1]-cuts[a])+'px'; u.style.height=(H+WORLD_PAD_TOP)+'px';
    u.style.setProperty('--unit-color', pm.colorRaw);
    u.innerHTML='<div class="lu-chip"><b></b><span></span></div>';
    u.querySelector('b').textContent=pm.numeral; u.querySelector('span').textContent=(pm.label.split(' — ')[1]||pm.label);
    world.insertBefore(u, world.firstChild);
    stops.push(pm.colorRaw+'b3 '+((cuts[a]+cuts[a+1])/2/W*100).toFixed(1)+'%');
  });
  var slab=document.getElementById('glass-slab');
  if(!slab){ slab=document.createElement('div'); slab.id='glass-slab'; world.insertBefore(slab, world.firstChild); }
  slab.style.top='0px'; slab.style.height=(H+WORLD_PAD_TOP+200)+'px';
  ['width',W+'px','left','0px','transform','none'].forEach(function(v,i,a){ if(i%2===0) slab.style.setProperty(v,a[i+1],'important'); });
  if(stops.length) slab.style.backgroundImage='linear-gradient(90deg, '+stops[0].split(' ')[0]+' 0%, '+stops.join(', ')+', '+stops[stops.length-1].split(' ')[0]+' 100%)';
  window._headerTint={slabTop:0, slabH:H, stops:[{p:0,c:PHASE_META[0].colorRaw},{p:100,c:PHASE_META[0].colorRaw}]};
  if(window.updateHeaderTint) try{ window.updateHeaderTint(); }catch(e){}
}
/* arrow keys: along a line ←/→ in time; ↑/↓ to the nearest event on the next line over */
window._altoLanesNav=function(id, dir){
  var G=window._altoLanesGeo; if(!G || de.classList.contains('mobile')) return null;
  var lid=(L.ev[id]||{}).l||'main', l=null; G.lines.forEach(function(q){ if(q.id===lid) l=q; }); if(!l) return null;
  function live(i){ var c=document.querySelector('#node-'+i+' .node-card'); return c && !c.classList.contains('dimmed') && !c.classList.contains('ent-dimmed') && !c.classList.contains('rel-dimmed'); }
  if(dir==='e'||dir==='w'){
    var ev=l.ev.filter(live), i=ev.indexOf(id), j=i+(dir==='e'?1:-1);
    if(i>=0 && j>=0 && j<ev.length) return ev[j];
    /* the end of a side line: on into the event it converges into, or back to where it branched */
    if(dir==='e' && l.to) return l.to; if(dir==='w' && l.from) return l.from;
    return null;
  }
  if(dir==='n'||dir==='s'){
    var cy=G.y[id], sg=dir==='s'?1:-1, best=null, bd=Infinity;
    Object.keys(G.y).forEach(function(k){ if(k===id || !live(k)) return;
      var dyy=(G.y[k]-cy)*sg; if(dyy<=20) return;
      var c=Math.abs(G.x[k]-G.x[id])*1.6+dyy; if(c<bd){ bd=c; best=k; } });
    return best;
  }
  return null;
};
/* the wheel: a mouse wheel scrolls the page sideways (Shift: up and down);
   a trackpad, which scrolls both ways by itself, is left alone */
var _tp=0;
document.addEventListener('wheel', function(e){
  if(de.classList.contains('mobile') || !window._altoLanesGeo || e.ctrlKey || e.metaKey) return;
  var cv=document.getElementById('canvas'); if(!cv || !cv.contains(e.target) || cv.classList.contains('focus-mode')) return;
  if(e.deltaX){ _tp=e.timeStamp; return; }
  if(e.timeStamp-_tp<800) return;
  if(e.shiftKey){ cv.scrollTop+=e.deltaY; e.preventDefault(); return; }
  cv.scrollLeft+=e.deltaY*(e.deltaMode===1?40:1); e.preventDefault();
}, {passive:false});
/* isolating a line: its events, its curves, where it branches and joins, the
   arcs to it. A click keeps it; hovering shows it for as long as you point. */
var _lock=null, _ht=null;
function isolate(id){
  var cv=document.getElementById('canvas'); if(!cv) return;
  document.querySelectorAll('.ln-on').forEach(function(x){ x.classList.remove('ln-on'); });
  if(!id){ cv.classList.remove('ln-dimline'); return; }
  cv.classList.add('ln-dimline');
  document.querySelectorAll('[data-ln~="'+id+'"],[data-ln-tag="'+id+'"],.lk-row[data-k="'+id+'"]').forEach(function(x){ x.classList.add('ln-on'); });
  var l=null; L.lines.forEach(function(q){ if(q.id===id) l=q; });
  if(l) [l.from,l.to].forEach(function(f){ var n=f && document.getElementById('node-'+f); if(n) n.classList.add('ln-on'); });
}
function lnOf(t){
  if(!t || !t.closest) return null;
  var k=t.closest('.lk-row[data-k],.lanes-tag'); if(k) return k.getAttribute('data-k')||k.getAttribute('data-ln-tag');
  var h=t.closest('#lanes-svg g[data-ln]'); if(h && t.classList.contains('ln-hit')) return h.getAttribute('data-ln');
  var n=t.closest('#canvas .node[data-ln]'); return n ? n.getAttribute('data-ln') : null;
}
document.addEventListener('mouseover', function(e){
  if(_lock || de.classList.contains('mobile') || !window._altoLanesGeo) return;
  var id=lnOf(e.target), cv=document.getElementById('canvas');
  if(cv && cv.classList.contains('focus-mode')) return;
  clearTimeout(_ht); _ht=setTimeout(function(){ if(!_lock) isolate(id); }, id ? 140 : 220);
});
document.addEventListener('click', function(e){
  var t=e.target.closest && e.target.closest('.lanes-tag,.lk-row[data-k]'); if(!t || de.classList.contains('alto-editing')) return;
  e.stopPropagation(); var id=t.getAttribute('data-ln-tag')||t.getAttribute('data-k');
  _lock=(_lock===id)?null:id; isolate(_lock||id);
}, true);
document.addEventListener('keydown', function(e){ if(e.key==='Escape' && _lock){ _lock=null; isolate(null); } });
/* the key: what each line follows, where it branches and joins, what each kind of line means */
function key(){
  if(de.classList.contains('mobile')) return;
  var k=document.getElementById('lanes-key'); if(k) k.remove();
  k=document.createElement('div'); k.id='lanes-key';
  var T=function(id){ var n=(typeof NODES_SRC!=='undefined'?NODES_SRC:[]).filter(function(q){ return q.id===id; })[0]; return n?n.title:''; };
  var esc=function(v){ return String(v||'').replace(/[&<>"]/g,function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); };
  var sw=function(c,dash,w){ return '<svg width="26" height="10"><line x1="1" y1="5" x2="25" y2="5" stroke="'+c+'" stroke-width="'+(w||4)+'" stroke-linecap="round"'+(dash?' stroke-dasharray="'+dash+'"':'')+'/></svg>'; };
  var h='<h5><span>Lines</span><span>▾</span></h5><div class="lk-body">';
  h+='<div class="lk-row" data-k="main">'+sw('var(--accent)','',6)+'<div><b>'+esc(L.main||'Main line')+'</b><small>The main line — every other line branches off it</small></div></div>';
  L.lines.forEach(function(l){
    var w=[l.from?'branches off at “'+esc(T(l.from))+'”':'begins on its own', l.to?'joins at “'+esc(T(l.to))+'”':'runs on'].join(' · ');
    h+='<div class="lk-row" data-k="'+esc(l.id)+'">'+sw(l.color)+'<div><b>'+esc(l.label)+'</b><small>'+w+'</small></div></div>';
  });
  h+='<div class="lk-sep"></div>';
  h+='<div class="lk-row">'+sw('var(--muted)')+'<div>Solid: the line through its own events</div></div>';
  h+='<div class="lk-row">'+sw('var(--muted)','9 7',3.5)+'<div>Dashed: no events of its own here — waiting to branch off or join</div></div>';
  var rels={}; (typeof CONNECTIONS!=='undefined'?CONNECTIONS:[]).forEach(function(c){ if(c && c[2]!=='spine') rels[c[2]]=1; });
  Object.keys(rels).forEach(function(r){ var c=(typeof COLOR_MAP!=='undefined'&&COLOR_MAP[r])||'var(--muted)', lb=(typeof REL_LABELS!=='undefined'&&REL_LABELS[r])||r;
    h+='<div class="lk-row">'+sw(c,'7 5',2.2)+'<div>Arc: '+esc(lb)+' <small>a link between events on different lines</small></div></div>'; });
  h+='<div class="lk-row"><span style="width:26px;text-align:center;flex:none">≈</span><div>Time squeezed — a long stretch with nothing in it</div></div>';
  h+='<small style="margin-top:4px">Point at a line, its label or a card to follow it; click a label to keep it.</small></div>';
  k.innerHTML=h; document.body.appendChild(k);
  k.querySelector('h5').addEventListener('click', function(){ k.classList.toggle('shut'); try{ localStorage.setItem('alto-lanes-key', k.classList.contains('shut')?'0':'1'); }catch(e){} });
  try{ if(localStorage.getItem('alto-lanes-key')==='0') k.classList.add('shut'); }catch(e){}
}
window.addEventListener('load', function(){ setTimeout(key, 300); });
})();
"""
