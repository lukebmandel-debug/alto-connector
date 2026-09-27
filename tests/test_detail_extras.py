"""The Torts engine issue log (ALTO-001..016), ported from hand patches on the
built page into the builder. Each test names the entry it holds in place."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import load_brief, build_timeline, place  # noqa: E402
from alto.build.brief import validate_brief  # noqa: E402
from alto.build.layout import TREE, outline_flanks, outline_tree  # noqa: E402
from alto.build.estimate import card_height  # noqa: E402
from alto.build import detail_extras as dx  # noqa: E402
from alto.build.single_file import preview  # noqa: E402

OUTLINE = ROOT / "samples" / "outline_brief.json"
LINEAR = ROOT / "samples" / "contracts_brief.json"


def _d(path=OUTLINE):
    return json.loads(path.read_text(encoding="utf-8"))


def _build(d):
    return build_timeline(*load_brief(d))


# ── ALTO-001 ────────────────────────────────────────────────────────────────

def test_a_hub_sits_above_every_child_in_the_hints():
    """The outline tree keeps every hub above its children (a flank shares its
    concept's row; everything else starts below the hub's bottom)."""
    b, nodes, _ = load_brief(_d())
    validate_brief(b)
    place(b, nodes)
    fl = outline_flanks(nodes)
    h = {n.id: card_height(n.desc, n.title, TREE["FLANK_W"] if n.id in fl else 270)
         for n in nodes}
    pos, _, _ = outline_tree(nodes, len(b.acts), h)
    for n in nodes:
        if not n.parent:
            continue
        if n.id in fl:
            assert abs(pos[n.id] - pos[n.parent]) < 0.5, n.id
        else:
            assert pos[n.id] - h[n.id] / 2 >= pos[n.parent] + h[n.parent] / 2, n.id


def test_the_browser_runs_the_tree_only_on_outlines():
    html, _ = _build(_d())
    assert "if(window._altoTree) window._altoTree(positions, nodeHeights);" in html  # hook
    assert "window._altoTree = function" in html
    linear, _ = _build(_d(LINEAR))
    assert "if(window._altoTree) window._altoTree(positions, nodeHeights);" in linear  # guard only
    assert "window._altoTree = function" not in linear
    assert "_altoHubsAbove" not in html + linear          # superseded by the tree


# ── ALTO-002/003/004 ────────────────────────────────────────────────────────

def test_outline_element_page_is_a_tree_and_links_its_relations():
    html, _ = _build(_d())
    assert "function _altoElementTree(members)" in html
    assert "_altoElementTree(members) : meta+rows" in html
    # "How they connect" in an outline: links, and only labelled relations
    assert "c[2]!=='spine'&&rl[c[2]]" in html
    assert "<a class=\"hc-link\" data-goto=\"'+c[0]+'\">" in html


def test_outline_badge_names_the_nodes_own_kind():
    html, _ = _build(_d())
    assert "${n.tag||'" in html                      # desktop
    assert "'+(nd.tag||'" in html                    # mobile peek
    assert "window._altoNodeName = function" in html
    assert "name = window._altoNodeName ? _altoNodeName(n) : n.title;" in html


# ── ALTO-005 ────────────────────────────────────────────────────────────────

def test_an_outline_with_no_overview_gets_one_from_its_own_text():
    d = _d()
    d["brief"]["overview_html"] = ""
    html, rep = _build(d)
    inner = html.split('<div id="summary-inner">', 1)[1][:4000]
    first = d["nodes"][0]
    assert f"showDetail('node','{first['id']}')" in inner
    assert any("no overview authored" in w for w in rep["warnings"])


# ── ALTO-006 ────────────────────────────────────────────────────────────────

def test_a_hide_nav_axis_gets_an_index_page_and_no_filter_by_default():
    html, _ = _build(_d())
    assert "showAxisIndex('env')" in html
    assert "if(type==='index'&&window._altoAxisIndex) return _altoAxisIndex(id);" in html
    assert "window._ALTO_AXES=" in html
    sections = json.loads(re.search(r"var FILTER_SECTIONS=(\[.*?\]);\n", html).group(1))
    assert "axis1" not in {s["key"] for s in sections}


def test_the_axis_filter_can_be_opted_back_in():
    d = _d()
    d["brief"]["axes"][0]["filter"] = True
    html, _ = _build(d)
    sections = json.loads(re.search(r"var FILTER_SECTIONS=(\[.*?\]);\n", html).group(1))
    assert "axis1" in {s["key"] for s in sections}


# ── ALTO-007 ────────────────────────────────────────────────────────────────

def test_chip_label_anchors_to_the_hovered_chips_row():
    html, _ = _build(_d(LINEAR))
    assert "tip.style.top=chip.offsetTop+'px';" in html
    assert "bottom:calc(100% + 8px); z-index:5;" not in html


# ── ALTO-008/009/010: on every page ─────────────────────────────────────────

def _tail_ok(html):
    tail = html[html.rfind("<script>window._ALTO_AUTOLINK="):]
    for marker in ('id="alto-autolink"', 'id="alto-banner-clearance"', 'id="alto-back-prev-js"'):
        assert marker in tail
    assert tail.index('id="alto-back-prev-js"') > tail.index('id="alto-autolink"')   # outermost
    assert tail.rstrip().endswith("</html>")


def test_detail_extras_ride_at_the_end_of_every_page():
    """Gated to outline/index pages only while private pages were stored
    uncompressed; now they are general, so a plain linear page gets them too."""
    _tail_ok(_build(_d())[0])
    d = _d(LINEAR)
    for ax in d["brief"].get("axes", []):
        ax["hide_nav"] = False
    d["brief"]["mode"] = "linear"
    _tail_ok(_build(d)[0])


def _brief_with(names):
    d = _d()
    d["brief"]["axes"][0]["values"] = [
        {"id": f"c{i}", "name": n} for i, n in enumerate(names)]
    b, _, _ = load_brief({"brief": d["brief"]})
    return b


def test_autolink_short_forms_are_generated_and_ambiguity_is_dropped():
    b = _brief_with(["Vosburg v. Putney", "Davis v. Feinstein",
                     "Davis v. Consolidated Rail Corp.", "Williams v. Hays",
                     "Mohr v. Williams", "The T.J. Hooper",
                     "United States v. Carroll Towing Co."])
    names = dx.autolink_table(b)["names"]
    assert names["Vosburg"] == ["env", "c0"]
    assert "Davis" not in names                           # two cases
    assert "Williams" not in names                        # a party elsewhere
    assert names["T.J. Hooper"] == ["env", "c5"]
    assert names["United States v. Carroll Towing"] == ["env", "c6"]


def test_authored_aliases_link_too():
    d = _d()
    d["brief"]["axes"][0]["values"][0]["aliases"] = ["the Zehmer case"]
    b, _, _ = load_brief({"brief": d["brief"]})
    assert dx.autolink_table(b)["names"]["the Zehmer case"][1] == \
        d["brief"]["axes"][0]["values"][0]["id"]


# ── ALTO-011/012/013/014 ────────────────────────────────────────────────────

def test_source_notes_citations_and_provenance_render_from_the_brief():
    d = _d()
    d["brief"]["source_docs"] = [{"id": "notes", "name": "Contracts notes",
                                  "url": "https://docs.google.com/document/d/x/edit"}]
    root = next(n for n in d["nodes"] if not n.get("parent"))
    root["sources"] = ["notes"]
    ax = d["brief"]["axes"][0]
    ax["cite_link"] = {"label": "Casebook", "url": "https://book.example/{sec}#page-{p}",
                       "sections": {"2": "sec-two"}}
    v = ax["values"][0]
    v["cite"] = {"ch": "Chapter 2 — Formation", "p": "41"}
    v["sections"] = [{"h": "Text", "t": "the rule", "prov": "notes"}]
    html, rep = _build(d)
    assert "https://docs.google.com/document/d/x/edit" in html
    assert "https://book.example/sec-two#page-41" in html
    assert "Casebook" in html
    assert "sec-prov" in html
    assert any("headed like primary text" in w for w in rep["warnings"])
    # a child with no sources of its own inherits the root's
    kid = next(n for n in d["nodes"] if n.get("parent") == root["id"])
    nd = html.split("const NODE_DETAILS=", 1)[1].split("\n};", 1)[0]
    assert f"'{kid['id']}':" in nd and nd.count("Contracts notes") >= 2


def test_non_https_source_urls_are_refused():
    d = _d()
    d["brief"]["source_docs"] = [{"id": "x", "name": "x", "url": "javascript:alert(1)"}]
    with pytest.raises(Exception):
        _build(d)


# ── ALTO-016 ────────────────────────────────────────────────────────────────

def test_preview_saves_through_the_artifact_downloads_capability():
    b, nodes, conns = load_brief(_d())
    html, _ = build_timeline(b, nodes, conns)
    page = preview(b, html)
    assert page.startswith("<title>")
    assert "window.__altoSave=function" in page
    assert "createObjectURL" not in page and "a.download" not in page


def test_external_links_open_in_a_new_tab_and_h2_survives():
    from alto.build.sanitize import clean_linked_markup, clean_overview
    out, _ = clean_linked_markup('<a href="https://docs.google.com/d/x">notes</a>', {})
    assert 'class="note-link" target="_blank" rel="noopener"' in out
    ov, _ = clean_overview("<h2>I. Torts</h2><p>x</p>", set())
    assert "<h2>I. Torts</h2>" in ov


def test_index_chrome_options():
    d = _d()
    d["brief"]["index_label"] = "Authorities"
    ax = d["brief"]["axes"][0]
    ax["nav_label"] = "Cases list"
    ax["index_sections"] = [{"h": "Source", "t": "From the syllabus."}]
    ax["values"][0]["cite"] = {"note": "Not in the table of contents", "short": "not in TOC"}
    html, _ = _build(d)
    assert "Authorities" in html and "Cases list" in html
    cfg = json.loads(html.split("window._ALTO_AXES=", 1)[1].split(";\n", 1)[0])
    assert cfg["env"]["top"][0]["t"] == "From the syllabus."
    assert "not in TOC" in cfg["env"]["cites"].values()


def test_a_story_can_link_its_characters_only():
    d = _d()
    b0 = d["brief"]
    b0["autolink"] = ["char"]
    b0["autolink_overview"] = False
    b0["entities"] = [{"id": "tom", "name": "Tom Reyes"}, {"id": "ada", "name": "Ada Reyes"},
                      {"id": "lin", "name": "Lin Park", "aliases": []},
                      {"id": "hale", "name": "Hale"}]
    b0["axes"][0]["values"] = [{"id": "hq", "name": "Hale House"}, {"id": "ctl", "name": "Control"}]
    b, _, _ = load_brief({"brief": b0})
    t = dx.autolink_table(b)
    assert t["names"]["Lin"] == ["char", "lin"] and t["names"]["Tom"] == ["char", "tom"]
    assert "Reyes" not in t["names"]                    # two characters share it
    assert "Control" not in t["names"]                  # settings/themes are not linked
    assert t["names"]["Hale House"] is None             # held whole, not linked as Hale
    assert t["ov"] is False
