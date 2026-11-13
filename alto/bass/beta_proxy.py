"""The Bass beta proxy: the HTTPS handler the "bass-proxy" Cloud Function runs. Pure Python, no Google libraries here:
everything outside Alto's control is an INTERFACE (TokenVerifier, SecretReader, the store), so the same code runs in-process
against fakes (the tests) and in the function against Firebase Auth, Secret Manager and Firestore (IT's adapters, deploy/bass-proxy/).

One request, in this order (nothing before the last step can reach Anthropic):
    method / size / JSON check -> CORS origin -> Firebase ID token -> uid + verified email
    -> BetaService.handle (per-IP limit, allowlist, kill switch, opening grant, per-account limit, in-flight, allowance,
       estimate prompt, per-action cap, transactional hold + daily reservation, refunds, metadata log)
    -> response: Alto's own JSON only. No upstream header, body, id or key ever reaches the caller.

The key: read from Secret Manager ONLY when the server flag `bass_beta/live_go` is on, once per cold start, held in memory.
Flag off (the default): every model call goes to the mock transport. Nothing here reads an env var or a file for a key.
"""
from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path
from typing import Callable

from . import keys
from .beta_config import BetaConfig
from .beta_guard import Allowlist, BetaFlags, BetaService, KillSwitch, MetaLog, RecordingSink, Watchdog
from .beta_ledger import LIVE_GO_KEY, BetaLedger
from .client import make_client
from .errors import NotConfigured
from .mock_anthropic import MockAnthropic

SECRET_NAME = "alto-bass-beta-key"
SAFE_HEADERS = {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff"}


class AuthError(Exception):
    """The ID token is missing, malformed, expired or not Alto's. Carries no detail on purpose."""


class TokenVerifier:
    """Interface: verify(id_token) -> {"uid", "email", "email_verified"}; raises AuthError. The real one is
    firebase_admin.auth.verify_id_token behind this signature (IT)."""

    def verify(self, id_token: str) -> dict:             # pragma: no cover - interface
        raise NotImplementedError


class SecretReader:
    """Interface: read(name) -> str. The real one is Secret Manager's access_secret_version of the latest version (IT)."""

    def read(self, name: str) -> str:                    # pragma: no cover - interface
        raise NotImplementedError


class SecretKeyProvider(keys.KeyProvider):
    name = "secret-manager"

    def __init__(self, reader: SecretReader, name: str = SECRET_NAME):
        self.reader, self.secret = reader, name
        self._key = None
        self._lock = threading.Lock()

    def get_key(self) -> str:
        with self._lock:
            if self._key is None:
                try:
                    self._key = self.reader.read(self.secret)
                except Exception:
                    raise NotConfigured("the Bass key is not available", code="bass_paused") from None
                if not self._key:
                    raise NotConfigured("the Bass key is empty", code="bass_paused")
            return self._key

    def describe(self) -> dict:
        return {"provider": self.name, "secret": self.secret}        # where it comes from, never what it is


class Proxy:
    """handle_http(method, headers, body) -> (status, headers, body_bytes)."""

    def __init__(self, cfg: BetaConfig, store, verifier: TokenVerifier, secrets: SecretReader, tools, *,
                 clock: Callable, origins=None, sink=None, mock: MockAnthropic | None = None, sleep=None, mock_tools=None,
                 blobs=None, research=None):
        from . import engine as E
        from .actions import Actions
        self.cfg, self.store, self.verifier, self.clock = cfg, store, verifier, clock
        self.origins = frozenset(cfg.allowed_origins if origins is None else origins)
        self.sink = sink if sink is not None else RecordingSink()
        self.mock = mock or MockAnthropic()
        self.keyprov = SecretKeyProvider(secrets)
        self.kill = KillSwitch(store, self.sink, clock)
        self.ledger = BetaLedger(store, cfg, clock, sink=self.sink, kill=self.kill, sleep=sleep or (lambda s: None))
        self.ledger.on_commit = Watchdog(cfg, self.kill, clock)
        self.flags = BetaFlags(self.kill, self.sink, store=store, clock=clock, cfg=cfg)
        self._client, self._client_mode = None, None
        self._last_reap = 0.0
        self._lock = threading.Lock()
        # With live_go OFF the answers come from the mock, and whatever the mock "builds" goes to a throw-away store, NEVER the tester's
        # real account (a mock build must not look like, or sit among, real work).
        self.real_tools = tools
        self.mock_tools = mock_tools if mock_tools is not None else _scratch_tools()
        engine = E.Engine(_LazyClient(self), self.ledger, _LazyTools(self), flags=self.flags, sleep=sleep or (lambda s: None),
                          monotonic=lambda: clock().timestamp())
        engine.cfg.per_action_cap_mc = cfg.per_action_cap_mc
        engine.cfg.max_wall_s = cfg.action_wall_s                 # an action stops itself before the platform's timeout can cut it
        self.service = BetaService(cfg, Actions(engine, self.ledger), self.ledger, store=store, kill=self.kill,
                                   allow=Allowlist(store, cfg, self.sink), sink=self.sink, clock=clock, metalog=MetaLog(clock, store=store, zone=cfg.zone), blobs=blobs, research=research)
        bad = cfg.problems()
        if bad:
            raise ValueError("the beta config is not safe to serve: " + "; ".join(bad))

    # -- the client: mock unless the server's own flag says go ------------------------------------------------------
    def live_go(self) -> bool:
        try:
            return bool((self.store.get(LIVE_GO_KEY) or {}).get("on"))
        except Exception:
            return False                                              # unknown means off

    def client(self):
        go = self.live_go()
        mode = "live" if go else "mock"
        with self._lock:
            if self._client is None or self._client_mode != mode:
                if go:
                    self._client = make_client("live", key_provider=self.keyprov, go_check=lambda: True)
                else:
                    self._client = make_client("mock", mock=self.mock)
                self._client_mode = mode
            return self._client

    def _maybe_reap(self) -> None:
        """The reaper rides on traffic: at most every 5 minutes a request frees holds a crashed instance left behind
        (a scheduled job is optional, not needed). A failure here never blocks the request."""
        now = self.clock().timestamp()
        if now - self._last_reap < 300:
            return
        self._last_reap = now
        try:
            self.ledger.reap()
        except Exception:
            pass

    # -- http ----------------------------------------------------------------------------------------------------------
    def _reply(self, status: int, payload: dict, origin: str | None = None):
        headers = dict(SAFE_HEADERS)
        if origin and origin in self.origins:
            headers.update({"Access-Control-Allow-Origin": origin, "Vary": "Origin"})
        return status, headers, json.dumps(payload, separators=(",", ":")).encode("utf-8")

    def handle_http(self, method: str, headers: dict, body: bytes | str | None):
        h = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
        origin = h.get("origin")
        if method == "OPTIONS":
            st, hd, _ = self._reply(204, {}, origin)
            hd.update({"Access-Control-Allow-Methods": "POST", "Access-Control-Allow-Headers": "Authorization, Content-Type"})
            return st, hd, b""
        if method != "POST":
            return self._reply(405, {"ok": False, "message": "POST only."}, origin)
        raw = body.encode("utf-8") if isinstance(body, str) else (body or b"")
        if len(raw) > self.cfg.max_request_bytes:
            return self._reply(413, {"ok": False, "message": "That request is too large."}, origin)
        try:
            request = json.loads(raw.decode("utf-8"))
            if not isinstance(request, dict):
                raise ValueError
        except ValueError:
            return self._reply(400, {"ok": False, "message": "Bass could not read that request."}, origin)
        auth = h.get("authorization", "")
        try:
            if not auth.lower().startswith("bearer ") or not auth[7:].strip():
                raise AuthError
            who = self.verifier.verify(auth[7:].strip())
            uid, email, verified = str(who["uid"]), str(who["email"]), who.get("email_verified") is True
        except Exception:                                              # AuthError or anything a verifier raises: the same 401
            return self._reply(401, {"ok": False, "message": "Please sign in again."}, origin)
        self._maybe_reap()
        out = self.service.handle({"uid": uid, "email": email, "email_verified": verified, "xff": h.get("x-forwarded-for"),
                                   "remote": h.get("x-real-ip"), "request": request})
        if not self.live_go() and isinstance(out, dict):
            out["mock"] = True                                    # a practice answer from the mock: the page must say so
            out["notice"] = MOCK_NOTICE
        return self._reply(200, out, origin)


MOCK_NOTICE = "Test mode: this answer came from a practice model and nothing was saved to your account."


def _scratch_tools():
    from .tools import ToolBox
    from alto.store.local import LocalStore
    return ToolBox(LocalStore(Path(tempfile.mkdtemp(prefix="bass-mock-"))))


class _LazyTools:
    """What the engine holds as its tool belt: the tester's REAL tools when live_go is on, a scratch belt when it is off."""

    def __init__(self, proxy: "Proxy"):
        object.__setattr__(self, "_p", proxy)

    def _belt(self):
        p = object.__getattribute__(self, "_p")
        return p.real_tools if p.live_go() else p.mock_tools

    def specs(self):
        return self._belt().specs()

    def execute(self, uid, name, tool_input):
        return self._belt().execute(uid, name, tool_input)

    def __getattr__(self, name):
        return getattr(self._belt(), name)


class _LazyClient:
    """What the engine holds as its client: resolves to the right (mock or live) client on every use, so flipping
    bass_beta/live_go takes effect on the next call without a restart."""

    def __init__(self, proxy: Proxy):
        object.__setattr__(self, "_p", proxy)

    @property
    def messages(self):
        return object.__getattribute__(self, "_p").client().messages
