"""Printing a timeline: the page's three print views, and the link that asks for one.

The engine already prints the outline (its "Main timeline"), one detail page and
every detail page. This module adds what it lacks, in the page itself so that the
two ways in share one piece of code:

  * the notes panel's share dialog (its PRINT list), and
  * the homepage's Print... dialog, which opens the timeline with
    `#altoprint=outline|full|ink` and lets the page print itself.

`ink` is the timeline PICTURE (cards and lines) on white paper with no colour,
no glass, no shadows: a copy of the canvas placed in the document (so every card
rule still applies) and then stripped to black and grey. It always prints on
LANDSCAPE sheets with narrow margins, at the largest scale that reads: a picture
that fits one sheet is one sheet, anything else is laid out as one continuous
strip (tall pictures run down it, wide ones across it) and cut in as few, as
even pieces as it can, only where no card is, at the gap the fewest connector
lines cross. Every piece keeps the same scale and the same offset, so a line
that crosses a cut leaves one sheet and arrives on the next at the same place.

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
  #alto-print-msg.on{display:block;position:fixed;left:50%;top:40%;transform:translate(-50%,-50%);z-index:9999;
    padding:14px 22px;border-radius:14px;background:var(--surface,#fff);color:var(--text,#222);
    border:1px solid var(--border,#ccc);box-shadow:0 10px 30px rgba(0,0,0,.25);font:14px/1.4 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}
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
    html.printing.print-ink .ink-tile{position:relative;overflow:hidden;contain:size layout paint;break-after:page;page-break-after:always;}
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
  }
</style>
<div id="alto-print-msg" role="status">Preparing your print…</div>
"""

PRINT_JS = r"""<script id="alto-print-views-js">
(function(){
  if(window._altoInkStage) return;
  // Landscape sheets only. What a sheet always holds in CSS px with 0.25in margins on Letter or A4 (whichever is smaller each way).
  var LAND = {w:1004, h:741, name:'landscape'};
  var MIN_ONE = 0.5, MIN_READ = 0.42;                                                      // below these a sheet is too small to read

  function pageStyle(orient){
    var s = document.getElementById('alto-ink-page');
    if(!s){ s = document.createElement('style'); s.id = 'alto-ink-page'; document.head.appendChild(s); }
    s.textContent = '@media print{@page{size:' + orient + ';margin:0.25in;}}';
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
  window._altoInkPlan = function(w, h, boxes, segs){
    var o = LAND, s, cols, rows, colCuts;
    segs = segs || [];
    var s1 = Math.min(1, o.w / w, o.h / h);
    if(s1 >= MIN_ONE){ s = s1; rows = [[0, h]]; colCuts = [[0, w]]; }
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

  var inkPrev = null;
  window._altoInkUnstage = function(){
    var h = document.getElementById('alto-ink-host'); if(h) h.remove();
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
    var plan = window._altoInkPlan(W, H, boxes, segs);

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
