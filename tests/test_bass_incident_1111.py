"""Incident 11 Nov (notes-bass-review-1111.md): ad-hoc runs outside pytest let store_mode() go 'auto' -> cloud on this Mac's real
site.json, and Session._load() read the real refresh token into memory before the network guard blocked the token exchange.

  (a) every net_guard block writes one line (time, host, pid, argv[0], rule) to a fixed log; no secret, no URL path, no body;
  (b) an offline process (ALTO_NO_NETWORK=1, or the guard installed) refuses every account store at store selection, BEFORE site.json,
      a sign-in file or Session._load() is touched; explicit ALTO_STORE=local and a set_store() test store keep working; the real app
      path (no ALTO_NO_NETWORK, no guard) is unchanged;
  (c) tools/bass_live_check.py, tools/bass_local_server.py and tests/bass_apidoc.py refuse to start without ALTO_STORE=local, and run
      under a private HOME: each is run here in a CLEAN subprocess (outside conftest) with a fake HOME holding a fake site.json and
      sign-in, and an audit hook proves those fake credential files are never opened.

Zero network: every host check raises before any real DNS or socket; the subprocesses get ALTO_NO_NETWORK=1 except the one that proves
the app path unchanged, which only reads its own fake files and never asks for a token."""
import pytest as _pytest_sdk
_pytest_sdk.importorskip("anthropic")   # public CI has no SDK: these skip there (listed in test_bass_sdk_free.py) and run in the SDK env
_pytest_sdk.importorskip("httpx2")
import json
import os
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

from bass_support import ROOT
from alto.bass import net_guard
from alto.cloud import offline

PY = sys.executable
FAKE_KEY, FAKE_REFRESH, FAKE_PROJECT = "FAKE-SITE-KEY-1111", "FAKE-REFRESH-TOKEN-1111", "fake-proj-1111"


def fake_config(cfg_root: Path) -> Path:
    """<cfg_root>/alto with a READY site.json, a sign-in file and accounts.json, all fake. -> the alto config dir."""
    d = cfg_root / "alto"
    d.mkdir(parents=True, exist_ok=True)
    (d / "site.json").write_text(json.dumps({"status": "ready", "project": FAKE_PROJECT, "site": FAKE_PROJECT,
                                             "config": {"apiKey": FAKE_KEY, "projectId": FAKE_PROJECT}}))
    (d / f"session-{FAKE_PROJECT}.json").write_text(json.dumps({"refresh_token": FAKE_REFRESH, "uid": "U-fake", "email": "f@x.invalid"}))
    (d / "accounts.json").write_text(json.dumps({"accounts": [{"id": FAKE_PROJECT, "project": FAKE_PROJECT}]}))
    return d


# ── (a) the block log ────────────────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def guard_log(monkeypatch, tmp_path):
    p = tmp_path / "logs" / "net_guard.log"
    monkeypatch.setenv("ALTO_NET_GUARD_LOG", str(p))
    return p


def _lines(p: Path):
    return p.read_text().splitlines() if p.exists() else []


def test_every_block_writes_one_log_line_with_time_host_pid_argv0(guard_log, monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")
    monkeypatch.delenv("ALTO_LIVE_ANTHROPIC", raising=False)
    with pytest.raises(net_guard.RealNetworkBlocked):
        net_guard._check("securetoken.googleapis.com")
    with pytest.raises(net_guard.RealNetworkBlocked):
        net_guard._check("api.anthropic.com")
    net_guard._check("127.0.0.1")                                     # allowed: not a block, not logged
    lines = _lines(guard_log)
    assert len(lines) == 2
    f = lines[0].split("\t")
    assert f[1] == "blocked" and f[2] == "host=securetoken.googleapis.com" and f[3] == f"pid={os.getpid()}"
    assert f[4] == "argv0=" + sys.argv[0][:200] and f[5] == "rule=no_network"
    assert time.strptime(f[0][:19], "%Y-%m-%dT%H:%M:%S")             # local ISO time
    assert "host=api.anthropic.com" in lines[1] and lines[1].endswith("rule=anthropic")
    assert oct(guard_log.stat().st_mode & 0o777) == "0o600"


def test_refused_google_url_logs_the_host_only_never_path_query_or_userinfo(guard_log):
    with pytest.raises(net_guard.RealNetworkBlocked):
        net_guard.check_google_url("https://user:PASSWORD-X@evil.example/drive?access_token=TOKEN-X#frag")
    text = guard_log.read_text()
    assert "host=evil.example" in text and "rule=google_url" in text
    for secret in ("PASSWORD-X", "TOKEN-X", "access_token", "/drive", "user"):
        assert secret not in text


def test_log_line_cannot_be_split_by_a_hostile_host(guard_log, monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")
    with pytest.raises(net_guard.RealNetworkBlocked):
        net_guard._check("a.example\nforged\tline")
    assert len(_lines(guard_log)) == 1


def test_log_write_failure_never_stops_the_block(monkeypatch, tmp_path):
    (tmp_path / "file").write_text("x")
    monkeypatch.setenv("ALTO_NET_GUARD_LOG", str(tmp_path / "file" / "cannot" / "net_guard.log"))
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")
    with pytest.raises(net_guard.RealNetworkBlocked):
        net_guard._check("example.com")


def test_default_log_path_is_fixed_under_the_real_home_not_HOME(monkeypatch, tmp_path):
    import pwd
    monkeypatch.delenv("ALTO_NET_GUARD_LOG")
    monkeypatch.setenv("HOME", str(tmp_path))                         # a private temp HOME (isolate.py) must not move the log
    assert net_guard.log_path() == os.path.join(pwd.getpwuid(os.getuid()).pw_dir, "Library", "Logs", "Alto", "net_guard.log")


# ── (b) refuse every account store before any credential read ───────────────────────────────────────────────────────────────────

@pytest.fixture
def offline_world(monkeypatch, tmp_path):
    """A fake READY site + sign-in in an UNREGISTERED config dir (as on this Mac outside pytest), ALTO_STORE unset, spies on reads."""
    from pathlib import Path as P
    from alto import mcp_server as srv
    from alto.cloud import session as sess, site as site_rec
    cfg = tmp_path / "xdg"
    fake = fake_config(cfg)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg))
    monkeypatch.delenv("ALTO_STORE", raising=False)
    monkeypatch.setattr(offline, "_TEST_ROOTS", [])                   # NOT pytest's registered fake: behave as an ad-hoc script would
    srv.set_store(None)
    sess.set_session(None)
    calls = {"Session._load": 0, "site.load": 0, "opened": []}
    real_load, real_site_load, real_rt, real_open = sess.Session._load, site_rec.load, P.read_text, P.open

    def spy_load(self):
        calls["Session._load"] += 1
        return real_load(self)

    def spy_site_load():
        calls["site.load"] += 1
        return real_site_load()

    def spy_rt(self, *a, **k):
        if str(self).startswith(str(fake)):
            calls["opened"].append(str(self))
        return real_rt(self, *a, **k)

    def spy_open(self, *a, **k):
        if str(self).startswith(str(fake)):
            calls["opened"].append(str(self))
        return real_open(self, *a, **k)
    monkeypatch.setattr(sess.Session, "_load", spy_load)
    monkeypatch.setattr(site_rec, "load", spy_site_load)
    monkeypatch.setattr(P, "read_text", spy_rt)
    monkeypatch.setattr(P, "open", spy_open)
    yield srv, calls
    srv.set_store(None)
    sess.set_session(None)


def _untouched(calls):
    assert calls["Session._load"] == 0, "Session._load was called"
    assert calls["site.load"] == 0, "site.json was read"
    assert calls["opened"] == [], calls["opened"]


@pytest.mark.parametrize("why", ["env", "guard"])
@pytest.mark.parametrize("store", [None, "auto", "cloud", "firestore", "${ALTO_STORE}"])
def test_offline_refuses_every_account_store_before_any_credential_read(offline_world, monkeypatch, store, why):
    srv, calls = offline_world
    if store is not None:
        monkeypatch.setenv("ALTO_STORE", store)
    if why == "env":
        monkeypatch.setenv("ALTO_NO_NETWORK", "1")
    else:                                                             # no env var, but the Bass mock's guard is installed
        monkeypatch.delenv("ALTO_NO_NETWORK", raising=False)
        monkeypatch.setattr(net_guard, "_installed", True)
    assert srv.store_mode() == "local"                                # never 'cloud' offline, decided without opening site.json
    with pytest.raises(offline.CloudStoreRefused, match="ALTO_STORE=local"):
        srv.get_store()                                               # store selection refuses: not even the real local folder
    assert srv.uid() == "local"
    from alto.cloud.session import get_session
    with pytest.raises(offline.CloudStoreRefused):
        get_session()
    _untouched(calls)


def test_offline_refuses_an_account_scoped_call_before_its_sign_in_is_read(offline_world, monkeypatch):
    srv, calls = offline_world
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")
    from alto.cloud import accounts
    a = {"id": FAKE_PROJECT, "project": FAKE_PROJECT, "site": FAKE_PROJECT, "config": {"apiKey": FAKE_KEY, "projectId": FAKE_PROJECT}}
    tok = accounts._ACTIVE.set(a)
    try:
        with pytest.raises(offline.CloudStoreRefused):
            srv.get_store()
        assert srv.store_mode() == "local"
        with pytest.raises(offline.CloudStoreRefused):
            accounts.session_for(a)
    finally:
        accounts._ACTIVE.reset(tok)
    _untouched(calls)


def test_offline_second_wall_reads_no_real_file(offline_world, monkeypatch):
    srv, calls = offline_world
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")
    from alto.cloud import accounts, session as sess
    import alto.cloud.site as site_mod
    assert site_mod.load() == {} and site_mod.ready() is False        # called directly: answers empty without opening the file
    assert accounts._load_saved() == [] and accounts._peek(FAKE_PROJECT)["signed_in"] is False
    assert sess.Session({"projectId": FAKE_PROJECT, "apiKey": "k"}).data == {}       # constructed directly: _load answers empty, no open
    assert calls["opened"] == []


def test_offline_explicit_local_store_keeps_working(offline_world, monkeypatch):
    srv, calls = offline_world
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")
    monkeypatch.setenv("ALTO_STORE", "local")
    from alto.store.local import LocalStore
    assert srv.store_mode() == "local" and isinstance(srv.get_store(), LocalStore) and srv.uid() == "local"
    _untouched(calls)


def test_offline_a_test_store_handed_in_keeps_working(offline_world, monkeypatch, tmp_path):
    srv, calls = offline_world
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")
    from alto.store.local import LocalStore
    st = LocalStore(str(tmp_path / "s"))
    srv.set_store(st)
    assert srv.get_store() is st and srv.store_mode() == "local" and srv.uid() == "local"
    _untouched(calls)


# ── clean subprocesses (outside conftest) ───────────────────────────────────────────────────────────────────────────────────────

# Runs a target with an audit hook that appends to REPORT every open() of a file under the fake ~/.config. Written on each hit, so a
# server that is terminated still leaves its record.
_HOOK = textwrap.dedent("""
    import os, sys, runpy
    FAKE, REPORT = os.path.realpath(os.environ.pop("T_FAKE_CFG")), os.environ.pop("T_REPORT")
    def hook(ev, args):
        if ev == "open" and args and isinstance(args[0], (str, bytes)):
            p = os.fsdecode(args[0])
            try:
                rp = os.path.realpath(p)
            except Exception:
                rp = p
            if rp.startswith(FAKE):
                with open(REPORT, "a") as f:
                    f.write(rp + "\\n")
    sys.addaudithook(hook)
    target = sys.argv[1]
    sys.argv = sys.argv[1:]
    if target == "-c":
        sys.argv = ["-c"]
        exec(compile(os.environ.pop("T_CODE"), "<t>", "exec"), {"__name__": "__main__"})
    else:
        runpy.run_path(target, run_name="__main__")
""")


@pytest.fixture
def clean(tmp_path):
    """-> run(args, extra_env, code=None, popen=False): a clean subprocess, fake HOME with fake site.json + sign-in under ~/.config/alto."""
    home = tmp_path / "home"
    fake = fake_config(home / ".config")
    report = tmp_path / "opened.txt"
    log = tmp_path / "net_guard.log"

    def env_for(extra):
        e = {"PATH": "/usr/bin:/bin", "HOME": str(home), "LANG": "en_US.UTF-8", "ALTO_UPDATE_CHECK": "off",
             "PYTHONDONTWRITEBYTECODE": "1", "ALTO_NET_GUARD_LOG": str(log), "T_FAKE_CFG": str(fake), "T_REPORT": str(report)}
        e.update(extra)
        return e

    def run(args, extra=None, code=None, popen=False, timeout=240):
        e = env_for(extra or {})
        if code is not None:
            e["T_CODE"] = code
            args = ["-c"]
        cmd = [PY, "-c", _HOOK] + list(args)
        if popen:
            return subprocess.Popen(cmd, env=e, cwd=str(tmp_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return subprocess.run(cmd, env=e, cwd=str(tmp_path), capture_output=True, text=True, timeout=timeout)

    def opened():
        return report.read_text().splitlines() if report.exists() else []
    run.opened, run.home, run.fake, run.log = opened, home, fake, log
    return run


def _app_code(body):
    return f"import sys; sys.path.insert(0, {str(ROOT)!r})\n" + textwrap.dedent(body)


def test_clean_subprocess_default_store_is_refused_and_no_credential_is_opened(clean):
    code = _app_code("""
        from alto.cloud import session as sess
        hits = []
        real = sess.Session._load
        sess.Session._load = lambda self: hits.append(1) or real(self)
        from alto import mcp_server as srv
        from alto.cloud.offline import CloudStoreRefused
        assert srv.store_mode() == "local" and srv.uid() == "local"
        try:
            srv.get_store(); print("NOT REFUSED"); sys.exit(1)
        except CloudStoreRefused as e:
            assert "ALTO_STORE=local" in str(e)
        assert hits == [], "Session._load was called"
        print("REFUSED-OK")
    """)
    r = clean([], {"ALTO_NO_NETWORK": "1"}, code=code)
    assert r.returncode == 0 and "REFUSED-OK" in r.stdout, r.stdout + r.stderr
    assert clean.opened() == []


def test_clean_subprocess_mock_guard_alone_refuses_the_default_store(clean):
    code = _app_code("""
        from alto.bass import mock_anthropic as M
        M.MockAnthropic()                          # installs the network guard, as the Bass mock always does
        from alto import mcp_server as srv
        from alto.cloud.offline import CloudStoreRefused
        try:
            srv.get_store(); sys.exit(1)
        except CloudStoreRefused:
            print("REFUSED-OK")
    """)
    r = clean([], {}, code=code)
    assert r.returncode == 0 and "REFUSED-OK" in r.stdout, r.stdout + r.stderr
    assert clean.opened() == []


def test_clean_subprocess_block_goes_through_the_installed_guard_and_is_logged(clean):
    code = _app_code("""
        import socket
        from alto.bass import net_guard
        net_guard.install()
        try:
            socket.getaddrinfo("securetoken.googleapis.com", 443); sys.exit(1)
        except net_guard.RealNetworkBlocked:
            print("BLOCKED-OK")
    """)
    r = clean([], {"ALTO_NO_NETWORK": "1"}, code=code)
    assert r.returncode == 0 and "BLOCKED-OK" in r.stdout, r.stdout + r.stderr
    (line,) = clean.log.read_text().splitlines()
    assert "\tblocked\thost=securetoken.googleapis.com\tpid=" in line and "\targv0=-c\t" in line and line.endswith("rule=no_network")


def test_clean_subprocess_real_app_path_is_unchanged(clean):
    """No ALTO_NO_NETWORK, no Bass guard: 'auto' still means the user's own account when site.json is ready (it reads only the fake)."""
    code = _app_code("""
        from alto import mcp_server as srv
        from alto.cloud import offline
        assert offline.reason() is None and "alto.bass.net_guard" not in sys.modules
        print("MODE", srv.store_mode())
    """)
    r = clean([], {}, code=code)
    assert r.returncode == 0 and "MODE cloud" in r.stdout, r.stdout + r.stderr
    assert any(p.endswith("site.json") for p in clean.opened())           # the app reads its site record exactly as before


TOOLS = {"bass_live_check": ROOT / "tools" / "bass_live_check.py", "bass_local_server": ROOT / "tools" / "bass_local_server.py",
         "bass_apidoc": ROOT / "tests" / "bass_apidoc.py"}


@pytest.mark.parametrize("name", sorted(TOOLS))
@pytest.mark.parametrize("store", ["auto", "cloud", "firestore"])
def test_each_tool_refuses_to_start_when_asked_for_any_store_but_its_own_local_one(clean, name, store):
    args = [str(TOOLS[name])] + (["--dry-run", "--out", str(clean.home / "out")] if name == "bass_live_check" else
                                 ["--purpose", "own", "--port", "0"] if name == "bass_local_server" else [])
    r = clean(args, {"ALTO_NO_NETWORK": "1", "ALTO_STORE": store}, timeout=120)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "runs only on its own throw-away local store" in r.stderr and repr(store) in r.stderr
    assert clean.opened() == []


@pytest.mark.parametrize("name,args", [("bass_live_check", []), ("bass_local_server", ["--purpose", "own", "--live", "--port", "0"])])
def test_a_live_run_without_an_explicit_test_store_refuses_before_any_gate(clean, name, args):
    r = clean([str(TOOLS[name])] + args, {"ALTO_NO_NETWORK": "1"}, timeout=120)
    assert r.returncode == 2 and "needs an explicit test store for a live run" in r.stderr, r.stdout + r.stderr
    assert clean.opened() == []


def test_live_check_dry_run_with_a_test_store_runs_and_never_opens_the_fake_credentials(clean, tmp_path):
    r = clean([str(TOOLS["bass_live_check"]), "--dry-run", "--builds", "5", "--out", str(tmp_path / "out")],
              {"ALTO_NO_NETWORK": "1", "ALTO_STORE": "local"})
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert (tmp_path / "out" / "measurements.dry-run.json").is_file() and "tool_failed" not in (tmp_path / "out" / "measurements.dry-run.json").read_text()
    assert clean.opened() == []


def test_apidoc_with_a_test_store_runs_and_never_opens_the_fake_credentials(clean):
    r = clean([str(TOOLS["bass_apidoc"])], {"ALTO_NO_NETWORK": "1"})                     # no ALTO_STORE: pinned to its own local store
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    # the same doc the pytest-made docs/bass-api.md is (the 16:38 run's mock build failed and came out with timeline_id null in more places)
    assert "Calls and states" in r.stdout and "tool_failed" not in r.stdout
    assert r.stdout.count('"timeline_id": null') == (ROOT / "docs" / "bass-api.md").read_text().count('"timeline_id": null')
    assert clean.opened() == []


def test_local_server_with_a_test_store_starts_and_never_opens_the_fake_credentials(clean, tmp_path):
    p = clean([str(TOOLS["bass_local_server"]), "--purpose", "own", "--build-site", "--store-root", str(tmp_path / "root"), "--port", "0"],
              {}, popen=True)                                          # mock server, no ALTO_STORE, not even ALTO_NO_NETWORK
    out, seen = [], threading.Event()

    def pump():
        for line in p.stdout:
            out.append(line)
            if "Open: http://127.0.0.1:" in line:
                seen.set()
    t = threading.Thread(target=pump, daemon=True)
    t.start()
    try:
        assert seen.wait(120), "".join(out)
    finally:
        p.terminate()
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=10)
        t.join(10)
        p.stdout.close()
        p.stderr.close()
    assert clean.opened() == []


# ── studio_key.get_key holds BOTH live locks itself ─────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("env_gate,go_file", [(False, False), (True, False), (False, True)])
def test_get_key_refuses_unless_both_gates_and_never_invokes_security(monkeypatch, tmp_path, env_gate, go_file):
    from alto.bass import studio_key
    go = tmp_path / "LIVE_GO"
    if go_file:
        go.write_text("go")
    monkeypatch.setenv("ALTO_BASS_LIVE_GO", str(go))
    if env_gate:
        monkeypatch.setenv("ALTO_LIVE_ANTHROPIC", "1")             # set on the function's own env only; nothing below can reach a key
    else:
        monkeypatch.delenv("ALTO_LIVE_ANTHROPIC", raising=False)
    calls = []
    monkeypatch.setattr(studio_key.subprocess, "run", lambda *a, **k: calls.append(a) or (_ for _ in ()).throw(AssertionError("security run")))
    monkeypatch.setattr(studio_key.subprocess, "Popen", lambda *a, **k: calls.append(a) or (_ for _ in ()).throw(AssertionError("Popen")))
    with pytest.raises(studio_key.KeyUnavailable, match="LIVE_GO" if env_gate else "ALTO_LIVE_ANTHROPIC"):
        studio_key.get_key()
    assert calls == []


# ── a Bass tool belt with no store refuses ──────────────────────────────────────────────────────────────────────────────────────────

def test_toolbox_with_no_store_refuses_instead_of_using_the_default_store():
    from alto.bass.tools import ToolBox
    with pytest.raises(offline.CloudStoreRefused, match="explicit store"):
        ToolBox()
    with pytest.raises(offline.CloudStoreRefused):
        ToolBox(None)


# ── IT's Google tools: a designed refusal offline, before any Google library or credential ──────────────────────────────────────────

@pytest.mark.parametrize("tool", ["bass_beta_report.py", "bass_docs_purge.py"])
def test_it_tools_refuse_offline_with_a_clear_message_before_google_credentials(clean, tool):
    r = clean([str(ROOT / "tools" / tool), "--project", "demo-fake-1111"], {"ALTO_NO_NETWORK": "1"}, timeout=120)
    assert r.returncode == 2 and f"refused: {tool} reads Firestore with Google's default credentials" in r.stderr, r.stdout + r.stderr
    assert "ModuleNotFoundError" not in r.stderr and clean.opened() == []


def test_update_check_stays_off_offline_unless_a_test_opts_in(monkeypatch):
    from alto import update_check as U
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")
    monkeypatch.delenv("ALTO_UPDATE_CHECK", raising=False)
    calls = []
    monkeypatch.setattr(U, "_fetch_latest", lambda: calls.append(1) or "")
    U.reset_for_tests()
    try:
        U.start()
        assert calls == [] and U._started is False                    # offline: never a GitHub call
        monkeypatch.setattr(U, "_TEST_ALLOW_OFFLINE", True)
        U.start(); U._done.wait(2)
        assert calls == [1]
    finally:
        U.reset_for_tests()
