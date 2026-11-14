"""Bass tools: the connector's own functions, offered to the model and run in-process against a TEMP local store."""
import pytest as _pytest_sdk
_pytest_sdk.importorskip("anthropic")   # public CI has no SDK: these skip there (listed in test_bass_sdk_free.py) and run in the SDK env
_pytest_sdk.importorskip("httpx2")
import json
from pathlib import Path

import pytest

from bass_support import bass_guard, ROOT  # noqa: F401
from alto import mcp_server as srv
from alto.store.local import LocalStore
from alto.bass import mock_anthropic as M
from alto.bass import tools as T
from alto.bass.client import make_client

SAMPLE = json.loads((ROOT / "samples" / "contracts_brief.json").read_text(encoding="utf-8"))


@pytest.fixture
def tb(tmp_path):
    store = LocalStore(tmp_path / "store")
    box = T.ToolBox(store)
    yield box
    srv.set_store(None)


def run(tb, tool, uid="u1", **kw):
    out = tb.execute(uid, tool, kw)
    return out, json.loads(out.content)


def test_runs_against_a_local_store_never_the_cloud(tb):
    tb.execute("u1", "list_projects", {})
    assert srv.store_mode() == "local" and isinstance(srv.get_store(), LocalStore)


def test_tools_are_the_connectors_own_function_objects(tb):
    for n in T.BASS_TOOLS:
        assert tb.function(n) is srv.mcp._tool_manager.get_tool(n).fn


def test_offered_subset_excludes_sign_in_delete_publish_and_network_tools(tb):
    names = [s["name"] for s in tb.specs()]
    assert names == list(T.BASS_TOOLS)
    for banned in T.NEVER_OFFERED:
        assert banned not in names
    for n in ("sign_in", "set_up_site", "delete_timeline", "delete_project", "publish_timeline",
              "set_up_palace", "connect_account"):
        assert n in T.NEVER_OFFERED
    for n in ("set_up_world", "set_up_building"):                  # allowed 2 Nov (CEO C-1101-222251): no network, nothing published
        assert n in T.BASS_TOOLS and n not in T.NEVER_OFFERED
    with pytest.raises(ValueError):
        T.ToolBox(None, names=("add_nodes", "delete_project"))
    with pytest.raises(KeyError):
        T.ToolBox(None, names=("no_such_tool",))


def test_specs_shape(tb):
    specs = tb.specs()
    assert len(specs) == len(T.BASS_TOOLS)
    for s in specs:
        assert set(s) <= {"name", "description", "input_schema", "strict"}
        sch = s["input_schema"]
        assert sch["type"] == "object" and "account" not in sch["properties"]
        assert "account" not in sch.get("required", [])
        assert s["description"] and "\n" not in s["description"]
    by = {s["name"]: s for s in specs}
    assert by["add_nodes"]["input_schema"]["required"] == ["timeline_id", "nodes"]
    assert by["create_timeline"].get("strict") is None          # open dicts (the brief) can never be strict
    assert by["list_projects"].get("strict") is True            # a closed schema can


def test_every_spec_is_accepted_by_the_simulated_api(tb):
    mock = M.MockAnthropic()
    c = make_client("mock", mock=mock)
    n = c.messages.count_tokens(model="claude-sonnet-5-5", messages=[{"role": "user", "content": "hi"}],
                                tools=tb.specs()).input_tokens
    assert n > 1000                                              # the 17 tool definitions are real weight
    assert tb.strict_names and "add_nodes" not in tb.strict_names


def test_strict_off_when_asked(tmp_path):
    box = T.ToolBox(LocalStore(tmp_path), use_strict=False)
    assert not any("strict" in s for s in box.specs())


def test_full_flow_through_execute_and_the_consent_gate_holds(tb):
    out, r = run(tb, "create_project", name="Law School", purpose="1L", kind="studying")
    assert not out.is_error and out.wrote and r["project_id"]
    out, r = run(tb, "create_timeline", project_id=r["project_id"], brief=SAMPLE["brief"])
    assert not out.is_error, r
    tid = r["timeline_id"]
    out, r = run(tb, "add_nodes", timeline_id=tid, nodes=SAMPLE["nodes"])
    assert out.is_error and r["error"] == "consent_gate" and not out.wrote       # the gate holds in Bass too
    out, r = run(tb, "record_materials_consent", timeline_id=tid, sources=[{"name": "notes.pdf", "kind": "notes"}],
                 consent=True)
    assert r["gate"] == "open" and out.wrote
    run(tb, "set_entities", timeline_id=tid, entities=SAMPLE["brief"]["entities"])
    out, r = run(tb, "add_nodes", timeline_id=tid, nodes=SAMPLE["nodes"])
    assert not out.is_error and r["total_nodes"] == 6
    out, r = run(tb, "build_timeline", timeline_id=tid)
    assert r.get("verify") == "passed" and out.wrote
    out, r = run(tb, "get_timeline", timeline_id=tid)
    assert not out.wrote and len(r["node_ids"]) == 6


def test_accounts_are_isolated_by_uid(tb):
    run(tb, "create_project", uid="alice", name="Alice Only")
    _, r = run(tb, "list_projects", uid="bob")
    assert "Alice Only" not in json.dumps(r)
    _, r = run(tb, "list_projects", uid="alice")
    assert "Alice Only" in json.dumps(r)


def test_invalid_input_comes_back_as_an_error_result_not_an_exception(tb):
    out, r = run(tb, "add_nodes", timeline_id="t")                     # missing required `nodes`
    assert out.is_error and r["error"] == "invalid_input" and "nodes" in r["message"]
    out, r = run(tb, "add_nodes", timeline_id="t", nodes="not a list")
    assert out.is_error and r["error"] == "invalid_input"
    out, r = run(tb, "add_nodes", timeline_id="t", nodes=[], account="evil.web.app")   # the model may not pick accounts
    assert out.is_error and r["error"] == "invalid_input"
    assert tb.execute("u1", "add_nodes", [1]).is_error
    out, r = run(tb, "delete_project", project_id="x")
    assert out.is_error and r["error"] == "unknown_tool"


def test_a_tool_that_raises_becomes_is_error(tb, monkeypatch):
    t = srv.mcp._tool_manager.get_tool("list_projects")
    monkeypatch.setattr(t, "fn", lambda **kw: (_ for _ in ()).throw(RuntimeError("boom")))
    out, r = run(tb, "list_projects")
    assert out.is_error and r["error"] == "tool_failed" and "boom" in r["message"]


def test_big_results_are_truncated(tmp_path, monkeypatch):
    box = T.ToolBox(LocalStore(tmp_path), max_result_chars=200)
    t = srv.mcp._tool_manager.get_tool("list_projects")
    monkeypatch.setattr(t, "fn", lambda **kw: {"blob": "x" * 5000})
    out = box.execute("u", "list_projects", {})
    assert len(out.content) < 300 and "truncated" in out.content
    srv.set_store(None)


# ── the Atlas and the curated Blueprint (alto-bass-parity) ───────────────────────────────────────────────────────

def test_the_blueprint_tool_takes_the_curated_museum_only(tb):
    spec = {s["name"]: s for s in tb.specs()}["set_up_building"]
    props = spec["input_schema"]["properties"]
    assert set(props) == {"timeline_id", "mode", "assignments", "building"}
    assert props["building"]["enum"] == ["pma"] and spec["input_schema"]["required"] == ["timeline_id", "building"]
    assert "plan" not in props and "demo" not in props and "name" not in props
    assert len(spec["description"]) < 900
    for bad in ({"timeline_id": "t", "building": "test-pavilion"}, {"timeline_id": "t", "building": "pma", "demo": True},
                {"timeline_id": "t", "building": "pma", "plan": {"v": 1}}, {"timeline_id": "t"}):
        out, body = run(tb, "set_up_building", **bad)
        assert out.is_error and body["error"] == "invalid_input" and not out.wrote


def test_the_blueprint_runs_for_pma_and_the_atlas_places_cards_with_nothing_fetched(tb, monkeypatch):
    import socket
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    from tests.test_building_palace_tools import NODES
    pid = run(tb, "create_project", name="Museum", purpose="x", kind="studying")[1]["project_id"]
    tid = run(tb, "create_timeline", project_id=pid, brief={"title": "Walk", "mode": "palace", "palace_view": "building", "columns": 5,
                      "node_noun": "Room", "period_noun": "Wing", "acts": [{"label": "Ground"}, {"label": "Upper"}]})[1]["timeline_id"]
    run(tb, "record_materials_consent", timeline_id=tid, sources=[{"name": "n.pdf", "kind": "notes"}], consent=True)
    run(tb, "add_nodes", timeline_id=tid, nodes=json.loads(json.dumps(NODES)))
    out, body = run(tb, "set_up_building", timeline_id=tid, building="pma")
    assert not out.is_error and out.wrote and body.get("building", {}).get("id") == "pma", body
    pid2 = run(tb, "create_project", name="Atlas", purpose="x", kind="studying")[1]["project_id"]
    tid2 = run(tb, "create_timeline", project_id=pid2, brief={"title": "Map", "mode": "palace", "palace_view": "world", "columns": 5,
                       "acts": [{"label": "One"}, {"label": "Two"}]})[1]["timeline_id"]
    run(tb, "record_materials_consent", timeline_id=tid2, sources=[{"name": "n.pdf", "kind": "notes"}], consent=True)
    run(tb, "add_nodes", timeline_id=tid2, nodes=json.loads(json.dumps(NODES)))
    out, body = run(tb, "set_up_world", timeline_id=tid2)
    assert not out.is_error and out.wrote, body
