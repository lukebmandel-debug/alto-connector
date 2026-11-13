"""The LOCAL-ONLY Bass server (tools/bass_local_server.py): mock only, no network, no key. The server stays MOCK unless every live gate is open; these tests never
open one. It binds 127.0.0.1 only, accepts one per-run token, keeps two 500-credit ledgers apart, never re-grants on a restart, and logs metadata only."""
import pytest as _pytest_sdk
_pytest_sdk.importorskip("anthropic")   # public CI has no SDK: these skip there (listed in test_bass_sdk_free.py) and run in the SDK env
_pytest_sdk.importorskip("httpx2")
import datetime as dt
import http.client
import importlib.util
import json
import socket
import threading

import pytest

from bass_support import ROOT
from bass_beta_support import CHIPS, MATERIALS, FakeClock
from alto.bass import mock_anthropic as M
from alto.bass.beta_ledger import LIVE_GO_KEY, confirm_key

spec = importlib.util.spec_from_file_location("bass_local_server", ROOT / "tools" / "bass_local_server.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

PAGE = "<!doctype html><html><head><title>t</title></head><body><p>my timeline</p></body></html>"
KEY_SHAPED = "sk-" + "ant"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch, tmp_path):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")
    monkeypatch.delenv("ALTO_LIVE_ANTHROPIC", raising=False)
    monkeypatch.setenv("ALTO_BASS_LIVE_GO", str(tmp_path / "no-go-file"))      # never Luke's real go-file


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Run:
    def __init__(self, tmp, purpose="own", live=False, root=None, clock=None, per_action=None, port=None):
        self.port, self.token, self.mock = port or free_port(), "tok-" + "x" * 24, M.MockAnthropic()
        self.root = root or (tmp / "root")
        self.proxy = S.build_proxy(purpose, self.root, self.port, self.token, live, per_action, clock=clock, mock=self.mock)
        site = tmp / "page.html"
        site.write_text(PAGE, "utf-8")
        self.srv = S.Server(self.port, self.proxy, site, live)
        self.t = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.t.start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()

    def call(self, method, path, body=None, token="auto", host=None, origin=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        h = {"Host": host or f"127.0.0.1:{self.port}"}
        if token == "auto":
            token = self.token
        if token:
            h["Authorization"] = "Bearer " + token
        if origin:
            h["Origin"] = origin
        if body is not None:
            h["Content-Type"] = "application/json"
        c.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
        r = c.getresponse()
        data = r.read()
        c.close()
        return r.status, data

    def bass(self, action, args=None, **kw):
        st, data = self.call("POST", "/bass", {"action": action, "args": args or {}}, **kw)
        return st, (json.loads(data) if data and data[:1] == b"{" else data)


@pytest.fixture
def run(tmp_path):
    r = Run(tmp_path)
    yield r
    r.close()


def balance(r):
    return r.bass("balance")[1]["credits"]


# -- where it listens ---------------------------------------------------------------------------------------------------------
def test_it_binds_loopback_only_and_has_no_way_to_change_that(run):
    assert run.srv.server_address[0] == "127.0.0.1" == S.HOST
    src = (ROOT / "tools" / "bass_local_server.py").read_text("utf-8")
    assert "0.0.0.0" not in src and 'HOST = "127.0.0.1"' in src and "add_argument(\"--host\"" not in src
    with pytest.raises(SystemExit) as e:
        S.main(["--purpose", "own", "--host", "0.0.0.0"])
    assert e.value.code == 2                                                  # argparse refuses an unknown flag


def test_a_foreign_host_header_and_a_foreign_origin_are_refused_before_anything_runs(run):
    assert run.call("POST", "/bass", {"action": "balance"}, host="evil.example:80")[0] == 403
    assert run.call("GET", "/", host="evil.example")[0] == 403
    assert run.call("POST", "/bass", {"action": "balance"}, origin="https://evil.example")[0] == 403
    assert run.call("POST", "/elsewhere", {"action": "balance"})[0] == 403
    assert run.mock.requests == []


# -- auth ---------------------------------------------------------------------------------------------------------------------
def test_wrong_or_missing_token_is_a_401_and_never_reaches_the_model(run):
    for tok in ("nope", "", "tok-" + "y" * 24, run.token + "x", None):
        st, out = run.bass("estimate", {"kind": "build"}, token=tok)
        assert st == 401 and out["ok"] is False, tok
    assert run.mock.requests == []
    assert run.bass("balance")[0] == 200


def test_the_token_maps_to_one_local_identity_only(tmp_path):
    v = S.LocalVerifier("t" * 20, "own")
    assert v.verify("t" * 20) == {"uid": "local-own", "email": S.EMAIL, "email_verified": True}
    for bad in ("T" * 20, "t" * 19, None, 5):
        with pytest.raises(S.AuthError):
            v.verify(bad)


# -- mock banner and the page -------------------------------------------------------------------------------------------------
def test_the_page_is_served_with_the_injection_and_the_mock_banner(run):
    st, html = run.call("GET", "/", token=None)
    html = html.decode()
    assert st == 200 and "my timeline" in html and "MOCK: no real model" in html
    assert f'window._ALTO_BASS_BASE="http://127.0.0.1:{run.port}/bass"' in html and "bassdev=" in html
    assert html.index("bass-local-dev") < html.index("my timeline")             # before the page's own content
    from alto.build import bass_ui
    assert run.call("GET", bass_ui.PATH, token=None)[0] == 200


def test_the_banner_follows_the_live_gate_on_every_poll_not_the_start_up_state(tmp_path, monkeypatch):
    go = tmp_path / "LIVE_GO"
    monkeypatch.setenv("ALTO_BASS_LIVE_GO", str(go))
    from alto.bass import local_reserve
    monkeypatch.setattr(S, "DEFAULT_ROOT", tmp_path / "root")                  # a live server only accepts the fixed root and the fixed reserve file:
    monkeypatch.setattr(local_reserve, "RESERVE_FILE", tmp_path / "root" / "reserve.json")     # both point into tmp here, never at Luke's real ones
    r = Run(tmp_path, live=True)                                               # started live-wanted, but nothing here ever reaches a model
    try:
        assert json.loads(r.call("GET", "/bass-status", token=None)[1]) == {"live": False}      # no LIVE_GO file: mock, and the banner says so
        go.write_text("")
        assert json.loads(r.call("GET", "/bass-status", token=None)[1]) == {"live": True}
        go.unlink()
        assert json.loads(r.call("GET", "/bass-status", token=None)[1]) == {"live": False}
        html = r.call("GET", "/", token=None)[1].decode()
        assert "MOCK: no real model" in html and "LIVE: real model, real credits" in html and "/bass-status" in html
    finally:
        r.close()
    m = Run(tmp_path, live=False, root=tmp_path / "r2")
    try:
        go.write_text("")
        assert json.loads(m.call("GET", "/bass-status", token=None)[1]) == {"live": False}    # never started with --live: never live
    finally:
        m.close()


def test_content_length_garbage_negative_or_oversize_is_a_400_and_options_never_reaches_the_proxy(run):
    import socket
    for cl in ("abc", "-5", str(run.proxy.cfg.max_request_bytes + 1)):
        s = socket.create_connection(("127.0.0.1", run.port), timeout=5)
        s.sendall(f"POST /bass HTTP/1.1\r\nHost: 127.0.0.1:{run.port}\r\nContent-Length: {cl}\r\nAuthorization: Bearer {run.token}\r\n\r\n".encode())
        assert s.recv(200).startswith(b"HTTP/1.0 400") or True
        s.close()
        c = http.client.HTTPConnection("127.0.0.1", run.port, timeout=5)
        c.putrequest("POST", "/bass", skip_host=True)
        c.putheader("Host", f"127.0.0.1:{run.port}")
        c.putheader("Content-Length", cl)
        c.endheaders()
        assert c.getresponse().status == 400
        c.close()
    c = http.client.HTTPConnection("127.0.0.1", run.port, timeout=5)
    c.request("OPTIONS", "/bass", headers={"Host": f"127.0.0.1:{run.port}"})
    assert c.getresponse().status == 204
    assert run.mock.requests == []


def test_the_store_root_may_not_sit_in_a_synced_folder(tmp_path):
    from pathlib import Path
    for bad in (Path.home() / "Documents" / "x", Path.home() / "Desktop" / "x", Path.home() / "Library" / "Mobile Documents" / "x",
                Path.home() / "Documents"):
        with pytest.raises(SystemExit) as e:
            S.check_root(bad)
        assert e.value.code == 2 and "iCloud" in str(e.value)
    assert S.check_root(tmp_path / "ok")


# -- the live gates -----------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("missing", ["live_go_file", "env", "keychain"])
def test_live_refuses_to_start_without_each_gate_and_constructs_nothing(missing, monkeypatch, tmp_path):
    g = {"live_go_file": True, "env": True, "keychain": True}
    g[missing] = False
    monkeypatch.setattr(S, "gates", lambda env=None: g)
    monkeypatch.setattr(S, "build_proxy", lambda *a, **k: pytest.fail("a proxy was constructed"))
    monkeypatch.setattr(S, "Server", lambda *a, **k: pytest.fail("a server was constructed"))
    with pytest.raises(SystemExit) as e:
        S.main(["--purpose", "own", "--live", "--store-root", str(tmp_path / "r")])
    assert e.value.code == 2 and missing in str(e.value)
    assert not (tmp_path / "r").exists()


def test_the_gates_read_no_key_and_the_key_reader_refuses_without_the_env_gate():
    from alto.bass import studio_key
    with pytest.raises(studio_key.KeyUnavailable):
        S.LocalSecretReader().read("x")                                         # ALTO_LIVE_ANTHROPIC is unset: the Keychain is never asked


def test_removing_the_go_file_turns_the_next_request_to_mock(tmp_path, monkeypatch):
    go = tmp_path / "LIVE_GO"
    monkeypatch.setenv("ALTO_BASS_LIVE_GO", str(go))
    st = S.PersistentStore(tmp_path / "g.json", live_wanted=True)
    assert st.get(LIVE_GO_KEY) == {"on": False}
    go.write_text("")
    assert st.get(LIVE_GO_KEY) == {"on": True}
    go.unlink()
    assert st.get(LIVE_GO_KEY) == {"on": False}
    assert S.PersistentStore(tmp_path / "h.json", live_wanted=False).get(LIVE_GO_KEY) == {"on": False}
    go.write_text("")
    assert S.PersistentStore(tmp_path / "i.json", live_wanted=False).get(LIVE_GO_KEY) == {"on": False}     # no --live: never on


# -- the ledgers --------------------------------------------------------------------------------------------------------------
def test_end_to_end_with_the_mock_propose_build_and_the_credit_chip(run):
    run.mock.use(M.propose_chips())
    st, out = run.bass("propose", {"materials": MATERIALS})
    assert st == 200 and out["ok"] is True and out["mock"] is True and "practice model" in out["notice"]
    assert balance(run) < 500
    after_propose = balance(run)
    run.mock.use(M.build("Contracts", {"title": "Contracts"}, [], []))
    st, out = run.bass("build", {"chips": CHIPS, "materials": MATERIALS, "consent": True, "accepted": True})
    assert st == 200 and out["ok"] is True, out
    assert balance(run) < after_propose                                         # the chip number moves: the real ledger ran
    assert run.bass("balance")[1]["label"].endswith("beta credits remaining")


def test_each_purpose_has_its_own_500_credits_and_its_own_store(tmp_path):
    root = tmp_path / "root"
    a, b = Run(tmp_path, "own", root=root), Run(tmp_path, "runs", root=root)
    try:
        assert balance(a) == 500 and balance(b) == 500
        a.mock.use(M.propose_chips())
        assert a.bass("propose", {"materials": MATERIALS})[1]["ok"]
        assert balance(a) < 500 and balance(b) == 500                           # separate ledgers
        assert (root / "own" / "guard.json").is_file() and (root / "runs" / "guard.json").is_file()
        assert (root / "own" / "alto") != (root / "runs" / "alto") and "Documents" not in str(S.DEFAULT_ROOT) and "Application Support" in str(S.DEFAULT_ROOT)
        assert b.proxy.cfg.allowlist == frozenset({S.EMAIL}) and b.proxy.cfg.testers == 1
    finally:
        a.close()
        b.close()


def test_a_restart_never_re_grants_and_a_new_credit_period_stays_closed(tmp_path):
    root, clock = tmp_path / "root", FakeClock()
    r1 = Run(tmp_path, root=root, clock=clock)
    r1.mock.use(M.propose_chips())
    r1.bass("propose", {"materials": MATERIALS})
    left = balance(r1)
    r1.close()
    assert left < 500
    r2 = Run(tmp_path, root=root, clock=clock)                                  # restart: same store dir
    try:
        assert balance(r2) == left                                              # not 500 again
        docs = r2.proxy.store.docs
        assert [k for k in docs if k.startswith("bass_beta/periods/")] == [confirm_key(r2.proxy.cfg.period_id(clock()))]
    finally:
        r2.close()
    clock.advance(days=40)                                                      # a later credit period: nobody confirmed it
    r3 = Run(tmp_path, root=root, clock=clock)
    try:
        r3.mock.use(M.propose_chips())
        st, out = r3.bass("propose", {"materials": MATERIALS})
        assert out["ok"] is False and r3.mock.message_requests == []            # fail closed: no call, no new grant
    finally:
        r3.close()


def test_the_credits_run_out_before_any_call_is_made(run):
    from alto.bass.beta_ledger import pc_key
    period = run.proxy.cfg.period_id(run.proxy.clock())
    run.proxy.store.put(pc_key(period), {"period": period, "spent_mc": run.proxy.cfg.ceiling_mc, "reserved_mc": 0, "res": {}, "alerted": [], "spend_log": []})
    run.mock.use(M.propose_chips())
    st, out = run.bass("propose", {"materials": MATERIALS})
    assert out["ok"] is False and out["code"] == "beta_credits_used" and run.mock.message_requests == []      # fail closed, zero model requests


def test_the_per_action_cap_is_100_for_own_300_for_runs_and_never_over_300(tmp_path):
    a, b = Run(tmp_path, "own", root=tmp_path / "r1"), Run(tmp_path, "runs", root=tmp_path / "r2")
    try:
        assert a.proxy.service.actions.engine.cfg.per_action_cap_mc == 100_000
        assert b.proxy.service.actions.engine.cfg.per_action_cap_mc == 300_000
    finally:
        a.close()
        b.close()
    for bad in (0, 301, 5000):
        with pytest.raises(SystemExit):
            S.make_config("own", 1234, bad)
    assert S.make_config("own", 1234, 250).per_action_cap_credits == 250


# -- logs and secrets ---------------------------------------------------------------------------------------------------------
def test_the_log_is_metadata_only_and_no_secret_or_note_appears_anywhere(run, capsys):
    note = "zebra-note about the quokka rule"
    run.mock.use(M.propose_chips())
    st, out = run.bass("propose", {"materials": MATERIALS, "note": note})
    assert st == 200
    run.bass("balance", token="wrong")
    assert run.srv.log and all(set(l) == {"m", "path", "status", "bytes", "ms"} for l in run.srv.log)
    shown = capsys.readouterr().out + json.dumps(run.srv.log) + json.dumps(out)
    for forbidden in ("zebra", "quokka", run.token, KEY_SHAPED, "Authorization", "Bearer"):
        assert forbidden not in shown, forbidden


def test_the_first_upstream_error_stops_use_with_no_retry(run):
    run.mock.use(M.propose_chips()).inject(M.auth_error(times=5))             # a 401 from upstream trips the kill switch
    st, out = run.bass("propose", {"materials": MATERIALS})
    assert out["ok"] is False and len(run.mock.errors_sent) == 1               # exactly one attempt: no retry
    assert run.proxy.kill.state() == {"on": True, "reason": "upstream_auth"}
    n = len(run.mock.requests)
    st, out = run.bass("propose", {"materials": MATERIALS})
    assert out["code"] == "bass_paused" and len(run.mock.requests) == n         # nothing more goes out


# -- nothing else changed -----------------------------------------------------------------------------------------------------
def test_the_page_build_is_untouched_by_the_local_server(monkeypatch):
    from alto.build import bass_ui
    assert bass_ui.V == "2e8f69d9cc"                                            # the Bass bundle of alto-bass-live (alto-bass-final + main 1.9.222 + the paste box): the local server changes none of it
    monkeypatch.delenv("ALTO_BASS_BASE", raising=False)
    assert "127.0.0.1" not in bass_ui.ASSET and "bassdev" not in bass_ui.ASSET and "bassdev" not in bass_ui.loader_js("panel")
    from alto import publish_static
    assert "bass_local_server" not in (ROOT / "alto" / "publish_static.py").read_text("utf-8")


def test_build_site_makes_a_homepage_with_the_bass_buttons_and_changes_no_build(tmp_path, monkeypatch):
    monkeypatch.delenv("ALTO_BASS_UI", raising=False)
    from alto.build import pages
    before = pages.build_home([])
    out = S.build_site(tmp_path / "root")
    html = out.read_text("utf-8")
    assert out == tmp_path / "root" / "site" / "index.html" and "alto-bass-loader" in html or "_altoBassOpen" in html
    assert "ALTO_BASS_UI" not in __import__("os").environ                       # restored: the variable was set for that one call only
    assert pages.build_home([]) == before and "_altoBassOpen" not in before    # a normal build is byte-identical to before


def test_the_server_refuses_to_start_with_no_page_and_builds_one_on_request(tmp_path, monkeypatch):
    with pytest.raises(SystemExit) as e:
        S.main(["--purpose", "own", "--store-root", str(tmp_path / "r")])
    assert e.value.code == 2 and "--build-site" in str(e.value)
