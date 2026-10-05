"""Decision trees inside a page (Section.tree).

A page section may carry a small tree of its own: a question at the top, the
answers as labelled lines, and what follows each answer below it. It is drawn
inside that section, under the section's own text, so it sits within the page
rather than taking it over; a page without one is unchanged. The use it was
made for: deep in an outline, a concept still has a lot under it (a test with
branches, a sequence of elements) that would bury the map if every step were
a card of its own.

Each step of a tree is a card. What a card leads to is the author's choice:
  nothing        — a card is just its title and text;
  `link`         — the id of a timeline node, element or axis value; the card
                   opens that page;
  `sections`     — a page of its own, opened as a panel under the tree (with
                   the path that leads to it), never a full detail page.

    tree = {"nodes": [{id, title, parent?, text?, tag?, edge?, tone?, link?,
                       sections?: [{h, t, prov?}]}, ...],
            "layout": "auto" | "tree" | "list",   # list = indented, for phones
            "open": true,                         # false: starts folded away
            "fold_below": 0,                      # levels open at first (0 = all)
            "label": ""}                          # the bar's name ("Decision tree")

Exactly one step has no parent (the first question); `edge` is the label on the
line from the parent ("Yes", "No", "Consent given"). §0 applies as everywhere:
every word comes from the user's material.

Build path: brief._check_sections → check_tree (shape); sanitize.sanitize_brief
→ sanitize_tree (text, links); builder → prepare (a slot in the section's text
plus the data) → tree_block (data + renderer, only when some page has a tree).
"""
from __future__ import annotations

import json
import re

MAX_TREE_NODES = 80
MAX_TREE_DEPTH = 10
TREE_LAYOUTS = ("auto", "tree", "list")
TONES = ("", "green", "red", "amber", "blue", "violet", "gray")
TREE_KEYS = {"nodes", "layout", "open", "fold_below", "label"}
NODE_KEYS = {"id", "parent", "title", "text", "tag", "edge", "tone", "link",
             "sections"}
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
_LIMITS = {"title": 300, "text": 4000, "tag": 80, "edge": 80, "label": 120}
MAX_TREE_SECTIONS = 8


def _err(msg):
    from .brief import BriefError
    return BriefError(msg)


def check_tree(tree, what: str) -> None:
    """Shape only: keys, ids, one root, parents that exist, no cycles, limits.
    Links are checked in sanitize_tree, where the page ids are known."""
    if not tree:
        return
    if not isinstance(tree, dict):
        raise _err(f"{what} tree: must be an object {{nodes: [...]}}")
    bad = sorted(set(tree) - TREE_KEYS)
    if bad:
        raise _err(f"{what} tree: unknown key(s) {', '.join(bad)} — allowed: "
                   + ", ".join(sorted(TREE_KEYS)))
    if tree.get("layout", "auto") not in TREE_LAYOUTS:
        raise _err(f"{what} tree: layout must be one of {list(TREE_LAYOUTS)}")
    fb = tree.get("fold_below", 0)
    if not isinstance(fb, int) or isinstance(fb, bool) or not 0 <= fb <= MAX_TREE_DEPTH:
        raise _err(f"{what} tree: fold_below must be a whole number 0-{MAX_TREE_DEPTH}")
    if len(str(tree.get("label") or "")) > _LIMITS["label"]:
        raise _err(f"{what} tree: label is longer than {_LIMITS['label']} characters")
    nodes = tree.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise _err(f"{what} tree: needs a non-empty `nodes` list")
    if len(nodes) > MAX_TREE_NODES:
        raise _err(f"{what} tree: {len(nodes)} steps exceeds the {MAX_TREE_NODES}-step limit")
    ids, parent = set(), {}
    for i, n in enumerate(nodes):
        w = f"{what} tree step {i + 1}"
        if not isinstance(n, dict):
            raise _err(f"{w}: must be an object")
        bad = sorted(set(n) - NODE_KEYS)
        if bad:
            raise _err(f"{w}: unknown key(s) {', '.join(bad)} — allowed: "
                       + ", ".join(sorted(NODE_KEYS)))
        nid = n.get("id") or ""
        if not _ID.match(nid):
            raise _err(f"{w}: id {nid!r} must be a lowercase slug (a-z, 0-9, hyphens)")
        if nid in ids:
            raise _err(f"{w}: id {nid!r} is used twice in this tree")
        ids.add(nid)
        if not str(n.get("title") or "").strip():
            raise _err(f"{w} ({nid}): needs a title")
        for k, lim in _LIMITS.items():
            if k in n and len(str(n.get(k) or "")) > lim:
                raise _err(f"{w} ({nid}): {k} is longer than {lim} characters")
        if (n.get("tone") or "") not in TONES:
            raise _err(f"{w} ({nid}): tone must be one of {[t for t in TONES if t]}")
        secs = n.get("sections") or []
        if not isinstance(secs, list) or len(secs) > MAX_TREE_SECTIONS:
            raise _err(f"{w} ({nid}): sections must be a list of at most "
                       f"{MAX_TREE_SECTIONS} {{h, t}}")
        for j, s in enumerate(secs):
            if not isinstance(s, dict) or set(s) - {"h", "t", "prov"}:
                raise _err(f"{w} ({nid}) section {j + 1}: must be {{h, t, prov?}}")
            if len(str(s.get("t") or "")) > 20_000:
                raise _err(f"{w} ({nid}) section {j + 1}: text is longer than 20000 characters")
        parent[nid] = n.get("parent") or ""
    roots = [i for i, p in parent.items() if not p]
    if len(roots) != 1:
        raise _err(f"{what} tree: exactly one step must have no parent (the first "
                   f"question); found {len(roots)}" + (f": {', '.join(roots[:5])}" if roots else ""))
    for nid, p in parent.items():
        if p and p not in ids:
            raise _err(f"{what} tree step {nid}: parent {p!r} is not a step of this tree")
    for nid in parent:
        seen, cur, depth = set(), nid, 0
        while parent[cur]:
            if cur in seen:
                raise _err(f"{what} tree: steps {nid} and {cur} are each other's ancestors")
            seen.add(cur)
            cur, depth = parent[cur], depth + 1
        if depth >= MAX_TREE_DEPTH:
            raise _err(f"{what} tree step {nid}: more than {MAX_TREE_DEPTH} levels deep")


def sanitize_tree(tree, link_types: dict, sources, what: str) -> list[str]:
    """Plain text for the card fields, allowlisted markup for a step's own
    sections, and each `link` resolved to the page it names. In place;
    returns warnings (an unknown link is dropped, the card stays)."""
    from .sanitize import plain_text, clean_linked_markup
    if not tree:
        return []
    warnings = []
    tree["label"] = plain_text(tree.get("label") or "")
    for n in tree.get("nodes") or []:
        for k in ("title", "text", "tag", "edge"):
            if k in n:
                n[k] = plain_text(n.get(k) or "")
        link = (n.get("link") or "").strip()
        if link:
            typ = link_types.get(link)
            if typ:
                n["link"] = [typ, link]
            else:
                warnings.append(f"{what} tree step {n['id']}: link {link!r} is not a "
                                "page of this timeline — the card shows without it")
                n.pop("link", None)
        for i, s in enumerate(n.get("sections") or []):
            s["h"] = plain_text(s.get("h") or "")
            s["t"], w = clean_linked_markup(s.get("t") or "", link_types, sources)
            warnings.extend(f"{what} tree step {n['id']} section {i + 1}: {m}" for m in w)
    return warnings


def _all_sections(b, nodes):
    for n in nodes:
        yield f"n-{n.id}", n.sections
    for e in b.entities:
        yield f"c-{e.id}", e.sections
    for ai, ax in enumerate(b.axes):
        yield f"x{ai}", ax.index_sections
        for v in ax.values:
            yield f"a{ai}-{v.id}", v.sections


def prepare(b, nodes) -> dict:
    """After sanitize: give every section that carries a tree a slot at the end
    of its text (the tree's words inside it, hidden, so search finds them) and
    return the data the renderer reads, {key: tree}."""
    from .sanitize import esc
    reg = {}
    for owner, secs in _all_sections(b, nodes):
        for i, s in enumerate(secs or []):
            tree = getattr(s, "tree", None)
            if not tree or not tree.get("nodes"):
                continue
            key = f"{owner}-{i}"
            words = " · ".join(
                " ".join(x for x in (n.get("edge"), n.get("title"), n.get("text")) if x)
                for n in tree["nodes"])
            s.t = (s.t or "") + (f'<span class="adt-slot" data-adt="{key}" hidden>'
                                 f"{esc(words)}</span>")
            reg[key] = _compact(tree)
    return reg


def _compact(tree) -> dict:
    out = {"n": [], "lay": tree.get("layout") or "auto",
           "open": tree.get("open", True) is not False,
           "fold": int(tree.get("fold_below") or 0),
           "label": tree.get("label") or ""}
    for n in tree["nodes"]:
        c = {"i": n["id"], "t": n.get("title") or ""}
        for src, dst in (("parent", "p"), ("text", "x"), ("tag", "g"),
                         ("edge", "e"), ("tone", "c"), ("link", "l")):
            if n.get(src):
                c[dst] = n[src]
        secs = [{"h": s.get("h") or "", "t": s["t"]}
                for s in n.get("sections") or [] if s.get("t")]
        if secs:
            c["s"] = secs
        out["n"].append(c)
    return out


def tree_block(reg: dict) -> str:
    """The data and the renderer, or "" when no page has a tree (a timeline
    without one is byte-for-byte what it was)."""
    if not reg:
        return ""
    data = json.dumps(reg, ensure_ascii=False, separators=(",", ":"))
    data = data.replace("</", "<\\/").replace("<!--", "<\\!--")
    return (f'<script id="alto-dt-data">window._ALTO_DT={data};</script>\n'
            + TREE_CSS + "\n" + TREE_JS + "\n")


TREE_CSS = r"""<style id="alto-dt-css">
  .adt{--adt-line:color-mix(in srgb,var(--text) 34%,transparent);margin:18px 0 6px;border:1px solid var(--border);border-radius:16px;
    background:color-mix(in srgb,var(--surface) 55%,transparent);font-size:14px;line-height:1.45;color:var(--text);
    -webkit-user-select:text;user-select:text;}
  .adt-bar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:9px 12px 9px 14px;}
  .adt-name{font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);}
  .adt-meta{font-size:12px;color:var(--muted);opacity:.8;}
  .adt-sp{flex:1;}
  .adt-btn{font:inherit;font-size:12px;line-height:1;padding:6px 10px;border-radius:999px;border:1px solid var(--btn-border,var(--border));
    background:transparent;color:var(--text);cursor:pointer;-webkit-tap-highlight-color:transparent;}
  .adt-btn:hover{background:var(--btn-hover-bg,rgba(0,0,0,.06));border-color:var(--btn-hover-border,var(--border));}
  .adt.shut .adt-body{display:none;}
  .adt.shut .adt-bar{cursor:pointer;}
  .adt-scroll{overflow-x:auto;overflow-y:hidden;overscroll-behavior-x:contain;border-top:1px solid var(--border);}
  .adt-stage{position:relative;display:block;min-width:100%;box-sizing:border-box;padding:18px 14px 22px;vertical-align:top;}
  .adt-lines{position:absolute;left:0;top:0;overflow:visible;pointer-events:none;z-index:0;}
  .adt-lines path{fill:none;stroke:var(--adt-line);stroke-width:1.5;stroke-linecap:round;transition:opacity .2s,stroke .2s;}
  .adt-tree{display:flex;justify-content:center;}
  .adt-sub{display:flex;flex-direction:column;align-items:center;padding:0 5px;position:relative;flex-shrink:0;}
  .adt-kids{display:flex;align-items:flex-start;justify-content:center;margin-top:24px;}
  .adt-sub.folded>.adt-kids{display:none;}
  .adt-edge{height:22px;margin-bottom:8px;display:flex;align-items:center;justify-content:center;position:relative;z-index:1;}
  .adt-edge span{font-size:10.5px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;padding:2px 9px;border-radius:999px;
    background:var(--bg);border:1px solid var(--border);color:var(--muted);white-space:nowrap;}
  .adt-card{position:relative;z-index:1;width:166px;box-sizing:border-box;padding:9px 12px 10px;border-radius:12px;text-align:left;
    background:var(--card-glass-bg,var(--surface));border:1px solid var(--border);box-shadow:0 4px 14px var(--node-rest-shadow,rgba(0,0,0,.08));
    transition:box-shadow .2s,border-color .2s,opacity .2s;}
  .adt-card.go{cursor:pointer;}
  .adt-card.go:hover{border-color:var(--card-hover-border,var(--muted));box-shadow:0 8px 22px var(--node-hover-shadow,rgba(0,0,0,.16));}
  .adt-card.sel{border-color:var(--accent,#7c6cf0);box-shadow:0 0 0 2px color-mix(in srgb,var(--accent,#7c6cf0) 35%,transparent);}
  .adt-card::before{content:"";position:absolute;left:10px;right:10px;top:0;height:3px;border-radius:0 0 3px 3px;background:var(--adt-tone,transparent);}
  .adt-tag{font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--adt-tone,var(--muted));margin-bottom:3px;}
  .adt-t{font-weight:650;font-size:14px;line-height:1.35;}
  .adt-x{margin-top:4px;font-size:12.5px;line-height:1.45;color:var(--card-desc-color,var(--muted));}
  .adt-foot{display:flex;flex-wrap:wrap;gap:6px;margin-top:7px;}
  .adt-foot:empty{display:none;}
  .adt-chip{font-size:11px;line-height:1;padding:4px 7px;border-radius:999px;border:1px solid var(--border);color:var(--muted);
    background:var(--chip-plate,transparent);cursor:pointer;white-space:nowrap;}
  .adt-chip:hover{color:var(--text);border-color:var(--muted);}
  .adt-fold{position:absolute;left:50%;bottom:-11px;transform:translateX(-50%);z-index:2;min-width:22px;height:20px;padding:0 6px;
    border-radius:999px;border:1px solid var(--border);background:var(--bg);color:var(--muted);font:inherit;font-size:11px;line-height:18px;cursor:pointer;}
  .adt-fold:hover{color:var(--text);border-color:var(--muted);}
  .adt-card.tone-green{--adt-tone:#16a34a;} .adt-card.tone-red{--adt-tone:#dc2626;} .adt-card.tone-amber{--adt-tone:#d97706;}
  .adt-card.tone-blue{--adt-tone:#2563eb;} .adt-card.tone-violet{--adt-tone:#7c3aed;} .adt-card.tone-gray{--adt-tone:#64748b;}
  html.dark .adt-card.tone-green{--adt-tone:#4ade80;} html.dark .adt-card.tone-red{--adt-tone:#f87171;} html.dark .adt-card.tone-amber{--adt-tone:#fbbf24;}
  html.dark .adt-card.tone-blue{--adt-tone:#60a5fa;} html.dark .adt-card.tone-violet{--adt-tone:#a78bfa;} html.dark .adt-card.tone-gray{--adt-tone:#94a3b8;}
  .adt.tracing .adt-lines path{opacity:.35;}
  .adt.tracing .adt-lines path.on{opacity:1;stroke:var(--accent,#7c6cf0);stroke-width:2.2;}
  .adt.tracing .adt-card:not(.on){opacity:.62;}
  .adt.tracing .adt-edge.on span{color:var(--text);border-color:var(--accent,#7c6cf0);}
  /* list view: indented, for narrow pages */
  .adt.list .adt-tree{display:block;}
  .adt.list .adt-sub{display:block;padding:0;}
  .adt.list .adt-kids{display:block;margin:10px 0 0 28px;}
  .adt.list .adt-kids>.adt-sub+.adt-sub{margin-top:10px;}
  .adt.list .adt-edge{height:auto;margin:0 0 4px;justify-content:flex-start;}
  .adt.list .adt-card{width:auto;max-width:560px;}
  .adt.list .adt-fold{left:auto;right:10px;bottom:auto;top:8px;transform:none;}
  .adt-panel{border-top:1px solid var(--border);padding:16px 18px 18px;}
  .adt-panel[hidden]{display:none;}
  .adt-ph{display:flex;align-items:flex-start;gap:10px;}
  .adt-ph>div{flex:1;}
  .adt-pt{font-size:19px;font-weight:650;line-height:1.3;}
  .adt-path{margin:8px 0 4px;font-size:12.5px;color:var(--muted);line-height:1.7;}
  .adt-path b{font-weight:650;color:var(--text);}
  .adt-path i{font-style:normal;font-size:10.5px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;padding:1px 6px;
    border:1px solid var(--border);border-radius:999px;margin:0 2px;}
  .adt-ps{margin-top:14px;}
  .adt-ps h4{margin:0 0 4px;font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);}
  .adt-ps div{font-size:15px;line-height:1.75;}
  .adt-open{margin-top:14px;}
  html.mobile .adt{margin-left:-4px;margin-right:-4px;}
  @media print{ .adt-btn,.adt-fold{display:none;} .adt.shut .adt-body{display:block;} .adt-scroll{overflow:visible;} }
</style>"""


# Renders every .adt-slot that appears on the page (the detail page, a mobile
# swipe peek), wherever it was rendered from. Geometry is layout px measured up
# the offsetParent chain to the stage (never screen coordinates: those are wrong
# in Safari under CSS zoom — see the 1.8.34 note in the deploy map).
TREE_JS = r"""<script id="alto-dt">
(function(){
  var D = window._ALTO_DT || {}, SVGNS = 'http://www.w3.org/2000/svg';
  function el(tag, cls, txt){ var e = document.createElement(tag); if(cls) e.className = cls; if(txt != null) e.textContent = txt; return e; }
  function mobile(){ return document.documentElement.classList.contains('mobile'); }
  function render(slot){
    var key = slot.getAttribute('data-adt'), T = D[key];
    if(!T || !T.n || !T.n.length){ slot.removeAttribute('data-adt'); return; }
    var byId = {}, kids = {}, root = null;
    T.n.forEach(function(n){ byId[n.i] = n; kids[n.i] = []; });
    T.n.forEach(function(n){ if(n.p && byId[n.p]) kids[n.p].push(n.i); else if(!root) root = n.i; });
    function depth(id){ var d = 0; while(byId[id] && byId[id].p){ id = byId[id].p; d++; } return d; }
    var levels = 0; T.n.forEach(function(n){ levels = Math.max(levels, depth(n.i) + 1); });

    var box = el('div', 'adt' + (T.open ? '' : ' shut')); box.setAttribute('data-adt-key', key);
    var bar = el('div', 'adt-bar');
    bar.appendChild(el('span', 'adt-name', T.label || 'Decision tree'));
    bar.appendChild(el('span', 'adt-meta', T.n.length + ' steps · ' + levels + ' levels'));
    bar.appendChild(el('span', 'adt-sp'));
    var bView = el('button', 'adt-btn'), bAll = el('button', 'adt-btn', 'Unfold all'), bShut = el('button', 'adt-btn');
    bView.type = bAll.type = bShut.type = 'button';
    bar.appendChild(bView); bar.appendChild(bAll); bar.appendChild(bShut);
    var body = el('div', 'adt-body'), scroll = el('div', 'adt-scroll'), stage = el('div', 'adt-stage');
    var svg = document.createElementNS(SVGNS, 'svg'); svg.setAttribute('class', 'adt-lines');
    var treeEl = el('div', 'adt-tree'), panel = el('div', 'adt-panel'); panel.hidden = true;
    stage.appendChild(svg); stage.appendChild(treeEl); scroll.appendChild(stage);
    body.appendChild(scroll); body.appendChild(panel);
    box.appendChild(bar); box.appendChild(body);

    var subs = {}, cards = {}, edges = {};
    function count(id){ var c = 0; kids[id].forEach(function(k){ c += 1 + count(k); }); return c; }
    function make(id, d){
      var n = byId[id], sub = el('div', 'adt-sub'); sub.setAttribute('data-i', id);
      if(n.p){ var ed = el('div', 'adt-edge'); if(n.e) ed.appendChild(el('span', '', n.e)); sub.appendChild(ed); edges[id] = ed; }
      var card = el('div', 'adt-card' + (n.c ? ' tone-' + n.c : '') + ((n.s || n.l) ? ' go' : ''));
      card.setAttribute('data-i', id);
      if(n.s || n.l){ card.tabIndex = 0; card.setAttribute('role', 'button'); }
      if(n.g) card.appendChild(el('div', 'adt-tag', n.g));
      card.appendChild(el('div', 'adt-t', n.t));
      if(n.x) card.appendChild(el('div', 'adt-x', n.x));
      var foot = el('div', 'adt-foot');
      if(n.s) foot.appendChild(el('span', 'adt-chip adt-more', 'More ›'));
      if(n.l){ var lc = el('span', 'adt-chip adt-link', '↗ ' + pageName(n.l)); lc.setAttribute('data-go', '1'); foot.appendChild(lc); }
      card.appendChild(foot);
      sub.appendChild(card); subs[id] = sub; cards[id] = card;
      if(kids[id].length){
        var f = el('button', 'adt-fold'); f.type = 'button'; f.setAttribute('data-fold', id); card.appendChild(f);
        var wrap = el('div', 'adt-kids');
        kids[id].forEach(function(k){ wrap.appendChild(make(k, d + 1)); });
        sub.appendChild(wrap);
        if(T.fold && d + 1 >= T.fold) sub.classList.add('folded');
      }
      return sub;
    }
    function pageName(l){
      try{
        if(l[0] === 'node'){ var nn = (typeof NODES_SRC !== 'undefined' ? NODES_SRC : (typeof NODES !== 'undefined' ? NODES : [])).filter(function(x){ return x.id === l[1]; })[0];
          return nn ? (window._altoNodeName ? window._altoNodeName(nn) : nn.title) : 'Open page'; }
        var M = l[0] === 'char' ? (typeof CHARS !== 'undefined' && CHARS) : l[0] === 'env' ? (typeof ENVS !== 'undefined' && ENVS) : (typeof THEMES !== 'undefined' && THEMES);
        var v = M && M[l[1]]; return v && v.name ? String(v.name).replace(/<[^>]*>/g, '') : 'Open page';
      }catch(e){ return 'Open page'; }
    }
    treeEl.appendChild(make(root, 0));
    function syncFolds(){
      Object.keys(subs).forEach(function(id){
        var b = subs[id].querySelector(':scope>.adt-card>.adt-fold'); if(!b) return;
        var f = subs[id].classList.contains('folded');
        b.textContent = f ? '+' + count(id) : '−';
        b.title = f ? 'Show the ' + count(id) + ' steps under this one' : 'Fold the steps under this one';
      });
      var any = !!box.querySelector('.adt-sub.folded'); bAll.textContent = any ? 'Unfold all' : 'Fold all';
    }

    // ── place: tree (top-down) or list (indented) ──
    var mode = null, userMode = null, treeW = 0;
    function want(){
      if(userMode) return userMode;
      if(T.lay === 'tree' || T.lay === 'list') return T.lay;
      var w = scroll.clientWidth || box.clientWidth;
      return (treeW > w + 4 && (mobile() || w < 600)) ? 'list' : 'tree';
    }
    function setMode(m){
      mode = m; box.classList.toggle('list', m === 'list');
      bView.textContent = m === 'list' ? 'Tree view' : 'List view';
    }
    function pos(e){ var x = 0, y = 0; while(e && e !== stage){ x += e.offsetLeft; y += e.offsetTop; e = e.offsetParent; } return [x, y]; }
    function draw(){
      if(box.classList.contains('shut') || !stage.offsetParent) return;
      svg.setAttribute('width', stage.scrollWidth); svg.setAttribute('height', stage.scrollHeight);
      while(svg.firstChild) svg.removeChild(svg.firstChild);
      T.n.forEach(function(n){
        if(!n.p) return; var c = cards[n.i], pc = cards[n.p];
        if(!c.offsetParent || !pc.offsetParent) return;
        var a = pos(pc), b = pos(c), d;
        if(mode === 'list'){
          var tx = a[0] + 14, y0 = a[1] + pc.offsetHeight, cy = b[1] + 17, r = Math.min(7, (cy - y0) / 2);
          d = 'M' + tx + ' ' + y0 + ' V' + (cy - r) + ' Q' + tx + ' ' + cy + ' ' + (tx + r) + ' ' + cy + ' H' + b[0];
        } else {
          var px = a[0] + pc.offsetWidth / 2, py = a[1] + pc.offsetHeight, cx = b[0] + c.offsetWidth / 2,
              kt = pos(subs[n.p].querySelector(':scope>.adt-kids'))[1], by = py + Math.max(6, (kt - py) * 0.55), dx = cx - px,
              rr = Math.min(9, Math.abs(dx) / 2, by - py, 9);
          if(Math.abs(dx) < 1) d = 'M' + px + ' ' + py + ' V' + b[1];
          else { var s = dx > 0 ? 1 : -1;
            d = 'M' + px + ' ' + py + ' V' + (by - rr) + ' Q' + px + ' ' + by + ' ' + (px + s * rr) + ' ' + by
              + ' H' + (cx - s * rr) + ' Q' + cx + ' ' + by + ' ' + cx + ' ' + (by + rr) + ' V' + b[1]; }
        }
        var p = document.createElementNS(SVGNS, 'path'); p.setAttribute('d', d); p.setAttribute('data-c', n.i); svg.appendChild(p);
      });
    }
    function layout(){
      if(box.classList.contains('shut')) return;
      // A tree's own width, measured: Chrome's intrinsic width for nested
      // centred flex columns overshoots by hundreds of px.
      var m = want(); if(m !== mode) setMode(m);
      if(mode === 'tree'){ stage.style.width = (subs[root].offsetWidth + 28) + 'px'; treeW = stage.offsetWidth;
        m = want(); if(m !== mode) setMode(m); }
      if(mode === 'list') stage.style.width = '';
      draw();
      if(mode === 'tree' && !scroll._c && stage.offsetWidth > scroll.clientWidth){
        scroll._c = 1; var rc = cards[root]; scroll.scrollLeft = Math.max(0, pos(rc)[0] + rc.offsetWidth / 2 - scroll.clientWidth / 2);
      }
    }

    // ── trace the path to a card ──
    function chain(id){ var out = []; while(id){ out.unshift(id); id = byId[id] ? byId[id].p : ''; } return out; }
    function trace(id){
      Object.keys(cards).forEach(function(k){ cards[k].classList.remove('on'); });
      Object.keys(edges).forEach(function(k){ edges[k].classList.remove('on'); });
      Array.prototype.forEach.call(svg.childNodes, function(p){ p.classList.remove('on'); });
      if(!id){ box.classList.remove('tracing'); return; }
      var on = {}; chain(id).forEach(function(k){ on[k] = 1; cards[k].classList.add('on'); if(edges[k]) edges[k].classList.add('on'); });
      Array.prototype.forEach.call(svg.childNodes, function(p){ if(on[p.getAttribute('data-c')]) p.classList.add('on'); });
      box.classList.add('tracing');
    }

    // ── a step's own page, under the tree ──
    var openId = null;
    function closePanel(){ panel.hidden = true; panel.innerHTML = ''; if(openId && cards[openId]) cards[openId].classList.remove('sel'); openId = null; }
    function openPanel(id){
      var n = byId[id]; if(openId === id){ closePanel(); return; }
      closePanel(); openId = id; cards[id].classList.add('sel');
      var head = el('div', 'adt-ph'), hd = el('div');
      if(n.g) hd.appendChild(el('div', 'adt-tag', n.g));
      hd.appendChild(el('div', 'adt-pt', n.t)); head.appendChild(hd);
      var x = el('button', 'adt-btn', 'Close'); x.type = 'button'; x.onclick = closePanel; head.appendChild(x);
      panel.appendChild(head);
      var ch = chain(id);
      if(ch.length > 1){
        var path = el('div', 'adt-path');
        ch.forEach(function(k, i){
          if(i){ path.appendChild(document.createTextNode(' → ')); if(byId[k].e){ path.appendChild(el('i', '', byId[k].e)); path.appendChild(document.createTextNode(' ')); } }
          path.appendChild(i === ch.length - 1 ? el('b', '', byId[k].t) : document.createTextNode(byId[k].t));
        });
        panel.appendChild(path);
      }
      if(n.x) panel.appendChild(el('div', 'adt-x', n.x));
      (n.s || []).forEach(function(s){
        var w = el('div', 'adt-ps'); if(s.h) w.appendChild(el('h4', '', s.h));
        var t = el('div'); t.innerHTML = s.t; w.appendChild(t); panel.appendChild(w);
      });
      if(n.l){ var go = el('button', 'adt-btn adt-open', '↗ Open ' + pageName(n.l)); go.type = 'button';
        go.onclick = function(){ window.showDetail(n.l[0], n.l[1]); }; panel.appendChild(go); }
      panel.hidden = false;
      try{ panel.scrollIntoView({block:'nearest', behavior:'smooth'}); }catch(e){}
    }

    box.addEventListener('click', function(e){
      var t = e.target;
      var sel = window.getSelection && String(window.getSelection() || '');
      if(sel && sel.trim().length > 1 && !t.closest('button')) return;      // a highlight, not a click
      if(t.closest('.adt-bar') && box.classList.contains('shut') && !t.closest('button')){ shut(false); return; }
      var fb = t.closest('[data-fold]');
      if(fb){ e.stopPropagation(); subs[fb.getAttribute('data-fold')].classList.toggle('folded'); syncFolds(); layout(); return; }
      var card = t.closest('.adt-card'); if(!card) return;
      var n = byId[card.getAttribute('data-i')];
      if(t.closest('[data-go]') && n.l){ window.showDetail(n.l[0], n.l[1]); return; }
      if(n.s) openPanel(n.i); else if(n.l) window.showDetail(n.l[0], n.l[1]);
    });
    box.addEventListener('keydown', function(e){
      if(e.key !== 'Enter' && e.key !== ' ') return;
      var card = e.target.closest && e.target.closest('.adt-card.go'); if(!card) return;
      e.preventDefault(); card.click();
    });
    if(!mobile()){
      box.addEventListener('mouseover', function(e){ var c = e.target.closest('.adt-card'); trace(c ? c.getAttribute('data-i') : null); });
      box.addEventListener('mouseleave', function(){ trace(null); });
    }
    function shut(v){ box.classList.toggle('shut', v); bShut.textContent = v ? 'Show' : 'Hide'; if(!v) requestAnimationFrame(layout); }
    bShut.onclick = function(e){ e.stopPropagation(); shut(!box.classList.contains('shut')); };
    bView.onclick = function(){ userMode = mode === 'list' ? 'tree' : 'list'; if(userMode === 'tree') scroll._c = 0; setMode(userMode); layout(); };
    bAll.onclick = function(){
      var any = !!box.querySelector('.adt-sub.folded');
      Object.keys(subs).forEach(function(id){ if(kids[id].length && id !== root) subs[id].classList.toggle('folded', !any); });
      if(!any) subs[root].classList.remove('folded');
      syncFolds(); layout();
    };
    bShut.textContent = T.open ? 'Hide' : 'Show';
    setMode(T.lay === 'list' ? 'list' : 'tree');
    syncFolds();

    // Put the tree after the paragraph that held its slot, inside the section.
    var p = slot.parentNode, host = p && p.tagName === 'P' ? p : null;
    if(host && host.parentNode){ host.parentNode.insertBefore(box, host.nextSibling); slot.parentNode.removeChild(slot);
      if(!host.textContent.trim() && !host.querySelector('img,svg')) host.parentNode.removeChild(host); }
    else slot.parentNode.replaceChild(box, slot);
    if(window.ResizeObserver){ var ro = new ResizeObserver(function(){ if(document.contains(box)) layout(); else ro.disconnect(); }); ro.observe(scroll); }
    requestAnimationFrame(layout);
    if(document.fonts && document.fonts.ready) document.fonts.ready.then(function(){ if(document.contains(box)) layout(); });
  }
  function scan(){ var s = document.querySelectorAll('.adt-slot[data-adt]'); for(var i = 0; i < s.length; i++){ try{ render(s[i]); }catch(e){ if(window.console) console.warn('alto tree', e); } } }
  window._altoTrees = scan;
  var queued = false;
  function soon(){ if(queued) return; queued = true; Promise.resolve().then(function(){ queued = false; scan(); }); }
  // The detail page in depth; the body only at its top level, where the mobile
  // swipe peeks are added — never the canvas, whose cards and lines move a lot.
  function watch(){
    var mo = new MutationObserver(function(ms){
      for(var i = 0; i < ms.length; i++){ var a = ms[i].addedNodes;
        for(var j = 0; j < a.length; j++){ var x = a[j]; if(x.nodeType === 1 && (x.classList.contains('adt-slot') || x.querySelector('.adt-slot'))){ soon(); return; } } }
    });
    var dp = document.getElementById('detail-page') || document.getElementById('detail-content');
    if(dp) mo.observe(dp, {childList:true, subtree:true});
    mo.observe(document.body, {childList:true});
    scan();
  }
  if(document.body) watch(); else document.addEventListener('DOMContentLoaded', watch);
})();
</script>"""
