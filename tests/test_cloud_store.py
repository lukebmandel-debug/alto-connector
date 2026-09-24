"""Projects in the user's own Firestore, reached as the user (alto/store/cloud.py,
alto/cloud/session.py). A fake speaks just enough of the Firestore REST and
secure-token APIs for the whole MCP flow to run against it."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.parse
from pathlib import Path

import pytest

from alto.cloud.meta import meta_of
from alto.cloud.session import CloudError, Session, SignInRequired
from alto.store.cloud import API, CloudStore
from alto.store.local import LocalStore

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cloudfake import FakeFirebase  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CFG = {"apiKey": "k", "projectId": "proj", "appId": "a"}


@pytest.fixture
def fake(tmp_path):
    return FakeFirebase()


@pytest.fixture
def session(fake, tmp_path):
    s = Session(CFG, http=fake, path=tmp_path / "cfg" / "session-proj.json",
                opener=lambda u: None)
    s._accept("RT")
    return s


@pytest.fixture
def cloud(session, tmp_path):
    return CloudStore(session, LocalStore(tmp_path / "local"))


# ── session ─────────────────────────────────────────────────────────────────

def test_signed_out_tools_say_how_to_sign_in(fake, tmp_path):
    s = Session(CFG, http=fake, path=tmp_path / "s.json")
    with pytest.raises(SignInRequired, match="sign_in tool"):
        s.uid


def test_the_refresh_token_is_private_to_this_user(session):
    assert session.uid == "U1" and session.email == "me@example.com"
    if os.name != "nt":          # Windows has no POSIX mode bits to check
        assert os.stat(session.path).st_mode & 0o777 == 0o600


def test_a_revoked_token_asks_to_sign_in_again(session, fake):
    fake.good_rt = "other"
    with pytest.raises(SignInRequired, match="sign in again"):
        session.id_token(force=True)


def test_the_loopback_checks_state_and_takes_the_token(fake, tmp_path):
    import urllib.request
    opened = []
    s = Session(CFG, http=fake, path=tmp_path / "s.json", opener=opened.append)
    p = s.start("https://site.web.app")
    assert opened[0].startswith("https://site.web.app/connect/?port=")
    url = f"http://127.0.0.1:{p['port']}/cb"
    bad = urllib.request.Request(url, data=b"state=nope&rt=RT", method="POST")
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen(bad, timeout=5)
    assert not s.signed_in
    body = urllib.parse.urlencode({"state": p["state"], "rt": "RT"}).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=body, method="POST"), timeout=5) as r:
        assert b"connected" in r.read()
    assert s.signed_in and s.uid == "U1"


# ── store ───────────────────────────────────────────────────────────────────

def test_documents_round_trip_including_nested_arrays(cloud):
    cloud.put_project("U1", "p1", {"project_id": "p1", "name": "Civ Pro", "created": "2"})
    cloud.put_project("U1", "p0", {"project_id": "p0", "name": "Torts", "created": "1"})
    assert [p["name"] for p in cloud.list_projects("U1")] == ["Torts", "Civ Pro"]
    cloud.put_connections("U1", "t1", [["a", "b", "cites"], ["b", "c", "overrules"]])
    assert cloud.get_connections("U1", "t1") == [["a", "b", "cites"], ["b", "c", "overrules"]]
    assert cloud.get_timeline("U1", "missing") is None


def test_nodes_keep_their_order_and_upsert(cloud):
    cloud.put_nodes("U1", "t1", [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}])
    cloud.put_nodes("U1", "t1", [{"id": "c", "title": "C"}, {"id": "a", "title": "A2"}])
    ns = cloud.list_nodes("U1", "t1")
    assert [(n["id"], n["_seq"]) for n in ns] == [("a", 1), ("b", 2), ("c", 3)]
    assert ns[0]["title"] == "A2"
    cloud.delete_nodes("U1", "t1", ["b"])
    assert [n["id"] for n in cloud.list_nodes("U1", "t1")] == ["a", "c"]


def test_artifacts_stay_on_this_computer(cloud, fake, tmp_path):
    path = cloud.put_artifact("U1", "t1", "timeline.html", "<html>")
    assert Path(path).is_file() and str(tmp_path / "local") in path
    assert not any("artifact" in n for n in fake.docs)


def test_a_private_page_is_written_the_way_the_browser_writes_it(cloud, fake):
    fake.docs["projects/proj/databases/(default)/documents/users/U1/pagemeta/k1"] = {
        "shareKey": {"stringValue": "S"}}
    meta = {"title": "P", "heading": "H", "project": "P", "tid": "t1",
            "units": ["#fff"], "search": [{"id": "a", "t": "A", "d": "d"}], "v": 1}
    cloud.put_page("U1", "k1", "<html>", "P", meta)
    base = "projects/proj/databases/(default)/documents/users/U1"
    assert fake.docs[f"{base}/pages/k1"]["html"] == {"stringValue": "<html>"}
    pm = fake.docs[f"{base}/pagemeta/k1"]
    assert pm["shareKey"] == {"stringValue": "S"}, "the share link survives a republish"
    assert "timestampValue" in pm["updatedAt"]
    assert fake.docs[base]["pagemetaV"] == {"integerValue": "1"}


# ── the whole MCP flow, on the cloud store ─────────────────────────────────

def test_the_mcp_flow_runs_on_the_cloud_store(cloud, session, monkeypatch):
    import alto.mcp_server as srv
    from alto.cloud import session as sess
    srv.set_store(cloud)
    sess.set_session(session)
    monkeypatch.setenv("ALTO_STORE", "cloud")
    try:
        assert srv.uid() == "U1"
        srv.create_project(name="Civil Procedure — Priya", purpose="exam", kind="studying")
        lp = srv.list_projects()
        assert [p["name"] for p in lp["projects"]] == ["Civil Procedure — Priya"]
        assert "another device" not in lp.get("note", "")
    finally:
        sess.set_session(None)
        srv.set_store(None)


# ── the two listing-record writers agree ────────────────────────────────────

PAGES = sorted(Path.home().glob("Documents/Alto/luke/timelines/*/artifacts/private.html"))


@pytest.mark.skipif(not PAGES or not shutil.which("node"), reason="needs real pages + node")
@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.parent.parent.name)
def test_python_and_browser_listing_records_match(page, tmp_path):
    js = (ROOT / "alto" / "cloud" / "alto-cloud.js").read_text(encoding="utf-8")
    a, b = js.index("  const META_V"), js.index("  async function _getPageMeta")
    idf = js[js.index("  function _identityOf"):js.index("  function _reidentify")]
    runner = tmp_path / "m.js"
    runner.write_text(
        "const fs=require('fs');const f=new Function(" + json.dumps(js[a:b] + idf + "; return _metaOf;")
        + ")();process.stdout.write(JSON.stringify(f(fs.readFileSync(process.argv[2],'utf8'))));")
    out = subprocess.check_output(["node", str(runner), str(page)])
    assert json.loads(out) == meta_of(page.read_text(encoding="utf-8"))


def test_python_listing_record_reads_a_built_page():
    html = ("<title>Civil Procedure — Alto Timeline</title>"
            '<meta name="alto-label" content="Civil Procedure &amp; More">'
            "var COURSE_ID = 'cp';\nconst PHASE_META = [\n{colorRaw:'#4a9eff'},{colorRaw:'#e8a87c'}\n];"
            "\nconst NODES_SRC=[\n{id:'a', title:'Int\\'l Shoe', desc:'min contacts'}\n];")
    m = meta_of(html)
    assert m["project"] == "Civil Procedure & More" and m["heading"] == "Civil Procedure"
    assert m["units"] == ["#4a9eff", "#e8a87c"] and m["tid"] == "cp"
    assert m["search"] == [{"id": "a", "t": "Int'l Shoe", "d": "min contacts"}]
