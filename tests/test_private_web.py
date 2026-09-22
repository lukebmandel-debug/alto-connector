"""visibility='private-web': a timeline only the publishing account can open.

The page is not on the web at all — the site carries a sign-in shell, and the
page itself lives in Firestore under the owner's uid, where the existing rule
    match /users/{uid}/{document=**} { allow read: request.auth.uid == uid }
decides who may read it. So the thing worth testing hardest is the negative:
that nothing published for a private timeline says anything about it. A leak
here is silent — the feature still appears to work perfectly.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import load_brief, build_timeline  # noqa: E402
from alto.build.private_shell import shell  # noqa: E402
from alto.build.single_file import private_page  # noqa: E402
from alto.publish_static import (  # noqa: E402
    _private_web, _published, regenerate_site)
from alto.store.local import LocalStore  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"
KEY = "czckq4utebcx5rvgdptrgt"          # shaped like a real _private_key()


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    """Publishing a private timeline needs a Firebase project — without one
    there is nothing to sign into, and regenerate_site refuses (see
    test_publishing_a_private_timeline_without_sign_in_is_refused)."""
    monkeypatch.setenv("ALTO_FIREBASE_CONFIG", json.dumps(
        {"apiKey": "test-key", "projectId": "test-project", "appId": "test-app"}))


@pytest.fixture(scope="module")
def built():
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    b, nodes, conns = load_brief(d)
    html, _ = build_timeline(b, nodes, conns)
    return d, b, html


def _store(tmp_path, built, visibility="private-web", key=KEY):
    d, b, html = built
    st = LocalStore(tmp_path / "store")
    st.put_artifact("local", b.timeline_id, "timeline.html", html)
    doc = {"timeline_id": b.timeline_id, "project_id": "", "brief": d["brief"],
           "status": "published", "visibility": visibility}
    if visibility == "private-web":
        doc["private_key"] = key
    else:
        doc["share_slug"] = f"{b.timeline_id}-ab23cd45"
    st.put_timeline("local", b.timeline_id, doc)
    return st, doc


# ── the key ─────────────────────────────────────────────────────────────────

def test_the_private_key_says_nothing_about_the_timeline():
    """/t/{slug}/ keeps the timeline id so a shared link reads well. For a
    private page that same courtesy would announce the subject in the URL."""
    from alto.mcp_server import _private_key
    keys = {_private_key() for _ in range(50)}
    assert len(keys) == 50, "keys are not unique"
    for k in keys:
        assert re.fullmatch(r"[abcdefghijkmnpqrstuvwxyz23456789]{22}", k), k
        assert "contracts" not in k


def test_publish_rejects_an_unknown_visibility():
    from alto import mcp_server as M
    assert "private-web" in M.publish_timeline.__doc__


# ── the shell leaks nothing ─────────────────────────────────────────────────

def test_the_shell_is_the_same_for_every_private_timeline():
    """It takes no arguments at all — it works out which timeline it is showing
    from its own URL, so there is nothing in it to leak."""
    assert shell() == shell()
    assert len(shell()) < 20_000, "shell should be tiny"


def test_the_shell_carries_no_timeline_content(tmp_path, built):
    d, b, html = built
    st, doc = _store(tmp_path, built)
    site = tmp_path / "site"
    regenerate_site(st, "local", site)

    page = (site / "pv" / KEY / "index.html").read_text(encoding="utf-8")
    for label, needle in [("title", b.title), ("timeline id", b.timeline_id),
                          ("its own key", KEY)]:
        assert needle not in page, f"shell leaks the {label}"
    # and no node text
    first_node = d["nodes"][0]["title"]
    assert first_node not in page, "shell leaks node content"


def test_the_shell_asks_search_engines_to_stay_away():
    assert 'name="robots" content="noindex, nofollow"' in shell()


def test_the_shell_resolves_its_state_even_when_sync_is_unconfigured():
    """alto-cloud.js returns early, before ever calling renderAccount, when the
    publisher has no Firebase project. Without a fallback the page sits on
    'Checking your account' forever on exactly the sites least able to say why."""
    s = shell()
    assert "window.addEventListener('load'" in s
    assert "if(!c || !c.enabled) window.renderAccount();" in s


# ── it stays off the public site ────────────────────────────────────────────

def test_a_private_timeline_is_not_on_the_homepage(tmp_path, built):
    """Everything _published() returns reaches build_home(). A private entry
    there would leak its title AND its capability URL."""
    d, b, html = built
    st, doc = _store(tmp_path, built)
    assert _published(st, "local") == []
    assert [t["timeline_id"] for t in _private_web(st, "local")] == [b.timeline_id]

    site = tmp_path / "site"
    regenerate_site(st, "local", site)
    home = (site / "index.html").read_text(encoding="utf-8")
    block = home[home.index("const PROJECTS = ["):]
    block = block[:block.index("\n];")]
    assert b.timeline_id not in block
    assert b.title not in block


def test_no_timeline_page_is_written_for_a_private_timeline(tmp_path, built):
    d, b, html = built
    st, doc = _store(tmp_path, built)
    site = tmp_path / "site"
    regenerate_site(st, "local", site)
    assert not (site / "t" / b.timeline_id).exists()
    assert list((site / "pv").iterdir()) != []


def test_private_shells_prune_on_their_own_key_set(tmp_path, built):
    """The /t prune is driven by link-visible timelines. Sharing that set would
    delete every shell on each publish; not pruning at all would leave a
    revoked timeline reachable."""
    d, b, html = built
    st, doc = _store(tmp_path, built)
    site = tmp_path / "site"
    regenerate_site(st, "local", site)
    assert (site / "pv" / KEY / "index.html").exists()

    stale = site / "pv" / "aaaaaaaaaaaaaaaaaaaaaa"
    stale.mkdir(parents=True)
    (stale / "index.html").write_text("old", encoding="utf-8")

    regenerate_site(st, "local", site)
    assert (site / "pv" / KEY).exists(), "live shell was pruned"
    assert not stale.exists(), "revoked shell survived"


def test_revoking_removes_the_shell(tmp_path, built):
    d, b, html = built
    st, doc = _store(tmp_path, built)
    site = tmp_path / "site"
    regenerate_site(st, "local", site)
    assert (site / "pv" / KEY).exists()

    doc["visibility"] = "private"
    st.put_timeline("local", b.timeline_id, doc)
    regenerate_site(st, "local", site)
    assert not (site / "pv" / KEY).exists(), "revoked shell still on disk"


# ── the uploaded page ───────────────────────────────────────────────────────

def test_the_uploaded_page_is_self_contained(tmp_path, built):
    """It is delivered by srcdoc, where relative URLs resolve against
    about:srcdoc and fetch nothing. Anything external is simply broken."""
    d, b, html = built
    page = private_page(b, html)
    assert re.findall(r"<script[^>]*\ssrc=", page) == []
    assert re.findall(r"<link[^>]*\shref=", page) == []
    assert "function initLayout(" in page, "engine missing"


def test_the_uploaded_page_is_regenerated_at_publish_time(tmp_path, built):
    """A timeline built before private.html existed has no such artifact, and
    one built long ago predates current engine fixes."""
    d, b, html = built
    st, doc = _store(tmp_path, built)
    assert st.get_artifact("local", b.timeline_id, "private.html") is None
    regenerate_site(st, "local", tmp_path / "site")
    page = st.get_artifact("local", b.timeline_id, "private.html")
    assert page and "function initLayout(" in page


def test_the_uploaded_page_fits_a_firestore_document(tmp_path, built):
    """Firestore caps a document at 1 MiB and the shell refuses past 900 KB."""
    from alto.build.private_shell import MAX_PAGE_BYTES
    d, b, html = built
    assert len(private_page(b, html).encode()) < MAX_PAGE_BYTES


def test_publishing_a_private_timeline_without_sign_in_is_refused(tmp_path, built, monkeypatch):
    """A private timeline is opened by signing in. With no Firebase project
    there is nothing to sign into, so the shell would be a locked door with no
    key — and this is silent: the deploy succeeds and the page simply never
    opens, for anyone, including the owner."""
    from alto.publish_static import PublishError
    monkeypatch.delenv("ALTO_FIREBASE_CONFIG", raising=False)
    d, b, html = built
    st, doc = _store(tmp_path, built)
    with pytest.raises(PublishError, match="private-web"):
        regenerate_site(st, "local", tmp_path / "site")


def test_a_configured_site_publishes_the_private_timeline(tmp_path, built):
    d, b, html = built
    st, doc = _store(tmp_path, built)
    site = regenerate_site(st, "local", tmp_path / "site")
    assert (site / "pv" / KEY / "index.html").exists()


def test_a_refused_sign_in_leaves_the_button_usable_and_says_why():
    """signIn() rejects on a refused popup. The first version swallowed that
    and left the button disabled, so the window blinked shut, nothing was
    explained, and there was no way to try again."""
    s = shell()
    assert "c.signIn().catch(function(e){" in s
    assert "btn.disabled = false;" in s
    assert "auth/unauthorized-domain" in s
    assert "auth/popup-closed-by-user" in s


def test_signing_out_puts_the_page_back_behind_the_gate():
    """Rewriting the gate's text is not enough: render() hid the gate and put
    the frame on top, so without lock() the timeline stays on screen after a
    sign-out — and a hidden iframe still holds every word of it."""
    s = shell()
    assert "function lock(){" in s
    assert "stage.srcdoc = '';" in s, "the page must leave the DOM, not just hide"
    assert "gate.classList.remove('off');" in s
    assert "if(!cloud.user){ lock(); signedOut(); return; }" in s


def test_the_framed_page_offers_no_sign_out_that_does_nothing(built):
    """The engine's account panel would clear a localStorage key, change
    nothing about Firebase, and leave the timeline up."""
    d, b, html = built
    assert "#account-btn{display:none !important}" in private_page(b, html)
