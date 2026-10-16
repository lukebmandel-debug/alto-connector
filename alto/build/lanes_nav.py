"""Going round a horizontal timeline (brief.mode "lanes"): step event to event.

Luke (2026-10-16): the horizontal timeline should have "a bit more of an
automatic feeling for going around it, as opposed to a free form where you can
scroll wherever you want." So the page is a sequence of STOPS and every way of
moving — the wheel, a trackpad swipe, a touch swipe, ← / →, Space / PageDown —
moves one stop along it, with the camera gliding there on the engine's own curve.

The stops are the main line's events in page order (the order the story tells
them: ACT_SEQS flattened), including the events of a flashback, so stepping
runs down into a flashback's detour and back up out of it as the story does.
An event on a character's own line (off the page) is reached with ↑ / ↓ or a
click; a step from it goes on to its page-order neighbour on the main line.
A timeline with no `present` and no flashbacks yet (a v1 brief) steps through
every event in page order, since its side lines carry the story.

Character focus: clicking a character in the key, or its label on the page,
keeps that line (lanes.py isolate) and stepping then visits only that
character's events: its own and the ones it is on the page for. Click again,
or Esc, for all of them again.

The camera: the event is centred left to right; up and down it keeps the line
the event sits on where the main line sat when the page opened, and moves only
as far as it must to keep the card clear of the bars at the top and the nav
rail at the bottom — so stepping along the main line never bobs, and it follows
a flashback's dip down and back up. Resting is exact: the glide ends on the
offset the canvas can really take (the engine's whole-px scroll axis).

The whole timeline: a toggle on the rail fits the timeline to the window;
clicking a spot there comes back down to the event nearest it. Dragging pans
there (and the wheel), and in step mode only the rail's thumb or a deliberate
drag of the background moves the view freely; the wheel never free-scrolls.

The wheel: a gesture (a run of wheel events with no pause) is one step. A
mouse notch arrives on its own (nothing within NOTCH ms either side) and is a
step each; a trackpad's stream steps once on its first TRAVEL px and then
waits: its inertia tail can never step again. A second flick inside the same
stream (its energy rising again) steps once the glide has landed plus GRACE.
Steps wait their turn like the engine's arrow hops (_hop): up to three queued,
a held key adds one at a time, so a burst never skips an event or piles up.

Phones keep the engine's card-by-card view and its swipe-peek: none of this
runs there. prefers-reduced-motion jumps instead of gliding.

Geometry read from window._altoLanesGeo (lanes.py; agent B's drawing keeps
it): x[id], y[id] (card centre, world px without WORLD_PAD_TOP), h[id], lines
[{id, y, ev}], W, H, and (lanes v2 drawing) at[id] = {x, y, line, flash}: where
the event sits on its line — the main line's dot, on a flashback's lowered past
track, or on a character's track. Without `at` the event's own line's y is
used (no dip for flashbacks).
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
  /* step mode: the camera goes event to event; nothing pans the board by itself */
  html.alto-lanes:not(.mobile):not(.alto-editing) #canvas{ touch-action:none; overscroll-behavior:none; }
  html.alto-lanes:not(.mobile) #world .node[data-ln] .node-card:focus{ outline:none; }
  html.alto-lanes:not(.mobile) #world .node[data-ln] .node-card:focus-visible{ outline:2px solid var(--accent); outline-offset:3px; }
  /* the event the steps are on */
  html.alto-lanes.ln-stepped:not(.mobile) #world .node.ln-cur:not(.focused) .node-card{ box-shadow:0 0 0 2px color-mix(in srgb,var(--accent) 60%,transparent), 0 10px 26px var(--node-rest-shadow); }
  /* the whole timeline, fitted to the window */
  html.alto-lanes #canvas.ln-ov{ cursor:zoom-in; overflow:hidden !important; }
  html.alto-lanes #canvas.ln-ov.ln-drag{ cursor:grabbing; }
  html.alto-lanes #canvas.ln-ov #world, html.alto-lanes #canvas.ln-ovanim #world{ pointer-events:none; transform-origin:0 0; will-change:transform; }
"""

NAV_JS = r"""
(function(){
var L=window._ALTO_LANES; if(!L) return;
var de=document.documentElement;
if(de.classList.contains('mobile')) return;          // phones: the engine's card-by-card view and swipe-peek
var NOTCH=40, GAP=120, TRAVEL=30, GRACE=110, SHORT=70, SPIKE=1.6, RETRAVEL=34, QMAX=3, OV_MIN=0.14;
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
function live(id){ var c=document.querySelector('#node-'+id+' .node-card'); return !!c && !c.classList.contains('dimmed') && !c.classList.contains('ent-dimmed') && !c.classList.contains('rel-dimmed'); }
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
/* the scroll offsets that put this event where it rests */
function camFor(id, B){
  var c=cv(), G=geo(), off=worldOff(c), P=PAD(), a=anchor(id);
  B=B||band(c);
  var cw=c.clientWidth, ch=c.clientHeight;
  var tl=a.x+off.x-cw/2;
  var ay=a.y+P+off.y, h=G.h[id]||120, top=(G.y[id]!=null?G.y[id]:a.y)-h/2+P+off.y, bot=top+h;
  var lo=Math.min(ay,top), hi=Math.max(ay,bot);
  var tt=ay-home(c,B);                          // the line stays where the main line has always been
  if(hi-tt>B.b) tt=hi-B.b;                      // the card would run under the rail: up just enough
  if(lo-tt<B.t) tt=lo-B.t;                      // ... or under the bars (the top of the card wins)
  return {l:Math.max(0,Math.min(tl, c.scrollWidth-cw)), t:Math.max(0,Math.min(tt, c.scrollHeight-ch)), ml:c.scrollWidth-cw, mt:c.scrollHeight-ch};
}

/* rest on whole DEVICE pixels (CSS px x page zoom x dpr), so the cards come to rest crisp;
   Safari's axis then takes the nearest offset it can really scroll to */
function dev(v, max){ var z=zk(cv())*(window.devicePixelRatio||1); if(!(z>0)) return v; var r=Math.round(v*z)/z; if(max!=null && r>max) r=Math.floor(max*z)/z; return Math.max(0,r); }
/* ── where the steps are ─────────────────────────────────────────────────── */
var _cur=null, _land=null, _trust=false, _anim=null, _busy=false, _q=[], _landT=0, _gl=null;
function moved(c){ return !_land || Math.abs(c.scrollLeft-_land[0])>3 || Math.abs(c.scrollTop-_land[1])>3; }
/* the event the view is on: the last one stepped to, unless the view has been moved since;
   then the stop whose resting view is nearest the view as it is (ties: the first in page
   order, so the page as it opens is on the first event) */
function current(){
  var c=cv(); if(!c || !geo()) return null;
  if(_cur && geo().x[_cur]!=null && live(_cur) && (_trust || !moved(c))) return _cur;
  var S=stops().ids, B=band(c), best=null, bd=Infinity;
  for(var i=0;i<S.length;i++){ var t=camFor(S[i],B), d=Math.abs(t.l-c.scrollLeft)+Math.abs(t.t-c.scrollTop); if(d<bd-0.5){ bd=d; best=S[i]; } }
  return best;
}
function stopGlide(){ if(_anim){ cancelAnimationFrame(_anim); _anim=null; } }
function cancelAll(){ stopGlide(); _q.length=0; _busy=false; if(_gl){ var g=_gl; _gl=null; g.cancel(); } }
function setCur(id){
  if(_cur===id) return;
  document.querySelectorAll('#world .node.ln-cur').forEach(function(n){ n.classList.remove('ln-cur'); });
  _cur=id; var n=id && document.getElementById('node-'+id); if(n) n.classList.add('ln-cur');
}
/* glide the camera to an event; done() when it has come to rest */
function glideTo(id, opt, done){
  opt=opt||{};
  var c=cv(); if(!c || !geo() || geo().x[id]==null){ if(done) done(); return; }
  stopGlide();
  var B=band(c), t=camFor(id,B), qx=axis('scrollLeft'), qy=axis('scrollTop');
  var tl=qx.stop(dev(t.l,t.ml)), tt=qy.stop(dev(t.t,t.mt)), l0=qx.at(), t0=qy.at(), d=Math.sqrt((tl-l0)*(tl-l0)+(tt-t0)*(tt-t0));
  setCur(id); _trust=true; ui(id, opt.instant||reduced()||d<0.5 ? 0 : glideMs(d));
  var finish=function(){ _anim=null; _gl=null; _land=[c.scrollLeft, c.scrollTop]; _trust=false; _landT=performance.now(); announce(id); if(done) done(); };
  if(opt.instant || reduced() || d<0.5){ qx.go(tl); qy.go(tt); finish(); return; }
  var ms=glideMs(d), s0=performance.now();
  _gl={cancel:function(){ stopGlide(); _land=[c.scrollLeft, c.scrollTop]; _trust=false; }};
  function fr(now){
    var p=Math.min(1,(now-s0)/ms), k=ease(p);
    qx.go(l0+(tl-l0)*k); qy.go(t0+(tt-t0)*k);
    if(p<1) _anim=requestAnimationFrame(fr); else { qx.go(tl); qy.go(tt); finish(); }
  }
  _anim=requestAnimationFrame(fr);
}
/* one step at a time, each landing before the next starts (the engine's _hop):
   up to three wait their turn, a held key's repeat adds at most one */
function step(dir, src, repeat){
  if(!on() || _ov) return;
  if(_busy){ if(repeat ? !_q.length : _q.length<QMAX) _q.push([dir,src]); return; }
  run(dir, src);
}
function run(dir, src){
  var from=current(), nx=null;
  if(typeof dir==='string') nx=dir;
  else nx=from ? neighbour(from, dir) : stops().ids[dir>0?0:stops().ids.length-1];
  if(!nx){ if(from && from!==_cur) glideTo(from); return; }      // the end: rest on the last one
  de.classList.add('ln-stepped');
  _busy=true;
  glideTo(nx, {}, function(){ _busy=false; var q=_q.shift(); if(q) run(q[0], q[1]); });
  if(src==='key') focusCard(nx);
}
window._altoLanesStep=function(d){ step(d,'api'); };       // for tests and the rail
window._altoLanesCurrent=function(){ return current(); };
function focusCard(id){
  var c=document.querySelector('#node-'+id+' .node-card'); if(!c) return;
  if(!c.hasAttribute('tabindex')) c.setAttribute('tabindex','0');
  try{ c.focus({preventScroll:true}); }catch(e){}
}

/* ── the stops in the engine's own hops (an enlarged card's ← / →) ─────────── */
var _navPrev=window._altoLanesNav;
window._altoLanesNav=function(id, dir){
  if(!geo() || de.classList.contains('mobile')) return null;
  if(dir==='e'||dir==='w'){ var r=neighbour(id, dir==='e'?1:-1); if(r){ setCur(r); _trust=true; } return r; }
  var n=_navPrev ? _navPrev(id, dir) : null;
  if(n){ setCur(n); _trust=true; }
  return n;
};

/* ── keys ──────────────────────────────────────────────────────────────── */
document.addEventListener('keydown', function(e){
  if(!on() || e.metaKey || e.ctrlKey || e.altKey) return;
  var k=e.key;
  if(k==='Escape' && _ov){ e.preventDefault(); e.stopPropagation(); ovLeave(current()); return; }
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
    e.preventDefault(); stopGlide(); if(window.enterFocus) window.enterFocus(cur); return;
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

/* ── the wheel ─────────────────────────────────────────────────────────── */
var W={last:-1e9, cand:null, stream:false, fired:false, ax:0, ay:0, bt:[], bm:[], valley:1e9, peak:0, armed:false, sx:0, sy:0, lastFire:-1e9};
function dirOf(x,y){ var v=Math.abs(x)>Math.abs(y)?x:y; return v>0?1:v<0?-1:0; }
function wfire(x,y,ts){ var d=dirOf(x,y); if(!d) return; W.fired=true; W.lastFire=ts; W.ax=W.ay=0; W.armed=false; W.valley=W.peak=0; step(d,'wheel'); }
function onWheel(e){
  if(!on() || e.ctrlKey || e.metaKey) return;
  if(window._focusedNodeId) return;                         // an enlarged card: the engine's swipe hops (along the stops)
  if(_ov){ ovWheel(e); return; }
  if(busyElsewhere()) return;
  e.preventDefault();                                       // step mode: the wheel never free-scrolls
  var m=e.deltaMode===1?40:e.deltaMode===2?800:1, dx=e.deltaX*m, dy=e.deltaY*m, ts=e.timeStamp;
  if(e.shiftKey && !dx){ dx=dy; dy=0; }
  var gap=ts-W.last; W.last=ts;
  if(gap>GAP){                                              // a new gesture
    W.stream=false; W.fired=false; W.ax=W.ay=0; W.bt.length=0; W.bm.length=0; W.valley=1e9; W.peak=0; W.armed=false;
  }
  if(gap>=NOTCH && !W.stream){
    /* maybe a notch: one only if nothing follows within NOTCH ms */
    var me=W.cand={x:dx, y:dy, ts:ts};
    setTimeout(function(){ if(W.cand===me && W.last===me.ts){ W.cand=null; if(Math.abs(me.x)+Math.abs(me.y)>=3) step(dirOf(me.x,me.y),'wheel'); W.fired=true; } }, NOTCH+5);
    return;
  }
  if(W.cand){ dx+=W.cand.x; dy+=W.cand.y; W.cand=null; }  // it was the start of a stream
  W.stream=true;
  var mag=Math.abs(dx)+Math.abs(dy);
  W.bt.push(ts); W.bm.push(mag); while(W.bt.length && W.bt[0]<ts-SHORT){ W.bt.shift(); W.bm.shift(); }
  var s=0; for(var i=0;i<W.bm.length;i++) s+=W.bm[i]; var cur=W.bm.length?s/W.bm.length:0;
  W.ax+=dx; W.ay+=dy;
  if(cur>W.peak){ W.peak=cur; W.valley=cur; } else if(cur<W.valley) W.valley=cur;
  if(!W.fired){ if(Math.abs(W.ax)+Math.abs(W.ay)>=TRAVEL) wfire(W.ax,W.ay,ts); return; }
  /* after its step a stream only steps again for a second flick (its energy rising
     again), and not before the glide has landed and GRACE has passed: inertia never does */
  if(!W.armed){ if(ts-W.lastFire>150 && cur>=SPIKE*Math.max(W.valley,1)){ W.armed=true; W.sx=W.ax; W.sy=W.ay; } return; }
  if(_busy || performance.now()-_landT<GRACE) return;
  var rx=W.ax-W.sx, ry=W.ay-W.sy;
  if(Math.abs(rx)+Math.abs(ry)>=RETRAVEL) wfire(rx,ry,ts);
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

/* ── touch (a desktop with a touch screen): a swipe is a step ───────────── */
var T=null;
document.addEventListener('pointerdown', function(e){
  if(e.pointerType!=='touch' || !on() || _ov || window._focusedNodeId) return;
  var c=cv(); if(!c || !c.contains(e.target)) return;
  T={x:e.clientX, y:e.clientY, t:e.timeStamp, id:e.pointerId};
}, true);
document.addEventListener('pointerup', function(e){
  if(!T || e.pointerId!==T.id) return;
  var dx=e.clientX-T.x, dy=e.clientY-T.y; T=null;
  if(Math.abs(dx)>=40 && Math.abs(dx)>1.3*Math.abs(dy)) step(dx<0?1:-1,'touch');
  else if(Math.abs(dy)>=40 && Math.abs(dy)>1.3*Math.abs(dx)) step(dy<0?1:-1,'touch');
}, true);
document.addEventListener('pointercancel', function(){ T=null; }, true);

/* a hand on the board stops a glide; a drag of the background is the explicit free pan */
document.addEventListener('mousedown', function(e){
  var c=cv(); if(!c || !c.contains(e.target) || _ov) return;
  if(_anim) cancelAll();
  if(!(e.target.closest && e.target.closest('.node-card,.lanes-tag'))){ _trust=false; _land=null; }   // the view is about to be moved by hand
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
    var c=charOf(); ui(current(),0);
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
    if(c.classList.contains('focus-mode')){ if(_anim || _busy) cancelAll(); if(window._focusedNodeId){ _lastFocus=window._focusedNodeId; setCur(_lastFocus); _trust=true; ui(_lastFocus,0); } }
    else if(_lastFocus){ setCur(_cur||_lastFocus); _trust=true; _lastFocus=null; }
  }).observe(c,{attributes:true, attributeFilter:['class']});
}

/* ── the rail ──────────────────────────────────────────────────────────── */
var R=null;
function svgI(d){ return '<svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+d+'</svg>'; }
function buildRail(){
  if(R || de.classList.contains('mobile')) return;
  var n=document.createElement('div'); n.id='lanes-nav'; n.setAttribute('role','navigation'); n.setAttribute('aria-label','Step through the timeline');
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
  R.ov.addEventListener('click', function(){ if(_ov) ovLeave(current()); else ovEnter(); });
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
/* the rail says where the steps are; the thumb travels with the glide (same clock, same curve) */
function ui(id, ms){
  if(!R) return;
  var S=stops(), N=S.ids.length, i=S.ids.indexOf(id), pos=i;
  if(i<0 && id!=null){ var oi=S.at[id]; pos=-1; for(var k=0;k<N;k++) if(S.at[S.ids[k]]<oi) pos=k; }
  R.n.textContent=i>=0 ? String(i+1) : (pos>=0 ? (pos+1)+'+' : '–'); R.N.textContent=String(N);
  var fb=id && flashOf(id), ev=id && L.ev[id], ln=ev && ev.l!=='main' ? lineDef(ev.l) : null, c=charOf(), tag='';
  if(c){ tag=(lineDef(c)||{}).label||''; R.tag.innerHTML=''; R.tag.textContent=tag+' only'; var x=document.createElement('button'); x.type='button'; x.textContent='✕'; x.title='All events (Esc)'; x.setAttribute('aria-label','Show all events');
         x.addEventListener('click', function(e){ e.stopPropagation(); if(window._altoLanesLock) window._altoLanesLock(null); ui(current(),0); }); R.tag.appendChild(x); }
  else { tag=fb ? fb.label : (ln ? ln.label+' · off the page' : ''); R.tag.textContent=tag; }
  R.tag.style.color=c ? (lineDef(c)||{}).color||'' : (ln ? ln.color : '');
  R.prev.disabled=!(N && (i>0 || (i<0 && pos>=0))); R.next.disabled=!(N && (i<N-1 || (i<0 && pos<N-1)));
  var f=railFrac(Math.max(0,i>=0?i:pos+.5), N), w=R.rail.clientWidth;
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
  function look(f){
    var S=sc.S, N=S.length; if(!N) return;
    var fi=f*(N-1), a=Math.floor(fi), b=Math.min(N-1,a+1), u=fi-a;
    var A=camFor(S[a],sc.B), Bc=camFor(S[b],sc.B), c=cv();
    c.scrollLeft=Math.round(A.l+(Bc.l-A.l)*u); c.scrollTop=Math.round(A.t+(Bc.t-A.t)*u);
    R.thumb.style.transition='none'; R.thumb.style.transform='translateX('+(f*R.rail.clientWidth).toFixed(2)+'px)';
    sc.f=f;
  }
  R.rail.addEventListener('pointerdown', function(e){
    if(!on() || e.button>0) return; e.preventDefault();
    if(_ov) ovLeave(null, true);
    cancelAll(); sc={S:stops().ids, B:band(cv()), x:e.clientX, moved:false, f:at(e), id:e.pointerId};
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
    var f=sc.moved ? sc.f : at(e), S=sc.S, i=Math.round(f*(S.length-1)); sc=null; R.el.classList.remove('scrub');
    if(S[i]) step(S[i],'rail');
  }
  R.rail.addEventListener('pointerup', end); R.rail.addEventListener('pointercancel', function(){ sc=null; R.el.classList.remove('scrub'); });
}

/* ── the whole timeline ─────────────────────────────────────────────────── */
var _ov=null, _ovA=null;
function ovSet(o){
  var w=document.getElementById('world'), c=cv(), off=worldOff(c);
  w.style.transform='translate('+(o.tx-off.x)+'px,'+(o.ty-off.y)+'px) scale('+o.s+')';
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
  var c=cv(), off=worldOff(c), from={s:1, tx:off.x-c.scrollLeft, ty:off.y-c.scrollTop}, to=ovFit();
  _ov=to;
  ovSet(from); c.scrollLeft=0; c.scrollTop=0; c.classList.add('ln-ov');
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
  ovSet(from);
  var fin=function(){ w.style.transform=''; qx.go(tl); qy.go(tt); setCur(id); _land=[c.scrollLeft,c.scrollTop]; _trust=false; ui(id,0); announce(id); };
  if(instant){ fin(); return; }
  de.classList.add('ln-stepped');
  ovAnim(from, {s:1, tx:off.x-tl, ty:off.y-tt}, fin);
}
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
  hookWheel(); watchFocus(); buildRail();
  document.querySelectorAll('#world .node[data-ln] .node-card').forEach(function(c){ if(!c.hasAttribute('tabindex')) c.setAttribute('tabindex','0'); });
  if(_cur && !document.getElementById('node-'+_cur)) _cur=null;
  if(_cur){ var n=document.getElementById('node-'+_cur); if(n) n.classList.add('ln-cur'); }
  railMarks();
  if(_ov){ var c=cv(); _ov=ovFit(); ovSet(_ov); c.scrollLeft=0; c.scrollTop=0; ui(current(),0); return; }
  /* a re-layout (a resize, an edit) keeps the view on the event the steps were on */
  if(!first && _cur && de.classList.contains('ln-stepped') && on() && !window._focusedNodeId && !_anim){ _home=null; glideTo(_cur,{instant:true}); }
  else ui(current(),0);
}
var _lay=window._altoLanes, _laid=0;
if(_lay) window._altoLanes=function(h){
  var r=_lay.apply(this, arguments);
  if(r){ var first=!_laid++; setTimeout(function(){ relaid(first); }, first ? 140 : 0); }   // first: after lanes.py's open-at-the-start
  return r;
};
window.addEventListener('resize', function(){ if(R) ui(current(),0); });
})();
"""
