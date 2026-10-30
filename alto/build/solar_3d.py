"""The Star chart's Realistic 3D style as a real 3D scene (Luke, 2026-10-21: "I see no difference between 3d
hyperrealistic style and classic star chart"; he asked for "a 3D game world" — clean 3D objects with real depth
and lighting, like a space strategy game; a FREE camera, drag to turn the whole system and look from any angle,
with a reset; varied real body types, each easy to tell apart; the unit still readable).

With html.sk-real on a desktop System page (and WebGL there), a WebGL canvas takes the board's place:
  * every body a lit sphere with its own surface (solar_stars.py's painter, laid out once as a seamless
    longitude x latitude texture) turning on its axis, lit by its own sun, with an atmosphere's rim where it has
    air, a glint on water, and a ring on some gas giants; each sun an emitting sphere with a warm bloom;
  * planets of a system cycle through rocky, ocean, banded gas giant, icy, desert and lava, so neighbours never
    look alike (each unit starting the cycle elsewhere); moons are cratered; satellites small metal craft;
  * the orbits and spokes drawn in the scene (orbits in the unit's colour), the unit's reach as a faint ring, its
    name above its sun, and every body's name under it;
  * a free camera: drag turns the system (any angle), the wheel / pinch comes nearer or farther, a sideways
    swipe turns it about; "Reset view" (and a double-click on space) brings back the default three-quarter view;
  * the same navigation as ever: a click on a body (or a spoke: its far end; an orbit: what is on it) enlarges it
    through the engine's own enterFocus, the arrows and Spokes only step through it, and the camera glides to
    whatever is enlarged; the hints (where each arrow goes) are pills at their bodies, edge pills when off screen.
The board's own DOM stays as it is, hidden (the enlarged disc still shows, over the scene), so nothing else
needs to know. Without WebGL the style stays the 2D one (solar_stars.py realTick). System pages only.

The close-up (Luke, 2026-10-21: "Not happy with the 3d level of detail/feel when planets are enlarged"; he wants a
game close-up, Stellaris / Mass Effect): the enlarged body IS the globe. The camera dives (one continuous move,
minimum-jerk, distance on a log scale) until the body fills the enlarged disc's circle, wherever the engine shows
it, with its sun to one side so the day / night terminator shows; and flies back out to where it was. The disc
itself keeps only its content, on a soft dark scrim, fading in as the camera arrives. Every globe's detail is
procedural, in the fragment shader (3D value noise from a 256 x 256 noise texture made at load): terrain relief
lit per pixel, crisp coastlines, craters, dunes, ice cracks, lava glow, banded turbulence, a cloud layer of its
own (drifting, casting shadows), city lights on ocean worlds' night side, an atmosphere's rim and halo; its
octaves come in with the body's size on screen, so detail ramps up as the camera nears (no swap, no pop), and a
finer sphere is drawn once a body is big. A slow machine steps the detail (and the canvas's resolution) down.

Flights in 3D (Luke, 2026-10-21: "i want a real ship"): with Flights on, solar_fly.py's planner flies as ever (its
routes move the bodies on the flight's own clock, which this scene draws), and here the chosen craft
(solar_craft.py) is a lit model on the route: its nose on the route's tangent, banking a little into turns, its
engines glowing and a fine trail behind, the camera calm behind it (pulling back as it speeds up, turning towards the
body it is going to as it nears), and on landing the close-up's dive starts from there. Spokes only rides fly the same
craft (window._altoSolarRide). Flights off: the camera glides, as before. (Luke, 2026-10-22: "it should come
into a gentle orbit around planets") It never flies into a body: it comes into a gentle orbit round the one it goes to,
at a radius by that body's size, and goes on round it while the close-up shows; the model is small and clear, smaller
still near a small body.

The small bodies (Luke, 2026-10-22: an enlarged satellite was a blank grey grid sphere and the moon beside it a giant
black disc; "If its not a real moon, its ok to make a 3d render of satillite/space station/astroid/commet"): moons cycle
six kinds by their order under their planet (each planet starting elsewhere): cratered grey, icy and cracked (Europa),
sulphur with volcanoes (Io), rusty dust, dark carbon, orange haze (Titan), each its painted surface (the moon's,
recoloured) and its own detail in the shader. A satellite-level body is a real object, its neighbours never alike: an
artificial satellite (bus, solar wings, dish or telescope), a space station (truss, wings, modules with lit windows, a
ring, a docking port: the plan's station is always one), a lumpy asteroid (its shape pushed out in the vertex shader)
or a comet (an icy nucleus, its coma and two soft tails away from its sun). A plan's look (black hole, comet, asteroid)
is honoured as in 2D: a black hole is a black horizon with a photon rim, a hot accretion disc and a glow. No night side
goes black (a cool fill of about 8% and a soft rim towards the camera); close up, any other body nearer the camera than
the enlarged one, or larger on screen than its disc, fades away; small bodies keep their colour (a satellite far off a
coloured glint).
"""

SOLAR3D_CSS = r"""
  #sk3d,#sk3d-l{display:none;}
  html.sk-3d:not(.mobile) #sk3d{display:block;position:fixed;z-index:1;cursor:grab;touch-action:none;}
  html.sk-3d:not(.mobile) #sk3d.drag{cursor:grabbing;}
  html.sk-3d:not(.mobile) #sk3d-l{display:block;position:fixed;z-index:2;pointer-events:none;overflow:hidden;}
  html.sk-3d:not(.mobile) #world{pointer-events:none;position:relative;z-index:3;}   /* (the enlarged disc, the one body left showing, over the scene) */
  html.sk-3d:not(.mobile) #world>*:not(.node),html.sk-3d:not(.mobile) #world>.node:not(.focused):not(.sol-closing){visibility:hidden !important;}
  html.sk-3d:not(.mobile) #world>.node:is(.focused,.sol-closing){pointer-events:auto;}
  html.sk-3d:not(.mobile) #world>.node:is(.focused,.sol-closing)>:is(.sol-lbl,.sol-nh,.sol-dot){visibility:hidden !important;}
  html.sk-3d .sol-unit,html.sk-3d #sk-mark,html.sk-3d #sk-frame{display:none !important;}
  #sk3d-l b{position:absolute;left:0;top:0;white-space:nowrap;font:600 11.5px/1.2 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#eef2ff;
    text-shadow:0 0 3px #000,0 0 2px #000;transform:translate(-50%,0);letter-spacing:.02em;}
  #sk3d-l b.u{font-size:12px;letter-spacing:.22em;text-transform:uppercase;font-weight:700;transform:translate(-50%,-100%);padding:3px 9px;border-radius:999px;
    background:rgba(8,12,28,.55);border:1px solid var(--u,#9fb4ff);color:#fff;text-shadow:none;}
  #sk3d-l b.m{font-size:10px;font-weight:500;opacity:.85;}
  #sk3d-l i{position:absolute;left:0;top:0;font:600 11px/1 -apple-system,BlinkMacSystemFont,sans-serif;font-style:normal;white-space:nowrap;color:#e8eeff;
    background:rgba(14,20,44,.86);border:1px solid rgba(160,190,255,.55);border-radius:999px;padding:4px 9px 4px 6px;transform:translate(-50%,-100%);}
  #sk3d-l i kbd{display:inline-block;font:700 10px/16px inherit;min-width:16px;height:16px;text-align:center;border-radius:4px;margin-right:6px;
    background:#cfe0ff;color:#0b1430;}
  #sk3d-l i.pl{transform:none;}
  #sk3d-l i em{font-style:normal;opacity:.7;margin-right:5px;text-transform:uppercase;font-size:9px;letter-spacing:.1em;}
  /* the enlarged disc in 3D: no disc of its own (the globe under it is the body), its content on a soft scrim */
  html.sk-3d:not(.mobile) #world>.node[data-solar]:is(.focused,.sol-closing) .node-card:not(#_){background:transparent !important;border-color:transparent !important;
    box-shadow:none !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;}
  html.sk-3d:not(.mobile) #world>.node[data-solar]:is(.focused,.sol-closing) .node-card::before,html.sk-3d:not(.mobile) #world>.node[data-solar]:is(.focused,.sol-closing) .node-card::after{display:none !important;}
  html.sk-3d:not(.mobile) #world>.node[data-solar]:is(.focused,.sol-closing) .node-card>:is(.sk,.sk-rot){visibility:hidden !important;}
  html.sk-3d:not(.mobile) #world .alto-fshadow{visibility:hidden !important;}
  html.sk-3d:not(.mobile) #world>.node[data-solar]:is(.focused,.sol-closing) .sol-scrim:not(#_){opacity:calc(var(--sbo,1) * var(--s3o,1));
    background:radial-gradient(ellipse 47% 37% at 50% 40%,rgba(3,6,16,.58) 0%,rgba(3,6,16,.44) 48%,rgba(3,6,16,.16) 78%,rgba(3,6,16,0) 100%) !important;}
  html.sk-3d:not(.mobile) #world>.node[data-solar=sun]:is(.focused,.sol-closing) .sol-scrim:not(#_){
    background:radial-gradient(ellipse 50% 40% at 50% 41%,rgba(14,6,0,.8) 0%,rgba(14,6,0,.66) 50%,rgba(14,6,0,.25) 80%,rgba(14,6,0,0) 100%) !important;}
  html.sk-3d:not(.mobile) #world>.node[data-solar]:is(.focused,.sol-closing) :is(.sol-body,.node-card>.node-footer):not(#_){opacity:calc(var(--sbo,1) * var(--s3o,1)) !important;}
  html.sk-3d:not(.mobile) #world>.node[data-solar]:is(.focused,.sol-closing) .sol-body *{text-shadow:0 1px 2px rgba(0,0,0,.9),0 0 14px rgba(0,0,0,.6) !important;}
  html.sk-3d:not(.mobile) #world>.node[data-solar]:is(.focused,.sol-closing) .node-card>.node-footer>*{box-shadow:0 2px 10px rgba(0,0,0,.45);}
  #sol-ctl #sk3d-reset{display:none;}   /* (two ids: #sol-ctl button's own display no longer shows it in every style) */
  html.sk-3d #sol-ctl #sk3d-reset:not([hidden]){display:inline-flex;}
"""

SOLAR3D_JS = r"""
(function(){
'use strict';
var RC=null, de=document.documentElement, cv=null, lay=null, gl=null, P={}, ready=false, on=false, raf=0, BOD={}, sky=null;
var cam={tx:0, ty:0, tz:0, d:1600, az:-0.6, el:0.62, fov:0.82, ox:0, oy:0}, tw=null, LK=null, pre=null, QL=1, dtA=16, slow=0, lastT=0, TAU=Math.PI*2, foc=undefined, drag=null, VPm=null, EYE=[0, 0, 0], RT=[1, 0, 0], UP=[0, 1, 0];
var TYPES=['rocky', 'ocean', 'gas', 'ice', 'desert', 'lava'], ATM={rocky:[.55,.6,.7], ocean:[.4,.66,1], gas:[.95,.82,.6], ice:[.6,.88,1], desert:[1,.66,.45], lava:[1,.45,.2],
  icy:[.7,.85,1], sulphur:[1,.85,.45], rust:[1,.6,.4], haze:[1,.62,.25]};
/* the moons' six kinds (each the moon's painted surface recoloured: dark, middle, light) and the satellite level's four objects */
var MOONS=['moon', 'icy', 'sulphur', 'rust', 'carbon', 'haze'], SATS=['sat', 'asteroid', 'station', 'comet'], MK={sat:1, station:1}, NT={sun:1, sat:1, station:1, blackhole:1};
var MT={icy:[[.5,.44,.38],[.85,.8,.72],[.97,.96,.93]], sulphur:[[.5,.3,.08],[.92,.68,.22],[1,.9,.55]], rust:[[.3,.14,.08],[.62,.32,.18],[.85,.6,.42]],
  carbon:[[.07,.06,.05],[.18,.15,.12],[.34,.28,.22]], haze:[[.5,.3,.1],[.8,.55,.22],[.95,.78,.45]]};
/* each kind's shading: [type for the shader, atmosphere, cloud cover's threshold (1: none), cloud opacity] */
/* the craft's model: its scale on the way (the models are about 60 long) and the least near a small body; the chase camera's distance */
var K3={S:.2, S_MIN:.06, CD:[120, 340], Y:3};
var KD={rocky:[0, .32, .6, .5], ocean:[1, 1, .53, .95], gas:[2, .55, 1, 0], ice:[3, .7, .62, .45], desert:[4, .55, .66, .35], lava:[5, .4, .68, .3], moon:[6, 0, 1, 0], sun:[8, 0, 1, 0],
  icy:[9, .12, 1, 0], sulphur:[10, .1, 1, 0], rust:[11, .1, 1, 0], carbon:[12, 0, 1, 0], haze:[13, .95, .38, .75], asteroid:[14, 0, 1, 0], comet:[15, 0, 1, 0], blackhole:[16, 0, 1, 0]};
function geo(){ return window._altoSolarGeo ? window._altoSolarGeo() : null; }
function want(){ return de.classList.contains('sk-real') && de.classList.contains('alto-stars') && !de.classList.contains('mobile') && !de.classList.contains('alto-editing')
  && !document.querySelector('#detail-page.visible') && !!window._altoSolarGeo && !!window._altoSkPaint; }
function zoomK(){ return parseFloat(getComputedStyle(de).zoom)||1; }
/* ── a little matrix kit ── */
function persp(f, a, n, fa){ var t=1/Math.tan(f/2); return [t/a,0,0,0, 0,t,0,0, 0,0,(fa+n)/(n-fa),-1, 0,0,2*fa*n/(n-fa),0]; }
function look(e, c, u){ var z=nrm(sub(e, c)), x=nrm(crs(u, z)), y=crs(z, x); RT=x; UP=y;
  return [x[0],y[0],z[0],0, x[1],y[1],z[1],0, x[2],y[2],z[2],0, -dot(x,e),-dot(y,e),-dot(z,e),1]; }
function mul(a, b){ var o=new Array(16); for(var i=0;i<4;i++) for(var j=0;j<4;j++){ var s=0; for(var k=0;k<4;k++) s+=a[k*4+j]*b[i*4+k]; o[i*4+j]=s; } return o; }
function sub(a, b){ return [a[0]-b[0], a[1]-b[1], a[2]-b[2]]; } function dot(a, b){ return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]; }
function crs(a, b){ return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]; } function nrm(a){ var l=Math.hypot(a[0], a[1], a[2])||1; return [a[0]/l, a[1]/l, a[2]/l]; }
function proj(p){ var m=VPm, x=m[0]*p[0]+m[4]*p[1]+m[8]*p[2]+m[12], y=m[1]*p[0]+m[5]*p[1]+m[9]*p[2]+m[13], w=m[3]*p[0]+m[7]*p[1]+m[11]*p[2]+m[15];
  if(w<=1e-3) return null; var r=RC||(RC=cv.getBoundingClientRect()); return {x:r.left+(x/w*.5+.5)*r.width, y:r.top+(1-(y/w*.5+.5))*r.height, w:w, s:r.height/2/Math.tan(cam.fov/2)/w}; }
/* ── shaders ── */
function sh(vs, fs){ var p=gl.createProgram(); [[gl.VERTEX_SHADER, vs], [gl.FRAGMENT_SHADER, fs]].forEach(function(q){ var s=gl.createShader(q[0]); gl.shaderSource(s, q[1]); gl.compileShader(s);
    if(!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); gl.attachShader(p, s); });
  gl.linkProgram(p); var o={p:p, a:{}, u:{}}, n=gl.getProgramParameter(p, gl.ACTIVE_ATTRIBUTES), i;
  for(i=0;i<n;i++){ var a=gl.getActiveAttrib(p, i).name; o.a[a]=gl.getAttribLocation(p, a); }
  n=gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS); for(i=0;i<n;i++){ var u=gl.getActiveUniform(p, i).name; o.u[u]=gl.getUniformLocation(p, u); } return o; }
/* (an asteroid or a comet: lu = [lumps, 1 / its three half-axes], its shape turned with its spin sv, its normal from two
   neighbours; O the sphere's point, for its surface) */
var VS_B='attribute vec3 p;attribute vec2 t;uniform mat4 VP;uniform vec3 C,E,L;uniform vec2 sv;uniform vec4 lu;uniform float R,sp;varying vec3 N,V,Lv,O;varying vec2 T;'+
  'float sf(vec3 v){vec3 q=vec3(v.x*sv.x+v.z*sv.y,v.y,v.z*sv.x-v.x*sv.y),s=q*lu.yzw;return inversesqrt(dot(s,s))*(1.+lu.x*(sin(dot(q,vec3(3.1,1.7,2.3))+lu.y*9.)*.5'+
    '+sin(dot(q,vec3(-2.3,4.1,1.3))*1.7+lu.z*7.)*.3+sin(dot(q,vec3(5.3,-3.7,4.9))+lu.w*5.)*.2));}'+
  'void main(){O=p;vec3 n=p;float h=1.;if(lu.x>0.){h=sf(p);vec3 a=normalize(cross(abs(p.y)<.99?vec3(0.,1.,0.):vec3(1.,0.,0.),p)),b=cross(p,a),pa=normalize(p+a*.04),pb=normalize(p+b*.04);'+
    'n=normalize(cross(pa*sf(pa)-p*h,pb*sf(pb)-p*h));if(dot(n,p)<0.)n=-n;}N=n;vec3 w=C+p*h*R;V=E-w;Lv=L-w;T=vec2(t.x+sp,t.y);gl_Position=VP*vec4(w,1.);}';
/* a globe: its painted surface (the macro look) and, by its size on screen (oc octaves, dl detail), the procedural rest */
var FS_B='precision highp float;varying vec3 N,V,Lv,O;varying vec2 T;uniform sampler2D tx,th,nz;uniform vec3 A,K;uniform vec2 sc,cc;'+
  'uniform float em,ht,hm,ty,oc,dl,ep,tm,at,cv,ca,fa,sz;'+
  'vec3 tx2(vec2 u){vec3 a=texture2D(tx,u).rgb;return hm>0.?mix(a,texture2D(th,u).rgb,hm):a;}'+
  'vec3 ry(vec3 v,vec2 c){return vec3(v.x*c.x+v.z*c.y,v.y,v.z*c.x-v.x*c.y);}'+
  'float n3(vec3 x){vec3 p=floor(x),f=fract(x);f=f*f*(3.-2.*f);vec2 u=p.xy+vec2(37.,17.)*p.z+f.xy;vec2 g=texture2D(nz,(u+.5)/256.).xy;return mix(g.x,g.y,f.z);}'+
  'float fb(vec3 p,float o){float s=0.,a=.5;for(int i=0;i<7;i++){float w=clamp(o-float(i),0.,1.);if(w<=0.)break;s+=a*w*(n3(p)-.5);a*=.5;p=p*2.07+vec3(1.7,9.2,3.1);}return s;}'+
  'float rg(vec3 p,float o){float s=0.,a=.5;for(int i=0;i<6;i++){float w=clamp(o-float(i),0.,1.);if(w<=0.)break;float k=1.-abs(2.*n3(p)-1.);s+=a*w*(k*k-.45);a*=.5;p=p*2.11+vec3(4.1,2.3,7.7);}return s;}'+
  'float cr(vec3 p){vec3 b=floor(p-.5);float h=0.;for(int i=0;i<8;i++){float fi=float(i);vec3 c=b+vec3(mod(fi,2.),mod(floor(fi/2.),2.),floor(fi/4.));vec2 u=c.xy+vec2(37.,17.)*c.z;'+
    'float r1=texture2D(nz,(u+.5)/256.).x,r2=texture2D(nz,(u+vec2(91.5,53.5))/256.).x,r3=texture2D(nz,(u+vec2(13.5,201.5))/256.).x;if(r3<.45)continue;'+
    'vec3 q=c+vec3(r1,r2,fract(r1*7.13+r2*3.7));float d=length(p-q)/(.2+.32*fract(r3*5.3));h+=d<1.?(d*d-1.)*.5+.18*d*d*d*d:.18*exp(-(d-1.)*(d-1.)*14.);}return h*.5;}'+
  'float hg(vec3 r){if(ty<.5)return fb(r*5.,oc)*.9+rg(r*3.,oc-1.)*.5+cr(r*6.)*.55;if(ty<1.5)return fb(r*4.,oc);if(ty<2.5)return 0.;'+
    'if(ty<3.5)return fb(r*5.,oc)*.4+rg(r*2.5,oc)*.3;if(ty<4.5)return fb(r*4.5,oc)*.7+rg(r*vec3(3.,14.,3.),oc-1.)*.25+cr(r*5.)*.3;'+
    'if(ty<5.5)return fb(r*5.,oc)*.6+rg(r*3.,oc)*.5;if(ty<6.5||ty>10.5&&ty<12.5)return fb(r*5.,oc)*.6+cr(r*5.)+cr(r*13.)*.45;'+
    'if(ty<9.5)return fb(r*5.,oc)*.3+rg(r*vec3(2.,5.,2.),oc)*.3;if(ty<10.5)return fb(r*4.,oc)*.4+cr(r*4.)*.5;if(ty<13.5)return fb(r*4.,oc)*.3;'+
    'if(ty<14.5)return fb(r*4.,oc)*.8+cr(r*5.)*.9+cr(r*12.)*.4;return fb(r*5.,oc)*.8+rg(r*3.,oc)*.45;}'+
  'float cl(vec3 q,float o){vec3 w=q*3.+vec3(fb(q*2.,3.),fb(q*2.+5.2,3.),fb(q*2.-3.7,3.))*1.6;return smoothstep(cv,cv+.24,fb(w,o)+.5);}'+
  'void main(){vec3 n=normalize(N),v=normalize(V),l=normalize(Lv),r=ry(normalize(O),sc);vec2 tt=T;'+
    'if(ty>15.5){gl_FragColor=vec4(vec3(1.,.66,.36)*pow(1.-max(dot(n,v),0.),6.)*1.6*fa,fa);return;}'+
    'if(abs(ty-2.)<.5&&dl>0.){tt+=vec2(fb(r*vec3(2.5,10.,2.5)+vec3(tm*.004,0.,0.),oc)*.05,fb(r*vec3(4.,22.,4.)-vec3(0.,0.,tm*.006),oc)*.018)*dl;}'+
    'vec3 c=ht>.5?tx2(tt):K;'+
    'if(em>.5){float m=max(dot(n,v),0.),g=fb(r*18.+vec3(0.,tm*.01,0.),oc)+fb(r*48.-vec3(tm*.02),oc-1.)*.6;vec3 s=c*(.75+.6*m)+vec3(.25,.18,.05)*(1.-m);'+
      's=mix(s,c*(.6+.5*pow(m,.45))*mix(vec3(1.),vec3(1.,.62,.32),(1.-m)*.7),dl);s*=1.+g*.45*dl;gl_FragColor=vec4(s*fa,fa);return;}'+
    'float wet=abs(ty-1.)<.5?smoothstep(.05,.25,c.b-max(c.r,c.g)):0.,lg=0.,ct=0.,g0=dot(n,l);vec3 nn=n;'+
    'if(dl>0.){float h=hg(r),bs=ty<.5?.9:ty<1.5?.6:ty<2.5?0.:ty<3.5?.5:ty<4.5?.55:ty<5.5?.6:ty<6.5?1.1:ty<9.5?.45:ty<10.5?.6:ty<12.5?1.1:ty<13.5?.25:1.25;vec3 d=c;'+
      'if(ty<.5)d=c*(.78+h*.9);'+
      'else if(ty<1.5){vec2 bx=vec2(2.2/256.,1.1/128.)*(1.-.75*hm),by=vec2(-1.1/256.,2.2/128.)*(1.-.75*hm);vec3 cb=(c*2.+tx2(tt+bx)+tx2(tt-bx)+tx2(tt+by)+tx2(tt-by))/6.;'+
        'float wb=smoothstep(.05,.25,cb.b-max(cb.r,cb.g)),m=(1.-wb)+h*(.5+2.2*(1.-abs(2.*wb-1.))),ld=smoothstep(.46,.54,m),ic=smoothstep(.7,.82,min(c.r,min(c.g,c.b)));'+
        'vec3 lc=mix(mix(vec3(.22,.4,.18),vec3(.56,.48,.33),clamp(h*1.8+.5,0.,1.)),c,(1.-smoothstep(.02,.2,wet))*.7);'+
        'd=mix(mix(vec3(.02,.1,.3),vec3(.07,.36,.56),smoothstep(.2,.48,m)),lc*(.85+h*.7),ld);d=mix(d,vec3(.92,.95,.98),ic);'+
        'bs*=ld;wet=mix(wet,(1.-ld)*(1.-ic),dl);ct=smoothstep(.68,.85,n3(r*55.))*smoothstep(.55,.75,n3(r*11.))*ld*(1.-ic);}'+
      'else if(ty<2.5)d=c*(1.+(n3(r*vec3(1.5,70.,1.5))-.5)*.16*min(oc*.3,1.));'+
      'else if(ty<3.5){d=c*(.85+h*.55);d=mix(d,vec3(.16,.32,.5),smoothstep(.18,.34,rg(r*4.,oc))*.65);d=mix(d,vec3(.95,.98,1.),smoothstep(.05,.28,fb(r*3.,oc))*.5);}'+
      'else if(ty<4.5)d=c*(.82+h*.8);'+
      'else if(ty<5.5){d=c*(.65+h*.6);lg=smoothstep(.22,.42,rg(r*3.6,oc+1.));}'+
      'else if(ty<6.5)d=c*(.72+h*.75);'+
      'else if(ty<9.5){d=mix(c*(.9+h*.4),vec3(.62,.5,.38),smoothstep(.6,.75,n3(r*3.+8.))*.5);float L=0.;'+   /* (Europa: long crossing lineae, arcs of circles, faintly doubled) */
        'for(int i=0;i<6;i++){float f=float(i);vec3 a=normalize(vec3(sin(f*2.4+.3),cos(f*1.7)*.7,cos(f*2.4+.3)));float x=abs(dot(r,a)+.25*sin(f*1.9)+.07*(n3(r*3.+f*7.)-.5));'+
        'L=max(L,(1.-smoothstep(.004,.016,x))+(1.-smoothstep(.003,.01,abs(x-.03)))*.6);}d=mix(d,vec3(.6,.33,.2),min(L,1.)*.85);}'+
      'else if(ty<10.5){float z=n3(r*9.+11.);d=mix(c*(.85+h*.5),vec3(.96,.93,.84),smoothstep(.62,.75,n3(r*3.+4.))*.45);d=mix(d,vec3(.78,.26,.08),smoothstep(.6,.7,z)*.75);'+
        'd=mix(d,vec3(.1,.06,.04),smoothstep(.76,.8,z));lg=smoothstep(.84,.88,z)*.7*(1.-smoothstep(-.1,.3,g0));}'+
      'else if(ty<11.5)d=mix(c*(.78+h*.8),c*1.25+.05,smoothstep(.55,.7,fb(r*vec3(2.,7.,2.),oc)+.5)*.5);'+
      'else if(ty<12.5)d=c*(.75+h*.9)+vec3(.1,.09,.08)*smoothstep(.12,.3,cr(r*5.));'+
      'else if(ty<13.5)d=mix(c*(.9+h*.3),vec3(.45,.28,.12),smoothstep(.55,.9,abs(r.y))*.5);'+
      'else if(ty<14.5)d=c*(.7+h*.9);'+
      'else d=mix(c*(.6+h*.7),vec3(.82,.9,1.),smoothstep(.62,.72,n3(r*5.+2.))*.6);'+
      'if(bs>0.){vec3 t1=normalize(cross(abs(n.y)<.99?vec3(0.,1.,0.):vec3(1.,0.,0.),n)),t2=cross(n,t1);'+
        'vec3 gr=((hg(r+ry(t1,sc)*ep)-h)*t1+(hg(r+ry(t2,sc)*ep)-h)*t2)/ep;nn=normalize(n-gr*bs*.04*dl);}'+
      'c=mix(c,d,dl);}'+
    'float cw=0.,cs=0.;if(ca>0.){float co=max(oc,3.);vec3 q=ry(n,cc);cw=cl(q,co)*ca;cs=cl(ry(normalize(n-l*.02),cc),co-2.)*ca;}'+
    'float gt=smoothstep(-.12,.2,g0),df=max(dot(nn,l),0.)*gt;vec3 tn=mix(vec3(1.),vec3(1.,.5,.3),at*(1.-smoothstep(0.,.4,g0))*.8),hv=normalize(l+v);'+
    'float sp2=pow(max(dot(nn,hv),0.),90.)*wet*1.3+pow(max(dot(nn,hv),0.),24.)*(abs(ty-3.)<.5||abs(ty-9.)<.5?.25:.04),nv=max(dot(n,v),0.);'+
    'vec3 o=c*(vec3(.05,.058,.08)+vec3(.03,.035,.05)*max(dot(nn,v),0.)+1.12*df*tn)*(1.-cs*.55*gt)+vec3(1.,.95,.86)*sp2*gt*(1.-cw);'+   /* (a cool fill: no night side black) */
    'o+=vec3(1.,.42,.1)*lg*dl*(1.15-gt*.6)+vec3(1.,.75,.4)*ct*dl*.85*(1.-smoothstep(-.2,.05,g0))*(1.-cw);'+
    'vec3 ck=ty>3.5&&ty<4.5?vec3(.9,.76,.6):ty>4.5&&ty<5.5?vec3(.34,.31,.3):ty>12.5&&ty<13.5?vec3(.86,.6,.3):vec3(.97,.98,1.);o=mix(o,ck*(.06+1.05*max(g0,0.)*gt)*tn,cw);'+
    'float fr=pow(1.-nv,2.4);o+=A*fr*at*(.06+1.1*smoothstep(-.25,.6,g0))+(c+.12)*vec3(.3,.36,.5)*pow(1.-nv,3.)*(1.-gt)*.45;'+   /* (and a soft rim towards the camera) */
    'float sk=1.-smoothstep(3.,24.,sz);o=mix(vec3(dot(o,vec3(.3,.59,.11))),o,1.+sk*.5)*(1.+sk*.3);gl_FragColor=vec4(o*fa,fa);}';   /* (a small body keeps its colour) */
var VS_G='attribute vec2 q;uniform mat4 VP;uniform vec3 C,X,Y;uniform float S;varying vec2 Q;void main(){Q=q;gl_Position=VP*vec4(C+(X*q.x+Y*q.y)*S,1.);}';
var FS_G='precision mediump float;varying vec2 Q;uniform vec3 K;uniform float a;void main(){float r=length(Q);if(r>1.)discard;float g=pow(1.-r,2.4);gl_FragColor=vec4(K*g*a,g*a);}';
var FS_H='precision highp float;varying vec2 Q;uniform vec3 K,X,Y,L;uniform float a;void main(){float r=length(Q);if(r<.97||r>1.3)discard;'+
  'float g=r<1.?smoothstep(.97,1.,r):exp(-(r-1.)*24.);float k=g*smoothstep(-.45,.65,dot(normalize(X*Q.x+Y*Q.y),L))*a*.9;gl_FragColor=vec4(K*k,k*.6);}';
var CG=window._altoCraft && window._altoCraft.gl;            /* (the craft's high-definition shader: solar_craft.py) */
var VS_R='attribute vec2 q;uniform mat4 VP;uniform vec3 C,X,Y;uniform float R;varying vec2 Q;void main(){Q=q;gl_Position=VP*vec4(C+(X*q.x+Y*q.y)*R,1.);}';
var FS_R='precision mediump float;varying vec2 Q;uniform vec3 K;uniform float a;void main(){float r=length(Q);if(r<1.35||r>2.3)discard;float b=.55+.45*sin(r*38.)*sin(r*11.);'+
  'float e=smoothstep(1.35,1.45,r)*smoothstep(2.3,2.18,r);gl_FragColor=vec4(K*b,.6*e*(abs(r-1.9)<.04?.25:1.))*a;}';
/* a black hole's accretion disc: hot within, turning streaks */
var FS_A='precision mediump float;varying vec2 Q;uniform float a,tm;void main(){float r=length(Q);if(r<1.25||r>2.6)discard;float w=atan(Q.y,Q.x),t=1.-smoothstep(1.25,2.6,r);'+
  'float s=.62+.38*sin(w*3.-r*6.+tm*1.5)*sin(w*7.+r*11.-tm*2.3),e=smoothstep(1.25,1.33,r)*smoothstep(2.6,2.1,r)*a;'+
  'gl_FragColor=vec4(mix(vec3(.9,.25,.05),vec3(1.,.86,.58),t*t)*(.25+1.1*t*t)*s*e,e*.7);}';
/* a comet's tail: a soft strip from the nucleus away from its sun, widening and fading, faintly streaked */
var VS_T='attribute vec2 q;uniform mat4 VP;uniform vec3 C,D,X;uniform float Lg,Wd;varying vec2 Q;void main(){Q=q;gl_Position=VP*vec4(C+D*q.x*Lg+X*q.y*Wd*(.35+q.x*1.3),1.);}';
var FS_T='precision mediump float;varying vec2 Q;uniform vec3 K;uniform float a,tm;void main(){float u=Q.x,v=Q.y,s=.75+.25*sin(v*9.+u*4.-tm*.6)*sin(v*23.-u*7.);'+
  'float k=pow(1.-u,1.6)*exp(-v*v*3.5)*s*smoothstep(0.,.06,u)*a;gl_FragColor=vec4(K*k,k*.5);}';
var VS_L='attribute vec3 p;attribute vec4 k;uniform mat4 VP;varying vec4 K;void main(){K=k;gl_Position=VP*vec4(p,1.);}';
var FS_L='precision mediump float;varying vec4 K;void main(){gl_FragColor=vec4(K.rgb*K.a,K.a);}';
var VS_C='attribute vec2 c;uniform mat4 VP;uniform vec3 C;uniform float r;void main(){gl_Position=VP*vec4(C+vec3(c.x*r,0.,c.y*r),1.);}';
var FS_C='precision mediump float;uniform vec4 K;void main(){gl_FragColor=vec4(K.rgb*K.a,K.a);}';
var VS_S='attribute vec3 p;attribute float z;uniform mat4 VP;uniform vec3 E;varying float B;void main(){B=z;gl_Position=VP*vec4(E+p*90000.,1.);gl_PointSize=1.+z*1.8;}';
var FS_S='precision mediump float;varying float B;void main(){gl_FragColor=vec4(vec3(.75+.25*B),.35+.6*B);}';
function buf(a){ var b=gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(a), gl.STATIC_DRAW); return b; }
function attr(pr, name, b, n){ var l=pr.a[name]; if(l==null || l<0) return; gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.enableVertexAttribArray(l); gl.vertexAttribPointer(l, n, gl.FLOAT, false, 0, 0); }
function init(){
  cv=document.createElement('canvas'); cv.id='sk3d'; cv.setAttribute('aria-label', 'The system in 3D: drag to turn it, scroll to come nearer');
  lay=document.createElement('div'); lay.id='sk3d-l'; lay.setAttribute('aria-hidden', 'true');
  try{ gl=cv.getContext('webgl', {antialias:true, alpha:true, premultipliedAlpha:true}); }catch(e){ gl=null; }
  if(!gl) return false;
  var hp=gl.getShaderPrecisionFormat && gl.getShaderPrecisionFormat(gl.FRAGMENT_SHADER, gl.HIGH_FLOAT);
  if(!hp || !hp.precision){ FS_B=FS_B.replace('highp', 'mediump'); FS_H=FS_H.replace('highp', 'mediump'); if(CG) CG.fs=CG.fs.replace('highp', 'mediump'); QL=0; }   /* (no highp: no procedural detail) */
  try{ P.k=CG ? sh(CG.vs, CG.fs) : null; P.h=sh(VS_G, FS_H); P.b=sh(VS_B, FS_B); P.g=sh(VS_G, FS_G); P.r=sh(VS_R, FS_R); P.l=sh(VS_L, FS_L); P.c=sh(VS_C, FS_C); P.s=sh(VS_S, FS_S); P.a=sh(VS_R, FS_A); P.t=sh(VS_T, FS_T); }catch(e){ if(window.console) console.warn('3d', e); gl=null; return false; }
  /* a sphere, its texture's longitude across, latitude up: 40 x 24, and 128 x 64 for a big one */
  P.lo=mesh(40, 24); P.hi=mesh(128, 64);
  /* the noise: random values, the green a copy of the red 37 across and 17 down (one fetch gives two slices of 3D value noise) */
  var NR=mkR(11), nb=new Uint8Array(262144), rr=new Uint8Array(65536), i, j; for(i=0;i<65536;i++) rr[i]=(NR()*256)|0;
  for(j=0;j<256;j++) for(i=0;i<256;i++){ var o=(j*256+i)*4; nb[o]=rr[j*256+i]; nb[o+1]=rr[((j+17)&255)*256+((i+37)&255)]; nb[o+2]=nb[o+3]=255; }
  P.nz=gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, P.nz); gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 256, 256, 0, gl.RGBA, gl.UNSIGNED_BYTE, nb);
  [gl.TEXTURE_WRAP_S, gl.TEXTURE_WRAP_T].forEach(function(k){ gl.texParameteri(gl.TEXTURE_2D, k, gl.REPEAT); });
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  P.q=buf([-1,-1, 1,-1, -1,1, 1,1]); P.q3=buf([-3,-3, 3,-3, -3,3, 3,3]); P.q4=buf([-1.3,-1.3, 1.3,-1.3, -1.3,1.3, 1.3,1.3]);
  var c=[]; for(i=0;i<=128;i++){ var w=i/128*Math.PI*2; c.push(Math.cos(w), Math.sin(w)); } P.ci=buf(c);
  c=[]; for(i=0;i<=8;i++) c.push(i/8, -1, i/8, 1); P.qt=buf(c);
  var R=mkR(7), sp=[], sz=[]; for(i=0;i<2600;i++){ var u=R()*2-1, ph=R()*Math.PI*2, s=Math.sqrt(1-u*u); sp.push(s*Math.cos(ph), u, s*Math.sin(ph)); sz.push(Math.pow(R(), 6)); }
  P.sp=buf(sp); P.sz=buf(sz); P.sn2=sz.length;
  P.lb=gl.createBuffer(); P.tb=gl.createBuffer();
  cv.addEventListener('pointerdown', down); cv.addEventListener('pointermove', move); window.addEventListener('pointerup', up, true);
  cv.addEventListener('dblclick', function(e){ e.preventDefault(); e.stopPropagation(); reset(); });
  /* the pick is the pointerup's; no click on the scene (a pick, or the end of a turn) may reach the engine, which reads it as a
     click away and lets the enlarged body go: stopped at the window, ahead of the document's listeners */
  ['click', 'mousedown', 'mouseup'].forEach(function(ty){ window.addEventListener(ty, function(e){ if(e.target===cv){ e.stopImmediatePropagation(); e.preventDefault(); } }, true); });
  window.addEventListener('wheel', wheel, {capture:true, passive:false});
  return true;
}
function mesh(LO, LA){ var v=[], t=[], ix=[], i, j;
  for(j=0;j<=LA;j++){ var la=(j/LA-.5)*Math.PI; for(i=0;i<=LO;i++){ var lo=(i/LO)*Math.PI*2-Math.PI; v.push(Math.cos(la)*Math.sin(lo), Math.sin(la), Math.cos(la)*Math.cos(lo)); t.push(i/LO, 1-j/LA); } }
  for(j=0;j<LA;j++) for(i=0;i<LO;i++){ var a=j*(LO+1)+i, b=a+LO+1; ix.push(a, b, a+1, a+1, b, b+1); }
  var e=gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, e); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(ix), gl.STATIC_DRAW);
  return {v:buf(v), t:buf(t), i:e, n:ix.length}; }
function mkR(a){ return function(){ a=(a*1664525+1013904223)>>>0; return a/4294967296; }; }
function hsh(s){ var h=2166136261; for(var i=0;i<s.length;i++){ h^=s.charCodeAt(i); h=Math.imul(h, 16777619); } return h>>>0; }
function rgbOf(c){ var m=/^#?([0-9a-f]{6})$/i.exec(String(c||'').trim()); if(m){ var v=parseInt(m[1], 16); return [(v>>16&255)/255, (v>>8&255)/255, (v&255)/255]; }
  m=/rgb\w*\((\d+)[ ,]+(\d+)[ ,]+(\d+)/.exec(c||''); return m ? [m[1]/255, m[2]/255, m[3]/255] : [.62,.7,1]; }
/* each body: its kind (a system's planets cycle the types, each unit starting elsewhere), its name, its texture (built a few rows a frame) */
function bodies(G){
  var per={}, ps={}, st={}, ids=Object.keys(G.bodies), N=(window._ALTO_SOLAR||{}).nodes||{};
  ids.forEach(function(id){ if((N[id]||{}).station) st[G.bodies[id].p]=1; });          /* (beside the plan's station, no second one) */
  ids.forEach(function(id){ var g=G.bodies[id], o=BOD[id]; if(o) return;
    var n=document.getElementById('node-'+id), lb=n && n.querySelector('.sol-lbl'), kind, P=N[id]||{}, k=(per[g.p]=(per[g.p]||0)+1)-1;
    if(/^(blackhole|comet|asteroid)$/.test(P.look||'')) kind=P.look;            /* (a plan's look overrules the role's, as in 2D) */
    else if(g.role==='sun') kind='sun'; else if(g.role==='moon') kind=MOONS[(k+hsh(g.p||''))%6];
    else if(g.role==='sat'){ var L=st[g.p] ? SATS.filter(function(x){ return x!=='station'; }) : SATS; kind=P.station ? 'station' : L[((ps[g.p]=(ps[g.p]||0)+1)-1+hsh(g.p||''))%L.length]; }
    else kind=TYPES[(k+(g.si||0)*2)%TYPES.length];
    var R=mkR(hsh(id+'#3d')), lp=/^(asteroid|comet)$/.test(kind);
    BOD[id]={id:id, kind:kind, name:(lb && lb.getAttribute('data-l')) || (n && n.getAttribute('data-title')) || '', tex:null, ty:0, v:(kind==='station' ? 't' : 's')+(hsh(id)&3),
      spin:(lp ? 22 : kind==='gas' ? 40 : g.role==='moon' ? 160 : 70)*(.7+R()*.7), ph:R(), ring:kind==='gas' && R()<.6, tilt:(R()-.5)*.9,
      lu:lp ? [kind==='comet' ? .16 : .18+R()*.08, .95+R()*.05, 1.4+R()*.2, 1.15+R()*.15] : [0, 0, 0, 0]}; });
}
function texJob(o, W, H, inc){                      /* a surface painted a few rows a frame: job(deadline) -> its texture once done */
  var T=MT[o.kind], p0=window._altoSkPaint(T ? 'moon' : o.kind, o.id, {nc:1}), D=new Uint8Array(W*H*4), y=0, t=null;
  var pa=T ? function(lo, la){ var c=p0(lo, la), s=Math.max(0, Math.min(1, (c[0]-50)/150)), a=T[s<.5 ? 0 : 1], b=T[s<.5 ? 1 : 2], u=s<.5 ? s*2 : s*2-1;   /* (a moon's kind: its surface recoloured) */
    return [(a[0]+(b[0]-a[0])*u)*255, (a[1]+(b[1]-a[1])*u)*255, (a[2]+(b[2]-a[2])*u)*255]; } : p0;
  function mk(){ t=gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t); gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, W, H, 0, gl.RGBA, gl.UNSIGNED_BYTE, inc ? null : D);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR); }
  return function(dl){ var y0=y;
    while(y<H && performance.now()<dl){ var la=(.5-(y+.5)/H)*Math.PI;
      for(var x=0;x<W;x++){ var lo=(x+.5)/W*TAU-Math.PI, f=(x+.5)/W, a=pa(lo, la), b=pa(lo-TAU, la), i=(y*W+x)*4;
        D[i]=a[0]*(1-f)+b[0]*f; D[i+1]=a[1]*(1-f)+b[1]*f; D[i+2]=a[2]*(1-f)+b[2]*f; D[i+3]=255; }
      y++; }
    if(inc){ if(!t) mk(); if(y>y0){ gl.bindTexture(gl.TEXTURE_2D, t); gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, y0, W, y-y0, gl.RGBA, gl.UNSIGNED_BYTE, D.subarray(y0*W*4, y*W*4)); } }   /* (sent as painted: no big upload at the end) */
    if(y<H) return null;
    if(!inc) mk(); return t; };
}
function texStep(o, dl){
  if(NT[o.kind]) return true;
  if(!o.job) o.job=texJob(o, 256, 128, false);
  var t=o.job(dl); if(!t) return false; o.tex=t; o.job=null; return true;
}
/* the enlarged body's finer surface (and the last two kept): painted first, faded in over half a second */
var HI=[];
function hiStep(id, dl){ var o=BOD[id]; if(!o || !o.tex || NT[o.kind] || o.thi) return;
  if(!o.hj){ o.hj=texJob(o, 1024, 512, true); if(HI.indexOf(id)<0) HI.push(id);
    while(HI.length>3){ var q=BOD[HI.shift()]; if(q){ if(q.thi) gl.deleteTexture(q.thi); q.thi=q.hj=null; q.h0=0; } } }
  var t=o.hj(dl); if(t){ o.thi=t; o.hj=null; o.h0=performance.now(); } }
/* ── the camera ── */
function W(g){ return [g.x, 0, g.y]; }               /* the board's plane is the scene's ground: x across, the board's y into the distance */
function sunOf(G, id){ var g=G.bodies[id], k=0; while(g && g.role!=='sun' && g.p && G.bodies[g.p] && k++<6){ id=g.p; g=G.bodies[id]; } return g; }
function home(G){
  var U=G.units, best=null, bd=Infinity;
  (U||[]).forEach(function(u){ var s=G.bodies[u.sun]; if(!s) return; var dd=Math.hypot(s.x-cam.tx, s.y-cam.tz); if(dd<bd){ bd=dd; best=u; } });
  var s=best && G.bodies[best.sun]; return s ? {x:s.x, z:s.y, d:Math.max(900, (best.R||800)*2.3)} : {x:cam.tx, z:cam.tz, d:cam.d}; }
function snap(){ return {x:cam.tx, z:cam.tz, d:cam.d, az:cam.az, el:cam.el, ox:cam.ox, oy:cam.oy}; }
function glide(G, keepAngle){ var h=home(G); tw={t0:performance.now(), ms:850, hop:0, a:snap(), b:{x:h.x, z:h.z, d:h.d, az:keepAngle ? cam.az : -0.6, el:keepAngle ? cam.el : 0.62, ox:0, oy:0}}; }
function reset(){ var G=geo(); MOVED=0; if(!G) return;
  if(LK && foc){ LK.da=LK.de=0; tw={t0:performance.now(), ms:800, hop:0, a:snap(), lock:foc}; } else glide(G, false); }
function mj(p){ return p*p*p*(10+p*(6*p-15)); }                                  /* minimum jerk (Luke's eye, 1.9.16) */
function sm(a, b, x){ var t=Math.max(0, Math.min(1, (x-a)/(b-a))); return t*t*(3-2*t); }
function wrap(a){ return ((a+Math.PI)%TAU+TAU)%TAU-Math.PI; }
/* the close-up: the body where the engine shows its enlarged disc and as big as the disc will be (its card grows to
   --sD at zoom 1.7), seen with its sun 60 degrees to one side (the terminator in view), turned as far as the person dragged */
function cin(G, id, r){
  var g=G.bodies[id], R=g.d/2, cx=r.left+r.width/2, cy=r.top+r.height/2, rp=Math.min(r.width, r.height)*.24, n=document.getElementById('node-'+id), c=n && n.querySelector('.node-card');
  if(c){ var b=c.getBoundingClientRect(); if(b.width>2){ var D=parseFloat(n.style.getPropertyValue('--sD'))||0, w=parseFloat(n.style.getPropertyValue('--scd'))||D, z=parseFloat(c.style.zoom)||1;
    cx=b.left+b.width/2; cy=b.top+b.height/2; rp=b.width/2*(D && w ? D/w : 1)*(n.classList.contains('focused') ? 1.7/z : 1); } }
  cin.rp=rp; var F=r.height/2/Math.tan(cam.fov/2), s=sunOf(G, id), L=LK||{side:1, da:0, de:0}, az=(L.az0!=null ? L.az0 : cam.az)+L.da;
  if(s && s!==g) az=Math.atan2(s.x-g.x, s.y-g.y)+L.side*1.05+L.da;
  return {x:g.x, z:g.y, d:R*Math.sqrt(1+(F/rp)*(F/rp)), az:az, el:Math.max(-1.2, Math.min(1.35, (g.role==='sun' ? .45 : .3)+L.de)),
    ox:(cx-(r.left+r.width/2))/(r.width/2), oy:-(cy-(r.top+r.height/2))/(r.height/2)};
}
/* the focus moved: dive in (from where the camera was, kept to fly back to), hop across (pulling back on the way), or fly back out */
function focus(G, a, b){
  var t=performance.now(), A=snap(); if(!a && !b) return;
  if(b){ if(!a && !(pre && SH.end && t-SH.end<1500)) pre=tw && tw.b ? tw.b : A;      /* (a landing keeps the view from before the flight to go back to) */
    var g=G.bodies[b], s=sunOf(G, b), side=1;
    if(s && s!==g){ var sa=Math.atan2(s.x-g.x, s.y-g.y); side=Math.abs(wrap(cam.az-sa-1.05))<=Math.abs(wrap(cam.az-sa+1.05)) ? 1 : -1; }
    if(s && s!==g){ var ks=[side, -side].map(function(sd){ LK={id:b, side:sd, da:0, de:0, az0:cam.az}; var Q=cin(G, b, RC||cv.getBoundingClientRect()), E=[Q.x+Q.d*Math.cos(Q.el)*Math.sin(Q.az), Q.d*Math.sin(Q.el), Q.z+Q.d*Math.cos(Q.el)*Math.cos(Q.az)], m=1e9;
      Object.keys(G.bodies).forEach(function(i){ var o=G.bodies[i]; if(i!==b) m=Math.min(m, Math.hypot(E[0]-o.x, E[1], E[2]-o.y)-o.d/2); }); return m; });
      if(ks[0]<24 && ks[1]>ks[0]) side=-side; }          /* (the sun's side that leaves the eye clear of its moons) */
    LK={id:b, side:side, da:0, de:0, az0:cam.az};
    var tr=Math.hypot(g.x-A.x, g.y-A.z), nb=document.getElementById('node-'+b); if(nb) nb.style.setProperty('--s3o', '0');
    tw={t0:t, a:A, lock:b, leave:a, ms:a ? 1000 : 1150, hop:a ? Math.min(1.2, Math.max(0, tr/Math.max(A.d, 1)*.45-.1)) : 0}; }
  else { LK=null; tw={t0:t, a:A, b:pre || {x:A.x, z:A.z, d:A.d*6, az:A.az, el:.62, ox:0, oy:0}, leave:a, ms:950, hop:0}; pre=null; }
}
function blend(A, B, p, hop){ var e=mj(p), et=mj(Math.min(1, p*1.35));             /* (the aim leads the zoom: the body comes to its place, then near) */
  cam.tx=A.x+(B.x-A.x)*et; cam.tz=A.z+(B.z-A.z)*et; cam.d=Math.exp(Math.log(A.d)+(Math.log(B.d)-Math.log(A.d))*e)*(1+hop*Math.sin(Math.PI*e));
  cam.az=A.az+wrap(B.az-A.az)*e; cam.el=A.el+(B.el-A.el)*e; cam.ox=A.ox+(B.ox-A.ox)*e; cam.oy=A.oy+(B.oy-A.oy)*e; }
/* the eye never in a body, nor so near that the near plane cuts it (Luke, 2026-10-28: "it's the camera view for the
   viewer"): every body keeps a clear shell round it (half its radius, the sun four fifths, and a little more, and a few near planes), the eye
   pressed out of it along the line from the body's centre by a smooth curve (a flat push would be a visible kink), so
   a flight, a dive, a drag or a zoom arcs round a body instead of through it. w: how much of the push (the dive's
   last stretch lets it go, to land exactly on the close-up); ex: the bodies it is not applied to (the one dived to / left) */
function keep(G, E, w, ex){ if(w<=0) return E; var nr=Math.max(2, cam.d/400);
  for(var it=0;it<2;it++) Object.keys(G.bodies).forEach(function(id){ if(ex && ex[id]) return;
    var g=G.bodies[id], R=g.d/2, C=R*(g.role==='sun' ? .8 : .5)+6+nr*3, Rc=R+C, B=C*.7, dx=E[0]-g.x, dy=E[1], dz=E[2]-g.y, r=Math.hypot(dx, dy, dz); if(r>=Rc+B) return;
    var q=Rc+B*Math.exp((r-Rc-B)/B), u=r<1e-3 ? [0, 1, 0] : [dx/r, dy/r, dz/r];
    E=[E[0]+(g.x+u[0]*q-E[0])*w, E[1]+(u[1]*q-E[1])*w, E[2]+(g.y+u[2]*q-E[2])*w]; });
  return E; }
/* ── the minimap and the whole-system view (Luke, 2026-10-28: "minimap in 3D system isn't quite expanding to the whole system") ──
   The 2D camera (window._altoSolarCam) is what the minimap's box, the whole-system toggle, pinch and cmd-minus move; the
   scene's own camera followed none of it. Zoomed out, the scene now frames the same part of the plan: the view the 2D
   camera shows, and at the whole system every body and every unit's outer orbit, with a margin, at any aspect ratio. */
var OVS=null, WSAVE=null, WDET=0, WLAST=0, WM=.9;     /* the 2D view while zoomed out; the camera to go back to; a hand on the scene let it go */
function wpad(){ return (typeof WORLD_PAD_TOP!=='undefined') ? WORLD_PAD_TOP : 0; }
function ovWatch(){ var C=window._altoSolarCam; if(!C || C._w3) return; C._w3=1;
  C.onChange(function(g){ var z=g && g.scale<.999; if(!z || !OVS || Math.abs(g.scale-OVS.s)>1e-4 || Math.abs(g.cx-OVS.cx)>.5 || Math.abs(g.cy-OVS.cy)>.5) WDET=0; OVS=z ? g : null; kick(); }); }
/* the nearest the eye can be (aimed at tx, tz from this angle) with every ground point inside the frame, by a margin */
function fitD(pts, tx, tz, az, el, asp){
  var ce=Math.cos(el), z=[ce*Math.sin(az), Math.sin(el), ce*Math.cos(az)], x=nrm(crs([0, 1, 0], z)), y=crs(z, x), t=1/Math.tan(cam.fov/2), d=60;
  pts.forEach(function(q){ var r=[q[0]-tx, 0, q[1]-tz], vz=dot(r, z); d=Math.max(d, vz+Math.max(Math.abs(dot(r, x))*t/asp, Math.abs(dot(r, y))*t)/WM); });
  return d; }
function ovTarget(G, o, asp){
  var py=wpad(), cv0=document.getElementById('canvas')||{}, w=Math.max(1, cv0.clientWidth||1)/o.scale/2, h=Math.max(1, cv0.clientHeight||1)/o.scale/2;
  var all=[], x0=1e9, x1=-1e9, y0=1e9, y1=-1e9;
  Object.keys(G.bodies).forEach(function(i){ var g=G.bodies[i], r=Math.max(g.d/2, 4); [[g.x-r, g.y], [g.x+r, g.y], [g.x, g.y-r], [g.x, g.y+r]].forEach(function(q){ all.push(q); }); });
  (G.units||[]).forEach(function(u){ var s=G.bodies[u.sun]; if(!s || !u.R) return; for(var k=0;k<16;k++) all.push([s.x+u.R*Math.cos(k*TAU/16), s.y+u.R*Math.sin(k*TAU/16)]); });
  all.forEach(function(q){ x0=Math.min(x0, q[0]); x1=Math.max(x1, q[0]); y0=Math.min(y0, q[1]); y1=Math.max(y1, q[1]); });
  var m=Math.max(x1-x0, y1-y0)*.03; x0-=m; x1+=m; y0-=m; y1+=m;
  /* the 2D view, cut to the system (the board round it is empty): all of it showing, it is the whole system, orbits and all */
  var vx0=o.cx-w, vx1=o.cx+w, vy0=o.cy+py-h, vy1=o.cy+py+h, cx0=Math.max(vx0, x0), cx1=Math.min(vx1, x1), cy0=Math.max(vy0, y0), cy1=Math.min(vy1, y1);
  if(!all.length || cx1<=cx0 || cy1<=cy0){ cx0=vx0; cx1=vx1; cy0=vy0; cy1=vy1; }       /* (looking at the empty board: where it looks) */
  var tx=(cx0+cx1)/2, tz=(cy0+cy1)/2, whole=all.length && cx0<=x0+1e-6 && cx1>=x1-1e-6 && cy0<=y0+1e-6 && cy1>=y1-1e-6;
  var pts=whole ? all : [[cx0, cy0], [cx1, cy0], [cx0, cy1], [cx1, cy1]];
  return {x:tx, z:tz, d:fitD(pts, tx, tz, cam.az, cam.el, asp)}; }
function ovCam(G, now, asp){
  var o=OVS; if(!WSAVE){ WSAVE=snap(); }
  var B=ovTarget(G, o, asp), dt=Math.min(100, WLAST ? now-WLAST : 16), k=1-Math.exp(-dt/130); WLAST=now;
  cam.tx+=(B.x-cam.tx)*k; cam.tz+=(B.z-cam.tz)*k; cam.d=Math.exp(Math.log(cam.d)+(Math.log(B.d)-Math.log(cam.d))*k); cam.ox*=1-k; cam.oy*=1-k; }
/* ── input: drag turns, wheel / pinch nears, a click picks ── */
function down(e){ if(e.button) return; drag={x:e.clientX, y:e.clientY, az:cam.az, el:cam.el, da:LK ? LK.da : 0, de:LK ? LK.de : 0, m:false, id:e.pointerId}; try{ cv.setPointerCapture(e.pointerId); }catch(x){} }
function move(e){
  if(drag && e.pointerId===drag.id){ var dx=e.clientX-drag.x, dy=e.clientY-drag.y; if(!drag.m && Math.abs(dx)+Math.abs(dy)<4) return;
    drag.m=true; if(lk()) return;                 /* Spokes only: no free camera (a drag turns nothing) */
    cv.classList.add('drag'); MOVED=1;
    if(LK && foc){ var a0=LK.da, e0=LK.de; LK.da=drag.da-dx*.006; LK.de=Math.max(-1.5, Math.min(1.05, drag.de+dy*.006));
      if(!tw){ cam.az+=LK.da-a0; cam.el+=LK.de-e0; } return; }   /* (close up: the camera turns about the globe, at once) */
    tw=null; WDET=1; cam.az=drag.az-dx*.006; cam.el=Math.max(-1.45, Math.min(1.45, drag.el+dy*.006)); return; }
  var h=pick(e.clientX, e.clientY); cv.style.cursor=h ? 'pointer' : '';
  tip(h && h.line ? h : null, e);
}
function up(e){ if(!drag || e.pointerId!==drag.id) return; var d=drag; drag=null; cv.classList.remove('drag');
  if(d.m) return; var h=pick(e.clientX, e.clientY); if(!h) return;
  var to=h.id; if(h.sp) to=window._focusedNodeId===h.sp[1] ? h.sp[0] : h.sp[1];
  if(to && lk() && window._altoSolarGo){ setTimeout(function(){ window._altoSolarGo(to, e); }, 0); return; }   /* Spokes only: one spoke away rides, the rest says so */
  if(to && window.enterFocus) setTimeout(function(){ window.enterFocus(to); }, 0); }
function lk(){ return !!(window._altoSolarLock && window._altoSolarLock.get()); }   /* (after the click this pointerup makes: the engine reads that as a click away) */
function wheel(e){
  if(!on || !cv || !(e.target===cv || (lay && lay.contains(e.target)))) return;
  if(lk()) return;        /* (Spokes only: no zoom; a scroll rides a spoke, solar_draw.py) */
  e.preventDefault(); e.stopImmediatePropagation();
  var m=e.deltaMode===1 ? 16 : e.deltaMode===2 ? 400 : 1, dy=e.deltaY*m, dx=e.deltaX*m;
  if(LK && foc){ if(dy>2 && window.exitFocus) window.exitFocus(); return; }       /* close up, scrolling out leaves the close-up (flying back out) */
  tw=null; MOVED=1; WDET=1;
  cam.d=Math.max(60, Math.min(60000, cam.d*Math.exp(dy*(e.ctrlKey ? .012 : .0025))));
  if(!e.ctrlKey) cam.az-=dx*.004;
}
/* what is under the pointer: a body (its projected disc, at least 10px), else a spoke, else an orbit (6px) */
var LINES=[];
function pick(x, y){
  var G=geo(); if(!G || !VPm) return null; var best=null, bd=Infinity, near=null, nd=Infinity;
  /* on a body's own disc: the nearest to the camera; else, within 10px, the one whose edge is nearest (a small moon, not the satellite beside it) */
  Object.keys(G.bodies).forEach(function(id){ var g=G.bodies[id], q=proj(W(g)); if(!q || (BOD[id] && BOD[id].fa<.5)) return; var rp=g.d/2*q.s, d=Math.hypot(q.x-x, q.y-y);
    if(d<rp){ if(q.w<bd){ bd=q.w; best={id:id}; } } else if(d<Math.max(10, rp) && d-rp<nd){ nd=d-rp; near={id:id}; } });
  if(best || near) return best || near;
  for(var i=0;i<LINES.length;i++){ var L=LINES[i], k;
    for(k=0;k+1<L.pts.length;k++){ var a=L.pts[k], b=L.pts[k+1]; if(!a || !b) continue; var vx=b.x-a.x, vy=b.y-a.y, l2=vx*vx+vy*vy||1, t=Math.max(0, Math.min(1, ((x-a.x)*vx+(y-a.y)*vy)/l2));
      if(Math.hypot(a.x+vx*t-x, a.y+vy*t-y)<6) return L; } }
  return null;
}
var TIP=null, tipT=0;
function tip(h, e){ clearTimeout(tipT);
  if(!h){ if(TIP) TIP.style.display='none'; return; }
  tipT=setTimeout(function(){ if(!TIP){ TIP=document.createElement('div'); TIP.className='line-tip'; document.body.appendChild(TIP); }
    TIP.textContent=h.tip; TIP.style.display='block'; TIP.style.left=(e.clientX+12)+'px'; TIP.style.top=(e.clientY+14)+'px'; }, 300); }
/* ── a frame ── */
function frame(){
  raf=0; var w=want(); if(w!==on) toggle(w); if(!on) return;
  var G=geo(); if(!G){ raf=requestAnimationFrame(frame); return; }
  bodies(G);
  var now=performance.now(), f=window._focusedNodeId||null; if(f && !G.bodies[f]) f=null;
  var FS=fly(G, now);
  if(f!==foc){ if(FS){ LK=null; tw=null; } else focus(G, foc, f); foc=f; }        /* (on the way: the card it left goes home, the camera stays on the craft) */
  pace(now);
  size(); RC=null;
  var r=RC=cv.getBoundingClientRect(), asp=r.width/Math.max(1, r.height), nf=f && document.getElementById('node-'+f);
  if(FS) chase(G, now);
  else if(tw){ var p=Math.min(1, (now-tw.t0)/tw.ms); blend(tw.a, tw.lock ? cin(G, tw.lock, r) : tw.b, p, tw.hop);
    if(nf && tw.lock===f) nf.style.setProperty('--s3o', String(Math.round(sm(.72, 1, p)*1000)/1000));
    var nl=tw.leave && document.getElementById('node-'+tw.leave); if(nl){ if(p>=1) nl.style.removeProperty('--s3o'); else nl.style.setProperty('--s3o', String(Math.round((1-sm(0, .2, p))*1000)/1000)); }
    if(p>=1) tw=null; }
  else if(f && LK){ var B=cin(G, f, r); cam.tx=B.x; cam.tz=B.z; cam.d=B.d; cam.az=B.az; cam.el=B.el; cam.ox=B.ox; cam.oy=B.oy; if(nf) nf.style.setProperty('--s3o', '1'); }   /* (held on the disc, round its orbit) */
  else if(OVS && !f && !WDET && !FS && !LK){ ovCam(G, now, asp); }
  else if(WSAVE && !OVS){ var wb=WSAVE; WSAVE=null; WLAST=0; if(!f && !FS) tw={t0:now, ms:800, hop:0, a:snap(), b:wb}; }
  EYE=[cam.tx+cam.d*Math.cos(cam.el)*Math.sin(cam.az), cam.d*Math.sin(cam.el), cam.tz+cam.d*Math.cos(cam.el)*Math.cos(cam.az)];
  if(!(f && LK && !tw && !FS)){ var kx={}, kp=tw ? Math.min(1, (now-tw.t0)/tw.ms) : 1; if(tw && tw.lock) kx[tw.lock]=1; if(tw && tw.leave) kx[tw.leave]=1;      /* (held on a close-up: its own, with the fades; the dive eases the push off at its end) */
    EYE=keep(G, EYE, tw && tw.lock ? 1-sm(.6, 1, kp) : 1, kx); }
  var V=look(EYE, [cam.tx, 0, cam.tz], [0, 1, 0]); VPm=mul(persp(cam.fov, asp, Math.max(2, cam.d/400), 200000), V);
  for(var k=0;k<4;k++){ VPm[k*4]+=cam.ox*VPm[k*4+3]; VPm[k*4+1]+=cam.oy*VPm[k*4+3]; }         /* (the lens shifted: the aim drawn where the disc is) */
  /* close up, what fades: judged against the enlarged body (the one left, on the way out), coming in with the dive; "larger" against the disc it is diving to */
  var fi=LK ? LK.id : tw && tw.leave, gf=fi && G.bodies[fi], qf=gf && proj(W(gf)), pt=tw ? Math.min(1, (now-tw.t0)/tw.ms) : 1;
  FC=qf ? {id:fi, x:qf.x, y:qf.y, w:qf.w, rp:gf.d/2*qf.s, rd:LK && cin.rp || gf.d/2*qf.s, k:LK ? (tw && !tw.leave ? sm(.1, .5, pt) : 1) : 1-sm(0, .45, pt)} : null;
  gl.viewport(0, 0, cv.width, cv.height); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
  gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
  stars(); lines(G); spheres(G); objs(G, now); craft3(G, now); halos(G); fx(G, now); glows(G); labels(G, r);
  var dl=performance.now()+3; if(foc && (!tw || now-tw.t0>300)) hiStep(foc, performance.now()+3);      /* (not in the dive's first, busiest frames) */
  Object.keys(BOD).sort(function(a, b){ return dist(G, a)-dist(G, b); }).some(function(id){ var o=BOD[id]; if(o.tex || NT[o.kind]) return false; texStep(o, dl); return performance.now()>=dl; });
  raf=requestAnimationFrame(frame);
}
/* ── the craft: where the flight (or the Spokes-only ride) has it, its nose on the way's tangent and its bank
   (solar_craft.py's steer); landed, in its gentle orbit round the enlarged body (solar_craft.py's parked) while the
   close-up shows; the camera behind it on the way ── */
var SH={on:false, al:0, tr:[], hs:null, bk:0, v:0};
function fly(G, now){
  var A=window._altoCraft, F=window._altoSolarFlight && window._altoSolarFlight(), R=!F && window._altoSolarRide && window._altoSolarRide(), p=null, v=null, m=null, id=null, o;
  var dt=SH.lt ? Math.min(.05, (now-SH.lt)/1000) : 0; SH.lt=now;
  if(F && F.at){ p=F.at; v=F.v; m='fly'; } else if(R && R.p){ p=R.p; v=R.v || [Math.cos(R.h), Math.sin(R.h)]; m='fly'; }
  else if(A && A.orbiting()){ id=window._focusedNodeId; var g=id && G.bodies[id]; o=g && A.parked(id, [g.x, g.y]);
    if(o){ p=o.p; v=o.v; m='park'; } else A.unpark(); }              /* (left the close-up: the orbit is over) */
  if(!p){ if(SH.on){ SH.on=false; SH.end=now; SH.m=null; } SH.al=Math.max(0, SH.al-dt*1.8); return null; }
  var cr=A ? A.get() : {};
  if(!SH.on){ SH.on=true; SH.hs=null; SH.ht=null; SH.tr=[]; SH.v=0; SH.bk=0; SH.m=null; }
  if(SH.cr!==cr.id){ SH.cr=cr.id; SH.hs=SH.ht=null; }      /* (a new pick shows at once, in orbit too: the ship stays on between flights) */
  if(m==='fly' && SH.m!=='fly'){ SH.t0=now; SH.a=snap(); SH.hc=null; SH.cd=null; }   /* (the chase eases in from where the camera is; the heading carries on) */
  SH.m=m; if(A && v) A.steer(SH, v, dt); if(v && F && F.fx && F.fx.warp>.02){ SH.hs=SH.ht=Math.atan2(v[1], v[0]); SH.bk=0; }
  if(v) SH.v+=(Math.hypot(v[0], v[1])-SH.v)*Math.min(1, dt*2);
  SH.th=F && F.thr || null; SH.sg=F && F.sg || 1;            /* (the engines on the way: solar_craft.py thrust()) */
  SH.F=F || null; SH.fx=F && F.fx || null; if(SH.fx && SH.fx.vis<.99) SH.tr=[];      /* (a warp, a jump: solar_craft.py travel; no trail through a jump) */
  SH.p=[p[0], p[1]]; SH.to=F ? F.to : R ? R.to : id; SH.fr=F ? F.from : R ? R.from : id; SH.al=Math.min(1, SH.al+dt*3); SH.y=lift(G, p);
  SH.tr.push([p[0], p[1], now, SH.y]); while(SH.tr.length>2 && now-SH.tr[0][2]>1600) SH.tr.shift();
  return m==='fly' ? SH : null;
}
/* the craft's height over the board's plane: a little above it, in the plane its orbits and ways are flown in (Luke,
   2026-10-25: ships "end up going above"), lifted only where it would pass through a body (one merely passed on the
   way: its course keeps it off the bodies it goes round, its orbits clear of them): over a sphere 4 px larger than the
   body, tapering (a cubic, level at its edge) from 4 px inside the body's edge to 4 px outside it, so it never dips
   into the body and nothing lifts it a few px clear of one */
function lift(G, p){ var y=K3.Y, m=12;
  Object.keys(G.bodies).forEach(function(id){ var g=G.bodies[id], R=g.d/2, h=Math.hypot(g.x-p[0], g.y-p[1]), h0, V, t; if(h>=R+m) return;
    h0=Math.max(0, R-m); V=Math.sqrt((R+m)*(R+m)-h0*h0);
    if(h<=h0) y+=Math.sqrt((R+m)*(R+m)-h*h); else { t=(h-h0)/(R+m-h0); y+=(1-t)*(1-t)*(V*(1+2*t)-h0/V*(R+m-h0)*t); } });
  return y; }
/* the model's scale: small and clear on the way (Luke, 2026-10-22: "we don't need the ship to be massive, just clear"),
   smaller still near a small body (about a quarter of its width), so a moon's close-up is not all ship */
function shipS(G){ var S=K3.S, A=window._altoCraft;
  [SH.to, SH.fr].forEach(function(id){ var g=id && G.bodies[id]; if(!g || !A) return; var r=A.orbitR(g.d), sb=Math.max(K3.S_MIN, Math.min(K3.S, g.d/240)),
    w=sm(r*1.15, r*3.6, Math.hypot(g.x-SH.p[0], g.y-SH.p[1])); S=Math.min(S, sb+(K3.S-sb)*w); });
  return S; }
/* calm behind the craft: farther back the faster it goes, turning to the body it is going to as it nears; eased in from where the camera was */
function chase(G, now){
  if(SH.hs==null) return; var dt=Math.min(.05, SH.lt0 ? (now-SH.lt0)/1000 : .016); SH.lt0=now;
  var p=SH.p, q=G.bodies[SH.to], ht=SH.hs;
  if(q){ var dg=Math.hypot(q.x-p[0], q.y-p[1]); ht+=wrap(Math.atan2(q.y-p[1], q.x-p[0])-SH.hs)*sm(900, 200, dg)*.6; }
  SH.hc=SH.hc==null ? ht : SH.hc+wrap(ht-SH.hc)*Math.min(1, dt*1.5);
  var cd=Math.max(K3.CD[0], Math.min(K3.CD[1], K3.CD[0]+SH.v*.08)); SH.cd=SH.cd==null ? cd : SH.cd+(cd-SH.cd)*Math.min(1, dt*1.1);
  blend(SH.a, {x:p[0]+Math.cos(SH.hc)*40, z:p[1]+Math.sin(SH.hc)*40, d:SH.cd, az:Math.atan2(-Math.cos(SH.hc), -Math.sin(SH.hc)), el:.22+.12*sm(150, 420, SH.cd), ox:0, oy:0},
    Math.min(1, (now-SH.t0)/1000), 0);
}
var CM={};
function craft3(G, now){
  if(SH.al<=0 || !SH.p || SH.hs==null || !window._altoCraft || !P.k) return;
  var FX=SH.fx || {vis:1, warp:0, fa:0, fb:0, fw:0}, AL=SH.al*FX.vis;
  var cr=window._altoCraft.list.filter(function(c){ return c.id===SH.cr; })[0] || window._altoCraft.get(), m=CM[cr.id];
  if(!m){ var o=window._altoCraft.mesh(cr.id); m=CM[cr.id]={p:buf(o.p), n:buf(o.n), k:gl.createBuffer(), c:o.p.length/3};
    gl.bindBuffer(gl.ARRAY_BUFFER, m.k); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(o.k), gl.STATIC_DRAW); }
  /* (braking on the way in: a rocket turned tail first on its main engine, the others firing retro thrusters forward) */
  var E=window._altoCraft.engines ? window._altoCraft.engines(SH.th, cr.id) : {m:0, r:0, f:0};
  if(FX.wu>.02) E.m=Math.max(E.m, FX.wu);        /* (winding up for a warp or a jump) */
  SH.e=E; SH.nose=SH.hs+SH.sg*Math.PI*E.f;
  var S=shipS(G), th=-SH.nose+(cr.spin ? now/1000*cr.spin : 0), b=cr.roll ? now/1000*cr.roll : -SH.bk*(cr.bank||0)*.6*(1-E.f), c=Math.cos(th), s=Math.sin(th), cb=Math.cos(b), sb=Math.sin(b), Y=SH.y||K3.Y;
  var SX=1+1.2*Math.max(FX.warp, FX.ws||0), M=[c*S*SX, 0, -s*S*SX, 0, s*sb*S, cb*S, c*sb*S, 0, s*cb*S, -sb*S, c*cb*S, 0, SH.p[0], Y, SH.p[1], 1], sun=sunOf(G, SH.to)||{x:0, y:0};
  /* the trail: a fine line fading behind */
  var tv=[], tk=[], T=cr.trail||[.8, .85, 1];
  for(var i=0;i+1<SH.tr.length;i++){ var A=SH.tr[i], B2=SH.tr[i+1], a0=(1-(now-A[2])/1600)*.55*AL, a1=(1-(now-B2[2])/1600)*.55*AL;
    tv.push(A[0], A[3]||Y, A[1], B2[0], B2[3]||Y, B2[1]); tk.push(T[0], T[1], T[2], Math.max(0, a0), T[0], T[1], T[2], Math.max(0, a1)); }
  /* at warp, the stars streaking past: fine lines round the craft along its way, drifting aft */
  if(FX.warp>.02){ var hx=Math.cos(SH.hs), hz=Math.sin(SH.hs);
    for(var si=0;si<22;si++){ var sp=.35+((si*53)%7)/10, off=((si*37)%17-8)*7, yy=Y+((si*29)%11-5)*3, al0=(110-((now*.13*sp+si*71)%260))*.5, L=(10+70*FX.warp)*sp*.5, aw=.55*FX.warp*AL;
      var x0=SH.p[0]+hx*al0-hz*off, z0=SH.p[1]+hz*al0+hx*off; tv.push(x0, yy, z0, x0-hx*L, yy, z0-hz*L); tk.push(.8, .9, 1, aw, .8, .9, 1, 0); } }
  gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA); gl.enable(gl.DEPTH_TEST);
  if(tv.length){ var l=P.l; gl.useProgram(l.p); gl.uniformMatrix4fv(l.u.VP, false, VPm); gl.depthMask(false);
    gl.bindBuffer(gl.ARRAY_BUFFER, P.tb); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(tv.concat(tk)), gl.DYNAMIC_DRAW);
    gl.enableVertexAttribArray(l.a.p); gl.vertexAttribPointer(l.a.p, 3, gl.FLOAT, false, 0, 0); gl.enableVertexAttribArray(l.a.k); gl.vertexAttribPointer(l.a.k, 4, gl.FLOAT, false, 0, tv.length*4);
    gl.drawArrays(gl.LINES, 0, tv.length/3); dis(l); gl.depthMask(true); }
  var k=P.k; gl.useProgram(k.p); gl.uniformMatrix4fv(k.u.VP, false, VPm); gl.uniformMatrix4fv(k.u.M, false, M); gl.uniform3fv(k.u.E, EYE); gl.uniform3fv(k.u.L, W(sun)); gl.uniform1f(k.u.al, AL); if(k.u.WC) gl.uniform4fv(k.u.WC, cr.wc||[0, 0, 0, 1e9]);
  attr(k, 'p', m.p, 3); attr(k, 'n', m.n, 3); gl.bindBuffer(gl.ARRAY_BUFFER, m.k); gl.enableVertexAttribArray(k.a.k); gl.vertexAttribPointer(k.a.k, 4, gl.FLOAT, false, 0, 0);
  gl.drawArrays(gl.TRIANGLES, 0, m.c); dis(k);
  /* the engines' glow, flickering a little */
  var g=P.g, G2=cr.glow||[1, .8, .5]; gl.useProgram(g.p); gl.uniformMatrix4fv(g.u.VP, false, VPm); gl.uniform3fv(g.u.X, RT); gl.uniform3fv(g.u.Y, UP); attr(g, 'q', P.q, 2);
  gl.depthMask(false); gl.blendFunc(gl.ONE, gl.ONE); gl.uniform3fv(g.u.K, G2);
  (cr.eng||[]).forEach(function(e, j){ var w=[M[0]*e[0]+M[4]*e[1]+M[8]*e[2]+M[12], M[1]*e[0]+M[5]*e[1]+M[9]*e[2]+M[13], M[2]*e[0]+M[6]*e[1]+M[10]*e[2]+M[14]], fl=1+.12*Math.sin(now*.031+j*1.7);
    gl.uniform3fv(g.u.C, w); gl.uniform1f(g.u.S, 7.6*S*fl); gl.uniform1f(g.u.a, .95*AL); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    gl.uniform1f(g.u.S, 21*S*fl); gl.uniform1f(g.u.a, .35*AL); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4); });
  /* the flames: a plume of glows streaming from each main nozzle aft (nz3, else eng) and each retro thruster forward
     (rz3), long and bright as the engine fires, flickering */
  [[cr.nz3 || cr.eng || [], -1, E.m], [cr.rz3 || [], 1, E.r*.6]].forEach(function(q){ var k=q[2]; if(k<.02) return;
    var dx=M[0]/S*q[1], dz=M[2]/S*q[1];
    q[0].forEach(function(e, j){ var w=[M[0]*e[0]+M[4]*e[1]+M[8]*e[2]+M[12], M[1]*e[0]+M[5]*e[1]+M[9]*e[2]+M[13], M[2]*e[0]+M[6]*e[1]+M[10]*e[2]+M[14]], fl=k*(1+.15*Math.sin(now*.043+j*2.3));
      for(var i=0;i<6;i++){ var d=i*3.2*S*fl; gl.uniform3fv(g.u.K, i<2 ? [1, .92, .75] : [1, .58, .24]); gl.uniform3fv(g.u.C, [w[0]+dx*d, w[1], w[2]+dz*d]);
        gl.uniform1f(g.u.S, (7.5-i*.95)*S*(.5+.5*fl)); gl.uniform1f(g.u.a, (1-i/6.5)*.9*Math.min(1, k*1.6)*AL); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4); } }); });
  /* the flashes: where it leaves (a jump), round it as it drops out of warp, where it comes out */
  [[FX.fa && SH.F && SH.F.pa, FX.fa], [FX.fw && SH.p, FX.fw], [FX.fb && SH.F && SH.F.pb, FX.fb], [FX.cg>.01 && SH.p, FX.cg, FX.gr]].forEach(function(q){ if(!q[0] || q[1]<.01) return;
    [[22, [1, 1, 1]], [70, [.55, .8, 1]]].forEach(function(z){ gl.uniform3fv(g.u.K, z[1]); gl.uniform3fv(g.u.C, [q[0][0], Y, q[0][1]]); gl.uniform1f(g.u.S, z[0]*(q[2] ? q[2]/70 : .4+.6*q[1])); gl.uniform1f(g.u.a, q[1]*SH.al); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4); }); });
  dis(g); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA); gl.depthMask(true);
}
/* a machine that cannot keep up close up gets less detail, then a coarser canvas */
function pace(now){ var dt=lastT ? now-lastT : 16; lastT=now; if(dt>250) return; dtA=dtA*.92+dt*.08;
  if(foc && !tw && QL>0){ slow=dtA>24 ? slow+1 : Math.max(0, slow-2); if(slow>45 && QL>.45){ QL=Math.round((QL-.2)*10)/10; slow=0; } } }
function dist(G, id){ var g=G.bodies[id]; return g ? Math.hypot(g.x-cam.tx, g.y-cam.tz) : 1e9; }
function size(){ var c=document.getElementById('canvas'); if(!c) return; var r=c.getBoundingClientRect(), z=zoomK(), dpr=Math.min(2, window.devicePixelRatio||1)*(QL && QL<.7 ? .75 : 1);
  cv.style.left=lay.style.left=(r.left/z)+'px'; cv.style.top=lay.style.top=(r.top/z)+'px'; cv.style.width=lay.style.width=(r.width/z)+'px'; cv.style.height=lay.style.height=(r.height/z)+'px';
  var W2=Math.round(r.width*dpr), H2=Math.round(r.height*dpr); if(cv.width!==W2 || cv.height!==H2){ cv.width=W2; cv.height=H2; } }
function stars(){ var p=P.s; gl.useProgram(p.p); gl.uniformMatrix4fv(p.u.VP, false, VPm); gl.uniform3fv(p.u.E, EYE); attr(p, 'p', P.sp, 3); attr(p, 'z', P.sz, 1);
  gl.disable(gl.DEPTH_TEST); gl.drawArrays(gl.POINTS, 0, P.sn2); dis(p); }
function dis(p){ Object.keys(p.a).forEach(function(k){ if(p.a[k]>=0) gl.disableVertexAttribArray(p.a[k]); }); }
/* close up, a body nearer the camera than the enlarged one (where it would cover it), larger on screen than its disc, nearly as large and beside it, or over the disc at all, fades */
var FC=null;
function fade(id, q, rp){ if(!FC || id===FC.id || !q) return 1;
  var d=Math.hypot(q.x-FC.x, q.y-FC.y), k=rp/FC.rd, a=Math.max(sm(.9, 1.2, k), sm(.65, .9, k)*(1-sm(rp+FC.rd*.9, rp+FC.rd*1.5, d)), 1-sm(rp+FC.rd*.85, rp+FC.rd*1.1, d), sm(0, .05, 1-q.w/FC.w)*(1-sm(rp+FC.rp*1.2, rp+FC.rp*2, d)));
  return 1-a*FC.k; }
function spheres(G){
  var p=P.b, M0=null, LT=[]; gl.useProgram(p.p); gl.enable(gl.DEPTH_TEST); gl.depthMask(true); gl.disable(gl.BLEND);
  gl.uniformMatrix4fv(p.u.VP, false, VPm); gl.uniform3fv(p.u.E, EYE);
  gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, P.nz); gl.uniform1i(p.u.nz, 1);
  var now=performance.now()/1000; gl.uniform1f(p.u.tm, now%2000);
  function one(id){ var g=G.bodies[id], o=BOD[id], s=sunOf(G, id), q=proj(W(g)), rp=q ? g.d/2*q.s : 0;
    var M=rp>40 ? P.hi : P.lo; if(M!==M0){ M0=M; attr(p, 'p', M.v, 3); attr(p, 't', M.t, 2); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, M.i); }
    var a=(now/o.spin+o.ph)%1, w=a*TAU, wc=w*1.18+now*.004, k=KD[o.kind]||KD.rocky, rd=rp*(cv.width/Math.max(1, RC.width)), oc=QL ? Math.max(0, Math.min(7, 1+Math.log2(Math.max(1, rd)/20)))*QL : 0;
    gl.uniform3fv(p.u.C, W(g)); gl.uniform1f(p.u.R, g.d/2); gl.uniform1f(p.u.sp, a); gl.uniform2f(p.u.sc, Math.cos(w), Math.sin(w)); gl.uniform2f(p.u.sv, Math.cos(w), Math.sin(w)); gl.uniform2f(p.u.cc, Math.cos(wc), Math.sin(wc));
    gl.uniform4fv(p.u.lu, o.lu); gl.uniform1f(p.u.fa, o.fa); gl.uniform1f(p.u.sz, rd);
    gl.uniform1f(p.u.oc, oc); gl.uniform1f(p.u.dl, QL ? sm(22, 120, rp) : 0); gl.uniform1f(p.u.ep, Math.max(.0006, .45/(5*Math.pow(2, oc))));
    gl.uniform1f(p.u.ty, k[0]); gl.uniform1f(p.u.at, k[1]); gl.uniform1f(p.u.cv, k[2]); gl.uniform1f(p.u.ca, QL ? k[3] : 0);
    gl.uniform3fv(p.u.L, s ? W(s) : [0, 900, 0]); gl.uniform1f(p.u.em, o.kind==='sun' ? 1 : 0);
    gl.uniform3fv(p.u.A, ATM[o.kind] || [0, 0, 0]);
    gl.uniform3fv(p.u.K, o.kind==='sun' ? [1, .78, .36] : [.45, .45, .5]);
    if(o.tex){ gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, o.tex); gl.uniform1i(p.u.tx, 0); gl.uniform1f(p.u.ht, 1); } else gl.uniform1f(p.u.ht, 0);
    var hm=o.thi ? sm(0, 500, performance.now()-o.h0)*sm(30, 70, rp) : 0;            /* (no mipmaps: only while the body is big) */ gl.uniform1f(p.u.hm, hm);
    gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_2D, o.thi || o.tex || P.nz); gl.uniform1i(p.u.th, 2);
    gl.drawElements(gl.TRIANGLES, M.n, gl.UNSIGNED_SHORT, 0); }
  Object.keys(G.bodies).forEach(function(id){ var g=G.bodies[id], o=BOD[id]; if(!o) return; var q=proj(W(g)), rp=q ? g.d/2*q.s : 0; o.fa=fade(id, q, rp);
    if(MK[o.kind] || (q && rp<.4) || o.fa<.01) return; if(o.fa<.999) LT.push(id); else one(id); });
  gl.enable(gl.BLEND); if(LT.length){ gl.depthMask(false); LT.forEach(one); gl.depthMask(true); }      /* (the fading ones last, over the rest) */
  dis(p);
  /* rings round some gas giants, tilted, lit flat by their sun */
  var r=P.r; gl.useProgram(r.p); gl.uniformMatrix4fv(r.u.VP, false, VPm); attr(r, 'q', P.q3, 2); gl.depthMask(false);
  Object.keys(BOD).forEach(function(id){ var o=BOD[id], g=G.bodies[id]; if(!o.ring || !g || !(o.fa>.01)) return; var c=Math.cos(o.tilt), s=Math.sin(o.tilt);
    gl.uniform3fv(r.u.C, W(g)); gl.uniform3fv(r.u.X, [c, s, 0]); gl.uniform3fv(r.u.Y, [0, 0, 1]); gl.uniform1f(r.u.R, g.d/2); gl.uniform3fv(r.u.K, [.86, .78, .62]); gl.uniform1f(r.u.a, o.fa);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4); });
  dis(r); gl.depthMask(true);
}
/* the satellite level's craft: a satellite (bus, three-panel wings, a dish or a telescope's tube, a beacon) or a space station (a truss, eight
   wings, modules with rows of lit windows, a ring, a docking port, radiators), built once with the ships' kit, about 64 across, nose up */
var MS={};
function mk3(v){ var g=window._altoCraft.kit(), b=+v.charAt(1), wt=[.86,.87,.89,0], gr=[.62,.64,.68,0];
  if(v.charAt(0)==='s'){ var pn=b&2 ? [.16,.2,.32,0] : [.1,.16,.42,0];
    g.box([0, 0, 0], [11, 13, 11], b&1 ? [.86,.64,.24,0] : wt); g.box([0, 0, 5.8], [7, 8, .8], [.92,.93,.95,0]); g.box([0, -7, 0], [1.2, 1.2, 1.2], [1,.3,.2,1]);
    [-1, 1].forEach(function(sd){ g.box([sd*8, 0, 0], [5, .8, .8], gr);
      for(var i=0;i<3;i++){ var x0=sd*(10.5+i*7.3), x1=sd*(17+i*7.3); g.vslab([[x0, -6], [x1, -6], [x1, 6], [x0, 6]], 0, .5, pn); } });
    if(b&1){ g.slathe([[0, 0], [.8, 2.5], [1.8, 4.5], [3.2, 6.5], [3.4, 6.5]], 18, [.93,.94,.96,0], [0, 6.5, 0], true); g.box([0, 10.5, 0], [.5, 6, .5], [.8,.8,.82,0]); }
    else { g.slathe([[0, 3.2], [9, 3.2], [9.5, 2.6]], 16, [.75,.77,.8,0], [0, 6.5, 0], true); g.lathe([[9.4, 0], [9.4, 2.6]], 16, [.05,.05,.07,.3], [0, 6.5, 0], true); } }
  else { var pa=b&1 ? [.62,.44,.18,0] : [.12,.2,.46,0], wn=[.25,.27,.3,.6];
    g.box([0, 0, 0], [64, 1.6, 1.6], gr);
    [-1, 1].forEach(function(sd){ [22, 29].forEach(function(x){ [-1, 1].forEach(function(u){ g.vslab([[sd*x-2.8, u*2], [sd*x+2.8, u*2], [sd*x+2.8, u*20], [sd*x-2.8, u*20]], 0, .4, pa); }); });
      g.box([sd*1.5-1, 0, sd*9.5], [8, .4, 7], [.9,.9,.92,0]); g.box([sd*32, 0, 0], [1, 1, 1], sd>0 ? [.3,1,.4,1] : [1,.3,.2,1]); });
    g.slathe([[-11, 0], [-10.4, 2.8], [10.4, 2.8], [11, 0]], 18, wt); g.slathe([[-2.5, 0], [-2.5, 4.2], [2.5, 4.2], [2.5, 0]], 18, wt);
    [.8, -.8].forEach(function(y){ g.box([0, y, 2.6], [17, .7, .5], wn); g.box([0, y, -2.6], [17, .7, .5], wn); });
    g.torus(2.2, .5, 16, [.8,.8,.82,0], [11.6, 0, 0]); g.torus(17, 1.6, 48, [.8,.82,.85,.6], [0, 0, 0], true); g.box([0, 0, 0], [1, 1, 34], gr); }
  var o=g.out(), m={p:buf(o.p), n:buf(o.n), k:gl.createBuffer(), c:o.p.length/3}; gl.bindBuffer(gl.ARRAY_BUFFER, m.k); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(o.k), gl.STATIC_DRAW); return m; }
/* each turned to face its sun (its wings full on), rocking gently, and enlarged a little towards the close-up's camera (so its wings never show edge on); fading as the spheres do */
function objs(G, now){
  var k=P.k, A=window._altoCraft; if(!k || !A || !A.kit) return;
  gl.enable(gl.DEPTH_TEST); gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA); gl.useProgram(k.p); gl.uniformMatrix4fv(k.u.VP, false, VPm); gl.uniform3fv(k.u.E, EYE);
  Object.keys(G.bodies).forEach(function(id){ var g=G.bodies[id], o=BOD[id], q; if(!o || !MK[o.kind] || !(o.fa>.01) || !(q=proj(W(g))) || g.d/2*q.s<.6) return;
    var m=MS[o.v]||(MS[o.v]=mk3(o.v)), s=sunOf(G, id)||{x:0, y:0}, S=g.d/2/(o.kind==='station' ? 36 : 32), yo=LK && LK.id===id ? LK.side*.5 : 0;
    o.yo=(o.yo||0)+(yo-(o.yo||0))*.06; var th=Math.atan2(s.x-g.x, s.y-g.y)+o.yo+.12*Math.sin(now/1000/o.spin*TAU+o.ph*TAU), c=Math.cos(th), n=Math.sin(th);
    gl.uniformMatrix4fv(k.u.M, false, [c*S, 0, -n*S, 0, 0, S, 0, 0, n*S, 0, c*S, 0, g.x, 0, g.y, 1]); gl.uniform3fv(k.u.L, W(s)); gl.uniform1f(k.u.al, o.fa);
    if(k.u.WC) gl.uniform4fv(k.u.WC, o.kind==='station' ? [0, 0, 19, -2] : [0, 0, 0, 1e9]);
    attr(k, 'p', m.p, 3); attr(k, 'n', m.n, 3); gl.bindBuffer(gl.ARRAY_BUFFER, m.k); gl.enableVertexAttribArray(k.a.k); gl.vertexAttribPointer(k.a.k, 4, gl.FLOAT, false, 0, 0);
    gl.drawArrays(gl.TRIANGLES, 0, m.c); });
  dis(k);
}
/* the comets' tails (a long blue one straight away from the sun, a wider warm one curving off) and the black holes' discs */
function fx(G, now){
  var p=P.t, t=now/1000%1000; gl.useProgram(p.p); gl.uniformMatrix4fv(p.u.VP, false, VPm); gl.uniform1f(p.u.tm, t); attr(p, 'q', P.qt, 2); gl.depthMask(false); gl.blendFunc(gl.ONE, gl.ONE);
  Object.keys(G.bodies).forEach(function(id){ var g=G.bodies[id], o=BOD[id], s=sunOf(G, id); if(!o || o.kind!=='comet' || !(o.fa>.01) || !s || s===g) return; var C=W(g), R=g.d/2, D=nrm(sub(C, W(s)));
    [[D, 16, 1.1, [.45,.7,1], .5], [nrm([D[0]+D[2]*.35, .04, D[2]-D[0]*.35]), 10, 2.2, [1,.9,.7], .4]].forEach(function(T){
      gl.uniform3fv(p.u.C, C); gl.uniform3fv(p.u.D, T[0]); gl.uniform3fv(p.u.X, nrm(crs(T[0], sub(EYE, C)))); gl.uniform1f(p.u.Lg, R*T[1]); gl.uniform1f(p.u.Wd, R*T[2]);
      gl.uniform3fv(p.u.K, T[3]); gl.uniform1f(p.u.a, T[4]*o.fa); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 18); }); });
  dis(p); p=P.a; gl.useProgram(p.p); gl.uniformMatrix4fv(p.u.VP, false, VPm); gl.uniform1f(p.u.tm, t); attr(p, 'q', P.q3, 2);
  Object.keys(G.bodies).forEach(function(id){ var g=G.bodies[id], o=BOD[id]; if(!o || o.kind!=='blackhole' || !(o.fa>.01)) return; var c=Math.cos(o.tilt*.4+.18), s=Math.sin(o.tilt*.4+.18);
    gl.uniform3fv(p.u.C, W(g)); gl.uniform3fv(p.u.X, [c, s, 0]); gl.uniform3fv(p.u.Y, [0, 0, 1]); gl.uniform1f(p.u.R, g.d/2); gl.uniform1f(p.u.a, o.fa); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4); });
  dis(p); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA); gl.depthMask(true);
}
/* an atmosphere's halo past the globe's edge, brightest on its sun's side (a quad facing the eye at the globe's centre: the globe hides its inner part) */
function halos(G){
  var p=P.h; gl.useProgram(p.p); gl.uniformMatrix4fv(p.u.VP, false, VPm); attr(p, 'q', P.q4, 2); gl.depthMask(false); gl.blendFunc(gl.ONE, gl.ONE);
  Object.keys(G.bodies).forEach(function(id){ var g=G.bodies[id], o=BOD[id], k=o && KD[o.kind]; if(!k || !k[1] || !(o.fa>.01)) return; var C=W(g), q=proj(C), R=g.d/2; if(!q || R*q.s<3) return;
    var vz=sub(EYE, C), Dc=Math.hypot(vz[0], vz[1], vz[2]); if(Dc<=R*1.01) return; vz=nrm(vz);
    var X=crs([0, 1, 0], vz); X=Math.hypot(X[0], X[1], X[2])<1e-3 ? [1, 0, 0] : nrm(X); var Y=crs(vz, X), s=sunOf(G, id);
    gl.uniform3fv(p.u.C, C); gl.uniform3fv(p.u.X, X); gl.uniform3fv(p.u.Y, Y); gl.uniform1f(p.u.S, R*Dc/Math.sqrt(Dc*Dc-R*R));
    gl.uniform3fv(p.u.L, s && s!==g ? nrm(sub(W(s), C)) : [0, 1, 0]); gl.uniform3fv(p.u.K, ATM[o.kind]); gl.uniform1f(p.u.a, k[1]*o.fa); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4); });
  dis(p); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA); gl.depthMask(true);
}
function glows(G){
  var p=P.g; gl.useProgram(p.p); gl.uniformMatrix4fv(p.u.VP, false, VPm); gl.uniform3fv(p.u.X, RT); gl.uniform3fv(p.u.Y, UP); attr(p, 'q', P.q, 2);
  gl.depthMask(false); gl.blendFunc(gl.ONE, gl.ONE);
  function put(g, K, S, a){ gl.uniform3fv(p.u.C, W(g)); gl.uniform3fv(p.u.K, K); gl.uniform1f(p.u.S, S); gl.uniform1f(p.u.a, a); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4); }
  /* a sun's bloom; a black hole's ring of light (its horizon hides the middle); a comet's coma; a satellite or station too small to see, a coloured glint */
  Object.keys(G.bodies).forEach(function(id){ var g=G.bodies[id], o=BOD[id]||{}, f=o.fa==null ? 1 : o.fa, q;
    if(o.kind==='blackhole'){ put(g, [1, .55, .25], g.d*1.5, .6*f); return; }
    if(o.kind==='comet'){ put(g, [.55, .8, 1], g.d*2.6, .35*f); return; }
    if(MK[o.kind] && (q=proj(W(g)))){ var rp=g.d/2*q.s; if(rp<8) put(g, o.kind==='sat' ? [1, .8, .45] : [.75, .85, 1], Math.max(g.d*.8, 7/q.s), .55*(1-sm(3, 8, rp))*f); return; }
    if(g.role!=='sun') return;
    if(FC && FC.id===id) f*=.4;                      /* (its own close-up: the bloom calmer, the sky not washed out) */
    put(g, [1, .72, .38], g.d*2.4, .55*f); put(g, [1, .72, .38], g.d*7, .16*f); });
  dis(p); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA); gl.depthMask(true);
}
/* the orbits (each in its unit's colour), the units' reach, the spokes; kept for picking as screen polylines */
function lines(G){
  var U={}; (G.units||[]).forEach(function(u){ U[u.si]=rgbOf(u.c); });
  var hot=hints.hot||{}, c=P.c; gl.useProgram(c.p); gl.uniformMatrix4fv(c.u.VP, false, VPm); attr(c, 'c', P.ci, 2); gl.enable(gl.DEPTH_TEST); gl.depthMask(false);
  LINES=[]; var seen={};
  Object.keys(G.bodies).forEach(function(id){ var g=G.bodies[id], pa=g.p && G.bodies[g.p]; if(!pa) return; var rr=Math.hypot(g.x-pa.x, g.y-pa.y), k=g.p+'|'+Math.round(rr/2), col=U[g.si]||[.62,.7,1];
    if(seen[k]){ seen[k].ids.push(id); return; }
    var a=g.role==='planet' ? .42 : .26; if(hot[id]) a=.9;
    gl.uniform3fv(c.u.C, W(pa)); gl.uniform1f(c.u.r, rr); gl.uniform4fv(c.u.K, [col[0]*.8+.2, col[1]*.8+.2, col[2]*.8+.2, a]); gl.drawArrays(gl.LINE_STRIP, 0, 129);
    var pts=[]; for(var i=0;i<=32;i++){ var w=i/32*Math.PI*2; pts.push(proj([pa.x+Math.cos(w)*rr, 0, pa.y+Math.sin(w)*rr])); }
    var L={id:id, ids:[id], pts:pts, line:1}; L.tip='Orbit of '+((BOD[g.p]||{}).name||''); seen[k]=L; LINES.push(L); });
  (G.units||[]).forEach(function(u){ var s=G.bodies[u.sun]; if(!s || !u.R) return; var col=U[u.si];
    gl.uniform3fv(c.u.C, W(s)); gl.uniform1f(c.u.r, u.R+40); gl.uniform4fv(c.u.K, [col[0], col[1], col[2], .5]); gl.drawArrays(gl.LINE_STRIP, 0, 129); });
  dis(c);
  var v=[], k=[], l=P.l; Object.keys(G.bodies).forEach(function(id){ var g=G.bodies[id], pa=g.p && G.bodies[g.p]; if(!pa) return; var h=hot[id] || hot[g.p] && window._focusedNodeId===id;
    v.push(pa.x, 0, pa.y, g.x, 0, g.y); var a=h ? .95 : .34; k.push(.75, .82, 1, a, .75, .82, 1, a);
    LINES.unshift({sp:[g.p, id], pts:[proj(W(pa)), proj(W(g))], line:1, tip:((BOD[g.p]||{}).name||'')+' — '+((BOD[id]||{}).name||'')}); });
  /* a flight's charted course ahead of the craft, faint (solar_fly.py's path: where the craft will be, so it leads a
     moving moon to where it will meet it), plainer as it sets off */
  var Fl=window._altoSolarFlight && window._altoSolarFlight(), pp=Fl && Fl.mode!=='jump' && Fl.path;      /* (a jump: no transit to show) */
  if(pp && pp.length>1){ var n=pp.length-1, i0=Math.max(0, Math.min(n, Math.floor(Fl.tau/Fl.D*n))), a0=.22+.33*(1-sm(0, .5, Fl.tau/Fl.D));
    for(var i=i0;i<n;i++){ var a1=a0*(1-.7*(i-i0)/Math.max(1, n-i0)); v.push(pp[i][0], K3.Y, pp[i][1], pp[i+1][0], K3.Y, pp[i+1][1]); k.push(.6, .88, 1, a1, .6, .88, 1, a1); } }
  gl.useProgram(l.p); gl.uniformMatrix4fv(l.u.VP, false, VPm);
  gl.bindBuffer(gl.ARRAY_BUFFER, P.lb); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(v.concat(k)), gl.DYNAMIC_DRAW);
  gl.enableVertexAttribArray(l.a.p); gl.vertexAttribPointer(l.a.p, 3, gl.FLOAT, false, 0, 0);
  gl.enableVertexAttribArray(l.a.k); gl.vertexAttribPointer(l.a.k, 4, gl.FLOAT, false, 0, v.length*4);
  gl.drawArrays(gl.LINES, 0, v.length/3); dis(l); gl.depthMask(true);
}
/* the names (bodies' under them, units' above their suns) and the hints, an HTML layer over the scene */
var NHD={n:['↑', 'Up a level'], s:['↓', 'Down a level'], w:['←', 'Previous'], e:['→', 'Next'], c:['•', 'Click to ride']},
  NHT={n:['↑', 'Up'], s:['↓', 'Down'], w:['⇧←', 'Sibling'], e:['⇧→', 'Sibling']};   /* the Tour's (solar_draw.py): siblings are Shift+arrow */
function hints(G){
  var f=window._focusedNodeId, out={}; hints.hot={};
  if(!f || !G.bodies[f] || !window._altoSolarLevelNav || (window._altoSolarFlight && window._altoSolarFlight())) return out;
  var NA=window._altoSolarNavApi; if(NA && document.documentElement.classList.contains('navx')){ NA.kids(f).forEach(function(to){ if(G.bodies[to]){ out[to]=['c']; hints.hot[to]=1; } }); return out; }   /* (the nav: what is beside it, by name, a click away: solar_navopt.py) */
  var Wy=window._altoSolarLock && window._altoSolarLock.ways ? window._altoSolarLock.ways(f) : null;     /* the Tour's named ways (solar_draw.py), in both modes */
  if(lk() && Wy){ window._altoSolarLock.spokes(f).forEach(function(to){ hints.hot[to]=1; }); return out; }   /* (Spokes only: solar_draw.py's arrows, the spokes lit) */
  if(Wy){ Wy.nb.forEach(function(to){ if(G.bodies[to]){ out[to]=[Wy.d[to]||'c']; hints.hot[to]=1; } }); return out; }
  ['n', 's', 'w', 'e'].forEach(function(d){ var to=window._altoSolarLevelNav(f, d); if(to && to!==f && G.bodies[to]){ (out[to]=out[to]||[]).push(d); hints.hot[to]=1; } });
  return out;
}
var PB=[], PI=[];
function labels(G, r){
  var z=zoomK(), H=hints(G), nb=0, ni=0, f=window._focusedNodeId;
  function b(cls){ var e=PB[nb]; if(!e){ e=PB[nb]=document.createElement('b'); lay.appendChild(e); } nb++; e.className=cls; e.style.display=''; return e; }
  function pill(id){ var e=PI[ni]; if(!e){ e=PI[ni]=document.createElement('i'); e.innerHTML='<kbd></kbd><em></em><span></span>'; lay.appendChild(e); } ni++; e.style.display='';
    e.setAttribute('data-go', id);
    e.children[0].textContent=H[id].map(function(d){ return (NHT[d] || NHD[d])[0]; }).join(''); e.children[1].textContent=NHT[H[id][0]] ? NHT[H[id][0]][1] : NHD[H[id][0]][1]; e.children[2].textContent=(BOD[id]||{}).name||''; return e; }
  function at(e, x, y){ e.style.left=((x-r.left)/z)+'px'; e.style.top=((y-r.top)/z)+'px'; }
  var BX=[], NM=[], PL=[];                       /* (the boxes taken: a name that would overlap one is left out, the bigger bodies' first) */
  function free(x, y, w, h){ if(BX.some(function(a){ return x<a[2] && x+w>a[0] && y<a[3] && y+h>a[1]; })) return false; BX.push([x, y, x+w, y+h]); return true; }
  (G.units||[]).forEach(function(u){ var s=G.bodies[u.sun], q=s && proj(W(s)); if(!q || u.sun===f) return; var ch=document.querySelector('.sol-unit[data-unit="'+u.unit+'"] span'); if(!ch) return;
    var e=b('u'), y=q.y-Math.max(30, s.d/2*q.s*1.9), w=ch.textContent.length*10+24; e.textContent=ch.textContent; e.style.setProperty('--u', u.c||'#9fb4ff'); at(e, q.x, y); free(q.x-w/2, y-24, w, 24); });   /* (none for the enlarged sun: it would sit on the title) */
  Object.keys(G.bodies).forEach(function(id){ var g=G.bodies[id], o=BOD[id], q=proj(W(g)); if(!o || id===f || (o.fa<.5 && !H[id])) return;     /* (a faded body's name goes, its hint stays) */
    var inside=q && q.x>r.left && q.x<r.right && q.y>r.top && q.y<r.bottom, rp=q ? g.d/2*q.s : 0;
    if(H[id]){ PL.push({id:id, q:q, rp:rp}); return; }     /* (the pills: laid out together below, clear of the disc, the bodies and each other) */
    if(!inside || rp<(g.role==='planet' ? 1.2 : g.role==='sun' ? .5 : 3)) return;
    NM.push({id:id, x:q.x, y:q.y+rp+4, rk:({sun:0, planet:1, moon:2}[g.role]||3)*1e4-rp, m:g.role!=='planet' && g.role!=='sun'}); });
  var PP=window._altoSolarPills, fc=f && document.getElementById('node-'+f), fr=fc && (fc.querySelector('.node-card')||fc).getBoundingClientRect();
  if(PL.length && PP){ var obs=[], WB=PP.bounds(); WB.x1=Math.min(WB.x1, r.right-16);
    Object.keys(G.bodies).forEach(function(id){ var g=G.bodies[id], o=BOD[id]; if(!o || id===f || o.fa<.5) return; var q=proj(W(g)), rp=q ? g.d/2*q.s : 0;
      if(q && rp>2 && q.x>r.left && q.x<r.right && q.y>r.top && q.y<r.bottom) obs.push({id:id, r:[q.x-rp-2, q.y-rp-2, q.x+rp+2, q.y+rp+2]}); });
    BX.forEach(function(a){ obs.push({id:'', r:a}); });
    var disc=fr && fr.width ? {x:fr.left+fr.width/2, y:fr.top+fr.height/2, r:fr.width/2+10} : {x:(r.left+r.right)/2, y:(r.top+r.bottom)/2, r:0};
    PP.lay(PL.map(function(p){ var e=pill(p.id); e.classList.add('pl'); var w=e.offsetWidth*z||140, h=e.offsetHeight*z||24, q=p.q || {x:disc.x, y:r.top};
      return {e:e, id:p.id, w:w, h:h, bx:q.x, by:q.y, rb:p.rp+4, rank:{n:0, w:1, e:1, s:2}[H[p.id][0]]==null ? 3 : {n:0, w:1, e:1, s:2}[H[p.id][0]]}; }), WB, disc, obs)
      .forEach(function(it){ var p=it.at || it.row; if(!p){ it.e.style.display='none'; return; } it.e.classList.toggle('rw', !!it.row); at(it.e, p[0], p[1]); BX.push([p[0], p[1], p[0]+it.w, p[1]+it.h]); }); }
  NM.sort(function(a, c){ return a.rk-c.rk; }).forEach(function(n){ var nm=BOD[n.id].name, w=nm.length*(n.m ? 5.6 : 6.6)+4; if(!free(n.x-w/2, n.y, w, n.m ? 13 : 15)) return;
    var e=b(n.m ? 'm' : ''); e.textContent=nm; at(e, n.x, n.y); });
  for(var i=nb;i<PB.length;i++) PB[i].style.display='none';
  for(i=ni;i<PI.length;i++) PI[i].style.display='none';
}
/* ── on / off ── */
function toggle(w){
  if(w && !ready){ ready=init(); if(!ready){ on=false; return; } }
  on=w && !!gl; de.classList.toggle('sk-3d', on);
  if(on){ var c=document.getElementById('canvas'); if(c && cv.parentNode!==c){ c.insertBefore(cv, c.firstChild); c.insertBefore(lay, cv.nextSibling); }
    foc=undefined; var G=geo(); if(G){ var h=home(G); cam.tx=h.x; cam.tz=h.z; cam.d=h.d*1.6; glide(G, false); }
    ctl(); }
  else { if(TIP) TIP.style.display='none'; }
}
/* Reset view (the button audit, 2026-10-25: it was in every style's bar and did nothing in the flat ones, nor in 3D until
   the view had been turned): only in 3D Star chart, only with the camera turned or zoomed by hand since the last reset or
   the last body enlarged, and not in Spokes only (no free camera there) */
var MOVED=0, MVF;
function ctl(){ var w=document.getElementById('sol-ctl'); if(!w) return; var b=document.getElementById('sk3d-reset');
  if(!b){ b=document.createElement('button'); b.type='button'; b.id='sk3d-reset'; b.className='sol-opt'; b.title='Back to the first view (or double-click on space)';
    b.innerHTML='<svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path d="M4 10a6 6 0 1 0 2-4.5M4 4v3.5h3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg><span>Reset view</span>';
    b.addEventListener('click', function(e){ e.stopPropagation(); reset(); ctl(); }); w.appendChild(b); }
  var f=window._focusedNodeId||null; if(f!==MVF){ MVF=f; if(f) MOVED=0; }   /* (a body enlarged: a fresh close-up; leaving one keeps the turned view) */
  var hide=!(on && MOVED && !lk()); if(b.hidden!==hide){ b.hidden=hide; de.style.setProperty('--sol-ctl-h', w.offsetHeight+'px'); } }
function kick(){ if(!raf) raf=requestAnimationFrame(frame); }
setInterval(function(){ ovWatch(); if(!raf && want()) kick(); else if(!want() && on) kick(); ctl(); }, 600); ovWatch();
if(typeof MutationObserver==='function') new MutationObserver(kick).observe(de, {attributes:true, attributeFilter:['class']});
window._altoSolar3D={on:function(){ return on; }, cam:function(){ return {tx:cam.tx, tz:cam.tz, d:cam.d, az:cam.az, el:cam.el}; }, eye:function(){ return EYE; }, set:function(o){ tw=null; for(var k in o) cam[k]=o[k]; },
  pick:function(x, y){ var h=pick(x, y); return h && h.id || null; }, ship:function(){ if(!SH.p || SH.al<=0) return null; var q=VPm ? proj([SH.p[0], 3, SH.p[1]]) : null; return {x:SH.p[0], y:SH.p[1], h:SH.hs, al:SH.al, craft:SH.cr, on:SH.on, sx:q && q.x, sy:q && q.y, lift:SH.y, e:SH.e, nose:SH.nose, vis:SH.fx ? SH.fx.vis : 1, warp:SH.fx ? SH.fx.warp : 0}; }, closeup:function(){ return {lock:LK && LK.id, moving:!!tw, ql:QL, ox:cam.ox, oy:cam.oy}; }, kinds:function(){ var o={}; Object.keys(BOD).forEach(function(id){ o[id]=BOD[id].kind; }); return o; }, fades:function(){ var o={}; Object.keys(BOD).forEach(function(id){ if(BOD[id].fa<.999) o[id]=Math.round(BOD[id].fa*100)/100; }); return o; }, project:function(id){ var G=geo(), g=G && G.bodies[id]; return g && VPm ? proj(W(g)) : null; }, reset:reset, textures:function(){ return Object.keys(BOD).filter(function(id){ return !!BOD[id].tex; }).length; }, fine:function(){ return Object.keys(BOD).filter(function(id){ return !!BOD[id].thi; }); }};
})();
"""

from .solar_draw import _slim  # noqa: E402  (comments and indents out, as the other System scripts)

SOLAR3D_JS = _slim(SOLAR3D_JS)
