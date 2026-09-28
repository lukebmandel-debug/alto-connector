"""The user's own Alto site, when Alto set it up for them (set_up_site).

`provision.py` creates a Firebase project in the user's Google account, a web
app, Firestore, Google sign-in, the security rules and the site itself, and
records the result here: ~/.config/alto/site.json (mode 0600, next to the
sign-in session). Nothing in it is secret — the web config is public by design
and ends up in every published page — but it is the user's, so it stays out
of the timeline store they might sync or share.

Everything else in Alto reads its Firebase settings from the environment
(ALTO_FIREBASE_SITE / _PROJECT / _CONFIG / _BIN, ALTO_STORE). `apply()` fills
in whichever of those are EMPTY from this record, once at startup and again
the moment provisioning finishes, so no other code path needs to know whether
a person typed their settings in or Alto made them. Anything set explicitly —
an author's own deploy environment, the extension's advanced settings — wins.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .session import config_dir

READY = "ready"
# Set when apply() filled the Firebase settings from the managed site.
MANAGED_FLAG = "ALTO_SITE_MANAGED"


def path() -> Path:
    return config_dir() / "site.json"


def load() -> dict:
    try:
        d = json.loads(path().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save(d: dict) -> None:
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)
    os.replace(tmp, p)


def ready(d: dict | None = None) -> bool:
    d = load() if d is None else d
    return (d.get("status") == READY and bool(d.get("project"))
            and bool(d.get("site")) and bool((d.get("config") or {}).get("apiKey")))


def _unset(name: str) -> bool:
    v = os.environ.get(name, "").strip()
    # An .mcpb field left blank can arrive as its unexpanded placeholder.
    return not v or v.startswith("${")


def apply(d: dict | None = None, partial: bool = False) -> bool:
    """Fill the empty Firebase settings from the managed site. Returns whether
    a managed site is in use. A half-built site is only applied with
    `partial` — by the provisioner itself, for its own first deploy — so no
    publish ever aims at a project that has no rules or sign-in yet."""
    d = load() if d is None else d
    if not d.get("project") or not (partial or ready(d)):
        return False
    # Alto's own CLI serves any project, managed or typed in.
    if d.get("firebase_bin") and Path(d["firebase_bin"]).exists() \
            and _unset("ALTO_FIREBASE_BIN"):
        os.environ["ALTO_FIREBASE_BIN"] = d["firebase_bin"]
    # The rest only as a coherent set: never pair a typed-in site with a
    # managed project, or the other way round.
    if not (_unset("ALTO_FIREBASE_SITE") and _unset("ALTO_FIREBASE_PROJECT")):
        # A project the user typed in and set_up_site finished: its web
        # config (which they may never have pasted) is the one gap to fill.
        if d.get("adopted") and (d.get("config") or {}).get("apiKey") \
                and _unset("ALTO_FIREBASE_CONFIG"):
            os.environ["ALTO_FIREBASE_CONFIG"] = json.dumps(d["config"])
        return bool(d.get("adopted"))
    fills = {"ALTO_FIREBASE_PROJECT": d.get("project", ""),
             "ALTO_FIREBASE_SITE": d.get("site", "")}
    if (d.get("config") or {}).get("apiKey") and _unset("ALTO_FIREBASE_CONFIG"):
        fills["ALTO_FIREBASE_CONFIG"] = json.dumps(d["config"])
    for k, v in fills.items():
        if v:
            os.environ[k] = v
    # So hand_configured() can tell these from settings the user typed.
    os.environ[MANAGED_FLAG] = "1"
    return True


def hand_configured() -> tuple[str, str] | None:
    """(site, project) typed into the extension's settings or an author's own
    environment, when both are."""
    if _unset("ALTO_FIREBASE_SITE") or _unset("ALTO_FIREBASE_PROJECT") \
            or os.environ.get(MANAGED_FLAG) == "1":
        return None
    return (os.environ["ALTO_FIREBASE_SITE"].strip(),
            os.environ["ALTO_FIREBASE_PROJECT"].strip())
