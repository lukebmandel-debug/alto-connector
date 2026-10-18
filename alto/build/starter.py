"""A blank timeline the owner starts on their homepage, without Claude.

The homepage's "＋ New timeline" / "Start new project" can make a timeline in
the browser alone: it fetches a starter page from the site (/new/{kind}.html),
writes it into the owner's account as a private page with their title and a
fresh id, writes the matching draft (project, timeline, nodes) where the
connector keeps drafts, and opens it in manual edit mode — where the owner adds
units, cards, chips and words (alto/build/manual_edit.py). Whenever Claude next
opens the timeline, those edits are folded into the draft (alto/edits.py) and
the page is built for real.

The starter is an ordinary private page (single_file.private_page) built from a
two-unit brief, with placeholders the browser swaps out:

  TID     the timeline id, a slug: every occurrence is replaced as it is.
  TITLE   the timeline's title, in page text, JS strings and JSON alike. The
          browser first turns the few characters that would need escaping in
          any of those into their typographic look-alikes (clean_title), so
          one plain replacement is right everywhere; in the notes report's
          mailto link it is URL-encoded (MAILTO).
  LABEL   the project's name, in one HTML attribute (attribute-escaped).

/new/{kind}.json is the draft: {brief, nodes}, with the same placeholders.
"""
from __future__ import annotations

import json

TID, TITLE, LABEL = "zqtidqz", "Zqtitleqz", "Zqlabelqz"
MAILTO = "subject=" + TITLE
KINDS = ("outline", "timeline", "lanes", "solar")

# What each kind starts with: two units (a timeline needs two), one card each.
_STARTERS = {
    "outline": {
        # A tree from the start: an outline made by hand is drawn as one, so
        # its cards can be dragged and new ones hang under their parents.
        "brief": {"mode": "outline", "columns": 5, "layout": "tree",
                  "node_noun": "Card", "period_noun": "Unit",
                  "entity_axis_label": "Tags", "entity_axis_singular": "Tag",
                  "acts": [{"label": "Unit 1", "short": "Unit 1"},
                           {"label": "Unit 2", "short": "Unit 2"}]},
        "nodes": [{"id": "unit-1-start", "act": 0, "title": "First card", "tag": "", "desc": ""},
                  {"id": "unit-2-start", "act": 1, "title": "First card", "tag": "", "desc": ""}],
    },
    "timeline": {
        "brief": {"mode": "linear", "columns": 3,
                  "node_noun": "Event", "period_noun": "Part",
                  "entity_axis_label": "People", "entity_axis_singular": "Person",
                  "acts": [{"label": "Part 1", "short": "Part 1"},
                           {"label": "Part 2", "short": "Part 2"}]},
        "nodes": [{"id": "part-1-start", "act": 0, "title": "First event", "tag": "", "desc": "",
                   "col": "center"},
                  {"id": "part-2-start", "act": 1, "title": "First event", "tag": "", "desc": "",
                   "col": "center"}],
    },
    # The horizontal timeline (lanes.py): the main line is the story as it is
    # told; two characters whose lines come onto it where they are on the
    # page, and a short flashback — so the shape is there to see and change.
    "lanes": {
        "brief": {"mode": "lanes", "columns": 3,
                  "node_noun": "Event", "period_noun": "Part",
                  "entity_axis_label": "People", "entity_axis_singular": "Person",
                  "main_line": "The story",
                  "lines": [{"id": "first", "label": "First character", "side": "above"},
                            {"id": "second", "label": "Second character", "side": "below"}],
                  "flashbacks": [{"id": "earlier", "label": "Years earlier"}],
                  "acts": [{"label": "Part 1", "short": "Part 1"},
                           {"label": "Part 2", "short": "Part 2"}]},
        "nodes": [{"id": "part-1-start", "act": 0, "title": "The story opens", "tag": "", "desc": "",
                   "when": "Year 10", "present": ["first"]},
                  {"id": "a-memory", "act": 0, "title": "A memory", "tag": "", "desc": "",
                   "when": "Year 2", "present": ["first", "second"], "flash": "earlier"},
                  {"id": "second-start", "act": 0, "title": "Meanwhile, off the page", "tag": "", "desc": "",
                   "line": "second", "when": "Year 11"},
                  {"id": "part-2-start", "act": 1, "title": "Where they meet", "tag": "", "desc": "",
                   "when": "Year 12", "present": ["first", "second"]}],
    },
    # The solar outline (layout 'solar' of an outline): each unit is a sun, the
    # concepts under it planets (outline order = ring order), a concept under
    # a planet its moon. Orbit style to begin with (Claude can switch it to
    # spokes: build_timeline hub_style) and one unit per sun, so two systems
    # sit side by side. A shape to see and change; the words are theirs.
    "solar": {
        "brief": {"mode": "outline", "columns": 5, "layout": "solar", "hub_style": "orbit",
                  "node_noun": "Card", "period_noun": "Unit",
                  "entity_axis_label": "Tags", "entity_axis_singular": "Tag",
                  "acts": [{"label": "Unit 1", "short": "Unit 1"},
                           {"label": "Unit 2", "short": "Unit 2"}]},
        "nodes": [{"id": "unit-1-start", "act": 0, "title": "Unit 1 hub", "tag": "", "desc": ""},
                  {"id": "unit-1-a", "act": 0, "parent": "unit-1-start", "title": "First concept", "tag": "", "desc": ""},
                  {"id": "unit-1-a1", "act": 0, "parent": "unit-1-a", "title": "A part of it", "tag": "", "desc": ""},
                  {"id": "unit-1-b", "act": 0, "parent": "unit-1-start", "title": "Second concept", "tag": "", "desc": ""},
                  {"id": "unit-2-start", "act": 1, "title": "Unit 2 hub", "tag": "", "desc": ""},
                  {"id": "unit-2-a", "act": 1, "parent": "unit-2-start", "title": "First concept", "tag": "", "desc": ""},
                  {"id": "unit-2-b", "act": 1, "parent": "unit-2-start", "title": "Second concept", "tag": "", "desc": ""}],
    },
}


def draft(kind: str) -> dict:
    s = _STARTERS[kind]
    return {"brief": {**json.loads(json.dumps(s["brief"])), "title": TITLE, "timeline_id": TID},
            "nodes": json.loads(json.dumps(s["nodes"]))}


def page(kind: str) -> str:
    """The starter's private page, placeholders in place."""
    from .builder import build_timeline, load_brief
    from .single_file import private_page
    b, nodes, conns = load_brief(draft(kind))
    html, _ = build_timeline(b, nodes, conns)
    out = private_page(b, html, LABEL)
    # Every place the page names its title must be one the browser can fill.
    rest = out.replace(MAILTO, "").replace(TITLE, "")
    assert TITLE.lower() not in rest.lower(), "title in a form the browser cannot fill"
    return out


def write(site) -> None:
    """/new/{kind}.html and /new/{kind}.json, for the homepage (regenerate_site)."""
    d = site / "new"
    d.mkdir(parents=True, exist_ok=True)
    for k in KINDS:
        (d / f"{k}.html").write_text(page(k), encoding="utf-8")
        (d / f"{k}.json").write_text(json.dumps(draft(k), ensure_ascii=False), encoding="utf-8")
