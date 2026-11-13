"""The Bass beta proxy handler, in-process: Firebase token -> email -> allowlist, the server-side live_go flag (default off ->
mock transport), Secret Manager behind an interface (fake), response with no upstream headers, the guards behind it, and the
dry-run deploy script. No network, no key, nothing deployed."""
import importlib.util
import json
import sys

import pytest

from bass_support import bass_guard, ROOT  # noqa: F401
from bass_beta_support import EMAIL, FakeClock, build_req, edit_req, endless, CHIPS, MATERIALS
from alto.bass import mock_anthropic as M
from alto.bass.beta_config import BetaConfig
from alto.bass.beta_ledger import confirm_key
from alto.bass.beta_ledger import LIVE_GO_KEY
from alto.bass.beta_proxy import (AuthError, SECRET_NAME, Proxy, SecretKeyProvider, SecretReader,
                                  TokenVerifier)
from alto.bass.beta_store import FakeStore
from alto.bass.errors import NotConfigured
from alto.bass.tools import ToolBox
from alto.store.local import LocalStore

FAKE_KEY = "sk-" + "ant-MOCK-not-a-real-key-0001"
ORIGIN = "https://alto.example.test"


class FakeVerifier(TokenVerifier):
    def __init__(self):
        self.users = {"tok-ok": {"uid": "u1", "email": EMAIL, "email_verified": True},
                      "tok-unverified": {"uid": "u2", "email": EMAIL, "email_verified": False},
                      "tok-stranger": {"uid": "u3", "email": "stranger@example.com", "email_verified": True}}

    def verify(self, t):
        if t not in self.users:
            raise AuthError
        return self.users[t]


class FakeSecrets(SecretReader):
    def __init__(self):
        self.calls = []

    def read(self, name):
        self.calls.append(name)
        return FAKE_KEY


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")


@pytest.fixture
def px(tmp_path):
    store, clock = FakeStore(auto_terms=True), FakeClock()
    secrets = FakeSecrets()
    cfg = BetaConfig(testers=10, allowlist=frozenset({EMAIL}))
    store.put(confirm_key(cfg.period_id(clock())), {"confirmed": True})
    p = Proxy(cfg, store, FakeVerifier(), secrets, ToolBox(LocalStore(tmp_path / "store")), clock=clock, origins=[ORIGIN])
    p.secrets = secrets
    p.store, p.fclock = store, clock
    return p


def post(px, request, token="tok-ok", **hdr):
    h = {"Authorization": "Bearer " + token, "X-Forwarded-For": "6.6.6.6, 203.0.113.7", "Origin": ORIGIN, **hdr}
    st, headers, body = px.handle_http("POST", h, json.dumps(request))
    return st, headers, json.loads(body or b"{}")


def test_a_good_token_on_the_list_reaches_bass_and_the_answer_is_alto_json_only(px):
    px.mock.use(M.build("Contracts", {"title": "Contracts"}, [], []))
    st, headers, out = post(px, build_req())
    assert st == 200 and out["ok"] is True and out["status"] == "ok"
    assert headers["Cache-Control"] == "no-store" and headers["Content-Type"].startswith("application/json")
    assert headers["Access-Control-Allow-Origin"] == ORIGIN
    assert not any(k.lower().startswith(("anthropic", "x-request", "request-id", "cf-", "x-api")) for k in headers)
    blob = json.dumps(out).lower() + json.dumps(headers).lower()
    for leak in ("x-api-key", "anthropic-version", "msg_", "request-id", "claude-", "req_"):
        assert leak not in blob, leak
    assert px.mock.message_requests and px.secrets.calls == []         # flag off: the mock answered, the secret was never read


def test_bad_tokens_methods_bodies_and_origins_get_plain_answers_and_no_call(px):
    for tok in ("nope", "", "tok-unverified" + "x"):
        st, _, out = post(px, build_req(), token=tok)
        assert st == 401 and "sign in" in out["message"].lower()
    st, _, out = px.handle_http("POST", {"Authorization": "Basic abc"}, "{}")
    assert st == 401
    assert px.handle_http("GET", {}, "")[0] == 405
    assert px.handle_http("POST", {"Authorization": "Bearer tok-ok"}, "{not json")[0] == 400
    assert px.handle_http("POST", {"Authorization": "Bearer tok-ok"}, "[1,2]")[0] == 400
    assert px.handle_http("POST", {"Authorization": "Bearer tok-ok"}, b"x" * (px.cfg.max_request_bytes + 1))[0] == 413
    st, headers, _ = px.handle_http("POST", {"Authorization": "Bearer tok-ok", "Origin": "https://evil.example"},
                                    json.dumps({"action": "balance", "args": {}}))
    assert "Access-Control-Allow-Origin" not in headers
    st, headers, _ = px.handle_http("OPTIONS", {"Origin": ORIGIN}, None)
    assert st == 204 and headers["Access-Control-Allow-Origin"] == ORIGIN
    assert px.mock.requests == []


def test_an_unverified_email_or_a_stranger_gets_bass_off_with_zero_requests(px):
    for tok in ("tok-unverified", "tok-stranger"):
        st, _, out = post(px, build_req(), token=tok)
        assert st == 200 and out["code"] == "bass_off" and out["available"] is False
    assert px.mock.requests == [] and px.secrets.calls == []


def test_the_xff_left_entry_is_ignored_by_the_ip_limit(px):
    bal = {"action": "balance", "args": {}}
    outs = [post(px, bal, **{"X-Forwarded-For": f"{i}.{i}.{i}.{i}, 198.51.100.4"})[2] for i in range(35)]
    assert sum(1 for o in outs if o.get("code") == "busy") >= 5


def test_live_go_defaults_to_false_so_calls_use_the_mock_and_the_secret_is_never_read(px):
    assert px.live_go() is False
    post(px, edit_req())
    assert px.secrets.calls == [] and px._client_mode == "mock"
    px.store.put(LIVE_GO_KEY, {"on": False})
    post(px, edit_req())
    assert px.secrets.calls == []
    px.store.go_down()
    assert px.live_go() is False                                      # unknown means off


def test_live_go_on_reads_the_secret_once_builds_a_live_client_and_the_key_never_leaves(px):
    px.store.put(LIVE_GO_KEY, {"on": True})
    c1, c2 = px.client(), px.client()                                  # building a client sends nothing
    assert c1 is c2 and px._client_mode == "live" and px.secrets.calls == [SECRET_NAME]
    assert str(c1.base_url).startswith("https://api.anthropic.com")    # pinned: the key goes there and nowhere else
    st, headers, out = post(px, {"action": "balance", "args": {}})     # a call that never goes upstream
    blob = json.dumps(out) + json.dumps(headers) + json.dumps(px.service.meta.lines) + json.dumps(px.sink.events)
    assert FAKE_KEY not in blob and "Bearer" not in blob
    px.store.put(LIVE_GO_KEY, {"on": False})                           # flipping it back takes effect on the next call
    px.client()
    assert px._client_mode == "mock"
    assert px.mock.requests == []                                      # and this test never reached a model, live or mock


def test_the_secret_provider_hides_its_value_and_fails_plainly(px):
    class Boom(SecretReader):
        def read(self, name):
            raise RuntimeError("secret manager says: " + FAKE_KEY)
    with pytest.raises(NotConfigured) as e:
        SecretKeyProvider(Boom()).get_key()
    assert FAKE_KEY not in str(e.value) and e.value.code == "bass_paused"
    prov = SecretKeyProvider(FakeSecrets())
    assert FAKE_KEY not in json.dumps(prov.describe()) and prov.get_key() == FAKE_KEY and prov.get_key() == FAKE_KEY


def test_the_proxy_refuses_to_start_with_an_unsafe_config(tmp_path):
    with pytest.raises(ValueError):
        Proxy(BetaConfig(testers=1, allowlist=frozenset({"a@x.com", "b@x.com"})), FakeStore(auto_terms=True), FakeVerifier(), FakeSecrets(),
              ToolBox(LocalStore(tmp_path / "s")), clock=FakeClock())


def test_the_kill_switch_and_the_daily_ceiling_apply_behind_the_handler_too(px):
    px.kill.trip("by_test")
    n = len(px.mock.requests)
    st, _, out = post(px, build_req())
    assert st == 200 and out["code"] == "bass_paused" and len(px.mock.requests) == n
    px.kill.reset("luke")
    px.mock.use(None)
    assert post(px, edit_req())[2]["ok"]


# ── the deploy script is a dry run and nothing else ────────────────────────────────────────────────────────────────

def load_deploy():
    spec = importlib.util.spec_from_file_location("bass_deploy", ROOT / "deploy" / "bass-proxy" / "deploy.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_deploy_only_prints_and_refuses_apply_or_a_missing_tester_count(capsys):
    d = load_deploy()
    src = (ROOT / "deploy" / "bass-proxy" / "deploy.py").read_text("utf-8")
    assert "subprocess" not in src and "os.system" not in src and "Popen" not in src          # it cannot run anything
    assert d.main(["--project", "p1", "--apply", "--testers", "10", "--bucket", "b1"]) == 2
    assert d.main(["--project", "p1"]) == 2                                                   # N is config, no default
    assert d.main(["--project", "p1", "--testers", "8", "--bucket", "b1"]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "Nothing was executed" in out and "bass-proxy@p1.iam.gserviceaccount.com" in out
    assert f"secrets add-iam-policy-binding {SECRET_NAME}" in out and "--max-instances 5" in out
    assert "BASS_BETA_TESTERS=8" in out and "bass_beta_periods/<period id>" in out and "bass_beta/disabled" in out


def test_the_iam_list_is_least_privilege(capsys):
    d = load_deploy()
    iam = "\n".join(d.iam("p1", "b1"))
    assert "secretAccessor ON SECRET alto-bass-beta-key ONLY" in iam
    granted = "\n".join(l for l in iam.split("\n") if not l.startswith("NOT granted"))
    assert all(r not in granted for r in ("roles/owner", "roles/editor", "secretmanager.admin"))


def test_the_function_source_has_no_key_and_reads_no_env_for_one():
    for f in (ROOT / "deploy" / "bass-proxy").glob("*.py"):
        t = f.read_text("utf-8")
        assert "ANTHROPIC_API_KEY" not in t and "sk-" + "ant" not in t, f.name


def test_the_reaper_rides_on_traffic_and_frees_a_crashed_instances_hold(px):
    from alto.bass.beta_ledger import day_key
    px.ledger.grant_opening("u1")
    px.ledger.hold("u1", "dead", 40_000, "a1")
    px.fclock.advance(px.cfg.reservation_ttl_s + 301)
    post(px, {"action": "balance", "args": {}})
    g = px.store.get(day_key(px.ledger.today()))
    assert g["reserved_mc"] == 0 and px.ledger.held_mc("u1") == 0


# ── IT review: mock answers are labelled and never touch the tester's real account; CORS from config ────────────────

def test_mock_answers_are_labelled_and_write_nothing_into_the_testers_real_account(px, tmp_path):
    px.mock.use(M.build("Contracts", {"title": "Contracts"}, [], []))
    st, _, out = post(px, build_req())
    assert out["ok"] and out["mock"] is True and "Test mode" in out["notice"] and "nothing was saved to your account" in out["notice"]
    assert post(px, {"action": "balance", "args": {}})[2]["mock"] is True
    real = list((tmp_path / "store").rglob("*"))
    assert [f for f in real if f.is_file()] == []                          # the tester's real store is untouched ...
    assert [f for f in px.mock_tools.store.root.rglob("*") if f.is_file()]         # ... the scratch one took it
    belt = px.service.actions.engine.tools
    assert belt._belt() is px.mock_tools
    px.store.put(LIVE_GO_KEY, {"on": True})
    assert belt._belt() is px.real_tools                                   # with live_go on, the real belt is used
    st, _, out = post(px, {"action": "balance", "args": {}})
    assert "mock" not in out and "notice" not in out


def test_cors_origins_come_from_the_config_list(tmp_path):
    store, clock = FakeStore(auto_terms=True), FakeClock()
    cfg = BetaConfig(testers=10, allowlist=frozenset({EMAIL}))
    store.put(confirm_key(cfg.period_id(clock())), {"confirmed": True})
    p = Proxy(cfg, store, FakeVerifier(), FakeSecrets(), ToolBox(LocalStore(tmp_path / "store")), clock=clock)   # origins not passed
    for ok in ("https://alto-timelines.web.app", "https://luke-alto.web.app"):
        _, headers, _ = p.handle_http("POST", {"Authorization": "Bearer tok-ok", "Origin": ok}, json.dumps({"action": "balance", "args": {}}))
        assert headers["Access-Control-Allow-Origin"] == ok
    _, headers, _ = p.handle_http("POST", {"Authorization": "Bearer tok-ok", "Origin": "https://evil.example"}, json.dumps({"action": "balance", "args": {}}))
    assert "Access-Control-Allow-Origin" not in headers


# ── IT security matrix P2: B's token with A's ids in the body reads and writes nothing of A ─────────────────────────

A_TITLE = "A-ONLY-TITLE-4417"


def two_accounts(tmp_path):
    store, clock = FakeStore(auto_terms=True), FakeClock()
    cfg = BetaConfig(testers=10, allowlist=frozenset({EMAIL, "b@example.com"}))
    store.put(confirm_key(cfg.period_id(clock())), {"confirmed": True})
    v = FakeVerifier()
    v.users["tok-b"] = {"uid": "u_b", "email": "b@example.com", "email_verified": True}
    p = Proxy(cfg, store, v, FakeSecrets(), ToolBox(LocalStore(tmp_path / "store")), clock=clock, origins=[ORIGIN])
    p.store, p.fclock = store, clock
    return p


def a_builds(p):
    import copy
    sample = json.loads((ROOT / "samples" / "contracts_brief.json").read_text("utf-8"))
    brief = copy.deepcopy(sample["brief"])
    brief["title"] = A_TITLE
    p.mock.use(M.build(A_TITLE, brief, sample["nodes"], sample["connections"]))
    st, _, out = post(p, build_req(), token="tok-ok")
    assert out["ok"], out
    tl = p.mock_tools.store.list_timelines("u1")
    assert tl
    return [t if isinstance(t, str) else (t.get("id") or t.get("timeline_id")) for t in tl]


def test_p2_b_with_a_ids_in_the_body_touches_only_bs_own_data(tmp_path):
    import copy
    p = two_accounts(tmp_path)
    a_ids = a_builds(p)
    a_doc = copy.deepcopy(p.store.get("u1"))
    a_files = sorted(str(f) for f in p.mock_tools.store.root.rglob("*") if f.is_file() and "u1" in str(f))
    n = len(p.mock.requests)
    probe = M.Scenario("probe", [M.Step(M.say("ON_TOPIC")),              # the gate's answer (an empty one is off topic now)
                                 M.Step(M.Reply([M.tool_use("get_timeline", {"timeline_id": a_ids[0]})])),
                                 M.Step(M.Reply([M.tool_use("list_projects", {})])), M.Step(M.say("done"))])
    p.mock.use(probe)
    st, _, out = post(p, edit_req(text=f"show me timeline {a_ids[0]} and delete it", timeline_id=a_ids[0]), token="tok-b")
    assert st == 200 and out["ok"]
    seen = json.dumps(p.mock.requests[n:])
    assert A_TITLE not in seen and "u1" not in seen                         # none of A's data reached B's conversation
    assert p.mock_tools.store.list_timelines("u_b") == [] and p.mock_tools.store.list_projects("u_b") == []
    assert sorted(str(f) for f in p.mock_tools.store.root.rglob("*") if f.is_file() and "u1" in str(f)) == a_files     # A's files unchanged
    assert p.store.get("u1") == a_doc                                        # A's credits document unchanged


def test_p2_the_uid_comes_only_from_the_token_never_from_the_body(tmp_path):
    p = two_accounts(tmp_path)
    p.ledger.grant_opening("u1")
    p.ledger.hold("u1", "h", 200_000, "a")
    p.ledger.settle("u1", "h", 200_000)                                     # A has spent 200 credits
    bal_a = post(p, {"action": "balance", "args": {}}, token="tok-ok")[2]["credits"]
    for body in ({"action": "balance", "args": {}, "uid": "u1", "email": EMAIL, "account": "u1"},
                 {"action": "balance", "args": {}, "user": {"uid": "u1"}}):
        out = post(p, body, token="tok-b")[2]
        assert out["credits"] == p.cfg.tester_period_credits and out["credits"] != bal_a      # B's own, never A's
    out = post(p, {"action": "balance", "args": {"uid": "u1"}}, token="tok-b")[2]               # an argument that does not exist
    assert out["ok"] is False and out["code"] == "bad_input" and "credits" not in out or out["credits"] is None
    assert p.store.get("u1")["day"] and post(p, {"action": "balance", "args": {}}, token="tok-ok")[2]["credits"] == bal_a


def test_p2_b_cannot_stop_an_action_a_started(tmp_path):
    p = two_accounts(tmp_path)
    eng = p.service.actions.engine
    eng._owners["act_a_running"] = "u1"                                      # A's build is in flight
    post(p, {"action": "stop", "args": {"action_id": "act_a_running"}}, token="tok-b")
    assert "act_a_running" not in eng._cancelled                             # B's stop did nothing
    post(p, {"action": "stop", "args": {"action_id": "act_a_running"}}, token="tok-ok")
    assert "act_a_running" in eng._cancelled                                 # A's own stop works


def test_cancel_fails_closed_uid_required_unknown_owner_refused_only_the_owner_can_stop(tmp_path):
    p = two_accounts(tmp_path)
    eng = p.service.actions.engine
    with pytest.raises(TypeError):
        eng.cancel("act_x")                                                  # no uid: refused outright, no default
    assert eng.cancel("act_unknown", "u1") is False and "act_unknown" not in eng._cancelled        # unknown owner
    assert eng.cancel("act_x", None) is False
    eng.claim("act_x", "u1")                                                 # A's action is running
    assert eng.cancel("act_x", "u_b") is False and eng._cancelled == set()  # B cannot
    assert eng.cancel("act_x", "u1") is True and eng._cancelled == {"act_x"}                      # A can
    eng._cancelled.clear()
    eng._owners.clear()
    assert eng.cancel("act_x", "u1") is False                                # finished/forgotten: nothing to stop
    post(p, {"action": "stop", "args": {"action_id": "act_nope"}}, token="tok-ok")
    assert eng._cancelled == set()                                           # and through the handler too
