"""The Filter toggle: every filter a timeline has, in one panel.

A timeline's filters used to be scattered — rows of chips in the nav bar for the
slot filters and the relation "Lines", more sections in the mobile drawer. They
all live behind one toggle now, each kind as its own section:

  chips   one per kind of sub-chip a card carries (characters, environments,
          themes, doctrines…). Those chips have detail pages of their own, so
          any of them is a fair thing to filter by. Picking several inside one
          section keeps cards that carry ANY of them; sections combine with AND.
  slot    the author's declared filters (coverage, depth, a custom dimension…),
          driven by the engine's own two filter slots.
  lines   the relation key, isolating one relation's lines. Optional.

Desktop: a tab on the right edge in a rail with the overview star and Notes
(overview on top, Notes in the middle, Filter at the bottom), opening a panel.
Mobile: a tile at the bottom-left in the account toggle's old place, styled as
the INFO tile above it, opening a sheet.
"""

# The three right-edge tabs stack in one rail, in a fixed order. They were three
# independently positioned buttons; one flex column keeps the gaps even whatever
# the tab heights are, and lets the Filter tab slot in without any arithmetic.
RAIL_GLUE = """
(function(){
  if(window._altoRailBound) return; window._altoRailBound=1;
  var root=document.documentElement;
  if(root.classList.contains('mobile')) return;
  function build(){
    if(document.getElementById('tab-rail')) return;
    var ov=document.getElementById('overview-toggle'), nt=document.getElementById('notes-toggle');
    if(!ov && !nt) return;
    var rail=document.createElement('div'); rail.id='tab-rail';
    document.body.appendChild(rail);
    if(ov) rail.appendChild(ov);
    if(nt) rail.appendChild(nt);
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', build); else build();
})();"""

RAIL_CSS = (
    "\n  #tab-rail{position:fixed;right:0;top:calc(50% - 32px);z-index:395;"
    "display:flex;flex-direction:column;align-items:flex-end;gap:8px;}"
    "\n  html:not(.mobile) #tab-rail > button{position:static !important;"
    "transform:none !important;top:auto !important;right:auto !important;margin:0;}"
    "\n  html.printing #tab-rail{display:none !important;}"
    # Mobile: the account toggle stays on the home page; inside a timeline its
    # place is the Filter tile's, and the INFO tile only rises to make room for
    # that tile when there is one.
    "\n  html.mobile #account-btn{display:none !important;}")

FILTER_PANEL_GLUE = """
(function(){
  if(window._altoFilterBound) return; window._altoFilterBound=1;
  var root=document.documentElement;
  function mobile(){ return root.classList.contains('mobile'); }
  root.classList.add('has-filter-tab');
  var sel={}, slotState={};
  FILTER_SECTIONS.forEach(function(s){ if(s.kind==='chips') sel[s.key]={}; });
  function chipKeys(){ return Object.keys(sel).filter(function(k){ return Object.keys(sel[k]).length>0; }); }
  function keep(id){
    var ks=chipKeys();
    for(var i=0;i<ks.length;i++){
      var m=FILTER_NODES[ks[i]]||{}, ok=false;
      Object.keys(sel[ks[i]]).forEach(function(v){ if((m[v]||[]).indexOf(id)>=0) ok=true; });
      if(!ok) return false;
    }
    return true;
  }
  // Read by the engine's filtered-order code (next/previous, swipe, compass), so
  // stepping through the timeline skips what the filter has hidden.
  window._altoChipOn=function(){ return chipKeys().length>0; };
  window._altoChipKeep=keep;
  function slotVal(slot){ return mobile() ? ((window._mobileFilter||{})[slot]||null) : (slotState[slot]||null); }
  function activeLines(){ return document.querySelectorAll('#ef-panel .line-key-btn.active'); }
  function activeCount(){
    var n=0; chipKeys().forEach(function(k){ n+=Object.keys(sel[k]).length; });
    FILTER_SECTIONS.forEach(function(s){ if(s.kind==='slot' && slotVal(s.slot)) n++; });
    return n+activeLines().length;
  }
  function refresh(){
    var nodes=document.querySelectorAll('#world .node');
    for(var i=0;i<nodes.length;i++){
      var card=nodes[i].querySelector('.node-card'); if(!card) continue;
      card.classList.toggle('ent-dimmed', !keep(nodes[i].id.slice(5)));
    }
    document.querySelectorAll('#ef-panel .ef-chip[data-fs]').forEach(function(b){
      var k=b.getAttribute('data-fs'), id=b.getAttribute('data-fid'), on=false;
      if(sel[k]) on=!!sel[k][id];
      else {
        var s=FILTER_SECTIONS.filter(function(x){ return x.key===k; })[0];
        if(!s || s.kind==='lines') return;   // LINES_GLUE owns those chips' state
        on=slotVal(s.slot)===id;
      }
      b.classList.toggle('active', on);
    });
    var n=activeCount(), tab=document.getElementById('filter-toggle');
    if(tab){ tab.classList.toggle('active', n>0); tab.setAttribute('data-n', n||''); }
    var clr=document.getElementById('ef-clear'); if(clr) clr.hidden=!n;
  }
  function refeature(){
    // A phone shows one card at a time: if the filter just hid it, move to the
    // first one it kept.
    if(!mobile() || typeof window._filteredOrder!=='function') return;
    var order=window._filteredOrder();
    if(order.length && order.indexOf(window._featuredNodeId)<0 && typeof window.featureNode==='function') window.featureNode(order[0],false);
    try{ if(window._patchTimelineLabels) window._patchTimelineLabels(); }catch(e){}
  }
  function build(){
    if(document.getElementById('filter-toggle')) return;
    var tab=document.createElement('button');
    tab.id='filter-toggle'; tab.type='button';
    tab.title='Filter'; tab.setAttribute('aria-label','Filter'); tab.setAttribute('aria-expanded','false');
    tab.innerHTML='<svg viewBox="0 0 20 20" width="17" height="17" style="display:block" fill="currentColor" aria-hidden="true"><path d="M2 3.5h16l-6.2 7.4v5.1l-3.6 1.9v-7z"/></svg><span>FILTER</span>';
    var panel=document.createElement('div');
    panel.id='ef-panel'; panel.setAttribute('role','dialog'); panel.setAttribute('aria-label','Filter');
    var head=document.createElement('div'); head.className='ef-head';
    var ttl=document.createElement('span'); ttl.textContent='Filter';
    var clr=document.createElement('button'); clr.type='button'; clr.id='ef-clear'; clr.hidden=true; clr.textContent='Clear all';
    head.appendChild(ttl); head.appendChild(clr); panel.appendChild(head);
    FILTER_SECTIONS.forEach(function(s){
      var sec=document.createElement('div'); sec.className='ef-sec';
      var h=document.createElement('div'); h.className='ef-h'; h.textContent=s.label; sec.appendChild(h);
      var list=document.createElement('div'); list.className='ef-chips';
      s.items.forEach(function(it){
        var b=document.createElement('button'); b.type='button'; b.className='ef-chip';
        b.setAttribute('data-fs', s.key); b.setAttribute('data-fid', it.id);
        b.style.setProperty('--c', it.color || 'var(--accent)');
        if(s.kind==='lines'){
          b.classList.add('line-key-btn'); b.setAttribute('data-rel-key', it.id);
          var sw=document.createElement('span'); sw.className='ef-line';
          sw.style.background=it.swatch; b.appendChild(sw);
        } else if(it.symbol){
          var sy=document.createElement('span'); sy.className='ef-sym'; sy.innerHTML=it.symbol; b.appendChild(sy);
        }
        var nm=document.createElement('span'); nm.className='ef-name'; nm.textContent=it.name; b.appendChild(nm);
        if(it.count!=null){ var c=document.createElement('span'); c.className='ef-count'; c.textContent=it.count; b.appendChild(c); }
        list.appendChild(b);
      });
      sec.appendChild(list); panel.appendChild(sec);
    });
    document.body.appendChild(panel);
    var rail=document.getElementById('tab-rail');
    (rail && !mobile() ? rail : document.body).appendChild(tab);
    function open(v){ panel.classList.toggle('open', v); tab.setAttribute('aria-expanded', v?'true':'false'); }
    tab.addEventListener('click', function(e){ e.stopPropagation(); open(!panel.classList.contains('open')); });
    clr.addEventListener('click', function(){
      Object.keys(sel).forEach(function(k){ sel[k]={}; });
      FILTER_SECTIONS.forEach(function(s){
        if(s.kind!=='slot') return; var v=slotVal(s.slot); if(!v) return;
        if(mobile()){ if(window.setMobileFilter) window.setMobileFilter(s.slot, v); }
        else if(window.filterCanvas) window.filterCanvas(s.slot, v);
      });
      Array.prototype.forEach.call(activeLines(), function(b){ b.click(); });
      refresh(); refeature();
    });
    document.addEventListener('click', function(e){
      if(panel.classList.contains('open') && !e.target.closest('#ef-panel') && !e.target.closest('#filter-toggle')) open(false);
    });
    document.addEventListener('keydown', function(e){ if(e.key==='Escape') open(false); });
    // A detail page or the overview covers the timeline; the panel goes with it.
    new MutationObserver(function(){
      if(root.classList.contains('detail-open') || root.classList.contains('summary-open')) open(false);
    }).observe(root, {attributes:true, attributeFilter:['class']});
  }
  document.addEventListener('click', function(e){
    var b=e.target && e.target.closest && e.target.closest('#ef-panel .ef-chip[data-fs]');
    if(!b) return;
    var k=b.getAttribute('data-fs'), id=b.getAttribute('data-fid');
    if(sel[k]){
      e.preventDefault(); e.stopPropagation();
      if(sel[k][id]) delete sel[k][id]; else sel[k][id]=1;
      refresh(); refeature(); return;
    }
    var s=FILTER_SECTIONS.filter(function(x){ return x.key===k; })[0];
    if(s && s.kind==='slot'){
      e.preventDefault(); e.stopPropagation();
      if(mobile()){ if(window.setMobileFilter) window.setMobileFilter(s.slot, id); }
      else if(window.filterCanvas) window.filterCanvas(s.slot, id);
      setTimeout(refresh,0); return;
    }
    setTimeout(refresh,0);   // lines: LINES_GLUE owns the toggle
  }, true);
  // The engine owns the slot filters; mirror what it does so the chips can show it.
  var ofc=window.filterCanvas;
  if(typeof ofc==='function'){
    window.filterCanvas=function(axis, value){
      if(slotState[axis]===value) delete slotState[axis]; else slotState[axis]=value;
      var r=ofc.apply(this, arguments); setTimeout(refresh,0); return r;
    };
  }
  var tries=0;
  (function wrapMobile(){
    var omf=window.setMobileFilter;
    if(typeof omf!=='function'){ if(++tries<80) setTimeout(wrapMobile,250); return; }
    window.setMobileFilter=function(){ var r=omf.apply(this, arguments); setTimeout(refresh,0); return r; };
  })();
  // A re-render (theme toggle, back from a detail page) rebuilds the cards; put
  // the filter back on them.
  var queued=false;
  new MutationObserver(function(){
    if(queued || !window._altoChipOn()) return; queued=true;
    requestAnimationFrame(function(){ queued=false; refresh(); });
  }).observe(document.body, {childList:true, subtree:true});
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', build); else build();
})();"""


def filter_panel_css() -> str:
    return (
        "\n  .node-card.ent-dimmed{background:var(--surface) !important;"
        "border-top-color:var(--border) !important;}"
        "\n  .node-card.ent-dimmed > *{opacity:0.15;}"
        # ── desktop: an edge tab in the rail, glass like its neighbours ──
        "\n  html:not(.mobile) #filter-toggle{width:34px;height:34px;box-sizing:border-box;"
        "padding:0;display:flex;align-items:center;justify-content:center;cursor:pointer;"
        "position:relative;"
        "background:var(--card-glass-bg, var(--surface));"
        "-webkit-backdrop-filter:blur(18px) saturate(190%);backdrop-filter:blur(18px) saturate(190%);"
        "border:1px solid var(--card-glass-border, var(--border));border-right:none;"
        "border-radius:6px 0 0 6px;color:var(--muted);"
        "box-shadow:0 10px 26px var(--node-rest-shadow);}"
        "\n  html:not(.mobile) #filter-toggle span{display:none;}"
        "\n  html:not(.mobile) #filter-toggle:hover{color:var(--text);border-color:var(--muted);}"
        "\n  #filter-toggle.active{color:var(--accent);border-color:var(--accent);}"
        "\n  #filter-toggle[data-n]:not([data-n=\"\"])::after{content:attr(data-n);"
        "position:absolute;top:-6px;left:-7px;min-width:15px;height:15px;padding:0 3px;"
        "box-sizing:border-box;border-radius:8px;background:var(--accent);color:#fff;"
        "font-size:10px;line-height:15px;text-align:center;}"
        # ── mobile: the INFO tile's twin, in the account toggle's old place ──
        "\n  html.mobile #filter-toggle{position:fixed;left:0;"
        "bottom:calc(8px + env(safe-area-inset-bottom, 0px));z-index:295;"
        "min-width:36px;height:49px;box-sizing:border-box;padding:10px 4px;"
        "display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;"
        "background:var(--card-glass-bg);"
        "-webkit-backdrop-filter:blur(12px) saturate(170%);backdrop-filter:blur(12px) saturate(170%);"
        "border:1px solid var(--border);border-left:none;border-radius:0 6px 6px 0;"
        "box-shadow:0 10px 26px var(--node-rest-shadow), inset 0 0 0 0.5px var(--card-glass-rim);"
        "color:var(--text);font-size:8.5px;letter-spacing:.1em;text-transform:uppercase;"
        "font-family:-apple-system,BlinkMacSystemFont,sans-serif;cursor:pointer;"
        "-webkit-tap-highlight-color:transparent;transition:opacity .15s;}"
        "\n  html.mobile #filter-toggle svg{width:13px;height:13px;}"
        "\n  html.mobile #filter-toggle:active{opacity:.6;}"
        "\n  html.mobile.detail-open #filter-toggle, html.mobile.summary-open #filter-toggle,"
        "\n  html.mobile.detail-open #ef-panel, html.mobile.summary-open #ef-panel{display:none !important;}"
        # ── the panel ──
        "\n  #ef-panel{position:fixed;z-index:396;overflow:auto;padding:12px 12px 6px;"
        "border-radius:14px;opacity:0;pointer-events:none;"
        "transition:opacity .15s, transform .15s;"
        "background:var(--panel-glass-bg, var(--surface));"
        "-webkit-backdrop-filter:blur(30px) saturate(185%);backdrop-filter:blur(30px) saturate(185%);"
        "border:1px solid var(--card-glass-border, var(--border));"
        "box-shadow:0 18px 48px var(--node-hover-shadow);color:var(--text);}"
        "\n  html:not(.mobile) #ef-panel{right:46px;top:50%;width:340px;max-height:min(76vh,600px);"
        "transform:translateY(calc(-50% + 8px));}"
        "\n  html:not(.mobile) #ef-panel.open{opacity:1;pointer-events:auto;transform:translateY(-50%);}"
        "\n  html.mobile #ef-panel{left:10px;right:10px;bottom:calc(66px + env(safe-area-inset-bottom, 0px));"
        "z-index:450;max-height:min(60dvh,470px);transform:translateY(8px);}"
        "\n  html.mobile #ef-panel.open{opacity:1;pointer-events:auto;transform:none;}"
        "\n  #ef-panel .ef-head{display:flex;justify-content:space-between;align-items:center;"
        "font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);"
        "margin:0 2px 6px;min-height:20px;}"
        "\n  #ef-clear{font:inherit;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);"
        "background:none;border:0;cursor:pointer;padding:2px 4px;}"
        "\n  #ef-clear[hidden]{display:none;}"
        "\n  #ef-panel .ef-sec{margin:0 0 12px;}"
        "\n  #ef-panel .ef-h{font-size:10px;letter-spacing:.14em;text-transform:uppercase;"
        "color:var(--muted);margin:2px 2px 7px;}"
        "\n  #ef-panel .ef-chips{display:flex;flex-wrap:wrap;gap:6px;}"
        "\n  .ef-chip{display:inline-flex;align-items:center;gap:7px;box-sizing:border-box;"
        "padding:6px 10px;border-radius:999px;cursor:pointer;font:inherit;font-size:12.5px;"
        "line-height:1.2;color:var(--text);text-align:left;background:transparent;"
        "border:1.4px solid color-mix(in srgb, var(--c) 50%, transparent);}"
        "\n  .ef-chip:hover{background:color-mix(in srgb, var(--c) 10%, transparent);}"
        "\n  .ef-chip.active{background:color-mix(in srgb, var(--c) 24%, transparent);"
        "border-color:var(--c);}"
        "\n  .ef-sym{display:inline-flex;color:var(--c);font-size:15px;line-height:1;}"
        "\n  .ef-sym svg{width:1em;height:1em;}"
        "\n  .ef-line{display:inline-block;width:14px;height:3px;border-radius:2px;}"
        "\n  .ef-count{opacity:.5;font-size:.85em;}"
        "\n  html.printing #filter-toggle, html.printing #ef-panel{display:none !important;}")
