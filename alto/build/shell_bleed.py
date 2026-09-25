"""Wallpaper and bar tint for the sign-in shells.

Safari (iOS 26 on) tints the status-bar and toolbar strips from the background
colour of a fixed element on the top / bottom edge, else the body — it ignores
theme-color. The page's own fixed header does that job when it is opened
directly, but Safari cannot see inside a frame, so the shell keeps two thin
fixed strips, transparent to the eye but not to Safari, whose colour is worked
out from what the page shows at each edge.

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
    "pointer-events:none;display:none;opacity:0}"
    "\n#bar-top{top:-8px}\n#bar-bot{bottom:-8px}"
)

BLEED_JS = """
(function(){
  var stage = document.getElementById('stage'), bleed = document.getElementById('bleed'), mo = null;
  var barTop = document.getElementById('bar-top'), barBot = document.getElementById('bar-bot');
  if(!stage || !bleed) return;
  var root = document.documentElement, body = document.body, meta = null, key = '';
  var probe = document.createElement('div');
  function rgba(s){
    var m = /rgba?\\(([^)]+)\\)/.exec(s || '');
    if(!m) return null;
    var p = m[1].split(/[ ,\\/]+/).filter(Boolean).map(parseFloat);
    return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
  }
  function over(t, b){
    var a = t[3];
    return [t[0] * a + b[0] * (1 - a), t[1] * a + b[1] * (1 - a), t[2] * a + b[2] * (1 - a), 1];
  }
  function css(c){ return 'rgb(' + Math.round(c[0]) + ',' + Math.round(c[1]) + ',' + Math.round(c[2]) + ')'; }
  // the colour of a linear-gradient at a point of a w x h box (CSS gradient-line maths)
  function gradAt(g, w, h, x, y){
    probe.style.backgroundImage = g;
    var n = probe.style.backgroundImage, deg = /(-?[\\d.]+)deg/.exec(n);
    var re = /(rgba?\\([^)]*\\))\\s*([\\d.]+)%/g, st = [], m;
    while((m = re.exec(n))) st.push([parseFloat(m[2]) / 100, rgba(m[1])]);
    if(!deg || st.length < 2) return null;
    var a = parseFloat(deg[1]) * Math.PI / 180, dx = Math.sin(a), dy = -Math.cos(a);
    var L = Math.abs(w * dx) + Math.abs(h * dy);
    var t = Math.max(0, Math.min(1, ((x - w / 2) * dx + (y - h / 2) * dy) / L + 0.5));
    for(var i = 1; i < st.length; i++){
      if(t <= st[i][0] || i === st.length - 1){
        var s0 = st[i - 1], s1 = st[i], k = s1[0] === s0[0] ? 1 : Math.max(0, Math.min(1, (t - s0[0]) / (s1[0] - s0[0])));
        return [0, 1, 2, 3].map(function(j){ return s0[1][j] + (s1[1][j] - s0[1][j]) * k; });
      }
    }
    return null;
  }
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
    var g = cs.getPropertyValue('--page-grad').trim(), v = cs.getPropertyValue('--m-page-veil').trim();
    if(!g){ if(key) clear(); return; }
    var nav = d.getElementById('nav'), navBg = nav ? rgba(win.getComputedStyle(nav).backgroundColor) : null;
    var t = d.getElementById('meta-theme');
    var k = [g, v, cs.backgroundColor, navBg && navBg.join(), t && t.content, innerWidth, innerHeight].join('|');
    if(k === key) return;
    key = k;
    bleed.style.background = (v ? 'linear-gradient(' + v + ',' + v + '),' : '') + g;
    bleed.style.display = 'block';
    root.style.background = g + ' 0 0 / 100% 100% no-repeat ' + cs.backgroundColor;
    body.style.background = 'transparent';
    if(t && t.content){
      if(!meta){ meta = document.createElement('meta'); meta.name = 'theme-color'; document.head.appendChild(meta); }
      meta.content = t.content;
    }
    // What the page shows at the top and bottom edge: wallpaper, the frosted veil,
    // and (top only) the era-tinted header.
    var vv = rgba(v), w = innerWidth, h = innerHeight;
    function edge(y, tint){
      var c = gradAt(g, w, h, w / 2, y);
      if(!c) return null;
      c[3] = 1;
      if(vv) c = over(vv, c);
      if(tint) c = over(tint, c);
      return css(c);
    }
    var top = edge(0, navBg), bot = edge(h, null);
    if(barTop && top){ barTop.style.background = top; barTop.style.display = 'block'; }
    if(barBot && bot){ barBot.style.background = bot; barBot.style.display = 'block'; }
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
