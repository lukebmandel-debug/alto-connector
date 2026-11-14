"""Bass money paths (security finding B1) on the Firestore EMULATOR, through the real google-cloud-firestore client (run by
.github/workflows/security.yml, never locally).

tests/test_bass_beta_b1.py and tests/test_bass_live_fixes.py prove the beta ledger on FakeStore and on StrictFirestore, a stand-in for
Firestore's read-before-write rule. This runs the same ledger (alto/bass/beta_ledger.py) on deploy/bass-proxy/firestore_store.py over a
real Firestore transaction engine:

  1. the B1 cases: two testers 250 apart, one tester across midnight, a busy morning to the daily limit, the heaviest legitimate ten
     minutes: none switches Bass off; spend past what the caps allow still trips the switch;
  2. hold / settle / refund keep the books exact: the day and period counters end with reserved == 0 and spent == what was charged;
  3. release (the hold back, nothing booked), absorb (Alto's own cost, never the tester's), the reaper (an abandoned hold booked in
     full, the tester's hold given back, nothing twice; a late settle replaces the worst case), and a hold across a new credit period
     (booked in its own period; the new one refuses until confirmed, then opens with a fresh allowance);
  4. contention: 8 threads hold and settle at once on the same day and period counters; whatever the emulator lets through, the books
     equal the sum of what succeeded (no lost update, no double booking) and nothing is left reserved.

Emulator only: refuses unless FIRESTORE_EMULATOR_HOST is local and the project id is a demo- one (the emulator never connects to a real
project). No credential exists here (anonymous credentials); never the luke-alto cloud env; the Bass mock only (no key, no model call).

    npx firebase emulators:exec --only firestore --project demo-alto-security "python bass_money_emulator_check.py"
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
from pathlib import Path

PROJECT = os.environ.get("GCLOUD_PROJECT") or "demo-alto-security"
HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent


def guard() -> None:
    if not PROJECT.startswith("demo-"):
        raise SystemExit(f"refusing to run: project {PROJECT!r} is not a demo- emulator project")
    if "luke-alto" in " ".join(os.environ.values()) or os.environ.get("ALTO_LIVE_ANTHROPIC"):
        raise SystemExit("refusing to run: a cloud or live env is set")
    host = os.environ.get("FIRESTORE_EMULATOR_HOST", "")
    if not host:
        raise SystemExit("refusing to run: FIRESTORE_EMULATOR_HOST is not set (run it under `firebase emulators:exec`)")
    if host.split("://")[-1].rsplit(":", 1)[0] not in ("127.0.0.1", "localhost", "::1", "[::1]"):
        raise SystemExit(f"refusing to run: FIRESTORE_EMULATOR_HOST={host!r} is not local")
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    os.environ["ALTO_UPDATE_CHECK"] = "off"


for p in (REPO, REPO / "tests", REPO / "deploy" / "bass-proxy"):
    sys.path.insert(0, str(p))

from bass_beta_support import FakeClock, make_stack  # noqa: E402
from alto.bass.beta_config import MC  # noqa: E402
from alto.bass.beta_ledger import day_key, pc_key  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="bass-money-emu-"))
# main() points these at the emulator. tests/test_bass_money_emulator_cases.py runs the same CASES on FakeStore (locally, no emulator)
# so the cases themselves are checked before CI runs them on Firestore.
new_store = None
wipe = lambda: None  # noqa: E731


def stack(**k):
    wipe()
    d = TMP / str(len(list(TMP.iterdir())))
    d.mkdir()
    return make_stack(d, store=new_store(), **k)


def spend(st, uid, credits, hid):
    st.ledger.grant_opening(uid)
    st.ledger.hold(uid, hid, credits * MC, "a_" + hid)
    st.ledger.settle(uid, hid, credits * MC)


def at(h, m):
    import datetime as dt
    from zoneinfo import ZoneInfo
    return FakeClock(dt.datetime(2026, 11, 3, h, m, tzinfo=ZoneInfo("America/New_York")).astimezone(dt.timezone.utc))


def books(st):
    g = st.store.get(day_key(st.ledger.today())) or {"spent_mc": 0, "reserved_mc": 0}
    p = st.store.get(pc_key(st.ledger.period())) or {"spent_mc": 0, "reserved_mc": 0}
    return g, p


CASES = []


def case(fn):
    CASES.append(fn)
    return fn


@case
def the_store_round_trips_and_runs_a_transaction():
    st = stack()
    st.store.put("bass_beta/probe", {"n": 1})
    assert st.store.get("bass_beta/probe") == {"n": 1}

    def work(txn):
        d = txn.get("bass_beta/probe")
        txn.put("bass_beta/probe", {"n": d["n"] + 1})
    st.store.run_transaction(work)
    assert st.store.get("bass_beta/probe") == {"n": 2}


@case
def two_testers_250_five_minutes_apart_do_not_trip():
    st = stack()
    spend(st, "u1", 250, "a")
    st.clock.advance(300)
    spend(st, "u2", 250, "b")
    assert not st.kill.is_on(), st.kill.state()
    g, p = books(st)
    assert (g["spent_mc"], g["reserved_mc"], p["reserved_mc"]) == (500 * MC, 0, 0), (g, p)


@case
def one_tester_across_midnight_does_not_trip():
    st = stack(clock=at(23, 55))
    spend(st, "u1", 250, "a")
    st.clock.advance(7 * 60)
    spend(st, "u1", 250, "b")
    assert not st.kill.is_on(), st.kill.state()


@case
def busy_morning_to_the_daily_limit_alerts_but_does_not_trip():
    st = stack(testers=15)
    for i in range(5):
        spend(st, f"u{i}", 250, f"h{i}")
        st.clock.advance(15 * 60)
    assert not st.kill.is_on(), st.kill.state()
    assert st.sink.of("daily_over_80_before_18")


@case
def heaviest_legitimate_ten_minutes_never_trips():
    st = stack(testers=15, clock=at(23, 52))
    for day in range(2):
        for i in range(15):
            st.ledger.grant_opening(f"u{i}")
            for k in range(2):
                try:
                    spend(st, f"u{i}", 150, f"d{day}u{i}k{k}")
                except Exception:  # noqa: BLE001 -- refused by a cap: the cap working
                    pass
        st.clock.advance(9 * 60)
    assert not st.kill.is_on(), st.kill.state()


@case
def spend_past_the_caps_still_trips_the_switch():
    st = stack(testers=2)
    spend(st, "u1", 10, "x")
    assert not st.kill.is_on()
    key = pc_key(st.ledger.period())
    p = st.store.get(key)
    p["spend_log"] = p["spend_log"] + [[st.clock.ts(), st.cfg.spike_trip_mc + MC]]     # books that let more through than the caps allow
    st.store.put(key, p)
    spend(st, "u2", 10, "y")                                    # the next commit sees it
    assert st.kill.is_on() and st.kill.state()["reason"] == "spend_spike_10min", st.kill.state()


@case
def hold_settle_and_refund_keep_the_books_exact():
    st = stack()
    st.ledger.grant_opening("u1")
    st.ledger.hold("u1", "h1", 100 * MC, "a1")
    g, p = books(st)
    assert g["reserved_mc"] == 100 * MC and p["reserved_mc"] == 100 * MC, (g, p)
    st.ledger.settle("u1", "h1", 40 * MC)                      # cost less than held
    st.ledger.hold("u1", "h2", 50 * MC, "a2")
    st.ledger.settle("u1", "h2", 0, charge=False, note="refund")
    g, p = books(st)
    assert (g["reserved_mc"], p["reserved_mc"]) == (0, 0), (g, p)
    assert g["spent_mc"] == p["spent_mc"] == 40 * MC, (g, p)


@case
def a_second_settle_of_the_same_hold_never_charges_the_tester_twice():
    st = stack()
    st.ledger.grant_opening("u1")
    st.ledger.hold("u1", "h", 30 * MC, "a")
    st.ledger.settle("u1", "h", 30 * MC)
    left = st.store.get("u1")["allowance_mc"]
    st.ledger.settle("u1", "h", 30 * MC)                       # (the server counters book it again as Alto's own cost: an over-count, by design)
    assert st.store.get("u1")["allowance_mc"] == left
    g, p = books(st)
    assert (g["reserved_mc"], p["reserved_mc"]) == (0, 0), (g, p)



def allowance(st, uid):
    return st.store.get(uid)["allowance_mc"]


@case
def a_release_gives_the_hold_back_and_books_nothing():
    st = stack()
    st.ledger.grant_opening("u1")
    before = allowance(st, "u1")
    st.ledger.hold("u1", "h", 60 * MC, "a")
    st.ledger.release("u1", "h")
    g, p = books(st)
    assert (g["reserved_mc"], p["reserved_mc"], g["spent_mc"], p["spent_mc"]) == (0, 0, 0, 0), (g, p)
    assert allowance(st, "u1") == before


@case
def absorb_books_alto_s_own_cost_and_never_charges_the_tester():
    st = stack()
    st.ledger.grant_opening("u1")
    before = allowance(st, "u1")
    st.ledger.absorb("u1", "gate_1", 15 * MC, "off-topic gate")
    g, p = books(st)
    assert g["spent_mc"] == p["spent_mc"] == 15 * MC and (g["reserved_mc"], p["reserved_mc"]) == (0, 0), (g, p)
    assert allowance(st, "u1") == before


@case
def the_reaper_books_an_abandoned_hold_and_a_late_settle_replaces_its_worst_case():
    st = stack()
    st.ledger.grant_opening("u1")
    before = allowance(st, "u1")
    st.ledger.hold("u1", "h", 50 * MC, "a")
    assert st.ledger.reap() == 0                                # too fresh: a slow call is not a crashed one
    st.clock.advance(st.cfg.reservation_ttl_s + 1)
    assert st.ledger.reap() == 1
    g, p = books(st)
    assert (g["reserved_mc"], p["reserved_mc"]) == (0, 0) and g["spent_mc"] == p["spent_mc"] == 50 * MC, (g, p)
    assert allowance(st, "u1") == before                        # the tester got their hold back; Alto keeps the cost
    assert st.ledger.reap() == 0                                # nothing is booked twice
    st.ledger.settle("u1", "h", 30 * MC)                        # the call did finish after all: the real cost replaces the worst case
    g, p = books(st)
    assert g["spent_mc"] == p["spent_mc"] == 30 * MC and allowance(st, "u1") == before, (g, p)


@case
def a_hold_settles_in_its_own_period_and_the_next_period_opens_fresh():
    from alto.bass.beta_ledger import confirm_key
    st = stack()
    st.ledger.grant_opening("u1")
    p0 = st.ledger.period()
    st.ledger.hold("u1", "old", 10 * MC, "a1", worst_mc=10 * MC)
    st.clock.advance(days=20)
    p1 = st.ledger.period()
    assert p1 != p0
    st.ledger.settle("u1", "old", 7 * MC)                       # booked in the period it was taken in, even with the next unconfirmed
    assert st.store.get(pc_key(p0))["spent_mc"] == 7 * MC and st.store.get(pc_key(p0))["reserved_mc"] == 0
    assert (st.store.get(pc_key(p1)) or {}).get("spent_mc", 0) == 0
    try:
        st.ledger.hold("u1", "new0", 10 * MC, "a2")
        raise AssertionError("a hold in an unconfirmed period went through")
    except AssertionError:
        raise
    except Exception:  # noqa: BLE001 -- refused: the new period is closed until IT confirms it
        pass
    st.store.put(confirm_key(p1), {"confirmed": True})          # IT confirms the new credit period
    st.ledger.grant_opening("u1")
    st.ledger.hold("u1", "new", 20 * MC, "a3")
    st.ledger.settle("u1", "new", 20 * MC)
    q1, q0 = st.store.get(pc_key(p1)), st.store.get(pc_key(p0))
    assert q1["spent_mc"] == 20 * MC and q1["reserved_mc"] == 0 and q0["spent_mc"] == 7 * MC, (q0, q1)
    assert allowance(st, "u1") == st.cfg.tester_period_credits * MC - 20 * MC   # a fresh allowance for the new period, less the new call

@case
def eight_threads_at_once_lose_no_update_and_book_nothing_twice():
    st = stack(testers=15)
    ok, lock = [], threading.Lock()

    def one(i):
        uid = f"t{i}"
        try:
            spend(st, uid, 20, f"c{i}")
            with lock:
                ok.append(20 * MC)
        except Exception:  # noqa: BLE001 -- a lost race may be refused (bass_paused); the books must still be exact
            pass
    ts = [threading.Thread(target=one, args=(i,)) for i in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(120)
    assert not any(t.is_alive() for t in ts), "a thread hung"
    g, p = books(st)
    assert ok, "no hold went through at all"
    assert (g["reserved_mc"], p["reserved_mc"]) == (0, 0), (g, p)
    assert g["spent_mc"] == p["spent_mc"] == sum(ok), (g, p, len(ok))


def main() -> int:
    global new_store, wipe
    guard()
    from google.auth.credentials import AnonymousCredentials
    from google.cloud import firestore
    from firestore_store import FirestoreStore
    db = firestore.Client(project=PROJECT, credentials=AnonymousCredentials())

    def _wipe():
        for coll in db.collections():
            db.recursive_delete(coll)
    new_store, wipe = (lambda: FirestoreStore(db)), _wipe
    failed = []
    for fn in CASES:
        try:
            fn()
            print("ok  ", fn.__name__)
        except Exception as e:  # noqa: BLE001
            failed.append(fn.__name__)
            chain, c = [], e
            while c is not None and len(chain) < 5:                # what the ledger's fail-closed answer hides (emulator data only)
                chain.append(f"{type(c).__module__}.{type(c).__name__}: {str(c)[:300]}")
                c = c.__cause__ or c.__context__
            print("FAIL", fn.__name__, getattr(e, "detail", ""), " <- ".join(chain))
    wipe()
    print(f"bass money on the Firestore emulator: {len(CASES) - len(failed)}/{len(CASES)} ok")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
