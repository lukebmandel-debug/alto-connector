"""The credits ledger. Integer milli-credits, append-only entries, never negative.

Flow for every model call:  hold(estimate) -> call -> settle(actual from `usage`) -> leftover released.
A hold that would overdraw the balance fails BEFORE the call. Spend order: monthly allowance first, then purchased
lots (earliest expiry first). The store interface is the one a Firestore `credits/{uid}` doc would have: get(uid) /
put(uid, doc). In production the get/modify/put runs in a transaction; here a lock stands in for it.

Entry kinds: allowance, purchase, expire, hold (implicit in the doc), usage, release, refund, absorbed.
`absorbed` = cost Alto ate (the off-topic gate, an estimate that came in low); it never debits the user.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import threading
from pathlib import Path
from typing import Callable

from . import config as P
from .errors import CapReached, InsufficientCredits


class MemoryStore:
    def __init__(self):
        self.docs: dict[str, dict] = {}

    def get(self, uid: str):
        d = self.docs.get(uid)
        return copy.deepcopy(d) if d is not None else None

    def put(self, uid: str, doc: dict) -> None:
        self.docs[uid] = copy.deepcopy(doc)


class JsonFileStore:
    def __init__(self, folder):
        self.dir = Path(folder)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _p(self, uid):
        return self.dir / (uid.replace("/", "_") + ".json")

    def get(self, uid):
        p = self._p(uid)
        return json.loads(p.read_text("utf-8")) if p.is_file() else None

    def put(self, uid, doc):
        p = self._p(uid)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, sort_keys=True), "utf-8")
        tmp.replace(p)


def _empty(uid: str) -> dict:
    return {"uid": uid, "allowance_mc": 0, "allowance_period": "", "lots": [], "holds": {}, "actions": {},
            "entries": [], "day": {}, "month": {}}


class Ledger:
    def __init__(self, store=None, clock: Callable[[], dt.datetime] | None = None):
        self.store = store or MemoryStore()
        self.clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))
        self._lock = threading.RLock()

    # -- plumbing -----------------------------------------------------------------------------------------------
    def _load(self, uid: str) -> dict:
        d = self.store.get(uid) or _empty(uid)
        self._expire(d)
        return d

    def _save(self, d: dict) -> None:
        self.store.put(d["uid"], d)

    def _entry(self, d: dict, kind: str, mc: int, **kw) -> dict:
        e = {"n": len(d["entries"]) + 1, "t": self.clock().isoformat(), "kind": kind, "mc": int(mc)}
        e.update(kw)
        d["entries"].append(e)
        return e

    def _expire(self, d: dict) -> None:
        now = self.clock().isoformat()
        keep = []
        for lot in d["lots"]:
            if lot["expires"] <= now and lot["mc"] > 0:
                self._entry(d, "expire", -lot["mc"], lot=lot["id"])
            elif lot["expires"] > now or lot["mc"] > 0:
                keep.append(lot)
        d["lots"] = [lot for lot in keep if lot["expires"] > now]

    @staticmethod
    def _available(d: dict) -> int:
        return d["allowance_mc"] + sum(lot["mc"] for lot in d["lots"])

    def _take(self, d: dict, mc: int) -> dict:
        """Remove up to `mc` from the buckets in spend order. -> {"allowance": n, "lots": {id: n}} (sums to taken)."""
        out = {"allowance": 0, "lots": {}}
        a = min(mc, d["allowance_mc"])
        d["allowance_mc"] -= a
        out["allowance"], mc = a, mc - a
        for lot in sorted(d["lots"], key=lambda l: l["expires"]):
            if mc <= 0:
                break
            t = min(mc, lot["mc"])
            lot["mc"] -= t
            mc -= t
            if t:
                out["lots"][lot["id"]] = t
        return out

    def _give(self, d: dict, alloc: dict, limit: int | None = None) -> int:
        """Put an allocation back (allowance only if its period is still current). -> mc actually returned."""
        back = 0
        left = limit if limit is not None else 10 ** 15
        a = min(alloc.get("allowance", 0), left)
        if a and alloc.get("period", d["allowance_period"]) == d["allowance_period"]:
            d["allowance_mc"] += a
            back += a
        left -= a
        for lid, n in alloc.get("lots", {}).items():
            if left <= 0:
                break
            t = min(n, left)
            for lot in d["lots"]:
                if lot["id"] == lid:
                    lot["mc"] += t
                    back += t
                    break
            left -= t
        return back

    @staticmethod
    def _merge(into: dict, add: dict) -> None:
        into["allowance"] = into.get("allowance", 0) + add.get("allowance", 0)
        for k, v in add.get("lots", {}).items():
            into.setdefault("lots", {})
            into["lots"][k] = into["lots"].get(k, 0) + v

    @staticmethod
    def _total(alloc: dict) -> int:
        return alloc.get("allowance", 0) + sum(alloc.get("lots", {}).values())

    # -- credits in ---------------------------------------------------------------------------------------------
    def grant_allowance(self, uid: str, credits: float, period: str | None = None) -> int:
        """The monthly allowance: replaces what is left of the last one (no rollover). Idempotent per period."""
        mc = int(round(credits * P.MC))
        with self._lock:
            d = self._load(uid)
            period = period or self.clock().strftime("%Y-%m")
            if d["allowance_period"] == period:
                return self._available(d)
            if d["allowance_mc"]:
                self._entry(d, "expire", -d["allowance_mc"], what="allowance", period=d["allowance_period"])
            d["allowance_mc"], d["allowance_period"] = mc, period
            self._entry(d, "allowance", mc, period=period)
            self._save(d)
            return self._available(d)

    def add_purchase(self, uid: str, credits: float, lot_id: str) -> int:
        mc = int(round(credits * P.MC))
        with self._lock:
            d = self._load(uid)
            if any(l["id"] == lot_id for l in d["lots"]) or any(
                    e.get("lot") == lot_id and e["kind"] == "purchase" for e in d["entries"]):
                return self._available(d)             # replay of the same payment
            exp = (self.clock() + dt.timedelta(days=P.PURCHASE_LIFETIME_DAYS)).isoformat()
            d["lots"].append({"id": lot_id, "mc": mc, "expires": exp})
            self._entry(d, "purchase", mc, lot=lot_id, expires=exp)
            self._save(d)
            return self._available(d)

    # -- reads --------------------------------------------------------------------------------------------------
    def balance_mc(self, uid: str) -> int:
        with self._lock:
            return self._available(self._load(uid))

    def entries(self, uid: str) -> list:
        with self._lock:
            return list(self._load(uid)["entries"])

    def action_spent_mc(self, uid: str, action_id: str) -> int:
        with self._lock:
            a = self._load(uid)["actions"].get(action_id)
            return (a["spent"] - a["refunded"]) if a else 0

    def spent_today_mc(self, uid: str) -> int:
        with self._lock:
            return self._load(uid)["day"].get(self.clock().strftime("%Y-%m-%d"), 0)

    def spent_month_mc(self, uid: str) -> int:
        with self._lock:
            return self._load(uid)["month"].get(self.clock().strftime("%Y-%m"), 0)

    # -- hold / settle / refund ---------------------------------------------------------------------------------
    def hold(self, uid: str, hold_id: str, mc: int, action_id: str) -> None:
        if mc <= 0:
            raise ValueError("a hold must be positive")
        with self._lock:
            d = self._load(uid)
            if hold_id in d["holds"]:
                raise ValueError(f"hold {hold_id} already exists")
            if mc > self._available(d):
                raise InsufficientCredits(detail={"needed_mc": mc, "available_mc": self._available(d)})
            day, month = self.clock().strftime("%Y-%m-%d"), self.clock().strftime("%Y-%m")
            inflight = sum(h["mc"] for h in d["holds"].values())
            if d["day"].get(day, 0) + inflight + mc > P.DAILY_CEILING_CREDITS * P.MC:
                raise CapReached(code="daily_cap")
            if d["month"].get(month, 0) + inflight + mc > P.MONTHLY_CEILING_CREDITS * P.MC:
                raise CapReached(code="monthly_cap")
            alloc = self._take(d, mc)
            alloc["period"] = d["allowance_period"]
            d["holds"][hold_id] = {"mc": mc, "action": action_id, "from": alloc}
            self._save(d)

    def settle(self, uid: str, hold_id: str, actual_mc: int, *, charge: bool = True, note: str = "") -> dict:
        """Charge `actual_mc` against the hold and release the rest. charge=False: the whole hold goes back and the
        cost is recorded as absorbed. Returns {"charged_mc", "released_mc", "absorbed_mc"}."""
        with self._lock:
            d = self._load(uid)
            h = d["holds"].pop(hold_id)
            alloc, hold_mc = h["from"], h["mc"]
            if not charge:
                self._give(d, alloc)
                self._entry(d, "absorbed", actual_mc, action=h["action"], note=note)
                self._entry(d, "release", hold_mc, hold=hold_id)
                self._save(d)
                return {"charged_mc": 0, "released_mc": hold_mc, "absorbed_mc": actual_mc}
            use = min(actual_mc, hold_mc)
            # the used part comes out of the held allocation in spend order; the rest goes back
            kept = {"allowance": 0, "lots": {}, "period": alloc.get("period")}
            back = {"allowance": 0, "lots": {}, "period": alloc.get("period")}
            need = use
            a = min(need, alloc.get("allowance", 0))
            kept["allowance"], back["allowance"], need = a, alloc.get("allowance", 0) - a, need - a
            for lid, n in alloc.get("lots", {}).items():
                t = min(need, n)
                if t:
                    kept["lots"][lid] = t
                if n - t:
                    back["lots"][lid] = n - t
                need -= t
            released = self._give(d, back)
            absorbed = 0
            if actual_mc > hold_mc:          # the estimate was low: take what is there, Alto eats the rest
                extra = self._take(d, min(actual_mc - hold_mc, self._available(d)))
                extra["period"] = alloc.get("period")
                self._merge(kept, extra)
                absorbed = actual_mc - hold_mc - self._total(extra)
            charged = self._total(kept)
            act = d["actions"].setdefault(h["action"], {"spent": 0, "refunded": 0, "from": {}})
            act["spent"] += charged
            self._merge(act["from"], {k: v for k, v in kept.items() if k != "period"})
            act["from"]["period"] = alloc.get("period")
            day, month = self.clock().strftime("%Y-%m-%d"), self.clock().strftime("%Y-%m")
            d["day"][day] = d["day"].get(day, 0) + charged
            d["month"][month] = d["month"].get(month, 0) + charged
            self._entry(d, "usage", -charged, action=h["action"], hold=hold_id, note=note)
            if released:
                self._entry(d, "release", released, hold=hold_id)
            if absorbed:
                self._entry(d, "absorbed", absorbed, action=h["action"], note="estimate was low")
            self._save(d)
            return {"charged_mc": charged, "released_mc": released, "absorbed_mc": absorbed}

    def release(self, uid: str, hold_id: str) -> int:
        """Drop a hold with nothing used (the call never produced anything). Not a cost to anyone."""
        with self._lock:
            d = self._load(uid)
            h = d["holds"].pop(hold_id, None)
            if not h:
                return 0
            self._give(d, h["from"])
            self._entry(d, "release", h["mc"], hold=hold_id)
            self._save(d)
            return h["mc"]

    def refund(self, uid: str, action_id: str, reason: str, mc: int | None = None) -> int:
        """Give back up to `mc` (default: everything not yet refunded) of what the action was charged."""
        with self._lock:
            d = self._load(uid)
            act = d["actions"].get(action_id)
            if not act:
                return 0
            owed = act["spent"] - act["refunded"]
            amount = owed if mc is None else min(mc, owed)
            if amount <= 0:
                return 0
            src = act["from"]
            # refund into the buckets the charge came from, allowance first (the order it was spent)
            back = self._give(d, {**src, "allowance": min(src.get("allowance", 0), amount)}, amount)
            # whatever could not go back (an expired allowance) is simply gone: no rollover
            act["refunded"] += amount
            cut = amount
            a = min(src.get("allowance", 0), cut)
            src["allowance"] = src.get("allowance", 0) - a
            cut -= a
            for lid in list(src.get("lots", {})):
                t = min(cut, src["lots"][lid])
                src["lots"][lid] -= t
                cut -= t
            day, month = self.clock().strftime("%Y-%m-%d"), self.clock().strftime("%Y-%m")
            d["day"][day] = max(0, d["day"].get(day, 0) - amount)
            d["month"][month] = max(0, d["month"].get(month, 0) - amount)
            self._entry(d, "refund", back, action=action_id, reason=reason, owed_mc=amount)
            self._save(d)
            return back

    def held_mc(self, uid: str) -> int:
        with self._lock:
            return sum(h["mc"] for h in self._load(uid)["holds"].values())

    def absorb(self, uid: str, action_id: str, mc: int, note: str) -> None:
        """Alto's own cost (the off-topic gate): recorded, never debited."""
        with self._lock:
            d = self._load(uid)
            self._entry(d, "absorbed", mc, action=action_id, note=note)
            self._save(d)
