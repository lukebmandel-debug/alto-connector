"""The beta guard layer: allowlist, kill switch, alerts, logs, and the one service that puts them in front of Bass.

  handle(request) order (every step before the call spends nothing and sends nothing to Anthropic):
     malformed -> per-IP limit -> allowlist gate (verified Google email on the list, else Bass is OFF) -> per-account limit
     -> Beta Terms accepted? -> kill switch -> opening grant (idempotent) -> in-flight (1 build + 2 chat) -> beta credits used?
     -> upload text extraction (PDF / .docx, alto/bass/extract.py)
     -> Actions.dispatch (engine: estimate prompt, per-action cap, holds in ONE transaction with the global daily reservation,
        refusals/failures refunded within the 5/day cap) -> metadata-only log line.

Anything unexpected FAILS CLOSED: the caller gets a plain "paused" answer and no model call is made.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
import threading
from typing import Callable

from .beta_config import BetaConfig, _norm
from .beta_ledger import BASS_TESTERS_KEY, KILL_KEY, BetaLedger
from .beta_limits import InFlight, SlidingLimiter, client_ip
from .beta_store import StoreError
from .errors import POLICIES, Policy
from .documents import DocsError, Library, refusal as docs_refusal
from .extract import Extractor, UploadRefused
from .drive import DriveService

log = logging.getLogger("bass.beta")
FREE = ("balance", "stop")                       # the only actions that send nothing upstream (estimate makes the free count_tokens
                                                 # call). ANY other action name is gated like spending (fail closed): a new Bass path
                                                 # (grading, hypotheticals, ...) meets the closed check and the allowance precheck first
UPLOAD_ACTIONS = ("estimate", "propose", "build")  # the actions that take materials (and so may carry uploaded files)
from .research_share import RESEARCH                      # the opt-in conversation sharing action (alto/bass/research_share.py)
DRIVE = "drive"                                  # Add from Drive (alto/bass/drive.py): config / connect / add / disconnect; sends nothing to Anthropic, spends nothing
DOCS = "docs"                                    # the Documents library (alto/bass/documents.py): sends nothing upstream, spends nothing
SCOPED = ("estimate", "propose", "build", "edit")  # the actions that may name a Documents scope (args.scope_id)
SPENDING = ("build", "convert", "propose", "edit", "make_study_plan")          # what Actions dispatches today that spends (kept for the in-flight kinds)
STATUS_FOR = {"beta_credits_used": "no_credits", "beta_tester_daily": "capped", "beta_daily_full": "paused"}


# -- alerts ------------------------------------------------------------------------------------------------------------
class AlertSink:
    """Where alerts go. The real one is IT's (email/push, after Blaze); the interface is this one method."""

    def emit(self, kind: str, **detail) -> None:               # pragma: no cover - interface
        raise NotImplementedError


class RecordingSink(AlertSink):
    def __init__(self):
        self.events: list[dict] = []
        self._lock = threading.Lock()

    def emit(self, kind: str, **detail) -> None:
        with self._lock:
            self.events.append({"kind": kind, **detail})

    def kinds(self) -> list:
        return [e["kind"] for e in self.events]

    def of(self, kind: str) -> list:
        return [e for e in self.events if e["kind"] == kind]


# -- kill switch -------------------------------------------------------------------------------------------------------
class KillSwitch:
    """One flag in the store. Trips by itself (see Watchdog and BetaFlags), resets BY HAND only. If the store cannot be
    read the answer is "on" (fail closed). Viewing, presets and by-hand editing never consult it."""

    def __init__(self, store, sink: AlertSink | None = None, clock: Callable[[], dt.datetime] | None = None):
        self.store, self.sink = store, sink
        self.clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))
        self._local = None                      # a trip that could not be written to the store still stops THIS process

    def state(self) -> dict:
        try:
            doc = self.store.get(KILL_KEY) or {}
        except StoreError:
            return {"on": True, "reason": "store_unavailable"}
        if self._local and not doc.get("on"):
            reason = self._local
            try:                                # a trip that could not be written yet: try again, keep stopping meanwhile
                self.store.put(KILL_KEY, {"on": True, "reason": reason, "t": self.clock().isoformat(), "detail": {"retried": True}})
                self._local = None
            except StoreError:
                pass
            return {"on": True, "reason": reason}
        return {"on": bool(doc.get("on")), "reason": doc.get("reason", "")}

    def is_on(self) -> bool:
        return self.state()["on"]

    def trip(self, reason: str, **detail) -> bool:
        """-> True when THIS call flipped it (the first reason wins; later trips are no-ops)."""
        out = {"new": False}

        def work(txn):
            out["new"] = False
            k = txn.get(KILL_KEY) or {}
            if k.get("on"):
                return
            txn.put(KILL_KEY, {"on": True, "reason": reason, "t": self.clock().isoformat(), "detail": detail})
            out["new"] = True

        try:
            self.store.run_transaction(work)
        except StoreError:
            self._local, out["new"] = reason, True
        if out["new"] and self.sink is not None:
            self.sink.emit("kill_switch", reason=reason, **detail)
        return out["new"]

    def reset(self, by: str = "hand") -> None:
        self._local = None
        self.store.put(KILL_KEY, {"on": False, "reason": "", "reset_by": by, "t": self.clock().isoformat()})
        if self.sink is not None:
            self.sink.emit("kill_switch_reset", by=by)


class BetaFlags:
    """Duck-typed errors.Flags for the engine, backed by the kill switch: an upstream 401 / 403 / "credit balance too low" /
    Console limit (the engine calls trip() with that error's policy) flips the switch for everyone, with no retry.
    bad_input (a 400 about one tester's notes) never trips by itself: it raises an alert, and trips only when `bad_input_accounts`
    (3) DISTINCT accounts hit it inside `bad_input_window_s` (10 minutes): then it is more likely a request-format bug of ours."""
    takes_uid = True

    def __init__(self, kill: KillSwitch, sink: AlertSink | None = None, *, store=None, clock=None, cfg: BetaConfig | None = None):
        self.kill, self.sink = kill, sink
        self.store, self.cfg = store, cfg
        self.clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))
        self.alerts: list = []
        self._bad: list = []                       # in-memory fallback when no store is given: [(ts, uid)]
        self._lock = threading.Lock()

    @property
    def bass_enabled(self) -> bool:
        return not self.kill.is_on()

    @property
    def reason(self) -> str:
        return self.kill.state()["reason"]

    def _note_bad_input(self, uid) -> int:
        """-> how many distinct accounts hit bad_input inside the window (this one included)."""
        win = self.cfg.bad_input_window_s if self.cfg else 600
        now = self.clock().timestamp()
        out = {}

        def fold(events):
            ev = [e for e in events if now - e[0] <= win] + [[now, str(uid)]]
            out["n"] = len({e[1] for e in ev})
            return ev

        if self.store is None:
            with self._lock:
                self._bad = fold(self._bad)
            return out["n"]

        def work(txn):
            doc = txn.get("bass_beta/badinput") or {"events": []}
            doc["events"] = fold(doc["events"])
            txn.put("bass_beta/badinput", doc)

        try:
            self.store.run_transaction(work)
        except StoreError:
            return 0                                # the alert still went out; the trip needs the shared count
        return out["n"]

    def trip(self, policy: Policy, detail: dict | None = None, uid=None) -> None:
        if policy.code == "bad_input":
            self.alerts.append({"code": policy.code})
            if self.sink is not None:
                self.sink.emit("bad_input", uid=uid)
            need = self.cfg.bad_input_accounts if self.cfg else 3
            if self._note_bad_input(uid) >= need:
                self.kill.trip("bad_input_burst", accounts=need)
            return
        if policy.code == "history_mismatch":
            # the API's history-editing check refused ONE conversation's kept history (finding A2): alert, never the switch for everyone
            self.alerts.append({"code": policy.code})
            if self.sink is not None:
                self.sink.emit("history_mismatch", uid=uid)
            return
        if policy.kill_switch or policy.pause_bass or policy.code == "bad_request":
            # an unexpected 400 on a Bass call is treated like the others: stop for everyone, no retry, look at it by hand
            self.kill.trip("upstream_" + policy.code, status=(detail or {}).get("status"))
        if policy.alert:
            self.alerts.append({"code": policy.code, "detail": detail or {}})
            if self.sink is not None and not (policy.kill_switch or policy.pause_bass or policy.code == "bad_request"):
                self.sink.emit("upstream_error", code=policy.code)

    def reset(self) -> None:
        self.kill.reset()


class Watchdog:
    """Called with the day doc and the period doc after every commit that changed them (security finding B1: nothing the caps allow may
    switch Bass off for everyone, since the kill switch only resets by hand):
       (a) the day's counter (spent + reserved) over 80% of the day's limit before 18:00 local: an ALERT, once a day. The day's own limit
           already refuses everything past 100% (beta_daily_full) and resets itself at midnight;
       (b) more than cfg.spike_alert_credits ($4) of spend inside any 10 minutes: an ALERT (Luke's number, decision G1), at most once per
           window. It never stops Bass;
       (c) more than cfg.spike_trip_mc of spend inside any 10 minutes: the KILL SWITCH. That threshold sits above anything the caps allow,
           so it trips only when the books let through what they should have refused."""

    def __init__(self, cfg: BetaConfig, kill: KillSwitch, clock: Callable[[], dt.datetime], sink: AlertSink | None = None):
        self.cfg, self.kill, self.clock = cfg, kill, clock
        self.sink = sink if sink is not None else kill.sink
        self._warned_day = None
        self._spike_alert_t = None

    def __call__(self, g: dict, p: dict) -> None:
        now = self.clock().astimezone(self.cfg.zone)
        used = g["spent_mc"] + g["reserved_mc"]
        if used * 100 > self.cfg.trip_fraction * 100 * self.cfg.daily_ceiling_mc and now.hour < self.cfg.trip_before_hour:
            day = now.date().isoformat()
            if self._warned_day != day and self.sink is not None:
                self._warned_day = day
                self.sink.emit("daily_over_80_before_18", used_mc=used)
        t = now.timestamp()
        recent = sum(mc for ts, mc in p["spend_log"] if t - ts <= self.cfg.spike_window_s)
        if recent > self.cfg.spike_alert_credits * 1000 and self.sink is not None and \
                (self._spike_alert_t is None or t - self._spike_alert_t > self.cfg.spike_window_s):
            self._spike_alert_t = t
            self.sink.emit("spend_over_alert_10min", recent_mc=recent, alert_mc=self.cfg.spike_alert_credits * 1000,
                           window_s=self.cfg.spike_window_s)
        if recent > self.cfg.spike_trip_mc:
            self.kill.trip("spend_spike_10min", recent_mc=recent)


# -- allowlist ---------------------------------------------------------------------------------------------------------
class Allowlist:
    """Verified Google emails allowed to use BASS (review finding S1). Bass has its OWN list, the store doc `bass_beta/bass_testers`
    ({"emails": [...]}), edited by hand by Luke or IT; it wins over the config copy, so adding a tester needs no deploy. The Alto cloud
    beta's list (`bass_beta/allowlist`: who may save to the cloud) is never read here: being allowed to save does not make anyone a Bass
    tester. A list LONGER than N (cfg.testers, the number the allowances were budgeted for) admits NOBODY and raises an alert: more
    people than planned must never share Luke's credit by accident. A store error means "not allowed"."""

    def __init__(self, store, cfg: BetaConfig, sink: AlertSink | None = None):
        self.store, self.cfg, self.sink = store, cfg, sink
        self._alerted = None

    def emails(self) -> frozenset:
        try:
            doc = self.store.get(BASS_TESTERS_KEY)
        except StoreError:
            return frozenset()
        if doc and isinstance(doc.get("emails"), list):
            listed = frozenset(_norm(e) for e in doc["emails"] if _norm(e))
        else:
            listed = self.cfg.allowlist
        if len(listed) > int(self.cfg.testers):
            if self.sink is not None and self._alerted != len(listed):      # once per list size, not once per request
                self._alerted = len(listed)
                self.sink.emit("tester_list_too_long", listed=len(listed), budgeted=int(self.cfg.testers))
            return frozenset()
        self._alerted = None
        return listed

    def allowed(self, email: str, verified: bool) -> bool:
        return verified is True and _norm(email) in self.emails()


# -- the Beta Terms gate (IT's rule, privacy-inventory sec 5) ----------------------------------------------------------
TERMS_PREFIX = "terms_acceptance/"


class TermsGate:
    """Bass refuses a uid with no acceptance of the CURRENT Beta Terms version. The client writes `terms_acceptance/<uid>_<version>` =
    {uid, version, ageConfirmed: true, acceptedAt}; here ONE direct get by the id uid + "_" + version (the uid is the VERIFIED token's, the
    version the bundled one; never anything from the request body; no query, no list). It counts only when the doc is for this uid and
    this version, ageConfirmed is true and acceptedAt is present (other keys are ignored). Missing, unreadable, malformed, or a store error = not
    accepted (fail closed). A bumped version names a different document, so everyone is asked again."""

    def __init__(self, store, cfg: BetaConfig):
        self.store, self.cfg = store, cfg

    def accepted(self, uid: str) -> bool:
        ver = str(self.cfg.terms_version)
        if not isinstance(uid, str) or not uid or "/" in uid or not re.match(r"^[A-Za-z0-9._-]{1,32}$", ver):
            return False
        try:
            doc = self.store.get(f"{TERMS_PREFIX}{uid}_{ver}")
        except Exception:                                                # StoreError or anything else: closed
            return False
        return (isinstance(doc, dict) and doc.get("uid") == uid and doc.get("version") == ver
                and doc.get("ageConfirmed") is True and bool(doc.get("acceptedAt")))


# -- logs: metadata only -------------------------------------------------------------------------------------------------
LOG_FIELDS = ("t", "uid", "action", "status", "code", "credits_spent", "credits_refunded", "tool_calls", "out_tokens")


META_PREFIX = "bass_beta/meta/"                  # bass_beta/meta/<uid>_<YYYY-MM-DD>: that tester's day of log lines (tools/bass_beta_report.py)
META_MAX_LINES = 500


class MetaLog:
    """One line per call: who, what kind, how many credits, how many tool calls and output tokens. Never conversation text,
    never a title, material, email or IP. Fields outside LOG_FIELDS are dropped on the way in. With a store, the line is also kept in
    that tester's day doc (one doc per tester per day, so testers never contend), best effort: a store problem never touches the call."""

    def __init__(self, clock: Callable[[], dt.datetime], store=None, zone=None):
        self.clock, self.lines, self.store, self.zone = clock, [], store, zone

    def write(self, **rec) -> None:
        line = {k: rec[k] for k in LOG_FIELDS if k in rec}
        line["t"] = self.clock().isoformat()
        self.lines.append(line)
        log.info(json.dumps(line, sort_keys=True))
        uid = line.get("uid")
        if self.store is None or not isinstance(uid, str) or not re.match(r"^[A-Za-z0-9_-]{1,128}$", uid):
            return
        day = (self.clock().astimezone(self.zone) if self.zone else self.clock()).date().isoformat()
        key = f"{META_PREFIX}{uid}_{day}"

        def work(txn):
            doc = txn.get(key) or {"uid": uid, "day": day, "lines": []}
            if len(doc["lines"]) < META_MAX_LINES:
                doc["lines"].append(line)
                txn.put(key, doc)
        try:
            self.store.run_transaction(work)
        except Exception:
            pass


# -- the service ---------------------------------------------------------------------------------------------------------
def _answer(code: str, status: str, **extra) -> dict:
    out = {"ok": False, "status": status, "code": code, "message": POLICIES[code].user_message, "action_id": None,
           "work_saved": False, "credits": None, "retryable": status in ("busy", "paused"), "events": []}
    out.update(extra)
    return out


class BetaService:
    def __init__(self, cfg: BetaConfig, actions, ledger: BetaLedger, *, store, kill: KillSwitch, allow: Allowlist,
                 sink: AlertSink, clock: Callable[[], dt.datetime], metalog: MetaLog | None = None, extractor=None, blobs=None,
                 research=None, drive=None):
        self.cfg, self.actions, self.ledger, self.store = cfg, actions, ledger, store
        self.kill, self.allow, self.sink, self.clock = kill, allow, sink, clock
        self.terms = TermsGate(store, cfg)
        self.research = research                  # a ResearchShare, or None (no bucket wired = nothing is ever saved)
        if research is not None:
            research.on_error = lambda u, code: self.meta.write(uid=u, action="research_record", status="error", code=code)   # a dead recorder shows in the metadata log
        self.extractor = extractor or Extractor(cfg)
        self.library = Library(store, cfg, clock, extractor=self.extractor, blobs=blobs)
        self.drive = drive or DriveService(store, cfg, clock, self.library)       # the config is the server's environment: unset = the feature is off
        self.limiter = SlidingLimiter(lambda: self.clock().timestamp())
        self.inflight = InFlight(cfg.inflight_build, cfg.inflight_chat)
        self.meta = metalog or MetaLog(clock, store=store, zone=cfg.zone)
        self._results: dict = {}
        self._lock = threading.Lock()
        run = actions.engine.run_action

        def spy(*a, **k):                          # capture the ActionResult for the metadata log (tokens, tool calls)
            res = run(*a, **k)
            with self._lock:
                self._results[res.action_id] = res
            return res
        actions.engine.run_action = spy

    # -- helpers --------------------------------------------------------------------------------------------------
    def _miss(self, ip: str) -> None:
        key = "miss:" + ip
        self.limiter.allow(key, 10 ** 9, self.cfg.miss_window_s)         # records the hit
        if self.limiter.count(key, self.cfg.miss_window_s) == self.cfg.miss_burst:
            self.sink.emit("allowlist_miss_burst", ip_bucket=ip, window_s=self.cfg.miss_window_s)

    @staticmethod
    def _kind(name: str):
        return {"build": "build", "convert": "build", "propose": "chat", "edit": "chat", "make_study_plan": "chat"}.get(name)

    # -- the door -------------------------------------------------------------------------------------------------
    def handle(self, req: dict, on_event=None) -> dict:
        try:
            return self._handle(req, on_event)
        except Exception as e:                                           # fail closed, never a stack trace to a tester
            log.error("bass beta: unexpected %s", type(e).__name__)
            return _answer("bass_paused", "paused")

    def _handle(self, req: dict, on_event) -> dict:
        if not isinstance(req, dict) or not isinstance(req.get("request"), dict):
            return _answer("bad_input", "error")
        body, uid = req["request"], str(req.get("uid") or "")
        action = body.get("action")
        ip = client_ip(req.get("xff"), req.get("remote"), self.cfg.trusted_hops)
        if not self.limiter.allow("ip:" + ip, self.cfg.ip_per_min, 60):
            return _answer("busy", "busy")
        if not uid or not self.allow.allowed(req.get("email", ""), req.get("email_verified")):
            self._miss(ip)
            return _answer("bass_off", "paused", available=False)
        if action in (DOCS, DRIVE):                   # tidying a library is many small free calls: its own limit; an add runs the extractor (a Drive add also
            args = body.get("args") if isinstance(body.get("args"), dict) else {}      # fetches), so it also counts against the account's 12 a minute
            if not self.limiter.allow("docs:" + uid, self.cfg.docs_per_min, 60) or \
                    (args.get("op") == "add" and not self.limiter.allow("acct:" + uid, self.cfg.account_per_min, 60)):
                return _answer("busy", "busy")
        elif not self.limiter.allow("acct:" + uid, self.cfg.account_per_min, 60):     # before the terms read: a not-accepted uid cannot hammer the store
            return _answer("busy", "busy")
        if action != "stop" and not self.terms.accepted(uid):      # no acceptance of the current Beta Terms: nothing runs, nothing is held
            return _answer("terms_required", "paused", available=False, beta=True, retryable=False)
        if action in ("convert", "make_study_plan"):  # the format being made / the study plan feature: the ONE entitlement check (alto/entitlements.py), after the terms, before any hold or upstream call
            from alto import entitlements
            if action == "convert":
                args = body.get("args") if isinstance(body.get("args"), dict) else {}
                ok = entitlements.allowed(uid, str(args.get("target", "")))
            else:
                ok = entitlements.allowed(uid, "study_plan")
            if not ok["ok"]:
                self.meta.write(uid=uid, action=action, status="refused", code="needs_plan")
                return _answer("needs_plan", "refused", retryable=False, message=ok["message"], plan=ok["needs_plan"])
        if action == DOCS:                            # library management: allowlisted, rate-limited, terms accepted; no allowance, no upstream
            out = self._docs(uid, body.get("args"))
            self.meta.write(uid=uid, action=action, status=out.get("status"), code=out.get("code"))
            return out
        if action == DRIVE:                           # Add from Drive: allowlisted, rate-limited, terms accepted; no allowance, nothing upstream
            out = self._drive(uid, body.get("args"))
            self.meta.write(uid=uid, action=action, status=out.get("status"), code=out.get("code"))   # never the args: they carry a token or file ids
            return out
        if action == RESEARCH:                        # opt-in conversation sharing: status / optin / withdraw; free, no upstream, no allowance
            args = body.get("args") if isinstance(body.get("args"), dict) else {}
            if self.research is None:
                out = _answer("research_off", "paused")
            else:
                out = self.research.handle(uid, args)
            self.meta.write(uid=uid, action=action, status=out.get("status"), code=out.get("code"))
            return out
        spending = action not in FREE
        closed = self.ledger.closed_reason()          # kill switch, bass_beta/disabled (set or unreadable), period unconfirmed
        if spending and closed:
            return _answer(closed, STATUS_FOR.get(closed, "paused"))
        if not closed:
            self.ledger.grant_opening(uid)            # this period's allowance; idempotent
        kind = self._kind(action)
        if kind and not self.inflight.acquire(uid, kind):
            return _answer("busy", "busy")
        try:
            if spending:
                why = self.ledger.precheck(uid)       # nothing left today / this period: answer with zero requests
                if why:
                    return _answer(why, STATUS_FOR.get(why, "paused"))
            if action in UPLOAD_ACTIONS:              # PDF / .docx -> text: after the allowlist, the terms, the allowance; before any hold or upstream call
                try:
                    self.extractor.prepare((body.get("args") or {}).get("materials") if isinstance(body.get("args"), dict) else None)
                except UploadRefused as e:
                    self.meta.write(uid=uid, action=action, status="refused", code=e.code)
                    return _answer(e.code, "refused", retryable=False)
            if action in SCOPED:
                refused = self._scope_documents(uid, body)
                if refused:
                    self.meta.write(uid=uid, action=action, status="refused", code=refused["code"])
                    return refused
            out = self.actions.dispatch(uid, body, on_event=on_event)
            if action == "balance" and isinstance(out, dict):
                self._beta_balance(uid, out, closed)
        finally:
            if kind:
                self.inflight.release(uid, kind)
        self._record(uid, action, body, out)
        self._log(uid, action, out)
        return out

    def _record(self, uid: str, action, body: dict, out: dict) -> None:
        """An opted-in tester's turn is saved (text only); anyone else's is not. Never raises, never changes `out`."""
        if self.research is None or action not in ("propose", "edit", "build"):
            return
        try:
            with self._lock:
                res = self._results.get(out.get("action_id"))
            names = [getattr(c, "name", None) or (c.get("name") if isinstance(c, dict) else None) or str(c)[:40]
                     for c in (res.tool_calls if res else [])]
            self.research.record(uid, action, body, out, names)
        except Exception:
            pass

    def _docs(self, uid: str, args) -> dict:
        try:
            return self.library.handle(uid, args)
        except UploadRefused as e:
            return _answer(e.code, "refused", retryable=False)

    def _drive(self, uid: str, args) -> dict:
        try:
            return self.drive.handle(uid, args)
        except UploadRefused as e:
            return _answer(e.code, "refused", retryable=False)

    def sign_out(self, uid: str) -> None:
        """The student signs out: the Drive token is revoked and deleted (the page also sends op disconnect first; this is the server's own line)."""
        self.drive.disconnect(uid)

    def erase_account(self, uid: str) -> dict:
        """Account deletion (IT calls it with the Firebase Auth delete): every document, with the index, and the Drive token (revoked, no record left)."""
        return {"files": self.library.erase_account(uid), "drive": self.drive.erase_account(uid)}

    def _scope_documents(self, uid: str, body: dict):
        """The closed-system rule for Documents: whatever the page sent as `library` is dropped; when it names a scope, that scope's
        documents are read HERE, from the verified uid's own library, and handed to the action. -> a refusal dict, or None."""
        args = body.get("args")
        if not isinstance(args, dict):
            return None
        args.pop("library", None)
        sid = args.pop("scope_id", None)
        if sid is None:
            return None
        try:
            mats = self.library.materials(uid, sid)
        except DocsError as e:
            return docs_refusal(e.code)
        if mats:
            args["library"] = mats
        return None

    def _beta_balance(self, uid: str, out: dict, closed) -> None:
        """The balance answer in the beta: the tester's free allowance ("Beta credits remaining"), and, when no call could go out
        now (Bass closed, this tester's share or the whole pool used up, today's limit reached), why, in the tester's words."""
        out["beta"] = True
        if self.research is not None:                 # opt-in sharing state rides the balance answer (no extra round trip); available=false while the switch is off
            try:
                out["research"] = self.research.status(uid)
            except Exception:
                pass
        if out.get("ok") and isinstance(out.get("credits"), (int, float)):
            out["label"] = f"{int(out['credits'])} beta credits remaining"
        why = closed or self.ledger.precheck(uid)
        if why:
            out.update(available=False, code=why, message=POLICIES[why].user_message)

    def _log(self, uid: str, action, out: dict) -> None:
        with self._lock:
            res = self._results.pop(out.get("action_id"), None)
        cr = out.get("credits")
        cr = cr if isinstance(cr, dict) else {}        # balance answers a plain number
        self.meta.write(uid=uid, action=action, status=out.get("status"), code=out.get("code"),
                        credits_spent=cr.get("spent"), credits_refunded=cr.get("refunded"),
                        tool_calls=len(res.tool_calls) if res else 0, out_tokens=res.out_tokens if res else 0)
