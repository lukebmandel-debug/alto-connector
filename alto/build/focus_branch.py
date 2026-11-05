"""Focus on a branch: hold a card and what hangs from it, and leave the rest of the page alone.

Luke (L-1103-091725): "When a node is enlarged, a small button should show up just next to it that allows focus mode. This
mode does not dim out other nodes, but does something similar to how other nodes are when a node is enlarged. It allows the
user to navigate only through the node and children of that node, enlarged or unenlarged. All other branches stay in that
mode until that mode is deactivated, which should be very easy and apparent on how to do."  Rules he confirmed (Board
B-1103-091725): outside keeps the enlarged-card faded look (not the filter's dimming); outside is untouchable; one obvious
Exit focus button and Esc; Up stops at the focused card, Left / Right stay in the branch, Down goes to children; focus inside
focus, and Exit steps back one level; search and filters work only inside the branch; outlines and timelines, horizontal
too, and a phone gets the button and the behaviour (L-1103-091725); not remembered on reload.

How it is built, so the rest of the page needed almost nothing:

  * the branch is a card and its descendants (`window._ALTO_OUTLINE.kids`, or `window._altoBranchKids(id)`, which a format
    with its own children, the horizontal timeline's nested cards, sets). A page with no children (a plain timeline) holds
    the one card.
  * every step in every format already asks one question, "is this card shown under the filters?" (`window._altoShown`,
    filter_panel.py), and the phone's swipe, edge buttons and detail-page next / previous walk `_filteredOrder()`, which asks
    the same question when `_altoFilterOn()` says a filter is on. While a focus is held both answers are wrapped: outside the
    branch nothing is shown, so Up / Down / Left / Right, swipes and next / previous never leave it, and a filter or a
    search asks its question of the branch only. The wrappers are put on when a focus starts and taken off when the last one
    ends, so nothing of the page is touched at rest.
  * outside cards take the enlarged-card fade (opacity .14, as `#canvas.focus-mode` gives them) and `pointer-events:none`;
    the links between them fade the same; `enterFocus` / `featureNode` refuse them (search, the overview list and the like).
  * the button is one round glass button beside the enlarged card, only while a card is enlarged; the Exit pill sits low
    and centred for as long as a focus is held. Esc steps back one level (engine_patches: `_altoFocusEsc`, after the
    pop-ups and the detail page, before the card's own un-enlarge).
"""

CSS = r"""
/* focus on a branch (focus_branch.py) */
#af-btn,#af-exit{position:fixed;display:none;z-index:310;-webkit-tap-highlight-color:transparent;font-family:inherit;color:var(--text);cursor:pointer;
  background:var(--card-glass-bg,rgba(255,255,255,.7));border:1px solid var(--card-glass-border,rgba(127,127,127,.35));
  -webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);box-shadow:0 2px 10px rgba(0,0,0,.16);}
#af-btn{width:34px;height:34px;padding:0;border-radius:50%;align-items:center;justify-content:center;opacity:0;transition:opacity .22s,transform .15s;}
#af-btn.on{display:flex;}
#af-btn.on.in{opacity:1;}
#af-btn:hover,#af-btn:focus-visible{transform:scale(1.08);border-color:var(--accent,#6d5bd0);color:var(--accent,#6d5bd0);outline:none;}
#af-btn svg{width:19px;height:19px;display:block;}
#af-btn::after{content:attr(data-tip);position:absolute;left:50%;bottom:calc(100% + 7px);transform:translateX(-50%);white-space:nowrap;pointer-events:none;
  font:500 11.5px/1 -apple-system,system-ui,sans-serif;letter-spacing:.01em;padding:6px 9px;border-radius:7px;background:var(--text);color:var(--surface,#fff);opacity:0;transition:opacity .15s;}
#af-btn:hover::after,#af-btn:focus-visible::after{opacity:1;}
#af-exit{left:50%;bottom:22px;transform:translateX(-50%);z-index:420;align-items:center;gap:10px;height:40px;padding:0 16px 0 14px;border-radius:20px;
  font-size:13.5px;font-weight:600;letter-spacing:.01em;white-space:nowrap;max-width:calc(100vw - 32px);border-color:var(--accent,#6d5bd0);background:var(--accent,#6d5bd0);color:#fff;box-shadow:0 3px 14px rgba(0,0,0,.28);}
html.af-on #af-exit{display:flex;}
#af-exit:hover,#af-exit:focus-visible{filter:brightness(1.12);outline:2px solid #fff;outline-offset:2px;}
#af-exit svg{width:14px;height:14px;flex:none;}
#af-exit .af-who{font-weight:500;opacity:.9;max-width:30vw;overflow:hidden;text-overflow:ellipsis;}
#af-exit .af-esc{font-size:10.5px;font-weight:600;opacity:.9;border:1px solid currentColor;border-radius:4px;padding:1px 4px;}
html.detail-open #af-btn,html.detail-open #af-exit,html.printing #af-btn,html.printing #af-exit{display:none !important;}
html.alto-lanes #af-exit{bottom:76px;}
html.mobile #af-exit,html.phone-whole #af-exit{bottom:calc(70px + env(safe-area-inset-bottom,0px));}
html.mobile #af-exit .af-esc,html.phone-whole #af-exit .af-esc,html.mobile #af-btn::after,html.phone-whole #af-btn::after{display:none;}
/* outside the held branch: the enlarged card's faded look, and untouchable */
html.af-on #world .node.af-out{pointer-events:none !important;}
html.af-on:not(.mobile) #world .node.af-out .node-card{opacity:.14 !important;}
html.af-on:not(.mobile) #canvas.focus-mode .node:not(.focused):not(.af-out) .node-card{opacity:.42 !important;}
html.af-on:not(.mobile) #canvas :is(.phase-label,.phase-label-float,.unit-bar){opacity:.22 !important;transition:opacity .3s;}
html.af-on:not(.mobile) #canvas .phase-numeral{opacity:1 !important;}
html.af-on #river-svg [data-af-out]{opacity:.12 !important;transition:opacity .3s;}
@media (prefers-reduced-motion:reduce){#af-btn{transition:none;}}
"""

# The glyph: a viewfinder (four corners round a dot). The Exit mark: a cross.
BTN_SVG = ('<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'
           '<path d="M3 7V4.5A1.5 1.5 0 0 1 4.5 3H7M13 3h2.5A1.5 1.5 0 0 1 17 4.5V7M17 13v2.5a1.5 1.5 0 0 1-1.5 1.5H13M7 17H4.5A1.5 1.5 0 0 1 3 15.5V13"/>'
           '<circle cx="10" cy="10" r="2.1" fill="currentColor" stroke="none"/></svg>')
X_SVG = ('<svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 3l8 8M11 3l-8 8"/></svg>')

JS = r"""(function(){
  if(window._altoFocusBranch) return;
  var de=document.documentElement, W=document.getElementById('world'), CV=document.getElementById('canvas');
  if(!W||!CV) return;
  var TIP='Focus on this branch', stack=[], keep=null, origShown=null, origOn=null, hadShown=false, hadOn=false, B={}, edgeT=0;
  function $(i){ return document.getElementById(i); }
  function mobile(){ return de.classList.contains('mobile'); }
  function kidsOf(id){
    if(typeof window._altoBranchKids==='function'){ var k=window._altoBranchKids(id); if(k) return k; }
    return ((window._ALTO_OUTLINE||{}).kids||{})[id]||[];
  }
  function branch(root){
    var m={}, todo=[root];
    while(todo.length){ var i=todo.pop(); if(m[i]) continue; m[i]=1; kidsOf(i).forEach(function(c){ todo.push(c); }); }
    return m;
  }
  function active(){ return stack.length>0; }
  function root(){ return stack[stack.length-1]||null; }
  function has(id){ return !stack.length || !!B[id]; }
  function title(id){
    var e=$('node-'+id), t=e&&e.querySelector('.node-title'), s=t?(t.textContent||'').trim():'';
    if(!s && typeof NODES_SRC!=='undefined'){ NODES_SRC.forEach(function(n){ if(n.id===id) s=n.title||''; }); }
    return s||id;
  }
  function enlarged(){
    if(mobile()){ var f=window._featuredNodeId, e=f&&$('node-'+f); return e?f:null; }
    return window._focusedNodeId||null;
  }
  // ── the page: classes, the links, the two answers every step asks ──
  function edges(){
    edgeT=0; var svg=$('river-svg'); if(!svg) return;
    Array.prototype.forEach.call(svg.querySelectorAll('path[data-edge],path[data-edge-part]'), function(p){
      var ab=(p.getAttribute('data-edge')||p.getAttribute('data-edge-part')||'').split('|');
      if(active() && !(has(ab[0]) && has(ab[1]))) p.setAttribute('data-af-out','1'); else p.removeAttribute('data-af-out');
    });
  }
  var mo=null;
  // Classic: the Exit pill's ink follows the accent fill (whichever of dark ink and white reads better on it); Retro / Holographic set theirs in CSS
  function inkExit(ex){
    try{
      var m=(getComputedStyle(ex).backgroundColor||'').match(/[\d.]+/g); if(!m||m.length<3) return;
      var c=m.slice(0,3).map(function(v){ v=+v/255; return v<=.03928 ? v/12.92 : Math.pow((v+.055)/1.055,2.4); });
      var L=.2126*c[0]+.7152*c[1]+.0722*c[2];
      ex.style.color = L>.196 ? '#14122b' : '#fff';   // .196 = where the dark ink and white give the same ratio
    }catch(e){}
  }
  function apply(){
    de.classList.toggle('af-on', active());
    CV.classList.toggle('af-on', active());
    Array.prototype.forEach.call(W.querySelectorAll('.node'), function(n){ n.classList.toggle('af-out', active() && !B[n.id.slice(5)]); });
    edges();
    if(active() && !mo && window.MutationObserver && $('river-svg')){
      mo=new MutationObserver(function(){ if(!edgeT) edgeT=setTimeout(edges,60); }); mo.observe($('river-svg'),{childList:true});
    }
    if(!active() && mo){ mo.disconnect(); mo=null; }
    var ex=$('af-exit');
    if(ex){ inkExit(ex); var w=ex.querySelector('.af-who'); if(w) w.textContent=active()?title(root()):''; ex.setAttribute('aria-label','Exit focus'+(stack.length>1?' (back one level)':'')); }
    // a phone: the card's neighbours (the bar's previous / next names) are asked again under the new order
    if(mobile() && window._featuredNodeId && typeof window.featureNode==='function'){ try{ window.featureNode(window._featuredNodeId,false); }catch(e){} }
    sync(true);
  }
  function wrap(){
    hadShown=Object.prototype.hasOwnProperty.call(window,'_altoShown'); hadOn=Object.prototype.hasOwnProperty.call(window,'_altoFilterOn');
    origShown=window._altoShown; origOn=window._altoFilterOn;
    window._altoShown=function(id){ return !!B[id] && (typeof origShown!=='function' || origShown.apply(this,arguments)); };
    window._altoFilterOn=function(){ return true; };
  }
  function unwrap(){
    if(hadShown) window._altoShown=origShown; else delete window._altoShown;
    if(hadOn) window._altoFilterOn=origOn; else delete window._altoFilterOn;
    origShown=origOn=null;
  }
  function push(id){
    if(!id || !$('node-'+id)) return false;
    if(stack.length && !B[id]) return false;
    if(stack[stack.length-1]===id) return false;
    var first=!stack.length; if(first){ wrap(); guardAll(); }
    stack.push(id); B=branch(id); apply(); return true;
  }
  function pop(){
    if(!stack.length) return false;
    stack.pop();
    if(stack.length){ B=branch(root()); apply(); }
    else { B={}; unwrap(); apply(); }
    return true;
  }
  function clear(){ while(stack.length) pop(); }
  // outside is untouchable: nothing that enlarges or opens a card (search, the Map list, a link) gets past the branch. The engine puts its own
  // featureNode back on window after every call, so the guard is looked at again on every tick while a focus is held.
  function guard(name,type){
    var f=window[name]; if(typeof f!=='function' || f._af) return;
    var g=function(a,b){
      if(active()){ var id=type ? (a===type ? b : null) : a; if(typeof id==='string' && !B[id]) return; }
      return f.apply(this,arguments);
    };
    g._af=1; window[name]=g;
  }
  function guardAll(){ guard('enterFocus'); guard('featureNode'); guard('showDetail','node'); }

  // ── the button and the Exit pill ──
  var btn=null, last='', seen=0, shownFor=null;
  function build(){
    if(btn) return;
    btn=document.createElement('button'); btn.id='af-btn'; btn.type='button'; btn.setAttribute('data-tip',TIP); btn.setAttribute('aria-label',TIP); btn.title=TIP; btn.innerHTML=__BTN__;
    var ex=document.createElement('button'); ex.id='af-exit'; ex.type='button'; ex.title='Exit focus (Esc)';
    ex.innerHTML=__X__+'<span>Exit focus</span><span class="af-who"></span><span class="af-esc">Esc</span>';
    document.body.appendChild(btn); document.body.appendChild(ex);
    [btn,ex].forEach(function(b){
      ['pointerdown','mousedown','touchstart','dblclick'].forEach(function(t){ b.addEventListener(t,function(e){ e.stopPropagation(); }); });
    });
    btn.addEventListener('click',function(e){ e.stopPropagation(); e.preventDefault(); var id=enlarged(); if(id) push(id); });
    ex.addEventListener('click',function(e){ e.stopPropagation(); e.preventDefault(); pop(); });
  }
  function rect(id){
    var e=$('node-'+id), c=e&&e.querySelector('.node-card'); if(!c) return null;
    var r=c.getBoundingClientRect(); return r.width>20 ? r : null;
  }
  // the page is drawn under the desktop's page zoom (html{zoom}): a fixed box's left / top are in its px, not the screen's, so ask where one lands
  function zoomK(){
    btn.style.left='100px'; btn.style.top='100px'; var q=btn.getBoundingClientRect(); return q.left>0 ? q.left/100 : 1;
  }
  function place(r){
    var vw=window.innerWidth, vh=window.innerHeight, s=34*(zoomK()||1), x, y;
    if(mobile()){ x=r.right-s-6; y=r.top-s-8; if(y<56) y=Math.min(r.top+6, vh-s-8); }
    else { x=r.right+10; y=r.top; if(x+s>vw-8){ x=r.right-s-8; y=r.top-s-8; } if(y<8) y=r.top+8; }
    x=Math.max(8,Math.min(vw-s-8,x)); y=Math.max(8,Math.min(vh-s-8,y));
    var k=zoomK()||1; btn.style.left=Math.round(x/k)+'px'; btn.style.top=Math.round(y/k)+'px';
  }
  // Only while a card is enlarged, and only once it has landed (the same place on two looks in a row); gone the moment it is not.
  function sync(force){
    if(!btn) return;
    var id=enlarged(), det=de.classList.contains('detail-open'), show=!!id && !det && !(active() && root()===id);
    if(!show){ btn.classList.remove('on','in'); last=''; seen=0; shownFor=null; return; }
    var r=rect(id); if(!r){ btn.classList.remove('on','in'); return; }
    var k=id+'|'+Math.round(r.left)+','+Math.round(r.top)+','+Math.round(r.width);
    if(force && k!==last) seen=0;
    if(k===last){ seen++; } else { last=k; seen=0; btn.classList.remove('in'); if(shownFor!==id) btn.classList.remove('on'); }
    if(seen>=2 || (btn.classList.contains('on') && shownFor===id)){ btn.classList.add('on'); place(r); shownFor=id; requestAnimationFrame(function(){ if(btn.classList.contains('on') && last===k) btn.classList.add('in'); }); }
  }
  // Esc: one level back (the engine asks after its pop-ups and the detail page, before it un-enlarges the card)
  window._altoFocusEsc=function(e){
    if(!active()) return false;
    e.preventDefault(); e.stopImmediatePropagation(); pop(); return true;
  };
  // With a focus held and nothing enlarged, an arrow enlarges the focused card: the way back in
  window.addEventListener('keydown',function(e){
    if(!active() || mobile() || !/^Arrow/.test(e.key) || e.metaKey||e.ctrlKey||e.altKey) return;
    var t=e.target; if(t&&/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)||t&&t.isContentEditable) return;
    if(de.classList.contains('detail-open') || window._focusedNodeId || typeof window.enterFocus!=='function') return;
    e.preventDefault(); window.enterFocus(root());
  },true);
  // a card deleted under a held focus ends it (manual edit mode)
  function check(){ while(stack.length && !$('node-'+root())) pop(); }
  function boot(){ build(); setInterval(function(){ if(!btn) return; if(active()) guardAll(); check(); sync(); },110); }
  window._altoFocusBranch={push:push, pop:pop, clear:clear, active:active, root:root, has:has, depth:function(){ return stack.length; }, members:function(){ return Object.keys(B); }};
  if(document.readyState==='complete') boot(); else window.addEventListener('load',boot);
})();"""


def block() -> str:
    """The <style> and <script> for the end of a timeline's body (a plain timeline, an outline, the horizontal timeline)."""
    js = JS.replace("__BTN__", repr(BTN_SVG)).replace("__X__", repr(X_SVG))
    return '<style id="alto-focus-branch-css">' + CSS + '</style>\n<script id="alto-focus-branch">' + js + '</script>\n'
