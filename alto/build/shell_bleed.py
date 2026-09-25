"""Wallpaper bleed for the sign-in shells.

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
  function sync(){
    var d = null;
    try{ d = stage.contentDocument; }catch(e){}
    var root = d && d.documentElement;
    if(!root || !stage.classList.contains('on') || !root.classList.contains('mobile')){
      bleed.style.display = 'none'; return;
    }
    var cs = stage.contentWindow.getComputedStyle(root);
    var g = cs.getPropertyValue('--page-grad').trim(), v = cs.getPropertyValue('--m-page-veil').trim();
    if(!g){ bleed.style.display = 'none'; return; }
    bleed.style.background = (v ? 'linear-gradient(' + v + ',' + v + '),' : '') + g;
    bleed.style.display = 'block';
  }
  function watch(){
    if(mo){ mo.disconnect(); mo = null; }
    sync();
    var d = null;
    try{ d = stage.contentDocument; }catch(e){}
    if(d && d.documentElement){
      mo = new MutationObserver(sync);
      mo.observe(d.documentElement, {attributes: true, attributeFilter: ['class']});
    }
  }
  stage.addEventListener('load', watch);
  new MutationObserver(sync).observe(stage, {attributes: true, attributeFilter: ['class']});
})();
"""
