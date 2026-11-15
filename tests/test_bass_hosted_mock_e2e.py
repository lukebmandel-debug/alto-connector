"""Hosted Bass end to end through the REAL gate and the REAL beta Proxy, mock transport only (alto/bass/hosted.py). Needs the SDK (the mock
client is an SDK client), so it skips in public CI and is listed in test_bass_sdk_free.py; the SDK-free half is test_bass_hosted_luke_only.py.
No network (the net guard blocks every socket), no key, fakes only."""
import pytest as _pytest_sdk
_pytest_sdk.importorskip("anthropic")   # public CI has no SDK: these skip there (listed in test_bass_sdk_free.py) and run in the SDK env
_pytest_sdk.importorskip("httpx2")
import datetime as dt
import json
import logging

import pytest

from bass_support import bass_guard, ROOT  # noqa: F401
from bass_beta_support import EMAIL, build_req, edit_req
from alto.bass import mock_anthropic as M
from alto.bass.beta_ledger import LIVE_GO_KEY, confirm_key
from alto.bass.beta_proxy import AuthError, Proxy, SecretReader, TokenVerifier
from alto.bass.beta_store import FakeStore
from alto.bass.hosted import HostedGate, hosted_config
from alto.bass.tools import ToolBox
from alto.store.local import LocalStore

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
CUT = dt.datetime(2026, 11, 18, 23, 0, tzinfo=UTC)
LUKE, OTHER = "LukeUid0000000000000000001", "OtherUid000000000000000002"
CANARY = "sk-" + "ant-HOSTED-CANARY-not-a-key-0001"
ORIGIN = "https://luke-alto.web.app"


class V(TokenVerifier):
    def verify(self, t):
        u = {"tok-luke": (LUKE, EMAIL), "tok-other": (OTHER, "other@example.com")}.get(t)
        if not u:
            raise AuthError
        return {"uid": u[0], "email": u[1], "email_verified": True}


class Sec(SecretReader):
    def __init__(self):
        self.calls = []

    def read(self, name):
        self.calls.append(name)
        return CANARY


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")


def make(tmp_path, t=NOW):
    store, sec, cfg = FakeStore(auto_terms=True), Sec(), hosted_config()
    clock = lambda: t
    store.put(confirm_key(cfg.period_id(t)), {"confirmed": True})
    store.put("bass_beta/bass_testers", {"emails": [EMAIL]})
    store.put("bass_beta/hosted", {"uids": [LUKE]})
    p = Proxy(cfg, store, V(), sec, ToolBox(LocalStore(tmp_path / "store")), clock=clock)
    return HostedGate(p, store, V(), cfg=cfg, pins=frozenset({LUKE}), clock=clock), p, store, sec


def post(g, req, tok):
    st, h, b = g.handle_http("POST", {"Authorization": "Bearer " + tok, "Origin": ORIGIN}, json.dumps(req))
    return st, h, json.loads(b)


def test_luke_gets_a_mock_answer_and_the_second_uid_gets_nothing(tmp_path):
    g, p, _, sec = make(tmp_path)
    p.mock.use(M.build("Contracts", {"title": "Contracts"}, [], []))
    st, _, out = post(g, build_req(), "tok-luke")
    assert st == 200 and out["ok"] is True and out["mock"] is True and "practice model" in out["notice"]
    assert p.mock.message_requests and sec.calls == []
    n = len(p.mock.requests)
    for tok in ("tok-other", "forged"):
        assert post(g, build_req(), tok) == (200, g.empty(ORIGIN)[1], {})
    assert len(p.mock.requests) == n                                       # the others never reached even the mock


def test_balance_shows_the_hosted_allowance(tmp_path):
    g, *_ = make(tmp_path)
    out = post(g, {"action": "balance", "args": {}}, "tok-luke")[2]
    assert out["ok"] is True and out["credits"] == 400


def test_after_the_cutoff_luke_sees_the_free_credit_ended_and_no_model_is_asked(tmp_path):
    g, p, store, sec = make(tmp_path, CUT)
    store.put(LIVE_GO_KEY, {"on": True})
    for req in (build_req(), edit_req(), {"action": "balance", "args": {}}):
        out = post(g, req, "tok-luke")[2]
        assert out["code"] == "promo_ended" and out["message"] == "The free Bass credit has ended."
    assert p.mock.requests == [] and sec.calls == [] and p._client is None


def test_live_go_on_reads_the_key_from_the_secret_only_and_never_lets_it_out(tmp_path, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    g, p, store, sec = make(tmp_path)
    store.put(LIVE_GO_KEY, {"on": True})
    outs = [post(g, edit_req(), "tok-other"), post(g, {"action": "ext", "args": {}}, "forged")]
    assert sec.calls == [] and p._client is None                               # nobody else ever makes the proxy read the key
    c = p.client()                                                             # building the live client sends nothing
    assert sec.calls == ["alto-bass-beta-key"] and str(c.base_url).startswith("https://api.anthropic.com")
    outs += [post(g, {"action": "balance", "args": {}}, "tok-luke"), post(g, {"action": "ext", "args": {}}, "tok-luke")]
    assert sec.calls == ["alto-bass-beta-key"]                                 # once per cold start, from Secret Manager only
    blob = caplog.text + "".join(capsys.readouterr()) + json.dumps(outs) + json.dumps(p.service.meta.lines) + json.dumps(p.sink.events)
    assert CANARY not in blob and "Bearer" not in blob.replace("'Bearer '+t", "")      # the UI's own header code is not a token
    assert p.mock.requests == []


# -- the build lands where luke-alto reads (alto/store/admin_cloud.py, alto/bass/hosted_publish.py) -----------------------------------------------
def live_rig(tmp_path):
    """The real gate + Proxy + HostedToolBox over an AdminCloudStore on a fake Firestore; live_go ON but the model is the mock."""
    import copy
    from cloudfake import FakeFirebase
    from hosted_store_fake import DELETE_FIELD, SERVER_TIMESTAMP, FakeAdminDb
    from alto.bass.client import make_client
    from alto.bass.hosted_publish import HostedToolBox
    from alto.cloud.session import Session
    from alto.store.admin_cloud import AdminCloudStore
    from alto.store.cloud import CloudStore
    fake = FakeFirebase(uid=LUKE)
    db = FakeAdminDb(fake)
    admin = AdminCloudStore(db, LUKE, LocalStore(tmp_path / "scratch"), "proj", delete_field=DELETE_FIELD, server_timestamp=SERVER_TIMESTAMP)
    store, sec, cfg = FakeStore(auto_terms=True), Sec(), hosted_config()
    clock = lambda: NOW
    store.put(confirm_key(cfg.period_id(NOW)), {"confirmed": True})
    store.put("bass_beta/bass_testers", {"emails": [EMAIL]})
    store.put("bass_beta/hosted", {"uids": [LUKE]})
    store.put(LIVE_GO_KEY, {"on": True})
    p = Proxy(cfg, store, V(), sec, HostedToolBox(admin, LUKE), clock=clock)
    p._client, p._client_mode = make_client("mock", mock=p.mock), "live"          # live belt, mock model: no key, no network
    sample = json.loads((ROOT / "samples" / "contracts_brief.json").read_text("utf-8"))
    brief = copy.deepcopy(sample["brief"])
    brief["title"] = "Hosted Contracts"
    p.mock.use(M.build("Hosted Contracts", brief, sample["nodes"], sample["connections"]))
    s = Session({"apiKey": "k", "projectId": "proj", "appId": "a"}, http=fake, path=tmp_path / "s.json", opener=lambda u: None)
    s._accept("RT")
    luke_alto = CloudStore(s, LocalStore(tmp_path / "luke-alto"))                  # what luke-alto's own code reads with
    return HostedGate(p, store, V(), cfg=cfg, pins=frozenset({LUKE}), clock=clock), p, fake, db, luke_alto, sec


def test_a_timeline_bass_makes_for_luke_is_listed_and_opens_in_luke_alto(tmp_path):
    g, p, fake, db, la, sec = live_rig(tmp_path)
    st, _, out = post(g, build_req(), "tok-luke")
    assert st == 200 and out["ok"] is True and "mock" not in out, out
    tls = la.list_timelines(LUKE)
    assert len(tls) == 1 and [x["name"] for x in la.list_projects(LUKE)] == ["Hosted Contracts"]
    tid = tls[0]["timeline_id"]
    assert la.list_nodes(LUKE, tid) and la.get_connections(LUKE, tid)
    assert tls[0]["visibility"] == "private-web" and tls[0]["status"] == "published" and "urls" in tls[0]
    assert not any(k in json.dumps(tls[0]).lower() for k in ("share_key", "link"))            # private: no public link
    pages = la.list_pages(LUKE)                                                 # the homepage's list
    assert [(x["tid"], x["key"]) for x in pages] == [(tid, tls[0]["private_key"])]
    html = la.get_page(LUKE, pages[0]["key"])                                   # /pv/{key}/ opens exactly this
    assert "Hosted Contracts" in html and html.lstrip().lower().startswith("<!doctype html")
    assert not [k for k in fake.docs if "/shares/" in k or "/shared/" in k or "hosted_shares" in k]     # nothing shared or public
    assert sec.calls == [] or sec.calls == ["alto-bass-beta-key"]


def test_an_edit_bass_makes_updates_the_same_page(tmp_path):
    g, p, fake, db, la, _ = live_rig(tmp_path)
    post(g, build_req(), "tok-luke")
    tl = la.list_timelines(LUKE)[0]
    key, tid = tl["private_key"], tl["timeline_id"]
    before = la.get_page(LUKE, key)
    box = p.real_tools
    new = {k: v for k, v in la.list_nodes(LUKE, tid)[0].items() if not k.startswith("_")}
    new.update(id="zz-new", title="Brand new card")
    out = box.execute(LUKE, "add_nodes", {"timeline_id": tid, "nodes": [new]})
    assert not out.is_error, out.content
    out = box.execute(LUKE, "build_timeline", {"timeline_id": tid})
    assert not out.is_error and json.loads(out.content)["on_homepage"] is True, out.content
    assert [x["key"] for x in la.list_pages(LUKE)] == [key] and len(la.list_timelines(LUKE)) == 1      # same page, not a second one
    after = la.get_page(LUKE, key)
    assert "Brand new card" in after and "Brand new card" not in before


def test_a_second_uid_gets_nothing_and_nothing_is_written(tmp_path):
    g, p, fake, db, la, _ = live_rig(tmp_path)
    before, log, n = dict(fake.docs), list(db.log), len(p.mock.requests)
    for tok in ("tok-other", "forged"):
        assert post(g, build_req(), tok) == (200, g.empty(ORIGIN)[1], {})
    assert fake.docs == before and db.log == log and len(p.mock.requests) == n
    # and even if a build were somehow asked for the other uid, the store refuses it
    out = p.real_tools.execute(OTHER, "list_projects", {})
    assert out.is_error and "pinned account" in out.content
    assert fake.docs == before


def test_a_failed_homepage_step_is_told_plainly_and_without_internals(tmp_path, monkeypatch):
    g, p, fake, db, la, _ = live_rig(tmp_path)
    from alto.store.admin_cloud import AdminCloudStore
    def boom(self, *a, **k):
        raise RuntimeError("Firestore exploded at users/SECRET-PATH/pages")
    monkeypatch.setattr(AdminCloudStore, "put_page", boom)
    st, _, out = post(g, build_req(), "tok-luke")
    assert st == 200
    seen = json.dumps(p.mock.requests)
    assert "could not be added to your homepage" in seen
    assert "is on your homepage now" not in seen and "SECRET-PATH" not in seen and "RuntimeError" not in seen and "homepage_error" not in seen
    assert la.list_pages(LUKE) == [] and len(la.list_timelines(LUKE)) == 1          # the draft stands, nothing half-published
