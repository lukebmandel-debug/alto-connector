"""The horizontal timeline (brief.mode "lanes", lanes.py): reading `when`,
checking lines, what the page carries, and manual edit mode's when / line /
lines folded back into the draft."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.brief import BriefError, validate_brief, validate_nodes  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.lanes import parse_when  # noqa: E402
from alto.build.verify import find_node, verify_scripts  # noqa: E402

SAMPLE = ROOT / "samples" / "lanes_brief.json"


def _d():
    return json.loads(SAMPLE.read_text())


@pytest.mark.parametrize("s,want", [
    ("1842", 1842), ("1842-01", 1842), ("-500", -500), ("500 BC", -500), ("44 BCE", -44),
    ("Year 3", 3), ("Day 12", 12), ("", None), ("someday", None), (7, 7),
])
def test_parse_when(s, want):
    assert parse_when(s) == want


def test_dates_inside_a_year_keep_their_order():
    a, b, c = parse_when("1852-03-01"), parse_when("1852-06"), parse_when("March 1853")
    assert 1852 < a < b < 1853 <= c < 1853.3


def test_sample_validates_and_builds_with_the_layout():
    b, nodes, conns = load_brief(_d())
    validate_brief(b)
    w = validate_nodes(b, nodes)
    assert any("no `when`" in x for x in w)                # the one undated event is named
    html, _ = build_timeline(b, nodes, conns)
    assert "window._ALTO_LANES=" in html and "window._altoLanes=function" in html
    assert "if(window._altoLanes && window._altoLanes(nodeHeights)) return;" in html
    data = json.loads(re.search(r"window\._ALTO_LANES=(\{.*?\});\n", html).group(1))
    assert data["ev"]["storm-1810"] == {"l": "flashback", "w": "1810", "t": 1810.0}
    assert {l["id"]: l["to"] for l in data["lines"]}["flashback"] == "memory"
    assert data["main"] == "The town"


def test_other_modes_carry_no_lanes_code():
    d = json.loads((ROOT / "samples" / "contracts_brief.json").read_text())
    html, _ = build_timeline(*load_brief(d))
    assert "window._ALTO_LANES=" not in html and "window._altoLanes=function" not in html


@pytest.mark.parametrize("mutate,msg", [
    (lambda d: d["nodes"][0].update(line="nope"), "not one of the brief's lines"),
    (lambda d: d["brief"]["lines"].append({"id": "main", "label": "x"}), "main"),
    (lambda d: d["brief"]["lines"][0].update(side="left"), "side"),
    (lambda d: d["brief"]["lines"][0].update(to="tomas-camp"), "on the line itself"),
    (lambda d: d["brief"]["lines"][0].update(to="ghost"), "is not a node"),
    (lambda d: d["brief"]["lines"][0].update(**{"from": "council", "to": "letter"}), "before it branches"),
    (lambda d: d["brief"].update(mode="linear"), "need mode 'lanes'"),
])
def test_bad_lines_are_refused(mutate, msg):
    d = _d()
    mutate(d)
    b, nodes, _ = load_brief(d)
    with pytest.raises(BriefError, match=msg):
        validate_brief(b)
        validate_nodes(b, nodes)


@pytest.mark.skipif(find_node() is None, reason="node not installed")
def test_lanes_page_passes_the_js_gate():
    html, _ = build_timeline(*load_brief(_d()))
    assert verify_scripts(html, "timeline") == ([], [])


def test_when_line_and_lines_fold_into_the_draft():
    from tests.test_manual_edit import Store
    from alto.edits import fold
    st = Store(_d())
    st.doc["brief"]["timeline_id"] = "t1"
    newline = {"id": "line-ab12c", "label": "The ferry", "color": "#3d9a8b", "side": "below", "from": "arrive", "to": ""}
    old = {"id": "tomas", "label": "Tomas", "color": "#e07a5f", "side": "above", "from": "letter", "to": "council"}
    st.edits = {"v": 1, "ops": {
        "ln|line-ab12c": {"b": None, "v": newline, "t": 1},
        "ln|tomas": {"b": old, "v": dict(old, label="Tomas the sailor", to="light"), "t": 2},
        "n|repair|when": {"b": "1853-05", "v": "1853-09", "t": 3},
        "n|repair|line": {"b": "", "v": "line-ab12c", "t": 4}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and not r["gone"], r
    lines = {l["id"]: l for l in st.doc["brief"]["lines"]}
    assert lines["line-ab12c"]["label"] == "The ferry" and lines["line-ab12c"]["from"] == "arrive"
    assert lines["tomas"]["label"] == "Tomas the sailor" and lines["tomas"]["to"] == "light"
    n = next(x for x in st.nodes if x["id"] == "repair")
    assert n["when"] == "1853-09" and n["line"] == "line-ab12c"
    b, nodes, conns = load_brief({"brief": st.doc["brief"], "nodes": st.nodes, "connections": st.conns})
    validate_brief(b)
    validate_nodes(b, nodes)
