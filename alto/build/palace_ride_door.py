"""Part DOOR of the first-person city (FPV phase 1): the entrance of a node building, and going in through it from roam.

A node building (a building of yours with a detail page) was a plain glass box. Now each has a street-facing door:

  JS_DOOR_GEO   (shared scope, after part B)   nodeDoor(L, id) picks the face of the lot that looks at the nearest street and returns
                                               {x, y, nx, ny, w, id, name}: the middle of that face and its outward normal; gatherWorld stores it as solid.door.
                                               glDoor(b, s) (called by glSolid, palace_ride_gl.py) builds it in metres (1 m = UM = 1.3 units) on the wall:
                                               two low steps, a recessed pair of glass doors (warm light inside, material 25 in the shader) between dark
                                               jambs and a header with the push bars, and a flat canopy whose underside glows softly (material 26).
  JS_DOORS      (inside the ROAM closure, spliced into palace_ride_e.JS_E)
                                               the quiet prompt, the glow on the door, E / a click, and the way in and out of the detail page:

    * Facing a door: within DOOR_IN (12) units, on the street side of its wall, within 45 degrees of straight at it (held to 15 units / 60 degrees so it does not
      flicker at the edge), for a quarter of a second -> the building's real name appears under the street card (.rm-pin: a small map-pin glyph, the name, and a
      very small E key cap) and a soft warm glow is drawn on the door. Nothing bounces, nothing is yellow-arrowed.
    * E, a click on the door (a click, not a drag: the mouse looks around by dragging) or the pin (a real button: Tab reaches it, Enter or Space works) goes in.
    * Going in: roam's own keys are swallowed while it is on, which would break typing on the detail page, so roam is left FIRST: the camera walks up to the door
      (a dolly of ~430 ms, never through the wall: it stops one body length in front of it) while a dark veil fades in (#pal-fpv-veil), then ROAMAPI.exit(false)
      puts the aerial map back under the veil and window.showDetail('node', id) opens the page (palace.py wraps it to remember the map's view); the veil fades out
      over the page. Under prefers-reduced-motion there is no dolly: a plain 220 ms cross-fade.
    * Coming back: the page closes (anything that clears html.detail-open: its Back button, Esc, the timeline star) -> a MutationObserver sees it, the veil is
      opaque in the same task (no flash of the map), roam is entered again in front of the door, the camera backs out to the exact spot, yaw and pitch it left
      (the same dolly in reverse) and the veil fades away. Leaving roam afterwards gives the map back as it was before the FIRST entry (the view is kept).
    * Ride legs (palace_ride_d.py): at the end of a ride to a node building ("Arrived") the chip shows a very small E cap and E ends the trip and opens that building's page.
    * Esc during the dolly cancels it (the veil fades back, you are where the dolly had got to); Esc otherwise leaves roam as ever. All other roam keys behave as before.
"""

JS_DOOR_GEO = r"""
/* ── the entrance of a node building ── */
var DOORG=null;
function doorGrid(){
  var M=E.M; if(DOORG && DOORG.M===M) return DOORG; var g={M:M, c:{}}, CS=240;
  (M.streets||[]).forEach(function(s){ var p=s.p||[]; for(var i=0;i+3<p.length;i+=2){ var x0=p[i], y0=p[i+1], x1=p[i+2], y1=p[i+3], l=Math.hypot(x1-x0,y1-y0), n=Math.max(1,Math.ceil(l/100)), seen={}, seg=[x0,y0,x1-x0,y1-y0];
    for(var q=0;q<=n;q++){ var k=Math.floor((x0+(x1-x0)*q/n)/CS)+','+Math.floor((y0+(y1-y0)*q/n)/CS); if(seen[k]) continue; seen[k]=1; (g.c[k]=g.c[k]||[]).push(seg); } } });
  DOORG=g; return g; }
function streetGap(x,y){ var g=doorGrid(), CS=240, ci=Math.floor(x/CS), cj=Math.floor(y/CS), best=1e18;
  for(var a=-1;a<=1;a++) for(var b=-1;b<=1;b++){ var l=g.c[(ci+a)+','+(cj+b)]; if(!l) continue;
    for(var i=0;i<l.length;i++){ var s=l[i], l2=s[2]*s[2]+s[3]*s[3]||1e-9, t=Math.max(0,Math.min(1,((x-s[0])*s[2]+(y-s[1])*s[3])/l2)), dx=s[0]+s[2]*t-x, dy=s[1]+s[3]*t-y, d=dx*dx+dy*dy; if(d<best) best=d; } }
  return Math.sqrt(best); }
/* L = the lot [cx, cy, w, h, turn]; the face whose front lawn (14 units out) is nearest a street gets the door, the longer face winning a tie */
function nodeDoor(L, id){
  var r=turnedRing(L), cx=L[0], cy=L[1], best=null;
  for(var i=0;i<4;i++){ var j=(i+1)%4, ax=r[2*i], ay=r[2*i+1], bx=r[2*j], by=r[2*j+1], ex=bx-ax, ey=by-ay, l=Math.hypot(ex,ey); if(l<8) continue;
    var mx=(ax+bx)/2, my=(ay+by)/2, nx=ey/l, ny=-ex/l; if(nx*(mx-cx)+ny*(my-cy)<0){ nx=-nx; ny=-ny; }
    var sc=streetGap(mx+nx*14,my+ny*14)-l*.02; if(!best || sc<best.sc) best={sc:sc, x:mx, y:my, nx:nx, ny:ny, w:l}; }
  if(!best) return null;
  return {x:best.x, y:best.y, nx:best.nx, ny:best.ny, w:best.w, id:id, name:E.name(id)}; }
/* the door built into a GL buffer b (palace_ride_gl.py glSolid); every size in metres, a = along the wall, d = out from it, z = up */
function glDoor(b,s){
  var d=s.door; if(!d) return;
  var nx=d.nx, ny=d.ny, tx=ny, ty=-nx, yaw=Math.atan2(ty,tx), K=UM;
  glDC(null); _gH=0; _gL=0;
  function bx(a0,a1,d0,d1,z0,z1,pk,roof){ gbox(b, d.x+(tx*(a0+a1)+nx*(d0+d1))/2*K, d.y+(ty*(a0+a1)+ny*(d0+d1))/2*K, (a1-a0)/2*K, (d1-d0)/2*K, z0*K, z1*K, yaw, pk, 0, roof); }
  bx(-2.4,2.4,.02,1.5,0,.14,12);                 /* the steps: a low flag of paving, then a second */
  bx(-2.0,2.0,.02,.9,.14,.28,12);
  bx(-1.5,-1.3,.02,.55,.28,2.75,15);             /* the jambs and the header: dark metal, 0.5 m deep, so the doors sit back in the wall */
  bx(1.3,1.5,.02,.55,.28,2.75,15);
  bx(-1.5,1.5,.02,.55,2.55,2.75,15);
  bx(-1.3,-.03,.03,.07,.28,.4,15); bx(.03,1.3,.03,.07,.28,.4,15);          /* the kick plates */
  bx(-1.3,-.03,.03,.07,.4,2.55,25); bx(.03,1.3,.03,.07,.4,2.55,25);        /* the two glass leaves, warm inside */
  bx(-.23,-.18,.07,.2,.75,1.75,6); bx(.18,.23,.07,.2,.75,1.75,6);          /* the pull handles, either side of the middle */
  bx(-3.4,3.4,.02,2.3,3.4,3.55,15);              /* the canopy ... */
  var z=3.4*K, p=function(a,dd){ return [d.x+(tx*a+nx*dd)*K, d.y+(ty*a+ny*dd)*K]; }, q0=p(-3.4,.02), q1=p(3.4,.02), q2=p(3.4,2.3), q3=p(-3.4,2.3);
  gflat(b,[q0[0],q0[1],q1[0],q1[1],q2[0],q2[1],q3[0],q3[1]],z,26,0,false);   /* ... and the soft light under it, facing down */
}
"""

JS_DOORS = r"""
/* ── doors: the prompt, the glow, E / a click, and in and out of the detail page (palace_ride_door.py) ── */
var DR={cur:null, t:0, busy:0, tok:0, cine:null, ret:null, veil:null, hit:null, glow:0, mem:null, mo:null};
var DOOR_IN=12, DOOR_OUT=15, DOLLY_MS=430, FADE_MS=220;
function de_(){ return document.documentElement; }
function doorsAround(){ var o=[], ci=Math.floor(S.x/CELL), cj=Math.floor(S.y/CELL), a, b, c, i;
  for(a=-1;a<=1;a++) for(b=-1;b<=1;b++){ c=S.cells[(ci+a)+','+(cj+b)]; if(c && c.doors) for(i=0;i<c.doors.length;i++) o.push(c.doors[i]); } return o; }
/* the door I am facing: close, on the street side of its wall, and more or less straight at it (wider and farther once it has been found, so it does not flicker) */
function findDoor(){
  var list=doorsAround(), best=null, bd=1e9, lim=DR.cur?DOOR_OUT:DOOR_IN, mc=DR.cur?.5:.7, fc=Math.cos(S.yaw), fs=Math.sin(S.yaw);
  for(var i=0;i<list.length;i++){ var d=list[i].door, dx=d.x-S.x, dy=d.y-S.y, dist=Math.hypot(dx,dy); if(dist>lim) continue;
    if((S.x-d.x)*d.nx+(S.y-d.y)*d.ny<.3) continue; if(dist>.01 && (dx*fc+dy*fs)/dist<mc) continue;
    if(dist<bd){ bd=dist; best=d; } }
  return best; }
/* a map point to the screen with the camera that drew the frame (C: yaw, pitch, focal length, horizon) */
function toScr(x,y,z){ var dx=x-C.x, dy=y-C.y, dz=z-C.z, cy=Math.cos(C.yaw), sy=Math.sin(C.yaw), p=C.pitch||0, cp=Math.cos(p), sp=Math.sin(p);
  var f=dx*cy*cp+dy*sy*cp+dz*sp; if(f<.3) return null; return [C.hx+C.foc*(-dx*sy+dy*cy)/f, C.hy-C.foc*(-dx*sp*cy-dy*sp*sy+dz*cp)/f, f]; }
function doorBox(d){ var K=UM, tx=d.ny, ty=-d.nx, pts=[[-1.5,0],[1.5,0],[-1.5,2.75],[1.5,2.75]].map(function(q){ return toScr(d.x+tx*q[0]*K+d.nx*.1, d.y+ty*q[0]*K+d.ny*.1, q[1]*K); });
  if(pts.some(function(q){ return !q; })) return null; var xs=pts.map(function(q){ return q[0]; }), ys=pts.map(function(q){ return q[1]; });
  return [Math.min.apply(null,xs), Math.min.apply(null,ys), Math.max.apply(null,xs), Math.max.apply(null,ys)]; }
/* a soft warm glow over the door and a little on the ground in front of it: no motion, it only fades in */
function doorGlow(ctx){
  var d=DR.cur; DR.hit=null; if(!d || DR.glow<.01) return; var b=doorBox(d); if(!b) return; DR.hit=[b[0]-14, b[1]-14, b[2]+14, b[3]+14];
  var cx=(b[0]+b[2])/2, cy=(b[1]+b[3])/2, rx=Math.max(26,(b[2]-b[0])*.95), ry=Math.max(34,(b[3]-b[1])*.78), g=DR.glow, gr;
  ctx.save(); ctx.globalCompositeOperation='lighter'; ctx.translate(cx,cy); ctx.scale(1,ry/rx);
  gr=ctx.createRadialGradient(0,0,0,0,0,rx); gr.addColorStop(0,'rgba(255,208,140,'+(.26*g).toFixed(3)+')'); gr.addColorStop(.55,'rgba(255,186,110,'+(.09*g).toFixed(3)+')'); gr.addColorStop(1,'rgba(255,170,90,0)');
  ctx.fillStyle=gr; ctx.beginPath(); ctx.arc(0,0,rx,0,6.2832); ctx.fill(); ctx.restore();
  var f=toScr(d.x+d.nx*2.2*UM, d.y+d.ny*2.2*UM, 0); if(f){ var fw=Math.max(30,(b[2]-b[0])*1.2), fh=fw*.22; ctx.save(); ctx.globalCompositeOperation='lighter'; ctx.translate(f[0],f[1]); ctx.scale(1,fh/fw);
    gr=ctx.createRadialGradient(0,0,0,0,0,fw); gr.addColorStop(0,'rgba(255,200,130,'+(.2*g).toFixed(3)+')'); gr.addColorStop(1,'rgba(255,180,100,0)'); ctx.fillStyle=gr; ctx.beginPath(); ctx.arc(0,0,fw,0,6.2832); ctx.fill(); ctx.restore(); } }
function inHit(x,y){ var h=DR.hit; return !!(h && x>=h[0] && x<=h[2] && y>=h[1] && y<=h[3]); }
/* the pin in the street card: the real name, a map-pin glyph and a very small key cap; announced once to a screen reader */
function pinShow(d){
  var H=S.hud; if(!H || !H.pin) return;
  if(d){ H.pn.textContent=d.name||''; H.pin.setAttribute('aria-label','Enter '+(d.name||'this building')+' (E)'); H.pin.classList.add('on'); H.pin.removeAttribute('aria-hidden'); H.pin.tabIndex=0;
    H.live.textContent=(d.name||'A building')+'. Press E to go in.'; }
  else { H.pin.classList.remove('on'); H.pin.setAttribute('aria-hidden','true'); H.pin.tabIndex=-1; if(de_().contains(document.activeElement) && document.activeElement===H.pin && R.ov) try{ R.ov.focus({preventScroll:true}); }catch(x){} } }
function doorFrame(dt){
  if(DR.busy) return; var d=findDoor();
  if(d){ DR.t=Math.min(1,DR.t+dt); if(!DR.cur && DR.t>=.25){ DR.cur=d; pinShow(d); } else if(DR.cur && DR.cur!==d){ DR.cur=d; pinShow(d); } }
  else { DR.t=Math.max(0,DR.t-dt*3); if(DR.cur && DR.t<=0){ DR.cur=null; pinShow(null); } }
  DR.glow=DR.cur?Math.min(1,DR.glow+dt*2.2):Math.max(0,DR.glow-dt*3); if(!DR.cur && DR.glow<=.01) DR.hit=null; }
/* ── the veil: dark, over everything, so the map under a detail page is never seen going in or out ── */
function veilEl(){ if(!DR.veil){ var v=document.createElement('div'); v.id='pal-fpv-veil'; v.setAttribute('aria-hidden','true'); document.body.appendChild(v); DR.veil=v; } return DR.veil; }
function veil(to, ms){ var v=veilEl(); v.style.transition=ms>0?'opacity '+ms+'ms '+(to?'ease-in':'ease-out'):'none'; void v.offsetHeight; v.style.opacity=String(to); }
function ease(u){ return u<.5?4*u*u*u:1-Math.pow(-2*u+2,3)/2; }
function angTo(a,b){ var d=b-a; while(d>Math.PI) d-=6.2832; while(d<-Math.PI) d+=6.2832; return d; }
/* a scripted camera move (the dolly) in place of the walking tick */
function cineStep(ms){
  var c=DR.cine; if(!c) return; c.el=Math.min(c.dur,c.el+ms); var u=c.dur>0?c.el/c.dur:1, e=ease(u), f=c.from, t=c.to, nxx=f.x+(t.x-f.x)*e, nyy=f.y+(t.y-f.y)*e;
  if(!blockedAt(nxx,nyy)){ S.x=nxx; S.y=nyy; } S.yaw=f.yaw+angTo(f.yaw,t.yaw)*e; S.pitch=f.pitch+(t.pitch-f.pitch)*e; S.vx=S.vy=0; S.speed=0;
  plan(false); stream(!!S.hold);
  if(c.el>=c.dur){ DR.cine=null; if(c.then) c.then(); } }
function openDoor(){
  var d=DR.cur; if(!d || DR.busy || !S.on || typeof window.showDetail!=='function') return false;
  DR.busy=1; var tok=++DR.tok, rd=reduced(), stop=PRX()+1.1, ex=d.x+d.nx*stop, ey=d.y+d.ny*stop;
  if(blockedAt(ex,ey)){ ex=S.x; ey=S.y; }
  DR.mem={x:S.x, y:S.y, yaw:S.yaw, pitch:S.pitch, view:S.view, id:d.id, name:d.name, ex:ex, ey:ey, eyaw:Math.atan2(-d.ny,-d.nx), real:!!S.real};
  clearKeys(); S.drag=null; if(R.ov) R.ov.classList.remove('drag');
  var dur=rd?0:DOLLY_MS; veil(1, rd?FADE_MS:DOLLY_MS);
  DR.cine={el:0, dur:rd?FADE_MS:dur, from:{x:S.x,y:S.y,yaw:S.yaw,pitch:S.pitch}, to:rd?{x:S.x,y:S.y,yaw:S.yaw,pitch:S.pitch}:{x:ex,y:ey,yaw:DR.mem.eyaw,pitch:0}, then:function(){ finishOpen(tok); }};
  return true; }
function abortOpen(){ if(DR.busy!==1) return false; DR.tok++; DR.busy=0; DR.cine=null; veil(0, 200); return true; }
function finishOpen(tok){
  if(tok!==DR.tok || DR.busy!==1) return; DR.busy=2; var mem=DR.mem;
  if(insideEnter(mem)){ DR.busy=0; return; }                  /* [inside] the building's lobby; its directory opens the page (insideOpen -> openDetail). No GL / no room: straight to the page, as before */
  openDetail(mem); }
function openDetail(mem){
  DR.ret={mem:mem, opened:false, tm:0}; watchClose();
  exitCore(false);
  try{ if(mem.page) mkOpenPage(mem.page); else window.showDetail('node', mem.id); }catch(err){                /* mem.page: a landmark's page (palace_ride_mark.py) */ if(window.console) console.warn('door', err); }
  if(de_().classList.contains('detail-open')) DR.ret.opened=true;
  DR.busy=0;
  setTimeout(function(){ veil(0, 360); }, 30);
  DR.ret.tm=setTimeout(function(){ if(DR.ret && !DR.ret.opened && !de_().classList.contains('detail-open')) comeBack(); }, 900); }
function watchClose(){
  if(DR.mo) return;
  DR.mo=new MutationObserver(function(){ var r=DR.ret; if(!r) return; var open=de_().classList.contains('detail-open'); if(open){ r.opened=true; return; } if(r.opened) comeBack(); });
  DR.mo.observe(de_(), {attributes:true, attributeFilter:['class']}); }
function comeBack(){
  var r=DR.ret; DR.ret=null; if(!r) return; clearTimeout(r.tm); var mem=r.mem, h=de_();
  if(S.on || R.active || !h.classList.contains('alto-palace') || h.classList.contains('mobile') || h.classList.contains('printing')){ veil(0,150); return; }
  veil(1, 0);
  var ok=false, pg=mem.real&&typeof REAL!=='undefined'?REAL.exit(mem.ex,mem.ey):[mem.ex,mem.ey];
  try{ ok=!!enter(pg[0], pg[1], mem.eyaw, mem.real?{view:mem.view, hold:false, at:{x:mem.ex,y:mem.ey,h:mem.eyaw}}:{view:mem.view, hold:false}); }catch(err){ if(window.console) console.warn('door', err); }
  if(!ok){ veil(0,200); return; }
  try{ if(typeof UIX!=='undefined' && UIX && UIX.sync) UIX.sync(); }catch(x){}
  var rd=reduced(), tk=++DR.tok; S.pitch=mem.pitch; DR.busy=3;
  if(mem.real && !S.real){ DR.busy=0; veil(0, FADE_MS); return; }                       /* the real data is gone: stand where the lattice put us */
  var dur=rd?0:DOLLY_MS; S.yaw=rd?mem.yaw:mem.eyaw;
  if(rd){ S.x=mem.x; S.y=mem.y; var fr=freeNear(S.x,S.y); S.x=fr[0]; S.y=fr[1]; plan(true); stream(true); DR.busy=0; veil(0, FADE_MS); return; }
  DR.cine={el:0, dur:dur, from:{x:S.x,y:S.y,yaw:S.yaw,pitch:S.pitch}, to:{x:mem.x,y:mem.y,yaw:mem.yaw,pitch:mem.pitch}, then:function(){ if(tk===DR.tok) DR.busy=0; }};
  veil(0, dur); }
/* the key: E goes in, Esc during the dolly cancels it, nothing else is heard while the camera is moving by itself */
function doorKey(e){
  if(IN.on) return insideKey(e);
  if(DR.busy){ if(e.key==='Escape'){ if(DR.busy===1) abortOpen(); else if(DR.busy===3 && DR.cine) cineStep(1e9); } return true; }
  if(DR.cur && !e.repeat && (e.code==='KeyE' || e.key==='e' || e.key==='E')){ openDoor(); return true; }
  return false; }
/* leaving roam by any other road ends whatever the doors were doing */
function doorReset(){ insideReset(); var was=DR.busy; DR.tok++; DR.busy=0; DR.cine=null; DR.cur=null; DR.t=0; DR.glow=0; DR.hit=null; if(S.hud && S.hud.pin) pinShow(null); if(was && !DR.ret && DR.veil) veil(0,150); }
function doorClick(e){
  if(!S.on || DR.busy) return false; if(!inHit(e.clientX,e.clientY)) return false; return openDoor(); }
function doorHover(e){ var on=!!(S.on && !DR.busy && DR.cur && inHit(e.clientX,e.clientY)); if(R.ov && R.ov.classList.contains('rm-dh')!==on) R.ov.classList.toggle('rm-dh', on); }
"""

CSS_DOOR = r"""
  #pal-ride .rm-left{position:absolute;left:24px;top:20px;display:flex;flex-direction:column;align-items:flex-start;gap:8px;max-width:min(520px,calc(100vw - 420px));}
  #pal-ride .rm-pin{display:inline-flex;align-items:center;gap:8px;max-width:100%;box-sizing:border-box;padding:6px 9px 6px 11px;border-radius:999px;cursor:pointer;color:#fff;font:600 13px/1.2 system-ui,-apple-system,"Segoe UI",sans-serif;
    background:rgba(14,16,26,.62);border:1px solid rgba(255,255,255,.16);opacity:0;visibility:hidden;pointer-events:none;transition:opacity .3s ease,visibility 0s linear .3s;}
  #pal-ride .rm-pin.on{opacity:1;visibility:visible;pointer-events:auto;transition:opacity .3s ease;}
  #pal-ride .rm-pin:hover{background:rgba(44,48,72,.82);}
  #pal-ride .rm-pin:focus-visible{outline:2px solid #ffd166;outline-offset:2px;}
  #pal-ride .rm-pin svg{flex:none;width:14px;height:14px;color:#ffd166;}
  #pal-ride .rm-pin b{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0;}
  #pal-ride .rm-pin kbd{flex:none;font:600 9.5px/1 system-ui,-apple-system,sans-serif;padding:2px 4px;border-radius:4px;border:1px solid rgba(255,255,255,.28);color:rgba(255,255,255,.62);}
  #pal-ride.rm.rm-dh .pr-cv{cursor:pointer;}
  #pal-ride .pr-chip kbd{flex:none;font:600 9.5px/1 system-ui,-apple-system,sans-serif;padding:2px 4px;border-radius:4px;border:1px solid rgba(255,255,255,.28);color:rgba(255,255,255,.62);}
  #pal-fpv-veil{position:fixed;left:0;top:0;right:0;bottom:0;z-index:100000;background:#05060a;opacity:0;pointer-events:none;}
  html.printing #pal-fpv-veil{display:none !important;}
  @media (max-width:900px){ #pal-ride .rm-left{max-width:calc(100vw - 48px);top:64px;} }
  @media (prefers-reduced-motion: reduce){ #pal-ride .rm-pin,#pal-ride .rm-pin.on{transition:none;} }
"""
