"""The arrow keys move around the city map when no building is enlarged — in any direction.

Nothing used to answer them there (the canvas is not focused, so the browser scrolls nothing). Held arrows now glide the map: two
together (Up with Right) glide on the diagonal at the same speed as one — the direction is the sum of the held keys, normalised —
and Shift is faster. The speed eases in and out so a tap nudges and a hold travels. Spliced inside the palace's closure
(palace.py): it uses palaceOn / focused / PV / pvSet / Z from there.
"""

PAN_JS = r"""
/* ── arrow keys pan the map (any of the 8 ways: two held arrows are the diagonal) ── */
(function(){
  var KEYS={ArrowLeft:[-1,0], ArrowRight:[1,0], ArrowUp:[0,-1], ArrowDown:[0,1]};
  var SPEED=900, FAST=2.4, EASE=75;                 /* screen px per second; Shift; ms of easing */
  var dn={}, vel=[0,0], raf=0, t0=0, fast=1, fl=null, last=null;
  function typing(t){ var n=t&&t.tagName; return n==='INPUT'||n==='TEXTAREA'||n==='SELECT'||(t&&t.isContentEditable); }
  function by(dx, dy){
    if(PV){ pvSet(Z, PV.tx+dx, PV.ty+dy); fl=null; return; }
    var cv=document.getElementById('canvas'); if(!cv) return;
    /* carry the fractions: a slow glide would otherwise stall where the browser rounds the scroll */
    var x=(fl&&last&&Math.abs(cv.scrollLeft-last[0])<1.5)?fl[0]:cv.scrollLeft, y=(fl&&last&&Math.abs(cv.scrollTop-last[1])<1.5)?fl[1]:cv.scrollTop;
    x+=dx; y+=dy; cv.scrollLeft=x; cv.scrollTop=y;
    last=[cv.scrollLeft, cv.scrollTop]; fl=[Math.abs(last[0]-x)>1.5?last[0]:x, Math.abs(last[1]-y)>1.5?last[1]:y]; }
  function tick(t){
    var dt=Math.max(1, Math.min(50, t-t0)); t0=t;
    if(!palaceOn() || focused()){ dn={}; }
    var tx=0, ty=0; for(var k in dn){ tx+=KEYS[k][0]; ty+=KEYS[k][1]; }
    var m=Math.hypot(tx, ty); if(m){ tx/=m; ty/=m; }
    var a=1-Math.exp(-dt/EASE), sp=SPEED*fast;
    vel[0]+=(tx*sp-vel[0])*a; vel[1]+=(ty*sp-vel[1])*a;
    if(!m && Math.hypot(vel[0], vel[1])<6){ vel=[0,0]; raf=0; fl=null; return; }
    by(vel[0]*dt/1000, vel[1]*dt/1000);
    raf=requestAnimationFrame(tick); }
  window.addEventListener('keydown', function(e){
    if(!KEYS[e.key] || e.metaKey || e.ctrlKey || e.altKey || !palaceOn() || focused() || typing(e.target)) return;
    e.preventDefault(); dn[e.key]=1; fast=e.shiftKey?FAST:1;
    if(!raf){ t0=performance.now(); raf=requestAnimationFrame(tick); } }, true);
  window.addEventListener('keyup', function(e){ if(KEYS[e.key]) delete dn[e.key]; }, true);
  window.addEventListener('blur', function(){ dn={}; });
  window._altoPalacePanKeys=dn;                      /* read by the tests */
})();
"""
