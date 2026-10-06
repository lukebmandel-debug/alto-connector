"""Printing a timeline: the page's three print views, and the link that asks for one.

The engine already prints the outline (its "Main timeline"), one detail page and
every detail page. This module adds what it lacks, in the page itself so that the
two ways in share one piece of code:

  * the notes panel's share dialog (its PRINT list), and
  * the homepage's Print... dialog, which opens the timeline with
    `#altoprint=outline|full|ink` and lets the page print itself.

`ink` is the timeline PICTURE (cards and lines) on white paper with no colour,
no glass, no shadows: a copy of the canvas placed in the document (so every card
rule still applies) and then stripped to black and grey. It is scaled to the
sheet; one that cannot be read on one sheet goes across several, cut between
cards rather than through them, in portrait or landscape whichever reads larger.

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
  var PORT = {w:705, h:960, name:'portrait'}, LAND = {w:960, h:705, name:'landscape'};   // CSS px a sheet always holds, 11mm margins
  var MIN_ONE = 0.5, MIN_READ = 0.42;                                                      // below these a sheet is too small to read

  function pageStyle(orient){
    var s = document.getElementById('alto-ink-page');
    if(!s){ s = document.createElement('style'); s.id = 'alto-ink-page'; document.head.appendChild(s); }
    s.textContent = '@media print{@page{size:' + orient + ';margin:11mm;}}';
  }

  // Which sheet, what scale, and where the cuts fall. Pure, so it can be tested.
  window._altoInkPlan = function(w, h, boxes){
    var o, s, best = null;
    // the sheet that matches the picture's shape; the other only if it reads 50% larger
    var first = w > h ? LAND : PORT, second = w > h ? PORT : LAND;
    [first, second].forEach(function(c){
      var s1 = Math.min(1, c.w / w, c.h / h);
      if(!best || s1 > best.s1 * 1.5) best = {c:c, s1:s1};
    });
    var cols = 1, rows;
    if(best.s1 >= MIN_ONE){
      o = best.c; s = best.s1; rows = [[0, h]];
    } else {
      var pw = Math.min(1, PORT.w / w), lw = Math.min(1, LAND.w / w);
      o = (w > h) ? ((pw > lw * 1.5) ? PORT : LAND) : ((lw > pw * 1.5) ? LAND : PORT);
      s = Math.max(Math.min(1, o.w / w), MIN_READ);
      cols = Math.max(1, Math.ceil(w * s / o.w - 1e-6));
      var cap = 40;                                                 // never an unbounded stack of sheets
      while(cols * Math.ceil(h * s / o.h) > cap && s > 0.1){ s *= 0.9; cols = Math.max(1, Math.ceil(w * s / o.w - 1e-6)); }
      var Hw = o.h / s, y = 0; rows = [];
      while(y < h - 1){
        var end = Math.min(y + Hw, h);
        if(end < h){                                                // cut between cards, as late as fits
          var cand = [];
          boxes.forEach(function(b){ cand.push(b.y - 8, b.y + b.h + 8); });
          var cut = -1;
          cand.forEach(function(c){
            if(c <= y + Hw * 0.35 || c > end || c < cut) return;
            for(var i = 0; i < boxes.length; i++) if(boxes[i].y < c && c < boxes[i].y + boxes[i].h) return;
            cut = c;
          });
          if(cut > 0) end = cut;
        }
        rows.push([y, end]); y = end;
      }
    }
    return {orient:o.name, w:o.w, h:o.h, s:s, cols:cols, rows:rows};
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
    var plan = window._altoInkPlan(W, H, boxes);

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

    var host = document.createElement('div'); host.id = 'alto-ink-host';
    var offX = plan.cols === 1 ? Math.max(0, (plan.w - W * plan.s) / 2) : 0;
    var n = 0;
    plan.rows.forEach(function(row){
      for(var c = 0; c < plan.cols; c++){
        var tile = document.createElement('div'); tile.className = 'ink-tile';
        tile.style.cssText = 'width:' + plan.w + 'px;height:' + Math.min(plan.h, Math.ceil((row[1] - row[0]) * plan.s) + 1) + 'px;';
        var inner = document.createElement('div'); inner.className = 'ink-in';
        inner.style.cssText = 'left:' + offX + 'px;top:0;width:' + world.offsetWidth + 'px;height:' + world.offsetHeight + 'px;' +
          'transform:scale(' + plan.s + ') translate(' + (-(X0 + c * plan.w / plan.s)) + 'px,' + (-(Y0 + row[0])) + 'px);';
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
      }
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
