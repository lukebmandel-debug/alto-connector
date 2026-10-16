"""Mind Palace Directions: building to building, like the Apple Maps app, on the phone and on the desktop.

One shared engine (DIR_JS, spliced into the palace's own script so it sees its streets and buildings) and one panel
that either module can host: the phone's bottom sheet (palace_mobile.py) or a floating glass card beside the zoom
row on the desktop (#pal-dir). A route is planned on the same graph the hover routes use (palace_transit_js.py
exports it as window._palTRx: the grid streets plus the real SEPTA/PATCO lines, WALK/RIDE/BOARD/XFER costs, dijk),
cut into walking and riding legs, drawn (walk legs dashed in the accent, ride legs in their line's colour, a dot at
each stop you board or leave), and told as steps: "Walk 4 blocks east on Walnut St", "Board Market-Frankford Line
toward Frankford at 15th St", "Ride 3 stops", "Get off at 2nd St".

Choosing the ends happens ONLY inside this mode (a top banner says what is being chosen and has a Cancel), by
searching a name or number, or by tapping a building, landmark or station; outside it, a building opens as it always did.
"""

DIR_CSS = r"""
  /* ═══ DIRECTIONS (palace_directions.py): delimited block ═══ */
  .pal-svg .pl-dir{pointer-events:none;}
  .pal-svg .dr-case{fill:none;stroke:var(--pal-halo);stroke-width:12;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke;stroke-opacity:.9;}
  .pal-svg .dr-walk{fill:none;stroke:var(--accent,#6d5bd0);stroke-width:4.4;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:7 8;vector-effect:non-scaling-stroke;}
  .pal-svg .dr-ride{fill:none;stroke-width:8;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke;}
  .pal-svg .dr-rsh{fill:none;stroke:rgba(255,255,255,.7);stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke;}
  /* a marker sits at its map point by its transform ATTRIBUTE (map units) and keeps its screen size by a unitless CSS scale on
     its inner .dr-sc — never px in a CSS transform, which Safari multiplies by the page's CSS zoom (see palace.py .pl-sc) */
  .pal-svg .dr-sc{transform:scale(calc(1 / var(--pz,1)));}
  .pal-svg .dr-mk circle{vector-effect:none;}
  .pal-svg .dr-stop circle{fill:#fff;stroke-width:3.4;}
  .pal-svg .dr-a circle.o{fill:#fff;stroke:var(--accent,#6d5bd0);stroke-width:3;} .pal-svg .dr-a circle.i{fill:var(--accent,#6d5bd0);}
  .pal-svg .dr-b path{fill:#e5484d;stroke:#fff;stroke-width:2;stroke-linejoin:round;} .pal-svg .dr-b circle{fill:#fff;}
  .pal-svg .dr-cur circle{fill:none;stroke:var(--accent,#6d5bd0);stroke-width:3;} .pal-svg .dr-cur circle.p{animation:drpulse 1.5s ease-out infinite;}
  @keyframes drpulse{0%{transform:scale(.6);opacity:.9}100%{transform:scale(2.4);opacity:0}}
  @media (prefers-reduced-motion: reduce){.pal-svg .dr-cur circle.p{animation:none;}}
  .pal-svg.dr-on .pl-blds .pl-bld:not(.pal-hot){opacity:.62;}

  #pal-dr-banner{position:fixed;z-index:4600;top:calc(10px + env(safe-area-inset-top,0px));left:12px;right:68px;max-width:430px;min-height:44px;box-sizing:border-box;display:none;align-items:center;gap:8px;
    padding:4px 4px 4px 16px;border-radius:22px;font:600 14px/1.25 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--text);
    background:var(--card-glass-bg,var(--surface));border:1px solid var(--card-glass-border,var(--border));-webkit-backdrop-filter:blur(18px) saturate(190%);backdrop-filter:blur(18px) saturate(190%);
    box-shadow:0 10px 26px var(--node-rest-shadow),inset 0 0 0 .5px var(--card-glass-rim);}
  #pal-dr-banner.on{display:flex;}
  #pal-dr-banner b{flex:1;font-weight:700;} #pal-dr-banner small{display:block;font-weight:500;color:var(--muted);font-size:12px;}
  #pal-dr-banner button{flex:none;min-width:64px;height:36px;border:0;border-radius:18px;background:color-mix(in srgb,var(--text) 8%,transparent);color:var(--accent,#6d5bd0);font:700 14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding:0 14px;}
  html:not(.mobile) #pal-dr-banner{left:50%;right:auto;transform:translateX(-50%);top:70px;width:min(420px,calc(100vw - 40px));}
  html.detail-open #pal-dr-banner,html.printing #pal-dr-banner{display:none !important;}

  .dr-root{font:14px/1.35 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--text);}
  .dr-fields{display:flex;align-items:stretch;gap:8px;}
  .dr-ff{flex:1;min-width:0;display:flex;flex-direction:column;gap:7px;position:relative;}
  .dr-f{display:flex;align-items:center;gap:10px;height:44px;box-sizing:border-box;padding:0 12px;border-radius:12px;background:color-mix(in srgb,var(--text) 6%,transparent);border:1.5px solid transparent;}
  .dr-f.on{border-color:var(--accent,#6d5bd0);background:color-mix(in srgb,var(--accent,#6d5bd0) 8%,transparent);}
  .dr-f i{flex:none;width:12px;height:12px;border-radius:50%;box-sizing:border-box;}
  .dr-f.from i{border:3px solid var(--accent,#6d5bd0);background:#fff;} .dr-f.to i{background:#e5484d;border-radius:50% 50% 50% 0;transform:rotate(-45deg) scale(.9);}
  .dr-f input{flex:1;min-width:0;height:100%;border:0;outline:0;background:none;color:var(--text);font:inherit;font-size:16px;}
  .dr-f input::placeholder{color:var(--muted);}
  .dr-sw,.dr-x{flex:none;width:44px;border:0;border-radius:12px;background:none;color:var(--muted);display:flex;align-items:center;justify-content:center;padding:0;-webkit-tap-highlight-color:transparent;}
  .dr-sw{align-self:center;height:44px;color:var(--accent,#6d5bd0);} .dr-sw:active,.dr-x:active{background:color-mix(in srgb,var(--text) 10%,transparent);}
  .dr-hint{margin:14px 2px 4px;color:var(--muted);font-size:13px;}
  .dr-sg{margin:8px 0 0;padding:0;list-style:none;} .dr-sg li,.dr-st li{display:flex;gap:12px;align-items:center;min-height:52px;padding:6px 4px;border-bottom:1px solid color-mix(in srgb,var(--muted) 22%,transparent);cursor:pointer;-webkit-tap-highlight-color:transparent;}
  .dr-sg li:active,.dr-st li:active{background:color-mix(in srgb,var(--text) 7%,transparent);}
  .dr-sg .dr-bd{flex:none;min-width:34px;height:30px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-weight:750;font-size:12px;background:color-mix(in srgb,var(--accent,#6d5bd0) 14%,transparent);color:var(--accent,#6d5bd0);padding:0 5px;box-sizing:border-box;}
  .dr-sg b{display:block;font-size:15px;font-weight:650;} .dr-sg small,.dr-st small{display:block;color:var(--muted);font-size:12.5px;margin-top:1px;}
  .dr-opts{display:flex;gap:8px;margin:12px 0 4px;} .dr-opt{flex:1;min-height:44px;border-radius:12px;border:1.5px solid color-mix(in srgb,var(--muted) 35%,transparent);background:none;color:var(--text);font:inherit;font-weight:650;padding:4px 8px;}
  .dr-opt.on{border-color:var(--accent,#6d5bd0);background:color-mix(in srgb,var(--accent,#6d5bd0) 10%,transparent);color:var(--accent,#6d5bd0);} .dr-opt small{display:block;font-weight:500;font-size:12px;color:var(--muted);}
  .dr-sum{display:flex;align-items:center;gap:12px;margin:12px 2px 6px;} .dr-sum div{flex:1;min-width:0;} .dr-sum b{font-size:19px;font-weight:750;} .dr-sum small{display:block;color:var(--muted);font-size:13px;}
  .dr-go{flex:none;min-width:84px;height:44px;border:0;border-radius:22px;background:var(--accent,#6d5bd0);color:#fff;font:750 16px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding:0 20px;-webkit-tap-highlight-color:transparent;}
  .dr-go:active{filter:brightness(.88);}
  .dr-st{margin:0;padding:0;list-style:none;} .dr-st li{align-items:flex-start;padding:10px 4px;} .dr-st li.cur{background:color-mix(in srgb,var(--accent,#6d5bd0) 11%,transparent);border-radius:10px;}
  .dr-ic{flex:none;width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:color-mix(in srgb,var(--ic,var(--accent,#6d5bd0)) 16%,transparent);color:var(--ic,var(--accent,#6d5bd0));margin-top:1px;}
  .dr-st div b{font-weight:600;font-size:15px;display:block;}
  .dr-nav{display:flex;align-items:center;gap:8px;}
  .dr-nav .dr-nt{flex:1;min-width:0;} .dr-nav .dr-nt b{display:block;font-size:16px;font-weight:700;line-height:1.25;} .dr-nav .dr-nt small{display:block;color:var(--muted);font-size:12.5px;}
  .dr-nb{flex:none;width:44px;height:44px;border-radius:50%;border:0;background:color-mix(in srgb,var(--text) 8%,transparent);color:var(--text);display:flex;align-items:center;justify-content:center;padding:0;font-size:18px;}
  .dr-nb[disabled]{opacity:.35;} .dr-nb.end{width:auto;border-radius:22px;padding:0 14px;color:#e5484d;font:700 14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}

  /* the desktop's panel: a glass card above the zoom row, never a tooltip following the cursor */
  #pal-dir{position:fixed;left:71.5px;bottom:76px;z-index:312;width:min(360px,calc(100vw - 100px));max-height:min(560px,calc(100vh - 150px));overflow:auto;box-sizing:border-box;padding:12px 14px 14px;border-radius:16px;display:none;
    background:var(--card-glass-bg,var(--surface));border:1px solid var(--card-glass-border,var(--border));-webkit-backdrop-filter:blur(18px) saturate(190%);backdrop-filter:blur(18px) saturate(190%);
    box-shadow:0 14px 36px var(--node-rest-shadow),inset 0 0 0 .5px var(--card-glass-rim);}
  #pal-dir.on{display:block;} #pal-dir .dr-h{display:flex;align-items:center;margin:0 0 10px;font-weight:750;font-size:15px;} #pal-dir .dr-h span{flex:1;} #pal-dir .dr-h .dr-x{width:32px;height:32px;}
  html.mobile #pal-dir,html.detail-open #pal-dir,html.printing #pal-dir,html:not(.alto-palace) #pal-dir{display:none !important;}
  #pal-ctl .pc-dirb{position:relative;flex:none;width:35px;height:35px;box-sizing:border-box;border-radius:50%;padding:0;display:inline-flex;align-items:center;justify-content:center;color:var(--muted);cursor:pointer;
    background:var(--card-glass-bg,var(--surface));border:1px solid var(--card-glass-border,var(--border));-webkit-backdrop-filter:blur(18px) saturate(190%);backdrop-filter:blur(18px) saturate(190%);
    box-shadow:0 10px 26px var(--node-rest-shadow),inset 0 0 0 .5px var(--card-glass-rim);}
  #pal-ctl .pc-dirb:hover,#pal-ctl .pc-dirb:focus-visible{border-color:var(--muted);color:var(--text);outline:none;} #pal-ctl .pc-dirb.on{color:var(--accent,#6d5bd0);border-color:color-mix(in srgb,var(--accent,#6d5bd0) 55%,transparent);}
"""

DIR_JS = r"""
/* ═══ DIRECTIONS (palace_directions.py): the planner, the drawing and the panel ═══ */
var DIR=(function(){
var S={on:false, from:null, to:null, focus:'to', q:'', plans:null, opt:0, nav:null, ad:null, host:null, cur:null};
var TX=window._palTRx;
var COMP=['east','northeast','north','northwest','west','southwest','south','southeast'];
function compass(dx,dy){ var a=Math.atan2(-dy,dx)*180/Math.PI; if(a<0) a+=360; return COMP[Math.round(a/45)%8]; }
function lineCol(id){ var l=TX&&TX.lineOf(id); return l?TX.col(l):'#6d5bd0'; }
function ico(k,c){ var p={walk:'<circle cx="11" cy="4.2" r="1.7"/><path d="M11 7.5l-1.6 4.2 2.4 2.3.8 4.5M9.4 11.7L7 13.4M11 8.4l3 2.6 2.3-.2M11.8 14l2.9 4"/>',
  rail:'<rect x="5.5" y="3.5" width="11" height="12" rx="3"/><path d="M5.5 10h11M8 18.5l1.6-3M14 18.5l-1.6-3"/><circle cx="8.5" cy="12.6" r=".6"/><circle cx="13.5" cy="12.6" r=".6"/>',
  ride:'<path d="M4 11h14M13 6l5 5-5 5"/>', off:'<path d="M11 4v11M6.5 11l4.5 4.5 4.5-4.5M5 18.5h12"/>', start:'<circle cx="11" cy="11" r="4"/>', arrive:'<path d="M11 18.5s5.5-5 5.5-9.2a5.5 5.5 0 0 0-11 0c0 4.200 5.500 9.200 5.500 9.200z"/><circle cx="11" cy="9.400" r="1.800"/>'}[k]||'';
  return '<span class="dr-ic" style="--ic:'+(c||'var(--accent,#6d5bd0)')+'"><svg viewBox="0 0 22 22" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'+p+'</svg></span>'; }

/* ── the places: buildings (and floors), landmarks, stations ── */
function bldPlace(id, floor){ var b=bOf(id), L=lot(P.at[b]); if(!L||!TT[b]) return null;
  return {k:'b', id:b, name:title(b), num:num(b), sub:(P.near||{})[b]||'', x:L[0], y:L[1], node:entrance(b)}; }
function lmPlace(l){ var b=l.box, cx=b?(b[0]+b[2])/2:l.x, cy=b?(b[1]+b[3])/2:l.y;
  return {k:'l', id:'l:'+l.n, name:l.n, num:'', sub:l.page?'Landmark · reference inside':'Landmark', page:l.page||'', x:cx, y:cy, node:nearest(cx,cy,1,500)}; }
function stPlace(i){ var s=TX.stops()[i]; if(!s) return null; var ls=(s.l||[]).map(TX.lineOf).filter(Boolean);
  return {k:'s', id:'s:'+i, i:i, name:s.n, num:'', sub:ls.map(function(l){ return l.n; }).join(' · ')||'Station', x:s.x, y:s.y, node:nearest(s.x,s.y,1,600), lines:ls.map(function(l){ return l.id; })}; }
function index(){ var out=[];
  Object.keys(P.at).forEach(function(id){ if(!isB(id)) return; var p=bldPlace(id); if(p) out.push(p); });
  ORDER.forEach(function(id){ if(!P.of[id]) return; var p=bldPlace(P.of[id]); if(!p) return; var f=Object.create(p); f.name=title(id); f.num=num(id); f.sub='Floor of '+p.num+' '+p.name; f.fl=1; out.push(f); });
  (M.landmarks||[]).forEach(function(l){ if(l.n && (l.box||l.x!=null)) out.push(lmPlace(l)); });
  if(TX&&TX.has()) TX.stops().forEach(function(s,i){ if(s.n) out.push(stPlace(i)); });
  if(window._palHw&&window._palHw.has()) out=out.concat(window._palHw.places());   /* C3: highways and their exits */
  return out; }
function search(q, lim){ q=String(q||'').trim().toLowerCase(); if(!q) return []; var tk=q.split(/\s+/), all=index(), out=[];
  all.forEach(function(p){ var nm=p.name.toLowerCase(), nu=String(p.num||'').toLowerCase(), h=(nu+' '+nm+' '+String(p.sub||'').toLowerCase()), s=0;
    if(nu && nu===q) s=100; else if(nu && /\d/.test(q) && nu.indexOf(q)===0) s=84;
    if(nm===q) s=Math.max(s,96); else if(nm.indexOf(q)===0) s=Math.max(s,74); else if(nm.indexOf(' '+q)>=0) s=Math.max(s,58); else if(nm.indexOf(q)>=0) s=Math.max(s,44);
    else if(tk.every(function(t){ return h.indexOf(t)>=0; })) s=30;
    if(s) out.push([s-(p.fl?6:0)-(p.k==='s'?3:0),p]); });
  out.sort(function(a,b){ return b[0]-a[0] || (a[1].name<b[1].name?-1:1); });
  return out.slice(0,lim||12).map(function(a){ return a[1]; }); }

/* ── the plan: legs of walking and riding, then steps ── */
function nodeStop(g){ if(g._ns) return g._ns; var ns={}; Object.keys(g.at||{}).forEach(function(si){ g.at[si].forEach(function(q){ ns[q.n]=+si; }); }); return g._ns=ns; }
function legsOf(path, g){ var legs=[], cur=null;
  function kind(u,v){ var lu=g.lid[u], lv=g.lid[v]; if(lu && lu===lv) return 'ride'; if(lu && lv) return 'xfer'; return 'walk'; }
  for(var i=0;i+1<path.length;i++){ var k=kind(path[i],path[i+1]);
    if(!cur || cur.k!==k || k==='xfer' || (k==='ride' && cur.l!==g.lid[path[i]])){ cur={k:k, l:k==='ride'?g.lid[path[i]]:null, n:[path[i]]}; legs.push(cur); }
    cur.n.push(path[i+1]); }
  return legs; }
function runsOf(nodes, g){ var gn=graph().names, N=g.N, runs=[], cur=null;
  for(var i=0;i+1<nodes.length;i++){ var u=nodes[i], v=nodes[i+1]; if(u>=N||v>=N) continue;
    var nu=Object.keys(gn[u]), nv=Object.keys(gn[v]), nm=nu.filter(function(x){ return gn[v][x]; })[0] || (cur&&cur.name&&(gn[v][cur.name]||gn[u][cur.name])?cur.name:'') || nv[0] || nu[0] || '';
    if(!cur || (nm && cur.name && nm!==cur.name)){ cur={name:nm, blocks:0, x0:g.X[u], y0:g.Y[u]}; runs.push(cur); } else if(!cur.name && nm) cur.name=nm;
    if(nv.length>=2) cur.blocks++; cur.x1=g.X[v]; cur.y1=g.Y[v]; }
  return runs.filter(function(r){ return Math.hypot(r.x1-r.x0,r.y1-r.y0)>1; }); }
function option(path, A, B, g, kind){
  var legs=legsOf(path, g), ns=nodeStop(g), stops=TX.stops(), steps=[], walkBlocks=0, rideStops=0, rides=0, names=[];
  if(!legs.length) legs=[{k:'walk', l:null, n:path.slice()}];
  legs.forEach(function(l){ l.pts=l.n.map(function(n){ return [g.X[n],g.Y[n]]; }); });
  var f=legs[0], e=legs[legs.length-1];
  if(f.k==='walk') f.pts.unshift([A.x,A.y]); if(e.k==='walk') e.pts.push([B.x,B.y]);
  steps.push({k:'start', ic:'start', text:'Start at '+(A.num?A.num+' ':'')+A.name, sub:A.sub, x:A.x, y:A.y});
  legs.forEach(function(l,i){ var nx=legs[i+1];
    if(l.k==='walk'){ var runs=runsOf(l.n, g);
      runs.forEach(function(r){ var b=Math.max(1,r.blocks); walkBlocks+=b;
        steps.push({k:'walk', ic:'walk', text:'Walk '+b+' block'+(b>1?'s':'')+' '+compass(r.x1-r.x0,r.y1-r.y0)+(r.name?' on '+r.name:''), x:r.x0, y:r.y0}); });
      if(!runs.length){ var d=Math.hypot(l.pts[l.pts.length-1][0]-l.pts[0][0], l.pts[l.pts.length-1][1]-l.pts[0][1]); walkBlocks+=d>60?1:0;
        steps.push({k:'walk', ic:'walk', text:nx&&nx.k==='ride'&&ns[nx.n[0]]!=null?'Walk to '+stops[ns[nx.n[0]]].n:'Walk to '+B.name, x:l.pts[0][0], y:l.pts[0][1]}); } }
    else if(l.k==='ride'){ var line=TX.lineOf(l.l), c=lineCol(l.l), si=l.n.map(function(n){ return ns[n]; }).filter(function(v,k,a){ return v!=null && a.indexOf(v)===k; });
      if(si.length<2){ return; } rides++; rideStops+=si.length-1; names.push(line.n);
      var ord=(line.s||[]), i0=ord.indexOf(si[0]), i1=ord.indexOf(si[si.length-1]), toward=(i0>=0&&i1>=0)?stops[ord[i1>i0?ord.length-1:0]].n:'';
      var prev=legs[i-1], bs=stops[si[0]], as=stops[si[si.length-1]];
      steps.push({k:'board', ic:'rail', c:c, l:l.l, text:'Board '+line.n+(toward&&toward!==bs.n?' toward '+toward:'')+' at '+bs.n, x:bs.x, y:bs.y});
      steps.push({k:'ride', ic:'ride', c:c, l:l.l, text:'Ride '+(si.length-1)+' stop'+(si.length>2?'s':''), sub:si.slice(1).map(function(v){ return stops[v].n; }).join(' · '), x:bs.x, y:bs.y});
      var chg=nx&&nx.k==='xfer';
      steps.push({k:'alight', ic:'off', c:c, l:l.l, text:(chg?'Change at ':'Get off at ')+as.n, x:as.x, y:as.y});
      l.board=bs; l.alight=as; l.line=line; l.color=c; }
  });
  steps.push({k:'arrive', ic:'arrive', text:'Arrive at '+(B.num?B.num+' ':'')+B.name, sub:B.sub, x:B.x, y:B.y});
  var min=Math.max(1, Math.round(walkBlocks*1.6 + rideStops*1.8 + rides*4));
  var uniq=names.filter(function(v,k,a){ return a.indexOf(v)===k; });
  var sum=rides ? min+' min · '+rideStops+' stop'+(rideStops>1?'s':'')+' on '+(uniq.length===1?uniq[0]:uniq.length+' lines') : min+' min · '+Math.max(1,walkBlocks)+' block'+(walkBlocks>1?'s':'')+' walking';
  var bb=[1e9,1e9,-1e9,-1e9]; legs.forEach(function(l){ l.pts.forEach(function(p){ bb[0]=Math.min(bb[0],p[0]); bb[1]=Math.min(bb[1],p[1]); bb[2]=Math.max(bb[2],p[0]); bb[3]=Math.max(bb[3],p[1]); }); });
  return {kind:kind, min:min, rides:rides, rideStops:rideStops, blocks:walkBlocks, legs:legs, steps:steps, summary:sum, box:bb, lines:uniq}; }
function plan(A, B){ if(!A||!B) return null; var g=TX&&TX.graph(), out=[];
  if(!g || A.node<0 || B.node<0) return null;
  var tp=TX.dijk(A.node, B.node); if(tp){ var o=option(tp, A, B, g, 'transit'); if(o.rides) out.push(o); }
  var wp=route(A.node, B.node); if(wp){ var w=option(wp, A, B, g, 'walk'); out.push(w); }
  if(window._palHw&&window._palHw.has()){ var dv=window._palHw.drive(A, B); if(dv) out.push(dv); }   /* C3: drive by the highways */
  out.sort(function(a,b){ return a.min-b.min; });
  return out.length?out:null; }

/* ── on the map ── */
function mk(parent, cls, x, y, inner){ var gg=el('g',{'class':'dr-mk '+cls, transform:'translate('+(+x)+' '+(+y)+')'},parent); el('g',{'class':'dr-sc'},gg).innerHTML=inner; return gg; }
function mkAt(gg, x, y){ gg.setAttribute('transform', 'translate('+(+x)+' '+(+y)+')'); }
function draw(){ var ad=S.ad; if(!ad) return; var svg=ad.svg(); if(!svg) return;
  var g=svg._dir; if(!g || g.parentNode!==svg){ g=svg._dir=el('g',{'class':'pl-dir'},svg); } else svg.appendChild(g);
  g.innerHTML=''; var opt=S.plans&&S.plans[S.opt], hot=[];
  svg.classList.toggle('dr-on', !!(S.on && (S.from||S.to)));
  if(opt){ opt.legs.forEach(function(l){ var d='M'+l.pts.map(function(p){ return p[0]+' '+p[1]; }).join('L');
      if(l.k==='walk'){ el('path',{'class':'dr-case', d:d},g); el('path',{'class':'dr-walk', d:d},g); }
      else if(l.k==='ride'){ el('path',{'class':'dr-case', d:d},g); el('path',{'class':'dr-ride', d:d, stroke:l.color||lineCol(l.l)},g); el('path',{'class':'dr-rsh', d:d},g); } });
    opt.legs.forEach(function(l){ if(l.k!=='ride' || !l.board) return;
      [l.board,l.alight].forEach(function(s){ mk(g,'dr-stop',s.x,s.y,'<circle r="6.5" stroke="'+l.color+'"/>'); }); }); }
  if(S.from){ mk(g,'dr-a',S.from.x,S.from.y,'<circle class="o" r="9"/><circle class="i" r="4"/>'); if(S.from.k==='b') hot.push(S.from.id); }
  if(S.to){ mk(g,'dr-b',S.to.x,S.to.y,'<path d="M0 0C-10-12-12-22-6-27 0-31 6-27 8-22 11-13 4-8 0 0z" transform="translate(-1 0)"/><circle cx="0" cy="-17" r="3.4"/>'); if(S.to.k==='b') hot.push(S.to.id); }
  S.cur=mk(g,'dr-cur',-999,-999,'<circle class="p" r="12"/><circle r="12"/>');
  if(ad.hot) ad.hot(hot); }
function showStep(i){ var opt=S.plans&&S.plans[S.opt]; if(!opt) return; var s=opt.steps[i]; if(!s) return;
  if(S.cur) mkAt(S.cur, s.x, s.y);
  S.step=i; S.ad.fly(s.x, s.y, 'step'); }

/* ── the panel ── */
function banner(){ var b=document.getElementById('pal-dr-banner');
  if(!b){ b=document.createElement('div'); b.id='pal-dr-banner'; b.setAttribute('role','status'); document.body.appendChild(b);
    b.addEventListener('click', function(e){ if(e.target.closest('button')) close(); }); }
  var msg=S.focus==='from'?'Choose start':S.focus==='to'?'Choose destination':'';
  b.innerHTML='<b>'+(msg||'Directions')+'<small>'+(msg?'Tap a building, landmark or station — or search':'Tap a step to see it on the map')+'</small></b><button type="button">Cancel</button>';
  b.classList.toggle('on', !!S.on && S.nav==null); }
function fieldsHtml(){ function f(k,ph){ var p=S[k]; return '<div class="dr-f '+k+(S.focus===k?' on':'')+'" data-f="'+k+'"><i></i><input data-f="'+k+'" type="search" enterkeyhint="search" autocomplete="off" autocorrect="off" spellcheck="false" placeholder="'+ph+'" value="'+esc(S.focus===k&&S.q?S.q:(p?(p.num?p.num+' ':'')+p.name:''))+'" aria-label="'+ph+'"></div>'; }
  return '<div class="dr-fields"><div class="dr-ff">'+f('from','Start')+f('to','Destination')+'</div>'
    +'<button type="button" class="dr-sw" aria-label="Swap start and destination"><svg viewBox="0 0 22 22" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 18V5M3.500 8.500L7 5l3.500 3.500M15 4v13M11.500 13.500L15 17l3.500-3.500"/></svg></button></div>'; }
function mainHtml(){ var h='';
  if(S.q){ var r=search(S.q, 10);
    return r.length?'<ul class="dr-sg">'+r.map(function(p,i){ return '<li data-i="'+i+'"><span class="dr-bd">'+esc(p.num||(p.k==='s'?'●':'◆'))+'</span><div><b>'+esc(p.name)+'</b><small>'+esc(p.sub||'')+'</small></div></li>'; }).join('')+'</ul>'
      :'<p class="dr-hint">Nothing matches “'+esc(S.q)+'”.</p>'; }
  var opt=S.plans&&S.plans[S.opt];
  if(S.from && S.to && !S.plans) return '<p class="dr-hint">No way to get from '+esc(S.from.name)+' to '+esc(S.to.name)+' on these streets.</p>';
  if(!opt) return '<p class="dr-hint">'+(S.focus==='from'?'Choose where you start':'Choose where you are going')+' — tap a building on the map, or type a name or a number.</p>';
  if(S.plans.length>1) h+='<div class="dr-opts">'+S.plans.map(function(o,i){ return '<button type="button" class="dr-opt'+(i===S.opt?' on':'')+'" data-o="'+i+'">'+(o.kind==='walk'?'Walk':o.kind==='drive'?'Drive':'Transit')+'<small>'+o.min+' min</small></button>'; }).join('')+'</div>';
  h+='<div class="dr-sum"><div><b>'+esc(opt.summary.split(' · ')[0])+'</b><small>'+esc(opt.summary.split(' · ').slice(1).join(' · '))+'</small></div><button type="button" class="dr-go">Start</button></div>';
  h+='<ol class="dr-st">'+opt.steps.map(function(s,i){ return '<li data-i="'+i+'"'+(S.step===i?' class="cur"':'')+'>'+ico(s.ic,s.c)+'<div><b>'+esc(s.text)+'</b>'+(s.sub?'<small>'+esc(s.sub)+'</small>':'')+'</div></li>'; }).join('')+'</ol>';
  return h; }
function navHtml(){ var opt=S.plans&&S.plans[S.opt]; if(!opt||S.nav==null) return ''; var s=opt.steps[S.nav], n=opt.steps.length;
  return '<div class="dr-nav"><button type="button" class="dr-nb" data-n="-1" aria-label="Previous step"'+(S.nav<=0?' disabled':'')+'>‹</button>'+ico(s.ic,s.c)
    +'<div class="dr-nt"><b>'+esc(s.text)+'</b><small>Step '+(S.nav+1)+' of '+n+(s.sub?' · '+esc(s.sub):'')+'</small></div>'
    +'<button type="button" class="dr-nb" data-n="1" aria-label="Next step"'+(S.nav>=n-1?' disabled':'')+'>›</button><button type="button" class="dr-nb end" data-n="x">End</button></div>'; }
function render(){ var h=S.host; if(!h) return;
  if(S.nav!=null && S.ad.navEl){ S.ad.navEl.innerHTML=navHtml(); if(S.ad.onNav) S.ad.onNav(true); banner(); return; }
  if(S.ad.onNav) S.ad.onNav(false);
  h.innerHTML='<div class="dr-root">'+(S.nav!=null?navHtml():fieldsHtml()+'<div class="dr-main">'+mainHtml()+'</div>')+'</div>'; banner(); if(S.ad.onRender) S.ad.onRender(); }
function renderMain(){ var m=S.host&&S.host.querySelector('.dr-main'); if(m) m.innerHTML=mainHtml(); }
function replan(){ S.plans=(S.from&&S.to)?plan(S.from,S.to):null; S.opt=0; S.nav=null; S.step=null; draw();
  var o=S.plans&&S.plans[0]; if(o&&S.ad.fit) S.ad.fit(o.box); else if(S.from&&!S.to&&S.ad.fly) S.ad.fly(S.from.x,S.from.y,'place'); else if(S.to&&!S.from&&S.ad.fly) S.ad.fly(S.to.x,S.to.y,'place'); }
function pick(p, field){ if(!S.on||!p) return false; var f=field||S.focus; if(!f) return false; S[f]=p; S.q='';
  S.focus=!S.from?'from':!S.to?'to':null; replan(); render(); if(S.ad.onPick) S.ad.onPick(); return true; }
function open(ad, o){ o=o||{}; S.ad=ad; S.host=ad.host; S.on=true; S.from=o.from||null; S.to=o.to||null; S.q=''; S.nav=null; S.step=null;
  S.focus=!S.from?'from':!S.to?'to':null; if(ad.onOpen) ad.onOpen(); replan(); render(); }
function close(){ if(!S.on) return; var ad=S.ad; S.on=false; S.nav=null; S.plans=null; S.from=S.to=null; S.q=''; S.focus=null;
  if(ad){ var svg=ad.svg&&ad.svg(); if(svg&&svg._dir) svg._dir.innerHTML=''; if(svg) svg.classList.remove('dr-on'); if(ad.hot) ad.hot([]); if(ad.onClose) ad.onClose(); }
  var b=document.getElementById('pal-dr-banner'); if(b) b.classList.remove('on'); }
function wire(root){
  root.addEventListener('input', function(e){ var i=e.target.closest('input[data-f]'); if(!i) return; S.focus=i.getAttribute('data-f'); S.q=i.value; root.querySelectorAll('.dr-f').forEach(function(d){ d.classList.toggle('on', d.getAttribute('data-f')===S.focus); }); renderMain(); banner(); });
  root.addEventListener('focusin', function(e){ var i=e.target.closest('input[data-f]'); if(!i) return; S.focus=i.getAttribute('data-f'); root.querySelectorAll('.dr-f').forEach(function(d){ d.classList.toggle('on', d.getAttribute('data-f')===S.focus); }); banner(); if(S.ad.onType) S.ad.onType(); try{ i.select(); }catch(x){} });
  root.addEventListener('click', function(e){ var t=e.target;
    var sg=t.closest('.dr-sg li'); if(sg){ var r=search(S.q,10)[+sg.getAttribute('data-i')]; if(r){ if(document.activeElement&&document.activeElement.blur) document.activeElement.blur(); pick(r); } return; }
    if(t.closest('.dr-sw')){ var a=S.from; S.from=S.to; S.to=a; S.q=''; S.focus=!S.from?'from':!S.to?'to':null; replan(); render(); return; }
    var o=t.closest('.dr-opt'); if(o){ S.opt=+o.getAttribute('data-o'); S.step=null; draw(); render(); var p=S.plans[S.opt]; if(p&&S.ad.fit) S.ad.fit(p.box); return; }
    if(t.closest('.dr-go')){ S.nav=0; render(); showStep(0); return; }
    var st=t.closest('.dr-st li'); if(st){ var i=+st.getAttribute('data-i'); S.step=i; root.querySelectorAll('.dr-st li').forEach(function(li){ li.classList.toggle('cur', +li.getAttribute('data-i')===i); }); showStep(i); return; }
    var nb=t.closest('.dr-nb'); if(nb){ var v=nb.getAttribute('data-n'), opt=S.plans&&S.plans[S.opt];
      if(v==='x'){ S.nav=null; S.step=null; render(); if(S.ad.fit&&opt) S.ad.fit(opt.box); return; }
      S.nav=Math.max(0,Math.min(opt.steps.length-1,S.nav+(+v))); render(); showStep(S.nav); return; }
    if(t.closest('.dr-x')) close(); });
}
var api={state:function(){ return S; }, search:search, plan:plan, index:index, bldPlace:bldPlace, lmPlace:lmPlace, stPlace:stPlace, open:open, close:close, pick:pick, render:render, draw:draw, wire:wire,
  banner:banner, navHtml:navHtml, showStep:showStep, isOn:function(){ return S.on; }, ico:ico, lineCol:lineCol};
return api; })();
window._palDir=DIR;

/* ── the desktop's panel: a floating glass card above the zoom row, and its button beside the zoom pill ── */
(function(){
function pan(){ var p=document.getElementById('pal-dir'); if(p) return p;
  p=document.createElement('div'); p.id='pal-dir'; p.setAttribute('role','dialog'); p.setAttribute('aria-label','Directions');
  p.innerHTML='<div class="dr-h"><span>Directions</span><button type="button" class="dr-x" aria-label="Close directions"><svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M5 5l10 10M15 5L5 15"/></svg></button></div><div class="dr-body"></div>';
  document.body.appendChild(p); DIR.wire(p); return p; }
function adapter(){ var p=pan(), body=p.querySelector('.dr-body');
  return {desktop:true, host:body, navEl:null, svg:function(){ return svgD; },
    fly:function(x,y,m){ flyAway(x, y, m==='step'?Math.max(Z,1.1):Math.max(Z,.9)); },
    fit:function(b){ flyToBox(b); },
    hot:function(ids){ document.querySelectorAll('#world .node.pal-hot').forEach(function(n){ n.classList.remove('pal-hot'); });
      ids.forEach(function(id){ var n=document.getElementById('node-'+id); if(n) n.classList.add('pal-hot'); }); },
    onOpen:function(){ p.classList.add('on'); var b=document.getElementById('pal-dir-btn'); if(b) b.classList.add('on'); },
    onClose:function(){ p.classList.remove('on'); var b=document.getElementById('pal-dir-btn'); if(b) b.classList.remove('on'); },
    onRender:function(){ var i=body.querySelector('.dr-f.on input'); if(i && !i.value && document.activeElement!==i) i.focus({preventScroll:true}); }}; }
window._palDirOpen=function(o){ if(window._focusedNodeId && window.exitFocus) try{ window.exitFocus(); }catch(x){} DIR.open(adapter(), o); };
window._palDirMount=function(c){ if(c.querySelector('.pc-dirb')) return; var b=document.createElement('button'); b.type='button'; b.className='pc-dirb'; b.id='pal-dir-btn'; b.setAttribute('aria-label','Directions'); b.title='Directions';
  b.innerHTML='<svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 2.500l7.500 7.500-7.500 7.500L2.500 10z"/><path d="M6.800 11.300V9.200a1.200 1.200 0 0 1 1.200-1.200h3.700M10.800 6.300L12.500 8l-1.700 1.700"/></svg>';
  b.addEventListener('click', function(e){ e.stopPropagation(); if(DIR.isOn()) DIR.close(); else window._palDirOpen({}); }); c.appendChild(b); };
/* while Directions asks for an end, a click on a building, landmark or station is the answer (and only then); on the window, in the capture phase, so it comes before the palace's own click-to-enlarge */
window.addEventListener('click', function(e){ if(mob() || !DIR.isOn() || !DIR.state().ad || !DIR.state().ad.desktop) return; var t=e.target;
  if(!t.closest || t.closest('#pal-dir,#pal-ctl,#pal-key,#pal-dr-banner,#detail-page')) return;
  if(!DIR.state().focus) return; var id=bAt(t), p=null, lm=t.closest('#palace-svg .pl-lmb'), sn=t.closest('#palace-svg .pl-stn-hit,#palace-svg .tr-stn');
  if(id) p=DIR.bldPlace(id); else if(lm){ var nm=lm.getAttribute('data-name'); p=DIR.index().filter(function(q){ return q.k==='l' && q.name===nm; })[0]; }
  else if(sn){ p=DIR.stPlace(+sn.getAttribute('data-s')); }
  if(!p) return; e.preventDefault(); e.stopImmediatePropagation(); DIR.pick(p); }, true);
window.addEventListener('keydown', function(e){ if(e.key==='Escape' && DIR.isOn() && DIR.state().ad && DIR.state().ad.desktop){ DIR.close(); e.stopImmediatePropagation(); } }, true);
})();
"""
