"""2.0.0 FPV facade grammar (owner: the typology agent): every real building is drawn as what it is - a Philadelphia rowhouse, a storefront row, an office, a church,
a school, a factory, a garage - not one procedural wall for all.

DATA (palace_street.py, the 2.0.0 accuracy block; every field optional, an older blob falls back to inference here):
  ty typology 1..16, er era 1..5 (else yr / start_date / the 'old' flag), st stories, by bays across the front, fe front edge (1 + ring edge index),
  pe party-wall edge bitmask, pc roof pitch class, rs roof:shape, k building=*, po the building's own POI ("shop=bakery"), fl flags (1 storefront, 16 old).

JS (spliced into the ride by palace_ride_street.py):
  fcClass(rec, ring, n, h, area, ob, seed) -> s.fg = {g (= ty), er, by, st, fe, pe, sm (street-facing edge mask), sd (seed)}   (gather side, cached on the record)
  glFacW(b, s, st, r, i, n, ax, ay, bx, by, zb, h, pk) -> the pk of wall i (palace_ride_gl.py glSolid): the wall's ROLE and the building's grammar are packed into
     the aux byte range of pk (aux = 2 + role + 4*g + 128*er + 1024*bays; role 0 side/rear, 1 main front, 2 party wall, 3 another street side), the recorded stories ride in
     the fraction of H (H = floor(m) + (st+.5)/64); and the wall's 3D extras are appended to the cell buffer: marble stoops with railings, porch fronts, a mansard on the
     front of a Victorian house, chimneys, rooftop plant on big flat roofs, a loading dock, a church tower with its spire.
GLSL: FS_FACADE (fcBrick, fcDH, facadeG) goes before wallFacade in palace_ride_gl_shaders.py; wallFacade hands aux >= 2 to facadeG.
WebGL1 / one program: no new attribute, no new uniform, no texture.
"""

JS_FACADE = r"""
/* ── facade grammar (palace_ride_facade.py) ── */
var FC_ERA_OF_YR=function(y){ return !y?0:y<1830?1:y<1900?2:y<1946?3:y<1980?4:5; };
var FC_CIVIC=/^(civic|government|public|museum|library|courthouse|townhall|train_station|fire_station|police|post_office|transportation)$/, FC_REL=/^(church|cathedral|chapel|synagogue|mosque|temple|shrine|religious|monastery)$/,
    FC_SCH=/^(school|university|college|kindergarten|dormitory)$/, FC_IND=/^(industrial|warehouse|factory|manufacture|hangar|storage_tank|service|shed)$/, FC_PARK=/^(parking|garage|garages|carport)$/;
/* typology when the data has none: OSM building=*, the POI on it, the storefront flag, the height and the footprint's shape (a rowhouse is narrow, deep and low) */
function fcType(rec, h, area, ob){
  var k=String(rec.k||'').replace(/^p:/,''), po=String(rec.po||''), w=Math.min(ob.u1-ob.u0,ob.v1-ob.v0), sf=!!(rec.fl&1)||!!rec.storefront;
  if(FC_REL.test(k)||/place_of_worship/.test(po)) return 10;
  if(FC_SCH.test(k)||/amenity=(school|college|university|kindergarten)/.test(po)) return 14;
  if(k==='hospital'||/amenity=(hospital|clinic)/.test(po)) return 15;
  if(k==='hotel'||/tourism=(hotel|hostel|motel)/.test(po)) return 13;
  if(FC_PARK.test(k)||/amenity=parking/.test(po)) return 11;
  if(FC_IND.test(k)) return 9;
  if(FC_CIVIC.test(k)||/amenity=(townhall|courthouse|library|police|fire_station)|tourism=museum/.test(po)) return 8;
  if(k==='office'||/^office=/.test(po)&&h>14) return 12;
  if(k==='semidetached_house') return 2;
  if(k==='detached'||k==='bungalow') return 3;
  if(h>=40) return /apartments|residential/.test(k)?6:(h>=60?12:6);
  if(sf||/^(retail|commercial|kiosk|supermarket|shop|mixed_use)$/.test(k)) return h>11?16:7;
  if(k==='apartments') return h>16?5:4;
  if(h<=13.5 && w<=8.6 && area<=240 && (k==='yes'||k==='house'||k==='terrace'||k==='residential'||k==='townhouse'||k==='row_house'||k==='')) return 1;
  if(h<=13.5 && area<=420) return /house/.test(k)?3:4;
  if(h<=12 && area>1500) return 9;
  return h>16?(area>900?12:5):4; }
function fcClass(rec, ring, n, h, area, ob, seed){
  if(rec._fg && rec._fg.n===n) return rec._fg;
  var g=rec.ty>0&&rec.ty<=16?rec.ty:fcType(rec,h,area,ob), er=rec.er>0?rec.er:FC_ERA_OF_YR(rec.yr||parseInt(String(rec.sd||'').slice(0,4),10)||0);
  if(!er){ var old=!!(rec.fl&16); er=old?(seed<.35?1:2):(g<=3?(seed<.3?2:3):(g===6||g===12||g===13?(h>90?5:seed<.5?4:5):(g===7||g===16||g===8||g===10||g===14||g===9?(seed<.45?2:3):(seed<.5?3:4)))); }
  /* the street-facing edges (outward normal meets a road within its half width + 7 m, roughly parallel); the main front = the data's fe, else the longest of them */
  var cx=0, cy=0, i, sm=0, best=-1, bl=0; for(i=0;i<n;i++){ cx+=ring[2*i]/n; cy+=ring[2*i+1]/n; }
  for(i=0;i<n && i<31;i++){ var j=(i+1)%n, ax=ring[2*i], ay=ring[2*i+1], bx=ring[2*j], by=ring[2*j+1], ex=bx-ax, ey=by-ay, l=Math.hypot(ex,ey); if(l<2.2) continue;
    var mx=(ax+bx)/2, my=(ay+by)/2, nx=ey/l, ny=-ex/l; if(nx*(mx-cx)+ny*(my-cy)<0){ nx=-nx; ny=-ny; }
    var nr=rlNear(mx+nx*3,my+ny*3,20,false)[0]; if(!nr) continue; var cl=RCLS[nr.f[0]], hw=cl?cl[0]/2:5;
    if(nr.d<hw+7 && Math.abs(Math.cos(nr.ang-Math.atan2(ey,ex)))>.75){ sm|=(1<<i); if(l>bl){ bl=l; best=i; } } }
  var fe=rec.fe>0?rec.fe-1:best; if(fe>=0 && fe<31) sm|=(1<<fe);
  var pe=rec.pe|0; if(fe>=0) pe&=~(1<<fe);
  return rec._fg={g:g, er:er, by:Math.min(15,rec.by|0), st:Math.min(60,rec.st|0), fe:fe, pe:pe, sm:sm, sd:seed, n:n, pc:rec.pc|0}; }
/* the roof kind for gatherReal's roofOf: 0 flat+parapet, 1 gable, 2 hip, -1 none (towers) */
function fcRoofKind(fg, rs, rect, area, h, hs){
  var r=String(rs||''); if(/gabled|gambrel|saltbox/.test(r)) return rect?1:0; if(/hipped|pyramidal/.test(r)) return rect?2:0; if(/flat/.test(r)) return 0;
  if(fg.pc===1) return 0; if(fg.pc===3 && rect) return hs<.55?1:2;
  if(fg.g===1||fg.g===7||fg.g===16||fg.g===11||fg.g===12||fg.g===4&&h>9) return h<=40?0:-1;   /* Philadelphia rowhouses, shops, offices: flat behind a cornice */
  if(fg.g===10 && rect) return 1;
  if((fg.g===2||fg.g===3) && rect && area<400) return hs<.6?1:2;
  return -2; }                                                                                       /* -2: no opinion (the old rule) */
/* a shop's colours by what it sells: the hue picks the fascia (palace_ride_g.py atlasPaint FA, 8) and the awning (palace_ride_gl.py AWN, 7) together:
   cafe brown + sage, bar burgundy + navy, restaurant umber + burgundy, pharmacy green, bank navy, salon black + cream, clothes plum + charcoal, grocer / deli teal + sage */
var FC_SHOP=[[/cafe|coffee|bakery|tea/,.86],[/bar|pub|nightclub|wine|alcohol|brewery|biergarten/,.2],[/restaurant|fast_food|pizza|ice_cream|food_court/,.4],[/pharmacy|chemist|optician|doctors|dentist/,.27],
  [/bank|atm|money|bureau_de_change|insurance|estate_agent/,.05],[/hairdresser|beauty|salon|barber|cosmetics|tattoo|massage|nail/,.68],[/clothes|boutique|shoes|jewelry|fashion|bag|gift|florist|art|antique/,.55],
  [/convenience|supermarket|deli|greengrocer|butcher|grocery|seafood|alcohol|variety/,.93]];
function fcShopHue(cat,h){ var c=String(cat||''); for(var i=0;i<FC_SHOP.length;i++) if(FC_SHOP[i][0].test(c)) return FC_SHOP[i][1]; return h; }
/* ── the renderer's side: the pk of a wall and its 3D extras ── */
var FC_DOOR=[[.06,.06,.07],[.09,.22,.15],[.36,.08,.08],[.10,.16,.32],[.30,.19,.11],[.55,.53,.47]];
/* the bays across a front: the data's count when the frontage can hold it (a house bay is 1.6-2.6 m), else 2 or 3 for a house */
function fcBays(fg,L){ var h=fg.g>=1&&fg.g<=3, b=fg.by|0; if(h){ var lo=Math.max(1,Math.round(L/2.6)), hi=Math.max(lo,Math.round(L/1.6)); return (b>=lo&&b<=hi)?Math.min(b,L<8?3:b):Math.max(2,Math.min(3,Math.round(L/2.1))); } return b; }
function glFacW(b,s,st,r,i,n,ax,ay,bx,by,zb,h,pk){
  var fg=s.fg; if(!fg || st.aux) return pk;
  var oi=-1; if(s.ring.length===2*n){ var rev=!(r[0]===s.ring[0]&&r[1]===s.ring[1]); oi=rev?(2*n-2-i)%n:i; }
  var role=0; if(oi>=0 && oi<31){ if(oi===fg.fe) role=1; else if((fg.pe>>>oi)&1) role=2; else if((fg.sm>>>oi)&1) role=3; }
  var L=Math.hypot(bx-ax,by-ay)/UM, hm=(h-zb)/UM;
  if(role===1 && L>2.4 && s._fcx!==b && hm>2.5){ s._fcx=b; try{ fcExtras(b,s,st,fg,ax,ay,bx,by,zb,h,L,hm); }catch(e){} }
  return (pk%256)+256*(2+role+4*fg.g+128*Math.min(7,fg.er)+1024*(role===1?Math.min(15,fcBays(fg,L)):0)); }
/* the wall material a typology implies when the data names none (rowhouses, schools, mills are brick; churches stone; garages concrete) */
function fcStyle(s,st){ var fg=s.fg; if(!fg||st.aux) return st; var g=fg.g, hh=fg.sd; if(s.mat && !(s.matInf && (st.mat===3||st.mat===4&&(g===1||g===14||g===9||g===10)))) return st;
  if(g<=3||g===7||g===14||g===9) st.mat=(g===7&&hh>.8)?4:1; else if(g===10) st.mat=hh<.75?2:1; else if(g===11) st.mat=4; else if(g===8||g===15) st.mat=hh<.5?2:(hh<.8?1:4);
  else if(g===16||g===4) st.mat=hh<.8?1:4; else if((g===12||g===6||g===13)&&fg.er<=3) st.mat=hh<.55?2:1; return st; }
/* the stories ride in H's fraction (palace_ride_gl.py glSolid sets _gH) */
function glFacH(s,hm){ var fg=s.fg; return (!fg)?hm:Math.floor(hm)+((fg.st>0?Math.min(60,fg.st):0)+.5)/64; }
function fcExtras(b,s,st,fg,ax,ay,bx,by,zb,h,L,hm){
  var K=UM, dx=(bx-ax)/(L*K), dy=(by-ay)/(L*K), nx=-dy, ny=dx, yaw=Math.atan2(dy,dx), sd=fg.sd, g=fg.g, er=fg.er, T=st.t;
  var sv=[_gdr,_gdg,_gdb,_gH,_gL]; _gH=0; _gL=0; s._fcRoof=0;
  /* along-wall a (m from A), out d (m), z (m above the wall's foot) */
  function at(a,d){ return [ax+(dx*a+nx*d)*K, ay+(dy*a+ny*d)*K]; }
  function box(a0,a1,d0,d1,z0,z1,pk,dc){ var c=at((a0+a1)/2,(d0+d1)/2); if(dc){ _gdr=dc[0]; _gdg=dc[1]; _gdb=dc[2]; } else { _gdr=_gdg=_gdb=1; } gbox(b,c[0],c[1],(a1-a0)/2*K,(d1-d0)/2*K,zb+z0*K,zb+z1*K,yaw,pk,T,true); }
  var house=g>=1&&g<=3, nb=fcBays(fg,L), bw=L/nb, fr=T*17.3-Math.floor(T*17.3), di=fr<.5?0:nb-1, du=(di+.5)*bw;
  if(house && L<14){
    var porch=g===2||(g===1&&er===3&&sd>.7&&L>5.2&&hm<10.5);
    if(porch){                                                                    /* a porch front: deck, posts, a roof (West / North / Northeast Philly) */
      box(.1,L-.1,0,2.3,0,.75,47); box(.1,L-.1,2.12,2.22,1.55,1.63,39); for(var pb=.3;pb<L-.2;pb+=.32){ if(Math.abs(pb-du)<.7) continue; box(pb-.03,pb+.03,2.14,2.2,.75,1.56,39); } [0.2,L/2,L-.35].forEach(function(p){ box(p,p+.16,2.05,2.25,.75,3.0,14); });
      box(-.05,L+.05,0,2.45,3.0,3.18,5); box(du-.6,du+.6,2.3,3.4,0,.25,47); box(du-.6,du+.6,2.3,3.0,.25,.5,47); }
    else {                                                                        /* the stoop: marble (old), brownstone or concrete steps up to the door, iron railings */
      var sH=er<=3?.9:.35, nS=Math.max(1,Math.round(sH/.19)), dp=nS*.3+.35, mt=er<=1||er===3?14:(er===2&&sd<.4?2:(er===2?14:47)), sc=mt===2?[1.15,.95,.85]:null;
      for(var k=0;k<nS;k++) box(du-.68,du+.68,0,dp-k*.3,k*sH/nS,(k+1)*sH/nS,mt,sc);
      if(sH>.5){ box(du-.72,du-.68,.05,dp,sH+.82,sH+.9,39); box(du+.68,du+.72,.05,dp,sH+.82,sH+.9,39); box(du-.72,du-.68,dp-.06,dp,0,sH+.9,39); box(du+.68,du+.72,dp-.06,dp,0,sH+.9,39); box(du-.72,du-.68,.05,.11,sH,sH+.9,39); box(du+.68,du+.72,.05,.11,sH,sH+.9,39);
        if(er<=2&&sd<.6){ for(var a=.4;a<L-.3;a+=.25){ if(Math.abs(a-du)<.9) continue; box(a-.015,a+.015,1.09,1.13,0,.95,39); } box(.25,L-.25,1.08,1.14,.92,.98,39); box(.25,L-.25,1.08,1.14,.05,.1,39); } } }   /* the basement areaway fence */
    if(er===2 && g===1 && sd>.3 && sd<.62 && hm>7.5 && nb>=2){                   /* a Victorian oriel: a wooden bay window over the parlour, glass on three sides */
      var fh=(fg.st>1?(hm-.95)/fg.st:3.2), oz=(fg.st>1?fh:3.3)+.15, ob=di===0?nb-1:0, o0=ob*bw+.25, o1=Math.min(L-.25,(ob+1)*bw-.25), wd=[.40,.26,.18];
      box(o0,o1,0,.62,oz-.35,oz,9,null); box(o0+.06,o1-.06,0,.56,oz,oz+fh-.55,8,null); for(var mq=0;mq<3;mq++){ var ma=o0+.06+(o1-o0-.12)*mq/2; box(ma-.05,ma+.05,.5,.6,oz,oz+fh-.55,9,null); }
      box(o0-.05,o1+.05,0,.7,oz+fh-.55,oz+fh-.3,9,null); }
    if((er===1 || fg.pc===3) && g===1 && hm>6 && hm<14){                         /* a colonial / federal roof: the ridge runs along the street, a dormer in each house, the chimney on the party wall */
      var gz=hm, rz=gz+2.9, gA0=at(-.02,.12), gA1=at(L+.02,.12), gB0=at(-.02,-3.6), gB1=at(L+.02,-3.6), gn=Math.hypot(2.9,3.72); _gdr=_gdg=_gdb=1;
      gquad(b,[gA0[0],gA0[1],zb+gz*K],[gA1[0],gA1[1],zb+gz*K],[gB1[0],gB1[1],zb+rz*K],[gB0[0],gB0[1],zb+rz*K],nx*2.9/gn,ny*2.9/gn,3.72/gn,0,L,0,4.7,5,T);
      var gC0=at(-.02,-7.2), gC1=at(L+.02,-7.2); gquad(b,[gB0[0],gB0[1],zb+rz*K],[gB1[0],gB1[1],zb+rz*K],[gC1[0],gC1[1],zb+gz*K],[gC0[0],gC0[1],zb+gz*K],-nx*2.9/gn,-ny*2.9/gn,3.72/gn,0,L,0,4.7,5,T);
      var du2=L/2, dpk=st.mat+256*(2+3+4*g+128*er); box(du2-.55,du2+.55,-1.6,-.1,gz+.2,gz+2.0,dpk,null);
      var R0=at(du2-.68,.0), R1=at(du2+.68,.0), Rt=at(du2,.0), zr=zb+(gz+2.0)*K, zt2=zb+(gz+2.55)*K, Rb0=at(du2-.68,-1.7), Rb1=at(du2+.68,-1.7), Rbt=at(du2,-1.7);
      gquad(b,[R0[0],R0[1],zr],[Rb0[0],Rb0[1],zr],[Rbt[0],Rbt[1],zt2],[Rt[0],Rt[1],zt2],-dx*.63,-dy*.63,.78,0,1.7,0,.9,5,T);
      gquad(b,[Rt[0],Rt[1],zt2],[Rbt[0],Rbt[1],zt2],[Rb1[0],Rb1[1],zr],[R1[0],R1[1],zr],dx*.63,dy*.63,.78,0,1.7,0,.9,5,T);
      s._fcRoof=1; }
    if(er===2 && g===1 && sd>.72 && hm>8){                                        /* a Second Empire mansard on the front: slate slope, flat top */
      var z0=hm, A0=at(0,.05), A1=at(L,.05), B0=at(0,-1.0), B1=at(L,-1.0), z1=z0+2.5; _gdr=_gdg=_gdb=1;
      var mn=Math.hypot(2.5,1.05); gquad(b,[A0[0],A0[1],zb+z0*K],[A1[0],A1[1],zb+z0*K],[B1[0],B1[1],zb+z1*K],[B0[0],B0[1],zb+z1*K],nx*2.5/mn,ny*2.5/mn,1.05/mn,0,L,0,2.7,5,T);
      var C0=at(0,-3.2), C1=at(L,-3.2); gquad(b,[B0[0],B0[1],zb+z1*K],[B1[0],B1[1],zb+z1*K],[C1[0],C1[1],zb+z1*K],[C0[0],C0[1],zb+z1*K],0,0,1,0,L,0,2.2,5,T);
      for(var dm=0;dm<nb;dm++){ if(nb>2&&dm===1) continue; var uc=(dm+.5)*bw; box(uc-.5,uc+.5,-1.1,-.35,z0+.4,z0+2.1,st.mat+256*(2+3+4*g+128*er),null); box(uc-.62,uc+.62,-1.2,-.25,z0+2.1,z0+2.35,5); } }
    if(er<=3 && hm>5){ var cu=sd<.5?.35:L-.85, ch2=s._fcRoof?4.2:1.5; box(cu,cu+.55,s._fcRoof?-3.9:-6.5,s._fcRoof?-3.0:-5.6,hm,hm+ch2,23); box(cu-.05,cu+.6,s._fcRoof?-3.95:-6.55,s._fcRoof?-2.95:-5.55,hm+ch2-.05,hm+ch2+.1,47); }      /* a chimney stack on the party wall */
  }
  if((g===5||g===6||g===12||g===13||g===15||g===9||g===14) && L>12 && hm>9 && hm<120){ var w=Math.min(5,L*.25), c0=L*(.3+.3*sd); box(c0-w/2,c0+w/2,-6,-2.5,hm,hm+2.2,6); if(L>24) box(L*.7,L*.7+2.5,-9,-6.5,hm,hm+3.2,6); }   /* rooftop plant */
  if(g===9 && L>10){ var a0=L*(.15+.25*sd); box(a0,a0+Math.min(9,L*.4),0,1.6,0,1.15,47); }        /* a loading dock */
  if(g===10 && L>7 && hm>6){                                                                       /* a church front: a square tower at one end with its spire */
    var tw=Math.min(6,Math.max(3.2,L*.3)), t0=sd<.5?0:L-tw, th=hm*1.45+4, c=at(t0+tw/2,-tw/2+.4), pk2=st.mat+256*(2+0+4*10+128*er);
    _gdr=sv[0]; _gdg=sv[1]; _gdb=sv[2]; _gL=tw; _gH=Math.floor(th)+.5/64; gbox(b,c[0],c[1],tw/2*K,tw/2*K,zb,zb+th*K,yaw,pk2,T,false); _gL=0; _gH=0;
    var sh=tw*1.9, P0=at(t0-.15,.55), P1=at(t0+tw+.15,.55), P2=at(t0+tw+.15,-tw+.25), P3=at(t0-.15,-tw+.25), tip=at(t0+tw/2,-tw/2+.4), zt=zb+th*K, zs=zt+sh*K, Q=[P0,P1,P2,P3];
    _gdr=_gdg=_gdb=1; for(var e=0;e<4;e++){ var p=Q[e], q=Q[(e+1)%4]; gtri(b,[p[0],p[1],zt],[q[0],q[1],zt],[tip[0],tip[1],zs],(p[0]+q[0])/2-tip[0],(p[1]+q[1])/2-tip[1],sh*.4*K,0,0,1,0,.5,sh,5,T); } }
  _gdr=sv[0]; _gdg=sv[1]; _gdb=sv[2]; _gH=sv[3]; _gL=sv[4]; }
"""

FS_FACADE = r"""
/* ── facade grammar (palace_ride_facade.py): aux = 2 + role + 4*g + 128*era + 1024*bays; H = floor(m) + (stories+.5)/64 ── */
vec3 fcBrick(vec2 uv, float T, vec2 fp, float flem, vec3 tf){
  vec3 base=vec3(dot(brickPal(T),vec3(.333)))*tf*1.05;          /* the building's own colour (the data's), at brick's brightness */
  float fine=1.-smoothstep(.011,.03,max(fp.x*.5,fp.y));
  float row=floor(uv.y/.0762); float per=flem>.5?.3429:.2286;
  float bx=uv.x/per+.5*mod(row,2.); float cx=floor(bx); float fx=fract(bx)*per;
  float hd=flem>.5?step(fx,.1143):0.;
  float jx=flem>.5?min(min(fx,abs(fx-.1143)),per-fx):min(fx,per-fx);
  float jy=min(fract(uv.y/.0762),1.-fract(uv.y/.0762))*.0762;
  float mort=1.-smoothstep(.004,.012,min(jx*.45,jy));
  vec3 bc=base*(.8+.4*h21(vec2(cx*2.+hd,row)+T*17.)); bc=mix(bc,bc*vec3(.42,.4,.46),hd*.8);        /* Flemish bond: glazed dark headers */
  vec3 mc=vec3(.66,.63,.57);
  vec3 avg=mix(base,base*vec3(.72,.7,.74),flem*.3)*.94+mc*.04;
  float big=nz(uv*.45+T*31.)*.5+nz(uv*.11+T*5.)*.5;
  return mix(avg,mix(bc,mc,mort),fine)*(.88+.24*big); }
/* a double-hung sash window centred at c, half size hs: x glass, y frame, z lintel+sill, w muntins (by era: 6/6 colonial, 2/2 Victorian, 6/1 early modern, one pane after) */
vec4 fcDH(vec2 p, vec2 c, vec2 hs, vec2 fw, float er){
  float w=rectm(p,c,hs,fw); float fr=rectm(p,c,hs+.07,fw)-w;
  float lt=rectm(p,vec2(c.x,c.y+hs.y+.17),vec2(hs.x+(er<2.5?.17:.09),er<2.5?.12:.07),fw); float sl=rectm(p,vec2(c.x,c.y-hs.y-.09),vec2(hs.x+.12,.05),fw);
  vec2 d=p-c; float rail=1.-smoothstep(.022,.022+fw.y,abs(d.y));
  float nx=er<1.5?3.:(er<2.5?2.:(er<3.5?3.:1.)); float ny=er<1.5?2.:1.;
  float px=2.*hs.x/nx; float dxb=abs(fract((d.x+hs.x)/px+.5)-.5)*px; float bxm=nx>1.5?(1.-smoothstep(.014,.014+fw.x,dxb)):0.;
  if(er>2.5&&er<3.5) bxm*=step(0.,d.y);
  float py=hs.y/ny; float dyb=abs(fract((d.y+hs.y)/py+.5)-.5)*py; float bym=ny>1.5?(1.-smoothstep(.014,.014+fw.y,dyb)):0.;
  float mun=clamp(max(rail,max(bxm,bym))*(1.-smoothstep(.15,.6,fw.x*8.)*.6),0.,1.);
  return vec4(w,fr,max(lt,sl),mun*w); }
void facadeG(float type, vec2 uv, float L, float H, float T, vec2 fp, vec3 dc, float aux, vec3 V, vec3 N, out vec3 alb, out vec3 emi, out float refl){
  float q=aux-2.; float role=mod(q,4.); q=floor(q/4.); float g=mod(q,32.); q=floor(q/32.); float er=mod(q,8.); float byN=floor(q/8.);
  float stN=floor(fract(H)*64.); float Hh=max(floor(H),3.);
  bool front=role>.5&&role<1.5; bool party=role>1.5&&role<2.5; bool street=(role>.5&&!party);
  float u=uv.x; float v=uv.y; emi=vec3(0.); refl=0.;
  bool isBrick=type<1.5; bool isStone=type>1.5&&type<2.5; bool isGlass=type>2.5&&type<3.5; bool isConc=type>3.5;
  bool house=g>.5&&g<4.5; bool rowh=g>.5&&g<3.5; bool shopG=(g>6.5&&g<7.5)||g>15.5; bool office=g>11.5&&g<12.5; bool tower=g>4.5&&g<6.5; bool civic=(g>7.5&&g<8.5)||(g>14.5&&g<15.5);
  bool school=g>13.5&&g<14.5; bool rel=g>9.5&&g<10.5; bool ind=g>8.5&&g<9.5; bool park=g>10.5&&g<11.5; bool hotel=g>12.5&&g<13.5;
  bool modern=er>3.5; bool old=er>.5&&er<2.5;
  vec3 tf=clamp(dc/max((dc.r+dc.g+dc.b)/3.,.01),.4,1.8);
  vec3 body;
  if(isBrick) body=fcBrick(uv,T,fp,(er>.5&&er<1.5)?1.:0.,tf); else if(isStone) body=stoneTex(uv,T,fp); else if(isConc) body=concTex(uv,T,fp)*(modern?1.:1.18); else body=vec3(.12,.15,.2);
  body*=mix(vec3(1.),tf,isBrick?0.:(isConc?.8:.5));
  alb=body;
  vec2 fw=vec2(max(fp.x,.012),max(fp.y,.012));
  if(party){ alb=body*.93; return; }                                         /* a party wall: blank brick */
  /* storeys */
  float gh=rowh?3.3:(shopG?4.3:((office||hotel||tower)?(modern?4.6:5.2):((civic||school)?4.4:(ind?5.:(park?3.:3.5)))));
  float fhT=house?3.15:(office?(modern?3.9:3.6):(ind?4.6:(park?3.:((civic||school)?4.2:3.3))));
  float cor=(isGlass||modern)?.35:(rowh?.95:.8);
  if(stN>.5){ fhT=max(2.6,(Hh-cor)/stN); if(rowh) gh=fhT; else gh=max(fhT,min(gh,Hh-cor-(stN-1.)*2.7)); }
  if(rel){ gh=Hh; }
  if(Hh<gh+2.2){ gh=Hh-cor; }
  float nF=max(1.,floor((Hh-gh-cor)/fhT+.5)); float fh=max(2.4,(Hh-gh-cor)/nF);
  bool ground=v<gh; float fi=floor((v-gh)/fh); float vl=(v-gh)-fi*fh;
  /* bays */
  float bwT=house?(L<5.4?L*.5:min(L/3.,2.2)):(ind?4.6:(office&&!modern?3.:((civic||school)?3.8:(rel?4.4:(park?6.:(isGlass?1.5:3.2))))));
  float mg=house?.25:.5; float inner=max(L-2.*mg,.5);
  float nb=(front&&byN>.5)?byN:max(1.,floor(inner/bwT+.5)); float bwa=inner/nb; float uu=u-mg; float bi=floor(uu/bwa); float ul=uu-bi*bwa;
  bool pier=u<mg||u>L-mg;
  float fres=pow(1.-abs(dot(N,V)),3.); float night=uNight; float litP=.16+.34*fract(T*3.1);
  float glM=0.; vec3 glassAlb=vec3(.026,.033,.042); vec3 glEmi=vec3(0.);
  vec3 trim=old?(isBrick?vec3(.82,.80,.74):body*1.14):(er>2.5&&er<3.5?vec3(.70,.66,.58):vec3(.44,.45,.46));
  float fk=fract(T*53.1); vec3 frC=old?vec3(.84,.82,.76):(er<3.5?(fk<.5?vec3(.84,.82,.76):(fk<.75?vec3(.12,.13,.12):vec3(.22,.30,.25))):vec3(.55,.56,.57));
  float lit=step(h21(vec2(fi*7.1+bi*1.31,T*91.)),litP)*night; float blind=step(.72,h21(vec2(fi+bi*3.,T*5.)));
  bool blankB=!street&&(house||shopG)&&h21(vec2(bi*3.+fi,T*7.))<.65;      /* the side and the back of a house: few windows */
  if(!ground && !pier && !blankB && !rel){
    vec2 loc=vec2(ul,vl);
    if(isGlass){
      float spw=.95; float pane=rectm(loc,vec2(bwa*.5,spw+(fh-spw)*.5),vec2(bwa*.5-.04,(fh-spw)*.5-.03),fw); float spand=rectm(loc,vec2(bwa*.5,spw*.5),vec2(bwa*.5-.04,spw*.5-.02),fw);
      vec3 gt=mix(vec3(.30,.42,.50),vec3(.22,.32,.36),fract(T*5.))*mix(vec3(1.),tf,.6); float pv=.85+.3*h21(vec2(fi,bi)+T*3.);
      alb=mix(vec3(.20,.21,.23),gt*.13*pv,pane+spand); alb=mix(alb,gt*.09*pv,spand*(hotel?.2:1.));
      refl=((.34+.42*fres)*pane+.18*spand)*(.8+.3*h21(vec2(fi*1.7,bi*2.3+T*7.)));
      emi=vec3(1.,.84,.56)*(.4+.6*h11(fi*3.+bi))*lit*.7*pane*(office?1.:.8); return; }
    if(park){
      float sp=1.-smoothstep(1.0,1.05,vl); float col=1.-step(.45,ul)*step(ul,bwa-.45);
      alb=mix(vec3(.04,.045,.05)+vec3(.05)*smoothstep(fh-.5,fh-.25,vl),body*1.05,max(sp,col)); emi=vec3(.9,.9,.8)*(1.-max(sp,col))*smoothstep(fh-.45,fh-.3,vl)*(.15+night*.6); return; }
    if(ind){
      float ww=bwa-1.0; float wh=fh-1.7; vec2 c=vec2(bwa*.5,.95+wh*.5); float w=rectm(loc,c,vec2(ww*.5,wh*.5),fw);
      vec2 pq=(loc-c+vec2(ww,wh)*.5)/vec2(.46,.4); float pc=h21(floor(pq)+T*11.); vec2 pf=abs(fract(pq)-.5);
      float bar=(1.-smoothstep(.40,.40+fw.x*2.,max(pf.x*1.,0.)))*0.; bar=smoothstep(.43-fw.x,.47,max(pf.x,pf.y))*(1.-smoothstep(.3,.8,fw.x*4.));
      vec3 pane=pc<.12?vec3(.55,.56,.52):(pc<.2?vec3(.012):vec3(.05,.06,.065)+vec3(.05)*pc);
      float lt=rectm(loc,vec2(c.x,c.y+wh*.5+.16),vec2(ww*.5+.1,.13),fw);
      alb=mix(alb,trim*.85,lt); alb=mix(alb,mix(pane,vec3(.09,.1,.1),bar),w); refl=(.08+.3*fres)*w*(1.-bar)*step(.2,pc);
      alb=mix(alb,alb*1.12,1.-step(.35,ul)*step(ul,bwa-.35)); emi=vec3(1.,.8,.5)*w*(1.-bar)*lit*.5; return; }
    if(school){
      float ww=bwa-.55; float wh=min(fh*.64,2.7); vec2 c=vec2(bwa*.5,.85+wh*.5); float w=rectm(loc,c,vec2(ww*.5,wh*.5),fw);
      vec2 pq=(loc-c+vec2(ww,wh)*.5)/vec2(ww/4.,wh/3.); vec2 pf=abs(fract(pq)-.5); float bar=smoothstep(.44-fw.x,.48,max(pf.x,pf.y));
      float band=rectm(vec2(u,vl),vec2(u,c.y+wh*.5+.2),vec2(1e3,.17),fw); float sil=rectm(vec2(u,vl),vec2(u,c.y-wh*.5-.12),vec2(1e3,.09),fw);
      alb=mix(alb,stonePal(T+.4)*1.08,max(band,sil)); glM=w*(1.-bar); alb=mix(alb,vec3(.86,.84,.78)*.85,w*bar);
      alb=mix(alb,mix(glassAlb,vec3(.42,.40,.33)*.45,blind),glM); refl=(.12+.34*fres)*glM; emi=vec3(1.,.9,.7)*glM*lit*.6; return; }
    if((office&&modern&&isConc)||(g>14.5&&g<15.5)){
      float band=rectm(vec2(u,vl),vec2(u,fh*.55),vec2(1e3,fh*.24),fw); float mu=1.-smoothstep(.03,.03+fw.x,abs(fract(u/1.5+.5)-.5)*1.5);
      glM=band*(1.-mu); alb=mix(alb,vec3(.22,.23,.25),band*mu); alb=mix(alb,mix(vec3(.04,.05,.06),vec3(.35,.38,.4)*.5,blind),glM);
      refl=(.2+.4*fres)*glM; emi=vec3(1.,.9,.72)*glM*lit*.6; return; }
    /* punched windows: houses, apartments, old offices, hotels, the floors over a shop, civic halls */
    float pair=(office&&!modern)||(hotel&&!modern)?1.:0.;
    float ww=house?min(.98,bwa*.46):(civic?min(1.5,bwa*.42):(pair>.5?min(.95,bwa*.27):(tower?max(1.,bwa-.9):(modern?min(1.9,bwa*.62):min(1.05,bwa*.36)))));
    float wh=house?min(fh-1.15,old?1.85:1.7):(civic?min(fh-1.3,2.7):(tower?1.55:(modern?1.5:min(fh-1.2,1.9))));
    float cyw=.95+wh*.5; vec4 m;
    if(pair>.5){ float s1=bwa*.5-ww*.5-.18; vec4 m1=fcDH(loc,vec2(s1,cyw),vec2(ww,wh)*.5,fw,er); vec4 m2=fcDH(loc,vec2(bwa-s1,cyw),vec2(ww,wh)*.5,fw,er); m=max(m1,m2);
      float sp=rectm(loc,vec2(bwa*.5,cyw),vec2(bwa*.5-.15,wh*.5+.05),fw)*(1.-m.x)*(1.-m.y); alb=mix(alb,isBrick?alb*.8:body*.86,sp); }
    else m=fcDH(loc,vec2(bwa*.5,cyw),vec2(ww,wh)*.5,fw,modern?5.:er);
    if(tower){ float sl=rectm(vec2(u,vl),vec2(u,.12),vec2(1e3,.13),fw); alb=mix(alb,body*1.15,sl); alb*=1.-.22*rectm(vec2(u,vl),vec2(u,-.05),vec2(1e3,.12),fw); }
    if(old&&house&&fract(T*7.7)<.6){ float sh=rectm(loc,vec2(bwa*.5-ww*.5-.36,cyw),vec2(.27,wh*.5),fw)+rectm(loc,vec2(bwa*.5+ww*.5+.36,cyw),vec2(.27,wh*.5),fw);       /* louvred shutters */
      vec3 shc=fract(T*3.3)<.6?vec3(.05,.10,.07):vec3(.05,.05,.06); alb=mix(alb,shc*(.85+.3*step(.5,fract(vl/.09))),clamp(sh,0.,1.)); }
    alb=mix(alb,(er>.5&&er<1.5&&isBrick)?body*vec3(.82,.72,.7)*(.9+.2*step(.5,fract(u/.09))):trim,m.z); alb=mix(alb,frC,m.y);
    glM=clamp(m.x-m.w,0.,1.); alb=mix(alb,frC,m.w);
    glassAlb=mix(vec3(.026,.033,.042),vec3(.45,.40,.33)*.45,blind);
    alb=mix(alb,glassAlb,glM); refl=(.12+.36*fres)*glM*(1.-blind*.6)*(.75+.5*h21(vec2(fi*3.1,bi*1.9+T*3.)));
    emi=vec3(1.,.76,.45)*(.45+.5*h11(fi*3.+bi*5.))*lit*.85*glM;
  }
  if(rel && !pier){
    /* a church: lancet windows between buttresses, a rose and a pointed door on the front */
    float bt=1.-step(.38,ul)*step(ul,bwa-.38); alb=mix(alb,body*1.12,bt);
    float lw=min(.75,bwa*.18); float y0=1.6; float y1=max(y0+2.,Hh*.72); vec2 d=vec2(ul-bwa*.5,v);
    float inR=step(abs(d.x),lw)*step(y0,v)*step(v,y1); float ar=length(vec2(abs(d.x)+lw*.6,v-y1)); inR=max(inR,step(y1,v)*step(ar,lw*1.6)*step(abs(d.x),lw));
    float isW=inR*(1.-bt)*(front&&Hh>9.&&abs(u-L*.5)<max(2.6,L*.16)?0.:1.);
    vec3 sg=mix(vec3(.08,.10,.22),vec3(.30,.06,.07),step(.5,h21(floor(vec2(u,v)/.3))))*(.6+.6*h21(floor(vec2(u,v)/.15)+T));
    alb=mix(alb,sg*.6,isW); refl=(.1+.3*fres)*isW; emi=sg*isW*night*.9;
    if(front){ float rr=min(L*.16,2.6); float rc=length(vec2(u-L*.5,v-(Hh*.66))); float rose=1.-smoothstep(rr-.05,rr,rc); float spk=step(.5,fract(atan(v-Hh*.66,u-L*.5)*2.546));
      alb=mix(alb,mix(sg*.6,trim,spk*step(rr*.3,rc)*.6),rose); emi+=sg*rose*night*.8;
      float dw=min(1.3,L*.1); vec2 dd=vec2(u-L*.5,v); float da=step(abs(dd.x),dw)*step(v,2.9)+step(2.9,v)*step(length(vec2(abs(dd.x)+dw*.6,v-2.9)),dw*1.6)*step(abs(dd.x),dw);
      alb=mix(alb,mix(vec3(.18,.10,.06),trim,step(abs(dd.x),dw)*(1.-step(abs(dd.x),dw-.15))),clamp(da,0.,1.)); } }
  if(ground && !pier && !rel){
    vec2 gl=vec2(ul,v);
    if(rowh && front){
      float db=fract(T*17.3)<.5?0.:nb-1.; float sH=er<3.5?.9:.35;
      float wt=1.-smoothstep(sH,sH+.06,v); alb=mix(alb,(er<1.5?vec3(.86,.85,.82):stonePal(T+.3)*.9),wt);       /* the marble / stone water table */
      if(abs(bi-db)<.5){
        float dW=min(.52,bwa*.3); vec2 dc2=vec2(bwa*.5,sH+1.12); float door=rectm(gl,dc2,vec2(dW,1.12),fw); float sur=rectm(gl,dc2+vec2(0.,.3),vec2(dW+.17,1.48),fw)-door;
        float tr=rectm(gl,vec2(bwa*.5,sH+2.25+.24),vec2(dW,.22),fw);
        float dk=fract(T*29.1); vec3 dcol=dk<.25?vec3(.05,.05,.06):dk<.45?vec3(.08,.2,.14):dk<.6?vec3(.34,.07,.07):dk<.75?vec3(.09,.15,.3):dk<.9?vec3(.28,.17,.1):vec3(.55,.53,.47);
        float pnl=rectm(gl,dc2+vec2(-dW*.48,.45),vec2(dW*.3,.42),fw)+rectm(gl,dc2+vec2(dW*.48,.45),vec2(dW*.3,.42),fw)+rectm(gl,dc2+vec2(-dW*.48,-.55),vec2(dW*.3,.4),fw)+rectm(gl,dc2+vec2(dW*.48,-.55),vec2(dW*.3,.4),fw);
        alb=mix(alb,old?vec3(.86,.85,.81):trim*.95,sur); alb=mix(alb,dcol*(1.-.25*clamp(pnl,0.,1.)),door); alb=mix(alb,glassAlb+vec3(.02),tr*(1.-door));
        alb*=1.-.35*rectm(gl,dc2,vec2(dW+.02,1.14),vec2(.12,.12))*(1.-door);
        emi=vec3(1.,.72,.4)*tr*night*.7; refl=(.1+.3*fres)*tr; }
      else {
        vec4 m=fcDH(gl,vec2(bwa*.5,sH+1.42),vec2(min(.98,bwa*.46),1.6)*.5,fw,er); alb=mix(alb,trim,m.z); alb=mix(alb,frC,max(m.y,m.w)); glM=clamp(m.x-m.w,0.,1.);
        glassAlb=mix(vec3(.026,.033,.042),vec3(.45,.40,.33)*.45,step(.6,h21(vec2(bi,T*5.)))); alb=mix(alb,glassAlb,glM); refl=(.1+.34*fres)*glM; emi=vec3(1.,.74,.42)*glM*step(h21(vec2(bi*7.,T*91.)),litP+.1)*night*.8;
        if(sH>.5){ float bsw=rectm(gl,vec2(bwa*.5,sH*.45),vec2(.42,sH*.28),fw); alb=mix(alb,mix(vec3(.02),vec3(.1),step(.5,fract(ul/.13))*.7),bsw); } } }
    else if(street && shopG){
      /* a storefront: piers, a panelled bulkhead, the display glass over a lit room, a transom, the sign band, a recessed door; some shops closed behind a roll-down grille */
      float sg=gh-1.35; float pane=rectm(gl,vec2(bwa*.5,.6+(sg-.6)*.5),vec2(bwa*.5-.22,(sg-.6)*.5),fw); float trn=rectm(gl,vec2(bwa*.5,sg+.18),vec2(bwa*.5-.22,.14),fw);
      float sign=rectm(gl,vec2(bwa*.5,gh-.62),vec2(bwa*.5-.06,.34),fw); float bulk=rectm(gl,vec2(bwa*.5,.3),vec2(bwa*.5-.22,.3),fw);
      float dr=step(.5,h21(vec2(bi,T*13.)))*rectm(gl,vec2(bwa*.5,(sg)*.5),vec2(.5,sg*.5),fw); float mu=rectm(gl,vec2(bwa*.5,.6+(sg-.6)*.5),vec2(.03,(sg-.6)*.5),fw)*(1.-dr);
      float closed=step(.86,fract(T*41.3));
      vec3 sc=mix(mix(vec3(.10,.16,.12),vec3(.12,.15,.28),fract(T*3.3)),mix(vec3(.36,.09,.1),vec3(.08,.08,.09),fract(T*5.1)),step(.5,fract(T*7.7)));
      vec3 inter=mix(vec3(.08,.06,.05),vec3(.36,.27,.17),h21(vec2(bi*3.1,T*17.))*h21(vec2(floor(v*1.7),bi+T)));
      { float shf=1.-smoothstep(.02,.05+fw.y,abs(fract((v-.6)/.42)-.5)*.42-.15); float goods=h21(floor(vec2(u/.23,(v-.6)/.42))+T*5.); float ceil=smoothstep(sg-.5,sg-.1,v);       /* the room behind: shelves of goods, a lit ceiling */
        inter=mix(inter*(.55+.9*goods*goods)*mix(vec3(1.),vec3(.9,.7,.5)+vec3(.4)*fract(goods*7.),.5),inter*.4,shf*.8); inter=mix(inter,vec3(.6,.56,.5),ceil*.25); }
      vec3 bk=fract(T*19.)<.5?sc*.8:stonePal(T+.5)*.66;
      alb=mix(alb,sc*.8,sign); alb=mix(alb,bk*(1.-.18*rectm(gl,vec2(bwa*.5,.3),vec2(bwa*.5-.4,.18),vec2(.03))),bulk); alb=mix(alb,vec3(.08,.08,.08),trn*.5);
      float gm=pane*(1.-mu); vec3 gls=mix(inter*.24+vec3(.006),vec3(.03),dr*.6);
      vec3 gri=vec3(.42,.43,.44)*(.8+.25*step(.5,fract(v/.09)));
      alb=mix(alb,mix(gls,gri,closed),gm); alb=mix(alb,vec3(.1,.1,.1),mu);
      refl=(.03+.12*fres*fres)*gm*(1.-closed); emi=vec3(1.,.84,.58)*inter*gm*(1.-closed)*(night*2.2+.10)+sc*sign*night*.4+vec3(.9,.85,.7)*trn*night*.3*(1.-closed); }
    else if(street && (office||hotel||tower||g>4.5&&g<5.5||civic||school) && !isGlass){
      /* a stone base: rusticated courses, tall windows, the lobby glass on the front */
      vec3 st=stonePal(T+.6)*(isBrick?.95:1.05); float rus=1.-smoothstep(.0,.03+fw.y,abs(fract(v/.48)-.5)*.48-.2); alb=mix(st,st*.7,rus*.6*(1.-smoothstep(.3,1.,fw.y*10.)));
      float ww=min(1.4,bwa*.5); float w=rectm(gl,vec2(bwa*.5,gh*.5+.2),vec2(ww*.5,gh*.32),fw); float lob=front?rectm(vec2(u,v),vec2(L*.5,1.6),vec2(min(3.2,L*.18),1.6),fw):0.;
      glM=max(w,lob); alb=mix(alb,mix(vec3(.05,.055,.06),vec3(.3,.24,.16)*.45,lob),glM); refl=(.12+.34*fres)*glM; emi=vec3(1.,.82,.55)*(lob*(.25+night*1.6)+w*lit*.6)*glM; }
    else if(street && ind){
      float ld=step(.55,h21(vec2(bi,T*21.)))*rectm(gl,vec2(bwa*.5,1.9),vec2(min(1.7,bwa*.38),1.9),fw); float rib=step(.5,fract(v/.16));
      alb=mix(alb,vec3(.40,.41,.40)*(.82+.2*rib),ld); alb=mix(alb,alb*1.1,1.-step(.35,ul)*step(ul,bwa-.35));
      float w=(1.-ld)*rectm(gl,vec2(bwa*.5,gh*.6),vec2(bwa*.5-.6,gh*.22),fw); alb=mix(alb,vec3(.05,.06,.065),w); refl=(.1+.3*fres)*w; }
    else if(!(isGlass) && !(house&&!street&&h21(vec2(bi*5.,T*9.))<.7)){
      float ww=house?min(.98,bwa*.46):min(1.1,bwa*.38); vec4 m=fcDH(gl,vec2(bwa*.5,gh*.5+.15),vec2(ww,min(gh-1.2,1.7))*.5,fw,modern?5.:er);
      alb=mix(alb,trim,m.z); alb=mix(alb,frC,max(m.y,m.w)); glM=clamp(m.x-m.w,0.,1.); alb=mix(alb,glassAlb,glM); refl=(.1+.34*fres)*glM; emi=vec3(1.,.74,.42)*glM*lit*.8; }
    else if(isGlass){ float pane=rectm(vec2(mod(u-mg,1.5),v),vec2(.75,gh*.5),vec2(.7,gh*.5-.15),fw); alb=mix(vec3(.18,.19,.21),vec3(.06,.07,.08),pane); refl=(.14+.34*fres)*pane; emi=vec3(.3,.22,.14)*pane*(night*2.2+.04); }
  }
  /* the cornice: wood / pressed metal on houses and shops (dentils, brackets at the ends), stone on the rest; a shadow line under it */
  if(!isGlass){
    float c0=Hh-cor; float cb=smoothstep(c0,c0+.04,v);
    alb*=1.-.3*(1.-smoothstep(0.,.5,c0-v))*step(v,c0);
    vec3 cc=(rowh||shopG)?(fract(T*61.)<.5?vec3(.80,.78,.72):(fract(T*61.)<.8?vec3(.16,.15,.14):vec3(.36,.24,.17))):mix(trim,body,.3)*1.04;
    if(modern) cc=body*1.06;
    alb=mix(alb,cc,cb);
    if(cb>.5 && !modern){ float dent=step(.5,fract(u/.24))*(1.-smoothstep(c0+.12,c0+.16,v)); float br=(rowh||shopG)?(1.-step(.3,u)*step(u,L-.3))*(1.-step(c0+.75,v)):0.;
      alb*=1.-.22*dent*(1.-smoothstep(.4,1.6,fp.x*10.)); alb=mix(alb,cc*.8,br); alb*=.94+.08*smoothstep(c0+.3,c0+.34,v); emi=vec3(0.); refl=0.; }
  }
}
"""
