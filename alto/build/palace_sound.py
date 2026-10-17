"""1.9.97: the battleship's guns are heard (the palace page carries no audio files: everything is synthesised with the Web Audio API).

  report   a very short noise burst through a lowpass that sweeps high to low + a sine thump falling 90 -> 30 Hz, each twin mount
           firing two barrels a few ms apart, part of it sent to a small feedback-delay "distance" tail
  whistle  bandpass noise whose centre falls 2.8 kHz -> 0.9 kHz over the shell's flight time
  scream   a crowd of 4-7 distant sawtooth voices (two bandpass vowel formants, pitch glide up then down, vibrato), once per strike
  impact   a crack + four overlapping lowpass rumbles that close slowly (rolling) + a sub thump; quieter, darker and a little later the
           farther the strike is from the ship
Everything goes through a compressor (a volley never clips). The AudioContext is made and resumed inside the click that arms or fires the
guns (Safari), nothing plays while the page is hidden, standing down closes the context (pending sounds stop), and a speaker button in the
guns bar (remembered in localStorage 'alto-palace-sound', default on) mutes. Without Web Audio every call is a no-op.
`_palSnd.t(ctx)` builds the graph on any context (the tests render an OfflineAudioContext)."""
from __future__ import annotations

SOUND_JS = r"""
window._palSnd=(function(){
var C=null,M,R,N,O=[0,0],U=0,Z=-9,on=1,W='battleship',L='alto-palace-sound',P=Math.random;
try{ on=localStorage.getItem(L)!=='0'; }catch(e){}
function init(c){ C=c; Z=-9; var K=c.createDynamicsCompressor(), d, i;
  K.threshold.value=-9; K.knee.value=6; K.ratio.value=20; K.attack.value=.002; K.release.value=.3;
  M=c.createGain(); M.gain.value=.22; M.connect(K); K.connect(c.destination); R=c.createGain();
  [.19,.31,.47].forEach(function(t){ var y=c.createDelay(1), l=c.createBiquadFilter(), f=c.createGain(); y.delayTime.value=t; l.frequency.value=1300; f.gain.value=.42; R.connect(y); y.connect(l); l.connect(f); f.connect(y); l.connect(M); });
  N=c.createBuffer(1,c.sampleRate*2,c.sampleRate); d=N.getChannelData(0); for(i=0;i<d.length;i++) d[i]=P()*2-1; }
function ok(){ return C&&on&&!document.hidden&&(C.state!=='suspended'||C.startRendering||performance.now()-U<500); }
function amp(p,t,v,a,d){ p.setValueAtTime(0,t); p.linearRampToValueAtTime(v,t+a); p.exponentialRampToValueAtTime(.0005,t+a+d); }
function sw(p,t,a,b,d){ p.setValueAtTime(a,t); p.exponentialRampToValueAtTime(b,t+d); }
function out(g,s){ g.connect(M); if(s){ var x=C.createGain(); x.gain.value=s; g.connect(x); x.connect(R); } }
function nz(t,ty,fa,fb,fd,q,v,a,d,s){ var n=C.createBufferSource(), f=C.createBiquadFilter(), g=C.createGain(); n.buffer=N; n.loop=true; f.type=ty; f.Q.value=q;
  sw(f.frequency,t,fa,fb,fd); amp(g.gain,t,v,a,d); n.connect(f); f.connect(g); out(g,s); n.start(t,P()); n.stop(t+a+d+.1); }
function sn(t,fa,fb,fd,v,d,s){ var o=C.createOscillator(), g=C.createGain(); sw(o.frequency,t,fa,fb,fd); amp(g.gain,t,v,.006,d); o.connect(g); out(g,s); o.start(t); o.stop(t+d+.11); }
function rep(t,v){ nz(t,'lowpass',6000,150,.3,.7,v,.003,.28,.35); sn(t,90,30,.25,1.1*v,.55,.2); }
function vo(t,f,v){ var o=C.createOscillator(), l=C.createOscillator(), k=C.createGain(), g=C.createGain(), d=.6+P()*.6, p=o.frequency;
  o.type='sawtooth'; p.setValueAtTime(f,t); p.linearRampToValueAtTime(f*1.5,t+d*.4); p.linearRampToValueAtTime(f*1.1,t+d);
  l.frequency.value=5+P()*3; k.gain.value=f*.03; l.connect(k); k.connect(p);
  (P()<.5?[800,1200]:[600,2300]).forEach(function(q){ var b=C.createBiquadFilter(); b.type='bandpass'; b.frequency.value=q; b.Q.value=6; o.connect(b); b.connect(g); });
  amp(g.gain,t,v*(.12+P()*.12),.07,d); out(g,.5); o.start(t); l.start(t); o.stop(t+d+.2); l.stop(t+d+.2); }
function sc(v,w){ if(!ok()) return; var t=C.currentTime+(w||0), n=4+(P()*4|0); for(;n--;) vo(t+P()*.5,300+P()*600,v==null?1:v); }
function ic(s){ var a=(on?'Mute ':'Unmute ')+W+' sound'; s.setAttribute('aria-label',a); s.title=a;
  s.innerHTML='<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 6h3l4-3v10L5 10H2z"/><path d="'+(on?'M11.5 5.5a3.5 3.5 0 010 5M13 3.5a6 6 0 010 9':'M11.5 6l3.5 4M15 6l-3.5 4')+'"/></svg>'; }
function u(x,y){ if(x!=null) O=[x,y];
  if(!C&&on){ try{ var A=window.AudioContext||window.webkitAudioContext; if(A){ init(new A()); var b=C.createBufferSource(); b.buffer=C.createBuffer(1,1,22050); b.connect(C.destination); b.start(0); } }catch(e){ C=null; } }
  U=performance.now(); if(C&&C.state==='suspended'&&C.resume) try{ var p=C.resume(); if(p&&p.catch) p.catch(function(){}); }catch(e){} }
function x(){ if(!C) return; var c=C; C=null; try{ M.gain.setTargetAtTime(0,c.currentTime,.02); setTimeout(function(){ try{ c.close(); }catch(e){} },150); }catch(e){} }
document.addEventListener('visibilitychange',function(){ if(document.hidden) x(); });
return {
  u:u, x:x, sc:sc, t:function(c){ init(c); },
  f:function(ms){ if(!ok()) return; var t=C.currentTime; rep(t,1); rep(t+.035+P()*.02,.8); nz(t+.06,'bandpass',2800,900,ms/1000,14,1.5,ms*.0007,ms*.0003,.3); },
  b:function(px,py){ if(!ok()) return; var d=Math.hypot(px-O[0],py-O[1]), a=1/(1+d/2500), k=1/(1+d/4000), t=C.currentTime+Math.min(.6,d/9000);
    nz(t,'lowpass',3500*k,200,.35,.7,a,.004,.4,.3); sn(t,60,24,.8,1.2*a,1.2,.2);
    [0,.18,.5,.95].forEach(function(o,i){ nz(t+o,'lowpass',(900-i*150)*k,60,1.8,.8,a*(1-i*.22),.08,1.6,.5); });
    if(t-Z>.9){ Z=t; sc(a,t-C.currentTime+.12); } },
  bar:function(b,a,w){ if(w) W=w; var s=b.querySelector('.fx-s');
    if(!s){ s=document.createElement('button'); s.type='button'; s.className='fx-x fx-s'; s.style.margin='-3px 0 -3px 10px'; b.insertBefore(s,b.querySelector('.fx-x'));
      s.addEventListener('click',function(e){ e.stopPropagation(); e.preventDefault(); on=on?0:1; try{ localStorage.setItem(L,on); }catch(_){} if(on) u(); else x(); ic(s); }); } ic(s);
    if(a) u(); else x(); },
  /* 1.9.99: the other toys. A jet: a spool-up roar that climbs, then the flyby at the target (the noise's band falls 2.2 kHz -> 380 Hz, the Doppler pass). A bomb: a thin
     whistle falling 3.6 -> 1.0 kHz with a sine under it. Missiles: four hissing whooshes a launch apart. Sonar: a 1.48 kHz ping with its echo. A torpedo: a low motor rising in pitch. */
  jet:function(w,d){ if(!ok()) return; var t=C.currentTime+w, pt=t+Math.max(.5,d-1);
    nz(t,'bandpass',420,1400,d*.6,1.1,.5,.7,d*.7,.3); nz(pt,'bandpass',2200,380,1.7,1.6,.9,.45,1.5,.35); sn(pt-.1,520,240,1.6,.1,1.7,.2); },
  whistle:function(ms){ if(!ok()) return; var t=C.currentTime, d=ms/1000; nz(t,'bandpass',3600,1000,d,14,3.4,d*.9,d*.35,.2); sn(t,2900,1100,d,.34,d,.1); },
  rocket:function(ms){ if(!ok()) return; var t=C.currentTime; for(var i=0;i<4;i++){ nz(t+i*.19,'lowpass',700,3300,.5,.6,.9,.05,.8,.25); nz(t+i*.19,'highpass',1800,4200,.7,.4,.18,.1,.8,.2); } },
  ping:function(){ if(!ok()) return; var t=C.currentTime; [0,.4].forEach(function(o,i){ var s=C.createOscillator(), g=C.createGain(); s.frequency.value=1480-i*12; amp(g.gain,t+o,.5/(1+i),.004,1.3); s.connect(g); out(g,.8); s.start(t+o); s.stop(t+o+1.5); }); },
  torpedo:function(d){ if(!ok()) return; var t=C.currentTime, s=C.createOscillator(), f=C.createBiquadFilter(), g=C.createGain(); s.type='sawtooth'; sw(s.frequency,t,70,150,d); f.type='lowpass'; f.frequency.value=320;
    g.gain.setValueAtTime(0,t); g.gain.linearRampToValueAtTime(.34,t+d*.5); g.gain.exponentialRampToValueAtTime(.0005,t+d); s.connect(f); f.connect(g); out(g,.2); s.start(t); s.stop(t+d+.1); nz(t,'lowpass',500,260,d,.7,.18,d*.4,d*.6,.1); },
  on:function(){ return !!on; }
};
})();
"""
