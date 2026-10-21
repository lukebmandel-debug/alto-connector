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
                 '<path d="M2.5 16h15M5 16v-5M10 16V5M15 16V8.5"/>'
                 '<circle cx="5" cy="9.7" r="1.3"/><circle cx="10" cy="3.9" r="1.3"/>'
                 '<circle cx="15" cy="7.2" r="1.3"/>'),
    "outline": ("Outline",
                '<path d="M3 4.5h14M5 8v7.5M5 10.5h3M5 15.5h3M10.5 10.5H17M10.5 15.5H17"/>'),
    "system": ("System",
               '<circle cx="10" cy="10" r="1.8"/><circle cx="10" cy="10" r="7"/>'
               '<circle cx="15" cy="5" r="1.3"/>'),
    "palace": ("Mind Palace",
               '<path d="M2.5 17.5h15M4 17.5V9.5h4v8M8 17.5V4h5v13.5M13 17.5v-7h3v7M10 7h1M10 10h1M10 13h1"/>'),
    "building": ("Mind Palace \u00b7 Building",
                 '<path d="M3 17.5h14M5.5 17.5v-14h9v14M8.5 17.5V14h3v3.5M8.5 6.5h3M8.5 9.5h3"/>'),
}
KEYS = tuple(SYMBOLS)

_WRAP = ('<svg viewBox="0 0 20 20" width="{s}" height="{s}" fill="none" stroke="currentColor" '
         'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" '
         'aria-hidden="true">{p}</svg>')


def key_of(b) -> str:
    """The symbol of a brief: a System is an outline with the solar layout; a
    Building Palace a palace with the building view; lanes and the plain
    timeline are both timelines."""
    if b.mode == "outline":
        return "system" if b.layout == "solar" else "outline"
    if b.mode == "palace":
        return "building" if b.palace_view == "building" else "palace"
    return "timeline"


def name(key: str) -> str:
    return SYMBOLS[key][0]


def svg(key: str, size: int = 14) -> str:
    return _WRAP.format(s=size, p=SYMBOLS[key][1])


def badge(key: str, size: int = 14) -> str:
    """The symbol with its name as the tooltip and the accessible name."""
    return (f'<span class="fmt-sym" title="{name(key)}" role="img" aria-label="{name(key)}">'
            f'{svg(key, size)}</span>')
