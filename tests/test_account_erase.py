"""Account erasure (alto/store/erase.py) against an in-memory Firestore: the account's
pictures (pics, picbig) and the picture copies of its shares go with the rest; another
account's data, and shares it does not own, stay. No network, no real account."""
import re
from pathlib import Path

import pytest

from alto.store import erase

ROOT = Path(__file__).resolve().parent.parent


class _Snap:
    def __init__(self, ref, data, exists=True):
        self.reference, self._d, self.exists = ref, data, exists

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

    def get(self):
        d = self.db.docs.get(self.path)
        return _Snap(self, d if d is not None else {}, exists=d is not None)

    def update(self, data):
        assert self.path in self.db.docs
        self.db.docs[self.path].update(data)

    def stream(self):                                   # a collection: its direct documents
        n = len(self.path) + 1
        return [_Snap(_Ref(self.db, p), d) for p, d in list(self.db.docs.items()) if len(p) == n and p[:n - 1] == self.path]


class _Query:
    def __init__(self, db, test):
        self.db, self.test = db, test

    def where(self, field, op, value):
        t = self.test
        return _Query(self.db, lambda p, d: t(p, d) and d.get(field) == value)

    def stream(self):
        return [_Snap(_Ref(self.db, p), d) for p, d in list(self.db.docs.items()) if self.test(p, d)]


class _Blob:
    def __init__(self, db, name):
        self.db, self.name = db, name

    def delete(self):
        self.db.blobs.discard(self.name)


class FakeDB:
    def __init__(self):
        self.docs = {}
        self.blobs = set()

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

    def list_blobs(self, prefix):                       # (the Storage bucket: this fake is both)
        return [_Blob(self, n) for n in sorted(self.blobs) if n.startswith(prefix)]

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
    for uid in ("alice", "bob"):                       # what the account owns outside users/{uid}
        d.put(f"bass_credits/{uid}", {"entries": []})
        d.put(f"bass_docs/{uid}", {"files": {"f1": {"name": "x"}, "f2": {"deleted": "2026-11-01"}}})
        d.put(f"bass_doc_text/{uid}_f1", {"t": "x"})
        d.put(f"bass_doc_text/{uid}_f2", {"t": "x"})
        d.put(f"bass_beta_meta/{uid}_2026-11-01", {"n": 1})
        d.put(f"bass_beta_meta/{uid}_2026-11-02", {"n": 1})
        d.put(f"bass_research_consent/{uid}", {"v": 1})
        d.put(f"terms_acceptance/{uid}_v1", {"uid": uid, "version": "v1"})
        d.put(f"terms_acceptance/{uid}_v2", {"uid": uid, "version": "v2"})
        d.blobs |= {f"builds/{uid}/t1/page.html", f"builds/{uid}/t2/page.html", f"users/{uid}/bass/f1"}
    d.put("bass_beta/allowlist", {"emails": ["alice@example.com", "bob@example.com"]})
    return d


def test_erases_the_accounts_pictures_and_every_other_collection(db):
    out = erase.erase_user(db, "alice", email="Alice@Example.com", bucket=db)
    assert out == {"shares": 2, "hosted": 1, "terms": 2, "bass": 7, "allowlist": 1, "files": 3}
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
    assert erase.erase_user(db, "alice") == {"shares": 0, "hosted": 0, "terms": 0, "bass": 0, "allowlist": 0, "files": 0}
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


def test_everything_the_account_owns_outside_users_goes_and_another_account_keeps_its_own(db):
    erase.erase_user(db, "alice", email="alice@example.com", bucket=db)
    for prefix in ("bass_credits/alice", "bass_docs/alice", "bass_doc_text/alice_f1", "bass_doc_text/alice_f2",
                   "bass_beta_meta/alice_2026-11-01", "bass_beta_meta/alice_2026-11-02", "bass_research_consent/alice",
                   "terms_acceptance/alice_v1", "terms_acceptance/alice_v2"):
        assert not db.has(prefix), prefix
    assert not [b for b in db.blobs if "alice" in b]
    assert db.docs[("bass_beta", "allowlist")]["emails"] == ["bob@example.com"]
    for prefix in ("bass_credits/bob", "bass_docs/bob", "bass_doc_text/bob_f1", "bass_beta_meta/bob_2026-11-01",
                   "bass_research_consent/bob", "terms_acceptance/bob_v1"):
        assert db.has(prefix), prefix
    assert {b for b in db.blobs} == {f"builds/bob/t1/page.html", "builds/bob/t2/page.html", "users/bob/bass/f1"}


def test_a_uid_that_starts_another_uid_does_not_take_its_records(db):
    db.put("bass_beta_meta/alice_2_2026-11-01", {"n": 1})          # belongs to the account "alice_2"
    db.put("bass_doc_text/alice_2_f1", {"t": "x"})
    db.blobs.add("builds/alice_2/t/p.html")
    erase.erase_user(db, "alice", bucket=db)
    assert db.has("bass_beta_meta/alice_2_2026-11-01") and db.has("bass_doc_text/alice_2_f1") and "builds/alice_2/t/p.html" in db.blobs


def test_without_an_email_or_a_bucket_those_two_parts_are_left_and_a_bad_email_is_refused(db):
    out = erase.erase_user(db, "alice")
    assert out["allowlist"] == 0 and out["files"] == 0
    assert db.docs[("bass_beta", "allowlist")]["emails"] == ["alice@example.com", "bob@example.com"]
    assert any("alice" in b for b in db.blobs)
    with pytest.raises(ValueError):
        erase.erase_user(db, "alice", email="not-an-email")


def test_every_top_level_collection_in_the_rules_is_classified_and_the_storage_paths_are_covered():
    rules = (ROOT / "firestore.rules").read_text(encoding="utf-8")
    top = set(re.findall(r"^    match /(\w+)/\{\w+(?:=\*\*)?\} \{", rules, re.M))
    assert top and top <= set(erase.RULES_TOP_LEVEL), top - set(erase.RULES_TOP_LEVEL)
    for coll in ("terms_acceptance", "bass_beta"):
        assert coll in top
    storage = (ROOT / "storage.rules").read_text(encoding="utf-8")
    for path in re.findall(r"match /(users/\{uid\}/\w+)/\{\w+\}", storage):
        assert any(path.startswith(p.rstrip("/").format(uid="{uid}")) for p in erase.STORAGE_PREFIXES), path
    assert "builds/{uid}/" in erase.STORAGE_PREFIXES
    # the server-only collections the Bass proxy keeps per account (deploy/bass-proxy/firestore_store.py key map) are all named here
    assert set(erase.SERVER_BY_UID) >= {"bass_credits", "bass_docs", "bass_research_consent"} and "bass_beta_meta" in erase.SERVER_BY_UID_PREFIX


def test_the_admin_script_is_not_run_by_importing_it_and_dry_runs_by_default(capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("erase_account", ROOT / "tools" / "erase_account.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main(["--project", "p", "--bucket", "b", "--uid", "alice"]) == 0
    assert "DRY RUN" in capsys.readouterr().out
    assert mod.main(["--project", "p", "--bucket", "b", "--uid", "../x"]) == 2
