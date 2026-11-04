"""An older Alto must never quietly overwrite what a newer Alto built (Luke, L-1103-004328).

Three guards, all tested here without any network or real publish:
  - the out-of-date warning on build and publish results,
  - the engine stamp on built pages and the refusal to publish an older page over a newer one,
  - the private shell's file-upload control no longer called "Update".
"""
import base64
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from alto import update_check                                             # noqa: E402
from alto.build import engine_stamp as E                                   # noqa: E402
from alto.build.private_shell import shell, unpack_page                    # noqa: E402
from alto.cloud.session import Session                                     # noqa: E402
from alto.store.cloud import CloudStore                                    # noqa: E402
from alto.store.local import LocalStore                                    # noqa: E402
from cloudfake import FakeFirebase                                         # noqa: E402

CFG = {"apiKey": "k", "projectId": "proj", "appId": "a"}
BASE = "projects/proj/databases/(default)/documents/users/U1"
META = {"title": "P", "heading": "H", "project": "P", "tid": "t1", "units": [], "search": [], "v": 1}


def page(engine=None):
    tag = E.engine_meta_tag(engine) if engine else ""
    return f"<html><head>{tag}</head><body>x</body></html>"


@pytest.fixture
def fake():
    return FakeFirebase()


@pytest.fixture
def cloud(fake, tmp_path):
    s = Session(CFG, http=fake, path=tmp_path / "cfg" / "session-proj.json", opener=lambda u: None)
    s._accept("RT")
    return CloudStore(s, LocalStore(tmp_path / "local"))


@pytest.fixture
def check(monkeypatch):
    """The update check switched on, GitHub replaced: set check.latest to what the 'release' says."""
    monkeypatch.delenv("ALTO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr(E, "running_version", lambda: "1.9.187")
    monkeypatch.setattr(update_check, "running_version", lambda: "1.9.187")

    class C:
        latest = "1.9.211"
        calls = 0
    c = C()

    def fake_fetch():
        c.calls += 1
        if isinstance(c.latest, Exception):
            return ""                        # the real _fetch_latest swallows every failure and returns ''
        return c.latest
    monkeypatch.setattr(update_check, "_fetch_latest", fake_fetch)
    update_check.reset_for_tests()
    yield c
    update_check.reset_for_tests()


# ── the out-of-date warning ─────────────────────────────────────────────────

def test_an_older_extension_gets_the_warning(check):
    note = update_check.update_note()
    assert note.startswith("This Alto extension is 1.9.187, the latest is 1.9.211. Update it before editing pages: ")
    assert "alto-get.web.app" in note


def test_the_warning_leads_a_build_or_publish_result(check):
    out = update_check.with_update_note({"verify": "passed"})
    assert list(out)[0] == "update_alto" and out["verify"] == "passed"
    assert "1.9.211" in out["update_alto"]


@pytest.mark.parametrize("latest", ["1.9.187", "1.9.150", ""])
def test_current_or_newer_gets_no_warning(check, latest):
    check.latest = latest
    assert update_check.update_note() == ""
    assert update_check.with_update_note({"a": 1}) == {"a": 1}


def test_a_network_failure_is_silent(check):
    check.latest = RuntimeError("offline")
    assert update_check.update_note() == ""
    assert update_check.with_update_note({"a": 1}) == {"a": 1}


def test_the_real_fetch_swallows_errors(monkeypatch):
    def boom(*a, **k):
        raise OSError("no network")
    monkeypatch.setattr(update_check.urllib.request, "urlopen", boom)
    assert update_check._fetch_latest() == ""


def test_the_release_is_asked_for_once_per_session(check):
    for _ in range(4):
        update_check.update_note()
    assert check.calls == 1


# ── the engine stamp and the no-downgrade refusal ───────────────────────────

def test_built_private_pages_carry_the_engine_stamp():
    import json
    from alto.build.builder import build_timeline, load_brief
    from alto.build.single_file import private_page
    d = json.loads((ROOT / "samples" / "contracts_brief.json").read_text(encoding="utf-8"))
    b, nodes, conns = load_brief(d)
    html, _ = build_timeline(b, nodes, conns)
    built = private_page(b, html)
    from alto.mcp_server import __version__
    assert E.page_engine(built) == __version__


def test_version_order_is_numeric_not_textual():
    assert E.is_older("1.9.99", "1.9.100")
    assert not E.is_older("1.9.211", "1.9.211")
    assert not E.is_older("1.9.211", "1.9.99")
    assert not E.is_older("junk", "1.9.1")


@pytest.mark.parametrize("existing, new, ok", [
    ("1.9.300", "1.9.211", False),      # existing built by a newer Alto: refuse
    ("1.9.211", "1.9.211", True),       # equal
    ("1.9.200", "1.9.211", True),       # older
    (None, "1.9.211", True),            # no stamp: predates stamps
])
def test_check_no_downgrade(existing, new, ok):
    if ok:
        E.check_no_downgrade(page(existing), page(new))
    else:
        with pytest.raises(E.StaleEngineError) as ei:
            E.check_no_downgrade(page(existing), page(new))
        assert "Update the Alto extension first" in str(ei.value)


def test_publishing_over_a_newer_page_is_refused_and_leaves_it_alone(cloud, fake):
    cloud.put_page("U1", "k", page("1.9.300"), "P", META)
    with pytest.raises(E.StaleEngineError):
        cloud.put_page("U1", "k", page("1.9.211"), "P", META)
    stored = unpack_page(base64.b64decode(fake.docs[f"{BASE}/pages/k"]["z"]["bytesValue"]))
    assert E.page_engine(stored) == "1.9.300"


def test_equal_older_and_unstamped_pages_are_replaced(cloud, fake):
    for i, (before, after) in enumerate((("1.9.211", "1.9.211"), ("1.9.200", "1.9.211"), (None, "1.9.211"))):
        k = f"k{i}"
        cloud.put_page("U1", k, page(before), "P", META)
        cloud.put_page("U1", k, page(after), "P", META)
        stored = unpack_page(base64.b64decode(fake.docs[f"{BASE}/pages/{k}"]["z"]["bytesValue"]))
        assert E.page_engine(stored) == after


def test_a_first_publish_has_nothing_to_compare(cloud):
    cloud.put_page("U1", "new", page("1.9.211"), "P", META)


def test_the_tool_turns_the_refusal_into_an_error_with_no_override(monkeypatch):
    import inspect
    from alto import mcp_server as srv

    def refuse(*a, **k):
        raise E.StaleEngineError("1.9.300", "1.9.211")
    monkeypatch.setattr(srv, "_publish_timeline", refuse)
    inner = srv.publish_timeline.__wrapped__.__wrapped__          # update_noted -> accounted -> the tool body
    r = inner("t", "private-web")
    assert r["error"] == "newer_page_exists" and r["page_built_by"] == "1.9.300"
    assert "Update the Alto extension first" in r["message"]
    params = inspect.signature(srv.publish_timeline).parameters
    assert not any(p in params for p in ("force", "override", "allow_stale", "allow_downgrade"))
    assert "ALTO_ALLOW_STALE" not in inspect.getsource(E)


def test_the_early_check_stops_a_publish_before_any_deploy(monkeypatch):
    from alto import mcp_server as srv

    class St:
        def get_page(self, uid, key):
            return page("1.9.300")

        def get_artifact(self, uid, tid, name):
            return page("1.9.211")
    monkeypatch.setattr(srv, "get_store", lambda: St())
    monkeypatch.setattr(srv, "uid", lambda: "U1")
    with pytest.raises(E.StaleEngineError):
        srv._refuse_downgrade_early("t", {"private_key": "k"})
    srv._refuse_downgrade_early("t", {})            # never published yet: nothing to compare


# ── the shell's upload control ──────────────────────────────────────────────

def test_the_update_control_says_what_it_does():
    s = shell()
    assert "Replace page file" in s
    assert "does not update the Alto extension" in s
    assert ">Update<" not in s and "label class=\"file\">Update" not in s
    assert "Updating" not in s
