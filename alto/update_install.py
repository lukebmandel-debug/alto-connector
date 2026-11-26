"""update_alto: fetch the newest release's extension file and hand it to Claude Desktop, which shows its own Install pop-up.

Luke, 2026-11-26: a user must know, and be able to update, their connector every time they use Claude to change their Alto after a release.
What this does, and only this: asks GitHub for the latest release of the public repo, takes the one file for this computer (macOS Apple silicon,
macOS Intel or Windows), downloads it over https into a fresh temporary folder, checks its SHA-256 against the digest GitHub states for that file,
and opens it with Claude so Claude Desktop's Install pop-up appears. It never installs anything itself: the person clicks Install. A digest that
does not match, or a release without one, stops it with the file deleted.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request

from .build.engine_stamp import is_older, running_version

RELEASES_URL = "https://api.github.com/repos/lukebmandel-debug/alto-connector/releases/latest"
DOWNLOAD_PREFIX = "https://github.com/lukebmandel-debug/alto-connector/releases/download/"
TIMEOUT = 20.0
MAX_BYTES = 400 * 1024 * 1024


class UpdateError(Exception):
    """Something stopped the update; the message says what and what to do."""


def asset_name(system: str | None = None, machine: str | None = None) -> str:
    """The release file for this computer."""
    system = (system or sys.platform).lower()
    machine = (machine or platform.machine()).lower()
    if system.startswith("darwin"):
        return "Alto-macos-arm64.mcpb" if machine in ("arm64", "aarch64") else "Alto-macos-x64.mcpb"
    if system.startswith("win"):
        return "Alto-windows-x64.mcpb"
    raise UpdateError("Automatic update covers macOS and Windows only. Download the newest Alto for this computer from "
                      "https://github.com/lukebmandel-debug/alto-connector/releases/latest and open it.")


def open_command(path: str, system: str | None = None) -> list[str]:
    """The command that opens the file with Claude (never run in tests)."""
    system = (system or sys.platform).lower()
    if system.startswith("darwin"):
        return ["open", "-a", "Claude", path]
    if system.startswith("win"):
        return ["cmd", "/c", "start", "", path]
    raise UpdateError("Automatic update covers macOS and Windows only.")


def _json(url: str):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "alto-connector-update"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read(2_000_000).decode("utf-8"))


def _fetch_release() -> dict:
    return _json(RELEASES_URL)


def _download(url: str, dest: str) -> str:
    """Stream `url` (https, the release's own address) to `dest`; the file's SHA-256 hex."""
    if not url.startswith(DOWNLOAD_PREFIX):
        raise UpdateError("The release's download address is not the Alto repository's. Nothing was downloaded.")
    h = hashlib.sha256()
    n = 0
    req = urllib.request.Request(url, headers={"User-Agent": "alto-connector-update"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            n += len(chunk)
            if n > MAX_BYTES:
                raise UpdateError("The download is larger than expected. It was stopped and deleted.")
            h.update(chunk)
            f.write(chunk)
    return h.hexdigest()


def update_alto() -> dict:
    """Download the newest Alto for this computer, verify it, and open it so Claude Desktop shows its Install pop-up."""
    from .cloud import offline
    from .update_check import _TEST_ALLOW_OFFLINE
    if offline.reason() is not None and not _TEST_ALLOW_OFFLINE:
        return {"ok": False, "error": "offline", "message": "Alto cannot reach GitHub from here, so it cannot update itself. Try again when online."}
    tmp = None
    try:
        name = asset_name()
        rel = _fetch_release()
        latest = str(rel.get("tag_name", "")).lstrip("v")
        mine = running_version()
        if not latest:
            return {"ok": False, "error": "no_release", "message": "GitHub did not name a latest release. Try again in a minute."}
        if not is_older(mine, latest):
            return {"ok": True, "updated": False, "version": mine, "message": f"This Alto ({mine}) is already the newest ({latest})."}
        asset = next((a for a in rel.get("assets") or [] if a.get("name") == name), None)
        if not asset:
            raise UpdateError(f"The latest release ({latest}) has no file named {name}. Nothing was downloaded.")
        digest = str(asset.get("digest") or "")
        if not digest.startswith("sha256:") or len(digest) != 71:
            raise UpdateError(f"GitHub gave no SHA-256 for {name}, so it cannot be verified. Nothing was installed or opened.")
        tmp = tempfile.mkdtemp(prefix="alto-update-")
        path = os.path.join(tmp, name)
        got = _download(str(asset.get("browser_download_url") or ""), path)
        if got != digest[7:]:
            shutil.rmtree(tmp, ignore_errors=True)
            raise UpdateError(f"The downloaded {name} does not match the checksum GitHub states for it. It was deleted and "
                              "not opened. Do not install it; try again later.")
        subprocess.Popen(open_command(path), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)   # noqa: S603
        return {"ok": True, "updated": True, "from": mine, "to": latest, "file": path,
                "message": (f"Alto {latest} is downloaded and checked. Claude should now show an Install pop-up: tell the user to click "
                            "Install (and Replace if asked), then quit and reopen Claude. Nothing is installed until they click.")}
    except UpdateError as e:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
        return {"ok": False, "error": "update_failed", "message": str(e)}
    except Exception as e:                                          # noqa: BLE001
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
        return {"ok": False, "error": "update_failed",
                "message": f"The update could not be fetched ({type(e).__name__}). Download the newest Alto from {DOWNLOAD_PREFIX.rsplit('/download/', 1)[0]}/latest and open it."}
