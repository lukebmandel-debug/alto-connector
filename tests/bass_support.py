"""Shared guard for the Bass tests (imported by every tests/test_bass_*.py).

The `bass_guard` fixture is autouse in every module that imports it: it refuses to run against the cloud
(ALTO_STORE=cloud or any luke-alto env), and makes ANY real network attempt fail loudly. The only wire the tests have
is the MockTransport behind the SDK."""
import os
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class RealNetworkAttempt(AssertionError):
    pass


def _refuse_cloud_env():
    if os.environ.get("ALTO_LIVE_ANTHROPIC"):
        pytest.exit("alto bass tests: refusing to run with ALTO_LIVE_ANTHROPIC set", returncode=3)
    if os.environ.get("ALTO_STORE", "").strip().lower() in ("cloud", "firestore"):
        pytest.exit("alto bass tests: refusing to run with ALTO_STORE=cloud", returncode=3)
    for k, v in os.environ.items():
        if "luke-alto" in (k + "=" + v).lower():
            pytest.exit("alto bass tests: refusing to run with a luke-alto env set (" + k + ")", returncode=3)


_refuse_cloud_env()


@pytest.fixture(autouse=True, scope="session")
def _no_real_anthropic():
    """IT's guard (INSTALL.md section 4): any DNS/connect to an Anthropic host raises. Ours below is stricter per test."""
    from alto.bass import net_guard
    net_guard.install()


@pytest.fixture(autouse=True)
def bass_guard(monkeypatch, tmp_path):
    _refuse_cloud_env()
    hits = []

    def boom(what):
        def f(*a, **k):
            hits.append(what)
            raise RealNetworkAttempt(f"real network attempt: {what} {a[:1]}")
        return f

    monkeypatch.setattr(socket.socket, "connect", boom("socket.connect"))
    monkeypatch.setattr(socket.socket, "connect_ex", boom("socket.connect_ex"))
    monkeypatch.setattr(socket, "getaddrinfo", boom("getaddrinfo"))
    monkeypatch.setattr(socket, "create_connection", boom("create_connection"))
    import httpx2
    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", boom("httpx2.HTTPTransport"))
    monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", boom("httpx2.AsyncHTTPTransport"))
    monkeypatch.setenv("ALTO_STORE", "local")
    monkeypatch.setenv("ALTO_STORE_DIR", str(tmp_path / "store"))
    monkeypatch.setenv("ALTO_BASS_LIVE_GO", str(tmp_path / "no-such-go-flag"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    yield hits
    assert not hits, f"a real network attempt happened: {hits}"
