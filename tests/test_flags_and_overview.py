"""Flags (the user's own marks, several per node) in the Filter panel, and an
outline's Overview with a real summary of every section."""
import json
from pathlib import Path

import pytest

from alto.build.brief import BriefError
from alto.build.builder import build_timeline, load_brief

ROOT = Path(__file__).resolve().parent.parent


def _d():
    return json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))


def _flagged():
    d = _d()
    d["brief"]["flags"] = [{"id": "key", "name": "Pivotal"}, {"id": "old", "name": "Overruled"},
                           {"id": "unused", "name": "Nobody"}]
    ids = [n["id"] for n in d["nodes"]]
    d["nodes"][0]["flags"] = ["key"]
    d["nodes"][1]["flags"] = ["key", "old"]          # several flags on one node
    return d, ids


def _sections(html):
    dec = json.JSONDecoder()
    i = html.index("var FILTER_SECTIONS=") + len("var FILTER_SECTIONS=")
    secs, end = dec.raw_decode(html, i)
    k = html.index("var FILTER_NODES=", end) + len("var FILTER_NODES=")
    nodes, _ = dec.raw_decode(html, k)
    return secs, nodes


def test_a_node_shows_under_every_flag_it_carries():
    d, ids = _flagged()
    html, rep = build_timeline(*load_brief(d))
    secs, nodes = _sections(html)
    flags = next(s for s in secs if s["key"] == "flags")
    assert flags["kind"] == "chips" and flags["label"] == "Flags"
    assert [i["name"] for i in flags["items"]] == ["Pivotal", "Overruled"]
    assert nodes["flags"]["key"] == sorted([ids[0], ids[1]])
    assert nodes["flags"]["old"] == [ids[1]]          # the second node is under both
    # a flag nobody carries is left out, with a warning
    assert any("Nobody" in w for w in rep["warnings"])


def test_no_flags_means_no_flags_section():
    html, _ = build_timeline(*load_brief(_d()))
    if "var FILTER_SECTIONS=" in html:
        secs, _n = _sections(html)
        assert all(s["key"] != "flags" for s in secs)


def test_unknown_flag_on_a_node_is_refused():
    d, ids = _flagged()
    d["nodes"][2]["flags"] = ["ghost"]
    with pytest.raises(BriefError, match="unknown flag"):
        build_timeline(*load_brief(d))


def test_duplicate_or_nameless_flags_are_refused():
    d, _ = _flagged()
    d["brief"]["flags"].append({"id": "key", "name": "Again"})
    with pytest.raises(BriefError, match="duplicate flag"):
        build_timeline(*load_brief(d))
    d, _ = _flagged()
    d["brief"]["flags"][0]["name"] = " "
    with pytest.raises(BriefError, match="needs a name"):
        build_timeline(*load_brief(d))


def _overview(html):
    i = html.index('<div id="summary-inner">')
    return html[i:html.index("</div>", i)]


def test_each_section_gets_its_authored_summary_above_its_concepts():
    d = _d()
    d["brief"]["overview_html"] = ""
    for i, a in enumerate(d["brief"]["acts"]):
        a["summary"] = f"SUMMARY-{i}: what this section is about & how it fits."
    html, rep = build_timeline(*load_brief(d))
    ov = _overview(html)
    for i, a in enumerate(d["brief"]["acts"]):
        assert f"SUMMARY-{i}: what this section is about &amp; how it fits." in ov
    # summary comes before the section's concept list
    first = next(n for n in d["nodes"] if n["act"] == 0 and not n.get("parent"))
    assert ov.index("SUMMARY-0") < ov.index(f"showDetail('node','{first['id']}')")


def test_without_a_summary_the_overview_is_composed_from_the_hub_and_its_concepts():
    d = _d()
    d["brief"]["overview_html"] = ""
    html, rep = build_timeline(*load_brief(d))
    ov = _overview(html)
    hub = next(n for n in d["nodes"] if n["act"] == 0 and not n.get("parent"))
    kids = [n["title"] for n in d["nodes"] if n.get("parent") == hub["id"]]
    assert "It covers " in ov
    assert kids and kids[0].replace("&", "&amp;") in ov


def test_an_authored_overview_is_still_used_as_is():
    d = _d()
    d["brief"]["overview_html"] = "<p>HAND-WRITTEN</p>"
    for a in d["brief"]["acts"]:
        a["summary"] = "IGNORED"
    html, _ = build_timeline(*load_brief(d))
    assert "HAND-WRITTEN" in _overview(html) and "IGNORED" not in _overview(html)


def test_the_guide_never_defaults_to_coverage_and_asks_for_flags():
    g = (ROOT / "alto" / "interview_guide.md").read_text(encoding="utf-8")
    assert "Do not offer or add it on" in g and "only\n  when the user asks for it by name" in g
    assert "### F3. Flags in their notes" in g and "Which flags do you want" in g
    assert "`set_flags" in g and "section_summaries" in g
    assert "**coverage** + **depth**" not in g


def test_set_flags_is_a_tool():
    src = (ROOT / "alto" / "mcp_server.py").read_text(encoding="utf-8")
    assert src.count("@mcp.tool(") == 24 and "def set_flags(" in src
