"""Opt-in conversation sharing for Bass (alto-bass-optin; Luke L-1101-115150; IT design it/bass-conversation-storage-paper.md).

What it does: for a tester who has said yes, the TEXT of their Bass conversation turns (their words, Bass's reply, a timestamp, the names of the
tools used, the credit count) is written as one small object per turn to a separate research bucket, under a pseudonym path. For everyone else
NOTHING is written. Collection ships DARK: it needs the server-side switch bass_research/switch = {enabled: true}, which is absent (= off) until
Strategy, IT and the independent attack have all cleared it.

Fail closed, in this order, on EVERY turn, all read fresh (no cache): switch on -> consent doc for the VERIFIED uid is on and for the CURRENT
opt-in version -> secret readable -> write. Any store/secret/bucket error, any missing field: nothing is written and the call goes on as before.

Who can do what (three narrow views of the bucket, see FakeObjectStore):
  * the proxy gets CREATE ONLY (cannot read, list or delete);
  * the purge tool gets list + delete (IT runs it, daily and on request);
  * the export tool gets list + read (read-only; every read goes to an access log; the reader is a separate Google login with read-only IAM,
    granted by IT after the sitting; there is no reader UI in the app).
A record carries no uid, email, IP, share link or key, and no document text. Redaction is best effort and the notice must say so.
Mock only: nothing here calls Google; the real adapters live in deploy/bass-proxy/.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import re
import unicodedata
from typing import Callable

PLACEHOLDER_VERSION = "0.0-placeholder"
OPTIN_VERSION = "optin-1"              # the consent text's version (Strategy's stamp, ORG/beta-launch/legal-FINAL/OPTIN-CONSENT-STAMP.md). Any change to the sheet strings or the retention date needs a NEW string: it re-asks every tester. While the version is PLACEHOLDER_VERSION the switch is ignored (IT review 1)
RESEARCH = "research"                  # the action name: {op: status | optin | withdraw, version}
RECORDED = ("propose", "edit", "build")  # the chat/build turns that are saved for an opted-in tester
SWITCH_KEY = "bass_research/switch"    # server-only doc {enabled: true}; absent, unreadable or anything else = OFF
CONSENT_PREFIX = "bass_research_consent/"   # bass_research_consent/<uid>  server-only, written by the proxy only
PURGE_PREFIX = "bass_research_purge/"       # bass_research_purge/<pseudonym>  a purge ticket; it names no one
RETENTION_DAYS = 90                    # the bucket lifecycle rule (IT sets it; Strategy decides the final number)
PURGE_DAYS = 7                         # withdrawal / account deletion: that tester's prefix is purged within this many days
MAX_FIELD_CHARS = 20_000               # per text field, so one record stays small
MAX_TOOLS = 20
OBJECT_PREFIX = "conv/"

_UID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_VER = re.compile(r"^[A-Za-z0-9._-]{1,40}$")


class ResearchError(RuntimeError):
    """The research path could not do it. Callers treat it as 'nothing stored'."""


# -- redaction (best effort, said so in the notice) --------------------------------------------------------------------------
_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u200e\u200f\u2060\u2061\u2062\u2063\u2064\ufeff\u00ad\u180e"))
# LINEAR by construction (IT review of ef092a7: the first version was quadratic): the field is cut to MAX_FIELD_CHARS FIRST, split at whitespace, a
# whitespace-free run over MAX_TOKEN characters is replaced whole, and every pattern runs on one short token (or, for the two that cross a space,
# on a chunk of at most MAX_CHUNK characters), guarded by a cheap substring test so most tokens touch no regex at all.
MAX_TOKEN = 300
MAX_CHUNK = 1000
_JWT = re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*")
_URL_SCHEME = re.compile(r"https?://\S+|\bwww\.\S+", re.I)
_URL_BARE = re.compile(r"^(\W*)(?:[A-Za-z0-9-]+\.){1,8}[A-Za-z]{2,}/\S*")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,255}\.[A-Za-z]{2,}")
_PREFIXED_KEY = re.compile(r"\b(?:sk|pk|rk|AIza|ghp|gho|xox[abp])[-_A-Za-z0-9]{16,}\b")
_RUN = re.compile(r"[A-Za-z0-9_-]{20,}")
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IP6 = re.compile(r"(?<![\w:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![\w:])")
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I)
_PHONE = re.compile(r"(?<![\w.])\+?\d[\d\s().-]{8,}\d(?![\w])")
_SHARE_ALPHABET = frozenset("abcdefghijkmnpqrstuvwxyz23456789")           # a 22-character share/page key with no digit still has only these


def _run_key(m) -> str:
    r = m.group(0)
    mixed = any(c.isdigit() for c in r) and any(c.isalpha() for c in r)
    return "[key]" if mixed or (len(r) == 22 and set(r) <= _SHARE_ALPHABET) else r


def _ip6(m) -> str:
    g = m.group(0)
    return "[ip]" if ("::" in g or any(c in "abcdefABCDEF" for c in g)) else g          # a bare time like 12:30:45 stays


def _token(w: str) -> str:
    if "eyJ" in w:
        w = _JWT.sub("[key]", w)
    if "://" in w or "www." in w.lower():
        w = _URL_SCHEME.sub("[link]", w)
    if "/" in w and "[link]" not in w:
        m = _URL_BARE.match(w)
        if m:
            w = m.group(1) + "[link]"
    if "@" in w:
        w = _EMAIL.sub("[email]", w)
    if len(w) >= 20:
        w = _PREFIXED_KEY.sub("[key]", w)
        w = _RUN.sub(_run_key, w)
        if len(w) >= 32:
            w = re.sub(r"\b[0-9a-fA-F]{32,}\b", "[key]", w)
    if w.count(".") >= 3:
        w = _IPV4.sub("[ip]", w)
    if ":" in w:
        w = _IP6.sub(_ip6, w)
    return w


def _chunk(c: str) -> str:
    if "earer" in c:
        c = _BEARER.sub("[key]", c)
    return _PHONE.sub(lambda m: "[number]" if sum(ch.isdigit() for ch in m.group(0)) >= 9 else m.group(0), c)


def redact(text) -> str:
    s = text if isinstance(text, str) else ""
    s = unicodedata.normalize("NFKC", s[:MAX_FIELD_CHARS]).translate(_ZERO_WIDTH)[:MAX_FIELD_CHARS]       # cut FIRST; fullwidth @ and digits become ASCII, zero-width marks cannot split an address
    parts, out, size = re.split(r"(\s+)", s), [], 0
    chunk = []
    for part in parts:
        if part and not part.isspace():
            part = "[key]" if len(part) > MAX_TOKEN else _token(part)
        chunk.append(part)
        size += len(part)
        if size >= MAX_CHUNK:
            out.append(_chunk("".join(chunk)))
            chunk, size = [], 0
    out.append(_chunk("".join(chunk)))
    return "".join(out)[:MAX_FIELD_CHARS]


def pseudonym(uid: str, secret: str) -> str:
    """HMAC(uid, secret): a stable name for a tester's prefix that names no one. The secret lives in Secret Manager; there is no mapping table."""
    if not isinstance(uid, str) or not _UID.match(uid):
        raise ResearchError("bad uid")
    if not isinstance(secret, str) or len(secret) < 32:
        raise ResearchError("secret missing or too short")
    return hmac.new(secret.encode("utf-8"), uid.encode("utf-8"), hashlib.sha256).hexdigest()[:40]


# -- the bucket: a fake with three narrow views ------------------------------------------------------------------------------
class FakeObjectStore:
    """In-memory stand-in for the research bucket. writer() = create only; admin() = list + delete; reader() = list + read.
    A view that is asked for something it does not hold raises PermissionError, as IAM would. create() refuses to overwrite."""

    def __init__(self):
        self.objects: dict = {}                    # path -> (bytes, created datetime or None)
        self.fail_create = False
        self.reads: list = []                      # the access log the export tool writes (paths only, never content)

    def writer(self):
        return _View(self, {"create"})

    def admin(self):
        return _View(self, {"list", "delete"})

    def reader(self):
        return _View(self, {"list", "read"})

    def expire(self, now: dt.datetime, days: int = RETENTION_DAYS) -> int:
        """What the bucket lifecycle rule does: delete objects older than `days`. -> how many."""
        old = [p for p, (_, t) in self.objects.items() if t is not None and now - t > dt.timedelta(days=days)]
        for p in old:
            del self.objects[p]
        return len(old)

    @staticmethod
    def lifecycle_rule(days: int = RETENTION_DAYS) -> dict:
        return {"rule": [{"action": {"type": "Delete"}, "condition": {"age": days}}]}


class _View:
    def __init__(self, store: FakeObjectStore, can: set):
        self._s, self._can = store, can

    def _need(self, op: str) -> None:
        if op not in self._can:
            raise PermissionError(f"this identity may not {op}")

    def create(self, path: str, data: bytes, when: dt.datetime | None = None) -> None:
        self._need("create")
        if self._s.fail_create:
            raise ResearchError("bucket unavailable")
        if path in self._s.objects:
            raise ResearchError("object exists")           # ifGenerationMatch=0 on GCS: a record is never overwritten
        self._s.objects[path] = (bytes(data), when)

    def list(self, prefix: str) -> list:
        self._need("list")
        return sorted(p for p in self._s.objects if p.startswith(prefix))

    def read(self, path: str) -> bytes:
        self._need("read")
        self._s.reads.append(path)
        return self._s.objects[path][0]

    def delete(self, path: str) -> None:
        self._need("delete")
        self._s.objects.pop(path, None)


# -- the service the proxy uses ----------------------------------------------------------------------------------------------
class ResearchShare:
    """store: the guard store (get/put/run_transaction). objects: a CREATE-ONLY view of the bucket. secret: callable -> the HMAC secret."""

    def __init__(self, store, objects, secret: Callable[[], str], clock: Callable[[], dt.datetime], version: str = OPTIN_VERSION,
                 on_error: Callable[[str, str], None] | None = None):
        self.store, self.objects, self.secret, self.clock, self.version = store, objects, secret, clock, version
        self.on_error = on_error                          # (uid, error code): the guard writes one meta-log line; code only, never conversation text
        self._n = 0

    # -- state, always read fresh ----------------------------------------------------------------------------------
    def enabled(self) -> bool:
        if self.version == PLACEHOLDER_VERSION:               # the consent text is not stamped yet: nobody can be recorded against a placeholder
            return False
        try:
            doc = self.store.get(SWITCH_KEY)
        except Exception:
            return False
        return isinstance(doc, dict) and doc.get("enabled") is True

    def _consent(self, uid: str):
        doc = self.store.get(CONSENT_PREFIX + uid)        # may raise: the caller turns that into 'not collecting'
        return doc if isinstance(doc, dict) else None

    def is_on(self, uid: str) -> bool:
        """True only for this uid, this opt-in version, switched on. Missing, malformed or an error = False."""
        if not isinstance(uid, str) or not _UID.match(uid):
            return False
        try:
            d = self._consent(uid)
        except Exception:
            return False
        return (d is not None and d.get("uid") == uid and d.get("on") is True and d.get("version") == self.version
                and bool(d.get("acceptedAt")))

    # -- the action: {op: status | optin | withdraw} ---------------------------------------------------------------
    def handle(self, uid: str, args) -> dict:
        args = args if isinstance(args, dict) else {}
        op = args.get("op")
        if op == "status":
            return self._ok(**self.status(uid))
        if op == "optin":
            if not self.enabled():
                return self._refuse("research_off")
            if args.get("agree") is not True or args.get("version") != self.version:    # an explicit yes to THIS text, never a default
                return self._refuse("research_version")
            return self._optin(uid)
        if op == "withdraw":
            return self._withdraw(uid)                            # allowed even with the switch off: leaving always works
        return self._refuse("bad_input")

    def status(self, uid: str) -> dict:
        """What the page needs to know: is sharing available at all (switch on), is it on for this tester, which version is current, and must
        the sheet be shown. With the switch off this is ONE store read and the page shows nothing."""
        if not self.enabled():
            return {"available": False, "on": False, "version": self.version, "needs_optin": False}
        on = self.is_on(uid)
        return {"available": True, "on": on, "version": self.version, "needs_optin": not on}

    def _optin(self, uid: str) -> dict:
        now = self.clock().isoformat()

        def work(txn):
            d = txn.get(CONSENT_PREFIX + uid)
            if isinstance(d, dict) and d.get("on") is True and d.get("version") == self.version and d.get("acceptedAt"):
                return                                            # already on for this version: acceptedAt is write-once
            txn.put(CONSENT_PREFIX + uid, {"uid": uid, "version": self.version, "on": True, "acceptedAt": now})
        try:
            self.store.run_transaction(work)
        except Exception:
            return self._refuse("research_error")
        return self._ok(on=True, version=self.version)

    def _withdraw(self, uid: str) -> dict:
        now = self.clock()

        def work(txn):
            d = txn.get(CONSENT_PREFIX + uid)
            if isinstance(d, dict):
                txn.put(CONSENT_PREFIX + uid, {**d, "on": False, "withdrawnAt": now.isoformat()})
        try:
            self.store.run_transaction(work)                      # collection stops on the NEXT request
            self.request_purge(uid)
        except Exception:
            return self._refuse("research_error")
        return self._ok(on=False, version=self.version, purge_within_days=PURGE_DAYS)

    def request_purge(self, uid: str) -> None:
        """A ticket named by the pseudonym (it names no one): the purge tool deletes that tester's prefix within PURGE_DAYS."""
        p = pseudonym(uid, self.secret())
        now = self.clock()
        due, key = now + dt.timedelta(days=PURGE_DAYS), PURGE_PREFIX + p

        def work(txn):                                         # a second request never PUSHES the date out: the earliest ticket wins (IT/attack O2)
            old = txn.get(key)
            when, first = due, now
            try:
                if isinstance(old, dict):
                    when = min(dt.datetime.fromisoformat(old["purgeBy"]), due)
                    first = min(dt.datetime.fromisoformat(old["requestedAt"]), now)
            except Exception:
                when, first = due, now                       # an unreadable old ticket is replaced by a fresh one
            txn.put(key, {"pseudonym": p, "requestedAt": first.isoformat(), "purgeBy": when.isoformat()})
        self.store.run_transaction(work)

    def erase_account(self, uid: str) -> None:
        """Account deletion (next to documents.erase_account): stop, ticket the prefix, drop the consent record."""
        self.request_purge(uid)
        self.store.run_transaction(lambda txn: txn.delete(CONSENT_PREFIX + uid))

    # -- the recorder -----------------------------------------------------------------------------------------------
    def record(self, uid: str, action: str, body, out, tools=()) -> bool:
        """Save one turn. -> True when an object was written. Never raises, never changes the call's answer."""
        try:
            if action not in RECORDED or not isinstance(out, dict) or out.get("ok") is not True:
                return False
            if not self.enabled() or not self.is_on(uid):
                return False
            secret = self.secret()
            p = pseudonym(uid, secret)
            rec = self._record(action, body, out, tools)
            now = self.clock()
            self._n += 1
            path = f"{OBJECT_PREFIX}{p}/{now.strftime('%Y%m%dT%H')}_{self._n:06d}_{hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()[:8]}.json"
            self.objects.create(path, json.dumps(rec, ensure_ascii=False, sort_keys=True).encode("utf-8"), when=now)
            return True
        except Exception as e:                                # nothing is saved and the call goes on; the failure is counted, by class name only
            if self.on_error:
                try:
                    self.on_error(uid, re.sub(r"[^A-Za-z0-9_]", "", type(e).__name__)[:40] or "error")
                except Exception:
                    pass
            return False

    def _record(self, action: str, body, out: dict, tools) -> dict:
        args = body.get("args") if isinstance(body, dict) and isinstance(body.get("args"), dict) else {}
        said = args.get("text") if action == "edit" else args.get("note") if action == "propose" else None   # the student's own words only
        docs_used = bool(args.get("library"))                  # a Documents scope was used: Bass's reply may quote the student's files, so it is NOT stored (attack O5)
        cr = out.get("credits") if isinstance(out.get("credits"), dict) else {}
        names = [str(t)[:60] for t in list(tools)[:MAX_TOOLS]]
        return {"v": 1, "optin_version": self.version, "at": self.clock().replace(minute=0, second=0, microsecond=0).isoformat(), "action": action,     # to the hour (attack O6): exact times would let a record be joined to the meta log by anyone who holds both
                "user": redact(said) if isinstance(said, str) and said.strip() else None,
                "bass": None if docs_used else redact(out.get("message")), "documents_used": docs_used, "tools": names,
                "credits_spent": cr.get("spent") if isinstance(cr.get("spent"), (int, float)) else None}

    @staticmethod
    def _ok(**extra) -> dict:
        return {"ok": True, "status": "ok", "code": None, "message": "", "action_id": None, "work_saved": False, "credits": None,
                "retryable": False, "events": [], "research": extra}

    @staticmethod
    def _refuse(code: str) -> dict:
        from .errors import POLICIES
        return {"ok": False, "status": "error" if code != "research_off" else "paused", "code": code, "message": POLICIES[code].user_message,
                "action_id": None, "work_saved": False, "credits": None, "retryable": False, "events": []}


# -- IT's tools (run by hand / by Cloud Scheduler, never by the proxy) ----------------------------------------------------------
def purge_due(store, admin, now: dt.datetime, only_due: bool = True) -> dict:
    """Delete the prefix of every ticketed tester whose purgeBy has come (or every ticket with only_due=False), then drop the ticket.
    admin = the list+delete view. Answers counts only."""
    done = objs = failed = 0
    for key, doc in store.scan(PURGE_PREFIX):
        try:
            if not isinstance(doc, dict) or not re.match(r"^[0-9a-f]{40}$", str(doc.get("pseudonym", ""))):
                continue
            if only_due and dt.datetime.fromisoformat(doc["purgeBy"]) > now:
                continue
            for path in admin.list(f"{OBJECT_PREFIX}{doc['pseudonym']}/"):
                admin.delete(path)
                objs += 1
            store.run_transaction(lambda txn, k=key: txn.delete(k))
            done += 1
        except Exception:                                      # one bad ticket must not stop the rest; the count is the alarm (attack O3)
            failed += 1
    return {"tickets": done, "objects": objs, "failed": failed}


def export_opted_in(reader, access_log: list, who: str, now: dt.datetime, prefix: str = OBJECT_PREFIX) -> list:
    """Read-only export for the analyst: every record under the prefix, parsed. Every object read is written to access_log (path, who, when;
    never content). The reader can only list and read; this function cannot write, delete or reach anything outside the prefix."""
    if not prefix.startswith(OBJECT_PREFIX):
        raise ResearchError("outside the research prefix")
    out = []
    for path in reader.list(prefix):
        access_log.append({"path": path, "by": who, "at": now.isoformat()})
        out.append(json.loads(reader.read(path).decode("utf-8")))
    return out
