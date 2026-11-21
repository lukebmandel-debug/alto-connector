"""Harbour ship spacing and labels (1.9.262): DISPLAY ONLY, hosted with the rest of the fleet script (palace_fleet_asset.py), never in the page.

Real museum ships lie side by side on one pier (USS Olympia and USS Becuna are 11 m apart), and drawn at the map's scale they sat on top of one another, the submarine hidden
and the two names stacked. Two rules, both drawn from the page's own data (the real positions stay in the page; b.x0/b.y0 keep them):
  spaceBoats(M)       ships whose hulls (as drawn) come nearer than a gap fan out one after another along the river (their own heading), kept in the water of the river
                      they were in. It works in map units, so it holds at every zoom (a map zoom scales every hull alike).
  layoutLabels(items, tw)   each name sits beside its own ship, in the first free spot of a ring of them (right, left, above and below the hull, then farther out with a
                      thin leader line to the ship); never on another name or on any hull. Names keep their screen size, so it is laid out again when a zoom settles.
The pure parts (no DOM) are unit-tested in node (tests/test_palace_ship_space.py)."""
from __future__ import annotations

FLEET_S = r"""
/* ── harbour ship spacing and names (palace_fleet_space.py): display only ── */
function toyW(wk, L){ return wk==='cv'?Math.max(58, L/3.5):wk==='sub'?Math.max(15, L/8.5):wk==='dd'?Math.max(30, L/6):Math.max(46, L/4.2); }
/* the size a boat is drawn at (length, width) in map units */
function boatDims(b){ var wk=b.k||WK[boatKind(b.n, b.len, b.wid)]||''; if(wk){ var L=Math.max(b.len, MINL[wk]); return [L, toyW(wk, L)]; } return [b.len, b.wid]; }
function riverNear(river, x, y){ var best=null; (river||[]).forEach(function(r){ var p=r.p||[];
  for(var k=0;k+3<p.length;k+=2){ var ax=p[k], ay=p[k+1], dx=p[k+2]-ax, dy=p[k+3]-ay, L2=dx*dx+dy*dy||1e-9, t=Math.max(0, Math.min(1, ((x-ax)*dx+(y-ay)*dy)/L2)), qx=ax+t*dx, qy=ay+t*dy, d=Math.hypot(qx-x, qy-y);
    if(!best || d<best.d) best={d:d, qx:qx, qy:qy, hw:(+r.w||100)/2}; } }); return best; }
function spaceBoats(M){
  var bs=(M.boats||[]).filter(function(b){ return !b._sp; }); if(!bs.length) return;
  bs.forEach(function(b){ b._sp=1; b.x0=b.x; b.y0=b.y; var d=boatDims(b); b._L=d[0]; b._W=d[1]; var n=riverNear(M.river, b.x, b.y); b._in=!!(n && n.d<=n.hw); });
  function water(b){ if(!b._in) return; var n=riverNear(M.river, b.x, b.y); if(!n) return; var lim=Math.max(0, n.hw-b._W/2-3);
    if(n.d>lim){ var f=lim/(n.d||1); b.x=n.qx+(b.x-n.qx)*f; b.y=n.qy+(b.y-n.qy)*f; } }
  for(var it=0; it<120; it++){ var moved=false;
    for(var i=0;i<bs.length;i++) for(var j=i+1;j<bs.length;j++){ var A=bs[i], B=bs[j], r=A.a*Math.PI/180, ux=Math.cos(r), uy=Math.sin(r), dx=B.x-A.x, dy=B.y-A.y,
        al=dx*ux+dy*uy, cr=-dx*uy+dy*ux, g=Math.max(10, .12*Math.max(A._L, B._L)), need=(A._L+B._L)/2+g;
      if(Math.abs(al)<need-.01 && Math.abs(cr)<(A._W+B._W)/2+g){ var s=al>0?1:al<0?-1:1, p=(need-Math.abs(al))/2+.5;
        A.x-=ux*s*p; A.y-=uy*s*p; B.x+=ux*s*p; B.y+=uy*s*p; water(A); water(B); moved=true; } }
    if(!moved) break; }
  bs.forEach(function(b){ b.x=Math.round(b.x*10)/10; b.y=Math.round(b.y*10)/10; });
}
/* a hull as a turned box: centre, half length, half width, angle; its corners */
function hullBox(b){ var a=b.a*Math.PI/180, c=Math.cos(a), s=Math.sin(a), hl=b._L/2, hw=b._W/2;
  return {x:b.x, y:b.y, c:c, s:s, hl:hl, hw:hw, up:b._up||0, pts:[[-hl,-hw],[hl,-hw],[hl,hw],[-hl,hw]].map(function(p){ return [b.x+c*p[0]-s*p[1], b.y+s*p[0]+c*p[1]]; })}; }
/* a turned box touches an upright rectangle [l,t,r,b] (separating axes) */
function boxHitRect(H, R){ var rp=[[R[0],R[1]],[R[2],R[1]],[R[2],R[3]],[R[0],R[3]]], ax=[[1,0],[0,1],[H.c,H.s],[-H.s,H.c]];
  for(var i=0;i<4;i++){ var u=ax[i], a0=1e9, a1=-1e9, b0=1e9, b1=-1e9; H.pts.forEach(function(p){ var d=p[0]*u[0]+p[1]*u[1]; a0=Math.min(a0,d); a1=Math.max(a1,d); });
    rp.forEach(function(p){ var d=p[0]*u[0]+p[1]*u[1]; b0=Math.min(b0,d); b1=Math.max(b1,d); }); if(a1<b0 || b1<a0) return false; }
  return true; }
function rectHit(A, B){ return !(A[2]<=B[0] || B[2]<=A[0] || A[3]<=B[1] || B[3]<=A[1]); }
/* avoid: [l,t,r,b] rects in map units (the page's bars and buttons plus 20 screen px): a name keeps off them, or hides.
   items: [{b: boat (x, y, a, _L, _W, _up), w: the name's width in screen px}]; tw: map units per screen px. Sets it.x, it.y, it.an ('start' | 'end' | 'middle'), it.lead (a leader line to the ship), it.box [l,t,r,b] */
function layoutLabels(items, tw, avoid){
  var H=items.map(function(it){ return hullBox(it.b); }), pad=3*tw, hgt=15*tw, placed=[];
  function onChrome(box){ for(var k=0;k<(avoid||[]).length;k++) if(rectHit(box, avoid[k])) return true; return false; }
  function bad(box, self, chrome){ if(chrome && onChrome(box)) return true; for(var k=0;k<placed.length;k++) if(rectHit(box, placed[k])) return true;
    for(var m=0;m<H.length;m++){ if(boxHitRect(H[m], box)) return true;
      if(H[m].up){ var u=[H[m].x-H[m].hw-pad, H[m].y-H[m].up, H[m].x+H[m].hw+pad, H[m].y]; if(rectHit(box, u)) return true; } }
    return false; }
  items.forEach(function(it, i){ var b=it.b, h=H[i], w=it.w*tw+2*pad, a=Math.abs(b.a*Math.PI/180), ex=Math.abs(h.c)*h.hl+Math.abs(h.s)*h.hw, ey=Math.abs(h.s)*h.hl+Math.abs(h.c)*h.hw, g=3*tw, C=[];
    function add(x, y, an, lead){ var l=an==='start'?x:an==='end'?x-w:x-w/2; C.push({x:x, y:y, an:an, lead:lead, box:[l-pad*0, y-hgt/2, l+w, y+hgt/2]}); }
    var ys=[0, -.5, .5, -1, 1].map(function(k){ return k*Math.max(hgt, ey*.6); });
    ys.forEach(function(dy){ add(b.x+ex+g, b.y+dy, 'start', false); add(b.x-ex-g, b.y+dy, 'end', false); });
    add(b.x, b.y-ey-(h.up||0)-g-hgt/2, 'middle', false); add(b.x, b.y+ey+g+hgt/2, 'middle', false);
    for(var d=1; d<=5; d++){ var o=d*hgt*1.5; [0,-1,1,-2,2].forEach(function(k){ add(b.x+ex+g+o, b.y+k*hgt*1.2*d/1.5, 'start', true); add(b.x-ex-g-o, b.y+k*hgt*1.2*d/1.5, 'end', true); }); }
    var pick=null, hide=false; for(var c=0;c<C.length;c++) if(!bad(C[c].box, i, true)){ pick=C[c]; break; }
    if(!pick){ for(var c2=0;c2<C.length;c2++) if(!bad(C[c2].box, i, false)){ pick=C[c2]; break; } hide=!!pick && onChrome(pick.box); }     /* no spot clear of the bars: it waits, hidden, until the map moves */
    if(!pick){ pick=C[C.length-1]; hide=onChrome(pick.box); }
    it.hide=hide; it.x=pick.x; it.y=pick.y; it.an=pick.an; it.lead=pick.lead; it.box=pick.box; placed.push(pick.box); });
  return items;
}
/* the names of one drawn set of boats: placed now, and again whenever a zoom settles (the page sets --tw on the svg) */
var CHROME='#title-bar,#nav,#account-btn,#pal-ctl,#search-btn,#info-btn,#mode-toggle,#alto-edit-pill,#key-toggle,#tab-rail';
function chromeRects(lg){ var m=null; try{ m=lg.getScreenCTM(); }catch(e){} if(!m || !m.a || !m.d) return [];
  return [].map.call(document.querySelectorAll(CHROME), function(e){ var r=e.getBoundingClientRect(), cs=getComputedStyle(e); if(!(r.width>0 && r.height>0) || cs.display==='none' || cs.visibility==='hidden') return null;
    return [(r.left-20-m.e)/m.a, (r.top-20-m.f)/m.d, (r.right+20-m.e)/m.a, (r.bottom+20-m.f)/m.d]; }).filter(Boolean); }
function fitLabels(bs, tw, lg){
  var NS='http://www.w3.org/2000/svg', items=bs.map(function(q){ var L=q.L, w=0; try{ w=L.t.getComputedTextLength(); }catch(e){} if(!(w>0)) w=(q.b.n||'').length*6.8; return {b:q.b, L:L, w:w}; });
  layoutLabels(items, tw, lg?chromeRects(lg):[]);
  items.forEach(function(it){ var L=it.L; L.o.style.display=it.hide?'none':''; L.o.setAttribute('transform', 'translate('+it.x.toFixed(1)+' '+it.y.toFixed(1)+')'); L.t.setAttribute('text-anchor', it.an); L.t.setAttribute('y', 4);
    var ln=L.ld; if(it.lead){ if(!ln){ ln=L.ld=document.createElementNS(NS, 'line'); ln.setAttribute('class', 'pl-boat-ld'); L.o.insertBefore(ln, L.o.firstChild); }
      ln.setAttribute('x1', 0); ln.setAttribute('y1', 0); ln.setAttribute('x2', (it.b.x-it.x).toFixed(1)); ln.setAttribute('y2', (it.b.y-it.y).toFixed(1)); ln.setAttribute('stroke-width', (1.2*tw).toFixed(2)); ln.style.display=''; }
    else if(ln) ln.style.display='none'; });
}
function labelsFit(lg, M){
  var svg=lg.ownerSVGElement, bs=(M.boats||[]).filter(function(b){ return b._lb; }).map(function(b){ return {b:b, L:b._lb}; }); if(!svg || !bs.length) return; function run(){ fitLabels(bs, parseFloat(svg.style.getPropertyValue('--tw'))||1, lg); }
  function soon(){ clearTimeout(svg._flT); svg._flT=setTimeout(run, 120); }
  run(); try{ new MutationObserver(soon).observe(svg, {attributes:true, attributeFilter:['style']}); }catch(e){}
  var cv=document.getElementById('canvas'); if(cv) cv.addEventListener('scroll', soon, {passive:true}); window.addEventListener('resize', soon);
}
"""
