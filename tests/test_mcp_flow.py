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
    # The private page is stored gzipped; the build says what it will cost.
    assert 0 < r["private_stored_bytes"] < r["private_bytes"] // 3, r
    # There is no public visibility; sharing is a share link from the homepage.
    assert srv.publish_timeline(tid, "link")["error"] == "link_removed"
    r = srv.publish_timeline(tid, "private")
    assert r["visibility"] == "private"

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


def test_preview_is_an_artifact_page_and_publishes_nothing():
    tid = _setup_draft()
    assert srv.preview_timeline(tid).get("error") == "consent_gate"
    srv.record_materials_consent(tid, [{"name": "notes", "kind": "notes"}], True)
    srv.set_entities(tid, SAMPLE["brief"]["entities"])
    assert srv.preview_timeline(tid).get("error") == "no_nodes"
    srv.add_nodes(tid, SAMPLE["nodes"])
    srv.add_connections(tid, SAMPLE["connections"])
    r = srv.preview_timeline(tid)
    assert r.get("verify") == "passed", r
    page = Path(r["preview_path"]).read_text(encoding="utf-8")
    assert r["bytes"] == len(page.encode("utf-8"))
    # The Artifact host supplies the doctype/head/body; the shell must not.
    assert page.startswith("<title>") and "<!DOCTYPE" not in page[:200]
    assert "<body>" not in page.split("var __DOCS=")[0]
    # Opens on the timeline itself, not the home snapshot.
    assert page.rstrip().endswith('window.__altoSwap("t_0.html");\n</script>')
    # Nothing a sandboxed Artifact would block: no external script or style.
    import re
    assert not re.search(r'src=\\?"https?:', page)
    assert 'src=\\"alto-cloud.js\\"' not in page
    # A preview is not a build: status and live pages are left alone.
    assert srv.get_timeline(tid)["status"] == "draft"
    assert srv.publish_timeline(tid, "link").get("error")


def test_a_private_web_page_is_written_compressed(request, monkeypatch):
    """On the cloud store the connector writes the page into the account
    itself — gzipped, the same form the browser upload stores."""
    if request.node.callspec.params["fresh_store"] != "cloud":
        pytest.skip("only the cloud store writes pages")
    import base64
    from alto.build.private_shell import unpack_page
    import alto.publish_static as ps
    # No real site: the deploy and its checks are stubbed; the page write is not.
    monkeypatch.setattr(ps, "firebase_configured", lambda: True)
    monkeypatch.setattr(ps, "regenerate_site", lambda st, u: "site")
    monkeypatch.setattr(ps, "deploy_site", lambda site: "https://x.web.app")
    monkeypatch.setattr(ps, "verify_live", lambda site, live: [])
    monkeypatch.setattr(ps, "LAST_STALE", [])
    tid = _built_timeline()
    r = srv.publish_timeline(tid, "private-web")
    assert "error" not in r, r
    st = srv.get_store()
    page = st.get_artifact(srv.uid(), tid, "private.html")
    key = r["view_url"].rstrip("/").rsplit("/", 1)[1]
    fields = st.s.http.docs[f"{st.root}/users/{srv.uid()}/pages/{key}"]
    assert "html" not in fields and fields["enc"] == {"stringValue": "gzip"}
    assert unpack_page(base64.b64decode(fields["z"]["bytesValue"])) == page


def test_build_keeps_what_the_page_edits_folded_into_the_brief(monkeypatch):
    """1.9.49 regression: build_timeline folded the page's edits and then
    saved the timeline it had fetched BEFORE the fold, undoing every edit that
    lives in the brief (dragged cards, unit names, the Overview, filters).
    And a publish must never mark done an edit the draft does not carry."""
    tid = _setup_draft()
    srv.record_materials_consent(tid, [{"name": "notes", "kind": "notes"}], True)
    srv.add_nodes(tid, SAMPLE["nodes"])
    st = srv.get_store()
    store = {}
    monkeypatch.setattr(type(st), "get_edits", lambda self, u, t: json.loads(json.dumps(store.get(t))) if t in store else None, raising=False)
    monkeypatch.setattr(type(st), "put_edits", lambda self, u, t, d: store.__setitem__(t, json.loads(json.dumps(d))), raising=False)
    brief0 = srv.get_store().get_timeline(srv.uid(), tid)["brief"]
    l0, l1 = brief0["acts"][0]["label"], brief0["acts"][1]["label"]
    store[tid] = {"v": 1, "ops": {"u|0|label": {"b": l0, "v": "Renamed in the page", "t": 1},
                                 "u|1|label": {"b": l1, "v": "Also renamed", "t": 2}}}
    r = srv.build_timeline(tid)
    assert r.get("verify") == "passed" and r["manual_edits"].get("folded") == 2, r.get("manual_edits")
    acts = srv.get_store().get_timeline(srv.uid(), tid)["brief"]["acts"]
    assert (acts[0]["label"], acts[1]["label"]) == ("Renamed in the page", "Also renamed")
    from alto.edits import published
    assert published(srv.get_store(), srv.uid(), tid) == 2
    # a folded edit the draft lost is not marked done, and folds again
    store[tid] = {"v": 1, "ops": {"u|0|label": {"b": l0, "v": "Third name", "t": 3, "f": 1}}}
    assert published(srv.get_store(), srv.uid(), tid) == 0
    assert not store[tid]["ops"]["u|0|label"].get("done")
    store[tid]["ops"]["u|0|label"]["b"] = "Renamed in the page"
    srv.build_timeline(tid)
    assert srv.get_store().get_timeline(srv.uid(), tid)["brief"]["acts"][0]["label"] == "Third name"


def test_a_timeline_started_on_the_homepage_builds_with_what_was_written_in_it(monkeypatch):
    """1.9.51: the homepage writes a starter draft (alto-cloud.js
    createTimeline); everything after that is page edits. The connector's
    build folds them and keeps them (units, cards, moves, chips)."""
    from alto.build import starter
    st = srv.get_store()
    st.put_project(srv.uid(), "spring", {"project_id": "spring", "name": "Spring", "purpose": "",
                                         "kind": "studying", "created": "2026-10-05T00:00:00+00:00"})
    d = starter.draft("outline")
    tid = "my-outline"
    brief = {**d["brief"], "title": "My outline", "timeline_id": tid}
    st.put_timeline(srv.uid(), tid, {
        "timeline_id": tid, "project_id": "spring", "brief": brief,
        "consent": {"granted": True, "at": "x", "manual": True,
                    "sources": [{"name": "Written by the owner in the page", "kind": "own-writing"}]},
        "status": "published", "visibility": "private-web", "private_key": "k" * 22,
        "created": "2026-10-05T00:00:00+00:00", "started": "homepage"})
    st.put_nodes(srv.uid(), tid, [dict(n) for n in d["nodes"]])
    st.put_connections(srv.uid(), tid, [])
    assert any(t["timeline_id"] == tid for p in srv.list_projects()["projects"] for t in p.get("timelines", [])) \
        or tid in json.dumps(srv.list_projects())
    store = {}
    monkeypatch.setattr(type(st), "get_edits", lambda self, u, t: json.loads(json.dumps(store.get(t))) if t in store else None, raising=False)
    monkeypatch.setattr(type(st), "put_edits", lambda self, u, t, x: store.__setitem__(t, json.loads(json.dumps(x))), raising=False)
    store[tid] = {"v": 1, "ops": {
        "n|unit-1-start|title": {"b": "First card", "v": "Negligence", "t": 1},
        "nn|card-aa11bb": {"b": None, "v": {"p": "unit-1-start", "a": 0, "t": "Duty", "g": "", "d": ""}, "t": 2},
        "nu|unit-cc22dd": {"b": None, "v": {"n": 3, "c": "#2fb380", "l": "New unit"}, "t": 3},
        "nl|unit-cc22dd": {"b": "New unit", "v": "Strict liability", "t": 4},
        "nn|card-ee33ff": {"b": None, "v": {"p": "", "a": "unit-cc22dd", "t": "Animals"}, "t": 5},
        "rp|card-aa11bb": {"b": "unit-1-start", "v": "card-ee33ff", "t": 6},
        "rp|unit-2-start": {"b": "", "v": "card-ee33ff", "t": 6},
        "ne|c|duty-tag": {"b": None, "v": {"name": "Duty", "color": "#4a9eff"}, "t": 7},
        "ch|card-aa11bb|chars": {"b": [], "v": ["duty-tag"], "t": 8}}}
    r = srv.build_timeline(tid)
    assert r.get("verify") == "passed", r
    me = r["manual_edits"]
    assert me.get("conflicts") == ["rp|unit-2-start"], me          # a unit's top card stays
    doc = srv.get_store().get_timeline(srv.uid(), tid)
    assert [a["label"] for a in doc["brief"]["acts"]] == ["Unit 1", "Unit 2", "Strict liability"]
    assert any(e["id"] == "duty-tag" for e in doc["brief"]["entities"])
    nodes = {n["id"]: n for n in srv.get_store().list_nodes(srv.uid(), tid)}
    assert nodes["unit-1-start"]["title"] == "Negligence"
    assert nodes["card-aa11bb"]["entity_ids"] == ["duty-tag"]
    assert nodes["card-ee33ff"]["act"] == 2
    assert (nodes["card-aa11bb"]["parent"], nodes["card-aa11bb"]["act"]) == ("card-ee33ff", 2)
    assert nodes["unit-2-start"]["act"] == 1
