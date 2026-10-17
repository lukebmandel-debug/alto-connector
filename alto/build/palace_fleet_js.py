"""The toy fleet, part 1 (1.9.99): what the boats and bases look like. Hosted with the rest (palace_fleet_asset.py), never in the page.

Every warship and base is drawn as a piece of the board game Battleship seen from above: grey moulded plastic, a thick edge you can see, peg dimples,
a few pieces in relief (the bridge, the funnels, the gun mounts), engraved lines. Carrier = a long flat flight deck with its island and a few little jets,
battleship = the lens-shaped hull with two twin mounts (USS New Jersey, as 1.9.97), cruiser/destroyer = a slim hull with a launch-cell block and two
single mounts, submarine = a cigar with its fin, military base = a plate with a battery of guns or a runway with jets. The ships that are no warship
(tall ships, tugs, a restaurant ship) keep the older art of a hull with upright glass parts in the buildings' own lean.
"""
from __future__ import annotations

FLEET_A = r"""
/* ── the fleet (palace_fleet_js.py: art, palace_fleet_fx.py: weapons) ── */
window._palFleet=(function(){
var H=null, el, pin, ARM=null, LAST=0, SND=window._palSnd, R=Math.random, WP={}, bound=false, PI=Math.PI;
function cl(x){ return x<0?0:(x>1?1:x); }
function sm(x){ x=cl(x); return x*x*(3-2*x); }
function f1(v){ return (+v).toFixed(1); }

/* ── boats: a name tells what a boat is when the data does not (older pages carry no weapon class k) ── */
function boatKind(n, L, W){ n=String(n||'');
  if(/new jersey|\biowa\b|missouri|wisconsin|battleship/i.test(n)) return 'bb';
  if(/becuna|submarine|growler|\bSS-|nautilus|\bUSS [A-Z][a-z]+ \(SS/i.test(n)) return 'sub';
  if(/intrepid|carrier|midway|lexington|yorktown|hornet/i.test(n)) return 'carrier';
  if(/olympia|cruiser|cassin|destroyer|laffey|kidd|the sullivans|frigate/i.test(n)) return 'cruiser';
  if(/moshulu|wavertree|gazela|constitution|barque|schooner|clipper|\bpioneer\b|kalmar|peking/i.test(n)) return 'tall';
  if(/fireboat|lightship|lilac|nantucket|frying pan|ambrose|tug|ferry/i.test(n) || L<90) return 'small';
  return 'ship'; }
var WK={bb:'bb', sub:'sub', carrier:'cv', cruiser:'dd'};
var DEF={bb:'The battleship', cv:'The aircraft carrier', dd:'The warship', sub:'The submarine', army:'The artillery battery', air:'The air base'};
var MINL={bb:150, cv:170, dd:96, sub:84};

/* ── plastic: a hull / plate path(k) (k = how far it is drawn inside the edge) as a slab of five stacked walls and a top, the board game's thick edge ── */
function slab(g, x, y, a, path, h, inset, foam, wave){
  function layer(up){ return el('g',{transform:'translate('+f1(x)+' '+f1(y-up)+') rotate('+f1(a)+')'},g); }
  if(foam){ var w=layer(0); el('path',{'class':'bt-foam', d:path(-4)},w); if(wave) el('path',{'class':'bt-bowwave', d:wave},w); }
  for(var i=0;i<5;i++){ var f=Math.round(136+i*8); el('path',{'class':'bb-wall', d:path(0), style:'fill:rgb('+f+','+(f+3)+','+(f+10)+')'},layer(h*i/5)); }         /* the plastic's thick edge */
  var top=layer(h); el('path',{'class':'bb-plastic', d:path(0)},top); el('path',{'class':'bb-pdeck', d:path(inset)},top); return top; }
function rr(cx, cy, w, hh, r){ return 'M'+(cx-w/2+r)+' '+(cy-hh/2)+'L'+(cx+w/2-r)+' '+(cy-hh/2)+'Q'+(cx+w/2)+' '+(cy-hh/2)+' '+(cx+w/2)+' '+(cy-hh/2+r)+'L'+(cx+w/2)+' '+(cy+hh/2-r)+'Q'+(cx+w/2)+' '+(cy+hh/2)+' '+(cx+w/2-r)+' '+(cy+hh/2)+'L'+(cx-w/2+r)+' '+(cy+hh/2)+'Q'+(cx-w/2)+' '+(cy+hh/2)+' '+(cx-w/2)+' '+(cy+hh/2-r)+'L'+(cx-w/2)+' '+(cy-hh/2+r)+'Q'+(cx-w/2)+' '+(cy-hh/2)+' '+(cx-w/2+r)+' '+(cy-hh/2)+'Z'; }
function rel(top, d){ el('path',{'class':'bb-ms', d:d, transform:'translate(1.6 2.4)'},top); return el('path',{'class':'bb-m', d:d},top); }          /* a piece in relief: shadow, then the piece */
function bump(top, cx, cy, r){ el('circle',{'class':'bb-ms', cx:cx+1.6, cy:cy+2.4, r:r},top); el('circle',{'class':'bb-m', cx:cx, cy:cy, r:r},top); }
function pegs(top, xs, r, L){ xs.forEach(function(f){ var hg=el('g',{transform:'translate('+f1(f*L)+' 0)'},top);                                  /* the peg dimples */
    el('circle',{'class':'bb-hole', r:r.toFixed(1)},hg); el('circle',{'class':'bb-hole2', cx:(r*.1).toFixed(1), cy:(r*.13).toFixed(1), r:(r*.77).toFixed(1)},hg);
    el('path',{'class':'bb-hl', d:'M'+(-r*.58)+' '+(r*.37)+'A'+(r*.75)+' '+(r*.75)+' 0 0 0 '+(r*.37)+' '+(r*.62)},hg); }); }
/* a plan jet, nose at +x, length 1 (the carrier's parked ones, the strike's flying ones) */
var JET='M.5 0L-.04-.07L-.17-.5L-.26-.5L-.23-.07L-.38-.05L-.42-.16L-.48-.16L-.46 0L-.48.16L-.42.16L-.38.05L-.23.07L-.26.5L-.17.5L-.04.07Z';
function jet(top, x, y, ang, len, cls){ el('path',{'class':'bb-ms', d:JET, transform:'translate('+f1(x+1.4)+' '+f1(y+2.2)+') rotate('+ang+') scale('+len.toFixed(1)+')', 'vector-effect':'non-scaling-stroke'},top);
  return el('path',{'class':cls||'bb-m', d:JET, transform:'translate('+f1(x)+' '+f1(y)+') rotate('+ang+') scale('+len.toFixed(1)+')'},top); }
/* a gun mount: its barrels in a group the firing code turns about abs (world point), the recoil code pulls back */
function mountAt(g, b, abs, ang, r, nb, len){ var tg=el('g',{},g), bar=el('g',{'class':'bb-bar', transform:'translate('+f1(abs[0])+' '+f1(abs[1])+') rotate('+f1(ang)+')'},tg), bls=[];
  for(var i=0;i<nb;i++){ var o=(i-(nb-1)/2)*r*.9; el('line',{'class':'bb-barrel-o', x1:(r*.3).toFixed(1), y1:o.toFixed(1), x2:(r*len).toFixed(1), y2:o.toFixed(1)},bar);
    bls.push(el('line',{'class':'bb-barrel', x1:(r*.3).toFixed(1), y1:o.toFixed(1), x2:(r*len).toFixed(1), y2:o.toFixed(1)},bar)); }
  b._tur.push({x:0, bar:bar, bl:bls, r:r, len:len, abs:abs}); }
function label(g, x, y, text, anchor){ if(!text) return; var tg=pin(g,'pl-boat-l', x, y, {}), t=el('text',{x:0,y:0,'text-anchor':anchor||'start'},tg); t.textContent=text; }

/* hull outlines (bow +x): a lens, a tapered hull with a rounded transom, a cigar, a flight deck */
function lensP(L, q, k){ var x0=-L/2+k*1.2, x1=L/2-k*1.2, w=q-k; return 'M'+x0+' 0C'+(-L*.38)+' '+(-w*.98)+' '+(-L*.1)+' '+(-w*1.02)+' '+(L*.12)+' '+(-w*.92)+'C'+(L*.3)+' '+(-w*.8)+' '+(L*.44)+' '+(-w*.34)+' '+x1+' 0C'+(L*.44)+' '+(w*.34)+' '+(L*.3)+' '+(w*.8)+' '+(L*.12)+' '+(w*.92)+'C'+(-L*.1)+' '+(w*1.02)+' '+(-L*.38)+' '+(w*.98)+' '+x0+' 0Z'; }
function hullP(L, q, k, bowK, sternK){ var x0=-L/2+k, x1=L/2-k*.3, w=q-k, bl=Math.max(L*bowK-k, 4), sw=w*sternK;
  return 'M'+x0+' '+(-sw)+'L'+(x1-bl)+' '+(-w)+'C'+(x1-bl*.5)+' '+(-w)+' '+(x1-bl*.14)+' '+(-w*.62)+' '+x1+' 0C'+(x1-bl*.14)+' '+(w*.62)+' '+(x1-bl*.5)+' '+w+' '+(x1-bl)+' '+w+'L'+x0+' '+sw+'Q'+(x0-k*.5-3)+' 0 '+x0+' '+(-sw)+'Z'; }
function spinP(L, q, k){ var x0=-L/2+k*1.2, x1=L/2-k*1.2, w=q-k;
  return 'M'+x0+' 0C'+(x0+L*.03)+' '+(-w*.85)+' '+(-L*.3)+' '+(-w)+' '+(-L*.1)+' '+(-w)+'L'+(L*.18)+' '+(-w)+'C'+(L*.36)+' '+(-w)+' '+x1+' '+(-w*.7)+' '+x1+' 0C'+x1+' '+(w*.7)+' '+(L*.36)+' '+w+' '+(L*.18)+' '+w+'L'+(-L*.1)+' '+w+'C'+(-L*.3)+' '+w+' '+(x0+L*.03)+' '+(w*.85)+' '+x0+' 0Z'; }
function deckP(L, q, k){ var x0=-L/2+k, x1=L/2-k, w=q-k, r=Math.min(w*.5, L*.04);
  return 'M'+(x0+r)+' '+(-w)+'L'+(L*.3)+' '+(-w)+'Q'+(L*.45)+' '+(-w)+' '+x1+' '+(-w*.12)+'L'+x1+' '+(w*.12)+'Q'+(L*.45)+' '+w+' '+(L*.3)+' '+w+'L'+(x0+r)+' '+w+'Q'+x0+' '+w+' '+x0+' '+(w-r)+'L'+x0+' '+(-w+r)+'Q'+x0+' '+(-w)+' '+(x0+r)+' '+(-w)+'Z'; }
function waveP(L, q){ return 'M'+(L/2+3)+' 0Q'+(L/2-L*.1)+' '+(-q*1.1)+' '+(L/2-L*.2)+' '+(-q*1.4)+'M'+(L/2+3)+' 0Q'+(L/2-L*.1)+' '+(q*1.1)+' '+(L/2-L*.2)+' '+(q*1.4); }

/* ── a warship as the board game's piece ── */
function drawToy(lg, b, bi, wk){
  var L=Math.max(b.len, MINL[wk]), W=wk==='cv'?Math.max(58, L/3.5):wk==='sub'?Math.max(24, L/7.5):wk==='dd'?Math.max(30, L/6):Math.max(46, L/4.2), q=W/2;
  var a=b.a*PI/180, ca=Math.cos(a), sa=Math.sin(a), h=Math.max(6, W*.1);
  b.len=L; b.wid=W; b.k=wk; b._tur=[];
  var g=el('g',{'class':'pl-boat wp '+wk,'data-name':b.n||'','data-kind':wk},lg); g._b=b; g._w=wk; g.style.setProperty('--pc','#8a93a3');
  g.setAttribute('aria-label', (b.n||DEF[wk])+' \u2014 click, then click a building');
  function wp(fx, fy, up){ return [b.x+ca*fx-sa*fy, b.y+sa*fx+ca*fy-(up||0)]; }
  var path=wk==='bb'?function(k){ return lensP(L, q, k); }:wk==='sub'?function(k){ return spinP(L, q, k); }:wk==='cv'?function(k){ return deckP(L, q, k); }
    :function(k){ return hullP(L, q, k, .3, .62); };
  var top=slab(g, b.x, b.y, b.a, path, h, W*.06, true, waveP(L, q));
  el('path',{d:path(0), transform:'translate('+f1(b.x)+' '+f1(b.y-h)+') rotate('+f1(b.a)+')', fill:'rgba(0,0,0,0)', stroke:'rgba(0,0,0,0)', 'stroke-width':14, 'vector-effect':'non-scaling-stroke'},g);      /* a thin hull is still easy to click */
  el('path',{'class':'bb-gloss', d:'M'+(-L*.3)+' '+(-q*.74)+'C'+(-L*.1)+' '+(-q*.84)+' '+(L*.1)+' '+(-q*.78)+' '+(L*.3)+' '+(-q*.55)+'L'+(L*.28)+' '+(-q*.5)+'C'+(L*.1)+' '+(-q*.68)+' '+(-L*.1)+' '+(-q*.72)+' '+(-L*.3)+' '+(-q*.64)+'Z'},top);
  if(wk==='bb') toyBB(g, b, top, L, W, q, h, wp);
  else if(wk==='dd') toyDD(g, b, top, L, W, q, h, wp);
  else if(wk==='cv') toyCV(g, b, top, L, W, q, h, wp);
  else toySub(g, b, top, L, W, q, h, wp);
  el('title',{},g).textContent=(b.n||DEF[wk])+(wk==='bb'?' \u2014 click to man the guns':' \u2014 click to arm it');
  var s1=wp(0, q+12), s2=wp(0, -(q+12)), sp=s1[0]>=s2[0]?s1:s2; label(g, sp[0], sp[1], b.n);
}
/* USS New Jersey, as 1.9.97: four peg dimples down its deck (at the stern, in a raised block, in the bridge and at the bow), a twin mount fore and aft, a funnel and a bridge in relief,
   engraved lines along the stern. */
function toyBB(g, b, top, L, W, q, h, wp){
  for(var k=0;k<6;k++){ var yy=(k-2.5)*q*.17; el('line',{'class':'bb-eng', x1:(-L*.46+Math.abs(yy)*.5).toFixed(1), y1:yy.toFixed(1), x2:(-L*.31).toFixed(1), y2:yy.toFixed(1)},top); }             /* the engraved lines at the stern */
  rel(top, rr(-.13*L, 0, L*.125, W*.5, W*.16));
  [[-.04*L,-W*.1,W*.1],[-.035*L,W*.12,W*.08],[.016*L,0,W*.07]].forEach(function(c){ bump(top, c[0], c[1], c[2]); });
  rel(top, 'M'+(.06*L)+' '+(-W*.2)+'L'+(.15*L)+' '+(-W*.22)+'Q'+(.21*L)+' '+(-W*.1)+' '+(.235*L)+' 0Q'+(.21*L)+' '+(W*.1)+' '+(.15*L)+' '+(W*.22)+'L'+(.06*L)+' '+(W*.2)+'Q'+(.04*L)+' 0 '+(.06*L)+' '+(-W*.2)+'Z');
  rel(top, rr(-.245*L, 0, L*.06, W*.4, W*.1)); rel(top, rr(.29*L, 0, L*.07, W*.36, W*.12));                                           /* the bases of the two gun mounts */
  pegs(top, [-.40,-.13,.125,.38], W*.12, L);
  mountAt(g, b, wp(.29*L, 0, h+2), b.a, W*.17, 2, 2.0); mountAt(g, b, wp(-.245*L, 0, h+2), b.a+180, W*.17, 2, 2.0);
}
/* a cruiser / destroyer: a bridge, two funnel bumps, a block of missile launch cells, a single mount fore and aft; three pegs */
function toyDD(g, b, top, L, W, q, h, wp){
  rel(top, rr(.12*L, 0, L*.11, W*.5, W*.15)); bump(top, -.01*L, -W*.12, W*.1); bump(top, -.01*L, W*.12, W*.1);
  rel(top, rr(.30*L, 0, L*.05, W*.34, W*.1)); rel(top, rr(-.34*L, 0, L*.05, W*.34, W*.1));
  var vl=rel(top, rr(-.17*L, 0, L*.13, W*.46, W*.05)); b._cells=[];
  for(var i=0;i<4;i++) for(var j=0;j<2;j++){ var cx=(-.17+(i-1.5)*.027)*L, cy=(j-.5)*W*.19; el('rect',{'class':'bb-hole2', x:f1(cx-W*.05), y:f1(cy-W*.055), width:f1(W*.1), height:f1(W*.11), rx:1},top); }
  [[-.215,-1],[-.19,1],[-.165,-1],[-.14,1]].forEach(function(c){ b._cells.push(wp(c[0]*L, c[1]*W*.1, h+2)); });
  pegs(top, [-.46,.215,.41], W*.1, L);
  mountAt(g, b, wp(.30*L, 0, h+2), b.a, W*.17, 1, 2.2); mountAt(g, b, wp(-.34*L, 0, h+2), b.a+180, W*.17, 1, 2.2);
}
/* an aircraft carrier: the whole piece is the flight deck, with the angled landing strip, two lifts, the island on the starboard edge and a few jets parked aft */
function toyCV(g, b, top, L, W, q, h, wp){
  el('path',{'class':'fl-run', d:'M'+(-.44*L)+' '+(-.1*q)+'L'+(.18*L)+' '+(-.68*q)+'L'+(.2*L)+' '+(-.5*q)+'L'+(-.44*L)+' '+(.12*q)+'Z'},top);
  el('line',{'class':'fl-dash', x1:-.43*L, y1:-.0*q, x2:.19*L, y2:-.59*q},top);
  el('line',{'class':'fl-dash', x1:-.2*L, y1:.18*q, x2:.42*L, y2:.18*q},top);                                                                 /* the straight runway's centre line */
  el('rect',{'class':'fl-el', x:f1(-.06*L), y:f1(.38*q), width:f1(.07*L), height:f1(.34*q), rx:2},top); el('rect',{'class':'fl-el', x:f1(.27*L), y:f1(.3*q), width:f1(.06*L), height:f1(.3*q), rx:2},top);
  rel(top, rr(.14*L, .74*q, L*.1, q*.3, q*.08)); bump(top, .13*L, .74*q, q*.07); el('line',{'class':'bb-eng', x1:f1(.18*L), y1:f1(.74*q), x2:f1(.22*L), y2:f1(.74*q)},top);
  [[-.40,.48,-8],[-.35,.7,5],[-.29,.42,0],[-.24,.72,-6],[-.16,.55,9]].forEach(function(p){ jet(top, p[0]*L, p[1]*q, p[2], q*.62); });
  pegs(top, [-.42,-.30,0.0,.30,.42].map(function(v){ return v; }), W*.045, L);
  /* the catapults: where the strike's jets stand when they start their run (world points) and the heading they take off on */
  b._launch=[[-.12,-.28],[-.2,.0],[-.12,.28],[-.2,-.0],[-.04,.0]].map(function(p){ return wp(p[0]*L, p[1]*q, h+3); });
}
/* a submarine: a cigar with its conning tower and periscope, tail fins, a deck line, three pegs */
function toySub(g, b, top, L, W, q, h, wp){
  el('line',{'class':'bb-eng', x1:f1(-L*.4), y1:0, x2:f1(L*.4), y2:0},top);
  rel(top, rr(-.44*L, -W*.42, L*.05, W*.16, 2)); rel(top, rr(-.44*L, W*.42, L*.05, W*.16, 2));
  rel(top, rr(.04*L, 0, L*.13, W*.4, W*.2)); el('circle',{'class':'bb-hole2', cx:f1(.07*L), cy:0, r:f1(W*.06)},top);
  pegs(top, [-.3,-.14,.27], W*.1, L);
  b._muzzle=wp(L*.5, 0, h);
}
/* ── a base: a plate with its guns (army) or its runway and jets (air) ── */
function drawBase(lg, s, bi){
  var r=s.r||60, wk=s.k==='air'?'air':'army', hs=0; for(var i=0;i<(s.n||'x').length;i++) hs=(hs*31+(s.n||'x').charCodeAt(i))|0;
  s.a=wk==='air'?((Math.abs(hs)%5)-2)*9:0; s.len=r*2; s.wid=r*1.2; s._tur=[]; s.k=wk;
  var g=el('g',{'class':'pl-boat pl-base wp '+wk,'data-name':s.n||'','data-kind':wk},lg); g._b=s; g._w=wk; g.setAttribute('aria-label', (s.n||DEF[wk])+' \u2014 click, then click a building');
  var hh=r*.78, cr=r*.16, h=Math.max(5, r*.07), a=s.a*PI/180, ca=Math.cos(a), sa=Math.sin(a);
  function wp(fx, fy, up){ return [s.x+ca*fx-sa*fy, s.y+sa*fx+ca*fy-(up||0)]; }
  var top=slab(g, s.x, s.y, s.a, function(k){ return rr(0, 0, 2*r-2*k, 2*hh-2*k, cr); }, h, r*.05, false);
  el('path',{'class':'bb-gloss', d:'M'+(-r*.85)+' '+(-hh*.78)+'L'+(r*.5)+' '+(-hh*.78)+'L'+(r*.38)+' '+(-hh*.66)+'L'+(-r*.85)+' '+(-hh*.66)+'Z'},top);
  [[-.9,-.7],[.9,-.7],[-.9,.7],[.9,.7]].forEach(function(p){ el('circle',{'class':'bb-hole', cx:f1(p[0]*r), cy:f1(p[1]*hh), r:f1(r*.035)},top); });
  if(wk==='army'){
    [[-.5,-.22],[0,-.3],[.5,-.22]].forEach(function(p){ el('circle',{'class':'bb-pad', cx:f1(p[0]*r), cy:f1(p[1]*r), r:f1(r*.22)},top); bump(top, p[0]*r, p[1]*r, r*.11); });
    [[-.42,.38],[.18,.4]].forEach(function(p,i){ var x=p[0]*r, y=p[1]*r, w=r*.34, t=r*.2; rel(top, rr(x, y, w, t, 3)); bump(top, x-w*.04, y, t*.34);
      el('line',{'class':'bb-barrel', x1:f1(x), y1:f1(y), x2:f1(x+w*.62), y2:f1(y), 'stroke-width':2.4},top); });
    rel(top, rr(.62*r, .46*r, r*.16, r*.1, 2)); rel(top, rr(.7*r, .26*r, r*.1, r*.1, 2));
    [[-.5,-.22],[0,-.3],[.5,-.22]].forEach(function(p){ mountAt(g, s, wp(p[0]*r, p[1]*r, h+2), -90, r*.12, 1, 2.4); });
    label(g, s.x+r*.1, s.y+hh+14, s.n, 'middle');
  } else {
    el('rect',{'class':'fl-run', x:f1(-.94*r), y:f1(-.1*r), width:f1(1.88*r), height:f1(.2*r), rx:2},top);
    el('line',{'class':'fl-dash', x1:-.88*r, y1:0, x2:.88*r, y2:0},top);
    el('path',{'class':'fl-run', d:'M'+(-.5*r)+' '+(.1*r)+'L'+(-.4*r)+' '+(.1*r)+'L'+(-.3*r)+' '+(.26*r)+'L'+(-.5*r)+' '+(.26*r)+'Z'},top);
    rel(top, rr(.0*r, .5*r, r*.5, r*.26, 3)); el('line',{'class':'bb-eng', x1:f1(-.2*r), y1:f1(.5*r), x2:f1(.2*r), y2:f1(.5*r)},top);
    rel(top, rr(.58*r, .42*r, r*.12, r*.12, 3)); bump(top, .58*r, .42*r, r*.035);
    jet(top, -.62*r, .5*r, -90, r*.34); jet(top, -.8*r, .46*r, -90, r*.34); jet(top, .3*r, -.45*r, 180, r*.0);
    s._rw=[wp(-.94*r, 0, h+3), wp(.94*r, 0, h+3)];
    label(g, s.x+r*.1, s.y+hh+14, s.n, 'middle');
  }
  el('title',{},g).textContent=(s.n||DEF[wk])+' \u2014 click to arm it';
}
/* ── the boats that are no warship: a hull, its deck, and the upright parts (glass towers, funnels, masts and sails) in the buildings' own lean ── */
function drawBoat(lg, b, bi){
  var kind=boatKind(b.n, b.len, b.wid), wk=b.k||WK[kind]||'';
  if(wk){ drawToy(lg, b, bi, wk); return; }
  var L=b.len, W=b.wid, a=b.a*PI/180, ca=Math.cos(a), sa=Math.sin(a), q=W/2;
  var g=el('g',{'class':'pl-boat '+kind,'data-name':b.n||'','data-kind':kind},lg); g.style.setProperty('--pc', kind==='tall'?'#7b6a54':'#5d6f92');
  function wp(fx, fy){ return [b.x+ca*fx-sa*fy, b.y+sa*fx+ca*fy]; }                        /* hull coordinates (bow +x, port -y) -> the map */
  var rot=el('g',{transform:'translate('+b.x+' '+b.y+') rotate('+b.a+')'},g), bowK=kind==='tall'?.2:kind==='small'?.22:.26, stern=.82;
  el('path',{'class':'bt-foam', d:hullP(L, q, -4, bowK, Math.min(1,stern+.08))},rot);
  el('path',{'class':'bt-bowwave', d:'M'+(L/2+3)+' 0Q'+(L/2-L*.1)+' '+(-q*1.15)+' '+(L/2-L*.2)+' '+(-q*1.5)+'M'+(L/2+3)+' 0Q'+(L/2-L*.1)+' '+(q*1.15)+' '+(L/2-L*.2)+' '+(q*1.5)},rot);
  el('path',{'class':'bt-hull', d:hullP(L, q, 0, bowK, stern)},rot);
  el('path',{'class':'bt-boot', d:hullP(L, q, 1.6, bowK, stern)},rot);                                                              /* the red waterline stripe */
  el('path',{'class':'bt-deck '+(kind==='tall'?'wood':''), d:hullP(L, q, Math.min(5, W*.16), bowK*1.02, stern)},rot);
  el('line',{'class':'bt-cl', x1:-L/2+W*.2, y1:0, x2:L/2-L*bowK*.7, y2:0},rot);
  if(kind==='tall'){ for(var k=-L/2+L*.1; k<L/2-L*.22; k+=Math.max(5, L*.045)) el('line',{'class':'bt-plank', x1:k, y1:-q*.8, x2:k, y2:q*.8},rot); }
  var seq=0; function block(fx, fy, bl, bwid, hh){ var c=wp(fx, fy); H.nbDraw(g, [0,0,bl,bwid,b.a], hh, c[0], c[1], 'boat'+bi+'_'+(seq++)); return c; }
  function funnel(fx, fy, r, hh){ var c=wp(fx, fy); var d=el('g',{'class':'bt-fun'},g);
    el('path',{'class':'bt-fb', d:'M'+(c[0]-r)+' '+c[1]+'L'+(c[0]-r)+' '+(c[1]-hh)+'A'+r+' '+(r*.45)+' 0 0 1 '+(c[0]+r)+' '+(c[1]-hh)+'L'+(c[0]+r)+' '+c[1]+'A'+r+' '+(r*.45)+' 0 0 1 '+(c[0]-r)+' '+c[1]+'Z'},d);
    el('ellipse',{'class':'bt-ft', cx:c[0], cy:c[1]-hh, rx:r, ry:r*.45},d); el('ellipse',{'class':'bt-fh', cx:c[0], cy:c[1]-hh, rx:r*.62, ry:r*.26},d); }
  function mast(fx, fy, hh){ var c=wp(fx, fy); el('line',{'class':'bt-mast', x1:c[0], y1:c[1], x2:c[0], y2:c[1]-hh},g); return c; }
  var H0=Math.max(16, Math.min(60, L*.17)), yards=[.4,.62,.82,1];
  if(kind==='tall'){ var n=Math.max(2, Math.min(4, Math.round(L/42))), tp=Math.max(30, Math.min(L*.27, W*2.8));
    for(var i=0;i<n;i++){ var fx=(-.30+(.58*i/(n-1||1)))*L, c=mast(fx, 0, tp);
      yards.forEach(function(f, yi){ var hh=tp*f, wd=q*(1.3-yi*.12); var p1=[c[0]+(-sa*-wd), c[1]-hh+(ca*-wd)], p2=[c[0]+(-sa*wd), c[1]-hh+(ca*wd)];
        el('line',{'class':'bt-yard', x1:p1[0], y1:p1[1], x2:p2[0], y2:p2[1]},g);
        if(yi>0){ var h0=tp*yards[yi-1], w0=q*(1.3-(yi-1)*.12), a1=[c[0]+(-sa*-w0), c[1]-h0+(ca*-w0)], a2=[c[0]+(-sa*w0), c[1]-h0+(ca*w0)];
          el('polygon',{'class':'bt-sail', points:[a1,a2,p2,p1].map(function(v){ return v[0].toFixed(1)+','+v[1].toFixed(1); }).join(' ')},g); } }); }
    block(.36, 0, L*.06, W*.4, H0*.45); }
  else { block(.02, 0, L*.22, W*.5, H0*(kind==='small'?.7:1)); if(kind!=='small') funnel(-.12, 0, W*.13, H0*.9); mast(.12, 0, H0*1.7); }
  el('title',{},g).textContent=b.n||'A boat';
  if(b.n){ var tg=pin(g,'pl-boat-l', b.x, b.y-W*.5-H0*(kind==='tall'?1.0:1.5)-2, {}); var t=el('text',{x:0,y:-3,'text-anchor':'middle'},tg); t.textContent=b.n; }
}
"""
