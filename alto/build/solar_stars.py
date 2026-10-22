"""The Star chart look's skin: what makes a System page (outline, layout
"solar") in its Star chart look (the default; solar_draw's in-page toggle
flips it to System) look like a real solar system.

solar_draw.py draws the circles, rings and spokes and moves the bodies; this
module only dresses them. blocks.py emits it on every System page; it is
on only in the Star chart look on desktop (window._altoSolarLook, or the
html.alto-solar-stars / -hub classes, or else the plan's style "orbit") and
comes off whole in the System look (its canvases kept for the way back). With
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
  satellites are tiny craft pointed along their orbit, a kind each fixed by its id (a
  communications satellite, a probe, a space telescope, a CubeSat), and in each system the
  satellite with the most to read is a space station (plan nodes[id].station).
* SPACE. The canvas (the window under the bars, at every zoom: no board
  rectangle) is a night sky in both themes: two star tiles, a nebula wash;
  on the chart a faint glow of each system's unit colour, a few brighter
  stars twinkling (CSS, off under prefers-reduced-motion); orbit
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
from .retro import BRAND_CSS, CHROME_CSS, FRAME_CSS, WORDMARK_CSS, scoped, _slim as _rt_slim   # shared with every format's Retro (retro.py)

_P = "html.alto-stars:not(.mobile)"
# a resting circle (solar_draw's own rest selector)
_R = _P + " #world .node[data-solar]:not(.focused):not(.sol-closing)"
# any body, and an enlarged one (focused, or shrinking home)
_K = _P + " #world .node[data-solar]"
_F = _P + " #world .node[data-solar]:is(.focused,.sol-closing)"
_E = "html.alto-stars.alto-editing:not(.mobile) #world .node[data-solar]:not(.focused):not(.sol-closing)"

STARS_CSS = r"""
  .node-card>.sk{display:none;}
  /* space fills the canvas (the window under the bars) at every zoom — no board rectangle; its stars are at
     infinity, so they hold still while the chart pans and zooms (the twinkling ones and the glows ride the chart) */
  html.alto-stars:not(.mobile) #canvas{background:var(--sk-sky,linear-gradient(180deg,#05070f,#0a0b1d 50%,#06050f));}
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
  P #solar-svg .sol-ring{stroke:rgb(170,195,255);stroke-opacity:calc(.27 * var(--lk,1));stroke-width:calc(1.35px * var(--lw,1));}
  P #solar-svg .sol-ring.sol-m{stroke-opacity:calc(.2 * var(--lk,1));stroke-width:calc(1.1px * var(--lw,1));}
  P #solar-svg .sk-rg{fill:none;stroke:rgb(150,180,255);stroke-opacity:.05;stroke-width:7;}
  P #solar-svg .sol-spoke{stroke:rgb(180,200,255);stroke-opacity:calc(.26 * var(--lk,1));stroke-width:calc(1.5px * var(--lw,1));}
  P #solar-svg .sol-link{stroke:rgb(200,215,255);stroke-opacity:.22;}
  P #solar-svg [fill^="url(#sol-glow"]{display:none;}
  P #solar-svg .sk-tr{fill:none;stroke:rgb(195,215,255);stroke-linecap:round;}
  R .node-card{background:transparent !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;
    border-color:transparent !important;box-shadow:none !important;overflow:visible !important;isolation:isolate;will-change:transform;}
  /* (will-change: each resting body its own layer, as the glass card's backdrop-filter made it: a moving
     body is then a layer moved, not the board repainted under it — 4x cheaper with the whole chart in view) */
  R .node-card::before,R .node-card::after{display:none !important;}
  R .node-card:hover{box-shadow:0 0 0 1.5px rgba(205,220,255,.7) !important;}
  P #world .node[data-solar=sat]:not(.focused):not(.sol-closing) .node-card{border-color:rgba(170,190,255,.25) !important;}
  R .node-card>.sk.sk,F .node-card>.sk.sk{display:block !important;position:absolute;pointer-events:none;left:50%;top:50%;}
  /* enlarged (solar_draw's bigger disc, --sD): the body keeps its look under the scrim and the content */
  F{--skd:var(--scd,var(--sD));--card-desc-color:rgba(232,238,255,.88);}   /* (the engine's desc colour is an !important var: dark in the light theme) */
  F .sol-scrim.sol-scrim{background:radial-gradient(circle,rgba(3,5,12,var(--sk-scrim,.5)) 0 56%,rgba(3,5,12,calc(var(--sk-scrim,.5)*.4)) 100%) !important;}
  F .sol-body{color:#eef2ff;}
  F .sol-body .node-title{color:#fff;}
  F .sol-body .node-order,F .sol-body .node-desc{color:rgba(232,238,255,.88);}
  F .sk-craft.sk-craft{width:calc(var(--skd)*.8);height:calc(var(--skd)*.8);margin:calc(var(--skd)*-.4) 0 0 calc(var(--skd)*-.4);opacity:.55;}
  K .sk-tex{width:calc(var(--skd,var(--sd))*1.16);height:calc(var(--skd,var(--sd))*1.16);margin:calc(var(--skd,var(--sd))*-.58) 0 0 calc(var(--skd,var(--sd))*-.58);
    background:radial-gradient(circle closest-side,var(--sk-c) 85.5%,transparent 86.5%);}
  K .sk-tex.ok{background:none;}
  /* no border-radius clip anywhere in a body: every disc edge is its own antialiased alpha (canvas, or a
     gradient ending transparent) — a clipped edge inside a faded card was drawn stair-stepped (WebKit) */
  K .sk-lit,K .sk-sun,K .sk-gran{width:var(--skd,var(--sd));height:var(--skd,var(--sd));margin:calc(var(--skd,var(--sd))/-2) 0 0 calc(var(--skd,var(--sd))/-2);}
  K .sk-lit.a{opacity:.7;}
  K .sk-sun{background:radial-gradient(circle closest-side,var(--c0) 0%,var(--c0) 28%,var(--c1) 58%,var(--c2) 84%,var(--c3) 98.6%,transparent 100%);}
  K .sk-gran{animation:sk-spin 260s linear infinite;}
  K .sk-gran.b{animation-duration:410s;animation-direction:reverse;}
  K .sk-rb,K .sk-rf{width:calc(var(--skd,var(--sd))*2.4);height:calc(var(--skd,var(--sd))*2.4);margin:calc(var(--skd,var(--sd))*-1.2) 0 0 calc(var(--skd,var(--sd))*-1.2);}
  K .sk-bh{width:var(--skd,var(--sd));height:var(--skd,var(--sd));margin:calc(var(--skd,var(--sd))/-2) 0 0 calc(var(--skd,var(--sd))/-2);
    background:radial-gradient(circle closest-side,#000 0,#000 80%,rgba(255,240,210,.95) 86%,rgba(255,170,90,.45) 92%,rgba(255,120,60,0) 100%);}
  K .sk-tail{width:calc(var(--skd,var(--sd))*4);height:calc(var(--skd,var(--sd))*1.25);margin:calc(var(--skd,var(--sd))*-.625) 0 0 0;transform-origin:0 50%;}
  K .sk-craft{width:calc(var(--skd,var(--sd))*1.3);height:calc(var(--skd,var(--sd))*1.3);margin:calc(var(--skd,var(--sd))*-.65) 0 0 calc(var(--skd,var(--sd))*-.65);}
  P #world .node[data-solar] .sol-face{color:#f3f6ff;text-shadow:0 0 3px rgba(0,0,0,.95);}
  P #world .node[data-solar] .sol-face b{opacity:.92;}
  P #world .node[data-solar=sun] .sol-face{color:var(--sk-ink,#2a1400);text-shadow:0 0 4px rgba(255,250,228,.95);}
  /* the whole chart (solar_draw's zoomed-out view): the labels are a few px tall, their shadows cost every frame */
  P #canvas.sol-ov #world .node[data-solar] .sol-face,P #canvas.sol-ovanim #world .node[data-solar] .sol-face{text-shadow:none;}
  @media (prefers-reduced-motion:reduce){ .sk-cor,.sk-cacc,.sk-prom,.sk-tw,.sk-gran{animation:none !important;} }
  html.sk-still .sk-cor,html.sk-still .sk-cacc,html.sk-still .sk-prom,html.sk-still .sk-tw,html.sk-still .sk-gran{animation-play-state:paused !important;}
  /* a faded body (another one is enlarged) holds its surface still: a turning layer inside a faded card
     was drawn with stair-stepped edges (WebKit) */
  #canvas.focus-mode #world .node:not(.focused) .sk-gran{animation:none;}
  html.alto-editing .sk-cor,html.alto-editing .sk-cacc,html.alto-editing .sk-prom,html.alto-editing .sk-tw,html.alto-editing .sk-gran{animation:none !important;}
  html.alto-stars.alto-editing:not(.mobile) #canvas{background:#0a0c1a;}
  html.alto-stars.alto-editing .sk-sky,html.alto-stars.alto-editing #solar-svg .sk-tr,html.alto-stars.alto-editing #solar-svg .sk-belt{display:none !important;}
  html.alto-stars.alto-editing:not(.mobile) #world .node[data-solar] .node-card>.sk.sk.sk{display:none !important;}
  E .node-card{background:var(--sk-c) !important;}
  @media print{
    .sk-sky,#solar-svg .sk-tr,#solar-svg .sk-rg,#solar-svg .sk-belt{display:none !important;}
    html.alto-stars #canvas{background:none !important;}
    E .node-card>.sk.sk,R .node-card>.sk.sk{display:none !important;}
    R .node-card{background:#fff !important;border:1.5px solid #777 !important;}
    html.alto-stars #world .node[data-solar] .sol-face{color:#111 !important;text-shadow:none !important;}
  }
""".replace("E .", _E + " .").replace("R .", _R + " .").replace("K .", _K + " .").replace("F .", _F + " .").replace("F{", _F + "{").replace("P #", _P + " #")

STARS_JS = r"""
(function(){
var de=document.documentElement, NS='http://www.w3.org/2000/svg', DEG=180/Math.PI;
var PADW=0, S=null, world=null, BB={}, IDS=[], SUNC={}, TILES=null, ready=false, extT=-1e9, fbLast=0, fbR=0, fbS=0, idle=0, Q=[], qT=0, SPIN=-1;
var ST={t:[]};
function desk(){ return !de.classList.contains('mobile'); }
/* the skin is the Star chart look's (solar_draw's look switch: window._altoSolarLook, or the
   html.alto-solar-stars / -hub classes; with neither, the plan's own style) */
function look(){ var L=window._altoSolarLook; if(L && L.get) return L.get()==='stars';
  if(de.classList.contains('alto-solar-hub')) return false; if(de.classList.contains('alto-solar-stars')) return true;
  var s=window._ALTO_SOLAR; return !!(s && s.look!=='hub' && s.look!=='plain'); }
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
var SCRIM={sun:.62, desert:.5, ice:.52, gas:.5, comet:.46, moon:.44, asteroid:.42, rocky:.42, ocean:.38, lava:.38, blackhole:.25, sat:.5};
var STARS=[['#fffbea','#ffe680','#ffb432','#e8740e','255,190,90','#2a1400'], ['#fff2d8','#ffc870','#ff8f2a','#d3520c','255,150,70','#2a1000'],
  ['#ffffff','#fff4c8','#ffd780','#f0a43c','255,225,160','#2a1800'], ['#ffffff','#e6f0ff','#b4ccff','#7d9cff','160,190,255','#0b1a40']];
/* a plan's look (LEAD: nodes[id].look) overrules the role's: a black hole, a comet, an asteroid */
function kindOf(id, role, look){ if(/^(blackhole|comet|asteroid)$/.test(look||'')) return look; if(role!=='planet') return role; var r=rng(hash(id+'#k'))(), a=0;
  for(var i=0;i<KW.length;i++){ a+=KW[i]; if(r<a) return KINDS[i]; } return 'rocky'; }
/* a body's surface: (longitude, latitude) on the sphere -> colour */
function painter(kind, id, o){
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
      if(o && o.nc) return c; var k=fb(n2, lo*2.6+sx, la*4.4+sy, 4); return mix(c, [250,252,255], (k-.5)*3); };   /* (nc: no clouds, solar_3d.py draws its own) */
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
function texJob(k, N, cv){
  N=N||Math.min(256, Math.round(k.d*2.32)); var rd=N/2/1.16, h=N/2, P=painter(k.kind, k.id), A=ATM[k.kind]||ATM.moon,
    cr=k.kind==='moon' ? craters(k.id, 9+(hash(k.id)%7)) : /rocky|asteroid/.test(k.kind) ? craters(k.id, 5) : null,
    ne=k.kind==='asteroid' ? noise(hash(k.id+'e')) : null;
  return job(cv||k.tex, N, function(D, y){
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
/* the light: lit from +x (turned toward the sun each frame), the night side, a soft terminator
   (sharper on a moon), the lit limb's atmosphere, a soft highlight */
function litJob(k, cv, N){
  N=N||Math.min(256, Math.round(k.d*2)); var rd=N/2, m=/moon|comet|asteroid/.test(k.kind), A=ATM[k.kind]||ATM.moon, nt=m ? .93 : .9;
  return job(cv, N, function(D, y){
    var ny=(y+.5-rd)/rd;
    for(var x=0;x<N;x++){ var nx=(x+.5-rd)/rd, r=Math.hypot(nx, ny), e=cl((1-r)*rd+.5); if(e<=0) continue;
      var t=m ? cl((nx+.12)/.26) : cl((nx+.36)/.6), an=nt*(1-t*t*(3-2*t))*e,
        aa=A[3]*.6*Math.max(0, 1-Math.abs(r-.95)/.13)*e, ah=(m ? .16 : .2)*Math.max(0, 1-Math.hypot(nx-.48, ny)/.84)*e,
        cA=aa+ah*(1-aa), a=an+cA*(1-an), w=a>0 ? cA*(1-an)/a : 0, c=cA>0 ? mix(A, [255,252,240], ah/cA) : A;
      put(D, (y*N+x)*4, [c[0]*w, c[1]*w, c[2]*w], a); }
  });
}
function ringJob(k, cv, front, N){
  var R=rng(hash(k.id+'r')), bh=k.kind==='blackhole', ps=(R()-.5)*(bh ? .5 : .9), kk=bh ? .3 : .22+R()*.2, ri=bh ? 1.12 : 1.3+R()*.15, ro=bh ? 2.35 : ri+.45+R()*.45, cs=Math.cos(ps), sn=Math.sin(ps),
    C=R()<.5 ? [218,202,172] : [188,204,226], n=noise(hash(k.id+'g'));
  N=N||Math.min(320, Math.round(k.d*3.6));
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
function granJob(k, cv, b, N){
  N=N||Math.min(256, Math.round(k.d*1.6)); var n=noise(hash(k.id+(b ? 'h' : 'g'))), R=rng(hash(k.id+'s')), sp=b ? [] : [[(R()-.5)*.9, (R()-.5)*.9, .045]];
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
    for(var x=0;x<N;x++){ var nx=(x+.5)/N*2-1, ny=(y+.5)/N*2-1, r=Math.hypot(nx, ny)*3.6; if(r>3.6) continue;
      /* under the disc it is light, not a hole (seen through a faded star), easing into the corona */
      var th=Math.atan2(ny, nx), s=fb(n, Math.cos(th)*3+4, Math.sin(th)*3+4, 3), b=Math.exp(-Math.max(0, r-1)*1.7)*(.3+1.6*s*s*s)*cl((3.6-r)*2)*.95,
        w=cl((1.04-r)/.16); w=w*w*(3-2*w);
      put(D, (y*N+x)*4, mix([255,255,245], C, Math.max(0, r-1)*.8), w+cl(b)*(1-w)); }
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
/* small craft (round 7): a kind per satellite, fixed by its id — a communications satellite with
   its dish, a probe on a long antenna boom, a space telescope (a tube between two panels), a CubeSat
   — and the system's space station (plan nodes[id].station: a truss, four solar wings, a hab ring).
   Each drawn once on a canvas (an 88-unit square, nose up), never per frame. */
var CRAFT=['comsat', 'probe', 'telescope', 'cubesat'];
function craftKind(id){ var n=(S && S.nodes && S.nodes[id])||{}; return n.station ? 'station' : CRAFT[(hash(id+'c')>>>0)%CRAFT.length]; }
function craftDraw(k, cv, M){
  M=M||88; var R=rng(hash(k.id+'v')), N=88, x=cv.getContext('2d'), kind=craftKind(k.id), pc=R()<.6 ? ['#1d3f8f','#5d87d8'] : ['#2a2f45','#7f8bb5'], bc=R()<.6 ? ['#f1c34a','#8a5a10'] : ['#e8ecf2','#7d8492'];
  k.craftKind=kind; cv.setAttribute('data-craft', kind); cv.width=cv.height=M; x.scale(M/N, M/N); x.lineWidth=1;
  function panel(x0, y0, w, h){ var gr=x.createLinearGradient(0, y0, 0, y0+h); gr.addColorStop(0, pc[1]); gr.addColorStop(1, pc[0]);
    x.fillStyle=gr; x.fillRect(x0, y0, w, h); x.strokeStyle='rgba(190,215,255,.55)'; x.lineWidth=1;
    for(var q=x0+6;q<x0+w;q+=6){ x.beginPath(); x.moveTo(q+.5, y0); x.lineTo(q+.5, y0+h); x.stroke(); }
    x.strokeRect(x0+.5, y0+.5, w-1, h-1); }
  function bus(x0, y0, w, h){ var gb=x.createLinearGradient(x0, y0, x0+w, y0+h); gb.addColorStop(0, bc[0]); gb.addColorStop(1, bc[1]); x.fillStyle=gb; x.fillRect(x0, y0, w, h); }
  function line(x1, y1, x2, y2, w, c){ x.strokeStyle=c||'#c9ced8'; x.lineWidth=w||2; x.beginPath(); x.moveTo(x1, y1); x.lineTo(x2, y2); x.stroke(); }
  if(kind==='comsat'){                                   /* panels either side, a dish on top */
    panel(6, 38, 26, 14); panel(56, 38, 26, 14); line(32, 45, 56, 45); bus(37, 36, 14, 18);
    x.fillStyle='#eef1f6'; x.beginPath(); x.ellipse(44, 26, 11, 5, 0, Math.PI, 0); x.fill(); line(44, 31, 44, 36, 1.5); line(44, 26, 44, 17, 1, '#e6e9ef');
  } else if(kind==='probe'){                             /* Voyager-like: a big dish, a long boom, an antenna */
    x.fillStyle='#eef1f6'; x.beginPath(); x.arc(44, 40, 14, 0, 7); x.fill(); x.fillStyle='#b9c0cc'; x.beginPath(); x.arc(44, 40, 6, 0, 7); x.fill();
    bus(39, 52, 10, 9); line(49, 57, 84, 70, 1.5); line(39, 57, 8, 76, 1.5); line(44, 26, 44, 4, 1, '#e6e9ef');
    x.fillStyle='#d8dde6'; x.fillRect(80, 67, 6, 6);
  } else if(kind==='telescope'){                         /* Hubble-like: a long tube, two panels, an open aperture */
    var gt=x.createLinearGradient(36, 0, 52, 0); gt.addColorStop(0, '#9aa1ad'); gt.addColorStop(.5, '#eef1f6'); gt.addColorStop(1, '#8a919d');
    x.fillStyle=gt; x.fillRect(36, 14, 16, 60); x.fillStyle='#2b2f38'; x.fillRect(38, 12, 12, 4);
    panel(8, 34, 22, 26); panel(58, 34, 22, 26); line(30, 47, 36, 47); line(52, 47, 58, 47);
  } else if(kind==='cubesat'){                           /* a small cube, its panels unfolded */
    panel(10, 36, 22, 16); panel(56, 36, 22, 16); bus(33, 33, 22, 22);
    x.strokeStyle='rgba(40,40,50,.55)'; x.lineWidth=1; x.strokeRect(33.5, 33.5, 21, 21); line(44, 33, 44, 20, 1, '#e6e9ef');
  } else {                                               /* the space station: a truss, four wings, a hab ring */
    line(4, 44, 84, 44, 3, '#c9ced8'); panel(4, 22, 14, 18); panel(4, 48, 14, 18); panel(70, 22, 14, 18); panel(70, 48, 14, 18);
    x.strokeStyle='#dfe4ec'; x.lineWidth=3.2; x.beginPath(); x.arc(44, 44, 15, 0, 7); x.stroke();
    x.strokeStyle='rgba(120,130,150,.8)'; x.lineWidth=1; x.beginPath(); x.arc(44, 44, 15, 0, 7); x.stroke();
    line(44, 29, 44, 59, 2, '#c9ced8'); bus(38, 38, 12, 12); x.fillStyle='#eef1f6'; x.fillRect(41, 22, 6, 9); x.fillRect(41, 57, 6, 9);
  }
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
  var sl=document.getElementById('canvas'), T=tiles(); if(!sl) return;
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
    k.sky=[nb, gl, C.cor, C.prom]; k.x0=k.x; k.y0=k.y; k.tl='';   /* (moved with the sun as the galaxy turns: update) */
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
    g.innerHTML=out; tg.parentNode.insertBefore(g, tg); if(b.sun && BB[b.sun]){ BB[b.sun].belt=g; BB[b.sun].tl=''; } });
}
/* ── an enlarged body (solar_draw's bigger disc, --sD) keeps its look: its canvases painted again,
   once, at the disc's size (between frames, then swapped in), so a 300-420 px disc is not soft ── */
function hiRes(k){
  var D=parseFloat(k.n.style.getPropertyValue('--sD'))||0; if(!D || D<=k.hiD) return; k.hiD=D;
  var redo=function(cv, N, mk){ if(!cv || N<=cv.width) return; var off=document.createElement('canvas'), j=mk(off, N), e=j.end;
    j.end=function(){ e(); cv.width=off.width; cv.height=off.height; cv.getContext('2d').drawImage(off, 0, 0); }; Q.unshift(j); };
  redo(k.tex, Math.min(768, Math.round(D*2.32)), function(c, N){ return texJob(k, N, c); });
  redo(k.lit, Math.min(768, Math.round(D*2)), function(c, N){ return litJob(k, c, N); });
  [k.rb, k.rf].forEach(function(cv, i){ redo(cv, Math.min(900, Math.round(D*3.6)), function(c, N){ return ringJob(k, c, !!i, N); }); });
  (k.gr||[]).forEach(function(cv, i){ redo(cv, Math.min(768, Math.round(D*2)), function(c, N){ return granJob(k, c, i, N); }); });
  if(k.craft) craftDraw(k, k.craft, Math.min(512, Math.round(D*1.6)));
  clearTimeout(qT); pump();
}
function grown(ms){ ms.forEach(function(m){ var n=m.target, k=n.id && BB[n.id.slice(5)]; if(k && ready && n.classList.contains('focused')) requestAnimationFrame(function(){ hiRes(k); }); }); }
/* ── dressing the bodies, after every layout ── */
function dress(k, n, kind, d){
  var c=n.querySelector('.node-card'); if(!c) return;
  (k.els||[]).forEach(function(e){ e.remove(); });
  var f=c.querySelector('.sol-face'), els=[], add=function(t, cls){ var e=el(t, 'sk '+cls); c.insertBefore(e, f); els.push(e); return e; }, R=rng(hash(k.id+'x'));
  k.n=n; k.kind=kind; k.d=d; k.els=els; k.hiD=0; k.lit=k.tex=k.craft=k.tail=k.rb=k.rf=k.gr=null;
  n.style.setProperty('--sk-scrim', SCRIM[kind]||.5); k.la=k.ca=k.ta=null;
  if(kind==='sun'){
    k.star=STARS[k.si===0 ? 0 : ((R()*10)|0)<6 ? 0 : 1+((R()*3)|0)];
    ['--c0','--c1','--c2','--c3'].forEach(function(v, i){ n.style.setProperty(v, k.star[i]); });
    n.style.setProperty('--g', k.star[4]); n.style.setProperty('--sk-ink', k.star[5]); n.style.setProperty('--sk-c', k.star[1]);
    add('div', 'sk-sun'); k.gr=[add('canvas', 'sk-gran'), add('canvas', 'sk-gran b')]; Q.push(granJob(k, k.gr[0], 0)); Q.push(granJob(k, k.gr[1], 1));
    return;
  }
  n.style.setProperty('--sk-c', FLAT[kind]); n.style.setProperty('--sk-a', (ATM[kind]||ATM.moon).slice(0, 3).join(','));
  if(kind==='sat'){ k.craft=add('canvas', 'sk-craft'); craftDraw(k, k.craft); return; }
  if(kind==='blackhole'){ k.rb=add('canvas', 'sk-rb'); Q.push(ringJob(k, k.rb, false)); add('div', 'sk-bh'); k.rf=add('canvas', 'sk-rf'); Q.push(ringJob(k, k.rf, true)); return; }
  if(kind==='comet'){ k.tail=add('canvas', 'sk-tail'); tailDraw(k, k.tail); }
  var ring=!/moon|comet|asteroid/.test(kind) && rng(hash(k.id+'#r'))()<({gas:.55, ice:.45}[kind]||.08);
  if(ring){ k.rb=add('canvas', 'sk-rb'); Q.push(ringJob(k, k.rb, false)); }
  k.tex=add('canvas', 'sk-tex'); Q.push(texJob(k));
  k.lit=add('canvas', 'sk-lit'+(kind==='asteroid' ? ' a' : '')); Q.unshift(litJob(k, k.lit));
  if(ring){ k.rf=add('canvas', 'sk-rf'); Q.push(ringJob(k, k.rf, true)); }
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
  if(!skin.mo && typeof MutationObserver==='function'){ skin.mo=new MutationObserver(grown); skin.mo.observe(world, {attributes:true, subtree:true, attributeFilter:['class']}); }
  IDS.forEach(function(id){ var k=BB[id]; if(k.n && k.n.classList.contains('focused')) hiRes(k); });
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
/* the clock: the orbits' own (window._altoSolarT: stops with them), else ours — still under
   prefers-reduced-motion or with the motion switched off */
var ownT=0, ownL=null, RM=false; try{ RM=matchMedia('(prefers-reduced-motion: reduce)').matches; }catch(e){}
function clock(){ if(typeof window._altoSolarT==='number') return window._altoSolarT;
  var now=performance.now()/1000, M=window._altoSolarMotion;
  if(ownL!=null && !RM && !(M && M.get && !M.get())) ownT+=Math.min(.1, now-ownL); ownL=now; return ownT; }
function update(bodies){
  if(!ready || !desk() || de.classList.contains('alto-editing')) return false;
  var t0=performance.now(), ch=false;
  IDS.forEach(function(id){ var k=BB[id], p=pos(id, bodies); if(k && p){ ch=ch || k.x!==p[0] || k.y!==p[1]; k.x=p[0]; k.y=p[1]; } });
  /* a sun's glow, corona and belt go with it (the Star chart's galaxy turns about its core) */
  IDS.forEach(function(id){ var k=BB[id]; if(!k || !k.sky || k.role!=='sun') return; var dx=k.x-k.x0, dy=k.y-k.y0, tl=dx.toFixed(1)+'px '+dy.toFixed(1)+'px';
    if(tl===k.tl) return; k.tl=tl; k.sky.forEach(function(e){ if(e) e.style.translate=tl; }); if(k.belt) k.belt.setAttribute('transform', 'translate('+dx.toFixed(1)+' '+dy.toFixed(1)+')'); });
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
  var T=clock();
  IDS.forEach(function(id){ var k=BB[id], tb=k && k.tex && S.nodes[id] && S.nodes[id].tumble;
    if(tb){ var a=tb*T*DEG%360; if(turn(a, k.ta, 1)){ k.ta=a; k.tex.style.transform='rotate('+a.toFixed(1)+'deg)'; } } });
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
/* the System look (or a phone): the skin goes, its canvases kept for the way back */
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
/* ── Realistic 3D (Luke, 2026-10-21: "more realistic than what we currently have and feels 3d"), the Star chart's third
   style, html.sk-real (solar_draw.py's switch). What makes a body read as a turning globe, not a picture of one:
   (1) its surface turns on its axis: the painter's colours laid out once as a seamless longitude x latitude strip,
   each disc pixel's (longitude, latitude) and shading kept in a table, and the strip slid under it, so a turn is a
   table walk, not a repaint (redrawn a few times a second, on-screen bodies only, within ~3ms a frame);
   (2) an ocean world's clouds turn on their own, faster; (3) the lit side keeps facing its sun (the Classic .sk-lit,
   above it); (4) a nearer star field drifts slower than the board as it pans, so space has depth. ── */
var RL={raf:0, i:0, par:null};
function realOn(){ return ready && desk() && de.classList.contains('sk-real') && !de.classList.contains('sk-3d') && !de.classList.contains('alto-editing'); }   /* (with WebGL, solar_3d.py draws the style) */
function realBody(k){ return k.n && k.tex && /^(rocky|desert|ocean|gas|ice|lava|moon)$/.test(k.kind); }
/* the strip, built a few rows a frame: W = 3N longitudes, H = 1.5N latitudes; its two ends cross-faded so it wraps */
function realStrip(k){
  var N=k.rN, W=3*N, H=Math.round(1.5*N), P=painter(k.kind, k.id), cn=k.kind==='ocean' ? noise(hash(k.id+'cl')) : null, TAU=Math.PI*2;
  k.rW=W; k.rH=H; k.rS=new Uint8ClampedArray(W*H*3); if(cn) k.rC=new Uint8Array(W*H); k.rY=0;
  k.rRow=function(y){ var la=((y+.5)/H-.5)*Math.PI;
    for(var x=0;x<W;x++){ var lo=(x+.5)/W*TAU-Math.PI, f=(x+.5)/W, c0=P(lo, la), c1=P(lo-TAU, la), o=(y*W+x)*3;
      k.rS[o]=c0[0]*(1-f)+c1[0]*f; k.rS[o+1]=c0[1]*(1-f)+c1[1]*f; k.rS[o+2]=c0[2]*(1-f)+c1[2]*f;
      if(cn){ var v=fb(cn, lo*1.6+7, la*3.2+3, 4)*(1-f)+fb(cn, (lo-TAU)*1.6+7, la*3.2+3, 4)*f; k.rC[y*W+x]=Math.round(cl((v-.52)*4.2)*215); } } };
}
/* the table: for each pixel of the disc, where on the strip it looks (its longitude across the visible half), its
   shade (the limb darker) and its edge's alpha */
function realTable(k){
  var N=k.rN, r=N/2, W=k.rW, H=k.rH, ix=[], lo=[], rw=[], sh=[], ea=[];
  for(var y=0;y<N;y++) for(var x=0;x<N;x++){ var nx=(x+.5-r)/r, ny=(y+.5-r)/r, q=nx*nx+ny*ny, e=cl((1-Math.sqrt(q))*r+.5); if(e<=0) continue;
    var z=Math.sqrt(Math.max(0, 1-q)); ix.push((y*N+x)*4); lo.push((Math.atan2(nx, z)/(Math.PI*2)+.5)*W); rw.push(Math.min(H-1, Math.max(0, Math.round((Math.asin(cl(ny*.5+.5)*2-1)/Math.PI+.5)*H-.5))));
    sh.push(.62+.38*Math.pow(z, .7)); ea.push(Math.round(e*255)); }
  k.rT={ix:Int32Array.from(ix), lo:Float32Array.from(lo), rw:Int32Array.from(rw), sh:Float32Array.from(sh), ea:Uint8Array.from(ea)};
  var R=rng(hash(k.id+'spin')); k.rP=(k.kind==='gas' ? 26 : k.kind==='moon' ? 140 : 46)*(.75+R()*.6)*1000; k.rP2=k.rP*.62; k.rPh=R(); k.rLast=-1;
}
function realDraw(k, now){
  var T=k.rT, W=k.rW, S=k.rS, C=k.rC, cv=k.rot, N=k.rN; if(!k.rCtx){ cv.width=cv.height=N; k.rCtx=cv.getContext('2d'); k.rImg=k.rCtx.createImageData(N, N); }
  var ph=((now/k.rP+k.rPh)%1)*W, ph2=((now/k.rP2+k.rPh)%1)*W, D=k.rImg.data, n=T.ix.length;
  for(var i=0;i<n;i++){ var o=T.ix[i], row=T.rw[i]*W, sx=(T.lo[i]+ph)|0, s; sx%=W; s=(row+sx)*3; var l=T.sh[i], r=S[s]*l, g=S[s+1]*l, b=S[s+2]*l;
    if(C){ var c2=((T.lo[i]+ph2)|0)%W, a=C[row+c2]/255*(.55+.45*l); r+=(250-r)*a; g+=(252-g)*a; b+=(255-b)*a; }
    D[o]=r; D[o+1]=g; D[o+2]=b; D[o+3]=T.ea[i]; }
  k.rCtx.putImageData(k.rImg, 0, 0); k.rLast=now;
}
function realTick(){
  RL.raf=0; if(!realOn()){ realPar(false); return; }
  var t0=performance.now(), dl=t0+3, ids=Object.keys(BB), n=ids.length, vw=innerWidth, vh=innerHeight;
  realPar(true);
  for(var j=0;j<n && performance.now()<dl;j++){ var k=BB[ids[(RL.i+j)%n]]; if(!realBody(k)) continue;
    if(!k.rot || !k.rot.isConnected){ k.rot=document.createElement('canvas'); k.rot.className='sk-rot'; k.rot.setAttribute('aria-hidden', 'true');
      var c=k.n.querySelector('.node-card'); if(!c) continue; c.insertBefore(k.rot, k.lit && k.lit.parentNode===c ? k.lit : c.querySelector('.sol-face')); k.rCtx=null; }
    var q=k.n.getBoundingClientRect(); if(q.right<0 || q.bottom<0 || q.left>vw || q.top>vh || q.width<12) continue;
    var want=Math.max(24, Math.min(160, Math.round(q.width*(window.devicePixelRatio||1))));
    if(!k.rS || Math.abs(want-k.rN)>k.rN*.5){ k.rN=want; realStrip(k); k.rT=null; }
    if(k.rY<k.rH){ while(k.rY<k.rH && performance.now()<dl) k.rRow(k.rY++); if(k.rY<k.rH) break; }
    if(!k.rT) realTable(k);
    if(t0-k.rLast>=110) realDraw(k, t0); }
  RL.i=(RL.i+1)%Math.max(1, n);
  RL.raf=requestAnimationFrame(realTick);
}
/* the nearer stars: a layer in the board, counter-moved by 0.6 of each scroll so it drifts at 0.4 of the board's pace */
function realPar(on){
  var c=document.getElementById('canvas'), w=world;
  if(!on || !c || !w || c.classList.contains('sol-ov')){ if(RL.par) RL.par.style.display='none'; return; }
  if(!RL.par || !RL.par.isConnected){ RL.par=document.createElement('div'); RL.par.className='sk-par'; RL.par.setAttribute('aria-hidden', 'true'); w.appendChild(RL.par); }
  var T=tiles(); if(T.u && !RL.par._bg){ RL.par._bg=1; RL.par.style.backgroundImage='url('+T.u[1]+'),url('+T.u[0]+')'; }
  var x=c.scrollLeft, y=c.scrollTop, s=RL.par.style;
  s.display='block'; s.width=(c.clientWidth+400)+'px'; s.height=(c.clientHeight+400)+'px';
  s.transform='translate('+Math.round(x-200-((x*.4)%300))+'px,'+Math.round(y-200-((y*.4)%300))+'px)';
}
function realKick(){ if(!RL.raf && realOn()) RL.raf=requestAnimationFrame(realTick); }
if(typeof MutationObserver==='function') new MutationObserver(realKick).observe(de, {attributes:true, attributeFilter:['class']});
setInterval(realKick, 1000);
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
window._altoSkPaint=function(kind, id, o){ return painter(kind, id, o); };   /* (solar_3d.py paints its globes with the same surfaces) */
window._altoSkinStats={
  get:function(){ var d=ST.t.slice().sort(function(a, b){ return a-b; }), q=function(p){ return d.length ? +d[Math.min(d.length-1, Math.floor(d.length*p))].toFixed(3) : 0; };
    return {n:d.length, p50:q(.5), p95:q(.95), max:q(1), pending:Q.length, ext:extT>0}; },
  reset:function(){ ST.t=[]; },
  hashes:function(){ var o={}; [].forEach.call(document.querySelectorAll('#world canvas.sk,#world .sk-sky canvas'), function(c, i){ var n=c.closest('.node'), id=(n ? n.id : 'sky'+i)+':'+c.className;
    o[id]=c._h || sum(c.getContext('2d').getImageData(0, 0, c.width, c.height).data); }); return o; }
};
})();
"""

# ── Retro (round 10, Luke's NASA-poster reference): a style of the Star chart look. Flat black space, each system's
# reach in stepped blue bands round its sun, gold spokes, flat bodies, satellites drawn as a line probe, poster
# lettering. html.sk-retro is set by solar_draw.py's style switch (kept per timeline like the look).
_X = "html.alto-stars.sk-retro:not(.mobile)"
# ── Realistic 3D: the Star chart's third style (html.sk-real; the turning surfaces are drawn by STARS_JS realTick) ──
REAL_CSS = r"""
  .sk-rot,.sk-par{display:none;}
  html.sk-real.alto-stars:not(.mobile) #world .node[data-solar] .node-card>.sk-rot{display:block;position:absolute;left:50%;top:50%;pointer-events:none;
    width:var(--skd,var(--sd));height:var(--skd,var(--sd));margin:calc(var(--skd,var(--sd))/-2) 0 0 calc(var(--skd,var(--sd))/-2);}
  html.sk-real.alto-stars:not(.mobile) #world>.sk-par{display:block;position:absolute;left:0;top:0;z-index:4;pointer-events:none;opacity:.55;
    background-size:300px 300px,700px 700px;background-position:0 0,140px 90px;}
  /* each body a little lifted off the space behind it; the sun lighting the space round it: a wide warm bloom
     (a shadow's spread, no filter) */
  html.sk-real.alto-stars:not(.mobile) #world .node[data-solar]:not(.focused) .node-card:not(#_){box-shadow:0 10px 30px rgba(0,0,0,.45) !important;}
  html.sk-real.alto-stars:not(.mobile) #world .node[data-solar=sun]:not(.focused) .node-card:not(#_){
    box-shadow:0 0 60px 18px rgba(255,214,150,.30),0 0 180px 60px rgba(255,170,90,.14),0 0 420px 140px rgba(255,140,70,.06) !important;}
  @media print{ .sk-rot,.sk-par{display:none !important;} }
"""
STARS_CSS += REAL_CSS

RETRO_CSS = (r"""
  html.alto-clear-top.alto-stars:not(.mobile) #title-text{color:#eef2ff !important;}   /* (the bars are clear, clear_top.py: the sky is under the name) */
  #solar-svg .sol-bun,#solar-svg .sol-sig,#sk-mark,#sk-frame{display:none;}
  /* Foundation's Empire (Luke): black and gold, the imperial sun's sigil, a monumental frame, thin wide letters */
  X #solar-svg .sol-sig{display:inline;fill:none;stroke:#d9ae55;stroke-width:1.1;stroke-opacity:.85;}
  X #solar-svg .sol-sig .k{stroke-width:2;stroke-opacity:1;} X #solar-svg .sol-sig .w{stroke-opacity:.35;stroke-dasharray:1 9;stroke-width:3;}
  X #canvas.sol-ov #solar-svg .sol-sig line:not(.k){display:none;}
""" + FRAME_CSS + BRAND_CSS + r"""  X .sol-unit::before,X .sol-unit::after{content:'\25C6';margin:0 .7em;font-size:.7em;vertical-align:.15em;color:#d9ae55;}
  X #canvas{background:#000 !important;}
  X .sk-sky,X #solar-svg .sk-rg,X #solar-svg .sk-tr,X #solar-svg .sol-oort,X #solar-svg .sol-ubd,X #solar-svg [fill^="url(#sol-glow"]{display:none !important;}
  /* the orbits are the bands (solar_draw.py oBands): stepped, edge to edge, light near the sun and dark at the reach;
     a moon's a lighter blue over its planet's; no thin rings. A band takes an orbit's hover and click. */
  X #solar-svg .sol-hit.sol-oband{display:inline;fill:none;stroke:var(--bc);stroke-width:var(--bw);stroke-opacity:1;transition:stroke .2s,stroke-opacity .2s;}
  X #solar-svg .sol-hit.sol-oband.sol-m{stroke-opacity:.82;}
  X #solar-svg .sol-hit.sol-oband.sol-hot{stroke:color-mix(in srgb,var(--bc) 55%,#d9ae55);stroke-opacity:1;}
  X #canvas.sol-lhov #solar-svg .sol-hit.sol-oband:not(.sol-hot){stroke-opacity:.5;}
  X #solar-svg .sol-ring,X #solar-svg .sol-hit.sol-rgh{display:none;}
  /* the spokes: the poster's gold signal beam, five fine parallel lines */
  X #solar-svg .sol-spoke,X #solar-svg .sol-bun{display:inline;stroke:#f0c15e;stroke-opacity:1;stroke-width:calc(1.15px * var(--lw,1));stroke-linecap:butt;}
  X #canvas.sol-ov #solar-svg .sol-bun{display:none;}
  X #canvas.sol-ov #solar-svg .sol-spoke{stroke-width:calc(1.6px * var(--lw,1));}
  X #solar-svg .sol-spoke.sol-hot.sol-hot{stroke:#ffd27a !important;stroke-width:1.6px !important;}
  X #solar-svg .sol-link{stroke:#d9ae55;stroke-opacity:.6;stroke-dasharray:6 6;}
  X #river-svg path{stroke:#d9ae55 !important;stroke-opacity:.55;stroke-width:1.2px !important;stroke-dasharray:6 6;filter:none !important;}
  X #solar-svg .sk-belt{stroke:#d9ae55;stroke-opacity:.45;stroke-dasharray:1 7;stroke-linecap:round;}
  /* the bodies: flat cut-paper discs with a hard terminator, no texture, no glow */
  X #world .node[data-solar] .node-card>.sk.sk.sk{display:none !important;}
  X #world .node[data-solar] .node-card:not(#_){box-shadow:none !important;border-color:transparent !important;
    background:linear-gradient(118deg,var(--sk-c,#9fb0c8) 0 54%,color-mix(in srgb,var(--sk-c,#9fb0c8) 55%,#020611) 54% 100%) !important;filter:saturate(.8);}
  X #world .node[data-solar=sun] .node-card:not(#_){background:#f5e6bd !important;filter:none;
    box-shadow:0 0 0 7px #000,0 0 0 9px #f5e6bd,0 0 0 16px #000,0 0 0 17px rgba(245,230,189,.6) !important;}
  X #world .node[data-solar=blackhole] .node-card:not(#_){background:#000 !important;box-shadow:0 0 0 2px #d9ae55,0 0 0 6px #000,0 0 0 7px rgba(217,174,85,.5) !important;}
  X #world .node[data-solar=sat] .node-card:not(#_){background:url("PROBE") 50% 50%/118% 118% no-repeat !important;filter:none;}
  X #world .node[data-solar] .sol-face,X #world .node[data-solar] .sol-face *{color:#fff !important;text-shadow:none !important;}
  X #world .node[data-solar=sun] .sol-face.sol-face,X #world .node[data-solar=sun] .sol-face.sol-face *{color:#0a1b34 !important;}
  X #world .node[data-solar] .node-card:not(#_):hover{outline:1.5px solid #d9ae55;outline-offset:3px;}
  X #world .node[data-solar].sol-hint:not(.focused) .node-card:not(#_){outline:1.5px solid #d9ae55;outline-offset:4px;}
  X #world .sol-nh.sol-nh{background:#000;color:#d9ae55;border-radius:0;box-shadow:0 0 0 1px #d9ae55,0 0 0 4px #000;}
  X .sol-nh>kbd{border-radius:0;color:#d9ae55;box-shadow:inset 0 0 0 1px rgba(217,174,85,.55);} X .sol-nh[data-k=n]>kbd{background:#d9ae55;color:#000;}
  X .sol-nh[data-k=s]>kbd{box-shadow:inset 0 0 0 2px #d9ae55;} X .sol-nh>b{font-weight:500;letter-spacing:.12em;} X #sol-way path{stroke:#d9ae55;stroke-opacity:.9;}
  /* poster lettering */
  X #world .node[data-solar]>.sol-lbl,X #world .node[data-solar] .sol-face,X .sol-unit,X .sol-nh,X #sk-mark,X .line-tip{
    font-family:"Avenir Next","Futura","Century Gothic","Helvetica Neue",system-ui,sans-serif !important;letter-spacing:.06em;text-transform:uppercase;}
  X #world .node[data-solar]>.sol-lbl{color:#efe6cf;text-shadow:none;font-weight:500;font-size:.84em;letter-spacing:.16em;}
  X .sol-unit{font-weight:300 !important;background:#000 !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;box-shadow:none !important;
    border:0 !important;border-radius:0 !important;color:#d9ae55 !important;letter-spacing:.32em !important;}
  X .sol-unit b,X .sol-unit span{color:#d9ae55 !important;}
""" + WORDMARK_CSS + r"""  /* the page round the chart goes black too (the bars stay clear, as on every main page: clear_top.py), the switches rimmed in gold; the name, the chips
     and the rest of the chrome are every Retro's own (retro.CHROME_CSS, below) */
  X #page-bg:not(#_){background:#000 !important;} X #page-bg::before,X #page-bg::after{display:none !important;}
  X #sol-ctl .sol-seg,X #sol-ctl #sol-motion,X #sol-ctl .sol-opt{background:#000 !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;box-shadow:0 0 0 1px rgba(217,174,85,.55) !important;border-radius:0 !important;}
  X #sol-ctl button{color:#c9d1dc !important;font-family:"Avenir Next","Futura",system-ui,sans-serif !important;text-transform:uppercase;letter-spacing:.12em;font-size:11px !important;border-radius:0 !important;}
  X #sol-ctl .sol-seg button.on,X #sol-ctl #sol-motion.on,X #sol-ctl .sol-opt.on{color:#000 !important;background:#d9ae55 !important;}
  X #sol-ctl>*{border-radius:0 !important;} X #sol-ctl .sol-sw{border-radius:0;background:#333;} X #sol-ctl .sol-sw::after{border-radius:0;background:#d9ae55;} X #sol-ctl .on .sol-sw{background:#000;}
  /* the enlarged disc: a navy plate rimmed in gold */
  X #world .node[data-solar]:is(.focused,.sol-closing) .sol-scrim{background:#0a1b34 !important;}
  X #world .node[data-solar]:is(.focused,.sol-closing) .node-card:not(#_){background:#0a1b34 !important;filter:none;box-shadow:0 0 0 2px #d9ae55,0 0 0 8px #000,0 0 0 9px rgba(217,174,85,.55) !important;}
  X #world .node[data-solar]:is(.focused,.sol-closing) .sol-body *{color:#eef2f8 !important;text-shadow:none !important;}
  X #world .node[data-solar]:is(.focused,.sol-closing) .node-tag{color:#d9ae55 !important;letter-spacing:.2em;}
  X #world .node[data-solar]:is(.focused,.sol-closing) .node-title{font-family:"Avenir Next","Futura","Century Gothic",system-ui,sans-serif !important;text-transform:uppercase;letter-spacing:.06em;}
  X #world .node-card>.node-footer>:is(button,.sol-more){background:#000 !important;border:1px solid rgba(217,174,85,.75) !important;color:#d9ae55 !important;box-shadow:none !important;}
  X .line-tip{background:#000 !important;color:#d9ae55 !important;border:1px solid #d9ae55 !important;border-radius:0 !important;}
""").replace("X ", _X + " ").replace("PROBE", "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 40'%3E%3Cg fill='none' stroke='%23b9bec6' stroke-width='1.6'%3E%3Cpath d='M23 8v6h3M24 20l-7 14M24 20l4 9M24 20l7 7'/%3E%3Crect x='21' y='15' width='6' height='7' fill='%237d838c'/%3E%3C/g%3E%3Cpath d='M19 12a7 8 0 0 0 0 14z' fill='%23f2f2ee'/%3E%3Ccircle cx='24' cy='18.5' r='1.3' fill='%23d6a93c'/%3E%3C/svg%3E")
# the chrome round the chart and its detail pages, every Retro's own (retro.CHROME_CSS): dark whatever the theme toggle says
RETRO_CSS += "@media screen{\n" + _rt_slim(scoped(CHROME_CSS, _X)) + "\n}\n"
STARS_CSS += RETRO_CSS

STARS_JS = _slim(STARS_JS)
STARS_CSS = _slim(STARS_CSS)

