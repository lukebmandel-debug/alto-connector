"""Flash cards and quizzes inside a page (Section.cards / Section.quiz,
alto/build/study.py): validation, sanitizing, the build, search, folding the
owner's manual edits, and that a page without one is left alone."""
import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build.brief import BriefError  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.fingerprint import _TIMELINE_SOURCES  # noqa: E402
from alto.build.manual_edit import jhash  # noqa: E402
from alto.build.study import check_cards, check_quiz, compact, from_compact  # noqa: E402
from alto.edits import fold, study_list, order_sig, _View  # noqa: E402
from test_manual_edit import Store, _node, _build  # noqa: E402

OUTLINE = ROOT / "samples" / "outline_brief.json"

CARDS = {"label": "Elements", "cards": [
    {"id": "c1", "front": "What is an offer?", "back": "A manifestation of willingness to bargain."},
    {"front": "Acceptance?", "back": "Assent to the terms of the offer."}]}
QUIZ = {"label": "Formation", "questions": [
    {"id": "q1", "q": "Which is judged objectively?", "choices": ["Assent", "Damages", "Venue"], "answer": 0,
     "explain": "Outward expression, not secret intent."},
    {"q": "Which are elements? (all that apply)", "choices": ["Offer", "Acceptance", "Notary"], "answer": [0, 1]}]}


def _d(cards=None, quiz=None):
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    if cards:
        d["nodes"][0]["sections"].append({"h": "Flash cards", "t": "Flip these.", "cards": copy.deepcopy(cards)})
    if quiz:
        d["nodes"][0]["sections"].append({"h": "Quiz", "t": "", "quiz": copy.deepcopy(quiz)})
    return d


def _b(d):
    return build_timeline(*load_brief(d))


def _data(html):
    m = re.search(r'<script id="alto-st-data">window._ALTO_ST=(.*?);</script>', html)
    return json.loads(m.group(1).replace("<\\/", "</"))


# ── validation ──────────────────────────────────────────────────────────────

def test_good_cards_and_quizzes_pass():
    check_cards(CARDS, "x")
    check_quiz(QUIZ, "x")


@pytest.mark.parametrize("bad,msg", [
    ({"cards": []}, "non-empty"),
    ({"cards": [{"front": "a"}]}, "back"),
    ({"cards": [{"front": "a", "back": "b", "x": 1}]}, "unknown key"),
    ({"cards": [{"front": "a", "back": "b"}], "nope": 1}, "unknown key"),
    ({"cards": [{"id": "A B", "front": "a", "back": "b"}]}, "slug"),
    ({"cards": [{"id": "a", "front": "a", "back": "b"}, {"id": "a", "front": "c", "back": "d"}]}, "twice"),
    ({"cards": [{"front": "a", "back": "b"}], "shuffle": "yes"}, "shuffle"),
])
def test_bad_cards_are_refused_with_a_helpful_message(bad, msg):
    with pytest.raises(BriefError, match=msg):
        check_cards(bad, "node x section 1")


@pytest.mark.parametrize("bad,msg", [
    ({"questions": []}, "non-empty"),
    ({"questions": [{"q": "?", "choices": ["a"], "answer": 0}]}, "choices"),
    ({"questions": [{"q": "?", "choices": ["a", "b"], "answer": 2}]}, "answer"),
    ({"questions": [{"q": "?", "choices": ["a", "b"], "answer": -1}]}, "answer"),
    ({"questions": [{"q": "?", "choices": ["a", "b"], "answer": []}]}, "answer"),
    ({"questions": [{"q": "?", "choices": ["a", "b"], "answer": [0, 0]}]}, "answer"),
    ({"questions": [{"q": "?", "choices": ["a", "b"], "answer": [0, 1]}]}, "wrong choice"),
    ({"questions": [{"q": "?", "choices": ["a", "A"], "answer": 0}]}, "repeats"),
    ({"questions": [{"q": "?", "choices": ["a", ""], "answer": 0}]}, "empty"),
    ({"questions": [{"q": "", "choices": ["a", "b"], "answer": 0}]}, "question"),
    ({"questions": [{"q": "?", "choices": ["a", "b"], "answer": "a"}]}, "answer"),
    ({"questions": [{"q": "?", "choices": ["a", "b"], "answer": True}]}, "answer"),
    ({"questions": [{"q": "?", "choices": list("abcdefghi"), "answer": 0}]}, "choices"),
    ({"questions": [{"q": "?", "choices": ["a", "b"], "answer": 0, "hint": "x"}]}, "unknown key"),
])
def test_bad_quizzes_are_refused_with_a_helpful_message(bad, msg):
    with pytest.raises(BriefError, match=msg):
        check_quiz(bad, "node x section 1")


def test_the_build_refuses_a_bad_quiz_and_a_section_with_two_kinds():
    q = copy.deepcopy(QUIZ)
    q["questions"][0]["answer"] = 9
    with pytest.raises(BriefError, match="answer"):
        _b(_d(quiz=q))
    d = _d(quiz=QUIZ)
    d["nodes"][0]["sections"][-1]["cards"] = copy.deepcopy(CARDS)
    with pytest.raises(BriefError, match="one of"):
        _b(d)


# ── the build ───────────────────────────────────────────────────────────────

def test_a_page_without_one_has_an_empty_registry_and_no_slot():
    html, _ = _b(_d())
    assert _data(html) == {}
    assert 'class="ast-slot"' not in html and "data-ast=" not in html.split('id="alto-st"')[0]


def test_cards_and_a_quiz_get_slots_data_and_search_words():
    html, rep = _b(_d(CARDS, QUIZ))
    data = _data(html)
    assert sorted(data) == ["n-formation-1", "n-formation-2"]
    c, q = data["n-formation-1"], data["n-formation-2"]
    assert c["k"] == "c" and c["lab"] == "Elements" and [x["i"] for x in c["n"]] == ["c1", "c2"]   # c2 was given a slug
    assert q["k"] == "q" and q["n"][0]["a"] == 0 and q["n"][1]["a"] == [0, 1] and q["n"][0]["x"].startswith("Outward")
    assert 'data-ast="n-formation-1"' in html and 'data-ast="n-formation-2"' in html
    # the words are in the section's text (hidden), so the page's search finds them
    assert "Outward expression" in html and "manifestation of willingness" in html
    assert not any("study" in w.lower() for w in rep["warnings"])


def test_a_quiz_with_no_text_still_shows_its_section():
    html, _ = _b(_d(quiz=QUIZ))
    assert 'data-ast="n-formation-1"' in html


def test_all_text_is_plain_and_the_stored_dicts_are_untouched():
    d = _d(CARDS, QUIZ)
    d["nodes"][0]["sections"][1]["cards"]["cards"][0]["front"] = 'Offer? <script>alert(1)</script><b>x</b>'
    d["nodes"][0]["sections"][2]["quiz"]["questions"][0]["choices"][1] = '<img src=x onerror=alert(1)>Damages'
    before = json.dumps(d, sort_keys=True)
    html, _ = _b(d)
    assert json.dumps(d, sort_keys=True) == before
    data = _data(html)
    assert data["n-formation-1"]["n"][0]["f"] == "Offer? alert(1)x"
    assert data["n-formation-2"]["n"][0]["c"][1] == "Damages"
    assert "<script>alert(1)" not in html and "onerror=alert" not in html


def test_other_pages_carry_the_same_page_as_before():
    """A page with no flash cards or quiz is the page it was: its sections
    are untouched, and the only addition is the (empty) reader."""
    plain, _ = _b(_d())
    withs, _ = _b(_d(CARDS, QUIZ))
    cut = lambda h: re.sub(r'<script id="alto-st-data">.*?</script>', "", h, flags=re.S)  # noqa: E731
    a, b = cut(plain), cut(withs)
    assert len(b) > len(a)
    # every section's markup in the plain build is in the other (the new ones are extra)
    for m in re.findall(r"Offer \+ acceptance \+ consideration[^\"]{0,40}", a):
        assert m in b


def test_it_is_stamped_in_the_page_fingerprint():
    assert "study.py" in _TIMELINE_SOURCES and "study_edit.py" in _TIMELINE_SOURCES


def test_entity_and_axis_value_pages_can_carry_them_too():
    d = _d()
    d["brief"]["entities"][0].setdefault("sections", []).append({"h": "Quiz", "t": "", "quiz": copy.deepcopy(QUIZ)})
    ax = d["brief"]["axes"][0]
    ax["values"][0].setdefault("sections", []).append({"h": "Cards", "t": "", "cards": copy.deepcopy(CARDS)})
    html, _ = _b(d)
    keys = list(_data(html))
    assert any(k.startswith("c-") for k in keys) and any(k.startswith("a0-") for k in keys)


def test_the_progress_key_is_the_pages_own_highlight_key():
    html, _ = _b(_d(CARDS))
    assert "KEY = 'alto-hl-contracts-outline-st'" in html


# ── the page the owner edits ────────────────────────────────────────────────

def _view(st):
    return _View(st.doc, st.nodes, st.conns)


def _sig(v):
    return jhash(json.dumps(v, ensure_ascii=False, separators=(",", ":")))


def test_an_edited_quiz_folds_into_the_draft():
    st = Store(_d(CARDS, QUIZ))
    lst = study_list(_view(st).owner("n", "formation").sections[2])
    new = copy.deepcopy(lst)
    new["n"][0]["q"] = "Which is judged by outward expression?"
    new["n"][0]["c"].append("Notice")
    new["n"][1]["c"].append("Venue")
    new["n"][1]["a"] = [0, 1, 2]
    new["n"].append({"i": "q-new1", "q": "Consideration is...", "c": ["A gift", "A bargained-for exchange"], "a": 1, "x": "Bargained for."})
    st.edits = {"v": 1, "ops": {"sd|n-formation-2|study": {"b": _sig(lst), "v": new, "t": 1}}}
    r = fold(st, "u", "t1")
    assert r["folded"] == 1 and not r["conflicts"], r
    qz = _node(st, "formation")["sections"][2]["quiz"]
    assert qz["label"] == "Formation"
    assert qz["questions"][0]["q"] == "Which is judged by outward expression?" and qz["questions"][0]["choices"][-1] == "Notice"
    assert qz["questions"][1]["answer"] == [0, 1, 2]
    assert qz["questions"][2] == {"id": "q-new1", "q": "Consideration is...", "choices": ["A gift", "A bargained-for exchange"],
                                  "answer": 1, "explain": "Bargained for."}
    html, _ = _build(st)
    assert "Consideration is..." in html
    assert fold(st, "u", "t1")["folded"] == 0                       # built again: nothing more to do


def test_edited_cards_fold_with_their_settings():
    st = Store(_d(CARDS, QUIZ))
    lst = study_list(_view(st).owner("n", "formation").sections[1])
    new = copy.deepcopy(lst)
    new["n"] = new["n"][::-1]
    new["sh"] = True
    new["lab"] = "Renamed"
    st.edits = {"v": 1, "ops": {"sd|n-formation-1|study": {"b": _sig(lst), "v": new, "t": 1}}}
    assert fold(st, "u", "t1")["folded"] == 1
    c = _node(st, "formation")["sections"][1]["cards"]
    assert c["label"] == "Renamed" and c["shuffle"] is True and [x["id"] for x in c["cards"]] == ["c2", "c1"]


def test_a_quiz_edited_against_another_version_is_a_conflict():
    st = Store(_d(CARDS, QUIZ))
    lst = study_list(_view(st).owner("n", "formation").sections[2])
    new = copy.deepcopy(lst)
    new["lab"] = "Changed"
    st.edits = {"v": 1, "ops": {"sd|n-formation-2|study": {"b": "deadbeef", "v": new, "t": 1}}}
    r = fold(st, "u", "t1")
    assert r["conflicts"] == ["sd|n-formation-2|study"]


def test_a_quiz_that_would_not_build_is_refused_and_cards_never_become_a_quiz():
    st = Store(_d(CARDS, QUIZ))
    lst = study_list(_view(st).owner("n", "formation").sections[2])
    bad = copy.deepcopy(lst)
    bad["n"][0]["a"] = 7
    st.edits = {"v": 1, "ops": {"sd|n-formation-2|study": {"b": _sig(lst), "v": bad, "t": 1}}}
    assert fold(st, "u", "t1")["conflicts"] == ["sd|n-formation-2|study"]
    assert _node(st, "formation")["sections"][2]["quiz"]["questions"][0]["answer"] == 0
    cl = study_list(_view(st).owner("n", "formation").sections[1])
    st.edits = {"v": 1, "ops": {"sd|n-formation-1|study": {"b": _sig(cl), "v": lst, "t": 1}}}
    assert fold(st, "u", "t1")["conflicts"] == ["sd|n-formation-1|study"]


def test_a_new_quiz_section_made_on_the_page_folds_with_its_questions():
    st = Store(_d())
    sig = order_sig(_view(st).owner("n", "formation"))
    cur = [str(j) for j in range(len(_node(st, "formation")["sections"]))]
    v = {"k": "q", "lab": "My quiz", "n": [{"i": "q1", "q": "Offer?", "c": ["yes", "no"], "a": 0, "x": "Because."}]}
    st.edits = {"v": 1, "ops": {
        "n|formation|order": {"b": sig, "v": cur + ["new-q1q2q3"], "t": 1},
        "n|formation|s|new-q1q2q3|h": {"b": "", "v": "Quiz", "t": 2},
        "sd|n-formation-new-q1q2q3|study": {"b": "new", "v": v, "t": 3}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and not r["gone"] and r["folded"] == 3, r
    sec = _node(st, "formation")["sections"][-1]
    assert sec["h"] == "Quiz" and sec["t"] == "" and sec["quiz"]["label"] == "My quiz"
    assert sec["quiz"]["questions"][0]["explain"] == "Because."
    html, _ = _build(st)
    assert "My quiz" in html and f'data-ast="n-formation-{len(cur)}"' in html


def test_new_cards_section_folds_too_and_a_blank_one_is_not_kept():
    st = Store(_d())
    sig = order_sig(_view(st).owner("n", "formation"))
    cur = [str(j) for j in range(len(_node(st, "formation")["sections"]))]
    v = {"k": "c", "lab": "", "sh": False, "n": [{"i": "c1", "f": "Term", "b": "Meaning"}]}
    st.edits = {"v": 1, "ops": {
        "n|formation|order": {"b": sig, "v": cur + ["new-c1c2c3"], "t": 1},
        "n|formation|s|new-c1c2c3|h": {"b": "", "v": "Flash cards", "t": 2},
        "sd|n-formation-new-c1c2c3|study": {"b": "new", "v": v, "t": 3}}}
    assert fold(st, "u", "t1")["folded"] == 3
    assert _node(st, "formation")["sections"][-1]["cards"]["cards"] == [{"id": "c1", "front": "Term", "back": "Meaning"}]


def test_compact_round_trips_through_from_compact():
    html, _ = _b(_d(CARDS, QUIZ))
    for key, which in (("n-formation-1", "cards"), ("n-formation-2", "quiz")):
        c = _data(html)[key]
        w, stored = from_compact(c)
        assert w == which
    with pytest.raises(BriefError):
        from_compact({"k": "q", "n": [{"i": "a", "q": "?", "c": ["x", "y"], "a": 5}]})


def test_the_pages_manual_edit_script_carries_the_editor_and_the_kinds():
    html, _ = _b(_d())
    for needle in ("openStudyEditor", "kind === 'sd'", "Flash cards", "✎ Edit quiz", "_altoAskClaude", "Suggested: have Claude write this"):
        assert needle in html, needle
