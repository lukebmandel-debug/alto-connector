"""The connector's study plan tools (set_study_plan, get_study_signals) and the one entitlement check's `study_plan` feature row."""
import copy
import datetime as dt
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import entitlements as E          # noqa: E402
from alto import mcp_server as srv          # noqa: E402
from alto.store.local import LocalStore     # noqa: E402

SAMPLE = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def clean(tmp_path, monkeypatch):
    srv.set_store(LocalStore(tmp_path))
    monkeypatch.delenv("ALTO_PAYWALL", raising=False)
    monkeypatch.setattr(E, "FEATURE_MIN_PLAN", dict(E.FEATURE_MIN_PLAN))
    yield
    E.set_plan_lookup(None)
    srv.set_store(None)


def _tl():
    pid = srv.create_project("Law", "1L", "studying")["project_id"]
    tid = srv.create_timeline(pid, SAMPLE["brief"])["timeline_id"]
    srv.record_materials_consent(tid, [{"name": "notes", "kind": "notes"}], True)
    r = srv.add_nodes(tid, SAMPLE["nodes"])
    assert "error" not in r, r
    return tid


def _day(n=1):
    return (dt.date.today() + dt.timedelta(days=n)).isoformat()


def _item(node, n=1, why="You told me remedies are weak.", signal="told"):
    return {"node": node, "day": _day(n), "why": why, "signal": signal}


def test_in_the_beta_the_study_plan_feature_is_open_and_checked_like_a_format(monkeypatch):
    assert E.FEATURES == ("study_plan",) and E.allowed("u", "study_plan") == {"ok": True}
    assert E.allowed("u", "orchestra")["ok"] is False
    monkeypatch.setenv("ALTO_PAYWALL", "1")
    monkeypatch.setitem(E.FEATURE_MIN_PLAN, "study_plan", "plus")
    E.set_plan_lookup(lambda uid: "free")
    r = E.allowed("u", "study_plan")
    assert r["ok"] is False and r["needs_plan"] == "plus" and "Study plan" in r["message"] and "Plus" in r["message"]
    E.set_plan_lookup(lambda uid: "plus")
    assert E.allowed("u", "study_plan")["ok"] is True
    assert {r["id"] for r in E.formats_for("u")} == set(E.FORMATS)                       # features are not formats


def test_get_study_signals_lists_the_nodes_and_says_the_marks_are_the_students_to_give():
    tid = _tl()
    r = srv.get_study_signals(tid)
    ids = {n["id"] for n in r["nodes"]}
    assert ids == {n["id"] for n in SAMPLE["nodes"]} and r["plan"] is None
    assert set(r["nodes"][0]) == {"id", "title", "act", "parent", "flags", "cards", "quiz"}
    assert r["signals"] == ["marks", "quiz", "exam", "told", "syllabus"]


def test_set_study_plan_stores_a_checked_plan_and_replaces_or_adds():
    tid = _tl()
    ids = [n["id"] for n in SAMPLE["nodes"]]
    r = srv.set_study_plan(tid, [_item(ids[2], 3), _item(ids[0], 1)], exam_date=_day(20), days_per_week=5, minutes_per_day=90)
    assert r["ok"] and r["items"] == 2 and r["days"] == 2 and r["first_day"] == _day(1) and r["last_day"] == _day(3)
    plan = srv.get_study_signals(tid)["plan"]
    assert [i["node"] for i in plan["items"]] == [ids[0], ids[2]] and plan["exam_date"] == _day(20) and plan["minutes_per_day"] == 90
    r = srv.set_study_plan(tid, [_item(ids[1], 2)], replace=False)                       # add: the rest of the plan and its exam date stand
    assert r["items"] == 3
    plan = srv.get_study_signals(tid)["plan"]
    assert plan["exam_date"] == _day(20) and plan["days_per_week"] is None or plan["days_per_week"] == 5
    r = srv.set_study_plan(tid, [_item(ids[3], 4)])                                      # replace (the default): only this
    assert r["items"] == 1 and [i["node"] for i in srv.get_study_signals(tid)["plan"]["items"]] == [ids[3]]


def test_a_bad_plan_is_refused_whole_and_nothing_is_stored():
    tid = _tl()
    ids = [n["id"] for n in SAMPLE["nodes"]]
    srv.set_study_plan(tid, [_item(ids[0])])
    before = srv.get_study_signals(tid)["plan"]
    for bad, needle in (([_item("not-a-node")], "not in this timeline"),
                        ([{**_item(ids[0]), "day": "tomorrow"}], "not a date"),
                        ([_item(ids[0], 400)], "more than 366 days"),
                        ([_item(ids[0], why="")], "why is required"),
                        ([_item(ids[0], why="x" * 201)], "at most 200"),
                        ([_item(ids[0]), _item(ids[0], why="again")], "already planned"),
                        ([_item(ids[0], signal="importance")], "signal")):
        r = srv.set_study_plan(tid, bad)
        assert r.get("error") == "invalid_plan" and needle in r["message"], (needle, r)
    assert srv.get_study_signals(tid)["plan"] == before                                  # untouched


def test_the_plan_is_behind_the_consent_gate_and_the_feature_check(monkeypatch):
    pid = srv.create_project("Law", "1L", "studying")["project_id"]
    tid = srv.create_timeline(pid, SAMPLE["brief"])["timeline_id"]                      # no consent yet
    assert srv.set_study_plan(tid, [_item("x")]).get("error") == "consent_gate"
    monkeypatch.setenv("ALTO_PAYWALL", "1")
    monkeypatch.setitem(E.FEATURE_MIN_PLAN, "study_plan", "pro")
    E.set_plan_lookup(lambda uid: "free")
    for r in (srv.set_study_plan(tid, [_item("x")]), srv.get_study_signals(tid)):
        assert r.get("error") == "needs_plan" and r["feature"] == "study_plan" and r["plan"] == "pro"


def test_the_plan_survives_a_build_and_a_deleted_nodes_item_drops():
    tid = _tl()
    ids = [n["id"] for n in SAMPLE["nodes"]]
    srv.set_study_plan(tid, [_item(ids[0]), _item(ids[1], 2)])
    r = srv.build_timeline(tid)
    assert "error" not in r, r
    srv.delete_nodes(tid, [ids[1]])
    plan = srv.get_study_signals(tid)["plan"]
    assert len(plan["items"]) == 2                                                       # stored as the student set it; the page build drops the gone one
    from alto.build.builder import load_brief
    from alto.build.sanitize import sanitize_brief
    doc = srv.get_store().get_timeline(srv.uid(), tid)
    stored = [{k: v for k, v in n.items() if not k.startswith("_")} for n in srv.get_store().list_nodes(srv.uid(), tid)]     # (the store adds _seq)
    b, nodes, _ = load_brief({"brief": doc["brief"], "nodes": stored})
    sanitize_brief(b, nodes)
    assert [i["node"] for i in b.study_plan["items"]] == [ids[0]]
