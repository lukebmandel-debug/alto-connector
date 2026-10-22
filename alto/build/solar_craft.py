"""The craft that fly you between bodies on a Star chart (Luke, 2026-10-21: "i want a real ship, give users choice
ships/crafts, some from sci fi, others from real life. Same options should apply to star chart classic/retro").

One choice per viewer (localStorage alto-ship, every timeline); none chosen, Retro flies its Imperial vessel and the
other styles the Space Shuttle. Each craft is:
  * 2D art (top view, nose along +x, about 70 px long) in the Imperial vessel's classes (sh-hull, sh-deck, sh-fin,
    sh-gold, sh-eng, sh-glow, sh-ring): Retro paints them gold on black, Classic clean light grey (CRAFT_CSS); the
    flights (solar_fly.py) and the Spokes-only rider (solar_draw.py) draw it;
  * a low-poly 3D model built in code (lathes, boxes, slabs: no asset to load) that solar_3d.py lights and flies;
  * its own motion: k the flight's clock (a probe drifts, a fighter darts), turn how fast its heading comes round,
    bank how far it rolls into a turn, spin (the saucer) and roll (the probe), its engines' glow and trail.
The real craft are simple, recognisable models of public designs; the science-fiction ones are original designs in
familiar archetypes, under names of our own. The picker (window._altoCraft.open) is a pop-over from the chart's
controls. System pages only.
"""

CRAFT_JS = r"""
(function(){
'use strict';
var de=document.documentElement, TAU=Math.PI*2, KEY='alto-ship', subs=[];
var C=[
  {id:'shuttle', name:'Space Shuttle', real:true, k:1.05, turn:2.2, bank:.45, glow:[1, .8, .55], trail:[1, .86, .7], eng:[[-29, 1.5, 0], [-29, -1, -2.2], [-29, -1, 2.2]],
   svg:'<ellipse class="sh-glow" cx="-31" cy="0" rx="6" ry="5"/>'+
     '<path class="sh-hull" d="M14 -4 L-6 -9 L-18 -21 L-26 -21 L-26 -4 Z M14 4 L-6 9 L-18 21 L-26 21 L-26 4 Z"/>'+
     '<path class="sh-fin" d="M14 -4 L-6 -9 L-18 -21 L-19.5 -21 L-7.5 -10.4 L12 -5 Z M14 4 L-6 9 L-18 21 L-19.5 21 L-7.5 10.4 L12 5 Z"/>'+
     '<path class="sh-hull" d="M34 0 L28 -3 L18 -5 L-26 -5 L-28 -3.5 L-28 3.5 L-26 5 L18 5 L28 3 Z"/>'+
     '<path class="sh-deck" d="M14 -3.4 L-22 -3.4 L-22 3.4 L14 3.4 Z"/><path class="sh-fin" d="M34 0 L29.5 -2.6 L29.5 2.6 Z"/>'+
     '<path class="sh-gold" d="M14 0 L-22 0"/><circle class="sh-eng" cx="-28.6" cy="0" r="1.1"/><circle class="sh-eng" cx="-28.6" cy="-2.6" r="1"/><circle class="sh-eng" cx="-28.6" cy="2.6" r="1"/>',
   build:function(g){ var W=[.93, .93, .91], D=[.09, .09, .1];
     g.lathe([[34, 0], [31, 2.6], [26, 4.2], [18, 5], [-26, 5], [-28, 4], [-28, 0]], 14, W);
     g.lathe([[34.2, 0], [31.2, 2.7], [29.6, 3.5]], 14, D);
     [1, -1].forEach(function(s){ g.slab([[14, 4*s], [-6, 9*s], [-18, 21*s], [-26, 21*s], [-26, 4*s]], -2.4, .7, W); g.slab([[14, 4*s], [-6, 9*s], [-18, 21*s], [-26, 21*s], [-26, 4*s]], -3.1, .7, D);
       g.box([-21, 2.2, 3.6*s], [10, 3, 2.6], W); });
     g.vslab([[-14, 4], [-24, 17], [-28.5, 17], [-28, 4]], 0, 1.1, W);
     g.box([-4, 5, 0], [36, .3, .4], [.55, .56, .6]); }},
  {id:'apollo', name:'Apollo CSM', real:true, k:1.1, turn:2, bank:.2, glow:[1, .74, .42], trail:[1, .8, .6], eng:[[-31, 0, 0]],
   svg:'<ellipse class="sh-glow" cx="-34" cy="0" rx="7" ry="3"/>'+
     '<path class="sh-fin" d="M-22 -3 L-31 -6.5 L-31 6.5 L-22 3 Z"/>'+
     '<path class="sh-hull" d="M-22 -8 L4 -8 L4 8 L-22 8 Z"/><path class="sh-hull" d="M4 -8 L20 -2 L22 0 L20 2 L4 8 Z"/>'+
     '<path class="sh-deck" d="M-12 -8 L-4 -8 L-4 8 L-12 8 Z"/>'+
     '<path class="sh-gold" d="M-6 -8 L-6 8 M-14 -8 L-14 8 M-18 8 L-18 13 M-20.5 13 L-15.5 13"/><circle class="sh-eng" cx="-31.4" cy="0" r="1.5"/>',
   build:function(g){ var S=[.84, .86, .9];
     g.lathe([[18, 0], [17.6, 1.4], [4, 7.6], [3.6, 7.8], [3.2, 7.6]], 22, S);
     g.lathe([[3.2, 7.4], [-22, 7.4], [-22, 0]], 22, [.72, .74, .78]);
     g.lathe([[-10, 7.5], [-14, 7.5]], 22, [.5, .52, .56]);
     g.lathe([[-22, 2.8], [-31, 5.8]], 18, [.34, .32, .3]);
     g.box([-18, 0, 9.6], [.8, .8, 5], [.6, .6, .62]); g.lathe([[0, 0], [-1, 2.6]], 12, [.95, .95, .95], [-18, 0, 13]);
     [[0, 7.9], [0, -7.9]].forEach(function(q){ g.box([-2, q[0], q[1]], [2, 1.4, 1.4], [.55, .55, .58]); g.box([-2, q[1], q[0]], [2, 1.4, 1.4], [.55, .55, .58]); }); }},
  {id:'soyuz', name:'Soyuz', real:true, k:1.1, turn:2, bank:.2, glow:[1, .7, .4], trail:[1, .8, .6], eng:[[-30.5, 0, 0]],
   svg:'<ellipse class="sh-glow" cx="-33" cy="0" rx="6" ry="3"/>'+
     '<path class="sh-fin" d="M-13 -6.5 L-21 -6.5 L-21 -31 L-13 -31 Z M-13 6.5 L-21 6.5 L-21 31 L-13 31 Z"/>'+
     '<path class="sh-gold" d="M-17 -9 L-17 -29 M-17 9 L-17 29 M-13 -19 L-21 -19 M-13 19 L-21 19 M20 0 L26 0"/>'+
     '<path class="sh-hull" d="M-8 -6.5 L-28 -6.5 L-30 -5 L-30 5 L-28 6.5 L-8 6.5 Z"/>'+
     '<path class="sh-deck" d="M-8 -6.5 L4 -5 L6 -3 L6 3 L4 5 L-8 6.5 Z"/><circle class="sh-hull" cx="13" cy="0" r="7"/><circle class="sh-eng" cx="-30.4" cy="0" r="1.3"/>',
   build:function(g){ var sp=[], i; for(i=0;i<=10;i++){ var a=Math.PI*i/10; sp.push([13+6.8*Math.cos(a), 6.8*Math.sin(a)]); }
     g.lathe(sp, 18, [.55, .6, .46]);
     g.lathe([[6.5, 3], [4, 5.6], [-8, 6.6], [-8, 0]], 18, [.5, .52, .42]);
     g.lathe([[-8, 6.2], [-28, 6.2], [-30, 4.4], [-30, 0]], 18, [.64, .66, .68]);
     g.lathe([[22, 0], [19.5, .7]], 8, [.7, .7, .7]);
     [1, -1].forEach(function(s){ g.slab([[-13, 6.5*s], [-21, 6.5*s], [-21, 31*s], [-13, 31*s]], 0, .5, [.13, .2, .45]); g.box([-17, 0, 18.75*s], [.6, .7, 24.5], [.75, .62, .3]); }); }},
  {id:'voyager', name:'Voyager', real:true, k:1.35, turn:.9, bank:0, roll:.35, glow:[.75, .85, 1], trail:[.8, .88, 1], eng:[[-9.5, 0, 0]],
   svg:'<circle class="sh-glow" cx="-6" cy="0" r="5"/>'+
     '<path class="sh-gold" d="M2 0 L-36 -13 M-4 0 L-10 20 M-4 0 L-8 -18"/>'+
     '<rect class="sh-fin" x="-13" y="19" width="6" height="6"/><rect class="sh-fin" x="-11" y="-21" width="5" height="4"/>'+
     '<circle class="sh-hull" cx="8" cy="0" r="14"/><circle class="sh-ring sh-near" cx="8" cy="0" r="8.5"/><circle class="sh-deck" cx="-3" cy="0" r="5.5"/>'+
     '<path class="sh-gold" d="M8 0 L20 0"/>',
   build:function(g){ g.lathe([[0, 0], [-1.8, 5], [-3.2, 10], [-4.2, 14]], 26, [.92, .92, .9], [8, 0, 0]);
     g.lathe([[0, 0], [10, .4]], 6, [.7, .7, .7], [8, 0, 0]);
     g.lathe([[-3, 0], [-3, 5.4], [-9, 5.4], [-9, 0]], 10, [.66, .55, .32]);
     g.box([-26, 0, -6], [30, .45, .45], [.8, .8, .8]);
     g.box([-7, 0, 13], [.7, .7, 18], [.5, .5, .52]); g.box([-7, 0, 23.5], [3, 3, 5.5], [.22, .22, .24]);
     g.box([-7, 0, -11], [.7, .7, 15], [.5, .5, .52]); g.box([-7, 0, -19.5], [4, 3, 4], [.3, .3, .32]); }},
  {id:'starship', name:'Starship', real:true, k:1, turn:2, bank:.25, glow:[.65, .78, 1], trail:[.75, .85, 1], eng:[[-33, 0, -2.4], [-33, 0, 2.4], [-33, 2.2, 0]],
   svg:'<ellipse class="sh-glow" cx="-35" cy="0" rx="6" ry="5"/>'+
     '<path class="sh-fin" d="M22 -6 L16 -11.5 L10 -11.5 L12 -6 Z M22 6 L16 11.5 L10 11.5 L12 6 Z M-18 -6 L-24 -14.5 L-32 -14.5 L-30 -6 Z M-18 6 L-24 14.5 L-32 14.5 L-30 6 Z"/>'+
     '<path class="sh-hull" d="M36 0 L32 -4 L24 -6 L-30 -6 L-32 -5 L-32 5 L-30 6 L24 6 L32 4 Z"/>'+
     '<path class="sh-gold" d="M10 -6 L10 6 M-6 -6 L-6 6 M-22 -6 L-22 6"/><circle class="sh-eng" cx="-32.4" cy="-2.4" r="1.2"/><circle class="sh-eng" cx="-32.4" cy="2.4" r="1.2"/>',
   build:function(g){ var F=[.2, .2, .22];
     g.lathe([[36, 0], [34, 2.8], [30, 4.8], [24, 6], [-32, 6], [-32, 0]], 20, [.74, .76, .8]);
     g.lathe([[2, 6.05], [-30, 6.05]], 20, [.7, .72, .76]);
     [1, -1].forEach(function(s){ g.slab([[22, 5.5*s], [16, 11.5*s], [10, 11.5*s], [12, 5.5*s]], 0, .6, F); g.slab([[-18, 5.5*s], [-24, 14.5*s], [-32, 14.5*s], [-30, 5.5*s]], 0, .6, F); }); }},
  {id:'imperial', name:'Imperial Vessel', real:false, k:1, turn:2.4, bank:.3, glow:[1, .84, .5], trail:[1, .82, .45], eng:[[-31, 0, 0]],
   svg:'<ellipse class="sh-glow" cx="-33" cy="0" rx="10" ry="3.2"/>'+
     '<ellipse class="sh-ring" cx="-8" cy="0" rx="2.6" ry="10.5"/>'+
     '<path class="sh-fin" d="M-17 -3.6 L-27 -8.4 L-31.5 -8.4 L-28.5 -3 Z M-17 3.6 L-27 8.4 L-31.5 8.4 L-28.5 3 Z"/>'+
     '<path class="sh-hull" d="M37 0 L18 -2.1 L-6 -3.7 L-24 -3.7 L-30 -1.9 L-30 1.9 L-24 3.7 L-6 3.7 L18 2.1 Z"/>'+
     '<path class="sh-deck" d="M16 0 L-4 -1.8 L-22 -1.8 L-22 1.8 L-4 1.8 Z"/>'+
     '<path class="sh-gold" d="M34 0 L-27 0 M14 -2.3 L14 2.3 M-20 -3.7 L-20 3.7"/>'+
     '<path class="sh-ring sh-near" d="M-8 -10.5 A2.6 10.5 0 0 1 -8 10.5"/>'+
     '<circle class="sh-eng" cx="-30.6" cy="0" r="1.5"/>',
   build:function(g){ var H=[.11, .12, .15], G=[.86, .68, .33];
     g.lathe([[37, 0], [18, 2.6], [-6, 4.4], [-24, 4.4], [-30, 2.2], [-30, 0]], 6, H);
     g.box([4, 3.9, 0], [52, .5, 1.1], G); g.box([14, 0, 0], [.8, 5.4, 5.4], G);
     g.lathe([[-9, 10.2], [-7, 10.2], [-7, 11.4], [-9, 11.4], [-9, 10.2]], 40, G);
     g.box([-8, 0, 0], [1, 21, 1.2], G); g.box([-8, 0, 0], [1, 1.2, 21], G);
     [1, -1].forEach(function(s){ g.slab([[-17, 3.6*s], [-27, 8.4*s], [-31.5, 8.4*s], [-28.5, 3*s]], 0, .8, H); }); }},
  {id:'dart', name:'Dart', real:false, k:.85, turn:4, bank:.6, glow:[.55, .75, 1], trail:[.6, .8, 1], eng:[[-28, 0, -2.6], [-28, 0, 2.6]], lights:[[-25, 0, -19, 1, .2, .15], [-25, 0, 19, .2, 1, .4]],
   svg:'<ellipse class="sh-glow" cx="-31" cy="-2.6" rx="6" ry="2"/><ellipse class="sh-glow" cx="-31" cy="2.6" rx="6" ry="2"/>'+
     '<path class="sh-fin" d="M6 -3 L-22 -19 L-27 -19 L-20 -4 Z M6 3 L-22 19 L-27 19 L-20 4 Z"/>'+
     '<path class="sh-hull" d="M36 0 L14 -2.6 L-20 -5 L-27 -4 L-27 4 L-20 5 L14 2.6 Z"/>'+
     '<path class="sh-deck" d="M18 0 L8 -1.8 L0 -1.8 L0 1.8 L8 1.8 Z"/>'+
     '<path class="sh-gold" d="M30 0 L-24 0 M-12 -11 L-20 -17 M-12 11 L-20 17"/><circle class="sh-eng" cx="-27.6" cy="-2.6" r="1.3"/><circle class="sh-eng" cx="-27.6" cy="2.6" r="1.3"/>',
   build:function(g){ g.lathe([[36, 0], [22, 2.4], [4, 3.6], [-20, 4.2], [-27, 3.6], [-27, 0]], 8, [.8, .82, .88]);
     g.lathe([[8, 0], [4, 1.7], [-4, 1.7], [-8, 0]], 8, [.16, .28, .45], [12, 2.7, 0]);
     [1, -1].forEach(function(s){ g.slab([[6, 3*s], [-22, 19*s], [-27, 19*s], [-20, 4*s]], 0, .8, [.6, .62, .7]); g.vslab([[-14, 3], [-25, 10], [-28.5, 10], [-25, 3]], 4*s, .7, [.52, .54, .62]); }); }},
  {id:'bastion', name:'Bastion', real:false, k:1.25, turn:1.5, bank:.12, glow:[.6, .8, 1], trail:[.65, .82, 1], eng:[[-35, 0, -6], [-35, 0, 0], [-35, 0, 6]],
   svg:'<ellipse class="sh-glow" cx="-37" cy="-6" rx="5" ry="2"/><ellipse class="sh-glow" cx="-37" cy="0" rx="5" ry="2"/><ellipse class="sh-glow" cx="-37" cy="6" rx="5" ry="2"/>'+
     '<path class="sh-hull" d="M30 -3 L36 0 L30 3 L22 9.5 L-30 9.5 L-34 6.5 L-34 -6.5 L-30 -9.5 L22 -9.5 Z"/>'+
     '<path class="sh-deck" d="M18 -5.5 L-24 -5.5 L-24 5.5 L18 5.5 Z"/><path class="sh-fin" d="M-8 -3 L-20 -3 L-20 3 L-8 3 Z"/>'+
     '<path class="sh-gold" d="M30 0 L-30 0 M10 -9.5 L10 9.5 M-10 -9.5 L-10 9.5 M22 -9.5 L22 9.5"/>'+
     '<circle class="sh-eng" cx="-34.5" cy="-6" r="1.4"/><circle class="sh-eng" cx="-34.5" cy="0" r="1.4"/><circle class="sh-eng" cx="-34.5" cy="6" r="1.4"/>',
   build:function(g){ var A=[.34, .36, .41], B=[.44, .46, .52];
     g.box([-2, 0, 0], [60, 8, 19], A); g.slab([[28, -9.5], [36, 0], [28, 9.5]], 0, 8, A);
     g.box([-4, 5.5, 0], [42, 3, 11], B); g.box([-14, 9, 0], [12, 5, 6], [.52, .54, .6]);
     g.box([0, -5.5, 0], [44, 3, 8], [.26, .27, .31]);
     [1, -1].forEach(function(s){ g.box([-6, 5.5, 5.6*s], [36, .6, .25], [1, .85, .55, 1]); g.box([-2, 0, 9.6*s], [50, .5, .25], [.9, .78, .5, 1]); g.box([-31, 0, 6*s], [7, 6, 5], B); });
     g.box([-31, 0, 0], [7, 6, 5], B); g.box([-14, 11.6, 0], [3, .5, 5], [.75, .9, 1, 1]); }},
  {id:'halo', name:'Halo', real:false, k:1, turn:3, bank:0, spin:.6, glow:[.55, .85, 1], trail:[.6, .9, 1], eng:[[0, -2.8, 0]],
   svg:'<circle class="sh-glow" cx="0" cy="0" r="24"/><circle class="sh-ring" cx="0" cy="0" r="22"/><circle class="sh-hull" cx="0" cy="0" r="20"/>'+
     '<circle class="sh-gold" cx="0" cy="0" r="14.5"/><circle class="sh-deck" cx="0" cy="0" r="8.5"/><path class="sh-gold" d="M9 0 L19 0"/>'+
     '<g class="sh-spin"><circle class="sh-eng" cx="17.5" cy="0" r="1.2"/><circle class="sh-eng" cx="-17.5" cy="0" r="1.2"/><circle class="sh-eng" cx="0" cy="17.5" r="1.2"/><circle class="sh-eng" cx="0" cy="-17.5" r="1.2"/>'+
     '<circle class="sh-eng" cx="12.4" cy="12.4" r="1"/><circle class="sh-eng" cx="-12.4" cy="12.4" r="1"/><circle class="sh-eng" cx="12.4" cy="-12.4" r="1"/><circle class="sh-eng" cx="-12.4" cy="-12.4" r="1"/></g>',
   build:function(g){ g.lathe([[2.6, 0], [2.6, 6], [1.3, 15], [0, 22], [-1.2, 16], [-2.3, 8], [-2.3, 0]], 36, [.72, .74, .8], null, 1);
     g.lathe([[2.6, 8.5], [5.2, 6.5], [7.2, 3.6], [8, 0]], 24, [.34, .55, .78], null, 1);
     for(var i=0;i<12;i++){ var a=i/12*TAU; g.box([Math.cos(a)*20.6, 0, Math.sin(a)*20.6], [1.4, .9, 1.4], [.6, .92, 1, 1]); } }}
];
var BY={}; C.forEach(function(c){ BY[c.id]=c; });
var MINE;                                           /* (read once: a flight asks every frame, and WebKit's storage is a round trip) */
function pick(){ if(MINE===undefined){ var v=null; try{ v=localStorage.getItem(KEY); }catch(e){} MINE=v && BY[v] ? v : null; } return MINE; }
window.addEventListener('storage', function(e){ if(e.key===KEY){ MINE=undefined; subs.forEach(function(f){ try{ f(cur()); }catch(x){} }); } });
function cur(){ return pick() || (de.classList.contains('sk-retro') ? 'imperial' : 'shuttle'); }
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
  POP.innerHTML='<div class="cr-h">Your ship</div>'+[['Real spacecraft', true], ['Science fiction', false]].map(function(gp){
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
window._altoCraft={list:C, id:cur, get:function(){ return BY[cur()]; }, svg:function(id){ return BY[id||cur()].svg; }, art:art, mesh:mesh, set:set, open:open, close:close,
  chosen:function(){ return pick(); }, onChange:function(f){ subs.push(f); }};
window._altoSolarShip=BY.imperial.svg;      /* (the name 1.9.132's Retro read: the Imperial vessel) */
})();
"""

CRAFT_CSS = r"""
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
