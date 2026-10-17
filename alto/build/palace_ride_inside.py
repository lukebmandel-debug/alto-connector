"""Part INSIDE of the first-person city (FPV phase 2): going into a node building, from its door, and looking down on the street from its upper floors.

Before this, E at a door went straight to the building's detail page. Now it goes INSIDE (the dolly and the dark veil of palace_ride_door.py, unchanged), and the page is opened from the
building's directory board in the lobby ("Open <name>", E or a click), which uses the same showDetail flow and the same way back as the door (openDetail / comeBack).

  JS_INSIDE_GL  (shared scope)    glInside(b, d): the interior shell of a building in the GL vertex layout, in metres (1 m = UM = 1.3 units), for the floors from..to:
                                  floor slab, ceiling with light panels, plaster walls with a wainscot and WINDOW OPENINGS between pillars (sill 0.9 m, head 2.7 m, ~1.9 m wide every ~3 m),
                                  a doorway on the door wall of the ground floor, and a free-standing directory board facing the entrance. The shell is its own buffer (GLX.inside), drawn
                                  after the world by glDrawWorld (palace_ride_gl.py) with culling off and NOT in the shadow pass, with the interior materials 27..31 of the world shader
                                  (palace_ride_gl_shaders.py: lit by the room, not by the sun, no fog).
                                  Seeing the street through the windows costs nothing: the world's own buildings are single-sided (back faces culled), so from inside the footprint the building's
                                  exterior walls and roof are not drawn at all - the real street, trees, traffic and neighbours are simply there behind the openings. (The eaves and the roof get an
                                  underside - glSolid, palace_ride_gl.py - so that looking UP from a street is not looking through the roof.)
  JS_INSIDE     (inside the ROAM closure, spliced into palace_ride_e.JS_E)
                                  insideEnter(mem)   called by palace_ride_door.py finishOpen when the veil is dark: the camera is put 3.2 m inside the door, facing in, the shell is built, the
                                                     veil fades; false (no GL, no ring, no room) -> the old direct page.
                                  walking            roam's own walking with insideBlocked() as the wall test (the footprint inset by the player's radius, the board a post); the player cannot leave
                                                     except by the door.
                                  floors             [ and ] (PageDown / PageUp, or the two small chevrons) glide the eye to the next floor in 600 ms (an ease, no jump; none under
                                                     prefers-reduced-motion), 3.4 m a floor, as many floors as the building's real height holds; the quiet indicator reads '3 / 12'.
                                  the directory      within 12 m of the board on the ground floor, facing it: a card with the building's name and "Open <name>" (E, or a click).
                                  leaving            Esc, the quiet 'Leave' button, or walking into the doorway: fade out and stand on the doorstep, facing the street.
"""

JS_INSIDE_GL = r"""
/* ── the inside of a node building (palace_ride_inside.py): the shell for floors fa..fb ── */
var IN_FH=3.4, IN_F0=.22;
/* the layout of one wall Lm metres long: pillars (p), windows (w, 1.9 m wide, a slot of ~3 m each) and, on the ground floor of the door wall, the doorway (d, 3 m) */
function inSpans(Lm,dpar){
  var out=[], parts=dpar>=0?[[0,Math.max(0,dpar-1.5),0],[Math.max(0,dpar-1.5),Math.min(Lm,dpar+1.5),1],[Math.min(Lm,dpar+1.5),Lm,0]]:[[0,Lm,0]];
  parts.forEach(function(sp){ var s0=sp[0], s1=sp[1], w=s1-s0; if(w<.02) return;
    if(sp[2]){ out.push({t:'d',a:s0,b:s1}); return; }
    if(w<3.1){ out.push({t:'p',a:s0,b:s1}); return; }
    var nw=Math.max(1,Math.floor(w/3.0)), slot=w/nw, ww=Math.min(1.9,slot-1.0), pe=s0;
    for(var k=0;k<nw;k++){ var c=s0+slot*(k+.5), w0=c-ww/2, w1=c+ww/2; out.push({t:'p',a:pe,b:w0}); out.push({t:'w',a:w0,b:w1}); pe=w1; }
    out.push({t:'p',a:pe,b:s1}); });
  return out; }
/* the middle of every window opening: {x,y} just inside the wall, {nx,ny} into the room, {edge,len} */
function insideWindows(ring,sg){ var n=ring.length/2, K=UM, o=[];
  for(var i=0;i<n;i++){ var j=(i+1)%n, Ax=ring[2*i], Ay=ring[2*i+1], dx=ring[2*j]-Ax, dy=ring[2*j+1]-Ay, l=Math.hypot(dx,dy); if(l<.5) continue; var ux=dx/l, uy=dy/l, nx=-sg*dy/l, ny=sg*dx/l;
    inSpans(l/K,-1).forEach(function(it){ if(it.t!=='w') return; var m=(it.a+it.b)/2*K; o.push({x:Ax+ux*m, y:Ay+uy*m, nx:nx, ny:ny, edge:i, len:it.b-it.a}); }); }
  return o; }
/* d = {ring (flat, decimated), area sign, zb, fa, fb, door:{x,y,nx,ny}, board:{x,y,nx,ny}|null}; returns a GBuf */
function glInside(b,d){
  var ring=d.ring, n=ring.length/2, sg=d.sg, K=UM, FH=IN_FH*K, i, f;
  glDC(null); _gH=0; _gL=0;
  /* which edge holds the door, and where along it */
  var de=-1, dpar=0, db=1e18, dr=d.door;
  for(i=0;i<n;i++){ var j=(i+1)%n, ax=ring[2*i], ay=ring[2*i+1], ex=ring[2*j]-ax, ey=ring[2*j+1]-ay, l2=ex*ex+ey*ey||1e-9, t=Math.max(0,Math.min(1,((dr.x-ax)*ex+(dr.y-ay)*ey)/l2)), px=ax+ex*t-dr.x, py=ay+ey*t-dr.y, q=px*px+py*py;
    if(q<db){ db=q; de=i; dpar=t*Math.sqrt(l2)/K; } }
  for(f=d.fa; f<=d.fb; f++){
    var z0=d.zb+IN_F0*K+f*FH, zc=z0+FH-.25*K;
    gflat(b,ring,z0,28,0,true);                                   /* the floor */
    gflat(b,ring,zc,29,0,false);                                  /* the ceiling, with its light panels */
    for(i=0;i<n;i++){
      var j2=(i+1)%n, Ax=ring[2*i], Ay=ring[2*i+1], Bx=ring[2*j2], By=ring[2*j2+1], dx=Bx-Ax, dy=By-Ay, l=Math.hypot(dx,dy), Lm=l/K; if(l<.5) continue;
      var nx=-sg*dy/l, ny=sg*dx/l;                                /* into the room */
      var ux=dx/l, uy=dy/l;
      function P(s,zz){ return [Ax+ux*s*K, Ay+uy*s*K, z0+zz*K]; }
      function Q(s0,s1,m0,m1){ if(s1-s0<.02||m1-m0<.02) return; _gL=Lm; gquad(b,P(s0,m0),P(s1,m0),P(s1,m1),P(s0,m1),nx,ny,0,s0,s1,m0,m1,27,0); }
      var CH=IN_FH-.25;                                           /* CH: the height of the wall, to the underside of the ceiling slab */
      inSpans(Lm,(f===0&&i===de)?dpar:-1).forEach(function(it){
        if(it.t==='d') Q(it.a,it.b,2.75,CH);                      /* the doorway: open to 2.75 m, a header above */
        else if(it.t==='p') Q(it.a,it.b,0,CH);                    /* a pillar */
        else { Q(it.a,it.b,0,.9); Q(it.a,it.b,2.7,CH); } });       /* a window: wall under it and over it, open between */
    }
  }
  /* the directory board: a dark post-and-frame box with a lit face turned to the entrance, 1.4 m wide, standing from 0.2 to 2.3 m */
  var bd=d.board; if(bd && d.fa<=0){
    var zb0=d.zb+IN_F0*K, bn=[bd.nx,bd.ny], bt=[bd.ny,-bd.nx], yaw=Math.atan2(bd.ny,bd.nx);
    glDC(null); _gH=0; _gL=0;
    gbox(b,bd.x,bd.y,.07*K,.78*K,zb0+.12*K,zb0+2.32*K,yaw,31,0,true);
    var fx=bd.x+bn[0]*.08*K, fy=bd.y+bn[1]*.08*K, hw=.7*K, zf0=zb0+.5*K, zf1=zb0+2.2*K;
    _gL=1.4; gquad(b,[fx-bt[0]*hw,fy-bt[1]*hw,zf0],[fx+bt[0]*hw,fy+bt[1]*hw,zf0],[fx+bt[0]*hw,fy+bt[1]*hw,zf1],[fx-bt[0]*hw,fy-bt[1]*hw,zf1],bn[0],bn[1],0,0,1.4,0,1.7,30,0);
    var bx0=bd.x-bn[0]*.08*K, by0=bd.y-bn[1]*.08*K;
    gquad(b,[bx0+bt[0]*hw,by0+bt[1]*hw,zf0],[bx0-bt[0]*hw,by0-bt[1]*hw,zf0],[bx0-bt[0]*hw,by0-bt[1]*hw,zf1],[bx0+bt[0]*hw,by0+bt[1]*hw,zf1],-bn[0],-bn[1],0,0,1.4,0,1.7,30,0); }
  return b; }
function glInsideSet(d){
  if(!glOk()) return null; var old=GLX.inside; if(old) glFree(old); GLX.inside=null; if(!d) return null;
  var b=new GBuf(); glInside(b,d); var o=glUpload(b); GLX.inside=o; return o; }
"""

JS_INSIDE = r"""
/* ── inside a node building (palace_ride_inside.py) ── */
var IN={on:false, busy:0, tok:0, ring:null, sg:1, zb:0, nf:1, f:0, z:0, gl:null, door:null, board:null, mem:null, id:null, name:'', k:-99, ui:null, near:false, shown:false, builds:0, gen:-1, hint:null};
var IN_R_DIR=12, IN_PR=.62;                                    /* inside, the player's circle is half a metre: you can stand at a window */
function insideDecimate(r){ var n=r.length/2; if(n<=60) return r.slice(); var kk=Math.ceil(n/60), q=[]; for(var i=0;i<n;i+=kk) q.push(r[2*i],r[2*i+1]); return q; }
/* the point (x,y) is in the room and at least `pr` from every wall */
function insideClear(ring,x,y,pr){ var n=ring.length/2, inside=false, j=n-1, pr2=pr*pr;
  for(var i=0;i<n;i++){ var ax=ring[2*i], ay=ring[2*i+1], bx=ring[2*j], by=ring[2*j+1];
    if((ay>y)!==(by>y) && x<(bx-ax)*(y-ay)/(by-ay)+ax) inside=!inside;
    var ex=bx-ax, ey=by-ay, l2=ex*ex+ey*ey, t=l2>0?((x-ax)*ex+(y-ay)*ey)/l2:0; t=t<0?0:t>1?1:t; var qx=ax+t*ex-x, qy=ay+t*ey-y; if(qx*qx+qy*qy<pr2) return false;
    j=i; }
  return inside; }
function insideBlocked(x,y){ if(!insideClear(IN.ring,x,y,IN_PR)) return true; var b=IN.board; if(b){ var dx=x-b.x, dy=y-b.y, rr=IN_PR+.55*UM; if(dx*dx+dy*dy<rr*rr && IN.f===0) return true; } return false; }
function insideFloorZ(f){ return IN.zb+IN_F0*UM+f*IN_FH*UM; }
function insideShell(){
  var k=Math.max(0,Math.min(IN.nf-1,Math.round((IN.z-IN.zb-IN_F0*UM)/(IN_FH*UM))));
  var gen=GLX.gen; if(k===IN.k && IN.gen===gen && GLX.inside) return; IN.k=k; IN.gen=gen; IN.builds++;
  glInsideSet({ring:IN.ring, sg:IN.sg, zb:IN.zb, fa:Math.max(0,k-1), fb:Math.min(IN.nf-1,k+1), door:IN.door, board:IN.board}); }
/* ── the HUD parts: the floor indicator, Leave, the directory card ── */
function insideUI(){
  if(IN.ui) return IN.ui; var root=S.hud.root;
  var fl=document.createElement('div'); fl.className='rm-fl'; fl.setAttribute('role','group'); fl.setAttribute('aria-label','Floors');
  fl.innerHTML='<button type="button" class="rm-flb" data-in="down" aria-label="Floor down ([)"><svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></button>'
    +'<span class="rm-fln" aria-hidden="true"></span>'
    +'<button type="button" class="rm-flb" data-in="up" aria-label="Floor up (])"><svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2.5 7.5 6 4l3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></button>'
    +'<button type="button" class="rm-lv" data-in="leave" aria-label="Leave the building (Escape)">Leave <kbd aria-hidden="true">Esc</kbd></button>';
  var dr=document.createElement('div'); dr.className='rm-dir'; dr.setAttribute('role','group'); dr.setAttribute('aria-label','Directory');
  dr.innerHTML='<div class="rm-dcap">Directory</div><div class="rm-dnm"></div><button type="button" class="rm-dgo" data-in="open"><span class="rm-dtx">Open</span><kbd aria-hidden="true">E</kbd></button>';
  var lv=document.createElement('div'); lv.className='pr-live rm-live'; lv.setAttribute('aria-live','polite');
  root.appendChild(fl); root.appendChild(dr); root.appendChild(lv);
  IN.ui={fl:fl, fln:fl.querySelector('.rm-fln'), dr:dr, dnm:dr.querySelector('.rm-dnm'), dtx:dr.querySelector('.rm-dtx'), dgo:dr.querySelector('.rm-dgo'), live:lv, up:fl.querySelector('[data-in=up]'), dn:fl.querySelector('[data-in=down]')};
  [fl,dr].forEach(function(el){ el.addEventListener('click', function(e){ var b=e.target.closest&&e.target.closest('[data-in]'); if(!b) return; e.preventDefault(); e.stopPropagation(); var a=b.getAttribute('data-in');
    if(a==='up') insideGo(1); else if(a==='down') insideGo(-1); else if(a==='leave') insideLeave(); else if(a==='open') insideOpen(); }); });
  return IN.ui; }
function insideUIRefresh(){ var u=insideUI(); u.fln.textContent=(IN.f+1)+' / '+IN.nf; u.up.disabled=IN.f>=IN.nf-1; u.dn.disabled=IN.f<=0; u.fl.classList.toggle('one', IN.nf<2);
  u.live.textContent='Floor '+(IN.f+1)+' of '+IN.nf+'.'; }
function insideDirShow(on){ var u=insideUI(); if(on===IN.near) return; IN.near=on; u.dr.classList.toggle('on', on); u.dgo.tabIndex=on?0:-1; u.dr.setAttribute('aria-hidden', on?'false':'true');
  if(on){ u.dnm.textContent=IN.name; u.dtx.textContent='Open '+IN.name; u.dgo.setAttribute('aria-label','Open '+IN.name+' (E)'); u.live.textContent='Directory: '+IN.name+'. Press E to open it.'; }
  else if(document.activeElement===u.dgo && R.ov) try{ R.ov.focus({preventScroll:true}); }catch(x){} }
/* ── in ── */
function insideEnter(mem){
  if(IN.on || !glOk()) return false;
  var sol=null, list=doorsAround(); for(var i=0;i<list.length;i++){ if(list[i].door && list[i].door.id===mem.id){ sol=list[i]; break; } }
  if(!sol || !sol.ring || sol.ring.length<6) return false;
  var d=sol.door, ring=insideDecimate(sol.ring), n=ring.length/2, a2=0; for(i=0;i<n;i++){ var j=(i+1)%n; a2+=ring[2*i]*ring[2*j+1]-ring[2*j]*ring[2*i+1]; }
  var sg=a2>0?1:-1, hm=(sol.h-(sol.z0||0))/UM, nf=Math.max(1,Math.min(150,Math.floor(hm/IN_FH))), K=UM, sp=null, deep=[3.2,2.4,1.8,1.3];
  for(i=0;i<deep.length && !sp;i++){ var sx=d.x-d.nx*deep[i]*K, sy=d.y-d.ny*deep[i]*K; if(insideClear(ring,sx,sy,IN_PR+.2)) sp=[sx,sy]; }
  if(!sp) return false;
  var bd=null, offs=[[5.4,2.6],[4.6,-2.6],[3.8,2.6],[3.8,-2.6],[6.5,0],[2.8,2.2],[2.8,-2.2]];
  for(i=0;i<offs.length && !bd;i++){ var bx=d.x-d.nx*offs[i][0]*K+d.ny*offs[i][1]*K, by=d.y-d.ny*offs[i][0]*K-d.nx*offs[i][1]*K;
    if(insideClear(ring,bx,by,1.4*K) && Math.hypot(bx-sp[0],by-sp[1])>2.2*K) bd={x:bx, y:by, nx:d.nx, ny:d.ny}; }
  IN.ring=ring; IN.sg=sg; IN.zb=sol.z0||0; IN.nf=nf; IN.f=0; IN.z=insideFloorZ(0); IN.gl=null; IN.door={x:d.x,y:d.y,nx:d.nx,ny:d.ny}; IN.board=bd; IN.mem=mem; IN.id=mem.id; IN.name=mem.name||d.name||''; IN.k=-99; IN.gen=-1; IN.near=false; IN.busy=0; IN.tm=0;
  IN.on=true; var pu=insideUI(); pu.dr.classList.remove('on'); pu.dr.setAttribute('aria-hidden','true'); insideUIRefresh();
  S.x=sp[0]; S.y=sp[1]; S.yaw=Math.atan2(-d.ny,-d.nx); S.pitch=0; S.vx=S.vy=0; S.speed=0; plan(true); stream(true);
  DR.busy=0; DR.cine=null; DR.cur=null; DR.t=0; DR.glow=0; DR.hit=null; pinShow(null);
  R.ov.classList.add('rm-in'); insideShell(); veil(0, reduced()?FADE_MS:360);
  return true; }
/* ── floors ── */
function insideGo(df){
  if(!IN.on || IN.busy) return false; var t=Math.max(0,Math.min(IN.nf-1,IN.f+df)); if(t===IN.f) return false;
  IN.f=t; var to=insideFloorZ(t); insideUIRefresh();
  if(reduced()){ IN.z=to; IN.gl=null; insideShell(); return true; }
  IN.gl={el:0, dur:600, from:IN.z, to:to}; return true; }
function insideGlide(ms){ var g=IN.gl; if(!g) return; g.el=Math.min(g.dur,g.el+ms); var u=g.dur>0?g.el/g.dur:1; IN.z=g.from+(g.to-g.from)*ease(u); if(g.el>=g.dur){ IN.z=g.to; IN.gl=null; } insideShell(); }
/* per frame: the glide, the directory card, the doorway */
function insideFrame(dt){
  if(!IN.on) return; if(IN.gl) insideGlide(dt*1000); else if(!GLX.inside || IN.gen!==GLX.gen) insideShell();
  if(IN.busy) return;
  var b=IN.board, on=false;
  if(b && IN.f===0 && !IN.gl){ var dx=b.x-S.x, dy=b.y-S.y, dist=Math.hypot(dx,dy), lim=(IN.near?IN_R_DIR+3:IN_R_DIR)*UM; if(dist<lim && (dist<2.5*UM || (dx*Math.cos(S.yaw)+dy*Math.sin(S.yaw))/Math.max(dist,.01)>(IN.near?.35:.55))) on=true; }
  insideDirShow(on);
  var d=IN.door; if(d && IN.f===0){ var ex=d.x-S.x, ey=d.y-S.y, dd=Math.hypot(ex,ey);
    if(dd<2.6*UM && dd>.01 && S.speed>.35*UM && (S.vx*ex+S.vy*ey)/(dd*Math.max(S.speed,.01))>.5) insideLeave(); } }
/* ── out, and on to the page ── */
function insideTeardown(){ IN.on=false; IN.gl=null; IN.board=null; IN.ring=null; IN.near=false; if(GLX.inside){ glFree(GLX.inside); GLX.inside=null; }
  if(R.ov) R.ov.classList.remove('rm-in'); if(IN.ui){ IN.ui.dr.classList.remove('on'); IN.ui.dgo.tabIndex=-1; } }
function insideLeave(){
  if(!IN.on || IN.busy) return false; IN.busy=1; var tok=++IN.tok, m=IN.mem; veil(1, reduced()?150:260);
  setTimeout(function(){ if(tok!==IN.tok || !IN.on) return; insideTeardown(); IN.busy=0;
    var fr=freeNear(m.ex, m.ey); S.x=fr[0]; S.y=fr[1]; S.yaw=m.eyaw+Math.PI; S.pitch=0; S.vx=S.vy=0; S.speed=0; plan(true); stream(true); veil(0, reduced()?FADE_MS:320); }, reduced()?170:280);
  return true; }
function insideOpen(){
  if(!IN.on || IN.busy || typeof window.showDetail!=='function') return false; IN.busy=1; var tok=++IN.tok, m=IN.mem; veil(1, reduced()?150:260);
  setTimeout(function(){ if(tok!==IN.tok || !IN.on) return; insideTeardown(); IN.busy=0; DR.busy=2; openDetail(m); }, reduced()?170:280);
  return true; }
function insideReset(){ if(!IN.on && !GLX.inside) return; IN.tok++; IN.busy=0; insideTeardown(); }
function insideKey(e){
  if(IN.busy) return true;
  var k=e.key, c=e.code;
  if(k==='Escape'){ insideLeave(); return true; }
  if((c==='KeyE'||k==='e'||k==='E') && !e.repeat){ if(IN.near){ insideOpen(); return true; } return false; }
  if(!e.repeat){ if(k==='['||c==='BracketLeft'||k==='PageDown'){ insideGo(-1); return true; } if(k===']'||c==='BracketRight'||k==='PageUp'){ insideGo(1); return true; } }
  return false; }
var INSIDEAPI={ on:function(){ return IN.on; }, go:insideGo, leave:insideLeave, open:insideOpen, step:function(ms){ insideGlide(ms); }, frame:insideFrame, 
  state:function(){ return {on:IN.on, busy:IN.busy, floor:IN.f, floors:IN.nf, z:IN.z, gliding:!!IN.gl, near:IN.near, name:IN.name, id:IN.id, builds:IN.builds, board:IN.board, door:IN.door, shell:GLX.inside?{n:GLX.inside.n}:null, label:IN.ui?IN.ui.fln.textContent:''}; },
  windows:function(){ return IN.on?insideWindows(IN.ring,IN.sg):[]; }, blocked:function(x,y){ return IN.on?insideBlocked(x,y):null; }, shell:function(){ return GLX.inside; } };
"""

CSS_INSIDE = r"""
  #pal-ride .rm-fl,#pal-ride .rm-dir{display:none;}
  #pal-ride.rm-in .rm-fl{display:flex;align-items:center;gap:3px;position:absolute;right:20px;bottom:22px;padding:4px 5px 4px 9px;border-radius:999px;pointer-events:auto;background:rgba(14,16,26,.55);border:1px solid rgba(255,255,255,.14);
    font:600 12px/1 system-ui,-apple-system,"Segoe UI",sans-serif;color:rgba(255,255,255,.88);}
  #pal-ride .rm-fl.one .rm-flb,#pal-ride .rm-fl.one .rm-fln{display:none;}
  #pal-ride .rm-fln{min-width:42px;text-align:center;font-variant-numeric:tabular-nums;letter-spacing:.02em;}
  #pal-ride .rm-flb{width:24px;height:24px;display:inline-flex;align-items:center;justify-content:center;padding:0;border-radius:50%;border:0;background:transparent;color:inherit;cursor:pointer;}
  #pal-ride .rm-flb svg{width:12px;height:12px;}
  #pal-ride .rm-flb:hover:not(:disabled){background:rgba(255,255,255,.14);}
  #pal-ride .rm-flb:disabled{opacity:.3;cursor:default;}
  #pal-ride .rm-flb:focus-visible,#pal-ride .rm-lv:focus-visible,#pal-ride .rm-dgo:focus-visible{outline:2px solid #ffd166;outline-offset:2px;}
  #pal-ride .rm-lv{display:inline-flex;align-items:center;gap:6px;margin-left:4px;padding:5px 10px;border-radius:999px;border:0;background:rgba(255,255,255,.1);color:inherit;font:600 12px/1 system-ui,-apple-system,sans-serif;cursor:pointer;}
  #pal-ride .rm-lv:hover{background:rgba(255,255,255,.2);}
  #pal-ride .rm-lv kbd,#pal-ride .rm-dgo kbd{flex:none;font:600 9.5px/1 system-ui,-apple-system,sans-serif;padding:2px 4px;border-radius:4px;border:1px solid rgba(255,255,255,.28);color:rgba(255,255,255,.62);}
  #pal-ride.rm-in .rm-dir{display:block;position:absolute;left:50%;bottom:70px;transform:translateX(-50%);min-width:220px;max-width:min(420px,calc(100vw - 48px));box-sizing:border-box;padding:12px 14px 12px;border-radius:14px;text-align:center;
    background:rgba(14,16,26,.7);border:1px solid rgba(255,255,255,.16);color:#fff;opacity:0;visibility:hidden;pointer-events:none;transition:opacity .3s ease,visibility 0s linear .3s;}
  #pal-ride.rm-in .rm-dir.on{opacity:1;visibility:visible;pointer-events:auto;transition:opacity .3s ease;}
  #pal-ride .rm-dcap{font:600 10px/1 system-ui,-apple-system,sans-serif;letter-spacing:.14em;text-transform:uppercase;opacity:.55;}
  #pal-ride .rm-dnm{margin:7px 0 10px;font:700 15px/1.25 system-ui,-apple-system,"Segoe UI",sans-serif;overflow-wrap:anywhere;}
  #pal-ride .rm-dgo{display:inline-flex;align-items:center;gap:8px;max-width:100%;padding:7px 13px;border-radius:999px;border:1px solid rgba(255,255,255,.22);background:rgba(255,209,102,.16);color:#fff;font:700 13px/1.2 system-ui,-apple-system,sans-serif;cursor:pointer;}
  #pal-ride .rm-dgo:hover{background:rgba(255,209,102,.3);}
  #pal-ride .rm-dtx{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0;}
  #pal-ride.rm-in .rm-hint,#pal-ride.rm-in .rm-pin{display:none;}
  @media (max-width:900px){ #pal-ride.rm-in .rm-fl{bottom:64px;} }
  @media (prefers-reduced-motion: reduce){ #pal-ride.rm-in .rm-dir,#pal-ride.rm-in .rm-dir.on{transition:none;} }
"""
