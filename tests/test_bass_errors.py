"""Every Anthropic failure mode, through the real SDK exceptions: right user message, right retries (fake clock, no real
sleep), right refund, right kill-switch flags. A failed turn never costs the student anything."""
import anthropic
import pytest

from bass_support import bass_guard  # noqa: F401
from alto import mcp_server as srv
from alto.store.local import LocalStore
from alto.bass import engine as E
from alto.bass import errors as ER
from alto.bass import mock_anthropic as M
from alto.bass import config as P
from alto.bass.client import make_client
from alto.bass.ledger import Ledger, MemoryStore
from alto.bass.tools import ToolBox

MC = P.MC


@pytest.fixture
def env(tmp_path):
    class Env:
        pass
    e = Env()
    e.mock = M.MockAnthropic(M.Scenario("t", [M.Step(M.say("All good.")), M.Step(M.say("All good again."))]))
    e.client = make_client("mock", mock=e.mock)
    e.ledger = Ledger(MemoryStore())
    e.ledger.grant_allowance("u1", 100)
    e.slept = []
    e.flags = ER.Flags()
    e.engine = E.Engine(e.client, e.ledger, ToolBox(LocalStore(tmp_path / "s")), flags=e.flags, sleep=e.slept.append)
    e.start = e.ledger.balance_mc("u1")
    yield e
    srv.set_store(None)


def untouched(env):
    assert env.ledger.balance_mc("u1") == env.start and env.ledger.held_mc("u1") == 0


# ── retries ────────────────────────────────────────────────────────────────────────────────────────────────────

def test_429_honours_retry_after_then_succeeds(env):
    env.mock.inject(M.rate_limit(retry_after=7))
    r = env.engine.run_action("u1", "hello")
    assert r.status == "done" and env.slept == [7.0]
    assert r.refunded_mc == 0 and r.spent_mc > 0 and env.flags.bass_enabled


def test_429_retry_after_is_capped(env):
    env.mock.inject(M.rate_limit(retry_after=900))
    env.engine.run_action("u1", "hello")
    assert env.slept == [P.RETRY_MAX_WAIT_S]


def test_429_forever_gives_up_with_a_plain_message_and_no_charge(env):
    env.mock.inject(M.rate_limit(retry_after=2, times=99))
    r = env.engine.run_action("u1", "hello")
    assert r.status == "error" and r.code == "rate_limited"
    assert "busy" in r.user_message.lower() and "Nothing was charged" in r.user_message
    assert env.slept == [2.0] * P.MAX_RETRIES                          # bounded
    untouched(env)
    assert env.flags.bass_enabled and env.flags.alerts == []


def test_529_backs_off_exponentially_then_succeeds(env):
    env.mock.inject(M.overloaded(times=2))
    r = env.engine.run_action("u1", "hello")
    assert r.status == "done" and env.slept == [1, 2]


def test_529_exhausted_refunds(env):
    env.mock.inject(M.overloaded(times=99))
    r = env.engine.run_action("u1", "hello")
    assert r.status == "error" and r.code == "overloaded" and len(env.slept) == P.MAX_RETRIES
    untouched(env)


def test_a_connect_error_is_retried_free_but_a_read_timeout_is_booked_and_never_retried(env):
    env.mock.inject(M.connect_error())                               # never connected: provably unbilled, retried
    r = env.engine.run_action("u1", "hello")
    assert r.status == "done" and len(env.slept) == 1
    env.mock.inject(M.read_timeout())                                # the request left and nothing came back: it may be billed (finding M1)
    n = len(env.mock.message_requests)
    r = env.engine.run_action("u1", "again")
    assert r.status == "error" and r.code == "timeout" and len(env.slept) == 1 and len(env.mock.message_requests) == n + 1   # ONE attempt
    assert r.absorbed_mc > 0 and env.ledger.held_mc("u1") == 0
    assert [e["mc"] for e in env.ledger.entries("u1") if e["kind"] == "absorbed"][-1] == r.absorbed_mc


def test_timeout_forever_refunds(env):
    env.mock.inject(M.read_timeout(times=99))
    r = env.engine.run_action("u1", "hello")
    assert r.code == "timeout" and "too long" in r.user_message
    untouched(env)


def test_500_is_retried_and_alerts_when_it_persists(env):
    env.mock.inject(M.api_error())
    assert env.engine.run_action("u1", "hello").status == "done"
    env.mock.inject(M.api_error(times=99))
    r = env.engine.run_action("u1", "again")
    assert r.code == "upstream" and env.flags.alerts and env.flags.alerts[-1]["code"] == "upstream"
    assert env.flags.bass_enabled                                   # an alert, not a shutdown


def test_mid_stream_error_is_never_retried_and_is_booked_as_altos_cost_not_the_students(env):
    env.mock.inject(M.stream_error(after_events=4))
    r = env.engine.run_action("u1", "hello", on_event=lambda ev: None)
    assert r.status == "error" and env.slept == [] and len(env.mock.message_requests) == 1     # finding M1: no retry after the first stream event
    assert r.absorbed_mc > 0 and r.refunded_mc == 0 and r.spent_mc == 0
    assert env.ledger.held_mc("u1") == 0 and env.ledger.balance_mc("u1") == env.start          # the student pays nothing ...
    assert sum(e["mc"] for e in env.ledger.entries("u1") if e["kind"] == "absorbed") == r.absorbed_mc    # ... Alto's books keep the worst case


def test_dropped_stream_is_a_connection_error_and_refunds(env):
    env.mock.inject(M.stream_drop(after_events=4, times=99))
    r = env.engine.run_action("u1", "hello", on_event=lambda ev: None)
    assert r.status == "error" and r.code in ("connection", "upstream")
    untouched(env)


# ── Alto-side faults: kill switch / pause ──────────────────────────────────────────────────────────────────────

def test_401_trips_the_kill_switch_never_blames_the_student_and_stops_all_traffic(env):
    env.mock.inject(M.auth_error())
    r = env.engine.run_action("u1", "hello")
    assert r.status == "error" and r.code == "auth" and env.slept == []          # no retry
    assert "maintenance" in r.user_message and "your" not in r.user_message.lower()
    untouched(env)
    assert env.flags.bass_enabled is False and env.flags.reason == "auth"
    assert env.flags.alerts[-1]["code"] == "auth"
    seen = len(env.mock.requests)
    r2 = env.engine.run_action("u1", "hello again")                              # nobody else gets through either
    assert r2.status == "paused" and r2.code == "bass_paused" and len(env.mock.requests) == seen
    env.flags.reset()
    assert env.engine.run_action("u1", "back").status == "done"


def test_anthropic_balance_low_pauses_bass_refunds_and_alerts(env):
    env.mock.inject(M.credit_balance_low())
    r = env.engine.run_action("u1", "hello")
    assert r.code == "balance_low" and "maintenance" in r.user_message
    untouched(env)
    assert not env.flags.bass_enabled and env.flags.reason == "balance_low"
    assert env.flags.alerts[-1]["code"] == "balance_low"
    assert "credit balance" in env.flags.alerts[-1]["detail"]["message"]


def test_failure_after_good_work_keeps_the_work_and_refunds_only_the_failed_turn(env):
    env.mock.use(M.Scenario("t", [M.Step(M.Reply([M.tool_use("create_project", {"name": "Kept"})])),
                                  M.Step(M.say("never reached"))]))
    # let turn 1 through, then answer every later /v1/messages call with a 401
    orig = env.mock.handle
    state = {"n": 0}

    def flaky(request):
        if request.url.path == "/v1/messages":
            state["n"] += 1
            if state["n"] >= 2:
                return env.mock._error(401, "authentication_error", "invalid x-api-key")
        return orig(request)
    env.mock.handle = flaky
    env.client = make_client("mock", mock=env.mock)
    env.engine.client = env.client
    r = env.engine.run_action("u1", "build")
    assert r.status == "error" and r.wrote
    assert r.spent_mc > 0 and r.refunded_mc == 0                    # the stored project stays paid for
    assert env.ledger.held_mc("u1") == 0


# ── classification, unit level ─────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("fault,code,retry", [
    (M.rate_limit(), "rate_limited", True), (M.overloaded(), "overloaded", True),
    (M.auth_error(), "auth", False), (M.credit_balance_low(), "balance_low", False),
    (M.api_error(), "upstream", True), (M.read_timeout(), "timeout", True), (M.connect_error(), "connection", True),
    (M.Fault("http", 403, "permission_error", "no"), "auth", False),
    (M.Fault("http", 404, "not_found_error", "model: x"), "bad_request", False),
    (M.Fault("http", 400, "invalid_request_error", "messages: bad"), "bad_request", False),
])
def test_classify(fault, code, retry):
    m = M.MockAnthropic()
    c = make_client("mock", mock=m)
    m.inject(fault)
    with pytest.raises(anthropic.APIError) as e:
        c.messages.create(model="claude-haiku-5-5", max_tokens=10, messages=[{"role": "user", "content": "x"}])
    err = ER.classify(e.value)
    assert isinstance(err, ER.UpstreamError) and err.code == code and err.policy.retry is retry
    assert err.user_message == ER.POLICIES[code].user_message


def test_every_policy_message_is_plain_and_blames_no_one():
    for p in ER.POLICIES.values():
        assert p.user_message and "token" not in p.user_message.lower()
        assert "you did" not in p.user_message.lower() and "your fault" not in p.user_message.lower()
    for code in ("rate_limited", "overloaded", "timeout", "connection", "upstream", "auth", "balance_low",
                 "bad_request", "refused"):
        assert "Nothing was charged" in ER.POLICIES[code].user_message


def test_classify_leaves_bass_errors_alone_and_unknowns_become_upstream():
    e = ER.InsufficientCredits()
    assert ER.classify(e) is e
    assert ER.classify(RuntimeError("???")).code == "upstream"


def test_flags_only_trip_for_kill_or_pause_policies():
    f = ER.Flags()
    f.trip(ER.POLICIES["rate_limited"])
    assert f.bass_enabled and not f.alerts
    f.trip(ER.POLICIES["upstream"], {"x": 1})
    assert f.bass_enabled and f.alerts == [{"code": "upstream", "detail": {"x": 1}}]
    f.trip(ER.POLICIES["auth"])
    assert not f.bass_enabled
