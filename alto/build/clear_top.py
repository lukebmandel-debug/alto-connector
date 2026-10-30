"""The top bars without their glass (Luke, 2026-10-21, after the sample on his Torts System).

On a desktop timeline of any format the title bar and the unit / chip bar keep everything on them
(the clef, the name, the wordmark, the chips) but lose their tinted glass: the wallpaper (or picture)
runs up to the top of the window, and so does the board, with nothing ending where the bars were. Detail pages keep
the bars as they were (html.detail-open).

The engine pins #canvas under the nav (alignInfo: an inline !important top). Here #canvas starts at
the top instead, padded down by the bars' height so it still opens below them, with a detail page open the engine's own place stands, and phones keep their own layout.
"""

CSS = r"""
/* html.ct-on = html.alto-clear-top:not(.mobile):not(.detail-open), kept by the script below.
   main timeline / project pages only (Luke, 2026-10-21: "we can revert the top bars to how they were before for [detail pages], we
   just don't want top bars on main timeline/project pages"): every rule below is off while a detail page is open */
html.ct-on :is(#title-bar,#nav,#node-nav-bar):not(#_){background:transparent !important;-webkit-backdrop-filter:none !important;
  backdrop-filter:none !important;box-shadow:none !important;border-color:transparent !important;}
html.ct-on :is(#title-bar,#nav,#node-nav-bar):not(#_)::before,html.ct-on :is(#title-bar,#nav,#node-nav-bar):not(#_)::after{
  background:transparent !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;box-shadow:none !important;}
/* the board still opens below the bars and anything scrolled into view lands below them: it slides beneath only as it scrolls */
html.ct-on #canvas{padding-top:var(--nav-bottom,0px);scroll-padding-top:var(--nav-bottom,0px);}
/* a panel over the board runs the window's full height (Luke, 2026-10-30, his Torts Overview: "You see the problem at the top?
   Fix it across everything that is affected"): with no glass on the bars any more, a panel that began under them left the board
   showing above it as a cut strip, and the Overview's fixed height stopped short of the foot. Each starts at the top instead,
   its content padded down by the bars' height, and the chips float on its glass (the Notes rail's own z-index is higher than
   the bars', so while it is open they rise over it) */
/* (open only, and not on a phone held sideways, html.phone-whole: there the closed Overview is a shut accordion, not a panel
   parked off to the right, and sized to the window it would sit invisible over the board and take its touches) */
html.ct-on:not(.phone-whole) #summary-wrap.open:not(#_){top:0 !important;bottom:0 !important;height:auto !important;max-height:none !important;
  box-sizing:border-box;padding-top:var(--nav-bottom,0px);}
html.ct-on:not(.phone-whole) #notes-panel:not(#_){top:0 !important;bottom:0 !important;box-sizing:border-box;padding-top:var(--nav-bottom,0px);}
html.ct-on.np-open:not(.phone-whole) :is(#title-bar,#nav):not(#_){z-index:401;}
html.ct-on.np-open:not(.phone-whole) #ct-chips{z-index:402;}
/* each thing on the bars keeps itself legible over whatever scrolls under it: the chips have their own glass already;
   the name and the group labels get a light pad of the same frosted glass, nothing more (the clef and the wordmark
   stand as on the homepage: Luke, "like other toggles … but use it sparingly"). Retro's Star chart restyles its own. */
html.ct-on :is(#title-text,.nav-group-label){--ct-g:color-mix(in srgb,var(--surface,#fff) var(--ct-a,42%),transparent);
  background:var(--ct-g);-webkit-backdrop-filter:blur(10px) saturate(160%);backdrop-filter:blur(10px) saturate(160%);
  box-shadow:0 0 0 var(--ct-pad,6px) var(--ct-g);border-radius:999px;}   /* the pad is a spread, not padding: no box moves */
/* the chip groups' names (ELEMENT, AUTHORITIES …) stay readable over anything (Luke: "kind of impossible to read"): full strength
   in the theme's own ink, a size up, on a denser pad of the theme's surface, so ink and pad contrast whatever the background,
   picture or pattern is under them (Retro sets its own, retro.py) */
#nav .nav-group-label:not(#_){opacity:1;font-size:10px;font-weight:600;color:var(--text);
  --ct-a:80%;--ct-pad:3px;border-radius:4px;}
/* the bars are see-through now, the board under them: a click there reaches the board unless it is on a control */
html.ct-on :is(#title-bar,#nav,#node-nav-bar),html.ct-on :is(#title-bar,#nav,#node-nav-bar) *{pointer-events:none;}
html.ct-on :is(#title-bar,#nav,#node-nav-bar) :is(button,a,input,select,textarea,label,svg,[role=button],[onclick],[tabindex],#title-text),
html.ct-on :is(#title-bar,#nav,#node-nav-bar) :is(button,a,svg,[role=button],[onclick]) *{pointer-events:auto;}
/* the chips' own collapse (Luke): a little x in line with the chips, just before the first. Clicked, it spins like a wheel and winds
   the chips into itself like a tape measure, coming to rest as a + (the nearest first, the far ones travelling longest), and turned back it runs them
   out again; on the timeline and its detail pages alike, kept per viewer; the row keeps its height */
html.ct-on.ct-chips-off #nav>*{visibility:hidden !important;}
#ct-chips{position:fixed;z-index:120;left:-100px;width:22px;height:22px;margin-top:-11px;border-radius:50%;padding:0;display:flex;align-items:center;justify-content:center;
  cursor:pointer;color:var(--muted);border:1px solid var(--card-glass-border,var(--border));background:color-mix(in srgb,var(--surface,#fff) 55%,transparent);
  -webkit-backdrop-filter:blur(10px) saturate(160%);backdrop-filter:blur(10px) saturate(160%);transition:color .12s;}
#ct-chips:hover{color:var(--text);}
#ct-chips .rl{transform-origin:12px 12px;transform-box:view-box;}
html.ct-chips-off #ct-chips .rl{transform:rotate(45deg);}
html.mobile #ct-chips,html.detail-open #ct-chips{display:none;}   /* (Luke: detail pages keep their bars, and their chips) */
@media print{ #ct-chips{display:none !important;} }
"""

# the timeline's own unit-colour sheet, and the horizontal timeline's zoomed-out sky: a palace or a Star chart has neither
# (it hides #glass-slab), so they carry none of this
SHEET_CSS = r"""
html.ct-on #lanes-ov-sky{top:0 !important;}   /* (lanes_nav.py: the zoomed-out backdrop, under the bars too) */
/* the background runs to the top of the window (Luke, 2026-10-22: "having the background color cut off right there makes it look
   like there is a top bar again"): a picture is drawn from the top (backgrounds.py inset()), and the board's unit-colour sheet
   (#glass-slab, which starts just above the first unit) reaches up past the top of the window in the first unit's colour, as a
   border above its own box, so its gradient keeps its stops. A horizontal timeline's sheet is coloured left to right: its colours
   simply run up. Retro has no sheet. */
html.alto-clear-top:not(.mobile):not(.alto-retro) #glass-slab:not(#_){box-sizing:content-box !important;margin-top:-1200px;
  border-top:1200px solid var(--ct-c0,transparent) !important;background-clip:padding-box !important;}
html.alto-clear-top.alto-lanes:not(.mobile):not(.alto-retro) #glass-slab:not(#_){border-top-color:transparent !important;background-clip:border-box !important;background-origin:border-box !important;}
"""

JS = r"""(function(){
  var de=document.documentElement; if(de.classList.contains('mobile')) return;
  de.classList.add('alto-clear-top');
  function sync(){ var c=document.getElementById('canvas'); if(!c) return;
    var on=!de.classList.contains('mobile') && !de.classList.contains('detail-open'), t=c.style.getPropertyValue('top');
    de.classList.toggle('ct-on', on);   /* (html.ct-on: the bars are clear right now, a main page on a computer; the CSS above keys on it) */
    if(on){ if(t!=='0px'){ c._ctT=t; c.style.setProperty('top', '0px', 'important'); } }   /* (the board still opens under the bars: it slides beneath them only as it scrolls) */
    else if(t==='0px' && c._ctT){ c.style.setProperty('top', c._ctT, 'important'); } }
  if(typeof MutationObserver==='function'){ var c=document.getElementById('canvas');
    if(c) new MutationObserver(sync).observe(c, {attributes:true, attributeFilter:['style']});
    new MutationObserver(function(){ sync(); setTimeout(function(){ try{ place(); }catch(e){} }, 160); }).observe(de, {attributes:true, attributeFilter:['class']}); }   /* (edit mode adds a chip and re-centres the row: put the x clear of the first label again) */
  sync();
  __SHEET__
  /* the chips' reel, centred on the chip row (its place follows the row) */
  var nav=document.getElementById('nav'); if(!nav || !nav.querySelector('button')) return;
  var K='alto-chips-off', off=false, busy=false; try{ off=localStorage.getItem(K)==='1'; }catch(e){}
  var bt=document.createElement('button'); bt.type='button'; bt.id='ct-chips';
  bt.innerHTML='<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><g class="rl"><path d="M6 6l12 12M18 6 6 18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></g></svg>';   /* an x; spun shut it rests as a + */
  var reel=bt.querySelector('.rl');
  function label(){ bt.setAttribute('aria-pressed', off ? 'true' : 'false'); bt.title=off ? 'Show the chips' : 'Hide the chips'; bt.setAttribute('aria-label', bt.title); }
  function place(){ var f=nav.querySelector('button.nav-btn') || items()[0], g=items()[0]; if(!f) return; var gl=g ? g.getBoundingClientRect().left : 0; var r=f.getBoundingClientRect();     /* in line with the chips: just before the first (hidden ones keep their place) */
    if(!r.width) return; var cw=parseFloat(getComputedStyle(bt).width) || bt.offsetWidth, z=cw ? (bt.getBoundingClientRect().width/cw || 1) : 1;      /* (the page's own zoom, .8: screen px -> css px; the css width, not offsetWidth, which WebKit rounds up) */
    bt.style.top=Math.round((r.top+r.height/2)/z)+'px'; bt.style.left=Math.max(6, Math.round(Math.min(r.left, gl || r.left)/z-22-8/z))+'px'; }   /* (centred on a chip, 8 screen px before the row's first item) */
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
  if(typeof ResizeObserver==='function') new ResizeObserver(function(){ requestAnimationFrame(place); }).observe(nav);
  var pt=0; if(typeof MutationObserver==='function') new MutationObserver(function(){ requestAnimationFrame(place); clearTimeout(pt); pt=setTimeout(place, 400); }).observe(de, {attributes:true, attributeFilter:['class']});   /* (a style switch — Retro's wider labels — moves the row without resizing the bar: the x follows it, so it never sits on the first label) */   /* (a frame later: never a change inside the observer's own pass) */
})();"""


# the first unit's colour, for the sheet's reach above the window (SHEET_CSS); kept as the layout redraws it
SHEET_JS = r"""function c0(){ var t=window._headerTint, c=t && t.stops && t.stops[0] && t.stops[0].c;
    if(c && /^#[0-9a-f]{6}$/i.test(c)) de.style.setProperty('--ct-c0', c+'b3'); }
  var uh=window.updateHeaderTint; if(typeof uh==='function') window.updateHeaderTint=function(){ c0(); return uh.apply(this, arguments); };
  c0(); window.addEventListener('load', c0);"""


def block(sheet: bool = True) -> str:
    """The page copy: comments and indentation left out (the source keeps them; every byte counts on a palace page).
    `sheet`: the page has the timeline's unit-colour sheet (not a palace or a Star chart)."""
    import re
    from .backgrounds import _lean
    return ('<style id="alto-clear-top-css">' + _lean(CSS + (SHEET_CSS if sheet else ""), css=True)
            + '</style><script id="alto-clear-top-js">'
            + _lean(re.sub(r"/\*.*?\*/", "", JS.replace("__SHEET__", SHEET_JS if sheet else ""), flags=re.S)) + "</script>")
