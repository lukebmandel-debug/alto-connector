"""Testing seat alto-testing-1111-basslive2: the Firestore adapter's nested-array encoding (alto_array_v1) under every ledger path.
A stricter stand-in than tests/test_bass_live_fixes.py's StrictFirestore: it ALSO refuses what real Firestore refuses on write: an array
directly inside an array, and a field name that starts and ends with "__". Not the emulator. Copy into <worktree>/tests/ and run there."""
import pytest as _pytest_sdk
_pytest_sdk.importorskip("anthropic")   # public CI has no SDK: these skip there (listed in test_bass_sdk_free.py) and run in the SDK env
_pytest_sdk.importorskip("httpx2")
import copy
import json

import pytest

import test_bass_live_fixes as F
from test_bass_live_fixes import strict_fs  # noqa: F401  (fixture)
from bass_beta_support import EMAIL, build_req, edit_req, make_stack, req
from alto.bass import mock_anthropic as M
from alto.bass.beta_ledger import confirm_key, day_key, pc_key

MC = 1000
UID = "u_" + EMAIL.split("@")[0]


def _bad(v, in_array=False, path="$"):
    if isinstance(v, dict):
        for k, x in v.items():
            if isinstance(k, str) and k.startswith("__") and k.endswith("__"):
                return f"{path}.{k}: reserved field name"
            r = _bad(x, False, f"{path}.{k}")
            if r:
                return r
    elif isinstance(v, list):
        if in_array:
            return f"{path}: array in an array"
        for i, x in enumerate(v):
            r = _bad(x, True, f"{path}[{i}]")
            if r:
                return r
    return None


class Refused(Exception):
    pass


@pytest.fixture
def firestore_like(strict_fs, monkeypatch):
    store, db = strict_fs
    o_txn_set, o_ref_set = F._FsTxn.set, F._FsRef.set

    def txn_set(self, ref, doc):
        why = _bad(doc)
        if why:
            raise Refused("Cannot convert an array value in an array value / " + why)
        return o_txn_set(self, ref, doc)

    def ref_set(self, doc):
        why = _bad(doc)
        if why:
            raise Refused(why)
        return o_ref_set(self, doc)
    monkeypatch.setattr(F._FsTxn, "set", txn_set)
    monkeypatch.setattr(F._FsRef, "set", ref_set)
    return store, db


@pytest.fixture(autouse=True)
def _mock_only(monkeypatch, tmp_path):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")
    monkeypatch.delenv("ALTO_LIVE_ANTHROPIC", raising=False)
    monkeypatch.setenv("ALTO_BASS_LIVE_GO", str(tmp_path / "no-go-file"))


def test_every_ledger_path_round_trips_with_no_refused_write_and_the_books_match_the_fake_store(firestore_like, tmp_path):
    store, db = firestore_like
    runs = {}
    for name, s in (("firestore", store), ("fakefake_", None)):
        st = make_stack(tmp_path / name, store=s, tester_daily_credits=600)
        ver = st.cfg.terms_version
        st.store.put(f"terms_acceptance/{UID}_{ver}", {"uid": UID, "version": ver, "ageConfirmed": True, "acceptedAt": "2026-11-11T12:00:00Z"})
        brief = json.loads((F.ROOT / "samples" / "contracts_brief.json").read_text("utf-8"))
        st.mock.use(M.build("Contracts", brief["brief"], brief["nodes"], brief["connections"]))
        assert st.svc.handle(req(build_req()))["ok"] is True                         # hold + settle per turn (spend_log grows)
        st.mock.use(M.Scenario("g", [M.Step(M.say("OFF_TOPIC"))]))
        assert st.svc.handle(req(edit_req()))["status"] == "off_topic"               # absorb
        st.mock.use(None)
        st.mock.inject(M.overloaded(times=99))
        assert st.svc.handle(req(build_req()))["status"] == "error"                  # release
        st.mock.faults.clear()
        st.mock.inject(M.stream_drop(after_events=4))
        assert st.svc.handle(req(build_req()))["status"] == "error"                  # billed failure booked
        st.mock.use(M.Scenario("r", [M.Step(M.refusal())]))
        assert st.svc.handle(req(build_req()))["status"] == "refused"                # refund
        st.ledger.hold(UID, "cut", 5 * MC, "a9", worst_mc=9 * MC)
        st.clock.advance(st.cfg.reservation_ttl_s + 1)
        assert st.ledger.reap() == 1                                                  # reaper
        st.ledger.settle(UID, "cut", 4 * MC)                                          # late settle after the reaper
        p0 = st.ledger.period()
        st.clock.advance(days=20)
        st.store.put(confirm_key(st.ledger.period()), {"confirmed": True})
        st.ledger.hold(UID, "np", 5 * MC, "a10", worst_mc=5 * MC)                     # new-period hold (grants)
        st.ledger.settle(UID, "np", 3 * MC)
        assert st.kill.is_on() is False, "a refused write tripped the kill switch"
        runs[name] = {k: st.store.get(k) for k in (pc_key(p0), pc_key(st.ledger.period()), UID, "bass_beta/kill")}
    fs, fk = runs["firestore"], runs["fakefake_"]
    for k in fs:
        a, b = copy.deepcopy(fs[k]), copy.deepcopy(fk[k])
        for d in (a, b):
            if isinstance(d, dict):
                for e in d.get("entries", []):
                    for f in ("t", "hold", "action"):
                        e.pop(f, None)                                       # random ids and clock stamps
                d.pop("holds", None)
        assert a == b, k
    assert any(isinstance(x, list) and x and isinstance(x[0], list) for x in [fs[pc_key(p0)]["spend_log"]]), "spend_log decodes as [[t, mc], ...]"
    assert db.read_after_write == 0
    stored = db.docs[("bass_beta_period_counters", p0)]
    assert _bad(stored) is None and stored["spend_log"] and all(set(x) == {"alto_array_v1"} for x in stored["spend_log"])


def test_a_raw_nested_array_write_is_what_real_firestore_refuses(firestore_like):
    store, db = firestore_like
    with pytest.raises(Refused):
        db.collection("bass_beta").document("x").set({"a": [[1, 2]]})               # the stand-in really enforces it
    store.put("bass_beta/x", {"a": [[1, 2]], "b": [[[3]]], "c": [{"d": [[4]]}]})       # through the adapter: accepted, round-trips
    assert store.get("bass_beta/x") == {"a": [[1, 2]], "b": [[[3]]], "c": [{"d": [[4]]}]}


def test_the_marker_is_ambiguous_only_for_a_one_key_map_named_alto_array_v1_holding_a_list(firestore_like):
    """Recorded: a stored map {"alto_array_v1": [..]} reads back as a list. No Bass document has a caller-chosen map key (document ids are
    server-made), so this is not reachable from a tester; it pins the edge."""
    store, _ = firestore_like
    store.put("bass_beta/y", {"m": {"alto_array_v1": [1]}})
    assert store.get("bass_beta/y") == {"m": [1]}
