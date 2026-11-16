"""The words in the Info panel (a computer) and the How to use sheet (a phone), one set per format.

The panel used to be one text, written for the vertical timeline, shown on every format (a Memory Map told its
reader about a Filter tab and a picture tab, a System about cards and chips). Each page now carries its own: a
short part every page shares (making it, Overview, highlights, Notes, the bottom-right controls) and the part
that is its own format's controls. engine_patches.py leaves tokens where these go; blocks.py fills them from
`parts(key, sections)`. Text only: no markup the panel did not already use, and no quote marks (the phone's
sheet is built from JS strings).

Keys are format_symbols.key_of(brief): timeline, lanes, outline, system, palace, building, world.
"""
from __future__ import annotations

from . import bass_ui as _bass_ui          # Bass (bass_ui.py): its Info lines, only in a build made with ALTO_BASS_UI=1

# What each format is called in plain words (the "New" copy rule: name the format where it is known).
FMT = {"timeline": "timeline", "lanes": "horizontal timeline", "outline": "outline", "system": "System",
       "palace": "Memory Map", "building": "Memory Blueprint", "world": "Memory Atlas"}
LABEL = {"timeline": "Timeline", "lanes": "Horizontal timeline", "outline": "Outline", "system": "System",
         "palace": "Memory Map", "building": "Memory Blueprint", "world": "Memory Atlas"}

# ── a computer ──────────────────────────────────────────────────────────────

_BODY_D = {
    "timeline": "click any card to open its detail page ({sec}). &#8592; &#8594; step between pages; "
                "<em>&#8592; <span class=\"db-name\"></span></em> or Esc goes back.",
    "outline": "click any card to open its detail page ({sec}). &#8592; &#8594; step between pages; "
               "<em>&#8592; <span class=\"db-name\"></span></em> or Esc goes back.",
    "lanes": "click any card to open its page. The bar at the bottom steps to the previous or next event "
             "(&#8592; &#8594; too; hold to glide, &#8593; &#8595; hop lines), shows the whole "
             "timeline and zooms (pinch, &#8984;-scroll, + / &#8722;). Esc goes back; K shows the key.",
    "system": "click a body to fly to it and open its card ({sec}). Bottom left, <em>System</em> | <em>Star chart</em> "
              "switch the picture, <em>Orbit</em> (Space) stops and starts the orbits and <em>Ship</em> picks your ship. "
              "The pill beside shows where you are, with Back and Next; 1&#8211;9 fly to a neighbour, Esc climbs a "
              "level, ? lists the keys.",
    "palace": "click a building to open its card ({sec}); drag to move round and use the zoom buttons at bottom left. "
              "The target button shows the whole city, <em>Directions</em> plans a route between two buildings and "
              "the key button explains the lines.",
    "building": "click a room to open its card ({sec}). The dock at the bottom zooms (+ / &#8722;), fits the plan to "
                "the screen (0), lists the cards in order (C) and shows the key and credits (K).",
    "world": "click a pin to open its card ({sec}); Esc puts it back. The bottom bar switches <em>Flat map</em> | "
             "<em>Globe</em>, plays the Tour (previous or next stop) and zooms; Back and Next climb and walk the "
             "levels, 1&#8211;9 go to the lit places, O is the whole world and ? lists the keys.",
}

_SCENE_PICKER = ("the <em>Scene</em> tab on the right edge puts a colour, a pattern or a photograph behind this {fmt} "
                 "and switches Classic, Retro or Holographic (dark only). Each keeps its own.")
_SCENE = {
    "timeline": _SCENE_PICKER, "outline": _SCENE_PICKER, "lanes": _SCENE_PICKER,
    "system": "the <em>Scene</em> tab on the right edge switches the look: System, Star chart, Retro, 3D Star chart or "
              "Holographic (dark only). This format draws its own background.",
    "palace": "the <em>Scene</em> tab on the right edge switches Classic, Retro or Holographic (dark only). This "
              "format draws its own background; open a card to choose one for its page.",
    "building": "the <em>Scene</em> tab on the right edge switches Classic, Retro or Holographic (dark only). This "
                "format draws its own background; open a card to choose one for its page.",
    "world": "the <em>Scene</em> tab on the right edge switches Classic, Retro or Holographic (dark only). This "
             "format draws its own background; open a card to choose one for its page.",
}

_FILTER = ("the chips along the top open group pages; the <em>Filter</em> tab narrows the cards (double-click it: "
           "every filter off, again: back on).")
_FILTERED = ("timeline", "outline", "lanes")

_EDIT_TAIL = {
    "timeline": "click words to change them, drag to move, add entries",
    "outline": "click words to change them, drag to move, add entries",
    "lanes": "click words to change them, drag to move, add a box tag or a time flag",
    "system": "click words to change them, add or remove cards",
    "palace": "click words to change them, add a floor to a building",
    "building": "click words to change them",
    "world": "click words to change them, add a country",
}

_P = '      <p class="info-desktop" style="margin:5px 0"><strong>{h}</strong> &#8212; {t}</p>\n'


def _paras(rows):
    return "".join(_P.format(h=h, t=t) for h, t in rows)


def desktop(key, sections):
    """The panel's paragraphs, whole (engine_patches.py leaves only the box around them)."""
    fmt = FMT[key]
    rows = []
    rows.append(("Overview", "the &#10022; tab on the right edge gives an overview; click a phrase to jump to its card."))
    if key in _FILTERED:
        rows.append(("Groups &amp; filters", _FILTER))
    rows.append(("Scene", _SCENE[key].format(fmt=fmt)))
    rows.append(("Highlight &amp; note", "drag over text to highlight it (the dot at bottom center sets the color); "
                 "click a highlight to add a note."))
    rows.append(("Notes", "the <em>Notes</em> tab holds your highlights and reports, and shares or prints. Its "
                 "<em>Freewrite</em> mode is for writing as you browse; tick <em>Attach my "
                 "Freewrite</em> above <em>Generate Report</em> to include it."))
    rows.append(("Edit", "<em>Edit with Claude</em>: bigger changes. <em>Edit manually</em>: small ones &#8212; "
                 + _EDIT_TAIL[key] + ". &#8984;Z undoes."))
    rows.append(("Controls", "bottom right: search, this &#9432;, light or dark, Edit. Bottom left signs you in; the "
                 "Alto clef or wordmark opens your homepage."))
    making = ("build by hand if you like. The suggested route: have Claude build this " + fmt
              + " from your own notes or readings, then make small adjustments yourself.")
    first = [("Making it", making), (LABEL[key], _BODY_D[key].format(sec=sections))]
    return _bass_ui.info_desktop(_paras(first) + _paras(rows))


# ── a phone ─────────────────────────────────────────────────────────────────

_BODY_M = {
    "timeline": "Swipe a card left or right, or tap the arrows in the bar at the bottom, to step through in order. "
                "Tap the current card to open its detail page ({sec}). Tap the back arrow (top-left) to return.",
    "outline": "Swipe a card left or right, or tap the arrows in the bar at the bottom, to step through in order. "
               "Tap the current card to open its detail page ({sec}). Tap the back arrow (top-left) to return.",
    "lanes": "Drag along the line and pinch to zoom. The bar at the bottom steps to the previous or next event and "
             "shows the whole timeline. Tap a card to open its page ({sec}); tap the back arrow (top-left) to return.",
    "system": "Drag to look round and pinch to zoom. Tap a body to fly to it and open its card ({sec}); tap the back "
              "arrow (top-left) to return.",
    "palace": "Drag to move round and pinch to zoom. Tap a building to open its card ({sec}). <strong>Directions</strong> "
              "plans a route between two buildings. Tap the back arrow (top-left) to return.",
    "building": "Drag to move round and pinch to zoom. Tap a room to open its card ({sec}); tap the back arrow "
                "(top-left) to return.",
    "world": "Drag to move round and pinch to zoom. Tap a pin to open its card ({sec}). The pill at the top sets the "
             "scope; the Tour bar steps from place to place. Tap the back arrow (top-left) to return.",
}
_MENU_EXTRA = {
    "timeline": "; <strong>Whole view</strong> shows it all on one screen and <strong>One card</strong> brings the "
                "card back",
    "outline": "; <strong>Whole view</strong> shows it all on one screen and <strong>One card</strong> brings the "
               "card back",
    "system": "; its <strong>View</strong> list switches System, Star chart, Orbit and Ship",
    "world": "; its <strong>View</strong> list holds Tour and World",
}
_SCENE_M = {
    "timeline": "put a colour, a pattern or a photograph behind this {fmt}. Each one keeps its own.",
    "outline": "put a colour, a pattern or a photograph behind this {fmt}. Each one keeps its own.",
    "lanes": "put a colour, a pattern or a photograph behind this {fmt}. Each one keeps its own.",
}
_SCENE_M_OWN = "switch the look (Holographic is dark only). This format draws its own background."


def _h(title, text):
    return "    '    <h3>" + title + "</h3>',\n    '    <p>" + text + "</p>',\n"


def phone(key, sections):
    """The sheet's items, whole: JS array items for the engine's tutorial-body list."""
    fmt = FMT[key]
    out = _h("Find and MENU", "<strong>FIND</strong> (bottom-left) searches cards, pages and phrases. "
             "<strong>MENU</strong> (bottom-right) holds Overview, Dark / Light, Scene, Map, Notes, Filter and "
             "this How to use" + _MENU_EXTRA.get(key, "") + ". <strong>Filter</strong> narrows the cards; double-tap "
             "it to switch every filter off, and again to bring them back.")
    out += _h("Map and Overview", "<strong>Map</strong> lists every card, grouped by section; tap one to feature it, "
              "or, from a detail page, to jump to it. Tap a phrase in the <strong>Overview</strong> to jump to its card.")
    out += _h("Scene", "<strong>Scene</strong> in MENU will " + _SCENE_M.get(key, _SCENE_M_OWN).format(fmt=fmt))
    out += _h("MARK and NOTES", "On a page, tap <strong>MARK</strong> (bottom-right), then drag over text to highlight "
              "it; the dot at the bottom sets the color. Tap <strong>NOTES</strong> to see everything you&#8217;ve "
              "saved; tap a highlight there to add a note. Its <strong>Freewrite</strong> switch opens a page for "
              "writing an outline or answer as you move around; tick <strong>Attach my Freewrite</strong> above "
              "<strong>Generate Report</strong> to put it in a report too.")
    out += _h("Share &amp; Print", "Open <strong>NOTES</strong> and tap the share arrow in its header to send a copy "
              "or print it.")
    out += _h("Making and editing", "You can build one entirely by hand on a computer, but the suggested route is to "
              "have Claude build this " + fmt + " from your own notes, outlines or readings, then make small "
              "adjustments yourself. On a phone, <strong>Edit this page</strong> (at the foot of a page) changes its "
              "words; adding and moving are done on a computer.")
    return _bass_ui.info_phone(_h("Open a card" if key in ("timeline", "outline") else LABEL[key], _BODY_M[key].format(sec=sections)) + out)
