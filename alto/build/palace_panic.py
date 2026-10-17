"""1.9.97: when the battleship's shell brings a building down, the people in it run for their lives.

A crowd of 8-16 stick figures (a head dot and one stroked path: body, two arms, two legs, redrawn every frame as a walk cycle) spills out of
the struck building's foot and runs away along the real street graph (the page's own graph(), nearest() and route(): every figure picks a street
corner about 200 screen px away in its own direction and runs the route to it). Arms wave, a third of them trip and get up,
two stop and look back, small pills pop up and fade ("AAAH!", "RUN!", "HELP!"), and three of them stop at the end of their street and stand
watching the construction until the rebuilt building is shown (they fade with it, 20 s after the shell, as palace_construct.py's layer does).

Sizes are measured on the SCREEN: each figure is `pin()`-ed (a translate attribute in map units around a unitless --tw scale), so it keeps
its 6-8 px at every zoom in Safari too; everything moves by SVG attributes from one requestAnimationFrame loop (no CSS px in transforms,
no filters, no mask), at most 16 figures x 2 shapes + a handful of bubbles. prefers-reduced-motion: no crowd. Esc / "stand down" and a
re-shelled building remove the crowd; a crowd that has lost its svg is dropped. `_palPanic.freeze(ms)` shows any instant exactly (QA).
"""
from __future__ import annotations

PANIC_JS = r"""
/* ── people running and screaming from a collapsing building (palace_panic.py) ── */
window._palPanic=(function(){
var runs=[], raf=0, FORCE=null, END=20000, TXT=['AAAH!','RUN!','HELP!','AAAH!','!!'], R=Math.random;
function cl(x){ return x<0?0:(x>1?1:x); }
function sm(x){ x=cl(x); return x*x*(3-2*x); }
function setO(e, o){ var k=o>.01; if(e._v!==k){ e._v=k; if(k) e.removeAttribute('display'); else e.setAttribute('display','none'); } if(k) e.setAttribute('opacity', o.toFixed(2)); }
function at(f, s){ var c=f.cum, i=1; while(i<c.length-1 && c[i]<s) i++; var a=f.pts[i-1], b=f.pts[i], u=cl((s-c[i-1])/((c[i]-c[i-1])||1)); return [a[0]+(b[0]-a[0])*u, a[1]+(b[1]-a[1])*u, b[0]-a[0]]; }
function nodes(g, x, y, r, fn){ for(var i=-r;i<=r;i++) for(var j=-r;j<=r;j++) (g.NG[(Math.floor(x/120)+i)+','+(Math.floor(y/120)+j)]||[]).forEach(function(k){ fn(k, Math.hypot(g.X[k]-x, g.Y[k]-y)); }); }
function crowd(C, el_, X, Y, W){
  var el=C.el, Z=C.Z, g=C.graph(), dk=C.dk, col=dk?'rgb(214,218,232)':'rgb(52,56,76)', alt=dk?['#f0a08c','#8fc3e8','#b9d98a']:['#c0563f','#3f7fb0','#6f8f33'];
  var layer=el('g',{'class':'pl-fx pl-panic'}, C.svg), n=runs.length?8:(W>120?15:11), figs=[], bubs=[], sn=-1, bd=1e12, D=Math.min(900, 215/Z), cs=[], i, j;
  nodes(g, X, Y, 5, function(k, d){ if(g.Y[k]>=Y-8 && d<bd){ bd=d; sn=k; } });          /* the street corner nearest the door, on the front side (not behind the ruin) */
  if(sn<0) sn=C.nearest(X, Y, 0, 520);
  if(sn>=0) nodes(g, g.X[sn], g.Y[sn], Math.ceil(D/120), function(k, d){ if(d>D*.45 && d<D) cs.push(k); });
  for(i=0;i<n;i++){
    var th=i/n*6.283+R()*.6, ox=(R()-.5)*5/Z, oy=(R()-.5)*5/Z, pts=[[X+(R()-.5)*8/Z, Y]], best=null, bs=9, rt=null;
    cs.forEach(function(k){ var d=Math.abs(((Math.atan2(g.Y[k]-g.Y[sn], g.X[k]-g.X[sn])-th)%6.283+9.425)%6.283-3.1416)+R()*.35; if(d<bs){ bs=d; best=k; } });
    if(best!=null && sn>=0) rt=C.route(sn, best);
    if(rt) rt.forEach(function(k){ pts.push([g.X[k]+ox, g.Y[k]+oy]); }); else pts.push([X+Math.cos(th)*D*.6, Y+Math.sin(th)*D*.45]);          /* no street near: straight out and away */
    var cum=[0], p2=[pts[0]], tot=0, dur=3.2+R()*1.6, v, cap, a, b, l;
    for(j=1;j<pts.length;j++) tot+=Math.hypot(pts[j][0]-pts[j-1][0], pts[j][1]-pts[j-1][1]);
    v=Math.max(50/Z, Math.min(135/Z, tot/dur)); cap=v*dur;                                         /* 3-5 s of running, 50-135 screen px a second */
    for(j=1;j<pts.length;j++){ a=p2[j-1]; b=pts[j]; l=Math.hypot(b[0]-a[0], b[1]-a[1]); if(cum[j-1]+l>cap){ l=(cap-cum[j-1])/l; p2.push([a[0]+(b[0]-a[0])*l, a[1]+(b[1]-a[1])*l]); cum.push(cap); break; } p2.push(b); cum.push(cum[j-1]+l); }
    if(p2.length<2){ p2.push([X+1, Y]); cum.push(1); }
    var pa=C.pin(layer, 'pl-pp', X, Y, {}), use=(i%5===3)?alt[i%3]:col,
      f={og:pa.parentNode, head:el('circle',{r:1.7, fill:use},pa), body:el('path',{fill:'none', stroke:use, 'stroke-width':1.4, 'stroke-linecap':'round', 'stroke-linejoin':'round'},pa),
        pts:p2, cum:cum, L:cum[cum.length-1], v:v, d0:R()*620+i*28, k:.95+R()*.25, m:R()<.55, w:i===2||i===5||i===8, ps:null, ph0:R()*6, dir:1, x:X, y:Y};
    if(i===1||i===4) f.ps={t0:1500+R()*1100, dur:900, look:1}; else if(R()<.34) f.ps={t0:650+R()*1500, dur:1200};         /* a couple look back; a third trip and get up */
    f.tArr=f.d0+f.L/v*1000+(f.ps?f.ps.dur:0); figs.push(f);
    if(i%2 && bubs.length<7){ var tx=TXT[bubs.length%5], w=tx.length*5.2+8, bg=el('g',{display:'none'},C.pin(layer,'pl-pb',X,Y,{}));
      el('rect',{x:-w/2, y:-6.5, width:w, height:11, rx:5.5, fill:dk?'#262a3a':'#fff', stroke:col, 'stroke-opacity':.55, 'stroke-width':.8}, bg);
      el('text',{y:2, 'text-anchor':'middle', 'font-size':8, 'font-weight':800, fill:dk?'#ffb3a6':'#b8321f'}, bg).textContent=tx;
      bubs.push({f:f, t0:f.d0+900+R()*2200, g:bg, og:bg.parentNode.parentNode}); }
  }
  var c={layer:layer, key:el_, figs:figs, bubs:bubs, cx:X, t0:performance.now()};
  c.kill=function(){ if(layer.parentNode) layer.parentNode.removeChild(layer); var q=runs.indexOf(c); if(q>=0) runs.splice(q,1); };
  return c;
}
/* one figure at time t (ms after the shell): where it is, how it moves, drawn as one path */
function pose(f, t, cx){
  var u=t-f.d0, ph, amp=1, mode=f.m?1:0, rot=0, run=true, ps=f.ps, dir=f.dir, s, p, q, o;
  if(u<0){ setO(f.og, 0); return; }
  if(ps){ if(u>=ps.t0+ps.dur) u-=ps.dur; else if(u>=ps.t0){ q=(u-ps.t0)/ps.dur; u=ps.t0; run=false; mode=0;
    if(ps.look){ dir=cx>f.x?1:-1; amp=0; } else { rot=1.45*(q<.2?sm(q/.2):(q<.62?1:1-sm((q-.62)/.38))); amp=.25; } } }
  s=Math.min(f.L, f.v*u/1000); p=at(f, s);
  var home=s>=f.L-.01 && run;
  if(home){ amp=0; mode=f.w?4:2; dir=cx>p[0]?1:-1; } else if(run && Math.abs(p[2])>.2) dir=p[2]>0?1:-1;
  f.dir=dir; f.x=p[0]; f.y=p[1]; ph=f.ph0+u/1000*19.5; if(mode===1 && u<1300) mode=0;
  o=cl(u/170)*(f.w?1-sm((t-17000)/2700):1-sm((t-f.tArr-300)/700)); setO(f.og, o); if(o<=.01) return;
  f.og.setAttribute('transform', 'translate('+p[0].toFixed(1)+' '+p[1].toFixed(1)+')');
  var k=f.k, a=Math.sin(ph), lean=run&&!home?.9:0, c=Math.cos(rot*dir), sn=Math.sin(rot*dir), e=1.1*(1-amp), w=Math.sin(t/260+f.ph0);
  function P(x, y){ x*=dir*k; y*=k; return [x*c-y*sn, x*sn+y*c]; }
  function S(z){ return z[0].toFixed(1)+' '+z[1].toFixed(1); }
  var sh=P(lean,-5.6), hip=P(0,-3), hd=P(lean*1.2,-6.9), fa=P(a*2.6*amp+e, -Math.max(0,Math.cos(ph))*1.3*amp), fb=P(-a*2.6*amp-e, -Math.max(0,-Math.cos(ph))*1.3*amp), h1=P(1.5,-3.4), h2=P(-1.5,-3.4);
  if(mode===0){ h1=P(lean+2.5, -8.4+Math.sin(ph*1.6)*1.5); h2=P(lean-2.5, -8.4+Math.cos(ph*1.6)*1.5); }
  else if(mode===1){ h1=P(lean-a*2.4, -4.2); h2=P(lean+a*2.4, -4.2); }
  else if(mode===4) h2=P(-2.6, -7.6+w*1.1);
  f.head.setAttribute('cx', hd[0].toFixed(1)); f.head.setAttribute('cy', hd[1].toFixed(1)); f.head.setAttribute('r', (1.7*k).toFixed(2));
  f.body.setAttribute('d', 'M'+S(sh)+'L'+S(hip)+'L'+S(fa)+'M'+S(hip)+'L'+S(fb)+'M'+S(sh)+'L'+S(h1)+'M'+S(sh)+'L'+S(h2));
}
function bubble(b, t){
  var age=t-b.t0, f=b.f, on=age>=0 && age<1100 && f.og._v;
  b.g.setAttribute('display', on?'inline':'none'); if(!on) return;
  var k=age<140?.3+.85*age/140:(age<230?1.15-.15*(age-140)/90:1);
  b.og.setAttribute('transform', 'translate('+f.x.toFixed(1)+' '+f.y.toFixed(1)+')'); b.g.setAttribute('transform', 'translate(0 '+(-13-7*age/1100).toFixed(1)+') scale('+k.toFixed(2)+')'); b.g.setAttribute('opacity', cl((1100-age)/380).toFixed(2));
}
function loop(){
  raf=0; var now=performance.now();
  for(var i=runs.length-1;i>=0;i--){ var r=runs[i], t=(FORCE!=null)?FORCE:(now-r.t0);
    if(!r.layer.isConnected || t>=END){ r.kill(); continue; }
    r.figs.forEach(function(f){ pose(f, t, r.cx); }); r.bubs.forEach(function(b){ bubble(b, t); }); }
  if(runs.length) raf=requestAnimationFrame(loop);
}
function go(C, el_, tagEl){
  if(!el_ || !C.svg || (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches)) return;
  var X, Y, W, L=el_._lm, S=tagEl&&tagEl._nbS;
  if(L){ X=L.x+L.w/2; Y=L.y+L.h-2; W=L.w; } else if(S){ X=(S[0]+S[2])/2; Y=S[3]-3; W=S[2]-S[0]; } else return;
  runs.slice().forEach(function(r){ if(r.key===el_) r.kill(); }); if(runs.length>=3) runs[0].kill();
  var r=crowd(C, el_, X, Y, W); runs.push(r); r.figs.forEach(function(f){ pose(f, FORCE!=null?FORCE:0, X); }); if(!raf) raf=requestAnimationFrame(loop);
  try{ window._palSnd && window._palSnd.scream && window._palSnd.scream(1); }catch(e){}
}
return {go:go, stop:function(){ runs.slice().forEach(function(r){ r.kill(); }); }, freeze:function(ms){ FORCE=(ms==null)?null:+ms; if(!raf && runs.length) raf=requestAnimationFrame(loop); }, active:function(){ return runs.length; }};
})();
"""
