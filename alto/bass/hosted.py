"""Hosted Bass for ONE allowlisted account (Luke's), on luke-alto: the server-side gate in front of the beta Proxy.

Nobody but the allowlisted uid ever receives Bass code or Bass words. The pages stay the default build (no Bass UI, no /bass/ folder); the
only change a visitor's browser gets is the generic hook in alto-cloud.js (alto/cloud/ext_hook.py), which asks this gate once after sign-in.

One request:
    OPTIONS              -> the same CORS answer for everyone (it carries no account)
    anything else        -> POST, size, JSON, Firebase ID token (the verifier: Google sign-in only), uid + verified email, then ALL of:
                              1. the uid is in the deploy pin (ALTO_EXT_UIDS, at most cfg.testers uids)
                              2. the uid is in Firestore bass_beta/hosted {uids: [...]} (at most cfg.testers; longer admits nobody)
                              3. the verified email is on Bass's own tester list bass_beta/bass_testers (beta_guard.Allowlist, N = 1)
                           any check fails, or anything raises -> EMPTY: 200, body {}, the same headers. No 401, no 403, no message.
    allowed + "ext"      -> {"x": the hosted bundle}: the Bass UI with its entry points in the NEW dialog and on the study-plan line (alto/build/bass_hosted_ext.py)
    allowed, after the promo cutoff (promo.py, fail closed), any other action -> promo_ended ("The free Bass credit has ended."), nothing else runs
    allowed, otherwise   -> the beta Proxy, unchanged (its own token check, Beta Terms, kill switch, ledger, period marker, live_go flag)

Off-switch: delete bass_beta/hosted (the next request answers EMPTY, Luke included)."""
from __future__ import annotations

import json
import re
from typing import Callable

from . import promo
from .beta_config import BetaConfig
from .beta_guard import Allowlist, _answer
from . import editbass

HOSTED_KEY = "bass_beta/hosted"                 # {uids: [<uid>, ...]}: server only (firestore.rules: bass_beta/** denies every client)
PIN_ENV = "ALTO_EXT_UIDS"                       # the deploy's own pin, comma separated
EXT_ACTION = "ext"
EMPTY = b"{}"
_UID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_HEADERS = {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}

# Money (Board B-1114-b): the Console's org and workspace limits are $5 (500 credits). The books stop at 400 (a hard total; the 300 per-action
# cap is inside it, so an action after a 300 one is capped by the 100 left); the other 100 is never booked, so the books miss by up to 100 and
# it stays under the $5 limit, and all spend happens before the promo cutoff. Whether Anthropic draws the promo or the purchased credit first is outside this code: it keeps spend under $5 and before the
# promo's end, and does NOT promise which credit pays. The period starts on the 1st
# (like the Console's own month), so no new period (and no fresh ceiling) opens between the deploy and the cutoff.
TOTAL_CREDITS = 500
CEILING_CREDITS = 400
PER_ACTION_CREDITS = 300
ORIGINS = ("https://luke-alto.web.app", "https://luke-alto.firebaseapp.com")


def hosted_config(**kw) -> BetaConfig:
    base = dict(testers=1, allowlist=frozenset(), pool_credits=TOTAL_CREDITS, server_ceiling_credits=CEILING_CREDITS,
                per_action_cap_credits=PER_ACTION_CREDITS, tester_daily_credits=CEILING_CREDITS, global_daily_credits=CEILING_CREDITS,
                spike_credits=100, spike_alert_credits=200, start_day=1, allowed_origins=ORIGINS, zone_optional=True)
    base.update(kw)
    return BetaConfig(**base)


def hosted_problems(cfg: BetaConfig, now=None) -> list:
    """cfg.problems() plus the hosted money rules. The hosted function refuses to start with any."""
    out = list(cfg.problems())
    if cfg.testers != 1:
        out.append("hosted Bass is for one account: testers must be 1")
    if cfg.pool_credits > TOTAL_CREDITS:
        out.append(f"the pool is above the {TOTAL_CREDITS}-credit Console limit")
    if cfg.server_ceiling_credits > CEILING_CREDITS:
        out.append(f"the ceiling is above the {CEILING_CREDITS}-credit hard total")
    if cfg.per_action_cap_credits > PER_ACTION_CREDITS:
        out.append(f"the per-action cap is above {PER_ACTION_CREDITS} credits ($3)")
    if cfg.tester_daily_credits > cfg.server_ceiling_credits or cfg.global_daily_credits > cfg.server_ceiling_credits:
        out.append("a daily limit is above the ceiling")
    if now is not None and cfg.zone_ok and cfg.period_id(now) != cfg.period_id(promo.CUTOFF_UTC):
        out.append("a new credit period would open before the promo cutoff (its ceiling would be fresh)")
    return out


def pinned_uids(raw: str | None) -> frozenset:
    """The deploy pin: uids of the accepted shape only. A malformed entry voids the whole pin (fail closed)."""
    parts = [p.strip() for p in str(raw or "").split(",") if p.strip()]
    if not parts or any(not _UID.match(p) for p in parts):
        return frozenset()
    return frozenset(parts)


class HostedGate:
    def __init__(self, proxy, store, verifier, *, cfg: BetaConfig, pins: frozenset, clock: Callable, bundle: Callable[[], str] | None = None,
                 owns: Callable[[str, str], bool] | None = None):
        self.proxy, self.store, self.verifier, self.cfg, self.clock = proxy, store, verifier, cfg, clock
        self.owns = owns                                           # (verified uid, timeline id) -> does this account own it; None = Edit with Bass answers EMPTY (fail closed)
        self.pins = frozenset(pins) if len(pins) <= int(cfg.testers) else frozenset()
        self.origins = frozenset(cfg.allowed_origins)
        self.allow = Allowlist(store, cfg)
        self._bundle = bundle
        if bundle is None:                                         # serve only the pinned bundle: a drift refuses the cold start (fail closed)
            from alto.build import bass_hosted_ext
            from alto.cloud import ext_hook
            js = bass_hosted_ext.bundle()
            want = " ".join(str(x) for x in ext_hook.pin())
            if bass_hosted_ext.pin(js) != want:
                raise RuntimeError("the hosted bundle does not match alto/cloud/ext_pin.txt: re-pin and re-stamp")
            self._bundle = lambda: js

    def _headers(self, origin):
        h = dict(_HEADERS)
        if origin in self.origins:
            h.update({"Access-Control-Allow-Origin": origin, "Vary": "Origin"})
        return h

    def empty(self, origin=None):
        return 200, self._headers(origin), EMPTY

    def _listed(self, uid: str) -> bool:
        doc = self.store.get(HOSTED_KEY)
        uids = doc.get("uids") if isinstance(doc, dict) else None
        if not isinstance(uids, list) or len(uids) > int(self.cfg.testers):
            return False
        return uid in [u for u in uids if isinstance(u, str)]

    def who(self, headers: dict, request: dict):
        """(uid, email) when every gate holds, else None. Raises nothing the caller sees as different."""
        auth = headers.get("authorization", "")
        if not auth.lower().startswith("bearer ") or not auth[7:].strip():
            return None
        d = self.verifier.verify(auth[7:].strip())
        uid, email, verified = str(d["uid"]), str(d.get("email", "")), d.get("email_verified") is True
        if not verified or not _UID.match(uid) or uid not in self.pins or not self._listed(uid) or not self.allow.allowed(email, verified):
            return None
        confirm = getattr(self.verifier, "confirm", None)          # the hosted verifier: revoked or disabled? (an Auth call, only for the pinned uid)
        if confirm is not None and confirm(auth[7:].strip()) != uid:
            return None
        return uid, email

    def _owns(self, uid: str, request: dict) -> bool:
        """Edit with Bass: the body names no account at all, the timeline id has the one id shape, and the verified uid owns it. Never raises."""
        try:
            if self.owns is None or editbass.smuggled(request):
                return False
            tid = request["args"].get("timeline_id") if isinstance(request.get("args"), dict) else None
            return editbass.valid_tid(tid) and bool(self.owns(uid, tid))
        except Exception:
            return False

    def handle_http(self, method: str, headers: dict, body):
        h = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
        origin = h.get("origin")
        if method == "OPTIONS":
            hd = self._headers(origin)
            hd.update({"Access-Control-Allow-Methods": "POST", "Access-Control-Allow-Headers": "Authorization, Content-Type", "Access-Control-Max-Age": "600"})
            return 204, hd, b""
        try:
            if method != "POST" or not self.cfg.zone_ok:             # no usable time zone: the period and day cannot be told, so refuse (fail closed)
                return self.empty(origin)
            raw = body.encode("utf-8") if isinstance(body, str) else (body or b"")
            if len(raw) > self.cfg.max_request_bytes:
                return self.empty(origin)
            request = json.loads(raw.decode("utf-8"))
            who = self.who(h, request) if isinstance(request, dict) else None
            if who is None:
                return self.empty(origin)
            action = request.get("action")
            if action in editbass.EDIT_ACTIONS and not self._owns(who[0], request):   # Edit with Bass: the id is untrusted; the uid is the token's; a non-owned, unknown or
                return self.empty(origin)                                                # malformed id gets the same answer as a bad token (checked on EVERY request, Apply included)
            if action == EXT_ACTION:
                js = self._bundle()
                return 200, self._headers(origin), json.dumps({"x": js}, separators=(",", ":")).encode("utf-8")
            if not promo.live_allowed(self.clock):                   # the free credit's end, fail closed: nothing past here runs
                return 200, self._headers(origin), json.dumps(_answer("promo_ended", "paused"), separators=(",", ":")).encode("utf-8")
        except Exception:
            return self.empty(origin)
        return self.proxy.handle_http(method, headers, body)
