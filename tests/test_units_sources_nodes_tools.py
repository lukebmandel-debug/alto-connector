"""set_units / add_sources / get_nodes / get_timeline(compact): an existing
outline grows a unit and new notes without touching its nodes. Runs on a
folder and on a fake of Firestore's REST API — never a real account."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from alto import mcp_server as srv  # noqa: E402
from alto.store.local import LocalStore  # noqa: E402

OUTLINE = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True, params=["local", "cloud"])
def fresh_store(request, tmp_path, monkeypatch):
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


def _draft():
    pid = srv.create_project("Law School", "1L year", "studying")["project_id"]
    tid = srv.create_timeline(pid, OUTLINE["brief"])["timeline_id"]
    srv.record_materials_consent(tid, [{"id": "n1", "name": "notes 1", "kind": "notes"}], True)
    srv.set_entities(tid, OUTLINE["brief"].get("entities") or [])
    assert "error" not in srv.add_nodes(tid, OUTLINE["nodes"])
    return tid


def _strip(nodes):
    return sorted(json.dumps(n, sort_keys=True) for n in nodes)


def test_a_unit_is_appended_and_nodes_are_untouched():
    tid = _draft()
    before = srv.get_nodes(tid)["nodes"]
    n_acts = len(OUTLINE["brief"]["acts"])
    r = srv.set_units(tid, add=[{"label": "STRICT LIABILITY", "short": "Strict Liability"}])
    assert r["ok"] and r["added"] == [n_acts], r
    assert _strip(srv.get_nodes(tid)["nodes"]) == _strip(before)
    # before set_units this was "act out of range"
    hub = {"id": "sl-hub", "act": n_acts, "tag": "concept", "title": "Strict liability", "desc": "d"}
    assert "error" not in srv.add_nodes(tid, [hub])
    assert len(srv.get_timeline(tid)["node_ids"]) == len(before) + 1
    # summaries now take one entry per unit, the new one included
    r = srv.set_overview(tid, section_summaries=[""] * (n_acts + 1))
    assert "error" not in r, r


def test_units_can_be_renamed_and_bad_ones_refused():
    tid = _draft()
    assert srv.set_units(tid, update=[{"act": 0, "label": "RENAMED"}])["ok"]
    assert srv.get_timeline(tid)["brief"]["acts"][0]["label"] == "RENAMED"
    assert srv.set_units(tid, update=[{"act": 99, "label": "x"}])["error"] == "invalid_units"
    assert srv.set_units(tid, add=[{"short": "no label"}])["error"] == "invalid_units"
    assert srv.set_units(tid)["error"] == "nothing_to_do"


def test_no_upper_limit_on_units():
    tid = _draft()
    r = srv.set_units(tid, add=[{"label": f"U{i}"} for i in range(12)])
    assert r["ok"] and len(r["units"]) == len(OUTLINE["brief"]["acts"]) + 12


def test_add_sources_appends_without_a_new_consent():
    tid = _draft()
    at = srv.get_timeline(tid)["consent"]["at"]
    r = srv.add_sources(tid, [{"id": "n2", "name": "notes 2", "kind": "notes",
                               "url": "https://docs.google.com/document/d/x/edit"}])
    assert r["ok"] and r["added"] == ["n2"] and r["count"] == 2, r
    c = srv.get_timeline(tid)["consent"]
    assert c["granted"] and c["at"] == at and [s["id"] for s in c["sources"]] == ["n1", "n2"]
    r = srv.add_sources(tid, [{"id": "n1", "name": "notes 1 (renamed)", "kind": "notes"}])
    assert r["updated"] == ["n1"] and r["count"] == 2
    assert srv.add_sources(tid, [{"name": "no id"}])["error"] == "invalid_sources"


def test_add_sources_needs_consent_first():
    pid = srv.create_project("Law School", "1L year", "studying")["project_id"]
    tid = srv.create_timeline(pid, OUTLINE["brief"])["timeline_id"]
    assert srv.add_sources(tid, [{"id": "a", "name": "a"}])["error"] == "no_consent"


def test_get_nodes_filters_and_compact_timeline():
    tid = _draft()
    ids = [n["id"] for n in OUTLINE["nodes"]][:2]
    r = srv.get_nodes(tid, ids=ids + ["ghost"], fields=["title"])
    assert r["count"] == 2 and r["missing"] == ["ghost"]
    assert all(set(n) == {"id", "title"} for n in r["nodes"])
    assert all(n["act"] == 1 for n in srv.get_nodes(tid, act=1)["nodes"])
    full, small = srv.get_timeline(tid), srv.get_timeline(tid, compact=True)
    assert small["node_ids"] == full["node_ids"]
    assert len(json.dumps(small)) <= len(json.dumps(full))
