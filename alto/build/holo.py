"""Holographic: a third style of every format, after Classic and Retro (Luke, 2026-10-28, picking direction B of the Item 1 sheet:
"On holographic style, i like B, but make sure that text is not blending into the background too much.").

The look is the sheet's "Projector": one cyan light, square wireframe cards, a faint grid and scan lines, as if projected into the air.
It is square like Retro (the square-vs-round rule) and, unlike Retro, it wears BOTH themes: html.dark picks the dark tokens and the
reader's light theme the light ones, so the light/dark toggle stays.

THE CONTRAST FLOOR. Every colour a rule uses for text or for the plate under it is one of the tokens below (TOKENS), and every pair
that can meet (PAIRS) is held to WCAG AA by tests/test_holo.py (4.5:1 for text, 3:1 for a line or an outline), light and dark. The
bars and the chip rows are solid (not see-through), so a card passing under them never shows through a label.

How it is built. The rules are Retro's own (retro.CHROME_CSS / BOARD_CSS / FORMAT_CSS: the same selectors for the bars, chips, panels,
detail pages, cards, lines, both palaces' maps and the Atlas), re-inked: `ink()` swaps Retro's gold, black, cream and navy for the tokens,
drops the frame, the cartouche, the forced dark theme and the poster lettering, and HOLO_CSS adds what only Projector has (the grid, the
scan lines, the glow, the solid bars, the phone's square controls). A format department refines its own part by adding rules to
FORMAT_CSS below. Carried like Retro: a page holds only the switch (backgrounds.py head script, window._altoStyle, `holo`) and a hosted
script (/holo/alto-holo-<hash>.js, palace_assets.ASSETS) that adds the rules, fetched only by a page set to Holographic.
"""
from __future__ import annotations

import hashlib as _hashlib
import json as _json
import re as _re

from . import retro as _rt

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
  X:not(.alto-palace):not(.alto-stars) :is(body,#canvas):not(#_){background-color:var(--ho-bg) !important;
    background-image:repeating-linear-gradient(0deg,rgba(var(--ho-rgb),.045) 0 1px,transparent 1px 3px),linear-gradient(rgba(var(--ho-rgb),.07) 1px,transparent 1px),linear-gradient(90deg,rgba(var(--ho-rgb),.07) 1px,transparent 1px) !important;
    background-size:auto,48px 48px,48px 48px !important;}
  /* the bars are solid: a card or a line passing under a label never shows through it (the floor on text over anything) */
  X :is(#title-bar,#nav,#node-nav-bar):not(#_):not(#__){--header-tint:transparent !important;background:rgba(var(--ho-bgrgb),.97) !important;}
  X #title-bar:not(#_):not(#__){border-bottom:1px solid rgba(var(--ho-rgb),.5) !important;}
  X #title-bar:not(#_):not(#__){box-shadow:var(--ho-glow) !important;}
  X #title-text:not(#_){color:var(--ho-tx) !important;font-weight:500 !important;}
  /* the cards: a square wireframe plate lit from its edge */
  X #world .node-card:not(#_){border:1px solid rgba(var(--ho-rgb),.62) !important;border-radius:0 !important;
    box-shadow:var(--ho-glow),inset 0 0 18px rgba(var(--ho-rgb),.06) !important;}
  X #world .node:not(.dimmed):hover .node-card:not(#_){border-color:var(--ho-ac) !important;box-shadow:var(--ho-glow),var(--ho-glow),inset 0 0 18px rgba(var(--ho-rgb),.1) !important;}
  X #world .node.focused .node-card:not(#_){background:var(--ho-sf2) !important;border-color:var(--ho-ac) !important;box-shadow:0 0 0 2px var(--ho-bg),0 0 0 3px var(--ho-ac),var(--ho-glow) !important;}
  X #world .node-tag:not(#_){letter-spacing:.14em !important;}
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
  /* the palace has no nav items: its empty band is not painted, so the Tour / World / zoom row clears it (Art fix 2) */
  X.wpal-open #nav:not(#_):not(#__){background:transparent !important;border:0 !important;box-shadow:none !important;}
  @media print{ X :is(#title-bar,#nav,#node-nav-bar){box-shadow:none !important;} }
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
    css = _re.sub(r"#(?:030407|05070b|06080c|0b0d12|0d1016)(?![0-9a-fA-F])", "var(--ho-sf)", css)
    css = _re.sub(r"#000(?![0-9a-fA-F])", "var(--ho-bg)", css)
    css = css.replace("sepia(1) saturate(2) hue-rotate(-8deg) brightness(.85)", "grayscale(1) sepia(1) hue-rotate(125deg) saturate(3)")
    css = _re.sub(r"font-family:[^;}]*(;|(?=}))", "", css)
    css = _re.sub(r"letter-spacing:(\.\d+)em", lambda m: "letter-spacing:" + ("%.2f" % min(float(m.group(1)), .12)).lstrip("0") + "em", css)
    return css


def css() -> str:
    """Every format's Holographic rules, as the hosted script adds them."""
    base = ink(_rt.CHROME_CSS + _rt.BOARD_CSS + _rt.FORMAT_CSS)
    body = base + "\n" + HOLO_CSS + FORMAT_CSS + _UNIT_CSS
    sel = "html.alto-holo"
    toks = (f"  {sel}:not(#_){{color-scheme:light;{_vars(TOKENS['light'], UNITS['light'])}}}\n"
            f"  {sel}.dark:not(#_){{color-scheme:dark;{_vars(TOKENS['dark'], UNITS['dark'])}}}\n")
    return "@media screen{\n" + _rt._slim(toks + _rt.scoped(body, sel)) + "\n}"


JS = r"""(function(){
if(window._altoHolo) return;
var r=document.documentElement, CSS=__CSS__, st=null;
function redraw(){ try{ if(typeof window.drawLines==='function') window.drawLines(); window.dispatchEvent(new Event('resize')); }catch(e){} }
function on(){
  if(!st){ st=document.createElement('style'); st.id='alto-holo-css'; st.textContent=CSS; }
  if(!st.parentNode) (document.head||r).appendChild(st);
  r.classList.add('alto-holo'); redraw();
}
function off(){ if(!r.classList.contains('alto-holo')) return; r.classList.remove('alto-holo'); redraw(); }
window._altoHolo={on:on, off:off};
})();"""

ASSET = _rt._slim(JS.replace("__CSS__", _json.dumps(css())))
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
