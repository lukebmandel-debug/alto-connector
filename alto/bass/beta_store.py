"""The store the beta guards run on, and a transactional fake of it.

Interface (what a Firestore adapter implements; IT writes that one):
    get(key) -> dict | None        put(key, doc)
    run_transaction(fn, retries=5) -> fn's result.  fn(txn) reads with txn.get(key), writes with txn.put(key, doc);
                                   the writes land all-or-nothing, and the whole fn re-runs when something it read
                                   changed underneath it (optimistic concurrency). fn must have no side effects besides
                                   txn.put, because it can run more than once.

READS BEFORE WRITES (review finding B1). Firestore refuses a read that follows a write inside one transaction. The guards' code reads
and writes in whatever order is clearest, so every store hands fn a DeferredWrites view: reads go to the store's own transaction (and are
remembered), writes are only buffered (a later read of the same key sees them), and the buffer is flushed to the real transaction after
fn returns. Whatever fn does, the real transaction sees every read before the first write. FakeStore's raw transaction ENFORCES the
Firestore rule (a raw read after a raw write is a StoreError), so a guard path that slipped past the view would fail every test.

FakeStore is that, in memory, plus the faults the guard tests need: injected conflicts, an injected store outage, and a
crash right after the hold commits (the "function died before it released" case the reaper exists for).
"""
from __future__ import annotations

import copy
import json
import threading

# Firestore refuses a document over 1 MiB (1,048,576 bytes, field names included). The store refuses a bit below it, so an oversized write
# is a StoreError the caller sees (and turns into a plain message), never a silent truncation or a half-written transaction.
MAX_DOC_BYTES = 1_000_000


def doc_bytes(doc) -> int:
    return len(json.dumps(doc, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8"))


def check_size(doc) -> None:
    if doc_bytes(doc) > MAX_DOC_BYTES:
        raise StoreError("document too large")


class StoreError(RuntimeError):
    """The store is unavailable. The guards FAIL CLOSED on it: no hold, no call."""


class ConflictError(StoreError):
    """A transaction lost a race and ran out of retries."""


class SimulatedCrash(BaseException):
    """The process died. BaseException so no `except Exception` in the code under test can swallow it."""


class ReadAfterWrite(StoreError):
    """A transaction read a document after it had written one: Firestore refuses that (google.cloud.firestore ReadAfterWriteError)."""


_GONE = object()


class DeferredWrites:
    """The view of a store transaction that fn works on: every real read happens before the first real write (see the module docstring).
    `raw` is the store's own transaction (get / put / delete)."""

    def __init__(self, raw):
        self._raw, self._seen, self._w = raw, {}, {}

    def get(self, key: str):
        if key in self._w:
            d = self._w[key]
            return None if d is _GONE else copy.deepcopy(d)
        if key not in self._seen:
            self._seen[key] = self._raw.get(key)
        d = self._seen[key]
        return copy.deepcopy(d) if d is not None else None

    def put(self, key: str, doc: dict) -> None:
        check_size(doc)
        self._w[key] = copy.deepcopy(doc)

    def delete(self, key: str) -> None:
        self._w[key] = _GONE

    def flush(self) -> None:
        for key, d in self._w.items():
            if d is _GONE:
                self._raw.delete(key)
            else:
                self._raw.put(key, d)


def reads_first(fn):
    """fn(txn) -> the same fn working on a DeferredWrites view, flushed when it returns."""
    def run(raw):
        view = DeferredWrites(raw)
        out = fn(view)
        view.flush()
        return out
    return run


class _Txn:
    def __init__(self, store: "FakeStore"):
        self._s = store
        self._reads: dict[str, int] = {}
        self.writes: dict[str, dict] = {}

    def get(self, key: str):
        if self.writes:
            raise ReadAfterWrite("read after write in a transaction: " + key)      # what Firestore does
        self._s._check_key(key)
        with self._s._lock:
            self._reads.setdefault(key, self._s._ver.get(key, 0))
            d = self._s.docs.get(key)
            return copy.deepcopy(d) if d is not None else None

    def put(self, key: str, doc: dict) -> None:
        check_size(doc)
        self.writes[key] = copy.deepcopy(doc)

    def delete(self, key: str) -> None:
        self.writes[key] = None


class FakeStore:
    def __init__(self, auto_terms: bool = False, defer_writes: bool = True):
        # defer_writes=False hands fn the RAW transaction (what the Firestore adapter did before finding B1 was fixed): only the test that
        # proves the fix uses it.
        self.defer_writes = defer_writes
        # auto_terms: every terms_acceptance/<uid>_<version> read that was not written explicitly answers with a valid acceptance (for the
        # tests that are about something else than the terms gate; the gate's own tests use the default False and accept_terms()).
        self.auto_terms = auto_terms
        self.docs: dict[str, dict] = {}
        self._ver: dict[str, int] = {}
        self._lock = threading.RLock()
        self._conflicts = 0
        self._crash_after = None          # commits left before the crash
        self._down = None
        self._unreadable: set = set()
        self.commits = 0
        self.attempts = 0

    # -- plain access ---------------------------------------------------------------------------------------------
    def get(self, key: str):
        self._check_up()
        self._check_key(key)
        with self._lock:
            d = self.docs.get(key)
            if d is None:
                d = self._auto_terms(key)
            return copy.deepcopy(d) if d is not None else None

    def scan(self, prefix: str):
        """(key, doc) under a prefix; "" = the account ledgers (keys with no "/"). Same contract as the Firestore adapter's scan."""
        with self._lock:
            items = sorted(self.docs.items())
        for k, d in items:
            if (k.startswith(prefix) and prefix) or (not prefix and "/" not in k):
                yield k, copy.deepcopy(d)

    def accept_terms(self, uid: str, version: str, **over) -> None:
        """What the page writes after the box is ticked: terms_acceptance/<uid>_<version>. `over` replaces or adds fields."""
        doc = {"uid": uid, "version": version, "ageConfirmed": True, "acceptedAt": "2026-10-30T12:00:00Z"}
        doc.update(over)
        self.put(f"terms_acceptance/{uid}_{version}", doc)

    def _auto_terms(self, key: str):
        if self.auto_terms and key.startswith("terms_acceptance/") and "_" in key:
            uid, ver = key.split("/", 1)[1].rsplit("_", 1)
            return {"uid": uid, "version": ver, "ageConfirmed": True, "acceptedAt": "2026-10-30T12:00:00Z"}
        return None

    def put(self, key: str, doc: dict) -> None:
        self._check_up()
        check_size(doc)
        with self._lock:
            self.docs[key] = copy.deepcopy(doc)
            self._ver[key] = self._ver.get(key, 0) + 1

    # -- transactions ---------------------------------------------------------------------------------------------
    def run_transaction(self, fn, retries: int = 5):
        for _ in range(max(1, retries)):
            self._check_up()
            txn = _Txn(self)
            self.attempts += 1
            result = (reads_first(fn) if self.defer_writes else fn)(txn)        # any exception: nothing is written
            with self._lock:
                self._check_up()
                stale = self._conflicts > 0 or any(self._ver.get(k, 0) != v for k, v in txn._reads.items())
                if self._conflicts > 0:
                    self._conflicts -= 1
                if stale:
                    continue
                for k, d in txn.writes.items():
                    if d is None:
                        self.docs.pop(k, None)
                    else:
                        self.docs[k] = d
                    self._ver[k] = self._ver.get(k, 0) + 1
                self.commits += 1
                crash = self._crash_after is not None and self.commits > self._crash_after
                if crash:
                    self._crash_after = None
            if crash:
                raise SimulatedCrash("the function died right after this commit")
            return result
        raise ConflictError("the transaction kept conflicting")

    # -- fault injection --------------------------------------------------------------------------------------------
    def inject_conflicts(self, n: int) -> None:
        """The next n commit attempts fail as if another writer got there first."""
        self._conflicts = n

    def crash_after_commits(self, n: int) -> None:
        """After n more successful commits, the next commit lands and then SimulatedCrash is raised (the caller never
        sees the result). n=0: the very next commit."""
        self._crash_after = self.commits + n

    def go_down(self, down: bool = True) -> None:
        self._down = StoreError("store unavailable") if down else None

    def make_unreadable(self, key: str, unreadable: bool = True) -> None:
        """Reads of this one doc fail with StoreError (the rest of the store works): a doc whose state cannot be known."""
        (self._unreadable.add if unreadable else self._unreadable.discard)(key)

    def _check_key(self, key: str) -> None:
        if key in self._unreadable:
            raise StoreError("unreadable: " + key)

    def _check_up(self) -> None:
        if self._down is not None:
            raise self._down
