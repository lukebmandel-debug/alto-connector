"""The agent loop against the simulated API and the REAL tools: metering, caps, refunds, resume."""
import json

import pytest

from bass_support import bass_guard, ROOT  # noqa: F401
from alto import mcp_server as srv
from alto.store.local import LocalStore
from alto.bass import engine as E
from alto.bass import meter, config as P
from alto.bass import mock_anthropic as M
from alto.bass.client import make_client
from alto.bass.errors import Flags
from alto.bass.ledger import Ledger, MemoryStore
from alto.bass.tools import ToolBox

SAMPLE = json.loads((ROOT / "samples" / "contracts_brief.json").read_text(encoding="utf-8"))
MC = P.MC
S = P.SONNET


class Env:
    pass


@pytest.fixture
def env(tmp_path):
    e = Env()
    e.mock = M.MockAnthropic()
    e.client = make_client("mock", mock=e.mock)
    e.ledger = Ledger(MemoryStore())
    e.ledger.grant_allowance("u1", 500)
    e.tools = ToolBox(LocalStore(tmp_path / "store"))
    e.slept = []
    e.flags = Flags()
    e.engine = E.Engine(e.client, e.ledger, e.tools, flags=e.flags, sleep=e.slept.append)
    yield e
    srv.set_store(None)


def build_scn():
    return M.build("Law School", SAMPLE["brief"], SAMPLE["nodes"], SAMPLE["connections"])


def roles(messages):
    return [m["role"] for m in messages]


def test_full_build_end_to_end(env):
    env.mock.use(build_scn())
    r = env.engine.run_action("u1", "Build my contracts timeline from my notes.", kind="build")
    assert r.status == "done", (r.status, r.user_message, r.tool_calls)
    assert r.text == "Your timeline is built." and r.user_message == r.text
    assert [c["name"] for c in r.tool_calls] == ["create_project", "create_timeline", "record_materials_consent",
                                                  "set_entities", "add_nodes", "add_connections", "build_timeline"]
    assert not any(c["is_error"] for c in r.tool_calls) and r.wrote
    assert r.turns == 8
    assert roles(r.messages) == ["user"] + ["assistant", "user"] * 7 + ["assistant"]
    # the simulated API validated every request the loop made (alternation, tool_use/tool_result pairing)
    sent = env.mock.message_requests
    assert len(sent) == 8 and all(q["body"]["model"] == S for q in sent)
    # the page really got built in the temp store
    tid = next(d["timeline_id"] for m in r.messages if m["role"] == "user" and isinstance(m["content"], list)
               for b in m["content"] if b.get("type") == "tool_result"
               for d in [json.loads(b["content"])] if isinstance(d, dict) and d.get("timeline_id"))
    got = json.loads(env.tools.execute("u1", "get_timeline", {"timeline_id": tid}).content)
    assert len(got["node_ids"]) == 6 and got["status"] != "draft"


def test_metering_matches_the_usage_the_mock_reported(env):
    env.mock.use(build_scn())
    r = env.engine.run_action("u1", "Build it.")
    want = sum(meter.credits_for_usage(S, m["usage"]) for m in env.mock.responses)
    assert want > 0 and r.charged_mc == want and r.spent_mc == want and r.refunded_mc == 0
    assert env.ledger.balance_mc("u1") == 500 * MC - want and env.ledger.held_mc("u1") == 0
    assert env.ledger.action_spent_mc("u1", r.action_id) == want
    # the system prompt + tools were cached: turn 1 wrote the cache, later turns read it
    us = [m["usage"] for m in env.mock.responses]
    assert us[0]["cache_creation_input_tokens"] > 0 and all(u["cache_read_input_tokens"] > 0 for u in us[1:])


def test_holds_are_worst_case_and_never_exceed_what_the_cap_allows(env):
    env.mock.use(M.Scenario("t", [M.Step(M.say("hi"))]))
    env.engine.run_action("u1", "hello there")
    kinds = [e["kind"] for e in env.ledger.entries("u1")]
    assert kinds[-2:] == ["usage", "release"]


def test_parallel_tool_use_returns_one_user_message(env):
    env.mock.use(M.parallel_tool_use([("create_project", {"name": "A"}), ("create_project", {"name": "B"}),
                                      ("list_projects", {})]))
    r = env.engine.run_action("u1", "make two projects")
    assert r.status == "done"
    results = r.messages[2]
    assert results["role"] == "user" and len(results["content"]) == 3
    assert [b["type"] for b in results["content"]] == ["tool_result"] * 3
    assert [b["tool_use_id"] for b in results["content"]] == [b["id"] for b in r.messages[1]["content"]
                                                                if b["type"] == "tool_use"]
    assert len(env.mock.message_requests) == 2              # one turn for the calls, one after ALL results


def test_tool_errors_are_flagged_is_error_and_the_model_continues(env):
    env.mock.use(M.Scenario("t", [
        M.Step(M.Reply([M.tool_use("add_nodes", {"timeline_id": "nope", "nodes": []}),
                        M.tool_use("add_nodes", {"timeline_id": "nope"})])),
        M.Step(M.say("Sorry, that did not work. Shall I start over?"))]))
    r = env.engine.run_action("u1", "add a card")
    res = r.messages[2]["content"]
    assert all(b.get("is_error") for b in res) and r.status == "done" and not r.wrote
    assert "invalid_input" in res[1]["content"]
    assert [c["is_error"] for c in r.tool_calls] == [True, True]


def test_edit_card_chat_turn(env):
    p = env.tools.execute("u1", "create_project", {"name": "P"})
    env.mock.use(M.edit_card("x", {"id": "n1", "act": 0, "tag": "t", "title": "T", "desc": "d"}))
    r = env.engine.run_action("u1", "Change the title of card n1", kind="edit")
    assert r.status == "done" and r.tool_calls[0]["name"] == "add_nodes"
    assert env.mock.message_requests[0]["body"]["max_tokens"] == P.CHAT_MAX_TOKENS


def test_off_topic_gate_answers_with_the_canned_reply_and_costs_the_student_nothing(env):
    env.mock.use(M.off_topic_gate(on_topic=False))
    before = env.ledger.balance_mc("u1")
    r = env.engine.run_action("u1", "write me a poem about cats", kind="chat")
    assert r.status == "off_topic" and r.text == E.OFF_TOPIC_REPLY and r.turns == 0
    assert [q["body"]["model"] for q in env.mock.message_requests] == [P.HAIKU]      # the cheap gate model only
    assert env.ledger.balance_mc("u1") == before and r.spent_mc == 0
    assert any(e["kind"] == "absorbed" and e["note"] == "gate" for e in env.ledger.entries("u1"))


def test_on_topic_chat_passes_the_gate_then_runs_on_sonnet(env):
    env.mock.use(M.Scenario("t", [M.Step(M.say("ON_TOPIC")), M.Step(M.say("Sure, which card?"))]))
    r = env.engine.run_action("u1", "can you rename a card", kind="chat")
    assert r.status == "done" and r.text == "Sure, which card?"
    assert [q["body"]["model"] for q in env.mock.message_requests] == [P.HAIKU, P.HAIKU]   # chat runs on Haiku


def test_refusal_refunds_the_turn_and_the_empty_action(env):
    env.mock.use(M.refusal_scenario())
    before = env.ledger.balance_mc("u1")
    r = env.engine.run_action("u1", "something refused")
    assert r.status == "refused" and r.code == "refused" and "Nothing was charged" in r.user_message
    assert r.charged_mc > 0 and r.refunded_mc == r.charged_mc and r.spent_mc == 0
    assert env.ledger.balance_mc("u1") == before
    assert r.detail == {"category": "general_harms"}


def test_refusal_mid_build_refunds_only_the_refused_turn(env):
    env.mock.use(M.Scenario("t", [M.Step(M.Reply([M.tool_use("create_project", {"name": "Kept"})])),
                                  M.Step(M.refusal())]))
    r = env.engine.run_action("u1", "build")
    assert r.status == "refused" and r.wrote
    assert 0 < r.spent_mc < r.charged_mc                      # the good first turn stays charged


def test_max_tokens_stops_without_running_a_cut_off_tool_call(env):
    env.mock.use(M.Scenario("t", [M.Step(M.Reply([M.text("x " * 1000), M.tool_use("create_project", {"name": "Z"})]))]))
    env.engine.cfg.build_max_tokens = 50
    env.engine.cfg.thinking["build"] = "off"                    # with thinking on, max_tokens is never below the thinking floor
    r = env.engine.run_action("u1", "go")
    assert r.status == "max_tokens" and r.code == "max_tokens" and r.tool_calls == [] and not r.wrote
    assert "cut off" in r.user_message and r.messages[-1]["role"] == "assistant"
    assert not any(b.get("type") == "tool_use" for b in r.messages[-1]["content"])


def test_per_action_cap_stops_the_loop_and_keeps_partial_work(env):
    env.mock.use(build_scn())
    env.engine.cfg.per_action_cap_mc = 20_000                    # the first turns' worst case fits (about 17 credits each), later ones do not
    r = env.engine.run_action("u1", "Build it.")
    assert r.status == "capped" and r.code == "action_cap" and "saved" in r.user_message
    assert 1 <= r.turns < 8 and r.wrote                          # stopped part-way; what was written stays written
    assert 0 < r.spent_mc < 20_000                               # finding M7: never past the cap, not even by one turn
    assert roles(r.messages)[-1] == "user"                       # history ends on tool results: ready to resume
    # nothing was rolled back
    assert env.ledger.balance_mc("u1") == 500 * MC - r.spent_mc


def test_resume_from_the_returned_history_continues_the_same_build(env):
    env.mock.use(build_scn())
    env.engine.cfg.per_action_cap_mc = 2500
    first = env.engine.run_action("u1", "Build it.")
    assert first.status == "capped"
    env.engine.cfg.per_action_cap_mc = 300 * MC
    second = env.engine.run_action("u1", "Continue.", history=first.messages)     # the mock scenario carries on
    assert second.status == "done"
    assert roles(second.messages)[0] == "user" and roles(second.messages)[-1] == "assistant"


def test_no_credits_fails_before_any_call(env):
    env.ledger = Ledger(MemoryStore())
    env.engine.ledger = env.ledger
    env.mock.use(M.Scenario("t", [M.Step(M.say("never"))]))
    r = env.engine.run_action("broke", "Build it.")
    assert r.status == "no_credits" and r.code == "no_credits" and "saved" in r.user_message
    assert env.mock.message_requests == [] and r.turns == 0 and r.spent_mc == 0


def test_balance_runs_out_part_way_and_stops_cleanly(env):
    env.ledger.store.docs.clear()
    env.ledger.grant_allowance("u1", 20)                          # too little for the whole build
    env.mock.use(build_scn())
    r = env.engine.run_action("u1", "Build it.")
    assert r.status in ("no_credits", "done")
    bal = env.ledger.balance_mc("u1")
    assert bal >= 0 and env.ledger.held_mc("u1") == 0
    if r.status == "no_credits":
        assert r.wrote and r.turns >= 1


def test_streaming_events_reach_the_ui_callback(env):
    env.mock.use(M.Scenario("t", [M.Step(M.say("Here is a longer answer for the student."))]))
    seen = []
    env.engine.run_action("u1", "hi", on_event=lambda ev: seen.append(ev.type))
    assert seen[0] == "message_start" and "text" in seen and seen[-1] == "message_stop"


def test_estimate_prompt_uses_the_threshold(env):
    big = env.engine.estimate("build", first_input_tokens=9000)
    small = env.engine.estimate("chat", first_input_tokens=1000)
    assert big.show_prompt and "about" in big.message
    assert not small.show_prompt


def test_rate_limit_per_account(env):
    env.engine.cfg.actions_per_minute = 2
    env.mock.use(M.Scenario("t", [M.Step(M.say("a")), M.Step(M.say("b")), M.Step(M.say("c"))]))
    assert env.engine.run_action("u1", "one").status == "done"
    assert env.engine.run_action("u1", "two").status == "done"
    r = env.engine.run_action("u1", "three")
    assert r.status == "busy" and r.code == "busy" and len(env.mock.message_requests) == 2
    assert env.engine.run_action("someone-else", "x").status in ("no_credits", "done")   # other accounts unaffected


def test_history_blocks_survive_a_thinking_turn(env):
    env.mock.use(M.Scenario("t", [M.Step(M.Reply([M.thinking("let me see"), M.tool_use("list_projects", {})])),
                                  M.Step(M.say("Nothing yet."))]))
    r = env.engine.run_action("u1", "what do I have?")
    assert r.status == "done"
    types = [b["type"] for b in r.messages[1]["content"]]
    assert types == ["thinking", "thinking", "tool_use"]         # the model's own (bound, empty text) and the scripted one: passed back unchanged
    assert all(b["signature"] for b in r.messages[1]["content"][:2])
    assert env.mock.message_requests[1]["body"]["messages"][1]["content"] == r.messages[1]["content"]    # ... and the API accepted them


def test_models_per_kind_build_sonnet_edit_and_chat_haiku_and_metered_at_that_models_price(env):
    cfg = env.engine.cfg
    assert (cfg.model_for("build"), cfg.model_for("edit"), cfg.model_for("chat"), cfg.gate_model) == (S, P.HAIKU, P.HAIKU, P.HAIKU)
    for kind, model in (("build", S), ("edit", P.HAIKU), ("chat", P.HAIKU)):
        env.mock.requests.clear()
        env.mock.responses.clear()
        env.mock.use(M.Scenario("t", [M.Step(M.say("ON_TOPIC")), M.Step(M.say("fine"))] if kind == "chat"
                                else [M.Step(M.say("fine"))]))
        env.engine._recent.clear()
        before = env.ledger.balance_mc("u1")
        r = env.engine.run_action("u1", "hello", kind=kind)
        assert r.status == "done"
        main = [q for q in env.mock.message_requests][-1]
        assert main["body"]["model"] == model
        assert r.charged_mc == meter.credits_for_usage(model, env.mock.responses[-1]["usage"])
        assert before - env.ledger.balance_mc("u1") == r.spent_mc
    assert env.engine.estimate("chat", 3000).mc < env.engine.estimate("build", 3000).mc
    assert env.engine.estimate("edit", 3000).mc == meter.estimate_action(P.HAIKU, 3000, cfg.chat_max_tokens, 3).mc
    assert env.engine.estimate("build", 3000).mc == meter.estimate_action(S, 3000, cfg.build_max_tokens // 4, 12).mc
    assert cfg.model_for("anything-else") == P.HAIKU                       # an unknown kind gets the cheap model


def test_effort_is_sent_per_kind_and_the_gate_asks_for_low(env):
    for kind, want in (("build", "medium"), ("edit", "low"), ("chat", "low")):
        env.mock.requests.clear()
        env.mock.use(M.Scenario("t", [M.Step(M.say("ON_TOPIC")), M.Step(M.say("ok"))] if kind == "chat"
                                else [M.Step(M.say("ok"))]))
        env.engine._recent.clear()
        assert env.engine.run_action("u1", "hi", kind=kind).status == "done"
        bodies = [q["body"] for q in env.mock.message_requests]
        assert bodies[-1]["output_config"] == {"effort": want}
        if kind == "chat":
            assert bodies[0]["output_config"] == {"effort": "low"} and bodies[0]["model"] == P.HAIKU
            assert bodies[0]["thinking"] == {"type": "disabled"} and bodies[-1]["thinking"] == {"type": "disabled"}    # gate and chat: thinking off
    env.engine.cfg.efforts["build"] = "high"                                 # it is a config value
    env.mock.requests.clear()
    env.mock.use(M.Scenario("t", [M.Step(M.say("ok"))]))
    env.engine._recent.clear()
    env.engine.run_action("u1", "hi")
    assert env.mock.message_requests[-1]["body"]["output_config"] == {"effort": "high"}
    assert env.mock.message_requests[-1]["body"]["thinking"] == {"type": "adaptive"}     # the build thinks; it is sent as itself, never left to a default
