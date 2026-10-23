"""The craft that fly you between bodies on a Star chart (Luke, 2026-10-21: "i want a real ship, give users choice
ships/crafts ... Same options should apply to star chart classic/retro"; 2026-10-22, after three options sheets: "P4 is
the best, but ... i want high def graphics ... This level for 3d, we do a flat top down drawing for non-3d, make it retro
for retro").

Two craft: the Explorer (P4: a saucer, a swept neck, an engineering hull, two nacelles; in the style of a famous starship,
our own) and the Halo (the saucer Luke likes). One choice per viewer (localStorage alto-ship, every timeline); none chosen,
Retro flies the Halo and the other styles the Explorer. Each craft is:
  * a flat top-down drawing (nose along +x, about 60-70 px long, flown at 0.4-0.5 of that) in the classes sh-hull,
    sh-deck, sh-fin, sh-gold, sh-eng, sh-glow, sh-ring: Classic paints it clean and light (CRAFT_CSS), Retro gold on
    black (solar_draw.py), with its own deco details (sh-ro) shown in Retro only;
  * a high-definition 3D model built in code (smooth lathes and rings, slabs, boxes: no asset to load), drawn by GL
    (window._altoCraft.gl): physically based plated metal, glass, lit windows, lights;
  * its own motion: k the flight's clock, turn, bank, spin (the saucer), its engines' glow and trail.
Also here: the way a craft flies (track, steer, park: solar_fly.py, solar_draw.py and solar_3d.py share it). The picker
(window._altoCraft.open) is a pop-over from the chart's controls. System pages only.
"""

CRAFT_JS = r"""
(function(){
'use strict';
var de=document.documentElement, TAU=Math.PI*2, KEY='alto-ship', subs=[];
var C=[
  /* P4 of the third options sheet (Luke, 2026-10-22: "P4 is the best ... i want high def graphics"): a saucer, a swept
     neck, an engineering hull with a glowing deflector, two nacelles on pylons; in the style of a famous starship, our own */
  {id:'explorer', name:'Explorer', real:false, k:1, turn:2, bank:.2, glow:[.55, .75, 1], trail:[.6, .8, 1], eng:[[-31.9, 7, -11], [-31.9, 7, 11]], wc:[10, 0, 16.2, 3],
   svg:'<ellipse class="sh-glow" cx="-33" cy="-11" rx="3.5" ry="2"/><ellipse class="sh-glow" cx="-33" cy="11" rx="3.5" ry="2"/>'+
     '<path class="sh-fin" d="M-10 -1.6 L-16.5 -1.6 L-19.5 -10.2 L-13.5 -10.2 Z M-10 1.6 L-16.5 1.6 L-19.5 10.2 L-13.5 10.2 Z"/>'+
     '<path class="sh-hull" d="M-6.2 -11 Q-6.2 -13.25 -9 -13.25 L-29.5 -13.25 Q-31.9 -13.25 -31.9 -11 Q-31.9 -8.75 -29.5 -8.75 L-9 -8.75 Q-6.2 -8.75 -6.2 -11 Z M-6.2 11 Q-6.2 13.25 -9 13.25 L-29.5 13.25 Q-31.9 13.25 -31.9 11 Q-31.9 8.75 -29.5 8.75 L-9 8.75 Q-6.2 8.75 -6.2 11 Z"/>'+
     '<path class="sh-eng" d="M-27.5 -11.5 L-9.5 -11.5 L-9.5 -10.5 L-27.5 -10.5 Z M-27.5 11.5 L-9.5 11.5 L-9.5 10.5 L-27.5 10.5 Z M-5.5 -11 A1.3 1.3 0 1 0 -8.1 -11 A1.3 1.3 0 1 0 -5.5 -11 Z M-5.5 11 A1.3 1.3 0 1 0 -8.1 11 A1.3 1.3 0 1 0 -5.5 11 Z"/>'+
     '<path class="sh-hull" d="M3 0 Q3 -3.2 -1 -3.6 L-20 -3.3 Q-23 -2.6 -23 0 Q-23 2.6 -20 3.3 L-1 3.6 Q3 3.2 3 0 Z"/><path class="sh-deck" d="M8 -1.3 L-4 -1.3 L-4 1.3 L8 1.3 Z"/>'+
     '<circle class="sh-hull" cx="10" cy="0" r="15.8"/><path class="sh-gold" d="M20.4 0 A10.4 10.4 0 1 0 -.4 0 A10.4 10.4 0 1 0 20.4 0 M16.6 0 A6.6 6.6 0 1 0 3.4 0 A6.6 6.6 0 1 0 16.6 0"/><circle class="sh-deck" cx="10" cy="0" r="3.2"/><circle class="sh-eng" cx="10" cy="0" r="1"/>'+
     (function(){ var d='M-21 0 L1 0 M-28 -11 L-10 -11 M-28 11 L-10 11', i; for(i=0;i<16;i++){ var a=i/16*TAU, c=Math.cos(a), s=Math.sin(a); d+=' M'+(10+c*11.8).toFixed(1)+' '+(s*11.8).toFixed(1)+' L'+(10+c*14.6).toFixed(1)+' '+(s*14.6).toFixed(1); }
       return '<path class="sh-gold sh-ro" d="'+d+'"/>'; })(),
   build:function(g){ var H=[.74, .76, .8], H2=[.66, .68, .73], D=[.42, .44, .5], Wn=[.74, .76, .8, .6], Gl=[.12, .16, .24, .3];
     g.slathe([[2.4, 0], [2.32, 3], [2.05, 5.5], [1.72, 8], [1.28, 11], [.84, 13.4], [.46, 15], [.12, 15.6], [-.34, 15.8]], 128, H, [10, 6, 0], 1);
     g.slathe([[-.36, 15.82], [-.78, 15.3]], 128, Wn, [10, 6, 0], 1);
     g.slathe([[-.8, 15.28], [-1.12, 13], [-1.5, 9], [-1.86, 5], [-2.06, 2], [-2.12, 0]], 128, H2, [10, 6, 0], 1);
     g.slathe([[3.7, 0], [3.6, 1.1], [3.25, 2], [2.8, 2.7], [2.42, 3.3]], 48, H, [10, 6, 0], 1); g.slathe([[3.74, 0], [3.7, .7]], 32, Gl, [10, 6, 0], 1);
     g.slathe([[3.05, 3.4], [2.9, 4.2], [2.6, 4.7]], 48, Wn, [10, 6, 0], 1);
     g.slathe([[-2.1, 0], [-2.7, 1.5], [-3, 0]], 32, [.62, .66, .72], [10, 6, 0], 1); g.slathe([[-3.02, 0], [-3.02, .7]], 24, [1, .8, .55, 1], [10, 6, 0], 1);
     g.torus(10.4, .18, 128, D, [10, 8.05, 0], 1); g.torus(6.6, .14, 96, D, [10, 8.32, 0], 1);
     g.rbox([2.8, 7.2, 0], [3.4, 1.2, 7], 0, H2); [1, -1].forEach(function(s){ g.box([1.2, 7.2, 2.4*s], [.4, .6, 1.4], [1, .45, .3, 1]); });
     g.vslab([[8, 4.4], [1, 4.4], [-5, 1.2], [1.5, 1.2]], 0, 2.6, H2); [1.32, -1.32].forEach(function(z){ g.vslab([[6.6, 3.8], [1.8, 3.8], [-1.6, 2.2], [2.6, 2.2]], z, .1, Wn); });
     g.slathe([[3.1, 0], [2.7, 2.3], [1.2, 3.4], [-4, 3.85], [-14, 3.75], [-20, 3.25], [-22.6, 2.4], [-23.1, 0]], 96, H, [0, -1.6, 0]);
     [1, -1].forEach(function(s){ [.6, -.4].forEach(function(y){ g.box([-11, -1.6+y, 3.8*s], [10, .32, .12], Wn); }); });
     g.slathe([[3.2, 0], [2.95, 1.2], [2.55, 2.2]], 48, [1, .76, .42, 1], [0, -1.6, 0]); g.torus(2.45, .3, 64, D, [2.5, -1.6, 0]);
     g.box([-22.9, -1.6, 0], [.6, 2.6, 3.6], [.18, .2, .26]); g.box([-23.2, -.3, 0], [.4, .25, 3.2], [1, .82, .55, 1]);
     [1, -1].forEach(function(s){ var c=[0, 7, 11*s];
       g.slab([[-10, 1.6*s], [-16.5, 1.6*s], [-19.5, 10.2*s], [-13.5, 10.2*s]], 3.8, .9, H2); g.vslab([[-11, -1], [-17, -1], [-19, 6], [-14, 6]], 2.2*s, .8, H2);
       g.slathe([[-6, 0], [-6.25, 1.2], [-7, 1.9], [-9, 2.25], [-29, 2.25], [-30.6, 1.85], [-31.6, 1.05], [-31.9, 0]], 64, H, c);
       g.slathe([[-5.9, 0], [-6.12, 1.1], [-6.9, 1.85]], 40, [1, .32, .22, 1], c); g.torus(2.28, .16, 64, D, [-9.2, 7, 11*s]);
       g.box([-18.5, 7, 8.88*s], [19, 1.1, .3], [.45, .7, 1, 1]); g.box([-18.5, 9.2, 11*s], [19, .3, .9], [.45, .7, 1, 1]); g.box([-30.6, 7, 11*s], [1.4, 1.8, 1.8], [.35, .5, .9, 1]); }); }},
  /* the saucer Luke likes (in Retro above all), drawn in the same high definition: a polished lens, a glass dome, a lit
     window row round the rim, its ring of lights, a glow under it */
  {id:'halo', name:'Halo', real:false, k:1, turn:3, bank:0, spin:.6, glow:[.55, .85, 1], trail:[.6, .9, 1], eng:[[0, -2.8, 0]], wc:[0, 0, 30, -10],
   svg:'<circle class="sh-glow" cx="0" cy="0" r="24"/><circle class="sh-ring" cx="0" cy="0" r="22"/><circle class="sh-hull" cx="0" cy="0" r="20"/>'+
     '<circle class="sh-gold" cx="0" cy="0" r="14.5"/><circle class="sh-deck" cx="0" cy="0" r="8.5"/><path class="sh-gold" d="M9 0 L19 0"/>'+
     '<g class="sh-spin"><circle class="sh-eng" cx="17.5" cy="0" r="1.2"/><circle class="sh-eng" cx="-17.5" cy="0" r="1.2"/><circle class="sh-eng" cx="0" cy="17.5" r="1.2"/><circle class="sh-eng" cx="0" cy="-17.5" r="1.2"/>'+
     '<circle class="sh-eng" cx="12.4" cy="12.4" r="1"/><circle class="sh-eng" cx="-12.4" cy="12.4" r="1"/><circle class="sh-eng" cx="12.4" cy="-12.4" r="1"/><circle class="sh-eng" cx="-12.4" cy="-12.4" r="1"/></g>',
   build:function(g){ var H=[.74, .76, .82];
     g.slathe([[2.6, 0], [2.55, 4], [2.2, 8], [1.5, 13], [.7, 17.5], [0, 20.5], [-.3, 21.2]], 128, H, null, 1);
     g.slathe([[-.32, 21.22], [-.76, 20.1]], 128, [.74, .76, .82, .6], null, 1);
     g.slathe([[-.8, 20], [-1.4, 15], [-2, 9], [-2.3, 4], [-2.35, 0]], 128, [.62, .64, .7], null, 1);
     g.slathe([[2.6, 8.5], [4.6, 7.4], [6.4, 5.4], [7.6, 3], [8, 0]], 64, [.22, .42, .68, .3], null, 1); g.torus(8.6, .3, 96, [.46, .48, .55], [0, 2.6, 0], 1);
     g.torus(14.5, .16, 128, [.46, .48, .55], [0, 1.95, 0], 1); g.torus(10, .35, 96, [.6, .92, 1, 1], [0, -2.25, 0], 1);
     for(var i=0;i<12;i++){ var a=i/12*TAU; g.rbox([Math.cos(a)*18, .72, Math.sin(a)*18], [1.6, .5, 1.1], -a, [.6, .92, 1, 1]); } }}
];
var BY={}; C.forEach(function(c){ BY[c.id]=c; });
var MINE;                                           /* (read once: a flight asks every frame, and WebKit's storage is a round trip) */
function pick(){ if(MINE===undefined){ var v=null; try{ v=localStorage.getItem(KEY); }catch(e){} MINE=v && BY[v] ? v : null; } return MINE; }
window.addEventListener('storage', function(e){ if(e.key===KEY){ MINE=undefined; subs.forEach(function(f){ try{ f(cur()); }catch(x){} }); } });
function cur(){ return pick() || (de.classList.contains('sk-retro') ? 'halo' : 'explorer'); }
/* ── the 3D models: a little mesh kit (x along the nose, y up, z to starboard); each face's normal turned away from the
   point given (the part's axis or middle), so the parts read as solids from any side ── */
function kit(){
  var P=[], N=[], K=[];
  function tri(a, b, c, k, o){ var u=[b[0]-a[0], b[1]-a[1], b[2]-a[2]], v=[c[0]-a[0], c[1]-a[1], c[2]-a[2]], n=[u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]], l=Math.hypot(n[0], n[1], n[2]);
    if(l<1e-9) return; n=[n[0]/l, n[1]/l, n[2]/l];
    var m=[(a[0]+b[0]+c[0])/3-o[0], (a[1]+b[1]+c[1])/3-o[1], (a[2]+b[2]+c[2])/3-o[2]]; if(n[0]*m[0]+n[1]*m[1]+n[2]*m[2]<0) n=[-n[0], -n[1], -n[2]];
    [a, b, c].forEach(function(q){ P.push(q[0], q[1], q[2]); N.push(n[0], n[1], n[2]); K.push(k[0], k[1], k[2], k[3]||0); }); }
  function quad(a, b, c, d, k, o){ tri(a, b, c, k, o); tri(a, c, d, k, o); }
  return {
    /* a profile [[along, radius], ...] turned about the x axis (or y, for the saucer), from a centre c */
    lathe:function(pr, sg, k, c, ay){ c=c||[0, 0, 0];
      function pt(q, a){ return ay ? [c[0]+q[1]*Math.cos(a), c[1]+q[0], c[2]+q[1]*Math.sin(a)] : [c[0]+q[0], c[1]+q[1]*Math.cos(a), c[2]+q[1]*Math.sin(a)]; }
      for(var i=0;i<sg;i++){ var a0=i/sg*TAU, a1=(i+1)/sg*TAU;
        for(var j=0;j+1<pr.length;j++){ var A=pr[j], B=pr[j+1], h=(A[0]+B[0])/2; if(A[1]<1e-6 && B[1]<1e-6) continue;
          quad(pt(A, a0), pt(B, a0), pt(B, a1), pt(A, a1), k, ay ? [c[0], c[1]+h, c[2]] : [c[0]+h, c[1], c[2]]); } } },
    /* the same, smooth: each point's normal from the profile's own slope (shared where the profile bends gently, a crease
       where it turns sharply), so a hull reads as one polished surface, not facets */
    slathe:function(pr, sg, k, c, ay){ c=c||[0, 0, 0]; var n=pr.length, cA=0, cR=0, S=[], j, i;
      pr.forEach(function(q){ cA+=q[0]/n; cR+=q[1]/n; });
      for(j=0;j+1<n;j++){ var A=pr[j], B=pr[j+1], dA=B[0]-A[0], dR=B[1]-A[1], l=Math.hypot(dA, dR)||1, q=[-dR/l, dA/l];
        if(q[0]*((A[0]+B[0])/2-cA)+q[1]*((A[1]+B[1])/2-cR)<0) q=[-q[0], -q[1]]; S.push(q); }
      function nv(s, j2){ var o=j2===s ? s-1 : s+1, a=S[s], b=S[o]; if(!b || a[0]*b[0]+a[1]*b[1]<.5) return a; var x=a[0]+b[0], y=a[1]+b[1], l=Math.hypot(x, y)||1; return [x/l, y/l]; }
      function pt(q, a){ return ay ? [c[0]+q[1]*Math.cos(a), c[1]+q[0], c[2]+q[1]*Math.sin(a)] : [c[0]+q[0], c[1]+q[1]*Math.cos(a), c[2]+q[1]*Math.sin(a)]; }
      function nm(q, a){ return ay ? [q[1]*Math.cos(a), q[0], q[1]*Math.sin(a)] : [q[0], q[1]*Math.cos(a), q[1]*Math.sin(a)]; }
      function put(p, m){ P.push(p[0], p[1], p[2]); N.push(m[0], m[1], m[2]); K.push(k[0], k[1], k[2], k[3]||0); }
      for(i=0;i<sg;i++){ var a0=i/sg*TAU, a1=(i+1)/sg*TAU;
        for(j=0;j+1<n;j++){ var A2=pr[j], B2=pr[j+1]; if(A2[1]<1e-6 && B2[1]<1e-6) continue; var na=nv(j, j), nb=nv(j, j+1);
          var v=[[pt(A2, a0), nm(na, a0)], [pt(B2, a0), nm(nb, a0)], [pt(B2, a1), nm(nb, a1)], [pt(A2, a1), nm(na, a1)]];
          [0, 1, 2, 0, 2, 3].forEach(function(x){ put(v[x][0], v[x][1]); }); } } },
    /* a smooth ring: tube radius r round a circle of radius R, about x (or y) */
    torus:function(R, r, sg, k, c, ay){ var pr=[], i; for(i=0;i<=14;i++){ var t=i/14*TAU; pr.push([r*Math.sin(t), R+r*Math.cos(t)]); } this.slathe(pr, sg, k, c, ay); },
    /* a box turned by a about the vertical through its centre (a module on a ring) */
    rbox:function(c, s, a, k){ var ca=Math.cos(a), sa=Math.sin(a), v=[];
      [[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1], [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]].forEach(function(q){ var x=q[0]*s[0]/2, z=q[2]*s[2]/2; v.push([c[0]+x*ca-z*sa, c[1]+q[1]*s[1]/2, c[2]+x*sa+z*ca]); });
      [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [3, 2, 6, 7], [0, 3, 7, 4], [1, 2, 6, 5]].forEach(function(f){ quad(v[f[0]], v[f[1]], v[f[2]], v[f[3]], k, c); }); },
    box:function(c, s, k){ var x0=c[0]-s[0]/2, x1=c[0]+s[0]/2, y0=c[1]-s[1]/2, y1=c[1]+s[1]/2, z0=c[2]-s[2]/2, z1=c[2]+s[2]/2,
        v=[[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]];
      [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [3, 2, 6, 7], [0, 3, 7, 4], [1, 2, 6, 5]].forEach(function(f){ quad(v[f[0]], v[f[1]], v[f[2]], v[f[3]], k, c); }); },
    /* a flat convex plate, [[x, z], ...] at height y (a wing), or [[x, y], ...] at z (a fin: vslab), t thick */
    slab:function(pl, y, t, k){ plate(pl, t, k, function(u, v, w){ return [u, y+w, v]; }); },
    vslab:function(pl, z, t, k){ plate(pl, t, k, function(u, v, w){ return [u, v, z+w]; }); },
    out:function(){ return {p:P, n:N, k:K}; } };
  function plate(pl, t, k, at){ var cu=0, cv=0, i; pl.forEach(function(q){ cu+=q[0]; cv+=q[1]; }); cu/=pl.length; cv/=pl.length;
    for(i=1;i+1<pl.length;i++){ tri(at(pl[0][0], pl[0][1], t/2), at(pl[i][0], pl[i][1], t/2), at(pl[i+1][0], pl[i+1][1], t/2), k, at(cu, cv, -1));
      tri(at(pl[0][0], pl[0][1], -t/2), at(pl[i][0], pl[i][1], -t/2), at(pl[i+1][0], pl[i+1][1], -t/2), k, at(cu, cv, 1)); }
    for(i=0;i<pl.length;i++){ var a=pl[i], b=pl[(i+1)%pl.length]; quad(at(a[0], a[1], -t/2), at(b[0], b[1], -t/2), at(b[0], b[1], t/2), at(a[0], a[1], t/2), k, at(cu, cv, 0)); } }
}
var MESH={};
function mesh(id){ var c=BY[id]; if(!c) return null; if(!MESH[id]){ var g=kit(); c.build(g); MESH[id]=g.out(); } return MESH[id]; }
/* ── the picker: a pop-over over the controls, the real craft and the science-fiction ones, each its art in this style ── */
var POP=null;
function art(id, cls){ return '<svg class="cr-art'+(cls ? ' '+cls : '')+'" viewBox="-44 -34 88 68" aria-hidden="true">'+BY[id].svg+'</svg>'; }
function close(){ if(POP){ POP.remove(); POP=null; } var b=document.getElementById('sol-craft'); if(b) b.setAttribute('aria-expanded', 'false'); }
function open(btn){
  if(POP){ close(); return; }
  var cid=cur(); POP=document.createElement('div'); POP.id='sol-craft-pop'; POP.setAttribute('role', 'dialog'); POP.setAttribute('aria-label', 'Choose your ship');
  POP.innerHTML='<div class="cr-h">Your ship</div>'+[['Real spacecraft', true], ['Science fiction', false]].filter(function(gp){ return C.some(function(c){ return c.real===gp[1]; }); }).map(function(gp){
    return '<div class="cr-g">'+gp[0]+'</div><div class="cr-row">'+C.filter(function(c){ return c.real===gp[1]; }).map(function(c){
      return '<button type="button" class="cr-t'+(c.id===cid ? ' on' : '')+'" data-craft="'+c.id+'" aria-pressed="'+(c.id===cid)+'" title="'+c.name+'">'+art(c.id)+'<span>'+c.name+'</span></button>'; }).join('')+'</div>'; }).join('');
  POP.addEventListener('click', function(e){ e.stopPropagation(); var b=e.target.closest && e.target.closest('[data-craft]'); if(!b) return; set(b.getAttribute('data-craft')); close(); });
  document.body.appendChild(POP);
  var r=btn.getBoundingClientRect(), z=parseFloat(getComputedStyle(de).zoom)||1;
  POP.style.left=Math.max(8, Math.min(window.innerWidth/z-POP.offsetWidth-8, r.left/z-20))+'px'; POP.style.bottom=(window.innerHeight/z-r.top/z+10)+'px';
  btn.setAttribute('aria-expanded', 'true');
  setTimeout(function(){ var b=POP && POP.querySelector('.cr-t.on'); if(b) b.focus(); }, 0);
}
/* (on the window, first: the 3D scene and the flights stop clicks and keys on their way to the document) */
window.addEventListener('pointerdown', function(e){ if(POP && !POP.contains(e.target) && !(e.target.closest && e.target.closest('#sol-craft'))) close(); }, true);
window.addEventListener('keydown', function(e){ if(POP && e.key==='Escape'){ e.preventDefault(); e.stopPropagation(); close(); var b=document.getElementById('sol-craft'); if(b) b.focus(); } }, true);
function set(id){ if(!BY[id]) return; MINE=id; try{ localStorage.setItem(KEY, id); }catch(e){} subs.forEach(function(f){ try{ f(id); }catch(x){} }); }
/* ── how a craft flies a way (solar_fly.py's flights, solar_draw.py's Spokes-only rides, solar_3d.py's model; Luke,
   2026-10-22: "it should come into a gentle orbit around planets ... always be sort of pointing accurately according to
   its line"). It never touches a body: it sets off from an orbit round the body it is at and comes into a gentle orbit
   round the one it goes to, at a radius by that body's size, and stays in it while that body is enlarged. Its nose is
   the way's own tangent; its bank, subtle, the way's turning. ── */
var ORB_W=.42, ORB=null;                 /* the settled orbit's pace (rad a second of the flight's clock); the orbit the craft is in */
function wrap(a){ return Math.atan2(Math.sin(a), Math.cos(a)); }
function ss(x){ x=Math.min(Math.max(x, 0), 1); return x*x*(3-2*x); }
/* a body's orbit radius by its diameter (+ px: the 2D art's own half length, its size on screen), within room (the
   gap to its parent's surface and its own moons' paths: a moon's orbit never reaches its planet, a planet's never
   crosses its moons) */
function orbitR(d, px, room){ var R=(+d||20)/2, r=R*1.4+10+(px||0); return room>0 ? Math.min(r, Math.max(R+4+(px||0)/2, room)) : r; }
/* o: base(t) the way (ending on the centre it goes to at o.D), cen(t) that centre, r the orbit's radius, D, spin, and
   start {p, v} where the craft is and how it moves (blended in over the first stretch). → at(t) and pv(t) the craft
   on the way and on in its orbit after D; off(t) the orbit's offset from the centre, after D. The way is bent only
   near its end: inside r it is held off the centre (the radius softened) and swung round it, the way it was turning,
   easing to the orbit's pace. (Bodies passed on the way: the 3D scene lifts the craft over them.) */
function track(o){
  var D=o.D, r=o.r, N=160, tb=null, tc=null, i, pr=null, t, q, m;
  function rel(t){ var p=o.base(t), c=o.cen(t); return [p[0]-c[0], p[1]-c[1]]; }
  function ang(t){ var q=rel(t); return Math.atan2(q[1], q[0]); }
  for(i=N;i>=0 && tb===null;i--){ t=D*i/N; q=rel(t); m=Math.hypot(q[0], q[1]);     /* (from the end back: the last times it is r, and .3 r, out) */
    if(tc===null && m>=.3*r) tc=pr ? t+(pr[0]-t)*(m-.3*r)/Math.max(1e-9, m-pr[1]) : t;
    if(m>=r) tb=pr ? t+(pr[0]-t)*(m-r)/Math.max(1e-9, m-pr[1]) : t;
    pr=[t, m]; }
  if(tc===null) tc=0; if(tb===null) tb=0; tb=Math.max(0, Math.min(tb, tc-.5)); tc=Math.max(tc, tb+.05);
  var Tb=tc-tb, th=ang(tc), h=.01, w0=wrap(ang(tb+h)-ang(Math.max(0, tb-h)))/(tb+h-Math.max(0, tb-h));
  var sg=Math.abs(w0)>1e-3 ? (w0>0 ? 1 : -1) : (o.spin<0 ? -1 : 1), Wi=sg*Math.min(1.4, Math.max(ORB_W, Math.abs(w0))), Wo=sg*ORB_W, Ts=1.4, t0w=Math.max(0, tb-1.2);
  function G(t){ if(t<=tb) return 0; if(t<=tc){ var x=(t-tb)/Tb; return Wi*Tb*(x*x*x-x*x*x*x/2); }
    var u=t-tc; return Wi*Tb/2+Wo*u+(Wi-Wo)*Ts*(1-Math.exp(-u/Ts)); }
  function raw(t){
    var p=o.base(t); if(t<=t0w) return p;
    var c=o.cen(t), q=[p[0]-c[0], p[1]-c[1]], m=Math.hypot(q[0], q[1]), a=Math.atan2(q[1], q[0]), wr=tb>t0w ? ss((t-t0w)/(tb-t0w)) : 1;
    if(t>=tc) a=th; else if(t>tb) a+=wrap(th-a)*ss((t-tb)/Tb);
    m+=(Math.sqrt(m*m+r*r)-m)*wr; a+=G(t);
    return [c[0]+m*Math.cos(a), c[1]+m*Math.sin(a)]; }
  var Tq=Math.min(.8, D/3), S=o.start, dp=null, dv=null;
  if(S && Tq>0){ var p0=raw(0), p1=raw(.004); dp=[S.p[0]-p0[0], S.p[1]-p0[1]]; dv=[S.v[0]-(p1[0]-p0[0])/.004, S.v[1]-(p1[1]-p0[1])/.004]; }
  function at(t){ var p=raw(t); if(dp && t<Tq){ var x=Math.max(0, t)/Tq, a=2*x*x*x-3*x*x+1, b=(x*x*x-2*x*x+x)*Tq; p=[p[0]+a*dp[0]+b*dv[0], p[1]+a*dp[1]+b*dv[1]]; } return p; }
  function pv(t){ var e=.008, a=at(Math.max(0, t-e)), b=at(t+e), k=t+e-Math.max(0, t-e); return [(a[0]+b[0])/2, (a[1]+b[1])/2, (b[0]-a[0])/k, (b[1]-a[1])/k]; }
  var qe=rel(D), me=Math.hypot(qe[0], qe[1]), re=Math.sqrt(me*me+r*r);
  function off(t){ var a=th+G(t); return [re*Math.cos(a), re*Math.sin(a)]; }
  return {at:at, pv:pv, off:off, D:D, r:r, sg:sg};
}
/* the orbit the craft is in after a landing (k: the flight's clock to real time); parked(id, centre) → where it is now
   and how it moves (px a second), or null */
function park(id, tr, k){ ORB={id:id, tr:tr, k:k||1, t0:performance.now()}; }
function parked(id, c){ if(!ORB || !c || (id && ORB.id!==id)) return null; var t=ORB.tr.D+(performance.now()-ORB.t0)/1000/ORB.k, a=ORB.tr.off(t), b=ORB.tr.off(t+.01);
  return {id:ORB.id, p:[c[0]+a[0], c[1]+a[1]], v:[(b[0]-a[0])/.01/ORB.k, (b[1]-a[1])/.01/ORB.k], r:ORB.tr.r, sg:ORB.tr.sg}; }
/* the nose on the way's tangent (v: its velocity) every frame, and the bank by how fast that tangent turns; only a jump
   (a new way from where it is) is eased round, never snapped. S keeps hs (heading), ht, bk. */
function steer(S, v, dt){
  var sp=Math.hypot(v[0], v[1]); if(sp<.5){ S.bk=(S.bk||0)*(1-Math.min(1, dt*3)); return S; }
  var h=Math.atan2(v[1], v[0]); if(S.hs==null){ S.hs=S.ht=h; S.bk=0; return S; }
  var dd=S.ht!=null ? wrap(h-S.ht) : 0, w=dt>0 ? dd/dt : 0, d=wrap(h-S.hs), on=S.ht!=null && Math.abs(wrap(S.hs-S.ht))<.05; S.ht=h;
  /* (on the tangent, it stays on it however fast the way turns between frames; a jump — the way turning on itself where
     the craft all but stops, a new way — comes round eased, keeping up with the turning) */
  S.hs=Math.abs(d)<.25 || (on && Math.abs(w)<15) ? h : S.hs+Math.max(-15, Math.min(15, w))*dt+d*Math.min(1, dt*8);
  S.bk=(S.bk||0)+(Math.max(-1, Math.min(1, w/2.4))*ss(sp/80)-(S.bk||0))*Math.min(1, dt*3);
  return S;
}
/* the art on the screen (k its scale): at p, its nose at h, narrowed a little across as it banks */
function xf(p, h, bk, k){ var c=BY[cur()], f=function(v){ return Math.round(v*100)/100; }; k=k||1;
  return 'translate('+f(p[0])+' '+f(p[1])+') rotate('+f((h||0)*180/Math.PI)+') scale('+k+' '+f(k*(1-(c.bank==null ? .3 : c.bank)*.5*Math.abs(bk||0)))+')'; }
/* a ride along a straight line (a spoke): from the orbit the craft is in round a (or that orbit's point on the line) into
   an orbit round z; a(), z() → [x, y, d] now; ez the ease; px the art's half length */
function line(from, a, z, D, ez, px, spin){ var A=a(), rA=orbitR(A[2], px), st=parked(from, A), tr=track({D:D, r:orbitR(z()[2], px), spin:spin, start:st,
    base:function(t){ var p=a(), q=z(), dx=q[0]-p[0], dy=q[1]-p[1], l=Math.hypot(dx, dy)||1, sx=p[0]+dx/l*rA, sy=p[1]+dy/l*rA, e=ez(Math.min(1, Math.max(0, t/D)));
      return [sx+(q[0]-sx)*e, sy+(q[1]-sy)*e]; }, cen:z});
  ORB=null; return tr; }
/* where a flight from a body (centre c) towards b sets off: the orbit the craft is in round it, else the point of an
   orbit of radius r from which going round it (the orbits' way) is going towards b; as [x, y, vx, vy], v by k */
function leave(id, c, b, r, spin, k){ var o=parked(id, c); if(o) return [o.p[0], o.p[1], o.v[0]*k, o.v[1]*k];
  var sg=spin<0 ? -1 : 1, a=Math.atan2(b[1]-c[1], b[0]-c[0])-sg*Math.PI/2, w=ORB_W*r*sg;
  return [c[0]+r*Math.cos(a), c[1]+r*Math.sin(a), -Math.sin(a)*w, Math.cos(a)*w]; }
/* ── a course charted the way a ship would (Luke, 2026-10-22: "the 3d star chart ship navigation to moons/other things
   orbiting planets looks really weird. Make it more accurate to how you would actually chart a course to a moon").
   Within one system, from the orbit the craft is in: a coast round it to where the burn is made, then a transfer arc
   (Hohmann-like: half an ellipse, tangent to the orbit it leaves and to the one it meets) in the frame of the body both
   go round, aimed where the body it goes to WILL be (it leads a moving moon), meeting it alongside: on its inner side
   when climbing (slower than it there), its outer side when falling (faster), so either way already going round it
   the orbits' way, and on round into a gentle orbit. A level down (a planet to its moon) it waits in its parking orbit
   for the window, the arc about half a turn; a level up (a moon to its planet) it burns from the moon's inner or outer
   side into an orbit round the planet; across (moon to moon, planet to planet) from the side facing the way it goes;
   deeper chains hop a level at a time, each hop ending in an orbit round the body it passes. Paced like a ship: off
   at its orbit's speed, faster nearer what it falls round, into the new orbit at that orbit's speed. o: W, F (the
   planner, solar_fly.py), R (its route: the bodies' clock, retimed here), opt (the plan's options, for the clock),
   from, to, rc(id) the orbit radius round a body, v0 the speed it sets off at. → a track (as track()), or null (to
   another system: the planner's way). ── */
var KEP=.5, CAP_PHI=.45*Math.PI, OMG=3.2, CLR=6, PH_MIN=.3*Math.PI;
function course(o){
  var W=o.W, F=o.F, R=o.R, B=W.B, s=W.spin<0 ? -1 : 1, PI=Math.PI, from=o.from, to=o.to;
  if(!B[from] || !B[to] || !F.clk || !F.dur) return null;
  function chain(i){ var c=[]; while(i){ c.push(i); i=B[i].p; } return c; }
  var ca=chain(from), cb=chain(to), L=null, i, j;
  if(ca[ca.length-1]!==cb[cb.length-1]) return null;
  for(i=0;i<ca.length;i++) if(cb.indexOf(ca[i])>=0){ L=ca[i]; break; }
  var ia=ca.indexOf(L), ib=cb.indexOf(L), steps=[];
  for(i=0;i+1<ia;i++) steps.push(['up', ca[i], ca[i+1]]);
  if(ia>=1) steps.push(ib>=1 ? ['across', ca[ia-1], cb[ib-1], L] : ['up', ca[ia-1], L]);
  else steps.push(['down', L, cb[ib-1]]);
  for(i=ib-1;i>=1;i--) steps.push(['down', cb[i], cb[i-1]]);
  function at(id, t){ return F.pos(W, id, F.clock(R, Math.min(Math.max(t, 0), R.D))); }
  function pol(p, c){ var x=p[0]-c[0], y=p[1]-c[1]; return [Math.hypot(x, y), Math.atan2(y, x)]; }
  function md(a){ return ((a%(2*PI))+2*PI)%(2*PI); }
  function half(r0, r1){ return PI*Math.min(1, Math.max(.4, 2*Math.abs(r1-r0)/Math.max(r0, r1, 1))); }   /* (a small change of orbit: a short arc) */
  function rr(g, u){ return g.r0===g.r1 ? g.r0 : 2*g.r0*g.r1/((g.r0+g.r1)-(g.r0-g.r1)*Math.cos(PI*u)); }
  function loc(g, u){ var r=rr(g, u), a=g.a0+s*g.phi*u; return [r*Math.cos(a), r*Math.sin(a)]; }
  var c0=at(from, 0), p0=pol(o.st, c0), G, tb=null, Q, D=R.D, qa, qb, Wt, it;
  /* the segments for the times tb (the previous pass's; none: even shares) */
  /* (the choices — a lap round or not, which way round — made on the first pass and kept: later passes only move the
     angles to the bodies' new times, each kept nearest its first value, so the segments and their times agree) */
  var MEM=[];
  function keep(i, nm, v){ var m=MEM[i]=MEM[i]||{}; if(m[nm]==null){ m[nm]=v; return v; } return m[nm]+wrap(v-m[nm]); }
  function build(){
    var g=[], X=from, rho=Math.max(1, p0[0]), th=p0[1], n=steps.length*2+1, k=0;
    function T(m){ return tb ? tb[Math.min(m, tb.length-1)] : D*m/n; }
    function seg(f, r0, r1, a0, phi, kind, dep, t0){ g.push({f:f, r0:r0, r1:r1, a0:a0, phi:phi, k:kind, dep:dep, td:t0}); k++; }
    steps.forEach(function(q, si){
      var x=q[1], td=T(k+1), ta=T(k+2), c, Y, ax, ay, dp, r1, ty, ph, f;
      if(q[0]==='down'){ Y=q[2]; ty=pol(at(Y, ta), at(x, ta)); ay=ty[0]; r1=ay+o.rc(Y);
        var dl=md(s*(ty[1]-th)), pw=half(rho, r1); c=md(dl-pw); ph=pw;
        if(c>1.25*PI && dl>.3*PI){ c=0; ph=dl; }
        var tot=keep(si, 'p', c+ph); c=Math.max(0, keep(si, 'c', c)); ph=tot-c; if(ph<.2*PI) ph+=2*PI;
        seg(x, rho, rho, th, c, 'coast'); seg(x, rho, r1, th+s*c, ph, 'xfer');
        X=Y; rho=o.rc(Y); th=ty[1]; return; }
      f=q[0]==='up' ? q[2] : q[3]; ax=pol(at(x, td), at(f, td));
      if(q[0]==='up') r1=o.rc(f); else { Y=q[2]; ty=pol(at(Y, ta), at(f, ta)); r1=ty[0]+o.rc(Y); }
      c=md(s*(ax[1]-th)); if(c>1.9*PI) c=0;          /* (just past the burn point: from here) */
      c=Math.max(0, keep(si, 'c', c));
      seg(x, rho, rho, th, c, 'coast');
      var xc=at(x, td), a=th+s*c; dp=pol([xc[0]+rho*Math.cos(a), xc[1]+rho*Math.sin(a)], at(f, td));
      if(q[0]==='up'){ ph=half(dp[0], r1); seg(f, dp[0], r1, dp[1], ph, 'xfer', x, td); X=f; rho=r1; th=dp[1]+s*ph; }
      else { ph=md(s*(ty[1]-dp[1])); if(ph<PH_MIN) ph+=2*PI; ph=keep(si, 'p', ph);         /* (too little ahead for an arc: the next window, a lap on) */ seg(f, dp[0], r1, dp[1], ph, 'xfer', x, td); X=Y; rho=o.rc(Y); th=ty[1]; } });
    seg(X, rho, rho, th, CAP_PHI, 'cap');
    /* each segment's length in its own frame, sampled, and how unhurried each stretch: slower far out on an arc, quicker
       deep in (KEP) */
    g.forEach(function(e){ var N=24, pr=loc(e, 0), len=0, m; e.ds=[0]; e.kp=[0];
      for(m=1;m<=N;m++){ var cu=loc(e, m/N), u=(m-.5)/N, ds=Math.hypot(cu[0]-pr[0], cu[1]-pr[1]); len+=ds; e.ds.push(ds);
        e.kp.push(Math.pow(rr(e, u)/(Math.pow(e.r0, 1-ss(u))*Math.pow(e.r1, ss(u))), KEP)); pr=cu; }
      e.len=len; });
    return g;
  }
  /* the time weights: round a small body unhurried, never whipping round (at about the flight's peak speed, vb, under
     OMG rad/s), the pace changing smoothly along the whole course (a gaussian shoulder over its length), so no join jolts */
  var vb=0;
  function weigh(g){
    var X=[], d=[], x=0, Lt=g.reduce(function(a, e){ return a+e.len; }, 0), sg=Math.min(120, 30+.03*Lt), i, k;
    g.forEach(function(e){ var f=Math.max(1, 1.6*vb/(OMG*(e.k==='xfer' ? 1 : 1.4)*Math.max(1, (e.r0+e.r1)/2)));      /* (an orbit's steady turn: a little brisker) */
      for(var m=1;m<e.ds.length;m++){ x+=e.ds[m]; X.push([x-e.ds[m]/2, e.ds[m]]); d.push(f*e.kp[m]); } });
    var sd=X.map(function(q, j){ var a=d[j], z;                  /* (a slow stretch eased into, never diluted; within 3 sigma) */
      for(k=j-1;k>=0 && (z=(q[0]-X[k][0])/sg)<3;k--) a=Math.max(a, 1+(d[k]-1)*Math.exp(-z*z/2));
      for(k=j+1;k<X.length && (z=(X[k][0]-q[0])/sg)<3;k++) a=Math.max(a, 1+(d[k]-1)*Math.exp(-z*z/2));
      return Math.max(1, a); });
    i=0; g.forEach(function(e){ var w=[0]; for(var m=1;m<e.ds.length;m++){ w.push(w[m-1]+e.ds[m]*sd[i]); i++; }
      var n=w.length-1; e.w=w[n]; e.tab=w.map(function(v){ return w[n]>1e-9 ? v/w[n] : 0; }); });
  }
  /* the ship's clock: progress q(x) — the flights' ease, with its ends tilted to the orbits' speeds (a, b) */
  var QT=null;
  function qf(x){ var y=1-x; return (F.ease(x)+qa*(1-y*y*y*y)/4+qb*x*x*x*x/4)/(1+(qa+qb)/4); }     /* (rising all the way: q'(0), q'(1) the a, b asked) */
  function qinv(v){ if(v<=0) return 0; if(v>=1) return 1; var lo=0, hi=200; while(hi-lo>1){ var m=(lo+hi)>>1; if(QT[m]<=v) lo=m; else hi=m; }
    var d=QT[hi]-QT[lo]; return (lo+(d>0 ? (v-QT[lo])/d : 0))/200; }
  for(it=0;it<3;it++){
    G=build(); var Lt=G.reduce(function(a, e){ return a+e.len; }, 0); vb=Lt/D; weigh(G); Wt=G.reduce(function(a, e){ return a+e.w; }, 0)||1;
    D=Math.min(F.dur(1e9), F.dur(.8*Lt)+.15*(Wt-Lt)/Math.max(1, vb)); R.D=D; R.c=F.clk(o.opt, D);      /* (by its length — its orbits and burns no slower than the old route — a little longer for the slow stretches) */
    var ge=G[G.length-1];
    var A0=Math.min(1.4, Math.max(0, (o.v0||0)*D/Wt)), B0=Math.min(1.4, ORB_W*ge.r0*D/Wt), k4=1+(A0+B0)/(4-A0-B0); qa=A0*k4; qb=B0*k4;
    QT=[]; for(j=0;j<=200;j++) QT.push(qf(j/200)); for(j=1;j<=200;j++) QT[j]=Math.max(QT[j], QT[j-1]);
    Q=[0]; G.forEach(function(e, m){ Q.push(Q[m]+e.w/Wt); }); Q[G.length]=1;
    tb=Q.map(function(v){ return D*qinv(v); });
  }
  G=build(); weigh(G);            /* (the last pass's segments on its own times) */
  var E=G.map(function(e, m){ e.t0=tb[m]; e.t1=tb[m+1]; e.q0=Q[m]; e.q1=Q[m+1]; return e; }).filter(function(e){ return e.t1-e.t0>1e-3; });
  function uOf(e, t){ var v=(qf(Math.min(Math.max(t/D, 0), 1))-e.q0)/Math.max(1e-9, e.q1-e.q0), T2=e.tab, N=T2.length-1, lo=0, hi=N;
    if(v<=0) return v*(1/N)/Math.max(1e-6, T2[1]); if(v>=1) return 1+(v-1)*(1/N)/Math.max(1e-6, 1-T2[N-1]);
    while(hi-lo>1){ var m=(lo+hi)>>1; if(T2[m]<=v) lo=m; else hi=m; } var d=T2[hi]-T2[lo]; return (lo+(d>0 ? (v-T2[lo])/d : 0))/N; }
  /* (an arc off a body that goes round its frame's centre sets off going round with it, then on its own: so the body it
     leaves never catches it up) */
  function on(e, t){ var c=at(e.f, t), u=uOf(e, t), q=loc(e, u);
    if(e.dep){ var d0=pol(at(e.dep, e.td), at(e.f, e.td)), d1=pol(at(e.dep, t), c), dl=wrap(d1[1]-d0[1])*(1-ss(u/.45)), cs=Math.cos(dl), sn=Math.sin(dl); q=[q[0]*cs-q[1]*sn, q[0]*sn+q[1]*cs]; }
    return [c[0]+q[0], c[1]+q[1]]; }
  var ge2=G[G.length-1], th9=ge2.a0+s*ge2.phi, r9=ge2.r0;
  function off(t){ var a=th9+s*ORB_W*(t-D); return [r9*Math.cos(a), r9*Math.sin(a)]; }
  /* clear of the planets it goes round on the way (a moon's arc could swing over its planet, a moon being only a little
     off it; arcs round a sun stay between the orbits they join): a soft barrier R+CLR out, the way bending round it (eased in from the start and out over the last
     orbit, which are as they are; bodies merely passed: the 3D scene lifts the craft over them) */
  var BIG=ca.concat(cb).filter(function(i, j, l){ return B[i].role==='planet' && i!==from && i!==to && l.indexOf(i)===j; }), tc9=E[E.length-1].t0;
  function clear(p, t){ var k=Math.min(ss(t/.3), 1-ss((t-tc9)/Math.max(.05, D-tc9))); if(k<=0) return p;
    BIG.forEach(function(i){ var c=at(i, t), dx=p[0]-c[0], dy=p[1]-c[1], d=Math.hypot(dx, dy), m=B[i].d/2+CLR, w=CLR*2;
      if(d>=m+w || d<1e-6) return; var x=(d-m)/w, g=x>=1 ? x : Math.exp(x-1), d2=d+(m+w*g-d)*k; p=[c[0]+dx/d*d2, c[1]+dy/d*d2]; });
    return p; }
  function at2(t){
    if(t>=D){ var c=at(to, D), q=off(t); return [c[0]+q[0], c[1]+q[1]]; }
    return clear(at3(t), t); }
  function at3(t){
    t=Math.max(0, t); for(var m=0;m<E.length-1 && t>E[m].t1;m++);
    var e=E[m], p=on(e, t), h, w, z;
    if(m+1<E.length){ h=e.h; if(t>e.t1-h){ w=ss((t-e.t1+h)/(2*h)); z=on(E[m+1], t); p=[p[0]+(z[0]-p[0])*w, p[1]+(z[1]-p[1])*w]; } }
    if(m>0){ h=E[m-1].h; if(t<e.t0+h){ w=ss((t-e.t0+h)/(2*h)); z=on(E[m-1], t); p=[z[0]+(p[0]-z[0])*w, z[1]+(p[1]-z[1])*w]; } }
    return p; }
  /* (each join blended over a moment: short where it turns tightly — the two ways part fast round a small orbit) */
  E.forEach(function(e, m){ var n=E[m+1]; if(!n) return; var v=Math.max(e.len/(e.t1-e.t0), n.len/(n.t1-n.t0), 1);
    e.h=Math.max(.01, Math.min(.15, .35*(e.t1-e.t0), .35*(n.t1-n.t0), .25*Math.min(e.r1, n.r0)/v)); });
  function pv(t){ var e=.008, a=at2(Math.max(0, t-e)), b=at2(t+e), k=t+e-Math.max(0, t-e); return [(a[0]+b[0])/2, (a[1]+b[1])/2, (b[0]-a[0])/k, (b[1]-a[1])/k]; }
  return {at:at2, pv:pv, off:off, D:D, r:r9, sg:s, segs:E.map(function(e){ return e.k+':'+e.f; })};
}
/* landed: draw(o, dt) the craft going on round its orbit for ms (as its art fades), unless stop() */
function coast(c, draw, ms, stop){ var t1=performance.now()+ms, lt=0;
  (function step(now){ var o=!stop() && now<t1 && ORB && parked(ORB.id, c()); if(!o) return; draw(o, lt ? Math.min(.05, (now-lt)/1000) : 0); lt=now; requestAnimationFrame(step); })(performance.now()); }
/* ── the craft's look in 3D, high definition (Luke, 2026-10-22): a physically based metal with real reflections of a
   starry sky and the sun, plated in panels with fine seams, glass, rows of lit windows, lights; materials in the
   colour's 4th value (0 plated hull, .3 glass, .6 hull with a row of windows, 1 light); WC: where the windows and the
   plates run round a disc (centre x, z, its radius, from height y) rather than along the hull ── */
var GL={vs:'attribute vec3 p,n;attribute vec4 k;uniform mat4 VP,M;varying vec3 Wp,Nw,Op;varying vec4 Kc;void main(){vec4 w=M*vec4(p,1.);Wp=w.xyz;Nw=(M*vec4(n,0.)).xyz;Op=p;Kc=k;gl_Position=VP*w;}',
  fs:'precision highp float;varying vec3 Wp,Nw,Op;varying vec4 Kc;uniform vec3 L,E;uniform vec4 WC;uniform float al;'+
  'float h1(vec2 q){return fract(sin(dot(q,vec2(127.1,311.7)))*43758.5453);}'+
  'vec3 env(vec3 d,vec3 l){float s=d.y*.5+.5;vec3 c=mix(vec3(.015,.02,.04),vec3(.08,.11,.2),s*s);c+=vec3(.35,.22,.5)*pow(max(dot(d,normalize(vec3(-.6,.3,-.7))),0.),3.)*.25;'+
  'return c+vec3(1.,.93,.82)*pow(max(dot(d,l),0.),300.)*8.+vec3(1.,.9,.8)*pow(max(dot(d,l),0.),12.)*.25;}'+
  'void main(){vec3 n=normalize(Nw),v=normalize(E-Wp);if(dot(n,v)<0.)n=-n;vec3 l=normalize(L-Wp),hv=normalize(l+v);float m=Kc.a;vec3 b=Kc.rgb;'+
  'if(m>.9){gl_FragColor=vec4(pow(b*1.25,vec3(.9))*al,al);return;}'+
  'bool gs=m>.2&&m<.4;vec3 an=abs(n);vec2 uv=an.y>an.x&&an.y>an.z?Op.xz:(an.x>an.z?Op.zy:Op.xy);'+
  'float rr=length(Op.xz-WC.xy),sau=step(rr,WC.z)*step(WC.w,Op.y);if(sau>.5)uv=vec2(atan(Op.z-WC.y,Op.x-WC.x)*rr,rr);'+
  'vec2 ce=uv/vec2(3.4,2.1),f=fract(ce);float ln=smoothstep(0.,.025,f.x)*smoothstep(0.,.025,1.-f.x)*smoothstep(0.,.035,f.y)*smoothstep(0.,.035,1.-f.y);'+
  'vec2 c2=uv/vec2(6.8,4.2);float tone=.84+.24*h1(floor(c2))+.06*h1(floor(ce)+3.);if(!gs)b*=mix(.8,1.,ln)*tone;'+
  'float ro=gs?.08:mix(.5,.32,h1(floor(c2)+7.)),me=gs?0.:.45,NL=max(dot(n,l),0.),NV=max(dot(n,v),.001),NH=max(dot(n,hv),0.),a2=pow(ro,4.);'+
  'float D=a2/(3.14159*pow(NH*NH*(a2-1.)+1.,2.)),kk=pow(ro+1.,2.)/8.,G=NL/(NL*(1.-kk)+kk)*NV/(NV*(1.-kk)+kk);'+
  'vec3 F0=mix(vec3(.04),b,me),F=F0+(1.-F0)*pow(1.-max(dot(hv,v),0.),5.);vec3 col=((1.-F)*(1.-me)*b/3.14159+D*G*F/(4.*NL*NV+.001))*NL*vec3(1.,.96,.9)*5.2;'+
  'vec3 r=reflect(-v,n),Fr=F0+(1.-F0)*pow(1.-NV,5.);col+=b*env(n,l)*(1.-me)*.55+env(r,l)*Fr*mix(.3,1.2,1.-ro);'+
  'col+=b*vec3(.2,.26,.42)*max(dot(n,normalize(vec3(.2,-.6,.5))),0.)*.22;col*=.72+.28*smoothstep(-1.,.6,n.y);'+
  'if(m>.5&&m<.7){float t=sau>.5?atan(Op.z-WC.y,Op.x-WC.x)*rr:Op.x;float w=step(.6,fract(t*2.1))*step(fract(t*2.1),.84);col=mix(col,vec3(1.,.86,.62)*1.3,w*.85);}'+
  'col*=1.15;col=col*(2.51*col+.03)/(col*(2.43*col+.59)+.14);gl_FragColor=vec4(pow(col,vec3(1./2.2))*al,al);}'};
window._altoCraft={list:C, gl:GL, id:cur, get:function(){ return BY[cur()]; }, svg:function(id){ return BY[id||cur()].svg; }, art:art, mesh:mesh, kit:kit, set:set, open:open, close:close,
  chosen:function(){ return pick(); }, onChange:function(f){ subs.push(f); },
  track:track, orbitR:orbitR, park:park, parked:parked, unpark:function(){ ORB=null; }, orbiting:function(){ return ORB && ORB.id; }, steer:steer, W:ORB_W,
  xf:xf, line:line, leave:leave, coast:coast, course:course};
})();
"""

CRAFT_CSS = r"""
  /* the flying art is small (solar_fly.py SHIP / SHIP_RETRO, 0.4-0.5): its lines drawn twice as thick so they stay clear
     (not vector-effect: non-scaling strokes cost a recalculation every frame the camera moves) */
  :is(.sol-ship,.fly-ship) :is(.sh-hull,.sh-fin,.sh-gold,.sh-ring){stroke-width:1.8px !important;} :is(.sol-ship,.fly-ship) .sh-near{stroke-width:2.4px !important;}
  /* the Retro drawing's own deco details (the flat top-down drawing's gold sunburst and lines), Retro only */
  .sh-ro{display:none;} html.sk-retro :is(.sol-ship,.fly-ship,.cr-art) .sh-ro{display:inline;}
  /* Classic (and the 3D style's 2D pieces): the craft clean and light; Retro keeps solar_draw.py's gold on black */
  html:not(.sk-retro) :is(.sol-ship,.fly-ship,.cr-art) .sh-hull{fill:#e8ecf5;stroke:#27304c;stroke-width:.9;stroke-linejoin:round;}
  html:not(.sk-retro) :is(.sol-ship,.fly-ship,.cr-art) .sh-deck{fill:#aeb9d2;stroke:none;}
  html:not(.sk-retro) :is(.sol-ship,.fly-ship,.cr-art) .sh-fin{fill:#353d5a;stroke:#27304c;stroke-width:.8;stroke-linejoin:round;}
  html:not(.sk-retro) :is(.sol-ship,.fly-ship,.cr-art) .sh-gold{fill:none;stroke:#6f7fb8;stroke-width:.8;}
  html:not(.sk-retro) :is(.sol-ship,.fly-ship,.cr-art) .sh-eng{fill:#d8ecff;}
  html:not(.sk-retro) :is(.sol-ship,.fly-ship,.cr-art) .sh-glow{fill:#9fd0ff;fill-opacity:.38;}
  html:not(.sk-retro) :is(.sol-ship,.fly-ship,.cr-art) .sh-ring{fill:none;stroke:#8fa2d6;stroke-width:1.1;stroke-opacity:.7;}
  .cr-art .sh-hull{fill:#14161c;stroke:#d9ae55;stroke-width:.9;stroke-linejoin:round;} .cr-art .sh-deck{fill:#262a33;}
  .cr-art .sh-fin{fill:#0c0e12;stroke:#d9ae55;stroke-width:.8;stroke-linejoin:round;} .cr-art .sh-gold{fill:none;stroke:#d9ae55;stroke-width:.7;}
  .cr-art .sh-eng{fill:#ffe6a8;} .cr-art .sh-glow{fill:#ffd27a;fill-opacity:.3;} .cr-art .sh-ring{fill:none;stroke:#d9ae55;stroke-width:1.1;stroke-opacity:.55;}
  #sol-craft{display:inline-flex;align-items:center;gap:7px;}
  #sol-craft .cr-art{width:34px;height:26px;flex:none;}
  #sol-craft-pop{position:fixed;z-index:330;padding:12px 14px 14px;border-radius:16px;max-width:min(560px,calc(100vw - 16px));box-sizing:border-box;
    background:rgba(10,13,28,.9);-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);border:1px solid rgba(170,190,255,.28);color:#eef2ff;
    box-shadow:0 18px 50px rgba(0,0,0,.5);font:500 12px/1.3 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}
  html.sk-retro #sol-craft-pop{background:rgba(8,10,16,.94);border-color:rgba(217,174,85,.55);color:#f3e6c4;}
  #sol-craft-pop .cr-h{font-weight:700;font-size:13px;letter-spacing:.04em;margin:0 2px 8px;}
  #sol-craft-pop .cr-g{font-size:10px;letter-spacing:.14em;text-transform:uppercase;opacity:.7;margin:8px 2px 6px;}
  #sol-craft-pop .cr-row{display:flex;flex-wrap:wrap;gap:8px;}
  #sol-craft-pop .cr-t{display:flex;flex-direction:column;align-items:center;gap:4px;width:98px;padding:8px 4px 7px;border-radius:12px;cursor:pointer;
    background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);color:inherit;font:inherit;}
  #sol-craft-pop .cr-t:hover{background:rgba(255,255,255,.1);}
  #sol-craft-pop .cr-t.on{border-color:#9fb4ff;background:rgba(120,150,255,.18);box-shadow:0 0 0 1px #9fb4ff inset;}
  html.sk-retro #sol-craft-pop .cr-t.on{border-color:#d9ae55;background:rgba(217,174,85,.14);box-shadow:0 0 0 1px #d9ae55 inset;}
  #sol-craft-pop .cr-art{width:84px;height:62px;}
  #sol-craft-pop .cr-t span{text-align:center;white-space:nowrap;}
"""

from .solar_draw import _slim  # noqa: E402

CRAFT_JS = _slim(CRAFT_JS)
CRAFT_CSS = _slim(CRAFT_CSS)
