"""The phone at rest: the page, and two small controls (Luke, 2026-10-24).

Luke on the phone's tiles: "Still too much clutter, especially on system format"; of the round-3 mockups he picked
"A + fade, but its a little too minimal right now and looks unbalanced". So on every format a phone opens (a timeline or
an outline one card at a time or whole, the System, the horizontal timeline, the Memory Blueprint and the Memory Atlas):

  * at rest only two controls, the same size and look, one in each bottom corner: FIND (bottom-left) opens a full-screen
    search sheet, MENU (bottom-right) the drawer. A horizontal timeline's step bar sits between them. Round, square in
    Retro (Luke's square Retro controls).
  * MAP, INFO ("How to use"), FILTER, NOTES, MARK and each format's own controls (the System's looks and toggles, the
    Atlas's Tour / World) are square buttons in the MENU grid; MARK and NOTES come back on an enlarged card, where
    there is text to mark (the detail page's own BACK and FIND are its own).
  * the controls fade after a few seconds without a touch; any touch brings them back, and a control still answers its
    first tap. Nothing fades while a finger is down, a field has the keyboard or a panel / drawer / sheet is open.
    With reduced motion they stay put (no fade at all).
  * search is a sheet, never a bar on the page (Luke: "I don't want search up at the top ... But I also don't want search
    at the bottom because then when the keyboard pops up, it moves"): its field pinned at the top, results under it,
    Done closes it, the page under it never moves. It is the phone's own search (alto-search-mobile) dressed full screen.
  * the System at rest is the chart: moons' and satellites' names wait for a closer look, rings and paths sit back.
  * the Memory Map keeps its own Apple-Maps page and its bottom search sheet; only its zoom pill goes (a pinch zooms).

Like the whole view (phone.py) this is a hosted script (/phone/alto-phone-min-<hash>.js), fetched synchronously in
<head> on a phone, so its rules are in before Safari first lays the page out; a page whose file cannot be had (an exported
copy, an Artifact preview) keeps the tiles it had before. ?pm=0 on a phone shows the page without it (QA).
"""
from __future__ import annotations

import hashlib as _hashlib
import json as _json

from .phone import FOLDER, _slim

GUARD = "_altoPhoneMin"

# ── in every page's <head> (a phone only) ──
HEAD_JS = r"""(function(){var q=location.search;if(!(/Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent)||/[?&]mobile/.test(q))||/[?&]pm=0/.test(q))return;if(!(__DEFAULT__||/[?&]pm=1/.test(q)))return;__LOAD__})();"""

X = ":not(#_):not(#__)"          # outranks the phone design's own rules (and phone.py's remap of them) whatever their order
P = "html.pmin:is(.mobile,.phone-whole)"
WH = "html.pmin:is(.phone-whole,.bldg-open,.wpal-open)"    # a page seen whole (System, horizontal timeline, Blueprint, Atlas, a switched timeline)
C = "#pmin-find,#hamburger-tab"   # the two controls

CSS = r"""
/* at rest: the controls that move into the MENU grid */
P :is(#minimap-toggle,#tutorial-toggle,#filter-toggle,#hl-mode-btn,#notes-toggle,#hl-color-palette,#sol-ctl,#sol-tour,#scroll-hint)X{display:none !important;}
P:not(.msearch-open) #m-search X{opacity:0 !important;pointer-events:none !important;}
P:not(.detail-open) #detail-back-fixed X{display:none !important;}
WH #timeline-label-bar X,WH #bldg-root :is(.bl-zoom,.bl-head :is(.bl-sub,.bl-note)),WH #wpal-root :is(.wp-ctl,.wp-key),html.pmin #pal-mmap .pm-zoom{display:none !important;}
/* an enlarged card: MARK and NOTES come back (there is text to mark), low on the right above MENU */
P.detail-open :is(#hl-mode-btn,#notes-toggle)X{display:flex !important;}
P.detail-open.hl-mode #hl-color-palette X{display:flex !important;}
/* the two controls: one size, one look, one in each bottom corner */
P :is(C)X{position:fixed !important;top:auto !important;bottom:calc(14px + env(safe-area-inset-bottom,0px)) !important;width:44px !important;height:44px !important;min-width:0 !important;
  min-height:0 !important;padding:0 !important;margin:0 !important;transform:none !important;border-radius:22px !important;border:1px solid var(--border,rgba(127,127,127,.3)) !important;
  display:flex !important;flex-direction:column !important;align-items:center !important;justify-content:center !important;gap:0 !important;box-sizing:border-box !important;z-index:296 !important;
  -webkit-tap-highlight-color:transparent;}
P #pmin-find X{left:14px !important;right:auto !important;}
P #hamburger-tab X{right:14px !important;left:auto !important;}
P :is(C) span X{display:none !important;}
P :is(C) svg X{width:18px !important;height:18px !important;}
html.pmin.alto-retro :is(C)X,html.pmin.sk-retro :is(C)X{border-radius:0 !important;}
P.detail-open #hamburger-tab X{display:none !important;}
P.detail-open :is(#hl-mode-btn,#notes-toggle)X{right:14px !important;left:auto !important;top:auto !important;transform:none !important;}
P.detail-open #notes-toggle X{bottom:calc(14px + env(safe-area-inset-bottom,0px)) !important;}
P.detail-open #hl-mode-btn X{bottom:calc(70px + env(safe-area-inset-bottom,0px)) !important;}
P.detail-open #pmin-find X{display:none !important;}
/* the horizontal timeline's step bar: low between the corners */
html.pmin.phone-whole #lanes-nav X{left:70px !important;right:70px !important;width:auto !important;max-width:none !important;transform:none !important;bottom:calc(18px + env(safe-area-inset-bottom,0px)) !important;}
/* a Blueprint's or an Atlas's plan starts under the header (the tiles that sat there are gone) */
WH #bldg-root :is(.bl-head,.bl-tabs){top:62px !important;}
WH #bldg-root .bl-head{font-size:12px !important;padding:8px 12px !important;max-width:calc(100% - 96px) !important;}
/* the fade */
html.pmin :is(C,#lanes-nav,#hl-mode-btn,#notes-toggle,#pal-mmap .pm-close)X{transition:opacity .6s ease !important;}
html.pmin.pmin-idle :is(C,#lanes-nav,#hl-mode-btn,#notes-toggle,#pal-mmap .pm-close)X{opacity:0 !important;}
@media (prefers-reduced-motion:reduce){html.pmin :is(C,#lanes-nav,#hl-mode-btn,#notes-toggle,#pal-mmap .pm-close)X{transition:none !important;}}
/* the search sheet: full screen, its field pinned at the top */
P.msearch-open #m-search X{position:fixed !important;top:0 !important;bottom:auto !important;left:0 !important;right:0 !important;transform:none !important;width:auto !important;max-width:none !important;
  height:calc(60px + env(safe-area-inset-top,0px)) !important;padding:env(safe-area-inset-top,0px) 12px 0 !important;border-radius:0 !important;z-index:9001 !important;opacity:1 !important;
  display:flex !important;align-items:center !important;background:var(--surface,#fff) !important;box-shadow:0 1px 0 var(--border) !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;}
P.msearch-open #m-search input X{flex:1;height:40px;border-radius:12px;padding:0 12px;background:color-mix(in srgb,var(--text) 7%,transparent);border:0;}
P.msearch-open #m-search-results X{display:block !important;position:fixed !important;top:calc(60px + env(safe-area-inset-top,0px)) !important;bottom:0 !important;left:0 !important;right:0 !important;
  transform:none !important;width:auto !important;max-width:none !important;max-height:none !important;border-radius:0 !important;z-index:9000 !important;background:var(--surface,#fff) !important;overflow-y:auto !important;}
html.pmin.alto-retro.msearch-open :is(#m-search,#m-search-results)X{background:#000 !important;}
P.msearch-open :is(C)X{opacity:0 !important;pointer-events:none !important;}
#pmin-done{display:none;}
P.msearch-open #pmin-done{display:block;flex:none;margin-left:10px;font:600 16px -apple-system,system-ui,sans-serif;color:var(--accent,#6d5bd0);background:none;border:0;padding:8px 2px;}
/* the open MENU: every item a square button, icon over its name, three to a row; the section names run across */
P #nav-drawer X{width:min(330px,88vw) !important;max-width:88vw !important;}
P #nav-drawer-body X{display:grid !important;grid-template-columns:repeat(3,1fr);gap:8px;padding:12px !important;align-content:start;}
P #nav-drawer-body>:not(.drawer-btn)X{grid-column:1/-1;margin:6px 2px 0 !important;}
P #nav-drawer-body .drawer-btn X{aspect-ratio:1;width:auto !important;min-width:0 !important;height:auto !important;min-height:0 !important;margin:0 !important;display:flex !important;
  flex-direction:column !important;align-items:center !important;justify-content:center !important;gap:7px;padding:8px 4px !important;border-radius:14px !important;text-align:center !important;}
html.pmin.alto-retro #nav-drawer-body .drawer-btn X{border-radius:0 !important;}
P #nav-drawer-body .drawer-btn>* X{border:0 !important;margin:0 !important;padding:0 !important;flex:none !important;}
P #nav-drawer-body .drawer-btn .drawer-icon X{width:auto !important;height:24px !important;display:flex !important;align-items:center;justify-content:center;font-size:20px;}
html.pmin:not(.has-filter-tab) #pmin-filter-toggle{display:none !important;}
P #nav-drawer-body #drawer-timeline-btn .drawer-icon X{font-size:13px !important;letter-spacing:.04em;}
P #nav-drawer-body .drawer-btn.pmin-word X{aspect-ratio:auto;height:44px !important;}
P #nav-drawer-body .drawer-btn.pmin-word .drawer-icon X{display:none !important;}
P #nav-drawer-body .drawer-btn .drawer-label X{font-size:11.5px !important;line-height:1.2 !important;letter-spacing:.02em;text-align:center !important;white-space:normal !important;}
/* the System at rest is the chart */
html.pmin.alto-solar #world .node:is([data-solar=moon],[data-solar=sat]):not(.focused):not(.ph-hover)>.sol-lbl{opacity:0 !important;}
html.pmin.alto-solar #canvas:not(.focus-mode) :is(#solar-svg,#river-svg){opacity:.22 !important;}
"""


def _expand(css: str) -> str:
    """CSS's shorthand: P a phone page, WH a page seen whole, C the two controls, X the specificity that outranks the phone design."""
    css = _slim(css)
    for a, b in (("WH ", WH + " "), ("P.", P + "."), ("P ", P + " "), ("P:", P + ":"), (":is(C", ":is(" + C), (" X", X), (")X", ")" + X)):
        css = css.replace(a, b)
    return css

# The two controls' glyphs: a magnifier for FIND (the search sheet), the engine's three lines for MENU
FIND_SVG = ('<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">'
            '<circle cx="8.6" cy="8.6" r="5.6"/><line x1="12.6" y1="12.6" x2="16.7" y2="16.7"/></svg>')

JS = r"""(function(){var de=document.documentElement;if(window._altoPhoneMin)return;window._altoPhoneMin=1;de.classList.add('pmin');
var st=document.createElement('style');st.id='alto-phone-min';st.textContent=__CSS__;(document.head||de).appendChild(st);
function last(){if(document.body&&st.parentNode!==document.body||st.nextElementSibling)document.body.appendChild(st);}
function $(i){return document.getElementById(i);}
/* FIND: the look of MENU, copied; it opens the phone's own search, dressed as a full-screen sheet */
function find(){var g=$('m-search-glyph'),w=$('m-search'),m=$('hamburger-tab');if(!g||!w||!m)return;var b=$('pmin-find');
if(!b){b=document.createElement('button');b.id='pmin-find';b.type='button';b.setAttribute('aria-label','Find');b.className=m.className;b.innerHTML=__FIND__;
var go=function(e){e.stopPropagation();var gg=$('m-search-glyph');if(gg)gg.click();};
/* a finger acts on touchend, as MENU does: iOS drops the click of a tap that brought a faded control back */
var t0=null;b.addEventListener('touchstart',function(e){var t=e.touches[0];t0=t&&[t.clientX,t.clientY];},{passive:true});
b.addEventListener('touchend',function(e){var t=e.changedTouches&&e.changedTouches[0],ok=t0&&(!t||Math.abs(t.clientX-t0[0])<10&&Math.abs(t.clientY-t0[1])<10);t0=null;if(!ok)return;e.preventDefault();go(e);},{passive:false});
b.addEventListener('click',go);m.parentNode.insertBefore(b,m);}
if(!$('pmin-done')){var d=document.createElement('button');d.id='pmin-done';d.type='button';d.textContent='Done';
d.addEventListener('click',function(e){e.stopPropagation();var i=w.querySelector('input');if(i)i.blur();setTimeout(function(){document.body.dispatchEvent(new MouseEvent('click',{bubbles:true}));if(de.classList.contains('msearch-open')){de.classList.remove('msearch-open');w.classList.remove('expanded');}},0);});w.appendChild(d);}}
/* MENU gains the controls that left the page: Map, Notes, Filter, (Highlight on a card), How to use, and a "View" list of
   the format's own (the System's looks and toggles, the Atlas's Tour / World), by their own names */
function grid(){var b=$('nav-drawer-body');if(!b)return;var at=$('drawer-view-btn')||$('drawer-scene-btn')||$('drawer-mode-btn');if(!at)return;
function row(txt,ic,fn,id){var r=document.createElement('button');r.type='button';r.className='drawer-btn';if(id)r.id=id;r.innerHTML='<span class="drawer-icon"></span><span class="drawer-label"></span>';
r.querySelector('.drawer-label').textContent=txt;if(ic)r.querySelector('.drawer-icon').innerHTML=ic;else r.classList.add('pmin-word');
r.addEventListener('click',function(e){e.stopPropagation();if(window.closeNavDrawer)closeNavDrawer();setTimeout(fn,0);});return r;}
/* each square as soon as its control exists (some come late: the System's FILTER leaves the desktop rail after load) */
var prev=at;[['minimap-toggle','Map','&#9638;'],['notes-toggle','Notes','&#9776;'],['filter-toggle','Filter','&#9661;'],['tutorial-toggle','How to use','&#9432;']].forEach(function(s){
var el=$(s[0]),r=$('pmin-'+s[0]);if(!r){if(!el||el.hasAttribute('hidden'))return;var sv=el.querySelector('svg');
r=row(s[1],sv?sv.outerHTML:s[2],s[0]==='minimap-toggle'?function(){tap($(s[0]));}:function(){$(s[0]).click();},'pmin-'+s[0]);}
if(prev.nextSibling!==r)prev.parentNode.insertBefore(r,prev.nextSibling);prev=r;});
if($('pmin-view'))return;var src=[].slice.call(document.querySelectorAll('#sol-ctl button,#wpal-root .wp-ctl button')).filter(function(x){return (x.textContent||'').trim().length>1;});if(!src.length)return;
var f=document.createDocumentFragment(),l=document.createElement('div');l.className='drawer-section-label';l.id='pmin-view';l.textContent='View';f.appendChild(l);
src.forEach(function(x){var v=x.querySelector('svg');f.appendChild(row(x.textContent.replace(/\s+/g,' ').trim().replace(/\s*(ON|OFF)$/,''),v?v.outerHTML:'',function(){x.click();}));});
prev.parentNode.insertBefore(f,prev.nextSibling);}
/* FIND wears MENU's look (glass, Retro's black and gold, dark or light), copied again whenever the page's look changes */
var LOOK=['backgroundColor','backgroundImage','borderColor','color','boxShadow','backdropFilter','webkitBackdropFilter'],lq=0;
function look(){lq=0;var m=$('hamburger-tab'),b=$('pmin-find');if(!m||!b)return;var c=getComputedStyle(m);LOOK.forEach(function(k){try{b.style[k]=c[k]}catch(e){}});}
new MutationObserver(function(){if(!lq)lq=requestAnimationFrame(look);}).observe(de,{attributes:true,attributeFilter:['class','data-theme','style']});
/* MAP answers a finger's touchend (the engine's list, the Memory Map's own page), not a click */
function tap(el){var e=new Event('touchend',{bubbles:true,cancelable:true});Object.defineProperty(e,'changedTouches',{value:[]});Object.defineProperty(e,'touches',{value:[]});el.dispatchEvent(e);}
/* the squares are checked again each time the drawer opens (a control may have come since) */
function hook(){var o=window.openNavDrawer;if(typeof o!=='function'||o._pmin)return;var w=function(){grid();return o.apply(this,arguments);};w._pmin=1;window.openNavDrawer=w;}
function build(){find();grid();hook();last();look();}
document.addEventListener('DOMContentLoaded',build);window.addEventListener('load',function(){build();setTimeout(build,1000);setTimeout(build,2500);});
/* the fade: a few seconds after the last touch, unless something is in hand */
var IDLE=3500,T=0,down=0,rm=window.matchMedia?matchMedia('(prefers-reduced-motion: reduce)'):{matches:false};
function busy(){var a=document.activeElement;if(down||a&&/^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)||a&&a.isContentEditable)return true;
if(/(^|\s)(msearch-open|hl-mode|tut-open|minimap-open)(\s|$)/.test(de.className))return true;
return !!document.querySelector('#nav-drawer.open,#notes-panel.open,#minimap.open,#minimap-panel.open,#filter-panel.open,.ef-panel.open,#tutorial-overlay.visible,#tut-overlay.open,#pal-mmap.pm-tall');}
function rest(){clearTimeout(T);if(rm.matches)return;if(busy()){T=setTimeout(rest,IDLE);return;}de.classList.add('pmin-idle');}
function wake(){de.classList.remove('pmin-idle');clearTimeout(T);if(!rm.matches)T=setTimeout(rest,IDLE);}
document.addEventListener('touchstart',function(e){down=e.touches.length;wake();},{capture:true,passive:true});
document.addEventListener('touchend',function(e){down=e.touches.length;wake();},{capture:true,passive:true});
document.addEventListener('touchcancel',function(e){down=e.touches.length;wake();},{capture:true,passive:true});
['pointerdown','keydown','wheel'].forEach(function(t){document.addEventListener(t,wake,{capture:true,passive:true});});
if(rm.addEventListener)rm.addEventListener('change',wake);window.addEventListener('load',wake);
window._altoPhoneMinApi={wake:wake,rest:rest,busy:busy,build:build};
})();"""

ASSET = _slim(JS.replace("__CSS__", _json.dumps(_expand(CSS))).replace("__FIND__", _json.dumps(FIND_SVG)))
V = _hashlib.sha256(ASSET.encode("utf-8")).hexdigest()[:10]
PATH = f"/{FOLDER}/alto-phone-min-{V}.js"


def phone_min_asset() -> tuple[str, str]:
    """(file name under /phone/, the script) for the site (palace_assets.ASSETS)."""
    return PATH.rsplit("/", 1)[1], ASSET


# Formats whose phone default is the corner tiles (Luke, 2026-11-01: "I want my old toggles back except for the formats we were
# explicitly trying to make the toggles not overwhelm the page like star chart"): the layouts below. Every other page keeps the
# v1.9.152 edge tabs. One entry here adds a format.
TILE_LAYOUTS = ("solar",)


def tiles_by_default(brief) -> bool:
    return getattr(brief, "layout", None) in TILE_LAYOUTS


def head_block(tiles: bool = False) -> str:
    """The <script> for <head> of every page. A phone fetches the layer when the page's default is the tiles (`tiles`: the System,
    every style) or when the address says ?pm=1; ?pm=0 turns it off on any page. A page that does not fetch it keeps the v1.9.152 tabs."""
    from .palace_assets import loader
    js = HEAD_JS.replace("__DEFAULT__", "true" if tiles else "false").replace("__LOAD__", loader(PATH, GUARD))
    return '<script id="alto-phone-min-head">' + js + "</script>"
