"""The Memory Palace's transit, on the page (data: palace_transit.py).

  * the real lines (SEPTA's subways, trolleys and Regional Rail, PATCO) drawn as
    Alto's own connecting lines on the grid, their stops standing on them: a small
    dot at far zoom, named near, a striped ring where lines meet;
  * pointing at a line lights it and its stops; a click selects it and opens a
    small panel (its stops, "Ride this line"); a click on a stop flies there and
    lists the lines and transfers; riding steps stop to stop with the arrow keys
    or the panel's buttons, the map gliding along;
  * the key lists the lines and says what a dot is;
  * the top bar's ELEMENT chips: pointing at one (or turning it on in the filters)
    lights every building it tags and draws ONE route through them, along the
    transit where that helps and along streets elsewhere (a street graph with
    cheap transit edges and a walk to and from the nearest stop). The chip route
    takes precedence over the hover routes while it is up.

window._palTr is given the palace's own parts through init() (palace.py).
"""

TRANSIT_CSS = r"""
  .pal-svg .pl-tcase{fill:none;stroke:var(--pal-halo);stroke-width:calc(var(--tw,1) * 8px);stroke-opacity:.8;stroke-linecap:round;stroke-linejoin:round;}
  .pal-svg .pl-tube.tr-m{stroke-width:calc(var(--tw,1) * 5px);}
  .pal-svg .pl-sheen.tr-m{stroke-width:calc(var(--tw,1) * 1.7px);}
  .pal-svg .pl-tube.tr-r{stroke-width:calc(var(--tw,1) * 4.2px);}
  .pal-svg .pl-sheen.tr-r{stroke-width:calc(var(--tw,1) * 1.4px);}
  .pal-svg .pl-tube.tr-t{stroke-width:calc(var(--tw,1) * 3.4px);}
  .pal-svg .pl-sheen.tr-t{stroke-width:calc(var(--tw,1) * 1.2px);}
  .pal-svg .pl-tube.tr-bus{stroke-width:calc(var(--tw,1) * 2.8px);stroke-opacity:.8;}
  .pal-svg .pl-sheen.tr-bus{stroke-width:calc(var(--tw,1) * .9px);}
  .pal-svg .pl-tl[data-k=bus]{opacity:.62;}
  .pal-svg.far .pl-tl[data-k=bus],.pal-svg.far .tr-stn.bus,.pal-svg.mid .tr-stn.bus,.pal-svg.mid .tr-lbl.bus,.pal-svg.far .tr-lbl.bus{display:none;}
  .pal-svg.mid .pl-tl[data-k=bus]{opacity:.4;} .pal-svg.tr-focus .pl-tl[data-k=bus]:not(.hot){opacity:.12;} .pal-svg .pl-tl[data-k=bus].hot{opacity:1;}
  .pal-svg .tr-stn.bus .tr-ring{stroke-width:2;}
  .pal-svg .pl-tl{transition:opacity .15s;}
  .pal-svg .pl-tl.hot .pl-tube{filter:drop-shadow(0 0 3px var(--tc,#888));}
  .pal-svg.tr-focus .pl-tl:not(.hot){opacity:.22;}
  .pal-svg.tr-focus .tr-stn:not(.lit){opacity:.25;}
  /* a portal: a gateway at a station to a place off the map */
  .pal-svg .pl-portal{pointer-events:auto;cursor:pointer;}
  .pal-svg .pl-portal circle{fill:var(--surface,#fff);stroke:var(--accent,#6d5bd0);stroke-width:2;}
  .pal-svg .pl-portal text{font-size:12px;text-anchor:middle;dominant-baseline:central;pointer-events:none;fill:var(--accent,#6d5bd0);}
  .pal-svg .pl-portal line{stroke:var(--accent,#6d5bd0);stroke-width:1.5;stroke-dasharray:3 3;}
  .pal-svg .pl-portal.on-bldg circle{stroke-width:2.6;filter:drop-shadow(0 2px 3px rgba(0,0,0,.35));}
  .pal-svg .pl-portal:hover circle{fill:var(--accent,#6d5bd0);} .pal-svg .pl-portal:hover text{fill:#fff;}
  /* a line (or a filter that rides lines) in view: everything not on it steps back */
  .pal-svg.tr-focus .pl-streets,.pal-svg.tr-focus .pl-parks,.pal-svg.tr-focus .pl-washes,.pal-svg.tr-focus .pl-lms,.pal-svg.tr-focus .pl-lmb,.pal-svg.tr-focus .pl-blds,.pal-svg.tr-focus .pl-rails{opacity:.3;transition:opacity .2s;}
  html.alto-palace.tr-solo:not(.mobile) #world .node:not(.focused):not(.pal-chip-hot):not(.pal-hot){opacity:.3;}
  .pal-svg.tr-focus .tr-lbl:not(.lit){display:none;}
  .pal-svg .tr-ring{fill:var(--pal-halo);stroke-width:2.8;}
  .pal-svg .tr-ring.hubr{stroke-width:3.2;}
  .pal-svg .tr-arc{fill:none;stroke-width:3.6;}
  .pal-svg .tr-sh{fill:none;stroke:rgba(255,255,255,.75);stroke-width:1.2;}
  .pal-svg .tr-dot{transition:transform .15s;}
  .pal-svg.far .tr-stn:not(.cur) .tr-dot{transform:scale(.62);}
  .pal-svg.far .tr-lbl:not(.cur):not(.hub),.pal-svg.mid .tr-lbl:not(.cur):not(.hub):not(.lit):not(.maj){display:none;}
  .pal-svg.far .tr-lbl.hub:not(.cur):not(.lit):not(.maj){display:none;}
  .pal-svg.far .tr-lbl:not(.cur):not(.hub):not(.maj){display:none;}
  /* a mainline station (30th Street, Suburban, Jefferson …) is a landmark of the network: a bigger ring that never shrinks, named from the mid zoom */
  .pal-svg .tr-stn.maj .tr-dot{transform:scale(1.35);} .pal-svg.far .tr-stn.maj:not(.cur) .tr-dot{transform:scale(1.1);}
  .pal-svg .tr-stn.maj .tr-ring{stroke-width:3.4;}
  .pal-svg .tr-stn.lit .tr-dot,.pal-svg .tr-stn:hover .tr-dot{transform:scale(1.3);}
  .pal-svg .tr-stn.cur .tr-dot{transform:scale(1.7);}
  .pal-svg .tr-stn.cur .tr-pulse{animation:trpulse 1.6s ease-out 3;}
  .pal-svg .tr-pulse{fill:none;stroke:var(--tc,#888);stroke-width:2;opacity:0;}
  @keyframes trpulse{0%{r:8px;opacity:.9}100%{r:26px;opacity:0}}
  .pal-svg .tr-lbl{font-size:calc(11px / var(--pz,1));}
  .pal-svg .tr-lbl.cur{font-size:calc(14px / var(--pz,1));font-weight:800;}
  .pal-svg .pl-tl-hit{fill:none;stroke:transparent;stroke-width:calc(var(--tw,1) * 13px);stroke-linecap:round;stroke-linejoin:round;pointer-events:stroke;cursor:pointer;}
  .pal-svg .pl-stn-hit circle{fill:transparent;pointer-events:all;cursor:pointer;}
  /* .pl-stn-hit, like a stop, is placed by its transform attribute and sized by its inner .pl-sc (palace.py pin()) */
  /* the chip route: a tube in the chip's colour, a moving sheen and direction ticks */
  .pal-svg .pl-crt{fill:none;stroke-linecap:round;stroke-linejoin:round;pointer-events:none;}
  .pal-svg .pl-crt.case{stroke:var(--pal-halo);stroke-width:11;vector-effect:non-scaling-stroke;stroke-opacity:.85;}
  .pal-svg .pl-crt.base{stroke-width:7;vector-effect:non-scaling-stroke;stroke-opacity:.92;}
  .pal-svg .pl-crt.sh{stroke:rgba(255,255,255,.8);stroke-width:2.4;vector-effect:non-scaling-stroke;stroke-dasharray:1 16;animation:crtflow 1.4s linear infinite;}
  .pal-svg .pl-crt.tk{stroke:rgba(255,255,255,.95);stroke-width:2.2;vector-effect:non-scaling-stroke;stroke-dasharray:0.1 58;stroke-dashoffset:0;animation:crtflow 3.2s linear infinite;stroke-linecap:round;}
  @keyframes crtflow{to{stroke-dashoffset:-17;}}
  @media (prefers-reduced-motion: reduce){.pal-svg .pl-crt.sh,.pal-svg .pl-crt.tk,.pal-svg .tr-stn.cur .tr-pulse{animation:none;}}
  html.alto-palace #world .node.pal-chip-hot:not(.focused) .node-card{outline:3px solid var(--cc,#888);outline-offset:2px;}
  /* the small panel: a line, a stop, a ride */
  #pal-tr{position:fixed;left:30px;bottom:78px;z-index:311;width:290px;max-width:calc(100vw - 80px);box-sizing:border-box;padding:11px 13px 12px;border-radius:15px;display:none;
    font-size:12px;line-height:1.35;color:var(--text);background:var(--panel-glass-bg, var(--surface));
    -webkit-backdrop-filter:blur(30px) saturate(185%);backdrop-filter:blur(30px) saturate(185%);
    border:1px solid var(--card-glass-border, var(--border));box-shadow:0 18px 48px var(--node-hover-shadow);}
  #pal-tr.on{display:block;}
  #pal-tr .tr-h{display:flex;align-items:center;gap:8px;font-weight:700;font-size:13px;}
  #pal-tr .tr-sw{width:22px;height:6px;border-radius:3px;flex:none;}
  #pal-tr .tr-x{margin-left:auto;cursor:pointer;color:var(--muted);padding:0 3px;}
  #pal-tr .tr-x:hover{color:var(--text);}
  #pal-tr .tr-sub{color:var(--muted);margin:2px 0 7px;}
  #pal-tr .tr-stops{max-height:170px;overflow:auto;margin:0 -4px 8px;padding:0 4px;}
  #pal-tr .tr-st{display:flex;align-items:center;gap:8px;padding:3px 4px;border-radius:7px;cursor:pointer;}
  #pal-tr .tr-st:hover{background:color-mix(in srgb,var(--text) 8%,transparent);}
  #pal-tr .tr-st.cur{background:color-mix(in srgb,var(--tc,#888) 18%,transparent);font-weight:700;}
  #pal-tr .tr-st i{width:9px;height:9px;border-radius:50%;border:2.4px solid var(--tc,#888);box-sizing:border-box;flex:none;background:var(--pal-halo);}
  #pal-tr .tr-chips{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 8px;}
  #pal-tr .tr-chip{display:inline-flex;align-items:center;gap:6px;padding:3px 9px;border-radius:999px;cursor:pointer;border:1px solid var(--tc,#888);font-weight:600;}
  #pal-tr .tr-chip:hover{background:color-mix(in srgb,var(--tc,#888) 16%,transparent);}
  #pal-tr .tr-chip b{width:9px;height:9px;border-radius:50%;background:var(--tc,#888);display:block;}
  #pal-tr .tr-btns{display:flex;gap:7px;align-items:center;}
  #pal-tr .tr-b{cursor:pointer;border:1px solid var(--card-glass-border, var(--border));border-radius:999px;padding:5px 12px;font-weight:700;color:var(--text);background:transparent;font-size:12px;}
  #pal-tr .tr-b:hover{border-color:var(--tc,var(--muted));background:color-mix(in srgb,var(--tc,#888) 14%,transparent);}
  #pal-tr .tr-b.go{background:var(--tc,#888);color:#fff;border-color:transparent;}
  #pal-tr .tr-b[disabled]{opacity:.35;pointer-events:none;}
  #pal-tr .tr-steps{list-style:none;margin:2px -4px 8px;padding:0 4px;max-height:176px;overflow:auto;font-size:11.5px;}
  #pal-tr .tr-steps li{display:flex;gap:8px;align-items:flex-start;padding:3px 0;line-height:1.3;}
  #pal-tr .tr-steps li b{flex:none;width:9px;height:9px;margin-top:3px;border-radius:50%;border:2.4px solid var(--sc,var(--muted));box-sizing:border-box;background:var(--pal-halo);}
  #pal-tr .tr-steps li.walk b{border-style:dotted;border-width:2px;border-color:var(--muted);}
  #pal-tr .tr-steps li.board span,#pal-tr .tr-steps li.alight span{font-weight:700;}
  #pal-tr .tr-steps li small{display:block;color:var(--muted);font-weight:500;}
  #pal-tr .tr-hint{color:var(--muted);font-size:11px;margin-left:auto;}
  #pal-chiprt,#pal-relrt{position:fixed;left:50%;transform:translateX(-50%);bottom:26px;z-index:311;display:none;align-items:center;gap:9px;padding:7px 15px;border-radius:999px;
    font-size:12px;color:var(--text);background:var(--panel-glass-bg, var(--surface));-webkit-backdrop-filter:blur(24px) saturate(185%);backdrop-filter:blur(24px) saturate(185%);
    border:1px solid var(--card-glass-border, var(--border));box-shadow:0 12px 32px var(--node-hover-shadow);max-width:min(640px,calc(100vw - 460px));}
  #pal-chiprt.on,#pal-relrt.on{display:flex;}
  #pal-relrt.above{bottom:70px;}
  /* ride the route a filter draws: a button on the route's pill, a rider on the map */
  .tr-px{cursor:pointer;flex:none;width:22px;height:22px;border-radius:50%;border:0;padding:0;font-size:12px;line-height:22px;color:var(--muted);background:color-mix(in srgb,var(--text) 8%,transparent);}
  .tr-px:hover{color:var(--text);background:color-mix(in srgb,var(--text) 16%,transparent);}
  .tr-md{display:inline-flex;gap:2px;padding:2px;border-radius:999px;background:color-mix(in srgb,var(--text) 8%,transparent);flex:none;}
  .tr-md button{cursor:pointer;border:0;border-radius:999px;padding:3px 9px;font-size:11px;font-weight:700;color:var(--muted);background:transparent;}
  .tr-md button.on{background:var(--surface,#fff);color:var(--text);box-shadow:0 1px 3px rgba(20,26,55,.25);}
  #pal-tr .tr-md{margin:0 0 7px;}
  #pal-chiprt .tr-b,#pal-relrt .tr-b{cursor:pointer;border:1px solid transparent;border-radius:999px;padding:4px 12px;font-weight:700;font-size:12px;background:var(--cc,#888);color:#fff;flex:none;}
  #pal-chiprt .tr-b:hover,#pal-relrt .tr-b:hover{filter:brightness(1.08);}
  html.pal-tripping #pal-chiprt .tr-b,html.pal-tripping #pal-relrt .tr-b{display:none;}
  .pal-svg .pl-rider circle.rd-o{fill:var(--rc,#888);stroke:#fff;stroke-width:3;}
  .pal-svg .pl-rider circle.rd-i{fill:#fff;}
  .pal-svg .pl-rider{pointer-events:none;filter:drop-shadow(0 2px 4px rgba(0,0,0,.35));}
  html.alto-palace #world .node.pal-trip-cur:not(.focused) .node-card{outline:5px solid var(--cc,#888);outline-offset:3px;}
  #pal-chiprt i,#pal-relrt i{width:22px;height:6px;border-radius:3px;flex:none;background:var(--cc,#888);}
  #pal-chiprt small,#pal-relrt small{color:var(--muted);}
  html.mobile #pal-tr,html.detail-open #pal-tr,html.printing #pal-tr,html:not(.alto-palace) #pal-tr,
  html.mobile #pal-chiprt,html.detail-open #pal-chiprt,html.printing #pal-chiprt,html:not(.alto-palace) #pal-chiprt,html.mobile #pal-relrt,html.detail-open #pal-relrt,html.printing #pal-relrt,html:not(.alto-palace) #pal-relrt{display:none !important;}
"""

TRANSIT_JS = r"""
(function(){
if(window._palTr) return;
var E=null, T=null, NS='http://www.w3.org/2000/svg';
var WALK=1, RIDE=.2, BOARD=120, XFER=70, BUSRIDE=.6, BUSBOARD=120;
var S={portal:null, line:null, stop:null, ride:null, trip:null, chipH:null, chipF:null, mode:'transit'};
try{ var m0=localStorage.getItem('alto-palace-mode'); if(m0==='drive'||m0==='walk'||m0==='transit') S.mode=m0; }catch(x){}   /* a line picked; a stop picked; riding {l,i}; the chip pointed at; the chips filtered */
function el(tag,attrs,parent){ var e=document.createElementNS(NS,tag); for(var k in attrs) e.setAttribute(k,attrs[k]); if(parent) parent.appendChild(e); return e; }
function esc(v){ return String(v==null?'':v).replace(/[&<>"]/g,function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
function col(l){ return E.tubeCol(l.c); }
function lineOf(id){ return T&&T.byId[id]; }
function stopsOn(l){ return (l.s||[]).map(function(i){ return T.stops[i]; }); }
/* The stops of a line in the order you meet them riding along its drawn track, so "next stop" is always the
   one ahead in the direction of travel (the stored order could run back and forth along a branched line). */
function orderStops(l){
  if(!l.s || l.s.length<3 || !l.p || !l.p.length) return;
  var polys=l.p.filter(function(a){ return a && a.length>=4; }), lens=polys.map(function(a){ var L=0; for(var k=0;k+3<a.length;k+=2) L+=Math.hypot(a[k+2]-a[k],a[k+3]-a[k+1]); return L; });
  if(!polys.length) return;
  /* each piece runs away from what came before it: a piece's start is its end nearer the earlier pieces
     (pieces that continue one another chain; branches leave the shared trunk) */
  var rev=[];
  polys.forEach(function(a,i){ var r=false;
    if(i>0){ var nearer=function(x,y){ var m=1e18; for(var j=0;j<i;j++){ var q=projSeg(polys[j],x,y); if(q.d<m) m=q.d; } return m; };
      r = nearer(a[a.length-2],a[a.length-1]) < nearer(a[0],a[1]); }
    rev.push(r); });
  var items=l.s.map(function(si,oi){ var st=T.stops[si], best=null, bp=0;
    polys.forEach(function(a,pi){ var q=projSeg(a, st.x, st.y); if(!best || q.d<best.d-6){ best=q; bp=pi; } });   /* a stop on the shared trunk belongs to the first piece */
    var a=polys[bp], pos=0; for(var k=0;k<best.k;k+=2) pos+=Math.hypot(a[k+2]-a[k],a[k+3]-a[k+1]);
    pos+=best.t*Math.hypot(a[best.k+2]-a[best.k],a[best.k+3]-a[best.k+1]);
    if(rev[bp]) pos=lens[bp]-pos;
    return {si:si, oi:oi, key:bp*1e7+pos}; });
  items.sort(function(x,y){ return x.key-y.key; });
  var up=0, dn=0; for(var i=1;i<items.length;i++){ if(items[i].oi>items[i-1].oi) up++; else dn++; }
  if(dn>up) items.reverse();
  l.s=items.map(function(x){ return x.si; });
}
function init(e){ E=e; var t=E.M.transit; T=null;
  if(t && t.lines && t.lines.length){ T={lines:t.lines, stops:t.stops, byId:{}}; t.lines.forEach(function(l){ T.byId[l.id]=l; });
    T.lines.forEach(function(l){ try{ orderStops(l); }catch(x){} }); }
  return !!T; }
/* take the camera onto what is lit: the track of the lines (and stops) and any extra box [x0,y0,x1,y1], fitted in the window */
function fitLines(ids, extra){
  var cv=document.getElementById('canvas'); if(!cv || !T) return;
  var x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
  (ids||[]).forEach(function(id){ var l=lineOf(id); if(!l) return;
    (l.p||[]).forEach(function(a){ for(var k=0;k+1<a.length;k+=2){ x0=Math.min(x0,a[k]); x1=Math.max(x1,a[k]); y0=Math.min(y0,a[k+1]); y1=Math.max(y1,a[k+1]); } }); });
  if(extra){ x0=Math.min(x0,extra[0]); y0=Math.min(y0,extra[1]); x1=Math.max(x1,extra[2]); y1=Math.max(y1,extra[3]); }
  if(x0>x1) return;
  var w=Math.max(x1-x0,300), h=Math.max(y1-y0,300), z=Math.min((cv.clientWidth-160)/w, (cv.clientHeight-240)/h);
  E.flyMap((x0+x1)/2, (y0+y1)/2, Math.max(.05, Math.min(1.3, z)));
}
/* the box of a path's points (map units; routes are M/L only) */
function boxOf(d, b){ b=b||[1e9,1e9,-1e9,-1e9]; var v=(d.match(/-?\d*\.?\d+/g)||[]).map(parseFloat);
  for(var i=0;i+1<v.length;i+=2){ b[0]=Math.min(b[0],v[i]); b[2]=Math.max(b[2],v[i]); b[1]=Math.min(b[1],v[i+1]); b[3]=Math.max(b[3],v[i+1]); } return b; }
function joinBox(a, b){ if(!b || b[0]>b[2]) return a; if(!a) return b.slice(); return [Math.min(a[0],b[0]), Math.min(a[1],b[1]), Math.max(a[2],b[2]), Math.max(a[3],b[3])]; }
function has(){ return !!T; }

/* ── drawing: the lines under the buildings, the stops over them ── */
function lines(svg){
  if(!T) return; var g=el('g',{'class':'pl-transit'},svg);
  T.lines.forEach(function(l){ var c=col(l), cls=l.k==='metro'?'tr-m':l.k==='tram'?'tr-t':l.k==='bus'?'tr-bus':'tr-r';
    var lg=el('g',{'class':'pl-tl','data-l':l.id,'data-k':l.k, style:'--tc:'+c},g);
    l.p.forEach(function(a){ var d=E.rp(a,14); el('path',{'class':'pl-tcase', d:d},lg);
      if(l.k==='rail') el('path',{'class':'pl-ties', d:d, stroke:c},lg);
      E.tube(lg, d, c, 4.6, .96, cls); }); });
}
var RIN=4.6, RHUB=8;
function stations(svg){
  if(!T) return; var stl=el('g',{'class':'pl-stns pl-tstns'},svg); svg._tst=stl;
  T.stops.forEach(function(s,i){ var ls=s.l.map(lineOf).filter(Boolean), busy=ls.length>0 && ls.every(function(l){ return l.k==='bus'; }), hub=ls.length>1 && !busy, c0=ls.length?col(ls[0]):E.NEUTRAL();
    var maj=ls.some(function(l){ return l.k==='rail'; }) && /station|terminal|center|centre/i.test(s.n||'');     /* a mainline station: seen at every zoom */
    var g=E.pin(stl, 'pl-stn tr-stn'+(hub?' hub':'')+(maj?' maj':'')+(busy?' bus':''), s.x, s.y, {'data-s':i, style:'--tc:'+c0});
    var d=el('g',{'class':'tr-dot'},g);
    if(hub){ el('circle',{'class':'tr-ring hubr', r:RHUB, stroke:E.NEUTRAL()},d);
      ls.forEach(function(l,k){ var a0=k/ls.length*Math.PI*2-Math.PI/2, a1=(k+1)/ls.length*Math.PI*2-Math.PI/2-.12, r=RHUB;
        el('path',{'class':'tr-arc', d:'M'+(r*Math.cos(a0)).toFixed(2)+' '+(r*Math.sin(a0)).toFixed(2)+'A'+r+' '+r+' 0 '+((a1-a0)>Math.PI?1:0)+' 1 '+(r*Math.cos(a1)).toFixed(2)+' '+(r*Math.sin(a1)).toFixed(2), stroke:col(l)},d); });
      el('circle',{'class':'tr-sh', r:RHUB},d); }
    else { el('circle',{'class':'tr-ring', r:RIN, stroke:c0},d); el('circle',{'class':'tr-sh', r:RIN},d); }
    el('circle',{'class':'tr-pulse', r:8},g);
    E.stLbl(stl, 'pl-stt tr-lbl'+(hub?' hub':'')+(maj?' maj':'')+(busy?' bus':''), s.n, s.x, s.y, hub||maj).setAttribute('data-s', i); });
}
/* A portal stands ON the station's building when the station is a landmark (30th Street, Suburban, Jefferson: a badge over its roof,
   drawn above every building), else at the station's stop. One portal per station, however many stops carry its name. */
function portals(svg){
  if(!T || !(E.P.po||[]).length) return; var pg=el('g',{'class':'pl-portals'},svg); svg._pt=pg;
  var lms=[].filter.call(svg.querySelectorAll('.pl-lmb'), function(g){ return g._lm; });
  (E.P.po||[]).forEach(function(po,pi){ var done={};
    portalStops(po).forEach(function(i){ var s=T.stops[i], k=pnk(s.n), best=null, bd=1200;
      lms.forEach(function(g){ var L=g._lm, nk=pnk(L.name); if(!nk || !k || !(nk.indexOf(k)>=0 || k.indexOf(nk)>=0)) return;
        var d=Math.hypot(L.x+L.w/2-s.x, L.y+L.h/2-s.y); if(d<bd){ bd=d; best=L; } });
      var key=best?'b:'+best.name:'s:'+i; if(done[key]) return; done[key]=1;
      var x=s.x, y=s.y, g;
      if(best){ x=best.x+best.w/2; y=best.y+best.h*.4; g=E.pin(pg,'pl-portal on-bldg',x,y,{'data-po':pi,'data-s':i});
        el('circle',{cx:0,cy:0,r:12},g); el('text',{x:0,y:0},g).textContent='\u2708'; }
      else { g=E.pin(pg,'pl-portal',x,y,{'data-po':pi,'data-s':i}); el('line',{x1:0,y1:-6,x2:-13,y2:-17},g);       /* up and to the left: the station's name reads to the right */
        el('circle',{cx:-16,cy:-20,r:11},g); el('text',{x:-16,y:-20},g).textContent='\u2708'; }
      var t=el('title',{},g); t.textContent='Go to '+po.name+(best?' \u00b7 from '+best.name:'');
      g.parentNode.setAttribute('data-x', x); g.parentNode.setAttribute('data-y', y);                       /* each portal goes from where it stands */
      if(!po._at) po._at={x:x, y:y}; }); });
}
/* the stops a portal opens from: named stations (on its line, when it names one) */
function pnk(n){ return String(n||'').toLowerCase().replace(/philadelphia|station|street|\bst\b/g,'').replace(/[^a-z0-9]/g,''); }
function portalStops(po){ var want=(po.stations||[]).map(pnk).filter(Boolean), out=[];
  T.stops.forEach(function(s,i){ var k=pnk(s.n); if(!k) return;
    if(po.line && !s.l.some(function(id){ var l=lineOf(id); return l && String(l.n).toLowerCase().indexOf(String(po.line).toLowerCase())>=0; })) return;
    if(want.some(function(w){ return k===w || k.indexOf(w)>=0 || w.indexOf(k)>=0; })) out.push(i); });
  return out; }
/* the chip route sits above the street hits and below the stops */
function hits(svg){
  if(!T || svg._sid!=='d') return; var h=el('g',{'class':'pl-tr-hits'},svg);
  T.lines.forEach(function(l){ l.p.forEach(function(a){ var p=el('path',{'class':'pl-tl-hit', d:E.pts(a),'data-l':l.id},h); }); });
  T.stops.forEach(function(s,i){ el('circle',{r:12}, E.pin(h, 'pl-stn-hit', s.x, s.y, {'data-s':i})); });
  var fx=E.fx&&E.fx(), cr=el('g',{'class':'pl-chiprt'},fx||svg); svg._cr=cr; if(!fx) svg.insertBefore(cr, svg._tst||null);   /* (its dashes flow: #pal-fx, palace.py) */
  svg.classList.toggle('tr-focus', false); paint();
}

/* ── lit lines and stops ── */
function lit(){
  var svg=E.svg(); if(!svg || !T) return;
  var l=S.ride?S.ride.l:S.line, s=S.stop, ids={}, cur=S.ride?stopsOn(lineOf(S.ride.l))[S.ride.i]:null, curI=cur?T.stops.indexOf(cur):-1;
  if(l) T.stops.forEach(function(st,i){ if(st.l.indexOf(l)>=0) ids[i]=1; });
  if(s!=null){ ids[s]=1; }
  var focus=!!(l||s!=null);
  svg.classList.toggle('tr-focus', focus); document.documentElement.classList.toggle('tr-solo', focus);
  svg.querySelectorAll('.pl-tl').forEach(function(g){ var on=g.getAttribute('data-l')===l || (s!=null && T.stops[s].l.indexOf(g.getAttribute('data-l'))>=0); g.classList.toggle('hot', !!on); });
  svg.querySelectorAll('.tr-stn,.tr-lbl').forEach(function(g){ var i=+g.getAttribute('data-s'); g.classList.toggle('lit', !!ids[i]); g.classList.toggle('cur', i===curI || (!S.ride && i===s)); });
}
function tipAt(txt, elm){ if(window._palHover) window._palHover(txt ? elm : null, txt||''); }   /* labelled in place (palace.py _palHover), never a box following the cursor */
function stopTip(i){ var s=T.stops[i], ls=s.l.map(lineOf).filter(Boolean); return s.n+(ls.length?' · '+ls.map(function(l){ return l.n; }).join(' · '):''); }
function lineTip(l){ return l.n+' · '+l.s.length+' stops'; }

/* ── the panel ── */
function panel(){ var p=document.getElementById('pal-tr'); if(!p){ p=document.createElement('div'); p.id='pal-tr'; document.body.appendChild(p);
  p.addEventListener('click', function(e){ var b=e.target.closest('[data-a]'); if(!b) return; var a=b.getAttribute('data-a'), v=b.getAttribute('data-v');
    if(a==='x') clear(); else if(a==='tnext') tripStep(1); else if(a==='tprev') tripStep(-1); else if(a==='tauto') tripAuto(); else if(a==='ride') ride(v, +b.getAttribute('data-i')||0); else if(a==='next') step(1); else if(a==='prev') step(-1); else if(a==='portal'){ takePortal(+v); } else if(a==='pstop') pickStop(+b.getAttribute('data-s'), true);
    else if(a==='stop') { var l=lineOf(v||S.line); if(S.ride){ ride(S.ride.l, +b.getAttribute('data-i')); } else if(l) pickStop(+b.getAttribute('data-s'), true); }
    else if(a==='line') pickLine(v, true); }); }
  return p; }
function paintPortal(p){ var po=(E.P.po||[])[S.portal]; if(!po) return false; var sts=portalStops(po);
  p.style.setProperty('--tc','var(--accent,#6d5bd0)');
  p.innerHTML='<div class="tr-h"><span class="tr-sw" style="background:var(--accent,#6d5bd0)"></span>\u2708 '+esc(po.name)+'<span class="tr-x" data-a="x" role="button" aria-label="Close">\u2715</span></div>'
    +'<div class="tr-sub">A portal \u00b7 this place is off the map'+(po.via?' \u00b7 reached by '+esc(po.via):'')+'</div>'
    +'<div class="tr-sub" style="margin:0 0 4px">Reached from</div><div class="tr-stops">'+sts.map(function(i){ return '<div class="tr-st" data-a="pstop" data-s="'+i+'"><i></i>'+esc(T.stops[i].n)+'</div>'; }).join('')+'</div>';
  p.classList.add('on'); return true; }
function paint(){
  var p=panel(); lit(); if(S.trip) paintUsed();
  if(S.trip){ paintTrip(p); return; }
  if(S.portal!=null && !S.ride && !S.line && S.stop==null && paintPortal(p)) return;
  if(S.ride){ var l=lineOf(S.ride.l), ss=stopsOn(l), s=ss[S.ride.i], c=col(l), si=T.stops.indexOf(s);
    var others=s.l.filter(function(q){ return q!==l.id; }).map(lineOf).filter(Boolean);
    p.style.setProperty('--tc', c);
    p.innerHTML='<div class="tr-h"><span class="tr-sw" style="background:'+c+'"></span>'+esc(l.n)+'<span class="tr-x" data-a="x" role="button" aria-label="Close">✕</span></div>'
      +'<div class="tr-sub">Riding · stop '+(S.ride.i+1)+' of '+ss.length+'</div>'
      +'<div style="font-size:15px;font-weight:800;margin-bottom:3px">'+esc(s.n)+'</div>'
      +(others.length?'<div class="tr-sub" style="margin:0 0 4px">Change here for</div><div class="tr-chips">'+others.map(function(o){ return '<span class="tr-chip" data-a="line" data-v="'+o.id+'" style="--tc:'+col(o)+'"><b></b>'+esc(o.n)+'</span>'; }).join('')+'</div>':'<div style="height:6px"></div>')
      +'<div class="tr-btns"><button class="tr-b" data-a="prev" '+(S.ride.i<=0?'disabled':'')+'>◀ '+(ss[S.ride.i-1]?esc(ss[S.ride.i-1].n):'')+'</button><button class="tr-b go" data-a="next" '+(S.ride.i>=ss.length-1?'disabled':'')+'>'+(ss[S.ride.i+1]?esc(ss[S.ride.i+1].n):'End')+' ▶</button></div>'
      +(window._palRide?window._palRide.switchHtml():'')+'<div class="tr-sub" style="margin:7px 0 0">← → or ↑ ↓ step along · '+(window._palRide?'V first-person rides on / off · ':'')+'Esc to get off</div>';
    p.classList.add('on'); return; }
  if(S.line){ var L=lineOf(S.line), c2=col(L), ss2=stopsOn(L); p.style.setProperty('--tc', c2);
    p.innerHTML='<div class="tr-h"><span class="tr-sw" style="background:'+c2+'"></span>'+esc(L.n)+'<span class="tr-x" data-a="x" role="button" aria-label="Close">✕</span></div>'
      +'<div class="tr-sub">'+ss2.length+' stops in the city · '+(L.k==='metro'?'subway':L.k==='tram'?'subway-surface trolley':L.k==='bus'?'bus route':'regional rail')+'</div>'
      +'<div class="tr-stops">'+ss2.map(function(s,i){ var si=T.stops.indexOf(s); return '<div class="tr-st'+(S.stop===si?' cur':'')+'" data-a="stop" data-v="'+L.id+'" data-s="'+si+'" data-i="'+i+'"><i></i>'+esc(s.n)+'</div>'; }).join('')+'</div>'
      +'<div class="tr-btns"><button class="tr-b go" data-a="ride" data-v="'+L.id+'" data-i="'+Math.max(0,S.stop!=null?(L.s.indexOf(S.stop)):0)+'">Ride this line ▶</button></div>';
    p.classList.add('on'); return; }
  if(S.stop!=null){ var s3=T.stops[S.stop], ls=s3.l.map(lineOf).filter(Boolean); p.style.setProperty('--tc', ls.length?col(ls[0]):'#888');
    p.innerHTML='<div class="tr-h">'+esc(s3.n)+'<span class="tr-x" data-a="x" role="button" aria-label="Close">✕</span></div>'
      +'<div class="tr-sub">'+(ls.length>1?'Transfer between '+ls.length+' lines':'A stop on one line')+'</div>'
      +'<div class="tr-chips">'+ls.map(function(o){ return '<span class="tr-chip" data-a="ride" data-v="'+o.id+'" data-i="'+Math.max(0,o.s.indexOf(S.stop))+'" style="--tc:'+col(o)+'"><b></b>'+esc(o.n)+' ▶</span>'; }).join('')+'</div>'
      +(portalsAt(S.stop).map(function(pi){ return '<div class="tr-chips"><span class="tr-chip" data-a="portal" data-v="'+pi+'" style="--tc:var(--accent,#6d5bd0)"><b></b>\u2708 Portal: '+esc(E.P.po[pi].name)+' \u203a</span></div>'; }).join(''))
      +'<div class="tr-sub" style="margin:0">Pick a line to ride from here.</div>';
    p.classList.add('on'); return; }
  p.classList.remove('on');
}
function clear(){ endTrip(); S.portal=null; S.line=null; S.stop=null; S.ride=null; paint(); }
/* a portal is taken: the trip to the place it names (palace_airport.py) */
function takePortal(pi, pin){ endTrip(); var po=(E.P.po||[])[pi]; if(!po) return; var g=pin;
  if(!g){ var all=[].slice.call(document.querySelectorAll('#palace-svg .pl-portal[data-po="'+pi+'"]')), cs=S.stop!=null&&T?T.stops[S.stop]:null, bd=1e18;   /* from a stop's panel: the portal at that stop */
    all.forEach(function(q){ var d=cs?Math.hypot(+q.getAttribute('data-x')-cs.x, +q.getAttribute('data-y')-cs.y):0; if(d<bd){ bd=d; g=q; } }); }
  var at=g&&g.getAttribute&&g.getAttribute('data-x')!=null?{x:+g.getAttribute('data-x'), y:+g.getAttribute('data-y')}:null;
  if(window._palAirport) window._palAirport.go(po, g, at); else { S.portal=pi; S.ride=null; S.line=null; S.stop=null; paint(); } }
function portalsAt(i){ var o=[]; (E.P.po||[]).forEach(function(po,pi){ if(portalStops(po).indexOf(i)>=0) o.push(pi); }); return o; }
function pickLine(id, fly){ endTrip(); S.portal=null; S.ride=null; S.line=id; S.stop=null; paint(); fitLines([id]); }
function pickStop(i, fly){ endTrip(); S.portal=null; S.stop=i; if(!S.line && !S.ride){ /* a stop alone */ } S.ride=null; if(fly) glide(i); paint(); }
function glide(i){ var s=T.stops[i]; if(s) E.flyMap(s.x, s.y, Math.max(E.Z(), 1.0)); }
function ride(id, i){ var rr=window._palRide, was=rr&&rr.active(); if(rr&&!was) rr.mark(); endTrip(); var l=lineOf(id); if(!l || !l.s.length) return; i=Math.max(0, Math.min(l.s.length-1, i|0)); S.ride={l:id, i:i}; S.line=id; S.stop=l.s[i];
  if(rr && rr.lineEnter(id, i)) { paint(); return; }   /* first-person: the platform at this stop (palace_ride.py) */
  glide(l.s[i]); paint(); }
/* an arrow key goes where it points: with the next stop to the left of you, Left is "next" (the direction of travel) */
function arrowDir(k, d){
  var l=lineOf(S.ride.l), i=S.ride.i, cur=T.stops[l.s[i]], nx=T.stops[l.s[i+1]], pv=T.stops[l.s[i-1]];
  var horiz=(k==='ArrowLeft'||k==='ArrowRight'), sg=(k==='ArrowRight'||k==='ArrowDown')?1:-1;
  function comp(s){ return s ? (horiz ? s.x-cur.x : s.y-cur.y) : 0; }
  var cn=comp(nx), cp=comp(pv);
  if(nx && pv){ return (cn*sg >= cp*sg) ? 1 : -1; }          /* both ways open: the one the key points toward */
  if(nx) return (cn*sg > 0 || Math.abs(cn)<20) ? 1 : (sg*cn<0 ? 0 : 1);
  if(pv) return (cp*sg > 0 || Math.abs(cp)<20) ? -1 : 0;
  return d; }
function step(d){ if(!S.ride || !d) return; var l=lineOf(S.ride.l), i=S.ride.i+d; if(i<0||i>=l.s.length) return;
  if(window._palRide && window._palRide.active() && !S.ride.busy){ var i0=S.ride.i; S.ride.busy=true; if(window._palRide.lineStep(S.ride.l, i0, i, function(){ if(!S.ride) return; S.ride.busy=false; S.ride.i=i; S.stop=l.s[i]; paint(); })) return; S.ride.busy=false; }   /* first-person */
  if(S.ride.busy) return; ride(S.ride.l, i); }

/* ── the key: the lines and what a dot means ── */
function keyHtml(sw){ if(!T) return '';
  var h='', nb=0; T.lines.forEach(function(l){ if(l.k==='bus'){ nb++; return; } var c=col(l), w=l.k==='metro'?5:l.k==='tram'?3.4:4.2;
    h+='<div class="pk-row" data-tl="'+l.id+'" style="cursor:pointer">'+sw((l.k==='rail'?'<line x1="1" y1="6" x2="25" y2="6" stroke="'+c+'" stroke-width="7" stroke-dasharray="1.4 4.6" opacity=".7"/>':'')+'<line x1="1" y1="6" x2="25" y2="6" stroke="'+c+'" stroke-width="'+w+'" stroke-linecap="round"/>')
      +'<div>'+esc(l.n)+' <small>'+l.s.length+' stops · click to open and ride it</small></div></div>'; });
  if(nb) h+='<div class="pk-row">'+sw('<line x1="1" y1="6" x2="25" y2="6" stroke="#3f7f9b" stroke-width="2.8" stroke-linecap="round"/><circle cx="8" cy="6" r="2.2" fill="#fff" stroke="#3f7f9b"/><circle cx="18" cy="6" r="2.2" fill="#fff" stroke="#3f7f9b"/>')+'<div>Buses <small>'+nb+' main routes along the streets \u2014 stops show as you zoom in; part of every transit route here</small></div></div>';
  h+='<div class="pk-row">'+sw('<circle cx="13" cy="6" r="4.2" fill="#fff" stroke="#0097d6" stroke-width="2.6"/>')+'<div>Stop <small>a station on a line, in its colour — named as you zoom in; click one to fly there</small></div></div>';
  h+='<div class="pk-row">'+sw('<circle cx="13" cy="6" r="5.2" fill="#fff" stroke="#59616c" stroke-width="1"/><path d="M13 .8A5.2 5.2 0 0 1 18 8" fill="none" stroke="#0097d6" stroke-width="2.8"/><path d="M18 8A5.2 5.2 0 0 1 8 8.4" fill="none" stroke="#6ea516" stroke-width="2.8"/><path d="M8 8.4A5.2 5.2 0 0 1 13 .8" fill="none" stroke="#f58220" stroke-width="2.8"/>')+'<div>Interchange <small>a ringed stop where lines meet — change here</small></div></div>';
  h+='<div class="pk-row">'+sw('<line x1="1" y1="6" x2="25" y2="6" stroke="#8a6bd8" stroke-width="5" stroke-linecap="round" opacity=".9"/><line x1="1" y1="6" x2="25" y2="6" stroke="#fff" stroke-width="1.6" stroke-dasharray="1 7" stroke-linecap="round"/>')+'<div>Tour <small>point at an Element chip in the top bar (or switch it on in Filter): every building it tags lights up and one route links them, riding the lines where that is quicker</small></div></div>';
  return h; }

/* ── a street graph with the transit in it: walking costs its length, riding a fifth of it, boarding a little more ── */
var GG=null;
function projSeg(a, x, y){ var best=null, bd=1e18;
  for(var k=0;k+3<a.length;k+=2){ var ax=a[k], ay=a[k+1], bx=a[k+2], by=a[k+3], dx=bx-ax, dy=by-ay, L2=dx*dx+dy*dy||1e-9, t=Math.max(0,Math.min(1,((x-ax)*dx+(y-ay)*dy)/L2)), px=ax+t*dx, py=ay+t*dy, d=Math.hypot(px-x,py-y);
    if(d<bd){ bd=d; best={k:k, t:t, x:px, y:py, d:d}; } }
  return best; }
function bigG(){
  if(GG) return GG; var g=E.graph(), N=g.X.length, X=g.X.slice(), Y=g.Y.slice(), adj=g.adj.map(function(a){ return a.map(function(e){ return [e[0], e[1]*WALK, null]; }); }), lid=[];
  for(var i=0;i<N;i++) lid.push(null);
  function add(a,b,c,l){ adj[a].push([b,c,l]); adj[b].push([a,c,l]); }
  var at={};                                                /* stop index -> [{line, node}] */
  T.lines.forEach(function(l){
    var polys=l.p.map(function(a){ return a.slice(); }), ins=polys.map(function(){ return {}; });
    T.stops.forEach(function(s,si){ if(s.l.indexOf(l.id)<0) return; var best=null, bp=-1;
      polys.forEach(function(a,pi){ var r=projSeg(a, s.x, s.y); if(r && (!best || r.d<best.d)){ best=r; bp=pi; } });
      if(best && best.d<260){ (ins[bp][best.k]=ins[bp][best.k]||[]).push({t:best.t,x:best.x,y:best.y,si:si}); } });
    var key={};
    function node(x,y){ var k=Math.round(x)+','+Math.round(y); if(key[k]==null){ key[k]=X.length; X.push(x); Y.push(y); adj.push([]); lid.push(l.id); } return key[k]; }
    polys.forEach(function(a,pi){ var prev=null;
      for(var k=0;k+1<a.length;k+=2){ var n=node(a[k],a[k+1]);
        if(prev!=null && prev!==n){ var L=Math.hypot(X[n]-X[prev],Y[n]-Y[prev]); add(prev,n,L*(l.k==='bus'?BUSRIDE:RIDE),l.id); } prev=n;
        var list=(ins[pi][k]||[]).sort(function(p,q){ return p.t-q.t; });
        if(k+3<a.length) list.forEach(function(q){ var m=node(q.x,q.y); if(prev!==m){ var L2=Math.hypot(X[m]-X[prev],Y[m]-Y[prev]); add(prev,m,L2*(l.k==='bus'?BUSRIDE:RIDE),l.id); prev=m; } (at[q.si]=at[q.si]||[]).push({l:l.id,n:m}); }); } });
  });
  /* the stops: a walk to the nearest street, a change between the lines that meet there */
  Object.keys(at).forEach(function(si){ var s=T.stops[si], st=E.nearest(s.x,s.y,1,600);
    at[si].forEach(function(q){ if(st>=0){ var d=Math.hypot(X[st]-X[q.n],Y[st]-Y[q.n]), ql=T.byId[q.l]; add(st,q.n,d*WALK+(ql&&ql.k==='bus'?BUSBOARD:BOARD),null); } });
    for(var a=0;a<at[si].length;a++) for(var b=a+1;b<at[si].length;b++) add(at[si][a].n, at[si][b].n, XFER, null); });
  GG={X:X,Y:Y,adj:adj,lid:lid,N:N,at:at}; return GG;
}
function dijk(a,b){
  var g=bigG(); if(a<0||b<0) return null; if(a===b) return [a];
  var dist={}, prev={}, H=[[0,a]]; dist[a]=0;
  function push(it){ H.push(it); var i=H.length-1; while(i>0){ var p=(i-1)>>1; if(H[p][0]<=H[i][0]) break; var t=H[p]; H[p]=H[i]; H[i]=t; i=p; } }
  function pop(){ var top=H[0], last=H.pop(); if(H.length){ H[0]=last; var i=0; for(;;){ var l=2*i+1, r=l+1, m=i;
    if(l<H.length&&H[l][0]<H[m][0]) m=l; if(r<H.length&&H[r][0]<H[m][0]) m=r; if(m===i) break; var t=H[m]; H[m]=H[i]; H[i]=t; i=m; } } return top; }
  while(H.length){ var it=pop(), d=it[0], u=it[1]; if(d>dist[u]) continue; if(u===b) break;
    g.adj[u].forEach(function(e){ var nd=d+e[1]; if(dist[e[0]]==null || nd<dist[e[0]]){ dist[e[0]]=nd; prev[e[0]]=u; push([nd,e[0]]); } }); }
  if(dist[b]==null) return null;
  var out=[b]; while(out[out.length-1]!==a) out.push(prev[out[out.length-1]]); return out.reverse();
}

/* ── the chip route: every building a chip tags, one tour ── */
var chipFn=null;
function chipNodes(id){ var o=null, m=window.FILTER_NODES||{}; Object.keys(m).forEach(function(k){ if(m[k] && m[k][id]) o=m[k][id]; }); return o; }
function chipColor(id){ var c=null; (window.FILTER_SECTIONS||[]).forEach(function(s){ (s.items||[]).forEach(function(it){ if(it.id===id) c=it.color; }); }); return c; }
function chipName(id){ var c=null; (window.FILTER_SECTIONS||[]).forEach(function(s){ (s.items||[]).forEach(function(it){ if(it.id===id) c=it.name; }); }); return c; }
function wanted(){                      /* what to light now: the chip pointed at, else what the filters are showing */
  if(S.chipH && !S.trip){ var ids=chipNodes(S.chipH)||[]; return {ids:ids, color:chipColor(S.chipH), name:chipName(S.chipH)}; }
  if(S.chipF && S.chipF.ids.length) return S.chipF;
  return null; }
function holds(){ return !!(S.chipH || (S.chipF && S.chipF.ids.length)); }
function tour(bs){
  var ord=E.order(), ix={}; ord.forEach(function(id,i){ ix[id]=i; });
  bs=bs.slice().sort(function(a,b){ return ix[a]-ix[b]; });
  var out=[bs.shift()], P=E.P;
  while(bs.length){ var cur=E.lot(P.at[out[out.length-1]]), bi=0, bd=1e18;
    bs.forEach(function(b,i){ var L=E.lot(P.at[b]); if(!L||!cur) return; var d=Math.hypot(L[0]-cur[0],L[1]-cur[1]); if(d<bd){ bd=d; bi=i; } });
    out.push(bs.splice(bi,1)[0]); }
  return out;
}
function renderChip(){
  var svg=E.svg(); if(!svg) return; var P=E.P, cr=svg._cr; if(cr) cr.innerHTML='';
  var pill=document.getElementById('pal-chiprt'); if(!pill){ pill=document.createElement('div'); pill.id='pal-chiprt'; document.body.appendChild(pill); }
  var nodes=[].slice.call(document.querySelectorAll('#world .node'));
  var w=wanted();
  if(!w || !E.palaceOn()){ nodes.forEach(function(n){ n.classList.remove('pal-chip-hot'); if(n._chipDim){ n.classList.remove('pal-dim'); n._chipDim=0; } if(n._chipHot){ n.classList.remove('pal-hot'); n._chipHot=0; } });
    if(pill) pill.classList.remove('on'); S.uT={}; paintUsed(); renderRel(); return; }
  var bset={}; (w.ids||[]).forEach(function(id){ var b=E.bOf(id); if(E.isB(b)) bset[b]=1; });
  var bs=Object.keys(bset).filter(function(b){ return E.lot(P.at[b]); });
  nodes.forEach(function(n){ var id=n.id.slice(5), on=!!bset[E.bOf(id)]; n.classList.remove('pal-hot','pal-dim'); n.classList.toggle('pal-chip-hot', on); n.classList.toggle('pal-hot', on); n.classList.toggle('pal-dim', !on);
    n._chipDim=on?0:1; n._chipHot=on?1:0; n.style.setProperty('--cc', w.color||'var(--accent)'); });
  var c=(w.color&&w.color.indexOf('var(')<0)?E.tubeCol(w.color):(w.color||'var(--accent)');
  var used={}, d='', n=bs.length, legs=[]; S.cbox=null; S.tourLegs=[]; S.tourCol=c; S.tourName=w.name||'Filter';
  bs.forEach(function(b){ var L=E.lot(P.at[b]); if(L){ var r=Math.max(L[2],L[3]); S.cbox=joinBox(S.cbox,[L[0]-r,L[1]-r,L[0]+r,L[1]+r]); } });
  if(cr && T && n>1){ var order=tour(bs), pathPts=[], g=bigG();
    var A0=E.lot(P.at[order[0]]); d='M'+A0[0]+' '+A0[1]; legs=[];
    for(var i=0;i+1<order.length;i++){ var A=E.lot(P.at[order[i]]), B=E.lot(P.at[order[i+1]]), rt=legRoute(order[i], order[i+1]), tail='', lu={};
      if(rt){ tail=rt.d.slice(rt.d.indexOf('L')); rt.lines.forEach(function(k){ used[k]=1; lu[k]=1; }); }
      else { var r=dijk(E.entrance(order[i]), E.entrance(order[i+1])); tail='';
        if(r) r.forEach(function(q,k){ tail+='L'+g.X[q]+' '+g.Y[q]; if(k>0 && g.lid[q] && g.lid[q]===g.lid[r[k-1]]){ used[g.lid[q]]=1; lu[g.lid[q]]=1; } });
        tail+='L'+B[0]+' '+B[1]; }
      d+=tail; legs.push({a:order[i], b:order[i+1], d:'M'+A[0]+' '+A[1]+tail, lines:Object.keys(lu), color:c, opt:rt&&rt.opt}); }
    S.cbox=joinBox(S.cbox, boxOf(d)); S.tourLegs=legs;
    el('path',{'class':'pl-crt case', d:d},cr); el('path',{'class':'pl-crt base', d:d, stroke:c},cr); el('path',{'class':'pl-crt sh', d:d},cr); el('path',{'class':'pl-crt tk', d:d},cr); }
  if(pill){ var ul=Object.keys(used).map(lineOf).filter(Boolean);
    pill.style.setProperty('--cc', c); pill.innerHTML='<i></i><span><b>'+esc(w.name||'Filter')+'</b> · '+n+' building'+(n===1?'':'s')+(ul.length?' · rides '+ul.map(function(l){ return esc(l.n); }).join(', '):'')+'</span>'
    +(!S.chipH && S.tourLegs.length?modeHtml()+'<button class="tr-b" type="button" data-trip="chip">'+(S.mode==='drive'?'Drive':S.mode==='walk'?'Walk':'Ride')+' this route \u25b6</button>'+(window._palRide&&window._palRide.ui?window._palRide.ui.pillHtml():''):'')
    +(!S.chipH?'<button class="tr-px" type="button" data-pillx="1" aria-label="Clear the filter" title="Clear the filter">\u2715</button>':''); pill.classList.add('on'); }
  S.uT=used; paintUsed();
}
function chipRefresh(){
  var on=window._altoChipOn&&window._altoChipOn(), sel=window._altoChipSel?window._altoChipSel():null, ids=[], color=null, name=null;
  if(on && sel){ var first=null; Object.keys(sel).forEach(function(k){ sel[k].forEach(function(v){ if(!first){ first=v; } }); });
    (E.order()||[]).forEach(function(id){ if(window._altoChipKeep(id)) ids.push(id); });
    var names=[]; Object.keys(sel).forEach(function(k){ sel[k].forEach(function(v){ names.push(chipName(v)||v); }); });
    color=first?chipColor(first):null; name=names.join(' + '); }
  S.chipF=ids.length?{ids:ids, color:color, name:name}:null;
  renderChip();
}

/* ── routes that ride the transit: one building to another (the hover routes, the Lines filters) ── */
/* a filter's leg building to building, by the way the person chose (transit, driving, walking): its drawn path is the plan's own real path (the
   track of the line it rides, the highway, the streets), its steps the plan's */
var MODES=[['transit','Transit'],['drive','Drive'],['walk','Walk']];
function legRoute(a,b){
  var A=E.lot(E.P.at[a]), B=E.lot(E.P.at[b]); if(!A||!B) return null; var o=null;
  try{ o=window._palDir&&window._palDir.legPlan?window._palDir.legPlan(a, b, S.mode):null; }catch(x){}
  if(!o || !o.legs.length) return null;
  var d='M'+A[0]+' '+A[1], lu={}; o.legs.forEach(function(l){ l.pts.forEach(function(q){ d+='L'+q[0]+' '+q[1]; }); if(l.k==='ride' && l.l && T && T.byId[l.l]) lu[l.l]=1; });
  return {d:d+'L'+B[0]+' '+B[1], lines:Object.keys(lu), opt:o}; }
function modeHtml(){ return '<span class="tr-md" role="group" aria-label="How to get around">'+MODES.map(function(m){ return '<button type="button" data-mode="'+m[0]+'" class="'+(S.mode===m[0]?'on':'')+'">'+m[1]+'</button>'; }).join('')+'</span>'; }
function setMode(m){ if(S.mode===m) return; S.mode=m; try{ localStorage.setItem('alto-palace-mode', m); }catch(x){} endTrip(); renderChip(); renderRel(); paint(); }
function routeD(a,b,used){
  var P=E.P, A=E.lot(P.at[a]), B=E.lot(P.at[b]); if(!A||!B) return null;
  var g=bigG(), r=dijk(E.entrance(a), E.entrance(b)); if(!r) return null;
  var d='M'+A[0]+' '+A[1];
  r.forEach(function(q,k){ d+='L'+g.X[q]+' '+g.Y[q]; if(used && k>0 && g.lid[q] && g.lid[q]===g.lid[r[k-1]]) used[g.lid[q]]=1; });
  return d+'L'+B[0]+' '+B[1]; }
window._palTR=function(a,b){ return (E && T) ? routeD(a,b) : null; };
/* the routing graph for Directions (palace_directions.py): the walk/ride/board costs above, its stops and lines */
window._palTRx={graph:function(){ return (E&&T)?bigG():null; }, dijk:dijk, stops:function(){ return T?T.stops:[]; }, lines:function(){ return T?T.lines:[]; }, lineOf:lineOf, col:function(l){ return col(l); }, has:has};
/* the lines a tour or a relation filter rides stay lit; the rest of the network fades */
function paintUsed(){
  var svg=E.svg(); if(!svg || !T) return; var u={}, k;
  for(k in (S.uT||{})) u[k]=1; for(k in (S.uR||{})) u[k]=1;
  if(!Object.keys(u).length){ S.fitSig=''; lit(); return; }
  if(S.line || S.stop!=null || S.ride) return;
  svg.classList.toggle('tr-focus', true); document.documentElement.classList.add('tr-solo');
  S.fitSig=Object.keys(u).sort().join('|');
  svg.querySelectorAll('.pl-tl').forEach(function(g){ g.classList.toggle('hot', !!u[g.getAttribute('data-l')]); });
  svg.querySelectorAll('.tr-stn,.tr-lbl').forEach(function(g){ var i=+g.getAttribute('data-s'); var on=T.stops[i].l.some(function(l){ return u[l]; }); g.classList.toggle('lit', on); });
}
/* the Lines filters (Connects, Overrules …): every relation of a picked kind drawn at once, in its colour, on the transit */
function relKeys(){ var k=[]; document.querySelectorAll('.line-key-btn[data-rel-key].active').forEach(function(b){ k.push(b.getAttribute('data-rel-key')); }); return k; }
function renderRel(){
  var svg=E.svg(); if(!svg || !T) return; var P=E.P, rr=svg._rr;
  if(!rr || rr.parentNode!==svg){ rr=svg._rr=el('g',{'class':'pl-relrt'},svg); svg.insertBefore(rr, svg._tst||null); }
  rr.innerHTML=''; S.uR={}; S.rbox=null; S.relLegs=[];
  var pill=document.getElementById('pal-relrt'), keys=relKeys();
  if(!keys.length || !E.palaceOn() || typeof CONNECTIONS==='undefined'){ if(pill) pill.classList.remove('on');
    if(!holds()) document.querySelectorAll('#world .node').forEach(function(nd){ if(nd._relMark){ nd._relMark=0; nd.classList.remove('pal-hot','pal-dim'); } });
    paintUsed(); return; }
  var seen={}, ends={}, n=0, rl=(typeof REL_LABELS!=='undefined')?REL_LABELS:{};
  CONNECTIONS.forEach(function(c){ if(keys.indexOf(c[2])<0) return; var a=E.bOf(c[0]), b=E.bOf(c[1]); if(a===b || !E.isB(a) || !E.isB(b)) return;
    var id=(a<b?a+'|'+b:b+'|'+a)+'|'+c[2]; if(seen[id]) return; seen[id]=1;
    var lu={}, rt=legRoute(a,b), d=rt?rt.d:routeD(a,b,lu); if(!d) return; if(rt) rt.lines.forEach(function(k){ lu[k]=1; }); Object.keys(lu).forEach(function(k){ S.uR[k]=1; }); S.rbox=joinBox(S.rbox, boxOf(d)); var col=(typeof COLOR_MAP!=='undefined'&&COLOR_MAP[c[2]])||'var(--accent)';
    S.relLegs.push({a:a, b:b, d:d, opt:rt&&rt.opt, lines:Object.keys(lu), color:(col.indexOf('var(')<0?E.tubeCol(col):col), label:rl[c[2]]||c[2]});
    el('path',{'class':'pl-crt case', d:d},rr); el('path',{'class':'pl-crt base', d:d, stroke:col},rr); el('path',{'class':'pl-crt tk', d:d},rr); ends[a]=1; ends[b]=1; n++; });
  if(!holds()){ document.querySelectorAll('#world .node').forEach(function(nd){ var on=!!ends[E.bOf(nd.id.slice(5))]; nd.classList.toggle('pal-hot', on); nd.classList.toggle('pal-dim', !on); nd._relMark=1; }); }
  if(!pill){ pill=document.createElement('div'); pill.id='pal-relrt'; document.body.appendChild(pill); }
  var ul=Object.keys(S.uR).map(lineOf).filter(Boolean);
  pill.style.setProperty('--cc', 'var(--accent)'); pill.classList.toggle('above', !!document.getElementById('pal-chiprt') && document.getElementById('pal-chiprt').classList.contains('on'));
  pill.innerHTML='<i></i><span><b>'+keys.map(function(k){ return esc(rl[k]||k); }).join(' + ')+'</b> · '+n+' route'+(n===1?'':'s')+(ul.length?' · rides '+ul.map(function(l){ return esc(l.n); }).join(', '):'')+'</span>'
    +(S.relLegs.length?modeHtml()+'<button class="tr-b" type="button" data-trip="rel">'+(S.mode==='drive'?'Drive':S.mode==='walk'?'Walk':'Ride')+' \u25b6</button>'+(window._palRide&&window._palRide.ui?window._palRide.ui.pillHtml():''):'')
    +'<button class="tr-px" type="button" data-pillx="1" aria-label="Clear the filter" title="Clear the filter">\u2715</button>';
  pill.classList.add('on'); paintUsed();
}

/* ── riding a filter's route: a guided trip, building to building along the drawn route ──
   The camera follows a rider along each leg; the panel names where you are and where you go next. */
var tripRaf=0, tripTimer=0;
function nameOf(id){ return E.name?E.name(id):id; }
function stopAnim(){ cancelAnimationFrame(tripRaf); tripRaf=0; clearTimeout(tripTimer); tripTimer=0; }
function riderG(){ var svg=E.svg(); if(!svg) return null; var h=E.fx&&E.fx()||svg, g=svg._rd; if(!g || g.parentNode!==h){ g=svg._rd=el('g',{'class':'pl-rd'},h); } if(h.lastChild!==g) h.appendChild(g); return g; }
function markCur(id){ document.querySelectorAll('#world .node.pal-trip-cur').forEach(function(n){ n.classList.remove('pal-trip-cur'); });
  var n=id!=null?document.getElementById('node-'+E.bOf(id)):null; if(n){ n.classList.add('pal-trip-cur'); n.style.setProperty('--cc', (S.trip&&S.trip.color)||'var(--accent)'); } }
function endTrip(){ if(window._palRide) window._palRide.exit(); if(!S.trip && !tripRaf) return; stopAnim(); S.trip=null; document.documentElement.classList.remove('pal-tripping'); markCur(null);
  var svg=E&&E.svg(); if(svg && svg._rd) svg._rd.innerHTML=''; }
function startTrip(kind){
  var L=((kind==='rel'?S.relLegs:S.tourLegs)||[]).slice(); if(!L.length || !E) return;
  if(window._palRide) window._palRide.mark();
  S.portal=null; S.line=null; S.stop=null; S.ride=null; stopAnim();
  S.trip={legs:L, at:-1, kind:kind, color:kind==='rel'?L[0].color:S.tourCol, name:kind==='rel'?'Routes':S.tourName, auto:false, busy:false, x:0, y:0};
  document.documentElement.classList.add('pal-tripping');
  var A=E.lot(E.P.at[L[0].a]); if(A){ S.trip.x=A[0]; S.trip.y=A[1]; E.flyMap(A[0], A[1], Math.max(E.Z(), .9), function(){ rider(A[0], A[1]); }); }
  markCur(L[0].a); paint(); }
function rider(x, y){ var g=riderG(); if(!g || !S.trip) return null; var o=g.querySelector('.pl-rider-o');
  if(!o){ var inner=E.pin(g, 'pl-rider-o', x, y); o=inner.parentNode; var c=el('g',{'class':'pl-rider'},inner); c.style.setProperty('--rc', S.trip.color||'#888');
    el('circle',{'class':'rd-o', r:11},c); el('circle',{'class':'rd-i', r:4},c); }
  o.setAttribute('transform','translate('+x+' '+y+')'); o.firstChild.firstChild.style.setProperty('--rc', S.trip.color||'#888'); return o; }
function animLeg(leg, rev, done){
  var g=riderG(); if(!g){ done(); return; }
  var p=el('path',{d:leg.d, fill:'none', stroke:'none'}, g), len=p.getTotalLength(); if(!(len>0)){ p.remove(); done(); return; }
  var reduce=window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches, ms=reduce?1:Math.max(1000, Math.min(4200, 800+len/5)), t0=performance.now();
  S.trip.busy=true;
  if(window._palRide && window._palRide.leg(leg, rev, function(x,y){ p.remove(); if(!S.trip) return; S.trip.busy=false; rider(x, y); S.trip.x=x; S.trip.y=y; if(E.center) E.center(x, y); done(); })) return;     /* first-person (palace_ride.py) */
  (function frame(t){ if(!S.trip){ p.remove(); return; }
    var k=Math.min(1,(t-t0)/ms), e=k*k*(3-2*k), q=p.getPointAtLength((rev?1-e:e)*len);
    rider(q.x, q.y); S.trip.x=q.x; S.trip.y=q.y; if(E.center) E.center(q.x, q.y);
    if(k<1) tripRaf=requestAnimationFrame(frame); else { tripRaf=0; p.remove(); S.trip.busy=false; done(); } })(t0);
}
function tripStep(d){
  var T0=S.trip; if(!T0 || T0.busy || !d) return; var L=T0.legs;
  if(d>0){ var nx=L[T0.at+1]; if(!nx){ T0.auto=false; paint(); return; }
    var go=function(){ T0.color=nx.color||T0.color; animLeg(nx, false, function(){ T0.at++; markCur(nx.b); paint(); if(T0.auto) tripTimer=setTimeout(function(){ tripStep(1); }, 650); }); };
    var here=T0.at<0?L[0].a:L[T0.at].b;
    if(nx.a!==here){ var A=E.lot(E.P.at[nx.a]); if(A){ T0.busy=true; E.flyMap(A[0], A[1], Math.max(E.Z(), .9), function(){ T0.busy=false; rider(A[0], A[1]); markCur(nx.a); go(); }); return; } }
    go(); }
  else { if(T0.at<0) return; var lg=L[T0.at]; T0.auto=false; animLeg(lg, true, function(){ T0.at--; markCur(T0.at<0?L[0].a:L[T0.at].b); paint(); }); }
}
function tripAuto(){ var T0=S.trip; if(!T0) return; T0.auto=!T0.auto; paint(); if(T0.auto && !T0.busy) tripStep(1); }
/* how a leg is made: the steps of its real path (walk, board a line at its stop, ride so many stops, get off), from the directions' own planner */
function legSteps(leg){ if(leg._st===undefined){ var pl=leg.opt||null; try{ if(!pl) pl=window._palDir&&window._palDir.legPlan?window._palDir.legPlan(leg.a, leg.b, S.mode):null; }catch(x){} leg._st=pl?pl.steps.filter(function(t){ return t.k!=='start' && t.k!=='arrive'; }):null; leg._sum=pl?pl.summary:''; } return leg._st; }
function stepsHtml(leg){ var st=legSteps(leg); if(!st || !st.length) return ''; var cc=function(t){ return t.c?' style="--sc:'+t.c+'"':''; };
  return '<ol class="tr-steps">'+st.map(function(t){ return '<li class="'+t.k+'"'+cc(t)+'><b></b><span>'+esc(t.text)+(t.sub?'<small>'+esc(t.sub)+'</small>':'')+'</span></li>'; }).join('')+'</ol>'; }
function paintTrip(p){
  var T0=S.trip, L=T0.legs, at=T0.at, here=at<0?L[0].a:L[at].b, nx=L[at+1], rel=T0.kind==='rel', c=(nx&&nx.color)||T0.color||'#888', n=rel?L.length:L.length+1;
  var linesOn=function(ids){ return (ids||[]).map(lineOf).filter(Boolean).map(function(l){ return esc(l.n); }).join(', '); };
  p.style.setProperty('--tc', c);
  p.innerHTML='<div class="tr-h"><span class="tr-sw" style="background:'+c+'"></span>'+esc(T0.name)+'<span class="tr-x" data-a="x" role="button" aria-label="Close">\u2715</span></div>'+modeHtml()
    +'<div class="tr-sub">'+(rel?(at<0?'Riding '+n+' route'+(n===1?'':'s')+' \u00b7 not started':'Route '+(at+1)+' of '+n):'Stop '+(at+2)+' of '+n).replace('Stop 1 of','Start \u00b7 stop 1 of')+'</div>'
    +'<div style="font-size:15px;font-weight:800;margin-bottom:3px">'+esc(nameOf(here))+'</div>'
    +(nx?'<div class="tr-sub" style="margin:0 0 4px">'+(rel?esc(nx.label||'Next')+': '+esc(nameOf(nx.a))+' \u2192 '+esc(nameOf(nx.b)):'Next: '+esc(nameOf(nx.b)))+(nx.lines&&nx.lines.length?' \u00b7 rides '+linesOn(nx.lines):(S.mode==='drive'?' \u00b7 by car':' \u00b7 on foot'))+'</div>'+stepsHtml(nx):'<div class="tr-sub" style="margin:0 0 6px">End of the route</div>')
    +'<div class="tr-btns"><button class="tr-b" data-a="tprev" '+(at<0||T0.busy?'disabled':'')+'>\u25c0</button><button class="tr-b go" data-a="tnext" '+(!nx||T0.busy?'disabled':'')+'>'+(nx?(rel?'Next route':'Next stop')+' \u25b6':'End')+'</button>'
    +(nx?'<button class="tr-b" data-a="tauto">'+(T0.auto?'Pause':'Ride it all')+'</button>':'')+'</div>'
    +(window._palRide?window._palRide.switchHtml():'')+'<div class="tr-sub" style="margin:7px 0 0">\u2190 \u2192 step along \u00b7 Space rides it all \u00b7 '+(window._palRide?'V first-person rides on / off \u00b7 ':'')+'Esc to get off</div>';
  p.classList.add('on'); }
/* ── pointing and clicking ── */
function chipOf(t){ var b=t.closest && t.closest('#nav .nav-btn'); if(!b) return null;
  var m=/showDetail\('[a-z]+','([^']+)'\)/.exec(b.getAttribute('onclick')||''); return (m && chipNodes(m[1]))?m[1]:null; }
var HOVER_DWELL=320;      /* ms the pointer must rest on a line / stop before the rest of the city fades */
function bind(){
  if(bind.done) return; bind.done=1;
  document.addEventListener('mouseover', function(e){
    if(!E || !E.palaceOn()) return;
    var c=chipOf(e.target); if(c){ if(S.chipH!==c){ S.chipH=c; renderChip(); } return; }
    if(S.chipH && !(e.target.closest && e.target.closest('#nav .nav-btn'))){ S.chipH=null; renderChip(); }
    if(!T) return; var tgt=e.target.closest && e.target.closest('#palace-svg .pl-stn-hit, #palace-svg .pl-tl-hit'); if(!tgt){ clearTimeout(S.dwT); if(S.hov){ S.hov=null; tipAt(''); if(!S.line&&S.stop==null&&!S.ride) lit(); } return; }
    /* hover INTENT: the line (or stop) fades the rest of the city only once the pointer has rested on it for a moment, not as it passes over */
    var key=tgt.classList.contains('pl-stn-hit')?'s'+tgt.getAttribute('data-s'):'l'+tgt.getAttribute('data-l'); if(S.hov && S.hov.key===key) return;
    clearTimeout(S.dwT); S.hov={key:key}; if(S.hovOn){ S.hovOn=0; tipAt(''); if(!S.line&&S.stop==null&&!S.ride) lit(); }
    S.dwT=setTimeout(function(){ if(!S.hov || S.hov.key!==key || !tgt.isConnected) return; S.hovOn=1;
      if(tgt.classList.contains('pl-stn-hit')){ var i=+tgt.getAttribute('data-s'); S.hov={key:key, s:i}; tipAt(stopTip(i), tgt);
        if(!S.line && S.stop==null && !S.ride){ var save=[S.line,S.stop]; S.stop=i; lit(); S.stop=save[1]; } }
      else { var id=tgt.getAttribute('data-l'); S.hov={key:key, l:id}; tipAt(lineTip(lineOf(id)), tgt);
        if(!S.line && S.stop==null && !S.ride){ var sv=S.line; S.line=id; lit(); S.line=sv; } } }, HOVER_DWELL);
  });
  document.addEventListener('mouseout', function(e){
    if(!E) return; var c=chipOf(e.target); if(c && !(e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest('#nav .nav-btn')===e.target.closest('#nav .nav-btn'))){ if(S.chipH===c){ S.chipH=null; renderChip(); } }
    var tgt=e.target.closest && e.target.closest('#palace-svg .pl-stn-hit, #palace-svg .pl-tl-hit');
    if(tgt && !(e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest('#palace-svg .pl-stn-hit, #palace-svg .pl-tl-hit'))){ clearTimeout(S.dwT); S.hov=null; S.hovOn=0; tipAt(''); lit(); }
  });
  document.addEventListener('click', function(e){
    if(!E || !T || !E.palaceOn()) return;
    var px=e.target.closest && e.target.closest('[data-pillx]'); if(px){ e.stopPropagation(); e.preventDefault(); endTrip(); var cl=document.getElementById('ef-clear'); if(cl) cl.click(); S.chipH=null; paint(); return; }
    var mb=e.target.closest && e.target.closest('[data-mode]'); if(mb && (mb.closest('#pal-chiprt,#pal-relrt,#pal-tr'))){ e.stopPropagation(); e.preventDefault(); setMode(mb.getAttribute('data-mode')); return; }
    var tb=e.target.closest && e.target.closest('[data-trip]'); if(tb){ e.stopPropagation(); e.preventDefault(); startTrip(tb.getAttribute('data-trip')); return; }
    var kr=e.target.closest && e.target.closest('.pk-row[data-tl]'); if(kr){ e.stopPropagation(); pickLine(kr.getAttribute('data-tl')); return; }
    var ph=e.target.closest && e.target.closest('#palace-svg .pl-portal'); if(ph){ e.stopPropagation(); e.preventDefault(); tipAt(''); takePortal(+ph.getAttribute('data-po'), ph); return; }
    var sh=e.target.closest && e.target.closest('#palace-svg .pl-stn-hit'); if(sh){ e.stopPropagation(); e.preventDefault(); tipAt(''); var i=+sh.getAttribute('data-s'); S.line=null; pickStop(i, true); return; }
    var lh=e.target.closest && e.target.closest('#palace-svg .pl-tl-hit'); if(lh){ e.stopPropagation(); e.preventDefault(); tipAt(''); pickLine(lh.getAttribute('data-l')); return; }
  }, true);
  window.addEventListener('keydown', function(e){
    if((!S.ride && !S.trip) || !E || e.metaKey || e.ctrlKey || e.altKey) return; var t=e.target; if(t && (t.tagName==='INPUT'||t.tagName==='TEXTAREA'||t.isContentEditable)) return;
    if(S.trip){ var kt=e.key, dt=(kt==='ArrowRight'||kt==='ArrowDown')?1:(kt==='ArrowLeft'||kt==='ArrowUp')?-1:0;
      if(dt){ e.preventDefault(); e.stopImmediatePropagation(); tripStep(dt); } else if(kt===' '){ e.preventDefault(); e.stopImmediatePropagation(); tripAuto(); } else if(kt==='Escape'){ e.preventDefault(); e.stopImmediatePropagation(); clear(); } return; }
    var k=e.key, d=(k==='ArrowRight'||k==='ArrowDown')?1:(k==='ArrowLeft'||k==='ArrowUp')?-1:0;
    if(d && S.ride){ d=arrowDir(k, d); }
    if(d){ e.preventDefault(); e.stopImmediatePropagation(); step(d); } else if(k==='Escape'){ e.preventDefault(); e.stopImmediatePropagation(); clear(); } }, true);
  /* a filter picked: the camera goes to where its route runs, from wherever the user is (a detail page or an enlarged building is left first) */
  function filterSig(){ var sel=window._altoChipSel?window._altoChipSel():{}, on=window._altoChipOn&&window._altoChipOn();
    return (on?JSON.stringify(sel):'')+'|'+relKeys().join(','); }
  document.addEventListener('alto-filter-changed', function(){
    var sig=filterSig(), fresh=sig!=='|' && sig!==S.flySig; if(sig==='|') S.flySig='';
    if(!fresh || !E){ chipRefresh(); renderRel(); return; }
    S.flySig=sig;
    E.leave(function(){
      endTrip(); S.portal=null; S.line=null; S.stop=null; S.ride=null; paint();         /* a picked line gives way to the filter's route */
      chipRefresh(); renderRel();
      var box=joinBox(S.cbox, S.rbox);                                       /* the route itself, not the whole length of every line it rides */
      if(box) fitLines([], [box[0]-60, box[1]-60, box[2]+60, box[3]+60]);
    });
  });
  window.addEventListener('click', function(e){ if(!E || !T) return; if(e.target.closest && e.target.closest('#ef-panel')) setTimeout(renderRel, 40); }, true);
}
function ready(){ bind(); chipRefresh(); renderRel(); }
window._palTr={init:init, has:has, lines:lines, stations:stations, portals:portals, hits:hits, keyHtml:keyHtml, holds:holds, ready:ready, redraw:function(){ endTrip(); paint(); renderChip(); renderRel(); },
  state:function(){ return S; }, nodeNear:function(x,y){ return E.nearest(x,y,1,600); }, ridden:function(p){ var g=bigG(), u={}; p.forEach(function(q,k){ if(k>0 && g.lid[q] && g.lid[q]===g.lid[p[k-1]]) u[g.lid[q]]=1; }); return Object.keys(u); }, ride:ride, pickStop:pickStop, pickLine:pickLine, route:function(a,b){ return dijk(a,b); }, clear:clear};
})();
"""
