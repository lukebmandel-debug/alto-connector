"""Search on a mobile detail page.

On the timeline the search field is a pill in the top row, between MAP and
MENU. A detail page has no room for it, so there it becomes a SEARCH tile where
INFO would sit (above the back tile) that opens a full-page panel from the left,
the way INFO and Notes open. The search itself is the timeline's own: the same
index, the same ranking, the same navigation.
"""

MSEARCH_PANEL_GLUE = """
(function(){
  if(window._altoMspBound) return; window._altoMspBound=1;
  var root=document.documentElement;
  if(!root.classList.contains('mobile')) return;
  function build(){
    if(document.getElementById('search-toggle')) return;
    var tab=document.createElement('button');
    tab.id='search-toggle'; tab.type='button'; tab.setAttribute('aria-label','Search');
    tab.innerHTML='<svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11.4" cy="8.6" r="5.6"></circle><line x1="7.44" y1="12.56" x2="3.3" y2="16.7"></line></svg><span>SEARCH</span>';
    var p=document.createElement('div'); p.id='msp'; p.setAttribute('role','dialog'); p.setAttribute('aria-label','Search');
    p.innerHTML='<div id="msp-head"><span id="msp-label">Search</span><button id="msp-close" type="button" aria-label="Close">&#x2715;</button></div>'+
      '<div id="msp-field"><input id="msp-input" type="text" autocomplete="off" spellcheck="false" placeholder="Search"></div>'+
      '<div id="msp-results"></div>';
    document.body.appendChild(p); document.body.appendChild(tab);
    var input=p.querySelector('#msp-input'), results=p.querySelector('#msp-results'), lastRes=[], deb=null;
    function render(q){
      var core=window._altoSearchCore; if(!core) return;
      q=(q||'').trim(); results.innerHTML='';
      if(q.length<2) return;
      var res=core.search(q); lastRes=res;
      if(!res.length){ results.innerHTML='<div class="search-empty">No matches.</div>'; return; }
      var ql=q.toLowerCase();
      res.forEach(function(o,i){
        var b=document.createElement('button'); b.type='button'; b.className='search-result'; b.setAttribute('data-i',i);
        b.innerHTML='<span class="sr-kind">'+o.r.kind+'</span><span class="sr-title">'+core.esc(o.r.title)+'</span><span class="sr-snip">'+core.snippet(o.r.text,ql)+'</span>';
        results.appendChild(b);
      });
    }
    function open(v){
      p.classList.toggle('open', v);
      if(v){ try{ input.focus({preventScroll:true}); }catch(e){} }
      else { input.blur(); input.value=''; results.innerHTML=''; }
    }
    tab.addEventListener('click', function(e){ e.stopPropagation(); open(true); });
    p.querySelector('#msp-close').addEventListener('click', function(){ open(false); });
    input.addEventListener('input', function(){ if(deb) clearTimeout(deb); var v=input.value; deb=setTimeout(function(){ render(v); },120); });
    input.addEventListener('keydown', function(e){ if(e.key==='Enter'){ var f=results.querySelector('.search-result'); if(f) f.click(); } });
    results.addEventListener('click', function(e){
      var b=e.target && e.target.closest ? e.target.closest('.search-result') : null; if(!b) return;
      var o=lastRes[parseInt(b.getAttribute('data-i'),10)]; if(!o) return;
      open(false);
      if(typeof window._mSearchNavigate==='function') window._mSearchNavigate(o.r);
    });
    // Leaving the detail page takes the panel with it.
    new MutationObserver(function(){ if(!root.classList.contains('detail-open')) open(false); })
      .observe(root, {attributes:true, attributeFilter:['class']});
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', build); else build();
})();"""

MSEARCH_PANEL_CSS = (
    # The pill gives way to the tile on a detail page.
    "\n  html.mobile.detail-open #m-search, html.mobile.detail-open #m-search-results{display:none !important;}"
    "\n  html:not(.mobile) #search-toggle, html:not(.mobile) #msp{display:none !important;}"
    # The tile: the INFO tile's twin, at INFO's height (above the back tile).
    "\n  html.mobile #search-toggle{display:none;position:fixed;left:0;"
    "bottom:calc(66px + env(safe-area-inset-bottom, 0px));z-index:295;"
    "min-width:36px;height:49px;box-sizing:border-box;padding:10px 4px;"
    "flex-direction:column;align-items:center;justify-content:center;gap:4px;"
    "background:var(--card-glass-bg);"
    "-webkit-backdrop-filter:blur(12px) saturate(170%);backdrop-filter:blur(12px) saturate(170%);"
    "border:1px solid var(--border);border-left:none;border-radius:0 6px 6px 0;"
    "box-shadow:0 10px 26px var(--node-rest-shadow), inset 0 0 0 0.5px var(--card-glass-rim);"
    "color:var(--text);font-size:8.5px;letter-spacing:.1em;text-transform:uppercase;"
    "font-family:-apple-system,BlinkMacSystemFont,sans-serif;cursor:pointer;"
    "-webkit-tap-highlight-color:transparent;transition:opacity .15s;}"
    "\n  html.mobile.detail-open #search-toggle{display:flex;}"
    "\n  html.mobile #search-toggle:active{opacity:.6;}"
    # The panel: full page, in from the left, like INFO.
    "\n  html.mobile #msp{position:fixed;inset:0;z-index:401;display:flex;flex-direction:column;"
    "background:var(--panel-glass-bg);"
    "-webkit-backdrop-filter:blur(24px) saturate(185%);backdrop-filter:blur(24px) saturate(185%);"
    "transform:translateX(-100%);pointer-events:none;"
    "transition:transform .22s cubic-bezier(.4,0,.2,1);}"
    "\n  html.mobile #msp.open{transform:none;pointer-events:auto;}"
    "\n  html.mobile #msp-head{display:flex;align-items:center;justify-content:space-between;"
    "padding:16px 16px 12px;border-bottom:1px solid var(--header-hairline, var(--border));flex-shrink:0;}"
    "\n  html.mobile #msp-label{font-size:12px;letter-spacing:.14em;text-transform:uppercase;"
    "color:var(--muted);font-family:-apple-system,BlinkMacSystemFont,sans-serif;}"
    "\n  html.mobile #msp-close{width:32px;height:32px;border-radius:50%;cursor:pointer;font-size:14px;"
    "display:flex;align-items:center;justify-content:center;color:var(--text);"
    "background:var(--card-glass-bg);border:1px solid var(--card-glass-border);}"
    "\n  html.mobile #msp-field{padding:14px 16px 6px;flex-shrink:0;}"
    "\n  html.mobile #msp-input{width:100%;box-sizing:border-box;height:44px;padding:0 16px;"
    "border-radius:22px;outline:none;font-size:16px;color:var(--text);"
    "font-family:Georgia,'Times New Roman',serif;"
    "background:var(--card-glass-bg);border:1px solid var(--card-glass-border);}"
    "\n  html.mobile #msp-input::placeholder{color:var(--muted);}"
    "\n  html.mobile #msp-results{flex:1;overflow-y:auto;-webkit-overflow-scrolling:touch;padding:4px 0 40px;}"
    "\n  html.mobile #msp-results .search-result{display:block;width:100%;text-align:left;"
    "background:transparent;border:none;padding:12px 18px;cursor:pointer;"
    "font-family:Georgia,'Times New Roman',serif;color:var(--text);-webkit-tap-highlight-color:transparent;}"
    "\n  html.mobile #msp-results .sr-kind{display:block;}"
    "\n  html.mobile #msp-results .sr-title{font-size:15px;display:block;}"
    "\n  html.mobile #msp-results .sr-snip{font-size:12.5px;display:block;white-space:normal;overflow-wrap:anywhere;}"
    "\n  html.mobile #msp-results .search-empty{padding:16px 18px;color:var(--muted);}"
    "\n  html.printing #search-toggle, html.printing #msp{display:none !important;}")
