"""The beta allowance, end to end through the proxy on the MOCK (brief bass-beta-allowance, Luke 2026-10-30: "since we won't have paid users
in beta testing, make sure the Bass stuff will work for them at that point"). A fresh allowlisted tester with no payment method of any kind
uses every Bass path on the free allowance from Luke's pool (floor(9,000 / N) credits per period); a used-up share or pool answers with the
friendly message and sends nothing upstream; a non-allowlisted account is refused at the proxy for every action. No network, no key."""
import pytest as _pytest_sdk
_pytest_sdk.importorskip("anthropic")   # public CI has no SDK: these skip there (listed in test_bass_sdk_free.py) and run in the SDK env
_pytest_sdk.importorskip("httpx2")
import json

import pytest

from bass_support import bass_guard, ROOT  # noqa: F401
from bass_beta_support import FakeClock, MATERIALS, CHIPS, build_req, edit_req
from test_bass_beta_proxy import FakeSecrets, FakeVerifier, ORIGIN, post
from alto.bass import mock_anthropic as M
from alto.bass.beta_config import BetaConfig
from alto.bass.beta_guard import FREE
from alto.bass.beta_ledger import BASS_TESTERS_KEY, TopUpNotAllowed, confirm_key, pc_key
from alto.bass.beta_proxy import Proxy
from alto.bass.beta_store import FakeStore
from alto.bass.tools import ToolBox
from alto.store.local import LocalStore

FRESH = "fresh.tester@example.com"
USED_UP = "Your Bass beta credits are used up. Thank you for testing Bass!"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")


@pytest.fixture
def px(tmp_path):
    store, clock = FakeStore(auto_terms=True), FakeClock()
    cfg = BetaConfig(testers=10, server_ceiling_credits=9000)            # the planned ceiling; no config allowlist: the store doc decides, as in the beta
    store.put(confirm_key(cfg.period_id(clock())), {"confirmed": True})
    store.put(BASS_TESTERS_KEY, {"emails": [FRESH]})                        # IT adds the tester by hand; nothing else about them exists
    v = FakeVerifier()
    v.users["tok-fresh"] = {"uid": "u_fresh", "email": FRESH, "email_verified": True}
    p = Proxy(cfg, store, v, FakeSecrets(), ToolBox(LocalStore(tmp_path / "store")), clock=clock, origins=[ORIGIN])
    p.store, p.fclock = store, clock
    return p


def call(p, action, token="tok-fresh", **args):
    st, _, out = post(p, {"action": action, "args": args}, token=token)
    assert st == 200
    return out


def test_a_fresh_unpaid_tester_completes_every_bass_path_on_the_beta_allowance(px):
    assert px.store.get("u_fresh") is None                               # never seen: no account, no lots, no card, no purchase
    bal = call(px, "balance")
    assert bal["ok"] and bal["beta"] is True and bal["available"] is True and bal["credits"] == 900
    assert bal["label"] == "900 beta credits remaining" and bal["mock"] is True
    assert call(px, "estimate", kind="build", materials=MATERIALS)["ok"]

    px.mock.use(M.Scenario("p", [M.Step(M.Reply([M.tool_use("propose_chips", CHIPS)]))]))
    prop = call(px, "propose", materials=MATERIALS)
    assert prop["ok"] and prop["chips"]["title"] == CHIPS["title"]

    sample = json.loads((ROOT / "samples" / "contracts_brief.json").read_text("utf-8"))
    px.mock.use(M.build("Contracts", sample["brief"], sample["nodes"], sample["connections"]))
    st, _, built = post(px, build_req(), token="tok-fresh")
    assert built["ok"] and built["status"] == "ok" and built["timeline_id"] and built["credits"]["spent"] > 0

    px.mock.use(None)
    ed = call(px, "edit", **edit_req(timeline_id=built["timeline_id"])["args"])
    assert ed["status"] == "ok" and ed["code"] is None, ed

    after = call(px, "balance")
    assert 0 < after["credits"] < 900 and after["available"] is True and after["label"].endswith(" beta credits remaining")
    doc = px.store.get("u_fresh")
    assert doc["lots"] == [] and not [e for e in doc["entries"] if e["kind"] in ("purchase", "topup")]
    blob = json.dumps(doc).lower()
    for paid in ("stripe", "card", "payment", "purchase", "customer"):
        assert paid not in blob, paid                                    # nothing in the path depends on a paid account
    with pytest.raises(TopUpNotAllowed):
        px.ledger.add_purchase("u_fresh", 500, "lot1")
    assert px.mock.message_requests                                      # the mock answered every step


def _spend_share(px):
    call(px, "balance")                                                  # the opening grant
    doc = px.store.get("u_fresh")
    doc["allowance_mc"] = 0
    px.store.put("u_fresh", doc)


def _fill_pool(px):
    pid = px.ledger.period()
    px.store.put(pc_key(pid), {"period": pid, "spent_mc": px.cfg.ceiling_mc, "reserved_mc": 0, "res": {}, "alerted": [], "spend_log": []})


@pytest.mark.parametrize("use_up", [_spend_share, _fill_pool], ids=["share", "pool"])
def test_a_used_up_share_or_pool_shows_the_friendly_message_and_sends_nothing(px, use_up):
    use_up(px)
    n = len(px.mock.requests)
    bal = call(px, "balance")                                            # the UI learns it on open, before anything is tried
    assert bal["available"] is False and bal["code"] == "beta_credits_used" and bal["message"] == USED_UP
    for action, args in (("estimate", {"kind": "build", "materials": MATERIALS}), ("propose", {"materials": MATERIALS}),
                         ("build", build_req()["args"]), ("edit", edit_req()["args"]), ("grade", {"essay": "x"})):
        out = call(px, action, **args)
        assert out["ok"] is False and out["code"] == "beta_credits_used" and out["message"] == USED_UP, action
        assert "Traceback" not in json.dumps(out)
    assert len(px.mock.requests) == n                                    # not even the free token count went out


def test_a_non_allowlisted_account_is_refused_at_the_proxy_for_every_action(px):
    for action, args in (("balance", {}), ("estimate", {"kind": "build", "materials": MATERIALS}), ("propose", {"materials": MATERIALS}),
                         ("build", build_req()["args"]), ("edit", edit_req()["args"]), ("stop", {"action_id": "act_x"}),
                         ("grade", {"essay": "x"})):
        out = call(px, action, token="tok-stranger", **args)
        assert out["code"] == "bass_off" and out["available"] is False and out["ok"] is False, action
    assert px.mock.requests == [] and px.store.get("u3") is None         # no grant, no account, no upstream request


def test_only_balance_and_stop_skip_the_allowance_gate_so_a_new_bass_path_is_gated_before_it_is_wired():
    assert FREE == ("balance", "stop")
