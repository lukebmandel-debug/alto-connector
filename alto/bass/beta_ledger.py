"""The beta ledger: the credits ledger plus the beta's money rules, all inside TRANSACTIONS.

What it adds to ledger.Ledger:
  * a tester's allowance is floor(ceiling / N) per CREDIT PERIOD (the 17th to the 16th). It is granted when the period is open,
    never resets with the calendar day, replaces (never adds to) what is left of the last period, and can never be topped up;
  * every model call's hold is ONE transaction. Order of checks, all fail closed (nothing held, no call):
       switch state: kill switch, bass_beta/disabled (set, or unreadable), the period confirmed
       1. this tester's day (300)      2. this tester's period allowance
       3. all testers' day (1,500)     4. all testers' period ceiling (9,000)
    then the account hold AND the worst-case reservation against the day and period counters;
  * settle books Alto's real cost against the day and period the HOLD was taken in (a call that crosses the boundary settles
    in its own period) and gives the unused reservation back;
  * the reaper (review finding M2): a reservation older than the TTL with no settle belongs to a call that was SENT and then cut off
    (the platform's timeout, a crash). Anthropic billed it, so the reaper BOOKS the whole reservation as Alto's spend (absorbed) on the
    day and period it was taken in, and gives only the tester's own hold back. It never returns an abandoned reservation to the pool;
  * refunds are capped (5 per account per day): past that the cost stays with the account. A refund gives the credits back but the
    cost still counts against that tester's own day (finding M5), so refused or failed actions cannot run past the daily limit.

Docs: `bass_beta/day/<YYYY-MM-DD>` (day counter), `bass_beta/pc/<period id>` (period counter + reservation index),
`bass_beta/periods/<period id>` ({confirmed: true}, written by IT only), `bass_beta/kill`, `bass_beta/disabled`.
Days and periods are the configured zone's calendar.
"""
from __future__ import annotations

import datetime as dt
import time
from typing import Callable

from .beta_config import BetaConfig
from .beta_store import ConflictError, StoreError
from .errors import BassError, InsufficientCredits
from .ledger import Ledger

KILL_KEY = "bass_beta/kill"
DISABLED_KEY = "bass_beta/disabled"
ALLOWLIST_KEY = "bass_beta/allowlist"          # the ALTO cloud beta's list (firestore.rules reads it). Bass does NOT use it (finding S1)
BASS_TESTERS_KEY = "bass_beta/bass_testers"    # who may use Bass: its own list, {"emails": [...]}, edited by hand by Luke or IT
LIVE_GO_KEY = "bass_beta/live_go"


def day_key(day: str) -> str:
    return f"bass_beta/day/{day}"


def pc_key(period: str) -> str:
    return f"bass_beta/pc/{period}"


def confirm_key(period: str) -> str:
    return f"bass_beta/periods/{period}"


def _empty_day(day: str) -> dict:
    return {"day": day, "spent_mc": 0, "reserved_mc": 0, "alerted": []}


def _empty_pc(period: str) -> dict:
    return {"period": period, "spent_mc": 0, "reserved_mc": 0, "res": {}, "alerted": [], "spend_log": [], "reaped": {}}


class TopUpNotAllowed(BassError):
    code = "beta_credits_used"


def _disabled(doc) -> bool:
    """The budget cutoff's flag: the doc exists and does not say off."""
    return doc is not None and doc.get("on", True) is not False


class BetaLedger(Ledger):
    takes_worst_case = True            # the engine passes worst_mc= to hold(): see engine._run

    def __init__(self, store, cfg: BetaConfig, clock: Callable[[], dt.datetime] | None = None, *, sink=None,
                 on_commit: Callable[[dict, dict], None] | None = None, kill=None, sleep: Callable[[float], None] = time.sleep):
        base = clock or (lambda: dt.datetime.now(dt.timezone.utc))
        self._zone = cfg.zone
        super().__init__(store, lambda: base().astimezone(self._zone))
        self.cfg, self.sink = cfg, sink
        self.on_commit = on_commit               # called with (day doc, period doc) after every commit that changed them
        self.kill, self.sleep = kill, sleep      # the switch a settle that cannot be booked trips; the backoff sleep (tests: no-op)

    # -- helpers --------------------------------------------------------------------------------------------------
    def today(self) -> str:
        return self.cfg.day_id(self.clock())

    def period(self) -> str:
        return self.cfg.period_id(self.clock())

    def _inner(self, txn) -> Ledger:
        """A plain Ledger whose reads and writes go through this transaction."""
        return Ledger(txn, self.clock)

    def _txn(self, fn):
        try:
            return self.store.run_transaction(fn, retries=25)         # 20 testers racing one counter: Firestore retries too
        except (ConflictError, StoreError) as e:
            raise BassError(code="bass_paused", detail={"why": type(e).__name__}) from e      # FAIL CLOSED

    def closed_reason(self):
        """None when Bass may spend; else the BassError code that says why not. Read-only (no transaction), fail closed."""
        try:
            kill = self.store.get(KILL_KEY)
            if kill and kill.get("on"):
                return "bass_paused"
            if _disabled(self.store.get(DISABLED_KEY)):
                return "bass_disabled"
            conf = self.store.get(confirm_key(self.period()))
        except StoreError:
            return "bass_disabled"
        return None if conf and conf.get("confirmed") is True else "beta_credits_used"

    def precheck(self, uid: str):
        """A cheap read-only look BEFORE any model call (the hold transaction stays the real check): the BassError code when
        this tester or the whole beta has nothing at all left today or this period, else None. Lets the service answer with
        zero requests, not even the free token count."""
        try:
            day, pid = self.today(), self.period()
            user = self.store.get(uid) or {"day": {}, "holds": {}, "allowance_mc": 0, "lots": [], "allowance_period": ""}
            if user["day"].get(day, 0) + sum(h["mc"] for h in user["holds"].values()) >= self.cfg.tester_daily_mc:
                return "beta_tester_daily"
            left = user["allowance_mc"] + sum(lot["mc"] for lot in user["lots"]) if user["allowance_period"] == pid \
                else self.cfg.allowance_mc
            if left <= 0:
                return "beta_credits_used"
            g = self.store.get(day_key(day)) or _empty_day(day)
            if g["spent_mc"] + g["reserved_mc"] >= self.cfg.daily_ceiling_mc:
                return "beta_daily_full"
            p = self.store.get(pc_key(pid)) or _empty_pc(pid)
            if p["spent_mc"] + p["reserved_mc"] >= self.cfg.ceiling_mc:
                return "beta_credits_used"
        except StoreError:
            return "bass_paused"
        return None

    def _gate(self, txn) -> str:
        kill = txn.get(KILL_KEY)
        if kill and kill.get("on"):
            raise BassError(code="bass_paused", detail={"why": "kill_switch", "reason": kill.get("reason")})
        if _disabled(txn.get(DISABLED_KEY)):
            raise BassError(code="bass_disabled", detail={"why": "disabled_flag"})
        pid = self.period()
        conf = txn.get(confirm_key(pid))
        if not (conf and conf.get("confirmed") is True):
            raise BassError(code="beta_credits_used", detail={"why": "period_unconfirmed", "period": pid})
        return pid

    def _levels(self, doc: dict, limit_mc: int) -> list:
        """Alert levels newly crossed by committed exposure (spent + reserved). Marks them on the doc."""
        used = doc["spent_mc"] + doc["reserved_mc"]
        new = []
        for pct in self.cfg.alert_levels:
            if used * 100 >= pct * limit_mc and pct not in doc["alerted"]:
                doc["alerted"].append(pct)
                new.append(pct)
        return new

    def _after(self, g: dict, p: dict, day_levels: list, period_levels: list) -> None:
        if self.sink is not None:
            for pct in day_levels:
                self.sink.emit("daily_ceiling", percent=pct, used_mc=g["spent_mc"] + g["reserved_mc"],
                               ceiling_mc=self.cfg.daily_ceiling_mc, day=g["day"])
            for pct in period_levels:
                self.sink.emit("period_ceiling", percent=pct, used_mc=p["spent_mc"] + p["reserved_mc"],
                               ceiling_mc=self.cfg.ceiling_mc, period=p["period"])
        if self.on_commit is not None:
            self.on_commit(g, p)

    # -- the beta rules -------------------------------------------------------------------------------------------
    def grant_opening(self, uid: str) -> int:
        """The tester's allowance for the CURRENT period. Idempotent within a period; a new (confirmed) period replaces
        what was left. Raises BassError when the period is not open."""
        out = {}

        def work(txn):
            pid = self._gate(txn)
            out["bal"] = self._inner(txn).grant_allowance(uid, self.cfg.tester_period_credits, period=pid)

        self._txn(work)
        return out["bal"]

    def add_purchase(self, uid, credits, lot_id):          # noqa: D401 - no top-up in the beta
        raise TopUpNotAllowed("the beta has no top-ups")

    def hold(self, uid: str, hold_id: str, mc: int, action_id: str, worst_mc: int | None = None) -> None:
        out = {}
        cfg = self.cfg
        reserve = max(mc, worst_mc or 0)          # what the server-wide counters set aside: the call's true worst case

        def work(txn):
            out.clear()
            pid = self._gate(txn)
            day = self.today()
            led = self._inner(txn)
            led.grant_allowance(uid, cfg.tester_period_credits, period=pid)       # a new period replaces the last one
            user = txn.get(uid)
            inflight = sum(h["mc"] for h in user["holds"].values())
            if user["day"].get(day, 0) + inflight + mc > cfg.tester_daily_mc:                         # 1
                raise BassError(code="beta_tester_daily", detail={"why": "tester_daily"})
            if mc > user["allowance_mc"] + sum(lot["mc"] for lot in user["lots"]):                    # 2
                raise BassError(code="beta_credits_used", detail={"why": "tester_period"})
            g = txn.get(day_key(day)) or _empty_day(day)
            p = txn.get(pc_key(pid)) or _empty_pc(pid)
            refuse = None
            if g["spent_mc"] + g["reserved_mc"] + reserve > cfg.daily_ceiling_mc:                    # 3
                refuse = BassError(code="beta_daily_full", detail={"why": "global_daily", "day": day})
            elif p["spent_mc"] + p["reserved_mc"] + reserve > cfg.ceiling_mc:                        # 4
                refuse = BassError(code="beta_credits_used", detail={"why": "period_ceiling", "period": pid})
            if refuse is None:
                try:
                    led.hold(uid, hold_id, mc, action_id)
                except InsufficientCredits as e:
                    raise BassError(code="beta_credits_used", detail={"why": "tester_period"}) from e
                u2 = txn.get(uid)
                u2["holds"][hold_id]["beta"] = {"period": pid, "day": day}
                txn.put(uid, u2)
                p["res"][hold_id] = {"mc": reserve, "uid": uid, "t": self.clock().timestamp(), "day": day}
                g["reserved_mc"] += reserve
                p["reserved_mc"] += reserve
            out["dl"], out["pl"] = self._levels(g, cfg.daily_ceiling_mc), self._levels(p, cfg.ceiling_mc)
            if refuse is not None and refuse.detail.get("why") == "global_daily" and 100 not in g["alerted"]:
                g["alerted"].append(100)                          # a call that does not fit means the day is full
                out["dl"].append(100)
            if refuse is not None and refuse.detail.get("why") == "period_ceiling" and 100 not in p["alerted"]:
                p["alerted"].append(100)
                out["pl"].append(100)
            out["g"], out["p"], out["refuse"] = g, p, refuse
            txn.put(day_key(day), g)                              # committed even when refusing: the alert marks stick
            txn.put(pc_key(pid), p)

        self._txn(work)
        self._after(out["g"], out["p"], out["dl"], out["pl"])
        if out["refuse"] is not None:
            raise out["refuse"]

    def _book(self, txn, hold_id: str, actual_mc: int, info: dict | None):
        """Move a hold's reservation into spent, in the day and period the hold was taken in (else today's)."""
        pid = (info or {}).get("period") or self.period()
        p = txn.get(pc_key(pid)) or _empty_pc(pid)
        r = p["res"].pop(hold_id, None)
        late = p.setdefault("reaped", {}).pop(hold_id, None) if r is None else None     # the reaper already booked this hold in full
        day = (r or late or {}).get("day") or (info or {}).get("day") or self.today()
        g = txn.get(day_key(day)) or _empty_day(day)
        if r:
            g["reserved_mc"] -= r["mc"]
            p["reserved_mc"] -= r["mc"]
        booked = actual_mc - (late["mc"] if late else 0)       # a late settle replaces the reaper's worst case with the real cost
        g["spent_mc"] += booked
        p["spent_mc"] += booked
        now = self.clock().timestamp()
        p["spend_log"] = [e for e in p["spend_log"] if now - e[0] <= self.cfg.spike_window_s] + [[now, actual_mc]]
        return g, p

    def _commit_books(self, txn, g, p, out):
        out["dl"], out["pl"] = self._levels(g, self.cfg.daily_ceiling_mc), self._levels(p, self.cfg.ceiling_mc)
        out["g"], out["p"] = g, p
        txn.put(day_key(g["day"]), g)
        txn.put(pc_key(p["period"]), p)

    def settle(self, uid: str, hold_id: str, actual_mc: int, *, charge: bool = True, note: str = "") -> dict:
        out = {}

        def work(txn):
            hold = (txn.get(uid) or {}).get("holds", {}).get(hold_id)
            g, p = self._book(txn, hold_id, actual_mc, (hold or {}).get("beta"))
            if hold is None:                      # the reaper got there first: Alto still paid upstream
                out["res"] = {"charged_mc": 0, "released_mc": 0, "absorbed_mc": actual_mc}
            else:
                out["res"] = self._inner(txn).settle(uid, hold_id, actual_mc, charge=charge, note=note)
            self._commit_books(txn, g, p, out)

        last = None
        for attempt in range(max(1, self.cfg.settle_attempts)):
            try:
                self._txn(work)
                break
            except BassError as e:
                if e.code != "bass_paused":
                    raise
                last = e
                if attempt + 1 < self.cfg.settle_attempts:
                    self.sleep(0.25 * 2 ** attempt)            # back off, then try again: the model call was already paid for
        else:
            self._settle_failed(uid, hold_id, actual_mc, last)
            raise last
        self._after(out["g"], out["p"], out["dl"], out["pl"])
        return out["res"]

    def _settle_failed(self, uid: str, hold_id: str, actual_mc: int, err: BassError) -> None:
        """The upstream call is paid for but the books would not take it. The reaper will later RELEASE the hold without booking
        the spend, so the counters would under-count: the books are no longer reliable, so stop Bass for everyone and say exactly what
        is unbooked (uid, hold, credits) so it can be put right by hand. Metadata only."""
        if self.sink is not None:
            self.sink.emit("settle_failed", uid=uid, hold=hold_id, unbooked_mc=actual_mc, why=(err.detail or {}).get("why"))
        if self.kill is not None:
            self.kill.trip("settle_failed", hold=hold_id, unbooked_mc=actual_mc)

    def release(self, uid: str, hold_id: str) -> int:
        out = {}

        def work(txn):
            hold = (txn.get(uid) or {}).get("holds", {}).get(hold_id)
            if hold is not None:
                info = hold.get("beta") or {}
                p = txn.get(pc_key(info.get("period") or self.period())) or _empty_pc(self.period())
                r = p["res"].pop(hold_id, None)
                if r:
                    g = txn.get(day_key(r["day"])) or _empty_day(r["day"])
                    g["reserved_mc"] -= r["mc"]
                    p["reserved_mc"] -= r["mc"]
                    txn.put(day_key(r["day"]), g)
                    txn.put(pc_key(p["period"]), p)
            out["mc"] = self._inner(txn).release(uid, hold_id)

        self._txn(work)
        return out["mc"]

    def absorb(self, uid: str, action_id: str, mc: int, note: str) -> None:
        """Alto's own cost (the gate call): never debited from the tester, but it IS spend against the day and period."""
        out = {}

        def work(txn):
            g, p = self._book(txn, "-", mc, None)
            self._commit_books(txn, g, p, out)
            self._inner(txn).absorb(uid, action_id, mc, note)

        self._txn(work)
        self._after(out["g"], out["p"], out["dl"], out["pl"])

    def refund(self, uid: str, action_id: str, reason: str, mc: int | None = None) -> int:
        """Capped: past refunds_per_day refunds today the account keeps the cost (a refund loop gains nothing)."""
        out = {}

        def work(txn):
            doc = txn.get(uid) or {"entries": []}
            today = self.today()
            n = sum(1 for e in doc["entries"] if e["kind"] == "refund" and e["t"][:10] == today)
            out["denied"] = n >= self.cfg.refunds_per_day
            out["mc"] = 0 if out["denied"] else self._inner(txn).refund(uid, action_id, reason, mc)
            after = txn.get(uid)
            if after is not None and after.get("day") != doc.get("day") and "day" in doc:
                after["day"] = doc["day"]             # M5: the credits went back; the cost still counts against this tester's day
                txn.put(uid, after)

        self._txn(work)
        if out["denied"] and self.sink is not None:
            self.sink.emit("refund_capped", uid=uid, action=action_id)
        return out["mc"]

    # -- the reaper -----------------------------------------------------------------------------------------------
    def reap(self, max_age_s: int | None = None) -> int:
        """Every reservation older than max_age_s that was never settled is an ABANDONED CALL (cut off after it was sent): its whole
        reservation is booked as Alto's spend on the day and period it was taken in, and the tester's own hold is given back.
        -> how many were booked. Looks at this period and the one before."""
        age = self.cfg.reservation_ttl_s if max_age_s is None else max_age_s
        now = self.clock().timestamp()
        freed = {"n": 0}
        cur = self.period()
        prev = self.cfg.period_id(dt.datetime.fromisoformat(cur + "T00:00:00").replace(tzinfo=self._zone) - dt.timedelta(days=1))

        def work(txn):
            freed["n"], freed["mc"] = 0, 0
            led = self._inner(txn)
            for pid in (cur, prev):
                p = txn.get(pc_key(pid))
                if not p:
                    continue
                reaped = p.setdefault("reaped", {})
                for hid in [h for h, v in reaped.items() if now - v["t"] > 86400]:
                    del reaped[hid]                                   # a settle this late is not coming
                days = {}
                for hold_id, r in list(p["res"].items()):
                    if now - r["t"] < age:
                        continue
                    hold = ((txn.get(r["uid"]) or {}).get("holds") or {}).get(hold_id)
                    led.release(r["uid"], hold_id)                    # the tester gets their own hold back
                    led.absorb(r["uid"], (hold or {}).get("action", ""), r["mc"], "abandoned call: booked at its reservation")
                    g = days.get(r["day"]) or txn.get(day_key(r["day"])) or _empty_day(r["day"])
                    days[r["day"]] = g
                    g["reserved_mc"] -= r["mc"]
                    p["reserved_mc"] -= r["mc"]
                    g["spent_mc"] += r["mc"]                          # ... and the books keep the cost: it was sent, so it was billed
                    p["spent_mc"] += r["mc"]
                    reaped[hold_id] = {"mc": r["mc"], "day": r["day"], "t": now}
                    del p["res"][hold_id]
                    freed["n"] += 1
                    freed["mc"] += r["mc"]
                for g in days.values():
                    txn.put(day_key(g["day"]), g)
                txn.put(pc_key(pid), p)

        self._txn(work)
        if freed["n"] and self.sink is not None:
            self.sink.emit("abandoned_calls_booked", count=freed["n"], absorbed_mc=freed["mc"])
        return freed["n"]


def _closed_on_store_error(fn):
    """A read the guards depend on: if the store cannot answer, Bass is paused (fail closed), never a stack trace."""
    def wrapped(*a, **k):
        try:
            return fn(*a, **k)
        except StoreError as e:
            raise BassError(code="bass_paused", detail={"why": type(e).__name__}) from e
    wrapped.__name__, wrapped.__doc__ = fn.__name__, fn.__doc__
    return wrapped


for _n in ("balance_mc", "entries", "action_spent_mc", "spent_today_mc", "spent_month_mc", "held_mc"):
    setattr(BetaLedger, _n, _closed_on_store_error(getattr(Ledger, _n)))
