"""Key figures (alto/build/figures.py, figures_edit.py): a Deadlines-style section any page can carry. The brief, the build, folding the page's edits
into the draft (add, edit, reorder, delete), and in a real browser edit mode: adding a block, editing its rows, undo. Existing Deadlines blocks
render unchanged. Never touches a real account."""
import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import detail_extras as dx, figures  # noqa: E402
from alto.build.brief import BriefError  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.manual_edit import jhash  # noqa: E402
from alto.edits import fold, figures_list, _jdump, order_sig, published  # noqa: E402
from tests.test_manual_edit import Store, _build as _build_store, _node, _view  # noqa: E402,F401
from tests.test_photos import site, browser, _open, _detail  # noqa: E402,F401

OUTLINE = ROOT / "samples" / "outline_brief.json"
ROWS = [{"figure": "21 days", "label": "To answer", "detail": "after service", "quote": "within 21 days", "cite": "Rule 12(a)(1)(A)"},
        {"figure": "$75,000", "label": "Amount in controversy"}, {"figure": "3 years", "label": "Limit"}]


def _d(rows=None, h="Key figures"):
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    d["nodes"][0]["sections"].append({"h": h, "t": "", "figures": {"items": copy.deepcopy(rows or ROWS)}})
    return d


def _html(d=None):
    return build_timeline(*load_brief(d or _d()))[0]


def _reg(html):
    return json.loads(re.search(r'window\._ALTO_FG=(.*?);</script>', html).group(1))


def _idx(st):
    return len(_view(st).owner("n", "formation").sections) - 1


# ── the brief and the build ──────────────────────────────────────────────

def test_a_figures_section_reaches_the_page_as_data_and_a_slot_the_page_draws_into_the_deadlines_box():
    html = _html()
    reg = _reg(html)
    key = next(iter(reg))
    assert reg[key]["n"][0] == {"i": "r1", "f": "21 days", "l": "To answer", "d": "after service", "q": "within 21 days", "c": "Rule 12(a)(1)(A)"}
    assert [x["f"] for x in reg[key]["n"]] == ["21 days", "$75,000", "3 years"] and "d" not in reg[key]["n"][1]
    assert f'class="afg-slot" data-afg="{key}" hidden>' in html.replace("\\u003c", "<") or "afg-slot" in html
    assert html.count(".dl-box{display:block") == 1 and dx.DEADLINES_CSS in html           # the same sheet the Deadlines box wears
    assert _html(copy.deepcopy(_d())) == html                                               # repeatable


def test_a_page_without_figures_draws_nothing_and_a_build_never_changes_the_brief():
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    assert _reg(_html(d)) == {}
    d2 = _d()
    before = copy.deepcopy(d2)
    _html(d2)
    assert d2 == before


@pytest.mark.parametrize("bad,why", [
    ({"items": []}, "at least one"),
    ({"items": [{"label": "No figure"}]}, "figure is required"),
    ({"items": [{"figure": "1", "colour": "red"}]}, "a row is"),
    ({"items": [{"figure": "x" * 41}]}, "over the 40"),
    ({"items": [{"figure": "1"}] * 25}, "24-row"),
    ({"rows": []}, "`figures` is"),
])
def test_a_bad_figures_section_is_refused_with_the_reason(bad, why):
    d = _d()
    d["nodes"][0]["sections"][-1]["figures"] = bad
    with pytest.raises(BriefError, match=why):
        _html(d)


def test_a_section_carries_one_of_figures_and_the_others():
    d = _d()
    d["nodes"][0]["sections"][-1]["cards"] = {"cards": [{"front": "a", "back": "b"}]}
    with pytest.raises(BriefError, match="one of"):
        _html(d)


def test_the_words_are_plain_text_and_drawn_escaped():
    html = _html(_d([{"figure": "<b>9</b> days", "label": "<script>x</script>Label"}]))
    key = next(iter(_reg(html)))
    assert _reg(html)[key]["n"][0] == {"i": "r1", "f": "9 days", "l": "xLabel"}


def test_an_existing_deadlines_block_is_untouched_and_carries_its_sheet_once():
    from tests.test_deadlines import _doc as dl_doc
    items = [{"period": "21 days", "what": "To answer", "trigger": "after service", "quote": "within 21 days", "cite": "Rule 12(a)"}]
    assert dx.deadlines_html(items) == (
        '<span class="dl-box"><span class="dl-row"><span class="dl-per">21 days</span><span class="dl-tx"><span class="dl-what">To answer</span>'
        '<span class="dl-trg">after service</span><span class="dl-q">within 21 days</span><span class="dl-cite">Rule 12(a)</span></span></span></span>')
    html = build_timeline(*load_brief(dl_doc()))[0]
    assert html.count(".dl-box{display:block") == 1 and 'id="alto-fg-css"' not in html        # one sheet: the page's own, not a second
    assert "Deadlines" in html and "30 days" in html


def test_the_page_stays_small():
    base = _html(json.loads(OUTLINE.read_text(encoding="utf-8")))
    from alto.build.private_shell import stored_bytes
    assert stored_bytes(_html()) - stored_bytes(base) < 2500


# ── folding the page's edits into the draft ─────────────────────────────

def _store(rows=None):
    return Store(_d(rows))


def test_the_list_round_trips_and_a_reorder_a_new_row_and_a_removal_fold_and_a_rebuilt_page_wears_them():
    st = _store()
    n = _idx(st)
    lst = figures_list(_view(st).owner("n", "formation").sections[n])
    assert lst["n"][1] == {"i": "r2", "f": "$75,000", "l": "Amount in controversy"}
    new = {"n": [lst["n"][2], lst["n"][0], {"i": "r9", "f": "12", "l": "Jurors", "c": "Rule 48"}]}       # 2nd row removed, rest reordered, one added
    st.edits = {"v": 1, "ops": {"fg|n-formation-%d|figs" % n: {"b": jhash(_jdump(lst)), "v": new, "t": 5}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and r["folded"] == 1, r
    got = _node(st, "formation")["sections"][n]["figures"]["items"]
    assert [x["figure"] for x in got] == ["3 years", "21 days", "12"] and got[2] == {"id": "r9", "figure": "12", "label": "Jurors", "cite": "Rule 48"}
    reg = _reg(_build_store(st)[0])
    assert [x["f"] for x in reg["n-formation-%d" % n]["n"]] == ["3 years", "21 days", "12"]
    assert fold(st, "u", "t1")["folded"] == 0                                                             # folded once, and no more
    assert published(st, "u", "t1") == 1


def test_a_list_made_against_another_page_is_a_conflict_and_a_list_with_no_figure_is_too():
    st = _store()
    n = _idx(st)
    st.edits = {"v": 1, "ops": {"fg|n-formation-%d|figs" % n: {"b": "deadbeef", "v": {"n": [{"i": "a", "f": "1"}]}, "t": 1}}}
    assert fold(st, "u", "t1")["conflicts"] == ["fg|n-formation-%d|figs" % n]
    st = _store()
    lst = figures_list(_view(st).owner("n", "formation").sections[n])
    st.edits = {"v": 1, "ops": {"fg|n-formation-%d|figs" % n: {"b": jhash(_jdump(lst)), "v": {"n": [{"i": "a", "f": " "}]}, "t": 1}}}
    assert fold(st, "u", "t1")["conflicts"] == ["fg|n-formation-%d|figs" % n]


def test_a_new_figures_section_folds_with_its_name_and_rows_and_an_empty_one_leaves_no_section():
    st = _store()
    sig = order_sig(_view(st).owner("n", "formation"))
    cur = [str(j) for j in range(len(_node(st, "formation")["sections"]))]
    st.edits = {"v": 1, "ops": {
        "n|formation|order": {"b": sig, "v": cur + ["new-fg1fg1", "new-fg2fg2"], "t": 1},
        "n|formation|s|new-fg1fg1|h": {"b": "", "v": "Deadlines", "t": 2},
        "fg|n-formation-new-fg1fg1|figs": {"b": "new", "v": {"n": [{"i": "r1", "f": "21 days", "l": "Answer"}, {"i": "r2", "f": "$5", "l": "Fee", "q": "five dollars"}]}, "t": 3},
        "n|formation|s|new-fg2fg2|h": {"b": "", "v": "Nothing yet", "t": 4},
        "fg|n-formation-new-fg2fg2|figs": {"b": "new", "v": {"n": []}, "t": 5}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"], r
    secs = _node(st, "formation")["sections"]
    assert secs[-1]["h"] == "Deadlines" and [x["figure"] for x in secs[-1]["figures"]["items"]] == ["21 days", "$5"]
    assert [s["h"] for s in secs].count("Nothing yet") == 0
    _build_store(st)


# ── the page, in a real browser: edit mode ───────────────────────────────

def _boxes(pg):
    return pg.evaluate("""[...document.querySelectorAll('#detail-content .dl-box.afg')].map(b => [...b.querySelectorAll('.dl-row')].map(r => [
      r.querySelector('.dl-per').textContent, (r.querySelector('.dl-what')||{}).textContent||'', (r.querySelector('.dl-trg')||{}).textContent||'',
      (r.querySelector('.dl-q')||{}).textContent||'', (r.querySelector('.dl-cite')||{}).textContent||'']))""")


def _heads(pg):
    return pg.evaluate("[...document.querySelectorAll('#detail-content .detail-section > h3')].map(h => h.textContent.trim())")


def _fgkeys(pg):
    return [k for k in pg.evaluate("Object.keys(window.__edits.ops)") if k.startswith("fg|")]


def test_a_built_figures_section_draws_as_the_deadlines_box(browser, site):
    _b, root = site
    (root / "fig.html").write_text(_html(), encoding="utf-8")
    pg = _open(browser, site, page="fig")
    _detail(pg)
    assert _boxes(pg) == [[["21 days", "To answer", "after service", "within 21 days", "Rule 12(a)(1)(A)"], ["$75,000", "Amount in controversy", "", "", ""], ["3 years", "Limit", "", "", ""]]]
    assert pg.evaluate("document.querySelectorAll('#detail-content .afg-slot').length") == 0
    big = pg.evaluate("parseFloat(getComputedStyle(document.querySelector('.dl-per')).fontSize) > 1.8 * parseFloat(getComputedStyle(document.querySelector('.dl-what')).fontSize)")
    assert big and not pg.errs, pg.errs
    pg.context.close()


def test_edit_mode_adds_a_block_edits_its_rows_reorders_removes_and_undoes(browser, site):
    _b, root = site
    (root / "plain.html").write_text(_html(json.loads(OUTLINE.read_text(encoding="utf-8"))), encoding="utf-8")
    pg = _open(browser, site, page="plain", edit=True)
    _detail(pg)
    n0 = len(_heads(pg))
    pg.click("#detail-content .aed-add >> nth=-1")
    pg.click("#aed-kinds button[data-k=figures]")
    pg.wait_for_selector("#aed-study.aed-fig .afe-f", timeout=8000)
    pg.fill("#aed-study .afe-f >> nth=0", "21 days")
    pg.fill("#aed-study .afe-l >> nth=0", "To answer")
    pg.fill("#aed-study .afe-d >> nth=0", "after service")
    pg.fill("#aed-study .as-x >> nth=0", "within 21 days")
    pg.fill("#aed-study .afe-c >> nth=0", "Rule 12(a)(1)(A)")
    pg.click("#aed-study .as-add")
    pg.fill("#aed-study .afe-f >> nth=1", "$75,000")
    pg.fill("#aed-study .afe-l >> nth=1", "Amount")
    pg.click("#aed-study .as-add")
    pg.fill("#aed-study .afe-f >> nth=2", "12")
    pg.fill("#aed-study .afe-l >> nth=2", "Jurors")
    pg.click("#aed-study .as-item >> nth=2 >> .as-tools button >> nth=0")                     # move row 3 up
    pg.fill("#aed-study input[type=text] >> nth=0", "Limits")                                  # the block's name
    pg.click("#aed-study .as-save")
    pg.wait_for_timeout(900)
    assert len(_heads(pg)) == n0 + 1 and "Limits" in _heads(pg)
    assert [r[0] for r in _boxes(pg)[0]] == ["21 days", "12", "$75,000"]
    assert len(_fgkeys(pg)) == 1
    # edit: remove the middle row, change a figure
    pg.click(".aed-fg[data-fk]")
    pg.wait_for_selector("#aed-study .afe-f")
    pg.click("#aed-study .as-item >> nth=1 >> .as-tools button >> nth=2")
    pg.fill("#aed-study .afe-f >> nth=1", "$80,000")
    pg.click("#aed-study .as-save")
    pg.wait_for_timeout(700)
    assert [r[0] for r in _boxes(pg)[0]] == ["21 days", "$80,000"]
    op = pg.evaluate("window.__edits.ops['%s'].v" % _fgkeys(pg)[0])
    assert [x["f"] for x in op["n"]] == ["21 days", "$80,000"] and op["n"][0]["c"] == "Rule 12(a)(1)(A)"
    # undo the edit, then the add
    pg.keyboard.press("Control+z")
    pg.wait_for_timeout(700)
    assert [r[0] for r in _boxes(pg)[0]] == ["21 days", "12", "$75,000"]
    assert not pg.errs, pg.errs
    pg.context.close()


def test_cancelling_a_new_block_takes_it_away_again(browser, site):
    _b, root = site
    pg = _open(browser, site, page="plain", edit=True)
    _detail(pg)
    n0 = len(_heads(pg))
    pg.click("#detail-content .aed-add >> nth=-1")
    pg.click("#aed-kinds button[data-k=figures]")
    pg.wait_for_selector("#aed-study.aed-fig .afe-f", timeout=8000)
    pg.click("#aed-study .as-save")                                                                # nothing typed: refused, still open
    assert "at least one figure" in pg.inner_text("#aed-study .as-err")
    pg.click("#aed-study .as-foot button >> nth=0")                                                # Cancel
    pg.wait_for_timeout(700)
    assert len(_heads(pg)) == n0 and pg.evaluate("document.querySelectorAll('.dl-box').length") == 0
    pg.context.close()


def test_the_block_wears_each_look_the_phone_and_the_ink_saver_print_like_the_deadlines_box(browser, site):
    _b, root = site
    (root / "fig.html").write_text(_html(), encoding="utf-8")
    pg = _open(browser, site, page="fig")
    _detail(pg)
    css = "(p) => { const b = document.querySelector('.dl-box.afg'), c = getComputedStyle(b); return [c.borderTopColor, c.borderTopWidth, c.borderTopLeftRadius, getComputedStyle(b.querySelector('.dl-per')).textTransform]; }"
    classic = pg.evaluate(css)
    assert classic[1] == "3px" and classic[2] != "0px"
    pg.evaluate("window._altoStyle.set('retro')")
    pg.wait_for_timeout(1200)
    _detail(pg)
    assert pg.evaluate(css) == ["rgb(217, 174, 85)", "2px", "0px", "uppercase"]                  # Retro's gold square box
    pg.evaluate("window._altoStyle.set('holo')")
    pg.wait_for_timeout(1200)
    _detail(pg)
    holo = pg.evaluate(css)
    assert holo[1] == "1px" and holo[2] == "0px"
    pg.evaluate("window._altoStyle.set('classic')")
    pg.emulate_media(media="print")
    assert pg.evaluate(css)[0] == "rgb(0, 0, 0)"                                                 # the ink-saver sheet: black on white, no fill
    pg.context.close()
    pg = _open(browser, site, page="fig", mobile=True)
    pg.evaluate("showDetail('node','formation')")
    pg.wait_for_timeout(900)
    cols = pg.evaluate("getComputedStyle(document.querySelector('.dl-row')).gridTemplateColumns.split(' ').length")
    assert cols == 1 and not pg.errs, pg.errs                                                    # phone: the figure over its words
    pg.context.close()
