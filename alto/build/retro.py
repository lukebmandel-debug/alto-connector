"""Retro: the Star chart's Retro style (solar_stars.RETRO_CSS, Luke's Voyager poster and Foundation's Empire) as a style
of every format (Luke, 2026-10-22: "add retro style to timeline (vertical/horizontal), outline, and mind palace (world,
city, and building) in blueprint mode (not fpv)").

One look for the family: poster black with gold linework, the art-deco frame and its corners, spaced capitals, gold
accents, Alto's marks in gold. Each format keeps its own layout; only how it is drawn changes (Luke: "Everything but
same general structure that is unique to that format").

How it is carried. A page holds only the switch's hook (HEAD_JS, inside the background head script): the choice,
Classic or Retro, kept per timeline in the browser like the Star chart's styles (`alto-hl-{tid}-style`), and, when it
is Retro, a synchronous request for the hosted script (/retro/alto-retro-<hash>.js, palace_assets.ASSETS) that adds the
rules below and the frame. A Classic page never fetches it; a page whose file is missing (an exported copy) stays
Classic. The switch itself is drawn in the Background picker by the hosted /alto-bglib.js (backgrounds_import.py),
which the picker already loads, so the page carries no switch either. The System format keeps its own three styles
(solar_draw.py); the frame, the gold marks, the wordmark and the palette below are shared with them.

A format that is added later (the world-map palace) adopts Retro by adding its rules to FORMAT_CSS: html.alto-retro is
on <html>, the engine's dark tokens are in force (Retro wears the dark theme), and #sk-frame / #sk-mark are drawn for it.
"""
from __future__ import annotations

import hashlib as _hashlib
import json as _json
import re as _re

FOLDER = "retro"

# the palette and the lettering (the Star chart's Retro uses the same)
GOLD = "#d9ae55"
GOLD_HI = "#f0c15e"
CREAM = "#efe6cf"
NAVY = "#0a1b34"
FONT = '"Avenir Next","Futura","Century Gothic","Helvetica Neue",system-ui,sans-serif'

# ── shared with the Star chart (solar_stars.RETRO_CSS splices these in; `X ` is the style's own selector) ──
FRAME_CSS = r"""  /* the frame round the whole page (Luke, 2026-10-22: "for the two top corners, they should be above the Alto logo", "bottom
     corner caps … should actually be at the bottom corner"): its corners in the window's four corners, clear of the marks and controls */
  X #sk-frame{display:block;position:fixed;pointer-events:none;z-index:299;left:4px;right:4px;top:3px;bottom:calc(3px + env(safe-area-inset-bottom,0px));}
  X #title-bar:not(#_)>*{translate:0 8px;}   /* (the clef, the name and the wordmark a little lower, inside the corners) */
  X #sk-frame i{position:absolute;width:46px;height:46px;border:0 solid #d9ae55;opacity:.8;}
  X #sk-frame i:nth-child(1){left:0;top:0;border-width:1.5px 0 0 1.5px;} X #sk-frame i:nth-child(2){right:0;top:0;border-width:1.5px 1.5px 0 0;}
  X #sk-frame i:nth-child(3){left:0;bottom:0;border-width:0 0 1.5px 1.5px;} X #sk-frame i:nth-child(4){right:0;bottom:0;border-width:0 1.5px 1.5px 0;}
  X #sk-frame i::after{content:'';position:absolute;width:7px;height:7px;background:#d9ae55;transform:rotate(45deg);}
  X #sk-frame i:nth-child(1)::after{left:8px;top:8px;} X #sk-frame i:nth-child(2)::after{right:8px;top:8px;}
  X #sk-frame i:nth-child(3)::after{left:8px;bottom:8px;} X #sk-frame i:nth-child(4)::after{right:8px;bottom:8px;}
  X #sk-frame b{position:absolute;left:50%;top:31px;width:min(46vw,520px);height:1.5px;transform:translateX(-50%);
    background:linear-gradient(90deg,transparent,#d9ae55 18%,#d9ae55 46%,transparent 46% 54%,#d9ae55 54%,#d9ae55 82%,transparent);opacity:.7;}
  X #sk-frame b::after{content:'';position:absolute;left:50%;top:-5px;width:10px;height:10px;margin-left:-5px;border:1.5px solid #d9ae55;transform:rotate(45deg);}
"""
BRAND_CSS = r"""  /* Alto's own marks in Retro: the glyph and the wordmark in the Empire's gold (Retro only) */
  X svg:is(.brand-mark,.brand-word) [fill^="url"],X svg:is(.brand-mark,.brand-word) .alto-word{fill:#d9ae55 !important;}
  X svg:is(.brand-mark,.brand-word) [stroke^="url"],X svg.brand-mark .alto-head{stroke:#d9ae55 !important;}
  X svg:is(.brand-mark,.brand-word){filter:drop-shadow(0 0 6px rgba(217,174,85,.35));}
"""
WORDMARK_CSS = r"""  X #sk-mark{display:block;position:fixed;left:50%;transform:translateX(-50%);bottom:78px;z-index:300;pointer-events:none;color:#efe6cf;font-size:20px;font-weight:300;letter-spacing:.62em;opacity:.95;white-space:nowrap;}
  X #sk-mark::before,X #sk-mark::after{content:'';display:inline-block;width:64px;height:1.5px;margin:0 22px 6px;background:#d9ae55;vertical-align:middle;}
"""
FRAME_HTML = "<i></i><i></i><i></i><i></i><b></b>"

# ── the chrome round every Retro page, shared with the System's Retro (solar_stars.RETRO_CSS splices it in with scoped()): Retro is a
# dark look, so these are the dark tokens and the dark drawing of the bars, chips, controls, panels and detail pages whatever the theme
# toggle says (DARK_JS keeps html.dark on while Retro is), screen only (a page prints in the engine's own black on white) ──
CHROME_CSS = r"""
  X:not(#_){color-scheme:dark;--rt-g:#d9ae55;--rt-gh:#f0c15e;--rt-c:#efe6cf;--rt-ink:#b9b2a0;--rt-line:rgba(217,174,85,.5);--rt-f:FONT;
    --bg:#000;--surface:#05070b;--border:rgba(217,174,85,.32);--text:#efe6cf;--muted:#b9b2a0;--accent:#d9ae55;
    --card-glass-bg:#05070b;--card-desc-color:#b9b2a0;--panel-glass-bg:rgba(3,4,7,.97);--chip-glass-bg:#000;--chip-plate:#000;
    --nav-bg:rgba(0,0,0,.96);--nav-bar-bg:rgba(0,0,0,.96);--legend-bg:rgba(0,0,0,.94);--header-glass-bg:transparent;--page-glass-tint:transparent;
    --glass-slab-bg:none;--glass-slab-border:transparent;--glass-slab-shadow:none;--glass-sheen:transparent;}
  X body:has(#detail-page.visible) :is(#sk-mark,#sk-frame),X.detail-open :is(#sk-mark,#sk-frame){display:none !important;}
  X #mode-toggle{display:none !important;}
  /* the bars: the name in poster letters, the chips cut square and rimmed in gold */
  X #title-text:not(#_){color:#efe6cf !important;font-family:var(--rt-f) !important;font-weight:300 !important;text-transform:uppercase;letter-spacing:.5em;font-size:15px;}
  X :is(#title-text,.nav-group-label){box-shadow:none !important;background:transparent !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;}
  X #nav .nav-group-label:not(#_){color:#d9ae55 !important;font-family:var(--rt-f) !important;font-weight:400 !important;letter-spacing:.28em !important;
    background:#000 !important;box-shadow:0 0 0 3px #000 !important;text-shadow:none;}   /* the chip groups' names on a black pad: readable over whatever passes under them */
  X :is(#title-bar,#nav,#node-nav-bar):not(#_){background:transparent !important;box-shadow:none !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;border-color:transparent !important;}
  X.detail-open :is(#title-bar,#nav,#node-nav-bar):not(#_){background:#000 !important;border-bottom:1px solid rgba(217,174,85,.35) !important;}
  X :is(#title-bar,#nav,#node-nav-bar):not(#_)::before,X :is(#title-bar,#nav,#node-nav-bar):not(#_)::after{background:transparent !important;box-shadow:none !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;}
  X #nav .nav-btn:not(#_){background:#000 !important;color:#efe6cf !important;border:1px solid rgba(217,174,85,.55) !important;border-radius:0 !important;box-shadow:none !important;
    -webkit-backdrop-filter:none !important;backdrop-filter:none !important;font-family:var(--rt-f) !important;text-transform:uppercase;letter-spacing:.12em;font-size:10px !important;}
  X #nav .nav-btn:hover,X #nav .nav-btn.active{border-color:#d9ae55 !important;color:#d9ae55 !important;}
  X #nav .nav-btn :is(.nav-chip-count){color:#d9ae55 !important;background:transparent !important;}
  X #nav .nav-divider{background:rgba(217,174,85,.4) !important;}
  X #ct-chips{background:#000 !important;border-color:rgba(217,174,85,.6) !important;color:#d9ae55 !important;}
  /* the controls round the edges (rail, search, info, account, the format's own buttons): black, square, a gold rim */
  X :is(#tab-rail>button,#search-btn,#info-icon,#account-btn,#key-toggle,.alto-edit-pill,#timeline-return-pill,#sx-toggle):not(#_){background:#000 !important;color:#d9ae55 !important;
    border:0 !important;border-radius:0 !important;box-shadow:0 0 0 1px rgba(217,174,85,.55) !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;}
  X #tab-rail>button:not(#_){font-family:var(--rt-f) !important;letter-spacing:.18em;}
  X :is(#tab-rail>button,#search-btn,#info-icon,#account-btn,#key-toggle):hover{box-shadow:0 0 0 1px #d9ae55 !important;}
  X :is(#tab-rail>button.active,#tab-rail>button[aria-expanded=true]){background:#d9ae55 !important;color:#000 !important;}
  X #search-input{color:#efe6cf !important;font-family:var(--rt-f) !important;letter-spacing:.08em;}
  X #search-results,X #info-content,X #bg-panel,X #ef-panel,X #notes-panel,X #summary-wrap,X .key-pop,X #share-dialog>*{background:rgba(3,4,7,.97) !important;color:#efe6cf !important;
    border:1px solid rgba(217,174,85,.45) !important;border-radius:0 !important;box-shadow:0 0 0 4px #000 !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;}
  X :is(#bg-panel,#ef-panel,#notes-panel,#summary-wrap) :is(h1,h2,h3,.bg-t,.bg-h,.ef-h){color:#d9ae55 !important;font-family:var(--rt-f) !important;text-transform:uppercase;letter-spacing:.22em;font-weight:400 !important;}
  /* a detail page: the poster's black, gold rules and headings, cream text */
  X #detail-page:not(#_){background:#000 !important;color:#efe6cf !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;}
  X #detail-page :is(h1,.detail-name):not(#_){color:#efe6cf !important;font-family:var(--rt-f) !important;text-transform:uppercase;letter-spacing:.12em;font-weight:300 !important;}
  X #detail-page :is(h2,h3,h4,.detail-section-title,.section-title,.dp-h):not(#_){color:#d9ae55 !important;font-family:var(--rt-f) !important;text-transform:uppercase;letter-spacing:.26em;font-weight:400 !important;border-color:rgba(217,174,85,.4) !important;}
  X #detail-page :is(p,li,td,th,dd,dt,blockquote){color:#e3dccb;}
  X #detail-page .detail-role:not(#_){color:#d9ae55 !important;font-family:var(--rt-f) !important;letter-spacing:.3em;}
  X #detail-page .detail-header:not(#_){border-color:rgba(217,174,85,.45) !important;}
  X #detail-page a{color:#f0c15e !important;}
  X #detail-page :is(.detail-card,.detail-section,.dp-card,section,.card,.panel,blockquote,table):not(#_){background:#030407 !important;border-color:rgba(217,174,85,.35) !important;border-radius:0 !important;box-shadow:none !important;
    -webkit-backdrop-filter:none !important;backdrop-filter:none !important;}
  X #detail-page :is(button,.chip,.nav-btn,.node-nav-btn):not(#_){background:#000 !important;color:#d9ae55 !important;border:1px solid rgba(217,174,85,.55) !important;border-radius:0 !important;box-shadow:none !important;}
  X .node-nav-btn:not(#_){background:#000 !important;color:#d9ae55 !important;border:1px solid rgba(217,174,85,.55) !important;border-radius:0 !important;font-family:var(--rt-f) !important;letter-spacing:.14em;text-transform:uppercase;}
  X :is(#nav-prev-label,#nav-next-label,#nav-prev-label .wrap-pill,#nav-next-label .wrap-pill):not(#_){background:#000 !important;color:#efe6cf !important;border-radius:0 !important;box-shadow:none !important;
    font-family:var(--rt-f) !important;text-transform:uppercase;letter-spacing:.12em;font-size:11px !important;}
  X :is(#nav-prev-label,#nav-next-label) .wrap-pill:not(#_){box-shadow:0 0 0 1px rgba(217,174,85,.55) !important;}
  X #nav-label{color:#efe6cf !important;font-family:var(--rt-f) !important;letter-spacing:.3em;text-transform:uppercase;}
  X .alto-fmt-sym,X [class*="fmt-sym"],X .fmt-badge{color:#d9ae55 !important;opacity:1 !important;}   /* the format symbols keep showing, in gold */
  /* the name stands at the foot of a Retro page (the cartouche, #sk-mark), so the top keeps only the frame's crown, in the name's
     place between the clef and the wordmark (Luke, 2026-10-22: "put it where Torts -- System would be, then eliminate that in retro
     mode because we already have the title at the bottom of the page"); a detail page, a narrow window and the horizontal timeline have
     no cartouche: there the name stays and the crown goes back to the very top */
  @media (min-width:901px){ X:not(.detail-open):not(.mobile):not(.alto-lanes) #title-bar #title-text:not(#_){visibility:hidden !important;} }
  @media (max-width:900px){ X #sk-frame b:not(#_){top:0;} }
  /* the rest of a detail page (Luke, 2026-10-22: "detail pages are the worst"): its back button, the page's chips, the study blocks' buttons */
  X #desk-back:not(#_){background:#000 !important;color:#d9ae55 !important;border:0 !important;border-radius:0 !important;box-shadow:0 0 0 1px rgba(217,174,85,.55) !important;
    -webkit-backdrop-filter:none !important;backdrop-filter:none !important;}
  X #detail-page .char-chip:not(#_){background:#000 !important;color:#d9ae55 !important;border:1px solid rgba(217,174,85,.55) !important;border-radius:0 !important;box-shadow:none !important;}
  X #detail-page .ast-btn.pri:not(#_){background:#d9ae55 !important;color:#000 !important;}
  /* the controls drawn round in Classic, as deliberate squares in Retro (Luke, 2026-10-23: "things that were designed to be circular
     toggles but are square in retro, make them square properly"): the same box (so the same hit area), corners square on the control and
     on everything inside it (no round halo, knob or pill left within), a 1px gold rim, the glyph centred, gold when on; Classic stays round */
  X :is(#info-btn,#ct-chips,#m-search,.wrap-pill,#sol-tour):not(#_){border-radius:0 !important;}
  X #info-btn:not(#_){box-shadow:none !important;background:transparent !important;}
  X #ct-chips:not(#_){border:0 !important;box-shadow:0 0 0 1px rgba(217,174,85,.6) !important;}
  X :is(#notes-panel button:not(#fw-seg button),#ef-close,#bg-close,#msp-close,#minimap-close,#tutorial-close,.nt-btn):not(#_){border-radius:0 !important;background:#000 !important;color:#d9ae55 !important;
    border:0 !important;box-shadow:0 0 0 1px rgba(217,174,85,.55) !important;display:inline-flex;align-items:center;justify-content:center;}
  X :is(#notes-panel button:not(#fw-seg button),#ef-close,#bg-close,#msp-close,#minimap-close,#tutorial-close,.nt-btn):not(#_):hover{box-shadow:0 0 0 1px #d9ae55 !important;}
  X :is(#notes-panel button,.nt-btn):is(.active,[aria-pressed=true]):not(#fw-seg button):not(#_){background:#d9ae55 !important;color:#000 !important;}
  /* the panel's two tabs (Notes & highlights | Freewrite, freewrite.py): one square segmented bar, the chosen half in gold */
  X #fw-seg:not(#_){border-radius:0 !important;border-color:rgba(217,174,85,.55) !important;background:#000 !important;}
  X #fw-seg button:not(#_){border-radius:0 !important;background:transparent !important;color:#b9b2a0 !important;box-shadow:none !important;font-family:var(--rt-f) !important;text-transform:uppercase;letter-spacing:.12em;}
  X #fw-seg button[aria-selected="true"]:not(#_){background:#d9ae55 !important;color:#000 !important;}
  /* the filter's chips: square tabs, gold when on */
  X .ef-chip:not(#_){border-radius:0 !important;background:#000 !important;color:#efe6cf !important;border:1px solid rgba(217,174,85,.5) !important;box-shadow:none !important;
    font-family:var(--rt-f) !important;letter-spacing:.06em;}
  X .ef-chip:not(#_):hover{border-color:#d9ae55 !important;}
  X .ef-chip:is(.active,[aria-pressed=true]):not(#_){background:#d9ae55 !important;color:#000 !important;border-color:#d9ae55 !important;}
  X .ef-chip .ef-line:not(#_){border-radius:0 !important;}
  /* the highlight colours: square swatches; the chosen one framed in gold (not grown) */
  X .hl-color-swatch:not(#_){border-radius:0 !important;box-shadow:0 0 0 1px rgba(217,174,85,.35) !important;}
  X .hl-color-swatch.active:not(#_){transform:none !important;box-shadow:0 0 0 2px #000,0 0 0 3px #d9ae55 !important;}
  /* a phone's search: a square field with the gold rim, no soft shadow */
  X #m-search:not(#_){background:#000 !important;border:0 !important;box-shadow:0 0 0 1px rgba(217,174,85,.55) !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;}
  X .wrap-pill:not(#_){background:#000 !important;color:#efe6cf !important;box-shadow:0 0 0 1px rgba(217,174,85,.55) !important;font-family:var(--rt-f) !important;}
  /* the System's tour bar (Next / Back, solar_*.py): a square bar of square buttons, Next in gold */
  X #sol-tour:not(#_){background:#000 !important;border:0 !important;box-shadow:0 0 0 1px rgba(217,174,85,.55) !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;}
  X #sol-tour button:not(#_){border-radius:0 !important;font-family:var(--rt-f) !important;text-transform:uppercase;letter-spacing:.12em;}
  X #sol-tour .tb-next:not(#_){background:#d9ae55 !important;color:#000 !important;}
  X #sol-tour button:not(.tb-next):not(#_):hover{box-shadow:inset 0 0 0 1px rgba(217,174,85,.7) !important;color:#d9ae55 !important;}
  /* the cards' chips (doctrine / court glyphs) wherever they stand, the System's bodies included: square, a gold rim */
  X :is(.csym-btn,.esym-btn,.tsym-btn):not(#_){border-radius:0 !important;background:#000 !important;color:#d9ae55 !important;border:0 !important;box-shadow:inset 0 0 0 1px rgba(217,174,85,.55) !important;}
"""

# ── the board of an engine page (timeline, horizontal, outline, the palaces' map and plan): the hosted layer only ──
BOARD_CSS = r"""
  /* the poster's name on an engine page: a small cartouche in the bottom row, between its controls (the Star chart keeps its own place) */
  X:not(.alto-stars) #sk-mark{bottom:28px;font-size:12px;letter-spacing:.5em;padding:9px 4px 9px 16px;background:#000;font-family:var(--rt-f);text-transform:uppercase;}
  X:not(.alto-stars) #sk-mark::before,X:not(.alto-stars) #sk-mark::after{width:40px;margin:0 16px 4px;}
  X.alto-lanes #sk-mark{display:none !important;}
  X.alto-lanes #sk-frame b:not(#_){top:0;}   /* (the horizontal timeline has no cartouche: its name stays, the crown above it) */
  @media (max-width:900px){ X #sk-mark{display:none !important;} X #title-text:not(#_){letter-spacing:.22em;font-size:13px;} }   /* (a narrow window: the name fits, no cartouche) */
  X:is(.bldg-open,.wpal-open) #sk-frame i{display:none;}  X.wpal-open #sk-mark{display:none !important;}   /* (the World map's Tour bar has the bottom middle) */                  /* (the Museum's own panels sit in the corners: the frame keeps its crown) */           /* (the horizontal timeline's step bar has the middle of that row) */                 /* Retro is one look: the poster's night, in either theme */
  /* the page: flat black, no wallpaper, no picture, no glass slab */
  X body,X #app,X #canvas{background:#000 !important;}
  X #page-bg:not(#_){background:#000 !important;filter:none !important;} X #page-bg::before,X #page-bg::after{display:none !important;}
  X #glass-slab{background:none !important;box-shadow:none !important;border-color:transparent !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;}
  /* the units: no glass bars; a fine gold rule, the unit's name in spaced capitals, its numeral in thin gold */
  X:not(.alto-lanes) #world .phase-band:not(#_){background:none !important;border:0 !important;box-shadow:none !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;}
  X #world .phase-band::before,X #world .phase-band::after{display:none !important;}
  X #world :is(.unit-bar,.phase-label-float):not(#_){background:none !important;border:0 !important;box-shadow:none !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;}
  X #world .unit-bar::before{content:'';position:absolute;left:0;right:0;top:50%;height:1px;background:linear-gradient(90deg,rgba(217,174,85,.55),rgba(217,174,85,.15) 30%,rgba(217,174,85,.15) 70%,rgba(217,174,85,.55));}
  X #world :is(.phase-label,.phase-label-float .phase-label):not(#_){background:#000 !important;color:#d9ae55 !important;border:1px solid rgba(217,174,85,.7) !important;border-radius:0 !important;box-shadow:0 0 0 4px #000 !important;
    -webkit-backdrop-filter:none !important;backdrop-filter:none !important;font-family:var(--rt-f) !important;font-weight:400 !important;letter-spacing:.32em !important;text-transform:uppercase;}
  X #world .phase-label::before,X #world .phase-label::after{content:'\25C6';margin:0 .8em;font-size:.7em;vertical-align:.15em;color:#d9ae55;}
  X #world .phase-numeral:not(#_){background:#000 !important;color:#d9ae55 !important;border:1px solid rgba(217,174,85,.7) !important;border-radius:0 !important;box-shadow:0 0 0 4px #000 !important;
    -webkit-backdrop-filter:none !important;backdrop-filter:none !important;font-family:var(--rt-f) !important;font-family:"Didot","Bodoni 72","Bodoni MT",Georgia,serif !important;font-style:normal !important;font-weight:400 !important;letter-spacing:.06em;}
  X #world :is(.unit-dots,.ud-base,.ud-sheen){filter:sepia(1) saturate(2) hue-rotate(-8deg) brightness(.85);}
  /* the cards: a black plate, a fine gold rim, the unit's hue on its top edge, poster letters */
  X #world .node-card:not(#_){background:#05070b !important;border-radius:2px !important;box-shadow:none !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;filter:none !important;
    border-left-color:rgba(217,174,85,.4) !important;border-right-color:rgba(217,174,85,.4) !important;border-bottom-color:rgba(217,174,85,.4) !important;}
  X #world .node-card::before,X #world .node-card::after{display:none !important;}
  X #world .node:not(.dimmed):hover .node-card:not(#_){border-left-color:#d9ae55 !important;border-right-color:#d9ae55 !important;border-bottom-color:#d9ae55 !important;}
  X #world .node-tag:not(#_){color:#d9ae55 !important;font-family:var(--rt-f) !important;letter-spacing:.24em !important;font-weight:400 !important;}
  X #world .node-title:not(#_){color:#efe6cf !important;font-family:var(--rt-f) !important;text-transform:uppercase;letter-spacing:.07em;font-weight:500 !important;}
  X #world .node-desc:not(#_){color:#b9b2a0 !important;font-family:var(--rt-f) !important;}
  X #world .node-order:not(#_){color:#d9ae55 !important;font-family:var(--rt-f) !important;letter-spacing:.1em;}
  X #world .node-unit:not(#_){color:#d9ae55 !important;font-family:var(--rt-f) !important;letter-spacing:.22em;}
  X #world .node-footer :is(button,.chip,.csym-btn,.esym-btn,.tsym-btn,a):not(#_){background:#000 !important;color:#d9ae55 !important;border:0 !important;border-radius:0 !important;
    box-shadow:inset 0 0 0 1px rgba(217,174,85,.55) !important;font-family:var(--rt-f) !important;}
  X #world .footer-sep{background:rgba(217,174,85,.4) !important;}
  X #world .node.focused .node-card:not(#_){background:#0a1b34 !important;border-color:#d9ae55 !important;box-shadow:0 0 0 6px #000,0 0 0 7px rgba(217,174,85,.55) !important;}
  X .alto-fshadow{display:none !important;}
  /* the lines: gold linework; a line of a named kind keeps its own hue, drawn flat */
  X #river-svg path[data-edge]:not(#_){stroke-width:1.6px !important;stroke-opacity:.95 !important;filter:none !important;}
  X #river-svg path[data-edge]:is([stroke="rgb(60,64,84)"],[stroke="rgb(208,212,226)"]){stroke:#d9ae55 !important;}
  X #river-svg path[data-edge-part]{display:none;}
  X .line-tip{background:#000 !important;color:#d9ae55 !important;border:1px solid #d9ae55 !important;border-radius:0 !important;font-family:var(--rt-f) !important;letter-spacing:.06em;text-transform:uppercase;}
"""

# ── every engine page (timeline, horizontal, outline, the palaces' chrome and detail pages) ──
COMMON_CSS = r"""
  #sk-frame,#sk-mark{display:none;}
""" + CHROME_CSS + "  FRAME BRAND WORD\n" + BOARD_CSS

# ── each format's own drawing (its structure stays; only how it is drawn changes) ──
FORMAT_CSS = r"""
  /* the horizontal timeline (lanes.py): the story's line a gold beam, each character's line its own hue, flat and fine */
  X #lanes-svg .ln-main-halo{stroke:#d9ae55 !important;stroke-opacity:.12 !important;stroke-width:14 !important;}
  X #lanes-svg .ln-main{stroke:#d9ae55 !important;stroke-width:4 !important;}
  X #lanes-svg .ln-br{stroke-width:1.8 !important;opacity:1 !important;}
  X #lanes-svg .ln-ring,X #lanes-svg .ln-dot,X #lanes-svg .ln-merge{fill:#000 !important;stroke:#d9ae55 !important;}
  X #lanes-svg .ln-past-band{fill:#0a1b34 !important;fill-opacity:.55 !important;stroke:#d9ae55 !important;stroke-opacity:.6 !important;stroke-dasharray:6 6;}
  X #lanes-svg :is(.ln-tick,.ln-break){stroke:#d9ae55 !important;opacity:.45 !important;}
  X #lanes-svg .ln-rule{stroke:#d9ae55 !important;opacity:.18 !important;}
  X .lu-chip b{color:#d9ae55 !important;font-family:"Didot","Bodoni 72",Georgia,serif !important;}
  X #lanes-svg .ln-ticklbl{fill:#d9ae55 !important;font-family:var(--rt-f);letter-spacing:.12em;}
  X #lanes-svg .ln-stem{stroke:#d9ae55 !important;opacity:.4 !important;}
  X .lanes-when:not(#_){color:#d9ae55 !important;background:none !important;border:0 !important;box-shadow:none !important;font-family:var(--rt-f) !important;letter-spacing:.16em;}
  X #world .phase-band:not(#_){background:none !important;box-shadow:none !important;border-color:rgba(217,174,85,.16) !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;}
  X .lanes-unit:not(#_){background:none !important;box-shadow:none !important;border-color:rgba(217,174,85,.13) !important;}
  X :is(.lanes-tag,.ln-main-tag,.lanes-past,.lu-chip):not(#_){background:#000 !important;color:#d9ae55 !important;border:1px solid rgba(217,174,85,.6) !important;border-radius:0 !important;
    box-shadow:none !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;font-family:var(--rt-f) !important;text-transform:uppercase;letter-spacing:.16em;}
  X #lanes-nav:not(#_),X #lanes-nav *:not(svg *){background-color:transparent;}
  X #lanes-nav:not(#_){background:#000 !important;border:0 !important;border-radius:0 !important;box-shadow:0 0 0 1px rgba(217,174,85,.55) !important;color:#d9ae55 !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;}
  X #lanes-ov-sky{background:#000 !important;}
  X #lanes-nav .lnv-thumb:not(#_){border-radius:0 !important;background:#d9ae55 !important;box-shadow:0 0 0 2px #000 !important;}   /* (the step bar's thumb: a square, not a dot) */
  /* the outline (the tree): its lines are the engine's, drawn gold above */

  /* the city Mind Palace's map (palace.py), as a blueprint: the ground black, the streets fine gold, water deep navy,
     parks a dim green line, buildings outlined; the units keep their hue on the buildings that hold their cards */
  X:not(#_){--pal-river:#0e2a4d !important;--pal-rv-rim:rgba(217,174,85,.45) !important;--pal-casing:#000 !important;--pal-br-edge:rgba(217,174,85,.7) !important;--pal-br-pier:rgba(217,174,85,.45) !important;--pal-br-text:#d9ae55 !important;--pal-rv-lite:#163a66 !important;--pal-rv-sheen:rgba(217,174,85,.25) !important;--pal-glass:rgba(217,174,85,.05) !important;--pal-glass-edge:rgba(217,174,85,.45) !important;--pal-water:#0a1b34 !important;--pal-water-edge:rgba(217,174,85,.5) !important;--pal-park:rgba(217,174,85,.04) !important;--pal-pk:rgba(140,170,110,.10) !important;--pal-pk-edge:rgba(160,190,120,.5) !important;--pal-pk-path:rgba(217,174,85,.3) !important;--pal-pk-txt:#b9c79a !important;--pal-lm:rgba(217,174,85,.06) !important;--pal-text:#efe6cf !important;--pal-halo:#000 !important;--pal-trail:#9fb27a !important;--pal-ground:0,0,0 !important;}
  X.alto-palace :is(#page-bg,#canvas):not(#_){background:#000 !important;}
  X .pal-svg .pl-tube:not(.tr-m):not(.tr-r):not(.tr-t):not(.tr-bus):not(.hw):not(.r-line){stroke:#d9ae55 !important;stroke-opacity:.62;filter:none !important;}
  X .pal-svg .pl-tube.t-min{stroke-width:calc(var(--tw,1) * 1.4px) !important;stroke-opacity:.38 !important;}
  X .pal-svg .pl-tube.t-maj{stroke-width:calc(var(--tw,1) * 2.4px) !important;}
  X .pal-svg .pl-sheen{display:none;}
  X .pal-svg .pl-tube:is(.tr-m,.tr-r,.tr-t,.tr-bus,.hw,.r-line){filter:none !important;stroke-opacity:.85;}
  X .pal-svg :is(.pl-land,.pl-land-top){fill:#030407 !important;}
  X .pal-svg :is(.pl-land-bank,.pl-sea-bank){stroke:rgba(217,174,85,.12) !important;}
  X .pal-svg .pl-sea{fill:#0a1b34 !important;}
  X .pal-svg .pl-st:not(#_){fill:#d9ae55 !important;stroke:#000 !important;font-family:var(--rt-f);letter-spacing:.14em;text-transform:uppercase;font-weight:500 !important;}
  X .pal-svg :is(.pl-area,.pl-pkt,.pl-brn,.pl-river):not(#_){fill:#d9ae55 !important;stroke:#000 !important;font-family:var(--rt-f);font-weight:400 !important;letter-spacing:.3em;}
  X .pal-svg .pl-river:not(#_){fill:#7f9cc4 !important;}
  X .pal-svg :is(.lm-name,.pl-stt,.tr-lbl):not(#_){fill:#efe6cf !important;stroke:#000 !important;font-family:var(--rt-f) !important;letter-spacing:.1em;text-transform:uppercase;font-weight:500 !important;}
  X .pal-svg .pl-lmb .lm-card{fill:#000 !important;stroke:#d9ae55 !important;}
  X .pal-svg .pl-lmb .lm-shadow{fill:transparent !important;}
  X .pal-svg .tr-ring{fill:#000 !important;}
  /* the buildings as drawings: outlines in their hue on black, no glass (the 3D faces keep their shape) */
  X .pal-svg:not(#_){--lz-line:rgba(217,174,85,.55);--lz-win:rgba(217,174,85,.18);--lz-mu:rgba(217,174,85,.10);--lz-sl:#0b0d12;--lz-hi:rgba(217,174,85,.12);--lz-gs:transparent;
    --lz-seat-a:#1b2030;--lz-seat-b:#151a28;--lz-seat-d:#10141f;--lz-grass:#1d2a1a;--lz-grass2:#1a2617;--lz-dirt:#2a2418;--lz-endz:#1a2a20;--lz-base:#0b0d12;}
  X .pal-svg :is(.lz-f,.lz-sd,.lz-tp){stroke:rgba(217,174,85,.55) !important;}
  /* a card's building (nbDraw): dark glass in its unit's hue, its window lines faint */
  X .nb3d :is(.nb-f,.nb-s):not(#_){fill:color-mix(in srgb,var(--pc,#888) 15%,#000) !important;}
  X .nb3d .nb-r:not(#_){fill:color-mix(in srgb,var(--pc,#888) 30%,#000) !important;}
  X .nb3d .nb-l{stroke-opacity:.16 !important;}
  X .pal-svg :is(.lz-f,.lz-sd){fill:#06080c !important;} X .pal-svg .lz-tp{fill:#0d1016 !important;}
  X .pal-svg :is(.lz-gl,.lz-hi,.lm-sheen,.lm-strip){display:none !important;}
  X .nb3d .nb-sheen{display:none;}
  X .nb3d :is(.nb-f,.nb-s,.nb-r){stroke-width:1.4 !important;}
  X #pal-ctl :is(.pc-pill,button):not(#_),X #pal-tr :is(button,.pc-pill):not(#_){background:#000 !important;color:#d9ae55 !important;border:0 !important;border-radius:0 !important;
    box-shadow:0 0 0 1px rgba(217,174,85,.55) !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;font-family:var(--rt-f) !important;text-transform:uppercase;letter-spacing:.12em;}
  X #pal-ctl .pc-pill button:not(#_){box-shadow:none !important;}
  X #pal-ctl :is(button.on,button[aria-pressed=true]):not(#_){background:#d9ae55 !important;color:#000 !important;}
  X #pal-ctl .pc-div{background:rgba(217,174,85,.45) !important;}
  /* the controls' tips and the ride switch in the key (palace.py, palace_ride_*): square too; a card's number pin a square tab */
  X :is(#pal-ctl button,#alto-edit-pill .aep-half)::after{border-radius:0 !important;background:#000 !important;color:#d9ae55 !important;box-shadow:0 0 0 1px rgba(217,174,85,.6) !important;
    font-family:var(--rt-f) !important;text-transform:uppercase;letter-spacing:.1em;}
  X .pr-tk:not(#_){border-radius:0 !important;background:#000 !important;box-shadow:inset 0 0 0 1px rgba(217,174,85,.6) !important;}
  X .pr-tk i:not(#_){border-radius:0 !important;background:rgba(217,174,85,.55) !important;box-shadow:none !important;}
  X [aria-checked=true] > .pr-tk:not(#_){background:rgba(217,174,85,.22) !important;} X [aria-checked=true] > .pr-tk i:not(#_){background:#d9ae55 !important;}
  X.alto-palace #world .node-card::before{border-radius:0 !important;}

  /* the Museum / Building Palace's blueprint (palace_building_asset.py): an architect's plan in gold on black */
  X #bldg-root:not(#_){--bl-ink:#d9ae55;--bl-sheen:rgba(0,0,0,0);--bl-glass:rgba(217,174,85,.035);--bl-glass-edge:rgba(217,174,85,.38);--bl-paper:#000;--bl-text:#efe6cf;--bl-muted:#b9b2a0;
    --bl-line:rgba(217,174,85,.55);--bl-panel:#000;--bl-accent:#f0c15e;background:#000 !important;}
  X #bldg-root .bl-tube{stroke-width:2.2px;}
  X #bldg-root .bl-grid{stroke-opacity:.09;}
  X #bldg-root .bl-lab{font-family:var(--rt-f);letter-spacing:.12em;text-transform:uppercase;font-weight:500;}
  X #bldg-root .bl-pill rect{fill:#000 !important;stroke:var(--bl-tint,#d9ae55) !important;stroke-width:1.4px;rx:0;}
  X #bldg-root .bl-pill text{fill:#efe6cf !important;font-family:var(--rt-f);letter-spacing:.08em;font-weight:500;}
  X #bldg-root :is(.bl-tab,.bl-btn,.bl-head,.bl-info,.bl-credits,.bl-go):not(#_){background:#000 !important;color:#efe6cf !important;border-color:rgba(217,174,85,.55) !important;border-radius:0 !important;
    box-shadow:none !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;font-family:var(--rt-f) !important;}
  X #bldg-root :is(.bl-tab.on,.bl-go):not(#_){background:#d9ae55 !important;color:#000 !important;}
  X #bldg-root .bl-kind{color:#d9ae55 !important;letter-spacing:.28em !important;font-weight:400 !important;}
  X #bldg-root .bl-head h2{text-transform:uppercase;letter-spacing:.14em;font-weight:300 !important;}

  /* the World Palace's map (palace_world.py): a navigator's chart, gold on night blue, the units in the poster's inks */
  X #wpal-root:not(#_){--w-sea1:#0a1b34;--w-sea2:#05070b;--w-land:#0b0d12;--w-edge:rgba(217,174,85,.32);--w-grat:rgba(217,174,85,.07);--w-text:#efe6cf;--w-sub:#b9b2a0;
    --w-panel:#000;--w-panel-b:rgba(217,174,85,.55);--w-card:#000;--w-shadow:none;--w-font:var(--rt-f);--w-mix:#0b0d12;--w-used:22%;--w-pin:#05070b;
    background:radial-gradient(120% 90% at 50% 45%,#0a1b34 0%,#05070b 75%) !important;}
  X #wpal-root .wu0:not(#_){--u:#d9ae55;}
  X #wpal-root .wu1:not(#_){--u:#9fb27a;}
  X #wpal-root .wu2:not(#_){--u:#7f9cc4;}
  X #wpal-root .wu3:not(#_){--u:#e3dccb;}
  X #wpal-root .wu4:not(#_){--u:#c98a5a;}
  X #wpal-root .wu5:not(#_){--u:#b28ad1;}
  X #wpal-root .wu6:not(#_){--u:#f0c15e;}
  X #wpal-root .wu7:not(#_){--u:#b9c79a;}
  X #wpal-root .wu8:not(#_){--u:#a7bde0;}
  X #wpal-root .wu9:not(#_){--u:#d8b48a;}
  X #wpal-root .wu10:not(#_){--u:#cfa0d8;}
  X #wpal-root .wu11:not(#_){--u:#efe6cf;}
  X #wpal-root .wp-land{filter:none;}
  X #wpal-root .wp-c.wp-on{fill:color-mix(in srgb,var(--u) 34%,#0b0d12);}
  X #wpal-root :is(.wp-arc.h,.wp-arc.s){display:none;}
  X #wpal-root .wp-arc.m{stroke-width:1.6px;}
  X #wpal-root .wp-chev{stroke:#efe6cf;stroke-width:1.4px;}
  X #wpal-root .wp-pin:not(#_){box-shadow:none;border-width:1.4px;font-weight:400;font-family:var(--rt-f);color:var(--u);}
  X #wpal-root .wp-lbl{font-weight:400;text-transform:uppercase;letter-spacing:.16em;font-size:10.5px;text-shadow:0 0 4px #000,0 0 4px #000;}
  X #wpal-root .wp-lbl i{text-transform:none;letter-spacing:.04em;font-style:italic;}
  X #wpal-root :is(.wp-card,.wp-bar,.wp-list,.wp-tag):not(#_){border-radius:0;-webkit-backdrop-filter:none;backdrop-filter:none;box-shadow:none;}
  X #wpal-root .wp-tag:not(#_){border-width:1px;letter-spacing:.06em;}
  X #wpal-root .wp-card h4{font-weight:400;letter-spacing:.03em;}
  X #wpal-root .wp-card .n{font-weight:400;letter-spacing:.18em;}
  X #wpal-root .wp-btn:not(#_){border-radius:0;color:#d9ae55;border-color:rgba(217,174,85,.55);letter-spacing:.12em;text-transform:uppercase;font-size:11px;}
  X #wpal-root .wp-btn.r:not(#_){border-radius:0;}                       /* (round in Classic: a deliberate square here, 1.9.160) */
  X #wpal-root .wp-key i:not(#_){border-radius:0;}
  X #wpal-root .wp-tour .c{color:#f0c15e;font-weight:400;letter-spacing:.06em;}
"""

JS = r"""(function(){
if(window._altoRetro) return;
var r=document.documentElement, CSS=__CSS__, FRAME=__FRAME__, st=null;
function desk(){ return !r.classList.contains('mobile'); }
function plain(s){ return String(s||'').replace(/\s+/g,' ').trim(); }
// the frame and the wordmark are the Star chart's (#sk-frame, #sk-mark): drawn on a desktop page
function art(){
  if(!document.body) return;
  var on=r.classList.contains('alto-retro') && desk(), fr=document.getElementById('sk-frame'), m=document.getElementById('sk-mark');
  if(on && !fr){ fr=document.createElement('div'); fr.id='sk-frame'; fr.setAttribute('aria-hidden','true'); fr.innerHTML=FRAME; document.body.appendChild(fr); }
  else if(!on && fr) fr.remove();
  if(on){ if(!m){ m=document.createElement('div'); m.id='sk-mark'; m.setAttribute('aria-hidden','true'); document.body.appendChild(m); }
    var tt=document.getElementById('title-text'); m.textContent=plain(tt ? tt.textContent : document.title).split(/\s+[—–-]\s+/)[0]; }
  else if(m) m.remove();
}
__DARK__
function redraw(){ try{ if(typeof window.drawLines==='function') window.drawLines(); window.dispatchEvent(new Event('resize')); }catch(e){} }
function on(){
  if(!st){ st=document.createElement('style'); st.id='alto-retro-css'; st.textContent=CSS; }
  if(!st.parentNode) (document.head||r).appendChild(st);
  r.classList.add('alto-retro'); window._altoRetroDark(1); art(); redraw();
}
function off(){
  if(!r.classList.contains('alto-retro')) return;
  r.classList.remove('alto-retro'); window._altoRetroDark(0); art(); redraw();
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', art);
window.addEventListener('load', art);
window._altoRetro={on:on, off:off, art:art};
})();"""


# Retro wears the dark theme, in every format and the System's Star chart alike (Luke, 2026-10-22: "finding many things about dark
# mode do not work on retro"): on, html.dark goes on and stays on whatever the toggle does (the toggle is hidden: CHROME_CSS); off,
# the theme the reader had comes back (the engine stores a theme only when its toggle is used). One function, in the hosted layer
# and in the System's page (solar_draw.py).
DARK_JS = r"""window._altoRetroDark=window._altoRetroDark||function(on){
  var r=document.documentElement, o=window._altoRetroDark;
  if(on){ if(o.was==null) o.was=r.classList.contains('dark'); r.classList.add('dark');
    if(!o.mo && typeof MutationObserver==='function'){ o.mo=new MutationObserver(function(){ if(o.was!=null && !r.classList.contains('dark')) r.classList.add('dark'); });
      o.mo.observe(r,{attributes:true,attributeFilter:['class']}); } }
  else if(o.was!=null){ var w=o.was; o.was=null; if(!w) r.classList.remove('dark'); }
};"""


def scoped(css: str, sel: str) -> str:
    """Rules written with the `X` selector token (X , X., X:, X{) for the style class `sel`."""
    return (css.replace("FONT", FONT).replace("X ", sel + " ").replace("X.", sel + ".").replace("X{", sel + "{")
            .replace("X:", sel + ":"))


def _slim(src: str) -> str:
    src = _re.sub(r"/\*.*?\*/", "", src, flags=_re.S)
    return "\n".join(t for t in (ln.strip() for ln in src.split("\n")) if t and not t.startswith("//"))


def css() -> str:
    """Every format's Retro rules, as the hosted script adds them."""
    body = COMMON_CSS.replace("FRAME BRAND WORD", FRAME_CSS + BRAND_CSS + WORDMARK_CSS) + FORMAT_CSS
    return ("@media screen{\n" + _slim(scoped(body, "html.alto-retro")) + "\n}\n"     # (printing: the engine's black on white)
            "@media print{#sk-frame,#sk-mark{display:none !important;}}")


ASSET = _slim(JS.replace("__DARK__", DARK_JS).replace("__CSS__", _json.dumps(css())).replace("__FRAME__", _json.dumps(FRAME_HTML)))
V = _hashlib.sha256(ASSET.encode("utf-8")).hexdigest()[:10]
PATH = f"/{FOLDER}/alto-retro-{V}.js"
GUARD = "_altoRetro"


def retro_asset() -> tuple[str, str]:
    """(file name under /retro/, the script) for the site (palace_assets.ASSETS)."""
    return PATH.rsplit("/", 1)[1], ASSET
