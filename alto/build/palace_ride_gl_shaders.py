"""GLSL (WebGL1, GLSL ES 1.00) for the first-person city renderer (palace_ride_gl.py).

World program: every surface of the city (buildings, ground, way, landmark and scenery meshes, movers) in one fragment shader that picks the material by id
(palace_ride_mesh.py MAT + the GL-only ids below).  Vertex layout (15 floats): x y z | nx ny nz | u v | pk tint | dr dg db | H L
  pk   = mat + 64*bias + 256*aux   (bias 0..3: depth bias toward the eye for decals laid on the ground, aux: 1 = a node building)
  dr.. = the district hue (1,1,1 = none)    H = height of the building this wall belongs to (m, 0 = unknown)    L = the wall's length (m)
GL-only material ids: 40 marking, 41 ballast+ties, 42 rail, 43 roadway (lane lines), 44 portal glow, 45 curb, 46 lot, 47 plain concrete, 48 crosswalk
"""

SH_COMMON = r"""
precision highp float;
uniform vec3 uEye; uniform vec3 uSun; uniform vec3 uSunCol; uniform vec3 uSkyA; uniform vec3 uGndA; uniform vec3 uZen; uniform vec3 uHor; uniform vec3 uFog;
uniform float uFogD; uniform float uNight; uniform float uTime; uniform float uPix; uniform float uExp;
uniform sampler2D uNz;
const float UMc=1.3;
float h11(float x){ return fract(sin(x*12.9898+1.234)*43758.5453); }
float h21(vec2 p){ return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
float nz(vec2 p){ return texture2D(uNz,p*(1./64.)).r; }
vec3 nz3(vec2 p){ return texture2D(uNz,p*(1./64.)).rgb; }
vec3 skyAt(vec3 d){
  float h=clamp(d.z,0.,1.);
  vec3 c=mix(uHor,uZen,pow(h,.5));
  float sd=max(dot(d,uSun),0.);
  float day=1.-uNight;
  c+=uSunCol*(pow(sd,6.)*.10+pow(sd,60.)*.16)*(.35+.65*day);
  c+=uSunCol*smoothstep(.99955,.99985,sd)*(day*6.+uNight*1.6);
  return c; }
vec3 aces(vec3 x){ vec3 c=clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14),0.,1.); float l=dot(c,vec3(.2126,.7152,.0722)); return clamp(mix(vec3(l),c,1.14),0.,1.); }
"""

VS_WORLD = r"""
attribute vec3 aP; attribute vec3 aN; attribute vec2 aUV; attribute vec2 aMT; attribute vec3 aDC; attribute vec2 aHA; attribute vec4 aI; attribute vec2 aT2;
uniform mat4 uVP; uniform vec3 uEye; uniform float uInst; uniform mat4 uLP; uniform mat4 uLQ; uniform vec2 uNOff;
varying vec3 vP; varying vec3 vN; varying vec2 vUV; varying vec4 vM; varying vec3 vDC; varying vec2 vHA; varying vec3 vSL; varying vec3 vSQ; varying float vFade;
void main(){
  float pk=aMT.x; float aux=floor(pk/256.); float r=pk-aux*256.; float bias=floor(r/64.); float id=r-bias*64.;
  vec3 p=aP; vec3 n=aN; float tint=aMT.y;
  if(uInst>.5){ float c=cos(aI.w); float s=sin(aI.w); p=vec3(c*aP.x-s*aP.y, s*aP.x+c*aP.y, aP.z)+aI.xyz; n=vec3(c*aN.x-s*aN.y, s*aN.x+c*aN.y, aN.z); if(aT2.x>=0.) tint=aT2.x; }
  vFade=1.; if(uInst>.5 && aT2.y>0.){ float dm=length(aI.xyz-uEye)/aT2.y; vFade=1.-smoothstep(.74,.98,dm); }
  vP=p; vN=n; vUV=aUV; vM=vec4(id,aux,tint,bias); vDC=aDC; vHA=aHA;
  vec3 q=p+(uEye-p)*bias*0.0022;
  vec3 nn=normalize(n); vSL=(uLP*vec4(p+nn*uNOff.x,1.)).xyz; vSQ=(uLQ*vec4(p+nn*uNOff.y,1.)).xyz;
  gl_Position=uVP*vec4(q,1.);
}
"""

FS_WORLD = r"""
varying vec3 vP; varying vec3 vN; varying vec2 vUV; varying vec4 vM; varying vec3 vDC; varying vec2 vHA; varying vec3 vSL; varying vec3 vSQ;
uniform sampler2D uPal; uniform sampler2D uAtl; uniform vec2 uAtlS; uniform vec4 uLamp[12]; uniform vec3 uLampC;
varying float vFade;
uniform sampler2D uSh; uniform sampler2D uSq; uniform vec4 uShP;   /* x: 1 when shadows are on, y: 1/size of the far map, z: its depth bias, w: the near map's depth bias */
uniform vec2 uShQ;                                                  /* x: 1/size of the near map, y: unused */
float pcf(sampler2D s, vec2 uv, float z, float ts){
  vec2 q=uv/ts-.5; vec2 f=fract(q); vec2 b=(floor(q)+.5)*ts;
  float a=step(z,texture2D(s,b).r); float c=step(z,texture2D(s,b+vec2(ts,0.)).r); float d=step(z,texture2D(s,b+vec2(0.,ts)).r); float e=step(z,texture2D(s,b+vec2(ts,ts)).r);
  return mix(mix(a,c,f.x),mix(d,e,f.x),f.y); }
float shadowAt(float nl){
  if(uShP.x<.5) return 1.;
  float sl=1.+3.*(1.-nl); float vis=1.; float wq=0.;
  vec3 sc=vSQ*.5+.5; float fq=1.-smoothstep(.70,.96,max(abs(vSQ.x),abs(vSQ.y)));
  float vf=1.;
  { vec3 sf=vSL*.5+.5; float ff=1.-smoothstep(.72,.98,max(abs(vSL.x),abs(vSL.y))); float o=uShP.y*.8; float z=sf.z-uShP.z*sl;
    if(ff>0.&&sf.z<1.&&sf.z>0.){ float v=(pcf(uSh,sf.xy+vec2(-o,-o),z,uShP.y)+pcf(uSh,sf.xy+vec2(o,-o),z,uShP.y)+pcf(uSh,sf.xy+vec2(-o,o),z,uShP.y)+pcf(uSh,sf.xy+vec2(o,o),z,uShP.y))*.25; vf=mix(1.,v,ff); } }
  if(fq>0.&&sc.z<1.&&sc.z>0.){ float o=uShQ.x*.8; float z=sc.z-uShP.w*sl;
    float v=(pcf(uSq,sc.xy+vec2(-o,-o),z,uShQ.x)+pcf(uSq,sc.xy+vec2(o,-o),z,uShQ.x)+pcf(uSq,sc.xy+vec2(-o,o),z,uShQ.x)+pcf(uSq,sc.xy+vec2(o,o),z,uShQ.x))*.25;
    vis=mix(vf,v,fq); } else vis=vf;
  return vis; }

vec3 palCol(float t){ return texture2D(uPal,vec2((floor(t*255.+.5)+.5)*(1./256.),.5)).rgb; }
vec3 lin(vec3 c){ return c*c*(c*.305306011+.682171111)+.012522878; }     /* sRGB -> linear, close to pow 2.2 */
float rectm(vec2 p, vec2 c, vec2 hs, vec2 w){ vec2 d=abs(p-c)-hs; vec2 k=1.-smoothstep(-w,w,d); return k.x*k.y; }
vec3 brickPal(float T){
  float k=fract(T*7.31);
  vec3 a=vec3(.52,.20,.15); vec3 b=vec3(.42,.23,.17); vec3 c=vec3(.58,.36,.25); vec3 d=vec3(.31,.19,.17);
  if(k<.5) return mix(a,b,k*2.*.5);
  if(k<.8) return mix(b,c,(k-.5)/.3);
  return mix(d,a,(k-.8)/.2); }
vec3 stonePal(float T){
  float k=fract(T*3.77);
  vec3 a=vec3(.70,.67,.59); vec3 b=vec3(.60,.60,.58); vec3 c=vec3(.66,.55,.42); vec3 d=vec3(.78,.76,.70);
  if(k<.3) return a; if(k<.55) return b; if(k<.8) return c; return d; }

vec3 brickTex(vec2 uv, float T, vec2 fp){
  vec3 base=brickPal(T);
  float fine=1.-smoothstep(.011,.03,max(fp.x*.5,fp.y));
  float row=floor(uv.y/.0762); float bx=uv.x/.2286+.5*mod(row,2.); float cx=floor(bx);
  float jx=min(fract(bx),1.-fract(bx))*.2286; float jy=min(fract(uv.y/.0762),1.-fract(uv.y/.0762))*.0762;
  float mort=1.-smoothstep(.004,.012,min(jx*.45,jy));
  vec3 bc=base*(.78+.44*h21(vec2(cx,row)+T*17.));
  vec3 mc=vec3(.50,.48,.44);
  vec3 pat=mix(bc,mc,mort);
  vec3 avg=base*.93+mc*.07*.5;
  float big=nz(uv*.45+T*31.)*.5+nz(uv*.11+T*5.)*.5;
  return mix(avg,pat,fine)*(.86+.28*big); }
vec3 stoneTex(vec2 uv, float T, vec2 fp){
  vec3 base=stonePal(T);
  float fine=1.-smoothstep(.04,.13,max(fp.x*.5,fp.y));
  float row=floor(uv.y/.45); float bx=uv.x/.9+.5*mod(row,2.); float cx=floor(bx);
  float jx=min(fract(bx),1.-fract(bx))*.9; float jy=min(fract(uv.y/.45),1.-fract(uv.y/.45))*.45;
  float jn=1.-smoothstep(.006,.02,min(jx,jy));
  vec3 bc=base*(.9+.2*h21(vec2(cx,row)+T*9.));
  float big=nz(uv*.7+T*13.)*.6+nz(uv*.18)*.4;
  return mix(base*.97,mix(bc,bc*.72,jn),fine)*(.84+.3*big); }
vec3 concTex(vec2 uv, float T, vec2 fp){
  vec3 base=mix(vec3(.55,.55,.53),vec3(.62,.61,.58),fract(T*5.1));
  float fine=1.-smoothstep(.06,.2,max(fp.x*.5,fp.y));
  float j=1.-smoothstep(.01,.03,abs(fract(uv.y/1.22)-.5)*1.22*2.-.5*1.22*2.+.02);
  float stain=nz(vec2(uv.x*1.3,uv.y*.12)+T*7.);
  float big=nz(uv*.5+T*3.);
  return base*(.88+.2*stain+.12*big)*(1.-.07*fine*step(fract(uv.y/1.22),.025)); }

/* a wall: albedo, emission and mirror strength at (u,v) metres; type 1 brick, 2 stone, 3 glass, 4 concrete */
void wallFacade(float type, vec2 uv, float L, float H, float T, vec2 fp, vec3 dc, float aux, vec3 V, vec3 N, out vec3 alb, out vec3 emi, out float refl){
  bool tall=H>0.5; float Hh=tall?H:400.; float u=uv.x; float v=uv.y;
  float night=uNight; alb=vec3(.5); emi=vec3(0.); refl=0.;
  bool isGlass=(type>2.5&&type<3.5); bool isStone=(type>1.5&&type<2.5); bool isConc=(type>3.5); bool isBrick=(type<1.5);
  bool rowh=isBrick&&Hh<9.6&&tall;
  float gh=0.; if(tall){ gh=isGlass?4.4:(Hh>13.?4.7:(rowh?3.2:3.5)); if(Hh<gh+(rowh?2.:3.)) gh=0.; }
  float fhT=isGlass?3.9:(rowh?3.1:3.5);
  float nF=max(1.,floor((Hh-gh)/fhT+.5)); float fh=tall?(Hh-gh)/nF:3.4;
  float vv=v-gh; bool ground=tall&&gh>0.&&v<gh; float fi=floor(vv/fh); float vl=vv-fi*fh;
  float rnd=fract(T*91.7);
  float bw=rowh?4.9:(isGlass?1.5:(isStone?3.7:3.3)); bw*=.9+.2*fract(T*13.3);
  float mg=tall?.55:0.; float Lw=tall&&L>.1?L:1e4;
  float inner=tall?max(Lw-2.*mg,.1):1e4; float nb=tall?max(1.,floor(inner/bw+.5)):1.; float bwa=tall?inner/nb:bw;
  float uu=u-mg; float bi=floor(uu/bwa); float ul=uu-bi*bwa;
  bool pier=tall&&(u<mg||u>Lw-mg||Lw<2.2);
  float W1=max(fp.x,.012); float W2=max(fp.y,.012);
  vec2 fw=vec2(W1,W2);
  /* body */
  vec3 body;
  if(isBrick) body=brickTex(uv,T,fp); else if(isStone) body=stoneTex(uv,T,fp); else if(isConc) body=concTex(uv,T,fp); else body=vec3(.12,.15,.2);
  float dk=isGlass?.5:(isConc?.22:.15); if(aux>.5) dk=.9;
  vec3 tf=clamp(dc/max((dc.r+dc.g+dc.b)/3.,.01),.4,1.8);
  body*=mix(vec3(1.),tf,dk);
  alb=body;
  /* trim colour (lintels, sills, frames) */
  vec3 trim=isBrick?vec3(.74,.72,.66):(isStone?body*1.1:vec3(.45,.46,.47));
  vec3 sk=skyAt(reflect(-V,N));
  float ndv=abs(dot(N,V)); float fres=pow(1.-ndv,3.);
  float winM=0.; float glM=0.; float frM=0.; vec3 glassAlb=vec3(.03,.04,.05); vec3 glEmi=vec3(0.);
  vec2 loc=vec2(ul,vl);
  float lit1=h21(vec2(fi*7.1+bi*1.31,T*91.));
  float litP=.16+.34*fract(T*3.1);
  if(!pier && !ground){
    if(isGlass){
      /* curtain wall: spandrel band below each pane, mullions between */
      float spw=.95; float pane=rectm(loc,vec2(bwa*.5,spw+(fh-spw)*.5),vec2(bwa*.5-.045,(fh-spw)*.5-.03),fw);
      float spand=rectm(loc,vec2(bwa*.5,spw*.5),vec2(bwa*.5-.045,spw*.5-.02),fw);
      float louv=step(19.,mod(fi,20.))*step(60.,Hh); pane*=1.-louv; spand*=1.-louv;
      glM=pane; winM=pane;
      vec3 gtint=mix(vec3(.30,.42,.50),vec3(.20,.34,.36),fract(T*5.))*mix(vec3(1.),tf,.7);
      if(aux>.5) gtint=mix(gtint,gtint*tf*1.1,.8);
      float pv=.85+.3*h21(vec2(fi,bi)+T*3.);
      glassAlb=gtint*.30*pv;
      alb=mix(vec3(.30,.31,.33)*mix(vec3(1.),tf,.35),mix(glassAlb,gtint*.17,.5),1.);
      alb=mix(vec3(.20,.21,.23),alb,pane+spand);       /* mullions are metal */
      alb=mix(alb,vec3(.34,.35,.37)*(.6+.4*step(.5,fract(vl*2.5))),louv);
      alb=mix(alb,gtint*.12*pv,spand);
      refl=((.34+.42*fres)*pane+.2*spand)*(.78+.34*h21(vec2(fi*1.7+3.,bi*2.3+T*7.)))*(.85+.3*clamp(vl/fh,0.,1.));
      float on=step(lit1,litP)*night; glEmi=vec3(1.,.82,.52)*(.4+.6*h11(fi*3.+bi))*on*.75;
      emi=glEmi*pane;
    } else if(rowh){
      float s1=ul/bwa;
      vec2 ws=vec2(.95,1.65)*.5;
      float c1=.27*bwa; float c2=.73*bwa;
      float cy=.83+.82;
      float w1=rectm(loc,vec2(c1,cy),ws,fw); float w2=rectm(loc,vec2(c2,cy),ws,fw);
      float f1=rectm(loc,vec2(c1,cy),ws+.07,fw)-w1; float f2=rectm(loc,vec2(c2,cy),ws+.07,fw)-w2;
      float li1=rectm(loc,vec2(c1,cy+ws.y+.12),vec2(ws.x+.18,.1),fw); float li2=rectm(loc,vec2(c2,cy+ws.y+.12),vec2(ws.x+.18,.1),fw);
      float si1=rectm(loc,vec2(c1,cy-ws.y-.07),vec2(ws.x+.14,.06),fw); float si2=rectm(loc,vec2(c2,cy-ws.y-.07),vec2(ws.x+.14,.06),fw);
      winM=max(w1,w2); glM=winM; frM=max(f1,f2);
      alb=mix(alb,trim,clamp(max(max(li1,li2),max(si1,si2)),0.,1.));
      float st1=rectm(loc,vec2(c1,cy-ws.y-.55),vec2(ws.x*.8,.55),vec2(.25,.4))*(1.-w1); float st2=rectm(loc,vec2(c2,cy-ws.y-.55),vec2(ws.x*.8,.55),vec2(.25,.4))*(1.-w2); alb*=1.-.16*max(st1,st2);
      float acb=step(.9,h21(vec2(fi*5.+bi*3.,T*37.)))*rectm(loc,vec2(c2,cy-ws.y*.55),vec2(.34,.2),fw); alb=mix(alb,vec3(.55,.56,.57),acb*(1.-w2));
      alb=mix(alb,vec3(.80,.78,.72),frM);
      /* sash bars */
      float bar=rectm(loc,vec2(c1,cy),vec2(ws.x,.02),fw)+rectm(loc,vec2(c2,cy),vec2(ws.x,.02),fw);
      float bar2=rectm(loc,vec2(c1,cy),vec2(.02,ws.y),fw)+rectm(loc,vec2(c2,cy),vec2(.02,ws.y),fw);
      glM=clamp(winM-clamp(bar+bar2,0.,1.)*.8,0.,1.);
      alb=mix(alb,vec3(.78,.76,.70),clamp(bar+bar2,0.,1.)*winM);
      float on=step(h21(vec2(fi*7.1+bi*1.31+floor(ul/(bwa*.5)),T*91.)),litP)*night;
      float blind=step(.7,h21(vec2(fi+bi*3.+floor(ul/(bwa*.5))*7.,T*5.)));
      glassAlb=mix(vec3(.025,.032,.04),vec3(.45,.40,.33)*.45,blind);
      glEmi=vec3(1.,.74,.42)*(.4+.55*h11(fi*3.+bi*5.+floor(ul/(bwa*.5))))*on*.85;
      refl=(.10+.34*fres)*glM*(1.-blind*.6)*(.75+.5*h21(vec2(fi*3.1,bi*1.9+T*3.+floor(ul/(bwa*.5)))));
    } else {
      float ww=isConc?bwa-.55:(isStone?bwa*.40:bwa*.40+.15); float wh=isConc?1.55:(isStone?2.05:1.95);
      float cy=fh*.5+.15;
      vec2 ws=vec2(ww*.5,wh*.5);
      float w1=rectm(loc,vec2(bwa*.5,cy),ws,fw);
      float f1=rectm(loc,vec2(bwa*.5,cy),ws+.08,fw)-w1;
      float li=rectm(loc,vec2(bwa*.5,cy+ws.y+.14),vec2(ws.x+.2,.11),fw);
      float si=rectm(loc,vec2(bwa*.5,cy-ws.y-.08),vec2(ws.x+.15,.07),fw);
      float mull=rectm(loc,vec2(bwa*.5,cy),vec2(.025,ws.y),fw)*w1;
      winM=w1; glM=clamp(w1-mull*.7,0.,1.); frM=f1;
      float stn=rectm(loc,vec2(bwa*.5,cy-ws.y-.7),vec2(ws.x*.75,.7),vec2(.3,.5))*(1.-w1); alb*=1.-.15*stn*(isConc?.6:1.);
      if(isConc){ alb=mix(alb,vec3(.30,.31,.33),frM); } else { alb=mix(alb,trim,clamp(max(li,si),0.,1.)); alb=mix(alb,isStone?vec3(.46,.44,.40):vec3(.78,.76,.70),frM); }
      float acb=step(.93,h21(vec2(fi*5.+bi*3.,T*37.)))*rectm(loc,vec2(bwa*.5+ws.x*.5,cy-ws.y*.5),vec2(.4,.22),fw); alb=mix(alb,vec3(.55,.56,.57),acb*(1.-w1));
      alb=mix(alb,vec3(.30,.31,.32),mull*.5);
      float on=step(lit1,litP)*night; float blind=step(.78,h21(vec2(fi+bi*3.,T*5.)));
      glassAlb=mix(vec3(.028,.036,.045),vec3(.40,.42,.45)*.4,blind);
      glEmi=vec3(1.,.78,.48)*(.4+.55*h11(fi*3.+bi*5.))*on*.8;
      refl=(.14+.36*fres)*glM*(1.-blind*.6)*(.75+.5*h21(vec2(fi*3.1,bi*1.9+T*3.)))*(.8+.35*clamp(vl/fh*1.2,0.,1.));
      if(isConc){ /* ribbon window bands read as one strip */ }
    }
    alb=mix(alb,glassAlb,glM); emi=glEmi*glM;
  }
  if(ground){
    if(rowh){ }
    else if(isGlass){
      float pane=rectm(vec2(mod(u-mg,bw*.0+1.5),v),vec2(.75,gh*.5+.2),vec2(.75-.05,gh*.5-.2),fw)*(pier?0.:1.);
      vec3 gtint=vec3(.30,.42,.50)*mix(vec3(1.),tf,.7);
      float plinth=1.-smoothstep(.9,.95,v); vec3 inter=mix(vec3(.30,.22,.14),vec3(.10,.075,.05),smoothstep(.0,4.2,v))*(.65+.55*h21(vec2(floor((u-mg)/(bw*.0+1.5)),T*9.)));
      alb=mix(vec3(.2,.21,.23),gtint*.15,pane); alb=mix(alb,stonePal(T+.6)*.8,plinth); pane*=1.-plinth;
      refl=(.14+.34*fres)*pane; emi=inter*pane*(night*2.2+.3);
    } else {
      /* storefront: piers, glass over a lit interior, an awning on some, a sign band above */
      float sg=gh-1.05;
      float pane=rectm(vec2(ul,v),vec2(bwa*.5,.35+(sg-.35)*.5),vec2(bwa*.5-.28,(sg-.35)*.5),fw)*(pier?0.:1.);
      float sign=rectm(vec2(ul,v),vec2(bwa*.5,gh-.6),vec2(bwa*.5-.12,.36),fw)*(pier?0.:1.);
      float lit2=step(h21(vec2(bi,T*53.)),.8);
      vec3 sc=mix(mix(vec3(.12,.2,.16),vec3(.16,.2,.34),fract(T*3.3+bi*.37)),mix(vec3(.4,.1,.12),vec3(.1,.1,.11),fract(T*5.1+bi*.23)),step(.5,fract(T*7.7+bi*.51)));
      vec3 inter=mix(vec3(.07,.055,.045),vec3(.32,.24,.15),h21(vec2(bi*3.1,T*17.))*h21(vec2(floor(v*1.7),bi+T)));
      alb=mix(alb*.75,inter*.5,pane); alb=mix(alb,sc*.7,sign);
      float strip=rectm(vec2(ul,v),vec2(bwa*.5,gh-.6),vec2(bwa*.5-.4,.09),fw); float letter=step(.3,h21(vec2(floor(ul*4.),bi+T*3.)))*strip*sign;
      alb=mix(alb,vec3(.8,.78,.7),letter);
      float awn=step(.68,h21(vec2(bi,T*13.)))*rectm(vec2(ul,v),vec2(bwa*.5,sg-.22),vec2(bwa*.5-.2,.24),fw)*(pier?0.:1.);
      vec3 ac=mix(vec3(.55,.1,.1),mix(vec3(.1,.35,.2),vec3(.12,.2,.45),fract(T*9.)),step(.5,fract(T*21.+bi*.1)));
      alb=mix(alb,mix(ac,vec3(.85),step(.5,fract(ul/.32)))*.8,awn);
      emi=vec3(1.,.82,.55)*inter*pane*(1.-awn)*lit2*(night*2.4+.25)+vec3(1.,.95,.8)*letter*night*1.4+sc*sign*night*.5;
      refl=(.05+.3*fres)*pane*(1.-awn);
      alb=mix(alb,vec3(.22,.22,.24),rectm(vec2(u,v),vec2(u,.2),vec2(1e3,.2),fw)*.5);
    }
  }
  if(rowh && ground){
    /* door and window on the ground floor, with a stoop */
    float c1=.27*bwa; float c2=.73*bwa;
    float door=rectm(vec2(ul,v),vec2(c1,1.15),vec2(.50,1.15),fw); float dtr=rectm(vec2(ul,v),vec2(c1,2.55),vec2(.5,.3),fw);
    float df=rectm(vec2(ul,v),vec2(c1,1.2),vec2(.57,1.22),fw)-door;
    float dk4=fract(T*17.1+bi*.13); vec3 dcol=dk4<.3?vec3(.07,.07,.08):dk4<.55?vec3(.08,.24,.17):dk4<.75?vec3(.38,.08,.08):vec3(.10,.17,.36);
    dcol*=mix(1.,.55,step(.9,fract(T*41.)));
    alb=mix(alb,vec3(.8,.78,.72),df); alb=mix(alb,dcol,door);
    alb=mix(alb,glassAlb*.7+vec3(.01),dtr*(1.-door));
    vec2 ws=vec2(.5,.78); float cyw=1.55;
    float w2=rectm(vec2(ul,v),vec2(c2,cyw),ws,fw); float f2=rectm(vec2(ul,v),vec2(c2,cyw),ws+.07,fw)-w2;
    float si=rectm(vec2(ul,v),vec2(c2,cyw-ws.y-.07),vec2(ws.x+.14,.06),fw);
    float li=rectm(vec2(ul,v),vec2(c2,cyw+ws.y+.12),vec2(ws.x+.18,.1),fw);
    alb=mix(alb,trim,clamp(si+li,0.,1.)); alb=mix(alb,vec3(.8,.78,.72),f2);
    float blind=step(.6,h21(vec2(bi,T*5.)));
    vec3 ga=mix(vec3(.025,.032,.04),vec3(.45,.40,.33)*.45,blind);
    float on=step(h21(vec2(bi*7.,T*91.)),litP+.1)*night;
    alb=mix(alb,ga,w2); emi=vec3(1.,.74,.42)*(.6+.4*h11(bi*3.+T))*on*(w2*.9+dtr*(1.-door)*.5);
    refl=(.1+.3*fres)*w2*(1.-blind*.6);
    /* the water table: a stone course along the foot */
    float wt=1.-smoothstep(.9,.95,v); alb=mix(alb,stonePal(T+.3)*.85,wt*step(0.,v));
  }
  if(tall && gh<=0. && !rowh && !isGlass){ }
  if(!tall){ }
  /* cornice and parapet band at the top */
  if(tall){
    float cb=smoothstep(Hh-.95,Hh-.9,v);
    if(!isGlass) alb=mix(alb,mix(trim,body,.35)*1.02,cb);
    else alb=mix(alb,vec3(.30,.31,.33)*mix(vec3(1.),tf,.3),smoothstep(Hh-.6,Hh-.55,v));
    if(!isGlass && cb>.5){ float dent=step(.5,fract(u/.38)); alb*=.9+.1*dent*(1.-smoothstep(.5,2.,fp.x)); emi*=0.; refl*=0.; }
  }
}

vec3 asphalt(vec2 gp, float fpx){
  float lo=nz(gp*.11+7.); float mid=nz(gp*.9); float gr=nz(gp*11.)*(1.-smoothstep(.01,.06,fpx))+nz(gp*37.)*(1.-smoothstep(.003,.02,fpx));
  float patch=smoothstep(.62,.75,nz(gp*.045+2.));
  vec3 a=vec3(.30,.302,.31)*(.88+.2*lo)*(.95+.1*mid)+vec3(.05)*(gr-.8)*.5;
  a=mix(a,vec3(.23,.23,.24),patch*.3);
  float stain=smoothstep(.7,.85,nz(gp*.3+11.)); a*=1.-.14*stain;
  return a; }
void main(){
  if(vFade<1.){ float dn=fract(52.9829189*fract(dot(gl_FragCoord.xy,vec2(.06711056,.00583715)))); if(vFade<dn) discard; }
  float id=floor(vM.x+.5); float aux=floor(vM.y+.5); float T=vM.z;
  vec3 N=normalize(vN); vec3 toE=uEye-vP; float dist=length(toE); vec3 V=toE/dist;
  if(dot(N,V)<0.) N=-N;
  float fpx=dist*uPix/UMc; float ndv=max(abs(dot(N,V)),.1);
  vec2 fp=vec2(fpx/ndv,fpx);
  vec3 alb=vec3(.5); vec3 emi=vec3(0.); float refl=0.; float ao=1.; float spec=0.; float wrap=0.;
  vec2 gp=abs(N.z)>.7?vP.xy/UMc:vec2(vUV.x,vUV.y+vP.z/UMc*.0);
  bool wallLike=abs(N.z)<.55;
  vec3 tf=clamp(vDC/max((vDC.r+vDC.g+vDC.b)/3.,.01),.4,1.8);
  if(id<.5){            /* ground */
    alb=vec3(.40,.39,.37)*(.85+.3*nz(gp*.4));
  } else if(id<4.5 && id>.5 && id!=0.){
    /* brick 1, stone 2, glass 3, concrete 4 */
    if(id>2.5&&id<3.5&&N.z>.55){ alb=vec3(.22,.22,.23)*(.8+.4*nz(gp*.8)); }
    else if(wallLike){ wallFacade(id,vUV,vHA.y,vHA.x,T,fp,vDC,aux,V,N,alb,emi,refl);
      if(vHA.x>.5){ float vv=vUV.y; ao*=mix(.62,1.,smoothstep(.0,2.2,vv)); ao*=mix(.78,1.,smoothstep(vHA.x-1.9,vHA.x-1.0,vv)+step(vHA.x-1.0,vv)); } }
    else if(N.z<=-.55){ alb=vec3(.46,.45,.43)*(.9+.2*nz(gp)); ao=.7; }
    else { /* a roof */ float g=nz(gp*.55)*.6+nz(gp*2.9)*.4*(1.-smoothstep(.02,.1,fpx)); alb=vec3(.27,.265,.26)*(.86+.3*g)*mix(vec3(1.),tf,.12); alb=mix(alb,vec3(.5,.5,.48),smoothstep(.62,.8,nz(gp*.09+3.))*.4); }
  } else if(id<5.5){    /* roof */
    float g=nz(gp*.55)*.6+nz(gp*2.9)*.4*(1.-smoothstep(.02,.1,fpx)); alb=vec3(.27,.265,.26)*(.86+.3*g);
    if(!(N.z>.9)){ float rowv=fract(vUV.y/.4); alb=mix(vec3(.26,.2,.18),vec3(.20,.16,.15),smoothstep(.0,.2,rowv)*(1.-smoothstep(.25,.45,rowv))); }
  } else if(id<6.5){    /* metal */
    alb=vec3(.42,.44,.47)*(.85+.3*nz(gp*3.)); refl=.18+.25*pow(1.-ndv,3.); spec=1.;
  } else if(id<7.5){    /* copper, aged to verdigris */
    alb=mix(vec3(.33,.57,.5),vec3(.66,.38,.22),step(.97,nz(gp*.3)))*(.85+.3*nz(gp*1.1)); refl=.1;
  } else if(id<8.5){    /* glass dome */
    alb=vec3(.12,.2,.24); refl=.45+.4*pow(1.-ndv,3.);
  } else if(id<9.5){    /* wood */
    alb=vec3(.42,.3,.2)*(.8+.4*nz(vec2(vUV.x*2.,vUV.y*40.)));
  } else if(id<10.5){   /* water */
    float t=uTime; vec2 q=gp;
    vec2 g1=vec2(nz(q*.55+vec2(t*.35,t*.21))-.5, nz(q*.55+7.+vec2(-t*.27,t*.33))-.5);
    vec2 g2=vec2(nz(q*1.7+vec2(-t*.6,t*.4))-.5, nz(q*1.7+3.+vec2(t*.5,-t*.45))-.5);
    float calm=1.-smoothstep(.05,.7,fpx*2.);
    vec3 wn=normalize(vec3((g1.x*.30+g2.x*.14)*calm,(g1.y*.30+g2.y*.14)*calm,1.));
    vec3 R=reflect(-V,wn);
    float fr=.03+.97*pow(1.-max(dot(wn,V),0.),5.);
    vec3 deep=vec3(.045,.10,.13)*mix(1.,.35,uNight);
    vec3 shallow=vec3(.10,.19,.20)*mix(1.,.4,uNight);
    vec3 body=mix(deep,shallow,nz(gp*.04)*.7);
    vec3 sk=skyAt(vec3(R.xy,abs(R.z)));
    float gl=pow(max(dot(R,uSun),0.),90.)*(.4+.6*calm);
    vec3 col0=mix(body,sk,fr*.9+.08)+uSunCol*gl*1.4;
    vec3 colL=col0;
    float fq=dist/uFogD; float f=1.-exp(-fq*fq); colL=mix(colL,uFog,f);
    colL=aces(colL*uExp); gl_FragColor=vec4(pow(colL,vec3(1./2.2)),1.); return;
  } else if(id<11.5){   /* asphalt */
    alb=asphalt(gp,fpx);
  } else if(id<12.5){   /* paving: concrete slabs */
    vec2 q=gp/1.55; vec2 f=abs(fract(q)-.5); float j=max(f.x,f.y);
    float wd=.012+fpx/1.55*.6; float joint=smoothstep(.5-wd*1.6,.5-wd*.2,j)*(1.-smoothstep(.02,.4,fpx*4.));
    alb=vec3(.60,.585,.56)*(.86+.2*nz(gp*.7)+.1*nz(gp*4.)*(1.-smoothstep(.04,.2,fpx)))*(1.-.22*joint);
    alb*=.92+.16*h21(floor(q));
  } else if(id<13.5){   /* grass */
    float a=nz(gp*.35); float b=nz(gp*1.3+4.); float c=nz(gp*6.)*(1.-smoothstep(.03,.18,fpx));
    vec3 g1=vec3(.19,.30,.14); vec3 g2=vec3(.27,.38,.18); vec3 g3=vec3(.32,.41,.21);
    alb=mix(g1,g2,a); alb=mix(alb,g3,b*.4); alb*=.92+.22*(c-.5)*2.; alb*=mix(vec3(1.),tf,.04);
  } else if(id<14.5){ alb=vec3(.88,.88,.86);
  } else if(id<15.5){ alb=vec3(.07,.07,.08);
  } else if(id<16.5){   /* roof tile */
    float rowv=fract(vUV.y/.32); alb=mix(vec3(.45,.2,.14),vec3(.3,.13,.1),smoothstep(.0,.35,rowv))*(.85+.3*h21(floor(vUV*vec2(3.,3.1))));
  } else if(id<17.5){   /* trunk: the scenery palette colour, barked */
    alb=palCol(T)*(.78+.45*nz(vec2(vUV.x*14.,vUV.y*2.6)));
  } else if(id<18.5){   /* leaves: the palette colour (three shades a tree), broken up by noise */
    vec2 lq=vP.xy*.9+vec2(vP.z*1.7,vP.z*-1.3); float cl=nz(lq*1.1)*.6+nz(lq*3.9)*.4; float cl2=nz(lq*13.)*(1.-smoothstep(.02,.1,fpx));
    alb=palCol(T)*(.7+.62*cl)*(.88+.22*cl2); wrap=.6; ao*=(.62+.38*smoothstep(.0,3.,vP.z))*(.8+.2*(N.z*.5+.5));
  } else if(id<19.5){   /* car paint, glass, tyres, lamps: palette colours, glossy */
    vec3 pc=palCol(T); float lum=dot(pc,vec3(.3,.59,.11));
    alb=pc; refl=(.10+.35*pow(1.-ndv,3.))*(lum<.2?1.3:1.); spec=1.;
    if(pc.r>.9&&pc.g>.9&&pc.b>.75){ emi=pc*(.3+uNight*2.); } else if(pc.r>.75&&pc.g<.2&&pc.b<.2){ emi=pc*(.2+uNight*1.6); }
  } else if(id<20.5){   /* skin, hair and clothes */
    alb=palCol(T);
  } else if(id<21.5){   /* lamp heads and signal lenses: lit ones glow */
    vec3 pc=palCol(T); float mx=max(pc.r,max(pc.g,pc.b)); alb=pc*.5; emi=mix(vec3(0.),pc,step(.8,mx))*(.9+uNight*3.4);
  } else if(id<22.5){   /* paint, plates, hydrants, bins */
    vec3 sc=palCol(T); if(vDC.r<.99||vDC.g<.99||vDC.b<.99) sc=vDC; alb=sc; emi=sc*uNight*.07;
  } else if(id<23.5){   /* red brick */
    alb=brickTex(vUV,T*.1+.01,fp);
  } else if(id<24.5){   /* street-name text from the atlas, unlit */
    vec3 tc=texture2D(uAtl,vUV*uAtlS).rgb; alb=vec3(0.); emi=lin(tc)*(.8+.2*(1.-uNight)); refl=0.;
  } else if(id<25.5){   /* the glass leaves of a node building's door: dark glass, a warm room behind it, the sky in it */
    float vh=clamp(vUV.y/2.2,0.,1.); float gl=.45+.55*sin(vh*3.14159); alb=vec3(.045,.05,.055);
    emi=vec3(1.,.66,.34)*(.2+uNight*1.1)*gl*(.88+.2*nz(vUV*2.6)); refl=.16+.34*pow(1.-ndv,3.); spec=1.;
  } else if(id<26.5){   /* the soft light under a canopy */
    alb=vec3(.09,.085,.08); emi=vec3(1.,.7,.4)*(.07+uNight*.7);
  } else if(id<39.5){ alb=vec3(.5);
  } else if(id<40.5){   /* paint on the road */
    vec3 pc=mix(vec3(.88,.87,.8),vec3(.93,.74,.15),step(1.5,vDC.r)); float wear=nz(gp*2.7); alb=mix(vec3(.26),pc,smoothstep(.08,.4,wear)*.22+.76);
  } else if(id<41.5){   /* ballast and ties */
    float u=vUV.x; float v=vUV.y; float w=.02+fpx*.6;
    float ph=fract(v/.65)*.65; float tie=smoothstep(.0,w+.01,ph)*(1.-smoothstep(.26,.26+w+.01,ph))*(1.-smoothstep(1.35,1.5,abs(u)));
    tie=clamp(tie,0.,1.)*(1.-smoothstep(.1,.5,fpx*3.));
    float gr=nz(gp*.7)*.3+nz(gp*3.1)*.3+nz(gp*13.)*.25*(1.-smoothstep(.01,.06,fpx))+nz(gp*47.)*.15*(1.-smoothstep(.004,.02,fpx));
    vec3 ball=vec3(.33,.325,.32)*(.62+.8*gr);
    alb=mix(ball,vec3(.20,.15,.11)*(.8+.4*nz(gp*8.)),tie*.9);
    float sh=smoothstep(2.4,3.2,abs(u)); alb=mix(alb,ball*.8,sh);
  } else if(id<42.5){   /* rail */
    alb=vec3(.40,.40,.42); if(N.z>.6) { alb=vec3(.66,.66,.69); spec=1.; } refl=.15;
  } else if(id<43.5){   /* roadway with lane lines */
    alb=asphalt(gp,fpx);
    float a=abs(vUV.x); float hw=vDC.r; float w=fpx*.8+.02;
    float dash=smoothstep(0.,w+.02,fract(vUV.y/12.)*12.-.0)*smoothstep(0.,w+.02,3.1-fract(vUV.y/12.)*12.);
    float cen=(1.-smoothstep(.07-w,.07+w,a))*dash*(1.-hw);
    float dbl=(1.-smoothstep(.07-w,.07+w,abs(a-.14)))*hw;
    float edge=(1.-smoothstep(.07-w,.07+w,abs(a-vDC.g)))*step(.5,hw);
    vec3 pc=vec3(.88,.87,.8); vec3 yc=vec3(.93,.74,.15);
    alb=mix(alb,pc,cen*.9); alb=mix(alb,yc,dbl*.9); alb=mix(alb,pc,edge*.9);
  } else if(id<44.5){   /* the mouth of a tunnel */
    vec2 q=vUV; float r=length(vec2(q.x/7.,(q.y-5.)/6.)); vec3 c=vDC;
    alb=vec3(.01,.01,.02); emi=mix(c*.2,c*1.6,(1.-smoothstep(.0,.9,r)))*(1.+uNight*.4)+vec3(.02);
  } else if(id<45.5){   /* curb */
    alb=vec3(.64,.63,.60)*(.85+.25*nz(gp*1.3));
  } else if(id<46.5){   /* lot / yard */
    float a=nz(gp*.25); float b=nz(gp*1.1+5.); float c=nz(gp*6.7)*(1.-smoothstep(.01,.08,fpx))+nz(gp*23.)*(1.-smoothstep(.004,.03,fpx));
    float gz=smoothstep(.68,.86,a+.15*(b-.5));
    alb=mix(vec3(.40,.395,.37),vec3(.25,.32,.19),gz*.75)*(.86+.2*b)*(.9+.14*(c-.7));
  } else if(id<47.5){   /* plain concrete */
    alb=vec3(.45,.45,.44)*(.84+.26*nz(gp*.8)+.08*nz(vec2(vUV.x*3.,vUV.y*.8)));
    if(vHA.y>.5){ }
  } else {              /* crosswalk bars */
    alb=mix(vec3(.2),vec3(.9,.9,.86),smoothstep(.1,.5,nz(gp*3.))*.5+.45);
  }
  float nl=max(dot(N,uSun),0.); float nlw=max(dot(N,uSun)*(1.-wrap)+wrap,0.);
  float shd=nl>.001?shadowAt(nl):1.;
  vec3 amb=mix(uGndA,uSkyA,N.z*.5+.5);
  vec3 L=lin(clamp(alb,0.,1.));
  /* sun on the surface, ambient from the sky; a touch of bounce from the street onto walls */
  vec3 col=L*(amb*ao+uSunCol*nlw*ao*mix(1.,.85,wrap)*shd) +emi*1.0;
  if(uNight>.5){ for(int i=0;i<12;i++){ vec4 lp=uLamp[i]; if(lp.w>.5){ vec3 dl=lp.xyz-vP; float dd=dot(dl,dl); float dis=sqrt(dd); float att=exp(-dd*(1./(27.*27.)))*(1.-smoothstep(70.,120.,dis)); float nlL=max(dot(N,dl/max(dis,.01)),0.)*.8+.2*step(.5,N.z); col+=L*uLampC*att*nlL*.6; } } }
  if(spec>.5){ vec3 H=normalize(uSun+V); col+=uSunCol*pow(max(dot(N,H),0.),70.)*.45*(1.-uNight*.7)*shd; }
  if(refl>0.){ vec3 R=reflect(-V,N); vec3 sr=mix(uHor*.30+vec3(.02),skyAt(vec3(R.xy,max(R.z,0.))),smoothstep(-.12,.16,R.z)); col=mix(col,sr,clamp(refl,0.,.95)); if(spec>.5||id>2.5&&id<3.5){ col+=uSunCol*pow(max(dot(R,uSun),0.),240.)*refl*3.*shd; } }
  float fq=dist/uFogD; float f=1.-exp(-fq*fq); float hf=clamp(1.-(vP.z/UMc)/260.,.0,1.); f*=mix(.5,1.,hf);
  vec3 fogc=uFog+uSunCol*.045*pow(max(dot(-V,uSun),0.),5.)*(1.-uNight);
  col=mix(col,fogc,clamp(f,0.,1.));
  col=aces(col*uExp);
  gl_FragColor=vec4(pow(col,vec3(1./2.2)),1.);
}
"""

VS_SKY = r"""
attribute vec2 aQ; varying vec2 vQ;
void main(){ vQ=aQ; gl_Position=vec4(aQ,.9999,1.); }
"""

FS_SKY = r"""
varying vec2 vQ;
uniform vec3 uF; uniform vec3 uR; uniform vec3 uU; uniform vec4 uPrj; uniform mat2 uUn; uniform vec2 uUt; uniform vec3 uGnd;
float fbm(vec2 p){ float a=.5; float s=0.; for(int i=0;i<4;i++){ s+=a*nz(p); p=p*2.03+vec2(11.7,3.1); a*=.5; } return s; }
void main(){
  vec2 n=uUn*(vQ-uUt);
  float xr=(n.x-uPrj.y)*uPrj.x; float yr=(n.y-uPrj.w)*uPrj.z;
  vec3 d=normalize(uR*xr+uU*yr+uF);
  vec3 c;
  if(d.z>=0.){
    c=skyAt(d);
    float cs=smoothstep(.015,.25,d.z);
    vec2 p=d.xy/(d.z+.12)*3.2+vec2(uTime*.05,uTime*.02);
    float f=fbm(p*1.3);
    float dens=smoothstep(.50,.78,f)*cs;
    float lt=.55+.45*clamp(dot(vec3(d.xy,d.z),uSun)*.6+.5,0.,1.);
    vec3 cc=mix(vec3(.62,.66,.74),vec3(1.,.99,.96),lt)*(1.-.88*uNight)+vec3(.035,.045,.085)*uNight;
    cc=mix(cc,uHor*1.05,.25);
    c=mix(c,cc,dens*.82);
    if(uNight>.5){ vec3 sd=floor(d*220.); float st=h21(sd.xy+sd.z*7.3); float tw=.7+.3*sin(uTime*1.3+st*40.); c+=vec3(.9,.92,1.)*step(.9984,st)*tw*(1.-dens)*smoothstep(.02,.2,d.z)*.9; }
  } else {
    float t=min(uEye.z/max(-d.z,.002),9000.);
    float fq=t/uFogD; float f=1.-exp(-fq*fq);
    c=mix(uGnd,uFog,clamp(f,0.,1.));
  }
  c=aces(c*uExp);
  gl_FragColor=vec4(pow(c,vec3(1./2.2)),1.);
}
"""

VS_SHADOW = r"""
attribute vec3 aP; uniform mat4 uLP;
void main(){ gl_Position=uLP*vec4(aP,1.); }
"""

FS_SHADOW = r"""
precision mediump float;
void main(){ gl_FragColor=vec4(1.); }
"""
