"""The title header: a tab hanging from the top edge, with the page's format symbol beside the name (Luke, 2026-11-05: "1, B" of the
title-header sheet; Art's option B: readable on every ground, hangs from the very top so it cannot touch the corner buttons).

One tab on the homepage, Reports and every timeline page on a computer (a phone keeps the header it has: nothing here runs there).
Classic's tab is below and rides in the page; Retro's (a gold plate with chamfered feet) and Holographic's (a lit pane) ride in the hosted
scripts (retro.py, holo.py), which restyle the same element with the same two variables.

How the symbol gets there. The name is a bare <span id="title-text"> that other code rewrites (a rename sets its textContent, the cloud
store swaps its text), so no markup goes inside it. The symbol is its ::after, this page's own drawing as a background image with the ink baked
in (format_symbols.ink_uri; no mask), one per ink the styles use: --tt-sym on a light theme and --tt-syd on a dark one (Classic), --tt-syr (Retro's
black), --tt-syh and --tt-syk (Holographic's light and dark), and --tt-sw (the room it takes beside the name; 0 where a page has no format, the
homepage and Reports). The hover line (hover_lines.py) is the name's ::before, laid at the name's own padding.
"""
from __future__ import annotations

from . import format_symbols
from .backgrounds import _lean

# the tab's room, shared by every style (the hover line is laid at the same place)
AFTER_CSS = r"""
html:not(.mobile) #title-bar #title-text:not(#_)::after{content:"";position:absolute;left:var(--tt-px);top:calc(50% - 1.5px);translate:0 -50%;
  width:var(--tt-w,0);height:var(--tt-w,0);background:var(--tt-i,var(--tt-sym)) center/contain no-repeat;}
html.dark:not(.mobile) #title-bar #title-text:not(#_){--tt-i:var(--tt-syd);}
"""
BASE_CSS = r"""
html:not(.mobile) #title-bar #title-text:not(#_){--tt-px:20px;--tt-pt:7px;position:relative;align-self:start;box-sizing:border-box;display:block;white-space:nowrap;
  padding:var(--tt-pt) var(--tt-px) calc(var(--tt-pt) + 3px) calc(var(--tt-px) + var(--tt-sw,0px));font-size:20px;font-weight:600;letter-spacing:.04em;text-transform:none;}
html:not(.mobile) #title-bar #title-text:not(#_):hover::before{left:calc(var(--tt-px) + var(--tt-sw,0px));top:var(--tt-pt);}
"""

# Classic: a solid sheet of the theme's own surface, square at the top edge, rounded at its feet, a soft shadow so it reads on any ground
CLASSIC_CSS = r"""
html:not(.mobile) #title-bar #title-text:not(#_){background:color-mix(in srgb,var(--surface,#fff) 96%,transparent);color:var(--text);border-radius:0 0 14px 14px;
  box-shadow:0 0 0 1px var(--border,rgba(0,0,0,.12)),0 10px 22px -12px rgba(0,0,0,.5);-webkit-backdrop-filter:none;backdrop-filter:none;}
"""


# a System's own sky is dark in every theme and forces its name light (solar_stars.py): the sheet there is dark too
SOLAR_CSS = r"""
html.alto-stars:not(.mobile) #title-bar #title-text:not(#_){background:rgba(8,10,20,.9);color:#eef2ff !important;box-shadow:0 0 0 1px rgba(255,255,255,.22),0 10px 22px -12px #000;}
"""


# the inks, as the styles colour the name: Classic's text (light, dark), Retro's black on gold, Holographic's text (light, dark; holo.TOKENS tx), a System's light
INKS = {"sym": "#1a1a2e", "syd": "#e2e2f0", "syr": "#000", "syh": "#06485c", "syk": "#c9fffa"}


def vars_css(key: str | None) -> str:
    """The page's own symbol, once in each ink (none for the homepage and Reports). A System's sky is light in every theme: its one ink is the dark theme's."""
    if not key:
        return ""
    ink = {k: format_symbols.ink_uri(key, v) for k, v in INKS.items()}
    if key == "system":
        ink["sym"] = format_symbols.ink_uri(key, "#eef2ff")
        ink["syd"] = "var(--tt-sym)"
    return ":root{" + ";".join("--tt-%s:%s" % kv for kv in ink.items()) + ";--tt-w:18px;--tt-sw:26px;}"


def block(key: str | None = None) -> str:
    """The page copy, for a timeline page (comments and indentation left out; every byte counts on a palace page)."""
    return ('<style id="alto-title-tab">' + _lean(BASE_CSS + AFTER_CSS + CLASSIC_CSS + (SOLAR_CSS if key == "system" else ""), css=True)
            + vars_css(key) + "</style>")


def home_css(media: bool = True) -> str:
    """The homepage's and Reports' copy: a computer only (a phone keeps its header)."""
    body = _lean(BASE_CSS + CLASSIC_CSS, css=True).replace("html:not(.mobile) ", "html ")
    return "@media (min-width:641px){" + body + "}" if media else body
