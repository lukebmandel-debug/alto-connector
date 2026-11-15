"""Hosted Bass on luke-alto for ONE account (alto/bass/hosted.py, alto/cloud/ext_hook.py, alto/build/bass_hosted_ext.py; Board B-1114-b).

SDK-free (public CI): no anthropic, no httpx2, no network (ALTO_NO_NETWORK=1), no key, fakes only (FakeStore, a stub verifier, stand-ins for the
Google and Firebase libraries). Nothing here touches the luke-alto env, Luke's store or his account. The mock-answer end to end, which needs
the SDK, is tests/test_bass_hosted_mock_e2e.py."""
import datetime as dt
import importlib.util
import json
import re
import shutil
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy" / "bass-proxy"
UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
CUT = dt.datetime(2026, 11, 18, 23, 0, tzinfo=UTC)
LUKE, OTHER = "LukeUid0000000000000000001", "OtherUid000000000000000002"
LUKE_EMAIL, OTHER_EMAIL = "luke@example.com", "other@example.com"
ORIGIN = "https://luke-alto.web.app"
NAMED = re.compile(rb"bass|anthropic|claude|studio|credit", re.I)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")
    for k in ("ALTO_EXT_URL", "ALTO_BASS_UI", "ALTO_BASS_BASE", "ALTO_LIVE_ANTHROPIC", "ALTO_FIREBASE_CONFIG"):
        monkeypatch.delenv(k, raising=False)


# ── fakes ────────────────────────────────────────────────────────────────────────────────────────────────────────────
class Verifier:
    """Token -> identity, the way the deployed verifier answers (Google sign-in only is main.py's; tested below)."""
    TOKENS = {"tok-luke": (LUKE, LUKE_EMAIL, True), "tok-other": (OTHER, OTHER_EMAIL, True),
              "tok-luke-unverified": (LUKE, LUKE_EMAIL, False), "tok-other-luke-email": (OTHER, LUKE_EMAIL, True)}

    def __init__(self):
        self.calls = 0

    def verify(self, t):
        from alto.bass.beta_proxy import AuthError
        self.calls += 1
        if t not in self.TOKENS:                                  # forged, expired, another project's: the real verifier raises
            raise AuthError
        uid, email, ver = self.TOKENS[t]
        return {"uid": uid, "email": email, "email_verified": ver}


class StubProxy:
    def __init__(self):
        self.calls = []

    def handle_http(self, method, headers, body):
        self.calls.append(json.loads(body)["action"])
        return 200, {"Content-Type": "application/json; charset=utf-8"}, b'{"ok":true,"from":"proxy"}'


def at(t):
    return lambda: t


def setup(clock=NOW, hosted=(LUKE,), testers=(LUKE_EMAIL,), pins=(LUKE,)):
    from alto.bass.beta_store import FakeStore
    from alto.bass.hosted import HostedGate, hosted_config
    store = FakeStore(auto_terms=True)
    if hosted is not None:
        store.put("bass_beta/hosted", {"uids": list(hosted)})
    if testers is not None:
        store.put("bass_beta/bass_testers", {"emails": list(testers)})
    proxy = StubProxy()
    gate = HostedGate(proxy, store, Verifier(), cfg=hosted_config(), pins=frozenset(pins), clock=at(clock) if isinstance(clock, dt.datetime) else clock)
    return gate, proxy, store


def post(gate, action, token=None, method="POST", body=None):
    h = {"Origin": ORIGIN, "Content-Type": "application/json"}
    if token is not None:
        h["Authorization"] = "Bearer " + token
    return gate.handle_http(method, h, body if body is not None else json.dumps({"action": action, "args": {}}))


# ── 1. the identical empty answer: cross-account, signed out, forged / expired token, share viewers, every missing gate ──────────
ACTIONS = ["ext", "balance", "build", "chat", "edit", "docs", "drive", "research", "estimate", "anything_new"]


def _reference():
    gate, _, _ = setup()
    return post(gate, "ext", "tok-other")


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("case", ["second_uid", "signed_out", "forged", "expired", "empty_bearer", "unverified", "uid_with_lukes_email",
                                  "not_pinned", "not_in_firestore", "no_hosted_doc", "hosted_list_too_long", "no_tester_list",
                                  "tester_list_too_long", "email_not_listed", "pin_too_long", "store_down", "share_viewer"])
def test_everyone_else_gets_one_identical_empty_answer_and_never_reaches_the_proxy(case, action):
    kw, token = {}, "tok-luke"
    if case == "second_uid":
        token = "tok-other"
    elif case == "signed_out":
        token = None
    elif case == "forged":
        token = "eyJhbGciOiJub25lIn0.eyJ1aWQiOiJMdWtlIn0."
    elif case == "expired":
        token = "tok-luke-expired"
    elif case == "empty_bearer":
        token = ""
    elif case == "unverified":
        token = "tok-luke-unverified"
    elif case == "uid_with_lukes_email":
        token = "tok-other-luke-email"
    elif case == "not_pinned":
        kw["pins"] = (OTHER,)
    elif case == "not_in_firestore":
        kw["hosted"] = (OTHER,)
    elif case == "no_hosted_doc":
        kw["hosted"] = None
    elif case == "hosted_list_too_long":
        kw["hosted"] = (LUKE, OTHER)
    elif case == "no_tester_list":
        kw["testers"] = None
    elif case == "tester_list_too_long":
        kw["testers"] = (LUKE_EMAIL, OTHER_EMAIL)
    elif case == "email_not_listed":
        kw["testers"] = (OTHER_EMAIL,)
    elif case == "pin_too_long":
        kw["pins"] = (LUKE, OTHER)
    elif case == "share_viewer":
        token = "tok-other"                                        # a share link's viewer is another account (or signed out, above)
    gate, proxy, store = setup(**kw)
    if case == "store_down":
        store.get = lambda k: (_ for _ in ()).throw(RuntimeError("down"))
    got = post(gate, action, token)
    assert got == _reference(), case
    assert got[0] == 200 and got[2] == b"{}" and proxy.calls == []
    assert not NAMED.search(got[2]) and not any(NAMED.search(str(v).encode()) for v in got[1].values())


@pytest.mark.parametrize("method,body", [("GET", ""), ("PUT", "{}"), ("POST", "not json"), ("POST", "[1]"), ("POST", "x" * 9_100_000)])
def test_bad_requests_get_the_same_empty_answer(method, body):
    gate, proxy, _ = setup()
    assert post(gate, "ext", "tok-luke", method=method, body=body) == _reference() and proxy.calls == []


def test_the_preflight_is_the_same_for_everyone_and_names_nothing():
    gate, _, _ = setup()
    st, h, b = gate.handle_http("OPTIONS", {"Origin": ORIGIN}, b"")
    assert st == 204 and b == b"" and h["Access-Control-Allow-Origin"] == ORIGIN and not any(NAMED.search(str(v).encode()) for v in h.values())
    st2, h2, _ = gate.handle_http("OPTIONS", {"Origin": "https://evil.example"}, b"")
    assert st2 == 204 and "Access-Control-Allow-Origin" not in h2


def test_the_pin_parser_fails_closed():
    from alto.bass.hosted import pinned_uids
    assert pinned_uids(LUKE) == {LUKE} and pinned_uids(f" {LUKE} ,") == {LUKE}
    for bad in ("", None, ",", f"{LUKE},bad/uid", "a b", "x" * 129):
        assert pinned_uids(bad) == frozenset(), bad


# ── 2. the allowed account ─────────────────────────────────────────────────────────────────────────────────────────
def test_the_allowlisted_uid_gets_the_bundle_with_the_beta_button():
    gate, proxy, _ = setup()
    st, h, b = post(gate, "ext", "tok-luke")
    j = json.loads(b)
    assert st == 200 and set(j) == {"x"} and proxy.calls == []
    assert "Bass (beta)" in j["x"] and "window._altoBass=" in j["x"] and "window._ALTO_BASS_BASE=u" in j["x"]
    assert "__ID__" not in j["x"] and "__LABEL__" not in j["x"] and "__GLYPH__" not in j["x"]
    assert h["Cache-Control"] == "no-store" and h["Access-Control-Allow-Origin"] == ORIGIN


def test_the_allowlisted_uid_reaches_the_proxy_for_other_actions():
    gate, proxy, _ = setup()
    st, _, b = post(gate, "balance", "tok-luke")
    assert st == 200 and json.loads(b)["from"] == "proxy" and proxy.calls == ["balance"]


# ── 3. the promo cutoff, in the gate (fail closed) and in the Proxy for the free actions ─────────────────────────────────
@pytest.mark.parametrize("t", [CUT, CUT + dt.timedelta(days=1), dt.datetime(2026, 12, 1, tzinfo=UTC), "naive", "raises", "early"])
@pytest.mark.parametrize("action", ["balance", "stop", "build", "chat", "docs", "drive", "research", "anything_new"])
def test_after_the_cutoff_every_action_answers_promo_ended_and_nothing_reaches_the_proxy(t, action):
    clock = {"naive": lambda: dt.datetime(2026, 11, 15), "raises": lambda: 1 / 0, "early": at(dt.datetime(2026, 1, 1, tzinfo=UTC))}.get(t) \
        if isinstance(t, str) else at(t)
    gate, proxy, _ = setup(clock=clock)
    st, _, b = post(gate, action, "tok-luke")
    j = json.loads(b)
    assert st == 200 and j["code"] == "promo_ended" and j["message"] == "The free Bass credit has ended." and j["ok"] is False
    assert proxy.calls == []
    assert json.loads(post(gate, "ext", "tok-luke")[2])["x"]               # the UI still loads, so it can say so
    assert post(gate, action, "tok-other") == _reference()                    # and everyone else still gets nothing


def test_just_before_the_cutoff_the_proxy_is_reached():
    gate, proxy, _ = setup(clock=CUT - dt.timedelta(seconds=1))
    post(gate, "build", "tok-luke")
    assert proxy.calls == ["build"]


def _real_proxy(tmp_path, clock, live=True):
    from alto.bass import beta_proxy
    from alto.bass.beta_ledger import LIVE_GO_KEY, confirm_key
    from alto.bass.beta_store import FakeStore
    from alto.bass.hosted import hosted_config
    from alto.bass.tools import ToolBox
    from alto.store.local import LocalStore

    class Sec(beta_proxy.SecretReader):
        reads = []

        def read(self, name):
            Sec.reads.append(name)
            return "sk-" + "ant-canary-NEVER-LOGGED"

    store = FakeStore(auto_terms=True)
    cfg = hosted_config()
    store.put("bass_beta/bass_testers", {"emails": [LUKE_EMAIL]})
    store.put(confirm_key(cfg.period_id(clock())), {"confirmed": True})
    if live:
        store.put(LIVE_GO_KEY, {"on": True})
    p = beta_proxy.Proxy(cfg, store, Verifier(), Sec(), ToolBox(LocalStore(tmp_path / "s")), clock=clock)
    return p, store, Sec


class Upstream:
    """Stands in for the Anthropic client and its constructor: any request or client made counts."""

    def __init__(self, monkeypatch, proxy):
        from alto.bass import beta_proxy
        self.made = self.sent = 0
        outer = self

        class _M:
            def __getattr__(self, name):
                outer.sent += 1
                raise AssertionError("upstream reached: " + name)

        class _C:
            messages = _M()

        def make(*a, **k):
            outer.made += 1
            return _C()
        monkeypatch.setattr(beta_proxy, "make_client", make)
        monkeypatch.setattr(proxy, "_client", None)


@pytest.mark.parametrize("action,args", [("docs", {"op": "list"}), ("docs", {"op": "add", "files": []}), ("drive", {"op": "config"}),
                                         ("drive", {"op": "disconnect"}), ("research", {"op": "status"}), ("balance", {}), ("stop", {})])
@pytest.mark.parametrize("t", [CUT, CUT + dt.timedelta(days=2)])
def test_after_the_cutoff_the_proxys_exempt_actions_never_reach_the_anthropic_client(tmp_path, monkeypatch, action, args, t):
    """The Proxy exempts FREE, docs, drive and research from its own cutoff check because they send nothing upstream. Enforced here, live_go
    ON, past the cutoff, straight into the Proxy (no gate): a stub client sees zero clients made and zero requests, and the key is never read."""
    p, _, Sec = _real_proxy(tmp_path, at(t))
    up = Upstream(monkeypatch, p)
    st, _, b = p.handle_http("POST", {"Authorization": "Bearer tok-luke"}, json.dumps({"action": action, "args": args}))
    assert st == 200 and isinstance(json.loads(b), dict)
    assert up.made == 0 and up.sent == 0 and Sec.reads == []


@pytest.mark.parametrize("action", ["build", "chat", "edit", "propose", "estimate", "convert", "make_study_plan", "anything_new"])
def test_after_the_cutoff_the_proxy_refuses_every_spending_action(tmp_path, monkeypatch, action):
    p, _, Sec = _real_proxy(tmp_path, at(CUT))
    up = Upstream(monkeypatch, p)
    st, _, b = p.handle_http("POST", {"Authorization": "Bearer tok-luke"}, json.dumps({"action": action, "args": {}}))
    assert json.loads(b)["code"] == "promo_ended" and up.made == up.sent == 0 and Sec.reads == []


# ── 4. money: the caps sized to the $5 Console limit ─────────────────────────────────────────────────────────────────────
def test_the_hosted_config_is_clean_with_one_tester_and_fits_the_console_limit():
    from alto.bass.hosted import hosted_config, hosted_problems
    cfg = hosted_config()
    assert cfg.testers == 1 and cfg.problems() == [] and hosted_problems(cfg, NOW) == []
    assert cfg.pool_credits == 500 and cfg.server_ceiling_credits == 400 and cfg.per_action_cap_credits == 100
    assert cfg.tester_period_credits == 400 and cfg.tester_daily_credits <= 400 and cfg.global_daily_credits <= 400
    assert cfg.server_ceiling_credits + cfg.per_action_cap_credits <= 500           # a whole missed turn still stays under $5
    assert set(cfg.allowed_origins) == {"https://luke-alto.web.app", "https://luke-alto.firebaseapp.com"}


def test_no_new_credit_period_opens_between_any_deploy_day_and_the_cutoff():
    from alto.bass.hosted import hosted_config, hosted_problems
    cfg = hosted_config()
    t = dt.datetime(2026, 11, 1, 5, 0, tzinfo=UTC)
    while t < CUT:
        assert cfg.period_id(t) == "2026-11-01" == cfg.period_id(CUT) and hosted_problems(cfg, t) == [], t
        t += dt.timedelta(hours=6)
    assert hosted_problems(hosted_config(start_day=17), NOW)                       # the beta's own 17th would reset the ceiling


@pytest.mark.parametrize("kw", [dict(testers=2), dict(pool_credits=600), dict(server_ceiling_credits=450), dict(per_action_cap_credits=150),
                                dict(tester_daily_credits=450), dict(global_daily_credits=450)])
def test_hosted_problems_catch_every_cap_above_the_limit(kw):
    from alto.bass.hosted import hosted_config, hosted_problems
    assert hosted_problems(hosted_config(**kw), NOW)


def test_the_ledger_never_books_past_the_ceiling(tmp_path):
    from alto.bass.beta_ledger import BetaLedger, confirm_key
    from alto.bass.beta_store import FakeStore
    from alto.bass.errors import BassError
    from alto.bass.hosted import hosted_config
    cfg = hosted_config()
    store = FakeStore(auto_terms=True)
    store.put(confirm_key(cfg.period_id(NOW)), {"confirmed": True})
    led = BetaLedger(store, cfg, at(NOW), sleep=lambda s: None)
    booked, refused = 0, None
    for i in range(10):
        try:
            led.hold(LUKE, f"h{i}", cfg.per_action_cap_mc, f"a{i}")
        except BassError as e:
            refused = e.code
            break
        led.settle(LUKE, f"h{i}", cfg.per_action_cap_mc)
        booked += cfg.per_action_cap_mc
    assert booked == 400_000 and refused in ("beta_credits_used", "beta_tester_daily", "beta_daily_full")


def test_the_proxy_built_on_the_hosted_config_caps_each_action_at_one_dollar(tmp_path):
    p, _, _ = _real_proxy(tmp_path, at(NOW), live=False)
    assert p.cfg.per_action_cap_mc == 100_000 and p.cfg.ceiling_mc == 400_000


# ── 5. the key ───────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_key_is_never_read_for_anyone_else_and_never_logged(tmp_path, monkeypatch, caplog, capsys):
    import logging
    from alto.bass.hosted import HostedGate, hosted_config
    caplog.set_level(logging.DEBUG)
    p, store, Sec = _real_proxy(tmp_path, at(NOW))
    store.put("bass_beta/hosted", {"uids": [LUKE]})
    up = Upstream(monkeypatch, p)
    gate = HostedGate(p, store, Verifier(), cfg=hosted_config(), pins=frozenset({LUKE}), clock=at(NOW))
    outs = [post(gate, a, tok) for a in ACTIONS for tok in ("tok-other", None, "forged")]
    assert all(o == outs[0] for o in outs) and Sec.reads == [] and up.made == 0
    outs.append(post(gate, "balance", "tok-luke"))
    text = caplog.text + "".join(capsys.readouterr()) + "".join(o[2].decode() + json.dumps(o[1]) for o in outs)
    assert "sk-ant" not in text and "canary" not in text


# ── 6. the hook and the pages: every visitor gets the default build plus a hook that names nothing ───────────────────────────────
URL = "https://us-central1-demo-project.cloudfunctions.net/altoext"


def test_without_the_env_alto_cloud_js_and_the_csp_are_unchanged(monkeypatch):
    from alto import publish_static as ps
    from alto.cloud import SOURCE, emit_cloud_js, ext_hook
    a = emit_cloud_js({})
    assert ext_hook.url() == "" and ext_hook.origin() == "" and "alto-ext" not in a and "__altoExtUrl" not in a
    assert ps._bass_src() == "" and "cloudfunctions" not in ps._csp("'none'")
    assert a.count("\n") >= SOURCE.read_text("utf-8").count("\n") - 5


def test_with_the_env_the_hook_is_appended_names_nothing_and_asks_only_on_home(monkeypatch):
    from alto import publish_static as ps
    from alto.cloud import emit_cloud_js, ext_hook
    base = emit_cloud_js({})
    monkeypatch.setenv("ALTO_EXT_URL", URL)
    withh = emit_cloud_js({})
    assert withh.startswith(base) and withh[len(base):] == ext_hook.hook_js(URL)
    hook = ext_hook.hook_js(URL).encode()
    assert not NAMED.search(hook) and b"<svg" not in hook and b"_altoBass" not in hook
    assert "return p==='/'||p==='/index.html'; }" in hook.decode()                # never /s/ (share links), /pv/ (private-web) or /connect/
    assert "if(src||!u||!u.getIdToken" in hook.decode()                                              # signed out: nothing is sent
    csp = ps._csp("'none'")
    assert ps._bass_src() == " https://us-central1-demo-project.cloudfunctions.net" and "connect-src" in csp
    assert csp.count("cloudfunctions.net") == 1 and "altoext" not in csp


@pytest.mark.parametrize("bad", ["http://us-central1-p.cloudfunctions.net/altoext", "https://us-central1-p.cloudfunctions.net/bass-proxy",
                                 "https://bass-proxy-abc-uc.a.run.app", "https://evil.example/altoext", "https://us-central1-p.cloudfunctions.net/x?y=1",
                                 "https://us-central1-p.cloudfunctions.net/Claude", "javascript:alert(1)", " "])
def test_a_url_that_names_bass_or_is_not_a_function_adds_nothing(monkeypatch, bad):
    from alto import publish_static as ps
    from alto.cloud import emit_cloud_js, ext_hook
    monkeypatch.setenv("ALTO_EXT_URL", bad)
    assert ext_hook.url() == "" and ps._bass_src() == "" and "__altoExtUrl" not in emit_cloud_js({})


def test_pages_and_hosted_assets_are_byte_identical_with_the_hook_on(monkeypatch):
    from alto.build import palace_assets
    from alto.build.builder import build_timeline, load_brief
    from alto.build.pages import build_home
    from alto.hosted import hosted_home

    def build():
        b, n, c = load_brief(json.loads((ROOT / "samples" / "outline_brief.json").read_text("utf-8")))
        return (build_timeline(b, n, c)[0], hosted_home(build_home([{"name": "Law", "pid": "p", "courses": []}])),
                sorted(str(a[0]) for a in palace_assets.assets()))
    off = build()
    monkeypatch.setenv("ALTO_EXT_URL", URL)
    on = build()
    assert on == off
    for page in on[:2]:
        assert "_altoBass" not in page and "alto-bass" not in page and "Bass (beta)" not in page
    assert not any(a.startswith("bass") or "/bass/" in a for a in on[2])                              # /bass/ is never published


# ── 7. the Firebase CLI entry and the bundle ───────────────────────────────────────────────────────────────────────────
def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def firebase_fakes(monkeypatch):
    seen = {}
    ff = types.ModuleType("firebase_functions")
    https_fn = types.ModuleType("firebase_functions.https_fn")
    opts = types.ModuleType("firebase_functions.options")

    class MemoryOption:
        MB_512 = "512MiB"
    opts.MemoryOption = MemoryOption

    def on_request(**kw):
        seen.update(kw)
        return lambda f: f
    https_fn.on_request = on_request

    class Response:
        def __init__(self, body, status, headers):
            self.body, self.status, self.headers = body, status, headers
    https_fn.Response = Response
    ff.https_fn, ff.options = https_fn, opts
    for k, v in {"firebase_functions": ff, "firebase_functions.https_fn": https_fn, "firebase_functions.options": opts}.items():
        monkeypatch.setitem(sys.modules, k, v)
    monkeypatch.syspath_prepend(str(DEPLOY))
    return seen


def test_the_firebase_entry_builds_the_gate_and_serves_through_it(firebase_fakes, monkeypatch, tmp_path):
    from alto.bass.beta_store import FakeStore
    store = FakeStore(auto_terms=True)
    store.put("bass_beta/hosted", {"uids": [LUKE]})
    store.put("bass_beta/bass_testers", {"emails": [LUKE_EMAIL]})
    pm = _load("proxy_main", DEPLOY / "main.py")
    for k, v in {"ALTO_EXT_PROJECT": "demo-project", "ALTO_EXT_UIDS": LUKE}.items():
        monkeypatch.setenv(k, v)
    import firestore_store
    monkeypatch.setattr(firestore_store, "FirestoreStore", lambda db: store)
    from alto.bass import beta_proxy
    real = pm.build_hosted
    monkeypatch.setattr(pm, "build_hosted", lambda: real(adapters=lambda project: (Verifier(), beta_proxy.SecretReader(), object())))
    fb = _load("altoext_main", DEPLOY / "fb_main.py")
    assert firebase_fakes["max_instances"] == 1 and firebase_fakes["concurrency"] == 4 and firebase_fakes["invoker"] == "public" and firebase_fakes["timeout_sec"] == 300

    class Req:
        def __init__(self, tok):
            self.method, self.headers = "POST", {"Authorization": "Bearer " + tok, "Origin": ORIGIN}

        def get_data(self):
            return b'{"action":"ext","args":{}}'
    assert "Bass (beta)" in json.loads(fb.altoext(Req("tok-luke")).body)["x"]
    r = fb.altoext(Req("tok-other"))
    assert r.status == 200 and r.body == b"{}"


@pytest.mark.parametrize("env,msg", [({}, "missing"), ({"ALTO_EXT_UIDS": f"{LUKE},{OTHER}"}, "exactly one"), ({"ALTO_EXT_UIDS": "bad/uid"}, "exactly one")])
def test_the_hosted_cold_start_refuses_a_bad_environment(monkeypatch, env, msg):
    monkeypatch.syspath_prepend(str(DEPLOY))
    pm = _load("proxy_main_cold", DEPLOY / "main.py")
    for k in ("ALTO_EXT_PROJECT", "ALTO_EXT_UIDS"):
        monkeypatch.delenv(k, raising=False)
    if env:
        monkeypatch.setenv("ALTO_EXT_PROJECT", "p")
        for k, v in env.items():
            monkeypatch.setenv(k, v)
    with pytest.raises(RuntimeError) as e:
        pm.build_hosted(adapters=lambda p: (_ for _ in ()).throw(AssertionError("adapters before the checks")))
    assert msg in str(e.value)


def test_the_deployed_verifier_takes_google_sign_in_only(monkeypatch):
    monkeypatch.syspath_prepend(str(DEPLOY))
    claims = {}
    fa = types.ModuleType("firebase_admin")
    fa._apps = {"[DEFAULT]": object()}
    fa_auth = types.ModuleType("firebase_admin.auth")
    fa_auth.verify_id_token = lambda t, check_revoked=False: dict(claims)
    fa.auth = fa_auth
    gc = types.ModuleType("google.cloud")
    gfs, gsm = types.ModuleType("google.cloud.firestore"), types.ModuleType("google.cloud.secretmanager")
    gfs.Client, gsm.SecretManagerServiceClient = (lambda: object()), (lambda: object())
    gc.firestore, gc.secretmanager = gfs, gsm
    for k, v in {"firebase_admin": fa, "firebase_admin.auth": fa_auth, "google": sys.modules.get("google") or types.ModuleType("google"),
                 "google.cloud": gc, "google.cloud.firestore": gfs, "google.cloud.secretmanager": gsm}.items():
        monkeypatch.setitem(sys.modules, k, v)
    pm = _load("proxy_main_ver", DEPLOY / "main.py")
    from alto.bass.beta_proxy import AuthError
    v, _, _ = pm._adapters("p")
    for prov in ("password", "anonymous", "phone", "custom", None):
        claims.clear()
        claims.update({"uid": LUKE, "email": LUKE_EMAIL, "email_verified": True, "firebase": {"sign_in_provider": prov}})
        with pytest.raises(AuthError):
            v.verify("t")
    claims["firebase"] = {"sign_in_provider": "google.com"}
    assert v.verify("t")["uid"] == LUKE


def test_the_firebase_bundle_has_the_function_and_no_secret_or_env(tmp_path):
    bb = _load("bb_hosted", DEPLOY / "build_bundle.py")
    out = bb.firebase_bundle(tmp_path / "b", "altoext@demo-project.iam.gserviceaccount.com")
    fn = out / "functions"
    assert json.loads((out / "firebase.json").read_text())["functions"][0]["source"] == "functions"
    assert (fn / "proxy_main.py").read_text() == (DEPLOY / "main.py").read_text() and (fn / "alto" / "bass" / "hosted.py").is_file()
    assert "SERVICE_ACCOUNT = 'altoext@demo-project.iam.gserviceaccount.com'" in (fn / "main.py").read_text()
    reqs = (fn / "requirements.txt").read_text()
    assert reqs.startswith("firebase-functions==") and "functions-framework" not in reqs and "anthropic==" in reqs
    assert not (fn / ".env").exists() and not list(out.rglob("*.pyc"))
    with pytest.raises(SystemExit):
        bb.firebase_bundle(tmp_path / "c", "not an account")


def test_the_hosted_deploy_plan_only_prints_and_uses_the_firebase_cli(capsys):
    d = _load("deploy_hosted", DEPLOY / "deploy.py")
    assert d.main(["--hosted", "--project", "demo-project", "--bucket", "b1"]) == 2              # no service account: refused
    capsys.readouterr()
    assert d.main(["--hosted", "--project", "demo-project", "--bucket", "b1", "--service-account", "altoext@demo-project.iam.gserviceaccount.com"]) == 0
    out = capsys.readouterr().out
    assert "--service-account altoext@demo-project.iam.gserviceaccount.com" in out and "not <number>-compute@" in out
    assert "DRY RUN" in out and "firebase deploy --only functions:altoext:altoext --project demo-project" in out
    assert "gcloud" not in out.replace("no gcloud", "") and "ALTO_EXT_UIDS=<LUKE_UID>" in out and "sk-ant" not in out
    assert "bass_beta/hosted" in out and "bass_beta_periods/2026-11-01" in out
    assert d.main(["--hosted", "--project", "p"]) == 2


# ── 8. erase and rules ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_an_account_erase_takes_the_uid_off_the_hosted_list():
    from alto.store import erase

    class Snap:
        def __init__(self, ref):
            self.ref, self.exists = ref, ref.data is not None

        def to_dict(self):
            return dict(self.ref.data or {})

    class Ref:
        def __init__(self, data):
            self.data = data

        def get(self):
            return Snap(self)

        def update(self, d):
            self.data.update(d)

        def delete(self):
            self.data = None

    class Coll:
        def __init__(self, db, name):
            self.db, self.name = db, name

        def document(self, doc):
            return self.db.refs.setdefault((self.name, doc), Ref(None))

        def stream(self):
            return iter(())

        def where(self, *a):
            return self

    class DB:
        def __init__(self):
            self.refs = {("bass_beta", "hosted"): Ref({"uids": [LUKE, "x"]})}

        def collection(self, name):
            return Coll(self, name)
    db = DB()
    erase.erase_bass_records(db, LUKE)
    assert db.refs[("bass_beta", "hosted")].data == {"uids": ["x"]}
    assert "hosted" in erase.BASS_COLLECTIONS["bass_beta"]


def test_firestore_rules_keep_every_hosted_doc_server_only():
    for path in ("firestore.rules", "alto/firestore.rules"):
        src = (ROOT / path).read_text("utf-8")
        assert "match /bass_beta/{document=**} {\n      allow read, write: if false;\n    }" in src
        for coll in ("bass_beta_periods", "bass_credits", "bass_beta_days", "bass_beta_period_counters", "bass_beta_meta"):
            assert f"match /{coll}" not in src                                                 # no rule = default deny for clients
    mjs = (ROOT / "tests" / "security" / "firestore_rules.test.mjs").read_text("utf-8")
    for doc in ("bass_beta/hosted", "bass_beta/live_go", "bass_beta_periods/2026-11-01"):
        assert f"'{doc}'" in mjs


def test_the_upstream_stub_bites_before_the_cutoff(tmp_path, monkeypatch):
    """Control for the two tests above: the same stub DOES see the client when a spending action runs before the cutoff with live_go on."""
    p, _, _ = _real_proxy(tmp_path, at(NOW))
    up = Upstream(monkeypatch, p)
    p.handle_http("POST", {"Authorization": "Bearer tok-luke"}, json.dumps({"action": "estimate", "args": {"materials": [{"name": "n.txt", "kind": "text", "text": "Negligence: duty, breach, causation, harm. " * 20}]}}))
    assert up.made + up.sent >= 1



# ── 9. the pin (Board B-1114-001500): the hook runs ONLY the one pinned bundle; script-src is unchanged ─────────────────────────────
def test_the_committed_pin_is_the_served_bundle():
    """Drift guard: any change to the bundle (bass_ui, its JS/CSS, the button) fails here until ext_pin.txt is re-pinned, and so re-stamped."""
    from alto.build import bass_hosted_ext
    from alto.cloud import ext_hook
    integrity, size = ext_hook.pin()
    assert integrity and size and bass_hosted_ext.pin() == f"{integrity} {size}"
    gate, _, _ = setup()
    served = json.loads(post(gate, "ext", "tok-luke")[2])["x"]
    assert bass_hosted_ext.pin(served) == f"{integrity} {size}"
    assert not NAMED.search((ROOT / "alto" / "cloud" / "ext_pin.txt").read_bytes())


def test_a_drifted_bundle_stops_the_gate_from_starting(monkeypatch):
    from alto.build import bass_hosted_ext
    real = bass_hosted_ext.bundle
    monkeypatch.setattr(bass_hosted_ext, "bundle", lambda: real() + ";")
    with pytest.raises(RuntimeError, match="re-pin"):
        setup()


def test_a_missing_or_malformed_pin_means_no_hook_and_no_csp_change(monkeypatch, tmp_path):
    from alto import publish_static as ps
    from alto.cloud import emit_cloud_js, ext_hook
    monkeypatch.setenv("ALTO_EXT_URL", URL)
    for text in (None, "", "sha384-short 10", "sha256-" + "A" * 64 + " 10"):
        f = tmp_path / "pin.txt"
        if text is None:
            f.unlink(missing_ok=True)
        else:
            f.write_text(text)
        monkeypatch.setattr(ext_hook, "PIN_FILE", f)
        assert ext_hook.pin() == ("", 0) and "__altoExtUrl" not in emit_cloud_js({}) and ps._bass_src() == ""


def _script_src(csp):
    return [p for p in csp.split("; ") if p.startswith("script-src")][0]


def test_script_src_is_byte_identical_with_the_hook_on_and_gains_nothing(monkeypatch):
    """The Board asked that script-src gain no 'unsafe-inline'. It gains NOTHING: not 'unsafe-inline', not a hash, not blob:, not the function.
    (The site's script-src has carried 'unsafe-inline' since before Bass, for every page's own inline scripts. A hash source cannot be added
    for the bundle: under CSP Level 2+ any hash or nonce in script-src switches 'unsafe-inline' OFF for every inline script, which would stop
    every Alto page. That is reported to the Board; the pin is enforced by the hook instead.)"""
    from alto import publish_static as ps
    off = _script_src(ps._csp("'none'"))
    monkeypatch.setenv("ALTO_EXT_URL", URL)
    on = _script_src(ps._csp("'none'"))
    assert on == off and "cloudfunctions" not in on and "blob:" not in on and "sha384-" not in on
    assert on.count("'unsafe-inline'") == off.count("'unsafe-inline'")


# A small DOM and fetch in node run the REAL hook text: what it runs, for each answer the server could send.
NODE = next((p for p in (shutil.which("node"), str(Path.home() / ".local/node/bin/node"), "/Users/lbmandel/.local/node/bin/node") if p and Path(p).is_file()), None)
_HARNESS = r"""
const [hook, body, path, uid, ctype] = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const ran = [], asked = [];
const el = () => ({ set textContent(v) { this._t = v; }, get textContent() { return this._t; } });
const doc = { head: { appendChild(s) { ran.push(s._t); } }, body: {}, getElementById: () => null, createElement: el };
const listeners = {};
const win = { AltoCloud: uid ? { user: { uid, getIdToken: async () => 'tok' } } : {}, crypto: globalThis.crypto, TextEncoder,
  addEventListener: (k, f) => { listeners[k] = f; } };
const fetch = async (u, o) => { asked.push(u); return { ok: true, headers: { get: () => String(Buffer.byteLength(body)) }, text: async () => body }; };
new Function('window', 'document', 'location', 'fetch', 'addEventListener', 'crypto', 'btoa', 'TextEncoder', hook)(
  win, doc, { pathname: path }, fetch, win.addEventListener, globalThis.crypto, btoa, TextEncoder);
setTimeout(() => { process.stdout.write(JSON.stringify({ ran, asked: asked.length, w: win.__altoExtUrl || null })); }, 300);
"""


def _run_hook(body, path="/", uid="u1"):
    import subprocess
    from alto.cloud import ext_hook
    r = subprocess.run([NODE, "-e", _HARNESS], input=json.dumps([ext_hook.hook_js(URL), body, path, uid, "json"]), capture_output=True,
                       text=True, timeout=30)
    assert r.returncode == 0, r.stderr[-500:]
    return json.loads(r.stdout)


@pytest.mark.skipif(NODE is None, reason="node is not installed (the WebKit check covers the same cases)")
def test_the_hook_runs_the_pinned_bundle_and_nothing_else():
    from alto.build import bass_hosted_ext
    good = bass_hosted_ext.bundle()
    ok = _run_hook(json.dumps({"x": good}))
    assert ok["ran"] == [good] and ok["w"] == URL
    i = len(good) // 2
    flipped = good[:i] + ("A" if good[i] != "A" else "B") + good[i + 1:]
    cases = {
        "one byte changed": json.dumps({"x": flipped}),
        "a different script": json.dumps({"x": "window.__pwned=1"}),
        "same size, other bytes": json.dumps({"x": "x" * len(good.encode())}),
        "one byte added": json.dumps({"x": good + " "}),
        "one byte missing": json.dumps({"x": good[:-1]}),
        "oversized body": json.dumps({"x": good, "pad": "x" * (3 * len(good))}),
        "oversized script": json.dumps({"x": good * 2}),
        "not json": good,
        "x not a string": json.dumps({"x": [good]}),
        "empty answer": "{}",
    }
    for name, body in cases.items():
        out = _run_hook(body)
        assert out["ran"] == [] and out["w"] is None, name


@pytest.mark.skipif(NODE is None, reason="node is not installed (the WebKit check covers the same cases)")
@pytest.mark.parametrize("uid", ["u1", ""])
@pytest.mark.parametrize("path", ["/s/abc/", "/s/", "/pv/k1/", "/pv/", "/connect/", "/reports/", "/drive-picker/", "/index.htm",
                                  "/preview.html", "/artifacts/preview.html", "srcdoc", "/t_0.html", "/t/x/", "/p/x/", "/new/"])
def test_share_preview_connect_and_private_web_pages_send_zero_requests_signed_in_or_not(path, uid):
    """STAMP-hosted F1 / Board (c): only the homepage ("/" and "/index.html") ever asks."""
    from alto.build import bass_hosted_ext
    out = _run_hook(json.dumps({"x": bass_hosted_ext.bundle()}), path=path, uid=uid)
    assert out["asked"] == 0 and out["ran"] == []


@pytest.mark.skipif(NODE is None, reason="node is not installed (the WebKit check covers the same cases)")
@pytest.mark.parametrize("path", ["/", "/index.html"])
def test_only_the_homepage_asks(path):
    from alto.build import bass_hosted_ext
    assert _run_hook(json.dumps({"x": bass_hosted_ext.bundle()}), path=path)["asked"] == 1


@pytest.mark.skipif(NODE is None, reason="node is not installed (the WebKit check covers the same cases)")
def test_signed_out_never_calls_the_hook():
    from alto.build import bass_hosted_ext
    out = _run_hook(json.dumps({"x": bass_hosted_ext.bundle()}), uid="")
    assert out["asked"] == 0 and out["ran"] == []


# ── 10. (a) identical answers; (b) the token is verified on the server and the body never names the account ─────────────────────
def test_a_non_allowlisted_uid_a_bad_token_and_no_token_get_identical_status_headers_and_body():
    gate, proxy, _ = setup()
    answers = [post(gate, a, tok) for a in ("ext", "balance", "build") for tok in ("tok-other", "forged.jwt.sig", "", None)]
    assert all(a == answers[0] for a in answers) and answers[0][0] == 200 and answers[0][2] == b"{}" and proxy.calls == []
    assert set(answers[0][1]) == {"Content-Type", "Cache-Control", "X-Content-Type-Options", "Access-Control-Allow-Origin", "Vary"}


@pytest.mark.parametrize("body", [{"action": "ext", "uid": LUKE}, {"action": "ext", "args": {"uid": LUKE, "email": LUKE_EMAIL}},
                                  {"action": "build", "uid": LUKE, "email": LUKE_EMAIL, "email_verified": True}])
def test_a_uid_in_the_request_body_is_never_trusted(body):
    gate, proxy, _ = setup()
    assert post(gate, None, "tok-other", body=json.dumps(body)) == _reference() and proxy.calls == []
    assert post(gate, None, None, body=json.dumps(body)) == _reference()


def _strict_verifier(monkeypatch, claims, init):
    monkeypatch.syspath_prepend(str(DEPLOY))
    fa = types.ModuleType("firebase_admin")
    fa._apps = {}

    def initialize_app(*a, **k):
        init.append(k)
        fa._apps["[DEFAULT]"] = object()
    fa.initialize_app = initialize_app
    fa_auth = types.ModuleType("firebase_admin.auth")

    def verify_id_token(t, check_revoked=False):
        if t != "good":                      # the library raises for a bad signature, a wrong audience or an expired token
            raise ValueError("invalid token")
        return dict(claims)
    fa_auth.verify_id_token = verify_id_token
    fa.auth = fa_auth
    gc = types.ModuleType("google.cloud")
    gfs, gsm = types.ModuleType("google.cloud.firestore"), types.ModuleType("google.cloud.secretmanager")
    gfs.Client, gsm.SecretManagerServiceClient = (lambda: object()), (lambda: object())
    gc.firestore, gc.secretmanager = gfs, gsm
    for k, v in {"firebase_admin": fa, "firebase_admin.auth": fa_auth, "google": sys.modules.get("google") or types.ModuleType("google"),
                 "google.cloud": gc, "google.cloud.firestore": gfs, "google.cloud.secretmanager": gsm}.items():
        monkeypatch.setitem(sys.modules, k, v)
    pm = _load("proxy_main_strict", DEPLOY / "main.py")
    return pm._adapters("demo-project", strict=True)[0]


def test_the_hosted_verifier_checks_signature_audience_issuer_and_expiry(monkeypatch):
    import time as _t
    from alto.bass.beta_proxy import AuthError
    good = {"uid": LUKE, "email": LUKE_EMAIL, "email_verified": True, "aud": "demo-project",
            "iss": "https://securetoken.google.com/demo-project", "exp": int(_t.time()) + 600, "firebase": {"sign_in_provider": "google.com"}}
    claims, init = dict(good), []
    v = _strict_verifier(monkeypatch, claims, init)
    assert init == [{"options": {"projectId": "demo-project"}}]               # the library checks the audience against THIS project
    assert v.verify("good")["uid"] == LUKE
    with pytest.raises(AuthError):
        v.verify("bad-signature")
    for k, bad in (("aud", "other-project"), ("aud", None), ("iss", "https://securetoken.google.com/other"), ("iss", "https://evil"),
                   ("exp", int(_t.time()) - 1), ("exp", None), ("exp", True), ("exp", "9999999999")):
        claims.clear()
        claims.update(good)
        claims[k] = bad
        with pytest.raises(AuthError):
            v.verify("good")


def test_build_bundle_refuses_a_folder_whose_bundle_and_pin_drift(tmp_path):
    bb = _load("bb_hosted_drift", DEPLOY / "build_bundle.py")
    out = bb.firebase_bundle(tmp_path / "b", "altoext@demo-project.iam.gserviceaccount.com")
    fn = out / "functions"
    assert bb.check_pin(fn) == (ROOT / "alto" / "cloud" / "ext_pin.txt").read_text().strip()
    p = fn / "alto" / "build" / "bass_hosted_ext.py"
    p.write_text(p.read_text().replace('LABEL = "Bass (beta)"', 'LABEL = "Bass (beta) "'))
    with pytest.raises(SystemExit, match="does not match"):
        bb.check_pin(fn)



@pytest.mark.parametrize("sa", [None, "", "not an account", "123-compute@developer.gserviceaccount.com"])
def test_the_firebase_bundle_refuses_without_its_own_service_account(tmp_path, sa):
    """STAMP-hosted F2: never the default compute account (Editor)."""
    bb = _load("bb_hosted_sa", DEPLOY / "build_bundle.py")
    with pytest.raises(SystemExit, match="service"):
        bb.firebase_bundle(tmp_path / "x", sa)
    assert not (tmp_path / "x" / "functions" / "main.py").exists()
    sys.argv = ["build_bundle", "--firebase", str(tmp_path / "y")]
    with pytest.raises(SystemExit):
        bb.main()


def test_a_revoked_token_or_disabled_account_gets_the_empty_answer():
    """STAMP-hosted F4: the hosted verifier's confirm() (check_revoked=True) runs after the pin and the lists; a refusal is the same {}."""
    from alto.bass.beta_proxy import AuthError

    class Revoking(Verifier):
        confirms = 0

        def confirm(self, t):
            Revoking.confirms += 1
            raise AuthError
    gate, proxy, _ = setup()
    gate.verifier = Revoking()
    assert post(gate, "ext", "tok-luke") == _reference() and proxy.calls == []
    assert post(gate, "ext", "tok-other") == _reference() and Revoking.confirms == 1          # a non-pinned uid never costs an Auth call


def test_the_hosted_verifier_confirm_checks_revocation(monkeypatch):
    import time as _t
    from alto.bass.beta_proxy import AuthError
    claims = {"uid": LUKE, "email": LUKE_EMAIL, "email_verified": True, "aud": "demo-project", "iss": "https://securetoken.google.com/demo-project",
              "exp": int(_t.time()) + 600, "firebase": {"sign_in_provider": "google.com"}}
    v = _strict_verifier(monkeypatch, claims, [])
    fa_auth = sys.modules["firebase_admin.auth"]
    seen = []

    def verify(t, check_revoked=False):
        seen.append(check_revoked)
        if check_revoked:
            raise ValueError("revoked")
        return dict(claims)
    monkeypatch.setattr(fa_auth, "verify_id_token", verify)
    assert v.verify("good")["uid"] == LUKE
    with pytest.raises(AuthError):
        v.confirm("good")
    assert seen == [False, True]


# ── 11. the bundle never turns a server value into markup (STAMP-hosted row 3; Board B-1114-043000) ──────────────────────────────
_SINK = re.compile(r"\.(innerHTML|outerHTML)\s*(\+?=)(?!=)|\.insertAdjacentHTML\s*\(|\bdocument\s*\.\s*(write|writeln)\s*\(|\bD\s*\.\s*(write|writeln)\s*\(|\[\s*['\"](innerHTML|outerHTML)['\"]\s*\]")
_LITERAL_RHS = re.compile(r"""\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')\s*[;,})]""")


def _sinks(js):
    out = []
    for m in _SINK.finditer(js):
        if m.group(1) and m.group(2) == "=" and _LITERAL_RHS.match(js, m.end()):
            continue                                                      # x.innerHTML = "<one literal constant>";
        out.append(js[max(0, m.start() - 60):m.end() + 60])
    return out


def test_lint_the_bundle_sets_no_markup_from_anything_but_a_literal():
    from alto.build import bass_hosted_ext
    js = bass_hosted_ext.bundle()
    assert _sinks(js) == []
    assert "new DOMParser().parseFromString(" in js and "function clean(n)" in js and "put(root,inner)" in js
    for bad in ("eval(", "new Function", "setTimeout('", 'setTimeout("', "srcdoc", "insertAdjacentHTML"):
        assert bad not in js, bad


@pytest.mark.parametrize("snippet,caught", [("el.innerHTML=x;", True), ("el.innerHTML = a+'<b>';", True), ("el.outerHTML=meter();", True),
                                            ("el.innerHTML+='<i>';", True), ("el['innerHTML']=v;", True), ("el.insertAdjacentHTML('beforeend','<b>');", True),
                                            ("document.write(x);", True), ("D.write('<p>');", True), ("el.innerHTML='<input type=\"text\">';", False),
                                            ("el.innerHTML=\"<svg></svg><span>Bass (beta)</span>\";", False), ("var h=k.outerHTML;", False),
                                            ("if(a.innerHTML==b)x();", False)])
def test_the_lint_bites(snippet, caught):
    assert bool(_sinks(snippet)) is caught


def test_fail_hide_make_it_with_bass_is_not_exposed():
    from alto.build import bass_hosted_ext
    js = bass_hosted_ext.bundle()
    assert "Make it with Bass" not in js and "_altoConvertRoutes" not in js


# ── 9. no zone database (a Windows Python without tzdata): fail closed, no crash ─────────────────────────────────────────
def test_a_missing_zone_database_fails_closed_without_a_crash(monkeypatch):
    import zoneinfo

    from alto.bass.hosted import hosted_config, hosted_problems

    def _gone(key, *a, **k):
        raise zoneinfo.ZoneInfoNotFoundError(f"No time zone found with key {key}")
    monkeypatch.setattr(zoneinfo, "ZoneInfo", _gone)
    cfg = hosted_config()                                             # builds (does not crash) ...
    assert cfg.zone_ok is False
    assert hosted_problems(cfg, NOW) and any("time zone" in p for p in hosted_problems(cfg, NOW))   # ... and the deploy check refuses it
    from alto.bass.beta_store import FakeStore
    from alto.bass.hosted import HostedGate
    store = FakeStore(auto_terms=True)
    store.put("bass_beta/hosted", {"uids": [LUKE]})
    store.put("bass_beta/bass_testers", {"emails": [LUKE_EMAIL]})
    proxy = StubProxy()
    gate = HostedGate(proxy, store, Verifier(), cfg=cfg, pins=frozenset({LUKE}), clock=at(NOW))
    for action in ACTIONS:                                            # even Luke, even before the cutoff: the identical empty answer
        st, _, body = post(gate, action, "tok-luke")
        assert (st, body) == (200, b"{}")
    assert proxy.calls == []


def test_a_missing_zone_database_still_raises_for_every_other_config(monkeypatch):
    import zoneinfo

    from alto.bass.beta_config import BetaConfig
    monkeypatch.setattr(zoneinfo, "ZoneInfo", lambda key, *a, **k: (_ for _ in ()).throw(zoneinfo.ZoneInfoNotFoundError(key)))
    with pytest.raises(zoneinfo.ZoneInfoNotFoundError):
        BetaConfig(testers=1)
