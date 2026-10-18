"""The client side of the street data (palace_street.py has the format): STREET_JS, a small decoder the first-person ride includes.

The ride gets the manifest's hash from the page's map data (m.street.h, 12 hex chars; the page growth is that one field) and does

    _palStreet.load('/street/palace-street-' + M.street.h + '.json').then(function(){ return _palStreet.need(x, y, 120); }).then(function(){ var near = _palStreet.near(x, y, 60); ... });

STREET_JS defines  window._palStreet  (a no-op when it already exists):
  load(url)              fetch the MANIFEST (a Promise; a second call returns the same promise; rejects, never throws, on a network, 404, HTML or format error; a FAILED load is not remembered:
                         the next call tries again once the backoff (2 s, 4 s, 8 s.. up to 60 s, jittered) is over, and rejects at once, without a request, until then). Shards are fetched on demand from the same folder.
  use(manifest, shards)  the same with parsed objects (tests, inline use); shards optional: {id: shard}
  ready()                true once a manifest is in
  attribution()          the string to show ("© OpenStreetMap contributors, ODbL"; empty before a manifest is in)
  place(x, y)            the real neighbourhood / suburb / quarter (OSM place=*) at a point in metres: the smallest drawn outline that contains it, else a place node within 300 m, else ''
  health()               {fails, wait(ms until a retry is allowed), last(message)} of the most recent loads, for a "loading the street" note
  need(x, y, r)          Promise: fetches the shard files under the circle (x, y, r metres) and its 8-neighbour cells that are not loaded yet; resolves to the API
  loaded(x, y, r)        true when every shard under that circle is in
  cell(ix, iy)           the decoded cell (cached): undefined while its shard is not loaded yet, an empty cell when the manifest has nothing there, else
                         {b, r, t, f, p, e, a, w, l} — arrays of objects, every coordinate in METRES east (x) and north (y) of the blob origin
                         b: {k, lv, h(units), hm(m), mh, mhm(m), bc, bm, rs, rc, rm, rl, nm, ad, po, sd, wd, fl, colour:'#rrggbb', material:'brick'.., storefront:bool,
                             ty, yr, er, st, ss, hs, fr(units), frm(m), by, pe, fe, pw, pc, rd, cf, ar, hr, wp, ex, sy, tp(units), tpm(m: top, >= hm), typology:'rowhouse'.., era:'victorian'..,
                             party(i): true when ring edge i is a party wall (pe), front: the front edge index or -1,
                             ring:[[x,y]..], holes:[[[x,y]..]..]}      (bc / rc are RGB565 ints, bm a material code; the accuracy block: palace_street.py)
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
var B=null, CELLS={}, SH={}, INFL={}, PROM=null, BASE='', FAIL={}, QUE=[], RUN=0, MAXF=4, LASTERR='', DEFATTR='© OpenStreetMap contributors, ODbL';
var TYP=['unknown','rowhouse','twin','detached','lowrise_apts','midrise','highrise','storefront_row','civic','industrial','religious','parking','office','hotel','school','hospital','mixed_use'],
    ERA=['unknown','colonial_federal','victorian','early_modern','postwar','contemporary'];
var MATS=['','brick','stone','stucco','painted','concrete','glass','metal','wood','brownstone','cladding','tile','plaster'];
var IB=null, HEXID=/^[0-9a-f]{8}$/;
function num(v){ return typeof v==='number' && isFinite(v); }
function arr(v){ return Object.prototype.toString.call(v)==='[object Array]'; }
function obj(v){ return !!v && typeof v==='object' && !arr(v); }
/* the shape of a manifest / a shard: anything else is a failed download (HTML from a rewrite, a truncated or newer file), never a half-working world */
function okManifest(b){
  if(!obj(b)||b.v!==2||!obj(b.c)||!obj(b.f)) return false;
  if(!num(b.q)||b.q<=0||!num(b.cs)||b.cs<=0||!num(b.kx)||b.kx<=0||!num(b.ky)||b.ky<=0) return false;
  if(!arr(b.o)||b.o.length!==4||!b.o.every(num)||b.o[0]<-90||b.o[2]>90||b.o[1]<-180||b.o[3]>180) return false;
  if(!arr(b.n)||b.n.length!==2||!b.n.every(function(v){ return num(v)&&v>=1&&v<=100000&&Math.floor(v)===v; })) return false;
  for(var k in b.f) if(!HEXID.test(k)||!num(b.f[k])) return false;
  for(var c in b.c){ if(!/^-?\d+,-?\d+$/.test(c)||typeof b.c[c]!=='string'||!HEXID.test(b.c[c])) return false; }
  if(b.ib!==undefined && !(obj(b.ib)&&arr(b.ib.r)&&b.ib.r.every(function(r){ return arr(r)&&r.length===3&&r.every(num); }))) return false;
  if(b.pl!==undefined && !(arr(b.pl)&&b.pl.every(function(p){ return arr(p)&&typeof p[0]==='string'&&num(p[2])&&num(p[3])&&(p[4]===0||(arr(p[4])&&p[4].length%2===0&&p[4].every(num))); }))) return false;
  if(b.a!==undefined && typeof b.a!=='string') return false;
  return true; }
var PTW={t:4,f:4,p:5,e:3}, POLY={b:1,a:1,r:1,w:1,l:1};
function okShard(sh){
  if(!obj(sh)||!arr(sh.S)||!obj(sh.c)||!sh.S.every(function(v){ return typeof v==='string'; })) return false;
  for(var k in sh.c){ var c=sh.c[k]; if(!obj(c)) return false;
    for(var kind in c){ var L=c[kind]; if(!arr(L)) return false;
      if(PTW[kind]){ if(L.length%PTW[kind]!==0||!L.every(num)) return false; }
      else if(POLY[kind]){ for(var i=0;i<L.length;i++){ var r=L[i]; if(!arr(r)||!arr(r[0])||r[0].length%2!==0||!arr(r[1])) return false; } } } }
  return true; }
function use(b,shards){ if(!okManifest(b)) throw new Error('street manifest'); B=b; CELLS={}; SH={}; INFL={}; IB=null; if(shards){ for(var id in shards) if(okShard(shards[id])) SH[id]=shards[id]; } return API; }
/* the in-bounds extent the data was written for (manifest ib: runs [iy, ix0, ix1] of cells, buffered b metres): true without ib (the whole box) */
function inScope(x,y){ if(!B||!B.ib) return true; if(!IB){ IB={}; B.ib.r.forEach(function(r){ IB[r[0]]=(IB[r[0]]||[]).concat([[r[1],r[2]]]); }); } var q=B.q*B.cs, ix=Math.floor(x/q), iy=Math.floor(y/q), L=IB[iy]; if(!L) return false; for(var i=0;i<L.length;i++) if(ix>=L[i][0]&&ix<=L[i][1]) return true; return false; }
function line(a,ox,oy,q){ var o=[], x=0, y=0; for(var i=0;i<a.length;i+=2){ if(i===0){ x=a[0]; y=a[1]; } else { x+=a[i]; y+=a[i+1]; } o.push([(x+ox)*q,(y+oy)*q]); } return o; }
var BF=['k','lv','h','bc','bm','rs','rc','rm','rl','nm','ad','po','sd','wd','fl','mh','ty','yr','er','st','ss','hs','fr','by','pe','fe','pw','pc','rd','cf','ar','hr','wp','ex','sy','tp'], RF=['hw','nm','ln','wd','ow','sw','cy','sf','ms','lt','sl','sr','cl','cr','br','tn','la'],
    AF=['k','nm','sp','sf'], WF=['k','ht','mt'], LF=['sp','lf'];
function set(a){ var o={}; a.forEach(function(k){ o[k]=1; }); return o; }
var SB=set(['k','rs','rm','nm','ad','po','sd','wd','ar','hr','wp','sy']), SR=set(['hw','nm','sw','cy','sf','ms','sl','sr','cl','cr']), SA=set(AF), SW=set(['k','mt']), SL=set(LF);
function props(names,str,p,S){ var d={}; for(var i=0;i<names.length;i++){ var v=i<p.length?p[i]:0; d[names[i]]=str[names[i]]?S[v]:v; } return d; }
function hex(v){ var r=(v>>11)&31, g=(v>>5)&63, b=v&31; function h(n){ return ('0'+n.toString(16)).slice(-2); } return '#'+h((r<<3)|(r>>2))+h((g<<2)|(g>>4))+h((b<<3)|(b>>2)); }
function partyOf(pe){ return function(i){ return i<31 && !!((pe>>>i)&1); }; }
function empty(){ return {b:[],r:[],t:[],f:[],p:[],e:[],a:[],w:[],l:[]}; }
function cell(ix,iy){
  var key=ix+','+iy; if(CELLS[key]) return CELLS[key]; if(!B) return undefined;
  var id=B.c[key]; if(!id) return CELLS[key]=empty();
  var sh=SH[id]; if(!sh) return undefined;
  try{ return decode(key,ix,iy,sh); }catch(e){ LASTERR='street cell '+key; return CELLS[key]=empty(); } }       /* a cell that will not decode is empty, never a throw out of the frame loop */
function decode(key,ix,iy,sh){
  var c=sh.c[key]||{}, q=B.q, ox=ix*B.cs, oy=iy*B.cs, S=sh.S, out=empty(), i, j, d, a;
  (c.b||[]).forEach(function(r){ d=props(BF,SB,r[1],S); d.hm=d.h*q; d.mhm=d.mh*q; d.colour=d.bc?hex(d.bc):''; d.material=MATS[d.bm]||''; d.storefront=!!(d.fl&1);
    d.frm=d.fr*q; d.tpm=Math.max(d.tp*q,d.hm); d.typology=TYP[d.ty]||'unknown'; d.era=ERA[d.er]||'unknown'; d.front=d.fe?d.fe-1:-1; d.party=partyOf(d.pe);
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
/* ── fetching: every request goes through one queue (at most MAXF at a time), a failed one is remembered with a backoff so nothing is asked again every frame ── */
function backoff(n){ return Math.min(60000, 2000*Math.pow(2,Math.max(0,n-1)))*(0.75+0.5*((Date.now()%997)/997)); }       /* 2 s, 4 s, 8 s.. cap 60 s, +-25% jitter (from the clock: the ride keeps one random number, the tunnel's hue) */
function fail(key,msg){ var f=FAIL[key]||(FAIL[key]={n:0,until:0}); f.n++; f.until=Date.now()+backoff(f.n); LASTERR=msg; }
function waitOf(key){ var f=FAIL[key]; return f&&f.until>Date.now()?f.until-Date.now():0; }
function drain(){ while(RUN<MAXF && QUE.length){ var j=QUE.shift(); RUN++; j(); } }
function get(url,key,okf){                          /* -> Promise of a parsed, validated object; a rejection leaves nothing cached (not here, not in the browser) */
  var w=waitOf(key); if(w){ var e=new Error('street: wait '+Math.ceil(w/1000)+' s'); e.wait=w; return Promise.reject(e); }
  return new Promise(function(res,rej){
    QUE.push(function(){
      var done=function(f,v){ RUN--; setTimeout(drain,0); f(v); };
      var bad=function(msg){ fail(key,msg); done(rej,new Error(msg)); };
      var p; try{ p=fetch(url); }catch(e){ bad('street fetch'); return; }
      Promise.resolve(p).then(function(r){
        if(!r||!r.ok) throw new Error('street '+(r?r.status:'no response'));
        var ct=(r.headers&&r.headers.get&&r.headers.get('content-type'))||'';
        if(/html/i.test(ct)) throw new Error('street html');
        return typeof r.text==='function'?r.text():r.json().then(JSON.stringify); })
      .then(function(t){ if(typeof t!=='string'||/^\s*</.test(t)) throw new Error('street html'); var o; try{ o=JSON.parse(t); }catch(e){ throw new Error('street json'); }
        if(!okf(o)) throw new Error('street format'); delete FAIL[key]; done(res,o); })
      .then(null,function(e){ bad(String((e&&e.message)||e).slice(0,80)); }); });
    drain(); }); }
function need(x,y,r){
  if(!B) return Promise.reject(new Error('street: no manifest'));
  return Promise.all(missing(x,y,r).map(function(id){
    return INFL[id]||(INFL[id]=get(BASE+'s-'+id+'.json','s'+id,okShard).then(function(sh){ SH[id]=sh; delete INFL[id]; },function(e){ delete INFL[id]; throw e; }));
  })).then(function(){ return API; }); }
function fromLatLon(lat,lon){ return [(lon-B.o[1])*B.kx,(lat-B.o[0])*B.ky]; }
function toLatLon(x,y){ return [B.o[0]+y/B.ky, B.o[1]+x/B.kx]; }
function toMap(x,y,sc){ sc=sc||1; return [x*sc,((B.o[2]-B.o[0])*B.ky-y)*sc]; }
function load(url){
  if(PROM) return PROM;
  var key='m'+url, w=waitOf(key); if(w){ var e=new Error('street: wait '+Math.ceil(w/1000)+' s'); e.wait=w; return Promise.reject(e); }
  BASE=String(url).replace(/[^\/]*$/,'');
  var pr=get(url,key,okManifest).then(function(m){ return use(m); });
  PROM=pr; pr.then(null,function(){ if(PROM===pr) PROM=null; });         /* a failed manifest is forgotten: the next call asks again (after the backoff) */
  return pr; }
function pip(x,y,f){ var n=f.length/2, ins=false, i, j=n-1; for(i=0;i<n;i++){ var xi=f[2*i], yi=f[2*i+1], xj=f[2*j], yj=f[2*j+1]; if((yi>y)!==(yj>y) && x<(xj-xi)*(y-yi)/((yj-yi)||1e-9)+xi) ins=!ins; j=i; } return ins; }
function parea(f){ var a=0, n=f.length/2; for(var i=0;i<n;i++){ var j=(i+1)%n; a+=f[2*i]*f[2*j+1]-f[2*j]*f[2*i+1]; } return Math.abs(a)/2; }
/* the real neighbourhood at (x, y) metres: the smallest drawn outline that holds it, else the nearest place node within 300 m ('' when the data has none: the caller shows nothing rather than a wrong name) */
function place(x,y){ if(!B||!arr(B.pl)) return ''; var best='', ba=1e18, nn='', nd=300*300, i, p;
  for(i=0;i<B.pl.length;i++){ p=B.pl[i]; if(p[4]){ if(pip(x,y,p[4])){ var a=parea(p[4]); if(a<ba){ ba=a; best=p[0]; } } } else { var d=(p[2]-x)*(p[2]-x)+(p[3]-y)*(p[3]-y); if(d<nd){ nd=d; nn=p[0]; } } }
  return best||nn; }
function health(){ var f=0, w=0; for(var k in FAIL){ f+=FAIL[k].n; w=Math.max(w,waitOf(k)); } return {fails:f, wait:w, last:LASTERR, inflight:RUN, queued:QUE.length}; }
var API={place:place,health:health,inScope:inScope,bounds:function(){ return B&&B.ib||null; },load:load,use:use,ready:function(){ return !!B; },attribution:function(){ return B?(B.a||DEFATTR):''; },cell:cell,near:near,need:need,loaded:loaded,fromLatLon:fromLatLon,toLatLon:toLatLon,toMap:toMap};
window._palStreet=API;
})();
"""
