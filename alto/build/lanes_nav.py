"""Going round a horizontal timeline (brief.mode "lanes"): guided travel with a magnetic settle.

Luke (2026-10-16): the horizontal timeline should have "a bit more of an
automatic feeling for going around it, as opposed to a free form where you can
scroll wherever you want". The first answer (1.9.88: every gesture one event,
locked out until it landed) was, in his words, "too rigid to navigate now". So
this is the middle: the camera moves as freely and as far as the hand says, but
only ALONG the story, and when the hand stops it comes to rest on an event.

The path: the main line's events in page order (ACT_SEQS flattened), each with
the view it rests in — centred across; up and down the line kept where the main
line sat when the page opened, moved only as far as it must to keep the card
clear of the bars at the top and the rail at the bottom. Strung together they are
the path. Across is the input: wheel, trackpad, a drag (mouse, pen, touch screen)
move the camera along it one px for one; the height follows by itself, level at
every event and easing between (so it dips into a flashback's past track and back
up with the line). Up-and-down input is the same travel (a vertical wheel, a
vertical drag); nobody scrolls the height by hand. A view off the path (a
character's own event reached with ↑ / ↓, the page as it opens, a scrollbar)
is carried as an offset that fades over the next few hundred px of travel.

Inertia: a trackpad's own inertia tail is just more, smaller wheel events, so it
is more travel, never a new gesture. A mouse notch moves about a third of the gap
to the next event, chased smoothly; a fast spin adds up. A flung drag coasts and
slows. Nothing is swallowed and nothing is locked out.

The magnetic settle: SETTLE ms after the last movement the camera glides (the
engine's curve, _altoEase) on to an event: the next one in the direction of
travel once BIAS of the gap has been covered toward it (BIAS_MIN..BIAS_MAX px),
otherwise back onto the one it came from / passed. Any input interrupts the settle
where it is: a wheel takes over with the glide's speed, a hand stops it dead.
Resting is exact: the canvas's own whole-px offsets (the engine's scroll axis).

The deliberate steps stay: ← / → / Space / PageUp / PageDown / Home / End and the
rail's buttons go exactly one event (each landing before the next, up to three
waiting, like the engine's _hop). ↑ / ↓ go to the nearest event on the next line
over (lanes.py). A click on a card enlarges it; Enter enlarges the current one.

Character focus: clicking a character in the key, or its label on the page,
keeps that line (lanes.py isolate) and the path is then only that character's
events: its own and the ones it is on the page for. Click again, or Esc, for all.
A timeline with no `present` and no flashbacks (a v1 brief) has every event on
the path, in page order.

The rail: n / N (the nearest event while travelling, the one at rest when still),
the flashback's name, a thumb that moves with the camera and can be dragged along
the path, and the toggle for the whole timeline fitted to the window (clicking a
spot there comes back down to the event nearest it).

Safari: the wheel is held (non-passive) on #canvas only; every scroll write goes
through the engine's whole-px axis; the document never scrolls; #glass-slab is
never resized (the whole timeline's backdrop is a fixed layer of its own).
Phones keep the engine's card-by-card view and its swipe-peek: none of this runs
there. prefers-reduced-motion: travel follows the hand with no smoothing, steps
and settles jump.

Geometry read from window._altoLanesGeo (lanes.py): x[id], y[id] (card centre,
world px without WORLD_PAD_TOP), h[id], lines [{id, y, ev}], W, H, and at[id] =
{x, y, line, flash}: where the event sits on its line.
"""

NAV_CSS = """
  /* the rail: where you are in the story, and the way to the whole timeline (lanes_nav.py) */
  #lanes-nav{ position:fixed; z-index:305; left:50%; bottom:22px; transform:translateX(-50%); display:flex; align-items:center; gap:4px;
    height:40px; box-sizing:border-box; padding:0 6px; border-radius:20px; color:var(--muted); font-size:12px; user-select:none; -webkit-user-select:none;
    background:var(--card-glass-bg, var(--surface));
    -webkit-backdrop-filter:blur(18px) saturate(190%) brightness(var(--card-glass-bright, 1)); backdrop-filter:blur(18px) saturate(190%) brightness(var(--card-glass-bright, 1));
    border:1px solid var(--card-glass-border, var(--border)); box-shadow:0 10px 26px var(--node-rest-shadow), inset 0 0 0 0.5px var(--card-glass-rim); }
  #lanes-nav button{ all:unset; box-sizing:border-box; width:28px; height:28px; border-radius:50%; display:flex; align-items:center; justify-content:center; cursor:pointer; color:var(--muted); }
  #lanes-nav button:hover{ color:var(--text); background:color-mix(in srgb,var(--text) 8%,transparent); }
  #lanes-nav button:focus-visible{ outline:2px solid var(--accent); outline-offset:1px; }
  #lanes-nav button[aria-pressed="true"]{ color:var(--accent); }
  #lanes-nav button:disabled{ opacity:.3; cursor:default; background:none; }
  #lanes-nav{ transition:opacity .25s; }
  #lanes-nav.lnv-away{ opacity:0; pointer-events:none; }
  #lanes-nav .lnv-mid{ display:flex; flex-direction:column; justify-content:center; gap:4px; width:250px; padding:0 4px; }
  #lanes-nav .lnv-txt{ display:flex; align-items:baseline; gap:7px; white-space:nowrap; overflow:hidden; font-variant-numeric:tabular-nums; line-height:1; }
  #lanes-nav .lnv-txt b{ color:var(--text); font-weight:700; }
  #lanes-nav .lnv-tag{ overflow:hidden; text-overflow:ellipsis; font-weight:700; letter-spacing:.03em; }
  #lanes-nav .lnv-tag button{ display:inline-flex; width:auto; height:auto; padding:0 3px; margin-left:3px; border-radius:4px; font-size:11px; }
  #lanes-nav .lnv-rail{ position:relative; height:12px; cursor:pointer; touch-action:none; }
  #lanes-nav .lnv-rail::before{ content:''; position:absolute; left:0; right:0; top:5px; height:2px; border-radius:1px; background:color-mix(in srgb,var(--muted) 35%,transparent); }
  #lanes-nav .lnv-fb{ position:absolute; top:4px; height:4px; border-radius:2px; background:color-mix(in srgb,var(--muted) 75%,transparent); min-width:4px; }
  #lanes-nav .lnv-thumb{ position:absolute; left:0; top:1px; width:10px; height:10px; margin-left:-5px; border-radius:50%; background:var(--accent); cursor:grab;
    box-shadow:0 0 0 2px var(--surface); will-change:transform; }
  #lanes-nav .lnv-thumb:focus-visible{ outline:2px solid var(--accent); outline-offset:2px; }
  #lanes-nav.scrub .lnv-thumb{ cursor:grabbing; }
  .lnv-sr{ position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; }
  html.mobile #lanes-nav, html.detail-open #lanes-nav, html.printing #lanes-nav, html.alto-editing #lanes-nav{ display:none !important; }
  /* the camera keeps to the path: nothing pans the board by itself */
  html.alto-lanes:not(.mobile):not(.alto-editing) #canvas{ touch-action:none; overscroll-behavior:none; }
  html.alto-lanes:not(.mobile):not(.alto-editing) #canvas.ln-drag{ cursor:grabbing; }
  html.alto-lanes:not(.mobile) #world .node[data-ln] .node-card:focus{ outline:none; }
  html.alto-lanes:not(.mobile) #world .node[data-ln] .node-card:focus-visible{ outline:2px solid var(--accent); outline-offset:3px; }
  /* the event the steps are on */
  html.alto-lanes.ln-stepped:not(.mobile) #world .node.ln-cur:not(.focused) .node-card{ box-shadow:0 0 0 2px color-mix(in srgb,var(--accent) 60%,transparent), 0 10px 26px var(--node-rest-shadow); }
  /* the whole timeline, fitted to the window */
  html.alto-lanes #canvas.ln-ov{ cursor:zoom-in; }
  html.alto-lanes #canvas.ln-ov.ln-drag{ cursor:grabbing; }
  html.alto-lanes #canvas.ln-ov #world, html.alto-lanes #canvas.ln-ovanim #world{ pointer-events:none; transform-origin:0 0; will-change:transform; }
"""

NAV_JS = r"""
(function(){
var L=window._ALTO_LANES; if(!L) return;
var de=document.documentElement;
if(de.classList.contains('mobile')) return;          // phones: the engine's card-by-card view and swipe-peek
/* travel (see the docstring): the settle waits SETTLE ms of stillness; the wheel is chased
   with TAU_CHASE; a flung drag coasts as far as TAU_FLING of its speed; the settle goes on to the next event
   once BIAS of the gap (BIAS_MIN..BIAS_MAX px) is travelled toward it */
var SETTLE=170, TAU_CHASE=55, TAU_FLING=330, FLING_MIN=.12, FLING_MAX=5, COAST_PW=2.5, OFFLEN=260, MINSEG=56,
    BIAS=.12, BIAS_MIN=12, BIAS_MAX=48, NOTCH=.34, NOTCH_MIN=90, NOTCH_MAX=240, NOTCH_MS=260, SOFT=12, SFN=4.000244140625, LONE=40, GESTURE=120,
    QMAX=3, OV_MIN=0.14;
var RM=window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
function reduced(){ return !!(RM && RM.matches); }
function cv(){ return document.getElementById('canvas'); }
function geo(){ return window._altoLanesGeo; }
function PAD(){ return typeof WORLD_PAD_TOP!=='undefined' ? WORLD_PAD_TOP : 0; }
function on(){ return !!geo() && !de.classList.contains('mobile') && !de.classList.contains('alto-editing') && !de.classList.contains('printing'); }
function busyElsewhere(){
  return de.classList.contains('detail-open') || !!window._focusedNodeId ||
    !!document.querySelector('#notes-panel.open,#summary-wrap.open,#ef-panel.open,#bg-panel.open,#note-dialog.visible,#search-btn.expanded,#share-dialog.visible');
}
/* the same curve as every other glide (the engine's _altoEase, B(1.4,2.6)); the table is only a fallback */
var _tab=(function(){ var M=1000, c=[0], s=0, i, x; for(i=0;i<M;i++){ x=(i+.5)/M; s+=Math.pow(x,.4)*Math.pow(1-x,1.6); c.push(s); } for(i=0;i<=M;i++) c[i]/=s; return c; })();
function ease(p){ if(window._altoEase) return window._altoEase(p); if(p<=0) return 0; if(p>=1) return 1; var f=p*1000, i=Math.floor(f); return _tab[i]+(_tab[i+1]-_tab[i])*(f-i); }
/* longer hops take a little longer, as a hand's do: gentle, never a rush (1.9.67) */
function glideMs(d){ return Math.round(Math.min(1100, Math.max(560, 460+.2*d))); }
/* the canvas's scroll, written through the engine's whole-px axis (Safari floors a
   written offset under the page's zoom; engine_patches fly-scrolls-in-whole-px) */
function axis(prop){
  var c=cv();
  if(window._altoScrollAxis) return window._altoScrollAxis(prop);
  return {at:function(){ return c[prop]; }, stop:function(v){ return Math.round(v); }, go:function(v){ c[prop]=v; }};
}

/* ── the stops ─────────────────────────────────────────────────────────── */
function pageOrder(){
  var G=geo(), seen={}, out=[], src=(typeof ACT_SEQS!=='undefined' ? [].concat.apply([],ACT_SEQS) : []).concat(L.order||[], Object.keys(L.ev));
  src.forEach(function(id){ if(!seen[id] && L.ev[id] && G && G.x[id]!=null){ seen[id]=1; out.push(id); } });
  return out;
}
/* v1 data (no one on the page anywhere, no flashbacks): the side lines carry the story, so every event is a stop */
function legacy(){
  if((L.flashbacks||[]).length) return false;
  for(var k in L.ev){ var p=L.ev[k].present; if(p && p.length) return false; }
  return true;
}
function live(id){ return !!document.querySelector('#node-'+id+' .node-card') && (!window._altoShown || window._altoShown(id)); }
function lineDef(id){ for(var i=0;i<L.lines.length;i++) if(L.lines[i].id===id) return L.lines[i]; return null; }
function charOf(){ var k=window._altoLanesLock ? window._altoLanesLock() : null; return (k && k!=='main' && lineDef(k)) ? k : null; }
function ofChar(id, c){
  var e=L.ev[id], ln=lineDef(c); if(!e) return false;
  if(e.l===c || (e.present||[]).indexOf(c)>=0) return true;
  return !!ln && ((ln.presence||[]).indexOf(id)>=0 || ln.from===id || ln.to===id);
}
var _S=null;       // cached per call chain: {ids, at}
function stops(){
  var o=pageOrder(), c=charOf(), lg=legacy();
  var ids=o.filter(function(id){ if(!live(id)) return false; if(c) return ofChar(id,c); return lg || (L.ev[id].l||'main')==='main'; });
  if(!ids.length) ids=o.filter(live);
  var at={}; o.forEach(function(id,i){ at[id]=i; });
  return _S={ids:ids, at:at, ch:c};
}
function neighbour(id, dir){
  var S=stops(), i=S.ids.indexOf(id);
  if(i>=0) return S.ids[i+dir]||null;
  var oi=S.at[id]; if(oi==null) return dir>0 ? S.ids[0] : S.ids[S.ids.length-1];
  /* an event off the main line: on to its page-order neighbour */
  if(dir>0){ for(var k=0;k<S.ids.length;k++) if(S.at[S.ids[k]]>oi) return S.ids[k]; return null; }
  for(var j=S.ids.length-1;j>=0;j--) if(S.at[S.ids[j]]<oi) return S.ids[j]; return null;
}
function flashOf(id){ var f=(L.ev[id]||{}).flash; if(!f) return null; var fb=(L.flashbacks||[]).filter(function(q){ return q.id===f; })[0]; return fb||null; }
function title(id){ var n=(typeof NODES_SRC!=='undefined'?NODES_SRC:[]).filter(function(q){ return q.id===id; })[0]; return n ? (n.title||'') : ''; }

/* ── the camera ─────────────────────────────────────────────────────────── */
function zk(c){ var r=c.getBoundingClientRect(); return (r.width && c.offsetWidth) ? r.width/c.offsetWidth : 1; }
function worldOff(c){ var w=document.getElementById('world'), ox=0, oy=0, q=w; while(q && q!==c){ ox+=q.offsetLeft; oy+=q.offsetTop; q=q.offsetParent; } return {x:ox, y:oy}; }
function shown(el){ if(!el) return null; var r=el.getBoundingClientRect(); return (r.width && r.height && getComputedStyle(el).display!=='none') ? r : null; }
/* the part of the canvas no chrome sits over: under the key's toggle, above the rail */
function band(c){
  var r=c.getBoundingClientRect(), k=zk(c), ch=c.clientHeight, t=16, b=ch-16, q;
  if((q=shown(document.getElementById('key-toggle'))) && q.bottom>r.top) t=Math.max(t,(q.bottom-r.top)/k+12);
  if((q=shown(document.getElementById('lanes-nav'))) && q.top<r.bottom) b=Math.min(b,(q.top-r.top)/k-14);
  if(b-t<160){ t=16; b=ch-16; }
  return {t:t, b:b};
}
function lineY(G, id){ for(var i=0;i<G.lines.length;i++){ var l=G.lines[i]; if(l.ev && l.ev.indexOf(id)>=0) return l.y; } return G.lines[0] ? G.lines[0].y : G.y[id]; }
function anchor(id){
  var G=geo(), a=(G.at && G.at[id]) || (G.anchor && G.anchor[id]);
  if(a && a.x!=null && a.y!=null) return {x:a.x, y:a.y};
  return {x:G.x[id], y:lineY(G,id)};
}
var _home=null;    // where (canvas px from its top) the main line sat when the page opened
function home(c, B){
  if(_home==null){
    var G=geo(), my=(G.lines[0]?G.lines[0].y:0)+PAD()+worldOff(c).y-c.scrollTop;
    _home=Math.max(B.t+80, Math.min(B.b-80, my));
  }
  return Math.max(B.t, Math.min(B.b, _home));
}
/* where the main line rests: the opening height, moved (once, for every event alike) so that
   the tallest card above the line and the deepest below it both fit between the bars and the
   rail; if they cannot all fit, the middle of the misfit. The camera follows the MAIN LINE and
   nothing else: it never moves up or down to suit one event's card or a character's track
   (that was the bounce). Only a flashback's dip, which is the main line itself, moves it. */
var _fit=null;
function mainAt(id){ var G=geo(), a=anchor(id), ev=G.at && G.at[id];       // the main line's height at this event (a character's own event: the page's height beside it)
  return (ev && ev.line && ev.line!=='main' && G.mainY!=null) ? G.mainY : a.y; }
function fitHome(c, B, ids){
  var G=geo(), up=0, dn=0;
  ids.forEach(function(id){ var m=mainAt(id), h=G.h[id]||120, top=(G.y[id]!=null?G.y[id]:m)-h/2;
    up=Math.max(up, m-Math.min(m,top)); dn=Math.max(dn, Math.max(m,top+h)-m); });
  var lo=B.t+up, hi=B.b-dn, h0=home(c,B);
  return lo<=hi ? Math.max(lo,Math.min(hi,h0)) : (lo+hi)/2;
}
function lineHome(c, B){ if(_fit==null || _fit.t!==B.t || _fit.b!==B.b) _fit={t:B.t, b:B.b, y:fitHome(c,B,stops().ids)}; return _fit.y; }
/* the scroll offsets that put this event where it rests */
function camFor(id, B){
  var c=cv(), G=geo(), off=worldOff(c), P=PAD(), a=anchor(id);
  B=B||band(c);
  var cw=c.clientWidth, ch=c.clientHeight;
  var tl=a.x+off.x-cw/2;
  var tt=mainAt(id)+P+off.y-lineHome(c,B);      // the main line stays where it rests, whatever this event's card or line does
  return {l:Math.max(0,Math.min(tl, c.scrollWidth-cw)), t:Math.max(0,Math.min(tt, c.scrollHeight-ch)), ml:c.scrollWidth-cw, mt:c.scrollHeight-ch};
}

/* ── the path: the stops' resting views strung together in page order ──────
   The camera travels along it. Where it is along the path (u, px) is the only
   thing the wheel, a drag or a fling change; across and up and down follow from
   it: across moves with u one for one, up and down eases from one stop's rest
   height to the next (smoothstep, so it is level at every stop and dips into a
   flashback's past track and back up with the line). A view that is not on the
   path (a character's own event, the page as it opened, a scrollbar drag) is an
   offset (ox, oy) from the nearest point of the path, which fades out over the
   next few hundred px of travel, so nothing ever jumps back onto the path. */
var M={u:0, uT:0, pend:[], vel:0, ox:0, oy:0, raf:0, last:0, input:-1e9, dir:1, restU:0, restId:null, gl:null, drag:null, pth:null, wr:null, near:null, stale:false};
function buildPath(){
  var c=cv(), S=stops(), B=band(c), ids=S.ids, P=[], U=[], ml=0, mt=0;
  _fit={t:B.t, b:B.b, y:fitHome(c,B,ids)};
  for(var i=0;i<ids.length;i++){
    var t=camFor(ids[i],B); ml=t.ml; mt=t.mt; P.push([t.l,t.t]);
    U.push(i ? U[i-1]+Math.max(MINSEG, Math.abs(t.l-P[i-1][0])) : 0);
  }
  if(!ids.length){ ml=c.scrollWidth-c.clientWidth; mt=c.scrollHeight-c.clientHeight; }
  return M.pth={ids:ids, P:P, U:U, end:U.length ? U[U.length-1] : 0, ml:ml, mt:mt};
}
function seg(u){ var U=M.pth.U, lo=0, hi=U.length-2; if(hi<0) return 0; while(lo<hi){ var m=(lo+hi+1)>>1; if(U[m]<=u) lo=m; else hi=m-1; } return lo; }
function sm(f){ return f*f*(3-2*f); }
function pathAt(u){
  var p=M.pth, P=p.P; if(!P.length) return [cv().scrollLeft, cv().scrollTop]; if(P.length<2) return [P[0][0],P[0][1]];
  var i=seg(u), a=P[i], b=P[i+1], f=Math.max(0,Math.min(1,(u-p.U[i])/(p.U[i+1]-p.U[i])));
  return [a[0]+(b[0]-a[0])*f, a[1]+(b[1]-a[1])*sm(f)];
}
function fracAt(u){ var U=M.pth.U; if(U.length<2) return 0; var i=seg(u); return i+Math.max(0,Math.min(1,(u-U[i])/(U[i+1]-U[i]))); }
/* the point of the path nearest a view: across first, then height; ties go to the nearest u */
function project(L,T){
  var p=M.pth, P=p.P, U=p.U, n=P.length, best=0, bd=Infinity;
  if(n<2) return 0;
  for(var i=0;i<n-1;i++){
    var a=P[i], b=P[i+1], dl=b[0]-a[0], fs=[0,1,.5];
    if(Math.abs(dl)>.5) fs.push(Math.max(0,Math.min(1,(L-a[0])/dl)));
    for(var j=0;j<fs.length;j++){
      var u=U[i]+(U[i+1]-U[i])*fs[j], q=pathAt(u), d=Math.abs(q[0]-L)+.5*Math.abs(q[1]-T)+.001*Math.abs(u-M.u);
      if(d<bd){ bd=d; best=u; }
    }
  }
  return best;
}
function stopIx(id){ return M.pth ? M.pth.ids.indexOf(id) : -1; }
/* take the camera from wherever the view is now */
function resync(){
  var c=cv(), L=axis('scrollLeft').at(), T=axis('scrollTop').at();
  buildPath();
  var k=stopIx(_cur), u=(k>=0 && _land && !moved(c)) ? M.pth.U[k] : project(L,T), q;
  M.u=M.uT=u; q=pathAt(u); M.ox=L-q[0]; M.oy=T-q[1]; M.pend.length=0; M.vel=0;
  M.wr=[c.scrollLeft, c.scrollTop]; M.near=null;
}
function invalidate(){ _fit=null; if(M.raf) M.stale=true; else M.pth=null; }
function extMoved(){ var c=cv(); return !M.wr || Math.abs(c.scrollLeft-M.wr[0])>2 || Math.abs(c.scrollTop-M.wr[1])>2; }
/* any input: the camera is taken from where it is, with no jump. A glide in flight
   hands its speed on to the travel (grab: a hand on the board stops it dead) */
function prepare(grab){
  if(M.gl){
    var g=M.gl; M.gl=null; if(g.step){ _busy=false; _q.length=0; }
    M.uT=M.u+(grab||reduced() ? 0 : M.vel*TAU_CHASE);
  } else if(!M.raf || !M.pth || extMoved()){
    resync(); M.restU=M.u; M.restId=(_land && !moved(cv())) ? _cur : null;
  }
  if(grab){ M.pend.length=0; M.uT=M.u; }
  de.classList.add('ln-stepped');
}
function clampU(u){ return Math.max(0, Math.min(M.pth.end, u)); }
/* travel by d px; a notch's travel (soft) is let out over NOTCH_MS on a smooth (half-cosine)
   ramp, so a mouse's discrete clicks still start and stop like a glide */
function addTravel(d, soft){
  if(!on() || _ov || window._focusedNodeId) return;
  prepare(false); if(!d) return;
  var now=performance.now();
  M.dir=d>0?1:-1;
  if(soft && !reduced()) M.pend.push({a:d, t0:now, f:0}); else M.uT=clampU(M.uT+d);
  M.input=now; wake();
}
function release(now){
  for(var i=M.pend.length-1;i>=0;i--){
    var q=M.pend[i], p=Math.min(1,(now-q.t0)/NOTCH_MS), f=(1-Math.cos(Math.PI*p))/2;
    M.uT=clampU(M.uT+q.a*(f-q.f)); q.f=f; if(p>=1) M.pend.splice(i,1);
  }
}
function fade(du){ if(du){ var k=Math.exp(-Math.abs(du)/OFFLEN); M.ox*=k; M.oy*=k; if(Math.abs(M.ox)<.05) M.ox=0; if(Math.abs(M.oy)<.05) M.oy=0; } }
function setU(u){ u=clampU(u); fade(u-M.u); M.u=M.uT=u; }
function wake(){ if(!M.raf){ M.last=performance.now(); M.raf=requestAnimationFrame(tick); } }
function stopLoop(){ if(M.raf) cancelAnimationFrame(M.raf); M.raf=0; M.gl=null; M.pend.length=0; M.uT=M.u; }
/* write the view: through the engine's whole-px axis (Safari), only when it changes */
var _drawn=null;
function draw(){
  var c=cv(), q=pathAt(M.u), L=Math.max(0,Math.min(M.pth.ml,q[0]+M.ox)), T=Math.max(0,Math.min(M.pth.mt,q[1]+M.oy));
  if(_drawn && Math.abs(_drawn[0]-L)<.01 && Math.abs(_drawn[1]-T)<.01 && !extMoved()) return;
  _drawn=[L,T]; axis('scrollLeft').go(L); axis('scrollTop').go(T); M.wr=[c.scrollLeft, c.scrollTop];
}
/* the rail and the ring follow the nearest event while travelling */
function follow(){
  var p=M.pth, U=p.U, n=U.length; if(!n) return;
  var i=seg(M.u), k=(n>1 && M.u-U[i]>U[i+1]-M.u) ? i+1 : i, id=p.ids[k];
  if(id!==M.near){ M.near=id; setCur(id); ui(id,0); }
}
function thumb(){ if(!R || !M.pth) return; var N=M.pth.ids.length, f=railFrac(fracAt(M.u),N); R.thumb.style.transition='none'; R.thumb.style.transform='translateX('+(f*R.rail.clientWidth).toFixed(2)+'px)'; }
function tick(now){
  M.raf=0;
  var c=cv();
  if(!c || !on() || _ov || window._focusedNodeId){ if(M.gl && M.gl.step){ _busy=false; _q.length=0; } M.gl=null; M.pend.length=0; return; }
  if(M.stale && !M.drag){                                     // laid out again mid-travel: carry on from the view as it is
    M.stale=false; var g0=M.gl; M.gl=null; resync();
    if(g0){ glideTo(g0.id, {settle:g0.settle, step:g0.step}, g0.done); return; }
  }
  if(!M.pth) resync();
  var dt=Math.max(1,Math.min(50,now-M.last)), u0=M.u; M.last=now;
  if(M.gl){
    var g=M.gl, p=g.ms>0 ? Math.max(0,Math.min(1,(now-g.s0)/g.ms)) : 1, k=g.pw ? 1-Math.pow(1-p,g.pw) : ease(p);
    M.u=M.uT=g.u0+(g.u1-g.u0)*k; M.ox=g.ox0+(g.ox1-g.ox0)*k; M.oy=g.oy0+(g.oy1-g.oy0)*k; M.vel=(M.u-u0)/dt;
    if(p>=1){ M.gl=null; land(g); return; }
    draw(); thumb(); M.raf=requestAnimationFrame(tick); return;
  }
  {
    if(M.pend.length) release(now);
    var kk=(reduced() || M.drag) ? 1 : 1-Math.exp(-dt/TAU_CHASE), nu2=M.u+(M.uT-M.u)*kk;
    if(Math.abs(M.uT-nu2)<.05) nu2=M.uT;
    fade(nu2-M.u); M.u=nu2;
  }
  M.vel=(M.u-u0)/dt;
  draw(); follow(); thumb();
  var moving=!!M.drag || M.pend.length>0 || Math.abs(M.uT-M.u)>.05;
  if(!moving && now-M.input>=SETTLE){ settle(); return; }
  M.raf=requestAnimationFrame(tick);
}
/* the magnetic settle: input has stopped, so glide on to the nearest event, leaning the
   way the travel went (BIAS of the gap, at least BIAS_MIN and at most BIAS_MAX px into it
   is enough to go on to the next one; less eases back) */
function pick(u, dir){
  var p=M.pth, U=p.U, n=U.length; if(!n) return null;
  if(u==null) u=M.u; if(dir==null) dir=M.dir;
  if(M.restId && stopIx(M.restId)<0 && Math.abs(u-M.restU)<BIAS_MIN) return M.restId;   // barely moved off a character's event
  if(n<2 || u<=U[0]) return p.ids[0]; if(u>=U[n-1]) return p.ids[n-1];
  var i=seg(u), L=U[i+1]-U[i], into=u-U[i], th=Math.min(L/2, Math.max(BIAS_MIN, Math.min(BIAS_MAX, L*BIAS)));
  if(dir>=0) return p.ids[into>=th ? i+1 : i];
  return p.ids[(L-into)>=th ? i : i+1];
}
function settle(){
  var id=pick(); if(!id){ M.raf=0; return; }
  glideTo(id, {settle:true});
}
function settleMs(d){ return Math.round(Math.min(700, Math.max(380, 340+.6*d))); }
/* glide the camera to an event along the path (on the engine's curve); done() when it rests */
function glideTo(id, opt, done){
  opt=opt||{};
  var c=cv(); if(!c || !geo() || geo().x[id]==null){ if(done) done(); return; }
  if(M.gl){ var gx=M.gl; M.gl=null; if(gx.step && !opt.step){ _busy=false; _q.length=0; } }
  if(!M.raf || !M.pth || extMoved()) resync();
  var k=stopIx(id), u1, ox1=0, oy1=0;
  if(k>=0) u1=M.pth.U[k];
  else { var t=camFor(id); u1=project(t.l,t.t); var q1=pathAt(u1); ox1=t.l-q1[0]; oy1=t.t-q1[1]; }
  var q0=pathAt(M.u), q2=pathAt(u1), dx=(q2[0]+ox1)-(q0[0]+M.ox), dy=(q2[1]+oy1)-(q0[1]+M.oy), d=Math.sqrt(dx*dx+dy*dy);
  var ms=(opt.instant || reduced() || d<.5) ? 0 : opt.ms ? opt.ms : (opt.settle ? settleMs(d) : glideMs(d));
  setCur(id); M.near=id; _trust=true; M.pend.length=0;
  var g={id:id, u0:M.u, u1:u1, ox0:M.ox, oy0:M.oy, ox1:ox1, oy1:oy1, s0:performance.now(), ms:ms, done:done, settle:!!opt.settle, step:!!opt.step, quiet:d<.5, pw:opt.pw||0};
  if(!ms){ if(M.raf){ cancelAnimationFrame(M.raf); M.raf=0; } land(g); return; }
  M.gl=g; wake(); ui(id,0);
}
/* at rest: exactly on the offset the canvas can really take, in whole device px */
function land(g){
  var c=cv(), qx=axis('scrollLeft'), qy=axis('scrollTop'), q=pathAt(g.u1);
  var L=Math.max(0,Math.min(M.pth.ml,q[0]+g.ox1)), T=Math.max(0,Math.min(M.pth.mt,q[1]+g.oy1));
  qx.go(qx.stop(dev(L,M.pth.ml))); qy.go(qy.stop(dev(T,M.pth.mt)));
  M.u=M.uT=g.u1; M.ox=g.ox1; M.oy=g.oy1; M.vel=0; M.raf=0; M.gl=null;
  M.wr=[c.scrollLeft, c.scrollTop]; _drawn=null;
  var was=_cur;
  setCur(g.id); M.restU=g.u1; M.restId=g.id; M.near=null;
  _land=[c.scrollLeft, c.scrollTop]; _trust=false;
  ui(g.id,0); if(!g.quiet || was!==g.id) announce(g.id);
  if(g.done) g.done();
}
function dev(v, max){ var z=zk(cv())*(window.devicePixelRatio||1); if(!(z>0)) return v; var r=Math.round(v*z)/z; if(max!=null && r>max) r=Math.floor(max*z)/z; return Math.max(0,r); }
/* ── where the camera is ──────────────────────────────────────────────────── */
var _cur=null, _land=null, _trust=false, _busy=false, _q=[];
function moved(c){ return !_land || Math.abs(c.scrollLeft-_land[0])>3 || Math.abs(c.scrollTop-_land[1])>3; }
/* the event the view is on: a glide's destination; while travelling, the nearest stop;
   at rest, the last one landed on unless the view has been moved since — then the stop
   whose resting view is nearest the view as it is (ties: the first in page order, so
   the page as it opens is on the first event) */
function current(){
  var c=cv(); if(!c || !geo()) return null;
  if(M.gl) return M.gl.id;
  if(M.raf && M.near) return M.near;
  if(_cur && geo().x[_cur]!=null && live(_cur) && (_trust || !moved(c))) return _cur;
  var S=stops().ids, B=band(c), best=null, bd=Infinity;
  for(var i=0;i<S.length;i++){ var t=camFor(S[i],B), d=Math.abs(t.l-c.scrollLeft)+Math.abs(t.t-c.scrollTop); if(d<bd-0.5){ bd=d; best=S[i]; } }
  return best;
}
function cancelAll(){ var was=!!M.raf; stopLoop(); _q.length=0; _busy=false; M.drag=null; if(was){ _land=null; _trust=false; } }
function setCur(id){
  if(_cur===id) return;
  document.querySelectorAll('#world .node.ln-cur').forEach(function(n){ n.classList.remove('ln-cur'); });
  _cur=id; var n=id && document.getElementById('node-'+id); if(n) n.classList.add('ln-cur');
}
/* the deliberate steps (← → Space PageUp PageDown Home End, the rail's buttons): one
   event each, each landing before the next starts (the engine's _hop): up to three
   wait their turn, a held key's repeat adds at most one */
function step(dir, src, repeat){
  if(!on() || _ov) return;
  if(_busy){ if(repeat ? !_q.length : _q.length<QMAX) _q.push([dir,src]); return; }
  run(dir, src);
}
function run(dir, src){
  var from=current(), nx=null;
  if(typeof dir==='string') nx=dir;
  else if(M.raf && !M.gl && M.pth && M.pth.ids.length){       // mid-travel: the next event ahead of the camera that way
    var U=M.pth.U, I=M.pth.ids, k;
    if(dir>0){ for(k=0;k<U.length && !nx;k++) if(U[k]>M.u+1) nx=I[k]; if(!nx) nx=I[I.length-1]; }
    else { for(k=U.length-1;k>=0 && !nx;k--) if(U[k]<M.u-1) nx=I[k]; if(!nx) nx=I[0]; }
  }
  else nx=from ? neighbour(from, dir) : stops().ids[dir>0?0:stops().ids.length-1];
  if(!nx){ if(from && (from!==_cur || moved(cv()))) glideTo(from,{step:true}); return; }      // the end: rest on the last one
  de.classList.add('ln-stepped');
  _busy=true;
  glideTo(nx, {step:true}, function(){ _busy=false; var q=_q.shift(); if(q) run(q[0], q[1]); });
  if(src==='key') focusCard(nx);
}
window._altoLanesStep=function(d){ step(d,'api'); };       // for tests and the rail
window._altoLanesCurrent=function(){ return current(); };
window._altoLanesTravel=function(){ return M.pth ? {u:M.u, end:M.pth.end, U:M.pth.U.slice(), ids:M.pth.ids.slice(), P:M.pth.P.map(function(q){ return [Math.round(q[0]),Math.round(q[1])]; }), moving:!!M.raf, settling:!!(M.gl && M.gl.settle)} : null; };   // for tests
function focusCard(id){
  var c=document.querySelector('#node-'+id+' .node-card'); if(!c) return;
  if(!c.hasAttribute('tabindex')) c.setAttribute('tabindex','0');
  try{ c.focus({preventScroll:true}); }catch(e){}
}

/* ── the stops in the engine's own hops (an enlarged card's ← / →) ─────────── */
var _navPrev=window._altoLanesNav;
window._altoLanesNav=function(id, dir){
  if(!geo() || de.classList.contains('mobile')) return null;
  var r=(dir==='e'||dir==='w') ? neighbour(id, dir==='e'?1:-1) : (_navPrev ? _navPrev(id, dir) : null);
  if(r && window._focusedNodeId){ setCur(r); _trust=true; ui(r,0); }     // the engine is hopping the enlarged card there
  return r;
};

/* ── keys ──────────────────────────────────────────────────────────────── */
document.addEventListener('keydown', function(e){
  if(!on() || e.metaKey || e.ctrlKey || e.altKey) return;
  var k=e.key;
  if(k==='Escape' && _ov){ e.preventDefault(); e.stopPropagation(); ovLeave(null); return; }
  if(k==='Escape'){ setTimeout(function(){ invalidate(); ui(current(),0); },0); return; }     // lanes.py lets go of a kept line: all events again
  if(window._focusedNodeId || busyElsewhere()) return;
  var ae=document.activeElement, tg=ae && ae.tagName;
  if(tg==='INPUT' || tg==='TEXTAREA' || tg==='SELECT' || (ae && ae.isContentEditable)) return;
  var onCtl=(tg==='BUTTON' || tg==='A' || (ae && ae.getAttribute && ae.getAttribute('role')==='button'));
  var d=null, sh=e.shiftKey;
  if(k==='ArrowRight' && !sh) d=1; else if(k==='ArrowLeft' && !sh) d=-1;
  else if(k==='PageDown' || (k===' ' && !sh && !onCtl)) d=1;
  else if(k==='PageUp' || (k===' ' && sh && !onCtl)) d=-1;
  else if(k==='Home' && !onCtl) d='first'; else if(k==='End' && !onCtl) d='last';
  else if((k==='ArrowUp' || k==='ArrowDown') && !sh) d=k==='ArrowUp'?'n':'s';
  else if(k==='Enter' && !onCtl){
    var cur=current(); if(!cur) return;
    e.preventDefault(); cancelAll(); if(window.enterFocus) window.enterFocus(cur); return;
  }
  if(d==null) return;
  if(_ov){ e.preventDefault(); return; }
  e.preventDefault();
  if(d==='first'){ step(stops().ids[0],'key'); return; }
  if(d==='last'){ var S=stops().ids; step(S[S.length-1],'key'); return; }
  if(d==='n'||d==='s'){
    /* up and down: the nearest event on the next line over (lanes.py) */
    if(_busy){ return; }
    var from=current(), nx=from && _navPrev ? _navPrev(from, d) : null;
    if(nx) step(nx,'key');
    return;
  }
  step(d,'key',e.repeat);
}, true);
/* Tab onto a card: the camera goes to it the same way (not the browser's jump) */
var _tabAt=null;
document.addEventListener('keydown', function(e){ if(e.key==='Tab'){ var c=cv(); _tabAt=c?[c.scrollLeft,c.scrollTop,performance.now()]:null; } }, true);
document.addEventListener('focusin', function(e){
  if(!on() || _ov || window._focusedNodeId) return;
  var n=e.target && e.target.closest && e.target.closest('#world .node[data-ln]'); if(!n) return;
  var id=n.id.slice(5), c=cv();
  if(id===_cur || !_tabAt || performance.now()-_tabAt[2]>500) return;    // only Tab: a click's focus is the engine's to enlarge
  c.scrollLeft=_tabAt[0]; c.scrollTop=_tabAt[1];                        // undo the browser's jump, then glide
  _tabAt=null; cancelAll(); step(id,'tab');
});

/* ── the wheel: travel ────────────────────────────────────────────────────
   Every wheel event is travel along the path, as far as it says: a trackpad's
   stream (and its inertia tail, which is only more, smaller events) moves the
   camera one for one, a mouse's notch moves a NOTCH-sized share of the gap to the
   next event, chased smoothly (TAU_CHASE). Nothing is swallowed and nothing waits
   its turn. When it all stops, the settle takes the camera to an event. A stream
   keeps the axis it started on (a horizontal swipe's wobble is not travel back),
   and up and down are the same travel as across: the camera's height is the path's. */
var WH={last:-1e9, ax:null, sx:0, sy:0, cand:null};
function notch(s){
  var p=M.pth; if(!p || p.U.length<2) return 120;
  var U=p.U, i=seg(M.uT); if(s<0 && M.uT<=U[i]+.5 && i>0) i--;
  var L=U[i+1]-U[i];
  return Math.min(NOTCH_MAX, Math.max(NOTCH*L, Math.min(NOTCH_MIN, .6*L)));
}
/* Safari's mouse wheel: whole multiples of 4.000244… px (a trackpad's are not) */
function sfNotch(a){ var k=Math.round(a/SFN); return k>=1 && Math.abs(a-k*SFN)<1e-4 && Math.abs(a-Math.round(a))>1e-4; }
function onWheel(e){
  if(!on() || e.ctrlKey || e.metaKey) return;
  if(window._focusedNodeId) return;                         // an enlarged card: the engine's swipe hops (along the stops)
  if(_ov){ ovWheel(e); return; }
  if(busyElsewhere()) return;
  e.preventDefault();                                       // the camera stays on the path: no free scroll
  if(M.drag) return;
  var m=e.deltaMode===1?40:e.deltaMode===2?800:1, dx=e.deltaX*m, dy=e.deltaY*m, now=performance.now();
  if(e.shiftKey && !dx){ dx=dy; dy=0; }
  var gap=now-WH.last; WH.last=now;
  if(gap>GESTURE){ WH.ax=null; WH.sx=WH.sy=0; }
  WH.sx+=Math.abs(dx); WH.sy+=Math.abs(dy);
  if(!WH.ax && WH.sx+WH.sy>=4) WH.ax=WH.sx>=WH.sy ? 'x' : 'y';
  var d=WH.ax==='x' ? dx : WH.ax==='y' ? dy : (Math.abs(dx)>=Math.abs(dy) ? dx : dy);
  if(!d) return;
  prepare(false);
  var a=Math.abs(d), s=d>0?1:-1;
  var soft=false;
  if(e.deltaMode){ d=s*Math.max(a, notch(s)); soft=true; }                          // lines or pages: a notch
  else if(sfNotch(a)){ d=s*notch(s)*Math.min(3, 1+.35*(Math.round(a/SFN)-1)); soft=true; }   // Safari's notch (faster spins: bigger)
  else if(gap>=LONE){
    /* on its own (nothing within LONE ms) it was a mouse's notch: a notch's worth, however
       big its delta. Until that is known it moves at most a notch; a stream gets the rest */
    var n0=notch(s), me=WH.cand={t:now, a:a, s:s, held:Math.max(0,a-n0)};
    d=s*Math.min(a,n0); soft=a>SOFT;
    setTimeout(function(){ if(WH.cand===me && WH.last===me.t){ WH.cand=null; if(!M.pth) return; if(n0>me.a) addTravel(me.s*(n0-me.a), true); } }, LONE+5);
  } else if(WH.cand){ if(WH.cand.held && WH.cand.s===s) d+=s*WH.cand.held; WH.cand=null; }
  addTravel(d, soft);
}
/* only the canvas holds the wheel: everywhere else Safari keeps scrolling off the main thread */
function hookWheel(){ var c=cv(); if(!c || c._lnWheel) return; c._lnWheel=1; c.addEventListener('wheel', onWheel, {passive:false}); }
/* editing: the old free scroll, a mouse wheel going sideways (shift: up and down) */
document.addEventListener('wheel', function(e){
  if(!geo() || !de.classList.contains('alto-editing') || e.ctrlKey || e.metaKey || e.deltaX) return;
  var c=cv(); if(!c || !c.contains(e.target) || c.classList.contains('focus-mode')) return;
  if(e.shiftKey){ c.scrollTop+=e.deltaY; e.preventDefault(); return; }
  if(e.deltaMode===0 && Math.abs(e.deltaY)<40) return;      // a trackpad scrolls both ways by itself
  c.scrollLeft+=e.deltaY*(e.deltaMode===1?40:1); e.preventDefault();
}, {passive:false});

/* ── a drag (mouse, pen, a touch screen): the board follows the hand along the path ──
   A hand on the board stops the camera where it is. Dragging the background moves
   it along the path (the hand's across movement, or its up and down if that is how
   it set off); let go with speed and it coasts (TAU_FLING), then settles. The
   engine's own free pan never sees the drag. */
var DR=null, _noClick=0;
document.addEventListener('pointerdown', function(e){
  var c=cv(); if(!c || !c.contains(e.target) || e.button>0) return;
  if(!on() || _ov || window._focusedNodeId || busyElsewhere()) return;
  var r=c.getBoundingClientRect(), k=zk(c);
  if((e.clientX-r.left)/k>c.clientWidth || (e.clientY-r.top)/k>c.clientHeight) return;         // the scrollbars
  /* the background (a finger or a pen may set off from a card too: a tap is still a tap) */
  var bg=!(e.target.closest && e.target.closest((e.pointerType==='mouse' ? '.node-card,' : '')+'.lanes-tag,button,a,input,textarea,select,[contenteditable="true"]'));
  if(!bg){ if(M.raf){ prepare(true); M.input=performance.now(); } return; }   // a card: held still; its click enlarges it, or the settle goes on
  prepare(true);
  DR=M.drag={id:e.pointerId, x:e.clientX, y:e.clientY, lx:e.clientX, ly:e.clientY, moved:false, ax:null, smp:[]};
  M.input=performance.now(); wake();
}, true);
window.addEventListener('pointermove', function(e){
  if(!DR || e.pointerId!==DR.id) return;
  var k=zk(cv()), tx=(e.clientX-DR.x)/k, ty=(e.clientY-DR.y)/k, now=performance.now();
  if(!DR.moved){ if(Math.abs(tx)+Math.abs(ty)<5) return; DR.moved=true; DR.ax=Math.abs(tx)>=.7*Math.abs(ty) ? 'x' : 'y'; cv().classList.add('ln-drag'); }
  var d=DR.ax==='x' ? -(e.clientX-DR.lx)/k : -(e.clientY-DR.ly)/k;
  DR.lx=e.clientX; DR.ly=e.clientY;
  if(d){ M.dir=d>0?1:-1; setU(M.u+d); }
  DR.smp.push([now, M.u]); while(DR.smp.length>2 && DR.smp[0][0]<now-90) DR.smp.shift();
  M.input=now; wake();
}, true);
function dragEnd(e, fling){
  if(!DR || e.pointerId!==DR.id) return;
  var d=DR, now=performance.now(); DR=M.drag=null; cv().classList.remove('ln-drag');
  if(d.moved){
    _noClick=now;                                            // the drag's mouseup is not a click on what is under it
    var s=d.smp, a=s[0], b=s[s.length-1];
    if(fling && !reduced() && s.length>=2 && now-b[0]<60){ var v=(b[1]-a[1])/Math.max(16,b[0]-a[0]); if(Math.abs(v)>FLING_MIN && coast(Math.max(-FLING_MAX,Math.min(FLING_MAX,v)))) return; }
  }
  M.input=now; wake();
}
/* let go with speed: coast on to the event the throw reaches (where TAU_FLING of the speed
   would carry it, leaning the throw's way), slowing from the hand's own speed to rest on it
   (an ease-out whose first frame goes as fast as the hand did) */
function coast(v){
  var dir=v>0?1:-1, id=pick(clampU(M.u+v*TAU_FLING), dir), k=stopIx(id);
  if(k<0) return false;
  var D=M.pth.U[k]-M.u; if(D*v<=0 || Math.abs(D)<2) return false;
  var ms=Math.max(260, Math.min(1100, COAST_PW*D/v));
  M.dir=dir; glideTo(id, {settle:true, ms:ms, pw:Math.max(1.6, Math.min(4, v*ms/D))});
  return true;
}
window.addEventListener('pointerup', function(e){ dragEnd(e, true); }, true);
window.addEventListener('pointercancel', function(e){ dragEnd(e, false); }, true);
/* the engine's free pan reads the mouse's moves on window: not while the path has the hand */
window.addEventListener('mousemove', function(e){ if(DR) e.stopPropagation(); }, true);
document.addEventListener('click', function(e){ if(_noClick && performance.now()-_noClick<400 && cv() && cv().contains(e.target)){ _noClick=0; e.stopImmediatePropagation(); e.preventDefault(); } }, true);

/* cards gliding under a still pointer are not pointed at (the engine's hover asks the
   same; here it keeps lanes.py from isolating whichever line slides under it) */
document.addEventListener('mouseover', function(e){
  if(on() && window._altoPointerStill && window._altoPointerStill(e) && cv() && cv().contains(e.target)) e.stopPropagation();
}, true);

/* clicking a card enlarges it (the engine, on the same curve); the steps go on from it */
document.addEventListener('click', function(e){
  if(!on() || _ov) return;
  var n=e.target.closest && e.target.closest('#world .node[data-ln]'); if(!n) return;
  cancelAll(); setCur(n.id.slice(5)); _trust=true;
}, true);
/* a character's label or key row: its line is kept (lanes.py) and the steps visit only
   its events — go to the nearest of them */
document.addEventListener('click', function(e){
  if(!on() || _ov || de.classList.contains('alto-editing')) return;
  var t=e.target.closest && e.target.closest('.lanes-tag,.lk-row[data-k]'); if(!t) return;
  setTimeout(function(){   // after lanes.py's own handler (same node and phase, registered first) has kept or let go of the line
    var c=charOf(); invalidate(); ui(current(),0);
    if(!c) return;
    var from=current(); if(from && ofChar(from,c)) return;
    var S=stops(), oi=from!=null ? S.at[from] : -1, nx=null;
    for(var i=0;i<S.ids.length && !nx;i++) if(S.at[S.ids[i]]>oi) nx=S.ids[i];
    if(!nx) nx=S.ids[S.ids.length-1];
    if(nx){ cancelAll(); step(nx,'line'); }
  },0);
}, true);
/* an enlarged card's own hops and exits move the steps along with it */
var _lastFocus=null;
function watchFocus(){
  var c=cv(); if(!c || c._lnObs || !window.MutationObserver) return; c._lnObs=1;
  new MutationObserver(function(){
    if(R) R.el.classList.toggle('lnv-away', c.classList.contains('focus-mode'));    // an enlarged card has the stage
    if(c.classList.contains('focus-mode')){ if(M.raf || _busy) cancelAll(); if(window._focusedNodeId){ _lastFocus=window._focusedNodeId; setCur(_lastFocus); _trust=true; ui(_lastFocus,0); } }
    else if(_lastFocus){ setCur(_cur||_lastFocus); _trust=true; _lastFocus=null; }
  }).observe(c,{attributes:true, attributeFilter:['class']});
}

/* ── the rail ──────────────────────────────────────────────────────────── */
var R=null;
function svgI(d){ return '<svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+d+'</svg>'; }
function buildRail(){
  if(R || de.classList.contains('mobile')) return;
  var n=document.createElement('div'); n.id='lanes-nav'; n.setAttribute('role','navigation'); n.setAttribute('aria-label','Go through the timeline');
  n.innerHTML='<button type="button" class="lnv-ov" aria-pressed="false" title="The whole timeline" aria-label="The whole timeline">'
    +svgI('<rect x="2.5" y="4.5" width="15" height="11" rx="2"/><path d="M5.5 10h9M7 7.5h2M11 12.5h2"/>')+'</button>'
    +'<button type="button" class="lnv-prev" title="Previous event (←)" aria-label="Previous event">'+svgI('<path d="M12 5l-5 5 5 5"/>')+'</button>'
    +'<div class="lnv-mid"><div class="lnv-txt"><span><b class="lnv-n">1</b> / <span class="lnv-N">1</span></span><span class="lnv-tag"></span></div>'
    +'<div class="lnv-rail" title="Drag to look along the timeline"><i class="lnv-thumb" role="slider" tabindex="0" aria-label="Where you are in the story"></i></div></div>'
    +'<button type="button" class="lnv-next" title="Next event (→)" aria-label="Next event">'+svgI('<path d="M8 5l5 5-5 5"/>')+'</button>'
    +'<span class="lnv-sr" aria-live="polite"></span>';
  document.body.appendChild(n);
  R={el:n, n:n.querySelector('.lnv-n'), N:n.querySelector('.lnv-N'), tag:n.querySelector('.lnv-tag'), rail:n.querySelector('.lnv-rail'),
     thumb:n.querySelector('.lnv-thumb'), ov:n.querySelector('.lnv-ov'), prev:n.querySelector('.lnv-prev'), next:n.querySelector('.lnv-next'), sr:n.querySelector('.lnv-sr')};
  R.prev.addEventListener('click', function(){ step(-1,'rail'); });
  R.next.addEventListener('click', function(){ step(1,'rail'); });
  R.ov.addEventListener('click', function(){ if(_ov) ovLeave(null); else ovEnter(); });
  R.thumb.addEventListener('keydown', function(e){
    var d=e.key==='ArrowRight'||e.key==='ArrowUp'?1:e.key==='ArrowLeft'||e.key==='ArrowDown'?-1:0;
    if(d){ e.preventDefault(); e.stopPropagation(); step(d,'rail',e.repeat); }
  });
  scrubber();
}
function railFrac(i, N){ return N>1 ? i/(N-1) : 0; }
function railMarks(){
  if(!R) return;
  R.rail.querySelectorAll('.lnv-fb').forEach(function(x){ x.remove(); });
  var S=stops(), N=S.ids.length;
  (L.flashbacks||[]).forEach(function(fb){
    var ix=(fb.nodes||[]).map(function(id){ return S.ids.indexOf(id); }).filter(function(i){ return i>=0; });
    if(!ix.length) return;
    var a=railFrac(Math.min.apply(null,ix),N), b=railFrac(Math.max.apply(null,ix),N), m=document.createElement('i');
    m.className='lnv-fb'; m.style.left=(a*100)+'%'; m.style.width='calc('+((b-a)*100)+'% + 4px)'; m.style.marginLeft='-2px'; m.title=fb.label||'';
    R.rail.insertBefore(m, R.thumb);
  });
}
/* the rail says which event the camera is on (or nearest, travelling); the thumb is where it is */
function ui(id, ms){
  if(!R) return;
  var S=stops(), N=S.ids.length, i=S.ids.indexOf(id), pos=i;
  if(i<0 && id!=null){ var oi=S.at[id]; pos=-1; for(var k=0;k<N;k++) if(S.at[S.ids[k]]<oi) pos=k; }
  R.n.textContent=i>=0 ? String(i+1) : (pos>=0 ? (pos+1)+'+' : '–'); R.N.textContent=String(N);
  var fb=id && flashOf(id), ev=id && L.ev[id], ln=ev && ev.l!=='main' ? lineDef(ev.l) : null, c=charOf(), tag='';
  if(c){ tag=(lineDef(c)||{}).label||''; R.tag.innerHTML=''; R.tag.textContent=tag+' only'; var x=document.createElement('button'); x.type='button'; x.textContent='✕'; x.title='All events (Esc)'; x.setAttribute('aria-label','Show all events');
         x.addEventListener('click', function(e){ e.stopPropagation(); if(window._altoLanesLock) window._altoLanesLock(null); invalidate(); ui(current(),0); }); R.tag.appendChild(x); }
  else { tag=fb ? fb.label : (ln ? ln.label+' · off the page' : ''); R.tag.textContent=tag; }
  R.tag.style.color=c ? (lineDef(c)||{}).color||'' : (ln ? ln.color : '');
  R.prev.disabled=!(N && (i>0 || (i<0 && pos>=0))); R.next.disabled=!(N && (i<N-1 || (i<0 && pos<N-1)));
  var f=railFrac(Math.max(0,i>=0?i:pos+.5), N), w=R.rail.clientWidth;
  if(M.raf) return;                                          // travelling: the thumb goes with the camera (thumb())
  R.thumb.style.transition=ms ? 'transform '+ms+'ms cubic-bezier(.25,.2,.4,1)' : 'none';
  R.thumb.style.transform='translateX('+(f*w).toFixed(2)+'px)';
  R.thumb.setAttribute('aria-valuemin','1'); R.thumb.setAttribute('aria-valuemax',String(N)); R.thumb.setAttribute('aria-valuenow',String(Math.max(1,(i>=0?i:pos)+1)));
}
function announce(id){ if(!R || !id) return; var S=_S||stops(), i=S.ids.indexOf(id), ev=L.ev[id]||{}, fb=flashOf(id);
  R.sr.textContent=(i>=0?'Event '+(i+1)+' of '+S.ids.length+': ':'')+title(id)+(ev.w?', '+ev.w:'')+(fb?' — '+fb.label:''); }
/* the thumb is the grab handle: drag it to look along the timeline freely, let go to settle on the nearest event */
function scrubber(){
  var sc=null;
  function at(e){ var r=R.rail.getBoundingClientRect(); return Math.max(0,Math.min(1,(e.clientX-r.left)/(r.width||1))); }
  function look(f){                                       // along the path, as travel is
    var S=M.pth.ids, U=M.pth.U, N=S.length; if(!N) return;
    var fi=f*(N-1), a=Math.floor(fi), b=Math.min(N-1,a+1);
    setU(U[a]+(U[b]-U[a])*(fi-a)); M.input=performance.now(); wake();
    sc.f=f;
  }
  R.rail.addEventListener('pointerdown', function(e){
    if(!on() || e.button>0) return; e.preventDefault();
    if(_ov) ovLeave(null, true);
    _q.length=0; _busy=false; prepare(true); M.drag={rail:1};
    sc={S:M.pth.ids, x:e.clientX, moved:false, f:at(e), id:e.pointerId};
    try{ R.rail.setPointerCapture(e.pointerId); }catch(er){}
    if(e.target===R.thumb){ sc.moved=true; R.el.classList.add('scrub'); }
  });
  R.rail.addEventListener('pointermove', function(e){
    if(!sc || e.pointerId!==sc.id) return;
    if(!sc.moved && Math.abs(e.clientX-sc.x)<4) return;
    sc.moved=true; R.el.classList.add('scrub'); look(at(e));
  });
  function end(e){
    if(!sc || (e && e.pointerId!==sc.id)) return;
    var f=sc.moved ? sc.f : at(e), S=sc.S, i=Math.round(f*(S.length-1)); sc=null; M.drag=null; R.el.classList.remove('scrub');
    if(S[i]) step(S[i],'rail');
  }
  R.rail.addEventListener('pointerup', end);
  R.rail.addEventListener('pointercancel', function(){ sc=null; M.drag=null; M.input=performance.now(); wake(); R.el.classList.remove('scrub'); });
}

/* ── the whole timeline ─────────────────────────────────────────────────── */
var _ov=null, _ovA=null;
function ovSet(o){
  var w=document.getElementById('world'), c=cv(), off=worldOff(c);
  w.style.transform='translate('+(o.tx-off.x)+'px,'+(o.ty-off.y)+'px) scale('+o.s+')';
  ovSlab(o);
}
/* The glass slab is the timeline's own backdrop. Shrunk with the board it becomes a thin
   ribbon floating on the empty page. Zoomed out, a layer of the same colours covers the
   whole window instead (the slab fades out as it fades in), so the timeline reads as one
   landscape seen from above. The slab itself is never resized: the page's height follows
   its bottom edge. The layer is fixed under the canvas, so it adds nothing to what scrolls. */
var _sky=null;
function ovSkyOn(){
  var sl=document.getElementById('glass-slab'), c=cv(); if(!sl || !c || _sky) return;
  _sky=document.createElement('div'); _sky.id='lanes-ov-sky'; _sky.setAttribute('aria-hidden','true');
  _sky._a=parseFloat(getComputedStyle(sl).opacity); if(!(_sky._a>0)) _sky._a=1;
  _sky.style.cssText='position:fixed;left:0;right:0;bottom:0;top:var(--nav-bottom,112px);pointer-events:none;background-repeat:no-repeat;background-image:'+sl.style.backgroundImage+';opacity:0;'
    +(reduced()?'':'transition:opacity .62s cubic-bezier(.25,.2,.4,1);');
  c.parentNode.insertBefore(_sky, c);
  if(!reduced()) sl.style.transition='opacity .62s cubic-bezier(.25,.2,.4,1)';
  void _sky.offsetWidth; _sky.style.opacity=String(_sky._a); sl.style.opacity='0';
}
function ovSkyFade(){ var sl=document.getElementById('glass-slab'); if(_sky) _sky.style.opacity='0'; if(sl) sl.style.opacity=''; }
function ovSlab(o){
  var sl=document.getElementById('glass-slab'), c=cv();
  if(!o || o.s>=0.999){ if(_sky){ _sky.remove(); _sky=null; } if(sl){ sl.style.opacity=''; sl.style.transition=''; } return; }
  if(!sl || !c) return;
  if(!_sky) ovSkyOn();
  var W=geo().W*o.s, cw=c.clientWidth, gl=Math.max(0,o.tx), gr=Math.max(0,cw-(o.tx+W));   // a gap left or right of the board is covered by stretching the colours to the window's edge
  _sky.style.backgroundSize=(W+gl+gr).toFixed(1)+'px 100%'; _sky.style.backgroundPositionX=Math.min(0,o.tx).toFixed(1)+'px';
}
function ovFit(){
  var c=cv(), G=geo(), B=band(c), cw=c.clientWidth, P=PAD(), H=G.H+P;
  var s=Math.min(1,(cw-60)/G.W,(B.b-B.t-16)/H); s=Math.max(OV_MIN,s);
  var tx=cw/2-(c.scrollLeft+cw/2-worldOff(c).x)*s;          // what is in the middle now stays in the middle
  var ty=H*s<=B.b-B.t ? B.t+(B.b-B.t-H*s)/2 : B.t;
  return ovClampX({s:s, tx:tx, ty:ty});
}
function ovClampX(o){ var c=cv(), cw=c.clientWidth, Wd=geo().W*o.s; o.tx=Wd<=cw ? (cw-Wd)/2 : Math.max(cw-Wd-30, Math.min(30, o.tx)); return o; }
function ovAnim(from, to, done){
  if(_ovA) cancelAnimationFrame(_ovA);
  var c=cv(); c.classList.add('ln-ovanim');
  if(reduced()){ ovSet(to); _ovA=null; c.classList.remove('ln-ovanim'); done(); return; }
  var ms=620, s0=performance.now();
  function fr(now){
    var p=Math.min(1,(now-s0)/ms), k=ease(p);
    /* zoom in the log of the scale, so the shrinking reads as one even movement */
    var s=Math.exp(Math.log(from.s)+(Math.log(to.s)-Math.log(from.s))*k);
    var u=(Math.abs(to.s-from.s)>1e-6) ? (s-from.s)/(to.s-from.s) : k;
    ovSet({s:s, tx:from.tx+(to.tx-from.tx)*u, ty:from.ty+(to.ty-from.ty)*u});
    if(p<1) _ovA=requestAnimationFrame(fr); else { _ovA=null; c.classList.remove('ln-ovanim'); done(); }
  }
  _ovA=requestAnimationFrame(fr);
}
function ovEnter(){
  if(!on() || _ov) return;
  if(window._focusedNodeId && window.exitFocus) window.exitFocus();
  cancelAll();
  var here=current(); if(here) setCur(here);                 // Esc / the toggle come back to this one
  var c=cv(), off=worldOff(c), from={s:1, tx:off.x-c.scrollLeft, ty:off.y-c.scrollTop}, to=ovFit();
  _ov=to;
  ovHold(true); ovSet(from); c.scrollLeft=0; c.scrollTop=0; c.classList.add('ln-ov');
  if(R){ R.ov.setAttribute('aria-pressed','true'); R.ov.title='Back to the events'; }
  ovAnim(from, to, function(){});
}
/* back down to step mode, resting on this event (null: where the steps were) */
function ovLeave(id, instant){
  if(!_ov) return;
  var c=cv(), from=_ov; id=id||_cur||stops().ids[0];
  _ov=null; c.classList.remove('ln-ov','ln-drag');
  if(R){ R.ov.setAttribute('aria-pressed','false'); R.ov.title='The whole timeline'; }
  var w=document.getElementById('world'), off=worldOff(c);
  /* where the camera will rest, worked out as if the board were at scale 1 */
  w.style.transform='none';
  var B=band(c), t=camFor(id,B), qx=axis('scrollLeft'), qy=axis('scrollTop'), tl=qx.stop(dev(t.l,t.ml)), tt=qy.stop(dev(t.t,t.mt));
  ovSet(from); ovSkyFade();
  var fin=function(){ w.style.transform=''; ovSlab(null); ovHold(false); qx.go(tl); qy.go(tt); setCur(id); _land=[c.scrollLeft,c.scrollTop]; _trust=false; ui(id,0); announce(id); };
  if(instant){ fin(); return; }
  de.classList.add('ln-stepped');
  ovAnim(from, {s:1, tx:off.x-tl, ty:off.y-tt}, fin);
}
/* The scaled board no longer overflows the canvas, so where scrollbars take room (Safari
   with a mouse plugged in, "always show scrollbars") they would vanish, the canvas would
   change size and the engine would lay the whole page out again mid-zoom. A spacer the
   board's full size holds the canvas's scroll extent as it was. */
function ovHold(on){
  var c=cv(), sp=document.getElementById('lanes-ov-hold');
  if(!on){ if(sp) sp.remove(); return; }
  if(!sp){ sp=document.createElement('div'); sp.id='lanes-ov-hold'; sp.setAttribute('aria-hidden','true');
    sp.style.cssText='position:absolute;left:0;top:0;width:1px;height:1px;visibility:hidden;pointer-events:none;'; c.appendChild(sp); }
  sp.style.width=c.scrollWidth+'px'; sp.style.height=c.scrollHeight+'px';
}
/* the board is moved by its transform there, never scrolled (a scrollbar drag is undone) */
function ovNoScroll(){ var c=cv(); if(!c || c._lnOvS) return; c._lnOvS=1; c.addEventListener('scroll', function(){ if(_ov && (c.scrollLeft || c.scrollTop)){ c.scrollLeft=0; c.scrollTop=0; } }, {passive:true}); }
function ovWheel(e){
  e.preventDefault();
  if(_ovA) return;
  var m=e.deltaMode===1?40:e.deltaMode===2?800:1;
  _ov.tx-=(Math.abs(e.deltaX)>Math.abs(e.deltaY)?e.deltaX:e.deltaY)*m; ovClampX(_ov); ovSet(_ov);
}
function ovPoint(cx, cy){
  var c=cv(), r=c.getBoundingClientRect(), k=zk(c), lx=(cx-r.left)/k, ly=(cy-r.top)/k, P=PAD();
  var wx=(lx-_ov.tx)/_ov.s, wy=(ly-_ov.ty)/_ov.s-P, G=geo(), best=null, bd=Infinity;
  Object.keys(G.x).forEach(function(id){
    if(!live(id)) return;
    var a=anchor(id), h=G.h[id]||120, top=G.y[id]-h/2, bot=G.y[id]+h/2;
    var dyc=wy<top ? top-wy : wy>bot ? wy-bot : 0, dya=Math.abs(wy-a.y);   // on the card, or near its dot on the line
    var d=Math.abs(wx-a.x)+Math.min(dyc,dya)*1.4;
    if(d<bd){ bd=d; best=id; }
  });
  return best;
}
(function(){
  var dn=null;
  document.addEventListener('pointerdown', function(e){
    if(!_ov) return; var c=cv(); if(!c || !c.contains(e.target)) return;
    e.preventDefault(); e.stopPropagation();
    dn={x:e.clientX, y:e.clientY, tx:_ov.tx, moved:false, id:e.pointerId};
  }, true);
  document.addEventListener('pointermove', function(e){
    if(!dn || !_ov || e.pointerId!==dn.id) return;
    var k=zk(cv()), dx=(e.clientX-dn.x)/k;
    if(!dn.moved && Math.abs(e.clientX-dn.x)+Math.abs(e.clientY-dn.y)<5) return;
    dn.moved=true; cv().classList.add('ln-drag'); _ov.tx=dn.tx+dx; ovClampX(_ov); ovSet(_ov);
  }, true);
  document.addEventListener('pointerup', function(e){
    if(!dn || e.pointerId!==dn.id) return;
    var d=dn; dn=null; cv().classList.remove('ln-drag');
    if(!_ov || d.moved) return;
    var id=ovPoint(e.clientX, e.clientY); if(id) ovLeave(id);
  }, true);
  /* nothing under the whole timeline is clicked through to (cards, the engine's own drag) */
  ['mousedown','click','dblclick'].forEach(function(t){ document.addEventListener(t, function(e){ var c=cv(); if(_ov && c && c.contains(e.target)){ e.preventDefault(); e.stopPropagation(); } }, true); });
})();

/* ── after every layout ─────────────────────────────────────────────────── */
function relaid(first){
  var G=geo(); if(!G) return;
  hookWheel(); watchFocus(); buildRail(); ovNoScroll();
  document.querySelectorAll('#world .node[data-ln] .node-card').forEach(function(c){ if(!c.hasAttribute('tabindex')) c.setAttribute('tabindex','0'); });
  if(_cur && !document.getElementById('node-'+_cur)) _cur=null;
  if(_cur){ var n=document.getElementById('node-'+_cur); if(n) n.classList.add('ln-cur'); }
  railMarks();
  if(_ov){ var c=cv(); _ov=ovFit(); ovSet(_ov); c.scrollLeft=0; c.scrollTop=0; ui(current(),0); return; }
  /* a re-layout (a resize, an edit) keeps the view on the event the steps were on */
  if(M.raf){ M.stale=true; ui(current(),0); return; }        // mid-travel: tick carries on from the view as it is
  M.pth=null; _fit=null;
  if(!first && _cur && de.classList.contains('ln-stepped') && on() && !window._focusedNodeId){ glideTo(_cur,{instant:true}); }
  else ui(current(),0);
}
var _lay=window._altoLanes, _laid=0;
if(_lay) window._altoLanes=function(h){
  var r=_lay.apply(this, arguments);
  if(r){ var first=!_laid++; setTimeout(function(){ relaid(first); }, first ? 140 : 0); }   // first: after lanes.py's open-at-the-start
  return r;
};
window.addEventListener('resize', function(){ invalidate(); if(R) ui(current(),0); });
})();
"""
