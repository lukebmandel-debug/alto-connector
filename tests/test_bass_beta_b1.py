"""Security finding B1 (reports/security-review.md, MEDIUM, Luke: fix before the beta): normal use by one tester at midnight, or by two at once,
switched Bass off for EVERYONE (the kill switch, reset by hand only). Reproduced here with the reviewer's own cases on the real ledger and
watchdog, then the fix: no spend the caps allow can trip the switch; spend the caps should have made impossible still does."""
import datetime as dt

from bass_support import ROOT  # noqa: F401
from bass_beta_support import FakeClock, make_stack
from test_bass_beta import spend
from alto.bass.beta_config import MC, BetaConfig


def _at(h, m):                                       # New York wall time on Tue 3 Nov 2026
    from zoneinfo import ZoneInfo
    return FakeClock(dt.datetime(2026, 11, 3, h, m, tzinfo=ZoneInfo("America/New_York")).astimezone(dt.timezone.utc))


def test_b1_two_testers_spending_250_five_minutes_apart_do_not_switch_bass_off(tmp_path):
    st = make_stack(tmp_path)
    spend(st, "u1", 250, hid="a")
    st.clock.advance(300)
    spend(st, "u2", 250, hid="b")
    assert not st.kill.is_on(), st.kill.state()


def test_b1_one_tester_at_midnight_within_both_days_caps_does_not_switch_bass_off(tmp_path):
    st = make_stack(tmp_path, clock=_at(23, 55))
    spend(st, "u1", 250, hid="a")
    st.clock.advance(7 * 60)                                                 # 00:02, a new day: a fresh 300
    spend(st, "u1", 250, hid="b")
    assert not st.kill.is_on(), st.kill.state()


def test_b1_a_busy_morning_up_to_the_daily_limit_does_not_switch_bass_off(tmp_path):
    """Five testers at their 300/day by 10:00 = the 1,500 day: the day's own cap refuses the rest (and resets at midnight by itself);
    it is an alert, never the hand-reset kill switch for everyone."""
    st = make_stack(tmp_path, testers=15)
    for i in range(5):
        spend(st, f"u{i}", 250, hid=f"h{i}")                                 # 1,250 = 83% by 11:00
        st.clock.advance(15 * 60)
    assert not st.kill.is_on(), st.kill.state()
    assert st.sink.of("daily_over_80_before_18")                             # Luke and IT still hear about it


def test_b1_the_heaviest_legitimate_ten_minutes_never_trips(tmp_path):
    """Every tester spends their whole day just before midnight and again just after, as fast as the guards allow."""
    st = make_stack(tmp_path, testers=15, clock=_at(23, 52))
    for day in range(2):
        for i in range(15):
            st.ledger.grant_opening(f"u{i}")
            for k in range(2):
                try:
                    spend(st, f"u{i}", 150, hid=f"d{day}u{i}k{k}")
                except Exception:
                    pass                                                     # refused by a cap: that is the cap working
        st.clock.advance(9 * 60)
    assert not st.kill.is_on(), st.kill.state()


def test_b1_spend_past_what_the_caps_allow_still_trips_the_switch(tmp_path):
    """If the books ever let more through in 10 minutes than the caps permit, something is broken: stop for everyone, as before."""
    st = make_stack(tmp_path)
    cfg = st.cfg
    g = {"spent_mc": 0, "reserved_mc": 0}
    now = st.clock().timestamp()
    st.ledger.on_commit(g, {"spend_log": [[now, cfg.spike_trip_mc + MC]]})
    assert st.kill.state()["reason"] == "spend_spike_10min"


def test_b1_the_spike_threshold_is_above_what_the_caps_allow():
    for n in (1, 10, 15):
        c = BetaConfig(testers=n)
        legit = min(n * 2 * c.tester_daily_mc, 2 * c.daily_ceiling_mc)       # every account across one midnight, bounded by two global days
        assert c.spike_trip_mc > legit + c.per_action_cap_mc - 1
        assert c.spike_trip_mc >= c.spike_mc                                  # a configured higher threshold is kept
