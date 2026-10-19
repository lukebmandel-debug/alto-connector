"""The Star chart look's skin: what makes a Hub & spoke page (outline, layout
"solar") in its Star chart look (the default; solar_draw's in-page toggle
flips it to Plain) look like a real solar system.

solar_draw.py draws the circles, rings and spokes and moves the bodies; this
module only dresses them. blocks.py emits it on every Hub & spoke page; it is
on only in the Star chart look on desktop (window._altoSolarLook, or the
html.alto-solar-stars / -plain classes, or else the plan's style "orbit") and
comes off whole in the Plain look (its canvases kept for the way back). With
motion switched off (window._altoSolarMotion) its animations pause too.

* THE STAR. Each sun is a glowing star: a white-hot core darkening to an
  orange limb (CSS gradients, the colours seeded from the sun's id: the first
  system's is always a yellow G star), two granulation layers turning slowly
  against each other, a corona with streamers and a few prominences (canvases
  drawn once, turned and pulsed by CSS animations, i.e. composited), and a
  soft light on the sky round it.
* PLANETS are shaded spheres. Each gets a procedural look seeded from its id
  (rocky, desert, ocean with clouds, gas giant bands, ice giant, lava; rings
  on some), painted ONCE into a small canvas from value-noise fbm mapped onto
  a sphere, a few rows at a time between frames. The lighting is one overlay
  (terminator, night side, lit atmosphere limb) turned toward the sun as the
  body orbits — a rotate() written only when the angle moved, never a
  re-rendered texture. Moons are grey and cratered with the same phase light;
  satellites are tiny craft (body + solar panels) pointed along their orbit.
* SPACE. The board (#glass-slab) is a night sky in both themes: two star
  tiles, a nebula wash, a faint glow of each system's unit colour, a few
  brighter stars twinkling (CSS, off under prefers-reduced-motion); orbit
  rings get a soft wide glow and each planet a fading trail behind it.
* Every body is still the engine's circle .node-card (hit-testing, hover
  grow, focus, search ring, edit mode untouched): the skin is children of the
  card with pointer-events off, shown only on a resting circle. Edit mode is a
  flat version (plain discs in each body's colour, nothing animated); print
  drops the skin.

The per-frame contract with solar_draw.py: its animation loop, after placing
the bodies, calls window._altoSkinTick(plan, bodies, tSeconds) (bodies: id ->
{rx, ry} or {x, y}). Until that lands — or if it is never called — the skin
runs its own light loop (<= 30 fps, asleep while nothing moves) reading the
bodies' style.left/top. No engine patch: the skin wraps window._altoSolarLayout
(to dress the bodies after each layout, edit mode's included) and
window._altoSolarLines (the connections recoloured for a night sky in the light
theme). window._altoSkinStats exposes tick timings and texture hashes for tests.
"""
from __future__ import annotations

from .solar_draw import _slim

_P = "html.alto-stars:not(.mobile)"
# a resting circle (solar_draw's own rest selector)
_R = _P + " #world .node[data-solar]:not(.focused):not(.sol-closing)"
_E = "html.alto-stars.alto-editing:not(.mobile) #world .node[data-solar]:not(.focused):not(.sol-closing)"

STARS_CSS = r"""
  .node-card>.sk{display:none;}
  P #world #glass-slab:not(#_){background:var(--sk-sky,linear-gradient(180deg,#05070f,#0a0b1d 50%,#06050f)) !important;opacity:1 !important;
    -webkit-backdrop-filter:none !important;backdrop-filter:none !important;box-shadow:none !important;border:0 !important;}
  .sk-sky{position:absolute;left:0;top:0;right:0;bottom:0;z-index:5;pointer-events:none;}
  html.mobile .sk-sky,html:not(.alto-stars) .sk-sky{display:none !important;}
  .sk-sky>*{position:absolute;pointer-events:none;border-radius:50%;}
  .sk-cor{animation:sk-spin 300s linear infinite;}
  .sk-cacc{animation:sk-spin 150s linear infinite reverse;}
  .sk-hz{background:radial-gradient(circle closest-side,#000 0,#000 84%,rgba(255,236,210,.9) 90%,rgba(255,236,210,0) 100%);}
  P #solar-svg .sk-belt{fill:rgb(176,164,150);}
  .sk-prom{animation:sk-spin 520s linear infinite reverse,sk-pulse 6s ease-in-out infinite alternate;}
  .sk-tw{width:3px;height:3px;background:#fff;box-shadow:0 0 4px 1px rgba(190,215,255,.8);animation:sk-tw 3s ease-in-out infinite alternate;}
  @keyframes sk-spin{to{transform:rotate(360deg);}}
  @keyframes sk-pulse{from{opacity:.5;}to{opacity:1;}}
  @keyframes sk-tw{from{opacity:.2;}to{opacity:1;}}
  P #solar-svg .sol-ring{stroke:rgb(170,195,255);stroke-opacity:.17;stroke-width:1.1;}
  P #solar-svg .sol-ring.sol-m{stroke-opacity:.12;stroke-width:.9;}
  P #solar-svg .sk-rg{fill:none;stroke:rgb(150,180,255);stroke-opacity:.05;stroke-width:7;}
  P #solar-svg .sol-spoke{stroke:rgb(180,200,255);stroke-opacity:.12;stroke-width:1.2;}
  P #solar-svg .sol-link{stroke:rgb(200,215,255);stroke-opacity:.22;}
  P #solar-svg [fill^="url(#sol-glow"]{display:none;}
  P #solar-svg .sk-tr{fill:none;stroke:rgb(195,215,255);stroke-linecap:round;}
  R .node-card{background:transparent !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;
    border-color:transparent !important;box-shadow:none !important;overflow:visible !important;isolation:isolate;}
  R .node-card::before,R .node-card::after{display:none !important;}
  R .node-card:hover{box-shadow:0 0 0 1.5px rgba(205,220,255,.7) !important;}
  P #world .node[data-solar=sat]:not(.focused):not(.sol-closing) .node-card{border-color:rgba(170,190,255,.25) !important;}
  R .node-card>.sk.sk{display:block !important;position:absolute;pointer-events:none;left:50%;top:50%;}
  R .sk-tex{width:calc(var(--sd)*1.16);height:calc(var(--sd)*1.16);margin:calc(var(--sd)*-.58) 0 0 calc(var(--sd)*-.58);
    background:radial-gradient(circle closest-side,var(--sk-c) 85.5%,transparent 86.5%);}
  R .sk-tex.ok{background:none;}
  R .sk-lit,R .sk-sun,R .sk-gran{width:var(--sd);height:var(--sd);margin:calc(var(--sd)/-2) 0 0 calc(var(--sd)/-2);border-radius:50%;}
  R .sk-lit{background:linear-gradient(90deg,rgba(2,4,12,.9) 0%,rgba(2,4,12,.8) 33%,rgba(2,4,12,.38) 48%,rgba(2,4,12,0) 62%),
    radial-gradient(circle closest-side,rgba(var(--sk-a),0) 80%,rgba(var(--sk-a),.55) 96%,rgba(var(--sk-a),0) 100%),
    radial-gradient(circle at 74% 50%,rgba(255,252,240,.2) 0,rgba(255,252,240,0) 42%);}
  R .sk-lit.m{background:linear-gradient(90deg,rgba(4,5,10,.94) 0%,rgba(4,5,10,.88) 40%,rgba(4,5,10,.32) 50%,rgba(4,5,10,0) 57%),
    radial-gradient(circle at 72% 50%,rgba(255,255,250,.16) 0,rgba(255,255,250,0) 45%);}
  R .sk-lit.a{opacity:.7;}
  R .sk-sun{background:radial-gradient(circle closest-side,var(--c0) 0%,var(--c0) 28%,var(--c1) 58%,var(--c2) 84%,var(--c3) 100%);}
  R .sk-gran{animation:sk-spin 260s linear infinite;}
  R .sk-gran.b{animation-duration:410s;animation-direction:reverse;}
  R .sk-rb,R .sk-rf{width:calc(var(--sd)*2.4);height:calc(var(--sd)*2.4);margin:calc(var(--sd)*-1.2) 0 0 calc(var(--sd)*-1.2);}
  R .sk-bh{width:var(--sd);height:var(--sd);margin:calc(var(--sd)/-2) 0 0 calc(var(--sd)/-2);border-radius:50%;
    background:radial-gradient(circle closest-side,#000 0,#000 80%,rgba(255,240,210,.95) 86%,rgba(255,170,90,.45) 92%,rgba(255,120,60,0) 100%);}
  R .sk-tail{width:calc(var(--sd)*4);height:calc(var(--sd)*1.25);margin:calc(var(--sd)*-.625) 0 0 0;transform-origin:0 50%;}
  R .sk-craft{width:calc(var(--sd)*1.3);height:calc(var(--sd)*1.3);margin:calc(var(--sd)*-.65) 0 0 calc(var(--sd)*-.65);}
  P #world .node[data-solar] .sol-face{color:#f3f6ff;text-shadow:0 0 3px rgba(0,0,0,.95);}
  P #world .node[data-solar] .sol-face b{opacity:.92;}
  P #world .node[data-solar=sun] .sol-face{color:var(--sk-ink,#2a1400);text-shadow:0 0 4px rgba(255,250,228,.95);}
  /* the whole chart (solar_draw's zoomed-out view): the labels are a few px tall, their shadows cost every frame */
  P #canvas.sol-ov #world .node[data-solar] .sol-face,P #canvas.sol-ovanim #world .node[data-solar] .sol-face{text-shadow:none;}
  @media (prefers-reduced-motion:reduce){ .sk-cor,.sk-cacc,.sk-prom,.sk-tw,.sk-gran{animation:none !important;} }
  html.sk-still .sk-cor,html.sk-still .sk-cacc,html.sk-still .sk-prom,html.sk-still .sk-tw,html.sk-still .sk-gran{animation-play-state:paused !important;}
  html.alto-editing .sk-cor,html.alto-editing .sk-cacc,html.alto-editing .sk-prom,html.alto-editing .sk-tw,html.alto-editing .sk-gran{animation:none !important;}
  html.alto-stars.alto-editing:not(.mobile) #world #glass-slab:not(#_){background:#0a0c1a !important;}
  html.alto-stars.alto-editing .sk-sky,html.alto-stars.alto-editing #solar-svg .sk-tr,html.alto-stars.alto-editing #solar-svg .sk-belt{display:none !important;}
  E .node-card>.sk.sk{display:none !important;}
  E .node-card{background:var(--sk-c) !important;}
  @media print{
    .sk-sky,#solar-svg .sk-tr,#solar-svg .sk-rg,#solar-svg .sk-belt{display:none !important;}
    html.alto-stars #world #glass-slab:not(#_){background:none !important;}
    E .node-card>.sk.sk,R .node-card>.sk.sk{display:none !important;}
    R .node-card{background:#fff !important;border:1.5px solid #777 !important;}
    html.alto-stars #world .node[data-solar] .sol-face{color:#111 !important;text-shadow:none !important;}
  }
""".replace("E .", _E + " .").replace("R .", _R + " .").replace("P #", _P + " #")

STARS_JS = r"""
(function(){
var de=document.documentElement, NS='http://www.w3.org/2000/svg', DEG=180/Math.PI;
var PADW=0, S=null, world=null, BB={}, IDS=[], SUNC={}, TILES=null, ready=false, extT=-1e9, fbLast=0, fbR=0, fbS=0, idle=0, Q=[], qT=0, SPIN=-1;
var ST={t:[]};
function desk(){ return !de.classList.contains('mobile'); }
/* the skin is the Star chart look's (solar_draw's look switch: window._altoSolarLook, or the
   html.alto-solar-stars / -plain classes; with neither, the plan's own style) */
function look(){ var L=window._altoSolarLook; if(L && L.get) return L.get()==='stars';
  if(de.classList.contains('alto-solar-plain')) return false; if(de.classList.contains('alto-solar-stars')) return true;
  var s=window._ALTO_SOLAR; return !!(s && s.style!=='spoke'); }
function on(){ var s=window._ALTO_SOLAR; return !!(s && s.nodes) && look(); }
function still(){ var M=window._altoSolarMotion; de.classList.toggle('sk-still', !!(M && M.get && !M.get())); }
/* ── seeded randomness and value noise (same pixels on every load) ── */
function hash(s){ var h=2166136261; for(var i=0;i<s.length;i++){ h^=s.charCodeAt(i); h=Math.imul(h, 16777619); } return h>>>0; }
function rng(a){ a>>>=0; return function(){ a=(a+0x6D2B79F5)>>>0; var t=Math.imul(a^a>>>15, a|1); t^=t+Math.imul(t^t>>>7, t|61); return ((t^t>>>14)>>>0)/4294967296; }; }
function noise(seed){
  var r=rng(seed), p=new Uint16Array(512), v=new Float32Array(256), i, j, t;
  for(i=0;i<256;i++){ p[i]=i; v[i]=r(); }
  for(i=255;i>0;i--){ j=(r()*(i+1))|0; t=p[i]; p[i]=p[j]; p[j]=t; }
  for(i=0;i<256;i++) p[i+256]=p[i];
  return function(x, y){ var xi=Math.floor(x), yi=Math.floor(y), xf=x-xi, yf=y-yi; xi&=255; yi&=255;
    var u=xf*xf*(3-2*xf), w=yf*yf*(3-2*yf), a=v[p[p[xi]+yi]], b=v[p[p[xi+1]+yi]], c=v[p[p[xi]+yi+1]], d=v[p[p[xi+1]+yi+1]];
    return a+(b-a)*u+(c-a)*w+(a-b-c+d)*u*w; };
}
function fb(n, x, y, o){ var s=0, a=.5, t=0; for(var i=0;i<o;i++){ s+=a*n(x, y); t+=a; a*=.5; x*=2.03; y*=2.03; } return s/t; }
function cl(t){ return t<0 ? 0 : t>1 ? 1 : t; }
function mix(a, b, t){ t=cl(t); return [a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t, a[2]+(b[2]-a[2])*t]; }
function rgb(c){ return 'rgb('+c.map(Math.round).join(',')+')'; }
/* ── what each body is ── */
var KINDS=['rocky','desert','ocean','gas','ice','lava'], KW=[.17,.16,.19,.22,.14,.12];
var ATM={rocky:[200,200,210,.12], desert:[235,160,120,.3], ocean:[120,185,255,.55], gas:[235,205,160,.3], ice:[150,225,255,.5], lava:[255,130,60,.4], moon:[0,0,0,0], asteroid:[0,0,0,0], comet:[170,220,255,.35], blackhole:[255,170,80,0]};
var FLAT={rocky:'#8a8076', desert:'#b8693c', ocean:'#2f6fb8', gas:'#c9a272', ice:'#71bcd6', lava:'#6a3a2c', moon:'#8d8e94', sat:'#4a5168', sun:'#ffcf4a', asteroid:'#7a6e64', comet:'#a9c9e0', blackhole:'#141018'};
var STARS=[['#fffbea','#ffe680','#ffb432','#e8740e','255,190,90','#2a1400'], ['#fff2d8','#ffc870','#ff8f2a','#d3520c','255,150,70','#2a1000'],
  ['#ffffff','#fff4c8','#ffd780','#f0a43c','255,225,160','#2a1800'], ['#ffffff','#e6f0ff','#b4ccff','#7d9cff','160,190,255','#0b1a40']];
/* a plan's look (LEAD: nodes[id].look) overrules the role's: a black hole, a comet, an asteroid */
function kindOf(id, role, look){ if(/^(blackhole|comet|asteroid)$/.test(look||'')) return look; if(role!=='planet') return role; var r=rng(hash(id+'#k'))(), a=0;
  for(var i=0;i<KW.length;i++){ a+=KW[i]; if(r<a) return KINDS[i]; } return 'rocky'; }
/* a body's surface: (longitude, latitude) on the sphere -> colour */
function painter(kind, id){
  var R=rng(hash(id)), n1=noise(hash(id+'a')), n2=noise(hash(id+'b')), sx=R()*40, sy=R()*40, j=[.9+R()*.2, .9+R()*.2, .9+R()*.2], f;
  if(kind==='gas'){
    var G=[[[236,220,190],[205,160,110],[150,100,70]], [[240,226,180],[218,190,130],[176,146,98]], [[222,204,232],[170,140,200],[108,88,160]], [[214,236,228],[140,190,190],[78,128,140]]][(R()*4)|0];
    var bands=4+R()*5, ph=R()*6, st=R()<.6 ? [(R()-.5)*1.2, (R()-.5)*1.2, .14+R()*.1] : null;
    f=function(lo, la){ var b=Math.sin(la*bands*2+ph+fb(n1, lo*1.3+sx, la*5+sy, 4)*3.4)*.5+.5, c=b<.5 ? mix(G[0], G[1], b*2) : mix(G[1], G[2], b*2-1);
      if(st){ var dx=(lo-st[0])/(st[2]*1.9), dy=(la-st[1])/st[2], e=dx*dx+dy*dy; if(e<1) c=mix(c, [190,92,60], (1-e)*.9); }
      return c; };
  } else if(kind==='ice'){
    var I=R()<.5 ? [120,200,222] : [72,112,215];
    f=function(lo, la){ var v=1+Math.sin(la*9+fb(n1, lo*2+sx, la*4+sy, 3)*2.4)*.07; return [I[0]*v, I[1]*v, I[2]*v]; };
  } else if(kind==='ocean'){
    var sea=.5+R()*.08;
    f=function(lo, la){ var h=fb(n1, lo*2.1+sx, la*2.1+sy, 5), c=h<sea ? mix([10,38,100], [42,108,182], h/sea) : mix([64,118,58], [158,130,88], (h-sea)*4.5);
      if(Math.abs(la)>1.18+(h-.5)*.5) c=[236,240,250];
      var k=fb(n2, lo*2.6+sx, la*4.4+sy, 4); return mix(c, [250,252,255], (k-.5)*3); };
  } else if(kind==='desert'){
    f=function(lo, la){ var h=fb(n1, lo*2.4+sx, la*2.4+sy, 5), c=mix([110,44,24], [218,128,72], h*1.5-.25);
      return Math.abs(la)>1.3+(h-.5)*.4 ? mix(c, [240,236,232], .9) : c; };
  } else if(kind==='lava'){
    f=function(lo, la){ var h=fb(n1, lo*3+sx, la*3+sy, 4), r=1-Math.abs(fb(n2, lo*3.6+sx, la*3.6+sy, 4)*2-1), c=mix([34,25,23], [84,64,56], h);
      return r>.84 ? mix(mix(c, [255,128,36], (r-.84)*9), [255,226,130], (r-.93)*14) : c; };
  } else if(kind==='comet'){
    f=function(lo, la){ var h=fb(n1, lo*3+sx, la*3+sy, 4); return mix([96,108,122], [214,228,240], h*1.3-.1); };
  } else if(kind==='asteroid'){
    f=function(lo, la){ var h=fb(n1, lo*3+sx, la*3+sy, 4); return mix([62,54,48], [150,136,120], h); };
  } else if(kind==='moon'){
    f=function(lo, la){ var h=fb(n1, lo*2.2+sx, la*2.2+sy, 4), m=fb(n2, lo*1.1+sx, la*1.1+sy, 3), g=92+h*96-(m>.54 ? (m-.54)*190 : 0); return [g, g*.985, g*.96]; };
  } else {
    f=function(lo, la){ var h=fb(n1, lo*2.4+sx, la*2.4+sy, 5), c=mix([58,54,52], [176,164,148], h); return fb(n2, lo*5, la*5, 2)>.68 ? mix(c, [40,36,34], .45) : c; };
  }
  return function(lo, la){ var c=f(lo, la); return [c[0]*j[0], c[1]*j[1], c[2]*j[2]]; };
}
function craters(id, n){ var R=rng(hash(id+'c')), o=[]; for(var i=0;i<n;i++){ var a=R()*6.283, r=Math.sqrt(R())*.86; o.push([Math.cos(a)*r, Math.sin(a)*r, .04+Math.pow(R(), 2.2)*.2]); } return o; }
/* ── canvases drawn once, a few rows at a time between frames ── */
function job(cv, N, row, done){ cv.width=cv.height=N; var ctx=cv.getContext('2d'), img=ctx.createImageData(N, N), y=0;
  return {cv:cv, step:function(dl){ while(y<N && performance.now()<dl) row(img.data, y++); return y>=N; },
    end:function(){ ctx.putImageData(img, 0, 0); cv._h=sum(img.data); if(done) done(); }}; }
function sum(D){ var h=2166136261; for(var i=0;i<D.length;i+=7) h=Math.imul(h^D[i], 16777619); return (h>>>0).toString(36); }
function put(D, i, c, a){ D[i]=c[0]; D[i+1]=c[1]; D[i+2]=c[2]; D[i+3]=Math.round(cl(a)*255); }
function texJob(k){
  var N=Math.min(256, Math.round(k.d*2.32)), rd=N/2/1.16, h=N/2, P=painter(k.kind, k.id), A=ATM[k.kind]||ATM.moon,
    cr=k.kind==='moon' ? craters(k.id, 9+(hash(k.id)%7)) : /rocky|asteroid/.test(k.kind) ? craters(k.id, 5) : null,
    ne=k.kind==='asteroid' ? noise(hash(k.id+'e')) : null;
  return job(k.tex, N, function(D, y){
    var ny=(y+.5-h)/rd;
    for(var x=0;x<N;x++){
      var nx=(x+.5-h)/rd, my=ny, i=(y*N+x)*4, ha=0;
      if(ne){ var th=Math.atan2(my, nx), e0=.86+.14*fb(ne, Math.cos(th)*1.7+3, Math.sin(th)*1.7+3, 3); nx/=e0; my/=e0; }   /* a lumpy rock */
      var q=nx*nx+my*my, r=Math.sqrt(q);
      if(r>=1.16) continue;
      if(r>1-1/rd){ var t=Math.max(0, (r-1)/.16); ha=A[3]*Math.pow(1-t, 2.4); }
      if(r>=1+.5/rd){ put(D, i, A, ha); continue; }
      var z=Math.sqrt(Math.max(0, 1-q)), c=P(Math.atan2(nx, z), Math.asin(cl(my*.5+.5)*2-1), nx, my), l=.68+.32*z;
      if(cr) for(var m=0;m<cr.length;m++){ var e=Math.hypot(nx-cr[m][0], my-cr[m][1])/cr[m][2]; if(e<1.15) l*=e<.82 ? .8+e*.1 : 1.14; }
      var e2=cl((1-r)*rd+.5), a=e2+ha*(1-e2), w=a>0 ? e2/a : 1;
      put(D, i, [c[0]*l*w+A[0]*(1-w), c[1]*l*w+A[1]*(1-w), c[2]*l*w+A[2]*(1-w)], a);
    }
  }, function(){ k.tex.classList.add('ok'); });
}
function ringJob(k, cv, front){
  var R=rng(hash(k.id+'r')), bh=k.kind==='blackhole', ps=(R()-.5)*(bh ? .5 : .9), kk=bh ? .3 : .22+R()*.2, ri=bh ? 1.12 : 1.3+R()*.15, ro=bh ? 2.35 : ri+.45+R()*.45, cs=Math.cos(ps), sn=Math.sin(ps),
    C=R()<.5 ? [218,202,172] : [188,204,226], n=noise(hash(k.id+'g')), N=Math.min(320, Math.round(k.d*3.6));
  return job(cv, N, function(D, y){
    for(var x=0;x<N;x++){ var u=(x+.5-N/2)/(N/2)*2.4, v=(y+.5-N/2)/(N/2)*2.4, xr=u*cs+v*sn, yr=-u*sn+v*cs;
      if((yr>0)!==front) continue;
      var p=Math.hypot(xr, yr/kk); if(p<=ri || p>=ro) continue;
      var t=(p-ri)/(ro-ri), a=(.3+.7*n(p*14, 3))*Math.min(1, t*8, (1-t)*8)*(Math.abs(t-.62)<.035 ? .15 : .75);
      if(bh){ a=Math.pow(1-t, .8)*Math.min(1, t*12)*(.55+.45*n(p*9, 5))*(1-.45*xr/p);       /* hot inside, the near-light side brighter */
        put(D, (y*N+x)*4, t<.35 ? mix([255,250,232], [255,176,84], t/.35) : mix([255,176,84], [170,40,30], (t-.35)/.65), a); continue; }
      put(D, (y*N+x)*4, mix(C, [C[0]*.7, C[1]*.7, C[2]*.7], n(p*5, 9)), a); }
  });
}
function granJob(k, cv, b){
  var N=Math.min(256, Math.round(k.d*1.6)), n=noise(hash(k.id+(b ? 'h' : 'g'))), R=rng(hash(k.id+'s')), sp=b ? [] : [[(R()-.5)*.9, (R()-.5)*.9, .045]];
  return job(cv, N, function(D, y){
    for(var x=0;x<N;x++){ var nx=(x+.5)/N*2-1, ny=(y+.5)/N*2-1, r=Math.hypot(nx, ny); if(r>=.995) continue;
      var g=fb(n, nx*17+(b ? 50 : 0), ny*17, 2), i=(y*N+x)*4, f=Math.sqrt(1-r*r);
      if(g<.42) put(D, i, [190,80,0], (.42-g)*.9*f); else if(g>.6) put(D, i, [255,255,236], (g-.6)*.8*f);
      for(var s=0;s<sp.length;s++){ var e=Math.hypot(nx-sp[s][0], ny-sp[s][1])/sp[s][2]; if(e<1) put(D, i, [70,26,0], e<.45 ? .8 : .35); } }
  });
}
function corJob(k, cv, g){
  var N=256, n=noise(hash(k.id+'o')), C=g.split(',').map(Number);
  return job(cv, N, function(D, y){
    for(var x=0;x<N;x++){ var nx=(x+.5)/N*2-1, ny=(y+.5)/N*2-1, r=Math.hypot(nx, ny)*3.6; if(r<.96 || r>3.6) continue;
      var th=Math.atan2(ny, nx), s=fb(n, Math.cos(th)*3+4, Math.sin(th)*3+4, 3), b=Math.exp(-(r-1)*1.7)*(.3+1.6*s*s*s)*cl((3.6-r)*2);
      put(D, (y*N+x)*4, mix([255,255,245], C, (r-1)*.8), b*.95); }
  });
}
function promDraw(k, cv, g){
  var N=192, ctx=cv.getContext('2d'), R=rng(hash(k.id+'p')), c=N/2, rr=N/2/1.6;
  cv.width=cv.height=N; ctx.globalCompositeOperation='lighter'; ctx.lineCap='round';
  for(var i=0;i<3;i++){ var a=R()*6.283, w=(.05+R()*.08)*rr*2, h=(.1+R()*.2)*rr;
    ctx.save(); ctx.translate(c+Math.cos(a)*rr*.98, c+Math.sin(a)*rr*.98); ctx.rotate(a+Math.PI/2);
    ctx.shadowColor='rgba(255,80,30,.8)'; ctx.shadowBlur=5;
    for(var q=0;q<3;q++){ ctx.strokeStyle='rgba(255,'+(100+((R()*70)|0))+',50,'+(.25+R()*.3).toFixed(2)+')'; ctx.lineWidth=.8+R()*1.4;
      ctx.beginPath(); ctx.ellipse((q-1)*w*.08, 0, w/2*(.8+q*.12), h*(.75+R()*.35), 0, Math.PI, 2*Math.PI); ctx.stroke(); }
    ctx.restore(); }
}
function tailDraw(k, cv){
  var W=256, H=80, x=cv.getContext('2d'), m=H/2; cv.width=W; cv.height=H;
  var g=x.createLinearGradient(0, 0, W, 0); g.addColorStop(0, 'rgba(255,244,220,.75)'); g.addColorStop(.35, 'rgba(255,236,205,.3)'); g.addColorStop(1, 'rgba(255,230,200,0)');
  x.fillStyle=g; x.beginPath(); x.moveTo(6, m-4); x.quadraticCurveTo(W*.5, m-10, W, m-36); x.lineTo(W, m+6); x.quadraticCurveTo(W*.5, m+8, 6, m+4); x.fill();
  var i=x.createLinearGradient(0, 0, W, 0); i.addColorStop(0, 'rgba(150,205,255,.9)'); i.addColorStop(1, 'rgba(120,180,255,0)');
  x.fillStyle=i; x.beginPath(); x.moveTo(6, m-2.5); x.lineTo(W, m-3); x.lineTo(W, m+3); x.lineTo(6, m+2.5); x.fill();
}
function craftDraw(k, cv){
  var R=rng(hash(k.id+'v')), N=88, x=cv.getContext('2d'), pc=R()<.6 ? ['#1d3f8f','#5d87d8'] : ['#2a2f45','#7f8bb5'], bc=R()<.6 ? ['#f1c34a','#8a5a10'] : ['#e8ecf2','#7d8492'];
  cv.width=cv.height=N; x.lineWidth=1;
  [[6,34],[54,82]].forEach(function(p){ var gr=x.createLinearGradient(0, 36, 0, 52); gr.addColorStop(0, pc[1]); gr.addColorStop(1, pc[0]);
    x.fillStyle=gr; x.fillRect(p[0], 36, p[1]-p[0], 16); x.strokeStyle='rgba(190,215,255,.55)';
    for(var q=p[0]+7;q<p[1];q+=7){ x.beginPath(); x.moveTo(q+.5, 36); x.lineTo(q+.5, 52); x.stroke(); }
    x.strokeRect(p[0]+.5, 36.5, p[1]-p[0]-1, 15); });
  x.strokeStyle='#c9ced8'; x.lineWidth=2; x.beginPath(); x.moveTo(34, 44); x.lineTo(54, 44); x.stroke();
  var gb=x.createLinearGradient(36, 34, 52, 54); gb.addColorStop(0, bc[0]); gb.addColorStop(1, bc[1]); x.fillStyle=gb; x.fillRect(37, 34, 14, 20);
  x.fillStyle='#e6e9ef'; x.beginPath(); x.arc(44, 29, 5, 0, 7); x.fill(); x.strokeStyle='#e6e9ef'; x.lineWidth=1; x.beginPath(); x.moveTo(44, 24); x.lineTo(44, 17); x.stroke();
}
function tiles(){
  if(TILES) return TILES; TILES={u:null};
  var mk=function(N, css, cnt, seed, big){ var cv=document.createElement('canvas'), x=cv.getContext('2d'), R=rng(seed), k=N/css;
    cv.width=cv.height=N;
    for(var i=0;i<cnt;i++){ var px=R()*N, py=R()*N, s=(.35+Math.pow(R(), 7)*big)*k, c=[[255,255,255],[205,218,255],[255,236,212],[255,214,196]][(R()*4)|0], a=.3+R()*.65;
      if(s>1.4*k){ var gr=x.createRadialGradient(px, py, 0, px, py, s*3); gr.addColorStop(0, 'rgba('+c+','+a+')'); gr.addColorStop(.3, 'rgba('+c+','+a*.35+')'); gr.addColorStop(1, 'rgba('+c+',0)');
        x.fillStyle=gr; x.fillRect(px-s*3, py-s*3, s*6, s*6); }
      x.fillStyle='rgba('+c+','+a+')'; x.beginPath(); x.arc(px, py, s, 0, 7); x.fill(); }
    return cv; };
  var A=mk(1024, 512, 170, 7, 1.6), B=mk(600, 300, 230, 11, .4), out=[], left=2;
  [A, B].forEach(function(cv, i){ var fin=function(u){ out[i]=u; if(--left===0){ TILES.u=out; sky(); } };
    if(cv.toBlob) cv.toBlob(function(b){ fin(b ? URL.createObjectURL(b) : cv.toDataURL()); }); else fin(cv.toDataURL()); });
  return TILES;
}
/* ── the board ── */
function hexRgb(h){ h=String(h||'').replace('#', ''); if(h.length===3) h=h.replace(/(.)/g, '$1$1'); var v=parseInt(h.slice(0, 6), 16); return isNaN(v) ? null : [v>>16&255, v>>8&255, v&255]; }
function sky(){
  var sl=document.getElementById('glass-slab'), T=tiles(); if(!sl) return;
  var v='radial-gradient(60% 34% at 22% 18%,rgba(112,64,176,.2),rgba(112,64,176,0) 70%),radial-gradient(50% 30% at 80% 46%,rgba(36,112,170,.16),rgba(36,112,170,0) 70%),'+
    'radial-gradient(56% 28% at 34% 82%,rgba(170,52,112,.13),rgba(170,52,112,0) 70%),linear-gradient(180deg,#05070f,#0a0b1d 50%,#06050f)';
  if(T.u) v='url('+T.u[0]+') 0 0/512px 512px,url('+T.u[1]+') 37px 91px/300px 300px,'+v;
  sl.style.setProperty('--sk-sky', v);
}
function unitRgb(si){ var s=(S.systems||[])[si], pm=(s && typeof PHASE_META!=='undefined') ? PHASE_META[s.unit] : null; return (pm && hexRgb(pm.colorRaw)) || [120,110,200]; }
function el(t, c, p){ var e=document.createElement(t); e.className=c; if(p) p.appendChild(e); return e; }
function board(PAD){
  var old=world.querySelector('.sk-sky'); if(old) old.remove();
  var sk=el('div', 'sk-sky'), sl=document.getElementById('glass-slab'); sk.setAttribute('aria-hidden', 'true');
  world.insertBefore(sk, sl && sl.parentNode===world ? sl.nextSibling : world.firstChild);
  sky();
  (S.systems||[]).forEach(function(s, si){
    var k=BB[s.sun]; if(!k || !k.n || k.kind!=='sun') return;
    var u=unitRgb(si), d=k.d, R=Math.max(s.R||d*3, d*3), nb=el('div', '', sk);
    nb.style.cssText='left:'+(k.x-R*1.1)+'px;top:'+(k.y-R*1.1)+'px;width:'+R*2.2+'px;height:'+R*2.2+'px;background:radial-gradient(closest-side,rgba('+u+',.12),rgba('+u+',.045) 55%,rgba('+u+',0))';
    var C=SUNC[s.sun]||(SUNC[s.sun]={}), g=k.star[4];
    var gl=el('div', '', sk); gl.style.cssText='left:'+(k.x-d*3.5)+'px;top:'+(k.y-d*3.5)+'px;width:'+d*7+'px;height:'+d*7+'px;background:radial-gradient(closest-side,rgba('+g+',.34),rgba('+g+',.13) 26%,rgba('+g+',.04) 55%,rgba('+g+',0))';
    if(!C.cor || C.d!==d){ C.d=d; C.cor=el('canvas', 'sk-cor'); Q.push(corJob(k, C.cor, g)); C.prom=el('canvas', 'sk-prom'); promDraw(k, C.prom, g); }
    [[C.cor, 3.6], [C.prom, 1.6]].forEach(function(q){ var w=d*q[1]; q[0].style.cssText='left:'+(k.x-w/2)+'px;top:'+(k.y-w/2)+'px;width:'+w+'px;height:'+w+'px'; sk.appendChild(q[0]); });
  });
  var co=S.core;                                    /* the galactic core's black hole (LEAD: plan.core {x, y, r}) */
  if(co && co.r>0){ var cy=co.y+PAD, put2=function(c, w){ c.style.cssText='left:'+(co.x-w/2)+'px;top:'+(cy-w/2)+'px;width:'+w+'px;height:'+w+'px'; sk.appendChild(c); };
    var gw=el('div', ''); gw.style.background='radial-gradient(closest-side,rgba(255,190,140,.22),rgba(180,90,160,.08) 45%,rgba(120,60,160,0))'; put2(gw, co.r*12);
    if(!SUNC._core || SUNC._core.r!==co.r){ var cv=el('canvas', 'sk-cacc'); SUNC._core={r:co.r, c:cv}; Q.unshift(coreJob(cv)); }
    put2(SUNC._core.c, co.r*8); var hz=el('div', 'sk-hz'); put2(hz, co.r*2.3); }
  var W=world.offsetWidth, H=Math.max(world.offsetHeight, (S.world||{}).h||0), R=rng(4242), n=Math.max(12, Math.min(64, Math.round(W*H/90000)));
  for(var i=0;i<n;i++){ var t=el('div', 'sk-tw', sk); t.style.cssText='left:'+Math.round(R()*W)+'px;top:'+Math.round(PAD+R()*(H-PAD))+'px;animation-duration:'+(2+R()*3).toFixed(2)+'s;animation-delay:-'+(R()*5).toFixed(2)+'s'; }
}
/* the core's accretion disc, face on: hot spiral arms round a black horizon (turned by CSS) */
function coreJob(cv){
  var N=320, n=noise(77);
  return job(cv, N, function(D, y){
    for(var x=0;x<N;x++){ var u=(x+.5)/N*2-1, v=(y+.5)/N*2-1, p=Math.hypot(u, v)*4; if(p<1.12 || p>4) continue;
      var th=Math.atan2(v, u), t=(p-1.12)/2.88, sp=.5+.5*Math.sin(2*th+4.2*Math.log(p)+fb(n, u*6, v*6, 2)*2.5);
      put(D, (y*N+x)*4, t<.3 ? mix([255,250,235], [255,178,96], t/.3) : mix([255,178,96], [150,60,170], (t-.3)/.7), Math.pow(1-t, 1.6)*(.3+.7*sp)); }
  });
}
/* the orbit rings' glow and the planets' trails, in solar_draw's #solar-svg */
function untrail(){ [].forEach.call(document.querySelectorAll('#solar-svg .sk-trails,#solar-svg .sk-rg,#solar-svg .sk-belt'), function(e){ e.remove(); });
  IDS.forEach(function(id){ if(BB[id]) BB[id].tr=null; }); }
function trails(){
  var svg=document.getElementById('solar-svg'); untrail(); if(!svg) return;
  [].forEach.call(svg.querySelectorAll('circle.sol-ring:not(.sol-m)'), function(r){ var g=r.cloneNode(); g.setAttribute('class', 'sk-rg'); r.parentNode.insertBefore(g, r); });
  var tg=document.createElementNS(NS, 'g'); tg.setAttribute('class', 'sk-trails'); svg.insertBefore(tg, svg.firstChild ? svg.firstChild.nextSibling : null);
  IDS.forEach(function(id){ var k=BB[id]; if(!k || k.role!=='planet') return;
    k.tr=[[14, 70, .2, 2], [30, 150, .1, 1.6], [55, 260, .05, 1.2]].map(function(a){ var p=document.createElementNS(NS, 'path');
      p.setAttribute('class', 'sk-tr'); p.setAttribute('stroke-opacity', a[2]); p.setAttribute('stroke-width', a[3]); p._a=a; tg.appendChild(p); return p; });
    k.ph=null; });
  /* asteroid belts (LEAD: plan.belts [{r, w, n, seed}], round a system's sun) — a static field of grains */
  var bl=(S.belts||[]).slice(); (S.systems||[]).forEach(function(s, si){ (s.belts||[]).forEach(function(b){ bl.push(Object.assign({system:si}, b)); }); });
  bl.forEach(function(b){
    var sy=(S.systems||[])[b.system||0], c=b.cx!=null ? {x:b.cx, y:b.cy+PADW} : BB[b.sun || (sy && sy.sun)];
    if(!c || !(b.r>0)) return;
    var g=document.createElementNS(NS, 'g'), R=rng(b.seed!=null ? b.seed : hash(String(b.r))), w=b.w||40, m=Math.min(b.n||260, 900), out='';
    g.setAttribute('class', 'sk-belt');
    for(var i=0;i<m;i++){ var a=R()*6.2832, rr=b.r+(R()+R()-1)*w/2, z=(.5+Math.pow(R(), 3)*1.7).toFixed(2);
      out+='<circle cx="'+(c.x+rr*Math.cos(a)).toFixed(1)+'" cy="'+(c.y+rr*Math.sin(a)).toFixed(1)+'" r="'+z+'" fill-opacity="'+(.3+R()*.5).toFixed(2)+'"/>'; }
    g.innerHTML=out; tg.parentNode.insertBefore(g, tg); });
}
/* ── dressing the bodies, after every layout ── */
function dress(k, n, kind, d){
  var c=n.querySelector('.node-card'); if(!c) return;
  (k.els||[]).forEach(function(e){ e.remove(); });
  var f=c.querySelector('.sol-face'), els=[], add=function(t, cls){ var e=el(t, 'sk '+cls); c.insertBefore(e, f); els.push(e); return e; }, R=rng(hash(k.id+'x'));
  k.n=n; k.kind=kind; k.d=d; k.els=els; k.lit=k.tex=k.craft=k.tail=null; k.la=k.ca=null;
  if(kind==='sun'){
    k.star=STARS[k.si===0 ? 0 : ((R()*10)|0)<6 ? 0 : 1+((R()*3)|0)];
    ['--c0','--c1','--c2','--c3'].forEach(function(v, i){ n.style.setProperty(v, k.star[i]); });
    n.style.setProperty('--g', k.star[4]); n.style.setProperty('--sk-ink', k.star[5]); n.style.setProperty('--sk-c', k.star[1]);
    add('div', 'sk-sun'); Q.push(granJob(k, add('canvas', 'sk-gran'), 0)); Q.push(granJob(k, add('canvas', 'sk-gran b'), 1));
    return;
  }
  n.style.setProperty('--sk-c', FLAT[kind]); n.style.setProperty('--sk-a', (ATM[kind]||ATM.moon).slice(0, 3).join(','));
  if(kind==='sat'){ k.craft=add('canvas', 'sk-craft'); craftDraw(k, k.craft); return; }
  if(kind==='blackhole'){ Q.push(ringJob(k, add('canvas', 'sk-rb'), false)); add('div', 'sk-bh'); Q.push(ringJob(k, add('canvas', 'sk-rf'), true)); return; }
  if(kind==='comet'){ k.tail=add('canvas', 'sk-tail'); tailDraw(k, k.tail); }
  var ring=!/moon|comet|asteroid/.test(kind) && rng(hash(k.id+'#r'))()<({gas:.55, ice:.45}[kind]||.08);
  if(ring) Q.push(ringJob(k, add('canvas', 'sk-rb'), false));
  k.tex=add('canvas', 'sk-tex'); Q.push(texJob(k));
  k.lit=add('div', 'sk-lit'+(/moon|comet/.test(kind) ? ' m' : kind==='asteroid' ? ' m a' : ''));
  if(ring) Q.push(ringJob(k, add('canvas', 'sk-rf'), true));
}
function skin(){
  S=window._ALTO_SOLAR; if(!on() || !desk()){ if(ready) down(); return; }
  world=document.getElementById('world'); if(!world) return;
  de.classList.add('alto-stars'); SPIN=S.spin||-1;
  var PAD=PADW=(typeof WORLD_PAD_TOP!=='undefined') ? WORLD_PAD_TOP : 0, sys={}, keep={};
  (S.systems||[]).forEach(function(s, si){ sys[s.sun]=si; });
  IDS=Object.keys(S.nodes).filter(function(id){ return document.getElementById('node-'+id); });
  IDS.forEach(function(id){
    var P=S.nodes[id], n=document.getElementById('node-'+id), role=n.getAttribute('data-solar')||P.role, k=BB[id]||(BB[id]={id:id}), sun=id, g=0;
    while(S.nodes[sun] && S.nodes[sun].parent && g++<6) sun=S.nodes[sun].parent;
    k.sun=sun; k.par=P.parent||''; k.si=sys[sun]||0; k.role=role; k.x=P.x; k.y=P.y+PAD; keep[id]=1;
    var d=parseFloat(n.style.getPropertyValue('--sd'))||P.d, kind=role==='sun' && !P.look ? 'sun' : kindOf(id, role, P.look);
    if(k.n!==n || k.kind!==kind || k.d!==d || !k.els[0] || !k.els[0].isConnected) dress(k, n, kind, d);
  });
  Object.keys(BB).forEach(function(id){ if(!keep[id]) delete BB[id]; });
  Q.sort(function(a, b){ return (a.cv.classList.contains('sk-cor') ? 0 : 1)-(b.cv.classList.contains('sk-cor') ? 0 : 1); });
  board(PAD); trails();
  ready=true; update(null); pump(); kick();
}
function pump(){ qT=0; var dl=performance.now()+6;
  while(Q.length && performance.now()<dl){ if(Q[0].step(dl)){ Q[0].end(); Q.shift(); } }
  if(Q.length) qT=setTimeout(pump, 8); }
/* ── every frame: light toward the sun, craft along their orbit, trails behind ── */
function pos(id, bodies){ var b=bodies && bodies[id], k=BB[id];
  if(b && b.rx!=null) return [b.rx, b.ry]; if(b && b.x!=null) return [b.x, b.y];
  return k && k.n ? [parseFloat(k.n.style.left)||0, parseFloat(k.n.style.top)||0] : null; }
function turn(a, b, lim){ return b==null || Math.abs(((a-b)%360+540)%360-180)>lim; }
function update(bodies){
  if(!ready || !desk() || de.classList.contains('alto-editing')) return false;
  var t0=performance.now(), ch=false;
  IDS.forEach(function(id){ var k=BB[id], p=pos(id, bodies); if(k && p){ ch=ch || k.x!==p[0] || k.y!==p[1]; k.x=p[0]; k.y=p[1]; } });
  IDS.forEach(function(id){
    var k=BB[id], s=k && BB[k.sun]; if(!k || !s || k===s) return;
    if(k.lit){ var a=Math.atan2(s.y-k.y, s.x-k.x)*DEG; if(turn(a, k.la, .4)){ k.la=a; k.lit.style.transform='rotate('+a.toFixed(1)+'deg)';
      if(k.tail) k.tail.style.transform='rotate('+(a+180).toFixed(1)+'deg)'; } }
    if(k.craft){ var q=BB[k.par]||s, c=Math.atan2(k.y-q.y, k.x-q.x)*DEG+90; if(turn(c, k.ca, 1)){ k.ca=c; k.craft.style.transform='rotate('+c.toFixed(1)+'deg)'; } }
    if(k.tr){ var dx=k.x-s.x, dy=k.y-s.y, r=Math.hypot(dx, dy), ph=Math.atan2(dy, dx);
      if(k.ph==null || Math.abs(ph-k.ph)*r>.35){ k.ph=ph;
        k.tr.forEach(function(p){ var w=Math.min(p._a[0]/DEG, p._a[1]/r), e=ph-SPIN*w;
          p.setAttribute('d', 'M'+(s.x+r*Math.cos(ph)).toFixed(1)+' '+(s.y+r*Math.sin(ph)).toFixed(1)+'A'+r.toFixed(1)+' '+r.toFixed(1)+' 0 0 '+(SPIN<0 ? 1 : 0)+' '+(s.x+r*Math.cos(e)).toFixed(1)+' '+(s.y+r*Math.sin(e)).toFixed(1)); }); } }
  });
  if(ST.t.length>=600) ST.t.shift(); ST.t.push(performance.now()-t0);
  return ch;
}
/* solar_draw's loop calls this after placing the bodies; until it does, a light loop of our own */
window._altoSkinTick=function(plan, bodies, t){ extT=performance.now(); update(bodies); };
function fbk(){ fbR=0; if(!ready) return; var now=performance.now();
  if(now-extT<600){ fbS=setTimeout(function(){ fbS=0; kick(); }, 500); return; }
  if(now-fbLast>=32){ fbLast=now; idle=update(null) ? 0 : idle+1; }
  if(idle>45 || document.hidden){ fbS=setTimeout(function(){ fbS=0; idle=Math.min(idle, 40); kick(); }, 250); return; }
  kick(); }
function kick(){ if(!fbR && !fbS) fbR=requestAnimationFrame(fbk); }
/* the connections drawn for a night sky in the light theme too */
function relines(){
  if(de.classList.contains('dark')) return;
  var rv=document.getElementById('river-svg'), rel={}; if(!rv) return;
  (typeof CONNECTIONS!=='undefined' ? CONNECTIONS : []).forEach(function(c){ rel[c[0]+'|'+c[1]]=c[2]; });
  [].forEach.call(rv.querySelectorAll('path[data-edge]'), function(p){ var r=rel[p.getAttribute('data-edge')], col='rgb(208,212,226)';
    if(r!=='spine') try{ var ad=_lineAdapt(_lineToRgb(_lineResolveVar(COLOR_MAP[r]||'var(--line-flow)')), [12,13,20]); if(!ad) return; col='rgb('+ad.join(',')+')'; }catch(e){ return; }
    p.setAttribute('stroke', col); var sh=p.nextElementSibling; if(sh && !sh.hasAttribute('data-edge')) sh.setAttribute('stroke', 'rgba(255,255,255,0.50)'); });
}
/* the Plain look (or a phone): the skin goes, its canvases kept for the way back */
function down(){
  ready=false; de.classList.remove('alto-stars'); cancelAnimationFrame(fbR); clearTimeout(fbS); clearTimeout(qT); fbR=fbS=qT=0;
  var sk=document.querySelector('#world .sk-sky'); if(sk) sk.remove(); untrail(); }
function sw(){ if(on() && desk()){ if(!ready && document.querySelector('#world .node[data-solar]')) skin(); } else if(ready) down(); still(); }
/* the renderer's look and motion switches, listened to once they exist */
function api(){ var Lk=window._altoSolarLook, M=window._altoSolarMotion;
  if(Lk && Lk.onChange && !Lk._sk){ Lk._sk=1; Lk.onChange(function(){ requestAnimationFrame(sw); }); }
  if(M && M.onChange && !M._sk){ M._sk=1; M.onChange(still); } }
/* after the renderer's own layout / lines, ours (it calls window[k] each time) */
function wrap(k, then){ var f=window[k]; if(!f || f._sk) return;
  var w=function(){ var r=f.apply(this, arguments); try{ then(r); }catch(e){ if(window.console) console.warn('stars', e); } return r; }; w._sk=1; window[k]=w; }
function hook(){
  var s=window._ALTO_SOLAR; if(!s || !s.nodes) return;
  api();
  if(!hook.mo && typeof MutationObserver==='function'){ hook.mo=new MutationObserver(function(){ api(); sw(); }); hook.mo.observe(de, {attributes:true, attributeFilter:['class']}); }
  wrap('_altoSolarLayout', function(){ skin(); });
  wrap('_altoSolarLines', function(r){ if(r) relines(); });
  if(!ready && on() && document.querySelector('#world .node[data-solar]')) try{ skin(); }catch(e){}
  still();
}
hook();
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', hook);
window.addEventListener('afterprint', function(){ idle=0; kick(); });
window._altoSkinStats={
  get:function(){ var d=ST.t.slice().sort(function(a, b){ return a-b; }), q=function(p){ return d.length ? +d[Math.min(d.length-1, Math.floor(d.length*p))].toFixed(3) : 0; };
    return {n:d.length, p50:q(.5), p95:q(.95), max:q(1), pending:Q.length, ext:extT>0}; },
  reset:function(){ ST.t=[]; },
  hashes:function(){ var o={}; [].forEach.call(document.querySelectorAll('#world canvas.sk,#world .sk-sky canvas'), function(c, i){ var n=c.closest('.node'), id=(n ? n.id : 'sky'+i)+':'+c.className;
    o[id]=c._h || (c.className.indexOf('sk-craft')>=0 || c.className.indexOf('sk-prom')>=0 ? sum(c.getContext('2d').getImageData(0, 0, c.width, c.height).data) : null); }); return o; }
};
})();
"""

STARS_JS = _slim(STARS_JS)
STARS_CSS = _slim(STARS_CSS)

