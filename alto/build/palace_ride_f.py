"""Part F of the first-person ride: the entry points - the aerial / first-person switch, key, drop-in, ride-view setting (owner: the ui agent).

The switch **Aerial | First-person** lives in the palace's own control cluster (#pal-ctl, beside the zoom pill and Directions), key `F`.
Choosing First-person puts the map in "drop in" mode: a ghost figure (with an arrow along the nearest street) follows the pointer; a click flies there
with the palace's own flyMap and then hands over to free roaming (ROAM.enter, palace_ride_e.py, which dissolves the overlay in over the map);
Enter, or a double-click on the First-person segment, drops in at the middle of the screen; Esc cancels.  Leaving (the Aerial segment, F, Esc inside
the roam) gives the map back exactly as it was (R.saved = E.curView() taken before the fly, closeNow / E.putView) unless "Stay here".

The second control is the setting **First-person rides** (on/off): the same localStorage key (alto-palace-ride-view, 'fp'|'map') and the V key as
the old ride view button.  A ride started from the aerial view uses first-person only when it is on (leg() / lineEnter() already test pref()); the cluster
button, the key's rows, the trip panel (switchHtml, which replaces the old 'Map view' button) and the route pills (pillHtml) all show it as a labelled switch.

Nothing here draws on the phone (html.mobile), when printing, or outside the palace.  Everything is wrapped in one function so no name here can
shadow a function of the other parts that share this scope.
"""

JS_F = r"""
var UIX=(function(){
var US={mode:'aerial', leaving:0, tok:0, prev:null, hd:-Math.PI/2, ptr:null, raf:0, down:null, watch:0, msgT:0, near:null, grid:null, ghost:null, msg:null, live:null};
var UI_SEL='#pal-ctl,#pal-key,#pal-tr,#pal-chiprt,#pal-relrt,#pal-dir,#pal-fp-msg,#pal-ride,#detail-page,#nav,.pal-fp-ui';
function html(){ return document.documentElement; }
function hc(c){ return html().classList.contains(c); }
function okPage(){ return hc('alto-palace') && !hc('mobile') && !hc('printing') && !hc('detail-open') && !!E; }
function roam(){ return (typeof ROAM!=='undefined' && ROAM) || null; }
function roamOn(){ var r=roam(); try{ return !!(r && r.active && r.active()); }catch(x){ return false; } }
function cur(){ if(roamOn() && !US.leaving) return 'fp'; if(US.mode==='placing' || US.mode==='flying') return US.mode; return 'aerial'; }
function ridesOn(){ return pref()==='fp'; }
function trState(){ try{ return (window._palTr && window._palTr.state && window._palTr.state()) || null; }catch(x){ return null; } }
function inRide(){ var S=trState(); return !!(S && (S.trip || S.ride) && typeof R!=='undefined' && R.active && !roamOn()); }

/* ── the words ── */
var RIDES_TIP_ON='First-person rides: on. Rides on lines and routes show the view from inside the vehicle. Click to ride the map instead.';
var RIDES_TIP_OFF='First-person rides: off. Rides play on the top-down map. Click to ride from inside the vehicle.';
var RIDES_LINE='See each ride from inside the vehicle. Off keeps it on the map.';
var DROP_MSG='Click the map to drop in at street level · Enter drops in at the middle of the screen · Esc cancels';

/* ── icons ── */
function ic(d, w){ return '<svg viewBox="0 0 20 20" width="'+(w||18)+'" height="'+(w||18)+'" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+d+'</svg>'; }
var I_AERIAL='<path d="M3 5.6l4.6-1.9 4.8 1.9L17 3.7v10.7l-4.6 1.9-4.8-1.9L3 16.3z"/><path d="M7.6 3.7v10.7M12.4 5.6v10.7"/>';
var I_FIRST='<circle cx="10" cy="4.6" r="2.1"/><path d="M6.4 17.3v-4.6a3.6 3.6 0 0 1 7.2 0v4.6"/><path d="M8.2 9.2h3.6"/>';
var I_RIDES='<rect x="4.2" y="3.4" width="11.6" height="10.2" rx="3"/><path d="M4.2 8.6h11.6"/><path d="M7 16.9l-1.2 1.2M13 16.9l1.2 1.2"/><circle cx="7.4" cy="11.3" r=".5" fill="currentColor"/><circle cx="12.6" cy="11.3" r=".5" fill="currentColor"/>';
var I_SLASH='<path class="pc-slash" d="M3.4 17L16.6 3"/>';

/* ── the controls in the cluster ── */
function mount(c){
  if(!c || c.querySelector('.pc-fp')) return; html().classList.add('pal-fpui');
  var seg=document.createElement('div'); seg.className='pc-pill pc-fp'; seg.setAttribute('role','group'); seg.setAttribute('aria-label','View: aerial map or first-person');
  seg.innerHTML='<button type="button" data-fp="aerial" aria-pressed="true" aria-keyshortcuts="F" data-tip="Aerial view · F">'+ic(I_AERIAL)+'<span>Aerial</span></button><span class="pc-div"></span>'
    +'<button type="button" data-fp="first" aria-pressed="false" aria-keyshortcuts="F" data-tip="Walk the city at street level · F">'+ic(I_FIRST)+'<span>First-person</span></button>';
  var rd=document.createElement('button'); rd.type='button'; rd.className='pc-rides'; rd.setAttribute('data-fp','rides'); rd.setAttribute('role','switch'); rd.setAttribute('aria-keyshortcuts','V');
  rd.innerHTML=ic(I_RIDES+I_SLASH);
  var st=document.createElement('button'); st.type='button'; st.className='pc-stay'; st.setAttribute('data-fp','stay'); st.setAttribute('aria-label','Leave first-person and stay here on the map'); st.setAttribute('data-tip','Back to the map, centred here');
  st.innerHTML=ic('<path d="M10 17.2s5.2-4.4 5.2-8.6a5.2 5.2 0 0 0-10.4 0c0 4.2 5.2 8.6 5.2 8.6z"/><circle cx="10" cy="8.6" r="1.8"/>')+'<span>Stay here</span>';
  var dirb=c.querySelector('.pc-dirb'); c.insertBefore(seg, dirb||null); c.insertBefore(st, dirb||null); c.appendChild(rd); sync(); }
/* rows in the key (the legend) */
function keyRows(){
  var sw=function(d){ return '<svg viewBox="0 0 20 20" width="26" height="14" style="flex:none" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+d+'</svg>'; };
  return '<div class="pk-sep"></div>'
    +'<button type="button" class="pk-row pk-fp" data-fp="first-key">'+sw(I_FIRST)+'<div><b>Aerial | First-person</b> <small>Key F · First-person walks the streets at eye level: click the map to drop in (Enter drops in at the middle), Esc to leave.</small></div></button>'
    +'<button type="button" class="pk-row pk-fp" role="switch" data-fp="rides" aria-checked="'+ridesOn()+'">'+sw(I_RIDES)+'<div><b>First-person rides</b> <span class="pr-st">'+(ridesOn()?'On':'Off')+'</span> <small>Key V · '+RIDES_LINE+'</small></div><span class="pr-tk" style="margin-left:auto"><i></i></span></button>'; }
/* the trip panel: the labelled setting with its explanation, and the Exit button (replaces the old "Map view · V") */
function panelHtml(){
  return '<div class="pr-opt"><button type="button" class="pr-swb" role="switch" data-fp="rides" aria-checked="'+ridesOn()+'" aria-keyshortcuts="V"><span class="pr-lb">First-person rides</span><span class="pr-tk"><i></i></span><span class="pr-st">'+(ridesOn()?'On':'Off')+'</span><span class="pr-k">V</span></button>'
    +'<div class="tr-sub pr-ln">'+RIDES_LINE+'</div></div><div class="tr-btns pr-sw"><button class="tr-b pr-ex" type="button" data-ride="exit">Exit ride</button></div>'; }
/* the route pills: a labelled switch beside the Ride button */
function pillHtml(){
  return '<button type="button" class="pr-pfp" role="switch" data-fp="rides" aria-checked="'+ridesOn()+'" aria-keyshortcuts="V" title="'+(ridesOn()?RIDES_TIP_ON:RIDES_TIP_OFF)+'">'+ic(I_RIDES,14)+'<span class="pr-lb">First-person</span><span class="pr-tk"><i></i></span></button>'; }

/* ── keeping every copy of the controls in step with the state ── */
function sync(){
  var m=cur(), h=html();
  h.classList.toggle('pal-placing', m==='placing'); h.classList.toggle('pal-flying', m==='flying');
  if(m==='fp'){ h.classList.add('pal-roam'); if(!US.watch) startWatch(); }
  [].forEach.call(document.querySelectorAll('[data-fp=aerial]'), function(b){ b.setAttribute('aria-pressed', String(m==='aerial')); });
  [].forEach.call(document.querySelectorAll('[data-fp=first]'), function(b){ b.setAttribute('aria-pressed', String(m!=='aerial')); b.setAttribute('data-state', m); });
  var on=ridesOn();
  [].forEach.call(document.querySelectorAll('[data-fp=rides]'), function(b){ b.setAttribute('aria-checked', String(on)); b.classList.toggle('on', on);
    var s=b.querySelector('.pr-st'); if(s) s.textContent=on?'On':'Off';
    if(b.classList.contains('pc-rides')){ b.setAttribute('aria-label','First-person rides: '+(on?'on':'off')); b.setAttribute('data-tip', 'First-person rides: '+(on?'on':'off')+' · V'); b.title=''; }
    else if(b.classList.contains('pr-pfp')) b.title=on?RIDES_TIP_ON:RIDES_TIP_OFF; });
  [].forEach.call(document.querySelectorAll('.pc-stay'), function(b){ b.classList.toggle('show', m==='fp'); });
}
/* the other parts call labelBtns() whenever the ride view setting or the overlay changes: the controls follow */
var _lb=labelBtns; labelBtns=function(){ _lb(); sync(); };

/* ── the message (the prompt while dropping in, and short confirmations) ── */
function say(text, sticky){
  if(!US.msg){ var d=document.createElement('div'); d.id='pal-fp-msg'; d.className='pal-fp-ui'; d.setAttribute('role','status'); d.setAttribute('aria-live','polite'); document.body.appendChild(d); US.msg=d; }
  clearTimeout(US.msgT); US.msg.textContent=text||''; US.msg.classList.toggle('on', !!text);
  if(text && !sticky) US.msgT=setTimeout(function(){ if(US.msg) US.msg.classList.remove('on'); }, 2600); }

/* ── the nearest street: where the ghost's arrow points, and the way you face when you drop in ── */
function buildGrid(){
  var G={c:150, m:{}}, ss=(E&&E.M&&E.M.streets)||[]; US.grid=G;
  ss.forEach(function(s){ if(s.t || !s.p) return; var p=s.p;
    for(var i=0;i+3<p.length;i+=2){ var a=[p[i],p[i+1],p[i+2],p[i+3],s.n||''], x0=Math.floor(Math.min(a[0],a[2])/G.c), x1=Math.floor(Math.max(a[0],a[2])/G.c), y0=Math.floor(Math.min(a[1],a[3])/G.c), y1=Math.floor(Math.max(a[1],a[3])/G.c);
      if((x1-x0+1)*(y1-y0+1)>40) continue;
      for(var gx=x0;gx<=x1;gx++) for(var gy=y0;gy<=y1;gy++){ var k=gx+','+gy; (G.m[k]=G.m[k]||[]).push(a); } } });
  return G; }
function facing(dx, dy){ var h=Math.atan2(dy,dx), s=-Math.sin(h); if(Math.abs(s)<.3) return Math.cos(h)>=0?h:h+Math.PI; h=s>0?h:h+Math.PI; return Math.atan2(Math.sin(h),Math.cos(h)); }
function near(x, y, maxr){
  if(!E || !E.M) return null; var G=US.grid||buildGrid(), gx=Math.floor(x/G.c), gy=Math.floor(y/G.c), rr=Math.ceil((maxr||450)/G.c), best=null, bd=1e18, seen=null;
  for(var r=0;r<=rr;r++){
    for(var dx=-r;dx<=r;dx++) for(var dy=-r;dy<=r;dy++){ if(Math.max(Math.abs(dx),Math.abs(dy))!==r) continue; var L=G.m[(gx+dx)+','+(gy+dy)]; if(!L) continue;
      for(var i=0;i<L.length;i++){ var a=L[i], ex=a[2]-a[0], ey=a[3]-a[1], q=ex*ex+ey*ey||1e-9, t=Math.max(0,Math.min(1,((x-a[0])*ex+(y-a[1])*ey)/q)), px=a[0]+t*ex, py=a[1]+t*ey, d=(px-x)*(px-x)+(py-y)*(py-y);
        if(d<bd){ bd=d; best={x:px, y:py, h:facing(ex,ey), d:Math.sqrt(d), name:a[4]}; } } }
    if(best && best.d<=r*G.c) break; }
  return best; }

/* ── the pointer: the ghost follows it over the map ── */
function ghostEl(){
  if(US.ghost) return US.ghost;
  var g=document.createElement('div'); g.id='pal-fp-ghost'; g.className='pal-fp-ui'; g.setAttribute('aria-hidden','true');
  g.innerHTML='<svg class="pg-dir" viewBox="-30 -30 60 60" width="60" height="60"><path d="M29 0L20.5 -8L23 0L20.5 8Z"/></svg>'
    +'<i class="pg-disc"><svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true"><circle cx="10" cy="5.6" r="3.1"/><path d="M4 17.4v-3.4a6 6 0 0 1 12 0v3.4z"/></svg></i>';
  document.body.appendChild(g); US.ghost=g; US.dir=g.querySelector('.pg-dir'); return g; }
function overMap(t){ return !!(t && t.closest && t.closest('#canvas') && !t.closest(UI_SEL)); }
/* the page may be scaled (CSS zoom on <html>): pointer coordinates are the window's, a fixed element's are the page's - measure the ratio once */
function measureZoom(){ var g=ghostEl(), keep=g.style.transform; g.style.transform='translate3d(200px,200px,0)'; var r=g.getBoundingClientRect(); g.style.transform=keep; US.zk=(r.left>1?r.left/200:1)||1; }
function onMove(e){
  if(US.mode!=='placing') return; US.ptr={x:e.clientX, y:e.clientY, t:e.target};
  if(!US.raf) US.raf=requestAnimationFrame(frame); }
function frame(){
  US.raf=0; var p=US.ptr, g=ghostEl(); if(!p || US.mode!=='placing'){ g.classList.remove('on'); return; }
  var over=overMap(p.t); g.classList.toggle('on', over);
  if(!over){ return; }
  var k=US.zk||1; g.style.transform='translate3d('+(p.x/k).toFixed(1)+'px,'+(p.y/k).toFixed(1)+'px,0)';
  var m=E&&E.mapAt?E.mapAt(p.x,p.y):null, n=m?near(m[0],m[1],450):null; US.near=n;
  if(n){ US.hd=n.h; } US.dir.style.transform='rotate('+US.hd.toFixed(4)+'rad)'; US.dir.style.opacity=n?1:.35; }
function pdown(e){ if(US.mode==='placing') US.down={x:e.clientX, y:e.clientY, t:e.target}; }

/* ── the flow ── */
function startPlacing(){
  if(!okPage() || cur()!=='aerial') return false; if(inRide()) return false;
  if(!roam() || !roam().enter){ say('Walking the city is not available on this page.'); return false; }
  US.mode='placing'; US.tok++; US.ptr=null; ghostEl().classList.remove('on'); measureZoom(); say(DROP_MSG, true); sync(); return true; }
function stopPlacing(){
  if(US.mode!=='placing' && US.mode!=='flying') return; US.mode='aerial'; US.tok++; if(US.ghost) US.ghost.classList.remove('on'); say(''); sync(); }
function cancel(){ if(US.mode==='flying' && US.prev && E && E.putView){ E.putView(US.prev); } US.prev=null; stopPlacing(); }
function centre(){ var cv=document.getElementById('canvas'); if(!cv) return null; var r=cv.getBoundingClientRect(), x0=Math.max(r.left,0), x1=Math.min(r.right,window.innerWidth), y0=Math.max(r.top,0), y1=Math.min(r.bottom,window.innerHeight);
  var m=E&&E.mapAt?E.mapAt((x0+x1)/2,(y0+y1)/2):null; return m; }
function dropCentre(){ var m=centre(); if(m) dropIn(m[0], m[1]); }
/* x, y in map units; h = facing (radians, 0 = east, map y down) or null for "along the nearest street" */
function dropIn(x, y, h, o){
  if(!okPage() || !roam() || !roam().enter) return false; if(cur()==='fp' || US.mode==='flying') return false;
  o=o||{}; var S=trState(); if(S && (S.trip||S.ride||S.line||S.stop!=null) && window._palTr.clear){ try{ window._palTr.clear(); }catch(e){} }
  var n=near(x,y,450); if(h==null) h=n?n.h:US.hd; var view=E.curView?E.curView():null, tok=++US.tok;
  US.mode='flying'; US.prev=view; if(US.ghost) US.ghost.classList.remove('on'); say('', false); sync();
  var z=Math.max(E.Z?E.Z():1, 1.5);
  function enter(){
    if(tok!==US.tok) return; var ok=false, r=roam();
    try{ ok=!!r.enter(x, y, h, {from:'aerial', view:view, near:n, street:n&&n.name||''}); }catch(err){ if(window.console) console.warn('roam', err); }
    if(!ok){ if(view && E.putView) E.putView(view); US.mode='aerial'; US.prev=null; sync(); say('Walking the city is not ready here yet.'); return; }
    US.mode='fp'; if(view && R.active && !R.saved) R.saved=view; US.prev=null; sync(); }
  if(o.noFly){ enter(); return true; }
  if(E.fly) E.fly(x, y, z, enter); else enter();
  return true; }
function leave(stay){
  var r=roam(); if(cur()!=='fp'){ cancel(); return; }
  US.leaving=1; US.mode='aerial'; sync();
  try{ r.exit(!!stay); }catch(e){ if(window.console) console.warn('roam exit', e); }
  startWatch(); }
function startWatch(){ if(US.watch) return;
  US.watch=setInterval(function(){
    if(roamOn()) { if(!US.leaving) html().classList.add('pal-roam'); return; }
    clearInterval(US.watch); US.watch=0; var was=US.leaving; US.leaving=0; if(US.mode==='fp') US.mode='aerial'; sync();
    setTimeout(function(){ if(!roamOn()) html().classList.remove('pal-roam'); }, 420);
    if(was) say('Back on the aerial map.'); }, 160); }
function setRides(on){
  var want=on?'fp':'map';
  if(pref()!==want){ try{ toggle(); }catch(e){ setPref(want); } if(pref()!==want) setPref(want); }
  labelBtns(); say('First-person rides '+(on?'on · you ride inside the vehicle':'off · rides play on the map')); }
function toggleRides(){ setRides(!ridesOn()); }

/* ── clicks and keys ── */
document.addEventListener('click', function(e){
  var t=e.target; if(!t || !t.closest) return;
  if(US.mode==='placing' && overMap(t)){
    var d=US.down; US.down=null; e.preventDefault(); e.stopImmediatePropagation();
    if(d && Math.hypot(e.clientX-d.x, e.clientY-d.y)>6) return;                 /* a drag across the map, not a click */
    var m=E&&E.mapAt?E.mapAt(e.clientX, e.clientY):null; if(m) dropIn(m[0], m[1]); return; }
  var b=t.closest('[data-fp]'); if(!b) return; var a=b.getAttribute('data-fp'); e.preventDefault(); e.stopImmediatePropagation();
  if(a==='aerial'){ if(cur()==='fp') leave(false); else if(cur()!=='aerial') cancel(); }
  else if(a==='first' || a==='first-key'){ var m2=cur(); if(m2==='aerial') startPlacing(); else if(m2==='fp' && a==='first-key') leave(false); }
  else if(a==='rides'){ toggleRides(); }
  else if(a==='stay'){ leave(true); } }, true);
document.addEventListener('dblclick', function(e){ var b=e.target&&e.target.closest&&e.target.closest('[data-fp=first]'); if(!b) return; e.preventDefault();
  if(cur()==='placing') dropCentre(); }, true);
window.addEventListener('pointermove', onMove, {passive:true});
window.addEventListener('pointerdown', pdown, true);
window.addEventListener('keydown', function(e){
  if(e.metaKey||e.ctrlKey||e.altKey) return; var t=e.target; if(t && (t.tagName==='INPUT'||t.tagName==='TEXTAREA'||t.tagName==='SELECT'||t.isContentEditable)) return;
  var k=e.key, m=cur();
  if(k==='Escape'){ if(m==='placing'||m==='flying'){ e.preventDefault(); e.stopImmediatePropagation(); cancel(); } return; }
  if(!okPage()) return;
  if(k==='Enter'){ if(m!=='placing') return; var fb=t&&t.closest&&t.closest('[data-fp]'); if(fb && fb.getAttribute('data-fp')!=='first') return; e.preventDefault(); e.stopImmediatePropagation(); dropCentre(); return; }
  if(k==='f'||k==='F'){ if(e.repeat || inRide()) return; e.preventDefault(); e.stopImmediatePropagation();
    if(m==='fp') leave(false); else if(m==='aerial') startPlacing(); else cancel(); return; }
  if(k==='v'||k==='V'){ if(e.repeat) return; var S=trState(); if(S && (S.trip||S.ride)) return;   /* during a ride the ride's own handler switches it */
    e.preventDefault(); e.stopImmediatePropagation(); toggleRides(); } }, true);
/* if the page changes under a drop-in (a detail page opens, the palace is left) it ends quietly */
new MutationObserver(function(){ if((US.mode==='placing'||US.mode==='flying') && !okPage()) cancel(); }).observe(document.documentElement, {attributes:true, attributeFilter:['class']});

/* the ride panel's switch is this one now */
switchHtml=panelHtml;

return {mount:mount, keyRows:keyRows, panelHtml:panelHtml, pillHtml:pillHtml, sync:sync, state:cur, startPlacing:startPlacing, cancel:cancel, dropIn:dropIn, dropCentre:dropCentre, leave:leave,
  setRides:setRides, toggleRides:toggleRides, near:near, ridesOn:ridesOn, st:US};
})();
"""

CSS_F = r"""
  /* ── the aerial / first-person switch and the ride setting, in the zoom cluster (palace.py ctl): the cluster's own glass, 35px, same centre line ── */
  #pal-ctl .pc-pill.pc-fp button{width:auto;min-width:0;padding:0 14px 0 12px;gap:7px;}
  #pal-ctl .pc-pill.pc-fp button span{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:13px;font-weight:600;letter-spacing:.02em;line-height:1;}
  #pal-ctl .pc-pill.pc-fp button[aria-pressed=true]{color:var(--accent,#6d5bd0);background:color-mix(in srgb,var(--accent,#6d5bd0) 13%,transparent);}
  #pal-ctl .pc-pill.pc-fp button[aria-pressed=true]:hover{background:color-mix(in srgb,var(--accent,#6d5bd0) 20%,transparent);}
  #pal-ctl .pc-pill.pc-fp button[aria-pressed=true]:focus-visible{box-shadow:inset 0 0 0 2px var(--accent,#6d5bd0);}
  #pal-ctl .pc-fp .pc-div{margin:8px 0;}
  #pal-ctl .pc-rides,#pal-ctl .pc-stay{position:relative;flex:none;height:35px;box-sizing:border-box;border-radius:17.5px;padding:0;display:inline-flex;align-items:center;justify-content:center;color:var(--muted);cursor:pointer;
    background:var(--card-glass-bg,var(--surface));border:1px solid var(--card-glass-border,var(--border));-webkit-backdrop-filter:blur(18px) saturate(190%) brightness(var(--card-glass-bright,1));backdrop-filter:blur(18px) saturate(190%) brightness(var(--card-glass-bright,1));
    box-shadow:0 10px 26px var(--node-rest-shadow),inset 0 0 0 .5px var(--card-glass-rim);}
  #pal-ctl .pc-rides{width:35px;}
  #pal-ctl .pc-rides:hover,#pal-ctl .pc-stay:hover,#pal-ctl .pc-rides:focus-visible,#pal-ctl .pc-stay:focus-visible{border-color:var(--muted);color:var(--text);}
  #pal-ctl .pc-rides.on{color:var(--accent,#6d5bd0);border-color:color-mix(in srgb,var(--accent,#6d5bd0) 55%,transparent);}
  #pal-ctl .pc-rides .pc-slash{opacity:0;}
  #pal-ctl .pc-rides:not(.on) .pc-slash{opacity:1;}
  #pal-ctl .pc-rides:not(.on) svg{opacity:.75;}
  #pal-ctl .pc-stay{display:none;padding:0 15px 0 12px;gap:7px;}
  #pal-ctl .pc-stay.show{display:inline-flex;}
  #pal-ctl .pc-stay span{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:13px;font-weight:600;letter-spacing:.02em;line-height:1;}
  #pal-ctl .pc-rides:focus-visible,#pal-ctl .pc-stay:focus-visible{box-shadow:0 10px 26px var(--node-rest-shadow),inset 0 0 0 2px var(--accent,#6d5bd0);}
  /* walking the city: the cluster rises over the ride layer (so the switch is there to go back), the map's own buttons step aside without moving it */
  #pal-ctl > *{transition:opacity .25s ease;}
  html.pal-roam #pal-ctl{z-index:430;}
  html.pal-roam #pal-ctl > :not(.pc-fp):not(.pc-stay){opacity:0;pointer-events:none;}
  /* the drop-in: a ghost figure on the pointer, an arrow along the street it will face, and a line of words */
  html.pal-placing #canvas,html.pal-placing #canvas *{cursor:crosshair !important;}
  #pal-fp-ghost{position:fixed;left:0;top:0;width:0;height:0;z-index:305;pointer-events:none;opacity:0;transition:opacity .14s ease;will-change:transform;}
  #pal-fp-ghost.on{opacity:1;}
  #pal-fp-ghost .pg-disc{position:absolute;left:-18px;top:-18px;width:36px;height:36px;box-sizing:border-box;border-radius:50%;border:2.5px solid #fff;background:var(--accent,#6d5bd0);display:flex;align-items:center;justify-content:center;
    box-shadow:0 3px 10px rgba(20,16,50,.38),0 0 0 6px color-mix(in srgb,var(--accent,#6d5bd0) 22%,transparent);}
  #pal-fp-ghost .pg-disc svg{display:block;fill:#fff;}
  #pal-fp-ghost .pg-dir{position:absolute;left:-30px;top:-30px;overflow:visible;filter:drop-shadow(0 1px 2px rgba(20,16,50,.4));}
  #pal-fp-ghost .pg-dir path{fill:var(--accent,#6d5bd0);stroke:#fff;stroke-width:2;stroke-linejoin:round;}
  #pal-fp-msg{position:fixed;left:50%;top:112px;transform:translateX(-50%);z-index:312;max-width:min(680px,calc(100vw - 48px));box-sizing:border-box;padding:8px 17px;border-radius:999px;font:600 12.5px/1.3 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    color:var(--text);background:var(--panel-glass-bg,var(--surface));border:1px solid var(--card-glass-border,var(--border));-webkit-backdrop-filter:blur(24px) saturate(185%);backdrop-filter:blur(24px) saturate(185%);
    box-shadow:0 12px 32px var(--node-hover-shadow);opacity:0;pointer-events:none;transition:opacity .18s ease;text-align:center;}
  #pal-fp-msg.on{opacity:1;}
  html.pal-roam #pal-fp-msg{z-index:431;top:76px;}
  /* the setting in the trip panel, the route pills and the key: a labelled switch */
  .pr-tk{position:relative;flex:none;width:24px;height:14px;border-radius:7px;background:color-mix(in srgb,var(--muted) 45%,transparent);transition:background .15s ease;}
  .pr-tk i{position:absolute;left:2px;top:2px;width:10px;height:10px;border-radius:50%;background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.3);transition:transform .15s ease;}
  [aria-checked=true] > .pr-tk{background:var(--accent,#6d5bd0);}
  [aria-checked=true] > .pr-tk i{transform:translateX(10px);}
  #pal-tr .pr-opt{margin:7px 0 0;}
  #pal-tr .pr-swb{display:flex;align-items:center;gap:8px;width:100%;box-sizing:border-box;padding:6px 10px;border-radius:10px;cursor:pointer;font:700 12px/1.2 inherit;color:var(--text);text-align:left;
    background:color-mix(in srgb,var(--text) 6%,transparent);border:1px solid var(--card-glass-border,var(--border));}
  #pal-tr .pr-swb:hover{border-color:var(--muted);}
  #pal-tr .pr-swb:focus-visible,.pr-pfp:focus-visible,#pal-key .pk-fp:focus-visible{outline:2px solid var(--accent,#6d5bd0);outline-offset:1px;}
  #pal-tr .pr-swb .pr-lb{flex:1;}
  #pal-tr .pr-swb .pr-st{color:var(--muted);font-weight:700;min-width:22px;text-align:right;}
  #pal-tr .pr-swb[aria-checked=true] .pr-st{color:var(--accent,#6d5bd0);}
  #pal-tr .pr-swb .pr-k{flex:none;min-width:15px;height:15px;line-height:15px;text-align:center;border-radius:4px;font-size:10px;color:var(--muted);border:1px solid var(--card-glass-border,var(--border));}
  #pal-tr .pr-ln{margin:5px 2px 0;font-size:11px;}
  .pr-pfp{display:inline-flex;align-items:center;gap:6px;flex:none;cursor:pointer;border:1px solid var(--card-glass-border,var(--border));background:transparent;color:var(--muted);border-radius:999px;padding:3px 9px 3px 8px;font:700 11px/1.2 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}
  .pr-pfp:hover{border-color:var(--muted);color:var(--text);}
  .pr-pfp[aria-checked=true]{color:var(--text);border-color:color-mix(in srgb,var(--accent,#6d5bd0) 55%,transparent);}
  .pr-pfp svg{flex:none;}
  #pal-key button.pk-fp{width:100%;box-sizing:border-box;margin:0;border:0;background:none;color:inherit;font:inherit;text-align:left;cursor:pointer;}
  #pal-key button.pk-fp:hover{background:color-mix(in srgb,var(--text) 7%,transparent);}
  #pal-key .pk-fp svg{color:var(--muted);}
  #pal-key .pk-fp[aria-checked=true] svg{color:var(--accent,#6d5bd0);}
  #pal-key .pk-fp .pr-st{font-size:11px;font-weight:700;color:var(--muted);}
  #pal-key .pk-fp[aria-checked=true] .pr-st{color:var(--accent,#6d5bd0);}
  /* the cluster is wider now: the route pills stand a little to the right of it */
  html.pal-fpui #pal-chiprt > i + span,html.pal-fpui #pal-relrt > i + span{flex:1 1 auto;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  html.pal-fpui #pal-chiprt,html.pal-fpui #pal-relrt{left:calc(50% + clamp(0px,(100vw - 1000px)/4,110px));}
  html.mobile #pal-fp-ghost,html.mobile #pal-fp-msg,html.printing #pal-fp-ghost,html.printing #pal-fp-msg,html:not(.alto-palace) #pal-fp-ghost,html:not(.alto-palace) #pal-fp-msg,html.detail-open #pal-fp-ghost,html.detail-open #pal-fp-msg{display:none !important;}
  @media (max-width:1559px){.pr-pfp .pr-lb{display:none;}.pr-pfp{padding:3px 8px;}}
  @media (prefers-reduced-motion: reduce){#pal-ctl > *,#pal-fp-ghost,#pal-fp-msg,.pr-tk,.pr-tk i{transition:none !important;}}
"""
