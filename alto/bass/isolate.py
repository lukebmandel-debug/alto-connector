"""Start guard for the ad-hoc Bass tools (incident 11 Nov, notes-bass-review-1111.md).

tools/bass_live_check.py, tools/bass_local_server.py and tests/bass_apidoc.py run OUTSIDE pytest, so tests/conftest.py does not isolate
them. Each calls start() from its `if __name__ == "__main__":` block, before main() runs:

  1. Never the default store. ALTO_STORE set to anything but "local" (cloud, firestore, auto, a placeholder) is a refusal (exit 2).
  2. A mock run (--dry-run, the mock server, the API doc) uses only its own throw-away local store: ALTO_STORE is pinned to "local", and
     it gets a private, empty HOME and XDG_CONFIG_HOME in a new temp dir, so nothing under the real ~/.config/alto (site.json,
     accounts.json, sign-in files) is even reachable. ALTO_STORE_DIR and ALTO_BASS_LIVE_GO move with it unless the caller set them.
  3. A live run (Luke's go only) must be given ALTO_STORE=local explicitly: no silent fall-back to the account this computer is signed in
     to. ALTO_NO_NETWORK=1 always gets the private HOME too.
  4. The once-per-session GitHub update check is off for every one of them (none needs it; it is a network call).

Nothing here reads a file. alto/cloud/offline.py is the second wall: in an offline process the account stores are refused at store
selection, account and site files are not opened, and a Bass tool belt with no store refuses (alto/bass/tools.py).
"""
from __future__ import annotations

import os
import sys
import tempfile


class StartRefused(SystemExit):
    pass


def _refuse(msg: str):
    print("refused: " + msg, file=sys.stderr)
    raise StartRefused(2)


def start(tool: str, *, mock: bool, env=None) -> str | None:
    """-> the private home made (or None). Raises StartRefused (exit code 2) when asked for any store but a local one."""
    env = os.environ if env is None else env
    m = env.get("ALTO_STORE", "").strip().lower()
    if m and m != "local":
        _refuse(f"{tool} runs only on its own throw-away local store, never ALTO_STORE={m!r} "
                "(unset it, or set ALTO_STORE=local).")
    if not mock and m != "local":
        _refuse(f"{tool} needs an explicit test store for a live run: set ALTO_STORE=local "
                "(it never falls back to the Alto account this computer is signed in to).")
    env["ALTO_STORE"] = "local"
    env["ALTO_UPDATE_CHECK"] = "off"
    if not (mock or env.get("ALTO_NO_NETWORK") == "1"):
        return None
    home = tempfile.mkdtemp(prefix=f"alto-{tool}-home-")
    env["HOME"] = home
    env["XDG_CONFIG_HOME"] = os.path.join(home, ".config")
    env.setdefault("ALTO_STORE_DIR", os.path.join(home, "store"))
    env.setdefault("ALTO_BASS_LIVE_GO", os.path.join(home, "no-live-go"))
    return home
