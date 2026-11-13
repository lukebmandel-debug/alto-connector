"""Bass is INERT on a public build: with neither ALTO_LIVE_ANTHROPIC=1 nor the LIVE_GO file, nothing reaches an API client, nothing looks up
the key, and the UI exposes no live path. Each check runs in a fresh interpreter with a clean environment and tripwires on subprocess (the
Keychain is read through `security`), sockets and the SDK client, so the proof is observed behaviour, not a reading of the code.
No network, no key, no Anthropic call."""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Tripwires (any Keychain/`security` call, any non-loopback socket or DNS), installed before anything of Alto is imported. Every hit is appended to HITS and printed as the last line.
_PRELUDE = r"""
import json, os, socket, subprocess, sys
sys.path.insert(0, %(root)r)
HITS = []
_real_run, _real_popen = subprocess.run, subprocess.Popen
def _argv(a):
    a = a[0] if a else ""
    return " ".join(a) if isinstance(a, (list, tuple)) else str(a)
def _keychain(a, k):
    s = _argv(a) + " " + str(k.get("args", ""))
    return "security" in s or "find-generic-password" in s or "keychain" in s.lower()
def _run(*a, **k):
    if _keychain(a, k):
        HITS.append(("keychain", _argv(a)))
        raise RuntimeError("tripwire: keychain " + _argv(a))
    return _real_run(*a, **k)
class _Popen(_real_popen):
    def __init__(self, *a, **k):
        if _keychain(a, k):
            HITS.append(("keychain", _argv(a)))
            raise RuntimeError("tripwire: keychain " + _argv(a))
        super().__init__(*a, **k)
subprocess.run, subprocess.Popen = _run, _Popen
def _sock(self, address, *a, **k):
    HITS.append(("socket", str(address)))
    raise RuntimeError("tripwire: connect " + str(address))
socket.socket.connect = _sock
_gai = socket.getaddrinfo
def _gai2(host, *a, **k):
    if str(host) not in ("localhost", "127.0.0.1", "::1", ""):
        HITS.append(("dns", str(host)))
        raise RuntimeError("tripwire: dns " + str(host))
    return _gai(host, *a, **k)
socket.getaddrinfo = _gai2
def done(**extra):
    print(json.dumps(dict(hits=HITS, **extra)))
"""


def _run(body: str, extra_env: dict | None = None, tmp_path: Path | None = None, argv: list | None = None):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("ALTO_", "ANTHROPIC_")) and k not in ("HOME", "XDG_CONFIG_HOME")}
    env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"), ALTO_NO_NETWORK="1", ALTO_STORE="local",
               ALTO_STORE_DIR=str(tmp_path / "store"), ALTO_NET_GUARD_LOG=str(tmp_path / "ng.log"),
               ALTO_BASS_LIVE_GO=str(home / "no-live-go"), PYTHONDONTWRITEBYTECODE="1")
    env.update(extra_env or {})
    code = (_PRELUDE % {"root": str(ROOT)}) + textwrap.dedent(body)
    p = subprocess.run([sys.executable, "-W", "ignore", "-c", code, *(argv or [])], env=env, capture_output=True, text=True, timeout=240)
    assert p.returncode == 0, p.stderr[-2000:]
    return json.loads(p.stdout.strip().splitlines()[-1])


def _no_hits(r):
    assert r["hits"] == [], r["hits"]


def test_the_app_never_loads_bass_or_the_sdk(tmp_path):
    r = _run("""
        import alto, alto.mcp_server, alto.publish_static, alto.update_check
        from alto.build import pages, single_file, builder, palace_assets
        from alto.cloud import offline, accounts, session, site
        bass = sorted(m for m in sys.modules if m == "alto.bass" or m.startswith("alto.bass."))
        done(bass=bass, anthropic="anthropic" in sys.modules)
    """, tmp_path=tmp_path)
    _no_hits(r)
    assert r["bass"] == [] and r["anthropic"] is False


def test_a_normal_build_exposes_no_live_path(tmp_path):
    r = _run("""
        from alto.build import bass_ui, palace_assets, engine_patches
        from alto.build.builder import build_timeline, load_brief
        from alto.build.pages import build_home
        from alto import publish_static
        b, n, c = load_brief(json.loads(open(os.path.join(%r, "samples", "outline_brief.json")).read()))
        tl = build_timeline(b, n, c)[0]
        home = build_home([{"name": "Law", "pid": "p", "courses": []}])
        csp = publish_static._security_headers(None)
        done(enabled=bass_ui.enabled(), base=bass_ui.base_url(), picker=publish_static._picker_csp(),
             hosted=[a[0] for a in palace_assets.assets() if a[0] == "bass"], found=bool(palace_assets.find(bass_ui.PATH)),
             pages_have=[s for s in ("alto-bass", "aep-bass", "bs-panel", "_ALTO_BASS_BASE", "_altoBass", "drive-picker", "bass_beta", "api.anthropic.com")
                         if s in tl or s in home], headers_have=[s for s in ("anthropic", "drive-picker") if s in json.dumps(csp)],
             bass_loaded=any(m.startswith("alto.bass") for m in sys.modules))
    """ % str(ROOT), tmp_path=tmp_path)
    _no_hits(r)
    assert r["enabled"] is False and r["base"] == "" and r["picker"] is None
    assert r["hosted"] == [] and r["found"] is False
    assert r["pages_have"] == [] and r["headers_have"] == [] and r["bass_loaded"] is False


GATE_CASES = {"neither": ({}, False), "env only": ({"ALTO_LIVE_ANTHROPIC": "1"}, False), "file only": ({}, True)}


@pytest.mark.parametrize("name", list(GATE_CASES))
def test_any_one_gate_alone_never_looks_up_the_key_or_builds_a_live_client(tmp_path, name):
    env, make_file = GATE_CASES[name]
    if make_file:
        (tmp_path / "home").mkdir(exist_ok=True)
        (tmp_path / "home" / "no-live-go").write_text("")
    r = _run("""
        import anthropic
        built = []
        _init = anthropic.Anthropic.__init__
        def spy(self, *a, **k):
            built.append(str(k.get("base_url")))
            return _init(self, *a, **k)
        anthropic.Anthropic.__init__ = spy
        from alto.bass import studio_key, client as C, keys, errors
        out = {}
        try:
            studio_key.get_key(); out["get_key"] = "returned"
        except studio_key.KeyUnavailable as e:
            out["get_key"] = "refused"
        try:
            keys.KeychainKeyProvider().get_key(); out["provider"] = "returned"
        except keys.NotConfigured:
            out["provider"] = "refused"
        try:
            C.make_client("live"); out["live"] = "returned"
        except (errors.LiveNotEnabled, keys.NotConfigured):
            out["live"] = "refused"
        done(out=out, built=built)
    """, extra_env=env, tmp_path=tmp_path)
    _no_hits(r)                                       # no `security` call, no socket, no DNS
    assert r["out"] == {"get_key": "refused", "provider": "refused", "live": "refused"}
    assert r["built"] == []                           # no SDK client was constructed at all


def test_the_beta_proxy_without_the_server_flag_serves_only_the_mock(tmp_path):
    """The server side (deploy/bass-proxy) goes live only on its own store flag plus a secret read; with the flag absent it serves the mock,
    reads no secret, and its client is the mock transport. Nothing in the shipped app starts it."""
    r = _run("""
        sys.path.insert(0, os.path.join(%r, "tests"))
        import bass_beta_support as S
        from alto.bass import beta_proxy as BP
        reads = []
        class Reader(BP.SecretReader):
            def read(self, name):
                reads.append(name)
                raise AssertionError("secret read")
        st = S.make_stack(%r)
        px = BP.Proxy(st.cfg, st.store, None, Reader(), st.tools, clock=st.clock)
        c1 = px.client()
        c2 = px.client()
        done(reads=reads, live_go=px.live_go(), mode=px._client_mode, same=c1 is c2,
             transport=type(c1._client._transport).__name__, base=str(c1.base_url))
    """ % (str(ROOT), str(tmp_path / "stack")), tmp_path=tmp_path)
    _no_hits(r)
    assert r["reads"] == [] and r["live_go"] is False and r["mode"] == "mock" and r["same"] is True
    assert "HTTPTransport" not in r["transport"], r["transport"]


def test_the_live_tools_refuse_without_both_gates_and_touch_nothing(tmp_path):
    """The two scripts that could go live refuse before any key lookup or network, with each gate missing."""
    for tool, args in (("bass_live_check.py", []), ("bass_local_server.py", ["--purpose", "own", "--live"])):
        home = tmp_path / ("h-" + tool)
        home.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith(("ALTO_", "ANTHROPIC_")) and k != "HOME"}
        env.update(HOME=str(home), ALTO_NO_NETWORK="1", ALTO_STORE="local", ALTO_NET_GUARD_LOG=str(tmp_path / ("ng-" + tool)),
                   ALTO_BASS_LIVE_GO=str(home / "no-live-go"))
        # a PATH with no `security` binary: a Keychain lookup would fail loudly, not silently succeed
        bindir = tmp_path / ("bin-" + tool)
        bindir.mkdir()
        (bindir / "security").write_text("#!/bin/sh\necho SECURITY-CALLED >> %s\nexit 44\n" % (tmp_path / ("sec-" + tool)))
        (bindir / "security").chmod(0o755)
        env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
        p = subprocess.run([sys.executable, "-W", "ignore", str(ROOT / "tools" / tool), *args], env=env, capture_output=True, text=True, timeout=120)
        assert p.returncode != 0, (tool, p.stdout[-500:])
        assert not (tmp_path / ("sec-" + tool)).exists(), tool + " looked up the Keychain"
        assert not (tmp_path / ("ng-" + tool)).exists() or "host=" not in (tmp_path / ("ng-" + tool)).read_text(), tool + " tried the network"
