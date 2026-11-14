"""IT's review of the beta (ORG/it/bass-beta-review.md) as tests: the function's cold start, the Firestore adapter's retry mapping, a settle
that cannot be booked, input 400s that must not stop Bass for everyone, the org-level limit wordings, trusted proxy hops, limiter memory.
No network, no key, nothing deployed. The Google libraries are stood in for."""
import pytest as _pytest_sdk
_pytest_sdk.importorskip("anthropic")   # public CI has no SDK: these skip there (listed in test_bass_sdk_free.py) and run in the SDK env
_pytest_sdk.importorskip("httpx2")
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

from bass_support import bass_guard, ROOT  # noqa: F401
from bass_beta_support import EMAIL, FakeClock, build_req, edit_req, endless, make_stack, req
from alto.bass import config as P
from alto.bass import mock_anthropic as M
from alto.bass.beta_limits import SlidingLimiter, client_ip
from alto.bass.beta_store import ConflictError, StoreError
from alto.bass.errors import BassError

MC = P.MC
DEPLOY = ROOT / "deploy" / "bass-proxy"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


# ── 1: the function's cold start ─────────────────────────────────────────────────────────────────────────────────

class FakeGoogle:
    """Stands in for firebase_admin, google-cloud-firestore and Secret Manager, enough for _build() to run."""

    def __init__(self, monkeypatch):
        self.buckets, self.initialized = [], 0
        fa = types.ModuleType("firebase_admin")
        fa._apps = {}
        outer = self

        def initialize_app(*a, **k):
            outer.initialized += 1
            fa._apps["[DEFAULT]"] = object()
        fa.initialize_app = initialize_app
        fa_auth = types.ModuleType("firebase_admin.auth")
        fa_auth.verify_id_token = lambda t, check_revoked=False: {"uid": "u", "email": "e@x.com", "email_verified": True}
        fa_fs = types.ModuleType("firebase_admin.firestore")
        fa_fs.client = lambda: object()
        fa_st = types.ModuleType("firebase_admin.storage")
        fa_st.bucket = lambda name: self.buckets.append(name) or object()
        fa.auth, fa.firestore, fa.storage = fa_auth, fa_fs, fa_st
        gc = types.ModuleType("google.cloud")
        gfs = types.ModuleType("google.cloud.firestore")
        gfs.Client = lambda: object()
        gsm = types.ModuleType("google.cloud.secretmanager")
        gsm.SecretManagerServiceClient = lambda: object()
        gc.firestore, gc.secretmanager = gfs, gsm
        g = sys.modules.get("google") or types.ModuleType("google")
        for k, v in {"firebase_admin": fa, "firebase_admin.auth": fa_auth, "firebase_admin.firestore": fa_fs, "firebase_admin.storage": fa_st,
                     "google": g, "google.cloud": gc, "google.cloud.firestore": gfs, "google.cloud.secretmanager": gsm}.items():
            monkeypatch.setitem(sys.modules, k, v)


ENV = {"GCP_PROJECT": "demo-project", "BASS_BETA_TESTERS": "8", "ALTO_BUCKET": "demo-bass-bucket"}


@pytest.fixture
def cold(monkeypatch):
    for k in ("GCP_PROJECT", "BASS_BETA_TESTERS", "ALTO_BUCKET", "BASS_ALLOWED_ORIGINS"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.syspath_prepend(str(DEPLOY))
    fake = FakeGoogle(monkeypatch)
    main = load("bass_proxy_main", DEPLOY / "main.py")
    return main, fake


def test_the_functions_cold_start_builds_with_the_deployed_environment_and_names_the_bucket(cold, monkeypatch):
    main, fake = cold
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    proxy = main._build()
    assert proxy.cfg.testers == 8 and proxy.cfg.problems() == []
    assert fake.buckets == ["demo-bass-bucket"] and fake.initialized == 1
    assert main.bass_proxy is not None and "https://luke-alto.web.app" in proxy.origins


def test_the_cold_start_names_what_is_missing_instead_of_a_500(cold, monkeypatch):
    main, _ = cold
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("ALTO_BUCKET")
    with pytest.raises(RuntimeError) as e:
        main._build()
    assert "ALTO_BUCKET" in str(e.value)
    from alto.store.firestore import FirestoreStore                         # and the real store really does need it
    with pytest.raises(RuntimeError):
        FirestoreStore()


def test_the_deploy_plan_sets_every_variable_main_reads_and_grants_only_what_it_needs(capsys):
    d = load("bass_deploy", DEPLOY / "deploy.py")
    main_src = (DEPLOY / "main.py").read_text("utf-8")
    assert d.main(["--project", "p1", "--testers", "8", "--bucket", "b1"]) == 0
    out = capsys.readouterr().out
    for k in ("GCP_PROJECT", "BASS_BETA_TESTERS", "ALTO_BUCKET", "BASS_ALLOWED_ORIGINS"):
        assert k in main_src and f"{k}=" in out, k
    assert "ALTO_BUCKET=b1" in out and "--memory 512Mi" in out and "--concurrency 4" in out and "--timeout 300s" in out
    assert "roles/storage.objectAdmin" in out and "gs://b1" in out and "firebaseauth.viewer" in out.split("NOT granted")[1].split("\n")[0]
    granted = "\n".join(l for l in out.split("\n") if "NOT granted" not in l)
    assert "firebaseauth.viewer" not in granted and "buckets create" not in out and "mb gs" not in out        # no bucket is created
    assert "alto-timelines.web.app" in out and "luke-alto.web.app" in out                                             # CORS from config
    assert d.main(["--project", "p1", "--testers", "8"]) == 2                                                    # the bucket is required


def test_the_bundle_requirements_pin_what_was_tested_and_carry_the_connectors(tmp_path):
    b = load("bass_bundle", DEPLOY / "build_bundle.py")
    reqs = b.merged_requirements()
    assert "anthropic==" in reqs and "google-cloud-storage" in reqs and "firebase-admin==" in reqs
    lines = [b._name(l) for l in reqs.splitlines() if l.strip() and not l.startswith("#")]
    assert "mcp" in lines and len(lines) == len(set(lines))                    # the connector's own requirements, no duplicates
    assert b.main.__code__ and (DEPLOY / "requirements.txt").read_text("utf-8").count("anthropic==") == 1
    sys.argv = ["build_bundle", str(tmp_path / "bundle")]
    assert b.main() == 0
    assert (tmp_path / "bundle" / "main.py").is_file() and (tmp_path / "bundle" / "alto" / "bass" / "beta_proxy.py").is_file()
    assert "anthropic==" in (tmp_path / "bundle" / "requirements.txt").read_text("utf-8")


# ── 2: the Firestore adapter's transaction retries and document map ───────────────────────────────────────────────

@pytest.fixture
def fs(monkeypatch):
    class Aborted(Exception):
        pass

    class Conflict(Exception):
        pass
    gexc = types.ModuleType("google.api_core.exceptions")
    gexc.Aborted, gexc.Conflict = Aborted, Conflict
    api = types.ModuleType("google.api_core")
    api.exceptions = gexc
    gfs = types.ModuleType("google.cloud.firestore")
    gfs.transactional = lambda fn: fn
    gc = types.ModuleType("google.cloud")
    gc.firestore = gfs
    g = sys.modules.get("google") or types.ModuleType("google")
    for k, v in {"google": g, "google.api_core": api, "google.api_core.exceptions": gexc, "google.cloud": gc, "google.cloud.firestore": gfs}.items():
        monkeypatch.setitem(sys.modules, k, v)
    monkeypatch.syspath_prepend(str(DEPLOY))
    mod = load("bass_fs_store", DEPLOY / "firestore_store.py")

    class DB:
        attempts_seen = []

        def transaction(self, max_attempts=5):
            DB.attempts_seen.append(max_attempts)
            return object()
    return mod, DB(), gexc


def test_the_adapter_sets_the_retry_count_and_maps_exhausted_retries_to_a_conflict(fs):
    mod, db, gexc = fs
    s = mod.FirestoreStore(db)
    assert s.run_transaction(lambda txn: 42, retries=25) == 42 and db.attempts_seen[-1] == 25
    def lost(_txn):
        raise ValueError("Failed to commit transaction in 25 attempts.")
    with pytest.raises(ConflictError):
        s.run_transaction(lost, retries=25)
    def aborted(_txn):
        raise gexc.Aborted("409 aborted")
    with pytest.raises(ConflictError):
        s.run_transaction(aborted)
    def ours(_txn):
        raise ValueError("a hold must be positive")                          # the guards' own bug is not a store problem
    with pytest.raises(ValueError) as e:
        s.run_transaction(ours)
    assert not isinstance(e.value, StoreError)
    def bass(_txn):
        raise BassError(code="beta_credits_used")
    with pytest.raises(BassError):
        s.run_transaction(bass)
    class GoogleDown(Exception):
        __module__ = "google.api_core.exceptions"
    def down(_txn):
        raise GoogleDown("503")
    with pytest.raises(StoreError):
        s.run_transaction(down)


def test_the_document_map_matches_what_it_reads_and_writes(fs):
    mod, _, _ = fs
    P_ = mod._path
    assert P_("bass_beta/periods/2026-10-17") == ("bass_beta_periods", "2026-10-17")
    assert P_("bass_beta/disabled") == ("bass_beta", "disabled")
    assert P_("bass_beta/kill") == ("bass_beta", "kill") and P_("bass_beta/allowlist") == ("bass_beta", "allowlist")
    assert P_("bass_beta/live_go") == ("bass_beta", "live_go")
    assert P_("bass_beta/day/2026-11-03") == ("bass_beta_days", "2026-11-03")
    assert P_("bass_beta/pc/2026-10-17") == ("bass_beta_period_counters", "2026-10-17")
    assert P_("u_abc") == ("bass_credits", "u_abc")
    assert mod.is_retries_exhausted(ValueError("Failed to commit transaction in 5 attempts.")) and not mod.is_retries_exhausted(ValueError("x"))


# ── 3: a settle that cannot be booked ──────────────────────────────────────────────────────────────────────────

def test_a_settle_that_still_fails_after_the_retries_trips_the_kill_switch_and_the_reaper_books_the_whole_reservation(tmp_path):
    st = make_stack(tmp_path)
    st.ledger.grant_opening("u1")
    st.ledger.hold("u1", "paid", 50 * MC, "a1")                              # the model call happened and was paid for
    st.store.inject_conflicts(999)
    with pytest.raises(BassError) as e:
        st.ledger.settle("u1", "paid", 30 * MC)
    assert e.value.code == "bass_paused" and st.slept == [0.25, 0.5, 1.0]    # backed off between the 4 attempts
    assert st.kill.is_on() and st.sink.of("settle_failed")[0]["unbooked_mc"] == 30 * MC
    assert st.sink.of("settle_failed")[0]["hold"] == "paid" and st.sink.of("kill_switch")
    st.store.inject_conflicts(0)
    st.clock.advance(st.cfg.reservation_ttl_s + 1)
    assert st.ledger.reap() == 1                                             # finding M2: the reaper BOOKS the abandoned reservation in full
    day = st.store.get("bass_beta/day/" + st.ledger.today())
    assert day["spent_mc"] == 50 * MC and day["reserved_mc"] == 0             # (50, the worst case: at least the 30 that was paid)
    assert st.ledger.held_mc("u1") == 0 and st.sink.of("abandoned_calls_booked")[0]["absorbed_mc"] == 50 * MC
    assert st.kill.state()["on"] is True and st.store.get("bass_beta/kill")["on"] is True     # the switch still stays on until a human looks
    assert st.svc.handle(req(edit_req()))["code"] == "bass_paused"


def test_a_settle_that_fails_once_or_twice_is_retried_and_booked(tmp_path):
    st = make_stack(tmp_path)
    st.ledger.grant_opening("u1")
    st.ledger.hold("u1", "paid", 50 * MC, "a1")
    st.store.inject_conflicts(30)                                            # the first attempt's 25 tries lose, the second wins
    assert st.ledger.settle("u1", "paid", 30 * MC)["charged_mc"] == 30 * MC
    assert len(st.slept) == 1 and not st.kill.is_on() and not st.sink.of("settle_failed")
    assert st.store.get("bass_beta/day/" + st.ledger.today())["spent_mc"] == 30 * MC


# ── 4/5: which 400s stop Bass for everyone, and the org-level wordings ────────────────────────────────────────────

@pytest.mark.parametrize("msg", ["prompt is too long: 250000 tokens > 200000 maximum", "A maximum of 100 PDF pages may be provided",
                                 "Could not process image", "messages.0.content.1.document: the document is corrupted"])
def test_a_known_input_400_is_that_testers_problem_alone_and_does_not_trip_the_switch(tmp_path, msg):
    st = make_stack(tmp_path)
    st.mock.use(endless(2000)).inject(M.input_400(msg, times=9))
    out = st.svc.handle(req(build_req()))
    assert out["code"] == "bad_input" and out["status"] == "error" and "Nothing was charged" in out["message"]
    assert len(st.mock.errors_sent) == 1 and not st.kill.is_on() and not st.sink.of("kill_switch")       # no retry, no trip
    assert st.ledger.balance_mc("u_tester1") == st.cfg.allowance_mc
    st.mock.faults.clear()
    st.mock.use(M.build("Contracts", {"title": "Contracts"}, [], []))
    st.clock.advance(61)
    assert st.svc.handle(req(build_req()))["ok"]                              # everyone, including this tester, carries on


def test_an_unexpected_400_that_is_clearly_ours_still_trips_it(tmp_path):
    st = make_stack(tmp_path)
    st.mock.use(endless(2000)).inject(M.unexpected_400(times=3))
    st.svc.handle(req(build_req()))
    assert st.kill.state() == {"on": True, "reason": "upstream_bad_request"} and len(st.mock.errors_sent) == 1


@pytest.mark.parametrize("fault", [M.org_limit, M.workspace_limit, M.spend_limit_429, M.spend_limit_429_flat])
def test_the_console_and_org_limit_wordings_and_the_429_spend_cap_trip_the_switch_with_the_friendly_message_and_no_retry(tmp_path, fault):
    st = make_stack(tmp_path)
    st.mock.use(endless(2000)).inject(fault(times=9))
    out = st.svc.handle(req(build_req()))
    assert "beta credits are used up" in out["message"]
    assert len(st.mock.errors_sent) == 1                                     # a 429 is normally retried: this one is not
    assert st.kill.state() == {"on": True, "reason": "upstream_workspace_limit"} and st.sink.of("kill_switch")
    assert st.ledger.balance_mc("u_tester1") == st.cfg.allowance_mc


def test_an_ordinary_429_is_still_retried_not_tripped(tmp_path):
    st = make_stack(tmp_path)
    st.mock.use(M.build("Contracts", {"title": "Contracts"}, [], [])).inject(M.rate_limit(retry_after=1, times=1))
    out = st.svc.handle(req(build_req()))
    assert out["ok"] and not st.kill.is_on() and len(st.mock.errors_sent) == 1


# ── 8, 9: trusted hops and limiter memory ──────────────────────────────────────────────────────────────────────

def test_client_ip_trusts_exactly_the_hops_it_is_told_to():
    xff = "6.6.6.6, 198.51.100.4, 130.211.0.1"
    assert client_ip(xff) == "130.211.0.1"                                   # direct run.app: the last entry (Google's)
    assert client_ip(xff, hops=2) == "198.51.100.4"                          # behind one more trusted proxy: the one before it
    assert client_ip(xff, hops=3) == "6.6.6.6" and client_ip("1.2.3.4", hops=2) == "1.2.3.4"
    assert client_ip("x, 2001:db8:1:2:aaaa:bbbb:cccc:dddd, 130.211.0.1", hops=2) == "2001:db8:1:2::/64"


def test_the_service_uses_the_configured_hops_so_a_shared_front_end_does_not_make_one_ip_bucket(tmp_path):
    for hops, expect_limited in ((1, True), (2, False)):
        st = make_stack(tmp_path / str(hops), emails=[f"t{i}@example.com" for i in range(10)], trusted_hops=hops)
        outs = [st.svc.handle(req({"action": "balance", "args": {}}, email=f"t{i % 10}@example.com",
                                  xff=f"9.9.9.9, 198.51.100.{i}, 130.211.0.1")) for i in range(40)]      # 40 different real clients behind one front end
        assert (sum(1 for o in outs if o.get("code") == "busy") > 0) is expect_limited


def test_the_limiter_forgets_idle_keys_and_empty_counts():
    clock = FakeClock()
    lim = SlidingLimiter(lambda: clock.ts())
    for i in range(700):
        lim.allow(f"ip:{i}", 5, 60)
    assert lim.size() == 700
    clock.advance(7200)
    lim.allow("ip:new", 5, 60)
    assert lim.size() <= 2
    lim.allow("a", 5, 60)
    clock.advance(120)
    assert lim.count("a", 60) == 0 and "a" not in lim._hits


# ── IT re-review of f8ba660 ────────────────────────────────────────────────────────────────────────────────────

def test_the_real_429_shape_error_details_error_code_is_read_and_so_is_the_flat_one():
    from alto.bass import errors as ER

    class Exc(Exception):
        status_code = 429

        def __init__(self, body):
            self.body = body
    real = {"type": "error", "error": {"type": "rate_limit_error", "message": "over", "details": {"error_code": "enforced_spend_limit_reached"}}}
    flat = {"type": "error", "error": {"type": "rate_limit_error", "message": "over", "error_code": "enforced_spend_limit_reached"}}
    plain = {"type": "error", "error": {"type": "rate_limit_error", "message": "slow down"}}
    assert ER._error_code(Exc(real)) == ER._error_code(Exc(flat)) == "enforced_spend_limit_reached" and ER._error_code(Exc(plain)) == ""
    import anthropic

    class A(anthropic.APIStatusError):
        def __init__(self, body):
            Exception.__init__(self, "x")
            self.body, self.status_code = body, 429
    assert ER.classify(A(real)).code == "workspace_limit" and ER.classify(A(plain)).code == "rate_limited"


def test_the_bundle_requirements_cover_every_third_party_module_the_cold_start_imports():
    import ast
    b = load("bass_bundle2", DEPLOY / "build_bundle.py")
    have = {b._name(l) for l in b.merged_requirements().splitlines() if l.strip() and not l.startswith("#")}
    assert "tzdata" in have                                                  # BetaConfig's ZoneInfo needs zone data on a slim image
    pkg = {"anthropic": {"anthropic"}, "httpx2": {"anthropic"}, "httpx": {"anthropic"}, "jsonschema": {"mcp", "jsonschema"},
           "firebase_admin": {"firebase-admin"}, "functions_framework": {"functions-framework"}, "mcp": {"mcp"}, "pydantic": {"anthropic", "mcp"},
           "google": {"google-cloud-firestore", "google-cloud-storage", "google-cloud-secret-manager"}, "tzdata": {"tzdata"}, "pypdf": {"pypdf"}}
    files = [DEPLOY / "main.py", DEPLOY / "firestore_store.py", DEPLOY / "gcs_object_store.py"] + sorted((ROOT / "alto" / "bass").glob("*.py")) + [ROOT / "alto" / "store" / "firestore.py"]
    unknown = {}
    for f in files:
        for node in ast.walk(ast.parse(f.read_text("utf-8"))):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                ([node.module] if isinstance(node, ast.ImportFrom) and node.module and node.level == 0 else [])
            for m in mods:
                top = m.split(".")[0]
                if top in sys.stdlib_module_names or top in ("alto", "firestore_store", "gcs_object_store", "bass_support"):
                    continue
                if not (pkg.get(top, set()) & have):
                    unknown.setdefault(top, set()).add(f.name)
    assert unknown == {}, f"third-party imports with no package in the bundle requirements: {unknown}"


def test_a_bad_input_always_alerts_and_trips_only_when_three_distinct_accounts_hit_it_in_ten_minutes(tmp_path):
    emails = [f"t{i}@example.com" for i in range(4)]
    # one account repeating: alert every time, never a trip
    st = make_stack(tmp_path / "one", emails=emails)
    st.mock.use(endless(2000)).inject(M.input_400("prompt is too long: 250000 tokens > 200000 maximum", times=50))
    for _ in range(6):
        st.svc.handle(req(build_req(), email=emails[0], xff="203.0.113.1"))
        st.clock.advance(20)
    assert len(st.sink.of("bad_input")) == 6 and not st.kill.is_on()
    # three distinct accounts inside 10 minutes: trip
    st = make_stack(tmp_path / "three", emails=emails)
    st.mock.use(endless(2000)).inject(M.input_400("Could not process image", times=50))
    for i in range(2):
        st.svc.handle(req(build_req(), email=emails[i], xff=f"203.0.113.{i}"))
        st.clock.advance(60)
    assert not st.kill.is_on()
    st.svc.handle(req(build_req(), email=emails[2], xff="203.0.113.9"))
    assert st.kill.state() == {"on": True, "reason": "bad_input_burst"} and len(st.sink.of("bad_input")) == 3
    assert st.sink.of("kill_switch")[0]["reason"] == "bad_input_burst"
    # three distinct accounts spread over more than 10 minutes: no trip
    st = make_stack(tmp_path / "slow", emails=emails)
    st.mock.use(endless(2000)).inject(M.input_400("too many pages", times=50))
    for i in range(3):
        st.svc.handle(req(build_req(), email=emails[i], xff=f"203.0.113.{i}"))
        st.clock.advance(601)
    assert not st.kill.is_on() and len(st.sink.of("bad_input")) == 3


def test_the_runbook_and_deploy_example_name_the_dedicated_bucket_and_the_first_deploy_rules():
    rb = (ROOT / "docs" / "bass-beta-runbook.md").read_text("utf-8")
    assert "<alto-bass-bucket>" in rb and "us-central1" in rb and "uniform" in rb and "public access prevention" in rb.lower()
    assert "anthropic==2.3.0" in rb and "Python 3.12" in rb and "first deploy" in rb.lower() and "live_go" in rb
    assert "<alto-bass-bucket>" in (DEPLOY / "deploy.py").read_text("utf-8")


def test_the_daily_purge_answers_500_when_a_ticket_failed_and_200_when_none_did(cold, monkeypatch):
    main, _ = cold
    gcs = types.ModuleType("google.cloud.storage")
    gcs.Client = lambda: types.SimpleNamespace(bucket=lambda name: object())
    monkeypatch.setitem(sys.modules, "google.cloud.storage", gcs)
    sys.modules["google.cloud"].storage = gcs
    monkeypatch.setenv("BASS_RESEARCH_BUCKET", "demo-research")
    monkeypatch.setattr(main, "_docs_env", lambda: (object(), None))
    monkeypatch.setattr(main, "_clock", lambda: None)
    monkeypatch.setitem(sys.modules, "gcs_object_store", types.SimpleNamespace(Admin=lambda b: b))
    from alto.bass import research_share
    req = types.SimpleNamespace(method="POST")
    for failed, want in ((0, 200), (2, 500)):
        monkeypatch.setattr(research_share, "purge_due", lambda s, a, n, failed=failed: {"tickets": 3, "objects": 9, "failed": failed})
        body, status, _h = main.bass_research_purge_daily(req)
        assert status == want and b"failed" in body and b"uid" not in body
