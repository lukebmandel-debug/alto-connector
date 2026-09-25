"""Wallpaper and bar tint for the sign-in shells.

On an iPhone a fixed full-screen layer under-covers the real screen: the strips
behind the status bar and the bottom toolbar show whatever is behind it. A
timeline page fixes that itself with an oversized wallpaper, but inside the
shell's frame that wallpaper is clipped to the frame, so the strips showed the
shell's plain grey. The shell paints the same wallpaper, with the same
oversize, behind the frame — read from the page itself so it follows light and
dark mode — and nothing inside the frame moves.
"""

BLEED_HTML = '<div id="bleed"></div>\n'

BLEED_CSS = (
    "\n#bleed{position:fixed;top:-12%;right:-6%;bottom:-12%;left:-6%;"
    "pointer-events:none;display:none;background-repeat:no-repeat}"
)

BLEED_JS = """
(function(){
  var stage = document.getElementById('stage'), bleed = document.getElementById('bleed'), mo = null;
  if(!stage || !bleed) return;
  var root = document.documentElement, body = document.body;
  var meta = document.querySelector('meta[name="theme-color"]');
  function clear(){
    bleed.style.display = 'none';
    root.style.background = ''; body.style.background = '';
    if(meta){ meta.parentNode.removeChild(meta); meta = null; }
  }
  function sync(){
    var d = null;
    try{ d = stage.contentDocument; }catch(e){}
    var r = d && d.documentElement;
    if(!r || !stage.classList.contains('on') || !r.classList.contains('mobile')){ clear(); return; }
    var cs = stage.contentWindow.getComputedStyle(r);
    var g = cs.getPropertyValue('--page-grad').trim(), v = cs.getPropertyValue('--m-page-veil').trim();
    if(!g){ clear(); return; }
    bleed.style.background = (v ? 'linear-gradient(' + v + ',' + v + '),' : '') + g;
    bleed.style.display = 'block';
    // The page tints the browser's own top and bottom strips from its root
    // background and its theme-color; a frame's do not count, so repeat both here.
    root.style.background = g + ' 0 0 / 100% 100% no-repeat ' + cs.backgroundColor;
    body.style.background = 'transparent';
    var t = d.getElementById('meta-theme');
    if(t && t.content){
      if(!meta){ meta = document.createElement('meta'); meta.name = 'theme-color'; document.head.appendChild(meta); }
      meta.content = t.content;
    }
  }
  function watch(){
    if(mo){ mo.disconnect(); mo = null; }
    sync();
    var d = null;
    try{ d = stage.contentDocument; }catch(e){}
    if(d && d.documentElement){
      mo = new MutationObserver(sync);
      mo.observe(d.documentElement, {attributes: true, attributeFilter: ['class']});
      var t = d.getElementById('meta-theme');
      if(t) mo.observe(t, {attributes: true, attributeFilter: ['content']});
    }
  }
  stage.addEventListener('load', watch);
  new MutationObserver(sync).observe(stage, {attributes: true, attributeFilter: ['class']});
})();
"""
