"""Tell Claude and the user when this Alto extension is behind the latest release.

Checked once per session (a connector process), against the GitHub releases of
the public repo, with a short timeout and the answer cached for the life of the
process. Any failure (offline, rate-limited, odd reply) is silent: the check is
a courtesy and must never get between a person and their work.

The note rides on build and publish results. It is advice, not a gate; the
gate that cannot be argued with is build/engine_stamp.py's refusal to publish
an older page over a newer one.
"""
from __future__ import annotations

import json
import os
import threading
import urllib.request

from .build.engine_stamp import UPDATE_HOW, is_older, parse_version, running_version

RELEASES_URL = "https://api.github.com/repos/lukebmandel-debug/alto-connector/releases/latest"
TIMEOUT = 3.0

_lock = threading.Lock()
_started = False
_done = threading.Event()
_latest = ""


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
    global _latest
    try:
        _latest = _fetch_latest()
    finally:
        _done.set()


def start() -> None:
    """Begin the once-per-session check in the background (idempotent)."""
    global _started
    if os.environ.get("ALTO_UPDATE_CHECK") == "off":
        return
    with _lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_run, daemon=True, name="alto-update-check").start()


def latest_version() -> str:
    start()
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
    global _started, _latest
    with _lock:
        _started, _latest = False, ""
        _done.clear()
