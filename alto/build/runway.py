"""The mobile scroll runway shared by timeline pages and the homepage.

Safari (iOS 26 on) paints the strips behind the clock and the toolbar flat when
a position:fixed or sticky element sits on that edge, and it keeps that colour
from the page's first layout. It shows the page's real pixels there only if
they are part of the document above and below the visible area. So a mobile
page opened directly (html.rw, set in <head>):

  * rests 80px down a short scroll runway (body = the screen box, 80px above
    it, 140px below), pinned there;
  * has no fixed chrome: every fixed piece is position:absolute in the body;
  * never lets anything else move the page: a finger drag reaches only a panel
    that can still scroll that way, scrollIntoView scrolls only the panel the
    element is in, and the pin restores both axes.

What each page does with its own chrome is in engine_patches.py (timeline)
and pages.py (homepage). See the Alto deploy-map notes for how each rule was
measured in the iOS 27 simulator.
"""

RUNWAY_JS = r"""(function(){
  var r = document.documentElement, OFF = 80;
  // (the homepage's html.rw follows its phone layout, pages.py: there the class comes and goes with a turn, and everything below asks on())
  if(!r.classList.contains('rw') && !window._altoRwLive) return;
  function on(){ return r.classList.contains('rw'); }
  var nat = Element.prototype.scrollIntoView;
  // The page itself now scrolls (it rests on the runway), so the engine's
  // scrollIntoView calls — the Map centring the current node, search jumping
  // to a hit — scrolled the page too, dragging every tile with it until the
  // pin below snapped it back. Scroll only the panel the element is in.
  function scroller(e){
    for(var p = e.parentElement; p && p !== document.body && p !== r; p = p.parentElement){
      var c = getComputedStyle(p);
      if(/(auto|scroll)/.test(c.overflowY) && p.scrollHeight > p.clientHeight + 1) return p;
    }
    return null;
  }
  Element.prototype.scrollIntoView = function(o){
    if(!on()) return nat.apply(this, arguments);
    var p = scroller(this);
    if(!p) return;
    var block = (o && typeof o === 'object' && o.block) || (o === false ? 'end' : 'start');
    var a = this.getBoundingClientRect(), b = p.getBoundingClientRect();
    var top = p.scrollTop + (a.top - b.top);
    if(block === 'center') top -= (p.clientHeight - a.height) / 2;
    else if(block === 'end') top -= p.clientHeight - a.height;
    else if(block === 'nearest'){
      if(a.top >= b.top && a.bottom <= b.bottom) return;
      if(a.bottom > b.bottom) top -= p.clientHeight - a.height;
    }
    p.scrollTo({top: Math.max(0, top), behavior: (o && o.behavior === 'smooth') ? 'smooth' : 'auto'});
  };
  // Any other fixed piece at the level of <body> / #app (one added by a later
  // script, say) goes absolute too. Fixed pieces inside a positioned parent
  // are left alone: absolute would move them.
  function loose(e){
    for(var p = e.parentElement; p && p !== document.body; p = p.parentElement){
      if(p.id === 'app') continue;
      var c = getComputedStyle(p);
      if(c.position !== 'static' || c.transform !== 'none' || c.filter !== 'none') return false;
    }
    return true;
  }
  function sweep(root){
    var all = [root].concat([].slice.call(root.querySelectorAll('*')));
    for(var i = 0; i < all.length; i++){
      var e = all[i];
      if(e.nodeType !== 1 || e.classList.contains('rw-abs')) continue;
      var pos = getComputedStyle(e).position;
      if((pos === 'fixed' || pos === 'sticky') && e.parentElement && loose(e)) e.classList.add('rw-abs');
    }
  }
  if(on()) sweep(document.body);
  new MutationObserver(function(ms){
    if(on()) ms.forEach(function(m){ [].forEach.call(m.addedNodes, function(n){ if(n.nodeType === 1) sweep(n); }); });
  }).observe(document.body, {childList: true, subtree: true});
  // A finger never moves the page itself. On an iPhone touch-action:none on
  // the root does not hold, and a drag that reached the page made every tile
  // move and snap back ("seizure"). One-finger drags go only to a panel that
  // can still scroll that way; anything else is refused. Two fingers (the
  // engine's own panel zoom), text selection and form fields are left alone.
  var tx = 0, ty = 0, tt = 0;
  document.addEventListener('touchstart', function(e){
    tt = Date.now();
    if(e.touches.length === 1){ tx = e.touches[0].clientX; ty = e.touches[0].clientY; }
  }, {passive: true, capture: true});
  document.addEventListener('touchmove', function(e){
    if(!on() || e.touches.length !== 1 || !e.cancelable) return;
    var t = e.target;
    if(t && t.closest && t.closest('input, textarea, select, [contenteditable="true"]')) return;
    var sel = window.getSelection && window.getSelection();
    if(sel && !sel.isCollapsed) return;
    var dx = e.touches[0].clientX - tx, dy = e.touches[0].clientY - ty;
    var vert = Math.abs(dy) >= Math.abs(dx);
    for(var p = t && t.nodeType === 1 ? t : t && t.parentElement; p && p !== document.body && p !== r; p = p.parentElement){
      var c = getComputedStyle(p);
      if(vert){
        if(/(auto|scroll)/.test(c.overflowY) && p.scrollHeight > p.clientHeight + 1 &&
           ((dy > 0 && p.scrollTop > 0) || (dy < 0 && p.scrollTop + p.clientHeight < p.scrollHeight - 1))) return;
      } else {
        if(/(auto|scroll)/.test(c.overflowX) && p.scrollWidth > p.clientWidth + 1 &&
           ((dx > 0 && p.scrollLeft > 0) || (dx < 0 && p.scrollLeft + p.clientWidth < p.scrollWidth - 1))) return;
      }
    }
    e.preventDefault();
  }, {passive: false});
  // Rest 80px down the runway, and stay there: no touch scrolling, and a
  // snap-back if anything (a focused field, a hash jump) moves the page.
  var busy = false;
  // While a field has focus, let Safari keep the page where it put it only if
  // pinning would hide the field (a notes box low on the screen, under the
  // keyboard). A field that stays in view once pinned (a search box at the top)
  // does not need the page moved, and a moved page is a flat strip at the top.
  function typing(){
    var a = document.activeElement;
    if(!a || !/^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) return false;
    var b = a.getBoundingClientRect(), vv = window.visualViewport;
    var h = vv ? vv.height : window.innerHeight, shift = (window.pageYOffset || 0) - OFF;
    return b.top + shift < 0 || b.bottom + shift > h - 8;
  }
  function pin(){
    if(!on() || busy || typing() || (Math.abs((window.pageYOffset || 0) - OFF) <= 1 && !(window.pageXOffset || 0))) return;
    busy = true;
    requestAnimationFrame(function(){ busy = false; if(on()) window.scrollTo(0, OFF); });
  }
  function settle(){ if(!on()) return; window.scrollTo(0, OFF); setTimeout(pin, 100); setTimeout(pin, 400); setTimeout(pin, 1000); }
  window.addEventListener('scroll', pin, {passive: true});
  window.addEventListener('load', settle);
  window.addEventListener('pageshow', settle);
  window.addEventListener('orientationchange', settle);
  window.addEventListener('resize', pin);
  document.addEventListener('focusout', function(){ setTimeout(pin, 50); });
  settle();
  // (sim1112c T1) The runway taken away by a turn (the homepage on its side has none): the page goes back to its top, and is held there while the turn
  // lasts. Safari puts the page back where it was as its turn ends (80px down the runway: the list stood 78pt higher than on a page opened on its side,
  // until the reader scrolled). A finger on the screen ends the hold.
  function top0(){
    var t0 = Date.now();
    function z(){
      if(on() || tt >= t0 || Date.now() - t0 > 1600){ window.removeEventListener('scroll', z); return; }
      if(window.pageYOffset || window.pageXOffset) window.scrollTo(0, 0);
    }
    window.addEventListener('scroll', z, {passive: true});
    z(); [80, 350, 450, 600, 800, 1100, 1500, 1700].forEach(function(t){ setTimeout(z, t); });
  }
  var was = on();
  // (early: the class set on orientationchange, the layout still the last way up's. What is fixed there is not what is fixed upright: the sweep waits for the layout)
  window._altoRw = function(v, early){ if(v){ was = true; if(!early) sweep(document.body); settle(); } else if(was){ was = false; top0(); } };
})();
"""


def _strip_comments(js: str) -> str:
    """Whole-line // comments only: they explain the code here, in the source,
    and cost bytes in every page (a private page is capped at 1,000,000)."""
    return "\n".join(l for l in js.split("\n") if not l.lstrip().startswith("//"))


def runway_script() -> str:
    return '<script id="alto-runway-js">\n' + _strip_comments(RUNWAY_JS) + '</script>\n'
