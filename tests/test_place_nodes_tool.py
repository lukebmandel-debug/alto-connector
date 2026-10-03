"""place_nodes: the chat's way to put an outline's cards where the user asks.
Runs on a folder and on the user's own account (a fake of Firestore's REST API),
like the flow tests, because hints are stored in the brief."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from alto import mcp_server as srv  # noqa: E402
from alto.store.local import LocalStore  # noqa: E402

OUTLINE = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
LINEAR = json.loads((ROOT / "samples" / "contracts_brief.json").read_text(encoding="utf-8"))


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


def _draft(sample):
    pid = srv.create_project("Law School", "1L year", "studying")["project_id"]
    tid = srv.create_timeline(pid, sample["brief"])["timeline_id"]
    srv.record_materials_consent(tid, [{"name": "notes.pdf", "kind": "notes"}], True)
    srv.set_entities(tid, sample["brief"].get("entities") or [])
    assert "error" not in srv.add_nodes(tid, sample["nodes"])
    return tid


def _hub(sample, act=0):
    return next(n["id"] for n in sample["nodes"] if n["act"] == act and not n.get("parent"))


def test_placing_a_row_under_a_hub_is_stored_laid_out_and_reported():
    tid = _draft(OUTLINE)
    hub = _hub(OUTLINE)
    r = srv.place_nodes(tid, {hub: {"arrange": "row"}})
    assert r["ok"] and r["layout"] == "tree", r
    assert r["hints"] == {hub: {"arrange": "row"}}
    kids = [n["id"] for n in OUTLINE["nodes"] if n.get("parent") == hub]
    # the cards named and their children come back with where they landed
    assert hub in r["placed"] and set(kids) <= set(r["placed"])
    assert len({r["placed"][k]["top"] for k in kids}) == 1       # one row
    assert r["placement"]["overlap_count"] == 0 and r["placement"]["off_margin"] == []
    assert srv.get_timeline(tid)["brief"]["placement"] == {hub: {"arrange": "row"}}
    # the build uses it and still verifies
    b = srv.build_timeline(tid)
    assert b.get("verify") == "passed", b


def test_hints_merge_a_null_removes_one_and_clear_and_reset_remove_more():
    tid = _draft(OUTLINE)
    hub, other = _hub(OUTLINE), _hub(OUTLINE, 1)
    srv.place_nodes(tid, {hub: {"arrange": "row"}, other: {"dx": 30}})
    r = srv.place_nodes(tid, {hub: {"dy": 20}})
    assert r["hints"][hub] == {"arrange": "row", "dy": 20}
    r = srv.place_nodes(tid, {hub: {"dy": None}})
    assert r["hints"][hub] == {"arrange": "row"}
    r = srv.place_nodes(tid, clear=[hub])
    assert r["hints"] == {other: {"dx": 30}}
    r = srv.place_nodes(tid, reset=True)
    assert r["hints"] == {} and srv.get_timeline(tid)["brief"]["placement"] == {}


def test_a_mistake_is_refused_with_the_reason_and_nothing_is_stored():
    tid = _draft(OUTLINE)
    hub = _hub(OUTLINE)
    r = srv.place_nodes(tid, {"no-such-card": {"dx": 1}})
    assert r["error"] == "unknown_nodes" and "no-such-card" in r["message"] and hub in r["node_ids"]
    r = srv.place_nodes(tid, {hub: {"arrange": "diagonal"}})
    assert r["error"] == "invalid_placement" and "arrange" in r["message"]
    r = srv.place_nodes(tid, {hub: {"colour": "red"}})
    assert r["error"] == "invalid_placement" and "unknown hint" in r["message"]
    r = srv.place_nodes(tid, {hub: "row"})
    assert r["error"] == "invalid_placement"
    assert not srv.get_timeline(tid)["brief"].get("placement")


def test_an_overlap_is_reported_so_it_can_be_fixed_before_building():
    tid = _draft(OUTLINE)
    hub = _hub(OUTLINE)
    first = next(n["id"] for n in OUTLINE["nodes"] if n.get("parent") == hub)
    # a floated card keeps its place while the flow runs on beneath it
    r = srv.place_nodes(tid, {hub: {"arrange": "column"}, first: {"float": True}})
    assert r["placement"]["overlap_count"] > 0 and "overlaps" in r["placement"], r
    assert "Fix any overlaps" in r["next"]
    b = srv.build_timeline(tid)
    assert any("overlap" in w for w in b["warnings"]), b


def test_order_changes_the_sibling_order_and_the_preview_can_show_every_box():
    tid = _draft(OUTLINE)
    hub = _hub(OUTLINE)
    kids = [n["id"] for n in OUTLINE["nodes"] if n.get("parent") == hub]
    last = kids[-1]
    srv.place_nodes(tid, {last: {"order": 1}})
    r = srv.run_layout_preview(tid, layout="tree", boxes=True)
    boxes = r["boxes"]
    assert set(boxes) == {n["id"] for n in OUTLINE["nodes"]}
    assert all(set(b) == {"x", "top", "w", "h"} for b in boxes.values())
    # the card moved to first place sits above-or-level with the others in a column
    assert boxes[last]["top"] <= min(boxes[k]["top"] for k in kids[:-1])
    assert "boxes" not in srv.run_layout_preview(tid)


def test_a_linear_timeline_has_nothing_to_place():
    tid = _draft(LINEAR)
    r = srv.place_nodes(tid, {LINEAR["nodes"][0]["id"]: {"dx": 5}})
    assert r["error"] == "needs_outline"


def test_the_guide_tells_the_chat_when_and_how_to_place_cards():
    g = (ROOT / "alto" / "interview_guide.md").read_text(encoding="utf-8")
    assert "**Placing cards.**" in g and "`place_nodes`" in g
    assert "Only when they ask" in g and 'arrange: "row"' in g
