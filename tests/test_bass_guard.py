"""The loud-fail guards: real network attempts, stray client construction, live mode without Luke's go, and the
refusal to run against the cloud."""
import re
import socket
from pathlib import Path

import pytest

from bass_support import bass_guard, RealNetworkAttempt, _refuse_cloud_env, ROOT  # noqa: F401
from alto.bass import client as C
from alto.bass import errors as ER
from alto.bass import keys
from alto.bass import mock_anthropic as M

PKG = ROOT / "alto" / "bass"


def test_a_real_socket_attempt_fails_loudly(bass_guard):
    with pytest.raises(RealNetworkAttempt):
        socket.create_connection(("api.anthropic.com", 443), timeout=1)
    with pytest.raises(RealNetworkAttempt):
        socket.getaddrinfo("api.anthropic.com", 443)
    s = socket.socket()
    with pytest.raises(RealNetworkAttempt):
        s.connect(("127.0.0.1", 9))
    s.close()
    assert len(bass_guard) == 3
    bass_guard.clear()                         # these were on purpose; the fixture fails the test if any remain


def test_a_real_httpx_transport_fails_loudly(bass_guard):
    import httpx2
    with pytest.raises(RealNetworkAttempt):
        httpx2.get("https://api.anthropic.com/v1/models")
    bass_guard.clear()


def test_a_sdk_client_without_the_mock_transport_cannot_reach_anthropic(bass_guard):
    import anthropic
    c = anthropic.Anthropic(api_key=keys.MockKeyProvider().get_key(), max_retries=0)
    with pytest.raises(Exception):
        c.messages.create(model="claude-haiku-5-5", max_tokens=5, messages=[{"role": "user", "content": "x"}])
    assert bass_guard                          # the attempt was seen ...
    bass_guard.clear()                         # ... and refused


def test_the_mock_client_never_touches_the_network(bass_guard):
    m = M.MockAnthropic()
    c = C.make_client("mock", mock=m)
    c.messages.create(model="claude-haiku-5-5", max_tokens=5, messages=[{"role": "user", "content": "x"}])
    assert bass_guard == [] and len(m.requests) == 1


def test_only_client_py_constructs_an_anthropic_client():
    pat = re.compile(r"\b(?:Async)?Anthropic(?:Bedrock|Vertex|Foundry)?\s*\(")
    offenders = []
    for f in sorted(PKG.glob("*.py")):
        for i, line in enumerate(f.read_text("utf-8").splitlines(), 1):
            code = line.split("#")[0]
            if pat.search(code) and f.name != "client.py":
                offenders.append(f"{f.name}:{i}")
    assert offenders == []
    assert pat.search((PKG / "client.py").read_text("utf-8"))        # and it really is constructed there


def test_the_scan_would_catch_a_stray_construction(tmp_path):
    pat = re.compile(r"\b(?:Async)?Anthropic(?:Bedrock|Vertex|Foundry)?\s*\(")
    assert pat.search("c = anthropic.Anthropic(api_key=k)") and pat.search("x = AsyncAnthropic()")
    assert not pat.search("from anthropic import Anthropic")


def test_no_key_literal_anywhere_but_the_mock_prefix():
    key = re.compile("sk-" + "ant-(?!MOCK)")
    bad = [f.name for f in PKG.glob("*.py") if key.search(f.read_text("utf-8"))]
    assert bad == []
    bad_tests = [f.name for f in (ROOT / "tests").glob("*bass*.py") if key.search(f.read_text("utf-8"))]
    assert bad_tests == []
    assert M.MOCK_KEY.startswith("sk-" + "ant-MOCK")


def test_no_bass_code_reads_a_key_from_the_environment_or_a_file():
    for f in PKG.glob("*.py"):
        src = f.read_text("utf-8")
        assert "ANTHROPIC_API_KEY" not in src and "ANTHROPIC_AUTH_TOKEN" not in src, f.name
        assert ".env" not in src.replace("os.environ", ""), f.name


def test_live_mode_refuses_without_the_go_flag():
    assert not C.live_enabled()
    with pytest.raises(ER.LiveNotEnabled) as e:
        C.make_client("live")
    assert e.value.code == "bass_paused" and "Nothing was charged" in e.value.user_message


def test_live_mode_with_the_flag_still_needs_the_live_gate_and_never_reaches_the_keychain(tmp_path, monkeypatch):
    import subprocess
    flag = tmp_path / "go"
    flag.write_text("go")
    monkeypatch.setenv("ALTO_BASS_LIVE_GO", str(flag))
    monkeypatch.delenv("ALTO_LIVE_ANTHROPIC", raising=False)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("the Keychain must not be touched"))
    assert C.live_enabled()
    with pytest.raises(ER.NotConfigured) as e:    # IT's gate: no ALTO_LIVE_ANTHROPIC=1, so no key and no client
        C.make_client("live")
    assert "not enabled" in str(e.value)
    assert keys.KeychainKeyProvider().describe() == {"provider": "keychain", "service": "alto-anthropic-test"}


def test_studio_key_refuses_without_the_gate_and_secret_hides_itself(monkeypatch):
    import subprocess
    from alto.bass import studio_key
    monkeypatch.delenv("ALTO_LIVE_ANTHROPIC", raising=False)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("the Keychain must not be touched"))
    with pytest.raises(studio_key.KeyUnavailable):
        studio_key.get_key()
    s = studio_key.Secret("sk-" + "ant-MOCK-demo")
    assert repr(s) == "<Secret>" and f"{s}" == "<Secret>" and str(s) == "<Secret>"


def test_net_guard_blocks_anthropic_hosts_and_the_mock_installs_it():
    from alto.bass import net_guard
    M.MockAnthropic()
    with pytest.raises(net_guard.RealNetworkBlocked):
        net_guard._check("api.anthropic.com")
    with pytest.raises(net_guard.RealNetworkBlocked):
        net_guard._check("console.claude.ai")
    mp = pytest.MonkeyPatch()
    try:
        mp.delenv("ALTO_NO_NETWORK", raising=False)
        net_guard._check("example.org")                      # only Anthropic hosts are blocked by default
        mp.setenv("ALTO_NO_NETWORK", "1")
        with pytest.raises(net_guard.RealNetworkBlocked):    # and with the beta runs' ALTO_NO_NETWORK=1, every other host too
            net_guard._check("example.org")
        net_guard._check("127.0.0.1")
    finally:
        mp.undo()


def test_key_providers():
    assert keys.MockKeyProvider().get_key().startswith("sk-" + "ant-MOCK")
    with pytest.raises(ER.NotConfigured):
        keys.KeychainKeyProvider().get_key()          # gate off in tests: never reaches the Keychain
    assert "key" not in str(keys.KeychainKeyProvider().describe()).replace("keychain", "")


def test_unknown_client_mode():
    with pytest.raises(ValueError):
        C.make_client("staging")


def test_tests_refuse_to_run_with_the_live_gate_set(monkeypatch):
    monkeypatch.setenv("ALTO_LIVE_ANTHROPIC", "1")
    with pytest.raises(BaseException) as e:
        _refuse_cloud_env()
    assert "ALTO_LIVE_ANTHROPIC" in str(e.value)


def test_tests_refuse_to_run_against_the_cloud(monkeypatch):
    monkeypatch.setenv("ALTO_STORE", "cloud")
    with pytest.raises(BaseException) as e:
        _refuse_cloud_env()
    assert "refusing" in str(e.value)
    monkeypatch.setenv("ALTO_STORE", "local")
    monkeypatch.setenv("ALTO_FIREBASE_SITE", "luke-alto.web.app")
    with pytest.raises(BaseException) as e2:
        _refuse_cloud_env()
    assert "luke-alto" in str(e2.value)
    monkeypatch.delenv("ALTO_FIREBASE_SITE")
    _refuse_cloud_env()                           # clean env: fine


def test_mock_requires_the_headers_a_real_key_would_send():
    import httpx2
    m = M.MockAnthropic()
    assert m.handle(httpx2.Request("POST", "https://api.anthropic.com/v1/messages", json={})).status_code == 401


BOGUS = "https://evil.example.invalid"


class _FakeKeys(keys.KeyProvider):
    name = "fake"

    def get_key(self):
        return M.MOCK_KEY


def test_mock_client_ignores_anthropic_env_and_every_request_goes_to_api_anthropic_com(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", BOGUS)
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "bogus-token")
    monkeypatch.setenv("ANTHROPIC_CUSTOM_HEADERS", "X-Leak: 1")
    m = M.MockAnthropic()
    c = C.make_client("mock", mock=m)
    assert c.base_url.host == "api.anthropic.com" and c.auth_token is None
    c.messages.create(model="claude-haiku-5-5", max_tokens=5, messages=[{"role": "user", "content": "x"}])
    req = m.requests[-1]
    h = req["headers"]
    assert req["host"] == "api.anthropic.com" and "bogus-token" not in str(h)
    assert M.MOCK_KEY in (h.get("x-api-key", ""), h.get("authorization", "").removeprefix("Bearer "))   # SDK 2.x sends Bearer
    assert "x-leak" not in h
    import os
    assert os.environ["ANTHROPIC_BASE_URL"] == BOGUS and os.environ["ANTHROPIC_AUTH_TOKEN"] == "bogus-token"   # restored


def test_live_client_pins_base_url_and_ignores_anthropic_env(tmp_path, monkeypatch):
    flag = tmp_path / "go"
    flag.write_text("go")
    monkeypatch.setenv("ALTO_BASS_LIVE_GO", str(flag))
    for k in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_CUSTOM_HEADERS", "ANTHROPIC_PROFILE"):
        monkeypatch.setenv(k, BOGUS if k.endswith("URL") else "bogus")
    c = C.make_client("live", key_provider=_FakeKeys())            # a fake provider: no real key, no network
    assert c.base_url.host == "api.anthropic.com" and str(c.base_url).startswith("https://api.anthropic.com")
    assert c.auth_token is None and c.api_key == M.MOCK_KEY and c.max_retries == 0
    assert "evil" not in str(c.base_url) and not c._custom_headers.get("X-Leak")
    hdrs = c.auth_headers
    assert M.MOCK_KEY in (hdrs.get("X-Api-Key", ""), hdrs.get("Authorization", "").removeprefix("Bearer "))
    assert "bogus" not in str(hdrs)
    import os
    assert os.environ["ANTHROPIC_BASE_URL"] == BOGUS                # the process environment is put back untouched
