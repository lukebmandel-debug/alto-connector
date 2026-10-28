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

A tree with `layout: "timeline"` is a mini horizontal timeline instead: its steps
have no parents, they run in reading order along a time axis (the same shape
otherwise, so it rides every path a tree does: brief, sanitize, search slot,
manual edit, fold-in):
    {id, title, text?, tag?, tone?, link?, sections?,     # an event: a small card
     when?, kind?: "event"|"flag"|"box", to?, side?}      # when = a date ("1215",
                                                          # "March 1842", "Day 3"); a flag
                                                          # is a pennant on the axis (to =
                                                          # where its era ends); a box tag
                                                          # is a dashed caption at `when`;
                                                          # side = "above" | "below"
Dated events (two or more) are placed to scale, undated ones evenly.

Build path: brief._check_sections → check_tree (shape); sanitize.sanitize_brief
→ sanitize_tree (text, links); builder → prepare (a slot in the section's text
plus the data) → tree_block (data + renderer, on every page: manual edit mode can add a tree).
"""
from __future__ import annotations

import json
import re

from .sanitize import js_json

MAX_TREE_NODES = 80
MAX_TREE_DEPTH = 10
TREE_LAYOUTS = ("auto", "tree", "list", "timeline")
TL_KINDS = ("event", "flag", "box")
TL_SIDES = ("", "above", "below")
MAX_TL_ITEMS = 60
TONES = ("", "green", "red", "amber", "blue", "violet", "gray")
TREE_KEYS = {"nodes", "layout", "open", "fold_below", "label"}
NODE_KEYS = {"id", "parent", "title", "text", "tag", "edge", "tone", "link",
             "sections", "when", "to", "kind", "side"}
TL_ONLY = ("when", "to", "kind", "side")
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
_LIMITS = {"title": 300, "text": 4000, "tag": 80, "edge": 80, "label": 120,
           "when": 80, "to": 80}
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
    tl = tree.get("layout") == "timeline"
    if tl and len(nodes) > MAX_TL_ITEMS:
        raise _err(f"{what} timeline: {len(nodes)} items exceeds the {MAX_TL_ITEMS}-item limit")
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
        if tl:
            _check_tl_item(n, w, nid)
        elif any(n.get(k) for k in TL_ONLY):
            raise _err(f"{w} ({nid}): when / to / kind / side belong to a timeline "
                       "(tree layout: \"timeline\")")
    if tl:
        return
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


def _check_tl_item(n, w, nid) -> None:
    """One item of a mini timeline (layout "timeline"): no parent, a kind,
    and for a flag or a box tag the date it stands at."""
    if n.get("parent"):
        raise _err(f"{w} ({nid}): a timeline has no parents — its items run in "
                   "reading order along the axis; drop `parent`")
    kind = n.get("kind") or "event"
    if kind not in TL_KINDS:
        raise _err(f"{w} ({nid}): kind must be one of {list(TL_KINDS)}")
    if (n.get("side") or "") not in TL_SIDES:
        raise _err(f"{w} ({nid}): side must be \"above\" or \"below\"")
    if kind != "event" and not str(n.get("when") or "").strip():
        raise _err(f"{w} ({nid}): a {kind} stands at a date — give it `when`")
    if n.get("to") and kind != "flag":
        raise _err(f"{w} ({nid}): `to` (where an era ends) belongs to a flag")
    if kind != "event" and (n.get("sections") or n.get("link") or n.get("text")):
        raise _err(f"{w} ({nid}): a {kind} is just its words; text, link and "
                   "sections belong to an event")


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
        for k in ("title", "text", "tag", "edge", "when", "to"):
            if k in n:
                n[k] = plain_text(n.get(k) or "")
        link = n.get("link") or ""
        if isinstance(link, list):          # already resolved: [type, id]
            link = link[-1] if link else ""
        link = str(link).strip()
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
                " ".join(x for x in (n.get("edge"), n.get("title"), n.get("when"), n.get("to"), n.get("text")) if x)
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
    tl = tree.get("layout") == "timeline"
    if tl:
        from .lanes import parse_when
        out["lay"] = "timeline"
    for n in tree["nodes"]:
        c = {"i": n["id"], "t": n.get("title") or ""}
        if tl:
            c["k"] = (n.get("kind") or "event")[0]       # e / f / b: a step with a kind is a timeline's
            for src, dst in (("when", "w"), ("to", "z"), ("side", "d")):
                if n.get(src):
                    c[dst] = n[src]
            for src, dst in (("when", "v"), ("to", "u")):
                num = parse_when(n.get(src)) if n.get(src) else None
                if num is not None:
                    c[dst] = round(num, 4)
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
    """The data and the renderer. Always there, trees or not: manual edit
    mode can add a section with a tree to any page (an empty registry draws
    nothing)."""
    data = js_json(reg, separators=(",", ":"))
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
  /* mini timeline (layout "timeline"): a horizontal axis in a band; events above and below it, flags on it */
  .amt{--amt-c:var(--accent,#7c6cf0);border-radius:12px;border:1px solid color-mix(in srgb,var(--text) 20%,transparent);
    -webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);}
  .amt-body,.amt-wrap{position:relative;}
  .amt .adt-scroll{cursor:grab;-webkit-overflow-scrolling:touch;scrollbar-width:thin;}
  .amt .adt-scroll.pan{cursor:grabbing;user-select:none;-webkit-user-select:none;}
  .amt-stage{position:relative;display:block;min-width:100%;min-height:120px;box-sizing:border-box;}
  .amt-lines{position:absolute;left:0;top:0;overflow:visible;pointer-events:none;z-index:0;}
  .amt-axis{fill:none;stroke:color-mix(in srgb,var(--text) 50%,transparent);stroke-width:1.5;stroke-linecap:round;}
  .amt-tick{stroke:color-mix(in srgb,var(--text) 38%,transparent);stroke-width:1;}
  .amt-tl{fill:color-mix(in srgb,var(--text) 55%,transparent);font-size:9.5px;font-variant-numeric:tabular-nums;text-anchor:middle;}
  .amt-dot{fill:var(--amt-dc,var(--text));stroke:var(--bg,var(--surface));stroke-width:1.5;}
  .amt-con{fill:none;stroke:color-mix(in srgb,var(--text) 34%,transparent);stroke-width:1;stroke-linecap:round;}
  .amt-pole{stroke:var(--amt-fc,var(--amt-c));stroke-width:1.5;opacity:.5;}
  .amt-era{fill:var(--amt-fc,var(--amt-c));opacity:.4;}
  .amt-i{position:absolute;z-index:2;box-sizing:border-box;}
  .amt-ev{width:150px;padding:6px 9px 7px;border-radius:9px;text-align:left;background:var(--card-glass-bg,var(--surface));
    border:1px solid var(--border);box-shadow:0 3px 10px var(--node-rest-shadow,rgba(0,0,0,.08));}
  .amt-ev .adt-t{font-size:12px;line-height:1.3;font-weight:650;}
  .amt-ev .adt-x{font-size:11px;line-height:1.35;margin-top:3px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}
  .amt-ev .adt-tag{font-size:9px;margin-bottom:2px;}
  .amt-ev .adt-foot{margin-top:5px;}
  .amt-ev .adt-chip{font-size:10px;padding:3px 6px;}
  .amt-flag .adt-t,.amt-box .adt-t{font-size:inherit;font-weight:inherit;line-height:inherit;display:inline;}
  .amt-box .adt-t{font-weight:400;}
  .amt-when{font-size:10px;font-weight:700;letter-spacing:.04em;color:var(--muted);font-variant-numeric:tabular-nums;margin-bottom:2px;}
  .amt-ev:focus-visible,.amt-chip:focus-visible,.amt-box:focus-visible,.amt-flag:focus-visible{outline:2px solid var(--accent,#7c6cf0);outline-offset:2px;}
  .amt-box{max-width:150px;padding:3px 9px;border-radius:6px;font-size:11px;line-height:1.3;color:color-mix(in srgb,var(--text) 75%,transparent);
    border:1px dashed color-mix(in srgb,var(--text) 40%,transparent);background:color-mix(in srgb,var(--bg,var(--surface)) 80%,transparent);}
  .amt-box .amt-when{margin:0 0 1px;}
  .amt-flag{white-space:nowrap;max-width:200px;overflow:hidden;text-overflow:ellipsis;padding:2px 9px 2px 8px;border-radius:0 5px 5px 0;font-size:11px;font-weight:700;
    letter-spacing:.02em;color:var(--text);background:color-mix(in srgb,var(--amt-fc,var(--amt-c)) 14%,var(--surface));
    border:1px solid color-mix(in srgb,var(--amt-fc,var(--amt-c)) 50%,transparent);border-left:3px solid var(--amt-fc,var(--amt-c));}
  .amt-nav{position:absolute;top:50%;z-index:5;width:26px;height:26px;margin-top:-13px;padding:0;border-radius:50%;border:1px solid var(--border);
    background:var(--bg,var(--surface));color:var(--text);font:inherit;font-size:16px;line-height:24px;text-align:center;cursor:pointer;opacity:0;pointer-events:none;transition:opacity .2s;}
  .amt-nav.l{left:6px;} .amt-nav.r{right:6px;}
  .amt-nav.on{opacity:.9;pointer-events:auto;}
  .amt-fade{position:absolute;top:0;bottom:0;width:46px;z-index:4;pointer-events:none;opacity:0;transition:opacity .2s;}
  .amt-fade.l{left:0;background:linear-gradient(90deg,var(--bg,var(--surface)) 55%,transparent);}
  .amt-fade.r{right:0;background:linear-gradient(270deg,var(--bg,var(--surface)) 55%,transparent);}
  .amt-fade.on{opacity:.9;}
  /* chips: the phone's (and a narrow band's) single row */
  .amt-row{position:relative;display:flex;align-items:center;gap:8px;padding:18px 14px;min-height:96px;box-sizing:border-box;width:max-content;min-width:100%;}
  .amt-row::before{content:"";position:absolute;left:0;right:0;top:50%;height:0;border-top:1.5px solid color-mix(in srgb,var(--text) 40%,transparent);}
  .amt-chip{position:relative;flex:none;display:inline-flex;align-items:center;gap:6px;max-width:190px;padding:7px 11px;border-radius:999px;font-size:12px;line-height:1.2;
    background:var(--card-glass-bg,var(--surface));border:1px solid var(--border);color:var(--text);cursor:pointer;-webkit-tap-highlight-color:transparent;}
  .amt-chip .amt-g{flex:none;font-size:11px;color:var(--amt-dc,var(--text));}
  .amt-chip .adt-t{font-weight:650;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0;}
  .amt-chip .amt-when{margin:0;white-space:nowrap;}
  .amt-chip.sel{border-color:var(--accent,#7c6cf0);box-shadow:0 0 0 2px color-mix(in srgb,var(--accent,#7c6cf0) 35%,transparent);}
  .amt-chip.f{border-radius:0 999px 999px 0;border-left:3px solid var(--amt-fc,var(--amt-c));}
  .amt-chip.b{border-style:dashed;border-radius:8px;}
  .amt .adt-panel .amt-when{font-size:11px;margin-bottom:4px;}
  .amt-i.tone-green,.amt-chip.tone-green{--amt-dc:#16a34a;--amt-fc:#16a34a;} .amt-i.tone-red,.amt-chip.tone-red{--amt-dc:#dc2626;--amt-fc:#dc2626;}
  .amt-i.tone-amber,.amt-chip.tone-amber{--amt-dc:#d97706;--amt-fc:#d97706;} .amt-i.tone-blue,.amt-chip.tone-blue{--amt-dc:#2563eb;--amt-fc:#2563eb;}
  .amt-i.tone-violet,.amt-chip.tone-violet{--amt-dc:#7c3aed;--amt-fc:#7c3aed;} .amt-i.tone-gray,.amt-chip.tone-gray{--amt-dc:#64748b;--amt-fc:#64748b;}
  html.dark .amt-i.tone-green,html.dark .amt-chip.tone-green{--amt-dc:#4ade80;--amt-fc:#4ade80;} html.dark .amt-i.tone-red,html.dark .amt-chip.tone-red{--amt-dc:#f87171;--amt-fc:#f87171;}
  html.dark .amt-i.tone-amber,html.dark .amt-chip.tone-amber{--amt-dc:#fbbf24;--amt-fc:#fbbf24;} html.dark .amt-i.tone-blue,html.dark .amt-chip.tone-blue{--amt-dc:#60a5fa;--amt-fc:#60a5fa;}
  html.dark .amt-i.tone-violet,html.dark .amt-chip.tone-violet{--amt-dc:#a78bfa;--amt-fc:#a78bfa;} html.dark .amt-i.tone-gray,html.dark .amt-chip.tone-gray{--amt-dc:#94a3b8;--amt-fc:#94a3b8;}
  .amt-i.sel.amt-ev{border-color:var(--accent,#7c6cf0);box-shadow:0 0 0 2px color-mix(in srgb,var(--accent,#7c6cf0) 35%,transparent);}
  html.mobile .amt{margin-left:-4px;margin-right:-4px;}
  @media print{.amt-nav,.amt-fade{display:none;} .amt .adt-scroll{overflow:visible;}}
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
  // ── the mini timeline (layout "timeline"): events along a horizontal axis ──
  function pageName(l){
    try{
      if(l[0] === 'node'){ var nn = (typeof NODES_SRC !== 'undefined' ? NODES_SRC : (typeof NODES !== 'undefined' ? NODES : [])).filter(function(x){ return x.id === l[1]; })[0];
        return nn ? (window._altoNodeName ? window._altoNodeName(nn) : nn.title) : 'Open page'; }
      var M = l[0] === 'char' ? (typeof CHARS !== 'undefined' && CHARS) : l[0] === 'env' ? (typeof ENVS !== 'undefined' && ENVS) : (typeof THEMES !== 'undefined' && THEMES);
      var v = M && M[l[1]]; return v && v.name ? String(v.name).replace(/<[^>]*>/g, '') : 'Open page';
    }catch(e){ return 'Open page'; }
  }
  function place(slot, box){
    var p = slot.parentNode, host = p && p.tagName === 'P' ? p : null;
    if(host && host.parentNode){ host.parentNode.insertBefore(box, host.nextSibling); slot.parentNode.removeChild(slot);
      if(!host.textContent.trim() && !host.querySelector('img,svg')) host.parentNode.removeChild(host); }
    else slot.parentNode.replaceChild(box, slot);
  }
  function niceTick(raw){ var e = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10)), f = raw / e; return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * e; }
  function whenLabel(v, step){ if(v < 0) return Math.abs(Math.round(v)) + ' BC'; return step >= 1 ? String(Math.round(v)) : String(Math.round(v * 10) / 10); }
  function renderTL(slot, key, T){
    var byId = {}; T.n.forEach(function(n){ byId[n.i] = n; });
    var evs = T.n.filter(function(n){ return n.k !== 'f'; }), flags = T.n.filter(function(n){ return n.k === 'f'; });
    var box = el('div', 'adt amt' + (T.open ? '' : ' shut')); box.setAttribute('data-adt-key', key);
    var bar = el('div', 'adt-bar');
    bar.appendChild(el('span', 'adt-name', T.label || 'Timeline'));
    var nEv = T.n.filter(function(n){ return n.k !== 'f' && n.k !== 'b'; }).length;
    bar.appendChild(el('span', 'adt-meta', nEv + (nEv === 1 ? ' event' : ' events') + (flags.length ? ' · ' + flags.length + (flags.length === 1 ? ' flag' : ' flags') : '')));
    bar.appendChild(el('span', 'adt-sp'));
    var bShut = el('button', 'adt-btn'); bShut.type = 'button'; bar.appendChild(bShut);
    var body = el('div', 'adt-body amt-body'), scroll = el('div', 'adt-scroll'), stage = el('div', 'adt-stage amt-stage');
    var svg = document.createElementNS(SVGNS, 'svg'); svg.setAttribute('class', 'adt-lines amt-lines');
    var panel = el('div', 'adt-panel'); panel.hidden = true;
    var navL = el('button', 'amt-nav l', '‹'), navR = el('button', 'amt-nav r', '›'), fadeL = el('div', 'amt-fade l'), fadeR = el('div', 'amt-fade r');
    navL.type = navR.type = 'button'; navL.setAttribute('aria-label', 'Scroll left'); navR.setAttribute('aria-label', 'Scroll right');
    var wrap = el('div', 'amt-wrap'); scroll.appendChild(stage); wrap.appendChild(scroll); wrap.appendChild(fadeL); wrap.appendChild(fadeR); wrap.appendChild(navL); wrap.appendChild(navR);
    body.appendChild(wrap); body.appendChild(panel);
    box.appendChild(bar); box.appendChild(body);

    var els = {}, mode = null, openId = null;
    function hasMore(n){ return !!(n.s || n.l); }
    function tone(n){ return n.c ? ' tone-' + n.c : ''; }
    function whenEl(n){ var w = n.w ? n.w + (n.z ? ' – ' + n.z : '') : ''; return w ? el('div', 'amt-when', w) : null; }
    function build(m){
      mode = m; els = {}; while(stage.firstChild) stage.removeChild(stage.firstChild);
      if(m === 'chips'){
        var row = el('div', 'amt-row'); stage.appendChild(row);
        T.n.forEach(function(n){
          var c = el('div', 'amt-chip amt-i ' + (n.k || 'e') + tone(n)); c.setAttribute('data-i', n.i); c.tabIndex = 0; c.setAttribute('role', 'button');
          c.appendChild(el('span', 'amt-g', n.k === 'f' ? '⚑' : n.k === 'b' ? '▭' : '●'));
          c.appendChild(el('span', 'adt-t', n.t));
          if(n.w) c.appendChild(el('span', 'amt-when', n.w));
          row.appendChild(c); els[n.i] = c;
        });
        return;
      }
      stage.appendChild(svg);
      T.n.forEach(function(n){
        var c;
        if(n.k === 'f'){ c = el('div', 'amt-i amt-flag' + tone(n)); c.appendChild(el('span', 'adt-t', n.t)); c.title = (n.w || '') + (n.z ? ' – ' + n.z : ''); }
        else if(n.k === 'b'){ c = el('div', 'amt-i amt-box' + tone(n)); var bw = whenEl(n); if(bw) c.appendChild(bw); c.appendChild(el('div', 'adt-t', n.t)); }
        else {
          c = el('div', 'adt-card amt-i amt-ev' + tone(n) + (hasMore(n) ? ' go' : ''));
          var w = whenEl(n); if(w) c.appendChild(w);
          if(n.g) c.appendChild(el('div', 'adt-tag', n.g));
          c.appendChild(el('div', 'adt-t', n.t));
          if(n.x) c.appendChild(el('div', 'adt-x', n.x));
          var foot = el('div', 'adt-foot');
          if(n.s) foot.appendChild(el('span', 'adt-chip adt-more', 'More ›'));
          if(n.l){ var lc = el('span', 'adt-chip adt-link', '↗ ' + pageName(n.l)); lc.setAttribute('data-go', '1'); foot.appendChild(lc); }
          c.appendChild(foot);
        }
        c.setAttribute('data-i', n.i); c.tabIndex = 0; if(hasMore(n)) c.setAttribute('role', 'button');
        stage.appendChild(c); els[n.i] = c;
      });
    }
    function pos(e){ var x = 0, y = 0; while(e && e !== stage){ x += e.offsetLeft; y += e.offsetTop; e = e.offsetParent; } return [x, y]; }
    function mk(tag, attrs){ var e = document.createElementNS(SVGNS, tag); for(var k in attrs) e.setAttribute(k, attrs[k]); return e; }
    function layoutCards(){
      var w = scroll.clientWidth || box.clientWidth, CW = 150, PAD = CW / 2 + 16, GAP = 12, STEP = CW * 0.62;
      var dated = evs.filter(function(n){ return n.v != null; }), all = [];
      T.n.forEach(function(n){ if(n.v != null) all.push(n.v); if(n.u != null) all.push(n.u); });
      var scaled = dated.length >= 2, mn = Math.min.apply(null, all), mx = Math.max.apply(null, all), span = (mx - mn) || 1;
      var L = Math.max(w - 2 * PAD, Math.max(1, evs.length - 1) * STEP);
      var xOf = function(v){ return PAD + (v - mn) / span * L; };
      var X = {};
      if(scaled){
        evs.forEach(function(n){ if(n.v != null) X[n.i] = xOf(n.v); });
        evs.forEach(function(n, k){
          if(X[n.i] != null) return;
          var a = k - 1, b = k + 1;
          while(a >= 0 && X[evs[a].i] == null) a--;
          while(b < evs.length && X[evs[b].i] == null) b++;
          if(a >= 0 && b < evs.length) X[n.i] = X[evs[a].i] + (X[evs[b].i] - X[evs[a].i]) * (k - a) / (b - a);
          else if(a >= 0) X[n.i] = X[evs[a].i] + STEP * (k - a);
          else X[n.i] = X[evs[b].i] - STEP * (b - k);
        });
      } else {
        var st = evs.length > 1 ? Math.max(STEP, (w - 2 * PAD) / (evs.length - 1)) : 0;
        evs.forEach(function(n, k){ X[n.i] = PAD + k * st; });
      }
      var minX = Math.min.apply(null, evs.map(function(n){ return X[n.i]; }).concat([PAD])), shift = Math.max(0, PAD - minX);
      if(shift){ for(var q in X) X[q] += shift; }
      var fx = function(n){ if(scaled && n.v != null) return xOf(n.v) + shift;
        var m = evs.filter(function(e){ return e.w && e.w === n.w; })[0]; return m ? X[m.i] : PAD; };
      // lanes: alternating, unless an event says which side; the card slides right of its neighbour in the lane
      var lane = {}, alt = 0, last = {0: -1e9, 1: -1e9}, C = {};
      evs.forEach(function(n){ var l = n.d === 'above' ? 0 : n.d === 'below' ? 1 : (alt++ % 2); lane[n.i] = l; });
      evs.forEach(function(n){ var l = lane[n.i], cx = Math.max(X[n.i], CW / 2 + 8, last[l] + CW + GAP); last[l] = cx; C[n.i] = cx; });
      var aboveH = 0, belowH = 0, H = {};
      evs.forEach(function(n){ var c = els[n.i]; c.style.width = CW + 'px'; c.style.left = (C[n.i] - CW / 2) + 'px'; c.style.top = '0px'; H[n.i] = c.offsetHeight;
        if(lane[n.i]) belowH = Math.max(belowH, H[n.i]); else aboveH = Math.max(aboveH, H[n.i]); });
      // flags on the axis: rows, so two that overlap stand one over the other
      var rows = [], FH = 22, F = {};
      flags.slice().sort(function(a, b){ return fx(a) - fx(b); }).forEach(function(n){
        var c = els[n.i], x0 = fx(n), x1 = n.u != null && scaled ? xOf(n.u) + shift : x0, r = 0, wd = c.offsetWidth + 6;
        while(rows[r] != null && rows[r] > x0 - 4) r++;
        rows[r] = x0 + wd; F[n.i] = {x: x0, r: r, x1: x1};
      });
      var top = 12, yAxis = top + (aboveH ? aboveH + 22 : 0) + rows.length * (FH + 4) + (rows.length ? 8 : 4) + 10, belowTop = yAxis + 30;
      var totalW = w;
      evs.forEach(function(n){
        var c = els[n.i], h = H[n.i]; c.style.top = (lane[n.i] ? belowTop : top + aboveH - h) + 'px'; totalW = Math.max(totalW, C[n.i] + CW / 2 + 16);
      });
      flags.forEach(function(n){ var c = els[n.i], f = F[n.i]; c.style.left = f.x + 'px'; c.style.top = (yAxis - 8 - f.r * (FH + 4) - FH) + 'px';
        totalW = Math.max(totalW, f.x + c.offsetWidth + 16, f.x1 + 16); });
      var stageH = Math.max(120, belowTop + belowH + 14);
      stage.style.width = totalW + 'px'; stage.style.height = stageH + 'px';
      svg.setAttribute('width', totalW); svg.setAttribute('height', stageH);
      while(svg.firstChild) svg.removeChild(svg.firstChild);
      svg.appendChild(mk('path', {'class': 'amt-axis', d: 'M12 ' + yAxis + ' H' + (totalW - 12)}));
      if(scaled){
        var tstep = niceTick(span / Math.max(2, L / 110));
        for(var tv = Math.ceil(mn / tstep) * tstep; tv <= mx + 1e-9; tv += tstep){
          var tx = xOf(tv) + shift;
          if(evs.some(function(n){ return Math.abs(X[n.i] - tx) < 14; })) continue;       // a connector runs through it: no label
          svg.appendChild(mk('path', {'class': 'amt-tick', d: 'M' + tx + ' ' + (yAxis - 4) + ' V' + (yAxis + 4)}));
          var tl = mk('text', {'class': 'amt-tl', x: tx, y: yAxis + 16}); tl.textContent = whenLabel(tv, tstep); svg.appendChild(tl);
        }
      }
      flags.forEach(function(n){ var f = F[n.i], c = els[n.i], g = mk('g', {'class': 'amt-fl'}), col = getComputedStyle(c).getPropertyValue('--amt-fc');
        if(col) g.setAttribute('style', '--amt-fc:' + col);
        if(f.x1 > f.x + 2) g.appendChild(mk('rect', {'class': 'amt-era', x: f.x, y: yAxis - 3, width: f.x1 - f.x, height: 6, rx: 3}));
        g.appendChild(mk('path', {'class': 'amt-pole', d: 'M' + f.x + ' ' + yAxis + ' V' + (yAxis - 8 - f.r * (FH + 4))}));
        svg.appendChild(g); });
      evs.forEach(function(n){
        var x = X[n.i], cx = C[n.i], c = els[n.i], up = !lane[n.i], y1 = up ? yAxis - 5 : yAxis + 5,
            y2 = up ? top + aboveH : belowTop, d;
        if(Math.abs(cx - x) < 1) d = 'M' + x + ' ' + y1 + ' V' + y2;
        else { var my = (y1 + y2) / 2, r = Math.min(8, Math.abs(cx - x) / 2, Math.abs(y2 - y1) / 4), sg = cx > x ? 1 : -1, dy = up ? -1 : 1;
          d = 'M' + x + ' ' + y1 + ' V' + (my - dy * r) + ' Q' + x + ' ' + my + ' ' + (x + sg * r) + ' ' + my + ' H' + (cx - sg * r)
            + ' Q' + cx + ' ' + my + ' ' + cx + ' ' + (my + dy * r) + ' V' + y2; }
        svg.appendChild(mk('path', {'class': 'amt-con', d: d}));
        var dot = mk('circle', {'class': 'amt-dot', cx: x, cy: yAxis, r: n.k === 'b' ? 2.5 : 4.2});
        var col = getComputedStyle(c).getPropertyValue('--amt-dc'); if(col) dot.setAttribute('style', '--amt-dc:' + col);
        svg.appendChild(dot);
      });
    }
    function wantChips(){ return mobile() || (scroll.clientWidth || box.clientWidth) < 520; }
    function layout(){
      if(box.classList.contains('shut') || !stage.offsetParent) return;
      var m = wantChips() ? 'chips' : 'cards';
      if(m !== mode){ closePanel(); build(m); }
      if(mode === 'cards') layoutCards(); else { stage.style.width = ''; stage.style.height = ''; }
      hint();
    }
    function hint(){
      var max = scroll.scrollWidth - scroll.clientWidth, x = scroll.scrollLeft, l = max > 4 && x > 2, r = max > 4 && x < max - 2;
      fadeL.classList.toggle('on', l); navL.classList.toggle('on', l); fadeR.classList.toggle('on', r); navR.classList.toggle('on', r);
    }
    scroll.addEventListener('scroll', hint, {passive: true});
    navL.onclick = function(){ scroll.scrollBy({left: -scroll.clientWidth * 0.7, behavior: 'smooth'}); };
    navR.onclick = function(){ scroll.scrollBy({left: scroll.clientWidth * 0.7, behavior: 'smooth'}); };

    // ── an item's own words, under the band ──
    function closePanel(){ panel.hidden = true; panel.innerHTML = ''; if(openId && els[openId]) els[openId].classList.remove('sel'); openId = null; }
    function openPanel(id){
      var n = byId[id]; if(!n) return; if(openId === id){ closePanel(); return; }
      closePanel(); openId = id; els[id].classList.add('sel');
      var head = el('div', 'adt-ph'), hd = el('div');
      var w = whenEl(n); if(w) hd.appendChild(w);
      if(n.g) hd.appendChild(el('div', 'adt-tag', n.g));
      hd.appendChild(el('div', 'adt-pt', n.t)); head.appendChild(hd);
      var x = el('button', 'adt-btn', 'Close'); x.type = 'button'; x.onclick = closePanel; head.appendChild(x);
      panel.appendChild(head);
      if(n.x) panel.appendChild(el('div', 'adt-x', n.x));
      (n.s || []).forEach(function(s){
        var wv = el('div', 'adt-ps'); if(s.h) wv.appendChild(el('h4', '', s.h));
        var t = el('div'); t.innerHTML = s.t; wv.appendChild(t); panel.appendChild(wv);
      });
      if(n.l){ var go = el('button', 'adt-btn adt-open', '↗ Open ' + pageName(n.l)); go.type = 'button';
        go.onclick = function(){ window.showDetail(n.l[0], n.l[1]); }; panel.appendChild(go); }
      panel.hidden = false;
      try{ panel.scrollIntoView({block: 'nearest', behavior: 'smooth'}); }catch(e){}
    }
    function opens(n){ return mode === 'chips' ? !!(n.x || n.s || n.l || n.w) : hasMore(n); }
    box.addEventListener('click', function(e){
      var t = e.target;
      if(scroll._moved){ scroll._moved = 0; e.stopPropagation(); e.preventDefault(); return; }
      var sel = window.getSelection && String(window.getSelection() || '');
      if(sel && sel.trim().length > 1 && !t.closest('button')) return;
      if(t.closest('.amt-nav')) return;
      if(t.closest('.adt-bar') && box.classList.contains('shut') && !t.closest('button')){ shut(false); return; }
      var it = t.closest('.amt-i'); if(!it) return;
      var n = byId[it.getAttribute('data-i')]; if(!n) return;
      if(t.closest('[data-go]') && n.l){ window.showDetail(n.l[0], n.l[1]); return; }
      if(mode === 'cards' && !n.s && n.l){ window.showDetail(n.l[0], n.l[1]); return; }
      if(opens(n)) openPanel(n.i);
    });
    box.addEventListener('keydown', function(e){
      var it = e.target.closest && e.target.closest('.amt-i'); if(!it || e.target.isContentEditable) return;
      if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); it.click(); return; }
      if(e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
      var ids = T.n.filter(function(n){ return els[n.i]; }).map(function(n){ return n.i; }), k = ids.indexOf(it.getAttribute('data-i')) + (e.key === 'ArrowRight' ? 1 : -1);
      if(k < 0 || k >= ids.length) return;
      e.preventDefault(); e.stopPropagation();           // (the page's own arrows go to the next card)
      var nx = els[ids[k]]; nx.focus();
      var a = pos(nx)[0], b = a + nx.offsetWidth; if(a < scroll.scrollLeft + 10 || b > scroll.scrollLeft + scroll.clientWidth - 10) scroll.scrollLeft = Math.max(0, a - 40);
    });
    // drag to pan (a mouse; a finger scrolls by itself), never the page's own scroll
    var drag = null;
    scroll.addEventListener('mousedown', function(e){
      if(e.button || document.documentElement.classList.contains('alto-editing') || e.target.closest('button,a,[contenteditable="true"]')) return;
      drag = {x: e.clientX, l: scroll.scrollLeft, on: false};
    });
    window.addEventListener('mousemove', function(e){
      if(!drag) return; var dx = e.clientX - drag.x;
      if(!drag.on && Math.abs(dx) > 4){ drag.on = true; scroll.classList.add('pan'); }
      if(drag.on) scroll.scrollLeft = drag.l - dx;
    });
    window.addEventListener('mouseup', function(){ if(!drag) return; if(drag.on){ scroll._moved = 1; setTimeout(function(){ scroll._moved = 0; }, 0); } scroll.classList.remove('pan'); drag = null; });
    function shut(v){ box.classList.toggle('shut', v); bShut.textContent = v ? 'Show' : 'Hide'; if(!v) requestAnimationFrame(layout); }
    bShut.onclick = function(e){ e.stopPropagation(); shut(!box.classList.contains('shut')); };
    bShut.textContent = T.open ? 'Hide' : 'Show';
    box.addEventListener('amt-relayout', function(){ if(document.contains(box)) layout(); });
    build('cards');
    place(slot, box);
    if(window.ResizeObserver){ var raf = 0, ro = new ResizeObserver(function(){ if(!document.contains(box)){ ro.disconnect(); return; } if(raf) return; raf = requestAnimationFrame(function(){ raf = 0; layout(); }); }); ro.observe(scroll); }
    requestAnimationFrame(layout);
    if(document.fonts && document.fonts.ready) document.fonts.ready.then(function(){ if(document.contains(box)) layout(); });
  }
  function render(slot){
    var key = slot.getAttribute('data-adt'), T = D[key];
    if(!T || !T.n || !T.n.length){ slot.removeAttribute('data-adt'); return; }
    if(T.lay === 'timeline') return renderTL(slot, key, T);
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
