"""STAMP-hosted2 row 1 (independent author): AdminCloudStore's path pin. SDK-free, fakes only, no network, no key.
Every Firestore reference the admin store ever asks the client for is recorded; none may name anything outside users/<pinned uid>,
and a second uid's documents must stay byte-identical whatever the input."""
import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hosted_store_fake import DELETE_FIELD, SERVER_TIMESTAMP, FakeAdminDb   # noqa: E402

from alto.store.admin_cloud import AdminCloudStore             # noqa: E402
from alto.store.local import LocalStore                        # noqa: E402

LUKE, OTHER = "LukeUid0000000000000000001", "OtherUid000000000000000002"
ROOT = "projects/proj/databases/(default)/documents"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")


class _Fake:
    project = "proj"

    def __init__(self):
        self.docs = {}


class RecDb(FakeAdminDb):
    """FakeAdminDb that records every path handed to document()/collection() and every batch op."""

    def __init__(self, fake):
        super().__init__(fake)
        self.touched = []

    def document(self, rel):
        self.touched.append(("doc", rel))
        return super().document(rel)

    def collection(self, rel):
        self.touched.append(("coll", rel))
        return super().collection(rel)


def _other_docs():
    d = {}
    for rel in ("alto_projects/p1", "alto_timelines/t1", "alto_timelines/t1/nodes/a", "alto_timelines/t1/meta/connections",
                "pages/k1", "pagemeta/k1", "alto_snapshots/k1"):
        d[f"{ROOT}/users/{OTHER}/{rel}"] = {"data": {"stringValue": json.dumps({"owner": "other", "rel": rel})}}
    d[f"{ROOT}/users/{OTHER}"] = {"pagemetaV": {"integerValue": "1"}}
    d[f"{ROOT}/shares/abcdefghijkmnpqrstuvwx"] = {"html": {"stringValue": "share"}}
    return d


@pytest.fixture
def rig(tmp_path):
    fake = _Fake()
    fake.docs.update(_other_docs())
    db = RecDb(fake)
    st = AdminCloudStore(db, LUKE, LocalStore(tmp_path / "scratch"), "proj", delete_field=DELETE_FIELD, server_timestamp=SERVER_TIMESTAMP)
    return fake, db, st


def _mine(rel):
    return rel == f"users/{LUKE}" or rel.startswith(f"users/{LUKE}/")


def _assert_pinned(fake, db, before_other):
    assert all(_mine(r) for _, r in db.touched), [r for _, r in db.touched if not _mine(r)]
    assert {k: v for k, v in fake.docs.items() if f"/users/{LUKE}" not in k + "/"} == before_other


BAD_UIDS = [OTHER, LUKE + "x", LUKE[:-1], "", ".", "..", "../" + OTHER, LUKE + "/../" + OTHER, LUKE + "%2F..%2F" + OTHER,
            OTHER + "/x", " " + LUKE, LUKE + "\n", None, "users", "*", "{uid}", "x" * 200]
BAD_IDS = ["", ".", "..", "../x", "a/b", "a%2Fb", "%2e%2e", "..%2F..%2Fusers%2F" + OTHER, "/", "\\x", "a b", "a\x00b",
           "users/" + OTHER, "x" * 200, ".hidden", None]


def _calls(uid, i):
    page = "<!doctype html><html><head></head><body>x</body></html>"
    meta = {"tid": "t", "title": "t", "units": [], "search": [], "v": 1}
    return [lambda: st_.put_project(uid, i, {"project_id": i, "name": "n"}),
            lambda: st_.get_project(uid, i), lambda: st_.list_projects(uid), lambda: st_.list_timelines(uid),
            lambda: st_.put_timeline(uid, i, {"timeline_id": i}), lambda: st_.get_timeline(uid, i),
            lambda: st_.put_nodes(uid, i, [{"id": "a", "t": "x"}]), lambda: st_.list_nodes(uid, i),
            lambda: st_.delete_nodes(uid, i, ["a"]), lambda: st_.put_connections(uid, i, [["a", "b", "x"]]),
            lambda: st_.get_connections(uid, i), lambda: st_.put_page(uid, i, page, "t", meta), lambda: st_.get_page(uid, i),
            lambda: st_.list_pages(uid), lambda: st_.delete_page(uid, i), lambda: st_.delete_timeline(uid, i),
            lambda: st_.delete_project(uid, i), lambda: st_.put_snapshot(uid, i, {"x": 1}), lambda: st_.get_snapshot(uid, i),
            lambda: st_.put_edits(uid, i, {"x": 1}), lambda: st_.get_edits(uid, i)]


st_ = None


@pytest.mark.parametrize("uid", BAD_UIDS, ids=repr)
def test_no_other_uid_reaches_any_store_method(rig, uid):
    global st_
    fake, db, st_ = rig
    before = {k: copy.deepcopy(v) for k, v in fake.docs.items()}
    for call in _calls(uid, "t1"):
        with pytest.raises(Exception):
            call()
    assert db.touched == [] and fake.docs == before          # refused before ANY client call: no read, no write


@pytest.mark.parametrize("i", BAD_IDS, ids=repr)
def test_odd_ids_for_the_pinned_uid_are_refused_or_stay_inside_it(rig, i):
    global st_
    fake, db, st_ = rig
    other = {k: copy.deepcopy(v) for k, v in fake.docs.items()}
    for call in _calls(LUKE, i):
        try:
            call()
        except Exception:
            pass
    _assert_pinned(fake, db, other)


@pytest.mark.parametrize("name", [
    f"{ROOT}/users/{OTHER}/alto_projects/p1", f"{ROOT}/users/{OTHER}", f"{ROOT}/users/{LUKE}x/alto_projects/p1",
    f"{ROOT}/users", f"{ROOT}/users/", f"{ROOT}", f"{ROOT}/", f"{ROOT}/shares/abcdefghijkmnpqrstuvwx",
    f"{ROOT}/shares/abcdefghijkmnpqrstuvwx/private/owner", f"{ROOT}/bass_beta/hosted", f"{ROOT}/bass_beta/live_go",
    f"{ROOT}:runQuery", f"{ROOT}:batchGet", f"{ROOT}:listCollectionIds", f"{ROOT}/users/{LUKE}:runQuery",
    f"{ROOT}/users/{LUKE}:listCollectionIds", f"{ROOT}/users/{OTHER}/pages:runQuery",
    f"projects/other/databases/(default)/documents/users/{LUKE}/pages/k", f"projects/proj/databases/x/documents/users/{LUKE}/pages/k",
    f"/{ROOT}/users/{LUKE}/pages/k", f"{ROOT}//users/{LUKE}/pages/k", f"{ROOT}/./users/{LUKE}/pages/k",
    f"{ROOT}/../documents/users/{OTHER}/pages/k1", f"users/{LUKE}/pages/k", f"{ROOT}/USERS/{LUKE}/pages/k",
])
@pytest.mark.parametrize("method", ["GET", "PATCH", "POST", "DELETE"])
def test_raw_requests_outside_the_pinned_account_are_refused_before_the_client(rig, name, method):
    fake, db, st = rig
    before = copy.deepcopy(fake.docs)
    with pytest.raises(Exception):
        st._req(method, name, {"fields": {"data": {"stringValue": "x"}}})
    assert db.touched == [] and fake.docs == before


@pytest.mark.parametrize("bad", [
    {"delete": f"{ROOT}/users/{OTHER}/alto_projects/p1"},
    {"delete": f"{ROOT}/shares/abcdefghijkmnpqrstuvwx"},
    {"update": {"name": f"{ROOT}/users/{OTHER}/pages/k1", "fields": {}}},
    {"update": {"name": f"{ROOT}/users/{OTHER}", "fields": {}}, "updateMask": {"fieldPaths": ["pagemetaV"]}},
    {"update": {"name": f"{ROOT}/shares/abcdefghijkmnpqrstuvwx/private/owner", "fields": {}}, "currentDocument": {"exists": False}},
    {"update": {"name": f"{ROOT}/users/{LUKE}/pages/k", "fields": {}}, "updateMask": {"fieldPaths": ["z"]},
     "updateTransforms": [{"fieldPath": "z", "appendMissingElements": {"values": []}}]},
    {"transform": {"document": f"{ROOT}/users/{OTHER}/pages/k1"}},
    {"verify": f"{ROOT}/users/{OTHER}/pages/k1"},
])
def test_a_commit_with_one_bad_write_writes_nothing_at_all(rig, bad):
    """A good write for the pinned uid first, then one outside it (or unsupported): the whole commit is refused, nothing lands."""
    fake, db, st = rig
    before = copy.deepcopy(fake.docs)
    good = {"update": {"name": f"{ROOT}/users/{LUKE}/alto_projects/p9", "fields": {"data": {"stringValue": "{}"}}}}
    with pytest.raises(Exception):
        st._req("POST", f"{ROOT}:commit", {"writes": [good, bad]})
    assert fake.docs == before
    assert all(_mine(r) for _, r in db.touched)


def test_dot_dot_inside_the_prefix_is_refused_by_the_per_segment_id_check(rig):
    """N1 (stamp follow-up): _rel was a prefix check, so users/<pinned>/../<other>/... passed it. Now every segment must be an id
    (non-empty, no '/', never '.' or '..'), so it is refused before Firestore is touched."""
    from alto.cloud.session import CloudError
    fake, db, st = rig
    before = copy.deepcopy(fake.docs)
    for bad in (f"users/{LUKE}/../{OTHER}/alto_projects/p1", f"users/{LUKE}/./alto_projects/p1", f"users/{LUKE}//alto_projects/p1"):
        with pytest.raises(CloudError):
            st._req("PATCH", f"{ROOT}/{bad}", {"fields": {"data": {"stringValue": "{}"}}})
    assert db.touched == [] and fake.docs == before


def test_a_second_uid_never_causes_a_read_or_a_write_even_mixed_with_the_pinned_one(rig):
    global st_
    fake, db, st_ = rig
    before = copy.deepcopy(fake.docs)
    st_.put_project(LUKE, "p1", {"project_id": "p1", "name": "mine"})
    n = len(db.touched)
    for call in _calls(OTHER, "p1") + _calls(OTHER, "t1"):
        with pytest.raises(Exception):
            call()
    assert len(db.touched) == n
    assert {k: v for k, v in fake.docs.items() if OTHER in k} == {k: v for k, v in before.items() if OTHER in k}
