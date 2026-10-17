"""First-person rides on the Mind Palace: when you ride a line or a filter's route you are INSIDE the vehicle.

A full-screen layer (one canvas, a small software 3D projection, no filters) renders the city as you move along the leg's real path
(the plan's own legs: palace_directions.py legPlan / the tour's S.tourLegs): the track, road or footpath ahead, the buildings you pass
as extruded boxes on their real footprints (your node buildings in their district's glass, the landmarks and towers, the fill-in
buildings), parks, water and bridges, the sky in the page's own light or dark theme. The vehicle's own window frames what you see:
a subway car, a trolley, a Regional Rail carriage, a bus, a car, or eye-level walking with footstep bob. Underground stretches
(the trolley tunnel, the Market-Frankford and Broad Street subways, the Center City commuter tunnel, PATCO) cut into the tunnel rush:
original abstract art - rings of light closing in, walls flooded with slowly sweeping colour, light bars chasing along them, the
vehicle's lamp pushing ahead, a warm mouth swelling at the end. It is smooth by design (see RING_HZ / BAR_HZ: nothing flashes
faster than three times a second, nothing hard-edged strobes) and with prefers-reduced-motion it is a calm still frame.

The transit panel keeps working (Next / back / Ride it all / Esc). 'V' (and a small button) switches between this view and the
old top-down map ride; the choice is remembered in localStorage (alto-palace-ride-view, default first-person). Esc / Exit ride
puts the map back exactly where it was (palace.py restoreView).

FPV phase 1 (1.9.100, palace_ride_door.py): the node buildings have a street-facing door (steps, recessed glass doors with warm light, a canopy); in roam, facing one within ~12 units
shows its real name under the street card (a small pin, a very small E) and E / a click on it goes in: roam is left, a dark veil and a dolly toward the door lead to the building's detail page, and
closing the page puts you back at the same spot, yaw and pitch. Human scale: eye 1.65 m, a 1.5 m/s walk (Shift 4 m/s, held longer 7 m/s), Street View's 90-degree view, a bob per footfall only while walking;
a walking ride leg plays at a walking pace where the 30 s allow (palace_ride_a.py timeline).

Hooks (palace_transit_js.py): animLeg -> _palRide.leg(), ride()/step() -> lineEnter()/lineStep(), startTrip/ride -> mark(), endTrip -> exit().
palace.py gives it the page's own parts through _palRide.init().
"""
from __future__ import annotations

from .palace_ride_a import JS_A
from .palace_ride_b import JS_B
from .palace_ride_c import JS_C
from .palace_ride_d import JS_D
from .palace_ride_door import JS_DOOR_GEO
from .palace_ride_e import JS_E, CSS_E
from .palace_ride_f import JS_F, CSS_F
from .palace_ride_g import JS_G, CSS_G
from .palace_ride_gl import CSS_GL, JS_GL
from .palace_ride_h import JS_H
from .palace_ride_mesh import JS_MB
from .palace_ride_real import JS_REAL
from .palace_street_js import STREET_JS
from .palace_ride_street import JS_STREET

RIDE_CSS_MAIN = r"""
  #pal-ride{position:fixed;left:0;top:0;right:0;bottom:0;z-index:399;background:#05060a;opacity:0;pointer-events:none;transition:opacity .28s ease;}
  #pal-ride.on{opacity:1;pointer-events:auto;}
  #pal-ride .pr-cv{position:absolute;left:0;top:0;width:100%;height:100%;display:block;}
  #pal-ride .pr-chip{position:absolute;left:24px;top:20px;max-width:min(560px,calc(100vw - 420px));display:flex;align-items:center;gap:9px;padding:8px 15px;border-radius:999px;
    font:600 13px/1.2 system-ui,-apple-system,"Segoe UI",sans-serif;color:#fff;background:rgba(14,16,26,.62);border:1px solid rgba(255,255,255,.16);white-space:nowrap;overflow:hidden;}
  #pal-ride .pr-chip i{width:10px;height:10px;border-radius:50%;background:var(--lc,#888);flex:none;box-shadow:0 0 0 3px rgba(255,255,255,.18);}
  #pal-ride .pr-chip span{opacity:.78;font-weight:500;overflow:hidden;text-overflow:ellipsis;}
  #pal-ride .pr-btns{position:absolute;right:20px;top:18px;display:flex;gap:8px;}
  #pal-ride .pr-btns button{cursor:pointer;border-radius:999px;padding:7px 14px;font:700 12px system-ui,-apple-system,"Segoe UI",sans-serif;color:#fff;background:rgba(14,16,26,.62);border:1px solid rgba(255,255,255,.2);}
  #pal-ride .pr-btns button:hover{background:rgba(44,48,72,.82);}
  #pal-ride .pr-live{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;}
  /* the panel stays above the ride; a blurred panel over a moving canvas would cost every frame, so it goes solid */
  html.pal-fp #pal-tr{z-index:420;-webkit-backdrop-filter:none;backdrop-filter:none;background:color-mix(in srgb,var(--surface,#fff) 95%,transparent);}
  html.pal-fp #pal-chiprt,html.pal-fp #pal-relrt{display:none !important;}
  #pal-tr .pr-sw{margin-top:7px;}
  #pal-tr .pr-ex{display:none;}
  html.pal-fp #pal-tr .pr-ex{display:inline-block;}
  html.mobile #pal-ride,html:not(.alto-palace) #pal-ride,html.printing #pal-ride,html.detail-open #pal-ride{display:none !important;}
  @media (prefers-reduced-motion: reduce){#pal-ride{transition:none;}}
"""

RIDE_CSS = RIDE_CSS_MAIN + CSS_GL + CSS_E + CSS_F + CSS_G

_API = r"""
function init(e){ E=e; RIDE_M=null; if(!init.done){ init.done=1; bind(); }
  /* the street data of the real-geometry view (palace_street.py): the manifest named by the page's map data; the shards follow on demand. Without it (or if it cannot be fetched) the ride and the walk stay on the lattice. */
  try{ var sh=e&&e.M&&e.M.street&&e.M.street.h; if(sh && window._palStreet && !window._palStreet.ready() && !init.sl){ init.sl=1; window._palStreet.load('/street/palace-street-'+sh+'.json').then(null,function(){ init.sl=0; }); } }catch(x){}
  return true; }
function stats(){ var a=(R.samples||[]).slice().sort(function(p,q){ return p-q; }), n=a.length; return {avg:R.ms, worst:R.worst, frames:R.frames, n:n, p50:n?a[n>>1]:0, p95:n?a[Math.min(n-1,Math.floor(n*.95))]:0, max:n?a[n-1]:0}; }
function resetStats(){ R.samples=[]; R.worst=0; R.frames=0; R.ms=0; }
/* tests and the QA kit: play a leg between two buildings by name, seek to a time, read the model */
function demo(a, b, mode){ var S=window._palTr.state(); S.mode=mode||S.mode||'transit'; var plan=window._palDir.legPlan(a, b, S.mode); if(!plan) return false;
  var o={a:a, b:b, d:'', opt:plan, lines:plan.lines||[], color:'#888'}; return leg(o, false, function(){}); }
function simTo(t){ var M=R.M; if(!M) return false; if(R.raf){ cancelAnimationFrame(R.raf); R.raf=0; } R.playing=false; R.t=0; TN=null; R.tun=0; R.yaw=null; R.lastEv=null; R.quiet=1;
  var dt=1/30, steps=Math.floor(t/dt); for(var i=0;i<steps;i++){ R.t=i*dt; render(dt); } R.t=Math.min(t,M.T); render(dt); R.quiet=0; showNow(); return true; }
/* the cost of a frame with the canvas flushed (a one-pixel read-back makes the browser finish the drawing): n frames along the model */
function bench(n){ var M=R.M; if(!M) return null; R.quiet=1; var t=[], ctx=R.ctx, keep=R.t, k;
  for(k=0;k<n;k++){ R.t=M.T*(k/n); var t0=performance.now(); render(1/60); ctx.getImageData(0,0,1,1); t.push(performance.now()-t0); } R.t=keep; R.quiet=0;
  t.sort(function(p,q){ return p-q; }); return {n:n, avg:t.reduce(function(p,q){ return p+q; },0)/n, p50:t[n>>1], p95:t[Math.floor(n*.95)], max:t[n-1], w:R.w, h:R.h, dpr:R.dpr}; }
function play(){ if(R.M){ R.playing=true; kick(); } }
function pause(){ R.playing=false; }
window._palRide={real:REAL, roam:(typeof ROAM!=='undefined'?ROAM:null), ui:(typeof UIX!=='undefined'?UIX:null), mb:MB, init:init, leg:leg, lineEnter:lineEnter, lineStep:lineStep, exit:exit, mark:mark, switchHtml:switchHtml, toggle:toggle,
  active:function(){ return R.active; }, pref:pref, setPref:function(v){ setPref(v); labelBtns(); }, stats:stats, resetStats:resetStats, demo:demo, simTo:simTo, bench:bench, play:play, pause:pause,
  model:function(){ return R.M; }, time:function(){ return R.t; }, flash:function(){ return {RING_HZ:RING_HZ, MAX_FLASH_HZ:MAX_FLASH_HZ, BAR_HZ:BAR_HZ, HUE_DPS:HUE_DPS}; }, build:buildModel,
  canvas:function(){ return R.cv; }, unlock:function(){ R.saved=null; }};
"""

RIDE_JS = "\n(function(){\nif(window._palRide) return;\n" + STREET_JS + JS_A + JS_MB + JS_B + JS_DOOR_GEO + JS_GL + JS_C + JS_D + JS_G + JS_H + JS_E + JS_F + JS_REAL + JS_STREET + _API + "})();\n"


# ── the ride is code the page loads, not part of the page ──────────────────
# RIDE_JS is ~370 KB (130 KB gzipped). A private page is ONE Firestore document (under 1,000,000 stored bytes: private_shell.MAX_PAGE_BYTES), and
# the palace page is already within ~15 KB of that, so the ride cannot ride inside it. It is a static file of the site instead
# (/ride/palace-ride-<hash>.js, written by publish_static.regenerate_site, kept by the browser for a year): it holds no timeline content at
# all (the renderer, the vehicle frames, the landmark models), and the page loads it where RIDE_JS used to stand. The page works without it
# (every use is guarded by `window._palRide`), a ride simply is not offered.
import hashlib as _hashlib

import json as _json

# the ride's own rules go with it (a style element added before its script runs): ~3 KB gzipped less in the page
RIDE_ASSET = ("(function(){var s=document.createElement('style');s.id='pal-ride-css';s.textContent=" + _json.dumps(RIDE_CSS)
              + ";(document.head||document.documentElement).appendChild(s);})();\n" + RIDE_JS)
RIDE_V = _hashlib.sha256(RIDE_ASSET.encode("utf-8")).hexdigest()[:10]
RIDE_PATH = f"/ride/palace-ride-{RIDE_V}.js"
# Loaded where RIDE_JS stood, before the palace's own code runs (which calls _palRide.init at once): a synchronous request answered from the
# browser's cache after the first visit, then the text run as an inline script (CSP allows inline scripts, not eval; document.write would
# run it only after the whole page script ended). A failed request leaves _palRide undefined and every use of it is guarded.
RIDE_LOADER = ("\n(function(){ if(window._palRide) return; try{ var x=new XMLHttpRequest(); x.open('GET','" + RIDE_PATH + "',false); x.send(null);"
               " if(x.status===200 && x.responseText){ var s=document.createElement('script'); s.text=x.responseText;"
               " (document.head||document.documentElement).appendChild(s); if(s.parentNode) s.parentNode.removeChild(s); } }catch(e){} })();\n")


def ride_asset() -> tuple[str, str]:
    """(file name under /ride/, the script) for the site."""
    return RIDE_PATH.rsplit("/", 1)[1], RIDE_ASSET
