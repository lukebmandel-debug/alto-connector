"""The Memory Blueprint's hosted renderer (brief.palace_view "building"): /bldg/palace-building-<hash>.js, loaded by the page (palace_assets.py).

The page holds a ~350 byte loader and the page data (`window._ALTO_BUILDING`: the plan's hash, the timeline's nodes and the room or anchor each stands
in); everything else — the blueprint, and later the first-person view — is this script plus the plan it fetches (/bldg/plan-<hash>.json,
building_schema.hosted_json). A page whose script or plan is missing (an exported single file, an old page) simply keeps its cards.
With the plan loaded there are two views only, the blueprint and the first-person walk (Luke, 2026-10-21): no switch to the card board; a card's
page opened from either returns to it (the blueprint comes back when the page's detail-open class goes, unless the walk is on and resumes itself).

The blueprint draws the plan in Alto's own language (feedback: palace style): every wall the same weight, a frosted tube with a white sheen, rounded
where it turns; a door is a gap in the tube; rooms are frosted glass, tinted by the section of the node standing in them; the nodes are numbered pills in
the section's colour. Geometry the plan is unsure of (confidence 0-1) is dashed. Floors are tabs (an "Outside" tab holds the shell, steps, terraces and
entrances). The text of a plan is only ever written with textContent.

SEAMS for later phases — everything a later module needs hangs on `window.AltoBuilding`:

  AltoBuilding.plan                the loaded plan (building_schema format), or null until `ready`
  AltoBuilding.data                the page data: {name, h, url, mode, acts: [{n, c}], nodes: {id: {n: path number, t: title, a: act index,
                                   r: room id, s: anchor id | null}}, order: [node ids]}
  AltoBuilding.ready               a Promise resolved with the plan (rejected with an Error when it cannot be had)
  AltoBuilding.load(plan)          use a plan object directly (tests, previews); mount(data) normally fetches data.url
  AltoBuilding.mount(data)         draw the blueprint over the page (the page calls this once)
  AltoBuilding.show() / hide() / toggle()   the blueprint over the page (hidden only under a card's page, the walk, or a plan that failed to load)
  AltoBuilding.selectLevel(id)     "outside" or a level id;  AltoBuilding.selectRoom(id)  select (and switch level to) a room
  AltoBuilding.enterFPV(roomId, opts)   THE FIRST-PERSON SEAM. Calls the implementation registered by registerFPV, else dispatches the DOM event
                                   'alto-building-fpv' on window (detail {room, opts}) and shows "not available yet". opts: {slot, node, from: "plan"|"link"}
  AltoBuilding.registerFPV(impl)   impl = {enter(roomId, ctx), exit()}; ctx = {plan, data, room, slot, node}. Returns nothing. The implementation is
                                   palace_building_fpv.py's hosted script, fetched from FPV_URL the first time enterFPV runs (enterFPV then returns 'loading')
  AltoBuilding.showWalker(pos)     draw where the first-person walker stood ({l, x, y, yaw, room}: the 'alto-building-fpv-exit' event's detail)
  AltoBuilding.roomOf(nodeId) -> {room, slot} | null;   AltoBuilding.nodesIn(roomId) -> [node ids]
  AltoBuilding.on(event, fn)       events: 'plan' (plan loaded), 'level', 'select', 'fpv'
  AltoBuilding.geometry            pure helpers shared with the FPV: wallSegments(wall) -> [[ [x,y],[x,y], openings-in-segment ]...], centroid(poly),
                                   bounds(plan, level)
"""
from __future__ import annotations

import hashlib as _hashlib
import json as _json

from .markers import MARKERS_CSS, MARKERS_JS
from .palace_assets import loader as _loader
from .palace_building_fpv import FPV_PATH as _FPV_PATH

BUILDING_CSS = r"""
#bldg-root{--bl-ink:rgb(60,64,84);--bl-sheen:rgba(255,255,255,.72);--bl-glass:rgba(255,255,255,.46);--bl-glass-edge:rgba(60,64,84,.22);--bl-paper:var(--bg,#f0efea);
  --bl-muted:var(--text-dim,#6b6f85);--bl-text:var(--text,#1c1e2b);--bl-accent:var(--accent,#7c5cff);--bl-panel:var(--surface,#fff);--bl-line:var(--border,#c8c8d8);
  position:fixed;left:0;right:0;bottom:0;top:var(--bl-top,0px);z-index:30;background:var(--bl-paper);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  color:var(--bl-text);overflow:hidden;touch-action:none;user-select:none;-webkit-user-select:none;}
html.dark #bldg-root{--bl-ink:rgb(208,212,226);--bl-sheen:rgba(255,255,255,.5);--bl-glass:rgba(255,255,255,.07);--bl-glass-edge:rgba(255,255,255,.2);}
#bldg-root[hidden]{display:none;}
#bldg-root svg.bl-svg{position:absolute;inset:0;width:100%;height:100%;display:block;cursor:grab;}
#bldg-root svg.bl-svg.bl-drag{cursor:grabbing;}
#bldg-root .bl-grid{stroke:var(--bl-ink);stroke-opacity:.06;stroke-width:1;vector-effect:non-scaling-stroke;}
#bldg-root .bl-tube,#bldg-root .bl-sheen{fill:none;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke;}
#bldg-root .bl-tube{stroke:var(--bl-ink);stroke-opacity:.92;stroke-width:4.2px;}
#bldg-root .bl-sheen{stroke:var(--bl-sheen);stroke-width:1.43px;}
#bldg-root .bl-tube.bl-guess{stroke-opacity:.5;stroke-dasharray:9 7;}
#bldg-root .bl-sheen.bl-guess{stroke-dasharray:9 7;stroke-opacity:.6;}
#bldg-root .bl-rail{stroke-width:2.2px;stroke-opacity:.7;}
#bldg-root .bl-sheen.bl-rail{stroke-width:.8px;}
#bldg-root .bl-win{fill:none;stroke:var(--bl-paper);stroke-width:2.2px;stroke-linecap:butt;vector-effect:non-scaling-stroke;}
#bldg-root .bl-door{fill:none;stroke:var(--bl-ink);stroke-opacity:.55;stroke-width:1.2px;stroke-linecap:round;vector-effect:non-scaling-stroke;}
#bldg-root .bl-room{fill:var(--bl-glass);stroke:var(--bl-glass-edge);stroke-width:1px;vector-effect:non-scaling-stroke;cursor:pointer;transition:fill .15s;}
#bldg-root .bl-room:hover,#bldg-root .bl-room.bl-sel{fill:color-mix(in srgb,var(--bl-accent) 16%,transparent);stroke:var(--bl-accent);stroke-width:1.6px;}
#bldg-root .bl-room.bl-tint{fill:color-mix(in srgb,var(--bl-tint) 15%,transparent);}
#bldg-root .bl-room.bl-guess{stroke-dasharray:5 4;}
#bldg-root .bl-room.bl-area{fill:color-mix(in srgb,var(--bl-area) 17%,transparent);}
#bldg-root .bl-room.bl-est{fill-opacity:.55;stroke-opacity:.7;}
#bldg-root .bl-room.bl-ov{fill:none;stroke:var(--bl-accent);stroke-width:1.4px;stroke-dasharray:2 3;}
#bldg-root .bl-room.bl-ov.bl-area{fill:color-mix(in srgb,var(--bl-area) 10%,transparent);}
#bldg-root .bl-void{fill:none;stroke:var(--bl-ink);stroke-opacity:.18;stroke-width:1px;vector-effect:non-scaling-stroke;}
#bldg-root .bl-shell{fill:color-mix(in srgb,var(--bl-ink) 7%,transparent);stroke:var(--bl-ink);stroke-opacity:.5;stroke-width:1.4px;vector-effect:non-scaling-stroke;}
#bldg-root .bl-terr{fill:color-mix(in srgb,var(--bl-ink) 4%,transparent);stroke:var(--bl-ink);stroke-opacity:.3;stroke-width:1px;stroke-dasharray:3 3;vector-effect:non-scaling-stroke;}
#bldg-root .bl-step{stroke:var(--bl-ink);stroke-opacity:.45;stroke-width:1px;vector-effect:non-scaling-stroke;fill:none;}
#bldg-root .bl-stair{fill:none;stroke:var(--bl-ink);stroke-opacity:.6;stroke-width:1px;vector-effect:non-scaling-stroke;}
#bldg-root .bl-stair-fill{fill:color-mix(in srgb,var(--bl-ink) 6%,transparent);stroke:var(--bl-ink);stroke-opacity:.55;stroke-width:1px;vector-effect:non-scaling-stroke;}
#bldg-root .bl-ghost{stroke-dasharray:3 3;opacity:.55;}
#bldg-root .bl-col{fill:var(--bl-ink);fill-opacity:.8;stroke:var(--bl-sheen);stroke-width:1px;vector-effect:non-scaling-stroke;}
#bldg-root .bl-fix{fill:color-mix(in srgb,var(--bl-ink) 14%,transparent);stroke:var(--bl-ink);stroke-opacity:.55;stroke-width:1px;vector-effect:non-scaling-stroke;}
#bldg-root .bl-slot{stroke:var(--bl-accent);stroke-width:3px;stroke-linecap:round;vector-effect:non-scaling-stroke;}
#bldg-root .bl-ent{fill:var(--bl-accent);fill-opacity:.9;}
#bldg-root .bl-me{fill:var(--bl-accent);stroke:#fff;stroke-width:2px;vector-effect:non-scaling-stroke;}
#bldg-root .bl-cone{fill:var(--bl-accent);fill-opacity:.22;stroke:none;}
#bldg-root .bl-walk{margin-top:8px;height:28px;font-size:12px;}
#bldg-root .bl-lab{font-size:var(--bl-fs,1px);fill:var(--bl-text);text-anchor:middle;pointer-events:none;font-weight:600;paint-order:stroke;stroke:var(--bl-paper);stroke-width:.25px;stroke-opacity:.8;}
#bldg-root .bl-lab2{font-weight:400;fill:var(--bl-muted);}
#bldg-root .bl-mk{position:absolute;left:0;top:0;width:0;height:0;z-index:1;pointer-events:none;}
#bldg-root .bl-pill{position:absolute;left:0;top:0;height:22px;margin-top:-11px;padding:0 10px;box-sizing:border-box;border-radius:11px;background:var(--bl-tint,var(--bl-accent));
  border:1.2px solid rgba(255,255,255,.85);color:#fff;font-size:12px;font-weight:700;line-height:19.6px;white-space:nowrap;overflow:hidden;pointer-events:auto;cursor:pointer;will-change:transform;}
#bldg-root .bl-pill:hover{border-color:var(--bl-text);}
#bldg-root .bl-pill>span{margin-left:6px;opacity:0;transition:opacity .22s ease;}
#bldg-root .bl-mk.bl-near .bl-pill.bl-t>span{opacity:1;}
#bldg-root .bl-gapfill{stroke:none;pointer-events:none;}
html.bldg-open #world{visibility:hidden !important;}
#bldg-root .bl-ui{position:absolute;z-index:2;pointer-events:auto;}
#bldg-root .bl-tabs{top:14px;right:14px;display:flex;flex-direction:column-reverse;gap:6px;}
/* a phone: the plan's name and floor tabs start below the phone design's MAP, Search and MENU (phone.py, 2026-10-23) */
html.mobile #bldg-root :is(.bl-head,.bl-tabs){top:112px;}
#bldg-root .bl-tab,#bldg-root .bl-btn{font:inherit;font-size:13px;min-width:38px;height:34px;padding:0 12px;border-radius:17px;border:1px solid var(--bl-line);background:color-mix(in srgb,var(--bl-panel) 82%,transparent);
  color:var(--bl-text);cursor:pointer;backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);transition:border-color .15s,color .15s;}
#bldg-root .bl-tab:hover,#bldg-root .bl-btn:hover{border-color:var(--bl-accent);}
#bldg-root .bl-tab.on{border-color:var(--bl-accent);color:var(--bl-accent);font-weight:600;}
#bldg-root .bl-zoom{right:14px;bottom:58px;display:flex;flex-direction:column;gap:6px;}
#bldg-root .bl-zoom .bl-btn{padding:0;width:34px;font-size:17px;line-height:1;}
#bldg-root .bl-head{left:14px;top:14px;max-width:min(360px,calc(100% - 140px));padding:10px 14px;border-radius:14px;border:1px solid var(--bl-line);
  background:color-mix(in srgb,var(--bl-panel) 82%,transparent);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);}
#bldg-root .bl-kind{font-size:11px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--bl-accent);margin-bottom:3px;}
#bldg-root .bl-head h2{margin:0;font-size:15px;font-weight:650;}
#bldg-root .bl-head p{margin:3px 0 0;font-size:12px;color:var(--bl-muted);line-height:1.4;}
#bldg-root .bl-info{left:14px;bottom:58px;width:min(340px,calc(100% - 28px));max-height:46%;overflow:auto;padding:12px 14px;border-radius:14px;border:1px solid var(--bl-line);
  background:color-mix(in srgb,var(--bl-panel) 90%,transparent);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);user-select:text;-webkit-user-select:text;}
#bldg-root .bl-info[hidden]{display:none;}
#bldg-root .bl-info h3{margin:0 0 2px;font-size:14px;}
#bldg-root .bl-info .bl-sub{font-size:12px;color:var(--bl-muted);margin-bottom:8px;}
#bldg-root .bl-info a{color:var(--bl-accent);cursor:pointer;text-decoration:none;}
#bldg-root .bl-info a:hover{text-decoration:underline;}
#bldg-root .bl-info li{margin:3px 0;font-size:13px;list-style:none;}
#bldg-root .bl-info ul{margin:6px 0 8px;padding:0;}
#bldg-root .bl-go{font:inherit;font-size:13px;height:32px;padding:0 14px;border-radius:16px;border:1px solid var(--bl-accent);background:var(--bl-accent);color:#fff;cursor:pointer;}
#bldg-root .bl-note{font-size:12px;color:var(--bl-muted);margin-top:6px;}
#bldg-root .bl-msg{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-align:center;padding:30px;font-size:14px;color:var(--bl-muted);pointer-events:none;}
#bldg-root .bl-foot{left:0;right:0;bottom:2px;z-index:3;text-align:center;font-size:10px;line-height:12px;color:var(--bl-muted);padding:0 8px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;cursor:pointer;}
#bldg-root .bl-foot:hover{color:var(--bl-text);}
#bldg-root .bl-credits{left:14px;right:14px;bottom:22px;max-width:640px;max-height:62%;overflow:auto;padding:12px 14px;border-radius:14px;border:1px solid var(--bl-line);font-size:12px;line-height:1.45;
  background:color-mix(in srgb,var(--bl-panel) 94%,transparent);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);user-select:text;-webkit-user-select:text;}
#bldg-root .bl-credits[hidden]{display:none;}
#bldg-root .bl-credits h3{margin:8px 0 4px;font-size:12px;} #bldg-root .bl-credits h3:first-child{margin-top:0;}
#bldg-root .bl-credits p{margin:3px 0;} #bldg-root .bl-key{display:flex;align-items:center;gap:7px;margin:2px 0;}
#bldg-root .bl-key i{display:inline-block;width:11px;height:11px;border-radius:3px;flex:none;}
@media print{#bldg-root{display:none !important;}}
@media (max-width:700px){#bldg-root .bl-head{max-width:calc(100% - 128px);}#bldg-root .bl-info{bottom:62px;}}
"""

_UNUSED_ICON = ('<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="vertical-align:-2px;margin-right:5px">'
                   '<path d="M3 9.5 12 4l9 5.5"/><path d="M5.5 10.5v7.5M9.5 10.5v7.5M14.5 10.5v7.5M18.5 10.5v7.5"/><path d="M3 20.5h18"/></svg>')

BUILDING_JS = r"""
(function(){
if(window.AltoBuilding) return;
var NS='http://www.w3.org/2000/svg';
var MUSEUM_ICON='<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="vertical-align:-2px;margin-right:5px"><path d="M3 9.5 12 4l9 5.5"/><path d="M5.5 10.5v7.5M9.5 10.5v7.5M14.5 10.5v7.5M18.5 10.5v7.5"/><path d="M3 20.5h18"/></svg>';
var A={version:1, plan:null, data:null, ready:null, geometry:{}}, ev={}, fpvImpl=null;
var S={root:null, svg:null, view:null, geo:null, rot:0, axis:null, level:'outside', sel:null, vb:null, home:null, info:null, tabs:null, head:null, msg:null, mo:null, nodesByRoom:{}, drag:null, pts:{}};

function on(e,f){ (ev[e]=ev[e]||[]).push(f); }
function emit(e,d){ (ev[e]||[]).slice().forEach(function(f){ try{ f(d); }catch(x){} }); }
A.on=on;
function el(t,a,p){ var n=document.createElementNS(NS,t); if(a) for(var k in a) n.setAttribute(k,a[k]); if(p) p.appendChild(n); return n; }
function h(t,a,p,txt){ var n=document.createElement(t); if(a) for(var k in a) n.setAttribute(k,a[k]); if(txt!=null) n.textContent=txt; if(p) p.appendChild(n); return n; }
function dec(s){ var t=document.createElement('textarea'); t.innerHTML=s==null?'':String(s); return t.value; }
function f2(v){ return Math.round(v*100)/100; }
// plan metres (x east, y north) -> svg (y flipped); the drawing group is then turned by S.rot degrees (orient), and V() gives a point's place after the turn
function P(p){ return f2(p[0])+','+f2(-p[1]); }
function V(p){ var X=p[0], Y=-p[1], a=S.rot*Math.PI/180, c=Math.cos(a), s=Math.sin(a); return [X*c-Y*s, X*s+Y*c]; }
/* the blueprint is turned so the main entrance faces the viewer (bottom of the screen): a symmetrical front then lies level, its wings
   spread left and right, its axis upright; S.axis is that axis on screen, used to centre the view. Labels and chips stay upright (drawn unturned at V()). */
function orient(plan){
  S.rot=0; S.axis=null;
  var ens=(plan.en||[]).filter(function(e){ return e.k==='main'&&e.fc!=null&&e.p; }), sp=plan.sp;
  var en=(sp&&ens.filter(function(e){ return e.l===sp.l; })[0])||ens[0]; if(!en) return;
  S.rot=((90+en.fc)%360+360)%360; S.axis=V(en.p)[0];
}
function screenBounds(lv){ // the level's extent on screen, widened to sit even about the entrance axis when the building is (nearly) symmetrical
  var b=A.geometry.bounds(A.plan,lv==='outside'?null:lv)||A.geometry.bounds(A.plan,null)||[0,0,10,10];
  var q=[[b[0],b[1]],[b[2],b[1]],[b[2],b[3]],[b[0],b[3]]].map(V), xs=q.map(function(p){ return p[0]; }), ys=q.map(function(p){ return p[1]; });
  var x0=Math.min.apply(null,xs), x1=Math.max.apply(null,xs), y0=Math.min.apply(null,ys), y1=Math.max.apply(null,ys);
  if(S.axis!=null){ var hw=Math.max(S.axis-x0,x1-S.axis); if(2*hw<=(x1-x0)*1.25){ x0=S.axis-hw; x1=S.axis+hw; } }
  return [x0,y0,x1,y1];
}
function pathOf(pts,loop){ var d='M'+P(pts[0]); for(var i=1;i<pts.length;i++) d+='L'+P(pts[i]); return d+(loop?'Z':''); }

// ── geometry shared with the first-person view ──
function plen(pts,loop){ var s=0,n=pts.length; for(var i=0;i<(loop?n:n-1);i++){ var a=pts[i], b=pts[(i+1)%n]; s+=Math.hypot(b[0]-a[0],b[1]-a[1]); } return s; }
// [start,end] metres along a wall's centre line -> the points of that stretch
function stretch(pts,loop,t0,t1){
  var n=pts.length, out=[], run=0, m=loop?n:n-1;
  for(var i=0;i<m;i++){
    var a=pts[i], b=pts[(i+1)%n], L=Math.hypot(b[0]-a[0],b[1]-a[1]);
    if(L<1e-9) continue;
    var s0=run, s1=run+L;
    if(s1>t0+1e-9 && s0<t1-1e-9){
      var u0=Math.max(t0,s0), u1=Math.min(t1,s1);
      var p0=[a[0]+(b[0]-a[0])*(u0-s0)/L, a[1]+(b[1]-a[1])*(u0-s0)/L], p1=[a[0]+(b[0]-a[0])*(u1-s0)/L, a[1]+(b[1]-a[1])*(u1-s0)/L];
      if(!out.length) out.push(p0); else { var q=out[out.length-1]; if(Math.hypot(q[0]-p0[0],q[1]-p0[1])>1e-6) out.push(p0); }
      out.push(p1);
    }
    run=s1;
  }
  return out;
}
function pointAt(pts,loop,t){ var s=stretch(pts,loop,Math.max(0,t-1e-4),t+1e-4); if(s.length<2) return {p:pts[0],ang:0}; var a=s[0], b=s[s.length-1]; return {p:[(a[0]+b[0])/2,(a[1]+b[1])/2], ang:Math.atan2(b[1]-a[1],b[0]-a[0])}; }
// a wall as solid stretches between its door-like openings: [{pts, ...}], plus the openings with their place
A.geometry.wallSegments=function(w){
  var L=plen(w.p,!!w.loop), gaps=[], wins=[], doors=[];
  (w.o||[]).forEach(function(o){
    var a0=Math.max(0,o.a-o.w/2), a1=Math.min(L,o.a+o.w/2);
    if(o.k==='window'){ wins.push([a0,a1,o]); }
    else { gaps.push([a0,a1,o]); doors.push([a0,a1,o]); }
  });
  gaps.sort(function(x,y){ return x[0]-y[0]; });
  var segs=[], cur=0;
  gaps.forEach(function(g){ if(g[0]>cur+1e-6) segs.push([cur,g[0]]); cur=Math.max(cur,g[1]); });
  if(cur<L-1e-6) segs.push([cur,L]);
  return {length:L, solid:segs.map(function(s){ return stretch(w.p,!!w.loop,s[0],s[1]); }).filter(function(p){ return p.length>1; }),
          windows:wins.map(function(g){ return {pts:stretch(w.p,!!w.loop,g[0],g[1]), o:g[2]}; }),
          doors:doors.map(function(g){ return {pts:stretch(w.p,!!w.loop,g[0],g[1]), o:g[2], at:pointAt(w.p,!!w.loop,(g[0]+g[1])/2)}; })};
};
function centroid(poly){
  var a=0,cx=0,cy=0,n=poly.length;
  for(var i=0;i<n;i++){ var p=poly[i], q=poly[(i+1)%n], c=p[0]*q[1]-q[0]*p[1]; a+=c; cx+=(p[0]+q[0])*c; cy+=(p[1]+q[1])*c; }
  if(Math.abs(a)<1e-9) return poly[0];
  var g=[cx/(3*a), cy/(3*a)];
  return inside(poly,g)?g:interior(poly);
}
function inside(poly,p){ var c=false; for(var i=0,n=poly.length;i<n;i++){ var a=poly[i], b=poly[(i+1)%n]; if((a[1]>p[1])!==(b[1]>p[1]) && p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]) c=!c; } return c; }
function interior(poly){ // a point inside a concave polygon: the widest horizontal chord through the middle of its height
  var y0=Infinity,y1=-Infinity; poly.forEach(function(p){ y0=Math.min(y0,p[1]); y1=Math.max(y1,p[1]); });
  var best=poly[0], bw=-1;
  for(var k=1;k<8;k++){
    var y=y0+(y1-y0)*k/8, xs=[];
    for(var i=0,n=poly.length;i<n;i++){ var a=poly[i], b=poly[(i+1)%n]; if((a[1]>y)!==(b[1]>y)) xs.push(a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1])); }
    xs.sort(function(p,q){ return p-q; });
    for(var j=0;j+1<xs.length;j+=2){ if(xs[j+1]-xs[j]>bw){ bw=xs[j+1]-xs[j]; best=[(xs[j]+xs[j+1])/2,y]; } }
  }
  return best;
}
A.geometry.centroid=centroid;
A.geometry.bounds=function(plan,level){
  var x0=Infinity,y0=Infinity,x1=-Infinity,y1=-Infinity;
  function take(pts){ (pts||[]).forEach(function(p){ x0=Math.min(x0,p[0]); y0=Math.min(y0,p[1]); x1=Math.max(x1,p[0]); y1=Math.max(y1,p[1]); }); }
  (plan.wl||[]).forEach(function(w){ if(!level||w.l===level) take(w.p); });
  (plan.rm||[]).forEach(function(r){ if(!level||r.l===level) take(r.p); });
  if(!level||level==='outside'){ var ex=plan.ex||{}; (ex.sh||[]).forEach(function(s){ take(s.p); }); (ex.stp||[]).forEach(function(s){ take(s.p); }); (ex.tr||[]).forEach(function(s){ take(s.p); }); }
  return x0===Infinity?null:[x0,y0,x1,y1];
};

// ── drawing ──
function conf(plan,e){ return e.c!=null?e.c:(plan.c!=null?plan.c:1); }
function tubes(parent,pts,cls,loop){
  var d=pathOf(pts,loop);
  el('path',{d:d,'class':'bl-tube '+cls},parent); el('path',{d:d,'class':'bl-sheen '+cls},parent);
}
function areaOf(r){ var l=A.plan&&A.plan.ca; if(!r.ca||!l) return null; for(var i=0;i<l.length;i++) if(l[i].id===r.ca) return l[i]; return null; }
function levelOf(id){ var l=A.plan.lv; for(var i=0;i<l.length;i++) if(l[i].id===id) return l[i]; return null; }
function tintOf(nodeIds){ var d=A.data; if(!nodeIds||!nodeIds.length||!d||!d.acts) return null; var n=d.nodes[nodeIds[0]]; var a=n&&d.acts[n.a]; return a&&a.c||null; }

function drawLevel(g,id){
  var plan=A.plan, d=A.data;
  var rooms=(plan.rm||[]).filter(function(r){ return r.l===id; });
  var gR=el('g',{},g), gW=el('g',{},g), gX=el('g',{},g), gL=el('g',{},S.view);
  var fs=Math.max(.4,Math.min(.9,Math.sqrt(plan._area||200)/30));
  S.view.style.setProperty('--bl-fs',fs+'px');
  rooms.forEach(function(r){
    var nodes=S.nodesByRoom[r.id]||[], tint=tintOf(nodes.map(function(n){ return n.id; }));
    var c=conf(plan,r), ar=areaOf(r);
    if(r.gp){ el('path',{d:pathOf(r.p,true),'class':'bl-room bl-gapfill'},gR); return; }
    var p=el('path',{d:pathOf(r.p,true),'class':'bl-room'+(c<=1?' bl-guess':'')+(c<=0?' bl-est':'')+(r.ov?' bl-ov':'')+(ar?' bl-area':''),'data-room':r.id},gR);
    if(ar) p.style.setProperty('--bl-area',ar.c);
    if(c<=0) p.setAttribute('filter','url(#bl-feather)');
    if(tint){ p.setAttribute('class',p.getAttribute('class')+' bl-tint'); p.style.setProperty('--bl-tint',tint); }
    p.addEventListener('click',function(e){ if(S.moved) return; e.stopPropagation(); A.selectRoom(r.id); });
  });
  // walls
  (plan.wl||[]).filter(function(w){ return w.l===id; }).forEach(function(w){
    var guess=conf(plan,w)<=1?' bl-guess':'', rail=w.k==='rail'?' bl-rail':'';
    var gm=A.geometry.wallSegments(w);
    gm.solid.forEach(function(pts){ tubes(gW,pts,guess+rail,false); });
    if(w.loop && gm.solid.length===1 && !(w.o||[]).some(function(o){ return o.k!=='window'; })) { /* closed, unbroken: drawn as a loop below */ }
    gm.windows.forEach(function(x){ if(x.pts.length>1) el('path',{d:pathOf(x.pts,false),'class':'bl-win'},gW); });
    gm.doors.forEach(function(x){ if(x.o.k==='door' && x.o.d!=='none' && x.pts.length>1){ var a=x.pts[0], b=x.pts[x.pts.length-1];
      el('path',{d:'M'+P(a)+'L'+P(b),'class':'bl-door'},gW); } });
  });
  // vertical links
  (plan.st||[]).forEach(function(s){
    var ghost=s.to===id, here=s.from===id; if(!here&&!ghost) return;
    var poly=s.fp, gs=el('g',{'class':ghost?'bl-ghost':''},gX);
    el('path',{d:pathOf(poly,true),'class':'bl-stair-fill'},gs);
    var c=centroid(poly);
    if(s.k==='elevator'){ var bb=ptsBounds(poly); el('path',{d:'M'+P([bb[0],bb[1]])+'L'+P([bb[2],bb[3]])+'M'+P([bb[0],bb[3]])+'L'+P([bb[2],bb[1]]),'class':'bl-stair'},gs); }
    else {
      var ang=(s.up!=null?s.up:90)*Math.PI/180, ux=Math.cos(ang), uy=Math.sin(ang), vx=-uy, vy=ux, mn=Infinity, mx=-Infinity, vn=Infinity, vm=-Infinity;
      poly.forEach(function(p){ var u=p[0]*ux+p[1]*uy, v=p[0]*vx+p[1]*vy; mn=Math.min(mn,u); mx=Math.max(mx,u); vn=Math.min(vn,v); vm=Math.max(vm,v); });
      var n=Math.max(2,Math.min(s.n||12,18));
      for(var i=1;i<n;i++){ var u=mn+(mx-mn)*i/n; if(!insideBand(poly,ux,uy,u)) continue;
        el('path',{d:'M'+P([u*ux+vn*vx,u*uy+vn*vy])+'L'+P([u*ux+vm*vx,u*uy+vm*vy]),'class':'bl-step','clip-path':''},gs); }
      var v0=(vn+vm)/2, a0=[mn*ux+v0*vx,mn*uy+v0*vy], a1=[mx*ux+v0*vx,mx*uy+v0*vy];
      el('path',{d:'M'+P(a0)+'L'+P(a1)+'M'+P([a1[0]-ux*.8+vx*.5,a1[1]-uy*.8+vy*.5])+'L'+P(a1)+'L'+P([a1[0]-ux*.8-vx*.5,a1[1]-uy*.8-vy*.5]),'class':'bl-stair'},gs);
    }
  });
  (plan.cols||[]).filter(function(c){ return c.l===id; }).forEach(function(c){
    if(c.r!=null) el('circle',{cx:f2(c.p[0]),cy:f2(-c.p[1]),r:c.r,'class':'bl-col'},gX);
    else el('rect',{x:f2(c.p[0]-c.sz[0]/2),y:f2(-c.p[1]-c.sz[1]/2),width:c.sz[0],height:c.sz[1],'class':'bl-col'},gX);
  });
  (plan.fx||[]).filter(function(f){ return f.l===id; }).forEach(function(f){
    var r=el('rect',{x:f2(-f.sz[0]/2),y:f2(-f.sz[1]/2),width:f.sz[0],height:f.sz[1],rx:.12,'class':'bl-fix',transform:'translate('+f2(f.p[0])+','+f2(-f.p[1])+') rotate('+(-(f.rot||0))+')'},gX);
    if(f.n){ var t=el('title',{},r); t.textContent=f.n; }
  });
  (plan.sl||[]).forEach(function(s){
    var room=(plan.rm||[]).filter(function(r){ return r.id===s.rm; })[0]; if(!room||room.l!==id) return;
    var a=(s.fc+180)*Math.PI/180, hw=s.sz[0]/2, tx=-Math.sin(a), ty=Math.cos(a); // along the wall = perpendicular to the facing
    el('path',{d:'M'+P([s.p[0]-tx*hw,s.p[1]-ty*hw])+'L'+P([s.p[0]+tx*hw,s.p[1]+ty*hw]),'class':'bl-slot'},gX);
  });
  // labels, then the numbered pills
  rooms.forEach(function(r){
    if(r.gp) return; var c=V(centroid(r.p)), bb=ptsBounds(r.p.map(V)), w=bb[2]-bb[0];
    var many=(S.nodesByRoom[r.id]||[]).length;
    if(w<fs*3) return;
    var up=many?1.7:0;                    // a room with cards: its name stands above them
    var t=el('text',{x:f2(c[0]),y:f2(c[1]-up),'class':'bl-lab'},gL); t.textContent=dec(r.n);
    if(r.no){ var t2=el('text',{x:f2(c[0]),y:f2(c[1]-up+fs*1.25),'class':'bl-lab bl-lab2'},gL); t2.textContent=dec(r.no); }
  });
  (plan.en||[]).filter(function(e){ return e.l===id; }).forEach(function(e){ entranceMark(gX,e); });
}
function ptsBounds(pts){ var x0=Infinity,y0=Infinity,x1=-Infinity,y1=-Infinity; pts.forEach(function(p){ x0=Math.min(x0,p[0]); y0=Math.min(y0,p[1]); x1=Math.max(x1,p[0]); y1=Math.max(y1,p[1]); }); return [x0,y0,x1,y1]; }
function insideBand(poly,ux,uy,u){ return true; }
function entranceMark(g,e){
  var a=e.fc*Math.PI/180, ux=Math.cos(a), uy=Math.sin(a), vx=-uy, vy=ux, p=e.p, s=Math.max(.9,(e.w||2)*.45);
  var tip=[p[0]+ux*s*1.7,p[1]+uy*s*1.7], l=[p[0]+ux*s*.5+vx*s*.7,p[1]+uy*s*.5+vy*s*.7], r=[p[0]+ux*s*.5-vx*s*.7,p[1]+uy*s*.5-vy*s*.7];
  var n=el('path',{d:'M'+P(tip)+'L'+P(l)+'L'+P([p[0]+ux*s*.9,p[1]+uy*s*.9])+'L'+P(r)+'Z','class':'bl-ent'},g); var t=el('title',{},n); t.textContent=dec(e.n||'Entrance');
}
/* the numbered chips (1.9.145, markers.py): an HTML layer over the drawing, each chip pinned to its anchor and one size on the screen.
   While a zoom or pan runs a chip only follows its anchor (a transform); where it stands beside a crowded anchor and whether it
   shows its title are decided once the gesture settles, held (a chip keeps its place while that is free; the title shows below
   .125 m per px and goes above .14) and glide. Anchors are screen-frame drawing coordinates (after the turn). */
function drawPills(levelId){
  var plan=A.plan, mk=S.mk; while(mk.firstChild) mk.removeChild(mk.firstChild); S.chips=[];
  (plan.rm||[]).filter(function(r){ return r.l===levelId&&!r.gp; }).forEach(function(r){
    var list=S.nodesByRoom[r.id]||[]; if(!list.length) return;
    var c=centroid(r.p);
    list.forEach(function(n,i){
      var pos=n.s?anchorPoint(n.s):null, q=V(pos||c);
      var title=dec(n.t); if(title.length>26) title=title.slice(0,25)+'…';
      var pill=h('div',{'class':'bl-pill alto-mk','data-node':n.id,role:'button',title:n.n+'  '+dec(n.t)},mk);
      h('b',null,pill,String(n.n)); h('span',null,pill,title);
      var col=A.data.acts&&A.data.acts[n.a]&&A.data.acts[n.a].c; if(col) pill.style.setProperty('--bl-tint',col);
      pill._n=n; pill._a=q; pill._o=[0,0]; S.chips.push(pill);
      pill.addEventListener('click',function(e){ if(S.moved) return; e.stopPropagation(); openNode(n.id); });
    });
  });
  S.mkLay=null; layoutPills(false);
}
function measurePills(){ // each chip's width with the number alone and with its title (once, while the blueprint shows)
  if(!S.chips.length||S.chips[0]._wF||!S.root.clientWidth) return;
  S.chips.forEach(function(p){ p.style.width='auto'; });
  S.chips.forEach(function(p){ var b=p.firstChild.offsetWidth, t=p.lastChild.offsetWidth; p._wF=Math.ceil(Math.max(32,b+22.4)); p._wT=Math.ceil(Math.min(250,b+t+28.4)); });
  S.chips.forEach(function(p){ p.style.width=''; });
}
function scr(){ var W=S.root.clientWidth||1, s=W/S.vb[2]; return {s:s, x:-S.vb[0]*s, y:-S.vb[1]*s}; }   // drawing units -> the root's px
function movePills(){ // every frame of a zoom or pan: each chip follows its anchor, nothing else changes (its left edge is the number's, so a title only grows rightwards)
  if(!S.chips||!S.vb) return; var t=scr();
  S.chips.forEach(function(p){ AltoMarkers.at(p, p._a[0]*t.s+t.x+p._o[0]-(p._wF||32)/2, p._a[1]*t.s+t.y+p._o[1]); });
}
function layoutPills(glide){ // once a gesture settles: the places of the numbers (held), then which titles have room, then a glide to them
  if(!S.chips||!S.vb||!S.root.clientWidth) return; measurePills();
  var k=S.vb[2]/S.root.clientWidth, key=Math.round(Math.log(k)*40)+':'+S.chips.length;
  if(key===S.mkLay){ movePills(); return; } S.mkLay=key;
  var near=S.near=AltoMarkers.band(S.near, -k, -.14, -.125), t=scr(), H=24, gap=3, sl=3;
  var hx=S.home&&[S.home[0]*t.s+t.x, (S.home[0]+S.home[2])*t.s+t.x];
  S.mk.classList.toggle('bl-near', near);
  // placed by the number alone, so a title showing or not never moves a chip (titles once widened every chip and re-laid the lot: up to 233 px)
  var items=S.chips.map(function(p){ var w=p._wF||32, W=w+gap, c=[[0,0]];
    for(var r=1;r<7;r++) c.push([0,r*H],[0,-r*H],[W,0],[-W,0],[W,r*H],[-W,-r*H],[W,-r*H],[-W,r*H]);
    return {id:p._n.id, x:p._a[0]*t.s+t.x, y:p._a[1]*t.s+t.y, w:w, h:H-2, c:c}; });
  S.mkSt=S.mkSt||{};
  var at=AltoMarkers.place(items, S.mkSt, {gap:gap, ok:function(x,y,w){ return !hx||(x-w/2>=hx[0]&&x+w/2<=hx[1]); }});   // pushed aside, a chip stays over the building's width
  var box=items.map(function(m){ var o=at[m.id]; return [m.x+o.dx-m.w/2, m.y+o.dy, m.w, m.h]; });   // [left, centre y, w, h]
  function clear(i, x, w, s){ var b=box[i]; for(var j=0;j<box.length;j++){ if(j===i) continue; var c=box[j];
    if(x<c[0]+c[2]+gap-s && c[0]<x+w+gap-s && Math.abs(b[1]-c[1])<(b[3]+c[3])/2+gap-s) return false; } return true; }
  S.chips.forEach(function(p, i){ var o=at[p._n.id], wF=p._wF||32, wT=Math.max(wF, p._wT||wF), on=near&&wT>wF&&clear(i, box[i][0], wT, p._tOn?sl:-sl);   // a title shown keeps its room within the slack
    p._tOn=on; if(on) box[i][2]=wT; p._o1=[o.dx,o.dy]; p._w1=on?wT:wF; p._o0=p._o; p._w0=p._w||p._w1; p.classList.toggle('bl-t', on); });
  if(!glide){ step(1); return; }
  AltoMarkers.glide(S.mk, step);
  function step(k){ // where each chip is k of the way from where it stood to its new place (and width); its anchor read afresh each frame
    S.chips.forEach(function(p){ var w=p._w0+(p._w1-p._w0)*k; p._o=[p._o0[0]+(p._o1[0]-p._o0[0])*k, p._o0[1]+(p._o1[1]-p._o0[1])*k];
      w=Math.round(w*10)/10; if(w!==p._w){ p._w=w; p.style.width=w+'px'; } });
    movePills(); }
}
function anchorPoint(id){ var s=(A.plan.sl||[]).concat(A.plan.fx||[]); for(var i=0;i<s.length;i++) if(s[i].id===id) return s[i].p; return null; }

function drawOutside(g){
  var plan=A.plan, ex=plan.ex||{};
  (ex.tr||[]).forEach(function(t){ var p=el('path',{d:pathOf(t.p,true),'class':'bl-terr'},g); var ti=el('title',{},p); ti.textContent=dec(t.n||'Terrace'); });
  (ex.stp||[]).forEach(function(s){
    el('path',{d:pathOf(s.p,true),'class':'bl-terr'},g);
    var ang=(s.up!=null?s.up:90)*Math.PI/180, ux=Math.cos(ang), uy=Math.sin(ang), vx=-uy, vy=ux, mn=Infinity,mx=-Infinity,vn=Infinity,vm=-Infinity;
    s.p.forEach(function(p){ var u=p[0]*ux+p[1]*uy, v=p[0]*vx+p[1]*vy; mn=Math.min(mn,u); mx=Math.max(mx,u); vn=Math.min(vn,v); vm=Math.max(vm,v); });
    var n=Math.max(2,Math.min(s.n||6,24));
    for(var i=1;i<n;i++){ var u=mn+(mx-mn)*i/n; el('path',{d:'M'+P([u*ux+vn*vx,u*uy+vn*vy])+'L'+P([u*ux+vm*vx,u*uy+vm*vy]),'class':'bl-step'},g); }
  });
  (ex.sh||[]).forEach(function(s){ var p=el('path',{d:pathOf(s.p,true),'class':'bl-shell'},g); });
  (ex.sh||[]).forEach(function(s){ tubes(g,s.p,conf(plan,s)<=1?' bl-guess':'',true); });
  (plan.en||[]).forEach(function(e){ entranceMark(g,e); });
}

function render(){
  if(!A.plan||!S.svg) return;
  var view=S.view; while(view.firstChild) view.removeChild(view.firstChild);
  var lv=S.level;
  S.geo=el('g',S.rot?{transform:'rotate('+f2(S.rot)+')'}:{},view);
  if(lv==='outside') drawOutside(S.geo); else drawLevel(S.geo,lv);
  var bb=screenBounds(lv);
  if(!S.home){ var m=Math.max(bb[2]-bb[0],bb[3]-bb[1])*(S.root.clientWidth<700?.02:.12)+2; S.home=[bb[0]-m,bb[1]-m,(bb[2]-bb[0])+2*m,(bb[3]-bb[1])+2*m]; }
  if(!S.vb) fit();
  if(lv==='outside'){ S.chips=[]; while(S.mk.firstChild) S.mk.removeChild(S.mk.firstChild); }
  applyVB(); if(lv!=='outside') drawPills(lv);
  [].forEach.call(S.tabs.children,function(b){ b.classList.toggle('on',b.getAttribute('data-level')===lv); });
  if(S.sel){ var r=S.svg.querySelector('[data-room="'+S.sel+'"]'); if(r) r.classList.add('bl-sel'); }
  drawWalker();
}
function fit(){ // the home box centred in the free part of the screen: on a phone the header card spans the top, the tool bar the bottom, the side rail the right (an equal gutter left keeps it centred)
  var h0=S.home, r=S.root.getBoundingClientRect(), W=r.width, H=r.height; S.vb=h0.slice(); if(W<1||H<1) return;
  var top=0, bot=H, side=0, hb=S.head&&S.head.getBoundingClientRect();
  if(hb&&hb.height&&hb.width>W*.6) top=Math.max(0,hb.bottom-r.top+6);
  if(W<700){ bot=H-58; side=30; }
  if(bot-top<H*.4){ top=0; bot=H; }
  var s=Math.min((W-2*side)/h0[2],(bot-top)/h0[3]), cx=h0[0]+h0[2]/2, cy=h0[1]+h0[3]/2;
  S.vb=[cx-W/2/s, cy-(top+bot)/2/s, W/s, H/s];
}
function applyVB(){ // keep the drawing's aspect equal to the viewport's
  if(!S.vb||!S.svg) return;
  var r=S.root.getBoundingClientRect(), W=Math.max(1,r.width), H=Math.max(1,r.height), vb=S.vb, asp=W/H;
  var w=vb[2], hh=vb[3];
  if(w/hh<asp){ var nw=hh*asp; vb[0]-=(nw-w)/2; vb[2]=nw; } else { var nh=w/asp; vb[1]-=(nh-hh)/2; vb[3]=nh; }
  S.svg.setAttribute('viewBox',vb.map(function(v){ return Math.round(v*1e4)/1e4; }).join(' '));
  if(S.mkSet){ AltoMarkers.stop(S.mk); S.mkSet.poke(); movePills(); } else layoutPills(false);
}

// ── panel ──
function nodesIn(roomId){ return (S.nodesByRoom[roomId]||[]).map(function(n){ return n.id; }); }
A.nodesIn=nodesIn;
A.roomOf=function(id){ var n=A.data&&A.data.nodes&&A.data.nodes[id]; return n&&n.r?{room:n.r,slot:n.s||null}:null; };
function roomById(id){ var l=A.plan.rm||[]; for(var i=0;i<l.length;i++) if(l[i].id===id) return l[i]; return null; }
function openNode(id){ if(typeof window.showDetail==='function'){ A.hide(); try{ window.showDetail('node',id); }catch(x){} } }
function info(r){
  var box=S.info; while(box.firstChild) box.removeChild(box.firstChild);
  if(!r){ box.hidden=true; return; }
  box.hidden=false;
  var lv=levelOf(r.l);
  h('h3',null,box,dec(r.n)+(r.no?'  ·  '+dec(r.no):''));
  h('div',{'class':'bl-sub'},box,(lv?dec(lv.n):'')+(r.ty?' · '+r.ty:'')+(conf(A.plan,r)<=0?' · estimated':conf(A.plan,r)<=1?' · approximate':''));
  var ar=areaOf(r); if(ar) h('div',{'class':'bl-note'},box,dec(ar.n));
  if(r.x28){ var ch={no:'Layout as drawn in 1928; little changed since.',partly:'1928 layout, partly changed since.',likely:'1928 layout; probably re-partitioned since.',yes:'1928 layout; changed since (rebuilt or converted).',"new":'Not on the 1928 plans: a modern space placed from published dimensions.'}[r.x28]; if(ch) h('div',{'class':'bl-note'},box,ch); }
  if(r.nt) h('div',{'class':'bl-note'},box,dec(r.nt));
  if(!r.no&&r.cand&&r.cand.length) h('div',{'class':'bl-note'},box,'Galleries here today (unresolved): '+r.cand.join(', ')+'.');
  var list=S.nodesByRoom[r.id]||[];
  if(list.length){
    var ul=h('ul',null,box);
    list.forEach(function(n){ var li=h('li',null,ul), a=h('a',null,li,n.n+'  '+dec(n.t)); a.addEventListener('click',function(){ openNode(n.id); }); });
  } else h('div',{'class':'bl-note'},box,'No card stands here yet.');
  var go=h('button',{'class':'bl-go',type:'button'},box,'Walk in'); go.addEventListener('click',function(){ A.enterFPV(r.id,{from:'plan'}); });
  S.fpvNote=h('div',{'class':'bl-note'},box,'');
}

// ── public ──
A.selectLevel=function(id){
  if(id!=='outside' && !levelOf(id)) return;
  S.level=id; S.home=null; S.vb=null; S.sel=null; info(null); render(); emit('level',id);
};
A.selectRoom=function(id){
  var r=roomById(id); if(!r) return;
  if(S.level!==r.l){ S.level=r.l; S.home=null; S.vb=null; }
  S.sel=id; render(); info(r); emit('select',id);
};
A.enterFPV=function(roomId,opts){
  opts=opts||{};
  var ctx={plan:A.plan,data:A.data,room:roomId,slot:opts.slot||null,node:opts.node||null,from:opts.from||'link'};
  emit('fpv',ctx);
  if(fpvImpl && typeof fpvImpl.enter==='function'){ try{ return fpvImpl.enter(roomId,ctx); }catch(x){ } }
  if(!fpvImpl && FPV_URL && !S.fpvTried && A.plan){         // the first-person view is its own hosted script, fetched the first time someone walks in
    S.fpvTried=1; if(S.fpvNote) S.fpvNote.textContent='Opening the first-person view\u2026';
    var get=function(){ return fetch(FPV_URL,{credentials:'same-origin'}).then(function(r){ if(!r.ok) throw new Error('HTTP '+r.status); return r.text(); }); };
    get().catch(function(){ return new Promise(function(ok){ setTimeout(ok,1200); }).then(get); }).then(function(t){          // one retry: a dropped request is not a missing file
      var sc=document.createElement('script'); sc.text=t; (document.head||document.documentElement).appendChild(sc); if(sc.parentNode) sc.parentNode.removeChild(sc);
      if(S.fpvNote) S.fpvNote.textContent=''; if(fpvImpl) A.enterFPV(roomId,opts); else noFPV(roomId,opts);
    }).catch(function(){ noFPV(roomId,opts); });
    return 'loading';
  }
  noFPV(roomId,opts);
  return false;
};
function noFPV(roomId,opts){
  try{ window.dispatchEvent(new CustomEvent('alto-building-fpv',{detail:{room:roomId,opts:opts}})); }catch(x){}
  if(S.fpvNote) S.fpvNote.textContent='The first-person view is not available yet.';
}
// where the walker stood when the first-person view closed: a dot with a view cone on that level's plan
A.showWalker=function(pos){ if(!pos||!A.plan) return; A.walker=pos; if(pos.l&&levelOf(pos.l)&&S.level!==pos.l){ S.level=pos.l; S.home=null; S.vb=null; render(); } else drawWalker(); if(pos.room) { S.sel=pos.room; var r=roomById(pos.room); render(); if(r) info(r); } };
function drawWalker(){ var g=S.svg&&S.svg.querySelector('.bl-walker'); if(g) g.remove(); var w=A.walker; if(!w||!S.view||S.level!==w.l) return;
  var a=(w.yaw||0)*Math.PI/180, x=w.x, y=w.y, c=Math.cos(a), s=Math.sin(a), L=3.2, sp=.55;
  g=el('g',{'class':'bl-walker','pointer-events':'none'},S.geo||S.view);
  el('path',{d:'M'+P([x,y])+'L'+P([x+L*Math.cos(a-sp),y+L*Math.sin(a-sp)])+'A'+L+' '+L+' 0 0 0 '+P([x+L*Math.cos(a+sp),y+L*Math.sin(a+sp)])+'Z','class':'bl-cone'},g);
  el('circle',{cx:f2(x),cy:f2(-y),r:.55,'class':'bl-me'},g); }
window.addEventListener('alto-building-fpv-pos',function(e){ A.walker=e.detail; });
window.addEventListener('alto-building-fpv-exit',function(e){ A.walker=e.detail; });
A.registerFPV=function(impl){ fpvImpl=impl||null; };
A.show=function(){ if(S.root){ S.root.hidden=false; setTop(); applyVB(); } document.documentElement.classList.add('bldg-open'); };
A.hide=function(){ if(S.root) S.root.hidden=true; document.documentElement.classList.remove('bldg-open'); };
function walking(){ try{ var f=window.AltoBuildingFPV, st=f&&f.state(); return !!(st&&st.on); }catch(x){ return false; } }
function watchDetail(){ // a card's page closed: back to the blueprint (the walk, when on, takes itself back)
  var de=document.documentElement, was=de.classList.contains('detail-open');
  S.mo=new MutationObserver(function(){ var o=de.classList.contains('detail-open'); if(was&&!o&&A.plan&&S.root&&S.root.hidden&&!walking()) A.show(); was=o; });
  S.mo.observe(de,{attributes:true,attributeFilter:['class']});
}
A.toggle=function(){ if(S.root&&S.root.hidden) A.show(); else A.hide(); };
A.load=function(plan){
  A.plan=plan; orient(plan);
  var bb=A.geometry.bounds(plan,null)||[0,0,10,10]; plan._area=(bb[2]-bb[0])*(bb[3]-bb[1]);
  index(); emit('plan',plan); build();
};
function index(){
  S.nodesByRoom={}; var d=A.data; if(!d||!d.nodes) return;
  (d.order||Object.keys(d.nodes)).forEach(function(id){ var n=d.nodes[id]; if(!n||!n.r) return; (S.nodesByRoom[n.r]=S.nodesByRoom[n.r]||[]).push({id:id,n:n.n,t:n.t,a:n.a,s:n.s||null}); });
}
function setTop(){ // under the page's title bar and nav, which settle (slide in) a moment after load
  if(!S.root) return;
  var top=0; ['title-bar','nav'].forEach(function(id){ var e=document.getElementById(id); if(!e) return; var b=e.getBoundingClientRect(); if(b.height>0&&b.height<200&&b.top<80&&b.bottom>top) top=Math.round(b.bottom); });
  S.root.style.setProperty('--bl-top',top+'px'); if(S.vb) applyVB();
}
function build(){
  if(!S.root||!A.plan) return;
  var plan=A.plan;
  if(S.msg){ S.msg.remove(); S.msg=null; }
  while(S.tabs.firstChild) S.tabs.removeChild(S.tabs.firstChild);
  var lv=(plan.lv||[]).slice().sort(function(a,b){ return a.e-b.e; });
  var mk=function(id,label){ var b=h('button',{'class':'bl-tab',type:'button','data-level':id,'aria-label':'Level '+label},S.tabs,label); b.addEventListener('click',function(){ A.selectLevel(id); }); return b; };
  if((plan.ex&&((plan.ex.sh||[]).length||(plan.ex.tr||[]).length))) mk('outside','Outside');
  lv.forEach(function(l){ mk(l.id,dec(l.lb||l.n)); });
  S.level=(plan.ex&&(plan.ex.sh||[]).length)?'outside':(lv[0]&&lv[0].id)||'outside';
  var en=(plan.en||[]).filter(function(e){ return e.k==='main'; })[0]||(plan.en||[])[0];
  if(en&&lv.some(function(l){ return l.id===en.l; })&&!(plan.ex&&(plan.ex.sh||[]).length)) S.level=en.l;
  if(plan.sp&&levelOf(plan.sp.l)) S.level=plan.sp.l;                                  /* open where the walk starts, not on an empty outline */
  while(S.head.firstChild) S.head.removeChild(S.head.firstChild);
  var kb=h('div',{'class':'bl-kind'},S.head); kb.innerHTML=MUSEUM_ICON; kb.appendChild(document.createTextNode((plan.kind==='museum'?'Memory Blueprint':'Memory Blueprint')));
  h('h2',null,S.head,dec(plan.name||A.data.name||'Building'));
  var n=0; for(var k in (A.data.nodes||{})) n++;
  h('p',null,S.head,n+(n===1?' card':' cards')+' placed in '+Object.keys(S.nodesByRoom).length+' rooms. Dashed outlines are approximate, blurred rooms estimated.');
  var wb=h('button',{'class':'bl-go bl-walk',type:'button'},S.head,'Walk in'); wb.addEventListener('click',function(){ A.enterFPV(null,{from:'plan'}); }); if(plan.ex&&(plan.ex.sh||[]).length&&plan.sp){ var wo=h('button',{'class':'bl-go bl-walk bl-alt',type:'button'},S.head,'Start outside'); wo.addEventListener('click',function(){ A.enterFPV(null,{from:'plan',outside:true}); }); }
  S.home=null; S.vb=null; render(); footer(); brand(); setTimeout(brand,600); setTimeout(brand,2500);
}
function footer(){
  if(!S.root) return;
  var old=S.root.querySelectorAll('.bl-foot,.bl-credits'); for(var i=0;i<old.length;i++) old[i].remove();
  var plan=A.plan, src=(plan.src||[]).filter(function(x){ return x.cr; });
  if(!src.length&&!(plan.ca||[]).length) return;
  var line=src.map(function(x){ return dec(x.cr); }).join(' ');
  var f=h('div',{'class':'bl-ui bl-foot',role:'button',tabindex:'0',title:'Key and credits'},S.root,line||'Key and credits');
  var box=h('div',{'class':'bl-ui bl-credits',hidden:''},S.root);
  h('h3',null,box,'Key');
  h('p',null,box,'Solid outlines: drawn from a plan or published dimensions. Dashed outlines: approximate. Blurred rooms: estimated. Dotted accent outlines: modern spaces placed from published sizes.');
  var used={}; (plan.rm||[]).forEach(function(r){ if(r.ca) used[r.ca]=1; });
  (plan.ca||[]).forEach(function(a){ if(!used[a.id]) return; var k=h('div',{'class':'bl-key'},box); var sw=h('i',null,k); sw.style.background=a.c; h('span',null,k,dec(a.n)); });
  h('h3',null,box,'Credits');
  src.forEach(function(x){ h('p',null,box,dec(x.cr)); });
  if(plan.n) h('p',{'class':'bl-note'},box,dec(plan.n));
  var tg=function(){ box.hidden=!box.hidden; };
  f.addEventListener('click',function(e){ e.stopPropagation(); tg(); });
  f.addEventListener('keydown',function(e){ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); tg(); } });
}
/* a Memory Palace in a building is told apart from the city one by its name and a symbol (columns and a pediment): the back button and nav say "Memory Blueprint" / "Memory Blueprint" */
function brand(){
  if(!A.plan) return; var nm=A.plan.kind==='museum'?'Memory Blueprint':'Memory Blueprint';
  var set=function(sel,pre){ [].forEach.call(document.querySelectorAll(sel),function(e){ e.innerHTML=pre+MUSEUM_ICON+nm; }); };
  set('#nav-timeline','\u21a9 '); set('#drawer-timeline-btn .drawer-label','');
  [].forEach.call(document.querySelectorAll('#desk-back'),function(e){ e.setAttribute('aria-label','Back to the '+nm); e.title='Back to the '+nm; });
}
function nomsg(t){ if(!S.msg){ S.msg=h('div',{'class':'bl-msg'},S.root); } S.msg.textContent=t; }

function zoom(f,cx,cy){ // cx,cy in client px
  var r=S.svg.getBoundingClientRect(), vb=S.vb; if(!vb) return;
  var px=vb[0]+(cx-r.left)/r.width*vb[2], py=vb[1]+(cy-r.top)/r.height*vb[3];
  var nw=Math.max(4,Math.min(S.home[2]*4,vb[2]*f)), k=nw/vb[2];
  vb[0]=px-(px-vb[0])*k; vb[1]=py-(py-vb[1])*k; vb[2]*=k; vb[3]*=k; applyVB();
}
function zoomGlide(f,cx,cy){ // the + and - buttons: the same zoom, eased over a moment instead of one jump
  cancelAnimationFrame(S.zg); var t0=performance.now(), done=0, ms=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches?1:240;
  (function step(t){ var u=Math.min(1,(t-t0)/ms), e=1-Math.pow(1-u,3); zoom(Math.exp(Math.log(f)*(e-done)),cx,cy); done=e; if(u<1) S.zg=requestAnimationFrame(step); })(t0);
}
function wire(){
  var svg=S.svg, pts=S.pts, both=function(t,f,o){ svg.addEventListener(t,f,o); S.mk.addEventListener(t,f,o); }, gs=0;
  both('wheel',function(e){ e.preventDefault(); cancelAnimationFrame(S.zg); zoom(Math.exp(e.deltaY*(e.ctrlKey?.01:.0016)),e.clientX,e.clientY); },{passive:false});
  /* Safari's trackpad pinch is gesturestart / gesturechange (scale since the start), not a ctrl-wheel */
  both('gesturestart',function(e){ e.preventDefault(); e.stopPropagation(); gs=e.scale||1; },{passive:false});
  both('gesturechange',function(e){ e.preventDefault(); e.stopPropagation(); if(!gs||!e.scale) return; zoom(gs/e.scale,e.clientX,e.clientY); gs=e.scale; },{passive:false});
  both('gestureend',function(e){ e.preventDefault(); gs=0; },{passive:false});
  both('pointerdown',function(e){
    pts[e.pointerId]={x:e.clientX,y:e.clientY}; S.moved=false;
    S.drag={x:e.clientX,y:e.clientY,vb:S.vb.slice(),d:pinch()};
  });             // (the pointer is captured only once a drag starts: capturing at once would send the click to the svg, not to the room or pill)
  both('pointermove',function(e){
    if(!pts[e.pointerId]) return; pts[e.pointerId]={x:e.clientX,y:e.clientY};
    var ids=Object.keys(pts), r=svg.getBoundingClientRect();
    if(ids.length>=2){ var d=pinch(); if(S.drag&&S.drag.d&&d){ zoom(S.drag.d/d,mid().x,mid().y); S.drag.d=d; S.moved=true; } return; }
    var dx=e.clientX-S.drag.x, dy=e.clientY-S.drag.y;
    if(!S.moved && Math.hypot(dx,dy)<5) return;
    if(!S.moved){ try{ svg.setPointerCapture(e.pointerId); }catch(x){} }
    S.moved=true; svg.classList.add('bl-drag');
    var vb=S.drag.vb; S.vb[0]=vb[0]-dx/r.width*vb[2]; S.vb[1]=vb[1]-dy/r.height*vb[3]; S.vb[2]=vb[2]; S.vb[3]=vb[3]; applyVB();
  });
  function up(e){ delete pts[e.pointerId]; svg.classList.remove('bl-drag'); if(!Object.keys(pts).length) setTimeout(function(){ S.moved=false; },0); if(S.drag) S.drag.d=0; }
  both('pointerup',up); both('pointercancel',up);
  svg.addEventListener('click',function(){ if(S.moved) return; S.sel=null; info(null); [].forEach.call(svg.querySelectorAll('.bl-sel'),function(n){ n.classList.remove('bl-sel'); }); });
  function pinch(){ var k=Object.keys(pts); if(k.length<2) return 0; return Math.hypot(pts[k[0]].x-pts[k[1]].x,pts[k[0]].y-pts[k[1]].y); }
  function mid(){ var k=Object.keys(pts); return {x:(pts[k[0]].x+pts[k[1]].x)/2,y:(pts[k[0]].y+pts[k[1]].y)/2}; }
  window.addEventListener('resize',function(){ if(S.root&&!S.root.hidden){ setTop(); if(S.vb) applyVB(); } });
}

A.mount=function(data){
  if(S.root) return;
  A.data=data||{};
  var css=document.createElement('style'); css.id='bldg-css'; css.textContent=BLDG_CSS; (document.head||document.documentElement).appendChild(css);
  var root=S.root=h('div',{id:'bldg-root','aria-label':'Building blueprint'},document.body);
  S.svg=el('svg',{'class':'bl-svg',role:'img','aria-label':'Blueprint of '+dec(A.data.name||'the building'),preserveAspectRatio:'xMidYMid meet',viewBox:'0 0 100 100'},root);
  var defs=el('defs',{},S.svg), flt=el('filter',{id:'bl-feather',x:'-8%',y:'-8%',width:'116%',height:'116%'},defs); el('feGaussianBlur',{stdDeviation:'.55'},flt);
  S.view=el('g',{},S.svg);
  S.mk=h('div',{'class':'bl-mk'},root); S.chips=[]; S.mkSet=AltoMarkers.settle(function(){ layoutPills(true); },170);
  AltoMarkers.reg('bldg',function(){ if(!S.vb||S.root.hidden) return []; var r=S.root.getBoundingClientRect(), z=r.width/(S.root.clientWidth||1), t=scr();   // tests: chips and anchors in client px
    return S.chips.map(function(p){ var b=p.getBoundingClientRect(), cs=getComputedStyle(p);
      return {id:p._n.id, x:b.left+b.width/2, y:b.top+b.height/2, w:b.width, h:b.height, ax:r.left+(p._a[0]*t.s+t.x)*z, ay:r.top+(p._a[1]*t.s+t.y)*z, op:cs.visibility==='hidden'?0:+cs.opacity}; }); });
  S.head=h('div',{'class':'bl-ui bl-head'},root);
  S.tabs=h('div',{'class':'bl-ui bl-tabs'},root);
  S.info=h('div',{'class':'bl-ui bl-info',hidden:''},root);
  var z=h('div',{'class':'bl-ui bl-zoom'},root);
  [['+',.7,'Zoom in'],['−',1.4,'Zoom out']].forEach(function(b){ var x=h('button',{'class':'bl-btn',type:'button','aria-label':b[2]},z,b[0]); x.addEventListener('click',function(){ var r=S.svg.getBoundingClientRect(); zoomGlide(b[1],r.left+r.width/2,r.top+r.height/2); }); });
  var fitb=h('button',{'class':'bl-btn',type:'button','aria-label':'Fit to screen'},z,'▣'); fitb.addEventListener('click',function(){ cancelAnimationFrame(S.zg); fit(); applyVB(); });
  setTop(); wire(); watchDetail();
  A.show();
  [150,500,1200,2500].forEach(function(t){ setTimeout(setTop,t); });
  if(A.data.none){ nomsg('No building plan yet. Ask Claude to run set_up_building for this timeline.'); A.ready=Promise.reject(new Error('no plan')); A.ready.catch(function(){}); return; }
  index();
  nomsg('Loading the plan…');
  A.ready=new Promise(function(res,rej){
    if(A.data.plan){ A.load(A.data.plan); res(A.plan); return; }
    fetch(A.data.url,{credentials:'same-origin'}).then(function(r){ if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); })
      .then(function(p){ A.load(p); res(p); }).catch(function(e){ nomsg('The blueprint could not load its plan. Reload the page; if it still does not appear, ask Claude to republish this timeline.'); rej(e); });   // never the cards: this method has only the blueprint and the walk
  });
  A.ready.catch(function(){});
};
A.unmount=function(){ if(S.root){ S.root.remove(); S.root=null; } if(S.mo){ S.mo.disconnect(); S.mo=null; } var c=document.getElementById('bldg-css'); if(c) c.remove(); document.documentElement.classList.remove('bldg-open'); };
window.AltoBuilding=A;
})();
"""

# the script text: the stylesheet is spliced in as a JS string, the whole wrapped so BLDG_CSS is not a global
BUILDING_ASSET = (MARKERS_JS + "(function(){\nvar BLDG_CSS=" + _json.dumps(BUILDING_CSS + MARKERS_CSS) + ";\nvar FPV_URL=" + _json.dumps(_FPV_PATH) + ";\n" + BUILDING_JS + "\n})();\n")
BUILDING_V = _hashlib.sha256(BUILDING_ASSET.encode("utf-8")).hexdigest()[:10]
BUILDING_PATH = f"/bldg/palace-building-{BUILDING_V}.js"
# The newest renderer under a fixed name, written by every publish beside the hashed one (no-cache). A page names the renderer of the
# release that built it; a later deploy that dropped that file left civ-pro-museum with no blueprint (1.9.154's renderer was gone
# once 1.9.155's site went up, 2026-10-23), so the page falls back to this one. The page data is the same contract (window._ALTO_BUILDING v 1).
BUILDING_LATEST = "/bldg/palace-building-latest.js"
# the page's loader: a synchronous request answered from the browser's cache after the first visit, run as an inline script (as the ride's and the fleet's);
# the fixed name only when the hashed file did not load
BUILDING_LOADER = ("\nfunction altoLoadBuilding(){ " + _json.dumps([BUILDING_PATH, BUILDING_LATEST]).replace('"', "'") + ".forEach(function(u){ if(window.AltoBuilding) return;"
                   " try{ var x=new XMLHttpRequest(); x.open('GET',u,false); x.send(null); if(x.status===200&&x.responseText){ var s=document.createElement('script');"
                   " s.text=x.responseText; (document.head||document.documentElement).appendChild(s); s.remove(); } }catch(e){} }); }\n")


def building_asset() -> tuple[str, str]:
    """(file name under /bldg/, the script) for the site."""
    return BUILDING_PATH.rsplit("/", 1)[1], BUILDING_ASSET


# Mounted, or, when no renderer loads at all, a plain notice over a hidden page: this method is the blueprint and the walk, never the
# timeline's cards (Luke: "we don't need the card view for that style").
BUILDING_START = ("\n(function(){ function fail(){ var d=document.documentElement, m=document.createElement('div'); d.classList.add('bldg-open'); m.id='bldg-fail'; m.setAttribute('role','alert');"
                  " m.style.cssText='position:fixed;left:50%;top:45%;transform:translate(-50%,-50%);max-width:min(440px,calc(100vw - 32px));padding:18px 22px;border-radius:14px;"
                  "background:#16181ddd;color:#f3f1ea;font:15px/1.45 system-ui;text-align:center;z-index:50';"
                  " m.textContent='The blueprint could not load. Reload the page; if it still does not appear, ask Claude to republish this timeline.'; document.body.appendChild(m);"
                  " var w=document.getElementById('world'); if(w) w.style.visibility='hidden'; }"
                  " function go(){ try{ altoLoadBuilding(); if(window.AltoBuilding) window.AltoBuilding.mount(window._ALTO_BUILDING); }catch(e){} if(!document.getElementById('bldg-root')) fail(); }"
" if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',go); else go(); })();\n")


def resolved(b, nodes) -> dict:
    """{"plan": the plan or None, "assign": {node id: {"r", "a"}}, "unplaced": [...], "notes": [...], "order": [node ids in outline order]} for a Building
    Palace brief: the stored plan, the nodes handed to rooms or anchors (building_schema.assign_nodes), the caller's overrides on top."""
    from .building_schema import assign_nodes, plan_of
    from .palace import structure
    units, floors, _of = structure(b, nodes)
    by = {n.id: n for n in nodes}
    order = [i for u in units for bid in u for i in [bid] + floors.get(bid, [])]
    order += [n.id for n in nodes if n.id not in set(order)]
    plan = plan_of(b)
    bd = b.building or {}
    res = {"plan": plan, "assign": {}, "unplaced": list(order), "notes": [], "order": order}
    if plan:
        res.update(assign_nodes(plan, [by[i] for i in order], bd.get("mode", "room"), bd.get("assign")))
    return res


def building_data(b, nodes) -> str:
    """window._ALTO_BUILDING: what the hosted renderer needs from the page (the plan itself is the hosted file, named by its hash)."""
    from .palace import numbers, structure
    from .sanitize import js_json
    units, floors, _of = structure(b, nodes)
    num = numbers(units, floors)
    r = resolved(b, nodes)
    bd = b.building or {}
    by = {n.id: n for n in nodes}
    data = {"v": 1, "name": bd.get("name") or "", "mode": bd.get("mode", "room"),
            "acts": [{"n": a.short or a.label, "c": a.color or ""} for a in b.acts],
            "nodes": {i: {"n": num.get(i, ""), "t": by[i].title, "a": by[i].act,
                          **({"r": r["assign"][i]["r"], "s": r["assign"][i]["a"]} if i in r["assign"] else {})} for i in r["order"]},
            "order": r["order"]}
    if r["plan"]:
        from .building_schema import file_name
        data["h"] = bd.get("plan_h")
        data["url"] = "/bldg/" + file_name(bd.get("plan_h"))
        data["name"] = data["name"] or r["plan"].get("name") or ""
        data["kind"] = r["plan"].get("kind") or ""
    else:
        data["none"] = 1
    return "\nwindow._ALTO_BUILDING=" + js_json(data, separators=(",", ":")) + ";" + BUILDING_LOADER + BUILDING_START
