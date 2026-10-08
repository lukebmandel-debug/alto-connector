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

Nothing else shows what is filtered (the engine's bar of active filters across
the top of the page is gone): the toggle's count says how many are on. A
double-click (a double-tap on a phone) on the toggle switches every filter off,
and the next one brings back exactly what was on.
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
  // The sections are read from FILTER_SECTIONS / FILTER_NODES each time, so
  // manual edit mode can change them and redraw (window._altoFilterRedraw).
  function secs(){ return window.FILTER_SECTIONS||[]; }
  if(secs().length) root.classList.add('has-filter-tab');
  var sel={}, slotState={};
  function syncSel(){
    var keep={};
    secs().forEach(function(s){
      if(s.kind!=='chips') return; keep[s.key]=1;
      var ids={}; s.items.forEach(function(it){ ids[it.id]=1; });
      if(!sel[s.key]) sel[s.key]={};
      Object.keys(sel[s.key]).forEach(function(v){ if(!ids[v]) delete sel[s.key][v]; });
    });
    Object.keys(sel).forEach(function(k){ if(!keep[k]) delete sel[k]; });
  }
  syncSel();
  function chipKeys(){ return Object.keys(sel).filter(function(k){ return Object.keys(sel[k]).length>0; }); }
  function keep(id){
    var ks=chipKeys();
    for(var i=0;i<ks.length;i++){
      var m=(window.FILTER_NODES||{})[ks[i]]||{}, ok=false;
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
    secs().forEach(function(s){ if(s.kind==='slot' && slotVal(s.slot)) n++; });
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
        var s=secs().filter(function(x){ return x.key===k; })[0];
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
  function fill(body){
    body.innerHTML='';
    secs().forEach(function(s){
      var sec=document.createElement('div'); sec.className='ef-sec'; sec.setAttribute('data-sec', s.key);
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
      sec.appendChild(list); body.appendChild(sec);
    });
    try{ document.dispatchEvent(new CustomEvent('alto-filter-drawn')); }catch(e){}
  }
  // Every filter off: the panel's "Clear all", and the double-click.
  function clearAll(){
    Object.keys(sel).forEach(function(k){ sel[k]={}; });
    secs().forEach(function(s){
      if(s.kind!=='slot') return; var v=slotVal(s.slot); if(!v) return;
      if(mobile()){ if(window.setMobileFilter) window.setMobileFilter(s.slot, v); }
      else if(window.filterCanvas) window.filterCanvas(s.slot, v);
    });
    Array.prototype.forEach.call(activeLines(), function(b){ b.click(); });
    refresh(); refeature();
  }
  // What a double-click switched off, to put back by the next one: the chips
  // picked, each declared filter's value, the lines isolated.
  var stash=null;
  function snapshot(){
    var o={chips:{}, slots:{}, lines:[]};
    chipKeys().forEach(function(k){ o.chips[k]=Object.keys(sel[k]); });
    secs().forEach(function(s){ if(s.kind==='slot'){ var v=slotVal(s.slot); if(v) o.slots[s.slot]=v; } });
    Array.prototype.forEach.call(activeLines(), function(b){ o.lines.push(b.getAttribute('data-rel-key')); });
    return o;
  }
  function restore(o){
    Object.keys(o.chips).forEach(function(k){ if(sel[k]) o.chips[k].forEach(function(id){ sel[k][id]=1; }); });
    Object.keys(o.slots).forEach(function(slot){
      if(slotVal(slot)===o.slots[slot]) return;
      if(mobile()){ if(window.setMobileFilter) window.setMobileFilter(slot, o.slots[slot]); }
      else if(window.filterCanvas) window.filterCanvas(slot, o.slots[slot]);
    });
    o.lines.forEach(function(k){
      var b=document.querySelector('#ef-panel .line-key-btn[data-rel-key="'+k+'"]');
      if(b && !b.classList.contains('active')) b.click();
    });
    refresh(); refeature();
  }
  function quickToggle(){
    if(activeCount()>0){ stash=snapshot(); clearAll(); }
    else if(stash){ var o=stash; stash=null; restore(o); }
  }
  function open(v){
    var panel=document.getElementById('ef-panel'), tab=document.getElementById('filter-toggle'); if(!panel) return;
    panel.classList.toggle('open', v); if(tab) tab.setAttribute('aria-expanded', v?'true':'false');
  }
  window._altoFilterOpen=open;
  function build(){
    if(document.getElementById('filter-toggle')) return;
    // Nothing to filter by: no tab (manual edit mode draws it once there is).
    if(!secs().length && !window._altoFilterWanted) return;
    root.classList.add('has-filter-tab');
    var tab=document.createElement('button');
    tab.id='filter-toggle'; tab.type='button';
    tab.title='Filter \u2014 double-click to switch filters off or on'; tab.setAttribute('aria-label','Filter'); tab.setAttribute('aria-expanded','false');
    tab.innerHTML='<svg viewBox="0 0 20 20" width="17" height="17" style="display:block" fill="currentColor" aria-hidden="true"><path d="M2 3.5h16l-6.2 7.4v5.1l-3.6 1.9v-7z"/></svg><span>FILTER</span>';
    var panel=document.createElement('div');
    panel.id='ef-panel'; panel.setAttribute('role','dialog'); panel.setAttribute('aria-label','Filter');
    var head=document.createElement('div'); head.className='ef-head';
    var ttl=document.createElement('span'); ttl.textContent='Filter';
    var clr=document.createElement('button'); clr.type='button'; clr.id='ef-clear'; clr.hidden=true; clr.textContent='Clear all';
    var cls=document.createElement('button'); cls.type='button'; cls.id='ef-close'; cls.setAttribute('aria-label','Close'); cls.innerHTML='&#x2715;';
    var act=document.createElement('span'); act.className='ef-act'; act.appendChild(clr); act.appendChild(cls);
    head.appendChild(ttl); head.appendChild(act); panel.appendChild(head);
    // The sections scroll in a body of their own, under a header that stays
    // put without being sticky (Safari paints its status-bar strip flat over
    // a sticky header; see engine_patches.py, mobile-runway-behind-bars).
    var body=document.createElement('div'); body.className='ef-body'; panel.appendChild(body);
    fill(body);
    document.body.appendChild(panel);
    var rail=document.getElementById('tab-rail');
    (rail && !mobile() ? rail : document.body).appendChild(tab);
    // A click opens or closes the panel at once, with no wait to see whether a
    // second is coming. If one is, within 400ms and on the same spot, it is a
    // double-click: the panel goes back to how it was and the filters switch
    // off or on. The second one is caught on the document in the capture phase,
    // by its touch as well as its click: on a phone the sheet is already
    // sliding over the tile, and WebKit sends that second tap no click at all.
    var firstAt=0, firstBox=null, wasOpen=false, hush=0;
    function second(x, y){
      if(!firstAt || Date.now()-firstAt>400) return false;
      var r=firstBox;
      if(!r || x<r.left-6 || x>r.right+6 || y<r.top-6 || y>r.bottom+6) return false;
      firstAt=0; hush=Date.now()+700;
      open(wasOpen); quickToggle();
      return true;
    }
    tab.addEventListener('click', function(e){
      e.stopPropagation();
      firstAt=Date.now(); firstBox=tab.getBoundingClientRect();
      wasOpen=panel.classList.contains('open');
      open(!wasOpen);
    });
    document.addEventListener('touchend', function(e){
      var t=e.changedTouches && e.changedTouches[0];
      if(t && second(t.clientX, t.clientY)) e.preventDefault();      // no click, no double-tap zoom
    }, {capture:true, passive:false});
    document.addEventListener('click', function(e){
      if(Date.now()<hush || second(e.clientX, e.clientY)){ e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation(); }
    }, true);
    cls.addEventListener('click', function(){ open(false); });
    clr.addEventListener('click', clearAll);
    document.addEventListener('click', function(e){
      if(panel.classList.contains('open') && !e.target.closest('#ef-panel') && !e.target.closest('#filter-toggle')) open(false);
    });
    document.addEventListener('keydown', function(e){ if(e.key==='Escape') open(false); });
    // Swipe left to put it away on a phone, as INFO does.
    var stries=0;
    (function wire(){
      if(!mobile()) return;
      if(typeof window._altoPanelSwipe!=='function'){ if(++stries<80) setTimeout(wire,250); return; }
      window._altoPanelSwipe(panel,{swipeSign:-1,closeVal:'translateX(-100%)',noButtonGuard:true,
        isOpen:function(){ return panel.classList.contains('open'); }, closeFn:function(){ open(false); }});
    })();
    // A detail page or the overview covers the timeline; the panel goes with it.
    new MutationObserver(function(){
      if(root.classList.contains('detail-open') || root.classList.contains('summary-open')) open(false);
    }).observe(root, {attributes:true, attributeFilter:['class']});
  }
  // Draw the panel again from FILTER_SECTIONS (manual edit mode changed them).
  // A slot filter or a line that is no longer offered is switched off first.
  window._altoFilterRedraw=function(){
    var have={}; secs().forEach(function(s){ have[s.key]=s; });
    Object.keys(slotState).forEach(function(slot){
      var s=have['slot-'+slot], v=slotState[slot];
      if(!s || !s.items.some(function(it){ return it.id===v; })){ if(window.filterCanvas) window.filterCanvas(slot, v); }
    });
    var lines=have.lines;
    Array.prototype.forEach.call(activeLines(), function(b){
      var k=b.getAttribute('data-rel-key'); if(!lines || !lines.items.some(function(it){ return it.id===k; })) b.click(); });
    syncSel();
    var panel=document.getElementById('ef-panel'), tab=document.getElementById('filter-toggle');
    if(!panel) build();
    else fill(panel.querySelector('.ef-body'));
    tab=document.getElementById('filter-toggle');
    var want=!!(secs().length || window._altoFilterWanted);
    if(tab) tab.style.display=want ? '' : 'none';
    root.classList.toggle('has-filter-tab', want);
    refresh(); refeature();
  };
  document.addEventListener('click', function(e){
    var b=e.target && e.target.closest && e.target.closest('#ef-panel .ef-chip[data-fs]');
    if(!b) return;
    if(window._altoFilterChipClick && window._altoFilterChipClick(e, b)) return;
    var k=b.getAttribute('data-fs'), id=b.getAttribute('data-fid');
    if(sel[k]){
      e.preventDefault(); e.stopPropagation();
      if(sel[k][id]) delete sel[k][id]; else sel[k][id]=1;
      refresh(); refeature(); return;
    }
    var s=secs().filter(function(x){ return x.key===k; })[0];
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
  window._altoFilterRefresh=refresh;
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
        "\n  #filter-toggle{touch-action:manipulation;}"
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
        "\n  html.mobile #filter-toggle[data-n]:not([data-n=\"\"])::after{left:auto;right:-7px;}"
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
        # mobile: a full page in from the left, like INFO and Notes
        "\n  html.mobile #ef-panel{inset:0;width:auto;max-height:none;padding:0 0 40px;border-radius:0;"
        "border:0;z-index:401;opacity:1;transform:translateX(-100%);"
        "-webkit-backdrop-filter:blur(24px) saturate(185%);backdrop-filter:blur(24px) saturate(185%);"
        "box-shadow:none;transition:transform .22s cubic-bezier(.4,0,.2,1);-webkit-overflow-scrolling:touch;}"
        "\n  html.mobile #ef-panel.open{pointer-events:auto;transform:none;}"
        "\n  html.mobile #ef-panel{touch-action:manipulation;}"
        # opened directly (engine_patches.py, mobile-runway-behind-bars): no sticky header
        "\n  html.mobile.rw #ef-panel{display:flex;flex-direction:column;overflow:hidden;}"
        "\n  html.mobile.rw #ef-panel .ef-head{position:relative;flex:none;}"
        "\n  html.mobile.rw #ef-panel .ef-body{flex:1;min-height:0;overflow:auto;-webkit-overflow-scrolling:touch;"
        "padding-bottom:180px;}"
        "\n  html.mobile #ef-panel .ef-head{position:sticky;top:0;z-index:1;margin:0 0 12px;"
        "padding:16px 16px 12px;font-size:12px;letter-spacing:.14em;min-height:0;"
        "background:var(--panel-glass-bg);border-bottom:1px solid var(--header-hairline, var(--border));}"
        "\n  html.mobile #ef-panel .ef-sec{padding:0 16px;margin-bottom:18px;}"
        "\n  html.mobile #ef-panel .ef-chip{font-size:14px;padding:9px 14px;}"
        "\n  html.mobile #ef-panel .ef-h{font-size:11px;margin-bottom:9px;}"
        "\n  #ef-panel .ef-head{display:flex;justify-content:space-between;align-items:center;"
        "font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);"
        "margin:0 2px 6px;min-height:20px;}"
        "\n  #ef-panel .ef-act{display:flex;align-items:center;gap:10px;}"
        "\n  #ef-close{display:none;width:32px;height:32px;border-radius:50%;cursor:pointer;font-size:14px;"
        "align-items:center;justify-content:center;color:var(--text);letter-spacing:0;"
        "background:var(--card-glass-bg);border:1px solid var(--card-glass-border);}"
        "\n  html.mobile #ef-close{display:flex;}"
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
