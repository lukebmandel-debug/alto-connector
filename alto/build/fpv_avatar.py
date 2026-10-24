"""Shared by both first-person views: the HOP, the third-person AVATAR the camera follows, the gamepad and the view settings.

The Memory Blueprint walk (palace_building_fpv.py, hosted /bldg/ renderer) embeds AVATAR_JS in its own scope; the city palace's roam did too until
it was retired to _cold-storage/memory-map-fpv (git tag cold/memory-map-fpv), which is why the city lookup below stays. Nothing of it is on a palace page (civ-pro-palace sits at its 976 KB cap).

  AV.city(place, lat, lon)   the palace's city from data already on the page (the city palace's `place` name; the building plan's geo lat/lon)
                             -> an entry of alto/buildings/city_mayors.json or null
  AV.make(city, want)        an avatar instance: the city's MAYOR figure when the city has a current mayor (Wikidata, alto/buildings/mayors.py)
                             and a look written for that same person, else (or with want 'generic') the neutral generic figure
  AV.tick(A, dt, o)          animate: o = {gait (speed / the view's walking pace), vx, vy (to face along), air (bool), vz}
  AV.emit(A, x, y, z, s)     skin the figure into A.pos / A.nrm (Float32Array, 3 per vertex, triangles) in world units: x, y, z of the feet,
                             s units a metre; A.ranges = [{c: colour index, first, count}] (vertices) and A.cols = ['#rrggbb', ...]
  AV.tag(A)                  the name tag's text ('' for the generic figure) and its title (where the name comes from, and when)
  AV.HOP                     the hop: v0 m/s, g m/s^2, coyote and buffer seconds (one hop from the ground, none in the air)
  AV.pad()                   the first standard gamepad: {mx, my, lx, ly, a, run} (sticks with a dead zone, A = hop) or null
  AV.pref(k) / AV.setPref    'view' third|first (default third), 'avatar' mayor|generic (default mayor); localStorage, wrapped

The figure: 11 bones (pelvis, chest, head, upper/fore arms, thighs, shins), tapered tubes and ellipsoid caps, about 900 triangles, no face
(a small nose only, so you can tell which way it faces), no photo, no logo. Walk, run, hop (tuck up, reach down), landing squash and an idle
(breathing, weight). The look carries public-facing cues only: height, build, skin tone, hair, typical attire.
"""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "buildings" / "city_mayors.json"


def avatar_table() -> list[dict]:
    """The cities the hosted scripts know: name, aliases, where, the current mayor and, only when written for that person, the look."""
    data = json.loads(DATA.read_text("utf-8"))
    out = []
    for c in data["cities"]:
        m = c.get("mayor") or None
        look = c.get("look") or None
        if not m or not look or look.get("for") != m.get("wikidata"):
            look = None
        e = {"id": c["id"], "n": c["name"], "lat": c["lat"], "lon": c["lon"], "r": c.get("r_km", 40), "mt": c.get("match") or [c["name"].lower()],
             "m": {"n": m["name"], "src": m["source"], "on": m["retrieved"], "since": m.get("since", "")} if m else None}
        if look:
            e["look"] = {k: v for k, v in look.items() if k not in ("for", "cues")}
        out.append(e)
    return out


_AVATAR_JS = r"""
var AV=(function(){
var TABLE=__AV_TABLE__;
var GEN={h:1.74, build:1, skin:'#a7b0b9', hair:{style:'none', c:'#a7b0b9'}, beard:null, top:{style:'jacket', c:'#4d7479'}, shirt:'#d9dcd6', tie:null,
  bottom:{style:'trousers', c:'#343a46'}, legs:null, shoes:'#23262c'};          /* the neutral figure: one soft grey for skin and head, no hair, a plain jacket */
var HOP={v0:3.3, g:13.5, coyote:.1, buffer:.13};                               /* apex 0.40 m, 0.49 s in the air: a natural little hop */
function clampv(v,a,b){ return v<a?a:v>b?b:v; }
function sstep(a,b,v){ var t=clampv((v-a)/(b-a),0,1); return t*t*(3-2*t); }
function city(place,lat,lon){ var best=null, bd=1e9, p=String(place||'').toLowerCase();
  TABLE.forEach(function(c){ if(lat!=null&&lon!=null&&isFinite(lat)&&isFinite(lon)){ var dx=(lon-c.lon)*111.32*Math.cos(c.lat*Math.PI/180), dy=(lat-c.lat)*110.57, d=Math.hypot(dx,dy); if(d<c.r&&d<bd){ bd=d; best=c; } } });
  if(best) return best;
  if(p) for(var i=0;i<TABLE.length;i++){ var c=TABLE[i]; for(var j=0;j<c.mt.length;j++) if(p.indexOf(c.mt[j])>=0) return c; }
  return null; }
function pref(k){ var d=k==='view'?'third':'mayor'; try{ var o=window._altoFpv; if(o&&o[k]) return o[k]; }catch(x){}          /* window._altoFpv = {view, avatar}: a page (or a test) may set the starting choice */
  try{ var v=localStorage.getItem('alto-fpv-'+k); return v||d; }catch(x){ return d; } }
function setPref(k,v){ try{ localStorage.setItem('alto-fpv-'+k,v); }catch(x){} }
function pad(){ var ps=null; try{ ps=navigator.getGamepads?navigator.getGamepads():null; }catch(x){ ps=null; } if(!ps) return null;
  for(var i=0;i<ps.length;i++){ var g=ps[i]; if(!g||!g.connected||!g.axes||g.axes.length<2) continue; var dz=function(v){ v=+v||0; return Math.abs(v)<.18?0:(v-(v>0?.18:-.18))/.82; };
    var b=function(n){ var q=g.buttons&&g.buttons[n]; return !!(q&&(q.pressed||q.value>.5)); };
    return {mx:dz(g.axes[0]), my:dz(g.axes[1]), lx:dz(g.axes[2]), ly:dz(g.axes[3]), a:b(0), run:b(10)||b(6)||b(7)}; }
  return null; }

/* ── geometry: triangles in bone-local metres, x forward, y left, z up ── */
function Geo(){ this.t=[]; this.cols=[]; this.ci={}; }
Geo.prototype.col=function(c){ c=String(c||'#888888').toLowerCase(); if(this.ci[c]==null){ this.ci[c]=this.cols.length; this.cols.push(c); } return this.ci[c]; };
Geo.prototype.tri=function(b,c,A,B,C,na,nb,nc){ var ux=B[0]-A[0], uy=B[1]-A[1], uz=B[2]-A[2], vx=C[0]-A[0], vy=C[1]-A[1], vz=C[2]-A[2];       /* counter-clockwise seen from the normal's side */
  if((uy*vz-uz*vy)*(na[0]+nb[0]+nc[0])+(uz*vx-ux*vz)*(na[1]+nb[1]+nc[1])+(ux*vy-uy*vx)*(na[2]+nb[2]+nc[2])<0){ var q=B; B=C; C=q; q=nb; nb=nc; nc=q; }
  this.t.push({b:b,c:c,p:[A,B,C],n:[na,nb,nc]}); };
function nz3(v){ var l=Math.hypot(v[0],v[1],v[2])||1; return [v[0]/l,v[1]/l,v[2]/l]; }
/* a tapered tube from a to b (both on the bone's z axis or anywhere), elliptical sections [rx, ry] at each end, capped */
Geo.prototype.tube=function(b,col,a,e,ra,rb,seg,caps){ var c=this.col(col), ax=[e[0]-a[0],e[1]-a[1],e[2]-a[2]], L=Math.hypot(ax[0],ax[1],ax[2])||1e-6, w=[ax[0]/L,ax[1]/L,ax[2]/L],
    u=Math.abs(w[2])>.9?[1,0,0]:nz3([-w[1],w[0],0]), v=[w[1]*u[2]-w[2]*u[1],w[2]*u[0]-w[0]*u[2],w[0]*u[1]-w[1]*u[0]], i, P=[], N=[];
  if(Math.abs(w[2])>.9){ u=[1,0,0]; v=[w[1]*u[2]-w[2]*u[1],w[2]*u[0]-w[0]*u[2],w[0]*u[1]-w[1]*u[0]]; }
  for(i=0;i<seg;i++){ var t=i/seg*2*Math.PI, ct=Math.cos(t), st=Math.sin(t), r0=[ra[0]*ct,ra[1]*st], r1=[rb[0]*ct,rb[1]*st];
    var p0=[a[0]+u[0]*r0[0]+v[0]*r0[1],a[1]+u[1]*r0[0]+v[1]*r0[1],a[2]+u[2]*r0[0]+v[2]*r0[1]], p1=[e[0]+u[0]*r1[0]+v[0]*r1[1],e[1]+u[1]*r1[0]+v[1]*r1[1],e[2]+u[2]*r1[0]+v[2]*r1[1]];
    var sl=((ra[0]+ra[1])-(rb[0]+rb[1]))/2/L, nn=nz3([u[0]*ct/ra[0]*ra[1]+v[0]*st+w[0]*sl,u[1]*ct/ra[0]*ra[1]+v[1]*st+w[1]*sl,u[2]*ct/ra[0]*ra[1]+v[2]*st+w[2]*sl]);
    P.push([p0,p1]); N.push(nn); }
  for(i=0;i<seg;i++){ var j=(i+1)%seg; this.tri(b,c,P[i][0],P[j][0],P[j][1],N[i],N[j],N[j]); this.tri(b,c,P[i][0],P[j][1],P[i][1],N[i],N[j],N[i]); }
  if(caps!==false){ var nA=[-w[0],-w[1],-w[2]]; for(i=0;i<seg;i++){ var j2=(i+1)%seg; this.tri(b,c,a,P[j2][0],P[i][0],nA,nA,nA); this.tri(b,c,e,P[i][1],P[j2][1],w,w,w); } } };
/* an ellipsoid (centre, radii) or the part of it whose quads pass keep(lat, lon): lat -1 (bottom) .. 1 (top), lon 0 = forward (+x) */
Geo.prototype.ell=function(b,col,ctr,r,su,sv,keep){ var c=this.col(col), i, j, V=[];
  for(j=0;j<=sv;j++){ var la=-Math.PI/2+j/sv*Math.PI, row=[]; for(i=0;i<=su;i++){ var lo=i/su*2*Math.PI, cx=Math.cos(la)*Math.cos(lo), cy=Math.cos(la)*Math.sin(lo), cz=Math.sin(la);
    row.push({p:[ctr[0]+r[0]*cx,ctr[1]+r[1]*cy,ctr[2]+r[2]*cz], n:nz3([cx/r[0],cy/r[1],cz/r[2]]), la:Math.sin(la), lo:lo}); } V.push(row); }
  for(j=0;j<sv;j++) for(i=0;i<su;i++){ var a=V[j][i], b2=V[j][i+1], d=V[j+1][i], e=V[j+1][i+1];
    if(keep && !keep((a.la+e.la)/2,(a.lo+b2.lo)/2)) continue;
    if(j>0) this.tri(b,c,a.p,b2.p,e.p,a.n,b2.n,e.n); if(j<sv-1) this.tri(b,c,a.p,e.p,d.p,a.n,e.n,d.n); } };
Geo.prototype.box=function(b,col,ctr,h){ var c=this.col(col), x0=ctr[0]-h[0], x1=ctr[0]+h[0], y0=ctr[1]-h[1], y1=ctr[1]+h[1], z0=ctr[2]-h[2], z1=ctr[2]+h[2], self=this;
  [[[x1,y0,z0],[x1,y1,z0],[x1,y1,z1],[x1,y0,z1],[1,0,0]],[[x0,y1,z0],[x0,y0,z0],[x0,y0,z1],[x0,y1,z1],[-1,0,0]],[[x0,y1,z0],[x1,y1,z0],[x1,y1,z1],[x0,y1,z1],[0,1,0]],
   [[x1,y0,z0],[x0,y0,z0],[x0,y0,z1],[x1,y0,z1],[0,-1,0]],[[x0,y0,z1],[x1,y0,z1],[x1,y1,z1],[x0,y1,z1],[0,0,1]],[[x0,y0,z0],[x0,y1,z0],[x1,y1,z0],[x1,y0,z0],[0,0,-1]]].forEach(function(f){ var n=f[4];
    self.tri(b,c,f[0],f[1],f[2],n,n,n); self.tri(b,c,f[0],f[2],f[3],n,n,n); }); };

/* ── the skeleton: [parent, joint x, y, z in the parent's frame] in units of the figure's height ── */
var BONES=[[-1,0,0,.53],[0,0,0,.07],[1,0,0,.235],[1,0,.125,.215],[3,0,0,-.19],[1,0,-.125,.215],[5,0,0,-.19],[0,0,.07,0],[7,0,0,-.245],[0,0,-.07,0],[9,0,0,-.245]];
function rig(L){ var g=new Geo(), H=L.h||1.74, w=L.build||1, sk=L.skin, top=L.top||{}, bot=L.bottom||{}, skirt=bot.style==='skirt', legC=skirt?(L.legs||sk):bot.c, hr=L.hair||{style:'none'}, sw=(skirt?.118:.125)*w;
  function s(v){ return v*H; }
  var bones=BONES.map(function(q,i){ var o=q.slice(); if(i===3) o[2]=sw; if(i===5) o[2]=-sw; if(i===7) o[2]=.07*w; if(i===9) o[2]=-.07*w; return o; });
  /* pelvis: hips, the jacket's skirt over them, a skirt to the knee */
  g.tube(0,bot.c,[0,0,s(-.06)],[0,0,s(.075)],[s(.064),s(.1*w)],[s(.06),s(.098*w)],8);
  if(top.style==='jacket') g.tube(0,top.c,[0,0,s(.075)],[0,0,s(-.035)],[s(.071),s(.109*w)],[s(.074),s(.113*w)],8,false);
  if(skirt) g.tube(0,bot.c,[0,0,s(.07)],[0,0,s(-.255)],[s(.068),s(.106*w)],[s(.088),s(.124*w)],10);
  /* chest: the torso up to the shoulders, shoulder caps, the neck, a shirt V and a tie */
  g.tube(1,top.c,[0,0,s(-.005)],[0,0,s(.215)],[s(.062),s(.097*w)],[s(.07),s(sw-.006)],8);
  g.ell(1,top.c,[0,s(sw-.012),s(.2)],[s(.045),s(.046),s(.04)],7,5); g.ell(1,top.c,[0,-s(sw-.012),s(.2)],[s(.045),s(.046),s(.04)],7,5);
  g.tube(1,sk,[0,0,s(.2)],[0,0,s(.262)],[s(.028),s(.028)],[s(.026),s(.026)],7);
  var fx=s(.0705), nz=[1,0,0];
  g.tri(1,g.col(L.shirt||top.c),[fx,s(.036),s(.214)],[fx,-s(.036),s(.214)],[fx+s(.001),0,s(.13)],nz,nz,nz);
  if(L.tie){ g.tri(1,g.col(L.tie),[fx+s(.002),s(.009),s(.205)],[fx+s(.002),-s(.009),s(.205)],[fx+s(.004),0,s(.06)],nz,nz,nz); g.tri(1,g.col(L.tie),[fx+s(.0021),s(.009),s(.205)],[fx+s(.004),0,s(.06)],[fx+s(.0021),-s(.009),s(.205)],nz,nz,nz); }
  /* head: skull, a small nose, hair, a trimmed beard */
  var hc=[0,0,s(.088)], hrd=[s(.064),s(.056),s(.075)];
  g.ell(2,sk,hc,hrd,12,8); g.ell(2,sk,[s(.064),0,s(.08)],[s(.012),s(.008),s(.014)],5,4);
  if(hr.style&&hr.style!=='none'){ var full=hr.style==='short-full'?1.11:1.06, bob=hr.style==='bob';
    g.ell(2,hr.c,[s(-.004),0,s(.093)],[hrd[0]*full,hrd[1]*(full+.01),hrd[2]*(full-.01)],12,8,function(la,lo){ var fr=Math.cos(lo); return fr>.3?la>.38-.12*(1-fr):la>(bob?-.62:-.12+.1*Math.max(0,fr)); }); }
  if(L.beard){ g.ell(2,L.beard.c||hr.c,[s(.003),0,s(.084)],[hrd[0]*1.035,hrd[1]*1.035,hrd[2]*1.03],12,8,function(la,lo){ var fr=Math.cos(lo); return la<-.12&&la>-.97&&fr>-.05&&!(fr>.85&&la>-.42&&la<-.25); }); }
  /* arms: sleeves, a shirt cuff, hands */
  [3,5].forEach(function(b){ g.tube(b,top.c,[0,0,s(.012)],[0,0,s(-.19)],[s(.03),s(.029)],[s(.025),s(.024)],7); g.ell(b,top.c,[0,0,s(-.19)],[s(.025),s(.024),s(.022)],6,4); });
  [4,6].forEach(function(b){ g.tube(b,top.c,[0,0,0],[0,0,s(-.142)],[s(.024),s(.023)],[s(.02),s(.019)],7); g.tube(b,L.shirt||top.c,[0,0,s(-.138)],[0,0,s(-.152)],[s(.019),s(.018)],[s(.018),s(.017)],7);
    g.ell(b,sk,[s(.004),0,s(-.19)],[s(.02),s(.013),s(.04)],7,5); });
  /* legs: thighs, shins, shoes */
  [7,9].forEach(function(b){ g.tube(b,skirt?legC:bot.c,[0,0,s(.01)],[0,0,s(-.245)],[s(.05),s(.05)],[s(.037),s(.036)],8); });
  [8,10].forEach(function(b){ g.tube(b,legC,[0,0,0],[0,0,s(-.25)],[s(.036),s(.035)],[s(.026),s(.025)],8); g.box(b,L.shoes,[s(.026),0,s(-.266)],[s(.058),s(.026),s(.018)]); });
  /* flatten, grouped by colour (one draw range per colour) */
  g.t.sort(function(p,q){ return p.c-q.c; });
  var n=g.t.length*3, P=new Float32Array(n*3), N=new Float32Array(n*3), B=new Uint8Array(n), ranges=[], k=0;
  g.t.forEach(function(t){ var r=ranges[ranges.length-1]; if(!r||r.c!==t.c){ r={c:t.c, first:k, count:0}; ranges.push(r); } for(var j=0;j<3;j++){ P.set(t.p[j],k*3); N.set(t.n[j],k*3); B[k]=t.b; k++; r.count++; } });
  return {P:P, N:N, B:B, n:n, ranges:ranges, cols:g.cols, bones:bones, H:H}; }

/* ── an instance: look, rig, the animation state ── */
function make(c,want){ var m=c&&c.m, mayor=!!(m&&c.look&&want!=='generic'), L=mayor?c.look:GEN, R=rig(L);
  return {L:L, R:R, mayor:mayor, city:c||null, cols:R.cols, ranges:R.ranges, n:R.n, pos:new Float32Array(R.n*3), nrm:new Float32Array(R.n*3), M:[],
    st:{ph:0, t:0, wm:0, wr:0, wa:0, land:9, yaw:null, air:false, vz:0, g:0}}; }
function tag(A){ var c=A.city, m=c&&c.m; if(!A.mayor||!m) return {text:'', title:''};
  return {text:'Mayor '+m.n, title:'A stylised figure after the current mayor of '+c.n+', '+m.n+' (Wikidata, read '+m.on+'). Choose the generic figure in the view settings.'}; }
function tick(A,dt,o){ var st=A.st; st.t+=dt; var g=Math.max(0,o.gait||0), mv=clampv(g/.22,0,1);
  st.wm+=(mv-st.wm)*(1-Math.exp(-dt/.12)); st.wr+=(sstep(1.25,2.1,g)-st.wr)*(1-Math.exp(-dt/.2));
  if(st.air&&!o.air) st.land=0; else st.land+=dt; st.air=!!o.air; st.vz=o.vz||0; st.wa+=((o.air?1:0)-st.wa)*(1-Math.exp(-dt/(o.air?.06:.05)));
  var hz=1.75+.45*Math.min(g,1)+.65*st.wr; st.ph+=Math.PI*hz*dt*(st.wm>.02?1:0)*(o.air?.35:1); st.g=g;
  var sp=Math.hypot(o.vx||0,o.vy||0); if(sp>.15){ var ty=Math.atan2(o.vy,o.vx); if(st.yaw==null) st.yaw=ty; var d=ty-st.yaw; while(d>Math.PI) d-=2*Math.PI; while(d<-Math.PI) d+=2*Math.PI; st.yaw+=d*(1-Math.exp(-dt/.09)); }
  else if(st.yaw==null) st.yaw=o.face||0; }
/* angles per bone: [swing (forward +), roll (out +, left side), twist] and the pelvis' drop/lean */
function angles(A){ var st=A.st, s=Math.sin(st.ph), c=Math.cos(st.ph), t=st.t, wm=st.wm, wr=st.wr, wa=st.wa, a={};
  var br=Math.sin(t*1.7)*.012;
  var W={th:[.42*s,-.42*s], sh:[-(.08+.62*Math.max(0,c)),-(.08+.62*Math.max(0,-c))], ua:[-.34*s,.34*s], fa:[.28+.12*Math.max(0,s),.28+.12*Math.max(0,-s)], lean:.03, bob:.012*Math.abs(c)-.008, tw:.07*s};
  var R={th:[.85*s,-.85*s], sh:[-(.25+1.25*Math.max(0,c)),-(.25+1.25*Math.max(0,-c))], ua:[-.75*s,.75*s], fa:[1.35,1.35], lean:.2, bob:.035*Math.abs(c)-.03, tw:.12*s};
  var I={th:[.02,-.01], sh:[-.03,-.05], ua:[.04+br,.04-br], fa:[.14,.14], lean:br*.6, bob:0, tw:0};
  function mix3(k){ var x=W[k], y=R[k], z=I[k]; if(typeof z==='number'){ var m=x+(y-x)*wr; return z+(m-z)*wm; } return [0,1].map(function(i){ var m=x[i]+(y[i]-x[i])*wr; return z[i]+(m-z[i])*wm; }); }
  var th=mix3('th'), sh=mix3('sh'), ua=mix3('ua'), fa=mix3('fa'), lean=mix3('lean'), bob=mix3('bob'), tw=mix3('tw');
  var up=clampv(st.vz/3,-1,1), Ath=[.62-.25*Math.max(0,-up),.3-.2*Math.max(0,-up)], Ash=[-1.05+.55*Math.max(0,-up),-.7+.45*Math.max(0,-up)];
  th=[th[0]+(Ath[0]-th[0])*wa,th[1]+(Ath[1]-th[1])*wa]; sh=[sh[0]+(Ash[0]-sh[0])*wa,sh[1]+(Ash[1]-sh[1])*wa];
  ua=[ua[0]+(-.35-ua[0])*wa,ua[1]+(-.35-ua[1])*wa]; fa=[fa[0]+(.75-fa[0])*wa,fa[1]+(.75-fa[1])*wa];
  var lk=st.land<.22?Math.sin(st.land/.22*Math.PI)*(1-st.land/.22*.4):0;          /* the landing squash: down and back up in 0.22 s */
  bob-=.045*lk; th=[th[0]+.38*lk,th[1]+.38*lk]; sh=[sh[0]-.75*lk,sh[1]-.75*lk];
  var roll=.07+.22*wa, skirt=A.L.bottom&&A.L.bottom.style==='skirt';
  a[0]=[-lean*.4,0,-tw*.6]; a[1]=[-(lean*.6+br*.4),0,tw]; a[2]=[lean*.5,0,-tw*.4];          /* a chest swung back is a NEGATIVE swing of an upward bone: lean forward = negative */
  a[3]=[ua[0],roll,0]; a[4]=[fa[0],0,0]; a[5]=[ua[1],-roll,0]; a[6]=[fa[1],0,0];
  a[7]=[th[0],skirt?.02:.03,0]; a[8]=[sh[0],0,0]; a[9]=[th[1],skirt?-.02:-.03,0]; a[10]=[sh[1],0,0];
  a.bob=bob; return a; }
/* 3x4 matrices: [r00 r01 r02 tx, r10 r11 r12 ty, r20 r21 r22 tz] */
function mul(A,B){ var o=new Array(12); for(var r=0;r<3;r++){ for(var c=0;c<3;c++) o[r*4+c]=A[r*4]*B[c]+A[r*4+1]*B[4+c]+A[r*4+2]*B[8+c]; o[r*4+3]=A[r*4]*B[3]+A[r*4+1]*B[7]+A[r*4+2]*B[11]+A[r*4+3]; } return o; }
function local(tx,ty,tz,sw,ro,tw){ var cs=Math.cos(sw), ss=Math.sin(sw), cr=Math.cos(ro), sr=Math.sin(ro), ct=Math.cos(tw), st=Math.sin(tw);
  var Y=[cs,0,-ss,0, 0,1,0,0, ss,0,cs,0], X=[1,0,0,0, 0,cr,-sr,0, 0,sr,cr,0], Z=[ct,-st,0,0, st,ct,0,0, 0,0,1,0], m=mul(mul(Z,Y),X); m[3]=tx; m[7]=ty; m[11]=tz; return m; }
function emit(A,x,y,z,s,yaw){ var R=A.R, H=R.H, an=angles(A), fy=yaw!=null?yaw:(A.st.yaw||0), cy=Math.cos(fy), sy=Math.sin(fy);
  var W=[cy*s,-sy*s,0,x, sy*s,cy*s,0,y, 0,0,s,z], M=A.M;
  for(var i=0;i<R.bones.length;i++){ var b=R.bones[i], q=an[i], L=local(b[1]*H,b[2]*H,b[3]*H+(i===0?an.bob*H:0),q[0],q[1],q[2]); M[i]=mul(b[0]<0?W:M[b[0]],L); }
  var P=R.P, N=R.N, B=R.B, op=A.pos, on=A.nrm, inv=1/s;
  for(var v=0;v<R.n;v++){ var m=M[B[v]], k=v*3, px=P[k], py=P[k+1], pz=P[k+2], nx=N[k], ny=N[k+1], nz=N[k+2];
    op[k]=m[0]*px+m[1]*py+m[2]*pz+m[3]; op[k+1]=m[4]*px+m[5]*py+m[6]*pz+m[7]; op[k+2]=m[8]*px+m[9]*py+m[10]*pz+m[11];
    on[k]=(m[0]*nx+m[1]*ny+m[2]*nz)*inv; on[k+1]=(m[4]*nx+m[5]*ny+m[6]*nz)*inv; on[k+2]=(m[8]*nx+m[9]*ny+m[10]*nz)*inv; }
  var hm=M[2]; A.head=[hm[3]+hm[2]*.19*H,hm[7]+hm[6]*.19*H,hm[11]+hm[10]*.19*H]; return A; }          /* the bone matrix carries the scale already */
function hex(c){ c=String(c).replace('#',''); return [parseInt(c.slice(0,2),16)/255,parseInt(c.slice(2,4),16)/255,parseInt(c.slice(4,6),16)/255]; }
return {city:city, make:make, tick:tick, emit:emit, tag:tag, HOP:HOP, pad:pad, pref:pref, setPref:setPref, hex:hex, table:TABLE, GEN:GEN};
})();
"""


def avatar_js() -> str:
    return _AVATAR_JS.replace("__AV_TABLE__", json.dumps(avatar_table(), separators=(",", ":"), ensure_ascii=True))
