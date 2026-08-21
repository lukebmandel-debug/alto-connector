"""Outline mode through the MCP tools — the path a student actually takes.

The build library is tested elsewhere; this is about the tool surface: that
`mode` survives create_timeline, that `parent` survives add_nodes, that
set_axis_values is consent-gated (which is why it exists), and that deleting a
hub does not silently orphan what it contains.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import mcp_server as M  # noqa: E402


BRIEF = {
    "title": "Contracts", "timeline_id": "c1", "mode": "outline", "columns": 5,
    "node_noun": "Concept",
    "acts": [{"label": "UNIT ONE — FORMATION"}, {"label": "UNIT TWO — REMEDIES"}],
    "relations": [{"key": "spine", "label": "Contains"},
                  {"key": "limits", "label": "Limits", "color": "#f43f5e"}],
}
NODES = [
    {"id": "formation", "act": 0, "tag": "F", "title": "Formation",
     "desc": "Assent plus consideration.", "entity_ids": ["formation"]},
    {"id": "offer", "act": 0, "parent": "formation", "tag": "F",
     "title": "Offer", "desc": "Willingness to bargain.",
     "entity_ids": ["formation"]},
    {"id": "acceptance", "act": 0, "parent": "formation", "tag": "F",
     "title": "Acceptance", "desc": "Assent to the terms.",
     "entity_ids": ["formation"]},
    {"id": "remedies", "act": 1, "tag": "R", "title": "Remedies",
     "desc": "Expectation is the default.", "entity_ids": ["remedies"]},
    {"id": "foreseeability", "act": 1, "parent": "remedies", "tag": "R",
     "title": "Foreseeability", "desc": "Limits recovery.",
     "entity_ids": ["remedies"]},
]


@pytest.fixture()
def tid():
    pid = M.create_project("Contracts", "1L", "studying")["project_id"]
    t = M.create_timeline(pid, dict(BRIEF))
    assert not t.get("error"), t
    return t["timeline_id"]


def _consent(tid):
    M.record_materials_consent(tid, ["my own outline"], True)
    M.set_entities(tid, [{"id": "formation", "name": "Formation"},
                         {"id": "remedies", "name": "Remedies"}])


def test_mode_round_trips_through_the_draft(tid):
    got = M.get_timeline(tid)
    assert got["brief"]["mode"] == "outline"


def test_authoring_stays_locked_until_consent(tid):
    assert M.add_nodes(tid, NODES).get("error") == "consent_gate"
    assert M.set_axis_values(
        tid, 1, "Cases", "Case",
        values=[{"id": "hadley", "name": "Hadley v. Baxendale",
                 "sections": [{"h": "Holding", "t": "Notice required."}]}]
    ).get("error") == "consent_gate"


def test_axis_values_upsert_and_carry_hide_nav(tid):
    _consent(tid)
    a = M.set_axis_values(tid, 1, "Cases", "Case", hide_nav=True, values=[
        {"id": "hadley", "name": "Hadley v. Baxendale"}])
    assert (a["slot"], a["values"], a["hide_nav"]) == (1, 1, True)
    b = M.set_axis_values(tid, 1, "Cases", "Case", hide_nav=True, values=[
        {"id": "hawkins", "name": "Hawkins v. McGee"}])
    assert b["values"] == 2                      # upsert, not replace
    ax = M.get_timeline(tid)["brief"]["axes"][0]
    assert ax["hide_nav"] is True
    assert {v["id"] for v in ax["values"]} == {"hadley", "hawkins"}


def test_parent_survives_add_nodes_and_the_build(tid):
    _consent(tid)
    assert not M.add_nodes(tid, NODES).get("error")
    got = M.get_timeline(tid)
    assert set(got["node_ids"]) == {n["id"] for n in NODES}
    assert not M.build_timeline(tid).get("error")


def test_a_child_may_arrive_before_its_parent(tid):
    """add_nodes is a batch upsert, so this only warns until the build."""
    _consent(tid)
    # the band still has its hub; only the named parent is missing
    r = M.add_nodes(tid, [NODES[0], {**NODES[1], "parent": "not-yet"}])
    assert not r.get("error"), r
    assert any("not a node yet" in w for w in r["warnings"])


def test_deleting_a_hub_refuses_to_orphan_its_children(tid):
    _consent(tid)
    M.add_nodes(tid, NODES)
    d = M.delete_nodes(tid, ["formation"])
    assert d["error"] == "has_children"
    assert set(d["children"]["formation"]) == {"offer", "acceptance"}
    assert len(M.get_timeline(tid)["node_ids"]) == len(NODES)   # nothing removed


def test_deleting_a_whole_subtree_is_allowed(tid):
    _consent(tid)
    M.add_nodes(tid, NODES)
    d = M.delete_nodes(tid, ["formation", "offer", "acceptance"])
    assert not d.get("error")
    assert d["remaining_nodes"] == 2


def test_a_linear_timeline_keeps_the_old_delete_behaviour():
    pid = M.create_project("Novel", "book", "writing")["project_id"]
    t = M.create_timeline(pid, {**BRIEF, "mode": "linear", "timeline_id": "n1"})
    tid2 = t["timeline_id"]
    _consent(tid2)
    M.add_nodes(tid2, NODES)
    assert not M.delete_nodes(tid2, ["formation"]).get("error")
