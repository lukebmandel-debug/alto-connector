"""Holographic's animated backgrounds (Luke, 2026-11-05, option sheet holo-anim-bg: "I like all of them for each respective background, and each holographic
background should have its own animation").

One slow moving layer over a Holographic background, each background with its own animation (the sheet's three, each on the scene it was shown over):
  A  falling signal   on Signal rain    (rain)   three fields of faint streaks falling at 9, 15 and 24 seconds a pass
  B  scan sweep       on Grid horizon   (sweep)  one soft band drifting down the page every 16 seconds
  C  slow lightspeed  on Lightspeed     (drift)  two sets of streaks swelling out from the middle and fading, a wave every 7 seconds
  D  neon rain        on Neon rain      (neon)   slanted rain at the scene's 12 degree lean, calmer than the sheet's demo (Luke: "make rain a little calmer"), and the
                                                 scene's two neon signs that flicker off gently once in 12 seconds. Periodic over a 12 s LOOP (rain 4 s and 6 s a tile, signs 12 s),
                                                 and PLAYED AS A VIDEO (holo_video.py, Luke 2026-11-05: "like a lofi background music animation that repeats ... even 10 second
                                                 loop is fine, just make transition smooth"): the compositor drew the CSS version at 18-21% of a core in WindowServer, a hardware-decoded
                                                 clip is far cheaper. The CSS layer stays as the fallback when the clip cannot play.
  E  amber haze       on Amber haze     (haze)   dust drifting on the wind in two depths (52 s and 30 s a tile) and the low sun's glow breathing over 12 seconds
  F  targeting        on Targeting      (target) a range ping swelling from the display's middle every 6 seconds and the two dashed rings turning slowly against each other
The last three are ORG/option-sheets/holo-anim-extras (Art's sheet), approved by Luke 2026-11-05. They sit on a "scene box" laid exactly over the background's own picture
(16:10, centred, bottom-aligned, covering the picture's own area: backgrounds.py paints it on #page-bg::before, 40px past the window on three sides, `cover`), so a sign,
the sun and the display's middle land on the picture's. The box is sized by the script (hafit) from the layer's own rectangle, never by vw/vh or container units: the page is zoomed
(html{zoom}), and WebKit and Blink disagree about what a viewport or container unit means inside a zoomed page; a pixel and a percentage mean the same in both.

The rules (the cost, the sheet's measurement: a page standing still 1.0% of one core, A 1.2%, B 1.7%, C 2.0%):
  transform and opacity only, on a layer of their own (will-change); the layer is one fixed element behind the page's content, never over a card, a label or a line;
  Reduce Motion stops every one (the layer is not drawn at all); print hides them; a phone has none (the layer is drawn on a computer's page only, and the CSS shows it
  only at 641px and wider); a hidden tab pauses them (html.hp-hid, holo.py); Holographic is dark on a computer, so the layer is drawn for the dark theme only.
The hosted Holographic script carries all of it (holo.py): the page holds nothing. A page that draws no background of its own choice (a System, an Atlas, a city map:
its chosen background shows only behind a detail page) has no animation either, because the layer follows the background that is painted.
"""
from __future__ import annotations

import json as _json
import math
import random
import re
from urllib.parse import quote, unquote

from . import holo_backgrounds as _hb, holo_video as _hv

IDS = {"h-signal-rain": "rain", "h-grid-horizon": "sweep", "h-lightspeed": "drift", "h-neon-rain": "neon", "h-amber-haze": "haze", "h-targeting": "target"}   # background id -> its animation
INK = "79,240,224"
INK_HEX = "4ff0e0"          # the style's cyan light (holo.py TOKENS dark ac)
LOOP = 12                   # seconds: Neon rain's loop. Every layer's period divides it (rain 4 s and 6 s a tile, both signs 12 s), so frame 360 is frame 0 and the video's seam is invisible
W = 2560                    # the widest screen the streaks are laid over; a wider one repeats nothing, it just has bare edges
# What ships (Board B-1105-190000, Luke's video-only rule): a Holographic background animates ONLY as a video loop that has passed, never as a CSS loop. Until the quiet-Mac CPU
# number for the Neon rain clip has gone to Luke, every background ships STILL. The release flips this one constant to "video" (Neon rain's clip; the others stay still).
#   "still"  no layer at all (the default)          "video"  a background with a clip plays it; a clip that cannot play leaves the still background
#   "all"    the design reference: clip where there is one, the CSS layer elsewhere and as the clip's fallback (QA and the Art sheet only)
# A computer can try another for itself: localStorage 'alto-holo-anim' = still | video | all (QA; nothing in the UI sets it).
MODE = "still"
MODES = ("still", "video", "all")


def _rain() -> str:
    """Three fields of streaks, each a tall tile (height = the fall of one pass) repeated down the page; one gradient (--gN) is the streak, each position one copy."""
    R = random.Random(21)
    spec = ((230, 9, 1, .55, 44), (340, 15, 1, .42, 32), (520, 24, 2, .30, 24))     # (tile height px, seconds, streak width px, tail opacity, streaks)
    out = [f".ha-rain{{{';'.join(f'--g{i + 1}:linear-gradient(180deg,rgba({INK},0) 0,rgba({INK},0) 62%,rgba({INK},{a}) 100%)' for i, (_, _, _, a, _) in enumerate(spec))}}}"]
    for i, (h, sec, w, _, n) in enumerate(spec):
        layers = ",".join(f"var(--g{i + 1}) {R.randrange(W)}px {R.randrange(h)}px/{w}px {h}px repeat-y" for _ in range(n))
        out.append(f".ha-rain i:nth-of-type({i + 1}){{top:-{h}px;height:calc(100% + {h}px);background:{layers};animation:ha-fall{i + 1} {sec}s linear infinite}}"
                   f"@keyframes ha-fall{i + 1}{{to{{transform:translateY({h}px)}}}}")
    return "\n".join(out)


def _drift_svg() -> str:
    """The lightspeed streaks (the background's own: stars stretched out from the middle), as one path."""
    R = random.Random(9)
    d = ""
    for _ in range(110):
        t = R.uniform(0, 2 * math.pi)
        r0 = R.uniform(40, 420)
        ln = r0 * R.uniform(.25, .8)
        d += f"M{r0 * math.cos(t):.0f} {r0 * math.sin(t):.0f}L{(r0 + ln) * math.cos(t):.0f} {(r0 + ln) * math.sin(t):.0f}"
    return ('<svg viewBox="-800 -500 1600 1000" preserveAspectRatio="xMidYMid slice" aria-hidden="true">'
            f'<path d="{d}" stroke="#dffcff" stroke-width="1.3" stroke-linecap="round" fill="none"/></svg>')


def _url(svg: str) -> str:
    return 'url("data:image/svg+xml,' + quote(svg.replace('"', "'"), safe=" '=/:;,.-()!") + '")'


def _tile(seed: int, w: int, h: int, n: int, make) -> str:
    R = random.Random(seed)
    return _url(f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}'>" + "".join(make(R) for _ in range(n)) + "</svg>")


# Neon rain. The sheet's demo had 22 near and 30 far streaks passing in 2.6 s and 4.8 s a tile; Luke, "a little calmer": about a third fewer, and a half slower.
def _neon_tiles() -> str:
    def streak(ln, lo, hi):
        return lambda R: f"<path d='M{R.randrange(500)} {R.randrange(300 - ln)}l0 {ln}' stroke='#a8d8ff' stroke-opacity='{R.uniform(lo, hi):.2f}' stroke-width='1'/>"
    return f":root{{--ha-rn:{_tile(31, 500, 300, 14, streak(42, .28, .43))};--ha-rf:{_tile(32, 500, 300, 19, streak(24, .20, .32))}}}"


# Amber haze: the sheet's two dust tiles (motes in the scene's own colours; the far one 400 x 300, the near one 500 x 360)
def _dust_tiles() -> str:
    def mote(c, r0, r1, a0, a1, w, h):
        return lambda R: f"<circle cx='{R.randrange(w)}' cy='{R.randrange(h)}' r='{R.uniform(r0, r1):.1f}' fill='{c}' fill-opacity='{R.uniform(a0, a1):.2f}'/>"
    return (f":root{{--ha-df:{_tile(41, 400, 300, 26, mote('#ffcf99', .8, 1.5, .26, .34, 400, 300))};"
            f"--ha-dn:{_tile(42, 500, 360, 10, mote('#ffd9a8', 1.6, 2.4, .12, .22, 500, 360))}}}")


# the scene's own signs (holo_backgrounds.neon_rain draws a 5 px wide bar down the side of a tower, the dark version's colour over #060812 towers): found in the picture
# itself, so a cover can stand exactly on each one
def _signs() -> list[tuple[float, float, float, float]]:
    dark = unquote(_hb.neon_rain()[1]["b"].split(" center bottom")[0])
    out = []
    for x, y, h in re.findall(r"<rect x='(-?\d+)' y='(-?\d+)' width='5' height='(\d+)'", dark):
        out.append((int(x) / 16, int(y) / 10, 5 / 16, int(h) / 10))        # percent of the 1600 x 1000 scene box
    return out


def _neon() -> tuple[str, str]:
    sg = [_signs()[i] for i in (2, 4)]         # the two the sheet flickers: the third tower's and the fifth's
    css = "".join(f".ha-neon .sg:nth-of-type({i + 1}){{left:{x:.2f}%;top:{y:.2f}%;width:{w + .06:.2f}%;height:{h:.2f}%;animation-duration:{LOOP}s;animation-delay:-{(0, 5)[i % 2]}s}}"
                  for i, (x, y, w, h) in enumerate(sg))
    return css, "".join("<i class=\"sg\"></i>" for _ in sg)


_NEON_CSS, _NEON_HTML = _neon()


# Targeting's picture keeps its two dashed rings; under the turning copies they make a moire. While the layer runs the picture is the same scene without them (the script
# puts html.ha-nd on); a phone, Reduce Motion, print and Classic keep the scene as it is.
_DA = _hb.targeting(False)[1]["b"]

CSS = ("""
#alto-ha{display:none;position:fixed;inset:0;overflow:hidden;pointer-events:none;z-index:0;contain:strict}
#alto-ha,#alto-ha *{pointer-events:none}
html.hp-hid #alto-ha *{animation-play-state:paused}
@media screen and (min-width:641px) and (prefers-reduced-motion:no-preference){
html.alto-holo:not(.mobile) #alto-ha{display:block}
""" + _rain() + f"""
.ha-rain i{{position:absolute;left:0;right:0;will-change:transform}}
.ha-sweep i{{position:absolute;left:0;right:0;top:-280px;height:280px;will-change:transform;
 background:linear-gradient(180deg,rgba({INK},0),rgba({INK},.10) 55%,rgba({INK},.22) 96%,rgba(160,255,248,.7) 100%);animation:ha-sweep 16s cubic-bezier(.45,.05,.55,.95) infinite}}
.ha-sweep i::after{{content:"";position:absolute;left:0;right:0;bottom:0;height:2px;background:rgba(160,255,248,.8);box-shadow:0 0 16px 3px rgba({INK},.6)}}
@keyframes ha-sweep{{0%{{transform:translateY(0)}}72%,100%{{transform:translateY(calc(100vh + 280px))}}}}
.ha-drift div{{position:absolute;inset:0;will-change:transform,opacity;transform-origin:50% 50%;animation:ha-drift 14s ease-in infinite;opacity:0}}
.ha-drift div+div{{animation-delay:-7s}}
.ha-drift svg{{display:block;width:100%;height:100%}}
@keyframes ha-drift{{0%{{transform:scale(.7);opacity:0}}15%{{opacity:.5}}100%{{transform:scale(1.7);opacity:0}}}}
.ha-scene{{position:absolute;bottom:-40px;left:50%;width:125%;aspect-ratio:16/10;transform:translateX(-50%)}}
.ha .zp{{position:absolute;left:0;top:0;width:100px;height:0;visibility:hidden}}
.ha-scene>*{{position:absolute}}
.ha-scene video{{display:block;left:0;top:0;width:100%;height:100%;opacity:0;transition:opacity .9s ease-out}}
.ha-scene video.on{{opacity:1}}
#alto-ha[data-v]{{clip-path:inset(max(0px,calc(var(--alto-t,0px) - 40px)) 0 0 0)}}
.ha-neon .rn,.ha-neon .rf{{position:absolute;inset:-15%;transform:rotate(12deg)}}
.ha-neon .rn i,.ha-neon .rf i{{position:absolute;left:0;right:0;top:-300px;height:calc(100% + 300px);will-change:transform}}
.ha-neon .rn i{{background:var(--ha-rn);animation:ha-nfall 4s linear infinite}}
.ha-neon .rf i{{background:var(--ha-rf);animation:ha-nfall 6s linear infinite}}
@keyframes ha-nfall{{to{{transform:translateY(300px)}}}}
.ha-neon .sg{{background:#060812;opacity:0;will-change:opacity;animation:ha-flick 12s linear infinite}}
@keyframes ha-flick{{0%,88%{{opacity:0}}89.7%{{opacity:.8}}91.2%{{opacity:.15}}92.7%{{opacity:.7}}94.4%,100%{{opacity:0}}}}
.ha-haze .dust{{position:absolute;top:0;bottom:0;right:0;will-change:transform}}
.ha-haze .df{{left:-400px;background:var(--ha-df);animation:ha-dfar 52s linear infinite}}
.ha-haze .dn{{left:-500px;background:var(--ha-dn);animation:ha-dnear 30s linear infinite}}
@keyframes ha-dfar{{to{{transform:translateX(400px)}}}}
@keyframes ha-dnear{{to{{transform:translateX(500px)}}}}
.ha-haze .sun{{left:37.13%;top:22.2%;width:49.75%;height:79.6%;background:radial-gradient(closest-side,rgba(255,177,90,.26),rgba(255,154,60,0));opacity:.35;will-change:opacity;animation:ha-breathe 12s ease-in-out infinite alternate}}
@keyframes ha-breathe{{from{{opacity:.35}}to{{opacity:1}}}}
.ha-target .pa,.ha-target .ring{{left:71.875%}}
.ha-target .pa{{top:52%;width:0;height:0;opacity:0;transform:scale(.17);will-change:transform,opacity;animation:ha-ping 6s cubic-bezier(.2,.6,.3,1) infinite}}
.ha-target .ping{{position:absolute;box-sizing:border-box;border:1.4px solid rgba({INK},.55);border-radius:50%}}
@keyframes ha-ping{{0%{{transform:scale(.17);opacity:.6}}100%{{transform:scale(1);opacity:0}}}}
.ha-target .ring{{will-change:transform}}
.ha-target .ring svg{{display:block;width:100%;height:100%}}
.ha-target .r1{{width:21.25%;height:34%;top:35%;margin-left:-10.625%;animation:ha-turn1 60s linear infinite}}
.ha-target .r2{{width:47.5%;height:76%;top:14%;margin-left:-23.75%;animation:ha-turn2 90s linear infinite}}
@keyframes ha-turn1{{to{{transform:rotate(360deg)}}}}
@keyframes ha-turn2{{to{{transform:rotate(-360deg)}}}}
html.ha-nd:not(.mobile) #page-bg::before{{background:"""+_DA+"""}
}
"""+_neon_tiles()+_dust_tiles()+_NEON_CSS+"""
@media print{#alto-ha{display:none !important}}
""")

_RING = lambda r, op, dash: (f'<svg viewBox="{-r - 2} {-r - 2} {2 * r + 4} {2 * r + 4}"><circle r="{r}" fill="none" stroke="#{INK_HEX}" stroke-opacity="{op}" '
                             f'stroke-dasharray="{dash}" stroke-width="1.4"/></svg>')
HTML = {"rain": "<i></i><i></i><i></i>", "sweep": "<i></i>", "drift": "<div>" + _drift_svg() + "</div><div>" + _drift_svg() + "</div>",
        "neon": '<div class="rf"><i></i></div><div class="rn"><i></i></div><div class="ha-scene">' + _NEON_HTML + "</div>",
        "haze": '<div class="ha-scene"><i class="sun"></i></div><div class="dust df"></div><div class="dust dn"></div>',
        "target": '<div class="ha-scene"><div class="pa"><i class="ping"></i></div><div class="ring r1">' + _RING(170, .35, "2 10") + '</div><div class="ring r2">' + _RING(380, .2, "40 14") + "</div></div>"}

# the hosted script's part: the layer follows the painted background (window._altoBgId), on a computer, with Holographic on, Reduce Motion off
JS = r"""
// the animated backgrounds (holo_anim.py): one layer, first in the body (under the page's content, over its background), drawn only for a background that has one
// Nothing happens before the page has loaded (WebKit's loads were slowed by layer work at start), nothing for a still background, a still mode or Reduce Motion, and the layer's
// rules go into the page only when a layer is first drawn.
var HA=__HA__, rmq=window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null, hamo=null, haok=document.readyState==='complete', hasig='', hafail={};
var HAM=(function(){ try{ var m=localStorage.getItem('alto-holo-anim'); if(HA.modes.indexOf(m)>=0) return m; }catch(e){} return HA.mode; })();
if(!haok) window.addEventListener('load', function(){ setTimeout(function(){ haok=true; hasync(); }, 0); });
function hasync(){
  var k=HA.ids[window._altoBgId||''], l=document.getElementById('alto-ha'), v=k && HAM!=='still' && HA.vid[k] && !hafail[k];
  if(!(k && haok && (v || HAM==='all') && r.classList.contains('alto-holo') && desk() && !(rmq && rmq.matches) && document.body)){ hasig=''; if(l) l.remove(); hand(false); return; }
  var sig=k+'|'+r.className+'|'+innerWidth+'x'+innerHeight;
  if(l && sig===hasig){ havis(l); return; }    // (the class watcher fires on every change of the root's classes: refit only when something that moves the box changed)
  hasig=sig;
  if(!document.getElementById('alto-ha-css')){ var c=document.createElement('style'); c.id='alto-ha-css'; c.textContent=HA.css; (document.head||r).appendChild(c); }
  if(!l){ l=document.createElement('div'); l.id='alto-ha'; l.setAttribute('aria-hidden','true'); document.body.insertBefore(l, document.body.firstChild); }
  if(l.getAttribute('data-k')!==k){ l.setAttribute('data-k',k); l.className='ha ha-'+k; l.removeAttribute('data-v'); if(v){ l.innerHTML='<b class="zp"></b><div class="ha-scene"></div>'; havid(l,k); } else l.innerHTML='<b class="zp"></b>'+HA.html[k]; }
  hafit(l); hand(k==='target' && !v); havis(l);
}
// a background with a clip (holo_video.py): the picture and its animation as one looping H.264 video in the scene box, muted, inline, fading in once it plays. If it cannot load
// or play (a blocked autoplay, a codec, the network) the layer falls back to the CSS animation, which is the same picture and motion. A hidden tab pauses it.
function havid(l,k){
  var s=l.querySelector('.ha-scene'), v=document.createElement('video');
  var css=function(){ if(l.getAttribute('data-k')!==k || l.querySelector('.rn,.ha-scene>i')) return; hafail[k]=1;
    if(HAM==='all'){ l.removeAttribute('data-v'); l.innerHTML='<b class="zp"></b>'+HA.html[k]; hafit(l); hand(k==='target'); } else hasync(); };   // (video mode: the still background stays)
  v.muted=true; v.defaultMuted=true; v.loop=true; v.autoplay=true; v.playsInline=true; v.preload='auto'; v.disablePictureInPicture=true; v.setAttribute('aria-hidden','true'); v.tabIndex=-1;
  v.setAttribute('muted',''); v.setAttribute('playsinline','');
  v.addEventListener('playing', function(){ v.classList.add('on'); l.setAttribute('data-v','1'); });
  v.addEventListener('error', css);
  v.src=HA.vid[k]; s.appendChild(v);
  var p=v.play(); if(p && p.catch) p.catch(css);
}
function havis(l){
  var v=l.querySelector('video'); if(!v) return;
  if(r.classList.contains('hp-hid')){ if(!v.paused) v.pause(); } else if(v.paused && v.readyState>1) v.play().catch(function(){});
}
function hand(on){ if(r.classList.contains('ha-nd')!==on) r.classList.toggle('ha-nd', on); }
// the scene box = the picture's area (#page-bg::before: the window and 40px past it on three sides, less --alto-t at the top; bottom-centred `cover`, 16:10); the rain's rotated sheets
// reach past every corner. All in the layer's own pixels, found from a 100px probe so the page's zoom cancels out.
function hafit(l){
  var p=l.firstChild, L=l.getBoundingClientRect(), z=(p && p.getBoundingClientRect().width/100)||1, s=l.querySelector('.ha-scene'), q=l.querySelectorAll('.rn,.rf');
  if(!L.width) return;
  if(s){ var t=(parseFloat(getComputedStyle(r).getPropertyValue('--alto-t'))||0)*z, w=Math.max(L.width+80*z, 1.6*(L.height+80*z-t)); s.style.width=(w/L.width*100).toFixed(3)+'%'; }
  var g=l.querySelector('.ping');     // the ping swells about a zero-size anchor, so no transform-origin has to be worked out under the page zoom (WebKit got it wrong)
  if(g && s){ var u=s.getBoundingClientRect().width/1600/z; g.style.width=g.style.height=(1040*u).toFixed(2)+'px'; g.style.left=g.style.top=(-520*u).toFixed(2)+'px'; }
  for(var i=0;i<q.length;i++) q[i].style.inset='-'+Math.ceil(.13*Math.max(L.width,L.height)/z)+'px';
}
function hawatch(on){
  if(on && !hamo && typeof MutationObserver==='function'){ hamo=new MutationObserver(hasync); hamo.observe(r,{attributes:true,attributeFilter:['class']}); }
  else if(!on && hamo){ hamo.disconnect(); hamo=null; }
}
window.addEventListener('alto-bg-painted', hasync); window.addEventListener('alto-bg', hasync);
if(rmq && rmq.addEventListener) rmq.addEventListener('change', hasync);
"""


def client() -> str:
    """The JSON the script reads: which background has which animation, and each one's layer."""
    assert MODE in MODES, MODE
    return _json.dumps({"ids": IDS, "html": HTML, "vid": _hv.paths(), "mode": MODE, "modes": list(MODES), "css": _slim(CSS)}, separators=(",", ":"))


def _slim(css: str) -> str:
    from . import retro as _rt
    return _rt._slim(css)
