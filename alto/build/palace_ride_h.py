"""Part H of the first-person ride: detailed landmark models in the shared mesh format (owner: the landmarks agent).

Each landmark of the city (City Hall, Independence Hall, the Art Museum, the stations, the Convention Center, the towers, the courthouses, the arena and the two
grounds) gets a model of its real silhouette, SIMPLIFIED and cheap (a few thousand vertices, built once per world), in the proportions of the lead's 2D art
(palace_skyline.py / palace_towers.py: the specs are the same, in metres) and standing where that art stands: centred across its block, its front (street) face
on the block's front edge (south), City Hall centred in its block, the grounds scaled down only as far as it takes to fit their block.

MATERIALS (palace_ride_mesh.py MAT) as these models use them, for the renderer's facade shader:
  stone / brick / brickred / concrete / glass   walls WITH windows: the shader draws the window grid from u,v. Every wall's u,v are "shader metres" = real metres x k,
                                                 k = 3.4 / the building's real storey height, so the shader's 3.4 m floor is the building's own storey (City Hall 8 m, the
                                                 Art Museum 12 m ...). brickred is also the red granite of Three Logan Square; stone is the limestone of the courthouses/stations.
  white                                          plain pale stone or marble WITHOUT windows: columns, cornices, pilasters, pediments, City Hall's tower, the steeple
  dark                                           openings: doors, arches, window panes cut into a wall (decals 0.12 m off the wall), the recess behind a colonnade
  copper (verdigris) / roof (slate) / tile / metal / wood / paving / grass / asphalt   as named; metal = steel, bronze, glass-and-steel frames, light masts, spires
  glassdome                                      the glass of the Convention Center vault and the Jefferson Station hall
All faces are oriented outward (see palace_ride_mesh.py WINDING). The u of a wall runs to the viewer's right, v is the height above the ground.

landmarkMeshes(l, floors, W) keeps the extruded stand-in (lmSolids -> W.solids, for the 2D fallback) and, when it has a model for l, pushes {a, id: l.n} to W.meshes and
marks the stand-in solids `.mesh=1` (the GL renderer must not extrude those: the model replaces them).
"""

JS_H_KIT = r"""
/* ══ LANDMARKS (palace_ride_h.py): detailed models in the shared mesh format ══ */
var LMV=1.3;                                                  /* map units per metre: UM */
function lmKey(n){ n=String(n||'');
  var T=[['usch',/byrne|601 market|united states court ?house.*philadelphia/i],['nix',/\bnix\b|900 market/i],['cjc',/criminal justice center|1301 filbert/i],['fam',/family court/i],['ind',/independence hall/i],['city',/city hall/i],
    ['art',/art museum|museum of art|philadelphia museum/i],['frank',/franklin institute/i],['conv',/convention cent(er|re)/i],['stn',/(30th|thirtieth) street station/i],['sub',/suburban station/i],['jef',/jefferson station/i],
    ['lff',/lincoln financial/i],['cbp',/citizens bank park/i],['arena',/xfinity mobile arena|wells fargo center|\barena\b|spectrum/i],['stad',/\bstadium\b|ballpark|\bfield$/i],
    ['lib1',/one liberty place|liberty place one|liberty one/i],['lib2',/two liberty place|liberty place two|liberty two/i],['ccc',/comcast center(?! tech)|comcast building/i],['ctc',/comcast tech/i],
    ['bny',/bny mellon|mellon bank center|mellon center/i],['tls',/three logan square|3 logan square/i],['cira',/cira centre(?! south)|cira center(?! south)/i],['fmc',/fmc tower/i],
    ['court',/court ?house|courts? building|justice cent(er|re)|hall of justice|supreme court|court of appeals/i]];
  for(var i=0;i<T.length;i++) if(T[i][1].test(n)) return T[i][0]; return 'gen'; }


/* the shader picks a wall's palette from the building's tint T: stone by fract(T*3.77) (<.3 warm grey, <.55 grey, <.8 tan, else pale limestone), brick by fract(T*7.31) (<.5 red-brown ... ), glass by
   fract(T*5) (blue ... teal): a landmark scans for a tint that gives it its real colours. cons = {s:[lo,hi], b:[lo,hi], g:[lo,hi]} */
function lmPickTint(F,cons){ if(!cons) return F.tint; var t0=F.tint, fr=function(x){ return x-Math.floor(x); };
  for(var i=0;i<4000;i++){ var T=fr(t0+i*0.00137); if((!cons.s||(fr(T*3.77)>=cons.s[0]&&fr(T*3.77)<=cons.s[1])) && (!cons.b||(fr(T*7.31)>=cons.b[0]&&fr(T*7.31)<=cons.b[1])) && (!cons.g||(fr(T*5)>=cons.g[0]&&fr(T*5)<=cons.g[1]))) return T; }
  return F.tint; }
/* the local frame of one landmark: metres x (across, east), v (back from the front edge, north), z (up); S = map units per metre */
function lmFrame(l, S, centred, depthM, front){
  var b=l.box, cx=(b[0]+b[2])/2, fy=b[3]-11-Math.max(3,(front||0)*S);      /* the front face stands on the block's front edge, less what steps and canopies push out (the street is 11 units each side of the edge) */
  if(centred) fy=(b[1]+b[3])/2+depthM*S/2;
  var F={m:MB.mk(), S:S, cx:cx, fy:fy, box:b, tint:hashXY(cx,(b[1]+b[3])/2), n:0, fp:[]};
  F.m.o=[cx,fy];
  F.X=function(x){ return F.cx+x*S; }; F.Y=function(v){ return F.fy-v*S; }; F.Z=function(z){ return z*S; };
  return F; }
/* footprints for the stand-in solids (roaming collides with them; the 2D fallback draws them): a local rectangle with its height in metres, or a ring of local [x,v] pairs */
function lfoot(F,x0,v0,x1,v1,hM){ F.fp.push({r:[F.X(x0),F.Y(v0),F.X(x1),F.Y(v0),F.X(x1),F.Y(v1),F.X(x0),F.Y(v1)], h:hM*F.S}); }
function lfootRing(F,pts,hM){ F.fp.push({r:lring(F,pts), h:hM*F.S}); }
/* an axis-aligned block: centre x, front plane v0, w across, d deep, from z0 to z1; skip bits: 1 front 2 back 4 east 8 west 16 top */
function lbox(F,x,v0,w,d,z0,z1,wm,tm,k,skip){ MB.slab(F.m,F.X(x-w/2),F.Y(v0+d),F.Z(z0),F.X(x+w/2),F.Y(v0),F.Z(z1),wm,tm,F.tint,k||1,skip||0); }
function lrect(F,x0,v0,x1,v1,z0,z1,wm,tm,k,skip){ lbox(F,(x0+x1)/2,v0,x1-x0,v1-v0,z0,z1,wm,tm,k,skip); }
/* a ring of local [x,v] pairs -> map ring */
function lring(F,pts){ var o=[]; for(var i=0;i<pts.length;i++){ o.push(F.X(pts[i][0]),F.Y(pts[i][1])); } return o; }
/* a hip / mansard roof over a local rectangle: tiers in metres [[inset,rise],..] */
function lroof(F,x0,v0,x1,v1,z,tiers,mat,k,top){ var t=tiers.map(function(q){ return [q[0]*F.S,q[1]*F.S]; }); return MB.roofTiers(F.m,F.X(x0),F.Y(v1),F.X(x1),F.Y(v0),F.Z(z),t,mat,F.tint,k||1,top==null?mat:top)/F.S; }
/* a gable roof, ridge along x (axis 'x') or along v ('v'); rise in metres; the hipped ends are NOT built: it sits on walls the caller closes */
function lgable(F,x0,v0,x1,v1,z,rise,axis,mat,k){ var m=F.m, X0=F.X(x0), X1=F.X(x1), Y0=F.Y(v1), Y1=F.Y(v0), Z0=F.Z(z), Z1=F.Z(z+rise), mx=(X0+X1)/2, my=(Y0+Y1)/2, F_=MB.face, t=F.tint;
  if(axis==='x'){ F_(m,[[X0,Y1,Z0],[X1,Y1,Z0],[X1,my,Z1],[X0,my,Z1]],[0,Z1-Z0,(Y1-Y0)/2],mat,t,k); F_(m,[[X0,Y0,Z0],[X1,Y0,Z0],[X1,my,Z1],[X0,my,Z1]],[0,-(Z1-Z0),(Y1-Y0)/2],mat,t,k);
    F_(m,[[X0,Y0,Z0],[X0,Y1,Z0],[X0,my,Z1]],[-1,0,0],mat,t,k); F_(m,[[X1,Y0,Z0],[X1,Y1,Z0],[X1,my,Z1]],[1,0,0],mat,t,k); }
  else { F_(m,[[X1,Y0,Z0],[X1,Y1,Z0],[mx,Y1,Z1],[mx,Y0,Z1]],[Z1-Z0,0,(X1-X0)/2],mat,t,k); F_(m,[[X0,Y0,Z0],[X0,Y1,Z0],[mx,Y1,Z1],[mx,Y0,Z1]],[-(Z1-Z0),0,(X1-X0)/2],mat,t,k);
    F_(m,[[X0,Y0,Z0],[X1,Y0,Z0],[mx,Y0,Z1]],[0,-1,0],mat,t,k); F_(m,[[X0,Y1,Z0],[X1,Y1,Z0],[mx,Y1,Z1]],[0,1,0],mat,t,k); } }
/* a column row: n columns from x0 to x1 (centres) at depth v, from z0 to z1, shaft radius r metres */
function lcols(F,x0,x1,v,n,z0,z1,r,mat,k,seg){ for(var i=0;i<n;i++){ var x=n>1?x0+(x1-x0)*i/(n-1):x0; MB.col(F.m,F.X(x),F.Y(v),F.Z(z0),F.Z(z1),r*F.S,seg||8,mat,F.tint,k||1); } }
/* a light column: a tapering 6-sided shaft and an abacus (for colonnades seen from far) */
function lcolLite(F,x,v,z0,z1,r,mat){ var cx=F.X(x), cy=F.Y(v), R=r*F.S, a=[], b=[]; for(var i=0;i<6;i++){ var t=i/6*6.2832; a.push(cx+Math.cos(t)*R,cy+Math.sin(t)*R); b.push(cx+Math.cos(t)*R*.82,cy+Math.sin(t)*R*.82); }
  MB.loft(F.m,a,F.Z(z0),b,F.Z(z1-r*.8),mat,F.tint,1); MB.slab(F.m,cx-R*1.35,cy-R*1.35,F.Z(z1-r*.8),cx+R*1.35,cy+R*1.35,F.Z(z1),mat,mat,F.tint,1,0); }
/* a horizontal band round a local rectangle: projecting `pr` metres, from z0 to z1 */
function lband(F,x0,v0,x1,v1,z0,z1,pr,mat,skip){ lrect(F,x0-pr,v0-pr,x1+pr,v1+pr,z0,z1,mat,mat,1,skip||0); }
/* a decal on a face: dir = 's' (front, v small), 'n' (back), 'e', 'w'; (x,v) the centre of the wall point, z the base; pts [u,v] in METRES (u to the viewer's right) */
var LDIR={s:[0,1],n:[0,-1],e:[1,0],w:[-1,0]};
function ldecal(F,dir,x,v,z,pts,mat,off){ var d=LDIR[dir], S=F.S; MB.decal(F.m,F.X(x),F.Y(v),F.Z(z),d[0],d[1],pts.map(function(q){ return [q[0]*S,q[1]*S]; }),mat,F.tint,(off==null?.3:off),1); }
function lopen(mat){ return mat==='dark'?'glass':mat==='void'?'dark':mat; }                   /* openings: 'dark' is a pane of reflective glass (doors, windows); 'void' is a real shadow (a portal) */
function larch(F,dir,x,v,z,w,h,mat,off){ ldecal(F,dir,x,v,z,MB.archPts(w,h,8),lopen(mat),off); }
function lrectd(F,dir,x,v,z,w,h,mat,off){ ldecal(F,dir,x,v,z,[[-w/2,0],[w/2,0],[w/2,h],[-w/2,h]],lopen(mat),off); }
function lcircle(F,dir,x,v,zc,r,mat,off){ ldecal(F,dir,x,v,zc,MB.circPts(r,16),mat,off); }
/* a clock face: a pale disc in a dark rim with two hands */
function lclock(F,dir,x,v,zc,r){ lcircle(F,dir,x,v,zc,r*1.12,'dark',.3); lcircle(F,dir,x,v,zc,r,'lamp',.42); ldecal(F,dir,x,v,zc,[[-.12*r,0],[.12*r,0],[.07*r,.78*r],[-.07*r,.78*r]],'dark',.55); ldecal(F,dir,x,v,zc,[[0,-.11*r],[.62*r,.2*r],[.6*r,.3*r],[0,.1*r]],'dark',.55); }
/* a gabled dormer standing out of a roof face: dir 's','n','e','w'; (x,v) its front, z the sill; w wide, h wall height, rise of its little roof */
function ldormer(F,dir,x,v,z,w,h,rise,depth,wm,rm,glass){ var d=LDIR[dir], S=F.S, m=F.m, t=F.tint, cx=F.X(x), cy=F.Y(v), rx=d[1], ry=-d[0], hw=w/2*S, H=h*S, R=rise*S, D=depth*S, z0=F.Z(z), F_=MB.face;
  var A=[cx-rx*hw,cy-ry*hw,z0], B=[cx+rx*hw,cy+ry*hw,z0], A1=[A[0],A[1],z0+H], B1=[B[0],B[1],z0+H], T=[cx,cy,z0+H+R], bx=-d[0]*D, by=-d[1]*D;
  F_(m,[A,B,B1,T,A1],[d[0],d[1],0],wm,t,1);
  F_(m,[A,[A[0]+bx,A[1]+by,z0],[A1[0]+bx,A1[1]+by,z0+H],A1],[-rx,-ry,0],wm,t,1); F_(m,[B,[B[0]+bx,B[1]+by,z0],[B1[0]+bx,B1[1]+by,z0+H],B1],[rx,ry,0],wm,t,1);
  F_(m,[A1,T,[T[0]+bx,T[1]+by,z0+H+R],[A1[0]+bx,A1[1]+by,z0+H]],[-rx*R,-ry*R,hw],rm,t,1); F_(m,[B1,T,[T[0]+bx,T[1]+by,z0+H+R],[B1[0]+bx,B1[1]+by,z0+H]],[rx*R,ry*R,hw],rm,t,1);
  if(glass) ldecal(F,dir,x,v,z+h*.12,[[-w*.3,0],[w*.3,0],[w*.3,h*.7],[-w*.3,h*.7]],lopen(glass),.3); }
/* a small solid dome / ogee as a lathe: points are [r,z] in METRES about local (x,v) */
function llathe(F,x,v,prof,seg,mat,soft,k){ MB.lathe(F.m,F.X(x),F.Y(v),prof.map(function(q){ return [q[0]*F.S,q[1]*F.S]; }),seg||12,mat,F.tint,k||1,soft!==false); }
/* a paved or grassed ground patch over a local rectangle (a plaza, a lawn) a hair above the ground tiles */
function lpatch(F,x0,v0,x1,v1,z,mat){ MB.cap(F.m,lring(F,[[x0,v0],[x1,v0],[x1,v1],[x0,v1]]),F.Z(z),mat,F.tint,1); }
function lpatchBox(F,mat,inset,z){ var b=F.box, i=inset; MB.cap(F.m,[b[0]+i,b[1]+i,b[2]-i,b[1]+i,b[2]-i,b[3]-i,b[0]+i,b[3]-i],F.Z(z),mat,F.tint,1); }
function lsteps(F,dir,x,v,w,n,rise,tread,z,mat){ var d=LDIR[dir]; MB.steps(F.m,F.X(x),F.Y(v),d[0],d[1],w*F.S,n,rise*F.S,tread*F.S,F.Z(z),mat,F.tint,1); }
/* a superellipse / rounded plan as local [x,v] pairs: w across, d deep, front edge on v=0, exponent e */
function lsuper(w,d,e,n,cv){ var o=[]; cv=cv==null?d/2:cv; for(var i=0;i<n;i++){ var t=6.2832*i/n, c=Math.cos(t), s=Math.sin(t); o.push([w/2*Math.sign(c)*Math.pow(Math.abs(c),2/e), cv+d/2*Math.sign(s)*Math.pow(Math.abs(s),2/e)]); } return o; }
/* the ring moved in by d metres (a counter-clockwise ring of [x,v]) */
function linset(R,d){ var n=R.length, o=[]; for(var i=0;i<n;i++){ var p=R[(i+n-1)%n], a=R[i], b=R[(i+1)%n], tx=b[0]-p[0], tv=b[1]-p[1], L=Math.hypot(tx,tv)||1, dd=typeof d==='function'?d(a[0],a[1]):d; o.push([a[0]-tv/L*dd, a[1]+tx/L*dd]); } return o; }
function lccw(R){ var s=0; for(var i=0;i<R.length;i++){ var a=R[i], b=R[(i+1)%R.length]; s+=a[0]*b[1]-b[0]*a[1]; } return s>0?R:R.slice().reverse(); }
"""

JS_H_CITY = r"""
/* ── City Hall: Second Empire, white marble, four wings round a courtyard, a copper-green mansard on every wing, the 167 m tower with Penn on top (148 x 145 m) ── */
function bCityHall(F){
  var k=3.4/8, ST='stone', WH='white', CP='copper', CO='concrete', i, x, v;
  lpatchBox(F,'paving',11,.1); lpatch(F,-38,36,38,109,.15,'paving');
  var bodies=[[-74,0,74,36],[-74,109,74,145],[-74,36,-38,109],[38,36,74,109]];
  bodies.forEach(function(r){ lrect(F,r[0]-1,r[1]-1,r[2]+1,r[3]+1,0,3.4,CO,CO,1,16);                 /* the granite base */
    lrect(F,r[0],r[1],r[2],r[3],0,34,ST,null,k); lband(F,r[0],r[1],r[2],r[3],16.2,17.2,.5,WH); lband(F,r[0],r[1],r[2],r[3],33.2,34.9,1.3,WH); lroof(F,r[0],r[1],r[2],r[3],34.9,[[4.5,8.5],[3,1.2]],CP,1); });
  /* corner pavilions: taller, with paired pilasters and a high mansard */
  [[-74,0,-38,36],[38,0,74,36],[-74,109,-38,145],[38,109,74,145]].forEach(function(r){ lrect(F,r[0],r[1],r[2],r[3],0,39,ST,null,k); lband(F,r[0],r[1],r[2],r[3],16.2,17.2,.5,WH); lband(F,r[0],r[1],r[2],r[3],38.2,39.9,1.4,WH); lroof(F,r[0],r[1],r[2],r[3],39.9,[[5,10],[3,2]],CP,1);
    var sx=r[0]<0?-1:1, sv=r[1]<50?-1:1, xo=sx<0?r[0]:r[2], vo=sv<0?r[1]:r[3];                    /* the two outer faces */
    [-1,1].forEach(function(e){ var xa=xo+(-sx)*(e<0?1.6:34.4), va=vo+(-sv)*(e<0?1.6:34.4);
      lrect(F,xa-.9,vo-(sv>0?0:1.2),xa+.9,vo+(sv>0?1.2:0),3.4,38.2,WH,WH,1,16);                       /* on the long (E-W) face */
      lrect(F,xo-(sx>0?0:1.2),va-.9,xo+(sx>0?1.2:0),va+.9,3.4,38.2,WH,WH,1,16); });                  /* on the N-S face */
    lband(F,r[0]+.01,r[1]+.01,r[2]-.01,r[3]-.01,9.4,10.2,.4,WH);
    var xm=(r[0]+r[2])/2, vm=(r[1]+r[3])/2;                                                         /* a projecting central bay with a pediment on each outer face */
    var fdir=sv<0?'s':'n', fv=vo+(sv<0?-1.4:1.4), sdir=sx<0?'w':'e', sxo=xo+(sx<0?-1.4:1.4);
    lrect(F,xm-6,Math.min(vo,fv),xm+6,Math.max(vo,fv),3.4,38.2,ST,ST,k,16); lrect(F,xo<sxo?xo:sxo,vm-6,xo<sxo?sxo:xo,vm+6,3.4,38.2,ST,ST,k,16);
    [-6,6].forEach(function(e){ lrect(F,xm+e-.7,Math.min(vo,fv)-.3*(sv<0?1:0),xm+e+.7,Math.max(vo,fv)+.3*(sv<0?0:1),3.4,38.4,WH,WH,1,16); lrect(F,Math.min(xo,sxo)-.3*(sx<0?1:0),vm+e-.7,Math.max(xo,sxo)+.3*(sx<0?0:1),vm+e+.7,3.4,38.4,WH,WH,1,16); });
    MB.pediment(F.m,F.X(xm),F.Y(fv),LDIR[fdir][0],LDIR[fdir][1],F.Z(39.9),14*F.S,3.6*F.S,5*F.S,WH,CP,F.tint,1); MB.pediment(F.m,F.X(sxo),F.Y(vm),LDIR[sdir][0],LDIR[sdir][1],F.Z(39.9),14*F.S,3.6*F.S,5*F.S,WH,CP,F.tint,1); });
  /* the midway pavilions of the side wings */
  [[-76,54,-38,90],[38,54,76,90]].forEach(function(r){ lrect(F,r[0],r[1],r[2],r[3],0,38,ST,null,k); lband(F,r[0],r[1],r[2],r[3],37.2,38.9,1.3,WH); lroof(F,r[0],r[1],r[2],r[3],38.9,[[4.5,9],[3,1.5]],CP,1);
    var xo=r[0]<0?r[0]:r[2], d=r[0]<0?-1:1; [57,87].forEach(function(vv){ lrect(F,xo-(d>0?0:1.1),vv-.9,xo+(d>0?1.1:0),vv+.9,3.4,37.2,WH,WH,1,16); }); lrect(F,xo-(d>0?0:1.1),71,xo+(d>0?1.1:0),73,3.4,37.2,WH,WH,1,16);
    larch(F,d<0?'w':'e',xo,72,3.4,6,14,'dark',.4); MB.pediment(F.m,F.X(xo+d*1.1),F.Y(72),d,0,F.Z(38.9),24*F.S,4.4*F.S,5*F.S,WH,CP,F.tint,1); });
  /* the south entrance: a pavilion with eight columns, the arch of the Broad Street portal, steps */
  lrect(F,-22,-8,22,0,0,3.4,CO,CO,1,0);
  lrect(F,-20,-2,20,20,0,38,ST,null,k); lband(F,-20,-2,20,20,37.2,38.9,1.3,WH); lroof(F,-20,-2,20,20,38.9,[[5,8],[3,1.5]],CP,1);
  larch(F,'s',0,-2,3.4,11,17,'white',.3); larch(F,'s',0,-2,3.4,9,15,'void',.45);
  lcols(F,-16.5,16.5,-6.2,8,3.4,35,.85,WH,1,8); lrect(F,-20,-7.6,20,-4.6,35,37.2,WH,WH,1,0);
  lsteps(F,'s',0,-8,40,7,3.4/7,.75,3.4,CO);
  /* the tower: a stone foot (the Broad Street arches north and south), then stages of white marble */
  lrect(F,-16,111,16,143,0,34.9,ST,null,k); lband(F,-16,111,16,143,33.2,34.9,1.3,WH); larch(F,'n',0,143,3.4,11,17,'white',.3); larch(F,'n',0,143,3.4,9,15,'void',.45); larch(F,'s',0,111,3.4,11,17,'white',.3); larch(F,'s',0,111,3.4,9,15,'void',.45);
  var tc=127, hw=13.5, z;
  function stage(h2,z0,z1,tex){ lrect(F,-h2,tc-h2,h2,tc+h2,z0,z1,WH,WH,1,0); }
  stage(13.5,34.9,62); lband(F,-13.5,tc-13.5,13.5,tc+13.5,60.8,62.4,1.4,WH);
  stage(12.5,62.4,102); lband(F,-12.5,tc-12.5,12.5,tc+12.5,100.4,102.2,1.5,WH); lband(F,-12.5,tc-12.5,12.5,tc+12.5,84,85.2,.8,WH);
  function faces(h2,fn){ fn('s',0,tc-h2); fn('n',0,tc+h2); fn('e',h2,tc); fn('w',-h2,tc); }
  faces(13.5,function(dr,xx,vv){ var along=(dr==='s'||dr==='n')?0:1; [-8,0,8].forEach(function(o){ var x2=along?xx:xx+o, v2=along?vv+o:vv; larch(F,dr,x2,v2,40,3.4,11,'dark'); larch(F,dr,x2,v2,52.5,3.4,7,'dark'); }); });
  faces(12.5,function(dr,xx,vv){ var along=(dr==='s'||dr==='n')?0:1; [-7,0,7].forEach(function(o){ var x2=along?xx:xx+o, v2=along?vv+o:vv; larch(F,dr,x2,v2,67,3,11,'dark'); larch(F,dr,x2,v2,87,3,8,'dark'); }); });
  [[-13.5,tc-13.5],[13.5,tc-13.5],[-13.5,tc+13.5],[13.5,tc+13.5]].forEach(function(c){ lrect(F,c[0]-1.1,c[1]-1.1,c[0]+1.1,c[1]+1.1,34.9,62,WH,WH,1,16); });
  [[-12.5,tc-12.5],[12.5,tc-12.5],[-12.5,tc+12.5],[12.5,tc+12.5]].forEach(function(c){ lrect(F,c[0]-1,c[1]-1,c[0]+1,c[1]+1,62.4,100.4,WH,WH,1,16); });
  stage(11.5,102.2,117); faces(11.5,function(dr,xx,vv){ lclock(F,dr,xx,vv,109.5,5.2); });
  [[-11.5,tc-11.5],[11.5,tc-11.5],[-11.5,tc+11.5],[11.5,tc+11.5]].forEach(function(c){ lrect(F,c[0]-1.2,c[1]-1.2,c[0]+1.2,c[1]+1.2,102.2,117,WH,WH,1,16); });
  lband(F,-11.5,tc-11.5,11.5,tc+11.5,115.6,117.2,1.2,WH); lband(F,-11.5,tc-11.5,11.5,tc+11.5,117.2,118.4,.5,WH);
  lrect(F,-7.5,tc-7.5,7.5,tc+7.5,117.2,130.2,'dark','dark',1,16);                                      /* the open drum: a dark core inside a ring of columns */
  for(i=0;i<5;i++){ var c=-8+i*4; lcolLite(F,c,tc-8,118.4,130.2,.55,WH); lcolLite(F,c,tc+8,118.4,130.2,.55,WH); if(i>0&&i<4){ lcolLite(F,-8,tc+c,118.4,130.2,.55,WH); lcolLite(F,8,tc+c,118.4,130.2,.55,WH); } }
  lrect(F,-9.4,tc-9.4,9.4,tc+9.4,130.2,131.8,WH,WH,1,0);
  llathe(F,0,tc,[[8.4,131.8],[8.7,133.2],[8.5,135.4],[7.9,137.8],[6.8,140.2],[5.4,142.5],[3.8,144.5],[2.5,146.2],[1.9,147.4],[1.9,148.4],[2.3,148.7],[2.3,149.4],[1.6,150.2],[.5,152]],14,CP);
  lrect(F,-2.2,tc-2.2,2.2,tc+2.2,152,155.6,WH,WH,1,0);
  llathe(F,0,tc,[[1.2,155.6],[1.35,158.4],[1.05,162],[.85,164],[1.15,165],[.5,165.8]],8,'metal');                       /* William Penn, in bronze: robe, shoulders, head, hat */
  llathe(F,0,tc,[[.7,165],[.85,165.8],[.7,166.5],[0,167]],8,'metal'); llathe(F,0,tc,[[1.5,166.2],[1.5,166.4],[0,166.6]],10,'metal'); lrect(F,-.4,tc-4,.4,tc-1,162,163,'metal','metal',1,0);
  /* dormers on the outer faces of the wings */
  [-34,-28,-22].concat([22,28,34]).forEach(function(xx){ ldormer(F,'s',xx,-0+.8,35.6,2.2,3.4,1.3,3.6,WH,CP,'dark'); });
  [-34,-28,-22].concat([22,28,34]).forEach(function(xx){ ldormer(F,'n',xx,145-.8,35.6,2.2,3.4,1.3,3.6,WH,CP,'dark'); });
  [-1,1].forEach(function(sd){ [40,46,50,94,99,104].forEach(function(vv){ ldormer(F,sd<0?'w':'e',sd*74-sd*.8,vv,35.6,2.2,3.4,1.3,3.6,WH,CP,'dark'); }); });
  lfoot(F,-74,0,74,36,45); lfoot(F,-74,109,74,145,45); lfoot(F,-74,36,-38,109,45); lfoot(F,38,36,74,109,45); lfoot(F,-16,111,16,143,167);
  return F.m; }
"""


JS_H_KIT2 = r"""
/* ── more shapes shared by the models ── */
/* a barrel vault running along v from v0 to v1, springing at z0, h high, w wide centred on x: glass or metal skin, end arches of capMat */
function lvault(F,x,w,v0,v1,z0,h,mat,capMat,seg){ seg=seg||14; var m=F.m, a=w/2, P=[], i, t=F.tint, S=F.S;
  for(i=0;i<=seg;i++){ var th=i/seg*3.14159; P.push([x+a*Math.cos(th), z0+h*Math.sin(th), th]); }
  for(i=0;i<seg;i++){ var p=P[i], q=P[i+1], tm=(p[2]+q[2])/2;
    MB.face(m,[[F.X(p[0]),F.Y(v0),F.Z(p[1])],[F.X(q[0]),F.Y(v0),F.Z(q[1])],[F.X(q[0]),F.Y(v1),F.Z(q[1])],[F.X(p[0]),F.Y(v1),F.Z(p[1])]],[Math.cos(tm)/a,0,Math.sin(tm)/h],mat,t,1); }
  var ring=P.map(function(q){ return [F.X(q[0]),F.Y(v0),F.Z(q[1])]; }), ring2=P.map(function(q){ return [F.X(q[0]),F.Y(v1),F.Z(q[1])]; });
  if(capMat!=null){ MB.face(m,ring,[0,1,0],capMat,t,1); MB.face(m,ring2,[0,-1,0],capMat,t,1); } }
/* a square-plan crown of two crossing gable roofs (Liberty Place): the box walls and a gable roof each way */
function lcross(F,x,v,w,z,wall,rise,mat){ lbox(F,x,v-w/2,w,w,z,z+wall,mat,null,1,16); lgable(F,x-w/2,v-w/2,x+w/2,v+w/2,z+wall,rise,'x',mat,1); lgable(F,x-w/2,v-w/2,x+w/2,v+w/2,z+wall,rise,'v',mat,1); }
/* walls over a map-unit ring with a bottom and a top height (metres) per vertex */
function lwallZ(F,R,zb,zt,mat,k){ var n=R.length/2, sg=MB.area(R)>0?1:-1, Z=F.Z; for(var i=0;i<n;i++){ var j=(i+1)%n, dx=R[2*j]-R[2*i], dy=R[2*j+1]-R[2*i+1];
    MB.face(F.m,[[R[2*i],R[2*i+1],Z(zb[i])],[R[2*j],R[2*j+1],Z(zb[j])],[R[2*j],R[2*j+1],Z(zt[j])],[R[2*i],R[2*i+1],Z(zt[i])]],[dy*sg,-dx*sg,0],mat,F.tint,k||1); } }
/* a sloped ring between an outer and inner map ring, each vertex with its own height (metres); out is up (or down) */
function lbandZ(F,rO,zO,rI,zI,mat,k,dn){ var n=rO.length/2, Z=F.Z, s=dn?-1:1; for(var i=0;i<n;i++){ var j=(i+1)%n;
    MB.face(F.m,[[rO[2*i],rO[2*i+1],Z(zO[i])],[rO[2*j],rO[2*j+1],Z(zO[j])],[rI[2*j],rI[2*j+1],Z(zI[j])],[rI[2*i],rI[2*i+1],Z(zI[i])]],[0,0,s],mat,F.tint,k||1); } }
function lconst(n,v){ var o=[]; for(var i=0;i<n;i++) o.push(v); return o; }
/* a floodlight mast: a slim shaft and a bank of lamps */
function lmast(F,x,v,z0,z1,w,bank){ lbox(F,x,v-w/2,w,w,z0,z1,'metal','metal',1,0); lbox(F,x,v-bank*.5,bank,bank*.45,z1-bank*.55,z1+bank*.3,'dark','lamp',1,0); }
/* a ring of map points from a local ring: z-constant helper */
function lmap(F,R){ return lring(F,R); }
/* the point of a local ring farthest toward the direction deg (from +x toward +v), moved in by `inset` metres */
function lon(R,deg,inset){ var cx=0,cv=0,i; R.forEach(function(q){ cx+=q[0]; cv+=q[1]; }); cx/=R.length; cv/=R.length; var ux=Math.cos(deg*Math.PI/180), uv=Math.sin(deg*Math.PI/180), best=R[0], bd=-1e9;
  R.forEach(function(q){ var d=(q[0]-cx)*ux+(q[1]-cv)*uv; if(d>bd){ bd=d; best=q; } }); var L=Math.hypot(best[0]-cx,best[1]-cv)||1, kk=Math.max(0,1-inset/L); return [cx+(best[0]-cx)*kk, cv+(best[1]-cv)*kk]; }
/* a parapet ring (4 thin walls) round a local rectangle on a flat roof */
function lparapet(F,x0,v0,x1,v1,z,h,t,mat){ lrect(F,x0,v0,x1,v0+t,z,z+h,mat,mat,1,0); lrect(F,x0,v1-t,x1,v1,z,z+h,mat,mat,1,0); lrect(F,x0,v0+t,x0+t,v1-t,z,z+h,mat,mat,1,0); lrect(F,x1-t,v0+t,x1,v1-t,z,z+h,mat,mat,1,0); }
/* roof gear: n deterministic boxes (air handlers, stair and lift housings) on a flat roof rectangle */
function lgear(F,x0,v0,x1,v1,z,n,seed){ var t=Math.floor(F.tint*9973), i; for(i=0;i<n;i++){ var r1=hash(t+i*17+(seed||0)*131), r2=hash(t+i*29+7+(seed||0)*131), r3=hash(t+i*43+3+(seed||0)*131), r4=hash(t+i*61+11+(seed||0)*131);
    var w=2.4+r3*4.6, d=2+r4*3.6, h=1.4+r1*2.4, x=x0+w/2+1+(x1-x0-w-2)*r1, v=v0+1+(v1-v0-d-2)*r2; if(x1-x0<w+3||v1-v0<d+3) continue; lbox(F,x,v,w,d,z,z+h,'metal','metal',1,0); } }
/* a canopy slab pushed out of a face: dir 's','n','e','w'; (x,v) the centre on the wall, w wide along the wall, d out from it, at height z, with two slim posts */
function lcanopy(F,dir,x,v,w,d,z,mat){ var o=LDIR[dir], ax=Math.abs(o[0]), x0, x1, v0, v1;
  if(ax===0){ x0=x-w/2; x1=x+w/2; if(o[1]>0){ v0=v-d; v1=v; } else { v0=v; v1=v+d; } } else { v0=v-w/2; v1=v+w/2; if(o[0]>0){ x0=x; x1=x+d; } else { x0=x-d; x1=x; } }
  lrect(F,x0,v0,x1,v1,z,z+.5,mat||'white','metal',1,0); var px=ax===0?[x0+.6,x1-.6]:[(o[0]>0?x1-.6:x0+.6),(o[0]>0?x1-.6:x0+.6)], pv=ax===0?[(o[1]>0?v0+.6:v1-.6),(o[1]>0?v0+.6:v1-.6)]:[v0+.6,v1-.6];
  for(var i=0;i<2;i++) lrect(F,px[i]-.25,pv[i]-.25,px[i]+.25,pv[i]+.25,0,z,'metal','metal',1,16); }
/* faceted glass: a wall from corner a to corner b (local [x,v]) whose top at each end is za / zb (metres): nu x nv panels, the odd ones pushed `bump` metres out along dir (['s','n','e','w']) */
function lfacets(F,a,b,za,zb,nu,nv,bump,dir,mat){ var d=LDIR[dir], S=F.S, m=F.m, i, j, G=[];
  for(i=0;i<=nu;i++){ G.push([]); var t=i/nu, x=a[0]+(b[0]-a[0])*t, v=a[1]+(b[1]-a[1])*t, zt=za+(zb-za)*t;
    for(j=0;j<=nv;j++){ var o=(((i+j)&1)&&i>0&&i<nu&&j>0&&j<nv)?bump:0; G[i].push([F.X(x)+d[0]*o*S, F.Y(v)+d[1]*o*S, F.Z(zt*j/nv)]); } }
  for(i=0;i<nu;i++) for(j=0;j<nv;j++) MB.face(m,[G[i][j],G[i+1][j],G[i+1][j+1],G[i][j+1]],[d[0],d[1],0],mat,F.tint,1); }
"""

JS_H_CIVIC = r"""
/* ── Independence Hall: red Flemish-bond brick, white trim, a hipped roof with its pairs of chimneys, the arcades and the two end buildings, the brick tower and the white steeple (104 x 22 m, 51 m) ── */
function bIndependence(F){
  var k=3.4/6.5, BR='brick', WH='white', RF='roof', i;
  lpatchBox(F,'grass',11,.08); lpatch(F,-70,-8,70,2,.14,'paving'); lpatch(F,-4,0,4,100,.14,'paving'); lpatch(F,-60,40,60,43,.14,'paving');
  /* the main building: two storeys and an attic under a hipped roof, a white belt and cornice */
  lrect(F,-16.5,8,16.5,22,0,13,BR,null,k); lband(F,-16.5,8,16.5,22,6.2,6.7,.4,WH); lband(F,-16.5,8,16.5,22,12.2,13.4,.7,WH); lband(F,-16.5,8,16.5,22,0,.9,.4,WH);
  lroof(F,-16.5,8,16.5,22,13.4,[[5.2,5.8]],RF,1);
  [[-9,11.6],[9,11.6],[-9,18.4],[9,18.4]].forEach(function(c){ lrect(F,c[0]-.9,c[1]-.9,c[0]+.9,c[1]+.9,15,20.5,'brickred',WH,k,0); lrect(F,c[0]-1.1,c[1]-1.1,c[0]+1.1,c[1]+1.1,20.5,21.1,WH,WH,1,0); });
  /* the arcades (the "hyphens") and the end buildings: Congress Hall and Old City Hall */
  [-1,1].forEach(function(sd){ var xa=sd*27;
    lrect(F,xa-6,12,xa+6,18,0,6.5,BR,null,k); lband(F,xa-6,12,xa+6,18,5.9,6.7,.4,WH); lroof(F,xa-6,12,xa+6,18,6.7,[[2.4,1.8]],RF,1);
    [-3.6,0,3.6].forEach(function(o){ larch(F,'s',xa+o,12,0,2.3,4.6,'dark'); });
    var xe=sd*43; lrect(F,xe-9,2,xe+9,22,0,11,BR,null,3.4/5.5); lband(F,xe-9,2,xe+9,22,5.2,5.7,.4,WH); lband(F,xe-9,2,xe+9,22,10.2,11.1,.7,WH); lroof(F,xe-9,2,xe+9,22,11.1,[[5.5,4.4]],RF,1);
    larch(F,'s',xe,2,0,2.2,4,'dark'); lbox(F,xe,.6,3.2,1.4,0,.5,WH,WH,1,0); });
  /* the tower: brick to 29 m with its great arched window, then the white wooden stages */
  lrect(F,-4.5,0,4.5,9,0,29,BR,null,3.4/6); lband(F,-4.5,0,4.5,9,17.2,17.8,.4,WH); lband(F,-4.5,0,4.5,9,28.2,29.4,.7,WH);
  larch(F,'s',0,0,18.6,4.4,9.6,'white',.3); larch(F,'s',0,0,19.4,3.2,8.6,'dark',.5); larch(F,'s',0,0,.3,3.6,6,'white',.3); larch(F,'s',0,0,.5,2.8,5.2,'dark',.5);
  lsteps(F,'s',0,0,5,3,.18,.5,.55,'concrete');
  lrect(F,-4,.5,4,8.5,29.4,34.6,WH,WH,1,0); [['s',0,.5],['n',0,8.5],['e',4,4.5],['w',-4,4.5]].forEach(function(q){ lclock(F,q[0],q[1],q[2],32,1.9); });
  lband(F,-4,.5,4,8.5,34.6,35.4,.5,WH);
  var oc=[],oi=[]; for(i=0;i<8;i++){ var t=(i+.5)/8*6.2832; oc.push([Math.cos(t)*3.4,4.5+Math.sin(t)*3.4]); }
  MB.loft(F.m,lring(F,oc),F.Z(35.4),lring(F,oc),F.Z(36.6),WH,F.tint,1);
  MB.loft(F.m,lring(F,oc.map(function(q){ return [q[0]*.8,4.5+(q[1]-4.5)*.8]; })),F.Z(36.6),lring(F,oc.map(function(q){ return [q[0]*.8,4.5+(q[1]-4.5)*.8]; })),F.Z(39.2),'dark',F.tint,1);
  for(i=0;i<8;i++){ var t2=i/8*6.2832; lcolLite(F,Math.cos(t2)*3.5,4.5+Math.sin(t2)*3.5,36.6,39.2,.28,WH); }
  MB.loft(F.m,lring(F,oc.map(function(q){ return [q[0]*1.1,4.5+(q[1]-4.5)*1.1]; })),F.Z(39.2),lring(F,oc.map(function(q){ return [q[0]*1.1,4.5+(q[1]-4.5)*1.1]; })),F.Z(40.4),WH,F.tint,1,WH);
  llathe(F,0,4.5,[[3.5,40.4],[3.6,41.3],[3.1,42.5],[2.1,43.5],[1.4,44.2],[1.4,44.8],[1.1,45],[1.1,46.5],[.9,46.9],[.3,48.2],[.12,49.6],[.1,51]],10,WH);
  llathe(F,0,4.5,[[.45,46.6],[.5,47.0],[.35,47.4],[0,47.5]],8,'metal');
  lfoot(F,-16.5,8,16.5,22,19); lfoot(F,-4.5,0,4.5,9,51); [-1,1].forEach(function(sd){ lfoot(F,sd*27-6,12,sd*27+6,18,8); lfoot(F,sd*43-9,2,sd*43+9,22,15); });
  return F.m; }

/* ── Philadelphia Museum of Art: the U of tan limestone, three Greek temple fronts, blue-green tiled roofs, the long steps (196 x 110 m, 36 m) ── */
function bArt(F){
  var k=3.4/13, ST='stone', WH='white', CP='copper', CO='concrete';
  lpatchBox(F,'grass',11,.08); lpatch(F,-70,24,70,56,.16,'paving'); lpatch(F,-100,-10,100,2,.16,'paving');
  /* the central block with its temple front on the court */
  lrect(F,-62,66,62,110,0,27,ST,null,k); lband(F,-62,66,62,110,26,27.6,.9,WH); lroof(F,-62,66,62,110,27.6,[[8,6.2]],CP,1);
  lrect(F,-30,53,30,66,0,3.2,CO,CO,1,0); lrect(F,-30,56,30,66,3.2,27,ST,null,k);
  lcols(F,-26,26,54.4,8,3.2,24.2,1.15,WH,1,8); lrect(F,-31,53,31,66,24.2,27.4,WH,WH,1,0);
  MB.pediment(F.m,F.X(0),F.Y(53),0,1,F.Z(27.4),31*2*F.S,9*F.S,13*F.S,WH,CP,F.tint,1);
  larch(F,'s',0,56,3.2,6,11,'dark'); lsteps(F,'s',0,53,56,8,.4,.75,3.2,CO);
  /* the long wings forward to the end pavilions */
  [-1,1].forEach(function(sd){ var xa=sd*80; lrect(F,xa-13,20,xa+13,110,0,21,ST,null,k); lband(F,xa-13,20,xa+13,110,20.2,21.5,.9,WH); lroof(F,xa-13,20,xa+13,110,21.5,[[5,4.4]],CP,1);
    var xp=sd*84; lrect(F,xp-14,0,xp+14,24,0,23,ST,null,k); lband(F,xp-14,0,xp+14,24,22.2,23.6,.9,WH); lroof(F,xp-14,0,xp+14,24,23.6,[[6,3.4]],CP,1);
    lrect(F,xp-15,-5,xp+15,0,0,2.4,CO,CO,1,0); lcols(F,xp-10,xp+10,-2.2,4,2.4,21.6,1.05,WH,1,8); lrect(F,xp-15,-3.6,xp+15,0,21.6,23.8,WH,WH,1,0);
    MB.pediment(F.m,F.X(xp),F.Y(-3.6),0,1,F.Z(23.8),30*F.S,5.6*F.S,10*F.S,WH,CP,F.tint,1); lsteps(F,'s',xp,-5,24,4,.6,.8,2.4,CO); larch(F,'s',xp,0,2.4,5,10,'dark'); });
  lfoot(F,-62,53,62,110,36); [-1,1].forEach(function(sd){ lfoot(F,sd*80-13,20,sd*80+13,110,26); lfoot(F,sd*84-14,-3,sd*84+14,24,29); });
  return F.m; }

/* ── The Franklin Institute: a limestone block, the six-column Ionic portico and pediment, the green dome of the Franklin memorial (110 x 70 m, 38 m) ── */
function bFranklin(F){
  var k=3.4/9.5, ST='stone', WH='white', CP='copper', CO='concrete';
  lpatchBox(F,'paving',11,.1);
  lrect(F,-55,8,55,70,0,19,ST,null,k); lband(F,-55,8,55,70,18,19.8,.9,WH); lrect(F,-55,8,55,70,19.8,20.6,ST,ST,1,0);
  lrect(F,-18,18,18,54,19.8,26,ST,null,k); lband(F,-18,18,18,54,25,26.6,.8,WH);
  llathe(F,0,36,[[17,26.6],[17.2,28],[16.4,30.4],[14.6,33],[11.4,35.4],[7,37.2],[3,38],[.3,38.5]],20,CP);
  lrect(F,-25,0,25,9,0,21,ST,null,k); lrect(F,-25,-6,25,0,0,2.6,CO,CO,1,0); lcols(F,-19,19,-1.8,6,2.6,19.6,1.05,WH,1,8); lrect(F,-26,-3.2,26,3,19.6,21.6,WH,WH,1,0);
  MB.pediment(F.m,F.X(0),F.Y(-3.2),0,1,F.Z(21.6),54*F.S,7*F.S,12*F.S,WH,'roof',F.tint,1); larch(F,'s',0,0,2.6,6,10,'dark'); lsteps(F,'s',0,-6,50,6,.43,.8,2.6,CO);
  lfoot(F,-55,8,55,70,26); lfoot(F,-18,18,18,54,38); lfoot(F,-25,-3,25,9,28);
  return F.m; }

/* ── 30th Street Station: the long Neoclassical block of pale stone, a front of giant columns, a cornice and a low roof, a lower wing at each end with its own colonnade (190 x 100 m, 36 m) ── */
function bStation(F){
  var k=3.4/12, ST='stone', WH='white', RF='roof', CO='concrete', i;
  lpatchBox(F,'paving',11,.1);
  lrect(F,-46,6,46,100,0,29,ST,null,k); lrect(F,-46,0,46,6.2,29,29.8,WH,WH,1,0);
  for(i=0;i<9;i++){ var xw=-37.3+i*9.3; lrectd(F,'s',xw,6,3,5.2,17.5,'dark'); }
  lcols(F,-42,42,1.8,10,1.6,27,1.45,WH,1,8);
  lrect(F,-47,-.6,47,6.6,27,29.8,WH,WH,1,0); lrect(F,-48,-1.6,48,6.8,29.8,31.6,WH,WH,1,0); lroof(F,-45,6,45,94,31.6,[[24,3.6]],RF,1);
  lrect(F,-44,-4,44,0,0,1.6,CO,CO,1,0); lsteps(F,'s',0,-4,60,4,.4,.9,1.6,CO);
  [-1,1].forEach(function(sd){ var xa=sd*70; lrect(F,xa-25,3,xa+25,100,0,23,ST,null,3.4/11); lrect(F,xa-26,-.6,xa+26,3.4,23,25,WH,WH,1,0); lrect(F,xa-26,3,xa+26,100,25,25.6,ST,RF,1,0);
    lcols(F,xa-18,xa+18,1.5,5,1.6,21.6,1.1,WH,1,8); for(i=0;i<4;i++) lrectd(F,'s',xa-13.5+i*9,3.4,3,4.2,15,'dark'); });
  larch(F,'s',0,6,3,9,14,'dark',.5);
  lfoot(F,-46,0,46,100,35); lfoot(F,-95,0,-45,100,25); lfoot(F,45,0,95,100,25);
  return F.m; }

/* ── Penn Center Suburban Station: the 1930 Art Deco limestone tower over the commuter station: a broad base, two setbacks and a small slate cap (92 x 46 m, 78 m) ── */
function bSuburban(F){
  var k=3.4/6.5, ST='stone', WH='white', RF='roof', i;
  lpatchBox(F,'paving',11,.1);
  lrect(F,-46,0,46,46,0,40,ST,null,k); lband(F,-46,0,46,46,38.4,40.4,1,WH); lband(F,-46,0,46,46,5.6,6.4,.5,WH);
  for(i=0;i<12;i++){ var xp=-45+i*8.18; lrect(F,xp-1,-.6,xp+1,.4,6.4,38.4,WH,WH,1,16); }
  lrect(F,-33,7,33,39,40,60,ST,null,k); lband(F,-33,7,33,39,58.4,60.4,.9,WH); for(i=0;i<9;i++){ var x2=-32+i*8; lrect(F,x2-.9,6.4,x2+.9,7.4,40.4,58.4,WH,WH,1,16); }
  lrect(F,-21,12,21,34,60,73,ST,null,k); lband(F,-21,12,21,34,71.6,73.4,.8,WH); for(i=0;i<6;i++){ var x3=-20+i*8; lrect(F,x3-.8,11.4,x3+.8,12.4,60.4,71.6,WH,WH,1,16); }
  lroof(F,-20,13,20,33,73.4,[[8,3],[2,1.6]],RF,1);
  larch(F,'s',0,0,0,8,9,'dark'); lbox(F,0,-3,22,3,0,4,'white','metal',1,0); lcols(F,-9,9,-1.5,4,0,4,.4,WH,1,6);
  lfoot(F,-46,0,46,46,40); lfoot(F,-33,7,33,39,60); lfoot(F,-21,12,21,34,78);
  return F.m; }

/* ── Jefferson Station: a broad glass concourse with a stepped glazed hall and skylight over its middle and a columned canopy at the entrance (100 x 50 m, 22 m) ── */
function bJefferson(F){
  var G='glass', GD='glassdome', i;
  lpatchBox(F,'paving',11,.1);
  lrect(F,-50,6,50,50,0,10,G,'metal',3.4/5,0); lrect(F,-31,12,31,40,10,16,G,'metal',3.4/5,0); lroof(F,-31,12,31,40,16,[[14,6]],GD,1);
  lbox(F,0,-9,44,9,7,8.6,'white','metal',1,0); lcols(F,-20,20,-6,5,0,7,.45,'metal',1,6);
  larch(F,'s',0,6,0,9,6,'dark'); for(i=0;i<8;i++) lrect(F,-49+i*14,5.4,-48.3+i*14,6,0,10,'metal','metal',1,0);
  lrect(F,-50,0,50,6,0,.6,'concrete','concrete',1,0);
  lfoot(F,-50,6,50,50,10); lfoot(F,-31,12,31,40,22);
  return F.m; }

/* ── Pennsylvania Convention Center: the Reading Terminal headhouse of red brick under a mansard, the sloping glass lobby, the great halls under barrel vaults (250 x 190 m, 40 m) ── */
function bConvention(F){
  var BR='brick', i;
  lpatchBox(F,'paving',11,.1);
  lrect(F,-125,44,125,190,0,21,'metal',null,1); lrect(F,-125,44,125,190,21,21.6,'metal','roof',1,0);
  [-84,84].forEach(function(xa){ lvault(F,xa,74,52,182,21.6,11.4,'glassdome','metal',14); }); lvault(F,0,82,40,190,21.6,18.4,'glassdome','metal',16);
  /* the headhouse */
  lrect(F,-100,0,-24,44,0,30,BR,null,3.4/7.5); [8,16,24].forEach(function(z){ lband(F,-100,0,-24,44,z-.3,z+.3,.4,'white'); }); lband(F,-100,0,-24,44,29,30.8,1,'white'); lroof(F,-100,0,-24,44,30.8,[[13,10]],'roof',1);
  [-92,-84,-76,-68,-56,-48,-40,-32].forEach(function(xx,j){ larch(F,'s',xx,0,3,3,10,'dark'); larch(F,'s',xx,0,15,3,8,'dark'); });
  larch(F,'s',-62,0,0,9,12,'white',.3); larch(F,'s',-62,0,0,7.6,11,'dark',.5);
  [-90,-76,-48,-34].forEach(function(xx){ ldormer(F,'s',xx,2.6,32,2.6,3.6,1.5,3.5,'white','roof','dark'); });
  /* the sloping glass lobby on Arch Street */
  var m=F.m, Z=F.Z, X=F.X, Y=F.Y, x0=-12, x1=116, v0=0, v1=38, z0=12, z1=27, t=F.tint;
  MB.face(m,[[X(x0),Y(v0),Z(0)],[X(x1),Y(v0),Z(0)],[X(x1),Y(v0),Z(z1)],[X(x0),Y(v0),Z(z0)]],[0,1,0],'glass',t,3.4/7);
  MB.face(m,[[X(x1),Y(v0),Z(0)],[X(x1),Y(v1),Z(0)],[X(x1),Y(v1),Z(z1)],[X(x1),Y(v0),Z(z1)]],[1,0,0],'glass',t,3.4/7);
  MB.face(m,[[X(x0),Y(v0),Z(0)],[X(x0),Y(v1),Z(0)],[X(x0),Y(v1),Z(z0)],[X(x0),Y(v0),Z(z0)]],[-1,0,0],'glass',t,3.4/7);
  MB.face(m,[[X(x0),Y(v0),Z(z0)],[X(x1),Y(v0),Z(z1)],[X(x1),Y(v1),Z(z1)],[X(x0),Y(v1),Z(z0)]],[0,0,1],'glassdome',t,1);
  for(i=0;i<9;i++){ var xs=x0+i*(x1-x0)/8, zs=z0+(z1-z0)*i/8; lrect(F,xs-.3,-.3,xs+.3,.3,0,zs,'metal','metal',1,0); }
  lbox(F,52,-6,30,7,9,10.6,'white','metal',1,0); lcols(F,40,64,-4,3,0,9,.4,'metal',1,6);
  lfoot(F,-125,44,125,190,40); lfoot(F,-100,0,-24,44,40); lfoot(F,-12,0,116,38,27);
  return F.m; }
"""

JS_H_TOWERS = r"""
/* ── the skyscrapers: each a podium, a shaft that tapers or steps back, and its own crown (heights, plans and floor counts from palace_skyline.py / palace_towers.py) ── */
var LMFL={lib1:61,lib2:58,ccc:57,ctc:60,bny:54,tls:55,cira:29,fmc:49};
function sq(F,x,v,hw,hd){ return [F.X(x-hw),F.Y(v-hd),F.X(x+hw),F.Y(v-hd),F.X(x+hw),F.Y(v+hd),F.X(x-hw),F.Y(v+hd)]; }   /* a rectangle ring about (x,v), half sizes hw hd (metres) */
function bandRing(F,hw,hd,x,v,z0,z1,pr,mat){ lrect(F,x-hw-pr,v-hd-pr,x+hw+pr,v+hd+pr,z0,z1,mat,mat,1,0); }
function ktw(F,top,pod){ return 3.4*(LMFL[F.key]||40)/(top-(pod||0)); }                /* uv scale so the shader's 3.4 m floor is this tower's real floor */
function bLiberty(F,o){                                   /* o: p podium, tw tower width, sets [[z0,z1,w],..] setbacks, crown0/crown [[w,wall]..], tip */
  var c=o.p/2, kt=ktw(F,o.crown0,14), hp=o.p/2, tw=o.tw; lpatchBox(F,'paving',11,.1);
  lbox(F,0,0,o.p,o.p,0,14,'stone',null,3.4/7,16); lparapet(F,-hp,0,hp,o.p,14,1.1,.5,'white'); lbox(F,0,0,o.p,o.p,13.9,14.1,'stone','roof',3.4/7,31-16);
  lband(F,-hp,0,hp,o.p,6.6,7.2,.4,'white');
  lbox(F,0,c-tw/2,tw,tw,14,o.sets[0][0],'glass',null,kt,16);
  o.sets.forEach(function(st){ var w=st[2]; lbox(F,0,c-w/2,w,w,st[0],st[1],'glass','roof',kt,0); });
  [.28,.5,.72].forEach(function(f){ var zz=14+(o.sets[0][0]-14)*f; bandRing(F,tw/2,tw/2,0,c,zz,zz+1.4,.5,'stone'); });
  lgear(F,-hp+2,2,hp-2,(c-tw/2)-1,14.1,3,1); lgear(F,-hp+2,c+tw/2+1,hp-2,o.p-2,14.1,3,2);
  larch(F,'s',0,0,0,10,9,'dark',.4); lcanopy(F,'s',0,0,16,4.2,9.4,'white'); larch(F,'s',-21,0,0,5,6,'dark',.4); larch(F,'s',21,0,0,5,6,'dark',.4);
  var y=o.crown0, ap=y;
  o.crown.forEach(function(q){ var w=q[0], wall=q[1], rise=w*.42; lcross(F,0,c,w,y,wall,rise,'glass'); ap=y+wall+rise; y=y+wall+rise*.55; });
  llathe(F,0,c,[[1.3,ap-3],[.9,ap+8],[.4,ap+(o.tip-ap)*.6],[.1,o.tip]],8,'metal');
  lfoot(F,-hp,0,hp,o.p,14); lfoot(F,-tw/2,c-tw/2,tw/2,c+tw/2,o.tip);
  return F.m; }
function bLib1(F){ return bLiberty(F,{p:64,tw:50,sets:[[176,204,42],[204,222,34]],crown0:222,crown:[[34,4],[27,4],[20,3],[13,3]],tip:288}); }
function bLib2(F){ return bLiberty(F,{p:56,tw:42,sets:[[194,214,34]],crown0:214,crown:[[32,4],[23,3],[14,3]],tip:258}); }
function bComcast(F){
  var kt=ktw(F,297,22); lpatchBox(F,'paving',11,.1);
  lbox(F,0,0,70,56,0,22,'glass',null,3.4/3.7,16); lbox(F,0,0,70,56,21.9,22.1,'glass','roof',1,15); lgear(F,-33,2,33,6,22.1,2,3);
  lbox(F,0,8,52,40,22,238,'glass',null,kt,16);
  MB.loft(F.m,sq(F,0,28,26,20),F.Z(238),sq(F,0,28,23,20),F.Z(279),'glass',F.tint,kt,'roof');
  lbox(F,0,11,44,34,279,297,'glass','roof',kt,0);
  lrect(F,-25.8,7.4,-23.4,48.6,22,238,'white','white',1,16); lrect(F,23.4,7.4,25.8,48.6,22,238,'white','white',1,16);
  larch(F,'s',0,0,0,14,10,'dark',.4); lcanopy(F,'s',0,0,24,5,10.4,'white');
  lfoot(F,-35,0,35,56,22); lfoot(F,-26,8,26,48,297);
  return F.m; }
/* X-bracing bands on a tapering tower (half width hw0 at za, hw1 at zb; plan half depth hd about v=vc) */
function lbracing(F,hw0,hw1,za,zb,vc,hd,n){
  function hwAt(z){ return hw0+(hw1-hw0)*(z-za)/(zb-za); }
  for(var i=0;i<n;i++){ var z0=za+(zb-za)*i/n, z1=za+(zb-za)*(i+1)/n, wa=hwAt(z0), wb=hwAt(z1);
    [[-1,1],[1,-1]].forEach(function(sg){ var xa=sg[0]*wa, xb=sg[1]*wb;
      [['s',vc-hd-.4],['n',vc+hd+.4]].forEach(function(f){ var o=LDIR[f[0]]; MB.face(F.m,[[F.X(xa-.7),F.Y(f[1]),F.Z(z0)],[F.X(xa+.7),F.Y(f[1]),F.Z(z0)],[F.X(xb+.7),F.Y(f[1]),F.Z(z1)],[F.X(xb-.7),F.Y(f[1]),F.Z(z1)]],[o[0],o[1],0],'metal',F.tint,1); });
      [['e',1],['w',-1]].forEach(function(f){ var o=LDIR[f[0]], xe0=f[1]*(wa+.4), xe1=f[1]*(wb+.4), va=vc+sg[0]*hd, vb=vc+sg[1]*hd;
        MB.face(F.m,[[F.X(xe0),F.Y(va-.7),F.Z(z0)],[F.X(xe0),F.Y(va+.7),F.Z(z0)],[F.X(xe1),F.Y(vb+.7),F.Z(z1)],[F.X(xe1),F.Y(vb-.7),F.Z(z1)]],[o[0],o[1],0],'metal',F.tint,1); }); }); } }
function bCTC(F){
  var hw0=23, hw1=20.5, za=20, zb=304, vc=25, kt=ktw(F,304,20);
  lpatchBox(F,'paving',11,.1);
  lbox(F,0,0,92,50,0,20,'stone',null,3.4/5,16); lparapet(F,-46,0,46,50,20,1.1,.5,'white'); lbox(F,0,0,92,50,19.9,20.1,'stone','roof',3.4/5,15);
  for(var i=0;i<9;i++){ lrect(F,-44+i*11,-.7,-43+i*11,.3,0,20,'white','white',1,16); }
  MB.loft(F.m,sq(F,0,vc,hw0,20),F.Z(za),sq(F,0,vc,hw1,20),F.Z(zb),'glass',F.tint,kt,'roof');
  lbracing(F,hw0,hw1,za,zb,vc,20,5); lgear(F,-44,2,44,4.4,20.1,2,5);
  [-16,-8,0,8,16].forEach(function(x,j){ var tops=[318,330,342,330,318]; lbox(F,x,vc-1.6,4.4,3.2,zb,tops[j],'glass','glass',1,0); });
  larch(F,'s',0,0,0,12,10,'dark',.4); lcanopy(F,'s',0,0,22,5,10.6,'white');
  lfoot(F,-46,0,46,50,20); lfoot(F,-23,5,23,45,342);
  return F.m; }
function bBNY(F){
  var kt=ktw(F,199,20); lpatchBox(F,'paving',11,.1);
  lbox(F,0,0,66,66,0,20,'stone',null,3.4/5,16); lparapet(F,-33,0,33,66,20,1.1,.5,'white'); lbox(F,0,0,66,66,19.9,20.1,'stone','roof',3.4/5,15);
  MB.loft(F.m,sq(F,0,33,27,27),F.Z(20),sq(F,0,33,21,21),F.Z(199),'glass',F.tint,kt,null);
  bandRing(F,23,23,0,33,199,204,0,'white'); lroof(F,-22,11,22,55,204,[[22,29]],'metal',1,'metal');
  llathe(F,0,33,[[.9,232],[.6,236],[.15,241]],6,'metal'); lgear(F,-32,2,32,5.5,20.1,2,6);
  larch(F,'s',0,0,0,12,9,'dark',.4); lcanopy(F,'s',0,0,20,5,9.6,'white');
  lfoot(F,-33,0,33,66,20); lfoot(F,-27,6,27,60,241);
  return F.m; }
function bTLS(F){
  var i, kt=ktw(F,205,14); lpatchBox(F,'paving',11,.1);
  lbox(F,0,0,58,58,0,14,'brick','roof',3.4/4.2,0);
  lbox(F,0,7,44,44,14,188,'brick',null,kt,16); lbox(F,0,11,36,36,188,205,'brick',null,kt,16); lrect(F,-22.6,6.4,22.6,51.6,187.4,189,'brick','brick',kt,0);
  var c=29, hw=16, cut=8, R=[-hw+cut,c-hw,hw-cut,c-hw,hw,c-hw+cut,hw,c+hw-cut,hw-cut,c+hw,-hw+cut,c+hw,-hw,c+hw-cut,-hw,c-hw+cut], Rm=[]; for(i=0;i<R.length;i+=2) Rm.push(F.X(R[i]),F.Y(R[i+1]));
  MB.loft(F.m,Rm,F.Z(205),Rm,F.Z(225),'brick',F.tint,kt,'roof'); lgear(F,-26,2,26,6,14.1,2,7);
  larch(F,'s',0,0,0,10,8,'dark',.4); lcanopy(F,'s',0,0,18,4.5,8.6,'white');
  lfoot(F,-29,0,29,58,14); lfoot(F,-22,7,22,51,225);
  return F.m; }
function bCira(F){
  lpatchBox(F,'paving',11,.1);
  var w=50, d=36, zl=100, zr=133, bump=.9, x0=-w/2, x1=w/2, m=F.m, t=F.tint;
  lfacets(F,[x0,0],[x1,0],zl,zr,6,10,bump,'s','glass'); lfacets(F,[x1,d],[x0,d],zr,zl,6,10,bump,'n','glass');
  lfacets(F,[x1,0],[x1,d],zr,zr,4,10,bump,'e','glass'); lfacets(F,[x0,d],[x0,0],zl,zl,4,8,bump,'w','glass');
  MB.face(m,[[F.X(x0),F.Y(0),F.Z(zl)],[F.X(x1),F.Y(0),F.Z(zr)],[F.X(x1),F.Y(d),F.Z(zr)],[F.X(x0),F.Y(d),F.Z(zl)]],[0,0,1],'glass',t,1);
  larch(F,'s',0,0,0,10,8,'dark',.4); lcanopy(F,'s',0,0,18,4.5,8.6,'white');
  lfoot(F,-25,0,25,36,133);
  return F.m; }
function bFMC(F){
  lpatchBox(F,'paving',11,.1);
  var kt=ktw(F,223,0), kw=3.4/3.8;
  lbox(F,-15,0,26,34,0,40,'glass',null,kw,16); lbox(F,-15,0,26,34,39.9,40.1,'glass','roof',1,15); lgear(F,-27,1,-3,33,40.1,2,8);
  var x0=-12, x1=24, d=36, zl=204, zr=223, m=F.m, t=F.tint, Z=F.Z, X=F.X, Y=F.Y, xs=[x0,x0+.3*(x1-x0),x0+.72*(x1-x0),x1], i;
  function zt(x){ return zl+(zr-zl)*(x-x0)/(x1-x0); }
  [[0,'s'],[d,'n']].forEach(function(f){ var vv=f[0], dr=f[1];
    var P=[[xs[0],vv],[xs[1],vv+(dr==='s'?-1.6:1.6)],[xs[2],vv+(dr==='s'?-1.6:1.6)],[xs[3],vv]], o=LDIR[dr];
    for(i=0;i<3;i++) MB.face(m,[[X(P[i][0]),Y(P[i][1]),Z(0)],[X(P[i+1][0]),Y(P[i+1][1]),Z(0)],[X(P[i+1][0]),Y(P[i+1][1]),Z(zt(P[i+1][0]))],[X(P[i][0]),Y(P[i][1]),Z(zt(P[i][0]))]],[o[0],o[1],0],'glass',t,kt); });
  MB.face(m,[[X(x1),Y(0),Z(0)],[X(x1),Y(d),Z(0)],[X(x1),Y(d),Z(zr)],[X(x1),Y(0),Z(zr)]],[1,0,0],'glass',t,kt);
  MB.face(m,[[X(x0),Y(0),Z(0)],[X(x0),Y(d),Z(0)],[X(x0),Y(d),Z(zl)],[X(x0),Y(0),Z(zl)]],[-1,0,0],'glass',t,kt);
  MB.face(m,[[X(x0),Y(0),Z(zl)],[X(x1),Y(0),Z(zr)],[X(x1),Y(d),Z(zr)],[X(x0),Y(d),Z(zl)]],[0,0,1],'glass',t,1);
  larch(F,'s',-15,0,0,9,8,'dark',.4); lcanopy(F,'s',-15,0,16,4.5,8.6,'white');
  lfoot(F,-28,0,-2,34,40); lfoot(F,-12,0,24,36,223);
  return F.m; }
"""

JS_H_COURTS = r"""
/* ── the courthouses ── */
/* Byrne US Courthouse: a stone-and-glass slab over a granite podium with a glass atrium on the street (100 x 60 m, 75 m) */
function bByrne(F){
  lpatchBox(F,'paving',11,.1);
  lbox(F,0,0,100,60,0,12,'concrete','roof',3.4/6,0); lband(F,-50,0,50,60,11,12.4,.6,'white');
  lbox(F,0,14.4,78,37.2,12,75,'stone','roof',3.4/4.2,0); lbox(F,-12,11.4,42,6,12,61.5,'glass','roof',3.4/4,0);
  lbox(F,0,-1.6,50,9.6,0,14,'glass','roof',3.4/7,0); larch(F,'s',0,-1.6,0,6,7,'dark'); lrect(F,-39.6,13.8,39.6,52.2,74.4,75.6,'white','white',1,0);
  lsteps(F,'s',0,0,30,3,.2,.8,.6,'concrete');
  lfoot(F,-50,0,50,60,12); lfoot(F,-39,14.4,39,51.6,75);
  return F.m; }
/* Nix Federal Building and Courthouse: stripped classical limestone, pilasters the full height of its Market Street front, a set-back top storey (120 x 60 m, 45 m) */
function bNix(F){
  var i; lpatchBox(F,'paving',11,.1);
  lrect(F,-60,0,60,60,0,39,'stone',null,3.4/9); lband(F,-60,0,60,60,36.4,38.2,1,'white'); lband(F,-60,0,60,60,3.6,4.4,.5,'white');
  for(i=0;i<14;i++){ var x=-42+84*(i+.5)/14; lrect(F,x-1.2,-.9,x+1.2,.2,4.4,36.4,'white','white',1,16); }
  lrect(F,-48,3,48,57,39,45,'stone','roof',3.4/6,0); lband(F,-48,3,48,57,44,45.8,.8,'white');
  lbox(F,0,-3,22,3,0,9,'stone','white',3.4/9,0); lband(F,-11,-3,11,0,8.2,9.2,.5,'white'); lrect(F,-11.6,-3.4,-10.2,0,0,8.2,'white','white',1,16); lrect(F,10.2,-3.4,11.6,0,0,8.2,'white','white',1,16); larch(F,'s',0,-3,0,7,8,'dark',.4);
  lfoot(F,-60,0,60,60,45);
  return F.m; }
/* Criminal Justice Center: a granite tower in ribbons of glazing over a granite podium (80 x 60 m, 82 m) */
function bCJC(F){
  lpatchBox(F,'paving',11,.1);
  lbox(F,0,0,80,60,0,20,'concrete','roof',3.4/5,0); lband(F,-40,0,40,60,19,20.6,.6,'white');
  lbox(F,0,16.5,46.4,33,20,78,'concrete','roof',3.4/4.2,0); lbox(F,0,17.5,40,28.2,78,82,'white','roof',1,0);
  lbox(F,0,-1.6,28.8,8.6,0,16,'glass','roof',3.4/5,0); larch(F,'s',0,-1.6,0,6,7,'dark');
  lfoot(F,-40,0,40,60,20); lfoot(F,-23.2,16.5,23.2,49.5,82);
  return F.m; }
/* a classical courthouse: columned portico and pediment between flanking wings (Family Court; any named courthouse): W x D m, h to the cornice-top */
function bClassicCourt(F,l,W,D,h){
  W=W||90; D=D||45; h=h||28; var body=h*.7, pw=Math.min(W*.58,70), hw=W/2, kc=3.4/(body/2.2);
  lpatchBox(F,'paving',11,.1);
  lrect(F,-hw,10,hw,D,0,body,'stone',null,kc); lband(F,-hw,10,hw,D,body-1.2,body,.8,'white'); lband(F,-hw,10,hw,D,0,1.4,.4,'concrete'); lroof(F,-hw,10,hw,D,body,[[5,3.5]],'roof',1);
  lrect(F,-(pw+8)/2,0,(pw+8)/2,6.5,0,2,'concrete','concrete',1,0);
  lrect(F,-pw/2,7,pw/2,14,2,body+1,'stone',null,kc,0); lrect(F,-pw/2,6.2,-pw/2+4,7,2,body+1,'white','white',1,0); lrect(F,pw/2-4,6.2,pw/2,7,2,body+1,'white','white',1,0);   /* the set-back wall of the portico, framed by piers */
  lcols(F,-pw*.45,pw*.45,2.4,pw<45?6:8,2,body,1.0+pw*.01,'white',1,8); lrect(F,-pw/2-.8,.6,pw/2+.8,8.4,body-.2,body+1.2,'white','white',1,0);
  MB.pediment(F.m,F.X(0),F.Y(.6),0,1,F.Z(body+1.2),(pw+3)*F.S,pw*.2*F.S,10*F.S,'white','roof',F.tint,1);
  larch(F,'s',0,7,2,4,7,'dark',.4); lsteps(F,'s',0,0,pw*.8,5,.4,.9,2,'concrete');
  lfoot(F,-hw,6,hw,D,body+4); lfoot(F,-pw/2,0,pw/2,14,body+12);
  return F.m; }
function bFamily(F,l){ return bClassicCourt(F,l,90,45,28); }
function bCourt(F,l){ return bClassicCourt(F,l,90,45,28); }
/* a building for any landmark the models do not know (another city's): height from the record (hm, metres) or lmHeightM, a tower of glass over a podium when tall, else a stone block with a cornice and a hipped roof */
function bGeneric(F,l){
  var b=l.box, S=F.S, hm=(+l.hm>0)?+l.hm:lmHeightM(l.n||'',F.floors||30), wM=(+l.fw>0)?+l.fw:Math.max(24,Math.min(80,(b[2]-b[0]-40)/LMV*.6)), dM=Math.max(18,Math.min(60,(b[3]-b[1]-40)/LMV*.55)), hw=wM/2;
  lpatchBox(F,'paving',11,.1);
  if(hm>=70){ var kt=3.4/4.2, tw=wM*.78, td=dM*.78, cw=tw*.62, cd=td*.62;
    lbox(F,0,0,wM,dM,0,14,'stone',null,3.4/6,16); lparapet(F,-hw,0,hw,dM,14,1.1,.5,'white'); lbox(F,0,0,wM,dM,13.9,14.1,'stone','roof',1,15); lgear(F,-hw+2,1,hw-2,dM*.12,14.1,2,1);
    lbox(F,0,(dM-td)/2,tw,td,14,hm*.82,'glass',null,kt,16); lbox(F,0,(dM-td)/2,tw,td,hm*.82-.2,hm*.82+.2,'glass','roof',kt,15);
    lbox(F,0,(dM-cd)/2,cw,cd,hm*.82,hm*.97,'glass','roof',kt,0); llathe(F,0,dM/2,[[.8,hm*.97],[.5,hm*.99],[.12,hm]],6,'metal');
    larch(F,'s',0,0,0,8,8,'dark',.4); lcanopy(F,'s',0,0,14,4.5,8.6,'white'); lfoot(F,-hw,0,hw,dM,hm);
    return F.m; }
  lrect(F,-hw,0,hw,dM,0,hm,'stone',null,3.4/Math.max(3.4,Math.min(7,hm/3.5))); lband(F,-hw,0,hw,dM,hm-1.2,hm,.6,'white'); lband(F,-hw,0,hw,dM,0,1.2,.4,'concrete');
  lroof(F,-hw,0,hw,dM,hm,[[Math.min(hw,dM/2)*.55,Math.min(9,hm*.35)]],'roof',1,'roof');
  larch(F,'s',0,0,0,4,6,'dark',.4); lcanopy(F,'s',0,0,8,3.5,5.2,'white'); lfoot(F,-hw,0,hw,dM,hm+Math.min(9,hm*.35));
  return F.m; }
"""

JS_H_VENUES = r"""
/* ── the arena and the two grounds: stands as rings, built at the block's fit scale S ── */
function ringZ(F,R,z){ return lconst(R.length,z); }
/* Xfinity Mobile Arena: a closed drum, glass-and-steel walls in two bands, a lower roof stepping up to the flat lid, a canopy over the entrance (174 x 163 m, 42 m) */
function bArena(F){
  var W=174, D=163, R=lccw(lsuper(W,D,2.8,40)), i, n=R.length;
  lpatchBox(F,'paving',11,.1);
  var R0=lmap(F,R), R1=lmap(F,linset(R,4)), R2=lmap(F,linset(R,18)), R3=lmap(F,linset(R,34));
  MB.loft(F.m,R0,0,R0,F.Z(24),'glass',F.tint,3.4/6); MB.band(F.m,R0,F.Z(24),R1,F.Z(24),'concrete',F.tint,1);
  MB.loft(F.m,R1,F.Z(24),R1,F.Z(33),'metal',F.tint,1); MB.band(F.m,R1,F.Z(33),R2,F.Z(33),'concrete',F.tint,1);
  MB.loft(F.m,R2,F.Z(33),R2,F.Z(40),'metal',F.tint,1); MB.band(F.m,R2,F.Z(40),R3,F.Z(40),'roof',F.tint,1);
  MB.loft(F.m,R3,F.Z(40),R3,F.Z(42),'white',F.tint,1,'roof');
  lbox(F,0,-9,44,15,12,14.4,'white','metal',1,0); lcols(F,-18,18,-6,5,0,12,.6,'metal',1,6); lsteps(F,'s',0,-9,44,3,.25,.9,.75,'concrete');
  lrectd(F,'s',-40,0,0,8,6,'dark',.4); lrectd(F,'s',40,0,0,8,6,'dark',.4);
  lfootRing(F,R,42);
  return F.m; }
/* the bowl inside a ring of stands: tiers stepping down from the rim ring Rin (local) at z=top to a field ring, then the grass */
function lbowl(F,Rin,top,low,tiers,fieldK,cx,cv){ var m=F.m, Z=F.Z, prev=Rin, i, n=Rin.length; var rings=[];
  for(i=0;i<=tiers;i++){ var t=i/tiers, k=1-(1-fieldK)*t, z=top-(top-low)*Math.pow(t,.9); rings.push([Rin.map(function(q){ return [cx+(q[0]-cx)*k, cv+(q[1]-cv)*k]; }), z]); }
  for(i=0;i<tiers;i++){ var A=lmap(F,rings[i][0]), B=lmap(F,rings[i+1][0]); MB.band(m,A,Z(rings[i][1]),B,Z(rings[i+1][1]),(i&1)?'concrete':'tile',F.tint,1); }
  return rings[tiers][0]; }
/* Lincoln Financial Field: a rounded oval bowl of glass and silver stands, the open pitch inside, the roof edge sweeping up over the sidelines (252 x 285 m) */
function bLFF(F){
  var W=252, D=285, R=lccw(lsuper(W,D,2.35,64)), Ro=lmap(F,R), R5=lmap(F,linset(R,5)), RI=linset(R,34), RO=linset(R,50), n=R.length, i;
  lpatchBox(F,'paving',11,.1);
  MB.loft(F.m,Ro,0,Ro,F.Z(28),'glass',F.tint,3.4/7); MB.band(F.m,Ro,F.Z(28),R5,F.Z(28),'concrete',F.tint,1); MB.loft(F.m,R5,F.Z(28),R5,F.Z(38),'metal',F.tint,1);
  /* the roof: a ring whose height swings up at the sidelines (east and west) */
  var zo=[], zi=[]; for(i=0;i<n;i++){ var cx=Math.abs(R[i][0])/(W/2), lift=24*Math.pow(Math.max(0,cx),3); zo.push(38+lift*.55); zi.push(38+lift); }
  lbandZ(F,R5,zo,lmap(F,RI),zi,'metal',1); lbandZ(F,R5,zo.map(function(z){ return z-.8; }),lmap(F,RI),zi.map(function(z){ return z-1.2; }),'metal',1,true);
  var rim=lmap(F,RO); MB.band(F.m,lmap(F,RI),F.Z(37),rim,F.Z(37),'concrete',F.tint,1,true);
  var low=lbowl(F,RO,36,5,8,.5,0,D/2); MB.cap(F.m,lmap(F,low),F.Z(.5),'grass',F.tint,1);
  for(i=-5;i<=5;i++) lpatch(F,-24,D/2+i*9.1-.25,24,D/2+i*9.1+.25,.62,'white');                        /* the yard lines of the field of play */
  [35,145,215,325].forEach(function(a){ var p=lon(R,a,22); lmast(F,p[0],p[1],0,70,2.6,7); });
  lrectd(F,'s',-30,0,0,10,7,'dark',.4); lrectd(F,'s',30,0,0,10,7,'dark',.4);
  lfootRing(F,R,56);
  return F.m; }
/* Citizens Bank Park: a red-brick and sandstone ballpark, the grandstand tall behind home plate and round the infield, falling to a low outfield, the diamond and its fence inside (281 x 263 m, 52 m) */
function bCBP(F){
  var CBP=[[-135,100],[-124,196],[-96,246],[-40,258],[58,250],[112,238],[138,214],[131,150],[120,90],[101,36],[40,8],[-22,4],[-86,24],[-126,62]], i;
  var R=CBP; for(var it=0;it<2;it++){ var o=[]; for(i=0;i<R.length;i++){ var a=R[i], b=R[(i+1)%R.length]; o.push([.75*a[0]+.25*b[0],.75*a[1]+.25*b[1]],[.25*a[0]+.75*b[0],.25*a[1]+.75*b[1]]); } R=o; }
  R=lccw(R); var n=R.length;
  function face(x,v){ var t=Math.max(0,Math.min(1,.5+.5*((x*-.25+(v-131)*-1)/135))); return 14+24*Math.pow(t,1.4); }
  function inn(x,v){ return 12+34*Math.max(0,Math.min(1,.5+.5*((x*-.25+(v-131)*-1)/135))); }
  var RO=linset(R,inn), Rm=lmap(F,R), Rin=lmap(F,RO), zt=R.map(function(q){ return face(q[0],q[1]); });
  lpatchBox(F,'paving',11,.1);
  lwallZ(F,Rm,lconst(n,0),zt,'brick',3.4/6);
  lbandZ(F,Rm,zt,Rin,zt,'concrete',1);
  var bowl=RO.map(function(q){ return q; });
  for(i=0;i<5;i++){ var t=i/5, t1=(i+1)/5; var A=RO.map(function(q,j){ return [131*0+(q[0]-0)*(1-.5*t)+0, 131+(q[1]-131)*(1-.5*t)]; }), B=RO.map(function(q){ return [(q[0])*(1-.5*t1), 131+(q[1]-131)*(1-.5*t1)]; });
    MB.band(F.m,lmap(F,A),F.Z(zt[0]*(1-t)*.0+30-i*5.4),lmap(F,B),F.Z(30-(i+1)*5.4),(i&1)?'concrete':'tile',F.tint,1); }
  var floor=RO.map(function(q){ return [q[0]*.5, 131+(q[1]-131)*.5]; }); MB.cap(F.m,lmap(F,floor),F.Z(.5),'grass',F.tint,1);
  var hp=[-10,96]; lpatch(F,hp[0]-3,hp[1]-3,hp[0]+3,hp[1]+3,.6,'tile');
  MB.cap(F.m,lring(F,[[hp[0],hp[1]-2],[hp[0]+21,hp[1]+19],[hp[0],hp[1]+40],[hp[0]-21,hp[1]+19]]),F.Z(.65),'tile',F.tint,1);
  MB.cap(F.m,lring(F,[[hp[0],hp[1]+4],[hp[0]+14,hp[1]+19],[hp[0],hp[1]+34],[hp[0]-14,hp[1]+19]]),F.Z(.7),'grass',F.tint,1);
  [200,330,85,20].forEach(function(a){ var p=lon(R,a,14); lmast(F,p[0],p[1],0,52,2.8,7); });
  lrectd(F,'s',-20,5,0,8,5,'dark',.4);
  lfootRing(F,R,45);
  return F.m; }
"""
JS_H_MAIN = r"""
/* the table of models: key -> [builder, depth in metres, centred in its block?, fit into the block?] */
var LMT={}, LMC={};
function lmBuild(l, floors){
  var key=lmKey(l.n), t=LMT[key]; if(!t) t=LMT.gen; var b=l.box, S=LMV, wM=t[4]||100, fr=t[5]||0;
  /* true scale (1.3 map units a metre) unless the model would cover the streets round its block: then every dimension, height too, is scaled by the same factor (the 2D art does that for the grounds) */
  var fw=(b[2]-b[0]-26)/wM, fd=(b[3]-b[1]-26)/(t[1]+fr); S=Math.min(LMV,Math.max(.6,Math.min(fw,fd)));
  var F=lmFrame(l,S,!!t[2],t[1],fr); F.key=key; F.floors=floors; F.tint=lmPickTint(F,LMC[key]);
  t[0](F,l); return {a:MB.done(F.m), fp:F.fp}; }
var LM_FOOT=true;                                             /* the stand-in solids follow the model's real footprint (roaming walks up to the steps; the 2D fallback draws a true-size building) instead of filling the block */
var LMCACHE={};                                               /* a landmark's model never changes (its box and name are all it depends on): one array for every world, so the renderer keeps one GPU buffer too */
function landmarkMeshes(l, floors, W){
  var n0=W.solids.length; lmSolids(l, W.solids, floors);
  if(!l.box) return; var key=l.n+'|'+l.box.join(','), rec=LMCACHE[key];
  if(rec===undefined){ rec=null; try{ rec=lmBuild(l,floors); }catch(e){ rec=null; if(window.console&&console.warn) console.warn('landmark model failed',l.n,e&&e.message); } LMCACHE[key]=rec; }
  if(!rec || !rec.a.length) return;
  W.meshes.push({a:rec.a, id:l.n}); var i;
  if(LM_FOOT && rec.fp.length && typeof solid==='function'){ var old=W.solids.splice(n0), col=(old[0]&&old[0].col)||[200,200,208]; rec.fp.forEach(function(f){ var s=solid(f.r, f.h, col, 'lm', l.n); s.mesh=1; W.solids.push(s); }); }
  else for(i=n0;i<W.solids.length;i++) W.solids[i].mesh=1; }
window._palRideLm={key:lmKey, build:function(l,f){ return lmBuild(l,f).a; }, mesh:landmarkMeshes, table:LMT};
"""

JS_H_TABLE = r"""
/* real colours: pale marble (City Hall, stations, Franklin Institute, courthouses), tan limestone (Art Museum), Liberty Place's pink-tan granite, red brick (Independence Hall, Reading Terminal, Citizens Bank Park, Three Logan Square) */
LMC.city={s:[.84,.98]}; LMC.art={s:[.58,.78]}; LMC.frank={s:[.84,.98]}; LMC.stn={s:[.84,.98]}; LMC.sub={s:[.84,.98]}; LMC.nix={s:[.84,.98]}; LMC.fam={s:[.84,.98]}; LMC.court={s:[.84,.98]}; LMC.usch={s:[.84,.98]};
LMC.ind={b:[.02,.16]}; LMC.conv={b:[.02,.16],g:[.2,.5]}; LMC.cbp={b:[.02,.16]}; LMC.tls={b:[.02,.16]};
LMC.lib1={s:[.58,.78],g:[.0,.3]}; LMC.lib2={s:[.58,.78],g:[.0,.3]}; LMC.ccc={g:[.28,.5]}; LMC.ctc={s:[.3,.52],g:[.3,.5]}; LMC.bny={s:[.3,.52],g:[.5,.75]}; LMC.cira={g:[.72,.95]}; LMC.fmc={g:[.12,.34]};
LMC.jef={g:[.3,.6]}; LMC.arena={g:[.2,.45]}; LMC.lff={g:[.2,.45]}; LMC.stad={g:[.2,.45]};
/* key -> [builder, plan depth m, centred in its block?, (unused), plan width m, how far steps / canopies push out of the front face m] */
LMT.city=[bCityHall,145,true,false,148,13.5]; LMT.ind=[bIndependence,22,false,false,105,1.5]; LMT.art=[bArt,110,false,false,198,9]; LMT.frank=[bFranklin,70,false,false,112,11]; LMT.stn=[bStation,100,false,false,192,8];
LMT.sub=[bSuburban,46,false,false,94,3]; LMT.jef=[bJefferson,50,false,false,100,9]; LMT.conv=[bConvention,190,false,false,250,6];
LMT.lib1=[bLib1,64,false,false,64,5]; LMT.lib2=[bLib2,56,false,false,56,5]; LMT.ccc=[bComcast,56,false,false,70,5]; LMT.ctc=[bCTC,50,false,false,92,5]; LMT.bny=[bBNY,66,false,false,66,5]; LMT.tls=[bTLS,58,false,false,58,5]; LMT.cira=[bCira,36,false,false,52,5]; LMT.fmc=[bFMC,36,false,false,52,5];
LMT.usch=[bByrne,60,false,false,100,3]; LMT.nix=[bNix,60,false,false,122,3]; LMT.cjc=[bCJC,60,false,false,80,1]; LMT.fam=[bFamily,45,false,false,92,5]; LMT.court=[bCourt,45,false,false,92,5]; LMT.gen=[bGeneric,40,false,false,70,1];
LMT.arena=[bArena,163,false,false,174,12]; LMT.lff=[bLFF,285,false,false,252,0]; LMT.cbp=[bCBP,263,false,false,281,0]; LMT.stad=[bLFF,285,false,false,252,0];
"""

JS_H = JS_H_KIT + JS_H_KIT2 + JS_H_CITY + JS_H_CIVIC + JS_H_TOWERS + JS_H_COURTS + JS_H_VENUES + JS_H_MAIN.replace("var LMT={}, LMC={};", "var LMT={}, LMC={};") + JS_H_TABLE
