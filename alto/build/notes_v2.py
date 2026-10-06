"""Notes and highlights, second pass: one place that owns the highlight store,
the note box, the Notes list and their histories.

What it fixes in the layers it replaces (all found in a real browser):

* A new highlight got an id like `hl-1` from a counter that restarts at 0 on
  every page load, so after a reload it collided with an older note. The box
  then showed the OLD note's text, Save overwrote it and the x deleted both.
  Ids are unique now, and a store that already holds duplicates is repaired.
* The desktop never re-applied highlights after leaving a page, and the
  re-apply that did exist marked the first matching text anywhere, even on a
  card of the timeline. A highlight now remembers the page it was made on
  (`src`) plus a little text on each side of it, and is painted back on that
  page, across inline tags, every time the page is shown.
* The "+" placeholder of a note that was never saved piled up as empty notes.

What it adds: Undo and Redo in the note box (that one note's own history),
Undo with Redo in the Notes panel for every change (new, edited, deleted,
recoloured), a "Note" pop-up after a highlight, and tapping a note in the Notes
list takes you to the page it came from (a pencil on the note edits it).

Every storage key is built from the page's own highlight key, so a share
re-stamps all of them like the rest of the page.
"""
from __future__ import annotations

NOTES_V2 = r"""<style id="alto-notes-v2-css">
  .alto-note-pop{position:fixed;left:0;top:0;z-index:8100;display:flex;align-items:center;gap:6px;padding:4px 11px 5px 9px;
    border-radius:9px;font-family:inherit;font-size:12px;letter-spacing:.05em;line-height:1.4;color:var(--text);
    background:var(--bg);border:1px solid var(--border);box-shadow:0 8px 22px var(--card-shadow);cursor:pointer;
    opacity:0;transition:opacity .12s ease;-webkit-tap-highlight-color:transparent;white-space:nowrap;}
  .alto-note-pop.on{opacity:1;}
  .alto-note-pop:hover{border-color:var(--muted);}
  .alto-note-pop svg{display:block;pointer-events:none;}
  html.mobile .alto-note-pop{font-size:14px;padding:7px 14px 8px 12px;border-radius:11px;}
  mark[data-hl-id].alto-hl-flash{animation:altoHlFlash 1.8s ease-out 1;}
  @keyframes altoHlFlash{0%,35%{outline:2px solid var(--accent,#d9a400);outline-offset:2px;}100%{outline:2px solid transparent;outline-offset:2px;}}
  #note-dialog .nd-head{display:flex;align-items:center;justify-content:space-between;gap:10px;}
  #note-dialog .nd-tools{display:flex;gap:8px;}
  #note-dialog .nd-btn{box-sizing:border-box;width:30px;height:30px;padding:0;border-radius:50%;cursor:pointer;display:flex;
    align-items:center;justify-content:center;background:var(--surface);border:1px solid var(--border);color:var(--muted);
    -webkit-tap-highlight-color:transparent;}
  #note-dialog .nd-btn svg{display:block;pointer-events:none;}
  #note-dialog .nd-btn:disabled{opacity:.35;cursor:default;}
  #note-dialog .nd-btn:not(:disabled):hover{color:var(--text);border-color:var(--muted);}
  #notes-footer .nt-btn.nt-redo svg{transform:scaleX(-1);}
  #notes-list .note-item{cursor:pointer;}
  #notes-list .note-item .note-where{font-size:10.5px;color:var(--muted);margin-top:5px;padding-left:12px;letter-spacing:.02em;
    word-break:break-word;opacity:.85;}
  #notes-list .note-item .note-quote, #notes-list .note-item .note-text{padding-right:68px !important;}
  #notes-list .note-edit{position:absolute;top:50%;right:38px;transform:translateY(-50%);width:22px;height:22px;padding:0;
    border-radius:50%;cursor:pointer;display:flex;align-items:center;justify-content:center;background:var(--surface);
    border:1px solid var(--border);color:var(--muted);}
  #notes-list .note-edit svg{display:block;pointer-events:none;}
  #notes-list .note-edit:hover{color:var(--text);border-color:var(--muted);}
  @media (hover:hover){
    #notes-list .note-item:hover{border-color:var(--muted) !important;}
    #notes-list .note-item .note-del:hover,#notes-list .note-item .note-edit:hover{border-color:var(--muted) !important;color:var(--text) !important;}
  }
  @media print{.alto-note-pop,#note-dialog .nd-tools{display:none !important;}}
</style>
<script id="alto-notes-v2">
(function(){
  if(window._altoNotesV2) return;
  var KEY = '__ALTO_HL_KEY__', TKEY = KEY + '-trash', OKEY = KEY + '-ops', HKEY = KEY + '-hist';
  var ls = window.localStorage, CAPO = 60, CAPV = 40, CTX = 30;
  var PEN = '<svg viewBox="0 0 12 12" width="11" height="11" fill="none" style="display:block"><path d="M9 1.5L10.5 3L4.5 9H3V7.5L9 1.5Z" fill="currentColor"/></svg>';
  var UNDO = '<svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3.5 3 6.5l3 3"/><path d="M3.4 6.5H9a3.6 3.6 0 0 1 0 7.2H6.5"/></svg>';
  var PENCIL = '<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M11 2.5l2.5 2.5L5.5 13H3v-2.5z"/></svg>';
  var XSVG = '<svg viewBox="0 0 12 12" width="8" height="8" style="display:block;pointer-events:none"><line x1="2" y1="2" x2="10" y2="10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="10" y1="2" x2="2" y2="10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
  var BORDER = {yellow:'rgba(255,220,50,0.7)', orange:'rgba(251,146,60,0.7)', green:'rgba(74,222,128,0.6)', blue:'rgba(74,158,255,0.5)', pink:'rgba(232,100,130,0.55)'};

  /* ── storage ─────────────────────────────────────────────────────────── */
  function jp(s, d){ try { var v = JSON.parse(s); return v == null ? d : v; } catch(e){ return d; } }
  function rdA(k){ var a; try { a = jp(ls.getItem(k), []); } catch(e){ a = []; } return Array.isArray(a) ? a : []; }
  function wr(k, v){ try { ls.setItem(k, v); } catch(e){} }
  function items(){ return rdA(KEY); }
  function put(arr){ wr(KEY, JSON.stringify(arr)); }
  function uid(p){ return p + Date.now().toString(36) + Math.floor(Math.random() * 46656).toString(36); }
  function byId(arr, id){ for(var i = 0; i < arr.length; i++) if(arr[i] && arr[i].id === id) return arr[i]; return null; }
  function mobile(){ return document.documentElement.classList.contains('mobile'); }
  function $(id){ return document.getElementById(id); }
  function el(tag, cls, text){ var n = document.createElement(tag); if(cls) n.className = cls; if(text != null) n.textContent = text; return n; }
  /* A tap that works the same under a finger and a mouse: touchend when it did not move, else click. */
  function tap(n, fn){
    var sx = 0, sy = 0, moved = false;
    n.addEventListener('touchstart', function(e){ var t = e.touches[0]; sx = t.clientX; sy = t.clientY; moved = false; }, {passive:true});
    n.addEventListener('touchmove', function(e){ var t = e.touches[0]; if(Math.abs(t.clientX - sx) > 8 || Math.abs(t.clientY - sy) > 8) moved = true; }, {passive:true});
    n.addEventListener('touchend', function(e){ if(moved) return; e.preventDefault(); e.stopPropagation(); fn(e); }, {passive:false});
    n.addEventListener('click', function(e){ e.stopPropagation(); fn(e); });
  }
  function fire(name){ try { window.dispatchEvent(new Event(name)); } catch(e){} }

  /* ── where we are ────────────────────────────────────────────────────── */
  var PG = null;                          // {type,id} of the open detail page
  function detailOpen(){ var d = $('detail-page'); return !!(d && d.classList.contains('visible')); }
  function curPage(){
    if(!detailOpen()) return null;
    if(PG && PG.type) return PG;
    return window._currentDetailType ? {type: window._currentDetailType, id: window._currentDetailId} : null;
  }
  function srcOfNode(n){
    if(!n || !n.closest) return null;
    if(n.closest('#detail-content')){ var p = curPage(); return p ? {t:'page', type:p.type, id:p.id} : null; }
    if(n.closest('#summary-wrap')) return {t:'summary'};
    var c = n.closest('.node'); if(c && /^node-/.test(c.id)) return {t:'card', id:c.id.replace(/^node-/, '')};
    return null;
  }
  function rootOf(src){
    if(!src) return null;
    if(src.t === 'page'){
      var p = curPage();
      return (p && p.type === src.type && String(p.id) === String(src.id)) ? $('detail-content') : null;
    }
    if(src.t === 'summary'){ var s = $('summary-wrap'); return s && s.classList.contains('open') ? s : null; }
    if(src.t === 'card') return $('node-' + src.id);
    return null;
  }
  function samePage(a, b){ return !!(a && b && a.t === b.t && String(a.type) === String(b.type) && String(a.id) === String(b.id)); }

  /* ── text map: the visible text of a page as one lower-case string with no spaces in it, and the way
        back from each character to its text node. Matching ignores spacing and case on purpose: the text
        a selection reports differs from the page's own (upper-cased headings, a space or a line break
        where one block ends and the next begins, non-breaking spaces). ── */
  function lc(c){ var l = c.toLowerCase(); return l.length === 1 ? l : c; }
  function sq(str){ var o = ''; str = String(str == null ? '' : str); for(var i = 0; i < str.length; i++){ var c = str.charAt(i); if(!/\s/.test(c)) o += lc(c); } return o; }
  function textMap(root){
    var nodes = [], idx = [], s = '', n;
    var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {acceptNode: function(t){
      var p = t.parentElement; return (!p || p.closest('script,style,textarea,.note-del,.alto-note-pop')) ? 2 : 1; }});
    while((n = w.nextNode())){
      var ni = nodes.length, t = n.nodeValue; nodes.push(n);
      for(var i = 0; i < t.length; i++){
        var c = t.charAt(i);
        if(!/\s/.test(c)){ s += lc(c); idx.push([ni, i]); }
      }
    }
    return {nodes:nodes, idx:idx, s:s};
  }
  function ctxScore(s, i, len, h){
    var pre = h.pre || '', post = h.post || '', sc = 0, a, b;
    if(pre){ a = s.slice(Math.max(0, i - pre.length), i); for(b = 0; b < pre.length && b < a.length && a.charAt(a.length - 1 - b) === pre.charAt(pre.length - 1 - b); b++) sc++; }
    if(post){ a = s.slice(i + len, i + len + post.length); for(b = 0; b < post.length && b < a.length && a.charAt(b) === post.charAt(b); b++) sc++; }
    return sc;
  }

  /* ── marks ───────────────────────────────────────────────────────────── */
  function mk(h){
    var m = document.createElement('mark');
    m.className = 'hl-' + (h.color || 'yellow'); m.dataset.hlId = h.id;
    m.title = h.note ? h.note : 'Click to add/view note';
    m.onclick = function(){ if(window.openNoteForHighlight) window.openNoteForHighlight(h.id); };
    return m;
  }
  function wrapSeg(node, a, b, h){
    if(b <= a) return null;
    if(!/\S/.test(node.nodeValue.slice(a, b))) return null;
    var p = node.parentElement;
    if(p && p.closest('mark[data-hl-id="' + h.id + '"]')) return null;
    var r = document.createRange(); r.setStart(node, a); r.setEnd(node, b);
    var m = mk(h);
    try { r.surroundContents(m); return m; } catch(e){ return null; }
  }
  function wrapMap(map, from, to, h){          // from..to inclusive indexes into map.s
    var segs = {}, order = [], i, m;
    for(i = from; i <= to; i++){
      m = map.idx[i]; if(!m) continue;
      if(!segs[m[0]]){ segs[m[0]] = {a:m[1], b:m[1] + 1}; order.push(m[0]); } else segs[m[0]].b = m[1] + 1;
    }
    var made = 0;
    order.forEach(function(ni){ if(wrapSeg(map.nodes[ni], segs[ni].a, segs[ni].b, h)) made++; });
    return made;
  }
  function wrapLive(range, h){                  // the exact range a person just selected
    var root = range.commonAncestorContainer, list = [], made = 0;
    if(root.nodeType === 3) list.push(root);
    else {
      var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT), n;
      while((n = w.nextNode())){ if(range.intersectsNode(n)) list.push(n); }
    }
    list.forEach(function(n){
      var a = n === range.startContainer ? range.startOffset : 0;
      var b = n === range.endContainer ? range.endOffset : n.nodeValue.length;
      if(wrapSeg(n, a, b, h)) made++;
    });
    return made;
  }
  function unmark(id){
    document.querySelectorAll('mark[data-hl-id="' + id + '"]').forEach(function(m){
      var p = m.parentNode; if(!p) return;
      while(m.firstChild) p.insertBefore(m.firstChild, m);
      p.removeChild(m); p.normalize();
    });
  }
  function markIn(root, h){
    var q = sq(h.quote); if(!q) return false;
    if(root.querySelector('mark[data-hl-id="' + h.id + '"]')) return true;
    var map = textMap(root), pos = -1, best = -1, from = 0, i;
    while((i = map.s.indexOf(q, from)) >= 0){
      var sc = ctxScore(map.s, i, q.length, h);
      if(sc > best){ best = sc; pos = i; }
      from = i + 1;
      if(best > 0 && best >= (h.pre || '').length + (h.post || '').length) break;
    }
    if(pos < 0) return false;
    return wrapMap(map, pos, pos + q.length - 1, h) > 0;
  }
  var painting = false, again = null;
  function paint(){
    if(painting) return; painting = true;
    try {
      var arr = items(), keep = {};
      arr.forEach(function(h){ if(h && h.id) keep[h.id] = 1; });
      document.querySelectorAll('mark[data-hl-id]').forEach(function(m){
        if(!keep[m.getAttribute('data-hl-id')]){
          var p = m.parentNode; if(!p) return;
          while(m.firstChild) p.insertBefore(m.firstChild, m);
          p.removeChild(m);
        }
      });
      var by = {};
      arr.forEach(function(h){ if(h && h.id) by[h.id] = h; });
      document.querySelectorAll('mark[data-hl-id]').forEach(function(m){      // colour and note shown on the page follow the store
        var h = by[m.getAttribute('data-hl-id')]; if(!h) return;
        var cls = 'hl-' + (h.color || 'yellow');
        if(!m.classList.contains(cls)){
          Array.prototype.slice.call(m.classList).forEach(function(c){ if(/^hl-/.test(c)) m.classList.remove(c); });
          m.classList.add(cls);
        }
        var t = h.note ? h.note : 'Click to add/view note'; if(m.title !== t) m.title = t;
      });
      arr.forEach(function(h){
        if(!h || !h.quote || !h.src) return;
        var root = rootOf(h.src); if(root) markIn(root, h);
      });
    } catch(e){}
    painting = false;
  }
  function paintSoon(){ paint(); setTimeout(paint, 80); setTimeout(paint, 320); }

  /* ── histories ───────────────────────────────────────────────────────── */
  function snapshot(){ return items().filter(function(h){ return h && h.id && !h.pending; }); }
  function pick(h){ return {note: h.note || '', color: h.color || 'yellow'}; }
  function diff(a, b){
    var A = {}, B = {}, add = [], del = [], chg = [];
    a.forEach(function(h){ A[h.id] = h; }); b.forEach(function(h){ B[h.id] = h; });
    b.forEach(function(h){ if(!A[h.id]) add.push(h); });
    a.forEach(function(h){ if(!B[h.id]) del.push(h); });
    b.forEach(function(h){
      var o = A[h.id]; if(!o) return;
      var x = pick(o), y = pick(h);
      if(x.note !== y.note || x.color !== y.color) chg.push({id:h.id, before:x, after:y});
    });
    return (add.length || del.length || chg.length) ? {add:add, del:del, chg:chg} : null;
  }
  var OPS = jp(ls.getItem(OKEY), null);
  if(!OPS || !Array.isArray(OPS.ops) || typeof OPS.p !== 'number') OPS = {p:0, ops:[]};
  var replaying = false;
  function saveOps(){ wr(OKEY, JSON.stringify(OPS)); fire('alto-trash-sync'); }
  function record(before, after){
    if(replaying) return;
    var d = diff(before, after); if(!d) return;
    d.ts = Date.now();
    OPS.ops = OPS.ops.slice(0, OPS.p); OPS.ops.push(d);
    if(OPS.ops.length > CAPO) OPS.ops = OPS.ops.slice(-CAPO);
    OPS.p = OPS.ops.length; saveOps();
  }
  function around(f){
    return function(){
      var before = snapshot(), r = f.apply(this, arguments);
      try { record(before, snapshot()); } catch(e){}
      return r;
    };
  }
  function alias(from, to){
    OPS.ops.forEach(function(o){
      (o.add || []).forEach(function(h){ if(h.id === from) h.id = to; });
      (o.del || []).forEach(function(h){ if(h.id === from) h.id = to; });
      (o.chg || []).forEach(function(c){ if(c.id === from) c.id = to; });
    });
  }
  function freshId(h){ return (h.kind === 'freeform' ? 'fn_' : 'hl-r') + uid(''); }
  function reinsert(list){                    // put items back under fresh ids (the old ids are on the sync ledger)
    var arr = items(), ids = {};
    list.forEach(function(h){
      var c = {}, f; for(f in h) if(f !== 'del' && f !== 'batch' && f !== 'pending') c[f] = h[f];
      c.id = freshId(h); if(!c.ts) c.ts = Date.now(); c.mod = Date.now();
      alias(h.id, c.id); arr.push(c); ids[h.id + '§' + (h.quote || '')] = 1;
    });
    arr.sort(function(a, b){ return (a.ts || 0) - (b.ts || 0); });
    put(arr);
    wr(TKEY, JSON.stringify(rdA(TKEY).filter(function(h){ return !ids[h.id + '§' + (h.quote || '')]; })));
  }
  function dropQuiet(ids){
    var set = {}; ids.forEach(function(i){ set[i] = 1; });
    put(items().filter(function(h){ return !(h && set[h.id]); }));
    ids.forEach(unmark);
  }
  function setFields(id, f){
    var arr = items(), h = byId(arr, id); if(!h) return false;
    h.note = f.note; h.color = f.color; h.mod = Date.now(); put(arr); return true;
  }
  function apply(o, back){
    replaying = true;
    try {
      if(back){
        if((o.add || []).length) dropQuiet(o.add.map(function(h){ return h.id; }));
        (o.chg || []).forEach(function(c){ setFields(c.id, c.before); });
        if((o.del || []).length) reinsert(o.del);
      } else {
        if((o.add || []).length) reinsert(o.add);
        (o.chg || []).forEach(function(c){ setFields(c.id, c.after); });
        if((o.del || []).length){
          var ids = o.del.map(function(h){ return h.id; }), before = items();
          var gone = before.filter(function(h){ return ids.indexOf(h.id) >= 0; });
          put(before.filter(function(h){ return ids.indexOf(h.id) < 0; }));
          ids.forEach(unmark);
          try { if(gone.length && window._altoNotesTrash && window._altoNotesTrash.trashGone) window._altoNotesTrash.trashGone(before, items()); } catch(e){}
        }
      }
    } finally { replaying = false; }
    reload();
  }
  var HIST = {
    canUndo: function(){ return OPS.p > 0; },
    canRedo: function(){ return OPS.p < OPS.ops.length; },
    undo: function(){ if(OPS.p <= 0) return false; var o = OPS.ops[OPS.p - 1]; OPS.p--; apply(o, true); saveOps(); return true; },
    redo: function(){ if(OPS.p >= OPS.ops.length) return false; var o = OPS.ops[OPS.p]; OPS.p++; apply(o, false); saveOps(); return true; }
  };
  window._altoNotesHist = HIST;

  /* ── repair what older builds left behind ────────────────────────────── */
  function repair(){
    var arr = items(), seen = {}, dirty = false, now = Date.now();
    arr = arr.filter(function(h){
      if(!h || typeof h !== 'object') { dirty = true; return false; }
      if(h.pending){ dirty = true; return false; }               // a note that was never saved
      return true;
    });
    arr.forEach(function(h, i){
      if(!h.kind){ h.kind = 'highlight'; dirty = true; }
      if(!h.ts){ h.ts = now - (arr.length - i) * 1000; dirty = true; }
      if(!h.id || seen[h.id]){ h.id = (h.kind === 'freeform' ? 'fn_' : 'hl-') + uid(''); dirty = true; }
      seen[h.id] = 1;
      if(h.kind === 'freeform' && !h.src && h.nodeId){ h.src = {t:'page', type:'node', id:h.nodeId}; dirty = true; }
    });
    if(dirty) put(arr);
    var H = jp(ls.getItem(HKEY), {}), hd = false;
    Object.keys(H).forEach(function(k){ if(!seen[k]){ delete H[k]; hd = true; } });
    if(hd) wr(HKEY, JSON.stringify(H));
  }
  /* A highlight made before pages were recorded: find the page whose text holds it. */
  function plain(html){ var d = document.createElement('div'); d.innerHTML = String(html == null ? '' : html); return sq(d.textContent); }
  function sectionsText(list){ return (list || []).map(function(s){ return s ? plain(s.t) : ''; }).join(''); }
  function guessSrc(h){
    var q = sq(h.quote); if(!q) return null;
    try {
      if(typeof NODES !== 'undefined'){
        for(var i = 0; i < NODES.length; i++){
          var n = NODES[i], nd = (typeof NODE_DETAILS !== 'undefined' && NODE_DETAILS[n.id]) || {};
          if((plain(n.desc) + plain(n.title) + sectionsText(nd.sections)).indexOf(q) >= 0) return {t:'page', type:'node', id:n.id};
        }
      }
      var pools = [['char', typeof CHAR_PAGES !== 'undefined' ? CHAR_PAGES : null], ['env', typeof ENVS !== 'undefined' ? ENVS : null],
                   ['theme', typeof THEMES !== 'undefined' ? THEMES : null]];
      for(var j = 0; j < pools.length; j++){
        var P = pools[j][1]; if(!P) continue;
        for(var k in P){ if(sectionsText(P[k] && P[k].sections).indexOf(q) >= 0) return {t:'page', type:pools[j][0], id:k}; }
      }
    } catch(e){}
    return null;
  }
  function backfillSrc(){
    var arr = items(), dirty = false;
    arr.forEach(function(h){ if(h && !h.src && h.kind !== 'freeform' && h.quote){ var s = guessSrc(h); if(s){ h.src = s; dirty = true; } } });
    if(dirty) put(arr);
    return dirty;
  }

  /* ── reload everything from storage ──────────────────────────────────── */
  function reload(){
    var arr = items().sort(function(a, b){ return (a.ts || 0) - (b.ts || 0); });
    try { if(typeof loadHighlights === 'function') loadHighlights(); } catch(e){}
    window.highlights = arr;
    paint(); render();
    try { if(typeof updateNotesToggle === 'function') updateNotesToggle(); } catch(e){}
    fire('alto-trash-sync');
  }

  /* ── making a highlight ──────────────────────────────────────────────── */
  function selectionContext(range, root, nq){
    var map = textMap(root), from = 0, i;
    while((i = map.s.indexOf(nq, from)) >= 0){
      var m = map.idx[i];
      if(m){
        var node = map.nodes[m[0]], inside = false;
        try { inside = range.isPointInRange(node, m[1]); } catch(e){}
        if(inside) return {pre: map.s.slice(Math.max(0, i - CTX), i), post: map.s.slice(i + nq.length, i + nq.length + CTX)};
      }
      from = i + 1;
    }
    return {pre:'', post:''};
  }
  function applyHighlight(color){
    var sel = window.getSelection(), range = null;
    if(window._pendingHlRange){ range = window._pendingHlRange; window._pendingHlRange = null; }   // phones: the range was taken off the screen already
    else if(sel && sel.rangeCount) range = sel.getRangeAt(0);
    if(!range) return null;
    var quote = range.toString().trim();
    if(!quote) return null;
    var anchor = range.commonAncestorContainer; if(anchor.nodeType === 3) anchor = anchor.parentElement;
    if(anchor && anchor.closest && anchor.closest('mark[data-hl-id]') && sq(anchor.closest('mark[data-hl-id]').textContent) === sq(quote)) return null;
    var src = srcOfNode(anchor), root = rootOf(src), ctx = {pre:'', post:''};
    if(root){ try { ctx = selectionContext(range.cloneRange(), root, sq(quote)); } catch(e){} }
    var h = {id: uid('hl-'), kind:'highlight', quote: quote, color: color || 'yellow', note:'', ts: Date.now(), src: src, pre: ctx.pre, post: ctx.post};
    var before = snapshot(), arr = items(); arr.push(h); put(arr);
    wrapLive(range, h);
    try { if(sel) sel.removeAllRanges(); } catch(e){}
    try { record(before, snapshot()); } catch(e){}
    window._lastHlId = h.id;
    reload();
    if(!mobile() && typeof window._showHlDot === 'function'){ try { window._showHlDot(); } catch(e){} }
    showPop(h.id);
    return h.id;
  }
  function addNoteToSelection(){
    var s = window.getSelection();
    if(!s || s.toString().trim().length < 1) return;
    applyHighlight(window._desktopHlColor || 'yellow');
  }

  /* ── the "Note" pop-up after a highlight ─────────────────────────────── */
  var pop = null, popTimer = null;
  function hidePop(){
    clearTimeout(popTimer);
    if(pop && pop.parentNode) pop.parentNode.removeChild(pop);
    pop = null;
  }
  function place(node, x, y){                 // x,y = wanted top-left of node in viewport px, whatever zoom the page runs at
    node.style.left = x + 'px'; node.style.top = y + 'px';
    for(var i = 0; i < 2; i++){
      var r = node.getBoundingClientRect();
      var k = r.width && node.offsetWidth ? r.width / node.offsetWidth : 1;
      node.style.left = (parseFloat(node.style.left) + (x - r.left) / k) + 'px';
      node.style.top = (parseFloat(node.style.top) + (y - r.top) / k) + 'px';
    }
  }
  function showPop(id){
    hidePop();
    var marks = document.querySelectorAll('mark[data-hl-id="' + id + '"]');
    if(!marks.length) return;
    var r = marks[0].getBoundingClientRect();
    if(!r.width && marks.length > 1) r = marks[1].getBoundingClientRect();
    var b = el('button', 'alto-note-pop'); b.type = 'button'; b.setAttribute('aria-label', 'Add a note to this highlight');
    b.innerHTML = PEN + '<span>Note</span>';
    document.body.appendChild(b); pop = b;
    var w = b.getBoundingClientRect().width, vw = window.innerWidth || document.documentElement.clientWidth;
    var x = Math.min(Math.max(8, r.left + r.width / 2 - w / 2), vw - w - 8);
    var h = b.getBoundingClientRect().height, y = r.top - h - 8;
    if(y < 8) y = r.bottom + 8;
    place(b, x, y);
    requestAnimationFrame(function(){ b.classList.add('on'); });
    function go(e){ if(e){ e.preventDefault(); e.stopPropagation(); } hidePop(); openNote(id); }
    b.addEventListener('mousedown', function(e){ e.preventDefault(); e.stopPropagation(); });
    b.addEventListener('click', go);
    b.addEventListener('touchend', go, {passive:false});
    popTimer = setTimeout(hidePop, 7000);
  }
  document.addEventListener('mousedown', function(e){ if(pop && !(e.target.closest && e.target.closest('.alto-note-pop'))) hidePop(); }, true);
  document.addEventListener('touchstart', function(e){ if(pop && !(e.target.closest && e.target.closest('.alto-note-pop'))) hidePop(); }, {capture:true, passive:true});
  window.addEventListener('scroll', function(){ if(pop) hidePop(); }, true);

  /* ── the note box ────────────────────────────────────────────────────── */
  var S = null, cpTimer = null;                // S = {id, v:[versions], p, saved, fresh}
  function box(){ return $('note-dialog'); }
  function ta(){ return $('note-input'); }
  function tools(){
    var d = box(); if(!d || d.querySelector('.nd-head')) return;
    var first = d.firstElementChild; if(!first) return;
    first.classList.add('nd-head');
    var label = el('span', 'nd-label', first.textContent); first.textContent = ''; first.appendChild(label);
    var t = el('span', 'nd-tools');
    var u = el('button', 'nd-btn nd-undo'); u.type = 'button'; u.title = 'Undo'; u.setAttribute('aria-label', 'Undo in this note'); u.innerHTML = UNDO;
    var r = el('button', 'nd-btn nd-redo'); r.type = 'button'; r.title = 'Redo'; r.setAttribute('aria-label', 'Redo in this note'); r.innerHTML = UNDO; r.firstChild.style.transform = 'scaleX(-1)';
    [u, r].forEach(function(b){ b.addEventListener('mousedown', function(e){ e.preventDefault(); }); });
    u.addEventListener('click', function(){ step(-1); });
    r.addEventListener('click', function(){ step(1); });
    t.appendChild(u); t.appendChild(r); first.appendChild(t);
    var a = ta();
    a.addEventListener('input', function(){ clearTimeout(cpTimer); cpTimer = setTimeout(checkpoint, 600); buttons(); });
    a.addEventListener('keydown', function(e){
      if(e.key === 'Escape'){ e.preventDefault(); cancelNote(); }
      else if(e.key === 'Enter' && (e.metaKey || e.ctrlKey)){ e.preventDefault(); saveNote(); }
    });
  }
  function checkpoint(){
    clearTimeout(cpTimer);
    if(!S) return;
    var v = ta().value;
    if(v === S.v[S.p]) return;
    S.v = S.v.slice(0, S.p + 1); S.v.push(v);
    if(S.v.length > CAPV) S.v = S.v.slice(-CAPV);
    S.p = S.v.length - 1; buttons();
  }
  function step(d){
    if(!S) return;
    checkpoint();
    var p = S.p + d; if(p < 0 || p >= S.v.length) return;
    S.p = p; ta().value = S.v[p]; buttons();
    try { ta().focus(); } catch(e){}
  }
  function buttons(){
    var d = box(); if(!d) return;
    var u = d.querySelector('.nd-undo'), r = d.querySelector('.nd-redo'); if(!u || !r) return;
    var dirty = !!S && ta().value !== S.v[S.p];
    u.disabled = !S || !(S.p > 0 || dirty);
    r.disabled = !S || !(S.p < S.v.length - 1);
  }
  function histFor(h){
    var H = jp(ls.getItem(HKEY), {}), r = H[h.id], cur = h.note || '';
    if(r && Array.isArray(r.v) && typeof r.p === 'number'){
      if(r.v[r.p] === cur) return {v: r.v.slice(), p: r.p};
      var v = r.v.slice(0, r.p + 1); v.push(cur); return {v: v, p: v.length - 1};
    }
    return {v:[cur], p:0};
  }
  function keepHist(id, text){
    var H = jp(ls.getItem(HKEY), {});
    var v = S.v.slice(), p = S.p;
    if(v[p] !== text){ v = v.slice(0, p + 1); v.push(text); p = v.length - 1; }
    if(v.length > CAPV){ v = v.slice(-CAPV); p = Math.min(p, v.length - 1); }
    H[id] = {v: v, p: p}; wr(HKEY, JSON.stringify(H));
  }
  function closeBox(){
    clearTimeout(cpTimer);
    var d = box(); if(d) d.classList.remove('visible');
    S = null;
    try { window.pendingSelection = null; } catch(e){}
  }
  function openNote(id){
    hidePop();
    tools();
    if(S && S.id !== id) settle();
    var h = byId(items(), id);
    if(!h) return;
    if(S && S.id === id){ try { ta().focus(); } catch(e){} return; }
    var hs = histFor(h);
    S = {id:id, v:hs.v, p:hs.p, saved:h.note || '', fresh:!!h.pending};
    var d = box(), a = ta();
    a.value = S.v[S.p];
    var lab = d.querySelector('.nd-label'); if(lab) lab.textContent = h.note ? 'EDIT NOTE' : 'ADD NOTE';
    d.style.top = '200px'; d.style.left = '50%'; d.style.transform = 'translateX(-50%)';
    d.classList.add('visible');
    buttons();
    try { a.focus(); } catch(e){}
  }
  /* Writes the box's text into its note; false when the note is gone. */
  function commit(){
    if(!S) return false;
    checkpoint();
    var text = ta().value.trim(), before = snapshot(), arr = items(), h = byId(arr, S.id);
    if(!h) return false;
    var changed = (h.note || '') !== text;
    h.note = text; if(changed || h.pending) h.mod = Date.now();
    delete h.pending; if(!h.ts) h.ts = Date.now();
    put(arr); keepHist(S.id, text);
    try { record(before, snapshot()); } catch(e){}
    return true;
  }
  function removePlaceholder(id){
    var arr = items(), h = byId(arr, id);
    if(h && h.pending && !(h.note && h.note.length)) put(arr.filter(function(x){ return x.id !== id; }));
  }
  /* The box is about to be used for something else: keep what was typed. */
  function settle(){
    if(!S) return;
    var id = S.id, dirty = ta().value.trim() !== S.saved.trim();
    if(dirty) commit(); else if(S.fresh) removePlaceholder(id);
    closeBox(); reload();
  }
  function saveNote(){
    if(!S) return;
    commit(); closeBox(); reload();
  }
  function cancelNote(){
    if(S && S.fresh) removePlaceholder(S.id);
    closeBox(); reload();
  }
  function addFreeformNote(){
    settle();
    var arr = items().filter(function(h){ return !h.pending; });     // a placeholder nobody saved is not a note
    var cp = curPage();
    var h = {id: uid('fn_'), kind:'freeform', ts: Date.now(), nodeId: cp && cp.type === 'node' ? cp.id : null,
             src: cp ? {t:'page', type:cp.type, id:cp.id} : null, note:'', quote:'', color:'yellow', pending:true};
    arr.push(h); put(arr);
    reload(); openNote(h.id);
  }

  /* Escape belongs to the open note box first: the page's own Escape handler (registered before this
     script, so it cannot be pre-empted) would close the Notes panel or leave the page instead. Each of
     the things it calls says no while the box is open and the key is Escape, and the box cancels. */
  function escOnBox(){
    var ev = window.event, d = box();
    return !!(ev && ev.type === 'keydown' && ev.key === 'Escape' && d && d.classList.contains('visible'));
  }
  function guardEsc(name){
    var f = window[name];
    if(typeof f !== 'function' || f.__altoEsc) return;
    var w = function(){ if(escOnBox()){ cancelNote(); return; } return f.apply(this, arguments); };
    w.__altoEsc = true; window[name] = w;
  }

  /* ── deleting ────────────────────────────────────────────────────────── */
  function trashed(before){
    try { if(window._altoNotesTrash && window._altoNotesTrash.trashGone) window._altoNotesTrash.trashGone(before, items()); } catch(e){}
  }
  function deleteHighlight(id){
    if(S && S.id === id) closeBox();
    var before = items(), snap = snapshot();
    if(!byId(before, id)) return;
    put(before.filter(function(h){ return h.id !== id; }));
    unmark(id); trashed(before);
    try { record(snap, snapshot()); } catch(e){}
    reload();
  }
  function clearAllHighlights(){
    var before = items(); if(!before.length) return;
    if(!confirm('This will delete all your highlights and notes. You can bring them back from the trash button in Notes. Continue?')) return;
    closeBox();
    var snap = snapshot();
    put([]); before.forEach(function(h){ unmark(h.id); }); trashed(before);
    try { record(snap, snapshot()); } catch(e){}
    reload();
    try { if(typeof notesOpen !== 'undefined' && notesOpen && typeof toggleNotes === 'function') toggleNotes(); } catch(e){}
  }

  /* ── going to where a note came from ─────────────────────────────────── */
  function placeName(src){
    try {
      if(!src) return '';
      if(src.t === 'summary') return 'Overview';
      if(src.t === 'card'){ var n = NODES.filter(function(x){ return x.id === src.id; })[0]; return n ? (window._altoNodeName ? window._altoNodeName(n) : n.title) : ''; }
      if(src.t === 'page'){
        if(src.type === 'node'){ var m = NODES.filter(function(x){ return x.id === src.id; })[0]; return m ? (window._altoNodeName ? window._altoNodeName(m) : m.title) : ''; }
        var pool = src.type === 'char' ? CHARS : src.type === 'env' ? ENVS : src.type === 'theme' ? THEMES : null;
        if(pool && pool[src.id]) return pool[src.id].name || '';
        if(src.type === 'index') return 'Index';
      }
    } catch(e){}
    return '';
  }
  function flash(id){
    var ms = document.querySelectorAll('mark[data-hl-id="' + id + '"]'); if(!ms.length) return;
    try { ms[0].scrollIntoView({block:'center', inline:'nearest'}); } catch(e){}
    ms.forEach(function(m){ m.classList.remove('alto-hl-flash'); void m.offsetWidth; m.classList.add('alto-hl-flash'); });
    setTimeout(function(){ ms.forEach(function(m){ m.classList.remove('alto-hl-flash'); }); }, 2000);
  }
  function holdPanelOpen(){                   // desktop: the Notes panel closes itself when the page changes; going to a note should not
    if(mobile()) return;
    window._notesOpenContext = null;
    setTimeout(function(){
      var p = $('notes-panel');
      window._notesOpenContext = p && p.classList.contains('open') ? {kind: detailOpen() ? 'detail' : 'main', id: window._currentDetailId || null, type: window._currentDetailType || null} : null;
    }, 40);
  }
  function go(h){
    var s = h.src || (h.kind !== 'freeform' ? guessSrc(h) : null);
    if(!s){                                   // no page on record (made on the timeline, or not findable): the timeline, never the box
      holdPanelOpen();
      if(mobile()){ var q = $('notes-panel'); if(q && q.classList.contains('open') && typeof toggleNotes === 'function') toggleNotes(); }
      if(detailOpen() && typeof window.showTimeline === 'function') window.showTimeline();
      return;
    }
    if(!h.src){ var arr = items(), x = byId(arr, h.id); if(x){ x.src = s; put(arr); } }
    holdPanelOpen();
    if(mobile()){ var p = $('notes-panel'); if(p && p.classList.contains('open') && typeof toggleNotes === 'function') toggleNotes(); }
    var here = rootOf(s);
    if(!here){
      if(s.t === 'page' && typeof window.showDetail === 'function') window.showDetail(s.type, s.id);
      else if(s.t === 'summary'){ if(!$('summary-wrap').classList.contains('open') && typeof toggleSummary === 'function') toggleSummary(); }
      else if(s.t === 'card'){ if(window._altoSearch && window._altoSearch.land) window._altoSearch.land(s.id); else if(typeof showTimeline === 'function') showTimeline(); }
    }
    paintSoon();
    setTimeout(function(){ paint(); flash(h.id); }, here ? 30 : 360);
  }

  /* ── the Notes list ──────────────────────────────────────────────────── */
  function render(){
    var list = $('notes-list'), empty = $('notes-empty');
    if(!list) return;
    Array.prototype.slice.call(list.children).forEach(function(n){ if(n.id !== 'notes-empty') n.remove(); });   // a phone's own renderer wipes the list, empty note included
    if(!empty){
      empty = el('div'); empty.id = 'notes-empty';
      empty.innerHTML = 'Select any text to highlight it.<br><br>Add notes to your highlights.<br><br>Make a report of them anytime.<br><br>Or switch to Freewrite to write an outline or answer.';
      list.appendChild(empty);
    }
    var arr = items().filter(function(h){ return h && !(h.pending && !(h.note && h.note.length)); });
    if(!arr.length){ if(empty) empty.style.display = 'block'; return; }
    if(empty) empty.style.display = 'none';
    arr.sort(function(a, b){ return (a.ts || 0) - (b.ts || 0); });
    arr.forEach(function(h){
      var item = el('div', 'note-item' + (h.kind === 'freeform' ? ' note-item-freeform' : '')); item.dataset.hlId = h.id;
      if(h.kind !== 'freeform'){
        var q = el('div', 'note-quote', '“' + (h.quote.length > 90 ? h.quote.slice(0, 90) + '…' : h.quote) + '”');
        q.style.borderColor = BORDER[h.color] || BORDER.yellow;
        item.appendChild(q);
      }
      var has = !!(h.note && h.note.length);
      var t = el('div', 'note-text', has ? h.note : (h.kind === 'freeform' ? 'Empty note — tap the pencil to edit' : 'No note — tap the pencil to add'));
      if(!has){ t.style.color = 'var(--muted)'; t.style.fontStyle = 'italic'; }
      item.appendChild(t);
      var where = placeName(h.src);
      if(where) item.appendChild(el('div', 'note-where', '↗ ' + where));
      var ed = el('button', 'note-edit'); ed.type = 'button'; ed.title = 'Edit this note'; ed.setAttribute('aria-label', 'Edit this note'); ed.innerHTML = PENCIL;
      tap(ed, function(){ openNote(h.id); });
      var del = el('button', 'note-del'); del.type = 'button'; del.setAttribute('aria-label', 'Delete'); del.innerHTML = XSVG;
      tap(del, function(){ deleteHighlight(h.id); });
      item.appendChild(ed); item.appendChild(del);
      tap(item, function(){ go(byId(items(), h.id) || h); });
      list.appendChild(item);
    });
  }

  /* ── the Notes panel's own Undo / Redo ───────────────────────────────── */
  function panelButtons(){
    var u = $('notes-undo-btn'); if(!u) return;
    var r = $('notes-redo-btn');
    if(!r){
      r = el('button', 'nt-btn nt-redo'); r.id = 'notes-redo-btn'; r.type = 'button';
      r.title = 'Redo'; r.setAttribute('aria-label', 'Redo'); r.innerHTML = UNDO;
      u.parentNode.insertBefore(r, u.nextSibling);
      r.addEventListener('click', function(){ HIST.redo(); });
      window.addEventListener('alto-trash-sync', panelButtons);
    }
    u.title = 'Undo'; u.setAttribute('aria-label', 'Undo');
    r.disabled = !HIST.canRedo();
  }

  /* ── install ─────────────────────────────────────────────────────────── */
  function own(name, fn){ fn.__terrariumWrapped = true; fn.__altoTrash = true; window[name] = fn; }
  function override(){
    own('openNoteForHighlight', openNote);
    own('saveNote', saveNote);
    own('cancelNote', cancelNote);
    own('addFreeformNote', addFreeformNote);
    own('deleteHighlight', deleteHighlight);
    own('clearAllHighlights', clearAllHighlights);
    own('applyHighlight', applyHighlight);
    own('addNoteToSelection', addNoteToSelection);
    own('renderNotesList', render);
    own('renderHighlightMarks', paint);
    own('findAndMarkText', function(){});
    own('reapplyHighlightsAfterNav', paintSoon);
  }
  function install(){
    repair();
    tools();
    override();
    ['toggleNotes', 'toggleSummary', 'toggleInfoPanel', 'toggleSearch', 'showTimeline', 'exitFocus'].forEach(guardEsc);
    var sd = window.showDetail;
    if(typeof sd === 'function' && !sd.__altoNotesV2){
      var w = function(type, id){ PG = {type:type, id:id}; hidePop(); var r = sd.apply(this, arguments); paintSoon(); return r; };
      w.__altoNotesV2 = true; window.showDetail = w;
    }
    var st = window.showTimeline;
    if(typeof st === 'function' && !st.__altoNotesV2){
      var w2 = function(){ PG = null; hidePop(); var r = st.apply(this, arguments); paintSoon(); return r; };
      w2.__altoNotesV2 = true; window.showTimeline = w2;
    }
    var ts = window.toggleSummary;
    if(typeof ts === 'function' && !ts.__altoNotesV2){
      var w3 = function(){ var r = ts.apply(this, arguments); paintSoon(); return r; };
      w3.__altoNotesV2 = true; window.toggleSummary = w3;
    }
    var dc = $('detail-content');
    if(dc){ try { new MutationObserver(function(){ if(!painting) paintSoon(); }).observe(dc, {childList:true}); } catch(e){} }
    document.addEventListener('click', function(e){                      // a colour picked from the dot: one undoable step
      var sw = e.target.closest && e.target.closest('.hl-pal-swatch'); if(!sw) return;
      var before = snapshot(); setTimeout(function(){ try { record(before, snapshot()); } catch(x){} reload(); }, 0);
    }, true);
    window.addEventListener('storage', function(ev){ if(ev && ev.key === OKEY){ OPS = jp(ev.newValue, OPS); fire('alto-trash-sync'); } });
    panelButtons();
    reload();
    if(backfillSrc()) reload();
  }
  window._altoNotesV2 = {open: openNote, go: go, paint: paint, hist: HIST, keys: {KEY: KEY, OPS: OKEY, HIST: HKEY}};
  function boot(){ install(); setTimeout(override, 900); setTimeout(override, 3000); }
  if(document.readyState === 'complete') boot(); else window.addEventListener('load', boot);
})();
</script>"""


def notes_v2(b) -> str:
    """NOTES_V2 with this timeline's highlight storage key (the page's own
    `alto-hl-{tid}` text, which a share re-stamps like every other copy)."""
    from .blocks import ID_PATTERNS
    return NOTES_V2.replace("__ALTO_HL_KEY__", ID_PATTERNS["hl_key"].format(tid=b.timeline_id)) + "\n"
