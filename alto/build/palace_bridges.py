"""The Mind Palace's bridges: a deck with design elements, still one calm line weight (data: M.streets with o=1, M.river).

A bridge is a street that crosses water (or a rail / road): palace.py draws its deck (a light band between two fine rail lines) and the
street's own tube on it. This module gives each bridge a character, read from the plan view, by what it crosses:

  * a SUSPENSION bridge (the street crosses the wide river, or is a named big one such as the Ben Franklin, Walt Whitman, Betsy Ross):
    a fine cable line along each rail, hangers ticked across the deck at a close rhythm, and two towers (an H-frame: a crossbar between
    two end caps) standing at a fifth and four fifths of the span;
  * an ARCH / girder bridge (a street over the narrow river: the Market, Chestnut, Walnut, Arch, Girard Avenue bridges): parapet pilasters
    (the dashed thicker edge), expansion-joint ticks across the deck at a slow rhythm, piers ticked out into the water;
  * a VIADUCT (a street over a rail line or a road, no river under it): pilasters and joints only;
  * every bridge: an abutment block (a short bar across the deck) where the deck leaves each bank.

Everything is measured on the SCREEN, like the rest of the page: strokes and dash lengths are calc(var(--tw) * Npx) (--tw is the map unit
of one screen px, set by placeAll), and the towers / abutments are pin()s (a translate in map units, a unitless CSS scale inside), so
nothing is a px inside a CSS transform on SVG content (Safari zooms those) and the rhythm holds at every zoom. The decoration is drawn on
the stretch over the water (+ a few px of bank), found once from the river course; svg.far keeps only the abutments, towers and cables.

  window._palBr.init({M, el, pts, pin})
  window._palBr.under(parent, st, d) -> plan   pier / pilaster / cable / edge / casing / joint layers (the deck); the tube goes on top
  window._palBr.over(parent, plan)             abutments and towers, above the street's tube
"""

BRIDGE_CSS = r"""
  /* ═══ BRIDGES (palace_bridges.py): delimited block ═══ */
  html{--pal-br-fine:rgba(44,52,84,.74);--pal-br-joint:rgba(44,52,84,.34);--pal-br-hang:rgba(44,52,84,.34);}
  html.dark{--pal-br-fine:rgba(222,229,248,.78);--pal-br-joint:rgba(222,229,248,.32);--pal-br-hang:rgba(222,229,248,.34);}
  .pal-svg .pl-bridges .br-d{fill:none;stroke-linecap:butt;stroke-linejoin:round;pointer-events:none;}
  .pal-svg .pl-bridges .br-pil{stroke:var(--pal-br-edge);stroke-width:calc(var(--tw,1) * 18.4px);
    stroke-dasharray:calc(var(--tw,1) * 2.3px) calc(var(--tw,1) * 13.7px);}
  .pal-svg .pl-bridges .br-d.pl-br-pier{stroke-width:calc(var(--tw,1) * 25px);stroke-dasharray:calc(var(--tw,1) * 2px) calc(var(--tw,1) * 52px);}
  .pal-svg .pl-bridges .br-cable{stroke:var(--pal-br-fine);stroke-width:calc(var(--tw,1) * 18px);}
  .pal-svg .pl-bridges .br-joint{stroke:var(--pal-br-joint);stroke-width:calc(var(--tw,1) * 12.4px);
    stroke-dasharray:calc(var(--tw,1) * 1px) calc(var(--tw,1) * 23px);}
  .pal-svg .pl-bridges .br-hang{stroke:var(--pal-br-hang);stroke-width:calc(var(--tw,1) * 12.4px);
    stroke-dasharray:calc(var(--tw,1) * .8px) calc(var(--tw,1) * 9.2px);}
  .pal-svg .pl-bridges .br-abut,.pal-svg .pl-bridges .br-tower{pointer-events:none;}
  .pal-svg .pl-bridges .br-abut rect,.pal-svg .pl-bridges .br-tower rect{fill:var(--pal-br-fine);}
  .pal-svg.far .pl-bridges :is(.br-pil,.br-joint,.br-hang){display:none;}
"""

BRIDGE_JS = r"""
/* ═══ BRIDGES (palace_bridges.py) ═══ */
(function(){
if(window._palBr) return;
var E=null, RV=[], PLANS=[], SUS_NAME=/franklin|whitman|betsy ross|tacony|palmyra/i;
var BANK=8, WIDE=200, STEP=4;        /* map px: the decoration runs this far past the water's edge; a river this wide is a suspension crossing */
function init(e){ E=e; RV=[]; PLANS.length=0; (E.M.river||[]).forEach(function(r){ var p=r.p||[]; if(p.length<4) return; var hw=(r.w||100)/2+6, x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
    for(var i=0;i<p.length;i+=2){ x0=Math.min(x0,p[i]); x1=Math.max(x1,p[i]); y0=Math.min(y0,p[i+1]); y1=Math.max(y1,p[i+1]); }
    RV.push({p:p, hw:hw, w:r.w||100, x0:x0-hw, y0:y0-hw, x1:x1+hw, y1:y1+hw}); }); }
/* the width of the river whose water (rim included) holds (x,y), or 0 */
function wet(x,y){ var best=0, bw=0;
  for(var k=0;k<RV.length;k++){ var r=RV[k]; if(x<r.x0||x>r.x1||y<r.y0||y>r.y1) continue; var p=r.p, d2=1e18;
    for(var i=0;i+3<p.length;i+=2){ var ax=p[i], ay=p[i+1], dx=p[i+2]-ax, dy=p[i+3]-ay, L2=dx*dx+dy*dy||1e-9, t=Math.max(0,Math.min(1,((x-ax)*dx+(y-ay)*dy)/L2)), qx=ax+t*dx-x, qy=ay+t*dy-y, q=qx*qx+qy*qy; if(q<d2) d2=q; }
    var ins=r.hw-Math.sqrt(d2); if(ins>best){ best=ins; bw=r.w; } }
  return best>0?bw:0; }
/* the point and heading (degrees) s px along the path */
function at(P, L, s){ var a=0; s=Math.max(0,Math.min(L,s));
  for(var i=0;i+3<P.length;i+=2){ var dx=P[i+2]-P[i], dy=P[i+3]-P[i+1], l=Math.hypot(dx,dy); if(l<1e-6) continue;
    if(a+l>=s || i+4>=P.length){ var t=Math.max(0,Math.min(1,(s-a)/l)); return {x:P[i]+dx*t, y:P[i+1]+dy*t, a:Math.atan2(dy,dx)*180/Math.PI}; } a+=l; }
  return {x:P[0], y:P[1], a:0}; }
function slice(P, L, a, b){ var o=[], s=0, A=at(P,L,a); o.push(A.x,A.y);
  for(var i=0;i+3<P.length;i+=2){ s+=Math.hypot(P[i+2]-P[i], P[i+3]-P[i+1]); if(s>a && s<b) o.push(P[i+2],P[i+3]); }
  var B=at(P,L,b); o.push(B.x,B.y); return o; }
function edge(P, L, lo, hi, out){ for(var k=0;k<7;k++){ var m=(lo+hi)/2, q=at(P,L,m), on=wet(q.x,q.y)>0; if(on===!!out) lo=m; else hi=m; } return out?lo:hi; }
/* the stretch of the path over water: {a, b, w} (px along it; w the widest river under it), or null if it crosses none */
function wetSpan(P, L){ var s0=-1, s1=-1, w=0, prev=false, ps=0;
  for(var s=0;s<L+STEP;s+=STEP){ var c=Math.min(s,L), q=at(P,L,c), ww=wet(q.x,q.y), on=ww>0;
    if(on){ if(s0<0) s0=prev||c===0?c:edge(P,L,ps,c,false); s1=c; w=Math.max(w,ww); }
    else if(prev){ s1=edge(P,L,ps,c,true); }
    prev=on; ps=c; }
  return s0<0?null:{a:s0, b:s1, w:w}; }
function under(parent, st, d){
  var P=st.p, L=0, i; for(i=0;i+3<P.length;i+=2) L+=Math.hypot(P[i+2]-P[i], P[i+3]-P[i+1]);
  var sp=RV.length?wetSpan(P,L):null, sus=!!sp && (sp.w>=WIDE || (st.br && SUS_NAME.test(st.n||''))), type=sus?'sus':sp?'arch':'via';
  var a=sp?Math.max(0,sp.a-BANK):0, b=sp?Math.min(L,sp.b+BANK):L, plan={type:type, P:P, L:L, a:a, b:b};
  var mid=at(P,L,(a+b)/2); PLANS.push({n:st.n, type:type, L:Math.round(L), a:Math.round(a), b:Math.round(b), x:Math.round(mid.x), y:Math.round(mid.y)});
  var deck=(a>0||b<L)?E.pts(slice(P,L,a,b)):d;
  var pt=function(cls){ return E.el('path',{'class':'br-d '+cls, d:deck},parent); };
  if(type==='arch') pt('pl-br-pier');                     /* piers: the existing ticks, now only over the water */
  if(type!=='sus') pt('br-pil'); else pt('br-cable');
  E.el('path',{'class':'pl-br-edge', d:d},parent); E.el('path',{'class':'pl-casing', d:d},parent);
  pt(type==='sus'?'br-hang':'br-joint');
  return plan; }
/* above the street's tube: an abutment (a bar across the deck) where it leaves each bank; on a suspension bridge a tower (an H-frame:
   a crossbar between two end caps) at a fifth and four fifths of the span. Drawn in a rotated group inside the screen-scaled pin. */
function over(parent, plan){
  var P=plan.P, L=plan.L;
  function rot(g, o){ return E.el('g',{transform:'rotate('+o.a.toFixed(2)+')'},g); }
  if(plan.b-plan.a<12) return;
  [plan.a, plan.b].forEach(function(s){ var o=at(P,L,s), r=rot(E.pin(parent,'br-abut',o.x,o.y),o);
    E.el('rect',{x:-1.7,y:-9.8,width:3.4,height:19.6,rx:.9},r); });
  if(plan.type==='sus' && plan.b-plan.a>60){ [.2,.8].forEach(function(f){ var o=at(P,L,plan.a+(plan.b-plan.a)*f), r=rot(E.pin(parent,'br-tower',o.x,o.y),o);
    E.el('rect',{x:-3.2,y:-17,width:6.4,height:8.4,rx:1.4},r); E.el('rect',{x:-3.2,y:8.6,width:6.4,height:8.4,rx:1.4},r);
    E.el('rect',{x:-1,y:-9,width:2,height:18},r); }); } }
window._palBr={init:init, under:under, over:over, plans:PLANS, _wet:wet, _span:wetSpan};
})();
"""
