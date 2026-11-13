"""Bass makes the study plan: the timeline's own nodes and what the student gave in, a saved plan out, closed system, mock only.

Nothing is saved unless the check passes (every node theirs, every signal one they gave, every why quoting it, every day in the
window); a failure refunds the call. The entitlement check runs first. No network, no key, no count_tokens."""
import datetime as dt
import json
import sys
from pathlib import Path

import pytest

from bass_support import bass_guard, ROOT  # noqa: F401
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bass_apidoc as D
from alto import entitlements as ENT
from alto import mcp_server as srv
from alto.bass import mock_anthropic as M
from alto.bass import studyplan as SP

OUTLINE = json.loads((ROOT / "samples" / "outline_brief.json").read_text("utf-8"))
TODAY = dt.date(2026, 11, 2)                                 # a Monday
NODES = OUTLINE["nodes"]
REM = next(n for n in NODES if "remed" in n["title"].lower() or "damages" in n["title"].lower())
OFFER = next(n for n in NODES if n["title"] == "Offer")
UNMARKED = next(n for n in NODES if n["id"] != OFFER["id"] and n["id"] != NODES[0]["id"])


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")
    monkeypatch.delenv("ALTO_PAYWALL", raising=False)
    yield
    ENT.set_plan_lookup(None)
    srv.set_store(None)


@pytest.fixture
def env(tmp_path):
    e = D.make_env(tmp_path / "store", allowance=2000)
    e.acts.engine.cfg.actions_per_minute = 100
    yield e
    srv.set_store(None)


def _source(e):
    e.mock.use(M.build("Law", OUTLINE["brief"], OUTLINE["nodes"], OUTLINE["connections"]))
    out = e.acts.dispatch("student", {"action": "build", "args": {"chips": D.CHIPS, "materials": D.MATERIALS, "consent": True, "accepted": True}})
    assert out["ok"], out
    return out["timeline_id"]


def _item(node, day, why, signal):
    return {"node": node["id"] if isinstance(node, dict) else node, "day": day, "why": why, "signal": signal}


GOOD = [_item(REM, "2026-11-03", "You told me you are weak on remedies.", "told"),
        _item(OFFER, "2026-11-04", "You marked Offer as Still learning.", "marks"),
        _item(NODES[0], "2026-11-05", "Your exam is on 2026-11-20.", "exam")]
ANS = {"exam_date": "2026-11-20", "days_per_week": 5, "minutes_per_day": 60, "weak": ["remedies"], "told": ""}
MARKS = {OFFER["id"]: "still_learning"}


def _run(e, tid, items, **kw):
    e.mock.use(M.Scenario("plan", [M.Step(M.Reply([M.text("Here is the plan."), M.tool_use("propose_study_plan", {"items": items})]))]))
    args = {"timeline_id": tid, "answers": ANS, "marks": MARKS, "consent": True, "accepted": True, "today": TODAY}
    args.update(kw)
    return e.acts.dispatch("student", {"action": "make_study_plan", "args": args})


# ── the grounding check, pure ──────────────────────────────────────────────

def _g(items, answers=None, marks=None, quiz=None, today=TODAY):
    a, m, q, bad = SP.clean_inputs(answers if answers is not None else ANS, marks if marks is not None else MARKS, quiz or {})
    assert bad is None
    return SP.ground_plan(NODES, items, a, m, q, today)


def test_a_grounded_plan_passes_and_says_what_it_is():
    g = _g(GOOD)
    assert g["ok"] and g["nodes"] == 3 and g["days"] == 3
    assert SP.summary([{"node": i["node"], "day": i["day"]} for i in GOOD]) == "3 nodes, Tue-Thu"
    assert SP.summary([{"node": "a", "day": "2026-11-02"}, {"node": "b", "day": "2026-11-04"}, {"node": "c", "day": "2026-11-06"}]) == "3 nodes, Mon, Wed and Fri"
    assert SP.summary([{"node": "a", "day": "2026-11-02"}]) == "1 node, Mon"


@pytest.mark.parametrize("bad,needle", [
    (_item("not-a-node", "2026-11-03", "You told me remedies.", "told"), "not in this timeline"),
    (_item(REM, "2026-11-03", "It matters a lot.", "told"), "does not quote what the student said"),
    (_item(UNMARKED, "2026-11-03", "You marked it Still learning.", "marks"), "was not marked Still learning"),
    (_item(OFFER, "2026-11-03", "It is important.", "marks"), "does not quote the mark"),
    (_item(NODES[3], "2026-11-03", "Your quiz was low.", "quiz"), "no low quiz score"),
    (_item(NODES[0], "2026-11-03", "It looks key.", "exam"), "does not name the exam"),
    (_item(NODES[0], "2026-11-03", "It is in the syllabus.", "syllabus"), "no syllabus was given"),
    (_item(REM, "2026-11-01", "You told me remedies.", "told"), "outside"),
    (_item(REM, "2026-11-21", "You told me remedies.", "told"), "outside"),
    (_item(REM, "someday", "You told me remedies.", "told"), "not a date"),
    (_item(REM, "2026-11-03", "You told me remedies.", "importance"), "not one of the student"),
])
def test_ground_fails_closed(bad, needle):
    g = _g([bad])
    assert g["ok"] is False and any(needle in r for r in g["reasons"]), g


def test_no_exam_date_means_a_two_week_window_and_no_exam_signal():
    a = dict(ANS, exam_date="")
    assert _g([_item(REM, "2026-11-16", "You told me remedies.", "told")], answers=a)["ok"]
    assert not _g([_item(REM, "2026-11-17", "You told me remedies.", "told")], answers=a)["ok"]                 # day 15
    assert "no exam date" in " ".join(_g([_item(NODES[0], "2026-11-03", "Your exam is soon.", "exam")], answers=a)["reasons"])


def test_a_quiz_score_and_a_syllabus_are_signals_when_the_student_gave_them():
    q = {NODES[3]["id"]: 40}
    assert _g([_item(NODES[3], "2026-11-03", "Your quiz was 40%.", "quiz")], quiz=q)["ok"]
    assert not _g([_item(NODES[3], "2026-11-03", "Your quiz was 40%.", "quiz")], quiz={NODES[3]["id"]: 90})["ok"]
    a = dict(ANS, syllabus="Week 1: Formation. Week 2: " + NODES[3]["title"])
    assert _g([_item(NODES[3], "2026-11-03", "It is in your syllabus.", "syllabus")], answers=a)["ok"]


def test_inputs_are_bounded_and_typed():
    assert SP.clean_inputs({"weak": ["x" * 121]}, None, None)[3]
    assert SP.clean_inputs({"weak": ["a"] * 21}, None, None)[3]
    assert SP.clean_inputs({"told": "x" * 1001}, None, None)[3]
    a, m, q, bad = SP.clean_inputs({"weak": [" remedies ", ""]}, {"n1": "still_learning", "n2": "bogus"}, {"n1": 50, "n2": 101, "n3": True})
    assert bad is None and a["weak"] == ["remedies"] and m == {"n1": "still_learning"} and q == {"n1": 50}


# ── the action ─────────────────────────────────────────────────────────────

def test_it_estimates_first_at_a_safe_constant_without_calling_the_model(env):
    tid = _source(env)
    n, bal = len(env.mock.message_requests), env.ledger.balance_mc("student")
    out = env.acts.dispatch("student", {"action": "make_study_plan", "args": {"timeline_id": tid, "answers": ANS, "consent": True, "today": TODAY}})
    assert out["status"] == "estimate" and out["show_prompt"] is True and out["kind"] == "make_study_plan" and out["nodes_in"] == len(NODES)
    assert out["estimate_credits"] >= SP.STUDYPLAN_SAFE_CREDITS
    assert len(env.mock.message_requests) == n and env.ledger.balance_mc("student") == bal


def test_a_grounded_plan_is_saved_in_the_brief_and_the_page_is_rebuilt(env):
    tid = _source(env)
    out = _run(env, tid, GOOD)
    assert out["ok"] and out["plan_saved"] is True and out["nodes"] == 3 and out["days"] == 3 and out["summary"] == "3 nodes, Tue-Thu"
    assert out["credits"]["spent"] > 0 and out["page_rebuilt"] is True and out["grounding"] == []
    st = srv.get_store()
    plan = st.get_timeline("student", tid)["brief"]["study_plan"]
    assert plan["exam_date"] == "2026-11-20" and plan["days_per_week"] == 5 and [i["day"] for i in plan["items"]] == ["2026-11-03", "2026-11-04", "2026-11-05"]
    assert len(st.list_nodes("student", tid)) == len(NODES)                              # the nodes are untouched


@pytest.mark.parametrize("bad", [
    [_item("not-a-node", "2026-11-03", "You told me remedies.", "told")],
    [_item(REM, "2026-11-03", "It matters a lot.", "told")],
    [_item(UNMARKED, "2026-11-03", "You marked it Still learning.", "marks")],
])
def test_an_ungrounded_plan_saves_nothing_and_refunds_the_call(env, bad):
    tid = _source(env)
    bal = env.ledger.balance_mc("student")
    out = _run(env, tid, bad)
    assert out["ok"] is False and out["code"] == "plan_failed" and out["plan_saved"] is False and out["grounding"]
    assert "nothing was saved" in out["message"] and out["work_saved"] is False
    assert "study_plan" not in srv.get_store().get_timeline("student", tid)["brief"]
    assert env.ledger.balance_mc("student") == bal                                       # nothing charged


def test_the_entitlement_check_runs_first_with_zero_requests_and_zero_credits(env, monkeypatch):
    tid = _source(env)
    monkeypatch.setenv("ALTO_PAYWALL", "1")
    monkeypatch.setitem(ENT.FEATURE_MIN_PLAN, "study_plan", "plus")
    ENT.set_plan_lookup(lambda uid: "free")
    n, bal = len(env.mock.message_requests), env.ledger.balance_mc("student")
    out = env.acts.dispatch("student", {"action": "make_study_plan", "args": {"timeline_id": tid, "answers": ANS, "consent": True, "accepted": True}})
    assert out["code"] == "needs_plan" and out["plan"] == "plus" and out["feature"] == "study_plan" and "Study plan" in out["message"]
    assert len(env.mock.message_requests) == n and env.ledger.balance_mc("student") == bal


def test_it_refuses_what_it_must_not_do(env):
    tid = _source(env)
    base = {"timeline_id": tid, "answers": ANS, "today": TODAY}
    assert env.acts.dispatch("student", {"action": "make_study_plan", "args": {**base, "consent": False}})["code"] == "consent_required"
    assert env.acts.dispatch("student", {"action": "make_study_plan", "args": {**base, "timeline_id": "nope", "consent": True}})["code"] == "bad_input"
    assert env.acts.dispatch("student", {"action": "make_study_plan", "args": {**base, "answers": {"weak": ["x" * 500]}, "consent": True}})["code"] == "bad_input"
    assert env.acts.dispatch("student", {"action": "make_study_plan", "args": {"answers": ANS, "consent": True}})["code"] == "bad_input"


def test_the_model_is_offered_only_the_plan_tool(env):
    tid = _source(env)
    _run(env, tid, GOOD)
    req = env.mock.message_requests[-1]["body"]
    assert [t["name"] for t in req["tools"]] == ["propose_study_plan"]                   # nothing that writes


# ── the beta guard ─────────────────────────────────────────────────────────

def test_the_beta_guard_refuses_a_feature_not_in_the_plan_before_any_hold_or_request(tmp_path, monkeypatch):
    from bass_beta_support import make_stack, req
    s = make_stack(tmp_path)
    monkeypatch.setenv("ALTO_PAYWALL", "1")
    monkeypatch.setitem(ENT.FEATURE_MIN_PLAN, "study_plan", "pro")
    ENT.set_plan_lookup(lambda uid: "plus")
    n = len(s.mock.message_requests)
    out = s.svc.handle(req({"action": "make_study_plan", "args": {"timeline_id": "t1", "answers": ANS, "consent": True, "accepted": True}}))
    assert out["code"] == "needs_plan" and out["status"] == "refused" and out["retryable"] is False and "Pro" in out["message"]
    assert len(s.mock.message_requests) == n and s.ledger.held_mc("u_tester1") == 0
    ENT.set_plan_lookup(lambda uid: "pro")
    out = s.svc.handle(req({"action": "make_study_plan", "args": {"timeline_id": "t1", "answers": ANS, "consent": True, "accepted": True}}))
    assert out["code"] == "bad_input"                                                     # open: on to the action (no such timeline)
