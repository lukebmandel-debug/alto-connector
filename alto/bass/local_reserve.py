"""The LOCAL reserve: the $10 of each credit period set aside for Luke's own Mac (review finding M3).

Before this there were three separate pots, none tied to the credit period: tools/bass_live_check.py made a fresh in-memory $10 on every
run, and tools/bass_local_server.py granted $5 to each `--purpose` under whatever `--store-root` it was given, so a new root was a new
grant. Now there is ONE file,

    ~/Library/Application Support/Alto-bass-local/reserve.json        (RESERVE_FILE; not in an iCloud-synced folder)

and every local spender (the live check, the local server's `own` and `runs` purposes) takes its holds from it and books its real cost
into it, per credit period (the 17th, BetaConfig.period_id). The total over ALL of them can never pass cap_credits (1,000 = $10) in a
period, whichever tool, purpose or directory is used, and across restarts and processes (a file lock serialises them).

Rules:
  * hold(source, hold_id, mc) BEFORE a call: refused (InsufficientCredits) when spent + open holds + mc would pass the cap.
  * settle(hold_id, actual_mc) books the real cost; release(hold_id) gives a hold back ONLY for a call that provably cost nothing;
    absorb(source, mc) books a cost that had no hold (the off-topic gate).
  * a hold older than `ttl_s` with no settle is an abandoned call: it is booked in full (the same rule as the hosted reaper, finding M2).
  * a NEW credit period is not opened by the calendar. The first period is opened when the file is first created; every later one only by
    open_period(), which a human runs after Luke confirms the credit refreshed. An unopened period refuses every hold.
  * LIVE use must use RESERVE_FILE. Any other path is refused for live calls (require_fixed); tests and mock runs pass their own file,
    because mock money must never be booked against the real reserve.
The file holds numbers only: period ids, source names, hold ids, milli-credits, timestamps.
"""
from __future__ import annotations

import datetime as dt
import fcntl
import json
import os
from pathlib import Path
from typing import Callable

from .beta_config import BetaConfig
from .errors import BassError, InsufficientCredits

MC = 1000
RESERVE_FILE = Path.home() / "Library" / "Application Support" / "Alto-bass-local" / "reserve.json"
CAP_CREDITS = 1000                    # $10 per credit period, every local spender together
TTL_S = 900


class WrongReserve(BassError):
    """A live call was about to use a reserve file other than the fixed one."""
    code = "bass_paused"


class LocalReserve:
    def __init__(self, path: Path | str | None = None, *, cap_credits: int = CAP_CREDITS, clock: Callable[[], dt.datetime] | None = None,
                 cfg: BetaConfig | None = None, ttl_s: int = TTL_S):
        self.path = Path(RESERVE_FILE if path is None else path).expanduser()      # looked up at call time
        self.cap_mc = int(cap_credits) * MC
        self.clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))
        self.cfg = cfg or BetaConfig(testers=1)
        self.ttl_s = ttl_s

    # -- which file ---------------------------------------------------------------------------------------------------------
    def is_fixed(self) -> bool:
        return self.path.resolve() == RESERVE_FILE.expanduser().resolve()

    def require_fixed(self) -> None:
        if not self.is_fixed():
            raise WrongReserve(f"live calls use the one fixed reserve file ({RESERVE_FILE}); refusing {self.path}")

    # -- the file, under a lock -----------------------------------------------------------------------------------------------
    def period(self) -> str:
        return self.cfg.period_id(self.clock())

    def _locked(self, fn):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path.with_suffix(".lock"), "a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                fresh = not self.path.is_file()
                doc = {"periods": {}} if fresh else json.loads(self.path.read_text("utf-8"))
                if fresh:                                   # the first period is opened with the file, and never again by itself
                    doc["periods"][self.period()] = self._new_period("first use")
                now = self.clock().timestamp()
                for p in doc["periods"].values():           # abandoned calls: booked in full, never returned
                    for hid, h in list(p["holds"].items()):
                        if now - h["t"] >= self.ttl_s:
                            p["spent"][h["source"]] = p["spent"].get(h["source"], 0) + h["mc"]
                            p["abandoned_mc"] = p.get("abandoned_mc", 0) + h["mc"]
                            del p["holds"][hid]
                out = fn(doc)
                tmp = self.path.with_suffix(".tmp")
                tmp.write_text(json.dumps(doc, sort_keys=True, indent=1), "utf-8")
                os.replace(tmp, self.path)
                return out
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _new_period(self, why: str) -> dict:
        return {"opened": self.clock().isoformat(), "why": why, "cap_mc": self.cap_mc, "spent": {}, "holds": {}}

    @staticmethod
    def _used(p: dict) -> int:
        return sum(p["spent"].values()) + sum(h["mc"] for h in p["holds"].values())

    def _open(self, doc: dict) -> dict:
        p = doc["periods"].get(self.period())
        if p is None:
            raise BassError(code="beta_credits_used", detail={"why": "local_period_unopened", "period": self.period()})
        return p

    # -- the rules ------------------------------------------------------------------------------------------------------------
    def open_period(self, why: str = "confirmed by hand") -> str:
        """Open the CURRENT credit period (idempotent). Run by a human after Luke confirms the credit refreshed."""
        def work(doc):
            doc["periods"].setdefault(self.period(), self._new_period(why))
            return self.period()
        return self._locked(work)

    def hold(self, source: str, hold_id: str, mc: int) -> None:
        def work(doc):
            p = self._open(doc)
            cap = min(self.cap_mc, int(p.get("cap_mc", self.cap_mc)))
            if self._used(p) + mc > cap:
                raise InsufficientCredits(detail={"why": "local_reserve", "needed_mc": mc, "left_mc": max(0, cap - self._used(p))})
            p["holds"][hold_id] = {"source": source, "mc": int(mc), "t": self.clock().timestamp()}
        self._locked(work)

    def _find(self, doc: dict, hold_id: str):
        for p in doc["periods"].values():
            if hold_id in p["holds"]:
                return p
        return None

    def settle(self, hold_id: str, actual_mc: int, source: str = "") -> None:
        def work(doc):
            p = self._find(doc, hold_id)
            h = p["holds"].pop(hold_id) if p else None
            p = p or doc["periods"].get(self.period()) or next(reversed(list(doc["periods"].values())))
            src = (h or {}).get("source") or source or "unknown"
            p["spent"][src] = p["spent"].get(src, 0) + int(actual_mc)       # the cost is real whatever happened to the hold
        self._locked(work)

    def release(self, hold_id: str) -> None:
        def work(doc):
            p = self._find(doc, hold_id)
            if p:
                del p["holds"][hold_id]
        self._locked(work)

    def absorb(self, source: str, mc: int) -> None:
        def work(doc):
            p = doc["periods"].get(self.period()) or next(reversed(list(doc["periods"].values())))
            p["spent"][source] = p["spent"].get(source, 0) + int(mc)
        self._locked(work)

    def status(self) -> dict:
        """Numbers only, for the tools' own output."""
        def work(doc):
            p = doc["periods"].get(self.period())
            if p is None:
                return {"period": self.period(), "open": False, "cap_credits": self.cap_mc / MC, "left_credits": 0.0}
            cap = min(self.cap_mc, int(p.get("cap_mc", self.cap_mc)))
            return {"period": self.period(), "open": True, "cap_credits": cap / MC, "used_credits": self._used(p) / MC,
                    "left_credits": max(0, cap - self._used(p)) / MC, "by_source_credits": {k: v / MC for k, v in sorted(p["spent"].items())}}
        return self._locked(work)

    def left_mc(self) -> int:
        return int(round(self.status()["left_credits"] * MC))


class ReservedLedger:
    """Any ledger (ledger.Ledger or beta_ledger.BetaLedger), with every hold also taken from the local reserve and every real cost booked
    into it. Everything else (balances, refunds, reads) is the inner ledger's. The reserve is asked FIRST: when it refuses, nothing is held
    anywhere and no call is made."""

    def __init__(self, inner, reserve: LocalReserve, source: str):
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_reserve", reserve)
        object.__setattr__(self, "_source", source)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_inner"), name)

    def hold(self, uid, hold_id, mc, action_id, worst_mc=None):
        amount = max(int(mc), int(worst_mc or 0))
        self._reserve.hold(self._source, hold_id, amount)
        try:
            if worst_mc is not None and getattr(self._inner, "takes_worst_case", False):
                self._inner.hold(uid, hold_id, mc, action_id, worst_mc=worst_mc)
            else:
                self._inner.hold(uid, hold_id, mc, action_id)
        except BaseException:
            self._reserve.release(hold_id)                 # nothing was sent: the hold was refused before any call
            raise

    def settle(self, uid, hold_id, actual_mc, **kw):
        try:
            return self._inner.settle(uid, hold_id, actual_mc, **kw)
        finally:
            self._reserve.settle(hold_id, actual_mc, self._source)       # the cost is booked even if the inner books failed

    def release(self, uid, hold_id):
        try:
            return self._inner.release(uid, hold_id)
        finally:
            self._reserve.release(hold_id)

    def absorb(self, uid, action_id, mc, note):
        try:
            return self._inner.absorb(uid, action_id, mc, note)
        finally:
            self._reserve.absorb(self._source, mc)
