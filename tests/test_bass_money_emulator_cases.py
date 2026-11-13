"""The Firestore-emulator money check (tests/security/bass_money_emulator_check.py, CI only) runs its cases on the real Firestore client.
Here the SAME cases run on FakeStore, locally and with no emulator, so a case that is wrong in itself is caught before CI."""
import importlib.util

import pytest

from bass_support import ROOT
from alto.bass.beta_store import FakeStore

spec = importlib.util.spec_from_file_location("bass_money_emulator_check", ROOT / "tests" / "security" / "bass_money_emulator_check.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)


@pytest.mark.parametrize("fn", C.CASES, ids=[f.__name__ for f in C.CASES])
def test_emulator_money_case_holds_on_the_fake_store(monkeypatch, fn):
    monkeypatch.setattr(C, "new_store", lambda: FakeStore(auto_terms=True))
    fn()


def test_the_emulator_check_refuses_without_a_local_emulator(monkeypatch):
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
    with pytest.raises(SystemExit, match="FIRESTORE_EMULATOR_HOST"):
        C.guard()
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "firestore.googleapis.com:443")
    with pytest.raises(SystemExit, match="not local"):
        C.guard()


def _nested(v, in_array=False):
    if isinstance(v, dict):
        return any(_nested(x) for x in v.values())
    if isinstance(v, list):
        return in_array or any(_nested(x, True) for x in v)
    return False


def test_firestore_adapter_never_writes_an_array_inside_an_array_and_reads_it_back_unchanged(tmp_path):
    """The emulator found it (11 Nov): the period counter's spend_log is [[t, mc], ...], which Firestore refuses, so every real settle
    failed and tripped the kill switch. The adapter (deploy/bass-proxy/firestore_store.py) encodes the inner arrays and decodes them on read."""
    import sys
    sys.path.insert(0, str(ROOT / "deploy" / "bass-proxy"))
    import firestore_store as F
    st = C.make_stack(tmp_path)
    C.spend(st, "u1", 10, "a")
    C.spend(st, "u1", 10, "b")
    docs = [st.store.get(C.pc_key(st.ledger.period())), st.store.get(C.day_key(st.ledger.today())), st.store.get("u1")]
    assert _nested(docs[0]), "the ledger no longer keeps a nested array: this test and the adapter's encoding can be simplified"
    for d in docs:
        enc = F._enc(d)
        assert not _nested(enc), enc
        assert F._dec(enc) == d
    assert F._dec(F._enc({"a": [[1, [2, 3]], {"b": [[4]]}], "c": [], "d": {F.NESTED: "not a list"}})) == \
        {"a": [[1, [2, 3]], {"b": [[4]]}], "c": [], "d": {F.NESTED: "not a list"}}
