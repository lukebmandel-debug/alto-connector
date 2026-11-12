"""Holographic's animated backgrounds as looping video (Luke, 2026-11-05: "its like a lofi background music animation that repeats, no one minds. I think even 10 second loop is
fine, just make transition smooth").

The CSS animations (holo_anim.py) cost the compositor: a headed WebKit reading put WindowServer at 18-21% of a core on Neon rain, Amber haze, Targeting and Signal rain, against 0.5-2% on a
still page. A background that has a clip here is played as a muted, looping, inline H.264 video in the scene box instead, which the Mac's hardware decoder plays for next to nothing.

  alto/assets/holo_video/<name>.mp4   the clip: the background's picture AND its animation, 16:10 (the picture's own proportions, `cover` in the scene box), 30 fps, a loop whose every
                                      layer's period divides its length, so the last frame runs straight into the first
  /hvid/<name>-<10 hex of sha256>.mp4 where the site serves it (content-hash named, immutable, off the page: the page holds no video and no path; the hosted Holographic script names it)

Made by docs/holo-video/render_frames.py (deterministic frames from the CSS animation, every animation set to a time and screenshotted) and docs/holo-video/encode.swift (AVAssetWriter,
H.264 High; this Mac has no ffmpeg). A background without a clip keeps its CSS animation; a clip that cannot play falls back to the CSS layer (holo_anim.py havid).
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

VIDEO_DIR = Path(__file__).resolve().parent.parent / "assets" / "holo_video"
FOLDER = "hvid"
NAME_RE = re.compile(r"^[a-z]+(-[a-z]+)*-[0-9a-f]{10}\.mp4$")
_SRC_RE = re.compile(r"^[a-z]+(-[a-z]+)*\.mp4$")
CLIPS = {"neon": "neon-rain"}          # animation kind (holo_anim.IDS values) -> the clip's file stem


def _hashed(p: Path) -> str:
    return p.stem + "-" + hashlib.sha256(p.read_bytes()).hexdigest()[:10] + p.suffix


def files() -> list:
    """[(published name, bytes)] of every clip in alto/assets/holo_video."""
    if not VIDEO_DIR.is_dir():
        return []
    return [(_hashed(p), p.read_bytes()) for p in sorted(VIDEO_DIR.iterdir()) if p.is_file() and _SRC_RE.match(p.name)]


def paths() -> dict:
    """{animation kind: "/hvid/<name>"} for each clip that exists; a kind with no clip file keeps its CSS animation."""
    out = {}
    for kind, stem in CLIPS.items():
        p = VIDEO_DIR / (stem + ".mp4")
        if p.is_file():
            out[kind] = "/" + FOLDER + "/" + _hashed(p)
    return out
