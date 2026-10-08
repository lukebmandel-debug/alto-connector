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

from .backgrounds_catalog import PHOTOS

BG_V = "1"
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


def tune(p: dict) -> dict:
    """The photo's lift and veil for each theme, from its measured luminance.

    Light: lift a dark photo (at most 2x) until its middle is ~0.55, then veil
    until the middle is ~0.78 and the darkest tenth ~0.62 — the pale ground the
    light engine expects. Dark: dim a bright photo (at least 0.55x) toward ~0.30,
    then veil until the middle is ~0.15 and the brightest tenth ~0.34."""
    L10, L50, L90 = p["L10"], p["L50"], p["L90"]
    # dark
    bd = 1.0 if L50 <= 0.30 else max(0.55, 0.30 / L50)
    m, h = L50 * bd, L90 * bd
    vd = _clamp(max((m - 0.15) / (m - 0.04), (h - 0.34) / (h - 0.04), 0.0), 0.20, 0.70)
    # light
    bl = 1.0 if L50 >= 0.55 else min(2.0, 0.55 / max(L50, 0.06))
    m, lo = min(1.0, L50 * bl), min(1.0, L10 * bl)
    vl = _clamp(max((0.78 - m) / (0.97 - m), (0.62 - lo) / (0.97 - lo), 0.0), 0.22, 0.70)

    def settle(color, b, v, veil):
        c = tuple(min(255, ch * b) for ch in _rgb(color))
        return _hex(_mix(c, veil, v))
    return {
        "bl": round(bl, 2), "vl": round(vl, 2), "bd": round(bd, 2), "vd": round(vd, 2),
        # what the page's backdrop looks like at rest, for the colour a gate
        # paints while it opens (ql/qd) and for the status bar (tl/td, its top edge)
        "ql": settle(p["mean"], bl, vl, _VEIL_L), "qd": settle(p["mean"], bd, vd, _VEIL_D),
        "tl": settle(p["top"], bl, vl, _VEIL_L), "td": settle(p["top"], bd, vd, _VEIL_D),
    }


def client_catalog() -> dict:
    """What a page needs to know about each photograph, as compactly as it can:
    id -> {g group, n name, f file, by author, l licence, u source page, m mean
    colour, bl/vl lift and veil in light, bd/vd in dark, ql/qd gate colour, tl/td
    status-bar colour}."""
    out = {}
    for p in PHOTOS:
        t = tune(p)
        out[p["id"]] = {"g": p["group"], "n": p["name"], "f": p["id"] + ".jpg",
                        "by": p["by"], "l": p["lic"], "u": p["url"], "m": p["mean"],
                        **t}
    return out


def catalog_json() -> str:
    return json.dumps(client_catalog(), separators=(",", ":"), ensure_ascii=False
                      ).replace("</", "<\\/")


# ── in <head>: apply the choice before anything paints ──────────────────────
# (Safari takes the colour of its bar strips from the first layout, and the
# private shell paints a gate while a timeline opens; both must already know.)
HEAD_JS = r"""(function(){
  var C=__CATALOG__, KEY=__KEY__, BASE=__BASE__, r=document.documentElement;
  var VARS=['--alto-img','--alto-mean','--alto-veil-l','--alto-veil-d','--alto-bright-l','--alto-bright-d','--alto-q-l','--alto-q-d'];
  var cur='';
  // On a web address. A share is shown in a srcdoc frame whose own address is about:srcdoc, so ask the
  // base URL it inherits (the same question the page's local-file links ask); a downloaded copy is file:.
  function web(){ return /^https?:/i.test(document.baseURI || location.href); }
  function read(){ try{ var s=JSON.parse(localStorage.getItem(KEY)||'null'); return (s && s.v) || ''; }catch(e){ return ''; } }
  // the opaque key in a private or shared page's address: what a gate knows about this page before it has it
  function gate(){ var p=location.pathname.split('/').filter(Boolean); return (p[0]==='pv' || p[0]==='s') && p[1] ? p[0]+'/'+p[1] : ''; }
  function remember(c){
    var k=gate(); if(!k) return;
    try{
      var m=JSON.parse(localStorage.getItem('alto-bgq-v1')||'{}') || {};
      if(!c && !(k in m)) return;          // nothing chosen, nothing remembered: no write
      if(c) m[k]=[c.ql,c.qd]; else delete m[k];
      var ks=Object.keys(m); if(ks.length>60) delete m[ks[0]];
      localStorage.setItem('alto-bgq-v1',JSON.stringify(m));
    }catch(e){}
  }
  // The status-bar colour follows the photograph's top edge; with none it is the engine's own pair.
  var touched=false;
  function bar(){
    var m=document.getElementById('meta-theme'); if(!m) return;
    var dark=r.classList.contains('dark'), c=cur && C[cur];
    if(!c && !touched) return;             // never chosen: the engine's own colour, untouched
    touched=!!c;
    m.setAttribute('content', c ? (dark ? c.td : c.tl) : (dark ? '#6b4326' : '#ffc59e'));
  }
  function apply(id){
    var c=C[id], st=r.style;
    if(!c || !web()){
      cur='';
      if(r.classList.contains('alto-bg')){ r.classList.remove('alto-bg'); VARS.forEach(function(v){ st.removeProperty(v); }); bar(); }
      window._altoBgId=''; remember(null); return;
    }
    cur=id; window._altoBgId=id;
    st.setProperty('--alto-img','url('+BASE+c.f+')'); st.setProperty('--alto-mean',c.m);
    st.setProperty('--alto-veil-l','rgba(247,249,253,'+c.vl+')'); st.setProperty('--alto-veil-d','rgba(8,10,18,'+c.vd+')');
    st.setProperty('--alto-bright-l',c.bl); st.setProperty('--alto-bright-d',c.bd);
    st.setProperty('--alto-q-l',c.ql); st.setProperty('--alto-q-d',c.qd);
    r.classList.add('alto-bg'); bar(); remember(c);
  }
  window._altoBg={C:C, key:KEY, base:BASE, read:read, apply:apply,
    choose:function(id){ try{ localStorage.setItem(KEY, JSON.stringify({v:id||'', t:Date.now()})); }catch(e){} apply(id); }};
  apply(read());
  window.addEventListener('alto-bg', function(){ apply(read()); });
  window.addEventListener('storage', function(e){ if(e && e.key===KEY) apply(read()); });
  // The engine sets the bar colour itself when the page loads and when the theme flips; ours goes last.
  new MutationObserver(bar).observe(r,{attributes:true,attributeFilter:['class']});
  document.addEventListener('DOMContentLoaded', bar);
  window.addEventListener('load', bar);
})();"""


def head_block(key: str) -> str:
    """The <script> for <head>. `key` is the localStorage key of this page's choice."""
    js = (HEAD_JS.replace("__CATALOG__", catalog_json())
          .replace("__KEY__", json.dumps(key)).replace("__BASE__", json.dumps(BG_BASE)))
    return '<script id="alto-bg-head">' + js + "</script>"


# ── the photograph behind the glass ─────────────────────────────────────────
CSS = """
/* Backgrounds (backgrounds.py): inert unless <html> carries alto-bg. */
html.alto-bg{ --alto-veil:var(--alto-veil-l); --alto-bright:var(--alto-bright-l); background-color:var(--alto-q-l); }
html.alto-bg.dark{ --alto-veil:var(--alto-veil-d); --alto-bright:var(--alto-bright-d); background-color:var(--alto-q-d); }
html.alto-bg #page-bg:not(#_), html.alto-bg.mobile.rw #page-bg:not(#_){ overflow:hidden !important; background:var(--alto-mean) !important; }
html.alto-bg #page-bg::before{ content:''; position:absolute; inset:-40px; pointer-events:none;
  background:var(--alto-img) center / cover no-repeat;
  -webkit-filter:brightness(var(--alto-bright)) blur(6px) saturate(1.15); filter:brightness(var(--alto-bright)) blur(6px) saturate(1.15); }
html.alto-bg #page-bg::after{ content:''; position:absolute; inset:0; pointer-events:none; background:var(--alto-veil); }
/* the veil is the wallpaper's now: no second frosted plate, and the slab over the timeline
   lets the photo through (it used to hide the wallpaper entirely) */
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
.bg-tile:hover{ box-shadow:0 0 0 1px var(--muted); }
.bg-tile.active{ border-color:var(--accent, #6d5bd0); box-shadow:none; }
.bg-tile:focus-visible{ outline:2px solid var(--accent, #6d5bd0); outline-offset:2px; }
#bg-panel .bg-foot{ font-size:11px; line-height:1.5; color:var(--muted); margin:6px 2px 2px; min-height:1.5em; }
html.mobile #bg-panel .bg-foot{ padding:8px 16px 0; margin:0; border-top:1px solid var(--header-hairline, var(--border)); }
#bg-panel .bg-foot a{ color:inherit; text-decoration:underline; }
html.printing #bg-toggle, html.printing #bg-panel{ display:none !important; }
"""

UI_JS = r"""(function(){
  var B=window._altoBg; if(!B || window._altoBgUi) return; window._altoBgUi=1;
  var root=document.documentElement, LABEL=__LABEL__, RAIL=__RAIL__;
  function mobile(){ return root.classList.contains('mobile'); }
  function mk(tag, cls, txt){ var e=document.createElement(tag); if(cls) e.className=cls; if(txt!=null) e.textContent=txt; return e; }
  var ICON='<svg viewBox="0 0 20 20" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" aria-hidden="true"><rect x="2.5" y="3.5" width="15" height="13" rx="2.4"/><circle cx="7" cy="8" r="1.4" fill="currentColor" stroke="none"/><path d="M3 14.5l4.2-4.2 3.3 3.3 2.2-2.2 4.3 4.3"/></svg>';
  var tab, panel, body, foot, tiles=[], drawn=false;
  function credit(){
    var id=B.read(), c=B.C[id]; foot.textContent='';
    if(!c){ foot.textContent='The Alto wallpaper.'; return; }
    foot.appendChild(document.createTextNode(c.n+' — '+c.by+' · '+c.l+' · '));
    var a=mk('a',null,'source'); a.href=c.u; a.target='_blank'; a.rel='noopener'; foot.appendChild(a);
  }
  function mark(){
    var cur=B.read();
    tiles.forEach(function(t){ var on=(t.getAttribute('data-bg')||'')===cur; t.classList.toggle('active',on); t.setAttribute('aria-pressed',on?'true':'false'); });
    if(tab) tab.classList.toggle('active', !!cur);
    if(foot) credit();
  }
  function tile(id, c){
    var b=mk('button','bg-tile'); b.type='button'; b.setAttribute('data-bg',id);
    if(c){
      var im=new Image(); im.alt=''; im.decoding='async'; im.loading='lazy'; im.src=B.base+'t/'+c.f; b.appendChild(im);
      b.appendChild(mk('span','bg-name',c.n)); b.setAttribute('aria-label',c.n+', '+c.g);
    } else { b.classList.add('bg-def'); b.appendChild(mk('span','bg-name','Alto')); b.setAttribute('aria-label','Alto wallpaper'); }
    b.addEventListener('click', function(){ B.choose(id); mark(); });
    tiles.push(b); return b;
  }
  function draw(){
    if(drawn) return; drawn=true;
    var groups=[], by={};
    Object.keys(B.C).forEach(function(id){ var g=B.C[id].g; if(!by[g]){ by[g]=[]; groups.push(g); } by[g].push(id); });
    function sec(title, ids){
      var s=mk('div','bg-sec'); s.appendChild(mk('div','bg-h',title));
      var g=mk('div','bg-grid'); ids.forEach(function(id){ g.appendChild(tile(id, B.C[id])); }); s.appendChild(g); return s;
    }
    var first=mk('div','bg-sec'), g0=mk('div','bg-grid'); g0.appendChild(tile('',null)); first.appendChild(g0);
    body.appendChild(first);
    groups.forEach(function(g){ body.appendChild(sec(g, by[g])); });
    mark();
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
    }).observe(root,{attributes:true,attributeFilter:['class']});
    window.addEventListener('alto-bg', mark);
    window.addEventListener('storage', function(e){ if(e && e.key===B.key) mark(); });
    mark();
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
