"""The Building Palace's first-person view (phase 2): /bldg/palace-building-fpv-<hash>.js, a hosted, standalone interior renderer for ANY plan in
the building_schema format. It registers itself with the blueprint through `AltoBuilding.registerFPV({enter, exit})`; the blueprint
(palace_building_asset.py) fetches this script the first time someone walks in, so the page itself carries nothing for it.

Nothing here is shared with the city ride's closure (palace_ride_*); ideas were ported, not code coupled: the quality tiers and the resolution
governor (palace_ride_gfx.py), the WebKit-safe MSAA resolve (a multisampled target resolved into a plain RGBA8 target, then a plain blit to the
alpha-less canvas), human scale and the Street-View drag (palace_ride_e.py / palace_ride_inside.py).

What it builds from the plan (all in metres, x east, y north, z up)
  walls      every polyline with its real thickness: mitred faces, door / arch / gap / gate / window openings cut through with jambs, heads, arched
             soffits, sills and thresholds; casings round doors and arches, skirting, picture rails and a cornice cove on room faces; window frames
             (mullion, transom) and glass; door leaves standing open; rails as metal balustrades or stone parapets. Each face is split where the room
             it faces changes, so it is lit and culled with that room.
  rooms      floor and ceiling per room (holes cut where a stair rises through), laylights for glass ceilings, slab edges over voids
  stairs     flights (treads, risers, soffit, sawtooth stringers, stone parapets with brass handrails) and landings, walkable with the eye following
             the pitch line; balustrades round the stairwell above; ramps, escalators; lifts as shafts with bronze doors (E rides them)
  columns    fluted round shafts with base and capital, square piers;  fixtures  case (vitrine with its object), plinth, bench, table, desk,
             shelf, fountain, statue (a proportionate figure), counter, stove
  art slots  frame (gilt for paintings, slim dark wood with a mat and glazing for works on paper), contact shadow, label plate, a spot light
             aimed at each; sculpture slots stand on plinths
  outside    the shell above the walls with a cornice and its roof (flat / hip / gable / dome / vault), steps, terraces, paving, sky
Lighting is per room (uniform arrays per draw): art spots and wall washers (warm), window daylight as area lights with sun patches cast through
the window rectangles (mullion and transom shadows), laylights, a hemisphere bounce tinted by the floor, analytic contact AO (wall-floor,
corners, room edges, column and fixture footprints), haze, filmic tone curve with eye adaptation, vignette and dither.
The graphics pass (fpv_gfx.py, per tier in FX): soft sun shadows (Poisson / blocker-sized penumbra), half-size SSAO and bloom after the MSAA
resolve, the HDRI sky as background, outdoor SH irradiance and reflections, and photographed CC0 material sets (KTX2) faded in over the
procedural ones (REAL); the light shafts step aside when the pass is on (the two together crash WebKit's Metal shader compiler).
Materials are procedural tileable textures rendered on the GPU at start (albedo+roughness, normal+height+cavity, mip-mapped): marble, limestone
ashlar, granite, brick, plaster, eggshell paint, wood panelling, floorboards, chevron parquet, tile, terrazzo, concrete, carpet, brushed metal,
leather, paving, roof tile.

Optional plan field read here (ignored by the validator): an art slot may carry  work: {t: title, a: artist, d: date, img: image URL,
lic: licence}. The image is only fetched when `lic` says public domain / CC0 (Luke's rule: real images only for clearly public-domain works);
otherwise the frame holds a quiet painted placeholder and the label plate carries the title.

Runtime seams: window.AltoBuildingFPV = {enter(roomId, ctx), exit(), state(), place(x, y, z, yaw, pitch), step(dt, keys), settle(), stats(),
geom: {wallPieces, support, blocked, flightZ}, tier}. Events on window: 'alto-building-fpv-pos' {l, x, y, yaw, room} while walking and
'alto-building-fpv-exit' (same detail) on leaving; the blueprint draws the walker on the plan from them.
"""
from __future__ import annotations

import hashlib as _hashlib
import json as _json

from .fpv_gfx import IBL_GLSL as _IBL_GLSL, gfx_js as _gfx_js

FPV_CSS = r"""
#bf-root{position:fixed;inset:0;z-index:2147483000;background:#0c0c0d;overflow:hidden;touch-action:none;user-select:none;-webkit-user-select:none;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#fff;}
#bf-root canvas{position:absolute;left:0;top:0;width:100%;height:100%;display:block;cursor:grab;touch-action:none;}
#bf-root.bf-drag canvas{cursor:grabbing;}
#bf-root .bf-ret{position:absolute;left:50%;top:50%;width:6px;height:6px;margin:-3px 0 0 -3px;border-radius:50%;background:rgba(255,255,255,.8);
  box-shadow:0 0 0 1px rgba(0,0,0,.3);pointer-events:none;transition:transform .15s;}
#bf-root .bf-ret.on{transform:scale(2.3);}
#bf-root .bf-pill{position:absolute;padding:7px 13px;border-radius:17px;background:rgba(20,20,24,.6);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
  border:1px solid rgba(255,255,255,.16);font-size:13px;line-height:1.3;}
#bf-root .bf-pick{left:50%;top:calc(50% + 20px);transform:translateX(-50%);max-width:min(78vw,520px);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  opacity:0;transition:opacity .2s;cursor:pointer;}
#bf-root .bf-pick.on{opacity:1;}
#bf-root kbd{font:600 11px ui-monospace,Menlo,monospace;padding:1px 5px;border-radius:4px;border:1px solid rgba(255,255,255,.55);margin-right:7px;}
#bf-root .bf-toast{left:50%;top:18px;transform:translateX(-50%);text-align:center;font-size:15px;font-weight:600;opacity:0;transition:opacity .7s;pointer-events:none;
  max-width:70vw;padding:9px 18px;}
#bf-root .bf-toast span{display:block;font-size:12px;font-weight:400;opacity:.8;margin-top:2px;}
#bf-root .bf-toast.on{opacity:1;}
#bf-root .bf-lv{position:absolute;right:14px;top:50%;transform:translateY(-50%);display:flex;flex-direction:column-reverse;gap:6px;}
#bf-root .bf-cardsbtn{position:absolute;left:14px;top:58px;height:32px;padding:0 14px;border-radius:16px;border:0;background:rgba(20,20,24,.62);color:#fff;font:600 13px -apple-system,Helvetica,Arial,sans-serif;cursor:pointer;-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);}
#bf-root .bf-cards{position:absolute;left:14px;top:98px;bottom:70px;width:min(340px,calc(100% - 28px));display:flex;flex-direction:column;background:rgba(20,20,24,.82);color:#f2f0ec;border-radius:14px;overflow:hidden;font:13px -apple-system,Helvetica,Arial,sans-serif;-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);}
#bf-root .bf-cards input{margin:10px;padding:8px 10px;border-radius:9px;border:1px solid rgba(255,255,255,.2);background:rgba(255,255,255,.08);color:#fff;font:inherit;outline:none;}
#bf-root .bf-clist{overflow:auto;padding:0 6px 8px;}
#bf-root .bf-clist button{display:flex;align-items:center;gap:8px;width:100%;text-align:left;padding:7px 8px;margin:1px 0;border:0;border-radius:8px;background:transparent;color:inherit;font:inherit;cursor:pointer;}
#bf-root .bf-clist button:hover{background:rgba(255,255,255,.12);}
#bf-root .bf-clist i{flex:0 0 8px;height:22px;border-radius:4px;background:#7c5cff;}
#bf-root .bf-clist b{flex:0 0 auto;min-width:30px;color:#cfc8ff;}
#bf-root .bf-lv button,#bf-root .bf-exit{font:inherit;font-size:12px;min-width:34px;height:30px;padding:0 10px;border-radius:15px;color:#fff;cursor:pointer;
  border:1px solid rgba(255,255,255,.22);background:rgba(20,20,24,.5);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);}
#bf-root .bf-lv button.on{border-color:#fff;font-weight:700;background:rgba(255,255,255,.22);}
#bf-root .bf-exit{position:absolute;left:14px;top:14px;height:32px;font-size:13px;padding:0 14px;}
#bf-root .bf-hint{left:50%;bottom:14px;transform:translateX(-50%);font-size:12px;opacity:.78;white-space:nowrap;pointer-events:none;transition:opacity 1.2s;}
#bf-root .bf-veil{position:absolute;inset:0;background:#0c0c0d;opacity:1;transition:opacity .5s;pointer-events:none;display:flex;align-items:center;justify-content:center;
  font-size:14px;color:rgba(255,255,255,.7);}
#bf-root .bf-joy{position:absolute;bottom:26px;width:116px;height:116px;border-radius:50%;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.22);display:none;}
#bf-root .bf-joy i{position:absolute;left:50%;top:50%;width:46px;height:46px;margin:-23px 0 0 -23px;border-radius:50%;background:rgba(255,255,255,.3);}
#bf-root .bf-jl{left:22px;} #bf-root .bf-jr{right:22px;}
#bf-root.bf-touch .bf-joy{display:block;} #bf-root.bf-touch .bf-hint{display:none;}
#bf-root.bf-touch .bf-lv{top:auto;bottom:160px;transform:none;}
#bf-root .bf-credit{position:absolute;right:12px;bottom:6px;max-width:min(46vw,560px);font-size:10px;line-height:1.3;color:rgba(255,255,255,.62);text-shadow:0 1px 2px rgba(0,0,0,.6);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;pointer-events:auto;}
#bf-root.bf-touch .bf-credit{bottom:4px;left:12px;right:12px;max-width:none;text-align:center;}
#bf-root .bf-perf{left:12px;bottom:12px;font:600 11px/1.35 ui-monospace,Menlo,monospace;white-space:pre;pointer-events:none;border-radius:8px;}
#bf-root .bf-opts{position:absolute;right:14px;top:14px;display:flex;gap:6px;}
#bf-root .bf-opts button{font:inherit;font-size:12px;height:30px;padding:0 12px;border-radius:15px;color:#fff;cursor:pointer;border:1px solid rgba(255,255,255,.22);background:rgba(20,20,24,.5);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);white-space:nowrap;}
#bf-root .bf-opts button:disabled{opacity:.55;cursor:default;}
#bf-root .bf-tag{position:absolute;left:0;top:0;padding:3px 9px;border-radius:10px;background:rgba(20,20,24,.55);border:1px solid rgba(255,255,255,.18);font-size:11px;font-weight:600;letter-spacing:.01em;white-space:nowrap;pointer-events:none;opacity:0;transition:opacity .2s;will-change:transform;}
#bf-root .bf-nav{left:50%;bottom:58px;transform:translateX(-50%);display:flex;align-items:center;gap:10px;font-size:14px;font-weight:600;opacity:0;transition:opacity .3s;max-width:min(80vw,560px);}
#bf-root .bf-nav span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
#bf-root .bf-nav button{border:0;background:rgba(255,255,255,.18);color:#fff;border-radius:50%;width:24px;height:24px;cursor:pointer;flex:none;font-size:12px;}
#bf-root .bf-hop{position:absolute;right:40px;bottom:158px;width:64px;height:64px;border-radius:50%;border:1px solid rgba(255,255,255,.3);background:rgba(255,255,255,.12);color:#fff;font:600 13px -apple-system,Helvetica,Arial,sans-serif;display:none;touch-action:none;}
#bf-root.bf-touch .bf-hop{display:block;} #bf-root.bf-touch .bf-lv{bottom:236px;}
@media (max-width:700px){#bf-root .bf-toast{top:56px;font-size:14px;}}
"""

# ── shaders (GLSL ES 1.0 text; the header turns them into ES 3.00 on WebGL2) ────────────────────────────────────────────────────────────
_GLSL_TEXGEN = r"""
precision highp float;
VARY_F vec2 vQ;
uniform float uG; uniform float uO; uniform float uSeed; uniform float uPx;
float hs(vec2 p){ return fract(sin(dot(p,vec2(12.9898,78.233))+uSeed*7.31)*43758.5453); }
float vn(vec2 p, vec2 P){ vec2 i=floor(p), f=fract(p); f=f*f*(3.-2.*f);
  return mix(mix(hs(mod(i,P)),hs(mod(i+vec2(1.,0.),P)),f.x),mix(hs(mod(i+vec2(0.,1.),P)),hs(mod(i+vec2(1.,1.),P)),f.x),f.y); }
float fbm(vec2 u, vec2 P, float oc){ float s=0., a=.5, n=0.; vec2 q=u*P, PP=P;
  for(int i=0;i<7;i++){ if(float(i)>=oc) break; s+=a*vn(q,PP); n+=a; q*=2.; PP*=2.; a*=.5; } return s/n; }
vec3 cell(vec2 u, float P){ vec2 p=u*P, i=floor(p), f=fract(p); float d1=9.; vec2 id=vec2(0.);
  for(int y=-1;y<=1;y++) for(int x=-1;x<=1;x++){ vec2 g=vec2(float(x),float(y)), c=mod(i+g,vec2(P)); vec2 o=vec2(hs(c),hs(c+31.7)); vec2 r=g+o-f; float d=dot(r,r); if(d<d1){ d1=d; id=c; } }
  return vec3(sqrt(d1),id); }
void gen(vec2 u, out vec3 c, out float r, out float h){
  float G=uG; c=vec3(.8); r=.8; h=.5;
  if(G<.5){                      /* 0 marble: 4x4 slabs, warped veins */
    vec2 s=u*4., si=floor(s), sf=fract(s);
    float t=6.2832*(2.*u.x+u.y)+5.5*fbm(u,vec2(4.),6.), v1=pow(1.-abs(sin(t)),70.)*(.4+.6*fbm(u+.2,vec2(8.),3.))+pow(1.-abs(sin(t)),8.)*.12;
    float t2=6.2832*(5.*u.x-3.*u.y)+6.*fbm(u+.37,vec2(6.),6.), v2=pow(1.-abs(sin(t2)),90.)*.5;
    float cl=fbm(u,vec2(8.),5.);
    c=mix(vec3(.95,.94,.92),vec3(.88,.875,.865),cl)*(1.-.085*v1-.05*v2); r=.09+.08*v1+.06*cl; h=.6-.06*v1;
  } else if(G<1.5){              /* 1 ashlar: courses .5 m, three blocks a course */
    float cy=u.y*10., ci=floor(cy), cf=fract(cy), bx=u.x*5.+hs(vec2(ci,7.))*.9, bi=mod(floor(bx),5.), bf=fract(bx); vec2 id=vec2(bi,ci);
    float jw=.0045+.004*hs(id+3.), jd=min(min(bf,1.-bf)*1.2,min(cf,1.-cf)*.6), e=smoothstep(jw,jw+.009,jd);
    float sp=fbm(u,vec2(160.),3.), bg=fbm(u+hs(id)*.3,vec2(14.),4.), pit=smoothstep(.74,.8,fbm(u+3.1,vec2(220.),2.)), fos=smoothstep(.83,.9,vn(u*vec2(600.,140.)+hs(id)*50.,vec2(600.,140.)));
    float k=hs(id); c=vec3(.9,.84,.71)*(1.+(k-.5)*.1+(sp-.5)*.05+(bg-.5)*.09-pit*.05+fos*.05); c=mix(c,c*vec3(1.02,.98,.95),step(.7,hs(id+9.)));
    c=mix(vec3(.8,.76,.68),c,e); h=e*(.9+.1*sp)-pit*.06; r=.86;
  } else if(G<2.5){              /* 2 granite */
    float a=vn(u*180.,vec2(180.)), b=vn(u*260.+7.,vec2(260.)), m=fbm(u,vec2(12.),3.);
    c=vec3(.6,.58,.56)*(.9+.2*m); c=mix(c,vec3(.3,.29,.29),smoothstep(.6,.72,a)*.7); c=mix(c,vec3(.8,.78,.76),smoothstep(.66,.78,b)*.6); c=mix(c,vec3(.66,.55,.5),smoothstep(.72,.8,vn(u*140.+3.,vec2(140.)))*.35);
    r=.38; h=.5+.1*a;
  } else if(G<3.5){              /* 3 brick: 6 x 16 running bond */
    float cy=u.y*16., ci=floor(cy), cf=fract(cy), bx=u.x*6.+mod(ci,2.)*.5, bi=mod(floor(bx),6.), bf=fract(bx);
    float jd=min(min(bf,1.-bf)*.2,min(cf,1.-cf)*.075), e=smoothstep(.004,.008,jd), n=fbm(u,vec2(40.),3.);
    c=mix(vec3(.55,.53,.5),vec3(.6,.3,.22)*(.8+.4*hs(vec2(bi,ci)))*(.9+.2*n),e); h=e*(.9+.1*n); r=.9;
  } else if(G<4.5){              /* 4 plaster */
    float a=fbm(u,vec2(6.),5.), b=fbm(u,vec2(32.),3.);
    c=vec3(.94,.92,.88)*(1.+(a-.5)*.035+(b-.5)*.02); h=a*.5+b*.3; r=.9;
  } else if(G<5.5){              /* 5 eggshell paint */
    float a=fbm(u,vec2(5.),4.), b=vn(u*256.,vec2(256.));
    c=vec3(.96)*(1.+(a-.5)*.03); h=b*.5+a*.2; r=.62;
  } else if(G<6.5){              /* 6 wood panelling: one bay a tile, raised fields */
    vec2 d=min(u,1.-u); float e=min(d.x,d.y);
    float fld=smoothstep(.095,.14,e), gr=1.-smoothstep(.0,.008,abs(e-.09));
    float gv=fbm(u,vec2(36.,3.),4.), gh=fbm(u,vec2(3.,36.),4.), g=(d.y<.1&&d.x>.1)?gh:gv;
    c=vec3(.45,.29,.17)*(.8+.4*g)*(1.-gr*.35); h=mix(.25,.9,fld)-gr*.2; r=.42+.1*g;
  } else if(G<7.5){              /* 7 floorboards: 13 boards a tile */
    float by=u.y*13., bi=floor(by), bf=fract(by), o=hs(vec2(bi,1.)), sx=u.x*2.+o, si=mod(floor(sx),2.), sf=fract(sx);
    float g=fbm(u+vec2(0.,bi*.13),vec2(3.,104.),4.), k=hs(vec2(si,bi));
    float gap=1.-smoothstep(.0,.012,min(bf,1.-bf))*smoothstep(.0,.004,min(sf,1.-sf));
    c=vec3(.6,.47,.33)*(.86+.2*k)*(.88+.24*g)*(1.-gap*.55); h=1.-gap; r=.5+.15*g;
  } else if(G<8.5){              /* 8 chevron parquet: 6 columns of .4 m, blocks .1 m */
    vec2 m=u*2.4; float col=floor(m.x/.4), xl=m.x-col*.4, sg=mod(col,2.)<.5?1.:-1.;
    float yy=sg>0.?m.y+xl:m.y-xl+.4, bl=yy/.1, bi=floor(bl), bf=fract(bl);
    vec2 id=vec2(mod(col,6.),mod(bi,24.)); float k=hs(id);
    float al=(sg>0.?xl:.4-xl)/.4, g=vn(vec2(bf*7.+k*9.,al*1.5+k*5.),vec2(64.))*.6+vn(vec2(bf*30.,al*3.),vec2(64.))*.4;
    float jt=min(min(bf,1.-bf)*.0707,min(xl,.4-xl)), e=smoothstep(.0004,.0018,jt);
    c=vec3(.58,.43,.29)*(.8+.3*k)*(.88+.22*g)*mix(.55,1.,e); h=e; r=.42+.14*g;
  } else if(G<9.5){              /* 9 tile: 4x4, grout 4 mm */
    vec2 s=u*4., si=floor(s), sf=fract(s); float jd=min(min(sf.x,1.-sf.x),min(sf.y,1.-sf.y))*.3, e=smoothstep(.0015,.006,jd);
    c=mix(vec3(.62,.6,.57),vec3(.9,.88,.84)*(.94+.1*hs(mod(si,4.)))*(1.+(fbm(u,vec2(16.),3.)-.5)*.05),e); h=e; r=mix(.85,.22,e);
  } else if(G<10.5){             /* 10 terrazzo */
    vec3 a=cell(u,120.), b=cell(u+.5,260.); float ka=hs(a.yz), kb=hs(b.yz);
    c=vec3(.86,.83,.77)*(1.+(fbm(u,vec2(20.),3.)-.5)*.06);
    vec3 pa=ka<.4?vec3(.95,.94,.92):ka<.7?vec3(.66,.65,.63):ka<.88?vec3(.7,.55,.47):vec3(.36,.35,.34);
    c=mix(c,pa,(1.-smoothstep(.2+.18*hs(a.yz+1.),.25+.18*hs(a.yz+1.),a.x))*.8);
    c=mix(c,kb<.6?vec3(.96):vec3(.5),(1.-smoothstep(.16,.22,b.x))*.55); r=.2; h=.5;
  } else if(G<11.5){             /* 11 concrete */
    float a=fbm(u,vec2(8.),5.), p=cell(u,70.).x;
    c=vec3(.62,.62,.6)*(.88+.24*a)*(1.-(1.-smoothstep(.05,.1,p))*.35); h=a*.5+smoothstep(.05,.1,p)*.5; r=.88;
  } else if(G<12.5){             /* 12 carpet */
    float a=vn(u*300.,vec2(300.)), b=fbm(u,vec2(10.),3.); c=vec3(.5)*(.82+.25*a)*(.95+.1*b); h=a; r=1.;
  } else if(G<13.5){             /* 13 brushed metal */
    float a=fbm(u,vec2(2.,240.),4.); c=vec3(.84)*(.92+.14*a); h=a*.3; r=.26+.14*a;
  } else if(G<14.5){             /* 14 leather */
    float a=cell(u,64.).x, b=fbm(u,vec2(8.),3.); c=vec3(.5)*(.85+.2*a)*(.95+.1*b); h=a; r=.5;
  } else if(G<15.5){             /* 15 paving flags 1.5 x 1 m */
    float cy=u.y*6., ci=floor(cy), cf=fract(cy), bx=u.x*4.+hs(vec2(ci,3.))*.5, bi=mod(floor(bx),4.), bf=fract(bx);
    float jd=min(min(bf,1.-bf)*1.5,min(cf,1.-cf)), e=smoothstep(.006,.02,jd), a=fbm(u,vec2(24.),4.);
    c=vec3(.66,.64,.6)*(.88+.18*hs(vec2(bi,ci)))*(.9+.2*a); c=mix(vec3(.38,.37,.34),c,e); h=e*(.9+.1*a); r=.85;
  } else if(G<16.5){             /* 16 roof tile */
    float cy=u.y*20., cf=fract(cy), ci=floor(cy), bx=u.x*12.+mod(ci,2.)*.5, bf=fract(bx);
    float sh=smoothstep(0.,.9,cf), rnd=sin(bf*3.1416);
    c=vec3(.56,.3,.2)*(.75+.35*hs(vec2(mod(floor(bx),12.),ci)))*(.7+.3*sh)*(.8+.2*rnd); h=sh*.6+rnd*.4; r=.7;
  } else if(G<17.5){             /* 17 coffers: 2 x 2 a tile, three stepped frames and a rosette */
    vec2 q=fract(u*2.)-.5; float e=max(abs(q.x),abs(q.y)), st=floor(clamp((.46-e)/.045,0.,3.)), ro=length(q);
    float rs=smoothstep(.1,.07,ro)*(.6+.4*sin(atan(q.y,q.x)*8.)); float pl=fbm(u,vec2(12.),3.);
    h=1.-st*.22-(e<.32?.1:0.)+rs*.35; c=vec3(.95,.93,.88)*(1.-st*.02)*(.97+.06*pl); c=mix(c,vec3(.86,.68,.36),clamp(rs*1.4,0.,1.)*.8); c=mix(c,vec3(.8,.66,.4),(1.-smoothstep(.003,.008,abs(e-.46)))*.6); r=mix(.85,.4,rs);
  } else if(G<18.5){             /* 18 foliage */
    vec3 a=cell(u,48.); float n=fbm(u,vec2(24.),4.); c=mix(vec3(.16,.24,.1),vec3(.34,.42,.18),hs(a.yz)*.7+n*.3)*(1.-smoothstep(.3,.5,a.x)*.45); h=1.-a.x; r=.8;
  } else if(G>19.5){             /* 20 painted panelling, 21 white-and-gold boiserie: raised fields, a bead, eggshell paint (21: gilded mouldings) */
    vec2 d=min(u,1.-u); float e=min(d.x,d.y), fld=smoothstep(.095,.14,e), gr=1.-smoothstep(.0,.008,abs(e-.09)), bd=1.-smoothstep(.0,.007,abs(e-.155)), a=fbm(u,vec2(5.),4.);
    c=vec3(.95)*(1.+(a-.5)*.04)*(1.-gr*.3); h=mix(.25,.9,fld)-gr*.2+bd*.12; r=.6;
    if(G>20.5){ float gl=max(bd,1.-smoothstep(.0,.009,abs(e-.06))); c=mix(c,vec3(.8,.66,.42),gl*.75); r=mix(r,.3,gl); }
  } else {                       /* 19 dolomite (Kasota stone): fine buff mottling, faint bedding, scattered pores, no veins */
    float a=fbm(u,vec2(6.),5.), b=fbm(u+.3,vec2(40.),3.), bed=fbm(vec2(u.x,u.y*1.)+.7,vec2(3.,28.),3.), sp=vn(u*320.,vec2(320.));
    c=vec3(.9,.82,.66)*(1.+(a-.5)*.13+(b-.5)*.06+(bed-.5)*.07)*(1.-smoothstep(.84,.93,sp)*.04); r=.36+.16*a; h=.5+.18*b-smoothstep(.84,.93,sp)*.04;
  }
}
void main(){
  vec2 u=vQ; vec3 c; float r, h; gen(u,c,r,h);
  if(uO<.5){ FRAG=vec4(c,r); return; }
  vec3 c1; float r1, hx, hy; gen(fract(u+vec2(uPx,0.)),c1,r1,hx); gen(fract(u+vec2(0.,uPx)),c1,r1,hy);
  vec3 n=normalize(vec3(-(hx-h)*6.,-(hy-h)*6.,1.));
  FRAG=vec4(n.xy*.5+.5,h,.55+.45*h);
}
"""

_GLSL_QUAD_VS = r"""
ATTR vec2 aQ; VARY_V vec2 vQ;
void main(){ vQ=aQ*.5+.5; gl_Position=vec4(aQ,0.,1.); }
"""

_GLSL_SKY = r"""
precision highp float;
VARY_F vec2 vQ;
uniform vec3 uF; uniform vec3 uR; uniform vec3 uU; uniform vec3 uSun; uniform vec3 uSunC; uniform vec3 uSkyC; uniform vec4 uScr;
""" + _IBL_GLSL + r"""
float hs(vec2 p){ return fract(sin(dot(p,vec2(12.9898,78.233)))*43758.5453); }
float vn(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.-2.*f); return mix(mix(hs(i),hs(i+vec2(1.,0.)),f.x),mix(hs(i+vec2(0.,1.)),hs(i+vec2(1.,1.)),f.x),f.y); }
vec3 tone(vec3 c){ c*=uScr.x; c=(c*(2.51*c+.03))/(c*(2.43*c+.59)+.14); return pow(clamp(c,0.,1.),vec3(1./2.2)); }
void main(){
  vec2 q=vQ*2.-1.; vec3 d=normalize(uF+uR*q.x+uU*q.y);
  float h=max(d.z,0.); vec3 zen=uSkyC*vec3(.5,.68,1.08), hor=uSkyC*vec3(1.12,1.08,1.02);
  vec3 c=mix(hor,zen,pow(h,.5));
  float sd=max(dot(d,uSun),0.); c+=uSunC*(pow(sd,1500.)*40.+pow(sd,10.)*.12);
  if(d.z>0.){ vec2 p=d.xy/(d.z+.18)*1.3; float n=vn(p)*.5+vn(p*2.1)*.3+vn(p*4.3)*.2; float cl=smoothstep(.52,.82,n)*smoothstep(0.,.3,d.z); c=mix(c,uSkyC*1.18+uSunC*.12,cl*.55); }
  else c=mix(hor*.92,uSkyC*vec3(.42,.41,.39),min(1.,-d.z*5.));
#ifdef ENV
  if(uEnvP.w>0.){ vec3 e=hdrAt(d,0.)+uSunC*(pow(sd,1500.)*40.+pow(sd,10.)*.06); c=mix(c,e,uIbl.z); }      /* the HDRI sky (its own sun painted out: ours is drawn), faded in once loaded */
#endif
  vec3 o=tone(c); o+=(hs(gl_FragCoord.xy)-.5)/255.;
  FRAG=vec4(o,1.);
}
"""

_GLSL_DEPTH_VS = r"""
ATTR vec3 aP; ATTR vec3 aN; ATTR vec2 aT; ATTR vec4 aX; uniform mat4 uLVP;
void main(){ gl_Position=uLVP*vec4(aP,1.); }
"""

_GLSL_DEPTH_FS = r"""
precision highp float;
void main(){ vec4 b=fract(gl_FragCoord.z*vec4(1.,255.,65025.,16581375.)); b-=b.yzww*vec4(1./255.,1./255.,1./255.,0.); FRAG=b; }
"""

_GLSL_WORLD_VS = r"""
ATTR vec3 aP; ATTR vec3 aN; ATTR vec2 aT; ATTR vec4 aX;
uniform mat4 uVP;
VARY_V vec3 vP; VARY_V vec3 vN; VARY_V vec2 vT; VARY_V vec4 vX;
void main(){ vP=aP; vN=aN; vT=aT; vX=aX; gl_Position=uVP*vec4(aP,1.); }
"""

_GLSL_WORLD_FS = r"""
precision highp float;
VARY_F vec3 vP; VARY_F vec3 vN; VARY_F vec2 vT; VARY_F vec4 vX;
uniform sampler2D uA; uniform sampler2D uB;
uniform vec4 uMat; uniform vec4 uTint; uniform vec4 uUv; uniform vec3 uEye;
uniform vec4 uRoom; uniform vec3 uAmbC; uniform vec3 uAmbF;
uniform vec4 uSpP[NS]; uniform vec4 uSpD[NS]; uniform vec4 uSpC[NS]; uniform float uNS;
uniform vec4 uWnC[NW]; uniform vec4 uWnU[NW]; uniform vec4 uWnN[NW]; uniform float uNW;
uniform vec4 uEd[NE]; uniform float uNE;
uniform vec4 uBl[NB]; uniform vec4 uBr[NB]; uniform float uNB;
uniform vec3 uSun; uniform vec3 uSunC; uniform vec3 uSkyC; uniform vec4 uFog; uniform vec4 uScr;
uniform vec4 uJ; uniform vec4 uVar; uniform sampler2D uSM; uniform mat4 uLVP; uniform vec4 uSMp;
uniform sampler2D uRT; uniform vec4 uRefl; uniform vec4 uClip; uniform float uPol;
#ifdef REALTEX
uniform sampler2D uA2; uniform sampler2D uB2; uniform vec4 uRx;      /* the real (photographed) set: x fade-in 0..1, y metres a tile, z joints baked into it */
#endif
""" + _IBL_GLSL + r"""
float h31(vec3 p){ p=fract(p*.1031); p+=dot(p,p.yzx+33.33); return fract((p.x+p.y)*p.z); }
float n3(vec3 p){ vec3 i=floor(p), f=fract(p); f=f*f*(3.-2.*f);
  return mix(mix(mix(h31(i),h31(i+vec3(1,0,0)),f.x),mix(h31(i+vec3(0,1,0)),h31(i+vec3(1,1,0)),f.x),f.y),mix(mix(h31(i+vec3(0,0,1)),h31(i+vec3(1,0,1)),f.x),mix(h31(i+vec3(0,1,1)),h31(i+vec3(1,1,1)),f.x),f.y),f.z); }
float unpk(vec4 b){ return dot(b,vec4(1.,1./255.,1./65025.,1./16581375.)); }
float shTap(vec2 uv, float z){ return step(z,unpk(TEX(uSM,uv))); }
#ifdef SOFTSH
/* soft sun shadows: a rotated Poisson disc; on high the disc grows with the distance to the blocker (a ~1.5 degree sun: sharp at contact, soft further off) */
const vec2 PD[16]=vec2[16](vec2(-.942,-.399),vec2(.946,-.769),vec2(-.094,-.929),vec2(.345,.294),vec2(-.916,.458),vec2(-.815,-.879),vec2(-.383,.277),vec2(.975,.756),
  vec2(.443,-.975),vec2(.537,-.474),vec2(-.265,-.419),vec2(.792,.191),vec2(-.242,.997),vec2(-.814,.914),vec2(.2,.786),vec2(.144,-.141));
float shadow(vec3 p, vec3 n){ if(uSMp.z<.5) return -1.; vec4 l=uLVP*vec4(p+n*uSMp.y*2.+uSun*uSMp.y,1.); vec3 c=l.xyz/l.w*.5+.5;
  if(c.x<.001||c.y<.001||c.x>.999||c.y>.999||c.z>.999) return -1.; float t=uSMp.x, s=0., z=c.z-uSMp.w;
  float a=fract(52.9829189*fract(dot(gl_FragCoord.xy,vec2(.06711056,.00583715))))*6.2832; mat2 R=mat2(cos(a),sin(a),-sin(a),cos(a));
#if SOFTSH>1
  float bs=0., bn=0.; for(int i=0;i<6;i++){ float d=unpk(TEX(uSM,c.xy+R*PD[i*2+1]*t*5.)); if(d<z){ bs+=d; bn+=1.; } }
  if(bn<.5) return 1.; float w=clamp((z-bs/bn)*279.*.026/uSMp.y,1.,6.); z-=uSMp.w*w*.35;
  for(int i=0;i<12;i++) s+=shTap(c.xy+R*PD[i]*t*w,z); return s/12.;
#else
  for(int i=0;i<8;i++) s+=shTap(c.xy+R*PD[i*2]*t*1.6,z); return s/8.;
#endif
  }
#else
float shadow(vec3 p, vec3 n){ if(uSMp.z<.5) return -1.; vec4 l=uLVP*vec4(p+n*uSMp.y*2.+uSun*uSMp.y,1.); vec3 c=l.xyz/l.w*.5+.5;
  if(c.x<.001||c.y<.001||c.x>.999||c.y>.999||c.z>.999) return -1.; float t=uSMp.x, s=0., z=c.z-uSMp.w;
  for(int i=-1;i<=1;i++) for(int j=-1;j<=1;j++) s+=shTap(c.xy+vec2(float(i),float(j))*t*1.3,z);
  return s/9.; }
#endif
float sh1(vec3 p){ vec4 l=uLVP*vec4(p,1.); vec3 c=l.xyz/l.w*.5+.5; if(c.x<.001||c.y<.001||c.x>.999||c.y>.999) return 0.; return shTap(c.xy,c.z-uSMp.w); }
float sd2(vec2 p, vec2 a, vec2 b){ vec2 pa=p-a, ba=b-a; float h=clamp(dot(pa,ba)/max(dot(ba,ba),1e-6),0.,1.); return length(pa-ba*h); }
float ggx(vec3 N, vec3 V, vec3 L, float r){ vec3 H=normalize(V+L); float a=r*r, a2=a*a, nh=max(dot(N,H),0.), d=nh*nh*(a2-1.)+1.;
  float nl=max(dot(N,L),0.), nv=max(dot(N,V),1e-3), k=(r+1.)*(r+1.)/8.;
  return a2/(3.14159*d*d)*(nv/(nv*(1.-k)+k))/(4.*nv*(nl*(1.-k)+k)+1e-4); }
vec3 tone(vec3 c){ c*=uScr.x; c=(c*(2.51*c+.03))/(c*(2.43*c+.59)+.14); return pow(clamp(c,0.,1.),vec3(1./2.2)); }
/* the material's two textures at uv: the procedural set (uA, uB), the real one (uA2, uB2) faded in over it once loaded */
void samp(vec2 uv, vec2 ur, bool rot, out vec4 A, out vec4 B){ A=vec4(0.); B=vec4(.5,.5,.5,1.);
#ifdef REALTEX
  if(uRx.x<1.){ A=TEX(uA,uv); B=TEX(uB,uv); }
  if(uRx.x>0.&&!(rot&&uRx.z>.5)){ vec4 A2=TEX(uA2,ur), B2=TEX(uB2,ur); A=uRx.x<1.?mix(A,A2,uRx.x):A2; B=uRx.x<1.?mix(B,B2,uRx.x):B2; }
#else
  A=TEX(uA,uv); B=TEX(uB,uv);
#endif
}
vec3 post(vec3 c, float dist){ c=mix(c,uFog.rgb,1.-exp(-dist*uFog.a));
#ifdef SHAFTS
  if(uSMp.z>.5&&uRoom.z<.5&&uClip.x<.5){ float L=min(dist,28.), dn=fract(sin(dot(gl_FragCoord.xy,vec2(12.9898,78.233)))*43758.5453), a=0.; vec3 dir=(vP-uEye)/max(dist,1e-3);
    for(int i=0;i<10;i++){ a+=sh1(uEye+dir*(L*(float(i)+dn)/10.)); } c+=uSunC*(a/10.)*L*.0045*(1.+.6*pow(max(dot(-dir,-uSun),0.),6.)); }
#endif
  vec3 o=tone(c); if(uClip.x>.5) return o;
  vec2 sc=gl_FragCoord.xy*uScr.zw-.5; o*=1.-.2*dot(sc,sc);
  return o+(fract(sin(dot(gl_FragCoord.xy,vec2(12.9898,78.233)))*43758.5453)-.5)/255.; }
void main(){
  if(uClip.x>.5&&vP.z<uClip.y-.02) discard;
  float kind=uTint.a; vec3 V=uEye-vP; float dist=length(V); V/=dist;
  vec3 N=normalize(vN); if(kind>3.5&&kind<4.5&&dot(N,V)<0.) N=-N;
  if(kind>4.5&&kind<5.5){ vec2 q=max((abs(vT)-vX.zw)/max(1.-vX.zw,vec2(.01)),0.); float d=length(q); FRAG=vec4(0.,0.,0.,uMat.y*pow(1.-smoothstep(0.,1.,d),2.)); return; }
  if(kind>5.5){ FRAG=vec4(post(uTint.rgb*uMat.x,dist),1.); return; }
  if(kind>.5&&kind<1.5){ vec2 f=abs(fract(vT/vec2(.7,1.4))-.5)*vec2(.7,1.4); float mu=smoothstep(.337,.344,f.x)*.3+smoothstep(.689,.695,f.y)*.3; vec2 g=abs(fract(vT/4.2)-.5); mu=min(1.,max(mu,smoothstep(.492,.496,max(g.x,g.y))));
    float tr=fract(vT.x/2.8)-.5, sh=1.-.38*exp(-tr*tr/.006)-.22*exp(-pow(fract(vT.y/5.6)-.5,2.)/.004);
    vec2 cc=abs(fract(vT/4.2)-.5); float cloud=.5+.5*sin(vT.x*.37+sin(vT.y*.23)*2.)*sin(vT.y*.29+1.3);
    vec3 em=uTint.rgb*uRoom.w*(.72+.28*(1.-dot(cc,cc)*2.))*(.9+.1*cloud)*sh*vec3(.98,1.,1.03);
    FRAG=vec4(post(mix(em,em*.45+uAmbC*.2,mu),dist),1.); return; }
  vec3 alb; float rough, metal=uMat.z, cav=1., alpha=1.;
  float jl=0., brd=0.;
  if(kind<.5){
    vec2 uv=vT/uMat.x, sl=vec2(0.); float tone=1.;
    if(uJ.x>0.){ sl=floor(vT/uJ.x); float hh=h31(vec3(sl,uJ.x)); uv+=vec2(hh,h31(vec3(sl.yx,7.)))*3.7; if(hh>.5) uv=uv.yx;
      vec2 fj=abs(fract(vT/uJ.x)-.5)*uJ.x; float dj=uJ.x*.5-max(fj.x,fj.y); jl=1.-smoothstep(uJ.y*.5,uJ.y,dj); tone=1.+(h31(vec3(sl,3.))-.5)*uJ.z; }
    vec2 ur=uv;
#ifdef REALTEX
    if(uRx.x>0.){ if(uRx.z>.5){ ur=vT/uRx.y; jl*=1.-uRx.x; tone=mix(tone,1.,uRx.x); } else ur=uv*(uMat.x/uRx.y); }     /* a set with its own joints: no slabs of ours over it */
#endif
    vec4 A, B; samp(uv,ur,false,A,B);
    if(uVar.w>0.){ float an=n3(vP*.23+3.1)*.7+n3(vP*.97+1.3)*.3, wt=smoothstep(.36,.64,an); if(wt>.01){ vec2 u2=vec2(uv.y,-uv.x)*.83+vec2(.37,.61), r2=vec2(ur.y,-ur.x)*.83+vec2(.37,.61); vec4 A2, B2; samp(u2,r2,true,A2,B2);
#ifdef REALTEX
      if(uRx.z>.5) wt*=1.-uRx.x;
#endif
      vec2 n2=B2.xy*2.-1.; B2.xy=vec2(-n2.y,n2.x)*.5+.5; A=mix(A,A2,wt); B=mix(B,B2,wt); } }
    alb=pow(A.rgb,vec3(2.2))*uTint.rgb*tone; rough=clamp(A.a*uMat.y,.04,1.); cav=mix(1.,B.a,.75);
    float mv=n3(vP*.31+.5)*.65+n3(vP*1.7)*.35; alb*=1.+(mv-.5)*uVar.x; alb*=1.+(h31(vec3(floor(vT/uMat.x),1.))-.5)*uVar.y;
    alb=mix(alb,alb*vec3(.86,.82,.76),uVar.z*exp(-max(vP.z-uRoom.x,0.)/.45)*(1.-abs(vN.z)));
    alb=mix(alb,vec3(.18),jl*.55); rough=mix(rough,.8,jl);
#ifdef DERIV
    vec3 p1=dFdx(vP), p2=dFdy(vP); vec2 t1=dFdx(uv), t2=dFdy(uv);
    vec3 q2=cross(p2,N), q1=cross(N,p1), T=q2*t1.x+q1*t2.x, Bt=q2*t1.y+q1*t2.y; float im=inversesqrt(max(max(dot(T,T),dot(Bt,Bt)),1e-14));
    vec2 nm=(B.xy*2.-1.)*uMat.w; N=normalize(T*im*nm.x+Bt*im*nm.y+N*(1.+jl*2.));
#endif
  } else if(kind<2.5){ alb=pow(TEX(uA,vT*uUv.xy+uUv.zw).rgb,vec3(2.2)); rough=uMat.y; metal=0.; }
  else if(kind<3.5){ alb=uTint.rgb; rough=uMat.y; }
  else { alb=uTint.rgb; rough=.05; metal=0.; }
  /* contact AO from the room's shape */
  float hz=vP.z-uRoom.x, hc=uRoom.y-vP.z, ao=1., vt=1.-abs(N.z);
  ao*=1.-.5*vt*exp(-max(hz,0.)/.22);
  ao*=1.-.3*vt*exp(-max(hc,0.)/.3)*(1.-uRoom.z);
  vec2 cd=vX.xy*4.; ao*=1.-.36*exp(-min(cd.x,cd.y)/.3);
  if(abs(N.z)>.6){ float near=N.z>0.?hz:hc;
    if(near<.3){ float de=99.; for(int i=0;i<NE;i++){ if(float(i)>=uNE) break; de=min(de,sd2(vP.xy,uEd[i].xy,uEd[i].zw)); }
      ao*=1.-(N.z>0.?.42:.32)*exp(-de/(N.z>0.?.3:.5));
      if(uJ.w>0.&&N.z>0.&&kind<.5){ float bw=uJ.w; brd=1.-smoothstep(bw-.01,bw,de); float ln=1.-smoothstep(.012,.02,abs(de-bw-.035));
        alb=mix(alb,alb*vec3(.42,.36,.33),brd*.85); alb=mix(alb,vec3(.55,.38,.16),ln); metal=mix(metal,1.,ln); rough=mix(rough,.3,ln); } }
    if(N.z>0.&&hz<.3){ for(int i=0;i<NB;i++){ if(float(i)>=uNB) break; vec4 b=uBl[i], r=uBr[i]; vec2 q=vP.xy-b.xy, l=vec2(dot(q,r.xy),dot(q,vec2(-r.y,r.x))); float d;
        if(r.w>.5) d=length(l)-b.z; else { vec2 e=abs(l)-b.zw; d=length(max(e,0.))+min(max(e.x,e.y),0.); }
        ao*=1.-r.z*exp(-max(d,0.)/.2)*smoothstep(-.4,0.,d)*.9-r.z*.1*step(d,0.); } } }
  ao=clamp(ao,0.,1.);
  vec3 Ld=vec3(0.), Ls=vec3(0.);
  for(int i=0;i<NS;i++){ if(float(i)>=uNS) break; vec3 Lv=uSpP[i].xyz-vP; float d2=dot(Lv,Lv); vec3 L=Lv*inversesqrt(d2);
    float cone=smoothstep(uSpD[i].w,uSpC[i].w,dot(-L,uSpD[i].xyz)); float nl=max(dot(N,L),0.); vec3 E=uSpC[i].rgb*(uSpP[i].w*cone*nl/(d2+.04)); Ld+=E; Ls+=E*ggx(N,V,L,rough); }
  for(int i=0;i<NW;i++){ if(float(i)>=uNW) break; vec3 c=uWnC[i].xyz, U=uWnU[i].xyz, wn=uWnN[i].xyz; float hw=uWnC[i].w, hh=uWnU[i].w, I=uWnN[i].w; vec3 Vv=normalize(cross(wn,U));
    vec3 rel=vP-c; if(dot(rel,wn)<-.02) continue;
    vec3 q=c+U*clamp(dot(rel,U),-hw,hw)+Vv*clamp(dot(rel,Vv),-hh,hh), Lv=q-vP; float d2=dot(Lv,Lv)+.01; vec3 L=Lv*inversesqrt(d2);
    float ar=4.*hw*hh, em=max(dot(-L,wn),0.)*.85+.15, nl=max(dot(N,L),0.);
    vec3 E=uSkyC*(abs(I)*ar*em*nl/(d2+ar*.3)); Ld+=E; Ls+=E*ggx(N,V,L,max(rough,.18));
    if(I>0.&&uSMp.z<.5){ float sdn=dot(uSun,wn); if(sdn<-.03){ float t=dot(c-vP,wn)/sdn; vec3 h=vP+uSun*t-c; float hu=abs(dot(h,U)), hv=dot(h,Vv), pen=.01+t*.01;
      float m=(1.-smoothstep(hw-pen,hw+pen,hu))*(1.-smoothstep(hh-pen,hh+pen,abs(hv)));
      if(hw>.6) m*=smoothstep(.025,.035+pen,hu);
      if(hh>.8) m*=smoothstep(.025,.035+pen,abs(hv-hh*.35));
      vec3 E2=uSunC*(m*max(dot(N,uSun),0.)*.9); Ld+=E2; Ls+=E2*ggx(N,V,uSun,rough); } } }
  float sv=shadow(vP,normalize(vN)), snl=max(dot(N,uSun),0.);
  if(sv>=0.){ if(uRoom.z<.5) sv*=step(.0,dot(normalize(vN),uSun)); vec3 E=uSunC*snl*sv*(uRoom.z>.5?1.:.9); Ld+=E; Ls+=E*ggx(N,V,uSun,rough); }
  else if(uRoom.z>.5){ vec3 E=uSunC*snl*mix(.55,1.,smoothstep(0.,1.5,hz)); Ld+=E; Ls+=E*ggx(N,V,uSun,rough); }
  vec3 amb=mix(uAmbF,uAmbC,N.z*.3+.55);
#ifdef IBL
  if(uRoom.z>.5) amb=shIrr(N)*uIbl.x;                     /* outdoors: the HDRI sky's irradiance (and its sun-lit ground) */
#endif
  float nv=max(dot(N,V),1e-3); vec3 F0=mix(vec3(.04),alb,metal), F=F0+(1.-F0)*pow(1.-nv,5.)*(1.-rough*.8);
  vec3 R=reflect(-V,N); bool outside=uRoom.z>.5; if(kind>3.5&&vX.z>.25){ outside=(vX.z>.75)==(dot(normalize(vN),V)>0.); }
  vec3 env=outside?uSkyC*(.45+.55*clamp(R.z+.25,0.,1.))*(R.z<0.?.45:1.):mix(uAmbF*.55,uAmbC*1.55,smoothstep(-.45,.75,R.z))*1.15+uSkyC*(.06*uRoom.w*pow(max(R.z,0.),5.));
#ifdef IBL
  if(outside){ vec3 e=shIrr(R)*uIbl.x*1.15;
#ifdef ENV
    if(uEnvP.w>0.) e=mix(e,hdrAt(R,rough*7.)*uIbl.y,uIbl.z);
#endif
    env=e*(R.z<0.?.6:1.); }
#endif
  if(metal>.5&&!outside) env*=(.3+1.5*smoothstep(-.15,.85,R.z))*(.45+1.1*pow(max(dot(R,vec3(.36,.48,.8)),0.),2.));
  vec3 col;
  if(kind>3.5){ col=F*(env*1.2+Ls)+alb*(amb+Ld)*.03; alpha=clamp(uMat.y+dot(F,vec3(.33))*.9+(outside&&vX.z>.25?.22:0.),0.,.96); if(outside&&vX.z>.25) col+=env*.2; }
  else col=alb*(1.-metal)*(amb*ao*cav+Ld*mix(1.,ao,.55)*cav)+F*(Ls*cav+env*ao*(1.-rough)*(1.-rough)*(1.+metal*2.2))+metal*alb*(amb+Ld*.25)*.2;
  vec3 o=post(col,dist);
  /* polished floors: the planar reflection of the room, blurred by roughness, stronger at grazing angles */
  if(uRefl.x>.5&&uPol>0.&&kind<.5&&N.z>.75&&abs(vP.z-uRefl.y)<.03){ vec2 rq=gl_FragCoord.xy*uScr.zw+N.xy*.012; float g=pow(1.-max(dot(normalize(vN),V),0.),4.);
    vec3 rc=TEXB(uRT,rq,rough*5.5).rgb; o=mix(o,rc,uPol*uRefl.z*(.1+.55*g)*(1.-jl)*(1.-brd)*ao); }
  FRAG=vec4(o,alpha);
}
"""

FPV_JS = r"""
(function(){
if(window.AltoBuildingFPV) return;
var TEXGEN=__TEXGEN__, QUADVS=__QUADVS__, SKYFS=__SKYFS__, WVS=__WVS__, WFS=__WFS__, DVS=__DVS__, DFS=__DFS__;
var CFG={eye:1.65, walk:3.2, hurry:8.0, tau:.18, turn:1.9, pr:.26, step:.52, head:1.85, knee:.35, drop:1.0, minDoor:.9, pitchMax:85*Math.PI/180, lookX:.0042, lookY:.0036, near:.05, far:900, camD:3.4, camUp:.45};
/* the walker is a capsule: radius pr (0.26 m), feet to the top of the head `head` (1.85 m: the tallest avatar, 1.80 m, with hair); `drop` is the most it may step down off an edge that is not a stair (higher ledges are walls) */
var PI=Math.PI, D=typeof document!=='undefined'?document:null;
__AVATAR__
__FXG__
var S={on:false, gl:null};

/* ── small math ── */
function sub(a,b){ return [a[0]-b[0],a[1]-b[1],a[2]-b[2]]; }
function dot(a,b){ return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]; }
function cross(a,b){ return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]; }
function nrm(a){ var l=Math.sqrt(a[0]*a[0]+a[1]*a[1]+a[2]*a[2])||1; return [a[0]/l,a[1]/l,a[2]/l]; }
function clamp(v,a,b){ return v<a?a:v>b?b:v; }
function mmul(a,b){ var o=new Float32Array(16); for(var c=0;c<4;c++) for(var r=0;r<4;r++){ var s=0; for(var k=0;k<4;k++) s+=a[k*4+r]*b[c*4+k]; o[c*4+r]=s; } return o; }
function persp(fy,as,n,f){ var t=1/Math.tan(fy/2); return [t/as,0,0,0, 0,t,0,0, 0,0,(f+n)/(n-f),-1, 0,0,2*f*n/(n-f),0]; }
function lookAt(e,c,u){ var z=nrm(sub(e,c)), x=nrm(cross(u,z)), y=cross(z,x); return [x[0],y[0],z[0],0, x[1],y[1],z[1],0, x[2],y[2],z[2],0, -dot(x,e),-dot(y,e),-dot(z,e),1]; }
function planes(m){ var o=[]; for(var i=0;i<3;i++) for(var s=-1;s<=1;s+=2) o.push([m[3]+s*m[i],m[7]+s*m[4+i],m[11]+s*m[8+i],m[15]+s*m[12+i]]); return o; }
function boxIn(P,b){ for(var i=0;i<6;i++){ var p=P[i]; if(p[0]*(p[0]>0?b[3]:b[0])+p[1]*(p[1]>0?b[4]:b[1])+p[2]*(p[2]>0?b[5]:b[2])+p[3]<0) return false; } return true; }
function hash(s){ var h=2166136261; s=String(s); for(var i=0;i<s.length;i++){ h^=s.charCodeAt(i); h=Math.imul(h,16777619); } return (h>>>0)/4294967296; }
function rng(seed){ var s=Math.floor(seed*2147483646)+1; return function(){ s=s*16807%2147483647; return (s-1)/2147483646; }; }
function q(){ var o={}; try{ String(location.search||'').replace(/^\?/,'').split('&').forEach(function(kv){ var p=kv.split('='); if(p[0]) o[decodeURIComponent(p[0])]=decodeURIComponent(p[1]||'1'); }); }catch(x){} return o; }

/* ── polygons ── */
function bb2(p){ var a=[1e9,1e9,-1e9,-1e9]; for(var i=0;i<p.length;i++){ var v=p[i]; if(v[0]<a[0]) a[0]=v[0]; if(v[1]<a[1]) a[1]=v[1]; if(v[0]>a[2]) a[2]=v[0]; if(v[1]>a[3]) a[3]=v[1]; } return a; }
function bbHit(a,b,m){ m=m||0; return a[0]<=b[2]+m&&b[0]<=a[2]+m&&a[1]<=b[3]+m&&b[1]<=a[3]+m; }
function pip(p,x,y){ var c=false; for(var i=0,n=p.length,j=n-1;i<n;j=i++){ var a=p[i], b=p[j]; if((a[1]>y)!==(b[1]>y)&&x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]) c=!c; } return c; }
function parea(p){ var s=0; for(var i=0,n=p.length;i<n;i++){ var a=p[i], b=p[(i+1)%n]; s+=a[0]*b[1]-b[0]*a[1]; } return s/2; }
function segD(px,py,ax,ay,bx,by){ var dx=bx-ax, dy=by-ay, l=dx*dx+dy*dy, t=l?clamp(((px-ax)*dx+(py-ay)*dy)/l,0,1):0, ex=px-ax-t*dx, ey=py-ay-t*dy; return Math.sqrt(ex*ex+ey*ey); }
function interior(p){ var bb=bb2(p), best=[(bb[0]+bb[2])/2,(bb[1]+bb[3])/2], bw=-1;
  if(pip(p,best[0],best[1])){ var cx=0,cy=0,a=0; for(var i=0,n=p.length;i<n;i++){ var u=p[i], v=p[(i+1)%n], c=u[0]*v[1]-v[0]*u[1]; a+=c; cx+=(u[0]+v[0])*c; cy+=(u[1]+v[1])*c; } if(Math.abs(a)>1e-9&&pip(p,cx/(3*a),cy/(3*a))) return [cx/(3*a),cy/(3*a)]; }
  for(var k=1;k<10;k++){ var y=bb[1]+(bb[3]-bb[1])*k/10, xs=[]; for(var i2=0,n2=p.length;i2<n2;i2++){ var A=p[i2], B=p[(i2+1)%n2]; if((A[1]>y)!==(B[1]>y)) xs.push(A[0]+(y-A[1])*(B[0]-A[0])/(B[1]-A[1])); }
    xs.sort(function(a,b){return a-b;}); for(var j=0;j+1<xs.length;j+=2) if(xs[j+1]-xs[j]>bw){ bw=xs[j+1]-xs[j]; best=[(xs[j]+xs[j+1])/2,y]; } }
  return best; }
/* trapezoids of a polygon (the first ring) minus the UNION of its holes (the other rings; overlapping holes stay holes, as they are for walking): cb(xl0,xr0,y0,xl1,xr1,y1) */
function fillRings(rings,cb){ var ys=[], ER=rings.map(function(R){ var E=[]; for(var i=0,n=R.length;i<n;i++){ var a=R[i], b=R[(i+1)%n]; ys.push(a[1]); if(Math.abs(a[1]-b[1])>1e-9) E.push(a[1]<b[1]?[a[0],a[1],b[0],b[1]]:[b[0],b[1],a[0],a[1]]); } return E; });
  ys.sort(function(a,b){return a-b;}); var Y=[]; ys.forEach(function(y){ if(!Y.length||y-Y[Y.length-1]>1e-7) Y.push(y); });
  for(var k=0;k+1<Y.length;k++){ var y0=Y[k], y1=Y[k+1], ym=(y0+y1)/2, iv=null;
    for(var r=0;r<ER.length;r++){ var E=ER[r], xs=[];
      for(var j=0;j<E.length;j++){ var e=E[j]; if(e[1]<=ym&&e[3]>ym){ var s=(e[2]-e[0])/(e[3]-e[1]); xs.push([e[0]+s*(ym-e[1]),e[0]+s*(y0-e[1]),e[0]+s*(y1-e[1])]); } }
      xs.sort(function(a,b){return a[0]-b[0];}); var pr=[]; for(var m=0;m+1<xs.length;m+=2) pr.push([xs[m],xs[m+1]]);
      if(r===0){ iv=pr; continue; } if(!iv.length) break;
      pr.forEach(function(h){ var nv=[]; iv.forEach(function(v){ if(h[1][0]<=v[0][0]||h[0][0]>=v[1][0]){ nv.push(v); return; } if(h[0][0]>v[0][0]) nv.push([v[0],h[0]]); if(h[1][0]<v[1][0]) nv.push([h[1],v[1]]); }); iv=nv; }); }
    (iv||[]).forEach(function(v){ cb(v[0][1],v[1][1],y0,v[0][2],v[1][2],y1); }); } }
function clipHalf(p,nx,ny,c){ var o=[]; for(var i=0,n=p.length;i<n;i++){ var a=p[i], b=p[(i+1)%n], da=a[0]*nx+a[1]*ny-c, db=b[0]*nx+b[1]*ny-c;
    if(da>=0) o.push(a); if((da>=0)!==(db>=0)){ var t=da/(da-db); o.push([a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t]); } } return o; }

/* ── the plan, indexed: levels, rooms, wall pieces, openings, stairs, collision, supports, portals, batches ── */
var MAT={ marble:[0,[1,1,1],3.6,1,0,.35], limestone:[1,[1,1,1],6,1,0,.55], sandstone:[1,[.98,.82,.7],6,1,0,.55], stone:[1,[.97,.95,.92],6,1,0,.55],
  granite:[2,[1.22,1.2,1.17],1.6,1,0,.25], brick:[3,[1,1,1],1.2,1,0,1.4], plaster:[4,[1,1,1],3,1,0,.2], paint:[5,[1,1,1],2,1,0,.05], lath:[4,[1,1,1],3,1,0,.35],
  wood:[6,[1,1,1],1.2,1,0,1.2], parquet:[8,[1,1,1],2.4,1,0,.5], plank:[7,[1,1,1],2.4,1,0,.5], tile:[9,[1,1,1],1.2,1,0,.8], terrazzo:[10,[1,1,1],1.4,1,0,.1],
  concrete:[11,[1,1,1],2.5,1,0,.5], carpet:[12,[.62,.24,.22],1.2,1,0,.6], metal:[13,[.6,.6,.62],1,1,1,.25], bronze:[13,[.42,.27,.15],1,1.2,1,.25],
  gilt:[13,[.95,.72,.34],.8,1.1,1,.3], copper:[13,[.86,.5,.36],1,1.1,1,.25], fabric:[12,[.5,.47,.44],1,1,0,.5], leather:[14,[.26,.14,.08],1,1,0,.15],
  slate:[9,[.3,.31,.34],1.2,1,0,.6], terracotta:[9,[.82,.47,.33],1.2,1,0,.8], glass:[-1], none:[-1],
  paving:[15,[1,1,1],6,1,0,1], bark:[11,[.42,.33,.25],1.5,1,0,.8], flags:[15,[.86,.84,.82],3.2,.9,0,1], coffer:[17,[1,1,1],4.2,1,0,1.6], leaf:[18,[1,1,1],2,1,0,1], rooftile:[16,[1,1,1],2.4,1,0,1.2], patina:[11,[.42,.66,.58],3,1,0,.4], board:[7,[.92,.86,.78],2.4,1,0,.5], kasota:[19,[1,1,1],3.2,1,0,.3], oak:[6,[.66,.62,.6],1.2,1,0,1.2], pine:[6,[1.5,1.32,1.12],1.2,1,0,1.1], panelpaint:[20,[.86,.86,.8],1.2,1,0,.8], boiserie:[21,[1,1,1],1.2,1,0,.8], statuary:[4,[.96,.95,.92],1.5,.5,0,.04], giltpol:[13,[1,.78,.42],3,.5,1,.03], benchtop:[12,[.34,.27,.22],1.2,1,0,.3] };
var GEN_N=22;
/* per-material world-space variation [macro, per tile, grime near the floor] and slab joints [size m, width m, tone] */
var VAR={0:[.08,0,.15,1],1:[.16,.05,.5],2:[.08,0,.2,1],3:[.12,.04,.4],4:[.05,0,.14,1],5:[.04,0,.1,1],6:[.1,0,.05],7:[.12,0,.08],8:[.1,0,.06],9:[.06,.03,.15],10:[.08,0,.1,1],11:[.14,.05,.3,1],12:[.08,0,0,1],15:[.18,.06,.2],16:[.2,.05,0],17:[.04,0,0],18:[.2,0,0],19:[.12,.04,.35,1]};
function matName(m,dflt){ if(!m) return dflt; if(MAT[m]) return m; var s=String(m).toLowerCase();
  var ks=['panelpaint','boiserie','oak','pine','kasota','marble','limestone','sandstone','granite','brick','plaster','paint','parquet','plank','tile','terrazzo','concrete','carpet','glass','bronze','gilt','copper','metal','leather','slate','wood','stone','fabric'];
  for(var i=0;i<ks.length;i++) if(s.indexOf(ks[i])>=0) return ks[i]; return dflt; }
var PAINTS=[[.93,.91,.87],[.88,.86,.82],[.9,.88,.84],[.84,.83,.8],[.74,.77,.72],[.58,.22,.2],[.38,.44,.52],[.8,.75,.68],[.5,.56,.48],[.34,.36,.44],[.92,.9,.86],[.66,.62,.56]];
var LIGHT={sky:400, day:320, art:220, mixed:260, dim:70};
function defLight(ty){ return ty==='gallery'?'art':ty==='court'||ty==='hall'||ty==='lobby'||ty==='stair-hall'?'day':ty==='corridor'||ty==='service'||ty==='stair'||ty==='lift'||ty==='restroom'?'dim':'mixed'; }
function defFloor(ty){ return ty==='gallery'?'parquet':ty==='hall'||ty==='lobby'||ty==='stair-hall'||ty==='court'?'marble':ty==='corridor'?'terrazzo':ty==='service'?'concrete':ty==='library'||ty==='reading-room'||ty==='office'?'plank':ty==='restroom'?'tile':'marble'; }
function defWall(ty){ return ty==='gallery'?'paint':ty==='hall'||ty==='stair-hall'||ty==='court'?'limestone':'plaster'; }
function enc4(m){ return m==null?255:clamp(Math.round(m/4*255),0,255); }

function bfIndex(plan){
  plan=Object.assign({},plan); plan.fx=(plan.fx||[]).map(function(f){ var o=Object.assign({},f); if(f.p) o.p=f.p.slice(); return o; });     /* fixtures may be nudged: never the blueprint's copy */
  var G={plan:plan, lvs:[], lv:{}, rooms:[], rid:{}, rg:{}, walls:[], prims:[], pg:{}, st:[], portals:[], batches:[], picks:[], slots:{}, fxs:{}, lifts:[], rails:[]};
  (plan.lv||[]).slice().sort(function(a,b){ return a.e-b.e; }).forEach(function(l,i){ var o={id:l.id, n:l.n||l.id, lb:l.lb||l.n||l.id, e:l.e, h:l.h||4, i:i}; G.lvs.push(o); G.lv[l.id]=o; });
  G.lvs.forEach(function(o,i){ var nx=G.lvs[i+1]; o.top=nx?nx.e:o.e+o.h; o.wh=Math.max(o.h,o.top-o.e); });
  var ex=plan.ex||{}; G.gz=ex.gz!=null?ex.gz:(G.lvs[0]?G.lvs[0].e:0);
  (plan.rm||[]).forEach(function(r){ var l=G.lv[r.l]; if(!l||!r.p||r.p.length<3) return; var ty=r.ty||'other';
    var o={i:G.rooms.length, r:r, id:r.id, l:l, p:r.p, bb:bb2(r.p), ch:r.ch||l.h, ty:ty, holesF:[], holesC:[], items:[], nb:[], wins:[], name:r.n||r.id, no:r.no||''};
    o.ceil=l.e+o.ch; o.fm=matName(r.fm,defFloor(ty)); o.wm=matName(r.wm,defWall(ty)); o.cm=matName(r.cm,'plaster'); o.lk=(r.li&&r.li.k)||defLight(ty); o.lx=(r.li&&r.li.lx)||LIGHT[o.lk]||250;
    o.paint=PAINTS[Math.floor(hash((r.ca||r.id)+'p')*PAINTS.length)]; if(ty!=='gallery') o.paint=PAINTS[Math.floor(hash(r.id)*3)];
    o.wt=o.wm==='paint'?o.paint:({plaster:[.93,.91,.87],lath:[.93,.91,.87],wood:[.42,.28,.17],oak:[.3,.2,.13],pine:[.62,.45,.28],panelpaint:[.82,.82,.76],boiserie:[.93,.92,.88],kasota:[.86,.79,.64],limestone:[.86,.81,.72],marble:[.93,.92,.9],stone:[.78,.79,.8],brick:[.62,.34,.26],concrete:[.62,.62,.6]})[o.wm]||[.9,.88,.84];
    o.ctr=interior(r.p); G.rid[r.id]=o; G.rooms.push(o);
    for(var x=Math.floor(o.bb[0]/4);x<=Math.floor(o.bb[2]/4);x++) for(var y=Math.floor(o.bb[1]/4);y<=Math.floor(o.bb[3]/4);y++){ var k=l.id+':'+x+','+y; (G.rg[k]||(G.rg[k]=[])).push(o.i); } });
  adoptGaps(G);
  /* batches: one per room, one exterior batch per level, one site batch */
  G.rooms.forEach(function(o){ o.b=mkBatch(G,'room',o); o.b.bb=[o.bb[0],o.bb[1],o.l.e-.4,o.bb[2],o.bb[3],o.ceil+.2]; });
  G.lvs.forEach(function(l){ l.b=mkBatch(G,'ext',null); l.b.lv=l; });
  G.site=mkBatch(G,'site',null);
  G.rooms.forEach(function(r){ var A=(r.bb[2]-r.bb[0])*(r.bb[3]-r.bb[1]); G.lvs.forEach(function(l){ if(l.e<=r.l.e+.5||l.e>=r.ceil-.3) return;     /* a ceiling never pokes through the floor of a room above, unless that room shares its ceiling (an open hall and its balcony) */
      if(G.rooms.some(function(u){ return u.l===l&&Math.abs(u.ceil-r.ceil)>1&&ovl(u.bb,r.bb)>.3*Math.min(A,(u.bb[2]-u.bb[0])*(u.bb[3]-u.bb[1])); })){ r.ceil=l.e-.3; r.ch=r.ceil-r.l.e; } }); });
  voids(G); stairs(G); stairCuts(G); throughCuts(G); walls(G); gaps(G); voidRails(G); things(G); deadDoors(G); exterior(G); portals(G);
  return G; }
/* a floored gap between traced rooms (plan gp) is part of the room it opens from: that room's height, finishes, light and name, so it reads as one space */
function adoptGaps(G){ G.rooms.forEach(function(o){ if(!o.r.gp) return; var best=null, bs=0, e=[o.bb[0]-.5,o.bb[1]-.5,o.bb[2]+.5,o.bb[3]+.5];
    G.rooms.forEach(function(r){ if(r.l!==o.l||r.r.gp||r.isVoid) return; var s=ovl(e,[r.bb[0]-.5,r.bb[1]-.5,r.bb[2]+.5,r.bb[3]+.5]); if(s>bs){ bs=s; best=r; } });
    if(!best) return; o.of=best; ['ch','ceil','fm','wm','cm','lk','lx','paint','wt','name','no'].forEach(function(k){ o[k]=best[k]; }); }); }
function mkBatch(G,kind,room){ var b={i:G.batches.length, kind:kind, room:room, items:[], bb:[1e9,1e9,1e9,-1e9,-1e9,-1e9], built:null, picks:[], lastUse:0}; G.batches.push(b); return b; }
function grow(b,x0,y0,z0,x1,y1,z1){ var a=b.bb; if(x0<a[0]) a[0]=x0; if(y0<a[1]) a[1]=y0; if(z0<a[2]) a[2]=z0; if(x1>a[3]) a[3]=x1; if(y1>a[4]) a[4]=y1; if(z1>a[5]) a[5]=z1; }
function roomAt(G,lid,x,y){ var c=G.rg[lid+':'+Math.floor(x/4)+','+Math.floor(y/4)]; if(!c) return null;
  var v=null; for(var i=0;i<c.length;i++){ var o=G.rooms[c[i]]; if(x>=o.bb[0]&&x<=o.bb[2]&&y>=o.bb[1]&&y<=o.bb[3]&&pip(o.p,x,y)){ if(!o.isVoid) return o; v=o; } } return v; }
function roomNear(G,lid,x,y,nx,ny){ var ds=[.12,.4,.8,1.5]; for(var i=0;i<ds.length;i++){ var r=roomAt(G,lid,x+nx*ds[i],y+ny*ds[i]); if(r) return r; } return null; }
function batchOf(G,room,lv){ return room?room.b:lv.b; }
/* collision primitives on a 2 m grid: seg {ax,ay,bx,by,r}, box {x,y,hx,hy,c,s}, circ {x,y,r}; each with z0..z1 */
function addPrim(G,p){ var bb=p.k==='seg'?[Math.min(p.ax,p.bx)-p.r,Math.min(p.ay,p.by)-p.r,Math.max(p.ax,p.bx)+p.r,Math.max(p.ay,p.by)+p.r]:p.k==='box'?[p.x-p.R,p.y-p.R,p.x+p.R,p.y+p.R]:[p.x-p.r,p.y-p.r,p.x+p.r,p.y+p.r];
  p.i=G.prims.length; G.prims.push(p); for(var x=Math.floor(bb[0]/2);x<=Math.floor(bb[2]/2);x++) for(var y=Math.floor(bb[1]/2);y<=Math.floor(bb[3]/2);y++){ var k=x+','+y; (G.pg[k]||(G.pg[k]=[])).push(p.i); } }
function primsNear(G,x,y,r){ var out=[], seen={}; for(var X=Math.floor((x-r)/2);X<=Math.floor((x+r)/2);X++) for(var Y=Math.floor((y-r)/2);Y<=Math.floor((y+r)/2);Y++){ var c=G.pg[X+','+Y]; if(!c) continue; for(var i=0;i<c.length;i++) if(!seen[c[i]]){ seen[c[i]]=1; out.push(G.prims[c[i]]); } } return out; }
function boxPrim(G,x,y,w,d,rot,z0,z1,tag){ var c=Math.cos(rot), s=Math.sin(rot); addPrim(G,{k:'box',x:x,y:y,hx:w/2,hy:d/2,c:c,s:s,R:Math.hypot(w,d)/2,z0:z0,z1:z1,tag:tag}); }

function wallTop(w,lv){ return lv.e+(w.h!=null?w.h:lv.wh); }
function archTop(op,a){ if(!op.arch) return op.z1; var hw=(op.a1-op.a0)/2, x=a-(op.a0+op.a1)/2; return op.zc+Math.sqrt(Math.max(0,op.R*op.R-x*x)); }
/* traced plans put two walls side by side (an inner wall and the old outer shell, misregistered by a metre): a doorway in one then opens onto the solid
   face of the other. Where a room lies beyond that second wall the doorway goes through it too (a plain cut, same width and height); where none does,
   the doorway is recorded in G.dead (the walk audit reports it). The blueprint's plan is never changed: G.wl is the renderer's own copy. */
/* a flight always has a way on and off: a traced wall lying across the place where a flight starts or arrives (PMA: the small stairwells' enclosures)
   gets an opening as wide as the flight there (G.wl, the renderer's own copy of the walls; the blueprint is not changed) */
function stairCuts(G){ var wl=G.wl=(G.wl||(G.plan.wl||[]).slice()); G.scuts=[];
  G.st.forEach(function(o){ if(o.k==='elevator') return; o.fl.forEach(function(fl){ [[fl.a,-1],[fl.b,1]].forEach(function(en){ var E=en[0], dir=[fl.d[0]*en[1],fl.d[1]*en[1]], l=null;
      G.lvs.forEach(function(q){ if(Math.abs(q.e-E[2])<.3) l=q; }); if(!l) return;
      [0,.4,-.4].forEach(function(lat){ var nx=fl.n[0]*fl.w*lat, ny=fl.n[1]*fl.w*lat, P0=[E[0]-dir[0]*.15+nx,E[1]-dir[1]*.15+ny], P1=[E[0]+dir[0]*1.0+nx,E[1]+dir[1]*1.0+ny];        /* across the flight's width: a short wall piece beside the middle counts too */
      wl.forEach(function(w,wi){ if(w.l!==l.id||!w.p||w.k==='rail') return; var pts=w.p.slice(); if(w.loop) pts.push(pts[0]); var run=0;
        for(var i=0;i+1<pts.length;i++){ var A=pts[i], B=pts[i+1], ex=B[0]-A[0], ey=B[1]-A[1], L=Math.hypot(ex,ey); if(L<1e-6) continue;
          var fx=P1[0]-P0[0], fy=P1[1]-P0[1], den=fx*ey-fy*ex; if(Math.abs(den)>1e-9){ var t=((A[0]-P0[0])*ey-(A[1]-P0[1])*ex)/den, u=((A[0]-P0[0])*fy-(A[1]-P0[1])*fx)/den;
            if(t>=0&&t<=1&&u>=-.02&&u<=1.02){ var a=run+clamp(u,0,1)*L, ow=clamp(fl.w,CFG.minDoor,L), h=Math.min(2.4,(w.h!=null?w.h:l.wh)-.05);
              if(!(w.o||[]).some(function(q){ return q.k!=='window'&&(q.z||0)<=CFG.knee&&Math.abs(q.a-a)<q.w/2-.1; })){ if(w===(G.plan.wl||[])[wi]) w=wl[wi]=Object.assign({},w,{o:(w.o||[]).slice()}); w.o.push({k:'gap', a:a, w:ow, h:h, z:0, cut:1, st:1}); G.scuts.push({w:w.id, a:+a.toFixed(2), st:o.s.id}); } } }
          run+=L; } }); }); }); }); }); }
function throughCuts(G){ var wl=(G.wl||(G.plan.wl||[])).slice(), segsOf=function(w){ var pts=(w.p||[]).slice(), out=[], run=0; if(w.loop&&pts.length) pts.push(pts[0]);
    for(var i=0;i+1<pts.length;i++){ var A=pts[i], B=pts[i+1], dx=B[0]-A[0], dy=B[1]-A[1], L=Math.hypot(dx,dy); if(L<1e-6) continue; out.push({A:A, d:[dx/L,dy/L], n:[-dy/L,dx/L], L:L, s0:run}); run+=L; } return out; };
  var SG=wl.map(segsOf); G.cuts=[]; G.dead=[]; G.blind={};
  wl.forEach(function(w,wi){ var lv=G.lv[w.l]; if(!lv||w.k==='rail') return; (w.o||[]).forEach(function(o){ if(o.k==='window'||!(o.w>0)||(o.z||0)>CFG.knee||(o.z||0)+o.h<CFG.head+.1) return;
    var sg=null; SG[wi].forEach(function(q){ if(o.a>=q.s0-1e-6&&o.a<=q.s0+q.L+1e-6) sg=q; }); if(!sg) return; var u=o.a-sg.s0, c=[sg.A[0]+sg.d[0]*u,sg.A[1]+sg.d[1]*u], ht=(w.t||.2)/2, ow=Math.max(o.w,CFG.minDoor);
    /* a second wall traced on the same line (overlapping this one's thickness) and solid across the doorway: cut it too, when there is a room on both sides */
    if([1,-1].every(function(sd){ var r=roomAt(G,lv.id,c[0]+sg.n[0]*sd*(ht+.35),c[1]+sg.n[1]*sd*(ht+.35)); return r&&!r.isVoid; }))
      wl.forEach(function(w2,wj){ if(wj===wi||w2.l!==w.l||w2.k==='rail') return; var ht2=(w2.t||.2)/2; SG[wj].forEach(function(q){ if(Math.abs(q.d[0]*sg.d[0]+q.d[1]*sg.d[1])<.95) return;
        var rx=c[0]-q.A[0], ry=c[1]-q.A[1], t=rx*q.d[0]+ry*q.d[1], off=Math.abs(rx*q.n[0]+ry*q.n[1]); if(t<-.2||t>q.L+.2||off>=ht+ht2-.02) return;
        var a2=q.s0+clamp(t,0,q.L), w3=wl[wj]; if((w3.o||[]).some(function(o2){ return o2.k!=='window'&&(o2.z||0)<=CFG.knee&&Math.abs(o2.a-a2)<Math.max(.05,o2.w/2-ow/2+.05); })) return;
        if(w3===(G.plan.wl||[])[wj]) w3=wl[wj]=Object.assign({},w3,{o:(w3.o||[]).slice()}); w3.o.push({k:'gap', a:a2, w:o.w, h:o.h, z:o.z||0, cut:1}); G.cuts.push({w:w3.id, a:+a2.toFixed(2), for:w.id+'@'+o.a.toFixed(1), on:1}); }); });
    [1,-1].forEach(function(sd){ var hit=null, hd=1e9;
      wl.forEach(function(w2,wj){ if(wj===wi||w2.l!==w.l||w2.k==='rail') return; var ht2=(w2.t||.2)/2; SG[wj].forEach(function(q){ if(Math.abs(q.d[0]*sg.d[0]+q.d[1]*sg.d[1])<.95) return;
        var rx=c[0]-q.A[0], ry=c[1]-q.A[1], t=rx*q.d[0]+ry*q.d[1], dist=-(rx*q.n[0]+ry*q.n[1])*(q.n[0]*sg.n[0]+q.n[1]*sg.n[1]>0?1:-1)*sd;      /* how far along this side's normal the other wall's centre line lies */
        if(t<-.2||t>q.L+.2||dist<=.02||dist-ht-ht2>=2*CFG.pr+.1||dist>=hd) return;                 /* a gap the walker fits in is a passage, not a blocked door */ hd=dist; hit={w:w2, wj:wj, q:q, a:q.s0+clamp(t,0,q.L), ht2:ht2}; }); });
      if(!hit) return; var w2=wl[hit.wj], covered=(w2.o||[]).some(function(o2){ return o2.k!=='window'&&(o2.z||0)<=CFG.knee&&(o2.z||0)+o2.h>=CFG.head+.1&&Math.abs(o2.a-hit.a)<Math.max(.05,o2.w/2-ow/2+.05); });
      if(covered) return; var bx=c[0]+sg.n[0]*sd*(hd+hit.ht2+.4), by=c[1]+sg.n[1]*sd*(hd+hit.ht2+.4), rb=roomAt(G,lv.id,bx,by);
      if(!rb||rb.isVoid||rb.r.gp){ G.dead.push({w:w.id, a:o.a, side:sd, by:w2.id}); G.blind[w.id+'@'+o.a]=1; return; }                 /* nothing real beyond (outside, or a floor-only gap): the doorway is closed in the walk, never a door you cannot use */
      if(w2===(G.plan.wl||[])[hit.wj]) w2=wl[hit.wj]=Object.assign({},w2,{o:(w2.o||[]).slice()});
      w2.o.push({k:'gap', a:hit.a, w:ow, h:o.h, z:o.z||0, cut:1}); G.cuts.push({w:w2.id, a:+hit.a.toFixed(2), for:w.id+'@'+o.a.toFixed(1)}); }); }); });
  G.wl=wl; }
/* a doorway with no room to stand on one side (traced walls crowding it, a sliver of floor) is filled with a wall panel: collision and picture.
   Nothing in the walk is a door you cannot go through (G.dead lists them; the walk audit reports them). */
/* can the capsule slide straight from P to Q at floor e (free and floored all the way)? */
function reachLine(G,P,Q,e){ var L=Math.hypot(Q[0]-P[0],Q[1]-P[1]), n=Math.max(1,Math.ceil(L/.1)); for(var i=0;i<=n;i++){ var x=P[0]+(Q[0]-P[0])*i/n, y=P[1]+(Q[1]-P[1])*i/n, sp=supportDisc(G,x,y,e+.3); if(sp==null||Math.abs(sp-e)>.3||blockedAt(G,x,y,e)) return false; } return true; }
function deadDoors(G){ var reach=function(P,Q,e){ return reachLine(G,P,Q,e); }; G.walls.forEach(function(W){ W.ops.forEach(function(op){ if(!op.pass||!op.sg||W.rail) return; var sg=op.sg, e=W.lv.e+(op.o.z||0), um=(op.a0+op.a1)/2-sg.s0, c=[sg.A[0]+sg.d[0]*um,sg.A[1]+sg.d[1]*um];
    var hw=(op.a1-op.a0)/2, ls=[0]; for(var q=.3;q<hw-.2;q+=.3) ls.push(q,-q);                 /* across the whole opening: a wide one can have a column or a wall stub in its middle */
    var spot=function(cj,sd){ var os=[.45,.6,.75,.9,1.1,1.3,1.5]; for(var i=0;i<os.length;i++){ var o=W.ht+os[i], x=cj[0]+sg.n[0]*sd*o, y=cj[1]+sg.n[1]*sd*o, sp=supportAt(G,x,y,e+.3);
        if(sp!=null&&Math.abs(sp-e)<.15&&!blockedAt(G,x,y,e)&&reach(cj,[x,y],e)) return [x,y]; } return null; };
    if(W.k==='ext'&&!(op.ra&&op.rb)) return;                           /* an entrance: the outside is checked by the exterior, not here */
    if(op.o.st||G.st.some(function(o){ return o.k!=='elevator'&&o.fl.some(function(fl){ return segD(c[0],c[1],fl.a[0],fl.a[1],fl.b[0],fl.b[1])<fl.w/2+1.2; }); })) return;      /* a stair's way on or off: the flight is the room beyond */
    for(var j=0;j<ls.length;j++){ var cj=[c[0]+sg.d[0]*ls[j],c[1]+sg.d[1]*ls[j]]; if(blockedAt(G,cj[0],cj[1],e)) continue; if(spot(cj,1)&&spot(cj,-1)){ op.passAt=ls[j]; return; } }       /* a straight way through at one place across it, room to stand on both sides */
    op.pass=false; op.plug=1; G.dead.push({w:W.w.id, a:op.o.a, side:0, by:'no room to stand'});
    var a=op.a0-sg.s0, b=op.a1-sg.s0; addPrim(G,{k:'seg', flat:1, ax:sg.A[0]+sg.d[0]*a, ay:sg.A[1]+sg.d[1]*a, bx:sg.A[0]+sg.d[0]*b, by:sg.A[1]+sg.d[1]*b, r:W.ht, z0:op.z0, z1:op.z1, wall:1, plug:1});
    [op.ra,op.rb].forEach(function(r,j){ var bt=batchOf(G,r,W.lv); bt.items=bt.items.filter(function(it){ return !(it.t==='op'&&it.op===op)&&!(it.t==='niche'&&it.op===op); }); bt.items.push({t:'plug', W:W, op:op, room:r, s:j?-1:1}); }); }); }); }
function walls(G){
  (G.wl||G.plan.wl||[]).forEach(function(w,wi){
    var lv=G.lv[w.l]; if(!lv||!w.p||w.p.length<2) return;
    var pts=w.p.slice(); if(w.loop) pts.push(pts[0]);
    var W={w:w, wi:wi, lv:lv, ht:Math.max(.01,(w.t||.2)/2), base:lv.e, top:wallTop(w,lv), exH:w.h!=null, k:w.k||'int', m:matName(w.m,'plaster'), segs:[], ops:[]};
    W.rail=W.k==='rail'; W.low=W.lv===G.lvs[0]&&W.k==='ext';
    var run=0;
    for(var i=0;i+1<pts.length;i++){ var A=pts[i], B=pts[i+1], dx=B[0]-A[0], dy=B[1]-A[1], L=Math.hypot(dx,dy); if(L<1e-6) continue;
      W.segs.push({A:A, B:B, L:L, d:[dx/L,dy/L], n:[-dy/L,dx/L], s0:run}); run+=L; }
    W.L=run; var ns=W.segs.length; if(!ns) return;
    if(W.k==='ext'&&!W.low&&lv.i>0){ var s0=W.segs[0], m0=[(s0.A[0]+s0.B[0])/2,(s0.A[1]+s0.B[1])/2], o0=W.ht+.6, dn=G.lvs[lv.i-1];        /* an outer wall with nothing under it reaches down to the ground */
      if(![1,-1].some(function(sd){ return roomAt(G,dn.id,m0[0]+s0.n[0]*o0*sd,m0[1]+s0.n[1]*o0*sd); })) W.low=true; }
    W.segs.forEach(function(sg,i){ var pv=i>0?W.segs[i-1]:(w.loop?W.segs[ns-1]:null), nx=i<ns-1?W.segs[i+1]:(w.loop?W.segs[0]:null);
      var k0=0, k1=0; if(pv){ var c0=1+pv.n[0]*sg.n[0]+pv.n[1]*sg.n[1]; k0=c0>.05?W.ht*(pv.n[0]*sg.d[0]+pv.n[1]*sg.d[1])/c0:0; }
      if(nx){ var c1=1+nx.n[0]*sg.n[0]+nx.n[1]*sg.n[1]; k1=c1>.05?W.ht*(nx.n[0]*sg.d[0]+nx.n[1]*sg.d[1])/c1:0; }
      sg.k0=k0; sg.k1=k1; sg.o0=!pv; sg.o1=!nx; });
    (w.o||[]).forEach(function(o){ if(!(o.w>0&&o.h>0)||(G.blind&&G.blind[w.id+'@'+o.a])) return; var z0=lv.e+(o.z||0), op={o:o, k:o.k, a0:Math.max(0,o.a-o.w/2), a1:Math.min(run,o.a+o.w/2), z0:z0, z1:Math.min(W.top,z0+o.h), arch:o.k==='arch'};
      if(o.k!=='window'&&op.a1-op.a0<CFG.minDoor&&run>=CFG.minDoor){ var oc=clamp(o.a,CFG.minDoor/2,run-CFG.minDoor/2); op.a0=oc-CFG.minDoor/2; op.a1=oc+CFG.minDoor/2; op.widened=1; }      /* a traced door narrower than the walker (PMA: 7 of 191) opens to 0.9 m: every doorway fits the capsule */
      if(op.arch){ var hw=(op.a1-op.a0)/2, rise=Math.min(hw,(op.z1-op.z0)*.45); op.R=(rise*rise+hw*hw)/(2*rise); op.zc=op.z1-op.R; op.zs=op.z1-rise; }
      op.pass=o.k!=='window'&&(o.z||0)<=CFG.knee&&(o.z||0)+o.h>=CFG.head+.1; op.W=W; W.ops.push(op); });
    G.walls.push(W);
    /* collision: the solid stretches between passable openings, per segment */
    W.segs.forEach(function(sg){ var cuts=[[0,sg.L]];
      W.ops.forEach(function(op){ if(!op.pass) return; var a=op.a0-sg.s0, b=op.a1-sg.s0; if(b<=0||a>=sg.L) return; var nc=[]; cuts.forEach(function(c){ if(b<=c[0]||a>=c[1]){ nc.push(c); return; } if(a>c[0]) nc.push([c[0],a]); if(b<c[1]) nc.push([b,c[1]]); }); cuts=nc; });
      cuts.forEach(function(c){ if(c[1]-c[0]<.01) return; var e0=c[0]<1e-6&&!sg.o0?W.ht:0, e1=c[1]>sg.L-1e-6&&!sg.o1?W.ht:0;      /* FLAT-ended (a box, not a capsule): a round cap reached half the wall's thickness into every doorway (a 0.9 m door in a 0.75 m wall left 0.15 m); at a corner the piece runs on by its half thickness so the corner stays closed */
        var up=G.lvs[lv.i+1], z1w=W.top; if(up&&W.top>up.e+CFG.knee){ var hits=0, nS=Math.max(2,Math.ceil((c[1]-c[0])/1.2));        /* a tall wall from below stops at the floor above wherever that floor runs over it (it has its own walls; PMA: G walls 12 m high blocked L1 doors) */
          for(var k2=0;k2<=nS;k2++){ var uu=c[0]+(c[1]-c[0])*k2/nS, qx=sg.A[0]+sg.d[0]*uu, qy=sg.A[1]+sg.d[1]*uu; if([0,1,-1].some(function(sd){ var r=roomAt(G,up.id,qx+sg.n[0]*sd*(W.ht+.3),qy+sg.n[1]*sd*(W.ht+.3)); return r&&!r.isVoid; })) hits++; }
          if(hits>(nS+1)/2){ z1w=up.e; G.clipped=(G.clipped||0)+1; } }
        var nI=0, nT=Math.max(2,Math.ceil((c[1]-c[0])/.5)); for(var k3=0;k3<=nT;k3++){ var u3=c[0]+(c[1]-c[0])*k3/nT, x3=sg.A[0]+sg.d[0]*u3, y3=sg.A[1]+sg.d[1]*u3; if(G.st.some(function(o){ return o.k!=='elevator'&&o.lo===lv&&pip(o.fp,x3,y3); })) nI++; }
        if(nI>(nT+1)*.6){ G.inStair=(G.inStair||0)+1; return; }             /* a wall of the lower floor standing inside a stairwell: the flights pass over it (PMA: it stopped walkers near the top) */
        var wp={k:'seg', flat:1, ax:sg.A[0]+sg.d[0]*(c[0]-e0), ay:sg.A[1]+sg.d[1]*(c[0]-e0), bx:sg.A[0]+sg.d[0]*(c[1]+e1), by:sg.A[1]+sg.d[1]*(c[1]+e1), r:W.ht, z0:W.low?Math.min(G.gz,W.base):W.base, z1:z1w, wall:1}; addPrim(G,wp); (W.cp||(W.cp=[])).push(wp); }); });
    if(!W.rail&&W.k!=='ext'&&W.segs.every(function(sg){ var mx=(sg.A[0]+sg.B[0])/2, my=(sg.A[1]+sg.B[1])/2, o=W.ht+.6, ra=roomAt(G,lv.id,mx+sg.n[0]*o,my+sg.n[1]*o), rb=roomAt(G,lv.id,mx-sg.n[0]*o,my-sg.n[1]*o);
        return ra&&ra===rb&&ra.ceil>lv.top+.5; })){ W.rail=1; W.top=W.base+1.05; W.m=(function(){ var sg=W.segs[0], r0=roomAt(G,lv.id,(sg.A[0]+sg.B[0])/2+sg.n[0]*(W.ht+.6),(sg.A[1]+sg.B[1])/2+sg.n[1]*(W.ht+.6)); return r0&&/^(limestone|stone)$/.test(r0.wm)?'kasota':'marble'; })(); W.bal=1; (W.cp||[]).forEach(function(q){ q.z1=Math.min(q.z1,W.top); }); }      /* a balustrade's collision is as high as the balustrade (it was the old wall's full height: an invisible wall over the rail) */
    if(W.rail){ var stoneRail=/^(marble|kasota|limestone|stone|sandstone|granite|concrete|brick)$/.test(W.m);
      W.segs.forEach(function(sg){ var mx=(sg.A[0]+sg.B[0])/2, my=(sg.A[1]+sg.B[1])/2, rr=roomAt(G,lv.id,mx+sg.n[0]*.3,my+sg.n[1]*.3)||roomAt(G,lv.id,mx-sg.n[0]*.3,my-sg.n[1]*.3), rb=batchOf(G,rr,lv);
        rb.items.push({t:stoneRail?'parapet':'rail', a:sg.A, b:sg.B, z:W.base, h:W.top-W.base, w:W.bal?Math.min(.45,W.ht*2):W.ht*2, m:W.m, bal:W.bal}); grow(rb,Math.min(sg.A[0],sg.B[0])-.2,Math.min(sg.A[1],sg.B[1])-.2,W.base,Math.max(sg.A[0],sg.B[0])+.2,Math.max(sg.A[1],sg.B[1])+.2,W.top+.1); });
      return; }
    /* faces: each side split where the room it faces changes */
    W.segs.forEach(function(sg){ [1,-1].forEach(function(s){
      var uS=s*sg.k0, uE=sg.L+s*sg.k1; if(uE-uS<.005) return;
      var at=function(u){ var x=sg.A[0]+sg.d[0]*u+sg.n[0]*s*(W.ht+.12), y=sg.A[1]+sg.d[1]*u+sg.n[1]*s*(W.ht+.12); var r=roomAt(G,lv.id,x,y);
        if(!r&&W.k!=='ext') r=roomNear(G,lv.id,x,y,sg.n[0]*s,sg.n[1]*s); return r?r.i:-1; };
      var u=clamp(uS+.02,uS,uE), cur=at(u), start=uS, step=.5;
      while(u<uE){ var un=Math.min(uE-.02,u+step), r=at(un);
        if(r!==cur){ var lo=u, hi=un; for(var it=0;it<7;it++){ var mid=(lo+hi)/2; if(at(mid)===cur) lo=mid; else hi=mid; } var cut=(lo+hi)/2; addFace(G,W,sg,s,start,cut,cur,uS,uE); start=cut; cur=r; }
        if(un>=uE-.02) break; u=un; }
      addFace(G,W,sg,s,start,uE,cur,uS,uE); }); });
    /* openings: reveals, frames, leaves go with the room on either side */
    W.ops.forEach(function(op){ var sg=segAt(W,(op.a0+op.a1)/2); if(!sg) return; op.sg=sg; var um=(op.a0+op.a1)/2-sg.s0;
      var cx=sg.A[0]+sg.d[0]*um, cy=sg.A[1]+sg.d[1]*um, ra=roomAt(G,lv.id,cx+sg.n[0]*(W.ht+.3),cy+sg.n[1]*(W.ht+.3)), rb=roomAt(G,lv.id,cx-sg.n[0]*(W.ht+.3),cy-sg.n[1]*(W.ht+.3));
      op.ra=ra; op.rb=rb; op.c=[cx,cy]; var host=ra||rb, b=batchOf(G,host,lv); op.side=ra?1:-1;
      if(op.pass){ var hw=W.ht+.5, u0=op.a0-sg.s0, u1=op.a1-sg.s0, at2=function(u,o){ return [sg.A[0]+sg.d[0]*u+sg.n[0]*o,sg.A[1]+sg.d[1]*u+sg.n[1]*o]; }, sp2=[at2(u0,hw),at2(u1,hw),at2(u1,-hw),at2(u0,-hw)], sb=bb2(sp2);       /* the floor under the doorway: rooms end at the wall faces, so without it the strip under every door had no floor (stand in a doorway and you fell to the floor below) */
        var sl={p:sp2, z:op.z0, bb:sb}; (G.sills||(G.sills=[])).push(sl); for(var gx=Math.floor(sb[0]/2);gx<=Math.floor(sb[2]/2);gx++) for(var gy=Math.floor(sb[1]/2);gy<=Math.floor(sb[3]/2);gy++){ var gk=gx+','+gy; ((G.sg||(G.sg={}))[gk]||(G.sg[gk]=[])).push(sl); } }
      if(W.k!=='ext'&&op.k!=='window'&&(ra?1:0)+(rb?1:0)===1){ op.niche=1; b.items.push({t:'niche', W:W, op:op, room:host, s:ra?-1:1}); }
      b.items.push({t:'op', W:W, op:op}); grow(b,cx-op.o.w,cy-op.o.w,op.z0,cx+op.o.w,cy+op.o.w,op.z1);
      if(op.k==='window'){ [ra,rb].forEach(function(r,j){ if(r&&!(ra&&rb)) r.wins.push({c:[cx,cy,(op.z0+op.z1)/2], U:[sg.d[0],sg.d[1],0], hw:(op.a1-op.a0)/2, hh:(op.z1-op.z0)/2, n:j===0?[sg.n[0],sg.n[1],0]:[-sg.n[0],-sg.n[1],0], ext:W.k==='ext'}); }); }
      if(op.k==='door'&&op.o.d!=='none'&&op.pass){ var side=ra?-1:1; if(W.k!=='ext') side=ra?1:-1; op.leafSide=side; var lw=op.o.d==='single'?(op.a1-op.a0):(op.a1-op.a0)/2;
        var hinge=op.o.d==='single'?[op.a0]:[op.a0,op.a1]; hinge.forEach(function(a,j){ var u2=a-sg.s0+(j?-.03:.03), px=sg.A[0]+sg.d[0]*u2+sg.n[0]*side*(W.ht+lw/2), py=sg.A[1]+sg.d[1]*u2+sg.n[1]*side*(W.ht+lw/2);
          boxPrim(G,px,py,.06,lw,Math.atan2(sg.d[1],sg.d[0]),op.z0,op.z1); }); }
    });
  }); }
/* traced plans have gaps: a room edge with no wall and no room beyond it gets a plain wall; an interior door that leads to no room opens on an alcove */
function gaps(G){ G.rooms.forEach(function(r){ if(r.isVoid) return; var p=r.p, sg=parea(p)>0?1:-1, e=r.l.e;
    for(var i=0;i<p.length;i++){ var A=p[i], B=p[(i+1)%p.length], L=Math.hypot(B[0]-A[0],B[1]-A[1]); if(L<.4) continue; var ux=(B[0]-A[0])/L, uy=(B[1]-A[1])/L, ox=uy*sg, oy=-ux*sg, run=null, n=Math.ceil(L/.5);
      var flush=function(t1){ if(run!=null&&t1-run>.6){ var P0=[A[0]+ux*run,A[1]+uy*run], P1=[A[0]+ux*t1,A[1]+uy*t1]; r.b.items.push({t:'gapwall', a:P0, b:P1, n:[-ox,-oy], room:r});
          addPrim(G,{k:'seg', ax:P0[0], ay:P0[1], bx:P1[0], by:P1[1], r:.1, z0:e, z1:r.ceil, wall:1}); } run=null; };
      for(var k=0;k<=n;k++){ var t=Math.min(L,k*L/n), x=A[0]+ux*t, y=A[1]+uy*t, z=e+1.2;
        var open=!primsNear(G,x,y,.9).some(function(q2){ return q2.k==='seg'&&q2.z0<=z&&q2.z1>=z&&segD(x,y,q2.ax,q2.ay,q2.bx,q2.by)<q2.r+.45; })&&!roomAt(G,r.l.id,x+ox*.5,y+oy*.5)&&!onOpening(x,y,z,G);
        var inside=G.st.some(function(o){ return pip(o.fp,x-ox*.3,y-oy*.3)||(o.k!=='elevator'&&(o.lo===r.l||o.hi===r.l)&&pip(o.fp,x+ox*.5,y+oy*.5)); });      /* a stairwell's edge has its balustrade (stairs()), and the flight arrives across it: never a plain wall */
        if(open&&!inside){ if(run==null) run=t; } else flush(t); }
      flush(L); } }); }
function gapwallItem(G,mb,it){ var r=it.room, A=it.a, B=it.b, n=it.n, k=wallKey(r,{m:r.wm}), e=r.l.e, c=r.ceil, L=Math.hypot(B[0]-A[0],B[1]-A[1]);
  mb.quad(k,[[A[0],A[1],e],[B[0],B[1],e],[B[0],B[1],c],[A[0],A[1],c]],[n[0],n[1],0],[[0,e],[L,e],[L,c],[0,c]]);
  var F={ox:A[0], oy:A[1], dx:(B[0]-A[0])/L, dy:(B[1]-A[1])/L, n:[n[0],n[1],0], uo:0}; strip(mb,'skirt#'+r.i,F,0,L,[[.016,e],[.016,e+.15],[.008,e+.165],[0,e+.175]]); };
function segAt(W,a){ for(var i=0;i<W.segs.length;i++){ var s=W.segs[i]; if(a>=s.s0-1e-6&&a<=s.s0+s.L+1e-6) return s; } return null; }
function addFace(G,W,sg,s,u0,u1,ri,uS,uE){ if(u1-u0<.004) return; var room=ri>=0?G.rooms[ri]:null;
  var fb=W.base, ft;
  if(room){ ft=W.exH?Math.min(W.top,room.ceil):room.ceil; if(W.rail||W.k==='screen') ft=Math.min(ft,W.top); }
  else { ft=W.top; if(W.low) fb=Math.min(G.gz,W.base); }
  var f={t:'face', W:W, sg:sg, s:s, u0:u0, u1:u1, room:room, fb:fb, ft:ft, c0:Math.abs(u0-uS)<1e-3&&!sg.o0?uS:null, c1:Math.abs(u1-uE)<1e-3&&!sg.o1?uE:null};
  var b=batchOf(G,room,W.lv); b.items.push(f);
  var x0=sg.A[0]+sg.d[0]*u0, y0=sg.A[1]+sg.d[1]*u0, x1=sg.A[0]+sg.d[0]*u1, y1=sg.A[1]+sg.d[1]*u1, m=W.ht+.3;
  grow(b,Math.min(x0,x1)-m,Math.min(y0,y1)-m,fb,Math.max(x0,x1)+m,Math.max(y0,y1)+m,ft); }

/* is a doorway (any opening but a window, on level lid) within d of the segment a-c? from the plan, before the walls are built */
function opNear(G,lid,a,c,d){ if(!G.opc){ G.opc=[]; (G.plan.wl||[]).forEach(function(w){ var pts=(w.p||[]).slice(); if(w.loop&&pts.length) pts.push(pts[0]); var run=0, sg=[];
      for(var i=0;i+1<pts.length;i++){ var A=pts[i], B=pts[i+1], L=Math.hypot(B[0]-A[0],B[1]-A[1]); if(L<1e-6) continue; sg.push({A:A, d:[(B[0]-A[0])/L,(B[1]-A[1])/L], L:L, s0:run}); run+=L; }
      (w.o||[]).forEach(function(o){ if(o.k==='window') return; sg.forEach(function(q){ if(o.a>=q.s0&&o.a<=q.s0+q.L) G.opc.push({l:w.l, x:q.A[0]+q.d[0]*(o.a-q.s0), y:q.A[1]+q.d[1]*(o.a-q.s0)}); }); }); }); }
  return G.opc.some(function(o){ return o.l===lid&&segD(o.x,o.y,a[0],a[1],c[0],c[1])<d; }); }
function stairs(G){
  (G.plan.st||[]).forEach(function(s){ var f=G.lv[s.from], t=G.lv[s.to]; if(!f||!t||!s.fp) return; var lo=f.e<=t.e?f:t, hi=f.e<=t.e?t:f;
    var o={s:s, k:s.k||'stair', lo:lo, hi:hi, fp:s.fp, bb:bb2(s.fp), fl:[], ld:[], rails:[]};
    if(o.k==='elevator'){ G.lifts.push(o); [lo,hi].forEach(function(l){ var r=roomAt(G,l.id,interior(s.fp)[0],interior(s.fp)[1])||nearestRoom(G,l,interior(s.fp));
        var b=batchOf(G,r,l); b.items.push({t:'lift', st:o, lv:l, room:r}); grow(b,o.bb[0],o.bb[1],l.e,o.bb[2],o.bb[3],l.e+3);
        for(var i=0,n=s.fp.length;i<n;i++){ var a=s.fp[i], c=s.fp[(i+1)%n]; if(opNear(G,l.id,a,c,1.2)) continue; addPrim(G,{k:'seg',ax:a[0],ay:a[1],bx:c[0],by:c[1],r:.08,z0:l.e,z1:l.e+2.6}); } }); G.st.push(o); return; }      /* the cab is open on the side a doorway faces: you walk in */
    var dl=[], fls=(s.fl&&s.fl.length)?s.fl:deriveFlights(s,lo,hi,dl,G);
    o.fl=fls.map(function(fl){ var a=fl.a, b=fl.b; if(a[2]>b[2]){ var x=a; a=b; b=x; } var dx=b[0]-a[0], dy=b[1]-a[1], L=Math.hypot(dx,dy)||1;
      return {a:a, b:b, w:fl.w||s.w||1.4, L:L, d:[dx/L,dy/L], n:[-dy/L,dx/L], H:b[2]-a[2], ramp:o.k==='ramp', esc:o.k==='escalator'}; });
    o.ld=(s.ld||[]).concat(dl).map(function(l){ return {p:l.p, z:l.z, bb:bb2(l.p)}; });
    var ctr=interior(s.fp), host=roomAt(G,lo.id,ctr[0],ctr[1])||nearestRoom(G,lo,ctr), b=batchOf(G,host,lo); o.host=host;
    o.fl.forEach(function(fl){ b.items.push({t:'flight', fl:fl, st:o, room:host}); var m=fl.w;
      grow(b,Math.min(fl.a[0],fl.b[0])-m,Math.min(fl.a[1],fl.b[1])-m,fl.a[2]-.4,Math.max(fl.a[0],fl.b[0])+m,Math.max(fl.a[1],fl.b[1])+m,fl.b[2]+1.2);
      [-1,1].forEach(function(sd){ var ox=fl.n[0]*sd*(fl.w/2+.09), oy=fl.n[1]*sd*(fl.w/2+.09);
        addPrim(G,{k:'seg', ax:fl.a[0]+ox, ay:fl.a[1]+oy, bx:fl.b[0]+ox, by:fl.b[1]+oy, r:.1, z0:fl.a[2]-.1, z1:fl.b[2]+1.0, flight:fl}); }); });
    o.ld.forEach(function(l){ b.items.push({t:'land', ld:l, st:o}); grow(b,l.bb[0],l.bb[1],l.z-.4,l.bb[2],l.bb[3],l.z+1); });
    G.rooms.forEach(function(r){ if(!bbHit(r.bb,o.bb)) return; if(r.l===hi&&!(r.vholes&&r.vholes.some(function(v){ return bbHit(o.bb,v); }))) r.holesF.push(s.fp); if(r.l===lo&&r.ceil>=hi.e-.8&&r.ceil<=hi.e+.4) r.holesC.push({p:s.fp, z1:hi.e}); });
    /* a balustrade round the stairwell above, except where a flight arrives */
    (G.railJobs||(G.railJobs=[])).push(function(){ for(var i=0,n=s.fp.length;i<n;i++){ var A=s.fp[i], B=s.fp[(i+1)%n], arr=G.st.some(function(o2){ return o2.k!=='elevator'&&o2.fl.some(function(fl){ return [fl.a,fl.b].some(function(E){ return Math.abs(E[2]-hi.e)<.4&&segD(E[0],E[1],A[0],A[1],B[0],B[1])<.6+fl.w/2*0; }); }); });      /* every stair's flights, run once all are known: a stacked stair starts where the one below arrives */
      var mx0=(A[0]+B[0])/2, my0=(A[1]+B[1])/2; if(arr||G.rooms.some(function(r){ return r.l===hi&&r.vholes&&r.vholes.some(function(v){ return mx0>=v[0]-.3&&mx0<=v[2]+.3&&my0>=v[1]-.3&&my0<=v[3]+.3; }); })) continue; var mx=(A[0]+B[0])/2, my=(A[1]+B[1])/2, nearWall=primsNear(G,mx,my,.6).some(function(p){ return p.wall&&p.k==='seg'&&segD(mx,my,p.ax,p.ay,p.bx,p.by)<p.r+.35&&p.z0<=hi.e+.5&&p.z1>hi.e+.5; });
      if(nearWall) continue; var rr=roomAt(G,hi.id,mx,my)||nearestRoom(G,hi,[mx,my]), rb=batchOf(G,rr,hi);
      rb.items.push({t:'rail', a:A, b:B, z:hi.e, m:'metal'}); grow(rb,Math.min(A[0],B[0]),Math.min(A[1],B[1]),hi.e,Math.max(A[0],B[0]),Math.max(A[1],B[1]),hi.e+1.1);
      addPrim(G,{k:'seg', ax:A[0], ay:A[1], bx:B[0], by:B[1], r:.04, z0:hi.e, z1:hi.e+1.05}); } });
    G.st.push(o); }); (G.railJobs||[]).forEach(function(f){ f(); }); G.railJobs=[]; }
function ovl(a,b){ var ix=Math.min(a[2],b[2])-Math.max(a[0],b[0]), iy=Math.min(a[3],b[3])-Math.max(a[1],b[1]); return ix>0&&iy>0?ix*iy:0; }
function voids(G){ G.voids=[];
  G.rooms.forEach(function(T){ G.lvs.forEach(function(l){ if(l.e<=T.l.e+.5||l.e>=T.ceil-1) return;
    var well=null; G.rooms.forEach(function(W){ if(W.l===l&&(/well|void|open to/i.test(W.name)||W.ty==='court')&&T.ceil>=W.ceil-1&&ovl(W.bb,T.bb)>.6*(W.bb[2]-W.bb[0])*(W.bb[3]-W.bb[1])) { W.isVoid=1; well=W; } });
    G.rooms.forEach(function(U){ if(U.l!==l||U.isVoid||T.ceil<U.ceil-1) return; if(ovl(T.bb,U.bb)<.5*(T.bb[2]-T.bb[0])*(T.bb[3]-T.bb[1])) return;
      var d=clamp(Math.min(T.bb[2]-T.bb[0],T.bb[3]-T.bb[1])*.12,2.5,4.5), h=well?[Math.max(well.bb[0],T.bb[0]),Math.max(well.bb[1],T.bb[1]),Math.min(well.bb[2],T.bb[2]),Math.min(well.bb[3],T.bb[3])]:[T.bb[0]+d,T.bb[1]+d,T.bb[2]-d,T.bb[3]-d];
      (G.plan.st||[]).forEach(function(st){ if(st.to!==l.id||!st.fp||st.k==='elevator') return; var fl=(st.fl&&st.fl.length)?st.fl[st.fl.length-1]:derive(st,G.lv[st.from],l), a=fl.a[2]<fl.b[2]?fl.a:fl.b, b=fl.a[2]<fl.b[2]?fl.b:fl.a, dx=b[0]-a[0], dy=b[1]-a[1];
        if(b[0]<h[0]||b[0]>h[2]||b[1]<h[1]||b[1]>h[3]) return; if(Math.abs(dx)>Math.abs(dy)){ if(dx<0) h[0]=Math.max(h[0],b[0]); else h[2]=Math.min(h[2],b[0]); } else { if(dy<0) h[1]=Math.max(h[1],b[1]); else h[3]=Math.min(h[3],b[1]); } });
      (G.plan.st||[]).forEach(function(st){ if(st.to!==l.id||!st.fp) return; var b=bb2(st.fp); if(bbHit(b,h)) h=[Math.min(h[0],b[0]),Math.min(h[1],b[1]),Math.max(h[2],b[2]),Math.max(h[3],b[3])]; });
      var hp=[[h[0],h[1]],[h[2],h[1]],[h[2],h[3]],[h[0],h[3]]]; U.holesF.push(hp); U.voidHole=h; (U.vholes||(U.vholes=[])).push(h); if(Math.abs(U.ceil-T.ceil)<.5) U.ceilHoles=(U.ceilHoles||[]).concat([T.p]);
      G.voids.push({T:T, U:U, h:hp, l:l}); }); }); }); }
function voidRails(G){ (G.voids||[]).forEach(function(v){ var l=v.l, hp=v.h, arr=[];
    G.st.forEach(function(o){ o.fl.forEach(function(fl){ if(Math.abs(fl.b[2]-l.e)<.4) arr.push(fl); }); });
    for(var i=0;i<4;i++){ var A=hp[i], B=hp[(i+1)%4], L=Math.hypot(B[0]-A[0],B[1]-A[1]), ux=(B[0]-A[0])/L, uy=(B[1]-A[1])/L, cut=[[0,L]];
      arr.forEach(function(fl){ if(segD(fl.b[0],fl.b[1],A[0],A[1],B[0],B[1])>1.2) return; var t=(fl.b[0]-A[0])*ux+(fl.b[1]-A[1])*uy, a=t-fl.w/2-.2, b=t+fl.w/2+.2, nc=[];
        cut.forEach(function(c){ if(b<=c[0]||a>=c[1]){ nc.push(c); return; } if(a>c[0]) nc.push([c[0],a]); if(b<c[1]) nc.push([b,c[1]]); }); cut=nc; });
      var edge=function(t){ var x=A[0]+ux*t, y=A[1]+uy*t, f=function(sd){ return supports(G,x-uy*sd*.4,y+ux*sd*.4).some(function(z){ return Math.abs(z-l.e)<.05; }); }; return !(f(1)&&f(-1))&&!opNear(G,l.id,[x,y],[x,y],1.0); };      /* the void's box is a rectangle: no parapet where floor runs on both sides (it crossed a doorway on L3) */
      cut=[].concat.apply([],cut.map(function(c){ var o=[], st=null, n=Math.max(1,Math.ceil((c[1]-c[0])/.5)); for(var k=0;k<=n;k++){ var t=c[0]+(c[1]-c[0])*k/n, e=edge(t); if(e&&st==null) st=t; if((!e||k===n)&&st!=null){ if(t-st>.3) o.push([st,t]); st=null; } } return o; }));
      cut.forEach(function(c){ if(c[1]-c[0]<.3) return; var P0=[A[0]+ux*c[0],A[1]+uy*c[0]], P1=[A[0]+ux*c[1],A[1]+uy*c[1]];
        v.U.b.items.push({t:'parapet', a:P0, b:P1, z:l.e, h:1.05, w:.32, m:/^(limestone|stone)$/.test(v.U.wm)?'kasota':'marble', bal:1}); addPrim(G,{k:'seg', ax:P0[0], ay:P0[1], bx:P1[0], by:P1[1], r:.16, z0:l.e, z1:l.e+1.05}); }); } }); }
function nearestRoom(G,l,p){ var best=null, bd=1e9; G.rooms.forEach(function(r){ if(r.l!==l) return; var d=Math.hypot(r.ctr[0]-p[0],r.ctr[1]-p[1]); if(d<bd){ bd=d; best=r; } }); return best; }
function derive(s,lo,hi){ var ang=(s.up!=null?s.up:90)*PI/180, ux=Math.cos(ang), uy=Math.sin(ang), vx=-uy, vy=ux, mn=1e9, mx=-1e9, vn=1e9, vm=-1e9;
  s.fp.forEach(function(p){ var u=p[0]*ux+p[1]*uy, v=p[0]*vx+p[1]*vy; mn=Math.min(mn,u); mx=Math.max(mx,u); vn=Math.min(vn,v); vm=Math.max(vm,v); });
  var v0=(vn+vm)/2; return {a:[mn*ux+v0*vx,mn*uy+v0*vy,lo.e], b:[mx*ux+v0*vx,mx*uy+v0*vy,hi.e], w:Math.min(s.w||(vm-vn),vm-vn)}; }

/* a stair with no drawn flights: one straight flight along `up` when that is a sane stair (<= 37 degrees); a traced stairwell is often a small box for a
   whole storey (PMA: 1.9 x 4.3 m for 6.6 m), which made a 60-70 degree ramp, sometimes across the narrow side; then it is a SWITCHBACK along the box's long
   side: two flights side by side and a landing at the turn (the same box, the same floors; walkable up and down) */
/* can you step off a stair end at P on level l? a room there (not a void) and no traced wall right across it without an opening (from the plan: the walls are not built yet) */
function endOk(G,l,P){ var r=roomAt(G,l.id,P[0],P[1]); if(!r||r.isVoid) return 0; var bad=(G.wl||G.plan.wl||[]).some(function(w){ if(w.l!==l.id||!w.p) return false; var pts=w.p.slice(); if(w.loop) pts.push(pts[0]);
    for(var i=0;i+1<pts.length;i++) if(segD(P[0],P[1],pts[i][0],pts[i][1],pts[i+1][0],pts[i+1][1])<(w.t||.2)/2+.3) return !opNear(G,l.id,P,P,1.0); return false; }); return bad?1:2; }
function deriveFlights(s,lo,hi,lands,G){ var one=derive(s,lo,hi), H=hi.e-lo.e, L1=Math.hypot(one.b[0]-one.a[0],one.b[1]-one.a[1]); if(H/Math.max(.01,L1)<=.75) return [one];
  var bb=bb2(s.fp), ex=bb[2]-bb[0], ey=bb[3]-bb[1], along=ex>=ey, ux=along?1:0, uy=along?0:1, sgn=Math.cos(((s.up!=null?s.up:90)*PI/180)-(along?0:PI/2))<-.3?-1:1;
  if(G){ var u0b=along?bb[0]:bb[1], Lb=along?ex:ey, vcb=(along?bb[1]+ey/2:bb[0]+ex/2), Q=function(u){ return along?[u,vcb]:[vcb,u]; }, lo0=Q(u0b-.6), hi0=Q(u0b+Lb+.6);
    var sc=function(sg2){ return sg2>0?endOk(G,lo,lo0)+endOk(G,hi,hi0):endOk(G,lo,hi0)+endOk(G,hi,lo0); }; var a1=sc(sgn), a2=sc(-sgn); if(a2>a1) sgn=-sgn; }      /* run the way both ends can be stepped off */
  var Lu=along?ex:ey, Wv=along?ey:ex, u0=along?bb[0]:bb[1], v0=along?bb[1]:bb[0], d=clamp(Wv/2,.9,1.4), lw=Wv/2, mid=lo.e+H/2;
  var P=function(u,v){ return along?[u,v]:[v,u]; }, uA=sgn>0?u0:u0+Lu, uT=sgn>0?u0+Lu-d:u0+d, uE=sgn>0?u0+Lu:u0;
  if(lw<1.0){ var vc=v0+Wv/2, S0=P(uA,vc), S1=P(uE,vc); return [{a:[S0[0],S0[1],lo.e], b:[S1[0],S1[1],hi.e], w:Wv-.1}]; }       /* too narrow for two flights side by side: one flight along the long side */
  var c0=v0+lw/2, c1=v0+lw*1.5, A=P(uA,c0), B=P(uT,c0), C=P(uT,c1), D=P(uA,c1);
  lands.push({p:[P(uT,v0),P(uE,v0),P(uE,v0+Wv),P(uT,v0+Wv)], z:mid});
  return [{a:[A[0],A[1],lo.e], b:[B[0],B[1],mid], w:lw-.06}, {a:[C[0],C[1],mid], b:[D[0],D[1],hi.e], w:lw-.06}]; }
function things(G){
  var P=G.plan;
  var cols=(P.cols||[]).filter(function(c){ return G.lv[c.l]&&c.p; }), skip={}, hm={};
  cols.forEach(function(c){ var l=G.lv[c.l]; if(roomAt(G,l.id,c.p[0],c.p[1])) return; var up=G.lvs[l.i+1]; if(!up) return;
    cols.forEach(function(d){ if(d.l===up.id&&!skip[d.id]&&Math.hypot(d.p[0]-c.p[0],d.p[1]-c.p[1])<.6&&!roomAt(G,up.id,d.p[0],d.p[1])){ skip[d.id]=1; hm[c.id]=(hm[c.id]||l.wh)+(d.h||up.wh); } }); });
  cols.forEach(function(c){ if(skip[c.id]) return; var l=G.lv[c.l];
    if(G.st.some(function(o){ return o.k!=='elevator'&&(o.lo===l||o.hi===l)&&o.fl.some(function(fl){ return flightZ(fl,c.p[0],c.p[1],-.15)!=null; }); })) return; var r=roomAt(G,l.id,c.p[0],c.p[1]), b=batchOf(G,r,l), h=hm[c.id]||c.h||(r?r.ch:l.h), R=c.r!=null?c.r:Math.max(c.sz[0],c.sz[1])/2;
    b.items.push({t:'col', c:c, z0:l.e, h:h, room:r}); grow(b,c.p[0]-R*1.4,c.p[1]-R*1.4,l.e,c.p[0]+R*1.4,c.p[1]+R*1.4,l.e+h);
    if(c.r!=null) addPrim(G,{k:'circ',x:c.p[0],y:c.p[1],r:c.r*1.15,z0:l.e,z1:l.e+h}); else boxPrim(G,c.p[0],c.p[1],c.sz[0]*1.1,c.sz[1]*1.1,0,l.e,l.e+h);
    if(r) r.items.push({blob:[c.p[0],c.p[1],R*1.2,R*1.2],rot:0,round:c.r!=null,str:.55}); });
  /* an entablature (architrave, frieze, cornice) over each run of free-standing outdoor columns; proportions assumed */
  var ex=cols.filter(function(c){ return !skip[c.id]&&c.r!=null&&c.r>.45&&!roomAt(G,c.l,c.p[0],c.p[1]); });
  ex.forEach(function(c,i){ var nd=1e9; ex.forEach(function(d,j){ if(j!==i&&d.l===c.l) nd=Math.min(nd,Math.hypot(d.p[0]-c.p[0],d.p[1]-c.p[1])); }); c._nd=nd; });
  ex.forEach(function(c,i){ ex.forEach(function(d,j){ if(j<=i||d.l!==c.l) return; var L=Math.hypot(d.p[0]-c.p[0],d.p[1]-c.p[1]); if(L>Math.min(c._nd,d._nd)*1.35||L>9) return;
    var l=G.lv[c.l], h=hm[c.id]||c.h||l.h, z=l.e+h, b=l.b; l.b.items.push({t:'entab', a:c.p, b:d.p, z:z, r:Math.max(c.r,d.r)}); grow(b,Math.min(c.p[0],d.p[0])-3,Math.min(c.p[1],d.p[1])-3,z-1,Math.max(c.p[0],d.p[0])+3,Math.max(c.p[1],d.p[1])+3,z+4); }); });
  /* the East Entrance pediment: a low (Greek, about 1:8) gable over the front colonnade with its roof running back to the facade. The PMA has eight pediments (Wikipedia; the central front is a Greek temple front);
     pitch, depth and tile colour are assumed, and the tympanum is left plain (its sculpture is not reproduced) */
  (function(){ var en=(P.en||[]).filter(function(e){ return (e.k||'main')==='main'; })[0]; if(!en||en.fc==null||!en.p) return; var l=G.lv[en.l]; if(!l) return;
    var fc=en.fc*PI/180, u=[Math.cos(fc),Math.sin(fc)], vd=[-u[1],u[0]], groups={}, best=null;
    l.b.items.forEach(function(it){ if(it.t!=='entab') return; var dx=it.b[0]-it.a[0], dy=it.b[1]-it.a[1], L=Math.hypot(dx,dy)||1; if(Math.abs((dx*u[0]+dy*u[1])/L)>.2) return;
      var s=((it.a[0]+it.b[0])/2-en.p[0])*u[0]+((it.a[1]+it.b[1])/2-en.p[1])*u[1]; if(s<2) return; var key=Math.round(s/.8)+'|'+Math.round(it.z*2), g=groups[key]||(groups[key]={s:0,n:0,z:it.z,r:0,v0:1e9,v1:-1e9,len:0});
      [it.a,it.b].forEach(function(q){ var v=(q[0]-en.p[0])*vd[0]+(q[1]-en.p[1])*vd[1]; g.v0=Math.min(g.v0,v); g.v1=Math.max(g.v1,v); }); g.s+=s; g.n++; g.r=Math.max(g.r,it.r); g.len+=L; });
    for(var k in groups){ var g=groups[k]; if(!best||g.len>best.len) best=g; } if(!best||best.n<3) return;
    var ov=best.r*1.35, v0=best.v0-ov, v1=best.v1+ov, rise=(v1-v0)*.125, o={t:'pedi', o:en.p, u:u, vd:vd, s0:best.s/best.n+best.r*.5, sb:.6, v0:v0, v1:v1, z:best.z+best.r*2.73, rise:rise}, xs=[], ys=[];
    [o.s0+1,o.sb].forEach(function(sv){ [v0-1,v1+1].forEach(function(vv){ xs.push(en.p[0]+u[0]*sv+vd[0]*vv); ys.push(en.p[1]+u[1]*sv+vd[1]*vv); }); });
    l.b.items.push(o); grow(l.b,Math.min.apply(null,xs),Math.min.apply(null,ys),o.z-.5,Math.max.apply(null,xs),Math.max.apply(null,ys),o.z+rise+2); })();
  /* a statue (and the plinth under it) stands clear of the walls, facing away from the nearest one */
  (P.fx||[]).forEach(function(f){ var l=G.lv[f.l]; if(f.k!=='statue'||!l||!f.p||!f.sz||f._moved) return; var need=Math.max(f.sz[0],f.sz[1])*.5+1.0, x=f.p[0], y=f.p[1], push=[0,0];
    primsNear(G,x,y,need+1).forEach(function(q2){ if(!q2.wall||q2.z1<l.e-.3||q2.z0>l.e+2) return; var d=primDist(q2,x,y); if(d>=need) return; var e=.01, gx=(primDist(q2,x+e,y)-primDist(q2,x-e,y))/(2*e), gy=(primDist(q2,x,y+e)-primDist(q2,x,y-e))/(2*e), gl=Math.hypot(gx,gy)||1;
      push[0]+=gx/gl*(need-d); push[1]+=gy/gl*(need-d); });
    if(push[0]||push[1]){ var np=[x+push[0],y+push[1]]; (P.fx||[]).forEach(function(o){ if(o.l===f.l&&o.p&&Math.hypot(o.p[0]-x,o.p[1]-y)<.6) { o.p=np.slice(); o._moved=1; } });
      if(f.rot==null||f.rot===0) f.rot=Math.atan2(push[1],push[0])*180/PI-90; } });
  var plinths=(P.fx||[]).filter(function(f){ return f.k==='plinth'&&f.p&&f.sz; });
  (P.fx||[]).forEach(function(f){ var l=G.lv[f.l]; if(!l||!f.p||!f.sz) return; var r=roomAt(G,l.id,f.p[0],f.p[1]), b=batchOf(G,r,l), rot=(f.rot||0)*PI/180, R=Math.hypot(f.sz[0],f.sz[1])/2;
    var on=0; if(f.k==='statue') plinths.forEach(function(q2){ if(q2.l===f.l&&Math.hypot(q2.p[0]-f.p[0],q2.p[1]-f.p[1])<.6) on=Math.max(on,q2.sz[2]); });
    b.items.push({t:'fx', f:f, z0:l.e, rot:rot, room:r, on:on}); grow(b,f.p[0]-R,f.p[1]-R,l.e,f.p[0]+R,f.p[1]+R,l.e+on+f.sz[2]+.5);
    if(f.k==='statue'&&r) r.items.push({statue:f, z:l.e+on+f.sz[2]*.55, h:f.sz[2]});
    boxPrim(G,f.p[0],f.p[1],f.sz[0],f.sz[1],rot,l.e,l.e+Math.max(f.sz[2],f.k==='bench'?.5:f.sz[2]),f.id); G.fxs[f.id]={f:f,l:l,r:r};
    if(r) r.items.push({blob:[f.p[0],f.p[1],f.sz[0]/2,f.sz[1]/2],rot:rot,round:false,str:f.k==='bench'?.35:.5});
    b.picks.push({k:'fx', id:f.id, box:{x:f.p[0],y:f.p[1],hx:f.sz[0]/2+.02,hy:f.sz[1]/2+.02,c:Math.cos(rot),s:Math.sin(rot),z0:l.e,z1:l.e+f.sz[2]+(f.k==='statue'?0:.4)}, room:r}); });
  var mkSlot=function(s,si){ var r=G.rid[s.rm]; if(!r||!s.p||!s.sz) return; var l=r.l, b=r.b, fc=(s.fc||0)*PI/180, n=[Math.cos(fc),Math.sin(fc)], al=s.al||['any'];
    var sculpt=(al.indexOf('sculpture')>=0||al.indexOf('object')>=0)&&!s.w&&!al.some(function(a){ return a==='painting'||a==='drawing'||a==='print'||a==='tapestry'; });
    var edge=1e9; for(var i=0,m=r.p.length;i<m;i++){ var a=r.p[i], c=r.p[(i+1)%m]; edge=Math.min(edge,segD(s.p[0],s.p[1],a[0],a[1],c[0],c[1])); }
    if(sculpt&&edge<.6) sculpt=false;
    var it={t:'slot', s:s, si:si, room:r, n:n, d:[-n[1],n[0]], z:l.e+s.z, sculpt:sculpt, ord:r.items.filter(function(x){ return x.t==='slot'; }).length};
    r.items.push(it); b.items.push(it); G.slots[s.id]=it;
    var W=s.sz[0], H=s.sz[1];
    if(sculpt){ boxPrim(G,s.p[0],s.p[1],Math.max(.5,W*1.1),Math.max(.5,W*1.1),fc,l.e,l.e+2); r.items.push({blob:[s.p[0],s.p[1],Math.max(.25,W*.55),Math.max(.25,W*.55)],rot:fc,round:false,str:.5});
      b.picks.push({k:'slot', id:s.id, box:{x:s.p[0],y:s.p[1],hx:Math.max(.3,W*.6),hy:Math.max(.3,W*.6),c:1,s:0,z0:l.e,z1:l.e+1+H}, room:r}); }
    else b.picks.push({k:'slot', id:s.id, rect:{c:[s.p[0]+n[0]*.03,s.p[1]+n[1]*.03,it.z], n:[n[0],n[1],0], d:[-n[1],n[0],0], hw:W/2+.2, hh:H/2+.1}, room:r}); };
  G.mkSlot=mkSlot; (P.sl||[]).forEach(mkSlot); }

/* a card that sits in a ROOM (not on a wall slot) stands there as a sign: number, section colour and title, readable from both sides, E opens it */
/* a spot inside the room, on its floor (not over a stairwell or the open hall), clear of walls and fixtures, nearest the wanted point */
function cardSpot(G,r,dx,dy,base){ var c=base||r.ctr, wx=c[0]+dx, wy=c[1]+dy, e=r.l.e, best=null, bd=1e9;
  for(var rad=0;rad<=14;rad+=.5) for(var a=0;a<(rad?16:1);a++){ var t=a/16*2*PI, x=wx+Math.cos(t)*rad, y=wy+Math.sin(t)*rad; if(!pip(r.p,x,y)) continue;
    var sp=supportAt(G,x,y,e+.2); if(sp==null||Math.abs(sp-e)>.12||blockedAt(G,x,y,e)) continue; if(r.holesF&&r.holesF.some(function(h){ return pip(h,x,y); })) continue; if(inWay(G,x,y,e)) continue;
    var d=Math.hypot(x-wx,y-wy); if(d<bd){ bd=d; best=[x,y]; } } if(best) return best; return base?base:[r.ctr[0],r.ctr[1]]; }
/* is (x,y) in the way: within 1.3 m of a doorway's middle or of a stair's end on this floor, or on a stair? (card signs never stand there) */
function inWay(G,x,y,e){ if(onStair(G,x,y)) return true; for(var i=0;i<G.walls.length;i++){ var W=G.walls[i]; if(Math.abs(W.lv.e-e)>.3) continue; for(var j=0;j<W.ops.length;j++){ var op=W.ops[j]; if(op.pass&&op.c&&Math.hypot(x-op.c[0],y-op.c[1])<1.3+(op.a1-op.a0)/2) return true; } }
  return G.st.some(function(o){ return o.fl.some(function(fl){ return [fl.a,fl.b].some(function(E){ return Math.abs(E[2]-e)<.3&&Math.hypot(x-E[0],y-E[1])<1.5+fl.w/2; }); }); }); }
function addCards(G){ var d=S.data||{}, ns=d.nodes||{}, ord=d.order||Object.keys(ns), per={}; G.cards=[];
  ord.forEach(function(id){ var n=ns[id]; if(!n||!n.r||n.s) return; var r=G.rid[n.r]; if(!r) return; var k=per[r.id]=(per[r.id]||0); per[r.id]++;
    var c=cardSpot(G,r,0,0), dx=(k%2?1:-1)*Math.ceil(k/2)*1.6, p=cardSpot(G,r,dx,0,c), si=(G.plan.sl||[]).length+G.cards.length;
    var bw=r.bb[2]-r.bb[0], bd=r.bb[3]-r.bb[1], cw=clamp(.8+.1*Math.min(bw,bd),1.2,2.6), ch=cw*.65;                 /* big rooms get bigger signs; the sign faces along the room's long axis, where people walk */
    var s={id:'card-'+id, rm:r.id, p:[p[0],p[1]], z:.55+ch/2, sz:[cw,ch], fc:bw>=bd?0:90, al:['text'], card:1, work:{title:dec(n.t)}};
    G.mkSlot(s,si); G.cards.push(id); boxPrim(G,p[0],p[1],.5,.4,0,r.l.e,r.l.e+.55+ch,s.id); }); }
function cardPaint(g,x,y,C,asp,it){ var d=S.data||{}, id=String(it.s.id).slice(5), n=(d.nodes||{})[id]||{}, ac=(d.acts&&d.acts[n.a])||{}, col=ac.c||'#7c5cff', VW=C*asp, VH=C, F='-apple-system,"Segoe UI",Helvetica,Arial,sans-serif';
  g.save(); g.beginPath(); g.rect(x,y,C,C); g.clip(); g.translate(x,y); g.scale(1/asp,1);
  g.fillStyle='#f7f2e8'; g.fillRect(0,0,VW,VH); g.fillStyle=col; g.fillRect(0,0,VW*.05,VH); g.fillRect(0,VH*.93,VW,VH*.07);
  g.fillStyle=col; g.font='700 '+Math.round(VH*.2)+'px '+F; g.fillText(String(n.n||''),VW*.09,VH*.27);
  var words=dec(n.t).split(/\s+/), lines=[], cur=''; g.font='600 '+Math.round(VH*.135)+'px '+F; words.forEach(function(w){ var t=cur?cur+' '+w:w; if(g.measureText(t).width>VW*.84&&cur){ lines.push(cur); cur=w; } else cur=t; }); if(cur) lines.push(cur);
  if(lines.length>3){ lines=lines.slice(0,3); lines[2]=lines[2].replace(/.{0,2}$/,'…'); } g.fillStyle='#1d1b18'; lines.forEach(function(t,i){ g.fillText(t,VW*.09,VH*(.47+i*.16)); });
  g.fillStyle='#6b665c'; g.font=Math.round(VH*.075)+'px '+F; g.fillText((ac.n?String(ac.n)+'  ·  ':'')+'press E to open',VW*.09,VH*.89); g.restore(); }
function roomHasWin(G,r){ if(r.hasWin!=null) return r.hasWin; var has=false, p=r.p;
  for(var i=0;i<G.walls.length&&!has;i++){ var W=G.walls[i]; if(W.lv!==r.l) continue;
    for(var j=0;j<W.ops.length;j++){ var o=W.ops[j]; if(o.k!=='window'||!o.sg) continue; var sg=o.sg, u=(o.a0+o.a1)/2-sg.s0, x=sg.A[0]+sg.d[0]*u, y=sg.A[1]+sg.d[1]*u;
      for(var q=0,n=p.length;q<n;q++){ var a=p[q], b=p[(q+1)%n], dx=b[0]-a[0], dy=b[1]-a[1], l2=dx*dx+dy*dy||1, t=Math.max(0,Math.min(1,((x-a[0])*dx+(y-a[1])*dy)/l2)); if(Math.hypot(x-a[0]-t*dx,y-a[1]-t*dy)<1.2){ has=true; break; } }
      if(has) break; } }
  r.hasWin=has; return has; }
function exterior(G){ var ex=G.plan.ex||{}, sb=G.site;
  var wtop=-1e9; G.walls.forEach(function(W){ if(W.k==='ext') wtop=Math.max(wtop,W.top); });
  (ex.sh||[]).forEach(function(sh){ if(!sh.p||sh.p.length<3) return; var z0=wtop>-1e8?Math.max(wtop-.02,sh.z!=null?sh.z:G.gz):(sh.z!=null?sh.z:G.gz), bb=bb2(sh.p), top=Math.max(sh.h+(sh.z||0),z0);
    var tall=[]; G.rooms.filter(function(r){ return r.ceil>top-.1&&pip(sh.p,r.ctr[0],r.ctr[1])&&!r.isVoid; }).sort(function(a,b){ return Math.abs(parea(b.p))-Math.abs(parea(a.p)); })
      .forEach(function(r){ if(!tall.some(function(t){ return ovl(t.bb,r.bb)>.5*(r.bb[2]-r.bb[0])*(r.bb[3]-r.bb[1]); })) tall.push(r); });   /* one raised roof per hall (a hall and its balcony share one) */
    sb.items.push({t:'shell', sh:sh, z0:z0, top:top, solid:wtop<-1e8, tall:tall});
    if(z0>G.gz+.5){ if(!G.back) G.back=mkBatch(G,'back',null); G.back.items.push({t:'backing', sh:sh, z0:G.gz-.2, z1:z0+.05}); grow(G.back,bb[0]-1,bb[1]-1,G.gz-.2,bb[2]+1,bb[3]+1,z0+.1); }
    tall.forEach(function(r){ grow(sb,r.bb[0],r.bb[1],top,r.bb[2],r.bb[3],r.ceil+1.2); }); grow(sb,bb[0]-1,bb[1]-1,G.gz,bb[2]+1,bb[3]+1,top+((sh.rf&&sh.rf.h)||0)+(sh.rf&&sh.rf.k==='dome'?Math.min(bb[2]-bb[0],bb[3]-bb[1])*.5:0)+.5);
    if(wtop<-1e8) for(var i=0,n=sh.p.length;i<n;i++){ var a=sh.p[i], c=sh.p[(i+1)%n]; addPrim(G,{k:'seg',ax:a[0],ay:a[1],bx:c[0],by:c[1],r:.2,z0:G.gz,z1:top}); } });
  (ex.stp||[]).forEach(function(s){ if(!s.p) return; var bb=bb2(s.p); sb.items.push({t:'steps', s:s}); grow(sb,bb[0],bb[1],G.gz,bb[2],bb[3],Math.max(s.z0,s.z1)); });
  (ex.tr||[]).forEach(function(t){ if(!t.p) return; var bb=bb2(t.p); sb.items.push({t:'terr', tr:t}); grow(sb,bb[0],bb[1],G.gz,bb[2],bb[3],t.z); });
  var B=AltoBounds(G); G.B=B; trees(G,sb,ex); var c=[(B[0]+B[2])/2,(B[1]+B[3])/2], R=Math.max(B[2]-B[0],B[3]-B[1])/2+260;
  sb.items.push({t:'ground', c:c, R:R}); grow(sb,c[0]-R,c[1]-R,G.gz-.1,c[0]+R,c[1]+R,G.gz+.1); }
function trees(G,sb,ex){ var areas=[].concat(ex.stp||[],ex.tr||[]).filter(function(a){ return a.p; }), shells=(ex.sh||[]).map(function(s){ return s.p; }), out=[];
  var clear=function(x,y){ if(areas.some(function(a){ var b=bb2(a.p); return x>b[0]-2.5&&x<b[2]+2.5&&y>b[1]-2.5&&y<b[3]+2.5; })) return false; if(shells.some(function(p){ var b=bb2(p); return x>b[0]-6&&x<b[2]+6&&y>b[1]-6&&y<b[3]+6&&(pip(p,x,y)||Math.min.apply(null,p.map(function(v,i){ var w=p[(i+1)%p.length]; return segD(x,y,v[0],v[1],w[0],w[1]); }))<6); })) return false;
    if(G.lvs.some(function(l){ return roomAt(G,l.id,x,y); })) return false; return !out.some(function(o){ return Math.hypot(o[0]-x,o[1]-y)<6; }); };
  areas.forEach(function(a){ var b=bb2(a.p), lx=b[2]-b[0]>=b[3]-b[1]; if(Math.max(b[2]-b[0],b[3]-b[1])<12) return;
    [-1,1].forEach(function(sd){ var L=lx?b[2]-b[0]:b[3]-b[1], n=Math.floor(L/9); for(var i=0;i<=n;i++){ var t=(lx?b[0]:b[1])+L*i/Math.max(1,n), x=lx?t:(sd<0?b[0]-5:b[2]+5), y=lx?(sd<0?b[1]-5:b[3]+5):t; if(clear(x,y)) out.push([x,y]); } }); });
  out.slice(0,90).forEach(function(p,i){ var z=G.gz; sb.items.push({t:'tree', p:p, z:z, h:7+hash(i+'t')*4}); addPrim(G,{k:'circ',x:p[0],y:p[1],r:.35,z0:z,z1:z+3}); }); }
function treeItem(G,mb,it){ var x=it.p[0], y=it.p[1], z=it.z, h=it.h, R0=rng(hash(x*7+y)); limb(mb,'bark',[x,y,z],[x+.2,y,z+h*.45],.22,.15,8); limb(mb,'bark',[x+.2,y,z+h*.45],[x,y+.3,z+h*.62],.15,.1,7);
  for(var i=0;i<6;i++){ var a=R0()*6.28, rr=h*(.08+R0()*.12); ell(mb,'leaf',[x+Math.cos(a)*rr,y+Math.sin(a)*rr,z+h*(.58+R0()*.28)],[h*(.18+R0()*.1),h*(.18+R0()*.1),h*(.15+R0()*.08)],R0()*3,0,9); } };
function AltoBounds(G){ var bb=[1e9,1e9,-1e9,-1e9]; function t(p){ (p||[]).forEach(function(v){ bb[0]=Math.min(bb[0],v[0]); bb[1]=Math.min(bb[1],v[1]); bb[2]=Math.max(bb[2],v[0]); bb[3]=Math.max(bb[3],v[1]); }); }
  G.rooms.forEach(function(r){ t(r.p); }); (G.plan.wl||[]).forEach(function(w){ t(w.p); }); var ex=G.plan.ex||{}; (ex.sh||[]).forEach(function(s){ t(s.p); }); (ex.tr||[]).forEach(function(s){ t(s.p); }); (ex.stp||[]).forEach(function(s){ t(s.p); });
  return bb[0]<1e8?bb:[0,0,10,10]; }

/* rooms joined by openings, by open boundaries, by stairs and by tall rooms; -1 is outside */
function portals(G){
  function link(a,b,bb,k){ var p={a:a?a.i:-1, b:b?b.i:-1, bb:bb, k:k}; if(p.a===p.b) return; G.portals.push(p); if(a) a.nb.push(p); if(b) b.nb.push(p); if(!a||!b) (G.outNb||(G.outNb=[])).push(p); }
  G.outNb=[];
  G.walls.forEach(function(W){ W.ops.forEach(function(op){ if(!op.sg) return; var sg=op.sg, A=[sg.A[0]+sg.d[0]*(op.a0-sg.s0),sg.A[1]+sg.d[1]*(op.a0-sg.s0)], B=[sg.A[0]+sg.d[0]*(op.a1-sg.s0),sg.A[1]+sg.d[1]*(op.a1-sg.s0)], m=W.ht+.05;
    if(!op.ra&&!op.rb||op.niche) return; link(op.ra,op.rb,[Math.min(A[0],B[0])-m,Math.min(A[1],B[1])-m,op.z0,Math.max(A[0],B[0])+m,Math.max(A[1],B[1])+m,op.z1],op.k); }); });
  G.rooms.forEach(function(r){ G.rooms.forEach(function(o){ if(o.i<=r.i||o.l!==r.l||!bbHit(r.bb,o.bb,.35)) return;
    for(var i=0,n=r.p.length;i<n;i++){ var a=r.p[i], b=r.p[(i+1)%n], dx=b[0]-a[0], dy=b[1]-a[1], L=Math.hypot(dx,dy); if(L<.5) continue; var ux=dx/L, uy=dy/L;
      for(var j=0,m=o.p.length;j<m;j++){ var c=o.p[j], d=o.p[(j+1)%m]; if(Math.abs((d[0]-c[0])*uy-(d[1]-c[1])*ux)>.05*Math.hypot(d[0]-c[0],d[1]-c[1])) continue;
        if(Math.abs((c[0]-a[0])*uy-(c[1]-a[1])*ux)>.35) continue;
        var t0=(c[0]-a[0])*ux+(c[1]-a[1])*uy, t1=(d[0]-a[0])*ux+(d[1]-a[1])*uy, lo=Math.max(0,Math.min(t0,t1)), hi=Math.min(L,Math.max(t0,t1)); if(hi-lo<.6) continue;
        var steps=Math.max(2,Math.ceil((hi-lo)/.8)), open=0;
        for(var k=0;k<steps;k++){ var t=lo+(hi-lo)*(k+.5)/steps, mx=a[0]+ux*t, my=a[1]+uy*t, z=r.l.e+1.2;
          var blocked=primsNear(G,mx,my,.8).some(function(p){ return p.wall&&p.k==='seg'&&p.z0<=z&&p.z1>=z&&segD(mx,my,p.ax,p.ay,p.bx,p.by)<p.r+.2; }); if(!blocked) open++; }
        if(open){ var x0=a[0]+ux*lo, y0=a[1]+uy*lo, x1=a[0]+ux*hi, y1=a[1]+uy*hi; link(r,o,[Math.min(x0,x1)-.3,Math.min(y0,y1)-.3,r.l.e,Math.max(x0,x1)+.3,Math.max(y0,y1)+.3,Math.min(r.ceil,o.ceil)],'open'); } } } }); });
  G.st.forEach(function(o){ var c=interior(o.fp), a=roomAt(G,o.lo.id,c[0],c[1])||o.host, top=o.fl.length?o.fl[o.fl.length-1].b:null, b=top?roomAt(G,o.hi.id,top[0],top[1]):null;
    if(!b&&top) b=roomNear(G,o.hi.id,top[0],top[1],o.fl[o.fl.length-1].d[0],o.fl[o.fl.length-1].d[1]); if(!b) b=roomAt(G,o.hi.id,c[0],c[1]);
    if(a&&b) link(a,b,[o.bb[0]-.5,o.bb[1]-.5,o.lo.e,o.bb[2]+.5,o.bb[3]+.5,o.hi.e+2.5],'stair');
    if(b) G.rooms.forEach(function(r){ if(r.l===o.hi&&r!==b&&bbHit(r.bb,o.bb)) link(b,r,[o.bb[0],o.bb[1],o.hi.e,o.bb[2],o.bb[3],o.hi.e+2],'stair'); }); });
  G.rooms.forEach(function(r){ G.lvs.forEach(function(l){ if(l.e<=r.l.e+.5||l.e>=r.ceil-.5) return; G.rooms.forEach(function(o){ if(o.l===l&&bbHit(r.bb,o.bb,-.2)){
    link(r,o,[Math.max(r.bb[0],o.bb[0]),Math.max(r.bb[1],o.bb[1]),l.e-.5,Math.min(r.bb[2],o.bb[2]),Math.min(r.bb[3],o.bb[3]),Math.min(r.ceil,o.ceil)],'void'); } }); }); }); }

/* ── supports: what the walker stands on ── */
function flightZ(fl,x,y,tol){ var px=x-fl.a[0], py=y-fl.a[1], u=px*fl.d[0]+py*fl.d[1], v=px*fl.n[0]+py*fl.n[1]; tol=tol||0;
  if(u<-.3-tol||u>fl.L+.3+tol||Math.abs(v)>fl.w/2+tol) return null; return fl.a[2]+fl.H*clamp(u/fl.L,0,1); }
function stepsZ(s,x,y){ if(!pip(s.p,x,y)) return null; var ang=(s.up!=null?s.up:90)*PI/180, ux=Math.cos(ang), uy=Math.sin(ang), mn=1e9, mx=-1e9;
  s.p.forEach(function(p){ var u=p[0]*ux+p[1]*uy; mn=Math.min(mn,u); mx=Math.max(mx,u); }); var t=clamp(((x*ux+y*uy)-mn)/Math.max(.01,mx-mn),0,1), n=s.n||Math.max(1,Math.round(Math.abs(s.z1-s.z0)/.15));
  return s.z0+(s.z1-s.z0)*t; }
function inShell(G,x,y){ var sh=(G.plan.ex||{}).sh||[]; for(var i=0;i<sh.length;i++) if(sh[i].p&&pip(sh[i].p,x,y)) return true; return false; }
function supports(G,x,y){ var out=[], cov=false, sl=G.sg&&G.sg[Math.floor(x/2)+','+Math.floor(y/2)]; if(sl) for(var q=0;q<sl.length;q++) if(pip(sl[q].p,x,y)) out.push(sl[q].z);
  G.lvs.forEach(function(l){ var r=roomAt(G,l.id,x,y); if(!r) return; cov=true; if(r.isVoid) return; for(var i=0;i<r.holesF.length;i++) if(pip(r.holesF[i],x,y)) return; out.push(l.e); });
  if(!cov||!inShell(G,x,y)) out.unshift(G.gz);                       /* the site's ground only outside the building: under a room it was a slab 2 m over the basement (the Forum stair) */
  G.st.forEach(function(o){ if(x<o.bb[0]-2||x>o.bb[2]+2||y<o.bb[1]-2||y>o.bb[3]+2) return; o.fl.forEach(function(fl){ var z=flightZ(fl,x,y); if(z!=null) out.push(z); }); o.ld.forEach(function(l){ if(pip(l.p,x,y)) out.push(l.z); }); });
  var ex=G.plan.ex||{}; (ex.stp||[]).forEach(function(s){ var z=stepsZ(s,x,y); if(z!=null) out.push(z); }); (ex.tr||[]).forEach(function(t){ if(pip(t.p,x,y)) out.push(t.z); });
  return out; }
function onStair(G,x,y){ for(var i=0;i<G.st.length;i++){ var o=G.st[i]; if(x<o.bb[0]-2||x>o.bb[2]+2||y<o.bb[1]-2||y>o.bb[3]+2) continue; for(var j=0;j<o.fl.length;j++) if(flightZ(o.fl[j],x,y)!=null) return true; for(var k=0;k<o.ld.length;k++) if(pip(o.ld[k].p,x,y)) return true; } return false; }
/* what the capsule stands on: the highest support under its foot disc (centre and 8 points 0.2 m out), never above a step up; hairline gaps between traced rooms carry you */
var DISC=[[0,0]].concat([0,1,2,3,4,5,6,7].map(function(i){ return [Math.cos(i*PI/4)*.2,Math.sin(i*PI/4)*.2]; }));
function supportDisc(G,x,y,fz){ var best=null; for(var i=0;i<DISC.length;i++){ var s=supportAt(G,x+DISC[i][0],y+DISC[i][1],fz); if(s!=null&&(best==null||s>best)) best=s; } return best; }
function supportAt(G,x,y,fz){ var s=supports(G,x,y), best=-1e9; for(var i=0;i<s.length;i++) if(s[i]<=fz+CFG.step&&s[i]>best) best=s[i]; return best>-1e8?best:null; }
function blockedAt(G,x,y,fz){ var s=supports(G,x,y); for(var i=0;i<s.length;i++) if(s[i]>fz+CFG.step&&s[i]<fz+CFG.head) return true;
  var ps=primsNear(G,x,y,CFG.pr+.5), z0=fz+CFG.knee, z1=fz+CFG.head;
  for(var j=0;j<ps.length;j++){ var p=ps[j]; if(p.z1<(p.wall?z0+CFG.step+.08-CFG.knee:z0)||p.z0>z1) continue; if(primDist(p,x,y)<CFG.pr) return true; } return false; }
function primDist(p,x,y){ if(p.k==='seg'){ if(p.flat){ var fx=p.bx-p.ax, fy=p.by-p.ay, fl=Math.hypot(fx,fy)||1e-9, qx=x-p.ax, qy=y-p.ay, al=(qx*fx+qy*fy)/fl, lx2=Math.abs(al-fl/2)-fl/2, ly2=Math.abs((qx*fy-qy*fx)/fl)-p.r; return Math.hypot(Math.max(lx2,0),Math.max(ly2,0))+Math.min(Math.max(lx2,ly2),0); } return segD(x,y,p.ax,p.ay,p.bx,p.by)-p.r; } if(p.k==='circ') return Math.hypot(x-p.x,y-p.y)-p.r;
  var dx=x-p.x, dy=y-p.y, lx=Math.abs(dx*p.c+dy*p.s)-p.hx, ly=Math.abs(-dx*p.s+dy*p.c)-p.hy; return Math.hypot(Math.max(lx,0),Math.max(ly,0))+Math.min(Math.max(lx,ly),0); }
/* push a walker circle out of every primitive it overlaps (a few rounds: sliding along walls falls out of it) */
function resolve(G,x,y,fz){ var z0=fz+CFG.knee, z1=fz+CFG.head, R=CFG.pr;
  for(var it=0;it<4;it++){ var moved=false, ps=primsNear(G,x,y,R+.6);
    for(var j=0;j<ps.length;j++){ var p=ps[j]; if(p.z1<(p.wall?z0+CFG.step+.08-CFG.knee:z0)||p.z0>z1) continue; var d=primDist(p,x,y); if(d>=R) continue;
      var e=.002, gx=(primDist(p,x+e,y)-primDist(p,x-e,y))/(2*e), gy=(primDist(p,x,y+e)-primDist(p,x,y-e))/(2*e), gl=Math.hypot(gx,gy)||1;
      x+=gx/gl*(R-d+.001); y+=gy/gl*(R-d+.001); moved=true; }
    if(!moved) break; }
  return [x,y]; }

/* ── packed vertices: pos 3 f32, normal 3 i8, uv 2 f32, aux 4 u8 = 28 bytes ── */
var STRIDE=28, Z4=[0,0,0,0];
function Buf(){ this.ab=new ArrayBuffer(STRIDE*512); this.mk(); this.n=0; }
Buf.prototype.mk=function(){ this.f=new Float32Array(this.ab); this.i8=new Int8Array(this.ab); this.u8=new Uint8Array(this.ab); };
Buf.prototype.v=function(p,n,t,x){ if((this.n+1)*STRIDE>this.ab.byteLength){ var nb=new ArrayBuffer(this.ab.byteLength*2); new Uint8Array(nb).set(this.u8); this.ab=nb; this.mk(); }
  var o=this.n*7, b=this.n*STRIDE, f=this.f, i8=this.i8, u8=this.u8; f[o]=p[0]; f[o+1]=p[1]; f[o+2]=p[2];
  i8[b+12]=Math.round(n[0]*127); i8[b+13]=Math.round(n[1]*127); i8[b+14]=Math.round(n[2]*127); i8[b+15]=0; f[o+4]=t[0]; f[o+5]=t[1];
  u8[b+24]=x[0]; u8[b+25]=x[1]; u8[b+26]=x[2]; u8[b+27]=x[3]; this.n++; };
var AX0=[255,255,0,0];
function MB(){ this.k={}; this.order=[]; this.tris=0; }
MB.prototype.b=function(k){ var b=this.k[k]; if(!b){ b=this.k[k]=new Buf(); this.order.push(k); } return b; };
MB.prototype.tri=function(k,a,b,c,na,nb,nc,ta,tb,tc,xa,xb,xc){
  var g=cross(sub(b,a),sub(c,a)), h=[na[0]+nb[0]+nc[0],na[1]+nb[1]+nc[1],na[2]+nb[2]+nc[2]];
  if(g[0]*g[0]+g[1]*g[1]+g[2]*g[2]<1e-14) return;
  var B=this.b(k); if(dot(g,h)<0){ B.v(a,na,ta,xa); B.v(c,nc,tc,xc); B.v(b,nb,tb,xb); } else { B.v(a,na,ta,xa); B.v(b,nb,tb,xb); B.v(c,nc,tc,xc); } this.tris++; };
MB.prototype.quad=function(k,p,n,t,x){ var N=typeof n[0]==='number'?[n,n,n,n]:n, X=!x?[AX0,AX0,AX0,AX0]:typeof x[0]==='number'?[x,x,x,x]:x;
  this.tri(k,p[0],p[1],p[2],N[0],N[1],N[2],t[0],t[1],t[2],X[0],X[1],X[2]); this.tri(k,p[0],p[2],p[3],N[0],N[2],N[3],t[0],t[2],t[3],X[0],X[2],X[3]); };
/* a quad whose normal is its own geometric one, turned to agree with a hint */
MB.prototype.qg=function(k,p,hint,t,x){ var g=nrm(cross(sub(p[1],p[0]),sub(p[2],p[0]))); if(g[0]*g[0]+g[1]*g[1]+g[2]*g[2]<.5) g=nrm(cross(sub(p[2],p[0]),sub(p[3],p[0])));
  if(dot(g,hint)<0) g=[-g[0],-g[1],-g[2]]; this.quad(k,p,g,t||[[0,0],[1,0],[1,1],[0,1]],x); };
function flat(mb,k,rings,z,up){ var nz=up?[0,0,1]:[0,0,-1]; fillRings(rings,function(a,b,y0,c,d,y1){ mb.quad(k,[[a,y0,z],[b,y0,z],[d,y1,z],[c,y1,z]],nz,[[a,y0],[b,y0],[d,y1],[c,y1]]); }); }
/* an oriented box: centre x,y, bottom z0, size w (local x) d (local y) h, turned rot; skip: {b:1,t:1} */
function box(mb,k,x,y,z0,w,d,h,rot,skip){ var c=Math.cos(rot||0), s=Math.sin(rot||0), hw=w/2, hd=d/2, z1=z0+h; skip=skip||{};
  var P=function(a,b,z){ return [x+a*c-b*s,y+a*s+b*c,z]; }, L=[[-hw,-hd],[hw,-hd],[hw,hd],[-hw,hd]];
  for(var i=0;i<4;i++){ var a=L[i], b=L[(i+1)%4], ex=b[0]-a[0], ey=b[1]-a[1], el=Math.hypot(ex,ey), nl=[ey/el,-ex/el], nw=[nl[0]*c-nl[1]*s,nl[0]*s+nl[1]*c,0];
    mb.quad(k,[P(a[0],a[1],z0),P(b[0],b[1],z0),P(b[0],b[1],z1),P(a[0],a[1],z1)],nw,[[0,z0],[el,z0],[el,z1],[0,z1]]); }
  if(!skip.t) mb.quad(k,[P(-hw,-hd,z1),P(hw,-hd,z1),P(hw,hd,z1),P(-hw,hd,z1)],[0,0,1],[[x-hw,y-hd],[x+hw,y-hd],[x+hw,y+hd],[x-hw,y+hd]]);
  if(!skip.b) mb.quad(k,[P(-hw,-hd,z0),P(hw,-hd,z0),P(hw,hd,z0),P(-hw,hd,z0)],[0,0,-1],[[x-hw,y-hd],[x+hw,y-hd],[x+hw,y+hd],[x-hw,y+hd]]); }
/* a solid of revolution about (x,y): prof [[r,z]...] bottom to top, seg sides; flutes: [count, depth, z0, z1] */
function lathe(mb,k,x,y,prof,seg,flu){ var rings=[];
  for(var j=0;j<prof.length;j++){ var r=prof[j][0], z=prof[j][1], pr=prof[Math.max(0,j-1)], nx=prof[Math.min(prof.length-1,j+1)], dz=nx[1]-pr[1], dr=nx[0]-pr[0], l=Math.hypot(dz,dr)||1, row=[];
    for(var i=0;i<=seg;i++){ var a=i/seg*2*PI, ca=Math.cos(a), sa=Math.sin(a), rr=r, nr=[ca*dz/l,sa*dz/l,-dr/l];
      if(flu&&z>=flu[2]&&z<=flu[3]){ var m=.5+.5*Math.cos(flu[0]*a); rr=r*(1-flu[1]*m); var dd=r*flu[1]*.5*flu[0]*Math.sin(flu[0]*a), tx=-sa*rr+ca*dd, ty=ca*rr+sa*dd, tl=Math.hypot(tx,ty)||1; nr=nrm([ty/tl*dz/l,-tx/tl*dz/l,-dr/l]); }
      row.push({p:[x+ca*rr,y+sa*rr,z], n:nr, t:[a*Math.max(r,.05),z]}); }
    rings.push(row); }
  for(var j2=0;j2+1<rings.length;j2++) for(var i2=0;i2<seg;i2++){ var A=rings[j2][i2], B=rings[j2][i2+1], C=rings[j2+1][i2+1], E=rings[j2+1][i2]; mb.quad(k,[A.p,B.p,C.p,E.p],[A.n,B.n,C.n,E.n],[A.t,B.t,C.t,E.t]); } }
/* an ellipsoid at c with radii r, turned rot about z and tilt about the local x */
function ell(mb,k,c,r,rot,tilt,seg){ seg=seg||10; var cr=Math.cos(rot||0), sr=Math.sin(rot||0), ct=Math.cos(tilt||0), st=Math.sin(tilt||0);
  var T=function(v){ var y=v[1]*ct-v[2]*st, z=v[1]*st+v[2]*ct; return [v[0]*cr-y*sr,v[0]*sr+y*cr,z]; }, rows=[];
  for(var j=0;j<=seg;j++){ var th=j/seg*PI, row=[]; for(var i=0;i<=seg*2;i++){ var ph=i/(seg*2)*2*PI, u=[Math.sin(th)*Math.cos(ph),Math.sin(th)*Math.sin(ph),Math.cos(th)];
      var p=T([u[0]*r[0],u[1]*r[1],u[2]*r[2]]); row.push({p:[c[0]+p[0],c[1]+p[1],c[2]+p[2]], n:nrm(T([u[0]/r[0],u[1]/r[1],u[2]/r[2]])), t:[ph*r[0],th*r[2]]}); } rows.push(row); }
  for(var j2=0;j2<seg;j2++) for(var i2=0;i2<seg*2;i2++){ var A=rows[j2][i2], B=rows[j2][i2+1], C=rows[j2+1][i2+1], E=rows[j2+1][i2]; mb.quad(k,[A.p,B.p,C.p,E.p],[A.n,B.n,C.n,E.n],[A.t,B.t,C.t,E.t]); } }
/* a tapered limb from a to b */
function limb(mb,k,a,b,r0,r1,seg){ seg=seg||10; var ax=nrm(sub(b,a)), up=Math.abs(ax[2])<.9?[0,0,1]:[1,0,0], u=nrm(cross(ax,up)), v=cross(ax,u);
  for(var i=0;i<seg;i++){ var a0=i/seg*2*PI, a1=(i+1)/seg*2*PI, n0=[u[0]*Math.cos(a0)+v[0]*Math.sin(a0),u[1]*Math.cos(a0)+v[1]*Math.sin(a0),u[2]*Math.cos(a0)+v[2]*Math.sin(a0)], n1=[u[0]*Math.cos(a1)+v[0]*Math.sin(a1),u[1]*Math.cos(a1)+v[1]*Math.sin(a1),u[2]*Math.cos(a1)+v[2]*Math.sin(a1)];
    mb.quad(k,[[a[0]+n0[0]*r0,a[1]+n0[1]*r0,a[2]+n0[2]*r0],[a[0]+n1[0]*r0,a[1]+n1[1]*r0,a[2]+n1[2]*r0],[b[0]+n1[0]*r1,b[1]+n1[1]*r1,b[2]+n1[2]*r1],[b[0]+n0[0]*r1,b[1]+n0[1]*r1,b[2]+n0[2]*r1]],[n0,n1,n1,n0],[[a0*r0,0],[a1*r0,0],[a1*r1,1],[a0*r1,1]]); }
  ell(mb,k,b,[r1,r1,r1],0,0,6); }
/* a strip with a profile [[w,z]...] (w out of the face) along a face run u0..u1; F = the face frame */
function strip(mb,k,F,u0,u1,prof){ if(u1-u0<.01) return; for(var i=0;i+1<prof.length;i++){ var a=prof[i], b=prof[i+1], dw=b[0]-a[0], dz=b[1]-a[1], l=Math.hypot(dw,dz)||1;
    var nv=nrm([F.n[0]*dz/l,F.n[1]*dz/l,-dw/l]), P=function(u,w,z){ return [F.ox+F.dx*u+F.n[0]*w,F.oy+F.dy*u+F.n[1]*w,z]; };
    mb.quad(k,[P(u0,a[0],a[1]),P(u1,a[0],a[1]),P(u1,b[0],b[1]),P(u0,b[0],b[1])],nv,[[F.uo+u0,a[1]+a[0]],[F.uo+u1,a[1]+a[0]],[F.uo+u1,b[1]+b[0]],[F.uo+u0,b[1]+b[0]]]); } }

/* ── building a batch ── */
function wallKey(r,W){ var m=r?r.wm:W.m; return m==='paint'?'paint#'+(r?r.i:0):m; }
function buildBatch(G,b){ var mb=new MB(); b.lab=[]; b.art=[]; b.trans={};
  var r=b.room;
  if(r) buildRoomShell(G,mb,r);
  b.items.forEach(function(it){ try{ ITEM[it.t](G,mb,it,b); }catch(e){ if(window.console) console.warn('bldg fpv',it.t,e); } });
  b.light=b.kind==='room'?roomLight(G,r,b):extLight(G,b);
  return mb; }
var ITEM={tree:treeItem, gapwall:gapwallItem};
ITEM.face=function(G,mb,f,b){ var W=f.W, sg=f.sg, s=f.s, r=f.room, ox=sg.A[0]+sg.n[0]*s*W.ht, oy=sg.A[1]+sg.n[1]*s*W.ht;
  var F={ox:ox, oy:oy, dx:sg.d[0], dy:sg.d[1], n:[sg.n[0]*s,sg.n[1]*s,0], uo:sg.s0}, k=wallKey(r,W), fb=f.fb, ft=f.ft;
  var ops=W.ops.filter(function(op){ return op.a1-sg.s0>f.u0+1e-4&&op.a0-sg.s0<f.u1-1e-4; }), cuts=[f.u0,f.u1];
  ops.forEach(function(op){ var a=op.a0-sg.s0, c=op.a1-sg.s0; [a,c].forEach(function(v){ if(v>f.u0&&v<f.u1) cuts.push(v); }); if(op.arch) for(var i=1;i<24;i++){ var v=a+(c-a)*i/24; if(v>f.u0&&v<f.u1) cuts.push(v); } });
  cuts.sort(function(a,c){ return a-c; });
  var ax=function(u){ return [enc4(f.c0!=null?u-f.c0:null),enc4(f.c1!=null?f.c1-u:null),0,0]; };
  var P=function(u,z){ return [ox+sg.d[0]*u,oy+sg.d[1]*u,z]; };
  var Q=function(u0,u1,b0,b1,t0,t1){ if(t0-b0<1e-3&&t1-b1<1e-3) return; mb.quad(k,[P(u0,b0),P(u1,b1),P(u1,t1),P(u0,t0)],F.n,[[F.uo+u0,b0],[F.uo+u1,b1],[F.uo+u1,t1],[F.uo+u0,t0]],[ax(u0),ax(u1),ax(u1),ax(u0)]); };
  var low=[], rail=[], top=[], zr=Math.min(fb+3.4,ft-.4);
  for(var i=0;i+1<cuts.length;i++){ var u0=cuts[i], u1=cuts[i+1]; if(u1-u0<1e-4) continue; var um=(u0+u1)/2, op=null;
    for(var j=0;j<ops.length;j++){ var o=ops[j]; if(um>o.a0-sg.s0&&um<o.a1-sg.s0){ op=o; break; } }
    if(!op){ Q(u0,u1,fb,fb,ft,ft); low.push([u0,u1]); rail.push([u0,u1]); top.push([u0,u1]); continue; }
    var z0=Math.max(fb,op.z0), t0=Math.min(ft,archTop(op,u0+sg.s0)), t1=Math.min(ft,archTop(op,u1+sg.s0));
    if(z0>fb+1e-3){ Q(u0,u1,fb,fb,z0,z0); if(z0>fb+.2) low.push([u0,u1]); }
    Q(u0,u1,t0,t1,ft,ft); if(Math.max(t0,t1)<zr-.06) rail.push([u0,u1]); if(Math.max(t0,t1)<ft-.3) top.push([u0,u1]); }
  if(!r||W.rail) return;
  var mg=function(L){ var o=[]; L.forEach(function(a){ if(o.length&&Math.abs(o[o.length-1][1]-a[0])<1e-4) o[o.length-1][1]=a[1]; else o.push([a[0],a[1]]); }); return o; };
  var stone=/^(limestone|kasota|marble|stone|sandstone|granite)$/.test(r.wm), trim=stone?r.wm:'trim#'+r.i;
  if(fb>=r.l.e-.01){ mg(low).forEach(function(a){ strip(mb,stone?'marble':'skirt#'+r.i,F,a[0],a[1],[[.016,fb],[.016,fb+.15],[.008,fb+.165],[0,fb+.175]]); }); }
  if(!stone&&r.ch>3.2&&r.ty==='gallery') mg(rail).forEach(function(a){ strip(mb,trim,F,a[0],a[1],[[0,zr-.022],[.022,zr-.014],[.022,zr+.01],[0,zr+.022]]); });
  mg(top).forEach(function(a){ var c=ft, d=r.ch>7?Math.min(1.5,r.ch*.085):r.cm==='glass'?Math.min(.75,r.ch*.13):Math.min(.32,r.ch*.06); strip(mb,stone?r.wm:'plaster',F,a[0],a[1],[[0,c-d-.06],[.03,c-d-.04],[.03,c-d],[d*.45,c-d*.55],[d*.8,c-d*.2],[d,c]]); });
  /* casings round doors and arches whose both ends stand on this face */
  ops.forEach(function(op){ if(!(op.k==='door'||op.k==='arch')) return; var a=op.a0-sg.s0, c=op.a1-sg.s0; if(a<f.u0-1e-3||c>f.u1+1e-3||op.z0>fb+.05) return;
    var cw=Math.min(.16,(c-a)*.08+.06), dp=.028, path=[[a,op.z0]];
    if(op.arch){ for(var i=0;i<=24;i++){ var u=a+(c-a)*i/24; path.push([u,Math.min(ft,archTop(op,u+sg.s0))]); } } else { path.push([a,Math.min(ft,op.z1)]); path.push([c,Math.min(ft,op.z1)]); }
    path.push([c,op.z0]);
    var out=path.map(function(p,i){ var pv=path[Math.max(0,i-1)], nx=path[Math.min(path.length-1,i+1)], du=nx[0]-pv[0], dz=nx[1]-pv[1], l=Math.hypot(du,dz)||1, nu=-dz/l, nz=du/l;
      if(i===0||i===path.length-1){ nu=i===0?-1:1; nz=0; } var k2=1; if(!op.arch&&(i===1||i===2)){ nu=i===1?-1:1; nz=1; k2=1; } return [p[0]+nu*cw*k2,Math.min(ft-.01,p[1]+nz*cw*k2)]; });
    var W3=function(p,w){ return [ox+sg.d[0]*p[0]+F.n[0]*w,oy+sg.d[1]*p[0]+F.n[1]*w,p[1]]; };
    for(var i2=0;i2+1<path.length;i2++){ var p0=path[i2], p1=path[i2+1], q0=out[i2], q1=out[i2+1];
      mb.qg(trim,[W3(p0,dp),W3(p1,dp),W3(q1,dp),W3(q0,dp)],F.n,[[p0[0],p0[1]],[p1[0],p1[1]],[q1[0],q1[1]],[q0[0],q0[1]]]);
      var cu=(a+c)/2, cz=op.z0+(op.arch?op.zs-op.z0:0), mu=(p0[0]+p1[0])/2-cu, mz=(p0[1]+p1[1])/2-cz, ml=Math.hypot(mu,mz)||1, hin=[-(sg.d[0]*mu)/ml,-(sg.d[1]*mu)/ml,-mz/ml];
      mb.qg(trim,[W3(p0,0),W3(p1,0),W3(p1,dp),W3(p0,dp)],hin,[[0,0],[1,0],[1,dp],[0,dp]]);
      mb.qg(trim,[W3(q0,0),W3(q1,0),W3(q1,dp),W3(q0,dp)],[-hin[0],-hin[1],-hin[2]],[[0,0],[1,0],[1,dp],[0,dp]]); } }); };
ITEM.op=function(G,mb,it,b){ var W=it.W, op=it.op, sg=op.sg, ht=W.ht, k=W.m==='paint'?'plaster':W.m;
  var a=op.a0-sg.s0, c=op.a1-sg.s0, z0=op.z0, top=function(u){ return archTop(op,u+sg.s0); };
  var P=function(u,w,z){ return [sg.A[0]+sg.d[0]*u+sg.n[0]*w,sg.A[1]+sg.d[1]*u+sg.n[1]*w,z]; }, N=[sg.n[0],sg.n[1],0], Dv=[sg.d[0],sg.d[1],0];
  var zj=op.arch?op.zs:op.z1;
  var fin=function(r){ return r?(r.wm==='paint'?'paint#'+r.i:r.wm):W.m; }, halves=[[-ht,0,fin(op.rb)],[0,ht,fin(op.ra)]];
  if(fin(op.ra)===fin(op.rb)) halves=[[-ht,ht,fin(op.ra)]];
  halves.forEach(function(hv){ var w0=hv[0], w1=hv[1], kk=hv[2];
    if(op.a0>sg.s0-1e-4) mb.quad(kk,[P(a,w0,z0),P(a,w1,z0),P(a,w1,zj),P(a,w0,zj)],Dv,[[w0,z0],[w1,z0],[w1,zj],[w0,zj]]);
    if(op.a1<sg.s0+sg.L+1e-4) mb.quad(kk,[P(c,w0,z0),P(c,w1,z0),P(c,w1,zj),P(c,w0,zj)],[-Dv[0],-Dv[1],0],[[w0,z0],[w1,z0],[w1,zj],[w0,zj]]);
    if(op.arch){ for(var i=0;i<24;i++){ var u0=a+(c-a)*i/24, u1=a+(c-a)*(i+1)/24; mb.qg(kk,[P(u0,w0,top(u0)),P(u1,w0,top(u1)),P(u1,w1,top(u1)),P(u0,w1,top(u0))],[0,0,-1],[[u0,w0],[u1,w0],[u1,w1],[u0,w1]]); } }
    else mb.quad(kk,[P(a,w0,op.z1),P(c,w0,op.z1),P(c,w1,op.z1),P(a,w1,op.z1)],[0,0,-1],[[a,w0],[c,w0],[c,w1],[a,w1]]); });
  if(z0>W.base+.01) mb.quad(k==='plaster'?'marble':k,[P(a,-ht-.03,z0),P(c,-ht-.03,z0),P(c,ht+.03,z0),P(a,ht+.03,z0)],[0,0,1],[[a,0],[c,0],[c,2*ht],[a,2*ht]]);
  else if(op.pass) mb.quad(W.k==='ext'||/^(limestone|stone|kasota)$/.test(W.m)||op.ra&&op.ra.wm==='kasota'?'kasota':'marble',[P(a,-ht,z0+.004),P(c,-ht,z0+.004),P(c,ht,z0+.004),P(a,ht,z0+.004)],[0,0,1],[[a,0],[c,0],[c,2*ht],[a,2*ht]]);
  if(op.k==='window'){ var fk='bronze', fw=.055, fd=.035, w2=0; var bar=function(u0,u1,za,zb){ var cx=(u0+u1)/2, p=P(cx,w2,0); box(mb,fk,p[0],p[1],za,u1-u0,fd*2,zb-za,Math.atan2(sg.d[1],sg.d[0])); };
    var zt=op.arch?op.zs:op.z1; bar(a,a+fw,z0,zt); bar(c-fw,c,z0,zt); bar(a,c,z0,z0+fw); if(!op.arch) bar(a,c,zt-fw,zt);
    if(c-a>1.2) bar((a+c)/2-fw/2,(a+c)/2+fw/2,z0,zt); var zm=(z0+zt)/2+(zt-z0)/2*.35; if(zt-z0>1.6) bar(a,c,zm-fw/2,zm+fw/2);
    var gk='glass', gx=[255,255,op.ra&&!op.rb?128:!op.ra&&op.rb?255:0,0]; if(op.arch){ for(var i3=0;i3<16;i3++){ var v0=a+(c-a)*i3/16, v1=a+(c-a)*(i3+1)/16; mb.quad(gk,[P(v0,0,z0),P(v1,0,z0),P(v1,0,top(v1)),P(v0,0,top(v0))],N,[[0,0],[1,0],[1,1],[0,1]],gx); } }
    else mb.quad(gk,[P(a,0,z0),P(c,0,z0),P(c,0,op.z1),P(a,0,op.z1)],N,[[0,0],[1,0],[1,1],[0,1]],gx); b.trans[gk]=1; }
  if(op.k==='door'&&op.leafSide&&op.o.d!=='none'){ var side=op.leafSide, single=op.o.d==='single', lw=single?(c-a):(c-a)/2, lk=op.o.m==='bronze'||W.k==='ext'?'bronze':'wood', zt2=op.arch?op.zs:op.z1;
    (single?[a]:[a,c]).forEach(function(u,j){ var uu=u+(j?-.03:.03), p=P(uu,side*(ht+lw/2),0); box(mb,lk,p[0],p[1],z0,.055,lw,zt2-z0-.01,Math.atan2(sg.d[1],sg.d[0]));
      [-1,1].forEach(function(fs){ var hp=P(uu+fs*.05,side*(ht+lw-.12),0); box(mb,'gilt',hp[0],hp[1],z0+.85,.025,.03,.42,0,{}); }); box(mb,'gilt',p[0],p[1],z0+.02,.06,lw*.9,.22,Math.atan2(sg.d[1],sg.d[0]),{b:1}); }); }
};
ITEM.flight=function(G,mb,it){ var fl=it.fl, st=it.st, r=it.room, mk=fl.esc?'metal':(r&&/^(marble|granite)$/.test(r.fm)?r.fm:r&&/^(stone|limestone|sandstone)$/.test(r.fm+'')||r&&/^(limestone|stone)$/.test(r.wm)?'kasota':'marble'), pk=fl.esc?'glass':(r&&/^(limestone|stone|sandstone)$/.test(r.wm)?r.wm:'marble');
  var N=fl.ramp?1:Math.max(2,Math.round(fl.H/.165)), a=fl.a, d=fl.d, n=fl.n, hw=fl.w/2, L=fl.L, H=fl.H;
  if(st.s.n&&st.fl.length===1&&!fl.ramp) N=st.s.n;
  var P=function(u,v,z){ return [a[0]+d[0]*u+n[0]*v,a[1]+d[1]*u+n[1]*v,z]; }, Dn=[d[0],d[1],0], Nn=[n[0],n[1],0];
  var soff=function(u){ return a[2]+H*u/L-.32*Math.sqrt(1+H*H/(L*L)); };
  if(fl.ramp){ mb.qg(mk,[P(0,-hw,a[2]),P(L,-hw,fl.b[2]),P(L,hw,fl.b[2]),P(0,hw,a[2])],[0,0,1],[[0,-hw],[L,-hw],[L,hw],[0,hw]]); }
  else for(var i=0;i<N;i++){ var u0=L*i/N, u1=L*(i+1)/N, z=a[2]+H*(i+1)/N, zp=a[2]+H*i/N, nose=Math.min(.025,(u1-u0)*.15);
    mb.quad(mk,[P(u0-nose,-hw,z),P(u1,-hw,z),P(u1,hw,z),P(u0-nose,hw,z)],[0,0,1],[[u0,-hw],[u1,-hw],[u1,hw],[u0,hw]]);
    mb.quad(mk,[P(u0,-hw,zp),P(u0,hw,zp),P(u0,hw,z-.025),P(u0,-hw,z-.025)],[-d[0],-d[1],0],[[-hw,zp],[hw,zp],[hw,z],[-hw,z]]);
    mb.quad(mk,[P(u0-nose,-hw,z-.025),P(u0-nose,hw,z-.025),P(u0-nose,hw,z),P(u0-nose,-hw,z)],[-d[0],-d[1],0],[[-hw,z],[hw,z],[hw,z+.02],[-hw,z+.02]]);
    mb.quad(mk,[P(u0-nose,-hw,z-.025),P(u0,-hw,z-.025),P(u0,hw,z-.025),P(u0-nose,hw,z-.025)],[0,0,-1],[[0,0],[1,0],[1,1],[0,1]]); }
  var lo=it.room?it.room.l.e:a[2], us=0; while(us<L&&soff(us)<lo+.02) us+=L/40;
  if(us<L) mb.qg('plaster',[P(us,-hw-.18,soff(us)),P(L,-hw-.18,soff(L)),P(L,hw+.18,soff(L)),P(us,hw+.18,soff(us))],[0,0,-1],[[us,-hw],[L,-hw],[L,hw],[us,hw]]);
  /* stone parapets with a moulded cap and a brass handrail */
  var arrive=G.lvs.some(function(l){ return Math.abs(l.e-fl.b[2])<.05; });
  [-1,1].forEach(function(sd){ var vi=sd*hw, vo=sd*(hw+.18), pz=function(u){ return a[2]+H*clamp(u/L,0,1); }, hgt=.95, us2=-.15, ue=arrive?L-Math.min(L*.5,hgt*L/Math.max(H,.01)):L+.15;
    var pt=function(u,v,dz){ return P(u,v,pz(u)+dz); }, bot=function(u){ return Math.max(lo,soff(u)); };
    mb.qg(pk,[P(us2,vi,bot(us2)),P(ue,vi,bot(ue)),pt(ue,vi,hgt),pt(us2,vi,hgt)],[-n[0]*sd,-n[1]*sd,0],[[us2,0],[ue,0],[ue,hgt],[us2,hgt]]);
    mb.qg(pk,[P(us2,vo,bot(us2)),P(ue,vo,bot(ue)),pt(ue,vo,hgt),pt(us2,vo,hgt)],[n[0]*sd,n[1]*sd,0],[[us2,0],[ue,0],[ue,hgt],[us2,hgt]]);
    mb.qg(pk,[pt(us2,vi-sd*.03,hgt),pt(ue,vi-sd*.03,hgt),pt(ue,vo+sd*.03,hgt),pt(us2,vo+sd*.03,hgt)],[0,0,1],[[us2,0],[ue,0],[ue,.24],[us2,.24]]);
    mb.qg(pk,[pt(us2,vi-sd*.03,hgt-.05),pt(ue,vi-sd*.03,hgt-.05),pt(ue,vi-sd*.03,hgt),pt(us2,vi-sd*.03,hgt)],[-n[0]*sd,-n[1]*sd,0],[[us2,0],[ue,0],[ue,.05],[us2,.05]]);
    mb.qg(pk,[pt(us2,vi-sd*.03,hgt-.05),pt(ue,vi-sd*.03,hgt-.05),pt(ue,vi,hgt-.05),pt(us2,vi,hgt-.05)],[0,0,-1],[[0,0],[1,0],[1,1],[0,1]]);
    [us2,ue].forEach(function(u,j){ mb.qg(pk,[P(u,vi,bot(u)),P(u,vo,bot(u)),pt(u,vo,hgt),pt(u,vi,hgt)],[d[0]*(j?1:-1),d[1]*(j?1:-1),0],[[0,0],[.18,0],[.18,hgt],[0,hgt]]); });
    var hr=pt(us2,vi-sd*.06,hgt-.12), he=pt(ue,vi-sd*.06,hgt-.12); limb(mb,'gilt',hr,he,.024,.024,8); }); };
ITEM.land=function(G,mb,it){ var l=it.ld, h=it.st&&it.st.host, k=h&&/^(limestone|stone)$/.test(h.wm)?'kasota':'marble'; flat(mb,k,[l.p],l.z,true); flat(mb,'plaster',[l.p],l.z-.3,false);
  for(var i=0,n=l.p.length;i<n;i++){ var a=l.p[i], c=l.p[(i+1)%n]; mb.qg(k,[[a[0],a[1],l.z-.3],[c[0],c[1],l.z-.3],[c[0],c[1],l.z],[a[0],a[1],l.z]],[c[1]-a[1],a[0]-c[0],0].map(function(v){ return v*(parea(l.p)>0?1:-1); }),[[0,0],[1,0],[1,.3],[0,.3]]); } };
ITEM.plug=function(G,mb,it){ var W=it.W, op=it.op, sg=op.sg, r=it.room, s=it.s, a=op.a0-sg.s0, c=op.a1-sg.s0, z0=op.z0, z1=op.z1, k=r?wallKey(r,{m:r.wm}):(W.m==='paint'?'plaster':W.m);
  var P=function(u,z){ return [sg.A[0]+sg.d[0]*u+sg.n[0]*W.ht*s,sg.A[1]+sg.d[1]*u+sg.n[1]*W.ht*s,z]; }; mb.quad(k,[P(a,z0),P(c,z0),P(c,z1),P(a,z1)],[sg.n[0]*s,sg.n[1]*s,0],[[a,z0],[c,z0],[c,z1],[a,z1]]); };
ITEM.niche=function(G,mb,it){ var W=it.W, op=it.op, sg=op.sg, r=it.room, s=it.s, a=op.a0-sg.s0, c=op.a1-sg.s0, z0=op.z0, z1=op.arch?op.z1:op.z1, d=W.ht+1.3, k=wallKey(r,{m:r.wm});
  var P=function(u,w,z){ return [sg.A[0]+sg.d[0]*u+sg.n[0]*w*s,sg.A[1]+sg.d[1]*u+sg.n[1]*w*s,z]; }, N=[sg.n[0]*s,sg.n[1]*s,0], D=[sg.d[0],sg.d[1],0];
  mb.quad(k,[P(a,d,z0),P(c,d,z0),P(c,d,z1),P(a,d,z1)],[-N[0],-N[1],0],[[a,z0],[c,z0],[c,z1],[a,z1]]);
  mb.quad(k,[P(a,W.ht,z0),P(a,d,z0),P(a,d,z1),P(a,W.ht,z1)],D,[[0,z0],[d,z0],[d,z1],[0,z1]]); mb.quad(k,[P(c,W.ht,z0),P(c,d,z0),P(c,d,z1),P(c,W.ht,z1)],[-D[0],-D[1],0],[[0,z0],[d,z0],[d,z1],[0,z1]]);
  mb.quad('plaster',[P(a,W.ht,z1),P(c,W.ht,z1),P(c,d,z1),P(a,d,z1)],[0,0,-1],[[a,0],[c,0],[c,d],[a,d]]); mb.quad(floorKey(r.fm,r),[P(a,W.ht,z0),P(c,W.ht,z0),P(c,d,z0),P(a,d,z0)],[0,0,1],[[a,0],[c,0],[c,d],[a,d]]); };
ITEM.entab=function(G,mb,it){ var A=it.a, B=it.b, r=it.r, L=Math.hypot(B[0]-A[0],B[1]-A[1])+r*2.7, rot=Math.atan2(B[1]-A[1],B[0]-A[0]), cx=(A[0]+B[0])/2, cy=(A[1]+B[1])/2, z=it.z, k='kasota', D=r*2.5;
  box(mb,k,cx,cy,z,L,D,r*1.1,rot,{}); box(mb,k,cx,cy,z+r*1.1,L+.02,D*1.04,.08,rot,{b:1}); box(mb,k,cx,cy,z+r*1.18,L,D*.96,r*1.05,rot,{b:1}); box(mb,k,cx,cy,z+r*2.23,L+r*.5,D+r*.5,r*.18,rot,{b:1}); box(mb,k,cx,cy,z+r*2.41,L+r*.8,D+r*.8,r*.32,rot,{}); };
ITEM.pedi=function(G,mb,it){ var O=it.o, u=it.u, d=it.vd, P=function(sv,v,z){ return [O[0]+u[0]*sv+d[0]*v,O[1]+u[1]*sv+d[1]*v,z]; }, vm=(it.v0+it.v1)/2, zb=it.z, zr=zb+it.rise, sf=it.s0, sb=it.sb, oh=.55, th=.5;
  var Q=function(k,pts,hint,uv){ var n=nrm(cross(sub(pts[1],pts[0]),sub(pts[3],pts[0]))); if(dot(n,hint)<0){ pts=[pts[3],pts[2],pts[1],pts[0]]; uv=[uv[3],uv[2],uv[1],uv[0]]; n=[-n[0],-n[1],-n[2]]; } mb.quad(k,pts,n,uv); };
  var run=(zr-zb)/(vm-it.v0), zA=zb+th-run*oh, zA2=zb+th-run*oh;
  Q('kasota',[P(sf,it.v0,zb),P(sf,it.v1,zb),P(sf,vm,zr),P(sf,vm,zr)],[u[0],u[1],0],[[it.v0,zb],[it.v1,zb],[vm,zr],[vm,zr]]);                        /* the plain tympanum */
  Q('kasota',[P(sf+.15,it.v0-.2,zb),P(sf+.15,vm,zr),P(sf+.15,vm,zr+th),P(sf+.15,it.v0-.2,zb+th)],[u[0],u[1],0],[[0,0],[1,0],[1,.5],[0,.5]]);          /* raking cornice, front, both slopes */
  Q('kasota',[P(sf+.15,vm,zr),P(sf+.15,it.v1+.2,zb),P(sf+.15,it.v1+.2,zb+th),P(sf+.15,vm,zr+th)],[u[0],u[1],0],[[0,0],[1,0],[1,.5],[0,.5]]);
  Q('rooftile',[P(sf+.3,it.v0-oh,zA),P(sb,it.v0-oh,zA),P(sb,vm,zr+th),P(sf+.3,vm,zr+th)],[-d[0]*.3,-d[1]*.3,1],[[0,0],[sf-sb,0],[sf-sb,vm-it.v0],[0,vm-it.v0]]);   /* the two roof slopes */
  Q('rooftile',[P(sf+.3,it.v1+oh,zA2),P(sb,it.v1+oh,zA2),P(sb,vm,zr+th),P(sf+.3,vm,zr+th)],[d[0]*.3,d[1]*.3,1],[[0,0],[sf-sb,0],[sf-sb,it.v1-vm],[0,it.v1-vm]]);
  Q('kasota',[P(sf,it.v0,zb),P(sb,it.v0,zb),P(sb,it.v1,zb),P(sf,it.v1,zb)],[0,0,-1],[[0,it.v0],[sf-sb,it.v0],[sf-sb,it.v1],[0,it.v1]]); };                  /* the soffit under the roof */
ITEM.parapet=function(G,mb,it){ var A=it.a, B=it.b, L=Math.hypot(B[0]-A[0],B[1]-A[1]), rot=Math.atan2(B[1]-A[1],B[0]-A[0]), k=matName(it.m,'marble');
  if(it.bal){ var cx=(A[0]+B[0])/2, cy=(A[1]+B[1])/2, z=it.z, w=it.w; box(mb,k,cx,cy,z,L,w,.16,rot,{}); box(mb,k,cx,cy,z+it.h-.14,L+.06,w+.08,.14,rot,{b:1}); box(mb,k,cx,cy,z+it.h-.2,L,w*.8,.06,rot,{b:1,t:1});
    var n=Math.max(2,Math.floor(L/.32)); for(var i=0;i<n;i++){ var t=(i+.5)/n, x=A[0]+(B[0]-A[0])*t, y=A[1]+(B[1]-A[1])*t, bh=it.h-.36;
      lathe(mb,k,x,y,[[.07,z+.16],[.09,z+.2],[.05,z+.16+bh*.25],[.1,z+.16+bh*.55],[.05,z+.16+bh*.85],[.08,z+.16+bh]],10); }
    [A,B].forEach(function(p){ box(mb,k,p[0],p[1],z,w+.1,w+.1,it.h,rot,{}); }); return; }
  box(mb,k,(A[0]+B[0])/2,(A[1]+B[1])/2,it.z,L,Math.max(.12,it.w),it.h-.06,rot,{b:1}); box(mb,k,(A[0]+B[0])/2,(A[1]+B[1])/2,it.z+it.h-.06,L+.04,Math.max(.12,it.w)+.06,.06,rot,{b:1}); };
ITEM.rail=function(G,mb,it){ var A=it.a, B=it.b, z=it.z, dx=B[0]-A[0], dy=B[1]-A[1], L=Math.hypot(dx,dy), rot=Math.atan2(dy,dx), cx=(A[0]+B[0])/2, cy=(A[1]+B[1])/2;
  box(mb,'gilt',cx,cy,z+.96,L,.06,.045,rot); box(mb,'bronze',cx,cy,z+.08,L,.04,.03,rot);
  var nb=Math.max(2,Math.round(L/.13)); for(var i=0;i<=nb;i++){ var t=i/nb, x=A[0]+dx*t, y=A[1]+dy*t; box(mb,'bronze',x,y,z,.022,.022,.97,rot,{b:1,t:1}); }
  [A,B].forEach(function(p){ box(mb,'bronze',p[0],p[1],z,.07,.07,1.0,rot); }); };
ITEM.col=function(G,mb,it){ var c=it.c, z0=it.z0, h=it.h, ext=!it.room, k=matName(c.m,'kasota'), x=c.p[0], y=c.p[1]; if(k==='stone'||k==='limestone') k='kasota';
  if(c.r!=null){ var r=c.r, o=(c.o||'').toLowerCase(), rich=/ionic|corinth|composite/.test(o);
    box(mb,k,x,y,z0,r*2.5,r*2.5,.12,0,{b:1});
    var cap=rich?r*1.2:r*.95, sh0=z0+.12+r*.35, sh1=z0+h-cap-.14;
    lathe(mb,k,x,y,[[r*1.16,z0+.12],[r*1.17,z0+.12+r*.12],[r*1.08,z0+.12+r*.2],[r*1.02,z0+.12+r*.3],[r,sh0],[r*.94,sh0+(sh1-sh0)*.6],[r*.86,sh1],[r*.88,sh1+.04],[r*.86,sh1+.06],
      rich?[r*1.08,sh1+cap*.55]:[r*1.08,sh1+cap*.7],rich?[r*1.25,sh1+cap]:[r*1.2,sh1+cap]],48,[20,.07,sh0+.01,sh1-.01]);
    box(mb,k,x,y,sh1+cap,r*2.6,r*2.6,Math.max(.1,z0+h-(sh1+cap)),0,{});
    if(ext&&r>.45) for(var q=0;q<4;q++){ var a=PI/4+q*PI/2, vx=x+Math.cos(a)*r*1.18, vy=y+Math.sin(a)*r*1.18, vz=sh1+cap*.62;        /* Ionic angle volutes (the order from published descriptions; the capital's detail is assumed) */
      var vr=r*.3, prev=null; for(var t=0;t<=10;t++){ var th=t/10*PI*2.2, rr=vr*(1-t/12), p=[vx+Math.cos(a)*Math.cos(th)*rr*.4,vy+Math.sin(a)*Math.cos(th)*rr*.4,vz+Math.sin(th)*rr]; if(prev) limb(mb,k,prev,p,r*.07,r*.07,6); prev=p; } } }
  else { var w=c.sz[0], d=c.sz[1]; box(mb,k,x,y,z0,w*1.12,d*1.12,.22,0,{b:1}); box(mb,k,x,y,z0+.22,w*1.04,d*1.04,.06,0,{b:1}); box(mb,k,x,y,z0+.28,w,d,h-.28-.3,0,{b:1,t:1});
    box(mb,k,x,y,z0+h-.3,w*1.05,d*1.05,.1,0,{b:1}); box(mb,k,x,y,z0+h-.2,w*1.12,d*1.12,.2,0,{b:1}); } };
/* ── sculpture: smooth figures from signed distances (tapered capsules and ellipsoids blended by smooth unions, robes with folds), meshed once by
   surface nets at load and cached; units are the figure's height, x forward, y its left, z up ── */
var SCU={};
function sdC(a,b,r0,r1,k,fold){ var ba=sub(b,a), L2=dot(ba,ba)||1e-9, u=nrm(cross(ba,Math.abs(ba[2])<.9*Math.sqrt(L2)?[0,0,1]:[1,0,0])), v=nrm(cross(ba,u)), R=Math.sqrt(L2)/2+Math.max(r0,r1)+(fold?fold[0]:0);
  return {t:0, a:a, ba:ba, ib:1/L2, r0:r0, r1:r1, k:k||0, u:u, v:v, fd:fold, c:[(a[0]+b[0])/2,(a[1]+b[1])/2,(a[2]+b[2])/2], R:R}; }
function sdE(c,r,rot,tilt,k){ var cr=Math.cos(rot||0), sr=Math.sin(rot||0), ct=Math.cos(tilt||0), st=Math.sin(tilt||0);
  return {t:1, c:c, r:r, k:k||0, m:[cr,sr,0, -ct*sr,ct*cr,st, st*sr,-st*cr,ct], R:Math.max(r[0],r[1],r[2])}; }
function sdAll(P,x,y,z,ix){ var d=1e9, n=ix?ix.length:P.length;
  for(var i0=0;i0<n;i0++){ var q=P[ix?ix[i0]:i0], dx=x-q.c[0], dy=y-q.c[1], dz=z-q.c[2]; if(Math.sqrt(dx*dx+dy*dy+dz*dz)-q.R>d+q.k) continue; var e;
    if(q.t===0){ var ax=x-q.a[0], ay=y-q.a[1], az=z-q.a[2], h=clamp((ax*q.ba[0]+ay*q.ba[1]+az*q.ba[2])*q.ib,0,1), ex=ax-q.ba[0]*h, ey=ay-q.ba[1]*h, ez=az-q.ba[2]*h;
      e=Math.sqrt(ex*ex+ey*ey+ez*ez)-(q.r0+(q.r1-q.r0)*h);
      if(q.fd){ var an=Math.atan2(ex*q.v[0]+ey*q.v[1]+ez*q.v[2],ex*q.u[0]+ey*q.u[1]+ez*q.u[2]); e-=q.fd[0]*Math.pow(h,q.fd[2]||1)*(Math.sin(an*q.fd[1])+.35*Math.sin(an*q.fd[1]*2.3+1.7)); } }
    else { var M=q.m, r=q.r, lx=(dx*M[0]+dy*M[1]+dz*M[2]), ly=(dx*M[3]+dy*M[4]+dz*M[5]), lz=(dx*M[6]+dy*M[7]+dz*M[8]), a0=lx/r[0], a1=ly/r[1], a2=lz/r[2], k0=Math.sqrt(a0*a0+a1*a1+a2*a2), k1=Math.sqrt(a0*a0/(r[0]*r[0])+a1*a1/(r[1]*r[1])+a2*a2/(r[2]*r[2]));
      e=k1>1e-9?k0*(k0-1)/k1:-Math.min(r[0],r[1],r[2]); }
    if(q.k>0){ var hh=clamp(.5+.5*(e-d)/q.k,0,1); d=e+(d-e)*hh-q.k*hh*(1-hh); } else if(e<d) d=e; }
  return P.cut!=null?Math.max(d,P.cut-z):d; }
/* surface nets: one vertex per cell the surface crosses, one quad per crossed grid edge; normals from the field's gradient */
function sdMesh(P,cs){ var b0=[1e9,1e9,1e9], b1=[-1e9,-1e9,-1e9]; P.forEach(function(q){ for(var j=0;j<3;j++){ b0[j]=Math.min(b0[j],q.c[j]-q.R-q.k); b1[j]=Math.max(b1[j],q.c[j]+q.R+q.k); } });
  if(P.cut!=null) b0[2]=Math.max(b0[2],P.cut-cs*2); for(var j0=0;j0<3;j0++){ b0[j0]-=cs*1.5; b1[j0]+=cs*1.5; }
  var nx=Math.ceil((b1[0]-b0[0])/cs)+1, ny=Math.ceil((b1[1]-b0[1])/cs)+1, nz=Math.ceil((b1[2]-b0[2])/cs)+1, N=[nx,ny,nz], V=new Float32Array(nx*ny*nz), C=new Int32Array(nx*ny*nz);
  /* coarse first (every 4th node); a fine node is evaluated only where the coarse field says the surface may be near (the field is 1-Lipschitz) */
  var cx=Math.ceil(nx/4)+1, cy=Math.ceil(ny/4)+1, cz=Math.ceil(nz/4)+1, CV=new Float32Array(cx*cy*cz), lim=cs*4.2;
  var CI=[];      /* per coarse node near the surface: the primitives that can matter within reach of it */
  for(var k1=0;k1<cz;k1++) for(var j1=0;j1<cy;j1++) for(var i1=0;i1<cx;i1++){ var X=b0[0]+i1*4*cs, Y=b0[1]+j1*4*cs, Z=b0[2]+k1*4*cs, ci1=i1+cx*(j1+cy*k1), dv=sdAll(P,X,Y,Z); CV[ci1]=dv;
    if(Math.abs(dv)<=lim){ var ix=[]; for(var pi=0;pi<P.length;pi++){ var q=P[pi]; if(Math.hypot(X-q.c[0],Y-q.c[1],Z-q.c[2])-q.R<=Math.abs(dv)+q.k+cs*8) ix.push(pi); } CI[ci1]=ix; } }
  for(var k=0;k<nz;k++) for(var j=0;j<ny;j++) for(var i=0;i<nx;i++){ var cc=((i+2)>>2)+cx*(((j+2)>>2)+cy*((k+2)>>2)), cv=CV[cc];
    V[i+nx*(j+ny*k)]=Math.abs(cv)>lim?cv:sdAll(P,b0[0]+i*cs,b0[1]+j*cs,b0[2]+k*cs,CI[cc]); }
  var O=[[0,0,0],[1,0,0],[0,1,0],[1,1,0],[0,0,1],[1,0,1],[0,1,1],[1,1,1]], E=[[0,1],[2,3],[4,5],[6,7],[0,2],[1,3],[4,6],[5,7],[0,4],[1,5],[2,6],[3,7]], vp=[], vn=[], g=new Float32Array(8), qs=[];
  var OF=[0,1,nx,nx+1,nx*ny,nx*ny+1,nx*ny+nx,nx*ny+nx+1], c2s=cs*2; C.fill(-1);
  for(var k2=0;k2<nz-1;k2++) for(var j2=0;j2<ny-1;j2++) for(var i2=0;i2<nx-1;i2++){ var m=0, ci=i2+nx*(j2+ny*k2); if(V[ci]>c2s||V[ci]<-c2s) continue;
    for(var c=0;c<8;c++){ var gv=V[ci+OF[c]]; g[c]=gv; if(gv<0) m|=1<<c; } if(m===0||m===255) continue;
    var sx=0, sy=0, sz=0, n=0; for(var e=0;e<12;e++){ var a=E[e][0], b=E[e][1]; if((g[a]<0)!==(g[b]<0)){ var t=g[a]/(g[a]-g[b]); sx+=O[a][0]+(O[b][0]-O[a][0])*t; sy+=O[a][1]+(O[b][1]-O[a][1])*t; sz+=O[a][2]+(O[b][2]-O[a][2])*t; n++; } }
    var px=b0[0]+(i2+sx/n)*cs, py=b0[1]+(j2+sy/n)*cs, pz=b0[2]+(k2+sz/n)*cs, h=cs*.5; C[ci]=vp.length/3; vp.push(px,py,pz);
    var gr=nrm([sdAll(P,px+h,py,pz)-sdAll(P,px-h,py,pz),sdAll(P,px,py+h,pz)-sdAll(P,px,py-h,pz),sdAll(P,px,py,pz+h)-sdAll(P,px,py,pz-h)]); vn.push(gr[0],gr[1],gr[2]); }
  for(var k3=1;k3<nz-1;k3++) for(var j3=1;j3<ny-1;j3++) for(var i3=1;i3<nx-1;i3++){ var c0=i3+nx*(j3+ny*k3), v0=V[c0];
    for(var ax=0;ax<3;ax++){ var st=ax===0?1:ax===1?nx:nx*ny, v1=V[c0+st]; if((v0<0)===(v1<0)) continue; if((ax===0?i3:ax===1?j3:k3)>=N[ax]-1) continue;
      var su=ax===0?nx:ax===1?nx*ny:1, sw=ax===0?nx*ny:ax===1?1:nx, q4=[C[c0-su-sw],C[c0-sw],C[c0],C[c0-su]]; if(q4[0]<0||q4[1]<0||q4[2]<0||q4[3]<0) continue; qs.push(q4[0],q4[1],q4[2],q4[3]); } }
  return {v:vp, n:vn, q:qs}; }
function sdEmit(mb,k,M,x,y,z0,s,rot){ var cr=Math.cos(rot), sr=Math.sin(rot), v=M.v, n=M.n, q=M.q, W=function(i){ var a=v[i*3], b=v[i*3+1]; return [x+(a*cr-b*sr)*s,y+(a*sr+b*cr)*s,z0+v[i*3+2]*s]; },
    Nn=function(i){ var a=n[i*3], b=n[i*3+1]; return [a*cr-b*sr,a*sr+b*cr,n[i*3+2]]; }, T=function(p){ return [p[0]+p[1],p[2]]; };
  for(var i=0;i<q.length;i+=4){ var P=[W(q[i]),W(q[i+1]),W(q[i+2]),W(q[i+3])]; mb.quad(k,P,[Nn(q[i]),Nn(q[i+1]),Nn(q[i+2]),Nn(q[i+3])],P.map(T)); } }
function sdGet(key,mk,cs){ var M=SCU[key]; if(!M){ M=SCU[key]=sdMesh(mk(),cs); } return M; }
/* Saint-Gaudens' Diana (PMA: gilded copper, 14 ft 6 in): poised on the toes of the left foot on a ball, right leg reaching back, the left arm holding the
   bow out in front, the right hand drawing the string to the cheek; hair in a knot with a crescent over the brow. No drapery (none is modelled: unverified). */
function dianaPrims(){ var C=sdC, E=sdE, P=[], br=.07;
  P.push(E([0,0,-br],[br,br,br],0,0,0));
  P.push(C([.012,.022,0],[-.035,.024,.07],.016,.022,.01), C([-.035,.024,.07],[-.006,.038,.3],.025,.043,.018), C([-.006,.038,.3],[-.02,.055,.53],.04,.057,.025));
  P.push(C([-.03,-.05,.53],[-.21,-.06,.385],.057,.04,.025), C([-.21,-.06,.385],[-.43,-.068,.33],.043,.025,.018), C([-.43,-.068,.33],[-.525,-.07,.322],.022,.014,.012));
  P.push(E([-.026,0,.55],[.075,.1,.075],0,.1,.035), E([-.012,0,.64],[.058,.074,.065],0,.12,.04), E([.012,0,.73],[.072,.094,.1],0,.14,.04));
  P.push(E([.06,.043,.738],[.024,.026,.024],0,0,.018), E([.06,-.043,.738],[.024,.026,.024],0,0,.018));
  P.push(E([.022,.098,.808],[.036,.04,.036],0,0,.03), E([.004,-.098,.808],[.036,.04,.036],0,0,.03));
  P.push(C([.02,0,.8],[.032,0,.877],.032,.027,.03), E([.044,0,.93],[.053,.044,.064],0,.12,.02), E([.022,0,.948],[.055,.047,.056],0,.25,.012), E([-.022,0,.952],[.032,.03,.03],0,0,.012));
  P.push(C([.02,.1,.81],[.17,.086,.828],.031,.024,.02), C([.17,.086,.828],[.31,.076,.845],.024,.018,.015), E([.33,.073,.845],[.026,.019,.031],0,0,.012));
  P.push(C([.004,-.1,.81],[-.13,-.13,.852],.031,.025,.02), C([-.13,-.13,.852],[.022,-.046,.866],.025,.018,.015), E([.042,-.04,.866],[.026,.019,.026],0,0,.012));
  return P; }
function diana(mb,k,x,y,z0,H,rot){ var h=H/1.14, br=.07*h, M=sdGet('diana',dianaPrims,1/100), zf=z0+2*br; sdEmit(mb,k,M,x,y,zf,h,rot);
  var cr=Math.cos(rot), sr=Math.sin(rot), W=function(a,b,c){ return [x+(a*cr-b*sr)*h,y+(a*sr+b*cr)*h,zf+c*h]; }, bow=[];
  for(var i=0;i<=12;i++){ var t=i/6-1; bow.push(W(.33-.07*t*t,.073,.845+.31*t)); } for(var j=0;j<12;j++) limb(mb,k,bow[j],bow[j+1],.009*h*(1.3-.5*Math.abs(j/6-1)),.009*h*(1.3-.5*Math.abs((j+1)/6-1)),6);
  limb(mb,k,bow[0],W(.04,-.04,.866),.0025*h,.0025*h,4); limb(mb,k,W(.04,-.04,.866),bow[12],.0025*h,.0025*h,4); limb(mb,k,W(.03,-.042,.866),W(.44,.075,.846),.0045*h,.0035*h,5);
  var cm=[]; for(var c=0;c<=8;c++){ var a=-1.25+2.5*c/8; cm.push(W(.072,Math.sin(a)*.032,.99+Math.cos(a)*.028-.028)); } for(var c2=0;c2<8;c2++) limb(mb,k,cm[c2],cm[c2+1],.004*h,.004*h,5); }
/* a standing draped figure (weight on the right leg, a mantle over the left arm), and a portrait bust */
function robedPrims(){ var C=sdC, E=sdE, P=[];
  P.push(C([.01,0,.6],[.02,0,.02],.1,.165,.04,[.011,15,1.4]), C([.1,.11,.66],[.075,.15,.3],.035,.06,.04,[.007,9,1]));
  P.push(E([.075,.055,.02],[.05,.032,.02],0,0,.01), E([.07,-.06,.02],[.05,.032,.02],.15,0,.01));
  P.push(E([0,0,.56],[.085,.115,.085],0,0,.04), E([.005,0,.72],[.078,.106,.11],0,0,.04), E([.01,.02,.775],[.07,.11,.06],.2,.3,.03));
  P.push(E([0,.108,.808],[.036,.04,.036],0,0,.03), E([0,-.108,.808],[.036,.04,.036],0,0,.03));
  P.push(C([.005,0,.8],[.012,0,.875],.033,.028,.03), E([.022,0,.93],[.053,.044,.064],.12,.05,.02), E([.004,0,.95],[.056,.048,.058],.12,.2,.015));
  P.push(C([0,-.112,.805],[.012,-.13,.64],.032,.026,.02), C([.012,-.13,.64],[.05,-.125,.5],.026,.019,.015), E([.06,-.122,.47],[.02,.024,.035],0,0,.012));
  P.push(C([0,.112,.805],[.02,.14,.65],.032,.026,.02), C([.02,.14,.65],[.13,.085,.69],.026,.019,.015), E([.15,.08,.69],[.03,.02,.024],0,0,.012));
  return P; }
function bustPrims(){ var E=sdE, C=sdC, P=[E([0,0,.3],[.2,.36,.2],0,0,.05), C([.02,0,.42],[.04,0,.62],.11,.095,.06), E([.06,0,.78],[.15,.125,.18],0,.1,.04), E([.03,0,.83],[.155,.135,.16],0,.25,.02), E([.2,0,.75],[.03,.022,.05],0,-.2,.02)];
  P.cut=.22; return P; }
function figure(mb,k,x,y,z0,H,rot){ sdEmit(mb,k,sdGet('robed',robedPrims,1/80),x,y,z0,H,rot+PI/2); }
function archer(mb,k,x,y,z0,H,rot){ diana(mb,k,x,y,z0,H,rot+PI/2); }          /* shown in profile to someone climbing the stair (her facing is assumed) */
function sculpture(mb,k,x,y,z0,W,H,seed){ var s=seed%3;
  if(s<1) lathe(mb,k,x,y,[[0,z0],[W*.12,z0],[W*.1,z0+H*.08],[W*.05,z0+H*.14],[W*.16,z0+H*.4],[W*.22,z0+H*.62],[W*.14,z0+H*.86],[W*.04,z0+H*.98],[0,z0+H]],24);
  else if(s<2) lathe(mb,k,x,y,[[0,z0],[W*.3,z0],[W*.42,z0+H*.3],[W*.45,z0+H*.55],[W*.36,z0+H*.82],[W*.18,z0+H*.97],[0,z0+H]],28);
  else { var bh=Math.min(H,W*1.6); lathe(mb,k,x,y,[[W*.16,z0],[W*.16,z0+bh*.06],[W*.1,z0+bh*.1],[W*.07,z0+bh*.2],[0,z0+bh*.2]],16); sdEmit(mb,k,sdGet('bust',bustPrims,1/70),x,y,z0+bh*.2-bh*.22,bh,0); } }
ITEM.fx=function(G,mb,it,b){ var f=it.f, x=f.p[0], y=f.p[1], z0=it.z0, w=f.sz[0], d=f.sz[1], h=f.sz[2], rot=it.rot, k=matName(f.m,null), K=f.k;
  var seed=Math.floor(hash(f.id)*1000);
  if(K==='bench'){ var c5=Math.cos(rot), s5=Math.sin(rot); [-1,1].forEach(function(e5){ var u5=e5*(w/2-.12); box(mb,'bronze',x+u5*c5,y+u5*s5,z0,.05,d*.8,h-.12,rot,{b:1}); }); box(mb,'bronze',x,y,z0+h-.16,w*.9,d*.8,.03,rot,{b:1}); box(mb,'benchtop',x,y,z0+h-.13,w,d,.13,rot,{b:1}); }
  else if(K==='other'&&/rope|stanchion/i.test(f.n||'')){ var c4=Math.cos(rot), s4=Math.sin(rot), np=Math.max(2,Math.round(w/1.7)+1), pts=[];
    for(var i4=0;i4<np;i4++){ var u4=-w/2+w*i4/(np-1), px4=x+u4*c4, py4=y+u4*s4; pts.push([px4,py4]); lathe(mb,'gilt',px4,py4,[[.16,z0],[.16,z0+.02],[.05,z0+.05],[.022,z0+.08],[.018,z0+h-.06],[.03,z0+h-.04],[.035,z0+h],[0,z0+h+.03]],12); }
    for(var j4=0;j4+1<pts.length;j4++){ var A4=pts[j4], B4=pts[j4+1], prev=[A4[0],A4[1],z0+h-.08]; for(var t4=1;t4<=8;t4++){ var tt=t4/8, sg4=Math.sin(tt*PI)*.2, q4=[A4[0]+(B4[0]-A4[0])*tt,A4[1]+(B4[1]-A4[1])*tt,z0+h-.08-sg4]; limb(mb,'carpet',prev,q4,.022,.022,6); prev=q4; } } }
  else if(K==='case'){ var hb=Math.min(.86,h*.6); box(mb,k&&!/bronze|gilt|metal|copper/.test(k)?k:'paint#plinth',x,y,z0,w,d,hb,rot,{b:1}); box(mb,'bronze',x,y,z0+hb,w+.02,d+.02,.03,rot,{b:1});
    var hg=h-hb-.03, zg=z0+hb+.03, c=Math.cos(rot), s=Math.sin(rot), cn=[[-1,-1],[1,-1],[1,1],[-1,1]];
    cn.forEach(function(q){ box(mb,'bronze',x+(q[0]*w/2)*c-(q[1]*d/2)*s,y+(q[0]*w/2)*s+(q[1]*d/2)*c,zg,.02,.02,hg,rot,{b:1}); });
    box(mb,'glass',x,y,zg,w,d,hg,rot,{b:1}); b.trans.glass=1; box(mb,'bronze',x,y,zg+hg,w+.01,d+.01,.02,rot,{b:1});
    sculpture(mb,seed%2?'terracotta':'bronze',x,y,zg,Math.min(w,d)*.7,Math.min(hg*.7,.45),seed%2); }
  else if(K==='plinth'){ var bearsStatue=(S.G.plan.fx||[]).some(function(o){ return o.k==='statue'&&o.l===f.l&&o.p&&Math.hypot(o.p[0]-x,o.p[1]-y)<.6; });
    if(k&&k!=='paint'){ var pk=k==='stone'?(it.room&&/^(limestone|stone)$/.test(it.room.wm)?'kasota':'marble'):k; box(mb,pk,x,y,z0,w*1.12,d*1.12,.18,rot,{b:1}); box(mb,pk,x,y,z0+.18,w,d,h-.36,rot,{b:1,t:1}); box(mb,pk,x,y,z0+h-.18,w*1.1,d*1.1,.18,rot,{b:1}); }
    else { box(mb,'paint#plinth',x,y,z0+.03,w,d,h-.03,rot,{b:1}); box(mb,'bronze',x,y,z0,w-.04,d-.04,.03,rot,{b:1,t:1}); }
    if(!bearsStatue) sculpture(mb,seed%2?'statuary':'bronze',x,y,z0+h,Math.min(w,d)*.8,Math.min(.9,Math.max(.3,1.8-h)),seed); }
  else if(K==='statue'){ var sk=k==='gilt'?'giltpol':k==='bronze'||k==='copper'?k:'statuary';
    if(it.on){ if(/diana/i.test(f.n||'')) archer(mb,sk,x,y,z0+it.on,h,rot+PI/2); else figure(mb,sk,x,y,z0+it.on,h,rot); }
    else { var ph=Math.min(1.1,h*.35); box(mb,k&&!/gilt|bronze|copper/.test(k)?k:'marble',x,y,z0,w,d,ph,rot,{b:1}); box(mb,'marble',x,y,z0+ph,w*1.05,d*1.05,.06,rot,{b:1}); figure(mb,sk,x,y,z0+ph+.06,h-ph-.06,rot); } }
  else if(K==='table'||K==='desk'||K==='counter'){ var tk=k||'wood'; if(K==='counter') box(mb,tk,x,y,z0,w*.96,d*.9,h-.04,rot,{b:1}); else { var c2=Math.cos(rot), s2=Math.sin(rot);
      [[-1,-1],[1,-1],[1,1],[-1,1]].forEach(function(q){ var lx=q[0]*(w/2-.06), ly=q[1]*(d/2-.06); box(mb,tk,x+lx*c2-ly*s2,y+lx*s2+ly*c2,z0,.06,.06,h-.04,rot,{b:1,t:1}); }); if(K==='desk') box(mb,tk,x,y,z0+h-.22,w-.08,d-.08,.18,rot,{}); }
    box(mb,tk,x,y,z0+h-.04,w,d,.04,rot,{}); }
  else if(K==='shelf'){ var sk=k||'wood', n=Math.max(2,Math.floor(h/.36)), c3=Math.cos(rot), s3=Math.sin(rot), R=rng(hash(f.id));
    box(mb,sk,x,y,z0,w,d,.08,rot,{b:1}); for(var i=1;i<=n;i++) box(mb,sk,x,y,z0+h*i/n-.025,w,d,.025,rot,{});
    [-1,1].forEach(function(sd){ var lx=sd*(w/2-.015); box(mb,sk,x+lx*c3,y+lx*s3,z0,.03,d,h,rot,{}); }); var ox=-d/2+.01; box(mb,sk,x-ox*s3*-1,y+ox*c3,z0,w,.02,h,rot,{});
    var cols=[[.42,.12,.1],[.12,.2,.3],[.2,.28,.16],[.5,.4,.22],[.3,.16,.2],[.62,.55,.42]];
    for(var j=0;j<n;j++){ var zz=z0+(j?h*j/n:.08), uu=-w/2+.04; while(uu<w/2-.08){ var bw=.025+R()*.045, bh=.2+R()*.12; if(uu+bw>w/2-.04) break; var lx2=uu+bw/2;
        box(mb,'book'+Math.floor(R()*6),x+lx2*c3-(-.02)*s3,y+lx2*s3+(-.02)*c3,zz,bw,d*.75,Math.min(bh,h/n-.05),rot,{b:1}); uu+=bw+.002; } } }
  else if(K==='fountain'){ var R2=Math.min(w,d)/2; lathe(mb,k||'marble',x,y,[[R2*.8,z0],[R2,z0+.05],[R2,z0+h*.6],[R2*.92,z0+h*.62],[R2*.9,z0+h*.3]],40);
    flat(mb,'water',[circ(x,y,R2*.9,40)],z0+h*.5,true); b.trans.water=1; lathe(mb,k||'marble',x,y,[[R2*.12,z0+h*.3],[R2*.1,z0+h*.9],[R2*.3,z0+h],[R2*.05,z0+h*1.05]],20); }
  else box(mb,k||(K==='stove'?'metal':'wood'),x,y,z0,w,d,h,rot,{b:1}); };
function circ(x,y,r,n){ var o=[]; for(var i=0;i<n;i++){ var a=i/n*2*PI; o.push([x+Math.cos(a)*r,y+Math.sin(a)*r]); } return o; }
ITEM.slot=function(G,mb,it,b){ var s=it.s, r=it.room, n=it.n, d=it.d, W=s.sz[0], H=s.sz[1], cz=it.z, al=s.al||['any'], seed=hash(s.id);
  if(s.card){ var px=s.p[0], py=s.p[1], z0=r.l.e, ik0='art#'+it.ord, Fc=function(u,w,z){ return [px+d[0]*u+n[0]*w,py+d[1]*u+n[1]*w,z]; }, hw0=W/2, hh0=H/2, rt=Math.atan2(d[1],d[0]); b.art.push({it:it, key:ik0, paper:true, cloth:false});
    box(mb,'bronze',px,py,z0,.52,.36,.035,rt,{b:1}); box(mb,'bronze',px,py,z0+.035,.07,.07,cz-hh0-z0-.1,rt,{b:1,t:1}); box(mb,'bronze',px,py,cz-hh0-.07,W+.07,.05,H+.14,rt,{b:1});
    mb.quad(ik0,[Fc(-hw0,.03,cz-hh0),Fc(hw0,.03,cz-hh0),Fc(hw0,.03,cz+hh0),Fc(-hw0,.03,cz+hh0)],[n[0],n[1],0],[[0,0],[1,0],[1,1],[0,1]]);
    mb.quad(ik0,[Fc(hw0,-.03,cz-hh0),Fc(-hw0,-.03,cz-hh0),Fc(-hw0,-.03,cz+hh0),Fc(hw0,-.03,cz+hh0)],[-n[0],-n[1],0],[[0,0],[1,0],[1,1],[0,1]]); return; }
  if(it.sculpt){ var ph=H<1.2?1.0:.45, pw=Math.max(.42,W*.9); box(mb,'paint#plinth',s.p[0],s.p[1],r.l.e+.03,pw,pw,ph-.03,Math.atan2(n[1],n[0]),{b:1}); box(mb,'bronze',s.p[0],s.p[1],r.l.e,pw-.04,pw-.04,.03,0,{b:1,t:1});
    if(H>=1.2) figure(mb,seed>.5?'bronze':'statuary',s.p[0],s.p[1],r.l.e+ph,H,Math.atan2(n[1],n[0])-PI/2); else sculpture(mb,seed>.5?'bronze':'statuary',s.p[0],s.p[1],r.l.e+ph,W,H,Math.floor(seed*99));
    labelPlate(G,mb,b,it,[s.p[0]+n[0]*(pw/2+.004),s.p[1]+n[1]*(pw/2+.004)],r.l.e+ph-.18,n,d); return; }
  var paper=al.some(function(a){ return a==='drawing'||a==='print'||a==='text'; })&&al.indexOf('painting')<0, cloth=al.indexOf('tapestry')>=0||al.indexOf('textile')>=0;
  var o=[s.p[0]+n[0]*.004,s.p[1]+n[1]*.004], F=function(u,w,z){ return [o[0]+d[0]*u+n[0]*w,o[1]+d[1]*u+n[1]*w,z]; }, N3=[n[0],n[1],0];
  var fw=cloth?0:paper?.035:clamp(.045+.035*Math.max(W,H),.06,.14), dp=cloth?.01:paper?.035:clamp(.05+.02*Math.max(W,H),.055,.1), hw=W/2, hh=H/2;
  /* contact shadow on the wall */
  var sm=.07+dp*.6; mb.quad('shadow',[F(-hw-sm,.001,cz-hh-sm-.03),F(hw+sm,.001,cz-hh-sm-.03),F(hw+sm,.001,cz+hh+sm-.03),F(-hw-sm,.001,cz+hh+sm-.03)],N3,[[-1,-1],[1,-1],[1,1],[-1,1]],[0,0,Math.round(hw/(hw+sm)*255),Math.round(hh/(hh+sm)*255)]); b.trans.shadow=1;
  var ik='art#'+it.ord; b.art.push({it:it, key:ik, paper:paper, cloth:cloth, text:al.indexOf('text')>=0&&al.indexOf('painting')<0});
  if(cloth){ mb.quad(ik,[F(-hw,.012,cz-hh),F(hw,.012,cz-hh),F(hw,.012,cz+hh),F(-hw,.012,cz+hh)],N3,[[0,0],[1,0],[1,1],[0,1]]); limb(mb,'gilt',F(-hw-.05,.03,cz+hh+.02),F(hw+.05,.03,cz+hh+.02),.014,.014,8); }
  else { var fk=paper?'frame#dark':'gilt', O=[[-hw,-hh],[hw,-hh],[hw,hh],[-hw,hh]], I=O.map(function(p){ return [p[0]-Math.sign(p[0])*fw,p[1]-Math.sign(p[1])*fw]; }), M=O.map(function(p,i){ return [p[0]+(I[i][0]-p[0])*.4,p[1]+(I[i][1]-p[1])*.4]; });
    for(var i=0;i<4;i++){ var j=(i+1)%4, mid=[(O[i][0]+O[j][0])/2,(O[i][1]+O[j][1])/2], outv=[d[0]*Math.sign(mid[0])*(Math.abs(mid[0])>1e-6?1:0),d[1]*Math.sign(mid[0])*(Math.abs(mid[0])>1e-6?1:0),Math.abs(mid[1])>1e-6?Math.sign(mid[1]):0];
      mb.qg(fk,[F(O[i][0],0,cz+O[i][1]),F(O[j][0],0,cz+O[j][1]),F(O[j][0],dp,cz+O[j][1]),F(O[i][0],dp,cz+O[i][1])],outv,[[0,0],[1,0],[1,dp],[0,dp]]);
      mb.qg(fk,[F(O[i][0],dp,cz+O[i][1]),F(O[j][0],dp,cz+O[j][1]),F(M[j][0],dp+.004,cz+M[j][1]),F(M[i][0],dp+.004,cz+M[i][1])],N3,[[O[i][0],O[i][1]],[O[j][0],O[j][1]],[M[j][0],M[j][1]],[M[i][0],M[i][1]]]);
      mb.qg(fk,[F(M[i][0],dp+.004,cz+M[i][1]),F(M[j][0],dp+.004,cz+M[j][1]),F(I[j][0],dp*.55,cz+I[j][1]),F(I[i][0],dp*.55,cz+I[i][1])],[N3[0]-outv[0]*.6,N3[1]-outv[1]*.6,-outv[2]*.6],[[M[i][0],M[i][1]],[M[j][0],M[j][1]],[I[j][0],I[j][1]],[I[i][0],I[i][1]]]);
      mb.qg(fk,[F(I[i][0],dp*.55,cz+I[i][1]),F(I[j][0],dp*.55,cz+I[j][1]),F(I[j][0],.012,cz+I[j][1]),F(I[i][0],.012,cz+I[i][1])],[-outv[0],-outv[1],-outv[2]],[[0,0],[1,0],[1,dp],[0,dp]]); }
    var iw=hw-fw, ih=hh-fw;
    if(paper){ var mm=Math.min(iw,ih)*.22; mb.quad('mat',[F(-iw,.012,cz-ih),F(iw,.012,cz-ih),F(iw,.012,cz+ih),F(-iw,.012,cz+ih)],N3,[[0,0],[1,0],[1,1],[0,1]]);
      var aw=iw-mm, ah=ih-mm; mb.quad(ik,[F(-aw,.0135,cz-ah),F(aw,.0135,cz-ah),F(aw,.0135,cz+ah),F(-aw,.0135,cz+ah)],N3,[[0,0],[1,0],[1,1],[0,1]]);
      mb.quad('glaze',[F(-iw,dp*.5,cz-ih),F(iw,dp*.5,cz-ih),F(iw,dp*.5,cz+ih),F(-iw,dp*.5,cz+ih)],N3,[[0,0],[1,0],[1,1],[0,1]]); b.trans.glaze=1; }
    else mb.quad(ik,[F(-iw,.012,cz-ih),F(iw,.012,cz-ih),F(iw,.012,cz+ih),F(-iw,.012,cz+ih)],N3,[[0,0],[1,0],[1,1],[0,1]]); }
  var lz=clamp(cz-hh*.35,r.l.e+1.25,r.l.e+1.5); labelPlate(G,mb,b,it,[o[0]+d[0]*(hw+.2),o[1]+d[1]*(hw+.2)],lz,n,d); };
function labelPlate(G,mb,b,it,p,z,n,d){ if(b.lab.length>=8) return; var idx=b.lab.length; b.lab.push(it); var w=.16, h=.08, cx=idx%4, cy=Math.floor(idx/4);
  var u0=cx/4, u1=(cx+1)/4, v0=1-.75-(cy+1)*.125, v1=1-.75-cy*.125, F=function(u,w2,zz){ return [p[0]+d[0]*u+n[0]*w2,p[1]+d[1]*u+n[1]*w2,zz]; };
  box(mb,'mat',p[0]+n[0]*.002,p[1]+n[1]*.002,z-h/2,w,.004,h,Math.atan2(d[1],d[0]),{b:1});
  mb.quad('lab',[F(-w/2,.0045,z-h/2),F(w/2,.0045,z-h/2),F(w/2,.0045,z+h/2),F(-w/2,.0045,z+h/2)],[n[0],n[1],0],[[u0,v0],[u1,v0],[u1,v1],[u0,v1]]); }
ITEM.lift=function(G,mb,it,b){ var st=it.st, l=it.lv, r=it.room, fp=st.fp, h=Math.min(r?r.ch:l.h,3.4), k=r?(r.wm==='paint'?'paint#'+r.i:r.wm):'limestone', ctr=interior(fp), tgt=r?r.ctr:ctr;
  var best=-1, bd=-1e9; for(var i=0,n=fp.length;i<n;i++){ var a=fp[i], c=fp[(i+1)%n], mx=(a[0]+c[0])/2, my=(a[1]+c[1])/2, ln=Math.hypot(c[0]-a[0],c[1]-a[1]);
    var out=[(c[1]-a[1])/ln,(a[0]-c[0])/ln]; if(parea(fp)<0) out=[-out[0],-out[1]]; var sc=(tgt[0]-mx)*out[0]+(tgt[1]-my)*out[1]+ln*.2; mb.qg(k,[[a[0],a[1],l.e],[c[0],c[1],l.e],[c[0],c[1],l.e+h],[a[0],a[1],l.e+h]],[out[0],out[1],0],[[0,l.e],[ln,l.e],[ln,l.e+h],[0,l.e+h]]); if(sc>bd&&ln>1.2){ bd=sc; best=i; } }
  flat(mb,'plaster',[fp],l.e+h,true);
  if(best>=0){ var A=fp[best], B=fp[(best+1)%fp.length], L=Math.hypot(B[0]-A[0],B[1]-A[1]), ux=(B[0]-A[0])/L, uy=(B[1]-A[1])/L, on=[uy,-ux]; if(parea(fp)<0) on=[-on[0],-on[1]];
    var mx2=(A[0]+B[0])/2+on[0]*.02, my2=(A[1]+B[1])/2+on[1]*.02, dw=Math.min(1.2,L-.3); box(mb,'bronze',mx2,my2,l.e,dw,.04,2.25,Math.atan2(uy,ux),{b:1});
    box(mb,'gilt',mx2,my2,l.e+2.25,dw+.16,.05,.1,Math.atan2(uy,ux),{b:1}); box(mb,'lens',mx2+on[0]*.03+ux*(dw/2+.18),my2+on[1]*.03+uy*(dw/2+.18),l.e+1.1,.05,.02,.1,Math.atan2(uy,ux),{b:1});
    b.picks.push({k:'lift', st:st, lv:l, rect:{c:[mx2+on[0]*.03,my2+on[1]*.03,l.e+1.1], n:[on[0],on[1],0], d:[ux,uy,0], hw:dw/2+.2, hh:1.15}, room:r}); } };
/* the room's floor, ceiling, laylight, stairwell and slab edges */
function floorKey(m,r){ if(m==='paint') return 'plaster'; if(m==='wood'||m==='plank') return 'board'; if(m==='stone'||m==='limestone') m='kasota';
  return r&&/^(marble|terrazzo|granite|kasota|tile)$/.test(m)&&(/hall|lobby|court/.test(r.ty)||Math.abs(parea(r.p))>60)?m+'#f':m; }
function buildRoomShell(G,mb,r){ if(r.isVoid) return; var e=r.l.e, holesF=r.holesF, rings=[r.p].concat(holesF);
  flat(mb,floorKey(r.fm,r),rings,e,true);
  var cr=[r.p].concat(r.holesC.map(function(h){ return h.p; })).concat(r.ceilHoles||[]), tall=r.ch>7, ck=tall&&r.cm!=='glass'?'coffer':r.cm==='glass'||r.cm==='paint'||r.cm==='terracotta'?'plaster':r.cm;
  if(r.cm==='glass'||(r.lk==='sky'&&!r.ceilHoles)){ var bb=r.bb, rect=Math.abs(parea(r.p))/((bb[2]-bb[0])*(bb[3]-bb[1]))>.92, fx=tall?.3:.14, ix=rect?Math.max(.6,(bb[2]-bb[0])*fx):0, iy=rect?Math.max(.6,(bb[3]-bb[1])*fx):0;
    if(rect&&bb[2]-bb[0]-2*ix>1&&bb[3]-bb[1]-2*iy>1){ var lay=[[bb[0]+ix,bb[1]+iy],[bb[2]-ix,bb[1]+iy],[bb[2]-ix,bb[3]-iy],[bb[0]+ix,bb[3]-iy]];
      flat(mb,tall?'coffer':'plaster',cr.concat([lay]),r.ceil,false); flat(mb,'lay',[lay],r.ceil-.005,false); r.lay=lay;
      for(var i=0;i<4;i++){ var a=lay[i], c=lay[(i+1)%4]; mb.qg('plaster',[[a[0],a[1],r.ceil-.005],[c[0],c[1],r.ceil-.005],[c[0],c[1],r.ceil],[a[0],a[1],r.ceil]],[(a[0]+c[0])/2-(bb[0]+bb[2])/2,(a[1]+c[1])/2-(bb[1]+bb[3])/2,0].map(function(v){ return -v; }),[[0,0],[1,0],[1,1],[0,1]]); } }
    else { flat(mb,'lay',cr,r.ceil,false); r.lay=r.p; } }
  else flat(mb,ck,cr,r.ceil,false);
  if(tall&&r.cm!=='glass') cofferBeams(mb,r,cr.slice(1));
  r.holesC.forEach(function(h){ var p=h.p, s=parea(p)>0?1:-1; for(var i=0,n=p.length;i<n;i++){ var a=p[i], c=p[(i+1)%n], inw=[-(c[1]-a[1])*s,(c[0]-a[0])*s,0];
    if(h.z1>r.ceil+.01) mb.qg('plaster',[[a[0],a[1],r.ceil],[c[0],c[1],r.ceil],[c[0],c[1],h.z1],[a[0],a[1],h.z1]],inw,[[0,r.ceil],[1,r.ceil],[1,h.z1],[0,h.z1]]); } });
  holesF.forEach(function(p){ var s=parea(p)>0?1:-1; for(var i=0,n=p.length;i<n;i++){ var a=p[i], c=p[(i+1)%n], inw=[-(c[1]-a[1])*s,(c[0]-a[0])*s,0];
    mb.qg(floorKey(r.fm,r),[[a[0],a[1],e-.32],[c[0],c[1],e-.32],[c[0],c[1],e],[a[0],a[1],e]],inw,[[0,e-.32],[1,e-.32],[1,e],[0,e]]); } });
  if(r.l.i>0){ var c0=r.ctr, below=!r.voidHole&&G.rooms.some(function(o){ return o.l.e<e&&o.ceil>=e-.6&&pip(o.p,c0[0],c0[1]); });
    if(!below){ flat(mb,r.voidHole?'coffer':'plaster',rings,e-.32,false); var s2=parea(r.p)>0?1:-1;
      for(var i2=0,n2=r.p.length;i2<n2;i2++){ var a2=r.p[i2], b2=r.p[(i2+1)%n2]; mb.qg('plaster',[[a2[0],a2[1],e-.32],[b2[0],b2[1],e-.32],[b2[0],b2[1],e],[a2[0],a2[1],e]],[(b2[1]-a2[1])*s2,-(b2[0]-a2[0])*s2,0],[[0,0],[1,0],[1,.32],[0,.32]]); } } } }
/* a tall room's coffers are real: beams on the 2.1 m grid the coffer texture is drawn on (its rosettes sit in the middle of each bay) */
function cofferBeams(mb,r,holes){ var bb=r.bb, P=2.1, z=r.ceil, bd=clamp(r.ch*.028,.3,.55), bw=.3, inside=function(x,y){ if(!pip(r.p,x,y)) return false; for(var i=0;i<holes.length;i++) if(pip(holes[i],x,y)) return false; return true; };
  var piece=function(x0,y0,x1,y1){ var mx=(x0+x1)/2, my=(y0+y1)/2, L=Math.hypot(x1-x0,y1-y0)+bw, rot=Math.atan2(y1-y0,x1-x0); if(!(inside(x0,y0)&&inside(x1,y1)&&inside(mx,my))) return;
    box(mb,'plaster',mx,my,z-bd,L,bw,bd,rot,{t:1}); box(mb,'plaster',mx,my,z-bd*.38,L,bw+.16,bd*.38,rot,{t:1,b:0}); };
  for(var gx=Math.ceil(bb[0]/P);gx*P<bb[2];gx++) for(var gy=Math.floor(bb[1]/P);gy*P<bb[3];gy++){ piece(gx*P,gy*P,gx*P,(gy+1)*P); }
  for(var hy=Math.ceil(bb[1]/P);hy*P<bb[3];hy++) for(var hx=Math.floor(bb[0]/P);hx*P<bb[2];hx++){ piece(hx*P,hy*P,(hx+1)*P,hy*P); } }
ITEM.shell=function(G,mb,it){ var sh=it.sh, p=sh.p, s=parea(p)>0?1:-1, k=matName(sh.m,'limestone'), z0=it.z0, top=it.top, n=p.length, rf=sh.rf||{k:'flat'};
  for(var i=0;i<n;i++){ var a=p[i], c=p[(i+1)%n], L=Math.hypot(c[0]-a[0],c[1]-a[1]); if(L<1e-6) continue; var out=[(c[1]-a[1])/L*s,-(c[0]-a[0])/L*s,0];
    if(top>z0+.01) mb.quad(k,[[a[0],a[1],z0],[c[0],c[1],z0],[c[0],c[1],top],[a[0],a[1],top]],out,[[0,z0],[L,z0],[L,top],[0,top]]); }
  /* the cornice: an extruded profile round the eave */
  var prof=[[0,top-.75],[.06,top-.72],[.06,top-.62],[.14,top-.55],[.42,top-.32],[.5,top-.3],[.5,top-.12],[.58,top-.08],[.58,top]];
  var off=function(i,w){ var pv=p[(i-1+n)%n], cu=p[i], nx=p[(i+1)%n], l0=Math.hypot(cu[0]-pv[0],cu[1]-pv[1])||1, l1=Math.hypot(nx[0]-cu[0],nx[1]-cu[1])||1;
    var n0=[(cu[1]-pv[1])/l0*s,-(cu[0]-pv[0])/l0*s], n1=[(nx[1]-cu[1])/l1*s,-(nx[0]-cu[0])/l1*s], m=[n0[0]+n1[0],n0[1]+n1[1]], dd=1+n0[0]*n1[0]+n0[1]*n1[1]; dd=dd<.1?.1:dd; return [cu[0]+m[0]/dd*w,cu[1]+m[1]/dd*w]; };
  for(var j=0;j<n;j++){ var j2=(j+1)%n, L2=Math.hypot(p[j2][0]-p[j][0],p[j2][1]-p[j][1]), out2=[(p[j2][1]-p[j][1])/L2*s,-(p[j2][0]-p[j][0])/L2*s];
    for(var q2=0;q2+1<prof.length;q2++){ var A=prof[q2], B=prof[q2+1], a0=off(j,A[0]), a1=off(j2,A[0]), b0=off(j,B[0]), b1=off(j2,B[0]), dw=B[0]-A[0], dz=B[1]-A[1], l=Math.hypot(dw,dz)||1;
      mb.quad(k,[[a0[0],a0[1],A[1]],[a1[0],a1[1],A[1]],[b1[0],b1[1],B[1]],[b0[0],b0[1],B[1]]],nrm([out2[0]*dz/l,out2[1]*dz/l,-dw/l]),[[0,A[1]+A[0]],[L2,A[1]+A[0]],[L2,B[1]+B[0]],[0,B[1]+B[0]]]); } }
  var bb=bb2(p), rect=n===4&&Math.abs(Math.abs(parea(p))-(bb[2]-bb[0])*(bb[3]-bb[1]))<.01*(bb[2]-bb[0])*(bb[3]-bb[1]), rise=rf.h||(rf.k==='flat'||rf.k==='none'?0:2), ov=.58;
  var eave=[]; for(var e2=0;e2<n;e2++) eave.push(off(e2,ov));
  if(rf.k==='none') return;
  if((rf.k==='hip'||rf.k==='gable'||rf.k==='vault')&&rect){ var x0=bb[0]-ov, y0=bb[1]-ov, x1=bb[2]+ov, y1=bb[3]+ov, lx=x1-x0>=y1-y0, A2=lx?(x1-x0)/2:(y1-y0)/2, B2=lx?(y1-y0)/2:(x1-x0)/2, cx=(x0+x1)/2, cy=(y0+y1)/2, zt=top+rise;
    var W2=function(u,v,z){ return lx?[cx+u,cy+v,z]:[cx+v,cy+u,z]; };
    if(rf.k==='vault'){ for(var v=0;v<16;v++){ var t0=v/16*PI, t1=(v+1)/16*PI; mb.qg('patina',[W2(-A2,Math.cos(t0)*B2,top+Math.sin(t0)*rise),W2(A2,Math.cos(t0)*B2,top+Math.sin(t0)*rise),W2(A2,Math.cos(t1)*B2,top+Math.sin(t1)*rise),W2(-A2,Math.cos(t1)*B2,top+Math.sin(t1)*rise)],[0,0,1],[[0,t0*B2],[2*A2,t0*B2],[2*A2,t1*B2],[0,t1*B2]]); } return; }
    var rl=rf.k==='hip'?A2-B2:A2, rk='rooftile';
    [-1,1].forEach(function(sd){ mb.qg(rk,[W2(-A2,sd*B2,top),W2(A2,sd*B2,top),W2(rl,0,zt),W2(-rl,0,zt)],[0,0,1],[[-A2,0],[A2,0],[rl,Math.hypot(B2,rise)],[-rl,Math.hypot(B2,rise)]]);
      if(rf.k==='hip') mb.qg(rk,[W2(sd*A2,-B2,top),W2(sd*A2,B2,top),W2(sd*rl,0,zt),W2(sd*rl,0,zt+.0001)],[0,0,1],[[-B2,0],[B2,0],[0,Math.hypot(B2,rise)],[0,Math.hypot(B2,rise)]]);
      else mb.qg(k,[W2(sd*A2,-B2,top),W2(sd*A2,B2,top),W2(sd*A2,0,zt),W2(sd*A2,0,zt+.0001)],[lx?sd:0,lx?0:sd,0],[[-B2,top],[B2,top],[0,zt],[0,zt]]); });
    mb.qg(k,[W2(-A2,-B2,top),W2(A2,-B2,top),W2(A2,B2,top),W2(-A2,B2,top)],[0,0,-1],[[0,0],[1,0],[1,1],[0,1]]); return; }
  var tp=(it.tall||[]).map(function(r){ return r.p; });
  flat(mb,'concrete',[eave].concat(tp),top,true); flat(mb,k,[eave].concat(tp),top,false);
  (it.tall||[]).forEach(function(r){ var q=r.p, sq=parea(q)>0?1:-1, zt=r.ceil+.9;            /* a raised roof over a room taller than the building */
    for(var i=0;i<q.length;i++){ var a=q[i], c=q[(i+1)%q.length], L=Math.hypot(c[0]-a[0],c[1]-a[1]); if(L<1e-4) continue;
      mb.quad(k,[[a[0],a[1],top],[c[0],c[1],top],[c[0],c[1],zt],[a[0],a[1],zt]],[(c[1]-a[1])/L*sq,-(c[0]-a[0])/L*sq,0],[[0,top],[L,top],[L,zt],[0,zt]]); }
    flat(mb,'concrete',[q],zt,true); });
  if(rf.k==='dome'){ var c3=interior(p), R=Math.min(bb[2]-bb[0],bb[3]-bb[1])*.38, dz2=rise>0?rise:R; lathe(mb,k,c3[0],c3[1],[[R*1.06,top],[R*1.06,top+R*.35],[R*1.12,top+R*.38],[R*1.12,top+R*.45]],40);
    var pr=[]; for(var i3=0;i3<=12;i3++){ var t=i3/12*PI/2; pr.push([Math.max(.01,Math.cos(t)*R),top+R*.45+Math.sin(t)*dz2]); } lathe(mb,'patina',c3[0],c3[1],pr,48); } };
ITEM.backing=function(G,mb,it){ var p=it.sh.p, n=p.length, s=parea(p)>0?1:-1, k=matName(it.sh.m,'limestone'), z0=it.z0, z1=it.z1; if(k==='limestone'||k==='stone') k='kasota';
  var off=function(i,w){ var pv=p[(i-1+n)%n], cu=p[i], nx=p[(i+1)%n], l0=Math.hypot(cu[0]-pv[0],cu[1]-pv[1])||1, l1=Math.hypot(nx[0]-cu[0],nx[1]-cu[1])||1, n0=[(cu[1]-pv[1])/l0*s,-(cu[0]-pv[0])/l0*s], n1=[(nx[1]-cu[1])/l1*s,-(nx[0]-cu[0])/l1*s], m=[n0[0]+n1[0],n0[1]+n1[1]], dd=Math.max(.1,1+n0[0]*n1[0]+n0[1]*n1[1]); return [cu[0]+m[0]/dd*w,cu[1]+m[1]/dd*w]; };
  for(var i=0;i<n;i++){ var j=(i+1)%n, a=off(i,-.6), c=off(j,-.6), L=Math.hypot(c[0]-a[0],c[1]-a[1]); if(L<.05) continue; var o=[(p[j][1]-p[i][1])/L*s,-(p[j][0]-p[i][0])/L*s,0];
    mb.qg(k,[[a[0],a[1],z0],[c[0],c[1],z0],[c[0],c[1],z1],[a[0],a[1],z1]],o,[[0,z0],[L,z0],[L,z1],[0,z1]]); } };
ITEM.steps=function(G,mb,it){ var s=it.s, ang=(s.up!=null?s.up:90)*PI/180, ux=Math.cos(ang), uy=Math.sin(ang), mn=1e9, mx=-1e9, k='granite';
  s.p.forEach(function(p){ var u=p[0]*ux+p[1]*uy; mn=Math.min(mn,u); mx=Math.max(mx,u); }); var n=s.n||Math.max(1,Math.round(Math.abs(s.z1-s.z0)/.15)), base=Math.min(s.z0,G.gz);
  for(var i=0;i<n;i++){ var u0=mn+(mx-mn)*i/n, z=s.z0+(s.z1-s.z0)*(i+1)/n, band=clipHalf(s.p,ux,uy,u0); if(band.length<3) continue; flat(mb,k,[band],z,true);
    var sg2=parea(band)>0?1:-1; for(var j=0,m=band.length;j<m;j++){ var a=band[j], c=band[(j+1)%m], L=Math.hypot(c[0]-a[0],c[1]-a[1]); if(L<1e-4) continue;
      mb.quad(k,[[a[0],a[1],base],[c[0],c[1],base],[c[0],c[1],z],[a[0],a[1],z]],[(c[1]-a[1])/L*sg2,-(c[0]-a[0])/L*sg2,0],[[0,base],[L,base],[L,z],[0,z]]); } } };
ITEM.terr=function(G,mb,it){ var t=it.tr, k=!t.m||t.m==='granite'||t.m==='stone'?'flags':matName(t.m,'granite'), z=Math.max(t.z,G.gz+.012); flat(mb,k,[t.p],z,true);
  if(z>G.gz+.05){ var s=parea(t.p)>0?1:-1; for(var j=0,m=t.p.length;j<m;j++){ var a=t.p[j], c=t.p[(j+1)%m], L=Math.hypot(c[0]-a[0],c[1]-a[1]); mb.quad(k,[[a[0],a[1],G.gz],[c[0],c[1],G.gz],[c[0],c[1],z],[a[0],a[1],z]],[(c[1]-a[1])/L*s,-(c[0]-a[0])/L*s,0],[[0,0],[L,0],[L,z-G.gz],[0,z-G.gz]]); } } };
ITEM.ground=function(G,mb,it){ var c=it.c, R=it.R, z=G.gz-.004; mb.quad('paving',[[c[0]-R,c[1]-R,z],[c[0]+R,c[1]-R,z],[c[0]+R,c[1]+R,z],[c[0]-R,c[1]+R,z]],[0,0,1],[[c[0]-R,c[1]-R],[c[0]+R,c[1]-R],[c[0]+R,c[1]+R],[c[0]-R,c[1]+R]]); };

/* ── lights per room (uniform arrays) ── */
function roomLight(G,r,b){ var T=S.T, L={kind:0, spots:[], wins:[], edges:[], blobs:[]}, e=r.l.e, lx=r.lx, k=r.lk;
  var base={sky:.2, day:.34, art:.16, mixed:.26, dim:.1}[k]||.25, f=Math.pow(lx/250,.35); L.amb=base*f;
  var warm=[1,.84,.66], cool=[.86,.92,1], neutral=[1,.95,.87], lc=k==='sky'||k==='day'?neutral:warm;
  var fa=floorAlbedo(r.fm), wa=r.wt;
  var area=Math.max(4,Math.abs(parea(r.p)));
  /* art spots from the ceiling, aimed at every wall slot; wall washers when a gallery has few */
  var slots=r.items.filter(function(x){ return x.t==='slot'; });
  slots.forEach(function(it){ if(L.spots.length>=T.NS) return; var s=it.s, c=[s.p[0]+it.n[0]*.02,s.p[1]+it.n[1]*.02,it.z], ch=r.ceil-.32;
    var off=it.sculpt?1.6:clamp((ch-it.z)*.62,1.0,2.8), p=it.sculpt?[s.p[0]+it.n[0]*off,s.p[1]+it.n[1]*off,ch]:[c[0]+it.n[0]*off,c[1]+it.n[1]*off,ch];
    var tz=it.sculpt?e+(s.sz[1]<1.2?1.0:.45)+s.sz[1]*.5:c[2], tgt=[c[0],c[1],tz], dv=nrm(sub(tgt,p)), dist=Math.hypot(tgt[0]-p[0],tgt[1]-p[1],tgt[2]-p[2]);
    var rad=Math.max(s.sz[0],s.sz[1])*.62+.3, outer=Math.atan(rad/dist)*1.25, Et=(k==='sky'?1.6:2.6)*Math.pow(lx/220,.5);
    L.spots.push({p:p, d:dv, co:Math.cos(outer), ci:Math.cos(outer*.55), I:Et*(dist*dist+.04), c:warm}); });
  if((k==='art'||k==='mixed')&&L.spots.length<T.NS){ var faces=b.items.filter(function(x){ return x.t==='face'&&x.room===r&&x.u1-x.u0>2.2&&!x.W.rail; });
    faces.sort(function(a,c){ return (c.u1-c.u0)-(a.u1-a.u0); });
    faces.forEach(function(fc){ var sg=fc.sg, n2=[sg.n[0]*fc.s,sg.n[1]*fc.s], len=fc.u1-fc.u0, cnt=Math.max(1,Math.floor(len/3.6));
      for(var i=0;i<cnt&&L.spots.length<T.NS;i++){ var u=fc.u0+len*(i+.5)/cnt, wx=sg.A[0]+sg.d[0]*u+n2[0]*fc.W.ht, wy=sg.A[1]+sg.d[1]*u+n2[1]*fc.W.ht;
        if(slots.some(function(it){ return Math.hypot(it.s.p[0]-wx,it.s.p[1]-wy)<1.6; })) continue; var ch=r.ceil-.32, off=clamp((ch-e-1.6)*.5,.9,2.2), p=[wx+n2[0]*off,wy+n2[1]*off,ch], tgt=[wx,wy,e+1.5];
        var dv=nrm(sub(tgt,p)), dist=Math.hypot(tgt[0]-p[0],tgt[1]-p[1],tgt[2]-p[2]); L.spots.push({p:p, d:dv, co:Math.cos(.62), ci:Math.cos(.25), I:.75*Math.pow(lx/220,.5)*dist*dist, c:warm, wash:1}); } }); }
  r.wins.slice(0,T.NW).forEach(function(w){ var I=(k==='art'||k==='dim')?-.28:(k==='sky'?.7:1.0); L.wins.push({c:w.c, U:w.U, hw:w.hw, hh:w.hh, n:w.n, I:w.ext?I:I*.3}); });
  if(r.lay){ if(L.wins.length>=T.NW) L.wins.pop(); var bb=bb2(r.lay); L.wins.unshift({c:[(bb[0]+bb[2])/2,(bb[1]+bb[3])/2,r.ceil-.01], U:[1,0,0], hw:(bb[2]-bb[0])/2, hh:(bb[3]-bb[1])/2, n:[0,0,-1], I:-1.25*Math.pow(lx/400,.6)}); L.lay=1.45*Math.pow(lx/400,.6); }
  var light=0; L.spots.forEach(function(s){ light+=s.I/(Math.pow(s.p[2]-e,2)+1)*.012*(s.wash?1:.6); }); L.wins.forEach(function(w){ light+=Math.abs(w.I)*w.hw*w.hh*4*.02*(w.n[2]<0?2.2:1); });
  L.amb+=Math.min(.35,light*30/area);
  L.ambC=[lc[0]*L.amb*(.55+.45*wa[0]),lc[1]*L.amb*(.55+.45*wa[1]),lc[2]*L.amb*(.55+.45*wa[2])];
  L.ambF=[L.amb*.6*(.3+.35*fa[0]+.35*wa[0])*lc[0],L.amb*.6*(.3+.35*fa[1]+.35*wa[1])*lc[1],L.amb*.6*(.3+.35*fa[2]+.35*wa[2])*lc[2]];
  var es=[]; for(var i=0,n=r.p.length;i<n;i++){ var a=r.p[i], c=r.p[(i+1)%n]; es.push([a[0],a[1],c[0],c[1],Math.hypot(c[0]-a[0],c[1]-a[1])]); } es.sort(function(a,c){ return c[4]-a[4]; }); L.edges=es.slice(0,T.NE);
  r.items.forEach(function(x){ if(x.blob&&L.blobs.length<T.NB) L.blobs.push(x); });
  r.items.forEach(function(x){ if(!x.statue) return; var f=x.statue; [[2.6,2.2],[-2.4,1.6],[0,-2.8]].forEach(function(o,i){ if(L.spots.length>=T.NS) return; var p=[f.p[0]+o[0]*1.6,f.p[1]+o[1]*1.6,Math.min(r.ceil-.4,x.z+x.h*1.4+3)], tg=[f.p[0],f.p[1],x.z], dv=nrm(sub(tg,p)), dd=Math.hypot(tg[0]-p[0],tg[1]-p[1],tg[2]-p[2]), a=Math.atan((x.h*.7+.6)/dd);
    L.spots.unshift({p:p, d:dv, co:Math.cos(a), ci:Math.cos(a*.5), I:(i?1.6:3.2)*dd*dd, c:[1,.86,.7]}); }); });
  if(r.ch>7){ L.ambF=L.ambF.map(function(v){ return v*1.7; }); }
  L.room=[e,r.ceil,0,L.lay||0]; L.exp=clamp(.62/Math.max(.1,L.amb*.85+.2),.55,2.6)*(L.lay?.66:1)*(r.ch>7?.72:1); L.fog=[L.ambC[0]*.9,L.ambC[1]*.9,L.ambC[2]*.9,.006];
  return pack(L); }
function floorAlbedo(m){ return {parquet:[.55,.38,.24],plank:[.55,.4,.26],wood:[.45,.3,.18],marble:[.88,.87,.85],terrazzo:[.82,.8,.75],carpet:[.4,.18,.16],concrete:[.6,.6,.58],tile:[.85,.83,.78],granite:[.55,.53,.52],limestone:[.82,.77,.68],stone:[.75,.75,.72]}[m]||[.7,.68,.64]; }
function extLight(G,b){ var L={spots:[], wins:[], edges:[], blobs:[]}; var sky=S.sky; L.ambC=[sky[0]*.62,sky[1]*.62,sky[2]*.62]; L.ambF=[.34,.32,.29];
  var sh=(G.plan.ex&&G.plan.ex.sh)||[]; if(b.kind==='site'&&sh[0]){ var p=sh[0].p; for(var i=0;i<p.length&&L.edges.length<S.T.NE;i++){ var a=p[i], c=p[(i+1)%p.length]; L.edges.push([a[0],a[1],c[0],c[1]]); } }
  L.room=[G.gz,1e4,1,0]; L.exp=.21; L.fog=[sky[0]*.8,sky[1]*.85,sky[2]*.95,.0016]; return pack(L); }
function pack(L){ var T=S.T, o={exp:L.exp, fog:L.fog, room:L.room, ambC:L.ambC, ambF:L.ambF, ns:L.spots.length, nw:L.wins.length, ne:L.edges.length, nb:L.blobs.length, spots:L.spots, lay:L.lay||0};
  o.spP=new Float32Array(T.NS*4); o.spD=new Float32Array(T.NS*4); o.spC=new Float32Array(T.NS*4);
  L.spots.forEach(function(s,i){ o.spP.set([s.p[0],s.p[1],s.p[2],s.I],i*4); o.spD.set([s.d[0],s.d[1],s.d[2],s.co],i*4); o.spC.set([s.c[0],s.c[1],s.c[2],s.ci],i*4); });
  o.wC=new Float32Array(T.NW*4); o.wU=new Float32Array(T.NW*4); o.wN=new Float32Array(T.NW*4);
  L.wins.forEach(function(w,i){ o.wC.set([w.c[0],w.c[1],w.c[2],w.hw],i*4); o.wU.set([w.U[0],w.U[1],w.U[2],w.hh],i*4); o.wN.set([w.n[0],w.n[1],w.n[2],w.I],i*4); });
  o.ed=new Float32Array(T.NE*4); L.edges.forEach(function(e,i){ o.ed.set([e[0],e[1],e[2],e[3]],i*4); });
  o.bl=new Float32Array(T.NB*4); o.br=new Float32Array(T.NB*4); L.blobs.forEach(function(x,i){ o.bl.set(x.blob,i*4); o.br.set([Math.cos(x.rot),Math.sin(x.rot),x.str,x.round?1:0],i*4); });
  return o; }

/* ── materials: key -> {gen, tint, tile, rough, metal, bump, kind} ── */
function matOf(G,key){ var C=S.mc[key]; if(C) return C; var k=key, i=k.indexOf('#'), base=i>=0?k.slice(0,i):k, arg=i>=0?k.slice(i+1):'', m=null;
  if(base==='paint'){ var r=G.rooms[+arg]; var t=arg==='plinth'?[.95,.94,.92]:r?r.paint:[.9,.88,.84]; m={gen:5,tint:t,tile:2,rough:1,metal:0,bump:.05,kind:0}; }
  else if(base==='trim'){ var r2=G.rooms[+arg], c=r2?r2.wt:[.9,.88,.84], t2=[c[0]+(1-c[0])*.55,c[1]+(1-c[1])*.55,c[2]+(1-c[2])*.55]; if(c[0]+c[1]+c[2]<1.6) t2=[c[0]*.82,c[1]*.82,c[2]*.82];
    m=r2&&/^(wood|oak|pine)$/.test(r2.wm)?{gen:6,tint:MAT[r2.wm][1].map(function(v){ return v*.8; }),tile:1.2,rough:1,metal:0,bump:.3,kind:0}:r2&&r2.wm==='boiserie'?{gen:13,tint:[.86,.66,.3],tile:1,rough:.6,metal:1,bump:.1,kind:0}:{gen:5,tint:t2,tile:2,rough:.8,metal:0,bump:.05,kind:0}; }
  else if(base==='skirt'){ var r3=G.rooms[+arg], c3=r3?r3.wt:[.5,.5,.5]; m={gen:5,tint:[c3[0]*.5,c3[1]*.5,c3[2]*.5],tile:2,rough:.7,metal:0,bump:.05,kind:0}; }
  else if(base==='frame'){ m={gen:6,tint:[.32,.24,.18],tile:1.2,rough:.9,metal:0,bump:.3,kind:0}; }
  else if(base==='mat'){ m={kind:3,tint:[.93,.91,.86],rough:.95,metal:0}; }
  else if(base==='lab'){ m={kind:2,lab:1,rough:.9}; }
  else if(base==='art'){ m={kind:2,art:+arg,rough:.6}; }
  else if(base==='glass'){ m={kind:4,tint:[.92,.96,.95],rough:.05,a:.05,trans:1}; }
  else if(base==='glaze'){ m={kind:4,tint:[1,1,1],rough:.05,a:.0,trans:1}; }
  else if(base==='water'){ m={kind:4,tint:[.5,.62,.62],rough:.05,a:.55,trans:1}; }
  else if(base==='shadow'){ m={kind:5,a:.42,trans:1}; }
  else if(base==='lens'){ m={kind:6,tint:[1,.86,.66],e:9}; }
  else if(base==='lay'){ m={kind:1,tint:[1,.98,.94]}; }
  else if(base==='av'){ m={kind:3,tint:AV.hex(arg),rough:.72,metal:0}; }
  else if(base==='avshadow'){ m={kind:5,a:.5,trans:1}; }
  else if(base==='navglow'){ m={kind:6,tint:[1,.42,.08],e:1.5}; }          /* a deep orange: it reads on white marble as well as on parquet */
  else if(base.slice(0,4)==='book'){ var bc=[[.42,.12,.1],[.12,.2,.3],[.2,.28,.16],[.5,.4,.22],[.3,.16,.2],[.62,.55,.42]][+base.slice(4)||0]; m={kind:3,tint:bc,rough:.7,metal:0}; }
  else if(base==='plaster'&&arg){ m=null; }
  if(!m){ var d=MAT[base]||MAT.plaster; if(d[0]<0) d=MAT.plaster; m={gen:d[0],tint:d[1],tile:d[2],rough:d[3],metal:d[4],bump:d[5],kind:0};
    if(d[0]===0||d[0]===19) m.j=[arg==='f'?(d[0]===19?1.2:.9):(d[0]===19?1.5:1.2),.004,.1,0]; if(arg==='f'&&/^(marble|terrazzo|granite|kasota|tile)$/.test(base)) m.j=[m.j?m.j[0]:0,m.j?m.j[1]:0,m.j?m.j[2]:0,.5]; }
  if(m.kind===0&&!m.v) m.v=VAR[m.gen]||[.06,0,.1];
  if(m.kind===0&&(arg==='f'||base==='board'||base==='parquet')) m.pol=arg==='f'?.85:.28;
  if(m.tint&&!m.metal&&m.kind!==4) m.tint=m.tint.map(function(v){ return Math.pow(v,2.2); });   /* tints are sRGB; the shader works in linear light */
  S.mc[key]=m; return m; }

/* ── GL: context, programs, procedural textures ── */
function pickTier(o){ var f=o.force; if(f==='high'||f==='medium'||f==='low') return (f!=='low'&&!o.msaa)?'low':f;
  if(!o.wgl2||!o.msaa) return 'low'; var r=String(o.renderer||'').toLowerCase(); if(/swiftshader|llvmpipe|softpipe|software|microsoft basic/.test(r)) return 'low';
  if(o.mobile||o.ios||(o.mem&&o.mem<8)||(o.cores&&o.cores<6)||/mali|adreno|powervr|intel\(r\) hd graphics [2-5]/.test(r)||(o.samples||0)<4) return 'medium'; return 'high'; }
var TIERS={high:{NS:12,NW:6,NE:24,NB:12,tex:1024,samples:4,atlas:1024,scaleHi:2}, medium:{NS:8,NW:4,NE:16,NB:8,tex:512,samples:2,atlas:512,scaleHi:1.5}, low:{NS:4,NW:2,NE:8,NB:4,tex:512,samples:0,atlas:512,scaleHi:1}};
/* the graphics pass (fpv_gfx.py) per tier: soft shadows (2 = blocker-sized penumbra, 1 = fixed disc), SSAO taps at half size, bloom, the HDRI sky
   (its size; SH irradiance needs nothing loaded), the real material sets (albedo size; normals are 512). A phone's medium drops the SSAO.
   ?bldgfx=0 turns the whole pass off (the look before it: before/after strips) */
var FX={high:{soft:2, ao:12, bloom:1, ibl:1, env:'2048', real:'a1024'}, medium:{soft:1, ao:6, bloom:1, ibl:1, env:'1024', real:'a512'}, low:{soft:0, ao:0, bloom:0, ibl:1, env:'', real:''}, off:{soft:0, ao:0, bloom:0, ibl:0, env:'', real:''}};
function fxFor(name,o){ var f={}, b=FX[q().bldgfx==='0'?'off':name]; for(var k in b) f[k]=b[k]; if(name==='medium'&&o&&(o.mobile||o.ios)) f.ao=0;
  String(q().bldgfxoff||'').split(',').forEach(function(k){ if(k in f) f[k]=typeof f[k]==='string'?'':0; }); return f; }      /* ?bldgfxoff=soft,ao,...: QA, one feature at a time */
function glInit(cv){ var Q=q(), N=navigator, ua=String(N.userAgent||''), o={force:Q.bldgtier||'', wgl2:false, msaa:false, samples:0, renderer:'', mobile:matchMedia&&matchMedia('(pointer:coarse)').matches,
    ios:/iPhone|iPad|iPod/.test(ua)||(/Macintosh/.test(ua)&&(N.maxTouchPoints|0)>1), mem:+N.deviceMemory||0, cores:N.hardwareConcurrency|0}, gl=null;
  if(Q.bldggl!=='1'){ try{ gl=cv.getContext('webgl2',{alpha:false, antialias:false, depth:true, stencil:false, powerPreference:'high-performance', preserveDrawingBuffer:false}); }catch(x){ gl=null; } }
  if(gl){ o.wgl2=true; var dbg=gl.getExtension('WEBGL_debug_renderer_info'); o.renderer=dbg?String(gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL)):''; o.samples=Math.min(4,gl.getParameter(gl.MAX_SAMPLES)|0);
    if(o.samples>=2){ var t=target(gl,8,8,o.samples,null); if(t){ o.msaa=true; freeTarget(gl,t); } } }
  var tier=pickTier(o);
  if(tier==='low'&&gl&&!o.msaa){ gl=null; }
  if(!gl){ try{ gl=cv.getContext('webgl',{alpha:false, antialias:true, depth:true, stencil:false, powerPreference:'high-performance'})||cv.getContext('experimental-webgl',{alpha:false, antialias:true}); }catch(x){ gl=null; } o.wgl2=false; tier='low'; }
  if(!gl) return null;
  var T={}; for(var k in TIERS[tier]) T[k]=TIERS[tier][k]; T.name=tier; T.wgl2=o.wgl2; T.probe=o; T.fx=fxFor(tier,o); if(!o.wgl2){ T.fx.env=''; T.fx.real=''; T.fx.soft=0; T.fx.ao=0; T.fx.bloom=0; }
  var need=T.NS*3+T.NW*3+T.NE+T.NB*2+24; if((gl.getParameter(gl.MAX_FRAGMENT_UNIFORM_VECTORS)|0)<need){ T.NS=4; T.NW=2; T.NE=8; T.NB=4; }
  T.deriv=o.wgl2||!!gl.getExtension('OES_standard_derivatives'); T.aniso=gl.getExtension('EXT_texture_filter_anisotropic')||gl.getExtension('WEBKIT_EXT_texture_filter_anisotropic');
  T.vao=null; S.T=T; S.gl=gl; return gl; }
function target(gl,w,h,samples,old){ if(old) freeTarget(gl,old); var fb=gl.createFramebuffer(), rc=gl.createRenderbuffer(), rd=gl.createRenderbuffer();
  gl.bindRenderbuffer(gl.RENDERBUFFER,rc); gl.renderbufferStorageMultisample(gl.RENDERBUFFER,samples,gl.RGBA8,w,h); gl.bindRenderbuffer(gl.RENDERBUFFER,rd); gl.renderbufferStorageMultisample(gl.RENDERBUFFER,samples,gl.DEPTH_COMPONENT24,w,h);
  gl.bindFramebuffer(gl.FRAMEBUFFER,fb); gl.framebufferRenderbuffer(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.RENDERBUFFER,rc); gl.framebufferRenderbuffer(gl.FRAMEBUFFER,gl.DEPTH_ATTACHMENT,gl.RENDERBUFFER,rd);
  var ok=gl.checkFramebufferStatus(gl.FRAMEBUFFER)===gl.FRAMEBUFFER_COMPLETE, t={fb:fb,rc:rc,rd:rd,w:w,h:h,s:samples,rfb:null,rt:null};
  if(ok){ var rfb=gl.createFramebuffer(), rt=gl.createRenderbuffer(); gl.bindRenderbuffer(gl.RENDERBUFFER,rt); gl.renderbufferStorage(gl.RENDERBUFFER,gl.RGBA8,w,h); gl.bindFramebuffer(gl.FRAMEBUFFER,rfb);
    gl.framebufferRenderbuffer(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.RENDERBUFFER,rt); ok=gl.checkFramebufferStatus(gl.FRAMEBUFFER)===gl.FRAMEBUFFER_COMPLETE; t.rfb=rfb; t.rt=rt; }
  gl.bindFramebuffer(gl.FRAMEBUFFER,null); gl.bindRenderbuffer(gl.RENDERBUFFER,null); if(!ok){ freeTarget(gl,t); return null; } return t; }
function freeTarget(gl,t){ if(!t) return; try{ gl.deleteFramebuffer(t.fb); gl.deleteRenderbuffer(t.rc); gl.deleteRenderbuffer(t.rd); if(t.rfb){ gl.deleteFramebuffer(t.rfb); gl.deleteRenderbuffer(t.rt); } }catch(x){} }
function hdr(gl,frag){ var T=S.T, F=T.fx||{}, d='#define NS '+T.NS+'\n#define NW '+T.NW+'\n#define NE '+T.NE+'\n#define NB '+T.NB+'\n'+(T.deriv?'#define DERIV 1\n':'')+(T.name==='high'&&!(F.real&&T.wgl2)?'#define SHAFTS 1\n':'')      /* the light shafts' loop and the pass do not fit one shader in WebKit's Metal compiler (it crashes: the context is lost); bloom carries the windows' glow */
    +(F.soft&&T.wgl2?'#define SOFTSH '+F.soft+'\n':'')+(F.ibl&&FXG.env?'#define IBL 1\n':'')+(F.ibl&&F.env&&T.wgl2&&FXG.env?'#define ENV 1\n#define ENV_LOD 1\n':'')+(F.real&&T.wgl2?'#define REALTEX 1\n':'');
  if(T.wgl2) return '#version 300 es\n'+d+(frag?'precision highp float;\n#define VARY_F in\n#define TEX texture\n#define TEXB texture\nout vec4 oC;\n#define FRAG oC\n':'#define ATTR in\n#define VARY_V out\n');
  return (frag&&T.deriv?'#extension GL_OES_standard_derivatives : enable\n':'')+d+(frag?'#define VARY_F varying\n#define TEX texture2D\n#define TEXB texture2D\n#define FRAG gl_FragColor\n':'#define ATTR attribute\n#define VARY_V varying\n'); }
function prog(gl,vs,fs,attrs){ var sh=function(t,src){ var s=gl.createShader(t); gl.shaderSource(s,src); gl.compileShader(s); if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)) throw new Error('shader: '+gl.getShaderInfoLog(s)); return s; };
  var p=gl.createProgram(); gl.attachShader(p,sh(gl.VERTEX_SHADER,hdr(gl,false)+vs)); gl.attachShader(p,sh(gl.FRAGMENT_SHADER,hdr(gl,true)+fs)); attrs.forEach(function(a,i){ gl.bindAttribLocation(p,i,a); }); gl.linkProgram(p);
  if(!gl.getProgramParameter(p,gl.LINK_STATUS)) throw new Error('link: '+gl.getProgramInfoLog(p)); var u={}, n=gl.getProgramParameter(p,gl.ACTIVE_UNIFORMS);
  for(var i=0;i<n;i++){ var inf=gl.getActiveUniform(p,i), nm=inf.name.replace(/\[0\]$/,''); u[nm]=gl.getUniformLocation(p,inf.name); } return {p:p,u:u}; }
function smInit(){ var gl=S.gl, T=S.T; S.sm=null; if(T.name==='low'||q().bldgshadow==='0') return;
  try{ var N=T.name==='high'?2048:1024, tx=gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D,tx); gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,N,N,0,gl.RGBA,gl.UNSIGNED_BYTE,null);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.NEAREST); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.NEAREST); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
    var rb=gl.createRenderbuffer(); gl.bindRenderbuffer(gl.RENDERBUFFER,rb); gl.renderbufferStorage(gl.RENDERBUFFER,gl.DEPTH_COMPONENT16,N,N);
    var fb=gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER,fb); gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_2D,tx,0); gl.framebufferRenderbuffer(gl.FRAMEBUFFER,gl.DEPTH_ATTACHMENT,gl.RENDERBUFFER,rb);
    var ok=gl.checkFramebufferStatus(gl.FRAMEBUFFER)===gl.FRAMEBUFFER_COMPLETE; gl.bindFramebuffer(gl.FRAMEBUFFER,null); gl.bindRenderbuffer(gl.RENDERBUFFER,null);
    if(!ok){ gl.deleteTexture(tx); gl.deleteRenderbuffer(rb); gl.deleteFramebuffer(fb); return; }
    S.pd=prog(gl,DVS,DFS,['aP','aN','aT','aX']); S.sm={tx:tx, rb:rb, fb:fb, N:N, R:T.name==='high'?42:34, c:null, dirty:1, lvp:new Float32Array(16)}; S.texBytes+=N*N*6; }catch(e){ S.sm=null; } }
/* the polished floor's mirror image: the visible rooms drawn once more through a reflection about the floor plane, half size, mip-mapped for rough blur */
function rtTarget(gl,w,h){ var o=S.rt; if(o&&o.w===w&&o.h===h) return o; if(o){ gl.deleteTexture(o.tx); gl.deleteRenderbuffer(o.rb); gl.deleteFramebuffer(o.fb); S.texBytes-=o.bytes; }
  var tx=gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D,tx); gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,w,h,0,gl.RGBA,gl.UNSIGNED_BYTE,null); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR_MIPMAP_LINEAR); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE); gl.generateMipmap(gl.TEXTURE_2D);
  var rb=gl.createRenderbuffer(); gl.bindRenderbuffer(gl.RENDERBUFFER,rb); gl.renderbufferStorage(gl.RENDERBUFFER,gl.DEPTH_COMPONENT16,w,h);
  var fb=gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER,fb); gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_2D,tx,0); gl.framebufferRenderbuffer(gl.FRAMEBUFFER,gl.DEPTH_ATTACHMENT,gl.RENDERBUFFER,rb);
  var ok=gl.checkFramebufferStatus(gl.FRAMEBUFFER)===gl.FRAMEBUFFER_COMPLETE; gl.bindFramebuffer(gl.FRAMEBUFFER,null); gl.bindRenderbuffer(gl.RENDERBUFFER,null);
  if(!ok){ gl.deleteTexture(tx); gl.deleteRenderbuffer(rb); gl.deleteFramebuffer(fb); S.rt=null; S.noRefl=1; return null; }
  S.rt={tx:tx, rb:rb, fb:fb, w:w, h:h, bytes:w*h*6}; S.texBytes+=S.rt.bytes; return S.rt; }
function polish(r){ if(!r||r.isVoid) return 0; return /#f$/.test(floorKey(r.fm,r))?1:0; }        /* the mirror pass runs for polished stone floors only (halls, lobbies); wood keeps its cheap sheen */
function reflPass(G,vis,VP,eye,h){ var gl=S.gl, rt=rtTarget(gl,Math.max(16,S.cw>>1),Math.max(16,S.ch>>1)); if(!rt) return false;
  var Rm=[1,0,0,0, 0,1,0,0, 0,0,-1,0, 0,0,2*h,1], VPr=mmul(VP,Rm), PL=planes(VPr), u=S.pw.u, st={draws:0,tris:0};
  gl.activeTexture(gl.TEXTURE3); gl.bindTexture(gl.TEXTURE_2D,S.white); gl.activeTexture(gl.TEXTURE0); gl.bindFramebuffer(gl.FRAMEBUFFER,rt.fb); gl.viewport(0,0,rt.w,rt.h); var a=S.room&&S.room.b.light?S.room.b.light.ambC:[.2,.2,.2]; gl.clearColor(Math.min(1,a[0]*.5),Math.min(1,a[1]*.5),Math.min(1,a[2]*.5),1); gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
  gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL); gl.depthMask(true); gl.enable(gl.CULL_FACE); gl.cullFace(gl.FRONT); gl.disable(gl.BLEND);
  gl.useProgram(S.pw.p); gl.uniformMatrix4fv(u.uVP,false,VPr); gl.uniform3fv(u.uEye,[eye[0],eye[1],2*h-eye[2]]); gl.uniform4fv(u.uClip,[1,h,0,0]); gl.uniform4fv(u.uRefl,[0,0,0,0]);
  vis.forEach(function(b){ if(b.built&&b.kind!=='site'&&b.kind!=='back'&&b.bb[5]>h+.1&&bdist(b,eye)<30&&boxIn(PL,b.bb)) drawBatch(b,false,st); });
  gl.cullFace(gl.BACK); gl.uniform4fv(u.uClip,[0,0,0,0]); gl.bindTexture(gl.TEXTURE_2D,rt.tx); gl.generateMipmap(gl.TEXTURE_2D); S.reflDraws=st.draws; return true; }
function ortho(l,r,b,t,n,f){ return [2/(r-l),0,0,0, 0,2/(t-b),0,0, 0,0,-2/(f-n),0, -(r+l)/(r-l),-(t+b)/(t-b),-(f+n)/(f-n),1]; }
/* the sun's depth (packed into RGBA8: the same path on WebGL1, WebGL2 and Safari) over a box round the walker, re-drawn only when the walker has moved on or new rooms came in */
function smRender(G,eye){ var sm=S.sm, gl=S.gl; if(!sm) return; if(!sm.dirty&&sm.c&&Math.hypot(eye[0]-sm.c[0],eye[1]-sm.c[1])<sm.R*.3&&Math.abs(eye[2]-sm.c[2])<4) return;
  var L=S.sun, up=Math.abs(L[2])>.97?[1,0,0]:[0,0,1], xl=nrm(cross(up,L)), yl=cross(L,xl), t=2*sm.R/sm.N, D=160;
  var cx=Math.round(dot(eye,xl)/t)*t, cy=Math.round(dot(eye,yl)/t)*t, cz=dot(eye,L), c=[xl[0]*cx+yl[0]*cy+L[0]*cz,xl[1]*cx+yl[1]*cy+L[1]*cz,xl[2]*cx+yl[2]*cy+L[2]*cz];
  var V=lookAt([c[0]+L[0]*D,c[1]+L[1]*D,c[2]+L[2]*D],c,up), M=mmul(ortho(-sm.R,sm.R,-sm.R,sm.R,1,D+120),V); sm.lvp=M; sm.c=eye.slice(); sm.dirty=0;
  gl.bindFramebuffer(gl.FRAMEBUFFER,sm.fb); gl.viewport(0,0,sm.N,sm.N); gl.clearColor(1,1,1,1); gl.depthMask(true); gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
  gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL); gl.disable(gl.CULL_FACE); gl.disable(gl.BLEND); gl.useProgram(S.pd.p); gl.uniformMatrix4fv(S.pd.u.uLVP,false,M);
  G.batches.forEach(function(b){ if(!b.built) return; var a=b.bb, lo=[1e9,1e9], hi=[-1e9,-1e9];
    for(var i=0;i<8;i++){ var pt=[i&1?a[3]:a[0],i&2?a[4]:a[1],i&4?a[5]:a[2]], u=dot(pt,xl)-cx, v=dot(pt,yl)-cy; lo[0]=Math.min(lo[0],u); lo[1]=Math.min(lo[1],v); hi[0]=Math.max(hi[0],u); hi[1]=Math.max(hi[1],v); }
    if(hi[0]<-sm.R||lo[0]>sm.R||hi[1]<-sm.R||lo[1]>sm.R) return; var B=b.built; gl.bindBuffer(gl.ARRAY_BUFFER,B.vb); gl.enableVertexAttribArray(0); for(var k=1;k<4;k++) gl.disableVertexAttribArray(k);
    gl.vertexAttribPointer(0,3,gl.FLOAT,false,STRIDE,0); B.ranges.forEach(function(r){ if(!r.trans) gl.drawArrays(gl.TRIANGLES,r.first,r.count); }); });
  gl.bindFramebuffer(gl.FRAMEBUFFER,null); S.smDraws=(S.smDraws||0)+1; }
function glSetup(){ var gl=S.gl; S.pw=prog(gl,WVS,WFS,['aP','aN','aT','aX']); S.ps=prog(gl,QUADVS,SKYFS,['aQ']); S.pt=prog(gl,QUADVS,TEXGEN,['aQ']);
  S.quad=gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER,S.quad); gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);
  S.white=gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D,S.white); gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,1,1,0,gl.RGBA,gl.UNSIGNED_BYTE,new Uint8Array([255,255,255,255]));
  S.flatN=gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D,S.flatN); gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,1,1,0,gl.RGBA,gl.UNSIGNED_BYTE,new Uint8Array([128,128,128,255]));
  S.tex={}; S.mc={}; S.bytes=0; S.texBytes=0; smInit(); fxSetup(); }
/* ── the graphics pass (fpv_gfx.py): the post chain, the HDRI sky, the real material sets ── */
function fxSetup(){ var gl=S.gl, T=S.T, F=T.fx; S.real={}; S.env=null; S.envT0=0; S.post=null;
  if(T.wgl2&&T.samples&&(F.ao||F.bloom)){ S.post=FXG.post(gl); if(S.post){ S.post.o.ao=F.ao; S.post.o.bloom=F.bloom; S.post.o.bloomK=T.name==='high'?.05:.04; S.post.o.th=.9; } }
  if(F.env&&FXG.env&&FXG.env.px[F.env]) FXG.ktx2(gl,FXG.env.px[F.env],{clampT:1},function(t){ if(!t) return; if(S.gl!==gl){ gl.deleteTexture(t.tx); return; } S.env=t; S.envT0=performance.now(); }); }
/* procedural texture set -> the real set that stands in for it, and whether the photograph has its own joints (then our slabs step aside) */
var REAL={0:['marble',0], 19:['kasota',1], 1:['kasota',1,1.6], 8:['parquet',1], 7:['boards',1], 10:['terrazzo',0], 3:['brick',1]};
function realOf(g){ var T=S.T, F=T.fx, r=REAL[g]; if(!r||!F.real||!S.real) return null; var e=S.real[g]; if(e) return e.st===1?e:null;
  var set=FXG.A.tex[r[0]]; if(!set) return null; var gl=S.gl; e=S.real[g]={st:0, tile:set.tile*(r[2]||1), baked:r[1], n:0};
  var done=function(k){ return function(t){ if(!t||S.gl!==gl||!S.real){ if(t) gl.deleteTexture(t.tx); e.st=-1; return; } e[k]=t.tx; e.bytes=(e.bytes||0)+t.bytes; if(++e.n===2&&e.st===0){ e.st=1; e.t0=performance.now(); } }; };
  FXG.ktx2(gl,set[F.real],{aniso:T.aniso, an:T.name==='high'?8:4},done('a')); FXG.ktx2(gl,set.b512,{aniso:T.aniso, an:T.name==='high'?8:4},done('b')); return null; }
/* the governor at its floor and still slow: one tier down (programs rebuilt with the smaller pass; never back up in this visit) */
function fxDown(){ var T=S.T, gl=S.gl; if(!gl||T.name==='low') return; T.name=T.name==='high'?'medium':'low'; T.fx=fxFor(T.name,T.probe); S.down=(S.down||0)+1;
  if(T.name==='low'){ T.fx.env=''; T.fx.real=''; if(S.sm){ gl.deleteTexture(S.sm.tx); gl.deleteRenderbuffer(S.sm.rb); gl.deleteFramebuffer(S.sm.fb); S.sm=null; } }
  try{ S.pw=prog(gl,WVS,WFS,['aP','aN','aT','aX']); S.ps=prog(gl,QUADVS,SKYFS,['aQ']); }catch(e){ if(window.console) console.warn('bldg fpv tier',e); }
  if(S.post){ S.post.o.ao=T.fx.ao; S.post.o.bloom=T.fx.bloom; if(!T.fx.ao&&!T.fx.bloom){ S.post.free(); S.post=null; } }
  if(S.gov){ S.gov.buf.length=0; S.gov.good=performance.now(); } }
function genTex(g){ if(S.tex[g]) return S.tex[g]; var gl=S.gl, N=S.T.tex>512&&[0,7,8,10].indexOf(g)<0?512:S.T.tex, out=[];
  for(var o=0;o<2;o++){ var tx=gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D,tx); gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,N,N,0,gl.RGBA,gl.UNSIGNED_BYTE,null);
    var fb=gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER,fb); gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_2D,tx,0);
    gl.viewport(0,0,N,N); gl.disable(gl.DEPTH_TEST); gl.disable(gl.BLEND); gl.useProgram(S.pt.p); gl.uniform1f(S.pt.u.uG,g); gl.uniform1f(S.pt.u.uO,o); gl.uniform1f(S.pt.u.uSeed,g*1.37+.5); gl.uniform1f(S.pt.u.uPx,1/N);
    gl.bindBuffer(gl.ARRAY_BUFFER,S.quad); gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0,2,gl.FLOAT,false,8,0); for(var a=1;a<4;a++) gl.disableVertexAttribArray(a); gl.drawArrays(gl.TRIANGLES,0,6);
    gl.bindFramebuffer(gl.FRAMEBUFFER,null); gl.deleteFramebuffer(fb); gl.bindTexture(gl.TEXTURE_2D,tx); gl.generateMipmap(gl.TEXTURE_2D);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.REPEAT); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.REPEAT); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR_MIPMAP_LINEAR);
    if(S.T.aniso) gl.texParameterf(gl.TEXTURE_2D,S.T.aniso.TEXTURE_MAX_ANISOTROPY_EXT,S.T.name==='high'?8:4); out.push(tx); S.texBytes+=N*N*4*1.34; }
  S.tex[g]=out; return out; }

/* ── art: per-room atlas (paintings 4x3 above, labels 4x2 below) and public-domain images ── */
function artAtlas(G,b){ var A=S.T.atlas, cv=D.createElement('canvas'); cv.width=A; cv.height=A; var g=cv.getContext('2d'); if(!g) return null; var C=A/4;
  g.fillStyle='#3a3530'; g.fillRect(0,0,A,A);
  b.art.forEach(function(x,i){ if(i>=12) return; var it=x.it, s=it.s, cx=(i%4)*C, cy=Math.floor(i/4)*C, W=s.sz[0], H=s.sz[1], asp=W/H; if(s.card) cardPaint(g,cx,cy,C,asp,it); else paintPH(g,cx,cy,C,asp,hash(s.id),x.paper,x.cloth,s.work,x.text); });
  b.lab.forEach(function(it,i){ var cx=(i%4)*C, cy=A*.75+Math.floor(i/4)*A*.125; label(g,cx,cy,C,A*.125,it); });
  var gl=S.gl, tx=gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D,tx); gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true); gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,cv); gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,false);
  gl.generateMipmap(gl.TEXTURE_2D); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR_MIPMAP_LINEAR); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
  if(S.T.aniso) gl.texParameterf(gl.TEXTURE_2D,S.T.aniso.TEXTURE_MAX_ANISOTROPY_EXT,4); b.texBytes=A*A*4*1.34; return tx; }
/* a work with no hosted public-domain image is never faked: a quiet linen panel (paper: a blank mat) with its title, maker and "image not shown";
   a tapestry is plain woven ground inside a border, no invented figures */
function paintPH(g,x,y,C,asp,seed,paper,cloth,work,text){ var R=rng(seed), VW=C*asp, VH=C, w=work||{}, F='Georgia,"Times New Roman",serif', t=String(w.t||w.title||''), a=[w.a||w.artist,w.d||w.date].filter(Boolean).join(', ');
  g.save(); g.beginPath(); g.rect(x,y,C,C); g.clip(); g.translate(x,y); g.scale(1/asp,1);
  if(cloth){ g.fillStyle='#6d6250'; g.fillRect(0,0,VW,VH); var bw=Math.min(VW,VH)*.07; g.fillStyle='#837560'; g.fillRect(bw,bw,VW-2*bw,VH-2*bw);
    for(var j=0;j<VH;j+=2){ g.fillStyle='rgba(0,0,0,'+(.03+R()*.05)+')'; g.fillRect(0,j,VW,1); } for(var i=0;i<VW;i+=3){ g.fillStyle='rgba(255,240,210,'+(R()*.03)+')'; g.fillRect(i,0,1,VH); }
    g.strokeStyle='rgba(205,180,120,.55)'; g.lineWidth=bw*.08; g.strokeRect(bw*.5,bw*.5,VW-bw,VH-bw); g.strokeRect(bw,bw,VW-2*bw,VH-2*bw); }
  else if(text){ g.fillStyle='#2b2724'; g.fillRect(0,0,VW,VH); g.strokeStyle='rgba(214,190,130,.7)'; g.lineWidth=Math.min(VW,VH)*.03; g.strokeRect(VW*.04,VH*.06,VW*.92,VH*.88); paper=false; a=''; }
  else { g.fillStyle=paper?'#efe9dc':'#4b4740'; g.fillRect(0,0,VW,VH); if(!paper){ for(var k=0;k<VH;k+=2){ g.fillStyle='rgba(255,255,255,'+(R()*.025)+')'; g.fillRect(0,k,VW,1); } }
    var gr=g.createRadialGradient(VW/2,VH/2,Math.min(VW,VH)*.2,VW/2,VH/2,Math.max(VW,VH)*.8); gr.addColorStop(0,'rgba(0,0,0,0)'); gr.addColorStop(1,'rgba(0,0,0,.18)'); g.fillStyle=gr; g.fillRect(0,0,VW,VH); }
  var ink=paper?'rgba(60,54,46,.85)':'rgba(236,228,212,.82)', fs=Math.max(7,Math.min(VW*.075,VH*.07)), lines=[], cur=''; g.textAlign='center'; g.fillStyle=ink; g.font='italic '+Math.round(fs)+'px '+F;
  t.split(/\s+/).forEach(function(wd){ var tt=cur?cur+' '+wd:wd; if(g.measureText(tt).width>VW*.78&&cur){ lines.push(cur); cur=wd; } else cur=tt; }); if(cur) lines.push(cur); if(lines.length>3){ lines=lines.slice(0,3); lines[2]+='…'; }
  var y0=VH*.5-(lines.length-1)*fs*.62-(a?fs*.5:0); lines.forEach(function(l,i){ g.fillText(l,VW/2,y0+i*fs*1.24); });
  g.font=Math.round(fs*.72)+'px '+F; if(a) g.fillText(a,VW/2,y0+lines.length*fs*1.24+fs*.15); g.font=Math.round(fs*.6)+'px -apple-system,Helvetica,Arial,sans-serif'; g.fillStyle=paper?'rgba(60,54,46,.55)':'rgba(236,228,212,.5)'; if(!text) g.fillText('IMAGE NOT SHOWN',VW/2,VH*.9);
  g.restore(); }
function wkOf(s){ var w=s.work||{}; return {t:w.t||w.title, a:w.a||w.artist, d:w.d||w.date, lic:w.lic, img:w.img}; }
function label(g,x,y,w,h,it){ var s=it.s, d=S.data||{}, nid=nodeForAnchor(s.id), n=nid&&d.nodes?d.nodes[nid]:null, wk=wkOf(s);
  g.save(); g.beginPath(); g.rect(x,y,w,h); g.clip(); g.fillStyle='#f3efe6'; g.fillRect(x,y,w,h);
  if(n&&d.acts&&d.acts[n.a]&&d.acts[n.a].c){ g.fillStyle=d.acts[n.a].c; g.fillRect(x,y,w*.035,h); }
  var F='-apple-system,"Segoe UI",Helvetica,Arial,sans-serif', fit=function(t,px){ t=String(t||''); while(t.length>1&&g.measureText(t).width>w*.86) t=t.slice(0,-2)+'…'; return t; };
  g.fillStyle='#1d1b18'; g.font='600 '+Math.round(h*.2)+'px '+F; var t1=n?(n.n+'  '+dec(n.t)):(wk.t||it.room.name); g.fillText(fit(t1),x+w*.07,y+h*.32);
  g.fillStyle='#4a463f'; g.font=Math.round(h*.15)+'px '+F; var t2=n?(wk.t||''):[wk.a,wk.d].filter(Boolean).join(', '); if(!t2) t2=it.room.no?('Gallery '+it.room.no):it.room.name; g.fillText(fit(t2),x+w*.07,y+h*.58);
  g.fillStyle='#7a756c'; g.font=Math.round(h*.13)+'px '+F; g.fillText(fit(n?'Press E to open':(wk.lic?wk.lic:'')),x+w*.07,y+h*.82); g.restore(); }
function dec(s){ if(!D) return s==null?'':String(s); var t=D.createElement('textarea'); t.innerHTML=s==null?'':String(s); return t.value; }
var ART_URL=/^\/bart\/[a-z0-9][a-z0-9-]{0,80}\.(jpg|jpeg|png|webp)$/;
function loadImages(b){ b.art.forEach(function(x){ var wk=x.it.s.work; if(!wk||!wk.img||!ART_URL.test(String(wk.img))) return;          /* only the site's own vetted public-domain images */
    var img=new Image(); img.crossOrigin='anonymous'; img.onload=function(){ if(!S.on||!b.built) return; var gl=S.gl, M=S.T.name==='high'?1024:512, sc=Math.min(1,M/Math.max(img.width,img.height)), cv=D.createElement('canvas');
      cv.width=Math.max(1,Math.round(img.width*sc)); cv.height=Math.max(1,Math.round(img.height*sc)); var g=cv.getContext('2d'); g.drawImage(img,0,0,cv.width,cv.height);
      var tx=gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D,tx); gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true); try{ gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,cv); }catch(e){ gl.deleteTexture(tx); gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,false); return; }
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,false); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
      (b.imgs||(b.imgs={}))[x.key]=tx; b.texBytes+=cv.width*cv.height*4; S.abytes=(S.abytes||0)+cv.width*cv.height*4; }; img.src=wk.img; }); }

/* ── batches on the GPU (lazy, least recently used ones dropped past the memory cap) ── */
function upload(G,b){ var gl=S.gl, mb=buildBatch(G,b), total=0, ranges=[]; mb.order.forEach(function(k){ total+=mb.k[k].n; });
  var ab=new ArrayBuffer(Math.max(1,total)*STRIDE), u8=new Uint8Array(ab), off=0;
  mb.order.forEach(function(k){ var B=mb.k[k]; u8.set(new Uint8Array(B.ab,0,B.n*STRIDE),off*STRIDE); var m=matOf(G,k); ranges.push({k:k, m:m, first:off, count:B.n, trans:!!m.trans}); off+=B.n; });
  ranges.sort(function(a,c){ return (a.trans?1:0)-(c.trans?1:0)||(a.m.kind===5?0:1)-(c.m.kind===5?0:1); });
  var vb=gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER,vb); gl.bufferData(gl.ARRAY_BUFFER,ab,gl.STATIC_DRAW);
  b.built={vb:vb, ranges:ranges, bytes:ab.byteLength, tris:total/3}; b.texBytes=0; S.bytes+=ab.byteLength; if(S.sm) S.sm.dirty=1;
  ranges.forEach(function(r){ if(r.m.kind===0&&r.m.gen!=null){ genTex(r.m.gen); realOf(r.m.gen); } });
  if(b.art.length||b.lab.length){ b.atlas=artAtlas(G,b); S.abytes=(S.abytes||0)+(b.texBytes||0); loadImages(b); }
  S.built++; }
function drop(b){ var gl=S.gl; if(!b.built) return; gl.deleteBuffer(b.built.vb); S.bytes-=b.built.bytes; S.abytes=Math.max(0,(S.abytes||0)-(b.texBytes||0)); b.texBytes=0; if(b.atlas) gl.deleteTexture(b.atlas); if(b.imgs) for(var k in b.imgs) gl.deleteTexture(b.imgs[k]); b.atlas=null; b.imgs=null; b.built=null; }
/* geometry plus each room's art atlas and pictures count against the cap (phones: the medium tier) */
function budget(){ var cap=S.T.name==='high'?220e6:S.T.name==='medium'?110e6:64e6; if(S.bytes+(S.abytes||0)<cap) return; var list=S.G.batches.filter(function(b){ return b.built&&b.kind==='room'&&b.lastUse<S.frame-2; }); list.sort(function(a,c){ return a.lastUse-c.lastUse; });
  while(S.bytes+(S.abytes||0)>cap*.8&&list.length) drop(list.shift()); }

/* ── which batches to draw: room-to-room through openings in view ── */
function visible(G,P,eye){ var cur=S.room, seen={}, out=[], queue=[], vis={};
  var start=cur?cur.i:-1; queue.push([start,0]); seen[start]=1; var cr=S.camRoom; if(cr&&cr!==cur&&!seen[cr.i]){ queue.push([cr.i,0]); seen[cr.i]=1; }        /* third person: the camera may stand a room behind the walker */
  while(queue.length){ var it=queue.shift(), id=it[0], dp=it[1]; vis[id]=dp;
    var nb=id<0?G.outNb:G.rooms[id].nb; if(dp>=(start<0?3:7)||(id<0&&dp>0)) continue;
    for(var i=0;i<nb.length;i++){ var p=nb[i], o=p.a===id?p.b:p.a; if(seen[o]) continue; var bb=p.bb, near=eye[0]>bb[0]-1.5&&eye[0]<bb[3]+1.5&&eye[1]>bb[1]-1.5&&eye[1]<bb[4]+1.5&&eye[2]>bb[2]-1.5&&eye[2]<bb[5]+1.5;
      if(!near){ if(!boxIn(P,bb)) continue; var cx=(bb[0]+bb[3])/2, cy=(bb[1]+bb[4])/2, dd=Math.hypot(cx-eye[0],cy-eye[1]); if(dd>90||(dp>=3&&dd>55)) continue; }
      seen[o]=1; queue.push([o,dp+1]); } }
  S.outVis=false; for(var k in vis){ var id2=+k; if(id2<0){ S.outVis=true; G.lvs.forEach(function(l){ out.push(l.b); }); out.push(G.site); if(G.back&&start<0) out.push(G.back); } else out.push(G.rooms[id2].b); }
  if(cur){ cur.nb.forEach(function(p){ var o=p.a===cur.i?p.b:p.a; if(o>=0) (S.pre||(S.pre=[])).push(G.rooms[o].b); }); }
  return out; }

/* ── the frame ── */
function render(){ var gl=S.gl, G=S.G; if(!gl||S.lost) return; S.frame++; S.now=performance.now(); FXG.pump(S.settling?40:4);
  var cw=S.cw, ch=S.ch, T=S.T;
  if(T.samples&&T.wgl2){ if(!S.fb||S.fb.w!==cw||S.fb.h!==ch){ S.fb=target(gl,cw,ch,T.samples,S.fb); } gl.bindFramebuffer(gl.FRAMEBUFFER,S.fb?S.fb.fb:null); } else gl.bindFramebuffer(gl.FRAMEBUFFER,null);
  gl.viewport(0,0,cw,ch); gl.clearColor(.05,.05,.05,1); gl.depthMask(true); gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
  var asp=cw/ch, vf=asp>=1?2*Math.atan(Math.tan(PI/4)/asp):PI/2; vf=clamp(vf,50*PI/180,90*PI/180);
  var cp=Math.cos(S.pitch), fw=[Math.cos(S.yaw)*cp,Math.sin(S.yaw)*cp,Math.sin(S.pitch)], eye=camEye(fw), ctr=[eye[0]+fw[0],eye[1]+fw[1],eye[2]+fw[2]];
  var V=lookAt(eye,ctr,[0,0,1]), Pm=persp(vf,asp,CFG.near,CFG.far), VP=mmul(Pm,V), PL=planes(VP); S.VP=VP;
  var rt=nrm(cross(fw,[0,0,1])), up=cross(rt,fw), ty=Math.tan(vf/2), tx=ty*asp;
  /* the exposure eases toward the room's (or outdoors) */
  var lt=S.room?(S.room.b.light||null):null, et=lt?lt.exp:.21; S.exp+=(et-S.exp)*(1-Math.exp(-S.dt/.6)); if(S.snapExp){ S.exp=et; S.snapExp=0; }
  var scr=[S.exp,0,1/cw,1/ch];
  /* sky */
  var skyOn=!S.room||roomHasWin(G,S.room)||S.outVis;       /* a room with no window never shows sky: a hairline gap in its walls then reads as shadow, not a white crack */
  gl.disable(gl.DEPTH_TEST); gl.depthMask(false); gl.disable(gl.BLEND); gl.disable(gl.CULL_FACE); gl.useProgram(S.ps.p); var u=S.ps.u;
  gl.uniform3fv(u.uF,fw); gl.uniform3fv(u.uR,[rt[0]*tx,rt[1]*tx,rt[2]*tx]); gl.uniform3fv(u.uU,[up[0]*ty,up[1]*ty,up[2]*ty]); gl.uniform3fv(u.uSun,S.sun); gl.uniform3fv(u.uSunC,S.sunC); gl.uniform3fv(u.uSkyC,S.sky); gl.uniform4fv(u.uScr,[S.exp,0,1/cw,1/ch]);
  var ibl=[1.37,1,S.env?Math.min(1,(S.now-S.envT0)/800):0,0]; FXG.uni(gl,u,S.sun,1,S.env&&S.env.tx,6); if(u.uIbl) gl.uniform4fv(u.uIbl,ibl);
  gl.bindBuffer(gl.ARRAY_BUFFER,S.quad); gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0,2,gl.FLOAT,false,8,0); for(var a=1;a<4;a++) gl.disableVertexAttribArray(a); if(skyOn) gl.drawArrays(gl.TRIANGLES,0,6);
  /* world */
  S.pre=[]; var list=visible(G,PL,eye), t0=performance.now(); S.list=list;
  var want=list.concat(S.pre).filter(function(b){ return !b.built; }); want.sort(function(p,c){ return bdist(p,eye)-bdist(c,eye); });
  for(var w=0;w<want.length;w++){ if(w>0&&performance.now()-t0>(S.settling?1e9:7)) break; upload(G,want[w]); }
  var vis=list; list=list.filter(function(b){ return b.built&&boxIn(PL,b.bb); }); list.sort(function(p,c){ return bdist(p,eye)-bdist(c,eye); });
  if(S.sm){ smRender(G,eye); if(T.samples&&T.wgl2&&S.fb) gl.bindFramebuffer(gl.FRAMEBUFFER,S.fb.fb); else gl.bindFramebuffer(gl.FRAMEBUFFER,null); gl.viewport(0,0,cw,ch); }
  gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL); gl.depthMask(true); gl.enable(gl.CULL_FACE); gl.cullFace(gl.BACK); gl.frontFace(gl.CCW);
  var pw=S.pw; gl.useProgram(pw.p); u=pw.u; gl.uniformMatrix4fv(u.uVP,false,VP); gl.uniform3fv(u.uEye,eye); gl.uniform3fv(u.uSun,S.sun); gl.uniform3fv(u.uSunC,S.sunC); gl.uniform3fv(u.uSkyC,S.sky); gl.uniform4fv(u.uScr,scr);
  gl.uniform1i(u.uA,0); gl.uniform1i(u.uB,1); gl.uniform1i(u.uSM,2); if(u.uA2){ gl.uniform1i(u.uA2,4); gl.uniform1i(u.uB2,5); } FXG.uni(gl,u,S.sun,1,S.env&&S.env.tx,6); if(u.uIbl) gl.uniform4fv(u.uIbl,ibl);
  if(S.sm){ gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_2D,S.sm.tx); gl.activeTexture(gl.TEXTURE0); gl.uniformMatrix4fv(u.uLVP,false,S.sm.lvp); gl.uniform4fv(u.uSMp,[1/S.sm.N,2*S.sm.R/S.sm.N,1,.00035]); }
  else gl.uniform4fv(u.uSMp,[0,0,0,0]);
  var stats={draws:0, tris:0, batches:list.length}, rh=null, rp=S.room&&!S.noRefl&&T.name==='high'&&q().bldgrefl!=='0'?polish(S.room):0;
  if(rp>0&&S.fz-S.room.l.e<.4){ gl.uniform4fv(u.uSMp,S.sm?[1/S.sm.N,2*S.sm.R/S.sm.N,1,.00035]:[0,0,0,0]); if(reflPass(G,vis,VP,eye,S.room.l.e)) rh=S.room.l.e;
    if(T.samples&&T.wgl2&&S.fb) gl.bindFramebuffer(gl.FRAMEBUFFER,S.fb.fb); else gl.bindFramebuffer(gl.FRAMEBUFFER,null); gl.viewport(0,0,cw,ch); gl.uniformMatrix4fv(u.uVP,false,VP); gl.uniform3fv(u.uEye,eye); }
  gl.uniform4fv(u.uClip,[0,0,0,0]); gl.uniform4fv(u.uRefl,rh!=null?[1,rh,1,0]:[0,0,0,0]); gl.uniform1i(u.uRT,3); gl.activeTexture(gl.TEXTURE3); gl.bindTexture(gl.TEXTURE_2D,rh!=null?S.rt.tx:S.white); gl.activeTexture(gl.TEXTURE0);
  list.forEach(function(b){ b.lastUse=S.frame; drawBatch(b,false,stats); });
  var avb=avatarBatch(); if(avb) drawBatch(avb,false,stats); var lt0=S.room?S.room.b.light:(G.site&&G.site.light); if(lt0){ var nvb=navBatch(lt0); if(nvb) drawBatch(nvb,false,stats); }
  gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA); gl.depthMask(false); gl.disable(gl.CULL_FACE);
  for(var i=list.length-1;i>=0;i--) drawBatch(list[i],true,stats);
  if(avb) drawBatch(avb,true,stats);
  gl.disable(gl.BLEND); gl.depthMask(true);
  if(S.fb&&T.wgl2&&S.post&&S.post.ok&&S.post.end(S.fb.fb,cw,ch,{near:CFG.near, far:CFG.far, tx:tx, ty:ty})){}
  else if(S.fb&&T.wgl2){ var t=S.fb; gl.bindFramebuffer(gl.READ_FRAMEBUFFER,t.fb); if(t.rfb){ gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,t.rfb); gl.blitFramebuffer(0,0,cw,ch,0,0,cw,ch,gl.COLOR_BUFFER_BIT,gl.NEAREST); gl.bindFramebuffer(gl.READ_FRAMEBUFFER,t.rfb); }
    gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,null); gl.blitFramebuffer(0,0,cw,ch,0,0,cw,ch,gl.COLOR_BUFFER_BIT,gl.NEAREST); gl.bindFramebuffer(gl.FRAMEBUFFER,null); }
  S.stats=stats; budget(); }
function bdist(b,e){ var a=b.bb, dx=Math.max(a[0]-e[0],0,e[0]-a[3]), dy=Math.max(a[1]-e[1],0,e[1]-a[4]), dz=Math.max(a[2]-e[2],0,e[2]-a[5]); return Math.sqrt(dx*dx+dy*dy+dz*dz)+(b.kind==='site'?50:0); }
function drawBatch(b,trans,stats){ var gl=S.gl, u=S.pw.u, B=b.built, L=b.light, any=false;
  for(var i=0;i<B.ranges.length;i++){ if(B.ranges[i].trans===trans){ any=true; break; } } if(!any) return;
  gl.bindBuffer(gl.ARRAY_BUFFER,B.vb); for(var a=0;a<4;a++) gl.enableVertexAttribArray(a);
  gl.vertexAttribPointer(0,3,gl.FLOAT,false,STRIDE,0); gl.vertexAttribPointer(1,3,gl.BYTE,true,STRIDE,12); gl.vertexAttribPointer(2,2,gl.FLOAT,false,STRIDE,16); gl.vertexAttribPointer(3,4,gl.UNSIGNED_BYTE,true,STRIDE,24);
  gl.uniform4fv(u.uRoom,L.room); gl.uniform3fv(u.uAmbC,L.ambC); gl.uniform3fv(u.uAmbF,L.ambF); gl.uniform4fv(u.uFog,L.fog);
  gl.uniform4fv(u.uSpP,L.spP); gl.uniform4fv(u.uSpD,L.spD); gl.uniform4fv(u.uSpC,L.spC); gl.uniform1f(u.uNS,L.ns);
  gl.uniform4fv(u.uWnC,L.wC); gl.uniform4fv(u.uWnU,L.wU); gl.uniform4fv(u.uWnN,L.wN); gl.uniform1f(u.uNW,L.nw);
  gl.uniform4fv(u.uEd,L.ed); gl.uniform1f(u.uNE,L.ne); gl.uniform4fv(u.uBl,L.bl); gl.uniform4fv(u.uBr,L.br); gl.uniform1f(u.uNB,L.nb);
  for(var j=0;j<B.ranges.length;j++){ var r=B.ranges[j]; if(r.trans!==trans) continue; var m=r.m, ta=S.white, tb=S.flatN, uv=[1,1,0,0];
    if(m.kind===0){ var tx=S.tex[m.gen]||genTex(m.gen); ta=tx[0]; tb=tx[1];
      if(u.uRx){ var re=realOf(m.gen); if(re){ gl.activeTexture(gl.TEXTURE4); gl.bindTexture(gl.TEXTURE_2D,re.a); gl.activeTexture(gl.TEXTURE5); gl.bindTexture(gl.TEXTURE_2D,re.b); gl.uniform4fv(u.uRx,[Math.min(1,(S.now-re.t0)/700),re.tile,re.baked,0]); } else gl.uniform4fv(u.uRx,Z4); } }
    else if(m.kind===2){ if(m.lab){ ta=b.atlas||S.white; } else { var im=b.imgs&&b.imgs[r.k]; if(im) ta=im; else { ta=b.atlas||S.white; var i2=m.art%12; uv=[.25,.25,(i2%4)*.25,1-(Math.floor(i2/4)+1)*.25]; } } }
    if(m.kind!==0&&u.uRx) gl.uniform4fv(u.uRx,Z4);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D,ta); gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D,tb);
    var t=m.tint||[1,1,1]; gl.uniform4fv(u.uTint,[t[0],t[1],t[2],m.kind]); gl.uniform4fv(u.uJ,m.j||Z4); var mv=m.v||Z4; gl.uniform4fv(u.uVar,[mv[0],mv[1],mv[2],mv[3]||0]); gl.uniform1f(u.uPol,m.pol||0); gl.uniform4fv(u.uMat,[m.kind===6?(m.e||8):(m.tile||1),m.kind>=4&&m.kind<=5?(m.a||0):(m.rough||.8),m.metal||0,m.bump||0]); gl.uniform4fv(u.uUv,uv);
    gl.drawArrays(gl.TRIANGLES,r.first,r.count); stats.draws++; stats.tris+=r.count/3; } }

/* ── third person: the camera behind and a little above the walker's head, pulled in before any wall, floor or ceiling ── */
function third(){ return !!(S.av&&S.view==='third'); }
function camHit(G,x,y,z,lid){ var ps=primsNear(G,x,y,.4); for(var i=0;i<ps.length;i++){ var p=ps[i]; if(z>=p.z0-.1&&z<=p.z1+.1&&primDist(p,x,y)<.17){ S.camWhy='prim '+(p.tag||p.k)+(p.wall?' wall':''); return true; } }
  var s=supports(G,x,y); for(var j=0;j<s.length;j++) if(Math.abs(z-s[j])<.14){ S.camWhy='floor '+s[j]; return true; }
  var r=roomAt(G,lid,x,y); if(S.room&&(!r||r.isVoid&&z<r.l.e+.2)){ S.camWhy='no room'; return true; } if(r&&!r.isVoid&&z>r.ceil-.14){ S.camWhy='ceiling '+r.id; return true; } return false; }
function camEye(fw){ var me=[S.x,S.y,S.ez]; S.camRoom=null; if(!third()) return me; var G=S.G, piv=[S.x,S.y,S.ez-CFG.eye+S.av.R.H*.8], lid=levelAt(S.fz).id;
  var d=[-fw[0]*CFG.camD,-fw[1]*CFG.camD,-fw[2]*CFG.camD+CFG.camUp], L=Math.hypot(d[0],d[1],d[2]), u=[d[0]/L,d[1]/L,d[2]/L], t=L;
  for(var s=.12;s<=L+.2;s+=.08){ if(camHit(G,piv[0]+u[0]*s,piv[1]+u[1]*s,piv[2]+u[2]*s,lid)){ t=Math.max(.15,s-.24); break; } }
  if(S.camD==null||t<S.camD||S.snapCam) S.camD=t; else S.camD+=(t-S.camD)*(1-Math.exp(-(S.dt||.016)/.3)); S.snapCam=0;
  var e=[piv[0]+u[0]*S.camD,piv[1]+u[1]*S.camD,piv[2]+u[2]*S.camD]; S.camRoom=roomAt(G,lid,e[0],e[1]); S.camE=e; return e; }
/* the avatar as a batch of its own (one range per colour + its soft shadow), re-skinned every frame; lit like the room it stands in */
function avatarBatch(){ if(!third()||S.camD<.75) { if(S.tagEl) S.tagEl.style.opacity=0; return null; } var gl=S.gl, A=S.av, G=S.G, lt=S.room?S.room.b.light:(G.site&&G.site.light); if(!lt) return null;
  var fz=S.ez-CFG.eye+(S.dip||0); AV.emit(A,S.x,S.y,fz,1,null); var n=A.n, nv=n+6;
  if(!S.avAB||S.avAB.byteLength<nv*STRIDE){ S.avAB=new ArrayBuffer(nv*STRIDE); S.avF=new Float32Array(S.avAB); S.avI8=new Int8Array(S.avAB); S.avU8=new Uint8Array(S.avAB); }
  var f=S.avF, i8=S.avI8, u8=S.avU8, P=A.pos, N=A.nrm;
  for(var v=0;v<n;v++){ var o=v*7, b=v*STRIDE, k=v*3; f[o]=P[k]; f[o+1]=P[k+1]; f[o+2]=P[k+2]; i8[b+12]=Math.round(N[k]*127); i8[b+13]=Math.round(N[k+1]*127); i8[b+14]=Math.round(N[k+2]*127); f[o+4]=0; f[o+5]=0; u8[b+24]=255; u8[b+25]=255; u8[b+26]=0; u8[b+27]=0; }
  var sup=supportAt(G,S.x,S.y,S.fz+.05), sz=(sup==null?fz:sup)+.012, r=.42*(1-clamp((fz-(sup==null?fz:sup))*.8,0,.5)), Q=[[-1,-1],[1,-1],[1,1],[-1,-1],[1,1],[-1,1]];
  for(var q=0;q<6;q++){ var o2=(n+q)*7, b2=(n+q)*STRIDE; f[o2]=S.x+Q[q][0]*r; f[o2+1]=S.y+Q[q][1]*r; f[o2+2]=sz; i8[b2+12]=0; i8[b2+13]=0; i8[b2+14]=127; f[o2+4]=Q[q][0]; f[o2+5]=Q[q][1]; u8[b2+24]=255; u8[b2+25]=255; u8[b2+26]=0; u8[b2+27]=0; }
  if(!S.avVB) S.avVB=gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER,S.avVB); gl.bufferData(gl.ARRAY_BUFFER,new Uint8Array(S.avAB,0,nv*STRIDE),gl.DYNAMIC_DRAW);
  var ranges=A.ranges.map(function(rg){ var key='av#'+A.cols[rg.c].slice(1); return {k:key, m:matOf(G,key), first:rg.first, count:rg.count, trans:false}; });
  ranges.push({k:'avshadow', m:matOf(G,'avshadow'), first:n, count:6, trans:true});
  avatarTag(A); return {built:{vb:S.avVB, ranges:ranges}, light:lt}; }
function avatarTag(A){ var el2=S.tagEl; if(!el2||!A.head||!S.VP) return; var t=AV.tag(A); if(!t.text){ el2.style.opacity=0; return; }
  var m=S.VP, h=A.head, x=m[0]*h[0]+m[4]*h[1]+m[8]*(h[2]+.08)+m[12], y=m[1]*h[0]+m[5]*h[1]+m[9]*(h[2]+.08)+m[13], w=m[3]*h[0]+m[7]*h[1]+m[11]*(h[2]+.08)+m[15];
  if(w<.1){ el2.style.opacity=0; return; } var cw=S.root.clientWidth, ch=S.root.clientHeight; el2.style.transform='translate('+((x/w*.5+.5)*cw).toFixed(1)+'px,'+((.5-y/w*.5)*ch).toFixed(1)+'px) translate(-50%,-100%)'; el2.style.opacity=1;
  if(el2.textContent!==t.text){ el2.textContent=t.text; el2.title=t.title; } }
function setView(v){ S.view=v==='first'?'first':'third'; AV.setPref('view',S.view); S.snapCam=1; if(S.viewBtn) S.viewBtn.textContent=S.view==='third'?'First person · T':'Third person · T'; if(S.tagEl&&S.view!=='third') S.tagEl.style.opacity=0; }
function setAvatar(w){ var c=AV.city(S.G&&S.G.plan.name,(S.G&&S.G.plan.geo||{}).lat,(S.G&&S.G.plan.geo||{}).lon); S.av=AV.make(c,w==='generic'?'generic':'mayor'); AV.setPref('avatar',S.av.mayor?'mayor':'generic');
  if(S.avBtn){ var m=c&&c.m; S.avBtn.textContent=S.av.mayor?'Avatar: '+m.n:'Avatar: generic'; S.avBtn.disabled=!(c&&c.look&&m); S.avBtn.title=S.av.mayor?AV.tag(S.av).title:(c&&c.look&&m?'Switch to the figure after Mayor '+m.n:'No mayor data for this city: the generic figure'); } }

/* ── walking ── */
function levelAt(z){ var G=S.G, l=G.lvs[0]; G.lvs.forEach(function(o){ if(o.e<=z+.6) l=o; }); return l; }
function locate(){ var G=S.G, fz=S.fz, best=null; G.lvs.forEach(function(l){ if(l.e>fz+.6) return; var r=roomAt(G,l.id,S.x,S.y); if(r&&(!best||l.e>best.l.e)) best=r; });
  if(best&&S.fz>best.ceil) best=null; return best; }
function colZ(){ return S.air?Math.min(S.fz,S.gnd):S.fz; }        /* furniture and walls are tested from the ground you left: a hop never clears a bench or a rope (and never lands inside one) */
/* the lowest thing over the head at (x,y): a floor or flight above (its slab), the room's ceiling, a lintel or beam */
function ceilAt(G,x,y,fz){ var c=1e9, s=supports(G,x,y); for(var i=0;i<s.length;i++) if(s[i]>fz+CFG.step+.05&&s[i]-.25<c) c=s[i]-.25;
  G.lvs.forEach(function(l){ if(l.e>fz+.6||l.e<fz-6.5) return; var r=roomAt(G,l.id,x,y); if(r&&!r.isVoid&&r.ceil>fz+.5&&r.ceil<c) c=r.ceil; });
  var ps=primsNear(G,x,y,CFG.pr+.5); for(var j=0;j<ps.length;j++){ var p=ps[j]; if(p.z0>fz+CFG.knee+.05&&p.z0<c&&primDist(p,x,y)<CFG.pr) c=p.z0; } return c; }
function ledge(G,x,y){ var ref=S.air?S.gnd:S.fz, sup=supportDisc(G,x,y,Math.max(S.fz,ref)); if(sup==null) return true; return ref-sup>CFG.drop&&!onStair(G,x,y); }
function okAt(G,x,y){ return !blockedBySurf(x,y)&&!ledge(G,x,y); }
function step(dt,keys){ var G=S.G; keys=keys||S.keys; dt=Math.min(dt,.1); S.dt=dt; var H=AV.HOP, pd=S.noPad?null:AV.pad();
  if(S.nav||S.plan){ if(keys.f||keys.b||keys.l||keys.r||(pd&&(Math.abs(pd.mx)+Math.abs(pd.my)>.3))||S.joyL){ navStop('you took over'); } else { if(S.plan) navPlanStep(); if(S.nav){ var nk=navStep(dt); if(nk) keys=nk; } } }
  if(S.hiT>0) S.hiT-=dt;
  var f=(keys.f?1:0)-(keys.b?1:0)+(S.joyL?-S.joyL[1]:0)+(pd?-pd.my:0)+(keys.mf||0), s=(keys.r?1:0)-(keys.l?1:0)+(S.joyL?S.joyL[0]:0)+(pd?pd.mx:0)+(keys.ms||0), sp=keys.run||(pd&&pd.run)||(S.joyL&&Math.hypot(S.joyL[0],S.joyL[1])>.95)?CFG.hurry:CFG.walk;
  var mag=Math.hypot(f,s); if(mag>1){ f/=mag; s/=mag; }
  var cy=Math.cos(S.yaw), sy=Math.sin(S.yaw), tvx=(cy*f+sy*s)*sp, tvy=(sy*f-cy*s)*sp, k=1-Math.exp(-dt/(S.air?.5:CFG.tau)); S.vx+=(tvx-S.vx)*k; S.vy+=(tvy-S.vy)*k;      /* in the air you steer less */
  S.yaw+=((keys.tl?1:0)-(keys.tr?1:0))*CFG.turn*dt; if(S.joyR){ S.yaw-=S.joyR[0]*2.2*dt; S.pitch=clamp(S.pitch-S.joyR[1]*1.6*dt,-CFG.pitchMax,CFG.pitchMax); }
  if(pd){ S.yaw-=pd.lx*2.4*dt; S.pitch=clamp(S.pitch-pd.ly*1.7*dt,-CFG.pitchMax,CFG.pitchMax); }
  /* the hop: pressed within `buffer` s before touching ground, or within `coyote` s after leaving it; one per touch of the ground, none in the air */
  var hk=!!(keys.hop||(pd&&pd.a)); if(hk&&!S.hopHeld) S.hopBuf=H.buffer; S.hopHeld=hk; S.coy=S.grounded?H.coyote:Math.max(0,(S.coy||0)-dt);
  if(S.hopBuf>0&&S.coy>0&&!S.air&&!S.glide&&ceilAt(G,S.x,S.y,S.fz)-S.fz-CFG.head>.12){ S.air=true; S.gnd=S.fz; S.vz=H.v0; S.coy=0; S.hopBuf=0; S.grounded=false; S.hops=(S.hops||0)+1; }
  S.hopBuf=Math.max(0,(S.hopBuf||0)-dt);
  /* horizontal: sub-steps of at most 8 cm, each committed only when the capsule there is free and not over a drop; else slide along the wall */
  var cz=colZ(), dx=S.vx*dt, dy=S.vy*dt, n=Math.max(1,Math.ceil(Math.hypot(dx,dy)/.08)), x0=S.x, y0=S.y;
  for(var i=0;i<n;i++){ var nx=S.x+dx/n, ny=S.y+dy/n;
    if(!okAt(G,nx,ny)){ if(okAt(G,nx,S.y)) ny=S.y; else if(okAt(G,S.x,ny)) nx=S.x; else { S.vx*=.5; S.vy*=.5; break; } }
    var p=resolve(G,nx,ny,cz); if(!okAt(G,p[0],p[1])) break; S.x=p[0]; S.y=p[1]; }
  if(dt>0){ var mv=Math.hypot(S.x-x0,S.y-y0); S.spd=mv/dt; if(mv<Math.hypot(S.vx,S.vy)*dt*.3){ S.vx=(S.x-x0)/dt; S.vy=(S.y-y0)/dt; } }           /* against a wall: no speed stored up */
  /* stuck rescue: inside geometry for 3 frames in a row (a moved prop, a bad spawn) -> the nearest free spot */
  if(blockedAt(G,S.x,S.y,colZ())){ S.stuckN=(S.stuckN||0)+1; if(S.stuckN>=3){ var fr=freeNear(S.x,S.y,S.fz); S.x=fr[0]; S.y=fr[1]; S.stuckN=0; S.rescues=(S.rescues||0)+1; } } else S.stuckN=0;
  /* vertical: ground snap on stairs and small steps, else the hop / fall in sub-steps of at most 5 cm: land on the first support met, bonk the first ceiling */
  var sup=supportDisc(G,S.x,S.y,S.fz); if(sup==null) sup=S.fz;
  if(!S.air&&!S.glide){ if(sup>=S.fz||S.fz-sup<=CFG.step+.02){ S.fz=sup; S.vz=0; S.grounded=true; } else { S.air=true; S.gnd=S.fz; S.vz=0; S.grounded=false; } }
  if(S.air&&!S.glide){ S.vz-=H.g*dt; var dz=S.vz*dt, m=Math.max(1,Math.ceil(Math.abs(dz)/.05));
    for(var j=0;j<m;j++){ var z1=S.fz+dz/m;
      if(dz>0){ var ce=ceilAt(G,S.x,S.y,S.fz); if(z1+CFG.head>ce-.02){ S.fz=Math.max(S.fz,ce-CFG.head-.02); S.vz=0; S.bonks=(S.bonks||0)+1; break; } }
      else { var su=supportDisc(G,S.x,S.y,S.fz); if(su!=null&&z1<=su){ var imp=-S.vz; S.fz=su; S.vz=0; S.air=false; S.grounded=true; S.dip=Math.min(.07,imp*.011); break; } }
      S.fz=z1; } }
  if(sup>=S.fz-.005&&!S.air&&!S.glide&&!onStair(G,S.x,S.y)){ var sf=S.safe; if(!sf||Math.hypot(S.x-sf.x,S.y-sf.y)>1.5||Math.abs(S.fz-sf.z)>.4) S.safe={x:S.x,y:S.y,z:S.fz}; }
  if(S.safe&&!S.glide&&S.air&&S.fz<S.safe.z-1.3&&S.vz<-4.5&&!onStair(G,S.x,S.y)){ S.x=S.safe.x; S.y=S.safe.y; S.fz=S.safe.z; S.vz=0; S.vx=S.vy=0; S.air=false; S.grounded=true; S.snap=1; S.snapExp=1; S.nets=(S.nets||0)+1; }       /* never fall into another floor: back to the last safe spot */
  if(!isFinite(S.x+S.y+S.fz)&&S.safe){ S.x=S.safe.x; S.y=S.safe.y; S.fz=S.safe.z; S.vx=S.vy=S.vz=0; }
  if(S.glide){ var g=S.glide; g.t+=dt; var a=clamp(g.t/g.d,0,1), e=a*a*(3-2*a); S.fz=g.z0+(g.z1-g.z0)*e; S.vz=0; S.air=false; if(a>=1) S.glide=null; }
  S.dip=Math.max(0,(S.dip||0)-dt*.35);
  var tz=S.fz+CFG.eye-(S.dip||0); if(S.air) S.ez=tz; else S.ez+=(tz-S.ez)*(1-Math.exp(-dt*(Math.abs(tz-S.ez)>1?6:16))); if(S.snap){ S.ez=tz; S.snap=0; }
  S.room=locate(); S.lv=levelAt(S.fz);
  if(S.av&&dt>0) AV.tick(S.av,dt,{gait:(S.spd||0)/CFG.walk, vx:S.vx, vy:S.vy, air:S.air, vz:S.vz, face:S.yaw}); }
function blockedBySurf(x,y){ var s=supports(S.G,x,y), fz=S.fz; for(var i=0;i<s.length;i++) if(s[i]>fz+CFG.step&&s[i]<fz+CFG.head) return true; return false; }
function goLevel(dir){ var G=S.G, cur=levelAt(S.fz), i=G.lvs.indexOf(cur)+dir; if(i<0||i>=G.lvs.length) return false; var l=G.lvs[i];
  var r=roomAt(G,l.id,S.x,S.y), hole=r&&r.holesF.some(function(h){ return pip(h,S.x,S.y); });
  if(r&&!hole&&!blockedAt(G,S.x,S.y,l.e)){ S.glide={z0:S.fz,z1:l.e,t:0,d:reduced()?0.001:.6}; return true; }
  var t=nearestRoom(G,l,[S.x,S.y]); if(!t) return false; var p=freeNear(t.ctr[0],t.ctr[1],l.e); veilPulse(function(){ S.x=p[0]; S.y=p[1]; S.fz=l.e; S.snap=1; S.snapExp=1; }); return true; }
function freeNear(x,y,fz){ var G=S.G; for(var r=0;r<6;r+=.35) for(var a=0;a<12;a++){ var t=a/12*2*PI, px=x+Math.cos(t)*r, py=y+Math.sin(t)*r; if(!blockedAt(G,px,py,fz)&&supportAt(G,px,py,fz)!=null&&Math.abs(supportAt(G,px,py,fz)-fz)<.3) return [px,py]; if(!r) break; } return [x,y]; }
function reduced(){ try{ return matchMedia('(prefers-reduced-motion: reduce)').matches; }catch(x){ return false; } }

/* ── picking: what the reticle (or a click) rests on ── */
function ray(ox,oy,oz,dx,dy,dz,max){ var G=S.G, best={t:max,hit:null};
  var cands=[]; (S.list||[]).forEach(function(b){ cands=cands.concat(b.picks); }); if(S.room) cands=cands.concat(S.room.b.picks);
  cands.forEach(function(p){ var t=null;
    if(p.rect){ var R=p.rect, dn=dx*R.n[0]+dy*R.n[1]+dz*R.n[2]; if(dn>-1e-4) return; t=((R.c[0]-ox)*R.n[0]+(R.c[1]-oy)*R.n[1]+(R.c[2]-oz)*R.n[2])/dn; if(t<0||t>best.t) return;
      var hx=ox+dx*t-R.c[0], hy=oy+dy*t-R.c[1], hz=oz+dz*t-R.c[2], u=hx*R.d[0]+hy*R.d[1]+hz*R.d[2]; if(Math.abs(u)>R.hw||Math.abs(hz)>R.hh) return; }
    else if(p.box){ var X=p.box, lx=(ox-X.x)*X.c+(oy-X.y)*X.s, ly=-(ox-X.x)*X.s+(oy-X.y)*X.c, ldx=dx*X.c+dy*X.s, ldy=-dx*X.s+dy*X.c, t0=0, t1=best.t;
      var sl=function(o,d,lo,hi){ if(Math.abs(d)<1e-9) return o>=lo&&o<=hi; var a=(lo-o)/d, b=(hi-o)/d; if(a>b){ var c=a; a=b; b=c; } t0=Math.max(t0,a); t1=Math.min(t1,b); return t0<=t1; };
      if(!sl(lx,ldx,-X.hx,X.hx)||!sl(ly,ldy,-X.hy,X.hy)||!sl(oz,dz,X.z0,X.z1)) return; t=t0; }
    if(t!=null&&t<best.t){ best={t:t,hit:p}; } });
  if(best.hit){ var wt=wallHit(ox,oy,oz,dx,dy,dz,best.t); if(wt<best.t-.3) return null; } return best.hit; }
function wallHit(ox,oy,oz,dx,dy,dz,max){ var G=S.G, best=max, seen={}; for(var s=0;s<=max;s+=1){ primsNear(G,ox+dx*s,oy+dy*s,1.2).forEach(function(p){ if(seen[p.i]||p.k!=='seg'||!p.wall) return; seen[p.i]=1;
    var ex=p.bx-p.ax, ey=p.by-p.ay, den=dx*ey-dy*ex; if(Math.abs(den)<1e-9) return; var t=((p.ax-ox)*ey-(p.ay-oy)*ex)/den, v=((p.ax-ox)*dy-(p.ay-oy)*dx)/den; if(t<0||t>best||v<0||v>1) return;
    var z=oz+dz*t; if(z<p.z0||z>p.z1) return; var hx=ox+dx*t, hy=oy+dy*t; if(onOpening(hx,hy,z)) return; best=t; }); } return best; }
function onOpening(x,y,z,GG){ var G=GG||S.G; for(var i=0;i<G.walls.length;i++){ var W=G.walls[i]; for(var j=0;j<W.ops.length;j++){ var op=W.ops[j]; if(!op.sg) continue; var sg=op.sg, u=(x-sg.A[0])*sg.d[0]+(y-sg.A[1])*sg.d[1]+sg.s0, v=(x-sg.A[0])*sg.n[0]+(y-sg.A[1])*sg.n[1];
    if(Math.abs(v)<W.ht+.05&&u>op.a0&&u<op.a1&&z>op.z0&&z<archTop(op,u)) return true; } } return false; }
function nodeForAnchor(id){ if(String(id).indexOf('card-')===0) return String(id).slice(5); var d=S.data||{}, ns=d.nodes||{}, ord=d.order||Object.keys(ns); for(var i=0;i<ord.length;i++){ var n=ns[ord[i]]; if(n&&n.s===id) return ord[i]; } return null; }
function nodeForRoom(rid){ var d=S.data||{}, ns=d.nodes||{}, ord=d.order||Object.keys(ns), any=null; for(var i=0;i<ord.length;i++){ var n=ns[ord[i]]; if(n&&n.r===rid){ if(!n.s) return ord[i]; if(!any) any=ord[i]; } } return any; }
function pickNow(cx,cy){ var fw=dirAt(cx,cy), hit=ray(S.x,S.y,S.ez,fw[0],fw[1],fw[2],7); if(!hit) hit=doorPick(fw); return hit; }
function doorPick(fw){ var G=S.G, best=null, bt=5; G.walls.forEach(function(W){ if(W.lv!==S.lv) return; W.ops.forEach(function(op){ if(!op.pass||!op.sg) return; var tgt=null;
    [op.ra,op.rb].forEach(function(r){ if(r&&r!==S.room&&nodeForRoom(r.id)) tgt=r; }); if(!tgt) return; var sg=op.sg, n=[sg.n[0],sg.n[1],0], c=[op.c[0],op.c[1],(op.z0+Math.min(op.z1,op.z0+2.4))/2];
    var dn=fw[0]*n[0]+fw[1]*n[1]; if(Math.abs(dn)<1e-4) return; var t=((c[0]-S.x)*n[0]+(c[1]-S.y)*n[1])/dn; if(t<0||t>bt) return; var hx=S.x+fw[0]*t-c[0], hy=S.y+fw[1]*t-c[1], hz=S.ez+fw[2]*t;
    if(Math.abs(hx*sg.d[0]+hy*sg.d[1])>(op.a1-op.a0)/2||hz<op.z0||hz>op.z1) return; bt=t; best={k:'door', room:tgt}; }); }); return best; }
function dirAt(cx,cy){ var cw=S.root.clientWidth, ch=S.root.clientHeight, asp=cw/ch, vf=clamp(asp>=1?2*Math.atan(Math.tan(PI/4)/asp):PI/2,50*PI/180,PI/2), ty=Math.tan(vf/2), tx=ty*asp;
  var cp=Math.cos(S.pitch), fw=[Math.cos(S.yaw)*cp,Math.sin(S.yaw)*cp,Math.sin(S.pitch)], rt=nrm(cross(fw,[0,0,1])), up=cross(rt,fw), nx=(cx/cw*2-1)*tx, ny=(1-cy/ch*2)*ty;
  return nrm([fw[0]+rt[0]*nx+up[0]*ny,fw[1]+rt[1]*nx+up[1]*ny,fw[2]+rt[2]*nx+up[2]*ny]); }
function describe(h){ if(!h) { var rn=S.room&&nodeForRoom(S.room.id); return rn?{node:rn, text:nodeText(rn)}:null; }
  if(h.k==='slot'){ var nid=nodeForAnchor(h.id), it=S.G.slots[h.id], wk=it?wkOf(it.s):{}; if(nid) return {node:nid, text:nodeText(nid)}; return {text:wk.t?(wk.t+(wk.a?' · '+wk.a:'')):'A place for a work'}; }
  if(h.k==='fx'){ var n2=nodeForAnchor(h.id), f=S.G.fxs[h.id]; if(n2) return {node:n2, text:nodeText(n2)}; return f&&f.f.n?{text:f.f.n}:null; }
  if(h.k==='door'){ var n3=nodeForRoom(h.room.id); return n3?{node:n3, text:nodeText(n3)+' · '+h.room.name}:null; }
  if(h.k==='lift'){ var o=h.st, to=h.lv===o.lo?o.hi:o.lo; return {lift:h, text:'Take the lift to '+to.n}; } return null; }
function nodeText(id){ var n=(S.data.nodes||{})[id]; return n?('Open '+n.n+'  '+dec(n.t)):'Open'; }
function act(h){ var d=describe(h); if(!d) return; if(d.node) return openNode(d.node); if(d.lift){ var o=d.lift.st, to=d.lift.lv===o.lo?o.hi:o.lo; var p=freeNear(S.x,S.y,to.e); veilPulse(function(){ S.x=p[0]; S.y=p[1]; S.fz=to.e; S.snap=1; S.snapExp=1; }); } }

/* ── the detail page and the way back ── */
function openNode(id){ if(typeof window.showDetail!=='function') return; var html=D.documentElement; pause(true);
  try{ if(window.AltoBuilding) AltoBuilding.hide(); }catch(x){} S.ret={opened:false};
  try{ window.showDetail('node',id); }catch(e){ if(window.console) console.warn('bldg fpv',e); }
  if(html.classList.contains('detail-open')) S.ret.opened=true;
  S.mo=new MutationObserver(function(){ var r=S.ret; if(!r) return; var o=html.classList.contains('detail-open'); if(o){ r.opened=true; return; } if(r.opened) comeBack(); }); S.mo.observe(html,{attributes:true,attributeFilter:['class']});
  S.retT=setTimeout(function(){ if(S.ret&&!S.ret.opened&&!html.classList.contains('detail-open')) comeBack(); },900); }
function comeBack(){ if(S.mo){ S.mo.disconnect(); S.mo=null; } clearTimeout(S.retT); S.ret=null; if(!S.G) return; pause(false); }
function pause(p){ S.paused=p; if(S.root) S.root.style.display=p?'none':''; if(p){ cancelAnimationFrame(S.raf); S.raf=0; S.keys={}; } else { S.last=0; S.raf=requestAnimationFrame(loop); } }

/* ── HUD, input ── */
function el(t,c,p,txt){ var n=D.createElement(t); if(c) n.className=c; if(txt!=null) n.textContent=txt; if(p) p.appendChild(n); return n; }
/* find and go to a card: the list (C), next / previous card (N / P) */
/* ── going to a card (the Cards list C, N / P, the blueprint's chips): a pose in front of its sign, a route there, a guided walk or a short fade ── */
/* the sightline from the eye to the sign's middle crosses no wall, door leaf or tall prop */
function sightClear(G,x0,y0,z0,x1,y1,z1){ var L=Math.hypot(x1-x0,y1-y0), k=Math.max(1,Math.ceil(L/.12)); for(var i=1;i<k-1;i++){ var t=i/k, x=x0+(x1-x0)*t, y=y0+(y1-y0)*t, z=z0+(z1-z0)*t, ps=primsNear(G,x,y,.3);
    for(var j=0;j<ps.length;j++){ var p=ps[j]; if(String(p.tag||'').indexOf('card-')===0) continue; if(z>=p.z0&&z<=p.z1&&primDist(p,x,y)<.01) return false; } } return true; }
/* where to stand for slot `it`: ~2.2 m in front of it (either face of a card sign, any side of a sculpture), free, on its floor, in its room, seeing it; the yaw and pitch that face it */
function arrival(G,it){ var s=it.s, c=s.p, e=it.room.l.e, n=it.n, faces=s.card?[n,[-n[0],-n[1]]]:it.sculpt?[n,[-n[1],n[0]],[-n[0],-n[1]],[n[1],-n[0]]]:[n], best=null, bs=1e9, cz=it.z;
  faces.forEach(function(f,fi){ [2.2,1.8,2.6,1.5,3,3.6,4.2].forEach(function(d){ [0,.45,-.45,.9,-.9].forEach(function(lat){ var x=c[0]+f[0]*d-f[1]*lat, y=c[1]+f[1]*d+f[0]*lat;
      var sc=Math.abs(d-2.2)+Math.abs(lat)*.6+fi*.25; if(sc>=bs) return; var sp=supportDisc(G,x,y,e+.3); if(sp==null||Math.abs(sp-e)>.15||blockedAt(G,x,y,e)) return;
      var r=roomAt(G,it.room.l.id,x,y); if(r!==it.room&&!(r&&r.r.gp)) sc+=1.5; if(!sightClear(G,x,y,e+CFG.eye,c[0],c[1],cz)) return; bs=sc; best=[x,y]; }); }); });
  if(!best){ var fr=freeNear(c[0]+n[0]*2.2,c[1]+n[1]*2.2,e); best=fr; }
  var dx=c[0]-best[0], dy=c[1]-best[1], dist=Math.hypot(dx,dy)||1; return {x:best[0], y:best[1], z:e, yaw:Math.atan2(dy,dx), pitch:clamp(Math.atan2(cz-(e+CFG.eye),dist),-.5,.4)}; }
/* the route: A* over 0.4 m cells evaluated as they are reached, with the walker's own tests (floor under the capsule, nothing in the way, no step down a ledge); stairs are just cells whose floor rises */
var NAV={cell:.4, max:30000, frameMs:6, totalMs:1600};
function navBox(G){ if(G.navBB) return G.navBB; var b=[1e9,1e9,-1e9,-1e9]; G.rooms.forEach(function(r){ b[0]=Math.min(b[0],r.bb[0]); b[1]=Math.min(b[1],r.bb[1]); b[2]=Math.max(b[2],r.bb[2]); b[3]=Math.max(b[3],r.bb[3]); }); return G.navBB=[b[0]-10,b[1]-10,b[2]+10,b[3]+10]; }
function navCell(G,cache,i,j,zc){ var k=i+','+j+','+Math.round(zc*4), v=cache[k]; if(v!==undefined) return v; var x=i*NAV.cell, y=j*NAV.cell, bb=navBox(G); if(x<bb[0]||y<bb[1]||x>bb[2]||y>bb[3]){ cache[k]=null; return null; }          /* the building and 10 m round it: never a search across the whole site */
  z=supportAt(G,x,y,zc); if(z==null) z=supportDisc(G,x,y,zc);
  v=(z==null||z<zc-CFG.step-.02||blockedAt(G,x,y,z))?null:z; cache[k]=v; return v; }
/* the search keeps its state, so it can run a few milliseconds a frame (the trip's pill shows at once; nothing freezes) */
function routeStart(G,from,to){ var C=NAV.cell, R={G:G, from:from, to:to, cache:{}, open:[], seen:{}, n:0, gi:Math.round(to.x/C), gj:Math.round(to.y/C)}, si=Math.round(from.x/C), sj=Math.round(from.y/C);
  rPush(R,{i:si,j:sj,z:from.z,g:0,f:rH(R,si,sj,from.z),p:null}); R.seen[si+','+sj+','+Math.round(from.z*4)]=0; return R; }
function rH(R,i,j,z){ var C=NAV.cell; return 1.25*(Math.hypot((i-R.gi)*C,(j-R.gj)*C)+Math.abs(z-R.to.z)*1.5); }          /* weighted: a little longer than the best, found much sooner */
function rPush(R,o){ var open=R.open; open.push(o); var a=open.length-1; while(a>0){ var b=(a-1)>>1; if(open[b].f<=open[a].f) break; var q=open[a]; open[a]=open[b]; open[b]=q; a=b; } }
function rPop(R){ var open=R.open, top=open[0], last=open.pop(); if(open.length){ open[0]=last; var a=0; for(;;){ var l=2*a+1, r=l+1, m=a; if(l<open.length&&open[l].f<open[m].f) m=l; if(r<open.length&&open[r].f<open[m].f) m=r; if(m===a) break; var q=open[a]; open[a]=open[m]; open[m]=q; a=m; } } return top; }
var D8=[[1,0],[-1,0],[0,1],[0,-1],[1,1],[1,-1],[-1,1],[-1,-1]];
/* run the search for at most `ms`: null = not done yet, else {ok, pts | why, n} */
function routeRun(R,ms){ var G=R.G, C=NAV.cell, t0=Date.now(), to=R.to, from=R.from;
  while(R.open.length){ if((R.n&31)===0&&Date.now()-t0>ms) return null; var o=rPop(R); if(++R.n>NAV.max) return {ok:false, why:'too far', n:R.n};
    if(Math.abs(o.i-R.gi)<=1&&Math.abs(o.j-R.gj)<=1&&Math.abs(o.z-to.z)<.3){ var pts=[[to.x,to.y,to.z]]; for(var q=o;q;q=q.p) pts.push([q.i*C,q.j*C,q.z]); pts[pts.length-1]=[from.x,from.y,from.z]; pts.reverse(); return {ok:true, pts:smoothPath(G,pts), n:R.n}; }
    for(var d=0;d<8;d++){ var ni=o.i+D8[d][0], nj=o.j+D8[d][1], z=navCell(G,R.cache,ni,nj,o.z); if(z==null) continue;
      if(d>3&&(navCell(G,R.cache,o.i+D8[d][0],o.j,o.z)==null||navCell(G,R.cache,o.i,o.j+D8[d][1],o.z)==null)) continue;          /* no corner cutting */
      var g=o.g+(d>3?C*1.4142:C)+Math.abs(z-o.z)*.6, key=ni+','+nj+','+Math.round(z*4); if(R.seen[key]!=null&&R.seen[key]<=g) continue; R.seen[key]=g; rPush(R,{i:ni,j:nj,z:z,g:g,f:g+rH(R,ni,nj,z),p:o}); } }
  return {ok:false, why:'no way', n:R.n}; }
/* string-pulling: keep a point only when the straight walk past it would not stay on floor and clear */
function segWalk(G,a,b){ var L=Math.hypot(b[0]-a[0],b[1]-a[1]), k=Math.max(1,Math.ceil(L/.15)), z=a[2]; for(var i=1;i<=k;i++){ var t=i/k, x=a[0]+(b[0]-a[0])*t, y=a[1]+(b[1]-a[1])*t, s=supportDisc(G,x,y,z+.05);
    if(s==null||s<z-CFG.step||s>z+CFG.step||blockedAt(G,x,y,s)||Math.abs(s-(a[2]+(b[2]-a[2])*t))>.6) return false; z=s; } return true; }
function smoothPath(G,P){ var out=[P[0]], i=0; while(i<P.length-1){ var j=Math.min(P.length-1,i+40); while(j>i+1&&!segWalk(G,P[i],P[j])) j--; out.push(P[j]); i=j; } return out; }
function pathLen(P,k){ var L=0; for(var i=(k||0);i+1<P.length;i++) L+=Math.hypot(P[i+1][0]-P[i][0],P[i+1][1]-P[i][1],P[i+1][2]-P[i][2]); return L; }
/* start a trip to node `id`: walk the route when it is found and not too long (70 m), else a short, labelled fade; Esc, a move key or the pill's x cancels */
function goNode(id){ var G=S.G, d=S.data||{}, n=(d.nodes||{})[id]; if(!n||!n.r) return false; var sl=n.s&&G.slots[n.s]?n.s:(G.slots['card-'+id]?'card-'+id:null), it=sl?G.slots[sl]:null;
  S.cardIx=(d.order||Object.keys(d.nodes||{})).indexOf(id); var to=it?arrival(G,it):spawn(G,n.r,null); var name=String(n.n)+' '+dec(n.t);
  navStop(); S.plan={id:id, it:it, to:to, name:name, R:routeStart(G,{x:S.x,y:S.y,z:S.fz},to), t0:Date.now()}; S.lastRoute={mode:'planning'}; navPill(name); return true; }
/* each frame while planning: a few ms of search; then the walk (found, at most 70 m) or the fade (far, none, or taking too long) */
function navPlanStep(){ var P=S.plan; if(!P) return; var r=routeRun(P.R,NAV.frameMs); if(!r&&Date.now()-P.t0<NAV.totalMs) return; S.plan=null; if(!r) r={ok:false, why:'too long to find', n:P.R.n};
  var L=r.ok?pathLen(r.pts):0; S.lastRoute={ok:r.ok, why:r.why, n:r.n, len:L, mode:'', ms:Date.now()-P.t0};
  if(r.ok&&L<=70&&!reduced()){ S.nav={id:P.id, it:P.it, to:P.to, pts:r.pts, k:1, name:P.name, t:0, best:L, bestT:0, len:L}; S.lastRoute.mode='walk'; return; }
  S.lastRoute.mode='fade'; navFade(P.id,P.it,P.to,P.name); }
function navFade(id,it,to,name){ navPill(name,true); veilPulse(function(){ S.x=to.x; S.y=to.y; S.fz=to.z; S.yaw=to.yaw; S.pitch=to.pitch; S.snap=1; S.snapExp=1; S.snapCam=1; S.vx=S.vy=S.vz=0; S.air=false; S.glide=null; S.safe=null; navArrive(id,it,name); }, 'Going to '+name+'…'); }
function navStop(why){ if(S.nav&&why) S.lastRoute&&(S.lastRoute.stopped=why); S.plan=null; S.nav=null; S.navKeys=null; if(S.navEl&&!S.navEl._arr) S.navEl.style.opacity=0; }
function navArrive(id,it,name){ S.nav=null; S.navKeys=null; S.hiSlot=it||null; S.hiT=4.5; if(S.navEl){ S.navEl._arr=1; S.navEl.firstChild.textContent='✓ '+name; S.navEl.style.opacity=1; clearTimeout(S.navEl._t); S.navEl._t=setTimeout(function(){ if(S.navEl){ S.navEl.style.opacity=0; S.navEl._arr=0; } },2800); }
  S.lastRoute&&(S.lastRoute.arrived=true); }
function navPill(name,fade){ var p=S.navEl; if(!p) return; p._arr=0; clearTimeout(p._t); p.firstChild.textContent=(fade?'→ ':'→ ')+name; p.style.opacity=1; }
/* one frame of the guided walk: steer the walker at the next point of the route (run on long stretches), notice being stuck (then the fade), turn to the sign at the end */
function navStep(dt){ var N=S.nav; if(!N) return null; var P=N.pts; N.t+=dt;
  while(N.k<P.length-1&&Math.hypot(P[N.k][0]-S.x,P[N.k][1]-S.y)<.45&&Math.abs(P[N.k][2]-S.fz)<.6) N.k++;
  var tgt=P[N.k], rem=Math.hypot(tgt[0]-S.x,tgt[1]-S.y)+pathLen(P,N.k);
  if(rem<N.best-.25){ N.best=rem; N.bestT=N.t; } else if(N.t-N.bestT>1.6){ var to=N.to, it=N.it, id=N.id, nm=N.name; S.lastRoute&&(S.lastRoute.stuckFade=true); navStop(); navFade(id,it,to,nm); return null; }
  if(N.k===P.length-1&&Math.hypot(tgt[0]-S.x,tgt[1]-S.y)<.35){ var dy0=N.to.yaw-S.yaw; while(dy0>PI) dy0-=2*PI; while(dy0<-PI) dy0+=2*PI; S.yaw+=dy0*(1-Math.exp(-dt/.12)); S.pitch+=(N.to.pitch-S.pitch)*(1-Math.exp(-dt/.12));
    if(Math.abs(dy0)<.03){ S.yaw=N.to.yaw; navArrive(N.id,N.it,N.name); } return {}; }
  if((N.chk=(N.chk||0)+1)%6===0) while(N.k<P.length-1&&segWalk(G0(),[S.x,S.y,S.fz],P[N.k+1])) N.k++;                 /* skip ahead when a later point is in plain reach */
  tgt=P[N.k]; var want=Math.atan2(tgt[1]-S.y,tgt[0]-S.x), dyw=want-S.yaw; while(dyw>PI) dyw-=2*PI; while(dyw<-PI) dyw+=2*PI;
  S.yaw+=clamp(dyw,-3*dt,3*dt); S.pitch+=(-.1-S.pitch)*(1-Math.exp(-dt/.4));          /* the view turns after the walk, smoothly; the walk itself goes straight at the route */
  var dd=want-S.yaw; return {mf:Math.cos(dd), ms:-Math.sin(dd), run:rem>10?1:0}; }
function G0(){ return S.G; }
/* the trail ahead (a dashed glowing line on the floor) and a frame round the sign it leads to, as a batch of their own */
function navBatch(lt){ var G=S.G, N=S.nav, hi=S.hiSlot&&S.hiT>0?S.hiSlot:(N&&N.it), pts=[], gl=S.gl; if(!N&&!hi) return null;
  var quad=function(a,b,c,d,nn){ [a,b,c,a,c,d].forEach(function(v){ pts.push(v[0],v[1],v[2],nn[0],nn[1],nn[2]); }); };
  if(N){ var P=[[S.x,S.y,S.fz]].concat(N.pts.slice(N.k)); for(var i=0;i+1<P.length;i++){ var a=P[i], b=P[i+1], L=Math.hypot(b[0]-a[0],b[1]-a[1]); if(L<.01) continue; var ux=(b[0]-a[0])/L, uy=(b[1]-a[1])/L, w=.11;
      for(var u=(i?0:.8);u<L;u+=.7){ var u1=Math.min(L,u+.38), t0=u/L, t1=u1/L, x0=a[0]+ux*u, y0=a[1]+uy*u, x1=a[0]+ux*u1, y1=a[1]+uy*u1, z0=a[2]+(b[2]-a[2])*t0+.035, z1=a[2]+(b[2]-a[2])*t1+.035;
        var s0=supportAt(G,x0,y0,z0+.3), s1=supportAt(G,x1,y1,z1+.3); if(s0!=null&&Math.abs(s0+.035-z0)<.5) z0=s0+.035; if(s1!=null&&Math.abs(s1+.035-z1)<.5) z1=s1+.035;
        quad([x0+uy*w,y0-ux*w,z0],[x1+uy*w,y1-ux*w,z1],[x1-uy*w,y1+ux*w,z1],[x0-uy*w,y0+ux*w,z0],[0,0,1]); } } }          /* counter-clockwise seen from above (the other way round was culled) */
  if(hi){ var s=hi.s, c=s.p, n=hi.n, dd=[-n[1],n[0]], W=s.sz[0]/2+.08, H=s.sz[1]/2+.08, z=hi.z, fs=s.card?[1,-1]:[1], b2=.045;
    fs.forEach(function(f){ var o=f*(s.card?.06:.035), cx=c[0]+n[0]*o, cy=c[1]+n[1]*o, nn=[n[0]*f,n[1]*f,0], P2=function(a,v){ return [cx+dd[0]*a,cy+dd[1]*a,z+v]; };
      quad(P2(-W,-H),P2(W,-H),P2(W,-H+b2),P2(-W,-H+b2),nn); quad(P2(-W,H-b2),P2(W,H-b2),P2(W,H),P2(-W,H),nn); quad(P2(-W,-H),P2(-W+b2,-H),P2(-W+b2,H),P2(-W,H),nn); quad(P2(W-b2,-H),P2(W,-H),P2(W,H),P2(W-b2,H),nn); }); }
  var nv=pts.length/6; if(!nv) return null; var ab=new ArrayBuffer(nv*STRIDE), f=new Float32Array(ab), i8=new Int8Array(ab), u8=new Uint8Array(ab);
  for(var v=0;v<nv;v++){ var o=v*7, bb=v*STRIDE, q=v*6; f[o]=pts[q]; f[o+1]=pts[q+1]; f[o+2]=pts[q+2]; i8[bb+12]=Math.round(pts[q+3]*127); i8[bb+13]=Math.round(pts[q+4]*127); i8[bb+14]=Math.round(pts[q+5]*127); u8[bb+24]=255; u8[bb+25]=255; }
  if(!S.navVB) S.navVB=gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER,S.navVB); gl.bufferData(gl.ARRAY_BUFFER,ab,gl.DYNAMIC_DRAW);
  return {built:{vb:S.navVB, ranges:[{k:'navglow', m:matOf(G,'navglow'), first:0, count:nv, trans:false}]}, light:lt}; }
/* a filter on: only the cards it shows (window._altoShown, filter_panel.py); from a card it hides, the nearest shown one that way */
function stepCard(dir){ var d=S.data||{}, all=d.order||Object.keys(d.nodes||{}), on=!!(window._altoFilterOn&&window._altoFilterOn()), L=all.length;
  var ok=function(id){ var n=(d.nodes||{})[id]; return !!(n&&n.r) && (!on||!window._altoShown||window._altoShown(id)); };
  var c=S.cardIx==null?-1:S.cardIx, placed=c>=0&&!!((d.nodes||{})[all[c]]||{}).r, i=(c<0||(!on&&!placed))?(dir>0?0:L-1):c+dir;
  for(var k=0;k<L;k++,i+=dir){ var j=((i%L)+L)%L; if(ok(all[j])){ goNode(all[j]); return; } } }
function toggleCards(){ if(S.cp){ S.cp.remove(); S.cp=null; return; } var d=S.data||{}, ns=d.nodes||{}, ord=d.order||Object.keys(ns), p=S.cp=el('div','bf-cards',S.root), inp=el('input',null,p), list=el('div','bf-clist',p); inp.placeholder='Find a card'; inp.setAttribute('aria-label','Find a card');
  var fill=function(q){ while(list.firstChild) list.removeChild(list.firstChild); ord.forEach(function(id){ var n=ns[id]; if(!n||!n.r) return; var t=dec(n.t); if(q&&(n.n+' '+t).toLowerCase().indexOf(q)<0) return;
      var b=el('button',null,list), sw=el('i',null,b), ac=d.acts&&d.acts[n.a]; b.type='button'; if(ac&&ac.c) sw.style.background=ac.c; el('b',null,b,String(n.n)); b.appendChild(D.createTextNode(t)); b.addEventListener('click',function(e){ e.stopPropagation(); goNode(id); toggleCards(); }); }); };
  fill(''); inp.addEventListener('input',function(){ fill(inp.value.toLowerCase()); }); inp.addEventListener('keydown',function(e){ e.stopPropagation(); if(e.key==='Escape'){ toggleCards(); } }); p.addEventListener('pointerdown',function(e){ e.stopPropagation(); }); setTimeout(function(){ inp.focus(); },30); }
function mountHud(){ var css=D.getElementById('bf-css'); if(!css){ css=el('style'); css.id='bf-css'; css.textContent=BF_CSS; (D.head||D.documentElement).appendChild(css); }
  var root=S.root=el('div',null,D.body); root.id='bf-root'; root.setAttribute('role','application'); root.setAttribute('aria-label','First-person view of '+dec(S.G.plan.name||'the building'));
  var cv=S.cv=el('canvas',null,root); S.ret_=el('div','bf-ret',root); S.pk=el('div','bf-pill bf-pick',root); S.toast=el('div','bf-pill bf-toast',root);
  S.lvBox=el('div','bf-lv',root); S.G.lvs.forEach(function(l){ var b=el('button',null,S.lvBox,dec(l.lb)); b.type='button'; b.setAttribute('aria-label','Go to '+dec(l.n)); b.setAttribute('data-lv',l.id); b.addEventListener('click',function(e){ e.stopPropagation(); var i=S.G.lvs.indexOf(levelAt(S.fz)), j=S.G.lvs.indexOf(l); if(j!==i) goLevel(j>i?1:-1); }); });
  var ex=el('button','bf-exit',root,'Blueprint · Esc'); ex.type='button'; ex.addEventListener('click',function(e){ e.stopPropagation(); exit(); });
  var cbn=el('button','bf-cardsbtn',root,'Cards \u00b7 C'); cbn.type='button'; cbn.addEventListener('click',function(e){ e.stopPropagation(); toggleCards(); });
  var ob=el('div','bf-opts',root); S.viewBtn=el('button',null,ob,''); S.viewBtn.type='button'; S.viewBtn.addEventListener('click',function(e){ e.stopPropagation(); setView(S.view==='third'?'first':'third'); });
  S.avBtn=el('button',null,ob,''); S.avBtn.type='button'; S.avBtn.addEventListener('click',function(e){ e.stopPropagation(); setAvatar(S.av&&S.av.mayor?'generic':'mayor'); });
  S.tagEl=el('div','bf-tag',root,''); S.navEl=el('div','bf-pill bf-nav',root); el('span',null,S.navEl,''); var nx=el('button',null,S.navEl,'\u2715'); nx.type='button'; nx.setAttribute('aria-label','Cancel'); nx.title='Cancel (Esc)'; nx.addEventListener('click',function(e){ e.stopPropagation(); navStop('cancelled'); if(S.navEl) S.navEl.style.opacity=0; }); S.hopBtn=el('button','bf-hop',root,'Hop'); S.hopBtn.type='button'; S.hopBtn.setAttribute('aria-label','Hop');
  S.hopBtn.addEventListener('pointerdown',function(e){ e.stopPropagation(); e.preventDefault(); S.keys.hop=1; }); ['pointerup','pointercancel','pointerleave'].forEach(function(t){ S.hopBtn.addEventListener(t,function(e){ e.stopPropagation(); S.keys.hop=0; }); });
  S.hint=el('div','bf-pill bf-hint',root,'W A S D move \u00b7 Space hop \u00b7 T first / third person \u00b7 drag to look \u00b7 Shift run \u00b7 C cards \u00b7 N / P next / previous card \u00b7 [ ] floors \u00b7 E open \u00b7 Esc blueprint');
  S.jl=el('div','bf-joy bf-jl',root); el('i',null,S.jl); S.jr=el('div','bf-joy bf-jr',root); el('i',null,S.jr);
  var cr=(S.G.plan.src||[]).map(function(x){ return x&&x.cr; }).filter(Boolean); if(cr.length){ var ce=el('div','bf-credit',root,cr.map(dec).join(' \u00b7 ')); ce.title=ce.textContent; }
  S.veil=el('div','bf-veil',root,'Walking in…'); if(q().bldgperf==='1') S.perf=el('div','bf-pill bf-perf',root);
  if(matchMedia&&matchMedia('(pointer:coarse)').matches) root.classList.add('bf-touch');
  S.pk.addEventListener('click',function(e){ e.stopPropagation(); act(S.hover); });
  cv.addEventListener('pointerdown',function(e){ if(e.button>0) return; if(joyHit(e)) return; S.drag={id:e.pointerId,x:e.clientX,y:e.clientY,mv:0}; try{ cv.setPointerCapture(e.pointerId); }catch(x){} root.classList.add('bf-drag'); e.preventDefault(); });
  cv.addEventListener('pointermove',function(e){ var d=S.drag; if(joyMove(e)) return; if(!d||d.id!==e.pointerId){ S.mouse=[e.clientX,e.clientY]; return; } var mx=e.clientX-d.x, my=e.clientY-d.y; d.mv+=Math.abs(mx)+Math.abs(my);
    S.yaw+=mx*CFG.lookX; S.pitch=clamp(S.pitch+my*CFG.lookY,-CFG.pitchMax,CFG.pitchMax); d.x=e.clientX; d.y=e.clientY; });
  var up=function(e){ if(joyUp(e)) return; var d=S.drag; if(d&&d.id===e.pointerId){ S.drag=null; root.classList.remove('bf-drag'); try{ cv.releasePointerCapture(e.pointerId); }catch(x){} if(e.type==='pointerup'&&d.mv<6){ var r=S.root.getBoundingClientRect(), h=pickNow(e.clientX-r.left,e.clientY-r.top); if(h) act(h); } } };
  cv.addEventListener('pointerup',up); cv.addEventListener('pointercancel',up);
  [S.jl,S.jr].forEach(function(j){ j.addEventListener('pointerdown',function(e){ e.stopPropagation(); e.preventDefault(); var r=j.getBoundingClientRect(); (j===S.jl?S:S).joy=(S.joy||{}); S.joy[e.pointerId]={el:j,cx:r.left+r.width/2,cy:r.top+r.height/2}; try{ j.setPointerCapture(e.pointerId); }catch(x){} joyMove(e); });
    j.addEventListener('pointermove',function(e){ joyMove(e); }); j.addEventListener('pointerup',function(e){ joyUp(e); }); j.addEventListener('pointercancel',function(e){ joyUp(e); }); });
  S.onKey=function(e){ if(!S.on||S.paused) return; var t=e.target; if(t&&(t.tagName==='INPUT'||t.tagName==='TEXTAREA'||t.isContentEditable)) return; var down=e.type==='keydown', k=e.key, c=e.code, n=null;
    if(c==='KeyW'||k==='ArrowUp'||k==='w'||k==='W') n='f'; else if(c==='KeyS'||k==='ArrowDown'||k==='s'||k==='S') n='b'; else if(c==='KeyA'||k==='a'||k==='A') n='l'; else if(c==='KeyD'||k==='d'||k==='D') n='r';
    else if(k==='ArrowLeft') n='tl'; else if(k==='ArrowRight') n='tr'; else if(k==='Shift') n='run'; else if(k===' '||c==='Space') n='hop';
    if(n){ S.keys[n]=down?1:0; e.preventDefault(); e.stopPropagation(); return; }
    if(!down) return;
    if(k==='Escape'){ e.preventDefault(); e.stopPropagation(); if(S.nav||S.plan){ navStop('cancelled'); return; } exit(); return; }
    if(k===']'||k==='PageUp'){ e.preventDefault(); goLevel(1); return; } if(k==='['||k==='PageDown'){ e.preventDefault(); goLevel(-1); return; }
    if((k==='t'||k==='T')&&!e.repeat){ e.preventDefault(); setView(S.view==='third'?'first':'third'); return; }
    if(k==='c'||k==='C'){ e.preventDefault(); toggleCards(); return; } if(k==='n'||k==='N'){ e.preventDefault(); stepCard(1); return; } if(k==='p'||k==='P'){ e.preventDefault(); stepCard(-1); return; }
    if(k==='e'||k==='E'||k==='Enter'){ e.preventDefault(); act(S.hover); } };
  window.addEventListener('keydown',S.onKey,true); window.addEventListener('keyup',S.onKey,true);
  S.onBlur=function(){ S.keys={}; }; window.addEventListener('blur',S.onBlur);
  S.onResize=function(){ size(); }; window.addEventListener('resize',S.onResize);
  cv.addEventListener('webglcontextlost',function(e){ if(e.target!==S.cv||!S.on) return; e.preventDefault(); S.lost=1; },false);
  cv.addEventListener('webglcontextrestored',function(e){ if(e.target!==S.cv) return; S.lost=0; var T=S.T; if(T&&T.name==='high'&&T.fx&&(T.fx.real||T.fx.ao)){ T.name='medium'; T.fx=fxFor('medium',T.probe); S.down=(S.down||0)+1; }      /* a GPU that lost the context under the high pass comes back one tier down */
    try{ glSetup(); S.fb=null; S.rt=null; S.G.batches.forEach(function(b){ b.built=null; b.atlas=null; b.imgs=null; }); S.bytes=0; }catch(x){} },false); }
function joyHit(e){ return false; }
function joyMove(e){ var J=S.joy&&S.joy[e.pointerId]; if(!J) return false; var dx=(e.clientX-J.cx)/50, dy=(e.clientY-J.cy)/50, l=Math.hypot(dx,dy); if(l>1){ dx/=l; dy/=l; } J.el.firstChild.style.transform='translate('+(dx*34)+'px,'+(dy*34)+'px)';
  if(J.el===S.jl) S.joyL=[dx,dy]; else S.joyR=[dx,dy]; return true; }
function joyUp(e){ var J=S.joy&&S.joy[e.pointerId]; if(!J) return false; J.el.firstChild.style.transform=''; if(J.el===S.jl) S.joyL=null; else S.joyR=null; delete S.joy[e.pointerId]; return true; }
function size(){ if(!S.root) return; var w=S.root.clientWidth||innerWidth, h=S.root.clientHeight||innerHeight, dpr=window.devicePixelRatio||1, T=S.T;
  if(!S.gov){ var s0=Math.max(1,Math.min(Math.min(dpr,T.scaleHi),Math.sqrt(2.6e6/Math.max(1,w*h)))); S.gov=govNew(1,Math.max(1,Math.min(dpr,T.scaleHi)),Math.round(s0*4)/4); if(navigator.webdriver||q().bldgscale) S.gov.pin=1; if(+q().bldgscale) S.gov.s=+q().bldgscale; }
  var per=(T.samples&&T.wgl2?T.samples*8+8:8), cap=Math.sqrt(100e6/per/Math.max(1,w*h));      /* colour+depth samples, the resolve and the canvas: <= ~100 MB */
  if(S.gov.hi>cap){ S.gov.hi=Math.max(S.gov.lo,Math.floor(cap*4)/4); S.gov.ceil=Math.min(S.gov.ceil,S.gov.hi); } if(S.gov.s>cap) S.gov.s=Math.max(Math.min(1,cap),Math.floor(cap*4)/4);
  var s=S.gov.s, cw=Math.max(1,Math.round(w*s)), ch=Math.max(1,Math.round(h*s)); if(S.cv.width!==cw||S.cv.height!==ch){ S.cv.width=cw; S.cv.height=ch; } S.cw=cw; S.ch=ch; }
/* the resolution governor (palace_ride_gfx.py's, ported): 0.25 steps, down on slow windows, up after 3 s of good ones, no oscillation */
function govNew(lo,hi,s){ return {lo:lo, hi:hi, s:Math.min(hi,Math.max(lo,s)), ceil:hi, buf:[], tChange:-1e9, tUp:-1e9, good:0, step:.25}; }
function gov(g,dt,now){ if(g.pin) return ''; if(!(dt>3)||dt>100){ g.buf.length=0; g.good=now; return ''; } g.buf.push(dt); if(g.buf.length<24) return '';
  var a=g.buf.slice().sort(function(p,c){ return p-c; }), p75=a[Math.floor(a.length*.75)], p90=a[Math.floor(a.length*.9)], mean=0; a.forEach(function(v){ mean+=v/a.length; }); g.buf.length=0;
  if(p75>19.5||mean>19){ g.good=now; if(g.s<=g.lo+1e-6) return 'floor'; if(now-g.tUp<4000) g.ceil=Math.max(g.lo,g.s-g.step); g.s=Math.max(g.lo,g.s-g.step); g.tChange=now; return 'down'; }
  if(p90>18.2){ g.good=now; return ''; }
  if(now-g.good>=3000&&now-g.tChange>=3000&&g.s+g.step<=Math.min(g.hi,g.ceil)+1e-6){ g.s=Math.min(g.hi,g.ceil,g.s+g.step); g.tChange=now; g.tUp=now; g.good=now; return 'up'; } return ''; }
function hud(now){ var cw=S.root.clientWidth, ch=S.root.clientHeight;
  if(!S.pkT||now-S.pkT>90){ S.pkT=now; S.hover=pickNow(cw/2,ch/2); var d=describe(S.hover); S.ret_.classList.toggle('on',!!(S.hover&&d));
    var txt=d?d.text:''; if(txt!==S.pkTxt){ S.pkTxt=txt; while(S.pk.firstChild) S.pk.removeChild(S.pk.firstChild); if(d){ if(d.node||d.lift) el('kbd',null,S.pk,'E'); S.pk.appendChild(D.createTextNode(txt)); } } S.pk.classList.toggle('on',!!d); }
  var r=S.room, sig=r?r.id:(S.fz>S.G.gz+.5?'?':'out'); if(sig!==S.roomSig){ S.roomSig=sig; while(S.toast.firstChild) S.toast.removeChild(S.toast.firstChild);
    if(r){ S.toast.appendChild(D.createTextNode(dec(r.name))); el('span',null,S.toast,[r.no?(/^\d/.test(r.no)?'Gallery '+r.no:r.no):'',dec(r.l.n)].filter(Boolean).join(' · ')); }
    else S.toast.appendChild(D.createTextNode(sig==='out'?dec(S.G.plan.name||'Outside'):'On the stairs'));
    S.toast.classList.add('on'); clearTimeout(S.toastT); S.toastT=setTimeout(function(){ if(S.toast) S.toast.classList.remove('on'); },2600); }
  var lv=levelAt(S.fz); [].forEach.call(S.lvBox.children,function(b){ b.classList.toggle('on',b.getAttribute('data-lv')===lv.id); });
  if(!S.posT||now-S.posT>250){ S.posT=now; emitPos('alto-building-fpv-pos'); }
  if(S.perf&&(!S.perfT||now-S.perfT>500)){ S.perfT=now; var a=(S.iv||[]).slice().sort(function(p,c){ return p-c; }), n=a.length, st=S.stats||{};
    S.perf.textContent='tier '+S.T.name+(S.T.wgl2?' webgl2':' webgl1')+(S.fb?' msaa'+S.fb.s:'')+'\nscale '+S.gov.s.toFixed(2)+' '+S.cw+'x'+S.ch+'\nframe p50 '+(n?a[n>>1].toFixed(1):'-')+' p95 '+(n?a[Math.floor(n*.95)].toFixed(1):'-')+' ms\ndraws '+st.draws+' tris '+Math.round((st.tris||0)/1000)+'k batches '+st.batches+'\nbuilt '+S.G.batches.filter(function(b){ return b.built; }).length+'/'+S.G.batches.length+' '+(S.bytes/1e6).toFixed(1)+' MB'
      +'\nfx '+(S.T.fx.soft?'soft'+S.T.fx.soft+' ':'')+(S.post&&S.post.ok?(S.post.o.ao?'ao'+S.post.o.ao+' ':'')+(S.post.o.bloom?'bloom ':''):'')+(S.env?'sky ':'')+API.fx().real+' sets'+(FXG.err?' ('+FXG.err+')':''); } }
function emitPos(type){ var d={l:levelAt(S.fz).id, x:Math.round(S.x*100)/100, y:Math.round(S.y*100)/100, yaw:Math.round(S.yaw*180/PI), room:S.room?S.room.id:null, z:Math.round(S.fz*100)/100};
  S.lastPos=d; try{ window.dispatchEvent(new CustomEvent(type,{detail:d})); }catch(x){} }
function veilPulse(fn,label){ if(reduced()||!S.veil){ fn(); return; } S.veil.textContent=label||''; S.veil.style.opacity=1; setTimeout(function(){ fn(); setTimeout(function(){ if(S.veil) S.veil.style.opacity=0; },60); },260); }
function loop(t){ if(!S.on||S.paused) return; S.raf=requestAnimationFrame(loop); var now=performance.now(), dt=S.last?(now-S.last)/1000:1/60; S.last=now;
  if(dt*1000<1000){ (S.iv||(S.iv=[])).push(dt*1000); if(S.iv.length>240) S.iv.shift(); }
  var r=S.gov?gov(S.gov,dt*1000,now):''; if(r==='up'||r==='down') size(); else if(r==='floor') fxDown();
  step(dt); render(); hud(now); }

/* ── enter / exit ── */
function spawn(G,roomId,ctx){ var it=ctx&&ctx.slot?G.slots[ctx.slot]:null, r=G.rid[roomId]||null;
  if(it){ var ap=arrival(G,it); S.hiSlot=it; S.hiT=4.5; return ap; }
  if(r){ var c=freeNear(r.ctr[0],r.ctr[1],r.l.e), best=0, by=0; for(var a=0;a<16;a++){ var t=a/16*2*PI, L=sight(G,c[0],c[1],r.l.e,t,40); var sl=r.items.some(function(x){ return x.t==='slot'&&Math.abs(Math.atan2(x.s.p[1]-c[1],x.s.p[0]-c[0])-t)<.3; }); if(L+(sl?4:0)>best){ best=L+(sl?4:0); by=t; } }
    return {x:c[0],y:c[1],z:r.l.e,yaw:by,pitch:-.03}; }
  var sp0=G.plan.sp; if(sp0&&!(ctx&&ctx.outside)&&sp0.p&&G.lv[sp0.l]){ var zs=G.lv[sp0.l].e; return {x:sp0.p[0],y:sp0.p[1],z:zs,yaw:(sp0.yaw||0)*PI/180,pitch:sp0.pitch!=null?sp0.pitch:-.02}; }
  var en=(G.plan.en||[]).filter(function(e){ return (e.k||'main')==='main'; })[0]||(G.plan.en||[])[0];
  if(en){ var fc=(en.fc||0)*PI/180, ux=Math.cos(fc), uy=Math.sin(fc), dd=6, ex=G.plan.ex||{};
    [].concat(ex.stp||[],ex.tr||[]).forEach(function(s){ (s.p||[]).forEach(function(p){ var u=(p[0]-en.p[0])*ux+(p[1]-en.p[1])*uy; if(u>dd-4) dd=Math.min(40,u+4); }); });
    var x=en.p[0]+ux*dd, y=en.p[1]+uy*dd, z=supportAt(G,x,y,1e3); if(z==null) z=G.gz; return {x:x,y:y,z:z,yaw:fc+PI,pitch:.04}; }
  var r0=G.rooms[0]; if(r0) return spawn(G,r0.id,null); return {x:0,y:0,z:0,yaw:0,pitch:0}; }
function sight(G,x,y,z,a,max){ var dx=Math.cos(a), dy=Math.sin(a); for(var s=.3;s<max;s+=.3){ if(blockedAt(G,x+dx*s,y+dy*s,z)) return s; } return max; }
function enter(roomId,ctx){ ctx=ctx||{}; var A=window.AltoBuilding, plan=ctx.plan||(A&&A.plan); if(!plan) return false;
  if(S.on) exit(true);
  S.data=ctx.data||(A&&A.data)||{}; S.mc={};
  try{ S.G=bfIndex(plan); addCards(S.G); }catch(e){ if(window.console) console.warn('bldg fpv index',e); return false; }
  var geo=plan.geo||{}, north=(geo.north||0)*PI/180, bear=215*PI/180-north, el2=36*PI/180; S.sun=nrm([Math.cos(el2)*Math.sin(bear),Math.cos(el2)*Math.cos(bear),Math.sin(el2)]);
  S.sunC=[6.2,5.5,4.5]; S.sky=[1.9,2.25,2.8];
  S.lost=0; S.rt=null; S.noRefl=0; S.abytes=0; S.keys={}; S.vx=S.vy=S.vz=0; S.frame=0; S.built=0; S.last=0; S.iv=[]; S.roomSig=null; S.pkTxt=null; S.gov=null; S.fb=null; S.glide=null; S.safe=null; S.air=false; S.grounded=true; S.vz=0; S.dip=0; S.hopBuf=0; S.hopHeld=false; S.camD=null; S.av=null; S.avVB=null; S.avAB=null; S.nav=null; S.navVB=null; S.hiSlot=null; S.hiT=0;
  mountHud(); setAvatar(AV.pref('avatar')); setView(AV.pref('view')); var gl=glInit(S.cv); if(!gl){ unmount(); return false; }
  try{ glSetup(); }catch(e){ if(window.console) console.warn('bldg fpv gl',e); unmount(); return false; }
  var sp=spawn(S.G,roomId,ctx); S.x=sp.x; S.y=sp.y; S.fz=sp.z; S.ez=sp.z+CFG.eye; S.yaw=sp.yaw; S.pitch=sp.pitch; S.snap=1; S.snapExp=1; S.exp=1;
  S.on=true; S.paused=false; size(); step(0); S.settling=1; if(S.sm){ S.G.batches.forEach(function(b){ if(b.kind!=='room'&&!b.built) upload(S.G,b); }); } try{ render(); render(); }catch(e){ if(window.console) console.warn('bldg fpv render',e); } S.settling=0;
  setTimeout(function(){ if(S.veil){ S.veil.style.opacity=0; S.veil.textContent=''; } },60); setTimeout(function(){ if(S.hint) S.hint.style.opacity=0; },9000);
  S.raf=requestAnimationFrame(loop); emitPos('alto-building-fpv-pos'); return true; }
function exit(silent){ if(!S.on) return; emitPos('alto-building-fpv-exit'); S.on=false; cancelAnimationFrame(S.raf); S.raf=0; if(S.mo){ S.mo.disconnect(); S.mo=null; }
  var gl=S.gl; if(gl&&S.G){ S.G.batches.forEach(drop); for(var g in S.tex){ gl.deleteTexture(S.tex[g][0]); gl.deleteTexture(S.tex[g][1]); } freeTarget(gl,S.fb); if(S.rt){ gl.deleteTexture(S.rt.tx); gl.deleteRenderbuffer(S.rt.rb); gl.deleteFramebuffer(S.rt.fb); S.rt=null; } if(S.sm){ gl.deleteTexture(S.sm.tx); gl.deleteRenderbuffer(S.sm.rb); gl.deleteFramebuffer(S.sm.fb); S.sm=null; } try{ var lx=gl.getExtension('WEBGL_lose_context'); if(lx) lx.loseContext(); }catch(x){} }
  if(gl&&S.avVB){ gl.deleteBuffer(S.avVB); S.avVB=null; } if(gl&&S.navVB){ gl.deleteBuffer(S.navVB); S.navVB=null; } S.nav=null; unmount(); var pos=S.lastPos; S.gl=null; S.G=null; S.tex={}; S.fb=null;
  if(!silent){ try{ var A=window.AltoBuilding; if(A){ A.show(); if(pos&&A.showWalker) A.showWalker(pos); } }catch(x){} } }
function unmount(){ window.removeEventListener('keydown',S.onKey,true); window.removeEventListener('keyup',S.onKey,true); window.removeEventListener('blur',S.onBlur); window.removeEventListener('resize',S.onResize); if(S.root){ S.root.remove(); S.root=null; } }

var API={version:1, enter:enter, exit:function(){ exit(); },
  state:function(){ return S.G?{x:S.x, y:S.y, z:S.fz, eye:S.ez, yaw:S.yaw, pitch:S.pitch, air:!!S.air, vz:S.vz, hops:S.hops||0, bonks:S.bonks||0, nets:S.nets||0, rescues:S.rescues||0, view:S.view, avatar:S.av?{mayor:S.av.mayor, tag:AV.tag(S.av).text, city:S.av.city&&S.av.city.id}:null, cam:S.camE||null, camD:S.camD, room:S.room?S.room.id:null, level:levelAt(S.fz).id, tier:S.T.name, wgl2:S.T.wgl2, exp:S.exp, on:S.on}:null; },
  place:function(x,y,z,yaw,pitch){ S.safe=null; S.x=x; S.y=y; if(z!=null) S.fz=z; else { var s=supportAt(S.G,x,y,1e3); S.fz=s==null?S.fz:s; } if(yaw!=null) S.yaw=yaw; if(pitch!=null) S.pitch=clamp(pitch,-CFG.pitchMax,CFG.pitchMax); S.snap=1; S.snapExp=1; S.vx=S.vy=0; step(0); },
  step:function(dt,keys,n){ for(var i=0;i<(n||1);i++) step(dt,keys); }, look:function(yaw,pitch){ if(yaw!=null) S.yaw=yaw; if(pitch!=null) S.pitch=clamp(pitch,-CFG.pitchMax,CFG.pitchMax); },
  settle:function(){ S.settling=1; S.snapExp=1; render(); render(); S.settling=0; hud(performance.now()+1e4); return API.stats(); },
  fx:function(){ var T=S.T||{}, n=0, k; for(k in (S.real||{})) if(S.real[k].st===1) n++; return {tier:T.name, fx:T.fx, real:n, env:!!S.env, post:!!(S.post&&S.post.ok), err:FXG.err, down:S.down||0, fmt:S.gl?FXG.fmt(S.gl).n:'', pending:FXG.pending(), loads:FXG.loads}; },
  stats:function(){ var st=S.stats||{}; return {draws:st.draws, tris:st.tris, batches:st.batches, built:S.G?S.G.batches.filter(function(b){ return b.built; }).length:0, total:S.G?S.G.batches.length:0, mb:S.bytes/1e6, texMb:S.texBytes/1e6, artMb:(S.abytes||0)/1e6, tier:S.T&&S.T.name, samples:S.fb?S.fb.s:0, w:S.cw, h:S.ch}; },
  timeFrames:function(n){ var gl=S.gl, t0=performance.now(); for(var i=0;i<n;i++){ render(); } var px=new Uint8Array(4); gl.readPixels(0,0,1,1,gl.RGBA,gl.UNSIGNED_BYTE,px); return (performance.now()-t0)/n; },
  pick:function(){ var h=pickNow(S.root.clientWidth/2,S.root.clientHeight/2), d=describe(h); return d?{text:d.text, node:d.node||null, kind:h?h.k:'room'}:null; },
  act:function(){ act(S.hover||pickNow(S.root.clientWidth/2,S.root.clientHeight/2)); }, level:function(d){ return goLevel(d); },
  geom:{ index:bfIndex, support:function(x,y,z){ return supportAt(S.G,x,y,z); }, supports:function(x,y){ return supports(S.G,x,y); }, ceil:function(x,y,z){ return ceilAt(S.G,x,y,z); }, onStair:function(x,y){ return onStair(S.G,x,y); }, segD:segD, ok:function(x,y){ return {ledge:ledge(S.G,x,y), surf:blockedBySurf(x,y), prim:blockedAt(S.G,x,y,colZ())}; }, blocked:function(x,y,z){ return blockedAt(S.G,x,y,z); }, flightZ:flightZ,
    wallPieces:function(G,wid){ var W=G.walls.filter(function(w){ return w.w.id===wid; })[0]; if(!W) return null; var out={faces:[], ops:W.ops.map(function(o){ return {k:o.k, a0:o.a0, a1:o.a1, z0:o.z0, z1:o.z1, pass:o.pass, ra:o.ra?o.ra.id:null, rb:o.rb?o.rb.id:null}; }), prims:[]};
      G.batches.forEach(function(b){ b.items.forEach(function(f){ if(f.t==='face'&&f.W===W) out.faces.push({room:f.room?f.room.id:null, s:f.s, u0:f.u0+f.sg.s0, u1:f.u1+f.sg.s0, fb:f.fb, ft:f.ft}); }); });
      return out; },
    build:function(G,i){ var mb=buildBatch(G,G.batches[i]), o={}; mb.order.forEach(function(k){ o[k]=mb.k[k].n/3; }); return o; },
    /* the material keys of every opaque triangle that passes within tol of the point (x,y,z) and faces along n (tests: is an opening really cut?) */
    covered:function(x,y,z,n,tol){ var G=S.G, hits=[]; tol=tol||.02; G.batches.forEach(function(b){ var mb=buildBatch(G,b); mb.order.forEach(function(k){ var m=matOf(G,k); if(m.trans) return; var B=mb.k[k], f=B.f;
        for(var t=0;t<B.n;t+=3){ var P=[0,1,2].map(function(j){ var o=(t+j)*7; return [f[o],f[o+1],f[o+2]]; }), g=nrm(cross(sub(P[1],P[0]),sub(P[2],P[0])));
          if(n&&Math.abs(dot(g,n))<.9) continue; var d=dot(sub([x,y,z],P[0]),g); if(Math.abs(d)>tol) continue; var q=[x-g[0]*d,y-g[1]*d,z-g[2]*d], ok=true;
          for(var e=0;e<3;e++){ var A=P[e], B2=P[(e+1)%3]; if(dot(cross(sub(B2,A),sub(q,A)),g)<-1e-7){ ok=false; break; } } if(ok) hits.push(k); } }); }); return hits; } } };
API._debug=function(){ return S; };
API.camProbe=function(){ S.av=S.av||AV.make(AV.city('',39.97,-75.18),'mayor'); S.view='third'; S.camD=null; S.camWhy=''; var cp=Math.cos(S.pitch), e=camEye([Math.cos(S.yaw)*cp,Math.sin(S.yaw)*cp,Math.sin(S.pitch)]); return {cam:e, d:S.camD, why:S.camWhy}; };
API.go=function(id){ return goNode(id); }; API.routeTo=function(id){ var it=S.G.slots['card-'+id]; if(!it) return null; var to=arrival(S.G,it), r=routeRun(routeStart(S.G,{x:S.x,y:S.y,z:S.fz},to),1e9); return {ok:r.ok, why:r.why, len:r.ok?pathLen(r.pts):0, n:r.n}; }; API.nav=function(){ return {on:!!(S.nav||S.plan), k:S.nav?S.nav.k:0, n:S.nav?S.nav.pts.length:0, last:S.lastRoute||null, hi:!!(S.hiSlot&&S.hiT>0)}; }; API.arrival=function(slot){ var it=S.G.slots[slot]; return it?arrival(S.G,it):null; };
API.view=function(v){ if(v) setView(v); return S.view; }; API.avatar=function(w){ if(w) setAvatar(w); return S.av?{mayor:S.av.mayor, tag:AV.tag(S.av)}:null; }; API.AV=AV; API.CFG=CFG;
/* headless walking (tests in node, no GL, no page): the plan indexed, the walker placed, step() as in the view */
API.sim=function(plan,data){ S.data=data||{}; S.mc={}; S.G=bfIndex(plan); if(data) addCards(S.G); S.keys={}; S.vx=S.vy=S.vz=0; S.air=false; S.grounded=true; S.dip=0; S.safe=null; S.glide=null; S.noPad=1; S.hops=S.bonks=S.nets=S.rescues=0;
  var sp=spawn(S.G,null,{}); S.x=sp.x; S.y=sp.y; S.fz=sp.z; S.ez=sp.z+CFG.eye; S.yaw=sp.yaw; S.pitch=0; S.room=locate(); return S.G; };
window.AltoBuildingFPV=API;
function reg(){ if(window.AltoBuilding&&AltoBuilding.registerFPV) AltoBuilding.registerFPV({enter:function(id,ctx){ return enter(id,ctx); }, exit:function(){ exit(); }}); }
reg();
})();
"""


from .fpv_avatar import avatar_js  # noqa: E402  (the hop, the avatar, the gamepad: shared with the city roam)


def _js() -> str:
    js = FPV_JS
    for key, src in (("__TEXGEN__", _GLSL_TEXGEN), ("__QUADVS__", _GLSL_QUAD_VS), ("__SKYFS__", _GLSL_SKY), ("__WVS__", _GLSL_WORLD_VS), ("__WFS__", _GLSL_WORLD_FS),
                     ("__DVS__", _GLSL_DEPTH_VS), ("__DFS__", _GLSL_DEPTH_FS)):
        js = js.replace(key, _json.dumps(src))
    return js.replace("__AVATAR__", avatar_js()).replace("__FXG__", _gfx_js())


FPV_ASSET = "(function(){\nvar BF_CSS=" + _json.dumps(FPV_CSS) + ";\n" + _js() + "\n})();\n"
FPV_V = _hashlib.sha256(FPV_ASSET.encode("utf-8")).hexdigest()[:10]
FPV_PATH = f"/bldg/palace-building-fpv-{FPV_V}.js"


def fpv_asset() -> tuple[str, str]:
    """(file name under /bldg/, the script) for the site."""
    return FPV_PATH.rsplit("/", 1)[1], FPV_ASSET
