"""The hosted server's share index (alto/store/firestore.py), on a stand-in
for the Admin SDK: one account's publish never replaces or reveals another's,
and nothing of it lands in the publicly gettable `shares` collection."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from alto.store.firestore import FirestoreStore   # noqa: E402


class _Snap:
    def __init__(self, d):
        self.exists, self._d = d is not None, d

    def to_dict(self):
        return dict(self._d) if self._d is not None else None


class _Ref:
    def __init__(self, db, path):
        self.db, self.path = db, path

    def get(self):
        return _Snap(self.db.docs.get(self.path))

    def set(self, d):
        self.db.docs[self.path] = dict(d)

    def delete(self):
        self.db.docs.pop(self.path, None)


class _Coll:
    def __init__(self, db, name):
        self.db, self.name = db, name

    def document(self, i):
        return _Ref(self.db, f"{self.name}/{i}")


class _DB:
    def __init__(self):
        self.docs = {}

    def collection(self, name):
        return _Coll(self, name)


@pytest.fixture
def st():
    s = FirestoreStore.__new__(FirestoreStore)
    s.db = _DB()
    return s


def test_two_accounts_with_the_same_timeline_id_do_not_collide(st):
    st.put_share("contracts", {"uid": "alice", "visibility": "private-web"})
    st.put_share("contracts", {"uid": "bob", "visibility": "private"})
    assert st.get_share("contracts", "alice") == {"uid": "alice", "visibility": "private-web"}
    assert st.get_share("contracts", "bob") == {"uid": "bob", "visibility": "private"}


def test_another_account_neither_sees_nor_deletes_it(st):
    st.put_share("contracts", {"uid": "alice", "visibility": "private-web"})
    assert st.get_share("contracts", "mallory") is None
    assert st.get_share("contracts") is None
    st.delete_share("contracts", "mallory")
    st.delete_share("contracts")
    assert st.get_share("contracts", "alice")


def test_nothing_is_written_to_the_public_shares_collection(st):
    st.put_share("contracts", {"uid": "alice", "visibility": "private-web"})
    assert all(not p.startswith("shares/") for p in st.db.docs)
    assert list(st.db.docs) == ["hosted_shares/alice_contracts"]


def test_an_owner_is_required(st):
    with pytest.raises(ValueError):
        st.put_share("contracts", {"visibility": "private"})
    with pytest.raises(ValueError):
        st.put_share("contracts", {"uid": "a/b", "visibility": "private"})
