"""Hosted Bass saves where luke-alto reads (alto/store/admin_cloud.py). SDK-free: fakes only, no network, no key.
The hosted function writes with the admin SDK; luke-alto reads with CloudStore. Both run here over ONE fake Firestore table."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cloudfake import FakeFirebase                              # noqa: E402
from hosted_store_fake import DELETE_FIELD, SERVER_TIMESTAMP, FakeAdminDb   # noqa: E402

from alto.cloud.session import CloudError, Session             # noqa: E402
from alto.store.admin_cloud import AdminCloudStore             # noqa: E402
from alto.store.cloud import CloudStore                        # noqa: E402
from alto.store.local import LocalStore                        # noqa: E402

LUKE, OTHER = "LukeUid0000000000000000001", "OtherUid000000000000000002"
CFG = {"apiKey": "k", "projectId": "proj", "appId": "a"}


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")


@pytest.fixture
def rig(tmp_path):
    fake = FakeFirebase(uid=LUKE)
    s = Session(CFG, http=fake, path=tmp_path / "s.json", opener=lambda u: None)
    s._accept("RT")
    user = CloudStore(s, LocalStore(tmp_path / "user"))          # luke-alto's code
    db = FakeAdminDb(fake)
    admin = AdminCloudStore(db, LUKE, LocalStore(tmp_path / "scratch"), "proj", delete_field=DELETE_FIELD, server_timestamp=SERVER_TIMESTAMP)
    return fake, user, admin, db


PROJECT = {"project_id": "p1", "name": "Contracts", "created": "2026-11-15T10:00:00Z", "n": 3}
TIMELINE = {"timeline_id": "t1", "project_id": "p1", "created": "2026-11-15T10:01:00Z", "brief": {"title": "Café – “quotes” é 日本", "x": [[1, 2], [3]]}}
NODES = [{"id": "a", "t": "Offer", "d": "x" * 50, "refs": [["a", "b"]]}, {"id": "b", "t": "Accept", "d": "y"}]
CONNS = [["a", "b", "leads"], ["b", "a", "back"]]
PAGE = ("<!doctype html><html><head><title>Contracts — Alto Timeline</title></head><body>"
        "<div id=\"alto-label\">Contracts</div></body></html>")
META = {"tid": "t1", "title": "Contracts", "heading": "Contracts", "project": "Contracts", "units": ["#fff"],
        "search": [{"id": "a", "t": "Offer", "d": "d"}], "v": 1, "fmt": "timeline", "added": 1700000000}


def write_all(st, uid=LUKE):
    st.put_project(uid, "p1", dict(PROJECT))
    st.put_timeline(uid, "t1", json.loads(json.dumps(TIMELINE)))
    st.put_nodes(uid, "t1", [dict(n) for n in NODES])
    st.put_connections(uid, "t1", [list(c) for c in CONNS])


def read_all(st, uid=LUKE):
    return (st.list_projects(uid), st.list_timelines(uid), st.list_nodes(uid, "t1"), st.get_connections(uid, "t1"))


def test_what_the_hosted_store_writes_cloudstore_reads_back_identically(rig):
    fake, user, admin, _ = rig
    write_all(admin)
    assert read_all(user) == read_all(admin)
    projects, timelines, nodes, conns = read_all(user)
    assert projects == [PROJECT] and timelines == [TIMELINE] and conns == CONNS
    assert [(n["id"], n["_seq"]) for n in nodes] == [("a", 1), ("b", 2)]
    raw = fake.docs[f"projects/proj/databases/(default)/documents/users/{LUKE}/alto_timelines/t1"]
    assert set(raw) == {"data", "created"} and "stringValue" in raw["data"]       # {data: JSON text, created}, as CloudStore writes it


def test_what_cloudstore_writes_the_hosted_store_reads_back_identically(rig):
    _, user, admin, _ = rig
    write_all(user)
    assert read_all(admin) == read_all(user)
    admin.put_nodes(LUKE, "t1", [{"id": "c", "t": "Third"}, {"id": "a", "t": "Offer 2"}])      # an edit keeps narrative order and appends
    user._nodes_cache.clear()                                    # CloudStore reuses nodes for 5 s within a call; a new request starts clean
    assert [(n["id"], n["_seq"]) for n in read_all(user)[2]] == [("a", 1), ("b", 2), ("c", 3)]
    admin.delete_nodes(LUKE, "t1", ["b"])
    user._nodes_cache.clear()
    assert [n["id"] for n in user.list_nodes(LUKE, "t1")] == ["a", "c"]


def test_pages_and_the_homepage_list_agree_both_ways(rig):
    fake, user, admin, _ = rig
    admin.put_page(LUKE, "key1", PAGE, "Contracts", dict(META))
    assert user.get_page(LUKE, "key1") == PAGE == admin.get_page(LUKE, "key1")
    want = [{"key": "key1", "tid": "t1", "title": "Contracts", "project": "Contracts", "heading": "Contracts", "binned": 0}]
    assert user.list_pages(LUKE) == want == admin.list_pages(LUKE)
    meta = fake.docs[f"projects/proj/databases/(default)/documents/users/{LUKE}/pagemeta/key1"]
    assert meta["added"] == {"integerValue": "1700000000"} and "updatedAt" in meta and meta["units"]["arrayValue"]["values"]
    page = fake.docs[f"projects/proj/databases/(default)/documents/users/{LUKE}/pages/key1"]
    assert set(page) >= {"z", "enc", "title", "tid", "updatedAt"} and "bytesValue" in page["z"] and "html" not in page
    user.put_page(LUKE, "key2", PAGE.replace("Contracts", "Torts"), "Torts", {**META, "tid": "t2", "title": "Torts"})
    assert [p["key"] for p in admin.list_pages(LUKE)] == ["key1", "key2"] and "Torts" in admin.get_page(LUKE, "key2")
    admin.put_page(LUKE, "key1", PAGE + "<!-- v2 -->", "Contracts", dict(META))      # an update replaces the page in place
    assert user.get_page(LUKE, "key1").endswith("<!-- v2 -->") and len(user.list_pages(LUKE)) == 2


def test_a_snapshot_and_a_delete_round_trip(rig):
    _, user, admin, _ = rig
    write_all(admin)
    admin.put_page(LUKE, "key1", PAGE, "Contracts", dict(META))
    admin.put_snapshot(LUKE, "key1", {"timeline": TIMELINE})
    assert user.get_snapshot(LUKE, "key1") == {"timeline": TIMELINE}
    admin.delete_timeline(LUKE, "t1")
    user._nodes_cache.clear()
    assert user.list_timelines(LUKE) == [] and user.list_nodes(LUKE, "t1") == [] and user.get_connections(LUKE, "t1") == []


def test_the_store_only_ever_touches_the_pinned_account(rig):
    fake, user, admin, db = rig
    before, log = dict(fake.docs), list(db.log)
    for call in (lambda: admin.put_project(OTHER, "p1", dict(PROJECT)),
                 lambda: admin.list_timelines(OTHER),
                 lambda: admin.put_page(OTHER, "k", PAGE, "t", dict(META)),
                 lambda: admin.get_page(OTHER, "k"),
                 lambda: admin._req("GET", f"{admin.root}/shares/x"),
                 lambda: admin._req("POST", f"{admin.root}:commit", {"writes": [{"delete": f"{admin.root}/users/{OTHER}/alto_projects/p1"}]}),
                 lambda: admin._req("GET", f"{admin.root}/hosted_shares/x"),
                 lambda: admin._req("GET", f"{admin.root}/users/{LUKE}x/alto_projects/p1")):
        with pytest.raises(CloudError):
            call()
    assert fake.docs == before and db.log == log                      # nothing written, nothing deleted
    with pytest.raises(Exception):
        AdminCloudStore(db, "bad/uid", LocalStore("/tmp/x-unused"), "proj", delete_field=DELETE_FIELD, server_timestamp=SERVER_TIMESTAMP)


def test_the_deployed_path_needs_no_bucket():
    deploy = Path(__file__).resolve().parent.parent / "deploy" / "bass-proxy"
    main, plan = (deploy / "main.py").read_text("utf-8"), (deploy / "deploy.py").read_text("utf-8")
    assert 'HOSTED_ENV = ("ALTO_EXT_PROJECT", "ALTO_EXT_UIDS")' in main
    hosted = main[main.index("def build_hosted"):main.index("@_http")]
    assert "ALTO_BUCKET" not in hosted and "storage" not in hosted and "FirestoreStore as AltoStore" not in hosted
    seg = plan[plan.index("def hosted_plan"):plan.index("def main")]
    assert "ALTO_BUCKET" not in seg and "bucket" not in seg.lower()


@pytest.mark.parametrize("tail", ["", "//x", "/./x", "/../x", "/.", "/..", "/a b", "/a\\b", "/a%2Fb", "/x/", "/.hidden"])
def test_every_path_segment_must_be_an_id(rig, tail):
    fake, user, admin, db = rig
    before, log = dict(fake.docs), list(db.log)
    bad = f"{admin.root}/users/{LUKE}/alto_projects{tail}" if tail else f"{admin.root}/users/{LUKE}//alto_projects"
    for method in ("GET", "PATCH"):
        with pytest.raises(CloudError):
            admin._req(method, bad, {"fields": {}})
    with pytest.raises(CloudError):
        admin._req("POST", f"{admin.root}:commit", {"writes": [{"delete": bad}]})
    assert fake.docs == before and db.log == log
