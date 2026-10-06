"""Authorities added on a detail page: cases, statutes, Restatement sections
and the list sections (Cases, Authorities, Sources…) — the page side
(alto/build/manual_edit.py) and the fold (alto/edits.py). Folding through the
MCP tool is in tests/test_mcp_flow.py."""
import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.edits import _authority_fields, fold  # noqa: E402
from test_manual_edit import Store, _build, _d, _node  # noqa: E402


def _grouped():
    d = _d()
    d["brief"]["axes"].append({"label": "Statutes & Rules", "singular": "Section", "hide_nav": True, "values": [
        {"id": "frcp-4", "name": "Fed. R. Civ. P. 4", "group": "Federal Rules", "sections": [{"h": "Rule", "t": "x"}]},
        {"id": "usc-1367", "name": "28 U.S.C. § 1367", "group": "28 U.S.C.", "sections": [{"h": "Rule", "t": "y"}]},
        {"id": "loose", "name": "A loose one", "sections": [{"h": "Rule", "t": "z"}]}]})
    return d


def _edk(html):
    return json.loads(re.search(r"window\._ALTO_EDK=(\{.*?\});</script>", html).group(1).replace("<\\/", "</"))


def test_the_page_says_which_index_lists_there_are_and_which_group_each_joins():
    ix = _edk(build_timeline(*load_brief(_grouped()))[0])["ix"]
    assert ix["env"] == {"r": "env", "g": "", "l": "Cases"}
    assert ix["theme~federal-rules"]["g"] == "Federal Rules" and ix["theme~28-u-s-c"]["g"] == "28 U.S.C."
    assert ix["theme~statutes-rules"] == {"r": "theme", "g": "", "l": "Statutes & Rules"}      # the ungrouped ones
    assert _edk(build_timeline(*load_brief(_d()))[0])["ix"] == {"env": {"r": "env", "g": "", "l": "Cases"}}


def test_an_axis_that_is_not_hidden_has_no_index_to_add_to():
    d = _d()
    d["brief"]["axes"][0]["hide_nav"] = False
    for v in d["brief"]["axes"][0]["values"]:
        v["name"] = v["name"].replace("'", "")           # (an apostrophe in a nav-chip name breaks a build)
    assert _edk(build_timeline(*load_brief(d))[0])["ix"] == {}


def test_the_add_menu_offers_lists_of_cases_and_authorities():
    html = build_timeline(*load_brief(_d()))[0]
    for label in ("['cases', 'Cases'", "['authorities', 'Authorities'", "askForm(", "#aed-form"):
        assert label in html, label


def test_what_a_case_carries_is_written_as_text_and_a_checked_link():
    f = _authority_fields({"cite": "1 U.S. <b>1</b>", "h": "Holding", "t": "A & B <script>x</script>",
                           "link": "https://example.com/a?b=1&c=2", "grp": "28 U.S.C."})
    assert f["cite"] == {"note": "1 U.S. 1", "short": "1 U.S. 1"}
    assert f["sections"][0] == {"h": "Holding", "t": "A &amp; B x"}
    assert f["sections"][1]["h"] == "Link" and 'href="https://example.com/a?b=1&amp;c=2"' in f["sections"][1]["t"]
    assert f["group"] == "28 U.S.C."
    for bad in ("javascript:alert(1)", "ftp://x.y/z", "https://a b.c", "//x.y", 'https://x.y/"onclick="x'):
        assert "sections" not in _authority_fields({"link": bad}), bad
    assert _authority_fields({"t": "note"})["sections"][0]["h"] == "Notes"       # no sisters' heading known
    assert _authority_fields({}) == {}


def test_a_case_with_a_citation_only_or_a_link_only_builds():
    st = Store(_grouped())
    st.edits = {"v": 1, "ops": {
        "ne|env|just-cite": {"b": None, "t": 1, "v": {"name": "Just Cite", "cite": "9 U.S. 9"}},
        "ne|env|just-link": {"b": None, "t": 1, "v": {"name": "Just Link", "link": "https://example.com/l"}},
        "ne|theme|in-group": {"b": None, "t": 1, "v": {"name": "28 U.S.C. § 1441", "grp": "28 U.S.C."}},
        "ne|theme|bad": {"b": None, "t": 1, "v": {"name": "Bad", "grp": "x" * 600, "link": "javascript:alert(1)"}}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and not r["gone"], r
    html, _ = _build(st)
    assert "9 U.S. 9" in html and "https://example.com/l" in html and "javascript:alert" not in html
    cfg = json.loads(html.split("window._ALTO_AXES=", 1)[1].split(";\n", 1)[0])
    assert "in-group" in cfg["theme~28-u-s-c"]["ids"]
    assert "just-cite" in json.dumps(cfg["env"]["cites"]) and cfg["env"]["cites"]["just-cite"] == "9 U.S. 9"


def test_chips_reordered_on_a_page_fold_in_that_order():
    st = Store(_d())
    st.edits = {"v": 1, "ops": {"ch|bargained-exchange|envs": {"b": ["hamer", "kirksey"], "t": 1, "v": ["kirksey", "hamer"]}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"], r
    assert _node(st, "bargained-exchange")["axis1_values"] == ["kirksey", "hamer"]
    html, _ = _build(st)
    assert re.search(r'\[\s*"kirksey",\s*"hamer"\s*\]', html)


# ── in a browser: Chromium, the page's own add controls ─────────────────────

FAKE = ("window.AltoCloud={enabled:true,known:true,user:{uid:'u1'},putEdits:function(t,d){window.__edits=d;return Promise.resolve();},"
        "getEdits:function(){return Promise.resolve(window.__edits||null);},watchEdits:function(){return function(){};}};")


@pytest.fixture()
def edit_page():
    pw = pytest.importorskip("playwright.sync_api")
    html = build_timeline(*load_brief(_d()))[0]
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:                       # no browser downloaded
            pytest.skip(f"no Chromium: {e}")
        ctx = b.new_context(viewport={"width": 1400, "height": 900})
        ctx.add_init_script(FAKE)
        pg = ctx.new_page()
        pg.route("http://alto.test/**", lambda r: r.fulfill(
            status=200, content_type="text/html", body=html) if r.request.url.endswith("page.html")
            else r.fulfill(status=404, body=""))
        pg.goto("http://alto.test/page.html")
        pg.wait_for_timeout(1200)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.evaluate("window._altoManual.enter()")
        pg.wait_for_timeout(200)
        yield pg, errs
        b.close()


def _fill(pg, **kw):
    for k, v in kw.items():
        pg.fill(f"#aed-form [data-f={k}]", v)


def test_a_case_added_on_the_index_page_is_laid_over_the_page_and_survives_a_reload(edit_page):
    pg, errs = edit_page
    pg.evaluate("showAxisIndex('env')")
    pg.wait_for_timeout(400)
    assert pg.inner_text(".aed-ixadd") == "+ Add a case to Cases"
    pg.click(".aed-ixadd")
    _fill(pg, name="Raffles v. Wichelhaus", cite="159 Eng. Rep. 375 (1864)", t="Two ships named Peerless.", link="https://example.com/r")
    assert pg.input_value("#aed-form [data-f=attach]") == ""
    pg.click("#aed-form .ab-ok")
    pg.wait_for_timeout(500)
    row = pg.inner_text("#detail-content .doc-row:has-text('Raffles')")
    assert "159 Eng. Rep. 375 (1864)" in row and "Two ships named Peerless." in row     # as the others: name · cite, then the note
    ops = pg.evaluate("window._altoManual.ops()")
    assert ops["ne|env|raffles-v-wichelhaus"]["v"]["h"] == "Holding"                  # the heading the other cases use
    pg.evaluate("showDetail('env','raffles-v-wichelhaus')")
    pg.wait_for_timeout(300)
    txt = pg.inner_text("#detail-content")
    assert "CITATION" in txt.upper() and "Two ships named Peerless." in txt
    # undo takes it all away, redo brings it back
    pg.evaluate("window._altoManual.undo()")
    pg.evaluate("showAxisIndex('env')")
    pg.wait_for_timeout(300)
    assert "Raffles" not in pg.inner_text("#detail-content")
    pg.evaluate("window._altoManual.redo()")
    pg.wait_for_timeout(300)
    pg.reload()
    pg.wait_for_timeout(1200)
    pg.evaluate("showAxisIndex('env')")
    pg.wait_for_timeout(300)
    assert "Raffles v. Wichelhaus" in pg.inner_text("#detail-content")
    assert errs == []


def test_a_list_made_from_the_add_menu_takes_entries_that_move_and_go(edit_page):
    pg, errs = edit_page
    pg.evaluate("showDetail('node','offer')")
    pg.wait_for_timeout(400)
    pg.click("[data-x=addsec]")
    pg.click("#aed-kinds button[data-k=cases]")
    _fill(pg, name="Lucy v. Zehmer", cite="84 S.E.2d 516 (Va. 1954)", t="Objective theory.", link="https://example.com/l")
    pg.click("#aed-form .ab-ok")
    pg.wait_for_timeout(400)
    pg.click(".aed-lisadd")
    _fill(pg, name="Hamer v. Sidway", cite="27 N.E. 256 (N.Y. 1891)")
    pg.click("#aed-form .ab-ok")
    pg.wait_for_timeout(400)
    names = lambda: pg.evaluate("Array.from(document.querySelectorAll('.detail-section ul li')).map(l=>l.firstElementChild.textContent)")  # noqa: E731
    assert names() == ["Lucy v. Zehmer", "Hamer v. Sidway"]
    t = pg.evaluate("Object.values(window._altoManual.ops()).filter(o=>typeof o.v==='string'&&o.v.indexOf('<ul>')===0)[0].v")
    assert t.startswith("<ul><li><a class=\"note-link\" href=\"https://example.com/l\"") and "84 S.E.2d 516 (Va. 1954) — Objective theory.</li>" in t
    assert "<li><i>Hamer v. Sidway</i>, 27 N.E. 256 (N.Y. 1891)</li>" in t                 # the first entry's format
    pg.evaluate("document.querySelectorAll('.aed-lic')[1].querySelector('[data-x=up]').click()")
    pg.wait_for_timeout(300)
    assert names() == ["Hamer v. Sidway", "Lucy v. Zehmer"]
    pg.evaluate("document.querySelectorAll('.aed-lic')[0].querySelector('[data-x=del]').click()")
    pg.wait_for_timeout(300)
    assert names() == ["Lucy v. Zehmer"]
    assert errs == []


def test_a_heading_that_is_not_a_list_gets_no_entry_controls(edit_page):
    pg, _ = edit_page
    pg.evaluate("showDetail('node','offer')")           # its "Rule" is a paragraph
    pg.wait_for_timeout(400)
    assert pg.evaluate("document.querySelectorAll('.aed-lisadd,.aed-lic').length") == 0
