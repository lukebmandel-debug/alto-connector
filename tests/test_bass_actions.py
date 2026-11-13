"""The action layer the UI calls: contract shapes, every state, and that docs/bass-api.md matches the code."""
import json
import re
import sys
from pathlib import Path

import pytest

from bass_support import bass_guard, ROOT  # noqa: F401
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bass_apidoc as D
from alto import mcp_server as srv
from alto.bass import actions as A
from alto.bass import config as P
from alto.bass import mock_anthropic as M

MC = P.MC


@pytest.fixture
def env(tmp_path):
    e = D.make_env(tmp_path / "store")
    yield e
    srv.set_store(None)


def go(e, mock_scn, request, **kw):
    e.mock.use(mock_scn)
    return e.acts.dispatch("student", request, **kw)


def build_req(**over):
    args = {"chips": D.CHIPS, "materials": D.MATERIALS, "consent": True, "accepted": True}
    args.update(over)
    return {"action": "build", "args": args}


# ── the doc is the contract ────────────────────────────────────────────────────────────────────────────────────

def doc_blocks():
    text = (ROOT / "docs" / "bass-api.md").read_text("utf-8")
    text = text.split("## Calls and states, with real responses", 1)[1]
    out = {}
    for m in re.finditer(r"### (.+?)\n\n.*?\nRequest:\n```json\n(.*?)\n```\n\nResponse:\n```json\n(.*?)\n```", text, re.S):
        out[m.group(1)] = (json.loads(m.group(2)), json.loads(m.group(3)))
    return out


def test_doc_exists_and_every_sample_matches_the_codes_shapes(tmp_path):
    fresh = D.samples(tmp_path / "doc")
    doc = doc_blocks()
    assert len(doc) == len(fresh) >= 18
    for sm in fresh:
        assert sm["title"] in doc, sm["title"]
        req, resp = doc[sm["title"]]
        assert D.shape(req) == D.shape(sm["request"]), sm["title"]
        assert D.shape(resp) == D.shape(sm["response"]), f"docs/bass-api.md is stale for {sm['title']}: run tests/bass_apidoc.py --write"
    srv.set_store(None)


def test_doc_covers_every_call_and_every_status(tmp_path):
    fresh = D.samples(tmp_path / "doc")
    calls = {sm["request"]["action"] for sm in fresh}
    assert calls == {"balance", "estimate", "propose", "build", "edit", "stop"}
    assert {sm["response"]["status"] for sm in fresh if sm["response"]} >= set(A.STATUSES)
    srv.set_store(None)


def test_every_result_is_plain_json_and_has_the_common_keys(tmp_path):
    keys = {"ok", "status", "code", "message", "action_id", "work_saved", "credits", "retryable", "events"}
    for sm in D.samples(tmp_path / "doc"):
        r = sm["response"]
        json.dumps(r)
        if sm["request"]["action"] in ("balance", "estimate", "stop"):
            continue
        assert keys <= set(r), (sm["title"], keys - set(r))
        assert r["status"] in A.STATUSES and r["ok"] == (r["status"] == "ok")
    srv.set_store(None)


# ── behaviour ──────────────────────────────────────────────────────────────────────────────────────────────────

def test_balance_and_labels(env):
    r = env.acts.balance("student")
    assert r == {"ok": True, "status": "ok", "credits": 500.0, "label": "500 credits", "available": True}
    assert A.credits_label(0) == "0 credits" and A.credits_label(1) == "less than 1 credit"
    assert A.credits_label(1000) == "1 credit" and A.credits_label(41_900) == "41 credits"   # never rounds up a balance
    from alto.bass.errors import POLICIES
    env.flags.trip(POLICIES["auth"])
    assert env.acts.balance("student")["available"] is False


def test_estimate_numbers(env, tmp_path):
    small = env.acts.estimate("student", "edit", text="add a card")
    assert small["show_prompt"] is False and small["short_by"] == 0 and small["have"] == 500.0
    big = env.acts.estimate("student", "build", D.MATERIALS)
    assert big["show_prompt"] is True and big["estimate_credits"] > 20 and "about" in big["credits_text"]
    poor = D.make_env(tmp_path / "poor", allowance=5)
    p = poor.acts.estimate("student", "build", D.MATERIALS)
    assert p["short_by"] == p["estimate_credits"] - 5 and p["have_label"] == "5 credits"
    assert env.mock.message_requests == []                    # estimating is count_tokens only, never a model turn
    assert env.acts.estimate("student", "weird")["code"] == "bad_input"


def test_propose_writes_nothing_uses_one_turn_and_hands_back_chips(env):
    r = go(env, M.Scenario("p", [M.Step(M.Reply([M.tool_use("propose_chips", D.CHIPS)]))]),
           {"action": "propose", "args": {"materials": D.MATERIALS}})
    assert r["status"] == "ok" and r["chips"] == D.CHIPS and r["work_saved"] is False
    assert len(env.mock.message_requests) == 1               # the chips tool ends the action: no second model turn
    body = env.mock.message_requests[0]["body"]
    assert body["model"] == P.HAIKU and body["output_config"] == {"effort": "medium"}
    assert [t["name"] for t in body["tools"]] == ["propose_chips"]
    srv.set_store(env.tools.store)
    tok = srv.current_uid.set("student")
    try:
        assert srv.list_projects()["projects"] == [] if "projects" in srv.list_projects() else True
    finally:
        srv.current_uid.reset(tok)


def test_propose_bad_chips_are_an_error_result_the_model_can_fix(env):
    bad = {"title": "x"}                                       # missing acts/entities
    r = go(env, M.Scenario("p", [M.Step(M.Reply([M.tool_use("propose_chips", bad)])),
                                 M.Step(M.Reply([M.tool_use("propose_chips", D.CHIPS)]))]),
           {"action": "propose", "args": {"materials": D.MATERIALS}})
    assert r["status"] == "ok" and r["chips"] == D.CHIPS and len(env.mock.message_requests) == 2


def test_build_needs_consent_and_a_plan_and_materials_before_any_model_call(env):
    assert env.acts.dispatch("student", build_req(consent=False))["code"] == "consent_required"
    assert env.acts.dispatch("student", build_req(consent="yes"))["code"] == "consent_required"
    assert env.acts.dispatch("student", build_req(chips={}))["code"] == "bad_input"
    assert env.acts.dispatch("student", build_req(materials=[]))["code"] == "bad_input"
    assert env.acts.dispatch("student", build_req(materials=[{"name": "x", "text": "y" * 700_000}]))["code"] == "too_large"
    assert env.mock.message_requests == []


def test_build_estimate_state_stops_before_the_model_then_accepted_runs(env):
    r = env.acts.dispatch("student", build_req(accepted=False))
    assert r["status"] == "estimate" and r["ok"] is False and r["show_prompt"] and r["action_id"] is None
    assert env.mock.message_requests == [] and r["credits"]["spent"] == 0
    r = go(env, D.build_scenario(M), build_req())
    assert r["status"] == "ok" and r["work_saved"] and r["timeline_id"] and r["cards"] == {"done": 6, "total": 6}
    assert all(q["body"]["model"] == P.SONNET for q in env.mock.message_requests)


def test_build_events_are_pushed_live_in_order_and_match_the_result(env):
    seen = []
    r = go(env, D.build_scenario(M), build_req(), on_event=seen.append)
    assert seen == r["events"]
    kinds = [e["event"] for e in seen]
    assert kinds[0] == "start" and kinds[-1] == "result" and set(kinds[1:-1]) == {"progress"}
    steps = [e["step"] for e in seen if e["event"] == "progress"]
    assert steps == ["setup", "setup", "consent", "chips", "cards", "links", "build"]
    cards = next(e for e in seen if e.get("step") == "cards")
    assert cards["detail"] == "cards 6 of 6" and cards["cards_done"] == 6 and cards["ok"] is True
    spent = [e["spent_credits"] for e in seen if e["event"] == "progress"]
    assert spent == sorted(spent) and spent[-1] > 0
    assert seen[-1]["status"] == "ok"


def test_stop_ends_a_build_at_the_next_step_and_keeps_the_work(env):
    def stopper(ev):
        if ev["event"] == "progress" and ev["step"] == "chips":
            env.acts.dispatch("student", {"action": "stop", "args": {"action_id": ev["action_id"]}})
    r = go(env, D.build_scenario(M), build_req(), on_event=stopper)
    assert r["status"] == "stopped" and r["code"] == "stopped" and r["work_saved"] is True
    assert "saved" in r["message"] and [e["step"] for e in r["events"] if e["event"] == "progress"][-1] == "chips"
    assert env.acts.stop("student", "act_9999")["stopping"] == "act_9999"      # stopping an unknown id is harmless ...
    assert env.engine._cancelled == set()                                       # ... and records nothing (fails closed)


def test_stop_before_the_first_turn_costs_nothing(env):
    env.engine.claim("act_0001", "student")                                     # the id was handed out; the first turn has not run
    assert env.engine.cancel("act_0001", "student") is True
    r = go(env, D.build_scenario(M), build_req())
    assert r["action_id"] == "act_0001" and r["status"] == "stopped" and r["work_saved"] is False
    assert r["credits"]["spent"] == 0 and env.mock.message_requests == []
    assert "saved" not in r["message"]                                          # never promise work that is not there


def test_no_credits_before_the_call_has_no_saved_work_line(env, tmp_path):
    broke = D.make_env(tmp_path / "broke", allowance=0)
    broke.mock.use(D.build_scenario(M))
    r = broke.acts.dispatch("student", build_req())
    assert r["status"] == "no_credits" and r["work_saved"] is False and "saved" not in r["message"]
    assert broke.mock.message_requests == [] and r["retryable"] is False


def test_capped_build_keeps_work_and_says_so(env):
    env.engine.cfg.per_action_cap_mc = 20_000              # room for the first turns' worst case (a Sonnet turn reserves about 17 credits), not for all of them
    r = go(env, D.build_scenario(M), build_req())
    assert r["status"] == "capped" and r["code"] == "action_cap" and r["work_saved"] and "saved" in r["message"]


def test_edit_runs_the_gate_then_edits_and_remembers_the_conversation(env):
    r = go(env, D.build_scenario(M), build_req())
    tid = r["timeline_id"]
    scn = M.Scenario("e", [M.Step(M.say("ON_TOPIC")), M.Step(M.say("Which card?")),
                           M.Step(M.say("ON_TOPIC")), M.Step(M.say("Renamed."))])
    r1 = go(env, scn, {"action": "edit", "args": {"timeline_id": tid, "text": "rename a card"}})
    assert r1["status"] == "ok" and r1["message"] == "Which card?" and r1["changed"] is False and r1["timeline_id"] == tid
    r2 = env.acts.dispatch("student", {"action": "edit", "args": {"timeline_id": tid, "text": "the first one"}})
    assert r2["message"] == "Renamed."
    last = env.mock.message_requests[-1]["body"]["messages"]
    assert [m["role"] for m in last] == ["user", "assistant", "user"] and "rename a card" in str(last[0])
    r3 = go(env, M.Scenario("e", [M.Step(M.say("ON_TOPIC")), M.Step(M.say("Fresh."))]),
            {"action": "edit", "args": {"timeline_id": tid, "text": "hi", "reset": True}})
    assert len(env.mock.message_requests[-1]["body"]["messages"]) == 1 and r3["message"] == "Fresh."
    assert [q["body"]["model"] for q in env.mock.message_requests[-2:]] == [P.HAIKU, P.HAIKU]


def test_edit_off_topic_is_free_and_not_remembered(env):
    r = go(env, M.off_topic_gate(False), {"action": "edit", "args": {"timeline_id": "t1", "text": "tell me a joke"}})
    assert r["status"] == "off_topic" and r["credits"]["spent"] == 0 and ("student", "t1") not in env.acts.conversations


def test_long_edit_conversations_are_trimmed_without_breaking_tool_pairs(env):
    tool_turn = [M.Step(M.say("ON_TOPIC")), M.Step(M.Reply([M.tool_use("list_projects", {})])), M.Step(M.say("Looked."))]
    env.acts.keep_messages = 4
    env.engine.cfg.actions_per_minute = 100
    scn = M.Scenario("e", tool_turn * 5)
    env.mock.use(scn)
    for i in range(5):
        r = env.acts.dispatch("student", {"action": "edit", "args": {"timeline_id": "t", "text": f"look {i}"}})
        assert r["status"] == "ok", r                           # the mock rejects any broken tool_use/tool_result pairing
    kept = env.acts.conversations[("student", "t")]
    assert len(kept) <= 5 and kept[0]["role"] == "user" and isinstance(kept[0]["content"], (str, list))
    assert not any(b.get("type") == "tool_result" for b in (kept[0]["content"] if isinstance(kept[0]["content"], list) else []))


def test_dispatch_rejects_malformed_requests_without_calling_the_model(env):
    for bad in ({}, {"action": "nope"}, {"action": "build", "args": "x"}, {"action": "edit", "args": {"text": "x"}},
                {"action": "balance", "args": {"extra": 1}}, "balance", None):
        r = env.acts.dispatch("student", bad)
        assert r["status"] == "error" and r["code"] == "bad_input" and r["ok"] is False, bad
    assert env.mock.requests == []


def test_error_and_refusal_states_are_retryable_or_not_as_documented(env):
    env.mock.inject(M.overloaded(times=99))
    r = go(env, M.Scenario("x", []), {"action": "propose", "args": {"materials": D.MATERIALS}})
    assert r["status"] == "error" and r["code"] == "overloaded" and r["retryable"] is True and r["credits"]["spent"] == 0
    env.mock.faults.clear()
    r = go(env, M.refusal_scenario(), {"action": "propose", "args": {"materials": D.MATERIALS}})
    assert r["status"] == "refused" and r["retryable"] is False and r["credits"]["spent"] == 0 and r["credits"]["refunded"] > 0


def test_paused_state_after_the_kill_switch(env):
    env.mock.inject(M.auth_error())
    r = go(env, M.Scenario("x", []), {"action": "propose", "args": {"materials": D.MATERIALS}})
    assert r["status"] == "error" and r["code"] == "auth" and "maintenance" in r["message"]
    seen = len(env.mock.requests)
    r = env.acts.dispatch("student", {"action": "propose", "args": {"materials": D.MATERIALS}})
    assert r["status"] == "paused" and r["retryable"] is True and len(env.mock.requests) == seen
    assert env.acts.balance("student")["available"] is False


def test_nothing_in_a_result_leaks_internals(tmp_path):
    blob = json.dumps([sm["response"] for sm in D.samples(tmp_path / "leak")])
    for needle in ("sk-" + "ant", "x-api-key", "claude-", "token", "Anthropic", "anthropic.com"):
        assert needle not in blob, needle
    srv.set_store(None)


# ── the guided start (interview suggestions): text on propose only, goal and extras ride in the chips ──────────────

def _first_user_text(env, i=0):
    c = env.mock.message_requests[i]["body"]["messages"][0]["content"]
    return c if isinstance(c, str) else "\n".join(b.get("text", "") for b in c if isinstance(b, dict))


def test_propose_carries_the_guided_start_and_build_edit_do_not(env):
    go(env, M.Scenario("p", [M.Step(M.Reply([M.tool_use("propose_chips", D.CHIPS)]))]),
       {"action": "propose", "args": {"materials": D.MATERIALS}})
    t = _first_user_text(env)
    assert A.GUIDED_START in t and t.index(A.GUIDED_START) < t.index("=== Material 1")      # materials come first in the student's data
    n = len(env.mock.message_requests)
    r = go(env, M.propose_chips(), build_req())
    assert len(env.mock.message_requests) > n and "Guided start" not in _first_user_text(env, n)


def test_the_opening_question_is_skipped_only_when_the_notes_give_both_goal_and_study_style():
    g = A.GUIDED_START
    assert "What is this for, and how do you like to study?" in g
    assert "Skip it ONLY when the materials or an earlier answer give BOTH what the work is for AND how they like to study" in g
    assert "ask just how they like to study" in g and "ask just what it is for" in g
    assert "NO menu of options" in g


def test_the_offers_are_questions_tailored_capped_final_and_closed_system():
    g = A.GUIDED_START
    assert "at most three things" in g and "An offer is a QUESTION" in g and "a no is final" in g
    assert "ends in a question mark" in g and "Never reclassify, regroup or relabel" in g and "never refuse it" in g
    assert "never add one that is not in their materials" in g and "never invent content" in g
    for kind in ("a quiz", "a decision tree", "a timeline", "flash cards"):
        assert kind in g
    assert "write the questions only from their notes" in g and "paste or upload" in g
    assert "ONE question per message" in g and "about 60 words" in g and "plain everyday words" in g
    assert "indentation or numbering" in g and "Where would you break this up, if anywhere?" in g and "at least two parts" in g
    assert "A stated habit IS the study style" in g
    assert "ONE kind of help per message" in g and "real yes/no test" in g and "plain simple timeline" in g
    assert "a study plan is one of the at-most-three offers of that round" in g and "propose at most six concepts" in g and "even after an add" in g
    assert len(g) < 7000                                                                       # compact: about 1,600 tokens


def test_goal_and_extras_are_optional_validated_and_reach_the_build_prompt(env):
    chips = dict(D.CHIPS, goal="MC final, learns by testing self",
                 extras=[{"kind": "quiz", "where": "Duty, Breach and Causation"}, {"kind": "cards"}])
    r = go(env, M.Scenario("p", [M.Step(M.Reply([M.tool_use("propose_chips", chips)]))]),
           {"action": "propose", "args": {"materials": D.MATERIALS}})
    assert r["status"] == "ok" and r["chips"] == chips                                         # kept as proposed
    bad = dict(D.CHIPS, extras=[{"kind": "podcast"}])
    r2 = go(env, M.Scenario("p", [M.Step(M.Reply([M.tool_use("propose_chips", bad)])),
                                  M.Step(M.Reply([M.tool_use("propose_chips", D.CHIPS)]))]),
            {"action": "propose", "args": {"materials": D.MATERIALS}})
    assert r2["chips"] == D.CHIPS                                                              # a bad kind is an error the model fixes
    n = len(env.mock.message_requests)
    go(env, M.propose_chips(), build_req(chips=chips))
    t = _first_user_text(env, n)
    assert "MC final, learns by testing self" in t and "Duty, Breach and Causation" in t and "build exactly those" in t
    n = len(env.mock.message_requests)
    go(env, M.propose_chips(), build_req())                                                    # no extras: the build prompt is unchanged
    assert len(env.mock.message_requests) > n and "build exactly those" not in _first_user_text(env, n)


def test_a_pasted_text_alone_is_a_text_material_and_the_closed_system_rule_stands(env):
    """The Upload step's "or paste your notes" sends {name: pasted-notes.txt, kind: notes, text}: no file, one text material."""
    pasted = [{"name": "pasted-notes.txt", "kind": "notes", "text": "Hearsay: an out-of-court statement offered for its truth. Exceptions: excited utterance, present sense impression."}]
    r = go(env, M.Scenario("p", [M.Step(M.Reply([M.tool_use("propose_chips", D.CHIPS)]))]), {"action": "propose", "args": {"materials": pasted}})
    assert r["status"] == "ok" and r["chips"] == D.CHIPS and r["work_saved"] is False
    t = _first_user_text(env)
    assert "=== Material 1: pasted-notes.txt (notes) ===" in t and "excited utterance" in t
    assert "Build only from their materials; never invent content." in t                  # the closed-system rule rides with it
    assert env.acts.estimate("student", "build", pasted)["estimate_credits"] > 0
    assert env.acts.propose("student", [])["code"] == "bad_input"                          # still nothing without any material
