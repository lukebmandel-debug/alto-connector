"""Mind Palace on a phone: the map page, drawn like the Apple Maps app (the Alto glass look kept).

The MAP button opens the city full-bleed. One finger pans and the map coasts on after you let go, two fingers pinch
around where they are, a double tap zooms in, a two-finger tap zooms out, and nothing scrolls the page behind it. A
bottom sheet with three heights (peek: a search field; half; full) rides over the map on a spring: drag its handle or
its header, flick it, and it settles on the nearest height. Tap a building and its place card fills the sheet (number,
title, what it holds, its unit and neighbourhood, the nearest corner, floors, Directions, Open, Share) while the
building is lit on the map; Open goes inside as it always did. Search finds buildings, floors, landmarks and stations.
Directions (palace_directions.py) plans building to building along the streets and the real transit lines, inside the
same sheet.

JS spliced into the palace's own script (it uses the palace's tables, drawing and routing). The round Close, the
zoom pill and the whole-city button keep their old classes (.pm-close, .pm-zoom with data-z in/out/fit).
"""

MOBILE_CSS = r"""
  /* ═══ the phone's map (palace_mobile.py): delimited block ═══ */
  html.pm-open,html.pm-open body{overflow:hidden !important;overscroll-behavior:none;}
  #pal-mmap{position:fixed;inset:0;z-index:4000;display:none;overflow:hidden;background:var(--page-grad,var(--bg));background-attachment:fixed;touch-action:none;-webkit-user-select:none;user-select:none;-webkit-touch-callout:none;--pm-sh:82px;}
  #pal-mmap.on{display:block;}
  html.alto-bg-map #pal-mmap{background:var(--alto-bg);background-attachment:scroll;}   /* the map ground chosen for this city (palace_backgrounds.py) */
  #pal-mmap .pm-scroll{position:absolute;inset:0;overflow:hidden;touch-action:none;}
  #pal-mmap .pm-scroll > svg{position:absolute;left:0;top:0;transform-origin:0 0;max-width:none;}
  #pal-mmap .pm-sheet{background:color-mix(in srgb,var(--surface) 84%,transparent) !important;}
  #pal-mmap .pm-close,#pal-mmap .pm-pill,#pal-mmap .pm-city,#pal-mmap .pm-sheet{background:var(--card-glass-bg,var(--surface));color:var(--muted);border:1px solid var(--card-glass-border,var(--border));
    -webkit-backdrop-filter:blur(18px) saturate(190%);backdrop-filter:blur(18px) saturate(190%);box-shadow:0 10px 26px var(--node-rest-shadow),inset 0 0 0 .5px var(--card-glass-rim);}
  #pal-mmap .pm-close{position:absolute;right:12px;top:calc(10px + env(safe-area-inset-top,0px));z-index:7;width:44px;height:44px;border-radius:50%;padding:0;display:flex;align-items:center;justify-content:center;}
  #pal-mmap .pm-zoom{position:absolute;right:12px;bottom:calc(var(--pm-sh,82px) + 14px);z-index:4;display:flex;flex-direction:column;align-items:center;gap:12px;transition:opacity .18s;}
  #pal-mmap.pm-tall .pm-zoom{opacity:0;pointer-events:none;}
  #pal-mmap .pm-pill{display:flex;flex-direction:column;width:44px;border-radius:22px;}
  #pal-mmap .pm-zoom button{display:flex;align-items:center;justify-content:center;padding:0;margin:0;border:0;background:none;color:inherit;-webkit-tap-highlight-color:transparent;}
  #pal-mmap .pm-pill button{width:44px;height:48px;}
  #pal-mmap .pm-pill button:first-child{border-radius:22px 22px 0 0;}
  #pal-mmap .pm-pill button:last-child{border-radius:0 0 22px 22px;}
  #pal-mmap .pm-div{height:1px;margin:0 10px;background:color-mix(in srgb,var(--muted) 45%,transparent);}
  #pal-mmap .pm-city{width:44px;height:44px;border-radius:50%;padding:0;}
  #pal-mmap .pm-zoom button:active,#pal-mmap .pm-close:active{color:var(--text);background:color-mix(in srgb,var(--text) 10%,transparent);}
  #pal-mmap svg.pm-ic{display:block;}
  #pal-mmap svg{display:block;}
  #pal-mmap .pm-sel .nb-r,#pal-mmap .pm-sel .b-tag{stroke-width:3.4;}
  .pal-svg .pl-sel{pointer-events:none;}

  /* the bottom sheet: peek (a search field) · half · full, on a spring */
  #pal-mmap .pm-sheet{position:absolute;left:0;right:0;bottom:0;z-index:5;height:var(--pm-full,720px);box-sizing:border-box;display:flex;flex-direction:column;border-radius:20px 20px 0 0;border-bottom:0;color:var(--text);
    touch-action:none;will-change:transform;font:14px/1.35 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}
  #pal-mmap .pm-grab{flex:none;height:22px;display:flex;align-items:center;justify-content:center;touch-action:none;cursor:grab;}
  #pal-mmap .pm-grab i{display:block;width:38px;height:5px;border-radius:3px;background:color-mix(in srgb,var(--muted) 55%,transparent);}
  #pal-mmap .pm-head{flex:none;padding:0 14px 10px;min-height:44px;box-sizing:border-box;touch-action:none;}
  #pal-mmap .pm-body{flex:1;min-height:0;overflow:hidden;padding:0 14px calc(28px + env(safe-area-inset-bottom,0px));overscroll-behavior:contain;-webkit-overflow-scrolling:touch;}
  #pal-mmap .pm-sheet.full .pm-body{overflow-y:auto;touch-action:pan-y;}
  #pal-mmap .pm-search{display:flex;align-items:center;gap:8px;height:44px;box-sizing:border-box;padding:0 12px;border-radius:12px;background:color-mix(in srgb,var(--text) 7%,transparent);flex:1;min-width:0;color:var(--muted);}
  #pal-mmap .pm-q{flex:1;min-width:0;height:100%;border:0;outline:0;background:none;color:var(--text);font:inherit;font-size:16px;-webkit-appearance:none;appearance:none;-webkit-user-select:text;user-select:text;}
  #pal-mmap .pm-q::placeholder{color:var(--muted);}
  #pal-mmap .pm-hrow{display:flex;align-items:center;gap:10px;}
  #pal-mmap .pm-btn{flex:none;width:44px;height:44px;border-radius:50%;border:0;background:var(--accent,#6d5bd0);color:#fff;display:flex;align-items:center;justify-content:center;padding:0;-webkit-tap-highlight-color:transparent;}
  #pal-mmap .pm-btn.ghost{background:color-mix(in srgb,var(--text) 8%,transparent);color:var(--muted);}
  #pal-mmap .pm-btn:active{filter:brightness(.85);}
  #pal-mmap .pm-pt{flex:1;min-width:0;} #pal-mmap .pm-pt small{display:block;font-size:11.5px;font-weight:750;letter-spacing:.05em;color:var(--accent,#6d5bd0);}
  #pal-mmap .pm-pt b{display:block;font-size:20px;line-height:1.2;font-weight:750;} #pal-mmap .pm-pt span{display:block;color:var(--muted);font-size:13px;margin-top:1px;}
  #pal-mmap .pm-acts{display:flex;gap:8px;margin:2px 0 14px;}
  #pal-mmap .pm-act{flex:1;min-height:48px;border-radius:13px;border:0;background:color-mix(in srgb,var(--accent,#6d5bd0) 13%,transparent);color:var(--accent,#6d5bd0);font:700 13px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;padding:4px 6px;-webkit-tap-highlight-color:transparent;}
  #pal-mmap .pm-act.pri{background:var(--accent,#6d5bd0);color:#fff;} #pal-mmap .pm-act:active{filter:brightness(.88);}
  #pal-mmap .pm-desc{margin:0 0 14px;font-size:15px;line-height:1.45;color:var(--text);}
  #pal-mmap .pm-info{margin:0 0 12px;padding:0;list-style:none;border-radius:13px;background:color-mix(in srgb,var(--text) 5%,transparent);}
  #pal-mmap .pm-info li{display:flex;gap:12px;align-items:baseline;padding:11px 14px;border-bottom:1px solid color-mix(in srgb,var(--muted) 18%,transparent);} #pal-mmap .pm-info li:last-child{border:0;}
  #pal-mmap .pm-info small{flex:none;width:96px;color:var(--muted);font-size:12.5px;} #pal-mmap .pm-info span{flex:1;min-width:0;font-weight:560;}
  #pal-mmap .pm-info i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px;}
  #pal-mmap .pm-rel{display:block;margin:5px 2px;font-size:13px;color:var(--muted);} #pal-mmap .pm-rel i{display:inline-block;width:14px;height:4px;border-radius:2px;vertical-align:middle;margin-right:7px;}
  #pal-mmap .pm-h6{margin:16px 2px 4px;font-size:12px;font-weight:750;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);}
  #pal-mmap .pm-list{margin:0;padding:0;list-style:none;} #pal-mmap .pm-list li{display:flex;gap:12px;align-items:center;min-height:52px;padding:6px 4px;border-bottom:1px solid color-mix(in srgb,var(--muted) 20%,transparent);-webkit-tap-highlight-color:transparent;}
  #pal-mmap .pm-list li:active{background:color-mix(in srgb,var(--text) 7%,transparent);}
  #pal-mmap .pm-list .pm-bd{flex:none;min-width:36px;height:32px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-weight:750;font-size:12px;padding:0 5px;box-sizing:border-box;background:color-mix(in srgb,var(--bd,var(--accent,#6d5bd0)) 16%,transparent);color:var(--bd,var(--accent,#6d5bd0));}
  #pal-mmap .pm-list b{display:block;font-size:15px;font-weight:650;} #pal-mmap .pm-list small{display:block;color:var(--muted);font-size:12.5px;margin-top:1px;}
  #pal-mmap .pm-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:3px;} #pal-mmap .pm-chip{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:14px;font-size:12.5px;font-weight:650;background:color-mix(in srgb,var(--tc) 16%,transparent);color:var(--text);}
  #pal-mmap .pm-chip i{width:10px;height:10px;border-radius:50%;background:var(--tc);margin:0;}
  @media (prefers-reduced-motion: reduce){#pal-mmap .pm-zoom{transition:none;}}
"""

MOBILE_JS = r"""
/* ═══ the phone's map (palace_mobile.py): a full-bleed map, a bottom sheet, a place card ═══ */
var PM={H:0, W:0, sh:82, z:.46, sx:0, sy:0, det:'peek', mode:'home', sel:null, safeT:0, safeB:0, g:null, d:null, anim:null, mom:null, spring:null, lastTap:null, relT:0, sc:null, sheet:null, head:null, body:null, ad:null, lastTouch:0};
function pmReduced(){ return window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches; }
function pmMeasure(){ var b=MM.box; if(!b) return; PM.W=b.clientWidth||window.innerWidth; PM.H=b.clientHeight||window.innerHeight;
  var pr=document.createElement('div'); pr.style.cssText='position:fixed;left:0;top:0;visibility:hidden;padding:env(safe-area-inset-top,0px) 0 env(safe-area-inset-bottom,0px) 0;'; document.body.appendChild(pr);
  var cs=getComputedStyle(pr); PM.safeT=parseFloat(cs.paddingTop)||0; PM.safeB=parseFloat(cs.paddingBottom)||0; pr.remove();
  b.style.setProperty('--pm-full', pmDet().full+'px'); }
function pmDet(){ var H=PM.H||window.innerHeight; return {peek:82+PM.safeB, half:Math.round(H*.46), full:Math.round(H-(PM.safeT+62))}; }
function pmZmin(){ var h=PM.H-pmDet().peek-70; return Math.max(.02, Math.min((PM.W-24)/VW, h/VH)); }
/* ── the view: zoom z, and sx/sy = how far the city is slid left/up (screen = (map + margin) · z − s) ── */
function pmClamp(z, sx, sy){ z=Math.max(pmZmin(), Math.min(2.2, z));
  var cw=VW*z, ch=VH*z, hv=PM.H-Math.min(PM.sh, pmDet().half);
  sx = cw<=PM.W ? (cw-PM.W)/2 : Math.max(-50, Math.min(cw-PM.W+50, sx));
  sy = ch<=hv ? (ch-hv)/2 : Math.max(-70, Math.min(ch-hv+40, sy));
  return [z, sx, sy]; }
function pmCommit(z){ var sv=MM.svg; MM.z=z; sv.setAttribute('width', VW*z); sv.setAttribute('height', VH*z); sv.style.setProperty('--pz', z); sv.style.setProperty('--tw', tw(z));
  sv.classList.toggle('far', z<.42); sv.classList.toggle('mid', z<.8); clearTimeout(PM.relT);
  PM.relT=setTimeout(function(){ if(window._palLm) window._palLm.relayout(sv, MM.z); sizeChips(sv); }, 140); }
function pmApply(z, sx, sy){ var c=pmClamp(z, sx, sy); z=c[0]; sx=c[1]; sy=c[2]; PM.z=z; PM.sx=sx; PM.sy=sy;
  var s=z/MM.z; if(s<.55 || s>1.8){ pvIn(MM.svg); pmCommit(z); s=1; }
  MM.svg.style.transform='translate('+(-sx).toFixed(2)+'px,'+(-sy).toFixed(2)+'px) scale('+s.toFixed(5)+')'; if(window._nbMoving) window._nbMoving(); }
function pmSettle(){ if(Math.abs(PM.z-MM.z)>1e-6){ if(Math.abs(Math.log(PM.z/MM.z))>.12) pvIn(MM.svg); pmCommit(PM.z); MM.svg.style.transform='translate('+(-PM.sx).toFixed(2)+'px,'+(-PM.sy).toFixed(2)+'px) scale(1)'; } }
function pmStop(){ if(PM.anim){ cancelAnimationFrame(PM.anim); PM.anim=null; pmSettle(); } if(PM.mom){ cancelAnimationFrame(PM.mom); PM.mom=null; } }
/* a map point at the middle of the part of the map the sheet leaves free, at zoom z, gliding */
function pmGoto(mx, my, z, ms, sheetH){ pmStop(); var hv=PM.H-(sheetH==null?PM.sh:sheetH), z0=PM.z;
  z=Math.max(pmZmin(), Math.min(2.2, z==null?z0:z));
  var cx0=(PM.sx+PM.W/2)/z0-MX, cy0=(PM.sy+Math.min(PM.H-PM.sh,PM.H)/2)/z0-MY;
  if(pmReduced()) ms=1; ms=ms||520; var t0=performance.now();
  (function step(t){ var k=Math.min(1,(t-t0)/ms), e=k<.5?4*k*k*k:1-Math.pow(-2*k+2,3)/2, zz=Math.exp(Math.log(z0)+(Math.log(z)-Math.log(z0))*e),
      cx=cx0+(mx-cx0)*e, cy=cy0+(my-cy0)*e;
    pmApply(zz, (cx+MX)*zz-PM.W/2, (cy+MY)*zz-hv/2);
    if(k<1) PM.anim=requestAnimationFrame(step); else { PM.anim=null; pmSettle(); } })(t0); }
function pmFly(x, y, hint){ var det=pmDet(), h=(PM.det==='full'||(PM.det==='peek'&&PM.mode!=='home'))?det.half:Math.min(PM.sh,det.half);
  pmGoto(x, y, hint==='step'?Math.max(PM.z,1.0):Math.max(PM.z,.85), 520, h); }
function pmFitBox(b){ var det=pmDet(), hv=PM.H-Math.min(Math.max(PM.sh,det.half),det.half)-80, w=(b[2]-b[0])+200, h=(b[3]-b[1])+200;
  pmGoto((b[0]+b[2])/2, (b[1]+b[3])/2, Math.min(1.3, (PM.W-30)/w, hv/h), 600, Math.min(PM.sh,det.half)); }
function pmFitCity(){ pmGoto(M.W/2, M.H/2, pmZmin()*1.02, 560, PM.sh); }
function pmZoomBy(f, ax, ay){ pmStop(); var z0=PM.z, z=Math.max(pmZmin(), Math.min(2.2, z0*f)), sx0=PM.sx, sy0=PM.sy, ms=pmReduced()?1:340, t0=performance.now();
  if(ax==null){ ax=PM.W/2; ay=(PM.H-PM.sh)/2; }
  var mx=(sx0+ax)/z0, my=(sy0+ay)/z0;
  (function step(t){ var k=Math.min(1,(t-t0)/ms), e=k<.5?2*k*k:1-Math.pow(-2*k+2,2)/2, zz=Math.exp(Math.log(z0)+(Math.log(z)-Math.log(z0))*e);
    pmApply(zz, mx*zz-ax, my*zz-ay); if(k<1) PM.anim=requestAnimationFrame(step); else { PM.anim=null; pmSettle(); } })(t0); }

/* ── the sheet: three heights, a spring, a handle ── */
function pmSet(h){ var det=pmDet(); h=h>det.full?det.full+(h-det.full)*.22:h<det.peek?det.peek-(det.peek-h)*.22:h; PM.sh=h;
  var sh=PM.sheet; sh.style.transform='translateY('+(det.full-h).toFixed(2)+'px)'; MM.box.style.setProperty('--pm-sh', h.toFixed(1)+'px');
  MM.box.classList.toggle('pm-tall', h>PM.H*.62); }
function pmDetOf(h){ var d=pmDet(), best='peek', bd=1e9; ['peek','half','full'].forEach(function(k){ var q=Math.abs(h-d[k]); if(q<bd){ bd=q; best=k; } }); return best; }
function pmSnap(name, v0){ var det=pmDet(), target=det[name]; PM.det=name; PM.sheet.classList.toggle('full', name==='full'); if(name!=='full') PM.body.scrollTop=0;
  if(PM.spring) cancelAnimationFrame(PM.spring); if(pmReduced()){ pmSet(target); return; }
  var x=PM.sh, v=v0||0, last=performance.now();
  (function f(t){ var dt=Math.min(.032,(t-last)/1000); last=t; var a=-190*(x-target)-23*v; v+=a*dt; x+=v*dt; pmSet(x);
    if(Math.abs(x-target)<.4 && Math.abs(v)<5){ pmSet(target); PM.spring=null; } else PM.spring=requestAnimationFrame(f); })(last); }
function pmSheetTouch(){
  var sh=PM.sheet, D=null;
  function ys(e){ return e.touches[0].clientY; }
  sh.addEventListener('touchstart', function(e){ if(e.touches.length!==1){ D=null; return; } if(e.target.closest('input,textarea')&&!e.target.closest('.pm-grab')) { }
    if(PM.spring){ cancelAnimationFrame(PM.spring); PM.spring=null; }
    var inBody=!!e.target.closest('.pm-body');
    D={y0:ys(e), h0:PM.sh, body:inBody, top:PM.body.scrollTop, active:false, s:[[performance.now(), ys(e)]]}; }, {passive:true});
  sh.addEventListener('touchmove', function(e){ if(!D || e.touches.length!==1) return; var y=ys(e), dy=y-D.y0;
    if(!D.active){
      if(D.body){ if(PM.det==='full' && (D.top>0 || dy<=0 || PM.body.scrollTop>0)){ D=null; return; } if(Math.abs(dy)<6) return; }
      else if(Math.abs(dy)<3) return;
      D.active=true; D.y0=y; D.h0=PM.sh; dy=0; }
    if(e.cancelable) e.preventDefault(); D.s.push([performance.now(), y]); if(D.s.length>8) D.s.shift(); pmSet(D.h0-dy); }, {passive:false});
  function end(){ if(!D) return; var d=D; D=null; if(!d.active) return;
    var s=d.s, a=s[0], b=s[s.length-1], v=0; for(var i=0;i<s.length;i++) if(b[0]-s[i][0]<=110){ a=s[i]; break; } if(b[0]>a[0]) v=-(b[1]-a[1])/(b[0]-a[0])*1000;   /* px/s, up is positive */
    var det=pmDet(), order=['peek','half','full'], cur=pmDetOf(PM.sh), idx=order.indexOf(cur), name;
    if(Math.abs(v)>420){ var near=pmDetOf(d.h0); idx=order.indexOf(near); if(v>0) idx=Math.min(2, idx+(v>1900?2:1)); else idx=Math.max(0, idx-(v<-1900?2:1)); name=order[idx]; }
    else name=pmDetOf(PM.sh+v*.18);
    if(document.activeElement && document.activeElement.classList.contains('pm-q') && name!=='full') document.activeElement.blur();
    pmSnap(name, -v); }
  sh.addEventListener('touchend', end, {passive:true}); sh.addEventListener('touchcancel', end, {passive:true});
}

/* ── the map's own fingers: pan with momentum, pinch around the fingers, double tap in, two-finger tap out ── */
function pmGestures(){
  var sc=PM.sc, G=null;
  function pt(e,i){ return [e.touches[i].clientX, e.touches[i].clientY]; }
  function dist(e){ return Math.hypot(e.touches[0].clientX-e.touches[1].clientX, e.touches[0].clientY-e.touches[1].clientY); }
  sc.addEventListener('touchstart', function(e){ PM.lastTouch=Date.now(); pmStop(); if(document.activeElement && document.activeElement.blur && document.activeElement.classList.contains('pm-q')) document.activeElement.blur();
    if(e.touches.length===1){ var p=pt(e,0); G={m:'one', x0:p[0], y0:p[1], lx:p[0], ly:p[1], t0:Date.now(), moved:false, s:[[performance.now(),p[0],p[1]]], two:false}; }
    else if(e.touches.length===2){ var a=pt(e,0), b=pt(e,1), keepT=G&&G.t0||Date.now(); G={m:'two', d0:dist(e), z0:PM.z, mx0:(a[0]+b[0])/2, my0:(a[1]+b[1])/2, sx0:PM.sx, sy0:PM.sy, t0:Date.now(), moved:false, zt:PM.z}; }
    else G=null;
    if(e.cancelable) e.preventDefault(); }, {passive:false});
  sc.addEventListener('touchmove', function(e){ if(!G) return; if(e.cancelable) e.preventDefault();
    if(G.m==='one' && e.touches.length===1){ var p=pt(e,0); if(!G.moved && Math.hypot(p[0]-G.x0,p[1]-G.y0)<8) return; G.moved=true;
      pmApply(PM.z, PM.sx-(p[0]-G.lx), PM.sy-(p[1]-G.ly)); G.lx=p[0]; G.ly=p[1]; G.s.push([performance.now(),p[0],p[1]]); if(G.s.length>10) G.s.shift(); }
    else if(G.m==='two' && e.touches.length===2){ var a=pt(e,0), b=pt(e,1), mx=(a[0]+b[0])/2, my=(a[1]+b[1])/2, d=dist(e);
      if(Math.abs(d-G.d0)>9 || Math.hypot(mx-G.mx0,my-G.my0)>12) G.moved=true; if(!G.moved) return;
      var zt=Math.max(pmZmin(), Math.min(2.2, G.z0*d/G.d0)), r=zt/G.z0; G.zt=zt;
      pmApply(zt, (G.sx0+G.mx0)*r-mx, (G.sy0+G.my0)*r-my); } }, {passive:false});
  function finish(e){ if(!G) return; var g=G;
    if(g.m==='two'){ if(e.touches.length>=2) return;
      if(!g.moved && Date.now()-g.t0<320){ pmZoomBy(.5, g.mx0, g.my0); G=null; if(e.cancelable) e.preventDefault(); return; }
      pmSettle();
      if(e.touches.length===1){ var p=pt(e,0); G={m:'one', x0:p[0], y0:p[1], lx:p[0], ly:p[1], t0:Date.now(), moved:true, s:[[performance.now(),p[0],p[1]]], two:true}; } else G=null; return; }
    G=null; if(e.touches.length) return;
    if(!g.moved){ if(Date.now()-g.t0>450 || g.two) return; var c=e.changedTouches[0]; if(e.cancelable) e.preventDefault();
      var now=Date.now(), lt=PM.lastTap;
      if(lt && now-lt.t<330 && Math.hypot(c.clientX-lt.x,c.clientY-lt.y)<32){ PM.lastTap=null; pmZoomBy(2, c.clientX, c.clientY); return; }
      PM.lastTap={t:now, x:c.clientX, y:c.clientY}; pmTap(c.clientX, c.clientY); return; }
    var s=g.s, b=s[s.length-1], a=s[0]; for(var i=0;i<s.length;i++) if(b[0]-s[i][0]<=90){ a=s[i]; break; }
    var dt=b[0]-a[0], vx=0, vy=0; if(dt>0 && performance.now()-b[0]<80){ vx=(b[1]-a[1])/dt; vy=(b[2]-a[2])/dt; }
    if(Math.hypot(vx,vy)>.12 && !pmReduced()){ var last=performance.now();
      (function mo(t){ var dt2=Math.min(40,t-last); last=t; var f=Math.pow(.9972, dt2); vx*=f; vy*=f; pmApply(PM.z, PM.sx-vx*dt2, PM.sy-vy*dt2);
        if(Math.hypot(vx,vy)>.025) PM.mom=requestAnimationFrame(mo); else PM.mom=null; })(last); } }
  sc.addEventListener('touchend', finish, {passive:false}); sc.addEventListener('touchcancel', function(){ G=null; pmSettle(); }, {passive:true});
  /* a mouse or a synthetic click (no touches before it) acts as a tap */
  sc.addEventListener('click', function(e){ if(Date.now()-PM.lastTouch<700) return; pmTapEl(e.target, e.clientX, e.clientY); });
}

/* ── what a tap lands on ── */
function pmHit(x, y, el){ var r=PM.sc.getBoundingClientRect(), mx=(x-r.left+PM.sx)/PM.z-MX, my=(y-r.top+PM.sy)/PM.z-MY, z=PM.z, TXs=window._palTRx;
  if(TXs && TXs.has() && !(el&&el.closest&&el.closest('.pl-bld'))){ var bs=null, bd=1e9; TXs.stops().forEach(function(s,i){ var d=Math.hypot(s.x-mx,s.y-my)*z; if(d<bd){ bd=d; bs=i; } }); if(bs!=null && bd<17) return DIR.stPlace(bs); }
  if(el && el.closest){ var b=el.closest('.pl-bld[data-id]'); if(b) return DIR.bldPlace(b.getAttribute('data-id'));
    var lm=el.closest('.pl-lmb'); if(lm){ var nm=lm.getAttribute('data-name'); return DIR.index().filter(function(q){ return q.k==='l' && q.name===nm; })[0]||null; } }
  var best=null, bd2=26*26; Object.keys(P.at).forEach(function(id){ if(!isB(id)) return; var L=lot(P.at[id]); if(!L) return; var dx=(L[0]-mx)*z, dy=(L[1]-my)*z, d=dx*dx+dy*dy; if(d<bd2){ bd2=d; best=id; } });
  if(best) return DIR.bldPlace(best);
  return null; }
function pmTap(x, y){ pmTapEl(document.elementFromPoint(x,y), x, y); }
function pmTapEl(el, x, y){ var p=pmHit(x, y, el);
  if(DIR.isOn()){ var S=DIR.state(); if(p && S.focus && S.nav==null){ DIR.pick(p); pmSnap(PM.det==='peek'?'half':PM.det); } return; }
  if(p){ pmSelect(p, true); return; }
  var card=PM.body, du=el&&el.closest&&el.closest('.pl-dist');
  if(du){ var u=+du.getAttribute('data-u'), d=(P.d||[]).filter(function(q){ return q.u===u; })[0]; if(d){ pmFitBox(d.box); pmSelect({k:'d', u:u, name:d.n||PHASE_META[u].label, x:(d.box[0]+d.box[2])/2, y:(d.box[1]+d.box[3])/2}, false); return; } }
  var h=el&&el.closest&&el.closest('.pl-hit'); if(h){ var c=cornerAt(MM.svg, {clientX:x, clientY:y}, h._n); pmSelect({k:'c', name:c?c.join(' & '):h._n, x:null, y:null}, false); return; }
  pmDeselect(); }

/* ── the selection: lit on the map, a card in the sheet ── */
function pmMark(p){ var sv=MM.svg, g=sv._sel; if(!g || g.parentNode!==sv){ g=sv._sel=el('g',{'class':'pl-sel pl-dir'},sv); } else sv.appendChild(g); g.innerHTML='';
  if(p && p.x!=null){ var m=el('g',{'class':'dr-mk dr-cur', transform:'translate('+(+p.x)+' '+(+p.y)+')'},g); el('g',{'class':'dr-sc'},m).innerHTML='<circle class="p" r="12"/><circle r="12"/>'; } }
function pmDeselect(){ PM.sel=null; if(MM.svg){ drawRoutes(MM.svg, null); pmMark(null); MM.svg.querySelectorAll('.pm-sel').forEach(function(n){ n.classList.remove('pm-sel'); }); }
  if(PM.mode==='place'){ pmMode('home'); if(PM.det!=='peek') pmSnap('peek'); } }
function pmSelect(p, fly){ PM.sel=p; var sv=MM.svg;
  drawRoutes(sv, p.k==='b'?p.id:null); sv.querySelectorAll('.pm-sel').forEach(function(n){ n.classList.remove('pm-sel'); });
  if(p.k==='b'){ var b=sv.querySelector('.pl-bld[data-id="'+p.id+'"]'); if(b) b.classList.add('pm-sel'); }
  pmMark(p); pmMode('place');
  if(PM.det==='peek') pmSnap('half'); if(fly && p.x!=null) pmGoto(p.x, p.y, Math.max(PM.z,.85), 520, pmDet().half);
  else if(p.x!=null) pmGoto(p.x, p.y, Math.max(PM.z,.85), 520, pmDet().half); }
function pmDesc(id){ var n=TT[id]||{}, t=String(n.desc||n.body||n.text||n.summary||'').replace(/<[^>]+>/g,' ').replace(/[*_`#>]+/g,'').replace(/\s+/g,' ').trim();
  if(t.length>300){ t=t.slice(0,300); t=t.replace(/\s+\S*$/,'')+'…'; } return t; }
function pmCard(p){ var h='', ic=function(d){ return '<svg viewBox="0 0 20 20" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+d+'</svg>'; };
  var acts='<div class="pm-acts"><button type="button" class="pm-act pri" data-a="dir">'+ic('<path d="M10 2.500l7.500 7.500-7.500 7.500L2.500 10z"/><path d="M6.800 11.300V9.200a1.200 1.200 0 0 1 1.200-1.200h3.700M10.800 6.300L12.500 8l-1.700 1.700"/>')+'Directions</button>'
    +(p.k==='b'||(p.k==='l'&&p.page)?'<button type="button" class="pm-act" data-a="open">'+ic('<path d="M6 4h8v8M14 4L5 13"/>')+'Open</button>':'')
    +'<button type="button" class="pm-act" data-a="share">'+ic('<path d="M10 12V3M6.500 6.500L10 3l3.500 3.500M5 10v6h10v-6"/>')+'Share</button></div>';
  if(p.k==='b'){ var id=p.id, fl=P.fl[id]||[], u=ACT[id], pm=PHASE_META[u], dn=(P.d||[]).filter(function(q){ return q.u===u; })[0], col=pm?pm.colorRaw:'var(--accent)', d=pmDesc(id), rl=(typeof REL_LABELS!=='undefined')?REL_LABELS:{};
    h=acts+(d?'<p class="pm-desc">'+esc(d)+'</p>':'')+'<ul class="pm-info">'
      +(pm?'<li><small>Neighbourhood</small><span><i style="background:'+esc(col)+'"></i>'+esc((dn&&dn.n)||pm.label)+'</span></li><li><small>Unit</small><span>'+esc(pm.numeral)+' · '+esc(pm.label)+'</span></li>':'')
      +((P.near||{})[id]?'<li><small>Nearest corner</small><span>'+esc(P.near[id])+'</span></li>':'')
      +'<li><small>Floors</small><span>'+(fl.length?(fl.length+1)+' floors':'One floor')+'</span></li></ul>';
    var rs=rels(id).slice(0,6); if(rs.length){ h+='<div class="pm-h6">Connected to</div>'+rs.map(function(c){ var other=bOf(c[0])===id?c[1]:c[0], cl=(typeof COLOR_MAP!=='undefined'&&COLOR_MAP[c[2]])||'var(--accent)';
      return '<span class="pm-rel"><i style="background:'+cl+'"></i>'+esc(rl[c[2]]||c[2])+': '+esc(num(bOf(other)))+' '+esc(title(other))+'</span>'; }).join(''); }
    if(fl.length) h+='<div class="pm-h6">Inside</div><ul class="pm-list">'+fl.slice(0,8).map(function(f,i){ return '<li><span class="pm-bd">'+esc(num(f))+'</span><div><b>'+esc(title(f))+'</b></div></li>'; }).join('')+'</ul>'; }
  else if(p.k==='l'){ var g=MM.svg.querySelector('.pl-lmb[data-name="'+p.name.replace(/"/g,'\\"')+'"]'); h=acts+'<ul class="pm-info"><li><small>Kind</small><span>Landmark</span></li>'+(p.page&&g?'<li><small>Inside</small><span>'+esc(window._palLm.pageInfo(p.page, pageName).name||'')+(window._palLm.pageInfo(p.page,pageName).count?' · '+window._palLm.pageInfo(p.page,pageName).count+' '+esc(window._palLm.pageInfo(p.page,pageName).unit):'')+'</span></li>':'')+'</ul>'; }
  else if(p.k==='s'){ h=acts+'<div class="pm-h6">Lines here</div><div class="pm-chips">'+(p.lines||[]).map(function(id){ var l=window._palTRx.lineOf(id); return l?'<span class="pm-chip" style="--tc:'+DIR.lineCol(id)+'"><i></i>'+esc(l.n)+'</span>':''; }).join('')+'</div>'; }
  else if(p.k==='d'){ var ids=(P.units||[])[p.u]||[]; h='<div class="pm-h6">Buildings</div><ul class="pm-list">'+ids.slice(0,40).map(function(id){ return '<li data-pick="'+esc(id)+'"><span class="pm-bd">'+esc(num(id))+'</span><div><b>'+esc(title(id))+'</b></div></li>'; }).join('')+'</ul>'; }
  return h; }
function pmHeadHtml(){ var p=PM.sel, ic=function(d){ return '<svg viewBox="0 0 20 20" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+d+'</svg>'; }, x=ic('<path d="M5.500 5.500l9 9M14.500 5.500l-9 9"/>');
  if(PM.mode==='place' && p){ var sub=p.k==='b'?[(PHASE_META[ACT[p.id]]||{}).label, (P.near||{})[p.id]].filter(Boolean).join(' · '):p.k==='l'?'Landmark':p.k==='s'?(p.sub||'Station'):p.k==='d'?'Neighbourhood':'';
    return '<div class="pm-hrow"><div class="pm-pt">'+(p.num?'<small>'+esc(p.num)+'</small>':'')+'<b>'+esc(p.name)+'</b>'+(sub?'<span>'+esc(sub)+'</span>':'')+'</div><button type="button" class="pm-btn ghost" data-a="x" aria-label="Close">'+x+'</button></div>'; }
  if(PM.mode==='dir') return '<div class="pm-hrow"><div class="pm-pt"><b>Directions</b></div></div>';
  return '<div class="pm-hrow"><label class="pm-search">'+ic('<circle cx="9" cy="9" r="5.500"/><path d="M13.200 13.200L17 17"/>')+'<input class="pm-q" type="search" enterkeyhint="search" autocomplete="off" autocorrect="off" spellcheck="false" placeholder="Search the city" aria-label="Search buildings, landmarks and stations"></label>'
    +'<button type="button" class="pm-btn" data-a="dir" aria-label="Directions">'+ic('<path d="M10 2.500l7.500 7.500-7.500 7.500L2.500 10z"/><path d="M6.800 11.300V9.200a1.200 1.200 0 0 1 1.200-1.200h3.700M10.800 6.300L12.500 8l-1.700 1.700"/>')+'</button></div>'; }
function pmHome(){ var h='<div class="pm-h6" style="margin-top:6px">Neighbourhoods</div><ul class="pm-list">';
  (P.d||[]).forEach(function(d){ var pm=PHASE_META[d.u]; if(!pm) return; h+='<li data-d="'+d.u+'"><span class="pm-bd" style="--bd:'+esc(pm.colorRaw)+'">'+esc(pm.numeral)+'</span><div><b>'+esc(d.n||pm.label)+'</b><small>'+esc(pm.label)+' · '+(((P.units||[])[d.u]||[]).length)+' buildings</small></div></li>'; });
  h+='</ul>'; var lms=(M.landmarks||[]).filter(function(l){ return l.n && l.page; }).slice(0,12);
  if(lms.length){ h+='<div class="pm-h6">Landmarks</div><ul class="pm-list">'+lms.map(function(l){ return '<li data-lm="'+esc(l.n)+'"><span class="pm-bd">◆</span><div><b>'+esc(l.n)+'</b><small>Reference inside</small></div></li>'; }).join('')+'</ul>'; }
  return h; }
function pmResults(q){ var r=DIR.search(q, 14);
  return r.length?'<ul class="pm-list">'+r.map(function(p,i){ return '<li data-r="'+i+'"><span class="pm-bd">'+esc(p.num||(p.k==='s'?'●':'◆'))+'</span><div><b>'+esc(p.name)+'</b><small>'+esc(p.sub||'')+'</small></div></li>'; }).join('')+'</ul>':'<p class="dr-hint" style="margin:16px 2px">Nothing matches “'+esc(q)+'”.</p>'; }
function pmMode(m){ PM.mode=m; if(m!=='dir' && m!=='nav') { PM.head.innerHTML=pmHeadHtml(); }
  if(m==='place' && PM.sel) PM.body.innerHTML='<div class="pm-card">'+pmCard(PM.sel)+'</div>'; else if(m==='home'){ PM.body.innerHTML=pmHome(); PM.q=''; } else if(m==='dir'){ PM.head.innerHTML=pmHeadHtml(); }
  PM.body.scrollTop=0; }
function pmSheetClicks(){
  var sh=PM.sheet;
  sh.addEventListener('input', function(e){ var q=e.target.closest('.pm-q'); if(!q) return; PM.q=q.value; PM.body.innerHTML=q.value.trim()?pmResults(q.value):pmHome(); });
  sh.addEventListener('focusin', function(e){ if(e.target.closest('.pm-q') && PM.det!=='full') pmSnap('full'); });
  sh.addEventListener('click', function(e){ var t=e.target;
    var a=t.closest('[data-a]'); if(a){ var k=a.getAttribute('data-a'), p=PM.sel;
      if(k==='x'){ pmDeselect(); return; }
      if(k==='dir'){ pmDirections(p&&PM.mode==='place'?p:null); return; }
      if(k==='open' && p){ if(p.k==='b'){ var id=p.id; mmapClose(); if(window.featureNode) try{ window.featureNode(id, true); }catch(x){} setTimeout(function(){ window.showDetail('node', id); }, 60); } else if(p.page){ mmapClose(); openPage(p.page); } return; }
      if(k==='share' && p){ var url=location.href.split('#')[0], txt=(p.num?p.num+' ':'')+p.name;
        if(navigator.share) navigator.share({title:txt, text:txt+' — '+(P.place||'the city'), url:url}).catch(function(){}); else if(navigator.clipboard) navigator.clipboard.writeText(txt+' '+url).then(function(){ a.lastChild.nodeValue='Copied'; }, function(){}); return; } }
    var r=t.closest('[data-r]'); if(r){ var p2=DIR.search(PM.q,14)[+r.getAttribute('data-r')]; if(p2){ if(document.activeElement && document.activeElement.blur) document.activeElement.blur(); pmSelect(p2, true); } return; }
    var d=t.closest('[data-d]'); if(d){ var u=+d.getAttribute('data-d'), dd=(P.d||[]).filter(function(q){ return q.u===u; })[0]; if(dd){ pmSnap('half'); pmSelect({k:'d', u:u, name:dd.n||PHASE_META[u].label, x:null, y:null}, false); pmFitBox(dd.box); } return; }
    var lm=t.closest('[data-lm]'); if(lm){ var nm=lm.getAttribute('data-lm'), q2=DIR.index().filter(function(q){ return q.k==='l' && q.name===nm; })[0]; if(q2) pmSelect(q2, true); return; }
    var pk=t.closest('[data-pick]'); if(pk){ var bp=DIR.bldPlace(pk.getAttribute('data-pick')); if(bp) pmSelect(bp, true); return; } });
}
function pmDirections(from){ var o={}; if(from) o.to=from; 
  DIR.open(PM.ad, o); }

/* ── building it, opening it, closing it ── */
function pmBuild(){ var box=document.getElementById('pal-mmap'); if(box) return box;
  box=document.createElement('div'); box.id='pal-mmap'; var pi=function(d){ return '<svg class="pm-ic" viewBox="0 0 20 20" width="21" height="21" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+d+'</svg>'; };
  box.innerHTML='<div class="pm-scroll"></div><button class="pm-close" aria-label="Close">'+pi('<path d="M5 5l10 10M15 5L5 15"/>')+'</button>'
    +'<div class="pm-zoom"><div class="pm-pill"><button type="button" data-z="in" aria-label="Zoom in">'+pi('<path d="M10 4.5v11M4.5 10h11"/>')+'</button><span class="pm-div"></span>'
    +'<button type="button" data-z="out" aria-label="Zoom out">'+pi('<path d="M4.5 10h11"/>')+'</button></div>'
    +'<button type="button" class="pm-city" data-z="fit" aria-label="The whole city">'+pi('<path d="M3.5 7.3V5.4a1.9 1.9 0 0 1 1.9-1.9h1.9M12.7 3.5h1.9a1.9 1.9 0 0 1 1.9 1.9v1.9M16.5 12.7v1.9a1.9 1.9 0 0 1-1.9 1.9h-1.9M7.3 16.5H5.4a1.9 1.9 0 0 1-1.9-1.9v-1.9"/>'
      +'<rect x="7.2" y="7.2" width="2.3" height="2.3" rx=".7" fill="currentColor" stroke="none"/><rect x="10.5" y="7.2" width="2.3" height="2.3" rx=".7" fill="currentColor" stroke="none"/><rect x="7.2" y="10.5" width="2.3" height="2.3" rx=".7" fill="currentColor" stroke="none"/><rect x="10.5" y="10.5" width="2.3" height="2.3" rx=".7" fill="currentColor" stroke="none"/>')+'</button></div>'
    +'<div class="pm-sheet" role="region" aria-label="Map sheet"><div class="pm-grab" role="separator" aria-label="Drag to resize"><i></i></div><div class="pm-head"></div><div class="pm-body"></div></div>';
  document.body.appendChild(box); MM.box=box;
  MM.svg=el('svg',{viewBox:(-MX)+' '+(-MY)+' '+VW+' '+VH, preserveAspectRatio:'none', id:'palace-svg-m', 'class':'pal-svg'}); MM.svg._sid='m'; drawCity(MM.svg);
  MM.svg.style.setProperty('--pz', MM.z); MM.svg.style.setProperty('--tw', tw(MM.z)); MM.svg.setAttribute('width', VW*MM.z); MM.svg.setAttribute('height', VH*MM.z);
  PM.sc=box.querySelector('.pm-scroll'); PM.sc.appendChild(MM.svg); PM.sheet=box.querySelector('.pm-sheet'); PM.head=box.querySelector('.pm-head'); PM.body=box.querySelector('.pm-body');
  box.querySelector('.pm-close').addEventListener('click', mmapClose);
  box.querySelector('.pm-zoom').addEventListener('click', function(e){ var b=e.target.closest('[data-z]'); if(!b) return; var k=b.getAttribute('data-z');
    if(k==='fit') pmFitCity(); else pmZoomBy(k==='in'?1.6:1/1.6); });
  box.addEventListener('touchmove', function(e){ if(e.cancelable && !e.target.closest('.pm-body') && !e.target.closest('.pm-sheet') && !e.target.closest('.pm-scroll')) e.preventDefault(); }, {passive:false});
  pmGestures(); pmSheetTouch(); pmSheetClicks(); DIR.wire(PM.body); DIR.wire(PM.head);
  PM.ad={mobile:true, host:PM.body, navEl:PM.head, svg:function(){ return MM.svg; }, fly:pmFly, fit:pmFitBox,
    hot:function(ids){ MM.svg.querySelectorAll('.pl-bld.pal-hot').forEach(function(n){ n.classList.remove('pal-hot'); }); ids.forEach(function(id){ var n=MM.svg.querySelector('.pl-bld[data-id="'+id+'"]'); if(n) n.classList.add('pal-hot'); }); },
    onOpen:function(){ drawRoutes(MM.svg, null); pmMark(null); MM.svg.querySelectorAll('.pm-sel').forEach(function(n){ n.classList.remove('pm-sel'); }); PM.mode='dir'; PM.head.innerHTML=pmHeadHtml(); if(PM.det==='peek') pmSnap('half'); },
    onType:function(){ if(PM.det!=='full') pmSnap('full'); },
    onPick:function(){ if(PM.det==='full') pmSnap('half'); },
    onNav:function(on){ if(on){ PM.mode='nav'; if(PM.det!=='peek') pmSnap('peek'); } else if(PM.mode==='nav'){ PM.mode='dir'; PM.head.innerHTML=pmHeadHtml(); if(PM.det==='peek') pmSnap('half'); } },
    onClose:function(){ PM.mode='home'; PM.sel=null; pmMode('home'); pmSnap('peek'); } };
  window.addEventListener('resize', function(){ if(!box.classList.contains('on')) return; pmMeasure(); pmSet(pmDet()[PM.det]); pmApply(PM.z, PM.sx, PM.sy); });
  return box; }
function mmapOpen(){
  var box=pmBuild(), first=!PM.inited; box.classList.add('on'); document.documentElement.classList.add('pm-open'); pmMeasure();
  if(first){ PM.inited=1; PM.z=Math.max(pmZmin(), MM.z); PM.sh=pmDet().peek; PM.det='peek'; pmMode('home'); pmSet(PM.sh); pmCommit(PM.z); }
  else { pmSet(pmDet()[PM.det]); }
  var f=window._featuredNodeId, L=f?lot(P.at[bOf(f)]):null;
  if(first||L){ var c=L?[L[0],L[1]]:[M.W/2, M.H/2], z=L?Math.max(PM.z,.6):pmZmin()*1.02; pmApply(z, (c[0]+MX)*z-PM.W/2, (c[1]+MY)*z-(PM.H-PM.sh)/2); pmSettle(); }
  if(L){ var id=bOf(f); drawRoutes(MM.svg, id); var b=MM.svg.querySelector('.pl-bld[data-id="'+id+'"]'); if(b) b.classList.add('pm-sel'); pmMark({x:L[0], y:L[1]}); }
}
function mmapClose(){ if(DIR.isOn()) DIR.close(); if(MM.box) MM.box.classList.remove('on'); document.documentElement.classList.remove('pm-open'); }
window._palMob={PM:function(){ return PM; }, goto:function(x,y,z){ pmGoto(x,y,z,1); pmSettle(); }, open:function(){ mmapOpen(); }, close:function(){ mmapClose(); }};
"""
