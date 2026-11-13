"""The Bass BETA guard set (G1-G10, G12-G15, B1-B3, U1-U4, P1-P6, G13b of ORG/notes-bass-beta.md), on the mock, with net_guard
installed and ALTO_NO_NETWORK=1. ZERO Anthropic requests: the mock is the only wire. G11 (Stripe) and the sales-history half of
G7 are post-beta. Numbers are the beta's config defaults: 9,000 per credit period, floor(9000/N) per tester, 300 per tester per
day, 1,500 per day for all, 300 per action; tests that need small numbers override the config, never the logic."""
import pytest as _pytest_sdk
_pytest_sdk.importorskip("anthropic")   # public CI has no SDK: these skip there (listed in test_bass_sdk_free.py) and run in the SDK env
_pytest_sdk.importorskip("httpx2")
import concurrent.futures as cf
import datetime as dt
import json
import re
import subprocess
import zoneinfo

import pytest

from bass_support import bass_guard, ROOT  # noqa: F401
from bass_beta_support import (EMAIL, FakeClock, build_req, edit_req, endless, long_text, make_stack, req, CHIPS, MATERIALS)
from alto.bass import config as P
from alto.bass import mock_anthropic as M
from alto.bass.beta_config import BetaConfig
from alto.bass.beta_guard import LOG_FIELDS
from alto.bass.beta_ledger import (DISABLED_KEY, TopUpNotAllowed, confirm_key, day_key, pc_key)
from alto.bass.beta_limits import client_ip
from alto.bass.beta_store import FakeStore, SimulatedCrash
from alto.bass.errors import BassError

MC = P.MC
UTC = dt.timezone.utc
BAL = {"action": "balance", "args": {}}


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")


@pytest.fixture
def st(tmp_path):
    return make_stack(tmp_path)


def day(st):
    return st.store.get(day_key(st.ledger.today())) or {"spent_mc": 0, "reserved_mc": 0, "alerted": []}


def pc(st):
    return st.store.get(pc_key(st.ledger.period())) or {"spent_mc": 0, "reserved_mc": 0, "res": {}, "alerted": [], "spend_log": []}


def no_requests(st):
    return st.mock.requests == []


def spend(st, uid, credits, hid="h"):
    """A call that cost `credits`, without a model: hold, then settle."""
    st.ledger.grant_opening(uid)
    st.ledger.hold(uid, hid, credits * MC, "a_" + hid)
    st.ledger.settle(uid, hid, credits * MC)


def byo_path_works(st):
    """The non-Bass (Claude / bring-your-own) path: the connector's own tools, which never touch Bass, its guards or its switches."""
    from alto import mcp_server as srv
    from alto.store.local import LocalStore
    srv.set_store(LocalStore(st.tmp / "byo"))
    try:
        return isinstance(srv.list_projects(), dict)
    finally:
        srv.set_store(None)


# ── config ────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_the_beta_numbers_are_config_defaults_and_overridable():
    assert BetaConfig(testers=10).server_ceiling_credits == 7000          # the INTERIM default (finding M4); the planned number is below
    c = BetaConfig(testers=10, server_ceiling_credits=9000)
    assert (c.server_ceiling_credits, c.tester_period_credits, c.tester_daily_credits, c.global_daily_credits) == (9000, 900, 300, 1500)
    assert (c.per_action_cap_credits, c.estimate_prompt_credits, c.spike_credits, c.start_day) == (300, 20, 400, 17)
    assert BetaConfig(testers=15, server_ceiling_credits=9000).tester_period_credits == 600 and 15 * 600 == c.server_ceiling_credits
    o = BetaConfig(testers=4, server_ceiling_credits=1000, tester_daily_credits=50, global_daily_credits=200, spike_credits=90)
    assert (o.tester_period_credits, o.tester_daily_mc, o.daily_ceiling_mc, o.spike_mc) == (250, 50 * MC, 200 * MC, 90 * MC)
    assert BetaConfig(testers=10, allowlist={"a@x.com", "b@x.com"}).problems() == []
    assert BetaConfig(testers=1, allowlist={"a@x.com", "b@x.com"}).problems()          # more listed than budgeted
    assert BetaConfig(testers=16).problems()                                            # past the 15 the ceiling was planned for
    with pytest.raises(ValueError):
        BetaConfig(testers=10, start_day=31)


def test_no_beta_number_is_hard_coded_outside_the_config_file():
    for f in sorted((ROOT / "alto" / "bass").glob("beta_*.py")):
        if f.name == "beta_config.py":
            continue
        assert not re.search(r"\b(?:9_?000|10_?000|1_?500)\b|\$\s?\d{2,}\b", f.read_text("utf-8")), f.name


# ── B1-B3: the allowance ─────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("n,want", [(10, 900), (15, 600), (7, 1285), (12, 750), (1, 9000)])
def test_b1_a_tester_gets_floor_of_the_ceiling_over_n_per_period_and_they_never_add_up_past_it(tmp_path, n, want):
    st = make_stack(tmp_path, testers=n)
    assert st.cfg.tester_period_credits == want == 9000 // n
    assert st.ledger.grant_opening("u1") == want * MC and st.ledger.balance_mc("u1") == want * MC
    assert n * want <= st.cfg.server_ceiling_credits


def test_b2_the_allowance_never_resets_inside_a_period_and_cannot_be_topped_up(st):
    uid = "u_tester1"
    st.ledger.grant_opening(uid)
    st.ledger.hold(uid, "h1", 200 * MC, "a1")
    st.ledger.settle(uid, "h1", 150 * MC)
    left = st.ledger.balance_mc(uid)
    assert left == 750 * MC
    for days in (1, 2, 3, 5):                                            # 2026-11-03 + 11 days is still before the 17th
        st.clock.advance(days=days)
        assert st.ledger.grant_opening(uid) == left and st.ledger.balance_mc(uid) == left
    with pytest.raises(TopUpNotAllowed):
        st.ledger.add_purchase(uid, 500, "lot1")


def test_b3_a_tester_at_zero_gets_a_plain_message_and_no_request(st):
    uid = "u_tester1"
    st.ledger.grant_opening(uid)
    for i in range(3):                                                    # 300 a day: three days to use 900
        st.ledger.hold(uid, f"h{i}", 300 * MC, f"a{i}")
        st.ledger.settle(uid, f"h{i}", 300 * MC)
        st.clock.advance(days=1)
    assert st.ledger.balance_mc(uid) == 0
    for r in (build_req(), edit_req()):
        out = st.svc.handle(req(r))
        assert out["status"] == "no_credits" and out["code"] == "beta_credits_used"
        assert "beta credits are used up" in out["message"] and "Traceback" not in out["message"]
    assert no_requests(st)


# ── U1-U4: the friendly limits, each with its own message and reason ───────────────────────────────────────────────

def test_u1_a_testers_own_credits_used_up_or_the_server_ceiling_gives_beta_credits_used_zero_requests_and_byo_works(tmp_path):
    for case in ("tester", "ceiling"):
        st = make_stack(tmp_path / case)
        if case == "tester":
            st.ledger.grant_opening("u_tester1")
            doc = st.store.get("u_tester1")
            doc["allowance_mc"] = 0
            st.store.put("u_tester1", doc)
        else:
            st.store.put(pc_key(st.ledger.period()), {"period": st.ledger.period(), "spent_mc": st.cfg.ceiling_mc, "reserved_mc": 0,
                                                       "res": {}, "alerted": [], "spend_log": []})
        for r in (build_req(), edit_req()):
            out = st.svc.handle(req(r))
            assert out["code"] == "beta_credits_used" and out["status"] == "no_credits", case
            assert "beta credits are used up" in out["message"]
        assert no_requests(st) and byo_path_works(st)


def test_u2_the_global_daily_limit_has_its_own_message_and_reason_and_zero_requests(st):
    g = {"day": st.ledger.today(), "spent_mc": st.cfg.daily_ceiling_mc, "reserved_mc": 0, "alerted": []}
    st.store.put(day_key(st.ledger.today()), g)                            # 1,500 credits already spent today by everyone
    out = st.svc.handle(req(edit_req()))
    assert out["code"] == "beta_daily_full" and "Today's beta limit has been reached" in out["message"] and "tomorrow" in out["message"]
    assert "used up" not in out["message"] and no_requests(st) and byo_path_works(st)
    st.clock.advance(days=1)                                               # the day boundary on the fake clock
    assert st.svc.handle(req(edit_req()))["ok"]


def test_u2_a_call_that_does_not_fit_in_what_is_left_of_the_day_is_refused_with_no_billable_request(tmp_path):
    st = make_stack(tmp_path, global_daily_credits=300)
    st.store.put(day_key(st.ledger.today()), {"day": st.ledger.today(), "spent_mc": 295 * MC, "reserved_mc": 0, "alerted": []})
    out = st.svc.handle(req(build_req()))
    assert out["code"] == "beta_daily_full" and st.mock.message_requests == []


def test_u3_the_disabled_flag_set_or_unreadable_turns_bass_off_with_zero_requests_and_leaves_the_rest(st):
    assert st.svc.handle(req(edit_req()))["ok"]                            # no doc: Bass is on
    n = len(st.mock.requests)
    for setup in (lambda: st.store.put(DISABLED_KEY, {"on": True}), lambda: st.store.put(DISABLED_KEY, {"cutoff": "budget"})):
        setup()
        out = st.svc.handle(req(edit_req()))
        assert out["code"] == "bass_disabled" and out["status"] == "paused" and "switched off" in out["message"]
        assert st.svc.handle(req(BAL))["available"] is False and byo_path_works(st)
        assert len(st.mock.requests) == n
    st.store.put(DISABLED_KEY, {"on": False})                              # IT clears it by hand
    assert st.svc.handle(req(edit_req()))["ok"]
    st.store.put(DISABLED_KEY, {"on": False})
    st.store.make_unreadable(DISABLED_KEY)                                 # cannot be read: fail closed
    n = len(st.mock.requests)
    for r in (build_req(), edit_req()):
        assert st.svc.handle(req(r))["code"] == "bass_disabled"
    with pytest.raises(BassError):
        st.ledger.hold("u_tester1", "hh", MC, "a")
    assert len(st.mock.requests) == n and byo_path_works(st)


def test_u3_the_disabled_flag_set_mid_action_stops_the_next_call(st):
    st.mock.use(endless(2000))
    st.engine.cfg.max_turns = 6
    st.ledger.grant_opening("u1")
    seen = {"n": 0}

    def flip(name, tool_input, out):
        seen["n"] += 1
        if seen["n"] == 2:
            st.store.put(DISABLED_KEY, {"on": True})
    res = st.engine.run_action("u1", "go", kind="build", on_tool=flip)
    assert res.status == "paused" and res.code == "bass_disabled" and res.turns == 2 and len(st.mock.message_requests) == 2


def test_u4_a_tester_at_300_today_gets_the_try_tomorrow_message_others_are_unaffected_and_it_resets(st):
    spend(st, "u_tester1", 300)                                            # the tester's whole day
    out = st.svc.handle(req(build_req()))
    assert out["code"] == "beta_tester_daily" and out["status"] == "capped" and "tomorrow" in out["message"]
    assert "Today's beta limit" not in out["message"] and no_requests(st)
    st.store.put("bass_beta/bass_testers", {"emails": [EMAIL, "tester2@example.com"]})
    assert st.svc.handle(req(edit_req(), email="tester2@example.com"))["ok"]            # another tester is fine
    st.clock.advance(days=1)
    assert st.svc.handle(req(edit_req()))["ok"]                                          # and a new day resets it
    assert byo_path_works(st)


def test_u4_a_holds_in_flight_count_toward_the_testers_day(st):
    st.ledger.grant_opening("u1")
    st.ledger.hold("u1", "a", 200 * MC, "x")
    with pytest.raises(BassError) as e:
        st.ledger.hold("u1", "b", 101 * MC, "y")                                          # 200 held + 101 > 300
    assert e.value.code == "beta_tester_daily"
    st.ledger.hold("u1", "c", 100 * MC, "z")


@pytest.mark.parametrize("setup,why,code", [
    ({"tester_day": 1, "tester_period": 0, "global_day": 0, "period": 0}, "tester_daily", "beta_tester_daily"),
    ({"tester_day": 0, "tester_period": 1, "global_day": 0, "period": 0}, "tester_period", "beta_credits_used"),
    ({"tester_day": 0, "tester_period": 0, "global_day": 1, "period": 0}, "global_daily", "beta_daily_full"),
    ({"tester_day": 0, "tester_period": 0, "global_day": 0, "period": 1}, "period_ceiling", "beta_credits_used"),
    ({"tester_day": 1, "tester_period": 1, "global_day": 1, "period": 1}, "tester_daily", "beta_tester_daily"),    # first wins
    ({"tester_day": 0, "tester_period": 1, "global_day": 1, "period": 1}, "tester_period", "beta_credits_used"),
    ({"tester_day": 0, "tester_period": 0, "global_day": 1, "period": 1}, "global_daily", "beta_daily_full"),
])
def test_the_hold_checks_in_order_tester_day_tester_period_global_day_global_period(st, setup, why, code):
    c, pid, today = st.cfg, st.ledger.period(), st.ledger.today()
    st.ledger.grant_opening("u1")
    u = st.store.get("u1")
    if setup["tester_day"]:
        u["day"][today] = c.tester_daily_mc
    if setup["tester_period"]:
        u["allowance_mc"] = 5 * MC
    st.store.put("u1", u)
    st.store.put(day_key(today), {"day": today, "spent_mc": c.daily_ceiling_mc if setup["global_day"] else 0, "reserved_mc": 0, "alerted": []})
    st.store.put(pc_key(pid), {"period": pid, "spent_mc": c.ceiling_mc if setup["period"] else 0, "reserved_mc": 0, "res": {},
                               "alerted": [], "spend_log": []})
    with pytest.raises(BassError) as e:
        st.ledger.hold("u1", "h", 10 * MC, "a")
    assert e.value.detail["why"] == why and e.value.code == code
    assert st.ledger.held_mc("u1") == 0


# ── P1-P6: credit periods ────────────────────────────────────────────────────────────────────────────────────────

NY = zoneinfo.ZoneInfo("America/New_York")


def ny(y, mo, d, h=0, mi=0, s=0):
    return dt.datetime(y, mo, d, h, mi, s, tzinfo=NY).astimezone(UTC)


def test_p1_crossing_the_boundary_with_confirmation_resets_totals_not_adds(tmp_path):
    st = make_stack(tmp_path, clock=FakeClock(ny(2026, 11, 16, 23, 50)))
    spend(st, "u_tester1", 250)
    assert st.ledger.balance_mc("u_tester1") == 650 * MC and pc(st)["spent_mc"] == 250 * MC
    old = st.ledger.period()
    assert old == "2026-10-17"
    st.store.put(confirm_key("2026-11-17"), {"confirmed": True})            # IT, after Luke confirms the refresh
    st.clock.advance(20 * 60)                                                # 00:10 on the 17th
    assert st.ledger.period() == "2026-11-17"
    out = st.svc.handle(req(edit_req()))
    assert out["ok"] and st.ledger.balance_mc("u_tester1") <= 900 * MC
    assert st.ledger.balance_mc("u_tester1") > 890 * MC                      # refilled to 900, the 650 left was NOT carried on top
    assert pc(st)["spent_mc"] < 5 * MC and st.store.get(pc_key(old))["spent_mc"] == 250 * MC
    assert day(st)["spent_mc"] < 5 * MC                                      # a new day too


def test_p2_crossing_without_confirmation_turns_bass_off_with_the_friendly_message(tmp_path):
    st = make_stack(tmp_path, clock=FakeClock(ny(2026, 11, 16, 23, 50)))
    st.clock.advance(20 * 60)
    for r in (build_req(), edit_req()):
        out = st.svc.handle(req(r))
        assert out["code"] == "beta_credits_used" and out["status"] == "no_credits" and "beta credits are used up" in out["message"]
    assert st.svc.handle(req(BAL))["available"] is False and no_requests(st) and byo_path_works(st)
    with pytest.raises(BassError) as e:
        st.ledger.hold("u1", "h", MC, "a")
    assert e.value.detail["why"] == "period_unconfirmed"
    st.store.put(confirm_key("2026-11-17"), {"confirmed": False})           # a present-but-false marker is still unconfirmed
    assert st.svc.handle(req(edit_req()))["code"] == "beta_credits_used"
    st.store.put(confirm_key("2026-11-17"), {"confirmed": True})
    assert st.svc.handle(req(edit_req()))["ok"]
    assert st.cfg.period_id(st.clock()) == "2026-11-17"


def test_p3_before_the_boundary_nothing_resets(tmp_path):
    st = make_stack(tmp_path, clock=FakeClock(ny(2026, 11, 16, 23, 40)))
    spend(st, "u_tester1", 250)
    st.store.put(confirm_key("2026-11-17"), {"confirmed": True})            # confirmed early: still not open before midnight
    st.clock.advance(15 * 60)                                                # 23:55
    assert st.ledger.period() == "2026-10-17"
    assert st.ledger.grant_opening("u_tester1") == 650 * MC and pc(st)["spent_mc"] == 250 * MC


def test_p4_an_in_flight_hold_across_the_boundary_settles_in_the_period_it_was_taken_in(tmp_path):
    st = make_stack(tmp_path, clock=FakeClock(ny(2026, 11, 16, 23, 59, 30)))
    st.store.put(confirm_key("2026-11-17"), {"confirmed": True})
    st.ledger.grant_opening("u1")
    st.ledger.hold("u1", "slow", 100 * MC, "a1")
    st.clock.advance(60)                                                     # the call finishes after midnight
    assert st.ledger.period() == "2026-11-17"
    st.ledger.settle("u1", "slow", 40 * MC)
    old, new = st.store.get(pc_key("2026-10-17")), st.store.get(pc_key("2026-11-17"))
    assert old["spent_mc"] == 40 * MC and old["reserved_mc"] == 0 and old["res"] == {}
    assert new is None or (new["spent_mc"] == 0 and new["reserved_mc"] == 0)
    d_old, d_new = st.store.get(day_key("2026-11-16")), st.store.get(day_key("2026-11-17"))
    assert d_old["spent_mc"] == 40 * MC and d_old["reserved_mc"] == 0 and (d_new is None or d_new["spent_mc"] == 0)


def test_p5_ten_testers_get_900_and_fifteen_get_600_and_together_they_can_use_exactly_the_ceiling(tmp_path):
    for n, per in ((10, 900), (15, 600)):
        st = make_stack(tmp_path / str(n), testers=n, trip_before_hour=0, spike_credits=10 ** 6, global_daily_credits=10 ** 5)
        for d in range(per // 300):                                          # 300 a day per tester
            for i in range(n):
                spend(st, f"u{i}", 300, hid=f"h{d}_{i}")
            st.clock.advance(days=1)
        assert pc(st)["spent_mc"] == st.cfg.ceiling_mc == 9000 * MC
        with pytest.raises(BassError) as e:
            st.ledger.hold("u0", "more", MC, "a")                            # the testers' own 900/600 are gone first
        assert e.value.detail["why"] == "tester_period"
        with pytest.raises(BassError) as e2:
            st.ledger.grant_opening("late-comer") and st.ledger.hold("late-comer", "h", MC, "a")
        assert e2.value.detail["why"] == "period_ceiling" and e2.value.code == "beta_credits_used"


@pytest.mark.parametrize("when,want", [
    (dt.datetime(2026, 12, 31, 17, 0, tzinfo=UTC), "2026-12-17"),             # year end
    (dt.datetime(2027, 1, 1, 5, 0, tzinfo=UTC), "2026-12-17"),                # 00:00 New Year in New York
    (dt.datetime(2027, 1, 16, 4, 59, 59, tzinfo=UTC), "2026-12-17"),          # 23:59:59 on the 15th
    (dt.datetime(2027, 1, 17, 5, 0, tzinfo=UTC), "2027-01-17"),               # 00:00 on the 17th, EST
    (dt.datetime(2027, 2, 16, 17, 0, tzinfo=UTC), "2027-01-17"),              # short February: 28 days
    (dt.datetime(2027, 2, 17, 17, 0, tzinfo=UTC), "2027-02-17"),
    (dt.datetime(2027, 3, 14, 17, 0, tzinfo=UTC), "2027-02-17"),              # DST starts that day
    (dt.datetime(2027, 3, 17, 3, 59, 59, tzinfo=UTC), "2027-02-17"),          # 23:59:59 EDT on the 16th
    (dt.datetime(2027, 3, 17, 4, 0, tzinfo=UTC), "2027-03-17"),               # 00:00 EDT on the 17th
    (dt.datetime(2026, 11, 1, 5, 30, tzinfo=UTC), "2026-10-17"),              # DST ends that day (a 25-hour day)
    (dt.datetime(2026, 11, 17, 4, 59, tzinfo=UTC), "2026-10-17"),             # 23:59 EST on the 16th (31-day period)
    (dt.datetime(2026, 12, 17, 4, 59, tzinfo=UTC), "2026-11-17"),             # 30-day period ends
])
def test_p6_period_math_at_month_and_year_ends_and_dst(when, want):
    assert BetaConfig(testers=10).period_id(when) == want


def test_p6_periods_are_31_30_and_28_days_and_a_dst_day_is_one_day_id():
    c = BetaConfig(testers=10)
    starts = ["2026-10-17", "2026-11-17", "2026-12-17", "2027-01-17", "2027-02-17", "2027-03-17"]
    lens = [(dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days for a, b in zip(starts, starts[1:])]
    assert lens == [31, 30, 31, 31, 28]
    for a, b in zip(starts, starts[1:]):                                       # the id flips exactly at local midnight on the 17th
        t = ny(int(b[:4]), int(b[5:7]), 17)
        assert c.period_id(t - dt.timedelta(seconds=1)) == a and c.period_id(t) == b
    ids = {c.day_id(ny(2026, 11, 1) + dt.timedelta(hours=h)) for h in range(25)}       # the 25-hour day
    assert ids == {"2026-11-01"}
    ids = {c.day_id(ny(2027, 3, 14) + dt.timedelta(hours=h)) for h in range(23)}       # the 23-hour day
    assert ids == {"2027-03-14"}


# ── G1, G10: the allowlist ───────────────────────────────────────────────────────────────────────────────────────

def test_g1_not_on_the_list_or_unverified_means_bass_is_off_and_zero_requests(st):
    cases = [req(build_req(), email="stranger@example.com"), req(build_req(), verified=False),
             req(build_req(), verified=None), req(build_req(), uid=""), req(edit_req(), email="TESTER1@EXAMPLE.COM.evil.io")]
    for c in cases:
        out = st.svc.handle(c)
        assert out["code"] == "bass_off" and out["status"] == "paused" and out["available"] is False, c
    assert no_requests(st)
    assert st.store.get("u_stranger") is None and st.store.get("u_tester1") is None      # no account was even created
    assert st.svc.handle(req(edit_req()))["ok"]
    assert st.svc.handle(req(BAL, email="Tester1@Example.com"))["ok"]                    # case-insensitive


def test_g1_the_list_is_edited_by_hand_in_the_store_without_a_deploy(st):
    assert st.svc.handle(req(BAL, email="new@example.com"))["code"] == "bass_off"
    st.store.put("bass_beta/bass_testers", {"emails": ["new@example.com"]})
    assert st.svc.handle(req(BAL, email="new@example.com"))["ok"]
    assert st.svc.handle(req(BAL))["code"] == "bass_off"                                   # the store doc replaces the config copy
    st.store.go_down()
    assert st.svc.handle(req(BAL, email="new@example.com"))["code"] == "bass_off"          # fails closed


def test_g10_a_hundred_fake_accounts_from_one_ip_get_nothing_and_make_no_request(st):
    outs = [st.svc.handle(req(build_req(), email=f"bot{i}@example.com", xff="198.51.100.9")) for i in range(100)]
    assert {o["code"] for o in outs} <= {"bass_off", "busy"}
    assert no_requests(st) and all(st.store.get(f"u_bot{i}") is None for i in range(100))
    assert "allowlist_miss_burst" in st.sink.kinds()


# ── G2, G5: refused before any call ──────────────────────────────────────────────────────────────────────────────

def test_g2_an_estimate_above_the_remaining_allowance_is_refused_and_the_ledger_never_goes_negative(tmp_path):
    st = make_stack(tmp_path, server_ceiling_credits=70)                   # allowance 7 credits: less than one build turn
    st.mock.use(M.build("Contracts", {"title": "Contracts"}, [], []))
    out = st.svc.handle(req(build_req()))
    assert out["status"] == "no_credits" and out["code"] == "beta_credits_used"
    assert st.mock.message_requests == []                                 # no billable request was made (count_tokens is free)
    assert 0 <= st.ledger.balance_mc("u_tester1") <= st.cfg.allowance_mc and st.ledger.held_mc("u_tester1") == 0
    assert day(st)["spent_mc"] == 0 and day(st)["reserved_mc"] == 0 and pc(st)["reserved_mc"] == 0


def test_g5_oversize_input_is_refused_before_any_call(st):
    big = [{"name": "huge.pdf", "kind": "notes", "text": "x" * 600_001}]
    for r in (build_req(materials=big), {"action": "estimate", "args": {"kind": "build", "materials": big}}):
        out = st.svc.handle(req(r))
        assert out["code"] == "too_large" and out["ok"] is False
    assert no_requests(st) and st.ledger.balance_mc("u_tester1") == st.cfg.allowance_mc


def test_the_estimate_prompt_shows_above_20_credits_and_the_tester_must_accept(st):
    out = st.svc.handle(req(build_req(accepted=False)))
    assert out["status"] == "estimate" and out["show_prompt"] is True and out["estimate_credits"] > st.cfg.estimate_prompt_credits
    assert st.mock.message_requests == [] and st.ledger.balance_mc("u_tester1") == st.cfg.allowance_mc


# ── G3: parallel calls, in-flight limits, the daily reservation ──────────────────────────────────────────────────

def test_g3_twenty_parallel_holds_against_an_allowance_for_three_settle_at_most_three(tmp_path):
    st = make_stack(tmp_path, server_ceiling_credits=700)                 # allowance 70 credits
    st.ledger.grant_opening("u1")
    st.store.inject_conflicts(3)                                          # the transaction retries through losing races
    won, lost = [], []

    def one(i):
        try:
            st.ledger.hold("u1", f"h{i}", 20 * MC, f"a{i}")
            won.append(i)
        except BassError as e:
            lost.append(e.code)

    with cf.ThreadPoolExecutor(20) as ex:
        list(ex.map(one, range(20)))
    assert len(won) == 3 and lost == ["beta_credits_used"] * 17           # 70 // 20 = 3, never a fourth
    for i in won:
        st.ledger.settle("u1", f"h{i}", 20 * MC)
    assert st.ledger.balance_mc("u1") == 10 * MC and st.ledger.held_mc("u1") == 0
    assert day(st)["spent_mc"] == 60 * MC and day(st)["reserved_mc"] == 0 and pc(st)["res"] == {}


def test_g3_in_flight_limits_one_build_and_two_chat_per_account(st):
    for kind, limit in (("build", 1), ("chat", 2)):
        with cf.ThreadPoolExecutor(20) as ex:
            got = list(ex.map(lambda _: st.svc.inflight.acquire("u1", kind), range(20)))
        assert sum(got) == limit
        for _ in range(limit):
            st.svc.inflight.release("u1", kind)
    assert st.svc.inflight.acquire("u2", "build")                         # another account is unaffected


def test_g3_and_g7_the_daily_reservation_is_never_exceeded_under_20_parallel_accounts(tmp_path):
    st = make_stack(tmp_path, global_daily_credits=150, trip_before_hour=0)
    for i in range(20):
        st.ledger.grant_opening(f"u{i}")
    st.store.inject_conflicts(3)

    def one(i):
        try:
            st.ledger.hold(f"u{i}", f"h{i}", 20 * MC, f"a{i}")
            return "ok"
        except BassError as e:
            return e.code

    with cf.ThreadPoolExecutor(20) as ex:
        codes = list(ex.map(one, range(20)))
    assert codes.count("ok") == 7 and codes.count("beta_daily_full") == 13       # 7 x 20 = 140 <= 150 < 160
    assert day(st)["reserved_mc"] == 140 * MC <= st.cfg.daily_ceiling_mc and len(pc(st)["res"]) == 7


# ── G4: the runaway loop ─────────────────────────────────────────────────────────────────────────────────────────

def test_g4_an_endless_tool_loop_stops_at_the_3_dollar_cap_and_keeps_the_partial_work(tmp_path):
    st = make_stack(tmp_path, tester_daily_credits=600)                   # so the per-action cap is what stops it
    st.mock.use(endless(15000))
    out = st.svc.handle(req(build_req()))
    assert out["status"] == "capped" and out["code"] == "action_cap" and out["work_saved"] is True
    spent = out["credits"]["spent"]
    assert 200 < spent <= 300                                             # finding M7: a turn whose worst case does not fit is not started, so it never passes the cap
    assert abs(st.ledger.balance_mc("u_tester1") - (st.cfg.allowance_mc - int(round(spent * MC)))) <= 20       # spent is shown rounded


# ── G6: bursts ───────────────────────────────────────────────────────────────────────────────────────────────────

def test_g6_a_per_account_burst_stops_at_the_limit_and_recovers_with_the_clock(st):
    codes = [st.svc.handle(req(BAL, xff=f"203.0.113.{i}")).get("code") for i in range(15)]   # a new IP each time: only the account counts
    assert codes.count("busy") == 3 and codes[:12] == [None] * 12
    st.clock.advance(61)
    assert st.svc.handle(req(BAL))["ok"] and no_requests(st)


def test_g6_a_per_ip_burst_stops_at_the_limit_whatever_the_accounts(tmp_path):
    st = make_stack(tmp_path, emails=[f"t{i}@example.com" for i in range(10)])
    outs = [st.svc.handle(req(BAL, email=f"t{i % 10}@example.com", xff="198.51.100.4")) for i in range(40)]
    assert sum(1 for o in outs if o["ok"]) == 30 and sum(1 for o in outs if o.get("code") == "busy") == 10
    st.clock.advance(61)
    assert st.svc.handle(req(BAL, email="t0@example.com", xff="198.51.100.4"))["ok"]


def test_g6_the_ip_is_the_last_xff_entry_and_ipv6_is_bucketed_by_64():
    assert client_ip("6.6.6.6, 203.0.113.9") == client_ip("7.7.7.7, 203.0.113.9") == "203.0.113.9"     # the spoofable left end is ignored
    assert client_ip("x, 2001:db8:1:2:aaaa:bbbb:cccc:dddd") == client_ip("2001:db8:1:2::1") == "2001:db8:1:2::/64"
    assert client_ip("2001:db8:1:3::1") != "2001:db8:1:2::/64"
    assert client_ip(None, "10.0.0.1") == "10.0.0.1" and client_ip("garbage") == "invalid"


def test_g6_a_spoofed_left_entry_does_not_dodge_the_ip_limit(tmp_path):
    st = make_stack(tmp_path, emails=[f"t{i}@example.com" for i in range(10)])
    outs = [st.svc.handle(req(BAL, email=f"t{i % 10}@example.com", xff=f"{i}.{i}.{i}.{i}, 198.51.100.4")) for i in range(40)]
    assert sum(1 for o in outs if o.get("code") == "busy") == 10


# ── G7 (the fixed daily limit), the reaper, fail closed ─────────────────────────────────────────────────────────

def flood(st, accounts, rounds):
    for i in range(accounts):
        st.ledger.grant_opening(f"u{i}")
    seen = set()
    for _ in range(rounds):
        for i in range(accounts):
            st.mock.use(endless(15000))
            out = st.acts.dispatch(f"u{i}", build_req())
            seen.add(out["code"])
            g = day(st)
            assert g["spent_mc"] + g["reserved_mc"] <= st.cfg.daily_ceiling_mc
    return seen


def test_g7_a_flood_stops_at_the_daily_limit_and_total_metered_cost_stays_under_it(tmp_path):
    st = make_stack(tmp_path, global_daily_credits=300, tester_daily_credits=1000, trip_before_hour=0, spike_credits=10 ** 6)
    seen = flood(st, accounts=4, rounds=3)
    g = day(st)
    assert "beta_daily_full" in seen or g["spent_mc"] > 0.9 * st.cfg.daily_ceiling_mc
    assert g["spent_mc"] + g["reserved_mc"] <= st.cfg.daily_ceiling_mc and g["reserved_mc"] == 0
    assert all(st.ledger.balance_mc(f"u{i}") >= 0 for i in range(4))
    before = len(st.mock.message_requests)
    out = st.acts.dispatch("u0", build_req())                   # the day is full: refused with no further model call
    assert out["status"] == "paused" and out["code"] == "beta_daily_full" and "tomorrow" in out["message"]
    assert len(st.mock.message_requests) == before


def test_g7_the_daily_limit_scales_with_its_config_and_the_next_day_starts_fresh(tmp_path):
    spent = {}
    for lim in (300, 600):
        st = make_stack(tmp_path / str(lim), global_daily_credits=lim, tester_daily_credits=1000, trip_before_hour=0, spike_credits=10 ** 6)
        flood(st, accounts=4, rounds=4)
        spent[lim] = day(st)["spent_mc"]
        assert spent[lim] <= st.cfg.daily_ceiling_mc == lim * MC
    assert spent[600] > spent[300]
    st.clock.advance(days=1)
    st.mock.use(endless(15000))
    assert st.acts.dispatch("u0", build_req())["code"] != "beta_daily_full"


def test_g7_a_crashed_function_leaves_a_hold_and_the_reaper_frees_it(st):
    st.ledger.grant_opening("u1")
    st.store.crash_after_commits(0)
    with pytest.raises(SimulatedCrash):
        st.ledger.hold("u1", "dead", 50 * MC, "a1")           # committed, then the function died before it could settle
    assert day(st)["reserved_mc"] == 50 * MC and pc(st)["reserved_mc"] == 50 * MC and st.ledger.held_mc("u1") == 50 * MC
    assert st.ledger.reap() == 0                              # too fresh: a slow call is not a crashed one
    st.clock.advance(st.cfg.reservation_ttl_s + 1)
    assert st.ledger.reap() == 1
    assert day(st)["reserved_mc"] == 0 and pc(st)["reserved_mc"] == 0 and pc(st)["res"] == {} and st.ledger.held_mc("u1") == 0
    assert st.ledger.balance_mc("u1") == st.cfg.allowance_mc
    st.ledger.hold("u1", "ok", 50 * MC, "a2")                 # the freed credits are spendable again


def test_g7_a_settle_that_finds_its_hold_reaped_still_counts_the_spend(st):
    st.ledger.grant_opening("u1")
    st.ledger.hold("u1", "slow", 50 * MC, "a1")
    st.clock.advance(st.cfg.reservation_ttl_s + 1)
    st.ledger.reap()
    st.ledger.settle("u1", "slow", 30 * MC)                   # the upstream call finished late: Alto still paid for it
    assert day(st)["spent_mc"] == 30 * MC and pc(st)["spent_mc"] == 30 * MC and st.ledger.balance_mc("u1") == st.cfg.allowance_mc


def test_g7_a_store_outage_or_endless_conflicts_fail_closed_with_no_call(st):
    st.ledger.grant_opening("u1")
    st.store.go_down()
    st.mock.use(endless(2000))
    assert st.svc.handle(req(build_req()))["status"] == "paused"          # the store cannot say who is allowed: Bass is off
    with pytest.raises(BassError) as e0:
        st.acts.dispatch("u1", build_req())                               # even called past the gate, it stops
    assert e0.value.code == "bass_paused" and st.mock.message_requests == []
    st.store.go_down(False)
    st.store.inject_conflicts(999)
    with pytest.raises(BassError) as e:
        st.ledger.hold("u1", "h", 10 * MC, "a")
    assert e.value.code == "bass_paused" and st.ledger.held_mc("u1") == 0
    st.store.inject_conflicts(0)
    st.ledger.hold("u1", "h", 10 * MC, "a")                   # and it recovers


# ── G8, G13, G13b: the kill switch ───────────────────────────────────────────────────────────────────────────────

def test_g8_the_kill_switch_stops_new_calls_with_zero_requests_and_resets_by_hand_only(st):
    assert st.svc.handle(req(edit_req()))["ok"]
    n = len(st.mock.requests)
    st.kill.trip("by_test")
    for r in (build_req(), edit_req()):
        out = st.svc.handle(req(r))
        assert out["status"] == "paused" and out["code"] == "bass_paused"
    assert len(st.mock.requests) == n
    assert st.svc.handle(req(BAL))["available"] is False and byo_path_works(st)           # viewing and balance stay up
    st.clock.advance(days=3)
    assert st.kill.is_on()                                    # time does not reset it
    st.kill.reset("luke")
    assert st.svc.handle(req(edit_req()))["ok"]
    assert [e["kind"] for e in st.sink.events if e["kind"].startswith("kill")] == ["kill_switch", "kill_switch_reset"]


def test_g8_a_trip_mid_action_stops_the_next_call(st):
    st.mock.use(endless(2000))
    st.engine.cfg.max_turns = 6
    calls = {"n": 0}

    def trip_after_two(name, tool_input, out):
        calls["n"] += 1
        if calls["n"] == 2:
            st.kill.trip("mid_action")
    st.ledger.grant_opening("u1")
    res = st.engine.run_action("u1", "go", kind="build", on_tool=trip_after_two)
    assert res.status == "paused" and res.turns == 2 and len(st.mock.message_requests) == 2


def test_g8_the_daily_counter_over_80_percent_before_18_alerts_once_but_not_after(tmp_path):
    """B1: an alert, not the kill switch (the day's own limit refuses past 100% and resets at midnight). tests/test_bass_beta_b1.py"""
    for hour_shift, should_alert in ((0, True), (9, False)):               # 10:00 and 19:00 New York
        st = make_stack(tmp_path / str(hour_shift), global_daily_credits=150)
        st.clock.advance(hour_shift * 3600)
        for i in range(7):
            st.ledger.grant_opening(f"u{i}")
            st.ledger.hold(f"u{i}", f"h{i}", 20 * MC, "a")             # 140 of 150 = 93%
        assert not st.kill.is_on()
        assert len(st.sink.of("daily_over_80_before_18")) == (1 if should_alert else 0)


def test_g8_a_ten_minute_spend_past_what_the_caps_allow_trips_but_slow_spend_does_not(tmp_path):
    """B1: the trip sits above anything the caps allow in 10 minutes (cfg.spike_trip_mc), so only books that let too much through reach it:
    fed to the watchdog directly, as such a period doc would look."""
    for gap, trips in ((60, True), (601, False)):
        st = make_stack(tmp_path / str(gap))
        half = st.cfg.spike_trip_mc // 2 + MC
        t = st.clock.ts()
        st.ledger.on_commit({"spent_mc": 0, "reserved_mc": 0}, {"spend_log": [[t - gap, half], [t, half]]})
        assert st.kill.is_on() is trips
        if trips:
            assert st.kill.state()["reason"] == "spend_spike_10min" and st.sink.of("kill_switch")


@pytest.mark.parametrize("fault,reason,friendly", [
    (M.auth_error, "upstream_auth", False), (M.credit_balance_low, "upstream_balance_low", False),
    (M.workspace_limit, "upstream_workspace_limit", True), (M.unexpected_400, "upstream_bad_request", False),
    (M.forbidden, "upstream_auth", False)])
def test_g13_every_401_403_credit_low_workspace_limit_or_unexpected_400_trips_the_switch_and_is_not_retried(st, fault, reason, friendly):
    st.mock.use(endless(2000)).inject(fault(times=5))
    out = st.svc.handle(req(build_req()))
    assert out["status"] in ("paused", "error")
    assert ("beta credits are used up" in out["message"]) if friendly else ("Nothing was charged" in out["message"])
    assert len(st.mock.errors_sent) == 1                                   # exactly one upstream attempt: no retry
    assert st.kill.state() == {"on": True, "reason": reason}
    assert st.sink.of("kill_switch")[0]["reason"] == reason
    n = len(st.mock.requests)
    assert st.svc.handle(req(build_req()))["code"] == "bass_paused" and len(st.mock.requests) == n
    assert st.ledger.balance_mc("u_tester1") == st.cfg.allowance_mc        # and nobody was charged
    assert byo_path_works(st)


# ── G9: refunds ──────────────────────────────────────────────────────────────────────────────────────────────────

def test_g9_the_refund_loop_is_capped_at_five_per_account_per_day(st):
    st.ledger.grant_opening("u1")
    got = []
    for i in range(8):
        st.ledger.hold("u1", f"h{i}", 10 * MC, f"a{i}")
        st.ledger.settle("u1", f"h{i}", 10 * MC)
        got.append(st.ledger.refund("u1", f"a{i}", "failed:upstream"))
    assert [g > 0 for g in got] == [True] * 5 + [False] * 3
    assert st.ledger.balance_mc("u1") == st.cfg.allowance_mc - 3 * 10 * MC           # the last three stay charged
    assert st.sink.of("refund_capped")
    st.clock.advance(days=1)
    st.ledger.hold("u1", "hx", 10 * MC, "ax")
    st.ledger.settle("u1", "hx", 10 * MC)
    assert st.ledger.refund("u1", "ax", "failed:upstream") > 0                        # a new day, a new five


def test_g9_a_failed_or_refused_turn_is_refunded_by_the_engine_inside_the_cap(st):
    st.mock.use(M.Scenario("refuse", [M.Step(M.refusal())], repeat_last=True))
    out = st.svc.handle(req(build_req()))
    assert out["status"] == "refused" and out["credits"]["spent"] == 0
    assert st.ledger.balance_mc("u_tester1") == st.cfg.allowance_mc


# ── G12: no key or upstream header outside the one place that builds the client ─────────────────────────────────

KEY_RE = re.compile("sk-" + "ant-[A-Za-z0-9_-]{8,}")
ALLOWED = {"alto/bass/mock_anthropic.py", "alto/bass/client.py", "alto/bass/keys.py", "alto/bass/studio_key.py",
           "alto/bass/net_guard.py", "tools/bass_firstcall_rehearse.py"}   # the rehearsal prints the header NAMES with the key shown as <keychain>


def test_g12_no_key_and_no_upstream_header_in_the_source_or_the_client_bundle():
    files = subprocess.check_output(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, text=True).split("\n")
    bad = []
    for f in files:
        if not f or f.startswith(("tests/", "docs/", "samples/")) or f in ALLOWED or not f.endswith((".py", ".js", ".html", ".css", ".json")):
            continue
        t = (ROOT / f).read_text("utf-8", "ignore")
        if KEY_RE.search(t) or re.search(r"x-api-key|anthropic-version|anthropic-beta", t, re.I):
            bad.append(f)
    assert bad == []


def test_g12_answers_and_logs_carry_no_key_or_upstream_header(st):
    st.mock.use(M.build("Contracts", {"title": "Contracts"}, [], []))
    out = st.svc.handle(req(build_req()))
    blob = json.dumps([out, st.svc.meta.lines]).lower()
    assert not KEY_RE.search(blob) and "x-api-key" not in blob and "anthropic-version" not in blob


# ── G14: presets cost nothing and are cacheable ────────────────────────────────────────────────────────────────

def test_g14_preset_fetches_make_no_anthropic_request_and_carry_cache_headers(st):
    from alto import publish_static as PS
    from alto.build import palace_assets
    assets = palace_assets.assets()
    assert assets
    for folder, name, _text in list(assets)[:20]:
        assert palace_assets.find("/" + folder + "/" + name) is not None
    assert st.mock.requests == []
    rules = PS._security_headers()
    immutable = [r for r in rules if any(h["key"] == "Cache-Control" and "immutable" in h["value"] for h in r["headers"])]
    assert immutable
    # no path to the Bass ENGINE package (alto.bass); the UI module alto.build.bass_ui is static text and imports none of it
    engine_import = re.compile(r"alto\.bass\b|from \.bass\b(?!_)|from \.\.bass\b")
    for f in ("alto/build/city_presets.py", "alto/build/palace_assets.py", "alto/publish_static.py",
              "alto/build/bass_ui.py", "alto/build/bass_ui_js.py", "alto/build/bass_ui_css.py"):
        assert not engine_import.search((ROOT / f).read_text("utf-8")), f


# ── G15: alerts ──────────────────────────────────────────────────────────────────────────────────────────────────

def test_g15_alerts_fire_once_each_at_50_80_100_percent_of_the_daily_limit(tmp_path):
    st = make_stack(tmp_path, global_daily_credits=150, trip_before_hour=0)       # no auto-trip, so the climb is not cut short
    for i in range(8):
        st.ledger.grant_opening(f"u{i}")
    for i in range(8):
        try:
            st.ledger.hold(f"u{i}", f"h{i}", 20 * MC, "a")
        except BassError:
            pass
    assert [e["percent"] for e in st.sink.of("daily_ceiling")] == [50, 80, 100]    # in order, once each, 100 when a call no longer fits
    st.clock.advance(days=1)
    st.ledger.hold("u0", "next", 20 * MC, "a")
    assert [e["percent"] for e in st.sink.of("daily_ceiling")] == [50, 80, 100]     # 13% of the new day: nothing new


def test_g15_the_period_ceiling_alerts_too(tmp_path):
    st = make_stack(tmp_path, testers=5, server_ceiling_credits=100, pool_credits=100)       # allowance 20 each
    for i in range(5):
        st.ledger.grant_opening(f"u{i}")
        st.ledger.hold(f"u{i}", f"h{i}", 20 * MC, "a")
    assert [e["percent"] for e in st.sink.of("period_ceiling")] == [50, 80, 100]


# ── logs: metadata only ──────────────────────────────────────────────────────────────────────────────────────────

def test_logs_hold_metadata_only_never_conversation_text(st, caplog):
    secret = "ZEBRA-SECRET-PHRASE-9931"
    st.mock.use(M.build("Contracts", {"title": "Contracts"}, [], []))
    with caplog.at_level("INFO", logger="bass.beta"):
        st.svc.handle(req(build_req(materials=[{"name": secret, "kind": "notes", "text": secret * 20}])))
        st.svc.handle(req(edit_req(text=secret)))
    assert st.svc.meta.lines and all(set(l) <= set(LOG_FIELDS) for l in st.svc.meta.lines)
    blob = json.dumps(st.svc.meta.lines) + caplog.text + json.dumps(st.sink.events)
    assert secret not in blob and "tester1@example.com" not in blob
    assert all({"uid", "action", "status"} <= set(l) for l in st.svc.meta.lines)
    assert any(l["out_tokens"] > 0 for l in st.svc.meta.lines)
