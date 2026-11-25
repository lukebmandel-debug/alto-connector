"""A page rebuilt with changes after a publish must never read as current
(Board L-1122-STALE-PUBLISH): status says the web copy is out of date, the
build's next step is to publish, and a publish clears it."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_mcp_flow import SAMPLE, fresh_store, _setup_draft  # noqa: E402,F401
from alto import mcp_server as srv  # noqa: E402
import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _no_real_deploy(monkeypatch, tmp_path):
    """No real site: deploys and their checks are stubbed, as in test_mcp_flow (CI has no firebase CLI, and an
    earlier test can leave a fake one on the path)."""
    import alto.publish_static as ps
    site = tmp_path / "site"; site.mkdir()
    monkeypatch.setattr(ps, "firebase_configured", lambda: ("firebase", "x", "proj"))
    monkeypatch.setattr(ps, "regenerate_site", lambda st, u: site)
    monkeypatch.setattr(ps, "deploy_site", lambda s: "https://x.web.app")
    monkeypatch.setattr(ps, "verify_live", lambda s, live: [])
    monkeypatch.setattr(ps, "LAST_STALE", [])


def _built():
    tid = _setup_draft()
    srv.record_materials_consent(tid, [{"name": "notes.pdf", "kind": "notes"}], True)
    srv.set_entities(tid, SAMPLE["brief"]["entities"])
    srv.add_nodes(tid, SAMPLE["nodes"])
    srv.add_connections(tid, SAMPLE["connections"])
    r = srv.build_timeline(tid)
    assert r.get("verify") == "passed", r
    return tid, r


def test_build_after_publish_reads_stale_until_published_again():
    tid, r = _built()
    assert r["status"] == "built" and r["built_at"] and "published_at" not in r
    assert srv.publish_timeline(tid, "private")["status"] == "published"
    g = srv.get_timeline(tid)
    assert g["status"] == "published" and g["published_at"] and g["built_at"]

    n = dict(SAMPLE["nodes"][0], title="Changed title")
    srv.add_nodes(tid, [n])
    assert srv.get_timeline(tid)["status"] == srv.STALE     # edited, not even rebuilt yet
    r = srv.build_timeline(tid)
    assert r["status"] == srv.STALE and r["published_at"] and r["built_at"]
    assert "publish_timeline(" in r["next"] and "'private'" in r["next"], r["next"]
    assert srv.get_timeline(tid)["status"] == srv.STALE
    assert srv.list_projects()["projects"][0]["timelines"][0]["status"] == srv.STALE

    assert srv.publish_timeline(tid, "private")["status"] == "published"
    assert srv.get_timeline(tid)["status"] == "published"


def test_rebuild_without_changes_stays_published():
    tid, _ = _built()
    srv.publish_timeline(tid, "private")
    r = srv.build_timeline(tid)
    assert r["status"] == "published", r
    assert "publish_timeline(" not in r["next"]
