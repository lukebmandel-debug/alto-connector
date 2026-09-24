"""Sign the local connector in as the user's own Firebase account.

The connector runs on the user's computer and holds no admin credentials, so it
reaches their Firestore the same way their browser does: as them, through the
security rules (users/{uid}/** is readable and writable by that uid only).

Signing in happens on the user's own site, at /connect/, because that page
already speaks Google sign-in for this Firebase project:

  1. `start()` opens a one-shot listener on 127.0.0.1 with a random `state` and
     opens https://{site}.web.app/connect/?port=N&state=S in the browser.
  2. The page signs in with Google and navigates the whole window to
     http://127.0.0.1:N/cb#state=S&rt=<refresh token>. A fragment never reaches
     a server log, and a top-level navigation needs no change to the site's CSP.
  3. The listener's page posts the fragment back to itself (same origin), the
     state is checked, and the refresh token is exchanged at Google's secure
     token endpoint — which both proves it and yields the uid.

The refresh token is kept in ~/.config/alto/, mode 0600, outside the timeline
store (which a user may sync or share). Stdlib only: the connector ships with
`mcp` as its sole dependency.
"""
from __future__ import annotations

import html
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from . import load_config

TOKEN_URL = "https://securetoken.googleapis.com/v1/token?key={key}"


class SignInRequired(RuntimeError):
    """Raised by cloud-backed tools when the connector is not signed in."""


class CloudError(RuntimeError):
    pass


def _http(method: str, url: str, body: bytes | None = None,
          headers: dict | None = None, timeout: int = 30):
    """(status, parsed JSON or None). Swapped out by tests."""
    req = urllib.request.Request(url, data=body, method=method,
                                 headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw) if raw else None
        except ValueError:
            return e.code, None


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "alto"


_CB_PAGE = """<!doctype html><meta charset="utf-8"><title>Alto</title>
<style>body{font:15px -apple-system,BlinkMacSystemFont,sans-serif;display:flex;
align-items:center;justify-content:center;height:90vh;color:#333}</style>
<p id="m">Connecting Alto&hellip;</p>
<script>
var h = location.hash.slice(1);
history.replaceState(null, '', '/cb');
fetch('/cb', {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'}, body:h})
  .then(function(r){ return r.text(); })
  .then(function(t){ document.getElementById('m').textContent = t; })
  .catch(function(){ document.getElementById('m').textContent = 'Something went wrong. Go back to Claude and try again.'; });
</script>"""


class Session:
    """The signed-in account for one Firebase project."""

    def __init__(self, config: dict | None = None, http=None,
                 path: Path | None = None, opener=None):
        self.config = config if config is not None else load_config()
        self.project = self.config.get("projectId", "")
        self.api_key = self.config.get("apiKey", "")
        self.http = http or _http
        self.path = path or (config_dir() / f"session-{self.project or 'none'}.json")
        self.opener = opener or webbrowser.open
        self._id_token = ""
        self._id_exp = 0.0
        self._pending: dict | None = None
        self._lock = threading.Lock()
        self.data = self._load()

    # ── stored session ───────────────────────────────────────────────────────
    def _load(self) -> dict:
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) and d.get("refresh_token") else {}
        except (OSError, ValueError):
            return {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.data, f)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)

    def forget(self) -> None:
        self.data, self._id_token, self._id_exp = {}, "", 0.0
        try:
            self.path.unlink()
        except OSError:
            pass

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.project)

    @property
    def signed_in(self) -> bool:
        return bool(self.data.get("refresh_token") and self.data.get("uid"))

    @property
    def uid(self) -> str:
        if not self.signed_in:
            raise SignInRequired(
                "Alto is not signed in on this computer yet. Call the sign_in "
                "tool: it opens the user's Alto site so they can continue with "
                "Google, once. Their projects then load from their account.")
        return self.data["uid"]

    @property
    def email(self) -> str:
        return self.data.get("email", "")

    # ── tokens ───────────────────────────────────────────────────────────────
    def _exchange(self, refresh_token: str) -> dict:
        body = urllib.parse.urlencode({"grant_type": "refresh_token",
                                       "refresh_token": refresh_token}).encode()
        status, js = self.http(
            "POST", TOKEN_URL.format(key=urllib.parse.quote(self.api_key)), body,
            {"Content-Type": "application/x-www-form-urlencoded"})
        if status != 200 or not js or not js.get("id_token"):
            msg = ((js or {}).get("error") or {}).get("message", "") if isinstance(
                (js or {}).get("error"), dict) else ""
            raise SignInRequired(
                "The saved Alto sign-in is no longer valid"
                + (f" ({msg})" if msg else "")
                + ". Call the sign_in tool to sign in again.")
        return js

    def id_token(self, force: bool = False) -> str:
        with self._lock:
            if not self.signed_in:
                self.uid  # raises SignInRequired with the instructions
            if force or not self._id_token or time.time() > self._id_exp - 120:
                js = self._exchange(self.data["refresh_token"])
                self._id_token = js["id_token"]
                self._id_exp = time.time() + int(js.get("expires_in", 3600))
                if js.get("refresh_token") and js["refresh_token"] != self.data["refresh_token"]:
                    self.data["refresh_token"] = js["refresh_token"]
                    self._save()
            return self._id_token

    def _accept(self, refresh_token: str) -> None:
        js = self._exchange(refresh_token)
        claims = _claims(js["id_token"])
        uid = js.get("user_id") or claims.get("user_id") or claims.get("sub")
        if not uid:
            raise CloudError("sign-in returned no account id")
        self.data = {"refresh_token": js.get("refresh_token") or refresh_token,
                     "uid": uid, "email": claims.get("email", ""),
                     "project": self.project,
                     "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        self._id_token = js["id_token"]
        self._id_exp = time.time() + int(js.get("expires_in", 3600))
        self._save()

    # ── browser sign-in ──────────────────────────────────────────────────────
    def start(self, site_url: str) -> dict:
        """Begin (or keep waiting on) a browser sign-in. Returns the pending
        state: {url, port, done, error}."""
        if not self.configured:
            raise CloudError(
                "Alto has no Firebase project configured (ALTO_FIREBASE_CONFIG), "
                "so there is no account to sign in to.")
        if self._pending and not self._pending["done"] and \
                time.time() < self._pending["deadline"]:
            return self._pending
        state = secrets.token_urlsafe(24)
        session = self
        pending = {"state": state, "done": False, "error": "",
                   "deadline": time.time() + 600}

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):  # stdio is the MCP channel: stay silent
                pass

            def _send(self, code, text, ctype="text/plain; charset=utf-8"):
                b = text.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(b)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):
                if self.path.split("?")[0] != "/cb":
                    return self._send(404, "Not found")
                self._send(200, _CB_PAGE, "text/html; charset=utf-8")

            def do_POST(self):
                if self.path != "/cb":
                    return self._send(404, "Not found")
                n = min(int(self.headers.get("Content-Length") or 0), 16384)
                q = urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8", "replace"))
                if (q.get("state") or [""])[0] != state:
                    return self._send(400, "This sign-in link has expired. Go back to Claude and try again.")
                if pending["done"]:
                    return self._send(200, "Already connected. You can close this tab.")
                try:
                    session._accept((q.get("rt") or [""])[0])
                    pending["done"] = True
                    who = session.email or "your account"
                    self._send(200, f"Alto is connected to {who}. You can close this tab and go back to Claude.")
                except Exception as e:  # noqa: BLE001 — reported to the tool call
                    pending["error"] = str(e)
                    self._send(400, "Sign-in did not complete. Go back to Claude and try again.")
                finally:
                    if pending["done"]:
                        threading.Thread(target=srv.shutdown, daemon=True).start()

        srv = HTTPServer(("127.0.0.1", 0), H)
        port = srv.server_address[1]
        base = site_url.rstrip("/")
        pending["port"] = port
        pending["url"] = f"{base}/connect/?port={port}&state={urllib.parse.quote(state)}"
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        t = threading.Timer(600, srv.shutdown)
        t.daemon = True          # never keep the connector alive on its own
        t.start()
        self._pending = pending
        try:
            self.opener(pending["url"])
        except Exception:  # noqa: BLE001 — the URL is returned for the user anyway
            pass
        return pending

    def wait(self, seconds: float) -> bool:
        end = time.time() + seconds
        while time.time() < end:
            if self._pending and (self._pending["done"] or self._pending["error"]):
                break
            time.sleep(0.25)
        return self.signed_in and bool(self._pending and self._pending["done"])


def _claims(jwt: str) -> dict:
    try:
        import base64
        part = jwt.split(".")[1]
        part += "=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(part))
    except Exception:  # noqa: BLE001
        return {}


_SESSION: Session | None = None


def get_session() -> Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = Session()
    return _SESSION


def set_session(s: Session | None) -> None:
    global _SESSION
    _SESSION = s


def escape(s: str) -> str:
    return html.escape(s or "", quote=True)
