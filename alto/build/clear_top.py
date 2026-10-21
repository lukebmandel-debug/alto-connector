"""The top bars without their glass (Luke, 2026-10-21, after the sample on his Torts System).

On a desktop timeline of any format the title bar and the unit / chip bar keep everything on them
(the clef, the name, the wordmark, the chips) but lose their tinted glass: the wallpaper (or picture)
runs up to the top of the window, and so does the board, with nothing ending where the bars were. Detail pages keep
the bars as they were (html.detail-open).

The engine pins #canvas under the nav (alignInfo: an inline !important top). Here #canvas starts at
the top instead, padded down by the bars' height so it still opens below them, with a detail page open the engine's own place stands, and phones keep their own layout.
"""

CSS = r"""
/* main timeline / project pages only (Luke, 2026-10-21: "we can revert the top bars to how they were before for [detail pages], we
   just don't want top bars on main timeline/project pages"): every rule below is off while a detail page is open */
html.alto-clear-top:not(.mobile):not(.detail-open) :is(#title-bar,#nav,#node-nav-bar):not(#_){background:transparent !important;-webkit-backdrop-filter:none !important;
  backdrop-filter:none !important;box-shadow:none !important;border-color:transparent !important;}
html.alto-clear-top:not(.mobile):not(.detail-open) :is(#title-bar,#nav,#node-nav-bar):not(#_)::before,html.alto-clear-top:not(.mobile):not(.detail-open) :is(#title-bar,#nav,#node-nav-bar):not(#_)::after{
  background:transparent !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;box-shadow:none !important;}
html.alto-clear-top.alto-bg:not(.mobile):not(.detail-open) #page-bg::before{top:-40px !important;}
/* the board still opens below the bars and anything scrolled into view lands below them: it slides beneath only as it scrolls */
html.alto-clear-top:not(.mobile):not(.detail-open) #canvas{padding-top:var(--nav-bottom,0px);scroll-padding-top:var(--nav-bottom,0px);}
html.alto-clear-top:not(.mobile):not(.detail-open) #lanes-ov-sky{top:0 !important;}   /* (lanes_nav.py: the zoomed-out backdrop, under the bars too) */
/* each thing on the bars keeps itself legible over whatever scrolls under it: the chips have their own glass already;
   the name and the group labels get a light pad of the same frosted glass, nothing more (the clef and the wordmark
   stand as on the homepage: Luke, "like other toggles … but use it sparingly"). Retro's Star chart restyles its own. */
html.alto-clear-top:not(.mobile):not(.detail-open) :is(#title-text,.nav-group-label){
  background:color-mix(in srgb,var(--surface,#fff) 42%,transparent);-webkit-backdrop-filter:blur(10px) saturate(160%);backdrop-filter:blur(10px) saturate(160%);
  --ct-g:color-mix(in srgb,var(--surface,#fff) 42%,transparent);box-shadow:0 0 0 var(--ct-pad,5px) var(--ct-g);}   /* the pad is a spread, not padding: no box moves */
html.alto-clear-top:not(.mobile):not(.detail-open) #title-text{--ct-pad:6px;border-radius:999px;}
html.alto-clear-top:not(.mobile):not(.detail-open) .nav-group-label{--ct-pad:3px;border-radius:4px;}
/* the bars are see-through now, the board under them: a click there reaches the board unless it is on a control */
html.alto-clear-top:not(.mobile):not(.detail-open) :is(#title-bar,#nav,#node-nav-bar),html.alto-clear-top:not(.mobile):not(.detail-open) :is(#title-bar,#nav,#node-nav-bar) *{pointer-events:none;}
html.alto-clear-top:not(.mobile):not(.detail-open) :is(#title-bar,#nav,#node-nav-bar) :is(button,a,input,select,textarea,label,svg,[role=button],[onclick],[tabindex],#title-text),
html.alto-clear-top:not(.mobile):not(.detail-open) :is(#title-bar,#nav,#node-nav-bar) :is(button,a,svg,[role=button],[onclick]) *{pointer-events:auto;}
/* the chips' own collapse (Luke): a little x in line with the chips, just before the first. Clicked, it spins like a wheel and winds
   the chips into itself like a tape measure, coming to rest as a + (the nearest first, the far ones travelling longest), and turned back it runs them
   out again; on the timeline and its detail pages alike, kept per viewer; the row keeps its height */
html.ct-chips-off:not(.mobile):not(.detail-open) #nav>*{visibility:hidden !important;}
#ct-chips{position:fixed;z-index:120;left:-100px;width:22px;height:22px;margin-top:-11px;border-radius:50%;padding:0;display:flex;align-items:center;justify-content:center;
  cursor:pointer;color:var(--muted);border:1px solid var(--card-glass-border,var(--border));background:color-mix(in srgb,var(--surface,#fff) 55%,transparent);
  -webkit-backdrop-filter:blur(10px) saturate(160%);backdrop-filter:blur(10px) saturate(160%);transition:color .12s;}
#ct-chips:hover{color:var(--text);}
#ct-chips .rl{transform-origin:12px 12px;transform-box:view-box;}
html.ct-chips-off #ct-chips .rl{transform:rotate(45deg);}
html.mobile #ct-chips,html.detail-open #ct-chips{display:none;}   /* (Luke: detail pages keep their bars, and their chips) */
@media print{ #ct-chips{display:none !important;} }
"""

JS = r"""(function(){
  var de=document.documentElement; if(de.classList.contains('mobile')) return;
  de.classList.add('alto-clear-top');
  function sync(){ var c=document.getElementById('canvas'); if(!c) return;
    var on=!de.classList.contains('mobile') && !de.classList.contains('detail-open'), t=c.style.getPropertyValue('top');
    if(on){ if(t!=='0px'){ c._ctT=t; c.style.setProperty('top', '0px', 'important'); } }   /* (the board still opens under the bars: it slides beneath them only as it scrolls) */
    else if(t==='0px' && c._ctT){ c.style.setProperty('top', c._ctT, 'important'); } }
  if(typeof MutationObserver==='function'){ var c=document.getElementById('canvas');
    if(c) new MutationObserver(sync).observe(c, {attributes:true, attributeFilter:['style']});
    new MutationObserver(sync).observe(de, {attributes:true, attributeFilter:['class']}); }
  sync();
  /* the chips' reel, centred on the chip row (its place follows the row) */
  var nav=document.getElementById('nav'); if(!nav || !nav.querySelector('button')) return;
  var K='alto-chips-off', off=false, busy=false; try{ off=localStorage.getItem(K)==='1'; }catch(e){}
  var bt=document.createElement('button'); bt.type='button'; bt.id='ct-chips';
  bt.innerHTML='<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><g class="rl"><path d="M6 6l12 12M18 6 6 18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></g></svg>';   /* an x; spun shut it rests as a + */
  var reel=bt.querySelector('.rl');
  function label(){ bt.setAttribute('aria-pressed', off ? 'true' : 'false'); bt.title=off ? 'Show the chips' : 'Hide the chips'; bt.setAttribute('aria-label', bt.title); }
  function place(){ var f=nav.querySelector('button.nav-btn') || items()[0], g=items()[0]; if(!f) return; var gl=g ? g.getBoundingClientRect().left : 0; var r=f.getBoundingClientRect();     /* in line with the chips: just before the first (hidden ones keep their place) */
    if(!r.width) return; var z=bt.offsetWidth ? (bt.getBoundingClientRect().width/bt.offsetWidth || 1) : 1;      /* (the page's own zoom, .8: screen px -> css px) */
    bt.style.top=Math.round((r.top+r.height/2)/z)+'px'; bt.style.left=Math.max(6, Math.round(Math.min(r.left, gl || r.left)/z-22-8))+'px'; }   /* (centred on a chip, before the row's first item) */
  function items(){ return [].filter.call(nav.querySelectorAll('button,.nav-group-label'), function(e){ return e.offsetWidth && !(e.parentElement && e.parentElement.closest('#nav button')); }); }
  function quiet(){ try{ return matchMedia('(prefers-reduced-motion: reduce)').matches; }catch(e){ return false; } }
  function turn(){
    if(busy) return; off=!off; try{ localStorage.setItem(K, off ? '1' : '0'); }catch(x){} label();
    if(quiet() || typeof Element.prototype.animate!=='function'){ de.classList.toggle('ct-chips-off', off); return; }
    if(!off) de.classList.remove('ct-chips-off');
    var b=bt.getBoundingClientRect(), hx=b.left+b.width/2, its=items(), T=0, anims=[];
    its.forEach(function(e){ var r=e.getBoundingClientRect(), dx=hx-(r.left+r.width/2), d=Math.abs(dx), ms=Math.min(720, 160+d*.45); T=Math.max(T, ms);
      var away={transform:'translateX('+dx.toFixed(1)+'px) scaleX(.06)', opacity:0}, home={transform:'none', opacity:1};
      anims.push(e.animate(off ? [home, away] : [away, home], {duration:ms, easing:off ? 'cubic-bezier(.55,0,.85,.4)' : 'cubic-bezier(.15,.6,.3,1)', fill:'both'})); });
    var turns=45+360*Math.max(1, Math.round(T/360));      /* the x turns like a wheel as they wind in, and lands a + (and back) */
    reel.animate(off ? [{transform:'rotate(0deg)'}, {transform:'rotate('+turns+'deg)'}] : [{transform:'rotate('+turns+'deg)'}, {transform:'rotate(0deg)'}], {duration:T, easing:'cubic-bezier(.3,0,.3,1)'});
    busy=true;
    setTimeout(function(){ busy=false; if(off) de.classList.add('ct-chips-off'); anims.forEach(function(a){ a.cancel(); }); }, T+20);
  }
  bt.addEventListener('click', function(e){ e.stopPropagation(); turn(); });
  document.body.appendChild(bt); de.classList.toggle('ct-chips-off', off); label(); place();
  window.addEventListener('resize', place); setTimeout(place, 300); setTimeout(place, 1200); if(document.fonts && document.fonts.ready) document.fonts.ready.then(place);   /* (after the row's own layout settles) */
  if(typeof ResizeObserver==='function') new ResizeObserver(function(){ requestAnimationFrame(place); }).observe(nav);   /* (a frame later: never a change inside the observer's own pass) */
})();"""


def block() -> str:
    return '<style id="alto-clear-top-css">' + CSS + '</style><script id="alto-clear-top-js">' + JS + "</script>"
