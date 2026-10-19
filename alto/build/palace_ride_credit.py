"""The first-person view's two honest labels over the real street data (2.0.0 review fixes 8 and 9).

CREDIT   The full-screen ride covers the map's own "(c) OpenStreetMap contributors", and the street data is OpenStreetMap's (ODbL): while the real streets
         are on screen a quiet credit stands in the corner of the view, a link to https://www.openstreetmap.org/copyright (new tab, rel noopener). Its text is
         window._palStreet.attribution() (the manifest's own line) set with textContent, never HTML.
AREA     The HUD's third line (the grey one under the street) names the palace DISTRICT ("Spring Garden"): the page's own lattice, not the city's. Where the real
         street data is on screen it is replaced by the real neighbourhood (OSM place=neighbourhood|suburb|quarter, window._palStreet.place) or, when the data
         has none there, dropped; the lattice walk keeps the district. (The HUD is inside ROAM's closure and is not edited: a MutationObserver corrects its line.)

Included by palace_ride.py after JS_STREET (the ride's closure: ROAM, REAL and UM are in reach).
"""
from __future__ import annotations

CSS_CREDIT = r"""
#pal-ride .pr-credit{position:absolute;right:12px;bottom:8px;z-index:6;padding:3px 9px;border-radius:999px;font:500 10.5px/1.25 system-ui,-apple-system,"Segoe UI",sans-serif;
  color:rgba(255,255,255,.74);background:rgba(14,16,26,.42);text-decoration:none;opacity:0;pointer-events:none;transition:opacity .4s ease;white-space:nowrap;}
#pal-ride .pr-credit.on{opacity:.85;pointer-events:auto;}
#pal-ride .pr-credit:hover,#pal-ride .pr-credit:focus-visible{opacity:1;color:#fff;text-decoration:underline;}
@media (prefers-reduced-motion: reduce){#pal-ride .pr-credit{transition:none;}}
"""

JS_CREDIT = r"""
/* ── the OpenStreetMap credit and the real neighbourhood (palace_ride_credit.py) ──
   The roam HUD lives inside ROAM's closure, so the area line is corrected from outside: a MutationObserver sees the HUD write the palace district into .rm-ar and replaces it (before the next paint) with the
   real neighbourhood, or empties and hides the line when the data has none here; leaving a real walk puts the last district the HUD wrote back. */
var CR={burst:0, warned:0, mo:null, force:null, a:null, ar:null, lv:null, orig:'', origDisp:'', mine:null, on:false, timer:0, px:1e9, py:1e9, t:0, name:''};
function crStreet(){ try{ return !!(window._palStreet && window._palStreet.ready && window._palStreet.ready() && typeof REAL!=='undefined' && REAL && REAL.on && REAL.src==='street'); }catch(e){ return false; } }
function crRoot(){ return document.getElementById('pal-ride'); }
function crEnsure(){
  var root=crRoot(); if(!root) return null;
  if(!document.getElementById('pal-credit-css')){ var st=document.createElement('style'); st.id='pal-credit-css'; st.textContent=CREDIT_CSS; (document.head||document.documentElement).appendChild(st); }
  if(!CR.a || CR.a.parentNode!==root){ var a=document.createElement('a'); a.className='pr-credit'; a.href='https://www.openstreetmap.org/copyright'; a.target='_blank'; a.rel='noopener'; root.appendChild(a); CR.a=a; }
  return CR.a; }
/* the roam state while it is a real walk on the street data, else null */
function crReal(){ try{ if(!crStreet() || typeof ROAM==='undefined' || !ROAM || !ROAM.active()) return null; var st=ROAM.state(); return st.real?st:null; }catch(e){ return null; } }
function crArea(st){
  var P=window._palStreet, x=st.x/UM, y=st.y/UM; if(!P.place) return null;
  if(Math.hypot(x-CR.px,y-CR.py)<4 && performance.now()-CR.t<2000) return CR.name;
  CR.px=x; CR.py=y; CR.t=performance.now(); try{ CR.name=P.place(x,P.toMap(0,0,1)[1]-y)||''; }catch(e){ CR.name=''; } return CR.name; }
/* the live line with the district at its end swapped for the real place: the new text, or null when nothing changes (2.0.1: writing the SAME text again is still a childList
   mutation, so when the real neighbourhood had the district's own name - Old City, Society Hill - the observer re-fired itself forever in one microtask chain and the tab froze) */
function crLiveText(t, pa, ar){ if(!t || !pa || t.slice(-(pa.length+2))!=='. '+pa) return null; var nu=t.slice(0,-(pa.length+2))+(ar?'. '+ar:''); return nu===t?null:nu; }
/* a safety net under the observer: more than CR_BURST corrections without a task in between is a feedback loop - stop observing, say so once */
var CR_BURST=40;
function crGuard(){ if(CR.burst++===0) setTimeout(function(){ CR.burst=0; },0); if(CR.burst<=CR_BURST) return true;
  if(CR.mo){ try{ CR.mo.disconnect(); }catch(e){} CR.mo=null; CR.ar=null; } if(!CR.warned){ CR.warned=1; if(window.console&&console.warn) console.warn('ride credit: the area line kept rewriting itself; corrections paused'); } return false; }
function crFix(){
  var H=CR.ar; if(!H || !crGuard()) return; var st=CR.force||crReal();
  if(H.textContent!==CR.mine){ CR.orig=H.textContent; CR.origDisp=H.style.display; }          /* the HUD wrote the district: remember it, it is what the lattice shows */
  if(!st){ if(CR.on){ CR.on=false; CR.mine=null; if(H.textContent!==CR.orig) H.textContent=CR.orig; H.style.display=CR.origDisp; } return; }
  var ar=CR.force?CR.force.ar:crArea(st); if(ar===null) return; CR.on=true; CR.mine=ar;
  if(H.textContent!==ar) H.textContent=ar; if(H.style.display!==(ar?'':'none')) H.style.display=ar?'':'none';
  var lv=CR.lv, nu=lv?crLiveText(lv.textContent, CR.orig, ar):null; if(nu!==null) lv.textContent=nu; }
function crTick(){
  var root=crRoot(), show=false;
  try{ show=!!(root && root.classList.contains('on') && crStreet() && ((typeof ROAM!=='undefined' && ROAM && ROAM.active() && ROAM.state().real) || (REAL.isOn && REAL.isOn()))); }catch(e){}
  var ar=root&&root.querySelector&&root.querySelector('.rm-ar');
  if(ar && ar!==CR.ar && typeof MutationObserver!=='undefined'){ CR.ar=ar; CR.lv=root.querySelector('.rm-live'); CR.mine=null;
    if(CR.mo){ try{ CR.mo.disconnect(); }catch(e){} } var mo=new MutationObserver(crFix); CR.mo=mo; mo.observe(ar,{childList:true,characterData:true,subtree:true,attributes:true,attributeFilter:['style']}); if(CR.lv) mo.observe(CR.lv,{childList:true,characterData:true,subtree:true}); }
  crFix();
  if(!show && !CR.a) return;
  var a=crEnsure(); if(!a) return;
  var txt=''; try{ txt=window._palStreet.attribution()||''; }catch(e){}
  if(a.textContent!==txt) a.textContent=txt;
  var on=show && !!txt; if(a.classList.contains('on')!==on) a.classList.toggle('on',on);
  a.tabIndex=on?0:-1; }
/* the poll runs only while the ride is open: it stops at the first tick that finds the overlay closed and the credit hidden, and starts again when the page marks the first-person view open (html.pal-fp) */
function crStart(){ if(!CR.timer) CR.timer=setInterval(crPoll,600); }
function crPoll(){ crTick(); var root=crRoot(), open=false; try{ open=!!(root && root.classList.contains('on')); }catch(e){} if(!open && !(CR.a && CR.a.classList.contains('on'))){ clearInterval(CR.timer); CR.timer=0; } }
try{ if(typeof MutationObserver!=='undefined' && document.documentElement && document.documentElement.classList) new MutationObserver(function(){ if(document.documentElement.classList.contains('pal-fp')) crStart(); }).observe(document.documentElement,{attributes:true,attributeFilter:['class']}); }catch(e){}
crStart();
REAL.credit={live:crLiveText, fix:crFix, cr:CR, tick:crTick};          /* tests: the pure rewrite, and CR.force = {x, y, real, ar} stands in for a real walk */
""".replace("CREDIT_CSS", "'" + CSS_CREDIT.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'")
