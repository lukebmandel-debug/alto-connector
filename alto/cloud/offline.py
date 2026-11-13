"""No-network processes never read a real sign-in (incident 11 Nov, notes-bass-review-1111.md).

A process is OFFLINE when ALTO_NO_NETWORK=1 is set or the Bass network guard (alto/bass/net_guard.py,
installed by the Bass mock) is in place. Such a process is a test or a mock run: it has no business with
anyone's real account. In it:

  * the cloud / firestore store, an account-scoped call and the default 'auto' choice are REFUSED at store
    selection (mcp_server.store_mode / get_store), before site.json, accounts.json, a session-*.json sign-in
    file or Session._load() is touched. Only an explicit ALTO_STORE=local, or a store handed in with
    set_store(), works;
  * as a second wall, site.json / accounts.json / session-*.json reads answer "nothing there" without
    opening the file.

The one exception is a config directory a TEST HARNESS registered with allow_test_root() (tests/conftest.py
registers pytest's own temp root, where every test's XDG_CONFIG_HOME lives). Nothing but test code calls
it, so an ad-hoc script never gets it. A normal app process (no ALTO_NO_NETWORK, no guard) is unchanged:
every function here answers "allowed" without looking at any file.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_TEST_ROOTS: list[Path] = []


class CloudStoreRefused(RuntimeError):
    """Raised at store selection in an offline process that named no test store."""


def reason() -> str | None:
    """Why this process is offline, or None for a normal app process."""
    if os.environ.get("ALTO_NO_NETWORK") == "1":
        return "ALTO_NO_NETWORK=1"
    ng = sys.modules.get("alto.bass.net_guard")          # never imported here: the app itself does not load Bass
    if ng is not None and getattr(ng, "_installed", False):
        return "the Bass network guard is installed"
    return None


def allow_test_root(path) -> None:
    """Test harnesses only: config dirs under `path` are the test's own fakes and may be used offline."""
    p = Path(path).resolve()
    if p not in _TEST_ROOTS:
        _TEST_ROOTS.append(p)


def _under_test_root(path) -> bool:
    try:
        p = Path(path).resolve()
    except (OSError, RuntimeError):
        return False
    return any(p == r or r in p.parents for r in _TEST_ROOTS)


def may_read(path) -> bool:
    """May this process read the sign-in / site file at `path`? Always yes outside an offline process."""
    return reason() is None or _under_test_root(path)


def blocks(config_dir) -> bool:
    """True when this process is offline and `config_dir` is not a registered test fake."""
    return reason() is not None and not _under_test_root(config_dir)


def refuse(what: str, config_dir) -> None:
    """Raise CloudStoreRefused when an offline process asks for `what` (a store needing an account) and its
    config dir is not a registered test fake. Reads only the environment, never a file."""
    why = reason()
    if why is None or _under_test_root(config_dir):
        return
    raise CloudStoreRefused(
        f"refused: {what} needs a real Alto account, and this process is offline ({why}). "
        "Set ALTO_STORE=local (or hand a test store to set_store()) for a test or mock run. "
        "No sign-in or site file was read.")
