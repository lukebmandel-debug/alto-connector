"""A timeline deleted on the homepage sits in Recently deleted (pagemeta.binned)
for 30 days. Claude sees it marked, and the interview offers it as nothing to
resume; the homepage's own list leaves it out of the projects (index.html)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import alto.mcp_server as srv  # noqa: E402

FROZEN = ROOT / "alto" / "engine" / "home_template.html"
CLOUD = (ROOT / "alto" / "cloud" / "alto-cloud.js").read_text(encoding="utf-8")


class Fake:
    def __init__(self):
        self.tl = [{"timeline_id": "torts", "project_id": "law", "private_key": "k1", "brief": {"title": "Torts"}},
                   {"timeline_id": "civ", "project_id": "law", "private_key": "k2", "brief": {"title": "Civ Pro"}}]

    def list_timelines(self, u): return self.tl
    def list_projects(self, u): return [{"project_id": "law", "name": "Law", "purpose": "", "kind": "studying"}]
    def list_pages(self, u):
        return [{"key": "k1", "tid": "torts", "title": "Law", "project": "Law", "heading": "Torts", "binned": 1791000000},
                {"key": "k2", "tid": "civ", "title": "Law", "project": "Law", "heading": "Civ Pro", "binned": 0},
                {"key": "k9", "tid": "gone", "title": "Old", "project": "Old", "heading": "Old", "binned": 1791000000}]
    def snapshot_keys(self, u): return set()
    def list_nodes(self, u, t): return []
    def get_connections(self, u, t): return []


def test_a_deleted_timeline_is_marked_in_the_listing(monkeypatch):
    monkeypatch.setattr(srv, "get_store", lambda: Fake())
    out = srv._projects_listing()
    rows = {t["timeline_id"]: t for t in out["projects"][0]["timelines"]}
    assert rows["torts"]["in_recently_deleted"] and "in_recently_deleted" not in rows["civ"]
    assert "Recently deleted" in out["recently_deleted_note"]
    # a page in Recently deleted with no draft here is not offered for import
    assert not any(p["published_key"] == "k9" for p in out.get("published_without_draft") or [])


def test_the_interview_does_not_offer_a_deleted_timeline(monkeypatch):
    monkeypatch.setattr(srv, "get_store", lambda: Fake())
    monkeypatch.setattr(srv, "_site_status", lambda: {})
    monkeypatch.setattr(srv, "_accounts_overview", lambda: [])
    monkeypatch.setattr(srv, "_completeness", lambda t, n, c: {})
    g = srv.get_interview_guide()
    assert [d["timeline_id"] for d in g["drafts"]] == ["civ"]


def test_the_homepage_deletes_only_by_way_of_recently_deleted():
    if not FROZEN.exists():
        import pytest
        pytest.skip("engine/FROZEN is not in this checkout")
    h = FROZEN.read_text(encoding="utf-8")
    js = h[h.index("function altoTileMenu"):h.index("// What is in Recently deleted")]
    assert "Confirm deletion" in js and "binTimeline" in js
    assert "ok.disabled = true" in js and "body.querySelector('button').focus()" in js   # Cancel takes Enter
    assert "purgeExpired" not in js                         # the menu never removes anything for good
    # the account side: removed for good only past BIN_DAYS, each checked again first
    p = CLOUD[CLOUD.index("async function _purgeExpired"):]
    p = p[:p.index("\n  }\n")]
    assert "BIN_DAYS * 86400" in p and "const again = await getDoc(d.ref)" in p
    assert "const BIN_DAYS = 30;" in CLOUD
