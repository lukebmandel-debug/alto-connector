"""Folding a Drive chip into the draft (alto/edits.py): a REFERENCE only. It becomes src:gd-… and a linked_files entry of kind drive; nothing is looked
up, found on disk or fetched; folding twice changes nothing; published() marks it done. Plain venv, no SDK, nothing skipped."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build.sanitize import clean_linked_markup  # noqa: E402
from alto.edits import fold, published, page_to_source, drives_in  # noqa: E402
from test_manual_edit import Store, _d, _node, _build  # noqa: E402

ID = "1AbCdEfGhIjKlMn"
KEY = "n|formation|s|0|t"


def _chip(share="0", key="gd-abc123", did=ID, name="Syllabus.pdf", words="the syllabus"):
    return ('<a class="note-link" href="https://drive.google.com/file/d/%s/view" target="_blank" rel="noopener noreferrer" data-gdrive="%s" '
            'data-gdrive-id="%s" data-file-name="%s" data-gdrive-share="%s">%s</a>' % (did, key, did, name, share, words))


def _store(chip):
    st = Store(_d())
    t0 = _node(st, "formation")["sections"][0]["t"]
    page, _ = clean_linked_markup(t0, {})
    st.edits = {"v": 1, "ops": {KEY: {"b": page, "v": page + " See " + chip + ".", "t": 1}}}
    return st


def test_the_chip_folds_to_a_reference_with_no_lookup(monkeypatch):
    import alto.edits as E
    monkeypatch.setattr(E, "find_file", lambda *a, **k: (_ for _ in ()).throw(AssertionError("a Drive chip must never look anything up")))
    st = _store(_chip())
    r = fold(st, "u", "t1")
    assert r["folded"] == 1 and not r.get("files_not_found"), r
    assert st.doc["brief"]["linked_files"] == [{"id": "gd-abc123", "kind": "drive", "drive_id": ID, "name": "Syllabus.pdf", "share": False}]
    assert 'href="src:gd-abc123"' in _node(st, "formation")["sections"][0]["t"]
    assert ID not in _node(st, "formation")["sections"][0]["t"]                    # the address is not stored in the card's words
    assert "local" not in json.dumps(st.doc["brief"]["linked_files"])


def test_folding_again_changes_nothing_and_a_new_share_flag_is_recorded():
    st = _store(_chip())
    fold(st, "u", "t1")
    first = json.dumps(st.doc["brief"]["linked_files"], sort_keys=True)
    st.edits["ops"][KEY].pop("f", None)
    fold(st, "u", "t1")
    assert json.dumps(st.doc["brief"]["linked_files"], sort_keys=True) == first
    st2 = _store(_chip(share="1"))
    fold(st2, "u", "t1")
    assert st2.doc["brief"]["linked_files"][0]["share"] is True
    st.edits["ops"][KEY]["v"] = st.edits["ops"][KEY]["v"].replace('data-gdrive-share="0"', 'data-gdrive-share="1"').replace("Syllabus.pdf", "Renamed")
    st.edits["ops"][KEY].pop("f", None)
    fold(st, "u", "t1")                                                                 # the flag can change later; the stored name stays
    assert st.doc["brief"]["linked_files"] == [{"id": "gd-abc123", "kind": "drive", "drive_id": ID, "name": "Syllabus.pdf", "share": True}]


def test_published_marks_the_edit_done():
    st = _store(_chip())
    fold(st, "u", "t1")
    assert published(st, "u", "t1") == 1
    assert all(o.get("done") for o in st.edits["ops"].values())


def test_a_bad_id_or_key_is_not_a_chip():
    for bad in (_chip(did="short"), _chip(did="has space 12345"), _chip(key="gd-"), _chip(key="file-abcdef12")):
        assert drives_in(bad) == [], bad
    st = _store(_chip(did="short"))
    fold(st, "u", "t1")
    assert not st.doc["brief"].get("linked_files")


def test_the_name_is_cleaned_on_the_way_in():
    got = drives_in(_chip(name="a&lt;b&gt;&quot;c" + "n" * 300))
    assert len(got[0]["name"]) <= 200 and "<" not in got[0]["name"] and '"' not in got[0]["name"]


def test_the_page_markup_goes_back_to_the_stored_reference():
    assert page_to_source(_chip()) == '<a href="src:gd-abc123">the syllabus</a>'


def test_the_folded_draft_builds_a_chip_with_the_address_made_from_the_id():
    st = _store(_chip(share="1"))
    fold(st, "u", "t1")
    html, rep = _build(st)
    assert "https://drive.google.com/file/d/%s/view" % ID in html
    assert 'data-gdrive="gd-abc123"' in html and 'data-gdrive-share="1"' in html
    assert not [w for w in rep["warnings"] if "gd-abc123" in w]
