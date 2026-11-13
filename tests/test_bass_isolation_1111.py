"""Testing seat alto-testing-1111-basslive: default-store / credential isolation for Bass, run OUTSIDE tests/conftest.py.

Incident 11 Nov (ORG/notes-bass-review-1111.md): outside pytest, XDG_CONFIG_HOME is not redirected, store_mode() "auto" picked cloud because
the Mac's site.json exists, and Session._load() read the refresh token before net_guard blocked securetoken.googleapis.com.

Every case runs in a SUBPROCESS with a clean env (env -i style), a FAKE HOME whose ~/.config/alto holds a ready site.json and sign-in files
with a sentinel refresh token, ALTO_NO_NETWORK=1, and probe_isolation.py (net_guard installed first, audit hook on opens + real sockets).
No real HOME, no real account, no key, no network. Expected RED on e198c1cb; each red names its cause.

    ALTO_REPO=<worktree> <venv-studio python> -m pytest -q -p no:cacheprovider test_bass_isolation_1111.py

Copied into the branch from ORG/notes-testing/alto-bass-live/ (Home SECURITY stamp alto-testing-1111-basslive); in the repo ALTO_REPO
defaults to this checkout, so the rows run with the rest of tests/.

Contracts these tests pin (for the builder):
  (a) net_guard writes ONE line per block, containing the host, to the file named by $ALTO_NET_GUARD_LOG (the builder may choose the default
      path when unset; the test sets it).
  (b) with ALTO_NO_NETWORK=1, mcp_server.store_mode() never answers "cloud" from site.json and get_store()/uid() never build a Session:
      site.json and the sign-in files are not even opened, Session._load is never called.
  (c) every Bass entry point (library Proxy, ToolBox, bass_live_check --dry-run, bass_local_server mock proxy, bass_apidoc) either runs
      on its own explicit throw-away store with ZERO reads of ~/.config/alto and ZERO non-loopback attempts, or refuses (exit != 0) when
      it would fall back to the default store (ToolBox with no store).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("ALTO_REPO") or HERE.parent).resolve()
PY = os.environ.get("ALTO_BASS_PY") or sys.executable
PROBE = HERE / "probe_isolation.py"
SENTINEL = "FAKE-REFRESH-SENTINEL-1111"
CRED_DIRS = (".config/alto/", ".config/gcloud/")

if not (REPO / "alto" / "bass" / "net_guard.py").is_file():
    pytest.skip("set ALTO_REPO to a Bass worktree", allow_module_level=True)


@pytest.fixture
def fakehome(tmp_path):
    home = tmp_path / "fakehome"
    cfg = home / ".config" / "alto"
    cfg.mkdir(parents=True)
    (cfg / "site.json").write_text(json.dumps({"status": "ready", "project": "demo-fake-1111", "site": "demo-fake-1111",
                                               "config": {"apiKey": "AIzaFAKE-not-a-key", "projectId": "demo-fake-1111", "appId": "1:0:web:0",
                                                          "authDomain": "demo-fake-1111.firebaseapp.com"}}))
    for n in ("demo-fake-1111", "none"):
        (cfg / f"session-{n}.json").write_text(json.dumps({"refresh_token": SENTINEL, "uid": "fakeuid", "email": "fake@example.invalid"}))
    adc = home / ".config" / "gcloud"
    adc.mkdir(parents=True)
    (adc / "application_default_credentials.json").write_text(json.dumps({"type": "authorized_user", "refresh_token": SENTINEL,
                                                                          "client_id": "x", "client_secret": "y"}))
    (tmp_path / "tmp").mkdir()
    return home


def env_for(home, **extra):
    e = {"PATH": "/usr/bin:/bin", "HOME": str(home), "TMPDIR": str(home.parent / "tmp"), "ALTO_NO_NETWORK": "1", "LANG": "en_US.UTF-8",
         "REPO": str(REPO)}
    e.update(extra)
    assert "ALTO_LIVE_ANTHROPIC" not in e and "XDG_CONFIG_HOME" not in e and "ALTO_STORE" not in e      # outside-pytest conditions
    return e


def probe(home, target, *args, timeout=240, **extra):
    log = home.parent / "probe.jsonl"
    if log.exists():
        log.unlink()
    r = subprocess.run([PY, "-I", str(PROBE), str(REPO), str(log), str(target), *map(str, args)], cwd=str(home.parent), env=env_for(home, **extra),
                       capture_output=True, text=True, timeout=timeout)
    evs = [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
    return r, evs


def leaks(evs):
    opened = sorted({e["path"] for e in evs if e["ev"] == "open" and e["path"].startswith(CRED_DIRS)})
    hosts = sorted({e["host"] for e in evs if e["ev"] in ("blocked", "allowed") and e["host"] not in ("127.0.0.1", "localhost", "::1", "")})
    real = [e for e in evs if e["ev"].startswith("socket.") and "127.0.0.1" not in e.get("arg", "")]
    return {"opened": opened, "hosts": hosts, "real_sockets": real}


CLEAN = {"opened": [], "hosts": [], "real_sockets": []}


def code(src):
    return "py:" + src


# ── (a) net_guard logs every block ──────────────────────────────────────────────────────────────────────────────────────────────────────

def test_a_net_guard_writes_one_log_line_per_block(fakehome):
    logf = fakehome.parent / "guard.log"
    src = r"""
import socket
from alto.bass import net_guard as G
G.install()
n = 0
for f in (lambda: socket.getaddrinfo("securetoken.googleapis.com", 443),
          lambda: socket.create_connection(("api.anthropic.com", 443), timeout=1),
          lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("192.0.2.1", 443))):
    try:
        f()
    except G.RealNetworkBlocked:
        n += 1
assert n == 3, n
"""
    r, evs = probe(fakehome, code(src), ALTO_NET_GUARD_LOG=str(logf))
    assert [e for e in evs if e["ev"] == "end"][0]["code"] == 0, (r.stderr[-800:], evs)
    assert logf.is_file(), "net_guard wrote no log line for 3 blocks (no log at all)"
    lines = [x for x in logf.read_text().splitlines() if x.strip()]
    assert len(lines) == 3, lines
    for host, line in zip(("securetoken.googleapis.com", "api.anthropic.com", "192.0.2.1"), lines):
        assert host in line, (host, line)


# ── (b) the cloud store is refused BEFORE any credential or site.json read ──────────────────────────────────────────────────────────────

B_SRC = r"""
import json, sys
from alto.cloud import session as S
calls = []
def _load(self):
    calls.append("_load"); raise AssertionError("Session._load called: the refresh token would be read")
def _exchange(self, rt):
    calls.append("_exchange"); raise AssertionError("Session._exchange called")
S.Session._load, S.Session._exchange = _load, _exchange
from alto import mcp_server as srv
out = {}
out["store_mode"] = srv.store_mode()
try:
    st = srv.get_store(); out["get_store"] = type(st).__name__
except Exception as e:
    out["get_store"] = "raised " + type(e).__name__ + ": " + str(e)[:120]
try:
    out["uid"] = srv.uid()
except Exception as e:
    out["uid"] = "raised " + type(e).__name__ + ": " + str(e)[:120]
out["calls"] = calls
print("B_RESULT " + json.dumps(out))
"""


@pytest.mark.parametrize("mock_installed", [False, True], ids=["ALTO_NO_NETWORK", "ALTO_NO_NETWORK+bass_mock"])
def test_b_cloud_store_is_refused_before_site_json_or_the_sign_in_file_is_read(fakehome, mock_installed):
    src = ("from alto.bass import mock_anthropic as M\nM.MockAnthropic()\n" if mock_installed else "") + B_SRC
    r, evs = probe(fakehome, code(src))
    line = [x for x in r.stdout.splitlines() if x.startswith("B_RESULT ")]
    assert line, (r.stdout[-500:], r.stderr[-1500:], evs[-3:])
    out = json.loads(line[0][9:])
    lk = leaks(evs)
    problems = []
    if out["store_mode"] == "cloud":
        problems.append("store_mode() answered 'cloud' from site.json under ALTO_NO_NETWORK=1")
    if out["get_store"] == "CloudStore":
        problems.append("get_store() built a CloudStore")
    if out["calls"]:
        problems.append(f"Session methods called: {out['calls']}")
    if lk["opened"]:
        problems.append(f"credential/config files opened: {lk['opened']}")
    if lk["hosts"]:
        problems.append(f"network attempted (blocked): {lk['hosts']}")
    assert problems == [], {"problems": problems, "out": out}


# ── (c) every Bass entry point, outside pytest, against a Mac that has a real-looking site.json ─────────────────────────────────────────

C1_PROXY = r"""
import sys, os, tempfile
from pathlib import Path
sys.path.insert(0, os.environ["REPO"] + "/tests")
import test_bass_beta_proxy as TP
p = TP.two_accounts(Path(tempfile.mkdtemp()))
TP.a_builds(p)              # the incident's script: one mock build through the beta Proxy with an explicit LocalStore belt
"""

C3_LOCAL_SERVER = r"""
import sys, os, json, runpy, tempfile
from pathlib import Path
sys.path.insert(0, os.environ["REPO"] + "/tests")
srv = runpy.run_path(os.environ["REPO"] + "/tools/bass_local_server.py", run_name="bass_local_server")
from alto.bass import mock_anthropic as M
import bass_beta_support as B
brief = json.load(open(os.environ["REPO"] + "/samples/contracts_brief.json"))
mock = M.MockAnthropic(M.build("Contracts", brief["brief"], brief["nodes"], brief["connections"]))
root = Path(tempfile.mkdtemp())
p = srv["build_proxy"]("own", root, 8765, "tok-" + "y" * 24, False, mock=mock)
h = {"Authorization": "Bearer tok-" + "y" * 24, "Origin": "http://127.0.0.1:8765"}
st, _, body = p.handle_http("POST", h, json.dumps({"action": "build", "args": B.build_req()["args"]}))
out = json.loads(body)
assert st == 200 and out.get("ok"), out
"""

C4_APIDOC = r"""
import sys, os, runpy, tempfile
m = runpy.run_path(os.environ["REPO"] + "/tests/bass_apidoc.py", run_name="bass_apidoc")
m["samples"](tempfile.mkdtemp())           # what --write runs, without writing docs/bass-api.md
"""

C5_TOOLBOX_NO_STORE = r"""
from alto.bass.tools import ToolBox
tb = ToolBox()                              # no explicit store: the belt would use Alto's DEFAULT store
r = tb.execute("u1", "list_projects", {})
print("C5_RESULT", str(getattr(r, "content", r))[:200])
"""


def _tool_errors(r):
    return [x for x in (r.stdout + r.stderr).splitlines() if "tool_failed" in x or "RealNetworkBlocked" in x][:3]


def test_c1_library_proxy_mock_build_never_touches_the_default_account(fakehome):
    r, evs = probe(fakehome, code(C1_PROXY))
    end = [e for e in evs if e["ev"] == "end"][0]
    assert (leaks(evs), end["code"]) == (CLEAN, 0), {"exc": [e for e in evs if e["ev"] == "exception"][:1], "tool_errors": _tool_errors(r)}


def test_c2_bass_live_check_dry_run_never_touches_the_default_account(fakehome):
    out = fakehome.parent / "lc-out"
    r, evs = probe(fakehome, REPO / "tools" / "bass_live_check.py", "--dry-run", "--builds", "5", "--out", out)
    end = [e for e in evs if e["ev"] == "end"][0]
    assert (leaks(evs), end["code"]) == (CLEAN, 0), {"stderr": r.stderr[-600:], "exc": [e for e in evs if e["ev"] == "exception"][:1]}


def test_c3_bass_local_server_mock_build_never_touches_the_default_account(fakehome):
    r, evs = probe(fakehome, code(C3_LOCAL_SERVER))
    end = [e for e in evs if e["ev"] == "end"][0]
    assert (leaks(evs), end["code"]) == (CLEAN, 0), {"exc": [e for e in evs if e["ev"] == "exception"][:1]}


def test_c4_bass_apidoc_samples_never_touch_the_default_account(fakehome):
    r, evs = probe(fakehome, code(C4_APIDOC))
    end = [e for e in evs if e["ev"] == "end"][0]
    assert (leaks(evs), end["code"]) == (CLEAN, 0), {"exc": [e for e in evs if e["ev"] == "exception"][:1]}


def test_c5_a_bass_belt_with_no_explicit_store_refuses_instead_of_using_the_default_store(fakehome):
    r, evs = probe(fakehome, code(C5_TOOLBOX_NO_STORE))
    end = [e for e in evs if e["ev"] == "end"][0]
    refused = end["code"] != 0 and not any(e["ev"] == "exception" and e["type"] in ("AssertionError",) for e in evs)
    assert leaks(evs) == CLEAN and refused, {"leaks": leaks(evs), "exit": end["code"], "stdout": r.stdout[-300:],
                                              "exc": [e for e in evs if e["ev"] == "exception"][:1]}


@pytest.mark.parametrize("tool", ["bass_beta_report.py", "bass_docs_purge.py"])
def test_c6_it_tools_refuse_under_alto_no_network_before_reading_google_credentials(fakehome, tool):
    r, evs = probe(fakehome, REPO / "tools" / tool, "--project", "demo-fake-1111")
    end = [e for e in evs if e["ev"] == "end"][0]
    exc = [e for e in evs if e["ev"] == "exception"]
    if exc and exc[0]["type"] in ("ModuleNotFoundError", "ImportError"):
        pytest.skip(f"{tool}: google-cloud libraries absent in this venv ({exc[0]['msg']}); refusal NOT designed, only an ImportError")
    assert leaks(evs) == CLEAN and end["code"] != 0, {"leaks": leaks(evs), "exit": end["code"], "stderr": r.stderr[-300:]}


# ── (d) get_key() itself holds BOTH gates (static: this seat never sets ALTO_LIVE_ANTHROPIC, so the env gate cannot be opened to test it) ─

def test_d_studio_key_get_key_checks_the_go_flag_itself_not_only_the_env_gate():
    import ast
    src = (REPO / "alto" / "bass" / "studio_key.py").read_text("utf-8")
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "get_key")
    body = ast.get_source_segment(src, fn)
    before_keychain = body.split('"security"', 1)[0]
    assert "ALTO_LIVE_ANTHROPIC" in before_keychain
    assert any(k in before_keychain for k in ("go_flag_path", "live_enabled", "LIVE_GO")), \
        "get_key() reads the Keychain on ALTO_LIVE_ANTHROPIC=1 alone; the LIVE_GO gate lives only in its callers"
