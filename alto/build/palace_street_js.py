"""The client side of the street blob (palace_street.py has the format): STREET_JS, a small decoder the first-person ride includes.

The ride gets the hashed file name from the page's map data (m.street.h, 12 hex chars; the page growth is that one field) and does

    _palStreet.load('/street/palace-street-' + M.street.h + '.json').then(function(){ var near = _palStreet.near(x, y, 60); ... });

STREET_JS defines  window._palStreet  (a no-op when it already exists):
  load(url)              fetch + parse the blob; returns a Promise (resolves to the API, rejects on a network or format error); a second call returns the same promise
  use(blob)              the same with an already parsed object (tests, inline use)
  ready()                true once a blob is in
  attribution()          the string to show ("© OpenStreetMap contributors, ODbL")
  cell(ix, iy)           the decoded cell (cached): {b, r, t, f, p, e} — arrays of objects, every coordinate in METRES east (x) and north (y) of the blob origin
                         b: {k, lv, h(units), bc, bm, rs, rc, rm, rl, nm, ad, po, sd, wd, ring:[[x,y]..], holes:[[[x,y]..]..]}, h is also given in metres as hm
                         r: {hw, nm, ln, wd, ow, sw, cy, sf, ms, lt, line:[[x,y]..]}   t: {x, y, sp, lf}   f: {x, y, kind}   p: {x, y, name, cat, ad}   e: {x, y, kind}
  near(x, y, r, kinds)   every feature of the cells under the circle (x, y, r metres) that has a point within r of it (a polygon/line: any vertex or edge point) —
                         {b:[], r:[], t:[], f:[], p:[], e:[]}; `kinds` optionally a string such as 'btf' limiting which lists are filled
  fromLatLon(lat, lon)   -> [x, y] metres     toLatLon(x, y) -> [lat, lon]
  toMap(x, y, scale)     -> [px, py] in the palace map's px (y down, like palace_map.project: x*scale, (north - south)*ky*scale - y*scale)
Cells are decoded when first asked for, so a ride that stays in one district decodes a few KB.
"""

STREET_JS = r"""
(function(){
if(window._palStreet) return;
var B=null, CELLS={}, PROM=null;
function use(b){ if(!b||b.v!==1||!b.c||!b.S) throw new Error('street blob'); B=b; CELLS={}; return API; }
function line(a,ox,oy,q){ var o=[], x=0, y=0; for(var i=0;i<a.length;i+=2){ if(i===0){ x=a[0]; y=a[1]; } else { x+=a[i]; y+=a[i+1]; } o.push([(x+ox)*q,(y+oy)*q]); } return o; }
var BF=['k','lv','h','bc','bm','rs','rc','rm','rl','nm','ad','po','sd','wd'], RF=['hw','nm','ln','wd','ow','sw','cy','sf','ms','lt'];
var SB={k:1,bc:1,bm:1,rs:1,rc:1,rm:1,nm:1,ad:1,po:1,sd:1,wd:1}, SR={hw:1,nm:1,sw:1,cy:1,sf:1,ms:1};
function props(names,str,p){ var d={}; for(var i=0;i<names.length;i++){ var v=i<p.length?p[i]:0; d[names[i]]=str[names[i]]?B.S[v]:v; } return d; }
function cell(ix,iy){
  var key=ix+','+iy; if(CELLS[key]) return CELLS[key];
  var c=B&&B.c[key]||{}, q=B.q, ox=ix*B.cs, oy=iy*B.cs, S=B.S, out={b:[],r:[],t:[],f:[],p:[],e:[]}, i, j, d, a;
  (c.b||[]).forEach(function(r){ d=props(BF,SB,r[1]); d.hm=d.h*q; d.ring=line(r[0],ox,oy,q); d.holes=(r[2]||[]).map(function(h){ return line(h,ox,oy,q); }); out.b.push(d); });
  (c.r||[]).forEach(function(r){ d=props(RF,SR,r[1]); d.line=line(r[0],ox,oy,q); out.r.push(d); });
  [['t',4,['sp','lf']],['f',3,['kind']],['p',5,['name','cat','ad']],['e',3,['kind']]].forEach(function(s){
    a=c[s[0]]||[]; for(i=0;i<a.length;i+=s[1]){ d={x:(a[i]+ox)*q,y:(a[i+1]+oy)*q}; for(j=0;j<s[2].length;j++) d[s[2][j]]=S[a[i+2+j]]; out[s[0]].push(d); } });
  return CELLS[key]=out;
}
function segD2(px,py,ax,ay,bx,by){ var dx=bx-ax, dy=by-ay, l=dx*dx+dy*dy, t=l?Math.max(0,Math.min(1,((px-ax)*dx+(py-ay)*dy)/l)):0, X=ax+t*dx-px, Y=ay+t*dy-py; return X*X+Y*Y; }
function nearPts(pts,x,y,r2,closed){ for(var i=0;i<pts.length;i++){ var a=pts[i], b=pts[i+1]||(closed?pts[0]:null); if(!b){ if((a[0]-x)*(a[0]-x)+(a[1]-y)*(a[1]-y)<=r2) return true; break; } if(segD2(x,y,a[0],a[1],b[0],b[1])<=r2) return true; } return false; }
function near(x,y,r,kinds){
  var out={b:[],r:[],t:[],f:[],p:[],e:[]}; if(!B) return out; kinds=kinds||'brtfpe';
  var q=B.q*B.cs, i0=Math.floor((x-r)/q), i1=Math.floor((x+r)/q), j0=Math.floor((y-r)/q), j1=Math.floor((y+r)/q), r2=r*r, nx=B.n[0], ny=B.n[1];
  for(var i=Math.max(0,i0-1);i<=Math.min(nx-1,i1+1);i++) for(var j=Math.max(0,j0-1);j<=Math.min(ny-1,j1+1);j++){
    if(!B.c[i+','+j]) continue; var c=cell(i,j);
    if(kinds.indexOf('b')>=0) c.b.forEach(function(f){ if(nearPts(f.ring,x,y,r2,true)) out.b.push(f); });
    if(kinds.indexOf('r')>=0) c.r.forEach(function(f){ if(nearPts(f.line,x,y,r2,false)) out.r.push(f); });
    ['t','f','p','e'].forEach(function(k){ if(kinds.indexOf(k)>=0) c[k].forEach(function(f){ if((f.x-x)*(f.x-x)+(f.y-y)*(f.y-y)<=r2) out[k].push(f); }); });
  }
  return out;
}
function fromLatLon(lat,lon){ return [(lon-B.o[1])*B.kx,(lat-B.o[0])*B.ky]; }
function toLatLon(x,y){ return [B.o[0]+y/B.ky, B.o[1]+x/B.kx]; }
function toMap(x,y,sc){ sc=sc||1; return [x*sc,((B.o[2]-B.o[0])*B.ky-y)*sc]; }
function load(url){
  if(PROM) return PROM;
  return PROM=fetch(url).then(function(r){ if(!r.ok) throw new Error('street '+r.status); return r.json(); }).then(use,function(e){ PROM=null; throw e; });
}
var API={load:load,use:use,ready:function(){ return !!B; },attribution:function(){ return B?B.a:''; },cell:cell,near:near,fromLatLon:fromLatLon,toLatLon:toLatLon,toMap:toMap};
window._palStreet=API;
})();
"""
