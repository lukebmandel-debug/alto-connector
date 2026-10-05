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
  dt|<tree key>|<step>|title  text  edge  a decision-tree step (subtree.py)
  p|<id>|shift                            a card dragged on an outline, [dx, dy]
  n|<id>|order  n|<id>|s|new-…|h t p      a page's own sections, new ones (p: their kind)
  dt|<owner>-new-…|tree                   a new section's decision tree
  nn|card-…   nd|<id>                     a card added here / a built card taken out
  fl|list   fn|<id>   fx|off              the owner's filters, a card's, the ones taken out
A section's `i` is its index among the object's OWN sections (the page also
carries ones the build adds); _ALTO_EDK maps the page's list to it. A link to a
file on the owner's computer is <a data-file="file-…">: the file itself (or,
in Chromium, its place on disk) stays in this browser's IndexedDB, and the
connector finds it by name to record its path (edits.find_file).

Desktop: everything. Phones: text on the page being read (no dragging, no
cards, filters or sections to add, no Claude half). Shares and copies opened from disk never offer it.
"""
from __future__ import annotations

import json


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
    data = json.dumps(edk, separators=(",", ":"), ensure_ascii=False)
    data = data.replace("</", "<\\/").replace("<!--", "<\\!--")
    return f'<script id="alto-edk">window._ALTO_EDK={data};</script>\n'


def manual_edit(b, nodes=()) -> str:
    return edit_keys(b, nodes) + MANUAL_CSS + "\n" + MANUAL_JS + "\n"


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
  /* the split Edit tile — also used at the foot of a page */
  .alto-edit-tile .et-head{display:flex;align-items:center;justify-content:center;gap:8px;}
  .alto-edit-tile .et-split{display:flex;align-items:stretch;width:100%;margin-top:4px;border-top:1px solid color-mix(in srgb,var(--muted) 40%,transparent);}
  .alto-edit-tile .et-half{flex:1;display:flex;flex-direction:column;align-items:center;gap:3px;padding:9px 8px 2px;border:0;background:none;
    color:inherit;font:inherit;font-size:12.5px;letter-spacing:.05em;cursor:pointer;border-radius:10px;-webkit-tap-highlight-color:transparent;}
  .alto-edit-tile .et-half small{font-size:10.5px;opacity:.72;letter-spacing:.02em;line-height:1.3;}
  .alto-edit-tile .et-half:hover,.alto-edit-tile .et-half:focus-visible{color:var(--text);background:color-mix(in srgb,var(--text) 5%,transparent);outline:none;}
  .alto-edit-tile .et-half.off{opacity:.45;cursor:default;}
  .alto-edit-tile .et-div{width:1px;margin:8px 0 2px;background:color-mix(in srgb,var(--muted) 40%,transparent);}
  .alto-edit-tile .et-hist{position:absolute;top:50%;transform:translateY(-50%);width:40px;height:40px;border-radius:50%;
    display:none;align-items:center;justify-content:center;border:1px solid var(--border);background:var(--surface);color:var(--text);
    cursor:pointer;font:inherit;font-size:18px;box-shadow:0 6px 16px var(--node-rest-shadow);}
  .alto-edit-tile .et-hist[disabled]{opacity:.35;cursor:default;}
  .alto-edit-tile .et-undo{left:-54px;} .alto-edit-tile .et-redo{right:-54px;}
  html.alto-editing .alto-edit-tile .et-hist{display:flex;}
  html.alto-editing .alto-edit-tile .et-manual{color:var(--text);}
  .alto-edit-tile.in-page{position:relative;left:auto;transform:none;margin:56px auto 24px;width:340px;max-width:calc(100% - 120px);}
  .alto-edit-tile.in-page:hover,.alto-edit-tile.in-page:focus-visible{transform:scale(1.02) translateY(-2px);}
  html.mobile .alto-edit-tile.in-page{display:flex !important;max-width:calc(100% - 110px);width:auto;}
  html.printing .alto-edit-tile.in-page{display:none !important;}

  /* the exit pill, like Back to Overview */
  #alto-edit-exit{position:fixed;left:50%;transform:translateX(-50%);top:140px;z-index:330;display:none;align-items:center;gap:10px;
    height:34px;padding:0 6px 0 16px;border-radius:6px;background:#7a4b00;color:#fff;font:13px Georgia,serif;letter-spacing:.05em;
    box-shadow:0 4px 16px rgba(0,0,0,.22);white-space:nowrap;}
  html.dark #alto-edit-exit{background:#5a3a08;box-shadow:0 4px 16px rgba(0,0,0,.55);}
  html.alto-editing #alto-edit-exit{display:flex;}
  #alto-edit-exit .ee-st{font-size:11px;opacity:.8;}
  #alto-edit-exit button{height:26px;border:0;border-radius:4px;padding:0 12px;background:rgba(255,255,255,.18);color:#fff;font:inherit;cursor:pointer;}
  #alto-edit-exit button:hover{background:rgba(255,255,255,.28);}
  #alto-edit-exit .ee-h{display:none;min-width:32px;padding:0 6px;line-height:0;}
  #alto-edit-exit .ee-h svg, .alto-edit-tile .et-hist svg{display:block;margin:auto;}
  #alto-edit-exit .ee-h[disabled]{opacity:.4;}
  /* phones: under the header, like Back to Overview; undo / redo ride in the pill
     (beside the tile they would sit under the side buttons) */
  html.mobile #alto-edit-exit{border-radius:20px;height:40px;font-size:14px;padding:0 5px 0 14px;gap:6px;}
  html.mobile #alto-edit-exit .ee-st{display:none;}
  html.mobile #alto-edit-exit .ee-h{display:inline-block;}
  html.mobile .alto-edit-tile .et-hist{display:none !important;}
  html.printing #alto-edit-exit{display:none !important;}

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
  html.alto-editing.alto-drag-ok:not(.mobile) #canvas .node-card{cursor:grab;}
  html.alto-dragging, html.alto-dragging *{cursor:grabbing !important;-webkit-user-select:none !important;user-select:none !important;}
  .node.aed-moving{z-index:60 !important;}
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
  html.aed-picking #canvas .node.aed-pick-out .node-card{opacity:.38;}
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
  #aed-name,#aed-kinds{position:fixed;z-index:8350;display:none;width:300px;max-width:calc(100vw - 24px);padding:12px;border-radius:12px;background:var(--surface);
    border:1px solid var(--border);box-shadow:0 12px 34px var(--card-shadow);font:13px/1.4 system-ui,-apple-system,sans-serif;color:var(--text);}
  #aed-name.show,#aed-kinds.show{display:block;}
  #aed-name h5,#aed-kinds h5{margin:0 0 8px;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);}
  #aed-name input{width:100%;box-sizing:border-box;padding:8px 10px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font:inherit;}
  #aed-name .al-go{display:flex;gap:6px;margin-top:8px;}
  #aed-name .al-go button{flex:1;height:30px;border-radius:8px;border:1px solid var(--border);background:none;color:var(--text);font:inherit;cursor:pointer;}
  #aed-name .al-go .ab-ok{background:var(--accent,#a78bfa);border-color:transparent;color:#fff;}
  #aed-kinds button{display:block;width:100%;text-align:left;padding:8px 10px;border:0;border-radius:8px;background:none;color:var(--text);font:inherit;cursor:pointer;}
  #aed-kinds button:hover{background:color-mix(in srgb,var(--accent,#a78bfa) 14%,transparent);}
  #aed-kinds button b{display:block;font-weight:600;}
  #aed-kinds button small{display:block;color:var(--muted);font-size:11.5px;}
  #aed-toast{position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:8400;display:none;padding:10px 16px;border-radius:12px;
    background:var(--surface);color:var(--text);border:1px solid var(--border);box-shadow:0 10px 30px var(--node-rest-shadow);font-size:13px;max-width:90vw;}
  #aed-toast.show{display:block;}
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
  var PROV = '<span class="sec-prov">', SLOT = /<span class="adt-slot"[\s\S]*$/;
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
  function setSlot(s, key, on){
    var t = String(s.t || ''), mk = MARK.exec(t), m = mk ? mk[0] : '';
    var body = t.replace(MARK, '').replace(SLOT, '');
    s.t = body + (on ? '<span class="adt-slot" data-adt="' + key + '" hidden></span>' : '') + m;
  }
  // a heading's kind tag, left off where the heading already says it (detail_extras.prov_heading)
  function provTail(v, h){ var L = PROVL[v]; if(!L || txt(h).trim().toLowerCase() === L.toLowerCase()) return ''; return PROV + esc(L) + '</span>'; }

  /* cards added and removed here, laid over the page's own (an outline's
     tree, or a unit's run of cards) */
  var OUT = window._ALTO_OUTLINE || null;
  var CARDS0 = null, NEWC = {}, NEWO = [], GONE = {};
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
        order: (typeof NODE_ORDER_MAP !== 'undefined') ? Object.assign({}, NODE_ORDER_MAP) : null};
    }catch(e){ CARDS0 = null; }
    return CARDS0;
  }
  function isNew(id){ return !!(NEWC[id] && !NEWC[id].off); }
  function cardGone(id){ return !!GONE[id] || !!(NEWC[id] && NEWC[id].off); }
  function kidsOf(id){ return ((OUT && OUT.kids) || {})[id] || []; }
  function descendantsOf(id){ var out = [], q = kidsOf(id).slice(); while(q.length){ var c = q.shift(); out.push(c); q = q.concat(kidsOf(c)); } return out; }
  function romanOf(n){ var r = '', V = [[1000,'M'],[900,'CM'],[500,'D'],[400,'CD'],[100,'C'],[90,'XC'],[50,'L'],[40,'XL'],[10,'X'],[9,'IX'],[5,'V'],[4,'IV'],[1,'I']];
    V.forEach(function(p){ while(n >= p[0]){ r += p[1]; n -= p[0]; } }); return r; }
  // blocks.py _mark: I. / A. / 1. / a. / i.
  function outMark(level, i){ return level === 0 ? romanOf(i + 1) + '.' : level === 1 ? String.fromCharCode(65 + i % 26) + '.'
    : level === 2 ? (i + 1) + '.' : level === 3 ? String.fromCharCode(97 + i % 26) + '.' : romanOf(i + 1).toLowerCase() + '.'; }
  function fill(obj, from){ Object.keys(obj).forEach(function(k){ delete obj[k]; }); Object.keys(from).forEach(function(k){ obj[k] = from[k]; }); }
  // A plan (layout.outline_plan) without the cards taken out.
  function prune(op){
    var k = op[0];
    if(k === 'card') return cardGone(op[1]) ? null : op;
    if(k === 'row'){ var ids = op[1].filter(function(i){ return !cardGone(i); }); return ids.length ? [k, ids].concat(op.slice(2)) : null; }
    if(k === 'seq') return [k, op[1].map(prune).filter(Boolean)];
    if(k === 'par') return [k, op[1].map(prune).filter(Boolean)].concat(op.slice(2));
    if(k === 'band'){
      var cards = op[1].filter(function(cd){ return !cardGone(cd[0]); }).map(function(cd){ return cd.length > 5 && cardGone(cd[5]) ? cd.slice(0, 5) : cd; });
      if(!cards.length) return null;
      var blocks = op[2].map(function(b){ var o = prune(b[2]); return o ? [b[0], b[1], o] : null; }).filter(Boolean);
      return [k, cards, blocks].concat(op.slice(3));
    }
    var inner = prune(op[1]); return inner ? [k, inner].concat(op.slice(2)) : null;     // float
  }
  // Every table the page keeps of its cards, from the cards as built plus
  // the ones added and less the ones removed here.
  function syncCards(){
    var B = cardsBase(); if(!B) return;
    var src = B.src.filter(function(n){ return !cardGone(n.id); });
    var seqs = B.seqs.map(function(a){ return a.filter(function(id){ return !cardGone(id); }); });
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
      var sp = c.spec, a = act[sp.p] != null ? act[sp.p] : sp.a, seq = seqs[a];
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
    var liveBy = {}; B.live.forEach(function(n){ liveBy[n.id] = n; });
    NODES_SRC.splice.apply(NODES_SRC, [0, NODES_SRC.length].concat(src));
    NODES.splice.apply(NODES, [0, NODES.length].concat(src.map(function(n){ return liveBy[n.id] || NEWC[n.id].live; })));
    ACT_SEQS.forEach(function(a, i){ a.splice.apply(a, [0, a.length].concat(seqs[i] || [])); });
    fill(NODE_ACT, act);
    if(B.conns) CONNECTIONS.splice.apply(CONNECTIONS, [0, CONNECTIONS.length].concat(
      spines.concat(B.conns.filter(function(c){ return !cardGone(c[0]) && !cardGone(c[1]); }))));
    var changed = NEWO.some(isNew) || Object.keys(GONE).length > 0;
    if(OUT){
      fill(OUT.kids, kids); fill(OUT.parent, par);
      if(!changed){ fill(OUT.num, B.num); fill(OUT.label, B.label); }
      else {
        var num = {}, lab = {};
        (function(){ var r = 0; seqs.forEach(function(ids){ ids.forEach(function(id){ if(par[id]) return;
          (function walk(x, level, i, pre){ var m = outMark(level, i); lab[x] = m; num[x] = pre + m;
            (kids[x] || []).forEach(function(k, j){ walk(k, level + 1, j, num[x]); }); })(id, 0, r++, ''); }); }); })();
        fill(OUT.num, num); fill(OUT.label, lab);
      }
    }
    if(B.order){ if(!changed) fill(NODE_ORDER_MAP, B.order);
      else { var om = {}; seqs.forEach(function(ids, a){ ids.forEach(function(id, j){ om[id] = (a + 1) + '.' + (j + 1); }); }); fill(NODE_ORDER_MAP, om); } }
    var T = plan(); if(T && B.plan) T.acts = changed ? B.plan.map(function(ops){ return ops.map(prune).filter(Boolean); }) : JSON.parse(JSON.stringify(B.plan));
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
  // A new card of an outline drawn as a tree, after the tree is laid out: under
  // its parent's last descendant (or at the foot of its unit), and everything
  // that starts below that point moves down to make room — so it covers
  // nothing until Claude's next build places it properly.
  function placeNew(pos, h){
    var G = window._altoTreeGeo, T = plan(); if(!G || !T) return;
    var ids = NEWO.filter(function(id){ return isNew(id) && pos[id] != null; }); if(!ids.length) return;
    var gap = T.row_gap || 40, W = {}, placed = {};
    function w(id){ if(W[id] == null){ var el = document.getElementById('node-' + id), c = el && el.querySelector('.node-card'); W[id] = c && c.offsetWidth ? c.offsetWidth : 240; } return W[id]; }
    ids.forEach(function(id){
      var sp = NEWC[id].spec, hc = h[id] || 120, x, cand;
      var all = Object.keys(pos).filter(function(q){ return q !== id && (!isNew(q) || placed[q]) && G.x[q] != null && h[q] != null; });
      if(sp.p && pos[sp.p] != null){
        var kin = descendantsOf(sp.p).filter(function(q){ return all.indexOf(q) >= 0; });
        var sib = kidsOf(sp.p).filter(function(q){ return all.indexOf(q) >= 0; });
        x = sib.length ? G.x[sib[sib.length - 1]] : G.x[sp.p];
        cand = Math.max.apply(null, kin.concat([sp.p]).map(function(q){ return pos[q] + h[q] / 2; })) + gap;
      } else {
        var mine = all.filter(function(q){ return NODE_ACT[q] === NODE_ACT[id]; });
        x = T.cx || 850;
        cand = mine.length ? Math.max.apply(null, mine.map(function(q){ return pos[q] + h[q] / 2; })) + gap : (T.top || 200);
      }
      for(var guard = 0, moved = true; moved && guard < 400; guard++){
        moved = false;
        all.forEach(function(q){ var top = pos[q] - h[q] / 2, bot = pos[q] + h[q] / 2;
          if(top < cand && bot > cand - gap + 1 && Math.abs(G.x[q] - x) < (w(q) + w(id)) / 2 + 16){ cand = bot + gap; moved = true; } });
      }
      var D = hc + gap;
      all.forEach(function(q){ if(pos[q] - h[q] / 2 >= cand - 0.5){ pos[q] += D; if(G.y[q] != null) G.y[q] = pos[q]; } });
      pos[id] = cand + hc / 2; G.y[id] = pos[id]; G.x[id] = x; G.h[id] = hc;
      var n = liveNode(id); if(n) n.displayX = x;
      var el = document.getElementById('node-' + id); if(el) el.style.left = x + 'px';
      placed[id] = 1;
    });
  }
  if(typeof window._altoTree === 'function'){
    var tree0 = window._altoTree;
    var withNew = function(pos, h){ var r = tree0.apply(this, arguments); if(r && NEWO.length){ try{ placeNew(pos, h); }catch(e){} } return r; };
    window._altoTree = withNew;
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
    var chips = FULL.sections.filter(function(s){ return s.kind === 'chips' && s.key !== 'flags'; });
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
      else if(FULL.nodes[s.key]) nodes[s.key] = FULL.nodes[s.key];
    });
    return {sections: out, nodes: nodes};
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

  // {get(), set(v), kind:'plain'|'html'|'shift'} for a key, or null when the page has no such field.
  function field(k){
    var p = k.split('|'), kind = p[0], id = p[1];
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
    if(kind === 'p' && p[2] === 'shift'){
      var T = plan(); if(!T || !srcNode(id)) return null;
      return {kind:'shift', get:function(){ return (T.shift && T.shift[id]) ? T.shift[id].slice() : null; },
        set:function(v){ T.shift = T.shift || {}; if(v && (v[0] || v[1])) T.shift[id] = v.slice(); else delete T.shift[id]; }};
    }
    return null;
  }

  /* ── lay the stored edits over the page ───────────────────────────────── */
  // Signatures of what the page was built with, taken before any edit lies over it.
  var PRIS = {};
  ['n', 'c', 'env', 'theme'].forEach(function(kind){ Object.keys(EDK[kind] || {}).forEach(function(id){ PRIS[kind + '|' + id] = jh(JSON.stringify(ownPairs(kind, id))); }); });
  Object.keys(window._ALTO_DT || {}).forEach(function(k){ PRIS['dt|' + k] = jh(JSON.stringify(window._ALTO_DT[k].n)); });
  var conflicts = {}, APPLIED = {};      // APPLIED: what this page last set each field to
  function sigOf(f){ return f.sig ? f.sig() : f.get(); }
  // structure first (a section list, a tree), then new sections' words, then the rest, oldest first
  // cards, then the filters' list, then structure (a section list, a tree; a
  // new section's tree after its section), new sections' words, the rest
  function pri(k){ var p = k.split('|');
    if(p[0] === 'nn' || p[0] === 'nd') return -2;
    if(p[0] === 'fl') return -1;
    if(p[0] === 'dt' && p[2] === 'tree') return NEWT.test(p[1]) ? 0.5 : 0;
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
  function relayout(){
    if(root.classList.contains('mobile') || typeof initLayout !== 'function') return;
    try{ initLayout(); if(window._applyActiveFilters) window._applyActiveFilters(); }catch(e){}
    try{ if(window._altoFilterRefresh && window._altoChipOn && window._altoChipOn()) window._altoFilterRefresh(); }catch(e){}
    decorateCanvas(); paintPick();
  }
  if(overlay()){
    requestAnimationFrame(function(){ requestAnimationFrame(function(){ requestAnimationFrame(relayout); }); });
    if(FTOUCH) drawFiltersSoon();
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
    document.querySelectorAll('.alto-edit-tile .et-undo, #alto-edit-exit .ee-undo').forEach(function(b){ b.disabled = HP <= 0; });
    document.querySelectorAll('.alto-edit-tile .et-redo, #alto-edit-exit .ee-redo').forEach(function(b){ b.disabled = HP >= HIST.length; });
  }

  /* ── showing a change: the page in front of the reader, in place ──────── */
  var relayT = null;
  function relayoutSoon(){ clearTimeout(relayT); relayT = setTimeout(relayout, 30); }
  function page(){ var dp = document.getElementById('detail-page'); if(!dp || !dp.classList.contains('visible')) return null;
    var P = window._altoPageNow || {type: window._currentDetailType, id: window._currentDetailId}; return P && P.id ? P : null; }
  var TYPE = {n:'node', c:'char', env:'env', theme:'theme'};
  function refresh(k){
    var p = k.split('|'), kind = p[0], P = page(), dc = document.getElementById('detail-content');
    if(kind === 'nn' || kind === 'nd'){
      relayoutSoon(); if(FLAGS.length || FTOUCH) drawFiltersSoon();
      if(P && P.type === 'node' && !srcNode(P.id)){ try{ window.showTimeline(); }catch(e){} }
      else if(P) { rerenderPage(P); repaint(); }
      return;
    }
    if(kind === 'fl' || kind === 'fn' || kind === 'fx'){
      if(P && P.type === 'node' && editing()) decorateFlags(true);
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
          else { var box = h3.parentNode; Array.prototype.slice.call(box.childNodes).forEach(function(c){ if(c !== h3 && !(c.classList && c.classList.contains('alto-edit-tile'))) box.removeChild(c); });
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
  }
  function exit(){
    if(!editing()) return;
    endField(true);
    root.classList.remove('alto-editing', 'alto-drag-ok');
    endPick(true); hideMenus();
    document.querySelectorAll('.aed-sc,.aed-tc,.aed-cc,.aed-uc,.aed-add,.aed-ph,.aed-flags,.aed-fx,.aed-fadd').forEach(function(el){ if(el.parentNode) el.parentNode.removeChild(el); });
    document.querySelectorAll('.aed-f').forEach(function(el){ el.classList.remove('aed-f'); });
    hideBar();
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
  function markSections(){
    if(marked) return; marked = true;
    ['n', 'c', 'env', 'theme'].forEach(function(kind){
      Object.keys(EDK[kind] || {}).forEach(function(id){
        var L = secList(kind, id), m = EDK[kind][id]; if(!L) return;
        var j = 0;
        L.forEach(function(s, i){ var src = m[i]; if(src == null || !own(src) || !s || MARK.test(s.t || '')) return;
          s.t = (s.t || '') + '<span class="aed-k" data-k="' + kind + '|' + id + '|s|' + src + '"></span>'; });
      });
    });
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
  function placePill(){
    var b = document.getElementById('alto-edit-exit'); if(!b) return;
    if(root.classList.contains('mobile')){
      var low = 0;
      ['title-bar', 'nav', 'node-nav-bar', 'mobile-filter-bar', 'back-to-overview-bar'].forEach(function(id){
        var el = document.getElementById(id); if(!el || !el.offsetHeight) return;
        var r = el.getBoundingClientRect(); if(r.top < 260 && r.bottom > low && r.bottom < 300) low = r.bottom; });
      b.style.top = Math.round((low || 100) + 10) + 'px'; return;
    }
    var row = document.getElementById('desktop-banner-row'), top = root.classList.contains('detail-open') ? 175 : 140;
    if(row && row.classList.contains('active') && row.offsetHeight) top = row.getBoundingClientRect().bottom + 8;
    b.style.top = Math.round(top) + 'px';
  }
  setInterval(function(){ if(editing()) placePill(); }, 400);

  /* ── the tiles ────────────────────────────────────────────────────────── */
  function tileHTML(phone){
    return '<button type="button" class="et-hist et-undo" title="Undo (⌘Z)" aria-label="Undo"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/></svg></button>'
      + '<span class="et-head"><span class="et-glyph">✎</span><span class="et-label">Edit timeline</span></span>'
      + '<span class="et-split">'
      + (phone ? '' : '<button type="button" class="et-half et-claude">Edit in Claude<small>Add notes, link sources or change anything</small></button><span class="et-div"></span>')
      + '<button type="button" class="et-half et-manual">Edit manually<small>' + (phone ? 'Change the words on this page' : 'Words, links, sections, moving cards') + '</small></button>'
      + '</span>'
      + '<button type="button" class="et-hist et-redo" title="Redo (⇧⌘Z)" aria-label="Redo"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m15 14 5-5-5-5"/><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/></svg></button>';
  }
  window._altoEditTileHTML = tileHTML;
  function wire(tile){
    if(tile._aed) return; tile._aed = 1;
    tile.addEventListener('click', function(e){
      var t = e.target.closest('button'); if(!t) return;
      e.stopPropagation();
      if(t.classList.contains('et-claude')){ if(window._altoEditTimeline) window._altoEditTimeline(); }
      else if(t.classList.contains('et-manual')){ if(editing()) exit(); else enter(); }
      else if(t.classList.contains('et-undo')) undo();
      else if(t.classList.contains('et-redo')) redo();
    });
  }
  function syncTiles(){
    var ok = canEdit();
    // The timeline's tile is drawn (detail_extras.EDIT_TILE) before this script
    // runs: give it both halves now. Its own click handler runs them.
    document.querySelectorAll('.alto-edit-tile:not(.in-page)').forEach(function(t){
      if(!t.querySelector('.et-manual')) t.innerHTML = tileHTML(false); });
    document.querySelectorAll('.alto-edit-tile').forEach(function(t){
      wire(t);
      var m = t.querySelector('.et-manual'); if(!m) return;
      m.classList.toggle('off', !ok); m.title = ok ? '' : whyNot();
      var sm = m.querySelector('small'); if(sm && editing()) sm.textContent = 'Click to stop editing';
    });
    syncHist();
  }
  window._altoWireEditTile = function(t){ wire(t); syncTiles(); };
  function pageTile(){
    var dc = document.getElementById('detail-content'); if(!dc || !page()) return;
    if(dc.querySelector(':scope > .alto-edit-tile')) return;
    if(!dc.querySelector('.detail-header')) return;
    var t = document.createElement('div'); t.className = 'alto-edit-tile in-page'; t.setAttribute('role', 'group');
    t.setAttribute('aria-label', 'Edit this timeline'); t.innerHTML = tileHTML(PHONE || root.classList.contains('mobile'));
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
        Array.prototype.forEach.call(h3.parentNode.children, function(c){ if(c !== h3 && !c.classList.contains('adt') && !c.classList.contains('alto-edit-tile')) c.classList.add('aed-f', 'aed-bodypart'); });
        if(structOK() && !h3.querySelector('.aed-sc')) h3.appendChild(ctl('aed-sc', [['up', '↑', 'Move this section up'], ['down', '↓', 'Move it down'], ['del', '✕', 'Remove this section']], {sk: k}));
      });
      if(kind && structOK() && !dc.querySelector('.aed-add') && field(kind + '|' + P.id + '|order')){
        var add = document.createElement('button'); add.type = 'button'; add.className = 'aed-add'; add.textContent = '+ Add a section';
        add.setAttribute('data-x', 'addsec'); add.setAttribute('data-ok', kind + '|' + P.id);
        var tile = dc.querySelector(':scope > .alto-edit-tile');
        if(lastOwn && lastOwn.nextSibling) dc.insertBefore(add, lastOwn.nextSibling);
        else if(tile) dc.insertBefore(add, tile); else dc.appendChild(add);
      }
      if(kind === 'n') decorateFlags(false);
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
      var b = document.createElement('button'); b.type = 'button'; b.className = 'aed-uc'; b.textContent = '+ Add a card';
      b.title = OUT ? 'Add a card to this unit, under its top card' : 'Add a card at the end of this unit';
      b.setAttribute('data-act', i);
      b.style.left = Math.round(l.offsetLeft + l.offsetWidth + 14) + 'px';
      b.style.top = Math.round(l.offsetTop + l.offsetHeight / 2 - 15) + 'px';
      world.appendChild(b);
    });
  }
  document.addEventListener('mouseover', function(e){
    if(!editing() || !structOK() || PICK || !cardsBase()) return;
    var nodeEl = e.target && e.target.closest && e.target.closest('#canvas .node'); if(!nodeEl) return;
    var card = nodeEl.querySelector('.node-card'), id = nodeEl.id.replace(/^node-/, '');
    if(!card || card.querySelector(':scope > .aed-cc') || !srcNode(id)) return;
    var items = [];
    if(OUT) items.push(['addc', '+', 'Add a card under this one']);
    if(canRemove(id)) items.push(['delc', '✕', 'Remove this card']);
    if(items.length) card.appendChild(ctl('aed-cc', items, {cid: id}));
  });
  function addCard(p, a){
    if(!cardsBase()) return;
    // an outline's unit has one card at its top (brief: one hub per unit): a
    // card added to the unit goes under it
    if(!p && OUT){ var hub = NODES_SRC.filter(function(n){ return NODE_ACT[n.id] === a && !(OUT.parent || {})[n.id]; })[0]; if(hub) p = hub.id; }
    var id = rid('card-'), par = p ? srcNode(p) : null, act = par ? NODE_ACT[p] : a;
    var inAct = NODES_SRC.filter(function(n){ return NODE_ACT[n.id] === act; }), like = par || inAct[inAct.length - 1] || null;
    var spec = {p: p || '', a: act, t: 'New ' + String(EDK.noun || 'card').toLowerCase(), g: like ? like.tag || '' : '', d: '', c: like ? like.color : 'var(--accent)'};
    if(!OUT) spec.col = like && like.col ? like.col : 'center';
    if(!change('nn|' + id, spec)) return;
    toast('Card added — Claude places it properly at the next build.');
    setTimeout(function(){ var el = document.querySelector('#node-' + id + ' .node-title');
      if(el){ try{ el.scrollIntoView({block:'center', inline:'nearest'}); }catch(_){} startField(el, 'n|' + id + '|title'); try{ document.execCommand('selectAll'); }catch(_){} } }, 140);
  }
  function removeCard(id){
    if(!canRemove(id)) { toast('Remove the cards under it first.'); return; }
    var ok = isNew(id) ? change('nn|' + id, null) : change('nd|' + id, 1);
    if(ok) toast('Card removed — ⌘Z brings it back.');
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
    document.querySelectorAll('.aed-pick-in,.aed-pick-out').forEach(function(el){ el.classList.remove('aed-pick-in', 'aed-pick-out'); });
    var b = document.getElementById('aed-pick'); if(b) b.classList.remove('show');
  }
  function paintPick(){
    if(!PICK) return;
    var f = FLAGS.filter(function(x){ return x.id === PICK; })[0]; if(!f){ endPick(); return; }
    var n = 0;
    document.querySelectorAll('#world .node').forEach(function(el){ var on = (FLN[el.id.slice(5)] || []).indexOf(PICK) >= 0; if(on) n++;
      el.classList.toggle('aed-pick-in', on); el.classList.toggle('aed-pick-out', !on); });
    var b = document.getElementById('aed-pick');
    if(!b){ b = document.createElement('div'); b.id = 'aed-pick';
      b.innerHTML = '<span class="ap-t"></span><span class="ap-n"></span><button type="button">Done</button>';
      b.querySelector('button').addEventListener('click', function(e){ e.stopPropagation(); endPick(); drawFilters(); if(window._altoFilterOpen) window._altoFilterOpen(true); });
      document.body.appendChild(b); }
    b.querySelector('.ap-t').textContent = 'Choosing the cards in “' + f.name + '” — click a card to put it in or take it out';
    b.querySelector('.ap-n').textContent = n + (n === 1 ? ' card' : ' cards');
    b.classList.add('show');
  }

  /* a small box asking for a name; a menu of kinds of section */
  function hideMenus(){ ['aed-name', 'aed-kinds'].forEach(function(id){ var b = document.getElementById(id); if(b) b.classList.remove('show'); }); }
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
    ['summary', 'Summary', 'A short summary'], ['tree', 'Decision tree', 'Questions and answers that branch, like a small timeline']];
  function chooseKind(at, ok){
    hideMenus();
    var b = document.getElementById('aed-kinds');
    if(!b){ b = document.createElement('div'); b.id = 'aed-kinds';
      b.innerHTML = '<h5>Add a section</h5>' + KINDS.map(function(k){ return '<button type="button" data-k="' + k[0] + '"><b>' + esc(k[1]) + '</b><small>' + esc(k[2]) + '</small></button>'; }).join('');
      b.addEventListener('mousedown', function(e){ e.stopPropagation(); });
      b.addEventListener('click', function(e){ e.stopPropagation(); var a = e.target.closest('button[data-k]'); if(!a) return; b.classList.remove('show'); addSection(b._ok, a.getAttribute('data-k')); });
      document.body.appendChild(b); }
    b._ok = ok; b.classList.add('show'); placeNear(b, at);
  }
  document.addEventListener('mousedown', function(e){ if(e.target.closest && !e.target.closest('#aed-name,#aed-kinds,.aed-add,.aed-fadd,.aed-fx')) hideMenus(); }, true);
  function addSection(ok, kind){
    var f = field(ok + '|order'); if(!f) return;
    var nk = rid('new-'), base = ok + '|s|' + nk, q = ok.split('|');
    var H = {text:'New section', list:'Key points', quoted:'Quote', notes:'Notes', summary:'Summary', tree:'Decision tree'}[kind] || 'New section';
    var T = kind === 'list' ? '<ul><li>First point</li><li>Second point</li></ul>' : kind === 'quoted' ? 'Paste the source’s words here.' : kind === 'tree' ? '' : 'Write here.';
    var L = [[ok + '|order', f.get().concat(nk)], [base + '|h', H]];
    if(T) L.push([base + '|t', T]);
    if(PROVL[kind]) L.push([base + '|p', kind]);
    if(kind === 'tree') L.push(['dt|' + DTPRE[q[0]] + '-' + q[1] + '-' + nk + '|tree', [{i: rid('s-'), t: 'First question'}]]);
    if(changes(L)){
      setTimeout(function(){ var mk = document.querySelector('#detail-content .aed-k[data-k="' + base + '"]'), sb = mk && mk.closest('.detail-section'), h3 = sb && sb.querySelector(':scope > h3');
        if(h3){ h3.scrollIntoView({block:'center'}); startField(h3, base + '|h'); try{ document.execCommand('selectAll'); }catch(_){} } }, 60);
    }
  }

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
    var id = nodeEl.id.replace(/^node-/, ''), f = t.closest('.node-title,.node-tag,.node-desc'); if(!f) return null;
    return {el: f, k: 'n|' + id + '|' + f.className.match(/node-(title|tag|desc)/)[1]};
  }
  function unitKey(t){
    var lb = t.closest('.phase-label-float'); if(!lb || !t.closest('#canvas')) return null;
    var all = Array.prototype.slice.call(document.querySelectorAll('#world .phase-label-float'));
    var bands = all.slice().sort(function(a, b){ return a.offsetTop - b.offsetTop; });
    var i = bands.indexOf(lb); return i >= 0 ? {el: lb, k: 'u|' + i + '|label'} : null;
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
    change(c.k, v2);
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
  function inUi(t){ return t.closest('#aed-bar,#aed-link,#alto-edit-exit,.alto-edit-tile,#aed-toast,#aed-pick,#aed-name,#aed-kinds,#ef-panel,#filter-toggle'); }
  // Move, add and remove: a page's sections, a tree's steps, an Overview's blocks.
  function structure(b){
    var x = b.getAttribute('data-x') || (b.classList.contains('aed-uc') ? 'addcu' : ''), w = b.closest('.aed-sc,.aed-tc,.aed-cc');
    if(x === 'addsec'){ chooseKind(b, b.getAttribute('data-ok')); return; }
    if(x === 'addcu'){ addCard(null, +b.getAttribute('data-act')); return; }
    if(w && w.hasAttribute('data-cid')){
      var cid = w.getAttribute('data-cid');
      if(x === 'addc') addCard(cid, null); else if(x === 'delc') removeCard(cid);
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
    var ck = canvasKey(t) || unitKey(t);
    var f = t.closest('[data-aed]'), body = t.closest('.aed-bodypart');
    if(ck || f || body || t.closest('#canvas .node-card') || t.closest('.adt-card') || t.closest('.aed-sc,.aed-tc,.aed-cc,.aed-add,.aed-uc,.aed-flags') || (PICK && t.closest('#canvas .node'))){
      e.stopPropagation(); if(e.type === 'click') e.preventDefault();
    }
  }
  ['mousedown', 'mouseup', 'dblclick'].forEach(function(ev){ window.addEventListener(ev, eatIfEditing, true); });
  window.addEventListener('click', function(e){
    if(!editing()) return;
    var t = e.target; if(!t || !t.closest || inUi(t)) return;
    if(cur && cur.el.contains(t)){ e.stopPropagation(); return; }
    if(dragJustEnded){ dragJustEnded = false; e.stopPropagation(); e.preventDefault(); return; }
    if(PICK){
      var pn = t.closest('#canvas .node');
      if(pn){ e.stopPropagation(); e.preventDefault(); var pid = pn.id.replace(/^node-/, ''); if(srcNode(pid)){ toggleFlag(pid, PICK); paintPick(); } return; }
      if(t.closest('#canvas')){ e.stopPropagation(); e.preventDefault(); return; }
    }
    var sb = t.closest('.aed-sc button,.aed-tc button,.aed-cc button,.aed-add,.aed-uc,.aed-flags button');
    if(sb){ e.stopPropagation(); e.preventDefault(); if(cur) endField(true); structure(sb); return; }
    var ck = canvasKey(t) || unitKey(t);
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
        if(cur) endField(true); hideBar(); return f.apply(this, arguments); };
    });
  }

  // Drag a card of an outline (desktop): it and its progeny move together.
  var drag = null, dragJustEnded = false;
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
  window.addEventListener('pointerdown', function(e){
    if(!editing() || !root.classList.contains('alto-drag-ok') || e.button !== 0) return;
    var t = e.target; if(!t.closest || inUi(t) || (cur && cur.el.contains(t))) return;
    var nodeEl = t.closest('#canvas .node'); if(!nodeEl || t.closest('button')) return;
    var id = nodeEl.id.replace(/^node-/, ''); if(PICK || isNew(id) || !srcNode(id) || !field('p|' + id + '|shift')) return;
    drag = {id:id, x0:e.clientX, y0:e.clientY, k:scale(nodeEl), on:false, els: subtree(id).map(function(i){ return document.getElementById('node-' + i); }).filter(Boolean)};
  }, true);
  window.addEventListener('pointermove', function(e){
    if(!drag) return;
    var dx = e.clientX - drag.x0, dy = e.clientY - drag.y0;
    if(!drag.on){ if(Math.abs(dx) + Math.abs(dy) < 6) return; drag.on = true; if(cur) endField(true);
      root.classList.add('alto-dragging'); drag.els.forEach(function(el){ el.classList.add('aed-moving'); }); }
    e.preventDefault();
    var wx = dx / drag.k, wy = dy / drag.k;
    drag.els.forEach(function(el){ el.style.translate = Math.round(wx) + 'px ' + Math.round(wy) + 'px'; });
    drag.wx = wx; drag.wy = wy;
  }, true);
  function endDrag(){
    if(!drag) return; var d = drag; drag = null;
    if(!d.on) return;
    dragJustEnded = true; setTimeout(function(){ dragJustEnded = false; }, 400);
    root.classList.remove('alto-dragging');
    d.els.forEach(function(el){ el.classList.remove('aed-moving'); el.style.translate = ''; });
    var f = field('p|' + d.id + '|shift'); if(!f) return;
    var old = f.get() || [0, 0], v = [Math.round(old[0] + (d.wx || 0)), Math.round(old[1] + (d.wy || 0))];
    // keep the card on the page
    var n = liveNode(d.id), el = document.getElementById('node-' + d.id), card = el && el.querySelector('.node-card');
    if(n && card){ var cx = (n.displayX != null ? n.displayX : 850) + (d.wx || 0), hw = card.offsetWidth / 2;
      var lo = hw + 30, hi = 1700 - hw - 30; if(cx < lo) v[0] += Math.round(lo - cx); if(cx > hi) v[0] -= Math.round(cx - hi); }
    change('p|' + d.id + '|shift', (v[0] || v[1]) ? v : null);
  }
  window.addEventListener('pointerup', endDrag, true);
  window.addEventListener('pointercancel', function(){ if(drag){ drag.wx = drag.wy = 0; } endDrag(); }, true);

  function boot(){ guardNav(); syncTiles(); decorate(); }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
  window.addEventListener('load', boot);
})();
</script>"""
