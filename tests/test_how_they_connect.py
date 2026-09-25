"""A line can say why it was drawn, and pages show it as "How they connect"."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import load_brief, build_timeline, place  # noqa: E402
from alto.build.verify import verify_data  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"


def _build(extra=None, connections=None):
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    if connections is not None:
        d["connections"] = connections
    elif extra:
        d["connections"] = d["connections"] + extra
    return build_timeline(*load_brief(d))


def test_a_line_may_carry_its_reason_as_a_fourth_element():
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    b, nodes, _ = load_brief(d)
    place(b, nodes)
    ok = [["lucy-v-zehmer", "carbolic", "spine", "The offer in one is the acceptance question in the next."]]
    assert verify_data(b, nodes, ok) == []
    bad = [["lucy-v-zehmer", "carbolic", "spine", 5]]
    assert any("how-they-connect" in f for f in verify_data(b, nodes, bad))
    assert any("must be" in f for f in verify_data(b, nodes, [["a", "b"]]))


def test_the_reason_reaches_the_page_and_is_made_inert():
    html, _ = _build(connections=[
        ["lucy-v-zehmer", "carbolic", "spine", "Because <script>alert(1)</script> it does."]])
    conns = html.split("const CONNECTIONS = [", 1)[1].split("];", 1)[0]
    assert "Because" in conns and "<script>" not in conns


def test_a_long_jump_without_a_reason_is_flagged_and_a_short_one_is_not():
    _, rep = _build(connections=[["lucy-v-zehmer", "carbolic", "spine"],
                                 ["lucy-v-zehmer", "feinberg", "spine"]])
    flagged = [w for w in rep["warnings"] if "no explanation" in w]
    assert len(flagged) == 1 and "feinberg" in flagged[0]


def test_giving_the_reason_clears_the_flag():
    _, rep = _build(connections=[["lucy-v-zehmer", "feinberg", "spine",
                                  "The first case sets the rule the last one tests."]])
    assert not [w for w in rep["warnings"] if "no explanation" in w]


def test_node_pages_get_their_connections_and_every_kind_of_chip():
    html, _ = _build()
    assert "function _altoNodeConnect(id){" in html
    assert "sections = sections.concat(_altoNodeConnect(id));" in html          # desktop and mobile
    assert "sections=sections.concat(_altoNodeConnect(targetId));" in html
    assert "html += _altoAxisChips(n, true);" in html
    assert "inner += _altoAxisChips(nd, false);" in html
    assert "var _ALTO_CHIP_HEADINGS=" in html


def test_an_outline_lists_what_a_concept_contains_instead():
    html, _ = _build()
    body = html.split("function _altoNodeConnect(id){", 1)[1].split("\n}", 1)[0]
    assert "window._ALTO_OUTLINE" in body.split("\n")[1]


def test_sub_chip_pages_list_every_node_and_the_steps_between():
    html, _ = _build()
    body = html.split("function _altoDoctrineBody(id, kind, have){", 1)[1]
    assert "_altoMembers(id, kind)" in body
    assert "hc-link" in body and "_altoHow(a.id,b.id)" in body
    # authored sections of the same name win over the generated ones
    assert "_altoHave(have, 'How they connect')" in body
