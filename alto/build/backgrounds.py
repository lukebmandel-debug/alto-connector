"""Backgrounds: a choice of photographs behind a timeline, and behind the homepage.

What a user picks is one id (or none: the Alto wallpaper). It is stored per
timeline in the browser as `{v, t}` under the timeline's own key
(`alto-hl-{tid}-bg`, so a share re-stamps it like every other per-timeline key)
and, for the account that owns the timeline, in its Firestore record, newest
choice winning (alto-cloud.js). The homepage and the reports page share one
choice of their own (`alto-bg-home-v1`).

Nothing is baked into a page: a timeline built before this existed shows the
same thing it always did until someone picks, and a pick needs no rebuild.
What a page carries is

  * HEAD_JS, in <head> before first paint, which reads the choice and sets the
    classes and custom properties below (and the status-bar colour, and the
    colour a private timeline's gate paints while it opens);
  * CSS, inert unless <html> has `alto-bg`;
  * UI_JS, the Background tab and its picker.

How a photograph is made to sit behind the existing glass. The engine's text,
lines and glass were all drawn for a pale wallpaper in light mode and a deep one
in dark, so the photograph is eased toward whichever the theme expects rather
than the UI being redrawn for every photo: it is lifted (or dimmed), blurred a
little, and a veil of the theme's own base colour goes over it, the veil's
strength worked out per photo and per theme from the photo's measured
luminance. That keeps the engine's contrast assumptions (the Alto mark's choice
of its pale or deep gradient, the muted ink of the labels on the top bar)
true for any photo. The unit-coloured glass over the page is thinned so the
photo shows through it, and the filters that blurred the wallpaper
(backdrop-filter, which Chrome does not apply under the page zoom) are replaced
by a blur on the photo itself, so every engine draws the same picture.

Photographs are served from /bg/v{BG_V}/ on the user's own site (publish_static)
and cached for a year; bump BG_V if a file ever changes.
"""
from __future__ import annotations

import json

from .backgrounds_catalog import COLOURS, PATTERNS, SCENES

BG_V = "2"
BG_BASE = f"/bg/v{BG_V}/"

# The base colours of the engine's own light and dark glass: a veil of these
# makes the page read as it always has.
_VEIL_L = (247, 249, 253)
_VEIL_D = (8, 10, 18)


def _rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(c) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in c)


def _mix(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def tune(p: dict, theme: str) -> dict:
    """The lift and veil for one photograph in one theme ("l" or "d"), from its measured luminance.

    Light: lift a dark photo (at most 2x) until its middle is ~0.55, then veil
    until the middle is ~0.70 and the darkest tenth ~0.52 — the pale ground the
    light engine expects. Dark: dim a bright photo (at least 0.55x) toward ~0.30,
    then veil until the middle is ~0.15 and the brightest tenth ~0.34. (The light
    set is chosen bright and the dark set dim, so neither does much.)"""
    L10, L50, L90 = p["L10"], p["L50"], p["L90"]
    if theme == "d":
        b = 1.0 if L50 <= 0.30 else max(0.55, 0.30 / L50)
        m, h = L50 * b, L90 * b
        v = _clamp(max((m - 0.15) / (m - 0.04), (h - 0.34) / (h - 0.04), 0.0), 0.20, 0.70)
        veil = _VEIL_D
    else:
        b = 1.0 if L50 >= 0.55 else min(2.0, 0.55 / max(L50, 0.06))
        m, lo = min(1.0, L50 * b), min(1.0, L10 * b)
        v = _clamp(max((0.70 - m) / (0.97 - m), (0.52 - lo) / (0.97 - lo), 0.0), 0.10, 0.70)
        veil = _VEIL_L

    def settle(color):
        c = tuple(min(255, ch * b) for ch in _rgb(color))
        return _hex(_mix(c, veil, v))
    return {
        "b": round(b, 2), "v": round(v, 2),
        # what the page's backdrop looks like at rest, for the colour a gate paints while it opens (q)
        # and for the status bar (s, the top edge); a: the top edge before the veil, which fills the
        # strip behind the top bars (the photograph starts below them)
        "q": settle(p["mean"]), "s": settle(p["top"]),
        "a": _hex(tuple(min(255, ch * b) for ch in _rgb(p["top"]))),
    }


def client_catalog() -> dict:
    """What a page needs to know about each background, as compactly as it can.
    A photograph (k "p"): g group, and for each theme (l, d) {n name, f file, w/h size, x/y where its
    subject sits, by author, lic licence, u source page, m mean colour, b lift, v veil, q gate colour,
    s status-bar colour, a top-strip colour}. A colour (k "c"): n, l and d = [from, to]. A pattern
    (k "x"): n, p kind, l and d = [from, to, ink, ink alpha]."""
    out = {}
    for sc in SCENES:
        e = {"g": sc["group"], "k": "p"}
        for m in ("l", "d"):
            v = sc[m]
            e[m] = {"n": v["name"], "f": f"{sc['id']}-{m}.jpg", "w": v["w"], "h": v["h"],
                    "x": v["fx"], "y": v["fy"], "by": v["by"], "lic": v["lic"], "u": v["url"],
                    "m": v["mean"], **tune(v, m)}
        out[sc["id"]] = e
    for c in COLOURS:
        out[c["id"]] = {"g": "Colors", "k": "c", "n": c["name"], "l": list(c["l"]), "d": list(c["d"])}
    for c in PATTERNS:
        out[c["id"]] = {"g": "Patterns", "k": "x", "n": c["name"], "p": c["kind"],
                        "l": list(c["l"]), "d": list(c["d"])}
    return out


def catalog_json() -> str:
    return json.dumps(client_catalog(), separators=(",", ":"), ensure_ascii=False
                      ).replace("</", "<\\/")


# ── in <head>: apply the choice before anything paints ──────────────────────
# (Safari takes the colour of its bar strips from the first layout, and the
# private shell paints a gate while a timeline opens; both must already know.)
#
# What the page does with a choice:
#   photograph  — the variant for the theme in use is drawn from just below the top bars (so its
#                 subject is never behind them), sized to cover the open area and placed so its
#                 subject (catalog x/y) lands in the middle of that area; the strip behind the bars
#                 is the photograph's own top edge colour. Recomputed on resize and theme change.
#   colour      — a soft gradient for the theme in use.
#   pattern     — a repeating mark over a gradient, built here from the catalog's kind.
#   custom      — "c:rrggbb": a colour of the user's own, drawn like the presets (pale in light, deep in dark).
HEAD_JS = r"""(function(){
  var C=__CATALOG__, KEY=__KEY__, BASE=__BASE__, r=document.documentElement;
  var VARS=['--alto-bg','--alto-top','--alto-q','--alto-veil','--alto-bright','--alto-blur','--alto-t','--alto-mask'];
  var cur='', sig='', touched=false;
  var HEX=/^c:([0-9a-f]{6})$/;
  function isDark(){ return r.classList.contains('dark'); }
  // On a web address. A share is shown in a srcdoc frame whose own address is about:srcdoc, so ask the
  // base URL it inherits (the same question the page's local-file links ask); a downloaded copy is file:.
  function web(){ return /^https?:/i.test(document.baseURI || location.href); }
  function read(){ try{ var s=JSON.parse(localStorage.getItem(KEY)||'null'); return (s && s.v) || ''; }catch(e){ return ''; } }
  // the opaque key in a private or shared page's address: what a gate knows about this page before it has it
  function gate(){ var p=location.pathname.split('/').filter(Boolean); return (p[0]==='pv' || p[0]==='s') && p[1] ? p[0]+'/'+p[1] : ''; }
  function h2n(h){ return parseInt(h.slice(1),16); }
  function mix(h,t,to){ var n=h2n(h), c=[n>>16&255,n>>8&255,n&255], o=to?255:0;
    return '#'+c.map(function(v){ return ('0'+Math.round(v+(o-v)*t).toString(16)).slice(-2); }).join(''); }
  function rgba(h,a){ var n=h2n(h); return 'rgba('+(n>>16&255)+','+(n>>8&255)+','+(n&255)+','+a+')'; }
  // an id -> its entry: the catalog's, or one made from a colour the user picked
  function get(id){
    if(C[id]) return C[id];
    var m=HEX.exec(id||''); if(!m) return null; var h='#'+m[1];
    return {g:'Colors', k:'c', n:'Custom color', custom:h, l:[mix(h,.84,true), mix(h,.66,true)], d:[mix(h,.80,false), mix(h,.90,false)]};
  }
  function svgu(s){ return 'url("data:image/svg+xml,'+encodeURIComponent(s)+'")'; }
  // the repeating mark of a pattern, over its gradient
  function pattern(kind, v){
    var a=v[0], b=v[1], ink=v[2], al=v[3], i=rgba(ink,al), S='<svg xmlns="http://www.w3.org/2000/svg" ', st='fill="none" stroke="'+ink+'" stroke-opacity="'+al+'" stroke-width="1.4" ';
    var L={
      dots:['radial-gradient('+i+' 1.7px, transparent 2.3px) 0 0/24px 24px'],
      grid:['linear-gradient('+i+' 1px, transparent 1px) 0 0/34px 34px','linear-gradient(90deg,'+i+' 1px, transparent 1px) 0 0/34px 34px'],
      lines:['repeating-linear-gradient(135deg,'+i+' 0,'+i+' 1.2px, transparent 1.2px, transparent 13px)'],
      waves:[svgu(S+'width="80" height="24"><path '+st+'d="M0 12 Q20 0 40 12 T80 12"/></svg>')+' 0 0/80px 24px'],
      hex:[svgu(S+'width="56" height="100"><path '+st+'d="M28 2 L54 17 L54 49 L28 64 L2 49 L2 17 Z M28 64 L28 98 M2 49 L-2 51 M54 49 L58 51"/></svg>')+' 0 0/56px 100px'],
      chevron:[svgu(S+'width="44" height="22"><path '+st+'d="M0 22 L22 2 L44 22"/></svg>')+' 0 0/44px 22px'],
      diamond:[svgu(S+'width="42" height="42"><path '+st+'d="M21 1 L41 21 L21 41 L1 21 Z"/></svg>')+' 0 0/42px 42px'],
      paper:[svgu(S+'width="160" height="160"><filter id="n" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" stitchTiles="stitch"/><feColorMatrix values="0 0 0 0 '+(h2n(ink)>>16&255)/255+' 0 0 0 0 '+(h2n(ink)>>8&255)/255+' 0 0 0 0 '+(h2n(ink)&255)/255+' '+al*1.2+' 0 0 0 -.2"/></filter><rect width="160" height="160" filter="url(#n)"/></svg>')+' 0 0/160px 160px']
    }[kind]||[];
    return L.concat(['linear-gradient(160deg,'+a+','+b+')']).join(',');
  }
  function remember(c){
    var k=gate(); if(!k) return;
    try{
      var m=JSON.parse(localStorage.getItem('alto-bgq-v1')||'{}') || {};
      if(!c && !(k in m)) return;          // nothing chosen, nothing remembered: no write
      if(c) m[k]=[c.k==='p' ? c.l.q : c.l[0], c.k==='p' ? c.d.q : c.d[0]]; else delete m[k];
      var ks=Object.keys(m); if(ks.length>60) delete m[ks[0]];
      localStorage.setItem('alto-bgq-v1',JSON.stringify(m));
    }catch(e){}
  }
  // The status-bar colour follows the background's top edge; with none it is the engine's own pair.
  function bar(){
    var m=document.getElementById('meta-theme'); if(!m) return;
    var c=cur && get(cur), dark=isDark();
    if(!c && !touched) return;             // never chosen: the engine's own colour, untouched
    touched=!!c;
    var v=c && (c.k==='p' ? (dark ? c.d.s : c.l.s) : (dark ? c.d[0] : c.l[0]));
    m.setAttribute('content', v || (dark ? '#6b4326' : '#ffc59e'));
  }
  // The bars across the top, as far down as they reach, in the page-bg layer's own pixels.
  function inset(pb, z){
    var mob=r.classList.contains('mobile'), t=pb.getBoundingClientRect().top, bt=0;
    ['title-bar','nav'].forEach(function(id){
      var e=document.getElementById(id); if(!e) return; var q=e.getBoundingClientRect();
      if(q.height>0 && q.bottom>bt) bt=q.bottom;
    });
    if(!bt) return mob ? 132 : 84;
    return Math.max(0, Math.round((bt-t)/z));
  }
  var VW='', VT=0;
  function geometry(v){
    var pb=document.getElementById('page-bg'); if(!pb || !pb.clientHeight || !pb.clientWidth) return null;
    var q=pb.getBoundingClientRect(), z=q.height/pb.clientHeight || 1, W=pb.clientWidth, H=pb.clientHeight, T=inset(pb,z);
    var bw=W+80, bh=H-T+80, s=Math.max(bw/v.w, bh/v.h), iw=v.w*s, ih=v.h*s;
    var open=Math.max(120, (window.innerHeight-q.top)/z - T);
    var tx=40+W*.5, ty=40+open*.5;
    var ox=Math.min(0, Math.max(bw-iw, tx-v.x*iw)), oy=Math.min(0, Math.max(bh-ih, ty-v.y*ih));
    return {T:T, bg:'url('+BASE+v.f+') '+ox.toFixed(1)+'px '+oy.toFixed(1)+'px / '+iw.toFixed(1)+'px '+ih.toFixed(1)+'px no-repeat'};
  }
  function clear(){
    cur=''; sig='';
    if(r.classList.contains('alto-bg')){ r.classList.remove('alto-bg'); VARS.forEach(function(v){ r.style.removeProperty(v); }); bar(); }
    window._altoBgId=''; remember(null);
  }
  // draw what is chosen, for the theme in use; cheap when nothing it depends on has changed
  function paint(){
    var c=cur && get(cur); if(!c || !web()){ if(cur || r.classList.contains('alto-bg')) clear(); return; }
    var dark=isDark(), st=r.style, key, bg, top, q, veil='transparent', bright=1, blur='0px', T=0, mask='none';
    if(c.k==='p'){
      var v=dark ? c.d : c.l, g=geometry(v);
      key=[cur,dark,g?g.bg:'',g?g.T:''].join('|'); if(key===sig) return; sig=key;
      bg=g ? g.bg : 'url('+BASE+v.f+') '+(v.x*100)+'% '+(v.y*100)+'% / cover no-repeat'; T=g ? g.T : (r.classList.contains('mobile') ? 132 : 84);
      top=v.a; q=v.q; bright=v.b; blur='6px'; mask='linear-gradient(transparent,#000 40px)';
      veil=(dark ? 'rgba(8,10,18,' : 'rgba(247,249,253,')+v.v+')';
    } else {
      var w=dark ? c.d : c.l; key=[cur,dark].join('|'); if(key===sig) return; sig=key;
      bg=c.k==='x' ? pattern(c.p, w) : 'linear-gradient(160deg,'+w[0]+','+w[1]+')'; top=w[0]; q=w[0];
    }
    st.setProperty('--alto-bg',bg); st.setProperty('--alto-top',top); st.setProperty('--alto-q',q); st.setProperty('--alto-veil',veil);
    st.setProperty('--alto-bright',bright); st.setProperty('--alto-blur',blur); st.setProperty('--alto-t',T+'px'); st.setProperty('--alto-mask',mask);
    r.classList.add('alto-bg'); window._altoBgId=cur; bar(); remember(c);
  }
  function apply(id){ cur=get(id) ? id : ''; sig=''; paint(); }
  window._altoBg={C:C, key:KEY, base:BASE, read:read, apply:apply, get:get, dark:isDark, paint:paint, pattern:pattern,
    choose:function(id){ try{ localStorage.setItem(KEY, JSON.stringify({v:id||'', t:Date.now()})); }catch(e){} apply(id); }};
  window._altoBgId='';
  apply(read());
  window.addEventListener('alto-bg', function(){ apply(read()); });
  window.addEventListener('storage', function(e){ if(e && e.key===KEY) apply(read()); });
  // The engine sets the bar colour itself when the page loads and when the theme flips; ours goes last. A
  // theme flip, or the page zoom changing (a style on <html>), draws the picture again.
  new MutationObserver(function(){ bar(); paint(); }).observe(r,{attributes:true,attributeFilter:['class','style']});
  var raf=0; function soon(){ if(raf) return; raf=requestAnimationFrame(function(){ raf=0; paint(); }); }
  document.addEventListener('DOMContentLoaded', function(){ bar(); sig=''; paint(); });
  window.addEventListener('load', function(){ bar(); soon(); });
  window.addEventListener('resize', soon);
  window.addEventListener('orientationchange', soon);
})();"""


def head_block(key: str) -> str:
    """The <script> for <head>. `key` is the localStorage key of this page's choice."""
    js = (HEAD_JS.replace("__CATALOG__", catalog_json())
          .replace("__KEY__", json.dumps(key)).replace("__BASE__", json.dumps(BG_BASE)))
    return '<script id="alto-bg-head">' + js + "</script>"


# ── the background behind the glass ─────────────────────────────────────────
CSS = """
/* Backgrounds (backgrounds.py): inert unless <html> carries alto-bg. */
html.alto-bg{ background-color:var(--alto-q); }
html.alto-bg #page-bg:not(#_), html.alto-bg.mobile.rw #page-bg:not(#_){ overflow:hidden !important; background:var(--alto-top) !important; }
html.alto-bg #page-bg::before{ content:''; position:absolute; left:-40px; right:-40px; bottom:-40px; top:calc(var(--alto-t, 0px) - 40px); pointer-events:none;
  background:var(--alto-bg); -webkit-mask-image:var(--alto-mask); mask-image:var(--alto-mask);
  -webkit-filter:brightness(var(--alto-bright)) blur(var(--alto-blur)) saturate(1.15); filter:brightness(var(--alto-bright)) blur(var(--alto-blur)) saturate(1.15); }
html.alto-bg #page-bg::after{ content:''; position:absolute; inset:0; pointer-events:none; background:var(--alto-veil); }
/* the veil is the wallpaper's now: no second frosted plate, and the slab over the timeline
   lets the background through (it used to hide the wallpaper entirely) */
html.alto-bg #page-glass:not(#_){ background:none !important; -webkit-backdrop-filter:none !important; backdrop-filter:none !important; }
html.alto-bg:not(.mobile) #glass-slab{ -webkit-backdrop-filter:none !important; backdrop-filter:none !important; opacity:.5; }
html.alto-bg:not(.mobile) .phase-band{ opacity:.35; }
html.printing.alto-bg #page-bg::before, html.printing.alto-bg #page-bg::after{ display:none; }
"""

# ── the Background tab and its picker ───────────────────────────────────────
UI_CSS = """
/* the Background tab: the right rail's fourth (desktop), the tile above INFO (phone) */
#bg-toggle{ touch-action:manipulation; }
html:not(.mobile) #bg-toggle{ width:34px; height:34px; box-sizing:border-box; padding:0; display:flex;
  align-items:center; justify-content:center; cursor:pointer; position:relative;
  background:var(--card-glass-bg, var(--surface));
  -webkit-backdrop-filter:blur(18px) saturate(190%); backdrop-filter:blur(18px) saturate(190%);
  border:1px solid var(--card-glass-border, var(--border)); border-right:none; border-radius:6px 0 0 6px;
  color:var(--muted); box-shadow:0 10px 26px var(--node-rest-shadow); }
html:not(.mobile) #bg-toggle span{ display:none; }
html:not(.mobile) #bg-toggle:hover{ color:var(--text); border-color:var(--muted); }
html:not(.mobile) #tab-rail > #bg-toggle{ position:static; }
#bg-toggle.active{ color:var(--accent, #6d5bd0); border-color:var(--accent, #6d5bd0); }
html.mobile #bg-toggle{ position:fixed; left:0; bottom:calc(66px + env(safe-area-inset-bottom, 0px)); z-index:295;
  min-width:36px; height:49px; box-sizing:border-box; padding:10px 4px; display:flex; flex-direction:column;
  align-items:center; justify-content:center; gap:4px; background:var(--card-glass-bg);
  -webkit-backdrop-filter:blur(12px) saturate(170%); backdrop-filter:blur(12px) saturate(170%);
  border:1px solid var(--border); border-left:none; border-radius:0 6px 6px 0;
  box-shadow:0 10px 26px var(--node-rest-shadow), inset 0 0 0 0.5px var(--card-glass-rim);
  color:var(--text); font-size:8.5px; letter-spacing:.1em; text-transform:uppercase;
  font-family:-apple-system,BlinkMacSystemFont,sans-serif; cursor:pointer; -webkit-tap-highlight-color:transparent;
  transition:opacity .15s; }
html.mobile.has-filter-tab #bg-toggle{ bottom:calc(124px + env(safe-area-inset-bottom, 0px)); }
html.mobile #bg-toggle svg{ width:14px; height:14px; }
html.mobile #bg-toggle:active{ opacity:.6; }
html.mobile.detail-open #bg-toggle, html.mobile.summary-open #bg-toggle,
html.mobile.detail-open #bg-panel, html.mobile.summary-open #bg-panel{ display:none !important; }
/* the picker */
#bg-panel{ position:fixed; z-index:396; overflow:hidden; display:flex; flex-direction:column; padding:12px 12px 8px; border-radius:14px; opacity:0;
  pointer-events:none; transition:opacity .15s, transform .15s; color:var(--text);
  background:var(--panel-glass-bg, var(--surface));
  -webkit-backdrop-filter:blur(30px) saturate(185%); backdrop-filter:blur(30px) saturate(185%);
  border:1px solid var(--card-glass-border, var(--border)); box-shadow:0 18px 48px var(--node-hover-shadow); }
html:not(.mobile) #bg-panel{ right:46px; top:50%; width:372px; max-height:min(78vh,660px); transform:translateY(calc(-50% + 8px)); }
html:not(.mobile) #bg-panel.open{ opacity:1; pointer-events:auto; transform:translateY(-50%); }
html.mobile #bg-panel{ inset:0; width:auto; max-height:none; padding:0 0 calc(14px + env(safe-area-inset-bottom, 0px)); border-radius:0; border:0; z-index:401; opacity:1;
  transform:translateX(-100%); -webkit-backdrop-filter:blur(24px) saturate(185%); backdrop-filter:blur(24px) saturate(185%);
  box-shadow:none; transition:transform .22s cubic-bezier(.4,0,.2,1); -webkit-overflow-scrolling:touch; touch-action:manipulation; }
html.mobile #bg-panel.open{ pointer-events:auto; transform:none; }
html.mobile.rw #bg-panel .bg-head{ position:relative; }
#bg-panel .bg-head{ display:flex; justify-content:space-between; align-items:center; gap:10px; font-size:10px;
  letter-spacing:.16em; text-transform:uppercase; color:var(--muted); margin:0 2px 8px; min-height:20px; }
#bg-panel .bg-sub{ margin-left:auto; letter-spacing:.08em; opacity:.8; }
html.mobile #bg-panel .bg-head{ position:sticky; top:0; z-index:1; margin:0 0 12px; padding:16px 16px 12px; font-size:12px;
  letter-spacing:.14em; background:var(--panel-glass-bg); border-bottom:1px solid var(--header-hairline, var(--border)); }
#bg-close{ display:none; width:32px; height:32px; border-radius:50%; cursor:pointer; font-size:14px; align-items:center;
  justify-content:center; color:var(--text); letter-spacing:0; background:var(--card-glass-bg); border:1px solid var(--card-glass-border); }
html.mobile #bg-close{ display:flex; }
#bg-panel .bg-body{ flex:1 1 auto; min-height:0; overflow-y:auto; -webkit-overflow-scrolling:touch; }
#bg-panel .bg-head, #bg-panel .bg-foot{ flex:none; }
#bg-panel .bg-sec{ margin:0 0 12px; }
html.mobile #bg-panel .bg-sec{ padding:0 16px; margin-bottom:18px; }
#bg-panel .bg-h{ font-size:10px; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); margin:2px 2px 7px; }
html.mobile #bg-panel .bg-h{ font-size:11px; margin-bottom:9px; }
#bg-panel .bg-grid{ display:grid; grid-template-columns:repeat(3, 1fr); gap:8px; }
.bg-tile{ position:relative; display:block; width:100%; aspect-ratio:16 / 10; padding:0; margin:0; overflow:hidden; cursor:pointer;
  border-radius:10px; border:2px solid transparent; background:var(--surface); font:inherit; color:#fff;
  box-shadow:0 0 0 1px var(--border); -webkit-tap-highlight-color:transparent; }
.bg-tile img{ position:absolute; inset:0; width:100%; height:100%; object-fit:cover; display:block; }
.bg-tile .bg-name{ position:absolute; left:0; right:0; bottom:0; padding:14px 6px 4px; font-size:10px; line-height:1.2; text-align:left;
  background:linear-gradient(transparent, rgba(0,0,0,.62)); text-shadow:0 1px 2px rgba(0,0,0,.5); overflow:hidden;
  text-overflow:ellipsis; white-space:nowrap; }
.bg-tile.bg-def{ background:var(--page-grad); }
.bg-tile.bg-sw{ aspect-ratio:16 / 9; }
.bg-tile.bg-sw .bg-name{ color:#fff; mix-blend-mode:normal; }
.bg-tile.bg-custom{ background:conic-gradient(#ff6f91,#b06ef0,#5b8cff,#28b9c4,#39dc84,#f5c542,#ff6f91); }
.bg-tile.bg-custom.set{ background:var(--bg-custom, #888); }
.bg-tile .bg-pick{ position:absolute; inset:0; width:100%; height:100%; opacity:0; cursor:pointer; border:0; padding:0; }
.bg-tile.bg-custom .bg-name::before{ content:'+ '; }
.bg-tile:hover{ box-shadow:0 0 0 1px var(--muted); }
.bg-tile.active{ border-color:var(--accent, #6d5bd0); box-shadow:none; }
.bg-tile:focus-visible{ outline:2px solid var(--accent, #6d5bd0); outline-offset:2px; }
#bg-panel .bg-foot{ font-size:11px; line-height:1.5; color:var(--muted); margin:6px 2px 2px; min-height:1.5em; }
html.mobile #bg-panel .bg-foot{ padding:8px 16px 0; margin:0; border-top:1px solid var(--header-hairline, var(--border)); }
#bg-panel .bg-foot a{ color:inherit; text-decoration:underline; }
html.printing #bg-toggle, html.printing #bg-panel{ display:none !important; }
/* on a phone the sheet runs under the bottom bar too (the runway, 140px): lift its last rows and its credit line above it */
html.rw #bg-panel:not(#_), html.mobile.rw #bg-panel:not(#_){ padding-bottom:calc(154px + env(safe-area-inset-bottom, 0px)) !important; }
"""

UI_JS = r"""(function(){
  var B=window._altoBg; if(!B || window._altoBgUi) return; window._altoBgUi=1;
  var root=document.documentElement, LABEL=__LABEL__, RAIL=__RAIL__;
  function mobile(){ return root.classList.contains('mobile'); }
  function mk(tag, cls, txt){ var e=document.createElement(tag); if(cls) e.className=cls; if(txt!=null) e.textContent=txt; return e; }
  var ICON='<svg viewBox="0 0 20 20" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" aria-hidden="true"><rect x="2.5" y="3.5" width="15" height="13" rx="2.4"/><circle cx="7" cy="8" r="1.4" fill="currentColor" stroke="none"/><path d="M3 14.5l4.2-4.2 3.3 3.3 2.2-2.2 4.3 4.3"/></svg>';
  var tab, panel, body, foot, tiles=[], drawn=false, customTile=null, customInput=null, lastDark=null;
  function dark(){ return root.classList.contains('dark'); }
  function variant(c){ return c.k==='p' ? (dark() ? c.d : c.l) : null; }
  function credit(){
    var id=B.read(), c=B.get(id); foot.textContent='';
    if(!c){ foot.textContent='The Alto wallpaper.'; return; }
    if(c.k!=='p'){ foot.textContent=c.n+(c.k==='x' ? ' pattern' : ' color')+' — for the light and the dark theme.'; return; }
    var v=variant(c);
    foot.appendChild(document.createTextNode(v.n+' — '+v.by+' · '+v.lic+' · '));
    var a=mk('a',null,'source'); a.href=v.u; a.target='_blank'; a.rel='noopener'; foot.appendChild(a);
  }
  function mark(){
    var cur=B.read(), custom=/^c:[0-9a-f]{6}$/.test(cur);
    tiles.forEach(function(t){ var id=t.getAttribute('data-bg')||'', on=id===cur || (id==='c:' && custom);
      t.classList.toggle('active',on); t.setAttribute('aria-pressed',on?'true':'false'); });
    if(customTile){ var h=custom ? '#'+cur.slice(2) : ''; customTile.classList.toggle('set', !!h); if(h) customTile.style.setProperty('--bg-custom', h); else customTile.style.removeProperty('--bg-custom'); if(customInput && h) customInput.value=h; }
    if(tab) tab.classList.toggle('active', !!cur);
    if(foot) credit();
  }
  // the tiles take the theme in use: a photograph's light or dark picture, a colour's or pattern's own
  function dress(t){
    var id=t.getAttribute('data-bg'), c=id && B.get(id); if(!c) return;
    if(c.k==='p'){
      var v=variant(c), im=t.querySelector('img'), nm=t.querySelector('.bg-name');
      var src=B.base+'t/'+v.f; if(im && im.getAttribute('src')!==src) im.src=src; if(nm) nm.textContent=v.n; t.setAttribute('aria-label',v.n+', '+c.g);
    } else if(c.k==='c'){ var w=dark() ? c.d : c.l; t.style.background='linear-gradient(160deg,'+w[0]+','+w[1]+')'; }
    else { var q=B.pattern(c.p, dark() ? c.d : c.l); t.style.background=q; }
  }
  function tile(id, c){
    var b=mk('button','bg-tile'); b.type='button'; b.setAttribute('data-bg',id);
    if(c && c.k==='p'){
      var im=new Image(); im.alt=''; im.decoding='async'; im.loading='lazy'; b.appendChild(im);
      b.appendChild(mk('span','bg-name','')); 
    } else if(c){ b.classList.add('bg-sw'); b.appendChild(mk('span','bg-name',c.n)); b.setAttribute('aria-label',c.n+', '+(c.k==='x' ? 'pattern' : 'color')); }
    else { b.classList.add('bg-def'); b.appendChild(mk('span','bg-name','Alto')); b.setAttribute('aria-label','Alto wallpaper'); }
    b.addEventListener('click', function(){ B.choose(id); mark(); });
    tiles.push(b); if(c) dress(b); return b;
  }
  function custom(){
    var b=mk('label','bg-tile bg-sw bg-custom'); b.setAttribute('data-bg','c:'); customTile=b;
    b.appendChild(mk('span','bg-name','Custom'));
    var inp=mk('input','bg-pick'); inp.type='color'; inp.value='#6d8fd8'; inp.setAttribute('aria-label','Pick a colour'); customInput=inp;
    inp.addEventListener('input', function(){ var h=(inp.value||'').toLowerCase(); if(/^#[0-9a-f]{6}$/.test(h)){ B.choose('c:'+h.slice(1)); mark(); } });
    b.appendChild(inp); tiles.push(b); return b;
  }
  function draw(){
    if(drawn) return; drawn=true;
    var order=[], by={};
    Object.keys(B.C).forEach(function(id){ var g=B.C[id].g; if(!by[g]){ by[g]=[]; order.push(g); } by[g].push(id); });
    function sec(title, ids, extra){
      var s=mk('div','bg-sec'); if(title) s.appendChild(mk('div','bg-h',title));
      var g=mk('div','bg-grid'); ids.forEach(function(id){ g.appendChild(tile(id, B.C[id])); }); if(extra) g.appendChild(extra); s.appendChild(g); return s;
    }
    var first=mk('div','bg-sec'), g0=mk('div','bg-grid'); g0.appendChild(tile('',null)); first.appendChild(g0);
    body.appendChild(first);
    // colours and patterns first (they are the quick ones), then the photographs
    ['Colors','Patterns'].forEach(function(g){ if(by[g]) body.appendChild(sec(g, by[g], g==='Colors' ? custom() : null)); });
    order.forEach(function(g){ if(g!=='Colors' && g!=='Patterns') body.appendChild(sec(g, by[g])); });
    lastDark=dark(); mark();
  }
  function open(v){
    if(!panel) return;
    if(v) draw();
    panel.classList.toggle('open', v); if(tab) tab.setAttribute('aria-expanded', v?'true':'false');
  }
  function build(){
    if(document.getElementById('bg-toggle')) return;
    tab=mk('button'); tab.id='bg-toggle'; tab.type='button'; tab.title='Background'; tab.setAttribute('aria-label','Background');
    tab.setAttribute('aria-expanded','false'); tab.innerHTML=ICON+'<span>SCENE</span>';
    panel=mk('div'); panel.id='bg-panel'; panel.setAttribute('role','dialog'); panel.setAttribute('aria-label','Background');
    var head=mk('div','bg-head'), cls=mk('button'); cls.id='bg-close'; cls.type='button'; cls.setAttribute('aria-label','Close'); cls.innerHTML='&#x2715;';
    var act=mk('span','bg-act'); act.style.display='flex'; act.style.alignItems='center'; act.style.gap='10px';
    act.appendChild(mk('span','bg-sub',LABEL)); act.appendChild(cls);
    head.appendChild(mk('span','bg-t','Background')); head.appendChild(act); panel.appendChild(head);
    body=mk('div','bg-body'); foot=mk('div','bg-foot'); panel.appendChild(body); panel.appendChild(foot);
    document.body.appendChild(panel);
    // Desktop: the fourth tab of the rail, after Filter. Filter's own script may add its tab later, so keep ours last.
    var rail=document.getElementById('tab-rail');
    if(RAIL && !mobile() && rail){
      rail.appendChild(tab);
      new MutationObserver(function(){ if(rail.lastElementChild!==tab) rail.appendChild(tab); }).observe(rail,{childList:true});
    } else document.body.appendChild(tab);
    tab.addEventListener('click', function(e){ e.stopPropagation(); open(!panel.classList.contains('open')); });
    cls.addEventListener('click', function(){ open(false); });
    document.addEventListener('click', function(e){
      if(panel.classList.contains('open') && !e.target.closest('#bg-panel') && !e.target.closest('#bg-toggle')) open(false);
    });
    document.addEventListener('keydown', function(e){ if(e.key==='Escape') open(false); });
    var tries=0;
    (function wire(){
      if(!mobile()) return;
      if(typeof window._altoPanelSwipe!=='function'){ if(++tries<80) setTimeout(wire,250); return; }
      window._altoPanelSwipe(panel,{swipeSign:-1,closeVal:'translateX(-100%)',noButtonGuard:true,
        isOpen:function(){ return panel.classList.contains('open'); }, closeFn:function(){ open(false); }});
    })();
    new MutationObserver(function(){
      if(root.classList.contains('detail-open') || root.classList.contains('summary-open')) open(false);
      if(lastDark!==dark()){ lastDark=dark(); if(drawn) tiles.forEach(dress); credit(); }
    }).observe(root,{attributes:true,attributeFilter:['class']});
    window.addEventListener('alto-bg', mark);
    window.addEventListener('storage', function(e){ if(e && e.key===B.key) mark(); });
    lastDark=dark(); mark();
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', build); else build();
})();"""


# The homepage and the reports page have no rail, and never carry the `mobile`
# class (their phone layout is a media query), so the tab sits on the right edge
# there and the picker narrows to the screen on a phone.
HOME_CSS = """
html:not(.mobile) body > #bg-toggle{ position:fixed; right:0; top:calc(50% - 17px); z-index:300; }
@media (max-width:640px){
  /* a phone gets the full-screen sheet the timeline's tile opens (see html.mobile above) */
  html:not(.mobile) #bg-panel{ left:0; right:0; top:0; bottom:0; width:auto; max-height:none; padding:0 0 calc(14px + env(safe-area-inset-bottom, 0px));
    border-radius:0; border:0; z-index:401; opacity:1; transform:translateX(-100%); box-shadow:none;
    -webkit-backdrop-filter:blur(24px) saturate(185%); backdrop-filter:blur(24px) saturate(185%);
    transition:transform .22s cubic-bezier(.4,0,.2,1); touch-action:manipulation; }
  html:not(.mobile) #bg-panel.open{ pointer-events:auto; transform:none; }
  html:not(.mobile) #bg-panel .bg-head{ margin:0 0 12px; padding:16px 16px 12px; font-size:12px; letter-spacing:.14em;
    background:var(--panel-glass-bg); border-bottom:1px solid var(--header-hairline, var(--border)); }
  html:not(.mobile) #bg-close{ display:flex; }
  html:not(.mobile) #bg-panel .bg-sec{ padding:0 16px; margin-bottom:18px; }
  html:not(.mobile) #bg-panel .bg-h{ font-size:11px; margin-bottom:9px; }
  html:not(.mobile) #bg-panel .bg-foot{ padding:8px 16px 0; margin:0; border-top:1px solid var(--header-hairline, var(--border)); }
}
"""


def ui_block(label: str, rail: bool) -> str:
    """The Background tab and picker: <style> + <script>, for the end of <body>.
    `label` says whose background this is; `rail` puts the tab in the timeline's
    right-edge rail (the homepage has none)."""
    js = UI_JS.replace("__LABEL__", json.dumps(label)).replace("__RAIL__", "true" if rail else "false")
    return ('<style id="alto-bg-css">' + CSS + UI_CSS + ("" if rail else HOME_CSS) + "</style>\n"
            '<script id="alto-bg-ui">' + js + "</script>")
