"""Part C of the first-person ride: the tunnel rush (original abstract art) and the vehicles' own windows and dashboards."""

JS_C = r"""
/* ── the tunnel: rings of light closing in, walls flooded with slowly sweeping colour, light bars chasing along the walls, the lamp pushing ahead.
   Smooth by design: a ring never passes faster than RING_HZ, nothing pulses faster than BAR_HZ, neighbouring bands differ in hue, not in brightness. ── */
var TN=null;
function tunnelReset(){ TN={ph:0, hue:Math.random()*360, rot:0, tau:0, parts:[], t:0};
  for(var i=0;i<70;i++) TN.parts.push({a:hash(i*13+1)*6.2832, r:hash(i*7+3), sp:.6+hash(i*5+2)*.9}); }
function lerpHue(a,b,t){ var d=((b-a+540)%360)-180; return a+d*t; }
function tunnelFrame(ctx, W, H, T){
  if(!TN) tunnelReset();
  var dt=T.dt||0, cx=W/2, cy=H*.5+(T.sway||0), N=34, Z0=7, BETA=.2, vis=T.vis, calm=T.calm, ramp=T.reduce?0:sstep(0,3,TN.tau), hz=RING_HZ*(.5+.5*ramp);
  if(!T.reduce){ TN.tau+=dt; TN.t+=dt; TN.ph+=dt*vis*hz; TN.hue+=dt*HUE_DPS*(.35+.65*ramp)*(.25+.75*vis); TN.rot+=dt*.12*(.2+.8*vis); }
  var frac=TN.ph-Math.floor(TN.ph), m0=Math.floor(TN.ph), R0=hypot2(cx,cy)*6.2, rxk=1.32, k, j, m;
  var lineH=T.lineHue||210, tt=TN.t;
  /* the rings, nearest first: each disc is the wall between its ring and the next, laid over the nearer one's */
  var ring=[], first=-1;
  for(k=0;k<=N;k++){ var z=Z0*Math.exp(BETA*(k-frac)); if(z<1.2) continue; if(first<0) first=k; ring.push({k:k, z:z, rad:R0/z}); }
  function bandCol(mm, z, a){ var hue=mm*24+TN.hue, s=.84, l=.45+((mm&1)?.07:-.05)+.05*Math.sin(mm*.9+tt*.7)+(1-clamp(z/1200,0,1))*.06;
    if(calm>0){ hue=lerpHue(hue, lineH, clamp(calm*1.3,0,1)); s=mix(s,.14,calm); l=mix(l,.76-((mm&1)*.05),calm); }
    l*=mix(1,.6,clamp(z/2000,0,1))*(T.dim==null?1:T.dim); return hsl(hue, s, l, a); }
  if(ring.length){ ctx.fillStyle=bandCol(m0+ring[0].k-1, ring[0].z, 1); ctx.fillRect(0,0,W,H); }
  for(j=0;j<ring.length;j++){ var r=ring[j]; m=m0+r.k; ctx.fillStyle=bandCol(m, r.z, 1); ctx.beginPath(); ctx.ellipse(cx,cy,r.rad*rxk,r.rad,0,0,6.2832); ctx.fill(); }
  /* the light bars along the walls: soft, chasing, never a hard on-off */
  var J=8, bars=T.reduce?0:J, nb=Math.min(ring.length-1, 18);
  for(var b=0;b<bars;b++){ var th=b*6.2832/J+TN.rot, dl=.05;
    for(j=0;j<nb;j++){ var r1=ring[j], r2=ring[j+1]; m=m0+r1.k; var al=Math.sin(6.2832*(m*.083+b*.31-tt*BAR_HZ*.5)); if(al<=0) continue; al=al*al*.55*(1-calm*.85)*ramp; if(al<.03) continue;
      var c1=Math.cos(th-dl), s1=Math.sin(th-dl), c2=Math.cos(th+dl), s2=Math.sin(th+dl);
      ctx.fillStyle=hsl(m*24+TN.hue+35, 1, .8, al); ctx.beginPath();
      ctx.moveTo(cx+c1*r1.rad*rxk, cy+s1*r1.rad); ctx.lineTo(cx+c2*r1.rad*rxk, cy+s2*r1.rad); ctx.lineTo(cx+c2*r2.rad*rxk, cy+s2*r2.rad); ctx.lineTo(cx+c1*r2.rad*rxk, cy+s1*r2.rad); ctx.closePath(); ctx.fill(); } }
  /* the rings of light */
  for(j=0;j<ring.length;j++){ var q=ring[j]; m=m0+q.k; var pulse=T.reduce?.5:(.5+.5*Math.sin(m*1.7-tt*6.2832*BAR_HZ)), a=(.55+.4*pulse)*(1-calm*.6)*clamp(1.3-q.z/1500,0,1);
    ctx.lineWidth=clamp(q.rad*.018,1,16); ctx.strokeStyle=hsl(m*24+TN.hue+40, 1, .86, a*.45); ctx.beginPath(); ctx.ellipse(cx,cy,q.rad*rxk,q.rad,0,0,6.2832); ctx.stroke();
    ctx.lineWidth=clamp(q.rad*.006,.8,5); ctx.strokeStyle=hsl(m*24+TN.hue+40, 1, .93, a); ctx.stroke(); }
  /* streaks: motes of light pouring out from the vanishing point */
  if(!T.reduce && vis>.02 && calm<.9){ ctx.lineCap='round'; var ps=TN.parts;
    for(j=0;j<ps.length;j++){ var p=ps[j], r0=p.r; p.r+=dt*(.08+p.r*1.3)*vis*p.sp*(.5+.5*ramp); if(p.r>1.1){ p.r=.02+hash(j*3+(TN.t*7|0))*.1; p.a=hash(j*5+(TN.t*3|0))*6.2832; }
      var rr1=p.r*p.r, rr0=Math.max(0,p.r-(.03+.14*vis*p.r)); rr0*=rr0;
      ctx.strokeStyle='rgba(255,255,255,'+(.10+.30*Math.min(1,p.r*2)*vis*(1-calm)).toFixed(3)+')'; ctx.lineWidth=.8+p.r*2.4;
      ctx.beginPath(); ctx.moveTo(cx+Math.cos(p.a)*rr0*W*.7, cy+Math.sin(p.a)*rr0*H*.62); ctx.lineTo(cx+Math.cos(p.a)*rr1*W*.7, cy+Math.sin(p.a)*rr1*H*.62); ctx.stroke(); } }
  /* the vehicle's lamp, and the dark closing round the edges */
  var lamp=(T.lamp==null?1:T.lamp)*(1-calm*.55), g=ctx.createRadialGradient(cx,cy,0,cx,cy,H*.55);
  g.addColorStop(0,'rgba(255,248,226,'+(.62*lamp*(.94+.06*Math.sin(tt*6.2832*1.1))).toFixed(3)+')'); g.addColorStop(.25,'rgba(255,240,205,'+(.22*lamp).toFixed(3)+')'); g.addColorStop(1,'rgba(255,240,205,0)'); ctx.fillStyle=g; ctx.fillRect(0,0,W,H);
  var vg=ctx.createRadialGradient(cx,cy,H*.28,cx,cy,hypot2(cx,cy)*1.05); vg.addColorStop(0,'rgba(0,0,0,0)'); vg.addColorStop(1,'rgba(4,2,14,'+(.55-.25*calm).toFixed(3)+')'); ctx.fillStyle=vg; ctx.fillRect(0,0,W,H);
  /* the way out: a warm mouth swelling ahead */
  if(T.mouth>0){ var mr=T.mouth*W*.62, mg=ctx.createRadialGradient(cx,cy,0,cx,cy,mr); mg.addColorStop(0,'rgba(255,253,240,'+(.96*T.mouth).toFixed(3)+')'); mg.addColorStop(.5,'rgba(255,244,214,'+(.55*T.mouth).toFixed(3)+')'); mg.addColorStop(1,'rgba(255,240,205,0)'); ctx.fillStyle=mg; ctx.fillRect(0,0,W,H); }
}
function hypot2(a,b){ return Math.sqrt(a*a+b*b); }
/* the platform name board, drawn into the tunnel (and over the 3D scene at an open station) */
function drawBoard(ctx, W, H, name, color, a, kind, sub){
  if(a<=0.01) return; var k=H/900, bw=Math.min(W*.5, 560*k+name.length*14*k), bh=96*k, x=W*.5-bw/2, y=H*.64; ctx.save(); ctx.globalAlpha=clamp(a,0,1);
  ctx.fillStyle='rgba(18,22,36,.88)'; rr(ctx,x,y,bw,bh,16*k); ctx.fill(); ctx.fillStyle=color||'#888'; rr(ctx,x,y+bh-9*k,bw,9*k,4*k); ctx.fill();
  ctx.fillStyle=color||'#888'; ctx.beginPath(); ctx.arc(x+38*k,y+bh*.48,17*k,0,6.2832); ctx.fill(); ctx.fillStyle='rgba(255,255,255,.95)'; ctx.beginPath(); ctx.arc(x+38*k,y+bh*.48,7*k,0,6.2832); ctx.fill();
  ctx.fillStyle='#fff'; ctx.textBaseline='middle'; ctx.textAlign='left'; ctx.font='800 '+(34*k).toFixed(1)+'px system-ui,-apple-system,Segoe UI,sans-serif'; ctx.fillText(name, x+70*k, y+bh*.40, bw-90*k);
  ctx.fillStyle='rgba(255,255,255,.72)'; ctx.font='600 '+(15*k).toFixed(1)+'px system-ui,-apple-system,Segoe UI,sans-serif'; ctx.fillText(sub||kind||'', x+70*k, y+bh*.76, bw-90*k); ctx.restore(); }

/* ── the vehicles' own frames: what you see of the car you are in ── */
function shadeHex(c, f){ var r=rgbOf(c); return css([r[0]*f, r[1]*f, r[2]*f]); }
function windowFrame(ctx, W, H, x0,y0,x1,y1,rad, fill){ ctx.save(); ctx.beginPath(); ctx.rect(0,0,W,H); rr2(ctx,x0,y0,x1-x0,y1-y0,rad); ctx.fillStyle=fill; ctx.fill('evenodd'); ctx.restore(); }
function rr2(ctx,x,y,w,h,r){ r=Math.min(r,w/2,h/2); ctx.moveTo(x+r,y); ctx.lineTo(x+w-r,y); ctx.arcTo(x+w,y,x+w,y+r,r); ctx.lineTo(x+w,y+h-r); ctx.arcTo(x+w,y+h,x+w-r,y+h,r); ctx.lineTo(x+r,y+h); ctx.arcTo(x,y+h,x,y+h-r,r); ctx.lineTo(x,y+r); ctx.arcTo(x,y,x+r,y,r); ctx.closePath(); }
function sign(ctx, x, y, w, h, text, color, k){ ctx.save(); ctx.fillStyle='#0b0c10'; rr(ctx,x,y,w,h,5*k); ctx.fill(); ctx.strokeStyle='rgba(255,255,255,.18)'; ctx.lineWidth=1.2; ctx.stroke();
  ctx.fillStyle='#ffb62e'; ctx.textBaseline='middle'; ctx.textAlign='center'; ctx.font='700 '+(h*.52).toFixed(1)+'px "Courier New",ui-monospace,monospace'; ctx.shadowColor='rgba(255,170,30,.6)'; ctx.shadowBlur=0; ctx.fillText(text, x+w/2, y+h/2+1, w-14*k);
  if(color){ ctx.fillStyle=color; ctx.fillRect(x+6*k,y+h-5*k,w-12*k,3*k); } ctx.restore(); }
function pole(ctx, x, y0, y1, k, lit){ var g=ctx.createLinearGradient(x-5*k,0,x+5*k,0); g.addColorStop(0,'#7e8594'); g.addColorStop(.45,'#f3f5fa'); g.addColorStop(1,'#6b7280'); ctx.fillStyle=g; ctx.fillRect(x-4*k,y0,8*k,y1-y0); }
function frameMetro(ctx, W, H, F){ var k=H/900, dk=F.dk, wall=dk?'#2c303b':'#c9cdd6', ceil=dk?'#383d4a':'#e2e5eb', floor=dk?'#1c1e26':'#484c58', x0=W*.17, x1=W*.83, y0=H*.13, y1=H*.71;
  windowFrame(ctx,W,H,x0,y0,x1,y1,26*k,wall);
  ctx.save(); ctx.beginPath(); ctx.rect(0,0,W,y0); ctx.clip(); var g=ctx.createLinearGradient(0,0,0,y0); g.addColorStop(0,ceil); g.addColorStop(1,shadeHex(ceil,.82)); ctx.fillStyle=g; ctx.fillRect(0,0,W,y0); ctx.restore();
  ctx.fillStyle=dk?'#a9b0c4':'#fff'; rr(ctx,W*.3,y0*.16,W*.4,y0*.1,4*k); ctx.fill();
  sign(ctx, W*.5-W*.17, y0*.40, W*.34, y0*.42, F.sign, F.color, k);
  ctx.fillStyle=floor; ctx.beginPath(); ctx.moveTo(x0,y1); ctx.lineTo(x1,y1); ctx.lineTo(W,H); ctx.lineTo(0,H); ctx.closePath(); ctx.fill();
  ctx.fillStyle='#e3b82b'; ctx.beginPath(); ctx.moveTo(x0+W*.02,y1+H*.012); ctx.lineTo(x1-W*.02,y1+H*.012); ctx.lineTo(x1-W*.02+W*.012,y1+H*.02); ctx.lineTo(x0+W*.02-W*.012,y1+H*.02); ctx.closePath(); ctx.fill();
  [[0,x0],[x1,W]].forEach(function(r,i){ var sx=i?r[0]:r[0], w=r[1]-r[0]; ctx.fillStyle=F.color; ctx.globalAlpha=.85; rr(ctx, i?x1+w*.14:w*.12, y1-H*.07, w*.74, H*.2, 14*k); ctx.fill(); ctx.globalAlpha=1;
    ctx.fillStyle='rgba(0,0,0,.18)'; rr(ctx, i?x1+w*.14:w*.12, y1+H*.07, w*.74, H*.07, 10*k); ctx.fill(); });
  pole(ctx, x0+W*.028, y0, H*.88, k); pole(ctx, x1-W*.028, y0, H*.88, k);
  ctx.fillStyle='#d9dde8'; ctx.fillRect(x0, y1-H*.07, x1-x0, 7*k); ctx.fillStyle='rgba(0,0,0,.25)'; ctx.fillRect(x0, y1-H*.07+7*k, x1-x0, 3*k);
  ctx.strokeStyle='rgba(0,0,0,.5)'; ctx.lineWidth=3*k; ctx.beginPath(); rr2(ctx,x0,y0,x1-x0,y1-y0,26*k); ctx.stroke(); }
function frameTram(ctx, W, H, F){ var k=H/900, dk=F.dk, x0=W*.055, x1=W*.945, y0=H*.12, y1=H*.70, body=dk?'#1c1f27':'#3a3f4c';
  windowFrame(ctx,W,H,x0,y0,x1,y1,18*k,body);
  ctx.fillStyle=F.color; ctx.globalAlpha=.9; ctx.fillRect(0,y0-9*k,W,6*k); ctx.globalAlpha=1;
  sign(ctx, W*.5-W*.16, H*.025, W*.32, H*.065, F.sign, F.color, k);
  [[x0+W*.012,0],[x1-W*.012,1],[W*.5,2]].forEach(function(p){ if(p[1]===2) return; ctx.fillStyle=body; ctx.fillRect(p[0]-W*.006,y0,W*.012,y1-y0); });
  var g=ctx.createLinearGradient(0,y1,0,H); g.addColorStop(0,dk?'#242834':'#4a5060'); g.addColorStop(1,dk?'#12141a':'#2a2e38'); ctx.fillStyle=g; ctx.fillRect(0,y1,W,H-y1);
  ctx.fillStyle='rgba(255,255,255,.12)'; ctx.fillRect(0,y1,W,3*k);
  ctx.fillStyle='#10121a'; ctx.beginPath(); ctx.arc(W*.26,y1+H*.12,H*.075,0,6.2832); ctx.fill(); ctx.strokeStyle='#8e96aa'; ctx.lineWidth=3*k; ctx.stroke();
  var sp=clamp(F.speed,0,1), a=Math.PI*.8+Math.PI*1.4*sp; ctx.strokeStyle='#ffb62e'; ctx.lineWidth=3*k; ctx.beginPath(); ctx.moveTo(W*.26,y1+H*.12); ctx.lineTo(W*.26+Math.cos(a)*H*.06,y1+H*.12+Math.sin(a)*H*.06); ctx.stroke();
  ctx.strokeStyle='#c7ccda'; ctx.lineWidth=7*k; ctx.lineCap='round'; ctx.beginPath(); ctx.moveTo(W*.7,y1+H*.2); ctx.lineTo(W*.7+W*.025,y1+H*.07); ctx.stroke(); ctx.fillStyle='#d4372c'; ctx.beginPath(); ctx.arc(W*.7+W*.027,y1+H*.065,10*k,0,6.2832); ctx.fill();
  ctx.strokeStyle='rgba(20,22,30,.85)'; ctx.lineWidth=4*k; [[.35,.72],[.62,.72]].forEach(function(p){ ctx.beginPath(); ctx.moveTo(W*p[0],y1); ctx.lineTo(W*(p[0]+.12),y1-H*.26); ctx.stroke(); }); }
function frameRail(ctx, W, H, F){ var k=H/900, dk=F.dk, x0=W*.14, x1=W*.86, y0=H*.15, y1=H*.66, wall=dk?'#262a35':'#d0d3dc';
  windowFrame(ctx,W,H,x0,y0,x1,y1,44*k,wall);
  ctx.fillStyle=dk?'#1b1e27':'#b6bac6'; ctx.fillRect(0,0,W,H*.075); ctx.strokeStyle='rgba(0,0,0,.25)'; ctx.lineWidth=2*k; for(var i=0;i<16;i++){ ctx.beginPath(); ctx.moveTo(W*i/16,0); ctx.lineTo(W*i/16,H*.075); ctx.stroke(); }
  sign(ctx, W*.5-W*.15, H*.092, W*.30, H*.04, F.sign, F.color, k);
  [[x0,x0+W*.045],[x1-W*.045,x1]].forEach(function(r){ var g=ctx.createLinearGradient(r[0],0,r[1],0); g.addColorStop(0,shadeHex(F.color,.5)); g.addColorStop(.5,shadeHex(F.color,.85)); g.addColorStop(1,shadeHex(F.color,.55)); ctx.fillStyle=g; ctx.fillRect(r[0],y0+10*k,r[1]-r[0],(y1-y0)*.8); });
  ctx.fillStyle=dk?'#2d3240':'#e7e8ee'; ctx.fillRect(x0-W*.01,y1,x1-x0+W*.02,H*.045); ctx.fillStyle='rgba(0,0,0,.2)'; ctx.fillRect(x0-W*.01,y1+H*.045,x1-x0+W*.02,3*k);
  var f=ctx.createLinearGradient(0,y1+H*.05,0,H); f.addColorStop(0,dk?'#171a22':'#3b3f4c'); f.addColorStop(1,dk?'#0e1015':'#23262f'); ctx.fillStyle=f; ctx.fillRect(0,y1+H*.045,W,H);
  [[W*.08,0],[W*.74,1]].forEach(function(p){ ctx.fillStyle=shadeHex(F.color,dk?.55:.8); rr(ctx,p[0],H*.76,W*.18,H*.3,40*k); ctx.fill(); ctx.fillStyle='rgba(255,255,255,.08)'; rr(ctx,p[0]+W*.012,H*.77,W*.156,H*.05,20*k); ctx.fill(); });
  ctx.strokeStyle='rgba(0,0,0,.5)'; ctx.lineWidth=3*k; ctx.beginPath(); rr2(ctx,x0,y0,x1-x0,y1-y0,44*k); ctx.stroke(); }
function frameBus(ctx, W, H, F){ var k=H/900, dk=F.dk, body=dk?'#171a21':'#2c303a';
  ctx.save(); ctx.fillStyle=body; ctx.beginPath(); ctx.rect(0,0,W,H); ctx.moveTo(W*.07,H*.17); ctx.lineTo(W*.93,H*.17); ctx.lineTo(W*.985,H*.64); ctx.lineTo(W*.015,H*.64); ctx.closePath(); ctx.fill('evenodd'); ctx.restore();
  sign(ctx, W*.5-W*.17, H*.03, W*.34, H*.07, F.sign, F.color, k);
  ctx.fillStyle=dk?'#22262f':'#454a58'; rr(ctx,W*.46,H*.115,W*.08,H*.045,8*k); ctx.fill();
  ctx.fillStyle=F.stopReq?'#ff3b2f':'#3b2220'; rr(ctx,W*.78,H*.04,W*.12,H*.05,8*k); ctx.fill(); ctx.fillStyle=F.stopReq?'#fff':'#6b4a46'; ctx.font='800 '+(15*k).toFixed(1)+'px system-ui,sans-serif'; ctx.textAlign='center'; ctx.textBaseline='middle'; ctx.fillText('STOP REQUESTED', W*.84, H*.066);
  var g=ctx.createLinearGradient(0,H*.62,0,H); g.addColorStop(0,dk?'#2a2e39':'#4d5362'); g.addColorStop(.18,dk?'#161920':'#2d313c'); g.addColorStop(1,dk?'#0d0f13':'#1c1f27'); ctx.fillStyle=g; ctx.beginPath(); ctx.moveTo(0,H*.64); ctx.quadraticCurveTo(W*.5,H*.60,W,H*.64); ctx.lineTo(W,H); ctx.lineTo(0,H); ctx.closePath(); ctx.fill();
  ctx.fillStyle='rgba(255,255,255,.1)'; ctx.fillRect(W*.02,H*.645,W*.96,2*k);
  var wx=W*.42, wy=H*.93, wr=H*.2; ctx.strokeStyle='#0c0d11'; ctx.lineWidth=H*.034; ctx.beginPath(); ctx.ellipse(wx,wy,wr*1.35,wr*.62,0,Math.PI*1.05,Math.PI*1.95); ctx.stroke(); ctx.strokeStyle='rgba(255,255,255,.1)'; ctx.lineWidth=2*k; ctx.stroke();
  ctx.fillStyle=F.color; ctx.globalAlpha=.8; ctx.fillRect(W*.66,H*.72,W*.18,6*k); ctx.globalAlpha=1;
  ctx.fillStyle='#10121a'; ctx.beginPath(); ctx.arc(W*.76,H*.80,H*.055,0,6.2832); ctx.fill(); var sp=clamp(F.speed,0,1), a=Math.PI*.8+Math.PI*1.4*sp; ctx.strokeStyle='#ffb62e'; ctx.lineWidth=3*k; ctx.beginPath(); ctx.moveTo(W*.76,H*.80); ctx.lineTo(W*.76+Math.cos(a)*H*.045,H*.80+Math.sin(a)*H*.045); ctx.stroke();
  ctx.strokeStyle='rgba(15,17,24,.9)'; ctx.lineWidth=3*k; [[.30,.62],[.58,.62]].forEach(function(p){ ctx.beginPath(); ctx.moveTo(W*p[0],H*.64); ctx.lineTo(W*(p[0]+.10),H*.64-H*.20); ctx.stroke(); });
  ctx.fillStyle=body; ctx.fillRect(0,0,W*.03,H); ctx.fillRect(W*.97,0,W*.03,H); }
function frameCar(ctx, W, H, F){ var k=H/900, dk=F.dk, body=dk?'#12141a':'#262a33';
  ctx.save(); ctx.fillStyle=body; ctx.beginPath(); ctx.rect(0,0,W,H); ctx.moveTo(W*.1,H*.08); ctx.lineTo(W*.9,H*.08); ctx.lineTo(W*.975,H*.72); ctx.lineTo(W*.025,H*.72); ctx.closePath(); ctx.fill('evenodd'); ctx.restore();
  ctx.fillStyle=dk?'#1e222b':'#3a3f4b'; rr(ctx,W*.43,H*.095,W*.14,H*.055,10*k); ctx.fill(); ctx.fillStyle='rgba(120,160,200,.25)'; rr(ctx,W*.435,H*.1,W*.13,H*.045,8*k); ctx.fill();
  var g=ctx.createLinearGradient(0,H*.7,0,H); g.addColorStop(0,dk?'#252934':'#444a57'); g.addColorStop(.1,dk?'#14161c':'#2a2e38'); g.addColorStop(1,dk?'#0a0b0e':'#171a20'); ctx.fillStyle=g; ctx.beginPath(); ctx.moveTo(0,H*.74); ctx.quadraticCurveTo(W*.5,H*.69,W,H*.74); ctx.lineTo(W,H); ctx.lineTo(0,H); ctx.closePath(); ctx.fill();
  ctx.fillStyle=dk?'#1a1d25':'#30343f'; ctx.beginPath(); ctx.moveTo(W*.18,H*.74); ctx.lineTo(W*.82,H*.74); ctx.lineTo(W*.92,H*.80); ctx.lineTo(W*.08,H*.80); ctx.closePath(); ctx.fill();
  var wx=W*.27, wy=H*.92; ctx.fillStyle='#0b0c10'; ctx.beginPath(); ctx.ellipse(wx,wy+H*.04,H*.2,H*.12,0,0,6.2832); ctx.fill();
  ctx.save(); ctx.beginPath(); ctx.rect(0,H*.78,W,H*.22); ctx.clip(); ctx.strokeStyle='#14161d'; ctx.lineWidth=H*.03; ctx.beginPath(); ctx.ellipse(wx,wy+H*.06,H*.24,H*.2,0,0,6.2832); ctx.stroke(); ctx.strokeStyle='rgba(255,255,255,.12)'; ctx.lineWidth=2*k; ctx.stroke(); ctx.restore();
  ctx.fillStyle='#0d1015'; ctx.beginPath(); ctx.arc(wx,H*.835,H*.056,0,6.2832); ctx.fill(); ctx.strokeStyle='#3a4150'; ctx.lineWidth=2*k; ctx.stroke(); var sp=clamp(F.speed,0,1), a=Math.PI*.8+Math.PI*1.4*sp; ctx.strokeStyle='#ff6a3a'; ctx.lineWidth=3*k; ctx.beginPath(); ctx.moveTo(wx,H*.835); ctx.lineTo(wx+Math.cos(a)*H*.046,H*.835+Math.sin(a)*H*.046); ctx.stroke();
  ctx.fillStyle=body; ctx.beginPath(); ctx.moveTo(0,H*.4); ctx.lineTo(W*.032,H*.4); ctx.lineTo(W*.05,H*.5); ctx.lineTo(0,H*.54); ctx.closePath(); ctx.fill(); ctx.beginPath(); ctx.moveTo(W,H*.4); ctx.lineTo(W*.968,H*.4); ctx.lineTo(W*.95,H*.5); ctx.lineTo(W,H*.54); ctx.closePath(); ctx.fill();
  ctx.fillStyle=F.color; ctx.globalAlpha=.8; ctx.fillRect(W*.62,H*.76,W*.2,5*k); ctx.globalAlpha=1; }
function frameWalk(ctx, W, H, F){ var g=ctx.createRadialGradient(W/2,H*.5,H*.5,W/2,H*.5,hypot2(W/2,H/2)); g.addColorStop(0,'rgba(0,0,0,0)'); g.addColorStop(1,'rgba(0,0,0,'+(F.dk?.34:.16)+')'); ctx.fillStyle=g; ctx.fillRect(0,0,W,H); }
var FRAMES={metro:frameMetro, tram:frameTram, rail:frameRail, bus:frameBus, car:frameCar, walk:frameWalk};
"""
