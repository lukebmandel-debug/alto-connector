"""Print... on a visual format: page 1 is a one-page STUDY SHEET, then the outline.

Art's spec (alto-art, 2026-11-01; CEO C-1101-120214): a System, a Memory Map
(city), a Memory Atlas (world map) and a Memory Blueprint (building) are drawn,
not read, so on paper they open with one page that shows the shape simply in
black and grey, then the existing outline pages, unchanged. Formats that already
print as what they are (timeline, outline, horizontal timeline) are untouched:
this module adds nothing to their pages at all.

  System     a boxed unit map: a title bar, then one box per unit in a grid of
             1, 2 or 3 columns, each box its unit heading and that unit's
             concepts by outline number and title. It always fits the one page:
             the type shrinks to 8 pt, then a box ends "+ N more: see outline".
  palaces    the route in order: stop number, card, and where it sits (street,
             country, or room and floor), with a small grey picture of the map
             when the page holds one. Two columns past 14 stops.

The sheet is built in the page at print time (window._altoStudySheet), from the
data the page already holds, and placed in front of whatever
_buildPrintTimelineHTML returns (engine patch `study-sheet-first`), so the
outline print and "Outline + all detail pages" both start with it, from the
homepage's Print... dialog, the notes panel's PRINT list, or the browser's own
print command. The ink-saver picture is not touched.

Paper: Letter and A4 portrait both hold a 188 x 257 mm box inside the engine's
11 mm @page margin; the sheet pads it by 4 mm, so the print has 15 mm margins.
Every size is in mm and pt, so the screen measures what the paper prints.
"""
from __future__ import annotations

import json
import re

from .brief import solar_style

# what the header calls each format, in words (paper has no hover)
FORMAT_NAMES = {"system": "System", "city": "Mind Palace", "world": "World map",
                "building": "Memory palace"}

# the line under the Print... dialog's note, desktop and phone (home_template.html
# keeps the same table, keyed by the homepage's own format names)
PALACE_LABEL = "Prints your route in order (with a small picture if one is saved), then the outline."
DIALOG_LABELS = {"system": "Prints a one-page unit map, then the outline.",
                 "palace": PALACE_LABEL, "world": PALACE_LABEL, "building": PALACE_LABEL}


def sheet_kind(brief) -> str:
    """'system' | 'city' | 'world' | 'building' for a visual format, '' for the rest."""
    if solar_style(brief):
        return "system"
    if getattr(brief, "mode", "") == "palace":
        v = getattr(brief, "palace_view", "city") or "city"
        return v if v in ("city", "world", "building") else "city"
    return ""


CSS = r"""<style id="alto-study-sheet">
  #alto-ss-measure{position:absolute;left:-30000px;top:0;visibility:hidden;pointer-events:none;}
  .ss-sheet{box-sizing:border-box;width:188mm;height:257mm;padding:4mm;margin:0;position:relative;overflow:hidden;
    display:flex;flex-direction:column;background:#fff;color:#000;font:10pt/1.25 -apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif;
    text-align:left;letter-spacing:normal;text-transform:none;}
  .ss-sheet *{box-sizing:border-box;}
  .ss-head{display:flex;align-items:flex-start;gap:6mm;border-bottom:.75pt solid #000;padding:0 0 2.5mm;margin:0 0 4mm;flex:0 0 auto;}
  .ss-head-l{flex:1 1 auto;min-width:0;}
  .ss-title{font-size:14pt;font-weight:600;line-height:1.2;margin:0;overflow-wrap:anywhere;}
  .ss-sub{font-size:10pt;margin:1mm 0 0;}
  .ss-date{flex:0 0 auto;font-size:10pt;white-space:nowrap;}
  .ss-body{flex:1 1 auto;min-height:0;position:relative;display:flex;flex-direction:column;}
  .ss-foot{flex:0 0 auto;border-top:.75pt solid #000;margin:4mm 0 0;padding:2mm 0 0;font-size:9pt;}
  /* System: the unit map */
  .ss-bar{position:relative;z-index:1;align-self:center;max-width:100%;border:.75pt solid #000;background:#fff;padding:1.5mm 5mm;
    font-size:11pt;font-weight:600;text-align:center;margin:0 0 6mm;overflow-wrap:anywhere;}
  .ss-grid{flex:1 1 auto;min-height:0;display:grid;gap:5mm;position:relative;z-index:1;}
  .ss-unit{border:.75pt solid #000;background:#fff;display:flex;flex-direction:column;min-height:0;overflow:hidden;}
  .ss-unit-h{font-size:11pt;font-weight:600;line-height:1.25;padding:1.2mm 2.5mm;background:#e0e0e0;border-bottom:.75pt solid #000;overflow-wrap:anywhere;}
  .ss-list{list-style:none;margin:0;padding:1.5mm 2.5mm 2mm;font-size:var(--ss-fs,10pt);line-height:1.25;flex:1 1 auto;min-height:0;}
  .ss-list li{display:flex;gap:1.6mm;margin:0 0 .7mm;padding-left:calc(var(--d,0) * 3.2mm);break-inside:avoid;}
  .ss-num{flex:0 0 auto;font-variant-numeric:tabular-nums;}
  .ss-t{flex:1 1 auto;min-width:0;overflow-wrap:anywhere;}
  .ss-list li.ss-more{font-style:italic;padding-left:0;}
  .ss-links{position:absolute;left:0;top:0;width:100%;height:100%;z-index:0;overflow:visible;pointer-events:none;}
  .ss-links line{stroke:#000;stroke-width:.75pt;fill:none;}
  /* palaces: the route */
  .ss-intro{font-size:10pt;margin:0 0 3mm;}
  .ss-route{display:flex;gap:5mm;align-items:flex-start;flex:1 1 auto;min-height:0;}
  .ss-thumb{flex:0 0 auto;max-width:70mm;max-height:100mm;border:1pt solid #000;filter:grayscale(1);display:block;object-fit:contain;}
  .ss-route.two .ss-thumb{max-width:50mm;}   /* two columns beside it need the room */
  .ss-cols{flex:1 1 auto;min-width:0;display:flex;gap:5mm;align-items:flex-start;}
  .ss-tbl{flex:1 1 0;min-width:0;border-collapse:collapse;font-size:var(--ss-fs,10pt);line-height:1.25;}
  .ss-tbl th{text-align:left;font-weight:600;border-bottom:.75pt solid #000;padding:0 2mm 1mm 0;white-space:nowrap;}
  .ss-tbl td{padding:.9mm 2mm .9mm 0;vertical-align:top;border-bottom:.5pt solid #e0e0e0;overflow-wrap:anywhere;}
  .ss-tbl td.ss-n{white-space:nowrap;font-variant-numeric:tabular-nums;}
  .ss-tbl td.ss-more{font-style:italic;border-bottom:0;}
  @media print{
    /* Chromium sizes the desktop body as 100vw / 0.8 (engine VIEWPORT FILL), which out-ranks the print reset, so the
       browser shrinks the whole print to 80% to fit it: the sheet's mm and pt would not be the paper's. */
    html.printing:not(.mobile):has(.ss-sheet) body{width:auto !important;height:auto !important;min-height:0 !important;}
    /* out-rank the engine's print strip (html.printing *: transparent fills, #9a9a9a borders) */
    html.printing .ss-sheet{display:flex !important;break-after:page;page-break-after:always;break-inside:avoid;}
    html.printing .ss-sheet,html.printing .ss-sheet *{color:#000 !important;-webkit-text-fill-color:#000 !important;
      -webkit-print-color-adjust:exact;print-color-adjust:exact;}
    html.printing .ss-sheet :is(.ss-head,.ss-foot,.ss-bar,.ss-unit,.ss-unit-h,.ss-tbl th,.ss-thumb){border-color:#000 !important;}
    html.printing .ss-sheet .ss-tbl td{border-color:#e0e0e0 !important;}
    html.printing .ss-sheet :is(.ss-bar,.ss-unit){background-color:#fff !important;}
    html.printing .ss-sheet .ss-unit-h{background-color:#e0e0e0 !important;}
    html.printing .ss-sheet .ss-links line{stroke:#000 !important;}
  }
</style>
"""

JS = r"""<script id="alto-study-sheet-js">
(function(){
  if(window._altoStudySheet) return;
  var KIND = __KIND__, FMT = __FMT__, TITLE = __TITLE__;
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function G(name){ try{ return (0, eval)('typeof ' + name + " !== 'undefined' ? " + name + ' : undefined'); }catch(e){ return undefined; } }
  function title(){ return TITLE || 'Untitled'; }
  function today(){
    try{ return new Date().toLocaleDateString(undefined, {year:'numeric', month:'long', day:'numeric'}); }catch(e){ return ''; }
  }
  function frame(sub, body, extra){
    return '<section class="ss-sheet" data-kind="' + KIND + '">' +
      '<header class="ss-head"><div class="ss-head-l"><h1 class="ss-title">' + esc(title()) + '</h1>' +
      (extra ? '<p class="ss-sub">' + esc(extra) + '</p>' : '') + '<p class="ss-sub">' + esc(sub) + '</p></div><div class="ss-date">' + esc(today()) + '</div></header>' +
      '<div class="ss-body">' + body + '</div>' +
      '<footer class="ss-foot">Page 1 of <span class="ss-pages">2</span>: the outline follows.</footer></section>';
  }

//<system>
  // ── the outline the page holds: units in order, each with its cards in outline order and depth
  function units(){
    var SEQ = G('ACT_SEQS') || [], NODES = G('NODES') || [], PM = G('PHASE_META') || [];
    var O = window._ALTO_OUTLINE || {label:{}, kids:{}, parent:{}};
    var byId = {}; NODES.forEach(function(n){ byId[n.id] = n; });
    return SEQ.map(function(ids, ui){
      var inU = {}; ids.forEach(function(id){ inU[id] = 1; });
      var roots = ids.filter(function(id){ var p = O.parent[id]; return !(p && inU[p]); });
      var items = [];
      function walk(id, d){
        var n = byId[id]; if(!n) return;
        items.push({id:id, num:(O.label && O.label[id]) || '', title:n.title || id, d:d});
        (O.kids[id] || []).forEach(function(k){ if(inU[k]) walk(k, d + 1); });
      }
      roots.forEach(function(r){ walk(r, roots.length > 1 ? 1 : 0); });
      var pm = PM[ui] || {};
      var head = roots.length === 1 && byId[roots[0]] ? byId[roots[0]].title
               : String(pm.label || '').replace(/^\s*unit\s+[\w-]+\s*[—–:-]\s*/i, '') || pm.label || '';
      return {n:ui + 1, title:head, items:roots.length === 1 ? items.slice(1) : items};
    });
  }

  // ── System: a boxed unit map
  function systemSheet(){
    var U = units();
    var cols = U.length <= 2 ? 1 : U.length <= 6 ? 2 : 3, rows = Math.max(1, Math.ceil(U.length / cols));
    var body = '<div class="ss-bar">' + esc(title()) + '</div>' +
      '<div class="ss-grid" style="grid-template-columns:repeat(' + cols + ',minmax(0,1fr));grid-template-rows:repeat(' + rows + ',minmax(0,1fr))">' +
      U.map(function(u){
        return '<div class="ss-unit" data-unit="' + u.n + '"><div class="ss-unit-h">Unit ' + u.n + ': ' + esc(u.title) + '</div>' +
          '<ul class="ss-list">' + u.items.map(function(it){
            return '<li style="--d:' + Math.max(0, it.d - 1) + '"><span class="ss-num">' + esc(it.num) + '</span><span class="ss-t">' + esc(it.title) + '</span></li>';
          }).join('') + '</ul></div>';
      }).join('') + '</div>' + (U.length && U.length <= 6 ? '<svg class="ss-links" aria-hidden="true"></svg>' : '');
    return frame('System · Study sheet', body);
  }
  function fitSystem(sheet){
    var lists = [].slice.call(sheet.querySelectorAll('.ss-list'));
    function over(){ return lists.some(function(l){ return l.scrollHeight > l.clientHeight + 0.5; }); }
    var sizes = [10, 9.5, 9, 8.5, 8];
    for(var i = 0; i < sizes.length; i++){
      sheet.style.setProperty('--ss-fs', sizes[i] + 'pt');
      if(!over()) break;
    }
    // still too long at 8 pt: each box that overflows ends "+ N more: see outline"
    lists.forEach(function(l){
      if(l.scrollHeight <= l.clientHeight + 0.5) return;
      var lis = [].slice.call(l.children), hidden = 0;
      var more = document.createElement('li'); more.className = 'ss-more'; l.appendChild(more);
      while(lis.length && l.scrollHeight > l.clientHeight + 0.5){
        l.removeChild(lis.pop()); hidden++;
        more.textContent = '+ ' + hidden + ' more: see outline';
      }
    });
    // the lines (6 units or fewer) run only through the gaps, never across a box: 2 columns, a trunk down the middle
    // gutter from the title bar with a stub into each box at its heading; 1 column, a chain from box to box
    var svg = sheet.querySelector('.ss-links');
    if(svg){
      // the screen page is zoomed (html{zoom:.8} on desktop): rects come back scaled, the SVG draws in the sheet's own px
      var k = sheet.offsetWidth / (sheet.getBoundingClientRect().width || sheet.offsetWidth || 1);
      var body = sheet.querySelector('.ss-body').getBoundingClientRect(), bar = sheet.querySelector('.ss-bar').getBoundingClientRect();
      var boxes = [].map.call(sheet.querySelectorAll('.ss-unit'), function(u){
        var r = u.getBoundingClientRect(), h = u.querySelector('.ss-unit-h').getBoundingClientRect();
        return {l:k * (r.left - body.left), r:k * (r.right - body.left), t:k * (r.top - body.top), b:k * (r.bottom - body.top),
                hy:k * ((h.top + h.bottom) / 2 - body.top)};
      });
      var X = k * (bar.left + bar.width / 2 - body.left), Y = k * (bar.bottom - body.top), L = [];
      function ln(x1, y1, x2, y2){ L.push('<line x1="' + x1.toFixed(1) + '" y1="' + y1.toFixed(1) + '" x2="' + x2.toFixed(1) + '" y2="' + y2.toFixed(1) + '"/>'); }
      if(boxes.length > 2){
        var last = 0;
        boxes.forEach(function(bx){ last = Math.max(last, bx.hy); ln(bx.l > X ? X : bx.r, bx.hy, bx.l > X ? bx.l : X, bx.hy); });
        ln(X, Y, X, last);
      } else {
        var px = X, py = Y;
        boxes.forEach(function(bx){ var cx = (bx.l + bx.r) / 2; ln(px, py, cx, bx.t); px = cx; py = bx.b; });
      }
      svg.innerHTML = L.join('');
    }
  }

//</system>
  // ── palaces: the route in order (study_route.py)
  __ROUTE_JS__

  // How many sheets the outline after page 1 takes. The print rules for the outline live in @media print, so they are
  // copied, unwrapped, onto a measuring box the width of the sheet; then the blocks are laid down greedily the way the
  // browser does (a block that does not fit starts the next sheet; a heading never ends one). Letter: the shorter sheet.
  var PAGE_H = (279.4 - 22) * 96 / 25.4, PAGE_W = (215.9 - 22) * 96 / 25.4;
  function printRules(){
    var out = [];
    [].forEach.call(document.styleSheets, function(ss){
      var rules; try{ rules = ss.cssRules; }catch(e){ return; }
      [].forEach.call(rules || [], function(r){
        if(r.media && /print/.test(r.media.mediaText) && r.cssRules){
          [].forEach.call(r.cssRules, function(x){
            if(x.selectorText && /print-(ol|tl|unit|node|spine|detail)|\.pn-/.test(x.selectorText)){
              out.push(x.selectorText.split(',').map(function(s){
                return '#alto-ss-measure ' + s.replace(/html[^\s]*\s*/g, '').replace(/#print-(timeline-host|all)\s*/g, '').trim();
              }).join(',') + '{' + x.style.cssText + '}');
            }
          });
        }
      });
    });
    return out.join('\n');
  }
  function sheetsFor(html){
    var m = document.createElement('div'); m.id = 'alto-ss-measure';
    m.style.width = PAGE_W + 'px';
    var st = document.createElement('style'); st.textContent = printRules();
    m.innerHTML = html; m.insertBefore(st, m.firstChild); document.body.appendChild(m);
    // laid out on the measuring box, every block's top and bottom include the margins round it; a sheet ends before the
    // first block that would cross its foot (a heading goes over with the block after it; a detail page starts a sheet)
    var blocks = [].filter.call(m.querySelectorAll('h1,h2,.print-ol-row,.print-node,.print-detail'), function(b){
      return !(b.parentElement && b.parentElement.closest('.print-ol-row,.print-node,.print-detail'));
    });
    var k = m.offsetWidth / (m.getBoundingClientRect().width || m.offsetWidth || 1), y0 = m.getBoundingClientRect().top;
    var pages = 1, start = 0, prev = null;
    blocks.forEach(function(b){
      var r = b.getBoundingClientRect(), top = k * (r.top - y0), bot = k * (r.bottom - y0);
      var from = prev && /^H/.test(prev.el.tagName) ? prev.top : top;
      if(b.classList.contains('print-detail') && top > start + 1){ pages++; start = top; }
      else if(bot - start > PAGE_H && from > start + 1){ pages++; start = from; }
      while(bot - start > PAGE_H){ pages++; start += PAGE_H; }         // a block taller than a sheet runs on
      prev = {el:b, top:top};
    });
    m.remove();
    return pages;
  }

  // page 1, laid out and fitted in a measuring box (same mm/pt sizes as on paper), then handed over as markup
  window._altoStudySheet = function(rest){
    var html = KIND === 'system' ? systemSheet() : routeSheet();
    var m = document.createElement('div'); m.id = 'alto-ss-measure'; m.innerHTML = html; document.body.appendChild(m);
    var sheet = m.firstChild;
    try{ if(KIND === 'system') fitSystem(sheet); else fitRoute(sheet); }catch(e){}
    try{ if(rest) sheet.querySelector('.ss-pages').textContent = String(1 + sheetsFor(rest)); }catch(e){}
    var out = sheet.outerHTML; m.remove();
    return out;
  };
  window._altoStudySheetKind = KIND;
})();
</script>
"""


def study_sheet(brief) -> str:
    """The study sheet's CSS and JS for a visual format's page; '' for every other page."""
    kind = sheet_kind(brief)
    if not kind:
        return ""
    from .study_route import ROUTE_JS
    js = (JS.replace("__ROUTE_JS__", "" if kind == "system" else ROUTE_JS))
    js = _only(js, kind)
    js = (js.replace("__KIND__", json.dumps(kind))
            .replace("__FMT__", json.dumps(FORMAT_NAMES[kind]))
            .replace("__TITLE__", json.dumps(getattr(brief, "title", "") or "").replace("</", "<\\/"))
        )
    return _small_css(CSS) + _small_js(js)


def _only(js: str, kind: str) -> str:
    """Keep the //<kind> ... //</kind> part for this page's format, drop the other formats' parts (a city page never
    names the Atlas's or the Blueprint's data, and the private page is near its size cap)."""
    def keep(m):
        return m.group(2) if m.group(1) == kind else ""
    return re.sub(r"//<(\w+)>\n(.*?)//</\1>\n", keep, js, flags=re.S)


def _small_js(js: str) -> str:
    """The comments and the indentation go; nothing else changes (no comment in this code sits inside a string)."""
    out = []
    for ln in js.split("\n"):
        ln = re.sub(r"\s+//\s.*$", "", ln).strip()
        if ln and not ln.startswith("//"):
            out.append(ln)
    return "\n".join(out) + "\n"


def _small_css(css: str) -> str:
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return re.sub(r"\n\s+", "\n", css)
