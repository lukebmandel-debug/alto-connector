"""A page saved by a NEWER Alto (Luke 2026-11-26: his connector, 1.9.284, on a page whose brief carried `extend`, a key newer than it; `glowfuture` stands in here, since this version knows `extend`: every add_nodes failed as "invalid_nodes ... unexpected
keyword argument 'extend'", which pointed the debugging at node fields). Reading keeps working; every write refuses with the real reason, says nothing was changed, never
reports invalid_nodes and never drops the unknown key. Test store only."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import mcp_server as srv  # noqa: E402
from alto.store.local import LocalStore  # noqa: E402

NODES = [{"id": "a", "act": 0, "title": "Alpha", "tag": "", "desc": "d"}]


@pytest.fixture
def store(tmp_path):
    st = LocalStore(tmp_path)
    srv.set_store(st)
    yield st
    srv.set_store(None)


def _newer_page(st, where="brief"):
    pid = srv.create_project("Course", "x", "studying")["project_id"]
    tid = srv.create_timeline(pid, {"title": "Torts", "mode": "linear", "columns": 3, "node_noun": "Event", "period_noun": "Era",
                                    "acts": [{"label": "One"}, {"label": "Two"}]})["timeline_id"]
    srv.record_materials_consent(tid, [{"name": "n.pdf", "kind": "notes"}], True)
    assert "error" not in srv.add_nodes(tid, json.loads(json.dumps(NODES)))
    doc = st.get_timeline(srv.uid(), tid)
    if where == "brief":
        doc["brief"]["glowfuture"] = {"on": True}                    # what a newer Alto saved
        st.put_timeline(srv.uid(), tid, doc)
    else:
        nodes = st.list_nodes(srv.uid(), tid)
        nodes[0]["glow"] = 3
        st.put_nodes(srv.uid(), tid, nodes)
    return tid, json.dumps(st.get_timeline(srv.uid(), tid), sort_keys=True), json.dumps(st.list_nodes(srv.uid(), tid), sort_keys=True)


@pytest.mark.parametrize("where", ["brief", "node"])
def test_a_write_to_a_page_saved_by_a_newer_alto_is_refused_and_changes_nothing(store, where):
    tid, doc0, nodes0 = _newer_page(store, where)
    new = [{"id": "b", "act": 0, "title": "Beta", "tag": "", "desc": "d"}]
    for call in (lambda: srv.add_nodes(tid, new), lambda: srv.delete_nodes(tid, ["a"]), lambda: srv.set_overview(tid, "<p>x</p>")):
        r = call()
        assert r["error"] == "page_saved_by_newer_alto", r
        assert "newer Alto" in r["message"] and "nothing was changed" in r["message"].lower() and "Update Alto" in r["message"] and "update_alto" in r["message"] and "releases/latest" in r["message"]
        assert "glowfuture" in r["message"] or "glow" in r["message"]
    assert json.dumps(store.get_timeline(srv.uid(), tid), sort_keys=True) == doc0       # (the unknown key is still there, nothing else moved)
    assert json.dumps(store.list_nodes(srv.uid(), tid), sort_keys=True) == nodes0


def test_reading_a_page_saved_by_a_newer_alto_still_works(store):
    tid, _, _ = _newer_page(store)
    r = srv.get_timeline(tid)
    assert "error" not in r and r["brief"]["glowfuture"] == {"on": True}
    assert srv.get_nodes(tid) if hasattr(srv, "get_nodes") else True


def test_a_page_with_only_known_keys_is_not_refused(store):
    pid = srv.create_project("Course", "x", "studying")["project_id"]
    tid = srv.create_timeline(pid, {"title": "Torts", "mode": "linear", "columns": 3, "node_noun": "Event", "period_noun": "Era", "acts": [{"label": "One"}, {"label": "Two"}]})["timeline_id"]
    srv.record_materials_consent(tid, [{"name": "n.pdf", "kind": "notes"}], True)
    assert "error" not in srv.add_nodes(tid, json.loads(json.dumps(NODES)))
