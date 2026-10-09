"""Freewrite: a second mode of the Notes panel, one rich-text document per
timeline, for writing a whole outline (an exam answer) while looking at the
timeline and moving between detail pages.

* A switch at the top of the panel: "Notes & highlights" | "Freewrite". The
  document never touches the highlight store.
* It saves itself (debounced on typing, at once on blur / pagehide / hiding the
  tab) into `{page hl key}-fw` as `{html, mod}`, and alto-cloud.js carries that
  to users/{uid}/tl/{tid}.fw (the later `mod` wins). The key is the page's own
  highlight key plus a suffix, so a share re-stamps it with the rest and a
  viewer of a share has a document of their own, never the owner's.
* It stays open until the panel's own x closes it: toggleNotes is guarded here
  (a close that did not come from the x is swallowed while Freewrite is the
  open mode), the engine's Escape / arrow / swipe / wheel paths are patched in
  engine_patches.py, and the open state is remembered across reloads.
* Stored and pasted HTML is rebuilt from a whitelist (b i u s h1 h2 p div br ul
  ol li); no attribute, script or style survives.
* A report can carry it: the Notes panel's footer offers "Attach my Freewrite"
  (shown only once there is something written, remembered with the panel's
  other choices) and the Freewrite pane's own footer has a Report button that
  makes a report with it attached. The engine's generateNotesReport (patched in
  engine_patches.py, freewrite-report-*) asks window._altoFwReport() for the
  document; what comes back is already rebuilt from the whitelist.
"""
from __future__ import annotations

FREEWRITE = r"""<style id="alto-freewrite-css">
  #fw-seg{display:flex;gap:2px;margin:10px 12px 0;padding:2px;border:1px solid var(--border);border-radius:9px;
    background:var(--surface);flex-shrink:0;}
  #fw-seg button{flex:1;font:inherit;font-size:11.5px;letter-spacing:.03em;padding:6px 6px;border:0;border-radius:7px;
    background:transparent;color:var(--muted);cursor:pointer;-webkit-tap-highlight-color:transparent;white-space:nowrap;}
  #fw-seg button[aria-selected="true"]{background:var(--card-glass-bg,var(--bg));color:var(--text);
    box-shadow:0 1px 3px var(--card-shadow,rgba(0,0,0,.12));}
  html.mobile #fw-seg button{font-size:13px;padding:9px 6px;}
  #fw-pane{display:none;flex:1;min-height:0;flex-direction:column;}
  #notes-panel.fw-mode #fw-pane{display:flex;}
  #notes-panel.fw-mode #notes-list, #notes-panel.fw-mode #notes-trash, #notes-panel.fw-mode #notes-footer{display:none !important;}
  html:not(.mobile) #notes-panel.fw-mode{width:var(--fw-w,460px) !important;max-width:calc(100vw - 110px);}
  html.mobile #notes-panel.fw-mode{background:var(--bg) !important;}   /* a sheet to write on: nothing of the page may show through the text */
  html:not(.mobile) #notes-panel.fw-dragging{transition:none !important;}
  html:not(.mobile).fw-open #detail-page{padding-right:calc(var(--fw-w,460px) + 62px) !important;}   /* the page being read stays beside the box, not under it */
  /* While the panel is open on a desktop the floating controls (engine_patches desktop-controls-row, via
     --np-dock) and the right-edge tabs sit just left of it; the Notes tab itself is redundant (the panel's x closes it). */
  html:not(.mobile).np-docked #tab-rail{right:var(--np-dock,0px);}
  html:not(.mobile).np-docked #notes-toggle{display:none !important;}
  html:not(.mobile).np-docked #ef-panel{right:calc(46px + var(--np-dock,0px));}
  html:not(.mobile).np-docked #world::after{content:"";position:absolute;left:100%;top:0;width:var(--np-dock,0px);height:1px;pointer-events:none;}   /* scroll room: the cards can always be brought out from under the panel */
  html.mobile.np-open #scroll-hint{display:none !important;}   /* the "Swipe to navigate" hint must not float over the sheet */
  #fw-resize{display:none;position:absolute;left:-4px;top:0;bottom:0;width:9px;cursor:ew-resize;z-index:3;touch-action:none;}
  #fw-resize::after{content:"";position:absolute;left:3px;top:50%;width:3px;height:36px;margin-top:-18px;border-radius:2px;
    background:var(--border);opacity:0;transition:opacity .15s ease;}
  html:not(.mobile) #notes-panel.fw-mode #fw-resize{display:block;}
  #fw-resize:hover::after, #fw-resize:focus-visible::after, #notes-panel.fw-dragging #fw-resize::after{opacity:1;background:var(--muted);}
  #fw-tools{display:flex;flex-wrap:wrap;align-items:center;gap:2px;padding:8px 10px;border-bottom:1px solid var(--header-hairline,var(--border));flex-shrink:0;}
  #fw-tools button{box-sizing:border-box;width:28px;height:28px;padding:0;border:1px solid transparent;border-radius:7px;background:transparent;
    color:var(--muted);cursor:pointer;display:flex;align-items:center;justify-content:center;font:inherit;font-size:13px;line-height:1;
    -webkit-tap-highlight-color:transparent;}
  html.mobile #fw-tools button{width:36px;height:36px;font-size:15px;flex:none;}
  html.mobile #fw-tools{flex-wrap:nowrap;overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;scrollbar-width:none;overscroll-behavior-x:contain;}   /* one row; the rest scrolls sideways */
  html.mobile #fw-tools::-webkit-scrollbar{display:none;}
  #fw-tools button svg{display:block;pointer-events:none;}
  #fw-tools button:disabled{opacity:.35;cursor:default;}
  #fw-tools button.on{color:var(--text);background:var(--surface);border-color:var(--border);}
  @media (hover:hover){#fw-tools button:not(:disabled):hover{color:var(--text);border-color:var(--muted);}}
  #fw-tools .fw-sep{width:1px;height:16px;margin:0 4px;background:var(--border);flex-shrink:0;}
  #fw-tools .fw-h{font-size:11.5px;font-weight:700;letter-spacing:-.02em;}
  #fw-editor{position:relative;flex:1;min-height:0;overflow-y:auto;padding:14px 16px;outline:none;font-size:14px;line-height:1.6;
    color:var(--text);word-break:break-word;-webkit-user-select:text;user-select:text;-webkit-overflow-scrolling:touch;
    overscroll-behavior:contain;cursor:text;}
  html.mobile #fw-editor{font-size:16px;padding:14px 16px 24px;}
  #fw-editor.fw-empty::before{content:attr(data-ph);color:var(--muted);float:left;height:0;pointer-events:none;max-width:92%;}
  #fw-editor p, #fw-editor div{margin:0;}
  #fw-editor h1{font-size:1.3em;font-weight:700;line-height:1.3;margin:.75em 0 .3em;}
  #fw-editor h2{font-size:1.12em;font-weight:700;line-height:1.3;margin:.65em 0 .25em;}
  #fw-editor > :first-child{margin-top:0;}
  #fw-editor ul, #fw-editor ol{margin:.15em 0;padding-left:1.55em;}
  #fw-editor ul{list-style:disc;} #fw-editor ul ul{list-style:circle;} #fw-editor ul ul ul{list-style:square;}
  #fw-editor ol{list-style:decimal;} #fw-editor ol ol{list-style:lower-alpha;} #fw-editor ol ol ol{list-style:lower-roman;}
  #fw-editor li{margin:.05em 0;}
  #fw-foot{display:flex;align-items:center;gap:10px;padding:8px 12px;border-top:1px solid var(--header-hairline,var(--border));
    flex-shrink:0;font-size:11px;color:var(--muted);letter-spacing:.02em;}
  html.mobile #fw-foot{padding-bottom:calc(8px + env(safe-area-inset-bottom,0px));font-size:12px;}
  #fw-foot .fw-grow{flex:1;}
  #fw-state{transition:opacity .5s ease;}
  #fw-state.idle{opacity:.55;}
  #fw-foot button{font:inherit;font-size:11.5px;padding:5px 11px;border-radius:14px;cursor:pointer;background:var(--surface);
    border:1px solid var(--border);color:var(--text);-webkit-tap-highlight-color:transparent;}
  html.mobile #fw-foot button{font-size:13px;padding:7px 14px;}
  @media (hover:hover){#fw-foot button:hover{border-color:var(--muted);}}
  #fw-attach{display:none;align-items:center;gap:8px;font-size:12px;letter-spacing:.02em;color:var(--muted);cursor:pointer;
    user-select:none;-webkit-user-select:none;-webkit-tap-highlight-color:transparent;}
  #fw-attach.has{display:flex;}
  #fw-attach input{margin:0;width:14px;height:14px;accent-color:var(--accent,#6d5bd0);cursor:pointer;}
  #fw-attach .fw-n{opacity:.75;}
  html.mobile #fw-attach{font-size:14px;padding:4px 0;gap:10px;} html.mobile #fw-attach input{width:20px;height:20px;}
  #notes-panel.trash-mode #fw-attach{display:none !important;}
  #fw-print-host{display:none;}
  @media print{
    html.fw-printing body > *:not(#fw-print-host){display:none !important;}
    html.fw-printing, html.fw-printing body{height:auto !important;min-height:0 !important;overflow:visible !important;background:#fff !important;}
    html.fw-printing #fw-print-host{display:block !important;position:static !important;color:#000;background:#fff;
      font:12pt/1.5 Georgia,'Times New Roman',serif;padding:0;margin:0;}
    #fw-print-host .fw-ph{font:600 9pt/1.4 -apple-system,Helvetica,Arial,sans-serif;letter-spacing:.08em;text-transform:uppercase;
      color:#666;border-bottom:1px solid #bbb;padding-bottom:6pt;margin-bottom:12pt;}
    #fw-print-host h1{font-size:16pt;margin:14pt 0 4pt;} #fw-print-host h2{font-size:13pt;margin:12pt 0 3pt;}
    #fw-print-host p, #fw-print-host div{margin:0;}
    #fw-print-host ul, #fw-print-host ol{margin:2pt 0;padding-left:20pt;}
    #fw-print-host ul{list-style:disc;} #fw-print-host ol{list-style:decimal;}
  }
</style>
<script id="alto-freewrite">
(function(){
  if(window._altoFw) return;
  var KEY = '__ALTO_HL_KEY__', FKEY = KEY + '-fw', UKEY = KEY + '-fwui', CAP = 400000, DEF_W = 460;
  var ls = window.localStorage;
  var LAB = {notes:'Notes & highlights', fw:'Freewrite', ph:'Write freely: an outline, an answer, anything. It saves on its own and stays here as you move between pages.',
    bold:'Bold (⌘B)', italic:'Italic (⌘I)', underline:'Underline (⌘U)', strike:'Strikethrough', h1:'Heading 1', h2:'Heading 2',
    ul:'Bulleted list', ol:'Numbered list', indent:'Indent list item (Tab)', outdent:'Outdent list item (Shift+Tab)', clear:'Clear formatting',
    copy:'Copy', print:'Print', report:'Report', reportTip:'Make a report with this Freewrite attached', attach:'Attach my Freewrite', saved:'Saved', saving:'Saving…', copied:'Copied', big:'Too long to save', resize:'Drag to resize'};
  function jp(s, d){ try { var v = JSON.parse(s); return v == null ? d : v; } catch(e){ return d; } }
  function rd(k, d){ try { return jp(ls.getItem(k), d); } catch(e){ return d; } }
  function wr(k, v){ try { ls.setItem(k, v); return true; } catch(e){ return false; } }
  function $(id){ return document.getElementById(id); }
  function mobile(){ return document.documentElement.classList.contains('mobile'); }
  function el(tag, attrs, html){ var n = document.createElement(tag); if(attrs) for(var k in attrs) n.setAttribute(k, attrs[k]); if(html != null) n.innerHTML = html; return n; }

  /* ── the whitelist: what a stored or pasted document may contain ─────── */
  var KEEP = {B:'b', STRONG:'b', I:'i', EM:'i', U:'u', S:'s', STRIKE:'s', DEL:'s', UL:'ul', OL:'ol', LI:'li', H1:'h1', H2:'h2', H3:'h2', H4:'h2', H5:'h2', H6:'h2',
              P:'p', DIV:'div', BR:'br', BLOCKQUOTE:'div', TR:'div', PRE:'div'};
  var DROP = {SCRIPT:1, STYLE:1, IFRAME:1, FRAME:1, OBJECT:1, EMBED:1, TEMPLATE:1, NOSCRIPT:1, SVG:1, MATH:1, HEAD:1, TITLE:1, META:1, LINK:1, TEXTAREA:1,
              SELECT:1, BUTTON:1, INPUT:1, FORM:1, CANVAS:1, AUDIO:1, VIDEO:1, IMG:1, PICTURE:1, BASE:1, APPLET:1};
  function wrapIn(parent, name){ var n = document.createElement(name); parent.appendChild(n); return n; }
  function clean(src, dst){
    for(var c = src.firstChild; c; c = c.nextSibling){
      if(c.nodeType === 3){ dst.appendChild(document.createTextNode(String(c.nodeValue).replace(/\u0000/g, ''))); continue; }
      if(c.nodeType !== 1) continue;
      var tag = String(c.tagName).toUpperCase();
      if(DROP[tag]) continue;
      var st = String(c.getAttribute('style') || '').toLowerCase(), name = KEEP[tag], into = dst;
      if((tag === 'B' || tag === 'STRONG') && /font-weight:\s*(normal|[1-5]00)/.test(st)) name = null;   // Google Docs wraps a paste in <b style="font-weight:normal">
      if(name){ into = wrapIn(dst, name); }
      else if(tag === 'TD' || tag === 'TH'){ if(dst.lastChild) dst.appendChild(document.createTextNode(' ')); }
      if(st){                                                                                           // Word / Docs / web pages say bold, italic... in a style
        if(/font-weight:\s*(bold|[6-9]00)/.test(st) && name !== 'b') into = wrapIn(into, 'b');
        if(/font-style:\s*italic/.test(st) && name !== 'i') into = wrapIn(into, 'i');
        if(/text-decoration[^;]*underline/.test(st) && name !== 'u') into = wrapIn(into, 'u');
        if(/text-decoration[^;]*line-through/.test(st) && name !== 's') into = wrapIn(into, 's');
      }
      clean(c, into);
    }
  }
  function sanitize(html){
    var body;
    try { body = new DOMParser().parseFromString('<body>' + String(html == null ? '' : html), 'text/html').body; } catch(e){ return ''; }
    var out = document.createElement('div');
    if(body) clean(body, out);
    if(!out.textContent.replace(/[\s ​]/g, '') && !out.querySelector('ul,ol,li,h1,h2')) return '';
    return out.innerHTML;
  }

  /* ── plain text of the document (Copy, and the text half of a rich copy) ── */
  function plain(root){
    var out = [];
    function line(s){ out.push(s); }
    function walk(n, depth, list){
      for(var c = n.firstChild; c; c = c.nextSibling){
        if(c.nodeType === 3){ var t = c.nodeValue.replace(/[ \r\n]+/g, ' '); if(t) line({t:t}); continue; }
        if(c.nodeType !== 1) continue;
        var g = c.tagName.toLowerCase();
        if(g === 'br'){ line({br:1}); continue; }
        if(g === 'ul' || g === 'ol'){ line({blk:1}); walk(c, depth + 1, {ord: g === 'ol', n: 0}); line({blk:1}); continue; }
        if(g === 'li'){ line({blk:1}); var mark = list && list.ord ? (++list.n + '. ') : '- '; line({t: new Array(Math.max(depth - 1, 0) + 1).join('  ') + mark}); walk(c, depth, null); line({blk:1}); continue; }
        if(/^(p|div|h1|h2)$/.test(g)){ line({blk:1}); walk(c, depth, list); line({blk:1}); continue; }
        walk(c, depth, list);
      }
    }
    walk(root, 0, null);
    var s = '', pend = false;
    out.forEach(function(x){
      if(x.t != null){ if(pend && s && s.charAt(s.length - 1) !== '\n') s += '\n'; pend = false; s += x.t; }
      else if(x.br){ s += '\n'; pend = false; }
      else if(x.blk){ pend = true; }
    });
    return s.replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').replace(/^\s+|\s+$/g, '');
  }

  /* ── state ───────────────────────────────────────────────────────────── */
  var ui = rd(UKEY, {}); if(!ui || typeof ui !== 'object') ui = {};
  var MODE = ui.mode === 'fw' ? 'fw' : 'notes', W = +ui.w || DEF_W, ATT = !!ui.att;
  var ed = null, panel = null, T = 0, dirty = false, LASTMOD = 0, lastRange = null, FORCE = false, stateTimer = 0;
  function saveUi(){ var p = $('notes-panel'); wr(UKEY, JSON.stringify({mode: MODE, open: !!(p && p.classList.contains('open')) && MODE === 'fw', w: W, att: ATT})); }
  function pinned(){ return MODE === 'fw' && typeof notesOpen !== 'undefined' && !!notesOpen; }
  function stored(){ var o = rd(FKEY, null); return o && typeof o === 'object' ? {html: String(o.html || ''), mod: Number(o.mod) || 0} : {html: '', mod: 0}; }

  function setState(t, quiet){
    var s = $('fw-state'); if(!s) return; s.textContent = t; s.classList.toggle('idle', !!quiet);
    clearTimeout(stateTimer); if(t === LAB.saved && !quiet) stateTimer = setTimeout(function(){ s.classList.add('idle'); }, 1800);
  }
  function words(){
    var t = (ed.innerText || ed.textContent || '').replace(/[ ​]/g, ' ').trim();
    var n = t ? t.split(/\s+/).length : 0;
    var c = $('fw-count'); if(c) c.textContent = n + (n === 1 ? ' word' : ' words');
    ed.classList.toggle('fw-empty', !t && !ed.querySelector('li,h1,h2'));
    attachRow(!!t || !!ed.querySelector('li,h1,h2'), n);
  }
  /* the footer's "Attach my Freewrite": there only once something is written */
  function attachRow(has, n){
    var a = $('fw-attach'); if(!a) return;
    a.classList.toggle('has', !!has);
    var c = $('fw-attach-n'); if(c) c.textContent = '(' + n + (n === 1 ? ' word' : ' words') + ')';
    var i = a.querySelector('input'); if(i) i.checked = ATT;
  }
  /* What a report takes from here: {html, text, words}, or null when it is not wanted (or nothing is written).
     `force` is the Freewrite pane's own Report button. The document is flushed and rebuilt from the whitelist first. */
  function forReport(force){
    if(!ed || !(force || ATT)) return null;
    flush();
    var h = sanitize(stored().html || ed.innerHTML);
    if(!h) return null;
    var box = document.createElement('div'); box.innerHTML = h;
    var t = plain(box); if(!t) return null;
    var w = t.replace(/^\s*(?:[-*\u2022]|\d+[.)])\s+/gm, '').trim();
    return {html: h, text: t, words: w ? w.split(/\s+/).length : 0};
  }
  function ensure(){                                    // an empty box still holds one line, so typing starts inside a block
    if(!ed.firstChild){ ed.innerHTML = '<div><br></div>'; if(document.activeElement === ed){ try { var r = document.createRange(); r.setStart(ed.firstChild, 0); r.collapse(true); var s = window.getSelection(); s.removeAllRanges(); s.addRange(r); } catch(e){} } }
  }
  function load(){
    var o = stored(); LASTMOD = o.mod;
    var h = sanitize(o.html);
    if(ed.innerHTML !== h) ed.innerHTML = h;
    ensure(); words();
  }
  function flush(){
    clearTimeout(T); T = 0;
    if(!dirty || !ed) return;
    var h = sanitize(ed.innerHTML);
    if(h.length > CAP){ setState(LAB.big); return; }
    var mod = Math.max(Date.now(), LASTMOD + 1);
    if(wr(FKEY, JSON.stringify({html: h, mod: mod}))){ LASTMOD = mod; dirty = false; setState(LAB.saved); }
  }
  function touch(){
    dirty = true; setState(LAB.saving); clearTimeout(T); T = setTimeout(flush, 600); words();
  }
  function remote(){                                    // another tab or the account has a newer copy
    if(!ed) return;
    var o = stored(); if(o.mod <= LASTMOD) return;
    if(dirty) return;                                   // what is being typed here is newer than it looks
    var had = document.activeElement === ed;
    load();
    if(had){ try { var r = document.createRange(); r.selectNodeContents(ed); r.collapse(false); var s = window.getSelection(); s.removeAllRanges(); s.addRange(r); } catch(e){} }
  }

  /* ── commands ────────────────────────────────────────────────────────── */
  function inEd(n){ return !!(n && ed && ed.contains(n)); }
  function selNode(){ var s = window.getSelection(); return s && s.rangeCount && inEd(s.anchorNode) ? (s.anchorNode.nodeType === 1 ? s.anchorNode : s.anchorNode.parentElement) : null; }
  function up(tag){ var n = selNode(); while(n && n !== ed){ if(n.tagName && n.tagName.toLowerCase() === tag) return n; n = n.parentElement; } return null; }
  function inList(){ return !!(up('li')); }
  function restore(){
    if(document.activeElement !== ed){
      ed.focus();
      if(lastRange){ try { var s = window.getSelection(); s.removeAllRanges(); s.addRange(lastRange); } catch(e){} }
    }
  }
  function cmd(c, v){ restore(); try { document.execCommand(c, false, v == null ? null : v); } catch(e){} touch(); sync(); }
  function heading(tag){
    restore(); if(inList()) return;
    var h = up(tag);
    try { document.execCommand('formatBlock', false, h ? '<p>' : '<' + tag + '>'); } catch(e){}
    touch(); sync();
  }
  function clearFmt(){
    restore();
    try {
      document.execCommand('removeFormat', false, null);
      if(up('h1') || up('h2')) document.execCommand('formatBlock', false, '<p>');
      if(up('ol')) document.execCommand('insertOrderedList', false, null);
      else if(up('ul')) document.execCommand('insertUnorderedList', false, null);
    } catch(e){}
    touch(); sync();
  }
  function sync(){
    var q = function(c){ try { return !!document.activeElement && document.activeElement === ed && document.queryCommandState(c); } catch(e){ return false; } };
    var on = {bold:q('bold'), italic:q('italic'), underline:q('underline'), strike:q('strikeThrough'),
              h1: !!up('h1'), h2: !!up('h2'), ul: !!up('ul'), ol: !!up('ol')};
    var li = inList();
    Array.prototype.forEach.call(document.querySelectorAll('#fw-tools button[data-fw]'), function(b){
      var k = b.getAttribute('data-fw'); b.classList.toggle('on', !!on[k]); if(k in on) b.setAttribute('aria-pressed', on[k] ? 'true' : 'false');
      if(k === 'indent' || k === 'outdent') b.disabled = !li;
      if(k === 'h1' || k === 'h2') b.disabled = li;
    });
  }

  /* An outline typed the way people type one: "- " or "1. " at the start of a line begins a list. */
  function autoList(e){
    if(!e || e.inputType !== 'insertText' || e.data !== ' ' || inList()) return;
    var s = window.getSelection(); if(!s || !s.rangeCount || !s.isCollapsed) return;
    var r = s.getRangeAt(0), n = r.endContainer, pre = document.createRange();
    var blk = n.nodeType === 1 ? n : n.parentElement; while(blk && blk !== ed && !/^(div|p)$/i.test(blk.tagName)) blk = blk.parentElement;
    if(!blk) return;
    if(blk !== ed){ pre.selectNodeContents(blk); pre.setStart(blk, 0); }
    else {                                              // a line typed straight into the box: back to the break or block before it
      var top = n; while(top.parentNode && top.parentNode !== ed) top = top.parentNode;
      while(top.previousSibling && !(top.previousSibling.nodeType === 1 && /^(br|div|p|ul|ol|h1|h2)$/i.test(top.previousSibling.tagName))) top = top.previousSibling;
      pre.setStartBefore(top);
    }
    pre.setEnd(r.endContainer, r.endOffset);
    var t = pre.toString().replace(/ /g, ' ');
    var ord = /^\d{1,3}[.)] $/.test(t);
    if(!ord && !/^[-*•] $/.test(t)) return;
    s.removeAllRanges(); s.addRange(pre);               // select the marker, then type over it with the list
    try { document.execCommand('delete', false, null); document.execCommand(ord ? 'insertOrderedList' : 'insertUnorderedList', false, null); } catch(x){}
  }

  function onKey(e){
    e.stopPropagation();                               // nothing of the page's (arrows, letters, undo) acts on what is typed here
    var k = e.key, mod = e.metaKey || e.ctrlKey;
    if(mod && !e.altKey && !e.shiftKey && /^[biu]$/i.test(k)){ e.preventDefault(); cmd(k.toLowerCase() === 'b' ? 'bold' : k.toLowerCase() === 'i' ? 'italic' : 'underline'); return; }
    if(k === 'Tab' && !mod && !e.altKey && inList()){ e.preventDefault(); cmd(e.shiftKey ? 'outdent' : 'indent'); return; }
  }
  function onPaste(e){
    var d = e.clipboardData; if(!d) return;
    e.preventDefault();
    var html = d.getData('text/html'), txt = d.getData('text/plain');
    restore();
    try {
      if(html){ var h = sanitize(html); if(h){ document.execCommand('insertHTML', false, h); touch(); return; } }
      if(txt){ document.execCommand('insertText', false, txt); touch(); }
    } catch(x){}
  }

  /* ── Copy and Print ──────────────────────────────────────────────────── */
  function flash(t){ setState(t); setTimeout(function(){ setState(LAB.saved, true); }, 1400); }
  function doCopy(){
    flush();
    var h = sanitize(ed.innerHTML), box = document.createElement('div'); box.innerHTML = h; var t = plain(box);
    function legacy(){
      var sel = window.getSelection(), keep = lastRange;
      var r = document.createRange(); r.selectNodeContents(ed); sel.removeAllRanges(); sel.addRange(r);
      var ok = false; try { ok = document.execCommand('copy'); } catch(e){}
      sel.removeAllRanges(); if(keep){ try { sel.addRange(keep); } catch(e){} }
      if(ok) flash(LAB.copied);
    }
    try {
      if(navigator.clipboard && window.ClipboardItem && navigator.clipboard.write){
        navigator.clipboard.write([new ClipboardItem({'text/html': new Blob([h], {type:'text/html'}), 'text/plain': new Blob([t], {type:'text/plain'})})])
          .then(function(){ flash(LAB.copied); }, legacy);
        return;
      }
    } catch(e){}
    legacy();
  }
  function doPrint(){
    flush();
    var old = $('fw-print-host'); if(old) old.remove();
    var host = el('div', {id:'fw-print-host'});
    var tt = $('title-text'), head = el('div', {'class':'fw-ph'}); head.textContent = ((tt && tt.textContent) || document.title || '').trim() + ' — ' + LAB.fw;
    var body = el('div'); body.innerHTML = sanitize(ed.innerHTML);
    host.appendChild(head); host.appendChild(body); document.body.appendChild(host);
    var root = document.documentElement; root.classList.add('fw-printing');
    var done = function(){ root.classList.remove('fw-printing'); if(host.parentNode) host.remove(); window.removeEventListener('afterprint', done); };
    window.addEventListener('afterprint', done);
    setTimeout(function(){ try { window.print(); } catch(e){ done(); } }, 30);
  }

  /* ── the mode, the width, the phone keyboard ─────────────────────────── */
  function setMode(m, focus){
    MODE = m === 'fw' ? 'fw' : 'notes';
    if(!panel) return;
    if(MODE === 'fw' && panel.classList.contains('trash-mode')){ var hm = $('notes-home-btn'); if(hm) hm.click(); }   // leave the deleted list
    panel.classList.toggle('fw-mode', MODE === 'fw');
    Array.prototype.forEach.call(document.querySelectorAll('#fw-seg button'), function(b){ b.setAttribute('aria-selected', b.getAttribute('data-m') === MODE ? 'true' : 'false'); });
    var title = $('notes-header-title');
    if(title){
      if(MODE === 'fw'){ if(!title.hasAttribute('data-fw-was')) title.setAttribute('data-fw-was', title.textContent); title.textContent = LAB.fw; }
      else if(title.hasAttribute('data-fw-was')){ title.textContent = title.getAttribute('data-fw-was'); title.removeAttribute('data-fw-was'); }
    }
    if(MODE !== 'fw') flush(); else { remote(); words(); sync(); }
    saveUi(); layout(); flag();
    if(MODE === 'fw' && focus && !mobile()) setTimeout(function(){ try { ed.focus(); } catch(e){} }, 30);
  }
  function ratio(){                                     // the page is zoomed to fit the window: CSS px per screen px
    var r = panel && panel.getBoundingClientRect().width, c = panel && parseFloat(getComputedStyle(panel).width);
    return r > 0 && c > 0 ? c / r : 1;
  }
  function width(w, keep){                              // w in CSS px
    var max = Math.max(320, Math.min(900, window.innerWidth * ratio() - 260));
    W = Math.max(320, Math.min(max, Math.round(w)));
    document.documentElement.style.setProperty('--fw-w', W + 'px');
    if(!keep) saveUi();
    dock();
  }
  function flag(){ document.documentElement.classList.toggle('fw-open', !!(panel && MODE === 'fw' && panel.classList.contains('open') && !mobile())); dock(); }
  function dock(){                                      // desktop: how far the open panel reaches in from the right (CSS px); 0 when shut
    var r = document.documentElement, p = $('notes-panel'), open = !!(p && p.classList.contains('open')), d = 0;
    if(open && !mobile()){ d = MODE === 'fw' ? Math.min(W, Math.max(0, window.innerWidth * ratio() - 260)) : parseFloat(getComputedStyle(p).width) || 0; }
    r.classList.toggle('np-open', open); r.classList.toggle('np-docked', d > 0);
    r.style.setProperty('--np-dock', Math.round(d) + 'px');
    if(window._altoAlignInfo) window._altoAlignInfo();
  }
  function layout(){                                    // a phone's keyboard covers the page without resizing it: keep the box above it
    if(!panel || !mobile()) return;
    var v = window.visualViewport, on = !!v && MODE === 'fw' && panel.classList.contains('open');
    if(on && document.documentElement.classList.contains('rw')){     // the runway pins the panel top and bottom (runway.py): lift its floor instead
      var kb = Math.round(window.innerHeight - v.height - v.offsetTop);
      panel.style.setProperty('padding-bottom', (140 + (kb > 80 ? kb : 0)) + 'px', 'important');
    } else if(on){
      panel.style.setProperty('height', Math.round(v.height) + 'px', 'important'); panel.style.setProperty('top', Math.round(v.offsetTop) + 'px', 'important');
    } else { panel.style.removeProperty('height'); panel.style.removeProperty('top'); panel.style.removeProperty('padding-bottom'); }
  }
  function guard(){
    var f = window.toggleNotes;
    if(typeof f !== 'function' || f.__altoFw) return;
    var w = function(){ if(pinned() && !FORCE) return; return f.apply(this, arguments); };   // only the panel's own x closes Freewrite
    w.__altoFw = true; window.toggleNotes = w;
  }

  function build(){
    panel = $('notes-panel'); var hdr = $('notes-header'), foot = $('notes-footer');
    if(!panel || !hdr || !foot || $('fw-pane')) return false;
    var seg = el('div', {id:'fw-seg', role:'tablist', 'aria-label':'Notes mode'});
    [['notes', LAB.notes], ['fw', LAB.fw]].forEach(function(p){
      var b = el('button', {type:'button', role:'tab', 'data-m':p[0], 'aria-selected':'false'}); b.textContent = p[1];
      b.addEventListener('click', function(){ setMode(p[0], true); });
      seg.appendChild(b);
    });
    hdr.parentNode.insertBefore(seg, hdr.nextSibling);
    var S = function(d){ return '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">' + d + '</svg>'; };
    var tools = [
      ['bold', '<b>B</b>', LAB.bold], ['italic', '<i style="font-family:Georgia,serif">I</i>', LAB.italic], ['underline', '<u>U</u>', LAB.underline], ['strike', '<s>S</s>', LAB.strike], '|',
      ['h1', '<span class="fw-h">H1</span>', LAB.h1], ['h2', '<span class="fw-h">H2</span>', LAB.h2], '|',
      ['ul', S('<circle cx="3" cy="4" r=".9" fill="currentColor"/><circle cx="3" cy="8" r=".9" fill="currentColor"/><circle cx="3" cy="12" r=".9" fill="currentColor"/><path d="M6.5 4H14M6.5 8H14M6.5 12H14"/>'), LAB.ul],
      ['ol', S('<path d="M2 3.3l1-.6v3M2 9.3h2l-2 2.4h2.1M6.5 4H14M6.5 8.5H14M6.5 13H14"/>'), LAB.ol],
      ['outdent', S('<path d="M7 4h7M7 8h7M7 12h7M5 5.5L2.5 8 5 10.5"/>'), LAB.outdent],
      ['indent', S('<path d="M7 4h7M7 8h7M7 12h7M2.5 5.5L5 8l-2.5 2.5"/>'), LAB.indent], '|',
      ['clear', S('<path d="M3.5 3.5h8M7.5 3.5v6M2 13.5l12-11"/>'), LAB.clear]
    ];
    var bar = el('div', {id:'fw-tools', role:'toolbar', 'aria-label':'Formatting'});
    tools.forEach(function(t){
      if(t === '|'){ bar.appendChild(el('span', {'class':'fw-sep'})); return; }
      var b = el('button', {type:'button', 'data-fw':t[0], title:t[2], 'aria-label':t[2].replace(/ \(.*\)$/, '')}, t[1]);
      b.addEventListener('mousedown', function(e){ e.preventDefault(); });            // keep the caret where it is
      b.addEventListener('click', function(){
        var k = t[0];
        if(k === 'bold') cmd('bold'); else if(k === 'italic') cmd('italic'); else if(k === 'underline') cmd('underline'); else if(k === 'strike') cmd('strikeThrough');
        else if(k === 'h1' || k === 'h2') heading(k); else if(k === 'ul') cmd('insertUnorderedList'); else if(k === 'ol') cmd('insertOrderedList');
        else if(k === 'indent') cmd('indent'); else if(k === 'outdent') cmd('outdent'); else if(k === 'clear') clearFmt();
      });
      bar.appendChild(b);
    });
    ed = el('div', {id:'fw-editor', contenteditable:'true', role:'textbox', 'aria-multiline':'true', 'aria-label':LAB.fw, spellcheck:'true',
                    'data-ph':LAB.ph, autocapitalize:'sentences'});
    var foo = el('div', {id:'fw-foot'});
    var cnt = el('span', {id:'fw-count'}, '0 words'), st = el('span', {id:'fw-state', 'aria-live':'polite', 'class':'idle'}, LAB.saved);
    var cp = el('button', {type:'button', id:'fw-copy'}); cp.textContent = LAB.copy;
    var pr = el('button', {type:'button', id:'fw-print'}); pr.textContent = LAB.print;
    var rp = el('button', {type:'button', id:'fw-report', title:LAB.reportTip}); rp.textContent = LAB.report;
    cp.addEventListener('click', doCopy); pr.addEventListener('click', doPrint);
    rp.addEventListener('click', function(){ flush(); window._altoFwForce = true; try { if(typeof generateNotesReport === 'function') generateNotesReport(); } finally { setTimeout(function(){ window._altoFwForce = false; }, 0); } });
    foo.appendChild(cnt); foo.appendChild(st); foo.appendChild(el('span', {'class':'fw-grow'})); foo.appendChild(cp); foo.appendChild(pr); foo.appendChild(rp);
    var pane = el('div', {id:'fw-pane'}); pane.appendChild(bar); pane.appendChild(ed); pane.appendChild(foo);
    foot.parentNode.insertBefore(pane, foot);
    var rb = $('notes-report-btn');
    if(rb && rb.parentNode){
      var at = el('label', {id:'fw-attach'}), ck = el('input', {type:'checkbox', 'aria-label':LAB.attach});
      at.appendChild(ck); at.appendChild(document.createTextNode(LAB.attach + ' ')); at.appendChild(el('span', {id:'fw-attach-n', 'class':'fw-n'}, ''));
      ck.addEventListener('change', function(){ ATT = ck.checked; saveUi(); });
      rb.parentNode.insertBefore(at, rb);
    }
    var rz = el('div', {id:'fw-resize', role:'separator', 'aria-orientation':'vertical', 'aria-label':LAB.resize, title:LAB.resize, tabindex:'0'});
    panel.appendChild(rz);

    ed.addEventListener('input', function(e){ autoList(e); ensure(); touch(); sync(); });
    ed.addEventListener('keydown', onKey);
    ed.addEventListener('keyup', function(e){ e.stopPropagation(); sync(); });
    ed.addEventListener('keypress', function(e){ e.stopPropagation(); });
    ed.addEventListener('paste', onPaste);
    ed.addEventListener('drop', function(e){ e.preventDefault(); });                // nothing dragged in: it would carry its own markup
    ed.addEventListener('focusout', function(){ flush(); });
    ed.addEventListener('focus', function(){ ensure(); sync(); });
    ed.addEventListener('mouseup', function(e){ e.stopPropagation(); }); ed.addEventListener('touchend', function(e){ e.stopPropagation(); }, {passive:true});
    document.addEventListener('selectionchange', function(){
      var s = window.getSelection(); if(s && s.rangeCount && inEd(s.anchorNode)){ lastRange = s.getRangeAt(0).cloneRange(); sync(); }
    });
    // Width: drag the left edge (desktop).
    var drag = false;
    rz.addEventListener('pointerdown', function(e){ drag = true; panel.classList.add('fw-dragging'); try { rz.setPointerCapture(e.pointerId); } catch(x){} e.preventDefault(); });
    rz.addEventListener('pointermove', function(e){ if(drag) width((window.innerWidth - e.clientX) * ratio(), true); });
    function stop(){ if(!drag) return; drag = false; panel.classList.remove('fw-dragging'); saveUi(); }
    rz.addEventListener('pointerup', stop); rz.addEventListener('pointercancel', stop);
    rz.addEventListener('dblclick', function(){ width(DEF_W); });
    rz.addEventListener('keydown', function(e){ if(e.key === 'ArrowLeft'){ e.preventDefault(); width(W + 24); } else if(e.key === 'ArrowRight'){ e.preventDefault(); width(W - 24); } });
    width(W, true);
    return true;
  }

  function install(){
    if(!build()) return;
    guard();
    // The panel's own x is the one deliberate way out: it alone is let through the guard.
    ['click', 'touchend'].forEach(function(t){
      document.addEventListener(t, function(e){
        if(e.target && e.target.closest && e.target.closest('#notes-close')){ FORCE = true; setTimeout(function(){ FORCE = false; }, 0); }
      }, true);
    });
    new MutationObserver(function(){ saveUi(); layout(); flag(); if(panel.classList.contains('open') && MODE === 'fw'){ remote(); words(); } }).observe(panel, {attributes:true, attributeFilter:['class']});
    load(); setMode(MODE, false);
    window.addEventListener('storage', function(ev){ if(ev && ev.key === FKEY) remote(); });
    window.addEventListener('alto-fw-sync', remote);
    window.addEventListener('pagehide', flush); window.addEventListener('beforeunload', flush);
    document.addEventListener('visibilitychange', function(){ if(document.visibilityState === 'hidden') flush(); });
    if(window.visualViewport){ window.visualViewport.addEventListener('resize', layout); window.visualViewport.addEventListener('scroll', layout); }
    window.addEventListener('resize', function(){ width(W, true); layout(); });
    // Reopen where the writer left off.
    if(ui.open && MODE === 'fw') setTimeout(function(){ if(typeof notesOpen !== 'undefined' && !notesOpen && typeof toggleNotes === 'function'){ toggleNotes(); } layout(); }, 250);
  }
  window._altoFwReport = function(force){ return forReport(force || !!window._altoFwForce); };
  window._altoFw = {pinned: pinned, report: forReport, mode: function(){ return MODE; }, setMode: function(m){ setMode(m, false); }, flush: flush, sanitize: sanitize, plain: plain,
                    labels: LAB, keys: {FW: FKEY, UI: UKEY}};
  function boot(){ install(); setTimeout(guard, 900); setTimeout(guard, 3000); }
  if(document.readyState === 'complete') boot(); else window.addEventListener('load', boot);
})();
</script>"""


def freewrite(b) -> str:
    """FREEWRITE with this timeline's highlight storage key (the page's own
    `alto-hl-{tid}` text, which a share re-stamps like every other copy)."""
    from .blocks import ID_PATTERNS
    return FREEWRITE.replace("__ALTO_HL_KEY__", ID_PATTERNS["hl_key"].format(tid=b.timeline_id)) + "\n"
