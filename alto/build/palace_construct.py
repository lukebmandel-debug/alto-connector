"""1.9.95: the battleship's victim is rebuilt as a REAL construction site, not a tree growing.

A struck building (a node's glass block, or a landmark tower) is rebuilt over 20 seconds:
  0 - 0.7 s    it pancakes: its storeys drop one after another, top first, into a heap of rubble and a drifting dust cloud
  2.2 - 3.6 s  the rubble is cleared; hoarding goes up round a concrete foundation pad with its rebar grid
  2.7 - 5.9 s  a tower crane is put up beside the lot (mast section by section, then the jib), a site hoist beside it
  4.0 - 10.5 s steel frame, a storey at a time: columns, a floor slab, diagonal bracing; the crane's hook ferries beams up
  6.2 - 12.6 s scaffolding climbs the two walls you can see
  8.8 - 16.8 s the building's own glass is hung storey by storey from the bottom up (the hook now carries glass panels)
  16.7 - 18.4 s the roof (a tower: its crown) is lifted by the crane and lowered into place, last
  16.6 - 19.6 s scaffold comes down from the top, the frame inside is covered, the crane and hoist are taken away
  20 s         the layer is removed and the real building is shown again: the last frame is the same picture, so nothing pops.

The building is never stretched: every storey is a copy of the building's own art, clipped to its band (a node building: the exact
parallelogram of each wall's storey, so the floor lines meet; a landmark: a horizontal band), and faded in. Everything is drawn from
SVG attributes (no CSS px in transforms, no <mask>, no filters), updated by one requestAnimationFrame loop from the elapsed time, so
`_palCon.freeze(ms)` can show any instant exactly (QA).
"""
from __future__ import annotations

CONSTRUCT_CSS = r"""
  /* the construction layer's props never take a click (the building's own clones do, as the glass always did) */
  .nb-pr,.nb-pr *{pointer-events:none !important;}
"""

CONSTRUCT_JS = r"""
/* ── the construction sequence (palace_construct.py) ── */
window._palCon=(function(){
var NS='http://www.w3.org/2000/svg', FORCE=null, runs=[], raf=0;
var T={coll:1200, rubIn:[500,1300], rubOut:[2500,3700], found:[2200,3600], mast:[2700,5200], jib:[5200,5900], frame:[4000,10500], hoist:[4600,11000],
  scaf:[6200,12600], clad:[8800,16800], hook0:5900, hook1:16000, roof:[16700,18400], scafOut:[16600,19200], frameOut:[17500,19200], propsOut:[18300,19600], xfade:[18600,19700], end:20000};
function E(tag, at, par){ var e=document.createElementNS(NS, tag); if(at) for(var k in at) e.setAttribute(k, at[k]); if(par) par.appendChild(e); return e; }
function cl(x){ return x<0?0:(x>1?1:x); }
function sm(x){ x=cl(x); return x*x*(3-2*x); }
function lerp(a, b, u){ return a+(b-a)*u; }
function rng(seed){ var s=(seed>>>0)||1; return function(){ s=(Math.imul(s,1664525)+1013904223)>>>0; return s/4294967296; }; }
function hash(str){ var h=2166136261; str=String(str||'x'); for(var i=0;i<str.length;i++){ h^=str.charCodeAt(i); h=Math.imul(h,16777619); } return h>>>0; }
function PT(pts){ return pts.map(function(q){ return q[0].toFixed(1)+','+q[1].toFixed(1); }).join(' '); }
function setO(el, o){ var k=o<=.004?'n':o.toFixed(2); if(el._k===k) return; el._k=k; if(k==='n') el.setAttribute('display','none'); else { el.removeAttribute('display'); el.setAttribute('opacity', k==='1.00'?'1':k); } }
function setT(el, s){ if(el._t!==s){ el._t=s; el.setAttribute('transform', s); } }
function setA(el, name, v){ var k='_a'+name, s=(typeof v==='number')?v.toFixed(1):v; if(el[k]!==s){ el[k]=s; el.setAttribute(name, s); } }
var STEEL='#4b566b', STEELHI='#a3b4cf', CONC='#c4c7d0', CONCD='#8b90a0', YEL='#f2b51b', YELD='#8a6a05', TAN='#b99a64';

/* the heart: build the layer for spec S, return {upd(t), kill()} */
function build(S){
  var C=S.C, H=S.H, N=S.N, hs=H/N, par=S.par, bands=S.mode==='bands', K=bands?N-1:N;
  var layer=E('g', {'class':'nb-con'}, par), defs=E('defs', null, layer), cid=0, uid='nbc'+(++cid)+'_'+((Math.random()*1e6)|0);
  var cx=0, cy=0; C.forEach(function(q){ cx+=q[0]/4; cy+=q[1]/4; });
  var minX=1e9, maxX=-1e9, yb=-1e9, yt=1e9; C.forEach(function(q){ minX=Math.min(minX,q[0]); maxX=Math.max(maxX,q[0]); yb=Math.max(yb,q[1]); yt=Math.min(yt,q[1]); });
  var fw=maxX-minX, fd=yb-yt, cs=Math.max(.7, Math.min(1.7, Math.max(fw, fd)/42)), rnd=rng(hash(S.id)), items=[];
  var side=(hash(S.id)%2)?1:-1, dir=-side;                                  /* the crane stands on one side (side), its jib reaches over the lot (dir) */
  function lvlAt(t){ var f=cl((t-T.frame[0])/(T.frame[1]-T.frame[0]-450)), fc=Math.floor(f*N+(t>=T.frame[0]?1:0)); fc=Math.min(N, Math.max(0, fc));
    var q=cl((t-T.clad[0])/(T.clad[1]-T.clad[0])), cc=Math.floor(q*K)+(t>=T.clad[0]?1:0); return Math.min(N, Math.max(fc, cc)); }
  var faces=[]; for(var i=0;i<4;i++){ var A=C[i], B=C[(i+1)%4]; if((B[0]-A[0])<0) faces.push({A:A, B:B}); }        /* the walls you can see, as nbDraw picks them */
  function inset(p, d){ var vx=cx-p[0], vy=cy-p[1], l=Math.hypot(vx,vy)||1; return [p[0]+vx/l*d, p[1]+vy/l*d]; }
  function grow(pts, d){ var mx=0,my=0; pts.forEach(function(q){ mx+=q[0]/pts.length; my+=q[1]/pts.length; }); return pts.map(function(q){ var vx=q[0]-mx, vy=q[1]-my, l=Math.hypot(vx,vy)||1; return [q[0]+vx/l*d, q[1]+vy/l*d]; }); }
  function up(p, t){ return [p[0], p[1]-t]; }

  /* ground: shadow (prism) + foundation + rubble */
  var gShadow=E('g', null, layer), gFound=E('g', null, layer), gFrame=E('g', null, layer), gBuilt=E('g', null, layer), gClad=E('g', null, gBuilt), gCladL=E('g', null, gBuilt), gFull=E('g', null, layer), gScaf=E('g', {'class':'nb-pr'}, layer), gProps=E('g', {'class':'nb-pr'}, layer);
  var shadowC=null; if(S.shadow){ shadowC=S.shadow.cloneNode(true); gShadow.appendChild(shadowC); }
  items.push(function(t){ if(shadowC){ var q=cl((t-T.clad[0])/(T.clad[1]-T.clad[0])); setO(shadowC, t<T.coll?(1-sm(t/T.coll)):(t<T.clad[0]?0:sm(q*1.4))); } });

  /* foundation: hoarding round the lot, a concrete pad with a rebar grid */
  var gFo=E('g', {'class':'nb-pr'}, gFound);
  var hoard=E('polygon', {points:PT(grow(C, 5*cs)), fill:'none', stroke:YEL, 'stroke-width':1.5, 'stroke-dasharray':'4 3', 'vector-effect':'non-scaling-stroke', 'stroke-linejoin':'round'}, gFo);
  var pad=E('polygon', {points:PT(grow(C, 1.2)), fill:'#7d8190', 'fill-opacity':.92, stroke:'#4d5160', 'stroke-width':1, 'vector-effect':'non-scaling-stroke'}, gFo);
  var rb=''; for(var gi=1;gi<6;gi++){ var u=gi/6; rb+='M'+(C[0][0]+(C[1][0]-C[0][0])*u).toFixed(1)+' '+(C[0][1]+(C[1][1]-C[0][1])*u).toFixed(1)+'L'+(C[3][0]+(C[2][0]-C[3][0])*u).toFixed(1)+' '+(C[3][1]+(C[2][1]-C[3][1])*u).toFixed(1);
    rb+='M'+(C[0][0]+(C[3][0]-C[0][0])*u).toFixed(1)+' '+(C[0][1]+(C[3][1]-C[0][1])*u).toFixed(1)+'L'+(C[1][0]+(C[2][0]-C[1][0])*u).toFixed(1)+' '+(C[1][1]+(C[2][1]-C[1][1])*u).toFixed(1); }
  E('path', {d:rb, fill:'none', stroke:'#c0693a', 'stroke-width':.8, 'stroke-opacity':.8, 'vector-effect':'non-scaling-stroke'}, gFo);
  items.push(function(t){ var a=sm((t-T.found[0])/(T.found[1]-T.found[0])); setO(gFo, a*(1-sm((t-T.propsOut[0])/(T.propsOut[1]-T.propsOut[0])))); });

  /* rubble: a heap of broken concrete, slabs and bent rebar over the footprint, biggest in the middle */
  var gRub=E('g', null, gFound), pcs=[], PAL=['#6c6f79','#8a8c96','#a4a6ae','#575a64','#8e857a','#7a7e8a'], nP=Math.max(16, Math.min(70, Math.round(fw*fd/110))), rs=Math.max(cs, Math.sqrt(fw*fd)/50);
  for(var p=0;p<nP;p++){ var u=rnd(), v=rnd(), px=C[0][0]+(C[1][0]-C[0][0])*u+(C[3][0]-C[0][0])*v, py=C[0][1]+(C[1][1]-C[0][1])*u+(C[3][1]-C[0][1])*v;
    var mid=1-Math.min(1, Math.hypot(u-.5, v-.5)*2), lift=mid*Math.min(10*rs, H*.2)*(.5+rnd()*.7), r=(1.6+rnd()*3.6)*rs*(.7+mid*.6), a0=rnd()*6.28, nv=4+(rnd()>.6?1:0), pts=[];
    for(var j=0;j<nv;j++){ var aj=a0+j*6.283/nv, rr=r*(.6+rnd()*.6); pts.push([px+Math.cos(aj)*rr*1.25, py-lift+Math.sin(aj)*rr*.8]); }
    pcs.push({y:py-lift, pts:pts, c:PAL[(rnd()*PAL.length)|0]}); }
  pcs.sort(function(a,b){ return a.y-b.y; });
  pcs.forEach(function(q){ E('polygon', {points:PT(q.pts), fill:q.c, stroke:'#3b3d46', 'stroke-width':.7, 'vector-effect':'non-scaling-stroke', 'stroke-linejoin':'round'}, gRub); });
  for(var sl=0;sl<3;sl++){ var u2=.2+rnd()*.6, v2=.3+rnd()*.5, sx=C[0][0]+(C[1][0]-C[0][0])*u2+(C[3][0]-C[0][0])*v2, sy=C[0][1]+(C[1][1]-C[0][1])*u2+(C[3][1]-C[0][1])*v2-Math.min(8*cs, H*.14), L=(7+rnd()*7)*rs, tl=(rnd()-.5)*.6;
    E('polygon', {points:PT([[sx-L/2,sy+tl*L/2],[sx+L/2,sy-tl*L/2],[sx+L/2,sy-tl*L/2+2.2*cs],[sx-L/2,sy+tl*L/2+2.2*cs]]), fill:'#b3b5bd', stroke:'#4a4c55', 'stroke-width':.8, 'vector-effect':'non-scaling-stroke'}, gRub); }
  var bars=''; for(var bI=0;bI<9;bI++){ var u3=rnd(), v3=rnd(), bx=C[0][0]+(C[1][0]-C[0][0])*u3+(C[3][0]-C[0][0])*v3, by=C[0][1]+(C[1][1]-C[0][1])*u3+(C[3][1]-C[0][1])*v3-Math.min(6*cs,H*.1), bl=(4+rnd()*6)*cs, ba=-1.2-rnd()*.8;
    bars+='M'+bx.toFixed(1)+' '+by.toFixed(1)+'L'+(bx+Math.cos(ba)*bl).toFixed(1)+' '+(by+Math.sin(ba)*bl).toFixed(1); }
  E('path', {d:bars, fill:'none', stroke:'#b0552b', 'stroke-width':1.1, 'stroke-linecap':'round', 'vector-effect':'non-scaling-stroke'}, gRub);
  items.push(function(t){ setO(gRub, sm((t-T.rubIn[0])/(T.rubIn[1]-T.rubIn[0]))*(1-sm((t-T.rubOut[0])/(T.rubOut[1]-T.rubOut[0])))); });

  /* dust: soft grey puffs that swell and drift up from the heap */
  var puffs=[]; for(var d=0;d<9;d++){ var u4=rnd(), v4=rnd(); puffs.push({e:E('circle', {r:3, fill:'#cdc7ba'}, gProps), x:C[0][0]+(C[1][0]-C[0][0])*u4+(C[3][0]-C[0][0])*v4, y:yb-fd*(.2+rnd()*.4), s:250+d*130+rnd()*160, L:1300+rnd()*700, r:(8+rnd()*8)*cs}); }
  items.push(function(t){ puffs.forEach(function(q){ var k=(t-q.s)/q.L; if(k<=0||k>=1){ setO(q.e, 0); return; } setA(q.e, 'cx', q.x+k*6*cs); setA(q.e, 'cy', q.y-k*(10+H*.18)*cs*.8); setA(q.e, 'r', 3+q.r*sm(k)); setO(q.e, .42*Math.sin(Math.PI*Math.min(1,k*1.15))); }); });

  /* the building's own storeys, kept as copies of its art, each clipped to its band (the walls, then the roof) */
  /* a node's art is cut two ways: the glass (its fills overlap the next storey's by a hair, so no seam shows) and the floor lines + sheen (cut half a storey lower, between the storey lines, so a floor line is drawn once by one storey, never doubled or halved) */
  function isLine(k){ var c=k.getAttribute&&k.getAttribute('class')||''; return c==='nb-l' || c==='nb-sheen'; }
  var gcount=0;
  function clipOf(poly){ var id=uid+'_'+(gcount++), cp=E('clipPath', {id:id}, defs); poly.forEach(function(q){ E('polygon', {points:PT(q)}, cp); }); return 'url(#'+id+')'; }
  /* (the lines of every storey are drawn in a layer over all the glass, so no storey's glass covers the lines of the one below) */
  function mkGroup(poly, polyL, cxy){ var o=E('g', null, gClad), i=E('g', {'clip-path':clipOf(poly)}, o), ol=polyL?E('g', null, gCladL):null, il=ol?E('g', {'clip-path':clipOf(polyL)}, ol):null;
    S.kids.forEach(function(k){ if(k===S.shadow) return; (il && isLine(k)?il:i).appendChild(k.cloneNode(true)); }); return {o:o, ol:ol, cx:cxy[0], cy:cxy[1]}; }
  function put(g, o, tr){ setO(g.o, o); setT(g.o, tr); if(g.ol){ setO(g.ol, o); setT(g.ol, tr); } }
  var grp=[], roof;
  for(var k=0;k<K;k++){
    var t0=k*hs, t1=(k+1)*hs, polys=[], polyL=[];
    if(!bands){ faces.forEach(function(f){ var A=f.A, B=f.B, ux=B[0]-A[0], uy=B[1]-A[1], ul=Math.hypot(ux,uy)||1; ux/=ul; uy/=ul; var e=1.8;
        var A2=[A[0]-ux*e, A[1]-uy*e], B2=[B[0]+ux*e, B[1]+uy*e], lo=(k===0?-3:t0-.4), hi=(k===N-1?t1+1.8:t1);
        polys.push([up(A2,lo), up(B2,lo), up(B2,hi), up(A2,hi)]); var l0=(k===0?-3:t0-hs/2), l1=(k===N-1?t1+1.8:t1-hs/2); polyL.push([up(A2,l0), up(B2,l0), up(B2,l1), up(A2,l1)]); }); }
    else { var ya=yb-t1, yb2=yb-t0+(k===0?400:.25); polys.push([[cx-1500,ya],[cx+1500,ya],[cx+1500,yb2],[cx-1500,yb2]]); polyL=null; }
    grp.push(mkGroup(polys, bands?null:polyL, [cx, yb-(k+.5)*hs]));
  }
  /* the roof: a node's top face; a tower's crown (everything above its last full storey, spire and all) */
  if(!bands){ roof=mkGroup([grow(C.map(function(q){ return up(q,H); }), 2.2)], null, [cx, cy-H]); }
  else { var yc=yb-(N-1)*hs; roof=mkGroup([[[cx-1500,-4000],[cx+1500,-4000],[cx+1500,yc+.25],[cx-1500,yc+.25]]], null, [cx, yb-H]); }
  /* at the end the banded copies are cross-faded into one whole, unclipped copy of the art (what the real building is), so any hairline where two bands meet is gone before the swap */
  S.kids.forEach(function(k){ if(k!==S.shadow) gFull.appendChild(k.cloneNode(true)); });
  items.push(function(t){ var x=sm((t-T.xfade[0])/(T.xfade[1]-T.xfade[0])), st=sm((t-60)/120);          /* (a hit starts from the real building itself: pure copy at t=0, the banded copies take over within 0.2 s) */
    if(t<T.xfade[0]){ setO(gFull, 1-st); setO(gBuilt, st); } else { setO(gFull, x); setO(gBuilt, 1-x); } });
  var tsC=function(k){ return T.clad[0]+k*((T.clad[1]-T.clad[0])/Math.max(1,K)); }, CD=560, cst=hash(S.id);
  grp.forEach(function(g, k){ var ra=(((cst>>(k%24))&3)-1.5)*3.2, cs0=200+(K-1-k)*(520/Math.max(1,K));
    items.push(function(t){ var o, dy=0, rot=0;
      if(t<T.coll+80){ var x=cl((t-cs0)/520); o=1-sm((x-.45)/.55); dy=x*x*(k*hs+8); rot=ra*x; }
      else { var b=cl((t-tsC(k))/CD); o=sm(b); }
      put(g, o, (dy||rot)?('translate(0 '+dy.toFixed(1)+') rotate('+rot.toFixed(1)+' '+g.cx.toFixed(1)+' '+g.cy.toFixed(1)+')'):''); }); });
  var lift=14+4*cs;
  items.push(function(t){ var o, dy=0, rot=0;
    if(t<T.coll+80){ var x=cl((t-200)/520); o=1-sm((x-.45)/.55); dy=x*x*(H+10); rot=-2.5*x; }
    else { o=cl((t-T.roof[0])/320); dy=-lift*(1-sm((t-T.roof[0]-300)/(T.roof[1]-T.roof[0]-600))); }
    setO(roof.o, o); setT(roof.o, (dy||rot)?('translate(0 '+dy.toFixed(1)+') rotate('+rot.toFixed(1)+' '+roof.cx.toFixed(1)+' '+roof.cy.toFixed(1)+')'):''); });
  function roofDy(t){ return -lift*(1-sm((t-T.roof[0]-300)/(T.roof[1]-T.roof[0]-600))); }

  /* the steel frame: per storey a floor slab (translucent, its edge thick), columns with a highlight, and a diagonal brace on the walls you see */
  var Ci=C.map(function(q){ return inset(q, .9); }), cols=Ci.map(function(q,ix){ return {p:q, back:ix<2}; });
  faces.forEach(function(f){ var len=Math.hypot(f.B[0]-f.A[0], f.B[1]-f.A[1]), nm=Math.min(5, Math.max(1, Math.round(len/(15*cs))));
    for(var m=1;m<nm;m++){ var u=m/nm; cols.push({p:inset([f.A[0]+(f.B[0]-f.A[0])*u, f.A[1]+(f.B[1]-f.A[1])*u], .9), back:false}); } });
  var fr=[];
  for(var s=0;s<N;s++){
    var g=E('g', null, gFrame), a0=s*hs, a1=(s+1)*hs;
    E('polygon', {points:PT(Ci.map(function(q){ return up(q,a1); })), fill:CONC, 'fill-opacity':.2, stroke:'#6b7385', 'stroke-width':1, 'vector-effect':'non-scaling-stroke', 'stroke-linejoin':'round'}, g);
    faces.forEach(function(f){ var A=inset(f.A,.9), B=inset(f.B,.9); E('polygon', {points:PT([up(A,a1), up(B,a1), [B[0],B[1]-a1+2], [A[0],A[1]-a1+2]]), fill:CONCD, stroke:'#5a6070', 'stroke-width':.8, 'vector-effect':'non-scaling-stroke'}, g); });
    var cd='', ch='', cb=''; cols.forEach(function(c){ var seg='M'+c.p[0].toFixed(1)+' '+(c.p[1]-a0).toFixed(1)+'L'+c.p[0].toFixed(1)+' '+(c.p[1]-a1).toFixed(1); if(c.back) cb+=seg; else { cd+=seg; ch+='M'+(c.p[0]+.8).toFixed(1)+' '+(c.p[1]-a0).toFixed(1)+'L'+(c.p[0]+.8).toFixed(1)+' '+(c.p[1]-a1).toFixed(1); } });
    E('path', {d:cb, fill:'none', stroke:STEEL, 'stroke-opacity':.45, 'stroke-width':1.3, 'vector-effect':'non-scaling-stroke'}, g);
    E('path', {d:cd, fill:'none', stroke:STEEL, 'stroke-width':1.9, 'vector-effect':'non-scaling-stroke'}, g);
    E('path', {d:ch, fill:'none', stroke:STEELHI, 'stroke-width':.8, 'vector-effect':'non-scaling-stroke'}, g);
    var br=''; faces.forEach(function(f){ var A=inset(f.A,.9), B=inset(f.B,.9), len=Math.hypot(B[0]-A[0], B[1]-A[1]), nb=Math.max(1, Math.round(len/(18*cs)));
      for(var m=0;m<nb;m++){ var ua=m/nb, ub=(m+1)/nb, fl=(s+m)%2, xa=A[0]+(B[0]-A[0])*ua, ya=A[1]+(B[1]-A[1])*ua, xb=A[0]+(B[0]-A[0])*ub, yb_=A[1]+(B[1]-A[1])*ub;
        br+='M'+xa.toFixed(1)+' '+(ya-(fl?a1:a0)).toFixed(1)+'L'+xb.toFixed(1)+' '+(yb_-(fl?a0:a1)).toFixed(1); } });
    E('path', {d:br, fill:'none', stroke:'#6f7c93', 'stroke-width':1, 'vector-effect':'non-scaling-stroke'}, g);
    fr.push(g); }
  var fS=function(s){ return T.frame[0]+s*((T.frame[1]-T.frame[0]-450)/N); };
  fr.forEach(function(g, s){ items.push(function(t){ var x=cl((t-fS(s))/450); setO(g, sm(x)*(1-sm((t-T.frameOut[0])/(T.frameOut[1]-T.frameOut[0])))); setT(g, x<1?('translate(0 '+(-7*(1-sm(x))).toFixed(1)+')'):''); }); });

  /* scaffolding: poles, ledgers with a board, and a diagonal, on each wall you can see, a storey at a time; it comes down from the top */
  var sc=[], so=2.6*cs;
  for(var q=0;q<N;q++){ var gq=E('g', null, gScaf), a0q=q*hs, a1q=(q+1)*hs, dd='';
    faces.forEach(function(f){ var A=f.A, B=f.B, nx=(B[1]-A[1]), ny=-(B[0]-A[0]), nl=Math.hypot(nx,ny)||1; nx=nx/nl*so; ny=ny/nl*so; var Ao=[A[0]+nx,A[1]+ny], Bo=[B[0]+nx,B[1]+ny], len=Math.hypot(B[0]-A[0], B[1]-A[1]), np=Math.max(1, Math.round(len/(9*cs)));
      for(var m=0;m<=np;m++){ var u=m/np, px=Ao[0]+(Bo[0]-Ao[0])*u, py=Ao[1]+(Bo[1]-Ao[1])*u; dd+='M'+px.toFixed(1)+' '+(py-a0q).toFixed(1)+'L'+px.toFixed(1)+' '+(py-a1q).toFixed(1); }
      dd+='M'+Ao[0].toFixed(1)+' '+(Ao[1]-a1q).toFixed(1)+'L'+Bo[0].toFixed(1)+' '+(Bo[1]-a1q).toFixed(1);
      var mm=(q%2)?0:np-1; if(np>0){ var ua=Math.max(0,mm)/np, ub=(Math.max(0,mm)+1)/np; dd+='M'+(Ao[0]+(Bo[0]-Ao[0])*ua).toFixed(1)+' '+(Ao[1]+(Bo[1]-Ao[1])*ua-a0q).toFixed(1)+'L'+(Ao[0]+(Bo[0]-Ao[0])*ub).toFixed(1)+' '+(Ao[1]+(Bo[1]-Ao[1])*ub-a1q).toFixed(1); } });
    E('path', {d:dd, fill:'none', stroke:TAN, 'stroke-width':1, 'stroke-linecap':'round', 'vector-effect':'non-scaling-stroke'}, gq); sc.push(gq); }
  sc.forEach(function(g, q){ items.push(function(t){ var a=sm((t-(T.scaf[0]+q*((T.scaf[1]-T.scaf[0])/N)))/420), o=sm((t-(T.scafOut[0]+(N-1-q)*((T.scafOut[1]-T.scafOut[0]-420)/N)))/420); setO(g, a*(1-o)); }); });

  /* the tower crane: mast (rails + lattice) climbs section by section, then the jib swings out and the hook starts work */
  var gy=yb-2, xc=side>0?maxX+11*cs:minX-11*cs, mw=2.6*cs, sH=6.5*cs, roofTop=bands?(yb-H):(cy-H), Hm=H+fd*.5+lift+20*cs+8, nSec=Math.ceil(Hm/sH);
  var ytopC=gy-Hm, gMast=E('g', null, gProps), rails=[E('line', {x1:xc-mw, y1:gy, x2:xc-mw, y2:gy, stroke:YEL, 'stroke-width':1.3, 'vector-effect':'non-scaling-stroke'}, gMast),
    E('line', {x1:xc+mw, y1:gy, x2:xc+mw, y2:gy, stroke:YEL, 'stroke-width':1.3, 'vector-effect':'non-scaling-stroke'}, gMast)], secs=[];
  E('rect', {x:xc-mw*1.9, y:gy-2.2*cs, width:mw*3.8, height:2.2*cs, fill:'#6c707c', stroke:'#3d404a', 'stroke-width':.8, 'vector-effect':'non-scaling-stroke'}, gMast);
  for(var ms=0;ms<nSec;ms++){ var y0=gy-ms*sH, y1=gy-(ms+1)*sH, fl=ms%2; secs.push(E('path', {d:'M'+(xc-mw)+' '+y0.toFixed(1)+'L'+(xc+mw)+' '+y1.toFixed(1)+'M'+(xc+mw)+' '+y0.toFixed(1)+'L'+(xc-mw)+' '+y1.toFixed(1)+'M'+(xc-mw)+' '+y1.toFixed(1)+'L'+(xc+mw)+' '+y1.toFixed(1),
    fill:'none', stroke:YELD, 'stroke-width':.8, 'vector-effect':'non-scaling-stroke'}, gMast)); }
  var yj=ytopC, Lj=Math.max(Math.abs(xc-cx)+8*cs, 26*cs), xtip=xc+dir*Lj, xcw=xc-dir*Math.max(12*cs, Lj*.28), gJ=E('g', null, gProps);
  function yTopAt(x){ return yj-4*cs*(1-Math.min(1, Math.abs(x-xc)/Lj)); }
  var jd='M'+xcw.toFixed(1)+' '+yj.toFixed(1)+'L'+xtip.toFixed(1)+' '+yj.toFixed(1)+'M'+xc.toFixed(1)+' '+(yj-4*cs).toFixed(1)+'L'+xtip.toFixed(1)+' '+yj.toFixed(1)+'M'+xc.toFixed(1)+' '+(yj-4*cs).toFixed(1)+'L'+xcw.toFixed(1)+' '+(yj-1).toFixed(1);
  var nz=Math.max(3, Math.round(Lj/(7*cs))); for(var z=0;z<nz;z++){ var xa_=xc+dir*Lj*z/nz, xb_=xc+dir*Lj*(z+.5)/nz, xc_=xc+dir*Lj*(z+1)/nz; jd+='M'+xa_.toFixed(1)+' '+yj.toFixed(1)+'L'+xb_.toFixed(1)+' '+yTopAt(xb_).toFixed(1)+'L'+xc_.toFixed(1)+' '+yj.toFixed(1); }
  E('path', {d:jd, fill:'none', stroke:YEL, 'stroke-width':1.15, 'stroke-linejoin':'round', 'vector-effect':'non-scaling-stroke'}, gJ);
  var apex=yj-14*cs, xp=xc+dir*Lj*.78; E('path', {d:'M'+(xc-mw)+' '+(yj-4*cs).toFixed(1)+'L'+xc+' '+apex.toFixed(1)+'L'+(xc+mw)+' '+(yj-4*cs).toFixed(1)+'M'+xc+' '+apex.toFixed(1)+'L'+xp.toFixed(1)+' '+yTopAt(xp).toFixed(1)+'M'+xc+' '+apex.toFixed(1)+'L'+xcw.toFixed(1)+' '+(yj-1).toFixed(1),
    fill:'none', stroke:YELD, 'stroke-width':.8, 'vector-effect':'non-scaling-stroke'}, gJ);
  E('rect', {x:xcw+dir*2.5*cs-2.5*cs, y:yj+.4, width:5*cs, height:5.5*cs, fill:'#7c7f89', stroke:'#3d404a', 'stroke-width':.8, 'vector-effect':'non-scaling-stroke'}, gJ);
  E('rect', {x:xc-2.2*cs, y:yj+.6, width:4.4*cs, height:4.2*cs, fill:'#fff7dc', stroke:YELD, 'stroke-width':.8, 'vector-effect':'non-scaling-stroke'}, gJ);
  var trolley=E('rect', {x:-1.6*cs, y:yj-.4, width:3.2*cs, height:2.1*cs, fill:'#40424c'}, gProps);
  var cable=E('line', {stroke:'#2d3038', 'stroke-width':.9, 'vector-effect':'non-scaling-stroke'}, gProps);
  var hk=E('path', {d:'M0 0v2.4a1.7 1.7 0 1 1 -1.7 1.7', fill:'none', stroke:'#2d3038', 'stroke-width':1.3, 'stroke-linecap':'round', 'vector-effect':'non-scaling-stroke'}, gProps);
  var sling=E('path', {fill:'none', stroke:'#2d3038', 'stroke-width':.8, 'vector-effect':'non-scaling-stroke'}, gProps), load=E('rect', {height:3.4*cs, width:8*cs, 'stroke-width':.9, 'vector-effect':'non-scaling-stroke', stroke:'#2a2d36'}, gProps);
  /* the hoist beside the lot (a mast with a cage that runs up and down it) */
  var xh=side>0?minX-8*cs:maxX+8*cs, gH=E('g', null, gProps), hr=[E('line', {x1:xh-1.5*cs, y1:gy, x2:xh-1.5*cs, y2:gy, stroke:'#56627f', 'stroke-width':1.2, 'vector-effect':'non-scaling-stroke'}, gH), E('line', {x1:xh+1.5*cs, y1:gy, x2:xh+1.5*cs, y2:gy, stroke:'#56627f', 'stroke-width':1.2, 'vector-effect':'non-scaling-stroke'}, gH)], hrung=[];
  for(var hq=0;hq<N;hq++){ hrung.push(E('path', {d:'M'+(xh-1.5*cs)+' '+(gy-hq*hs).toFixed(1)+'L'+(xh+1.5*cs)+' '+(gy-(hq+1)*hs).toFixed(1)+'M'+(xh+1.5*cs)+' '+(gy-hq*hs).toFixed(1)+'L'+(xh-1.5*cs)+' '+(gy-(hq+1)*hs).toFixed(1), fill:'none', stroke:'#56627f', 'stroke-width':.7, 'vector-effect':'non-scaling-stroke'}, gH)); }
  var cage=E('rect', {x:xh-3.4*cs, width:6.8*cs, height:6.2*cs, fill:'#eef0f6', stroke:'#56627f', 'stroke-width':1, 'vector-effect':'non-scaling-stroke'}, gH);
  /* the crane's mast grows */
  items.push(function(t){ var m=sm((t-T.mast[0])/(T.mast[1]-T.mast[0])), cur=Hm*m, top=gy-cur;
    rails.forEach(function(r){ setA(r, 'y2', top); }); secs.forEach(function(e, i){ setO(e, (i+1)*sH<=cur+.5?1:0); });
    var jk=sm((t-T.jib[0])/(T.jib[1]-T.jib[0])); setT(gJ, 'translate('+xc.toFixed(1)+' '+yj.toFixed(1)+') scale('+Math.max(.001,jk).toFixed(3)+' 1) translate('+(-xc).toFixed(1)+' '+(-yj).toFixed(1)+')');
    var out=1-sm((t-T.propsOut[0])/(T.propsOut[1]-T.propsOut[0])); setO(gMast, t<T.mast[0]?0:out); setO(gJ, jk>.01?out:0); setO(gH, t<T.hoist[0]?0:out); });
  /* the hook: ferries steel up to the top of the frame, then glass panels to the cladding; at the end it lowers the roof */
  var P_=(T.hook1-T.hook0)/4, xpk=xc+dir*10*cs, ypk=gy-3*cs;
  function dropY(c){ return yb-hs*lvlAt(T.hook0+(c+1)*P_)-4*cs; }
  function dropX(c){ return cx+(((c%3)+3)%3-1)*fw*.17; }
  function hookAt(t){
    var yUp=ytopC+9*cs;
    if(t<T.hook0) return {x:xc+dir*3*cs, y:yUp, l:0};
    if(t<T.hook1){ var c=Math.floor((t-T.hook0)/P_), tt=(t-T.hook0)/P_-c, xd0=dropX(c-1), yd0=c?dropY(c-1):dropY(0), xd=dropX(c), yd=dropY(c), yc=Math.max(yUp, yd-12*cs);
      var K_=[[0,xd0,yd0+0],[.12,xd0,yUp],[.35,xpk,yUp],[.5,xpk,ypk],[.56,xpk,ypk],[.72,xpk,yc],[.9,xd,yc],[1,xd,yd]];
      for(var i2=1;i2<K_.length;i2++) if(tt<=K_[i2][0]){ var a=K_[i2-1], b=K_[i2], u=sm((tt-a[0])/(b[0]-a[0])); return {x:lerp(a[1],b[1],u), y:lerp(a[2],b[2],u), l:i2>=5?1:0, c:c}; }
      return {x:xd, y:yd, l:1, c:c}; }
    var xl=dropX(3), yl=dropY(3);
    if(t<T.roof[0]){ var u1=sm((t-T.hook1)/(T.roof[0]-T.hook1)); return {x:lerp(xl, cx, u1), y:lerp(yl, roofTop-lift-8*cs-(0), u1), l:0, c:4}; }
    if(t<T.roof[1]) return {x:cx, y:roofTop+roofDy(t)-8*cs, l:2, c:4};
    var u2=sm((t-T.roof[1])/900); return {x:lerp(cx, xc+dir*3*cs, u2), y:lerp(roofTop-8*cs, yUp, u2), l:0, c:4};
  }
  items.push(function(t){ var h=hookAt(t), sw=h.l===1?Math.sin(t/330)*.9*cs:(h.l===2?0:Math.sin(t/410)*.35*cs), hx=h.x+sw;
    var on=sm((t-T.jib[0])/(T.jib[1]-T.jib[0])); var out=1-sm((t-T.propsOut[0])/(T.propsOut[1]-T.propsOut[0]));
    setA(trolley, 'x', h.x-1.6*cs); setA(trolley, 'y', yj-.4); setA(cable, 'x1', h.x); setA(cable, 'y1', yj+1.6); setA(cable, 'x2', hx); setA(cable, 'y2', h.y);
    setT(hk, 'translate('+hx.toFixed(1)+' '+h.y.toFixed(1)+') scale('+(cs*.8).toFixed(2)+')');
    var show=(h.l===1||h.l===2), ly=h.y+4.4*cs;
    if(h.l===2){ var L1=bands?[cx-fw*.4, roofTop+roofDy(t)+5]:null, L2=bands?[cx+fw*.4, roofTop+roofDy(t)+5]:null;
      if(!bands){ var rp=C.map(function(q){ return [q[0], q[1]-H+roofDy(t)]; }), lm=rp[0], rm=rp[0]; rp.forEach(function(q){ if(q[0]<lm[0]) lm=q; if(q[0]>rm[0]) rm=q; }); L1=lm; L2=rm; }
      setA(sling, 'd', 'M'+L1[0].toFixed(1)+' '+L1[1].toFixed(1)+'L'+hx.toFixed(1)+' '+(h.y+3).toFixed(1)+'L'+L2[0].toFixed(1)+' '+L2[1].toFixed(1)); }
    else if(show){ setA(sling, 'd', 'M'+(hx-3.4*cs).toFixed(1)+' '+ly.toFixed(1)+'L'+hx.toFixed(1)+' '+(h.y+3).toFixed(1)+'L'+(hx+3.4*cs).toFixed(1)+' '+ly.toFixed(1)); }
    var glass=t>=T.clad[0]-300; setA(load, 'x', hx-4*cs); setA(load, 'y', ly); setA(load, 'fill', glass?'#8cc2e4':'#5a6479');
    setO(trolley, h.l>=0?on*out:0); setO(cable, on*out); setO(hk, on*out); setO(sling, show?on*out:0); setO(load, h.l===1?on*out:0); });
  /* the hoist: its mast climbs with the frame, its cage runs up and down it */
  items.push(function(t){ var m=sm((t-T.hoist[0])/(T.hoist[1]-T.hoist[0])), top=gy-(H+4*cs)*m;
    hr.forEach(function(r){ setA(r, 'y2', top); }); hrung.forEach(function(e, i){ setO(e, (i+1)*hs<=(H+4*cs)*m+.5?1:0); });
    var run=sm((t-T.hoist[0])/600)*(1-sm((t-T.propsOut[0])/(T.propsOut[1]-T.propsOut[0]))), reach=Math.max(hs, (H+4*cs)*m), ph=.5-.5*Math.cos((t-T.hoist[0])/5200*Math.PI*2);
    setA(cage, 'y', gy-6.2*cs-(reach-6.2*cs)*ph); setO(cage, run>.02?1:0); });

  return {layer:layer, upd:function(t){ for(var i=0;i<items.length;i++) items[i](t); }};
}

/* ── specs: a node's glass block (an <svg class=nb3d>) and a landmark tower (a .pl-lmb group whose art is a <use>) ── */
function specNode(svg){
  var nb=svg._nb; if(!nb || !nb.C) return null; var kids=[].filter.call(svg.children, function(c){ return c.tagName!=='defs' && !(c.classList&&c.classList.contains('nb-con')); });
  var sh=svg.querySelector(':scope > .nb-sh'), H=nb.H, N=Math.max(3, Math.min(11, Math.round(H/9)));
  return {id:nb.id, mode:'prism', C:nb.C, H:H, N:N, par:svg, host:svg, kids:kids, shadow:sh};
}
function specLm(g){
  var L=g._lm; if(!L || !L.use || !L.art) return null; var u=L.use, uy=parseFloat(u.getAttribute('y')), x=L.x, y=L.y, w=L.w, h=L.h, lean=.25*h, ground=y+h, H=Math.max(30, ground-uy-3);
  var N=Math.max(6, Math.min(26, Math.round(H/(H>260?13:9))));
  return {id:L.name, mode:'bands', C:[[x+lean,y],[x+w,y],[x+w-lean,y+h],[x,y+h]], H:H, N:N, par:L.art, host:g, kids:[u], shadow:null};
}

function loop(){
  raf=0; var now=performance.now();
  for(var i=runs.length-1;i>=0;i--){ var r=runs[i], t=(FORCE!=null)?FORCE:(now-r.t0);
    if(!r.S.host.isConnected){ r.kill(); continue; }
    if(t>=T.end){ r.kill(); continue; }
    r.b.upd(t);
    var cardEl=r.tag&&r.tag.querySelector('.node-card'); if(cardEl){ var ta=(t<400)?(1-sm(t/400)):cl((t-(T.end-1000))/1000), tk=ta.toFixed(2); if(r.tk!==tk){ r.tk=tk; cardEl.style.setProperty('opacity', tk, 'important'); } } }          /* the number tag comes back with the finished building, not with a pop */
  if(runs.length) raf=requestAnimationFrame(loop);
}
function run(el_, tagEl){
  if(el_._con) el_._con.kill();
  var S=(el_.classList&&el_.classList.contains('pl-lmb'))?specLm(el_):specNode(el_); if(!S) return false;
  var r={S:S, t0:performance.now(), tag:tagEl, b:null};
  r.b=build(S); S.kids.forEach(function(k){ if(k.style) k.style.display='none'; });          /* the copies are taken first, then the real art is put away */
  if(tagEl) tagEl.classList.add('nb-ruin');
  r.kill=function(){ if(r.dead) return; r.dead=true; if(r.b.layer.parentNode) r.b.layer.parentNode.removeChild(r.b.layer);
    S.kids.forEach(function(k){ if(k.style) k.style.display=''; }); if(tagEl){ tagEl.classList.remove('nb-ruin'); var cd_=tagEl.querySelector('.node-card'); if(cd_) cd_.style.removeProperty('opacity'); } el_._con=null; var ix=runs.indexOf(r); if(ix>=0) runs.splice(ix,1); };
  el_._con=r; runs.push(r); r.b.upd(FORCE!=null?FORCE:0); if(!raf) raf=requestAnimationFrame(loop); return true;
}
return {run:run, freeze:function(ms){ FORCE=(ms==null)?null:+ms; if(!raf && runs.length) raf=requestAnimationFrame(loop); }, active:function(){ return runs.length; }, T:T};
})();
"""
