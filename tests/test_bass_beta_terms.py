"""The Beta Terms gate (IT, privacy-inventory sec 5; bench-tl-1 T1): Bass refuses a uid with no acceptance of the CURRENT terms version.
The record is Firestore terms_acceptance/<uid>_<version>, read with one get through the store interface, fail closed. Refusal = reason code
terms_required, zero upstream requests, no hold, no grant. Mock only, no network, no key."""
import json
import sys
from dataclasses import replace

import pytest

from bass_support import ROOT  # noqa: F401
from bass_beta_support import EMAIL, FakeClock, MATERIALS, build_req, edit_req, make_stack, req
from test_bass_beta_proxy import FakeSecrets, FakeVerifier, ORIGIN, post
from alto.bass import beta_config as BC, mock_anthropic as M
from alto.bass.beta_config import BetaConfig, current_terms_version
from alto.bass.beta_guard import FREE
from alto.bass.beta_ledger import confirm_key
from alto.bass.beta_proxy import Proxy
from alto.bass.beta_store import FakeStore
from alto.bass.errors import POLICIES
from alto.bass.tools import ToolBox
from alto.store.local import LocalStore

MSG = "Please accept the Beta Terms to use Bass. Sign in again to see the box."
UID = "u_" + EMAIL.split("@")[0]
KEY = f"terms_acceptance/{UID}_1.1"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")


@pytest.fixture
def st(tmp_path):
    s = make_stack(tmp_path, store=FakeStore())                          # a plain store: no terms record for anyone
    assert s.cfg.terms_version == "1.1"                                  # the version main ships in alto/legal/VERSION (review finding D1)
    return s


def refused(out):
    return (out["ok"] is False and out["code"] == "terms_required" and out["status"] == "paused" and out["message"] == MSG
            and out["retryable"] is False and out["action_id"] is None)


def test_not_accepted_every_action_but_stop_is_refused_with_no_upstream_request_and_no_hold(st):
    before = dict(st.store.docs)
    for body in (build_req(), {"action": "propose", "args": {"materials": MATERIALS}}, edit_req(),
                 {"action": "estimate", "args": {"kind": "build", "materials": MATERIALS}},
                 {"action": "grade", "args": {"essay": "x"}}, {"action": "anything-new", "args": {}}):
        out = st.svc.handle(req(body))
        assert refused(out), body["action"]
    assert st.mock.requests == []
    assert st.store.docs == before                                       # no hold, no grant, no counter touched
    assert POLICIES["terms_required"].user_message == MSG
    assert "stop" in FREE and "balance" in FREE


def test_the_gate_comes_after_the_allowlist_and_before_everything_else(st):
    out = st.svc.handle(req(build_req(), email="stranger@example.com"))
    assert out["code"] == "bass_off"                                     # not on the list: still bass_off
    st.kill.trip("test")
    out = st.svc.handle(req(build_req()))
    assert refused(out)                                                  # kill switch is behind the terms gate


def test_accepted_current_version_runs_and_extra_keys_are_ignored(st):
    st.store.accept_terms(UID, "1.1", somethingElse={"a": 1}, acceptedAt="whenever")
    st.mock.use(M.build("Contracts", {"title": "Contracts"}, [], []))
    out = st.svc.handle(req(build_req()))
    assert out["code"] != "terms_required" and out["ok"] is True and st.mock.message_requests


def test_an_old_version_does_not_count(st):
    st.store.accept_terms(UID, "0.0")
    assert refused(st.svc.handle(req(build_req()))) and st.mock.requests == []


def test_bumping_the_version_regates_everyone(st):
    st.store.accept_terms(UID, "1.1")
    assert st.svc.handle(req({"action": "balance", "args": {}}))["ok"] is True
    st.svc.terms.cfg = replace(st.cfg, terms_version="0.2")              # a new Terms version = a new document name
    assert refused(st.svc.handle(req(build_req())))
    out = st.svc.handle(req({"action": "balance", "args": {}}))
    assert refused(out) and out["available"] is False
    st.store.accept_terms(UID, "0.2")                                    # they sign in, tick the box, and are through again
    assert st.svc.handle(req({"action": "balance", "args": {}}))["ok"] is True


def test_the_version_comes_from_alto_legal_VERSION_when_it_exists_else_0_1(tmp_path, monkeypatch):
    fake = tmp_path / "alto" / "bass" / "beta_config.py"
    fake.parent.mkdir(parents=True)
    monkeypatch.setattr(BC, "__file__", str(fake))
    assert current_terms_version() == "0.1" and BetaConfig(testers=1).terms_version == "0.1"       # no file
    (tmp_path / "alto" / "legal").mkdir()
    (tmp_path / "alto" / "legal" / "VERSION").write_text("0.7\n", "utf-8")
    assert current_terms_version() == "0.7" and BetaConfig(testers=1).terms_version == "0.7"
    (tmp_path / "alto" / "legal" / "VERSION").write_text("\n", "utf-8")
    assert current_terms_version() == "0.1"                                                         # empty file = the fallback
    (tmp_path / "alto" / "legal" / "VERSION").write_text("../x/y", "utf-8")
    assert BetaConfig(testers=1).problems()                                                         # not a plain token: stops the deploy


def test_a_bad_version_token_refuses_everyone_fail_closed(st):
    st.store.accept_terms(UID, "../x")
    st.svc.terms.cfg = replace(st.cfg, terms_version="../x")
    assert refused(st.svc.handle(req(build_req())))


def test_bs_acceptance_does_not_cover_a(st):
    st.store.accept_terms("u_b", "1.1")
    assert refused(st.svc.handle(req(build_req())))                      # A (the default uid) has none
    assert st.mock.requests == []


def test_a_doc_that_names_another_uid_does_not_count(st):
    st.store.put(KEY, {"uid": "u_b", "version": "1.1", "ageConfirmed": True})
    assert refused(st.svc.handle(req(build_req())))


def test_a_doc_with_another_version_inside_does_not_count(st):
    st.store.put(KEY, {"uid": UID, "version": "0.0", "ageConfirmed": True})
    assert refused(st.svc.handle(req(build_req())))


@pytest.mark.parametrize("doc", [{"uid": UID, "version": "1.1", "ageConfirmed": False},
                                 {"uid": UID, "version": "1.1", "ageConfirmed": "true"},
                                 {"uid": UID, "version": "1.1", "ageConfirmed": 1},
                                 {"uid": UID, "version": "1.1"}, {"ageConfirmed": True}, {},
                                 {"uid": UID, "version": "1.1", "ageConfirmed": True},                        # no acceptedAt
                                 {"uid": UID, "version": "1.1", "ageConfirmed": True, "acceptedAt": None},
                                 {"uid": UID, "version": "1.1", "acceptedAt": "2026-10-30T12:00:00Z"},        # no ageConfirmed
                                 {"uid": "u_other", "version": "1.1", "ageConfirmed": True, "acceptedAt": "2026-10-30T12:00:00Z"},   # right id, wrong uid field
                                 {"uid": UID, "version": 1.1, "ageConfirmed": True}])
def test_age_not_confirmed_or_a_malformed_doc_is_refused(st, doc):
    st.store.put(KEY, doc)
    assert refused(st.svc.handle(req(build_req()))) and st.mock.requests == []


def test_an_unreadable_or_down_store_refuses(st):
    st.store.accept_terms(UID, "1.1")
    st.store.make_unreadable(KEY)
    assert refused(st.svc.handle(req(build_req())))
    st.store.make_unreadable(KEY, False)
    assert st.svc.handle(req({"action": "balance", "args": {}}))["ok"] is True
    st.store.go_down()
    assert st.svc.terms.accepted(UID) is False                           # the gate itself, store down
    assert st.svc.handle(req(build_req()))["ok"] is False                # (the allowlist read fails first and refuses too)
    assert st.mock.requests == []


def test_a_non_dict_doc_or_a_slash_in_the_uid_is_refused(st):
    st.store.put(KEY, ["uid"])
    assert refused(st.svc.handle(req(build_req())))
    st.store.accept_terms("u/evil", "1.1")
    assert refused(st.svc.handle(req(build_req(), uid="u/evil")))


def test_balance_answers_unavailable_with_the_terms_message_and_creates_nothing(st):
    out = st.svc.handle(req({"action": "balance", "args": {}}))
    assert refused(out) and out["available"] is False and out["beta"] is True and out["credits"] is None
    assert st.store.docs.get(UID) is None and st.mock.requests == []


def test_stop_stays_free_and_is_not_gated(st):
    out = st.svc.handle(req({"action": "stop", "args": {"action_id": "act_nope"}}))
    assert out.get("code") != "terms_required" and st.mock.requests == []


def test_acceptance_is_read_with_one_get_through_the_store(st):
    seen = []
    real = st.store.get
    st.store.get = lambda k: (seen.append(k), real(k))[1]
    st.svc.handle(req(build_req()))
    assert [k for k in seen if k.startswith("terms_acceptance/")] == [KEY]


def test_firestore_document_map_has_the_terms_collection():
    sys.path.insert(0, str(ROOT / "deploy" / "bass-proxy"))
    import firestore_store as FS
    assert FS._path("terms_acceptance/u_x_1.1") == ("terms_acceptance", "u_x_1.1")
    assert FS._path("u_x") == ("bass_credits", "u_x")


def test_through_the_http_handler_a_signed_in_tester_without_acceptance_is_told_to_accept(tmp_path):
    store, clock = FakeStore(), FakeClock()
    cfg = BetaConfig(testers=10, allowlist=frozenset({EMAIL}))
    store.put(confirm_key(cfg.period_id(clock())), {"confirmed": True})
    p = Proxy(cfg, store, FakeVerifier(), FakeSecrets(), ToolBox(LocalStore(tmp_path / "store")), clock=clock, origins=[ORIGIN])
    p.store = store
    for body in (build_req(), {"action": "balance", "args": {}}):
        _, _, out = post(p, body)
        assert out["code"] == "terms_required" and out["message"] == MSG and "Traceback" not in json.dumps(out)
    assert p.mock.requests == []
    store.accept_terms("u1", cfg.terms_version)                          # the FakeVerifier's uid for tok-ok
    _, _, out = post(p, {"action": "balance", "args": {}})
    assert out["ok"] is True


def test_the_account_limiter_counts_before_the_terms_read_so_a_not_accepted_uid_cannot_hammer_the_store(st):
    limit = st.cfg.account_per_min
    seen = []
    real = st.store.get
    st.store.get = lambda k: (seen.append(k), real(k))[1]
    outs = [st.svc.handle(req({"action": "balance", "args": {}}, xff=f"203.0.113.{i % 5 + 1}")) for i in range(limit + 8)]
    assert [o["code"] for o in outs[:limit]] == ["terms_required"] * limit
    assert all(o["code"] == "busy" and o["status"] == "busy" for o in outs[limit:])
    assert len([k for k in seen if k.startswith("terms_acceptance/")]) == limit            # the store saw at most that many gets
    assert st.mock.requests == []
