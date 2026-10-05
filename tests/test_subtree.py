"""Decision trees inside a page (Section.tree, alto/build/subtree.py)."""
import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.brief import BriefError  # noqa: E402
from alto.build.subtree import check_tree, MAX_TREE_NODES  # noqa: E402

OUTLINE = ROOT / "samples" / "outline_brief.json"

TREE = {"label": "Is there an offer?", "nodes": [
    {"id": "q", "title": "Was a definite promise communicated?", "tag": "Question"},
    {"id": "no", "parent": "q", "edge": "No", "title": "No offer", "tone": "red",
     "text": "An invitation to deal."},
    {"id": "yes", "parent": "q", "edge": "Yes", "title": "Offer", "tone": "green",
     "link": "definiteness",
     "sections": [{"h": "Why", "t": "The terms are <em>definite</em>."}]},
]}


def _d(tree=TREE, t="Follow the answers."):
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    d["nodes"][0]["sections"].append({"h": "Decision tree", "t": t, "tree": copy.deepcopy(tree)})
    return d


def _build(d):
    return build_timeline(*load_brief(d))


def _data(html):
    m = re.search(r'<script id="alto-dt-data">window._ALTO_DT=(.*?);</script>', html)
    return json.loads(m.group(1).replace("<\\/", "</"))


def test_a_page_without_a_tree_is_unchanged():
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    html, _ = _build(d)
    assert '<script id="alto-dt' not in html and '<style id="alto-dt-css">' not in html
    assert '\\u003cspan class="adt-slot"' not in html     # no slot in any page's data


def test_a_tree_section_gets_a_slot_and_its_data():
    html, rep = _build(_d())
    data = _data(html)
    key = "n-formation-1"
    assert list(data) == [key]
    assert f'data-adt="{key}"' in html
    steps = {n["i"]: n for n in data[key]["n"]}
    assert steps["no"]["e"] == "No" and steps["no"]["c"] == "red" and steps["no"]["p"] == "q"
    # the link is resolved to the page it names
    assert steps["yes"]["l"] == ["node", "definiteness"]
    assert steps["yes"]["s"][0]["t"] == "The terms are <em>definite</em>."
    assert data[key]["label"] == "Is there an offer?"
    assert '<script id="alto-dt">' in html and '<style id="alto-dt-css">' in html
    assert not any("tree" in w for w in rep["warnings"])


def test_the_trees_words_are_in_the_page_text_for_search():
    html, _ = _build(_d())
    slot = re.search(r'<span class=\\?"adt-slot\\?"[^>]*>(.*?)</span>',
                     html.replace("\\u003c", "<"))
    assert slot and "Was a definite promise communicated?" in slot.group(1)
    assert "No offer" in slot.group(1)


def test_a_tree_with_no_text_still_shows_its_section():
    html, _ = _build(_d(t=""))
    assert 'data-adt="n-formation-1"' in html


def test_an_unknown_link_is_dropped_with_a_warning():
    tree = copy.deepcopy(TREE)
    tree["nodes"][2]["link"] = "no-such-page"
    html, rep = _build(_d(tree))
    steps = {n["i"]: n for n in _data(html)["n-formation-1"]["n"]}
    assert "l" not in steps["yes"]
    assert any("no-such-page" in w for w in rep["warnings"])


def test_markup_in_card_fields_is_stripped():
    tree = copy.deepcopy(TREE)
    tree["nodes"][0]["title"] = "Offer? <script>alert(1)</script>"
    tree["nodes"][2]["sections"][0]["t"] = 'ok <img src=x onerror="alert(1)">'
    html, _ = _build(_d(tree))
    steps = {n["i"]: n for n in _data(html)["n-formation-1"]["n"]}
    assert "<" not in steps["q"]["t"]
    assert "onerror" not in steps["yes"]["s"][0]["t"]


def test_entity_pages_can_carry_a_tree_too():
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    d["brief"]["entities"][0].setdefault("sections", []).append(
        {"h": "Tree", "t": "", "tree": copy.deepcopy(TREE)})
    html, _ = _build(d)
    assert any(k.startswith("c-") for k in _data(html))


@pytest.mark.parametrize("bad, msg", [
    ({"nodes": []}, "non-empty"),
    ({"nodes": [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}]}, "exactly one step"),
    ({"nodes": [{"id": "a", "title": "A"}, {"id": "b", "title": "B", "parent": "zz"}]}, "not a step"),
    ({"nodes": [{"id": "a", "title": "A"}, {"id": "a", "title": "B", "parent": "a"}]}, "used twice"),
    ({"nodes": [{"id": "a", "title": "A", "tone": "pink"}]}, "tone"),
    ({"nodes": [{"id": "a", "title": ""}]}, "needs a title"),
    ({"nodes": [{"id": "a", "title": "A", "colour": "red"}]}, "unknown key"),
    ({"nodes": [{"id": "a", "title": "A"}], "layout": "radial"}, "layout"),
    ({"nodes": [{"id": "A b", "title": "A"}]}, "slug"),
    ({"nodes": [{"id": f"s{i}", "title": "x", "parent": f"s{i-1}" if i else ""}
                for i in range(12)]}, "levels deep"),
    ({"nodes": [{"id": f"s{i}", "title": "x", "parent": "s0" if i else ""}
                for i in range(MAX_TREE_NODES + 1)]}, "step limit"),
])
def test_bad_trees_are_refused(bad, msg):
    with pytest.raises(BriefError, match=msg):
        check_tree(bad, "node x section 1")


def test_a_cycle_is_refused():
    with pytest.raises(BriefError):
        check_tree({"nodes": [{"id": "r", "title": "R"},
                              {"id": "a", "title": "A", "parent": "b"},
                              {"id": "b", "title": "B", "parent": "a"}]}, "x")


def test_build_refuses_a_bad_tree():
    tree = copy.deepcopy(TREE)
    tree["nodes"][1]["parent"] = "nowhere"
    with pytest.raises(BriefError):
        _build(_d(tree))


def test_the_renderer_ships_only_with_a_tree_and_is_stamped():
    from alto.build.fingerprint import _TIMELINE_SOURCES
    assert "subtree.py" in _TIMELINE_SOURCES


# ── in a real browser (skipped where Playwright has no browser) ──────────────

def test_the_tree_draws_folds_and_opens_in_a_browser(tmp_path):
    pw = pytest.importorskip("playwright.sync_api")
    html, _ = _build(_d())
    f = tmp_path / "page.html"
    f.write_text(html, encoding="utf-8")
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no Chromium: {e}")
        pg = b.new_page(viewport={"width": 1400, "height": 900})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(f.as_uri())
        pg.wait_for_timeout(1000)
        pg.evaluate("showDetail('node','formation')")
        pg.wait_for_timeout(500)
        assert pg.evaluate("document.querySelectorAll('#detail-content .adt').length") == 1
        assert pg.evaluate("document.querySelectorAll('.adt-lines path').length") == 2
        assert pg.evaluate("!!document.querySelector('.adt').closest('p')") is False
        pg.click('.adt-card[data-i="yes"] .adt-t')
        pg.wait_for_timeout(300)
        assert "definite" in pg.evaluate("document.querySelector('.adt-panel').innerText")
        pg.click('.adt-fold[data-fold="q"]')
        pg.wait_for_timeout(200)
        assert pg.evaluate("document.querySelectorAll('.adt-lines path').length") == 0
        pg.click('.adt-card[data-i="q"]')            # no link, no page: nothing happens
        pg.click('.adt-fold[data-fold="q"]')
        pg.click('.adt-card[data-i="yes"] [data-go]')
        pg.wait_for_timeout(300)
        assert pg.evaluate("window._currentDetailId") == "definiteness"
        b.close()
        assert errs == []


def test_building_never_changes_the_stored_tree():
    """load_brief shares the stored node's dicts; a cleaned tree (links
    resolved to [type, id]) once leaked back and broke the next build."""
    d = _d()
    before = copy.deepcopy(d)
    first, _ = _build(d)
    assert d == before
    second, _ = _build(d)
    assert _data(first) == _data(second)
