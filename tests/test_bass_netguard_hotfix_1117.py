"""Hotfix v1.9.236: hosted Bass was blocked by our own net_guard (RealNetworkBlocked). BetaProxy built MockAnthropic() in every mode, and its
__init__ installs net_guard process-wide. Now the mock is built lazily, only in mock mode. Each test runs in a FRESH subprocess because other
tests install the guard in this process. No network, no key."""
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("anthropic")        # public CI has no SDK: these run in the SDK env (listed in test_bass_sdk_free.py)
pytest.importorskip("httpx2")

ROOT = Path(__file__).resolve().parent.parent

PRE = textwrap.dedent("""
    import os, sys, socket
    sys.path.insert(0, %r); sys.path.insert(0, %r)
    os.environ.pop("ALTO_LIVE_ANTHROPIC", None); os.environ["ALTO_NO_NETWORK"] = "1"
    from bass_beta_support import EMAIL, FakeClock
    from alto.bass.beta_config import BetaConfig
    from alto.bass.beta_proxy import Proxy, SecretReader, TokenVerifier
    from alto.bass.beta_store import FakeStore
    from alto.bass.beta_ledger import LIVE_GO_KEY
    from alto.bass.tools import ToolBox
    from alto.store.local import LocalStore
    import tempfile
    class V(TokenVerifier):
        def verify(self, t): raise RuntimeError("unused")
    class S(SecretReader):
        def read(self, name): return "sk-" + "ant-FAKE-not-a-real-key-0001"
    real = (socket.getaddrinfo, socket.socket.connect, socket.create_connection)
    def patched(): return (socket.getaddrinfo, socket.socket.connect, socket.create_connection) != real
    store = FakeStore(auto_terms=True)
    px = Proxy(BetaConfig(testers=10, allowlist=frozenset({EMAIL})), store, V(), S(), ToolBox(LocalStore(tempfile.mkdtemp())), clock=FakeClock())
""" % (str(ROOT), str(ROOT / "tests")))


def _run(body: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", PRE + textwrap.dedent(body)], capture_output=True, text=True, timeout=120, cwd=str(ROOT))


def test_a_live_mode_proxy_leaves_the_sockets_alone():
    r = _run("""
        store.put(LIVE_GO_KEY, {"on": True})
        assert px.live_go() is True
        assert px._mock is None, "the mock must not be built when the proxy is constructed"
        assert not patched(), "constructing a BetaProxy patched socket"
        print("OK")
    """)
    assert r.returncode == 0 and "OK" in r.stdout, r.stderr[-800:]


def test_a_mock_mode_proxy_still_installs_the_guard_and_refuses_an_anthropic_host():
    r = _run("""
        assert not patched()
        px.client()                       # live_go is off: the mock client, and with it the guard
        assert patched(), "mock mode must install the guard"
        from alto.bass.net_guard import RealNetworkBlocked
        try:
            socket.create_connection(("api.anthropic.com", 443), timeout=1)
        except RealNetworkBlocked:
            print("OK")
    """)
    assert r.returncode == 0 and "OK" in r.stdout, r.stderr[-800:]


def test_a_hosted_proxy_never_installs_the_guard_even_after_a_request_with_live_go_off():
    r = _run("""
        hpx = Proxy(BetaConfig(testers=10, allowlist=frozenset({EMAIL})), store, V(), S(), ToolBox(LocalStore(tempfile.mkdtemp())), clock=FakeClock(), hosted=True)
        assert hpx.live_go() is False
        hpx.client()                      # a request while live_go is off: the mock client is built, the guard must NOT be
        assert hpx._mock is not None and not patched(), "a hosted mock request patched socket"
        store.put(LIVE_GO_KEY, {"on": True})
        try:
            hpx.client()                  # live_go flips on in the same process: the live client (the promo check may refuse; that is not the guard)
        except Exception as e:
            assert type(e).__name__ != "RealNetworkBlocked"
        assert not patched(), "socket is patched after live_go went on"
        print("OK")
    """)
    assert r.returncode == 0 and "OK" in r.stdout, r.stderr[-800:]


def test_both_hosted_entries_build_the_proxy_hosted():
    src = (ROOT / "deploy" / "bass-proxy" / "main.py").read_text("utf-8")
    assert src.count("Proxy(cfg,") == 2 and src.count("hosted=True") == 2


def test_importing_the_hosted_entry_does_not_patch_the_sockets():
    r = subprocess.run([sys.executable, "-c", textwrap.dedent("""
        import os, sys, socket
        sys.path.insert(0, %r); sys.path.insert(0, %r)
        os.environ.pop("ALTO_LIVE_ANTHROPIC", None)
        real = (socket.getaddrinfo, socket.socket.connect, socket.create_connection)
        try:
            import main  # noqa: F401
        except ImportError as e:
            print("SKIP", e); raise SystemExit(0)
        assert (socket.getaddrinfo, socket.socket.connect, socket.create_connection) == real
        print("OK")
    """ % (str(ROOT), str(ROOT / "deploy" / "bass-proxy")))], capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    assert r.returncode == 0 and ("OK" in r.stdout or "SKIP" in r.stdout), r.stderr[-800:]
