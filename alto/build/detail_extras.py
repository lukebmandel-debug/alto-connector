"""Detail-page features first built by hand into the Torts preview (2026-09-26,
versions 2-13) and ported here so a rebuild keeps them: ALTO-001, 003, 004,
006, 008, 009, 010, 011, 012 and 013 in the engine issue log.

The general features (the back-to-previous-page control, the banner
clearance, auto-linking — builder._add_tail) go on every page. They were once
gated to outline and index pages because Terrarium's private page sat within a
kilobyte of the 1,000,000-byte cap; private pages are now stored gzipped (see
private_shell.MAX_PAGE_BYTES), so that gate is gone. What stays specific is
specific by nature: the outline pieces need an outline, the index pages need
a `hide_nav` axis.

Build-time pieces (source notes, citations, the autolink table) are plain
Python and cost nothing at runtime; the runtime pieces are JS strings in the
same style as blocks.py's glue.
"""
from __future__ import annotations

import json
import re
from urllib.parse import quote

from .brief import PROVENANCE, Section
from .sanitize import esc, LOCAL_ICON

# ── outline: a hub sits above its own children (ALTO-001) ───────────────────
# The engine hook (engine_patches: outline-hub-above-children) calls this from
# inside initLayout's resolver loop, on an outline laid out as flow (a tree
# guarantees it by construction); layout.resolve() runs the same pass so the
# baseY hints already satisfy it. 90 = layout.HUB_DROP.
HUBS_ABOVE_GLUE = """
window._altoHubsAbove = function(pos, h){
  var par = (window._ALTO_OUTLINE||{}).parent || {}, moved = false;
  Object.keys(par).forEach(function(id){
    var p = par[id]; if(pos[p]==null || pos[id]==null) return;
    var need = pos[p]-(h[p]||0)/2 + 90 + (h[id]||0)/2;
    if(pos[id] < need-0.5){ pos[id] = need; moved = true; }
  });
  return moved;
};"""

# ── outline: the desktop tree (layout.outline_plan, run on real heights) ────
# initLayout measures every card and runs its collision resolver; on an outline
# page laid out as a tree this then replaces those positions with the tree's.
# The builder has already worked out every card's x and the program that stacks
# them (layout.outline_plan: cards, rows, columns, floats); the page only runs
# it over the heights it measured, exactly as layout.run_plan does for the
# builder's own hints, keeping every hub above its children by construction.
# It sets each node's displayX, which the line router and the numeral check
# read, and records the fanned lines' end points in _altoEdgeTX.
def tree_glue(plan: dict) -> str:
    return "\nwindow._ALTO_TREE_PLAN=" + json.dumps(plan, separators=(",", ":")) + ";" + TREE_GLUE


TREE_GLUE = """
if(!document.documentElement.classList.contains('mobile')) window._altoTreeOn=true;
/* cards a dragged card lands on step out of its way (layout.make_room) */
window._altoMakeRoom = function(y, x, h, w, ids, moved, parent, gap, top){
  var free=ids.filter(function(i){ return !moved[i] && y[i]!=null; }); if(!free.length) return false;
  var y0={}, fset={}, kids={}; Object.keys(y).forEach(function(i){ y0[i]=y[i]; });
  free.forEach(function(i){ fset[i]=1; });
  free.forEach(function(i){ var p=parent[i]; if(p) (kids[p]=kids[p]||[]).push(i); });
  function ww(i){ return (w&&w[i])||270; }
  function rowroot(i){ for(;;){ var p=parent[i]; if(p && fset[p] && Math.abs(y0[p]-y0[i])<1) i=p; else return i; } }
  function unit(i, whole){ var out=[], q=[i]; while(q.length){ var c=q.shift(); out.push(c);
    (kids[c]||[]).forEach(function(k){ if(whole || Math.abs(y0[k]-y0[c])<1) q.push(k); }); } return out; }
  function near(i, ti, j, tj){ return Math.abs(x[i]-x[j]) < (ww(i)+ww(j))/2+12 && ti < tj+h[j]+gap && ti+h[i]+gap > tj; }
  function hits(i, t, j){ if(!moved[j] && near(i, y0[i]-h[i]/2, j, y0[j]-h[j]/2)) return false; return near(i, t, j, y[j]-h[j]/2); }
  function cmp(a, b){ return a[0]-b[0] || a[1]-b[1] || (a[2]<b[2]?-1:a[2]>b[2]?1:0); }
  var obst=ids.filter(function(i){ return moved[i] && y[i]!=null; }), done={}, changed=false;
  free.map(function(i){ return [-(y0[i]+h[i]/2), x[i], i]; }).sort(cmp).forEach(function(e){
    var r=rowroot(e[2]); if(done[r]) return;
    var grp=unit(r,false), t={}, lift=0, again=true, ing={};
    if(unit(r,true).length>grp.length) return;
    grp.forEach(function(k){ t[k]=y[k]-h[k]/2; ing[k]=1; });
    while(again){ again=false;
      grp.forEach(function(k){ obst.forEach(function(j){
        if(!ing[j] && y0[k]<y[j] && hits(k,t[k]-lift,j)){ lift=Math.max(lift,t[k]-(y[j]-h[j]/2-gap-h[k])); again=true; } }); }); }
    var mt=Math.min.apply(null, grp.map(function(k){ return t[k]; }));
    if(lift>0 && mt-lift>=top-0.5 && !grp.some(function(k){ return obst.some(function(j){ return !ing[j] && hits(k,t[k]-lift,j); }); })){ grp.forEach(function(k){ y[k]-=lift; done[k]=1; obst.push(k); }); changed=true; }
  });
  free.map(function(i){ return [y0[i]-h[i]/2, x[i], i]; }).sort(cmp).forEach(function(e){
    if(done[e[2]]) return;
    var r=rowroot(e[2]); if(done[r]) return;
    var row=unit(r,false);
    if(!row.some(function(k){ return obst.some(function(j){ return j!==k && hits(k,y[k]-h[k]/2,j); }); })) return;
    var grp=unit(r,true).filter(function(k){ return !done[k]; }), ing={}, drop=0, again=true;
    grp.forEach(function(k){ ing[k]=1; });
    while(again){ again=false;
      for(var a=0; a<grp.length; a++){ var k=grp[a], tk=y[k]-h[k]/2+drop, hit=null;
        for(var b=0; b<obst.length; b++){ var j=obst[b]; if(!ing[j] && hits(k,tk,j)){ hit=j; break; } }
        if(hit!=null){ drop+=y[hit]+h[hit]/2+gap-tk; again=true; } } }
    if(drop>0){ grp.forEach(function(k){ y[k]+=drop; done[k]=1; obst.push(k); }); changed=true; }
  });
  return changed;
};
/* no two cards of a unit touch once cards were dragged (layout.separate) */
window._altoSeparate = function(y, x, h, w, ids, y0, x0, parent, gap){
  ids=ids.filter(function(i){ return y[i]!=null; });
  function ww(i){ return (w&&w[i])||270; }
  var kids={}; ids.forEach(function(i){ var p=parent[i]; if(p) (kids[p]=kids[p]||[]).push(i); });
  function kept(i, j){ return Math.abs((y[i]-y[j])-(y0[i]-y0[j]))<0.5 && Math.abs((x[i]-x[j])-(x0[i]-x0[j]))<0.5; }
  function group(j){ var out=[], q=[j];
    while(q.length){ var c=q.shift(); if(out.indexOf(c)>=0) continue; out.push(c);
      q=q.concat(kids[c]||[]).concat(ids.filter(function(k){ return out.indexOf(k)<0 && Math.abs(y[k]-y[c])<0.5 && kept(c, k); })); }
    return out; }
  var changed=false;
  for(var g=0; g<ids.length*ids.length+1; g++){
    var order=ids.slice().sort(function(a, b){ return ((y[a]-h[a]/2)-(y[b]-h[b]/2)) || (x[a]-x[b]) || (a<b?-1:a>b?1:0); });
    var hit=null;
    for(var a=0; a<order.length && !hit; a++){ var i=order[a];
      for(var b=a+1; b<order.length; b++){ var j=order[b];
        if(Math.abs(x[i]-x[j]) < (ww(i)+ww(j))/2+12 && y[j]-h[j]/2 < y[i]+h[i]/2+gap && !kept(i, j)){ hit=[i, j]; break; } } }
    if(!hit) break;
    var G=group(hit[1]); if(G.indexOf(hit[0])>=0) G=[hit[1]];
    var d=y[hit[0]]+h[hit[0]]/2+gap+h[hit[1]]/2-y[hit[1]];
    G.forEach(function(k){ y[k]+=d; }); changed=true;
  }
  return changed;
};
/* the tree's places over these heights (layout.run_plan); `shift` and
   `slide` stand in for the plan's own while a card is being dragged */
window._altoTreeCalc = function(h, shift, TP, slide){
  var T=TP||window._ALTO_TREE_PLAN; if(!T || typeof NODES==='undefined') return null;
  if(shift===undefined) shift=T.shift;
  if(slide===undefined) slide=T.slide;
  var y={}, x={}, bottom=0;
  Object.keys(T.x).forEach(function(i){ x[i]=T.x[i]; });
  function put(i,top,rowH){ y[i]=top+(rowH!=null?rowH:h[i])/2; bottom=Math.max(bottom,y[i]+h[i]/2); }
  function run(op,c){
    var k=op[0];
    if(k==='card'){ c+=op[3]||0; put(op[1],c); return c+h[op[1]]+op[2]; }
    if(k==='row'){
      c+=op[3]||0;
      var rh=Math.max.apply(null,op[1].map(function(r){ return h[r]; }));
      op[1].forEach(function(r){ put(r,c,rh); });
      return c+rh+op[2];
    }
    if(k==='seq'){ op[1].forEach(function(o){ c=run(o,c); }); return c; }
    if(k==='par'){
      var ends=op[1].map(function(o){ return run(o,c)-T.row_gap; });
      return ends.length ? Math.max.apply(null,ends)+op[2] : c;
    }
    if(k==='band'){
      var cards=op[1], blocks=op[2], rg=op[3], gap=op[4], drop=op[5];
      var lay=function(flip){
        var tops={}, sky=[];
        cards.map(function(cd,j){ return [cd.length>5 ? 9 : (cd[3]^flip),j]; })
          .sort(function(a,b){ return a[0]-b[0] || a[1]-b[1]; })
          .forEach(function(kj){
            var cd=cards[kj[1]], t=c+(cd.length>5 ? 0 : kj[0]*drop);
            if(cd.length>5) t=Math.max(t,tops[cd[5]]+h[cd[5]]+rg);
            sky.forEach(function(s){ if(s[0]<cd[2] && cd[1]<s[1]) t=Math.max(t,s[2]+rg); });
            t+=cd[4]; tops[cd[0]]=t; sky.push([cd[1],cd[2],t+h[cd[0]]]);
          });
        return {tops:tops, sky:sky};
      };
      var low=function(L){ return Math.max.apply(null,L.sky.map(function(s){ return s[2]; })); };
      var sum=function(L){ return Object.keys(L.tops).reduce(function(a,i){ return a+L.tops[i]; },0); };
      var best=lay(0);
      if(op.length>6){
        var alt=lay(1), l0=low(best), l1=low(alt);
        if(l1<l0-1e-9 || (Math.abs(l1-l0)<=1e-9 && sum(alt)<sum(best)-1e-9)) best=alt;
      }
      Object.keys(best.tops).forEach(function(i){ put(i,best.tops[i]); });
      var sky2=best.sky;
      blocks.forEach(function(b){
        var t=c;
        sky2.forEach(function(s){ if(s[0]<b[1] && b[0]<s[1]) t=Math.max(t,s[2]+gap); });
        sky2.push([b[0],b[1],run(b[2],t)-T.row_gap]);
      });
      return Math.max.apply(null,sky2.map(function(s){ return s[2]; }))+gap;
    }
    run(op[1],op.length>2?op[2]:c); return c;                 // float / pinned: takes no room
  }
  /* `shift` hints (layout.shift_offsets): a card and its progeny move after
     their unit is laid out; nothing else in it moves. `slide`: the card alone */
  var off={}, P0=(window._ALTO_OUTLINE||{}).parent||{};
  if(shift || slide) Object.keys(NODE_ACT).forEach(function(i){
    var dx=0, dy=0, c=i, seen={};
    if(shift) while(c && !seen[c]){ seen[c]=1; var s=shift[c]; if(s){ dx+=s[0]; dy+=s[1]; } c=P0[c]||''; }
    var l=slide&&slide[i]; if(l){ dx+=l[0]; dy+=l[1]; }
    if(dx || dy) off[i]=[dx,dy];
  });
  var cur=T.top;
  T.acts.forEach(function(ops,a){
    if(a && ops.length) cur=bottom+T.act_gap;
    var start=cur;
    ops.forEach(function(o){ cur=run(o,cur); });
    var moved=Object.keys(off).filter(function(i){ return NODE_ACT[i]===a && y[i]!=null; });
    if(moved.length){
      var mv={}, mine=NODES.map(function(n){ return n.id; }).filter(function(i){ return NODE_ACT[i]===a && y[i]!=null; }), y0={}, x0={};
      mine.forEach(function(i){ y0[i]=y[i]; x0[i]=x[i]; });
      moved.forEach(function(i){ x[i]+=off[i][0]; y[i]+=off[i][1]; mv[i]=1; });
      window._altoMakeRoom(y, x, h, T.w, mine, mv, P0, T.row_gap, start);
      window._altoSeparate(y, x, h, T.w, mine, y0, x0, P0, T.row_gap);
      bottom=Math.max.apply(null, Object.keys(y).map(function(i){ return y[i]+h[i]/2; }));
    }
  });
  NODES.forEach(function(n){
    if(y[n.id]==null){ y[n.id]=bottom+T.row_gap+h[n.id]/2; x[n.id]=T.cx; bottom=y[n.id]+h[n.id]/2; }
  });
  var etx=T.etx||{};
  if(shift || slide){ etx={}; Object.keys(T.etx||{}).forEach(function(k){ var c=k.split('|')[1]; etx[k]=T.etx[k]+(off[c]?off[c][0]:0); }); }
  return {y:y, x:x, etx:etx, bottom:bottom};
};
window._altoTreeWrite = function(R, pos, h){
  NODES.forEach(function(n){
    pos[n.id]=R.y[n.id]; n.displayX=R.x[n.id];
    var el=document.getElementById('node-'+n.id); if(el) el.style.left=R.x[n.id]+'px';
  });
  window._altoEdgeTX=R.etx;
  window._altoTreeOn=true; window._altoTreeGeo={y:R.y, h:h, x:R.x};
};
window._altoTree = function(pos, h){
  if(document.documentElement.classList.contains('mobile')) return false;
  var R=window._altoTreeCalc(h); if(!R) return false;
  window._altoTreeWrite(R, pos, h);
  return true;
};
window._altoTreeMid = function(fm){
  var G=window._altoTreeGeo, P=(window._ALTO_OUTLINE||{}).parent||{}, E=window._altoEdgeTX||{}; if(!G) return;
  function ex(p,c){ var v=E[p+'|'+c]; return v!=null ? v : G.x[c]; }   // the line's end x
  var mid={};
  /* halfway down the gap to the parent's NEAREST child below — including one
     straight under it, whose line needs no turn but bounds the gap */
  Object.keys(P).forEach(function(c){
    var p=P[c]; if(G.y[p]==null||G.y[c]==null) return;
    var pb=G.y[p]+G.h[p]/2, ct=G.y[c]-G.h[c]/2; if(ct<=pb) return;   // flanks share the row
    mid[p]=Math.min(mid[p]==null?Infinity:mid[p], ct);
  });
  var T=window._ALTO_TREE_PLAN||{};
  Object.keys(P).forEach(function(c){
    var p=P[c]; if(mid[p]==null||Math.abs(ex(p,c)-G.x[p])<10) return;
    var pb=G.y[p]+G.h[p]/2; if(G.y[c]-G.h[c]/2<=pb) return;
    /* a long drop runs down the parent's own column and turns just over its
       children, rather than crossing every column between on a halfway bus */
    fm[p+'|'+c]=(mid[p]-pb>T.bus_span ? mid[p]-T.bus_above : pb+(mid[p]-pb)/2)+WORLD_PAD_TOP;
  });
};"""


# ── outline: a node's page names it (ALTO-004) ──────────────────────────────
# "Liable" appears under every concept, so a page titled only "Liable" says
# nothing. A title shared by several nodes is prefixed with its parent's.
NODE_NAME_GLUE = """
window._altoNodeName = function(n){
  var par = (window._ALTO_OUTLINE||{}).parent || {}, p = par[n.id];
  if(!p || NODES_SRC.filter(function(x){ return x.title===n.title; }).length < 2) return n.title;
  var pn = NODES_SRC.filter(function(x){ return x.id===p; })[0];
  return pn ? pn.title+': '+n.title : n.title;
};"""

# ── outline: an element's page as a tree (ALTO-003) ─────────────────────────
# Each concept the element touches, at its outline depth and number; under it,
# its outcome leaves — a leaf of a different kind (tag) from the concept that
# holds it, e.g. Liable / Not Liable under a Concept — with the cases decided
# each way. Replaces a flat list that mixed concepts with context-free
# "Liable" rows. Everything shown is the material's own titles and text.
ELEMENT_TREE = """
function _altoElementTree(members){
  var O = window._ALTO_OUTLINE || {}, num = O.num || {}, par = O.parent || {}, kids = O.kids || {};
  var byId = {}; NODES_SRC.forEach(function(n){ byId[n.id]=n; });
  var isM = {}; members.forEach(function(n){ isM[n.id]=1; });
  function isOut(n){ var p = byId[par[n.id]]; return !!(p && !(kids[n.id]||[]).length && n.tag && n.tag!==p.tag); }
  var rows = [], seen = {}, outs = {}, nOut = 0, outTag = '';
  members.forEach(function(n){
    if(isOut(n)){
      nOut++; outTag = outTag || n.tag;
      var p = par[n.id]; (outs[p]=outs[p]||[]).push(n);
      if(!seen[p]){ seen[p]=1; rows.push(byId[p]); }
    } else if(!seen[n.id]){ seen[n.id]=1; rows.push(n); }
  });
  var order = NODES_SRC.map(function(n){ return n.id; });
  rows.sort(function(a,b){ return order.indexOf(a.id)-order.indexOf(b.id); });
  var nCon = members.length-nOut, nn = String(_ALTO_NODE_NOUN||'Concept').toLowerCase(), ot = outTag.toLowerCase();
  var meta = '<div class="doc-meta">'+nCon+' '+nn+(nCon===1?'':'s')
    + (nOut ? ' &middot; '+nOut+' '+ot+(nOut===1?'':'s') : '') + '</div>';
  function depth(id){ return Math.max(0, String(num[id]||'').split('.').filter(Boolean).length-1); }
  return meta + rows.map(function(c){
    var faint = !isM[c.id];
    var h = '<div class="el-row" style="margin-left:'+(depth(c.id)*22)+'px'+(faint?';opacity:.7':'')+'">'
      + '<div><span class="el-num">'+(num[c.id]||'')+'</span>'
      + '<span class="alto-link el-title" data-sd-type="node" data-sd-id="'+c.id+'">'+(c.title||'')+'</span></div>'
      + (c.desc && !faint ? '<div class="doc-row-d">'+c.desc+'</div>' : '');
    (outs[c.id]||[]).forEach(function(o){
      var t = String(o.title||''), cls = /^liable$/i.test(t) ? 'el-liable' : /^not liable$/i.test(t) ? 'el-not' : '';
      var cases = (o.envs||[]).filter(function(e){ return ENVS[e]; }).map(function(e){
        return '<span class="alto-link" data-sd-type="env" data-sd-id="'+e+'">'+ENVS[e].name+'</span>'; }).join(', ');
      h += '<div class="el-out"><span class="alto-link el-verdict '+cls+'" data-sd-type="node" data-sd-id="'+o.id+'">'+t+'</span>'
        + (o.desc ? ' <span class="el-out-d">'+o.desc+'</span>' : '')
        + (cases ? '<div class="el-cases">'+cases+'</div>' : '') + '</div>';
    });
    return h + '</div>';
  }).join('');
}"""

ELEMENT_TREE_CSS = (
    "\n  .el-row{padding:10px 0 10px 12px;border-left:2px solid var(--border);margin-bottom:6px;line-height:1.6;}"
    "\n  .el-num{display:inline-block;min-width:3.4em;color:var(--muted);font-variant-numeric:tabular-nums;font-size:.9em;}"
    "\n  .el-title{font-weight:600;}"
    "\n  .el-out{margin:8px 0 0 3.4em;padding:6px 10px;border-radius:6px;"
    "background:color-mix(in srgb, var(--text) 4%, transparent);font-size:.94em;}"
    "\n  .el-verdict{font-weight:700;font-size:.82em;letter-spacing:.08em;text-transform:uppercase;}"
    "\n  .el-liable{color:#dc2626;} .el-not{color:#16a34a;}"
    "\n  html.dark .el-liable{color:#f87171;} html.dark .el-not{color:#4ade80;}"
    "\n  .el-out-d{opacity:.85;}"
    "\n  .el-cases{margin-top:4px;font-size:.92em;opacity:.95;}"
    "\n  html.mobile .el-out{margin-left:0;}")

# ── index pages for a big axis (ALTO-006) ───────────────────────────────────
# A hide_nav axis (a course's cases) has a page per value but no way in except
# a card chip. showDetail('index', 'env'|'theme') lists every value, grouped
# under the concept (outline) or band (linear) it is attached to, each linking
# to its page and to where it appears. _ALTO_AXES carries the labels, the
# optional source line and each value's citation, all built in Python.
AXIS_INDEX_GLUE = """
function showAxisIndex(kind){ window.showDetail('index', kind); }
function _altoAxisIndex(kind){
  var A = (window._ALTO_AXES||{})[kind]; if(!A) return;
  var base = kind.split('~')[0];
  var reg = {}, all = base==='env' ? ENVS : THEMES, field = base==='env' ? 'envs' : 'themes';
  // One Index chip per family of values ('theme~frcp'): only that family's rows.
  Object.keys(all).forEach(function(k){ if(!A.ids || A.ids.indexOf(k)>=0) reg[k]=all[k]; });
  var O = window._ALTO_OUTLINE, num = (O && O.num) || {}, par = (O && O.parent) || {};
  var byId = {}; NODES_SRC.forEach(function(n){ byId[n.id]=n; });
  // An outcome leaf files under the concept it belongs to; a linear page files by band.
  function home(n){
    if(!O){ var a = (typeof NODE_ACT!=='undefined' && NODE_ACT[n.id]!=null) ? NODE_ACT[n.id] : 0;
      return {id:'act-'+a, title:(PHASE_META[a]||{}).label||'', band:true}; }
    var p = byId[par[n.id]];
    return (p && !((O.kids||{})[n.id]||[]).length && n.tag && n.tag!==p.tag) ? p : n;
  }
  var groups = [], gi = {}, seen = {};
  NODES_SRC.forEach(function(n){
    (n[field]||[]).forEach(function(eid){
      if(!reg[eid]) return;
      var c = home(n);
      if(!gi.hasOwnProperty(c.id)){ gi[c.id]=groups.length; groups.push({c:c, rows:[], at:{}}); }
      var g = groups[gi[c.id]];
      if(!g.at.hasOwnProperty(eid)){ g.at[eid]=g.rows.length; g.rows.push({id:eid, via:[]}); }
      g.rows[g.at[eid]].via.push(n); seen[eid]=1;
    });
  });
  var loose = Object.keys(reg).filter(function(k){ return !seen[k]; });
  var color = base==='env' ? 'var(--env-color)' : 'var(--theme-color)', cites = A.cites || {};
  function blurb(e){
    var ok = (e.sections||[]).filter(function(x){ return x && x.t && x.h!==A.citeH && x.h!=='Source notes'; });
    var s = ok[0];
    if((A.blurb||[]).length) s = ok.filter(function(x){ return A.blurb.indexOf(String(x.h).toLowerCase())>=0; })[0];
    if(!s) return '';
    var t = String(s.t).replace(/<[^>]+>/g,'');
    return t.length>220 ? t.slice(0,217).replace(/\\s+\\S*$/,'')+'\\u2026' : t;
  }
  function row(eid, via){
    var e = reg[eid], b = blurb(e);
    var links = (via||[]).map(function(n){
      var c = home(n), lab = (c!==n && !c.band) ? c.title+' \\u2014 '+n.title : n.title;
      return '<span class="alto-link" data-sd-type="node" data-sd-id="'+n.id+'">'+(num[n.id]?num[n.id]+' ':'')+lab+'</span>';
    }).join(' &middot; ');
    return '<div class="doc-row" style="cursor:default">'
      + '<span class="alto-link doc-row-t" data-sd-type="'+base+'" data-sd-id="'+eid+'">'+e.name+'</span>'
      + (cites[eid] ? ' <span class="doc-row-tag">&middot; '+cites[eid]+'</span>' : '')
      + (b ? '<div class="doc-row-d">'+b+'</div>' : '')
      + (links ? '<div class="doc-row-d" style="margin-top:4px"><span class="doc-rel-lab">Appears in:</span> '+links+'</div>' : '')
      + '</div>';
  }
  var total = Object.keys(reg).length;
  var html = '<div class="detail-header"><div class="detail-symbol" style="color:'+color+'">'+A.sym+'</div><div>'
    + '<div class="detail-name" style="color:'+color+'">'+A.label+'</div>'
    + '<div class="detail-role">'+total+' '+A.unit+' &middot; in '+(O?'outline':'timeline')+' order</div>'
    + '<div class="detail-badge '+(base==='env'?'badge-env':'badge-theme')+'">Index</div></div></div>';
  (A.top||[]).forEach(function(s){ html += '<div class="detail-section"><h3>'+s.h+'</h3><p>'+s.t+'</p></div>'; });
  groups.forEach(function(g){
    var head = g.c.band ? g.c.title
      : '<span class="alto-link" data-sd-type="node" data-sd-id="'+g.c.id+'">'+(num[g.c.id]?num[g.c.id]+' ':'')+g.c.title+'</span>';
    html += '<div class="detail-section"><h3>'+head+'</h3>' + g.rows.map(function(r){ return row(r.id, r.via); }).join('') + '</div>';
  });
  if(loose.length) html += '<div class="detail-section"><h3>Not yet attached to '+(O?'a concept':'anything')+'</h3>'
    + loose.map(function(k){ return row(k, []); }).join('') + '</div>';
  window._currentDetailType = null; window._currentDetailId = null; _currentNodeId = null;
  updateNodeNavBar(null, null);
  _closeAllPanels();
  var pill = document.getElementById('timeline-return-pill');
  if(pill){ pill.style.display = 'block'; if(typeof _updateReturnPillPos==='function') _updateReturnPillPos(); }
  document.getElementById('canvas').style.display = 'none';
  document.getElementById('detail-page').classList.add('visible');
  document.querySelectorAll('.nav-btn').forEach(function(b){ b.classList.toggle('active', b.getAttribute('data-axis-index')===kind); });
  document.getElementById('detail-content').innerHTML = html;
  document.getElementById('detail-page').scrollTop = 0;
}"""

# Links out of the page: source docs, casebook pages. Also used by provenance tags.
NOTE_LINK_CSS = (
    "\n  .note-link{color:inherit;text-decoration:underline;"
    "text-decoration-color:color-mix(in srgb, var(--accent) 55%, transparent);text-underline-offset:2px;}"
    "\n  .note-link:hover{color:var(--accent);}"
    "\n  .ns-item{display:block;position:relative;padding-left:1.1em;margin:0 0 .55em;line-height:1.75;}"
    "\n  .ns-item::before{content:\"\\2022\";position:absolute;left:0;color:var(--muted);}"
    "\n  .ns-src{font-size:.72em;letter-spacing:.06em;text-transform:uppercase;"
    "color:var(--muted);white-space:nowrap;margin-left:4px;}")

# Casebook Connect's reader honours a link's #page-N only in windows at least
# 1224px wide; narrower ones (every phone) scroll to that browser's last-read
# page instead. Sending the same URL to the reader's tab again once it has
# drawn the chapter is a same-document fragment navigation, which the browser
# itself scrolls to. Safari only lets the opener navigate the tab while it
# stays its opener, so the tab keeps window.opener. Wide windows keep the
# plain link.
BOOK_JUMP = """<script id="alto-book-jump">
(function(){
  var gen=0, RE=/^https:\\/\\/(www\\.)?casebookconnect\\.com\\/[^#]*#page-\\d+$/i;
  document.addEventListener('click',function(e){
    if(e.defaultPrevented||e.button||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey) return;
    var a=e.target&&e.target.closest&&e.target.closest('a[href]');
    if(!a||!RE.test(a.href)||(window.outerWidth||window.innerWidth)>=1224) return;
    var u=a.href, w=null; try{ w=window.open(u,'_blank'); }catch(x){}
    if(!w) return;
    e.preventDefault();
    var g=++gen;
    [2500,5000,8000].forEach(function(ms){ setTimeout(function(){
      if(g===gen&&!w.closed) try{ w.location.href=u; }catch(x){}
    },ms); });
  },true);
})();
</script>"""

PROV_CSS = ("\n  .sec-prov{margin-left:8px;padding:1px 6px;border:1px solid var(--border);"
            "border-radius:8px;font-size:.85em;letter-spacing:.08em;opacity:.85;}")

# ── ← Back to <previous page> (ALTO-008) ────────────────────────────────────
# A link INSIDE a detail page that opens another detail page pushes the page
# it left; the control walks back one page at a time. Any other way of opening
# a page (nav bar, card, prev/next) or leaving the detail view clears the
# trail. Desktop: a segment in #desktop-banner-row beside Back to Overview;
# mobile: a floating pill. Must be the outermost showDetail wrapper, so it is
# emitted after every other one (end of body).
BACK_PREV = """<style id="alto-back-prev-css">
html:not(.mobile) #desktop-banner-row > .dbr-prev{ background:#2f5d3a; max-width:46vw; }
html:not(.mobile).dark #desktop-banner-row > .dbr-prev{ background:#1f3e2a; }
html:not(.mobile) #desktop-banner-row > .dbr-back:not([hidden]) + .dbr-prev{ border-left:1px solid rgba(255,255,255,.28); }
#alto-back-prev .bp-t{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
html.mobile #alto-back-prev{ position:fixed; left:50%; transform:translateX(-50%); bottom:calc(16px + env(safe-area-inset-bottom,0px));
  z-index:300; max-width:calc(100vw - 110px); display:flex; align-items:center; gap:6px; padding:10px 16px; border:0; border-radius:20px;
  background:#2f5d3a; color:#fff; font:14px Georgia,serif; box-shadow:0 6px 20px rgba(0,0,0,.28); }
html.mobile.dark #alto-back-prev{ background:#1f3e2a; }
html.mobile #alto-back-prev[hidden]{ display:none; }
html.printing #alto-back-prev{ display:none !important; }
</style>
<script id="alto-back-prev-js">
(function(){
  var root=document.documentElement, stack=[], fromDetail=false, goingBack=false;
  function mark(e){ var t=e.target; fromDetail=!!(t&&t.closest&&t.closest('#detail-content')); }
  document.addEventListener('mousedown', mark, true);
  document.addEventListener('touchstart', mark, true);
  document.addEventListener('click', function(e){ var t=e.target; if(t&&t.closest&&t.closest('#detail-content')) fromDetail=true; }, true);
  function btn(){
    var b=document.getElementById('alto-back-prev');
    if(b) return b;
    b=document.createElement('button'); b.id='alto-back-prev'; b.type='button'; b.setAttribute('hidden','');
    b.addEventListener('click', function(e){
      e.stopPropagation();
      var prev=stack.pop(); if(!prev) return;
      goingBack=true;
      try{ window.showDetail(prev.type, prev.id); }finally{ goingBack=false; }
    });
    var row=document.getElementById('desktop-banner-row');
    if(row && !root.classList.contains('mobile')){ b.className='dbr-seg dbr-prev'; row.appendChild(b); }
    else document.body.appendChild(b);
    return b;
  }
  function sync(){
    var b=btn(), top=stack[stack.length-1], dp=document.getElementById('detail-page');
    var open=dp && dp.classList.contains('visible');
    if(top && open){
      b.innerHTML='<span>&larr;</span><span class="bp-t">Back to '+top.title.replace(/[<&]/g,function(c){return c==='<'?'&lt;':'&amp;';})+'</span>';
      b.title='Back to '+top.title;
      b.removeAttribute('hidden');
    } else { b.setAttribute('hidden',''); if(!open) stack=[]; }
    var row=document.getElementById('desktop-banner-row');
    if(row && b.parentNode===row && !b.hasAttribute('hidden')) row.classList.add('active');
  }
  function current(){
    var dp=document.getElementById('detail-page'), nm=document.querySelector('#detail-content .detail-name');
    if(!dp || !dp.classList.contains('visible') || !nm || !window._altoPageNow) return null;
    return {type:window._altoPageNow.type, id:window._altoPageNow.id, title:(nm.textContent||'').trim()};
  }
  var prevFn=window.showDetail;
  window.showDetail=function(type,id){
    var was=current(), hop=fromDetail && !goingBack;
    fromDetail=false;
    var r=prevFn.apply(this, arguments);
    window._altoPageNow={type:type,id:id};
    if(!goingBack){
      if(hop && was && !(was.type===type && was.id===id)) stack.push(was);
      else if(!hop) stack=[];
    }
    try{ sync(); }catch(e){}
    return r;
  };
  var dp0=document.getElementById('detail-page');
  if(dp0) new MutationObserver(function(){ if(!dp0.classList.contains('visible')){ stack=[]; window._altoPageNow=null; } try{ sync(); }catch(e){} })
    .observe(dp0,{attributes:true,attributeFilter:['class']});
  // Other banner segments toggling must not collapse the row while this one shows.
  function watchRow(){
    var row=document.getElementById('desktop-banner-row'); if(!row){ return setTimeout(watchRow,300); }
    new MutationObserver(function(){ var b=document.getElementById('alto-back-prev');
      if(b && b.parentNode===row && !b.hasAttribute('hidden') && !row.classList.contains('active')) row.classList.add('active'); })
      .observe(row,{attributes:true,attributeFilter:['class']});
  }
  watchRow();
})();
</script>"""

# ── banner row clears the page title (ALTO-009) ─────────────────────────────
# #desktop-banner-row is fixed at top:175px, centred, over the detail page. A
# long title ("Johnson v. Wills Memorial Hospital & Nursing Home") runs under
# it. When the row would sit on the header's text, drop it to just below that
# text, inside the header above its divider, growing the header's bottom
# padding if the gap is too small. Measures through html{zoom}; a no-op when
# nothing overlaps.
BANNER_CLEARANCE = """<script id="alto-banner-clearance">
(function(){
  var root=document.documentElement;
  function hdr(){ return document.querySelector('#detail-content .detail-header'); }
  function reset(row){ if(row) row.style.top=''; var h=hdr(); if(h && h._altoPad!=null){ h.style.paddingBottom=''; h._altoPad=null; } }
  function place(){
    var row=document.getElementById('desktop-banner-row');
    if(!row || root.classList.contains('mobile')) return;
    var dp=document.getElementById('detail-page'), h=hdr();
    if(!row.classList.contains('active') || !dp || !dp.classList.contains('visible') || !h){ reset(row); return; }
    row.style.top='';
    if(h._altoPad!=null){ h.style.paddingBottom=''; h._altoPad=null; }
    var rr=row.getBoundingClientRect(); if(!rr.height) return;
    var k=rr.height/(row.offsetHeight||rr.height);              // rect px per CSS px (html zoom)
    var texts=h.querySelectorAll('.detail-name,.detail-role,.detail-badge'), hit=false, bottom=-1e9;
    Array.prototype.forEach.call(texts,function(t){
      var r=t.getBoundingClientRect(); if(!r.height) return;
      var range=document.createRange(); range.selectNodeContents(t); var ir=range.getBoundingClientRect();
      var L=ir.width?ir.left:r.left, R=ir.width?ir.right:r.right;   // the text's ink, not its block
      bottom=Math.max(bottom,r.bottom);
      if(L<rr.right+6*k && R>rr.left-6*k && r.top<rr.bottom+4*k && r.bottom>rr.top-4*k) hit=true;
    });
    if(!hit) return;
    var gap=14*k, want=bottom+gap;
    var cur=parseFloat(getComputedStyle(row).top)||0;
    row.style.top=(cur+(want-rr.top)/k)+'px';
    var need=want+rr.height+gap-h.getBoundingClientRect().bottom;
    if(need>0){ var pad=parseFloat(getComputedStyle(h).paddingBottom)||0; h._altoPad=pad; h.style.paddingBottom=(pad+need/k)+'px'; }
  }
  window._altoPlaceBanner=place;
  function later(){ requestAnimationFrame(function(){ place(); requestAnimationFrame(place); }); }
  var prevFn=window.showDetail;
  window.showDetail=function(){ var r=prevFn.apply(this,arguments); later(); return r; };
  function wire(){
    var dp=document.getElementById('detail-page'), row=document.getElementById('desktop-banner-row');
    if(!dp || !row){ return setTimeout(wire,300); }
    dp.addEventListener('scroll', place, {passive:true});
    window.addEventListener('resize', later);
    new MutationObserver(later).observe(row,{attributes:true,childList:true,subtree:true,attributeFilter:['class','hidden']});
    new MutationObserver(later).observe(dp,{attributes:true,attributeFilter:['class']});
  }
  wire();
})();
</script>"""

# ── mentions in running text link to their page (ALTO-010) ─────────────────
# Walks the text of the open detail page and the Overview after each render
# and wraps every name in _ALTO_AUTOLINK.names (built below from the material:
# full names, generated short forms, authored aliases) and every "§ N"
# reference in _ALTO_AUTOLINK.sec. A § number several values share links only
# where the page itself points at one of them. Never links a page to itself;
# card bodies are left alone (a link would fight the card's own click).
AUTOLINK = """<script id="alto-autolink">
(function(){
  var L=window._ALTO_AUTOLINK; if(!L) return;
  var names=L.names||{}, sec=L.sec||{};
  var keys=Object.keys(names).sort(function(a,b){ return b.length-a.length; });
  var esc=function(t){ return t.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&'); };
  var RE=keys.length ? new RegExp('(^|[^A-Za-z-])('+keys.map(esc).join('|')+')(?![A-Za-z0-9])','g') : null;
  var SRE=/\\u00a7\\s?(\\d+[A-Z]?)(\\([a-z]\\))?(\\s*\\((?:2d|3d)\\))?/g;
  var SKIP='a,button,.alto-link,.hc-link,.ov-node-link,.char-chip,.note-link,[data-sd-id],[data-goto],h1,script,style,textarea,.detail-name,.ns-src';
  function texts(root, test){
    var w=document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null), out=[], t;
    while((t=w.nextNode())){ if(t.nodeValue && test(t.nodeValue) && t.parentElement && !t.parentElement.closest(SKIP)) out.push(t); }
    return out;
  }
  function wrap(tn, re, resolve){
    var v=tn.nodeValue, frag=document.createDocumentFragment(), last=0, m;
    re.lastIndex=0;
    while((m=re.exec(v))){
      var lead=m[1]&&re===RE?m[1].length:0, hit=resolve(m); if(!hit) continue;
      var start=m.index+lead, txt=re===RE?m[2]:m[0];
      frag.appendChild(document.createTextNode(v.slice(last,start)));
      var sp=document.createElement('span'); sp.className='alto-link autolink';
      sp.setAttribute('data-sd-type',hit[0]); sp.setAttribute('data-sd-id',hit[1]); sp.textContent=txt;
      frag.appendChild(sp); last=start+txt.length;
    }
    if(!last) return;
    frag.appendChild(document.createTextNode(v.slice(last)));
    tn.parentNode.replaceChild(frag, tn);
  }
  function link(root, selfId, near){
    if(!root) return;
    if(RE) texts(root, function(v){ RE.lastIndex=0; return RE.test(v); }).forEach(function(tn){
      wrap(tn, RE, function(m){ var h=names[m[2]]; return h && h[1]!==selfId ? h : null; });
    });
    texts(root, function(v){ return v.indexOf('\\u00a7')>=0; }).forEach(function(tn){
      wrap(tn, SRE, function(m){
        var ids=sec['\\u00a7'+m[1]]; if(!ids) return null;
        var id=ids.length===1 ? ids[0] : ids.filter(function(i){ return near[i]; })[0];
        return id && id!==selfId ? ['theme', id] : null;
      });
    });
  }
  // The theme values this page points at, for a § number several share.
  function nearOf(type, id){
    var near={}, NS=(typeof NODES_SRC!=='undefined')?NODES_SRC:[];
    NS.forEach(function(n){
      var on = type==='node' ? n.id===id : type==='char' ? (n.chars||[]).indexOf(id)>=0
        : type==='env' ? (n.envs||[]).indexOf(id)>=0 : type==='theme' ? (n.themes||[]).indexOf(id)>=0 : false;
      if(on) (n.themes||[]).forEach(function(t){ near[t]=1; });
    });
    return near;
  }
  var prev=window.showDetail;
  window.showDetail=function(type,id){
    var r=prev.apply(this, arguments);
    try{ link(document.getElementById('detail-content'), (type==='env'||type==='theme'||type==='char')?id:null, nearOf(type,id)); }catch(e){}
    return r;
  };
  function ov(){ if(L.ov===false) return; try{ link(document.getElementById('summary-inner'), null, {}); }catch(e){} }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', ov); else ov();
})();
</script>"""

_CORP_SUFFIX = re.compile(r",? (?:Inc|Co|Corp|Ry|Ltd|L\.?L\.?C|R\. ?Co)\.?$")
_V_RE = re.compile(r"^(.+?) v\. (.+)$")
_SEC_RE = re.compile(r"§\s?(\d+[A-Z]?)")


def autolink_table(b) -> dict:
    """{names: {text: [type, id]}, sec: {"§8A": [theme ids]}} from the material.

    Generated short forms: a case's name without a trailing corporate suffix,
    and the first party of "X v. Y" when no other value in the page shares
    it. Authored aliases win over generated ones. A generated form that is
    ambiguous is dropped rather than guessed."""
    names: dict = {}
    taken: dict = {}          # generated short form → owners (to drop collisions)
    on = set(b.autolink)
    families = [(k, vals) for k, vals in (
        ("env", b.axes[0].values if len(b.axes) > 0 else []),
        ("theme", b.axes[1].values if len(b.axes) > 1 else [])) if k in on]
    for kind, values in families:
        for v in values:
            full = v.name.strip()
            if len(full) >= 4:
                names[full] = [kind, v.id]
            forms = {}          # ordered: the page must build byte-identically
            short = _CORP_SUFFIX.sub("", full)
            if short != full:
                forms[short] = 1
            m = _V_RE.match(short)
            if m and kind == "env":
                first = re.sub(r"^(The|In re) ", "", m.group(1)).strip()
                if len(first) >= 4:
                    forms[first] = 1
            if full.startswith("The ") and len(full) > 8:
                forms[full[4:]] = 1
            for f in forms:
                taken.setdefault(f, set()).add((kind, v.id))
    # A surname that is also a party to some other case ("Williams" in both
    # "Williams v. Hays" and "Mohr v. Williams") names neither reliably.
    parties: dict = {}
    for kind, values in families:
        for v in values:
            m = _V_RE.match(_CORP_SUFFIX.sub("", v.name.strip()))
            if m:
                for side in (m.group(1), m.group(2)):
                    parties.setdefault(side.strip(), set()).add(v.id)
    for f, owners in taken.items():
        others = parties.get(f, set()) - {o[1] for o in owners}
        if len(owners) == 1 and f not in names and not others:
            names[f] = list(next(iter(owners)))
    for kind, values in families:
        for v in values:
            for a in v.aliases:
                names[a.strip()] = [kind, v.id]
    if "char" in on:
        # A character by full name, and by a first or last name no other
        # character shares ("Ada" for Ada Reyes; not a surname two characters
        # carry — an alias settles that one).
        parts: dict = {}
        for e in b.entities:
            words = e.name.split()
            if len(words) > 1:
                for w in (words[0], words[-1]):
                    parts.setdefault(w, set()).add(e.id)
        for e in b.entities:
            if len(e.name.strip()) >= 3:
                names[e.name.strip()] = ["char", e.id]
        for w, owners in parts.items():
            if len(owners) == 1 and len(w) >= 3 and w not in names:
                names[w] = ["char", next(iter(owners))]
        for e in b.entities:
            for a in e.aliases:
                names[a.strip()] = ["char", e.id]
    # A name of a kind that is NOT linked, but contains a linked one
    # ("Hale House", a setting, holds "Hale", a character), is matched whole
    # and left alone, so its first word does not link to the wrong page.
    others = [e.name for e in b.entities] if "char" not in on else []
    for k, ax in (("env", b.axes[0] if len(b.axes) > 0 else None),
                  ("theme", b.axes[1] if len(b.axes) > 1 else None)):
        if ax and k not in on:
            others += [v.name for v in ax.values]
    for o in others:
        o = o.strip()
        if o not in names and any(re.search(r"(?<![A-Za-z])" + re.escape(n)
                                            + r"(?![A-Za-z])", o) for n in names):
            names[o] = None
    sec: dict = {}
    for v in (dict(families).get("theme") or []):
        for k in dict.fromkeys(_SEC_RE.findall(v.name)):
            sec.setdefault("§" + k, []).append(v.id)
    # Names are escaped text by now (sanitize ran); the walker sees decoded
    # text, so match on the decoded form.
    import html as _h
    return {"names": {_h.unescape(k): v for k, v in names.items()}, "sec": sec,
            "ov": b.autolink_overview}


# ── build-time sections: citations and source notes (ALTO-011/012/013) ──────

def _chapter_num(ch: str) -> str:
    m = re.search(r"\d+", ch or "")
    return m.group(0) if m else ""


def cite_html(ax, v, short: bool) -> str:
    """A value's citation as page text, linked when the axis has a cite_link
    and the chapter has a known section. "" when the value has no cite."""
    c = v.cite or {}
    if not c:
        return ""
    if c.get("note") and not c.get("p"):
        return (c.get("short") or c["note"]) if short else c["note"]
    page = c.get("p", "")
    label = f"p. {page}"
    tl = ax.cite_link or {}
    if tl.get("url") and page:
        num = _chapter_num(c.get("ch", ""))
        secs = tl.get("sections") or {}
        if "{sec}" not in tl["url"] or num in secs:
            url = (tl["url"].replace("{sec}", quote(str(secs.get(num, "")), safe=""))
                   .replace("{p}", quote(str(page), safe="")))
            label = (f'<a class="note-link" href="{esc(url)}" target="_blank" '
                     f'rel="noopener">{label}</a>')
    ch = c.get("ch", "")
    if short:
        n = _chapter_num(ch)
        return (f"Ch. {n}, {label}" if n else label)
    return f"{ch}, {label}" if ch else label


def cite_heading(ax) -> str:
    return esc((ax.cite_link or {}).get("label") or "Citation")


def source_section(ids, docs_by_id) -> "Section | None":
    """"Source notes": the documents a page was built from, linked when the
    manifest gave a url. Google Docs can deep-link only to headings and
    bookmarks, so a document-level link is the reliable default."""
    items = []
    for sid in dict.fromkeys(ids or []):
        d = docs_by_id.get(sid)
        if not d:
            continue
        name = d["name"]
        icon = LOCAL_ICON.format(id=sid) if d.get("local") else ""
        if d.get("url"):
            items.append(f'<span class="ns-item"><a class="note-link" href="{esc(d["url"])}" '
                         f'target="_blank" rel="noopener" data-src="{sid}">{name}</a>'
                         f'{icon}</span>')
        elif icon:
            items.append(f'<span class="ns-item"><a class="note-link" href="#" '
                         f'data-src="{sid}">{name}</a>{icon}</span>')
        else:
            items.append(f'<span class="ns-item">{name}</span>')
    return Section(h="Source notes", t="".join(items)) if items else None


# ── the material's own files, opened from this computer ─────────────────────
# A source with a `local` path (brief.source_docs) is tagged data-src wherever
# the page links to it, with sanitize.LOCAL_ICON after the link. Only a page
# opened from disk — an offline copy — can reach a file:// URL, so on the web
# nothing changes: the icons stay hidden and links go to the web copy. On disk
# the icons show, and a link to the web copy opens the local file instead when
# the browser reports no connection. The paths are in _ALTO_LOCAL alone, in a
# block of its own that a share snapshot empties (reidentify.strip_local).
#
# `root` is the folder the files have in common. An offline copy saved in a
# folder of that name, somewhere else, is taken to have moved together with
# the files: they are looked for beside it, not at the old path.
LOCAL_OPEN = r"""<style id="alto-local-css">
  .alto-src-local{display:none;}
  html.alto-disk .alto-src-local{display:inline-block;width:13px;height:13px;margin-left:4px;vertical-align:-2px;color:var(--muted);text-decoration:none;}
  html.alto-disk .alto-src-local::before{content:"";display:block;width:100%;height:100%;background:currentColor;
    -webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='none' stroke='black' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3' y='3.5' width='10' height='7' rx='1'/%3E%3Cpath d='M1.5 12.5h13'/%3E%3C/svg%3E") center/contain no-repeat;
    mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='none' stroke='black' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3' y='3.5' width='10' height='7' rx='1'/%3E%3Cpath d='M1.5 12.5h13'/%3E%3C/svg%3E") center/contain no-repeat;}
  html.alto-disk .alto-src-local:hover{color:var(--accent);}
  @media print{.alto-src-local{display:none!important;}}
</style>
<script id="alto-local-open">
(function(){
  var L=window._ALTO_LOCAL||{}, F=L.files||{};
  var base=String(document.baseURI||'');
  var disk=/^file:/i.test(base) && Object.keys(F).length>0;
  if(disk) document.documentElement.classList.add('alto-disk');
  function leaf(x){ return String(x).replace(/[\\/]+$/,'').split(/[\\/]/).pop(); }
  function pathOf(id){
    var p=F[id].p, root=L.root||'';
    try{
      var here=decodeURIComponent(base.replace(/^file:\/\/[^\/]*/i,'').replace(/[?#].*$/,'').replace(/\/[^\/]*$/,''));
      if(/^\/[A-Za-z]:\//.test(here)) here=here.slice(1);
      var r=root.replace(/\\/g,'/');
      if(r && here!==r && leaf(here)===leaf(r) && p.replace(/\\/g,'/').indexOf(r+'/')===0)
        p=here+p.replace(/\\/g,'/').slice(r.length);
    }catch(e){}
    return p;
  }
  function fileUrl(p){
    p=p.replace(/\\/g,'/'); if(p.charAt(0)!=='/') p='/'+p;
    return 'file://'+encodeURI(p).replace(/\?/g,'%3F').replace(/#/g,'%23');
  }
  window._altoOpenLocal=function(id){
    if(!disk || !F[id]) return false;
    var u=fileUrl(pathOf(id));
    // window.open: WebKit ignores a scripted link click to file:// from inside
    // the offline copy's srcdoc frame, and honours this.
    var w=null; try{ w=window.open(u,'_blank'); }catch(e){}
    if(!w){ var a=document.createElement('a'); a.href=u; a.target='_blank';
      document.body.appendChild(a); a.click(); a.remove(); }
    return true;
  };
  document.addEventListener('click',function(e){
    var a=e.target&&e.target.closest&&e.target.closest('a[data-src],a[data-src-local]');
    if(!a) return;
    var icon=a.hasAttribute('data-src-local');
    var id=a.getAttribute(icon?'data-src-local':'data-src');
    var web=/^https?:/i.test(a.getAttribute('href')||'');
    if(disk && F[id] && (icon || !web || navigator.onLine===false)){
      e.preventDefault(); e.stopPropagation(); window._altoOpenLocal(id); return;
    }
    if(!web) e.preventDefault();
  },true);
})();
</script>"""


# ── Edit with Claude: the way back to Claude ────────────────────────────────
# The building half of the edit toggle (manual_edit.py draws the toggle beside
# light/dark) opens Claude with a prompt naming this timeline — this script is
# that prompt (window._altoEditTimeline). Never on a phone: timelines are made
# with Claude on a computer. The last unit's band is lengthened by ROOM (engine
# patch edit-tile-inside-the-last-band) so edit mode's "+ Add a unit" has a row
# inside the timeline's own background. A share snapshot (id 's-...', see
# reidentify) is someone else's timeline: none of it, and no extra room.
EDIT_TILE = r"""<style id="alto-edit-css">
  #alto-edit-toast{position:fixed;left:50%;bottom:28px;transform:translateX(-50%) translateY(20px);opacity:0;
    pointer-events:none;z-index:400;padding:10px 16px;border-radius:12px;background:var(--surface);color:var(--text);
    border:1px solid var(--border);box-shadow:0 10px 30px var(--node-rest-shadow);font-size:13px;
    transition:opacity .2s ease,transform .2s ease;}
  #alto-edit-toast.show{opacity:1;transform:translateX(-50%) translateY(0);pointer-events:auto;}
  #alto-edit-toast a{color:inherit;margin-left:6px;}
</style>
<script id="alto-edit-tile">
(function(){
  var E = window._ALTO_EDIT || {};
  // `key` is blocks.ID_PATTERNS' doc_save_key, which reidentify rewrites in a
  // share — so a share reads back 's-…' here, like its COURSE_ID.
  var tid = String(E.key || '').replace(/^alto-doc-/, '');
  if(!tid || tid.indexOf('s-') === 0) return;
  // Not on a phone: timelines are made and changed with Claude on a computer.
  if(/iPhone|iPod|Android.*Mobile|Windows Phone/i.test(navigator.userAgent)) return;
  // The last unit's band grows by this much (engine patch
  // edit-tile-inside-the-last-band), so the tile sits inside the timeline's
  // own background. Set while the page parses — the first layout runs later.
  var ROOM = 70;
  window._altoEditRoom = ROOM;
  var TITLE = E.title || document.title;
  var GET = 'https://alto-get.web.app';
  // The address of this page (…/pv/<key>/) names the account's site and the
  // published copy, so a chat that cannot see the draft can still find it.
  function where(){
    var u = '';
    try{ u = window.top.location.href; }catch(e){}
    if(!/^https:\/\/[^\/]+\/pv\/[a-z0-9]+/.test(u)){ try{ u = document.referrer || ''; }catch(e){} }
    var m = /^(https:\/\/[^\/]+\/pv\/[a-z0-9]+\/?)/.exec(u);
    return m ? m[1] : '';
  }
  function prompt(){
    var at = where(), host = at ? at.split('/')[2] : '';
    return "I want to edit my Alto timeline \"" + TITLE + "\" (timeline id: " + tid +
      (at ? ", page: " + at : "") + "). " +
      "If the Alto connector isn't connected here yet, help me install it from " + GET +
      " first. Then open this timeline with Alto's get_timeline" +
      (at ? " \u2014 if it isn't found, it may be in another of my Alto accounts: look with " +
            "list_projects(account=\"all\"), and add my site (" + host + ") with connect_account " +
            "if it isn't listed" : "") +
      ". Then ask me what I'd like " +
      "to change \u2014 I may have new notes to add, sources to link, or edits to make. " +
      "Follow Alto's interview guide to make the changes, then rebuild and republish it.";
  }
  function go(u){
    // The page usually runs in a frame (private shell, offline copy): hand the
    // link to the top window, which is where an app link or claude.ai belongs.
    try{ window.top.location.href = u; } catch(e){ try{ window.open(u, '_blank'); } catch(_){ location.href = u; } }
  }
  function toast(web){
    var el = document.getElementById('alto-edit-toast');
    if(!el){ el = document.createElement('div'); el.id = 'alto-edit-toast'; document.body.appendChild(el); }
    el.textContent = 'Opening the Claude app… ';
    var a = document.createElement('a'); a.textContent = 'Open in browser instead';
    a.href = web; a.target = '_blank'; a.rel = 'noopener'; el.appendChild(a);
    el.classList.add('show');
    clearTimeout(toast._t); toast._t = setTimeout(function(){ el.classList.remove('show'); }, 6000);
  }
  function openClaude(){
    var q = encodeURIComponent(prompt()), web = 'https://claude.ai/new?q=' + q;
    var touch = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent) ||
                (/Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints > 1);
    if(touch){ go(web); return; }          // the Claude app intercepts the universal link
    toast(web);
    go('claude://claude.ai/new?q=' + q);
  }
  window._altoEditTimeline = openClaude;
  var world = null;
  // The editing controls live in the edit toggle beside light/dark
  // (manual_edit.py); the last unit's band keeps a little room under its cards
  // for edit mode's "+ Add a unit".
  function place(){
    world = document.getElementById('world');
    if(!world) return;
    // The page ends exactly where the timeline's background (the glass slab)
    // ends: no strip of bare page gradient below it (Luke). #world's height
    // is its min-height plus its padding; absolutely placed children add none.
    var slab = document.getElementById('glass-slab');
    if(!slab || !slab.offsetHeight) return;
    var end = slab.offsetTop + slab.offsetHeight, cs = getComputedStyle(world);
    var pads = (parseFloat(cs.paddingTop) || 0) + (parseFloat(cs.paddingBottom) || 0);
    var mh = Math.max(0, end - pads) + 'px';
    if(world.style.minHeight !== mh) world.style.minHeight = mh;
    // A timeline shorter than the window would still show page below its
    // end: lengthen the last band until the background fills the window.
    var cv = document.getElementById('canvas');
    var k = (world.getBoundingClientRect().height / world.offsetHeight) || 1;   // CSS zoom
    var short = cv ? Math.ceil(cv.clientHeight / k - end) : 0;
    if(short > 0 && typeof initLayout === 'function' && !place._relaying){
      window._altoEditRoom = (window._altoEditRoom || ROOM) + short;
      place._relaying = true;
      try{ initLayout(); if(window._applyActiveFilters) window._applyActiveFilters(); }
      finally{ place._relaying = false; }
    }
  }
  var tries = 0;
  (function poll(){ try{ place(); }catch(_){} if(++tries < 60) setTimeout(poll, 250); })();
  window.addEventListener('resize', function(){ setTimeout(function(){ try{ place(); }catch(_){} }, 250); });
  if(window.ResizeObserver){
    var ro = new ResizeObserver(function(){ try{ place(); }catch(_){} }), watched = null;
    (function watch(){
      var w = document.getElementById('world');
      if(w && w !== watched){ if(watched) ro.unobserve(watched); ro.observe(w); watched = w; }
      if(tries < 60) setTimeout(watch, 500);
    })();
  }
})();
</script>"""


NOTES_TRASH = r"""<style id="alto-trash-css">
  #notes-footer .nt-row{display:flex;align-items:center;justify-content:center;gap:14px;}
  #notes-footer .nt-btn{box-sizing:border-box;background:var(--surface);border:1px solid var(--border);color:var(--muted);
    cursor:pointer;padding:0;display:flex;align-items:center;justify-content:center;width:32px;height:32px;
    border-radius:50%;line-height:1;flex-shrink:0;}
  #notes-footer .nt-btn svg{display:block;pointer-events:none;}
  #notes-footer .nt-btn:disabled{opacity:.35;cursor:default;}
  #notes-footer .nt-btn.on{color:var(--text);border-color:var(--muted);}
  html:not(.mobile) #notes-footer .nt-btn, html.mobile #notes-footer .nt-btn{background:var(--card-glass-bg,var(--surface)) !important;border-color:var(--card-glass-border,var(--border)) !important;}
  html:not(.mobile) #notes-footer .nt-btn:not(:disabled):hover{border-color:var(--muted) !important;color:var(--text) !important;}
  #notes-trash{display:none;flex:1;overflow-y:auto;padding:12px;}
  #notes-panel.trash-mode #notes-list{display:none !important;}
  #notes-panel.trash-mode #notes-trash{display:block;}
  #notes-footer .nt-home{display:none !important;}
  #notes-panel.trash-mode #notes-add-btn{display:none !important;}
  #notes-panel.trash-mode #notes-footer .nt-home{display:flex !important;}
  #notes-panel.trash-mode #notes-report-btn, #notes-panel.trash-mode #notes-clear-btn{display:none !important;}
  html.mobile #notes-trash{-webkit-overflow-scrolling:touch;}
  #notes-trash .nt-empty{font-size:12px;color:var(--muted);text-align:center;padding:40px 20px;line-height:1.8;}
  #notes-trash .nt-item{background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:10px 12px;
    margin-bottom:10px;font-size:12px;line-height:1.6;color:var(--text);}
  #notes-trash .nt-quote{font-style:italic;color:var(--muted);margin-bottom:6px;font-size:11px;
    border-left:2px solid var(--accent);padding-left:8px;word-break:break-word;}
  #notes-trash .nt-text{color:var(--text);word-break:break-word;white-space:pre-wrap;}
  #notes-trash .nt-when{font-size:10.5px;color:var(--muted);margin-top:6px;letter-spacing:.02em;}
  #notes-trash .nt-acts{display:flex;gap:8px;margin-top:8px;}
  #notes-trash .nt-acts button{flex:1;font:inherit;font-size:11.5px;padding:6px 8px;border-radius:14px;cursor:pointer;
    background:var(--surface);border:1px solid var(--border);color:var(--text);}
  #notes-trash .nt-acts button.nt-purge{color:var(--muted);}
  #notes-trash .nt-acts button.nt-purge.sure{color:#d04a4a;border-color:#d04a4a;}
  @media print{#notes-footer .nt-row .nt-btn,#notes-trash{display:none !important;}}
</style>
<script id="alto-notes-trash">
(function(){
  var KEY = '__ALTO_HL_KEY__', TKEY = KEY + '-trash', CAP = 200;
  var ls = window.localStorage;
  function rd(k){ try { var a = JSON.parse(ls.getItem(k) || '[]'); return Array.isArray(a) ? a : []; } catch(e){ return []; } }
  function emptyFreeform(h){ return h && h.kind === 'freeform' && !(h.note && h.note.length) && !(h.quote && h.quote.length); }

  function wr(k, v){ try { ls.setItem(k, v); } catch(e){} }

  /* Every delete lands in the trash: the × on a note and Clear all. The store
     is read before and after the page's own delete runs, so whatever it took
     out is what is kept, and one click = one batch (Undo brings back a whole
     Clear all). Wrapping the two functions rather than localStorage.setItem:
     Safari ignores an override of that method on the localStorage object. */
  function trashGone(prev, next){
    var keep = {}; next.forEach(function(h){ if(h) keep[h.id] = 1; });
    var gone = prev.filter(function(h){ return h && !keep[h.id] && !emptyFreeform(h); });
    if(!gone.length) return;
    var now = Date.now(), batch = 'b' + now.toString(36), t = rd(TKEY), have = {};
    t.forEach(function(h){ have[h.id + '§' + h.quote] = 1; });
    gone.forEach(function(h){
      if(have[h.id + '§' + h.quote]) return;
      var c = {}; for(var f in h) c[f] = h[f];
      c.del = now; c.batch = batch; t.push(c);
    });
    t.sort(function(a,b){ return (a.del||0) - (b.del||0); });
    wr(TKEY, JSON.stringify(t.slice(-CAP)));
    refresh();
  }
  function wrap(name){
    var f = window[name];
    if(typeof f !== 'function' || f.__altoTrash) return;
    var w = function(){
      var before = rd(KEY), r = f.apply(this, arguments);
      try { trashGone(before, rd(KEY)); } catch(e){}
      return r;
    };
    w.__altoTrash = true;
    window[name] = w;
  }
  function wrapAll(){ wrap('deleteHighlight'); wrap('clearAllHighlights'); }
  wrapAll();
  window.addEventListener('load', function(){ wrapAll(); setTimeout(wrapAll, 400); });

  function el(tag, cls, text){ var n = document.createElement(tag); if(cls) n.className = cls; if(text != null) n.textContent = text; return n; }
  var UNDO_SVG = '<svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3.5 3 6.5l3 3"/><path d="M3.4 6.5H9a3.6 3.6 0 0 1 0 7.2H6.5"/></svg>';
  var HOME_SVG = '<svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 7.6 8 2.8l5.5 4.8"/><path d="M4 6.6v6.2a.9.9 0 0 0 .9.9h6.2a.9.9 0 0 0 .9-.9V6.6"/><path d="M6.6 13.7V9.6h2.8v4.1"/></svg>';
  var TRASH_SVG = '<svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2.8 4.2h10.4"/><path d="M6.3 4.2V2.8h3.4v1.4"/><path d="M4 4.2l.6 8.6a1 1 0 0 0 1 .9h4.8a1 1 0 0 0 1-.9l.6-8.6"/></svg>';

  function panel(){ return document.getElementById('notes-panel'); }
  function inTrash(){ var p = panel(); return !!(p && p.classList.contains('trash-mode')); }

  function reload(){
    try { if(typeof loadHighlights === 'function') loadHighlights(); } catch(e){}
    window.highlights = rd(KEY).sort(function(a,b){ return (a.ts||0) - (b.ts||0); });
    try { if(typeof renderNotesList === 'function') renderNotesList(); } catch(e){}
    try { if(typeof updateNotesToggle === 'function') updateNotesToggle(); } catch(e){}
  }

  /* A restored note gets a fresh id. The old id is on the sync ledger of
     removed highlights, and a ledger entry beats any copy that still carries it. */
  function bringBack(items){
    if(!items.length) return;
    var arr = rd(KEY), n = 0;
    items.forEach(function(h){
      var c = {}; for(var f in h) if(f !== 'del' && f !== 'batch') c[f] = h[f];
      c.id = (h.kind === 'freeform' ? 'fn_' : 'hl-r') + Date.now() + '_' + (n++) + Math.floor(Math.random()*1000);
      if(!c.ts) c.ts = Date.now();
      arr.push(c);
    });
    arr.sort(function(a,b){ return (a.ts||0) - (b.ts||0); });
    var ids = {}; items.forEach(function(h){ ids[h.id + '§' + h.quote] = 1; });
    var t = rd(TKEY).filter(function(h){ return !ids[h.id + '§' + h.quote]; });
    wr(TKEY, JSON.stringify(t));
    wr(KEY, JSON.stringify(arr));
    reload(); refresh();
  }

  function undo(){
    var t = rd(TKEY); if(!t.length) return;
    var last = t[t.length - 1];
    bringBack(t.filter(function(h){ return h.batch === last.batch; }));
  }
  function purge(h){
    wr(TKEY, JSON.stringify(rd(TKEY).filter(function(x){ return !(x.id === h.id && x.quote === h.quote); })));
    refresh();
  }

  function when(ts){
    try {
      var d = new Date(ts), now = new Date();
      var day = d.toDateString() === now.toDateString() ? 'today' : d.toLocaleDateString(undefined, {month:'short', day:'numeric'});
      return 'Deleted ' + day + ', ' + d.toLocaleTimeString(undefined, {hour:'numeric', minute:'2-digit'});
    } catch(e){ return 'Deleted'; }
  }
  var DOT = {yellow:'rgba(255,220,50,0.7)', blue:'rgba(74,158,255,0.5)'};

  function renderTrash(){
    var box = document.getElementById('notes-trash'); if(!box) return;
    box.textContent = '';
    var t = rd(TKEY).slice().reverse();
    if(!t.length){ box.appendChild(el('div', 'nt-empty', 'Nothing deleted yet.')); return; }
    t.forEach(function(h){
      var item = el('div', 'nt-item');
      if(h.kind !== 'freeform' && h.quote){
        var q = el('div', 'nt-quote', '“' + (h.quote.length > 120 ? h.quote.slice(0,120) + '…' : h.quote) + '”');
        q.style.borderColor = DOT[h.color] || 'rgba(232,100,130,0.55)';
        item.appendChild(q);
      }
      if(h.note) item.appendChild(el('div', 'nt-text', h.note));
      else if(h.kind !== 'freeform') item.appendChild(el('div', 'nt-text', 'No note')).style.cssText = 'color:var(--muted);font-style:italic';
      item.appendChild(el('div', 'nt-when', when(h.del)));
      var acts = el('div', 'nt-acts');
      var b1 = el('button', 'nt-restore', 'Bring back'); b1.type = 'button';
      b1.addEventListener('click', function(){ bringBack([h]); });
      var b2 = el('button', 'nt-purge', 'Delete forever'); b2.type = 'button';
      b2.addEventListener('click', function(){
        if(b2.classList.contains('sure')){ purge(h); return; }
        b2.classList.add('sure'); b2.textContent = 'Really delete?';
        setTimeout(function(){ b2.classList.remove('sure'); b2.textContent = 'Delete forever'; }, 3500);
      });
      acts.appendChild(b1); acts.appendChild(b2); item.appendChild(acts);
      box.appendChild(item);
    });
  }

  function refresh(){
    var u = document.getElementById('notes-undo-btn'), tb = document.getElementById('notes-trash-btn');
    var n = rd(TKEY).length;
    var H = window._altoNotesHist;
    if(u) u.disabled = !n && !(H && H.canUndo());
    if(tb){ tb.title = n ? 'Deleted notes (' + n + ')' : 'Deleted notes'; }
    if(inTrash()) renderTrash();
  }

  function setMode(on){
    var p = panel(), title = document.getElementById('notes-header-title'), tb = document.getElementById('notes-trash-btn');
    if(!p) return;
    p.classList.toggle('trash-mode', !!on);
    if(tb){ tb.classList.toggle('on', !!on); tb.setAttribute('aria-pressed', on ? 'true' : 'false'); }
    if(title){
      if(on){ title.setAttribute('data-was', title.textContent); title.textContent = 'Deleted notes'; }
      else if(title.hasAttribute('data-was')){ title.textContent = title.getAttribute('data-was'); title.removeAttribute('data-was'); }
    }
    if(on) renderTrash();
  }

  function install(){
    var add = document.getElementById('notes-add-btn'), list = document.getElementById('notes-list'), footer = document.getElementById('notes-footer');
    if(!add || !list || !footer || document.getElementById('notes-trash')) return;
    var box = document.createElement('div'); box.id = 'notes-trash';
    list.parentNode.insertBefore(box, list.nextSibling);
    var row = document.createElement('div'); row.className = 'nt-row';
    add.parentNode.insertBefore(row, add);
    var u = document.createElement('button'); u.id = 'notes-undo-btn'; u.type = 'button'; u.className = 'nt-btn';
    u.title = 'Undo'; u.setAttribute('aria-label', 'Undo'); u.innerHTML = UNDO_SVG;
    /* Undo steps back through every change (new, edited, deleted, recoloured: notes_v2); with no
       changes recorded it still brings back the last deleted batch. */
    u.addEventListener('click', function(){
      var H = window._altoNotesHist;
      if(H && H.canUndo()) H.undo(); else undo();
    });
    var tb = document.createElement('button'); tb.id = 'notes-trash-btn'; tb.type = 'button'; tb.className = 'nt-btn';
    tb.title = 'Deleted notes'; tb.setAttribute('aria-label', 'Deleted notes'); tb.setAttribute('aria-pressed', 'false'); tb.innerHTML = TRASH_SVG;
    tb.addEventListener('click', function(){ setMode(!inTrash()); });
    /* In the deleted list the + has no job, so its place holds Home: back to the notes. */
    var hm = document.createElement('button'); hm.id = 'notes-home-btn'; hm.type = 'button'; hm.className = 'nt-btn nt-home';
    hm.title = 'Back to notes'; hm.setAttribute('aria-label', 'Back to notes'); hm.innerHTML = HOME_SVG;
    hm.addEventListener('click', function(){ setMode(false); });
    row.appendChild(u); row.appendChild(add); row.appendChild(hm); row.appendChild(tb);
    /* Closing the panel leaves the deleted list: Notes reopens on the notes. */
    var wasOpen = false;
    new MutationObserver(function(){
      var p = panel(), open = !!(p && p.classList.contains('open'));
      if(wasOpen && !open && inTrash()) setMode(false);
      wasOpen = open;
    }).observe(panel(), {attributes:true, attributeFilter:['class']});
    window.addEventListener('storage', function(ev){ if(ev && (ev.key === TKEY || ev.key === KEY)) refresh(); });
    window.addEventListener('alto-trash-sync', refresh);
    refresh();
  }
  window._altoNotesTrash = {undo: undo, refresh: refresh, key: TKEY, trashGone: trashGone};
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install); else install();
})();
</script>"""


def notes_trash(b) -> str:
    """NOTES_TRASH with this timeline's highlight storage key (the page's own
    `alto-hl-{tid}` text, which a share re-stamps like every other copy)."""
    from .blocks import ID_PATTERNS
    return NOTES_TRASH.replace("__ALTO_HL_KEY__", ID_PATTERNS["hl_key"].format(tid=b.timeline_id)) + "\n"


def edit_tile(b) -> str:
    """EDIT_TILE with this timeline's title and id, which its prompt quotes."""
    from .blocks import ID_PATTERNS
    data = json.dumps({"title": b.title or "",
                       "key": ID_PATTERNS["doc_save_key"].format(tid=b.timeline_id)},
                      ensure_ascii=False).replace("</", "<\\/")
    return f"<script>window._ALTO_EDIT={data};</script>\n" + EDIT_TILE + "\n"


def local_sources(b) -> "tuple[str, list[str]]":
    """The page's _ALTO_LOCAL block plus LOCAL_OPEN, or "" when no source has a
    local copy — a timeline without one is byte-for-byte what it was. Warns
    about a path with no file behind it: the build runs on the author's own
    computer, so a missing file there is a real mistake, not a moved one."""
    import os
    files, warnings = {}, []
    for d in b.source_docs:
        loc = (d.get("local") or "").strip() if isinstance(d, dict) else ""
        if not loc:
            continue
        p = os.path.expanduser(loc)
        if not os.path.isfile(p):
            warnings.append(f"source {d['id']}: no file at {loc} — its "
                            "offline link will not open anything")
        files[d["id"]] = {"p": p}
    if not files:
        return "", warnings
    dirs = [os.path.dirname(f["p"]) for f in files.values()]
    try:
        root = os.path.commonpath(dirs)
    except ValueError:              # different drives
        root = ""
    data = json.dumps({"root": root, "files": files}, ensure_ascii=False)
    block = (f'<script id="{LOCAL_BLOCK_ID}">window._ALTO_LOCAL='
             + data.replace("</", "<\\/") + ";</script>\n")
    return block + LOCAL_OPEN + "\n", warnings


# The id reidentify.strip_local (and alto-cloud.js) look for.
LOCAL_BLOCK_ID = "alto-local-src"


def prov_heading(s) -> str:
    """A section heading with its provenance tag (ALTO-014)."""
    if not s.prov or (s.h or "").strip().lower() == PROVENANCE[s.prov].lower():
        return s.h
    return f'{s.h}<span class="sec-prov">{PROVENANCE[s.prov]}</span>'


def _list_and(items) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + (", and " if len(items) > 2 else " and ") + items[-1]


def outline_overview(b, nodes) -> str:
    """ALTO-005: an outline build with no authored overview gets one assembled
    from the outline itself. Each section (band) gets

      * a heading and a SUMMARY paragraph — the section's own `summary` when the
        author wrote one from the notes, else composed from the hub's
        description and the names of the concepts it branches into;
      * then each concept of its first two levels, linked, with its one-line
        description and the concepts beneath it.

    Nothing is written that the nodes do not already say. Emitted in the same
    deep-link form sanitize produces, so the Overview's link upgrader handles
    it."""
    from html import escape as esc
    kids: dict = {}
    for n in nodes:
        if n.parent:
            kids.setdefault(n.parent, []).append(n)

    def chip(n):
        return (f'<span class="ov-node-link">{esc(n.title, quote=False)}'
                f'<button class="ov-node-btn" '
                f"onclick=\"showDetail('node','{n.id}')\"></button></span>")

    def line(n):
        return chip(n) + (f" — {esc(n.desc, quote=False)}" if n.desc else "")

    out = ["<h2>Overview</h2>"]
    for i, a in enumerate(b.acts):
        roots = [n for n in nodes if n.act == i and not n.parent]
        if not roots:
            continue
        # The band's full name reads better than its abbreviation ("Personal
        # Jurisdiction", not "PJ") unless it is shouted (ACT ONE — ARRIVAL).
        head = a.label if a.label and not a.label.isupper() else (a.short or a.label)
        out.append(f"<h2>{esc(head, quote=False)}</h2>")
        paras = [p.strip() for p in (a.summary or "").split("\n\n") if p.strip()]
        if paras:
            out += [f"<p>{esc(p, quote=False)}</p>" for p in paras]
        else:
            # Composed: what the hub says, then where the section goes.
            hub = roots[0]
            branches = kids.get(hub.id, [])
            text = esc(hub.desc, quote=False) if hub.desc else ""
            if branches:
                text = (text + " " if text else "") + (
                    "It covers " + _list_and([esc(c.title, quote=False)
                                              for c in branches]) + ".")
            if text:
                out.append(f"<p>{text}</p>")
        for k, r in enumerate(roots):
            # The first hub's description is the summary's lead (or the
            # summary replaces it), so it appears as a link alone.
            out.append(f"<p>{chip(r) if k == 0 else line(r)}</p>")
            for c in kids.get(r.id, []):
                sub = kids.get(c.id, [])
                tail = ""
                if sub:
                    tail = " Covers " + ", ".join(chip(s) for s in sub) + "."
                out.append(f"<p>{line(c)}{tail}</p>")
    return "\n".join(out)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "x"


def index_entries(index_axes) -> list:
    """The Index chips: [(key, kind, label, value ids)]. One per axis, or — when
    some of its values carry a `group` — one per group (key 'theme~frcp'), in
    order of first appearance, with any ungrouped values under the axis's own
    name. The key is what showAxisIndex() and _ALTO_AXES are addressed by."""
    out = []
    for kind, ax in index_axes:
        label = ax.nav_label or ax.label
        if not any(v.group for v in ax.values):
            out.append((kind, kind, label, [v.id for v in ax.values]))
            continue
        groups: dict = {}
        for v in ax.values:
            groups.setdefault(v.group or "", []).append(v.id)
        used: set = set()
        for g, ids in groups.items():
            key = f"{kind}~{_slug(g or label)}"
            while key in used:
                key += "x"
            used.add(key)
            out.append((key, kind, g or label, ids))
    return out


def axes_config(b, index_axes) -> str:
    """window._ALTO_AXES for the index pages: label, glyph, source line, and
    each value's short citation — one entry per Index chip (index_entries)."""
    docs = {d["id"]: d for d in b.source_docs}
    cfg = {}
    axes_by_kind = dict(index_axes)
    for key, kind, label, ids in index_entries(index_axes):
        ax = axes_by_kind[kind]
        src = source_section(ax.sources, docs)
        top = [{"h": s.h, "t": s.t} for s in ax.index_sections if s.t]
        if src:
            top.append({"h": "Source", "t": src.t})
        vals = [v for v in ax.values if v.id in set(ids)]
        cfg[key] = {
            "label": label,
            "unit": (ax.singular or ax.label).lower() + ("" if (ax.singular or "").endswith("s") else "s"),
            "sym": "&#9670;" if kind == "env" else "&#167;",
            "top": top,
            "blurb": [h.lower() for h in ax.index_blurb],
            "citeH": cite_heading(ax),
            "cites": {v.id: cite_html(ax, v, True) for v in vals if v.cite},
        }
        if key != kind:
            cfg[key]["ids"] = ids
    return ("\nwindow._ALTO_AXES=" + json.dumps(cfg, ensure_ascii=False)
            .replace("</", "<\\/") + ";")
