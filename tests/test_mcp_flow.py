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


@pytest.fixture(autouse=True, params=["local", "cloud"])
def fresh_store(request, tmp_path, monkeypatch):
    """Every flow runs twice: on a folder, and on the user's own account
    (ALTO_STORE=cloud) through a fake of the Firestore REST API."""
    if request.param == "local":
        srv.set_store(LocalStore(tmp_path))
        yield
        srv.set_store(None)
        return
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cloudfake import FakeFirebase
    from alto.cloud import session as sess
    from alto.store.cloud import CloudStore
    s = sess.Session({"apiKey": "k", "projectId": "proj", "appId": "a"},
                     http=FakeFirebase(), path=tmp_path / "session.json",
                     opener=lambda u: None)
    s._accept("RT")
    sess.set_session(s)
    monkeypatch.setenv("ALTO_STORE", "cloud")
    srv.set_store(CloudStore(s, LocalStore(tmp_path / "local")))
    yield
    srv.set_store(None)
    sess.set_session(None)


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


def _built_timeline(visibility="private"):
    tid = _setup_draft()
    srv.record_materials_consent(tid, [{"name": "notes", "kind": "notes"}], True)
    srv.add_nodes(tid, SAMPLE["nodes"])
    srv.add_connections(tid, SAMPLE["connections"])
    assert srv.build_timeline(tid).get("verify") == "passed"
    return tid


def test_delete_timeline_needs_the_token_from_a_preview():
    tid = _built_timeline()
    preview = srv.delete_timeline(tid)
    assert preview["status"] == "confirmation_required"
    assert preview["will_delete"]["nodes"] == 6
    assert srv.get_timeline(tid)["node_ids"], "the preview must delete nothing"
    # a guessed or stale token deletes nothing either
    assert srv.delete_timeline(tid, "0000000000")["status"] == "confirmation_required"
    assert srv.get_timeline(tid)["node_ids"]
    done = srv.delete_timeline(tid, preview["confirm_token"])
    assert done["deleted"]["timeline_id"] == tid
    assert srv.get_timeline(tid)["error"] == "not_found"
    assert all(t["timeline_id"] != tid
               for p in srv.list_projects()["projects"] for t in p["timelines"])


def test_token_goes_stale_when_the_timeline_changes():
    tid = _built_timeline()
    token = srv.delete_timeline(tid)["confirm_token"]
    srv.delete_nodes(tid, ["feinberg"])
    assert srv.delete_timeline(tid, token)["status"] == "confirmation_required"
    assert srv.get_timeline(tid)["node_ids"]


def test_delete_project_refuses_non_empty_then_takes_timelines_with_it():
    tid = _built_timeline()
    pid = srv.get_timeline(tid)["project_id"]
    r = srv.delete_project(pid)
    assert r["error"] == "not_empty" and r["timelines"][0]["timeline_id"] == tid
    preview = srv.delete_project(pid, delete_timelines=True)
    assert preview["status"] == "confirmation_required"
    assert srv.list_projects()["projects"], "the preview must delete nothing"
    srv.delete_project(pid, True, preview["confirm_token"])
    assert srv.list_projects()["projects"] == []
    assert srv.get_timeline(tid)["error"] == "not_found"


def test_delete_empty_project():
    pid = srv.create_project("Scratch", "", "studying")["project_id"]
    token = srv.delete_project(pid)["confirm_token"]
    assert srv.delete_project(pid, False, token)["deleted"]["project_id"] == pid
    assert srv.delete_project(pid)["error"] == "not_found"


def test_delete_rejects_a_bad_id():
    assert srv.delete_timeline("../x")["error"] == "bad_id"
    assert srv.delete_project("../x")["error"] == "bad_id"
