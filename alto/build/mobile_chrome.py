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
    tab.id='search-toggle'; tab.type='button'; tab.setAttribute('aria-label','Find');
    tab.innerHTML='<svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11.4" cy="8.6" r="5.6"></circle><line x1="7.44" y1="12.56" x2="3.3" y2="16.7"></line></svg><span>FIND</span>';
    var p=document.createElement('div'); p.id='msp'; p.setAttribute('role','dialog'); p.setAttribute('aria-label','Find');
    p.innerHTML='<div id="msp-head"><span id="msp-label">Find</span><button id="msp-close" type="button" aria-label="Close">&#x2715;</button></div>'+
      '<div id="msp-field"><input id="msp-input" type="text" autocomplete="off" autocorrect="off" spellcheck="false" placeholder="Search"></div>'+
      '<div id="msp-results"></div>';
    document.body.appendChild(p); document.body.appendChild(tab);
    var input=p.querySelector('#msp-input'), results=p.querySelector('#msp-results'), lastRes=[], pageRes=[], deb=null;
    function esc(s){ return String(s==null?'':s).replace(/[&<>]/g,function(c){ return c==='&'?'&amp;':(c==='<'?'&lt;':'&gt;'); }); }
    // What this detail page itself says: every paragraph or row that carries the
    // words, with the heading it sits under. Read from the page as it is, so it
    // covers authored sections and the generated ones alike.
    function pageMatches(q){
      var dc=document.getElementById('detail-content'); if(!dc) return [];
      var ql=q.toLowerCase(), out=[];
      dc.querySelectorAll('p, li, .doc-row, .doc-rel, .hc-row, .detail-name').forEach(function(el){
        if(out.length>=12) return;
        if(el.querySelector('p, li, .doc-row, .doc-rel, .hc-row')) return;      // the smallest block that matches
        var tx=(el.textContent||'').replace(/\s+/g,' ').trim();
        var i=tx.toLowerCase().indexOf(ql); if(i<0) return;
        var sec=el.closest('.detail-section'), h=sec&&sec.querySelector('h3');
        var a=Math.max(0,i-50), b=Math.min(tx.length,i+ql.length+80);
        var snip=(a>0?'…':'')+esc(tx.slice(a,i))+'<mark>'+esc(tx.slice(i,i+ql.length))+'</mark>'+esc(tx.slice(i+ql.length,b))+(b<tx.length?'…':'');
        out.push({el:el, where:h?h.textContent.trim():'This page', snip:snip});
      });
      return out;
    }
    function render(q){
      var core=window._altoSearchCore;
      q=(q||'').trim(); results.innerHTML=''; pageRes=[]; lastRes=[];
      if(q.length<2) return;
      var frag='';
      pageRes=pageMatches(q);
      frag+='<div class="msp-h">On this page</div>';
      if(!pageRes.length) frag+='<div class="search-empty">Nothing on this page.</div>';
      pageRes.forEach(function(o,i){
        frag+='<button type="button" class="search-result" data-pg="'+i+'"><span class="sr-kind">'+esc(o.where)+'</span><span class="sr-snip">'+o.snip+'</span></button>';
      });
      frag+='<div class="msp-h">Whole timeline</div>';
      if(core){
        var res=core.search(q); lastRes=res; var ql=q.toLowerCase();
        if(!res.length) frag+='<div class="search-empty">No matches.</div>';
        res.forEach(function(o,i){
          frag+='<button type="button" class="search-result" data-i="'+i+'"><span class="sr-kind">'+o.r.kind+'</span><span class="sr-title">'+core.esc(o.r.title)+'</span><span class="sr-snip">'+core.snippet(o.r.text,ql)+'</span></button>';
        });
      }
      results.innerHTML=frag;
    }
    // The panel follows the visual viewport, so when iOS pans the page for the
    // keyboard it stays on screen instead of exposing what is behind it.
    var vv=window.visualViewport;
    function fit(){
      if(!vv||!p.classList.contains('open')) return;
      p.style.height=vv.height+'px'; p.style.top=vv.offsetTop+'px'; p.style.bottom='auto';
    }
    if(vv){ vv.addEventListener('resize',fit); vv.addEventListener('scroll',fit); }
    function open(v){
      p.classList.toggle('open', v); root.classList.toggle('msp-open', v);
      if(v){ fit(); try{ input.focus({preventScroll:true}); }catch(e){} }
      else { input.blur(); input.value=''; results.innerHTML=''; p.style.height=''; p.style.top=''; p.style.bottom=''; }
    }
    tab.addEventListener('click', function(e){ e.stopPropagation(); open(true); });
    p.querySelector('#msp-close').addEventListener('click', function(){ open(false); });
    input.addEventListener('input', function(){ if(deb) clearTimeout(deb); var v=input.value; deb=setTimeout(function(){ render(v); },120); });
    input.addEventListener('keydown', function(e){ if(e.key==='Enter'){ var f=results.querySelector('.search-result'); if(f) f.click(); } });
    // Only the results scroll. Everything else is pinned, and scrolling the
    // results puts the keyboard away so the field and its caret stay put.
    p.addEventListener('touchmove', function(e){
      if(!e.target.closest('#msp-results')) e.preventDefault();
      else if(document.activeElement===input) input.blur();
    }, {passive:false});
    results.addEventListener('click', function(e){
      var b=e.target && e.target.closest ? e.target.closest('.search-result') : null; if(!b) return;
      if(b.hasAttribute('data-pg')){
        var o=pageRes[parseInt(b.getAttribute('data-pg'),10)]; if(!o) return;
        open(false);
        setTimeout(function(){
          try{ o.el.scrollIntoView({block:'center'}); o.el.classList.add('search-flash-ov'); setTimeout(function(){ o.el.classList.remove('search-flash-ov'); },1700); }catch(_){}
        },260);
        return;
      }
      var r=lastRes[parseInt(b.getAttribute('data-i'),10)]; if(!r) return;
      open(false);
      if(typeof window._mSearchNavigate==='function') window._mSearchNavigate(r.r);
    });
    // Leaving the detail page takes the panel with it.
    new MutationObserver(function(){ if(!root.classList.contains('detail-open')) open(false); })
      .observe(root, {attributes:true, attributeFilter:['class']});
    // Swipe left to put it away, as INFO does.
    var tries=0;
    (function wire(){
      if(typeof window._altoPanelSwipe!=='function'){ if(++tries<80) setTimeout(wire,250); return; }
      window._altoPanelSwipe(p,{swipeSign:-1,closeVal:'translateX(-100%)',noButtonGuard:true,
        isOpen:function(){ return p.classList.contains('open'); }, closeFn:function(){ open(false); }});
    })();
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
    "width:38px;height:49px;box-sizing:border-box;padding:10px 0;"
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
    "overflow:hidden;background:linear-gradient(var(--panel-glass-bg),var(--panel-glass-bg)), var(--nav-bg);"
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
    "\n  html.mobile #msp-results{flex:1;min-height:0;overflow-y:auto;-webkit-overflow-scrolling:touch;"
    "overscroll-behavior:contain;padding:4px 0 40px;}"
    "\n  html.mobile #msp-results .msp-h{font-size:10px;letter-spacing:.16em;text-transform:uppercase;"
    "color:var(--muted);padding:14px 18px 4px;font-family:-apple-system,BlinkMacSystemFont,sans-serif;}"
    "\n  html.mobile #msp-results mark{background:color-mix(in srgb, var(--accent) 28%, transparent);color:inherit;}"
    "\n  html.msp-open, html.msp-open body{overflow:hidden !important;overscroll-behavior:none;}"
    "\n  html.mobile #msp-results .search-result{display:block;width:100%;text-align:left;"
    "background:transparent;border:none;padding:12px 18px;cursor:pointer;"
    "font-family:Georgia,'Times New Roman',serif;color:var(--text);-webkit-tap-highlight-color:transparent;}"
    "\n  html.mobile #msp-results .sr-kind{display:block;}"
    "\n  html.mobile #msp-results .sr-title{font-size:15px;display:block;}"
    "\n  html.mobile #msp-results .sr-snip{font-size:12.5px;display:block;white-space:normal;overflow-wrap:anywhere;}"
    "\n  html.mobile #msp-results .search-empty{padding:16px 18px;color:var(--muted);}"
    "\n  html.printing #search-toggle, html.printing #msp{display:none !important;}")
