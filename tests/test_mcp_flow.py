"""M2 flow tests: consent gate, full interview→build→publish, resume."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from alto import mcp_server as srv  # noqa: E402
from alto.store.local import LocalStore  # noqa: E402

SAMPLE = json.loads((ROOT / "samples" / "contracts_brief.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def fresh_store(tmp_path):
    srv.set_store(LocalStore(tmp_path))
    yield
    srv.set_store(None)


def _setup_draft():
    pid = srv.create_project("Law School", "1L year", "studying")["project_id"]
    r = srv.create_timeline(pid, SAMPLE["brief"])
    assert "error" not in r, r
    return r["timeline_id"]


def test_consent_gate_blocks_authoring():
    tid = _setup_draft()
    r = srv.add_nodes(tid, SAMPLE["nodes"])
    assert r.get("error") == "consent_gate"
    r = srv.build_timeline(tid)
    assert r.get("error") == "consent_gate"
    # consent without sources is rejected
    r = srv.record_materials_consent(tid, [], True)
    assert r.get("error") == "no_sources"


def test_full_flow_and_resume():
    tid = _setup_draft()
    assert srv.record_materials_consent(
        tid, [{"name": "Contracts casebook notes.pdf", "kind": "notes"}],
        True)["gate"] == "open"
    assert srv.set_entities(tid, SAMPLE["brief"]["entities"])["palette"]
    r = srv.add_nodes(tid, SAMPLE["nodes"])
    assert r["total_nodes"] == 6, r
    r = srv.add_connections(tid, SAMPLE["connections"])
    assert r["accepted"] == 5, r
    r = srv.run_layout_preview(tid)
    assert r["moved_on_recheck"] == [], r
    r = srv.build_timeline(tid)
    assert r.get("verify") == "passed", r
    r = srv.publish_timeline(tid, "link")
    assert r["visibility"] == "link"

    # resume in a "new conversation"
    state = srv.get_timeline(tid)
    assert state["status"] == "published"
    assert len(state["node_ids"]) == 6
    guide = srv.get_interview_guide()
    assert any(d["timeline_id"] == tid for d in guide["drafts"])
    assert "closed knowledge container" in guide["guide_markdown"]


def test_bad_connection_rejected_at_write():
    tid = _setup_draft()
    srv.record_materials_consent(tid, [{"name": "notes", "kind": "notes"}], True)
    srv.add_nodes(tid, SAMPLE["nodes"])
    r = srv.add_connections(tid, [["lucy-v-zehmer", "ghost-node", "spine"]])
    assert r.get("error") == "invalid_connections"


def test_upsert_and_delete_nodes():
    tid = _setup_draft()
    srv.record_materials_consent(tid, [{"name": "notes", "kind": "notes"}], True)
    srv.add_nodes(tid, SAMPLE["nodes"])
    # upsert one node with a new desc — count unchanged
    n0 = {**SAMPLE["nodes"][0], "desc": "Updated verbatim brief text."}
    r = srv.add_nodes(tid, [n0])
    assert r["total_nodes"] == 6
    srv.add_connections(tid, SAMPLE["connections"])
    r = srv.delete_nodes(tid, ["feinberg"])
    assert r["remaining_nodes"] == 5
    assert r["remaining_connections"] == 4  # ricketts→feinberg dropped
