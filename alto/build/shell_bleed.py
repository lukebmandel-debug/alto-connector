"""Wallpaper and bar tint for the sign-in shells.

Safari (iOS 26 on) tints the status-bar and toolbar strips from the background
colour of a fixed element on the top / bottom edge, else the body — it ignores
theme-color. The page's own fixed header does that job when it is opened
directly, but Safari cannot see inside a frame, so the shell keeps two thin
fixed strips whose colour is the page wallpaper's top / bottom edge colour (the
mobile wallpaper settles into one uniform colour at each edge, see
engine_patches.py), so they read as the wallpaper carrying on.

On an iPhone a fixed full-screen layer under-covers the real screen: the strips
behind the status bar and the bottom toolbar show whatever is behind it. A
timeline page fixes that itself with an oversized wallpaper, but inside the
shell's frame that wallpaper is clipped to the frame, so the strips showed the
shell's plain grey. The shell paints the same wallpaper, with the same
oversize, behind the frame — read from the page itself so it follows light and
dark mode — and nothing inside the frame moves.
"""

BLEED_HTML = '<div id="bleed"></div>\n'
BARS_HTML = '<div id="bar-top"></div><div id="bar-bot"></div>\n'

BLEED_CSS = (
    "\n#bleed{position:fixed;top:-12%;right:-6%;bottom:-12%;left:-6%;"
    "pointer-events:none;display:none;background-repeat:no-repeat}"
    "\n#bar-top,#bar-bot{position:fixed;left:0;width:100%;height:12px;"
    "pointer-events:none;display:none}"
    "\n#bar-top{top:-8px}\n#bar-bot{bottom:-8px}"
)

BLEED_JS = """
(function(){
  var stage = document.getElementById('stage'), bleed = document.getElementById('bleed'), mo = null;
  var barTop = document.getElementById('bar-top'), barBot = document.getElementById('bar-bot');
  if(!stage || !bleed) return;
  var root = document.documentElement, body = document.body, meta = null, key = '';
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
  // CSS filter: saturate(s) — the header saturates whatever sits behind it
  function saturate(c, s){
    var r = c[0], g = c[1], b = c[2];
    function cl(x){ return Math.max(0, Math.min(255, x)); }
    return [
      cl((0.213 + 0.787 * s) * r + (0.715 - 0.715 * s) * g + (0.072 - 0.072 * s) * b),
      cl((0.213 - 0.213 * s) * r + (0.715 + 0.285 * s) * g + (0.072 - 0.072 * s) * b),
      cl((0.213 - 0.213 * s) * r + (0.715 - 0.715 * s) * g + (0.072 + 0.928 * s) * b), 1];
  }
  function css(c){ return 'rgb(' + Math.round(c[0]) + ',' + Math.round(c[1]) + ',' + Math.round(c[2]) + ')'; }
  function clear(){
    key = '';
    bleed.style.display = 'none';
    if(barTop) barTop.style.display = 'none';
    if(barBot) barBot.style.display = 'none';
    root.style.background = ''; body.style.background = '';
    if(meta){ meta.parentNode.removeChild(meta); meta = null; }
  }
  function sync(){
    var d = null;
    try{ d = stage.contentDocument; }catch(e){}
    var r = d && d.documentElement;
    if(!r || !stage.classList.contains('on') || !r.classList.contains('mobile')){ if(key) clear(); return; }
    var win = stage.contentWindow, cs = win.getComputedStyle(r);
    var pb = d.getElementById('page-bg');
    var wall = pb ? win.getComputedStyle(pb).backgroundImage : '';
    var v = cs.getPropertyValue('--m-page-veil').trim();
    var eTop = rgba(cs.getPropertyValue('--m-edge-top')), eBot = rgba(cs.getPropertyValue('--m-edge-bot'));
    if(!wall || wall === 'none' || !eTop || !eBot){ if(key) clear(); return; }
    var nav = d.getElementById('nav'), navBg = nav ? rgba(win.getComputedStyle(nav).backgroundColor) : null;
    var t = d.getElementById('meta-theme');
    var k = [wall, v, eTop.join(), eBot.join(), navBg && navBg.join(), nav && (win.getComputedStyle(nav).backdropFilter || ''), t && t.content].join('|');
    if(k === key) return;
    key = k;
    // What is drawn behind the frame: the page's own wallpaper, same size, same veil.
    bleed.style.background = (v ? 'linear-gradient(' + v + ',' + v + '),' : '') + wall;
    bleed.style.display = 'block';
    // The colours Safari should carry into its top and bottom strips: the wallpaper's
    // uniform edge colour under the frosted veil, plus the era-tinted header on top.
    var vv = rgba(v), top = eTop, bot = eBot;
    if(vv){ top = over(vv, top); bot = over(vv, bot); }
    // the header frosts what is behind it (saturating it), then lays its era tint on top
    var bf = nav ? (win.getComputedStyle(nav).backdropFilter || win.getComputedStyle(nav).webkitBackdropFilter || '') : '';
    var sm = /saturate\\(([\\d.]+)(%?)\\)/.exec(bf);
    if(sm) top = saturate(top, parseFloat(sm[1]) / (sm[2] ? 100 : 1));
    if(navBg) top = over(navBg, top);
    root.style.background = css(bot);
    body.style.background = css(bot);
    if(barTop){ barTop.style.background = css(top); barTop.style.display = 'block'; }
    if(barBot){ barBot.style.background = css(bot); barBot.style.display = 'block'; }
    if(t && t.content){
      if(!meta){ meta = document.createElement('meta'); meta.name = 'theme-color'; document.head.appendChild(meta); }
      meta.content = t.content;
    }
  }
  function watch(){
    if(mo){ mo.disconnect(); mo = null; }
    key = '';
    sync();
    var d = null;
    try{ d = stage.contentDocument; }catch(e){}
    if(d && d.documentElement){
      mo = new MutationObserver(sync);
      mo.observe(d.documentElement, {attributes: true, attributeFilter: ['class', 'style']});
      var t = d.getElementById('meta-theme');
      if(t) mo.observe(t, {attributes: true, attributeFilter: ['content']});
    }
  }
  stage.addEventListener('load', watch);
  new MutationObserver(sync).observe(stage, {attributes: true, attributeFilter: ['class']});
  window.addEventListener('resize', sync);
  setInterval(sync, 600);
})();
"""
