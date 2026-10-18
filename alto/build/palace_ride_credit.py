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
var CR={a:null, ar:null, lv:null, orig:'', origDisp:'', mine:null, on:false, timer:0, px:1e9, py:1e9, t:0, name:''};
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
function crFix(){
  var H=CR.ar; if(!H) return; var st=crReal();
  if(H.textContent!==CR.mine){ CR.orig=H.textContent; CR.origDisp=H.style.display; }          /* the HUD wrote the district: remember it, it is what the lattice shows */
  if(!st){ if(CR.on){ CR.on=false; CR.mine=null; if(H.textContent!==CR.orig) H.textContent=CR.orig; H.style.display=CR.origDisp; } return; }
  var ar=crArea(st); if(ar===null) return; CR.on=true; CR.mine=ar;
  if(H.textContent!==ar) H.textContent=ar; if(H.style.display!==(ar?'':'none')) H.style.display=ar?'':'none';
  var lv=CR.lv, pa=CR.orig, t=lv&&lv.textContent;
  if(t && pa && t.slice(-(pa.length+2))=='. '+pa) lv.textContent=t.slice(0,-(pa.length+2))+(ar?'. '+ar:''); }
function crTick(){
  var root=crRoot(), show=false;
  try{ show=!!(root && root.classList.contains('on') && crStreet() && ((typeof ROAM!=='undefined' && ROAM && ROAM.active() && ROAM.state().real) || (REAL.isOn && REAL.isOn()))); }catch(e){}
  var ar=root&&root.querySelector&&root.querySelector('.rm-ar');
  if(ar && ar!==CR.ar && typeof MutationObserver!=='undefined'){ CR.ar=ar; CR.lv=root.querySelector('.rm-live'); CR.mine=null;
    var mo=new MutationObserver(crFix); mo.observe(ar,{childList:true,characterData:true,subtree:true,attributes:true,attributeFilter:['style']}); if(CR.lv) mo.observe(CR.lv,{childList:true,characterData:true,subtree:true}); }
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
""".replace("CREDIT_CSS", "'" + CSS_CREDIT.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'")
