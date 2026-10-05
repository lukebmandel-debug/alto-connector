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
A section's `i` is its index among the object's OWN sections (the page also
carries ones the build adds); _ALTO_EDK maps the page's list to it.

Desktop: everything. Phones: text on the page being read (no dragging, no
Claude half). Shares and copies opened from disk never offer it.
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
    data = json.dumps(edk, separators=(",", ":"), ensure_ascii=False)
    data = data.replace("</", "<\\/").replace("<!--", "<\\!--")
    return f'<script id="alto-edk">window._ALTO_EDK={data};</script>\n'


def manual_edit(b, nodes=()) -> str:
    return edit_keys(b, nodes) + MANUAL_CSS + "\n" + MANUAL_JS + "\n"


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
        set:function(v){ var q = hParts(s.h); s.h = q.lead + esc(v) + q.tail; }};
      if(p[4] === 't') return {kind:'html', get:function(){ return tParts(s.t).text; },
        set:function(v){ s.t = v + tParts(s.t).tail; }};
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
  function pri(k){ var p = k.split('|'); return (p[2] === 'order' || (p[0] === 'dt' && p[2] === 'tree')) ? 0 : (p[2] === 's' && /^new-/.test(p[3] || '')) ? 1 : 2; }
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
  }
  if(overlay()) requestAnimationFrame(function(){ requestAnimationFrame(function(){ requestAnimationFrame(relayout); }); });

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
  }
  function exit(){
    if(!editing()) return;
    endField(true);
    root.classList.remove('alto-editing', 'alto-drag-ok');
    document.querySelectorAll('.aed-sc,.aed-tc,.aed-add,.aed-ph').forEach(function(el){ if(el.parentNode) el.parentNode.removeChild(el); });
    document.querySelectorAll('.aed-f').forEach(function(el){ el.classList.remove('aed-f'); });
    hideBar();
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
        if(tag === 'A' && n.classList.contains(LOCAL_CLS)){ dst.appendChild(n.cloneNode(false)); return; }
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
        if(tag === 'A'){
          var href = n.getAttribute('href') || '';
          if(/^(https?:\/\/|mailto:)/i.test(href)){ var a = document.createElement('a'); a.setAttribute('href', href); a.className = 'note-link'; a.target = '_blank'; a.rel = 'noopener';
            var ds = n.getAttribute('data-src'); if(ds && /^[a-z0-9][a-z0-9-]{0,63}$/.test(ds)) a.setAttribute('data-src', ds); walk(n, a); dst.appendChild(a); return; }
          if(href === '#' && n.getAttribute('data-src')){ var a2 = document.createElement('a'); a2.setAttribute('href', '#'); a2.className = 'note-link'; a2.setAttribute('data-src', n.getAttribute('data-src')); walk(n, a2); dst.appendChild(a2); return; }
          walk(n, dst); return;
        }
        if(tag === 'MARK' || tag === 'FONT' || !OK[tag]){ walk(n, dst); return; }
        if(tag === 'DIV') tag = 'BR_DIV';
        if(tag === 'BR_DIV'){ if(dst.lastChild) dst.appendChild(document.createElement('br')); walk(n, dst); return; }
        var e = document.createElement(tag.toLowerCase());
        if(tag === 'SPAN'){ walk(n, dst); return; }
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
      + '<div class="al-msg"></div><div class="al-go"><button type="button" data-a="cancel">Cancel</button><button type="button" data-a="url">Link website</button></div>';
    b.addEventListener('mousedown', function(e){ e.stopPropagation(); });
    b.addEventListener('click', function(e){
      e.stopPropagation();
      var row = e.target.closest('.al-row'); if(row){ makeLink({t: row.getAttribute('data-t'), id: row.getAttribute('data-id')}); return; }
      var a = e.target.closest('button') && e.target.closest('button').getAttribute('data-a');
      if(a === 'cancel') hideLink(true);
      if(a === 'url') linkUrl();
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
  function inUi(t){ return t.closest('#aed-bar,#aed-link,#alto-edit-exit,.alto-edit-tile,#aed-toast'); }
  // Move, add and remove: a page's sections, a tree's steps, an Overview's blocks.
  function structure(b){
    var x = b.getAttribute('data-x'), w = b.closest('.aed-sc,.aed-tc');
    if(x === 'addsec'){
      var ok = b.getAttribute('data-ok'), f = field(ok + '|order'); if(!f) return;
      var nk = rid('new-'), ord = f.get().concat(nk);
      if(changes([[ok + '|order', ord], [ok + '|s|' + nk + '|h', 'New section'], [ok + '|s|' + nk + '|t', 'Write here.']])){
        setTimeout(function(){ var mk = document.querySelector('#detail-content .aed-k[data-k="' + ok + '|s|' + nk + '"]'), sb = mk && mk.closest('.detail-section'), h3 = sb && sb.querySelector(':scope > h3');
          if(h3){ h3.scrollIntoView({block:'center'}); startField(h3, ok + '|s|' + nk + '|h'); try{ document.execCommand('selectAll'); }catch(_){} } }, 60);
      }
      return;
    }
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
    if(ck || f || body || t.closest('#canvas .node-card') || t.closest('.adt-card') || t.closest('.aed-sc,.aed-tc,.aed-add')){
      e.stopPropagation(); if(e.type === 'click') e.preventDefault();
    }
  }
  ['mousedown', 'mouseup', 'dblclick'].forEach(function(ev){ window.addEventListener(ev, eatIfEditing, true); });
  window.addEventListener('click', function(e){
    if(!editing()) return;
    var t = e.target; if(!t || !t.closest || inUi(t)) return;
    if(cur && cur.el.contains(t)){ e.stopPropagation(); return; }
    if(dragJustEnded){ dragJustEnded = false; e.stopPropagation(); e.preventDefault(); return; }
    var sb = t.closest('.aed-sc button,.aed-tc button,.aed-add');
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
      window[name] = function(){ if(cur) endField(true); hideBar(); return f.apply(this, arguments); };
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
    var id = nodeEl.id.replace(/^node-/, ''); if(!srcNode(id) || !field('p|' + id + '|shift')) return;
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
