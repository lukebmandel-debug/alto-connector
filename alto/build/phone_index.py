"""The phone whole view's unit index (chunk 6, C2; Luke 2026-11-11: "I agree C2, but just to be clear, the progress bar is
for study plan, right?"; Art sheet ORG/notes-art/sheet-1111c).

The whole view of a timeline or an outline opens on one tile a unit, not on the board fitted to 402 pt (5 px text, audit W4):

  * at rest (C1) a tile is the unit's real branch shape: the board's rows 22 pt apart, its columns kept in order, a lead card
    (one that branches, the unit's first, the card you are on) a titled pill at 11 px, every other card a dot; the unit's own
    links are drawn, a link to the unit beside it runs through the gap, any other is a named chip. A tap on a titled card
    opens that card; a tap on a chip opens the unit it names with that card flagged;
  * a tap anywhere else on a tile opens it in place (C2): the same drawing at reading size, every card titled (12.5 px, whole
    words) and a 44 pt target, about 280 ms (a plain cross-fade under Reduce Motion); the other units fold to 44 pt bars. A
    tap on the open header, or a pinch out, folds it back;
  * a pinch out on the index at rest shows the real board fitted to the screen, as before; a pinch out on the fitted board
    comes back to the index.

Progress is the study plan's and nothing else's (Luke's question above; ORG/DECISIONS.md 6-C): "N of M done", the rule under a
unit's name and a dot's state (done / to do / in today's plan) are read from window._altoStudyPlan.states(), the same list that
draws the desktop's Done tags. A timeline with no plan has plain dots, no rule and no count of done.

All of it rides in the hosted phone script (phone.py ASSET), none in the page. `?ix=0` shows the board as before."""
from __future__ import annotations

CSS = r"""
/* ── the unit index (phone_index.py) ── */
html.ph-ix #canvas:not(#_){visibility:hidden !important;pointer-events:none !important;}
#ph-ix{display:none;position:absolute;left:0;right:0;bottom:0;top:98px;z-index:5;overflow-x:hidden;overflow-y:auto;-webkit-overflow-scrolling:touch;overscroll-behavior:contain;touch-action:pan-y;box-sizing:border-box;
  padding:8px calc(16px + max(var(--sh-right,0px),env(safe-area-inset-right,0px))) calc(84px + env(safe-area-inset-bottom,0px)) calc(16px + max(var(--sh-left,0px),env(safe-area-inset-left,0px)));
  background:transparent;color:var(--text);font-family:Georgia,'Times New Roman',serif;-webkit-text-size-adjust:100%;scrollbar-width:none;
  --ix-bg:color-mix(in srgb,var(--bg,#fff) 58%,transparent);--ix-bd:color-mix(in srgb,var(--text,#223) 16%,transparent);--ix-card:var(--bg,#fff);--ix-line:color-mix(in srgb,var(--text,#223) 46%,transparent);
  --ix-ok:var(--sp-ok,#1f6b3a);--ix-now:var(--sp-acc,#c2410c);--ix-late:var(--sp-late,#b42318);--ix-r:14px;--ix-cr:8px;}
#ph-ix::-webkit-scrollbar{display:none;}
html.ph-ix #ph-ix{display:block;}
/* the tiles run on through the runway under Safari's foot bar, as the board does (never a cut edge with the bare ground under it) */
html.rw #ph-ix{bottom:-140px;padding-bottom:calc(224px + env(safe-area-inset-bottom,0px));}
html.ph-ix.detail-open #ph-ix{visibility:hidden;pointer-events:none;}
#ph-ix *{box-sizing:border-box;}
#ph-ix button{font:inherit;color:inherit;-webkit-appearance:none;appearance:none;margin:0;-webkit-tap-highlight-color:transparent;}
#ph-ix .ix-list{position:relative;display:flex;flex-direction:column;gap:8px;}
#ph-ix .ix-x{position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;overflow:visible;z-index:3;}
#ph-ix .ix-tile{position:relative;min-width:0;background:var(--ix-bg);border:1px solid var(--ix-bd);border-radius:var(--ix-r);}
#ph-ix .ix-tile.open{border-color:var(--uc,var(--ix-bd));box-shadow:0 0 0 1px var(--uc,transparent);}
#ph-ix .ix-hd{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;column-gap:8px;width:100%;min-height:44px;padding:6px 14px 6px;background:none;border:0;text-align:left;cursor:pointer;}
#ph-ix .ix-num{font-style:italic;font-size:12px;color:var(--muted);min-width:14px;}
#ph-ix .ix-name{font-size:17px;line-height:1.2;letter-spacing:.01em;overflow-wrap:normal;word-break:normal;-webkit-hyphens:manual;hyphens:manual;}
#ph-ix .ix-name.long{font-size:15px;}
#ph-ix .ix-cnt{font:500 11px/1.2 system-ui,-apple-system,sans-serif;color:var(--muted);white-space:nowrap;}
#ph-ix .ix-rule{grid-column:1 / -1;display:block;height:3px;margin-top:5px;border-radius:2px;background:var(--ix-bd);overflow:hidden;}
#ph-ix .ix-rule i{display:block;height:100%;background:var(--ix-ok);border-radius:2px;}
#ph-ix .ix-flag{display:inline-block;padding:2px 6px 3px;border-radius:4px;background:var(--text);color:var(--bg,#fff);font:700 11px/1 system-ui,-apple-system,sans-serif;font-style:normal;white-space:nowrap;letter-spacing:.01em;}
#ph-ix .ix-hd .ix-flag{display:none;margin-left:8px;vertical-align:2px;}
#ph-ix .ix-tile.fold .ix-hd .ix-flag{display:inline-block;}
#ph-ix .ix-tile.fold .ix-body{display:none;}
#ph-ix .ix-body{position:relative;}
#ph-ix .ix-tile.open .ix-mini{display:none;}
#ph-ix .ix-tile:not(.open) .ix-open{display:none;}
/* at rest: the branch shape */
#ph-ix .ix-map{position:relative;margin:4px 20px 12px;}
#ph-ix .ix-map svg,#ph-ix .ix-grid svg{position:absolute;left:0;top:0;width:100%;height:100%;overflow:visible;pointer-events:none;}
#ph-ix svg path{fill:none;stroke:var(--ix-line);stroke-width:1.25;}
#ph-ix svg path.rel{stroke-width:1.5;}
#ph-ix .ix-pt,#ph-ix .ix-pill{position:absolute;transform:translate(-50%,-50%);display:inline-flex;align-items:center;}
#ph-ix .ix-pill{gap:5px;height:19px;padding:0 8px 0 5px;background:var(--ix-card);border:1px solid var(--ix-bd);border-radius:var(--ix-cr);font-size:11px;line-height:1;white-space:nowrap;cursor:pointer;z-index:1;}
#ph-ix .ix-pill::after{content:'';position:absolute;left:-4px;right:-4px;top:-2px;bottom:-2px;}
#ph-ix .ix-pill.here,#ph-ix .ix-card.here{border:2px solid var(--text);}
#ph-ix .ix-map>.ix-flag{position:absolute;transform:translate(-50%,0);z-index:2;}
#ph-ix .ix-dot{flex:none;display:block;width:9px;height:9px;border-radius:50%;background:var(--ix-line);}
#ph-ix .ix-dot.is-done{background:var(--ix-ok);}
#ph-ix .ix-dot.is-todo{background:var(--bg,#fff);border:1.5px solid var(--text);}
#ph-ix .ix-dot.is-today{background:var(--bg,#fff);border:2px solid var(--ix-now);box-shadow:inset 0 0 0 1.5px var(--bg,#fff),inset 0 0 0 5px var(--ix-now);}
#ph-ix .ix-dot.is-late{background:var(--bg,#fff);border:2px solid var(--ix-late);box-shadow:inset 0 0 0 1.5px var(--bg,#fff),inset 0 0 0 5px var(--ix-late);}
#ph-ix .dim{opacity:.35;}
#ph-ix .ix-chips{display:flex;flex-wrap:wrap;gap:6px;margin:0 14px 10px;}
#ph-ix .ix-chips:empty{display:none;}
#ph-ix .ix-chip{display:inline-flex;align-items:center;min-height:24px;padding:3px 8px;background:var(--ix-card);border:1px dashed var(--rc,var(--ix-line));border-radius:var(--ix-cr);font-size:11px;line-height:1.25;text-align:left;white-space:normal;overflow-wrap:normal;word-break:normal;cursor:pointer;position:relative;}
#ph-ix .ix-chip::after{content:'';position:absolute;left:0;right:0;top:-3px;bottom:-3px;}
#ph-ix .ix-open .ix-chip{min-height:44px;padding:4px 10px;font-size:12px;}
#ph-ix .ix-open .ix-chip::after{display:none;}
/* open in place: the same drawing at reading size */
#ph-ix .ix-open{padding:6px 12px 2px;transform-origin:50% 0;}
#ph-ix .ix-open.pan{overflow-x:auto;touch-action:pan-x pan-y;scrollbar-width:none;}
#ph-ix .ix-grid{position:relative;display:grid;gap:14px 8px;align-items:center;margin-bottom:12px;}
#ph-ix .ix-card{position:relative;z-index:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;min-height:44px;min-width:44px;padding:5px 7px;background:var(--ix-card);border:1px solid var(--ix-bd);border-radius:var(--ix-cr);
  font-size:12.5px;line-height:1.22;text-align:center;overflow-wrap:normal;word-break:normal;-webkit-hyphens:manual;hyphens:manual;cursor:pointer;}
#ph-ix .ix-card .ix-dot{position:absolute;left:-4px;top:-4px;}
#ph-ix .ix-open.tight .ix-grid{gap:12px 5px;}
#ph-ix .ix-open.tight .ix-card{font-size:11px;padding:4px 4px;}
#ph-ix .ix-key{display:flex;flex-wrap:wrap;justify-content:center;gap:4px 14px;margin:12px 0 0;font:500 11px/1.3 system-ui,-apple-system,sans-serif;color:var(--muted);}
#ph-ix .ix-key span{display:inline-flex;align-items:center;gap:5px;}
/* held sideways: two across; an open unit takes the left two thirds, the others are bars down the right third */
@media (orientation:landscape){
  #ph-ix .ix-list{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:8px 12px;align-items:start;}
  #ph-ix .ix-list.has-open{grid-template-columns:minmax(0,2fr) minmax(0,1fr);grid-auto-flow:row dense;}
  #ph-ix .ix-list.has-open .ix-tile{grid-column:2;}
  #ph-ix .ix-list.has-open .ix-tile.open{grid-column:1;grid-row:1 / span 40;}
  #ph-ix{padding-top:6px;}
}
/* Retro: square corners, squares for dots, capitals */
html.alto-retro #ph-ix{--ix-r:2px;--ix-cr:0px;--ix-bg:color-mix(in srgb,var(--card-glass-bg,#05070b) 82%,transparent);--ix-bd:var(--border);--ix-card:var(--card-glass-bg,#05070b);font-family:'Avenir Next',Futura,'Century Gothic','Helvetica Neue',system-ui,sans-serif;}
html.alto-retro #ph-ix .ix-dot{border-radius:0;}
html.alto-retro #ph-ix :is(.ix-name,.ix-pill,.ix-card,.ix-chip),html.alto-holo #ph-ix :is(.ix-name,.ix-pill,.ix-card,.ix-chip){text-transform:uppercase;letter-spacing:.05em;}
html.alto-retro #ph-ix .ix-name,html.alto-holo #ph-ix .ix-name{font-size:15px;font-weight:600;}
html.alto-retro #ph-ix .ix-open .ix-card,html.alto-holo #ph-ix .ix-open .ix-card{font-size:11.5px;}
html.alto-retro #ph-ix .ix-open.tight .ix-card,html.alto-holo #ph-ix .ix-open.tight .ix-card{font-size:11px;letter-spacing:.02em;}
/* Holo: the paper's own panels */
html.alto-holo #ph-ix{--ix-r:0px;--ix-cr:0px;--ix-bg:color-mix(in srgb,var(--card-glass-bg,#fcfeff) 86%,transparent);--ix-bd:var(--border);--ix-card:var(--card-glass-bg,#fcfeff);}
"""

JS = r"""(function(){
if(window._altoPhoneIx) return;
var de=document.documentElement, P=window._altoPhone; if(!P) return;
var ix=null, list=null, U=[], BY={}, PL=null, openI=-1, shown=false, here=null, busy=0, HK='alto-phone-here:'+location.pathname, SVG='http://www.w3.org/2000/svg', MS=280;
try{ here=sessionStorage.getItem(HK)||null; }catch(e){}
function can(){ return P.on() && P.fmt()==='tl' && !/[?&]ix=0/.test(location.search); }
function reduced(){ return window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches; }
function land(){ return window.matchMedia && matchMedia('(orientation:landscape)').matches; }
function el(t, c, x){ var e=document.createElement(t); if(c) e.className=c; if(x!=null) e.textContent=x; return e; }
function sv(t, a){ var e=document.createElementNS(SVG, t); for(var k in a) e.setAttribute(k, a[k]); return e; }
function nice(m){
  var s=String(m.label||'').trim(), t=m.numeral ? s.replace(/^\s*(unit|part|chapter|week|module|topic|section|act|phase)\s+[\w-]+\s*[—–:.-]\s*/i, '') : s; if(!t) t=s;
  if(t===t.toUpperCase() && /[A-Z]/.test(t)) t=t.toLowerCase().replace(/(^|[\s(—–-])([a-z])/g, function(_, a, b){ return a+b.toUpperCase(); });
  return t;
}
/* the study plan's own states, by card: every item ticked = done; one due today (or late) = in today's plan; else to do */
function plan(){
  var S=window._altoStudyPlan, L=null, o={}; try{ L=S && S.states(); }catch(e){} if(!L || !L.length) return null;
  L.forEach(function(x){ var p=o[x.it.node]||(o[x.it.node]={n:0, d:0, t:0, l:0}); p.n++; if(x.st==='done') p.d++; else if(x.st==='today') p.t++; else if(x.st==='late') p.l++; });
  return o;
}
function state(n){ var p=PL && PL[n.id]; return !p ? '' : p.d>=p.n ? 'done' : p.t ? 'today' : p.l ? 'late' : 'todo'; }
function dimmed(n){ try{ return !!(window._altoFilterOn && window._altoFilterOn() && window._altoShown && !window._altoShown(n.id)); }catch(e){ return false; } }
function relCol(l){ var c=null; try{ c=typeof COLOR_MAP!=='undefined' && COLOR_MAP[l.k]; }catch(e){} return c||l.a.c||'currentColor'; }

/* ── the units as the board lays them out: rows by y, columns in the board's left-to-right order ── */
function model(){
  var M=typeof PHASE_META!=='undefined' ? PHASE_META : [], N=typeof NODES!=='undefined' ? NODES : [], C=typeof CONNECTIONS!=='undefined' ? CONNECTIONS : [];
  BY={}; U=M.map(function(m, i){ return {i:i, m:m, nodes:[], links:[], x:[]}; });
  N.forEach(function(n){ var u=U[n.act]; if(!u) return; var e=document.getElementById('node-'+n.id);
    var o={id:n.id, t:String(n.title||n.id), x:+n.displayX||(e ? parseFloat(e.style.left) : 0)||0, y:+n.y||(e ? parseFloat(e.style.top) : 0)||0, c:n.color, u:u, out:0};
    BY[n.id]=o; u.nodes.push(o); });
  U=U.filter(function(u){ return u.nodes.length; }); U.forEach(function(u, k){ u.k=k; });
  C.forEach(function(c){ var a=BY[c[0]], b=BY[c[1]]; if(!a || !b || a===b) return; var l={a:a, b:b, k:c[2]};
    if(a.u===b.u){ a.u.links.push(l); if(l.k==='spine') a.out++; } else { a.u.x.push(l); b.u.x.push(l); } });
  U.forEach(function(u){
    var rows=[]; u.nodes.slice().sort(function(a, b){ return a.y-b.y||a.x-b.x; }).forEach(function(n){ var r=rows[rows.length-1]; if(!r || n.y-r.y>14){ r={y:n.y, n:[]}; rows.push(r); } r.n.push(n); });
    var K=1, x0=1e9, x1=-1e9; rows.forEach(function(r){ K=Math.max(K, r.n.length); r.n.forEach(function(n){ x0=Math.min(x0, n.x); x1=Math.max(x1, n.x); }); });
    rows.forEach(function(r, ri){ r.n.sort(function(a, b){ return a.x-b.x; }); var k=r.n.length, prev=-1;
      r.n.forEach(function(n, i){ var f=x1>x0 ? (n.x-x0)/(x1-x0) : .5, s=Math.round(f*(K-1)); n.w=0;
        if(k===1 && K>1 && K%2===0 && Math.abs(f-.5)<.12){ s=K/2-1; n.w=1; }
        s=Math.max(s, prev+1); s=Math.min(s, K-1-(k-1-i)); prev=s; n.r=ri; n.s=s; }); });
    u.K=K; u.R=rows.length; u.first=rows[0].n[0];
  });
  return U.length>1;
}
function fx(u, n){ return u.K>1 ? (n.s+(n.w ? .5 : 0))/(u.K-1) : .5; }
function lead(u, n){ return n.out>=2 || n===u.first || n.id===here; }

/* ── a tile ── */
function head(u){
  var h=el('button', 'ix-hd'); h.type='button'; h.setAttribute('aria-expanded', openI===u.k ? 'true' : 'false');
  h.appendChild(el('span', 'ix-num', u.m.numeral||String(u.k+1)));
  var t=nice(u.m), nm=el('span', 'ix-name'+(t.length>34 ? ' long' : ''), t); h.appendChild(nm);
  if(here && BY[here] && BY[here].u===u) nm.appendChild(el('span', 'ix-flag', 'You are here'));
  var pn=0, pd=0; if(PL) u.nodes.forEach(function(n){ var p=PL[n.id]; if(p){ pn++; if(p.d>=p.n) pd++; } });
  h.appendChild(el('span', 'ix-cnt', pn ? pd+' of '+pn+' done' : u.nodes.length+(u.nodes.length===1 ? ' card' : ' cards')));
  if(pn){ var r=el('span', 'ix-rule'), b=el('i'); b.style.width=Math.round(100*pd/pn)+'%'; r.appendChild(b); h.appendChild(r); }
  return h;
}
function dot(n){ var d=el('i', 'ix-dot'), s=state(n); if(s) d.classList.add('is-'+s); return d; }
function chip(l, out, full){
  var o=out ? l.b : l.a, c=el('button', 'ix-chip'); c.type='button'; c.dataset.u=o.u.k; c.dataset.j=o.id; c.style.setProperty('--rc', relCol(l));
  var num=o.u.m.numeral||String(o.u.k+1), me=out ? l.a : l.b;
  c.textContent=(full ? me.t+' ' : '')+(out ? '→ ' : '← ')+num+' '+o.t; return c;
}
function beside(u, v){ var d=v.k-u.k; return Math.abs(d)===1 && (!land() || Math.floor(u.k/2)===Math.floor(v.k/2)); }
function mini(u){
  var m=el('div', 'ix-mini'), map=el('div', 'ix-map'), hr=-1; u.nodes.forEach(function(n){ if(n.id===here) hr=n.r; });
  u.Y=function(r){ return 11+r*22+(hr>=0 && r>hr ? 18 : 0); };
  map.style.height=(u.R*22+(hr>=0 ? 18 : 0))+'px'; u.map=map; u.svg=sv('svg', {}); map.appendChild(u.svg);
  u.nodes.forEach(function(n){
    var L=lead(u, n), b=el(L ? 'button' : 'span', L ? 'ix-pill' : 'ix-pt'); if(L){ b.type='button'; b.dataset.n=n.id; }
    b.appendChild(dot(n)); if(L) b.appendChild(el('span', '', n.t)); if(dimmed(n)) b.classList.add('dim');
    b.style.left=(100*fx(u, n))+'%'; b.style.top=u.Y(n.r)+'px'; n.me=b; map.appendChild(b);
    if(n.id===here){ b.classList.add('here'); var f=el('span', 'ix-flag', 'You are here'); f.style.left=b.style.left; f.style.top=(u.Y(n.r)+12)+'px'; n.fl=f; map.appendChild(f); }
  });
  m.appendChild(map);
  var cs=el('div', 'ix-chips'); u.x.forEach(function(l){ if(l.a.u===u && !beside(u, l.b.u)) cs.appendChild(chip(l, true, true)); }); m.appendChild(cs);
  return m;
}
/* a pill stays inside the tile and clear of its row's other cards; one that cannot is a dot again (no title is cut or shrunk) */
function tidy(u){
  var map=u.map, W=map.clientWidth, mr=map.getBoundingClientRect(), kept=[]; if(!W) return;
  function demote(n){ var b=n.me; b.classList.remove('ix-pill'); b.classList.add('ix-pt'); b.removeAttribute('data-n'); if(b.lastChild && b.lastChild!==b.firstChild) b.removeChild(b.lastChild); n.pill=null; }
  var ps=u.nodes.filter(function(n){ return n.me.classList.contains('ix-pill'); }).sort(function(a, b){ return (b.id===here)-(a.id===here)||(a===u.first ? -1 : b===u.first ? 1 : 0)||b.out-a.out; });
  ps.forEach(function(n){
    var b=n.me, r=b.getBoundingClientRect(), w=r.width, cx=fx(u, n)*W, lo=-14+w/2, hi=W+14-w/2;
    if(w>W+28){ demote(n); return; }
    var x=Math.max(lo, Math.min(hi, cx)), a=x-w/2-4, z=x+w/2+4, bad=false;
    kept.forEach(function(k){ if(k.r===n.r && a<k.z && z>k.a) bad=true; });
    u.nodes.forEach(function(o){ if(o!==n && o.r===n.r && !o.me.classList.contains('ix-pill')){ var ox=fx(u, o)*W; if(ox>a-6 && ox<z+6) bad=true; } });
    if(bad && n.id!==here){ demote(n); return; }
    b.style.left=x+'px'; n.pill={a:a, z:z}; n.px=x; kept.push({n:n, r:n.r, a:a, z:z});
    if(n.fl){ var fw=n.fl.getBoundingClientRect().width; n.fl.style.left=Math.max(-14+fw/2, Math.min(W+14-fw/2, x))+'px'; }
  });
  u.nodes.forEach(function(o){ if(o.me.classList.contains('ix-pill')) return; var ox=fx(u, o)*W;
    kept.forEach(function(k){ if(k.n!==o && k.r===o.r && k.n.id!==here && k.n.pill && ox>k.a-2 && ox<k.z+2) demote(k.n); }); });
  u.nodes.forEach(function(o){ if(!o.pill && o.me.classList.contains('ix-pt')) o.me.style.left=(100*fx(u, o))+'%'; });
  wires(u, W);
}
function wires(u, W){
  var s=u.svg; while(s.firstChild) s.removeChild(s.firstChild);
  u.links.forEach(function(l){
    var a=l.a, b=l.b; if(a.r>b.r){ var t=a; a=b; b=t; }
    var ax=fx(u, a)*W, ay=u.Y(a.r), bx=fx(u, b)*W, by=u.Y(b.r), sp=l.k==='spine', o=sp ? 0 : 3;
    var d=a.r===b.r ? 'M'+ax+' '+(ay+o)+'H'+bx : 'M'+(ax+o)+' '+ay+'V'+(by-11+o)+'H'+(bx+o)+'V'+by;
    var p=sv('path', {d:d}); if(!sp){ p.setAttribute('class', 'rel'); p.style.stroke=relCol(l); } s.appendChild(p);
  });
}
/* a link to the unit beside this one, through the gap (only while every tile is at rest) */
function cross(){
  var x=list.querySelector('.ix-x'); if(x) x.remove(); if(openI>=0 || !shown) return;
  x=sv('svg', {'class':'ix-x'}); var lr=list.getBoundingClientRect(), seen=[], n=0;
  function at(o){ var r=o.me.querySelector('.ix-dot').getBoundingClientRect(); return [r.left+r.width/2-lr.left, r.top+r.height/2-lr.top]; }
  U.forEach(function(u){ u.x.forEach(function(l){
    if(seen.indexOf(l)>=0 || !beside(l.a.u, l.b.u)) return; seen.push(l);
    var a=l.a, b=l.b; if(a.u.k>b.u.k){ var t=a; a=b; b=t; }
    var p=at(a), q=at(b), ar=a.u.tile.getBoundingClientRect(), br=b.u.tile.getBoundingClientRect(), side=br.left>ar.right-2, k=3*(n++);
    var lane=side ? (ar.right+br.left)/2-lr.left : ar.right-lr.left-8-k, ya=p[1]+11, yb=q[1]-11;
    var path=sv('path', {'class':'rel', d:'M'+p[0]+' '+p[1]+'V'+ya+'H'+lane+'V'+yb+'H'+q[0]+'V'+q[1]}); path.style.stroke=relCol(l); x.appendChild(path);
  }); });
  if(x.firstChild) list.appendChild(x);
}
function openLayer(u){
  var o=el('div', 'ix-open'), g=el('div', 'ix-grid'); g.style.gridTemplateColumns='repeat('+u.K+',minmax(min-content,1fr))';
  u.gsvg=sv('svg', {}); g.appendChild(u.gsvg);
  u.nodes.forEach(function(n){
    var c=el('button', 'ix-card'); c.type='button'; c.dataset.n=n.id; c.style.gridRow=String(n.r+1); c.style.gridColumn=(n.s+1)+(n.w ? ' / span 2' : '');
    c.appendChild(dot(n)); c.appendChild(el('span', 'ix-ct', n.t)); if(dimmed(n)) c.classList.add('dim');
    if(n.id===here){ c.classList.add('here'); c.appendChild(el('em', 'ix-flag', 'You are here')); }
    n.card=c; g.appendChild(c); });
  o.appendChild(g);
  var cs=el('div', 'ix-chips'); u.x.forEach(function(l){ cs.appendChild(chip(l, l.a.u===u, true)); }); o.appendChild(cs);
  u.grid=g; return o;
}
function gridWires(u){
  var g=u.grid, o=g.parentNode, s=u.gsvg; if(!g.clientWidth) return;
  o.classList.remove('tight', 'pan'); if(g.scrollWidth>g.clientWidth+1) o.classList.add('tight'); if(g.scrollWidth>g.clientWidth+1) o.classList.add('pan');
  while(s.firstChild) s.removeChild(s.firstChild);
  var gr=g.getBoundingClientRect();
  function box(n){ var r=n.card.getBoundingClientRect(); return {l:r.left-gr.left, r:r.right-gr.left, t:r.top-gr.top, b:r.bottom-gr.top, x:(r.left+r.right)/2-gr.left, y:(r.top+r.bottom)/2-gr.top}; }
  u.links.forEach(function(l){
    var a=l.a, b=l.b; if(a.r>b.r){ var t=a; a=b; b=t; }
    var A=box(a), B=box(b), sp=l.k==='spine', k=sp ? 0 : 4, d;
    if(a.r===b.r) d=A.x<B.x ? 'M'+A.r+' '+(A.y+k)+'H'+B.l : 'M'+A.l+' '+(A.y+k)+'H'+B.r;
    else d='M'+(A.x+k)+' '+A.b+'V'+(B.t-7+k/2)+'H'+(B.x+k)+'V'+B.t;
    var p=sv('path', {d:d}); if(!sp){ p.setAttribute('class', 'rel'); p.style.stroke=relCol(l); } s.appendChild(p);
  });
}

/* ── the whole index, drawn from the model (a redraw keeps what is open) ── */
function render(){
  if(!ix) return; PL=plan(); var top=ix.scrollTop;
  ix.textContent=''; list=el('div', 'ix-list'); if(openI>=U.length) openI=-1; if(openI>=0) list.classList.add('has-open');
  U.forEach(function(u){
    var t=el('section', 'ix-tile'); t.dataset.u=u.k; t.style.setProperty('--uc', u.m.colorRaw||u.m.cssVar||''); u.tile=t;
    if(openI>=0) t.classList.add(openI===u.k ? 'open' : 'fold');
    t.appendChild(head(u)); var b=el('div', 'ix-body'); b.appendChild(mini(u)); u.body=b; u.open=null; t.appendChild(b); list.appendChild(t);
  });
  ix.appendChild(list);
  if(PL){ var k=el('div', 'ix-key'); [['done', 'done'], ['todo', 'to do'], ['today', "in today's plan"]].forEach(function(p){ var s=el('span'), d=el('i', 'ix-dot is-'+p[0]); s.appendChild(d); s.appendChild(document.createTextNode(p[1])); k.appendChild(s); }); ix.appendChild(k); }
  if(openI>=0){ var u=U[openI]; u.open=openLayer(u); u.body.appendChild(u.open); }
  measure(); ix.scrollTop=top;
}
function measure(){
  if(!ix || !shown) return; place();
  U.forEach(function(u){ if(openI<0) tidy(u); else if(openI===u.k) gridWires(u); });
  cross();
}
function place(){ var r=document.getElementById('summary-wrap'), a=ix.offsetParent, t=r ? r.getBoundingClientRect().top+2 : 52; if(a) t-=a.getBoundingClientRect().top; ix.style.top=Math.max(44, Math.round(t))+'px'; }

/* ── open in place, and fold ── */
function anim(e, frames, done){
  if(!e.animate){ if(done) done(); return; }
  var a=e.animate(frames, {duration:MS, easing:'cubic-bezier(.2,.7,.2,1)'}); busy++; a.onfinish=a.oncancel=function(){ a.onfinish=a.oncancel=null; busy--; if(done) done(); };
}
function scrollTo(y){
  var y0=ix.scrollTop, t0=performance.now(); if(reduced() || Math.abs(y-y0)<2){ ix.scrollTop=y; return; }
  (function fr(t){ var k=Math.min(1, (t-t0)/MS), e=1-Math.pow(1-k, 3); ix.scrollTop=y0+(y-y0)*e; if(k<1) requestAnimationFrame(fr); })(t0);
}
function open(k, quiet){
  var u=U[k]; if(!u || !ix) return; if(openI===k){ return; }
  var was=openI, rm=reduced()||quiet, x=list.querySelector('.ix-x'); if(x) x.remove();
  var h0=u.body.offsetHeight, hs=U.map(function(v){ return v.body.offsetHeight; });
  if(was>=0 && U[was].open){ U[was].open.remove(); U[was].open=null; }
  openI=k; list.classList.add('has-open');
  U.forEach(function(v){ v.tile.classList.toggle('open', v===u); v.tile.classList.toggle('fold', v!==u); v.tile.firstChild.setAttribute('aria-expanded', v===u ? 'true' : 'false'); });
  u.open=openLayer(u); u.body.appendChild(u.open); gridWires(u);
  var h1=u.body.offsetHeight;
  if(!quiet) anim(u.open, rm ? [{opacity:0}, {opacity:1}] : [{opacity:0, transform:'scaleY('+Math.max(.3, Math.min(1, h0/(h1||1))).toFixed(3)+')'}, {opacity:1, transform:'none'}]);
  if(!rm){
    u.body.style.overflow='hidden'; anim(u.body, [{height:h0+'px'}, {height:h1+'px'}], function(){ u.body.style.overflow=''; });
    U.forEach(function(v, i){ if(v!==u && hs[i]>0 && !land()){ var b=v.body; v.tile.classList.remove('fold'); b.style.overflow='hidden';
      anim(b, [{height:hs[i]+'px', opacity:1}, {height:'0px', opacity:0}], function(){ b.style.overflow=''; if(openI>=0 && openI!==v.k) v.tile.classList.add('fold'); }); } });
  }
  var above=land() ? 0 : k*52, vh=ix.clientHeight; scrollTo(Math.max(0, Math.round(above-vh*.4)));
}
function fold(quiet){
  if(openI<0 || !ix) return; var u=U[openI], rm=reduced()||quiet, h1=u.body.offsetHeight;
  openI=-1; list.classList.remove('has-open');
  U.forEach(function(v){ v.tile.classList.remove('open', 'fold'); v.tile.firstChild.setAttribute('aria-expanded', 'false'); });
  if(u.open){ u.open.remove(); u.open=null; }
  U.forEach(tidy);
  var h0=u.body.offsetHeight;
  if(!quiet) anim(u.body.firstChild, [{opacity:0}, {opacity:1}]);
  if(!rm){
    u.body.style.overflow='hidden'; anim(u.body, [{height:h1+'px'}, {height:h0+'px'}], function(){ u.body.style.overflow=''; });
    if(!land()) U.forEach(function(v){ if(v!==u){ var b=v.body, h=b.offsetHeight; b.style.overflow='hidden'; anim(b, [{height:'0px', opacity:0}, {height:h+'px', opacity:1}], function(){ b.style.overflow=''; }); } });
  }
  var after=function(){ if(openI<0){ cross(); var r=u.tile.getBoundingClientRect(), c=ix.getBoundingClientRect(); if(r.top<c.top || r.top>c.bottom-60) ix.scrollTop+=r.top-c.top-8; } };
  if(rm) after(); else setTimeout(after, MS+40);
}
function mark(id){ here=id||null; try{ if(here) sessionStorage.setItem(HK, here); else sessionStorage.removeItem(HK); }catch(e){} }
/* a card: its own page, the index kept under it */
function card(id){ mark(id); try{ showDetail('node', id); }catch(e){} setTimeout(render, 400); }
/* a chip, a search hit, MAP's list: that card's unit opened, the card flagged and in view */
function jump(id){
  var n=BY[id]; if(!n) return false; mark(id); var k=n.u.k, same=openI===k; openI=k; render();
  if(!same){ var u=U[k]; anim(u.open, [{opacity:0}, {opacity:1}]); }
  setTimeout(function(){ var c=BY[id] && BY[id].card; if(c && c.scrollIntoView) c.scrollIntoView({block:'center', behavior:reduced() ? 'auto' : 'smooth'}); }, 30);
  return true;
}
function show(){
  if(!can()) return false; if(!ix){ if(!model()) return false; build(); } else model();
  shown=true; de.classList.add('ph-ix'); render(); return true;
}
function hide(){ if(!shown) return; shown=false; de.classList.remove('ph-ix'); if(P.fit) P.fit(); }
function build(){
  var c=document.getElementById('canvas'); ix=el('div'); ix.id='ph-ix'; ix.setAttribute('role', 'navigation'); ix.setAttribute('aria-label', 'Units');
  c.parentNode.insertBefore(ix, c.nextSibling);
  ix.addEventListener('click', function(e){
    var t=e.target, tl=t.closest && t.closest('.ix-tile'); if(!tl) return; var k=+tl.dataset.u, j=t.closest('[data-j]'), n=t.closest('[data-n]');
    if(j){ jump(j.dataset.j); return; }
    if(n){ card(n.dataset.n); return; }
    if(tl.classList.contains('open')){ if(t.closest('.ix-hd')) fold(); return; }
    open(k);
  });
  /* two fingers: together = fold the open unit, or (at rest) the real board; apart over a tile = open it */
  var G=null;
  function d2(e){ var a=e.touches[0], b=e.touches[1]; return Math.hypot(a.clientX-b.clientX, a.clientY-b.clientY)||1; }
  ix.addEventListener('touchstart', function(e){ if(e.touches.length===2){ e.preventDefault(); var tl=e.target.closest && e.target.closest('.ix-tile'); G={d0:d2(e), s:1, k:tl ? +tl.dataset.u : -1}; } }, {passive:false});
  ix.addEventListener('touchmove', function(e){ if(G && e.touches.length>=2){ e.preventDefault(); G.s=d2(e)/G.d0; } }, {passive:false});
  function end(e){ if(!G || (e.touches && e.touches.length>=2)) return; var g=G; G=null;
    if(g.s<.8){ if(openI>=0) fold(); else hide(); } else if(g.s>1.25 && g.k>=0 && openI!==g.k) open(g.k); }
  ix.addEventListener('touchend', end); ix.addEventListener('touchcancel', function(){ G=null; });
}
/* search, MAP's list and the page's own "go to this card" land on the board (enterFocus); with the index up they open the unit here */
function hook(){
  var f=window.enterFocus; if(typeof f==='function' && !f._ix){ window.enterFocus=function(id){ if(shown && !de.classList.contains('detail-open') && jump(id)) return; return f.apply(this, arguments); }; window.enterFocus._ix=1; }
  var s=window.showDetail; if(typeof s==='function' && !s._ix){ window.showDetail=function(type, id){ if(type==='node' && shown) mark(id); return s.apply(this, arguments); }; window.showDetail._ix=1; }
  var b=window.showTimeline; if(typeof b==='function' && !b._ix){ window.showTimeline=function(){ var r=b.apply(this, arguments); if(shown) setTimeout(render, 60); return r; }; window.showTimeline._ix=1; }
}
var rT=0, sig='';
function soon(){ clearTimeout(rT); rT=setTimeout(function(){ if(shown && !busy){ model(); render(); } else if(shown) soon(); }, 160); }
function start(){ if(!can()) return; hook(); if(!ix) show(); else soon(); }
window.addEventListener('load', function(){ start(); setTimeout(start, 1000); if(document.fonts && document.fonts.ready) document.fonts.ready.then(soon); });
if(document.readyState==='complete') start();
window.addEventListener('resize', soon); window.addEventListener('orientationchange', soon);
window.addEventListener('alto-study-sync', soon); window.addEventListener('storage', soon);
document.addEventListener('visibilitychange', function(){ if(!document.hidden) soon(); });
new MutationObserver(function(){ var c=de.classList, s=[c.contains('alto-retro'), c.contains('alto-holo'), c.contains('dark'), c.contains('light'), c.contains('sp-open'), c.contains('detail-open')].join(); if(s!==sig){ sig=s; soon(); } }).observe(de, {attributes:true, attributeFilter:['class']});
document.addEventListener('click', function(e){ if(shown && ix && !ix.contains(e.target)) soon(); }, true);
window._altoPhoneIx={show:show, hide:hide, open:open, fold:fold, jump:jump, render:render, shown:function(){ return shown; }, state:function(){ return {shown:shown, open:openI, here:here, units:U.length, plan:!!PL}; }};
})();"""
