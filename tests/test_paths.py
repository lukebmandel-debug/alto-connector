"""Path-traversal regressions.

A timeline_id reaches the filesystem (the local store) and the published site
tree, so a caller-supplied one must never contain a path separator. These
assert both layers independently: the MCP tool boundary rejects with a useful
error, and the store refuses regardless of what the boundary did.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.store.local import LocalStore, StorePathError, check_component  # noqa: E402

HOSTILE = [
    "../../../../tmp/pwned",
    "..",
    "../sibling",
    "a/b",
    "a\\b",
    "/etc/passwd",
    "with\x00nul",
    ".hidden",
    "..%2f..%2fetc",
    "-",
]


@pytest.mark.parametrize("bad", HOSTILE)
def test_check_component_rejects(bad):
    with pytest.raises(StorePathError):
        check_component(bad)


def test_check_component_allows_real_ids():
    for good in ("contracts-i", "doc.json", "lucy-v-zehmer.json", "_shares",
                 "offline.html", "local", "luke"):
        assert check_component(good) == good


@pytest.mark.parametrize("bad", HOSTILE)
def test_store_refuses_hostile_timeline_id(tmp_path, bad):
    st = LocalStore(tmp_path)
    with pytest.raises(StorePathError):
        st.put_timeline("local", bad, {"timeline_id": bad})
    with pytest.raises(StorePathError):
        st.get_timeline("local", bad)


def test_store_refuses_hostile_artifact_name(tmp_path):
    st = LocalStore(tmp_path)
    with pytest.raises(StorePathError):
        st.put_artifact("local", "contracts-i", "../../escape.html", "x")


def test_nothing_is_written_outside_the_store_root(tmp_path):
    """The property that actually matters: after a hostile run, the only files
    on disk are inside the root."""
    root = tmp_path / "store"
    outside = tmp_path / "canary"
    outside.mkdir()
    st = LocalStore(root)
    for bad in HOSTILE:
        for call in (lambda: st.put_timeline("local", bad, {}),
                     lambda: st.put_nodes("local", bad, [{"id": "n1"}]),
                     lambda: st.put_artifact("local", bad, "x.html", "x")):
            with pytest.raises(StorePathError):
                call()
    assert list(outside.iterdir()) == []
    for p in root.rglob("*"):
        assert root.resolve() in p.resolve().parents or p.resolve() == root.resolve()


# ── tool boundary ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", ["../../etc", "a/b", "..", "With Caps", ""])
def test_tool_boundary_rejects_bad_timeline_id(bad):
    from alto import mcp_server as srv
    _, err = srv._check_ref(bad, "timeline_id")
    assert err and err["error"] == "bad_id"


def test_tool_boundary_accepts_a_real_id():
    from alto import mcp_server as srv
    value, err = srv._check_ref("contracts-i", "timeline_id")
    assert err is None and value == "contracts-i"


def test_timeline_tools_reject_traversal(tmp_path, monkeypatch):
    """End to end through a tool: a hostile id must not reach the store."""
    from alto import mcp_server as srv
    srv.set_store(LocalStore(tmp_path))
    monkeypatch.setenv("ALTO_DEV_UID", "local")
    doc, err = srv._timeline_or_error("../../../../tmp/pwned")
    assert doc is None and err["error"] == "bad_id"


# ── size caps and fail-closed identity ───────────────────────────────────────

def test_oversized_field_is_rejected():
    import json
    from alto.build.builder import load_brief
    from alto.build.brief import BriefError, validate_brief, MAX_LEN
    d = json.loads((ROOT / "samples" / "contracts_brief.json").read_text(encoding="utf-8"))
    d["brief"]["title"] = "x" * (MAX_LEN["title"] + 1)
    b, _, _ = load_brief(d)
    with pytest.raises(BriefError, match="exceeds"):
        validate_brief(b)


def test_oversized_node_desc_is_rejected():
    import json
    from alto.build.builder import load_brief
    from alto.build.brief import BriefError, validate_brief, validate_nodes, MAX_LEN
    d = json.loads((ROOT / "samples" / "contracts_brief.json").read_text(encoding="utf-8"))
    d["nodes"][0]["desc"] = "x" * (MAX_LEN["desc"] + 1)
    b, nodes, _ = load_brief(d)
    validate_brief(b)
    with pytest.raises(BriefError, match="exceeds"):
        validate_nodes(b, nodes)


def test_uid_fails_closed_when_auth_is_required():
    """Importing alto.web flips this flag process-wide, which is correct in
    production (a process is either the stdio server or the web app) but leaks
    between test modules — so set both states explicitly here."""
    from alto import mcp_server as srv
    previous = srv._require_auth
    try:
        srv.require_auth(False)
        assert srv.uid()                  # stdio/local: a dev uid is fine
        srv.require_auth(True)
        with pytest.raises(srv.AuthError):
            srv.uid()
    finally:
        srv.require_auth(previous)


# ── no public pages ──────────────────────────────────────────────────────────

def test_publish_refuses_link():
    """Alto has no public visibility: a timeline reaches anyone but its owner
    only through a share link the owner creates from their homepage."""
    src = (ROOT / "alto" / "mcp_server.py").read_text(encoding="utf-8")
    assert "_share_slug" not in src
    # the tool (publish_timeline) wraps _publish_timeline, which holds the rule
    fn = src[src.index("def _publish_timeline("):]
    fn = fn[:fn.index("st = get_store()")]
    assert 'if visibility == "link":' in fn and '"link_removed"' in fn


def test_a_formerly_public_page_is_removed_on_the_next_publish(tmp_path):
    """A timeline stored as 'link' (published before public pages were
    removed) must not be served, and whatever the staged site still holds
    under /t/, /p/ and /offline.html from those days must be deleted, since the
    deploy uploads that whole directory."""
    import json
    from alto.publish_static import regenerate_site
    from alto.build.builder import load_brief, build_timeline
    from alto.build.single_file import bundle
    from alto.hosted import hosted_timeline

    st = LocalStore(tmp_path / "store")
    d = json.loads((ROOT / "samples" / "contracts_brief.json").read_text(encoding="utf-8"))
    b, nodes, conns = load_brief(d)
    html, _ = build_timeline(b, nodes, conns)
    tid, slug = b.timeline_id, "contracts-i-ab23cd45"
    st.put_artifact("local", tid, "hosted.html", hosted_timeline(html, tid))
    st.put_artifact("local", tid, "offline.html", bundle(b, html))
    st.put_timeline("local", tid, {
        "timeline_id": tid, "project_id": "", "brief": d["brief"],
        "status": "published", "visibility": "link", "share_slug": slug})

    site = tmp_path / "site"
    for rel in (f"t/{slug}", "p/proj"):
        (site / rel).mkdir(parents=True)
        (site / rel / "index.html").write_text(html, encoding="utf-8")
    (site / "offline.html").write_text(html, encoding="utf-8")

    regenerate_site(st, "local", site)
    assert not (site / "t").exists(), "a public page survived"
    assert not (site / "p").exists()
    assert not (site / "offline.html").exists()
    home = (site / "index.html").read_text(encoding="utf-8")
    assert b.title not in home


# ── first run without Claude Desktop ──────────────────────────────────────────

def test_default_store_is_somewhere_a_person_would_look(monkeypatch):
    """A user installing via uvx sets no environment at all. The finished
    timeline has to land somewhere they can find — the old default was
    ~/.alto-connector-dev, hidden and named for a developer.

    Asserts on store_dir() rather than get_store(): constructing a LocalStore
    would mkdir the path, and an earlier version of this test duly created a
    real ~/Documents/Alto on the machine running it."""
    from pathlib import Path as P
    from alto import mcp_server as srv
    monkeypatch.delenv("ALTO_STORE_DIR", raising=False)
    root = P(srv.store_dir())
    assert not root.name.startswith("."), f"{root} is hidden"
    assert "dev" not in root.name.lower(), f"{root} is named for a developer"
    assert root == P.home() / "Documents" / "Alto"


def test_unexpanded_mcpb_placeholder_never_becomes_a_path(monkeypatch):
    """Observed on a real install (2026-08-12): Claude Desktop passed the
    .mcpb user_config default through verbatim, so ALTO_STORE_DIR arrived as
    the literal '${HOME}/Documents/Alto'. LocalStore then tried to mkdir
    '${HOME}' at the filesystem root and every tool failed with EROFS."""
    from pathlib import Path as P
    from alto import mcp_server as srv
    home = P.home() / "Documents" / "Alto"

    # HOME present: expand it properly rather than trusting the client.
    monkeypatch.setenv("ALTO_STORE_DIR", "${HOME}/Documents/Alto")
    assert P(srv.store_dir()) == home

    # HOME absent: unresolvable placeholder must fall back, never be a path.
    monkeypatch.delenv("HOME", raising=False)
    got = srv.store_dir()
    assert "$" not in got and "{" not in got, got

    monkeypatch.setenv("ALTO_STORE_DIR", "~/Documents/Alto")
    assert "~" not in srv.store_dir()


def test_the_suite_never_writes_to_the_real_store(monkeypatch):
    """conftest points ALTO_STORE_DIR at a temp dir for every test; this is
    the canary if that fixture is ever removed."""
    import os
    from pathlib import Path as P
    configured = os.environ.get("ALTO_STORE_DIR")
    assert configured, "conftest should always set ALTO_STORE_DIR"
    assert P.home() / "Documents" / "Alto" != P(configured)


def test_default_uid_is_not_dev():
    """It becomes a directory name inside the user's store."""
    import os
    from alto import mcp_server as srv
    previous = os.environ.pop("ALTO_DEV_UID", None)
    try:
        assert srv.uid() == "local"
    finally:
        if previous is not None:
            os.environ["ALTO_DEV_UID"] = previous


def test_publish_without_firebase_explains_the_offline_file(tmp_path, monkeypatch):
    """Ending with a bare path leaves the user guessing. The response must say
    the offline file IS the timeline and how to open it."""
    import json
    from alto import mcp_server as srv
    from alto.build.builder import load_brief, build_timeline
    from alto.build.single_file import bundle

    monkeypatch.delenv("ALTO_PUBLISH_MODE", raising=False)
    monkeypatch.delenv("ALTO_PUBLIC_BASE", raising=False)
    monkeypatch.setenv("ALTO_DEV_UID", "local")
    st = LocalStore(tmp_path)
    srv.set_store(st)
    try:
        d = json.loads((ROOT / "samples" / "contracts_brief.json").read_text(
            encoding="utf-8"))
        b, nodes, conns = load_brief(d)
        html, _ = build_timeline(b, nodes, conns)
        tid = b.timeline_id
        st.put_artifact("local", tid, "offline.html", bundle(b, html))
        st.put_timeline("local", tid, {
            "timeline_id": tid, "project_id": "", "brief": d["brief"],
            "consent": {"granted": True}, "status": "built",
            "visibility": "private"})

        out = srv.publish_timeline(tid, "private")
        assert "offline_path" in out, out
        note = out.get("note", "").lower()
        assert "complete timeline" in note or "the complete" in note, out
        assert "browser" in note, "does not say how to open it"
        assert out["offline_path"].endswith("offline.html")
    finally:
        srv.set_store(None)
