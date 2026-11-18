"""The symbol each project format wears instead of its name.

A project (timeline, outline, Memory Palace, System) is labelled with one small
line drawing wherever it is named as a label: the homepage cards, the way back
from a detail page, the print heading. The name rides along as the tooltip and
the aria-label. Stroke-only, in the style of glyphs.py, so a symbol takes
the colour of the text it sits in.

The homepage template (engine/home_template.html) holds its own copy of these
drawings; tests/test_format_symbols.py keeps the two the same.
"""
from __future__ import annotations

BADGE = '<rect x="2.5" y="2.5" width="19" height="19" rx="5.5"/>'

# key -> (name shown as the tooltip, drawing, grid). Every glyph is a solid
# plate with the mark cut out by an SVG mask (id alto-inv-KEY, unique per key) on a 24-grid.
SYMBOLS: dict[str, tuple[str, str, int]] = {
    # a classic hourglass: the vertical timeline
    "timeline": ("Timeline",
        '<defs><mask id="alto-inv-timeline" maskUnits="userSpaceOnUse" x="0" y="0" width="24" height="24"><rect width="24" height="24" fill="#fff" stroke="none"/><g stroke="#000" fill="none" stroke-width="1.4"><path d="M8 6.25h8M8 17.75h8M9.25 6.25c0 3 2.75 4 2.75 5.75s-2.75 2.75-2.75 5.75M14.75 6.25c0 3-2.75 4-2.75 5.75s2.75 2.75 2.75 5.75"/></g></mask></defs><rect x="2.5" y="2.5" width="19" height="19" rx="5.5" fill="currentColor" stroke="none" mask="url(#alto-inv-timeline)"/>', 24),
    # a winding path with ring milestones and an arrowhead: the horizontal timeline
    "lanes": ("Timeline \u00b7 Horizontal",
        '<defs><mask id="alto-inv-lanes" maskUnits="userSpaceOnUse" x="0" y="0" width="24" height="24"><rect width="24" height="24" fill="#fff" stroke="none"/><g stroke="#000" fill="none" stroke-width="1.5"><g transform="translate(12 12) scale(.62) translate(-12 -12)" stroke-width="2.4"><path d="M3.5 19h3.2M12.3 19h3.2a3.5 3.5 0 0 0 0-7h-1.3M8.8 12H7.5a3.5 3.5 0 0 1 0-7h4.7M17.8 5h2.7M17.5 2.4 20.5 5l-3 2.6"/><circle cx="9.5" cy="19" r="2.2" stroke-width="1.25"/><circle cx="11.5" cy="12" r="2.2" stroke-width="1.25"/><circle cx="15" cy="5" r="2.2" stroke-width="1.25"/></g></g></mask></defs><rect x="2.5" y="2.5" width="19" height="19" rx="5.5" fill="currentColor" stroke="none" mask="url(#alto-inv-lanes)"/>', 24),
    "outline": ("Outline",
        '<defs><mask id="alto-inv-outline" maskUnits="userSpaceOnUse" x="0" y="0" width="24" height="24"><rect width="24" height="24" fill="#fff" stroke="none"/><g stroke="#000" fill="none" stroke-width="1.4"><path d="M10.25 8.25H17M10.25 12H17M10.25 15.75H17"/><circle cx="7.25" cy="8.25" r="0.9" fill="#000" stroke="none"/><circle cx="7.25" cy="12" r="0.9" fill="#000" stroke="none"/><circle cx="7.25" cy="15.75" r="0.9" fill="#000" stroke="none"/></g></mask></defs><rect x="2.5" y="2.5" width="19" height="19" rx="5.5" fill="currentColor" stroke="none" mask="url(#alto-inv-outline)"/>', 24),
    "system": ("System",
        '<defs><mask id="alto-inv-system" maskUnits="userSpaceOnUse" x="0" y="0" width="24" height="24"><rect width="24" height="24" fill="#fff" stroke="none"/><g stroke="#000" fill="none" stroke-width="2.2727272727272725"><g transform="translate(12 12) scale(0.66) translate(-10 -10)"><circle cx="10" cy="10" r="1.8"/><circle cx="10" cy="10" r="7"/><circle cx="5" cy="5" r="1.3"/></g></g></mask></defs><rect x="2.5" y="2.5" width="19" height="19" rx="5.5" fill="currentColor" stroke="none" mask="url(#alto-inv-system)"/>', 24),
    # a map pin
    "palace": ("Memory Map",
        '<defs><mask id="alto-inv-palace" maskUnits="userSpaceOnUse" x="0" y="0" width="24" height="24"><rect width="24" height="24" fill="#fff" stroke="none"/><g stroke="#000" fill="none" stroke-width="1.5"><g transform="translate(0 -0.4)"><path d="M12 16.5s-3-2.9-3-5.2a3 3 0 0 1 6 0c0 2.3-3 5.2-3 5.2z"/><circle cx="12" cy="11.3" r="1" fill="#000"/></g></g></mask></defs><rect x="2.5" y="2.5" width="19" height="19" rx="5.5" fill="currentColor" stroke="none" mask="url(#alto-inv-palace)"/>', 24),
    # a solid blueprint panel with the plan cut out in light lines (the one filled badge in the family)
    "building": ("Memory Blueprint",
                 '<defs><mask id="alto-bp-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="24" height="24"><rect width="24" height="24" fill="#fff" stroke="none"/><path d="M6.75 8.25h6v3.75h4.5v4.5H6.75zM6.75 12.75h3" stroke="#000" fill="none"/></mask></defs><rect x="2.5" y="2.5" width="19" height="19" rx="5.5" fill="currentColor" stroke="none" mask="url(#alto-bp-mask)"/>', 24),
    # a globe with a route arc hopping to a stop: the Memory Atlas
    "world": ("Memory Atlas",
        '<defs><mask id="alto-inv-world" maskUnits="userSpaceOnUse" x="0" y="0" width="24" height="24"><rect width="24" height="24" fill="#fff" stroke="none"/><g stroke="#000" fill="none" stroke-width="1.5"><circle cx="12" cy="12" r="5.5" fill="#000" stroke="none"/><clipPath id="alto-inv-world-clip"><circle cx="12" cy="12" r="4.9"/></clipPath><g clip-path="url(#alto-inv-world-clip)"><path d="M9.45 7.8l.05 -.3 .75 -.45 .55 .3 .2 -.1 .25 .15 .2 -.25 0 .15 .3 -.05 0 .15 -.5 .1 -.2 .35 .55 .25 .05 .3 .25 -.4 0 -.35 .35 .05 .05 .2 .2 -.15 .6 .55 -.6 .15 -1.05 .65 .05 -.3 -.35 -.25 -1.85 -.2 .15 -.55zM10.8 7.05l.35 0 0 .15 -.4 .05 .05 -.2zM11.75 6.75l.4 0 -.45 .2 .25 -.15 -.15 0zM12.55 8.85l-.2 -.2 -.35 .2 .65 -.35 -.1 .1 .4 .2 -.3 .15 .15 -.15 -.25 .05zM13 8.6l.15 -.3 -.05 .15 .2 0 .1 .2 -.4 -.05zM11.55 7.15l.7 .1 .25 .15 -.25 .05 .2 .15 -.6 -.1 .2 -.2 -.5 -.15zM11.3 12.05l-.05 .15 -.25 -.35 .3 .2zM11.1 10.85l.4 -.1 .55 .25 -.3 .05 -.35 -.25 -.25 .05zM12.3 11.25l0 -.2 .25 .15 -.25 .05zM12.05 6.9l.45 -.2 .7 .25 .3 .15 -.2 .3 .15 .35 -.65 -.35 -.1 -.25 -.65 -.25zM10.4 11.5l.3 -.3 .1 .25 -.35 .1zM11.25 11.5l-.4 .2 -.15 -.15 .1 -.1 .45 .05zM8.9 9.7l1 .35 .25 .35 -.1 .45 .2 .3 .7 -.25 -.55 .6 -.6 -.25 -.4 -.3 -.35 -1.15 .05 .8 -.2 -.9zM11.25 11.5l-.1 .4 -.35 -.2 .4 -.2zM11.75 12.15l-.05 .1 -.1 -.15 -.1 .15 -.25 -.05 0 -.15 .5 .05zM9.45 7.8l.05 -.4 -.25 .05 .2 -.1 -.6 .25 1.4 -.7 -.75 .6 0 .3zM12 8.85l.35 -.2 .2 .2 -.2 .25 -.3 .05 -.1 .35 0 -.2 -.1 .05 .1 .25 -.45 .4 0 .55 -.2 -.45 -.35 -.05 -.2 0 .05 .15 -.45 -.1 -.2 .3 -.6 -.55 -.3 0 -.5 -.35 .05 -.5 .4 -.65 1.95 .2 .35 .25 -.05 .3 .55 -.25zM13.4 15.5l0 .45 -.7 .3 .1 .1 -.4 .5 -.3 -.1 .45 -1.6 .5 -.25 .45 .25 -.1 .15 .4 -.15 -.35 .35zM12.5 14.55l0 -.6 .4 -.1 .65 .7 -.45 .35 -.45 .1 -.15 -.45zM12.8 12.85l.3 -.15 -.15 -.15 .4 -.1 .2 .35 .5 -.1 .15 -.25 .15 .3 -.25 .3 .25 .05 .2 -.2 .2 .25 .4 -.1 .35 .2 -.65 1.5 -.65 .35 -.5 .65 -.3 -.25 .4 -.3 -.15 -.3 -.15 0 0 -.5 -.55 -.35 -.05 -.2 -.5 .1 -.3 -.3 .4 -.3 0 -.55 .25 .05zM12.4 14.6l.3 .4 -.6 1.75 .3 .1 -.35 .05 -.1 -.3 .2 -.1 -.05 -.45 .3 -1.45zM12.35 11.8l-.2 .3 .55 .25 .1 .5 -.3 -.05 0 .55 -.05 -.15 -.85 -.4 .2 -.2 -.05 -.45 .6 -.35zM11.95 12.95l-.45 .4 0 -.45 .45 .05zM13.35 12.45l.05 -.35 .25 .2 .1 .4 -.2 .1 -.2 -.35zM12.5 13.35l-.4 .3 .5 .45 -.15 .5 -.55 -.35 -.5 -.9 .2 .05 .4 -.45 .5 .4zM13.5 14.75l.3 .25 -.2 .3 -.2 0 .1 -.15 -.4 -.25 .1 -.2 .3 0zM13.95 12.4l-.15 .35 -.2 -.3 .35 -.1zM13.7 15.75l-.35 .05 .05 -.3 .3 .25zM13.4 12.1l-.05 .35 -.4 .1 .15 .15 -.25 .15 -.15 -.5 -.4 -.05 -.1 -.4 .15 -.1 -.05 .3 .15 -.3 .2 .15 .6 -.05 .15 .2z" fill="#fff" stroke="#fff" stroke-width=".2" stroke-linejoin="round"/></g></g></mask></defs><rect x="2.5" y="2.5" width="19" height="19" rx="5.5" fill="currentColor" stroke="none" mask="url(#alto-inv-world)"/>', 24),
}
KEYS = tuple(SYMBOLS)

_WRAP = ('<svg viewBox="0 0 {g} {g}" width="{s}" height="{s}" fill="none" stroke="currentColor" '
         'stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round" '
         'aria-hidden="true">{p}</svg>')


def key_of(b) -> str:
    """The symbol of a brief: a System is an outline with the solar layout; a
    Memory Blueprint a palace with the building view (a Memory Atlas the world view); the plain timeline
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


def ink_uri(key: str, ink: str) -> str:
    """The symbol as a CSS url() for `background-image`, drawn in one flat ink (the title tab's, title_tab.py; a style's own ink is baked in, no mask).
    Quotes, brackets and the hash are escaped so it sits in a style rule on any page."""
    g = SYMBOLS[key][2]
    body = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" fill="none" stroke="%s" stroke-width="%s" '
            'stroke-linecap="round" stroke-linejoin="round">%s</svg>' % (g, g, ink, g / 16, SYMBOLS[key][1].replace("currentColor", ink)))
    body = body.replace('"', "'").replace("<", "%3C").replace(">", "%3E").replace("#", "%23")
    return 'url("data:image/svg+xml,%s")' % body
