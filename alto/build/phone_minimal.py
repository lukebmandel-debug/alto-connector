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
HEAD_JS = r"""(function(){var q=location.search;if(!(/Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent)||/[?&]mobile/.test(q))||/[?&]pm=0/.test(q))return;__LOAD__})();"""

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
/* a detail page's own FIND (the engine's tab on the left edge, a third of the way up: it sat on the first letters of the text, always; sim1111h) joins the other two:
   the bottom-left corner, 14 pt in, NOTES' mirror, and it fades with them while the page is read */
html.pmin.mobile.detail-open #search-toggle X{left:14px !important;bottom:calc(14px + env(safe-area-inset-bottom,0px)) !important;border-left:1px solid var(--border) !important;border-radius:6px !important;}
html.pmin.mobile.detail-open:is(.alto-retro,.alto-holo) #search-toggle X{border-radius:0 !important;}
html.pmin.mobile.detail-open #alto-back-prev X{max-width:calc(100vw - 140px) !important;}   /* (the pill between them: clear of FIND and of NOTES) */
/* the horizontal timeline's step bar: low between the corners */
/* (centred between the corner tiles, 70 px each side, and the island's insets; at most 360 px, so on its side it is a bar, not a 734 px rail) */
html.pmin.phone-whole #lanes-nav X{left:50% !important;right:auto !important;width:min(360px,calc(100vw - 140px - var(--sh-left,0px) - var(--sh-right,0px))) !important;max-width:none !important;transform:translateX(-50%) !important;box-sizing:border-box !important;bottom:calc(18px + env(safe-area-inset-bottom,0px)) !important;}
/* a Blueprint's or an Atlas's plan starts under the header (the tiles that sat there are gone) */
WH #bldg-root :is(.bl-head,.bl-tabs){top:62px !important;}
WH #bldg-root .bl-head{font-size:12px !important;padding:8px 12px !important;max-width:calc(100% - 96px) !important;}
/* the fade */
/* (sim1111h A2: the first tap after the fade was swallowed, 4 of 4. Safari's tap-to-click watches for content that a touch makes VISIBLE and, when clickable content
   appears, treats the touch as a hover and sends no click; to it "hidden" is display:none, visibility:hidden or opacity 0. The controls rest at .01, which no eye
   sees and Safari does not count as hidden, so waking them is not "content appearing" and the tap that wakes them also acts) */
html.pmin :is(C,#lanes-nav,#hl-mode-btn,#notes-toggle,#search-toggle,#pal-mmap .pm-close)X{transition:opacity .6s ease !important;}
html.pmin.pmin-idle :is(C,#lanes-nav,#hl-mode-btn,#notes-toggle,#search-toggle,#pal-mmap .pm-close)X{opacity:.01 !important;}
@media (prefers-reduced-motion:reduce){html.pmin :is(C,#lanes-nav,#hl-mode-btn,#notes-toggle,#search-toggle,#pal-mmap .pm-close)X{transition:none !important;}}
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


# ── a phone held on its side (Luke 2026-11-11, Art sheet 1111b option 5-C; audit rows C1, C3, W2, F5, H1) ──
# Safari's bars leave the page about 250 pt of 402; the portrait header (52 pt title row + 44 pt prev/next strip) and a card laid out like the portrait one used
# most of it. On a phone on its side: ONE 44 pt header row (clef, previous name, title, next name, wordmark, all kept) and the one-card view's card laid out as a
# two-page spread (unit, kind, title and the chips on the left, the text on the right at about 60 characters a line, scrolling inside its page), 16 pt clear of the
# safe edges and clear of the two corner controls. The row is the page's own glass at its own place, never a painted bar. Portrait is not touched.
LAND_MQ = "@media (orientation:landscape) and (max-height:480px)"
LAND = r"""
:root{--ls-l:max(var(--sh-left,0px),env(safe-area-inset-left,0px));--ls-r:max(var(--sh-right,0px),env(safe-area-inset-right,0px));--ls-cx:calc(var(--ls-l) + 66px);--ls-cy:calc(var(--ls-r) + 66px);}
/* the header row: one 44 pt row */
LH #nav@@{height:44px !important;min-height:0 !important;padding:0 !important;box-sizing:border-box !important;}
LH #nav .brand-mark@@{translate:none !important;left:calc(var(--ls-l) + 16px) !important;right:auto !important;top:50% !important;height:34px !important;}
LH #nav>svg:not(.brand-mark)@@{translate:none !important;right:calc(var(--ls-r) + 16px) !important;left:auto !important;top:50% !important;height:22px !important;}
LH #nav .title@@{position:absolute !important;left:calc(50% + (var(--ls-l) - var(--ls-r)) / 2) !important;top:50% !important;transform:translate(-50%,-50%) !important;flex:none !important;width:auto !important;
  max-width:24% !important;font-size:15px !important;line-height:1.2 !important;text-indent:0 !important;white-space:nowrap !important;overflow:hidden !important;text-overflow:ellipsis !important;margin:0 !important;padding:0 !important;}
LH #timeline-label-bar@@{top:0 !important;height:44px !important;left:0 !important;right:0 !important;padding:0 var(--ls-r) 0 var(--ls-l) !important;box-sizing:border-box !important;background:none !important;border:0 !important;
  box-shadow:none !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;pointer-events:none !important;z-index:106 !important;}
LH #timeline-label-bar :is(#tlb-prev,#tlb-next)@@{pointer-events:auto !important;min-width:0 !important;font-size:12px !important;}
LH #tlb-prev@@{padding:0 10px 0 62px !important;}
LH #tlb-next@@{padding:0 62px 0 10px !important;}
LH #tlb-divider@@{flex:0 0 26% !important;width:26% !important;background:none !important;height:100% !important;pointer-events:none !important;}
LH #timeline-label-bar .wrap-pill@@{max-width:100% !important;margin:0 !important;overflow:hidden !important;text-overflow:ellipsis !important;}
LH #summary-wrap@@{top:44px !important;}
LH #summary-wrap.open@@{max-height:calc(100vh - 44px) !important;height:calc(100vh - 44px) !important;}
/* the corner controls move in by the safe insets themselves (the shell's translate would add them twice) */
LC :is(#pmin-find,#hamburger-tab)@@{translate:none !important;}
LC #pmin-find@@{left:calc(var(--ls-l) + 14px) !important;}
LC #hamburger-tab@@{right:calc(var(--ls-r) + 14px) !important;}
/* the card: a spread, 16 pt clear of the safe edges and of the two corner controls, under the row */
LC.focus-mode:not(.detail-open) .node.mobile-featured@@{left:calc(50% + (var(--ls-l) - var(--ls-r)) / 2) !important;top:calc(52px + (100dvh - 64px) / 2) !important;}
LC.focus-mode .node.mobile-featured .node-card@@{box-sizing:border-box !important;width:calc(100vw - var(--ls-cx) - var(--ls-cy)) !important;height:calc(100dvh - 64px) !important;max-height:none !important;min-height:0 !important;
  overflow:hidden !important;padding:12px 18px 12px !important;display:grid !important;grid-template-columns:minmax(0,38%) minmax(0,1fr);grid-template-rows:minmax(34px,auto) auto minmax(0,1fr) auto;column-gap:22px;align-content:stretch;}
LC.focus-mode .node.mobile-featured .node-card>*@@{grid-column:1 / -1;min-width:0;}
LC.focus-mode .node.mobile-featured .node-card>.node-unit@@{grid-column:1 / -1;grid-row:1;position:static !important;margin:0 0 4px !important;padding:0 170px 0 0 !important;letter-spacing:.1em !important;line-height:1.4 !important;}
LC.focus-mode .node.mobile-featured .node-card>.node-tag@@{grid-column:1;grid-row:2;margin:0 0 4px !important;}
LC.focus-mode .node.mobile-featured .node-card>.node-title@@{grid-column:1;grid-row:3;align-self:start;margin:0 !important;font-size:20px !important;line-height:24px !important;max-height:100%;overflow-y:auto;}
LC.focus-mode .node.mobile-featured .node-card>.node-footer@@{grid-column:1;grid-row:4;align-self:end;margin:8px 0 0 !important;}
LC.focus-mode .node.mobile-featured .node-card>.node-desc@@{grid-column:2;grid-row:2 / 5;align-self:stretch;max-height:none !important;height:auto !important;min-height:0;overflow-y:auto !important;
  -webkit-overflow-scrolling:touch;padding:2px 0 0 !important;margin:0 !important;font-size:14px !important;line-height:1.55 !important;overscroll-behavior:contain;}
LC.focus-mode .node.mobile-featured .node-card>.node-order@@{position:absolute !important;top:12px !important;right:18px !important;left:auto !important;}
LC.focus-mode .node.mobile-featured .sp-tag@@{top:12px !important;right:124px !important;bottom:auto !important;}
/* a detail page on its side (sim1111h): the text keeps clear of the island (its symbol and first letters were under it), and the "Back to" pill, which lay on the
   first line of the summary on so short a screen, sits in the page's own empty top margin at the right */
/* (sim1112a R1: --dp-il / --dp-ir tell a style what the page's side padding gained, so a plate laid behind the text column (Holo on one of its own backgrounds) can run on to the page's
   edges under the island, as it does upright; inset, a 124 pt band of the bare scene rode between the two pages of a swipe) */
/* (sim1112b S4: scrolled, FIND lay on the first letter of a heading and MARK touched the end of a line. FIND, MARK and NOTES stand 14 pt inside the insets and are up to 45 pt
   wide: the text column runs between their two columns, 65 pt in from each inset, so nothing is ever under a tile wherever the page is scrolled to) */
LC.detail-open #detail-page@@{--dp-il:calc(var(--ls-l) + 47px);--dp-ir:calc(var(--ls-r) + 47px);padding-left:calc(var(--ls-l) + 65px) !important;padding-right:calc(var(--ls-r) + 65px) !important;}
/* (sim1112a: the names strip stood at the upright header's 52 pt under this 44 pt row: a pale 8 pt strip of bare ground between the two. It hangs from the row, and the page from it) */
LC.detail-open #node-nav-bar@@{top:44px !important;}
LC.detail-open #detail-page@@{top:86px !important;}
LC.detail-open #alto-back-prev@@{--bp-page:1;position:absolute !important;left:auto !important;right:calc(var(--ls-r) + 18px) !important;bottom:auto !important;top:6px !important;transform:none !important;max-width:42vw !important;padding:8px 14px !important;}
/* the focus button: in the card's top-right corner, between DONE and the number (it was above the card, on the strip) */
LC #af-btn@@{left:auto !important;top:calc(52px + 5px) !important;right:calc(var(--ls-cy) + 74px) !important;}
"""


def _expand(css: str) -> str:
    """CSS's shorthand: P a phone page, WH a page seen whole, C the two controls, X the specificity that outranks the phone design."""
    css = _slim(css)
    for a, b in (("WH ", WH + " "), ("P.", P + "."), ("P ", P + " "), ("P:", P + ":"), (":is(C", ":is(" + C), (" X", X), (")X", ")" + X)):
        css = css.replace(a, b)
    return css

def _land() -> str:
    """The landscape rules (LAND), inside one media query: LC the one-card view, @@ the specificity that outranks the phone design."""
    css = _slim(LAND).replace("LC", "html.pmin.mobile:not(.phone-whole)").replace("LH", "html.pmin:is(.mobile,.phone-whole)").replace("@@", X)
    return LAND_MQ + "{\n" + css + "\n}"


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

ASSET = _slim(JS.replace("__CSS__", _json.dumps(_expand(CSS) + "\n" + _land())).replace("__FIND__", _json.dumps(FIND_SVG)))
V = _hashlib.sha256(ASSET.encode("utf-8")).hexdigest()[:10]
PATH = f"/{FOLDER}/alto-phone-min-{V}.js"


def phone_min_asset() -> tuple[str, str]:
    """(file name under /phone/, the script) for the site (palace_assets.ASSETS)."""
    return PATH.rsplit("/", 1)[1], ASSET


def head_block() -> str:
    """The <script> for <head> of every page (a phone fetches the layer, nothing else does)."""
    from .palace_assets import loader
    return '<script id="alto-phone-min-head">' + HEAD_JS.replace("__LOAD__", loader(PATH, GUARD)) + "</script>"
