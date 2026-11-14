"""The product must not need the Anthropic SDK (anthropic, httpx2) to load, and the set of Bass tests that skip without it is pinned.
Both run in fresh interpreters with the SDK BLOCKED (a meta-path finder that raises ModuleNotFoundError), so they behave the same with or
without the SDK installed. No network, no key."""
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_BLOCK = textwrap.dedent('''
    import sys
    class _Block:
        def find_spec(self, name, path=None, target=None):
            if name.split(".")[0] in ("anthropic", "httpx2"):
                raise ModuleNotFoundError("No module named %r (blocked: the SDK is not installed)" % name, name=name)
    sys.meta_path.insert(0, _Block())
''')

# POSIX-only stdlib modules, blocked the way a Windows interpreter lacks them (an import raises ImportError). `posix` itself is not blocked:
# os needs it on POSIX; the product never imports it directly (scanned: none).
POSIX_ONLY = ("pwd", "grp", "fcntl", "termios", "resource", "pty", "tty", "syslog", "crypt", "spwd", "nis")

# Needs fastapi (the hosted-web extra), not the SDK; unrelated to Bass and absent from the plain install at 1.9.225 too.
NEEDS_FASTAPI = {"alto.auth.oauth", "alto.web"}

# Bass test files with a skip because the SDK (anthropic / httpx2) is absent. A new entry must be a deliberate, reviewed change. These tests
# run in the SDK env (venv-studio: the Bass suite, 1,057 tests) and the money-emulator step of the private CI. test_bass_inert_public.py is
# listed for ONE test only (the beta-proxy mock transport builds an SDK client); its other tests run without the SDK. test_bass_proxy_not_started
# and test_stale_guard never skip. Skips for other reasons (pypdf, playwright) are not counted here.
EXPECTED_SKIPPED_WITHOUT_SDK = {
    "tests/test_bass_actions.py",
    "tests/test_bass_array_roundtrip_1111.py",
    "tests/test_bass_beta.py",
    "tests/test_bass_beta_allowance.py",
    "tests/test_bass_beta_b1.py",
    "tests/test_bass_beta_proxy.py",
    "tests/test_bass_beta_report.py",
    "tests/test_bass_beta_review.py",
    "tests/test_bass_beta_terms.py",
    "tests/test_bass_convert.py",
    "tests/test_bass_engine.py",
    "tests/test_bass_errors.py",
    "tests/test_bass_firstcall_rehearse.py",
    "tests/test_bass_guard.py",
    "tests/test_bass_incident_1111.py",
    "tests/test_bass_inert_public.py",
    "tests/test_bass_isolation_1111.py",
    "tests/test_bass_live_check.py",
    "tests/test_bass_live_fixes.py",
    "tests/test_bass_local_server.py",
    "tests/test_bass_meter_ledger.py",
    "tests/test_bass_money_emulator_cases.py",
    "tests/test_bass_research_share.py",
    "tests/test_bass_shapes.py",
    "tests/test_bass_studyplan.py",
    "tests/test_bass_tools.py",
    "tests/test_bass_wire.py",
}


def _env(tmp, posix=False):
    env = {k: v for k, v in os.environ.items() if not k.startswith("ANTHROPIC_") and k != "ALTO_LIVE_ANTHROPIC"}
    env.update(ALTO_NO_NETWORK="1", HOME=str(tmp), PYTHONPATH=str(tmp) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    Path(tmp, "sitecustomize.py").write_text(_BLOCK + ("\nfor _m in %r:\n    sys.modules[_m] = None\n" % (POSIX_ONLY,) if posix else ""))
    return env


import pytest


@pytest.mark.parametrize("posix", [False, True], ids=["posix", "no-posix"])
def test_every_alto_module_imports_and_a_page_builds_with_the_sdk_blocked(posix):
    with tempfile.TemporaryDirectory() as tmp:
        code = textwrap.dedent('''
            import asyncio, importlib, json, pkgutil, sys
            sys.path.insert(0, %r)
            import alto
            skip = set(%r)
            bad = []
            for m in pkgutil.walk_packages(alto.__path__, "alto."):
                if m.name in skip:
                    continue
                try:
                    importlib.import_module(m.name)
                except BaseException as e:
                    bad.append([m.name, repr(e)[:160]])
            from alto import mcp_server
            tools = asyncio.run(mcp_server.mcp.list_tools())
            from alto.build.builder import build_timeline, load_brief
            from alto.build.pages import build_home
            b, n, c = load_brief(json.load(open(%r)))
            page = build_timeline(b, n, c)[0]
            home = build_home([{"name": "Law", "pid": "p", "courses": []}])
            print(json.dumps({"bad": bad, "tools": len(tools), "page": len(page), "home": len(home),
                              "sdk": [k for k in sys.modules if k.split(".")[0] in ("anthropic", "httpx2")]}))
        ''' % (str(ROOT), sorted(NEEDS_FASTAPI), str(ROOT / "samples" / "outline_brief.json")))
        r = subprocess.run([sys.executable, "-c", code], cwd=tmp, env=_env(tmp, posix), capture_output=True, text=True, timeout=300)
        assert r.returncode == 0, r.stderr[-1500:]
        out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["bad"] == [], out["bad"]
    assert out["tools"] > 0 and out["page"] > 100000 and out["home"] > 10000
    assert out["sdk"] == [], "the SDK got imported while loading the product: " + str(out["sdk"])


def test_the_whole_tests_folder_collects_with_the_posix_modules_blocked():
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "--ignore=tests/security"],
                           cwd=ROOT, env=_env(tmp, True), capture_output=True, text=True, timeout=600)
    last = r.stdout.strip().splitlines()[-1]
    assert r.returncode == 0 and "error" not in last, (last, [l for l in r.stdout.splitlines() if l.startswith("ERROR")][:10])


@pytest.mark.parametrize("posix", [False, True], ids=["posix", "no-posix"])
def test_the_bass_tests_that_skip_without_the_sdk_are_exactly_the_expected_list(posix):
    with tempfile.TemporaryDirectory() as tmp:
        files = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "tests").glob("test_bass_*.py"))
        files = [f for f in files if "browser" not in f and not f.endswith("test_bass_sdk_free.py")] + ["tests/test_stale_guard.py"]
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider", *files],
                           cwd=ROOT, env=_env(tmp, posix), capture_output=True, text=True, timeout=900)
    last = r.stdout.strip().splitlines()[-1]
    assert " failed" not in last and " error" not in last, (last, [l for l in r.stdout.splitlines() if l.startswith(("FAILED", "ERROR"))][:10])
    skipped, per_file = set(), {}
    for line in r.stdout.splitlines():
        m = re.match(r"SKIPPED \[(\d+)\] (tests/\S+?):\d+: could not import '(anthropic|httpx2)'", line)
        if m:
            skipped.add(m.group(2))
            per_file[m.group(2)] = int(m.group(1))
    assert skipped == EXPECTED_SKIPPED_WITHOUT_SDK, sorted(skipped ^ EXPECTED_SKIPPED_WITHOUT_SDK)
    assert per_file["tests/test_bass_inert_public.py"] == 1     # only the beta-proxy mock-transport test
    assert not any("proxy_not_started" in f or "stale_guard" in f for f in skipped)
