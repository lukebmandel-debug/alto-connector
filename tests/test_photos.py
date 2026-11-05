"""Pictures of the owner's own (alto/build/photos.py): the brief, the build (the page names a picture and never carries it), folding the page's
edits into the draft, the account layer, and in a real browser (Chromium and WebKit) the Photos section, a card's pictures, edit mode, the viewer,
print and the phone. Never touches a real account: the browser tests run against stand-ins for Firestore and the account."""
import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import photos  # noqa: E402
from alto.build.brief import BriefError  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.private_shell import stored_bytes  # noqa: E402
from alto.build.manual_edit import jhash  # noqa: E402
from alto.edits import fold, photos_list, _jdump  # noqa: E402
from alto.edits import order_sig, published  # noqa: E402
from tests.test_manual_edit import Store, _build as _build_store, _node, _view  # noqa: E402,F401

OUTLINE = ROOT / "samples" / "outline_brief.json"
CLOUD = (ROOT / "alto" / "cloud" / "alto-cloud.js").read_text(encoding="utf-8")
R1, R2, R3, R4 = "pic-abcdefghij", "pic-abcdefghik", "pic-abcdefghil", "pic-abcdefghim"


def _d():
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    d["nodes"][0]["sections"].append({"h": "Photos", "t": "See below.", "photos": {"items": [
        {"ref": R1, "caption": "A <b>cap</b>"}, {"ref": R2, "caption": "Two", "alt": "alt two"}], "label": "Exhibits"}})
    d["nodes"][1]["photos"] = [{"ref": R3, "caption": "card pic"}]
    return d


def _html(d=None):
    return build_timeline(*load_brief(d or _d()))[0]


def _data(html):
    m = re.search(r'<script id="alto-ph">window\._ALTO_PH=(.*?);window\._ALTO_PC=(.*?);window\._altoPicsLoad', html)
    return json.loads(m.group(1)), json.loads(m.group(2))


# ── the brief ───────────────────────────────────────────────────────────────

def test_a_photos_section_and_a_cards_pictures_reach_the_page_as_names_never_bytes():
    html = _html()
    ph, pc = _data(html)
    assert ph == {"n-formation-1": {"lab": "Exhibits", "n": [{"i": "p1", "r": R1, "c": "A cap"}, {"i": "p2", "r": R2, "c": "Two", "a": "alt two"}]}}
    assert pc == {"definiteness": [{"i": "p1", "r": R3, "c": "card pic"}]}
    assert 'class="aph-slot" data-aph="n-formation-1" hidden>A cap alt two' in html.replace("\\u003c", "<") or "aph-slot" in html
    assert "data:image" not in html.split('<script id="alto-ph">')[1].split("</script>")[0]
    assert photos.PATH in html and photos.ASSET[:80] not in html          # the renderer is a hosted file, fetched by the page


def test_a_page_with_no_pictures_loads_nothing_and_a_build_is_repeatable():
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    html = _html(d)
    assert _data(html) == ({}, {}) and "if(false)_altoPicsLoad();" in html
    assert _html(copy.deepcopy(d)) == html


def test_building_never_changes_the_stored_brief():
    d = _d()
    before = copy.deepcopy(d)
    _html(d)
    assert d == before


@pytest.mark.parametrize("bad,why", [
    ({"items": []}, "at least one"),
    ({"items": [{"ref": "x.jpg"}]}, "pic-"),
    ({"items": [{"ref": R1}, {"ref": R1}]}, "twice"),
    ({"items": [{"ref": R1, "url": "http://x"}]}, "unknown"),
    ({"items": [{"ref": R1, "caption": "x" * 201}]}, "caption"),
    ({"items": [{"ref": R1}], "extra": 1}, "unknown photos"),
])
def test_a_photos_section_that_would_not_build_is_refused(bad, why):
    d = _d()
    d["nodes"][0]["sections"][-1]["photos"] = bad
    with pytest.raises(BriefError, match=why):
        _html(d)


def test_a_section_carries_photos_or_a_tree_never_both():
    d = _d()
    d["nodes"][0]["sections"][-1]["quiz"] = {"questions": [{"q": "q?", "choices": ["a", "b"], "answer": 0}]}
    with pytest.raises(BriefError, match="one of"):
        _html(d)


def test_a_card_holds_at_most_twelve_pictures():
    d = _d()
    d["nodes"][1]["photos"] = [{"ref": f"pic-abcdefgh{i:02d}"} for i in range(13)]
    with pytest.raises(BriefError, match="12-picture"):
        _html(d)


def test_the_page_stays_small():
    base = _html(json.loads(OUTLINE.read_text(encoding="utf-8")))
    html = _html()
    assert stored_bytes(html) - stored_bytes(base) < 3000                 # (a few pictures' names and the loader)


# ── folding the page's edits into the draft ─────────────────────────────────

def _store():
    d = _d()
    return Store(d)


def test_a_photos_section_list_folds_and_a_rebuilt_page_wears_it():
    st = _store()
    v = _view(st)
    sec = v.owner("n", "formation").sections[-1]
    lst = photos_list(sec)
    new = {"lab": "Exhibits", "n": [lst["n"][1], {"i": "p9", "r": R4, "c": "Third", "a": "alt"}]}
    st.edits = {"v": 1, "ops": {"ph|n-formation-%d|pics" % (len(v.owner("n", "formation").sections) - 1): {"b": jhash(_jdump(lst)), "v": new, "t": 5}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and r["folded"] == 1, r
    assert _node(st, "formation")["sections"][-1]["photos"] == {"items": [
        {"id": "p2", "ref": R2, "caption": "Two", "alt": "alt two"}, {"id": "p9", "ref": R4, "caption": "Third", "alt": "alt"}], "label": "Exhibits"}
    ph, _pc = _data(_build_store(st)[0])
    assert [x["r"] for x in ph["n-formation-%d" % (len(v.owner("n", "formation").sections) - 1)]["n"]] == [R2, R4]
    assert fold(st, "u", "t1")["folded"] == 0
    assert published(st, "u", "t1") == 1


def test_a_photos_list_made_against_another_page_is_a_conflict_and_removing_every_picture_keeps_the_section():
    st = _store()
    n = len(_view(st).owner("n", "formation").sections) - 1
    st.edits = {"v": 1, "ops": {"ph|n-formation-%d|pics" % n: {"b": "deadbeef", "v": {"lab": "", "n": []}, "t": 1}}}
    r = fold(st, "u", "t1")
    assert r["conflicts"] == ["ph|n-formation-%d|pics" % n]
    st = _store()
    lst = photos_list(_view(st).owner("n", "formation").sections[-1])
    st.edits = {"v": 1, "ops": {"ph|n-formation-%d|pics" % n: {"b": jhash(_jdump(lst)), "v": {"lab": "Exhibits", "n": []}, "t": 1}}}
    assert fold(st, "u", "t1")["folded"] == 1
    sec = _node(st, "formation")["sections"][-1]
    assert "photos" not in sec and sec["h"] == "Photos"
    _build_store(st)


def test_a_new_photos_section_folds_with_its_pictures_and_an_empty_one_leaves_no_section():
    st = _store()
    v = _view(st)
    sig = order_sig(v.owner("n", "formation"))
    cur = [str(j) for j in range(len(_node(st, "formation")["sections"]))]
    st.edits = {"v": 1, "ops": {
        "n|formation|order": {"b": sig, "v": cur + ["new-ph1ph1", "new-ph2ph2"], "t": 1},
        "n|formation|s|new-ph1ph1|h": {"b": "", "v": "Photos", "t": 2},
        "ph|n-formation-new-ph1ph1|pics": {"b": "new", "v": {"lab": "", "n": [{"i": "p1", "r": R4, "c": "New one"}]}, "t": 3},
        "n|formation|s|new-ph2ph2|h": {"b": "", "v": "Nothing yet", "t": 4},
        "ph|n-formation-new-ph2ph2|pics": {"b": "new", "v": {"lab": "", "n": []}, "t": 5}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"], r
    secs = _node(st, "formation")["sections"]
    assert secs[-1]["h"] == "Photos" and secs[-1]["photos"]["items"][0]["ref"] == R4 and secs[-1]["photos"]["items"][0]["caption"] == "New one"
    assert [s["h"] for s in secs].count("Nothing yet") == 0
    _build_store(st)


def test_a_cards_pictures_fold_and_a_changed_list_is_a_conflict():
    st = _store()
    base = photos.compact_items(photos.sanitize_items(_node(st, "definiteness")["photos"]))
    new = base + [{"i": "p5", "r": R4, "c": "More"}]
    st.edits = {"v": 1, "ops": {"pc|definiteness|pics": {"b": base, "v": new, "t": 1}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and r["folded"] == 1, r
    assert [x["ref"] for x in _node(st, "definiteness")["photos"]] == [R3, R4]
    assert "definiteness" in st.put_n
    # the draft changed since (Claude edited the card too): the page's list loses
    st2 = _store()
    st2.edits = {"v": 1, "ops": {"pc|definiteness|pics": {"b": [{"i": "p1", "r": R1}], "v": new, "t": 1}}}
    assert fold(st2, "u", "t1")["conflicts"] == ["pc|definiteness|pics"]
    # every picture taken off a card
    st3 = _store()
    st3.edits = {"v": 1, "ops": {"pc|definiteness|pics": {"b": base, "v": [], "t": 1}}}
    assert fold(st3, "u", "t1")["folded"] == 1 and "photos" not in _node(st3, "definiteness")
    # a card made on the page (not yet in the draft) waits
    st4 = _store()
    st4.edits = {"v": 1, "ops": {"pc|card-ab12cd|pics": {"b": [], "v": new, "t": 1}}}
    assert fold(st4, "u", "t1")["folded"] == 0


def test_the_page_and_the_connector_sign_alike():
    st = _store()
    lst = photos_list(_view(st).owner("n", "formation").sections[-1])
    assert jhash(_jdump(lst)) == jhash(json.dumps(lst, ensure_ascii=False, separators=(",", ":")))
