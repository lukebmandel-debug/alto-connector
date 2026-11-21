"""A deploy never prunes a hosted file a stored page names (a refused or skipped republish leaves the page naming an earlier build's file)."""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import publish_static as ps  # noqa: E402
from alto.store.local import LocalStore  # noqa: E402

NAMED = ["bldg/plan-063d955b8ca3.json", "fleet/palace-fleet-aaaaaaaaaa.js", "retro/alto-retro-aaaaaaaaaa.js", "phone/phone-aaaaaaaaaa.js",
         "world/a1-AUS-aaaaaaaaaa.json", "gfx/sky-aaaaaaaaaa.ktx2", "bart/art-aaaaaaaaaa.jpg", "hvid/clip-aaaaaaaaaa.mp4",
         "cmap/b-aaaaaaaaaaaa.json", "bldg/palace-building-aaaaaaaaaa.js"]
UNNAMED = ["bldg/plan-ffffffffffff.json", "hvid/clip-bbbbbbbbbb.mp4", "cmap/b-bbbbbbbbbbbb.json"]


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    monkeypatch.setenv("ALTO_FIREBASE_CONFIG", json.dumps({"apiKey": "test-key", "projectId": "test-project", "appId": "test-app"}))


def _site(tmp_path):
    site = tmp_path / "site"
    for i, ref in enumerate(NAMED + UNNAMED):
        p = site / ref
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("old")
        os.utime(p, (1000 + i, 1000 + i))
    # two newer releases of the retro script, so the old one is beyond _kept_earlier's one-per-kind
    for h in ("bbbbbbbbbb", "cccccccccc"):
        (site / "retro" / f"alto-retro-{h}.js").write_text("newer")
    (site / "retro" / "alto-retro-aaaaaaaaaa.js").write_text("/* names /hvid/clip-aaaaaaaaaa.mp4 */")
    return site


def _store(tmp_path, page, status="published", visibility="private-web", binned=False):
    st = LocalStore(tmp_path / "store")
    st.put_artifact("local", "tl1", "private.html", page)
    st.put_timeline("local", "tl1", {"timeline_id": "tl1", "project_id": "", "brief": {}, "status": status, "visibility": visibility,
                                     "private_key": "czckq4utebcx5rvgdptrgt"})
    if binned:
        st.list_pages = lambda uid: [{"key": "czckq4utebcx5rvgdptrgt", "binned": 1}]
    return st


def test_files_a_stored_page_names_survive_a_deploy_and_the_rest_are_pruned(tmp_path):
    site = _site(tmp_path)
    page = "<script>" + " ".join("/" + r for r in NAMED if not r.startswith("hvid/")) + "</script>"     # the hvid clip is named only by the retro script
    ps.regenerate_site(_store(tmp_path, page), "local", site)
    for ref in NAMED:
        assert (site / ref).is_file(), ref + " was pruned though a stored page names it"
    assert (site / "bldg/plan-063d955b8ca3.json").read_text() == "old"
    assert (site / "hvid/clip-aaaaaaaaaa.mp4").is_file()
    for ref in UNNAMED:
        assert not (site / ref).exists(), ref + " names no page and must be pruned"


def test_with_no_stored_page_naming_it_the_plan_is_pruned_as_before(tmp_path):
    site = _site(tmp_path)
    ps.regenerate_site(_store(tmp_path, "<p>nothing hosted</p>"), "local", site)
    assert not (site / "bldg/plan-063d955b8ca3.json").exists()
    assert not (site / "hvid/clip-aaaaaaaaaa.mp4").exists()


def test_an_unreadable_store_pins_nothing_and_a_missing_file_is_skipped(tmp_path):
    class Bad:
        def list_timelines(self, uid):
            raise RuntimeError("quota")
    assert ps._stored_page_refs(Bad(), "u") == set()
    assert ps._pin_named(tmp_path, {"bldg/plan-063d955b8ca3.json", "street/x-aaaaaaaaaa.json", "../x-aaaaaaaaaa.js"}) == {}


PLAN = "bldg/plan-063d955b8ca3.json"


def _page_naming_plan():
    return "<script>/" + PLAN + "</script>"


@pytest.mark.parametrize("kw", [dict(status="draft"), dict(status="unpublished"), dict(visibility="link"), dict(binned=True)])
def test_a_draft_unpublished_or_binned_timelines_plan_is_not_kept(tmp_path, kw):
    site = _site(tmp_path)
    ps.regenerate_site(_store(tmp_path, _page_naming_plan(), **kw), "local", site)
    assert not (site / PLAN).exists(), f"{kw}: a timeline that is not published must pin nothing (a plan can be a home with its lat/lon)"


def test_published_then_unpublished_is_pruned_on_the_next_deploy(tmp_path):
    site = _site(tmp_path)
    st = _store(tmp_path, _page_naming_plan())
    ps.regenerate_site(st, "local", site)
    assert (site / PLAN).is_file()                                        # published now: kept
    doc = st.get_timeline("local", "tl1")
    doc["status"] = "unpublished"
    st.put_timeline("local", "tl1", doc)
    ps.regenerate_site(st, "local", site)
    assert not (site / PLAN).exists()                                     # the kept set is recomputed on every deploy


def test_a_symlink_is_not_pinned_and_an_unreadable_store_warns(tmp_path, caplog):
    (tmp_path / "bldg").mkdir()
    (tmp_path / "secret").write_text("x")
    (tmp_path / "bldg/plan-063d955b8ca3.json").symlink_to(tmp_path / "secret")
    assert ps._pin_named(tmp_path, {PLAN}) == {}

    class Bad:
        def list_timelines(self, uid):
            raise RuntimeError("quota")
    ps.LAST_STALE.clear()
    with caplog.at_level("WARNING"):
        assert ps._stored_page_refs(Bad(), "u") == set()
    assert "not being kept" in caplog.text and any("quota" in n for n in ps.LAST_STALE)
