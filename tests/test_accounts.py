"""More than one Alto account, and a chat that starts on its own.

A person can have several Alto sites, one per Google account they have used it
with, and a Claude chat that did not come from a timeline's "Edit timeline"
button has to be able to find the right one (alto/cloud/accounts.py). Every
Firestore in these tests is an in-memory fake (cloudfake.py); no test touches
the real account or the real ~/.config/alto (conftest points both at temp
directories).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cloudfake import FakeFirebase  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = json.loads((ROOT / "samples" / "contracts_brief.json").read_text(encoding="utf-8"))
KEY = "3nyerz5twqgfzaczvnddkk"         # a published key that starts with a digit


def cfg(n):
    return {"apiKey": f"k{n}", "projectId": f"proj{n}", "appId": "a"}


@pytest.fixture
def world(monkeypatch):
    """Two Alto accounts — school (proj1) and personal (proj2) — each signed in
    on this computer, neither the default. Drafts live in the local folder."""
    from alto import mcp_server as srv
    from alto.cloud import accounts as A, session as sess
    for k in ("ALTO_STORE", "ALTO_FIREBASE_SITE", "ALTO_FIREBASE_PROJECT",
              "ALTO_FIREBASE_CONFIG", "ALTO_SITE_MANAGED"):
        monkeypatch.delenv(k, raising=False)
    A._reset_for_tests()
    srv.set_store(None)
    f1 = FakeFirebase("U1", "proj1", "school@example.com")
    f2 = FakeFirebase("U2", "proj2", "me@example.com")

    def dispatch(method, url, body=None, headers=None, timeout=30):
        if url.startswith("https://securetoken.googleapis.com/"):
            f = f1 if "key=k1" in url else f2
        else:
            f = f1 if "/projects/proj1/" in url else f2
        return f(method, url, body, headers, timeout)

    monkeypatch.setattr(sess, "_http", dispatch)
    for n, f in ((1, f1), (2, f2)):
        sess.Session(cfg(n), http=dispatch,
                     path=sess.config_dir() / f"session-proj{n}.json",
                     opener=lambda u: None)._accept("RT")
    A.register({"id": "school-alto", "site": "school-alto", "project": "proj1",
                "config": cfg(1), "email": "school@example.com", "uid": "U1"})
    A.register({"id": "me-alto", "site": "me-alto", "project": "proj2",
                "config": cfg(2), "email": "me@example.com", "uid": "U2"})
    monkeypatch.setattr(A, "probe", lambda url: 200)
    yield type("W", (), {"srv": srv, "A": A, "f1": f1, "f2": f2, "sess": sess,
                         "dispatch": dispatch})
    A._reset_for_tests()
    srv.set_store(None)


def _seed(w, account, tid="contracts-i", key=None, status="built"):
    """A finished draft in an account, written as the connector would."""
    a, _ = w.A.resolve(account)
    d = SAMPLE
    with w.A.scope(a):
        st = w.srv.get_store()
        u = w.srv.uid()
        st.put_project(u, "law", {"project_id": "law", "name": "Law", "purpose": "p",
                                  "kind": "studying", "created": "2026-09-01T00:00:00+00:00"})
        doc = {"timeline_id": tid, "project_id": "law", "brief": d["brief"],
               "status": status, "consent": {"granted": True}}
        if key:
            doc.update(private_key=key, visibility="private-web")
        st.put_timeline(u, tid, doc)
        st.put_nodes(u, tid, [dict(n) for n in d["nodes"]])
        st.put_connections(u, tid, d["connections"])
    return a


# ── naming an account ───────────────────────────────────────────────────────

def test_a_site_name_comes_out_of_any_address(world):
    p = world.A.parse_site
    assert p("luke-alto") == p("luke-alto.web.app") == p("https://luke-alto.web.app/pv/x/") == "luke-alto"
    assert p("luke-alto.firebaseapp.com") == "luke-alto"
    assert p("me@example.com") == "" and p("Contracts I") == "" and p("") == ""
    assert p("Torts") == "torts"          # a bare word can be a site name


def test_the_accounts_this_computer_knows(world):
    rows = world.A.known()
    assert [a["id"] for a in rows] == ["school-alto", "me-alto"]
    assert [a["email"] for a in rows] == ["school@example.com", "me@example.com"]
    assert all(a["signed_in"] for a in rows)
    assert not any(world.A.is_default(a) for a in rows)


def test_a_sign_in_nothing_names_is_still_an_account(world, tmp_path):
    """An earlier sign_in, or another Alto install, left a session for a project
    accounts.json does not list. It is reachable; its site is learned later."""
    world.sess.Session(cfg(3), http=world.dispatch,
                       path=world.sess.config_dir() / "session-proj3.json",
                       opener=lambda u: None)._accept("RT")
    a = [x for x in world.A.known() if x["project"] == "proj3"][0]
    assert a["source"] == "session" and a["site"] == "" and a["id"] == "proj3"


def test_resolve_by_email_site_address_or_project(world):
    r = world.A.resolve
    assert r("school@example.com")[0]["id"] == "school-alto"
    assert r("https://me-alto.web.app/")[0]["id"] == "me-alto"
    assert r("proj2")[0]["id"] == "me-alto"
    assert r("me")[0]["id"] == "me-alto"                      # a part of the name
    acct, err = r("nobody@example.com")
    assert acct is None and err["error"] == "unknown_account"
    assert "connect_account" in err["message"] and len(err["accounts"]) == 2


def test_an_email_on_two_sites_is_ambiguous_not_guessed(world):
    world.A.register({"id": "second-alto", "site": "second-alto", "project": "proj1",
                      "config": cfg(1)})
    acct, err = world.A.resolve("school@example.com")
    assert acct is None and err["error"] == "ambiguous_account"
    assert {a["account"] for a in err["accounts"]} == {"school-alto", "second-alto"}


# ── a call runs as one account, then everything is put back ─────────────────

def test_scope_points_the_store_and_settings_at_the_account_and_back(world):
    a, _ = world.A.resolve("school-alto")
    before = dict(os.environ)
    with world.A.scope(a):
        assert world.srv.store_mode() == "cloud" and world.srv.uid() == "U1"
        assert os.environ["ALTO_FIREBASE_PROJECT"] == "proj1"
        assert os.environ["ALTO_FIREBASE_SITE"] == "school-alto"
        assert json.loads(os.environ["ALTO_FIREBASE_CONFIG"])["apiKey"] == "k1"
    assert dict(os.environ) == before
    assert world.srv.store_mode() == "local"


def test_scope_restores_the_environment_when_the_call_fails(world):
    a, _ = world.A.resolve("me-alto")
    before = dict(os.environ)
    with pytest.raises(RuntimeError):
        with world.A.scope(a):
            raise RuntimeError("boom")
    assert dict(os.environ) == before and world.A.current() is None


def test_each_account_has_its_own_projects(world):
    srv = world.srv
    assert srv.create_project(name="Torts", account="school-alto")["account"] == "school-alto"
    srv.create_project(name="Novel", account="me@example.com")
    names = lambda r: [p["name"] for p in r["projects"]]
    assert names(srv.list_projects(account="school-alto")) == ["Torts"]
    assert names(srv.list_projects(account="me-alto")) == ["Novel"]
    assert names(srv.list_projects()) == []                   # the local folder
    assert any("Torts" in json.dumps(d) for d in world.f1.docs.values())
    assert not any("Torts" in json.dumps(d) for d in world.f2.docs.values())


def test_all_accounts_lists_each_one_labelled(world):
    srv = world.srv
    srv.create_project(name="Torts", account="school-alto")
    srv.create_project(name="Novel", account="me-alto")
    rows = srv.list_projects(account="all")["accounts"]
    by = {r["account"]: r for r in rows}
    assert by["(folder on this computer)"]["projects"] == []
    assert [p["name"] for p in by["school-alto"]["projects"]] == ["Torts"]
    assert by["school-alto"]["email"] == "school@example.com"
    assert [p["name"] for p in by["me-alto"]["projects"]] == ["Novel"]


def test_a_lapsed_account_does_not_hide_the_others(world):
    world.f2.good_rt = "revoked"
    rows = world.srv.list_projects(account="all")["accounts"]
    by = {r["account"]: r for r in rows}
    assert "projects" in by["school-alto"] and "error" in by["me-alto"]
    one = world.srv.list_projects(account="me-alto")
    assert one["error"] == "sign_in_required" and one["account"] == "me-alto"
    assert "sign_in(account='me-alto')" in one["next"]


def test_the_local_listing_points_at_the_accounts(world):
    out = world.srv.list_projects()
    assert [a["account"] for a in out["accounts"]] == ["school-alto", "me-alto"]
    assert 'account="all"' in out["note"]
    assert "create it here with exactly" in out["note"]       # the last resort


def test_nothing_is_remembered_between_calls(world):
    """One connector process can serve several chats; a choice made in one must
    never redirect another's writes."""
    srv = world.srv
    srv.create_project(name="Novel", account="me-alto")
    assert not hasattr(srv, "use_account")
    assert srv.list_projects()["projects"] == []            # no account: the folder
    assert [p["name"] for p in srv.list_projects(account="me-alto")["projects"]] == ["Novel"]
    assert srv.list_projects()["projects"] == []            # and still none after


def test_a_project_the_accounts_already_hold_is_not_created_again(world):
    """The failure that started this: a chat that could not see 'Torts' made an
    empty one in the folder and was about to rebuild the timeline."""
    srv = world.srv
    srv.create_project(name="Torts", account="school-alto")
    out = srv.create_project(name="Torts")                   # no account: the folder
    assert out["error"] == "exists_in_account" and out["account"] == "school-alto"
    assert "account='school-alto'" in out["next"]
    assert srv.list_projects()["projects"] == []             # nothing was created
    assert srv.create_project(name="Novel")["project_id"] == "novel"   # other names are fine
    again = srv.create_project(name="torts", account="me-alto")        # a different account
    assert again["error"] == "exists_in_account"


def test_an_unknown_account_is_an_error_with_the_choices(world):
    out = world.srv.list_projects(account="stranger@example.com")
    assert out["error"] == "unknown_account" and len(out["accounts"]) == 2


# ── the guide shows a chat that starts on its own where everything is ───────

def test_the_guide_lists_the_timelines_in_every_signed_in_account(world):
    _seed(world, "me-alto")
    g = world.srv.get_interview_guide()
    assert [a["account"] for a in g["accounts"]["known"]] == ["school-alto", "me-alto"]
    rows = {r["account"]: r for r in g["accounts"]["timelines_in_accounts"]}
    tl = rows["me-alto"]["projects"][0]["timelines"][0]
    assert tl["timeline_id"] == "contracts-i" and tl["title"] == "Contracts I"
    assert "never create it again" in g["accounts"]["next"]
    assert g["drafts"] == []                                   # nothing in the folder


def test_with_no_account_the_guide_says_how_to_get_one(world):
    for f in (world.A.accounts_path(),):
        f.unlink()
    for s in world.sess.config_dir().glob("session-*.json"):
        s.unlink()
    g = world.srv.get_interview_guide()
    assert g["accounts"]["known"] == [] and "connect_account" in g["accounts"]["next"]


# ── a timeline the chat cannot find is never "missing" ──────────────────────

def test_a_timeline_in_another_account_is_pointed_to(world):
    _seed(world, "me-alto")
    out = world.srv.get_timeline("contracts-i")                # no account: the folder
    assert out["error"] == "not_found"
    assert out["found_in_accounts"] == [
        {"account": "me-alto", "email": "me@example.com",
         "timeline_id": "contracts-i", "title": "Contracts I"}]
    assert "account=<account>" in out["next"]
    got = world.srv.get_timeline("contracts-i", account="me-alto")
    assert got["timeline_id"] == "contracts-i" and got["account"] == "me-alto"
    assert len(got["node_ids"]) == len(SAMPLE["nodes"])


def test_a_published_address_or_a_title_names_the_timeline(world):
    _seed(world, "me-alto", key=KEY)
    for ref in (f"https://me-alto.web.app/pv/{KEY}/", KEY, "Contracts I",
                "contracts i — alto timeline", "contracts-i"):
        out = world.srv.get_timeline(ref, account="me-alto")
        assert out.get("timeline_id") == "contracts-i", (ref, out)


def test_a_url_key_is_not_called_a_bad_id_without_saying_what_to_pass(world):
    out = world.srv.get_timeline("3nyerz5twqgfzaczvnddkk-nope!", account="me-alto")
    assert out["error"] == "bad_id" and "published page" in out["message"]


def test_a_page_with_no_draft_is_reported_and_importable_or_not(world):
    """A page on the homepage that no draft here belongs to — published from
    another computer. It is listed, said to be so, and whether it can come back."""
    a, _ = world.A.resolve("me-alto")
    with world.A.scope(a):
        st = world.srv.get_store()
        u = world.srv.uid()
        st.put_page(u, KEY, "<html>x</html>", "Contracts I", {
            "title": "Contracts I — Alto Timeline", "heading": "Contracts I",
            "project": "Law", "tid": "contracts-i", "units": [], "search": [], "v": 1})
    out = world.srv.list_projects(account="me-alto")
    pg = out["published_without_draft"][0]
    assert pg["published_key"] == KEY and pg["can_import"] is False
    miss = world.srv.get_timeline("Contracts I", account="me-alto")
    assert miss["error"] == "bad_id" and "published page" in miss["message"]
    assert miss["published_without_draft"][0]["published_key"] == KEY
    assert "import_timeline" in miss["next"]
    no = world.srv.import_timeline(KEY, account="me-alto")
    assert no["error"] == "no_snapshot" and "Do not rebuild it from memory" in no["next"]


def test_a_draft_published_from_a_folder_comes_back_with_import_timeline(world):
    """The folder keeps the draft and the page goes to the account, with a
    restorable copy beside it; any other chat restores it exactly."""
    a, _ = world.A.resolve("me-alto")
    from alto.store.cloud import CloudStore
    from alto.store.local import LocalStore
    srv = world.srv
    folder = LocalStore(srv.store_dir())
    folder.put_project("local", "law", {"project_id": "law", "name": "Law", "kind": "studying",
                                        "purpose": "p", "created": "2026-09-01"})
    doc = {"timeline_id": "contracts-i", "project_id": "law", "brief": SAMPLE["brief"],
           "status": "published", "private_key": KEY, "visibility": "private-web"}
    folder.put_timeline("local", "contracts-i", doc)
    folder.put_nodes("local", "contracts-i", [dict(n) for n in SAMPLE["nodes"]])
    folder.put_connections("local", "contracts-i", SAMPLE["connections"])
    with world.A.scope(a):
        cloud = CloudStore(world.A.session_for(a), folder)
        cloud.put_page(srv.uid(), KEY, "<html>x</html>", "Contracts I", {
            "title": "Contracts I", "heading": "Contracts I", "project": "Law",
            "tid": "contracts-i", "units": [], "search": [], "v": 1})
        cloud.put_snapshot(srv.uid(), KEY, {
            "v": 1, "project": folder.get_project("local", "law"), "timeline": doc,
            "nodes": [{k: v for k, v in n.items() if k != "_seq"}
                      for n in folder.list_nodes("local", "contracts-i")],
            "connections": folder.get_connections("local", "contracts-i")})
    pg = srv.list_projects(account="me-alto")["published_without_draft"][0]
    assert pg["can_import"] is True
    got = srv.import_timeline(pg["published_key"], account="me-alto")
    assert got["restored"]["timeline_id"] == "contracts-i"
    assert got["restored"]["nodes"] == len(SAMPLE["nodes"])
    after = srv.list_projects(account="me-alto")
    assert "published_without_draft" not in after
    assert [p["name"] for p in after["projects"]] == ["Law"]
    again = srv.import_timeline("contracts-i", account="me-alto")
    assert again["error"] == "already_here"


# ── publishing into an account this computer cannot deploy for ──────────────

def test_publishing_into_a_connected_account_writes_the_page_and_never_deploys(world, monkeypatch):
    import alto.publish_static as ps
    monkeypatch.setattr(ps, "deploy_site",
                        lambda *a, **k: pytest.fail("a connected account must not be deployed to"))
    _seed(world, "me-alto")
    out = world.srv.publish_timeline("contracts-i", "private-web", account="me-alto")
    assert out["account"] == "me-alto" and out["visibility"] == "private-web"
    key = out["view_url"].rsplit("/pv/", 1)[1].strip("/")
    assert out["view_url"] == f"https://me-alto.web.app/pv/{key}/"
    pages = [n for n in world.f2.docs if n.endswith(f"/users/U2/pages/{key}")]
    metas = [n for n in world.f2.docs if n.endswith(f"/users/U2/pagemeta/{key}")]
    assert pages and metas
    assert not [n for n in world.f1.docs if "/pages/" in n]   # the other account untouched
    again = world.srv.get_timeline("contracts-i", account="me-alto")
    assert again["status"] == "published" and again["urls"]["view_url"] == out["view_url"]


def test_publishing_says_so_when_the_site_shell_is_missing(world, monkeypatch):
    monkeypatch.setattr(world.A, "probe", lambda url: 404)
    _seed(world, "me-alto")
    out = world.srv.publish_timeline("contracts-i", "private-web", account="me-alto")
    assert "shell is not deployed" in out["note"]


def test_a_sign_in_with_no_known_site_gets_no_made_up_address(world, monkeypatch):
    """Never aim at the project's default site: it may be someone else's."""
    f3 = FakeFirebase("U3", "proj3", "third@example.com")
    real = world.dispatch

    def dispatch(method, url, body=None, headers=None, timeout=30):
        if "key=k3" in url or "/projects/proj3/" in url:
            return f3(method, url, body, headers, timeout)
        return real(method, url, body, headers, timeout)
    monkeypatch.setattr(world.sess, "_http", dispatch)
    world.sess.Session(cfg(3), http=dispatch,
                       path=world.sess.config_dir() / "session-proj3.json",
                       opener=lambda u: None)._accept("RT")
    monkeypatch.setattr(world.A, "fetch_config", lambda host: cfg(3))
    a, _ = world.A.resolve("proj3")
    assert a["site"] == "" and a["source"] == "session"
    assert world.srv.sign_in(account="proj3")["status"] == "signed_in"
    out = world.srv.list_projects(account="proj3")
    assert out["projects"] == []
    again, _ = world.A.resolve("third@example.com")
    assert again["site"] == ""                       # nothing to learn it from yet
    # Publishing has no address to give back, and says so instead of inventing one.
    _seed(world, "proj3")
    res = world.srv.publish_timeline("contracts-i", "private-web", account="proj3")
    assert "view_url" not in res and "does not know this account's site" in res["note"]


# ── connect_account ─────────────────────────────────────────────────────────

def test_connect_adds_an_existing_site_from_its_address_alone(world, monkeypatch):
    monkeypatch.setattr(world.A, "fetch_config", lambda host: cfg(4))
    monkeypatch.setattr(world.A, "SIGN_IN_WAIT", 0)
    f4 = FakeFirebase("U4", "proj4", "extra@example.com")
    real = world.dispatch

    def dispatch(method, url, body=None, headers=None, timeout=30):
        if "key=k4" in url or "/projects/proj4/" in url:
            return f4(method, url, body, headers, timeout)
        return real(method, url, body, headers, timeout)
    monkeypatch.setattr(world.sess, "_http", dispatch)
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda u: opened.append(u))
    out = world.srv.connect_account("https://extra-alto.web.app/pv/abc/")
    assert out["status"] == "waiting" and "/connect/?port=" in out["url"]
    assert out["url"].startswith("https://extra-alto.web.app/connect/") and opened
    # The user clicks Continue with Google: the page posts to the loopback.
    q = urllib.parse.parse_qs(urllib.parse.urlparse(out["url"]).query)
    body = urllib.parse.urlencode({"state": q["state"][0], "rt": "RT"}).encode()
    urllib.request.urlopen(urllib.request.Request(
        f"http://127.0.0.1:{q['port'][0]}/cb", data=body, method="POST"), timeout=5).read()
    done = world.srv.connect_account("extra-alto")
    assert done["status"] == "connected" and done["email"] == "extra@example.com"
    assert done["account"] == "extra-alto" and "account='extra-alto'" in done["next"]
    saved = json.loads(world.A.accounts_path().read_text())["accounts"]
    assert [r["site"] for r in saved][-1] == "extra-alto"
    assert "refresh_token" not in json.dumps(saved) and "RT" not in json.dumps(saved)
    assert world.A.resolve("extra@example.com")[0]["id"] == "extra-alto"


def test_connect_refuses_a_site_that_is_not_alto(world, monkeypatch):
    monkeypatch.setattr(world.A, "fetch_config", lambda host: cfg(9))
    monkeypatch.setattr(world.A, "probe", lambda url: 404)
    out = world.srv.connect_account("some-other-site")
    assert out["error"] == "not_an_alto_site" and "next" in out


def test_connect_says_when_the_address_reaches_nothing(world, monkeypatch):
    def nope(host):
        raise world.sess.CloudError("could not reach it")
    monkeypatch.setattr(world.A, "fetch_config", nope)
    assert world.srv.connect_account("ghost-alto")["error"] == "site_not_found"
    assert world.srv.connect_account("me@example.com")["error"] == "bad_site"


def test_list_accounts_shows_email_and_site_but_no_token(world):
    out = world.srv.list_accounts()
    assert [a["account"] for a in out["accounts"]] == ["school-alto", "me-alto"]
    assert out["accounts"][1] == {"account": "me-alto", "email": "me@example.com",
                                  "site_url": "https://me-alto.web.app",
                                  "project": "proj2", "signed_in": True,
                                  "default": False}
    assert "RT" not in json.dumps(out) and "k2" not in json.dumps(out)


# ── the default account behaves exactly as before ───────────────────────────

def test_the_default_account_is_untouched_by_the_others(world, monkeypatch):
    monkeypatch.setenv("ALTO_FIREBASE_SITE", "school-alto")
    monkeypatch.setenv("ALTO_FIREBASE_PROJECT", "proj1")
    monkeypatch.setenv("ALTO_FIREBASE_CONFIG", json.dumps(cfg(1)))
    monkeypatch.setenv("ALTO_STORE", "cloud")
    world.sess.set_session(world.sess.Session(cfg(1), http=world.dispatch,
                                              opener=lambda u: None))
    try:
        d = world.A.default()
        assert d["id"] == "school-alto" and d["source"] == "settings"
        assert [a["id"] for a in world.A.known()] == ["school-alto", "me-alto"]
        # Asking for the default by name is the same as not asking: no scoping.
        world.srv.create_project(name="Torts", account="school-alto")
        assert [p["name"] for p in world.srv.list_projects()["projects"]] == ["Torts"]
        assert "account" not in world.srv.list_projects()
        # And the other account is still one argument away.
        assert world.srv.list_projects(account="me-alto")["projects"] == []
    finally:
        world.sess.set_session(None)


# ── the real publish path keeps a restorable copy ───────────────────────────

def test_publishing_from_a_folder_keeps_a_copy_any_other_chat_can_restore(world, monkeypatch):
    """Drafts in a folder, page in the account (the 'projects kept in a folder'
    publish): the next computer, or a chat that starts on its own, finds the
    page on the homepage and gets the draft back with import_timeline."""
    import alto.publish_static as ps
    srv = world.srv
    monkeypatch.setenv("ALTO_FIREBASE_SITE", "school-alto")
    monkeypatch.setenv("ALTO_FIREBASE_PROJECT", "proj1")
    monkeypatch.setenv("ALTO_FIREBASE_CONFIG", json.dumps(cfg(1)))
    monkeypatch.setenv("ALTO_FIREBASE_BIN", sys.executable)        # any file that exists
    monkeypatch.setenv("ALTO_STORE", "local")
    monkeypatch.setattr(ps, "deploy_site", lambda site: "https://school-alto.web.app")
    monkeypatch.setattr(ps, "verify_live", lambda site, live: [])
    world.sess.set_session(world.sess.Session(cfg(1), http=world.dispatch,
                                              opener=lambda u: None))
    try:
        from alto.store.local import LocalStore
        folder = LocalStore(srv.store_dir())
        folder.put_project("local", "law", {"project_id": "law", "name": "Law",
                                            "kind": "studying", "purpose": "p",
                                            "created": "2026-09-01T00:00:00+00:00"})
        folder.put_timeline("local", "contracts-i", {
            "timeline_id": "contracts-i", "project_id": "law", "brief": SAMPLE["brief"],
            "status": "built", "consent": {"granted": True}})
        folder.put_nodes("local", "contracts-i", [dict(n) for n in SAMPLE["nodes"]])
        folder.put_connections("local", "contracts-i", SAMPLE["connections"])
        out = srv.publish_timeline("contracts-i", "private-web")
        assert out["view_url"].startswith("https://school-alto.web.app/pv/"), out
        key = out["view_url"].rsplit("/pv/", 1)[1].strip("/")
        assert any(n.endswith(f"/users/U1/alto_snapshots/{key}") for n in world.f1.docs)
        # Another chat, the account's own store: a page, and no draft.
        monkeypatch.setenv("ALTO_STORE", "cloud")
        srv.set_store(None)
        listing = srv.list_projects()
        pg = listing["published_without_draft"][0]
        assert pg["published_key"] == key and pg["can_import"] is True
        got = srv.import_timeline(key)
        assert got["restored"]["nodes"] == len(SAMPLE["nodes"])
        back = srv.get_timeline("contracts-i")
        assert back["status"] == "published" and len(back["node_ids"]) == len(SAMPLE["nodes"])
        assert "published_without_draft" not in srv.list_projects()
    finally:
        world.sess.set_session(None)


def test_a_bare_sign_in_learns_its_site_from_its_own_timelines_and_keeps_working(world, monkeypatch):
    """A sign-in found on this computer knows its project, not its site. The
    first read of the account teaches it (from the addresses its published
    timelines already have); the name used before still finds it, and the
    account is not listed twice."""
    f3 = FakeFirebase("U3", "proj3", "third@example.com")
    real = world.dispatch

    def dispatch(method, url, body=None, headers=None, timeout=30):
        if "key=k3" in url or "/projects/proj3/" in url:
            return f3(method, url, body, headers, timeout)
        return real(method, url, body, headers, timeout)
    monkeypatch.setattr(world.sess, "_http", dispatch)
    world.sess.Session(cfg(3), http=dispatch,
                       path=world.sess.config_dir() / "session-proj3.json",
                       opener=lambda u: None)._accept("RT")
    monkeypatch.setattr(world.A, "fetch_config", lambda host: cfg(3))
    a, _ = world.A.resolve("proj3")
    with world.A.scope(a):
        st, u = world.srv.get_store(), world.srv.uid()
        st.put_timeline(u, "t1", {"timeline_id": "t1", "project_id": "p", "brief": {"title": "T"},
                                  "urls": {"view_url": "https://third-alto.web.app/pv/abc/"}})
    g = world.srv.get_interview_guide()
    third = [r for r in g["accounts"]["timelines_in_accounts"] if r["project"] == "proj3"][0]
    assert third["account"] == "third-alto" and third["site_url"] == "https://third-alto.web.app"
    assert [k["account"] for k in g["accounts"]["known"]].count("third-alto") == 1
    assert "proj3" not in [k["account"] for k in g["accounts"]["known"]]
    # the old name, the site, the project and the email all still find it
    for ref in ("proj3", "third-alto", "third@example.com"):
        assert world.A.resolve(ref)[0]["id"] == "third-alto"
    saved = json.loads(world.A.accounts_path().read_text())["accounts"]
    assert [r["id"] for r in saved if r["project"] == "proj3"] == ["third-alto"]


def test_two_sites_of_one_project_list_its_data_once(world):
    world.A.register({"id": "second-alto", "site": "second-alto", "project": "proj1",
                      "config": cfg(1), "email": "school@example.com", "uid": "U1"})
    rows = world.srv.list_projects(account="all")["accounts"]
    dup = [r for r in rows if r["account"] == "second-alto"][0]
    assert dup["same_data_as"] == "school-alto" and "projects" not in dup


# ── what the model is actually shown ────────────────────────────────────────

STORE_TOOLS = ("get_interview_guide", "sign_in", "list_projects", "create_project",
               "create_timeline", "record_materials_consent", "set_entities",
               "set_axis_values", "add_nodes", "add_connections", "set_flags",
               "set_overview", "run_layout_preview", "build_timeline",
               "preview_timeline", "publish_timeline", "get_timeline",
               "import_timeline", "delete_nodes", "delete_timeline", "delete_project")


def test_every_tool_that_touches_a_store_takes_an_optional_account(world):
    import asyncio
    by = {t.name: t for t in asyncio.run(world.srv.mcp.list_tools())}
    for name in STORE_TOOLS:
        schema = by[name].inputSchema
        assert "account" in schema["properties"], name
        assert "account" not in schema.get("required", []), name
    assert "Google email" in by["add_nodes"].inputSchema["properties"]["account"]["description"]
    for name in ("list_accounts", "connect_account"):
        assert name in by
    assert "use_account" not in by
    # the tools set_up_site and the guide prompt are not account-scoped
    assert "account" not in by["set_up_site"].inputSchema["properties"]


def test_a_call_through_the_mcp_layer_runs_as_the_account(world):
    import asyncio
    world.srv.create_project(name="Novel", account="me-alto")
    res = asyncio.run(world.srv.mcp.call_tool("list_projects", {"account": "me-alto"}))
    text = json.dumps(res, default=str)
    assert "Novel" in text and "me-alto" in text
    res = asyncio.run(world.srv.mcp.call_tool("list_accounts", {}))
    assert "school@example.com" in json.dumps(res, default=str)
