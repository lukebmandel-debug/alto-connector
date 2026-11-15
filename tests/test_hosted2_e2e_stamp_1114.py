"""STAMP-hosted2 (independent author): the hosted write path end to end through the REAL gate + Proxy + HostedToolBox over an
AdminCloudStore on a fake Firestore, the model always the mock. Needs the SDK (the mock client is an SDK client), so it skips without it;
named outside test_bass_* so test_bass_sdk_free's pinned list is unchanged. No network, no key, fakes only.

Rows: B1 forged uid/ids never reach another account; B2 private-web only, nothing for a second account; B3 the undo of one bad build
leaves every other document byte-identical; 2 the server publish is the same shape as luke-alto's own; 4 live_go is the only switch."""
import pytest as _pytest_sdk
_pytest_sdk.importorskip("anthropic")
_pytest_sdk.importorskip("httpx2")
import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bass_support import bass_guard, ROOT  # noqa: F401,E402
from bass_beta_support import EMAIL, build_req, edit_req   # noqa: E402
from cloudfake import FakeFirebase                         # noqa: E402
from hosted_store_fake import DELETE_FIELD, SERVER_TIMESTAMP, FakeAdminDb   # noqa: E402
from test_bass_hosted_mock_e2e import CANARY, LUKE, NOW, ORIGIN, OTHER, Sec, V   # noqa: E402,F401

from alto.bass import mock_anthropic as M                  # noqa: E402
from alto.bass.beta_ledger import LIVE_GO_KEY, confirm_key  # noqa: E402
from alto.bass.beta_proxy import Proxy                     # noqa: E402
from alto.bass.beta_store import FakeStore                 # noqa: E402
from alto.bass.client import make_client                   # noqa: E402
from alto.bass.hosted import HostedGate, hosted_config     # noqa: E402
from alto.bass.hosted_publish import HostedToolBox         # noqa: E402
from alto.cloud.session import Session                     # noqa: E402
from alto.store.admin_cloud import AdminCloudStore         # noqa: E402
from alto.store.cloud import CloudStore                    # noqa: E402
from alto.store.local import LocalStore                    # noqa: E402

DOCS = "projects/proj/databases/(default)/documents"
SAMPLE = json.loads((ROOT / "samples" / "contracts_brief.json").read_text("utf-8"))


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")


class RecDb(FakeAdminDb):
    def __init__(self, fake):
        super().__init__(fake)
        self.touched = []

    def document(self, rel):
        self.touched.append(rel)
        return super().document(rel)

    def collection(self, rel):
        self.touched.append(rel)
        return super().collection(rel)


def _mine(rel):
    return rel == f"users/{LUKE}" or rel.startswith(f"users/{LUKE}/")


def _session(fake, tmp_path, name):
    s = Session({"apiKey": "k", "projectId": "proj", "appId": "a"}, http=fake, path=tmp_path / f"{name}.json", opener=lambda u: None)
    s._accept("RT")
    return s


def _brief(title):
    b = copy.deepcopy(SAMPLE["brief"])
    b["title"] = title
    return b


def rig(tmp_path, live=True):
    fake = FakeFirebase(uid=LUKE)
    db = RecDb(fake)
    admin = AdminCloudStore(db, LUKE, LocalStore(tmp_path / "scratch"), "proj", delete_field=DELETE_FIELD, server_timestamp=SERVER_TIMESTAMP)
    store, sec, cfg = FakeStore(auto_terms=True), Sec(), hosted_config()
    clock = lambda: NOW
    store.put(confirm_key(cfg.period_id(NOW)), {"confirmed": True})
    store.put("bass_beta/bass_testers", {"emails": [EMAIL]})
    store.put("bass_beta/hosted", {"uids": [LUKE]})
    if live:
        store.put(LIVE_GO_KEY, {"on": True})
    p = Proxy(cfg, store, V(), sec, HostedToolBox(admin, LUKE), clock=clock)
    if live:
        p._client, p._client_mode = make_client("mock", mock=p.mock), "live"     # live belt, mock model: no key, no network
    la = CloudStore(_session(fake, tmp_path, "luke"), LocalStore(tmp_path / "luke-alto"))   # luke-alto's own reader/writer
    g = HostedGate(p, store, V(), cfg=cfg, pins=frozenset({LUKE}), clock=clock)
    return g, p, fake, db, la, store


def seed_other(fake):
    """A second account with a project, timeline, nodes, connections, a page, its list entry and a share."""
    for rel, val in {"alto_projects/p1": {"project_id": "p1", "name": "Other's"}, "alto_timelines/t1": {"timeline_id": "t1", "project_id": "p1"},
                     "alto_timelines/t1/nodes/a": {"id": "a", "t": "theirs"}, "alto_timelines/t1/meta/connections": {"c": []},
                     "pages/otherkey000000000000": {"html": "theirs"}, "pagemeta/otherkey000000000000": {"tid": "t1"}}.items():
        fake.docs[f"{DOCS}/users/{OTHER}/{rel}"] = {"data": {"stringValue": json.dumps(val)}}
    fake.docs[f"{DOCS}/shares/abcdefghijkmnpqrstuvwx"] = {"html": {"stringValue": "share"}}


def seed_luke_existing(la):
    """Luke's own timeline made in luke-alto before Bass ever runs (written as luke-alto writes it)."""
    la.put_project(LUKE, "p0", {"project_id": "p0", "name": "Torts", "created": "2026-10-01T10:00:00Z"})
    la.put_timeline(LUKE, "t0", {"timeline_id": "t0", "project_id": "p0", "created": "2026-10-01T10:00:00Z", "brief": {"title": "Torts"},
                                 "private_key": "lukeoldkey000000000000", "visibility": "private-web", "status": "published"})
    la.put_nodes(LUKE, "t0", [{"id": "n1", "t": "Battery"}, {"id": "n2", "t": "Assault"}])
    la.put_connections(LUKE, "t0", [["n1", "n2", "x"]])
    la.put_page(LUKE, "lukeoldkey000000000000", "<!doctype html><html><head></head><body>Torts</body></html>", "Torts",
                {"tid": "t0", "title": "Torts", "units": [], "search": [], "v": 1})
    la.put_snapshot(LUKE, "lukeoldkey000000000000", {"timeline": {"t": 1}})


def post(g, req, tok, extra_headers=None):
    h = {"Authorization": "Bearer " + tok, "Origin": ORIGIN, **(extra_headers or {})}
    st, _, b = g.handle_http("POST", h, json.dumps(req))
    return st, json.loads(b)


def _others(fake):
    return {k: copy.deepcopy(v) for k, v in fake.docs.items() if f"/users/{LUKE}/" not in k and not k.endswith(f"/users/{LUKE}")}


# -- B1 ---------------------------------------------------------------------------------------------------------------------------------
def test_b1_forged_uid_and_ids_in_the_body_headers_and_tool_args_never_reach_another_account(tmp_path):
    g, p, fake, db, la, _ = rig(tmp_path)
    seed_other(fake)
    others = _others(fake)
    brief = _brief("Forged")
    forged = M.Scenario("forged", [
        M.Step(M.Reply([M.tool_use("create_project", {"name": "Forged", "uid": OTHER})])),
        M.Step(M.Reply([M.tool_use("list_projects", {"uid": OTHER})])),
        M.Step(M.Reply([M.tool_use("get_timeline", {"timeline_id": "t1"})])),
        M.Step(M.Reply([M.tool_use("create_timeline", {"project_id": f"../../users/{OTHER}/alto_projects/p1", "brief": brief})])),
        M.Step(M.Reply([M.tool_use("create_timeline", {"project_id": "p1", "brief": brief})])),
        M.Step(M.Reply([M.tool_use("add_nodes", {"timeline_id": "t1", "nodes": SAMPLE["nodes"][:2]})])),
        M.Step(M.Reply([M.tool_use("add_nodes", {"timeline_id": f"t1/../../{OTHER}", "nodes": SAMPLE["nodes"][:1]})])),
        M.Step(M.Reply([M.tool_use("build_timeline", {"timeline_id": "t1"})])),
        M.Step(M.Reply([M.tool_use("build_timeline", {"timeline_id": f"{OTHER}"})])),
        M.Step(M.say("done")),
    ])
    p.mock.use(forged)
    hdr = {"X-Uid": OTHER, "X-Goog-Authenticated-User-Email": "other@example.com", "X-Forwarded-User": OTHER}
    body = build_req()
    body.update(uid=OTHER, user=OTHER, account=OTHER, project_id="p1", timeline_id="t1")
    post(g, body, "tok-luke", hdr)
    for req in (build_req(uid=OTHER, project_id="p1", timeline_id="t1"), edit_req(timeline_id="t1"),
                edit_req(timeline_id=f"../{OTHER}/t1"), {"action": "edit", "args": {"timeline_id": "t1", "text": "x", "uid": OTHER}}):
        post(g, req, "tok-luke", hdr)
        for tok in ("tok-other", "forged"):
            assert post(g, req, tok, {"X-Uid": LUKE}) == (200, {})
    # and a normal build still works, for Luke only
    p.mock.use(M.build("Real one", _brief("Real one"), SAMPLE["nodes"], SAMPLE["connections"]))
    st, out = post(g, build_req(), "tok-luke", hdr)
    assert st == 200 and out.get("ok") is True, out
    assert any(t["project_id"] for t in la.list_timelines(LUKE))
    assert _others(fake) == others                                          # the other account and the shares: byte-identical
    assert db.touched and all(_mine(r) for r in db.touched), sorted({r for r in db.touched if not _mine(r)})


# -- B2 + row 2 -----------------------------------------------------------------------------------------------------------------------
def test_b2_the_page_is_private_web_only_and_nothing_is_listed_for_anyone_else(tmp_path):
    g, p, fake, db, la, _ = rig(tmp_path)
    p.mock.use(M.build("Hosted Contracts", _brief("Hosted Contracts"), SAMPLE["nodes"], SAMPLE["connections"]))
    assert post(g, build_req(), "tok-luke")[1]["ok"] is True
    (tl,) = la.list_timelines(LUKE)
    key = tl["private_key"]
    assert tl["visibility"] == "private-web" and "share_key" not in tl and "view_url" not in json.dumps(tl)
    meta = fake.docs[f"{DOCS}/users/{LUKE}/pagemeta/{key}"]
    page = fake.docs[f"{DOCS}/users/{LUKE}/pages/{key}"]
    assert "shareKey" not in meta and "shareKey" not in page
    assert not [k for k in fake.docs if "/shares/" in k or "/shared/" in k or not (f"/users/{LUKE}/" in k or k.endswith(f"/users/{LUKE}"))]
    assert not list((tmp_path / "scratch").rglob("share*")) and not list((tmp_path / "scratch").rglob("*.html"))   # no /s/ entry, no built files left
    # a second account, reading the same Firestore as luke-alto's homepage does, lists nothing and cannot open Luke's page
    ofake = FakeFirebase(uid=OTHER)
    ofake.docs = fake.docs
    other = CloudStore(_session(ofake, tmp_path, "other"), LocalStore(tmp_path / "other"))
    assert other.list_pages(OTHER) == [] and other.list_timelines(OTHER) == [] and other.list_projects(OTHER) == []
    with pytest.raises(AssertionError, match="outside own uid"):           # the fake's stand-in for the owner-only rules
        other.get_page(LUKE, key)


def test_row2_the_server_publish_writes_exactly_what_luke_altos_own_publish_writes(tmp_path, monkeypatch):
    g, p, fake, db, la, _ = rig(tmp_path)
    p.mock.use(M.build("Hosted Contracts", _brief("Hosted Contracts"), SAMPLE["nodes"], SAMPLE["connections"]))
    assert post(g, build_req(), "tok-luke")[1]["ok"] is True
    (tl,) = la.list_timelines(LUKE)
    key, tid = tl["private_key"], tl["timeline_id"]
    hosted_page, hosted_meta = la.get_page(LUKE, key), copy.deepcopy(fake.docs[f"{DOCS}/users/{LUKE}/pagemeta/{key}"])
    hosted_doc_fields = set(copy.deepcopy(fake.docs[f"{DOCS}/users/{LUKE}/pages/{key}"]))
    # now luke-alto's own private-web publish of the same timeline, into the same account
    from alto import mcp_server as srv
    from alto.build import engine_stamp as es
    from alto.build.fingerprint import page_meta_tag
    from alto.cloud import accounts as A
    monkeypatch.setattr(A, "probe", lambda url: 200)
    srv.set_store(la)
    tok = srv.current_uid.set(LUKE)
    try:
        doc = la.get_timeline(LUKE, tid)
        out = srv._publish_to_account(tid, doc, "private-web", {"id": LUKE, "site": "luke-alto"})
    finally:
        srv.current_uid.reset(tok)
    assert "error" not in out, out
    alto_page, alto_meta = la.get_page(LUKE, key), fake.docs[f"{DOCS}/users/{LUKE}/pagemeta/{key}"]
    assert hosted_page == alto_page                                        # byte-identical page (luke-alto rebuilds from the nodes)
    assert es.page_engine(hosted_page) == srv.__version__ and page_meta_tag() in hosted_page   # the stamp and the fingerprint
    assert {k: v for k, v in hosted_meta.items() if k != "updatedAt"} == {k: v for k, v in alto_meta.items() if k != "updatedAt"}
    assert hosted_doc_fields == set(fake.docs[f"{DOCS}/users/{LUKE}/pages/{key}"])
    assert [x["key"] for x in la.list_pages(LUKE)] == [key]


def test_row2_publish_timeline_is_still_never_offered_and_a_rebuild_reuses_the_key(tmp_path):
    g, p, fake, db, la, _ = rig(tmp_path)
    assert "publish_timeline" not in p.real_tools.names and "publish_timeline" not in p.mock_tools.names
    assert p.real_tools.execute(LUKE, "publish_timeline", {"timeline_id": "x", "visibility": "link"}).is_error
    p.mock.use(M.build("Hosted Contracts", _brief("Hosted Contracts"), SAMPLE["nodes"], SAMPLE["connections"]))
    post(g, build_req(), "tok-luke")
    (tl,) = la.list_timelines(LUKE)
    for _ in range(2):
        out = json.loads(p.real_tools.execute(LUKE, "build_timeline", {"timeline_id": tl["timeline_id"]}).content)
        assert out["on_homepage"] is True
    assert [x["key"] for x in la.list_pages(LUKE)] == [tl["private_key"]] and la.list_timelines(LUKE)[0]["private_key"] == tl["private_key"]


# -- B3 ---------------------------------------------------------------------------------------------------------------------------------
def undo_docs(la, uid, tid):
    """The exact undo for ONE Bass-made timeline (HOSTED-BUILD.md): every document under users/<uid>/ that belongs to it, nothing else."""
    doc = la.get_timeline(uid, tid)
    key, pid = doc.get("private_key"), doc.get("project_id")
    out = [f"users/{uid}/alto_timelines/{tid}/nodes/{n['id']}" for n in la.list_nodes(uid, tid)]
    out += [f"users/{uid}/alto_timelines/{tid}/meta/connections", f"users/{uid}/alto_timelines/{tid}"]
    if key:
        out += [f"users/{uid}/pages/{key}", f"users/{uid}/pagemeta/{key}", f"users/{uid}/alto_snapshots/{key}"]
    out += [f"users/{uid}/edits/{tid}", f"users/{uid}/tl/{tid}"]            # only there if Luke opened/edited it; deleting a missing doc is a no-op
    if pid and not [t for t in la.list_timelines(uid) if t["timeline_id"] != tid and t.get("project_id") == pid]:
        out.append(f"users/{uid}/alto_projects/{pid}")                    # the project only when no other timeline lives in it
    return out


def test_b3_the_undo_of_one_bad_first_live_build_leaves_everything_else_byte_identical(tmp_path):
    g, p, fake, db, la, _ = rig(tmp_path)
    seed_other(fake)
    seed_luke_existing(la)
    before = copy.deepcopy(fake.docs)
    p.mock.use(M.build("Bad build", _brief("Bad build"), SAMPLE["nodes"], SAMPLE["connections"]))
    assert post(g, build_req(), "tok-luke")[1]["ok"] is True
    new = [t for t in la.list_timelines(LUKE) if t["timeline_id"] != "t0"]
    assert len(new) == 1
    tid = new[0]["timeline_id"]
    added = sorted(k[len(DOCS) + 1:] for k in fake.docs if k not in before)
    changed = sorted(k[len(DOCS) + 1:] for k in before if k in fake.docs and fake.docs[k] != before[k])
    assert changed == []                                                   # Bass changed none of Luke's existing documents (pagemetaV was already 1)
    undo = undo_docs(la, LUKE, tid)
    assert set(added) <= set(undo), sorted(set(added) - set(undo))         # the undo list covers everything the build wrote
    for rel in undo:
        fake.docs.pop(f"{DOCS}/{rel}", None)
    assert fake.docs == before                                             # every other timeline (and the other account): byte-identical
    assert [t["timeline_id"] for t in la.list_timelines(LUKE)] == ["t0"] and [x["key"] for x in la.list_pages(LUKE)] == ["lukeoldkey000000000000"]


# -- row 4 ------------------------------------------------------------------------------------------------------------------------------
def test_row4_live_go_off_writes_nothing_to_the_account_and_on_is_the_only_switch(tmp_path, monkeypatch):
    for k in ("ALTO_LIVE_ANTHROPIC", "LIVE_GO", "ALTO_BASS_LIVE"):
        monkeypatch.setenv(k, "1")                                         # environment switches do not change the belt
    g, p, fake, db, la, store = rig(tmp_path, live=False)
    seed_luke_existing(la)
    before = copy.deepcopy(fake.docs)
    p.mock.use(M.build("Mock one", _brief("Mock one"), SAMPLE["nodes"], SAMPLE["connections"]))
    st, out = post(g, build_req(), "tok-luke")
    assert st == 200 and out.get("mock") is True, out
    assert fake.docs == before and db.touched == []                        # nothing read or written in Luke's account
    assert p.mock_tools.store is not p.real_tools.store and p.mock_tools.store.list_timelines(LUKE)   # it went to the throw-away store
    for bad in ({"on": False}, {"on": 0}, {}, {"go": True}, {"on": None}):
        store.put(LIVE_GO_KEY, bad)
        assert p.live_go() is False
    store.put(LIVE_GO_KEY, {"on": True})
    p._client, p._client_mode = make_client("mock", mock=p.mock), "live"
    p.mock.use(M.build("Live one", _brief("Live one"), SAMPLE["nodes"], SAMPLE["connections"]))
    assert post(g, build_req(), "tok-luke")[1]["ok"] is True
    assert len(la.list_timelines(LUKE)) == 2 and fake.docs != before


# -- row 3 ------------------------------------------------------------------------------------------------------------------------------
def test_row3_put_page_refuses_to_downgrade_a_page_a_newer_alto_built_and_the_build_still_stands(tmp_path):
    from alto.build import engine_stamp as es
    g, p, fake, db, la, _ = rig(tmp_path)
    p.mock.use(M.build("Hosted Contracts", _brief("Hosted Contracts"), SAMPLE["nodes"], SAMPLE["connections"]))
    post(g, build_req(), "tok-luke")
    (tl,) = la.list_timelines(LUKE)
    key = tl["private_key"]
    newer = es.engine_meta_tag("9.9.999")
    la.put_page(LUKE, key, f"<!doctype html><html><head>{newer}</head><body>newer luke-alto page</body></html>", "x",
                {"tid": tl["timeline_id"], "title": "x", "units": [], "search": [], "v": 1})
    snap = copy.deepcopy(fake.docs[f"{DOCS}/users/{LUKE}/pages/{key}"])
    out = json.loads(p.real_tools.execute(LUKE, "build_timeline", {"timeline_id": tl["timeline_id"]}).content)
    assert out["on_homepage"] is False and "homepage_error" not in out and "StaleEngine" not in json.dumps(out)      # N2: no internals in the reply
    assert "could not be added to your homepage" in out["note"]
    assert fake.docs[f"{DOCS}/users/{LUKE}/pages/{key}"] == snap and "newer luke-alto page" in la.get_page(LUKE, key)
