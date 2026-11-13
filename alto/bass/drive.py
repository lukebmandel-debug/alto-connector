"""Bass "Add from Drive" (CoS-b C-1104-121200; Luke L-1102-220150 "Yes, tie to Bass"). MOCK ONLY until Luke's go: nothing here calls Google by itself,
the transport is injected, and tests never reach a real host.

What it is: the student picks files with Google's Picker (scope drive.file ONLY: Google lets the app see just the files that student picks,
never the rest of their Drive). The page sends the server ONLY the picked file ids; the server fetches each one with that student's token, turns
it into text through the SAME path an upload takes (extract.Extractor: size caps before parsing, child process, deadline, fail closed) and keeps
it as an ordinary Library document under that uid (documents.Library.add_file: same caps, same silos, same 7-day deletion rules).

Tokens (the part that must not leak):
  * Picker needs a token in the page, so the page holds one in a JS variable only (never stored, never in a URL or the DOM) and hands it to the
    server ONCE in a POST body (op "connect"). The server checks it with Google (tokeninfo, POST body): scope exactly drive.file, issued to OUR
    client id, still valid; anything else is refused and revoked. It is then kept server-side only, in bass_drive/<uid> (a server-only Firestore
    doc: the page rules match only users/ and shares/), with its expiry (<= 1 hour: the implicit/online token). NO refresh token exists or is
    kept: when it ends the student chooses again (Google asks nothing new).
  * Never in a URL (Drive calls use an Authorization header; tokeninfo and revoke take it in a POST body), never in a log or an error string
    (nothing in this file logs; every failure is a code from DRIVE_MESSAGES), never in the saved conversation (it is not in any action).
  * One token, one uid: bass_drive_tok/<sha256> names the uid that registered it; a second uid presenting the same token is refused.
  * Revoked at Google (POST oauth2.googleapis.com/revoke) and deleted on disconnect (sign-out) and on account deletion (erase_account).
Egress: net_guard.check_google_url (www.googleapis.com / oauth2.googleapis.com, https, no userinfo); a redirect is a failure, never followed.
Closed system: a fetched file is DATA. Its text is stored like an upload and reaches Bass only inside the Documents block; instructions inside it
are not instructions (the Documents rules, ORG notes/closed-system.md).
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import urllib.error
import urllib.request
from urllib.parse import quote, urlencode

from .documents import DocsError, Library, refusal as docs_refusal
from .net_guard import RealNetworkBlocked, check_google_url

log = logging.getLogger("bass.beta")
SCOPE = "https://www.googleapis.com/auth/drive.file"
MAX_IDS = 5                                    # files per request
TOKEN_MAX_S = 3600                             # a token is never kept longer than an hour, whatever Google says
_ID = re.compile(r"^[A-Za-z0-9_-]{10,100}$")
_TOKEN = re.compile(r"^[A-Za-z0-9._~+/=-]{20,2048}$")
GDOC = "application/vnd.google-apps.document"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
KINDS = {GDOC: ("export", ".txt"), "text/plain": ("media", ".txt"), "application/pdf": ("media", ".pdf"), DOCX: ("media", ".docx")}   # the mime allow-list

MESSAGES = {
    "drive_off": "Add from Drive isn't available right now.",
    "drive_not_connected": "Connect Google Drive first, then choose your files.",
    "drive_expired": "Your Google Drive connection ended. Choose your files again.",
    "drive_bad_token": "Bass could not connect to Google Drive. Please try again.",
    "drive_not_found": "Bass could not open that file from Drive. Choose it again.",
    "drive_unsupported": "Bass can read Google Docs, PDF, Word (.docx) and plain-text files from Drive.",
    "drive_unavailable": "Google Drive didn't answer. Please try again in a moment.",
    "drive_bad_request": "Bass could not read that request.",
}


def refusal(code: str) -> dict:
    return {"ok": False, "status": "refused", "code": code, "message": MESSAGES.get(code, MESSAGES["drive_bad_request"]), "retryable": code == "drive_unavailable"}


class DriveError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


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


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class Transport:
    """The one place a Google call leaves the process. request() -> (status, data) with data capped at max_bytes (more = DriveError, never a
    partial read). check_google_url first; a redirect comes back as its 3xx status and is never followed. Tests replace this class."""

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    def request(self, method: str, url: str, headers: dict | None = None, body: bytes | None = None, max_bytes: int = 1_000_000):
        check_google_url(url)
        req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
        opener = urllib.request.build_opener(_NoRedirect())
        try:
            resp = opener.open(req, timeout=self.timeout)
            status = resp.status
        except urllib.error.HTTPError as e:
            resp, status = e, e.code
        except Exception:
            raise DriveError("drive_unavailable")
        try:
            data = resp.read(max_bytes + 1)
        except Exception:
            raise DriveError("drive_unavailable")
        if len(data) > max_bytes:
            raise DriveError("upload_too_big")
        return status, data


def _ok_json(status, data):
    if status != 200:
        return None
    try:
        out = json.loads(data.decode("utf-8"))
    except Exception:
        return None
    return out if isinstance(out, dict) else None


def _clean_name(title, ext: str) -> str:
    t = re.sub(r"[\x00-\x1f\x7f/\\]", " ", str(title or ""))
    t = " ".join(t.split())
    t = re.sub(r"\.(pdf|docx|txt|md|markdown|csv|text)$", "", t, flags=re.I)         # the extension comes from what Bass actually read
    return (t[:100].strip() or "Drive file") + ext


class DriveService:
    OPS = ("config", "connect", "add", "disconnect")

    def __init__(self, store, cfg, clock, library: Library, config: DriveConfig | None = None, transport=None):
        self.store, self.cfg, self.clock, self.library = store, cfg, clock, library
        self.config = config or DriveConfig.from_env()
        self.transport = transport or Transport()
        if self.config.partial:
            log.error(self.config.problem())                         # names only; the feature stays off (every op but config answers drive_off)

    # -- keys ------------------------------------------------------------------------------------------------------
    @staticmethod
    def _key(uid: str) -> str:
        if not isinstance(uid, str) or not re.match(r"^[A-Za-z0-9_-]{1,128}$", uid):
            raise DriveError("drive_bad_request")
        return "bass_drive/" + uid

    @staticmethod
    def _tkey(token: str) -> str:
        return "bass_drive_tok/" + hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _now(self):
        return self.clock()

    # -- google ----------------------------------------------------------------------------------------------------
    def _call(self, method, url, token=None, form=None, max_bytes=1_000_000):
        h = {"Accept": "application/json"}
        body = None
        if token:
            h["Authorization"] = "Bearer " + token
        if form is not None:
            body = urlencode(form).encode("ascii")
            h["Content-Type"] = "application/x-www-form-urlencoded"
        try:
            return self.transport.request(method, url, headers=h, body=body, max_bytes=max_bytes)
        except RealNetworkBlocked:
            raise DriveError("drive_unavailable")

    def _revoke(self, token: str) -> None:
        try:
            self._call("POST", "https://oauth2.googleapis.com/revoke", form={"token": token}, max_bytes=65_536)
        except Exception:
            pass                                                     # best effort: the record is deleted either way, and the token ends in an hour

    # -- ops -------------------------------------------------------------------------------------------------------
    def handle(self, uid: str, args) -> dict:
        if not isinstance(args, dict) or args.get("op") not in self.OPS:
            return refusal("drive_bad_request")
        op = args["op"]
        if op == "config":
            return self.config.public()
        if not self.config.available:
            return refusal("drive_off")
        try:
            if op == "connect":
                if set(args) - {"op", "token"}:
                    return refusal("drive_bad_request")
                return self.connect(uid, args.get("token"))
            if op == "add":
                if set(args) - {"op", "scope_id", "file_ids"}:
                    return refusal("drive_bad_request")
                return self.add(uid, args.get("scope_id"), args.get("file_ids"))
            return self.disconnect(uid)
        except DriveError as e:
            return refusal(e.code)
        except DocsError as e:
            return docs_refusal(e.code)

    def connect(self, uid: str, token) -> dict:
        key = self._key(uid)
        if not isinstance(token, str) or not _TOKEN.match(token):
            raise DriveError("drive_bad_token")
        status, data = self._call("POST", "https://oauth2.googleapis.com/tokeninfo", form={"access_token": token}, max_bytes=65_536)
        info = _ok_json(status, data)
        scopes = set(str((info or {}).get("scope") or "").split())
        try:
            left = int(str((info or {}).get("expires_in") or "0"))
        except ValueError:
            left = 0
        if not info or scopes != {SCOPE} or (info.get("aud") != self.config.client_id and info.get("azp") != self.config.client_id) or left < 30:
            if info is not None:
                self._revoke(token)                                  # a token we refuse (wider scope, someone else's app) is not left alive
            raise DriveError("drive_bad_token")
        exp = self._now().timestamp() + min(left, TOKEN_MAX_S)
        tk, old = self._tkey(token), {}

        def work(txn):
            other = txn.get(tk)
            if isinstance(other, dict) and other.get("uid") != uid:
                raise DriveError("drive_bad_token")                  # one token, one uid
            cur = txn.get(key)
            old.update(cur if isinstance(cur, dict) else {})
            if old.get("token") and old["token"] != token:
                txn.delete(self._tkey(old["token"]))
            txn.put(key, {"token": token, "exp": exp})
            txn.put(tk, {"uid": uid})
        self.store.run_transaction(work)
        if old.get("token") and old["token"] != token:
            self._revoke(old["token"])
        return {"ok": True, "status": "ok", "connected": True, "expires_in": int(min(left, TOKEN_MAX_S))}

    def _token(self, uid: str) -> str:
        rec = self.store.get(self._key(uid))
        if not isinstance(rec, dict) or not isinstance(rec.get("token"), str):
            raise DriveError("drive_not_connected")
        if float(rec.get("exp") or 0) <= self._now().timestamp():
            self._drop(uid, rec["token"])
            raise DriveError("drive_expired")
        return rec["token"]

    def _drop(self, uid: str, token: str | None) -> None:
        def work(txn):
            txn.delete(self._key(uid))
            if token:
                txn.delete(self._tkey(token))
        self.store.run_transaction(work)

    def add(self, uid: str, scope_id, file_ids) -> dict:
        self._key(uid)
        if not isinstance(file_ids, list) or not 1 <= len(file_ids) <= MAX_IDS or len(set(map(str, file_ids))) != len(file_ids) \
                or not all(isinstance(i, str) and _ID.match(i) for i in file_ids):
            raise DriveError("drive_bad_request")
        token = self._token(uid)
        lib = self.library._load(uid)
        self.library._scope(lib, scope_id)                          # an unknown scope is refused BEFORE anything leaves the server
        added, first = [], None
        for fid in file_ids:
            try:
                added.append(self._one(uid, token, scope_id, fid))
            except DriveError as e:
                if e.code == "drive_expired":
                    raise
                first = first or ("drive", e.code)
            except DocsError as e:
                first = first or ("docs", e.code)
        if not added:
            kind, code = first
            if kind == "docs":
                raise DocsError(code)
            raise DriveError(code)
        return {"ok": True, "status": "ok", "files": [a["file"] for a in added], "failed": len(file_ids) - len(added)}

    def _one(self, uid: str, token: str, scope_id, fid: str) -> dict:
        cap = self.cfg.upload_max_file_bytes
        st, data = self._call("GET", "https://www.googleapis.com/drive/v3/files/%s?fields=id,name,mimeType,size,trashed&supportsAllDrives=false" % quote(fid, safe=""),
                              token, max_bytes=65_536)
        if st == 401:
            self._drop(uid, token)
            raise DriveError("drive_expired")
        if st in (403, 404):
            raise DriveError("drive_not_found")                      # Google hides what drive.file was not granted: a forged id looks like this
        meta = _ok_json(st, data)
        if meta is None:
            raise DriveError("drive_unavailable")
        if meta.get("id") != fid or meta.get("trashed") is True:
            raise DriveError("drive_not_found")
        kind = KINDS.get(str(meta.get("mimeType") or ""))
        if kind is None:
            raise DriveError("drive_unsupported")
        how, ext = kind
        try:
            if how == "media" and int(str(meta.get("size") or "0")) > cap:
                raise DriveError("upload_too_big")
        except ValueError:
            raise DriveError("drive_unavailable")
        base = "https://www.googleapis.com/drive/v3/files/%s" % quote(fid, safe="")
        url = base + "/export?mimeType=text%2Fplain" if how == "export" else base + "?alt=media&supportsAllDrives=false"
        st, body = self._call("GET", url, token, max_bytes=cap)
        if st == 401:
            self._drop(uid, token)
            raise DriveError("drive_expired")
        if st in (403, 404):
            raise DriveError("drive_not_found")
        if st != 200:
            raise DriveError("drive_unavailable")
        name = _clean_name(meta.get("name"), ext)
        if ext == ".txt":
            try:
                text = body.decode("utf-8")
            except UnicodeDecodeError:
                raise DriveError("drive_unsupported")                # "plain text" that is not text
            if "\x00" in text:
                raise DriveError("drive_unsupported")
            return self.library.add_file(uid, scope_id, name, text=text)
        return self.library.add_file(uid, scope_id, name, file_b64=base64.b64encode(body).decode("ascii"))

    def disconnect(self, uid: str) -> dict:
        key = self._key(uid)
        rec = self.store.get(key)
        tok = rec.get("token") if isinstance(rec, dict) else None
        if isinstance(tok, str):
            self._drop(uid, tok)
            self._revoke(tok)
        return {"ok": True, "status": "ok", "connected": False}

    def erase_account(self, uid: str) -> bool:
        """The account is being deleted (IT's path, next to Library.erase_account): the token is revoked and no record of it or of the account's
        Drive connection is left. The fetched files are ordinary Library documents and go with Library.erase_account. -> a connection was there."""
        was = isinstance(self.store.get(self._key(uid)), dict)
        self.disconnect(uid)
        return was
