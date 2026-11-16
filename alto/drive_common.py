"""What Bass "Add from Drive" and manual edit's "Add from Drive" share, in one neutral module: it imports NOTHING from alto.bass and nothing
from anthropic or httpx2 (tests/test_drive_common.py checks this in a subprocess), so a build without the SDK can use it.

  * SCOPE: drive.file ONLY (Google lets the app see just the files the person picks). Hard-coded here and in the picker page; no message can widen it.
  * _ID: what a Drive file id looks like; anything else is dropped.
  * DriveConfig: the three PUBLIC Picker identifiers from the environment (IT sets them; ORG/it/bass-drive-deploy.md). Any of the three absent =
    the feature is off, the control is hidden, and the page is byte-identical to a build without it.
  * Manual edit's chip (design (a), a REFERENCE only): the page keeps a file's id and name, builds the link itself from a checked id, and never
    reads the file. parse_drive_link / clean_name / drive_url / strip_unshared are its pure helpers; the share, offline and preview builds call
    strip_unshared so a chip the owner has not switched on for share links leaves no id in anything that goes to other people.
"""
from __future__ import annotations

import os
import re

SCOPE = "https://www.googleapis.com/auth/drive.file"
_ID = re.compile(r"^[A-Za-z0-9_-]{10,100}\Z")          # \Z, not $: "$" lets one trailing newline through
MAX_NAME = 200
MAX_PICK = 5                                       # files in one pick (the Picker's own cap in the popup)
REF_MIMES = ("application/vnd.google-apps.document", "application/vnd.google-apps.spreadsheet", "application/vnd.google-apps.presentation",
             "application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.openxmlformats-officedocument.presentationml.presentation",
             "text/plain", "text/csv", "image/png", "image/jpeg")


class DriveConfig:
    """The Picker's public identifiers, from the server's environment. Absent (any of the three) = the feature is off and the page hides its
    button. They are PUBLIC identifiers by design (they ride in the page); the client SECRET is never needed (the token is the implicit kind)."""

    ENV = ("ALTO_DRIVE_CLIENT_ID", "ALTO_DRIVE_API_KEY", "ALTO_DRIVE_APP_ID")           # names only; the values are IT's (ORG/it/bass-drive-deploy.md)

    def __init__(self, client_id: str = "", api_key: str = "", app_id: str = ""):
        self.client_id, self.api_key, self.app_id = client_id.strip(), api_key.strip(), app_id.strip()

    @classmethod
    def from_env(cls, env=None):
        e = os.environ if env is None else env
        return cls(*(str(e.get(n, "") or "") for n in cls.ENV))

    def missing(self) -> list:
        """The NAMES of the environment variables that are not set (never a value)."""
        return [n for n, v in zip(self.ENV, (self.client_id, self.api_key, self.app_id)) if not v]

    @property
    def partial(self) -> bool:
        """Some but not all set: a half-finished deploy. The feature stays off and the operator is told which are missing (fail closed, loudly)."""
        return 0 < len(self.missing()) < len(self.ENV)

    def problem(self) -> str:
        m = self.missing()
        return ("Add from Drive is off: missing environment variable%s %s. Set all of %s, or none." % ("s" if len(m) > 1 else "", ", ".join(m), ", ".join(self.ENV))) if m else ""

    @property
    def available(self) -> bool:
        return bool(self.client_id and self.api_key and self.app_id)

    def public(self) -> dict:
        if not self.available:
            return {"ok": True, "status": "ok", "available": False}
        return {"ok": True, "status": "ok", "available": True, "client_id": self.client_id, "api_key": self.api_key, "app_id": self.app_id, "scope": SCOPE}


def enabled(env=None) -> bool:
    """True only when all three public identifiers are set. Everything manual edit adds to a page is gated on this."""
    return DriveConfig.from_env(env).available


def drive_url(drive_id) -> "str | None":
    """The address a chip opens: BUILT from a checked id, never copied from anywhere (so no javascript: or look-alike host can ride in)."""
    return "https://drive.google.com/file/d/%s/view" % drive_id if isinstance(drive_id, str) and _ID.match(drive_id) else None


def clean_name(s, default: str = "Drive file") -> str:
    """A chip's name: control characters and < > " removed, capped at MAX_NAME. Always set as text, never as markup."""
    t = re.sub(r'[\x00-\x1f\x7f<>"]', "", str(s or "")).strip()[:MAX_NAME].strip()
    return t or default


_LINKS = (
    re.compile(r"^https://docs\.google\.com/(?:document|spreadsheets|presentation)/d/([A-Za-z0-9_-]{10,100})(?:[/?#].*)?$"),
    re.compile(r"^https://drive\.google\.com/file/d/([A-Za-z0-9_-]{10,100})(?:[/?#].*)?$"),
    re.compile(r"^https://drive\.google\.com/(?:open|uc)\?(?:[^#\s]*&)?id=([A-Za-z0-9_-]{10,100})(?:[&#].*)?$"),
)


def parse_drive_link(s) -> "str | None":
    """The file id in a pasted Drive link (docs.google.com/{document,spreadsheets,presentation}/d/ID, drive.google.com/file/d/ID, or ?id=ID), or
    None for anything else. https only; the host must be exactly docs.google.com or drive.google.com. manual_edit.py carries the same patterns."""
    t = str(s or "").strip()
    if not t or len(t) > 2000 or re.search(r"[\x00-\x20<>\"']", t):
        return None
    for r in _LINKS:
        m = r.match(t)
        if m:
            return m.group(1)
    return None


# What the page writes for a chip:
#   <a class="note-link" data-gdrive="gd-xxxxxxxx" data-gdrive-id="ID" data-gdrive-share="0|1" href="https://drive.google.com/file/d/ID/view">name</a>
# A chip is a reference. Share links, the offline copy and the preview drop every chip whose share flag is not "1": its words stay, its link goes.
GD_KEY = re.compile(r"^gd-[a-z0-9]{6,12}\Z")
# The page carries chips both as markup and inside its JSON data (js_json writes "<" as \u003c and quotes as \"), so both spellings are matched.
_LT = r"(?:<|\\u003[cC])"
_Q = r'\\?"'
_UNSHARED = re.compile(_LT + r"a\b[^>]*?\bdata-gdrive(?:-id)?=" + _Q + r"[^\"\\]*" + _Q + r"[^>]*>((?:(?!" + _LT + r"/a>)[\s\S])*)" + _LT + r"/a>")
_FLAGGED = re.compile(r"\bdata-gdrive-share=" + _Q + "1" + _Q)


# the ids of chips NOT flagged for sharing ride in the page's _ALTO_LOCAL block as "drive":{"gd-…":"ID"} (detail_extras.local_sources), last key
_DRIVE_MAP = re.compile(r",?\s*" + _Q + r"drive" + _Q + r"\s*:\s*\{\s*" + _Q + r"gd-[a-z0-9]{6,12}" + _Q + r"[^{}]*\}")


def strip_unshared(page_html: str) -> str:
    """The page with every Drive chip not flagged for sharing reduced to its words, and the id map of the unflagged ones removed. A flagged chip is kept.
    (A share snapshot needs neither: the build writes an unflagged chip with no id and its map in a block shares empty. This is for the offline copy
    and the preview, and a second wall behind the share.)"""
    if not page_html or ("data-gdrive" not in page_html and "drive" not in page_html):
        return page_html
    page_html = _DRIVE_MAP.sub("", page_html) if "alto-local-src" in page_html else page_html
    if "data-gdrive" not in page_html:
        return page_html

    def one(m):
        tag = m.group(0)[:m.group(0).index(">") + 1]
        return m.group(0) if _FLAGGED.search(tag) else m.group(1)
    return _UNSHARED.sub(one, page_html)
