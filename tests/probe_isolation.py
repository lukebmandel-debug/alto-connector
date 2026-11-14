"""Isolation probe (alto-testing-1111-basslive). Runs ONE Bass entry point OUTSIDE pytest (no tests/conftest.py) and records, to a JSON-lines
log, every file opened under $HOME/.config (Alto's site.json / sign-in files, gcloud ADC) and every network host anything tried to reach.

    python -I probe_isolation.py <repo> <log.jsonl> <target> [args...]

The caller gives a clean env with a FAKE HOME whose ~/.config/alto holds a ready site.json and a sign-in file with a sentinel refresh token.
Safety: ALTO_NO_NETWORK=1 is required, and the probe installs alto.bass.net_guard itself BEFORE the target runs, so a non-loopback host raises
whether or not the target would have installed the guard. Nothing here can reach the network or a real account.
"""
import json
import os
import runpy
import sys
import traceback

repo, logp, target, args = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
assert os.environ.get("ALTO_NO_NETWORK") == "1", "probe refuses without ALTO_NO_NETWORK=1"
assert "ALTO_LIVE_ANTHROPIC" not in os.environ, "probe refuses with ALTO_LIVE_ANTHROPIC set"
HOME = os.path.realpath(os.environ["HOME"])
assert "/fakehome" in HOME, "probe refuses a real HOME"
CFG = os.path.join(HOME, ".config")
_log = open(logp, "a", encoding="utf-8")


def rec(**k):
    _log.write(json.dumps(k) + "\n")
    _log.flush()


def hook(ev, a):
    if ev == "open" and a and isinstance(a[0], (str, bytes, os.PathLike)):
        p = os.path.realpath(os.fsdecode(a[0]))
        if p.startswith(CFG + os.sep):
            rec(ev="open", path=os.path.relpath(p, HOME), mode=str(a[1]), where=[f"{f.filename.split('/test-bass-live-1111/')[-1]}:{f.lineno}:{f.name}" for f in traceback.extract_stack()[:-1] if "/alto/" in f.filename or "/tools/" in f.filename][-6:])
    elif ev in ("socket.getaddrinfo", "socket.connect"):
        rec(ev=ev, arg=repr(a[:2])[:200])                   # a REAL socket call got past every guard (should never appear)


sys.addaudithook(hook)
sys.path.insert(0, repo)
from alto.bass import net_guard  # noqa: E402

_orig = net_guard._check


def _logged(host):
    try:
        _orig(host)
    except net_guard.RealNetworkBlocked:
        rec(ev="blocked", host=host, where=[f"{f.filename.split('/alto/',1)[-1]}:{f.lineno}:{f.name}" for f in traceback.extract_stack()[:-1] if "/alto/" in f.filename or "/tools/" in f.filename][-5:])
        raise
    rec(ev="allowed", host=host)


net_guard._check = _logged
net_guard.install()
rec(ev="start", target=target)
sys.argv = [target] + args
try:
    if target.startswith("py:"):                               # py:<code> runs inline code (library entry points)
        exec(compile(target[3:], "<probe-target>", "exec"), {"__name__": "__main__"})
        code = 0
    else:
        runpy.run_path(target, run_name="__main__")
        code = 0
except SystemExit as e:
    code = e.code if isinstance(e.code, int) else (0 if e.code is None else 2)
    rec(ev="exit_msg", msg=str(e.code)[:300] if not isinstance(e.code, int) else "")
except BaseException as e:  # noqa: BLE001
    rec(ev="exception", type=type(e).__name__, msg=str(e)[:300], tb=traceback.format_exc()[-1200:])
    code = 3
rec(ev="end", code=code)
sys.exit(code)
