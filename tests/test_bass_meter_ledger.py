"""usage -> credits arithmetic (meter.py) and the credits ledger (ledger.py)."""
import datetime as dt
import json
from pathlib import Path
from fractions import Fraction

import pytest

from bass_support import bass_guard  # noqa: F401
from alto.bass import meter, config as P
from alto.bass import mock_anthropic as M
from alto.bass.client import make_client
from alto.bass.errors import CapReached, InsufficientCredits
from alto.bass.ledger import JsonFileStore, Ledger, MemoryStore

H, S = P.HAIKU, P.SONNET
MC = P.MC


def u(i=0, o=0, cr=0, cw=0):
    return {"input_tokens": i, "output_tokens": o, "cache_read_input_tokens": cr, "cache_creation_input_tokens": cw}


# ── meter ──────────────────────────────────────────────────────────────────────────────────────────────────────

def test_prices_json_is_the_one_table(tmp_path):
    org = Path.home() / "Desktop/Terrarium/Alto/ORG/it/studio-key/prices.json"
    if org.is_file():                                               # the copy beside the code never drifts from IT's table
        strip = lambda d: {k: v for k, v in d.items() if not k.startswith("_")}      # notes may differ, numbers may not
        assert strip(json.loads(org.read_text())) == strip(json.loads(meter.PRICES_FILE.read_text()))
    assert meter.CREDITS_PER_USD == 100
    bad = tmp_path / "p.json"
    bad.write_text(json.dumps({"credits_per_usd": 100, "models": {"m": {"input": 1, "output": None,
                                                                         "cache_write": 1, "cache_read": 1}}}))
    with pytest.raises(ValueError):
        meter.load_prices(bad)                                      # an unpriced model is never metered as free
    assert not (Path(meter.__file__).with_name("prices.py")).exists()


def test_prices_are_the_cached_skill_table():
    assert meter.PRICES[H].base.inp == Fraction("0.10") and meter.PRICES[H].base.out == Fraction("0.50")
    assert meter.PRICES[S].base.inp == 2 and meter.PRICES[S].base.out == 10 and meter.PRICES[S].base.cache_read == Fraction("0.1")
    assert meter.price_for(H).long.inp == Fraction("0.50") and meter.price_for(H).long_threshold == 100_000
    with pytest.raises(KeyError):
        meter.price_for("claude-opus-9")


def test_haiku_arithmetic():
    # 1000 in + 1000 out = $0.0001 + $0.0005 = $0.0006 = 0.06 credit = 60 milli-credits
    assert meter.credits_for_usage(H, u(1000, 1000)) == 60


def test_sonnet_arithmetic_and_cache_rates():
    assert meter.credits_for_usage(S, u(10_000, 2_000)) == 4 * MC            # $0.02 + $0.02 = 4 credits
    assert meter.credits_for_usage(S, u(cr=10_000)) == 100                    # cache read $0.10/MTok = 0.1 credit
    assert meter.credits_for_usage(S, u(cw=4_000)) == 1 * MC                  # cache write 1.25x = $2.50/MTok
    assert meter.credits_for_usage(S, u(10_000, 2_000, cr=10_000, cw=4_000)) == 4 * MC + 100 + 1 * MC


def test_long_prompt_tier_prices_the_whole_request():
    base = meter.credits_for_usage(H, u(100_000, 1_000))                      # exactly at the threshold: base tier
    assert base == 1050                                                       # $0.01 + $0.0005 = 1.05 credits
    over = meter.credits_for_usage(H, u(100_001, 1_000))
    assert over > base * 4                                                    # 5x tier, on every token
    assert meter.credits_for_usage(H, u(150_000, 1_000)) == 7750


def test_cache_tokens_count_toward_the_tier():
    assert meter.prompt_tokens(u(60_000, cr=50_000)) == 110_000
    assert meter.rate_for(H, 110_000) is meter.PRICES[H].long
    assert meter.rate_for(S, 900_000) is meter.PRICES[S].base                     # Sonnet has no long tier


def test_rounds_up_never_to_zero():
    assert meter.credits_for_usage(H, u(1)) == 1
    assert meter.credits_for_usage(H, u()) == 0


def test_sdk_usage_object_and_none_fields():
    class Uo:
        input_tokens, output_tokens = 1000, 1000
        cache_creation_input_tokens, cache_read_input_tokens = None, None
    assert meter.credits_for_usage(H, Uo()) == 60


def test_credits_text_is_plain_words():
    assert meter.credits_text(0) == "less than 1 credit"
    assert meter.credits_text(999) == "less than 1 credit"
    assert meter.credits_text(1000) == "about 1 credit"
    assert meter.credits_text(1001) == "about 2 credits"


def test_estimate_threshold():
    small = meter.estimate_action(S, 3000, 500, turns=1)
    assert not small.show_prompt and "credit" in small.message
    big = meter.estimate_action(S, 8000, 4000, turns=12)
    assert big.show_prompt and big.mc > P.ESTIMATE_THRESHOLD_CREDITS * MC


def test_estimate_is_an_upper_bound_on_the_mock_cost():
    mock = M.MockAnthropic(M.Scenario("t", [M.Step(M.say("a short answer"))]))
    c = make_client("mock", mock=mock)
    msgs = [{"role": "user", "content": "hello " * 200}]
    n = c.messages.count_tokens(model=S, messages=msgs).input_tokens
    r = c.messages.create(model=S, max_tokens=800, messages=msgs)
    assert r.usage.input_tokens == n
    assert meter.estimate_turn(S, n, 800) >= meter.credits_for_usage(S, r.usage) > 0


def test_cost_of_real_shaped_mock_usage_matches_hand_math():
    mock = M.MockAnthropic(M.Scenario("t", [M.Step(M.say("x" * 350))]))
    c = make_client("mock", mock=mock)
    r = c.messages.create(model=S, max_tokens=800, messages=[{"role": "user", "content": "y" * 7000}])
    want = Fraction(r.usage.input_tokens * 2 + r.usage.output_tokens * 10, 1_000_000) * 100 * 1000
    assert meter.credits_for_usage(S, r.usage) == -(-want.numerator // want.denominator)


# ── ledger ─────────────────────────────────────────────────────────────────────────────────────────────────────

class Clock:
    def __init__(self, t="2026-10-28T12:00:00+00:00"):
        self.t = dt.datetime.fromisoformat(t)

    def __call__(self):
        return self.t

    def add(self, **kw):
        self.t += dt.timedelta(**kw)


@pytest.fixture
def L():
    clk = Clock()
    return Ledger(MemoryStore(), clock=clk), clk


def test_allowance_is_idempotent_per_month_and_does_not_roll_over(L):
    led, clk = L
    assert led.grant_allowance("u", 100) == 100 * MC
    assert led.grant_allowance("u", 100) == 100 * MC                          # same month: no second grant
    led.hold("u", "h", 30 * MC, "a")
    led.settle("u", "h", 30 * MC)
    assert led.balance_mc("u") == 70 * MC
    clk.add(days=35)
    assert led.grant_allowance("u", 100) == 100 * MC                          # 70 left over is gone, not added
    kinds = [e["kind"] for e in led.entries("u")]
    assert "expire" in kinds and kinds.count("allowance") == 2


def test_hold_settle_release_arithmetic(L):
    led, _ = L
    led.grant_allowance("u", 10)
    led.hold("u", "h", 4 * MC, "a")
    assert led.balance_mc("u") == 6 * MC and led.held_mc("u") == 4 * MC
    r = led.settle("u", "h", 1500, note="t")
    assert r == {"charged_mc": 1500, "released_mc": 2500, "absorbed_mc": 0}
    assert led.balance_mc("u") == 10 * MC - 1500 and led.held_mc("u") == 0
    assert led.action_spent_mc("u", "a") == 1500
    assert [e["kind"] for e in led.entries("u")][-2:] == ["usage", "release"]


def test_overdraw_fails_before_anything_moves(L):
    led, _ = L
    led.grant_allowance("u", 2)
    with pytest.raises(InsufficientCredits):
        led.hold("u", "h", 3 * MC, "a")
    assert led.balance_mc("u") == 2 * MC and led.held_mc("u") == 0
    with pytest.raises(InsufficientCredits):
        Ledger(MemoryStore()).hold("nobody", "h", 1, "a")                    # an account with nothing


def test_settle_over_the_hold_is_absorbed_and_balance_never_negative(L):
    led, _ = L
    led.grant_allowance("u", 5)
    led.hold("u", "h", 4 * MC, "a")
    r = led.settle("u", "h", 9 * MC)                                          # estimate was low
    assert r["charged_mc"] == 5 * MC and r["absorbed_mc"] == 4 * MC           # took all that was left, Alto ate 4
    assert led.balance_mc("u") == 0
    assert any(e["kind"] == "absorbed" for e in led.entries("u"))


def test_uncharged_settle_returns_the_whole_hold(L):
    led, _ = L
    led.grant_allowance("u", 5)
    led.hold("u", "h", 2 * MC, "a")
    r = led.settle("u", "h", 700, charge=False, note="gate")
    assert r == {"charged_mc": 0, "released_mc": 2 * MC, "absorbed_mc": 700}
    assert led.balance_mc("u") == 5 * MC and led.action_spent_mc("u", "a") == 0


def test_allowance_spent_before_purchase_and_lots_by_expiry(L):
    led, clk = L
    led.grant_allowance("u", 3)
    led.add_purchase("u", 10, "lotA")
    clk.add(days=10)
    led.add_purchase("u", 10, "lotB")
    led.hold("u", "h", 5 * MC, "a")
    led.settle("u", "h", 5 * MC)
    d = led.store.get("u")
    assert d["allowance_mc"] == 0                                              # allowance first
    lots = {l["id"]: l["mc"] for l in d["lots"]}
    assert lots == {"lotA": 8 * MC, "lotB": 10 * MC}                          # then the earliest-expiring lot


def test_purchase_replay_is_ignored_and_lots_expire_after_12_months(L):
    led, clk = L
    led.add_purchase("u", 10, "pay_1")
    led.add_purchase("u", 10, "pay_1")
    assert led.balance_mc("u") == 10 * MC
    clk.add(days=P.PURCHASE_LIFETIME_DAYS + 1)
    assert led.balance_mc("u") == 0
    assert any(e["kind"] == "expire" for e in led.entries("u"))


def test_refund_goes_back_to_the_bucket_it_came_from(L):
    led, _ = L
    led.grant_allowance("u", 2)
    led.add_purchase("u", 10, "lot")
    led.hold("u", "h", 5 * MC, "a")
    led.settle("u", "h", 5 * MC)                                               # 2 allowance + 3 purchased
    assert led.refund("u", "a", "refusal", mc=4 * MC) == 4 * MC
    d = led.store.get("u")
    assert d["allowance_mc"] == 2 * MC and d["lots"][0]["mc"] == 9 * MC
    assert led.refund("u", "a", "rest") == 1 * MC                              # default = everything still owed
    assert led.refund("u", "a", "again") == 0                                  # nothing left to refund
    assert led.balance_mc("u") == 12 * MC and led.action_spent_mc("u", "a") == 0


def test_allowance_refund_after_the_month_rolled_is_dropped(L):
    led, clk = L
    led.grant_allowance("u", 5)
    led.hold("u", "h", 3 * MC, "a")
    led.settle("u", "h", 3 * MC)
    clk.add(days=35)
    led.grant_allowance("u", 5)
    assert led.refund("u", "a", "late") == 0 and led.balance_mc("u") == 5 * MC  # no rollover, even by refund


def test_daily_and_monthly_ceilings(L, monkeypatch):
    led, clk = L
    monkeypatch.setattr(P, "DAILY_CEILING_CREDITS", 10)
    monkeypatch.setattr(P, "MONTHLY_CEILING_CREDITS", 15)
    led.grant_allowance("u", 100)
    led.hold("u", "h1", 8 * MC, "a")
    led.settle("u", "h1", 8 * MC)
    with pytest.raises(CapReached) as e:
        led.hold("u", "h2", 3 * MC, "a")
    assert e.value.code == "daily_cap"
    clk.add(days=1)
    led.hold("u", "h3", 7 * MC, "a")
    led.settle("u", "h3", 7 * MC)
    clk.add(days=1)
    with pytest.raises(CapReached) as e2:
        led.hold("u", "h4", 2 * MC, "a")
    assert e2.value.code == "monthly_cap"
    assert led.spent_today_mc("u") == 0 and led.spent_month_mc("u") == 15 * MC


def test_inflight_holds_count_toward_the_ceiling(L, monkeypatch):
    led, _ = L
    monkeypatch.setattr(P, "DAILY_CEILING_CREDITS", 10)
    led.grant_allowance("u", 100)
    led.hold("u", "h1", 6 * MC, "a")
    with pytest.raises(CapReached):
        led.hold("u", "h2", 5 * MC, "b")


def test_release_drops_a_hold_with_no_cost(L):
    led, _ = L
    led.grant_allowance("u", 5)
    led.hold("u", "h", 2 * MC, "a")
    assert led.release("u", "h") == 2 * MC and led.release("u", "h") == 0
    assert led.balance_mc("u") == 5 * MC and led.action_spent_mc("u", "a") == 0


def test_invariant_nothing_is_created_or_lost(L):
    led, _ = L
    led.grant_allowance("u", 50)
    led.add_purchase("u", 20, "lot")
    total = 70 * MC
    charged = 0
    for i, (hold, actual) in enumerate([(5, 3), (4, 4), (6, 1), (3, 9)]):
        led.hold("u", f"h{i}", hold * MC, f"a{i % 2}")
        charged += led.settle("u", f"h{i}", actual * MC)["charged_mc"]
    refunded = led.refund("u", "a0", "x", mc=2 * MC)
    assert led.held_mc("u") == 0
    assert led.balance_mc("u") + charged - refunded == total                   # absorbed cost is Alto's, not ours
    assert led.balance_mc("u") >= 0


def test_json_file_store_round_trip(tmp_path):
    clk = Clock()
    a = Ledger(JsonFileStore(tmp_path / "led"), clock=clk)
    a.grant_allowance("user/1", 12)
    a.hold("user/1", "h", 2 * MC, "act")
    b = Ledger(JsonFileStore(tmp_path / "led"), clock=clk)                     # a second process reading the same doc
    assert b.balance_mc("user/1") == 10 * MC and b.held_mc("user/1") == 2 * MC
    b.settle("user/1", "h", 500)
    assert a.balance_mc("user/1") == 12 * MC - 500
    assert not list((tmp_path / "led").glob("*.tmp"))
