"""STAMP-basscap (independent author): hosted PER_ACTION_CREDITS 100 -> 300 with the 400 allowance the hard total, through the REAL HostedGate
+ Proxy over a FakeStore, the model always the mock (needs the SDK: skips without it; named outside test_bass_* so test_bass_sdk_free's
pinned list is unchanged). No network, no key.

Rows: c2 a hosted 250k-character, 40-turn, cache-miss-every-turn worst case stops at 300, the 400 is never overdrawn, back to back too; the
per-tester day and the global day refuse exactly as before (same sequences at 62591229); c3 every config the old hosted_problems refused is
still refused unless it is the cap-in-(100,300] case, and the zero/negative ones it accepts are harmless; c4 the estimate only changes the
shown number (158,361-character build); c5 the 10-minute spend alert stays reachable under the 400 total."""
import pytest as _pytest_sdk
_pytest_sdk.importorskip("anthropic")
_pytest_sdk.importorskip("httpx2")
import datetime as dt
import importlib.util
import itertools
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bass_support import bass_guard, ROOT  # noqa: F401,E402
from bass_beta_support import EMAIL, build_req  # noqa: E402
from test_bass_hosted_mock_e2e import LUKE, NOW, Sec, V  # noqa: E402
from test_stamp_bassdocs_1115 import _forty_turns, _worst_usage, docs, post  # noqa: E402

from alto.bass import config as P, meter  # noqa: E402
from alto.bass.beta_ledger import LIVE_GO_KEY, BetaLedger, confirm_key, pc_key  # noqa: E402
from alto.bass.beta_proxy import Proxy  # noqa: E402
from alto.bass.beta_store import FakeStore  # noqa: E402
from alto.bass.client import make_client  # noqa: E402
from alto.bass.errors import BassError  # noqa: E402
from alto.bass.hosted import HostedGate, hosted_config, hosted_problems  # noqa: E402
from alto.bass.tools import ToolBox  # noqa: E402
from alto.store.local import LocalStore  # noqa: E402

BASE = "62591229"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")
    monkeypatch.delenv("ALTO_PAYWALL", raising=False)


def rig(tmp_path, **kw):
    t = [NOW]
    store, cfg = FakeStore(auto_terms=True), hosted_config(**kw)
    clock = lambda: t[0]
    store.put(confirm_key(cfg.period_id(NOW)), {"confirmed": True})
    store.put("bass_beta/bass_testers", {"emails": [EMAIL]})
    store.put("bass_beta/hosted", {"uids": [LUKE]})
    store.put(LIVE_GO_KEY, {"on": True})
    p = Proxy(cfg, store, V(), Sec(), ToolBox(LocalStore(tmp_path / "s")), clock=clock)
    p._client, p._client_mode = make_client("mock", mock=p.mock), "live"
    g = HostedGate(p, store, V(), cfg=cfg, pins=frozenset({LUKE}), clock=clock)
    return g, p, store, t


def _library(g, t, chars):
    c = docs(g, t, "add_scope", kind="class", name="Torts")["scope"]["id"]
    assert docs(g, t, "add", scope_id=c, name="Pasted.txt", text=("Negligence duty breach cause. " * 9000)[:chars])["ok"]
    return c


def _spy_holds(monkeypatch, ledger):
    holds = []
    real = type(ledger).hold

    def spy(self, uid, hold_id, mc, action_id, worst_mc=None):
        holds.append((mc, worst_mc))
        return real(self, uid, hold_id, mc, action_id, worst_mc=worst_mc)
    monkeypatch.setattr(type(ledger), "hold", spy)
    return holds


# ── c2: the hard stops ───────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("gap_s", [120, 0])
def test_c2_hosted_worst_case_stops_at_300_and_never_overdraws_400_back_to_back(tmp_path, monkeypatch, gap_s):
    g, p, store, t = rig(tmp_path)
    _worst_usage(monkeypatch, p.mock)
    c = _library(g, t, 250_000)
    holds = _spy_holds(monkeypatch, p.ledger)
    post(g, {"action": "balance", "args": {}})
    assert p.ledger.balance_mc(LUKE) == 400 * P.MC
    used, codes = [], []
    for _ in range(6):
        p.mock.use(_forty_turns())
        before = p.ledger.balance_mc(LUKE)
        t[0] += dt.timedelta(seconds=gap_s or 1)
        _, out = post(g, build_req(scope_id=c, materials=[]))
        used.append(before - p.ledger.balance_mc(LUKE))
        codes.append(out.get("status") or out.get("code"))
        assert 0 <= used[-1] <= 300 * P.MC and p.ledger.balance_mc(LUKE) >= 0, (used, codes)
        if used[-1] == 0:
            break
    pc = store.get(pc_key(hosted_config().period_id(NOW)))
    print("C2", gap_s, [u / P.MC for u in used], codes, "max hold", max(m for m, _ in holds) / P.MC, "books", pc["spent_mc"] / P.MC,
          "reserved", pc["reserved_mc"])
    assert used[0] > 290 * P.MC                                     # the first action really runs to the 300 cap
    assert sum(used) <= 400 * P.MC and used[1] <= 400 * P.MC - used[0] and used[-1] == 0, used
    assert pc["spent_mc"] <= 400 * P.MC and pc["reserved_mc"] == 0
    assert all(m == w and m <= 300 * P.MC for m, w in holds)        # every hold is worst_turn, never above the cap


def _seq(cfg, amounts, next_day=True):
    """Hold+settle each amount (credits) on one ledger, then one more the next day: the refusal sequence (code:why) is what the stamp
    compares across trees."""
    store, t = FakeStore(auto_terms=True), [NOW]
    store.put(confirm_key(cfg.period_id(NOW)), {"confirmed": True})
    led = BetaLedger(store, cfg, lambda: t[0], sleep=lambda s: None)
    out = []
    for i, a in enumerate(list(amounts) + ([amounts[-1]] if next_day else [])):
        if next_day and i == len(amounts):
            t[0] = NOW + dt.timedelta(days=1)
        try:
            led.hold(LUKE, f"h{i}", a * P.MC, f"a{i}", worst_mc=a * P.MC)
            led.settle(LUKE, f"h{i}", a * P.MC)
            out.append("ok")
        except BassError as e:
            out.append(f"{e.code}:{(e.detail or {}).get('why')}")
    return out


TD, GD, TP = "beta_tester_daily:tester_daily", "beta_daily_full:global_daily", "beta_credits_used:tester_period"
# The same sequences pass at 62591229 (the stamp ran this test there too): the day limits and the ceiling refuse exactly as before.
SEQS = [
    (dict(per_action_cap_credits=100, tester_daily_credits=250), [70] * 5, ["ok"] * 3 + [TD] * 2 + ["ok"]),
    (dict(per_action_cap_credits=100, global_daily_credits=250), [70] * 5, ["ok"] * 3 + [GD] * 2 + ["ok"]),
    (dict(per_action_cap_credits=100), [70] * 6, ["ok"] * 5 + [TD, TP]),
    (dict(per_action_cap_credits=100), [100] * 5, ["ok"] * 4 + [TD, TP]),
    (dict(per_action_cap_credits=100, tester_daily_credits=200), [100] * 3 + [100] * 3, ["ok", "ok", TD, TD, TD, TD, "ok"][:6] + ["ok"]),
]


@pytest.mark.parametrize("kw,amounts,want", SEQS)
def test_c2_seq_the_day_limits_and_the_ceiling_refuse_as_at_62591229(kw, amounts, want):
    cfg = hosted_config(spike_credits=100, spike_alert_credits=200, **kw)
    assert hosted_problems(cfg, NOW) == []
    got = _seq(cfg, amounts)
    print("SEQ", kw, amounts, got)
    assert got == want


def test_c2_hosted_300_day_and_global_limits_refuse_the_second_action(tmp_path):
    if hosted_config().per_action_cap_credits != 300:
        pytest.skip("the 300 cap is the head's")
    assert _seq(hosted_config(tester_daily_credits=350), [300, 300]) == ["ok", TD, TP]
    assert _seq(hosted_config(global_daily_credits=350), [300, 60]) == ["ok", GD, "ok"]
    assert _seq(hosted_config(), [300, 300, 100]) == ["ok", TD, "ok", TP]
    assert _seq(hosted_config(), [300, 100, 1]) == ["ok", "ok", TD, TP]


# ── c3: the hosted_problems replacement ──────────────────────────────────────────────────────────────────────────────
def _old_hosted_problems(tmp_path):
    try:
        src = subprocess.run(["git", "-C", str(ROOT), "show", f"{BASE}:alto/bass/hosted.py"], capture_output=True, text=True, check=True).stdout
    except Exception:
        pytest.skip("no git history for the base")
    f = tmp_path / "hosted_old.py"
    f.write_text(src.replace("from . import promo", "from alto.bass import promo").replace("from .", "from alto.bass."))
    spec = importlib.util.spec_from_file_location("hosted_old_62591229", f)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.PER_ACTION_CREDITS == 100
    return m.hosted_problems


VALS = dict(pool_credits=[-1, 0, 400, 500, 501],
            server_ceiling_credits=[-1, 0, 1, 100, 200, 300, 399, 400, 401, 450, 500],
            per_action_cap_credits=[-1, 0, 1, 100, 101, 200, 300, 301, 400, 401],
            tester_daily_credits=[-1, 0, 100, 300, 400, 401],
            global_daily_credits=[-1, 0, 100, 300, 400, 401],
            testers=[0, 1, 2])


def _problems(fn, cfg):
    try:
        return fn(cfg, NOW)
    except ZeroDivisionError:                                 # testers=0: the derived allowance divides by zero, so the start fails closed
        return ["raises"]


def test_c3_every_config_the_old_check_refused_is_still_refused_unless_it_is_the_boards_cap_case(tmp_path):
    old = _old_hosted_problems(tmp_path)
    loosened, tightened, n = [], [], 0
    keys = list(VALS)
    for combo in itertools.product(*(VALS[k] for k in keys)):
        kw = dict(zip(keys, combo))
        try:
            cfg = hosted_config(**kw)
        except Exception:
            continue
        n += 1
        o, w = _problems(old, cfg), _problems(hosted_problems, cfg)
        if o and not w:
            loosened.append(kw)
        if w and not o:
            tightened.append(kw)
    print("C3", n, "configs; loosened", len(loosened), "tightened", len(tightened))
    for kw in loosened:                                       # only the Board's case: a cap above 100 and at most 300, inside the 400
        assert 100 < kw["per_action_cap_credits"] <= 300, kw
        assert kw["testers"] == 1 and 0 < kw["server_ceiling_credits"] <= 400 and kw["pool_credits"] <= 500, kw
        assert kw["per_action_cap_credits"] <= kw["global_daily_credits"] <= kw["server_ceiling_credits"], kw
        assert kw["tester_daily_credits"] <= kw["server_ceiling_credits"], kw          # a negative day only refuses everything
    assert loosened and any(kw["per_action_cap_credits"] == 300 and kw["server_ceiling_credits"] == 400 for kw in loosened)
    for kw in tightened:                                      # the new rule is stricter on the ceiling: 401-450 with a small cap is now refused
        assert kw["server_ceiling_credits"] > 400, kw


@pytest.mark.parametrize("kw", [dict(server_ceiling_credits=401), dict(server_ceiling_credits=450, per_action_cap_credits=50),
                                dict(server_ceiling_credits=200, per_action_cap_credits=300, global_daily_credits=200, tester_daily_credits=200),
                                dict(server_ceiling_credits=0), dict(server_ceiling_credits=-1), dict(pool_credits=0),
                                dict(per_action_cap_credits=301), dict(testers=2), dict(pool_credits=501)])
def test_c3_named_bad_configs_are_refused(kw):
    """A ceiling above 400; an allowance above the ceiling cannot be built (allowance = ceiling // testers, testers must be 1); a cap above
    the allowance (cap <= global day <= ceiling); a zero or negative ceiling or pool."""
    try:
        cfg = hosted_config(**kw)
    except ValueError:                                        # a zero or negative ceiling cannot even be built: the start fails closed
        return
    assert _problems(hosted_problems, cfg), kw


@pytest.mark.parametrize("kw", [dict(per_action_cap_credits=0), dict(per_action_cap_credits=-1), dict(per_action_cap_credits=100, tester_daily_credits=0),
                                dict(per_action_cap_credits=100, tester_daily_credits=-1), dict(global_daily_credits=0, per_action_cap_credits=0)])
def test_c3_zero_or_negative_values_both_checks_accept_are_harmless(tmp_path, kw):
    old = _old_hosted_problems(tmp_path)
    cfg = hosted_config(**kw)
    assert _problems(old, cfg) == _problems(hosted_problems, cfg)            # not a new loosening either way
    if not hosted_problems(cfg, NOW):                                         # accepted: then nothing can be spent
        g, p, store, t = rig(tmp_path / "r", **kw)
        c = _library(g, t, 2000)
        post(g, {"action": "balance", "args": {}})
        p.mock.use(_forty_turns())
        before = p.ledger.balance_mc(LUKE)
        _, out = post(g, build_req(scope_id=c, materials=[]))
        assert p.ledger.balance_mc(LUKE) == before, out


# ── c4: the estimate ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_c4_the_158k_build_estimate_is_only_shown_and_never_feeds_a_hold(tmp_path, monkeypatch):
    g, p, store, t = rig(tmp_path)
    c = _library(g, t, 158_361)
    post(g, {"action": "balance", "args": {}})
    bal = p.ledger.balance_mc(LUKE)
    _, est = post(g, build_req(scope_id=c, materials=[], accepted=False))
    print("C4 shown", est.get("estimate_credits"), est.get("credits_text"), est.get("show_prompt"), est.get("short_by"))
    assert est.get("status") == "estimate" and est["show_prompt"] is True and 0 < est["estimate_credits"] <= 300
    assert p.ledger.balance_mc(LUKE) == bal                                   # asking spends and holds nothing
    holds = _spy_holds(monkeypatch, p.ledger)
    p.mock.use(_forty_turns())
    t[0] += dt.timedelta(minutes=2)
    post(g, build_req(scope_id=c, materials=[]))
    base = list(holds)
    g2, p2, _, t2 = rig(tmp_path / "b")
    c2 = _library(g2, t2, 158_361)
    post(g2, {"action": "balance", "args": {}})
    monkeypatch.setattr(meter, "estimate_action", lambda *a, **k: meter.Estimate(1, 1, False))
    holds.clear()
    p2.mock.use(_forty_turns())
    t2[0] += dt.timedelta(minutes=2)
    post(g2, build_req(scope_id=c2, materials=[]))
    assert holds == base and p2.service.actions.engine.cfg.per_action_cap_mc == 300 * P.MC     # the estimate rewritten: identical holds, same cap


# ── c5: the 10-minute spend alert ────────────────────────────────────────────────────────────────────────────────────
def test_c5_the_hosted_10_minute_spend_alert_stays_reachable(tmp_path, monkeypatch):
    g, p, store, t = rig(tmp_path)
    _worst_usage(monkeypatch, p.mock)
    c = _library(g, t, 250_000)
    post(g, {"action": "balance", "args": {}})
    for _ in range(3):
        p.mock.use(_forty_turns())
        t[0] += dt.timedelta(seconds=20)
        post(g, build_req(scope_id=c, materials=[]))
    print("C5 alert", hosted_config().spike_alert_credits, p.sink.kinds())
    assert "spend_over_alert_10min" in p.sink.kinds()
