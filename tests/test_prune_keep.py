"""The hosted-folder prune keeps what stored pages (binned ones too) and the previous release still name, the same on every site, and prunes
nothing when the store cannot be read (Board B-1123-LIVE282). Test store and temp dirs only."""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import publish_static as ps  # noqa: E402
from alto.build import palace_assets as pa  # noqa: E402
from alto.store.local import LocalStore  # noqa: E402

HOLO = lambda h: ("holo", f"alto-holo-{h * 10}.js", "holo " + h)         # noqa: E731
RETRO = lambda h: ("retro", f"alto-retro-{h * 10}.js", "retro " + h)     # noqa: E731


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("ALTO_FIREBASE_CONFIG", json.dumps({"apiKey": "test-key", "projectId": "test-project", "appId": "test-app"}))
    monkeypatch.delenv("ALTO_FIREBASE_SITE", raising=False)


def _release(monkeypatch, version, holo, retro):
    import alto.mcp_server as ms
    monkeypatch.setattr(ms, "__version__", version)
    monkeypatch.setattr(pa, "assets", lambda building_plans=None, cmap_refs=None: [HOLO(holo), RETRO(retro)])


def _names(site, folder):
    d = site / folder
    return {p.name for p in d.iterdir()} if d.is_dir() else set()


def _store(tmp_path, page="<p>none</p>", binned=False, uid="local"):
    st = LocalStore(tmp_path / "store")
    st.put_artifact(uid, "tl1", "private.html", page)
    st.put_timeline(uid, "tl1", {"timeline_id": "tl1", "project_id": "", "brief": {}, "status": "published", "visibility": "private-web",
                                 "private_key": "czckq4utebcx5rvgdptrgt"})
    if binned:
        st.list_pages = lambda u: [{"key": "czckq4utebcx5rvgdptrgt", "binned": 1}]
    return st


def test_a_binned_timelines_named_asset_survives_a_prune(tmp_path, monkeypatch):
    site = tmp_path / "site"
    old = site / "holo" / "alto-holo-9999999999.js"
    old.parent.mkdir(parents=True)
    old.write_text("old")
    other = site / "retro" / "alto-retro-8888888888.js"
    other.parent.mkdir(parents=True)
    other.write_text("unnamed")
    _release(monkeypatch, "1.0.1", "a", "a")
    st = _store(tmp_path, page='<script src="/holo/alto-holo-9999999999.js"></script>', binned=True)
    ps.regenerate_site(st, "local", site)
    assert (site / "holo/alto-holo-9999999999.js").read_text() == "old"       # named only by a binned timeline's page


def test_the_previous_releases_scripts_survive_one_release_and_go_at_the_second(tmp_path, monkeypatch):
    site, st = tmp_path / "site", _store(tmp_path)
    for v, h in (("1.0.1", "a"), ("1.0.2", "b"), ("1.0.3", "c")):
        _release(monkeypatch, v, h, h)
        ps.regenerate_site(st, "local", site)
        if v == "1.0.1":
            assert {"alto-holo-" + "a" * 10 + ".js"} <= _names(site, "holo")
        if v == "1.0.2":
            assert _names(site, "holo") == {"alto-holo-" + "a" * 10 + ".js", "alto-holo-" + "b" * 10 + ".js"}
            assert _names(site, "retro") == {"alto-retro-" + "a" * 10 + ".js", "alto-retro-" + "b" * 10 + ".js"}
    assert _names(site, "holo") == {"alto-holo-" + "b" * 10 + ".js", "alto-holo-" + "c" * 10 + ".js"}      # a is gone at the second
    assert _names(site, "retro") == {"alto-retro-" + "b" * 10 + ".js", "alto-retro-" + "c" * 10 + ".js"}
    man = json.loads((site / ps.KEEP_MANIFEST).read_text())
    assert man["release"] == "1.0.3" and man["previous_release"] == "1.0.2" and man["previous"]["holo"]["alto-holo.js"] == ["alto-holo-" + "b" * 10 + ".js"]


def test_a_dev_build_of_the_same_version_does_not_drop_the_released_script(tmp_path, monkeypatch):
    site, st = tmp_path / "site", _store(tmp_path)
    _release(monkeypatch, "1.0.1", "a", "a")
    ps.regenerate_site(st, "local", site)
    _release(monkeypatch, "1.0.2", "b", "a")
    ps.regenerate_site(st, "local", site)
    _release(monkeypatch, "1.0.2", "c", "a")                                  # a dev build under the released version string
    ps.regenerate_site(st, "local", site)
    assert {"alto-holo-" + "a" * 10 + ".js", "alto-holo-" + "b" * 10 + ".js", "alto-holo-" + "c" * 10 + ".js"} == _names(site, "holo")


def test_both_sites_get_the_same_keep_set_and_a_forced_difference_prints_the_per_site_line(tmp_path, monkeypatch):
    sites = {"site-one": tmp_path / "one" / "_site", "site-two": tmp_path / "two" / "_site"}
    st = _store(tmp_path)
    for v, h in (("1.0.1", "a"), ("1.0.2", "b")):
        _release(monkeypatch, v, h, h)
        for name, d in sites.items():
            monkeypatch.setenv("ALTO_FIREBASE_SITE", name)
            ps.regenerate_site(st, "local", d)
    one, two = sites.values()
    assert _names(one, "holo") == _names(two, "holo") and _names(one, "retro") == _names(two, "retro")
    assert json.loads((one / ps.KEEP_MANIFEST).read_text()) == json.loads((two / ps.KEEP_MANIFEST).read_text())
    # force a difference: site-two lost the previous holo script, so its keep set cannot match the manifest
    (two / "holo" / ("alto-holo-" + "b" * 10 + ".js")).unlink()
    _release(monkeypatch, "1.0.3", "c", "c")
    lines = {}
    for name, d in sites.items():
        monkeypatch.setenv("ALTO_FIREBASE_SITE", name)
        ps.regenerate_site(st, "local", d)
        lines[name] = list(ps.LAST_PRUNE)
    assert len(lines["site-one"]) == 1 and lines["site-one"][0].startswith("prune [one]") and "missing here" not in lines["site-one"][0]
    assert len(lines["site-two"]) == 1 and lines["site-two"][0].startswith("prune [two]")
    assert "missing here: holo/alto-holo-" + "b" * 10 + ".js" in lines["site-two"][0] and "kept" in lines["site-two"][0] and "pruned" in lines["site-two"][0]


class _Flaky:
    """Reads fine once (the publish's own listing), then fails like a spent quota."""
    def __init__(self, inner, fail_on="list"):
        self.inner, self.n, self.fail_on = inner, 0, fail_on

    def __getattr__(self, k):
        return getattr(self.inner, k)

    def list_timelines(self, uid):
        self.n += 1
        if self.fail_on == "list" and self.n > 1:
            raise RuntimeError("quota")
        return self.inner.list_timelines(uid)

    def get_artifact(self, uid, tid, name):
        if self.fail_on == "artifact" and name == "timeline.html" and not getattr(self, "failed", False):
            self.failed = True                                              # the first scan of the stored pages fails, like a quota stop
            raise RuntimeError("quota")
        return self.inner.get_artifact(uid, tid, name)


@pytest.mark.parametrize("fail_on", ["list", "artifact"])
def test_an_unreadable_store_prunes_nothing(tmp_path, monkeypatch, fail_on):
    site = tmp_path / "site"
    stale = ["holo/alto-holo-1111111111.js", "retro/alto-retro-2222222222.js", "hvid/clip-3333333333.mp4", "cmap/b-444444444444.json",
             "gfx/sky-5555555555.ktx2", "bart/art-6666666666.jpg", "phone/phone-7777777777.js"]
    for ref in stale:
        p = site / ref
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("keep me")
    _release(monkeypatch, "1.0.1", "a", "a")
    ps.LAST_STALE.clear()
    ps.regenerate_site(_Flaky(_store(tmp_path), fail_on), "local", site)
    for ref in stale:
        assert (site / ref).read_text() == "keep me", ref + " was pruned though the store could not be read"
    assert "pruned NOTHING" in ps.LAST_PRUNE[0] and any("prunes nothing" in n for n in ps.LAST_STALE)


def test_a_readable_store_still_prunes_what_nothing_names(tmp_path, monkeypatch):
    site = tmp_path / "site"
    p = site / "hvid" / "clip-3333333333.mp4"
    p.parent.mkdir(parents=True)
    p.write_text("x")
    _release(monkeypatch, "1.0.1", "a", "a")
    ps.regenerate_site(_store(tmp_path), "local", site)
    assert not p.exists() and "pruned 1" in ps.LAST_PRUNE[0]


def test_the_manifest_is_never_deployed():
    assert fnmatch_ignored(ps.KEEP_MANIFEST)


def fnmatch_ignored(name):
    return name.startswith(".")                                              # firebase.json's ignore is "**/.*" (deploy_site)
