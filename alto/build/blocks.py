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


def resolve_filters(b: Brief, nodes: list[Node]) -> list[dict]:
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


def _sym(svg: str) -> str:
    return js_str(svg) if svg else js_str(FALLBACK_GLYPH)


def timeline_blocks(b: Brief, nodes: list[Node], positions, heights,
                    mgrid, mobile_world_h: int, *, reports_href: str = None,
                    view_path: str = "", connections: list = None) -> tuple[dict, dict]:
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
    resolved_filters = resolve_filters(b, nodes)
    nav_replaced = {rf["spec"].source for rf in resolved_filters
                    if rf["spec"].replace_nav
                    and rf["spec"].source in ("entity", "axis1", "axis2")}

    # Relation "line key": the legend that names which line color means which
    # relation. Only relations actually used by a connection are shown, in
    # vocabulary order; a labeled spine appears last as the neutral flowing line.
    used_rels = {c[2] for c in (connections or []) if len(c) >= 3}
    rel_counts = {}
    for c in (connections or []):
        if len(c) >= 3:
            rel_counts[c[2]] = rel_counts.get(c[2], 0) + 1
    # (key, label, swatch) — the key drives the interactive isolate control.
    rel_key_items = [(r.key, r.label, f"var(--rel-{r.key})") for r in b.relations
                     if r.key != "spine" and r.color and r.label
                     and r.key in used_rels]
    # The spine joins the key only when there is a colored relation to tell it
    # apart from — a spine-only timeline's neutral thread is self-evident, and a
    # one-row "Lines" legend on it is noise (and would break byte-parity).
    _spine = next((r for r in b.relations if r.key == "spine"), None)
    if rel_key_items and _spine and _spine.label and "spine" in used_rels:
        rel_key_items.append(("spine", _spine.label, "var(--line-flow)"))

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
    if ax1 and "axis1" not in nav_replaced:
        axis_dots += ('\n    <div class="legend-item"><div class="legend-dot" '
                      'style="background:var(--env-color);border-radius:2px">'
                      f'</div>{ax1.singular}</div>')
    if ax2 and "axis2" not in nav_replaced:
        axis_dots += ('\n    <div class="legend-item"><div class="legend-dot" '
                      f'style="background:var(--theme-color)"></div>{ax2.singular}</div>')
    divider = ('\n    <div style="width:1px;height:14px;background:var(--border);'
               'margin:0 4px"></div>') if axis_dots else ""
    legend = f'<div id="legend">{legend_items}{divider}{axis_dots}\n  </div>'

    def nav_btn(kind, vid, sym, name, extra_cls=""):
        return (f'\n    <button class="nav-btn{extra_cls}" '
                f"onclick=\"showDetail('{kind}','{vid}')\">{sym} {name}</button>")

    nav = [f'<div id="nav">\n    <span class="title">{b.title}</span>']
    if b.entities and "entity" not in nav_replaced:
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
        if not ax or src in nav_replaced:
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
    # Relation line key (desktop): each entry is a toggle — click it to isolate
    # that relation's lines on the canvas (dim the rest) — with a live edge count.
    # Mobile hides #nav .nav-btn entirely, so the drawer carries its own copy.
    if rel_key_items:
        nav.append('\n    <div class="nav-divider"></div>')
        nav.append('\n    <span class="nav-group-label">Lines</span>')
        for key, label, swatch in rel_key_items:
            nav.append(
                f'\n    <button class="nav-btn line-key-btn" data-rel-key="{key}">'
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
        return f"const {name}={{" + ",".join(
            f"'{v.id}':{_sym(v.symbol_svg)}" for v in ax.values) + "};"

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
               + DOCTRINE_BODY + LINES_GLUE)
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
    if b.entities and "entity" not in nav_replaced:
        drawer.append(f"'    <div class=\"drawer-section-label\">{b.entity_axis_label}</div>',")
        for e in b.entities:
            thin = _ent_thin(e.id)
            nm = (e.name + f'<span class="nav-chip-count{" thin" if thin else ""}">'
                  f'{ent_count[e.id]}</span>')
            drawer.append(drawer_btn("char", e.id, e.symbol_svg, nm, data_char=e.id))
    for ax, src, kind, cls in ((ax1, "axis1", "env", " env-btn"),
                               (ax2, "axis2", "theme", " theme-btn")):
        if not ax or src in nav_replaced:
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
        "node_sections": NODE_SECTIONS_D,
        "char_sections": CHAR_SECTIONS_D,
        "env_sections": ENV_SECTIONS_D,
        "theme_sections": THEME_SECTIONS_D,
        "node_sections_m": NODE_SECTIONS_M,
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
        "course_id_lit": f"courseId:'{tid}'",
        "drawer_title": f"'    <span id=\"nav-drawer-title\">{b.title}</span>',",
        "doc_save_key": f"alto-doc-{tid}",
        "hl_key": f"alto-hl-{tid}",
        "hl_key_legacy": f"alto-hl-{tid}-legacy",
        "rp_key": f"alto-rp-{tid}",
        "sim_name": b.owner_name or "Alto User",
        "sim_email": owner_mail,
        "course_id_var": f"var COURSE_ID = '{tid}';",
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
        "print_title": f'<h1 class="print-tl-title">{b.title} — Timeline</h1>',
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
