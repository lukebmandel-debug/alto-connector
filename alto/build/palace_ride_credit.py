"""The first-person view's two honest labels over the real street data (2.0.0 review fixes 8 and 9).

CREDIT   The full-screen ride covers the map's own "(c) OpenStreetMap contributors", and the street data is OpenStreetMap's (ODbL): while the real streets
         are on screen a quiet credit stands in the corner of the view, a link to https://www.openstreetmap.org/copyright (new tab, rel noopener). Its text is
         window._palStreet.attribution() (the manifest's own line) set with textContent, never HTML.
AREA     The HUD's third line (the grey one under the street) names the palace DISTRICT ("Spring Garden"): the page's own lattice, not the city's. Where the real
         street data is on screen it is replaced by the real neighbourhood (OSM place=neighbourhood|suburb|quarter, window._palStreet.place) or, when the data
         has none there, dropped; the lattice walk keeps the district.

Included by palace_ride.py after JS_STREET (the same closure: S, IN, UM, REAL and hudFrame are the ride's own).
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
/* ── the OpenStreetMap credit and the real neighbourhood (palace_ride_credit.py) ── */
var CR={a:null, was:false, t:0, px:1e9, py:1e9, name:'', timer:0};
function crStreet(){ try{ return !!(window._palStreet && window._palStreet.ready && window._palStreet.ready() && typeof REAL!=='undefined' && REAL && REAL.on && REAL.src==='street'); }catch(e){ return false; } }
function crRoot(){ return document.getElementById('pal-ride'); }
function crEnsure(){
  var root=crRoot(); if(!root) return null;
  if(!document.getElementById('pal-credit-css')){ var st=document.createElement('style'); st.id='pal-credit-css'; st.textContent=CREDIT_CSS; (document.head||document.documentElement).appendChild(st); }
  if(!CR.a || CR.a.parentNode!==root){ var a=document.createElement('a'); a.className='pr-credit'; a.href='https://www.openstreetmap.org/copyright'; a.target='_blank'; a.rel='noopener'; root.appendChild(a); CR.a=a; }
  return CR.a; }
function crTick(){
  var root=crRoot(), show=false;
  try{ show=!!(root && root.classList.contains('on') && crStreet() && (S.real || (REAL.isOn && REAL.isOn()))); }catch(e){}
  if(!show && !CR.a) return;
  var a=crEnsure(); if(!a) return;
  var txt=''; try{ txt=window._palStreet.attribution()||''; }catch(e){}
  if(a.textContent!==txt) a.textContent=txt;
  var on=show && !!txt; if(a.classList.contains('on')!==on) a.classList.toggle('on',on);
  a.tabIndex=on?0:-1; }
function crStart(){ if(CR.timer) return; CR.timer=setInterval(crTick,600); }
/* the real neighbourhood under the walker (null: not a real walk, so the district stays) */
function crArea(){
  if(!(S.real && !IN.on && crStreet())) return null;
  var P=window._palStreet; if(!P.place) return null;
  var x=S.x/UM, y=S.y/UM; if(Math.hypot(x-CR.px,y-CR.py)<4 && performance.now()-CR.t<2000) return CR.name;
  var H=P.toMap(0,0,1)[1]; CR.px=x; CR.py=y; CR.t=performance.now(); try{ CR.name=P.place(x,H-y)||''; }catch(e){ CR.name=''; } return CR.name; }
var CR_hud=hudFrame;
hudFrame=function(force){
  var ar=null; try{ ar=crArea(); }catch(e){}
  if(CR.was && ar===null && S.hud) S.hud._sig=null;                  /* back to the lattice walk: let the HUD write the district again */
  CR.was=(ar!==null); CR_hud(force);
  if(ar===null) return;
  var H=S.hud; if(!H||!H.ar) return;
  if(H.ar.textContent!==ar) H.ar.textContent=ar; H.ar.style.display=ar?'':'none';
  try{ var pa=S.loc&&S.loc.area, lv=H.live&&H.live.textContent; if(pa && lv && lv.slice(-(pa.length+2))=='. '+pa) H.live.textContent=lv.slice(0,-(pa.length+2))+(ar?'. '+ar:''); }catch(e){}
};
crStart();
""".replace("CREDIT_CSS", "'" + CSS_CREDIT.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'")
