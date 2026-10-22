"""Part MARK of the first-person city (2.0.1): the buildings that HOLD something are obvious, from afar and from the street.

Owner report (real Safari, 1.9.102): "It's not obvious which buildings in FPV have content." A content building is a node building (a unit, section or index of
yours: E.P.at, one per lot) or a landmark with a page (E.M.landmarks[].page, e.g. Independence Hall -> the Constitution index). Before this, only a door and a
small name pin within ~12 units said so. Now (all of it in the roam closure, spliced into palace_ride_e.py at /*@MARK@*/; nothing in GL, so no blend state leaks):

  far        a floating place label per content building (screen space, like a maps place label): the number in a district-coloured chip, the name, the distance,
             and a thin leader line down to its roof (to its door when near). Up to MK_MAX (8) labels, chosen by mkLayout (a pure function: priority = distance,
             less for being near the middle of the view, a bonus for the target and for being shown already, so nothing pops) and kept apart (a label that would
             overlap a better one is stacked up to two rows higher, else it waits). Labels fade in and out by distance (full to MK_FULL 250 m, gone at MK_FAR 400 m),
             and one hidden behind a building dims to 40 % instead of vanishing (mkOcc: a ray against the footprints in the cells it crosses, two labels a frame).
             Over the roof a restrained light beam and crown glow in the district colour (2D overlay canvas, drawn over the other buildings, very low alpha).
  near       the building itself: a district-coloured banner on its canopy with the number and name, a name plaque beside the door (text painted on an offscreen
             canvas from textContent-safe strings: fillText only, never HTML), both mapped onto the wall in perspective strips; the building's roofline glows softly
             when you look at it (the reticle: the middle of the view); the door pin now says "Enter".
  navigate   a small "Nearby" panel (bottom left, collapsible, remembered in localStorage alto-palace-fpv-near) lists the six nearest: colour dot, number, name,
             distance and an arrow pointing to it relative to the way you face. A click turns you toward it. N / Shift+N cycle the nearest and turn toward each,
             G walks you to its door (steers round corners, stops when blocked, any move key takes over), E at a landmark with a page within 30 m opens that page.
  mini-map   a round north-up map (bottom right; M or its button; remembered as alto-palace-fpv-map): the roads of the loaded world (pre-drawn once per world
             version into an offscreen canvas), your heading cone, the content buildings as district-coloured dots; redrawn at ~8 Hz, never per frame.
  a11y       the panel is a labelled region of real buttons (Tab reaches them: roam's own Tab cycles the HUD's buttons), an aria-live note says what N / G did,
             the labels themselves are aria-hidden duplicates of the list; under prefers-reduced-motion turns snap and labels do not slide.
  cost       O(content buildings) a frame; one container, pooled label elements moved by transform / opacity; text written only when it changes.

API (tests): window._palRide.roam.marks = {layout, pick, list, state, next, walk, toggleMap, toggleNear, frame}.
"""
from __future__ import annotations

JS_MARK = r"""
/* ══ content buildings made obvious (palace_ride_mark.py) ══ */
var MK={on:true, list:null, lkey:'', lM:null, ver:-1, layer:null, labs:[], ui:null, tgt:null, turn:null, auto:null, map:false, near:true, last:0, occI:0, hov:null, plaq:{}, mapBg:null, mapVer:-1, mapAt:0, listAt:0, sig:'', said:'', n:0};
var MK_MAX=8, MK_FAR=400, MK_FULL=250, MK_NEAR=40, MK_OCCNEAR=30, MK_LS='alto-palace-fpv-near', MK_LSM='alto-palace-fpv-map', MK_LIST=6, MK_LMOPEN=30;
function mkGet(k,d){ try{ var v=window.localStorage.getItem(k); return v==null?d:v==='1'; }catch(x){ return d; } }
function mkSet(k,v){ try{ window.localStorage.setItem(k,v?'1':'0'); }catch(x){} }
function mkCol(c){ c=String(c||''); return (/^#[0-9a-f]{3,8}$/i.test(c)||/^rgba?\([\d\s.,%]+\)$/i.test(c))?c:'#8a93b0'; }
function mkRgb(c){ var m=/^#([0-9a-f]{3}|[0-9a-f]{6})/i.exec(c); if(m){ var h=m[1]; if(h.length===3) h=h[0]+h[0]+h[1]+h[1]+h[2]+h[2]; return [parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16)]; }
  var r=/rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)/i.exec(c); return r?[+r[1],+r[2],+r[3]]:[138,147,176]; }
function mkA(rgb,a){ return 'rgba('+Math.round(rgb[0])+','+Math.round(rgb[1])+','+Math.round(rgb[2])+','+a.toFixed(3)+')'; }
/* ── which buildings hold something: the node lots and the landmarks with a page, in world units (real metres x UM in the real world, map units on the lattice) ── */
function mkPageName(pg){ var q=String(pg||'').split(':'), k=q.slice(1).join(':'); if(q[0]==='index'){ var b=null; try{ b=document.querySelector('[data-axis-index="'+String(k).replace(/["\\]/g,'')+'"]'); }catch(x){} return b?b.textContent.replace(/\d+\s*$/,'').replace(/^[^A-Za-z\u00a7]+/,'').trim():k; }
  if(q[0]==='node' && E.title) return String(E.title(k)||k); return k; }
function mkList(){
  var key=(S.real?'r':'l'); if(MK.list && MK.lkey===key && MK.lM===E.M) return MK.list;
  var o=[], P=E.P||{}, seen={}, tmp={x:0,y:0,k:0};
  function at(x,y){ if(S.real){ realOf(x,y,tmp); return [tmp.x*UM,tmp.y*UM]; } return [x,y]; }
  Object.keys(P.at||{}).forEach(function(id){ if(E.bOf(id)!==id) return; var lk=P.at[id]; if(seen[lk]) return; seen[lk]=1; var L=E.lot(lk); if(!L) return;
    var p=at(L[0],L[1]), nm=String(E.name(id)||id), tt=String((E.title&&E.title(id))||''), num=(tt && nm.length>tt.length && nm.slice(-tt.length)===tt)?nm.slice(0,nm.length-tt.length).trim():'';
    if(!num){ var mm=/^(\d+(?:\.\d+)*[a-z]?)\s+(\S.*)$/i.exec(nm); if(mm){ num=mm[1]; if(!tt) tt=mm[2]; } }
    var tw=(P.tw||{})[id], hb=tw?Math.min(220,60+tw):(+E.nbH(id)||30), h=S.real?Math.max(hb*.42,14)*UM:hb*VEX, col=mkCol(E.tubeCol(E.ucol(id)));
    o.push({k:'n', id:String(id), num:num, name:tt||nm, full:nm, col:col, rgb:mkRgb(col), x:p[0], y:p[1], h:h, s:null, door:null, page:null, a:0, occ:false, el:null, d:1e9}); });
  ((E.M&&E.M.landmarks)||[]).forEach(function(l){ if(!l||!l.page||l.x==null||!l.n) return; var p=at(l.x,l.y), col='#d8b35a';
    o.push({k:'l', id:'l:'+l.n, num:'', name:String(l.n), full:String(l.n), sub:mkPageName(l.page), col:col, rgb:mkRgb(col), x:p[0], y:p[1], h:28*UM, s:null, door:null, page:String(l.page), a:0, occ:false, el:null, d:1e9}); });
  MK.list=o; MK.lkey=key; MK.lM=E.M; MK.ver=-1; return o; }
/* the world's own solids for them, when loaded: the real footprint, height and door */
function mkSync(L){
  var Wd=S.W; if(!Wd || Wd.ver===MK.ver) return; MK.ver=Wd.ver; var byId={}, byLm={};
  L.forEach(function(it){ if(it.k==='n') byId[it.id]=it; else byLm[it.name]=it; it.s=null; it.door=null; });
  (Wd.solids||[]).forEach(function(s){ var it=null;
    if(s.kind==='node' && s.id!=null) it=byId[String(s.id)];
    else if(s.lmReal && !s.part) it=byLm[s.lmReal];
    else if(s.kind==='lm' && s.name) it=byLm[s.name];
    if(!it || (it.s && (it.s.nm&&!s.nm || (!!it.s.nm===!!s.nm && it.s.h>=s.h)))) return; it.s=s; it.x=s.cx; it.y=s.cy; it.h=Math.max(s.h+(s.z0||0), it.k==='l'?14*UM:0); if(s.door) it.door=s.door; }); }
/* ── the label layout: a pure function. c = [{id, sx, sy (the anchor on screen), w, h, pri (lower first), lead}], the screen W x H, at most max; returns [{id, x, y, lead}] ── */
function mkLayout(c, W, H, max, top){
  top=top==null?66:top; var q=c.slice().sort(function(a,b){ return a.pri-b.pri; }), placed=[], out=[], i, k;
  function hit(r){ for(var j=0;j<placed.length;j++){ var p=placed[j]; if(r[0]<p[2]+6 && r[2]+6>p[0] && r[1]<p[3]+4 && r[3]+4>p[1]) return true; } return false; }
  for(i=0;i<q.length && out.length<max;i++){ var it=q[i], w=it.w, h=it.h, x=Math.max(8,Math.min(W-w-8,it.sx-w/2)), lead=it.lead||26;
    if(it.sx<-40 || it.sx>W+40 || it.sy<top || it.sy>H+400) continue;
    for(k=0;k<3;k++){ var y=Math.min(it.sy,H-8)-lead-h-k*(h+6); if(y<top) break; var r=[x,y,x+w,y+h]; if(!hit(r)){ placed.push(r); out.push({id:it.id, x:x, y:y, lead:it.sy-(y+h)}); break; } } }
  return out; }
/* the priority of a candidate: its distance in metres, less for being near the middle of the view, much less for the target, a little less for being shown already */
function mkPri(d, off, isT, shown){ return d*(1+.9*Math.min(1,Math.abs(off))) - (isT?1e5:0) - (shown?35:0); }
/* the alpha a label wants: by distance (smoothstep from MK_FAR to MK_FULL), dimmed when hidden behind a building */
function mkWant(d, occ){ var u=clamp((MK_FAR-d)/(MK_FAR-MK_FULL),0,1), a=u*u*(3-2*u); return !occ?a:(occ<MK_OCCNEAR?0:a*.4); }
/* ── a ray from the eye to (x,y,z) against the footprints of the cells it crosses: 0 when clear, else the distance in metres to the nearest building (not `skip`) in the way ── */
function mkOcc(x,y,z,skip){
  var x0=C.x, y0=C.y, z0=C.z, dx=x-x0, dy=y-y0, L=Math.hypot(dx,dy); if(L<1) return false; var seen={}, n=Math.ceil(L/(CELL*.5)), list=[], i, q;
  for(i=0;i<=n;i++){ var px=x0+dx*i/n, py=y0+dy*i/n, ci=Math.floor(px/CELL), cj=Math.floor(py/CELL); for(var a=-1;a<=1;a++) for(var b=-1;b<=1;b++){ var k=(ci+a)+','+(cj+b); if(seen[k]) continue; seen[k]=1; var c=S.cells[k]; if(c&&c.small) list.push(c.small); } }
  list.push(S.bigs||[]); var l2=L*L, hitT=2;
  for(q=0;q<list.length;q++){ var arr=list[q]; for(i=0;i<arr.length;i++){ var s=arr[i]; if(s===skip || (skip && skip.lmReal && s.lmReal===skip.lmReal) || !s.ring) continue;
      var t=((s.cx-x0)*dx+(s.cy-y0)*dy)/l2; if(t<-.05||t>1.05) continue; t=clamp(t,0,1); var ex=x0+dx*t-s.cx, ey=y0+dy*t-s.cy; if(ex*ex+ey*ey>s.r*s.r) continue;
      var th=mkRayRing(s, x0,y0,z0, dx,dy,z-z0); if(th<hitT) hitT=th; } }
  return hitT<=1?Math.max(.01,hitT*L/UM):0; }
function mkRayRing(s, x0,y0,z0, dx,dy,dz){
  var r=s.ring, n=r.length/2, top=(s.z0||0)+s.h, j=n-1, best=2;
  for(var i=0;i<n;j=i++){ var ax=r[2*j], ay=r[2*j+1], ex=r[2*i]-ax, ey=r[2*i+1]-ay, den=dx*ey-dy*ex; if(Math.abs(den)<1e-9) continue;
    var t=((ax-x0)*ey-(ay-y0)*ex)/den, u=((ax-x0)*dy-(ay-y0)*dx)/den; if(t<=.02||t>=.98||u<0||u>1) continue; if(z0+dz*t<top && t<best) best=t; }
  return best; }
/* ── the DOM: one layer of pooled labels, the Nearby panel, the mini-map ── */
function markHud(root){
  if(MK.layer) return; var ly=document.createElement('div'); ly.className='mk-layer'; ly.setAttribute('aria-hidden','true');
  for(var i=0;i<MK_MAX+4;i++){ var e=document.createElement('div'); e.className='mk-lab'; e.innerHTML='<u class="mk-ln"></u><div class="mk-card"><i class="mk-no"></i><b class="mk-nm"></b><span class="mk-dd"></span></div><div class="mk-hint"></div>';
    e.style.opacity='0'; ly.appendChild(e); MK.labs.push({el:e, it:null, ln:e.firstChild, no:e.querySelector('.mk-no'), nm:e.querySelector('.mk-nm'), dd:e.querySelector('.mk-dd'), hint:e.querySelector('.mk-hint'), t:{}}); }
  root.insertBefore(ly, root.firstChild); MK.layer=ly;
  ly.addEventListener('click', function(e){ var l=e.target.closest&&e.target.closest('.mk-lab'); if(!l) return; e.preventDefault(); e.stopPropagation(); for(var i=0;i<MK.labs.length;i++) if(MK.labs[i].el===l && MK.labs[i].it){ markWalk(MK.labs[i].it); } });          /* one click goes there (it used to turn you, and only a second click walked) */
  ly.addEventListener('pointerdown', function(e){ e.stopPropagation(); });
  var p=document.createElement('div'); p.className='mk-near'; p.setAttribute('role','region'); p.setAttribute('aria-label','Nearby places');
  p.innerHTML='<div class="mk-hd"><button type="button" class="mk-tg" data-mk="near" aria-expanded="true" aria-controls="mk-ol"><svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 4.5 6 7.5l3-3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg><span>Nearby</span><em class="mk-ct"></em></button>'
    +'<button type="button" class="mk-mb" data-mk="map" aria-pressed="false" aria-label="Mini-map (M)"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 4l4-1.5 4 1.5 4-1.5v9.5L10 13.5 6 12 2 13.5z M6 2.5V12 M10 4v9.5" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/></svg></button></div>'
    +'<ol class="mk-ol" id="mk-ol"></ol><div class="mk-keys" aria-hidden="true"><kbd>N</kbd> next <kbd>G</kbd> walk there <kbd>M</kbd> map</div><div class="pr-live mk-live" aria-live="polite"></div>';
  var ol=p.querySelector('.mk-ol'), its=[];
  for(i=0;i<MK_LIST;i++){ var li=document.createElement('li'), b=document.createElement('button'); b.type='button'; b.className='mk-it'; b.innerHTML='<i class="mk-dot"></i><span class="mk-in"></span><b class="mk-iname"></b><em class="mk-id"></em><svg class="mk-ar" viewBox="0 0 12 12" aria-hidden="true"><path d="M6 1.5 10 10 6 8 2 10z" fill="currentColor"/></svg>';
    li.hidden=true; li.appendChild(b); ol.appendChild(li); its.push({li:li, b:b, dot:b.querySelector('.mk-dot'), n:b.querySelector('.mk-in'), nm:b.querySelector('.mk-iname'), d:b.querySelector('.mk-id'), ar:b.querySelector('.mk-ar'), it:null, t:{}}); }
  var mp=document.createElement('div'); mp.className='mk-map'; mp.innerHTML='<canvas width="176" height="176" role="img" aria-label="Mini-map: you, the way you face, and the buildings that hold something"></canvas><b class="mk-mn" aria-hidden="true">N</b>';
  root.appendChild(p); root.appendChild(mp);
  MK.ui={p:p, ol:ol, its:its, tg:p.querySelector('.mk-tg'), ct:p.querySelector('.mk-ct'), mb:p.querySelector('.mk-mb'), live:p.querySelector('.mk-live'), map:mp, cv:mp.querySelector('canvas')};
  p.addEventListener('click', function(e){ var b=e.target.closest&&e.target.closest('button'); if(!b) return; e.preventDefault(); e.stopPropagation();
    var a=b.getAttribute('data-mk'); if(a==='near') markNearToggle(); else if(a==='map') markMapToggle(); else { for(var i=0;i<its.length;i++) if(its[i].b===b && its[i].it){ markWalk(its[i].it); } } });
  var pin=S.hud&&S.hud.pin; if(pin && !pin.querySelector('.mk-ent')){ var en=document.createElement('span'); en.className='mk-ent'; en.textContent='Enter'; pin.insertBefore(en, pin.querySelector('kbd')); }
  MK.near=mkGet(MK_LS,true); MK.map=mkGet(MK_LSM,false); markUiState(); }
function markUiState(){ var u=MK.ui; if(!u) return; u.p.classList.toggle('shut', !MK.near); u.tg.setAttribute('aria-expanded', MK.near?'true':'false'); u.ol.hidden=!MK.near;
  u.map.classList.toggle('on', MK.map); u.mb.setAttribute('aria-pressed', MK.map?'true':'false'); MK.mapAt=0; }
function markNearToggle(v){ MK.near=v==null?!MK.near:!!v; mkSet(MK_LS,MK.near); markUiState(); MK.listAt=0; return MK.near; }
function markMapToggle(v){ MK.map=v==null?!MK.map:!!v; mkSet(MK_LSM,MK.map); markUiState(); markSay(MK.map?'Mini-map shown.':'Mini-map hidden.'); return MK.map; }
function markSay(t){ if(MK.ui && t){ MK.ui.live.textContent=t; MK.said=t; } }
function mkDist(d){ return d<1000?Math.round(d/(d<100?5:10))*(d<100?5:10)+' m':(d/1000).toFixed(1)+' km'; }
function mkRel(it){ var a=angTo(S.yaw, Math.atan2(it.y-S.y,it.x-S.x)); return a; }
function mkSide(a){ var d=Math.abs(a)*180/Math.PI; if(d<20) return 'ahead'; if(d>150) return 'behind you'; return (d<70?'ahead on the ':(d<110?'on the ':'behind on the '))+(a<0?'left':'right'); }
function mkLabel(it){ return (it.num?it.num+' ':'')+it.name+', '+mkDist(it.d).replace(' m',' metres').replace(' km',' kilometres')+', '+mkSide(mkRel(it)); }
/* the nearest content buildings, nearest first (distance in metres) */
function markNearest(n){ var L=mkList(), o=[]; for(var i=0;i<L.length;i++){ var it=L[i]; it.d=Math.hypot(it.x-S.x,it.y-S.y)/UM; o.push(it); } o.sort(function(a,b){ return a.d-b.d; }); return n?o.slice(0,n):o; }
/* ── aim, cycle, walk ── */
function markAim(it, say){ if(!it) return false; MK.tgt=it; MK.auto=null; var to=Math.atan2(it.y-S.y,it.x-S.x);
  if(reduced()){ S.yaw=to; MK.turn=null; } else MK.turn={from:S.yaw, to:to, el:0, dur:Math.min(700,260+Math.abs(angTo(S.yaw,to))*240), p0:S.pitch};
  if(say){ it.d=Math.hypot(it.x-S.x,it.y-S.y)/UM; markSay(mkLabel(it)+'. Press G to walk there.'); } MK.listAt=0; return true; }
function markNext(dir){ var L=markNearest(8).filter(function(it){ return it.d<MK_FAR*2; }); if(!L.length){ markSay('Nothing that holds a page is near.'); return null; }
  var i=L.indexOf(MK.tgt), j=i<0?(dir<0?L.length-1:0):(i+(dir<0?L.length-1:1))%L.length, it=L[j]; markAim(it,false);
  markSay((j+1)+' of '+L.length+': '+mkLabel(it)+'. G to walk there.'); return it; }
/* the point to walk to: a few metres out from the door, or from the nearest wall of a landmark */
function mkGoal(it){ var d=it.door; if(d) return [d.x+d.nx*3*UM, d.y+d.ny*3*UM, Math.atan2(-d.ny,-d.nx), 1];
  var s=it.s; if(s && s.ring){ var r=s.ring, n=r.length/2, best=null, bd=1e18, j=n-1; for(var i=0;i<n;j=i++){ var ax=r[2*j], ay=r[2*j+1], ex=r[2*i]-ax, ey=r[2*i+1]-ay, l2=ex*ex+ey*ey||1e-9, t=clamp(((S.x-ax)*ex+(S.y-ay)*ey)/l2,0,1), px=ax+ex*t, py=ay+ey*t, q=(px-S.x)*(px-S.x)+(py-S.y)*(py-S.y); if(q<bd){ bd=q; best=[px,py]; } }
    if(best){ var ox=S.x-best[0], oy=S.y-best[1], ol=Math.hypot(ox,oy)||1; return [best[0]+ox/ol*4*UM, best[1]+oy/ol*4*UM, Math.atan2(-oy,-ox)]; } }
  var dx=S.x-it.x, dy=S.y-it.y, l=Math.hypot(dx,dy)||1; return [it.x+dx/l*25*UM, it.y+dy/l*25*UM, Math.atan2(-dy,-dx)]; }
/* a walking route: A* on a 3 m grid, the free test (blockedAt) asked lazily, at most MK_ASTAR nodes; null when there is none (then it steers straight) */
var MK_ASTAR=20000, MK_ASTMS=110, MK_WALKMAX=150;                /* at most 12000 nodes and ~90 ms, once per G */
function mkPath(sx,sy,gx,gy){
  var G=(Math.hypot(gx-sx,gy-sy)<90*UM?1.4:2.4)*UM, gi=Math.round((gx-sx)/G),          /* fine enough for an alley (it was 3.5 m: narrow ways failed and it steered at walls) */ gj=Math.round((gy-sy)/G), open=[], came={}, cost={}, free={}, n=0, D=[[1,0,1],[-1,0,1],[0,1,1],[0,-1,1],[1,1,1.414],[1,-1,1.414],[-1,1,1.414],[-1,-1,1.414]];
  function ok(i,j){ var k=i+','+j; if(free[k]===undefined) free[k]=(i===0&&j===0)||!blockedAt(sx+i*G,sy+j*G); return free[k]; }
  function h(i,j){ return Math.hypot(i-gi,j-gj); }
  function push(e){ open.push(e); var c=open.length-1; while(c>0){ var p=(c-1)>>1; if(open[p][0]<=e[0]) break; open[c]=open[p]; c=p; } open[c]=e; }
  function pop(){ var top=open[0], last=open.pop(); if(open.length){ var c=0, L=open.length; for(;;){ var l=2*c+1, r=l+1, m=-1, mv=last[0]; if(l<L && open[l][0]<mv){ m=l; mv=open[l][0]; } if(r<L && open[r][0]<mv) m=r; if(m<0) break; open[c]=open[m]; c=m; } open[c]=last; } return top; }
  cost['0,0']=0; push([h(0,0),0,0]); var end=null, bh=1e9, bk=null;
  var t0=performance.now();
  while(open.length && n<MK_ASTAR && (n&63 || performance.now()-t0<MK_ASTMS)){ var e=pop(), i=e[1], j=e[2], k=i+','+j, g=cost[k]; n++; var hh=h(i,j); if(hh<bh){ bh=hh; bk=k; } if(hh<1.5){ end=k; break; }
    for(var q=0;q<8;q++){ var a=i+D[q][0], b=j+D[q][1]; if(!ok(a,b) || (D[q][2]>1 && (!ok(i,b)||!ok(a,j)))) continue; var nk=a+','+b, ng=g+D[q][2]; if(cost[nk]!==undefined && cost[nk]<=ng) continue; cost[nk]=ng; came[nk]=k; push([ng+h(a,b)*1.05,a,b]); } }
  MK.astar=n; if(!end){ if(bk && bh<h(0,0)*.5) end=bk; else return null; }
  var pts=[], kk=end; while(kk){ var ij=kk.split(','); pts.push([sx+ij[0]*G, sy+ij[1]*G]); kk=came[kk]; } pts.reverse();
  var out=[pts[0]]; for(var t=1;t<pts.length-1;t++){ var a0=out[out.length-1], b0=pts[t+1], cl=true; for(var u=.25;u<1;u+=.25) if(blockedAt(a0[0]+(b0[0]-a0[0])*u,a0[1]+(b0[1]-a0[1])*u)){ cl=false; break; } if(!cl) out.push(pts[t]); }
  out.push(pts[pts.length-1]); if(end===gi+','+gj) out.push([gx,gy]); return out; }
function markWalk(it){ it=it||MK.tgt; if(!it || IN.on || DR.busy) return false; MK.tgt=it; MK.turn=null; markFadeStop(); var g=mkGoal(it), d=Math.hypot(g[0]-S.x,g[1]-S.y)/UM, path=null;
  if(d<=MK_WALKMAX){ try{ path=mkPath(S.x,S.y,g[0],g[1]); }catch(x){ path=null; } }
  MK.trips=(MK.trips||0)+1;
  if(!path||d>MK_WALKMAX){ markFade(it,g,d>MK_WALKMAX?'far':'no way'); return true; }
  MK.auto={it:it, x:g[0], y:g[1], face:g[2], slow:0, t:0, best:1e18, since:0, path:path, pi:1, re:0}; MK.last1={mode:'walk', len:d};
  markSay('Walking to '+(it.num?it.num+' ':'')+it.name+'. Esc or a move key stops.'); mkPill(it,'→ '); return true; }
/* the quick way: a short dark fade with the name, and you stand in front of it facing its door (far, or no walkable way, or stuck) */
function markFade(it,g,why){ MK.auto=null; S.keys={}; S.run=false; MK.last1={mode:'fade', why:why, stuck:why==='stuck'}; mkPill(it,'→ '); var V=mkVeil(); var done=function(){ S.x=g[0]; S.y=g[1]; plan(true); stream(true); MK.ver=-1; mkSync(mkList()); var g2=it.door||!g[3]?mkGoal(it):g;          /* a far building's door is known only once its part of the city is loaded: load it, then stand at its door */
    var f=freeNear(g2[0],g2[1]); S.x=f[0]; S.y=f[1]; S.vx=S.vy=0; S.yaw=g2[2]; S.pitch=.02; plan(true); stream(true); markArrive(it); };
  if(S.hold||reduced()||!V){ done(); return; } V.firstChild.textContent='Going to '+(it.num?it.num+' ':'')+it.name+'…'; V.style.opacity='1'; MK.fadeT=setTimeout(function(){ MK.fadeT=null; if(!S.on){ V.style.opacity='0'; return; } done(); setTimeout(function(){ V.style.opacity='0'; },80); },260); }
function markFadeStop(){ if(MK.fadeT){ clearTimeout(MK.fadeT); MK.fadeT=null; } if(MK.veil) MK.veil.style.opacity='0'; }
function mkVeil(){ var H=S.hud&&S.hud.root; if(!H) return null; if(MK.veil&&MK.veil.parentNode) return MK.veil; var v=document.createElement('div'); v.className='mk-veil'; v.setAttribute('aria-hidden','true'); v.appendChild(document.createElement('span')); H.appendChild(v); MK.veil=v; return v; }
function mkPill(it,pre){ var H=S.hud&&S.hud.root; if(!H) return; var p=MK.pill; if(!p||!p.parentNode){ p=MK.pill=document.createElement('div'); p.className='mk-go'; p.appendChild(document.createElement('span')); var x=document.createElement('button'); x.type='button'; x.textContent='✕'; x.title='Stop (Esc)'; x.setAttribute('aria-label','Stop');
    x.addEventListener('click',function(e){ e.preventDefault(); e.stopPropagation(); markStop('Stopped.'); markFadeStop(); mkPillOff(); }); p.appendChild(x); H.appendChild(p); }
  clearTimeout(p._t); p.firstChild.textContent=pre+(it.num?it.num+' ':'')+it.name; p.lastChild.style.display=pre==='✓ '?'none':''; p.style.opacity='1'; }
function mkPillOff(){ if(MK.pill){ MK.pill.style.opacity='0'; } }
function markArrive(it){ MK.auto=null; S.keys={}; S.run=false; MK.arrived=(MK.arrived||0)+1; if(MK.last1) MK.last1.arrived=true; MK.hi={it:it, t:4}; mkPill(it,'✓ '); if(MK.pill){ MK.pill._t=setTimeout(mkPillOff,3200); }
  markSay('At '+(it.num?it.num+' ':'')+it.name+'.'+(it.k==='n'?' Press E to go in.':(it.page?' Press E to open its page.':''))); }
function markStop(why){ if(!MK.auto) return; MK.auto=null; S.keys.f=0; S.run=false; if(why) markSay(why); mkPillOff(); }
/* before the walking tick: the scripted turn and the walk to a door (it presses W for you and steers round what is in front) */
function markSteer(dt){
  var t=MK.turn; if(t){ t.el+=dt*1000; var u=Math.min(1,t.el/t.dur); S.yaw=t.from+angTo(t.from,t.to)*ease(u); S.pitch=t.p0+(.02-t.p0)*ease(u); if(u>=1) MK.turn=null; }
  var A=MK.auto; if(!A) return; A.t+=dt; var dx=A.x-S.x, dy=A.y-S.y, d=Math.hypot(dx,dy);
  if(d<1.6*UM){ var it0=A.it; MK.auto=null; S.keys={}; S.run=false; S.vx=S.vy=0; if(reduced()) S.yaw=A.face; else MK.turn={from:S.yaw, to:A.face, el:0, dur:420, p0:S.pitch}; markArrive(it0); return; }
  if(d<A.best-2){ A.best=d; A.since=0; } else A.since+=dt;
  if(A.since>2.5 && !A.re){ A.re=1; A.since=0; try{ A.path=mkPath(S.x,S.y,A.x,A.y); A.pi=1; }catch(x){} }                           /* stuck once: plan again from here */
  if(A.since>2.5 || A.t>90){ if(MK.last1) MK.last1.stuck=true; markFade(A.it,[A.x,A.y,A.face],'stuck'); return; }                 /* never left standing: the quick way there */
  var P=A.path, wx=A.x, wy=A.y; if(P){ while(A.pi<P.length-1 && Math.hypot(P[A.pi][0]-S.x,P[A.pi][1]-S.y)<2.5*UM) A.pi++; wx=P[Math.min(A.pi,P.length-1)][0]; wy=P[Math.min(A.pi,P.length-1)][1]; }
  var want=Math.atan2(wy-S.y,wx-S.x), look=(P?1.6:3)*UM, offs=[0,.35,-.35,.7,-.7,1.05,-1.05,1.4,-1.4], pick=want;
  for(var i=0;i<offs.length;i++){ var a=want+offs[i]; if(!blockedAt(S.x+Math.cos(a)*look,S.y+Math.sin(a)*look) && !blockedAt(S.x+Math.cos(a)*look*.5,S.y+Math.sin(a)*look*.5)){ pick=a; break; } }
  var turn=angTo(S.yaw,pick), mx=(reduced()?6:3.2)*dt; S.yaw+=Math.max(-mx,Math.min(mx,turn)); S.pitch+=(0.02-S.pitch)*Math.min(1,dt*4);
  var wd=Math.hypot(wx-S.x,wy-S.y); S.keys={f:Math.abs(turn)<1.2?1:0}; S.run=d>40*UM && wd>12*UM && Math.abs(turn)<.35; }
/* ── the per-frame part, after the world is drawn with the camera of this frame (C) ── */
/* the way ahead while walking to a building: a dashed line on the street from your feet along the route (projected each frame; warm, quiet) */
function mkTrail(ctx){ var A=MK.auto; if(!A||!ctx) return; var P=[[S.x,S.y]], i, pts=[], z=.06*UM; if(A.path) for(i=Math.max(1,A.pi);i<A.path.length;i++) P.push(A.path[i]); P.push([A.x,A.y]);
  for(i=0;i+1<P.length;i++){ var a=P[i], b=P[i+1], L=Math.hypot(b[0]-a[0],b[1]-a[1]), n=Math.max(1,Math.ceil(L/(1.2*UM))); for(var k=(i?0:1);k<=n;k++) pts.push([a[0]+(b[0]-a[0])*k/n,a[1]+(b[1]-a[1])*k/n]); }
  ctx.save(); ctx.lineCap='round'; ctx.lineJoin='round'; ctx.setLineDash([10,9]); ctx.lineDashOffset=-(performance.now()/40)%19; ctx.strokeStyle='rgba(255,206,120,.85)'; ctx.shadowColor='rgba(0,0,0,.45)'; ctx.shadowBlur=3;
  var on=false; ctx.beginPath(); for(i=0;i<pts.length&&i<220;i++){ var q=toScr(pts[i][0],pts[i][1],z); if(!q||q[2]>700*UM){ on=false; continue; } ctx.lineWidth=Math.max(1.5,Math.min(7,90/q[2]*UM)); if(on) ctx.lineTo(q[0],q[1]); else { ctx.moveTo(q[0],q[1]); on=true; } }
  ctx.stroke(); ctx.restore(); }
function markDraw(ctx){
  if(!S.on || !MK.layer) return; if(!MK.on){ MK.layer.style.visibility='hidden'; return; } var now=performance.now(), dt=MK.last?Math.min(.1,(now-MK.last)/1000):.016; MK.last=now;
  var hide=IN.on||DR.busy; MK.layer.style.visibility=hide?'hidden':''; if(MK.ui) MK.ui.p.style.visibility=hide?'hidden':''; if(hide){ return; }
  mkTrail(ctx); if(MK.hi){ MK.hi.t-=dt; if(MK.hi.t<=0) MK.hi=null; }
  var L=mkList(); mkSync(L); var W=R.w, H=R.h, cand=[], i, it, fc=Math.cos(S.yaw), fs=Math.sin(S.yaw), half=Math.atan(W/2/(C.foc||W/2));
  /* the reticle: the building under the middle of the view, within 160 m */
  MK.hov=null; var hb=1e9;
  for(i=0;i<L.length;i++){ it=L[i]; var dx=it.x-S.x, dy=it.y-S.y, d=Math.hypot(dx,dy)/UM; it.d=d; it.off=Math.atan2(-dx*fs+dy*fc, dx*fc+dy*fs)/(half||1);
    if(d>MK_FAR){ it.want=0; continue; }
    var near=d<MK_NEAR && it.door, ax=near?it.door.x+it.door.nx*1.2*UM:it.x, ay=near?it.door.y+it.door.ny*1.2*UM:it.y, az=near?4.6*UM:it.h+1.5*UM, sp=toScr(ax,ay,az);
    it.ax=ax; it.ay=ay; it.az=az; it.sp=sp;
    if(!sp || sp[0]<-60 || sp[0]>W+60){ it.want=0; continue; }
    if(it.s && d<160 && Math.abs(it.off)<.5){ var bb=mkBox(it); if(bb && W/2>=bb[0] && W/2<=bb[2] && H/2>=bb[1] && H/2<=bb[3] && d<hb){ hb=d; MK.hov=it; } }
    var m=mkMeasure(it); cand.push({id:it.id, sx:sp[0], sy:sp[1], w:m[0], h:m[1], pri:mkPri(d, it.off, it===MK.tgt, it.a>.3), lead:near?18:26, it:it}); }
  if(MK.tgt && MK.tgt.d>MK_FAR*2) MK.tgt=null;
  var lay=mkLayout(cand, W, H, MK_MAX), pos={}; for(i=0;i<lay.length;i++) pos[lay[i].id]=lay[i];
  /* occlusion, two shown labels a frame */
  var shown=L.filter(function(q){ return pos[q.id]||q.a>.02; });
  for(i=0;i<2 && shown.length;i++){ var o=shown[(MK.occI++)%shown.length]; o.occ=mkOcc(o.ax,o.ay,o.az,o.s); }
  var k=reduced()?1:1-Math.exp(-dt*7);
  for(i=0;i<L.length;i++){ it=L[i]; var p=pos[it.id], want=p?mkWant(it.d,it.occ):0; it.a+=(want-it.a)*k; if(it.a<.01 && !want) it.a=0; if(p) it.pl=p; }
  /* the labels: the shown keep their element, the rest give theirs back */
  var labs=MK.labs; for(i=0;i<labs.length;i++){ var lb=labs[i]; if(lb.it && (lb.it.a<=0 || !lb.it.pl || !lb.it.sp)){ lb.it.el=null; lb.it=null; lb.el.style.opacity='0'; } }
  for(i=0;i<L.length;i++){ it=L[i]; if(it.a<=0 || !it.pl || !it.sp) continue; var lb2=it.el;
    if(!lb2){ for(var j=0;j<labs.length;j++) if(!labs[j].it){ lb2=labs[j]; break; } if(!lb2) continue; lb2.it=it; it.el=lb2; }
    mkPaint(lb2, it); }
  /* the 2D marks on the scene: beams, the roofline glow under the reticle, the banner and plaque at the door */
  ctx.save(); for(i=0;i<L.length;i++){ it=L[i]; if(it.a>.02 && it.d>MK_NEAR*.8) mkBeam(ctx, it); } ctx.restore();
  var ho=MK.hov||(MK.tgt&&MK.tgt.d<160?MK.tgt:null); if(ho && ho.s && !ho.s.nodraw) mkOutline(ctx, ho, MK.hov?1:.6);
  for(i=0;i<L.length;i++){ it=L[i]; if(it.door && it.d<160) mkSign(ctx, it); }
  if(now-MK.listAt>250){ MK.listAt=now; markListPaint(); }
  if(MK.map && now-MK.mapAt>120){ MK.mapAt=now; markMapPaint(); } }
var MKC=null;
function mkMeasure(it){ var key=it.num+'|'+it.name; if(it.mw && it.mk===key) return it.mw; if(!MKC){ try{ MKC=document.createElement('canvas').getContext('2d'); }catch(x){ MKC=null; } }
  var nm=it.name.length>30?it.name.slice(0,29)+'\u2026':it.name, tw=nm.length*7.4, cw=(it.num||it.k==='l')?((it.num||'*').length*7+12):0;
  if(MKC){ MKC.font='600 12.5px system-ui,-apple-system,"Segoe UI",sans-serif'; tw=MKC.measureText(nm).width; MKC.font='700 11.5px system-ui,-apple-system,"Segoe UI",sans-serif'; if(cw) cw=MKC.measureText(it.num||'\u2605').width+12; }
  var w=Math.min(300,Math.ceil(4+cw+7+tw+7+44+10)); it.mk=key; it.mw=[w,26]; return it.mw; }
function mkPaint(lb, it){
  var p=it.pl, t=lb.t, el=lb.el, txt=it.name.length>30?it.name.slice(0,29)+'\u2026':it.name, dd=mkDist(it.d);
  if(t.id!==it.id){ t.id=it.id; lb.no.textContent=it.num||(it.k==='l'?'\u2605':''); lb.no.style.display=(it.num||it.k==='l')?'':'none'; lb.nm.textContent=txt; el.style.setProperty('--mk-c', it.col); el.classList.toggle('lm', it.k==='l'); t.dd=''; t.hint=null; }
  if(t.dd!==dd){ t.dd=dd; lb.dd.textContent=dd; }
  var hot=(it===MK.hov||it===MK.tgt), hint=hot?(DR.cur&&String(DR.cur.id)===it.id?'Enter  E':(it.d<MK_LMOPEN&&it.k==='l'?'Open  E':'Walk there  G')):'';
  if(t.hint!==hint){ t.hint=hint; lb.hint.textContent=hint; el.classList.toggle('hot', !!hint); }
  var x=Math.round(p.x*2)/2, y=Math.round(p.y*2)/2, w=it.mw[0], ln=Math.max(0,it.sp[1]-(p.y+26));
  el.style.transform='translate3d('+x+'px,'+y+'px,0)'; el.style.width=w+'px'; lb.ln.style.left=(it.sp[0]-x-.5).toFixed(1)+'px'; lb.ln.style.transform='scaleY('+(ln/100).toFixed(3)+')';
  var op=it.a.toFixed(2); if(t.op!==op){ t.op=op; el.style.opacity=op; } el.classList.toggle('occ', !!it.occ); }
/* the screen box of a building (its footprint at the ground and at the roof) */
function mkBox(it){ var s=it.s, r=s.ring, n=r.length/2, st=Math.max(1,Math.floor(n/16)), x0=1e9, y0=1e9, x1=-1e9, y1=-1e9, ok=0, z1=(s.z0||0)+s.h;
  for(var i=0;i<n;i+=st){ for(var zz=0;zz<2;zz++){ var q=toScr(r[2*i],r[2*i+1],zz?z1:0); if(!q) continue; ok++; if(q[0]<x0)x0=q[0]; if(q[0]>x1)x1=q[0]; if(q[1]<y0)y0=q[1]; if(q[1]>y1)y1=q[1]; } }
  return ok>2?[x0,y0,x1,y1]:null; }
/* a soft beam of the district colour standing on the roof, and a crown glow: very low alpha, drawn over the other buildings so it reads from the next street */
function mkBeam(ctx, it){
  var b=toScr(it.x,it.y,it.h), t=toScr(it.x,it.y,it.h+70*UM); if(!b||!t) return; var u=clamp((it.d-70)/80,0,1), a=it.a*(it.occ?.7:1)*u*u*(3-2*u), f=b[2]; if(a<.01) return; var w=Math.max(2.5,Math.min(16,2.2*UM*C.foc/f)), rgb=it.rgb, dk=dark();
  var g=ctx.createLinearGradient(b[0],b[1],t[0],t[1]); g.addColorStop(0,mkA(rgb,(dk?.42:.30)*a)); g.addColorStop(.35,mkA(rgb,(dk?.16:.11)*a)); g.addColorStop(1,mkA(rgb,0));
  ctx.globalCompositeOperation=dk?'lighter':'source-over'; ctx.fillStyle=g; ctx.beginPath(); ctx.moveTo(b[0]-w/2,b[1]); ctx.lineTo(t[0]-w*.15,t[1]); ctx.lineTo(t[0]+w*.15,t[1]); ctx.lineTo(b[0]+w/2,b[1]); ctx.closePath(); ctx.fill();
  var rr=Math.max(8,Math.min(70,(it.s?it.s.r:20*UM)*C.foc/f*.7)), gr=ctx.createRadialGradient(b[0],b[1],0,b[0],b[1],rr); gr.addColorStop(0,mkA(rgb,(dk?.34:.22)*a)); gr.addColorStop(1,mkA(rgb,0));
  ctx.fillStyle=gr; ctx.save(); ctx.translate(b[0],b[1]); ctx.scale(1,.42); ctx.translate(-b[0],-b[1]); ctx.beginPath(); ctx.arc(b[0],b[1],rr,0,6.2832); ctx.fill(); ctx.restore(); ctx.globalCompositeOperation='source-over'; }
/* the roofline of the building under the reticle, in its colour, with two outer corner edges */
function mkOutline(ctx, it, k){
  var s=it.s, r=s.ring, n=r.length/2, z1=(s.z0||0)+s.h, pts=[], fr=[], i, lo=null, hi=null, cx=0, cy=0; for(i=0;i<n;i++){ cx+=r[2*i]/n; cy+=r[2*i+1]/n; }
  for(i=0;i<n;i++){ var q=toScr(r[2*i],r[2*i+1],z1); pts.push(q); if(q){ if(!lo||q[0]<lo[0][0]) lo=[q,i]; if(!hi||q[0]>hi[0][0]) hi=[q,i]; }
    var j=(i+1)%n, ex=r[2*j]-r[2*i], ey=r[2*j+1]-r[2*i+1], nx=ey, ny=-ex, mx=(r[2*i]+r[2*j])/2, my=(r[2*i+1]+r[2*j+1])/2; if(nx*(mx-cx)+ny*(my-cy)<0){ nx=-nx; ny=-ny; } fr.push(nx*(C.x-mx)+ny*(C.y-my)>0); }      /* the edges that face me: the roofline I can see */
  ctx.save(); ctx.lineJoin='round'; ctx.lineCap='round';
  [[7,.13],[2,.75]].forEach(function(st){ ctx.strokeStyle=mkA(it.rgb,st[1]*k); ctx.lineWidth=st[0]; ctx.beginPath();
    for(var i=0;i<n;i++){ var a=pts[i], b=pts[(i+1)%n]; if(!a||!b||!fr[i]) continue; ctx.moveTo(a[0],a[1]); ctx.lineTo(b[0],b[1]); }
    [lo,hi].forEach(function(e){ if(!e) return; var g=toScr(r[2*e[1]],r[2*e[1]+1],s.z0||0); if(g){ ctx.moveTo(e[0][0],e[0][1]); ctx.lineTo(g[0],g[1]); } }); ctx.stroke(); });
  ctx.restore(); }
/* the banner over the canopy (number and name on the district colour) and the plaque beside the door, painted once per building on a canvas and mapped onto the wall */
function mkSignTex(it){ var c=MK.plaq[it.id]; if(c) return c; c={};
  var b=document.createElement('canvas'); b.width=1024; b.height=110; var g=b.getContext('2d'); g.fillStyle=it.col; g.fillRect(0,0,1024,110); g.fillStyle='rgba(0,0,0,.18)'; g.fillRect(0,96,1024,14);
  g.fillStyle='#fff'; g.textBaseline='middle'; var x=34; if(it.num){ g.font='800 62px system-ui,-apple-system,"Segoe UI",sans-serif'; g.fillText(it.num,x,50); x+=g.measureText(it.num).width+30; g.fillStyle='rgba(255,255,255,.55)'; g.fillRect(x-16,24,3,54); g.fillStyle='#fff'; }
  g.font='600 50px system-ui,-apple-system,"Segoe UI",sans-serif'; var nm=it.name, mw=1024-x-30; while(nm.length>4 && g.measureText(nm).width>mw) nm=nm.slice(0,-2); if(nm!==it.name) nm=nm.replace(/\s+\S*$/,'')+'\u2026'; g.fillText(nm,x,52); c.b=b;
  var p=document.createElement('canvas'); p.width=360; p.height=240; g=p.getContext('2d'); g.fillStyle='#2b2620'; g.fillRect(0,0,360,240); g.strokeStyle='#c9a86a'; g.lineWidth=6; g.strokeRect(12,12,336,216);
  g.fillStyle=it.col; g.fillRect(12,12,336,10); g.fillStyle='#ecd9b0'; g.textBaseline='top'; g.font='700 40px Georgia,"Times New Roman",serif'; g.fillText(it.num||'\u2605',30,40);
  g.font='500 30px Georgia,"Times New Roman",serif'; var words=it.name.split(/\s+/), line='', y=96, lines=0; for(var i=0;i<words.length && lines<3;i++){ var tl=line?line+' '+words[i]:words[i]; if(g.measureText(tl).width>300 && line){ g.fillText(line,30,y); y+=38; lines++; line=words[i]; } else line=tl; }
  if(lines<3 && line) g.fillText(line,30,y); c.p=p; MK.plaq[it.id]=c; return c; }
/* an image on a wall rectangle (a = along the wall, z = up, metres, in the door's frame), in `n` vertical strips each with its own affine map */
function mkWall(ctx, img, d, a0, a1, z0, z1, off, n){
  var K=UM, tx=d.ny, ty=-d.nx, W_=img.width, H_=img.height, dpr=R.dpr||1;
  function P(a,z){ return toScr(d.x+(tx*a+d.nx*off)*K, d.y+(ty*a+d.ny*off)*K, z*K); }
  var lim=3*Math.max(R.w||1400,R.h||900);
  function bad(p){ return !p || p[2]<2.5 || p[0]<-lim || p[0]>lim || p[1]<-lim || p[1]>lim; }                 /* WebKit paints a near-plane quad with a huge transform for seconds: such a strip is skipped */
  for(var s=0;s<n;s++){ var aa=a0+(a1-a0)*s/n, ab=a0+(a1-a0)*(s+1)/n, p0=P(aa,z1), p1=P(ab,z1), p2=P(aa,z0), p3=P(ab,z0); if(bad(p0)||bad(p1)||bad(p2)||bad(p3)) continue;
    var sx0=W_*s/n, sw=W_/n;
    ctx.save(); ctx.beginPath(); ctx.moveTo(p0[0],p0[1]); ctx.lineTo(p1[0],p1[1]); ctx.lineTo(p3[0],p3[1]); ctx.lineTo(p2[0],p2[1]); ctx.closePath(); ctx.clip();
    ctx.setTransform(dpr*(p1[0]-p0[0])/sw, dpr*(p1[1]-p0[1])/sw, dpr*(p2[0]-p0[0])/H_, dpr*(p2[1]-p0[1])/H_, dpr*p0[0], dpr*p0[1]);
    var sw2=Math.min(sw+.5, W_-sx0); ctx.drawImage(img, sx0, 0, sw2, H_, 0, 0, sw2, H_); ctx.restore(); } }
function mkSign(ctx, it){
  var d=it.door; if(!d || IN.on) return; var vx=C.x-d.x, vy=C.y-d.y, vl=Math.hypot(vx,vy)||1; if((vx*d.nx+vy*d.ny)/vl<.17) return;      /* from the street side only, never at a grazing angle */
  var q=toScr(d.x+d.nx*2.3*UM,d.y+d.ny*2.3*UM,3.9*UM); if(!q) return; var dd=Math.hypot(d.x-C.x,d.y-C.y)/UM; if(dd>70 || (dd>45 && it.occ)) return;
  var tx=mkSignTex(it), fa=clamp((70-dd)/20,0,1); ctx.save(); ctx.globalAlpha=fa;
  mkWall(ctx, tx.b, d, -3.4, 3.4, 3.56, 4.28, 2.31, 8);                                                     /* the banner: on the canopy's front edge */
  if(dd<30) mkWall(ctx, tx.p, d, 1.75, 2.65, 1.15, 1.75, .05, 2);                                       /* the plaque: beside the door, at eye level */
  ctx.restore(); }
/* ── the Nearby list ── */
function markListPaint(){
  var u=MK.ui; if(!u) return; var L=markNearest(MK_LIST).filter(function(it){ return it.d<MK_FAR*2; }), sig='';
  u.ct.textContent=L.length?String(L.length):''; if(!MK.near) return;
  for(var i=0;i<u.its.length;i++){ var r=u.its[i], it=L[i]; if(!it){ if(r.it){ r.it=null; r.li.hidden=true; r.t={}; } continue; }
    if(r.li.hidden) r.li.hidden=false; var t=r.t, dd=mkDist(it.d), rel=mkRel(it);
    if(t.id!==it.id){ t.id=it.id; r.n.textContent=it.num||(it.k==='l'?'\u2605':''); r.nm.textContent=it.name; r.dot.style.background=it.col; t.dd=''; }
    if(t.dd!==dd){ t.dd=dd; r.d.textContent=dd; }
    var deg=Math.round(rel*180/Math.PI/5)*5; if(t.deg!==deg){ t.deg=deg; r.ar.style.transform='rotate('+deg+'deg)'; }
    var lab=mkLabel(it); if(t.lab!==lab){ t.lab=lab; r.b.setAttribute('aria-label', lab); }
    var on=it===MK.tgt; if(t.on!==on){ t.on=on; r.b.classList.toggle('on', on); r.b.setAttribute('aria-current', on?'true':'false'); }
    r.it=it; } }
/* ── the mini-map: north up, about MAPR metres round you ── */
var MAPR=230;
function mkMapBg(){
  var Wd=S.W; if(!Wd) return null; if(MK.mapBg && MK.mapVer===Wd.ver) return MK.mapBg; var rd=Wd.roads||[], x0=1e18, y0=1e18, x1=-1e18, y1=-1e18, i;
  for(i=0;i<rd.length;i++){ var r=rd[i]; x0=Math.min(x0,r.x0,r.x1); y0=Math.min(y0,r.y0,r.y1); x1=Math.max(x1,r.x0,r.x1); y1=Math.max(y1,r.y0,r.y1); }
  if(!rd.length){ MK.mapBg={c:null, x0:0, y0:0, s:1}; MK.mapVer=Wd.ver; return MK.mapBg; }
  var sc=Math.min(.9, 1400/Math.max(x1-x0,y1-y0,1)), c=document.createElement('canvas'); c.width=Math.ceil((x1-x0)*sc)+4; c.height=Math.ceil((y1-y0)*sc)+4; var g=c.getContext('2d');
  g.lineCap='round'; g.strokeStyle='rgba(255,255,255,.34)';
  for(i=0;i<rd.length;i++){ var q=rd[i]; g.lineWidth=Math.max(1,(q.w||8)*sc); g.beginPath(); g.moveTo((q.x0-x0)*sc+2,(q.y0-y0)*sc+2); g.lineTo((q.x1-x0)*sc+2,(q.y1-y0)*sc+2); g.stroke(); }
  MK.mapBg={c:c, x0:x0-2/sc, y0:y0-2/sc, s:sc}; MK.mapVer=Wd.ver; return MK.mapBg; }
function markMapPaint(){
  var u=MK.ui; if(!u) return; var cv=u.cv, dpr=Math.min(2,window.devicePixelRatio||1), N=176; if(cv.width!==N*dpr){ cv.width=N*dpr; cv.height=N*dpr; }
  var g=cv.getContext('2d'); if(!g) return; g.setTransform(dpr,0,0,dpr,0,0); g.clearRect(0,0,N,N); var c=N/2, k=(c-6)/(MAPR*UM);
  g.save(); g.beginPath(); g.arc(c,c,c-1,0,6.2832); g.clip(); g.fillStyle='rgba(16,19,30,.86)'; g.fillRect(0,0,N,N);
  var bg=mkMapBg(); if(bg && bg.c){ var f=k/bg.s; g.drawImage(bg.c, c+(bg.x0-S.x)*k, c+(bg.y0-S.y)*k, bg.c.width*f, bg.c.height*f); }
  var L=mkList(); for(var i=0;i<L.length;i++){ var it=L[i], x=c+(it.x-S.x)*k, y=c+(it.y-S.y)*k, dd=Math.hypot(x-c,y-c), lim=c-9; if(dd>lim){ x=c+(x-c)/dd*lim; y=c+(y-c)/dd*lim; }
    if(dd>lim*2.2) continue; var far=dd>lim; g.globalAlpha=far?.55:1; g.fillStyle=it.col; g.strokeStyle='rgba(255,255,255,.9)'; g.lineWidth=1.4; g.beginPath(); g.arc(x,y,far?3:4.5,0,6.2832); g.fill(); g.stroke();
    if(it===MK.tgt){ g.strokeStyle=it.col; g.lineWidth=1.6; g.beginPath(); g.arc(x,y,8,0,6.2832); g.stroke(); } }
  g.globalAlpha=1; var hf=Math.atan((R.w||1400)/2/(C.foc||700)), cone=g.createRadialGradient(c,c,0,c,c,46); cone.addColorStop(0,'rgba(255,209,102,.55)'); cone.addColorStop(1,'rgba(255,209,102,0)');
  g.fillStyle=cone; g.beginPath(); g.moveTo(c,c); g.arc(c,c,46,S.yaw-hf,S.yaw+hf); g.closePath(); g.fill();
  g.fillStyle='#fff'; g.strokeStyle='rgba(0,0,0,.45)'; g.lineWidth=1.5; g.beginPath(); g.arc(c,c,4.2,0,6.2832); g.fill(); g.stroke(); g.restore();
  g.strokeStyle='rgba(255,255,255,.22)'; g.lineWidth=1; g.beginPath(); g.arc(c,c,c-1,0,6.2832); g.stroke(); }
/* ── keys (from roam's own capture handler; nothing new on window) ── */
function markKey(e){
  if(!MK.on || IN.on) return false; var k=e.key;
  if(MK.auto && (keyName(e) || k==='Escape')){ markStop('Stopped.'); return k==='Escape'; }
  if(k==='Enter' && MK.tgt && !MK.auto && !DR.cur){ markWalk(MK.tgt); return true; }
  if(MK.turn && keyName(e)) MK.turn=null;
  if(e.repeat) return false;
  if(k==='n'||k==='N'||e.code==='KeyN'){ markNext(e.shiftKey?-1:1); return true; }
  if(k==='g'||k==='G'||e.code==='KeyG'){ if(!MK.tgt) markNext(1); if(MK.tgt) markWalk(MK.tgt); return true; }
  if(k==='m'||k==='M'||e.code==='KeyM'){ markMapToggle(); return true; }
  if((k==='e'||k==='E'||e.code==='KeyE') && !DR.cur){ var it=mkLmHere(); if(it){ markOpenLm(it); return true; } }
  return false; }
/* a landmark with a page within MK_LMOPEN m and in front of you */
function mkLmHere(){ var L=mkList(), best=null; for(var i=0;i<L.length;i++){ var it=L[i]; if(it.k!=='l') continue; var near=it.s?mkGoal(it):[it.x,it.y]; var d=Math.hypot(near[0]-S.x,near[1]-S.y)/UM;
    if(d<MK_LMOPEN && Math.abs(mkRel(it))<1.2 && (!best||d<best.dd)){ best=it; best.dd=d; } } return best; }
function mkOpenPage(pg){ var q=String(pg||'').split(':'), k=q.slice(1).join(':'); if(!k||typeof window.showDetail!=='function') return; var t=q[0];
  if(t==='index'||t==='char'||t==='node') window.showDetail(t, k); }
function markOpenLm(it){
  if(DR.busy || !S.on || typeof window.showDetail!=='function') return false; DR.busy=1; var tok=++DR.tok;
  DR.mem={x:S.x, y:S.y, yaw:S.yaw, pitch:S.pitch, view:S.view, id:null, page:it.page, name:it.name, ex:S.x, ey:S.y, eyaw:S.yaw, real:!!S.real};
  clearKeys(); markStop(null); veil(1, reduced()?0:FADE_MS); setTimeout(function(){ if(tok!==DR.tok) return; DR.busy=2; openDetail(DR.mem); }, reduced()?0:FADE_MS); return true; }
function markReset(){ markFadeStop(); mkPillOff(); MK.hi=null; MK.auto=null; MK.turn=null; MK.tgt=null; MK.hov=null; MK.last=0; MK.list=null; MK.ver=-1; MK.mapBg=null; MK.mapVer=-1;
  for(var i=0;i<MK.labs.length;i++){ var lb=MK.labs[i]; lb.it=null; lb.t={}; lb.el.style.opacity='0'; } }
var MARKAPI={ layout:mkLayout, pri:mkPri, want:mkWant, list:function(){ return mkList().map(function(it){ return {id:it.id, k:it.k, num:it.num, name:it.name, col:it.col, x:it.x, y:it.y, h:it.h, d:it.d, a:it.a, occ:it.occ, door:!!it.door, page:it.page}; }); },
  state:function(){ var s=MK.labs.filter(function(l){ return l.it; }).map(function(l){ return {id:l.it.id, a:l.it.a, occ:l.it.occ, x:l.it.pl&&l.it.pl.x, y:l.it.pl&&l.it.pl.y, w:l.it.mw&&l.it.mw[0]}; });
    return {labels:s, path:MK.auto&&MK.auto.path?MK.auto.path.length:0, astar:MK.astar||0, tgt:MK.tgt&&MK.tgt.id, hov:MK.hov&&MK.hov.id, auto:!!MK.auto, turn:!!MK.turn, map:MK.map, near:MK.near, said:MK.said, pool:MK.labs.length}; },
  trip:function(){ return {last:MK.last1||null, trips:MK.trips||0, arrived:MK.arrived||0}; }, go:function(id){ var it=mkList().filter(function(q){ return q.id===id; })[0]; return markWalk(it); },
  next:markNext, aim:function(id){ var it=mkList().filter(function(q){ return q.id===id; })[0]; return markAim(it,true); }, walk:markWalk, stop:markStop, steer:markSteer, nearest:function(n){ return markNearest(n).map(function(it){ return it.id; }); },
  enable:function(v){ MK.on=!!v; if(!MK.on && MK.layer){ MK.layer.style.visibility='hidden'; } return MK.on; },
  toggleMap:markMapToggle, toggleNear:markNearToggle, occ:mkOcc, cfg:{MAX:MK_MAX, FAR:MK_FAR, FULL:MK_FULL} };
"""

CSS_MARK = r"""
  #pal-ride .mk-go{position:absolute;left:50%;bottom:100px;transform:translateX(-50%);display:flex;align-items:center;gap:10px;padding:7px 9px 7px 15px;border-radius:999px;background:rgba(14,16,26,.7);border:1px solid rgba(255,255,255,.18);color:#fff;font:600 13px system-ui,-apple-system,sans-serif;opacity:0;transition:opacity .3s;pointer-events:auto;max-width:min(80vw,520px);}
  #pal-ride .mk-go span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  #pal-ride .mk-go button{flex:none;width:24px;height:24px;border-radius:50%;border:0;background:rgba(255,255,255,.18);color:#fff;cursor:pointer;font-size:12px;}
  #pal-ride .mk-veil{position:absolute;inset:0;background:#05060a;opacity:0;transition:opacity .25s ease;pointer-events:none;display:flex;align-items:center;justify-content:center;color:rgba(255,255,255,.75);font:500 14px system-ui,-apple-system,sans-serif;z-index:5;}
  #pal-ride .mk-layer{position:absolute;left:0;top:0;right:0;bottom:0;pointer-events:none;overflow:hidden;}
  #pal-ride .mk-lab{position:absolute;left:0;top:0;height:26px;will-change:transform,opacity;pointer-events:none;}
  #pal-ride .mk-card{position:relative;display:flex;align-items:center;gap:7px;height:26px;box-sizing:border-box;padding:0 10px 0 4px;border-radius:13px;pointer-events:auto;cursor:pointer;
    background:rgba(16,18,28,.74);border:1px solid rgba(255,255,255,.14);box-shadow:0 2px 10px rgba(0,0,0,.28);color:#fff;font:600 12.5px/1 system-ui,-apple-system,"Segoe UI",sans-serif;white-space:nowrap;}
  #pal-ride .mk-no{flex:none;font-style:normal;font-weight:700;font-size:11.5px;padding:4px 6px;border-radius:9px;background:var(--mk-c,#8a93b0);color:#fff;text-shadow:0 1px 1px rgba(0,0,0,.25);}
  #pal-ride .mk-lab.lm .mk-no{background:#d8b35a;color:#2b2210;text-shadow:none;}
  #pal-ride .mk-nm{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;font-weight:600;}
  #pal-ride .mk-dd{flex:none;font-weight:500;font-size:11px;opacity:.62;}
  #pal-ride .mk-ln{position:absolute;top:26px;left:0;width:1px;height:100px;transform-origin:0 0;background:linear-gradient(rgba(255,255,255,.75),var(--mk-c,#fff));pointer-events:none;}
  #pal-ride .mk-ln::after{content:"";position:absolute;left:-2px;bottom:-3px;width:5px;height:5px;border-radius:50%;background:var(--mk-c,#fff);box-shadow:0 0 0 1.5px rgba(255,255,255,.85);}
  #pal-ride .mk-lab.occ .mk-card{background:rgba(16,18,28,.5);}
  #pal-ride .mk-lab.hot .mk-card{border-color:var(--mk-c,#fff);box-shadow:0 0 0 1px var(--mk-c,#fff),0 4px 16px rgba(0,0,0,.35);}
  #pal-ride .mk-hint{position:absolute;left:0;top:-21px;font:600 10.5px/1 system-ui,-apple-system,sans-serif;letter-spacing:.02em;color:#fff;opacity:0;white-space:pre;padding:3px 7px;border-radius:7px;background:rgba(16,18,28,.62);}
  #pal-ride .mk-lab.hot .mk-hint{opacity:.92;}
  #pal-ride .mk-near{position:absolute;left:24px;bottom:22px;width:268px;box-sizing:border-box;padding:6px;border-radius:16px;background:rgba(14,16,26,.66);border:1px solid rgba(255,255,255,.14);pointer-events:auto;color:#fff;}
  #pal-ride .mk-near.shut{width:auto;}
  #pal-ride .mk-hd{display:flex;align-items:center;gap:4px;}
  #pal-ride .mk-near button{cursor:pointer;color:#fff;background:transparent;border:0;font:600 12.5px/1.2 system-ui,-apple-system,"Segoe UI",sans-serif;border-radius:10px;}
  #pal-ride .mk-near button:hover{background:rgba(255,255,255,.08);}
  #pal-ride .mk-near button:focus-visible{outline:2px solid #ffd166;outline-offset:1px;}
  #pal-ride .mk-tg{flex:1;display:flex;align-items:center;gap:6px;padding:5px 8px;text-align:left;}
  #pal-ride .mk-tg svg{width:12px;height:12px;flex:none;transition:transform .2s ease;}
  #pal-ride .mk-near.shut .mk-tg svg{transform:rotate(-90deg);}
  #pal-ride .mk-ct{font-style:normal;font-weight:500;opacity:.55;margin-left:auto;}
  #pal-ride .mk-mb{flex:none;width:30px;height:28px;display:grid;place-items:center;}
  #pal-ride .mk-mb svg{width:16px;height:16px;}
  #pal-ride .mk-mb[aria-pressed=true]{background:rgba(255,209,102,.18);color:#ffd166;}
  #pal-ride .mk-ol{list-style:none;margin:4px 0 0;padding:0;}
  #pal-ride .mk-it{width:100%;display:flex;align-items:center;gap:7px;padding:6px 8px !important;text-align:left;font-weight:500 !important;}
  #pal-ride .mk-it.on{background:rgba(255,255,255,.1);}
  #pal-ride .mk-dot{flex:none;width:9px;height:9px;border-radius:50%;box-shadow:0 0 0 2px rgba(255,255,255,.16);}
  #pal-ride .mk-in{flex:none;font-weight:700;font-size:11.5px;opacity:.85;}
  #pal-ride .mk-iname{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600;}
  #pal-ride .mk-id{flex:none;font-style:normal;font-size:11.5px;opacity:.6;}
  #pal-ride .mk-ar{flex:none;width:12px;height:12px;color:#ffd166;transition:transform .25s ease;}
  #pal-ride .mk-keys{margin:5px 8px 3px;font:500 10.5px/1.4 system-ui,-apple-system,sans-serif;opacity:.5;}
  #pal-ride .mk-keys kbd{font:600 9.5px/1 system-ui,-apple-system,sans-serif;padding:1px 4px;border-radius:4px;border:1px solid rgba(255,255,255,.3);margin:0 2px 0 6px;}
  #pal-ride .mk-keys kbd:first-child{margin-left:0;}
  #pal-ride .mk-near.shut .mk-ol,#pal-ride .mk-near.shut .mk-keys{display:none;}
  #pal-ride .mk-map{position:absolute;right:24px;bottom:22px;width:176px;height:176px;border-radius:50%;box-shadow:0 4px 18px rgba(0,0,0,.35);opacity:0;visibility:hidden;transition:opacity .25s ease,visibility 0s linear .25s;}
  #pal-ride .mk-map.on{opacity:1;visibility:visible;transition:opacity .25s ease;}
  #pal-ride .mk-map canvas{width:176px;height:176px;display:block;border-radius:50%;}
  #pal-ride .mk-mn{position:absolute;left:50%;top:5px;transform:translateX(-50%);font:700 10px/1 system-ui,-apple-system,sans-serif;color:#ffd166;}
  #pal-ride .rm-pin .mk-ent{flex:none;font-weight:500;opacity:.75;}
  @media (max-width:900px){ #pal-ride .mk-near{width:220px;} #pal-ride .mk-map{width:132px;height:132px;} #pal-ride .mk-map canvas{width:132px;height:132px;} }
  @media (prefers-reduced-motion: reduce){ #pal-ride .mk-tg svg,#pal-ride .mk-ar,#pal-ride .mk-map,#pal-ride .mk-map.on{transition:none;} }
"""
