"""Tell Claude and the user when this Alto extension is behind the latest release.

Checked on the first call of a session (a connector process) and again after 6 hours, against the GitHub releases of
the public repo, with a short timeout and the answer cached for 6 hours. Any failure (offline, rate-limited, odd reply) is silent: the check is
a courtesy and must never get between a person and their work.

The note rides on build and publish results. It is advice, not a gate; the
gate that cannot be argued with is build/engine_stamp.py's refusal to publish
an older page over a newer one.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.request

from .build.engine_stamp import UPDATE_HOW, is_older, parse_version, running_version

RELEASES_URL = "https://api.github.com/repos/lukebmandel-debug/alto-connector/releases/latest"
TIMEOUT = 3.0
TTL = 6 * 3600.0          # how long a fetched answer is trusted before the next call asks again
_clock = time.monotonic   # tests swap in a fake clock

_lock = threading.Lock()
# Test-only: tests/test_stale_guard.py sets this (with its GitHub fetch stubbed) so the check runs even in an offline process, e.g. after a
# Bass suite has installed the network guard. Nothing outside the tests sets it; offline app and Bass processes stay without the check.
_TEST_ALLOW_OFFLINE = False
_started = False
_done = threading.Event()
_latest = ""
_fetched_at = 0.0
_refreshing = False


def _fetch_latest() -> str:
    """The latest release number from GitHub, '' on any failure."""
    try:
        req = urllib.request.Request(RELEASES_URL, headers={
            "Accept": "application/vnd.github+json", "User-Agent": "alto-connector-update-check"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            tag = (json.loads(r.read(200000).decode("utf-8")) or {}).get("tag_name", "")
        return tag.lstrip("v") if parse_version(tag) else ""
    except Exception:                                   # noqa: BLE001 — a courtesy check never raises
        return ""


def _run() -> None:
    global _latest, _fetched_at, _refreshing
    try:
        got = _fetch_latest()
        if got or not _latest:                  # a failed re-check keeps the older answer
            _latest = got
        _fetched_at = _clock()
    finally:
        _refreshing = False
        _done.set()


def start() -> None:
    """Begin the once-per-session check in the background (idempotent)."""
    global _started
    if os.environ.get("ALTO_UPDATE_CHECK") == "off":
        return
    from .cloud import offline
    if offline.reason() is not None and not _TEST_ALLOW_OFFLINE:   # ALTO_NO_NETWORK=1 or the Bass mock's guard: never a GitHub call
        return
    with _lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_run, daemon=True, name="alto-update-check").start()


def latest_version() -> str:
    global _refreshing
    start()
    if os.environ.get("ALTO_UPDATE_CHECK") != "off" and _started:
        with _lock:
            stale = _fetched_at and not _refreshing and _clock() - _fetched_at >= TTL
            if stale:
                _refreshing = True
                _done.clear()
        if stale:
            threading.Thread(target=_run, daemon=True, name="alto-update-recheck").start()
    _done.wait(TIMEOUT + 1)
    return _latest


def update_note() -> str:
    """The plain warning when the running extension is older than the latest
    release; '' when it is current, newer, or the check could not be made."""
    try:
        if os.environ.get("ALTO_UPDATE_CHECK") == "off":
            return ""
        mine, latest = running_version(), latest_version()
        if latest and is_older(mine, latest):
            return (f"This Alto extension is {mine}, the latest is {latest}. "
                    f"Update it before editing pages: {UPDATE_HOW}.")
    except Exception:                                   # noqa: BLE001
        pass
    return ""


def with_update_note(result):
    """Put the out-of-date warning first in a build or publish result."""
    note = update_note()
    if note and isinstance(result, dict):
        return {"update_alto": note,
                "update_alto_instruction": ("Tell the user this, in these words, before anything else, "
                                            "and again if they go on editing pages."),
                **result}
    return result


def reset_for_tests() -> None:
    global _started, _latest, _fetched_at, _refreshing
    with _lock:
        _started, _latest, _fetched_at, _refreshing = False, "", 0.0, False
        _done.clear()
