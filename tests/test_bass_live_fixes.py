"""The fixes from the pre-live review of 11 Nov 2026 (ORG/notes-bass-review-1111.md, decision L-1111-161625), one group per finding id.
MOCK ONLY: every model call goes to the MockTransport, every store is in memory or under tmp_path, no key and no Keychain.
Each group holds at least one test that FAILS on the code as it was before the fix (alto-bass-drive-r2 + main + local + paste)."""
import copy
import datetime as dt
import importlib.util
import json
import re
import sys
import types

import pytest

from bass_support import bass_guard, ROOT  # noqa: F401
from bass_beta_support import CHIPS, EMAIL, MATERIALS, FakeClock, build_req, edit_req, make_stack, req
from alto.bass import beta_config as BC
from alto.bass import config as P
from alto.bass import engine as E
from alto.bass import meter
from alto.bass import mock_anthropic as M
from alto.bass.beta_config import BetaConfig
from alto.bass.beta_ledger import confirm_key, day_key, pc_key
from alto.bass.beta_store import FakeStore, ReadAfterWrite, StoreError
from alto.bass.client import make_client
from alto.bass.errors import BassError, InsufficientCredits

MC = 1000
UID = "u_" + EMAIL.split("@")[0]
DEPLOY = ROOT / "deploy" / "bass-proxy"


@pytest.fixture(autouse=True)
def _mock_only(monkeypatch, tmp_path):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")
    monkeypatch.delenv("ALTO_LIVE_ANTHROPIC", raising=False)
    monkeypatch.setenv("ALTO_BASS_LIVE_GO", str(tmp_path / "no-go-file"))        # never Luke's real go-file


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def day(st):
    return st.store.get(day_key(st.ledger.today()))


def pc(st):
    return st.store.get(pc_key(st.ledger.period()))


# ══ M1: a request that was sent is never released for free, and never retried after the stream began ═══════════════════════════════════

def test_m1_a_stream_that_drops_is_booked_on_the_day_and_the_period_and_is_not_retried(tmp_path):
    st = make_stack(tmp_path)
    st.mock.inject(M.stream_drop(after_events=4, times=3))                # the old code retried 3 times and then booked nothing
    out = st.svc.handle(req(build_req()))
    assert out["status"] == "error" and out["ok"] is False
    assert len(st.mock.message_requests) == 1                             # ONE attempt: no retry after the first stream event
    d, p = day(st), pc(st)
    assert d["spent_mc"] > 0 and d["reserved_mc"] == 0                    # the books took it (at the reserved worst case) ...
    assert p["spent_mc"] == d["spent_mc"] and p["res"] == {}
    assert st.store.get(UID)["holds"] == {} and st.ledger.balance_mc(UID) == st.cfg.allowance_mc     # ... and the tester paid nothing
    assert [e for e in st.ledger.entries(UID) if e["kind"] == "absorbed"][-1]["mc"] == d["spent_mc"]


def test_m1_the_booked_cost_is_the_holds_worst_case_never_less_than_what_a_whole_turn_could_cost(tmp_path):
    st = make_stack(tmp_path)
    st.mock.inject(M.stream_error(after_events=3))                        # an error EVENT mid-stream (the API answered 200 first)
    st.svc.handle(req(build_req()))
    n_in = st.mock.requests[-2]["body"] and [r for r in st.mock.requests if r["path"].endswith("count_tokens")][-1]
    counted = st.mock.count_input(n_in["body"])["total"]
    assert day(st)["spent_mc"] == meter.worst_turn(P.SONNET, counted, st.engine.cfg.max_tokens_for("build"))
    assert day(st)["spent_mc"] >= meter.estimate_turn(P.SONNET, counted, P.BUILD_MAX_TOKENS)


def test_m1_a_timeout_after_the_request_left_is_booked_and_not_retried_even_on_the_gate(tmp_path):
    st = make_stack(tmp_path)
    st.mock.inject(M.read_timeout())                                      # the gate's call: sent, then silence
    out = st.svc.handle(req(edit_req()))
    assert out["status"] == "error" and out["code"] == "timeout" and len(st.mock.message_requests) == 1
    assert day(st)["spent_mc"] > 0 and st.ledger.balance_mc(UID) == st.cfg.allowance_mc


def test_m1_an_error_answer_or_a_failed_connection_is_still_free_and_still_retried(tmp_path):
    st = make_stack(tmp_path)
    st.mock.inject(M.overloaded(times=1), M.connect_error(times=1))       # provably unbilled: no stream ever started
    out = st.svc.handle(req(build_req()))
    assert out["ok"] is True and len(st.mock.message_requests) == 3
    cost = round(out["credits"]["spent"] * MC)
    assert abs(day(st)["spent_mc"] - cost) <= 10 and day(st)["reserved_mc"] == 0      # only the good attempt is on the books


def test_m1_three_failed_turns_raise_the_counters_three_times(tmp_path):
    st = make_stack(tmp_path)
    seen = []
    for _ in range(3):
        st.mock.inject(M.stream_drop(after_events=5))
        st.svc.handle(req(build_req()))
        seen.append(day(st)["spent_mc"])
    assert 0 < seen[0] < seen[1] < seen[2] and len(st.mock.message_requests) == 3


# ══ M2: the reaper books an abandoned reservation; an action's wall time is bounded below the function timeout ═════════════════════════

def test_m2_the_reaper_books_an_abandoned_reservation_as_absorbed_and_gives_only_the_testers_hold_back(tmp_path):
    st = make_stack(tmp_path)
    st.ledger.grant_opening(UID)
    st.ledger.hold(UID, "cut", 40 * MC, "act1", worst_mc=60 * MC)         # the call went out; then the platform cut the function
    assert day(st)["reserved_mc"] == 60 * MC and st.ledger.balance_mc(UID) == st.cfg.allowance_mc - 40 * MC
    st.clock.advance(st.cfg.reservation_ttl_s + 1)
    assert st.ledger.reap() == 1
    d, p = day(st), pc(st)
    assert (d["spent_mc"], d["reserved_mc"]) == (60 * MC, 0) and (p["spent_mc"], p["reserved_mc"]) == (60 * MC, 0)    # booked, not freed
    assert st.ledger.balance_mc(UID) == st.cfg.allowance_mc and st.ledger.held_mc(UID) == 0                          # the tester's hold is back
    assert st.sink.of("abandoned_calls_booked") == [{"kind": "abandoned_calls_booked", "count": 1, "absorbed_mc": 60 * MC}]
    assert [e["mc"] for e in st.ledger.entries(UID) if e["kind"] == "absorbed"] == [60 * MC]
    assert st.ledger.reap() == 0                                          # once


def test_m2_a_settle_that_arrives_after_the_reaper_replaces_the_worst_case_with_the_real_cost(tmp_path):
    st = make_stack(tmp_path)
    st.ledger.grant_opening(UID)
    st.ledger.hold(UID, "slow", 40 * MC, "act1", worst_mc=60 * MC)
    st.clock.advance(st.cfg.reservation_ttl_s + 1)
    st.ledger.reap()
    st.ledger.settle(UID, "slow", 25 * MC)                                # the call finished after all
    assert day(st)["spent_mc"] == 25 * MC and pc(st)["spent_mc"] == 25 * MC and pc(st)["reaped"] == {}     # never counted twice


def test_m2_an_action_stops_before_starting_a_turn_it_has_no_time_for(tmp_path):
    st = make_stack(tmp_path, tester_daily_credits=600)
    st.engine.cfg.max_wall_s = st.cfg.action_wall_s                       # what the proxy sets (asserted below)

    def slow(ctx):
        st.clock.advance(115)                                             # every model turn takes 115 s
        return M.Reply([M.text("working"), M.tool_use("create_project", {"name": "Loop"})])
    st.mock.use(M.Scenario("slow", [M.Step(slow)], repeat_last=True))
    out = st.svc.handle(req(build_req()))
    assert out["status"] == "capped" and out["code"] == "time_limit" and out["work_saved"] is True
    assert len(st.mock.message_requests) == 2                             # at 230 s there is no room for a third turn: it is not started
    assert day(st)["reserved_mc"] == 0 and "ran out of time" in out["message"]


def test_m2_a_turn_still_streaming_at_the_bound_is_cut_by_us_and_booked(tmp_path):
    st = make_stack(tmp_path, tester_daily_credits=600)
    st.engine.cfg.max_wall_s = st.cfg.action_wall_s

    def slow(ctx):
        st.clock.advance(130)
        return M.Reply([M.text("working"), M.tool_use("create_project", {"name": "Loop"})])
    st.mock.use(M.Scenario("slow", [M.Step(slow)], repeat_last=True))
    before = 0
    out = st.svc.handle(req(build_req()))                                 # turn 2 is at 260 s when its stream is read: past 240
    assert out["code"] == "time_limit" and len(st.mock.message_requests) == 2
    absorbed = [e["mc"] for e in st.ledger.entries(UID) if e["kind"] == "absorbed"]
    assert len(absorbed) == 1 and absorbed[0] > before and day(st)["spent_mc"] >= absorbed[0] and day(st)["reserved_mc"] == 0


def test_m2_the_wall_bound_is_config_sits_below_the_function_timeout_and_the_proxy_and_the_deploy_plan_use_it(tmp_path, capsys):
    cfg = BetaConfig(testers=10)
    assert cfg.action_wall_s == 240 and cfg.function_timeout_s == 300 and cfg.problems() == []
    assert any("action_wall_s" in x for x in cfg.with_(action_wall_s=290).problems())
    import test_bass_beta_proxy as TP
    p = TP.two_accounts(tmp_path)
    assert p.service.actions.engine.cfg.max_wall_s == p.cfg.action_wall_s
    dep = load("bass_deploy_fix", DEPLOY / "deploy.py")
    assert dep.main(["--project", "demo-project", "--testers", "10", "--bucket", "demo-bucket"]) == 0
    assert "--timeout 300s" in capsys.readouterr().out


# ══ M3: one fixed local reserve per credit period, shared by the live check and the local server ════════════════════════════════════════

from alto.bass import local_reserve as LR                                 # noqa: E402
from alto.bass.local_reserve import LocalReserve                          # noqa: E402


@pytest.fixture
def blc():
    import test_bass_live_check as T
    return T.BLC


@pytest.fixture
def srv():
    import test_bass_local_server as T
    return T.S


def dry_run(blc, tmp, reserve, builds=5, cap=1000):
    mock = M.MockAnthropic()
    brief = json.loads((ROOT / "samples" / "contracts_brief.json").read_text("utf-8"))
    return blc.run_check(make_client("mock", mock=mock), tmp / "out", builds=builds, cap_credits=cap, dry=True, mock=mock, reserve=reserve,
                         log=lambda *a: None, scenario=lambda: M.build("Contracts", brief["brief"], brief["nodes"], brief["connections"]))


def test_m3_every_run_of_the_live_check_draws_on_the_same_reserve_and_a_used_up_reserve_stops_the_run(blc, tmp_path):
    path = tmp_path / "reserve.json"
    first = dry_run(blc, tmp_path, LocalReserve(path, cap_credits=60))
    used1 = LocalReserve(path, cap_credits=60).status()["used_credits"]              # a NEW object, the same file: it is all still there
    assert used1 > 0 and first["meta"]["local_reserve"]["used_credits"] == used1
    second = dry_run(blc, tmp_path, LocalReserve(path, cap_credits=60))
    used2 = LocalReserve(path, cap_credits=60).status()["used_credits"]
    assert used1 < used2 <= 60                                                       # the old code gave the second run a fresh $10
    assert second["meta"]["cap_credits"] <= 60 - int(used1) and second["meta"]["spent_credits"] < first["meta"]["spent_credits"]
    for _ in range(4):
        last = dry_run(blc, tmp_path, LocalReserve(path, cap_credits=60))
    assert LocalReserve(path, cap_credits=60).status()["used_credits"] <= 60         # never past the cap, however many runs
    assert last["meta"]["result"] != "completed"


def test_m3_the_local_server_and_the_live_check_share_it_across_purposes_and_store_roots(blc, srv, tmp_path):
    clock = FakeClock()
    R = LocalReserve(tmp_path / "reserve.json", cap_credits=1000, clock=clock)

    def propose(purpose, root):
        mock = M.MockAnthropic(M.Scenario("p", [M.Step(M.Reply([M.tool_use("propose_chips", CHIPS)]))]))
        p = srv.build_proxy(purpose, root, 8765, "tok-" + "y" * 24, False, clock=clock, mock=mock, reserve=R)
        h = {"Authorization": "Bearer tok-" + "y" * 24, "Origin": "http://127.0.0.1:8765"}
        st, _, body = p.handle_http("POST", h, json.dumps({"action": "propose", "args": {"materials": MATERIALS}}))
        assert st == 200 and json.loads(body)["ok"] is True
    propose("own", tmp_path / "root-a")
    propose("runs", tmp_path / "root-b")                                             # another purpose AND another directory
    dry_run(blc, tmp_path, R, builds=5)
    by = R.status()["by_source_credits"]
    assert set(by) == {"local-server:own", "local-server:runs", "live-check"} and all(v > 0 for v in by.values())
    assert abs(R.status()["used_credits"] - sum(by.values())) < 1e-6


def test_m3_a_hold_the_reserve_cannot_cover_is_refused_before_any_call(srv, tmp_path):
    clock = FakeClock()
    R = LocalReserve(tmp_path / "reserve.json", cap_credits=10, clock=clock)          # $0.10 left: less than one build turn's worst case
    mock = M.MockAnthropic()
    p = srv.build_proxy("runs", tmp_path / "root", 8765, "tok-" + "z" * 24, False, clock=clock, mock=mock, reserve=R)
    h = {"Authorization": "Bearer tok-" + "z" * 24, "Origin": "http://127.0.0.1:8765"}
    st, _, body = p.handle_http("POST", h, json.dumps({"action": "build", "args": build_req()["args"]}))
    out = json.loads(body)
    assert out["status"] == "no_credits" and mock.message_requests == [] and R.status()["used_credits"] == 0


def test_m3_live_refuses_any_root_or_reserve_file_but_the_fixed_ones(blc, srv, tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        srv.build_proxy("own", tmp_path / "elsewhere", 8765, "tok", True)             # live + another root: a fresh grant, refused
    assert "fixed store root" in str(e.value) and not (tmp_path / "elsewhere").exists()
    assert blc.main(["--reserve-file", str(tmp_path / "mine.json"), "--out", str(tmp_path / "o")], env={"ALTO_LIVE_ANTHROPIC": "1"}) == 2
    assert "fixed reserve file" in capsys.readouterr().err and not (tmp_path / "o").exists() and not (tmp_path / "mine.json").exists()
    with pytest.raises(BassError):
        LocalReserve(tmp_path / "other.json").require_fixed()
    with pytest.raises(BassError):
        blc.run_check(None, tmp_path / "o", builds=5, cap_credits=10, dry=False, reserve=LocalReserve(tmp_path / "other.json"))
    assert LR.RESERVE_FILE.name == "reserve.json" and "Alto-bass-local" in str(LR.RESERVE_FILE)
    assert not any(part in ("Desktop", "Documents", "Mobile Documents") for part in LR.RESERVE_FILE.parts)      # not an iCloud-synced folder


def test_m3_the_reserve_is_per_credit_period_a_new_period_stays_shut_until_opened_and_abandoned_holds_are_booked(tmp_path):
    clock = FakeClock()
    R = LocalReserve(tmp_path / "reserve.json", cap_credits=100, clock=clock)
    R.hold("live-check", "h1", 30 * MC)
    R.settle("h1", 12 * MC)
    R.hold("live-check", "h2", 80 * MC)
    with pytest.raises(InsufficientCredits):
        R.hold("local-server:own", "h3", 10 * MC)                                     # 12 + 80 + 10 > 100
    R.release("h2")
    R.hold("local-server:own", "h4", 50 * MC)
    clock.advance(LR.TTL_S + 1)                                                        # h4 was never settled: an abandoned call
    assert R.status()["by_source_credits"] == {"live-check": 12.0, "local-server:own": 50.0} and R.status()["left_credits"] == 38.0
    assert R.period() == "2026-10-17"
    clock.advance(days=20)                                                             # past the 17th
    assert R.period() == "2026-11-17" and R.status()["open"] is False
    with pytest.raises(BassError) as e:
        R.hold("live-check", "h5", MC)
    assert e.value.code == "beta_credits_used"                                         # the calendar alone grants nothing
    assert R.open_period() == "2026-11-17"
    R.hold("live-check", "h5", MC)
    assert R.status()["left_credits"] == 99.0


# ══ M4 (interim): the server ceiling is $70 until M1 and M2 have been tested live ═══════════════════════════════════════════════════════

def test_m4_the_default_server_ceiling_is_the_interim_70_dollars_a_config_number_with_the_reason_written_down(tmp_path):
    c = BetaConfig(testers=10)
    assert c.server_ceiling_credits == BC.INTERIM_SERVER_CEILING_CREDITS == 7000 and BC.PLANNED_SERVER_CEILING_CREDITS == 9000
    assert c.tester_period_credits == 700 and c.ceiling_mc == 7000 * MC and c.problems() == []
    assert c.server_ceiling_credits + LR.CAP_CREDITS <= c.pool_credits - 2000          # $20 of room inside the $100 for what the books miss
    assert "INTERIM" in BC.__doc__ and "M1" in BC.__doc__ and "M2" in BC.__doc__
    st = make_stack(tmp_path, server_ceiling_credits=7000)
    bal = st.svc.handle(req({"action": "balance", "args": {}}))
    assert bal["credits"] == 700
    p = pc(st) or {"period": st.ledger.period(), "spent_mc": 0, "reserved_mc": 0, "res": {}, "alerted": [], "spend_log": []}
    p["spent_mc"] = 7000 * MC - 1                                                      # one milli-credit short of the ceiling
    st.store.put(pc_key(st.ledger.period()), p)
    out = st.svc.handle(req(build_req()))
    assert out["code"] == "beta_credits_used" and st.mock.message_requests == []


# ══ A1: thinking and max_tokens ══════════════════════════════════════════════════════════════════════════════════════════════════════

def test_a1_the_gate_runs_with_thinking_off_so_a_thinking_model_cannot_make_it_fail_open(tmp_path):
    st = make_stack(tmp_path)
    st.mock.think_tokens = 40                                              # the model would think first, and 40 > the gate's 16 tokens
    st.mock.use(M.Scenario("g", [M.Step(M.say("OFF_TOPIC")), M.Step(M.say("should never be reached"))]))
    out = st.svc.handle(req(edit_req(text="write my history essay for me")))
    assert out["status"] == "off_topic" and len(st.mock.message_requests) == 1
    gate = st.mock.message_requests[0]["body"]
    assert gate["thinking"] == {"type": "disabled"} and gate["max_tokens"] == P.GATE_MAX_TOKENS and gate["model"] == P.HAIKU
    assert [b["type"] for b in st.mock.responses[0]["content"]] == ["text"]


def test_a1_an_empty_gate_answer_is_off_topic(tmp_path):
    st = make_stack(tmp_path)
    st.mock.use(M.Scenario("g", [M.Step(M.say("  ")), M.Step(M.say("should never be reached"))]))
    out = st.svc.handle(req(edit_req()))
    assert out["status"] == "off_topic" and len(st.mock.message_requests) == 1


def test_a1_chat_and_propose_replies_are_not_cut_off_by_thinking(tmp_path):
    st = make_stack(tmp_path)
    st.mock.think_tokens = 3000                                            # more than chat's 800 and all of propose's 3,000
    words = "word " * 400
    st.mock.use(M.Scenario("c", [M.Step(M.say("ON_TOPIC")), M.Step(M.say(words))]))
    out = st.svc.handle(req(edit_req()))
    assert out["ok"] is True and out["message"].strip() == words.strip()
    st.mock.use(M.Scenario("p", [M.Step(M.Reply([M.tool_use("propose_chips", CHIPS)]))]))
    out = st.svc.handle(req({"action": "propose", "args": {"materials": MATERIALS}}))
    assert out["ok"] is True and out["chips"]["title"] == CHIPS["title"]
    kinds = [(r["body"]["model"], r["body"]["thinking"]) for r in st.mock.message_requests]
    assert kinds == [(P.HAIKU, {"type": "disabled"})] * 3                  # gate, chat, propose: Haiku, thinking off (allowed at low/medium)
    assert all(r["body"]["output_config"]["effort"] in P.THINKING_OFF_EFFORTS for r in st.mock.message_requests)


def test_a1_the_build_thinks_with_room_for_it_and_a_thinking_kind_never_gets_a_small_max_tokens(tmp_path):
    st = make_stack(tmp_path)
    st.mock.think_tokens = 3000
    out = st.svc.handle(req(build_req()))
    body = st.mock.message_requests[-1]["body"]
    assert out["ok"] is True and body["model"] == P.SONNET and body["thinking"] == {"type": "adaptive"} and body["max_tokens"] == 16000
    assert [b["type"] for b in st.mock.responses[-1]["content"]] == ["thinking", "text"] and st.mock.responses[-1]["usage"]["output_tokens"] > 3000
    cfg = E.BassConfig()
    assert cfg.max_tokens_for("chat") == P.CHAT_MAX_TOKENS and cfg.max_tokens_for("propose") == 3000
    cfg.thinking["chat"] = "adaptive"
    assert cfg.max_tokens_for("chat") == P.THINKING_MIN_MAX_TOKENS >= 4000


def test_a1_turning_thinking_off_uses_each_models_documented_parameter_and_refuses_anything_else():
    assert E.thinking_off(P.HAIKU, "low") == {"type": "disabled"} and E.thinking_off(P.SONNET, "medium") == {"type": "between_tools"}
    for model, effort in ((P.HAIKU, "xhigh"), (P.SONNET, "max"), ("claude-opus-5-5", "low")):
        with pytest.raises(ValueError):
            E.thinking_off(model, effort)
    cfg = E.BassConfig()
    cfg.thinking["build"] = "off"
    assert cfg.thinking_for("build") == {"type": "between_tools"}          # never {"type": "disabled"} on Sonnet 5.5 (a 400)


# ══ A2: kept history and the history-editing check ═══════════════════════════════════════════════════════════════════════════════════

LIB = [{"name": "Outline.txt", "text": "Consideration is a bargained-for exchange. " * 40}]


def test_a2_a_second_edit_after_the_documents_marker_swap_is_accepted_and_the_kept_history_has_no_thinking_block(tmp_path):
    st = make_stack(tmp_path)
    if hasattr(st.engine.cfg, "thinking"):
        st.engine.cfg.thinking["chat"] = "adaptive"                        # the hard case: the edit model thinks (the API default)
    st.ledger.grant_opening(UID)
    st.mock.use(M.Scenario("e", [M.Step(M.say("ON_TOPIC")), M.Step(M.Reply([M.text("Looking."), M.tool_use("list_projects", {})])),
                                 M.Step(M.say("Added.")), M.Step(M.say("ON_TOPIC")), M.Step(M.say("Done again."))]))
    one = st.acts.edit(UID, "t1", "Add a card about consideration.", library=LIB)
    assert one["ok"] is True
    kept = st.acts.conversations[(UID, "t1")]
    assert not any(isinstance(m["content"], list) and any(b.get("type") in E.THINKING_BLOCKS for b in m["content"]) for m in kept)
    assert "[the student's documents were shown here]" in json.dumps(kept)                 # the swap that used to break the next turn
    two = st.acts.edit(UID, "t1", "And one about promissory estoppel.", library=LIB)
    assert two["ok"] is True, two
    assert not st.kill.is_on() and not [e for e in st.mock.errors_sent if "bound to a different conversation" in e["message"]]


def test_a2_inside_one_action_the_history_is_append_only_and_thinking_blocks_go_back_unchanged(tmp_path):
    st = make_stack(tmp_path)
    brief = json.loads((ROOT / "samples" / "contracts_brief.json").read_text("utf-8"))
    st.mock.use(M.build("Contracts", brief["brief"], brief["nodes"], brief["connections"]))
    out = st.svc.handle(req(build_req()))
    assert out["ok"] is True and st.mock.errors_sent == []
    bodies = [r["body"]["messages"] for r in st.mock.message_requests]
    for a, b in zip(bodies, bodies[1:]):
        assert b[:len(a)] == a                                              # every request repeats the one before it, then appends
    assert sum(1 for m in bodies[-1] if m["role"] == "assistant" and m["content"][0]["type"] == "thinking") >= 3


def test_a2_a_history_check_400_is_recovered_once_by_dropping_thinking_and_never_trips_the_kill_switch(tmp_path):
    st = make_stack(tmp_path)
    bound = "messages.1.content.0: " + M.BINDING_400
    st.mock.use(M.Scenario("e", [M.Step(M.say("ON_TOPIC")), M.Step(M.say("Added."))]))
    st.mock.inject(M.Fault("http", 400, "invalid_request_error", bound, times=1, path="/v1/messages/count_tokens"))
    assert st.svc.handle(req(edit_req()))["ok"] is True                    # one refusal: thinking is stripped, the turn goes through
    assert (UID, "t1") in st.acts.conversations
    st.mock.use(M.Scenario("e", [M.Step(M.say("ON_TOPIC")), M.Step(M.say("never"))]))
    st.mock.inject(M.Fault("http", 400, "invalid_request_error", bound, times=9, path="/v1/messages/count_tokens"))
    out = st.svc.handle(req(edit_req()))
    assert out["status"] == "error" and out["code"] == "history_mismatch" and "lost its place" in out["message"]
    assert not st.kill.is_on() and st.sink.of("history_mismatch") and not st.sink.of("kill_switch")
    assert (UID, "t1") not in st.acts.conversations                        # that conversation starts clean next time
    st.mock.faults.clear()
    st.mock.use(M.Scenario("e", [M.Step(M.say("ON_TOPIC")), M.Step(M.say("Fine."))]))
    assert st.svc.handle(req(edit_req()))["ok"] is True                    # and Bass still works for everyone
    st.mock.inject(M.unexpected_400())                                     # any OTHER unexpected 400 still stops Bass for everyone
    st.mock.use(M.Scenario("e", [M.Step(M.say("ON_TOPIC"))]))
    st.svc.handle(req(edit_req()))
    assert st.kill.is_on()


def test_a2_trimming_only_drops_whole_turns_from_the_front_and_never_rewrites_a_kept_turn(tmp_path):
    st = make_stack(tmp_path)
    msgs = []
    for i in range(30):
        msgs += [{"role": "user", "content": f"q{i}"}, {"role": "assistant", "content": [{"type": "text", "text": f"a{i}"}]}]
    snapshot = copy.deepcopy(msgs)
    kept = st.acts._trim(msgs)
    assert len(kept) <= st.acts.keep_messages and kept == msgs[len(msgs) - len(kept):] and all(a is b for a, b in zip(kept, msgs[-len(kept):]))
    assert msgs == snapshot and kept[0]["role"] == "user"
    tool_only = [{"role": "user", "content": "go"}] + [x for i in range(20) for x in (
        {"role": "assistant", "content": [{"type": "tool_use", "id": f"t{i}", "name": "x", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"t{i}", "content": "ok"}]})]
    assert st.acts._trim(tool_only) == []                                  # no plain user turn to start at: nothing is kept, nothing is cut mid-round


# ══ S1: Bass has its own tester list ═════════════════════════════════════════════════════════════════════════════════════════════════

def test_s1_being_on_the_cloud_beta_allowlist_gives_no_bass_access_only_the_bass_tester_list_does(tmp_path):
    st = make_stack(tmp_path, emails=())                                   # no config copy: the store decides, as deployed
    st.store.put("bass_beta/allowlist", {"emails": [EMAIL]})               # may save to the cloud in the Alto beta
    out = st.svc.handle(req({"action": "balance", "args": {}}))
    assert out["code"] == "bass_off" and out["available"] is False and st.store.get(UID) is None       # no grant, nothing created
    assert st.svc.handle(req(build_req()))["code"] == "bass_off" and st.mock.requests == []
    st.store.put("bass_beta/bass_testers", {"emails": [EMAIL.upper()]})
    assert st.svc.handle(req({"action": "balance", "args": {}}))["ok"] is True


def test_s1_a_list_longer_than_n_admits_nobody_and_raises_one_alert(tmp_path):
    st = make_stack(tmp_path, testers=3, emails=())
    st.store.put("bass_beta/bass_testers", {"emails": [EMAIL, "b@example.com", "c@example.com"]})
    assert st.svc.handle(req({"action": "balance", "args": {}}))["ok"] is True
    st.store.put("bass_beta/bass_testers", {"emails": [EMAIL, "b@example.com", "c@example.com", "d@example.com"]})      # 4 > N = 3
    for _ in range(3):
        assert st.svc.handle(req(build_req()))["code"] == "bass_off"
    assert st.mock.requests == []
    assert st.sink.of("tester_list_too_long") == [{"kind": "tester_list_too_long", "listed": 4, "budgeted": 3}]
    assert make_stack(tmp_path / "b", testers=2, emails=(EMAIL, "b@example.com", "c@example.com")).svc.allow.emails() == frozenset()     # the config copy too


def test_s1_the_rules_deny_clients_the_whole_bass_beta_collection_and_no_rule_reads_the_tester_list():
    # firestore.rules itself is pinned byte-for-byte to public main (tests/security/test_security_parity.py): its existing deny-all on
    # bass_beta/** already covers the new document, so the file is not edited; this test and the emulator suite pin the behaviour.
    for name in ("firestore.rules", "alto/firestore.rules"):
        rules = (ROOT / name).read_text("utf-8")
        assert re.search(r"match /bass_beta/\{document=\*\*\} \{\s*allow read, write: if false;\s*\}", rules)
        assert "bass_beta/bass_testers" not in rules                       # nothing reads it for a client: the rules never name it at all
        assert rules.count("documents/bass_beta/") == 1 and "documents/bass_beta/allowlist" in rules       # the one get() is the cloud beta's list
        assert len(re.findall(r"match /bass_beta/", rules)) == 1                                            # no second, looser match
    fs = load("bass_fs_store_s1", DEPLOY / "firestore_store.py")
    assert fs._path("bass_beta/bass_testers") == ("bass_beta", "bass_testers")
    mjs = (ROOT / "tests" / "security" / "firestore_rules.test.mjs").read_text("utf-8")
    assert "bass_beta/bass_testers" in mjs                                 # the emulator suite checks it too (needs the Firebase emulator)


# ══ S2: Google sign-in only ══════════════════════════════════════════════════════════════════════════════════════════════════════════

from test_bass_beta_review import ENV, cold  # noqa: E402,F401


def test_s2_the_verifier_refuses_every_sign_in_provider_but_google(cold, monkeypatch):
    main, _ = cold
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    proxy = main._build()
    from alto.bass.beta_proxy import AuthError
    auth = sys.modules["firebase_admin.auth"]

    def token(provider):
        d = {"uid": "u1", "email": "e@x.com", "email_verified": True}
        if provider is not None:
            d["firebase"] = {"sign_in_provider": provider}
        return lambda t, check_revoked=False: d
    monkeypatch.setattr(auth, "verify_id_token", token("google.com"))
    assert proxy.verifier.verify("tok") == {"uid": "u1", "email": "e@x.com", "email_verified": True}
    for provider in ("password", "anonymous", "custom", "phone", "apple.com", "GOOGLE.COM", "", None):
        monkeypatch.setattr(auth, "verify_id_token", token(provider))
        with pytest.raises(AuthError):
            proxy.verifier.verify("tok")
        st, _, body = proxy.handle_http("POST", {"Authorization": "Bearer tok"}, json.dumps({"action": "balance", "args": {}}))
        assert st == 401 and json.loads(body) == {"ok": False, "message": "Please sign in again."}


# ══ G1: Luke's numbers are ALERTS; the trips stay where they are ═══════════════════════════════════════════════════════════════════════

def test_g1_more_than_4_dollars_in_10_minutes_is_an_alert_once_per_window_and_not_a_trip(tmp_path):
    st = make_stack(tmp_path)
    wd, now = st.ledger.on_commit, st.clock().timestamp()
    g = {"day": st.ledger.today(), "spent_mc": 0, "reserved_mc": 0, "alerted": []}
    p = {"period": st.ledger.period(), "spend_log": [[now - 500, 200 * MC], [now - 30, 200 * MC]]}
    wd(g, p)
    assert st.sink.of("spend_over_alert_10min") == []                      # exactly $4: not over
    p["spend_log"].append([now - 5, MC])
    wd(g, p)
    wd(g, p)
    assert st.sink.of("spend_over_alert_10min") == [{"kind": "spend_over_alert_10min", "recent_mc": 401 * MC, "alert_mc": 400 * MC, "window_s": 600}]
    assert not st.kill.is_on()                                             # an alert never stops Bass
    st.clock.advance(601)
    p["spend_log"] = [[st.clock().timestamp() - 1, 500 * MC]]
    wd(g, p)
    assert len(st.sink.of("spend_over_alert_10min")) == 2 and not st.kill.is_on()
    assert st.cfg.spike_trip_mc == 3301 * MC                               # the TRIP is unchanged: $33 at N = 10 (security fix B1)
    p["spend_log"] = [[st.clock().timestamp() - 1, st.cfg.spike_trip_mc + 1]]
    wd(g, p)
    assert st.kill.is_on() and st.kill.state()["reason"] == "spend_spike_10min"


def test_g1_80_percent_of_the_day_before_18_is_an_alert_once_a_day_and_not_a_trip(tmp_path):
    st = make_stack(tmp_path)                                              # the clock is 10:00 in New York
    wd = st.ledger.on_commit
    p = {"period": st.ledger.period(), "spend_log": []}
    wd({"day": st.ledger.today(), "spent_mc": 1200 * MC, "reserved_mc": 0, "alerted": []}, p)
    assert st.sink.of("daily_over_80_before_18") == []                     # exactly 80%: not over
    for _ in range(2):
        wd({"day": st.ledger.today(), "spent_mc": 1100 * MC, "reserved_mc": 101 * MC, "alerted": []}, p)
    assert len(st.sink.of("daily_over_80_before_18")) == 1 and not st.kill.is_on()
    late = make_stack(tmp_path / "late")
    late.clock.advance(9 * 3600)                                           # 19:00 in New York
    late.ledger.on_commit({"day": late.ledger.today(), "spent_mc": 1400 * MC, "reserved_mc": 0, "alerted": []}, p)
    assert late.sink.of("daily_over_80_before_18") == []


def test_g1_the_notes_say_alert_for_luke_s_numbers_and_trip_only_for_the_higher_line():
    doc = BC.__doc__
    assert "ALERTS" in doc and "400 credits ($4)" in doc and "trips too" not in doc and "spike trip       400" not in doc
    rb = (ROOT / "docs" / "bass-beta-runbook.md").read_text("utf-8")
    assert "400 credits ($4) of spend in any 10 minutes" in rb and "3,301 credits" in rb and "$4 trip" not in rb
    assert BetaConfig(testers=10).summary()["spike_alert_credits"] == 400 and BetaConfig(testers=10).summary()["spike_trip_credits"] == 3301


# ══ D1 / D2 / D3 ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

def test_d1_bass_requires_the_terms_version_main_ships(tmp_path):
    shipped = (ROOT / "alto" / "legal" / "VERSION").read_text("utf-8").strip()
    assert shipped == "1.1" == BetaConfig(testers=1).terms_version
    st = make_stack(tmp_path, store=FakeStore())
    st.store.accept_terms(UID, "0.1")                                      # the old acceptance does not count
    assert st.svc.handle(req({"action": "balance", "args": {}}))["code"] == "terms_required"
    st.store.accept_terms(UID, "1.1")
    assert st.svc.handle(req({"action": "balance", "args": {}}))["ok"] is True


def test_d2_every_collection_the_bass_proxy_keeps_is_classified_for_account_erase():
    from alto.store import erase
    fs = load("bass_fs_store_d2", DEPLOY / "firestore_store.py")
    keys = ["u1", "bass_beta/kill", "bass_beta/day/2026-11-01", "bass_beta/pc/2026-10-17", "bass_beta/meta/u1_2026-11-01", "bass_beta/periods/2026-10-17",
            "terms_acceptance/u1_1.1", "bass_research/switch", "bass_research_consent/u1", "bass_research_purge/abc", "bass_docs/u1",
            "bass_doc_text/u1_f1", "bass_drive/u1", "bass_drive_tok/" + "a" * 64]
    used = {fs._path(k)[0] for k in keys}
    assert used == set(erase.BASS_COLLECTIONS), used ^ set(erase.BASS_COLLECTIONS)
    src = (DEPLOY / "firestore_store.py").read_text("utf-8").split("def _path", 1)[1].split("def is_retries_exhausted", 1)[0]
    assert set(re.findall(r'"((?:bass|terms)_[a-z_]+)/', src)) <= {k.split("/")[0] for k in keys}        # no prefix in the map the samples miss
    assert set(re.findall(r'return "(\w+)"', src)) <= set(erase.BASS_COLLECTIONS)
    assert all(v.split(":")[0] in ("erase", "none", "ticket") for v in erase.BASS_COLLECTIONS.values())
    rules = (ROOT / "firestore.rules").read_text("utf-8")
    assert set(re.findall(r"^    match /(\w+)/\{\w+(?:=\*\*)?\} \{", rules, re.M)) <= set(erase.RULES_TOP_LEVEL)


def test_d2_one_erase_path_removes_every_bass_record_of_the_account_and_the_hook_calls_the_same_function(tmp_path, monkeypatch):
    from alto.store import erase
    from test_account_erase import FakeDB
    db = FakeDB()
    for uid in ("alice", "bob"):
        db.put(f"bass_credits/{uid}", {"entries": []})
        db.put(f"bass_drive/{uid}", {"token": "t-" + uid, "exp": 1})
        db.put(f"bass_drive_tok/hash-{uid}", {"uid": uid})
        db.put(f"bass_beta_meta/{uid}_2026-11-01", {"n": 1})
        db.put(f"bass_research_consent/{uid}", {"v": 1})
    db.put("bass_beta/allowlist", {"emails": ["alice@example.com", "bob@example.com"]})
    db.put("bass_beta/bass_testers", {"emails": ["Alice@Example.com", "bob@example.com"]})
    out = erase.erase_user(db, "alice", email="alice@example.com")
    assert out["bass"] == 5 and out["allowlist"] == 2
    assert not any(db.has(p) for p in ("bass_credits/alice", "bass_drive/alice", "bass_drive_tok/hash-alice", "bass_beta_meta/alice_", "bass_research_consent/alice"))
    assert all(db.has(p) for p in ("bass_credits/bob", "bass_drive/bob", "bass_drive_tok/hash-bob", "bass_beta_meta/bob_2026-11-01", "bass_research_consent/bob"))
    assert db.docs[("bass_beta", "bass_testers")]["emails"] == ["bob@example.com"] and db.docs[("bass_beta", "allowlist")]["emails"] == ["bob@example.com"]
    # the Auth "user deleted" hook: the same function, on the Firestore client behind the guard store
    main = load("bass_proxy_main_d2", DEPLOY / "main.py")
    store = FakeStore()
    store.db = db
    monkeypatch.setattr(main, "_docs_env", lambda: (store, None))
    monkeypatch.delenv("BASS_RESEARCH_BUCKET", raising=False)
    assert main.bass_docs_account_deleted({"uid": "bob"})["records"] == 5
    assert not any(db.has(p) for p in ("bass_credits/bob", "bass_drive/bob", "bass_drive_tok/hash-bob", "bass_beta_meta/bob_", "bass_research_consent/bob"))
    with pytest.raises(ValueError):
        erase.erase_bass_records(db, "../x")


def test_d3_no_bass_file_carries_the_project_or_sender_id():
    import subprocess
    files = subprocess.run(["git", "ls-files", "alto/bass", "deploy/bass-proxy", "tools", "docs", "tests"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    bass = [f for f in files if "bass" in f.lower() and not f.endswith(("test_no_leaks.py", "test_bass_live_fixes.py"))]
    assert len(bass) > 60
    needles = ("terrarium" + "-alto", "1059051" + "849224")
    assert [f for f in bass if any(n in (ROOT / f).read_text("utf-8", errors="ignore") for n in needles)] == []
    dep = load("bass_deploy_d3", DEPLOY / "deploy.py")
    assert dep.main(["--testers", "10"]) == 2                              # the ids come from the operator (arguments or ALTO_BASS_PROJECT / ALTO_BASS_BUCKET)


# ══ B1: every transaction reads before it writes (Firestore refuses a read after a write) ══════════════════════════════════════════════

class _FsSnap:
    def __init__(self, d):
        self.exists, self._d = d is not None, d

    def to_dict(self):
        return copy.deepcopy(self._d)


class _FsRef:
    def __init__(self, db, coll, doc):
        assert doc and "/" not in doc, (coll, doc)                         # a Firestore document id has no slash
        self.db, self.key = db, (coll, doc)

    def get(self, transaction=None):
        if transaction is not None:
            transaction.read()
        return _FsSnap(self.db.docs.get(self.key))

    def set(self, doc):
        self.db.docs[self.key] = copy.deepcopy(doc)


class _FsTxn:
    """What google.cloud.firestore's Transaction enforces: a read after a write raises (ReadAfterWriteError)."""

    def __init__(self, db):
        self.db, self.writes = db, []

    def read(self):
        if self.writes:
            self.db.read_after_write += 1
            raise type("ReadAfterWriteError", (Exception,), {"__module__": "google.cloud.firestore_v1.base_transaction"})("Attempted read after write in a transaction.")

    def set(self, ref, doc):
        self.writes.append((ref.key, copy.deepcopy(doc)))

    def delete(self, ref):
        self.writes.append((ref.key, None))


class StrictFirestore:
    """An in-memory stand-in for the Firestore client with the ONE rule the fake store never had. Not the emulator."""

    def __init__(self):
        self.docs, self.read_after_write = {}, 0

    def collection(self, coll):
        return types.SimpleNamespace(document=lambda doc: _FsRef(self, coll, doc))

    def transaction(self, max_attempts=5):
        return _FsTxn(self)


@pytest.fixture
def strict_fs(monkeypatch):
    gexc = types.ModuleType("google.api_core.exceptions")
    gexc.Aborted, gexc.Conflict = type("Aborted", (Exception,), {}), type("Conflict", (Exception,), {})
    api = types.ModuleType("google.api_core")
    api.exceptions = gexc
    gfs = types.ModuleType("google.cloud.firestore")

    def transactional(fn):
        def run(txn):
            out = fn(txn)
            for key, doc in txn.writes:                                    # the commit
                if doc is None:
                    txn.db.docs.pop(key, None)
                else:
                    txn.db.docs[key] = doc
            return out
        return run
    gfs.transactional = transactional
    gc = types.ModuleType("google.cloud")
    gc.firestore = gfs
    g = sys.modules.get("google") or types.ModuleType("google")
    for k, v in {"google": g, "google.api_core": api, "google.api_core.exceptions": gexc, "google.cloud": gc, "google.cloud.firestore": gfs}.items():
        monkeypatch.setitem(sys.modules, k, v)
    monkeypatch.syspath_prepend(str(DEPLOY))
    mod = load("bass_fs_store_b1", DEPLOY / "firestore_store.py")
    db = StrictFirestore()
    return mod.FirestoreStore(db), db


def test_b1_the_whole_money_path_runs_on_the_firestore_adapter_with_no_read_after_a_write(strict_fs, tmp_path):
    store, db = strict_fs
    st = make_stack(tmp_path, store=store, tester_daily_credits=600)
    ver = st.cfg.terms_version
    store.put(f"terms_acceptance/{UID}_{ver}", {"uid": UID, "version": ver, "ageConfirmed": True, "acceptedAt": "2026-11-11T12:00:00Z"})
    brief = json.loads((ROOT / "samples" / "contracts_brief.json").read_text("utf-8"))
    st.mock.use(M.build("Contracts", brief["brief"], brief["nodes"], brief["connections"]))
    assert st.svc.handle(req(build_req()))["ok"] is True                   # grant, hold, settle on every turn
    st.mock.use(M.Scenario("g", [M.Step(M.say("OFF_TOPIC"))]))
    assert st.svc.handle(req(edit_req()))["status"] == "off_topic"         # absorb (the gate's cost)
    st.mock.use(None)
    st.mock.inject(M.overloaded(times=99))
    assert st.svc.handle(req(build_req()))["status"] == "error"            # release (an unbilled failure)
    st.mock.faults.clear()
    st.mock.inject(M.stream_drop(after_events=4))
    assert st.svc.handle(req(build_req()))["status"] == "error"            # settle as absorbed (a billed failure)
    st.mock.use(M.Scenario("r", [M.Step(M.refusal())]))
    assert st.svc.handle(req(build_req()))["status"] == "refused"          # refund
    st.ledger.hold(UID, "cut", 5 * MC, "a9", worst_mc=9 * MC)
    st.clock.advance(st.cfg.reservation_ttl_s + 1)
    assert st.ledger.reap() == 1                                           # the reaper
    st.clock.advance(days=20)                                              # a new credit period, confirmed: the hold that also grants
    store.put(confirm_key(st.ledger.period()), {"confirmed": True})
    st.ledger.hold(UID, "new-period", 5 * MC, "a10", worst_mc=5 * MC)
    assert st.ledger.release(UID, "new-period") == 5 * MC
    assert st.kill.trip("test") is True and st.kill.is_on()                # the kill switch's own transaction
    assert db.read_after_write == 0
    d = db.docs[("bass_beta_days", "2026-11-03")]
    assert d["reserved_mc"] == 0 and d["spent_mc"] > 0
    assert ("bass_credits", UID) in db.docs and ("bass_beta_period_counters", "2026-10-17") in db.docs and ("bass_beta", "kill") in db.docs


def test_b1_the_raw_transaction_refuses_a_read_after_a_write_which_is_what_every_ledger_path_used_to_do(tmp_path):
    raw = make_stack(tmp_path / "raw", store=FakeStore(auto_terms=True, defer_writes=False))     # fn gets the raw transaction, as before the fix
    raw.ledger.grant_opening(UID)
    for op in (lambda: raw.ledger.hold(UID, "h", 5 * MC, "a1", worst_mc=5 * MC), lambda: raw.ledger.absorb(UID, "a1", MC, "gate")):
        with pytest.raises(BassError) as e:
            op()
        assert e.value.code == "bass_paused" and e.value.detail == {"why": "ReadAfterWrite"}
    with pytest.raises(ReadAfterWrite):
        raw.store.run_transaction(lambda txn: (txn.put("a", {"x": 1}), txn.get("b")))
    ok = make_stack(tmp_path / "ok")                                       # the default store hands fn the deferred view
    ok.ledger.grant_opening(UID)
    ok.ledger.hold(UID, "h", 5 * MC, "a1", worst_mc=5 * MC)
    ok.ledger.absorb(UID, "a1", MC, "gate")
    assert ok.ledger.release(UID, "h") == 5 * MC
    assert ok.store.run_transaction(lambda txn: (txn.put("a", {"x": 1}), txn.get("a"), txn.get("b"))) == (None, {"x": 1}, None)
    assert issubclass(ReadAfterWrite, StoreError)


# ══ B2: the Drive paths ══════════════════════════════════════════════════════════════════════════════════════════════════════════════

def test_b2_the_drive_records_have_their_own_collections_and_an_unmapped_key_is_refused(strict_fs):
    store, db = strict_fs
    mod = sys.modules["bass_fs_store_b1"]
    tok = "bass_drive_tok/" + "a" * 64
    assert mod._path("bass_drive/u1") == ("bass_drive", "u1") and mod._path(tok) == ("bass_drive_tok", "a" * 64)
    for bad in ("bass_newthing/u1", "bass_drive/a/b", "bass_drive/", "u1/x", ""):
        with pytest.raises(StoreError):
            mod._path(bad)

    def connect(txn):                                                     # what drive.py's connect transaction does
        assert txn.get(tok) is None and txn.get("bass_drive/u1") is None
        txn.put("bass_drive/u1", {"token": "t", "exp": 9})
        txn.put(tok, {"uid": "u1"})
    store.run_transaction(connect)
    assert store.get("bass_drive/u1") == {"token": "t", "exp": 9} and store.get(tok) == {"uid": "u1"}
    assert set(db.docs) == {("bass_drive", "u1"), ("bass_drive_tok", "a" * 64)}
    store.run_transaction(lambda txn: (txn.delete("bass_drive/u1"), txn.delete(tok)))
    assert db.docs == {}


# ══ M5 / M6 / M7 ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

def test_m5_a_refund_gives_the_credits_back_but_the_cost_still_counts_against_that_testers_day(tmp_path):
    st = make_stack(tmp_path)
    st.ledger.grant_opening(UID)
    st.ledger.hold(UID, "h", 100 * MC, "a1", worst_mc=100 * MC)
    st.ledger.settle(UID, "h", 100 * MC)
    assert st.ledger.refund(UID, "a1", "failed:test") == 100 * MC
    assert st.ledger.balance_mc(UID) == st.cfg.allowance_mc                # the credits are back ...
    assert st.store.get(UID)["day"][st.ledger.today()] == 100 * MC         # ... the day is not: 3 such actions reach the 300 limit
    for i in range(2):
        st.ledger.hold(UID, f"h{i}", 100 * MC, f"b{i}", worst_mc=100 * MC)
        st.ledger.settle(UID, f"h{i}", 100 * MC)
        st.ledger.refund(UID, f"b{i}", "failed:test")
    with pytest.raises(BassError) as e:
        st.ledger.hold(UID, "one-more", MC, "c1", worst_mc=MC)
    assert e.value.code == "beta_tester_daily"


def test_m6_a_hold_reserves_the_input_at_the_cache_write_rate():
    plain, worst = meter.estimate_turn(P.SONNET, 40_000, 16_000), meter.worst_turn(P.SONNET, 40_000, 16_000)
    r = meter.rate_for(P.SONNET, 40_000)
    assert r.cache_write > r.inp and worst - plain == meter._mc(40_000 * (r.cache_write - r.inp) / 1_000_000) > 0
    assert meter.worst_turn(P.HAIKU, 1, 1) >= meter.estimate_turn(P.HAIKU, 1, 1)


def test_m7_a_turn_whose_worst_case_does_not_fit_the_actions_cap_is_not_started(tmp_path):
    st = make_stack(tmp_path, tester_daily_credits=600)
    st.mock.use(M.Scenario("loop", [M.Step(M.Reply([M.text("more"), M.tool_use("create_project", {"name": "Loop"})]))], repeat_last=True))
    st.engine.cfg.per_action_cap_mc = 40 * MC
    out = st.svc.handle(req(build_req()))
    assert out["status"] == "capped" and out["code"] == "action_cap" and 0 < out["credits"]["spent"] <= 40
    st2 = make_stack(tmp_path / "small", tester_daily_credits=600)
    st2.engine.cfg.per_action_cap_mc = 5 * MC                              # less than one Sonnet turn's worst case
    out = st2.svc.handle(req(build_req()))
    assert out["code"] == "action_cap" and st2.mock.message_requests == [] and out["credits"]["spent"] == 0


# ══ parity, first step: get_nodes and get_timeline(compact) are in the belt (they also cut what an edit has to read) ═══════════════════

def test_parity_the_belt_reads_nodes_and_a_compact_timeline_for_the_callers_own_timeline_only(tmp_path):
    from alto.bass import tools as T
    st = make_stack(tmp_path)
    assert "get_nodes" in T.BASS_TOOLS and "get_nodes" not in T.WRITE_TOOLS
    specs = {s["name"]: s for s in st.tools.specs()}
    assert "compact" in specs["get_timeline"]["input_schema"]["properties"] and "fields" in specs["get_nodes"]["input_schema"]["properties"]
    brief = json.loads((ROOT / "samples" / "contracts_brief.json").read_text("utf-8"))
    st.mock.use(M.build("Contracts", brief["brief"], brief["nodes"], brief["connections"]))
    assert st.svc.handle(req(build_req()))["ok"] is True
    tl = st.tools.store.list_timelines(UID)
    tid = tl[0] if isinstance(tl[0], str) else (tl[0].get("id") or tl[0].get("timeline_id"))
    mine = st.tools.execute(UID, "get_nodes", {"timeline_id": tid, "ids": None, "act": None, "fields": ["title"]})
    assert not mine.is_error and not mine.wrote and len(json.loads(mine.content)["nodes"]) == len(brief["nodes"])
    full = st.tools.execute(UID, "get_timeline", {"timeline_id": tid, "compact": False})
    small = st.tools.execute(UID, "get_timeline", {"timeline_id": tid, "compact": True})
    assert not small.is_error and len(small.content) <= len(full.content)
    other = st.tools.execute("u_someone_else", "get_nodes", {"timeline_id": tid, "ids": None, "act": None, "fields": None})
    assert other.is_error and brief["nodes"][0]["title"] not in other.content      # another account's id gets nothing
