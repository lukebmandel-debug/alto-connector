"""Holographic: a third style of every format, after Classic and Retro (Luke, 2026-10-28, picking direction B of the Item 1 sheet:
"On holographic style, i like B, but make sure that text is not blending into the background too much.").

The look is the sheet's "Projector": one cyan light, square wireframe cards, a faint grid and scan lines, as if projected into the air.
It is square like Retro (the square-vs-round rule). On a computer it is dark only, like Retro (Luke, 2026-11-01: "Eliminate light mode on
holographic, just like retro"): the light/dark button is hidden and html.dark held on while the style is, and the reader's own theme comes back
with the style off. On a phone nothing changes (the button stays, html.dark picks the dark tokens and the light theme the light ones).

THE CONTRAST FLOOR. Every colour a rule uses for text or for the plate under it is one of the tokens below (TOKENS), and every pair
that can meet (PAIRS) is held to WCAG AA by tests/test_holo.py (4.5:1 for text, 3:1 for a line or an outline), light and dark. The
bars and the chip rows are solid (not see-through), so a card passing under them never shows through a label.

How it is built. The rules are Retro's own (retro.CHROME_CSS / BOARD_CSS / FORMAT_CSS / HOME_CSS: the same selectors for the bars, chips,
panels, detail pages, cards, lines, both palaces' maps, the Atlas and the homepage), re-inked: `ink()` swaps Retro's gold, black, cream and navy for the tokens,
drops the frame, the cartouche, the forced dark theme and the poster lettering, and HOLO_CSS adds what only Projector has (the grid, the
scan lines, the glow, the solid bars, the phone's square controls). A format department refines its own part by adding rules to
FORMAT_CSS below. Carried like Retro: a page holds only the switch (backgrounds.py head script, window._altoStyle, `holo`) and a hosted
script (/holo/alto-holo-<hash>.js, palace_assets.ASSETS) that adds the rules, fetched only by a page set to Holographic.
"""
from __future__ import annotations

import hashlib as _hashlib
import json as _json
import re as _re

from . import holo_backgrounds as _hb, retro as _rt

FOLDER = "holo"

# ── the tokens: (dark, light). tx text, mu quieter text, ac the cyan light (lines, accents, text on a plate), ac2 its brighter pair, bg the page, sf a
# card's plate, sf2 a deeper plate (water, a chosen card), on the text that stands on a filled cyan, rgb / bgrgb / sfrgb the same for alpha, glow the
# light's halo (Art's spec, ORG/notes-art-projector-spec.md: ac is the line, ac2 the ink of controls) ──
TOKENS = {
    "dark": {"tx": "#c9fffa", "mu": "#8fc9c6", "ac": "#4ff0e0", "ac2": "#8ffcf2", "bg": "#010a0e", "sf": "#021b21", "sf2": "#06323a", "on": "#00262b",
             "rgb": "79,240,224", "bgrgb": "1,10,14", "sfrgb": "2,27,33", "glow": "0 0 10px rgba(79,240,224,.45)"},
    "light": {"tx": "#06485c", "mu": "#335f6c", "ac": "#0a6f8c", "ac2": "#06607c", "bg": "#e9f7fa", "sf": "#fcfeff", "sf2": "#dcf1f6", "on": "#ffffff",
              "rgb": "10,111,140", "bgrgb": "233,247,250", "sfrgb": "252,254,255", "glow": "0 0 3px rgba(10,111,140,.1)"},
}
# the twelve unit hues of the Atlas (retro's .wu0-.wu11), chosen per theme so each reads on every plate
UNITS = {
    "dark": ["#22e0f0", "#9fe0a0", "#7fb4ff", "#e3f3ff", "#ffb482", "#d2a2ff", "#ffe27a", "#c6e68a", "#a7c8ff", "#f0c898", "#f0a8ff", "#ffffff"],
    "light": ["#00606f", "#2f5f12", "#1f4f9a", "#274453", "#8a3a00", "#6a2490", "#6a4d00", "#3f5f1a", "#24489a", "#6a4218", "#7a2a80", "#2a2a2a"],
}
# (foreground, background, minimum ratio): every pair the rules can put together
PAIRS = ([(f, b, 4.5) for f in ("tx", "mu", "ac", "ac2") for b in ("bg", "sf", "sf2")] + [("on", "ac", 4.5), ("on", "ac2", 4.5)])   # (Art: text 4.5; lines 3)
UNIT_PAIRS = [(i, b, 4.5) for i in range(12) for b in ("bg", "sf", "sf2")]


def _vars(t: dict, units: list) -> str:
    v = ";".join(f"--ho-{k}:{t[k]}" for k in t) + ";" + ";".join(f"--ho-u{i}:{c}" for i, c in enumerate(units))
    return v + (";--bg:var(--ho-bg);--surface:var(--ho-sf);--border:rgba(var(--ho-rgb),.42);--text:var(--ho-tx);--muted:var(--ho-mu);--accent:var(--ho-ac);"
                "--card-glass-bg:var(--ho-sf);--card-desc-color:var(--ho-mu);--panel-glass-bg:rgba(var(--ho-sfrgb),.98);--chip-glass-bg:var(--ho-bg);--chip-plate:var(--ho-bg);"
                "--nav-bg:rgba(var(--ho-bgrgb),.97);--nav-bar-bg:rgba(var(--ho-bgrgb),.97);--legend-bg:rgba(var(--ho-bgrgb),.97);--header-glass-bg:transparent;"
                "--page-glass-tint:transparent;--glass-slab-bg:none;--glass-slab-border:transparent;--glass-slab-shadow:none;--glass-sheen:transparent;--rt-f:inherit")


# ── what only Projector has ──
HOLO_CSS = r"""
  /* the plate of the page: the faint grid and the scan lines, under everything (the palaces and the Star chart draw their own ground) */
  X:not(.alto-palace):not(.alto-stars):not(.alto-bg-h) :is(body,#canvas):not(#_){background-color:var(--ho-bg) !important;
    background-image:repeating-linear-gradient(0deg,rgba(var(--ho-rgb),.045) 0 1px,transparent 1px 3px),linear-gradient(rgba(var(--ho-rgb),.07) 1px,transparent 1px),linear-gradient(90deg,rgba(var(--ho-rgb),.07) 1px,transparent 1px) !important;
    background-size:auto,48px 48px,48px 48px !important;}
  /* one of the style's own backgrounds chosen (holo_backgrounds.py): the background layer paints it again (Retro's rules, re-inked, hide it)
     and the plates under the board let it through */
  X.alto-bg-h #page-bg:not(#_):not(#__){background:var(--alto-top) !important;}
  X.alto-bg-h #page-bg:not(#_)::before{display:block !important;}
  X.alto-bg-h :is(body,#app,#canvas):not(#_):not(#__){background:transparent !important;}
  /* the bars: where a page keeps them (a detail page, a phone) they are solid, so a card or a line passing under a label never shows
     through it; a desktop timeline or the homepage has no top bars (clear_top.py, Luke 2026-10-21/22), so there each label carries its
     own solid square plate instead (the floor on text over anything) */
  X:not(.ct-on):not(.alto-home.alto-clear-top) :is(#title-bar,#nav,#node-nav-bar):not(#_):not(#__){--header-tint:transparent !important;background:rgba(var(--ho-bgrgb),.97) !important;}
  X:not(.ct-on):not(.alto-home.alto-clear-top) #title-bar:not(#_):not(#__){border-bottom:1px solid rgba(var(--ho-rgb),.5) !important;box-shadow:var(--ho-glow) !important;}
  X:is(.ct-on,.alto-home.alto-clear-top) :is(#title-text,.nav-group-label):not(#_):not(#__){background:var(--ho-bg) !important;box-shadow:0 0 0 6px var(--ho-bg) !important;border-radius:0 !important;}
  /* a group label's plate stays inside the gap between chips (the row's column gap is 5px): a 6px plate cut a corner off the chip on each side of ELEMENT (Luke, 2026-11-01) */
  X:is(.ct-on,.alto-home.alto-clear-top) #nav .nav-group-label:not(#_):not(#__){box-shadow:0 0 0 4px var(--ho-bg) !important;}
  /* Back stays on the clef's line: Retro lowers the clef, name and wordmark 8px and Back with them (retro.py), but this style leaves those three where Classic has them, so the carried 7.6px left Back lower than the name and wordmark and put its bottom edge on the header line (Luke, 2026-11-01) */
  X:not(.mobile) #desk-back:not(#_):not(#__){translate:none;}
  /* no unit-colour sheet, like Retro: clear_top.py's sheet reaching up past the window's top (#glass-slab's 1200px top border) is undone */
  X.alto-clear-top #glass-slab:not(#_):not(#__){margin-top:0 !important;border-top-width:0 !important;}
  X #title-text:not(#_){color:var(--ho-tx) !important;font-weight:500 !important;}
  /* the cards: a square wireframe plate lit from its edge */
  X #world .node-card:not(#_){border:1px solid rgba(var(--ho-rgb),.62) !important;border-radius:0 !important;
    box-shadow:var(--ho-glow),inset 0 0 18px rgba(var(--ho-rgb),.06) !important;}
  X #world .node:not(.dimmed):hover .node-card:not(#_){border-color:var(--ho-ac) !important;box-shadow:var(--ho-glow),var(--ho-glow),inset 0 0 18px rgba(var(--ho-rgb),.1) !important;}
  X #world .node.focused .node-card:not(#_){background:var(--ho-sf2) !important;border-color:var(--ho-ac) !important;box-shadow:0 0 0 2px var(--ho-bg),0 0 0 3px var(--ho-ac),var(--ho-glow) !important;}
  X #world .node-tag:not(#_){letter-spacing:.14em !important;}
  /* a System's suns, planets and moons stay round (Luke, 2026-10-30: "we don't want square planets"): only the cards above are square */
  X.alto-solar:not(.mobile) #world .node[data-solar] .node-card:not(#_):not(#__),X.alto-solar:not(.mobile) #world .node[data-solar] .node-card:not(#_):not(#__)::before{border-radius:50% !important;}
  /* no dimmed text (Art's rule 2): the small numerals and glyphs wear the controls' ink at full strength */
  X :is(.nav-chip-count,.node-order,.aep-pen,.node-unit):not(#_):not(#__){color:var(--ho-ac2) !important;opacity:1 !important;}
  X :is(#alto-edit-pill,#alto-edit-pill .aep-half):not(#_):not(#__){opacity:1 !important;}
  X #detail-page :is(.doc-row-tag,.hc-arrow,.detail-symbol):not(#_):not(#__){opacity:1 !important;}
  X #detail-page :is(.doc-thin,.doc-thin *):not(#_):not(#__){color:var(--ho-tx) !important;opacity:1 !important;}
  X #detail-page .detail-symbol:not(#_):not(#__){color:var(--ho-ac) !important;}
  /* the lines: one cyan light, glowing a little */
  X #river-svg path[data-edge]:is([stroke="rgb(60,64,84)"],[stroke="rgb(208,212,226)"]){stroke:var(--ho-ac) !important;filter:drop-shadow(var(--ho-glow)) !important;}
  /* the glass of the controls and panels is square and rimmed in the light, with a faint glow */
  X :is(#tab-rail>button,#search-btn,#info-icon,#account-btn,#key-toggle,.alto-edit-pill,#timeline-return-pill,#sx-toggle){box-shadow:0 0 0 1px var(--ho-ac),var(--ho-glow) !important;}
  X :is(#search-results,#info-content,#bg-panel,#ef-panel,#notes-panel,#summary-wrap,.key-pop,#share-dialog>*){box-shadow:0 0 0 4px var(--ho-bg),var(--ho-glow) !important;}
  X #search-input:not(#_){color:var(--ho-tx) !important;}
  X ::placeholder{color:var(--ho-mu);opacity:1;}
  X :focus-visible{outline:2px solid var(--ho-ac) !important;outline-offset:2px !important;}   /* (Art's rule 3: both themes) */
  /* the picker's style row (backgrounds_import.py): square, the chosen one filled */
  X #bg-panel .bg-seg{border-radius:0;border-color:rgba(var(--ho-rgb),.6);}
  X #bg-panel .bg-segb{text-transform:none;}
  X #bg-panel .bg-segb.on{background:var(--ho-ac);color:var(--ho-on);}
  /* the phone: its two corner controls and the MENU's squares, and the search sheet, square and in the light */
  html.pmin.alto-holo :is(#pmin-find,#hamburger-tab):not(#_):not(#__){border-radius:0 !important;}
  html.pmin.alto-holo #nav-drawer-body .drawer-btn:not(#_):not(#__){border-radius:0 !important;}
  html.pmin.alto-holo.msearch-open :is(#m-search,#m-search-results):not(#_):not(#__){background:var(--ho-bg) !important;}
  /* light/dark: a square chip with the same rim as its neighbours, not the engine's glowing circle (Art, alto-art-1029-0033, fix 1) */
  X #mode-toggle:not(#_):not(#__){background:var(--ho-bg) !important;color:var(--ho-ac) !important;border:0 !important;border-radius:0 !important;
    box-shadow:0 0 0 1px var(--ho-ac),var(--ho-glow) !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;}
  /* dark only on a computer (Luke, 2026-11-01): no light/dark button; a phone keeps its own (JS: hdark) */
  @media (min-width:641px){ X:not(.mobile) #mode-toggle:not(#_):not(#__){display:none !important;} }
  /* the Alto marks (Luke, 2026-11-01: "the alto logo and glyph in holographic style ... the glyph should rotate like the glyphs for file type"):
     the clef and the wordmark in the light, on every page that has them, a phone's too; the clef turns on Y on the homepage's motion budget, the phone timeline's clef in #nav too (CEO 2026-11-05)
     (transform only, 10 s, still under reduced motion and while the tab is hidden) */
  X svg:is(.brand-mark,.brand-word) [fill^="url"],X svg:is(.brand-mark,.brand-word) .alto-word{fill:var(--ho-ac2) !important;}
  X svg:is(.brand-mark,.brand-word) [stroke^="url"],X svg.brand-mark .alto-head{stroke:var(--ho-ac2) !important;}
  X #title-bar svg.brand-word:not(#_):not(#__){filter:drop-shadow(0 0 5px rgba(var(--ho-rgb),.5)) !important;}
  X #title-bar svg.brand-mark:not(#_):not(#__),X.pmin #nav svg.brand-mark:not(#_):not(#__){filter:drop-shadow(-1.5px 0 0 rgba(255,95,210,.5)) drop-shadow(0 0 5px rgba(var(--ho-rgb),.5)) !important;
    animation:ho-logo 10s linear infinite;will-change:transform;}
  X.hp-hid #title-bar svg.brand-mark,X.hp-hid.pmin #nav svg.brand-mark{animation-play-state:paused;}
  @keyframes ho-logo{from{transform:perspective(260px) rotateY(0)}to{transform:perspective(260px) rotateY(360deg)}}
  /* the phone's clef is centred by translateY(-50%) (html.mobile #nav .brand-mark), and an animated or reduced-motion transform replaces it: carry it */
  @keyframes ho-logo-p{from{transform:translateY(-50%) perspective(260px) rotateY(0)}to{transform:translateY(-50%) perspective(260px) rotateY(360deg)}}
  X.pmin #nav svg.brand-mark:not(#_):not(#__){animation-name:ho-logo-p;}
  @media (prefers-reduced-motion:reduce){ X #title-bar svg.brand-mark:not(#_):not(#__),X.pmin #nav svg.brand-mark:not(#_):not(#__){animation:none !important;transform:perspective(260px) rotateY(24deg);will-change:auto;}
    X.pmin #nav svg.brand-mark:not(#_):not(#__){transform:translateY(-50%) perspective(260px) rotateY(24deg);} }
  /* the toggles (Luke, 2026-11-01: "toggles feel a little bit heavy and not holographic enough"; Art's sheet, accepted): one 1px soft-cyan edge, square, the
     same on every one of them (the bottom-left and bottom-right controls, the edit pair, the right-edge tabs); at rest the plate is the page's own colour (so
     nothing under it shows through a glyph), no glow; hover and focus brighten the edge, the chosen one takes a faint tint. A computer only: a phone keeps its own */
  @media (min-width:641px){
   X:not(.mobile):not(.pmin){--ho-edge:#2fa79d;}
   X:not(.mobile):not(.pmin) :is(#tab-rail>button,#search-btn,#info-btn,#account-btn,#key-toggle,.alto-edit-pill,#timeline-return-pill,#sx-toggle):not(#_):not(#__){
     box-shadow:0 0 0 1px var(--ho-edge) !important;border:0 !important;background:var(--ho-bg) !important;color:var(--ho-ac2) !important;filter:none !important;}
   X:not(.mobile):not(.pmin) :is(#tab-rail>button,#search-btn,#info-btn,#account-btn,#key-toggle,.alto-edit-pill,#timeline-return-pill,#sx-toggle):is(:hover,:focus-visible,:focus-within):not(#_):not(#__){
     box-shadow:0 0 0 1px var(--ho-ac) !important;}
   X:not(.mobile):not(.pmin) :is(#tab-rail>button,#search-btn,#info-btn,#account-btn,#key-toggle,#sx-toggle):is(.on,.active,.open,[aria-pressed="true"],[aria-expanded="true"]):not(#_):not(#__){
     background:rgba(var(--ho-rgb),.16) !important;box-shadow:0 0 0 1px var(--ho-ac) !important;}
   X:not(.mobile):not(.pmin) .alto-edit-pill .aep-half:not(#_):not(#__){box-shadow:none !important;}
   X:not(.mobile):not(.pmin) .alto-edit-pill .aep-half + .aep-half:not(#_):not(#__){box-shadow:inset 1px 0 0 rgba(47,167,157,.45) !important;}
  }
  /* focus on a branch (focus_branch.py): square, the Exit pill's ink dark on the cyan fill, its keys at full strength; the rules live here, not in the page */
  X :is(#af-btn,#af-exit){border-radius:0;}
  X #af-exit{color:var(--ho-bg) !important;}
  X #af-exit :is(.af-who,.af-esc){opacity:1;}
  /* the palace has no nav items: its empty band is not painted, so the Tour / World / zoom row clears it (Art fix 2) */
  X.wpal-open #nav:not(#_):not(#__){background:transparent !important;border:0 !important;box-shadow:none !important;}
  @media print{ X :is(#title-bar,#nav,#node-nav-bar){box-shadow:none !important;} }
"""

# ── the homepage's Projector (Art, SPEC-holo-home-A, Luke 2026-11-01 "I like A"): the medallion's flat symbol becomes three layers turning on Y over a
# pulsing base ring, a light cone and one scan line per tile. transform and opacity only; desktop only (the script adds it on a computer's page) ──
PROJ_CSS = r"""
  X{--hp-mg:#ff5fd2;--hp-cone:.28;}
  X:not(.dark){--hp-mg:#b3249a;--hp-cone:.14;}
  X.alto-home .course-tile .tile-emblem.hp-on{pointer-events:auto !important;cursor:default;}
  X.alto-home .course-tile .tile-emblem.hp-on > svg{display:none !important;}
  X.alto-home .course-tile .tile-emblem.hp-on:focus-visible{outline:2px solid var(--ho-ac2);outline-offset:-3px;}
  X.alto-home .course-tile.hp:hover,X.alto-home .course-tile.hp:focus-within{z-index:4;}
  X .hp-stage{position:relative;width:84px;height:104px;perspective:420px;}
  X .hp-spin{position:absolute;inset:12px 14px 34px;transform-style:preserve-3d;animation:ho-spin 10s linear infinite;animation-delay:calc(var(--hp-i,0) * -.7s);}
  X.alto-home .course-tile .hp-stage .hp-l{position:absolute;inset:0;display:block;width:100%;height:100%;fill:none;stroke-width:1.4;stroke-linecap:round;stroke-linejoin:round;overflow:visible;}
  X .hp-stage .hp-l1{stroke:var(--hp-mg);color:var(--hp-mg);opacity:.55;transform:translateZ(-5px);}
  X .hp-stage .hp-l2{stroke:var(--ho-ac);color:var(--ho-ac);transform:translateZ(0);}
  X .hp-stage .hp-l3{stroke:var(--ho-ac);color:var(--ho-ac);opacity:.45;transform:translateZ(5px);}
  X .hp-beam{position:absolute;left:50%;bottom:22px;width:62px;height:58px;transform:translateX(-50%);background:linear-gradient(to top,rgba(var(--ho-rgb),var(--hp-cone)),transparent);clip-path:polygon(24% 0,76% 0,100% 100%,0 100%);}
  X .hp-base{position:absolute;left:50%;bottom:12px;width:64px;height:14px;transform:translateX(-50%);}
  X .hp-base i{position:absolute;inset:0;border:1px solid var(--ho-ac);border-radius:50%;}
  X .hp-base i + i{border-color:var(--hp-mg);animation:ho-pulse 3.2s ease-out infinite;animation-delay:calc(var(--hp-i,0) * -.7s);}
  X .hp-scan{position:absolute;inset:0;overflow:hidden;pointer-events:none;z-index:1;}
  X .hp-scan i{position:absolute;left:0;right:0;top:0;height:100%;background:linear-gradient(var(--ho-ac),var(--ho-ac)) top/100% 1px no-repeat;opacity:.16;animation:ho-scan 7s linear infinite;animation-delay:calc(var(--hp-i,0) * -.7s);}
  X .hp-tip{position:absolute;left:50%;top:-6px;transform:translate(-50%,-100%);z-index:9;padding:5px 8px;white-space:nowrap;pointer-events:none;opacity:0;transition:opacity .15s;
    background:var(--ho-bg);color:var(--ho-tx);border:1px solid var(--ho-ac);font:12px/1 "SF Mono",ui-monospace,Menlo,monospace;letter-spacing:.1em;text-transform:uppercase;}
  X .hp-on:hover .hp-tip,X .hp-on:focus-visible .hp-tip{opacity:1;}
  X .course-tile.hp-still .hp-spin{animation:none;transform:rotateY(28deg);}
  X .course-tile.hp-still :is(.hp-base i + i,.hp-scan){display:none;}
  X .course-tile.hp-off :is(.hp-spin,.hp-base i + i,.hp-scan i){animation-play-state:paused;}
  X.hp-hid .course-tile :is(.hp-spin,.hp-base i + i,.hp-scan i){animation-play-state:paused;}
  @keyframes ho-spin{from{transform:rotateY(0)}to{transform:rotateY(360deg)}}
  @keyframes ho-pulse{from{transform:scale(.55);opacity:.9}to{transform:scale(1.25);opacity:0}}
  @keyframes ho-scan{from{transform:translateY(0)}to{transform:translateY(100%)}}
  @media (prefers-reduced-motion:reduce){
   X .hp-spin{animation:none !important;transform:rotateY(28deg);}
   X .hp-base i + i,X .hp-scan{display:none !important;}
   X .hp-base i:first-child{opacity:.6;}
   X .hp-tip{transition:none;}
  }
"""

# ── each format's own refinement lives here: its department adds rules (Retro's FORMAT_CSS, re-inked, is the base) ──
FORMAT_CSS = r"""
"""

_UNIT_CSS = "".join(f"  X #wpal-root .wu{i}:not(#_){{--u:var(--ho-u{i});}}\n" for i in range(12))


def _chunks(css: str) -> list[str]:
    """Rules of an already comment-free sheet: a new one begins at each line indented by exactly two spaces."""
    out: list[str] = []
    for ln in css.split("\n"):
        if _re.match(r"^  \S", ln) or not out:
            out.append(ln)
        else:
            out[-1] += "\n" + ln
    return out


_DROP = ("#sk-", "visibility:hidden", "#mode-toggle", "--rt-g:", "#wpal-root .wu")


def ink(css: str) -> str:
    """Retro's rules, re-inked in the tokens: no frame, cartouche, forced dark theme or poster lettering; gold, black, cream and navy are
    the tokens (the plate under a gold fill carries the `on` text)."""
    css = _re.sub(r"/\*.*?\*/", "", css, flags=_re.S)
    css = "\n".join(c for c in _chunks(css) if not any(d in c for d in _DROP))
    css = _re.sub(r"(background:#d9ae55(?: !important)?;\s*color:)#000", r"\1var(--ho-on)", css)
    css = _re.sub(r"(background:#f0c15e(?: !important)?;\s*color:)#000", r"\1var(--ho-on)", css)
    css = css.replace("rgba(217,174,85,", "rgba(var(--ho-rgb),").replace("rgba(3,4,7,", "rgba(var(--ho-sfrgb),").replace("rgba(0,0,0,", "rgba(var(--ho-bgrgb),")
    for a, b in (("#f0c15e", "var(--ho-ac2)"), ("#d9ae55", "var(--ho-ac)"), ("#efe6cf", "var(--ho-tx)"), ("#b9b2a0", "var(--ho-mu)"), ("#7f9cc4", "var(--ho-mu)"),
                 ("#0a1b34", "var(--ho-sf2)"), ("#e3dccb", "var(--ho-tx)")):
        css = css.replace(a, b)
    css = _re.sub(r"#(?:030407|05070a|05070b|06080c|070a0f|090c11|0b0d12|0d1016)(?![0-9a-fA-F])", "var(--ho-sf)", css)
    css = _re.sub(r"#000(?![0-9a-fA-F])", "var(--ho-bg)", css)
    css = css.replace("sepia(1) saturate(2) hue-rotate(-8deg) brightness(.85)", "grayscale(1) sepia(1) hue-rotate(125deg) saturate(3)")
    css = _re.sub(r"font-family:[^;}]*(;|(?=}))", "", css)
    css = _re.sub(r"letter-spacing:(\.\d+)em", lambda m: "letter-spacing:" + ("%.2f" % min(float(m.group(1)), .12)).lstrip("0") + "em", css)
    return css


def css() -> str:
    """Every format's Holographic rules, as the hosted script adds them."""
    base = ink(_rt.CHROME_CSS + _rt.BOARD_CSS + _rt.FORMAT_CSS + _rt.HOME_CSS)   # (HOME_CSS: the homepage, home_look.py)
    body = base + "\n" + HOLO_CSS + PROJ_CSS + FORMAT_CSS + _UNIT_CSS
    sel = "html.alto-holo"
    toks = (f"  {sel}:not(#_){{color-scheme:light;{_vars(TOKENS['light'], UNITS['light'])}}}\n"
            f"  {sel}.dark:not(#_){{color-scheme:dark;{_vars(TOKENS['dark'], UNITS['dark'])}}}\n")
    return "@media screen{\n" + _rt._slim(toks + _rt.scoped(body, sel)) + "\n}"


JS = r"""(function(){
if(window._altoHolo) return;
var r=document.documentElement, CSS=__CSS__, BGS=__BGS__, st=null;
HOMEB
// the homepage's Projector (PROJ_CSS): each plate's flat symbol is kept (hidden) and three clones turn in its place. A computer's page only: a phone's tiles stay as they are.
var PN={timeline:'Timeline',lanes:'Timeline · Horizontal',outline:'Outline',system:'System',palace:'Memory Map',building:'Memory Blueprint',world:'Memory Atlas'}, MAXT=40, pmo=null, praf=0, pio=null, rz=0;
function pel(c,t){ var e=document.createElement(t||'div'); if(c) e.className=c; return e; }
function desk(){ return !r.classList.contains('mobile') && window.innerWidth>640; }   // (the home page's phone layout is the media query's, 640 and under)
function plive(){ return r.classList.contains('alto-holo') && r.classList.contains('alto-home') && desk(); }
function pun(t){
  var em=t.querySelector('.tile-emblem');
  [].slice.call(t.querySelectorAll('.hp-scan')).forEach(function(n){ n.remove(); });
  if(em){ [].slice.call(em.querySelectorAll('.hp-stage,.hp-tip')).forEach(function(n){ n.remove(); });
    if(em.classList.contains('hp-on')){ em.classList.remove('hp-on'); ['role','aria-label','tabindex'].forEach(function(a){ em.removeAttribute(a); }); em.setAttribute('aria-hidden','true'); if(!em.getAttribute('class')) em.removeAttribute('class'); } }
  t.classList.remove('hp','hp-still','hp-off'); t.style.removeProperty('--hp-i'); if(!t.getAttribute('style')) t.removeAttribute('style'); if(!t.getAttribute('class')) t.removeAttribute('class');
}
function proj(){
  if(!plive()) return;
  [].forEach.call(document.querySelectorAll('.course-tile:not(.new-tile)'), function(t,i){
    var em=t.querySelector('.tile-emblem'), name=PN[t.getAttribute('data-fmt')];
    if(!em||!name||!t.querySelector('.t-main')) return;
    var still=i>=MAXT;
    if(em.classList.contains('hp-on')){ t.classList.toggle('hp-still',still); return; }
    var svg=null; for(var c=em.firstChild;c;c=c.nextSibling){ if(c.nodeName.toLowerCase()==='svg'){ svg=c; break; } }
    if(!svg) return;
    var stage=pel('hp-stage'), spin=pel('hp-spin'), base=pel('hp-base'), scan=pel('hp-scan'), tip=pel('hp-tip'); stage.setAttribute('aria-hidden','true'); scan.setAttribute('aria-hidden','true');
    ['hp-l1','hp-l2','hp-l3'].forEach(function(k){ var s=svg.cloneNode(true); s.setAttribute('class','hp-l '+k); s.setAttribute('aria-hidden','true'); spin.appendChild(s); });
    base.appendChild(pel('','i')); base.appendChild(pel('','i')); scan.appendChild(pel('','i'));
    stage.appendChild(pel('hp-beam')); stage.appendChild(spin); stage.appendChild(base);
    tip.textContent=name; tip.setAttribute('aria-hidden','true');
    em.insertBefore(stage, em.firstChild); em.appendChild(tip);
    em.classList.add('hp-on'); em.setAttribute('role','img'); em.setAttribute('aria-label',name); em.setAttribute('tabindex','0'); em.setAttribute('aria-hidden','false');
    t.appendChild(scan); t.classList.add('hp'); t.classList.toggle('hp-still',still); t.style.setProperty('--hp-i', i);
    if(pio) pio.observe(t);
  });
}
function pwatch(){
  if(!pio && typeof IntersectionObserver==='function'){
    pio=new IntersectionObserver(function(es){ es.forEach(function(e){ e.target.classList.toggle('hp-off', !e.isIntersecting); }); }, {rootMargin:'80px'});
    [].forEach.call(document.querySelectorAll('.course-tile.hp'), function(t){ pio.observe(t); });
  }
  if(!pmo && typeof MutationObserver==='function'){
    pmo=new MutationObserver(function(){ if(praf) return; praf=requestAnimationFrame(function(){ praf=0; proj(); }); });
    pmo.observe(r,{childList:true,subtree:true});
  }
}
function punwatch(){ if(pmo){ pmo.disconnect(); pmo=null; } if(pio){ pio.disconnect(); pio=null; } }
// dark only on a computer (a phone keeps its light/dark button): html.dark is held on while the style is, the reader's own theme comes back with it off
var hd={was:null,mo:null};
function hdark(on){
  if(on){ if(hd.was==null) hd.was=r.classList.contains('dark'); r.classList.add('dark');
    if(!hd.mo && typeof MutationObserver==='function'){ hd.mo=new MutationObserver(function(){ if(hd.was!=null && !r.classList.contains('dark')) r.classList.add('dark'); }); hd.mo.observe(r,{attributes:true,attributeFilter:['class']}); } }
  else if(hd.was!=null){ var w=hd.was; hd.was=null; if(!w && !r.classList.contains('alto-retro')) r.classList.remove('dark'); }
  if(window._altoAlignInfo) setTimeout(window._altoAlignInfo, 0);
}
function hsync(){
  if(!r.classList.contains('alto-holo')) return;
  hdark(desk());
  var H=window._altoRetroHome;
  if(plive()){ if(H) H.on(); pwatch(); proj(); }
  else { punwatch(); [].forEach.call(document.querySelectorAll('.course-tile'), pun); if(H && !r.classList.contains('alto-retro')) H.off(); }
}
function hoff(){
  hdark(0); punwatch(); [].forEach.call(document.querySelectorAll('.course-tile'), pun); r.classList.remove('hp-hid');
  if(window._altoRetroHome && !r.classList.contains('alto-retro')) window._altoRetroHome.off();
}
document.addEventListener('visibilitychange', function(){ if(r.classList.contains('alto-holo')) r.classList.toggle('hp-hid', document.hidden); });
window.addEventListener('resize', function(){ if(rz) return; rz=setTimeout(function(){ rz=0; hsync(); }, 150); });
function redraw(){ try{ if(typeof window.drawLines==='function') window.drawLines(); if(typeof window.redrawConnections==='function') window.redrawConnections(); window.dispatchEvent(new Event('resize')); }catch(e){} }   // (the lines break at a divider by the style: vSegWithGaps)
// the style's own backgrounds (holo_backgrounds.py): in the picker's catalog only while Holographic is on; a page set to one of them
// paints it when the style comes on and goes back to no background when it goes off (the choice itself is kept)
function sec(){ var U=(window._altoBg||{}).ui; if(!U||!U.body) return null; return [].filter.call(U.body.querySelectorAll('.bg-sec'), function(s){ var h=s.querySelector('.bg-h'); return h && h.textContent==='Holographic'; })[0]||null; }
function bgs(on){
  var B=window._altoBg; if(!B||!B.C) return; var cur=B.read();
  Object.keys(BGS).forEach(function(id){ if(on) B.C[id]=BGS[id]; else delete B.C[id]; });
  if(cur in BGS) B.apply(cur);
  var U=B.ui, s=sec();
  if(!on){ if(s) s.parentNode.removeChild(s); return; }
  if(!U||!U.body||s) return;
  s=U.mk('div','bg-sec'); s.appendChild(U.mk('div','bg-h','Holographic')); var g=U.mk('div','bg-grid');
  Object.keys(BGS).forEach(function(id){ g.appendChild(U.tile(id, BGS[id])); }); s.appendChild(g);
  var at=document.getElementById('bg-yours'); if(!at){ var all=U.body.querySelectorAll('.bg-sec'); at=all[all.length>1 ? 2 : 0]||null; }
  U.body.insertBefore(s, at); if(U.mark) U.mark();
}
function on(){
  if(!st){ st=document.createElement('style'); st.id='alto-holo-css'; st.textContent=CSS; }
  if(!st.parentNode) (document.head||r).appendChild(st);
  r.classList.add('alto-holo'); bgs(true); redraw(); hsync();
}
function off(){ if(!r.classList.contains('alto-holo')) return; r.classList.remove('alto-holo'); hoff(); bgs(false); redraw(); }
window._altoHolo={on:on, off:off};
})();"""

ASSET = _rt._slim(JS.replace("HOMEB", _rt.HOME_B_JS).replace("__CSS__", _json.dumps(css())).replace("__BGS__", _json.dumps(_hb.client_entries(), separators=(",", ":"))))
V = _hashlib.sha256(ASSET.encode("utf-8")).hexdigest()[:10]
PATH = f"/{FOLDER}/alto-holo-{V}.js"
GUARD = "_altoHolo"


def holo_asset() -> tuple[str, str]:
    """(file name under /holo/, the script) for the site (palace_assets.ASSETS)."""
    return PATH.rsplit("/", 1)[1], ASSET


def _lum(h: str) -> float:
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a: str, b: str) -> float:
    """WCAG 2.x contrast ratio of two #rrggbb colours."""
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + .05) / (lb + .05)
