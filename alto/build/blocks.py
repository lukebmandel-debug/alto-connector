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

from .brief import Brief, Node, Section, COL_SETS, roman
from .numbering import NUM_JS, path_numbers
from .filter_panel import FILTER_PANEL_GLUE, RAIL_CSS, RAIL_GLUE, filter_panel_css
from .mobile_chrome import MSEARCH_PANEL_CSS, MSEARCH_PANEL_GLUE

# "How they connect": a node's steps to the nodes after it, and a sub-chip's steps
# through the nodes it is named in. Authored text uses the same markup, whose
# links the sanitizer turns into .alto-link spans.
HOW_CONNECT_CSS = (
    "\n  .hc-row{padding:9px 0;border-bottom:1px solid var(--border);line-height:1.6;}"
    "\n  .hc-row:last-child{border-bottom:0;}"
    "\n  .hc-link{cursor:pointer;font-weight:600;border-radius:3px;"
    "box-shadow:inset 0 -1px 0 color-mix(in srgb, var(--accent) 55%, transparent);}"
    "\n  .hc-link:hover{background:color-mix(in srgb, var(--accent) 12%, transparent);}"
    "\n  .hc-arrow{opacity:.5;margin:0 8px;}"
    "\n  .hc-num{opacity:.5;font-size:.85em;margin-right:6px;}"
    "\n  .hc-how{opacity:.88;font-size:.94em;margin-top:3px;}"
    "\n  .alto-lead{display:block;font-size:1.06em;line-height:1.6;}"
    "\n  .alto-lead-num{opacity:.55;font-size:.8em;font-weight:600;margin-right:8px;"
    "font-variant-numeric:tabular-nums;}")
from .sanitize import css_color, esc, js_json, one_line
from . import detail_extras as dx
from .layout import MOBILE_STEP, MOBILE_OX, MOBILE_OY, MOBILE_WORLD_W, TREE, outline_plan, plan_js, sized_placement

# Generic section-builder code (same shape as the template's empty defaults —
# kept in one place because emit() replaces the whole region span).
NODE_SECTIONS_D = (
    "sections = _altoCardLead(id).concat(((nd.sections)||[]).filter(s=>s&&s.t));\n"
    "    if(sections.length === 0) sections.push({h:'Synopsis', t: n.desc});\n"
    "    sections = sections.concat(_altoNodeConnect(id));")
CHAR_SECTIONS_D = ("sections=(p.sections||[]).filter(s=>s&&s.t);"
                   " sections=_altoOrder(sections.concat(_altoDoctrineBody(id,'char',sections)));")
ENV_SECTIONS_D = ("sections=(e.sections||[]).filter(s=>s&&s.t);"
                  " sections=_altoOrder(sections.concat(_altoDoctrineBody(id,'env',sections)));")
THEME_SECTIONS_D = ("sections=(th.sections||[]).filter(s=>s&&s.t);"
                    " sections=_altoOrder(sections.concat(_altoDoctrineBody(id,'theme',sections)));")
NODE_SECTIONS_M = (
    "var sections=_altoCardLead(targetId).concat(((ndDet.sections)||[]).filter(function(s){return s&&s.t;}));\n"
    "          if(sections.length===0) sections.push({h:'Synopsis',t:nd.desc||''});\n"
    "          sections=sections.concat(_altoNodeConnect(targetId));")
CHAR_SECTIONS_M = ("var chSecs=(cp.sections||[]).filter(function(s){return s&&s.t;});"
                   " chSecs=_altoOrder(chSecs.concat(_altoDoctrineBody(targetId,'char',chSecs)));")
ENV_SECTIONS_M = ("var enSecs=(en.sections||[]).filter(function(s){return s&&s.t;});"
                  " enSecs=_altoOrder(enSecs.concat(_altoDoctrineBody(targetId,'env',enSecs)));")
THEME_SECTIONS_M = ("var thSecs=(th.sections||[]).filter(function(s){return s&&s.t;});"
                    " thSecs=_altoOrder(thSecs.concat(_altoDoctrineBody(targetId,'theme',thSecs)));")

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
    # `<` (</script>) and the line/paragraph separators are written as \u
    # escapes, which a JS literal reads back as the same character.
    for ch, esc_ in (("<", "\\u003c"), ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        out = out.replace(ch, esc_)
    return "'" + out + "'"


def jsq(s) -> str:
    """The inside of js_str(), for text spliced into a quoted JS literal that a
    template already opened (the engine builds HTML in '…' and `…` strings).
    Also safe inside a template literal: a backtick or `${` is written as a unicode
    escape, which '…', "…" and `…` all read back as the same characters."""
    out = js_str("" if s is None else str(s))[1:-1]
    return out.replace("`", "\\u0060").replace("$", "\\u0024")


def _rgb(hexcolor: str):
    h = hexcolor.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _sections_js(sections, indent="    ") -> str:
    items = ",".join(
        f"{{h:{js_str(dx.prov_heading(s))},t:{js_str(s.t)}}}"
        for s in (sections or []) if s.t)
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
# The card's number and summary line, as the lead section of its detail page
# (brief.card_on_detail): the page must never show less than the card did.
# Escaped here because the card renders desc as text, the page as HTML.
CARD_LEAD_BODY = """
function _altoCardLead(id){
  if(!window._ALTO_CARD_LEAD || typeof NODES_SRC==='undefined') return [];
  var n=null; for(var i=0;i<NODES_SRC.length;i++){ if(NODES_SRC[i].id===id){ n=NODES_SRC[i]; break; } }
  if(!n || !n.desc) return [];
  var e=function(t){ return String(t).replace(/[&<>"]/g,function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); };
  var num=(typeof NODE_ORDER_MAP!=='undefined' && NODE_ORDER_MAP[id]) || '';
  return [{h:'Summary', t:'<span class="alto-lead">'+(num?'<span class="alto-lead-num">'+e(num)+'</span>':'')+e(n.desc)+'</span>'}];
}
"""
DOCTRINE_BODY = """
function _altoMembers(id, kind){
  var f = kind==='env' ? 'envs' : (kind==='theme' ? 'themes' : 'chars');
  var by={}; NODES_SRC.forEach(function(n){ by[n.id]=n; });
  var order=(typeof NODE_ORDER!=='undefined')?NODE_ORDER:NODES_SRC.map(function(n){ return n.id; });
  return order.map(function(i){ return by[i]; }).filter(function(n){ return n && (n[f]||[]).indexOf(id)!==-1; });
}
// The reason a line between two nodes exists, if its author gave one — either way round.
function _altoHow(a, b){
  if(typeof CONNECTIONS==='undefined') return '';
  for(var i=0;i<CONNECTIONS.length;i++){
    var c=CONNECTIONS[i];
    if(c[3] && ((c[0]===a&&c[1]===b)||(c[0]===b&&c[1]===a))) return c[3];
  }
  return '';
}
// The list of nodes reads before the steps between them, whichever of the two the
// author wrote.
function _altoOrder(secs){
  var nn=(typeof _ALTO_NODE_NOUN!=='undefined' && _ALTO_NODE_NOUN) || 'Case';
  var ev=(nn+(/s$/i.test(nn)?'':'s')).toLowerCase(), hc=-1, ei=-1;
  secs.forEach(function(s,i){ var k=String(s.h||'').trim().toLowerCase(); if(k==='how they connect') hc=i; if(k===ev) ei=i; });
  if(hc>=0 && ei>hc){ var e=secs.splice(ei,1)[0]; secs.splice(hc,0,e); }
  return secs;
}
function _altoHave(have, h){
  var k=String(h).toLowerCase();
  return (have||[]).some(function(s){ return s && String(s.h||'').trim().toLowerCase()===k; });
}
// A page for a sub-chip (character, environment, theme, doctrine…): every node
// it is named in, then how those nodes connect. Authored sections of the same
// name win; this fills in what is missing from the material's own text and the
// lines' own explanations, and never invents any.
function _altoDoctrineBody(id, kind, have){
  if(typeof NODES_SRC==='undefined') return [];
  kind = kind || 'char';
  var outline = !!window._ALTO_OUTLINE;
  if(outline && kind!=='char') return [];
  var members = _altoMembers(id, kind);
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
    + (kind==='char' && thin?' &middot; <strong class="doc-thin">THIN &mdash; sparse in your notes</strong>':'')
    + '</div>';
  var rows = members.map(function(n){
    return '<div class="doc-row" data-goto="'+n.id+'">'
      + '<span class="doc-row-t">'+(n.title||'')+'</span>'
      + (n.tag?' <span class="doc-row-tag">'+n.tag+'</span>':'')
      + (n.desc?'<div class="doc-row-d">'+n.desc+'</div>':'')
      + '</div>';
  }).join('');
  var heading = nn + (/s$/i.test(nn)?'':'s');
  var out=[];
  if(!_altoHave(have, heading)) out.push({h: heading,
    t: (outline && typeof _altoElementTree==='function') ? _altoElementTree(members) : meta+rows});
  if(_altoHave(have, 'How they connect')) return out;
  if(outline){
    // A concept outline: the labelled cross-links among these concepts. The
    // spokes are the tree the list above already shows, so a line with no
    // label of its own ("related") adds nothing and is left out.
    if(typeof CONNECTIONS!=='undefined'){
      var rl=(typeof REL_LABELS!=='undefined')?REL_LABELS:{};
      var internal=CONNECTIONS.filter(function(c){ return memberSet[c[0]]&&memberSet[c[1]]&&c[2]!=='spine'&&rl[c[2]]; });
      if(internal.length){
        out.push({h:'How they connect', t: internal.map(function(c){
          var col=(typeof COLOR_MAP!=='undefined'&&COLOR_MAP[c[2]])||'var(--line-flow)';
          return '<div class="doc-rel"><span class="doc-rel-dot" style="background:'+col+'"></span>'
            +'<a class="hc-link" data-goto="'+c[0]+'">'+(titleOf[c[0]]||c[0])+'</a> <span class="doc-rel-lab">'+rl[c[2]]
            +' &rarr;</span> <a class="hc-link" data-goto="'+c[1]+'">'+(titleOf[c[1]]||c[1])+'</a></div>';
        }).join('')});
      }
    }
    return out;
  }
  // Story order: each node this chip is named in, and its step to the next one.
  if(members.length>1){
    var steps=[];
    for(var i=0;i<members.length-1;i++){
      var a=members[i], b=members[i+1], how=_altoHow(a.id,b.id);
      steps.push('<div class="hc-row"><a class="hc-link" data-goto="'+a.id+'">'+(a.title||'')+'</a>'
        +'<span class="hc-arrow">&rarr;</span>'
        +'<a class="hc-link" data-goto="'+b.id+'">'+(b.title||'')+'</a>'
        +(how?'<div class="hc-how">'+how+'</div>':'')+'</div>');
    }
    out.push({h:'How they connect', t: steps.join('')});
  }
  return out;
}
// A node's own "How they connect": the nodes after it that a line leads to,
// each linked, each with the reason the line was drawn when there is one.
function _altoNodeConnect(id){
  if(window._ALTO_OUTLINE) return [];          // an outline lists what a concept contains instead
  if(typeof CONNECTIONS==='undefined' || typeof NODE_ORDER==='undefined') return [];
  var pos=NODE_ORDER.indexOf(id), titleOf={};
  NODES_SRC.forEach(function(n){ titleOf[n.id]=n.title; });
  var kids=CONNECTIONS.filter(function(c){ return c[0]===id && NODE_ORDER.indexOf(c[1])>pos; });
  if(!kids.length) return [];
  return [{h:'How they connect', t: kids.map(function(c){
    return '<div class="hc-row"><a class="hc-link" data-goto="'+c[1]+'">'+(titleOf[c[1]]||c[1])+'</a>'
      +(c[3]?'<div class="hc-how">'+c[3]+'</div>':'')+'</div>';
  }).join('')}];
}
// The sub-chips a node carries beyond its entities, as sections of their own.
function _altoAxisChips(n, clickable){
  var out='';
  [['envs','env','ENVS'],['themes','theme','THEMES']].forEach(function(k){
    var reg=(typeof window[k[2]]!=='undefined')?window[k[2]]:(k[2]==='ENVS'?ENVS:THEMES);
    var ids=n[k[0]]||[], h='';
    ids.forEach(function(cid){
      var v=reg&&reg[cid]; if(!v) return;
      var col=(!v.color||v.color==='#8888aa')?(k[1]==='env'?'var(--env-color)':'var(--theme-color)'):v.color;
      h+='<span class="char-chip" style="color:'+col+';border-color:color-mix(in srgb, '+col+' 30%, transparent);background:color-mix(in srgb, '+col+' 8%, transparent);"'
        +(clickable?' onclick="showDetail(\\''+k[1]+'\\',\\''+cid+'\\')"':'')+'>'+v.symbol+' '+v.name+'</span>';
    });
    if(h) out+='<div class="detail-section"><h3>'+_ALTO_CHIP_HEADINGS[k[0]]+'</h3><div class="char-chips">'+h+'</div></div>';
  });
  return out;
}
(function(){
  if(window._altoDocRowBound) return; window._altoDocRowBound=1;
  document.addEventListener('click', function(e){
    var r = e.target && e.target.closest && e.target.closest('.doc-row[data-goto], .hc-link[data-goto]');
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
  // Shown only once the pointer RESTS on a line (LINE_NAV_GLUE's dwell), not
  // as it passes over one on the way somewhere else.
  document.addEventListener('alto:edge-dwell', function(e){
    var info=edgeInfo(e.detail.key); if(!info) return;
    if(!tip){ tip=document.createElement('div'); tip.className='line-tip'; document.body.appendChild(tip); }
    tip.textContent=info; tip.style.display='block';
    tip.style.left=(e.detail.x+12)+'px'; tip.style.top=(e.detail.y+14)+'px';
  });
  document.addEventListener('mousemove', function(e){
    if(tip && tip.style.display==='block'){ tip.style.left=(e.clientX+12)+'px'; tip.style.top=(e.clientY+14)+'px'; }
  });
  document.addEventListener('alto:edge-leave', function(){ if(tip) tip.style.display='none'; });
})();"""



# Following a line (desktop). Clicking a connecting line flies to the node at
# its far end — the end farther from where you clicked, so a line reads as
# "go there" from either side — and enlarges it (the engine's own focus). Moving
# onto a line fades every other card and line a little, so the two cards it
# joins stand out; the existing .line-tip label still names the relation.
# Both wait for intent: the pointer has to rest on the line (DWELL ms without
# moving more than a few px), so sweeping across the map never flickers the
# page. While faded, the other lines are cut wherever a faded card covers
# them, so a faded line never shows through a faded (translucent) card.
# The engine's drawing is left alone: after each redraw, every path belonging
# to an edge (tube, frosted sheen, two-colour flags) is tagged with its key, and
# a wide transparent hit path is laid over each tube so a 5px line is easy to
# catch. The hit path carries data-edge-hit, not data-edge, which the engine's
# audit sampler and the relation filter count. Mobile is untouched.
LINE_NAV_GLUE = """
(function(){
  if(window._altoLineNav) return; window._altoLineNav=1;
  var de=document.documentElement;
  function desktop(){ return !de.classList.contains('mobile'); }
  function tag(){
    var svg=document.getElementById('river-svg'); if(!svg) return;
    [].forEach.call(svg.querySelectorAll('[data-edge-hit]'),function(h){ h.parentNode.removeChild(h); });
    var key=null, hits=[];
    [].forEach.call(svg.children,function(el){
      if(el.hasAttribute('data-edge')){ key=el.getAttribute('data-edge'); hits.push(el); }
      else if(key && el.tagName.toLowerCase()==='path') el.setAttribute('data-edge-part',key);
    });
    if(!desktop()) return;
    fadeSoon();                     // a redraw drew every line whole again
    hits.forEach(function(t){
      var h=document.createElementNS('http://www.w3.org/2000/svg','path');
      h.setAttribute('d',t.getAttribute('d')); h.setAttribute('fill','none');
      h.setAttribute('stroke','transparent'); h.setAttribute('stroke-width','14');
      h.setAttribute('stroke-linecap','round'); h.setAttribute('stroke-linejoin','round');
      h.setAttribute('data-edge-hit',t.getAttribute('data-edge'));
      svg.appendChild(h);
    });
  }
  var _rc=window.redrawConnections;
  if(typeof _rc==='function') window.redrawConnections=function(){
    var r=_rc.apply(this,arguments); try{ tag(); }catch(e){} return r; };
  function edgeOf(t){ return t && t.closest && t.closest('#river-svg [data-edge-hit],#river-svg [data-edge]'); }
  function keyOf(p){ return p.getAttribute('data-edge-hit')||p.getAttribute('data-edge'); }
  var hot=null;
  /* Faded cards are translucent, so a line behind one would show through it.
     While anything is faded — a card enlarged (every other card fades), cards
     dimmed by a filter, a line singled out on hover — each faded line is
     redrawn with the stretches under faded cards left out, and put back as it
     was when nothing is faded. Plain paths with gaps: every browser draws them
     the same, at no cost. (An SVG <mask> on each line made Safari re-render it
     every frame of a fly, slower further down the page; a clipPath, and a mask
     on the outer <svg>, Safari does not reliably apply.) A card at full
     strength — the enlarged one, a hovered line's two ends, the cards a filter
     keeps — does not hide lines, just as at rest. */
  function dimmed(c){
    return c.classList.contains('dimmed')||c.classList.contains('rel-dimmed')||c.classList.contains('ent-dimmed');
  }
  function fadeOn(){
    var cv=document.getElementById('canvas');
    return !!cv && (cv.classList.contains('focus-mode') ||
      !!document.querySelector('#world .node-card.dimmed,#world .node-card[class~="rel-dimmed"],#world .node-card[class~="ent-dimmed"]'));
  }
  /* The faded cards' boxes, in the line layer's own units — which are the
     world's layout px: the engine draws every line from node positions in
     those px. So the boxes come from layout too (offsetLeft/Top/Width/Height
     under #world), never from screen coordinates run back through
     getScreenCTM: under the page's CSS zoom Safari maps those differently
     from other engines, which put the cuts beside the cards (1.8.30-33). */
  /* A card's box is always its RESTING box. A card on the move — the one an
     arrow hop just left, gliding home at 1.7x on its fly transform; the one
     leaving focus; a hovered card mid-ramp — is measured where it will land,
     not where it is this frame: otherwise its cuts were wrong for the whole
     glide and fixed only by a second redraw once it landed (1.8.35-36: lines
     'late to the party' on every hop). The anchor (offsetLeft less the
     centring margin) never moves; the card's size and offset from the anchor
     are remembered from whenever it was last at rest. */
  function atRest(n,c){
    return !n.classList.contains('focused') && !n._hovOn && !n._rel &&
      !c.style.zoom && !(n.style.transform && n.style.transform!=='none') &&
      !n.style.getPropertyValue('--fx') && !n.style.getPropertyValue('--fy');
  }
  function restBox(n,c){
    /* the anchor from the node's own left/top (offsetLeft/Top round, and the
       rounding differs with and without the centring margin) */
    var ax=parseFloat(n.style.left), ay=parseFloat(n.style.top);
    if(isNaN(ax)||isNaN(ay)){ var cs=getComputedStyle(n); ax=n.offsetLeft-(parseFloat(cs.marginLeft)||0); ay=n.offsetTop-(parseFloat(cs.marginTop)||0); }
    if(atRest(n,c) && c.offsetWidth)
      n._rb={dx:n.offsetLeft+c.offsetLeft-ax, dy:n.offsetTop+c.offsetTop-ay, w:c.offsetWidth, h:c.offsetHeight};
    var b=n._rb; if(!b) return null;
    return {x0:ax+b.dx, y0:ay+b.dy, x1:ax+b.dx+b.w, y1:ay+b.dy+b.h};
  }
  function holes(svg,faded){
    var R=[];
    [].forEach.call(document.querySelectorAll('#world .node'),function(n){
      var c=n.querySelector('.node-card'); if(!c) return;
      var b=restBox(n,c); if(b && faded(c)) R.push(b);
    });
    return R;
  }
  function inside(x,y,R){
    for(var i=0;i<R.length;i++){ var r=R[i]; if(x>r.x0&&x<r.x1&&y>r.y0&&y<r.y1) return true; }
    return false;
  }
  /* The engine draws lines with absolute M / L / Q only. piecesD(d, keep, B)
     keeps the parts of a line where keep(x,y) holds: a straight stretch is
     split at every edge of the boxes in B (Liang–Barsky) and each piece kept
     or dropped by its midpoint; a corner curve (a 20px quarter turn) is kept
     or dropped whole. */
  function piecesD(d,keep,B){
    var tk=d.match(/[MLQ]|-?\d*\.?\d+(?:e-?\d+)?/gi)||[], i=0, out='', px=0, py=0, pen=false, lastT=0;
    function num(){ return parseFloat(tk[i++]); }
    function f(v){ return Math.round(v*100)/100; }
    while(i<tk.length){
      var c=tk[i++];
      if(c==='M'){ px=num(); py=num(); pen=false; }
      else if(c==='L'){
        var x=num(), y=num(), dx=x-px, dy=y-py, ts=[0,1];
        B.forEach(function(r){
          var t0=0, t1=1, P=[-dx,dx,-dy,dy], Q=[px-r.x0,r.x1-px,py-r.y0,r.y1-py], ok=true;
          for(var k=0;k<4;k++){
            if(P[k]===0){ if(Q[k]<=0){ ok=false; break; } }
            else { var t=Q[k]/P[k]; if(P[k]<0){ if(t>t0) t0=t; } else { if(t<t1) t1=t; } }
          }
          if(ok && t0<t1){ ts.push(t0); ts.push(t1); }
        });
        ts.sort(function(a,b){ return a-b; });
        for(var j=0;j<ts.length-1;j++){
          var a=ts[j], b=ts[j+1]; if(b-a<1e-6) continue;
          var m=(a+b)/2;
          if(keep(px+dx*m,py+dy*m)){
            if(!(pen && a===lastT)) out+='M'+f(px+dx*a)+' '+f(py+dy*a);
            out+='L'+f(px+dx*b)+' '+f(py+dy*b); pen=true; lastT=b;
          } else pen=false;
        }
        pen=pen && lastT===1; px=x; py=y; lastT=0;
      }
      else if(c==='Q'){
        var cx=num(), cy=num(), x2=num(), y2=num(), all=true;
        [0.25,0.5,0.75].forEach(function(t){
          var u=1-t; if(!keep(u*u*px+2*u*t*cx+t*t*x2, u*u*py+2*u*t*cy+t*t*y2)) all=false;
        });
        if(all){ if(!pen) out+='M'+f(px)+' '+f(py); out+='Q'+f(cx)+' '+f(cy)+' '+f(x2)+' '+f(y2); pen=true; }
        else pen=false;
        px=x2; py=y2; lastT=0;
      }
      else return null;                    // anything else: leave the line whole
    }
    return out || 'M0 0';
  }
  function keyOfPath(e){ return e.getAttribute('data-edge')||e.getAttribute('data-edge-part'); }
  function bboxOf(d){
    var v=(d.match(/-?\d*\.?\d+(?:e-?\d+)?/gi)||[]).map(parseFloat), b={x0:1e9,y0:1e9,x1:-1e9,y1:-1e9};
    for(var i=0;i+1<v.length;i+=2){ if(v[i]<b.x0)b.x0=v[i]; if(v[i]>b.x1)b.x1=v[i]; if(v[i+1]<b.y0)b.y0=v[i+1]; if(v[i+1]>b.y1)b.y1=v[i+1]; }
    return b;
  }
  function touching(R,bb){
    return R.filter(function(r){ return r.x0<bb.x1+1 && r.x1>bb.x0-1 && r.y0<bb.y1+1 && r.y1>bb.y0-1; });
  }
  function sameR(a,b){
    if(a.length!==b.length) return false;
    for(var i=0;i<a.length;i++) if(a[i].x0!==b[i].x0||a[i].y0!==b[i].y0||a[i].x1!==b[i].x1||a[i].y1!==b[i].y1) return false;
    return true;
  }
  /* Applied the instant the faded set changes (a hover starts or ends, a card
     is enlarged or left, a hop, a filter) — never debounced or faded on its
     own. The line layer and each line already fade with the cards; a piece
     put back or taken away at that same instant rides that fade and arrives
     with the rest of its line. (A separate fade for the pieces trailed the
     line, 1.8.35; waiting for the fly to settle made them late, 1.8.34.) */
  function syncCuts(){
    if(!desktop()) return;
    var svg=document.getElementById('river-svg'), cv=document.getElementById('canvas'); if(!svg||!cv) return;
    var focus=cv.classList.contains('focus-mode'), fade=fadeOn(), R=[];
    /* measured even when nothing is faded, so every card's resting box is
       known before its first enlarge or hop */
    R=holes(svg,function(c){
      if(!(fade||hot)) return false;
      var n=c.closest('.node');
      if(focus) return !n.classList.contains('focused');
      if(hot) return !n.classList.contains('edge-end');
      return dimmed(c);
    });
    [].forEach.call(svg.querySelectorAll('path:not([data-edge-hit])'),function(e){
      if(e.closest('defs')) return;
      var d0=e.getAttribute('data-d0'), src=d0===null?e.getAttribute('d'):d0;
      if(e._bbd!==src){ e._bbd=src; e._bb=bboxOf(src); }
      var newR=((fade||hot) && !(hot && keyOfPath(e)===hot)) ? touching(R,e._bb) : [];
      if(sameR(e._R||[],newR)) return;      // nothing changes for this line
      if(!newR.length){ e._R=[]; if(d0!==null){ e.setAttribute('d',d0); e.removeAttribute('data-d0'); } return; }
      if(d0===null){ d0=e.getAttribute('d'); e.setAttribute('data-d0',d0); }
      var cut=piecesD(d0,function(x,y){ return !inside(x,y,newR); },newR);
      e._R=newR; e.setAttribute('d',cut===null?d0:cut);
    });
  }
  var fadeT=null;
  function fadeSoon(){ clearTimeout(fadeT); fadeT=setTimeout(syncCuts,120); }
  window._altoSyncFade=syncCuts;
  (function watch(){
    var cv=document.getElementById('canvas'), w=document.getElementById('world');
    if(!cv||!w||typeof MutationObserver!=='function'){ document.addEventListener('DOMContentLoaded',watch); return; }
    /* a state change (enlarge, hop, filter) is applied on the same frame the
       cards start to fade; only layout changes wait for things to settle */
    new MutationObserver(function(){ clearTimeout(fadeT); syncCuts(); })
      .observe(cv,{attributes:true,attributeFilter:['class']});
    new MutationObserver(function(ms){
      var cls=false, sty=false;
      ms.forEach(function(m){ if(m.target.closest && m.target.closest('#river-svg')) return;
        if(m.attributeName==='class') cls=true; else sty=true; });
      if(!(fadeOn() || document.querySelector('#river-svg [data-d0]'))) return;
      if(cls){ clearTimeout(fadeT); syncCuts(); } else if(sty) fadeSoon();
    }).observe(w,{attributes:true,subtree:true,attributeFilter:['class','style']});
  })();
  function clear(){
    if(!hot) return; hot=null;
    var cv=document.getElementById('canvas'); if(cv) cv.classList.remove('edge-hover');
    [].forEach.call(document.querySelectorAll('.edge-end,.edge-hot'),function(e){ e.classList.remove('edge-end'); e.classList.remove('edge-hot'); });
    syncCuts();
    document.dispatchEvent(new CustomEvent('alto:edge-leave'));
  }
  function light(key,x,y){
    if(hot===key) return; clear();
    var cv=document.getElementById('canvas'), svg=document.getElementById('river-svg');
    if(!cv || !svg || cv.classList.contains('focus-mode')) return;
    hot=key; var ends=key.split('|');
    ends.forEach(function(id){ var n=document.getElementById('node-'+id); if(n) n.classList.add('edge-end'); });
    [].forEach.call(svg.querySelectorAll('[data-edge],[data-edge-part]'),function(e){
      if(keyOfPath(e)===key) e.classList.add('edge-hot'); });
    syncCuts();
    cv.classList.add('edge-hover');
    document.dispatchEvent(new CustomEvent('alto:edge-dwell',{detail:{key:key,x:x,y:y}}));
  }
  /* intent: the pointer must rest on a line, not just cross it */
  var DWELL=300, SLOP=6, arm=null, ax=0, ay=0, akey=null;
  function disarm(){ clearTimeout(arm); arm=null; akey=null; }
  function rearm(key,x,y){
    clearTimeout(arm); akey=key; ax=x; ay=y;
    arm=setTimeout(function(){ arm=null; if(akey) light(akey,ax,ay); },DWELL);
  }
  /* a line the canvas slides under a still pointer is not one it rests on */
  function still(e){ return !!(window._altoPointerStill && window._altoPointerStill(e)); }
  document.addEventListener('mouseover',function(e){
    if(!desktop()) return; var p=edgeOf(e.target);
    if(p){ if(hot!==keyOf(p) && !still(e)) rearm(keyOf(p),e.clientX,e.clientY); }
    else if(!(e.target.closest && e.target.closest('#river-svg'))){ disarm(); clear(); }
  });
  document.addEventListener('mousemove',function(e){
    var p=edgeOf(e.target);
    if(!akey){ if(p && desktop() && hot!==keyOf(p) && !still(e)) rearm(keyOf(p),e.clientX,e.clientY); return; }
    if(hot===akey) return;
    if(!p || keyOf(p)!==akey){ disarm(); return; }
    if(Math.abs(e.clientX-ax)>SLOP || Math.abs(e.clientY-ay)>SLOP) rearm(akey,e.clientX,e.clientY);
  });
  document.addEventListener('mouseout',function(e){
    if(!edgeOf(e.target) || edgeOf(e.relatedTarget)) return;
    disarm(); clear();
  });
  document.addEventListener('click',function(e){
    if(!desktop()) return; var p=edgeOf(e.target); if(!p) return;
    var ends=keyOf(p).split('|'), best=null, bd=-1;
    ends.forEach(function(id){
      var c=document.querySelector('#node-'+id+' .node-card'); if(!c) return;
      var r=c.getBoundingClientRect(), dx=r.left+r.width/2-e.clientX, dy=r.top+r.height/2-e.clientY, dd=dx*dx+dy*dy;
      if(dd>bd){ bd=dd; best=id; }
    });
    if(!best || typeof window.enterFocus!=='function') return;
    e.preventDefault(); e.stopPropagation(); disarm(); clear();
    window.enterFocus(best);
  }, true);
  if(document.readyState!=='loading') tag(); else document.addEventListener('DOMContentLoaded',tag);
})();"""


# Mobile unit label. The phone shows one card at a time, with nothing around
# it to say which unit (act, era — whatever this timeline calls its bands) the
# card belongs to. Every card gets that band's label hung just above it, in
# the band's colour: small and quiet, outside the card so it never competes
# with the card's own text or chips. It replaced an outline-only "under
# {parent}" crumb in the card footer, which read as one more chip.
# If a very tall card on a short screen would put the label against the top
# toggles (Search, MAP, MENU, the filter bar), it moves inside the card's top
# edge instead. Desktop and print are untouched.
UNIT_GLUE = """
(function(){
  var ACTS = (typeof PHASE_META !== 'undefined') ? PHASE_META : [];
  var OF = (typeof NODE_ACT !== 'undefined') ? NODE_ACT : {};
  if(!ACTS.length) return;
  function inject(){
    if(!document.getElementById('alto-unit-css')){
      var st = document.createElement('style');
      st.id = 'alto-unit-css';
      st.textContent = '.node-unit{display:none;}' +
        'html.mobile .node-unit{display:block;position:absolute;left:12px;right:12px;' +
        'bottom:calc(100% + 7px);text-align:center;pointer-events:none;' +
        'font:600 10px/1.2 -apple-system,BlinkMacSystemFont,sans-serif;' +
        'letter-spacing:.2em;text-transform:uppercase;opacity:.9;' +
        'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}' +
        'html.mobile .node-unit.in-card{position:static;text-align:left;margin:0 0 6px;opacity:.8;}' +
        'html.printing .node-unit{display:none !important;}';
      document.head.appendChild(st);
    }
    var nodes = document.querySelectorAll('#world .node');
    for(var i = 0; i < nodes.length; i++){
      var el = nodes[i];
      if(el.querySelector('.node-unit')) continue;
      var a = ACTS[OF[el.id.slice(5)]];
      if(!a) continue;
      var u = document.createElement('div');
      u.className = 'node-unit';
      u.textContent = a.label;
      u.style.color = a.colorRaw;
      u.setAttribute('aria-hidden', 'true');
      el.insertBefore(u, el.firstChild);
    }
  }
  function clear(){
    var el = document.querySelector('.node.mobile-featured');
    var u = el && el.querySelector('.node-unit');
    if(!u || !document.documentElement.classList.contains('mobile')) return;
    if(u.classList.contains('in-card')){
      u.classList.remove('in-card'); el.insertBefore(u, el.firstChild);
    }
    var top = u.getBoundingClientRect().top, lim = 0;
    ['m-search','minimap-toggle','hamburger-tab','mobile-filter-bar'].forEach(function(id){
      var t = document.getElementById(id);
      if(!t || getComputedStyle(t).display === 'none') return;
      var r = t.getBoundingClientRect();
      if(r.height && r.bottom > lim) lim = r.bottom;
    });
    var card = el.querySelector('.node-card');
    if(card && top < lim + 4){ u.classList.add('in-card'); card.insertBefore(u, card.firstChild); }
  }
  /* The cards the glue first sees are the pre-rendered ones; engine init
     rebuilds them once, sweeping early injections away. So: keep re-injecting
     (idempotent) through the init window, and again after every featureNode —
     the same seam the template uses for its own post-nav patches. */
  var tries = 0;
  (function go(){ inject(); clear(); if(++tries < 80) setTimeout(go, 250); })();
  (function hook(){
    var fn = window.featureNode;
    if(typeof fn === 'function' && !fn._altoUnits){
      var w = function(){ var r = fn.apply(this, arguments);
        try{ inject(); setTimeout(clear, 360); }catch(_){} return r; };
      w._altoUnits = true;
      window.featureNode = w;
      return;
    }
    if(!(fn && fn._altoUnits)) setTimeout(hook, 250);
  })();
  window.addEventListener('resize', function(){ setTimeout(clear, 200); });
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
    "sections = _altoCardLead(id).concat(_altoOutlineHead(id))"
    ".concat(((nd.sections)||[]).filter(s=>s&&s.t))"
    ".concat(_altoOutlineTail(id));\n"
    "    if(sections.length === 0) sections.push({h:'Synopsis', t: n.desc});")
NODE_SECTIONS_OUTLINE_M = (
    "var sections=_altoCardLead(targetId).concat(_altoOutlineHead(targetId))"
    ".concat(((ndDet.sections)||[]).filter(function(s){return s&&s.t;}))"
    ".concat(_altoOutlineTail(targetId));\n"
    "          if(sections.length===0) sections.push({h:'Synopsis',t:nd.desc||''});")


def _sym(svg: str) -> str:
    return js_str(svg) if svg else js_str(FALLBACK_GLYPH)


def timeline_blocks(b: Brief, nodes: list[Node], positions, heights,
                    mgrid, mobile_world_h: int, *, reports_href: str = None,
                    view_path: str = "", connections: list = None,
                    warnings: list = None, tree: bool = False) -> tuple[dict, dict]:
    """Return (regions, tokens) for emit() against timeline_template.html.

    nodes must be validated, in narrative order, with col set and positions
    resolved. mgrid: id -> [colIndex, row]. connections (optional) drives the
    relation "line key" — only relations actually used by a connection appear.
    """
    tid = b.timeline_id
    # An outline drawn as a tree: the page runs this plan over its measured
    # card heights, and narrows the cards the plan gives less than a full width.
    tree_plan = outline_plan(nodes, len(b.acts), sized_placement(b), b.tree_lines, b.outcomes) if tree else None
    ax1 = b.axes[0] if len(b.axes) > 0 else None
    ax2 = b.axes[1] if len(b.axes) > 1 else None
    _warn0 = warnings if warnings is not None else []
    # A hide_nav axis is too big for the nav row, so it gets an index page and
    # a nav entry for it instead (ALTO-006).
    index_axes = [(k, ax) for k, ax in (("env", ax1), ("theme", ax2))
                  if ax and ax.hide_nav]
    index_entries = dx.index_entries(index_axes)
    # Pages that get the detail-navigation extras (back-to-previous, banner
    # clearance, auto-linking). See detail_extras' docstring for why not all.
    rich_detail = b.mode == "outline" or bool(index_axes)
    # Build-time sections: citation (axis values) and source notes.
    _docs = {d["id"]: d for d in b.source_docs}
    _by_id = {n.id: n for n in nodes}

    def _node_sources(n):
        seen, cur = set(), n
        while cur is not None and cur.id not in seen:
            if cur.sources or b.mode != "outline":
                return cur.sources
            seen.add(cur.id)
            cur = _by_id.get(cur.parent)
        return []

    def _extra(obj, ax=None):
        """The page's own sections framed by what the build knows about it:
        its citation first (ALTO-013), its source notes last (ALTO-011)."""
        head = []
        if ax is not None and getattr(obj, "cite", None):
            c = dx.cite_html(ax, obj, False)
            if c:
                head.append(Section(h=dx.cite_heading(ax), t=c))
        ids = _node_sources(obj) if isinstance(obj, Node) else obj.sources
        src = dx.source_section(ids, _docs)
        return head + list(obj.sections) + ([src] if src else [])
    uses_note_links = False
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
    b._alto_navrep = set(nav_replaced)            # manual edit mode: chips cards show
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
        # Auto-linking (detail_extras.AUTOLINK, on every page) makes
        # .alto-link spans at runtime out of this table, too.
        from .detail_extras import autolink_table
        t = autolink_table(b)
        if t["names"] or t["sec"]:
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
        if not _kept and _rf["spec"].source == "coverage":
            # The notes are uniformly full (or uniformly thin): coverage
            # cannot divide them. Say what would, so the slot is not wasted.
            alt = ("'depth' (Level 1/2/3+ from the outline's own structure)"
                   if b.mode == "outline" or any(n.parent for n in nodes)
                   else "a custom dimension the material marks")
            _warn.append(f"filter {_rf['spec'].label!r}: coverage does not "
                         f"divide these notes, so the filter is empty — use "
                         f"{alt} for this slot instead")

    # ── the Filter panel: one section per kind of filter ─────────────────────
    # Every kind of sub-chip a card carries is filterable — those chips have
    # detail pages of their own — so each gets a section, unless an explicit
    # filter already mirrors that axis. A chip still has to divide the set.
    filter_sections, filter_nodes = [], {}
    _covered = {rf["spec"].source for rf in resolved_filters}
    if b.chip_filters:
        _dims = []
        if b.entities:
            _dims.append(("entity", b.entity_axis_singular, "entity_ids", [
                (e.id, e.name, e.color, e.symbol_svg or FALLBACK_GLYPH) for e in b.entities]))
        for _ax, _key, _attr, _dflt in ((ax1, "axis1", "axis1_values", "var(--env-color)"),
                                        (ax2, "axis2", "axis2_values", "var(--theme-color)")):
            # Opt-in for an axis with an index page (ALTO-006).
            if _ax and (_ax.filter if _ax.filter is not None else not _ax.hide_nav):
                _dims.append((_key, _ax.singular, _attr, [
                    (v.id, v.name, v.color or _dflt, v.symbol_svg) for v in _ax.values]))
        for _key, _label, _attr, _vals in _dims:
            if _key in _covered:
                continue
            _items, _map = [], {}
            for _vid, _name, _color, _symbol in _vals:
                _t = {n.id for n in nodes if _vid in getattr(n, _attr)}
                if _partitions(_t, f"{_label.lower()} filter {_name!r}"):
                    _items.append({"id": _vid, "name": _name, "color": _color,
                                   "symbol": _symbol, "count": len(_t)})
                    _map[_vid] = sorted(_t)
            if _items:
                filter_sections.append({"key": _key, "kind": "chips",
                                        "label": _label, "items": _items})
                filter_nodes[_key] = _map
    # The user's own flags (pivotal, revisit…): one chip each, and a card shows
    # under EVERY flag it carries. Not a canvas slot — those hold one value per
    # node — so it is a panel section like the sub-chip ones, any-of within it.
    if b.flags:
        _fitems, _fmap = [], {}
        for _fl in b.flags:
            _t = {n.id for n in nodes if _fl["id"] in n.flags}
            if not _t:
                _warn.append(f"flag {_fl['name']!r}: no node carries it, so it "
                             "is left out of the Filter")
                continue
            _fitems.append({"id": _fl["id"], "name": _fl["name"],
                            "color": _fl.get("color") or "var(--accent)",
                            "count": len(_t)})
            _fmap[_fl["id"]] = sorted(_t)
        if _fitems:
            filter_sections.append({"key": "flags", "kind": "chips",
                                    "label": "Flags", "items": _fitems})
            filter_nodes["flags"] = _fmap
    for rf in resolved_filters:
        filter_sections.append({
            "key": "slot-" + rf["slot"], "kind": "slot", "slot": rf["slot"],
            "label": rf["spec"].label,
            "items": [{"id": vid, "name": name} for vid, name in rf["values"]]})
    if rel_key_items:
        filter_sections.append({
            "key": "lines", "kind": "lines", "label": "Lines",
            "items": [{"id": k, "name": lbl, "swatch": sw, "count": rel_counts.get(k, 0)}
                      for k, lbl, sw in rel_key_items]})
    # Filters the owner took out (manual edit mode, Brief.filters_off): left out
    # of the panel. The whole set goes to the edit layer (manual_edit), which
    # lets the owner put one back.
    _slot_ids = {"slot-" + rf["slot"]: "filter:" + rf["spec"].id for rf in resolved_filters}
    b._alto_filters = {"sections": filter_sections, "nodes": filter_nodes, "slot": _slot_ids}
    if b.filters_off:
        _off = set(b.filters_off)
        _kept = []
        for _s in filter_sections:
            _k = _slot_ids.get(_s["key"], _s["key"])
            if _k in _off:
                continue
            _its = [it for it in _s["items"] if f"{_k}:{it['id']}" not in _off]
            if _its:
                _kept.append({**_s, "items": _its})
        filter_sections = _kept
        filter_nodes = {k: v for k, v in filter_nodes.items()
                        if any(s_["key"] == k for s_ in filter_sections)}

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
    if index_axes:
        nav.append('\n    <span class="nav-divider"></span>'
                   f'\n    <span class="nav-group-label">{b.index_label}</span>')
        for key, kind, label, ids in index_entries:
            glyph = "&#9670;" if kind == "env" else "&#167;"
            nav.append(
                f'\n    <button class="nav-btn {kind}-btn" data-axis-index="{key}" '
                f"onclick=\"showAxisIndex('{key}')\">{glyph} {label}"
                f'<span class="nav-chip-count">{len(ids)}</span></button>')
    nav.append("\n  </div>")
    nav = "".join(nav)

    overview_html = b.overview_html
    if not overview_html:
        if b.mode == "outline":
            overview_html = dx.outline_overview(b, nodes)
            _bare = [(x.short or x.label) for i, x in enumerate(b.acts)
                     if not (x.summary or "").strip()
                     and any(n.act == i and not n.parent for n in nodes)]
            if _bare:
                _warn0.append("no overview summary for " + ", ".join(_bare)
                              + " — the Overview composes one from the hub's "
                              "description and its concepts' names; "
                              "set_overview(section_summaries) to write a real one")
        else:
            _warn0.append("no overview authored — the Overview (\u2605) opens blank; "
                          "set_overview to write one")
    overview = (f'<div id="summary-inner">\n{overview_html}\n    </div>'
                if overview_html else '<div id="summary-inner"></div>')

    # ── JS data consts ───────────────────────────────────────────────────────
    # Keys are quoted because entity ids are slugs and may contain hyphens,
    # which are illegal in bare JS object keys (an unquoted hyphenated key is
    # a SyntaxError that kills the whole engine script block).
    chars = "const CHARS={" + ",".join(
        f"\n  '{e.id}': {{name:{js_str(e.name)}, role:{js_str(e.role)}, "
        f"color:'#{e.color.lstrip('#')}', symbol:{_sym(e.symbol_svg)}}}"
        for e in b.entities) + "\n};"

    # Manual edit mode (manual_edit.py) needs to know, for each section the
    # page carries, which of the object's own sections it is (-1: one the
    # build adds — a citation, Source notes). Read by builder._add_tail.
    # -1: a section the build puts ahead of the object's own (a citation);
    # -2: one it puts after them (Source notes).
    def _edk(obj, secs):
        out, seen = [], False
        for s in secs:
            if not s.t:
                continue
            j = next((j for j, o in enumerate(obj.sections) if o is s), None)
            if j is None:
                out.append(-2 if seen else -1)
            else:
                seen = True
                out.append(j)
        return out
    b._alto_edk = {
        "n": {n.id: _edk(n, _extra(n)) for n in nodes},
        "c": {e.id: _edk(e, _extra(e)) for e in b.entities},
        "env": {v.id: _edk(v, _extra(v, ax1)) for v in (ax1.values if ax1 else [])},
        "theme": {v.id: _edk(v, _extra(v, ax2)) for v in (ax2.values if ax2 else [])},
    }

    char_pages = "const CHAR_PAGES={" + ",".join(
        f"\n  '{e.id}': {{{_sections_js(_extra(e))}}}"
        for e in b.entities) + "\n};"

    def axis_registry(name, ax):
        if not ax:
            return f"const {name}={{}};"
        return f"const {name}={{" + ",".join(
            f"\n  '{v.id}': {{name:{js_str(v.name)}, role:{js_str(v.role)}, "
            f"color:{js_str(v.color or '#8888aa')}, symbol:{_sym(v.symbol_svg)}, "
            f"{_sections_js(_extra(v, ax))}}}"
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

    _nsecs = {n.id: _extra(n) for n in nodes}
    node_details = "const NODE_DETAILS={" + ",".join(
        f"\n  '{n.id}':{{{_sections_js(_nsecs[n.id])}}}"
        for n in nodes if any(s.t for s in _nsecs[n.id])) + "\n};"
    uses_note_links = 'class="note-link"' in (char_pages + envs + themes + node_details)

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
               + "\nvar _ALTO_CHIP_HEADINGS={envs:" + js_str(ax1.label if ax1 else "Environments")
               + ",themes:" + js_str(ax2.label if ax2 else "Themes") + "};"
               + f"\nwindow._ALTO_CARD_LEAD={'true' if b.card_on_detail else 'false'};"
               + CARD_LEAD_BODY + DOCTRINE_BODY + LINES_GLUE + LINE_NAV_GLUE
               + (ALTO_LINK_GLUE if uses_alto_link else ""))
    if b.mode == "outline":
        # Outline numbers, derived at build from the tree — a stored path
        # would be silently invalidated the moment a sibling is inserted. A
        # unit's top card is the unit's number; under it a, b, c, then .1,
        # .1, -1, then letters again (numbering.py). The full path is both the
        # card's number and its label, so every list shows whose child it is.
        _kids: dict[str, list] = {}
        for n in nodes:
            if n.parent:
                _kids.setdefault(n.parent, []).append(n.id)
        _parent = {n.id: n.parent for n in nodes if n.parent}
        _num = path_numbers([[n.id for n in nodes if n.act == a] for a in range(len(b.acts))],
                            _kids, _parent)
        _label = dict(_num)
        orders += ("\nwindow._ALTO_OUTLINE={num:" + json.dumps(_num)
                   + ",label:" + js_json(_label)
                   + ",kids:" + json.dumps(_kids)
                   + ",parent:" + json.dumps(_parent) + "};"
                   + NUM_JS + OUTLINE_BODY + OUTLINE_PRINT_GLUE
                   + dx.NODE_NAME_GLUE + dx.ELEMENT_TREE
                   + (dx.tree_glue(plan_js(tree_plan)) if tree else dx.HUBS_ABOVE_GLUE))
    if index_axes:
        orders += dx.AXIS_INDEX_GLUE + dx.axes_config(b, index_axes)
    if rel_key_items:
        orders += ("\nvar REL_NODES={" + ",".join(
            f"{js_str(k)}:{json.dumps(sorted(rel_nodes.get(k, set())))}"
            for k, _lbl, _sw in rel_key_items) + "};" + REL_FILTER_GLUE)
    orders += "\n" + RAIL_GLUE + "\n" + MSEARCH_PANEL_GLUE + UNIT_GLUE
    # Always there, empty or not: manual edit mode can add the first filter.
    # With no sections the panel draws no tab.
    orders += ("\nvar FILTER_SECTIONS=" + js_json(filter_sections) + ";"
               "\nvar FILTER_NODES=" + js_json(filter_nodes) + ";"
               + FILTER_PANEL_GLUE)
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
        "\n  html:not(.mobile) #river-svg [data-edge-hit]{pointer-events:stroke;cursor:pointer;}"
        "\n  html:not(.mobile) #river-svg [data-edge],html:not(.mobile) #river-svg [data-edge-part]{transition:opacity .18s;}"
        "\n  html:not(.mobile) #canvas.edge-hover #river-svg [data-edge]:not(.edge-hot),"
        "html:not(.mobile) #canvas.edge-hover #river-svg [data-edge-part]:not(.edge-hot){opacity:.15 !important;}"
        "\n  html:not(.mobile) #canvas.edge-hover .node:not(.edge-end) .node-card{opacity:.35 !important;}"
        "\n  .line-tip{position:fixed;z-index:9999;pointer-events:none;display:none;"
        "background:var(--surface);color:var(--text);border:1px solid var(--border);"
        "border-radius:6px;padding:4px 8px;font-size:12px;max-width:280px;"
        "box-shadow:0 4px 16px rgba(0,0,0,.2);}")
    # An outline's flanking outcome cards are narrower on desktop, so a tree
    # row (flank | concept | flank, twice) fits the 1700px world (layout.TREE);
    # so are the cards of a placed row of three or more.
    if tree:
        _narrow: dict[int, list] = {}
        for _i, _w in tree_plan["w"].items():
            if _w != TREE["CARD_W"]:
                _narrow.setdefault(_w, []).append(_i)
        if _narrow:
            nav_char_css += "".join(
                "\n  " + ",".join(f"html:not(.mobile) #node-{i} .node-card"
                                  for i in sorted(ids))
                + f"{{width:{_w:g}px;}}" for _w, ids in sorted(_narrow.items()))
            _fl = sorted(i for ids in _narrow.values() for i in ids)
            nav_char_css += ("\n  " + ",".join(
                f"html:not(.mobile) #node-{i} .esym-btn,"
                f"html:not(.mobile) #node-{i} .tsym-btn" for i in _fl)
                + "{max-width:100%;}")
    # A card sized by its owner (brief.card_size): its width, and the least
    # height it takes. After the tree's widths above, so it wins.
    _ids = {n.id for n in nodes}
    for _i, _sz in sorted((b.card_size or {}).items()):
        if _i in _ids and isinstance(_sz, dict):
            _d = ((f"width:{_sz['w']:g}px;" if _sz.get("w") else "")
                  + (f"min-height:{_sz['h']:g}px;" if _sz.get("h") else ""))
            if _d:
                nav_char_css += f"\n  html:not(.mobile) #node-{_i} .node-card{{{_d}}}"
    # A named chip (hide_nav axes, above) has to stay inside its card, so cap it
    # at the footer's own width and ellipsise past that. It takes as much of the
    # row as its name needs: a name that fits shows whole and needs no hover
    # label. The glyph form is a fixed 14px and needs none of this.
    if any(ax.hide_nav for ax in b.axes[:2]):
        nav_char_css += (
            "\n  .esym-btn,.tsym-btn{max-width:100%;overflow:hidden;"
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
    nav_char_css += RAIL_CSS + MSEARCH_PANEL_CSS + HOW_CONNECT_CSS
    if b.mode == "outline":
        nav_char_css += dx.ELEMENT_TREE_CSS
    if uses_note_links or index_axes:
        nav_char_css += dx.NOTE_LINK_CSS
    if any(s.prov for g in ([n.sections for n in nodes] + [e.sections for e in b.entities]
                            + [v.sections for ax in b.axes for v in ax.values])
           for s in g):
        nav_char_css += dx.PROV_CSS
    # Always: manual edit mode can draw the panel for a timeline's first filter.
    nav_char_css += filter_panel_css()
    # Outline detail pages: a numbered "Contains" list and an ancestry trail,
    # set to read like a written outline rather than a table.
    if b.mode == "outline":
        nav_char_css += (
            "\n  .ol-row{display:grid;grid-template-columns:minmax(2.6em,max-content) 1fr;"
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
            "\n    .print-ol-num{flex:0 0 auto;min-width:2.2em;text-align:right;"
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
        drawer.append(f"'    <div class=\"drawer-section-label\">{jsq(b.entity_axis_label)}</div>',")
        for e in b.entities:
            thin = _ent_thin(e.id)
            nm = (jsq(e.name) + f'<span class="nav-chip-count{" thin" if thin else ""}">'
                  f'{ent_count[e.id]}</span>')
            drawer.append(drawer_btn("char", e.id, e.symbol_svg, nm, data_char=e.id))
    for ax, src, kind, cls in ((ax1, "axis1", "env", " env-btn"),
                               (ax2, "axis2", "theme", " theme-btn")):
        if not ax or src in nav_hidden:
            continue
        drawer.append(f"'    <div class=\"drawer-section-label\">{jsq(ax.label)}</div>',")
        for v in ax.values:
            drawer.append(drawer_btn(kind, v.id, v.symbol_svg, jsq(v.name), cls))
    if index_axes:
        drawer.append(f"'    <div class=\"drawer-section-label\">{js_str(b.index_label)[1:-1]}</div>',")
        for key, kind, label, ids in index_entries:
            glyph = "&#9670;" if kind == "env" else "&#167;"
            drawer.append(
                f"'    <button class=\"drawer-btn {kind}-btn\" "
                f"onclick=\"showAxisIndex(\\'{key}\\');closeNavDrawer()\">"
                f"<span class=\"drawer-icon\">{glyph}</span>"
                f"<span class=\"drawer-label\">{js_str(label)[1:-1]}</span></button>',")
    # Filters are not in the drawer: the Filter tile (bottom-left) opens them.
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
        "report_title": f"{jsq(b.title)} — Notes Report",
        "report_h1": f"<h1>{jsq(b.title)}</h1>",
        "report_footer": ("Generated from highlights and notes in the "
                          f"{jsq(b.title)} study timeline."),
        "reports_link": rhref,
        "course_id_lit": ID_PATTERNS["course_id_lit"].format(tid=tid),
        "drawer_title": f"'    <span id=\"nav-drawer-title\">{jsq(b.title)}</span>',",
        "doc_save_key": ID_PATTERNS["doc_save_key"].format(tid=tid),
        "hl_key": ID_PATTERNS["hl_key"].format(tid=tid),
        "hl_key_legacy": ID_PATTERNS["hl_key"].format(tid=tid) + "-legacy",
        "rp_key": ID_PATTERNS["rp_key"].format(tid=tid),
        "sim_name": jsq(b.owner_name or "Alto User"),
        "sim_email": jsq(owner_mail),
        "course_id_var": ID_PATTERNS["course_id_var"].format(tid=tid),
        # An outline names each node's kind by its own tag (Concept, Outcome…)
        # rather than one noun for all (ALTO-004).
        "badge_event_d": (f'<div class="detail-badge ${{badgeClass}}">'
                          + (f"${{n.tag||{js_str(b.node_noun)}}}" if b.mode == "outline"
                             else jsq(b.node_noun)) + '</div>'),
        "badge_event_m": ('<div class="detail-badge badge-node">'
                          + (f"'+(nd.tag||{js_str(b.node_noun)})+'" if b.mode == "outline"
                             else jsq(b.node_noun)) + '</div>'),
        "badge_char_m": f'<div class="detail-badge badge-char">{jsq(b.entity_axis_singular)}</div>',
        "badge_env_m": ('<div class="detail-badge badge-env">'
                        f'{jsq(ax1.singular if ax1 else "Group")}</div>'),
        "badge_theme_m": ('<div class="detail-badge badge-theme">'
                          f'{jsq(ax2.singular if ax2 else "Group")}</div>'),
        "type_labels": ("const typeLabel=type==='char'?"
                        f"{js_str(b.entity_axis_singular)}:type==='env'?"
                        f"{js_str(ax1.singular if ax1 else 'Group')}:"
                        f"{js_str(ax2.singular if ax2 else 'Group')};"),
        "chips_heading": f"<h3>{jsq(b.entity_axis_label)} Present</h3>",
        "help_sections_m": ("Tap the current card to open its detail page "
                            f"&#8212; {jsq(sec_hint)}."),
        "help_sections_d": ("click any card to open its detail page "
                            f"({sec_hint})"),
        # An outline printed as an outline should not be headed "Timeline".
        "print_title": (
            f'<h1 class="print-tl-title">{jsq(b.title)} — '
            f'{"Outline" if b.mode == "outline" else "Timeline"}</h1>'),
        # navigator.share() displays this as text, so it gets the tag-free
        # title — and it is a JS literal, so js_str() rather than interpolation.
        "share_title": f"title:{js_str(title_txt + ' Timeline')}",
        "share_import": f"Someone shared their {jsq(b.title)} timeline with you",
        "act_names": act_names_lit,
        "map_act_names": f"var ACT_NAMES = {act_names_lit};",
        "map_act_colors": ("var ACCENT_COLORS = ["
                           + ",".join(js_str(a.color + "cc") for a in b.acts) + "];"),
    }
    return regions, tokens


def connections_block(connections: list) -> str:
    return "const CONNECTIONS = [" + ",".join(
        f"\n  {js_json(c, ensure_ascii=True)}" for c in connections) + "\n];"
