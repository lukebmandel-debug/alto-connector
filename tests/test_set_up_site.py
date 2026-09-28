"""set_up_site: a new user's own site, Firestore, rules and sign-in, driven
end to end against a fake Firebase CLI (no network, no browser).

The fake keeps the state a real project would: logged in or not, projects,
web apps, databases, hosting sites, whether Google sign-in was deployed. Each
test drives the provisioner synchronously (`_drive`) so the order of effects is
deterministic."""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import mcp_server as srv  # noqa: E402
from alto.cloud import provision as pv  # noqa: E402
from alto.cloud import site as site_rec  # noqa: E402

CFG = {"apiKey": "AIza-new", "authDomain": "x.firebaseapp.com",
       "projectId": "PID", "appId": "1:2:web:3", "projectNumber": "9"}


class FakeFirebase:
    def __init__(self, email="priya.k@example.com", tos=False, taken=0,
                 fail_once=()):
        self.email, self.tos, self.taken = email, tos, taken
        self.fail_once = set(fail_once)
        self.logged_in = False
        self.projects, self.apps, self.dbs, self.sites = [], [], [], []
        self.auth_config = None
        self.calls = []
        self.enabled = set()
        self.log_reason = ""
        self.opened = []

    def api(self, method, url, body, token):
        self.calls.append(["<api>", method, url])
        assert token == "TOKEN"
        if url.endswith(":batchEnable"):
            self.enabled.update(body["serviceIds"])
            return 200, {"name": "operations/op1", "done": False}
        return 200, {"name": "operations/op1", "done": True}

    def ok(self, result):
        return 0, "✔ spinner\n" + json.dumps({"status": "success",
                                              "result": result}), ""

    def err(self, msg):
        return 1, json.dumps({"status": "error", "error": msg}), msg

    def __call__(self, args, timeout=0):
        self.calls.append(args)
        cmd = args[0]
        proj = args[args.index("--project") + 1] if "--project" in args else ""
        if cmd in self.fail_once:
            self.fail_once.discard(cmd)
            return self.err(f"{cmd}: 503 backend unavailable")
        if cmd == "login:list":
            return self.ok([{"user": {"email": self.email}}]
                           if self.logged_in else [])
        if cmd == "projects:create":
            if self.tos:
                # What the real CLI prints: the reason is only in its log.
                self.log_reason = ("Callers must accept Terms of Service "
                                   "(cloudresourcemanager.googleapis.com)")
                return self.err("Failed to create project. See "
                                "firebase-debug.log for more info.")
            if self.taken:
                self.taken -= 1
                return self.err("Project ID already exists")
            self.projects.append(args[1])
            self.sites.append(args[1])          # the default site
            return self.ok({"projectId": args[1]})
        if cmd == "projects:list":
            return self.ok([{"projectId": p} for p in self.projects])
        if cmd == "apps:list":
            return self.ok(self.apps)
        if cmd == "apps:create":
            app = {"appId": "1:2:web:3", "displayName": args[2]}
            self.apps.append(app)
            return self.ok(app)
        if cmd == "apps:sdkconfig":
            return self.ok({"fileName": "x", "sdkConfig": {**CFG, "projectId": proj}})
        if cmd == "firestore:databases:list":
            return self.ok([{"name": f"projects/{proj}/databases/{d}"}
                            for d in self.dbs])
        if cmd == "firestore:databases:create":
            if "firestore.googleapis.com" not in self.enabled:
                return self.err("HTTP Error: 403, Cloud Firestore API has not "
                                "been used in project x before or it is disabled")
            self.dbs.append(args[1])
            return self.ok({"name": args[1]})
        if cmd == "hosting:sites:list":
            return self.ok({"sites": [{"name": f"projects/{proj}/sites/{s}"}
                                      for s in self.sites]})
        if cmd == "deploy" and "auth" in args:
            cfg = json.loads(Path(args[args.index("--config") + 1]).read_text())
            self.auth_config = cfg["auth"]["providers"]["googleSignIn"]
            return 0, "Auth providers enabled: Google sign-in", ""
        raise AssertionError(f"unexpected CLI call {args}")


class FakeSession:
    uid = "UID-1"
    email = "priya.k@example.com"

    def __init__(self, config):
        self.config, self.signed_in, self.started = config, False, None

    def start(self, site_url):
        self.started = site_url
        self.signed_in = True               # the person clicks Continue
        return {"url": f"{site_url}/connect/?port=1&state=s", "error": ""}


def live(overrides=None):
    def http(url):
        codes = {"/connect/": 200, "/documents/users": 403,
                 "/documents/shares": 403}
        codes.update(overrides or {})
        return next(v for k, v in codes.items() if url.endswith(k))
    return http


@pytest.fixture
def fb_bin(tmp_path):
    p = tmp_path / "firebase"
    p.write_text("#!/bin/sh\n")
    return str(p)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in ("ALTO_FIREBASE_SITE", "ALTO_FIREBASE_PROJECT",
              "ALTO_FIREBASE_CONFIG", "ALTO_FIREBASE_BIN", "ALTO_STORE",
              "ALTO_SITE_MANAGED"):
        monkeypatch.delenv(k, raising=False)


def make(fake, fb_bin, http=None, **kw):
    statuses = []

    def login():
        def done():
            fake.logged_in = True
            return True
        return "https://accounts.google.com/o/oauth2/auth?x", done

    p = pv.Provisioner(run=fake, http=http or live(),
                       opener=fake.opened.append,
                       debug_reason=lambda: fake.log_reason,
                       login=login, session_factory=FakeSession,
                       deploy=lambda: fake.calls.append(["<deploy site+rules>"]),
                       migrate=lambda s: {"projects": 1, "timelines": 2,
                                          "nodes": 30, "skipped": 0},
                       sleep=lambda s: statuses.append(p.state.get("status")),
                       api=fake.api, **kw)
    p._token = lambda: "TOKEN"
    p.state["firebase_bin"] = fb_bin          # tools step: already installed
    p.statuses = statuses
    return p


# ── the whole run ───────────────────────────────────────────────────────────

def test_a_new_user_ends_with_a_ready_private_site(fb_bin):
    fake = FakeFirebase()
    p = make(fake, fb_bin)
    p._drive()
    st = p.status()
    assert st["status"] == "ready", st
    pid = st["project"]
    assert pid.startswith("priya-k-alto-") and len(pid) <= 30
    assert st["site_url"] == f"https://{pid}.web.app"
    # Firestore, the web app, Google sign-in and the rules+site deploy all ran.
    assert fake.dbs == ["(default)"]
    assert fake.apps and fake.apps[0]["displayName"] == "Alto"
    assert fake.auth_config["supportEmail"] == "priya.k@example.com"
    # the API adds the project's own handler; naming it is refused as a duplicate
    assert "authorizedRedirectUris" not in fake.auth_config
    order = [c[0] for c in fake.calls]
    assert order.index("deploy") < order.index("<deploy site+rules>")
    # Recorded, and applied: every other code path now sees the site.
    rec = site_rec.load()
    assert site_rec.ready(rec) and rec["config"]["apiKey"] == "AIza-new"
    assert os.environ["ALTO_FIREBASE_SITE"] == pid
    assert json.loads(os.environ["ALTO_FIREBASE_CONFIG"])["projectId"] == pid
    assert rec["migrated"]["timelines"] == 2
    if os.name != "nt":                       # POSIX permissions only
        assert oct(site_rec.path().stat().st_mode)[-3:] == "600"


def test_the_person_is_told_what_to_click_while_it_waits(fb_bin):
    fake = FakeFirebase()
    p = make(fake, fb_bin)
    seen = []

    def login():
        n = {"i": 0}

        def done():
            n["i"] += 1
            seen.append((p.state["status"], p.state.get("url")))
            fake.logged_in = n["i"] > 2
            return fake.logged_in
        return "https://accounts.google.com/o/oauth2/auth?x", done

    p.login_starter = login
    p._drive()
    assert seen[0] == ("waiting_for_google",
                       "https://accounts.google.com/o/oauth2/auth?x")
    assert p.status()["status"] == "ready"


def test_a_taken_project_id_is_retried(fb_bin):
    fake = FakeFirebase(taken=2)
    p = make(fake, fb_bin)
    p._drive()
    assert p.status()["status"] == "ready"
    assert sum(c[0] == "projects:create" for c in fake.calls) == 3


def test_google_terms_become_a_browser_step(fb_bin):
    """2026-09-28, a real new account: every projects:create failed with only
    "Failed to create project. See firebase-debug.log" — Google's "Callers
    must accept Terms of Service" was in the log alone, so the terms were never
    detected and the user got five identical generic errors."""
    fake = FakeFirebase(tos=True)
    p = make(fake, fb_bin)
    p._drive()
    st = p.status()
    assert st["status"] == "needs_browser_step", st
    url = "https://console.cloud.google.com/?authuser=priya.k%40example.com"
    assert st["url"] == url and fake.opened[-1] == url   # opened, as the account
    assert "Google Cloud" in st["message"] and "Agree" in st["message"]
    assert sum(c[0] == "projects:create" for c in fake.calls) == 1  # no retry loop
    assert not site_rec.ready()
    # Accepted: the next call carries on and finishes.
    fake.tos = False
    p._drive()
    assert p.status()["status"] == "ready"


def test_the_real_cli_log_yields_the_reason(tmp_path, monkeypatch):
    monkeypatch.setenv("ALTO_TOOLS_DIR", str(tmp_path))
    (tmp_path / "firebase-debug.log").write_text(
        '[debug] Command: node firebase.js projects:list\n'
        '[debug] <<< [apiv2][body] GET https://firebase.googleapis.com/v1beta1/projects {}\n'
        '[debug] Command: node firebase.js projects:create x --json\n'
        '[debug] >>> [apiv2][body] POST https://cloudresourcemanager.googleapis.com/v1/projects {"projectId":"x"}\n'
        '[debug] <<< [apiv2][body] GET https://cloudresourcemanager.googleapis.com/v1/operations/o '
        '{"name":"o","done":true,"error":{"code":9,"message":"Callers must accept Terms of Service"}}\n'
        '[debug] FirebaseError: Callers must accept Terms of Service\n'
        '[error] Error: Failed to create project. See firebase-debug.log for more info.\n')
    assert pv._debug_reason() == ("Callers must accept Terms of Service "
                                  "(cloudresourcemanager.googleapis.com)")


def test_the_same_failure_three_times_says_retrying_will_not_help(fb_bin):
    fake = FakeFirebase()
    p = make(fake, fb_bin)
    real = fake.__call__

    def broken(args, timeout=0):
        if args[0] == "firestore:databases:create":
            fake.calls.append(args)
            return fake.err("Failed to create database.")
        return real(args, timeout)
    p.run = broken
    fake.log_reason = "PERMISSION_DENIED (firestore.googleapis.com)"
    for i in range(3):
        p._drive()
        st = p.status()
        assert "PERMISSION_DENIED" in st["message"]      # the real reason, shown
        assert ("will not help" in st["message"]) == (i == 2)


def test_an_interrupted_setup_resumes_without_redoing_anything(fb_bin):
    fake = FakeFirebase(fail_once={"firestore:databases:create"})
    p = make(fake, fb_bin)
    p._drive()
    assert p.status()["status"] == "error"
    assert "creating Firestore failed" in p.status()["message"]
    assert "app" in site_rec.load()["done"]
    # A fresh process (the connector restarted) picks it up from site.json.
    p2 = make(fake, fb_bin)
    p2._drive()
    assert p2.status()["status"] == "ready"
    assert sum(c[0] == "projects:create" for c in fake.calls) == 1
    assert sum(c[0] == "apps:create" for c in fake.calls) == 1


def test_rules_that_are_not_live_fail_the_setup(fb_bin):
    fake = FakeFirebase()
    p = make(fake, fb_bin, http=live({"/documents/users": 200}))
    p._drive()
    st = p.status()
    assert st["status"] == "error"
    assert "safety check" in st["message"] and "users" in st["message"]
    assert not site_rec.ready()
    assert srv.store_mode() == "local"          # nothing switched over


# ── tools ───────────────────────────────────────────────────────────────────

def test_a_node_download_that_fails_its_checksum_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(pv, "node_platform", lambda: "darwin-arm64")
    p = pv.Provisioner(run=FakeFirebase(), download=lambda url: b"not node")
    with pytest.raises(pv.StepError, match="checksum"):
        p._tools()
    assert pv.managed_node() is None


def test_every_node_build_is_pinned():
    assert set(pv.NODE_SHA256) == {"darwin-arm64", "darwin-x64", "win-x64"}
    assert all(len(h) == 64 for h in pv.NODE_SHA256.values())
    assert pv.FIREBASE_TOOLS.count(".") == 2       # an exact version


# ── what the rest of Alto sees ──────────────────────────────────────────────

def test_store_mode_auto_follows_the_site(fb_bin, monkeypatch):
    monkeypatch.setenv("ALTO_STORE", "auto")
    assert srv.store_mode() == "local"
    make(FakeFirebase(), fb_bin)._drive()
    assert srv.store_mode() == "cloud"
    monkeypatch.setenv("ALTO_STORE", "local")       # an explicit choice wins
    assert srv.store_mode() == "local"
    monkeypatch.setenv("ALTO_STORE", "${user_config.store_mode}")
    assert srv.store_mode() == "cloud"


def test_typed_settings_are_never_overridden(fb_bin, monkeypatch):
    make(FakeFirebase(), fb_bin)._drive()
    monkeypatch.setenv("ALTO_FIREBASE_SITE", "my-alto")
    monkeypatch.setenv("ALTO_FIREBASE_PROJECT", "my-own-project")
    monkeypatch.setenv("ALTO_FIREBASE_CONFIG", '{"apiKey":"mine"}')
    site_rec.apply()
    assert os.environ["ALTO_FIREBASE_SITE"] == "my-alto"
    assert os.environ["ALTO_FIREBASE_CONFIG"] == '{"apiKey":"mine"}'


def test_a_half_built_site_is_never_applied(fb_bin):
    fake = FakeFirebase(fail_once={"deploy"})
    p = make(fake, fb_bin)
    p._drive()
    assert p.status()["status"] == "error"
    for k in ("ALTO_FIREBASE_SITE", "ALTO_FIREBASE_PROJECT"):
        os.environ.pop(k, None)
    assert site_rec.apply() is False
    assert "ALTO_FIREBASE_SITE" not in os.environ


def test_typed_settings_without_a_cli_adopt_that_project(fb_bin, monkeypatch):
    """Filled-in settings, no Firebase CLI: finish THAT project."""
    monkeypatch.setenv("ALTO_FIREBASE_SITE", "my-alto")
    monkeypatch.setenv("ALTO_FIREBASE_PROJECT", "my-alto")
    monkeypatch.setenv("ALTO_FIREBASE_BIN", "/nonexistent/firebase")
    fake = FakeFirebase()
    fake.projects.append("my-alto")
    fake.sites.append("my-alto")
    p = make(fake, fb_bin)
    p.kick = lambda code="", adopt=None: (
        p.state.update(site=adopt[0], project=adopt[1], adopted=True),
        p._drive())
    pv.set_provisioner(p)
    srv.set_up_site()
    assert not any(c[0] == "projects:create" for c in fake.calls)
    assert p.status()["status"] == "ready"
    assert json.loads(os.environ["ALTO_FIREBASE_CONFIG"])["apiKey"] == "AIza-new"


def test_guide_reports_the_site(fb_bin):
    assert srv.get_interview_guide()["site_status"]["status"] == "not_started"
    p = make(FakeFirebase(), fb_bin)
    pv.set_provisioner(p)
    p._drive()
    srv.set_store(None)
    from alto.store.local import LocalStore
    srv.set_store(LocalStore(Path(os.environ["ALTO_STORE_DIR"])))
    assert srv.get_interview_guide()["site_status"]["status"] == "ready"


def test_unconfigured_publish_points_at_set_up_site(tmp_path):
    from alto.store.local import LocalStore
    srv.set_store(LocalStore(tmp_path))
    pid = srv.create_project("C", "", "studying")["project_id"]
    tid = srv.create_timeline(pid, {"title": "C", "acts": [{"label": "A"},
                                                            {"label": "B"}]})["timeline_id"]
    srv.record_materials_consent(tid, [{"name": "notes"}], True)
    srv.add_nodes(tid, [{"id": "a", "act": 0, "tag": "x", "title": "A", "desc": "d"},
                        {"id": "b", "act": 1, "tag": "x", "title": "B", "desc": "d"}])
    srv.build_timeline(tid)
    os.environ["ALTO_PUBLISH_MODE"] = "firebase-static"
    try:
        r = srv.publish_timeline(tid, "private-web")
    finally:
        os.environ.pop("ALTO_PUBLISH_MODE")
    assert "set_up_site" in r["note"] and "README" not in r["note"]


def test_a_run_cut_off_mid_wait_resumes_as_paused(fb_bin):
    site_rec.save({"status": "waiting_for_google", "step": "login",
                   "url": "https://accounts.google.com/stale", "done": ["tools"],
                   "firebase_bin": fb_bin})
    p = pv.Provisioner()
    st = p.status()
    assert st["status"] == "paused" and "url" not in st
    fake = FakeFirebase()
    q = make(fake, fb_bin)
    q._drive()
    assert q.status()["status"] == "ready"


def test_the_services_a_new_project_lacks_are_switched_on_first(fb_bin):
    fake = FakeFirebase()
    p = make(fake, fb_bin)
    p._drive()
    assert p.status()["status"] == "ready"
    assert fake.enabled >= {"firestore.googleapis.com",
                            "firebaserules.googleapis.com",
                            "identitytoolkit.googleapis.com"}
    order = [c[0] for c in fake.calls]
    assert order.index("<api>") < order.index("firestore:databases:create")


def test_typed_settings_stay_configured_whatever_another_setup_left(
        fb_bin, monkeypatch, tmp_path):
    """site.json is per OS user, so a second Claude account's failed setup on
    the same Mac is visible to the first. Typed settings with a working CLI
    must still read as configured — never as a setup to resume or adopt."""
    site_rec.save({"status": "error", "step": "project", "email": "other@x",
                   "done": ["tools", "login"], "firebase_bin": fb_bin})
    pv.set_provisioner(None)
    cli = tmp_path / "firebase"
    cli.write_text("#!/bin/sh\n")
    monkeypatch.setenv("ALTO_FIREBASE_BIN", str(cli))
    monkeypatch.setenv("ALTO_FIREBASE_SITE", "my-alto")
    monkeypatch.setenv("ALTO_FIREBASE_PROJECT", "my-own-project")
    monkeypatch.setenv("ALTO_FIREBASE_CONFIG",
                       '{"apiKey":"k","projectId":"my-own-project","appId":"a"}')
    assert srv.get_interview_guide()["site_status"]["status"] == "configured"
    r = srv.set_up_site()
    assert r["status"] == "configured"
    assert pv.get_provisioner()._thread is None          # nothing started


# ── the user is never handed a chore ────────────────────────────────────────
# 2026-09-28: with only "See firebase-debug.log" to go on, the chat model had
# the user run `find` in a terminal. It has no access to their computer; every
# reply now says what to do next and carries the diagnostics itself.

CHORES = ("run a command", "find or send a file", "change a setting",
          "install anything", "Firebase or Google Cloud console")


@pytest.mark.parametrize("status", ["working", "waiting_for_google",
                                    "waiting_for_sign_in", "needs_browser_step",
                                    "needs_code", "error"])
def test_every_status_says_what_to_do_next(status):
    p = pv.Provisioner()
    p.state.update(status=status, message="m")
    nxt = p.status()["next"]
    if status != "working":
        assert all(c in nxt for c in CHORES), (status, nxt)


def test_an_error_carries_its_diagnostics_without_secrets(tmp_path, monkeypatch, fb_bin):
    monkeypatch.setenv("ALTO_TOOLS_DIR", str(tmp_path))
    (tmp_path / "firebase-debug.log").write_text(
        '[debug] [t] Command: node firebase.js projects:create x --json\n'
        '[debug] [t] >>> [apiv2][query] POST https://x.googleapis.com/v1/p?key=AIzaSECRETKEY1\n'
        '[debug] [t] Authorization: Bearer ya29.SECRETTOKEN\n'
        '[debug] [t] <<< [apiv2][status] POST https://x.googleapis.com/v1/p 403\n'
        '[debug] [t] <<< [apiv2][body] {"access_token":"ya29.SECRET2","error":{"code":7,"message":"Permission denied"}}\n'
        '[debug] [t] FirebaseError: Permission denied\n')
    p = pv.Provisioner()
    p._fail("error", "creating your Firebase project failed")
    st = p.status()
    assert "403" in st["details"] and "Permission denied" in st["details"]
    assert "SECRET" not in st["details"]
    assert st["log"] == str(tmp_path / "firebase-debug.log")
    for _ in range(2):
        p._fail("error", "creating your Firebase project failed")
    assert "Stop calling set_up_site" in p.status()["next"]


def test_the_guide_forbids_handing_the_user_chores():
    g = (ROOT / "alto" / "interview_guide.md").read_text(encoding="utf-8")
    assert "Never hand the user a technical task" in g
    doc = srv.set_up_site.__doc__ or ""
    assert "Never ask the user to run commands" in doc


def test_typed_settings_without_a_web_config_are_finished_not_left(fb_bin, monkeypatch, tmp_path):
    """Site and project typed in, config never pasted: set_up_site reads the
    config itself instead of calling the setup done."""
    cli = tmp_path / "firebase"
    cli.write_text("#!/bin/sh\n")
    monkeypatch.setenv("ALTO_FIREBASE_BIN", str(cli))
    monkeypatch.setenv("ALTO_FIREBASE_SITE", "my-alto")
    monkeypatch.setenv("ALTO_FIREBASE_PROJECT", "my-alto")
    assert srv.get_interview_guide()["site_status"]["status"] != "configured"


def test_private_publish_from_a_folder_writes_the_page_itself(tmp_path, monkeypatch):
    """Projects kept in a folder used to end private-web publishing with "open
    the link and upload this file yourself". Now: sign in once, and Alto
    writes the page into the account; nothing to upload."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cloudfake import FakeFirebase as FakeFirestore
    from alto import publish_static as ps
    from alto.cloud import session as sess
    from alto.store.local import LocalStore
    cli = tmp_path / "firebase"
    cli.write_text("#!/bin/sh\nexit 0\n")
    cli.chmod(0o755)
    cfg = '{"apiKey":"k","projectId":"proj","appId":"a"}'
    for k, v in {"ALTO_FIREBASE_BIN": str(cli), "ALTO_FIREBASE_SITE": "my-alto",
                 "ALTO_FIREBASE_PROJECT": "proj", "ALTO_FIREBASE_CONFIG": cfg,
                 "ALTO_STORE": "local", "ALTO_PUBLISH_MODE": "firebase-static",
                 "ALTO_ALLOW_STALE": "1"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(ps, "verify_live", lambda site, live: [])
    fs = FakeFirestore()
    opened = []
    s = sess.Session(json.loads(cfg), http=fs, path=tmp_path / "s.json",
                     opener=opened.append)
    sess.set_session(s)
    srv.set_store(LocalStore(tmp_path / "store"))
    try:
        pid = srv.create_project("C", "", "studying")["project_id"]
        tid = srv.create_timeline(pid, {"title": "C", "acts": [
            {"label": "A"}, {"label": "B"}]})["timeline_id"]
        srv.record_materials_consent(tid, [{"name": "notes"}], True)
        srv.add_nodes(tid, [{"id": "a", "act": 0, "tag": "x", "title": "A", "desc": "d"},
                            {"id": "b", "act": 1, "tag": "x", "title": "B", "desc": "d"}])
        srv.build_timeline(tid)
        first = srv.publish_timeline(tid, "private-web")
        assert first["status"] == "waiting_for_sign_in"
        assert opened and "/connect/" in opened[0]
        assert "upload" in first["next"] and "Never" in first["next"]
        s._accept("RT")                          # they clicked Continue with Google
        r = srv.publish_timeline(tid, "private-web")
        assert r["view_url"].startswith("https://my-alto.web.app/pv/")
        assert "upload_file" not in r and "Nothing to upload" in r["note"]
        assert any("/pages/" in k for k in fs.docs), list(fs.docs)[:5]
    finally:
        sess.set_session(None)
