"""net_guard is a security component. Without the POSIX account database (Windows: no `pwd`) it must stay FAIL-CLOSED: either it fully enforces
(an Anthropic host is refused, nothing is opened) or, when it cannot establish its home / log path, install() refuses (GuardUnavailable) so Bass
does not start unguarded. Never a weakened guard. Fresh interpreters with `pwd` blocked; no network, no key."""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_CODE = textwrap.dedent('''
    import json, os, socket, sys
    sys.modules["pwd"] = None                     # no account database, as on Windows
    sys.path.insert(0, %r)
    opened = []
    _real = socket.socket.connect
    socket.socket.connect = lambda self, a: opened.append(a) or (_ for _ in ()).throw(AssertionError("a connect was attempted"))
    from alto.bass import net_guard
    out = {"pwd_none": net_guard.pwd is None}
    try:
        net_guard.install(); out["install"] = "ok"
    except net_guard.GuardUnavailable as e:
        out["install"] = "refused"
    # whatever install did, an Anthropic host must still be refused when the guard is on, and nothing may connect
    try:
        net_guard._check("api.anthropic.com"); out["check"] = "allowed"
    except net_guard.RealNetworkBlocked:
        out["check"] = "blocked"
    try:
        socket.getaddrinfo("api.anthropic.com", 443); out["dns"] = "allowed"
    except net_guard.RealNetworkBlocked:
        out["dns"] = "blocked"
    except Exception as e:
        out["dns"] = "other:" + type(e).__name__
    try:
        p = net_guard.log_path(); out["log"] = p
    except net_guard.GuardUnavailable:
        out["log"] = None
    out["connects"] = len(opened)
    print(json.dumps(out))
''' % str(ROOT))


def _run(env_extra, unset=()):
    env = {k: v for k, v in os.environ.items() if k not in ("ALTO_LIVE_ANTHROPIC", "ALTO_NET_GUARD_LOG", *unset)}
    env.update(ALTO_NO_NETWORK="1", **env_extra)
    r = subprocess.run([sys.executable, "-W", "ignore", "-c", _CODE], env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-1500:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_without_pwd_but_with_a_home_the_guard_fully_enforces_and_logs_under_that_home(tmp_path):
    out = _run({"HOME": str(tmp_path), "USERPROFILE": str(tmp_path)})
    assert out["pwd_none"] is True and out["install"] == "ok"
    assert out["check"] == "blocked" and out["dns"] == "blocked" and out["connects"] == 0
    assert out["log"] == os.path.join(str(tmp_path), "Library", "Logs", "Alto", "net_guard.log")


def test_without_pwd_and_without_any_home_install_refuses_and_nothing_is_allowed(tmp_path):
    out = _run({}, unset=("HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH"))
    assert out["pwd_none"] is True
    assert out["install"] == "refused" and out["log"] is None            # fail closed: Bass cannot start with this guard
    assert out["check"] == "blocked"                                      # and the check itself still refuses Anthropic hosts
    assert out["connects"] == 0     # (DNS is not patched when install refuses: Bass never starts then, see the mock-layer test below)


def test_the_mock_layer_refuses_to_start_when_the_guard_cannot_install(tmp_path):
    code = textwrap.dedent('''
        import os, sys
        sys.modules["pwd"] = None
        sys.path.insert(0, %r)
        from alto.bass import net_guard, mock_anthropic
        try:
            mock_anthropic.MockAnthropic()
            print("STARTED")
        except net_guard.GuardUnavailable:
            print("REFUSED")
    ''' % str(ROOT))
    env = {k: v for k, v in os.environ.items() if k not in ("HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "ALTO_NET_GUARD_LOG", "ALTO_LIVE_ANTHROPIC")}
    env["ALTO_NO_NETWORK"] = "1"
    r = subprocess.run([sys.executable, "-W", "ignore", "-c", code], env=env, capture_output=True, text=True, timeout=120)
    assert r.stdout.strip().splitlines()[-1:] == ["REFUSED"], (r.stdout[-300:], r.stderr[-800:])
