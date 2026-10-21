"""The symbol each project format wears instead of its name.

A project (timeline, outline, Mind Palace, System) is labelled with one small
line drawing wherever it is named as a label: the homepage cards, the way back
from a detail page, the print heading. The name rides along as the tooltip and
the aria-label. Same 20x20 stroke-only style as glyphs.py, so a symbol takes
the colour of the text it sits in.

The homepage template (engine/home_template.html) holds its own copy of these
drawings; tests/test_format_symbols.py keeps the two the same.
"""
from __future__ import annotations

# key -> (name shown as the tooltip, drawing)
SYMBOLS: dict[str, tuple[str, str]] = {
    "timeline": ("Timeline",
                 '<path d="M5 2.5v15M9 4h8M9 10h5M9 16h8"/>'
                 '<g fill="currentColor"><circle cx="5" cy="4" r="1.3"/><circle cx="5" cy="10" r="1.3"/>'
                 '<circle cx="5" cy="16" r="1.3"/></g>'),
    "lanes": ("Timeline \u00b7 Horizontal",
              '<path d="M2.5 6h15M2.5 14h15M4.5 17.5v-1.2M9.5 17.5v-1.2M14.5 17.5v-1.2"/>'
              '<g fill="currentColor"><circle cx="5" cy="6" r="1.3"/><circle cx="11" cy="6" r="1.3"/>'
              '<circle cx="8" cy="14" r="1.3"/><circle cx="15" cy="14" r="1.3"/></g>'),
    "outline": ("Outline",
                '<path d="M3 4.5h14M5 8v7.5M5 10.5h3M5 15.5h3M10.5 10.5H17M10.5 15.5H17"/>'),
    "system": ("System",
               '<circle cx="10" cy="10" r="1.8"/><circle cx="10" cy="10" r="7"/>'
               '<circle cx="15" cy="5" r="1.3"/>'),
    "palace": ("Mind Palace",
               '<path d="M2.5 5.5 7 3.5l6 2 4.5-2v11l-4.5 2-6-2-4.5 2zM7 3.5v11M13 5.5v11M10 9.5h.1"/>'),
    "building": ("Mind Palace \u00b7 Building",
                 '<path d="M2 17.5h16M6.5 17.5v-6.5h7v6.5M6.8 11a3.2 3.8 0 0 1 6.4 0M10 7.2V4.5M8.8 17.5v-3a1.2 1.2 0 0 1 2.4 0v3"/>'
                 '<path d="M3.5 17.5V8.5M16.5 17.5V8.5M2.5 8.5h2M15.5 8.5h2"/>'),
}
KEYS = tuple(SYMBOLS)

_WRAP = ('<svg viewBox="0 0 20 20" width="{s}" height="{s}" fill="none" stroke="currentColor" '
         'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" '
         'aria-hidden="true">{p}</svg>')


def key_of(b) -> str:
    """The symbol of a brief: a System is an outline with the solar layout; a
    Building Palace a palace with the building view; the plain timeline
    runs down the page, the lanes timeline along it."""
    if b.mode == "outline":
        return "system" if b.layout == "solar" else "outline"
    if b.mode == "palace":
        return "building" if b.palace_view == "building" else "palace"
    return "lanes" if b.mode == "lanes" else "timeline"


def name(key: str) -> str:
    return SYMBOLS[key][0]


def svg(key: str, size: int = 14) -> str:
    return _WRAP.format(s=size, p=SYMBOLS[key][1])


def badge(key: str, size: int = 14) -> str:
    """The symbol with its name as the tooltip and the accessible name."""
    return (f'<span class="fmt-sym" title="{name(key)}" role="img" aria-label="{name(key)}">'
            f'{svg(key, size)}</span>')
