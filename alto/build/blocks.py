"""Generate every template region/token for a timeline page from a Brief.

Formats mirror the originals recorded in TEMPLATE_MANIFEST.json (see M0
extraction) so the engine consumes them identically.

Contract with sanitize.py: by the time a Brief reaches this module,
`sanitize_brief()` has reduced every plain-text field to tag-free text and
rebuilt every markup-bearing one through an allowlist, so no value can open an
HTML tag. This module is still responsible for *syntactic* safety in the
non-HTML contexts the template has — `js_str()` for JS string literals,
`url_q()` for URL parameters, and `css_color()` for anything landing in a CSS
declaration. `one_line()` flattens the title for the two sinks that display a
string rather than parse it (navigator.share and the mailto subject).
"""
from __future__ import annotations

import json
import re
from urllib.parse import quote as url_q

from .brief import Brief, Node, COL_SETS, roman
from .sanitize import css_color, esc, one_line
from .layout import MOBILE_STEP, MOBILE_OX, MOBILE_OY, MOBILE_WORLD_W

# Generic section-builder code (same shape as the template's empty defaults —
# kept in one place because emit() replaces the whole region span).
NODE_SECTIONS_D = (
    "sections = ((nd.sections)||[]).filter(s=>s&&s.t);\n"
    "    if(sections.length === 0) sections.push({h:'Synopsis', t: n.desc});")
CHAR_SECTIONS_D = ("sections=(p.sections||[]).filter(s=>s&&s.t)"
                   ".concat(_altoDoctrineBody(id));")
ENV_SECTIONS_D = "sections=(e.sections||[]).filter(s=>s&&s.t);"
THEME_SECTIONS_D = "sections=(th.sections||[]).filter(s=>s&&s.t);"
NODE_SECTIONS_M = (
    "var sections=((ndDet.sections)||[]).filter(function(s){return s&&s.t;});\n"
    "          if(sections.length===0) sections.push({h:'Synopsis',t:nd.desc||''});")
CHAR_SECTIONS_M = ("var chSecs=(cp.sections||[]).filter(function(s){return s&&s.t;})"
                   ".concat(_altoDoctrineBody(targetId));")
ENV_SECTIONS_M = "var enSecs=(en.sections||[]).filter(function(s){return s&&s.t;});"
THEME_SECTIONS_M = "var thSecs=(th.sections||[]).filter(function(s){return s&&s.t;});"

FALLBACK_GLYPH = "&#9670;"   # ◆ — used when an entity/axis value has no SVG

_SVG_STYLE_RE = re.compile(r'(<svg\b[^>]*?)\s+style="[^"]*"')


# Every place a page is stamped with WHICH timeline it is. These decide the
# localStorage namespace and the Firestore sync key, so two pages sharing them
# share their reader's highlights, notes and reports — which is exactly what
# must not happen between a private master and a copy handed to someone else.
#
# Listed here rather than inline below because alto/build/reidentify.py and
# alto-cloud.js both have to know the same set, and a page identity that three
# files each described separately would drift silently and merge two readers'
# work the day it did.
#
# hl_key_legacy is absent on purpose: it is hl_key plus a suffix, so rewriting
# hl_key rewrites it too. A separate entry would match the same text twice.
ID_PATTERNS = {
    "course_id_lit": "courseId:'{tid}'",
    "course_id_var": "var COURSE_ID = '{tid}';",
    "doc_save_key": "alto-doc-{tid}",
    "hl_key": "alto-hl-{tid}",
    "rp_key": "alto-rp-{tid}",
}


def _normalize_symbol(svg: str) -> str:
    """Strip the root svg's style attribute. A baked-in margin/vertical-align
    (the old §C1 wrapper carried both) skews centring inside the flex-centred
    chip contexts; spacing belongs to the rendering context, supplied by the
    glyph-context CSS emitted with nav_char_css."""
    if not svg:
        return svg
    return _SVG_STYLE_RE.sub(r"\1", svg, count=1)


def js_str(s: str) -> str:
    """Single-quoted JS string literal, </script>-safe."""
    out = json.dumps(s or "", ensure_ascii=False)[1:-1]
    out = out.replace('\\"', '"').replace("'", "\\'")
    out = out.replace("<", "\\u003c")
    return "'" + out + "'"


def _rgb(hexcolor: str):
    h = hexcolor.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _sections_js(sections, indent="    ") -> str:
    items = ",".join(
        f"{{h:{js_str(s.h)},t:{js_str(s.t)}}}" for s in (sections or []) if s.t)
    return f"sections:[{items}]"


def resolve_filters(b: Brief, nodes: list[Node],
                    connections: list = None) -> list[dict]:
    """Brief.filters → the engine's two scalar filter slots.

    Returns [{slot, node_key, spec, values: [(id, name)], node_value: {node
    id → value id}}]; first filter lands on the 'era' slot (node field
    `era`), second on 'weight' (node field `examWeight` — the engine's
    historical name for it)."""
    out = []
    for i, f in enumerate(b.filters[:2]):
        slot, node_key = (("era", "era"), ("weight", "examWeight"))[i]
        if f.source == "entity":
            values = [(e.id, e.name) for e in b.entities]
            nv = {n.id: n.entity_ids[0] for n in nodes if n.entity_ids}
        elif f.source in ("axis1", "axis2"):
            ax = b.axes[0] if f.source == "axis1" else b.axes[1]
            attr = "axis1_values" if f.source == "axis1" else "axis2_values"
            values = [(v.id, v.name) for v in ax.values]
            nv = {n.id: getattr(n, attr)[0] for n in nodes if getattr(n, attr)}
        elif f.source == "acts":
            values = [(f"act-{j+1}", a.short or a.label)
                      for j, a in enumerate(b.acts)]
            nv = {n.id: f"act-{n.act+1}" for n in nodes}
        elif f.source == "coverage":
            # Derived from how much the student authored on each node: a node
            # with ≥2 detail sections is Solid, otherwise Thin (stub/one-liner).
            values = [("solid", "Solid"), ("thin", "Thin")]
            nv = {n.id: ("solid" if sum(1 for s in n.sections if s.t) >= 2
                         else "thin") for n in nodes}
        elif f.source == "depth":
            # How deep each node sits in the structure the connections already
            # describe: a node no spine edge points at is a root (Level 1), its
            # children Level 2, everything below Level 3+. Nothing extra to
            # author, and §0-safe for the same reason coverage is — it measures
            # the shape of the student's own outline rather than adding to it.
            # Node.parent is the tree when there is one, and it is authored
            # rather than derived — so prefer it over the spine edges, which in
            # outline mode are themselves generated FROM it later in the build.
            # Reading the edges here would make depth depend on call ordering.
            parent = {n.id: n.parent for n in nodes if n.parent}
            if not parent:
                for c in (connections or []):
                    if len(c) >= 3 and c[2] == "spine" and c[0] != c[1]:
                        parent.setdefault(c[1], c[0])

            def _depth(nid):
                seen, d = {nid}, 1
                while nid in parent and parent[nid] not in seen:
                    nid = parent[nid]
                    seen.add(nid)
                    d += 1
                    if d > 64:          # authored cycle; stop rather than hang
                        break
                return d

            depths = {n.id: _depth(n.id) for n in nodes}
            deepest = max(depths.values(), default=1)
            values = [("d1", "Level 1"), ("d2", "Level 2")]
            if deepest >= 3:
                values.append(("d3", "Level 3+"))
            nv = {nid: ("d1" if d == 1 else "d2" if d == 2 else "d3")
                  for nid, d in depths.items()}
        else:  # custom
            values = [(v.id, v.name) for v in f.values]
            nv = {n.id: n.filters[f.id] for n in nodes
                  if f.id in (n.filters or {})}
        out.append({"slot": slot, "node_key": node_key, "spec": f,
                    "values": values, "node_value": nv})
    return out


# Runtime glue emitted (into the `orders` region) only when filters exist.
# Two jobs the frozen engine no longer does itself:
#   1. bind clicks for the drawer's [data-sd-axis] filter chips (ConLaw bound
#      them at creation; the frozen drawer builder emits none of its own);
#   2. re-label the desktop active-filter banner, whose label maps are
#      pre-template fossils with a raw-id fallback.
FILTER_GLUE = """
(function(){
  document.addEventListener('click', function(e){
    var b = e.target && e.target.closest && e.target.closest('#nav-drawer [data-sd-axis]');
    if(!b) return;
    e.preventDefault(); e.stopPropagation();
    if(typeof window.setMobileFilter === 'function'){
      window.setMobileFilter(b.getAttribute('data-sd-axis'), b.getAttribute('data-sd-id'));
    }
  }, true);
  /* The engine's _activeFilters is script-scoped, so mirror the toggle by
     wrapping filterCanvas; the banner relabel falls back to a reverse lookup
     on the rendered raw id when the mirror is stale (direct clears). */
  var state = {};
  var of = window.filterCanvas;
  if(typeof of === 'function'){
    window.filterCanvas = function(axis, value){
      if(state[axis]===value) delete state[axis]; else state[axis]=value;
      return of.apply(this, arguments);
    };
  }
  function relabel(seg, key, labels){
    if(!seg || seg.hasAttribute('hidden')) return;
    var sp = seg.querySelector('span');
    if(!sp) return;
    var name = labels[state[key]] || labels[sp.textContent];
    if(name) sp.textContent = name;
  }
  /* A filter change does not navigate, so the engine's post-navigation label
     patch never runs: the mobile prev/next strip keeps naming the neighbours
     the filter just hid, and its tap targets still point at them. Every
     mobile filter path funnels through setMobileFilter, so re-patch there. */
  var mtries = 0;
  (function wrapMobile(){
    var omf = window.setMobileFilter;
    if(typeof omf !== 'function'){ if(++mtries < 80) setTimeout(wrapMobile, 250); return; }
    window.setMobileFilter = function(){
      var r = omf.apply(this, arguments);
      try{ if(window._patchTimelineLabels) window._patchTimelineLabels(); }catch(_){}
      return r;
    };
  })();
  var tries = 0;
  (function wrap(){
    var orig = window._updateDesktopFilterBar;
    if(typeof orig !== 'function'){ if(++tries < 80) setTimeout(wrap, 250); return; }
    window._updateDesktopFilterBar = function(){
      var r = orig.apply(this, arguments);
      try{
        var row = document.getElementById('desktop-banner-row');
        if(row){
          relabel(row.querySelector('.dbr-era'), 'era', ERA_LABELS);
          relabel(row.querySelector('.dbr-weight'), 'weight', WEIGHT_LABELS);
        }
      }catch(_){}
      return r;
    };
  })();
})();"""


# Emitted into the `orders` region. Builds a doctrine/entity detail page from
# the student's OWN material when authored sections are thin/absent — a member
# roster + the relations among those members, all re-projected from NODES_SRC /
# CONNECTIONS (never invented). This is the never-empty fallback: an entity has
# ≥1 member by construction, so the page is always populated; and every token is
# the student's own text or a derived count, so it is never slop. Rows carry
# data-goto and a delegated listener opens the node — no quote-escaping needed.
DOCTRINE_BODY = """
function _altoDoctrineBody(id){
  if(typeof NODES_SRC==='undefined') return [];
  var members = NODES_SRC.filter(function(n){ return (n.chars||[]).indexOf(id)!==-1; });
  if(!members.length) return [];
  var nn = (typeof _ALTO_NODE_NOUN!=='undefined' && _ALTO_NODE_NOUN) || 'Case';
  var titleOf={}; NODES_SRC.forEach(function(n){ titleOf[n.id]=n.title; });
  var memberSet={}; members.forEach(function(n){ memberSet[n.id]=1; });
  var actSet={};
  members.forEach(function(n){ var a=(typeof NODE_ACT!=='undefined'&&NODE_ACT[n.id]!=null)?NODE_ACT[n.id]:0; actSet[a]=1; });
  var spans=Object.keys(actSet).map(function(a){ return (typeof PHASE_META!=='undefined'&&PHASE_META[a])?PHASE_META[a].label:''; }).filter(Boolean);
  var thin = members.length<=2 || members.every(function(n){
    var d=(typeof NODE_DETAILS!=='undefined')&&NODE_DETAILS[n.id];
    return !(d&&d.sections&&d.sections.filter(function(s){return s&&s.t;}).length);
  });
  var meta = '<div class="doc-meta">'
    + members.length+' '+nn.toLowerCase()+(members.length===1?'':'s')
    + (spans.length?' &middot; '+spans.join(', '):'')
    + (thin?' &middot; <strong class="doc-thin">THIN &mdash; sparse in your notes</strong>':'')
    + '</div>';
  var rows = members.map(function(n){
    return '<div class="doc-row" data-goto="'+n.id+'">'
      + '<span class="doc-row-t">'+(n.title||'')+'</span>'
      + (n.tag?' <span class="doc-row-tag">'+n.tag+'</span>':'')
      + (n.desc?'<div class="doc-row-d">'+n.desc+'</div>':'')
      + '</div>';
  }).join('');
  var heading = nn + (/s$/i.test(nn)?'':'s');
  var out=[{h: heading, t: meta+rows}];
  if(typeof CONNECTIONS!=='undefined'){
    var rl=(typeof REL_LABELS!=='undefined')?REL_LABELS:{};
    var internal=CONNECTIONS.filter(function(c){ return memberSet[c[0]]&&memberSet[c[1]]; });
    if(internal.length){
      var relRows=internal.map(function(c){
        var lab=rl[c[2]]||'related';
        var col=(typeof COLOR_MAP!=='undefined'&&COLOR_MAP[c[2]])||'var(--line-flow)';
        return '<div class="doc-rel"><span class="doc-rel-dot" style="background:'+col+'"></span>'
          +(titleOf[c[0]]||c[0])+' <span class="doc-rel-lab">'+lab+' &rarr;</span> '+(titleOf[c[1]]||c[1])+'</div>';
      }).join('');
      out.push({h:'How they connect', t:relRows});
    }
  }
  return out;
}
(function(){
  if(window._altoDocRowBound) return; window._altoDocRowBound=1;
  document.addEventListener('click', function(e){
    var r = e.target && e.target.closest && e.target.closest('.doc-row[data-goto]');
    if(r && typeof showDetail==='function'){ e.preventDefault(); showDetail('node', r.getAttribute('data-goto')); }
  });
})();"""


# Interactive relation "Lines" key (emitted into `orders`). Clicking a line-key
# chip isolates that relation's edges on the canvas (dims the rest); active state
# lives in the chips' .active class so the engine's own nav-resets keep it in
# sync. Plus a per-edge hover tooltip (tubes get pointer-events via CSS since
# #river-svg is otherwise click-through). Dims only lines — node dimming is the
# filter's job, and touching it here would fight the filter state.
# Deep links inside detail-page section text. The overview's own upgrader
# (initOverviewNavLinks) cannot serve these: it runs once, only when the overview
# panel opens, and only for 'node' — a chip rendered later into #detail-content
# would stay an un-upgraded span, which .ov-node-btn{display:none} makes
# invisible. One delegated listener covers desktop, mobile and the swipe peek.
# Data attributes rather than an inline onclick, so nothing has to survive a JS
# string literal on the way in.
ALTO_LINK_GLUE = """
(function(){
  if(window._altoLinkBound) return; window._altoLinkBound=1;
  document.addEventListener('click', function(e){
    var a=e.target && e.target.closest && e.target.closest('.alto-link[data-sd-id]');
    if(!a || typeof showDetail!=='function') return;
    e.preventDefault(); e.stopPropagation();
    showDetail(a.getAttribute('data-sd-type')||'node', a.getAttribute('data-sd-id'));
  }, true);
})();
"""

# Printing an outline. The engine's own "main timeline" print lays every node
# out as a card hanging off a vertical spine — right for a sequence, wrong for a
# containment tree, where what you want on paper is the outline itself: nested
# headings, real outline numerals, the rule under each, and the authority beside
# it. An engine patch hands the data here (ACT_SEQS / NODES / PHASE_META / ENVS
# are module-scoped, so this cannot be done from outside without one).
#
# "With what is given" is the whole rule: a concept with nothing written under
# it still gets its heading, and nothing is filled in for it.
OUTLINE_PRINT_GLUE = """
window._altoPrintOutline = function(ACT_SEQS, NODES, PHASE_META, ENVS){
  var O = window._ALTO_OUTLINE; if(!O) return '';
  function esc(s){ return String(s==null?'':s).replace(/[&<>]/g,function(c){
    return c==='&'?'&amp;':(c==='<'?'&lt;':'&gt;'); }); }
  var byId={}; NODES.forEach(function(n){ byId[n.id]=n; });
  var out=['<div class="print-ol-doc">__ALTO_TOK_print_title__'];
  ACT_SEQS.forEach(function(ids, ui){
    var pm = PHASE_META[ui] || null;
    var inUnit={}; ids.forEach(function(id){ inUnit[id]=1; });
    out.push('<section class="print-ol-unit"><h2 class="print-ol-h">'
      + esc(pm ? pm.label : ('UNIT ' + (ui+1))) + '</h2>');
    function row(id, depth){
      var n = byId[id]; if(!n) return;
      out.push('<div class="print-ol-row" style="--lvl:' + depth + '">');
      out.push('<span class="print-ol-num">' + esc(O.label[id] || '') + '</span>');
      out.push('<div class="print-ol-body">');
      out.push('<span class="print-ol-name">' + esc(n.title || id) + '</span>');
      // the student's own one-liner, verbatim
      if(n.desc) out.push('<div class="print-ol-desc">' + esc(n.desc) + '</div>');
      // authority, named the way an outline cites it
      var cites = (n.envs || []).map(function(e){
        return esc((ENVS[e] && ENVS[e].name) || e); });
      if(cites.length) out.push('<div class="print-ol-cite">' + cites.join('; ') + '</div>');
      out.push('</div></div>');
      (O.kids[id] || []).forEach(function(kid){
        if(inUnit[kid]) row(kid, depth + 1); });
    }
    ids.forEach(function(id){ if(!O.parent[id]) row(id, 0); });
    out.push('</section>');
  });
  out.push('</div>');
  return out.join('');
};"""


# Relation filters dim cards, not just line tubes. LINES_GLUE still owns the
# tubes and the chips' active state; this runs just after it (a 0ms timeout, so
# the class toggle has already landed) and applies the node half.
#
# It deliberately uses its own `rel-dimmed` class rather than the engine's
# `dimmed`. The engine owns `dimmed` for slot filters, and two writers on one
# class is exactly the fight LINES_GLUE's comment warned about. Two classes
# compose instead: a card is lit only when it carries neither, which is the
# stacking we want — a node must satisfy the slot filters AND touch an active
# relation.
REL_FILTER_GLUE = """
(function(){
  if(window._altoRelFilterBound) return; window._altoRelFilterBound=1;
  function apply(){
    var active=[], nodes=document.querySelectorAll('#world .node');
    document.querySelectorAll('.line-key-btn[data-rel-key].active')
      .forEach(function(b){ active.push(b.getAttribute('data-rel-key')); });
    for(var i=0;i<nodes.length;i++){
      var card=nodes[i].querySelector('.node-card'); if(!card) continue;
      var id=nodes[i].id.slice(5), keep=!active.length;
      for(var j=0;!keep && j<active.length;j++){
        var set=(typeof REL_NODES!=='undefined' && REL_NODES[active[j]])||[];
        if(set.indexOf(id)>=0) keep=true;
      }
      card.classList.toggle('rel-dimmed', !keep);
    }
  }
  document.addEventListener('click', function(e){
    var b=e.target && e.target.closest && e.target.closest('.line-key-btn[data-rel-key]');
    if(b) setTimeout(apply, 0);
  }, true);
})();"""


# Entity filter: a Filter tab on the right edge (same rail as Notes and the
# overview star) opening a panel of the timeline's entity chips. A card stays lit
# when it carries at least one selected entity; the rest dim with their own
# `ent-dimmed` class, which composes with the engine's slot filters and the
# relation filters the same way `rel-dimmed` does. The chips are in the panel
# (desktop) and the drawer (mobile), never in the nav bar — the nav already has
# each entity once, as a link to its page.
ENT_FILTER_GLUE = """
(function(){
  if(window._altoEntFilterBound) return; window._altoEntFilterBound=1;
  var sel={};
  function keys(){ return Object.keys(sel); }
  function apply(){
    var on=keys(), nodes=document.querySelectorAll('#world .node');
    for(var i=0;i<nodes.length;i++){
      var card=nodes[i].querySelector('.node-card'); if(!card) continue;
      var id=nodes[i].id.slice(5), keep=!on.length;
      for(var j=0;!keep && j<on.length;j++){
        if((ENT_NODES[on[j]]||[]).indexOf(id)>=0) keep=true;
      }
      card.classList.toggle('ent-dimmed', !keep);
    }
    document.querySelectorAll('.ent-filter-btn[data-ent-key]').forEach(function(b){
      b.classList.toggle('active', !!sel[b.getAttribute('data-ent-key')]);
    });
    var tab=document.getElementById('filter-toggle');
    if(tab){ tab.classList.toggle('active', on.length>0); tab.setAttribute('data-n', on.length||''); }
    var clr=document.getElementById('ef-clear'); if(clr) clr.hidden=!on.length;
  }
  function build(){
    if(document.getElementById('filter-toggle')) return;
    var tab=document.createElement('button');
    tab.id='filter-toggle'; tab.type='button';
    tab.title='Filter by '+ENT_LABEL; tab.setAttribute('aria-label','Filter by '+ENT_LABEL);
    tab.setAttribute('aria-expanded','false');
    tab.innerHTML='<svg viewBox="0 0 20 20" width="17" height="17" style="display:block" fill="currentColor" aria-hidden="true"><path d="M2 3.5h16l-6.2 7.4v5.1l-3.6 1.9v-7z"/></svg>';
    var panel=document.createElement('div');
    panel.id='ef-panel'; panel.setAttribute('role','dialog'); panel.setAttribute('aria-label','Filter by '+ENT_LABEL);
    var head=document.createElement('div'); head.className='ef-head';
    var ttl=document.createElement('span'); ttl.textContent='Filter by '+ENT_LABEL;
    var clr=document.createElement('button'); clr.type='button'; clr.id='ef-clear'; clr.hidden=true; clr.textContent='Clear';
    head.appendChild(ttl); head.appendChild(clr); panel.appendChild(head);
    var list=document.createElement('div'); list.className='ef-list';
    ENT_ITEMS.forEach(function(it){
      var b=document.createElement('button'); b.type='button';
      b.className='ent-filter-btn ef-chip'; b.setAttribute('data-ent-key', it.id);
      b.style.setProperty('--c', it.color);
      var s=document.createElement('span'); s.className='ef-sym'; s.innerHTML=it.symbol; b.appendChild(s);
      var n=document.createElement('span'); n.className='ef-name'; n.textContent=it.name; b.appendChild(n);
      var c=document.createElement('span'); c.className='ef-count'; c.textContent=it.count; b.appendChild(c);
      list.appendChild(b);
    });
    panel.appendChild(list);
    document.body.appendChild(panel); document.body.appendChild(tab);
    function open(v){ panel.classList.toggle('open', v); tab.setAttribute('aria-expanded', v?'true':'false'); }
    tab.addEventListener('click', function(e){ e.stopPropagation(); open(!panel.classList.contains('open')); });
    clr.addEventListener('click', function(){ sel={}; apply(); });
    document.addEventListener('click', function(e){
      if(panel.classList.contains('open') && !e.target.closest('#ef-panel') && !e.target.closest('#filter-toggle')) open(false);
    });
    document.addEventListener('keydown', function(e){ if(e.key==='Escape') open(false); });
  }
  document.addEventListener('click', function(e){
    var b=e.target && e.target.closest && e.target.closest('.ent-filter-btn[data-ent-key]');
    if(!b) return;
    e.preventDefault(); e.stopPropagation();
    var k=b.getAttribute('data-ent-key');
    if(sel[k]) delete sel[k]; else sel[k]=1;
    apply();
  }, true);
  // A re-render (theme toggle, back from a detail page) rebuilds the cards, and
  // the mobile drawer is built when opened; put the filter back on both.
  var queued=false;
  new MutationObserver(function(){
    if(queued || !keys().length) return; queued=true;
    requestAnimationFrame(function(){ queued=false; apply(); });
  }).observe(document.body, {childList:true, subtree:true});
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', build); else build();
})();"""


LINES_GLUE = """
function isolateRelation(key){
  var svg=document.getElementById('river-svg'); if(!svg||typeof CONNECTIONS==='undefined') return;
  var btns=document.querySelectorAll('.line-key-btn[data-rel-key]');
  btns.forEach(function(b){ if(b.getAttribute('data-rel-key')===key) b.classList.toggle('active'); });
  var active={};
  btns.forEach(function(b){ if(b.classList.contains('active')) active[b.getAttribute('data-rel-key')]=1; });
  var tubes=svg.querySelectorAll('[data-edge]');
  if(!Object.keys(active).length){ tubes.forEach(function(p){ p.style.opacity=''; }); return; }
  var keep={};
  CONNECTIONS.forEach(function(c){ if(active[c[2]]) keep[c[0]+'|'+c[1]]=1; });
  tubes.forEach(function(p){ p.style.opacity = keep[p.getAttribute('data-edge')] ? '1' : '0.08'; });
}
(function(){
  if(window._altoLinesBound) return; window._altoLinesBound=1;
  document.addEventListener('click', function(e){
    var b=e.target && e.target.closest && e.target.closest('.line-key-btn[data-rel-key]');
    if(b){ e.preventDefault(); e.stopPropagation(); isolateRelation(b.getAttribute('data-rel-key')); }
  }, true);
  var tip=null;
  function edgeInfo(edge){
    if(typeof CONNECTIONS==='undefined') return '';
    var p=edge.split('|'), from=p[0], to=p[1], c=null;
    for(var i=0;i<CONNECTIONS.length;i++){ if(CONNECTIONS[i][0]===from&&CONNECTIONS[i][1]===to){ c=CONNECTIONS[i]; break; } }
    if(!c) return '';
    var rl=(typeof REL_LABELS!=='undefined')?REL_LABELS:{}, tt={};
    if(typeof NODES_SRC!=='undefined') NODES_SRC.forEach(function(n){ tt[n.id]=n.title; });
    return (rl[c[2]]?rl[c[2]]+': ':'')+(tt[from]||from)+' → '+(tt[to]||to);
  }
  document.addEventListener('mouseover', function(e){
    var p=e.target && e.target.closest && e.target.closest('#river-svg [data-edge]'); if(!p) return;
    var info=edgeInfo(p.getAttribute('data-edge')); if(!info) return;
    if(!tip){ tip=document.createElement('div'); tip.className='line-tip'; document.body.appendChild(tip); }
    tip.textContent=info; tip.style.display='block';
  });
  document.addEventListener('mousemove', function(e){
    if(tip && tip.style.display==='block'){ tip.style.left=(e.clientX+12)+'px'; tip.style.top=(e.clientY+14)+'px'; }
  });
  document.addEventListener('mouseout', function(e){
    var p=e.target && e.target.closest && e.target.closest('#river-svg [data-edge]');
    if(p && tip){ tip.style.display='none'; }
  });
})();"""



# Mobile depth cue (outline mode). On the desktop canvas, depth is geometry —
# hubs centre, spokes branch. The mobile stack has no geometry, so a level-3
# sub-point's card face is indistinguishable from a root concept's. Give every
# child card a breadcrumb in the footer's empty right half — "under {parent}",
# echoing the detail page's SITS UNDER — tappable to feature the parent.
# Authored structure only (_ALTO_OUTLINE.parent is Node.parent verbatim);
# desktop and print are untouched.
CRUMB_GLUE = """
(function(){
  function jump(p){ return function(e){
    e.preventDefault(); e.stopPropagation();
    if(typeof featureNode === 'function') featureNode(p, true);
  }; }
  function inject(){
    var O = window._ALTO_OUTLINE;
    if(!O || !document.querySelector('.node .node-footer')) return false;
    if(!document.getElementById('alto-crumb-css')){
      var st = document.createElement('style');
      st.id = 'alto-crumb-css';
      st.textContent = '.node-crumb{display:none;}' +
        'html.mobile .node-crumb{display:block;margin-left:auto;max-width:48%;' +
        'overflow:hidden;white-space:nowrap;text-overflow:ellipsis;text-align:right;' +
        'font-size:11px;color:var(--muted);background:none;border:none;padding:0;' +
        'font-family:inherit;letter-spacing:.02em;cursor:pointer;}' +
        'html.printing .node-crumb{display:none !important;}';
      document.head.appendChild(st);
    }
    Object.keys(O.parent).forEach(function(id){
      var card = document.getElementById('node-' + id);
      var f = card && card.querySelector('.node-footer');
      if(!f || f.querySelector('.node-crumb')) return;
      var pid = O.parent[id];
      /* NODES is a top-level const — global lexical scope, not a window
         property — so it must be referenced bare, behind a typeof guard. */
      var _list = (typeof NODES !== 'undefined') ? NODES : [];
      var pn = _list.find(function(n){ return n.id === pid; });
      if(!pn) return;
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'node-crumb';
      b.textContent = 'under ' + pn.title;
      b.setAttribute('aria-label', 'Sits under ' + pn.title + ' — go there');
      b.addEventListener('click', jump(pid));
      b.addEventListener('touchend', jump(pid), {passive: false});
      f.appendChild(b);
    });
    return true;
  }
  /* The cards the glue first sees are the pre-rendered ones; engine init
     rebuilds them once, sweeping early injections away. So: keep re-injecting
     (idempotent) through the init window, and again after every featureNode —
     the same seam the template uses for its own post-nav patches. */
  var tries = 0;
  (function go(){ inject(); if(++tries < 80) setTimeout(go, 250); })();
  (function hook(){
    var fn = window.featureNode;
    if(typeof fn === 'function' && !fn._altoCrumbs){
      var w = function(){ var r = fn.apply(this, arguments);
        try{ inject(); }catch(_){} return r; };
      w._altoCrumbs = true;
      window.featureNode = w;
      return;
    }
    if(!(fn && fn._altoCrumbs)) setTimeout(hook, 250);
  })();
})();"""


# Outline mode's node detail page: where you are, then what you contain.
# Same shape as DOCTRINE_BODY — a runtime function emitted into `orders` that
# synthesizes sections from data the page already carries, so the frozen
# engine's detail renderer needs no change. Children are `alto-link` chips, so
# the one delegated handler that serves inline links serves these too, on
# desktop, mobile and the swipe peek alike.
OUTLINE_BODY = """
function _altoOutlineHead(id){
  var O = window._ALTO_OUTLINE; if(!O || !O.parent) return [];
  var chain = [], cur = O.parent[id], guard = 0;
  while(cur && guard++ < 64){ chain.unshift(cur); cur = O.parent[cur]; }
  if(!chain.length) return [];
  var titleOf = {};
  if(typeof NODES_SRC!=='undefined') NODES_SRC.forEach(function(n){ titleOf[n.id]=n.title; });
  var parts = chain.map(function(pid){
    return '<span class="alto-link" data-sd-type="node" data-sd-id="'+pid+'">'
      + ((O.num[pid]?O.num[pid]+' ':'') + (titleOf[pid]||pid)) + '</span>';
  });
  return [{h:'Sits under', t:'<div class="ol-trail">'+parts.join(' <span class="ol-sep">\\u203a</span> ')+'</div>'}];
}
function _altoOutlineTail(id){
  var O = window._ALTO_OUTLINE; if(!O || !O.kids) return [];
  var kids = O.kids[id] || []; if(!kids.length) return [];
  var titleOf = {}, descOf = {};
  if(typeof NODES_SRC!=='undefined') NODES_SRC.forEach(function(n){
    titleOf[n.id]=n.title; descOf[n.id]=n.desc; });
  var rows = kids.map(function(kid){
    return '<div class="ol-row">'
      + '<span class="ol-num">'+(O.label[kid]||'')+'</span>'
      + '<span class="alto-link ol-name" data-sd-type="node" data-sd-id="'+kid+'">'
      + (titleOf[kid]||kid) + '</span>'
      + (descOf[kid] ? '<div class="ol-d">'+descOf[kid]+'</div>' : '')
      + '</div>';
  }).join('');
  return [{h:'Contains', t:rows}];
}"""

# Outline mode splices its own section builder: ancestry, then the student's
# own sections, then the children. The Synopsis fallback still applies when a
# concept has none of the three.
NODE_SECTIONS_OUTLINE_D = (
    "sections = _altoOutlineHead(id)"
    ".concat(((nd.sections)||[]).filter(s=>s&&s.t))"
    ".concat(_altoOutlineTail(id));\n"
    "    if(sections.length === 0) sections.push({h:'Synopsis', t: n.desc});")
NODE_SECTIONS_OUTLINE_M = (
    "var sections=_altoOutlineHead(targetId)"
    ".concat(((ndDet.sections)||[]).filter(function(s){return s&&s.t;}))"
    ".concat(_altoOutlineTail(targetId));\n"
    "          if(sections.length===0) sections.push({h:'Synopsis',t:nd.desc||''});")


def _sym(svg: str) -> str:
    return js_str(svg) if svg else js_str(FALLBACK_GLYPH)


def timeline_blocks(b: Brief, nodes: list[Node], positions, heights,
                    mgrid, mobile_world_h: int, *, reports_href: str = None,
                    view_path: str = "", connections: list = None,
                    warnings: list = None) -> tuple[dict, dict]:
    """Return (regions, tokens) for emit() against timeline_template.html.

    nodes must be validated, in narrative order, with col set and positions
    resolved. mgrid: id -> [colIndex, row]. connections (optional) drives the
    relation "line key" — only relations actually used by a connection appear.
    """
    tid = b.timeline_id
    ax1 = b.axes[0] if len(b.axes) > 0 else None
    ax2 = b.axes[1] if len(b.axes) > 1 else None
    ent_by_id = {e.id: e for e in b.entities}
    # Per-entity member count + "thin" flag — the nav "gap radar": a doctrine
    # with ≤2 members or only stub (section-less) members reads as thin.
    ent_count = {e.id: 0 for e in b.entities}
    ent_has_sec = {e.id: False for e in b.entities}
    for n in nodes:
        for eid in (n.entity_ids or []):
            if eid in ent_count:
                ent_count[eid] += 1
                if any(s.t for s in n.sections):
                    ent_has_sec[eid] = True

    def _ent_thin(eid):
        return ent_count[eid] <= 2 or not ent_has_sec[eid]

    for e in b.entities:
        e.symbol_svg = _normalize_symbol(e.symbol_svg)
    for ax in b.axes:
        for v in ax.values:
            v.symbol_svg = _normalize_symbol(v.symbol_svg)

    # Canvas filters: resolved slot data plus which axes' navigation chips the
    # filter chips replace (replace_nav on entity/axis1/axis2 sources).
    resolved_filters = resolve_filters(b, nodes, connections)
    nav_replaced = {rf["spec"].source for rf in resolved_filters
                    if rf["spec"].replace_nav
                    and rf["spec"].source in ("entity", "axis1", "axis2")}

    # Everything kept out of the navigation chrome — the nav row, the mobile
    # drawer and the legend dots. A replace_nav'd axis is hidden there AND loses
    # its card chips (below); an Axis.hide_nav axis is hidden here only, so its
    # chips stay on the cards and its detail pages stay reachable.
    nav_hidden = nav_replaced | {
        f"axis{i + 1}" for i, ax in enumerate(b.axes[:2]) if ax.hide_nav}

    # sanitize has already rewritten any showDetail() anchors in section text,
    # so the emitted spans are the honest signal for whether this build needs
    # the link handler and its CSS at all. A brief with no deep links adds no
    # bytes for them — the same discipline as the relation colour vars above.
    def _has_alto_link() -> bool:
        # Outline detail pages build their child links and ancestry trail at
        # runtime (OUTLINE_BODY), so they never appear in the emitted section
        # text this scan looks at — but they still need the handler and CSS.
        if b.mode == "outline":
            return True
        if 'class="alto-link"' in (b.overview_html or ""):
            return True
        groups = [n.sections for n in nodes] + [e.sections for e in b.entities]
        groups += [v.sections for ax in b.axes for v in ax.values]
        return any('class="alto-link"' in (s.t or "")
                   for g in groups for s in (g or []))

    uses_alto_link = _has_alto_link()

    # Relation "line key": the legend that names which line color means which
    # relation. Only relations actually used by a connection are shown, in
    # vocabulary order; a labeled spine appears last as the neutral flowing line.
    used_rels = {c[2] for c in (connections or []) if len(c) >= 3}
    rel_counts = {}
    for c in (connections or []):
        if len(c) >= 3:
            rel_counts[c[2]] = rel_counts.get(c[2], 0) + 1
    # Which nodes each relation actually touches — the set a relation filter
    # keeps lit. Built from the connections, so it costs nothing extra.
    rel_nodes = {}
    for c in (connections or []):
        if len(c) >= 3:
            rel_nodes.setdefault(c[2], set()).update((c[0], c[1]))

    _warn = warnings if warnings is not None else []
    _all_ids = {n.id for n in nodes}

    def _partitions(touched, what) -> bool:
        """A chip has to divide the set to be worth showing. One that matches
        every node changes nothing when clicked, and one that matches none is
        dead on arrival — both read as a broken control."""
        if not touched:
            _warn.append(f"{what}: matches no nodes — chip dropped")
            return False
        if _all_ids and touched >= _all_ids:
            _warn.append(f"{what}: matches every node, so filtering by it "
                         "changes nothing — chip dropped")
            return False
        return True

    # (key, label, swatch) — the key drives the interactive isolate control.
    rel_key_items = [(r.key, r.label, f"var(--rel-{r.key})") for r in b.relations
                     if b.line_filter
                     and r.key != "spine" and r.color and r.label
                     and r.key in used_rels]
    # The spine joins the key only when there is a colored relation to tell it
    # apart from — a spine-only timeline's neutral thread is self-evident, and a
    # one-row "Lines" legend on it is noise (and would break byte-parity).
    _spine = next((r for r in b.relations if r.key == "spine"), None)
    if rel_key_items and _spine and _spine.label and "spine" in used_rels:
        rel_key_items.append(("spine", _spine.label, "var(--line-flow)"))
    # Now that the chips also filter nodes, the same rule applies to them: a
    # structural spine touches every node in its band, so filtering by it lights
    # everything. Drop those rather than ship a control that does nothing.
    rel_key_items = [it for it in rel_key_items
                     if _partitions(rel_nodes.get(it[0], set()),
                                    f"line filter {it[1]!r}")]

    # Entity filter chips: same rule — an entity on every node, or on none,
    # would be a chip that cannot divide anything.
    ent_filter_items = []
    if b.entity_filter:
        for _e in b.entities:
            _t = {n.id for n in nodes if _e.id in n.entity_ids}
            if _partitions(_t, f"{b.entity_axis_singular.lower()} filter {_e.name!r}"):
                ent_filter_items.append((_e, sorted(_t)))

    # Same rule for the slot filters. A Coverage chip on a deck where every
    # node is Solid, or a custom value the student never assigned, is just as
    # dead as a spine chip — drop it and say why.
    for _rf in resolved_filters:
        _kept = []
        for _vid, _name in _rf["values"]:
            _touched = {nid for nid, v in _rf["node_value"].items() if v == _vid}
            if _partitions(_touched, f"filter {_rf['spec'].label!r} value {_name!r}"):
                _kept.append((_vid, _name))
        _rf["values"] = _kept

    # ── CSS variable blocks ──────────────────────────────────────────────────
    entity_vars = "".join(f"--{e.id}:{e.color};" for e in b.entities)
    entity_vars += f"--accent:{b.accent};"
    # --rel-<key> resolve the connection line colors: the engine's _lineResolveVar
    # reads getComputedStyle('--rel-<key>'); without these the tube stroke gets a
    # literal `var(--rel-…)` and contrast adaptation is skipped. Emitted only for
    # colored non-spine relations, so a relationless brief adds zero bytes.
    entity_vars += "".join(f"--rel-{r.key}:{r.color};" for r in b.relations
                           if r.key != "spine" and r.color)

    def phase_line(alpha):
        return "".join(
            f"--phase{i+1}:rgba({r},{g},{bl},{alpha});"
            for i, (r, g, bl) in enumerate(_rgb(a.color) for a in b.acts[:5]))

    # Bands 6+ land in their own <style> block rather than the :root above, so
    # this covers every remaining act — the count is whatever the brief carries.
    def phase_extra():
        if len(b.acts) <= 5:
            return ""
        light = "".join(f"--phase{i+6}:rgba({r},{g},{bl},0.09);"
                        for i, (r, g, bl) in
                        enumerate(_rgb(a.color) for a in b.acts[5:]))
        dark = "".join(f"--phase{i+6}:rgba({r},{g},{bl},0.07);"
                       for i, (r, g, bl) in
                       enumerate(_rgb(a.color) for a in b.acts[5:]))
        return (f":root{{{light}}}\n"
                f"@media(prefers-color-scheme:dark){{:root{{{dark}}}}}")

    # ── HTML chrome ──────────────────────────────────────────────────────────
    legend_items = "".join(
        f'\n    <div class="legend-item"><div class="legend-dot" '
        f'style="background:var(--{e.id})"></div>{e.name}</div>'
        for e in b.entities)
    axis_dots = ""
    if ax1 and "axis1" not in nav_hidden:
        axis_dots += ('\n    <div class="legend-item"><div class="legend-dot" '
                      'style="background:var(--env-color);border-radius:2px">'
                      f'</div>{ax1.singular}</div>')
    if ax2 and "axis2" not in nav_hidden:
        axis_dots += ('\n    <div class="legend-item"><div class="legend-dot" '
                      f'style="background:var(--theme-color)"></div>{ax2.singular}</div>')
    divider = ('\n    <div style="width:1px;height:14px;background:var(--border);'
               'margin:0 4px"></div>') if axis_dots else ""
    legend = f'<div id="legend">{legend_items}{divider}{axis_dots}\n  </div>'

    def nav_btn(kind, vid, sym, name, extra_cls=""):
        return (f'\n    <button class="nav-btn{extra_cls}" '
                f"onclick=\"showDetail('{kind}','{vid}')\">{sym} {name}</button>")

    nav = [f'<div id="nav">\n    <span class="title">{b.title}</span>']
    if b.entities and "entity" not in nav_hidden:
        nav.append(f'\n    <span class="nav-group-label">{b.entity_axis_singular}</span>')
        for e in b.entities:
            thin = _ent_thin(e.id)
            badge = (f'<span class="nav-chip-count{" thin" if thin else ""}">'
                     f'{ent_count[e.id]}</span>')
            nav.append(
                f'\n    <button class="nav-btn{" chip-thin" if thin else ""}" '
                f"onclick=\"showDetail('char','{e.id}')\">"
                f"{e.symbol_svg or FALLBACK_GLYPH} {e.name}{badge}</button>")
    for ax, src, kind, cls in ((ax1, "axis1", "env", " env-btn"),
                               (ax2, "axis2", "theme", " theme-btn")):
        if not ax or src in nav_hidden:
            continue
        nav.append('\n    <div class="nav-divider"></div>')
        nav.append(f'\n    <span class="nav-group-label">{ax.singular}</span>')
        for v in ax.values:
            nav.append(nav_btn(kind, v.id, v.symbol_svg or FALLBACK_GLYPH, v.name, cls))
    for rf in resolved_filters:
        nav.append('\n    <div class="nav-divider"></div>')
        nav.append(f'\n    <span class="nav-group-label">Filter · {rf["spec"].label}</span>')
        for vid, name in rf["values"]:
            nav.append(f'\n    <button class="nav-btn filter-btn" '
                       f'data-axis="{rf["slot"]}" data-value="{vid}" '
                       f'onclick="filterCanvas(\'{rf["slot"]}\',\'{vid}\')">'
                       f'{name}</button>')
    # Relation filters (desktop). These sit with the other filter groups and
    # read as filter chips, because that is what they now are: clicking one
    # dims the lines of every other relation AND dims the cards that relation
    # never touches, stacking with whatever slot filters are active.
    # Mobile hides #nav .nav-btn entirely, so the drawer carries its own copy.
    if rel_key_items:
        nav.append('\n    <div class="nav-divider"></div>')
        nav.append('\n    <span class="nav-group-label">Filter · Lines</span>')
        for key, label, swatch in rel_key_items:
            nav.append(
                # NOT .filter-btn: the engine sweeps every .filter-btn in
                # _applyActiveFilters (engine :2539) and in clear-all (:7931),
                # keying off data-axis/data-value these chips do not have — so
                # wearing that class made a slot-filter click light a relation
                # chip too. They sit in the filter group and are styled like
                # filter chips; they are not one of the engine's two slots.
                f'\n    <button class="nav-btn line-key-btn" '
                f'data-rel-key="{key}">'
                f'<span style="display:inline-block;width:14px;height:3px;'
                f'border-radius:2px;background:{swatch}"></span>{esc(label)}'
                f'<span class="line-key-count">{rel_counts.get(key, 0)}</span></button>')
    nav.append("\n  </div>")
    nav = "".join(nav)

    overview = (f'<div id="summary-inner">\n{b.overview_html}\n    </div>'
                if b.overview_html else '<div id="summary-inner"></div>')

    # ── JS data consts ───────────────────────────────────────────────────────
    # Keys are quoted because entity ids are slugs and may contain hyphens,
    # which are illegal in bare JS object keys (an unquoted hyphenated key is
    # a SyntaxError that kills the whole engine script block).
    chars = "const CHARS={" + ",".join(
        f"\n  '{e.id}': {{name:{js_str(e.name)}, role:{js_str(e.role)}, "
        f"color:'#{e.color.lstrip('#')}', symbol:{_sym(e.symbol_svg)}}}"
        for e in b.entities) + "\n};"

    char_pages = "const CHAR_PAGES={" + ",".join(
        f"\n  '{e.id}': {{{_sections_js(e.sections)}}}"
        for e in b.entities) + "\n};"

    def axis_registry(name, ax):
        if not ax:
            return f"const {name}={{}};"
        return f"const {name}={{" + ",".join(
            f"\n  '{v.id}': {{name:{js_str(v.name)}, role:{js_str(v.role)}, "
            f"color:{js_str(v.color or '#8888aa')}, symbol:{_sym(v.symbol_svg)}, "
            f"{_sections_js(v.sections)}}}"
            for v in ax.values) + "\n};"

    envs = axis_registry("ENVS", ax1)
    themes = axis_registry("THEMES", ax2)

    def sym_map(name, ax):
        if not ax:
            return f"const {name}={{}};"
        # The engine sets `btn.innerHTML = ENV_SYM[id]` on a flex pill with no
        # width constraint, so this slot takes a label just as happily as a
        # glyph. For a hide_nav axis it must: that axis is the large uncapped
        # kind (a course's cases), where drawing a unique glyph per value is not
        # realistic and every value would fall back to the same ◆ — a row of
        # identical diamonds on a card names nothing. `v.name` is plain_text'd
        # by sanitize before it gets here.
        def cell(v):
            if not ax.hide_nav:
                return _sym(v.symbol_svg)
            return (f"{js_str(v.symbol_svg)}+{js_str(' ' + v.name)}"
                    if v.symbol_svg else js_str(v.name))
        return f"const {name}={{" + ",".join(
            f"'{v.id}':{cell(v)}" for v in ax.values) + "};"

    env_sym = sym_map("ENV_SYM", ax1)
    theme_sym = sym_map("THEME_SYM", ax2)

    node_details = "const NODE_DETAILS={" + ",".join(
        f"\n  '{n.id}':{{{_sections_js(n.sections)}}}"
        for n in nodes if any(s.t for s in n.sections)) + "\n};"

    def node_color(n):
        # Lands inside a single-quoted JS literal, so a free-form value would
        # break out of it; entity ids are already slug-validated.
        if n.color:
            return css_color(n.color, "var(--ensemble)")
        if n.entity_ids and n.entity_ids[0] in ent_by_id:
            return f"var(--{n.entity_ids[0]})"
        return "var(--ensemble)"

    def _filter_fields(n):
        # Scalar filter-slot fields the engine tests in _applyActiveFilters
        # (era / examWeight). Omitted entirely when no filters are defined so
        # filterless briefs emit byte-identically to before.
        parts = ""
        for rf in resolved_filters:
            vid = rf["node_value"].get(n.id)
            if vid is not None:
                parts += f", {rf['node_key']}:'{vid}'"
        return parts

    # A replace_nav'd axis is filter-only: emptying its per-node arrays removes
    # its card/detail chips (which would open empty pages and all share the
    # fallback glyph); the filter still works off the brief via _filter_fields.
    envs_of = (lambda n: []) if "axis1" in nav_replaced \
        else (lambda n: n.axis1_values)
    themes_of = (lambda n: []) if "axis2" in nav_replaced \
        else (lambda n: n.axis2_values)

    nodes_src = "const NODES_SRC=[" + ",".join(
        f"\n  {{id:'{n.id}', baseY:{round(positions[n.id])}, col:'{n.col}', "
        f"tag:{js_str(n.tag)}, title:{js_str(n.title)}, desc:{js_str(n.desc)}, "
        f"chars:{json.dumps(n.entity_ids)}, color:'{node_color(n)}', "
        f"envs:{json.dumps(envs_of(n))}, themes:{json.dumps(themes_of(n))}"
        f"{_filter_fields(n)}}}"
        for n in nodes) + "\n];"

    act_seqs_list = [[] for _ in b.acts]
    for n in nodes:
        act_seqs_list[n.act].append(n.id)
    act_seqs = "const ACT_SEQS = [" + ",".join(
        "\n  " + json.dumps(ids) for ids in act_seqs_list) + "\n];"

    phase_meta = "const PHASE_META = [" + ",".join(
        f"\n  {{label:{js_str(a.label)}, numeral:'{roman(i + 1)}', "
        f"colorRaw:'{a.color}', cssVar:'var(--phase{i+1})'}}"
        for i, a in enumerate(b.acts)) + "\n];"

    node_act = "const NODE_ACT = {" + ",".join(
        f"'{n.id}':{n.act}" for n in nodes) + "};"

    css_hex_entries = [f"'var(--{e.id})':'{e.color}'" for e in b.entities]
    css_hex_entries.append("'var(--ensemble)':'#8888aa'")
    css_hex_entries.append(f"'var(--accent)':'{b.accent}'")
    for r in b.relations:
        if r.color:
            css_hex_entries.append(f"'var(--rel-{r.key})':'{r.color}'")
    css_hex = "const CSS_HEX = {\n  " + ",".join(css_hex_entries) + "\n};"

    col_x = ("const COL_X = {" + ",".join(
        f"'{k}':{v}" for k, v in COL_SETS[b.columns].items()) + "};")

    cmap_entries = ["spine:  'var(--line-flow)'"]
    for r in b.relations:
        if r.key == "spine":
            continue
        ref = f"var(--rel-{r.key})" if r.color else "var(--line-flow)"
        # Quoted because relation keys may contain hyphens, which are legal in
        # a slug but not in a bare JS object key.
        cmap_entries.append(f"'{r.key}': '{ref}'")
    # relations may also reference entity colors by using an entity id as key
    color_map = "const COLOR_MAP = {\n  " + ",\n  ".join(cmap_entries) + ",\n};"

    orders = (
        f"const CHAR_ORDER  = {json.dumps([e.id for e in b.entities])};\n"
        f"const ENV_ORDER   = {json.dumps([v.id for v in ax1.values] if ax1 else [])};\n"
        f"const THEME_ORDER = {json.dumps([v.id for v in ax2.values] if ax2 else [])};")
    if resolved_filters:
        def _label_map(slot):
            rf = next((r for r in resolved_filters if r["slot"] == slot), None)
            if not rf:
                return "{}"
            return "{" + ",".join(f"'{vid}':{js_str(name)}"
                                  for vid, name in rf["values"]) + "}"
        # ERA_LABELS/WEIGHT_LABELS are the free globals the engine's mobile
        # filter bar reads; FILTER_GLUE binds drawer chips + fixes the desktop
        # banner labels.
        orders += ("\nvar ERA_LABELS=" + _label_map("era") + ";"
                   "\nvar WEIGHT_LABELS=" + _label_map("weight") + ";"
                   + FILTER_GLUE)
    # Relation labels (quoted keys — relation keys may be hyphenated) + node noun,
    # consumed by the doctrine-page auto-body (and the interactive line key).
    # Only relations a connection actually uses — an unused relation's label
    # should not leak onto the page.
    rel_labels = ("var REL_LABELS={" + ",".join(
        f"{js_str(r.key)}:{js_str(r.label)}" for r in b.relations
        if r.label and r.key in used_rels) + "};")
    orders += ("\n" + rel_labels
               + f"\nvar _ALTO_NODE_NOUN={js_str(b.node_noun)};"
               + DOCTRINE_BODY + LINES_GLUE
               + (ALTO_LINK_GLUE if uses_alto_link else ""))
    if b.mode == "outline":
        # Outline numerals, derived at build from depth and sibling order — a
        # stored path would be silently invalidated the moment a sibling is
        # inserted. Level styles cycle I. / A. / 1. / a. / i. the way a written
        # outline does.
        _kids: dict[str, list] = {}
        for n in nodes:
            if n.parent:
                _kids.setdefault(n.parent, []).append(n.id)
        _num, _label, _parent = {}, {}, {}
        for n in nodes:
            if n.parent:
                _parent[n.id] = n.parent

        def _mark(level: int, i: int) -> str:
            if level == 0:
                return roman(i + 1) + "."
            if level == 1:
                return chr(ord("A") + i % 26) + "."
            if level == 2:
                return f"{i + 1}."
            if level == 3:
                return chr(ord("a") + i % 26) + "."
            return roman(i + 1).lower() + "."

        def _walk(nid: str, level: int, i: int, prefix: str) -> None:
            mark = _mark(level, i)
            _label[nid] = mark
            _num[nid] = (prefix + mark) if prefix else mark
            for j, kid in enumerate(_kids.get(nid, [])):
                _walk(kid, level + 1, j, _num[nid])

        for _i, _root in enumerate([n.id for n in nodes if not n.parent]):
            _walk(_root, 0, _i, "")
        orders += ("\nwindow._ALTO_OUTLINE={num:" + json.dumps(_num)
                   + ",label:" + json.dumps(_label)
                   + ",kids:" + json.dumps(_kids)
                   + ",parent:" + json.dumps(_parent) + "};"
                   + OUTLINE_BODY + OUTLINE_PRINT_GLUE + CRUMB_GLUE)
    if rel_key_items:
        orders += ("\nvar REL_NODES={" + ",".join(
            f"{js_str(k)}:{json.dumps(sorted(rel_nodes.get(k, set())))}"
            for k, _lbl, _sw in rel_key_items) + "};" + REL_FILTER_GLUE)
    if ent_filter_items:
        def _js_json(v):
            return json.dumps(v, ensure_ascii=False).replace("</", "<\\/")
        orders += (
            "\nvar ENT_LABEL=" + js_str(b.entity_axis_singular) + ";"
            "\nvar ENT_ITEMS=" + _js_json([
                {"id": e.id, "name": e.name, "color": e.color,
                 "symbol": e.symbol_svg or FALLBACK_GLYPH, "count": len(ids)}
                for e, ids in ent_filter_items]) + ";"
            "\nvar ENT_NODES=" + _js_json({e.id: ids for e, ids in ent_filter_items})
            + ";" + ENT_FILTER_GLUE)
    orders_m = (
        f"var CHAR_ORDER_M  = {json.dumps([e.id for e in b.entities])};\n"
        f"  var ENV_ORDER_M   = {json.dumps([v.id for v in ax1.values] if ax1 else [])};\n"
        f"  var THEME_ORDER_M = {json.dumps([v.id for v in ax2.values] if ax2 else [])};")

    id_names = "const _names = {\n      " + ",\n      ".join(
        [f"'{e.id}':{js_str(e.name)}" for e in b.entities]
        + [f"'{v.id}':{js_str(v.name)}" for ax in (ax1, ax2) if ax
           for v in ax.values]) + "\n    };"

    # ── per-entity CSS runs ──────────────────────────────────────────────────
    def tint(e):
        r, g, bl = _rgb(e.color)
        return r, g, bl

    drawer_char_css = "\n".join(
        'html.mobile .drawer-btn[data-char="{id}"] {{ background: rgba({r},{g},{b},0.08); '
        'border-color: rgba({r},{g},{b},0.28); }}'.format(
            id=e.id, r=tint(e)[0], g=tint(e)[1], b=tint(e)[2])
        for e in b.entities)
    nav_char_css = "\n  ".join(
        "button[onclick*=\"'char','{id}'\"]{{color:{c};border-color:rgba({r},{g},{b},.4);}}".format(
            id=e.id, c=e.color, r=tint(e)[0], g=tint(e)[1], b=tint(e)[2])
        for e in b.entities)
    # Glyph-context sizing/spacing. Authored symbol_svg is emitted bare (any
    # root style attr is stripped below): inside flex-centred chips a baked-in
    # margin skews centring, so spacing belongs to each CONTEXT, not the glyph.
    # 1em sizing scales the glyph with every context's own font-size (24px card
    # chips, mobile 30/34px, nav rows, detail headers) instead of a fixed 14px.
    nav_char_css += (
        "\n  .csym-btn svg,.esym-btn svg,.tsym-btn svg,.detail-symbol svg,"
        "#nav .nav-btn svg,.char-chip svg,.drawer-icon svg"
        "{width:1em;height:1em;margin:0;flex-shrink:0;}"
        "\n  #nav .nav-btn svg,.char-chip svg{vertical-align:-2px;margin-right:5px;}")
    # Doctrine/entity detail-page auto-body (member roster + relation rows).
    nav_char_css += (
        "\n  .doc-meta{opacity:.75;font-size:.9em;margin-bottom:8px;}"
        "\n  .doc-thin{color:#d97706;}"
        "\n  .doc-row{cursor:pointer;padding:7px 0;border-bottom:1px solid var(--border);}"
        "\n  .doc-row:hover .doc-row-t{color:var(--accent);}"
        "\n  .doc-row-t{font-weight:600;}"
        "\n  .doc-row-tag{opacity:.6;font-size:.85em;}"
        "\n  .doc-row-d{opacity:.8;font-size:.92em;margin-top:2px;}"
        "\n  .doc-rel{padding:4px 0;}"
        "\n  .doc-rel-dot{display:inline-block;width:12px;height:3px;border-radius:2px;"
        "vertical-align:middle;margin-right:6px;}"
        "\n  .doc-rel-lab{opacity:.6;}")
    # Interactive line-key chips + per-edge hover tooltip.
    nav_char_css += (
        "\n  .line-key-btn{cursor:pointer;}"
        "\n  .line-key-btn.active{border-color:currentColor;"
        "box-shadow:inset 0 0 0 1px currentColor;}"
        "\n  .line-key-count{margin-left:6px;opacity:.5;font-size:.85em;}"
        "\n  html:not(.mobile) #river-svg [data-edge]{pointer-events:stroke;}"
        "\n  .line-tip{position:fixed;z-index:9999;pointer-events:none;display:none;"
        "background:var(--surface);color:var(--text);border:1px solid var(--border);"
        "border-radius:6px;padding:4px 8px;font-size:12px;max-width:280px;"
        "box-shadow:0 4px 16px rgba(0,0,0,.2);}")
    # A named chip (hide_nav axes, above) has to stay inside a 270px card, so
    # cap it and ellipsise rather than letting one long case name reflow the
    # footer. The glyph form is a fixed 14px and needs none of this.
    if any(ax.hide_nav for ax in b.axes[:2]):
        nav_char_css += (
            "\n  .esym-btn,.tsym-btn{max-width:150px;overflow:hidden;"
            "text-overflow:ellipsis;white-space:nowrap;display:inline-block;"
            "line-height:18px;}")
    # A relation-filtered-out card reads exactly like a slot-filtered-out one
    # (the engine's `.node-card.dimmed`, engine :1167-1168) — same treatment,
    # separate class, so the two dim independently and compose.
    if rel_key_items:
        nav_char_css += (
            "\n  .node-card.rel-dimmed{background:var(--surface) !important;"
            "border-top-color:var(--border) !important;}"
            "\n  .node-card.rel-dimmed > *{opacity:0.15;}")
    if ent_filter_items:
        nav_char_css += (
            "\n  .node-card.ent-dimmed{background:var(--surface) !important;"
            "border-top-color:var(--border) !important;}"
            "\n  .node-card.ent-dimmed > *{opacity:0.15;}"
            "\n  #filter-toggle{position:fixed;right:0;top:calc(50% + 84px);z-index:395;"
            "width:34px;height:34px;box-sizing:border-box;padding:0;display:flex;"
            "align-items:center;justify-content:center;cursor:pointer;"
            "background:var(--card-glass-bg, var(--surface));"
            "-webkit-backdrop-filter:blur(18px) saturate(190%);backdrop-filter:blur(18px) saturate(190%);"
            "border:1px solid var(--card-glass-border, var(--border));border-right:none;"
            "border-radius:6px 0 0 6px;color:var(--muted);"
            "box-shadow:0 10px 26px var(--node-rest-shadow);}"
            "\n  #filter-toggle:hover{color:var(--text);border-color:var(--muted);}"
            "\n  #filter-toggle.active{color:var(--accent);border-color:var(--accent);}"
            "\n  #filter-toggle[data-n]:not([data-n=\"\"])::after{content:attr(data-n);"
            "position:absolute;top:-6px;left:-7px;min-width:15px;height:15px;padding:0 3px;"
            "box-sizing:border-box;border-radius:8px;background:var(--accent);color:#fff;"
            "font-size:10px;line-height:15px;text-align:center;}"
            "\n  #ef-panel{position:fixed;right:46px;top:50%;z-index:396;width:272px;"
            "max-height:min(70vh,540px);overflow:auto;padding:12px;border-radius:14px;"
            "opacity:0;pointer-events:none;transform:translateY(calc(-50% + 8px));"
            "transition:opacity .15s, transform .15s;"
            "background:var(--panel-glass-bg, var(--surface));"
            "-webkit-backdrop-filter:blur(30px) saturate(185%);backdrop-filter:blur(30px) saturate(185%);"
            "border:1px solid var(--card-glass-border, var(--border));"
            "box-shadow:0 18px 48px var(--node-hover-shadow);color:var(--text);}"
            "\n  #ef-panel.open{opacity:1;pointer-events:auto;transform:translateY(-50%);}"
            "\n  #ef-panel .ef-head{display:flex;justify-content:space-between;align-items:center;"
            "font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);"
            "margin:0 2px 10px;min-height:20px;}"
            "\n  #ef-clear{font:inherit;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);"
            "background:none;border:0;cursor:pointer;padding:2px 4px;}"
            "\n  #ef-clear[hidden]{display:none;}"
            "\n  #ef-panel .ef-list{display:flex;flex-direction:column;gap:6px;}"
            "\n  .ef-chip{display:flex;align-items:center;gap:9px;width:100%;box-sizing:border-box;"
            "padding:8px 11px;border-radius:10px;cursor:pointer;font:inherit;font-size:13px;"
            "color:var(--text);text-align:left;background:transparent;"
            "border:1.4px solid color-mix(in srgb, var(--c) 50%, transparent);}"
            "\n  .ef-chip:hover{background:color-mix(in srgb, var(--c) 10%, transparent);}"
            "\n  .ef-chip.active{background:color-mix(in srgb, var(--c) 24%, transparent);"
            "border-color:var(--c);}"
            "\n  .ef-sym{display:inline-flex;color:var(--c);font-size:16px;line-height:1;}"
            "\n  .ef-sym svg{width:1em;height:1em;}"
            "\n  .ef-name{flex:1;}"
            "\n  .ef-count{opacity:.5;font-size:.85em;}"
            "\n  html.mobile #filter-toggle, html.mobile #ef-panel{display:none !important;}"
            "\n  html.printing #filter-toggle, html.printing #ef-panel{display:none !important;}"
            "\n  .drawer-btn.ent-filter-btn.active{border-color:var(--accent);"
            "background:color-mix(in srgb, var(--accent) 16%, transparent);}")
    # Outline detail pages: a numbered "Contains" list and an ancestry trail,
    # set to read like a written outline rather than a table.
    if b.mode == "outline":
        nav_char_css += (
            "\n  .ol-row{display:grid;grid-template-columns:2.6em 1fr;"
            "align-items:baseline;column-gap:.4em;margin:.55em 0;}"
            "\n  .ol-num{color:var(--muted);font-variant-numeric:tabular-nums;"
            "letter-spacing:.02em;}"
            # a direct grid child blockifies, which stretched the link's
            # underline across the whole row — shrink it back to its text
            "\n  .ol-name{font-weight:600;justify-self:start;}"
            "\n  .ol-d{grid-column:2;color:var(--muted);font-size:.92em;"
            "line-height:1.5;margin-top:.15em;}"
            "\n  .ol-trail{color:var(--muted);line-height:1.9;}"
            "\n  .ol-sep{opacity:.5;padding:0 .15em;}"
            # Paper. Indentation carries the nesting, the numeral column keeps
            # the numbers aligned down the page, and a heading never sits alone
            # at the foot of a page away from what it contains.
            "\n  @media print{"
            "\n    .print-ol-doc{font-family:'Georgia',serif;font-size:10.5pt;"
            "line-height:1.4;}"
            "\n    .print-ol-unit{margin:0 0 1.4em;break-inside:auto;}"
            "\n    .print-ol-h{font-size:12pt;letter-spacing:.08em;"
            "text-transform:uppercase;border-bottom:1px solid #9a9a9a;"
            "padding-bottom:.25em;margin:0 0 .7em;break-after:avoid;}"
            "\n    .print-ol-row{display:flex;gap:.5em;align-items:baseline;"
            "margin:.28em 0;padding-left:calc(var(--lvl) * 1.6em);"
            "break-inside:avoid;}"
            "\n    .print-ol-num{flex:0 0 2.2em;text-align:right;"
            "font-variant-numeric:tabular-nums;}"
            "\n    .print-ol-body{flex:1 1 auto;min-width:0;}"
            "\n    .print-ol-name{font-weight:700;}"
            "\n    .print-ol-desc{margin-top:.1em;}"
            "\n    .print-ol-cite{margin-top:.1em;font-style:italic;}"
            "\n    .print-ol-row + .print-ol-row{break-before:auto;}"
            "\n  }")
    # Deep links in detail-page text. Styled after the overview's .ov-node-link
    # resting/hover chip so a link reads the same wherever it appears — but it
    # carries its own accent underline, since a detail page has no per-character
    # colour to borrow.
    if uses_alto_link:
        # Tighter than .ov-node-link's chip padding: these sit mid-sentence, so
        # a 3px gutter reads as a space before the following comma.
        nav_char_css += (
            "\n  .alto-link{display:inline;cursor:pointer;border-radius:3px;"
            "padding:0 1px;border:1px solid transparent;"
            "box-shadow:inset 0 -1px 0 color-mix(in srgb, var(--accent) 55%, transparent);"
            "transition:border-color .15s, background .15s;}"
            "\n  .alto-link:hover{"
            "border-color:color-mix(in srgb, var(--accent) 55%, transparent);"
            "background:color-mix(in srgb, var(--accent) 12%, transparent);}")
    # Gap-radar badges on the doctrine nav/drawer chips.
    nav_char_css += (
        "\n  .nav-chip-count{margin-left:5px;font-size:.8em;opacity:.45;}"
        "\n  .nav-chip-count.thin{color:#d97706;opacity:.9;font-weight:600;}"
        "\n  #nav .nav-btn.chip-thin{border-color:rgba(217,119,6,.5);}")
    nav_char_css_mix = "\n".join(
        "html:not(.mobile):not(.dark) button[onclick*=\"'char','{id}'\"]{{ "
        "color:color-mix(in srgb, var(--{id}) 50%, var(--text)); "
        "border-color:color-mix(in srgb, var(--{id}) 55%, var(--text)); }}".format(id=e.id)
        for e in b.entities)

    # ── drawer filter buttons (mobile nav drawer) ────────────────────────────
    def drawer_btn(kind, vid, sym, name, cls="", data_char=""):
        dc = f' data-char="{data_char}"' if data_char else ""
        return (f"'    <button class=\"drawer-btn{cls}\" data-sd-type=\"{kind}\" "
                f"data-sd-id=\"{vid}\"{dc}><span class=\"drawer-icon\">"
                + (sym or FALLBACK_GLYPH).replace("'", "\\'")
                + f"</span><span class=\"drawer-label\">{name}</span></button>',")

    drawer = []
    if b.entities and "entity" not in nav_hidden:
        drawer.append(f"'    <div class=\"drawer-section-label\">{b.entity_axis_label}</div>',")
        for e in b.entities:
            thin = _ent_thin(e.id)
            nm = (e.name + f'<span class="nav-chip-count{" thin" if thin else ""}">'
                  f'{ent_count[e.id]}</span>')
            drawer.append(drawer_btn("char", e.id, e.symbol_svg, nm, data_char=e.id))
    for ax, src, kind, cls in ((ax1, "axis1", "env", " env-btn"),
                               (ax2, "axis2", "theme", " theme-btn")):
        if not ax or src in nav_hidden:
            continue
        drawer.append(f"'    <div class=\"drawer-section-label\">{ax.label}</div>',")
        for v in ax.values:
            drawer.append(drawer_btn(kind, v.id, v.symbol_svg, v.name, cls))
    # Filter chips: data-sd-axis/-id (NOT data-sd-type, which would make the
    # engine's drawer handler navigate). Engine CSS already styles
    # .drawer-btn.filter-btn[data-sd-axis]; clicks are bound by FILTER_GLUE.
    # Text-only on purpose: filter values carry no authored glyphs, and a row
    # of identical fallback diamonds reads as meaning it doesn't have.
    for rf in resolved_filters:
        drawer.append(f"'    <div class=\"drawer-section-label\">Filter &middot; {rf['spec'].label}</div>',")
        for vid, name in rf["values"]:
            drawer.append(
                f"'    <button class=\"drawer-btn filter-btn\" "
                f"data-sd-axis=\"{rf['slot']}\" data-sd-id=\"{vid}\">"
                f"<span class=\"drawer-label\">{name}</span></button>',")
    # Entity filter (mobile): the desktop panel is hidden on a phone, so the
    # drawer carries the same chips. data-ent-key, not data-sd-*, so the
    # engine's drawer handler leaves them to ENT_FILTER_GLUE.
    if ent_filter_items:
        drawer.append(f"'    <div class=\"drawer-section-label\">Filter &middot; "
                      f"{esc(b.entity_axis_singular)}</div>',")
        for e, _ids in ent_filter_items:
            drawer.append(
                "'    <button class=\"drawer-btn ent-filter-btn\" data-ent-key=\""
                + e.id + "\"><span class=\"drawer-icon\">"
                + (e.symbol_svg or FALLBACK_GLYPH).replace("'", "\\'")
                + "</span><span class=\"drawer-label\">" + esc(e.name)
                + f"<span class=\"line-key-count\">{len(_ids)}</span>"
                + "</span></button>',")
    # Relation line key (mobile): data-rel-key (NOT data-sd-*, so the engine
    # drawer handler + FILTER_GLUE ignore them); the LINES_GLUE delegated handler
    # binds .line-key-btn to isolate that relation's lines.
    if rel_key_items:
        drawer.append("'    <div class=\"drawer-section-label\">Lines</div>',")
        for key, label, swatch in rel_key_items:
            drawer.append(
                "'    <button class=\"drawer-btn line-key-btn\" data-rel-key=\""
                + key + "\"><span class=\"drawer-icon\"><span style=\"display:"
                "inline-block;width:16px;height:3px;border-radius:2px;background:"
                + swatch + "\"></span></span><span class=\"drawer-label\">"
                + esc(label) + "<span class=\"line-key-count\">"
                + str(rel_counts.get(key, 0)) + "</span></span></button>',")
    drawer_filters = "\n".join(drawer)

    # ── mobile grid ──────────────────────────────────────────────────────────
    mobile_grid_js = "var MOBILE_GRID = {" + ",".join(
        f"\n    '{nid}':{json.dumps(mgrid[nid])}" for nid in mgrid) + "\n  };"
    mobile_world = (f"var MOBILE_STEP={MOBILE_STEP}, MOBILE_OX={MOBILE_OX}, "
                    f"MOBILE_OY={MOBILE_OY}, MOBILE_WORLD_W={MOBILE_WORLD_W}, "
                    f"MOBILE_WORLD_H={mobile_world_h};")

    regions = {
        "entity_css_vars": entity_vars,
        "phase_css_vars_light": phase_line("0.09"),
        "phase_css_vars_dark": phase_line("0.07"),
        "phase_css_vars_extra": phase_extra(),
        "legend": legend,
        "nav": nav,
        "overview": overview,
        "chars": chars,
        "char_pages": char_pages,
        "env_sym": env_sym,
        "theme_sym": theme_sym,
        "id_names": id_names,
        "drawer_char_css": drawer_char_css,
        "nav_char_css": nav_char_css,
        "nav_char_css_mix": nav_char_css_mix,
        "envs": envs,
        "themes": themes,
        "node_details": node_details,
        "nodes_src": nodes_src,
        "act_seqs": act_seqs,
        "phase_meta": phase_meta,
        "node_act": node_act,
        "css_hex": css_hex,
        "col_x": col_x,
        "color_map": color_map,
        "connections": None,   # filled below
        "orders": orders,
        "drawer_filters": drawer_filters,
        "orders_m": orders_m,
        "mobile_grid": mobile_grid_js,
        "mobile_world": mobile_world,
        "node_sections": (NODE_SECTIONS_OUTLINE_D if b.mode == "outline"
                          else NODE_SECTIONS_D),
        "char_sections": CHAR_SECTIONS_D,
        "env_sections": ENV_SECTIONS_D,
        "theme_sections": THEME_SECTIONS_D,
        "node_sections_m": (NODE_SECTIONS_OUTLINE_M if b.mode == "outline"
                            else NODE_SECTIONS_M),
        "char_sections_m": CHAR_SECTIONS_M,
        "env_sections_m": ENV_SECTIONS_M,
        "theme_sections_m": THEME_SECTIONS_M,
    }

    # ── tokens ───────────────────────────────────────────────────────────────
    act_names_lit = ("[" + ",".join(js_str(a.short) for a in b.acts) + "]")
    sec_names = [s.h for n in nodes for s in n.sections[:3] if s.t][:3]
    sec_hint = ", ".join(dict.fromkeys(sec_names)) or "its full details"
    # Tag-free title for the sinks that display a string rather than parse it.
    title_txt = one_line(b.title)
    owner_mail = b.owner_email or "user@example.com"
    rhref = reports_href or f"reports.html?course={tid}&amp;from=project"

    tokens = {
        "page_title": f"{b.title} — Alto Timeline",
        "title_text": f'<span id="title-text">{b.title}</span>',
        # href attribute: percent-encode, or a quote in the title closes it.
        "mailto_href": (f"mailto:{url_q(one_line(owner_mail), safe='@')}"
                        f"?subject={url_q(title_txt)}%20Notes%20Report&body="),
        "report_title": f"{b.title} — Notes Report",
        "report_h1": f"<h1>{b.title}</h1>",
        "report_footer": ("Generated from highlights and notes in the "
                          f"{b.title} study timeline."),
        "reports_link": rhref,
        "course_id_lit": ID_PATTERNS["course_id_lit"].format(tid=tid),
        "drawer_title": f"'    <span id=\"nav-drawer-title\">{b.title}</span>',",
        "doc_save_key": ID_PATTERNS["doc_save_key"].format(tid=tid),
        "hl_key": ID_PATTERNS["hl_key"].format(tid=tid),
        "hl_key_legacy": ID_PATTERNS["hl_key"].format(tid=tid) + "-legacy",
        "rp_key": ID_PATTERNS["rp_key"].format(tid=tid),
        "sim_name": b.owner_name or "Alto User",
        "sim_email": owner_mail,
        "course_id_var": ID_PATTERNS["course_id_var"].format(tid=tid),
        "badge_event_d": f'<div class="detail-badge ${{badgeClass}}">{b.node_noun}</div>',
        "badge_event_m": f'<div class="detail-badge badge-node">{b.node_noun}</div>',
        "badge_char_m": f'<div class="detail-badge badge-char">{b.entity_axis_singular}</div>',
        "badge_env_m": ('<div class="detail-badge badge-env">'
                        f'{(ax1.singular if ax1 else "Group")}</div>'),
        "badge_theme_m": ('<div class="detail-badge badge-theme">'
                          f'{(ax2.singular if ax2 else "Group")}</div>'),
        "type_labels": ("const typeLabel=type==='char'?"
                        f"{js_str(b.entity_axis_singular)}:type==='env'?"
                        f"{js_str(ax1.singular if ax1 else 'Group')}:"
                        f"{js_str(ax2.singular if ax2 else 'Group')};"),
        "chips_heading": f"<h3>{b.entity_axis_label} Present</h3>",
        "help_sections_m": ("Tap the current card to open its detail page "
                            f"&#8212; {sec_hint}."),
        "help_sections_d": ("click any card to open its detail page "
                            f"({sec_hint})"),
        # An outline printed as an outline should not be headed "Timeline".
        "print_title": (
            f'<h1 class="print-tl-title">{b.title} — '
            f'{"Outline" if b.mode == "outline" else "Timeline"}</h1>'),
        # navigator.share() displays this as text, so it gets the tag-free
        # title — and it is a JS literal, so js_str() rather than interpolation.
        "share_title": f"title:{js_str(title_txt + ' Timeline')}",
        "share_import": f"Someone shared their {b.title} timeline with you",
        "act_names": act_names_lit,
    }
    return regions, tokens


def connections_block(connections: list) -> str:
    return "const CONNECTIONS = [" + ",".join(
        f"\n  {json.dumps(c)}" for c in connections) + "\n];"
