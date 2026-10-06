"""The glyphs an owner chooses from for a chip made in manual edit mode.

A chip (an element, or a value of an axis shown in the top bar) is drawn with
its glyph on every card and in the top bar, so two chips of a timeline must
never share one. The page offers these fifty, dimming the ones its chips
already use (manual_edit.py pickGlyph); the fold accepts only a glyph from
this list (alto/edits.py), never markup from the page.

Each is drawn the way the timeline's own chip glyphs are: a 20×20 line
drawing in the chip's colour (stroke="currentColor").
"""
from __future__ import annotations

import re

_WRAP = ('<svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" '
         'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">{}</svg>')

GLYPHS: list[tuple[str, str]] = [
    ("circle", '<circle cx="10" cy="10" r="6"/>'),
    ("square", '<rect x="4.5" y="4.5" width="11" height="11" rx="1.5"/>'),
    ("triangle", '<path d="M10 3.5 17 16H3z"/>'),
    ("diamond", '<path d="M10 2.5 17.5 10 10 17.5 2.5 10z"/>'),
    ("star", '<path d="M10 2.8l2.2 4.6 5 .6-3.7 3.4 1 5-4.5-2.5-4.5 2.5 1-5L2.8 8l5-.6z"/>'),
    ("heart", '<path d="M10 16.5S3 12.3 3 7.6A3.6 3.6 0 0 1 10 6a3.6 3.6 0 0 1 7 1.6c0 4.7-7 8.9-7 8.9z"/>'),
    ("hexagon", '<path d="M10 2.5l6.5 3.75v7.5L10 17.5l-6.5-3.75v-7.5z"/>'),
    ("pentagon", '<path d="M10 2.8 17 8l-2.7 8.5H5.7L3 8z"/>'),
    ("plus", '<path d="M10 4v12M4 10h12"/>'),
    ("cross", '<path d="M5 5l10 10M15 5 5 15"/>'),
    ("check", '<path d="M4 10.5l4 4 8-9"/>'),
    ("bolt", '<path d="M11 2.5 4.5 11H10l-1 6.5L15.5 9H10z"/>'),
    ("flag", '<path d="M5 17.5V3M5 3.5h9l-2 3.5 2 3.5H5"/>'),
    ("bell", '<path d="M5 14V9a5 5 0 0 1 10 0v5l1.5 1.5h-13zM8.5 17.5h3"/>'),
    ("key", '<circle cx="7" cy="10" r="3.5"/><path d="M10.5 10H17M14.5 10v3M16.5 10v2"/>'),
    ("lock", '<rect x="4.5" y="9" width="11" height="8" rx="1.5"/><path d="M7 9V6.5a3 3 0 0 1 6 0V9"/>'),
    ("eye", '<path d="M2.5 10S5.5 4.5 10 4.5 17.5 10 17.5 10 14.5 15.5 10 15.5 2.5 10 2.5 10z"/>'
            '<circle cx="10" cy="10" r="2.2"/>'),
    ("sun", '<circle cx="10" cy="10" r="3.2"/><path d="M10 2.5v2M10 15.5v2M2.5 10h2M15.5 10h2M4.7 4.7l1.4 1.4'
            'M13.9 13.9l1.4 1.4M4.7 15.3l1.4-1.4M13.9 6.1l1.4-1.4"/>'),
    ("moon", '<path d="M15.5 12.5A6.5 6.5 0 0 1 7.5 4.5a6.5 6.5 0 1 0 8 8z"/>'),
    ("cloud", '<path d="M6 15.5h8.5a3.5 3.5 0 0 0 .2-7 5 5 0 0 0-9.4 1.3A2.9 2.9 0 0 0 6 15.5z"/>'),
    ("drop", '<path d="M10 2.8S4.5 9 4.5 12.3a5.5 5.5 0 0 0 11 0C15.5 9 10 2.8 10 2.8z"/>'),
    ("leaf", '<path d="M4 16C4 8 9 4 16.5 3.5 16 11 12 16 4 16zM4 16l6-6"/>'),
    ("tree", '<path d="M10 2.5 4.5 10h3L5 14h10l-2.5-4h3zM10 14v3.5"/>'),
    ("flower", '<circle cx="10" cy="10" r="2"/><circle cx="10" cy="5.5" r="2.5"/><circle cx="10" cy="14.5" r="2.5"/>'
               '<circle cx="5.5" cy="10" r="2.5"/><circle cx="14.5" cy="10" r="2.5"/>'),
    ("house", '<path d="M3 9.5 10 3.5l7 6M5 8v8.5h10V8"/>'),
    ("book", '<path d="M3 4.5h5a2 2 0 0 1 2 2v10a2 2 0 0 0-2-2H3zM17 4.5h-5a2 2 0 0 0-2 2v10a2 2 0 0 1 2-2h5z"/>'),
    ("scales", '<path d="M10 3v14M6 17h8M4 5.5h12M4 5.5l-2 5h4zM16 5.5l-2 5h4z"/>'),
    ("shield", '<path d="M10 2.5 16 5v5c0 4-3 6.5-6 7.5-3-1-6-3.5-6-7.5V5z"/>'),
    ("anchor", '<circle cx="10" cy="4.5" r="1.8"/><path d="M10 6.3V17M6.5 9h7M3.5 11.5a6.5 6.5 0 0 0 13 0"/>'),
    ("compass", '<circle cx="10" cy="10" r="7"/><path d="M12.8 7.2 11.2 11.2 7.2 12.8 8.8 8.8z"/>'),
    ("clock", '<circle cx="10" cy="10" r="7"/><path d="M10 6v4l2.8 1.8"/>'),
    ("hourglass", '<path d="M5.5 3h9M5.5 17h9M6.5 3c0 4 7 5 7 7s-7 3-7 7M13.5 3c0 4-7 5-7 7s7 3 7 7"/>'),
    ("target", '<circle cx="10" cy="10" r="7"/><circle cx="10" cy="10" r="4"/>'
               '<circle cx="10" cy="10" r="1" fill="currentColor"/>'),
    ("speech", '<path d="M3.5 4.5h13v8.5H9l-4 3.5V13H3.5z"/>'),
    ("person", '<circle cx="10" cy="6" r="3"/><path d="M4 17c.5-3.5 3-5.5 6-5.5s5.5 2 6 5.5"/>'),
    ("people", '<circle cx="7.5" cy="7" r="2.5"/><circle cx="13.5" cy="7.5" r="2"/>'
               '<path d="M2.5 16c.4-3 2.4-4.7 5-4.7s4.6 1.7 5 4.7M13 11.6c2.3 0 4 1.3 4.5 4"/>'),
    ("coin", '<circle cx="10" cy="10" r="7"/><path d="M12.3 7.3c-.5-.9-1.4-1.3-2.4-1.3-1.4 0-2.4.8-2.4 1.9 '
             '0 2.6 5 1.4 5 4.1 0 1.1-1.1 2-2.6 2-1.1 0-2.1-.5-2.6-1.4M10 4.8V6M10 14v1.2"/>'),
    ("gear", '<circle cx="10" cy="10" r="2.6"/><circle cx="10" cy="10" r="5.2"/><path d="M10 2.5v2.3M10 15.2v2.3'
             'M2.5 10h2.3M15.2 10h2.3M4.7 4.7l1.6 1.6M13.7 13.7l1.6 1.6M4.7 15.3l1.6-1.6M13.7 6.3l1.6-1.6"/>'),
    ("link", '<path d="M8.5 11.5a3 3 0 0 0 4.2 0l2.6-2.6a3 3 0 0 0-4.2-4.2l-1 1M11.5 8.5a3 3 0 0 0-4.2 0'
             'l-2.6 2.6a3 3 0 0 0 4.2 4.2l1-1"/>'),
    ("pin", '<path d="M10 17.5s5.5-5.2 5.5-9.5a5.5 5.5 0 0 0-11 0c0 4.3 5.5 9.5 5.5 9.5z"/>'
            '<circle cx="10" cy="8" r="2"/>'),
    ("globe", '<circle cx="10" cy="10" r="7"/><path d="M3 10h14M10 3c2 2 3 4.5 3 7s-1 5-3 7c-2-2-3-4.5-3-7s1-5 3-7z"/>'),
    ("mountain", '<path d="M2.5 16 8 7l3 5 2-3 4.5 7z"/>'),
    ("waves", '<path d="M2.5 8c2-2 3.5-2 5 0s3 2 5 0 3.5-2 5 0M2.5 13c2-2 3.5-2 5 0s3 2 5 0 3.5-2 5 0"/>'),
    ("flame", '<path d="M10 17.5c3 0 5-2 5-5 0-3.5-3-5-3.5-9-2 1.5-3 3.5-3 5.5-1-.5-1.5-1.5-1.5-2.5'
              'C5.5 8 5 10 5 12.5c0 3 2 5 5 5z"/>'),
    ("note", '<path d="M7.5 15V4.5l9-2V13"/><circle cx="5.5" cy="15" r="2"/><circle cx="14.5" cy="13" r="2"/>'),
    ("bulb", '<path d="M7.5 14.5h5M8 17h4M10 2.5a5 5 0 0 0-3 9c.6.5 1 1.4 1 2.2V14h4v-.3c0-.8.4-1.7 1-2.2'
             'a5 5 0 0 0-3-9z"/>'),
    ("crown", '<path d="M3 15.5h14M3.5 13 2.5 5.5l4.5 3.5L10 3.5l3 5.5 4.5-3.5-1 7.5z"/>'),
    ("infinity", '<path d="M10 10c-1.8-2.4-3.2-3.5-4.8-3.5a3.5 3.5 0 0 0 0 7c1.6 0 3-1.1 4.8-3.5zm0 0'
                 'c1.8 2.4 3.2 3.5 4.8 3.5a3.5 3.5 0 0 0 0-7c-1.6 0-3 1.1-4.8 3.5z"/>'),
    ("cycle", '<path d="M15.5 8A6 6 0 0 0 4.8 6.2M4.5 12a6 6 0 0 0 10.7 1.8M4.5 3v3.5H8M15.5 17v-3.5H12"/>'),
    ("bars", '<path d="M4 16.5V11M8 16.5V6M12 16.5V9M16 16.5V3.5"/>'),
]

LIBRARY: list[dict] = [{"n": n, "s": _WRAP.format(inner)} for n, inner in GLYPHS]
_BY_SVG = {g["s"] for g in LIBRARY}


def inner(svg: str) -> str:
    """What a glyph draws, without its <svg> wrapper or spacing — the same
    test the page uses to say a glyph is taken (manual_edit.py glyphKey)."""
    m = re.search(r"<svg\b[^>]*>(.*)</svg>", svg or "", re.S)
    return re.sub(r"\s+", "", (m.group(1) if m else svg or "")).replace("/>", ">")


def from_library(svg) -> str:
    """The glyph if it is one of the library's, else ""."""
    return svg if isinstance(svg, str) and svg in _BY_SVG else ""
