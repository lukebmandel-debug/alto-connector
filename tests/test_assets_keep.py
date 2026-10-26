"""A deploy keeps the previous release's hashed hosted files, and verify_assets walks the stored pages (publish_static)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import publish_static as ps  # noqa: E402


def _put(d, name, text="x", t=None):
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(text)
    if t:
        os.utime(d / name, (t, t))


def test_the_previous_releases_file_of_each_kind_is_kept(tmp_path):
    d = tmp_path / "retro"
    _put(d, "alto-retro-aaaaaaaaaa.js", "old", 100)
    _put(d, "alto-retro-bbbbbbbbbb.js", "older", 50)
    _put(d, "alto-retro-cccccccccc.js", "fresh", 200)
    _put(d, "stray 2-aaaaaaaaaa.js", "junk", 300)
    kept = ps._kept_earlier(d, {"alto-retro-cccccccccc.js"})
    assert set(kept) == {"alto-retro-aaaaaaaaaa.js"}                         # the newest earlier one only; the fresh one and the junk are not kept
    assert kept["alto-retro-aaaaaaaaaa.js"][0] == b"old"


def test_kinds_are_kept_apart_and_a_missing_folder_is_empty(tmp_path):
    d = tmp_path / "world"
    _put(d, "a1-AUS-aaaaaaaaaa.json", "x", 10)
    _put(d, "a1-BRA-bbbbbbbbbb.json", "y", 20)
    assert set(ps._kept_earlier(d, set())) == {"a1-AUS-aaaaaaaaaa.json", "a1-BRA-bbbbbbbbbb.json"}
    assert ps._kept_earlier(tmp_path / "nope", set()) == {}


def test_restore_keeps_the_age_and_never_overwrites(tmp_path):
    d = tmp_path / "gfx"
    _put(d, "sky-aaaaaaaaaa.ktx2", "NEW")
    ps._restore_kept(d, {"sky-aaaaaaaaaa.ktx2": (b"OLD", 5), "tex-bbbbbbbbbb.ktx2": (b"T", 7)})
    assert (d / "sky-aaaaaaaaaa.ktx2").read_text() == "NEW" and (d / "tex-bbbbbbbbbb.ktx2").read_bytes() == b"T"
    assert int((d / "tex-bbbbbbbbbb.ktx2").stat().st_mtime) == 7


def test_the_hosted_files_a_page_names_are_found():
    html = '<script src="/retro/alto-retro-6e24c329bb.js"></script> fetch("/world/palace-world-d96cc59d87.js") "/cmap/b-0977f766a2f7.json" /bldg/palace-building-2e31e3834f.js /notes/x.js'
    assert ps.hosted_refs(html) == {"retro/alto-retro-6e24c329bb.js", "world/palace-world-d96cc59d87.js", "cmap/b-0977f766a2f7.json",
                                    "bldg/palace-building-2e31e3834f.js"}


def test_verify_assets_reports_a_404_and_a_store_that_cannot_be_read(monkeypatch):
    class Store:
        def list_timelines(self, uid):
            return [{"timeline_id": "t1"}]

        def get_artifact(self, uid, tid, name):
            return 'x /retro/alto-retro-6e24c329bb.js y'

    class R:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake(req, timeout=0):
        if req.full_url.endswith("alto-retro-6e24c329bb.js"):
            raise ps.urllib.error.HTTPError(req.full_url, 404, "nf", {}, None)
        return R()

    monkeypatch.setattr(ps.urllib.request, "urlopen", fake)
    p = ps.verify_assets(Store(), "u", "https://example.test")
    assert len(p) == 1 and "404" in p[0] and "t1" in p[0]

    class Broken:
        def list_timelines(self, uid):
            raise RuntimeError("limit")
    assert "could not be read" in ps.verify_assets(Broken(), "u", "https://example.test")[0]
