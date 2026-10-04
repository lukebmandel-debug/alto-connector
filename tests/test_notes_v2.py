"""Notes and highlights, second pass (alto/build/notes_v2.py). The behaviour
itself was exercised in Chromium and WebKit (desktop + phone): highlight, Note
pop-up, box Undo/Redo, Notes-panel Undo/Redo, tap to go to the page, a store
with duplicate ids, and a highlight across two paragraphs (see
test_notes_v2_browser.py for the part that runs when Playwright is installed)."""
import json
import re
from pathlib import Path

import pytest

from alto.build.builder import build_timeline, load_brief
from alto.build.fingerprint import _TIMELINE_SOURCES

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def html():
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    return build_timeline(*load_brief(d))[0]


def _body(html):
    i = html.index('id="alto-notes-v2"')
    return html[i:html.index("</script>", i)]


def test_every_page_carries_the_module(html):
    assert 'id="alto-notes-v2"' in html and 'id="alto-notes-v2-css"' in html
    assert "__ALTO_HL_KEY__" not in html


def test_every_key_comes_from_the_pages_own_highlight_key(html):
    """A share re-stamps `alto-hl-{tid}` by text, so the module spells it out
    once and builds the ops/history keys from it."""
    tid = re.search(r"var COURSE_ID = '([^']*)';", html).group(1)
    body = _body(html)
    assert f"var KEY = 'alto-hl-{tid}', TKEY = KEY + '-trash', OKEY = KEY + '-ops', HKEY = KEY + '-hist';" in body


def test_ids_are_unique_not_a_counter_that_restarts(html):
    body = _body(html)
    assert "uid('hl-')" in body and "hlCounter" not in body
    assert "seen[h.id]" in body                      # a store that already has duplicates is repaired


def test_highlights_are_painted_back_by_page_not_by_first_match(html):
    body = _body(html)
    assert "own('renderHighlightMarks', paint)" in body and "own('findAndMarkText'" in body
    assert "src: src, pre: ctx.pre, post: ctx.post" in body


def test_the_note_box_has_its_own_undo_and_redo(html):
    body = _body(html)
    assert "nd-undo" in body and "nd-redo" in body and "function step(d)" in body


def test_the_panel_undo_covers_every_change_and_has_a_redo(html):
    body = _body(html)
    assert "notes-redo-btn" in body and "window._altoNotesHist = HIST" in body
    i = html.index('id="alto-notes-trash"')
    trash = html[i:html.index("</script>", i)]
    assert "H.canUndo()" in trash and "H.undo(); else undo();" in trash
    assert "trashGone: trashGone" in trash


def test_note_pop_up_and_tap_to_go(html):
    body = _body(html)
    assert "alto-note-pop" in body and "<span>Note</span>" in body
    assert "tap(item, function(){ go(" in body and "tap(ed, function(){ openNote(" in body


def test_the_module_is_part_of_the_page_stamp():
    assert "notes_v2.py" in _TIMELINE_SOURCES and "detail_extras.py" in _TIMELINE_SOURCES
