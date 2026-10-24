"""The Memory Palace's highways, on the page (data: city_highways.py, the map's M.hw).

  * each highway (Interstate, expressway, parkway, freeway) is ONE named route line, drawn like Alto's connecting lines
    but as a road: a thicker glass tube in the road colour with a white centre sheen and a halo casing, rounded only
    where it turns; a deck under it where it crosses water (a bridge), dashed where it runs in a tunnel;
  * its route shield ('I-95' blue, 'US-1' white, a state road's white oval, any other road green) repeats along it;
    pointing at the line names it and its two directions ("north toward Trenton · south toward the Airport");
  * its interchanges are junction rings on the line, standing where a drawn street crosses it, named by exit and street;
  * the key lists the highways (a click flies to one and lights it) and has a switch that shows / hides them all
    (remembered in this browser only);
  * Directions: window._palHw.drive(A, B) is a DRIVE option — the street graph plus each highway between its
    interchanges (joined to the streets only there: a highway passes over or under every other street), cut into
    street legs and highway legs; window._palHw.places() feeds the search (roads by name and ref, interchanges).

window._palHw is given the palace's own parts through init() (palace.py), the same parts as window._palTr.
"""

HIGHWAY_CSS = r"""
  /* ═══ HIGHWAYS (palace_highway_js.py): delimited block ═══ */
  .pal-svg{--pal-hw:#3d4757;--pal-hw-deck:#1f252e;}
  @media (prefers-color-scheme: dark){ .pal-svg{--pal-hw:#aab3bf;--pal-hw-deck:#11151b;} }
  .pal-svg .pl-hw.hw-off{display:none;}
  .pal-svg .hw-case{fill:none;stroke:var(--pal-halo);stroke-width:calc(var(--tw,1) * 16px);stroke-opacity:.95;stroke-linecap:round;stroke-linejoin:round;}
  .pal-svg .hw-deck{fill:none;stroke:var(--pal-hw-deck);stroke-width:calc(var(--tw,1) * 21px);stroke-linecap:butt;stroke-linejoin:round;opacity:.85;}
  .pal-svg .pl-tube.hw{stroke-width:calc(var(--tw,1) * 11px);}
  .pal-svg .pl-sheen.hw{stroke-width:calc(var(--tw,1) * 3px);}
  .pal-svg .hw-tun{fill:none;stroke:var(--pal-halo);stroke-width:calc(var(--tw,1) * 5px);stroke-dasharray:calc(var(--tw,1) * 9px) calc(var(--tw,1) * 7px);stroke-linecap:butt;}
  .pal-svg .pl-hwl{transition:opacity .15s;}
  .pal-svg.hw-focus .pl-hwl:not(.hot){opacity:.3;}
  .pal-svg .pl-hwl.hot .pl-tube{stroke:var(--accent,#6d5bd0);}
  .pal-svg .hw-sh rect{stroke:#fff;stroke-width:1.4;}
  .pal-svg .hw-sh text{font:800 12px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;text-anchor:middle;dominant-baseline:central;}
  .pal-svg .hw-sh.i rect{fill:#1d4f9c;} .pal-svg .hw-sh.i text{fill:#fff;} .pal-svg .hw-sh.i path{fill:#c8102e;}
  .pal-svg .hw-sh.us rect,.pal-svg .hw-sh.st rect{fill:#fff;stroke:#1d2229;} .pal-svg .hw-sh.us text,.pal-svg .hw-sh.st text{fill:#1d2229;}
  .pal-svg .hw-sh.o rect{fill:#1f7a3e;} .pal-svg .hw-sh.o text{fill:#fff;}
  .pal-svg .hw-sh.nm rect{fill:var(--pal-hw);} .pal-svg .hw-sh.nm text{fill:#fff;font-weight:700;}
  .pal-svg .pl-hwx circle{fill:#fff;stroke:var(--pal-hw);stroke-width:3;}
  .pal-svg .pl-hwx.hot circle{stroke:var(--accent,#6d5bd0);}
  .pal-svg .hw-hit{fill:none;stroke:transparent;stroke-width:calc(var(--tw,1) * 22px);pointer-events:stroke;cursor:pointer;}
  .pal-svg .hw-xhit{fill:transparent;cursor:pointer;}
  .pal-svg .pl-hw.hw-off ~ .pl-hw-hits{display:none;}
  #pal-ctl .hw-tog{margin-left:auto;border:0;border-radius:10px;padding:2px 9px;font:600 11px -apple-system,BlinkMacSystemFont,sans-serif;background:color-mix(in srgb,var(--text) 9%,transparent);color:var(--text);cursor:pointer;}
  #pal-ctl .hw-tog.on{background:var(--accent,#6d5bd0);color:#fff;}
"""

HIGHWAY_JS = r"""
/* ═══ HIGHWAYS (palace_highway_js.py) ═══ */
(function(){
if(window._palHw) return;
var NS='http://www.w3.org/2000/svg', E=null, H=null, S={on:true, hot:null}, DG=null;
function el(tag,attrs,parent){ var e=document.createElementNS(NS,tag); for(var k in attrs) e.setAttribute(k,attrs[k]); if(parent) parent.appendChild(e); return e; }
function esc(v){ return String(v==null?'':v).replace(/[&<>"]/g,function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
function roadOf(id){ return H && H.byId[id]; }
function title(r){ return (r.ref ? r.ref+(r.n && r.n!==r.ref ? ' · '+r.n : '') : r.n); }
function dirText(r){ return (r.dir||[]).filter(function(d){ return d && d[0]; }).map(function(d){ return d[0]+(d[1]?' toward '+d[1]:''); }).join(' · '); }
function tip(r){ var t=title(r), d=dirText(r); return t+(d?' — '+d:''); }
function xName(x){ return (x.ex&&x.ex.length?'Exit '+x.ex.join('/')+' · ':'')+(x.n||''); }
function load(){ try{ var v=localStorage.getItem('alto.palace.hw'); if(v==='0') S.on=false; }catch(e){} }
function save(){ try{ localStorage.setItem('alto.palace.hw', S.on?'1':'0'); }catch(e){} }
function init(e){ E=e; H=null; var h=E.M.hw;
  if(h && h.roads && h.roads.length){ H={roads:h.roads, x:h.x||[], byId:{}}; h.roads.forEach(function(r){ H.byId[r.id]=r; }); load(); }
  return !!H; }
function has(){ return !!H; }

/* ── drawing: under the transit lines; decks under the road, tunnels over it ── */
function lines(svg){
  if(!H) return; var g=el('g',{'class':'pl-hw'+(S.on?'':' hw-off')},svg); svg._hw=g;
  H.roads.forEach(function(r){ var lg=el('g',{'class':'pl-hwl','data-h':r.id},g), c=getComputedStyle(svg).getPropertyValue('--pal-hw').trim()||'#3d4757';
    (r.br||[]).forEach(function(a){ el('path',{'class':'hw-deck', d:E.pts(a)},lg); });
    r.p.forEach(function(a){ var d=E.rp(a,18); el('path',{'class':'hw-case', d:d},lg); E.tube(lg, d, c, 8.6, .97, 'hw'); });
    (r.tn||[]).forEach(function(a){ el('path',{'class':'hw-tun', d:E.pts(a)},lg); }); });
}
function shield(parent, r, x, y, k){
  var cls=r.ref?(r.net||'o'):'nm', txt=r.ref||short(r.n), w=Math.max(34, 8*txt.length+12);
  var g=E.pin(parent, 'hw-sh '+cls, x, y, {'data-h':r.id}), rx=cls==='st'?9:cls==='i'?3:4;
  el('rect',{x:-w/2, y:-10, width:w, height:20, rx:rx},g);
  if(cls==='i') el('path',{d:'M'+(-w/2+1.5)+' -8.5h'+(w-3)+'v5h-'+(w-3)+'z'},g);
  var t=el('text',{x:0, y:cls==='i'?1.6:0},g); t.textContent=txt; return g; }
function short(n){ return String(n||'').replace(/Expressway/,'Expy').replace(/Parkway/,'Pkwy').replace(/Freeway/,'Fwy').replace(/Highway/,'Hwy').replace(/Memorial /,''); }
function stops(svg){
  if(!H) return; var stl=el('g',{'class':'pl-hw-stops'},svg), sh=el('g',{'class':'pl-hw-sh'},svg); svg._hws=stl; svg._hwsh=sh;
  if(!S.on){ stl.style.display='none'; sh.style.display='none'; }
  H.x.forEach(function(x,i){ var g=E.pin(stl,'pl-hwx', x.x, x.y, {'data-x':i,'data-h':x.r}); el('circle',{r:5.2},g);
    E.stLbl(stl, 'pl-stt hw-xl', xName(x), x.x, x.y, false).setAttribute('data-x', i); });
  H.roads.forEach(function(r){ (r.sh||[]).forEach(function(s,k){ shield(sh, r, s[0], s[1], k); }); });
}
function hits(svg){
  if(!H || svg._sid!=='d') return; var h=el('g',{'class':'pl-hw-hits'},svg); svg._hwh=h; if(!S.on) h.style.display='none';
  H.roads.forEach(function(r){ r.p.forEach(function(a){ el('path',{'class':'hw-hit', d:E.pts(a),'data-h':r.id},h); }); });
  H.x.forEach(function(x,i){ el('circle',{'class':'hw-xhit', r:11}, E.pin(h, 'pl-hwx-hit', x.x, x.y, {'data-x':i})); });
}
function paint(){ var svg=E&&E.svg(); if(!svg || !svg._hw) return;
  svg.classList.toggle('hw-focus', !!S.hot);
  svg._hw.querySelectorAll('.pl-hwl').forEach(function(g){ g.classList.toggle('hot', g.getAttribute('data-h')===S.hot); });
  if(svg._hws) svg._hws.querySelectorAll('.pl-hwx').forEach(function(g){ g.classList.toggle('hot', g.getAttribute('data-h')===S.hot); }); }
function fit(id){ var r=roadOf(id), cv=document.getElementById('canvas'); if(!r || !cv) return; var x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
  r.p.forEach(function(a){ for(var k=0;k+1<a.length;k+=2){ x0=Math.min(x0,a[k]); x1=Math.max(x1,a[k]); y0=Math.min(y0,a[k+1]); y1=Math.max(y1,a[k+1]); } });
  var w=Math.max(x1-x0,300), h=Math.max(y1-y0,300), z=Math.min((cv.clientWidth-120)/w, (cv.clientHeight-200)/h);
  E.flyMap((x0+x1)/2, (y0+y1)/2, Math.max(.05, Math.min(2.4, z))); }
function pick(id){ S.hot=(S.hot===id?null:id); paint(); if(S.hot) fit(id); }
function show(on){ S.on=!!on; save(); document.querySelectorAll('.pal-svg').forEach(function(svg){
    if(svg._hw) svg._hw.classList.toggle('hw-off', !S.on); [svg._hws, svg._hwsh, svg._hwh].forEach(function(g){ if(g) g.style.display=S.on?'':'none'; }); });
  document.querySelectorAll('#pal-ctl .hw-tog').forEach(function(b){ b.classList.toggle('on', S.on); b.textContent=S.on?'Shown':'Hidden'; }); }

/* ── the key ── */
function keyHtml(sw){ if(!H) return '';
  var h='<div class="pk-row"><div><b>Highways</b> <small>'+H.roads.length+' · named route lines, exits as rings</small></div><button type="button" class="hw-tog'+(S.on?' on':'')+'" data-hwtog="1">'+(S.on?'Shown':'Hidden')+'</button></div>';
  H.roads.forEach(function(r){ var c=r.net==='i'?'#1d4f9c':r.net==='o'?'#1f7a3e':'#fff', tc=(r.net==='us'||r.net==='st')?'#1d2229':'#fff', t=r.ref||'';
    h+='<div class="pk-row" data-hw="'+esc(r.id)+'" style="cursor:pointer">'+sw('<line x1="1" y1="6" x2="25" y2="6" stroke="#5b6573" stroke-width="7" stroke-linecap="round"/><line x1="1" y1="6" x2="25" y2="6" stroke="#fff" stroke-width="1.6" stroke-linecap="round" opacity=".85"/>')
      +'<div>'+(t?'<span style="display:inline-block;min-width:26px;padding:0 4px;border-radius:3px;background:'+c+';color:'+tc+';border:1px solid #1d2229;font:800 10px sans-serif;text-align:center;margin-right:4px">'+esc(t)+'</span>':'')+esc(r.n)
      +' <small>'+H.x.filter(function(x){ return x.r===r.id; }).length+' interchanges'+(dirText(r)?' · '+esc(dirText(r)):'')+'</small></div></div>'; });
  h+='<div class="pk-row">'+sw('<line x1="1" y1="6" x2="25" y2="6" stroke="#5b6573" stroke-width="6"/><circle cx="13" cy="6" r="4.4" fill="#fff" stroke="#5b6573" stroke-width="2.6"/>')+'<div>Interchange <small>an exit where a street meets the highway — the only place a highway joins the streets</small></div></div>';
  h+='<div class="pk-row">'+sw('<line x1="1" y1="6" x2="25" y2="6" stroke="#2f3640" stroke-width="10"/><line x1="1" y1="6" x2="25" y2="6" stroke="#5b6573" stroke-width="6"/><line x1="4" y1="6" x2="22" y2="6" stroke="#fff" stroke-width="2.6" stroke-dasharray="4 3"/>')+'<div>Bridge / tunnel <small>a deck where it crosses water; dashed where it runs underground</small></div></div>';
  return h; }

/* ── the search: roads by name or ref, and their interchanges ── */
function places(){ if(!H) return []; var out=[];
  H.roads.forEach(function(r){ var a=r.p.slice().sort(function(p,q){ return q.length-p.length; })[0], k=Math.floor(a.length/4)*2, x=a[k], y=a[k+1];
    out.push({k:'h', id:'h:'+r.id, name:title(r), num:'', sub:'Highway'+(r.names&&r.names.length>1?' · '+r.names.slice(1,4).join(' · '):'')+(r.refs&&r.refs.length>1?' · '+r.refs.join(' / '):''), x:x, y:y, node:E.nearest(x,y,1,800)}); });
  H.x.forEach(function(x,i){ var r=roadOf(x.r); out.push({k:'x', id:'hx:'+i, name:xName(x), num:'', sub:(r?(r.ref||r.n):'')+' interchange', x:x.x, y:x.y, node:E.nearest(x.x,x.y,1,600)}); });
  return out; }

/* ── Directions: the drive option. Streets cost their length, a highway HWC of it, getting on or off RAMP; a highway
      joins the street graph only at its interchanges ── */
var HWC=.28, RAMP=90;
function dgraph(){ if(DG) return DG; var g=E.graph(), N=g.X.length, X=g.X.slice(), Y=g.Y.slice(), adj=g.adj.map(function(a){ return a.map(function(e){ return [e[0], e[1], null]; }); }), lid=[], xat={};
  for(var i=0;i<N;i++) lid.push(null);
  function add(a,b,c,l){ adj[a].push([b,c,l]); adj[b].push([a,c,l]); }
  function nd(x,y,l){ X.push(x); Y.push(y); adj.push([]); lid.push(l); return X.length-1; }
  H.roads.forEach(function(r){ var mine=H.x.map(function(x,i){ return [x,i]; }).filter(function(q){ return q[0].r===r.id; });
    r.p.forEach(function(a){ var prev=null, ins={};
      mine.forEach(function(q){ var x=q[0], best=null; for(var k=0;k+3<a.length;k+=2){ var ax=a[k],ay=a[k+1],dx=a[k+2]-ax,dy=a[k+3]-ay,L2=dx*dx+dy*dy||1e-9,t=Math.max(0,Math.min(1,((x.x-ax)*dx+(x.y-ay)*dy)/L2)),d=Math.hypot(ax+t*dx-x.x,ay+t*dy-x.y);
          if(!best||d<best.d) best={k:k,t:t,d:d}; } if(best && best.d<6) (ins[best.k]=ins[best.k]||[]).push({t:best.t, i:q[1]}); });
      for(var k=0;k+1<a.length;k+=2){ var n=nd(a[k],a[k+1],r.id); if(prev!=null) add(prev,n,Math.hypot(X[n]-X[prev],Y[n]-Y[prev])*HWC,r.id); prev=n;
        (ins[k]||[]).sort(function(p,q){ return p.t-q.t; }).forEach(function(q){ if(k+3>=a.length) return; var x=H.x[q.i], m=nd(x.x,x.y,r.id);
          add(prev,m,Math.hypot(X[m]-X[prev],Y[m]-Y[prev])*HWC,r.id); prev=m; (xat[q.i]=xat[q.i]||[]).push(m);
          var st=E.nearest(x.x,x.y,1,500); if(st>=0) add(st,m,Math.hypot(X[st]-x.x,Y[st]-x.y)+RAMP,null); }); } }); });
  DG={X:X,Y:Y,adj:adj,lid:lid,N:N,xat:xat}; return DG; }
function dijk(g,a,b){ var dist={}, prev={}, H_=[[0,a]]; dist[a]=0;
  function push(it){ H_.push(it); var i=H_.length-1; while(i>0){ var p=(i-1)>>1; if(H_[p][0]<=H_[i][0]) break; var t=H_[p]; H_[p]=H_[i]; H_[i]=t; i=p; } }
  function pop(){ var top=H_[0], last=H_.pop(); if(H_.length){ H_[0]=last; var i=0; for(;;){ var l=2*i+1, r=l+1, m=i; if(l<H_.length&&H_[l][0]<H_[m][0]) m=l; if(r<H_.length&&H_[r][0]<H_[m][0]) m=r; if(m===i) break; var t=H_[m]; H_[m]=H_[i]; H_[i]=t; i=m; } } return top; }
  while(H_.length){ var it=pop(), d=it[0], u=it[1]; if(d>dist[u]) continue; if(u===b) break;
    g.adj[u].forEach(function(e){ var nd=d+e[1]; if(dist[e[0]]==null||nd<dist[e[0]]){ dist[e[0]]=nd; prev[e[0]]=u; push([nd,e[0]]); } }); }
  if(dist[b]==null) return null; var out=[b]; while(out[out.length-1]!==a) out.push(prev[out[out.length-1]]); return out.reverse(); }
var COMP=['east','northeast','north','northwest','west','southwest','south','southeast'];
function compass(dx,dy){ var a=Math.atan2(-dy,dx)*180/Math.PI; if(a<0) a+=360; return COMP[Math.round(a/45)%8]; }
function bound(r, dx, dy){ var m=/^I-(\d+)/.exec(r.ref||''), ns=m?(+m[1])%2===1:Math.abs(dy)>=Math.abs(dx), w=ns?(dy>0?'south':'north'):(dx>0?'east':'west');
  var d=(r.dir||[]).filter(function(q){ return q[0]===w; })[0]; return w+(d&&d[1]?' toward '+d[1]:''); }
function xAt(g, n){ var hit=null; Object.keys(g.xat).forEach(function(i){ if(g.xat[i].indexOf(n)>=0) hit=H.x[+i]; }); return hit; }
function drive(A, B){ if(!H || !A || !B || A.node<0 || B.node<0) return null; var g=dgraph(), path=dijk(g, A.node, B.node); if(!path) return null;
  var legs=[], cur=null, gn=E.graph().names;
  for(var i=0;i+1<path.length;i++){ var u=path[i], v=path[i+1], l=(g.lid[u]&&g.lid[u]===g.lid[v])?g.lid[u]:null;
    if(!cur || cur.l!==l){ cur={k:'ride', l:l, n:[u]}; legs.push(cur); } cur.n.push(v); }
  if(!legs.some(function(l){ return l.l; })) return null;           /* no highway on the way: walking / transit say it already */
  var steps=[{k:'start', ic:'start', text:'Start at '+(A.num?A.num+' ':'')+A.name, sub:A.sub, x:A.x, y:A.y}], blocks=0, hwb=0, refs=[];
  legs.forEach(function(l,li){ l.pts=l.n.map(function(n){ return [g.X[n],g.Y[n]]; });
    if(li===0) l.pts.unshift([A.x,A.y]); if(li===legs.length-1) l.pts.push([B.x,B.y]);
    if(l.l){ var r=roadOf(l.l), a=l.pts[0], b=l.pts[l.pts.length-1], xi=xAt(g,l.n[0]), xo=xAt(g,l.n[l.n.length-1]), L=0;
      for(var k=1;k<l.pts.length;k++) L+=Math.hypot(l.pts[k][0]-l.pts[k-1][0], l.pts[k][1]-l.pts[k-1][1]); hwb+=L/240;
      l.color='#5b6573'; l.board={x:a[0],y:a[1],n:xi?xName(xi):''}; l.alight={x:b[0],y:b[1],n:xo?xName(xo):''}; l.line={n:title(r)}; refs.push(r.ref||r.n);
      steps.push({k:'board', ic:'ride', c:'#5b6573', text:'Take '+(r.ref||r.n)+' '+bound(r,b[0]-a[0],b[1]-a[1])+(xi?' at '+xName(xi):''), sub:r.n, x:a[0], y:a[1]});
      steps.push({k:'alight', ic:'off', c:'#5b6573', text:'Leave '+(r.ref||r.n)+(xo?' at '+xName(xo):''), sub:Math.max(1,Math.round(L/240))+' blocks on the highway', x:b[0], y:b[1]}); }
    else { l.color='var(--accent,#6d5bd0)'; var run=null, runs=[];
      for(var k=0;k+1<l.n.length;k++){ var u=l.n[k], v=l.n[k+1]; if(u>=g.N||v>=g.N) continue; var nu=Object.keys(gn[u]||{}), nv=Object.keys(gn[v]||{}), nm=nu.filter(function(x){ return (gn[v]||{})[x]; })[0]||'';
        if(!run || (nm && run.name && nm!==run.name)){ run={name:nm, b:0, x0:g.X[u], y0:g.Y[u]}; runs.push(run); } else if(!run.name) run.name=nm;
        if(nv.length>=2) run.b++; run.x1=g.X[v]; run.y1=g.Y[v]; }
      runs.forEach(function(r){ if(Math.hypot(r.x1-r.x0,r.y1-r.y0)<2) return; var b=Math.max(1,r.b); blocks+=b;
        steps.push({k:'walk', ic:'ride', text:'Drive '+b+' block'+(b>1?'s':'')+' '+compass(r.x1-r.x0,r.y1-r.y0)+(r.name?' on '+r.name:''), x:r.x0, y:r.y0}); }); } });
  steps.push({k:'arrive', ic:'arrive', text:'Arrive at '+(B.num?B.num+' ':'')+B.name, sub:B.sub, x:B.x, y:B.y});
  var min=Math.max(2, Math.round(blocks*.45 + hwb*.12 + 2)), uniq=refs.filter(function(v,k,a){ return a.indexOf(v)===k; });
  var bb=[1e9,1e9,-1e9,-1e9]; legs.forEach(function(l){ l.pts.forEach(function(p){ bb[0]=Math.min(bb[0],p[0]); bb[1]=Math.min(bb[1],p[1]); bb[2]=Math.max(bb[2],p[0]); bb[3]=Math.max(bb[3],p[1]); }); });
  return {kind:'drive', min:min, rides:uniq.length, rideStops:0, blocks:blocks, legs:legs, steps:steps, summary:min+' min · drive by '+uniq.join(', '), box:bb, lines:uniq}; }

/* ── pointing and clicking (the whole page: desktop board or phone map) ── */
function bind(){
  document.addEventListener('mouseover', function(e){ var t=e.target; if(!H || !t.closest) return;
    var h=t.closest('.hw-hit'), x=t.closest('.pl-hwx-hit');
    if(h){ var r=roadOf(h.getAttribute('data-h')); if(r && window._palHover) window._palHover(h, tip(r)); }
    else if(x){ var q=H.x[+x.getAttribute('data-x')], r2=q&&roadOf(q.r); if(q && window._palHover) window._palHover(x, xName(q)+(r2?' · '+(r2.ref||r2.n):'')); } });
  document.addEventListener('mouseout', function(e){ var t=e.target; if(t.closest && (t.closest('.hw-hit')||t.closest('.pl-hwx-hit')) && window._palHover) window._palHover(null); });
  document.addEventListener('click', function(e){ var t=e.target; if(!H || !t.closest) return;
    var tg=t.closest('[data-hwtog]'); if(tg){ e.stopPropagation(); show(!S.on); return; }
    var k=t.closest('#pal-ctl [data-hw]'); if(k){ pick(k.getAttribute('data-hw')); return; }
    var h=t.closest('.hw-hit'); if(h){ pick(h.getAttribute('data-h')); return; }
    var x=t.closest('.pl-hwx-hit'); if(x){ var q=H.x[+x.getAttribute('data-x')]; if(q) E.flyMap(q.x, q.y, Math.max(E.Z(), 1.0)); } }, true);
}
var bound_=false;
function ready(){ if(!bound_ && H){ bound_=true; bind(); } paint(); }
window._palHw={init:init, has:has, lines:lines, stops:stops, hits:hits, keyHtml:keyHtml, places:places, drive:drive, show:show, pick:pick, ready:ready,
  shown:function(){ return S.on; }, roads:function(){ return H?H.roads:[]; }, xs:function(){ return H?H.x:[]; }};
})();
"""
