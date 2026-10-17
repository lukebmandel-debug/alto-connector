"""The client side of the street data (palace_street.py has the format): STREET_JS, a small decoder the first-person ride includes.

The ride gets the manifest's hash from the page's map data (m.street.h, 12 hex chars; the page growth is that one field) and does

    _palStreet.load('/street/palace-street-' + M.street.h + '.json').then(function(){ return _palStreet.need(x, y, 120); }).then(function(){ var near = _palStreet.near(x, y, 60); ... });

STREET_JS defines  window._palStreet  (a no-op when it already exists):
  load(url)              fetch the MANIFEST (a Promise; a second call returns the same promise; rejects on a network or format error). Shards are fetched on demand from the same folder.
  use(manifest, shards)  the same with parsed objects (tests, inline use); shards optional: {id: shard}
  ready()                true once a manifest is in
  attribution()          the string to show ("© OpenStreetMap contributors, ODbL")
  need(x, y, r)          Promise: fetches the shard files under the circle (x, y, r metres) and its 8-neighbour cells that are not loaded yet; resolves to the API
  loaded(x, y, r)        true when every shard under that circle is in
  cell(ix, iy)           the decoded cell (cached): undefined while its shard is not loaded yet, an empty cell when the manifest has nothing there, else
                         {b, r, t, f, p, e, a, w, l} — arrays of objects, every coordinate in METRES east (x) and north (y) of the blob origin
                         b: {k, lv, h(units), hm(m), mh, mhm(m), bc, bm, rs, rc, rm, rl, nm, ad, po, sd, wd, fl, colour:'#rrggbb', material:'brick'.., storefront:bool,
                             ring:[[x,y]..], holes:[[[x,y]..]..]}      (bc / rc are RGB565 ints, bm a material code)
                         r: {hw, nm, ln, wd(units), ow, sw, cy, sf, ms, lt, sl, sr, cl, cr, br, tn, la, line:[[x,y]..]}   t: {x, y, sp, lf}   f: {x, y, kind, dir(deg or null)}
                         p: {x, y, name, cat, ad}   e: {x, y, kind}   a: {k, nm, sp, sf, ring, holes}   w: {k, ht(m), mt, line}   l: {sp, lf, line}
  near(x, y, r, kinds)   every feature of the LOADED cells under the circle that has a point within r of it (a polygon/line: any vertex or edge point) —
                         {b:[], r:[], t:[], f:[], p:[], e:[], a:[], w:[], l:[]}; `kinds` optionally a string such as 'btf' limiting which lists are filled
  fromLatLon(lat, lon)   -> [x, y] metres     toLatLon(x, y) -> [lat, lon]
  inScope(x, y)          metres; true when the point lies in the cells the data was written for (manifest "ib"; always true without it)   bounds()  the manifest's ib or null
  toMap(x, y, scale)     -> [px, py] in the palace map's px (y down, like palace_map.project: x*scale, ((north-south)*ky - y)*scale)
Cells are decoded when first asked for, so a ride that stays in one district decodes a few KB.
"""

STREET_JS = r"""
(function(){
if(window._palStreet) return;
var B=null, CELLS={}, SH={}, INFL={}, PROM=null, BASE='';
var MATS=['','brick','stone','stucco','painted','concrete','glass','metal','wood','brownstone','cladding','tile','plaster'];
var IB=null;
function use(b,shards){ if(!b||b.v!==2||!b.c||!b.f) throw new Error('street manifest'); B=b; CELLS={}; SH=shards||{}; INFL={}; IB=null; return API; }
/* the in-bounds extent the data was written for (manifest ib: runs [iy, ix0, ix1] of cells, buffered b metres): true without ib (the whole box) */
function inScope(x,y){ if(!B||!B.ib) return true; if(!IB){ IB={}; B.ib.r.forEach(function(r){ IB[r[0]]=(IB[r[0]]||[]).concat([[r[1],r[2]]]); }); } var q=B.q*B.cs, ix=Math.floor(x/q), iy=Math.floor(y/q), L=IB[iy]; if(!L) return false; for(var i=0;i<L.length;i++) if(ix>=L[i][0]&&ix<=L[i][1]) return true; return false; }
function line(a,ox,oy,q){ var o=[], x=0, y=0; for(var i=0;i<a.length;i+=2){ if(i===0){ x=a[0]; y=a[1]; } else { x+=a[i]; y+=a[i+1]; } o.push([(x+ox)*q,(y+oy)*q]); } return o; }
var BF=['k','lv','h','bc','bm','rs','rc','rm','rl','nm','ad','po','sd','wd','fl','mh'], RF=['hw','nm','ln','wd','ow','sw','cy','sf','ms','lt','sl','sr','cl','cr','br','tn','la'],
    AF=['k','nm','sp','sf'], WF=['k','ht','mt'], LF=['sp','lf'];
function set(a){ var o={}; a.forEach(function(k){ o[k]=1; }); return o; }
var SB=set(['k','rs','rm','nm','ad','po','sd','wd']), SR=set(['hw','nm','sw','cy','sf','ms','sl','sr','cl','cr']), SA=set(AF), SW=set(['k','mt']), SL=set(LF);
function props(names,str,p,S){ var d={}; for(var i=0;i<names.length;i++){ var v=i<p.length?p[i]:0; d[names[i]]=str[names[i]]?S[v]:v; } return d; }
function hex(v){ var r=(v>>11)&31, g=(v>>5)&63, b=v&31; function h(n){ return ('0'+n.toString(16)).slice(-2); } return '#'+h((r<<3)|(r>>2))+h((g<<2)|(g>>4))+h((b<<3)|(b>>2)); }
function empty(){ return {b:[],r:[],t:[],f:[],p:[],e:[],a:[],w:[],l:[]}; }
function cell(ix,iy){
  var key=ix+','+iy; if(CELLS[key]) return CELLS[key]; if(!B) return undefined;
  var id=B.c[key]; if(!id) return CELLS[key]=empty();
  var sh=SH[id]; if(!sh) return undefined;
  var c=sh.c[key]||{}, q=B.q, ox=ix*B.cs, oy=iy*B.cs, S=sh.S, out=empty(), i, j, d, a;
  (c.b||[]).forEach(function(r){ d=props(BF,SB,r[1],S); d.hm=d.h*q; d.mhm=d.mh*q; d.colour=d.bc?hex(d.bc):''; d.material=MATS[d.bm]||''; d.storefront=!!(d.fl&1);
    d.ring=line(r[0],ox,oy,q); d.holes=(r[2]||[]).map(function(h){ return line(h,ox,oy,q); }); out.b.push(d); });
  (c.r||[]).forEach(function(r){ d=props(RF,SR,r[1],S); d.line=line(r[0],ox,oy,q); out.r.push(d); });
  (c.w||[]).forEach(function(r){ d=props(WF,SW,r[1],S); d.ht=d.ht*q; d.line=line(r[0],ox,oy,q); out.w.push(d); });
  (c.l||[]).forEach(function(r){ d=props(LF,SL,r[1],S); d.line=line(r[0],ox,oy,q); out.l.push(d); });
  (c.a||[]).forEach(function(r){ d=props(AF,SA,r[1],S); d.ring=line(r[0],ox,oy,q); d.holes=(r[2]||[]).map(function(h){ return line(h,ox,oy,q); }); out.a.push(d); });
  [['t',4,['sp','lf']],['f',4,['kind','dir']],['p',5,['name','cat','ad']],['e',3,['kind']]].forEach(function(s){
    a=c[s[0]]||[]; for(i=0;i<a.length;i+=s[1]){ d={x:(a[i]+ox)*q,y:(a[i+1]+oy)*q}; for(j=0;j<s[2].length;j++){ var v=a[i+2+j]; d[s[2][j]]=s[2][j]==='dir'?(v?v-1:null):S[v]; } out[s[0]].push(d); } });
  return CELLS[key]=out;
}
function segD2(px,py,ax,ay,bx,by){ var dx=bx-ax, dy=by-ay, l=dx*dx+dy*dy, t=l?Math.max(0,Math.min(1,((px-ax)*dx+(py-ay)*dy)/l)):0, X=ax+t*dx-px, Y=ay+t*dy-py; return X*X+Y*Y; }
function nearPts(pts,x,y,r2,closed){ for(var i=0;i<pts.length;i++){ var a=pts[i], b=pts[i+1]||(closed?pts[0]:null); if(!b){ if((a[0]-x)*(a[0]-x)+(a[1]-y)*(a[1]-y)<=r2) return true; break; } if(segD2(x,y,a[0],a[1],b[0],b[1])<=r2) return true; } return false; }
function span(x,y,r){ var q=B.q*B.cs, o=[]; var i0=Math.floor((x-r)/q)-1, i1=Math.floor((x+r)/q)+1, j0=Math.floor((y-r)/q)-1, j1=Math.floor((y+r)/q)+1;
  for(var i=Math.max(0,i0);i<=Math.min(B.n[0]-1,i1);i++) for(var j=Math.max(0,j0);j<=Math.min(B.n[1]-1,j1);j++) o.push([i,j]); return o; }
function near(x,y,r,kinds){
  var out=empty(); if(!B) return out; kinds=kinds||'brtfpeawl'; var r2=r*r;
  span(x,y,r).forEach(function(ij){
    var c=cell(ij[0],ij[1]); if(!c) return;
    ['b','a'].forEach(function(k){ if(kinds.indexOf(k)>=0) c[k].forEach(function(f){ if(nearPts(f.ring,x,y,r2,true)) out[k].push(f); }); });
    ['r','w','l'].forEach(function(k){ if(kinds.indexOf(k)>=0) c[k].forEach(function(f){ if(nearPts(f.line,x,y,r2,false)) out[k].push(f); }); });
    ['t','f','p','e'].forEach(function(k){ if(kinds.indexOf(k)>=0) c[k].forEach(function(f){ if((f.x-x)*(f.x-x)+(f.y-y)*(f.y-y)<=r2) out[k].push(f); }); });
  });
  return out;
}
function missing(x,y,r){ var ids={}; if(B) span(x,y,r).forEach(function(ij){ var id=B.c[ij[0]+','+ij[1]]; if(id&&!SH[id]) ids[id]=1; }); return Object.keys(ids); }
function loaded(x,y,r){ return !!B && missing(x,y,r).length===0; }
function need(x,y,r){
  if(!B) return Promise.reject(new Error('street: no manifest'));
  return Promise.all(missing(x,y,r).map(function(id){
    return INFL[id]||(INFL[id]=fetch(BASE+'s-'+id+'.json').then(function(res){ if(!res.ok) throw new Error('street '+res.status); return res.json(); })
      .then(function(sh){ SH[id]=sh; delete INFL[id]; },function(e){ delete INFL[id]; throw e; }));
  })).then(function(){ return API; });
}
function fromLatLon(lat,lon){ return [(lon-B.o[1])*B.kx,(lat-B.o[0])*B.ky]; }
function toLatLon(x,y){ return [B.o[0]+y/B.ky, B.o[1]+x/B.kx]; }
function toMap(x,y,sc){ sc=sc||1; return [x*sc,((B.o[2]-B.o[0])*B.ky-y)*sc]; }
function load(url){
  if(PROM) return PROM;
  BASE=url.replace(/[^\/]*$/,'');
  return PROM=fetch(url).then(function(r){ if(!r.ok) throw new Error('street '+r.status); return r.json(); }).then(function(m){ return use(m); },function(e){ PROM=null; throw e; });
}
var API={inScope:inScope,bounds:function(){ return B&&B.ib||null; },load:load,use:use,ready:function(){ return !!B; },attribution:function(){ return B?B.a:''; },cell:cell,near:near,need:need,loaded:loaded,fromLatLon:fromLatLon,toLatLon:toLatLon,toMap:toMap};
window._palStreet=API;
})();
"""
