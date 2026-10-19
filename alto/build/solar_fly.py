"""Flying between bodies on a Star chart (the moving look of a Hub & spoke page).

Luke (spec round 4, item 4): going to another body goes the way a spacecraft
would — a lunar injection to a moon, a Hohmann-style transfer to the next
planet, gravity assists round planets on the way out of a system. Changing the
enlarged body (arrows, clicks, search hits — anything through enterFocus) flies
a small craft there along such a route, the camera following, the orbits
moving on the flight's own clock so it meets the body where it really is; on
arrival the body is enlarged exactly as before and the orbits stand still.

THE PLANNER (FLY_PLAN_JS: window._altoFly; tests/solar_fly_twin.py is its
Python twin, held equal under node by tests/test_solar_fly.py) is pure: the
solar plan (window._ALTO_SOLAR), from, to, the bodies' clock now and its rate
→ a route. Bodies move as solar_draw.py moves them: a body at angle
spin·2πT/period (plus each system's slow turn when there are several) round
its parent's current place. The route's legs each are a curve in the frame of
one body (or the fixed frame), flown one after another along one progress
s = E(τ/D) — E the incomplete-beta curve family of the engine's _altoEase,
D clamped to 2.5–7 s by the route's length — each leg at an even pace along
its curve (shares of s by length). The bodies' clock is the flight's own:
from its rate at take-off up to full speed, and down to rest over the last
second, so the craft and the body it lands on arrive together and at rest.
Each leg that ends on a body ends where that body will be at that moment, so
the arrival is exact; the joins are made C1 by a cubic Hermite term that takes
in the incoming velocity over the first BLEND of the next leg.

Routing rules (chains: sat → moon → planet → sun):
* the same body: no flight.
* down from a body to one of its own (planet → its moon, sun → planet, moon
  → its satellite): a PARKING spiral just outside the body, then an
  INJECTION conic out to the child's orbit, arriving where the child will be
  (a lunar injection); a child nearer than HOP_R: one short HOP leg.
* up to an ancestor (moon → its planet, planet → its sun): an ARRIVAL spiral
  in to it (ret).
* across a common parent L (siblings, cousins): if A is below L's child A',
  an ESCAPE spiral out of A'’s family, leaving towards where it is going;
  then a TRANSFER conic round L from A'’s orbit to B'’s (Hohmann-like — a
  half ellipse when the window is right; a PHASING arc, out and back, when the
  two share a ring), turning the orbits' way; between planets FAR_RINGS or
  more rings apart a GRAVITY ASSIST on the way at the planet between that
  turns the craft least.
* down B's chain from B' to B: each level a CAPTURE conic from the point of
  the body's reach where going round it is going the way the craft arrives
  (so it turns straight on), to the next body down.
* to another system: an escape spiral out of A's planet's family (none from
  a sun), 1–3 GRAVITY ASSISTS round planets of the home system — each farther
  out than the last, lying toward the other system, and no lap of the system
  between them (hyperbolic flybys, turning TURN), an ESCAPE / cruise curve to
  the other system's edge, met on its near side where the capture turns about
  half an orbit to B's planet, then the captures down to B.
* the launch window: the transfers turn the orbits' way only (a target just
  behind is reached by a lap, as a phasing orbit would); a short COAST is
  added when it brings the transfers nearer a half orbit.

THE CAMERA keys frame the stretch of flight ahead (and the target as the
craft nears it), smoothed, zooming out as the transfer widens and back to
full size on the target; through window._altoSolarCam (solar_draw.py), the
board's offset on whole device px when zoomed out.

THE PAGE (FLY_RUN_JS): #solar-fly-svg in #world (pointer-events none, no
masks or filters): the route ahead dashed, a fading trail, the craft. Hooks:
window.enterFocus (wrapped: search hits, clicks, the whole chart's clicks)
and window._altoSolarNav (wrapped: the engine's focusNeighbor arrows; a hop
that flies returns an id no node has, so the engine's own enterFocus passes
it by, and window._altoFlyMs holds the engine's hop queue until the landing).
Arrows pressed while flying queue (≤ 3, auto-repeat at most one) and fly on
from each landing; a new target on the way re-plans from the craft's place
and velocity; Esc stops and brings the view back to full size where the craft
is; a wheel, another owner of the view, or of the focus, stops it where it is.
No flight (the existing instant focus): enlarging a body when none is
enlarged, phones, prefers-reduced-motion, edit mode, print, a zoomed-out
view, window._altoFlyOff (tests of other things), and the Plain look
(nothing of this runs).
"""
from __future__ import annotations

import json
import math

FLY = {
    # the progress curve: the regularized incomplete beta B(a, b), the family of
    # the engine's _altoEase (Luke's "F" is B(1.4, 2.6)); a flight is longer, so
    # its peak speed sits a little later
    "EASE": (1.6, 2.1),
    # flight time by route length: D_BASE + px * D_PER_PX, clamped (seconds)
    "D_MIN": 2.5, "D_MAX": 7.0, "D_BASE": 2.3, "D_PER_PX": 1 / 1150,
    # the bodies' clock ramps from its rate at take-off up to 1 and down to rest at landing
    "RAMP": 1.0,
    # routing
    "HOP_R": 70, "FAR_RINGS": 4, "ASSIST_DEV": math.radians(80), "ASSIST_MAX": 3, "ASSIST_SWEEP": 1.2 * math.pi, "CAP_SWEEP": 0.8 * math.pi,
    # a black-hole body is the swing-by of choice; the galactic core is swung round between
    # systems when going by it adds at most CORE_DETOUR to the way
    "BH_BONUS": 1.0, "CORE_DETOUR": 2.0, "TURN_CORE": (math.radians(30), math.radians(150)),
    "CORE_MIN": 700, "CORE_AHEAD": math.radians(70),
    "T_MID": 2.5,
    # geometry (px; radians)
    "CAP_PAD": 26, "ESC_PAD": 30, "PARK_GAP": 16, "SYS_PAD": 70, "FLY_Q": 40, "SOI_K": 3.0,
    "TURN": (math.radians(100), math.radians(160)), "CAP_ROT": 0.9, "BEZ_TURN": math.radians(75),
    "PHI_MIN": 0.7, "PHASE_PHI": 0.6, "ESC_PHI": 0.9 * math.pi, "PARK_PHI": 1.25 * math.pi,
    "RET_PHI": 1.1 * math.pi, "HOP_PHI": 0.6 * math.pi,
    "PHASE_K": 0.2, "DIP": -0.32, "ARC_N": 48,
    # time shares, iterations, a coast to wait for the window
    "MIN_SHARE": 0.08, "ITER": 3, "COAST": (0.0, 0.4, 0.8), "COAST_W": 0.35,
    # joins: a velocity blend over the first BLEND of a leg; the carry of a re-plan
    "H": 1e-4, "BLEND": 0.4, "BLEND_CAP": 3.0, "CARRY": 1.0,
    # camera: keys per flight, the stretch each frames (s), the target's lead-in
    "CAM_K": 40, "CAM_WIN": (-0.5, 1.0), "CAM_SEE": 2.0, "CAM_PAD": 160, "CAM_FILL": 0.72,
    "CAM_MIN": 0.06, "CAM_PIN": 1.2,
}
# the page's own: the trail's length, the landing glide an arrow waits for, the
# whole chart's click grace, when the view counts as taken over, near-full-size
# clamping of the camera to what the canvas can scroll to, the Esc glide
FLY_RT = {"TRAIL_MS": 1100, "LAND_MS": 500, "OV_MS": 900, "TAKE_S": 0.45, "TAKE_PX": 3,
          "CLAMP_FROM": 0.7, "CALM_MS": 520, "PATH_N": 180, "NEAR": 60, "TURN_V": 4, "HIT": 18}


FLY_PLAN_JS = r"""
/* The planner: pure, no DOM. window._altoFly.plan(S, from, to, o) → a route
   (null: nothing to fly); .at(R, tau) the craft, .cam(R, tau, o) the camera,
   .clock(R, tau) the bodies' clock. tests/solar_fly_twin.py is its Python twin. */
window._altoFly=(function(){
var C=__FLY__, PI=Math.PI, TAU=2*PI;
function hyp(x, y){ return Math.sqrt(x*x+y*y); }
function md(a, m){ return ((a%m)+m)%m; }
function bodies(S){
  var B={}, sy=S.systems||[];
  sy.forEach(function(s, si){
    function add(i, p, per, role, reach, ring, q){ var n=(S.nodes||{})[i]; if(!n) return;
      B[i]={id:i, p:p, x:n.x, y:n.y, per:+per||0, si:si, d:n.d, role:role, reach:reach, ring:ring||0, kids:[],
            orb:q ? (n.orbit||null) : null, r:q ? (q.r||0) : 0, a0:q ? (q.a0||0) : 0, look:n.look||''};
      if(p && B[p]) B[p].kids.push(i); }
    add(s.sun, '', 0, 'sun', s.R);
    (s.planets||[]).forEach(function(pl){ add(pl.id, s.sun, pl.period, 'planet', Math.max(pl.e||0, pl.d/2), pl.ring, pl);
      (pl.moons||[]).forEach(function(m){ var sats=m.sats||[], mr=0;
        if(sats.length) mr=(m.sat_r||0)+Math.max.apply(null, sats.map(function(q){ return q.d/2; }));
        add(m.id, pl.id, m.period, 'moon', Math.max(mr, m.d/2), 0, m);
        sats.forEach(function(q){ add(q.id, m.id, q.period, 'sat', q.d/2, 0, q); }); }); });
  });
  var co=S.core;                                         /* the galactic core: still, between the systems, not a node */
  if(co && sy.length>1) B[CORE]={id:CORE, p:'', x:co.x, y:co.y, per:0, si:-1, d:2*co.r, role:'core', reach:co.r, ring:0, kids:[], orb:null, r:0, a0:0, look:'blackhole'};
  return {B:B, many:sy.length>1, spin:S.spin||-1};
}
var CORE='#core';
function pos(W, i, T){
  var b=W.B[i]; if(!b.p) return [b.x, b.y];
  var p=W.B[b.p], o=pos(W, b.p, T), dx=b.x-p.x, dy=b.y-p.y, a=0;
  if(b.per>0) a=W.spin*TAU*T/b.per+(W.many ? W.spin*TAU*T/(540+60*b.si) : 0);
  if(b.orb){ var q=orbOff(b.r, b.a0+a, b.orb), h=orbOff(b.r, b.a0, b.orb); return [o[0]+dx+q[0]-h[0], o[1]+dy+q[1]-h[1]]; }   /* a comet: on its ellipse, from its plan home (as solar_draw) */
  var c=Math.cos(a), s=Math.sin(a);
  return [o[0]+dx*c-dy*s, o[1]+dx*s+dy*c];
}
/* solar.py's orbit_offset: R(rot)(A cos psi, B sin psi), A, B = r(1 +- c) */
function orbOff(r, ang, o){
  var e=o.e, q=Math.sqrt(Math.max(0, 1-e*e)), c=(1-q)/(1+q), A=r*(1+c), Bb=r*(1-c), m=ang-o.rot, ps=m;
  if(o.k) for(var i=0;i<12;i++) ps-=(ps-e*Math.sin(ps)-m)/(1-e*Math.cos(ps));
  var x=A*Math.cos(ps), y=Bb*Math.sin(ps), cr=Math.cos(o.rot), sr=Math.sin(o.rot);
  return [x*cr-y*sr, x*sr+y*cr];
}
function chain(W, i){ var o=[]; while(i){ o.push(i); i=W.B[i].p; } return o; }
/* the curve: B(a, b) as a cumulative table, like the engine's _altoEase */
var CV=(function(){ var a=C.EASE[0], b=C.EASE[1], c=[0], s=0, i, x;
  for(i=0;i<1000;i++){ x=(i+.5)/1000; s+=Math.pow(x, a-1)*Math.pow(1-x, b-1); c.push(s); }
  for(i=0;i<=1000;i++) c[i]/=s; return c; })();
function ease(x){ if(x<=0) return 0; if(x>=1) return 1; var f=x*1000, i=Math.floor(f); return CV[i]+(CV[i+1]-CV[i])*(f-i); }
function easeD(x){ var i=Math.min(999, Math.max(0, Math.floor(x*1000))); return (CV[i+1]-CV[i])*1000; }
function inv(G, s){ var N=G.length-1, lo=0, hi=N, m, d; while(hi-lo>1){ m=(lo+hi)>>1; if(G[m]<=s) lo=m; else hi=m; }
  d=G[hi]-G[lo]; return (lo+(d>0 ? (s-G[lo])/d : 0))/N; }
function easeInv(s){ return s<=0 ? 0 : s>=1 ? 1 : inv(CV, s); }
/* the bodies' clock: rate r0 up to 1, then down to rest as the craft lands */
function clock(c, tau){
  var D=c.D, ru=c.ru, r0=c.r0, t=Math.min(Math.max(tau, 0), D), x, A1;
  if(c.still) return c.T0;                              /* the orbits switched off: they stay put */
  if(t<=ru){ x=t/ru; return c.T0+r0*t+(1-r0)*ru*(x*x*x-x*x*x*x/2); }
  A1=r0*ru+(1-r0)*ru*.5;
  if(t<=D-ru) return c.T0+A1+(t-ru);
  x=(D-t)/ru; return c.T0+A1+(D-2*ru)+ru*(.5-(x*x*x-x*x*x*x/2));
}
function rate(c, tau){ var D=c.D, ru=c.ru, t=Math.min(Math.max(tau, 0), D), x;
  if(c.still) return 0;
  if(t<=ru){ x=t/ru; return c.r0+(1-c.r0)*x*x*(3-2*x); } if(t<=D-ru) return 1; x=(D-t)/ru; return x*x*(3-2*x); }
/* a leg's own curve, in its frame */
function sweep(a0, a1, spin, lo){ return lo+md(spin*(a1-a0)-lo, TAU); }
function polR(L, w){ var r0=L.r0, r1=L.r1, k=L.prof;
  if(k==='conic') return 2*r0*r1/((r0+r1)-(r0-r1)*Math.cos(PI*w));
  if(k==='cos') return r0+(r1-r0)*(1-Math.cos(PI*w))/2;
  if(k==='phase') return r0+(r1-r0)*w-L.dip*Math.sin(PI*w);
  return r0+(r1-r0)*w; }
function hypF(e, M){ var F=Math.asinh(M/e); for(var i=0;i<10;i++) F-=(e*Math.sinh(F)-F-M)/(e*Math.cosh(F)-1); return F; }
function raw(L, w){
  var k=L.k, P, v, x, y, F;
  if(k==='bez'){ P=L.P; v=1-w; var b0=v*v*v, b1=3*v*v*w, b2=3*v*w*w, b3=w*w*w;
    return [b0*P[0]+b1*P[2]+b2*P[4]+b3*P[6], b0*P[1]+b1*P[3]+b2*P[5]+b3*P[7]]; }
  if(k==='fly'){ F=hypF(L.e, -L.Mm+2*L.Mm*w); x=L.a*(L.e-Math.cosh(F)); y=L.a*Math.sqrt(L.e*L.e-1)*Math.sinh(F)*L.sense;
    return [x*L.pv[0]-y*L.pv[1], x*L.pv[1]+y*L.pv[0]]; }
  var r=polR(L, w), ang=L.a0+L.spin*L.phi*w; return [r*Math.cos(ang), r*Math.sin(ang)];
}
/* flown at an even pace along its curve: u (time) → w (parameter), by arc length */
function arc(L){ var N=C.ARC_N, g=[0], pr=raw(L, 0), cu, j;
  for(j=1;j<=N;j++){ cu=raw(L, j/N); g.push(g[j-1]+hyp(cu[0]-pr[0], cu[1]-pr[1])); pr=cu; }
  var t=g[N]; if(!(t>1e-9)) return null; return g.map(function(v){ return v/t; }); }
function nominal(L, u){ if(!('g' in L)) L.g=arc(L); var w=(!L.g || u<=0 || u>=1) ? Math.min(Math.max(u, 0), 1) : inv(L.g, u); return raw(L, w); }
function sub(a, b){ return [a[0]-b[0], a[1]-b[1]]; }
function unit(v, fb){ var n=hyp(v[0], v[1]); return n>1e-9 ? [v[0]/n, v[1]/n] : (fb===undefined ? [1, 0] : fb); }
function polar(v){ return [hyp(v[0], v[1]), Math.atan2(v[1], v[0])]; }
/* the skeleton */
function steps(W, A, Bt, Tm){
  var B=W.B, ca=chain(W, A), cb=chain(W, Bt), st=[], L, ia, ib, a1, b1, r, mid;
  if(ca[ca.length-1]!==cb[cb.length-1]){
    var pa=ca.length>=2 ? ca[ca.length-2] : '';
    if(ca.length>=2) st.push(['esc', pa]);
    var last=pa || ca[ca.length-1];
    assists(W, ca[ca.length-1], pa, cb[cb.length-1], Tm).forEach(function(I){ st.push(['xfer', ca[ca.length-1], I]); st.push(['fly', I]); last=I; });
    if(byCore(W, pos(W, last, Tm), cb[cb.length-1])){ st.push(['bez', CORE]); st.push(['fly', CORE]); }   /* round the galactic core */
    st.push(['bez', cb[cb.length-1]]);
    down(st, cb, cb.length-1); return st;
  }
  for(var i=0;i<ca.length;i++) if(cb.indexOf(ca[i])>=0){ L=ca[i]; break; }
  ia=ca.indexOf(L); ib=cb.indexOf(L); a1=ia>=1 ? ca[ia-1] : ''; b1=ib>=1 ? cb[ib-1] : '';
  if(ia>=2) st.push(['esc', a1]);
  if(!a1){ r=hyp(B[b1].x-B[L].x, B[b1].y-B[L].y);
    if(r<C.HOP_R) st.push(['hop', L, b1]); else { st.push(['park', L, b1]); st.push(['inj', L, b1]); }
    down(st, cb, ib-1); return st; }
  if(!b1){ st.push(['ret', L]); return st; }
  if(B[L].role==='sun' && Math.abs(B[a1].ring-B[b1].ring)>=C.FAR_RINGS){ mid=middle(W, L, a1, b1, Tm); if(mid){ st.push(['xfer', L, mid]); st.push(['fly', mid]); } }
  st.push(['xfer', L, b1]); down(st, cb, ib-1); return st;
}
/* the core is on the way from a: ahead, room to turn round it, little detour */
function byCore(W, a, s2){ var B=W.B; if(!B[CORE]) return false;
  var b=B[s2], c=B[CORE], d=hyp(b.x-a[0], b.y-a[1]), dc=hyp(c.x-a[0], c.y-a[1]);
  if(dc<C.CORE_MIN || d<1e-6 || hyp(b.x-c.x, b.y-c.y)-b.reach-C.SYS_PAD<C.CORE_MIN/2) return false;
  return ((c.x-a[0])*(b.x-a[0])+(c.y-a[1])*(b.y-a[1]))/(dc*d)>=Math.cos(C.CORE_AHEAD) && dc+hyp(b.x-c.x, b.y-c.y)<=C.CORE_DETOUR*d; }
function down(st, cb, k){
  if(k===cb.length-1 && st.length && st[st.length-1][0]==='bez'){
    if(k===0){ st.push(['ret', cb[0]]); return; }
    st.push(['xfer', cb[k], cb[k-1]]); k--; }
  while(k>=1){ st.push(['xfer', cb[k], cb[k-1]]); k--; }
}
function angAt(W, o, i, T){ var p=pos(W, i, T); return Math.atan2(p[1]-o[1], p[0]-o[0]); }
function middle(W, sun, a1, b1, Tm){
  var B=W.B, lo=Math.min(B[a1].ring, B[b1].ring), hi=Math.max(B[a1].ring, B[b1].ring), o=pos(W, sun, Tm), best='', bc=1e9;
  B[sun].kids.forEach(function(i){ if(lo<B[i].ring && B[i].ring<hi){
    var c=sweep(angAt(W, o, a1, Tm), angAt(W, o, i, Tm), W.spin, C.PHI_MIN)+sweep(angAt(W, o, i, Tm), angAt(W, o, b1, Tm), W.spin, C.PHI_MIN);
    c-=B[i].look==='blackhole' ? C.BH_BONUS : 0;          /* a black hole: the swing-by of choice */
    if(c<bc-1e-9){ best=i; bc=c; } } });
  return best;
}
function assists(W, s1, pa, s2, Tm){
  var B=W.B, o=[B[s1].x, B[s1].y], th=Math.atan2(B[s2].y-o[1], B[s2].x-o[0]), ring=pa ? B[pa].ring : 0, at=pa ? angAt(W, o, pa, Tm) : null, out=[];
  while(out.length<C.ASSIST_MAX){
    var best='', bc=1e9;
    B[s1].kids.forEach(function(i){ if(B[i].ring<=ring) return;
      var a=angAt(W, o, i, Tm), dev=Math.abs(md(a-th+PI, TAU)-PI), sw=at!==null ? sweep(at, a, W.spin, C.PHI_MIN) : 0;
      if(dev>C.ASSIST_DEV || sw>C.ASSIST_SWEEP) return;
      var c=sw+.5*dev-(B[i].look==='blackhole' ? C.BH_BONUS : 0); if(c<bc-1e-9){ best=i; bc=c; } });
    if(!best) break;
    out.push(best); ring=B[best].ring; at=angAt(W, o, best, Tm);
  }
  return out;
}
/* the legs */
function target(st, j, to){ for(var i=j+1;i<st.length;i++){ var q=st[i];
  if(q[0]==='xfer' || q[0]==='park' || q[0]==='inj' || q[0]==='hop') return q[2];
  if(q[0]==='fly' || q[0]==='bez' || q[0]==='ret') return q[1]; } return to; }
function capPoint(W, Y, T, din, spin){ var o=pos(W, Y, T), rho=W.B[Y].reach+C.CAP_PAD, a=Math.atan2(din[1], din[0])-spin*PI/2;
  return [o[0]+rho*Math.cos(a), o[1]+rho*Math.sin(a)]; }
function hyper(W, I, din, dout){
  var dot=Math.max(-1, Math.min(1, din[0]*dout[0]+din[1]*dout[1])), sg=din[0]*dout[1]-din[1]*dout[0]>=0 ? 1 : -1;
  var TN=I===CORE ? C.TURN_CORE : C.TURN, th=Math.min(Math.max(Math.acos(dot), TN[0]), TN[1]), c=Math.cos(sg*th), s=Math.sin(sg*th);   /* round the core: as much as the way needs */
  var dO=[din[0]*c-din[1]*s, din[0]*s+din[1]*c], e=1/Math.sin(th/2), q=W.B[I].d/2+C.FLY_Q, a=q/(e-1);
  var pv=unit([din[0]-dO[0], din[1]-dO[1]]), sense=-pv[1]*(din[0]+dO[0])+pv[0]*(din[1]+dO[1])>=0 ? 1 : -1;
  var Fm=Math.acosh((q*C.SOI_K/a+1)/e);
  return {e:e, a:a, Mm:e*Math.sinh(Fm)-Fm, pv:[pv[0], pv[1]], sense:sense};
}
function set(L, o){ for(var k in o) L[k]=o[k]; return L; }
function conic(W, L, cur, F, T0, ep, T1, lo){
  delete L.g;
  var p0=polar(sub(cur, pos(W, F, T0))), p1=polar(sub(ep, pos(W, F, T1))), r0=p0[0], a0=p0[1], r1=p1[0], a1=p1[1];
  if(r1<1e-6) set(L, {prof:'cos', r0:r0, r1:0, a0:a0, phi:C.RET_PHI});
  else if(Math.abs(r1-r0)<C.PHASE_K*Math.max(r0, r1)) set(L, {prof:'phase', r0:r0, r1:r1, a0:a0, dip:C.DIP*Math.min(r0, r1), phi:sweep(a0, a1, W.spin, C.PHASE_PHI)});
  else set(L, {prof:r0>1e-6 ? 'conic' : 'cos', r0:r0, r1:r1, a0:a0, phi:sweep(a0, a1, W.spin, lo)});
}
function legEnd(W, L, F, T){ var n=nominal(L, 1), o=F ? pos(W, F, T) : [0, 0]; return [o[0]+n[0], o[1]+n[1]]; }
function build(W, R, st){
  var B=W.B, spin=W.spin, c=R.c, legs=[], cur=R.p0, vdir=R.v0dir, hy=null, a, b;
  if(vdir===null && B[R.from].p){ a=pos(W, R.from, clock(c, 0)); b=pos(W, R.from, clock(c, 0)+.01); vdir=hyp(b[0]-a[0], b[1]-a[1])>1e-9 ? unit(sub(b, a), null) : null; }
  function tau(s){ return R.D*easeInv(s); }
  st.forEach(function(q, j){
    var s0=R.S[j], s1=R.S[j+1], T0=clock(c, tau(s0)), T1=clock(c, tau(s1)), k=q[0], F, Y, ep, pre, p9, o9, din, wn, of, p, a1;
    var L={k:k, s0:s0, s1:s1, spin:spin, f:''}, nxt=j+1<st.length ? st[j+1] : null;
    if(k==='esc'){ F=q[1]; L.f=F; p=polar(sub(cur, pos(W, F, T0))); wn=pos(W, target(st, j, R.to), T1); of=pos(W, F, T1);
      a1=Math.atan2(wn[1]-of[1], wn[0]-of[0])-spin*PI/2;
      set(L, {prof:'spiral', r0:p[0], r1:B[F].reach+C.ESC_PAD, a0:p[1], phi:sweep(p[1], a1, spin, C.ESC_PHI)}); }
    else if(k==='xfer' || k==='inj' || k==='hop'){ F=q[1]; Y=q[2]; L.f=F;
      if(nxt && nxt[0]==='fly'){ var oi=pos(W, Y, T1);
        conic(W, L, cur, F, T0, oi, T1, C.PHI_MIN); pre=legEnd(W, L, F, T1); p9=nominal(L, .995); o9=pos(W, F, T1);
        din=unit(sub(pre, [o9[0]+p9[0], o9[1]+p9[1]]), unit(sub(oi, cur)));
        wn=pos(W, target(st, j+1, R.to), clock(c, tau(R.S[j+2])));
        hy=hyper(W, Y, din, unit(sub(wn, oi)));
        var hl=set({k:'fly'}, hy), ent=nominal(hl, 0); ep=[oi[0]+ent[0], oi[1]+ent[1]]; }
      else if(nxt && nxt[0]==='xfer' && nxt[1]===Y){ var oy=pos(W, Y, T1);
        conic(W, L, cur, F, T0, oy, T1, C.PHI_MIN); pre=legEnd(W, L, F, T1); p9=nominal(L, .995); o9=pos(W, F, clock(c, tau(s0+(s1-s0)*.995)));
        din=unit(sub(pre, [o9[0]+p9[0], o9[1]+p9[1]]), unit(sub(oy, cur)));
        ep=capPoint(W, Y, T1, din, spin); }
      else ep=pos(W, Y, T1);
      if(k==='hop' && hyp.apply(null, sub(cur, pos(W, F, T0)))<1){ p=polar(sub(ep, pos(W, F, T1)));
        set(L, {prof:'cos', r0:0, r1:p[0], a0:p[1]-spin*C.HOP_PHI, phi:C.HOP_PHI}); }
      else conic(W, L, cur, F, T0, ep, T1, C.PHI_MIN); }
    else if(k==='park'){ F=q[1]; L.f=F; var Ti=clock(c, tau(R.S[j+2])), px=polar(sub(pos(W, q[2], Ti), pos(W, F, Ti))), pc=polar(sub(cur, pos(W, F, T0))), ae=px[1]+PI;
      if(pc[0]<1) set(L, {prof:'spiral', r0:pc[0], r1:B[F].d/2+C.PARK_GAP, a0:ae-spin*C.PARK_PHI, phi:C.PARK_PHI});
      else set(L, {prof:'spiral', r0:pc[0], r1:B[F].d/2+C.PARK_GAP, a0:pc[1], phi:sweep(pc[1], ae, spin, C.PHI_MIN)}); }
    else if(k==='ret'){ F=q[1]; L.f=F; p=polar(sub(cur, pos(W, F, T0))); set(L, {prof:'cos', r0:p[0], r1:0, a0:p[1], phi:C.RET_PHI}); }
    else if(k==='fly'){ L.f=q[1]; set(L, hy); }
    else if(k==='bez' && nxt && nxt[0]==='fly'){ var oc=pos(W, q[1], T1);   /* out to a swing round the core */
      wn=pos(W, target(st, j+1, R.to), clock(c, tau(R.S[j+2])));
      hy=hyper(W, q[1], unit(sub(oc, cur)), unit(sub(wn, oc)));
      var hc=set({k:'fly'}, hy), e0=nominal(hc, 0), e1=nominal(hc, .002);
      L.P=bez(cur, [oc[0]+e0[0], oc[1]+e0[1]], vdir, unit(sub(e1, e0))); }
    else if(k==='bez'){ var s2=q[1], o2=pos(W, s2, T1), tc=Math.atan2(cur[1]-o2[1], cur[0]-o2[0]), rr=B[s2].reach+C.SYS_PAD;
      var nb=(j+1<st.length && st[j+1][0]==='xfer') ? st[j+1][2] : '', al=tc+spin*C.CAP_ROT, best=null;
      if(nb){ var aT=Math.atan2.apply(null, sub(pos(W, nb, clock(c, R.D)), o2).reverse());
        for(var m=0;m<15;m++){ var dl=-1.2+.2*m, aa=tc+spin*dl, ch0=unit(sub([o2[0]+rr*Math.cos(aa), o2[1]+rr*Math.sin(aa)], cur)), ta=aa+spin*PI/2;
          if(ch0[0]*Math.cos(ta)+ch0[1]*Math.sin(ta)<Math.cos(C.BEZ_TURN)) continue;
          var cs=Math.abs(sweep(aa, aT, spin, C.PHI_MIN)-C.CAP_SWEEP)+.3*Math.abs(dl-C.CAP_ROT);
          if(best===null || cs<best[0]-1e-9) best=[cs, aa]; }
        if(best) al=best[1]; }
      L.P=bez(cur, [o2[0]+rr*Math.cos(al), o2[1]+rr*Math.sin(al)], vdir, [Math.cos(al+spin*PI/2), Math.sin(al+spin*PI/2)]); }
    legs.push(L);
    var end=legEnd(W, L, L.f, T1), T9=clock(c, tau(s0+(s1-s0)*.995)), n9=nominal(L, .995), q9=L.f ? pos(W, L.f, T9) : [0, 0], dv=sub(end, [q9[0]+n9[0], q9[1]+n9[1]]);
    vdir=hyp(dv[0], dv[1])>1e-6 ? unit(dv) : null;
    cur=end;
  });
  return legs;
}
/* a cruise from cur (going vdir) to p3 (arriving along t3), never setting off more than BEZ_TURN from its way */
function bez(cur, p3, vdir, t3){
  var ch=unit(sub(p3, cur)), t0v=vdir ? unit(vdir, ch) : ch, cr=ch[0]*t0v[1]-ch[1]*t0v[0], dt=ch[0]*t0v[0]+ch[1]*t0v[1];
  if(dt<Math.cos(C.BEZ_TURN)){ var g=C.BEZ_TURN*(cr>=0 ? 1 : -1); t0v=[ch[0]*Math.cos(g)-ch[1]*Math.sin(g), ch[0]*Math.sin(g)+ch[1]*Math.cos(g)]; }
  var ln=hyp(p3[0]-cur[0], p3[1]-cur[1])/3;
  return [cur[0], cur[1], cur[0]+t0v[0]*ln, cur[1]+t0v[1]*ln, p3[0]-t3[0]*ln, p3[1]-t3[1]*ln, p3[0], p3[1]];
}
function length(L){ var tot=0, pr=nominal(L, 0), cu; for(var j=1;j<=16;j++){ cu=nominal(L, j/16); tot+=hyp(cu[0]-pr[0], cu[1]-pr[1]); pr=cu; } return tot; }
function shares(lens){ var n=lens.length, tot=lens.reduce(function(a, v){ return a+v; }, 0)||1, lo=Math.min(C.MIN_SHARE, 1/n);
  var w=lens.map(function(v){ return Math.max(lo, v/tot); }), k=w.reduce(function(a, v){ return a+v; }, 0), S=[0], acc=0;
  w.forEach(function(v){ acc+=v/k; S.push(acc); }); S[S.length-1]=1; return S; }
function dur(t){ return Math.min(C.D_MAX, Math.max(C.D_MIN, C.D_BASE+t*C.D_PER_PX)); }
function clk(o, D){ return {T0:+(o.T0||0), r0:+(o.r0||0), D:D, ru:Math.min(C.RAMP, D/3), still:!!o.still}; }
function plan(S, A, Bt, o){
  o=o||{}; var W=bodies(S); if(!W.B[A] || !W.B[Bt] || A===Bt || A===CORE || Bt===CORE) return null;
  var T0=+(o.T0||0), st=steps(W, A, Bt, T0+C.T_MID); if(!st.length) return null;
  var sv=o.start, p0=sv ? [sv[0], sv[1]] : pos(W, A, T0), R={W:W, to:Bt, from:A, p0:p0, v0dir:null}, legs, it, lens;
  if(sv && hyp(sv[2], sv[3])>1e-6) R.v0dir=unit([sv[2], sv[3]]);
  R.D=dur(hyp.apply(null, sub(pos(W, Bt, T0), p0))*1.4);
  R.S=st.map(function(_, j){ return j/st.length; }).concat([1]); R.c=clk(o, R.D);
  for(it=0;it<C.ITER;it++){ legs=build(W, R, st); lens=legs.map(length); R.S=shares(lens); R.D=dur(lens.reduce(function(a, v){ return a+v; }, 0)); R.c=clk(o, R.D); }
  var best=null;
  C.COAST.forEach(function(cst){ var R2={}; for(var k in R) R2[k]=R[k]; R2.D=R.D+cst; if(R2.D>C.D_MAX+1e-9) return;
    R2.c=clk(o, R2.D); var lg=build(W, R2, st), cost=cst*C.COAST_W;
    lg.forEach(function(L){ if(L.prof==='conic') cost+=Math.abs(L.phi-PI)/PI; });
    if(best===null || cost<best[0]-1e-9) best=[cost, R2, lg]; });
  R=best[1]; R.legs=best[2]; R.steps=st;
  blends(R);
  if(sv){ var vn=vel(R, 0, 1); R.carry=[sv[2]-vn[0], sv[3]-vn[1], Math.min(C.CARRY, R.D/3)]; }
  R.keys=camKeys(R, o);
  return R;
}
function legXY(R, L, t, s, bl){
  var u=Math.min(Math.max((s-L.s0)/(L.s1-L.s0), 0), 1), T=clock(R.c, t), o=L.f ? pos(R.W, L.f, T) : [0, 0], n=nominal(L, u), x=o[0]+n[0], y=o[1]+n[1], H=L.H;
  if(bl!==false && H && u<H[4]){ var q=u/H[4], h00=2*q*q*q-3*q*q+1, h10=q*q*q-2*q*q+q; x+=h00*H[0]+h10*H[4]*H[2]; y+=h00*H[1]+h10*H[4]*H[3]; }
  return [x, y];
}
function legOf(R, s){ for(var i=0;i<R.legs.length;i++) if(s<=R.legs[i].s1) return R.legs[i]; return R.legs[R.legs.length-1]; }
function at(R, tau){
  var D=R.D, t=Math.min(Math.max(tau, 0), D), s=ease(t/D), p=legXY(R, legOf(R, s), t, s), Cr=R.carry;
  if(Cr && t<Cr[2]){ var k=t*(1-t/Cr[2])*(1-t/Cr[2]); p[0]+=Cr[0]*k; p[1]+=Cr[1]*k; }
  return p;
}
function vel(R, t, side){ var h=C.H, a=side>0 ? at(R, t) : at(R, t-h), b=side>0 ? at(R, t+h) : at(R, t); return [(b[0]-a[0])/h, (b[1]-a[1])/h]; }
function blends(R){
  var D=R.D;
  for(var i=1;i<R.legs.length;i++){
    var L=R.legs[i], t=D*easeInv(L.s0), h=C.H, pin=at(R, t), a=at(R, t-h), vin=[(pin[0]-a[0])/h, (pin[1]-a[1])/h];
    var n0=legXY(R, L, t, L.s0, false), n1=legXY(R, L, t+h, ease((t+h)/D), false), vn=[(n1[0]-n0[0])/h, (n1[1]-n0[1])/h];
    var du=easeD(t/D)/D/(L.s1-L.s0), ub=C.BLEND, gx=0, gy=0;
    if(du>1e-6){ gx=(vin[0]-vn[0])/du; gy=(vin[1]-vn[1])/du; }
    var cap=C.BLEND_CAP*Math.max(length(L), 40)/ub, m=hyp(gx, gy);
    if(m>cap){ gx=gx*cap/m; gy=gy*cap/m; }
    L.H=[pin[0]-n0[0], pin[1]-n0[1], gx, gy, ub];
  }
}
/* the camera: keys [tau, cx, cy, ln scale] framing the next stretch (and the target, nearing it), smoothed */
function camKeys(R, o){
  var D=R.D, v=o.view||[1500, 950], K=C.CAM_K, wn=C.CAM_WIN, end=pos(R.W, R.to, clock(R.c, D)), raw=[], k, j;
  for(k=0;k<=K;k++){ var t=D*k/K, xs=[], ys=[];
    for(j=0;j<7;j++){ var p=at(R, t+wn[0]+(wn[1]-wn[0])*j/6); xs.push(p[0]); ys.push(p[1]); }
    if(t>=D-C.CAM_SEE){ xs.push(end[0]); ys.push(end[1]); }
    var x0=Math.min.apply(null, xs), x1=Math.max.apply(null, xs), y0=Math.min.apply(null, ys), y1=Math.max.apply(null, ys);
    var sc=Math.min(1, v[0]*C.CAM_FILL/(x1-x0+C.CAM_PAD), v[1]*C.CAM_FILL/(y1-y0+C.CAM_PAD));
    raw.push([t, (x1+x0)/2, (y1+y0)/2, Math.log(Math.max(C.CAM_MIN, sc))]); }
  for(var pass=0;pass<2;pass++){ var sm=[];
    for(k=0;k<=K;k++){ var a=Math.max(0, k-2), b=Math.min(K, k+2), n=b-a+1, row=[raw[k][0]];
      for(j=1;j<=3;j++){ var s=0; for(var i=a;i<=b;i++) s+=raw[i][j]; row.push(s/n); } sm.push(row); }
    raw=sm; }
  return raw;
}
function cat(P, k, f, j){ var n=P.length-1, p0=P[Math.max(0, k-1)][j], p1=P[k][j], p2=P[Math.min(n, k+1)][j], p3=P[Math.min(n, k+2)][j];
  return .5*((2*p1)+(-p0+p2)*f+(2*p0-5*p1+4*p2-p3)*f*f+(-p0+3*p1-3*p2+p3)*f*f*f); }
function ss(x){ x=Math.min(Math.max(x, 0), 1); return x*x*(3-2*x); }
function cam(R, tau, o){
  var D=R.D, P=R.keys, t=Math.min(Math.max(tau, 0), D), K=P.length-1, x=t/D*K, k=Math.min(K-1, Math.floor(x)), f=x-k;
  var cx=cat(P, k, f, 1), cy=cat(P, k, f, 2), ls=cat(P, k, f, 3), c0=(o && o.cam) || [P[0][1], P[0][2], 1];
  var l0=Math.log(Math.max(C.CAM_MIN, Math.min(1, c0[2]))), end=pos(R.W, R.to, clock(R.c, D)), tp=Math.min(C.CAM_PIN, D/3), a=ss(t/tp), b;
  cx=c0[0]+(cx-c0[0])*a; cy=c0[1]+(cy-c0[1])*a; ls=l0+(ls-l0)*a;
  b=ss((t-(D-tp))/tp); cx=cx+(end[0]-cx)*b; cy=cy+(end[1]-cy)*b; ls=ls*(1-b);
  return [cx, cy, Math.min(1, Math.exp(ls))];
}
return {plan:plan, at:at, cam:cam, vel:vel, clock:function(R, t){ return clock(R.c, t); }, rate:function(R, t){ return rate(R.c, t); },
        pos:pos, bodies:bodies, ease:ease, easeInv:easeInv};
})();
""".replace("__FLY__", json.dumps(FLY, separators=(",", ":")))


FLY_RUN_JS = r"""
/* ── the flight in the page: a Star chart only (solar_fly.py) ─────────────────
   Changing the enlarged body (an arrow, a click, a search hit — anything through
   enterFocus) flies there: the craft and its trail in #solar-fly-svg, the route
   ahead dashed, the camera through window._altoSolarCam, the orbits driven on
   the flight's own clock (window._altoSolarDrive) so the craft meets the body
   where it is. On arrival the body is enlarged as ever and the orbits stand
   still. Only in the Star chart look of a Hub & spoke page (window._altoSolarLook;
   the Plain look has none of it: no layer, no frame loop). No flight: phones,
   reduced motion, edit mode, print, a zoomed-out view. */
(function(){
var F=window._altoFly, de=document.documentElement, NS='http://www.w3.org/2000/svg', K=__RT__;
function S(){ return window._ALTO_SOLAR; }
if(!F) return;
/* the Star chart look (moving orbits) is on */
function stars(){ var L=window._altoSolarLook; return !!S() && (L && L.get ? L.get()==='stars' : S().style==='orbit'); }
/* the orbits are on (the Orbit switch, window._altoSolarMotion): off, the craft flies among still bodies */
function moving(){ var M=window._altoSolarMotion; return !M || !M.get || !!M.get(); }
var FL=null, raf=0, Q=[], ovAt=-1e9, landAt=-1e9, enter0=null, nav0=null, svg=null, gp=null, pth=null, trl=null, grd=null, ship=null, lastS=0, reduced=false, printing=0, held={}, calm=0;
try{ var mq=matchMedia('(prefers-reduced-motion: reduce)'); reduced=mq.matches;
  var mqf=function(){ reduced=mq.matches; }; if(mq.addEventListener) mq.addEventListener('change', mqf); else mq.addListener(mqf); }catch(e){}
function cvs(){ return document.getElementById('canvas'); }
function cam(){ return window._altoSolarCam; }
function pad(){ return (typeof WORLD_PAD_TOP!=='undefined') ? WORLD_PAD_TOP : 0; }
function ss(x){ x=Math.min(Math.max(x, 0), 1); return x*x*(3-2*x); }
function el(t, a, p){ var e=document.createElementNS(NS, t); for(var k in a) e.setAttribute(k, a[k]); if(p) p.appendChild(e); return e; }
function f1(v){ return Math.round(v*10)/10; }
function dz(){ return (parseFloat(getComputedStyle(de).zoom)||1)*(window.devicePixelRatio||1); }
/* may this change of body be flown? */
function can(){
  if(window._altoFlyOff || !stars() || de.classList.contains('mobile') || reduced || printing || de.classList.contains('alto-editing')) return false;
  if(!cam() || !window._altoSolarDrive || !window._altoSolarRate || !cvs() || document.querySelector('#detail-page.visible')) return false;
  if(FL) return true;
  var g=cam().get(); return !!g && g.scale>=.999 && performance.now()-ovAt>K.OV_MS;
}
/* the body the craft is in among, flying (a re-plan starts from it): the smallest
   whose reach it is within, else the nearest system's sun */
function nearBody(p, T){
  var W=F.bodies(S()), best=null, br=1e18, sun=null, sd=1e18;
  Object.keys(W.B).forEach(function(i){ var b=W.B[i]; if(b.role==='core') return; var q=F.pos(W, i, T), d=Math.hypot(p[0]-q[0], p[1]-q[1]);
    if(d<b.reach+K.NEAR && b.reach<br){ br=b.reach; best=i; }
    if(!b.p && d-b.reach<sd){ sd=d-b.reach; sun=i; } });
  return best || sun;
}
/* the view's reach at full size (canvas scroll), in plan px: near full size the
   camera comes within it, and the landing's own glide pans the rest */
function extent(){
  var c=cvs(), w=document.getElementById('world'); if(!c || !w) return null;
  var ox=0, oy=0, q=w; while(q && q!==c){ ox+=q.offsetLeft; oy+=q.offsetTop; q=q.offsetParent; }
  var cw=c.clientWidth, ch=c.clientHeight, P=pad();
  return {x0:cw/2-ox, x1:c.scrollWidth-cw/2-ox, y0:ch/2-oy-P, y1:c.scrollHeight-ch/2-oy-P};
}
function clampTo(v, a, b){ return a>b ? (a+b)/2 : Math.min(b, Math.max(a, v)); }
function setCam(m){
  var c=cvs(), s=m[2]>=.999 ? 1 : m[2], cx=m[0], cy=m[1], E=FL.ext, w=ss((s-K.CLAMP_FROM)/(1-K.CLAMP_FROM));
  if(E && w>0){ cx+=(clampTo(cx, E.x0, E.x1)-cx)*w; cy+=(clampTo(cy, E.y0, E.y1)-cy)*w; }
  if(s<1){                               /* the board's offset on whole device px (crisp, Safari) */
    var z=dz(), cw=c.clientWidth/2, ch=c.clientHeight/2, P=pad(), tx=Math.round((cw-cx*s)*z)/z, ty=Math.round((ch-(cy+P)*s)*z)/z;
    cx=(cw-tx)/s; cy=(ch-ty)/s-P; }
  FL.set=cam().set(cx, cy, s);
}
/* ── the layer: the route ahead (dashed), the trail (fading), the craft ───── */
function layer(){
  var w=document.getElementById('world'); if(!w) return;
  if(!svg || !svg.isConnected){
    svg=el('svg', {id:'solar-fly-svg', width:1, height:1, 'aria-hidden':'true'});
    var df=el('defs', {}, svg);
    grd=el('linearGradient', {id:'sol-fly-trail', gradientUnits:'userSpaceOnUse'}, df);
    el('stop', {offset:'0', 'class':'fly-t0'}, grd); el('stop', {offset:'1', 'class':'fly-t1'}, grd);
    gp=el('g', {}, svg);
    pth=el('path', {'class':'fly-path'}, gp); trl=el('path', {'class':'fly-trail', stroke:'url(#sol-fly-trail)'}, gp);
    ship=el('g', {'class':'fly-craft'}, gp);
    el('circle', {r:9, 'class':'fly-halo'}, ship);
    el('path', {d:'M7 0 L-5 -4.6 L-2.6 0 L-5 4.6 Z', 'class':'fly-hull'}, ship);
    w.appendChild(svg);
  }
  svg.setAttribute('width', w.offsetWidth); svg.setAttribute('height', w.offsetHeight);
  gp.setAttribute('transform', 'translate(0,'+pad()+')');
  svg.classList.remove('fly-out'); lastS=0;
}
function route(R){
  var d='', n=K.PATH_N;
  for(var i=0;i<=n;i++){ var p=F.at(R, R.D*i/n); d+=(i ? 'L' : 'M')+f1(p[0])+' '+f1(p[1]); }
  pth.setAttribute('d', d);
}
function draw(p, h, s, now){
  var tr=FL.trail; tr.push([p[0], p[1], now]);
  while(tr.length>2 && now-tr[0][2]>K.TRAIL_MS) tr.shift();
  var d='M'+tr.map(function(q){ return f1(q[0])+' '+f1(q[1]); }).join('L');
  trl.setAttribute('d', d);
  var t0=tr[0]; grd.setAttribute('x1', f1(t0[0])); grd.setAttribute('y1', f1(t0[1])); grd.setAttribute('x2', f1(p[0])); grd.setAttribute('y2', f1(p[1]));
  ship.setAttribute('transform', 'translate('+f1(p[0])+','+f1(p[1])+') rotate('+Math.round(h*180/Math.PI)+') scale('+(Math.round(1000/s)/1000)+')');
  if(Math.abs(s-lastS)>lastS*.01){ lastS=s;                /* the lines keep their width on screen as the board scales */
    pth.setAttribute('stroke-width', f1(1.6/s*10)/10); pth.setAttribute('stroke-dasharray', f1(4/s)+' '+f1(8/s));
    trl.setAttribute('stroke-width', f1(2.6/s*10)/10); }
}
function fade(){ if(svg) svg.classList.add('fly-out'); }
/* ── a flight ─────────────────────────────────────────────────────────────── */
function fly(from, to, o){
  var rt=window._altoSolarRate(), c=cvs(), g=cam().get();
  var opt={T0:o ? o.T0 : rt.T, r0:o ? o.r0 : rt.r, view:[c.clientWidth, c.clientHeight], cam:[g.cx, g.cy, g.scale], still:!moving()};
  if(o && o.start) opt.start=o.start;
  var R=F.plan(S(), from, to, opt); if(!R) return false;
  if(!FL && window._focusedNodeId && window.exitFocus) window.exitFocus();       /* the card it leaves goes home */
  var tr=FL ? FL.trail : [];
  FL={R:R, o:opt, to:to, from:from, t0:performance.now(), trail:tr, set:null, ms:FL ? FL.ms : [], head:FL ? FL.head : 0, ext:(FL && FL.ext) || (g.scale>=.999 ? extent() : null)};
  window._altoFlyMs=Math.round(R.D*1000)+K.LAND_MS;     /* an arrow's hop waits for the landing */
  layer(); route(R);
  window._altoSolarDrive(F.clock(R, 0));
  de.classList.add('sol-flying');
  cancelAnimationFrame(raf); raf=requestAnimationFrame(frame);
  return true;
}
function frame(now){
  raf=0; if(!FL) return;
  var R=FL.R, tau=Math.max(0, (now-FL.t0)/1000), c0=performance.now();
  /* someone else took the view (a wheel, the whole-chart toggle) or the focus: it is theirs */
  if(!stars() || de.classList.contains('alto-editing') || printing || window._focusedNodeId) return stop(false);
  if(FL.set && tau>K.TAKE_S){ var g=cam().get();
    if(!g || Math.abs(g.scale-FL.set.scale)>.01*FL.set.scale || Math.hypot(g.cx-FL.set.cx, g.cy-FL.set.cy)>K.TAKE_PX/g.scale) return stop(false); }
  window._altoSolarDrive(F.clock(R, tau));
  var p=F.at(R, tau), m=F.cam(R, tau, FL.o), v=F.vel(R, Math.min(tau, R.D-.02), 1);
  if(Math.hypot(v[0], v[1])>K.TURN_V) FL.head=Math.atan2(v[1], v[0]);
  setCam(m);
  draw(p, FL.head, m[2], now);
  FL.ms.push(performance.now()-c0);                    /* this layer's own cost a frame (tests read it) */
  if(tau>=R.D) return land();
  raf=requestAnimationFrame(frame);
}
var LAST=null;
function land(){
  var to=FL.to; LAST={to:to, from:FL.from, D:FL.R.D, ms:FL.ms, steps:FL.R.steps.map(function(q){ return q[0]; }), how:'landed'}; FL=null; cancelAnimationFrame(raf); raf=0;
  landAt=performance.now(); fade(); de.classList.remove('sol-flying');
  (enter0 || window.enterFocus).call(window, to);         /* enlarged as ever: where it is, the orbits still */
  window._altoSolarDrive(null, 0);
  setTimeout(next, (window._altoFlyMs||460)+40);
}
/* stopped on the way: the orbits run on from where the clock was; calm (Esc): the
   view comes back to full size where the craft is */
function stop(calmly){
  if(!FL) return; var R=FL.R, tau=Math.min(R.D, Math.max(0, (performance.now()-FL.t0)/1000)), p=F.at(R, tau);
  LAST={to:FL.to, from:FL.from, D:R.D, ms:FL.ms, how:calmly ? 'esc' : 'stopped'};
  window._altoSolarDrive(null, F.rate(R, tau)); FL=null; cancelAnimationFrame(raf); raf=0; Q=[];
  fade(); de.classList.remove('sol-flying');
  var g=cam().get(); if(!calmly || !g || g.scale>=.999) return;
  var a={cx:g.cx, cy:g.cy, l:Math.log(g.scale)}, t0=performance.now(), me=++calm, ez=window._altoEase || ss;
  (function step(now){ if(me!==calm) return; var k=Math.min(1, (now-t0)/K.CALM_MS), e=ez(k);
    cam().set(a.cx+(p[0]-a.cx)*e, a.cy+(p[1]-a.cy)*e, Math.exp(a.l*(1-e))); if(k<1) requestAnimationFrame(step); })(t0);
}
/* a new target on the way: from where the craft is, as it is moving */
function replan(to){
  var R=FL.R, tau=Math.min(R.D, Math.max(0, (performance.now()-FL.t0)/1000)), p=F.at(R, tau), v=F.vel(R, tau, 1), T=F.clock(R, tau), from=nearBody(p, T);
  if(from===to){ var W=F.bodies(S()); from=W.B[to].p || W.B[to].kids[0] || from; }
  return from!==to && fly(from, to, {start:[p[0], p[1], v[0], v[1]], T0:T, r0:F.rate(R, tau)});
}
/* the arrows pressed on the way: one at a time, after each landing (as the engine's hops) */
function next(){
  if(FL || !Q.length) return; var id=window._focusedNodeId, d=Q.shift();
  if(!id || !nav0) return; var nx=nav0(id, d); if(!nx) return next();
  if(!can() || !fly(id, nx)) (enter0 || window.enterFocus).call(window, nx);
}
/* ── the hooks: window.enterFocus (search, clicks, the whole chart, …) and the
   arrows' window._altoSolarNav (engine focusNeighbor) ─────────────────────── */
var HOP='\u0001fly';                                  /* no node has this id: the engine's own enterFocus passes it by */
function hook(){
  if(typeof window.enterFocus==='function' && !window.enterFocus._fly){
    enter0=window.enterFocus;
    var w=function(id){
      if(FL){ if(id===FL.to) return; if(can() && replan(id)) return; stop(false); return enter0.apply(this, arguments); }
      /* a change of the enlarged body flies; enlarging from none is as ever */
      var from=window._focusedNodeId;
      if(!id || !from || id===from || !can() || !fly(from, id)) return enter0.apply(this, arguments);
    };
    w._fly=1; window.enterFocus=w;
  }
  if(typeof window._altoSolarNav==='function' && !window._altoSolarNav._fly){
    nav0=window._altoSolarNav;
    var n=function(id, dir){ var nx=nav0(id, dir); if(!nx || !can()) return nx; return fly(id, nx) ? HOP : nx; };
    n._fly=1; window._altoSolarNav=n;
  }
  return !!enter0 && !!nav0;
}
(function tryHook(k){ if(!hook() && k<200) setTimeout(function(){ tryHook(k+1); }, 50); })(0);
var ARR={ArrowLeft:'w', ArrowRight:'e', ArrowUp:'n', ArrowDown:'s'};
window.addEventListener('keyup', function(e){ delete held[ARR[e.key]]; }, true);
window.addEventListener('blur', function(){ held={}; });
window.addEventListener('keydown', function(e){
  var d=ARR[e.key]; if(d) held[d]=1;
  if(!FL) return;
  if(!stars()) return stop(false);
  if(e.key==='Escape'){ e.preventDefault(); e.stopImmediatePropagation(); stop(true); return; }
  if(!d) return;
  e.preventDefault(); e.stopImmediatePropagation();
  var v=d==='n' || d==='s', pr=v ? (held.e ? 'e' : held.w ? 'w' : '') : (held.n ? 'n' : held.s ? 's' : '');
  if(pr) d=v ? d+pr : pr+d;
  if(e.repeat ? !Q.length : Q.length<3) Q.push(d);
}, true);
/* zoomed out on the way, a click on a body goes there (not the whole chart's own click) */
var dn=null;
window.addEventListener('pointerdown', function(e){ dn=FL && cvs() && cvs().contains(e.target) ? {x:e.clientX, y:e.clientY} : null;
  if(dn){ e.preventDefault(); e.stopImmediatePropagation(); } }, true);
window.addEventListener('pointerup', function(e){
  if(!dn) return; var d0=dn; dn=null; if(!FL) return; e.preventDefault(); e.stopImmediatePropagation();
  if(Math.abs(e.clientX-d0.x)+Math.abs(e.clientY-d0.y)>6) return;
  var c=cvs(), r=c.getBoundingClientRect(), g=cam().get(), k=r.width/c.offsetWidth||1;
  var wx=g.cx+((e.clientX-r.left)/k-c.clientWidth/2)/g.scale, wy=g.cy+((e.clientY-r.top)/k-c.clientHeight/2)/g.scale;
  var W=F.bodies(S()), T=window._altoSolarRate().T, best=null, bd=1e18;
  Object.keys(W.B).forEach(function(i){ if(W.B[i].role==='core') return; var p=F.pos(W, i, T), dd=Math.hypot(p[0]-wx, p[1]-wy)-W.B[i].d/2; if(dd<bd){ bd=dd; best=i; } });
  if(best && bd<K.HIT/g.scale) window.enterFocus(best);
}, true);
['click', 'mousedown', 'dblclick'].forEach(function(t){ window.addEventListener(t, function(e){ if(FL && cvs() && cvs().contains(e.target)){ e.preventDefault(); e.stopImmediatePropagation(); } }, true); });
window.addEventListener('wheel', function(){ if(FL) stop(false); }, {capture:true, passive:true});
window.addEventListener('beforeprint', function(){ printing=1; stop(false); });
window.addEventListener('afterprint', function(){ printing=0; });
/* the whole chart left by the user (a click there enlarges a body: no flight) */
function watchOv(){ var c=cvs(); if(!c || typeof MutationObserver!=='function') return; var was=c.classList.contains('sol-ov');
  new MutationObserver(function(){ var now=c.classList.contains('sol-ov'); if(was && !now && !FL && performance.now()-landAt>K.OV_MS) ovAt=performance.now(); was=now; })
    .observe(c, {attributes:true, attributeFilter:['class']}); }
/* Plain look: nothing of the flight left (stopped where it was, the layer gone) */
function look(){ if(stars()) return; stop(false); Q=[]; if(svg){ svg.remove(); svg=null; } }
function init(){ watchOv(); var L=window._altoSolarLook, M=window._altoSolarMotion; if(L && L.onChange) L.onChange(look);
  if(M && M.onChange) M.onChange(function(){ if(FL && !!FL.o.still===moving() && !replan(FL.to)) stop(false); }); }   /* switched on the way: on from here, the new way */
if(document.readyState!=='loading') init(); else document.addEventListener('DOMContentLoaded', init);
window._altoSolarFlight=function(last){ if(last) return LAST; if(!FL) return null; var R=FL.R, tau=(performance.now()-FL.t0)/1000;
  return {from:FL.from, to:FL.to, D:R.D, tau:tau, steps:R.steps.map(function(q){ return q[0]; }), at:F.at(R, Math.min(tau, R.D)), queued:Q.slice(), ms:FL.ms.slice()}; };
})();
""".replace("__RT__", json.dumps(FLY_RT, separators=(",", ":")))

FLY_CSS = r"""
  #solar-fly-svg{position:absolute;left:0;top:0;z-index:150;overflow:visible;pointer-events:none;opacity:1;transition:opacity .45s cubic-bezier(.25,.2,.4,1);}
  #solar-fly-svg.fly-out{opacity:0;}
  html.mobile #solar-fly-svg{display:none !important;}
  @media print{ #solar-fly-svg{display:none !important;} }
  #solar-fly-svg .fly-path{fill:none;stroke:var(--text);stroke-opacity:.42;stroke-linecap:round;}
  #solar-fly-svg .fly-trail{fill:none;stroke-linecap:round;stroke-linejoin:round;}
  #solar-fly-svg .fly-t0{stop-color:var(--accent,#6d5bd0);stop-opacity:0;}
  #solar-fly-svg .fly-t1{stop-color:var(--accent,#6d5bd0);stop-opacity:.9;}
  #solar-fly-svg .fly-halo{fill:var(--accent,#6d5bd0);fill-opacity:.22;}
  #solar-fly-svg .fly-hull{fill:var(--accent,#6d5bd0);stroke:#fff;stroke-width:1.2;stroke-linejoin:round;}
  html.dark #solar-fly-svg .fly-path{stroke:#fff;stroke-opacity:.38;}
  html.dark #solar-fly-svg .fly-t0,html.dark #solar-fly-svg .fly-t1,html.dark #solar-fly-svg .fly-halo{stop-color:#cfc6ff;fill:#cfc6ff;}
  html.dark #solar-fly-svg .fly-hull{fill:#cfc6ff;stroke:#1a1830;}
"""


def _slim(src: str) -> str:
    """The page copy without comments and indentation (the source keeps them)."""
    import re
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(l.strip() for l in src.splitlines() if l.strip()) + "\n"


FLY_JS = _slim(FLY_PLAN_JS + FLY_RUN_JS)
FLY_CSS = _slim(FLY_CSS)
