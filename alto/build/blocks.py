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
from urllib.parse import quote as url_q

from .brief import Brief, Node, COL_SETS, ROMAN
from .sanitize import css_color, one_line
from .layout import MOBILE_STEP, MOBILE_OX, MOBILE_OY, MOBILE_WORLD_W

# Generic section-builder code (same shape as the template's empty defaults —
# kept in one place because emit() replaces the whole region span).
NODE_SECTIONS_D = (
    "sections = ((nd.sections)||[]).filter(s=>s&&s.t);\n"
    "    if(sections.length === 0) sections.push({h:'Synopsis', t: n.desc});")
CHAR_SECTIONS_D = "sections=(p.sections||[]).filter(s=>s&&s.t);"
ENV_SECTIONS_D = "sections=(e.sections||[]).filter(s=>s&&s.t);"
THEME_SECTIONS_D = "sections=(th.sections||[]).filter(s=>s&&s.t);"
NODE_SECTIONS_M = (
    "var sections=((ndDet.sections)||[]).filter(function(s){return s&&s.t;});\n"
    "          if(sections.length===0) sections.push({h:'Synopsis',t:nd.desc||''});")
CHAR_SECTIONS_M = "var chSecs=(cp.sections||[]).filter(function(s){return s&&s.t;});"
ENV_SECTIONS_M = "var enSecs=(en.sections||[]).filter(function(s){return s&&s.t;});"
THEME_SECTIONS_M = "var thSecs=(th.sections||[]).filter(function(s){return s&&s.t;});"

FALLBACK_GLYPH = "&#9670;"   # ◆ — used when an entity/axis value has no SVG


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


def _sym(svg: str) -> str:
    return js_str(svg) if svg else js_str(FALLBACK_GLYPH)


def timeline_blocks(b: Brief, nodes: list[Node], positions, heights,
                    mgrid, mobile_world_h: int, *, reports_href: str = None,
                    view_path: str = "") -> tuple[dict, dict]:
    """Return (regions, tokens) for emit() against timeline_template.html.

    nodes must be validated, in narrative order, with col set and positions
    resolved. mgrid: id -> [colIndex, row].
    """
    tid = b.timeline_id
    ax1 = b.axes[0] if len(b.axes) > 0 else None
    ax2 = b.axes[1] if len(b.axes) > 1 else None
    ent_by_id = {e.id: e for e in b.entities}

    # ── CSS variable blocks ──────────────────────────────────────────────────
    entity_vars = "".join(f"--{e.id}:{e.color};" for e in b.entities)
    entity_vars += f"--accent:{b.accent};"

    def phase_line(alpha):
        return "".join(
            f"--phase{i+1}:rgba({r},{g},{bl},{alpha});"
            for i, (r, g, bl) in enumerate(_rgb(a.color) for a in b.acts[:5]))

    def phase_extra():
        if len(b.acts) <= 5:
            return ""
        light = "".join(f"--phase{i+6}:rgba({r},{g},{bl},0.09);"
                        for i, (r, g, bl) in
                        enumerate(_rgb(a.color) for a in b.acts[5:7]))
        dark = "".join(f"--phase{i+6}:rgba({r},{g},{bl},0.07);"
                       for i, (r, g, bl) in
                       enumerate(_rgb(a.color) for a in b.acts[5:7]))
        return (f":root{{{light}}}\n"
                f"@media(prefers-color-scheme:dark){{:root{{{dark}}}}}")

    # ── HTML chrome ──────────────────────────────────────────────────────────
    legend_items = "".join(
        f'\n    <div class="legend-item"><div class="legend-dot" '
        f'style="background:var(--{e.id})"></div>{e.name}</div>'
        for e in b.entities)
    axis_dots = ""
    if ax1:
        axis_dots += ('\n    <div class="legend-item"><div class="legend-dot" '
                      'style="background:var(--env-color);border-radius:2px">'
                      f'</div>{ax1.singular}</div>')
    if ax2:
        axis_dots += ('\n    <div class="legend-item"><div class="legend-dot" '
                      f'style="background:var(--theme-color)"></div>{ax2.singular}</div>')
    divider = ('\n    <div style="width:1px;height:14px;background:var(--border);'
               'margin:0 4px"></div>') if axis_dots else ""
    legend = f'<div id="legend">{legend_items}{divider}{axis_dots}\n  </div>'

    def nav_btn(kind, vid, sym, name, extra_cls=""):
        return (f'\n    <button class="nav-btn{extra_cls}" '
                f"onclick=\"showDetail('{kind}','{vid}')\">{sym} {name}</button>")

    nav = [f'<div id="nav">\n    <span class="title">{b.title}</span>']
    if b.entities:
        nav.append(f'\n    <span class="nav-group-label">{b.entity_axis_singular}</span>')
        for e in b.entities:
            nav.append(nav_btn("char", e.id, e.symbol_svg or FALLBACK_GLYPH, e.name))
    for ax, kind, cls in ((ax1, "env", " env-btn"), (ax2, "theme", " theme-btn")):
        if not ax:
            continue
        nav.append('\n    <div class="nav-divider"></div>')
        nav.append(f'\n    <span class="nav-group-label">{ax.singular}</span>')
        for v in ax.values:
            nav.append(nav_btn(kind, v.id, v.symbol_svg or FALLBACK_GLYPH, v.name, cls))
    nav.append("\n  </div>")
    nav = "".join(nav)

    overview = (f'<div id="summary-inner">\n{b.overview_html}\n    </div>'
                if b.overview_html else '<div id="summary-inner"></div>')

    # ── JS data consts ───────────────────────────────────────────────────────
    chars = "const CHARS={" + ",".join(
        f"\n  {e.id}: {{name:{js_str(e.name)}, role:{js_str(e.role)}, "
        f"color:'#{e.color.lstrip('#')}', symbol:{_sym(e.symbol_svg)}}}"
        for e in b.entities) + "\n};"

    char_pages = "const CHAR_PAGES={" + ",".join(
        f"\n  {e.id}: {{{_sections_js(e.sections)}}}"
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

    nodes_src = "const NODES_SRC=[" + ",".join(
        f"\n  {{id:'{n.id}', baseY:{round(positions[n.id])}, col:'{n.col}', "
        f"tag:{js_str(n.tag)}, title:{js_str(n.title)}, desc:{js_str(n.desc)}, "
        f"chars:{json.dumps(n.entity_ids)}, color:'{node_color(n)}', "
        f"envs:{json.dumps(n.axis1_values)}, themes:{json.dumps(n.axis2_values)}}}"
        for n in nodes) + "\n];"

    act_seqs_list = [[] for _ in b.acts]
    for n in nodes:
        act_seqs_list[n.act].append(n.id)
    act_seqs = "const ACT_SEQS = [" + ",".join(
        "\n  " + json.dumps(ids) for ids in act_seqs_list) + "\n];"

    phase_meta = "const PHASE_META = [" + ",".join(
        f"\n  {{label:{js_str(a.label)}, numeral:'{ROMAN[i]}', "
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
    if b.entities:
        drawer.append(f"'    <div class=\"drawer-section-label\">{b.entity_axis_label}</div>',")
        for e in b.entities:
            drawer.append(drawer_btn("char", e.id, e.symbol_svg, e.name,
                                     data_char=e.id))
    for ax, kind, cls in ((ax1, "env", " env-btn"), (ax2, "theme", " theme-btn")):
        if not ax:
            continue
        drawer.append(f"'    <div class=\"drawer-section-label\">{ax.label}</div>',")
        for v in ax.values:
            drawer.append(drawer_btn(kind, v.id, v.symbol_svg, v.name, cls))
    drawer_filters = "\n".join(drawer)

    # ── mobile grid ──────────────────────────────────────────────────────────
    mobile_grid_js = "var MOBILE_GRID = {" + ",".join(
        f"\n    '{nid}':{json.dumps(mgrid[nid])}" for nid in mgrid) + "\n  };"
    mobile_world = (f"var MOBILE_STEP={MOBILE_STEP}, MOBILE_OX={MOBILE_OX}, "
                    f"MOBILE_OY={MOBILE_OY}, MOBILE_WORLD_W={MOBILE_WORLD_W}, "
                    f"MOBILE_WORLD_H={mobile_world_h};")

    connections = None  # provided by caller via separate argument historically
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
