"""Emit the client-side sync layer with the *publisher's own* Firebase project.

`alto-cloud.js` ships with a placeholder config. It must never ship with a real
one baked in: a published timeline runs this script against whatever project is
compiled into it, so a hardcoded project would collect every reader's account
and data — including readers of other people's timelines — into that one
project's Auth tenant, Firestore and free-tier quota.

The config therefore comes from `ALTO_FIREBASE_CONFIG` at emit time. Unset means
cloud sync is off and highlights stay in localStorage, which is the correct
state for someone who has not set publishing up yet.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

SOURCE = Path(__file__).resolve().parent / "alto-cloud.js"

# The literal `const firebaseConfig = {...};` object in the source file.
_CONFIG_RE = re.compile(
    r"const firebaseConfig = \{.*?\n  \};", re.DOTALL)

# Keys the Firebase web SDK expects. Anything else in the supplied JSON is
# dropped rather than passed through, so a stray value cannot reach the page.
_ALLOWED_KEYS = ("apiKey", "authDomain", "projectId", "storageBucket",
                 "messagingSenderId", "appId", "measurementId")

DISABLED = {"apiKey": "", "authDomain": "", "projectId": "",
            "storageBucket": "", "messagingSenderId": "", "appId": ""}


class CloudConfigError(ValueError):
    pass


def load_config(raw: str | None = None) -> dict:
    """Parse ALTO_FIREBASE_CONFIG. Returns the disabled config when unset."""
    raw = raw if raw is not None else os.environ.get("ALTO_FIREBASE_CONFIG", "")
    if not (raw or "").strip():
        return dict(DISABLED)
    try:
        cfg = json.loads(raw)
    except json.JSONDecodeError as e:
        raise CloudConfigError(
            f"ALTO_FIREBASE_CONFIG is not valid JSON: {e}") from e
    if not isinstance(cfg, dict):
        raise CloudConfigError("ALTO_FIREBASE_CONFIG must be a JSON object")
    missing = [k for k in ("apiKey", "projectId", "appId") if not cfg.get(k)]
    if missing:
        raise CloudConfigError(
            f"ALTO_FIREBASE_CONFIG is missing {', '.join(missing)} — copy the "
            "whole config object from your Firebase console "
            "(Project settings → Your apps → SDK setup and configuration)")
    return {k: str(cfg[k]) for k in _ALLOWED_KEYS if cfg.get(k)}


def emit_cloud_js(config: dict | None = None) -> str:
    """Return alto-cloud.js with `config` spliced in (default: the env one)."""
    cfg = config if config is not None else load_config()
    src = SOURCE.read_text(encoding="utf-8")
    if len(_CONFIG_RE.findall(src)) != 1:
        raise CloudConfigError(
            "alto-cloud.js: expected exactly one firebaseConfig literal — the "
            "file changed shape and this splice needs updating")
    body = ",\n".join(f"    {k}: {json.dumps(v)}" for k, v in cfg.items())
    return _CONFIG_RE.sub(
        lambda _: "const firebaseConfig = {\n" + body + ",\n  };", src, count=1)


def write_cloud_js(dest: Path, config: dict | None = None) -> Path:
    dest.write_text(emit_cloud_js(config), encoding="utf-8")
    return dest
