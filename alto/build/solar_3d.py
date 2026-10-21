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
  #sk3d-reset{display:none;}
  html.sk-3d #sol-ctl #sk3d-reset{display:inline-flex;}
"""

SOLAR3D_JS = r"""
(function(){
'use strict';
var RC=null, de=document.documentElement, cv=null, lay=null, gl=null, P={}, ready=false, on=false, raf=0, BOD={}, sky=null;
var cam={tx:0, ty:0, tz:0, d:1600, az:-0.6, el:0.62, fov:0.82, ox:0, oy:0}, tw=null, LK=null, pre=null, QL=1, dtA=16, slow=0, lastT=0, TAU=Math.PI*2, foc=undefined, drag=null, VPm=null, EYE=[0, 0, 0], RT=[1, 0, 0], UP=[0, 1, 0];
var TYPES=['rocky', 'ocean', 'gas', 'ice', 'desert', 'lava'], ATM={rocky:[.55,.6,.7], ocean:[.4,.66,1], gas:[.95,.82,.6], ice:[.6,.88,1], desert:[1,.66,.45], lava:[1,.45,.2], moon:[0,0,0], sat:[0,0,0]};
/* each kind's shading: [type for the shader, atmosphere, cloud cover's threshold (1: none), cloud opacity] */
var KD={rocky:[0, .32, .6, .5], ocean:[1, 1, .53, .95], gas:[2, .55, 1, 0], ice:[3, .7, .62, .45], desert:[4, .55, .66, .35], lava:[5, .4, .68, .3], moon:[6, 0, 1, 0], sat:[7, 0, 1, 0], sun:[8, 0, 1, 0]};
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
var VS_B='attribute vec3 p;attribute vec2 t;uniform mat4 VP;uniform vec3 C,E,L;uniform float R,sp;varying vec3 N,V,Lv;varying vec2 T;'+
  'void main(){N=p;vec3 w=C+p*R;V=E-w;Lv=L-w;T=vec2(t.x+sp,t.y);gl_Position=VP*vec4(w,1.);}';
/* a globe: its painted surface (the macro look) and, by its size on screen (oc octaves, dl detail), the procedural rest */
var FS_B='precision highp float;varying vec3 N,V,Lv;varying vec2 T;uniform sampler2D tx,th,nz;uniform vec3 A,K;uniform vec2 sc,cc;'+
  'uniform float em,ht,hm,ty,oc,dl,ep,tm,at,cv,ca;'+
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
    'if(ty<5.5)return fb(r*5.,oc)*.6+rg(r*3.,oc)*.5;if(ty<6.5)return fb(r*5.,oc)*.6+cr(r*5.)+cr(r*13.)*.45;return 0.;}'+
  'float cl(vec3 q,float o){vec3 w=q*3.+vec3(fb(q*2.,3.),fb(q*2.+5.2,3.),fb(q*2.-3.7,3.))*1.6;return smoothstep(cv,cv+.24,fb(w,o)+.5);}'+
  'void main(){vec3 n=normalize(N),v=normalize(V),l=normalize(Lv),r=ry(n,sc);vec2 tt=T;'+
    'if(abs(ty-2.)<.5&&dl>0.){tt+=vec2(fb(r*vec3(2.5,10.,2.5)+vec3(tm*.004,0.,0.),oc)*.05,fb(r*vec3(4.,22.,4.)-vec3(0.,0.,tm*.006),oc)*.018)*dl;}'+
    'vec3 c=ht>.5?tx2(tt):K;'+
    'if(em>.5){float m=max(dot(n,v),0.),g=fb(r*18.+vec3(0.,tm*.01,0.),oc)+fb(r*48.-vec3(tm*.02),oc-1.)*.6;vec3 s=c*(.75+.6*m)+vec3(.25,.18,.05)*(1.-m);'+
      's=mix(s,c*(.6+.5*pow(m,.45))*mix(vec3(1.),vec3(1.,.62,.32),(1.-m)*.7),dl);s*=1.+g*.45*dl;gl_FragColor=vec4(s,1.);return;}'+
    'float wet=abs(ty-1.)<.5?smoothstep(.05,.25,c.b-max(c.r,c.g)):0.,lg=0.,ct=0.,g0=dot(n,l);vec3 nn=n;'+
    'if(dl>0.){float h=hg(r),bs=ty<.5?.9:ty<1.5?.6:ty<2.5?0.:ty<3.5?.5:ty<4.5?.55:ty<5.5?.6:ty<6.5?1.1:0.;vec3 d=c;'+
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
      'else d=c*(1.-.35*max(step(.93,fract(atan(r.z,r.x)*3.82)),step(.9,fract(r.y*12.))));'+
      'if(bs>0.){vec3 t1=normalize(cross(abs(n.y)<.99?vec3(0.,1.,0.):vec3(1.,0.,0.),n)),t2=cross(n,t1);'+
        'vec3 gr=((hg(r+ry(t1,sc)*ep)-h)*t1+(hg(r+ry(t2,sc)*ep)-h)*t2)/ep;nn=normalize(n-gr*bs*.04*dl);}'+
      'c=mix(c,d,dl);}'+
    'float cw=0.,cs=0.;if(ca>0.){float co=max(oc,3.);vec3 q=ry(n,cc);cw=cl(q,co)*ca;cs=cl(ry(normalize(n-l*.02),cc),co-2.)*ca;}'+
    'float gt=smoothstep(-.12,.2,g0),df=max(dot(nn,l),0.)*gt;vec3 tn=mix(vec3(1.),vec3(1.,.5,.3),at*(1.-smoothstep(0.,.4,g0))*.8),hv=normalize(l+v);'+
    'float sp2=pow(max(dot(nn,hv),0.),90.)*wet*1.3+pow(max(dot(nn,hv),0.),24.)*(abs(ty-3.)<.5?.25:.04);'+
    'vec3 o=c*(.022+1.12*df*tn)*(1.-cs*.55*gt)+vec3(1.,.95,.86)*sp2*gt*(1.-cw);'+
    'o+=vec3(1.,.42,.1)*lg*dl*(1.15-gt*.6)+vec3(1.,.75,.4)*ct*dl*.85*(1.-smoothstep(-.2,.05,g0))*(1.-cw);'+
    'vec3 ck=ty>3.5&&ty<4.5?vec3(.9,.76,.6):ty>4.5&&ty<5.5?vec3(.34,.31,.3):vec3(.97,.98,1.);o=mix(o,ck*(.02+1.05*max(g0,0.)*gt)*tn,cw);'+
    'float fr=pow(1.-max(dot(n,v),0.),2.4);o+=A*fr*at*(.06+1.1*smoothstep(-.25,.6,g0));gl_FragColor=vec4(o,1.);}';
var VS_G='attribute vec2 q;uniform mat4 VP;uniform vec3 C,X,Y;uniform float S;varying vec2 Q;void main(){Q=q;gl_Position=VP*vec4(C+(X*q.x+Y*q.y)*S,1.);}';
var FS_G='precision mediump float;varying vec2 Q;uniform vec3 K;uniform float a;void main(){float r=length(Q);if(r>1.)discard;float g=pow(1.-r,2.4);gl_FragColor=vec4(K*g*a,g*a);}';
var FS_H='precision highp float;varying vec2 Q;uniform vec3 K,X,Y,L;uniform float a;void main(){float r=length(Q);if(r<.97||r>1.3)discard;'+
  'float g=r<1.?smoothstep(.97,1.,r):exp(-(r-1.)*24.);float k=g*smoothstep(-.45,.65,dot(normalize(X*Q.x+Y*Q.y),L))*a*.9;gl_FragColor=vec4(K*k,k*.6);}';
var VS_R='attribute vec2 q;uniform mat4 VP;uniform vec3 C,X,Y;uniform float R;varying vec2 Q;void main(){Q=q;gl_Position=VP*vec4(C+(X*q.x+Y*q.y)*R,1.);}';
var FS_R='precision mediump float;varying vec2 Q;uniform vec3 K;void main(){float r=length(Q);if(r<1.35||r>2.3)discard;float b=.55+.45*sin(r*38.)*sin(r*11.);'+
  'float e=smoothstep(1.35,1.45,r)*smoothstep(2.3,2.18,r);gl_FragColor=vec4(K*b,.6*e*(abs(r-1.9)<.04?.25:1.));}';
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
  if(!hp || !hp.precision){ FS_B=FS_B.replace('highp', 'mediump'); FS_H=FS_H.replace('highp', 'mediump'); QL=0; }   /* (no highp: no procedural detail) */
  try{ P.h=sh(VS_G, FS_H); P.b=sh(VS_B, FS_B); P.g=sh(VS_G, FS_G); P.r=sh(VS_R, FS_R); P.l=sh(VS_L, FS_L); P.c=sh(VS_C, FS_C); P.s=sh(VS_S, FS_S); }catch(e){ if(window.console) console.warn('3d', e); gl=null; return false; }
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
  var R=mkR(7), sp=[], sz=[]; for(i=0;i<2600;i++){ var u=R()*2-1, ph=R()*Math.PI*2, s=Math.sqrt(1-u*u); sp.push(s*Math.cos(ph), u, s*Math.sin(ph)); sz.push(Math.pow(R(), 6)); }
  P.sp=buf(sp); P.sz=buf(sz); P.sn2=sz.length;
  P.lb=gl.createBuffer();
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
  var per={}, ids=Object.keys(G.bodies);
  ids.forEach(function(id){ var g=G.bodies[id], o=BOD[id]; if(o) return;
    var n=document.getElementById('node-'+id), lb=n && n.querySelector('.sol-lbl'), kind;
    if(g.role==='sun') kind='sun'; else if(g.role==='moon') kind='moon'; else if(g.role==='sat') kind='sat';
    else { var k=(per[g.p]=(per[g.p]||0)+1)-1; kind=TYPES[(k+(g.si||0)*2)%TYPES.length]; }
    var R=mkR(hsh(id+'#3d'));
    BOD[id]={id:id, kind:kind, name:(lb && lb.getAttribute('data-l')) || (n && n.getAttribute('data-title')) || '', tex:null, ty:0,
      spin:(kind==='gas' ? 40 : kind==='moon' ? 160 : 70)*(.7+R()*.7), ph:R(), ring:kind==='gas' && R()<.6, tilt:(R()-.5)*.9}; });
}
function texJob(o, W, H, inc){                      /* a surface painted a few rows a frame: job(deadline) -> its texture once done */
  var pa=window._altoSkPaint(o.kind, o.id, {nc:1}), D=new Uint8Array(W*H*4), y=0, t=null;
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
  if(o.kind==='sun' || o.kind==='sat') return true;
  if(!o.job) o.job=texJob(o, 256, 128, false);
  var t=o.job(dl); if(!t) return false; o.tex=t; o.job=null; return true;
}
/* the enlarged body's finer surface (and the last two kept): painted first, faded in over half a second */
var HI=[];
function hiStep(id, dl){ var o=BOD[id]; if(!o || !o.tex || o.kind==='sun' || o.kind==='sat' || o.thi) return;
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
function reset(){ var G=geo(); if(!G) return;
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
  var F=r.height/2/Math.tan(cam.fov/2), s=sunOf(G, id), L=LK||{side:1, da:0, de:0}, az=(L.az0!=null ? L.az0 : cam.az)+L.da;
  if(s && s!==g) az=Math.atan2(s.x-g.x, s.y-g.y)+L.side*1.05+L.da;
  return {x:g.x, z:g.y, d:R*Math.sqrt(1+(F/rp)*(F/rp)), az:az, el:Math.max(-1.2, Math.min(1.35, (g.role==='sun' ? .45 : .3)+L.de)),
    ox:(cx-(r.left+r.width/2))/(r.width/2), oy:-(cy-(r.top+r.height/2))/(r.height/2)};
}
/* the focus moved: dive in (from where the camera was, kept to fly back to), hop across (pulling back on the way), or fly back out */
function focus(G, a, b){
  var t=performance.now(), A=snap(); if(!a && !b) return;
  if(b){ if(!a) pre=tw && tw.b ? tw.b : A;
    var g=G.bodies[b], s=sunOf(G, b), side=1;
    if(s && s!==g){ var sa=Math.atan2(s.x-g.x, s.y-g.y); side=Math.abs(wrap(cam.az-sa-1.05))<=Math.abs(wrap(cam.az-sa+1.05)) ? 1 : -1; }
    LK={id:b, side:side, da:0, de:0, az0:cam.az};
    var tr=Math.hypot(g.x-A.x, g.y-A.z), nb=document.getElementById('node-'+b); if(nb) nb.style.setProperty('--s3o', '0');
    tw={t0:t, a:A, lock:b, leave:a, ms:a ? 1000 : 1150, hop:a ? Math.min(1.2, Math.max(0, tr/Math.max(A.d, 1)*.45-.1)) : 0}; }
  else { LK=null; tw={t0:t, a:A, b:pre || {x:A.x, z:A.z, d:A.d*6, az:A.az, el:.62, ox:0, oy:0}, leave:a, ms:950, hop:0}; pre=null; }
}
function blend(A, B, p, hop){ var e=mj(p), et=mj(Math.min(1, p*1.35));             /* (the aim leads the zoom: the body comes to its place, then near) */
  cam.tx=A.x+(B.x-A.x)*et; cam.tz=A.z+(B.z-A.z)*et; cam.d=Math.exp(Math.log(A.d)+(Math.log(B.d)-Math.log(A.d))*e)*(1+hop*Math.sin(Math.PI*e));
  cam.az=A.az+wrap(B.az-A.az)*e; cam.el=A.el+(B.el-A.el)*e; cam.ox=A.ox+(B.ox-A.ox)*e; cam.oy=A.oy+(B.oy-A.oy)*e; }
/* ── input: drag turns, wheel / pinch nears, a click picks ── */
function down(e){ if(e.button) return; drag={x:e.clientX, y:e.clientY, az:cam.az, el:cam.el, da:LK ? LK.da : 0, de:LK ? LK.de : 0, m:false, id:e.pointerId}; try{ cv.setPointerCapture(e.pointerId); }catch(x){} }
function move(e){
  if(drag && e.pointerId===drag.id){ var dx=e.clientX-drag.x, dy=e.clientY-drag.y; if(!drag.m && Math.abs(dx)+Math.abs(dy)<4) return;
    drag.m=true; if(lk()) return;                 /* Spokes only: no free camera (a drag turns nothing) */
    cv.classList.add('drag');
    if(LK && foc){ var a0=LK.da, e0=LK.de; LK.da=drag.da-dx*.006; LK.de=Math.max(-1.5, Math.min(1.05, drag.de+dy*.006));
      if(!tw){ cam.az+=LK.da-a0; cam.el+=LK.de-e0; } return; }   /* (close up: the camera turns about the globe, at once) */
    tw=null; cam.az=drag.az-dx*.006; cam.el=Math.max(-1.45, Math.min(1.45, drag.el+dy*.006)); return; }
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
  tw=null;
  cam.d=Math.max(60, Math.min(60000, cam.d*Math.exp(dy*(e.ctrlKey ? .012 : .0025))));
  if(!e.ctrlKey) cam.az-=dx*.004;
}
/* what is under the pointer: a body (its projected disc, at least 10px), else a spoke, else an orbit (6px) */
var LINES=[];
function pick(x, y){
  var G=geo(); if(!G || !VPm) return null; var best=null, bd=Infinity;
  Object.keys(G.bodies).forEach(function(id){ var g=G.bodies[id], q=proj(W(g)); if(!q) return; var r=Math.max(10, g.d/2*q.s), d=Math.hypot(q.x-x, q.y-y);
    if(d<r && q.w<bd){ bd=q.w; best={id:id}; } });
  if(best) return best;
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
  if(f!==foc){ focus(G, foc, f); foc=f; }
  pace(now);
  size(); RC=null;
  var r=RC=cv.getBoundingClientRect(), asp=r.width/Math.max(1, r.height), nf=f && document.getElementById('node-'+f);
  if(tw){ var p=Math.min(1, (now-tw.t0)/tw.ms); blend(tw.a, tw.lock ? cin(G, tw.lock, r) : tw.b, p, tw.hop);
    if(nf && tw.lock===f) nf.style.setProperty('--s3o', String(Math.round(sm(.72, 1, p)*1000)/1000));
    var nl=tw.leave && document.getElementById('node-'+tw.leave); if(nl){ if(p>=1) nl.style.removeProperty('--s3o'); else nl.style.setProperty('--s3o', String(Math.round((1-sm(0, .2, p))*1000)/1000)); }
    if(p>=1) tw=null; }
  else if(f && LK){ var B=cin(G, f, r); cam.tx=B.x; cam.tz=B.z; cam.d=B.d; cam.az=B.az; cam.el=B.el; cam.ox=B.ox; cam.oy=B.oy; if(nf) nf.style.setProperty('--s3o', '1'); }   /* (held on the disc, round its orbit) */
  EYE=[cam.tx+cam.d*Math.cos(cam.el)*Math.sin(cam.az), cam.d*Math.sin(cam.el), cam.tz+cam.d*Math.cos(cam.el)*Math.cos(cam.az)];
  var V=look(EYE, [cam.tx, 0, cam.tz], [0, 1, 0]); VPm=mul(persp(cam.fov, asp, Math.max(2, cam.d/400), 200000), V);
  for(var k=0;k<4;k++){ VPm[k*4]+=cam.ox*VPm[k*4+3]; VPm[k*4+1]+=cam.oy*VPm[k*4+3]; }         /* (the lens shifted: the aim drawn where the disc is) */
  gl.viewport(0, 0, cv.width, cv.height); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
  gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
  stars(); lines(G); spheres(G); halos(G); glows(G); labels(G, r);
  var dl=performance.now()+3; if(foc && (!tw || now-tw.t0>300)) hiStep(foc, performance.now()+3);      /* (not in the dive's first, busiest frames) */
  Object.keys(BOD).sort(function(a, b){ return dist(G, a)-dist(G, b); }).some(function(id){ var o=BOD[id]; if(o.tex || o.kind==='sun' || o.kind==='sat') return false; texStep(o, dl); return performance.now()>=dl; });
  raf=requestAnimationFrame(frame);
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
function spheres(G){
  var p=P.b, M0=null; gl.useProgram(p.p); gl.enable(gl.DEPTH_TEST); gl.depthMask(true); gl.disable(gl.BLEND);
  gl.uniformMatrix4fv(p.u.VP, false, VPm); gl.uniform3fv(p.u.E, EYE);
  gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, P.nz); gl.uniform1i(p.u.nz, 1);
  var now=performance.now()/1000; gl.uniform1f(p.u.tm, now%2000);
  Object.keys(G.bodies).forEach(function(id){ var g=G.bodies[id], o=BOD[id]; if(!o) return; var s=sunOf(G, id), q=proj(W(g)), rp=q ? g.d/2*q.s : 0; if(q && rp<.4) return;
    var M=rp>40 ? P.hi : P.lo; if(M!==M0){ M0=M; attr(p, 'p', M.v, 3); attr(p, 't', M.t, 2); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, M.i); }
    var a=(now/o.spin+o.ph)%1, w=a*TAU, wc=w*1.18+now*.004, k=KD[o.kind]||KD.rocky, rd=rp*(cv.width/Math.max(1, RC.width)), oc=QL ? Math.max(0, Math.min(7, 1+Math.log2(Math.max(1, rd)/20)))*QL : 0;
    gl.uniform3fv(p.u.C, W(g)); gl.uniform1f(p.u.R, g.d/2); gl.uniform1f(p.u.sp, a); gl.uniform2f(p.u.sc, Math.cos(w), Math.sin(w)); gl.uniform2f(p.u.cc, Math.cos(wc), Math.sin(wc));
    gl.uniform1f(p.u.oc, oc); gl.uniform1f(p.u.dl, QL ? sm(22, 120, rp) : 0); gl.uniform1f(p.u.ep, Math.max(.0006, .45/(5*Math.pow(2, oc))));
    gl.uniform1f(p.u.ty, k[0]); gl.uniform1f(p.u.at, k[1]); gl.uniform1f(p.u.cv, k[2]); gl.uniform1f(p.u.ca, QL ? k[3] : 0);
    gl.uniform3fv(p.u.L, s ? W(s) : [0, 900, 0]); gl.uniform1f(p.u.em, o.kind==='sun' ? 1 : 0);
    gl.uniform3fv(p.u.A, ATM[o.kind] || [0, 0, 0]);
    gl.uniform3fv(p.u.K, o.kind==='sun' ? [1, .78, .36] : o.kind==='sat' ? [.72, .74, .8] : [.45, .45, .5]);
    if(o.tex){ gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, o.tex); gl.uniform1i(p.u.tx, 0); gl.uniform1f(p.u.ht, 1); } else gl.uniform1f(p.u.ht, 0);
    var hm=o.thi ? sm(0, 500, performance.now()-o.h0)*sm(30, 70, rp) : 0;            /* (no mipmaps: only while the body is big) */ gl.uniform1f(p.u.hm, hm);
    gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_2D, o.thi || o.tex || P.nz); gl.uniform1i(p.u.th, 2);
    gl.drawElements(gl.TRIANGLES, M.n, gl.UNSIGNED_SHORT, 0); });
  dis(p); gl.enable(gl.BLEND);
  /* rings round some gas giants, tilted, lit flat by their sun */
  var r=P.r; gl.useProgram(r.p); gl.uniformMatrix4fv(r.u.VP, false, VPm); attr(r, 'q', P.q3, 2); gl.depthMask(false);
  Object.keys(BOD).forEach(function(id){ var o=BOD[id], g=G.bodies[id]; if(!o.ring || !g) return; var c=Math.cos(o.tilt), s=Math.sin(o.tilt);
    gl.uniform3fv(r.u.C, W(g)); gl.uniform3fv(r.u.X, [c, s, 0]); gl.uniform3fv(r.u.Y, [0, 0, 1]); gl.uniform1f(r.u.R, g.d/2); gl.uniform3fv(r.u.K, [.86, .78, .62]);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4); });
  dis(r); gl.depthMask(true);
}
/* an atmosphere's halo past the globe's edge, brightest on its sun's side (a quad facing the eye at the globe's centre: the globe hides its inner part) */
function halos(G){
  var p=P.h; gl.useProgram(p.p); gl.uniformMatrix4fv(p.u.VP, false, VPm); attr(p, 'q', P.q4, 2); gl.depthMask(false); gl.blendFunc(gl.ONE, gl.ONE);
  Object.keys(G.bodies).forEach(function(id){ var g=G.bodies[id], o=BOD[id], k=o && KD[o.kind]; if(!k || !k[1]) return; var C=W(g), q=proj(C), R=g.d/2; if(!q || R*q.s<3) return;
    var vz=sub(EYE, C), Dc=Math.hypot(vz[0], vz[1], vz[2]); if(Dc<=R*1.01) return; vz=nrm(vz);
    var X=crs([0, 1, 0], vz); X=Math.hypot(X[0], X[1], X[2])<1e-3 ? [1, 0, 0] : nrm(X); var Y=crs(vz, X), s=sunOf(G, id);
    gl.uniform3fv(p.u.C, C); gl.uniform3fv(p.u.X, X); gl.uniform3fv(p.u.Y, Y); gl.uniform1f(p.u.S, R*Dc/Math.sqrt(Dc*Dc-R*R));
    gl.uniform3fv(p.u.L, s && s!==g ? nrm(sub(W(s), C)) : [0, 1, 0]); gl.uniform3fv(p.u.K, ATM[o.kind]); gl.uniform1f(p.u.a, k[1]); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4); });
  dis(p); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA); gl.depthMask(true);
}
function glows(G){
  var p=P.g; gl.useProgram(p.p); gl.uniformMatrix4fv(p.u.VP, false, VPm); gl.uniform3fv(p.u.X, RT); gl.uniform3fv(p.u.Y, UP); attr(p, 'q', P.q, 2);
  gl.depthMask(false); gl.blendFunc(gl.ONE, gl.ONE);
  Object.keys(G.bodies).forEach(function(id){ var g=G.bodies[id]; if(g.role!=='sun') return;
    gl.uniform3fv(p.u.C, W(g)); gl.uniform3fv(p.u.K, [1, .72, .38]);
    gl.uniform1f(p.u.S, g.d*2.4); gl.uniform1f(p.u.a, .55); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    gl.uniform1f(p.u.S, g.d*7); gl.uniform1f(p.u.a, .16); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4); });
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
  gl.useProgram(l.p); gl.uniformMatrix4fv(l.u.VP, false, VPm);
  gl.bindBuffer(gl.ARRAY_BUFFER, P.lb); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(v.concat(k)), gl.DYNAMIC_DRAW);
  gl.enableVertexAttribArray(l.a.p); gl.vertexAttribPointer(l.a.p, 3, gl.FLOAT, false, 0, 0);
  gl.enableVertexAttribArray(l.a.k); gl.vertexAttribPointer(l.a.k, 4, gl.FLOAT, false, 0, v.length*4);
  gl.drawArrays(gl.LINES, 0, v.length/3); dis(l); gl.depthMask(true);
}
/* the names (bodies' under them, units' above their suns) and the hints, an HTML layer over the scene */
var NHD={n:['↑', 'Up a level'], s:['↓', 'Down a level'], w:['←', 'Previous'], e:['→', 'Next'], c:['•', 'Click to ride']};
function hints(G){
  var f=window._focusedNodeId, out={}; hints.hot={};
  if(!f || !G.bodies[f] || !window._altoSolarLevelNav || (window._altoSolarFlight && window._altoSolarFlight())) return out;
  var Wy=lk() && window._altoSolarLock.ways ? window._altoSolarLock.ways(f) : null;     /* Spokes only: every body one spoke away, and only those */
  if(Wy){ Wy.nb.forEach(function(to){ if(G.bodies[to]){ out[to]=[Wy.d[to]||'c']; hints.hot[to]=1; } }); return out; }
  ['n', 's', 'w', 'e'].forEach(function(d){ var to=window._altoSolarLevelNav(f, d); if(to && to!==f && G.bodies[to]){ (out[to]=out[to]||[]).push(d); hints.hot[to]=1; } });
  return out;
}
var PB=[], PI=[];
function labels(G, r){
  var z=zoomK(), H=hints(G), nb=0, ni=0, f=window._focusedNodeId;
  function b(cls){ var e=PB[nb]; if(!e){ e=PB[nb]=document.createElement('b'); lay.appendChild(e); } nb++; e.className=cls; e.style.display=''; return e; }
  function pill(id){ var e=PI[ni]; if(!e){ e=PI[ni]=document.createElement('i'); e.innerHTML='<kbd></kbd><em></em><span></span>'; lay.appendChild(e); } ni++; e.style.display='';
    e.children[0].textContent=H[id].map(function(d){ return NHD[d][0]; }).join(''); e.children[1].textContent=(lk() && H[id][0]!=='c') ? 'Ride' : NHD[H[id][0]][1]; e.children[2].textContent=(BOD[id]||{}).name||''; return e; }
  function at(e, x, y){ e.style.left=((x-r.left)/z)+'px'; e.style.top=((y-r.top)/z)+'px'; }
  (G.units||[]).forEach(function(u){ var s=G.bodies[u.sun], q=s && proj(W(s)); if(!q) return; var ch=document.querySelector('.sol-unit[data-unit="'+u.unit+'"] span'); if(!ch) return;
    var e=b('u'); e.textContent=ch.textContent; e.style.setProperty('--u', u.c||'#9fb4ff'); at(e, q.x, q.y-Math.max(30, s.d/2*q.s*1.9)); });
  Object.keys(G.bodies).forEach(function(id){ var g=G.bodies[id], o=BOD[id], q=proj(W(g)); if(!o || id===f) return;
    var inside=q && q.x>r.left && q.x<r.right && q.y>r.top && q.y<r.bottom, rp=q ? g.d/2*q.s : 0;
    if(H[id]){ if(inside){ at(pill(id), q.x, q.y-rp-6); return; }
      /* a hint whose body is off the window: the pill at the edge, on the line towards it */
      /* (clear of the bars above, where the board runs under them, and of the controls below) */
      var T0=r.top+130, B0=r.bottom-80, cx=r.left+r.width/2, cy=(T0+B0)/2, x=q ? q.x : cx, y=q ? q.y : T0, dx=x-cx, dy=y-cy,
        k=Math.min((r.width/2-110)/Math.max(1, Math.abs(dx)), ((B0-T0)/2)/Math.max(1, Math.abs(dy)), 1);
      at(pill(id), cx+dx*k, cy+dy*k+12); return; }
    if(!inside || rp<(g.role==='planet' ? 1.2 : g.role==='sun' ? .5 : 3)) return;
    var e=b(g.role==='planet' || g.role==='sun' ? '' : 'm'); e.textContent=o.name; at(e, q.x, q.y+rp+4); });
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
function ctl(){ var w=document.getElementById('sol-ctl'); if(!w || document.getElementById('sk3d-reset')) return;
  var b=document.createElement('button'); b.type='button'; b.id='sk3d-reset'; b.className='sol-opt'; b.title='Back to the first view (or double-click on space)';
  b.innerHTML='<svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path d="M4 10a6 6 0 1 0 2-4.5M4 4v3.5h3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg><span>Reset view</span>';
  b.addEventListener('click', function(e){ e.stopPropagation(); reset(); }); w.appendChild(b); }
function kick(){ if(!raf) raf=requestAnimationFrame(frame); }
setInterval(function(){ if(!raf && want()) kick(); else if(!want() && on) kick(); ctl(); }, 600);
if(typeof MutationObserver==='function') new MutationObserver(kick).observe(de, {attributes:true, attributeFilter:['class']});
window._altoSolar3D={on:function(){ return on; }, cam:function(){ return {tx:cam.tx, tz:cam.tz, d:cam.d, az:cam.az, el:cam.el}; }, set:function(o){ tw=null; for(var k in o) cam[k]=o[k]; },
  closeup:function(){ return {lock:LK && LK.id, moving:!!tw, ql:QL, ox:cam.ox, oy:cam.oy}; }, kinds:function(){ var o={}; Object.keys(BOD).forEach(function(id){ o[id]=BOD[id].kind; }); return o; }, project:function(id){ var G=geo(), g=G && G.bodies[id]; return g && VPm ? proj(W(g)) : null; }, reset:reset, textures:function(){ return Object.keys(BOD).filter(function(id){ return !!BOD[id].tex; }).length; }, fine:function(){ return Object.keys(BOD).filter(function(id){ return !!BOD[id].thi; }); }};
})();
"""

from .solar_draw import _slim  # noqa: E402  (comments and indents out, as the other System scripts)

SOLAR3D_JS = _slim(SOLAR3D_JS)
