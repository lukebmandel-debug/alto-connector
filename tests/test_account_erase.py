"""Account erasure (alto/store/erase.py) against an in-memory Firestore: the account's
pictures (pics, picbig) and the picture copies of its shares go with the rest; another
account's data, and shares it does not own, stay. No network, no real account."""
import re
from pathlib import Path

import pytest

from alto.store import erase

ROOT = Path(__file__).resolve().parent.parent


class _Snap:
    def __init__(self, ref, data):
        self.reference, self._d = ref, data

    def to_dict(self):
        return dict(self._d)


class _Ref:
    def __init__(self, db, path):
        self.db, self.path = db, tuple(path)

    @property
    def id(self):
        return self.path[-1]

    @property
    def parent(self):
        return _Ref(self.db, self.path[:-1]) if len(self.path) > 1 else None

    def collection(self, name):
        return _Ref(self.db, self.path + (name,))

    document = collection

    def where(self, field, op, value):
        assert op == "=="
        return _Query(self.db, lambda p, d: len(p) == len(self.path) + 1 and p[:len(self.path)] == self.path
                      and d.get(field) == value)

    def delete(self):
        self.db.docs.pop(self.path, None)


class _Query:
    def __init__(self, db, test):
        self.db, self.test = db, test

    def where(self, field, op, value):
        t = self.test
        return _Query(self.db, lambda p, d: t(p, d) and d.get(field) == value)

    def stream(self):
        return [_Snap(_Ref(self.db, p), d) for p, d in list(self.db.docs.items()) if self.test(p, d)]


class FakeDB:
    def __init__(self):
        self.docs = {}

    def put(self, path, data=None):
        self.docs[tuple(path.split("/"))] = data or {"x": 1}

    def collection(self, name):
        return _Ref(self, (name,))

    def collection_group(self, name):
        db = self
        q = _Query(db, lambda p, d: len(p) >= 2 and p[-2] == name)
        return q

    def recursive_delete(self, ref):
        for p in [p for p in self.docs if p[:len(ref.path)] == ref.path]:
            del self.docs[p]

    def has(self, prefix):
        t = tuple(prefix.split("/"))
        return any(p[:len(t)] == t for p in self.docs)


@pytest.fixture
def db():
    d = FakeDB()
    for uid in ("alice", "bob"):
        for coll in erase.USER_COLLECTIONS:
            d.put(f"users/{uid}/{coll}/c1")
        d.put(f"users/{uid}")
        d.put(f"users/{uid}/tl/t1/reports/r1")
    # alice owns share A (owner record) and B (legacy: owner on the share doc); bob owns C
    for key, uid, legacy in (("A" * 22, "alice", False), ("B" * 22, "alice", True), ("C" * 22, "bob", False)):
        d.put(f"shares/{key}", {"title": "t", **({"owner": uid} if legacy else {})})
        if not legacy:
            d.put(f"shares/{key}/private/owner", {"owner": uid})
        d.put(f"shares/{key}/pics/pic-aaaaaaaaaa", {"d": b"x"})
        d.put(f"shares/{key}/picbig/pic-aaaaaaaaaa", {"d": b"x"})
    d.put("hosted_shares/alice_t1", {"uid": "alice"})
    d.put("hosted_shares/bob_t1", {"uid": "bob"})
    return d


def test_erases_the_accounts_pictures_and_every_other_collection(db):
    out = erase.erase_user(db, "alice")
    assert out == {"shares": 2, "hosted": 1}
    assert not db.has("users/alice")
    for coll in ("pics", "picbig", "bglib", "bgimg", "tl"):
        assert not any(p[0] == "users" and p[1] == "alice" and p[2] == coll for p in db.docs)


def test_erases_the_picture_copies_of_shares_the_account_owns(db):
    erase.erase_user(db, "alice")
    for key in ("A" * 22, "B" * 22):
        assert not db.has(f"shares/{key}"), key
    assert not db.has("hosted_shares/alice_t1")


def test_leaves_another_account_and_its_shares_alone(db):
    before = {p for p in db.docs if "bob" in p or p[1:2] == ("C" * 22,) or p[:2] == ("hosted_shares", "bob_t1")}
    erase.erase_user(db, "alice")
    assert before and before <= set(db.docs)
    assert db.has("shares/" + "C" * 22 + "/pics/pic-aaaaaaaaaa")
    assert db.has("shares/" + "C" * 22 + "/picbig/pic-aaaaaaaaaa")
    assert db.has("users/bob/pics/c1") and db.has("users/bob/picbig/c1")


def test_a_second_run_is_harmless_and_a_bad_uid_is_refused(db):
    erase.erase_user(db, "alice")
    assert erase.erase_user(db, "alice") == {"shares": 0, "hosted": 0}
    for bad in ("", "a/b", "..", None, "x" * 200):
        with pytest.raises(ValueError):
            erase.erase_user(db, bad)
    assert db.has("users/bob/pics/c1")


def test_the_erase_list_is_the_rules_list():
    rules = (ROOT / "firestore.rules").read_text(encoding="utf-8")
    m = re.search(r"function ownCollection\(coll\) \{\s*return coll in \[(.*?)\];", rules, re.S)
    assert set(re.findall(r"'(\w+)'", m.group(1))) == set(erase.USER_COLLECTIONS)
    assert {"pics", "picbig"} <= set(erase.USER_COLLECTIONS)
    assert set(erase.SHARE_COPY_COLLECTIONS) == {"pics", "picbig"}
