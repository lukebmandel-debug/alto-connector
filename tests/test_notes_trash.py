"""Undo + Deleted-notes trash in the Notes panel. The behaviour itself was
exercised in Chromium and WebKit (desktop + mobile): delete, Undo, the list,
Bring back, Delete forever, Clear all then Undo."""
import json
import re
from pathlib import Path

import pytest

from alto.build.builder import build_timeline, load_brief
from alto.cloud import SOURCE

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def html():
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    return build_timeline(*load_brief(d))[0]


def test_every_page_carries_the_trash(html):
    assert 'id="alto-notes-trash"' in html and 'id="alto-trash-css"' in html
    assert "notes-undo-btn" in html and "notes-trash-btn" in html and "notes-trash" in html


def test_its_storage_key_is_the_pages_own_highlight_key(html):
    """A share re-stamps `alto-hl-{tid}` by text, so the trash must spell it out
    in that form (then a share never reads or writes the master's trash)."""
    tid = re.search(r"var COURSE_ID = '([^']*)';", html).group(1)
    assert f"var KEY = 'alto-hl-{tid}', TKEY = KEY + '-trash'" in html
    assert "__ALTO_HL_KEY__" not in html


def test_deletes_are_caught_by_wrapping_not_by_overriding_setItem(html):
    """Safari ignores `localStorage.setItem = …`, so the trash wraps the delete
    functions instead."""
    i = html.index('id="alto-notes-trash"')
    body = html[i:html.index("</script>", i)]
    assert "wrap('deleteHighlight'); wrap('clearAllHighlights');" in body
    assert "localStorage.setItem =" not in body and "ls.setItem =" not in body


def test_cloud_layer_syncs_the_trash_and_hooks_safari():
    src = SOURCE.read_text()
    assert "TR_KEY" in src and "hl_trash" in src and "hl_trash_purged" in src
    assert "function mergeTrash" in src
    assert "Storage.prototype.setItem = function" in src
    assert "localStorage.setItem = function" not in src


def test_clear_all_no_longer_says_permanent(html):
    assert "permanently delete all" not in html


def test_the_deleted_list_has_a_home_button_where_the_plus_was(html):
    assert 'id = \'notes-home-btn\'' in html or "hm.id = 'notes-home-btn'" in html
    assert "#notes-panel.trash-mode #notes-add-btn{display:none !important;}" in html
    assert "#notes-panel.trash-mode #notes-footer .nt-home{display:flex !important;}" in html
    i = html.index("row.appendChild(u); row.appendChild(add); row.appendChild(hm)")
    assert "setMode(false)" in html[i - 400:i]
