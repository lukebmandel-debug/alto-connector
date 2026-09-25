"""Edge-to-edge wallpaper for the sign-in shells on a phone.

Safari (iOS 26 on) paints the strips behind the clock and the toolbar flat,
from a pinned element on the edge or the body, unless the top-level document
holds real pixels there AND is scrolled a little from its top. The timeline
sits in a frame, which Safari cannot see into, so the shell gives itself what
a plain page would have:

  * a wallpaper stage in the document itself, taller than the screen, whose ends
    are the page wallpaper's uniform top and bottom colours (the mobile
    wallpaper settles into one colour at each edge, see engine_patches.py) with
    the header's frosted tint continued upward over the top end;
  * a scroll "runway": the document is taller than the screen and rests in the
    middle of it, and is pinned there so the bars never show again.

No pinned element with a background sits on the top or bottom edge: Safari
would sample it and go back to a flat strip.
"""

BLEED_HTML = '<div id="app"><div id="rw-stage"><div id="navext"></div></div></div>\n'
BARS_HTML = ""

_OFF = 62   # runway: px the document rests below its top (also the bleed above the screen)

BLEED_CSS = (
    "\n#app,#rw-stage,#navext{display:none}"
    "\nhtml.rw{height:auto;overflow-y:scroll;overscroll-behavior:none}"
    f"\nhtml.rw body{{height:auto;min-height:calc(100dvh + {2 * _OFF}px)}}"
    f"\nhtml.rw #app{{display:block;position:relative;height:100dvh;margin-top:{_OFF}px}}"
    f"\nhtml.rw #rw-stage{{display:block;position:absolute;left:0;right:0;top:-{_OFF}px;"
    "height:calc(100dvh + 198px);pointer-events:none}"
    f"\nhtml.rw #navext{{display:block;position:absolute;left:0;right:0;top:0;height:{_OFF}px}}"
)

BLEED_JS = """
(function(){
  var OFF = __OFF__;
  var stage = document.getElementById('stage'), rw = document.getElementById('rw-stage');
  var navext = document.getElementById('navext'), mo = null, key = '', on = false;
  if(!stage || !rw) return;
  var root = document.documentElement, body = document.body;
  function rgba(s){
    s = (s || '').trim();
    var h = /^#([0-9a-f]{6})$/i.exec(s);
    if(h) return [parseInt(h[1].slice(0, 2), 16), parseInt(h[1].slice(2, 4), 16), parseInt(h[1].slice(4), 16), 1];
    var m = /rgba?\\(([^)]+)\\)/.exec(s);
    if(!m) return null;
    var p = m[1].split(/[ ,\\/]+/).filter(Boolean).map(parseFloat);
    return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
  }
  function over(t, b){
    var a = t[3];
    return [t[0] * a + b[0] * (1 - a), t[1] * a + b[1] * (1 - a), t[2] * a + b[2] * (1 - a), 1];
  }
  function css(c){ return 'rgb(' + Math.round(c[0]) + ',' + Math.round(c[1]) + ',' + Math.round(c[2]) + ')'; }
  // keep the document resting on its runway so the bars never get uncovered
  function pin(){ if(on && Math.abs((window.pageYOffset || 0) - OFF) > 0.5) window.scrollTo(0, OFF); }
  function settle(){ pin(); setTimeout(pin, 120); setTimeout(pin, 450); setTimeout(pin, 1000); }
  function off(){
    if(!on && !key) return;
    on = false; key = '';
    root.classList.remove('rw');
    root.style.background = ''; body.style.background = '';
    rw.style.background = ''; navext.style.background = '';
    navext.style.webkitBackdropFilter = navext.style.backdropFilter = '';
    window.scrollTo(0, 0);
  }
  function sync(){
    var d = null;
    try{ d = stage.contentDocument; }catch(e){}
    var r = d && d.documentElement;
    if(!r || !stage.classList.contains('on') || !r.classList.contains('mobile')){ off(); return; }
    var win = stage.contentWindow, cs = win.getComputedStyle(r);
    var v = cs.getPropertyValue('--m-page-veil').trim();
    var eTop = rgba(cs.getPropertyValue('--m-edge-top')), eBot = rgba(cs.getPropertyValue('--m-edge-bot'));
    if(!eTop || !eBot){ off(); return; }
    var nav = d.getElementById('nav'), ncs = nav ? win.getComputedStyle(nav) : null;
    var navBg = ncs ? ncs.backgroundColor : '';
    var bf = ncs ? (ncs.backdropFilter || ncs.webkitBackdropFilter || '') : '';
    var k = [v, eTop.join(), eBot.join(), navBg, bf].join('|');
    if(k === key && on) return;
    key = k;
    var vv = rgba(v), top = eTop, bot = eBot;
    if(vv){ top = over(vv, top); bot = over(vv, bot); }
    rw.style.background = 'linear-gradient(' + css(top) + ' 0 50%, ' + css(bot) + ' 50% 100%)';
    // the header, continued upward under the clock: same frost, same tint
    navext.style.background = navBg;
    navext.style.webkitBackdropFilter = navext.style.backdropFilter = bf;
    root.style.background = css(bot);
    body.style.background = css(bot);
    if(!on){ on = true; root.classList.add('rw'); settle(); }
  }
  function watch(){
    if(mo){ mo.disconnect(); mo = null; }
    key = '';
    sync();
    var d = null;
    try{ d = stage.contentDocument; }catch(e){}
    if(d && d.documentElement){
      // a scroll gesture that ends inside the frame must not chain out to this page
      if(!d.getElementById('shell-overscroll')){
        var st = d.createElement('style'); st.id = 'shell-overscroll';
        st.textContent = 'html,body{overscroll-behavior:none}';
        (d.head || d.documentElement).appendChild(st);
      }
      mo = new MutationObserver(sync);
      mo.observe(d.documentElement, {attributes: true, attributeFilter: ['class', 'style']});
    }
  }
  stage.addEventListener('load', watch);
  new MutationObserver(sync).observe(stage, {attributes: true, attributeFilter: ['class']});
  window.addEventListener('scroll', pin, {passive: true});
  window.addEventListener('resize', function(){ sync(); settle(); });
  window.addEventListener('pageshow', settle);
  window.addEventListener('orientationchange', settle);
  setInterval(sync, 600);
})();
""".replace("__OFF__", str(_OFF))
