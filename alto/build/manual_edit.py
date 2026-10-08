"""Manual edit mode: the owner changes a timeline's words, labels and links,
and moves an outline's cards, in the page itself.

Nothing changes until the owner enters edit mode (the "Edit manually" half of
the Edit tile, on the timeline or at the foot of any page). Each change is a
small record, "this field was X and is now Y", kept in localStorage and in the
owner's account (users/{uid}/edits/{tid}, alto-cloud.js getEdits/putEdits).
Every page load lays the records over the page's own data — but only where the
page still shows X, so a record can never overwrite a newer version of the
same field. The connector folds the records into the draft (alto/edits.py),
and once the rebuilt page carries them they are marked done.

Field keys ("|"-separated; ids are slugs):
  n|<id>|title  tag  desc                 a card
  n|<id>|s|<i>|h  t                       its page's own section i (heading, text)
  c|<id>|name  role   c|<id>|s|<i>|h  t   an entity page
  env|… theme|…                           an axis value's page (axis 1, axis 2)
  u|<i>|label                             a unit's name
  bt|title                                the timeline's own name (the title bar; Brief.title)
  dt|<tree key>|<step>|title  text  edge  a decision-tree step (subtree.py)
  p|<id>|shift                            a card dragged on an outline, [dx, dy]
  p|<id>|slide                            a card slid along its own line, [dx, dy] (it alone)
  n|<id>|order  n|<id>|s|new-…|h t p      a page's own sections, new ones (p: their kind)
  dt|<owner>-new-…|tree                   a new section's decision tree
  sd|<study key>|study                    a section's flash cards or quiz, whole (study.py; study_edit.py)
  sd|<owner>-new-…|study                  a new section's flash cards or quiz
  nn|card-…   nd|<id>                     a card added here / a built card taken out
  fl|list   fn|<id>   fx|off              the owner's filters, a card's, the ones taken out
  nu|unit-…   nl|unit-…                   a unit added here, its name
  rp|<id>                                 a card (and its progeny) moved under another card
  so|<parent>                             the order of a card's children, [ids]
  sx|<id>                                 a card that traded places with its parent (the value)
  ch|<id>|chars  envs  themes             a card's sub-chips
  ne|c|<id>  ne|env|<id>  ne|theme|<id>   a chip made here (an entity, an axis value). An axis
                                          value is a case / statute / Restatement section: its v is
                                          {name, color?, svg?, cite?, h?, t?, link?, grp?} — citation,
                                          a note under the heading its sisters use, a link, the Index
                                          list it joins (EDK.ix) — folded into cite, sections, group.
  <section>|t of a list section (Cases, Authorities, Sources…)  its <li> entries: added, removed,
                                          moved on the page as one change of the section's words.
A section's `i` is its index among the object's OWN sections (the page also
carries ones the build adds); _ALTO_EDK maps the page's list to it. A link to a
file on the owner's computer is <a data-file="file-…">: the file itself (or,
in Chromium, its place on disk) stays in this browser's IndexedDB, and the
connector finds it by name to record its path (edits.find_file).

A drag lays the whole tree out again with the card where it is held
(TREE_GLUE _altoTreeCalc), so the cards it lands on step aside
(layout.make_room) and go back once it moves on; no two cards are left
touching (layout.separate). Held close to its own line (the one from its
parent), a card slides along it alone (slide); taken off it, the cards under
it come along (shift).

Desktop: everything. Phones: text on the page being read (no dragging, no
cards, filters or sections to add, no Claude half). Shares and copies opened from disk never offer it.
"""
from __future__ import annotations

import json

from .sanitize import js_json


def jhash(s: str) -> str:
    """djb2 over UTF-16 code units, as hex — the page's jh(): the signature of
    what a structural edit was made against (MANUAL_JS, alto/edits.py)."""
    h = 5381
    b = str(s).encode("utf-16-le", "surrogatepass")
    for i in range(0, len(b), 2):
        h = ((h << 5) + h + (b[i] | (b[i + 1] << 8))) & 0xFFFFFFFF
    return format(h, "x")


def edit_keys(b, nodes=()) -> str:
    """_ALTO_EDK: each page's section list → the object's own section index
    (-1 / -2 for the build's own, ahead of / after them), and what the page's
    Overview is made of: an authored one (its signature) or one composed from
    the units (which heading each shows, and each unit's own summary)."""
    edk = dict(getattr(b, "_alto_edk", None) or {})
    if b.overview_html:
        edk["ov"] = "authored"
        edk["ovh"] = jhash(b.overview_html)
    elif b.mode == "outline":
        acts = [i for i, a in enumerate(b.acts)
                if any(n.act == i and not n.parent for n in nodes)]
        edk["ov"] = "composed"
        edk["ova"] = acts
        edk["ovf"] = {i: ("label" if b.acts[i].label and not b.acts[i].label.isupper()
                          or not b.acts[i].short else "short") for i in acts}
        edk["us"] = {i: b.acts[i].summary or "" for i in acts}
        edk["sh"] = {i: b.acts[i].short or "" for i in acts}
    # Filters: the owner's own (flags, and which cards carry each), the ones
    # taken out of the panel, and — when some are out — the whole set, so one
    # can be put back. Cards: what a new one is made like.
    edk["fl"] = [{"id": f["id"], "name": f.get("name") or f["id"]}
                 | ({"color": f["color"]} if f.get("color") else {})
                 for f in b.flags if isinstance(f, dict) and f.get("id")]
    edk["fln"] = {n.id: list(n.flags) for n in nodes if n.flags}
    edk["foff"] = list(b.filters_off or [])
    fa = getattr(b, "_alto_filters", None) or {}
    if fa.get("slot"):
        edk["fslot"] = fa["slot"]
    if b.filters_off and fa:
        edk["fall"] = {"sections": fa.get("sections") or [], "nodes": fa.get("nodes") or {}}
    edk["mode"] = b.mode
    edk["noun"] = b.node_noun or "Card"
    # Units: the ones added in a page carry that page's id for them. Chips: the
    # kinds a card shows (the build's own order), what each is called.
    edk["uids"] = [getattr(a, "id", "") or "" for a in b.acts]
    nav = getattr(b, "_alto_navrep", set())
    kinds = [{"f": "chars", "r": "c", "l": b.entity_axis_label or "Characters",
              "one": b.entity_axis_singular or "Character"}]
    for j, (key, f, r) in enumerate((("axis1", "envs", "env"), ("axis2", "themes", "theme"))):
        if j < len(b.axes) and key not in nav:
            ax = b.axes[j]
            kinds.append({"f": f, "r": r, "l": ax.label, "one": ax.singular,
                          "fk": key} | ({"hide": 1} if ax.hide_nav else {}))
    kinds[0]["fk"] = "entity"
    edk["chipk"] = kinds
    edk["nax"] = len(b.axes)
    # The Index pages (a hide_nav axis, or a group of its values): which kind
    # of chip each lists and the group a value added there joins ("" = none).
    from .detail_extras import index_entries
    ix = {}
    for key, kind, label, ids in index_entries([(k, ax) for k, ax in (("env", b.axes[0] if b.axes else None),
                                                                      ("theme", b.axes[1] if len(b.axes) > 1 else None))
                                                if ax and ax.hide_nav]):
        v0 = next((v for ax in b.axes[:2] for v in ax.values if v.id in ids), None)
        ix[key] = {"r": kind, "g": (v0.group if v0 else "") or "", "l": label}
    edk["ix"] = ix
    edk["sz"] = {k: v for k, v in (b.card_size or {}).items() if isinstance(v, dict)}
    from .glyphs import LIBRARY
    edk["glyphs"] = LIBRARY
    from .blocks import FALLBACK_GLYPH
    edk["glyph"] = FALLBACK_GLYPH
    data = js_json(edk, separators=(",", ":"))
    return f'<script id="alto-edk">window._ALTO_EDK={data};</script>\n'


def manual_edit(b, nodes=()) -> str:
    from .study_edit import STUDY_EDIT_CSS, STUDY_EDIT_FIELD, STUDY_EDIT_DECORATE, STUDY_EDIT_JS
    js = (MANUAL_JS.replace("/*__STUDY_FIELD__*/", STUDY_EDIT_FIELD)
          .replace("/*__STUDY_DECORATE__*/", STUDY_EDIT_DECORATE)
          .replace("/*__STUDY_EDIT__*/", STUDY_EDIT_JS))
    css = MANUAL_CSS[:MANUAL_CSS.rindex("</style>")] + STUDY_EDIT_CSS + "\n</style>"
    return edit_keys(b, nodes) + css + "\n" + js + "\n"


# How a linked file is shown (MANUAL_JS openFile). A Claude preview may not
# download through a page (single_file.preview, ALTO-016): it swaps this out.
SHOW_BLOB = """  function showBlob(file, name, w){
    var u = URL.createObjectURL(file);
    if(w) w.location.href = u;
    else { var a = document.createElement('a'); a.href = u; a.download = name; document.body.appendChild(a); a.click(); a.remove(); }
    setTimeout(function(){ URL.revokeObjectURL(u); }, 120000);
  }
"""
SHOW_BLOB_PREVIEW = """  function showBlob(file, name, w){ if(w) w.close(); }
"""


MANUAL_CSS = r"""<style id="alto-manual-css">
  /* the edit toggle: a split pill in the corner, where light/dark used to be — build with
     Claude on the left, edit by hand on the right. On a phone, a pencil-only
     pill at the foot of a page. While editing, the editing bar takes its place. */
  #alto-edit-pill{position:fixed;bottom:30px;right:30px;z-index:310;height:35px;display:inline-flex;align-items:stretch;
    border-radius:17.5px;background:var(--card-glass-bg);border:1px solid var(--card-glass-border);color:var(--muted);
    -webkit-backdrop-filter:blur(18px) saturate(190%) brightness(var(--card-glass-bright));backdrop-filter:blur(18px) saturate(190%) brightness(var(--card-glass-bright));
    box-shadow:0 10px 26px var(--node-rest-shadow),inset 0 0 0 .5px var(--card-glass-rim);}
  #alto-edit-pill:hover{border-color:var(--muted);}
  .alto-edit-pill .aep-half{position:relative;display:flex;align-items:center;justify-content:center;gap:8px;min-width:48px;padding:0 14px;border:0;
    background:none;color:inherit;font:inherit;font-size:15px;letter-spacing:.05em;cursor:pointer;-webkit-tap-highlight-color:transparent;}
  #alto-edit-pill .aep-claude{border-radius:17.5px 0 0 17.5px;padding:0 12px 0 15px;}
  #alto-edit-pill .aep-manual{border-radius:0 17.5px 17.5px 0;padding:0 15px 0 12px;}
  .alto-edit-pill .aep-half:hover,.alto-edit-pill .aep-half:focus-visible{color:var(--text);background:color-mix(in srgb,var(--text) 7%,transparent);outline:none;}
  .alto-edit-pill .aep-half.off{opacity:.4;cursor:default;}
  .alto-edit-pill .aep-half svg{display:block;}
  .alto-edit-pill .aep-pen{font-size:19px;line-height:1;font-weight:300;}
  .alto-edit-pill .aep-div{width:1px;margin:8px 0;background:color-mix(in srgb,var(--muted) 45%,transparent);}
  #alto-edit-pill .aep-half::after{content:attr(data-tip);position:absolute;bottom:calc(100% + 10px);left:50%;transform:translateX(-50%);
    padding:5px 10px;border-radius:8px;background:var(--surface);color:var(--text);border:1px solid var(--border);font-size:12px;letter-spacing:.02em;
    white-space:nowrap;box-shadow:0 6px 18px var(--node-rest-shadow);opacity:0;pointer-events:none;transition:opacity .12s;}
  #alto-edit-pill .aep-claude::after{left:auto;right:-50px;transform:none;}
  #alto-edit-pill .aep-manual::after{left:auto;right:0;transform:none;}   /* the pill sits at the screen's edge: grow leftward */
  #alto-edit-pill .aep-half:hover::after,#alto-edit-pill .aep-half:focus-visible::after{opacity:1;}
  html.dark:not(.mobile) #alto-edit-pill{color:var(--muted);}
  html.mobile #alto-edit-pill,html.alto-editing #alto-edit-pill,html.printing #alto-edit-pill{display:none !important;}
  .alto-edit-pill.in-page{display:none;margin:52px auto 28px;width:max-content;height:42px;border-radius:21px;
    background:var(--card-glass-bg,var(--surface));border:1px solid var(--card-glass-border,var(--border));color:var(--muted);
    box-shadow:0 8px 22px var(--node-rest-shadow);}
  .alto-edit-pill.in-page .aep-half{border-radius:21px;padding:0 20px;font-size:14px;}
  html.mobile .alto-edit-pill.in-page{display:flex;}
  html.alto-editing .alto-edit-pill.in-page,html.printing .alto-edit-pill.in-page{display:none !important;}

  /* the editing bar, at the foot of the screen */
  #alto-edit-exit{position:fixed;left:50%;transform:translateX(-50%);bottom:30px;z-index:330;display:none;align-items:center;gap:10px;
    height:38px;padding:0 6px 0 16px;border-radius:19px;background:#7a4b00;color:#fff;font:14px Georgia,serif;letter-spacing:.05em;
    box-shadow:0 6px 20px rgba(0,0,0,.25);white-space:nowrap;}
  html.dark #alto-edit-exit{background:#5a3a08;box-shadow:0 6px 20px rgba(0,0,0,.55);}
  html.alto-editing #alto-edit-exit{display:flex;}
  #alto-edit-exit .ee-st{font-size:11.5px;opacity:.8;}
  #alto-edit-exit button{height:28px;border:0;border-radius:14px;padding:0 14px;background:rgba(255,255,255,.18);color:#fff;font:inherit;cursor:pointer;}
  #alto-edit-exit button:hover{background:rgba(255,255,255,.28);}
  #alto-edit-exit .ee-h{min-width:34px;padding:0 6px;line-height:0;}
  #alto-edit-exit .ee-h svg{display:block;margin:auto;}
  #alto-edit-exit .ee-h[disabled]{opacity:.4;cursor:default;}
  /* phones: above the controls along the foot of the screen */
  html.mobile #alto-edit-exit{bottom:calc(66px + env(safe-area-inset-bottom,0px));height:42px;border-radius:21px;font-size:14px;padding:0 5px 0 14px;gap:6px;}
  html.mobile #alto-edit-exit .ee-st{display:none;}
  html.mobile.alto-editing #scroll-hint{display:none !important;}   /* the swipe hint would sit on the bar */
  html.printing #alto-edit-exit{display:none !important;}
  /* what else sits at the foot of the screen moves up while editing */
  html.alto-editing #aed-toast,html.alto-editing #aed-linkbar,html.alto-editing #aed-pick,html.alto-editing #alto-edit-toast{bottom:84px;}
  html.mobile.alto-editing #aed-toast,html.mobile.alto-editing #aed-linkbar{bottom:calc(120px + env(safe-area-inset-bottom,0px));}

  /* what can be edited, while editing */
  html.alto-editing .aed-f{outline:1.5px dashed transparent;outline-offset:3px;border-radius:4px;cursor:text;transition:outline-color .15s;}
  html.alto-editing .aed-f:hover{outline-color:color-mix(in srgb,var(--accent,#a78bfa) 70%,transparent);}
  html.alto-editing .aed-on{outline:2px solid var(--accent,#a78bfa) !important;outline-offset:3px;cursor:text;}
  html.alto-editing .aed-on:focus{outline:2px solid var(--accent,#a78bfa) !important;}
  html.alto-editing:not(.mobile) #canvas .node-card .node-title,
  html.alto-editing:not(.mobile) #canvas .node-card .node-tag,
  html.alto-editing:not(.mobile) #canvas .node-card .node-desc,
  html.alto-editing:not(.mobile) #canvas .phase-label-float{outline:1.5px dashed transparent;outline-offset:2px;border-radius:3px;cursor:text;}
  html.alto-editing:not(.mobile) #canvas .node-card .node-title:hover,
  html.alto-editing:not(.mobile) #canvas .node-card .node-tag:hover,
  html.alto-editing:not(.mobile) #canvas .node-card .node-desc:hover,
  html.alto-editing:not(.mobile) #canvas .phase-label-float:hover{outline-color:color-mix(in srgb,var(--accent,#a78bfa) 70%,transparent);}
  html.alto-editing:not(.mobile) #title-text{outline:1.5px dashed transparent;outline-offset:5px;border-radius:3px;cursor:text;}
  html.alto-editing:not(.mobile) #title-text:hover{outline-color:color-mix(in srgb,var(--accent,#a78bfa) 70%,transparent);}
  html.alto-editing.alto-drag-ok:not(.mobile) #canvas .node-card{cursor:grab;}
  html.alto-dragging, html.alto-dragging *{cursor:grabbing !important;-webkit-user-select:none !important;user-select:none !important;}
  .node.aed-moving{z-index:60 !important;}
  html.alto-editing:not(.mobile) #canvas .node-card .node-order{pointer-events:auto;cursor:text;border-radius:4px;padding:0 3px;margin:-1px -3px;transition:background .15s;}
  html.alto-editing:not(.mobile) #canvas .node-card .node-order:hover{background:color-mix(in srgb,var(--accent) 16%,transparent);color:var(--text);}
  .node.aed-moving .node-card{box-shadow:0 18px 44px var(--node-hover-shadow) !important;}
  .aed-body{font-size:17.5px;line-height:35px;min-height:35px;}
  .aed-para{white-space:pre-wrap;}
  /* structure: move / remove / add, shown while editing */
  .aed-sc,.aed-tc{display:none;gap:3px;vertical-align:middle;margin-left:10px;-webkit-user-select:none;user-select:none;}
  html.alto-editing .aed-sc{display:inline-flex;}
  .aed-sc button,.aed-tc button{width:24px;height:22px;padding:0;border-radius:6px;border:1px solid var(--border);background:var(--surface);
    color:var(--muted);cursor:pointer;font:600 12px/20px system-ui,-apple-system,sans-serif;letter-spacing:0;text-transform:none;}
  .aed-sc button:hover,.aed-tc button:hover{color:var(--text);border-color:var(--muted);}
  .aed-sc button::before,.aed-tc button::before{content:attr(data-g);}
  .aed-sc button[data-x="del"]:hover,.aed-tc button[data-x="del"]:hover{color:#dc2626;border-color:#dc2626;}
  #summary-inner > .aed-blk{position:relative;}
  #summary-inner > .aed-blk > .aed-sc{position:absolute;right:-4px;top:-14px;margin:0;}
  html.alto-editing .adt-card .aed-tc{display:flex;position:absolute;right:6px;top:-12px;z-index:3;opacity:0;transition:opacity .15s;}
  html.alto-editing .adt-card:hover .aed-tc,html.alto-editing .adt-card:focus-within .aed-tc{opacity:1;}
  .aed-add{display:none;margin:8px 0 34px;padding:10px 16px;border-radius:10px;border:1.5px dashed var(--border);background:none;color:var(--muted);
    cursor:pointer;font:inherit;font-size:13px;letter-spacing:.06em;}
  html.alto-editing .aed-add{display:inline-block;}
  .aed-add:hover{color:var(--text);border-color:var(--muted);}
  .aed-ph{color:var(--muted);font-style:italic;opacity:.8;}
  html:not(.alto-editing) .aed-ph{display:none;}
  html.mobile .aed-body{font-size:15px;line-height:2;}
  #aed-bar{position:fixed;z-index:8200;display:none;align-items:center;gap:4px;padding:4px;border-radius:10px;background:var(--surface);
    border:1px solid var(--border);box-shadow:0 8px 24px var(--card-shadow);font:12.5px/1 system-ui,-apple-system,sans-serif;}
  #aed-bar.show{display:flex;}
  #aed-bar button{height:28px;min-width:28px;padding:0 9px;border:0;border-radius:7px;background:none;color:var(--text);font:inherit;cursor:pointer;}
  #aed-bar button:hover{background:color-mix(in srgb,var(--text) 8%,transparent);}
  #aed-bar .ab-done{background:var(--accent,#a78bfa);color:#fff;}
  #aed-bar .ab-sep{width:1px;height:18px;background:var(--border);margin:0 2px;}
  #aed-bar .ab-hint{color:var(--muted);padding:0 6px;font-size:11px;}
  #aed-link{position:fixed;z-index:8300;display:none;width:320px;max-width:calc(100vw - 24px);padding:12px;border-radius:12px;background:var(--surface);
    border:1px solid var(--border);box-shadow:0 12px 34px var(--card-shadow);font:13px/1.4 system-ui,-apple-system,sans-serif;color:var(--text);}
  #aed-link.show{display:block;}
  #aed-link h5{margin:0 0 6px;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);}
  #aed-link input{width:100%;box-sizing:border-box;padding:8px 10px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font:inherit;}
  #aed-link .al-list{max-height:200px;overflow:auto;margin:6px 0 10px;}
  #aed-link .al-row{display:flex;justify-content:space-between;gap:8px;padding:7px 8px;border-radius:7px;cursor:pointer;}
  #aed-link .al-row:hover,#aed-link .al-row.sel{background:color-mix(in srgb,var(--accent,#a78bfa) 14%,transparent);}
  #aed-link .al-k{color:var(--muted);font-size:11px;white-space:nowrap;}
  #aed-link .al-go{display:flex;gap:6px;margin-top:6px;}
  #aed-link .al-go button{flex:1;height:30px;border-radius:8px;border:1px solid var(--border);background:none;color:var(--text);font:inherit;cursor:pointer;}
  #aed-link .al-msg{color:#c2410c;font-size:11.5px;min-height:14px;margin-top:4px;}
  #aed-link .al-fh{margin-top:12px;}
  #aed-link .al-fk{font-size:11px;line-height:1.35;margin-top:6px;}
  /* cards: + / ✕ on a card, + Add a card beside a unit's name */
  .aed-cc{position:absolute;right:40px;top:-13px;z-index:6;display:none;gap:3px;-webkit-user-select:none;user-select:none;}
  html.alto-editing:not(.mobile):not(.aed-picking) #canvas .node:hover .aed-cc{display:flex;}
  .aed-cc button{width:26px;height:24px;padding:0;border-radius:7px;border:1px solid var(--border);background:var(--surface);color:var(--muted);
    cursor:pointer;font:600 13px/22px system-ui,-apple-system,sans-serif;box-shadow:0 4px 12px var(--node-rest-shadow);}
  .aed-cc button::before{content:attr(data-g);}
  .aed-cc button:hover{color:var(--text);border-color:var(--muted);}
  .aed-cc button[data-x="delc"]:hover{color:#dc2626;border-color:#dc2626;}
  .aed-uc{position:absolute;z-index:21;height:30px;padding:0 12px;border-radius:8px;border:1.5px dashed var(--muted);background:var(--chip-glass-bg, var(--surface));
    color:var(--muted);cursor:pointer;font:12px/1 system-ui,-apple-system,sans-serif;letter-spacing:.04em;white-space:nowrap;}
  .aed-uc:hover{color:var(--text);border-color:var(--text);}
  html:not(.alto-editing) .aed-uc,html.mobile .aed-uc,html.aed-picking .aed-uc{display:none;}
  /* choosing a filter's cards */
  html.aed-picking #canvas .node{cursor:pointer !important;}
  /* faded, but still solid: the lines behind a card never show through it */
  html.aed-picking #canvas .node.aed-pick-out .node-card{position:relative;filter:saturate(.35);}
  html.aed-picking #canvas .node.aed-pick-out .node-card::after{content:'';position:absolute;inset:-1px;border-radius:inherit;pointer-events:none;z-index:50;
    background:color-mix(in srgb,var(--surface,#fff) 66%,transparent);}
  html.aed-picking #canvas .node.aed-pick-hit .node-card{outline:2px dashed var(--accent,#a78bfa);outline-offset:4px;}
  html.aed-picking #canvas .node.aed-pick-in.aed-pick-hit .node-card{outline-style:solid;}
  #aed-pick .ap-q{width:220px;height:30px;box-sizing:border-box;padding:0 10px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font:inherit;}
  #aed-pickres{position:fixed;left:50%;transform:translateX(-50%);z-index:8250;display:none;width:min(560px,92vw);max-height:46vh;overflow:auto;padding:8px;
    border-radius:12px;background:var(--surface);color:var(--text);border:1px solid var(--border);box-shadow:0 12px 34px var(--card-shadow);font:13px/1.3 system-ui,-apple-system,sans-serif;}
  #aed-pickres.show{display:block;}
  #aed-pickres .pr-h{display:flex;align-items:center;gap:8px;padding:2px 4px 8px;color:var(--muted);font-size:12px;}
  #aed-pickres .pr-h span{flex:1;}
  #aed-pickres .pr-h button{height:26px;padding:0 10px;border-radius:7px;border:1px solid var(--border);background:none;color:var(--text);font:inherit;font-size:12px;cursor:pointer;}
  #aed-pickres .pr-row{display:flex;align-items:center;gap:10px;padding:7px 8px;border-radius:8px;cursor:pointer;}
  #aed-pickres .pr-row:hover{background:color-mix(in srgb,var(--text) 6%,transparent);}
  #aed-pickres .pr-ck{width:16px;height:16px;flex:none;border-radius:4px;border:1.5px solid var(--muted);display:flex;align-items:center;justify-content:center;font-size:11px;color:#fff;}
  #aed-pickres .pr-row.on .pr-ck{background:var(--accent,#a78bfa);border-color:var(--accent,#a78bfa);}
  #aed-pickres .pr-t{flex:1;min-width:0;}
  #aed-pickres .pr-t b{display:block;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
  #aed-pickres .pr-t small{color:var(--muted);font-size:11.5px;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
  #aed-pickres .pr-none{padding:10px;color:var(--muted);}
  #aed-pickres .pr-g{width:16px;flex:none;display:flex;justify-content:center;}
  #aed-pickres .pr-g svg{width:15px;height:15px;}
  #aed-pickres .pr-h + .pr-row{margin-top:0;}
  #aed-pickres .pr-row + .pr-h{margin-top:8px;border-top:1px solid var(--border);padding-top:10px;}
  #aed-pick .ap-chips{background:none !important;color:var(--text) !important;border:1px solid var(--border) !important;white-space:nowrap;}
  html.aed-picking #canvas .node.aed-pick-in .node-card{outline:3px solid var(--accent,#a78bfa);outline-offset:3px;}
  #aed-pick{position:fixed;left:50%;transform:translateX(-50%);bottom:26px;z-index:8250;display:none;align-items:center;gap:12px;padding:8px 8px 8px 16px;
    border-radius:12px;background:var(--surface);color:var(--text);border:1px solid var(--border);box-shadow:0 12px 34px var(--card-shadow);font:13px/1.3 system-ui,-apple-system,sans-serif;max-width:92vw;}
  #aed-pick.show{display:flex;}
  #aed-pick .ap-n{color:var(--muted);white-space:nowrap;}
  #aed-pick button{height:30px;padding:0 14px;border:0;border-radius:8px;background:var(--accent,#a78bfa);color:#fff;font:inherit;cursor:pointer;}
  /* a card's page: which of your filters it is in */
  .aed-flags{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:14px 0 22px;padding:10px 12px;border-radius:12px;border:1.5px dashed var(--border);
    font:12.5px/1.2 system-ui,-apple-system,sans-serif;}
  .aed-flags .aed-fh{font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-right:4px;}
  .aed-fchip{padding:6px 11px;border-radius:999px;border:1.4px solid color-mix(in srgb,var(--c,var(--accent)) 50%,transparent);background:none;color:var(--text);font:inherit;cursor:pointer;}
  .aed-fchip.on{background:color-mix(in srgb,var(--c,var(--accent)) 24%,transparent);border-color:var(--c,var(--accent));}
  .aed-fchip.on::before{content:"✓ ";}
  .aed-fchip.aed-fnew{border-style:dashed;border-color:var(--border);color:var(--muted);}
  /* the Filter panel while editing */
  #ef-panel .aed-fhint{font-size:11.5px;color:var(--muted);margin:0 2px 10px;line-height:1.35;}
  #ef-panel .ef-h .aed-fx{margin-left:8px;font-size:10px;letter-spacing:.04em;text-transform:none;color:var(--muted);cursor:pointer;padding:1px 6px;border-radius:5px;border:1px solid var(--border);}
  #ef-panel .ef-h .aed-fx:hover{color:var(--text);border-color:var(--muted);}
  #ef-panel .aed-fxc{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;margin-left:-2px;border-radius:50%;color:var(--muted);font-size:11px;line-height:1;}
  #ef-panel .aed-fxc::before{content:attr(data-g);}
  #ef-panel .aed-fxc:hover{color:var(--text);background:color-mix(in srgb,var(--text) 10%,transparent);}
  #ef-panel .aed-foff{opacity:.42;}
  #ef-panel .ef-sec.aed-foff .ef-h .aed-fx,#ef-panel .ef-chip.aed-foff .aed-fxc{opacity:1;}
  #ef-panel .ef-sec.aed-foff{opacity:1;} #ef-panel .ef-sec.aed-foff .ef-chips{opacity:.42;}
  #ef-panel .aed-fadd{display:block;width:100%;margin:6px 0 8px;padding:9px;border-radius:10px;border:1.5px dashed var(--border);background:none;color:var(--muted);font:inherit;font-size:12.5px;cursor:pointer;}
  #ef-panel .aed-fadd:hover{color:var(--text);border-color:var(--muted);}
  /* a name to type; the kinds of section */
  /* a card's chips, beside the card on the timeline */
  #aed-chpop{position:fixed;z-index:8340;display:none;width:360px;max-width:calc(100vw - 24px);max-height:70vh;overflow:auto;padding:12px 12px 4px;border-radius:12px;
    background:var(--surface);color:var(--text);border:1px solid var(--border);box-shadow:0 14px 40px var(--node-rest-shadow);}
  #aed-chpop.show{display:block;}
  #aed-chpop h5{margin:0 0 4px;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);}
  #aed-chpop .aed-chips{margin:6px 0 8px;border:0;padding:0;}
  #aed-chpop .aed-chnone{font-size:12px;color:var(--muted);margin:4px 0 10px;line-height:1.5;}
  /* the bar at the top, while editing */
  .aed-navoff{display:none !important;}
  #nav .nav-btn{position:relative;}
  .aed-nx{position:absolute;top:-7px;right:-7px;width:17px;height:17px;border-radius:50%;display:none;align-items:center;justify-content:center;
    background:var(--surface);color:var(--muted);border:1px solid var(--border);font-size:9px;line-height:1;cursor:pointer;z-index:3;font-family:-apple-system,BlinkMacSystemFont,sans-serif;}
  .nav-btn:hover > .aed-nx,.nav-group-label:hover > .aed-nx{display:flex;}
  .aed-nx:hover{color:#dc2626;border-color:#dc2626;}
  .nav-group-label{position:relative;}
  .aed-nx.aed-nxl{top:-9px;right:-14px;}
  .aed-nadd{height:26px;padding:0 12px;margin-left:6px;border-radius:13px;border:1.5px dashed var(--muted);background:none;color:var(--muted);font:inherit;font-size:12px;cursor:pointer;white-space:nowrap;}
  .aed-nadd:hover{color:var(--text);border-color:var(--text);}
  /* a card's corner, to resize it */
  .aed-rz{position:absolute;right:-1px;bottom:-1px;width:18px;height:18px;display:none;cursor:nwse-resize;z-index:60;border-radius:0 0 8px 0;
    background:linear-gradient(135deg,transparent 52%,var(--muted) 52%,var(--muted) 60%,transparent 60%,transparent 70%,var(--muted) 70%,var(--muted) 78%,transparent 78%);}
  html.alto-editing:not(.mobile):not(.aed-picking):not(.aed-linking) #canvas .node:hover .aed-rz,html.aed-resizing .aed-rz{display:block;}
  html.alto-editing #canvas .node-card{position:relative;}
  html.aed-resizing,html.aed-resizing *{cursor:nwse-resize !important;user-select:none !important;}
  html.aed-resizing #canvas .node-card{transition:none !important;}
  #aed-rztip{position:fixed;z-index:8500;display:none;padding:3px 8px;border-radius:6px;background:var(--surface);color:var(--muted);border:1px solid var(--border);
    font:11px system-ui,-apple-system,sans-serif;pointer-events:none;}
  #aed-rztip.show{display:block;}
  /* the glyph library, for a chip made here */
  #aed-glyph{position:fixed;z-index:8360;display:none;width:330px;max-width:calc(100vw - 24px);padding:12px;border-radius:12px;background:var(--surface);
    color:var(--text);border:1px solid var(--border);box-shadow:0 14px 40px var(--node-rest-shadow);}
  #aed-glyph.show{display:block;}
  #aed-glyph h5{margin:0 0 8px;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);}
  #aed-glyph .ag-grid{display:grid;grid-template-columns:repeat(10,1fr);gap:4px;}
  #aed-glyph button{aspect-ratio:1;display:flex;align-items:center;justify-content:center;padding:0;border-radius:7px;border:1px solid transparent;
    background:none;color:var(--text);cursor:pointer;}
  #aed-glyph button svg{width:18px;height:18px;}
  #aed-glyph button:hover:not([disabled]),#aed-glyph button:focus-visible{border-color:var(--border);background:color-mix(in srgb,var(--text) 7%,transparent);outline:none;}
  #aed-glyph button[disabled]{opacity:.22;cursor:not-allowed;}
  #aed-glyph .ag-k{margin:8px 0 0;font-size:11px;color:var(--muted);}
  /* a question with a few answers: removing a card with cards under it, a unit */
  #aed-ask{position:fixed;inset:0;z-index:8450;display:none;align-items:center;justify-content:center;padding:20px;background:rgba(8,9,16,.42);}
  #aed-ask.show{display:flex;}
  #aed-ask .aa-box{width:390px;max-width:100%;max-height:calc(100vh - 40px);overflow:auto;padding:18px 18px 12px;border-radius:16px;background:var(--surface);color:var(--text);
    border:1px solid var(--border);box-shadow:0 24px 60px rgba(0,0,0,.35);font-size:13.5px;}
  #aed-ask h4{margin:0 0 6px;font-size:15px;font-weight:600;}
  #aed-ask p{margin:0 0 14px;color:var(--muted);font-size:12.5px;line-height:1.55;}
  #aed-ask .aa-l{font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:4px 0 6px;}
  #aed-ask button{display:block;width:100%;text-align:left;min-height:38px;margin:0 0 7px;padding:8px 13px;border-radius:10px;border:1px solid var(--border);
    background:none;color:var(--text);font:inherit;cursor:pointer;line-height:1.35;}
  #aed-ask button:hover{background:color-mix(in srgb,var(--text) 6%,transparent);}
  #aed-ask button[disabled]{opacity:.4;cursor:default;}
  #aed-ask button small{display:block;color:var(--muted);font-size:11.5px;margin-top:2px;}
  #aed-ask .aa-danger{color:#dc2626;border-color:color-mix(in srgb,#dc2626 45%,var(--border));}
  #aed-ask .aa-quiet{border-color:transparent;color:var(--muted);text-align:center;}
  .aed-uc.aed-ux{border-style:solid;border-color:color-mix(in srgb,var(--muted) 45%,transparent);}
  .aed-uc.aed-ux:hover{color:#dc2626;border-color:#dc2626;}
  #aed-name,#aed-kinds{position:fixed;z-index:8350;display:none;width:300px;max-width:calc(100vw - 24px);padding:12px;border-radius:12px;background:var(--surface);
    border:1px solid var(--border);box-shadow:0 12px 34px var(--card-shadow);font:13px/1.4 system-ui,-apple-system,sans-serif;color:var(--text);}
  #aed-name.show,#aed-kinds.show{display:block;}
  #aed-name h5,#aed-kinds h5{margin:0 0 8px;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);}
  #aed-name input{width:100%;box-sizing:border-box;padding:8px 10px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font:inherit;}
  #aed-form{position:fixed;z-index:8350;display:none;width:340px;max-width:calc(100vw - 24px);max-height:calc(100vh - 24px);overflow:auto;padding:14px;border-radius:12px;background:var(--surface);
    border:1px solid var(--border);box-shadow:0 12px 34px var(--card-shadow);font:13px/1.4 system-ui,-apple-system,sans-serif;color:var(--text);}
  #aed-form.show{display:block;}
  #aed-form h5{margin:0 0 10px;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);}
  #aed-form label{display:block;margin:0 0 9px;}
  #aed-form label span{display:block;margin:0 0 3px;font-size:11.5px;color:var(--muted);}
  #aed-form label small{display:block;margin-top:3px;font-size:11px;color:var(--muted);}
  #aed-form input,#aed-form textarea,#aed-form select{width:100%;box-sizing:border-box;padding:7px 10px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font:inherit;}
  #aed-form textarea{resize:vertical;min-height:60px;}
  #aed-form .bad{border-color:#dc2626;}
  #aed-form .al-go{display:flex;gap:6px;margin-top:12px;}
  #aed-form .al-go button{flex:1;height:30px;border-radius:8px;border:1px solid var(--border);background:none;color:var(--text);font:inherit;cursor:pointer;}
  #aed-form .al-go .ab-ok{background:var(--accent,#a78bfa);border-color:transparent;color:#fff;}
  /* a line of a list section, a row of an Index page: its controls */
  .aed-lic{margin-left:8px;opacity:.35;transition:opacity .12s;}
  li:hover > .aed-lic,.aed-lic:focus-within{opacity:1;}
  .aed-ixc{position:absolute;right:0;top:8px;margin:0;}
  html.alto-editing .doc-row{position:relative;padding-right:64px;}
  .aed-lisadd{margin:4px 0 22px;padding:6px 14px;font-size:13px;}
  .aed-ixadd{margin:2px 0 22px;}
  .aed-chip .aed-chmv{width:16px;font-size:13px;}
  .aed-chip .aed-chmv:hover{color:var(--text);background:color-mix(in srgb,var(--text) 10%,transparent);}
  #aed-name .al-go{display:flex;gap:6px;margin-top:8px;}
  #aed-name .al-go button{flex:1;height:30px;border-radius:8px;border:1px solid var(--border);background:none;color:var(--text);font:inherit;cursor:pointer;}
  #aed-name .al-go .ab-ok{background:var(--accent,#a78bfa);border-color:transparent;color:#fff;}
  #aed-kinds button{display:block;width:100%;text-align:left;padding:8px 10px;border:0;border-radius:8px;background:none;color:var(--text);font:inherit;cursor:pointer;}
  #aed-kinds button:hover{background:color-mix(in srgb,var(--accent,#a78bfa) 14%,transparent);}
  #aed-kinds button b{display:block;font-weight:600;}
  #aed-kinds button small{display:block;color:var(--muted);font-size:11.5px;}
  /* dragging: the cards in the way step aside, and back */
  .node.aed-room{transition:translate .22s cubic-bezier(.2,.7,.3,1);}
  .aed-uc.aed-ur{border-style:solid;border-color:color-mix(in srgb,var(--muted) 45%,transparent);}
  .aed-uc.aed-unew{height:36px;padding:0 16px;font-size:13px;}
  /* moving a card under another: click the new parent */
  html.aed-linking #canvas .node{cursor:pointer !important;}
  html.aed-linking #canvas .node.aed-link-no .node-card{opacity:.32;cursor:not-allowed;}
  html.aed-linking #canvas .node.aed-link-at .node-card{outline:2px dashed var(--muted);outline-offset:3px;}
  html.aed-linking #canvas .node:not(.aed-link-no):hover .node-card{outline:3px solid var(--accent,#a78bfa);outline-offset:3px;}
  html.aed-linking .aed-cc,html.aed-linking .aed-uc{display:none !important;}
  #aed-linkbar{position:fixed;left:50%;transform:translateX(-50%);bottom:26px;z-index:8250;display:none;align-items:center;gap:12px;padding:8px 8px 8px 16px;
    border-radius:12px;background:var(--surface);color:var(--text);border:1px solid var(--border);box-shadow:0 12px 34px var(--card-shadow);font:13px/1.3 system-ui,-apple-system,sans-serif;max-width:92vw;}
  #aed-linkbar.show{display:flex;}
  #aed-linkbar button{height:30px;padding:0 14px;border:1px solid var(--border);border-radius:8px;background:none;color:var(--text);font:inherit;cursor:pointer;}
  /* a card's sub-chips, on its page */
  .aed-chips{display:flex;flex-direction:column;gap:8px;margin:14px 0 22px;padding:10px 12px;border-radius:12px;border:1.5px dashed var(--border);
    font:12.5px/1.2 system-ui,-apple-system,sans-serif;}
  .aed-chips .aed-chrow{display:flex;flex-wrap:wrap;align-items:center;gap:6px;}
  .aed-chips .aed-fh{font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-right:4px;min-width:72px;}
  .aed-chip{display:inline-flex;align-items:center;gap:4px;padding:4px 4px 4px 11px;border-radius:999px;border:1.4px solid color-mix(in srgb,var(--c,var(--accent)) 55%,transparent);
    background:color-mix(in srgb,var(--c,var(--accent)) 14%,transparent);color:var(--text);}
  .aed-chip button{width:20px;height:20px;padding:0;border:0;border-radius:50%;background:none;color:var(--muted);cursor:pointer;font:600 11px/20px system-ui,sans-serif;}
  .aed-chip button:hover{color:#dc2626;background:color-mix(in srgb,#dc2626 12%,transparent);}
  .aed-chadd{padding:5px 11px;border-radius:999px;border:1.4px dashed var(--border);background:none;color:var(--muted);font:inherit;cursor:pointer;}
  .aed-chadd:hover{color:var(--text);border-color:var(--muted);}
  #aed-chip{position:fixed;z-index:8350;display:none;width:300px;max-width:calc(100vw - 24px);padding:12px;border-radius:12px;background:var(--surface);
    border:1px solid var(--border);box-shadow:0 12px 34px var(--card-shadow);font:13px/1.4 system-ui,-apple-system,sans-serif;color:var(--text);}
  #aed-chip.show{display:block;}
  #aed-chip h5{margin:0 0 8px;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);}
  #aed-chip input{width:100%;box-sizing:border-box;padding:8px 10px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font:inherit;}
  #aed-chip .al-list{max-height:240px;overflow:auto;margin:6px 0 2px;}
  #aed-chip .al-row{padding:7px 8px;border-radius:7px;cursor:pointer;}
  #aed-chip .al-row:hover{background:color-mix(in srgb,var(--accent,#a78bfa) 14%,transparent);}
  #aed-chip .al-new{color:var(--accent,#a78bfa);}
  #aed-chip .al-k{color:var(--muted);font-size:11px;}
  #aed-toast{position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:8400;display:none;padding:10px 16px;border-radius:12px;
    background:var(--surface);color:var(--text);border:1px solid var(--border);box-shadow:0 10px 30px var(--node-rest-shadow);font-size:13px;max-width:90vw;}
  #aed-toast.show{display:block;}
  #aed-toast{pointer-events:none;}     /* a passing word: never in the way of a click */
</style>"""


MANUAL_JS = r"""<script id="alto-manual">
(function(){
  var E = window._ALTO_EDIT || {};
  var TID = String(E.key || '').replace(/^alto-doc-/, '');
  // Shares carry 's-…' here (reidentify rewrites the key); they never edit.
  if(!TID || TID.indexOf('s-') === 0) return;
  var root = document.documentElement;
  var PHONE = /iPhone|iPod|Android.*Mobile|Windows Phone/i.test(navigator.userAgent);
  var LKEY = 'alto-ed-' + TID, EDK = window._ALTO_EDK || {};
  var MAX_HIST = 200;
  // a source's local-copy icon (sanitize.LOCAL_ICON); spelled in two parts so a
  // page without local copies carries none of that machinery's names
  var LOCAL_CLS = 'alto-src' + '-local';

  function rd(){ try{ var o = JSON.parse(localStorage.getItem(LKEY) || 'null'); return (o && o.ops) ? o : {v:1, ops:{}}; }catch(e){ return {v:1, ops:{}}; } }
  function wr(){ try{ localStorage.setItem(LKEY, JSON.stringify(STORE)); }catch(e){} }
  var STORE = rd();
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>]/g, function(c){ return c === '&' ? '&amp;' : c === '<' ? '&lt;' : '&gt;'; }); }
  function txt(html){ var d = document.createElement('div'); d.innerHTML = String(html == null ? '' : html); return d.textContent; }
  function same(a, b){ return JSON.stringify(a == null ? null : a) === JSON.stringify(b == null ? null : b); }
  // djb2 over UTF-16 code units (manual_edit.jhash): what a structural edit
  // was made against, so it is laid over that page and no other.
  function jh(s){ s = String(s); var h = 5381; for(var i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0; return (h >>> 0).toString(16); }
  function rid(p){ return p + Math.random().toString(36).slice(2, 8); }
  function own(x){ return typeof x === 'string' || x >= 0; }

  /* ── the page's data, field by field ───────────────────────────────────── */
  function srcNode(id){ if(typeof NODES_SRC === 'undefined') return null; for(var i = 0; i < NODES_SRC.length; i++) if(NODES_SRC[i].id === id) return NODES_SRC[i]; return null; }
  function liveNode(id){ if(typeof NODES === 'undefined') return null; for(var i = 0; i < NODES.length; i++) if(NODES[i].id === id) return NODES[i]; return null; }
  function reg(kind){
    try{ return kind === 'c' ? CHARS : kind === 'env' ? ENVS : kind === 'theme' ? THEMES : null; }catch(e){ return null; }
  }
  function secList(kind, id){
    try{
      if(kind === 'n') return (NODE_DETAILS[id] || {}).sections || null;
      if(kind === 'c') return (CHAR_PAGES[id] || {}).sections || null;
      var R = reg(kind); return R && R[id] ? R[id].sections || null : null;
    }catch(e){ return null; }
  }
  function sec(kind, id, i){
    var m = (EDK[kind] || {})[id], L = secList(kind, id); if(!m || !L) return null;
    for(var j = 0; j < m.length; j++) if(String(m[j]) === String(i)) return L[j] || null;
    return null;
  }
  // An object that can carry sections, its list made if the build gave it none.
  function ownable(kind, id){
    try{
      if(kind === 'n'){ if(!srcNode(id)) return false; if(!NODE_DETAILS[id]) NODE_DETAILS[id] = {sections: []}; if(!NODE_DETAILS[id].sections) NODE_DETAILS[id].sections = []; }
      else if(kind === 'c'){ if(!CHARS[id]) return false; if(!CHAR_PAGES[id]) CHAR_PAGES[id] = {sections: []}; if(!CHAR_PAGES[id].sections) CHAR_PAGES[id].sections = []; }
      else { var R = reg(kind); if(!R || !R[id]) return false; if(!R[id].sections) R[id].sections = []; }
      EDK[kind] = EDK[kind] || {}; if(!EDK[kind][id]) EDK[kind][id] = secList(kind, id).map(function(){ return -2; });
      return true;
    }catch(e){ return false; }
  }
  var ORIG = {};
  function reorder(kind, id, order){
    var L = secList(kind, id), m = EDK[kind][id], key = kind + '|' + id;
    if(!ORIG[key]){ ORIG[key] = {}; m.forEach(function(x, j){ if(own(x)) ORIG[key][String(x)] = L[j]; }); }
    var O = ORIG[key], head = [], hm = [], tail = [], tm = [], os = [], om = [];
    m.forEach(function(x, j){ if(x === -1){ head.push(L[j]); hm.push(-1); } else if(x === -2){ tail.push(L[j]); tm.push(-2); } });
    (order || []).forEach(function(x){
      x = String(x); var s = O[x];
      if(!s && /^new-[a-z0-9]+$/.test(x)) s = O[x] = {h: '', t: '<span class="aed-k" data-k="' + key + '|s|' + x + '"></span>'};
      if(s){ os.push(s); om.push(/^new-/.test(x) ? x : +x); } });
    L.splice.apply(L, [0, L.length].concat(head, os, tail));
    m.splice.apply(m, [0, m.length].concat(hm, om, tm));
  }
  function ownPairs(kind, id){ var L = secList(kind, id) || [], m = (EDK[kind] || {})[id] || [], out = [];
    L.forEach(function(s, i){ if(typeof m[i] === 'number' && m[i] >= 0) out.push([txt(hParts(s.h).text), tParts(s.t).text]); }); return out; }
  function connAt(s, t, j){ if(typeof CONNECTIONS === 'undefined') return null; var n = 0;
    for(var i = 0; i < CONNECTIONS.length; i++){ var c = CONNECTIONS[i]; if(c[0] === s && c[1] === t){ if(n === j) return c; n++; } } return null; }
  /* the Overview: an authored one is one field; a composed one is its units' headings and summaries */
  var OVROOT = document.getElementById('summary-inner'), OVCUR = OVROOT ? OVROOT.innerHTML : '';
  function reinitOv(){ try{ if(typeof ovNavLinksInit !== 'undefined' && ovNavLinksInit && typeof initOverviewNavLinks === 'function'){ ovNavLinksInit = false; initOverviewNavLinks(); } }catch(e){} }
  function ovHeads(){
    if(!OVROOT || EDK.ov !== 'composed') return {};
    var hs = Array.prototype.filter.call(OVROOT.children, function(c){ return c.tagName === 'H2'; }), out = {};
    (EDK.ova || []).forEach(function(a, i){ if(hs[i + 1]) out[a] = hs[i + 1]; });
    return out;
  }
  function summaryPs(a){ var h = ovHeads()[a], out = []; if(!h) return out;
    for(var e = h.nextElementSibling; e && e.tagName === 'P' && !e.querySelector('.ov-node-link'); e = e.nextElementSibling) out.push(e);
    return out; }
  function drawSummary(a){
    var h = ovHeads()[a]; if(!h) return;
    summaryPs(a).forEach(function(p){ p.parentNode.removeChild(p); });
    var at = h;
    String(EDK.us[a] || '').split(/\n\s*\n/).map(function(x){ return x.trim(); }).filter(Boolean).forEach(function(t){
      var p = document.createElement('p'); p.textContent = t; at.parentNode.insertBefore(p, at.nextSibling); at = p; });
  }
  function drawOvHead(a){
    var h = ovHeads()[a]; if(!h) return;
    var f = (EDK.ovf || {})[a], pm = (typeof PHASE_META !== 'undefined') ? PHASE_META[a] : null;
    h.textContent = f === 'short' ? ((EDK.sh || {})[a] || (pm && pm.label) || '') : ((pm && pm.label) || '');
  }
  var PROV = '<span class="sec-prov">', SLOT = /<span class="a(?:dt|st)-slot"[\s\S]*$/;
  function hParts(h){ h = String(h || ''); var at = h.indexOf(PROV), mk = /^<span class="aed-k"[^>]*><\/span>/.exec(h);
    var lead = mk ? mk[0] : '', body = mk ? h.slice(lead.length) : h; at = body.indexOf(PROV);
    return {lead:lead, text: at >= 0 ? body.slice(0, at) : body, tail: at >= 0 ? body.slice(at) : ''}; }
  // A section's text may end with its tree's slot and (while editing) its key —
  // kept in the TEXT, never the heading: pages compare headings by name.
  var MARK = /<span class="aed-k" data-k="[^"]*"><\/span>/;
  function tParts(t){ t = String(t || ''); var mk = MARK.exec(t), mks = mk ? mk[0] : '';
    if(mk) t = t.replace(MARK, ''); var m = SLOT.exec(t); return {text: m ? t.slice(0, m.index) : t, tail: (m ? m[0] : '') + mks}; }
  function plan(){ return window._ALTO_TREE_PLAN || null; }
  function treeStep(key, step){ var T = (window._ALTO_DT || {})[key]; if(!T) return null; for(var i = 0; i < T.n.length; i++) if(T.n[i].i === step) return T.n[i]; return null; }
  var DTF = {title:'t', text:'x', edge:'e', tag:'g'};

  /* a section added here: its kind (brief.PROVENANCE), and a tree of its own */
  var PROVL = {quoted:'Quoted', notes:'From your notes', summary:'Summary'};
  var DTPRE = {n:'n', c:'c', env:'a0', theme:'a1'};
  var NEWT = /^(n|c|a0|a1)-(.+)-(new-[a-z0-9]+)$/;
  function newTreeSec(key){
    var m = NEWT.exec(key); if(!m) return null;
    var kind = {n:'n', c:'c', a0:'env', a1:'theme'}[m[1]], s = sec(kind, m[2], m[3]);
    return s ? {kind:kind, id:m[2], x:m[3], s:s} : null;
  }
  function setSlot(s, key, on, pre){
    var t = String(s.t || ''), mk = MARK.exec(t), m = mk ? mk[0] : '';
    var body = t.replace(MARK, '').replace(SLOT, ''); pre = pre || 'adt';
    s.t = body + (on ? '<span class="' + pre + '-slot" data-' + pre + '="' + key + '" hidden></span>' : '') + m;
  }
  // a heading's kind tag, left off where the heading already says it (detail_extras.prov_heading)
  function provTail(v, h){ var L = PROVL[v]; if(!L || txt(h).trim().toLowerCase() === L.toLowerCase()) return ''; return PROV + esc(L) + '</span>'; }

  /* cards added and removed here, laid over the page's own (an outline's
     tree, or a unit's run of cards) */
  var OUT = window._ALTO_OUTLINE || null;
  var CARDS0 = null, NEWC = {}, NEWO = [], GONE = {};
  // units added here (in the order they were made), cards moved under
  // another card (the id moved: its new parent), and what that moved
  var NEWU = {}, NEWUO = [], REPAR = {}, REPO = [], MOVED = [], OUTP = {}, PLAN0 = null;
  // children put in another order (so|), cards swapped with their parent
  // (sx|), and what that did to the page, for laying it out (placeSwaps)
  var SO = {}, SOO = [], SX = {}, SXO = [], SWAPPED = [], REORD = [];
  // units taken out (a built one by its number), cards moved to another unit
  // (a unit's top card, or any card of a timeline: its unit), the built units
  // no longer on the page, and the classic layout's place of a moved card
  var GONEU = {}, UA = {}, UAO = [], UNITS_OUT = [], BASEY0 = {};
  // chips taken out of the timeline ('c|<id>'), categories taken out and
  // made here (axis1 / axis2), and the chips the page was built with
  var XGONE = {}, XA = {}, NA = {}, CHIP0 = {};
  ['c', 'env', 'theme'].forEach(function(r){ CHIP0[r] = Object.keys(reg(r) || {}); });
  var RF = {c: 'chars', env: 'envs', theme: 'themes'}, AXR = {axis1: 'env', axis2: 'theme'};
  // cards sized here ({w, h}; null: as built), and the tree's widths as built
  var SZ = {}, SZ0 = EDK.sz || {}, W0 = null;
  function cardsBase(){
    if(CARDS0) return CARDS0;
    try{
      if(typeof NODES_SRC === 'undefined' || typeof NODES === 'undefined' || typeof ACT_SEQS === 'undefined' || typeof NODE_ACT === 'undefined') return null;
      var T = plan();
      CARDS0 = {src: NODES_SRC.slice(), live: NODES.slice(), seqs: ACT_SEQS.map(function(a){ return a.slice(); }),
        conns: (typeof CONNECTIONS !== 'undefined') ? CONNECTIONS.slice() : null, act: Object.assign({}, NODE_ACT),
        kids: OUT ? JSON.parse(JSON.stringify(OUT.kids || {})) : null, par: OUT ? Object.assign({}, OUT.parent || {}) : null,
        num: OUT ? Object.assign({}, OUT.num || {}) : null, label: OUT ? Object.assign({}, OUT.label || {}) : null,
        plan: T ? JSON.parse(JSON.stringify(T.acts)) : null,
        units: (typeof PHASE_META !== 'undefined') ? PHASE_META.slice() : [],
        order: (typeof NODE_ORDER_MAP !== 'undefined') ? Object.assign({}, NODE_ORDER_MAP) : null};
    }catch(e){ CARDS0 = null; }
    return CARDS0;
  }
  function isNew(id){ return !!(NEWC[id] && !NEWC[id].off); }
  function liveUnits(){ return NEWUO.filter(function(u){ return NEWU[u] && !NEWU[u].off; })
    .sort(function(a, b){ return ((NEWU[a].v.n || 0) - (NEWU[b].v.n || 0)) || (a < b ? -1 : 1); }); }
  // a unit's place on the page: a built one by its number, one added here by its id
  function unitAt(a){ var B = cardsBase(); if(!B) return -1;
    if(typeof a === 'number'){ if(UNITS_OUT.indexOf(a) >= 0) return -1; return a - UNITS_OUT.filter(function(x){ return x < a; }).length; }
    var i = liveUnits().indexOf(a); return i < 0 ? -1 : B.units.length - UNITS_OUT.length + i; }
  function liveBase(){ var B = cardsBase(), out = []; if(B) for(var i = 0; i < B.units.length; i++) if(UNITS_OUT.indexOf(i) < 0) out.push(i); return out; }
  function unitKeyOf(i){ var lb = liveBase(); return i >= lb.length ? liveUnits()[i - lb.length] : lb[i]; }
  function dfsOf(kids, id){ var out = []; (function walk(x){ out.push(x); (kids[x] || []).forEach(walk); })(id); return out; }
  function cardGone(id){ return !!GONE[id] || !!(NEWC[id] && NEWC[id].off); }
  function kidsOf(id){ return ((OUT && OUT.kids) || {})[id] || []; }
  function descendantsOf(id){ var out = [], q = kidsOf(id).slice(); while(q.length){ var c = q.shift(); out.push(c); q = q.concat(kidsOf(c)); } return out; }
  function romanOf(n){ var r = '', V = [[1000,'M'],[900,'CM'],[500,'D'],[400,'CD'],[100,'C'],[90,'XC'],[50,'L'],[40,'XL'],[10,'X'],[9,'IX'],[5,'V'],[4,'IV'],[1,'I']];
    V.forEach(function(p){ while(n >= p[0]){ r += p[1]; n -= p[0]; } }); return r; }
  function fill(obj, from){ Object.keys(obj).forEach(function(k){ delete obj[k]; }); Object.keys(from).forEach(function(k){ obj[k] = from[k]; }); }
  // A plan (layout.outline_plan) without the cards taken out.
  function out_(i){ return cardGone(i) || !!OUTP[i]; }
  function prune(op){
    var k = op[0];
    if(k === 'card') return out_(op[1]) ? null : op;
    if(k === 'row'){ var ids = op[1].filter(function(i){ return !out_(i); }); return ids.length ? [k, ids].concat(op.slice(2)) : null; }
    if(k === 'seq') return [k, op[1].map(prune).filter(Boolean)];
    if(k === 'par') return [k, op[1].map(prune).filter(Boolean)].concat(op.slice(2));
    if(k === 'band'){
      var cards = op[1].filter(function(cd){ return !out_(cd[0]); }).map(function(cd){ return cd.length > 5 && out_(cd[5]) ? cd.slice(0, 5) : cd; });
      // a band of columns only (layout.columns packing them) has no cards of its own
      var blocks = op[2].map(function(b){ var o = prune(b[2]); return o ? [b[0], b[1], o] : null; }).filter(Boolean);
      if(!cards.length && !blocks.length) return null;
      return [k, cards, blocks].concat(op.slice(3));
    }
    var inner = prune(op[1]); return inner ? [k, inner].concat(op.slice(2)) : null;     // float
  }
  // Every table the page keeps of its cards, from the cards as built plus
  // the ones added and less the ones removed here.
  function syncCards(){
    var B = cardsBase(); if(!B) return;
    var nu = liveUnits();
    UNITS_OUT = [];               // full numbering while the tables are made
    var liveBy0 = {}; B.live.forEach(function(n){ liveBy0[n.id] = n; });
    Object.keys(BASEY0).forEach(function(id){ var o = BASEY0[id]; B.src.forEach(function(n){ if(n.id === id) n.baseY = o[0]; });
      if(liveBy0[id]){ liveBy0[id].baseY = o[0]; if(o[1] != null) liveBy0[id].y = o[1]; } delete BASEY0[id]; });
    var src = B.src.filter(function(n){ return !cardGone(n.id); });
    var seqs = B.seqs.map(function(a){ return a.filter(function(id){ return !cardGone(id); }); }).concat(nu.map(function(){ return []; }));
    var act = {}; Object.keys(B.act).forEach(function(id){ if(!cardGone(id)) act[id] = B.act[id]; });
    var kids = null, par = null;
    if(B.kids){
      kids = {}; par = {};
      Object.keys(B.kids).forEach(function(p){ if(cardGone(p)) return; var l = B.kids[p].filter(function(id){ return !cardGone(id); }); if(l.length) kids[p] = l; });
      Object.keys(B.par).forEach(function(c){ if(!cardGone(c)) par[c] = B.par[c]; });
    }
    var spines = [];
    NEWO.forEach(function(id){
      var c = NEWC[id]; if(!c || c.off) return;
      var sp = c.spec, a = act[sp.p] != null ? act[sp.p] : unitAt(sp.a), seq = seqs[a];
      if(!seq || (sp.p && act[sp.p] == null)) return;           // its unit or parent is not on the page
      var at = seq.length;
      if(sp.p && kids){
        var last = seq.indexOf(sp.p);
        (function walk(x){ (kids[x] || []).forEach(function(k){ var j = seq.indexOf(k); if(j > last) last = j; walk(k); }); })(sp.p);
        at = last + 1;
        par[id] = sp.p; (kids[sp.p] = kids[sp.p] || []).push(id);
        spines.push([sp.p, id, 'spine']);
      }
      var before = at > 0 ? seq[at - 1] : null, after = seq[at] || null;
      seq.splice(at, 0, id); act[id] = a;
      function at_(x){ for(var i = 0; i < src.length; i++) if(src[i].id === x) return i; return -1; }
      var si = before ? at_(before) + 1 : after ? at_(after) : src.length;
      src.splice(si < 0 ? src.length : si, 0, c.src);
      if(!c.src.baseY){ var ys = src.filter(function(n){ return act[n.id] === a && n !== c.src; }).map(function(n){ return n.baseY || 0; });
        c.src.baseY = c.live.baseY = c.live.y = (ys.length ? Math.max.apply(null, ys) : 300) + 1; }
      c.live.act = a;
      try{ if(!NODE_DETAILS[id]) NODE_DETAILS[id] = {sections: []}; }catch(e){}
    });
    // cards moved under another card: the card and everything under it go to
    // the new parent's unit, after the new parent's last card
    MOVED = []; OUTP = {}; var moves = [];
    if(kids) REPO.forEach(function(id){
      var np = REPAR[id]; if(np == null || act[id] == null || cardGone(id)) return;
      var op = par[id];
      if(np === ''){
        // the top card of its unit, in place of the one taken out above it
        if(op && kids[op]){ kids[op] = kids[op].filter(function(x){ return x !== id; }); if(!kids[op].length) delete kids[op]; }
        delete par[id]; moves.push({id: id, from: op, np: '', S: [], top: true}); return;
      }
      if(act[np] == null || cardGone(np)) return;
      var S = dfsOf(kids, id); if(S.indexOf(np) >= 0 || par[id] === np) return;
      if(op && kids[op]){ kids[op] = kids[op].filter(function(x){ return x !== id; }); if(!kids[op].length) delete kids[op]; }
      par[id] = np; (kids[np] = kids[np] || []).push(id);
      var na = act[np];
      S.forEach(function(m){ var q = seqs[act[m]], j = q.indexOf(m); if(j >= 0) q.splice(j, 1); act[m] = na; });
      var seq = seqs[na], last = seq.indexOf(np);
      (function walk(x){ (kids[x] || []).forEach(function(k){ if(S.indexOf(k) >= 0) return; var j = seq.indexOf(k); if(j > last) last = j; walk(k); }); })(np);
      var before = last >= 0 ? seq[last] : null;
      seq.splice.apply(seq, [last + 1, 0].concat(S));
      var keep = src.filter(function(n){ return S.indexOf(n.id) >= 0; }); src = src.filter(function(n){ return S.indexOf(n.id) < 0; });
      var bi = -1; for(var i = 0; i < src.length; i++) if(src[i].id === before) bi = i;
      src.splice.apply(src, [bi < 0 ? src.length : bi + 1, 0].concat(keep));
      S.forEach(function(m){ OUTP[m] = 1; });
      moves.push({id: id, from: op, np: np, S: S});
    });
    MOVED = moves.filter(function(m){ return !m.top; });
    // cards moved to another unit: a unit's top card and all under it (an
    // outline), or one card (a timeline), after the unit's last card
    var carry = {}, uam = [];
    UAO.forEach(function(id){
      var v = UA[id]; if(v == null || act[id] == null || cardGone(id)) return;
      var t = unitAt(v); if(t < 0 || !seqs[t] || t === act[id]) return;
      if(par && par[id]) return;
      var from = act[id], S = kids ? dfsOf(kids, id) : [id];
      S.forEach(function(m){ var q = seqs[act[m]], j = q.indexOf(m); if(j >= 0) q.splice(j, 1); act[m] = t; });
      var wasEmpty = !seqs[t].length;
      seqs[t] = seqs[t].concat(S);
      var keep = src.filter(function(n){ return S.indexOf(n.id) >= 0; }); src = src.filter(function(n){ return S.indexOf(n.id) < 0; });
      var bi = -1; src.forEach(function(n, i){ if(act[n.id] <= t) bi = i; });
      src.splice.apply(src, [bi + 1, 0].concat(keep));
      if(kids && wasEmpty && typeof from === 'number' && from < B.units.length) carry[t] = from;
      uam.push({S: S, t: t});
    });
    // a timeline's card goes below the cards of the unit it joined
    if(!kids) uam.forEach(function(m){ m.S.forEach(function(id, k){
      var ys = src.filter(function(n){ return act[n.id] === m.t && m.S.indexOf(n.id) < 0; }).map(function(n){ return n.baseY || 0; });
      var mine = src.filter(function(n){ return n.id === id; })[0]; if(!mine) return;
      BASEY0[id] = [mine.baseY, liveBy0[id] ? liveBy0[id].y : null];
      var y = (ys.length ? Math.max.apply(null, ys) : 300) + 1 + k;
      mine.baseY = y; if(liveBy0[id]){ liveBy0[id].baseY = y; liveBy0[id].y = y; } }); });
    // cards swapped with their parent: each takes the other's place, so the
    // parent and its other children go under it, and its own children under
    // the parent (sx|); then children in the order set here (so|)
    SWAPPED = []; REORD = [];
    if(kids){
      // in the order they were made: a swap moves what an order named, and the other way round
      var opT = function(k){ return ((typeof STORE !== 'undefined' && STORE.ops[k]) || {}).t || 0; };
      var evs = SXO.map(function(c){ return ['x', c, opT('sx|' + c)]; }).concat(SOO.map(function(q){ return ['o', q, opT('so|' + q)]; }))
        .sort(function(a, b){ return a[2] - b[2]; });
      var swapOne = function(c){
        var p = SX[c]; if(!p || par[c] !== p || cardGone(c) || cardGone(p) || act[c] == null || act[c] !== act[p]) return;
        var g = par[p] || null, S = (kids[p] || []).slice(), K = (kids[c] || []).slice();
        if(g){ kids[g] = kids[g].map(function(x){ return x === p ? c : x; }); par[c] = g; } else delete par[c];
        kids[c] = S.map(function(x){ return x === c ? p : x; }); kids[c].forEach(function(x){ par[x] = c; });
        if(K.length){ kids[p] = K; K.forEach(function(x){ par[x] = p; }); } else delete kids[p];
        SWAPPED.push([c, p, g]);
      };
      var orderOne = function(p){
        var want = SO[p], have = kids[p]; if(!want || !have || cardGone(p)) return;
        // the cards it names, in its order, in the turns they hold; the rest keep theirs (edits.in_order)
        var q = want.filter(function(x){ return have.indexOf(x) >= 0; }), next = have.map(function(x){ return want.indexOf(x) >= 0 ? q.shift() : x; });
        if(next.join('|') === have.join('|')) return;
        REORD.push({p: p, before: have.slice(), after: next}); kids[p] = next;
      };
      evs.forEach(function(e){ if(e[0] === 'x') swapOne(e[1]); else orderOne(e[1]); });
      if(SWAPPED.length || REORD.length){
        // reading order: each unit's cards depth first, as the outline now goes
        seqs = seqs.map(function(q){ var inQ = {}, out = [], seen = {}; q.forEach(function(i){ inQ[i] = 1; });
          q.forEach(function(i){ if(par[i] && inQ[par[i]]) return;
            (function walk(x){ if(seen[x] || !inQ[x]) return; seen[x] = 1; out.push(x); (kids[x] || []).forEach(walk); })(i); });
          q.forEach(function(i){ if(!seen[i]) out.push(i); }); return out; });
        var at = {}; seqs.forEach(function(q, a){ q.forEach(function(i, j){ at[i] = a * 1e5 + j; }); });
        src = src.map(function(n, j){ return [n, j]; }).sort(function(A, Bb){
          var a = at[A[0].id], b = at[Bb[0].id]; return (a == null || b == null) ? A[1] - Bb[1] : (a - b) || (A[1] - Bb[1]); }).map(function(e){ return e[0]; });
      }
    }
    // units taken out, once nothing is left in them
    var gone = [];
    for(var bu = 0; bu < B.units.length; bu++) if(GONEU[bu] && seqs[bu] && !seqs[bu].length) gone.push(bu);
    var renum = function(i){ return i - gone.filter(function(x){ return x < i; }).length; };
    if(gone.length){
      seqs = seqs.filter(function(q, i){ return gone.indexOf(i) < 0; });
      Object.keys(act).forEach(function(id){ act[id] = renum(act[id]); });
    }
    var liveBy = {}; B.live.forEach(function(n){ liveBy[n.id] = n; });
    Object.keys(act).forEach(function(m){ var l = liveBy[m] || (NEWC[m] && NEWC[m].live); if(l && 'act' in l) l.act = act[m]; });
    NODES_SRC.splice.apply(NODES_SRC, [0, NODES_SRC.length].concat(src));
    NODES.splice.apply(NODES, [0, NODES.length].concat(src.map(function(n){ return liveBy[n.id] || NEWC[n.id].live; })));
    ACT_SEQS.length = Math.min(ACT_SEQS.length, seqs.length); while(ACT_SEQS.length < seqs.length) ACT_SEQS.push([]);
    ACT_SEQS.forEach(function(a, i){ a.splice.apply(a, [0, a.length].concat(seqs[i] || [])); });
    fill(NODE_ACT, act);
    if(B.conns) CONNECTIONS.splice.apply(CONNECTIONS, [0, CONNECTIONS.length].concat(
      spines.concat(B.conns.filter(function(c){ return !cardGone(c[0]) && !cardGone(c[1]); }).map(function(c){
        var mv = moves.filter(function(m){ return m.id === c[1] && m.from === c[0] && c[2] === 'spine'; })[0];
        return mv ? (mv.np ? [mv.np, c[1], 'spine'] : null) : c; }).filter(Boolean))));
    // a swap: every line into the two cards and their children hangs from the parent they have now
    if(B.conns && SWAPPED.length && par){
      var hit = {}; SWAPPED.forEach(function(w){ [w[0], w[1]].forEach(function(i){ hit[i] = 1; (kids[i] || []).forEach(function(k){ hit[k] = 1; }); }); });
      var why = {}; CONNECTIONS.forEach(function(c){ if(c[2] === 'spine' && c[3]){ why[c[0] + '|' + c[1]] = c[3]; why[c[1] + '|' + c[0]] = c[3]; } });
      var keep = CONNECTIONS.filter(function(c){ return !(c[2] === 'spine' && hit[c[1]]); });
      Object.keys(hit).forEach(function(i){ if(par[i]){ var c = [par[i], i, 'spine']; if(why[par[i] + '|' + i]) c.push(why[par[i] + '|' + i]); keep.push(c); } });
      CONNECTIONS.splice.apply(CONNECTIONS, [0, CONNECTIONS.length].concat(keep));
    }
    // the units: the page's own, then the ones added here
    var baseU = B.units.filter(function(pm, i){ return gone.indexOf(i) < 0; });
    if(gone.length) baseU = baseU.map(function(pm, i){ return Object.assign({}, pm, {numeral: romanOf(i + 1)}); });
    if(typeof PHASE_META !== 'undefined') PHASE_META.splice.apply(PHASE_META, [0, PHASE_META.length].concat(baseU,
      nu.map(function(u, j){ var pm = NEWU[u].pm, i = baseU.length + j; pm.numeral = romanOf(i + 1); pm.cssVar = pm.colorRaw || 'var(--phase' + (i + 1) + ')'; return pm; })));
    UNITS_OUT = gone;
    var changed = NEWO.some(isNew) || Object.keys(GONE).length > 0 || nu.length > 0 || moves.length > 0 || uam.length > 0 || gone.length > 0 || SWAPPED.length > 0 || REORD.length > 0;
    if(OUT){
      fill(OUT.kids, kids); fill(OUT.parent, par);
      if(!changed){ fill(OUT.num, B.num); fill(OUT.label, B.label); }
      else {
        // numbering.py: 2, 2.e, 2.e.6, 2.e.6.2-1c … from the outline as it is now
        var num = window._altoPathNums(seqs, kids, par), lab = Object.assign({}, num);
        fill(OUT.num, num); fill(OUT.label, lab);
      }
    }
    if(B.order){ if(!changed) fill(NODE_ORDER_MAP, B.order);
      else if(OUT) fill(NODE_ORDER_MAP, Object.assign({}, OUT.num));
      else { var om = {}; seqs.forEach(function(ids, a){ ids.forEach(function(id, j){ om[id] = (a + 1) + '.' + (j + 1); }); }); fill(NODE_ORDER_MAP, om); } }
    // a phone swipes through the cards in this order
    try{ if(typeof NODE_ORDER !== 'undefined') NODE_ORDER.splice.apply(NODE_ORDER, [0, NODE_ORDER.length].concat(NODES_SRC.map(function(n){ return n.id; }))); }catch(e){}
    phoneDirty = true;
    var T = plan();
    if(T && B.plan){
      var acts = (changed ? B.plan.map(function(ops){ return ops.map(prune).filter(Boolean); }) : JSON.parse(JSON.stringify(B.plan))).concat(nu.map(function(){ return []; }));
      // a unit whose cards all went to a new unit takes its plan with it
      Object.keys(carry).forEach(function(t){ acts[+t] = acts[carry[t]]; acts[carry[t]] = []; });
      T.acts = acts.filter(function(a, i){ return gone.indexOf(i) < 0; });
      // the plan as built (less what was taken out): where moved cards sat among themselves
      var mo = OUTP; OUTP = {}; PLAN0 = moves.length ? B.plan.map(function(ops){ return ops.map(prune).filter(Boolean); }) : null; OUTP = mo;
    }
  }
  function setNew(id, v){
    if(!cardsBase()) return;
    var c = NEWC[id];
    if(!v){ if(c) c.off = true; syncCards(); return; }
    if(!c){
      var s = {id:id, baseY:0, col: v.col || 'center', tag: v.g || '', title: v.t || '', desc: v.d || '', chars:[], color: v.c || 'var(--accent)', envs:[], themes:[]};
      c = NEWC[id] = {spec: null, src: s, live: Object.assign({}, s, {y: 0, act: v.a || 0})};
      NEWO.push(id);
    }
    c.off = false; c.spec = JSON.parse(JSON.stringify(v));
    syncCards();
  }
  function setUnit(id, v){
    if(!cardsBase()) return;
    var u = NEWU[id];
    if(!v){ if(u) u.off = true; syncCards(); return; }
    if(!u){ u = NEWU[id] = {v: null, pm: {label: v.l || 'New unit', numeral: '', colorRaw: v.c || '#8888aa', cssVar: ''}}; NEWUO.push(id); }
    u.off = false; u.v = JSON.parse(JSON.stringify(v)); u.pm.colorRaw = v.c || u.pm.colorRaw;
    syncCards();
  }
  /* chips made here: a new entity (or axis value) the page draws like its own */
  var NEWE = {}, CHTOUCH = false;
  function setChip(kind, id, v, k){
    var R = reg(kind); if(!R) return;
    if(!v){ if(NEWE[k]) NEWE[k].off = true; delete R[id]; authDrop(kind, id); try{ if(kind === 'c') delete CHAR_PAGES[id]; }catch(e){} CHTOUCH = true; drawFiltersSoon(); return; }
    NEWE[k] = {v: JSON.parse(JSON.stringify(v)), off: false};
    var col = /^#[0-9a-f]{6}$/i.test(v.color || '') ? v.color : '#8888aa';
    var glyph = (EDK.glyphs || []).some(function(g){ return g.s === v.svg; }) ? v.svg : (EDK.glyph || '&#9670;');
    var kd = (EDK.chipk || []).filter(function(x){ return x.r === kind; })[0] || {};
    R[id] = Object.assign(R[id] || {sections: []}, {name: esc(v.name || 'New'), role: '', color: col, symbol: glyph});
    authSet(kind, id, v);
    try{
      if(kind === 'c'){ if(!CHAR_PAGES[id]) CHAR_PAGES[id] = {sections: []}; document.documentElement.style.setProperty('--' + id, col); if(typeof CSS_HEX !== 'undefined') CSS_HEX['var(--' + id + ')'] = col; }
      else if(kind === 'env' && typeof ENV_SYM !== 'undefined') ENV_SYM[id] = kd.hide ? esc(v.name) : glyph;
      else if(kind === 'theme' && typeof THEME_SYM !== 'undefined') THEME_SYM[id] = kd.hide ? esc(v.name) : glyph;
    }catch(e){}
    CHTOUCH = true; drawFiltersSoon();
  }
  // A card's width on the page (the plan's, else measured).
  var WID = {};
  function wOf(id){ var T = plan(); if(T && T.w && T.w[id]) return T.w[id];
    if(WID[id] == null){ var el = document.getElementById('node-' + id), c = el && el.querySelector('.node-card'); WID[id] = c && c.offsetWidth ? c.offsetWidth : 240; } return WID[id]; }
  /* a card's size: set by dragging its corner (or grown by more words) — its
     width, and the least height it takes; its words always fit */
  var SZ_W = [160, 520], SZ_H = [40, 1400];
  function sizeOf(id){ return id in SZ ? SZ[id] : (SZ0[id] || null); }
  function sizeCSS(){
    var st = document.getElementById('aed-sz');
    if(!st){ st = document.createElement('style'); st.id = 'aed-sz'; document.head.appendChild(st); }
    var css = '', T = plan();
    if(T && T.w && !W0) W0 = Object.assign({}, T.w);
    Object.keys(SZ).forEach(function(id){ var z = SZ[id];
      if(T && T.w){ if(z && z.w) T.w[id] = z.w; else if(W0 && W0[id] != null) T.w[id] = W0[id]; }
      delete WID[id];
      if(!z) return;
      css += 'html:not(.mobile) #node-' + id + ' .node-card{' + (z.w ? 'width:' + z.w + 'px !important;' : '') + (z.h ? 'min-height:' + z.h + 'px !important;' : '') + '}\n'; });
    st.textContent = css;
  }
  function cardEl(id){ return document.querySelector('#node-' + id + ' .node-card'); }
  // how tall the card's words are at width w
  function natH(id, w){
    var c = cardEl(id); if(!c) return 0;
    var ow = c.style.getPropertyValue('width'), op = c.style.getPropertyPriority('width'), oh = c.style.getPropertyValue('min-height'), oq = c.style.getPropertyPriority('min-height');
    c.style.setProperty('width', w + 'px', 'important'); c.style.setProperty('min-height', '0px', 'important');
    var h = c.offsetHeight;
    if(ow) c.style.setProperty('width', ow, op); else c.style.removeProperty('width');
    if(oh) c.style.setProperty('min-height', oh, oq); else c.style.removeProperty('min-height');
    return h;
  }
  // the widest the card can be at height h before it meets another card, or
  // the edge of the page (outline cards keep clear of it)
  function maxW(id, h){
    var n = document.getElementById('node-' + id); if(!n) return SZ_W[1];
    var cx = n.offsetLeft + n.offsetWidth / 2, cy = n.offsetTop + n.offsetHeight / 2, lim = SZ_W[1] / 2;
    var edge = OUT ? 115 : 60, world = document.getElementById('world'), ww = world ? Math.max(world.offsetWidth, 1700) : 1700;
    lim = Math.min(lim, cx - edge, ww - edge - cx);
    document.querySelectorAll('#world .node').forEach(function(o){ if(o === n || !o.offsetWidth) return;
      var t = o.offsetTop, b = t + o.offsetHeight; if(b < cy - h / 2 - 4 || t > cy + h / 2 + 4) return;
      var l = o.offsetLeft, r = l + o.offsetWidth;
      if(l >= cx) lim = Math.min(lim, l - 16 - cx); else if(r <= cx) lim = Math.min(lim, cx - r - 16); });
    return Math.max(SZ_W[0], Math.floor(lim * 2));
  }
  // more words than the card's shape held: it grows in both directions, keeping
  // its shape, unless that would meet another card — then it grows taller only,
  // and the cards below make way (the formation across stays as it is)
  function growFor(id, w0, h0){
    var need = natH(id, w0); if(need <= h0 + 2) return null;
    var a = h0 / Math.max(w0, 1), top = Math.min(SZ_W[1], maxW(id, need));
    for(var w = w0 + 4; w <= top; w += 4){ var nh = natH(id, w); if(nh <= Math.round(w * a)) return {w: w, h: Math.max(nh, Math.round(w * a))}; }
    return sizeOf(id) ? {w: w0, h: Math.min(SZ_H[1], need)} : null;
  }
  // dragging the corner
  var RZ = null;
  function startResize(e, id){
    var c = cardEl(id), world = document.getElementById('world'); if(!c || !world) return;
    e.preventDefault(); e.stopPropagation();
    var k = (world.getBoundingClientRect().width / world.offsetWidth) || 1;
    RZ = {id: id, x: e.clientX, y: e.clientY, w0: c.offsetWidth, h0: c.offsetHeight, k: k, before: sizeOf(id), t: 0};
    root.classList.add('aed-resizing');
    try{ e.target.setPointerCapture(e.pointerId); }catch(_){}
  }
  function moveResize(e){
    if(!RZ) return;
    var dx = (e.clientX - RZ.x) / RZ.k * 2, dy = (e.clientY - RZ.y) / RZ.k * 2;
    var want = Math.round(Math.max(SZ_W[0], Math.min(RZ.w0 + dx, SZ_W[1]))), hw = Math.min(RZ.h0 + dy, SZ_H[1]);
    // the widest it can be up to where the pointer is: a wider card is shorter,
    // so each width is tried at the height it would have
    var w = SZ_W[0], h = 0;
    for(var tw = want; tw >= SZ_W[0]; tw -= 6){
      var th = Math.max(natH(RZ.id, tw), hw, SZ_H[0]);
      if(tw <= maxW(RZ.id, th)){ w = tw; h = th; break; }
    }
    if(!h) h = Math.max(natH(RZ.id, w), hw, SZ_H[0]);
    w = Math.round(w); h = Math.round(h);
    SZ[RZ.id] = {w: w, h: h}; sizeCSS();
    var now = Date.now(); if(now - RZ.t > 90){ RZ.t = now; relayout(); }
    var b = document.getElementById('aed-rztip'); if(!b){ b = document.createElement('div'); b.id = 'aed-rztip'; document.body.appendChild(b); }
    b.textContent = w + ' × ' + h; b.style.left = (e.clientX + 14) + 'px'; b.style.top = (e.clientY + 14) + 'px'; b.classList.add('show');
  }
  function endResize(){
    if(!RZ) return; var R = RZ; RZ = null; root.classList.remove('aed-resizing');
    var b = document.getElementById('aed-rztip'); if(b) b.classList.remove('show');
    var z = SZ[R.id];
    if(R.before) SZ[R.id] = R.before; else delete SZ[R.id];
    sizeCSS();
    if(z && !same(z, R.before)){ if(change('sz|' + R.id, z)) toast('Card resized — ⌘Z puts it back.'); }
    else relayout();
  }
  document.addEventListener('pointermove', moveResize, true);
  document.addEventListener('pointerup', endResize, true);
  document.addEventListener('pointercancel', endResize, true);
  // Room for a block of cards at `cand` (their top): it starts below any card
  // already across that line in its width, and every card below moves down by
  // the block's height — so it covers nothing until the next build places it.
  function makeSpace(R, h, cand, lo, hi, bh, skip, gap){
    var all = Object.keys(R.y).filter(function(q){ return !skip[q] && h[q] != null; });
    for(var guard = 0, moved = true; moved && guard < 400; guard++){
      moved = false;
      all.forEach(function(q){ var top = R.y[q] - h[q] / 2, bot = R.y[q] + h[q] / 2, ww = wOf(q) / 2 + 16;
        if(top < cand && bot > cand - gap + 1 && R.x[q] + ww > lo && R.x[q] - ww < hi){ cand = bot + gap; moved = true; } });
    }
    var D = bh + gap;
    all.forEach(function(q){ if(R.y[q] - h[q] / 2 >= cand - 0.5) R.y[q] += D; });
    return cand;
  }
  // A new card of an outline drawn as a tree, after the tree is laid out: under
  // its parent's last descendant (or at the foot of its unit; the first card of
  // a unit added here, below every unit before it).
  function placeNew(R, h){
    var T = plan(); if(!T) return;
    var ids = NEWO.filter(function(id){ return isNew(id) && R.y[id] != null && h[id] != null; }); if(!ids.length) return;
    var gap = T.row_gap || 40, placed = {}, skip = {};
    ids.forEach(function(id){ skip[id] = 1; });
    ids.forEach(function(id){
      var sp = NEWC[id].spec, hc = h[id] || 120, x, cand;
      var all = Object.keys(R.y).filter(function(q){ return q !== id && (!isNew(q) || placed[q]) && h[q] != null; });
      if(sp.p && R.y[sp.p] != null){
        var kin = descendantsOf(sp.p).filter(function(q){ return all.indexOf(q) >= 0; });
        var sib = kidsOf(sp.p).filter(function(q){ return all.indexOf(q) >= 0; });
        x = sib.length ? R.x[sib[sib.length - 1]] : R.x[sp.p];
        cand = Math.max.apply(null, kin.concat([sp.p]).map(function(q){ return R.y[q] + h[q] / 2; })) + gap;
      } else {
        var a = NODE_ACT[id], mine = all.filter(function(q){ return NODE_ACT[q] === a; });
        var above = all.filter(function(q){ return NODE_ACT[q] < a; });
        x = T.cx || 850;
        cand = mine.length ? Math.max.apply(null, mine.map(function(q){ return R.y[q] + h[q] / 2; })) + gap
          : above.length ? Math.max.apply(null, above.map(function(q){ return R.y[q] + h[q] / 2; })) + (T.act_gap || 210) : (T.top || 200);
      }
      var sk = {}; Object.keys(skip).forEach(function(q){ if(!placed[q]) sk[q] = 1; });
      cand = makeSpace(R, h, cand, x - wOf(id) / 2 - 16, x + wOf(id) / 2 + 16, hc, sk, gap);
      R.y[id] = cand + hc / 2; R.x[id] = x;
      placed[id] = 1;
    });
  }
  // Cards moved under another card: laid out among themselves as they were,
  // hung under the new parent's last card, everything below moving down.
  function placeMoved(R, h, shift, slide){
    var T = plan(); if(!T || !MOVED.length || !PLAN0) return;
    var R0 = window._altoTreeCalc(h, null, Object.assign({}, T, {acts: PLAN0}), null); if(!R0) return;
    var gap = T.row_gap || 40, P = (OUT && OUT.parent) || {};
    if(shift === undefined) shift = T.shift;
    if(slide === undefined) slide = T.slide;
    MOVED.forEach(function(mv){
      var inS = {}; mv.S.forEach(function(i){ inS[i] = 1; });
      var S = mv.S.filter(function(i){ return !isNew(i) && R0.y[i] != null && h[i] != null; });
      if(!S.length || R.y[mv.np] == null) return;
      var minT = Infinity, maxB = -Infinity, lo = Infinity, hi = -Infinity;
      S.forEach(function(i){ minT = Math.min(minT, R0.y[i] - h[i] / 2); maxB = Math.max(maxB, R0.y[i] + h[i] / 2);
        lo = Math.min(lo, R0.x[i] - wOf(i) / 2); hi = Math.max(hi, R0.x[i] + wOf(i) / 2); });
      var dx = R.x[mv.np] - R0.x[mv.id];
      if(lo + dx < 115) dx += 115 - (lo + dx); if(hi + dx > 1585) dx -= hi + dx - 1585;
      var fam = [mv.np].concat(descendantsOf(mv.np)).filter(function(q){ return !inS[q] && R.y[q] != null && h[q] != null; });
      var cand = Math.max.apply(null, fam.map(function(q){ return R.y[q] + h[q] / 2; })) + gap;
      var skip = {}; Object.keys(inS).forEach(function(q){ skip[q] = 1; }); NEWO.forEach(function(q){ if(isNew(q)) skip[q] = 1; });
      cand = makeSpace(R, h, cand, lo + dx - 16, hi + dx + 16, maxB - minT, skip, gap);
      S.forEach(function(i){
        var ox = 0, oy = 0, c = i;
        while(c && inS[c]){ var s = shift && shift[c]; if(s){ ox += s[0]; oy += s[1]; } if(c === mv.id) break; c = P[c]; }
        var sl = slide && slide[i]; if(sl){ ox += sl[0]; oy += sl[1]; }
        R.y[i] = cand + (R0.y[i] - h[i] / 2 - minT) + h[i] / 2 + oy; R.x[i] = R0.x[i] + dx + ox; });
      Object.keys(R.etx).forEach(function(k){ var c = k.split('|')[1];
        if(c === mv.id) delete R.etx[k]; else if(inS[c] && R0.etx[k] != null) R.etx[k] = R0.etx[k] + dx; });
    });
  }
  // Swaps, until the next build lays them out: a card and its parent trade
  // places; children in a new order each take the place of the one that had
  // that turn (one under the other: stacked afresh in the new order), with
  // what hangs under them. Then no two cards touch (_altoSeparate).
  function placeSwaps(R, h){
    var T = plan(), gap = (T && T.row_gap) || 40, P = (OUT && OUT.parent) || {}, K = (OUT && OUT.kids) || {};
    var y0 = Object.assign({}, R.y), x0 = Object.assign({}, R.x), E0 = Object.assign({}, R.etx || {});
    function top(i){ return R.y[i] - h[i] / 2; }
    function block(i){ return dfsOf(K, i).filter(function(q){ return R.y[q] != null && h[q] != null; }); }
    SWAPPED.forEach(function(w){ var c = w[0], p = w[1], g = w[2]; if(R.y[c] == null || R.y[p] == null) return;
      var ct = top(c), pt = top(p), cx = R.x[c];
      R.x[c] = R.x[p]; R.y[c] = pt + h[c] / 2; R.x[p] = cx; R.y[p] = ct + h[p] / 2;
      // the lines' ends go with the places
      Object.keys(E0).forEach(function(k){ var e = k.split('|'), a = e[0], b = e[1], na = a, nb = b;
        if(a === p) na = c; else if(a === c) na = p;
        if(b === c) nb = p; else if(b === p) nb = c;
        if(a === p && b === c){ na = c; nb = p; }
        if(na !== a || nb !== b){ delete R.etx[k]; R.etx[na + '|' + nb] = E0[k]; } });
    });
    REORD.forEach(function(o){
      var B = o.before.filter(function(i){ return R.y[i] != null; }), A = o.after.filter(function(i){ return R.y[i] != null; });
      if(B.length < 2 || B.length !== A.length) return;
      var bl = {}; B.forEach(function(i){ var q = block(i); bl[i] = {ids: q, t: Math.min.apply(null, q.map(top)), b: Math.max.apply(null, q.map(function(j){ return R.y[j] + h[j] / 2; }))}; });
      var byTop = B.slice().sort(function(a, b){ return bl[a].t - bl[b].t; });
      var stacked = B.every(function(i){ return Math.abs(R.x[i] - R.x[B[0]]) < 1; }) &&
        byTop.every(function(i, j){ return !j || bl[byTop[j - 1]].b <= bl[i].t; }) && byTop.join('|') === B.join('|');
      var mv = {};
      if(stacked){
        var cur = bl[B[0]].t, gaps = B.slice(1).map(function(i, j){ return bl[i].t - bl[B[j]].b; });
        A.forEach(function(i, j){ mv[i] = [0, cur - bl[i].t]; cur += bl[i].b - bl[i].t + (gaps[j] != null ? gaps[j] : gap); });
      } else A.forEach(function(i, j){ var s = B[j]; mv[i] = [R.x[s] - R.x[i], top(s) - top(i)]; });
      A.forEach(function(i){ var d = mv[i]; bl[i].ids.forEach(function(q){ R.x[q] += d[0]; R.y[q] += d[1]; }); });
      // fanned lines' ends belong to the turn, not the card
      A.forEach(function(i, j){ var k0 = o.p + '|' + B[j]; if(E0[k0] != null) R.etx[o.p + '|' + i] = E0[k0]; });
    });
    var acts = {}; Object.keys(R.y).forEach(function(i){ if(h[i] != null) (acts[NODE_ACT[i]] = acts[NODE_ACT[i]] || []).push(i); });
    Object.keys(acts).forEach(function(a){ window._altoSeparate(R.y, R.x, h, (T && T.w) || {}, acts[a], y0, x0, P, gap); });
    // a unit that grew pushes the ones below it down
    var low = null, ag = (T && T.act_gap) || 210;
    Object.keys(acts).map(Number).sort(function(a, b){ return a - b; }).forEach(function(a){
      var ids = acts[a], t = Math.min.apply(null, ids.map(top));
      if(low != null && t < low + ag){ var d = low + ag - t; ids.forEach(function(i){ R.y[i] += d; }); }
      low = Math.max.apply(null, ids.map(function(i){ return R.y[i] + h[i] / 2; })); });
    R.bottom = Math.max.apply(null, Object.keys(R.y).filter(function(i){ return h[i] != null; }).map(function(i){ return R.y[i] + h[i] / 2; }));
  }
  // The tree as this page has it: laid out, then the cards moved and added here.
  function layoutAll(h, shift, slide){
    var R = window._altoTreeCalc(h, shift, undefined, slide); if(!R) return null;
    if(MOVED.length || NEWO.length){ R.etx = Object.assign({}, R.etx);
      try{ placeMoved(R, h, shift, slide); }catch(e){} try{ placeNew(R, h); }catch(e){} }
    if(SWAPPED.length || REORD.length){ R.etx = Object.assign({}, R.etx); try{ placeSwaps(R, h); }catch(e){} }
    return R;
  }
  if(typeof window._altoTreeCalc === 'function' && typeof window._altoTreeWrite === 'function'){
    var ownTree = function(pos, h){
      if(root.classList.contains('mobile')) return false;
      var R = layoutAll(h); if(!R) return false;
      window._altoTreeWrite(R, pos, h); return true;
    };
    window._altoTree = ownTree;
  }

  /* filters: the owner's own (flags) and the ones taken out of the panel */
  var FLAGS = EDK.fl || [], FLN = EDK.fln || {}, OFF = EDK.foff || [], FSLOT = EDK.fslot || {};
  var FULL = JSON.parse(JSON.stringify(EDK.fall || {sections: window.FILTER_SECTIONS || [], nodes: window.FILTER_NODES || {}}));
  var FORIG = {sections: window.FILTER_SECTIONS, nodes: window.FILTER_NODES}, FTOUCH = false;
  function fkey(k){ return FSLOT[k] || k; }
  // The panel's sections as the build would make them now (blocks.py), or,
  // while editing, with the ones taken out still there to put back.
  function filterSets(all){
    var here = {}; (typeof NODES_SRC !== 'undefined' ? NODES_SRC : []).forEach(function(n){ here[n.id] = 1; });
    var fm = {}; Object.keys(FLN).forEach(function(nid){ if(here[nid]) (FLN[nid] || []).forEach(function(f){ (fm[f] = fm[f] || []).push(nid); }); });
    var fitems = FLAGS.filter(function(f){ return all || (fm[f.id] || []).length; }).map(function(f){
      return {id:f.id, name:f.name, color:f.color || 'var(--accent)', count:(fm[f.id] || []).length}; });
    var CHN = {};
    var chips = FULL.sections.filter(function(s){ return s.kind === 'chips' && s.key !== 'flags' && !XA[s.key]; })
      .map(function(s){ var c = chipSec(s); if(c.nodes) CHN[s.key] = c.nodes; return c.s; });
    // every kind of chip is a filter of its own (not a catch-all one, like a
    // course's cases), the ones made here included
    chipKinds().forEach(function(k){
      if(k.hide || FULL.sections.some(function(s){ return s.key === k.fk; })) return;
      var c = chipSec({key: k.fk, kind: 'chips', label: k.l, items: []}, true);
      if(c.s.items.length){ CHN[k.fk] = c.nodes; chips.push(c.s); } });
    var rest = FULL.sections.filter(function(s){ return s.kind !== 'chips'; });
    var list = chips.concat(fitems.length ? [{key:'flags', kind:'chips', label:'Flags', items:fitems}] : []).concat(rest);
    var out = [], nodes = {};
    list.forEach(function(s){
      var k = fkey(s.key), off = OFF.indexOf(k) >= 0;
      if(off && !all) return;
      var items = s.items.filter(function(it){ return all || OFF.indexOf(k + ':' + it.id) < 0; });
      if(!items.length) return;
      var s2 = JSON.parse(JSON.stringify(s)); s2.items = JSON.parse(JSON.stringify(items));
      if(all){ s2.off = off; s2.items.forEach(function(it){ it.off = OFF.indexOf(k + ':' + it.id) >= 0; }); }
      out.push(s2);
      if(s.key === 'flags'){ var m = {}; fitems.forEach(function(it){ m[it.id] = (fm[it.id] || []).slice().sort(); }); nodes.flags = m; }
      else if(CHN[s.key]) nodes[s.key] = CHN[s.key];
      else if(FULL.nodes[s.key]) nodes[s.key] = FULL.nodes[s.key];
    });
    return {sections: out, nodes: nodes};
  }
  // A sub-chip section as the cards' chips are now (blocks.py: one item per
  // chip some card carries), once chips were changed here.
  var FK = {entity:'chars', axis1:'envs', axis2:'themes'}, RK = {entity:'c', axis1:'env', axis2:'theme'};
  function chipSec(s, force){
    var f = FK[s.key]; if(!f || (!CHTOUCH && !force) || typeof NODES_SRC === 'undefined') return {s: s, nodes: null};
    var m = {}; NODES_SRC.forEach(function(n){ (n[f] || []).forEach(function(v){ (m[v] = m[v] || []).push(n.id); }); });
    var R = reg(RK[s.key]) || {}, seen = {};
    var items = s.items.map(function(it){ seen[it.id] = 1; return Object.assign({}, it, {count: (m[it.id] || []).length}); });
    Object.keys(NEWE).forEach(function(k){ var q = k.split('|'); if(q[1] !== RK[s.key] || NEWE[k].off || seen[q[2]] || !R[q[2]]) return;
      items.push({id: q[2], name: NEWE[k].v.name, color: R[q[2]].color, symbol: R[q[2]].symbol || EDK.glyph || '', count: (m[q[2]] || []).length}); });
    items = items.filter(function(it){ return !chipGone(RK[s.key], it.id); });
    Object.keys(m).forEach(function(v){ m[v].sort(); });
    return {s: Object.assign({}, s, {items: items.filter(function(it){ return it.count > 0; })}), nodes: m};
  }
  var drawFT = null;
  function drawFiltersSoon(){ FTOUCH = true; clearTimeout(drawFT); drawFT = setTimeout(drawFilters, 0); }
  function drawFilters(){
    if(typeof window._altoFilterRedraw !== 'function') return;
    if(document.readyState === 'loading'){ document.addEventListener('DOMContentLoaded', function(){ setTimeout(drawFilters, 0); }); return; }
    var ed = editing() && structOK();
    if(!ed && !FTOUCH){ window.FILTER_SECTIONS = FORIG.sections; window.FILTER_NODES = FORIG.nodes; }
    else { var S = filterSets(ed); window.FILTER_SECTIONS = S.sections; window.FILTER_NODES = S.nodes; }
    window._altoFilterWanted = ed;
    try{ window._altoFilterRedraw(); }catch(e){}
    paintPick();
  }
  function slug(s){ return String(s || '').toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40).replace(/-+$/, ''); }

  // The timeline's own name: the title bar, the browser tab, the drawer on a phone. The
  // homepage's list reads it from the account's listing record, which is told once it settles.
  function setTimelineTitle(v){
    v = String(v || '').replace(/\s+/g, ' ').trim();
    var te = document.getElementById('title-text'); if(te) te.textContent = v;
    var dt = document.getElementById('nav-drawer-title'); if(dt) dt.textContent = v;
    if(v) document.title = v + ' \u2014 Alto Timeline';
  }
  var headT = null;
  function headingSoon(){
    clearTimeout(headT);
    headT = setTimeout(function(){
      var c = window.AltoCloud, m = /^\/pv\/([^\/]+)/.exec(location.pathname || ''), te = document.getElementById('title-text');
      if(c && c.setHeading && m && te){ try{ c.setHeading(m[1], (te.textContent || '').replace(/\s+/g, ' ').trim()); }catch(e){} }
    }, 600);
  }
  // {get(), set(v), kind:'plain'|'html'|'shift'} for a key, or null when the page has no such field.
  function field(k){
    var p = k.split('|'), kind = p[0], id = p[1];
    if(LN && (kind === 'ln' || (kind === 'n' && p.length === 3 && (p[2] === 'when' || p[2] === 'line')))) return laneField(kind, id, p[2]);
    if(kind === 'n' && p.length === 3 && /^(title|tag|desc)$/.test(p[2])){
      var n = srcNode(id); if(!n) return null;
      return {kind:'plain', get:function(){ return n[p[2]] || ''; }, set:function(v){
        n[p[2]] = v; var l = liveNode(id); if(l) l[p[2]] = v;
        var el = document.querySelector('#node-' + id + ' .node-' + p[2]); if(el) el.textContent = v; }};
    }
    if((kind === 'c' || kind === 'env' || kind === 'theme') && p.length === 3 && /^(name|role)$/.test(p[2])){
      var R = reg(kind); if(!R || !R[id]) return null;
      return {kind:'plain', get:function(){ return txt(R[id][p[2]] || ''); }, set:function(v){ R[id][p[2]] = esc(v); }};
    }
    if(/^(n|c|env|theme)$/.test(kind) && p[2] === 's' && p.length === 5){
      var s = sec(kind, id, p[3]); if(!s) return null;
      if(p[4] === 'h') return {kind:'plain', get:function(){ return txt(hParts(s.h).text); },
        set:function(v){ var q = hParts(s.h); s.h = q.lead + esc(v) + (s._p != null ? provTail(s._p, esc(v)) : q.tail); }};
      if(p[4] === 't') return {kind:'html', get:function(){ return tParts(s.t).text; },
        set:function(v){ s.t = v + tParts(s.t).tail; }};
      // a new section's kind: quoted, from your notes, a summary (or none)
      if(p[4] === 'p' && /^new-/.test(p[3])) return {kind:'plain', get:function(){ return s._p || ''; },
        set:function(v){ s._p = PROVL[v] ? v : ''; var q = hParts(s.h); s.h = q.lead + q.text + provTail(s._p, q.text); }};
      return null;
    }
    if(kind === 'u' && p[2] === 'label'){
      var pm = (typeof PHASE_META !== 'undefined') ? PHASE_META[+id] : null; if(!pm) return null;
      return {kind:'plain', get:function(){ return pm.label; }, set:function(v){ pm.label = v; drawOvHead(+id); }};
    }
    if(kind === 'u' && p[2] === 'summary' && EDK.ov === 'composed' && EDK.us && (id in EDK.us)){
      return {kind:'para', get:function(){ return EDK.us[id] || ''; }, set:function(v){ EDK.us[id] = v; drawSummary(+id); }};
    }
    if(kind === 'u' && p[2] === 'short' && EDK.sh && (id in EDK.sh)){
      return {kind:'plain', get:function(){ return EDK.sh[id] || ''; }, set:function(v){ EDK.sh[id] = v; drawOvHead(+id); }};
    }
    if(kind === 'bt' && id === 'title' && p.length === 2){
      var te = document.getElementById('title-text'); if(!te) return null;
      return {kind:'plain', get:function(){ return (te.textContent || '').replace(/\s+/g, ' ').trim(); }, set:setTimelineTitle};
    }
    if(kind === 'ov' && id === 'html' && EDK.ov === 'authored' && OVROOT){
      return {kind:'ovhtml', sig:function(){ return EDK.ovh; }, get:function(){ return OVCUR; },
        set:function(v){ OVCUR = v; OVROOT.innerHTML = v; reinitOv(); }};
    }
    if(/^(n|c|env|theme)$/.test(kind) && p.length === 3 && p[2] === 'order'){
      if(!ownable(kind, id)) return null;
      var pk = kind + '|' + id;
      if(!(pk in PRIS)) PRIS[pk] = jh(JSON.stringify(ownPairs(kind, id)));
      return {kind:'struct', sig:function(){ return PRIS[pk]; },
        get:function(){ return ((EDK[kind] || {})[id] || []).filter(own).map(String); },
        set:function(v){ reorder(kind, id, v || []); }};
    }
    /*__STUDY_FIELD__*/
    if(kind === 'dt' && p.length === 3 && p[2] === 'tree' && NEWT.test(id)){
      // a tree in a section added here: made with its first step
      if(!window._ALTO_DT || (!window._ALTO_DT[id] && !newTreeSec(id))) return null;
      return {kind:'struct', sig:function(){ return 'new'; },
        get:function(){ var X = window._ALTO_DT[id]; return X ? JSON.parse(JSON.stringify(X.n)) : []; },
        set:function(v){ var X = window._ALTO_DT[id]; v = JSON.parse(JSON.stringify(v || []));
          if(!X) X = window._ALTO_DT[id] = {n: [], lay: 'auto', open: true, fold: 0, label: ''};
          X.n = v; var q = newTreeSec(id); if(q) setSlot(q.s, id, v.length > 0); }};
    }
    if(kind === 'dt' && p.length === 3 && p[2] === 'tree'){
      var TT = (window._ALTO_DT || {})[id]; if(!TT) return null;
      return {kind:'struct', sig:function(){ return PRIS['dt|' + id]; },
        get:function(){ return JSON.parse(JSON.stringify(TT.n)); },
        set:function(v){ TT.n = JSON.parse(JSON.stringify(v || [])); }};
    }
    if(kind === 'cx' && p.length === 4){
      var cc = connAt(id, p[2], +p[3]); if(!cc) return null;
      return {kind:'html', get:function(){ return cc[3] || ''; }, set:function(v){ if(v) cc[3] = v; else cc.length = 3; }};
    }
    if(kind === 'dt' && p.length === 4 && DTF[p[3]]){
      var st = treeStep(id, p[2]); if(!st) return null;
      var f = DTF[p[3]];
      return {kind:'plain', get:function(){ return st[f] || ''; }, set:function(v){ if(v) st[f] = v; else delete st[f]; }};
    }
    if(kind === 'nn' && p.length === 2 && /^card-[a-z0-9]{4,12}$/.test(id)){
      // a page built with the card already has it: nothing to lay over
      var B1 = cardsBase(); if(!B1 || B1.src.some(function(n){ return n.id === id; })) return null;
      return {kind:'card', sig:function(){ return null; },
        get:function(){ return isNew(id) ? JSON.parse(JSON.stringify(NEWC[id].spec)) : null; },
        set:function(v){ setNew(id, v); }};
    }
    if(kind === 'nd' && p.length === 2){
      var B0 = cardsBase(); if(!B0 || !B0.src.some(function(n){ return n.id === id; })) return null;
      return {kind:'card', get:function(){ return GONE[id] ? 1 : 0; },
        set:function(v){ if(v) GONE[id] = 1; else delete GONE[id]; syncCards(); }};
    }
    if(kind === 'fl' && id === 'list' && p.length === 2){
      return {kind:'list', get:function(){ return JSON.parse(JSON.stringify(FLAGS)); },
        set:function(v){ FLAGS.splice.apply(FLAGS, [0, FLAGS.length].concat(JSON.parse(JSON.stringify(v || [])))); drawFiltersSoon(); }};
    }
    if(kind === 'fn' && p.length === 2){
      if(!srcNode(id)) return null;
      return {kind:'list', get:function(){ return (FLN[id] || []).slice(); },
        set:function(v){ if(v && v.length) FLN[id] = v.slice(); else delete FLN[id]; drawFiltersSoon(); }};
    }
    if(kind === 'fx' && id === 'off' && p.length === 2){
      return {kind:'list', get:function(){ return OFF.slice(); },
        set:function(v){ OFF.splice.apply(OFF, [0, OFF.length].concat(v || [])); drawFiltersSoon(); }};
    }
    if(kind === 'nu' && p.length === 2 && /^unit-[a-z0-9]{4,12}$/.test(id)){
      // a page built with the unit already has it
      var B3 = cardsBase(); if(!B3 || (EDK.uids || []).indexOf(id) >= 0) return null;
      return {kind:'card', sig:function(){ return null; },
        get:function(){ return (NEWU[id] && !NEWU[id].off) ? JSON.parse(JSON.stringify(NEWU[id].v)) : null; },
        set:function(v){ setUnit(id, v); }};
    }
    if(kind === 'nl' && p.length === 2){
      if(!NEWU[id]) return null;
      return {kind:'plain', get:function(){ return NEWU[id].pm.label; }, set:function(v){ NEWU[id].pm.label = v; }};
    }
    if(kind === 'rp' && p.length === 2){
      var B4 = cardsBase(); if(!B4 || !OUT || !B4.par || !B4.src.some(function(n){ return n.id === id; })) return null;
      return {kind:'card', get:function(){ return REPAR[id] != null ? REPAR[id] : (B4.par[id] || ''); },
        set:function(v){ if(v == null || v === (B4.par[id] || '')) delete REPAR[id]; else { REPAR[id] = v; if(REPO.indexOf(id) < 0) REPO.push(id); } syncCards(); }};
    }
    if(kind === 'so' && p.length === 2){
      var B7 = cardsBase(); if(!B7 || !OUT || !B7.kids || !(B7.kids[id] || []).length) return null;
      var so0 = B7.kids[id].slice();
      return {kind:'card', sig:function(){ return so0; }, get:function(){ return SO[id] ? SO[id].slice() : so0.slice(); },
        set:function(v){ if(!v || v.join('|') === so0.join('|')) delete SO[id]; else { SO[id] = v.slice(); if(SOO.indexOf(id) < 0) SOO.push(id); } syncCards(); }};
    }
    if(kind === 'sx' && p.length === 2){
      var B8 = cardsBase(); if(!B8 || !OUT || !B8.par || !B8.par[id]) return null;
      var sx0 = B8.par[id];
      return {kind:'card', sig:function(){ return sx0; }, get:function(){ return SX[id] || null; },
        set:function(v){ if(!v) delete SX[id]; else { SX[id] = v; if(SXO.indexOf(id) < 0) SXO.push(id); } syncCards(); }};
    }
    if(kind === 'xe' && p.length === 3 && RF[id] && CHIP0[id].indexOf(p[2]) >= 0){
      var xk = id + '|' + p[2];
      return {kind:'card', get:function(){ return XGONE[xk] ? 1 : 0; },
        set:function(v){ if(v) XGONE[xk] = 1; else delete XGONE[xk]; CHTOUCH = true; navSync(); drawFiltersSoon(); }};
    }
    if(kind === 'na' && p.length === 2 && AXR[id]){
      var nax = EDK.nax || 0;
      if(!(id === 'axis1' ? nax === 0 : (nax === 1 || nax === 0))) return null;
      return {kind:'card', sig:function(){ return null; }, get:function(){ return NA[id] ? JSON.parse(JSON.stringify(NA[id])) : null; },
        set:function(v){ if(v) NA[id] = {l: String(v.l || 'Chips'), one: String(v.one || 'Chip')}; else delete NA[id]; CHTOUCH = true; navSync(); drawFiltersSoon(); }};
    }
    if(kind === 'xa' && p.length === 2 && AXR[id]){
      var xkd = (EDK.chipk || []).filter(function(k){ return k.fk === id; })[0]; if(!xkd) return null;
      return {kind:'card', sig:function(){ return String(xkd.l || ''); }, get:function(){ return XA[id] ? 1 : 0; },
        set:function(v){ if(v) XA[id] = 1; else delete XA[id]; CHTOUCH = true; navSync(); drawFiltersSoon(); }};
    }
    if(kind === 'sz' && p.length === 2){
      if(!srcNode(id)) return null;
      return {kind:'card', get:function(){ var z = sizeOf(id); return z ? JSON.parse(JSON.stringify(z)) : null; },
        set:function(v){ SZ[id] = v ? {w: +v.w || undefined, h: +v.h || undefined} : null; sizeCSS(); relayoutSoon(); }};
    }
    if(kind === 'ud' && p.length === 2 && /^\d+$/.test(id)){
      var B5 = cardsBase(); if(!B5 || !B5.units[+id]) return null;
      var lab0 = String(B5.units[+id].label || '');
      return {kind:'card', sig:function(){ return lab0; }, get:function(){ return GONEU[+id] ? 1 : 0; },
        set:function(v){ if(v) GONEU[+id] = 1; else delete GONEU[+id]; syncCards(); }};
    }
    if(kind === 'ua' && p.length === 2){
      var B6 = cardsBase(); if(!B6 || !(id in B6.act)) return null;
      // made against the card's unit as built — its number and its name — so a
      // page whose units have moved up does not take it a second time
      var ua0 = [B6.act[id], String((B6.units[B6.act[id]] || {}).label || '')];
      return {kind:'card', sig:function(){ return ua0; }, get:function(){ return UA[id] != null ? UA[id] : B6.act[id]; },
        set:function(v){ if(v == null || v === B6.act[id]) delete UA[id]; else { UA[id] = v; if(UAO.indexOf(id) < 0) UAO.push(id); } syncCards(); }};
    }
    if(kind === 'ch' && p.length === 3 && /^(chars|envs|themes)$/.test(p[2])){
      var cn = srcNode(id); if(!cn) return null;
      return {kind:'list', get:function(){ return (cn[p[2]] || []).slice(); },
        set:function(v){ v = (v || []).slice(); cn[p[2]] = v; var l = liveNode(id); if(l) l[p[2]] = v.slice(); CHTOUCH = true; phoneDirty = true; drawFiltersSoon(); }};
    }
    if(kind === 'ne' && p.length === 3 && /^(c|env|theme)$/.test(id) && /^[a-z0-9][a-z0-9-]{0,47}$/.test(p[2])){
      var R5 = reg(id); if(!R5 || (R5[p[2]] && !NEWE[k])) return null;      // the page has it already
      return {kind:'card', sig:function(){ return null; },
        get:function(){ return NEWE[k] && !NEWE[k].off ? JSON.parse(JSON.stringify(NEWE[k].v)) : null; },
        set:function(v){ setChip(id, p[2], v, k); }};
    }
    if(kind === 'p' && (p[2] === 'shift' || p[2] === 'slide')){
      var T = plan(), hk = p[2]; if(!T || !srcNode(id)) return null;
      return {kind:'shift', get:function(){ return (T[hk] && T[hk][id]) ? T[hk][id].slice() : null; },
        set:function(v){ T[hk] = T[hk] || {}; if(v && (v[0] || v[1])) T[hk][id] = v.slice(); else delete T[hk][id]; }};
    }
    return null;
  }

  /* ── lay the stored edits over the page ───────────────────────────────── */
  // Signatures of what the page was built with, taken before any edit lies over it.
  var PRIS = {};
  ['n', 'c', 'env', 'theme'].forEach(function(kind){ Object.keys(EDK[kind] || {}).forEach(function(id){ PRIS[kind + '|' + id] = jh(JSON.stringify(ownPairs(kind, id))); }); });
  Object.keys(window._ALTO_DT || {}).forEach(function(k){ PRIS['dt|' + k] = jh(JSON.stringify(window._ALTO_DT[k].n)); });
  Object.keys(window._ALTO_ST || {}).forEach(function(k){ PRIS['sd|' + k] = jh(JSON.stringify(window._ALTO_ST[k])); });
  var conflicts = {}, APPLIED = {};      // APPLIED: what this page last set each field to
  function sigOf(f){ return f.sig ? f.sig() : f.get(); }
  // structure first (a section list, a tree), then new sections' words, then the rest, oldest first
  // cards, then the filters' list, then structure (a section list, a tree; a
  // new section's tree after its section), new sections' words, the rest
  function pri(k){ var p = k.split('|');
    if(p[0] === 'ln') return -1.6;
    if(p[0] === 'na') return -5;
    if(p[0] === 'sz') return 1.5;
    if(p[0] === 'nu') return -4;
    if(p[0] === 'ne') return -3;
    if(p[0] === 'nn' || p[0] === 'nd') return -2;
    if(p[0] === 'rp') return -1.5;
    if(p[0] === 'ua') return -1.45;
    if(p[0] === 'ud') return -1.4;
    if(p[0] === 'sx') return -1.35;
    if(p[0] === 'so') return -1.3;
    if(p[0] === 'fl') return -1;
    if((p[0] === 'dt' && p[2] === 'tree') || p[0] === 'sd') return NEWT.test(p[1]) ? 0.5 : 0;
    return p[2] === 'order' ? 0 : (p[2] === 's' && /^new-/.test(p[3] || '')) ? 1 : 2; }
  function overlay(){
    var any = false;
    Object.keys(STORE.ops).sort(function(a, b){ return pri(a) - pri(b) || ((STORE.ops[a] || {}).t || 0) - ((STORE.ops[b] || {}).t || 0); }).forEach(function(k){
      var o = STORE.ops[k]; if(!o || o.done) return;
      var f = field(k); if(!f) return;
      var cur = f.get();
      if(same(cur, o.v)) return;
      if(same(sigOf(f), o.b) || ((k in APPLIED) && same(cur, APPLIED[k]))){ f.set(o.v); APPLIED[k] = o.v; any = true; delete conflicts[k]; }
      else conflicts[k] = 1;            // the page changed under it: the page wins
    });
    return any;
  }
  var laidOut = false;
  // A change made while a page covers the timeline (a card's chips): the
  // cards are drawn again once the timeline shows.
  var relayLater = false, phoneDirty = false;
  function relayout(){
    if(typeof initLayout !== 'function') return;
    // a phone lays its cards out once: draw them again when cards changed
    if(root.classList.contains('mobile')){ if(phoneDirty){ phoneDirty = false; try{ initLayout(); }catch(e){} } return; }
    var cv = document.getElementById('canvas');
    if(cv && getComputedStyle(cv).display === 'none'){ relayLater = true; return; }
    relayLater = false;
    try{ initLayout(); if(window._applyActiveFilters) window._applyActiveFilters(); }catch(e){}
    try{ if(window._altoFilterRefresh && window._altoChipOn && window._altoChipOn()) window._altoFilterRefresh(); }catch(e){}
    decorateCanvas(); paintPick();
  }
  if(overlay()){
    requestAnimationFrame(function(){ requestAnimationFrame(function(){ requestAnimationFrame(relayout); }); });
    if(FTOUCH) drawFiltersSoon();
    if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', navSync); else navSync();
  }

  /* ── who may edit ─────────────────────────────────────────────────────── */
  function cloud(){ return window.AltoCloud && window.AltoCloud.enabled ? window.AltoCloud : null; }
  // An older cached alto-cloud.js has no edit calls: no edit mode until it updates.
  function canEdit(){ var c = cloud(); return !!(c && c.user && typeof c.putEdits === 'function' && typeof c.getEdits === 'function' && /^https?:/.test(location.protocol)); }
  function whyNot(){
    if(!/^https?:/.test(location.protocol)) return 'Manual editing works on your web timeline, not a downloaded copy.';
    var c = cloud(); if(!c) return 'Manual editing needs your Alto site.';
    if(!c.known) return 'Checking your sign-in…';
    if(c.user && typeof c.putEdits !== 'function') return 'Reload the page to edit here (your site has a newer Alto).';
    return 'Sign in to your Alto site to edit here.';
  }

  /* ── saving: localStorage at once, the account shortly after ──────────── */
  var pushT = null, status = 'saved', unwatch = null;
  function setStatus(s){ status = s; var el = document.querySelector('#alto-edit-exit .ee-st');
    if(el) el.textContent = s === 'saving' ? 'Saving…' : s === 'offline' ? 'Saved on this device' : s === 'error' ? 'Not saved to your account yet' : 'All changes saved'; }
  function merge(a, b){
    var out = {}, ka = (a && a.ops) || {}, kb = (b && b.ops) || {};
    Object.keys(ka).concat(Object.keys(kb)).forEach(function(k){
      var x = ka[k], y = kb[k];
      if(!x || !y){ out[k] = x || y; return; }
      if((x.t || 0) !== (y.t || 0)) out[k] = (x.t || 0) > (y.t || 0) ? x : y;
      else out[k] = y.done ? y : x.done ? x : Object.assign({}, x, y);   // keeps the connector's fold mark
    });
    var cut = Date.now() - 30 * 864e5;
    Object.keys(out).forEach(function(k){ if(out[k] && out[k].done && (out[k].t || 0) < cut) delete out[k]; });
    return {v:1, ops: out};
  }
  function push(){
    clearTimeout(pushT);
    var c = cloud(); if(!c || !c.user || typeof c.putEdits !== 'function'){ setStatus('offline'); return; }
    setStatus('saving');
    pushT = setTimeout(function(){
      c.getEdits(TID).then(function(remote){
        STORE = merge(STORE, remote); wr();
        return c.putEdits(TID, STORE);
      }).then(function(){ setStatus('saved'); }, function(){ setStatus('error'); pushT = setTimeout(push, 8000); });
    }, 600);
  }
  function listen(){
    var c = cloud(); if(!c || !c.user || unwatch || !c.watchEdits) return;
    unwatch = c.watchEdits(TID, function(remote){
      if(!remote) return;
      var before = JSON.stringify(STORE.ops);
      STORE = merge(STORE, remote);
      if(JSON.stringify(STORE.ops) === before) return;
      wr(); refreshAll();
    });
  }
  window.addEventListener('alto-auth', function(){ listen(); syncTiles(); });
  setTimeout(function(){ listen(); syncTiles(); }, 1500);

  /* ── changes, undo and redo ───────────────────────────────────────────── */
  var HIST = [], HP = 0;
  function apply(k, v){
    var f = field(k); if(!f) return false;
    var cur = f.get(), o = STORE.ops[k], sg = sigOf(f);
    var base = (o && !o.done && (same(cur, o.v) || same(sg, o.b))) ? o.b : sg;
    if((k in APPLIED) && same(cur, APPLIED[k]) && o && !o.done) base = o.b;
    STORE.ops[k] = {b: base, v: v, t: Date.now()};
    f.set(v); APPLIED[k] = v; wr(); push(); refresh(k);
    return true;
  }
  // Several changes as one step of undo (a new section is its place, heading and words).
  function changes(list){
    var done = [];
    list.forEach(function(kv){ var f = field(kv[0]); if(!f) return; var a = f.get(); if(same(a, kv[1])) return;
      if(apply(kv[0], kv[1])) done.push({k:kv[0], a:a, b:kv[1]}); });
    if(!done.length) return false;
    HIST = HIST.slice(0, HP); HIST.push(done); if(HIST.length > MAX_HIST) HIST.shift(); HP = HIST.length;
    syncHist(); return true;
  }
  function change(k, v){ return changes([[k, v]]); }
  function undo(){ if(HP <= 0) return false; var h = HIST[--HP]; h.slice().reverse().forEach(function(e){ apply(e.k, e.a); }); syncHist(); return true; }
  function redo(){ if(HP >= HIST.length) return false; var h = HIST[HP++]; h.forEach(function(e){ apply(e.k, e.b); }); syncHist(); return true; }
  function syncHist(){
    document.querySelectorAll('#alto-edit-exit .ee-undo').forEach(function(b){ b.disabled = HP <= 0; });
    document.querySelectorAll('#alto-edit-exit .ee-redo').forEach(function(b){ b.disabled = HP >= HIST.length; });
  }

  /* ── showing a change: the page in front of the reader, in place ──────── */
  var relayT = null;
  function relayoutSoon(){ clearTimeout(relayT); relayT = setTimeout(relayout, 30); }
  function page(){ var dp = document.getElementById('detail-page'); if(!dp || !dp.classList.contains('visible')) return null;
    var P = window._altoPageNow || {type: window._currentDetailType, id: window._currentDetailId}; return P && P.id ? P : null; }
  var TYPE = {n:'node', c:'char', env:'env', theme:'theme'};
  function refresh(k){
    var p = k.split('|'), kind = p[0], P = page(), dc = document.getElementById('detail-content');
    if(kind === 'bt'){ headingSoon(); return; }
    if(kind === 'nl' || kind === 'ln' || (kind === 'n' && (p[2] === 'when' || p[2] === 'line'))){ relayoutSoon(); return; }
    if(kind === 'ch' || kind === 'ne' || kind === 'xe' || kind === 'xa' || kind === 'na'){
      relayoutSoon(); navSync(); chipPopSync();
      if(P && (P.type === 'node' || kind === 'ne')){ rerenderPage(P); repaint(); }
      return;
    }
    if(kind === 'nn' || kind === 'nd' || kind === 'nu' || kind === 'rp' || kind === 'ua' || kind === 'ud' || kind === 'so' || kind === 'sx'){
      relayoutSoon(); if(FLAGS.length || FTOUCH) drawFiltersSoon();
      if(P && P.type === 'node' && !srcNode(P.id)){ try{ window.showTimeline(); }catch(e){} }
      else if(P) { rerenderPage(P); repaint(); }
      return;
    }
    if(kind === 'ch' && P && P.type === 'node' && editing()){ relayoutSoon(); rerenderPage(P); repaint(); return; }
    if(kind === 'fl' || kind === 'fn' || kind === 'fx'){
      if(P && P.type === 'node' && editing()) decorateFlags(true);
      return;
    }
    if(kind === 'sd'){
      if(NEWT.test(p[1] || '')){ if(P){ rerenderPage(P); repaint(); } return; }
      var sb0 = dc && dc.querySelector('.ast[data-ast-key="' + p[1] + '"]');
      if(sb0){ var sl0 = document.createElement('span'); sl0.className = 'ast-slot'; sl0.setAttribute('data-ast', p[1]); sl0.hidden = true;
        sb0.parentNode.replaceChild(sl0, sb0); if(window._altoStudy) window._altoStudy(); }
      return;
    }
    if((kind === 'dt' && NEWT.test(p[1] || '') && p[2] === 'tree') || (p[2] === 's' && p[4] === 'p')){
      if(P) { rerenderPage(P); repaint(); }
      return;
    }
    if(kind === 'n' && p.length === 3) relayoutSoon();
    if(kind === 'u' || kind === 'p') relayoutSoon();
    if(kind === 'u' || kind === 'ov') decorateOvSoon();
    if(!P || !dc) return;
    // the whole page again where a change reaches past one element
    if((TYPE[kind] && TYPE[kind] === P.type && p[1] === P.id && (p[2] === 'order' || p[2] === 'tag' || p[2] === 'role' || (p[2] === 's' && /^new-/.test(p[3] || ''))))
       || (kind === 'cx' && P.type === 'node' && p[1] === P.id)){ rerenderPage(P); repaint(); return; }
    if(TYPE[kind] && TYPE[kind] === P.type && p[1] === P.id){
      var f = field(k), v = f ? f.get() : '';
      if(p[2] === 'title' || p[2] === 'name'){ var nm = dc.querySelector('.detail-name');
        if(nm){ var sn = kind === 'n' ? srcNode(p[1]) : null; nm.textContent = (sn && window._altoNodeName) ? window._altoNodeName(sn) : v; } }
      if(p[2] === 'desc'){ var ld = dc.querySelector('.alto-lead'); if(ld){ var num = ld.querySelector('.alto-lead-num'); ld.textContent = v; if(num) ld.insertBefore(num, ld.firstChild); } }
      if(p[2] === 's'){
        var mk = dc.querySelector('.aed-k[data-k="' + kind + '|' + p[1] + '|s|' + p[3] + '"]'), sb = mk && mk.closest('.detail-section'), h3 = sb && sb.querySelector(':scope > h3');
        var s = sec(kind, p[1], p[3]);
        if(h3 && s){
          if(p[4] === 'h') h3.innerHTML = s.h;
          else { var box = h3.parentNode; Array.prototype.slice.call(box.childNodes).forEach(function(c){ if(c !== h3 && !(c.classList && c.classList.contains('alto-edit-pill'))) box.removeChild(c); });
            var para = document.createElement('p'); para.innerHTML = s.t; box.insertBefore(para, h3.nextSibling); }
        }
      }
      repaint();
    }
    if(kind === 'dt'){
      var bx = dc.querySelector('.adt[data-adt-key="' + p[1] + '"]');
      if(bx){ var sl = document.createElement('span'); sl.className = 'adt-slot'; sl.setAttribute('data-adt', p[1]); sl.hidden = true;
        bx.parentNode.replaceChild(sl, bx); if(window._altoTrees) window._altoTrees(); }
    }
  }
  function refreshAll(){
    overlay(); relayoutSoon();
    var P = page(); if(P) Object.keys(STORE.ops).forEach(function(k){ if(k.split('|')[1] === P.id) refresh(k); });
  }
  function repaint(){ try{ if(window.reapplyHighlightsAfterNav) window.reapplyHighlightsAfterNav(); }catch(e){} decorateSoon(); }

  /* ── edit mode ────────────────────────────────────────────────────────── */
  function editing(){ return root.classList.contains('alto-editing'); }
  function toast(msg){
    var t = document.getElementById('aed-toast'); if(!t){ t = document.createElement('div'); t.id = 'aed-toast'; document.body.appendChild(t); }
    t.textContent = msg; t.classList.add('show'); clearTimeout(toast._t); toast._t = setTimeout(function(){ t.classList.remove('show'); }, 4200);
  }
  function enter(){
    if(!canEdit()){ toast(whyNot()); return; }
    if(editing()) return;
    try{ if(window._focusedNodeId && window.exitFocus) window.exitFocus(); }catch(e){}
    markSections();
    root.classList.add('alto-editing');
    root.classList.toggle('alto-drag-ok', !!(plan() && window._altoTreeOn && !root.classList.contains('mobile') && !PHONE));
    exitPill(); setStatus(status); syncHist(); listen();
    var P = page(); if(P) rerenderPage(P);
    decorate(); decorateOv();
    if(structOK()){ drawFilters(); decorateCanvas(); }
    navSync();
  }
  function exit(){
    if(!editing()) return;
    endField(true);
    root.classList.remove('alto-editing', 'alto-drag-ok');
    endPick(true); endLink(); hideMenus();
    document.querySelectorAll('.aed-sc,.aed-tc,.aed-cc,.aed-uc,.aed-add,.aed-ph,.aed-flags,.aed-chips,.aed-fx,.aed-fadd,.aed-nadd,.aed-nx,.aed-st').forEach(function(el){ if(el.parentNode) el.parentNode.removeChild(el); });
    document.querySelectorAll('.aed-f').forEach(function(el){ el.classList.remove('aed-f'); });
    hideBar(); closeAsk(); navSync();
    if(FTOUCH || structOK()) drawFilters();
  }
  // A page shown again in place: keeps where the reader was, and adds nothing
  // to Back (BACK_PREV counts a page opened from inside a page as a hop).
  function rerenderPage(P){
    // every box that may be the page's scroller (the detail page itself, its
    // ancestors on a phone's runway, the document) keeps where it was
    var dc = document.getElementById('detail-content'), keep = [];
    for(var el = dc; el; el = el.parentElement) if(el.scrollTop) keep.push([el, el.scrollTop]);
    var se = document.scrollingElement; if(se && se.scrollTop) keep.push([se, se.scrollTop]);
    try{ document.body.dispatchEvent(new MouseEvent('mousedown', {bubbles:true})); }catch(e){}
    try{ window.showDetail(P.type, P.id); }catch(e){}
    keep.forEach(function(k){ k[0].scrollTop = k[1]; });
  }
  // Each of an object's own sections carries its key in its heading (an empty
  // span), so the page can say which section a heading and its text are.
  var marked = false;
  function markObj(kind, id){
    var L = secList(kind, id), m = (EDK[kind] || {})[id]; if(!L || !m) return;
    L.forEach(function(s, i){ var src = m[i]; if(src == null || !own(src) || !s || MARK.test(s.t || '')) return;
      s.t = (s.t || '') + '<span class="aed-k" data-k="' + kind + '|' + id + '|s|' + src + '"></span>'; });
  }
  function markSections(){
    if(marked) return; marked = true;
    ['n', 'c', 'env', 'theme'].forEach(function(kind){ Object.keys(EDK[kind] || {}).forEach(function(id){ markObj(kind, id); }); });
  }
  window._altoManual = {enter:enter, exit:exit, undo:undo, redo:redo, change:change, editing:editing,
                        canEdit:canEdit, ops:function(){ return STORE.ops; }};

  function exitPill(){
    var b = document.getElementById('alto-edit-exit'); if(b) return b;
    b = document.createElement('div'); b.id = 'alto-edit-exit';
    b.innerHTML = '<span>✎ Editing</span><span class="ee-st">All changes saved</span>'
      + '<button type="button" class="ee-h ee-undo" aria-label="Undo"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/></svg></button><button type="button" class="ee-h ee-redo" aria-label="Redo"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m15 14 5-5-5-5"/><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/></svg></button>'
      + '<button type="button" class="ee-done">Done</button>';
    b.addEventListener('click', function(e){ var t = e.target.closest('button'); if(!t) return; e.stopPropagation();
      if(t.classList.contains('ee-done')) exit(); else if(t.classList.contains('ee-undo')) undo(); else if(t.classList.contains('ee-redo')) redo(); });
    document.body.appendChild(b); placePill(); return b;
  }
  function placePill(){}

  /* ── the edit toggle ───────────────────────────────────────────────────
     A split pill in the corner of the row of controls at the foot of the screen
     (search, info and light/dark sit to its left): the building builds with Claude (detail_extras.EDIT_TILE's
     openClaude), the pencil edits by hand. A phone gets the pencil alone, at
     the foot of each page. While editing, the editing bar takes its place. */
  var BUILD_SVG = '<svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 21V6l7-3v18"/><path d="M11 9h9v12"/><path d="M2.5 21h19"/><path d="M7 8.5v.01M7 12v.01M7 15.5v.01M15 12.5v.01M15 16v.01"/></svg>';
  function pillHTML(phone){
    return (phone ? '' : '<button type="button" class="aep-half aep-claude" data-tip="Edit with Claude: best for bigger changes" aria-label="Edit with Claude">' + BUILD_SVG + '</button><span class="aep-div" aria-hidden="true"></span>')
      + '<button type="button" class="aep-half aep-manual" data-tip="Edit manually: best for small fixes" aria-label="Edit manually"><span class="aep-pen" aria-hidden="true">✎</span>' + (phone ? '<span>Edit this page</span>' : '') + '</button>';
  }
  function wire(el){
    if(el._aed) return; el._aed = 1;
    el.addEventListener('click', function(e){
      var t = e.target.closest('button'); if(!t) return;
      e.stopPropagation();
      if(t.classList.contains('aep-claude')){ if(window._altoEditTimeline) window._altoEditTimeline(); }
      else if(t.classList.contains('aep-manual')){ if(t.classList.contains('off')){ toast(whyNot()); return; } if(editing()) exit(); else enter(); }
    });
  }
  function deskPill(){
    var b = document.getElementById('alto-edit-pill');
    if(!b){ b = document.createElement('div'); b.id = 'alto-edit-pill'; b.className = 'alto-edit-pill'; b.setAttribute('role', 'group');
      b.setAttribute('aria-label', 'Edit this timeline'); b.innerHTML = pillHTML(false); document.body.appendChild(b); wire(b); }
    return b;
  }
  // The toggle holds the corner of the row (CSS: right/bottom 30); the engine's
  // alignInfo lines search, info and light/dark up to its left, so tell it when
  // the toggle exists or changes.
  function placeDesk(){
    if(PHONE || root.classList.contains('mobile')) return;
    deskPill();
    if(window._altoAlignInfo) window._altoAlignInfo();
  }
  window.addEventListener('resize', placeDesk);
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', placeDesk); else placeDesk();
  function syncTiles(){
    var ok = canEdit();
    if(!PHONE) placeDesk();
    document.querySelectorAll('.alto-edit-pill').forEach(function(t){
      wire(t);
      var m = t.querySelector('.aep-manual'); if(!m) return;
      m.classList.toggle('off', !ok); m.setAttribute('data-tip', ok ? 'Edit manually: best for small fixes' : whyNot());
    });
    syncHist();
  }
  window._altoWireEditTile = function(){ syncTiles(); };
  function pageTile(){
    var dc = document.getElementById('detail-content'); if(!dc || !page()) return;
    if(dc.querySelector(':scope > .alto-edit-pill')) return;
    if(!dc.querySelector('.detail-header')) return;
    var t = document.createElement('div'); t.className = 'alto-edit-pill in-page'; t.setAttribute('role', 'group');
    t.setAttribute('aria-label', 'Edit this page'); t.innerHTML = pillHTML(true);
    dc.appendChild(t); wire(t); syncTiles();
  }

  /* ── what is editable on screen ───────────────────────────────────────── */
  var decT = null;
  function decorateSoon(){ clearTimeout(decT); decT = setTimeout(decorate, 0); }
  function setF(el, k){ if(!el || !k || !field(k)) return; el.classList.add('aed-f'); el.setAttribute('data-aed', k); }
  function decorate(){
    pageTile();
    if(!editing()) return;
    var P = page(), dc = document.getElementById('detail-content');
    if(P && dc && P.type === 'index') decorateIndex(P);
    if(P && dc){
      var kind = {node:'n', char:'c', env:'env', theme:'theme'}[P.type];
      if(kind){
        setF(dc.querySelector('.detail-name'), kind + '|' + P.id + '|' + (kind === 'n' ? 'title' : 'name'));
        if(kind === 'n') setF(dc.querySelector('.alto-lead'), 'n|' + P.id + '|desc');
        setF(dc.querySelector('.detail-role'), kind + '|' + P.id + '|' + (kind === 'n' ? 'tag' : 'role'));
      }
      var lastOwn = null;
      dc.querySelectorAll('.aed-k[data-k]').forEach(function(mk){
        var box = mk.closest('.detail-section'), h3 = box && box.querySelector(':scope > h3'); if(!h3) return; var k = mk.getAttribute('data-k');
        setF(h3, k + '|h'); box.setAttribute('data-aed-body', k + '|t'); lastOwn = box;
        Array.prototype.forEach.call(h3.parentNode.children, function(c){ if(c !== h3 && !c.classList.contains('adt') && !c.classList.contains('ast') && !c.classList.contains('alto-edit-pill') && !c.classList.contains('aed-lisadd')) c.classList.add('aed-f', 'aed-bodypart'); });
        if(structOK() && !h3.querySelector('.aed-sc')) h3.appendChild(ctl('aed-sc', [['up', '↑', 'Move this section up'], ['down', '↓', 'Move it down'], ['del', '✕', 'Remove this section']], {sk: k}));
        decorateLists(box, k, h3);
      });
      if(kind && structOK() && !dc.querySelector('.aed-add') && field(kind + '|' + P.id + '|order')){
        var add = document.createElement('button'); add.type = 'button'; add.className = 'aed-add'; add.textContent = '+ Add a section';
        add.setAttribute('data-x', 'addsec'); add.setAttribute('data-ok', kind + '|' + P.id);
        var tile = dc.querySelector(':scope > .alto-edit-pill');
        if(lastOwn && lastOwn.nextSibling) dc.insertBefore(add, lastOwn.nextSibling);
        else if(tile) dc.insertBefore(add, tile); else dc.appendChild(add);
      }
      if(kind === 'n'){ decorateFlags(false); decorateChips(false); }
      if(kind === 'n'){
        var seenT = {};
        dc.querySelectorAll('.hc-row').forEach(function(row){
          var a = row.querySelector('.hc-link[data-goto]'); if(!a) return; var t = a.getAttribute('data-goto');
          var j = seenT[t] = (t in seenT) ? seenT[t] + 1 : 0, k = 'cx|' + P.id + '|' + t + '|' + j;
          if(!field(k)) return;
          var how = row.querySelector('.hc-how');
          if(!how){ how = document.createElement('div'); how.className = 'hc-how aed-ph'; how.textContent = '+ Add how they connect'; row.appendChild(how); }
          setF(how, k);
        });
      }
      /*__STUDY_DECORATE__*/
      dc.querySelectorAll('.adt[data-adt-key]').forEach(function(bx){
        var key = bx.getAttribute('data-adt-key');
        var T0 = (window._ALTO_DT || {})[key], rootId = T0 && T0.n.filter(function(x){ return !x.p; })[0];
        bx.querySelectorAll('.adt-card[data-i]').forEach(function(c){
          var i = c.getAttribute('data-i');
          setF(c.querySelector('.adt-t'), 'dt|' + key + '|' + i + '|title');
          setF(c.querySelector('.adt-x'), 'dt|' + key + '|' + i + '|text');
          setF(c.querySelector('.adt-tag'), 'dt|' + key + '|' + i + '|tag');
          if(structOK() && !c.querySelector('.aed-tc')){
            var isRoot = rootId && rootId.i === i;
            c.appendChild(ctl('aed-tc', isRoot ? [['add', '+', 'Add a step under this one']]
              : [['add', '+', 'Add a step under this one'], ['up', '←', 'Move before its neighbour'], ['down', '→', 'Move after its neighbour'], ['del', '✕', 'Remove this step and the steps under it']], {tk: key, ts: i}));
          }
        });
        // a step without an answer or a tag gets a place to write one
        bx.querySelectorAll('.adt-sub[data-i] > .adt-edge').forEach(function(ed){
          if(!ed.querySelector('span')){ var sp = document.createElement('span'); sp.className = 'aed-ph'; sp.textContent = '+ answer'; ed.appendChild(sp); } });
        bx.querySelectorAll('.adt-card[data-i]').forEach(function(c){
          if(!c.querySelector('.adt-tag')){ var tg = document.createElement('div'); tg.className = 'adt-tag aed-ph'; tg.textContent = '+ tag'; c.insertBefore(tg, c.firstChild);
            setF(tg, 'dt|' + key + '|' + c.getAttribute('data-i') + '|tag'); } });
        bx.querySelectorAll('.adt-sub[data-i] > .adt-edge > span').forEach(function(sp){
          setF(sp, 'dt|' + key + '|' + sp.parentNode.parentNode.getAttribute('data-i') + '|edge');
        });
      });
    }
  }
  // Moving, adding and removing pieces is for a computer; phones edit words.
  function structOK(){ return !PHONE && !root.classList.contains('mobile'); }
  function ctl(cls, items, data){
    var w = document.createElement('span'); w.className = cls; w.contentEditable = 'false';
    Object.keys(data || {}).forEach(function(k){ w.setAttribute('data-' + k, data[k]); });
    items.forEach(function(it){ var b = document.createElement('button'); b.type = 'button'; b.setAttribute('data-x', it[0]);
      b.setAttribute('data-g', it[1]); b.title = it[2]; b.setAttribute('aria-label', it[2]); w.appendChild(b); });
    return w;
  }
  /* cards: + under a card (an outline), ✕ on a card with nothing under it,
     + Add a card beside each unit's name */
  function canRemove(id){ return !kidsOf(id).some(function(k){ return !cardGone(k); }); }
  function decorateCanvas(){
    document.querySelectorAll('.aed-uc').forEach(function(el){ el.parentNode.removeChild(el); });
    if(!editing() || !structOK() || !cardsBase()) return;
    var world = document.getElementById('world'); if(!world) return;
    var lbls = Array.prototype.slice.call(world.querySelectorAll('.phase-label-float')).sort(function(a, b){ return a.offsetTop - b.offsetTop; });
    lbls.forEach(function(l, i){
      var r = document.createElement('button'); r.type = 'button'; r.className = 'aed-uc aed-ur'; r.textContent = '✎ Rename';
      r.title = 'Rename this unit'; r.setAttribute('data-x', 'renu'); r.setAttribute('data-act', i);
      r.style.left = Math.round(l.offsetLeft + l.offsetWidth + 14) + 'px';
      r.style.top = Math.round(l.offsetTop + l.offsetHeight / 2 - 15) + 'px';
      world.appendChild(r);
      var b = document.createElement('button'); b.type = 'button'; b.className = 'aed-uc'; b.textContent = '+ Add a card';
      b.title = OUT ? 'Add a card to this unit, under its top card' : 'Add a card at the end of this unit';
      b.setAttribute('data-act', i);
      b.style.left = Math.round(l.offsetLeft + l.offsetWidth + 14 + r.offsetWidth + 8) + 'px';
      b.style.top = r.style.top;
      world.appendChild(b);
      var x = document.createElement('button'); x.type = 'button'; x.className = 'aed-uc aed-ux'; x.textContent = '✕ Delete unit';
      x.title = 'Delete this unit — you choose what happens to its cards'; x.setAttribute('data-x', 'delu'); x.setAttribute('data-act', i);
      x.style.left = Math.round(b.offsetLeft + b.offsetWidth + 8) + 'px'; x.style.top = r.style.top;
      world.appendChild(x);
    });
    // + Add a unit, at the foot of the last one
    var bands = Array.prototype.slice.call(world.querySelectorAll('.phase-band')).sort(function(a, b){ return a.offsetTop - b.offsetTop; });
    var last = bands[bands.length - 1];
    if(last){
      var u = document.createElement('button'); u.type = 'button'; u.className = 'aed-uc aed-unew'; u.textContent = '+ Add a unit';
      u.title = 'A new unit at the end, with its first card'; u.setAttribute('data-x', 'addunit');
      // under the lowest card of the last unit
      var low = 0, la = PHASE_META.length - 1;
      world.querySelectorAll('.node').forEach(function(n){ if(NODE_ACT[n.id.slice(5)] === la && n.offsetHeight) low = Math.max(low, n.offsetTop + n.offsetHeight); });
      var y = low ? low + 34 : last.offsetTop + last.offsetHeight - 150;
      u.style.left = '40px'; u.style.top = Math.round(y) + 'px';
      world.appendChild(u);
    }
  }
  document.addEventListener('mouseover', function(e){
    if(!editing() || !structOK() || PICK || LINK || !cardsBase()) return;
    var nodeEl = e.target && e.target.closest && e.target.closest('#canvas .node'); if(!nodeEl) return;
    var card = nodeEl.querySelector('.node-card'), id = nodeEl.id.replace(/^node-/, '');
    if(!card || card.querySelector(':scope > .aed-cc') || !srcNode(id)) return;
    var items = [];
    if(OUT) items.push(['addc', '+', 'Add a card under this one']);
    if(OUT && (OUT.parent || {})[id]) items.push(['linkc', '⇄', 'Move it, and the cards under it, under another card']);
    if(OUT && (OUT.parent || {})[id]) items.push(['swapc', '⇅', 'Swap places with a card beside it, or with the card it sits under']);
    if(LN) items.push(['linec', '⟿', 'Put it on another line — or start a new line']);
    items.push(['chipc', '◆', 'Chips: add one to this card, or take one off']);
    items.push(['delc', '✕', kidsOf(id).some(function(k){ return !cardGone(k); }) ? 'Remove this card — you choose what happens to the cards under it' : 'Remove this card']);
    if(items.length) card.appendChild(ctl('aed-cc', items, {cid: id}));
    if(!card.querySelector(':scope > .aed-rz')){ var rz = document.createElement('span'); rz.className = 'aed-rz'; rz.title = 'Drag to change its size';
      rz.setAttribute('aria-hidden', 'true'); rz.addEventListener('pointerdown', function(e){ startResize(e, id); }); card.appendChild(rz); }
  });
  function addCard(p, a){
    if(!cardsBase()) return;
    // an outline's unit has one card at its top (brief: one hub per unit): a
    // card added to the unit goes under it
    if(!p && OUT){ var hub = NODES_SRC.filter(function(n){ return NODE_ACT[n.id] === a && !(OUT.parent || {})[n.id]; })[0]; if(hub) p = hub.id; }
    var id = rid('card-'), par = p ? srcNode(p) : null, act = par ? NODE_ACT[p] : a;
    var inAct = NODES_SRC.filter(function(n){ return NODE_ACT[n.id] === act; }), like = par || inAct[inAct.length - 1] || null;
    var spec = {p: p || '', a: unitKeyOf(act), t: 'New ' + String(EDK.noun || 'card').toLowerCase(), g: like ? like.tag || '' : '', d: '', c: like ? like.color : 'var(--accent)'};
    if(!OUT) spec.col = like && like.col ? like.col : 'center';
    if(!change('nn|' + id, spec)) return;
    toast('Card added — ⌘Z takes it back.');
    setTimeout(function(){ var el = document.querySelector('#node-' + id + ' .node-title');
      if(el){ try{ el.scrollIntoView({block:'center', inline:'nearest'}); }catch(_){} startField(el, 'n|' + id + '|title'); try{ document.execCommand('selectAll'); }catch(_){} } }, 140);
  }
  /* units: add one at the end (with its first card), rename one */
  var UNIT_COLORS = ['#e0654a', '#4a9eff', '#2fb380', '#c084fc', '#f2a93b', '#ec6fa8', '#22b8cf', '#8f9c3a', '#b07a4f', '#7c83f2'];
  function labelEl(i){ var all = Array.prototype.slice.call(document.querySelectorAll('#world .phase-label-float')).sort(function(a, b){ return a.offsetTop - b.offsetTop; }); return all[i] || null; }
  function renameUnit(i){
    var el = labelEl(i); if(!el) return; var u = unitKeyOf(i);
    startField(el, typeof u === 'string' ? 'nl|' + u : 'u|' + i + '|label'); try{ document.execCommand('selectAll'); }catch(_){}
  }
  function addUnit(){
    var B = cardsBase(); if(!B) return;
    var used = {}; PHASE_META.forEach(function(pm){ used[String(pm.colorRaw || '').toLowerCase()] = 1; });
    var col = UNIT_COLORS.filter(function(c){ return !used[c]; })[0] || UNIT_COLORS[PHASE_META.length % UNIT_COLORS.length];
    var uid = rid('unit-'), cid = rid('card-'), n = PHASE_META.length;
    var spec = {p: '', a: uid, t: 'New ' + String(EDK.noun || 'card').toLowerCase(), g: '', d: '', c: col};
    if(!OUT) spec.col = 'center';
    if(!changes([['nu|' + uid, {n: Date.now(), c: col, l: 'New unit'}], ['nn|' + cid, spec]])) return;
    toast('Unit added — name it, then fill in its first card.');
    setTimeout(function(){ var el = labelEl(n); if(el){ try{ el.scrollIntoView({block:'center'}); }catch(_){} renameUnit(n); } }, 160);
  }
  /* moving a card (and what hangs under it) under another card: click it */
  var LINK = null;
  function startLink(id){
    if(!OUT || !(OUT.parent || {})[id]) return;
    endPick(true);
    LINK = {id: id, S: dfsOf(OUT.kids || {}, id)};
    var t = document.getElementById('aed-toast'); if(t) t.classList.remove('show');
    root.classList.add('aed-linking'); paintLink();
  }
  function endLink(){
    if(!LINK) return; LINK = null; root.classList.remove('aed-linking');
    document.querySelectorAll('.aed-link-no,.aed-link-at').forEach(function(el){ el.classList.remove('aed-link-no', 'aed-link-at'); });
    var b = document.getElementById('aed-linkbar'); if(b) b.classList.remove('show');
  }
  function paintLink(){
    if(!LINK) return;
    var P = (OUT && OUT.parent) || {};
    document.querySelectorAll('#world .node').forEach(function(el){ var i = el.id.slice(5);
      el.classList.toggle('aed-link-no', LINK.S.indexOf(i) >= 0); el.classList.toggle('aed-link-at', P[LINK.id] === i); });
    var b = document.getElementById('aed-linkbar');
    if(!b){ b = document.createElement('div'); b.id = 'aed-linkbar';
      b.innerHTML = '<span class="ap-t"></span><button type="button">Cancel</button>';
      b.querySelector('button').addEventListener('click', function(e){ e.stopPropagation(); endLink(); });
      document.body.appendChild(b); }
    var n = srcNode(LINK.id);
    b.querySelector('.ap-t').textContent = 'Click the card “' + (n ? n.title : '') + '” should go under' + (LINK.S.length > 1 ? ' — the ' + (LINK.S.length - 1) + ' under it come along' : '') + ' · Esc to cancel';
    b.classList.add('show');
  }
  function relink(id, np){
    var S = dfsOf((OUT && OUT.kids) || {}, id);
    if(S.indexOf(np) >= 0){ toast('A card cannot go under itself or a card under it.'); return false; }
    if(((OUT && OUT.parent) || {})[id] === np){ endLink(); return false; }
    var ok, to = srcNode(np);
    if(isNew(id)){ var sp = JSON.parse(JSON.stringify(NEWC[id].spec)); sp.p = np; sp.a = unitKeyOf(NODE_ACT[np]); ok = change('nn|' + id, sp); }
    else {
      var L = [['rp|' + id, np]];
      ['shift', 'slide'].forEach(function(hk){ var sf = field('p|' + id + '|' + hk); if(sf && sf.get()) L.push(['p|' + id + '|' + hk, null]); });
      ok = changes(L);
    }
    endLink();
    if(ok) toast('Moved under “' + (to ? to.title : '') + '” — ⌘Z puts it back.');
    return ok;
  }
  /* ── a horizontal timeline (lanes.py): when, which line, the lines ───── */
  var LN = window._ALTO_LANES || null, LN0 = LN ? JSON.parse(JSON.stringify(LN)) : null, LPICK = null;
  function lanesWhen(s){                                 // lanes.parse_when, the common cases
    s = String(s || '').trim().toLowerCase(); if(!s) return null;
    var m = /^(-?\d{1,6})(?:-(\d{1,2}))?(?:-(\d{1,2}))?$/.exec(s);
    if(m){ var y = +m[1], mo = +(m[2] || 0), d = +(m[3] || 0); if(!mo) return y;
      var D = [31,28,31,30,31,30,31,31,30,31,30,31], n = 0; for(var i = 0; i < Math.min(12, mo) - 1; i++) n += D[i]; return y + (n + Math.max(0, (d || 1) - 1)) / 365; }
    var bc = /(\d+)\s*b\.?\s?c/.exec(s); if(bc) return -(+bc[1]);
    var x = /-?\d+(?:\.\d+)?/.exec(s); return x ? +x[0] : null;
  }
  function laneOf(id){ var l = null; (LN.lines || []).forEach(function(q){ if(q.id === id) l = q; }); return l; }
  function laneField(kind, id, f){
    if(kind === 'ln'){
      var l0 = null; (LN0.lines || []).forEach(function(q){ if(q.id === id) l0 = q; });
      return {kind:'card', sig:function(){ return l0; }, get:function(){ var l = laneOf(id); return l ? JSON.parse(JSON.stringify(l)) : null; },
        set:function(v){ var i = -1; LN.lines.forEach(function(q, j){ if(q.id === id) i = j; });
          if(!v){ if(i >= 0) LN.lines.splice(i, 1); } else if(i >= 0) LN.lines[i] = Object.assign({}, v, {id: id}); else LN.lines.push(Object.assign({}, v, {id: id})); }};
    }
    if(!srcNode(id)) return null;
    var e0 = (LN0.ev || {})[id] || {l: 'main', w: '', t: null};
    var ev = function(){ return LN.ev[id] = LN.ev[id] || {l: 'main', w: '', t: null}; };
    if(f === 'when') return {kind:'plain', sig:function(){ return e0.w || ''; }, get:function(){ return ev().w || ''; },
      set:function(v){ var q = ev(); q.w = String(v || '').trim(); q.t = lanesWhen(q.w); }};
    return {kind:'card', sig:function(){ return e0.l === 'main' ? '' : e0.l; }, get:function(){ var l = ev().l; return l === 'main' ? '' : l; },
      set:function(v){ ev().l = v || 'main'; }};
  }
  function lineName(lid){ if(!lid || lid === 'main') return LN.main || 'The main line'; var l = laneOf(lid); return l ? l.label : lid; }
  function lineMenu(id){
    var at = (LN.ev[id] || {}).l || 'main', A = [];
    [{id: 'main'}].concat(LN.lines).forEach(function(l){ if(l.id === at) return;
      A.push({t: 'Onto “' + lineName(l.id) + '”', sub: l.id === 'main' ? 'The line everything else branches off.' : 'It keeps its date; the line runs through it.',
        fn: function(){ if(change('n|' + id + '|line', l.id === 'main' ? '' : l.id)) toast('“' + titleOf(id) + '” is on “' + lineName(l.id) + '” now — ⌘Z puts it back.'); }}); });
    A.push({t: '+ A new line for it…', sub: 'A storyline of its own — a person, a place, a flashback. You choose where it branches off and joins the main line next.',
      fn: function(){ newLine(id); }});
    ask('Which line is “' + titleOf(id) + '” on?', 'Now: “' + lineName(at) + '”.', A);
  }
  var LINE_COLORS = ['#e07a5f', '#3d9a8b', '#8a6fd1', '#d4a017', '#4a90d9', '#c2577a', '#5a9e4b', '#b8763e'];
  function newLine(id){
    var nd = srcNode(id), at = (nd && nd.id && document.getElementById('node-' + id)) || document.body;
    askName(at, 'Name the new line', '', function(v){
      v = String(v || '').replace(/\s+/g, ' ').trim(); if(!v) return;
      var lid = 'line-' + Math.random().toString(36).slice(2, 7), n = LN.lines.length;
      var spec = {id: lid, label: v, color: LINE_COLORS[n % LINE_COLORS.length], side: n % 2 ? 'below' : 'above', from: '', to: ''};
      if(changes([['ln|' + lid, spec], ['n|' + id + '|line', lid]])) toast('“' + v + '” is a new line — click its label to choose where it branches off and joins.');
    });
  }
  function laneMenu(lid){
    if(lid === 'main'){ var el = document.querySelector('.lanes-tag[data-ln-tag=main]');
      toast('The main line runs through everything — its name is changed by Claude for now.'); return; }
    var l = laneOf(lid); if(!l) return;
    var has = Object.keys(LN.ev).some(function(i){ return LN.ev[i].l === lid && srcNode(i) && !cardGone(i); });
    var put = function(ch, msg){ var v = Object.assign({}, l, ch); if(change('ln|' + lid, v)) toast(msg + ' — ⌘Z puts it back.'); };
    var A = [
      {t: 'Rename it…', fn: function(){ askName(document.querySelector('.lanes-tag[data-ln-tag="' + lid + '"]') || document.body, 'Name this line', l.label, function(v){
        v = String(v || '').replace(/\s+/g, ' ').trim(); if(v && v !== l.label) put({label: v}, 'Renamed'); }); }},
      {t: l.from ? 'It branches off at “' + titleOf(l.from) + '” — change…' : 'Branch it off an event…', sub: 'Click the event on another line where it splits away.',
        fn: function(){ startLinePick(lid, 'from'); }},
      {t: l.to ? 'It joins at “' + titleOf(l.to) + '” — change…' : 'Join it into an event…', sub: 'Click the event where it converges — for a flashback, where the story brings it up.',
        fn: function(){ startLinePick(lid, 'to'); }}];
    if(l.from) A.push({t: 'Start it on its own', sub: 'No branch point: it begins just before its first event.', fn: function(){ put({from: ''}, 'It starts on its own'); }});
    if(l.to) A.push({t: 'Let it run on', sub: 'It does not join another line.', fn: function(){ put({to: ''}, 'It runs on'); }});
    A.push({t: 'Move it ' + (l.side === 'below' ? 'above' : 'below') + ' the main line', fn: function(){ put({side: l.side === 'below' ? 'above' : 'below'}, 'Moved'); }});
    A.push({t: 'Remove this line', cls: 'aa-danger', off: has, why: 'Put its events on another line first.', fn: function(){ if(change('ln|' + lid, null)) toast('Line removed — ⌘Z puts it back.'); }});
    ask('The line “' + l.label + '”', has ? '' : 'It has no events yet: put one on it with ⟿ on a card.', A);
  }
  function startLinePick(lid, which){
    LPICK = {lid: lid, which: which};
    var b = document.getElementById('aed-linkbar');
    if(!b){ b = document.createElement('div'); b.id = 'aed-linkbar';
      b.innerHTML = '<span class="ap-t"></span><button type="button">Cancel</button>';
      b.querySelector('button').addEventListener('click', function(e){ e.stopPropagation(); endLinePick(); endLink(); });
      document.body.appendChild(b); }
    b.querySelector('.ap-t').textContent = (which === 'from' ? 'Click the event “' + lineName(lid) + '” branches off from' : 'Click the event “' + lineName(lid) + '” joins into') + ' · Esc to cancel';
    b.classList.add('show');
  }
  function endLinePick(){ LPICK = null; var b = document.getElementById('aed-linkbar'); if(b && !LINK) b.classList.remove('show'); }
  function linePicked(id){
    var P = LPICK; endLinePick(); var l = laneOf(P.lid); if(!l) return;
    if(((LN.ev[id] || {}).l || 'main') === P.lid){ toast('That event is on this line — pick one on the line it ' + (P.which === 'from' ? 'branches off' : 'joins') + '.'); return; }
    var ch = {}; ch[P.which] = id;
    if(change('ln|' + P.lid, Object.assign({}, l, ch))) toast('“' + l.label + '” ' + (P.which === 'from' ? 'branches off at' : 'joins at') + ' “' + titleOf(id) + '” — ⌘Z puts it back.');
  }
  document.addEventListener('keydown', function(e){ if(e.key === 'Escape' && LPICK){ e.preventDefault(); e.stopPropagation(); endLinePick(); } }, true);
  /* swapping places: with a card under the same card, or with that card */
  function numOf(id){ return (typeof NODE_ORDER_MAP !== 'undefined' && NODE_ORDER_MAP[id]) || ''; }
  // every card's number as it would be with the outline changed by fn(kids, par)
  function numsIf(fn){
    var K = JSON.parse(JSON.stringify((OUT && OUT.kids) || {})), P = Object.assign({}, (OUT && OUT.parent) || {}),
        Q = ACT_SEQS.map(function(q){ return q.slice(); }); fn(K, P, Q);
    var drop = function(L){ return L.filter(function(i){ return !cardGone(i); }); };
    Object.keys(K).forEach(function(k){ K[k] = drop(K[k]); });
    return window._altoPathNums(Q.map(drop), K, P);
  }
  function orderWith(p, list){ return function(K){ K[p] = list.slice(); }; }
  function swapSibs(id, other, how){
    var p = ((OUT && OUT.parent) || {})[id], list = kidsOf(p).slice(), i = list.indexOf(id), j = list.indexOf(other);
    if(i < 0 || j < 0) return null;
    if(how === 'move'){ list.splice(i, 1); list.splice(j, 0, id); }        // it takes that turn; the ones between move along
    else { list[i] = other; list[j] = id; }
    return list;
  }
  function doOrder(id, list, what){
    var p = ((OUT && OUT.parent) || {})[id];
    if(change('so|' + p, list)) toast(what + ' — ⌘Z puts them back.');
  }
  function doParentSwap(id){
    var p = ((OUT && OUT.parent) || {})[id]; if(!p) return;
    var L = [['sx|' + id, p]];
    [id, p].forEach(function(i){ ['shift', 'slide'].forEach(function(hk){ var sf = field('p|' + i + '|' + hk); if(sf && sf.get()) L.push(['p|' + i + '|' + hk, null]); }); });
    if(!field('sx|' + id)){ toast('Only a card the page was built with can trade places with its parent — ask Claude to do it, or build first.'); return; }
    if(changes(L)) toast('“' + titleOf(id) + '” and “' + titleOf(p) + '” traded places — ⌘Z puts them back.');
  }
  function swapChoices(id){
    var P = (OUT && OUT.parent) || {}, p = P[id], A = [];
    if(!p) return A;
    var sib = kidsOf(p).filter(function(k){ return !cardGone(k); }), i = sib.indexOf(id);
    if(!field('so|' + p)) sib = [];
    sib.forEach(function(k, j){ if(k === id) return;
      var list = swapSibs(id, k, 'swap'), nn = numsIf(orderWith(p, list));
      A.push({t: 'Swap with ' + (numOf(k) ? numOf(k) + ' ' : '') + '“' + titleOf(k) + '”' + (j === i - 1 ? ' (above)' : j === i + 1 ? ' (below)' : ''),
        sub: 'It becomes ' + nn[id] + ', and “' + titleOf(k) + '” ' + nn[k] + '. The cards under each go with it.',
        fn: function(){ doOrder(id, list, 'Swapped'); }}); });
    var g = P[p];
    A.push({label: 'Its parent'});
    var nx = numsIf(function(K, Q){ var S = (K[p] || []).slice(), Kc = (K[id] || []).slice(), gg = Q[p];
      if(gg){ K[gg] = K[gg].map(function(x){ return x === p ? id : x; }); Q[id] = gg; } else delete Q[id];
      K[id] = S.map(function(x){ return x === id ? p : x; }); K[id].forEach(function(x){ Q[x] = id; });
      if(Kc.length){ K[p] = Kc; Kc.forEach(function(x){ Q[x] = p; }); } else delete K[p]; });
    var kn = liveKids(id).length;
    A.push({t: 'Trade places with ' + (numOf(p) ? numOf(p) + ' ' : '') + '“' + titleOf(p) + '”', off: !field('sx|' + id), why: 'Cards added here trade places once the timeline is built again.',
      sub: 'It becomes ' + nx[id] + (g ? '' : ', the top of its unit') + '; “' + titleOf(p) + '” and the cards under it go under it, as ' + nx[p] +
        (kn ? '. The ' + (kn === 1 ? 'card' : kn + ' cards') + ' under this one go under “' + titleOf(p) + '”.' : '.'),
      fn: function(){ doParentSwap(id); }});
    return A;
  }
  function swapMenu(id){
    var A = swapChoices(id); if(!A.length) return;
    ask('Swap “' + titleOf(id) + '” (' + numOf(id) + ') with…', 'Cards trade places with a card under the same card, or with the card they sit under. You can also click a card’s number and type the one it should have.', A);
  }
  // A card's number, typed: it goes there. The number names the card it goes
  // under (all but the last mark) and its place among that card's children
  // (the last mark); the card that held that place and the ones after it move
  // along one. Always asked first, saying what each card becomes.
  function renumber(id, typed){
    var want = String(typed || '').trim().toLowerCase().replace(/[.\s]+$/, ''); if(!want || want === numOf(id)) return;
    var eg = numOf(id) || '1.a';
    var pn = window._altoParseNum(want);
    if(!pn){ toast('Type a number like ' + eg + ' — the unit, then a letter, then .1, .1, -1, then letters again.'); return; }
    if(!pn.idx.length){ toast(pn.unit + ' is the top card of unit ' + pn.unit + '. To put this card there, use ⇅ and trade places with it.'); return; }
    var P = (OUT && OUT.parent) || {}, p = P[id];
    var pnum = window._altoFormatNum(pn.unit, pn.idx.slice(0, -1)), pos = pn.idx[pn.idx.length - 1];
    var np = Object.keys(NODE_ORDER_MAP).filter(function(k){ return NODE_ORDER_MAP[k] === pnum && srcNode(k) && !cardGone(k); })[0];
    if(!np){ toast('No card is numbered ' + pnum + ', so there is nothing for it to go under.'); return; }
    if(branchOf(id).indexOf(np) >= 0){ toast(pnum + ' is this card or a card under it — a card cannot go under itself.'); return; }
    var sibs = liveKids(np).filter(function(k){ return k !== id; });
    var at = Math.min(pos, sibs.length), list = sibs.slice(); list.splice(at, 0, id);
    var holder = liveKids(np)[pos], same = np === p;
    if(same && liveKids(np).join('|') === list.join('|')) return;
    // the whole child list as the page knows it (cards taken out keep their turns)
    var full = kidsOf(np).filter(function(k){ return k !== id; }), fi = holder ? full.indexOf(holder) : -1;
    if(fi < 0){ var lastLive = sibs[at - 1]; fi = lastLive ? full.indexOf(lastLive) + 1 : 0; }
    full.splice(fi, 0, id);
    var nn = numsIf(function(K, Q, S){
      if(!same){ if(p && K[p]) K[p] = K[p].filter(function(x){ return x !== id; }); Q[id] = np;
        var ua = NODE_ACT[id], ub = NODE_ACT[np];
        if(ua !== ub && S[ua] && S[ub]){ var br = branchOf(id); S[ua] = S[ua].filter(function(x){ return br.indexOf(x) < 0; }); S[ub] = S[ub].concat(br); } }
      K[np] = full.slice(); });
    var lands = nn[id] || want;
    var tail = holder && holder !== id ? ' “' + titleOf(holder) + '” becomes ' + nn[holder] + (liveKids(np).length - pos > 1 ? ', and the cards after it move along one.' : '.') : '';
    var under = liveKids(id).length ? ' The ' + (liveKids(id).length === 1 ? 'card' : liveKids(id).length + ' cards') + ' under it go with it.' : '';
    var where = same ? '' : ' It moves under “' + titleOf(np) + '” (' + pnum + ').';
    var note = (pos > sibs.length ? (sibs.length ? pnum + ' has ' + sibs.length + ' ' + (sibs.length === 1 ? 'card' : 'cards') + ' under it, so it goes last, as ' + lands + '.' : 'Nothing is under ' + pnum + ' yet, so it becomes ' + lands + '.') : '') + where + tail + under;
    ask('Move “' + titleOf(id) + '” to ' + lands + '?', note.trim(), [{t: 'Yes, make it ' + lands, fn: function(){ moveTo(id, np, full, same); }}]);
  }
  function moveTo(id, np, full, same){
    var L = [];
    if(!same){
      if(isNew(id)){ var sp = JSON.parse(JSON.stringify(NEWC[id].spec)); sp.p = np; sp.a = unitKeyOf(NODE_ACT[np]); L.push(['nn|' + id, sp]); }
      else { L.push(['rp|' + id, np]);
        ['shift', 'slide'].forEach(function(hk){ var sf = field('p|' + id + '|' + hk); if(sf && sf.get()) L.push(['p|' + id + '|' + hk, null]); }); }
    }
    // its turn among the children: only a card the page was built with keeps an order
    var later = false;
    if(!(full[full.length - 1] === id && !same)){
      if(field('so|' + np)) L.push(['so|' + np, full]);
      else if(same){ toast('Cards added here take a place by number once the timeline is built again.'); return; }
      else later = true;
    }
    if(later){ if(changes(L)) toast('Moved under “' + titleOf(np) + '” — it takes its place by number once the timeline is built again. ⌘Z puts it back.'); return; }
    if(changes(L)) toast('Moved to ' + (numOf(id) || '') + ' — ⌘Z puts it back.');
  }
  /* asking: a title, a line, and the answers (the last one cancels) */
  function ask(title, note, answers){
    var w = document.getElementById('aed-ask');
    if(!w){ w = document.createElement('div'); w.id = 'aed-ask'; w.innerHTML = '<div class="aa-box" role="dialog" aria-modal="true"></div>';
      w.addEventListener('mousedown', function(e){ e.stopPropagation(); if(e.target === w) closeAsk(); });
      w.addEventListener('click', function(e){ e.stopPropagation(); });
      document.body.appendChild(w); }
    var box = w.querySelector('.aa-box'); box.innerHTML = '';
    var h = document.createElement('h4'); h.textContent = title; box.appendChild(h);
    if(note){ var p = document.createElement('p'); p.textContent = note; box.appendChild(p); }
    answers.forEach(function(an){
      if(an.label){ var l = document.createElement('div'); l.className = 'aa-l'; l.textContent = an.label; box.appendChild(l); return; }
      var b = document.createElement('button'); b.type = 'button'; b.className = an.cls || '';
      b.appendChild(document.createTextNode(an.t)); if(an.sub){ var sm = document.createElement('small'); sm.textContent = an.sub; b.appendChild(sm); }
      if(an.off){ b.disabled = true; if(an.why) b.title = an.why; }
      b.addEventListener('click', function(e){ e.stopPropagation(); closeAsk(); if(an.fn) an.fn(); });
      box.appendChild(b); });
    var c = document.createElement('button'); c.type = 'button'; c.className = 'aa-quiet'; c.textContent = 'Cancel';
    c.addEventListener('click', function(e){ e.stopPropagation(); closeAsk(); }); box.appendChild(c);
    w.classList.add('show'); setTimeout(function(){ c.focus(); }, 0);
  }
  function closeAsk(){ var w = document.getElementById('aed-ask'); if(w) w.classList.remove('show'); }
  document.addEventListener('keydown', function(e){ if(e.key === 'Escape'){ var w = document.getElementById('aed-ask'); if(w && w.classList.contains('show')){ e.preventDefault(); e.stopPropagation(); closeAsk(); } } }, true);

  function titleOf(id){ var n = srcNode(id); return n ? txt(n.title || '') || 'Untitled' : ''; }
  function liveKids(id){ return kidsOf(id).filter(function(k){ return !cardGone(k); }); }
  function branchOf(id){ var out = [id]; (function walk(x){ liveKids(x).forEach(function(k){ out.push(k); walk(k); }); })(id); return out; }
  function unitIds(i){ return NODES_SRC.filter(function(n){ return NODE_ACT[n.id] === i && !cardGone(n.id); }).map(function(n){ return n.id; }); }
  function unitTop(i){ var P = (OUT && OUT.parent) || {}; return unitIds(i).filter(function(id){ return !P[id]; })[0] || null; }
  function unitName(i){ var pm = PHASE_META[i]; return pm ? txt(pm.label || '') || ('Unit ' + (i + 1)) : ''; }
  function delOps(ids){ return ids.map(function(m){ return isNew(m) ? ['nn|' + m, null] : ['nd|' + m, 1]; }); }
  // a card under another (np), or the top of its unit (np === '')
  function underOps(kid, np, unitKey){
    if(isNew(kid)){ var sp = JSON.parse(JSON.stringify(NEWC[kid].spec)); sp.p = np;
      if(!np) sp.a = unitKey != null ? unitKey : unitKeyOf(NODE_ACT[kid]); return ['nn|' + kid, sp]; }
    return ['rp|' + kid, np];
  }
  // a card (and, in an outline, all under it) into another unit
  function intoOps(id, key){
    if(isNew(id)){ var sp = JSON.parse(JSON.stringify(NEWC[id].spec)); sp.a = key; sp.p = ''; return ['nn|' + id, sp]; }
    return ['ua|' + id, key];
  }
  function removeCard(id){
    var a = NODE_ACT[id], K = liveKids(id), par = ((OUT && OUT.parent) || {})[id] || '', all = unitIds(a);
    var T = titleOf(id), n = branchOf(id).length - 1;
    function done(ok, msg){ if(ok) toast(msg + ' — ⌘Z brings it back.'); }
    if(all.length <= 1){ deleteUnit(a); return; }
    if(!K.length){ done(changes(delOps([id])), 'Card removed'); return; }
    var below = n === 1 ? 'the card under it' : 'the ' + n + ' cards under it';
    var A = [];
    if(par) A.push({t: 'Remove it and ' + below, cls: 'aa-danger', fn: function(){ done(changes(delOps(branchOf(id))), 'Removed with ' + below); }});
    A.push({t: 'Remove just this card',
      sub: par ? (K.length === 1 ? 'The card under it moves up under “' + titleOf(par) + '”.' : 'Its ' + K.length + ' cards move up under “' + titleOf(par) + '”.')
               : '“' + titleOf(K[0]) + '” takes its place at the top of the unit' + (K.length > 1 ? ', with the others under it.' : '.'),
      fn: function(){
        var L = par ? K.map(function(k){ return underOps(k, par); })
                    : [underOps(K[0], '')].concat(K.slice(1).map(function(k){ return underOps(k, K[0]); }));
        done(changes(L.concat(delOps([id]))), 'Card removed'); }});
    if(!par) A.push({t: 'Delete the whole unit…', cls: 'aa-danger', sub: 'This is its top card: you choose what happens to the unit’s cards.', fn: function(){ deleteUnit(a); }});
    ask('Remove “' + T + '”?', 'It has ' + below.replace(/^the /, '') + '.', A);
  }
  /* deleting a unit: its cards go to another unit, to a new unit, or with it */
  function unitGoneOp(i){ var k = unitKeyOf(i); return typeof k === 'string' ? ['nu|' + k, null] : ['ud|' + k, 1]; }
  function deleteUnit(i){
    var ids = unitIds(i), N = ids.length, U = PHASE_META.length, nm = unitName(i);
    var few = U <= 2, why = 'A timeline keeps at least two units.';
    var cards = N === 1 ? 'its card' : 'its ' + N + ' cards';
    var A = [{label: 'Move ' + cards + ' to'}];
    for(var j = 0; j < U; j++) if(j !== i) (function(j){ A.push({t: unitName(j), off: few, why: why, fn: function(){ moveUnit(i, j); }}); })(j);
    A.push({t: 'A new unit', sub: 'At the end, under a name you choose.', fn: function(){ moveUnitNew(i); }});
    A.push({label: 'Or'});
    A.push({t: 'Delete ' + (N === 1 ? 'its card' : 'all ' + N + ' cards') + ' too', cls: 'aa-danger', off: few, why: why,
      fn: function(){ if(changes(delOps(ids).concat([unitGoneOp(i)]))) toast('Unit deleted — ⌘Z brings it back.'); }});
    ask('Delete the unit “' + nm + '”?', few ? why + ' Its cards can still go to a new unit.' : 'It has ' + N + (N === 1 ? ' card.' : ' cards.'), A);
  }
  function moveUnit(i, j){
    var ids = unitIds(i), key = unitKeyOf(j), L;
    if(OUT){ var top = unitTop(i), tt = unitTop(j); if(!top || !tt) return;
      L = [underOps(top, tt)]; }
    else L = ids.map(function(id){ return intoOps(id, key); });
    var tn = unitName(j);
    if(changes(L.concat([unitGoneOp(i)]))) toast('Unit deleted — its cards are in “' + tn + '”. ⌘Z undoes it.');
  }
  function moveUnitNew(i){
    var ids = unitIds(i), used = {};
    PHASE_META.forEach(function(pm){ used[String(pm.colorRaw || '').toLowerCase()] = 1; });
    var col = UNIT_COLORS.filter(function(c){ return !used[c]; })[0] || UNIT_COLORS[PHASE_META.length % UNIT_COLORS.length];
    var uid = rid('unit-'), L = [['nu|' + uid, {n: Date.now(), c: col, l: 'New unit'}]];
    if(OUT){ var top = unitTop(i); if(!top) return; L.push(intoOps(top, uid)); }
    else ids.forEach(function(id){ L.push(intoOps(id, uid)); });
    if(!changes(L.concat([unitGoneOp(i)]))) return;
    toast('Its cards are in a new unit — name it.');
    setTimeout(function(){ var n = PHASE_META.length - 1, el = labelEl(n); if(el){ try{ el.scrollIntoView({block:'center'}); }catch(_){} renameUnit(n); } }, 160);
  }

  /* filters of the owner's own: on a card's page, which it is in */
  function decorateFlags(again){
    var P = page(), dc = document.getElementById('detail-content'); if(!P || P.type !== 'node' || !dc) return;
    var old = dc.querySelector('.aed-flags');
    if(old && !again) return;
    if(!editing() || !structOK() || !srcNode(P.id)){ if(old) old.parentNode.removeChild(old); return; }
    var row = document.createElement('div'); row.className = 'aed-flags'; row.contentEditable = 'false';
    var h = document.createElement('span'); h.className = 'aed-fh'; h.textContent = 'Filters'; row.appendChild(h);
    var mine = FLN[P.id] || [];
    FLAGS.forEach(function(f){ var b = document.createElement('button'); b.type = 'button'; b.className = 'aed-fchip' + (mine.indexOf(f.id) >= 0 ? ' on' : '');
      b.setAttribute('data-x', 'fltoggle'); b.setAttribute('data-fl', f.id); b.textContent = f.name; b.style.setProperty('--c', f.color || 'var(--accent)'); row.appendChild(b); });
    var add = document.createElement('button'); add.type = 'button'; add.className = 'aed-fchip aed-fnew'; add.setAttribute('data-x', 'flnew'); add.textContent = '+ New filter'; row.appendChild(add);
    if(old) old.parentNode.replaceChild(row, old);
    else { var hd = dc.querySelector('.detail-header'); if(hd && hd.parentNode === dc) dc.insertBefore(row, hd.nextSibling); else dc.insertBefore(row, dc.firstChild); }
  }
  /* sub-chips: on a card's page, the chips it carries — take one off, add one
     the timeline has, or make a new one */
  function aOne(k){ var w = String(k.one || 'chip').toLowerCase(); return (/^[aeiou]/.test(w) ? 'an ' : 'a ') + w; }
  function chipKinds(){ return (EDK.chipk || []).concat(newKinds()).filter(function(k){ return reg(k.r) && !XA[k.fk]; }); }
  // The chips a card carries, by kind: ✕ takes one off, + Add puts one on.
  function chipBox(nid){
    var n = srcNode(nid); if(!n) return null;
    var box = document.createElement('div'); box.className = 'aed-chips'; box.contentEditable = 'false';
    chipKinds().forEach(function(k){
      var R = reg(k.r) || {}, row = document.createElement('div'); row.className = 'aed-chrow';
      var h = document.createElement('span'); h.className = 'aed-fh'; h.textContent = k.l; row.appendChild(h);
      (n[k.f] || []).forEach(function(v){
        if(chipGone(k.r, v)) return;
        var c = document.createElement('span'); c.className = 'aed-chip'; var it = R[v];
        c.style.setProperty('--c', it && it.color ? it.color : 'var(--accent)');
        c.appendChild(document.createTextNode(it ? txt(it.name) : v));
        if((n[k.f] || []).length > 1) [['‹', -1, 'Move this chip earlier'], ['›', 1, 'Move this chip later']].forEach(function(m){
          var mv = document.createElement('button'); mv.type = 'button'; mv.className = 'aed-chmv'; mv.setAttribute('data-x', 'chipmv'); mv.setAttribute('data-f', k.f); mv.setAttribute('data-v', v); mv.setAttribute('data-nid', nid); mv.setAttribute('data-d', m[1]);
          mv.title = m[2]; mv.setAttribute('aria-label', m[2]); mv.textContent = m[0]; c.appendChild(mv); });
        var x = document.createElement('button'); x.type = 'button'; x.setAttribute('data-x', 'chipdel'); x.setAttribute('data-f', k.f); x.setAttribute('data-v', v); x.setAttribute('data-nid', nid);
        x.title = 'Take this chip off the card'; x.setAttribute('aria-label', x.title); x.textContent = '✕'; c.appendChild(x);
        row.appendChild(c); });
      var add = document.createElement('button'); add.type = 'button'; add.className = 'aed-chadd'; add.setAttribute('data-x', 'chipadd'); add.setAttribute('data-f', k.f); add.setAttribute('data-nid', nid);
      add.textContent = '+ Add'; add.title = 'Add ' + aOne(k) + ' to this card'; row.appendChild(add);
      box.appendChild(row);
    });
    return box;
  }
  function decorateChips(again){
    var P = page(), dc = document.getElementById('detail-content'); if(!P || P.type !== 'node' || !dc) return;
    var old = dc.querySelector(':scope > .aed-chips');
    if(old && !again) return;
    if(!editing() || !structOK() || !srcNode(P.id)){ if(old) old.parentNode.removeChild(old); return; }
    var box = chipBox(P.id);
    if(old) old.parentNode.replaceChild(box, old);
    else { var fl = dc.querySelector('.aed-flags'), hd = dc.querySelector('.detail-header');
      if(fl && fl.parentNode === dc) dc.insertBefore(box, fl.nextSibling);
      else if(hd && hd.parentNode === dc) dc.insertBefore(box, hd.nextSibling); else dc.insertBefore(box, dc.firstChild); }
  }
  // the same, for a card on the timeline: ◆ on the card opens it beside the card
  function chipPop(nid, at){
    hideMenus();
    var w = document.getElementById('aed-chpop');
    if(!w){ w = document.createElement('div'); w.id = 'aed-chpop';
      w.addEventListener('mousedown', function(e){ e.stopPropagation(); });
      w.addEventListener('click', function(e){ var b = e.target.closest('button'); if(!b) return; e.stopPropagation(); e.preventDefault(); structure(b); });
      document.body.appendChild(w); }
    w._nid = nid; w.innerHTML = '';
    var h = document.createElement('h5'); h.textContent = 'Chips on “' + titleOf(nid) + '”'; w.appendChild(h);
    var box = chipBox(nid); if(!box) return; w.appendChild(box);
    if(!chipKinds().length){ var none = document.createElement('p'); none.className = 'aed-chnone'; none.textContent = 'This timeline has no kinds of chip yet — add one with “+ Add” in the bar at the top.'; w.appendChild(none); }
    w.classList.add('show'); placeNear(w, at);
  }
  function chipPopSync(){ var w = document.getElementById('aed-chpop'); if(w && w.classList.contains('show') && w._nid){
    var box = chipBox(w._nid), old = w.querySelector('.aed-chips'); if(box && old) w.replaceChild(box, old); } }
  function chipToggle(nid, f, v, on){
    var n = srcNode(nid); if(!n || !v) return false;
    var L = (n[f] || []).slice(), i = L.indexOf(v);
    if(on && i < 0) L.push(v); else if(!on && i >= 0) L.splice(i, 1); else return false;
    return change('ch|' + nid + '|' + f, L);
  }
  function chooseChip(at, nid, f){
    hideMenus();
    var k = chipKinds().filter(function(x){ return x.f === f; })[0]; if(!k) return;
    var b = document.getElementById('aed-chip');
    if(!b){ b = document.createElement('div'); b.id = 'aed-chip';
      b.innerHTML = '<h5></h5><input type="text" maxlength="80" autocomplete="off" placeholder="Search or type a new name…"><div class="al-list"></div>';
      b.addEventListener('mousedown', function(e){ e.stopPropagation(); });
      b.addEventListener('click', function(e){ e.stopPropagation(); var r = e.target.closest('.al-row'); if(!r) return; pickChip(r.getAttribute('data-v'), r.getAttribute('data-new')); });
      b.querySelector('input').addEventListener('input', function(){ listChips(); });
      b.querySelector('input').addEventListener('keydown', function(e){ e.stopPropagation();
        if(e.key === 'Enter'){ e.preventDefault(); var r = b.querySelector('.al-row'); if(r) r.click(); }
        if(e.key === 'Escape'){ e.preventDefault(); b.classList.remove('show'); } });
      document.body.appendChild(b); }
    b._nid = nid; b._k = k;
    b.querySelector('h5').textContent = 'Add ' + aOne(k);
    var inp = b.querySelector('input'); inp.value = '';
    listChips(); b.classList.add('show'); placeNear(b, at); setTimeout(function(){ inp.focus(); }, 0);
  }
  function listChips(){
    var b = document.getElementById('aed-chip'); if(!b) return;
    var k = b._k, n = srcNode(b._nid), R = reg(k.r) || {}, have = (n && n[k.f]) || [];
    var q = b.querySelector('input').value.replace(/\s+/g, ' ').trim(), Q = q.toLowerCase(), L = b.querySelector('.al-list');
    var hits = Object.keys(R).filter(function(id){ return have.indexOf(id) < 0 && (!Q || txt(R[id].name).toLowerCase().indexOf(Q) >= 0); }).slice(0, 60);
    L.innerHTML = '';
    hits.forEach(function(id){ var r = document.createElement('div'); r.className = 'al-row'; r.setAttribute('data-v', id);
      var a = document.createElement('span'); a.textContent = txt(R[id].name); r.appendChild(a); L.appendChild(r); });
    var exact = Object.keys(R).some(function(id){ return txt(R[id].name).toLowerCase() === Q; });
    if(q && !exact){ var r = document.createElement('div'); r.className = 'al-row al-new'; r.setAttribute('data-new', q);
      var a = document.createElement('span'); a.textContent = '+ New ' + String(k.one || 'chip').toLowerCase() + ' “' + q + '”'; r.appendChild(a); L.appendChild(r); }
    if(!L.children.length){ var none = document.createElement('div'); none.className = 'al-k'; none.style.padding = '6px 8px'; none.textContent = 'Type a name to make a new one.'; L.appendChild(none); }
  }
  var CHIP_COLORS = ['#e0654a', '#4a9eff', '#2fb380', '#c084fc', '#f2a93b', '#ec6fa8', '#22b8cf', '#8f9c3a'];
  function pickChip(v, name){
    var b = document.getElementById('aed-chip'); if(!b) return; b.classList.remove('show');
    var k = b._k, nid = b._nid, n = srcNode(nid); if(!n) return;
    if(v){ chipToggle(nid, k.f, v, true); return; }
    if(k.r !== 'c'){ addAuthority(document.querySelector('#node-' + nid + ' .node-card') || document.getElementById('detail-content') || document.body, k, {nid: nid, name: name}); return; }
    withGlyph(document.querySelector('#node-' + nid + ' .node-card') || document.getElementById('detail-content') || document.body, k, name, function(svg){
      var c = newChip(k, name, svg); if(!c) return;
      var L = (n[k.f] || []).concat([c.id]);
      if(changes([c.op, ['ch|' + nid + '|' + k.f, L]]))
        toast('“' + c.name + '” made and added — it has a page of its own to fill in.'); });
  }
  /* the glyph a new chip is drawn with: one of the library's, never one a
     chip of this timeline already has (those are dimmed) */
  function glyphKey(svg){ var m = /<svg\b[^>]*>([\s\S]*)<\/svg>/.exec(String(svg || '')); return (m ? m[1] : String(svg || '')).replace(/\s+/g, '').split('/>').join('>'); }
  function glyphsInUse(){
    var used = {};
    ['c', 'env', 'theme'].forEach(function(r){ var R = reg(r) || {}; Object.keys(R).forEach(function(id){
      if(chipGone(r, id) || !R[id] || !R[id].symbol) return; var key = glyphKey(R[id].symbol); if(!used[key]) used[key] = txt(R[id].name || id); }); });
    return used;
  }
  function withGlyph(at, k, name, done){
    name = String(name || '').replace(/\s+/g, ' ').trim(); if(!name) return;
    var lib = EDK.glyphs || [];
    if(k.hide || !lib.length){ done(''); return; }       // shown by its name, not a glyph
    ['aed-name', 'aed-form', 'aed-kinds', 'aed-chip'].forEach(function(id){ var b = document.getElementById(id); if(b) b.classList.remove('show'); });
    var w = document.getElementById('aed-glyph');
    if(!w){ w = document.createElement('div'); w.id = 'aed-glyph';
      w.addEventListener('mousedown', function(e){ e.stopPropagation(); });
      w.addEventListener('click', function(e){ e.stopPropagation(); var b = e.target.closest('button[data-gi]'); if(!b || b.disabled) return;
        w.classList.remove('show'); var fn = w._done; if(fn) fn(lib[+b.getAttribute('data-gi')].s); });
      w.addEventListener('keydown', function(e){ e.stopPropagation(); if(e.key === 'Escape'){ e.preventDefault(); w.classList.remove('show'); } });
      document.body.appendChild(w); }
    w._done = done;
    var used = glyphsInUse(), html = '<h5></h5><div class="ag-grid">';
    lib.forEach(function(g, i){ var by = used[glyphKey(g.s)];
      html += '<button type="button" data-gi="' + i + '"' + (by ? ' disabled title="Already used by ' + esc(by).replace(/"/g, '&quot;') + '"' : ' title="' + esc(g.n) + '"') + '>' + g.s + '</button>'; });
    w.innerHTML = html + '</div><p class="ag-k">Dimmed glyphs are already on this timeline’s chips.</p>';
    w.querySelector('h5').textContent = 'A glyph for “' + name + '”';
    w.style.setProperty('--c', 'var(--text)');
    w.classList.add('show'); placeNear(w, at);
    var first = w.querySelector('button[data-gi]:not([disabled])'); if(first) setTimeout(function(){ first.focus(); }, 0);
  }
  // a new chip of kind k: its id (never one the page has) and the op that makes it
  function newChip(k, name, svg){
    name = String(name || '').replace(/\s+/g, ' ').trim().slice(0, 80); if(!name) return null;
    var R = reg(k.r) || {}, base = slug(name) || 'chip', id, i = 2;
    if(!/^[a-z]/.test(base)) base = 'c-' + base;
    id = base;
    // an entity's colour is the CSS variable named after it: never one the page already has
    var live = Object.keys(R).filter(function(x){ return !chipGone(k.r, x); }).length;
    if(k.r === 'c' && live >= 12){ toast('A timeline has at most 12 ' + String(k.l || 'of these').toLowerCase() + '.'); return null; }
    function taken(x){ if(reg('c') && reg('c')[x] || reg('env') && reg('env')[x] || reg('theme') && reg('theme')[x]) return true; try{ return k.r === 'c' && !!getComputedStyle(document.documentElement).getPropertyValue('--' + x).trim(); }catch(e){ return false; } }
    while(taken(id)) id = base.slice(0, 44) + '-' + (i++);
    var col = CHIP_COLORS[Object.keys(R).length % CHIP_COLORS.length];
    var v = {name: name, color: col}; if(svg) v.svg = svg;
    return {id: id, name: name, op: ['ne|' + k.r + '|' + id, v]};
  }

  /* the bar at the top, while editing: ✕ on a chip or a category takes it
     out of the timeline (off every card); + Add makes a chip or a category */
  function chipGone(r, id){ return !!XGONE[r + '|' + id] || !!(XA[r === 'env' ? 'axis1' : r === 'theme' ? 'axis2' : ''] ); }
  function newKinds(){ var out = []; ['axis1', 'axis2'].forEach(function(ax){ var v = NA[ax];
    if(v) out.push({f: RF[AXR[ax]], r: AXR[ax], l: v.l, one: v.one, fk: ax, na: 1}); }); return out; }
  function axesNow(){ return (EDK.nax || 0) + Object.keys(NA).length; }
  function isNewChip(r, id){ var e = NEWE['ne|' + r + '|' + id]; return !!(e && !e.off); }
  function rmEl(el){ if(el && el.parentNode) el.parentNode.removeChild(el); }
  function navChip(b){
    var oc = b.getAttribute('onclick') || '', m = /showDetail\('(char|env|theme)','([^']+)'\)/.exec(oc);
    if(m) return {r: m[1] === 'char' ? 'c' : m[1], id: m[2]};
    var ai = /showAxisIndex\('(env|theme)/.exec(oc);
    return ai ? {ax: ai[1] === 'env' ? 'axis1' : 'axis2'} : null;
  }
  function navSync(){
    var nav = document.getElementById('nav'); if(!nav) return;
    nav.querySelectorAll('.aed-newnav,.aed-nadd,.aed-nx').forEach(rmEl);
    nav.querySelectorAll('.nav-btn').forEach(function(b){ var c = navChip(b); if(!c) return;
      b.classList.toggle('aed-navoff', c.ax ? !!XA[c.ax] : chipGone(c.r, c.id)); });
    nav.querySelectorAll('.nav-group-label').forEach(function(l){ var t = l.textContent.trim().toLowerCase();
      var k = (EDK.chipk || []).filter(function(k){ return k.fk !== 'entity' && String(k.l || '').toLowerCase() === t; })[0];
      l.classList.toggle('aed-navoff', !!(k && XA[k.fk])); });
    // chips made here, after the last of their kind (a new kind: its own group)
    Object.keys(NEWE).forEach(function(key){ var e = NEWE[key]; if(!e || e.off) return; var q = key.split('|'), r = q[1], id = q[2];
      var kd = chipKinds().filter(function(k){ return k.r === r; })[0]; if(!kd || kd.hide) return;
      var t = r === 'c' ? 'char' : r, last = null;
      nav.querySelectorAll('.nav-btn').forEach(function(b){ var c = navChip(b); if(c && c.r === r && !b.classList.contains('aed-navoff')) last = b; });
      var b = document.createElement('button'); b.type = 'button'; b.className = 'nav-btn aed-newnav'; b.setAttribute('onclick', "showDetail('" + t + "','" + id + "')");
      var R0 = reg(r) || {}; if(R0[id] && R0[id].symbol && !kd.hide) b.innerHTML = R0[id].symbol + ' ';
      b.appendChild(document.createTextNode(e.v.name || 'New'));
      if(last) last.parentNode.insertBefore(b, last.nextSibling);
      else { var g = document.createElement('span'); g.className = 'nav-group-label aed-newnav'; g.textContent = kd.l; nav.appendChild(g); nav.appendChild(b); }
    });
    if(!editing() || !structOK()) return;
    nav.querySelectorAll('.nav-btn').forEach(function(b){ var c = navChip(b); if(!c || b.classList.contains('aed-navoff')) return;
      if(c.r === 'env' || c.r === 'theme'){ var kd = chipKinds().filter(function(k){ return k.r === c.r; })[0]; if(!kd) return; }
      var x = document.createElement('span'); x.className = 'aed-nx'; x.setAttribute('role', 'button'); x.setAttribute('data-x', 'navx');
      if(c.ax){ x.setAttribute('data-ax', c.ax); x.title = 'Remove this category of chips'; }
      else { x.setAttribute('data-r', c.r); x.setAttribute('data-id', c.id); x.title = 'Remove this chip from the timeline'; }
      x.setAttribute('aria-label', x.title); x.textContent = '✕'; b.appendChild(x); });
    // a visible axis: ✕ on its group's label removes the category
    nav.querySelectorAll('.nav-group-label').forEach(function(l){ if(l.classList.contains('aed-navoff')) return; var t = l.textContent.trim().toLowerCase();
      var k = chipKinds().filter(function(k){ return k.fk !== 'entity' && String(k.l || '').toLowerCase() === t; })[0]; if(!k) return;
      var x = document.createElement('span'); x.className = 'aed-nx aed-nxl'; x.setAttribute('role', 'button'); x.setAttribute('data-x', 'navx'); x.setAttribute('data-ax', k.fk);
      x.title = 'Remove this category of chips'; x.setAttribute('aria-label', x.title); x.textContent = '✕'; l.appendChild(x); });
    var add = document.createElement('button'); add.type = 'button'; add.className = 'aed-nadd'; add.setAttribute('data-x', 'navadd');
    add.textContent = '+ Add'; add.title = 'Add a chip, or a new category of chips'; nav.appendChild(add);
  }
  function cardsWith(r, id){ var f = RF[r]; return NODES_SRC.filter(function(n){ return (n[f] || []).indexOf(id) >= 0 && !cardGone(n.id); }).map(function(n){ return n.id; }); }
  function navRemove(b){
    var ax = b.getAttribute('data-ax');
    if(ax){
      var k = chipKinds().filter(function(x){ return x.fk === ax; })[0]; if(!k) return;
      var r = k.r, R = reg(r) || {}, ids = Object.keys(R).filter(function(i){ return !chipGone(r, i); });
      var cards = NODES_SRC.filter(function(n){ return (n[k.f] || []).length && !cardGone(n.id); });
      ask('Remove the category “' + k.l + '”?', 'Its ' + ids.length + (ids.length === 1 ? ' chip comes' : ' chips come') + ' off ' + (cards.length === 1 ? 'the 1 card that has them' : 'the ' + cards.length + ' cards that have them') + ', and their pages go with them.',
        [{t: 'Remove the category', cls: 'aa-danger', fn: function(){
          var L = cards.map(function(n){ return ['ch|' + n.id + '|' + k.f, []]; });
          ids.forEach(function(i){ if(isNewChip(r, i)) L.push(['ne|' + r + '|' + i, null]); });
          L.push(NA[ax] ? ['na|' + ax, null] : ['xa|' + ax, 1]);
          if(changes(L)) toast('“' + k.l + '” removed — ⌘Z brings it back.'); }}]);
      return;
    }
    var r2 = b.getAttribute('data-r'), id = b.getAttribute('data-id'), it = (reg(r2) || {})[id]; if(!it) return;
    var nm = txt(it.name || id), on = cardsWith(r2, id), f = RF[r2];
    ask('Remove “' + nm + '”?', on.length ? 'It comes off ' + (on.length === 1 ? 'the 1 card' : 'the ' + on.length + ' cards') + ' it is on, and its page goes with it.' : 'It is on no card. Its page goes with it.',
      [{t: 'Remove it', cls: 'aa-danger', fn: function(){
        var L = on.map(function(nid){ return ['ch|' + nid + '|' + f, (srcNode(nid)[f] || []).filter(function(x){ return x !== id; })]; });
        L.push(isNewChip(r2, id) ? ['ne|' + r2 + '|' + id, null] : ['xe|' + r2 + '|' + id, 1]);
        if(changes(L)) toast('“' + nm + '” removed — ⌘Z brings it back.'); }}]);
  }
  function singularOf(w){ w = String(w || '').trim(); return /ies$/i.test(w) ? w.slice(0, -3) + 'y' : /(ss|us|is)$/i.test(w) ? w : /s$/i.test(w) ? w.slice(0, -1) : w; }
  function navAdd(b){
    var A = chipKinds().map(function(k){ return {t: 'A new ' + String(k.one || 'chip').toLowerCase(), sub: 'In ' + k.l + ' — put it on cards with ◆ on a card, or on a card’s page.',
      fn: function(){ if(k.r !== 'c') return addAuthority(b, k, {});
        askName(b, 'Name the new ' + String(k.one || 'chip').toLowerCase(), '', function(nm){ withGlyph(b, k, nm, function(svg){
        var c = newChip(k, nm, svg); if(c && changes([c.op])) toast('“' + c.name + '” added — it has a page of its own to fill in.'); }); }); }}; });
    if(axesNow() < 2) A.push({t: 'A new category of chips', sub: 'Its own kind of chip, like Cases or Themes.',
      fn: function(){ askName(b, 'Name the category (plural, e.g. Cases)', '', function(nm){
        nm = String(nm || '').replace(/\s+/g, ' ').trim().slice(0, 60); if(!nm) return;
        var ax = (EDK.nax || 0) === 0 && !NA.axis1 ? 'axis1' : 'axis2';
        if(change('na|' + ax, {l: nm, one: singularOf(nm)})) toast('“' + nm + '” added — + Add makes its first chip.'); }); }});
    ask('Add to the bar at the top', null, A);
  }
  function newFlag(name){
    name = String(name || '').replace(/\s+/g, ' ').trim().slice(0, 80); if(!name) return null;
    if(FLAGS.length >= 12){ toast('A timeline has at most 12 filters of its own.'); return null; }
    var base = slug(name) || 'filter', id = base, i = 2;
    var taken = {}; FLAGS.forEach(function(f){ taken[f.id] = 1; });
    while(taken[id]) id = base.slice(0, 44) + '-' + (i++);
    return {id: id, name: name};
  }
  function toggleFlag(nid, fid){ var L = (FLN[nid] || []).slice(), i = L.indexOf(fid); if(i < 0) L.push(fid); else L.splice(i, 1); return change('fn|' + nid, L); }

  /* the Filter panel while editing: your own filters (choose their cards,
     rename, remove), the others (take out, put back), + Add a filter */
  var PICK = null;
  function decoratePanel(){
    var panel = document.getElementById('ef-panel'); if(!panel) return;
    panel.querySelectorAll('.aed-fx,.aed-fadd,.aed-fhint').forEach(function(el){ el.parentNode.removeChild(el); });
    panel.classList.toggle('aed-fedit', editing() && structOK());
    if(!editing() || !structOK()) return;
    var S = window.FILTER_SECTIONS || [], body = panel.querySelector('.ef-body'); if(!body) return;
    var hint = document.createElement('div'); hint.className = 'aed-fhint'; hint.textContent = 'Editing filters — click one of your own to choose its cards.'; body.insertBefore(hint, body.firstChild);
    panel.querySelectorAll('.ef-sec[data-sec]').forEach(function(sec){
      var key = sec.getAttribute('data-sec'), sd = S.filter(function(x){ return x.key === key; })[0]; if(!sd) return;
      sec.classList.toggle('aed-foff', !!sd.off);
      if(key !== 'flags'){
        var hx = document.createElement('span'); hx.className = 'aed-fx'; hx.setAttribute('role', 'button'); hx.setAttribute('data-x', sd.off ? 'fsecon' : 'fsecoff');
        hx.textContent = sd.off ? '↺ Put back' : '✕ Take out'; hx.title = sd.off ? 'Show this filter again' : 'Take this filter out of the panel';
        var hh = sec.querySelector('.ef-h'); if(hh) hh.appendChild(hx);
      }
      sec.querySelectorAll('.ef-chip[data-fid]').forEach(function(ch){
        var id = ch.getAttribute('data-fid'), it = sd.items.filter(function(x){ return x.id === id; })[0] || {};
        ch.classList.toggle('aed-foff', !!it.off);
        var acts = key === 'flags' ? [['flren', '✎', 'Rename'], ['fldel', '✕', 'Remove this filter']]
          : [[it.off ? 'fchipon' : 'fchipoff', it.off ? '↺' : '✕', it.off ? 'Put this back' : 'Take this out of the filter']];
        acts.forEach(function(a){ var x = document.createElement('span'); x.className = 'aed-fx aed-fxc'; x.setAttribute('role', 'button');
          x.setAttribute('data-x', a[0]); x.setAttribute('data-g', a[1]); x.title = a[2]; x.setAttribute('aria-label', a[2]); ch.appendChild(x); });
      });
    });
    var add = document.createElement('button'); add.type = 'button'; add.className = 'aed-fadd'; add.textContent = '+ Add a filter';
    add.title = 'A filter of your own: name it, then click the cards that belong in it'; body.appendChild(add);
  }
  document.addEventListener('alto-filter-drawn', function(){ decoratePanel(); });
  // A click on a chip while editing: its controls, or (your own filter) choosing its cards.
  window._altoFilterChipClick = function(e, b){
    if(!editing() || !structOK()) return false;
    var x = e.target.closest && e.target.closest('.aed-fx');
    var key = b.getAttribute('data-fs'), id = b.getAttribute('data-fid');
    if(!x && key !== 'flags' && !b.classList.contains('aed-foff')) return false;
    e.preventDefault(); e.stopPropagation();
    if(!x){ if(key === 'flags') startPick(id); return true; }
    filterAction(x.getAttribute('data-x'), key, id, x);
    return true;
  };
  function filterAction(a, key, id, at){
    var k = fkey(key), o = OFF.slice();
    if(a === 'fsecoff'){ o.push(k); change('fx|off', o); }
    else if(a === 'fsecon'){ change('fx|off', o.filter(function(x){ return x !== k; })); }
    else if(a === 'fchipoff'){ o.push(k + ':' + id); change('fx|off', o); }
    else if(a === 'fchipon'){ change('fx|off', o.filter(function(x){ return x !== k + ':' + id; })); }
    else if(a === 'fldel'){
      var f = FLAGS.filter(function(x){ return x.id === id; })[0]; if(!f) return;
      var L = [['fl|list', FLAGS.filter(function(x){ return x.id !== id; })]];
      Object.keys(FLN).forEach(function(nid){ if((FLN[nid] || []).indexOf(id) >= 0) L.push(['fn|' + nid, FLN[nid].filter(function(x){ return x !== id; })]); });
      if(changes(L)) toast('“' + f.name + '” removed — ⌘Z brings it back.');
    }
    else if(a === 'flren'){
      var f2 = FLAGS.filter(function(x){ return x.id === id; })[0]; if(!f2) return;
      askName(at, 'Rename this filter', f2.name, function(nm){
        nm = String(nm || '').replace(/\s+/g, ' ').trim().slice(0, 80); if(!nm || nm === f2.name) return;
        change('fl|list', FLAGS.map(function(x){ return x.id === id ? Object.assign({}, x, {name: nm}) : x; })); });
    }
  }
  function panelClick(e){
    if(!editing() || !structOK()) return;
    var t = e.target; if(!t.closest) return;
    var x = t.closest('#ef-panel .ef-h .aed-fx');
    if(x){ e.preventDefault(); e.stopPropagation(); var sec = x.closest('.ef-sec'); filterAction(x.getAttribute('data-x'), sec.getAttribute('data-sec'), null, x); return; }
    var add = t.closest('#ef-panel .aed-fadd');
    if(add){ e.preventDefault(); e.stopPropagation();
      askName(add, 'Name your filter', '', function(nm){ var f = newFlag(nm); if(!f) return; if(change('fl|list', FLAGS.concat([f]))) startPick(f.id); }); }
  }
  document.addEventListener('click', panelClick, true);

  /* choosing a filter's cards: click them on the timeline */
  function startPick(fid){
    if(!FLAGS.some(function(f){ return f.id === fid; })) return;
    PICK = fid; if(window._altoFilterOpen) window._altoFilterOpen(false);
    try{ if(page() && window.showTimeline) window.showTimeline(); }catch(e){}
    root.classList.add('aed-picking'); paintPick();
  }
  function endPick(quiet){
    if(!PICK) return; PICK = null; root.classList.remove('aed-picking');
    document.querySelectorAll('.aed-pick-in,.aed-pick-out,.aed-pick-hit').forEach(function(el){ el.classList.remove('aed-pick-in', 'aed-pick-out', 'aed-pick-hit'); });
    var b = document.getElementById('aed-pick'); if(b){ b.classList.remove('show'); var q = b.querySelector('.ap-q'); if(q) q.value = ''; }
    var r = document.getElementById('aed-pickres'); if(r) r.classList.remove('show');
    CHIPMENU = false;
  }
  /* finding cards for a filter: by their words, their page's words or their chips */
  function chipNames(n){ var out = []; [['chars', 'c'], ['envs', 'env'], ['themes', 'theme']].forEach(function(q){ var R = reg(q[1]) || {};
    (n[q[0]] || []).forEach(function(v){ if(R[v] && !chipGone(q[1], v)) out.push(txt(R[v].name)); }); }); return out; }
  function pageWords(id){ var L = secList('n', id) || []; return L.map(function(s){ return txt(s.h || '') + ' ' + txt(s.t || ''); }).join(' '); }
  function findCards(q){
    var Q = String(q || '').toLowerCase().replace(/\s+/g, ' ').trim(); if(!Q) return [];
    var words = Q.split(' ');
    return NODES_SRC.filter(function(n){ return !cardGone(n.id); }).map(function(n){
      var head = (txt(n.title || '') + ' ' + txt(n.tag || '')).toLowerCase(), chips = chipNames(n).join(' ').toLowerCase();
      var body = (txt(n.desc || '') + ' ' + pageWords(n.id)).toLowerCase();
      var all = head + ' ' + chips + ' ' + body;
      if(!words.every(function(w){ return all.indexOf(w) >= 0; })) return null;
      var score = (head.indexOf(Q) >= 0 ? 3 : 0) + (chips.indexOf(Q) >= 0 ? 2 : 0) + (body.indexOf(Q) >= 0 ? 1 : 0);
      var why = head.indexOf(Q) >= 0 ? '' : chips.indexOf(Q) >= 0 ? chipNames(n).filter(function(c){ return c.toLowerCase().indexOf(Q) >= 0 || words.some(function(w){ return c.toLowerCase().indexOf(w) >= 0; }); }).join(', ') : 'in its text';
      return {id: n.id, score: score, why: why};
    }).filter(Boolean).sort(function(a, b){ return b.score - a.score; });
  }
  // every kind of chip (not a catch-all one) with its chips: one puts all the
  // cards that carry it in the filter
  var CHIPMENU = false;
  function chipMenu(r){
    r.innerHTML = '';
    var kinds = chipKinds().filter(function(k){ return !k.hide; }), any = false;
    kinds.forEach(function(k){
      var R = reg(k.r) || {}, ids = Object.keys(R).filter(function(id){ return !chipGone(k.r, id) && cardsWith(k.r, id).length; });
      if(!ids.length) return; any = true;
      var hd = document.createElement('div'); hd.className = 'pr-h'; var sp = document.createElement('span'); sp.textContent = k.l; hd.appendChild(sp); r.appendChild(hd);
      ids.forEach(function(id){
        var cs = cardsWith(k.r, id), inN = cs.filter(function(c){ return (FLN[c] || []).indexOf(PICK) >= 0; }).length, on = inN === cs.length;
        var row = document.createElement('div'); row.className = 'pr-row' + (on ? ' on' : ''); row.setAttribute('data-pr', 'chip'); row.setAttribute('data-r', k.r); row.setAttribute('data-id', id);
        var ck = document.createElement('span'); ck.className = 'pr-ck'; ck.textContent = on ? '✓' : inN ? '–' : ''; if(inN && !on) ck.style.background = 'color-mix(in srgb,var(--accent,#a78bfa) 45%,transparent)'; row.appendChild(ck);
        var g = document.createElement('span'); g.className = 'pr-g'; g.style.color = R[id].color || 'var(--text)'; g.innerHTML = R[id].symbol || ''; row.appendChild(g);
        var t = document.createElement('span'); t.className = 'pr-t'; var bb = document.createElement('b'); bb.textContent = txt(R[id].name || id); t.appendChild(bb);
        var sm = document.createElement('small'); sm.textContent = cs.length + (cs.length === 1 ? ' card' : ' cards') + (inN && !on ? ' — ' + inN + ' in the filter' : ''); t.appendChild(sm); row.appendChild(t);
        r.appendChild(row); }); });
    if(!any){ var no = document.createElement('div'); no.className = 'pr-none'; no.textContent = 'No card carries a chip yet.'; r.appendChild(no); }
  }
  function paintFind(){
    var b = document.getElementById('aed-pick'), r = document.getElementById('aed-pickres'); if(!b || !PICK) return;
    var q = b.querySelector('.ap-q').value; if(String(q).trim()) CHIPMENU = false;
    var hits = findCards(q), H = {};
    hits.forEach(function(h){ H[h.id] = 1; });
    document.querySelectorAll('#world .node').forEach(function(el){ el.classList.toggle('aed-pick-hit', !!H[el.id.slice(5)]); });
    if(!r){ r = document.createElement('div'); r.id = 'aed-pickres'; document.body.appendChild(r);
      r.addEventListener('mousedown', function(e){ e.stopPropagation(); e.preventDefault(); });
      r.addEventListener('click', function(e){ e.stopPropagation(); var x = e.target.closest('[data-pr]'); if(!x || !PICK) return;
        var a = x.getAttribute('data-pr'), cur = findCards(b.querySelector('.ap-q').value);
        if(a === 'one') toggleFlag(x.getAttribute('data-id'), PICK);
        else if(a === 'chip'){ var ids = cardsWith(x.getAttribute('data-r'), x.getAttribute('data-id')), want2 = !x.classList.contains('on'), L2 = [];
          ids.forEach(function(id){ var have = (FLN[id] || []).indexOf(PICK) >= 0; if(have !== want2) L2.push(['fn|' + id, want2 ? (FLN[id] || []).concat([PICK]) : (FLN[id] || []).filter(function(f){ return f !== PICK; })]); });
          if(L2.length) changes(L2); }
        else { var want = a === 'all', L = [];
          cur.forEach(function(h){ var have = (FLN[h.id] || []).indexOf(PICK) >= 0; if(have !== want) L.push(['fn|' + h.id, want ? (FLN[h.id] || []).concat([PICK]) : (FLN[h.id] || []).filter(function(f){ return f !== PICK; })]); });
          if(L.length) changes(L); }
        paintPick(); }); }
    if(CHIPMENU){ chipMenu(r); var bb0 = b.getBoundingClientRect(); r.style.bottom = Math.round(window.innerHeight - bb0.top + 8) + 'px'; r.classList.add('show'); return; }
    if(!String(q).trim()){ r.classList.remove('show'); return; }
    var inN = hits.filter(function(h){ return (FLN[h.id] || []).indexOf(PICK) >= 0; }).length;
    r.innerHTML = '';
    var hd = document.createElement('div'); hd.className = 'pr-h';
    var sp = document.createElement('span'); sp.textContent = hits.length ? hits.length + (hits.length === 1 ? ' card matches' : ' cards match') + ' — ' + inN + ' in the filter' : ''; hd.appendChild(sp);
    if(hits.length && inN < hits.length){ var ab = document.createElement('button'); ab.type = 'button'; ab.setAttribute('data-pr', 'all'); ab.textContent = 'Add all ' + hits.length; hd.appendChild(ab); }
    if(inN){ var tb = document.createElement('button'); tb.type = 'button'; tb.setAttribute('data-pr', 'none'); tb.textContent = 'Take these out'; hd.appendChild(tb); }
    r.appendChild(hd);
    if(!hits.length){ var no = document.createElement('div'); no.className = 'pr-none'; no.textContent = 'No card has those words, on it, on its page or in its chips.'; r.appendChild(no); }
    hits.slice(0, 200).forEach(function(h){
      var n = srcNode(h.id), on = (FLN[h.id] || []).indexOf(PICK) >= 0;
      var row = document.createElement('div'); row.className = 'pr-row' + (on ? ' on' : ''); row.setAttribute('data-pr', 'one'); row.setAttribute('data-id', h.id);
      var ck = document.createElement('span'); ck.className = 'pr-ck'; ck.textContent = on ? '✓' : ''; row.appendChild(ck);
      var t = document.createElement('span'); t.className = 'pr-t'; var bb = document.createElement('b'); bb.textContent = txt(n.title || '') || 'Untitled'; t.appendChild(bb);
      var sm = document.createElement('small'); sm.textContent = unitName(NODE_ACT[h.id]) + (h.why ? ' · ' + h.why : ''); t.appendChild(sm); row.appendChild(t);
      r.appendChild(row); });
    r.classList.add('show');
    var br = b.getBoundingClientRect(); r.style.bottom = Math.round(window.innerHeight - br.top + 8) + 'px';
  }
  function paintPick(){
    if(!PICK) return;
    var f = FLAGS.filter(function(x){ return x.id === PICK; })[0]; if(!f){ endPick(); return; }
    var n = 0;
    document.querySelectorAll('#world .node').forEach(function(el){ var on = (FLN[el.id.slice(5)] || []).indexOf(PICK) >= 0; if(on) n++;
      el.classList.toggle('aed-pick-in', on); el.classList.toggle('aed-pick-out', !on); });
    var b = document.getElementById('aed-pick');
    if(!b){ b = document.createElement('div'); b.id = 'aed-pick';
      b.innerHTML = '<span class="ap-t"></span><input class="ap-q" type="search" autocomplete="off" placeholder="Find cards — words or a chip" aria-label="Find cards"><button type="button" class="ap-chips">From chips ▾</button><span class="ap-n"></span><button type="button" class="ap-done">Done</button>';
      b.querySelector('.ap-done').addEventListener('click', function(e){ e.stopPropagation(); endPick(); drawFilters(); if(window._altoFilterOpen) window._altoFilterOpen(true); });
      b.querySelector('.ap-chips').addEventListener('click', function(e){ e.stopPropagation(); var r = document.getElementById('aed-pickres');
        CHIPMENU = !(CHIPMENU && r && r.classList.contains('show')); b.querySelector('.ap-q').value = ''; paintFind(); });
      var q = b.querySelector('.ap-q');
      q.addEventListener('input', paintFind);
      q.addEventListener('keydown', function(e){ e.stopPropagation(); if(e.key === 'Escape'){ e.preventDefault(); if(q.value){ q.value = ''; paintFind(); } else endPick(); } });
      document.body.appendChild(b); }
    b.querySelector('.ap-t').textContent = 'Cards in “' + f.name + '”: click them, or find them';
    b.querySelector('.ap-n').textContent = n + (n === 1 ? ' card' : ' cards');
    b.classList.add('show');
    paintFind();
  }

  /*__STUDY_EDIT__*/
  /* a small box asking for a name; a menu of kinds of section */
  function hideMenus(){ ['aed-name', 'aed-form', 'aed-kinds', 'aed-chip', 'aed-chpop', 'aed-glyph'].forEach(function(id){ var b = document.getElementById(id); if(b) b.classList.remove('show'); }); }
  function placeNear(b, at){
    var r = at.getBoundingClientRect(), w = b.offsetWidth, h = b.offsetHeight;
    var top = r.bottom + 8; if(top + h > window.innerHeight - 8) top = Math.max(8, r.top - h - 8);
    b.style.top = Math.round(top) + 'px'; b.style.left = Math.round(Math.max(8, Math.min(window.innerWidth - w - 8, r.left))) + 'px';
  }
  function askName(at, title, val, done){
    hideMenus();
    var b = document.getElementById('aed-name');
    if(!b){ b = document.createElement('div'); b.id = 'aed-name';
      b.innerHTML = '<h5></h5><input type="text" maxlength="80" autocomplete="off"><div class="al-go"><button type="button" data-a="cancel">Cancel</button><button type="button" data-a="ok" class="ab-ok">Save</button></div>';
      b.addEventListener('mousedown', function(e){ e.stopPropagation(); });
      b.addEventListener('click', function(e){ e.stopPropagation(); var a = e.target.closest('button'); if(!a) return;
        if(a.getAttribute('data-a') === 'ok'){ var fn = b._done; b.classList.remove('show'); if(fn) fn(b.querySelector('input').value); } else b.classList.remove('show'); });
      b.querySelector('input').addEventListener('keydown', function(e){ e.stopPropagation();
        if(e.key === 'Enter'){ e.preventDefault(); var fn = b._done; b.classList.remove('show'); if(fn) fn(this.value); }
        if(e.key === 'Escape'){ e.preventDefault(); b.classList.remove('show'); } });
      document.body.appendChild(b); }
    b._done = done; b.querySelector('h5').textContent = title; var inp = b.querySelector('input'); inp.value = val || '';
    b.classList.add('show'); placeNear(b, at); setTimeout(function(){ inp.focus(); inp.select(); }, 0);
  }
  var KINDS = [['text', 'Text', 'A heading and a paragraph'], ['list', 'List', 'A heading and bullet points'],
    ['quoted', 'Quote', 'The source’s own words, marked Quoted'], ['notes', 'From your notes', 'Your notes, marked as yours'],
    ['summary', 'Summary', 'A short summary'], ['tree', 'Decision tree', 'Questions and answers that branch, like a small timeline'],
    ['quiz', 'Quiz', 'Multiple-choice questions that grade you — best written by Claude from your notes'],
    ['cards', 'Flash cards', 'Cards you flip and mark Know it / Still learning — best written by Claude from your notes'],
    ['cases', 'Cases', 'A list of cases — each with its citation, a note and a link'],
    ['authorities', 'Authorities', 'A list of statutes, rules, Restatement sections or other sources']];
  function chooseKind(at, ok){
    hideMenus();
    var b = document.getElementById('aed-kinds');
    if(!b){ b = document.createElement('div'); b.id = 'aed-kinds';
      b.innerHTML = '<h5>Add a section</h5>' + KINDS.map(function(k){ return '<button type="button" data-k="' + k[0] + '"><b>' + esc(k[1]) + '</b><small>' + esc(k[2]) + '</small></button>'; }).join('');
      b.addEventListener('mousedown', function(e){ e.stopPropagation(); });
      b.addEventListener('click', function(e){ e.stopPropagation(); var a = e.target.closest('button[data-k]'); if(!a) return; b.classList.remove('show'); addSection(b._ok, a.getAttribute('data-k'), b._at); });
      document.body.appendChild(b); }
    b._ok = ok; b._at = at; b.classList.add('show'); placeNear(b, at);
  }
  document.addEventListener('mousedown', function(e){ if(e.target.closest && !e.target.closest('#aed-name,#aed-form,#aed-kinds,#aed-chip,#aed-chpop,#aed-glyph,.aed-add,.aed-nadd,.aed-fadd,.aed-fx,.aed-chadd')) hideMenus(); }, true);
  function addSection(ok, kind, at){
    var f = field(ok + '|order'); if(!f) return;
    if(kind === 'cases' || kind === 'authorities'){ addAuthSection(ok, kind, at || document.body); return; }
    var nk = rid('new-'), base = ok + '|s|' + nk, q = ok.split('|');
    var H = {text:'New section', list:'Key points', quoted:'Quote', notes:'Notes', summary:'Summary', tree:'Decision tree', quiz:'Quiz', cards:'Flash cards'}[kind] || 'New section';
    var T = kind === 'list' ? '<ul><li>First point</li><li>Second point</li></ul>' : kind === 'quoted' ? 'Paste the source’s words here.' : kind === 'tree' ? '' : 'Write here.';
    var L = [[ok + '|order', f.get().concat(nk)], [base + '|h', H]];
    if(T) L.push([base + '|t', T]);
    if(PROVL[kind]) L.push([base + '|p', kind]);
    if(kind === 'tree') L.push(['dt|' + DTPRE[q[0]] + '-' + q[1] + '-' + nk + '|tree', [{i: rid('s-'), t: 'First question'}]]);
    if(kind === 'quiz' || kind === 'cards'){
      var sk = DTPRE[q[0]] + '-' + q[1] + '-' + nk;
      L.push(['sd|' + sk + '|study', studyStarter(kind)]);
      if(changes(L)) setTimeout(function(){ openStudyEditor(sk, {fresh: true}); }, 60);
      return;
    }
    if(changes(L)){
      setTimeout(function(){ var mk = document.querySelector('#detail-content .aed-k[data-k="' + base + '"]'), sb = mk && mk.closest('.detail-section'), h3 = sb && sb.querySelector(':scope > h3');
        if(h3){ h3.scrollIntoView({block:'center'}); startField(h3, base + '|h'); try{ document.execCommand('selectAll'); }catch(_){} } }, 60);
    }
  }

  /* ── authorities: the cases, statutes, Restatement sections and sources a
     page lists. An entry made as a chip of its own (a value of the Cases /
     Statutes axis) has a page; one in a list section (Cases, Authorities,
     Sources…) is a line of that section's list. Both are the owner's words:
     a name, a citation, a note, a link — nothing is filled in for them. ── */
  var AUTHRE = /\b(cases?|authorit(?:y|ies)|restatements?|statutes?|rules?|sources?|citations?|cited|precedents?|references?|readings?)\b/i;
  function authNoun(h){
    h = String(h || '');
    if(/restatement/i.test(h)) return 'Restatement section';
    if(/\bcases?\b/i.test(h)) return 'case';
    if(/statute|\brules?\b/i.test(h)) return 'statute or rule';
    if(/source|reading|reference/i.test(h)) return 'source';
    return 'authority';
  }
  function aOneW(w){ w = String(w || 'entry'); return (/^[aeiou]/i.test(w) ? 'an ' : 'a ') + w; }
  function linkHtml(u){ var e = esc(u).replace(/"/g, '&quot;'); return '<a class="note-link" href="' + e + '" target="_blank" rel="noopener">' + esc(u) + '</a>'; }
  function goodLink(u){ return /^https?:\/\/[^\s<>"']{3,2000}$/i.test(String(u || '').trim()); }
  // the heading the other entries of an axis put their words under
  function authHead(kind){
    var R = reg(kind) || {}, cnt = {}, order = [], A = null, X = EDK.ix || {};
    Object.keys(X).forEach(function(key){ if(!A && X[key].r === kind) A = (window._ALTO_AXES || {})[key]; });
    Object.keys(R).forEach(function(id){
      if(isNewChip(kind, id) || chipGone(kind, id)) return;
      var ss = R[id].sections || [];
      for(var i = 0; i < ss.length; i++){
        var h = txt(hParts(ss[i].h).text).trim();
        if(!h || /^(citation|source notes|link)$/i.test(h) || (A && A.citeH && h === txt(A.citeH))) continue;
        if(!(h in cnt)){ cnt[h] = 0; order.push(h); } cnt[h]++; break;
      } });
    var best = '', bn = 0;
    if(A && (A.blurb || []).length) order.forEach(function(h){ if(!best && h.toLowerCase() === A.blurb[0]) best = h; });
    if(!best) order.forEach(function(h){ if(cnt[h] > bn){ bn = cnt[h]; best = h; } });
    return best || 'Notes';
  }
  /* a box of a few labelled fields: fields [{k, l, type: text|area|select, val, opts, hint}] */
  function askForm(at, title, fields, ok, done){
    hideMenus();
    var b = document.getElementById('aed-form');
    if(!b){ b = document.createElement('div'); b.id = 'aed-form';
      b.addEventListener('mousedown', function(e){ e.stopPropagation(); });
      b.addEventListener('click', function(e){ e.stopPropagation(); var a = e.target.closest('button'); if(!a) return;
        if(a.getAttribute('data-a') === 'ok') submit(); else b.classList.remove('show'); });
      b.addEventListener('keydown', function(e){ e.stopPropagation();
        if(e.key === 'Escape'){ e.preventDefault(); b.classList.remove('show'); }
        if(e.key === 'Enter' && e.target.tagName === 'INPUT'){ e.preventDefault(); submit(); } });
      document.body.appendChild(b); }
    function submit(){
      var vals = {}, bad = null;
      b.querySelectorAll('[data-f]').forEach(function(el){ var k = el.getAttribute('data-f'); vals[k] = String(el.value || '').replace(/[ \t]+/g, ' ').trim();
        var fd = b._fields.filter(function(x){ return x.k === k; })[0]; if(fd && fd.req && !vals[k] && !bad) bad = el; });
      if(bad){ bad.focus(); bad.classList.add('bad'); return; }
      var fn = b._done; b.classList.remove('show'); if(fn) fn(vals);
    }
    b._fields = fields; b._done = done;
    var h = '<h5></h5>';
    fields.forEach(function(f){
      h += '<label><span>' + esc(f.l) + '</span>';
      if(f.type === 'select') h += '<select data-f="' + f.k + '">' + f.opts.map(function(o){ return '<option value="' + esc(o[0]).replace(/"/g, '&quot;') + '"' + (String(o[0]) === String(f.val) ? ' selected' : '') + '>' + esc(o[1]) + '</option>'; }).join('') + '</select>';
      else if(f.type === 'area') h += '<textarea data-f="' + f.k + '" rows="3" maxlength="2000" placeholder="' + esc(f.ph || '').replace(/"/g, '&quot;') + '">' + esc(f.val || '') + '</textarea>';
      else h += '<input data-f="' + f.k + '" type="text" maxlength="300" autocomplete="off" placeholder="' + esc(f.ph || '').replace(/"/g, '&quot;') + '" value="' + esc(f.val || '').replace(/"/g, '&quot;') + '">';
      if(f.hint) h += '<small>' + esc(f.hint) + '</small>';
      h += '</label>'; });
    h += '<div class="al-go"><button type="button" data-a="cancel">Cancel</button><button type="button" data-a="ok" class="ab-ok">' + esc(ok || 'Add') + '</button></div>';
    b.innerHTML = h; b.querySelector('h5').textContent = title;
    b.querySelectorAll('input,textarea').forEach(function(el){ el.addEventListener('input', function(){ el.classList.remove('bad'); }); });
    b.classList.add('show'); placeNear(b, at);
    var first = b.querySelector('input,textarea'); if(first) setTimeout(function(){ first.focus(); first.select && first.select(); }, 0);
  }
  /* an axis value: its own form, then (for one with a glyph) the glyph, then it is made */
  function authFields(k, o){
    var X = EDK.ix || {}, keys = Object.keys(X).filter(function(key){ return X[key].r === k.r; }), hd = authHead(k.r);
    var F = [{k: 'name', l: 'Name', val: o.name, req: 1}, {k: 'cite', l: 'Citation', val: o.cite},
             {k: 't', l: 'Note', type: 'area', val: o.t, hint: 'Shown under “' + hd + '”, like the others.'},
             {k: 'link', l: 'Link (optional)', val: o.link, ph: 'https://…'}];
    if(keys.length > 1) F.push({k: 'grp', l: 'List', type: 'select', val: o.grp || '', opts: keys.map(function(key){ return [X[key].g, X[key].l]; })});
    if(o.pick){
      var opts = [['', 'Not yet — attach it later']];
      NODES_SRC.forEach(function(n){ if(!cardGone(n.id)) opts.push([n.id, txt(n.title || '') || 'Untitled']); });
      F.push({k: 'attach', l: 'Put it on', type: 'select', val: '', opts: opts});
    }
    return F;
  }
  // the name of the list a new entry joins (an Index chip's own, else the kind's)
  function listName(k, grp){
    var X = EDK.ix || {}, hit = null;
    Object.keys(X).forEach(function(key){ if(X[key].r === k.r && (!hit || String(X[key].g || '') === String(grp || ''))) hit = X[key]; });
    return hit ? hit.l : k.l;
  }
  function addAuthority(at, k, ctx){
    ctx = ctx || {};
    var one = String(k.one || 'entry').toLowerCase();
    askForm(at, 'New ' + one + ' in ' + listName(k, ctx.grp), authFields(k, {name: ctx.name, grp: ctx.grp, pick: !ctx.nid}), 'Add', function(f){
      withGlyph(at, k, f.name, function(svg){
        var c = newChip(k, f.name, svg); if(!c) return;
        var v = c.op[1];
        if(f.cite) v.cite = f.cite; if(f.t){ v.t = f.t; v.h = authHead(k.r); }
        if(goodLink(f.link)) v.link = f.link.trim(); else if(f.link) toast('That link needs to start with https:// — the rest was added without it.');
        if(f.grp) v.grp = f.grp;
        var L = [c.op], att = ctx.nid || f.attach, n = att && srcNode(att);
        if(n) L.push(['ch|' + att + '|' + k.f, (n[k.f] || []).concat([c.id])]);
        if(changes(L)) toast('“' + c.name + '” added' + (n ? ' to “' + titleOf(att) + '”' : '') + ' — click its name to open its page.');
      }); });
  }
  function editAuthority(at, k, id){
    var e = NEWE['ne|' + k.r + '|' + id]; if(!e || e.off) return;
    var o = Object.assign({}, e.v);
    askForm(at, 'Change this ' + String(k.one || 'entry').toLowerCase() + ' in ' + listName(k, o.grp), authFields(k, {name: o.name, cite: o.cite, t: o.t, link: o.link, grp: o.grp}), 'Save', function(f){
      var v = Object.assign({}, e.v, {name: f.name.slice(0, 80)});
      ['cite', 't', 'link', 'grp'].forEach(function(x){ if(f[x]) v[x] = f[x]; else delete v[x]; });
      if(v.link && !goodLink(v.link)){ delete v.link; toast('That link needs to start with https://.'); }
      if(v.t) v.h = e.v.h || authHead(k.r); else delete v.h;
      change('ne|' + k.r + '|' + id, v); });
  }
  // an axis value's words (setChip): its citation (the build's own first section),
  // then its note and link — its own sections 0, 1
  function authSet(kind, id, v){
    var R = reg(kind); if(!R || !R[id] || kind === 'c') return;
    var ss = [], map = [], i = 0, cite = String(v.cite || '').trim();
    var A0 = null, X = EDK.ix || {}; Object.keys(X).forEach(function(key){ if(!A0 && X[key].r === kind) A0 = (window._ALTO_AXES || {})[key]; });
    if(cite){ ss.push({h: (A0 && A0.citeH) || 'Citation', t: esc(cite)}); map.push(-1); }
    if(String(v.t || '').trim()){ ss.push({h: esc(v.h || 'Notes'), t: esc(String(v.t).trim())}); map.push(i++); }
    if(goodLink(v.link)){ ss.push({h: 'Link', t: linkHtml(String(v.link).trim())}); map.push(i++); }
    R[id].sections = ss; EDK[kind] = EDK[kind] || {}; EDK[kind][id] = map; PRIS[kind + '|' + id] = jh('[]');
    if(marked) markObj(kind, id);
    var AX = window._ALTO_AXES || {};
    Object.keys(X).forEach(function(key){ var A = AX[key]; if(!A || X[key].r !== kind) return;
      A.cites = A.cites || {}; if(cite) A.cites[id] = esc(cite); else delete A.cites[id];
      if(A.ids){ var at = A.ids.indexOf(id), mine = String(X[key].g || '') === String(v.grp || '');
        if(mine && at < 0) A.ids.push(id); else if(!mine && at >= 0) A.ids.splice(at, 1); } });
  }
  function authDrop(kind, id){
    var AX = window._ALTO_AXES || {}, X = EDK.ix || {};
    Object.keys(X).forEach(function(key){ var A = AX[key]; if(!A || X[key].r !== kind) return;
      if(A.cites) delete A.cites[id]; if(A.ids){ var at = A.ids.indexOf(id); if(at >= 0) A.ids.splice(at, 1); } });
    if(EDK[kind]) delete EDK[kind][id]; delete PRIS[kind + '|' + id];
  }
  /* the Index page while editing: + Add at the top, ✕ (and ✎ for one made here) on each row */
  function decorateIndex(P){
    var dc = document.getElementById('detail-content'); if(!dc) return;
    var X = (EDK.ix || {})[P.id]; if(!X) return;
    if(!editing() || !structOK()){ dc.querySelectorAll('.aed-ixadd,.aed-ixc').forEach(rmEl); return; }
    var kd = chipKinds().filter(function(k){ return k.r === X.r; })[0]; if(!kd) return;
    var hd = dc.querySelector('.detail-header');
    if(!dc.querySelector('.aed-ixadd')){
    var add = document.createElement('button'); add.type = 'button'; add.className = 'aed-add aed-ixadd'; add.setAttribute('data-x', 'ixadd');
    add.setAttribute('data-r', X.r); add.setAttribute('data-g', X.g || '');
    add.textContent = '+ Add ' + aOne(kd) + ' to ' + X.l; add.title = 'Add ' + aOne(kd) + ' to this list — its name, citation, a note and a link';
    if(hd && hd.parentNode === dc) dc.insertBefore(add, hd.nextSibling); else dc.insertBefore(add, dc.firstChild);
    }
    dc.querySelectorAll('.doc-row-t[data-sd-id]').forEach(function(t){
      var row = t.closest('.doc-row'), id = t.getAttribute('data-sd-id'); if(!row || row.querySelector('.aed-ixc')) return;
      var mine = isNewChip(X.r, id);
      row.appendChild(ctl('aed-sc aed-ixc', (mine ? [['ixedit', '✎', 'Change this entry']] : []).concat([['ixdel', '✕', 'Remove this entry from the timeline']]), {ixr: X.r, ixid: id}));
    });
  }
  /* a list section (Cases, Authorities, Sources…): + Add at its foot, ↑ ↓ ✕ on each line */
  function liFmt(d, kind){
    var f = {tag: kind === 'cases' ? 'i' : '', s1: ', ', s2: ' — '}, li = null;
    Array.prototype.forEach.call(d.querySelectorAll('li'), function(x){ if(!li && x.textContent.trim()) li = x; });
    if(!li) return f;
    var el = li.firstChild; while(el && el.nodeType === 3 && !el.data.trim()) el = el.nextSibling;
    var inner = el && el.nodeType === 1 ? (el.tagName === 'A' && el.firstElementChild ? el.firstElementChild : el) : null;
    f.tag = inner && /^(I|EM|B|STRONG|U)$/.test(inner.tagName) ? inner.tagName.toLowerCase() : '';
    var rest = el && el.nodeType === 1 ? (el.nextSibling && el.nextSibling.nodeType === 3 ? el.nextSibling.data : '') : '';
    var m = /^\s*(,|:|—|–|-)\s/.exec(rest); if(m) f.s1 = m[1] === ',' || m[1] === ':' ? m[1] + ' ' : ' ' + m[1] + ' ';
    var t = li.textContent, m2 = /\s(—|–)\s/.exec(t) || /:\s/.exec(t); if(m2) f.s2 = m2[0].charAt(0) === ':' ? ': ' : ' ' + m2[1] + ' ';
    return f;
  }
  function liHtml(v, f){
    var nm = esc(v.name); if(f.tag) nm = '<' + f.tag + '>' + nm + '</' + f.tag + '>';
    if(goodLink(v.link)) nm = '<a class="note-link" href="' + esc(v.link.trim()).replace(/"/g, '&quot;') + '" target="_blank" rel="noopener">' + nm + '</a>';
    var out = nm; if(v.cite) out += f.s1 + esc(v.cite); if(v.t) out += f.s2 + esc(v.t);
    return out;
  }
  function liSet(lk, mut){
    var f = field(lk + '|t'); if(!f) return false;
    var d = document.createElement('div'); d.innerHTML = f.get();
    if(mut(d) === false) return false;
    return change(lk + '|t', d.innerHTML);
  }
  function topLis(d){ return Array.prototype.filter.call(d.querySelectorAll('li'), function(x){ return !(x.parentNode.closest && x.parentNode.closest('li')); }); }
  function liAdd(lk, at){
    var hf = field(lk + '|h'); if(!hf) return;
    var noun = authNoun(hf.get());
    askForm(at, 'Add ' + aOneW(noun), [{k: 'name', l: 'Name', req: 1}, {k: 'cite', l: 'Citation'}, {k: 't', l: 'Note', type: 'area'}, {k: 'link', l: 'Link (optional)', ph: 'https://…'}], 'Add', function(v){
      if(v.link && !goodLink(v.link)){ toast('That link needs to start with https:// — the rest was added without it.'); delete v.link; }
      if(liSet(lk, function(d){
        var fm = liFmt(d, /\bcases?\b/i.test(hf.get()) ? 'cases' : ''), ls = d.querySelectorAll('ul,ol'), ul = ls.length ? ls[ls.length - 1] : null;
        if(!ul){ ul = document.createElement('ul'); d.appendChild(ul); }
        var li = document.createElement('li'); li.innerHTML = liHtml(v, fm); ul.appendChild(li);
      })) toast('Added — ⌘Z takes it back.'); });
  }
  function liMove(lk, i, x){
    liSet(lk, function(d){ var L = topLis(d), li = L[i]; if(!li) return false;
      if(x === 'del'){ var ul = li.parentNode; ul.removeChild(li); if(!ul.children.length && ul.parentNode) ul.parentNode.removeChild(ul); toast('Removed — ⌘Z brings it back.'); return; }
      var nb = x === 'up' ? li.previousElementSibling : li.nextElementSibling; if(!nb) return false;
      if(x === 'up') li.parentNode.insertBefore(li, nb); else li.parentNode.insertBefore(nb, li); });
  }
  function decorateLists(box, k, h3){
    if(!structOK()) return;
    var hf = field(k + '|h'); if(!hf || !AUTHRE.test(hf.get()) || !topLis(box).length) return;
    topLis(box).forEach(function(li, i){
      if(li.querySelector(':scope > .aed-lic')) return;
      li.appendChild(ctl('aed-sc aed-lic', [['up', '↑', 'Move this entry up'], ['down', '↓', 'Move it down'], ['del', '✕', 'Remove this entry']], {lk: k, li: i})); });
    if(!box.querySelector(':scope > .aed-lisadd')){
      var b = document.createElement('button'); b.type = 'button'; b.className = 'aed-add aed-lisadd'; b.setAttribute('data-x', 'liadd'); b.setAttribute('data-lk', k);
      b.textContent = '+ Add ' + aOneW(authNoun(hf.get())); box.appendChild(b); }
  }
  // the + Add a section menu's "Cases" / "Authorities": the section is made with its first entry
  function addAuthSection(ok, kind, at){
    var f = field(ok + '|order'); if(!f) return;
    var cases = kind === 'cases', H = cases ? 'Cases' : 'Authorities', noun = cases ? 'case' : 'authority';
    askForm(at, 'Add ' + aOneW(noun) + ' — a new “' + H + '” list', [{k: 'name', l: 'Name', req: 1}, {k: 'cite', l: 'Citation'}, {k: 't', l: 'Note', type: 'area'}, {k: 'link', l: 'Link (optional)', ph: 'https://…'}], 'Make the list', function(v){
      if(v.link && !goodLink(v.link)){ toast('That link needs to start with https:// — the rest was added without it.'); delete v.link; }
      var nk = rid('new-'), base = ok + '|s|' + nk;
      var L = [[ok + '|order', f.get().concat(nk)], [base + '|h', H], [base + '|t', '<ul><li>' + liHtml(v, {tag: cases ? 'i' : '', s1: ', ', s2: ' — '}) + '</li></ul>']];
      if(changes(L)) setTimeout(function(){ var mk = document.querySelector('#detail-content .aed-k[data-k="' + base + '"]'), sb = mk && mk.closest('.detail-section'); if(sb) sb.scrollIntoView({block: 'center'}); }, 60); });
  }
  // ‹ › on a chip: where it stands among the card's chips
  function chipMove(nid, f, v, dir){
    var n = srcNode(nid); if(!n) return;
    var L = (n[f] || []).slice(), i = L.indexOf(v), j = i + dir;
    while(j >= 0 && j < L.length && chipGone(RK2[f], L[j])) j += dir;
    if(i < 0 || j < 0 || j >= L.length) return;
    L.splice(j, 0, L.splice(i, 1)[0]); change('ch|' + nid + '|' + f, L);
  }
  var RK2 = {chars: 'c', envs: 'env', themes: 'theme'};

  var decOvT = null;
  function decorateOvSoon(){ clearTimeout(decOvT); decOvT = setTimeout(decorateOv, 0); }
  function decorateOv(){
    if(!editing() || !OVROOT) return;
    if(EDK.ov === 'authored'){
      Array.prototype.forEach.call(OVROOT.children, function(el, i){
        if(el.classList.contains('aed-sc')) return;
        el.classList.add('aed-f', 'aed-blk'); el.setAttribute('data-aed', 'ov|html'); el.setAttribute('data-ovb', i);
        if(structOK() && !el.querySelector(':scope > .aed-sc'))
          el.appendChild(ctl('aed-sc', [['addp', '+', 'Add a paragraph after this'], ['up', '↑', 'Move up'], ['down', '↓', 'Move down'], ['del', '✕', 'Remove']], {ob: i}));
      });
    } else if(EDK.ov === 'composed'){
      var H = ovHeads();
      Object.keys(H).forEach(function(a){
        setF(H[a], 'u|' + a + '|' + ((EDK.ovf || {})[a] || 'label'));
        var ps = summaryPs(+a);
        if(!ps.length){ var ph = document.createElement('p'); ph.className = 'aed-ph'; ph.textContent = '+ Write a summary for this unit'; H[a].parentNode.insertBefore(ph, H[a].nextSibling); ps = [ph]; }
        ps.forEach(function(p){ setF(p, 'u|' + a + '|summary'); });
      });
    }
  }
  function watchPage(){
    var dc = document.getElementById('detail-content'); if(!dc) return;
    new MutationObserver(function(){ decorateSoon(); }).observe(dc, {childList:true, subtree:true});
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watchPage); else watchPage();

  /* ── editing one field ────────────────────────────────────────────────── */
  var cur = null;    // {el, k, kind, orig, body?, hidden?}
  function canvasKey(t){
    var nodeEl = t.closest('.node'); if(!nodeEl || !t.closest('#canvas')) return null;
    var wc = LN && t.closest('.lanes-when'); if(wc) return {el: wc, k: 'n|' + nodeEl.id.replace(/^node-/, '') + '|when'};
    var id = nodeEl.id.replace(/^node-/, ''), f = t.closest('.node-title,.node-tag,.node-desc'); if(!f) return null;
    return {el: f, k: 'n|' + id + '|' + f.className.match(/node-(title|tag|desc)/)[1]};
  }
  function titleKey(t){
    if(root.classList.contains('mobile')) return null;
    var te = t.closest('#title-text'); return te ? {el: te, k: 'bt|title'} : null;
  }
  function unitKey(t){
    var lb = t.closest('.phase-label-float'); if(!lb || !t.closest('#canvas')) return null;
    var all = Array.prototype.slice.call(document.querySelectorAll('#world .phase-label-float'));
    var bands = all.slice().sort(function(a, b){ return a.offsetTop - b.offsetTop; });
    var i = bands.indexOf(lb); if(i < 0) return null;
    var u = unitKeyOf(i); return {el: lb, k: typeof u === 'string' ? 'nl|' + u : 'u|' + i + '|label'};
  }
  function startField(el, k){
    if(cur && cur.el === el) return;
    endField(false);
    var f = field(k); if(!f) return;
    if(f.kind === 'html') return el.classList.contains('aed-bodypart') ? startBody(el, k, f) : startRich(el, k, f);
    if(f.kind === 'ovhtml') return startOvBlock(el);
    if(f.kind === 'para') return startPara(el, k, f);
    var orig = f.get();
    cur = {el: el, k: k, kind: 'plain', orig: orig, html: el.innerHTML, ph: el.classList.contains('aed-ph')};
    var cm = /^n\|([^|]+)\|(title|tag|desc)$/.exec(k), cc = cm && el.closest('#canvas .node-card');
    if(cc && structOK()) cur.box = {id: cm[1], w: cc.offsetWidth, h: cc.offsetHeight};
    el.classList.remove('aed-ph');
    if(k.indexOf('n|') === 0 && /\|desc$/.test(k) && el.classList.contains('alto-lead')){ cur.num = el.querySelector('.alto-lead-num'); }
    el.textContent = orig;
    try{ el.contentEditable = 'plaintext-only'; }catch(e){ el.contentEditable = 'true'; }
    if(el.contentEditable !== 'plaintext-only') el.contentEditable = 'true';
    el.classList.add('aed-on'); el.spellcheck = true; el.focus();
    caretEnd(el); keysOn(); showBar(el, false);
  }
  function startBody(el, k, f){
    var box = el.closest('[data-aed-body]') || el.parentNode;
    var parts = Array.prototype.slice.call(box.children).filter(function(c){ return c.classList.contains('aed-bodypart'); });
    var ed = document.createElement('div'); ed.className = 'aed-body aed-on'; ed.innerHTML = f.get();
    ed.querySelectorAll('.' + LOCAL_CLS).forEach(function(a){ a.contentEditable = 'false'; });
    parts.forEach(function(c){ c.style.display = 'none'; });
    var h3 = box.querySelector('h3'); box.insertBefore(ed, h3 ? h3.nextSibling : box.firstChild);
    ed.contentEditable = 'true'; ed.spellcheck = true;
    cur = {el: ed, k: k, kind: 'html', orig: f.get(), hidden: parts};
    ed.focus(); caretEnd(ed); keysOn(); showBar(ed, true);
  }
  // Rich words in place (a connection's reason): the element itself is edited.
  function startRich(el, k, f){
    cur = {el: el, k: k, kind: 'rich', orig: f.get(), html: el.innerHTML, ph: el.classList.contains('aed-ph')};
    el.classList.remove('aed-ph'); el.innerHTML = f.get();
    el.contentEditable = 'true'; el.classList.add('aed-on'); el.spellcheck = true; el.focus();
    caretEnd(el); keysOn(); showBar(el, true);
  }
  // A unit's summary (composed Overview): paragraphs as plain text, a blank line between.
  function startPara(el, k, f){
    var a = +k.split('|')[1], ps = summaryPs(a);
    if(!ps.length && el.classList.contains('aed-ph')) ps = [el];
    var ed = document.createElement('div'); ed.className = 'aed-body aed-para aed-on';
    ed.textContent = String(f.get() || '').split(/\n\s*\n/).join('\n\n');
    ps.forEach(function(x){ x.style.display = 'none'; });
    (ps[0] || el).parentNode.insertBefore(ed, ps[0] || el);
    try{ ed.contentEditable = 'plaintext-only'; }catch(e){ ed.contentEditable = 'true'; }
    if(ed.contentEditable !== 'plaintext-only') ed.contentEditable = 'true';
    cur = {el: ed, k: k, kind: 'para', orig: f.get(), hidden: ps};
    ed.focus(); caretEnd(ed); keysOn(); showBar(ed, false);
    bar().querySelector('.ab-hint').textContent = 'A new line starts a paragraph';
  }
  // One block of an authored Overview: its words come from the Overview as built
  // (not the screen, where links have been dressed up), and the whole changes.
  function ovBlocks(html){ var d = document.createElement('div'); d.innerHTML = html; return d; }
  function startOvBlock(el){
    var i = +el.getAttribute('data-ovb'), d = ovBlocks(OVCUR), blk = d.children[i]; if(!blk) return;
    var head = /^H[1-6]$/.test(blk.tagName);
    cur = {el: el, k: 'ov|html', kind: 'ovb', i: i, head: head, html: el.innerHTML, orig: head ? blk.textContent : blk.innerHTML};
    if(head) el.textContent = blk.textContent; else el.innerHTML = blk.innerHTML;
    el.querySelectorAll('.ov-node-link,.' + LOCAL_CLS).forEach(function(x){ x.contentEditable = 'false'; });
    if(head){ try{ el.contentEditable = 'plaintext-only'; }catch(e){} if(el.contentEditable !== 'plaintext-only') el.contentEditable = 'true'; }
    else el.contentEditable = 'true';
    el.classList.add('aed-on'); el.spellcheck = true; el.focus();
    caretEnd(el); keysOn(); showBar(el, !head);
  }
  function ovSet(fn){ var d = ovBlocks(OVCUR); if(fn(d) === false) return false; return change('ov|html', d.innerHTML); }
  function caretEnd(el){ try{ var r = document.createRange(); r.selectNodeContents(el); r.collapse(false); var s = getSelection(); s.removeAllRanges(); s.addRange(r); }catch(e){} }
  function endField(save){
    if(!cur) return; var c = cur; cur = null;
    keysOff(); hideBar(); hideLink();
    c.el.classList.remove('aed-on'); c.el.removeAttribute('contenteditable');
    if(c.kind === 'rich'){
      var vr = save ? clean(c.el) : c.orig;
      c.el.innerHTML = c.html; if(c.ph) c.el.classList.add('aed-ph');
      if(save && !same(vr, c.orig)) change(c.k, vr);
      return;
    }
    if(c.kind === 'para'){
      var vp = save ? String(c.el.innerText || c.el.textContent || '').replace(/\u00a0/g, ' ').replace(/</g, '')
        .split(/\n+/).map(function(x){ return x.replace(/\s+/g, ' ').trim(); }).filter(Boolean).join('\n\n') : c.orig;
      c.el.parentNode.removeChild(c.el);
      (c.hidden || []).forEach(function(x){ x.style.display = ''; });
      if(save && !same(vp, c.orig)) change(c.k, vp);
      return;
    }
    if(c.kind === 'ovb'){
      var vb = save ? (c.head ? String(c.el.textContent || '').replace(/</g, '').replace(/\s+/g, ' ').trim() : clean(c.el)) : c.orig;
      c.el.innerHTML = c.html;
      if(save && !same(vb, c.orig)) ovSet(function(d){ var b = d.children[c.i]; if(!b) return false; if(c.head) b.textContent = vb; else b.innerHTML = vb; });
      return;
    }
    if(c.kind === 'html'){
      var v = save ? clean(c.el) : c.orig;
      c.el.parentNode.removeChild(c.el);
      (c.hidden || []).forEach(function(x){ x.style.display = ''; });
      if(save && !same(v, c.orig)) change(c.k, v);
      return;
    }
    // plain text, as the build makes it (sanitize.plain_text): no '<' at all
    var v2 = String(c.el.textContent || '').replace(/</g, '').replace(/\s+/g, ' ').trim();
    var needs = /\|(title|name|label)$/.test(c.k) && c.k.indexOf('dt|') !== 0 || /^dt\|[^|]+\|[^|]+\|title$/.test(c.k);
    if(c.ph) c.el.classList.add('aed-ph');
    if(!save || (needs && !v2) || v2 === c.orig){
      c.el.innerHTML = c.html;
      if(save && needs && !v2) toast('A title cannot be empty — it is back as it was.');
      return;
    }
    c.el.innerHTML = c.html;           // what the page shows is re-drawn from the data
    if(change(c.k, v2) && c.box){
      var g = growFor(c.box.id, c.box.w, c.box.h);
      if(g) joinLast('sz|' + c.box.id, g);
    }
  }
  // one more change, undone with the one before it
  function joinLast(k, v){
    var f = field(k); if(!f) return false; var a = f.get(); if(same(a, v) || !apply(k, v)) return false;
    if(HP > 0 && HP === HIST.length) HIST[HP - 1].push({k: k, a: a, b: v}); else { HIST = HIST.slice(0, HP); HIST.push([{k: k, a: a, b: v}]); HP = HIST.length; }
    syncHist(); return true;
  }

  // A page's text, cleaned to what Alto pages allow (the build cleans again).
  var OK = {B:1,STRONG:1,I:1,EM:1,U:1,S:1,SMALL:1,CODE:1,SUP:1,SUB:1,BR:1,P:1,UL:1,OL:1,LI:1,BLOCKQUOTE:1,H4:1,H5:1,H6:1,HR:1,SPAN:1,A:1,DIV:1,Q:1,CITE:1,MARK:0};
  function clean(ed){
    function walk(src, dst){
      Array.prototype.forEach.call(src.childNodes, function(n){
        if(n.nodeType === 3){ dst.appendChild(document.createTextNode(n.nodeValue)); return; }
        if(n.nodeType !== 1) return;
        var tag = n.tagName;
        if(tag === 'A' && n.classList.contains(LOCAL_CLS)){ var ic = n.cloneNode(false); ic.removeAttribute('contenteditable'); dst.appendChild(ic); return; }
        if(tag === 'SPAN' && n.classList.contains('ov-node-link')){
          var ob = n.querySelector('button.ov-node-btn'), om = ob && /^showDetail\('node','([a-z0-9][a-z0-9-]{0,47})'\)$/.exec(ob.getAttribute('onclick') || '');
          if(om){ var sp = document.createElement('span'); sp.className = 'ov-node-link'; var bt = document.createElement('button'); bt.className = 'ov-node-btn';
            bt.setAttribute('onclick', "showDetail('node','" + om[1] + "')"); var first = n.firstChild === ob;
            if(first) sp.appendChild(bt); sp.appendChild(document.createTextNode(n.textContent)); if(!first) sp.appendChild(bt); dst.appendChild(sp); return; }
          walk(n, dst); return;
        }
        if(tag === 'BUTTON') return;
        if(tag === 'SPAN' && n.classList.contains('alto-link') && /^(node|char|env|theme)$/.test(n.getAttribute('data-sd-type') || '') && /^[a-z0-9][a-z0-9-]{0,47}$/.test(n.getAttribute('data-sd-id') || '')){
          var s = document.createElement('span'); s.className = 'alto-link'; s.setAttribute('data-sd-type', n.getAttribute('data-sd-type')); s.setAttribute('data-sd-id', n.getAttribute('data-sd-id')); walk(n, s); dst.appendChild(s); return; }
        if(tag === 'A' && FILE_ID.test(n.getAttribute('data-file') || '')){
          var fa = document.createElement('a'); fa.setAttribute('href', '#'); fa.className = 'note-link'; fa.setAttribute('data-file', n.getAttribute('data-file'));
          var fnm = String(n.getAttribute('data-file-name') || '').replace(/[\u0000-\u001f<>"]/g, '').slice(0, 200); if(fnm) fa.setAttribute('data-file-name', fnm);
          ['data-file-size', 'data-file-mod'].forEach(function(at){ var v = n.getAttribute(at); if(v && /^\d{1,15}$/.test(v)) fa.setAttribute(at, v); });
          walk(n, fa); dst.appendChild(fa); return; }
        if(tag === 'A'){
          var href = n.getAttribute('href') || '';
          if(/^(https?:\/\/|mailto:)/i.test(href)){ var a = document.createElement('a'); a.setAttribute('href', href);
            var tt = n.getAttribute('title'); if(tt) a.setAttribute('title', tt.slice(0, 300));
            a.className = 'note-link'; a.target = '_blank'; a.rel = 'noopener';
            var ds = n.getAttribute('data-src'); if(ds && /^[a-z0-9][a-z0-9-]{0,63}$/.test(ds)) a.setAttribute('data-src', ds); walk(n, a); dst.appendChild(a); return; }
          if(href === '#' && n.getAttribute('data-src')){ var a2 = document.createElement('a'); a2.setAttribute('href', '#'); a2.className = 'note-link'; a2.setAttribute('data-src', n.getAttribute('data-src')); walk(n, a2); dst.appendChild(a2); return; }
          walk(n, dst); return;
        }
        if(tag === 'MARK' || tag === 'FONT' || !OK[tag]){ walk(n, dst); return; }
        if(tag === 'DIV') tag = 'BR_DIV';
        if(tag === 'BR_DIV'){ if(dst.lastChild) dst.appendChild(document.createElement('br')); walk(n, dst); return; }
        var e = document.createElement(tag.toLowerCase());
        // a span the build wrote (a source note's item, its "Notes" tag…)
        // keeps its class; one the editor made (style only) is unwrapped
        if(tag === 'SPAN'){
          var sc = String(n.getAttribute('class') || '').trim();
          if(/^[a-z][a-z0-9-]*( [a-z][a-z0-9-]*)*$/.test(sc) && !/(^| )(aed|adt)-/.test(sc) && sc.length <= 80){ e.className = sc; walk(n, e); dst.appendChild(e); }
          else walk(n, dst);
          return; }
        walk(n, e); dst.appendChild(e);
      });
    }
    var out = document.createElement('div'); walk(ed, out);
    var h = out.innerHTML.replace(/(<br>)+$/, '').replace(/^\s+|\s+$/g, '');
    return h;
  }

  /* ── the bar over a field: link, bold, italic, done ───────────────────── */
  function bar(){
    var b = document.getElementById('aed-bar'); if(b) return b;
    b = document.createElement('div'); b.id = 'aed-bar';
    b.innerHTML = '<button type="button" data-a="link" title="Link the selected words to a page or a website">🔗 Link</button>'
      + '<button type="button" data-a="unlink" title="Remove the link">Unlink</button><span class="ab-sep"></span>'
      + '<button type="button" data-a="bold" title="Bold (⌘B)"><b>B</b></button><button type="button" data-a="italic" title="Italic (⌘I)"><i>I</i></button>'
      + '<span class="ab-sep"></span><span class="ab-hint"></span><button type="button" data-a="cancel">Cancel</button><button type="button" class="ab-done" data-a="done">Done</button>';
    b.addEventListener('mousedown', function(e){ e.preventDefault(); e.stopPropagation(); });   // keep the selection
    b.addEventListener('click', function(e){
      var t = e.target.closest('button'); if(!t) return; e.stopPropagation();
      var a = t.getAttribute('data-a');
      if(a === 'done') endField(true);
      else if(a === 'cancel') endField(false);
      else if(a === 'bold' || a === 'italic'){ try{ document.execCommand(a); }catch(_){} }
      else if(a === 'unlink') unlinkSel();
      else if(a === 'link') openLink();
    });
    document.body.appendChild(b); return b;
  }
  function showBar(el, rich){
    var b = bar(); b.classList.toggle('rich', rich);
    Array.prototype.forEach.call(b.querySelectorAll('[data-a=link],[data-a=unlink],[data-a=bold],[data-a=italic]'), function(x){ x.style.display = rich ? '' : 'none'; });
    Array.prototype.forEach.call(b.querySelectorAll('.ab-sep'), function(x, i){ x.style.display = rich ? '' : 'none'; });
    b.querySelector('.ab-hint').textContent = rich ? 'Select words, then Link'
      : (root.classList.contains('mobile') ? 'Tap Done to save' : 'Enter to save · Esc to cancel');
    b.classList.add('show'); placeBar();
    // A phone's keyboard covers the lower half: bring the field up to the
    // middle of what is still visible once it has opened.
    if(root.classList.contains('mobile')) [60, 450].forEach(function(ms){ setTimeout(function(){ if(cur && cur.el === el){ liftField(el); placeBar(); } }, ms); });
  }
  // The field just under the page's header: a phone's keyboard covers the
  // lower half, and the page itself is pinned, so its scrolling box moves.
  function liftField(el){
    for(var p = el.parentElement; p && p !== document.body; p = p.parentElement){
      var cs = getComputedStyle(p);
      if(/(auto|scroll)/.test(cs.overflowY) && p.scrollHeight > p.clientHeight){
        var top = p.getBoundingClientRect().top, pill = document.getElementById('alto-edit-exit');
        if(pill && pill.offsetHeight) top = Math.max(top, pill.getBoundingClientRect().bottom);
        var dy = el.getBoundingClientRect().top - (top + 70);
        if(Math.abs(dy) > 8) p.scrollTop += dy;
        return;
      }
    }
  }
  // Above the field, else below it, always inside what can be seen — on a
  // phone that is the visual viewport, which the keyboard shrinks.
  function placeBar(){
    var b = document.getElementById('aed-bar'); if(!b || !cur || !b.classList.contains('show')) return;
    var r = cur.el.getBoundingClientRect(), w = b.offsetWidth, h = b.offsetHeight, vv = window.visualViewport;
    var vt = vv ? vv.offsetTop : 0, vh = vv ? vv.height : window.innerHeight, minTop = vt + (root.classList.contains('mobile') ? 8 : 70);
    var top = r.top - h - 10;
    if(top < minTop) top = r.bottom + 10;
    if(top > vt + vh - h - 8) top = Math.max(minTop, vt + vh - h - 8);
    b.style.top = Math.round(top) + 'px'; b.style.left = Math.round(Math.max(8, Math.min(window.innerWidth - w - 8, r.left))) + 'px';
  }
  if(window.visualViewport){ window.visualViewport.addEventListener('resize', function(){ placeBar(); }); window.visualViewport.addEventListener('scroll', function(){ placeBar(); }); }
  function hideBar(){ var b = document.getElementById('aed-bar'); if(b) b.classList.remove('show'); }
  window.addEventListener('scroll', placeBar, true); window.addEventListener('resize', placeBar);

  /* ── links: to a page of this timeline, or out to a website ───────────── */
  var savedRange = null;
  function selRange(){ var s = getSelection(); if(!s || !s.rangeCount) return null; var r = s.getRangeAt(0);
    return cur && cur.el.contains(r.commonAncestorContainer) && !r.collapsed ? r.cloneRange() : null; }
  function targets(){
    var out = [];
    try{ NODES_SRC.forEach(function(n){ out.push({t:'node', id:n.id, name:n.title, k:n.tag || 'Card'}); }); }catch(e){}
    [['char', 'c'], ['env', 'env'], ['theme', 'theme']].forEach(function(p){ var R = reg(p[1]); if(!R) return;
      Object.keys(R).forEach(function(id){ out.push({t:p[0], id:id, name:txt(R[id].name), k:txt(R[id].role) || ({char:'Element', env:'Case', theme:'Page'}[p[0]])}); }); });
    return out;
  }
  function linkBox(){
    var b = document.getElementById('aed-link'); if(b) return b;
    b = document.createElement('div'); b.id = 'aed-link';
    b.innerHTML = '<h5>Link to a page in this timeline</h5><input class="al-q" type="text" placeholder="Search pages…" autocomplete="off">'
      + '<div class="al-list"></div><h5>or a website</h5><input class="al-url" type="url" placeholder="https://…" autocomplete="off">'
      + '<div class="al-msg"></div><div class="al-go"><button type="button" data-a="cancel">Cancel</button><button type="button" data-a="url">Link website</button></div>'
      + '<h5 class="al-fh">or a file on this computer</h5><div class="al-go"><button type="button" data-a="file">Choose a file…</button></div>'
      + '<div class="al-k al-fk">It opens from this browser on this computer. Claude also finds it in your Desktop, Documents or Downloads, so the copy of the timeline you download opens it too.</div>';
    b.addEventListener('mousedown', function(e){ e.stopPropagation(); });
    b.addEventListener('click', function(e){
      e.stopPropagation();
      var row = e.target.closest('.al-row'); if(row){ makeLink({t: row.getAttribute('data-t'), id: row.getAttribute('data-id')}); return; }
      var a = e.target.closest('button') && e.target.closest('button').getAttribute('data-a');
      if(a === 'cancel') hideLink(true);
      if(a === 'url') linkUrl();
      if(a === 'file') linkFile();
    });
    b.querySelector('.al-q').addEventListener('input', function(){ list(this.value); });
    b.querySelector('.al-q').addEventListener('keydown', function(e){ if(e.key === 'Enter'){ e.preventDefault(); var r = b.querySelector('.al-row'); if(r) r.click(); } if(e.key === 'Escape'){ e.preventDefault(); hideLink(true); } });
    b.querySelector('.al-url').addEventListener('keydown', function(e){ if(e.key === 'Enter'){ e.preventDefault(); linkUrl(); } if(e.key === 'Escape'){ e.preventDefault(); hideLink(true); } });
    document.body.appendChild(b); return b;
  }
  function list(q){
    var b = linkBox(), L = b.querySelector('.al-list'), Q = String(q || '').toLowerCase().trim();
    var hits = targets().filter(function(x){ return !Q || x.name.toLowerCase().indexOf(Q) >= 0; }).slice(0, 40);
    L.innerHTML = '';
    hits.forEach(function(x){ var r = document.createElement('div'); r.className = 'al-row'; r.setAttribute('data-t', x.t); r.setAttribute('data-id', x.id);
      var a = document.createElement('span'); a.textContent = x.name; var k = document.createElement('span'); k.className = 'al-k'; k.textContent = x.k;
      r.appendChild(a); r.appendChild(k); L.appendChild(r); });
    if(!hits.length){ var none = document.createElement('div'); none.className = 'al-k'; none.style.padding = '6px 8px'; none.textContent = 'No page by that name.'; L.appendChild(none); }
  }
  function openLink(){
    savedRange = selRange();
    if(!savedRange){ toast('Select the words to link first.'); return; }
    var b = linkBox(); b.querySelector('.al-q').value = ''; b.querySelector('.al-url').value = ''; b.querySelector('.al-msg').textContent = '';
    list(''); b.classList.add('show');
    var r = savedRange.getBoundingClientRect();
    b.style.top = Math.round(Math.min(window.innerHeight - b.offsetHeight - 8, r.bottom + 10)) + 'px';
    b.style.left = Math.round(Math.max(8, Math.min(window.innerWidth - b.offsetWidth - 8, r.left))) + 'px';
    b.querySelector('.al-q').focus();
  }
  function hideLink(back){ var b = document.getElementById('aed-link'); if(b) b.classList.remove('show');
    if(back && cur && savedRange){ cur.el.focus(); var s = getSelection(); s.removeAllRanges(); s.addRange(savedRange); } }
  function wrapSel(el){
    if(!cur || !savedRange) return;
    cur.el.focus(); var s = getSelection(); s.removeAllRanges(); s.addRange(savedRange);
    var frag = savedRange.extractContents();
    // a link never holds another link
    Array.prototype.forEach.call(frag.querySelectorAll ? frag.querySelectorAll('a,span.alto-link,span.ov-node-link') : [], function(x){ while(x.firstChild) x.parentNode.insertBefore(x.firstChild, x); x.parentNode.removeChild(x); });
    Array.prototype.forEach.call(frag.querySelectorAll ? frag.querySelectorAll('button') : [], function(x){ x.parentNode.removeChild(x); });
    el.appendChild(frag); savedRange.insertNode(el);
    s.removeAllRanges(); var r = document.createRange(); r.selectNodeContents(el); s.addRange(r);
    savedRange = null; hideLink(false);
  }
  function makeLink(x){
    if(cur && cur.kind === 'ovb' && x.t === 'node'){
      var o = document.createElement('span'); o.className = 'ov-node-link'; var b = document.createElement('button'); b.className = 'ov-node-btn';
      b.setAttribute('onclick', "showDetail('node','" + x.id + "')"); o.appendChild(b); wrapSel(o); return;
    }
    var s = document.createElement('span'); s.className = 'alto-link'; s.setAttribute('data-sd-type', x.t); s.setAttribute('data-sd-id', x.id); wrapSel(s);
  }
  function linkUrl(){
    var b = linkBox(), u = b.querySelector('.al-url').value.trim();
    if(/^www\./i.test(u)) u = 'https://' + u;
    if(!/^(https?:\/\/[^\s<>"]+|mailto:[^\s<>"]+)$/i.test(u)){ b.querySelector('.al-msg').textContent = 'Paste a full web address (https://…).'; return; }
    var a = document.createElement('a'); a.setAttribute('href', u); a.className = 'note-link'; a.target = '_blank'; a.rel = 'noopener'; wrapSel(a);
  }
  /* a file on this computer: the page keeps it (or, where the browser can,
     its place on disk) in this browser's own storage, under the link's id */
  var FILE_ID = /^file-[a-z0-9]{6,12}$/, MAX_KEEP = 300 * 1024 * 1024;
  var fdbP = null;
  function fdb(){
    if(!fdbP) fdbP = new Promise(function(res, rej){
      try{ var r = indexedDB.open('alto-files', 1);
        r.onupgradeneeded = function(){ r.result.createObjectStore('f'); };
        r.onsuccess = function(){ res(r.result); }; r.onerror = function(){ rej(r.error); }; }catch(e){ rej(e); } });
    return fdbP;
  }
  function fput(id, rec){ return fdb().then(function(db){ return new Promise(function(res, rej){
    var t = db.transaction('f', 'readwrite'); t.objectStore('f').put(rec, id); t.oncomplete = function(){ res(); }; t.onerror = t.onabort = function(){ rej(t.error); }; }); }); }
  function fget(id){ return fdb().then(function(db){ return new Promise(function(res){
    var q = db.transaction('f').objectStore('f').get(id); q.onsuccess = function(){ res(q.result || null); }; q.onerror = function(){ res(null); }; }); }).catch(function(){ return null; }); }
  function pickFile(){
    if(typeof window.showOpenFilePicker === 'function')
      return window.showOpenFilePicker({multiple: false}).then(function(hs){ return hs[0].getFile().then(function(f){ return {file: f, handle: hs[0]}; }); });
    return new Promise(function(res, rej){
      var inp = document.createElement('input'); inp.type = 'file'; inp.style.cssText = 'position:fixed;left:-9999px;top:0;';
      inp.addEventListener('change', function(){ var f = inp.files && inp.files[0]; inp.remove(); if(f) res({file: f}); else rej(new Error('none')); });
      inp.addEventListener('cancel', function(){ inp.remove(); rej(new Error('none')); });
      // inside the link box: a click there is not a click away from the words
      (document.getElementById('aed-link') || document.body).appendChild(inp); inp.click();
    });
  }
  function linkFile(){
    var b = linkBox(), keep = savedRange;
    pickFile().then(function(got){
      var f = got.file, id = rid('file-') + Math.random().toString(36).slice(2, 4);
      var rec = {name: f.name, size: f.size, type: f.type || '', mod: f.lastModified || 0};
      // where the browser can, its place on disk (opens the file as it is
      // now); elsewhere a copy of its bytes (WebKit will not keep a File in a
      // private window, bytes it will)
      var ready = got.handle ? Promise.resolve(rec.handle = got.handle)
        : f.size <= MAX_KEEP ? f.arrayBuffer().then(function(b){ rec.buf = b; }) : Promise.resolve();
      return ready.then(function(){ return fput(id, rec); }).catch(function(){ delete rec.buf; delete rec.handle; return fput(id, rec); }).then(function(){
        if(!rec.handle && !rec.buf) toast('“' + f.name + '” is linked, but too big to keep in this browser — the timeline you download opens it.');
        savedRange = keep;
        var a = document.createElement('a'); a.setAttribute('href', '#'); a.className = 'note-link'; a.setAttribute('data-file', id);
        a.setAttribute('data-file-name', String(f.name).slice(0, 200)); a.setAttribute('data-file-size', String(f.size));
        if(f.lastModified) a.setAttribute('data-file-mod', String(f.lastModified));
        wrapSel(a);
      });
    }).catch(function(e){ if(e && e.message !== 'none' && e.name !== 'AbortError') b.querySelector('.al-msg').textContent = 'That file could not be linked here.'; });
  }
  // Opens in a tab what a browser shows; anything else is handed to its own app.
  var VIEW = /\.(pdf|png|jpe?g|gif|webp|svg|txt|md|csv|html?|mp4|mov|webm|mp3|m4a|wav)$/i;
  function fileName(a, id){
    var n = a.getAttribute('data-file-name'); if(n) return n;
    var L = (window['_ALTO_' + 'LOCAL'] || {}).files || {}; if(L[id] && L[id].p) return String(L[id].p).split(/[\\/]/).pop();
    return a.textContent || 'the file';
  }
  function openFile(id, name){
    var w = null; if(VIEW.test(name)){ try{ w = window.open('', '_blank'); }catch(e){} }
    fget(id).then(function(rec){
      if(!rec){ if(w) w.close(); toast('“' + name + '” is on the computer it was linked from — open this timeline there to open it.'); return; }
      var got = rec.handle ? Promise.resolve(rec.handle.queryPermission ? rec.handle.queryPermission({mode: 'read'}) : 'granted').then(function(st){
          return st === 'granted' ? st : rec.handle.requestPermission({mode: 'read'}); }).then(function(st){ if(st !== 'granted') throw new Error('denied'); return rec.handle.getFile(); })
        : Promise.resolve(rec.buf ? new Blob([rec.buf], {type: rec.type || ''}) : null);
      return got.then(function(file){ if(!file) throw new Error('gone'); showBlob(file, rec.name || name, w); });
    }).catch(function(){ if(w) w.close(); toast('“' + name + '” could not be opened — it may have been moved or renamed. Link it again.'); });
  }
  function showBlob(file, name, w){
    var u = URL.createObjectURL(file);
    if(w) w.location.href = u;
    else { var a = document.createElement('a'); a.href = u; a.download = name; document.body.appendChild(a); a.click(); a.remove(); }
    setTimeout(function(){ URL.revokeObjectURL(u); }, 120000);
  }
  // On the web a page cannot reach a file on disk by its path: the link opens
  // what this browser kept. (A copy opened from disk opens the path itself —
  // detail_extras.LOCAL_OPEN.)
  if(/^https?:/.test(location.protocol)) window.addEventListener('click', function(e){
    var a = e.target && e.target.closest && e.target.closest('a[data-file],a.note-link[data-src^="file-"],a[data-src-local^="file-"]');
    if(!a || editing() || (cur && cur.el.contains(a))) return;
    var id = a.getAttribute('data-file') || a.getAttribute('data-src') || a.getAttribute('data-src-local');
    if(!FILE_ID.test(id || '')) return;
    e.preventDefault(); e.stopPropagation();
    openFile(id, fileName(a, id));
  }, true);

  function unlinkSel(){
    if(!cur) return; var s = getSelection(); if(!s.rangeCount) return;
    var n = s.anchorNode; n = n && (n.nodeType === 1 ? n : n.parentNode);
    var l = n && n.closest('a.note-link,span.alto-link,span.ov-node-link'); if(!l || !cur.el.contains(l)) { toast('Put the cursor in a link to remove it.'); return; }
    l.querySelectorAll('button').forEach(function(b){ b.parentNode.removeChild(b); });
    while(l.firstChild) l.parentNode.insertBefore(l.firstChild, l); l.parentNode.removeChild(l);
  }

  /* ── keys ─────────────────────────────────────────────────────────────── */
  // While a field is being edited, Escape cancels the field instead of
  // closing the page: the engine's capture handler is set aside meanwhile.
  function fieldKeys(e){
    if(!cur) return;
    if(e.key === 'Escape'){ e.preventDefault(); e.stopImmediatePropagation(); if(document.getElementById('aed-link') && document.getElementById('aed-link').classList.contains('show')) hideLink(true); else endField(false); return; }
    if(e.key === 'Enter' && (cur.kind === 'plain' || e.metaKey || e.ctrlKey)){ e.preventDefault(); e.stopImmediatePropagation(); endField(true); return; }
    if(cur.kind === 'plain' && (e.metaKey || e.ctrlKey) && /^[bi]$/i.test(e.key)) e.preventDefault();
  }
  var keysAreOn = false;
  function keysOn(){
    if(keysAreOn) return; keysAreOn = true;
    if(window._unifiedEscape) window.removeEventListener('keydown', window._unifiedEscape, true);
    window.addEventListener('keydown', fieldKeys, true);
  }
  function keysOff(){
    if(!keysAreOn) return; keysAreOn = false;
    window.removeEventListener('keydown', fieldKeys, true);
    if(window._unifiedEscape) window.addEventListener('keydown', window._unifiedEscape, true);
  }
  // Undo / redo from the keyboard: edits in edit mode, notes and highlights
  // otherwise. A text box being typed in keeps its own.
  window.addEventListener('keydown', function(e){
    if(e.key === 'Escape' && PICK && !cur){ e.preventDefault(); e.stopImmediatePropagation(); endPick(); drawFilters(); }
    if(e.key === 'Escape' && LINK && !cur){ e.preventDefault(); e.stopImmediatePropagation(); endLink(); }
  }, true);
  document.addEventListener('keydown', function(e){
    if(!(e.metaKey || e.ctrlKey) || e.altKey) return;
    var key = String(e.key || '').toLowerCase();
    var isUndo = key === 'z' && !e.shiftKey, isRedo = (key === 'z' && e.shiftKey) || (key === 'y' && e.ctrlKey && !e.metaKey);
    if(!isUndo && !isRedo) return;
    var a = document.activeElement;
    if(a && (a.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName))) return;
    var done = false;
    if(editing()) done = isUndo ? undo() : redo();
    else { var H = window._altoNotesHist; if(H) done = isUndo ? H.undo() : H.redo();
      if(done){ try{ if(window._altoNotesSync) window._altoNotesSync(); }catch(_){} } }
    if(done || editing()){ e.preventDefault(); }
  });

  /* ── clicks and drags while editing ───────────────────────────────────── */
  function inUi(t){ return t.closest('#aed-bar,#aed-link,#alto-edit-exit,.alto-edit-pill,#aed-toast,#aed-pick,#aed-pickres,#aed-linkbar,#aed-chip,#aed-chpop,#aed-glyph,#aed-name,#aed-form,#aed-kinds,#aed-ask,#aed-study,#ef-panel,#filter-toggle'); }
  // Move, add and remove: a page's sections, a tree's steps, an Overview's blocks.
  function structure(b){
    var x = b.getAttribute('data-x') || (b.classList.contains('aed-uc') ? 'addcu' : ''), w = b.closest('.aed-sc,.aed-tc,.aed-cc');
    if(x === 'addsec'){ chooseKind(b, b.getAttribute('data-ok')); return; }
    if(x === 'addcu'){ addCard(null, +b.getAttribute('data-act')); return; }
    if(x === 'addunit'){ addUnit(); return; }
    if(x === 'renu'){ renameUnit(+b.getAttribute('data-act')); return; }
    if(x === 'delu'){ deleteUnit(+b.getAttribute('data-act')); return; }
    if(x === 'chipdel'){ var n2 = b.getAttribute('data-nid') || (page() || {}).id; if(n2) chipToggle(n2, b.getAttribute('data-f'), b.getAttribute('data-v'), false); return; }
    if(x === 'chipadd'){ var n3 = b.getAttribute('data-nid') || (page() || {}).id; if(n3){ var keep = document.getElementById('aed-chpop'); var open = keep && keep.classList.contains('show');
      chooseChip(b, n3, b.getAttribute('data-f')); if(open) keep.classList.add('show'); } return; }
    if(x === 'navadd'){ navAdd(b); return; }
    if(x === 'ixadd'){ var xk = chipKinds().filter(function(q){ return q.r === b.getAttribute('data-r'); })[0]; if(xk) addAuthority(b, xk, {grp: b.getAttribute('data-g') || ''}); return; }
    if(x === 'liadd'){ liAdd(b.getAttribute('data-lk'), b); return; }
    if(x === 'chipmv'){ chipMove(b.getAttribute('data-nid') || (page() || {}).id, b.getAttribute('data-f'), b.getAttribute('data-v'), +b.getAttribute('data-d')); return; }
    if(w && w.hasAttribute('data-ixid')){
      var ir = w.getAttribute('data-ixr'), ii = w.getAttribute('data-ixid');
      if(x === 'ixdel') navRemove({getAttribute: function(a){ return {'data-r': ir, 'data-id': ii}[a] || null; }});
      else if(x === 'ixedit'){ var ek = chipKinds().filter(function(q){ return q.r === ir; })[0]; if(ek) editAuthority(b, ek, ii); }
      return;
    }
    if(w && w.hasAttribute('data-lk')){ liMove(w.getAttribute('data-lk'), +w.getAttribute('data-li'), x); return; }
    if(x === 'navx'){ navRemove(b); return; }
    if(w && w.hasAttribute('data-cid')){
      var cid = w.getAttribute('data-cid');
      if(x === 'addc') addCard(cid, null); else if(x === 'delc') removeCard(cid); else if(x === 'linkc') startLink(cid); else if(x === 'swapc') swapMenu(cid); else if(x === 'linec') lineMenu(cid); else if(x === 'chipc') chipPop(cid, b);
      return;
    }
    if(x === 'fltoggle'){ var P0 = page(); if(P0) toggleFlag(P0.id, b.getAttribute('data-fl')); return; }
    if(x === 'flnew'){ var P1 = page(); if(!P1) return;
      askName(b, 'Name your filter', '', function(nm){ var nf = newFlag(nm); if(!nf) return;
        changes([['fl|list', FLAGS.concat([nf])], ['fn|' + P1.id, (FLN[P1.id] || []).concat([nf.id])]]); });
      return; }
    if(w && w.hasAttribute('data-sk')){
      var sk = w.getAttribute('data-sk').split('|'), okey = sk[0] + '|' + sk[1], f2 = field(okey + '|order'); if(!f2) return;
      var o = f2.get(), i = o.indexOf(sk[3]); if(i < 0) return;
      if(x === 'del'){ o.splice(i, 1); if(change(okey + '|order', o)) toast('Section removed — ⌘Z brings it back.'); }
      else if(x === 'up' && i > 0){ o.splice(i - 1, 0, o.splice(i, 1)[0]); change(okey + '|order', o); }
      else if(x === 'down' && i < o.length - 1){ o.splice(i + 1, 0, o.splice(i, 1)[0]); change(okey + '|order', o); }
      return;
    }
    if(w && w.hasAttribute('data-tk')){
      var tk = w.getAttribute('data-tk'), ts = w.getAttribute('data-ts'), tf = field('dt|' + tk + '|tree'); if(!tf) return;
      var n = tf.get(), me = n.filter(function(q){ return q.i === ts; })[0]; if(!me) return;
      if(x === 'add'){
        var ni = rid('s-'); n.push({i: ni, p: ts, t: 'New step'});
        if(change('dt|' + tk + '|tree', n)) setTimeout(function(){ var c = document.querySelector('#detail-content .adt[data-adt-key="' + tk + '"] .adt-card[data-i="' + ni + '"] .adt-t');
          if(c){ decorate(); startField(c, 'dt|' + tk + '|' + ni + '|title'); try{ document.execCommand('selectAll'); }catch(_){} } }, 60);
        return;
      }
      if(x === 'del'){
        var gone = {}; gone[ts] = 1; var more = true;
        while(more){ more = false; n.forEach(function(q){ if(q.p && gone[q.p] && !gone[q.i]){ gone[q.i] = 1; more = true; } }); }
        if(change('dt|' + tk + '|tree', n.filter(function(q){ return !gone[q.i]; }))) toast('Step removed — ⌘Z brings it back.');
        return;
      }
      var sib = n.filter(function(q){ return (q.p || '') === (me.p || ''); }), k = sib.indexOf(me), other = sib[x === 'up' ? k - 1 : k + 1];
      if(!other) return;
      var a1 = n.indexOf(me), a2 = n.indexOf(other); n[a1] = other; n[a2] = me;
      change('dt|' + tk + '|tree', n);
      return;
    }
    if(w && w.hasAttribute('data-ob')){
      var bi = +w.getAttribute('data-ob');
      if(x === 'addp'){
        if(ovSet(function(d){ var b0 = d.children[bi]; if(!b0) return false; var np = document.createElement('p'); np.textContent = 'New paragraph.'; d.insertBefore(np, b0.nextSibling); }))
          setTimeout(function(){ var el = OVROOT.children[bi + 1]; if(el){ decorateOv(); startField(el, 'ov|html'); try{ document.execCommand('selectAll'); }catch(_){} } }, 60);
        return;
      }
      ovSet(function(d){ var b0 = d.children[bi]; if(!b0) return false;
        if(x === 'del'){ d.removeChild(b0); toast('Removed — ⌘Z brings it back.'); }
        else if(x === 'up'){ if(!b0.previousElementSibling) return false; d.insertBefore(b0, b0.previousElementSibling); }
        else if(x === 'down'){ var nx = b0.nextElementSibling; if(!nx) return false; d.insertBefore(nx, b0); } });
    }
  }
  function eatIfEditing(e){
    if(!editing()) return;
    var t = e.target; if(!t || !t.closest || inUi(t)) return;
    if(cur && cur.el.contains(t)){ e.stopPropagation(); return; }       // typing / selecting inside the field
    var ck = canvasKey(t) || unitKey(t) || titleKey(t);
    var f = t.closest('[data-aed]'), body = t.closest('.aed-bodypart');
    if(ck || f || body || t.closest('#canvas .node-card') || t.closest('.adt-card') || t.closest('.aed-sc,.aed-tc,.aed-cc,.aed-add,.aed-uc,.aed-flags,.aed-chips,.aed-nadd,.aed-nx') || ((PICK || LINK) && t.closest('#canvas .node'))){
      e.stopPropagation(); if(e.type === 'click') e.preventDefault();
    }
  }
  ['mousedown', 'mouseup', 'dblclick'].forEach(function(ev){ window.addEventListener(ev, eatIfEditing, true); });
  window.addEventListener('click', function(e){
    if(!editing()) return;
    var t = e.target; if(!t || !t.closest || inUi(t)) return;
    if(cur && cur.el.contains(t)){ e.stopPropagation(); return; }
    if(dragJustEnded){ dragJustEnded = false; e.stopPropagation(); e.preventDefault(); return; }
    if(LINK){
      var ln = t.closest('#canvas .node');
      if(ln){ e.stopPropagation(); e.preventDefault(); var lid = ln.id.replace(/^node-/, ''); if(srcNode(lid)) relink(LINK.id, lid); return; }
      if(t.closest('#canvas')){ e.stopPropagation(); e.preventDefault(); return; }
    }
    if(LN && LPICK){
      var lpn = t.closest('#canvas .node'); e.stopPropagation(); e.preventDefault();
      if(lpn){ var lpid = lpn.id.replace(/^node-/, ''); if(srcNode(lpid)) linePicked(lpid); } return;
    }
    var lt = LN && structOK() && t.closest('.lanes-tag');
    if(lt){ e.stopPropagation(); e.preventDefault(); if(cur) endField(true); laneMenu(lt.getAttribute('data-ln-tag')); return; }
    if(PICK){
      var pn = t.closest('#canvas .node');
      if(pn){ e.stopPropagation(); e.preventDefault(); var pid = pn.id.replace(/^node-/, ''); if(srcNode(pid)){ toggleFlag(pid, PICK); paintPick(); } return; }
      if(t.closest('#canvas')){ e.stopPropagation(); e.preventDefault(); return; }
    }
    // a card's number: type the one it should have
    var ordEl = structOK() && OUT && t.closest('#canvas .node-card .node-order');
    if(ordEl){ var on = ordEl.closest('.node'), oid = on && on.id.slice(5);
      if(oid && srcNode(oid) && ((OUT.parent || {})[oid])){ e.stopPropagation(); e.preventDefault(); if(cur) endField(true);
        askName(ordEl, 'Type its new number', numOf(oid), function(v){ renumber(oid, v); }); return; } }
    // a card's chips on the timeline: clicking one opens the card's chips to change
    var chipEl = structOK() && t.closest('#canvas .node-card .csym-btn,#canvas .node-card .esym-btn,#canvas .node-card .tsym-btn');
    if(chipEl){ var cn = chipEl.closest('.node'); if(cn && srcNode(cn.id.slice(5))){ e.stopPropagation(); e.preventDefault(); if(cur) endField(true); chipPop(cn.id.slice(5), chipEl); return; } }
    var stb = t.closest('.aed-st');
    if(stb){ e.stopPropagation(); e.preventDefault(); if(cur) endField(true); openStudyEditor(stb.getAttribute('data-sk')); return; }
    var sb = t.closest('.aed-sc button,.aed-tc button,.aed-cc button,.aed-add,.aed-uc,.aed-flags button,.aed-chips button,.aed-nadd,.aed-nx');
    if(sb){ e.stopPropagation(); e.preventDefault(); if(cur) endField(true); structure(sb); return; }
    var ck = canvasKey(t) || unitKey(t) || titleKey(t);
    if(ck){ e.stopPropagation(); e.preventDefault(); startField(ck.el, ck.k); return; }
    var f = t.closest('[data-aed]');
    if(f){ e.stopPropagation(); e.preventDefault(); startField(f, f.getAttribute('data-aed')); return; }
    var body = t.closest('.aed-bodypart');
    if(body){ var box = body.closest('[data-aed-body]'); if(box){ e.stopPropagation(); e.preventDefault(); startField(body, box.getAttribute('data-aed-body')); return; } }
    if(t.closest('#canvas .node-card') || t.closest('.adt-card')){ e.stopPropagation(); e.preventDefault(); }
    if(cur) endField(true);
  }, true);
  // Leaving a field by clicking anywhere else saves it.
  document.addEventListener('focusout', function(e){
    if(!cur || e.target !== cur.el) return;
    setTimeout(function(){ if(!cur) return; var a = document.activeElement;
      if(a && (cur.el.contains(a) || a.closest('#aed-bar,#aed-link'))) return; endField(true); }, 120);
  });
  // A page left (or the timeline shown) ends the field first, saving it.
  var sd0 = null;
  function guardNav(){
    if(sd0 || typeof window.showDetail !== 'function') return; sd0 = 1;
    ['showDetail', 'showTimeline'].forEach(function(name){
      var f = window[name]; if(typeof f !== 'function') return;
      window[name] = function(){
        // a link to a card taken out here (the build turns those into words)
        if(name === 'showDetail' && arguments[0] === 'node' && cardGone(arguments[1])){ toast('That card was removed.'); return; }
        if(cur) endField(true); hideBar(); var r = f.apply(this, arguments);
        if(name === 'showTimeline' && relayLater) setTimeout(relayout, 0);
        return r; };
    });
  }

  // Drag a card of an outline (desktop). Held close to its own line (the one
  // from its parent: down a spine, or across to a card beside its parent) it
  // slides along it alone, the cards under it staying put; taken off the line
  // it moves with all of them. A card with nothing under it moves freely.
  var drag = null, dragJustEnded = false, LINE_OFF = 44, LINE_ON = 26;
  function subtree(id){ var K = (window._ALTO_OUTLINE || {}).kids || {}, out = [id];
    for(var i = 0; i < out.length; i++) (K[out[i]] || []).forEach(function(c){ out.push(c); }); return out; }
  // Screen px per world px, measured on the card itself: a 100px nudge and how
  // far it moved on screen. Engines disagree on how CSS zoom reaches
  // getBoundingClientRect and pointer events; this asks the one in use.
  function scale(el){
    try{
      var a = el.getBoundingClientRect().left; el.style.translate = '100px 0';
      var b = el.getBoundingClientRect().left; el.style.translate = '';
      var k = (b - a) / 100; return k > 0.05 && k < 20 ? k : 1;
    }catch(e){ return 1; }
  }
  // the way its line runs: across for a card beside its parent, else down
  function lineOf(id){
    var G = window._altoTreeGeo, p = ((OUT && OUT.parent) || {})[id];
    if(G && p && G.y[p] != null && G.y[id] != null && Math.abs(G.y[p] - G.y[id]) < 1) return {ax: 'x', p: p};
    return {ax: 'y', p: p || null};
  }
  window.addEventListener('pointerdown', function(e){
    if(!editing() || !root.classList.contains('alto-drag-ok') || e.button !== 0) return;
    var t = e.target; if(!t.closest || inUi(t) || (cur && cur.el.contains(t))) return;
    var nodeEl = t.closest('#canvas .node'); if(!nodeEl || t.closest('button,.aed-rz')) return;
    var id = nodeEl.id.replace(/^node-/, ''); if(PICK || LINK || isNew(id) || !srcNode(id) || !field('p|' + id + '|shift')) return;
    var L = lineOf(id), sub = subtree(id);
    drag = {id:id, x0:e.clientX, y0:e.clientY, k:scale(nodeEl), on:false, ax:L.ax, p:L.p, mode:'tree', n:sub.length - 1,
      self:nodeEl, els: sub.map(function(i){ return document.getElementById('node-' + i); }).filter(Boolean)};
  }, true);
  function dragTip(d, e){
    var b = document.getElementById('aed-rztip'); if(!b){ b = document.createElement('div'); b.id = 'aed-rztip'; document.body.appendChild(b); }
    b.textContent = !d.n ? 'Drop it anywhere — the cards it lands on make room'
      : d.mode === 'line' ? 'Sliding along its line — the ' + (d.n === 1 ? 'card' : d.n + ' cards') + ' under it stay'
      : 'Moving with the ' + (d.n === 1 ? 'card' : d.n + ' cards') + ' under it — back on its line to slide it alone';
    b.style.left = (e.clientX + 16) + 'px'; b.style.top = (e.clientY + 16) + 'px'; b.classList.add('show');
  }
  window.addEventListener('pointermove', function(e){
    if(!drag) return;
    var dx = e.clientX - drag.x0, dy = e.clientY - drag.y0;
    if(!drag.on){ if(Math.abs(dx) + Math.abs(dy) < 6) return; drag.on = true; if(cur) endField(true);
      root.classList.add('alto-dragging'); }
    e.preventDefault();
    // off its line by more than a little: everything under it comes along
    var off = drag.ax === 'y' ? Math.abs(dx) : Math.abs(dy);
    var mode = !drag.n ? 'tree' : drag.mode === 'line' ? (off > LINE_OFF ? 'tree' : 'line') : (off < LINE_ON ? 'line' : 'tree');
    if(!drag.n || mode !== drag.mode || !drag.painted){ drag.mode = mode; drag.painted = true;
      drag.els.forEach(function(el){ el.classList.toggle('aed-moving', mode === 'tree' || el === drag.self); }); }
    drag.wx = dx / drag.k; drag.wy = dy / drag.k;
    if(drag.mode === 'line'){ if(drag.ax === 'y') drag.wx = 0; else drag.wy = 0; clampLine(drag); }
    dragTip(drag, e);
    if(!drag.raf) drag.raf = requestAnimationFrame(function(){ if(drag){ drag.raf = 0; preview(drag); } });
  }, true);
  // Along its line it stays on its side of its parent: below it on a spine,
  // clear of it when it sits beside it.
  function clampLine(d){
    var G = window._altoTreeGeo; if(!G || !d.p || G.y[d.p] == null || G.y[d.id] == null) return;
    var gap = (plan() || {}).row_gap || 40;
    if(d.ax === 'y'){
      if(G.y[d.p] >= G.y[d.id]) return;
      var lo = G.y[d.p] + G.h[d.p] / 2 + gap - (G.y[d.id] - G.h[d.id] / 2);
      if(d.wy < lo) d.wy = lo;
    } else {
      var side = G.x[d.id] > G.x[d.p] ? 1 : -1, room = (wOf(d.id) + wOf(d.p)) / 2 + 24;
      var nx = G.x[d.id] + d.wx; if(side * (nx - G.x[d.p]) < room) d.wx = G.x[d.p] + side * room - G.x[d.id];
    }
  }
  // the drag as hints: [shift, slide] with this card's own changed by (wx, wy)
  function hintsWith(d, wx, wy){
    var T = plan() || {}, sh = Object.assign({}, T.shift || {}), sl = Object.assign({}, T.slide || {});
    var M = d.mode === 'line' ? sl : sh, o = M[d.id] || [0, 0];
    M[d.id] = [o[0] + wx, o[1] + wy];
    return [sh, sl];
  }
  // The whole tree as it would be with the card dropped here: the cards in its
  // way step aside, and go back once it has moved on.
  function preview(d){
    var G = window._altoTreeGeo, T = plan(), R = null;
    if(G && T){ var H = hintsWith(d, d.wx, d.wy); try{ R = layoutAll(G.h, H[0], H[1]); }catch(e){ R = null; } }
    if(!R){ (d.mode === 'line' ? [d.self] : d.els).forEach(function(el){ el.style.translate = Math.round(d.wx) + 'px ' + Math.round(d.wy) + 'px'; }); return; }
    document.querySelectorAll('#world .node').forEach(function(el){
      var i = el.id.slice(5); if(G.y[i] == null || R.y[i] == null) return;
      var tx = Math.round(R.x[i] - G.x[i]), ty = Math.round(R.y[i] - G.y[i]);
      if(!el.classList.contains('aed-moving') && (tx || ty || el.style.translate)) el.classList.add('aed-room');
      el.style.translate = (tx || ty) ? tx + 'px ' + ty + 'px' : '';
    });
  }
  function clearPreview(){
    document.querySelectorAll('#world .node').forEach(function(el){ el.classList.remove('aed-room', 'aed-moving'); el.style.translate = ''; });
    var b = document.getElementById('aed-rztip'); if(b) b.classList.remove('show');
  }
  function endDrag(){
    if(!drag) return; var d = drag; drag = null;
    if(d.raf) cancelAnimationFrame(d.raf);
    if(!d.on) return;
    dragJustEnded = true; setTimeout(function(){ dragJustEnded = false; }, 400);
    root.classList.remove('alto-dragging');
    var hk = d.mode === 'line' ? 'slide' : 'shift';
    var f = field('p|' + d.id + '|' + hk); if(!f){ clearPreview(); return; }
    var wx = d.wx || 0, wy = d.wy || 0;
    // keep the card on the page
    var n = liveNode(d.id), el = document.getElementById('node-' + d.id), card = el && el.querySelector('.node-card');
    if(n && card){ var cx = (n.displayX != null ? n.displayX : 850) + wx, hw = card.offsetWidth / 2;
      var lo = hw + 30, hi = 1700 - hw - 30; if(cx < lo) wx += lo - cx; if(cx > hi) wx -= cx - hi; }
    // and in its unit: nothing above the unit's first card
    var G = window._altoTreeGeo;
    if(G){ try{
      var a = NODE_ACT[d.id], H = hintsWith(d, wx, wy), R1 = layoutAll(G.h, H[0], H[1]), R0 = layoutAll(G.h, {}, {});
      var top = function(R){ return Math.min.apply(null, Object.keys(R.y).filter(function(i){ return NODE_ACT[i] === a && G.h[i] != null; })
        .map(function(i){ return R.y[i] - G.h[i] / 2; })); };
      if(R0 && R1){ var t0 = top(R0), t1 = top(R1); if(isFinite(t0) && isFinite(t1) && t1 < t0 - 0.5) wy += t0 - t1; }
    }catch(e){} }
    var old = f.get() || [0, 0], v = [Math.round(old[0] + wx), Math.round(old[1] + wy)];
    // laid out at once where it was dropped, so nothing jumps back first
    if(change('p|' + d.id + '|' + hk, (v[0] || v[1]) ? v : null)){ clearTimeout(relayT); document.querySelectorAll('#world .node').forEach(function(x){ x.classList.remove('aed-room'); }); relayout(); }
    clearPreview();
  }
  window.addEventListener('pointerup', endDrag, true);
  window.addEventListener('pointercancel', function(){ if(drag){ drag.wx = drag.wy = 0; } endDrag(); clearPreview(); }, true);

  // A timeline just started on the homepage opens ready to write in.
  function startHere(){
    var want = null; try{ want = sessionStorage.getItem('alto-edit-now'); }catch(e){}
    if(want !== TID) return;
    var tries = 0;
    (function go(){
      if(canEdit()){
        try{ sessionStorage.removeItem('alto-edit-now'); }catch(e){}
        enter();
        toast(structOK() ? 'Your new timeline — click any words to write them, ✎ Rename a unit, + Add a card, + Add a unit at the foot. Claude can build it out from your notes any time.'
                         : 'Your new timeline — tap any words to write them. Cards and units are added on a computer.');
        return;
      }
      if(++tries < 60) setTimeout(go, 250);
    })();
  }
  var booted = false;
  function boot(){ guardNav(); syncTiles(); decorate(); if(!booted){ booted = true; startHere(); } }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
  window.addEventListener('load', boot);
})();
</script>"""
