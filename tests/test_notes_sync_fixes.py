"""Why notes sometimes would not save / stick. Each rule below was reproduced end
to end (two devices, real alto-cloud.js, a mock Firestore) in Chromium and WebKit
before it was fixed."""
import json
from pathlib import Path

from alto.build.builder import build_timeline, load_brief
from alto.cloud import SOURCE

ROOT = Path(__file__).resolve().parent.parent
JS = SOURCE.read_text(encoding="utf-8")


def _page():
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    return build_timeline(*load_brief(d))[0]


def test_the_storage_hook_writes_the_storage_it_was_called_on():
    """The 1.9.23 hook called a setter bound to localStorage, so every
    sessionStorage.setItem (the private shell's reload guard) landed in
    localStorage and the guard never saw it."""
    assert "const nativeSet = Storage.prototype.setItem;" in JS
    assert "nativeSet.call(this, k, v);" in JS
    assert "const origSet = (k, v) => nativeSet.call(localStorage, k, v);" in JS
    i = JS.index("Storage.prototype.setItem = function")
    assert "origSet(k, v)" not in JS[i:i + 300]


def test_a_later_edit_wins_so_shortening_a_note_sticks():
    """'The longer note wins' put a deleted sentence straight back after sync."""
    assert "function newerNote(local, remote)" in JS
    assert "if (lm || rm) return rm > lm;" in JS
    assert "out.push(r && newerNote(h, r) ? r : h)" in JS
    assert "String(r.note || '').length > String(h.note || '').length" not in JS
    page = _page()
    assert "hl.note = text; hl.mod = Date.now();" in page


def test_a_note_being_typed_is_not_shared_until_it_is_saved():
    assert "h && h.pending" in JS and "const pendingLocal" in JS
    assert "applyHighlightsLocally(keep, JSON.stringify(keep))" in JS
    page = _page()
    assert "note:'', quote:'', color:'yellow', pending:true" in page
    assert "delete hl.pending;" in page
