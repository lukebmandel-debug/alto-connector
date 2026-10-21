"""The top bars without their glass (Luke, 2026-10-21, after the sample on his Torts System).

On a desktop timeline of any format the title bar and the unit / chip bar keep everything on them
(the clef, the name, the wordmark, the chips) but lose their tinted glass: the wallpaper (or picture)
runs up to the top of the window, and so does the board, with nothing ending where the bars were.

The engine pins #canvas under the nav (alignInfo: an inline !important top). Here #canvas starts at
the top instead, padded down by the bars' height so it still opens below them, with a detail page open the engine's own place stands, and phones keep their own layout.
"""

CSS = r"""
html.alto-clear-top:not(.mobile) :is(#title-bar,#nav,#node-nav-bar):not(#_){background:transparent !important;-webkit-backdrop-filter:none !important;
  backdrop-filter:none !important;box-shadow:none !important;border-color:transparent !important;}
html.alto-clear-top:not(.mobile) :is(#title-bar,#nav,#node-nav-bar):not(#_)::before,html.alto-clear-top:not(.mobile) :is(#title-bar,#nav,#node-nav-bar):not(#_)::after{
  background:transparent !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;box-shadow:none !important;}
html.alto-clear-top.alto-bg:not(.mobile) #page-bg::before{top:-40px !important;}
/* the bars are see-through now, the board under them: a click there reaches the board unless it is on a control */
html.alto-clear-top:not(.mobile) :is(#title-bar,#nav,#node-nav-bar),html.alto-clear-top:not(.mobile) :is(#title-bar,#nav,#node-nav-bar) *{pointer-events:none;}
html.alto-clear-top:not(.mobile) :is(#title-bar,#nav,#node-nav-bar) :is(button,a,input,select,textarea,label,svg,[role=button],[onclick],[tabindex],#title-text),
html.alto-clear-top:not(.mobile) :is(#title-bar,#nav,#node-nav-bar) :is(button,a,svg,[role=button],[onclick]) *{pointer-events:auto;}
"""

JS = r"""(function(){
  var de=document.documentElement; if(de.classList.contains('mobile')) return;
  de.classList.add('alto-clear-top');
  function sync(){ var c=document.getElementById('canvas'); if(!c) return;
    var on=!de.classList.contains('mobile') && !de.classList.contains('detail-open'), t=c.style.getPropertyValue('top');
    if(on){ if(t!=='0px'){ c._ctT=t; c.style.setProperty('top', '0px', 'important'); c.style.setProperty('padding-top', t, 'important'); c.style.setProperty('scroll-padding-top', t, 'important'); } }   /* (the board still opens under the bars: it slides beneath them only as it scrolls) */
    else if(t==='0px' && c._ctT){ c.style.setProperty('top', c._ctT, 'important'); c.style.removeProperty('padding-top'); c.style.removeProperty('scroll-padding-top'); } }
  if(typeof MutationObserver==='function'){ var c=document.getElementById('canvas');
    if(c) new MutationObserver(sync).observe(c, {attributes:true, attributeFilter:['style']});
    new MutationObserver(sync).observe(de, {attributes:true, attributeFilter:['class']}); }
  sync();
})();"""


def block() -> str:
    return '<style id="alto-clear-top-css">' + CSS + '</style><script id="alto-clear-top-js">' + JS + "</script>"
