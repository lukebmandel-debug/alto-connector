"""Ink-saver print of an outline and of a horizontal timeline leaves out the chips that show only a glyph/icon/colour (Luke 2026-11-28:
"leave out the subchips that don't have text, so in Civ pro that would mean only including Rules/USC section/cases"). A chip stays when
it carries text (a case, a Rule, a U.S.C. section: an axis that names its values); the entity dots and icon-only axis values go.
A case's letter/★ badge stays with its chip. Screen view and the non-ink print are not touched. WebKit; a made-up board."""
import copy, json, sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import lanes_print_fixture as lf  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402

try:
    from playwright import sync_api as pw
    import phone_matrix as pm
    pm._playwright()
except Exception:
    pw = None

ROOT = Path(__file__).resolve().parent.parent
TEXT = {"Fed. R. Civ. P. 4(h)", "28 U.S.C. § 1367", "Lucy v. Zehmer"}


def _chips(d, kinds):
    """Give the first event a text chip of each kind plus icon-only ones."""
    b = d["brief"]
    b["entities"] = [{"id": "dot1", "name": "Doctrine dot", "role": "r"}, {"id": "dot2", "name": "Entity dot", "role": "r"}]
    b["axes"] = [{"label": "Cases", "singular": "Case", "hide_nav": True, "values": [
                    {"id": "lz", "name": "Lucy v. Zehmer", "labels": ["\u2605", "R"], "summary": "Joke sale of a farm; objective assent binds; reasonable-person test."},
                    {"id": "r4h", "name": "Fed. R. Civ. P. 4(h)", "summary": "unstarred: must not print"}, {"id": "u1367", "name": "28 U.S.C. § 1367"}]},
                 {"label": "Topics", "singular": "Topic", "values": [{"id": "tp1", "name": "Icon only topic"}, {"id": "tp2", "name": "Another icon topic"}]}]
    b["chip_legend"] = [{"label": "R", "meaning": "rule case"}]
    for n in d["nodes"]:
        n["entity_ids"] = []; n["axis1_values"] = []; n["axis2_values"] = []
    n0 = d["nodes"][0]
    n0["entity_ids"] = ["dot1", "dot2"]; n0["axis1_values"] = ["lz", "r4h", "u1367"]; n0["axis2_values"] = ["tp1", "tp2"]
    return d


def _outline():
    return _chips(json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8")), None)


def _lanes():
    return _chips(lf.brief(), None)


@pytest.fixture(scope="module")
def pages():
    if pw is None:
        pytest.skip("no Playwright")
    boards = {"outline": _outline(), "lanes": _lanes()}
    s = pm.serve({k: build_timeline(*load_brief(copy.deepcopy(v)))[0] for k, v in boards.items()}, {}, {})
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception as e:
            pytest.skip(f"no WebKit: {e}")
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        out = {}
        for k in boards:
            pg = ctx.new_page()
            pg.goto(f"http://127.0.0.1:{s.server_address[1]}/{k}.html", wait_until="load")
            pg.wait_for_timeout(3000)
            out[k] = pg
        yield out
        b.close()
    s.shutdown()


def _stage(pg):
    pg.evaluate("window._altoInkUnstage()")
    pg.emulate_media(media="screen")
    assert pg.evaluate("window._altoInkStage()") is True
    pg.evaluate("document.documentElement.classList.add('printing','print-ink')")
    pg.emulate_media(media="print")
    return pg.evaluate("""() => { const first = [...document.querySelectorAll('#alto-ink-host .ink-card')].find(c => c.querySelector('.node-footer'));
      return {chips: [...document.querySelectorAll('#alto-ink-host .node-footer > :not(.footer-sep)')].map(e => e.textContent.replace(/\\s+/g, ' ').trim()),
              empty: [...document.querySelectorAll('#alto-ink-host .node-footer')].filter(f => !f.children.length).length,
              blank: [...document.querySelectorAll('#alto-ink-host .node-footer > :not(.footer-sep)')].filter(e => !e.textContent.trim()).length,
              badges: [...document.querySelectorAll('#alto-ink-host .alto-lbl')].length}; }""")


@pytest.mark.parametrize("fmt", ["outline", "lanes"])
def test_only_chips_with_text_are_printed_in_ink_saver(pages, fmt):
    r = _stage(pages[fmt])
    got = {c.replace("\u2605", "").rstrip("R ").strip() if c.startswith("Lucy") else c for c in r["chips"] if not c.startswith("\u2605 ")}
    assert got == TEXT, r                                   # cases / Rules / U.S.C. stay; entity dots and icon-only axis values go
    assert r["blank"] == 0 and r["empty"] == 0, r           # no empty boxes, no empty footers left behind
    assert r["badges"] >= 1                                 # the case's letter stays with its chip


@pytest.mark.parametrize("fmt", ["outline", "lanes"])
def test_the_screen_page_keeps_every_chip(pages, fmt):
    pg = pages[fmt]
    pg.evaluate("window._altoInkUnstage()"); pg.emulate_media(media="screen")
    n = pg.evaluate("document.querySelectorAll('.node-footer .csym-btn, .node-footer .esym-btn, .node-footer .tsym-btn').length")
    assert n >= 7                                           # 2 dots + 3 text + 2 icon topics on the first card


@pytest.mark.parametrize("fmt", ["outline", "lanes"])
def test_a_starred_chip_with_a_summary_gets_one_line_under_its_chips_and_unstarred_do_not(pages, fmt):
    pg = pages[fmt]
    _stage(pg)
    r = pg.evaluate("""() => [...document.querySelectorAll('#alto-ink-host .ink-sum')].map(e => { const f = e.parentNode.querySelector('.node-footer');
        return {t: e.textContent, after: !f || !!(f.compareDocumentPosition(e) & Node.DOCUMENT_POSITION_FOLLOWING)}; })""")
    assert [x["t"] for x in r] == ["\u2605 Lucy v. Zehmer \u2014 Joke sale of a farm; objective assent binds; reasonable-person test."], r
    assert all(x["after"] for x in r)
