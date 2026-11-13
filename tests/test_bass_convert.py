"""Bass route of "Turn into another format…": a file's own cards in, a new timeline out, closed system, mock only.

The grounding check fails closed: nothing is kept and nothing is charged. The entitlement check runs first, on the format being
made, before any read, hold or upstream call. No network, no key, no count_tokens (the mock counts)."""
import pytest as _pytest_sdk
_pytest_sdk.importorskip("anthropic")   # public CI has no SDK: these skip there (listed in test_bass_sdk_free.py) and run in the SDK env
_pytest_sdk.importorskip("httpx2")
import copy
import json
import sys
from pathlib import Path

import pytest

from bass_support import bass_guard, ROOT  # noqa: F401
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bass_apidoc as D
from alto import entitlements as ENT
from alto import mcp_server as srv
from alto.bass import actions as A
from alto.bass import config as P
from alto.bass import convert as C
from alto.bass import mock_anthropic as M

OUTLINE = json.loads((ROOT / "samples" / "outline_brief.json").read_text("utf-8"))
MC = P.MC


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")
    monkeypatch.delenv("ALTO_PAYWALL", raising=False)
    yield
    ENT.set_plan_lookup(None)
    srv.set_store(None)


@pytest.fixture
def env(tmp_path):
    e = D.make_env(tmp_path / "store", allowance=2000)
    e.acts.engine.cfg.actions_per_minute = 100
    yield e
    srv.set_store(None)


def _source(e):
    """The student's own outline, built the usual way: -> its timeline id."""
    e.mock.use(M.build("Law", OUTLINE["brief"], OUTLINE["nodes"], OUTLINE["connections"]))
    out = e.acts.dispatch("student", {"action": "build", "args": {"chips": D.CHIPS, "materials": D.MATERIALS,
                                                                   "consent": True, "accepted": True}})
    assert out["ok"], out
    return out["timeline_id"]


def _store(e):
    srv.set_store(e.tools.store)
    return srv.get_store()


def _scenario(e, tid, nodes=None, report="good", brief_over=None, drop_report=None):
    """What a well-behaved model does: a new timeline (a plain one), the same cards, build, report."""
    st = _store(e)
    src = st.list_nodes("student", tid)
    new = nodes if nodes is not None else [{k: v for k, v in n.items() if k in ("id", "act", "tag", "title", "desc", "sections")} for n in src]
    new = copy.deepcopy(new)
    for n in new:
        n["id"] = "c-" + n["id"]
    brief = {**OUTLINE["brief"], "mode": "linear", "timeline_id": "converted", "title": "Law (timeline)", **(brief_over or {})}
    brief.pop("layout", None)
    rep = {"cards": [{"card": n["id"], "from": [n["id"][2:]]} for n in new]}
    if report == "none":
        rep = {"cards": [{"card": n["id"], "from": []} for n in new]}
    if drop_report is not None:
        rep["cards"] = [r for r in rep["cards"] if r["card"] != "c-" + drop_report]
    pid = st.get_timeline("student", tid)["project_id"]

    def tl(c):
        return c.find_in_results("timeline_id") or "converted"
    steps = [
        M.Step(M.Reply([M.text("Making it."), M.tool_use("create_timeline", {"project_id": pid, "brief": brief})])),
        M.Step(lambda c: M.Reply([M.tool_use("record_materials_consent", {"timeline_id": tl(c), "sources": [{"name": "Law", "kind": "timeline"}], "consent": True})])),
        M.Step(lambda c: M.Reply([M.tool_use("add_nodes", {"timeline_id": "converted", "nodes": new})])),
        M.Step(lambda c: M.Reply([M.tool_use("build_timeline", {"timeline_id": "converted"})])),
        M.Step(lambda c: M.Reply([M.tool_use("report_sources", rep)])),
    ]
    return M.Scenario("convert", steps), new


def _convert(e, tid, **kw):
    args = {"timeline_id": tid, "target": "timeline", "consent": True, "accepted": True}
    args.update(kw)
    return e.acts.dispatch("student", {"action": "convert", "args": args})


# ── the grounding check, pure ──────────────────────────────────────────────

SRC = [{"id": "a", "title": "Offer", "desc": "A manifestation of willingness to enter a bargain."},
       {"id": "b", "title": "Acceptance", "desc": "Assent to the terms of the offer."}]


def test_ground_passes_a_faithful_rearrangement_and_says_the_counts():
    made = [{"id": "x", "title": "Acceptance", "desc": "Assent to the terms of the offer."},
            {"id": "y", "title": "Offer", "desc": "A manifestation of willingness."}]
    g = C.ground(SRC, made, {"cards": [{"card": "x", "from": ["b"]}, {"card": "y", "from": ["a"]}]})
    assert g == {"ok": True, "reasons": [], "cards_in": 2, "cards_out": 2}


@pytest.mark.parametrize("made,report,needle", [
    ([{"id": "x", "title": "Offer", "desc": "Assent, and also promissory estoppel."}],
     {"cards": [{"card": "x", "from": ["a"]}]}, "words not in its source cards"),
    ([{"id": "x", "title": "Offer", "desc": "A manifestation of willingness."}],
     {"cards": [{"card": "x", "from": ["a"]}]}, "source cards left out"),
    ([{"id": "x", "title": "Offer", "desc": ""}, {"id": "y", "title": "Acceptance", "desc": ""}],
     {"cards": [{"card": "x", "from": ["a"]}]}, "names no source"),
    ([{"id": "x", "title": "Offer", "desc": ""}, {"id": "y", "title": "Acceptance", "desc": ""}],
     {"cards": [{"card": "x", "from": ["a"]}, {"card": "y", "from": ["zzz"]}]}, "unknown source"),
    ([{"id": "x", "title": "Offer", "desc": ""}, {"id": "y", "title": "Acceptance", "desc": ""}],
     {"cards": [{"card": "x", "from": []}, {"card": "y", "from": ["b"]}]}, "no real source"),
    ([{"id": "x", "title": "Offer", "desc": ""}],
     {"cards": [{"card": "x", "from": ["a"]}, {"card": "ghost", "from": ["b"]}]}, "was not made"),
    ([{"id": "x", "title": "Offer", "desc": ""}], None, "no source report"),
])
def test_ground_fails_closed(made, report, needle):
    g = C.ground(SRC, made, report)
    assert g["ok"] is False and any(needle in r for r in g["reasons"]), g


# ── the action ─────────────────────────────────────────────────────────────

def test_it_estimates_first_at_a_safe_constant_without_calling_the_model(env):
    tid = _source(env)
    n = len(env.mock.message_requests)
    out = _convert(env, tid, accepted=False)
    assert out["status"] == "estimate" and out["show_prompt"] is True and out["kind"] == "convert"
    assert out["estimate_credits"] >= C.CONVERT_SAFE_CREDITS and out["cards_in"] == len(OUTLINE["nodes"])
    assert len(env.mock.message_requests) == n                       # the estimate sent nothing (the mock counts the tokens)
    assert env.ledger.balance_mc("student") > 0


def test_a_faithful_conversion_makes_a_new_timeline_and_leaves_the_original_alone(env):
    tid = _source(env)
    st = _store(env)
    before = (json.dumps(st.get_timeline("student", tid), sort_keys=True, default=str), len(st.list_nodes("student", tid)))
    scn, new = _scenario(env, tid)
    env.mock.use(scn)
    out = _convert(env, tid)
    assert out["ok"] and out["timeline_id"] == "converted" and out["to"] == "timeline" and out["from_timeline"] == tid
    assert out["cards_in"] == out["cards_out"] == len(OUTLINE["nodes"]) and out["grounding"] == []
    assert len(st.list_nodes("student", "converted")) == len(new) and st.get_timeline("student", "converted")
    after = (json.dumps(st.get_timeline("student", tid), sort_keys=True, default=str), len(st.list_nodes("student", tid)))
    assert after == before                                           # the original is never changed
    assert out["credits"]["spent"] > 0


def test_an_invented_card_removes_the_draft_refunds_and_says_nothing_was_saved(env):
    tid = _source(env)
    st = _store(env)
    scn, new = _scenario(env, tid)
    new2 = copy.deepcopy(new)
    new2[0]["desc"] += " Also, the doctrine of quantum meruit applies to every such bargain."
    scn, _ = _scenario(env, tid, nodes=[{**n, "id": n["id"][2:]} for n in new2])
    env.mock.use(scn)
    bal = env.ledger.balance_mc("student")
    out = _convert(env, tid)
    assert out["ok"] is False and out["code"] == "conversion_failed" and out["timeline_id"] is None
    assert out["work_saved"] is False and "nothing was saved" in out["message"] and out["grounding"]
    assert st.get_timeline("student", "converted") is None           # the draft this action made is gone
    assert st.get_timeline("student", tid) and len(st.list_nodes("student", tid)) == len(OUTLINE["nodes"])
    assert env.ledger.balance_mc("student") == bal                   # nothing charged


def test_a_card_left_out_or_with_no_source_also_fails_the_whole_conversion(env):
    tid = _source(env)
    st = _store(env)
    first = st.list_nodes("student", tid)[0]["id"]
    for kw in ({"drop_report": first}, {"report": "none"}):
        scn, _ = _scenario(env, tid, **kw)
        env.mock.use(scn)
        out = _convert(env, tid)
        assert out["ok"] is False and out["code"] == "conversion_failed", kw
        assert st.get_timeline("student", "converted") is None
        st.delete_timeline("student", "converted") if st.get_timeline("student", "converted") else None


def test_the_entitlement_check_runs_first_with_zero_requests_and_zero_credits(env, monkeypatch):
    tid = _source(env)
    monkeypatch.setenv("ALTO_PAYWALL", "1")
    monkeypatch.setattr(ENT, "FORMAT_MIN_PLAN", {**ENT.FORMAT_MIN_PLAN, "timeline": "plus"})
    ENT.set_plan_lookup(lambda uid: "free")
    n, bal = len(env.mock.message_requests), env.ledger.balance_mc("student")
    out = _convert(env, tid)
    assert out["ok"] is False and out["code"] == "needs_plan" and out["plan"] == "plus" and "Plus" in out["message"]
    assert len(env.mock.message_requests) == n and env.ledger.balance_mc("student") == bal
    ENT.set_plan_lookup(lambda uid: "plus")
    assert _convert(env, tid, accepted=False)["status"] == "estimate"      # the right plan: it goes on


def test_it_refuses_what_it_cannot_or_must_not_do(env):
    tid = _source(env)
    assert _convert(env, tid, target="palace")["code"] == "bad_input"         # the palaces need map data: Claude makes those
    assert _convert(env, tid, target="outline")["code"] == "bad_input"        # the file already is an outline
    assert _convert(env, tid, consent=False)["code"] == "consent_required"
    assert _convert(env, "no-such-id")["code"] == "bad_input"
    assert env.acts.dispatch("student", {"action": "convert", "args": {"target": "timeline"}})["code"] == "bad_input"
    assert set(C.BASS_TARGETS) == {"timeline", "outline", "system", "lanes"} and set(C.BASS_TARGETS) <= set(ENT.FORMATS)


# ── the beta guard ─────────────────────────────────────────────────────────

def test_the_beta_guard_refuses_a_format_not_in_the_plan_before_any_hold_or_request(tmp_path, monkeypatch):
    from bass_beta_support import make_stack, req
    s = make_stack(tmp_path)
    monkeypatch.setenv("ALTO_PAYWALL", "1")
    monkeypatch.setattr(ENT, "FORMAT_MIN_PLAN", {**ENT.FORMAT_MIN_PLAN, "system": "pro"})
    ENT.set_plan_lookup(lambda uid: "plus")
    n = len(s.mock.message_requests)
    out = s.svc.handle(req({"action": "convert", "args": {"timeline_id": "t1", "target": "system", "consent": True, "accepted": True}}))
    assert out["code"] == "needs_plan" and out["status"] == "refused" and out["retryable"] is False and "Pro" in out["message"]
    assert len(s.mock.message_requests) == n and s.ledger.held_mc("u_tester1") == 0
    # a format that is open goes on to the action (here: no such timeline, so a plain bad_input, not a refusal)
    out = s.svc.handle(req({"action": "convert", "args": {"timeline_id": "t1", "target": "outline", "consent": True, "accepted": True}}))
    assert out["code"] == "bad_input"
