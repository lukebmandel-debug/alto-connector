"""set_axis_values and `deadlines`: a period the quote does not state is refused (closed system: nothing the quoted words
do not say), and word forms and plurals of the same limit are accepted."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from alto import mcp_server as M  # noqa: E402


@pytest.fixture()
def tid():
    pid = M.create_project("Civ Pro", "1L", "studying")["project_id"]
    t = M.create_timeline(pid, {"title": "Civ Pro", "timeline_id": "cp", "mode": "outline", "columns": 5, "node_noun": "Concept",
                                "acts": [{"label": "UNIT ONE"}, {"label": "UNIT TWO"}],
                                "relations": [{"key": "spine", "label": "Contains"}]})
    assert not t.get("error"), t
    M.record_materials_consent(t["timeline_id"], ["my own outline"], True)
    return t["timeline_id"]


def _vals(period, quote):
    return [{"id": "usc-1446", "name": "28 U.S.C. 1446", "sections": [{"h": "Text", "t": "x", "prov": "quoted"}],
             "deadlines": [{"period": period, "what": "Notice of removal", "quote": quote, "cite": "1446(b)(1)"}]}]


def test_a_period_the_quote_lacks_is_refused(tid):
    r = M.set_axis_values(tid, 2, "Statutes & Rules", "Section", _vals("30 days", "filed within 20 days"), hide_nav=True)
    assert r.get("error") == "invalid_axis" and "does not appear in the quote" in r["message"], r
    assert not (M.get_timeline(tid)["brief"].get("axes") or [{}])[-1].get("values")


@pytest.mark.parametrize("period,quote", [("30 days", "within 30 days after"), ("1 year", "more than one year after"),
                                           ("30 days", "within thirty days"), ("21 days", "twenty-one day period")])
def test_a_period_the_quote_states_is_kept(tid, period, quote):
    r = M.set_axis_values(tid, 2, "Statutes & Rules", "Section", _vals(period, quote), hide_nav=True)
    assert not r.get("error"), r
    v = M.get_timeline(tid)["brief"]["axes"][-1]["values"][0]
    assert v["deadlines"][0]["period"] == period
