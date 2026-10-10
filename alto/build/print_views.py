"""Printing a timeline: the page's three print views, and the link that asks for one.

The engine already prints the outline (its "Main timeline"), one detail page and
every detail page. This module adds what it lacks, in the page itself so that the
two ways in share one piece of code:

  * the notes panel's share dialog (its PRINT list), and
  * the homepage's Print... dialog, which opens the timeline with
    `#altoprint=outline|full|ink` and lets the page print itself.

`ink` is the timeline PICTURE (cards and lines) on white paper with no colour,
no glass, no shadows, always on LANDSCAPE sheets with narrow margins. Two ways
of drawing it:

  * an OUTLINE (a tree of units, sections, concepts and outcomes) is not cut
    out of its wide, mostly empty picture at all: it is re-flowed. Every card
    is made compact (small padding, tight lines, the cases as running chips),
    the cards are set down in outline order in a few columns per sheet, each
    child indented under its parent on a thin trunk line, and the columns are
    broken between sibling branches wherever they can be (a column that has to
    start inside a branch begins with a "continued" line naming it). The scale
    is the largest at which everything fits the number of sheets asked for
    (`sheets`, from the Print dialog or `&sheets=2` in the link; 0 = as few as
    read comfortably), so a two-sheet crib sheet is two sheets, whole, with no
    line running off one into the next. Links between branches that are not
    part of the tree are kept as "See also 4.b.3" on both cards;
  * any other timeline is a copy of the canvas placed in the document (so every
    card rule still applies) and stripped to black and grey, at the largest scale
    that reads: a picture that fits one sheet is one sheet, anything else is one
    continuous strip (tall pictures run down it, wide ones across it) cut in as
    few, as even pieces as it can, only where no card is, at the gap the fewest
    connector lines cross. Every piece keeps the same scale and the same offset,
    so a line that crosses a cut leaves one sheet and arrives on the next at the
    same place.

`full` (the outline, then every detail page in order) is staged by the engine
patch `print-views-engine` in engine_patches.py, which can see the engine's own
print builders; this file holds the picture and the link.

The hash is read without writing the word "location.hash" (single_file.py
rewrites every one of those to the shell's hand-over, and counts them): the
private shell hands the hash over in window.__altoQuery.hash and strips it from
the URL.
"""

PRINT_CSS = r"""<style id="alto-print-views">
  #alto-ink-host,#alto-print-msg{display:none;}
  .print-sheets{display:flex;align-items:center;gap:8px;margin-top:2px;font-size:12px;color:var(--muted,#888);}
  .print-sheets select{flex:1;min-width:0;padding:5px 7px;border-radius:8px;border:1px solid var(--border,#ccc);background:var(--surface,#fff);
    color:var(--text,#222);font:inherit;font-size:12px;}
  #alto-print-msg.on{display:block;position:fixed;left:50%;top:40%;transform:translate(-50%,-50%);z-index:9999;
    padding:14px 22px;border-radius:14px;background:var(--surface,#fff);color:var(--text,#222);
    border:1px solid var(--border,#ccc);box-shadow:0 10px 30px rgba(0,0,0,.25);font:14px/1.4 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}
  /* The outline sheets. The same rules on screen (where every card is measured, off to the side) and on paper. */
  #alto-ink-measure{position:absolute;left:-30000px;top:0;visibility:hidden;pointer-events:none;}
  html :is(#alto-ink-host,#alto-ink-measure) .ink-card{position:absolute !important;box-sizing:border-box !important;margin:0 !important;padding:5px 8px 6px !important;
    border:1px solid #555 !important;border-radius:6px !important;background:#fff !important;opacity:1 !important;
    transform:none !important;zoom:1 !important;height:auto !important;min-height:0 !important;max-height:none !important;
    max-width:none !important;overflow:visible !important;cursor:auto !important;transition:none !important;animation:none !important;
    box-shadow:none !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;}
  html :is(#alto-ink-host,#alto-ink-measure) .ink-card::before,html :is(#alto-ink-host,#alto-ink-measure) .ink-card::after{content:none !important;display:none !important;}
  html :is(#alto-ink-host,#alto-ink-measure) .ink-card.hub{border-width:2px !important;padding:6px 9px 7px !important;}
  html :is(#alto-ink-host,#alto-ink-measure) .ink-card .node-order{position:static !important;display:inline !important;margin:0 6px 0 0 !important;padding:0 !important;
    font:italic 10px/1.2 Georgia,serif !important;letter-spacing:.04em !important;opacity:1 !important;}
  html :is(#alto-ink-host,#alto-ink-measure) .ink-card .node-tag{display:inline !important;margin:0 !important;padding:0 !important;font-size:9px !important;
    line-height:1.2 !important;letter-spacing:.11em !important;}
  html :is(#alto-ink-host,#alto-ink-measure) .ink-card .node-title{display:block !important;margin:1px 0 2px !important;padding:0 !important;font-size:14px !important;
    line-height:1.2 !important;font-weight:700 !important;}
  html :is(#alto-ink-host,#alto-ink-measure) .ink-card.hub .node-title{font-size:15.5px !important;}
  html :is(#alto-ink-host,#alto-ink-measure) .ink-card .node-desc{display:block !important;margin:0 !important;padding:0 !important;font-size:11.5px !important;line-height:1.27 !important;}
  html :is(#alto-ink-host,#alto-ink-measure) .ink-card .node-footer{display:flex !important;flex-wrap:wrap !important;gap:3px !important;margin:4px 0 0 !important;padding:0 !important;
    align-items:flex-start !important;}
  html :is(#alto-ink-host,#alto-ink-measure) .ink-card .esym-btn,html :is(#alto-ink-host,#alto-ink-measure) .ink-card .ink-ent{display:inline-block !important;height:auto !important;width:auto !important;margin:0 !important;
    padding:0 4px !important;font-size:10px !important;line-height:1.35 !important;font-family:inherit !important;border:1px dashed #777 !important;
    border-radius:3px !important;white-space:normal !important;text-align:left !important;transform:none !important;opacity:1 !important;
    box-shadow:none !important;max-width:100% !important;overflow:visible !important;background:none !important;}
  html :is(#alto-ink-host,#alto-ink-measure) .ink-card .ink-ent{border-style:solid !important;}
  html :is(#alto-ink-host,#alto-ink-measure) .ink-card .footer-sep,html :is(#alto-ink-host,#alto-ink-measure) .ink-card svg{display:none !important;}
  html :is(#alto-ink-host,#alto-ink-measure) .ink-see{margin:3px 0 0 !important;font-size:9.5px !important;line-height:1.25 !important;font-style:italic !important;}
  html :is(#alto-ink-host,#alto-ink-measure) .ink-crumb{position:absolute !important;margin:0 !important;padding:0 !important;font-size:10px !important;line-height:16px !important;font-style:italic !important;font-family:inherit !important;
    white-space:nowrap !important;overflow:hidden !important;text-overflow:ellipsis !important;}
  @media print{
    #alto-print-msg{display:none !important;}
    /* the outline, then every detail page: one sheet break between the two */
    html.printing.print-full .print-ol-doc,html.printing.print-full .print-tl-doc{break-after:page;page-break-after:always;}
    html.printing.print-timeline.print-all #print-all{display:block !important;}
    /* the picture */
    html.printing.print-ink #canvas,html.printing.print-ink #detail-page,
    html.printing.print-ink #print-all,html.printing.print-ink #print-timeline-host{display:none !important;}
    html.printing.print-ink #alto-ink-host{display:block !important;}
    html.printing.print-ink,html.printing.print-ink body{min-height:0 !important;height:auto !important;}   /* 100vh body = a blank last sheet */
    html.printing.print-ink .ink-tile{position:relative;overflow:hidden;contain:size layout paint;break-after:page;page-break-after:always;margin:24px 0 0 24px;}
    html.printing.print-ink .ink-tile:last-child{break-after:auto;page-break-after:auto;}
    html.printing.print-ink .ink-tile .ink-in{position:absolute;transform-origin:0 0;}
    html.printing.print-ink #alto-ink-host *{color:#000 !important;background:none !important;background-image:none !important;
      box-shadow:none !important;text-shadow:none !important;filter:none !important;
      -webkit-backdrop-filter:none !important;backdrop-filter:none !important;mix-blend-mode:normal !important;
      border-color:#555 !important;outline-color:#555 !important;animation:none !important;transition:none !important;
      -webkit-text-fill-color:#000 !important;}
    html.printing.print-ink #alto-ink-host *::before,html.printing.print-ink #alto-ink-host *::after{background:none !important;
      background-image:none !important;box-shadow:none !important;filter:none !important;-webkit-backdrop-filter:none !important;
      backdrop-filter:none !important;border-color:#555 !important;color:#000 !important;animation:none !important;}
    html.printing.print-ink #alto-ink-host img,html.printing.print-ink #alto-ink-host canvas{filter:grayscale(1) contrast(1.1) !important;}
    html.printing.print-ink #alto-ink-host .ink-world .node{opacity:1 !important;}
    html.printing.print-ink #alto-ink-host .ink-world .node-card{background:#fff !important;border:1px solid #333 !important;
      border-radius:10px !important;}
    html.printing.print-ink #alto-ink-host .ink-world .node-tag,html.printing.print-ink #alto-ink-host .ink-world .node-order,
    html.printing.print-ink #alto-ink-host .ink-world .node-desc{color:#333 !important;-webkit-text-fill-color:#333 !important;}
    html.printing.print-ink #alto-ink-host .ink-world .node-title{font-weight:700 !important;}
    html.printing.print-ink #alto-ink-host .ink-world button{background:#fff !important;border:1px solid #777 !important;}
    html.printing.print-ink #alto-ink-host .ink-world .phase-label{background:#fff !important;border:1px solid #333 !important;border-radius:8px;}
    /* the page's fit-to-window zoom is for the screen: on paper a CSS px is a CSS px. The page also sizes <body> as 100vw / zoom,
       which on a sheet is wider than the sheet, and the browser then shrinks the whole print to fit that width */
    html.printing.print-ink{zoom:1 !important;--alto-zoom:1 !important;}
    html.printing.print-ink.print-ink:not(.mobile) body{width:auto !important;height:auto !important;min-height:0 !important;}
    html.printing.print-ink #alto-ink-host .ink-card .node-desc,html.printing.print-ink #alto-ink-host .ink-card .node-tag,
    html.printing.print-ink #alto-ink-host .ink-card .node-order,html.printing.print-ink #alto-ink-host .ink-see,
    html.printing.print-ink #alto-ink-host .ink-crumb{color:#333 !important;-webkit-text-fill-color:#333 !important;}
    html.printing.print-ink #alto-ink-host .ink-card .node-title{color:#000 !important;-webkit-text-fill-color:#000 !important;}
    html.printing.print-ink #alto-ink-host svg.ink-lines{display:block !important;}
    html.printing.print-ink #alto-ink-host svg.ink-lines line{stroke:#555 !important;fill:none !important;}
  }
</style>
<div id="alto-print-msg" role="status">Preparing your print…</div>
"""

PRINT_JS = r"""<script id="alto-print-views-js">
(function(){
  if(window._altoInkStage) return;
  // Landscape sheets only. What a sheet always holds in CSS px inside a quarter-inch margin on Letter or A4 (whichever is smaller each way).
  var LAND = {w:1004, h:741, name:'landscape'};
  var MIN_ONE = 0.5, MIN_READ = 0.42;                                                      // below these a sheet is too small to read

  function pageStyle(orient){
    var s = document.getElementById('alto-ink-page');
    if(s) s.remove();
    // the engine's own print style (@page margin 11mm) sits in the body: this one goes after it, so that it is the one that counts
    s = document.createElement('style'); s.id = 'alto-ink-page'; document.body.appendChild(s);
    s.textContent = '@media print{@page{size:' + orient + ';margin:0;}}';      // margin 0: the browser prints no header or footer; the tile's own margin is the quarter inch
  }

  // Where to cut a run of length `total` into pieces of at most `cap`, as few and as even as it can, never
  // through a box (`spans`: [start, end] of every card along this axis) and at the gap the fewest lines
  // cross (`segs`: [a, b] of every line segment along this axis; one that straddles a cut crosses it).
  // Pure, so it can be tested. Returns [[0, c1], [c1, c2], ... [cn, total]].
  function cuts(total, cap, spans, segs){
    if(total <= cap + 1) return [[0, total]];
    var out = [], y = 0;
    var cand = [];
    spans.forEach(function(b){ cand.push(b[0] - 8, b[1] + 8); });
    function crossings(c){
      var k = 0;
      for(var i = 0; i < segs.length; i++){ var a = segs[i][0], b = segs[i][1]; if((a < c && b >= c) || (b < c && a >= c)) k++; }
      return k;
    }
    function clear(c){
      for(var i = 0; i < spans.length; i++) if(spans[i][0] < c && c < spans[i][1]) return false;
      return true;
    }
    while(y < total - 1){
      var left = Math.ceil((total - y) / cap - 1e-6), ideal = y + (total - y) / left;     // an even share of what is left
      var limit = Math.min(y + cap, total);
      if(limit >= total - 1){ out.push([y, total]); y = total; break; }
      var best = -1, bestCost = 1e18;
      cand.forEach(function(c){
        if(c <= y + cap * 0.55 || c > limit || !clear(c)) return;
        // a line crossed costs one; a third of a sheet left unused costs three; running past the even share costs a little
        var cost = crossings(c) + 9 * (limit - c) / cap + 2 * Math.abs(c - ideal) / cap;
        if(cost < bestCost){ bestCost = cost; best = c; }
      });
      var end = best > 0 ? best : limit;                              // no clean gap: the cut falls at the sheet's edge
      out.push([y, end]); y = end;
    }
    if(y < total - 1) out.push([y, total]);
    return out;
  }
  window._altoInkCuts = cuts;

  // Which sheet, what scale, and where the cuts fall. Pure, so it can be tested.
  // boxes: [{x,y,w,h}] of every card; segs: optional [[x0,y0,x1,y1]] pieces of the connector lines.
  window._altoInkPlan = function(w, h, boxes, segs, maxSheets){
    var o = LAND, s, cols, rows, colCuts;
    segs = segs || [];
    var s1 = Math.min(1, o.w / w, o.h / h);
    if(s1 >= MIN_ONE){ s = s1; rows = [[0, h]]; colCuts = [[0, w]]; }
    else if(maxSheets > 0){
      // a limit was asked for: the largest scale at which the cut picture fits in that many sheets, however small
      var hi2 = Math.min(1, Math.max(o.w / w, o.h / h));
      for(s = hi2; ; s *= 0.98){
        var pw2 = o.w / s, ph2 = o.h / s;
        colCuts = cuts(w, pw2, boxes.map(function(b){ return [b.x, b.x + b.w]; }), segs.map(function(g){ return [g[0], g[2]]; }));
        rows = cuts(h, ph2, boxes.map(function(b){ return [b.y, b.y + b.h]; }), segs.map(function(g){ return [g[1], g[3]]; }));
        if(colCuts.length * rows.length <= maxSheets || s <= 0.05) break;
      }
    }
    else {
      // one continuous strip. The largest useful scale is the one that makes the picture as wide, or as tall, as a sheet
      // (never past life size); within a legible range (down to 60% of that, never below MIN_READ) take the largest scale
      // that needs the fewest sheets, so a long thin picture is not spread over more sheets than it has to be.
      var hi = Math.min(1, Math.max(o.w / w, o.h / h)), lo = Math.max(MIN_READ, Math.min(hi, 0.6)), least = 1e9;
      hi = Math.max(hi, MIN_READ); s = hi;
      for(var t = hi; t >= lo - 1e-9; t -= 0.005){
        var np = Math.ceil(w * t / o.w - 1e-6) * Math.ceil(h * t / o.h - 1e-6);
        if(np < least){ least = np; s = t; }
      }
      var cap = 40;                                                   // never an unbounded stack of sheets
      for(var guard = 0; guard < 40; guard++){
        var pw = o.w / s, ph = o.h / s;
        colCuts = cuts(w, pw, boxes.map(function(b){ return [b.x, b.x + b.w]; }), segs.map(function(g){ return [g[0], g[2]]; }));
        rows = cuts(h, ph, boxes.map(function(b){ return [b.y, b.y + b.h]; }), segs.map(function(g){ return [g[1], g[3]]; }));
        if(colCuts.length * rows.length <= cap || s <= 0.1) break;
        s *= 0.9;
      }
    }
    cols = colCuts.length;
    return {orient:o.name, w:o.w, h:o.h, s:s, cols:cols, colCuts:colCuts, rows:rows};
  };


  // ── Outline sheets ─────────────────────────────────────────────────────────
  // IND: how far a child sits in under its parent; GAP: between cards; TRUNK: where a parent's line runs (from its left edge);
  // STUB: how far down a child its line meets it; COLGAP: between columns on a sheet (print px); HDR: the "continued" line.
  var FL = {IND:16, GAP:7, TRUNK:6, STUB:11, COLGAP:20, HDR:16};
  var SHEET_W = LAND.w, SHEET_H = LAND.h;

  // Break cards, in order, into exactly K columns of at most H (layout px), never through a card, preferring breaks between
  // whole branches (a unit, then a section...) and never right after a parent so that it is left alone at the foot of a
  // column, and an even fill. h: heights; d: outline depths; first[i]: card i is the first child of the card before it;
  // F: {GAP, HDR}. A column that starts inside a branch (d > 0) also holds the "continued" line. Pure, so it can be
  // tested. Returns [[a, b), ...] (b exclusive) or null when it cannot be done.
  function packColumns(h, d, first, K, H, F){
    var n = h.length; if(!n || K < 1 || K > n) return null;
    var pre = [0], i, j, a, b;
    for(i = 0; i < n; i++) pre.push(pre[i] + h[i]);
    function used(a, b){ return pre[b] - pre[a] + F.GAP * (b - a - 1) + (d[a] > 0 ? F.HDR + F.GAP : 0); }
    function brk(a){ if(!a) return 0; var c = d[a] <= 0 ? -0.05 : d[a] === 1 ? 0.01 : d[a] === 2 ? 0.07 : 0.14; return first[a] ? c + 0.6 : c; }
    var INF = 1e18, f = [], from = [];
    for(j = 0; j <= K; j++){ f.push([]); from.push([]); for(i = 0; i <= n; i++){ f[j].push(INF); from[j].push(-1); } }
    f[0][0] = 0;
    for(j = 1; j <= K; j++) for(b = j; b <= n; b++) for(a = b - 1; a >= j - 1; a--){
      if(f[j-1][a] >= INF) continue;
      var u = used(a, b); if(u > H) continue;
      var lo = (H - u) / H, c = f[j-1][a] + lo * lo + brk(a);
      if(c < f[j][b]){ f[j][b] = c; from[j][b] = a; }
    }
    if(f[K][n] >= INF) return null;
    var out = [], e = n;
    for(j = K; j >= 1; j--){ var st = from[j][e]; out.unshift([st, e]); e = st; }
    return out;
  }
  window._altoInkPack = packColumns;

  function wantSheets(){
    var v = window._altoInkSheets;
    if(v == null){ try{ v = +localStorage.getItem('alto-ink-sheets'); }catch(e){ v = 0; } }
    v = Math.round(+v || 0);
    return v > 0 ? Math.min(v, 8) : 0;
  }

  // the select in the notes panel's PRINT list, put under the ink-saver button whenever the dialog is opened (the homepage's
  // own dialog has its own copy of this)
  function sheetsSelect(){
    var ink = document.querySelector('#share-dialog .print-opt[data-print="ink"]'); if(!ink) return;
    var sel = document.getElementById('ink-sheets'), v = wantSheets();
    if(!sel){
      var o = [[0, 'as few sheets as still read'], [1, '1 sheet'], [2, '2 sheets'], [3, '3 sheets'], [4, '4 sheets'], [6, '6 sheets']];
      var lab = document.createElement('label'); lab.className = 'print-sheets';
      lab.innerHTML = 'Ink-saver: fit to <select id="ink-sheets">' + o.map(function(x){ return '<option value="' + x[0] + '">' + x[1] + '</option>'; }).join('') + '</select>';
      ink.parentNode.insertBefore(lab, ink.nextSibling);
      sel = lab.querySelector('select');
    }
    sel.value = String(v);
    if(sel.value !== String(v)) sel.value = '0';
  }
  document.addEventListener('change', function(e){
    var t = e.target; if(!t || t.id !== 'ink-sheets') return;
    window._altoInkSheets = +t.value || 0;
    try{ localStorage.setItem('alto-ink-sheets', String(window._altoInkSheets)); }catch(err){}
  }, true);
  (function hook(){
    var sh = window.AltoShare;
    if(sh && typeof sh.open === 'function' && !sh._inkSheets){
      var open0 = sh.open; sh._inkSheets = 1;
      sh.open = function(){ var r = open0.apply(this, arguments); try{ sheetsSelect(); }catch(e){} return r; };
    }
    sheetsSelect();
  })();

  // Auto: as few sheets as still read (the scale at which the description text is about 4.3pt on paper; a crib sheet's own limit).
  // SLACK: the scale the sheets are drawn at, of the largest that fits.
  var AUTO_SCALE = 0.5, SLACK = 0.975;

  // The outline as compact sheets. Returns false when this page is not an outline tree (the picture is drawn instead).
  function flowStage(){
    var O = window._ALTO_OUTLINE;
    if(!O || !O.kids || typeof NODES === 'undefined' || !NODES.length) return false;
    var par = O.parent || {}, kids = O.kids || {}, num = O.num || {}, byId = {}, items = [], seen = {};
    NODES.forEach(function(n){ byId[n.id] = n; });
    function walk(id, dep){
      if(!byId[id] || seen[id]) return;
      seen[id] = 1; items.push({id:id, d:dep, p:par[id] || ''});
      (kids[id] || []).forEach(function(k){ walk(k, dep + 1); });
    }
    NODES.forEach(function(n){ if(!par[n.id]) walk(n.id, 0); });
    if(items.length !== NODES.length) return false;
    var idx = {}; items.forEach(function(it, i){ idx[it.id] = i; });

    // links that are not parent -> child, kept as "See also"
    var see = {};
    var tree = {}; items.forEach(function(it){ if(it.p) tree[it.p + '|' + it.id] = 1; });
    document.querySelectorAll('#world svg [data-edge]').forEach(function(e){
      var v = (e.getAttribute('data-edge') || '').split('|');
      if(v.length !== 2 || tree[v[0] + '|' + v[1]] || tree[v[1] + '|' + v[0]] || idx[v[0]] == null || idx[v[1]] == null) return;
      (see[v[0]] = see[v[0]] || {})[v[1]] = 1; (see[v[1]] = see[v[1]] || {})[v[0]] = 1;
    });

    // one compact copy of every card
    for(var i = 0; i < items.length; i++){
      var el = document.getElementById('node-' + items[i].id), card = el && el.querySelector('.node-card');
      if(!card) return false;
      var cl = card.cloneNode(true);
      cl.removeAttribute('id'); cl.removeAttribute('style');
      cl.className = 'node-card ink-card' + (items[i].d === 0 ? ' hub' : '');
      cl.querySelectorAll('[id]').forEach(function(e){ e.removeAttribute('id'); });
      cl.querySelectorAll('[class*="aed-"], [class*="alto-edit"], .alto-fshadow, .node-unit, .era-badge, .weight-badge').forEach(function(e){ e.remove(); });
      cl.querySelectorAll('.csym-btn, .tsym-btn').forEach(function(b){
        var t = b.getAttribute('title') || '';
        if(!t){ b.remove(); return; }
        var sp = document.createElement('span'); sp.className = 'ink-ent'; sp.textContent = t; b.parentNode.replaceChild(sp, b);
      });
      cl.querySelectorAll('button').forEach(function(b){ b.removeAttribute('title'); b.removeAttribute('onclick'); });
      var te = cl.querySelector('.node-title');
      items[i].title = te ? te.textContent.replace(/\s+/g, ' ').trim() : '';
      var refs = Object.keys(see[items[i].id] || {}).sort(function(a, b){ return idx[a] - idx[b]; })
        .map(function(k){ return num[k] || ''; }).filter(Boolean);
      if(refs.length){
        var sd = document.createElement('div'); sd.className = 'ink-see'; sd.textContent = 'See also ' + refs.join(', ');
        cl.appendChild(sd);
      }
      items[i].el = cl;
    }
    var n = items.length, d = items.map(function(it){ return it.d; });
    var first = items.map(function(it, i){ return i > 0 && it.p && items[i-1].id === it.p ? 1 : 0; });

    // measure them off to the side, at the sheet's own pixel size (the page's fit-to-window zoom is for the screen)
    var meas = document.createElement('div'); meas.id = 'alto-ink-measure'; meas.className = 'ink-flow';
    items.forEach(function(it){ meas.appendChild(it.el); });
    document.body.appendChild(meas);
    var root = document.documentElement, z0 = root.style.getPropertyValue('zoom'), zp = root.style.getPropertyPriority('zoom');
    root.style.setProperty('zoom', '1', 'important');
    var result = null;
    try{
      var heightsAt = function(Wl){
        items.forEach(function(it){ it.el.style.width = (Wl - FL.IND * it.d) + 'px'; });
        return items.map(function(it){ return it.el.getBoundingClientRect().height; });
      };
      var bestFor = function(sheets){
        var best = null;
        for(var C = 1; C <= 5; C++){
          var K = C * sheets; if(K > n) continue;
          var Wp = (SHEET_W - (C - 1) * FL.COLGAP) / C;
          var tryS = function(s){
            var Wl = Wp / s, h = heightsAt(Wl), cols = packColumns(h, d, first, K, SHEET_H / s, FL);
            return cols ? {s:s, C:C, Wl:Wl, h:h, cols:cols, sheets:sheets} : null;
          };
          var r = tryS(1);
          if(!r){
            var lo = 0.2, hi = 1, got = tryS(lo);
            if(!got) continue;
            for(var it2 = 0; it2 < 11; it2++){
              var mid = (lo + hi) / 2, g = tryS(mid);
              if(g){ lo = mid; got = g; } else hi = mid;
            }
            r = got;
          }
          if(!best || r.s > best.s + 1e-9) best = r;
        }
        return best;
      };
      var want = wantSheets();
      if(want){ result = bestFor(want); }
      else for(var sh = 1; sh <= 8; sh++){
        var rr = bestFor(sh);
        if(rr){ result = rr; if(rr.s >= AUTO_SCALE) break; }
      }
      if(result){                                                      // a little under the limit, so the breaks can fall where they should
        var fin = null, sl = SLACK;
        for(var tries = 0; tries < 6 && !fin; tries++, sl = 1 - (1 - sl) / 2){
          var s2 = result.s * sl, Wp2 = (SHEET_W - (result.C - 1) * FL.COLGAP) / result.C, Wl2 = Wp2 / s2, h2 = heightsAt(Wl2);
          var cols2 = packColumns(h2, d, first, result.C * result.sheets, SHEET_H / s2, FL);
          if(cols2) fin = {s:s2, C:result.C, Wl:Wl2, h:h2, cols:cols2, sheets:result.sheets};
        }
        if(fin) result = fin; else result.h = heightsAt(result.Wl);
      }
    } finally {
      if(z0) root.style.setProperty('zoom', z0, zp); else root.style.removeProperty('zoom');
    }
    if(!result){ meas.remove(); return false; }

    // lay the columns down
    var s = result.s, C = result.C, Wl = result.Wl, Hl = SHEET_H / s, gapL = FL.COLGAP / s, h = result.h;
    var host = document.createElement('div'); host.id = 'alto-ink-host'; host.className = 'ink-flow';
    var NS = 'http://www.w3.org/2000/svg', placed = {}, k = 0;
    for(var sheet = 0; sheet < result.sheets; sheet++){
      var tile = document.createElement('div'); tile.className = 'ink-tile';
      tile.style.cssText = 'width:' + SHEET_W + 'px;height:' + SHEET_H + 'px;';
      var inner = document.createElement('div'); inner.className = 'ink-in';
      var innerW = C * Wl + (C - 1) * gapL;
      inner.style.cssText = 'left:0;top:0;width:' + innerW + 'px;height:' + Hl + 'px;transform:scale(' + s + ');';
      var svg = document.createElementNS(NS, 'svg'); svg.setAttribute('class', 'ink-lines');
      svg.setAttribute('width', innerW); svg.setAttribute('height', Hl);
      svg.setAttribute('style', 'position:absolute;left:0;top:0;overflow:visible;');
      inner.appendChild(svg);
      var line = function(x1, y1, x2, y2){
        var l = document.createElementNS(NS, 'line');
        l.setAttribute('x1', x1); l.setAttribute('y1', y1); l.setAttribute('x2', x2); l.setAttribute('y2', y2);
        l.setAttribute('stroke', '#555'); l.setAttribute('stroke-width', 1.25); svg.appendChild(l);
      };
      for(var c = 0; c < C && k < result.cols.length; c++, k++){
        var a = result.cols[k][0], b = result.cols[k][1], x0 = c * (Wl + gapL), y = 0;
        if(d[a] > 0){                                                   // this column starts inside a branch: say which
          var chain = [], q = items[a].p;
          while(q){ chain.unshift((num[q] ? num[q] + ' ' : '') + items[idx[q]].title); q = items[idx[q]].p; }
          var cr = document.createElement('div'); cr.className = 'ink-crumb';
          cr.textContent = chain.join('  ›  ') + '  (continued)';
          cr.style.cssText = 'left:' + x0 + 'px;top:0;width:' + Wl + 'px;height:' + FL.HDR + 'px;';
          inner.appendChild(cr); y = FL.HDR + FL.GAP;
        }
        var top0 = y, here = {}, stubs = {};
        for(var i2 = a; i2 < b; i2++){
          var it = items[i2], left = x0 + FL.IND * it.d, w = Wl - FL.IND * it.d;
          it.el.style.cssText = 'left:' + left + 'px;top:' + y + 'px;width:' + w + 'px;';
          inner.appendChild(it.el);
          here[it.id] = {l:left, t:y, h:h[i2]};
          if(it.p){ var sy = y + Math.min(FL.STUB, h[i2] / 2); (stubs[it.p] = stubs[it.p] || []).push([left, sy]); }
          y += h[i2] + FL.GAP;
        }
        Object.keys(stubs).forEach(function(pid){
          var pl = x0 + FL.IND * items[idx[pid]].d, tx = pl + FL.TRUNK, pos = here[pid];
          var ty = pos ? pos.t + pos.h : top0, by = Math.max.apply(null, stubs[pid].map(function(v){ return v[1]; }));
          line(tx, ty, tx, by);
          stubs[pid].forEach(function(v){ line(tx, v[1], v[0], v[1]); });
        });
      }
      tile.appendChild(inner); host.appendChild(tile);
    }
    meas.remove();
    document.body.appendChild(host);
    pageStyle('landscape');
    window._altoInkLast = {orient:'landscape', flow:true, w:SHEET_W, h:SHEET_H, s:s, cols:C, sheets:result.sheets, breaks:result.cols};
    return true;
  }

  var inkPrev = null;
  window._altoInkUnstage = function(){
    var h = document.getElementById('alto-ink-host'); if(h) h.remove();
    var ms = document.getElementById('alto-ink-measure'); if(ms) ms.remove();
    var p = document.getElementById('alto-ink-page'); if(p) p.remove();
    if(inkPrev){
      var pv = inkPrev; inkPrev = null;
      try{ if(typeof window.showDetail === 'function') window.showDetail(pv[0], pv[1]); }catch(e){}
    }
  };

  // Stage the picture. Returns false when this page has no canvas to draw.
  window._altoInkStage = function(){
    window._altoInkUnstage();
    var world = document.getElementById('world');
    if(!world) return false;
    if(window._currentDetailId && typeof window.showTimeline === 'function'){
      inkPrev = [window._currentDetailType, window._currentDetailId];
      try{ window.showTimeline(); }catch(e){}
    }
    try{ if(flowStage()) return true; }catch(e){ var ms2 = document.getElementById('alto-ink-measure'); if(ms2) ms2.remove(); }
    var wr = world.getBoundingClientRect();
    var k = (world.offsetWidth ? wr.width / world.offsetWidth : 1) || 1;   // desktop zoom: layout px = rect px / k
    function box(el){
      var r = el.getBoundingClientRect();
      return (r.width > 0 && r.height > 0) ? {x:(r.left - wr.left) / k, y:(r.top - wr.top) / k, w:r.width / k, h:r.height / k} : null;
    }
    var boxes = [], X0 = 1e9, Y0 = 1e9, X1 = -1e9, Y1 = -1e9;
    world.querySelectorAll('.node, .phase-label').forEach(function(el){
      var b = box(el); if(!b) return;
      boxes.push(b);
      X0 = Math.min(X0, b.x); Y0 = Math.min(Y0, b.y); X1 = Math.max(X1, b.x + b.w); Y1 = Math.max(Y1, b.y + b.h);
    });
    if(!boxes.length) return false;
    X0 = Math.max(0, Math.floor(X0 - 16)); Y0 = Math.max(0, Math.floor(Y0 - 16));
    X1 = Math.ceil(X1 + 16); Y1 = Math.ceil(Y1 + 16);
    var W = X1 - X0, H = Y1 - Y0;
    boxes.forEach(function(b){ b.x -= X0; b.y -= Y0; });

    // The connector lines, as short straight pieces in the picture's own coordinates, so the cuts can keep clear of them.
    var segs = [];
    try{
      var paths = [], budget = 0;
      world.querySelectorAll('svg path, svg line, svg polyline').forEach(function(el){
        if(el.closest('defs, mask, clipPath, marker')) return;
        var cs = getComputedStyle(el);
        if(cs.stroke === 'none' || cs.fill !== 'none' && cs.fill !== 'rgba(0, 0, 0, 0)') return;
        var sm = /rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(cs.stroke);
        if(sm && (+sm[1] + +sm[2] + +sm[3]) / 3 > 190) return;                // the thin highlight laid over each line
        if(typeof el.getTotalLength !== 'function') return;
        var len = 0; try{ len = el.getTotalLength(); }catch(e){}
        if(len > 0){ paths.push([el, len]); budget += len; }
      });
      var step = Math.max(12, budget / 12000);                                 // at most about twelve thousand pieces
      paths.forEach(function(pl){
        var el = pl[0], len = pl[1], m = el.getScreenCTM(), svg = el.ownerSVGElement; if(!m || !svg) return;
        var prev = null;
        for(var d = 0; d <= len + 0.01; d += step){
          var pt = svg.createSVGPoint(); var q = el.getPointAtLength(Math.min(d, len)); pt.x = q.x; pt.y = q.y;
          var sp = pt.matrixTransform(m), cur = [(sp.x - wr.left) / k - X0, (sp.y - wr.top) / k - Y0];
          if(prev) segs.push([prev[0], prev[1], cur[0], cur[1]]);
          prev = cur;
        }
      });
    }catch(e){ segs = []; }
    var plan = window._altoInkPlan(W, H, boxes, segs, wantSheets());

    // One grey copy of the canvas. SVG paint comes from the LIVE computed style
    // (theme and state decide it, not an attribute) and is turned to grey; the
    // card mask in <defs> is left alone, it is what keeps lines out of cards.
    var proto = world.cloneNode(true);
    var live = world.querySelectorAll('svg, svg *'), copy = proto.querySelectorAll('svg, svg *');
    for(var i = 0; i < live.length && i < copy.length; i++){
      var tag = live[i].tagName.toLowerCase();
      if(!/^(path|line|rect|circle|ellipse|polyline|polygon|text|tspan|use)$/.test(tag)) continue;
      if(live[i].closest('defs, mask, clipPath, marker')) continue;
      var cs = getComputedStyle(live[i]);
      // a line is drawn as a dark stroke with a thin white highlight over it: keep the dark one, thin
      var sm = /rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(cs.stroke);
      if(sm && (+sm[1] + +sm[2] + +sm[3]) / 3 > 190 && cs.fill === 'none'){ copy[i].style.setProperty('display', 'none', 'important'); continue; }
      copy[i].style.setProperty('fill', cs.fill === 'none' ? 'none' : '#000', 'important');
      copy[i].style.setProperty('stroke', cs.stroke === 'none' ? 'none' : '#555', 'important');
      if(cs.stroke !== 'none'){ copy[i].style.setProperty('stroke-width', Math.min(parseFloat(cs.strokeWidth) || 1.5, 1.6) + 'px', 'important'); copy[i].style.setProperty('stroke-opacity', '1', 'important'); }
      copy[i].style.setProperty('filter', 'none', 'important');
      copy[i].style.setProperty('opacity', '1', 'important');
    }
    proto.querySelectorAll('#glass-slab, .phase-band, .unit-bar, .alto-fshadow, [class*="aed-"], [class*="alto-edit"]').forEach(function(e){ e.remove(); });
    proto.classList.add('ink-world');
    proto.style.cssText += ';position:relative;width:' + world.offsetWidth + 'px;height:' + world.offsetHeight + 'px;transform:none;margin:0;';

    // Every piece: the same scale, the same top-left origin on the sheet (a lone column is centred), the piece's own window
    // onto the picture. Pieces of one picture therefore line up edge to edge.
    var host = document.createElement('div'); host.id = 'alto-ink-host';
    var offX = plan.cols === 1 ? Math.max(0, (plan.w - W * plan.s) / 2) : 0;
    var n = 0;
    plan.rows.forEach(function(row){
      plan.colCuts.forEach(function(col){
        var tile = document.createElement('div'); tile.className = 'ink-tile';
        tile.style.cssText = 'width:' + Math.min(plan.w, Math.ceil((col[1] - col[0]) * plan.s) + 1) + 'px;height:' +
          Math.min(plan.h, Math.ceil((row[1] - row[0]) * plan.s) + 1) + 'px;';
        var inner = document.createElement('div'); inner.className = 'ink-in';
        inner.style.cssText = 'left:' + offX + 'px;top:0;width:' + world.offsetWidth + 'px;height:' + world.offsetHeight + 'px;' +
          'transform:scale(' + plan.s + ') translate(' + (-(X0 + col[0])) + 'px,' + (-(Y0 + row[0])) + 'px);';
        var cl = proto.cloneNode(true);
        // ids inside the svg (the card mask) must be unique per copy, with their references
        var map = {};
        cl.querySelectorAll('svg [id]').forEach(function(e){ map[e.id] = e.id + '-ink' + n; e.id = map[e.id]; });
        if(Object.keys(map).length) cl.querySelectorAll('svg, svg *').forEach(function(e){
          Array.prototype.slice.call(e.attributes).forEach(function(a){
            if(a.value.indexOf('url(#') < 0) return;
            e.setAttribute(a.name, a.value.replace(/url\(#([^)]+)\)/g, function(m, id){ return map[id] ? 'url(#' + map[id] + ')' : m; }));
          });
        });
        n++;
        inner.appendChild(cl); tile.appendChild(inner); host.appendChild(tile);
      });
    });
    document.body.appendChild(host);
    pageStyle(plan.orient);
    window._altoInkLast = plan;
    return true;
  };

  // #altoprint=outline|full|ink: the homepage asks the page to print itself.
  function hashNow(){
    try{ return (window.__altoQuery && window.__altoQuery.hash) || location['hash'] || ''; }catch(e){ return ''; }
  }
  var m = /[#&]altoprint=(outline|full|ink)\b/.exec(hashNow());
  if(!m) return;
  var ms = /[#&]sheets=(\d+)/.exec(hashNow());
  if(ms) window._altoInkSheets = +ms[1];                          // how many sheets the ink-saver print may use (0 = as few as read)
  var MODE = {outline:'timeline', full:'full', ink:'ink'}[m[1]];
  try{ history.replaceState(null, '', location.pathname + location.search); }catch(e){}   // a reload must not print again
  var msg = document.getElementById('alto-print-msg');
  function note(on){ if(msg) msg.classList.toggle('on', !!on); }
  window.addEventListener('afterprint', function(){
    note(false);
    if(window.opener){ setTimeout(function(){ try{ window.close(); }catch(e){} }, 250); }     // the tab the homepage opened for this
  });
  var tries = 0, lastSig = '';
  (function wait(){
    var w = document.getElementById('world');
    var ready = document.readyState === 'complete' && typeof window.altoPrint === 'function' && w &&
                w.querySelectorAll('.node').length > 0;
    var sig = ready ? (w.offsetHeight + ':' + w.querySelectorAll('.node').length) : '';
    if((ready && sig === lastSig) || ++tries > 80){
      var go = function(){ note(false); try{ window.altoPrint(MODE); }catch(e){} };
      (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(function(){ setTimeout(go, 300); });
      return;
    }
    lastSig = sig; note(true);
    setTimeout(wait, 150);
  })();
})();
</script>"""


def print_views() -> str:
    return PRINT_CSS + PRINT_JS + "\n"
