"""Bass beta spend report: READ ONLY. Spend by day, by tester and by action, for Strategy's daily spend line and the end-of-beta review.

Reads only metadata the ledger already keeps:
    bass_beta/day/<YYYY-MM-DD>       the day counter: what Alto actually paid that day (spent) and what is still held (reserved)
    <uid> (bass_credits/<uid>)       each tester's ledger entries: usage (charged), refund (given back to the allowance), absorbed (Alto's own
                                     cost, never charged: the off-topic gate, a turn the reaper settled)
    bass_beta/meta/<uid>_<day>       the per-call metadata log (MetaLog.LOG_FIELDS): action name, status, code, credits
Never read: document text, prompts, materials, titles, conversations, emails. Testers appear by uid only. Nothing is ever written: the
store is wrapped so a put or a transaction raises.

    python tools/bass_beta_report.py --project <gcp project> [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--json]
(--project uses Google's default credentials with a Firestore READ role; IT runs it, never a cloud seat.) Credits: 1 credit = 1 cent.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.bass.beta_config import MC, BetaConfig  # noqa: E402

DAY_PREFIX, META_PREFIX = "bass_beta/day/", "bass_beta/meta/"


class ReadOnly:
    """The only store the report gets: get and scan pass through, anything that writes raises."""

    def __init__(self, store):
        self._s = store

    def get(self, key):
        return self._s.get(key)

    def scan(self, prefix):
        return self._s.scan(prefix)

    def put(self, *a, **k):
        raise PermissionError("the spend report is read only")

    run_transaction = put


def _cr(mc) -> float:
    return round(int(mc or 0) / MC, 2)


def _in(day: str, since, until) -> bool:
    return (since is None or day >= since) and (until is None or day <= until)


def build(store, cfg: BetaConfig | None = None, since: str | None = None, until: str | None = None) -> dict:
    cfg = cfg or BetaConfig(testers=1)
    store = ReadOnly(store)
    days, testers, actions = {}, defaultdict(lambda: defaultdict(lambda: defaultdict(int))), defaultdict(lambda: defaultdict(int))
    for key, doc in store.scan(DAY_PREFIX):
        d = str((doc or {}).get("day") or key[len(DAY_PREFIX):])
        if _in(d, since, until):
            days[d] = {"day": d, "spent": _cr(doc.get("spent_mc")), "held_now": _cr(doc.get("reserved_mc"))}
    for uid, doc in store.scan(""):
        if not isinstance(doc, dict) or not isinstance(doc.get("entries"), list):
            continue
        for e in doc["entries"]:
            kind = e.get("kind")
            if kind not in ("usage", "refund", "absorbed"):
                continue
            try:
                d = dt.datetime.fromisoformat(e["t"]).astimezone(cfg.zone).date().isoformat()
            except (KeyError, TypeError, ValueError):
                continue
            if not _in(d, since, until):
                continue
            row = testers[uid][d]
            if kind == "usage":
                row["charged_mc"] += -int(e.get("mc") or 0)
            elif kind == "refund":
                row["refunded_mc"] += int(e.get("mc") or 0)
            else:
                row["absorbed_mc"] += int(e.get("mc") or 0)
    for key, doc in store.scan(META_PREFIX):
        d = str((doc or {}).get("day") or "")
        if not _in(d, since, until):
            continue
        for ln in (doc or {}).get("lines") or []:
            a = ln.get("action") if isinstance(ln.get("action"), str) else "unknown"
            row = actions[a]
            row["calls"] += 1
            row["done" if ln.get("status") == "ok" else "not_done"] += 1
            row["spent"] += float(ln.get("credits_spent") or 0)
            row["refunded"] += float(ln.get("credits_refunded") or 0)
    tester_rows = []
    for uid in sorted(testers):
        for d in sorted(testers[uid]):
            r = testers[uid][d]
            tester_rows.append({"uid": uid, "day": d, "charged": _cr(r["charged_mc"]), "refunded": _cr(r["refunded_mc"]),
                                "alto_absorbed": _cr(r["absorbed_mc"]), "cost": _cr(r["charged_mc"] + r["absorbed_mc"])})
    action_rows = [{"action": a, "calls": r["calls"], "done": r["done"], "not_done": r["not_done"], "spent": round(r["spent"], 2),
                    "refunded": round(r["refunded"], 2)} for a, r in sorted(actions.items())]
    day_rows = [days[d] for d in sorted(days)]
    return {"since": since, "until": until, "credits_note": "1 credit = 1 cent", "days": day_rows,
            "total_spent": round(sum(r["spent"] for r in day_rows), 2), "testers": tester_rows, "actions": action_rows}


def text(rep: dict) -> str:
    out = [f"Bass beta spend ({rep['credits_note']})" + (f", {rep['since'] or '...'} to {rep['until'] or '...'}" if rep["since"] or rep["until"] else ""),
           "", "By day: spent (held now)"]
    out += [f"  {r['day']}  {r['spent']:>9.2f}  ({r['held_now']:.2f})" for r in rep["days"]] or ["  none"]
    out += [f"  total       {rep['total_spent']:>9.2f}", "", "By tester and day: cost = charged + Alto absorbed; refunded went back to the allowance"]
    out += [f"  {r['uid'][:12]:<12} {r['day']}  cost {r['cost']:>8.2f}  charged {r['charged']:>8.2f}  refunded {r['refunded']:>7.2f}  absorbed {r['alto_absorbed']:>6.2f}"
            for r in rep["testers"]] or ["  none"]
    out += ["", "By action: calls (done / not done), credits spent, refunded"]
    out += [f"  {r['action']:<10} {r['calls']:>5} ({r['done']} / {r['not_done']})  {r['spent']:>9.2f}  {r['refunded']:>7.2f}" for r in rep["actions"]] or ["  none"]
    return "\n".join(out)


def _firestore(project: str):
    sys.path.insert(0, str(ROOT / "deploy" / "bass-proxy"))
    from google.cloud import firestore                                  # imported here: the tests never need Google's libraries
    from firestore_store import FirestoreStore
    return FirestoreStore(firestore.Client(project=project))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Bass beta spend report (read only).")
    ap.add_argument("--project", required=True)
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    from alto.cloud import offline
    if offline.reason() is not None:                                    # incident 11 Nov: no Google credential read in a test/mock process
        print(f"refused: {Path(__file__).name} reads Firestore with Google's default credentials, and this process is offline "
              f"({offline.reason()}). Run it from IT's own environment without ALTO_NO_NETWORK.", file=sys.stderr)
        return 2
    rep = build(_firestore(a.project), since=a.since, until=a.until)
    print(json.dumps(rep, indent=2) if a.json else text(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
