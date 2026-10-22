"""The symbol each project format wears instead of its name.

A project (timeline, outline, Mind Palace, System) is labelled with one small
line drawing wherever it is named as a label: the homepage cards, the way back
from a detail page, the print heading. The name rides along as the tooltip and
the aria-label. Stroke-only, in the style of glyphs.py, so a symbol takes
the colour of the text it sits in.

The homepage template (engine/home_template.html) holds its own copy of these
drawings; tests/test_format_symbols.py keeps the two the same.
"""
from __future__ import annotations

BADGE = '<rect x="2.5" y="2.5" width="19" height="19" rx="5.5"/>'

# key -> (name shown as the tooltip, drawing, grid). Outline and System are drawn
# on a 20-grid, the badged four on a 24-grid; the grid picks the view box.
SYMBOLS: dict[str, tuple[str, str, int]] = {
    # a classic hourglass: the vertical timeline
    "timeline": ("Timeline",
                 BADGE + '<path d="M7.5 5.5h9M7.5 18.5h9M9 6.5c0 3.4 3 4.2 3 5.5s-3 2.1-3 5.5'
                 'M15 6.5c0 3.4-3 4.2-3 5.5s3 2.1 3 5.5"/>', 24),
    # a winding path with ring milestones and an arrowhead: the horizontal timeline
    "lanes": ("Timeline \u00b7 Horizontal",
              BADGE + '<g transform="translate(12 12) scale(.62) translate(-12 -12)" stroke-width="2.4">'
              '<path d="M3.5 19h3.2M12.3 19h3.2a3.5 3.5 0 0 0 0-7h-1.3M8.8 12H7.5a3.5 3.5 0 0 1 0-7h4.7'
              'M17.8 5h2.7M17.5 2.4 20.5 5l-3 2.6"/><circle cx="9.5" cy="19" r="2.2" stroke-width="1.25"/>'
              '<circle cx="11.5" cy="12" r="2.2" stroke-width="1.25"/><circle cx="15" cy="5" r="2.2" '
              'stroke-width="1.25"/></g>', 24),
    "outline": ("Outline",
                '<path d="M3 4.5h14M5 8v7.5M5 10.5h3M5 15.5h3M10.5 10.5H17M10.5 15.5H17"/>', 20),
    "system": ("System",
               '<circle cx="10" cy="10" r="1.8"/><circle cx="10" cy="10" r="7"/>'
               '<circle cx="5" cy="5" r="1.3"/>', 20),
    # a map pin
    "palace": ("Mind Palace",
               BADGE + '<path d="M12 16.5s-3-2.9-3-5.2a3 3 0 0 1 6 0c0 2.3-3 5.2-3 5.2z"/>'
               '<circle cx="12" cy="11.3" r="1" fill="currentColor"/>', 24),
    # a domed palace
    "building": ("Mind Palace \u00b7 Building",
                 BADGE + '<path d="M6.5 17.5h11M8 17.5v-5h8v5M8.3 12.5c0-2.2 1.2-3.3 3.7-4.8 2.5 1.5 '
                 '3.7 2.6 3.7 4.8M12 7.7V6M10.8 17.5v-2.2a1.2 1.2 0 0 1 2.4 0v2.2"/>', 24),
    # a globe with a route arc hopping to a stop: the World Palace
    "world": ("Mind Palace \u00b7 World",
              BADGE + '<circle cx="11" cy="13.2" r="5.3"/><path d="M11 7.9a2.3 5.3 0 0 0 0 10.6a2.3 5.3 0 0 0 0-10.6"/>'
              '<path d="M5.9 8.4Q10.6 3.4 16.6 6.4" stroke-dasharray="1.5 1.7"/><circle cx="17.6" cy="7.1" r="1.25" fill="currentColor"/>', 24),
}
KEYS = tuple(SYMBOLS)

_WRAP = ('<svg viewBox="0 0 {g} {g}" width="{s}" height="{s}" fill="none" stroke="currentColor" '
         'stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round" '
         'aria-hidden="true">{p}</svg>')


def key_of(b) -> str:
    """The symbol of a brief: a System is an outline with the solar layout; a
    Building Palace a palace with the building view (a World Palace the world view); the plain timeline
    runs down the page, the lanes timeline along it."""
    if b.mode == "outline":
        return "system" if b.layout == "solar" else "outline"
    if b.mode == "palace":
        return {"building": "building", "world": "world"}.get(b.palace_view, "palace")
    return "lanes" if b.mode == "lanes" else "timeline"


def name(key: str) -> str:
    return SYMBOLS[key][0]


def svg(key: str, size: int = 20) -> str:
    g = SYMBOLS[key][2]
    return _WRAP.format(g=g, s=size, w=g / 16, p=SYMBOLS[key][1])


def badge(key: str, size: int = 20) -> str:
    """The symbol with its name as the tooltip and the accessible name."""
    return (f'<span class="fmt-sym" title="{name(key)}" role="img" aria-label="{name(key)}">'
            f'{svg(key, size)}</span>')
