"""Nothing shippable may carry the author's own Firebase project.

The connector is distributed publicly. A published timeline runs alto-cloud.js
against whatever Firebase project is compiled into it, so a project baked into
a shipped artifact would funnel every reader — of anyone's timeline — into that
one Auth tenant, Firestore and free-tier quota. The Terrarium app shares that
project, which is why this is a build gate rather than a lint.

These markers are the author's project identifiers, all of them public values
(a Firebase web API key is not a secret) but each uniquely identifying.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.cloud import DISABLED, emit_cloud_js, load_config, CloudConfigError  # noqa: E402

MARKERS = ("terrarium-alto", "AIzaSyDlTqMgJc8hZwHuTgaSIGvFFuVzA92mnV8",
           "1059051849224")

# Known carriers, exempted deliberately and listed so they stay visible rather
# than being swallowed by a directory-wide skip:
#
# engine/FROZEN and engine/TEMPLATE_MANIFEST.json used to be listed here. They
# are now untracked entirely (.gitignore): besides the API key, they contain the
# author's own Terrarium prose, and a public repo is not the place for it.
#
# EXEMPT is asserted against below: if it grows, that is a decision someone has
# to make on purpose.
EXEMPT = {
    "tests/test_no_leaks.py",
}

# Creative content, not configuration. The project-id markers above would not
# have caught these: the extraction tooling carried the author's cast list as a
# hygiene denylist, and the calibration data carried his node ids. Matched on
# word boundaries — "anya" is otherwise a substring of "anyActive" in the
# engine's own JavaScript.
CONTENT_MARKERS = ("jacob", "marcy", "sonya", "conrad", "voss")

SHIPPABLE_SUFFIXES = {".py", ".js", ".json", ".html", ".md", ".sh", ".rules"}
SKIP_DIRS = {".venv", ".git", "__pycache__", ".pytest_cache", ".claude"}


def _tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout.split()
    for rel in out:
        p = ROOT / rel
        if not p.exists() or p.suffix not in SHIPPABLE_SUFFIXES:
            continue
        if set(Path(rel).parts) & SKIP_DIRS or rel in EXEMPT:
            continue
        yield rel, p


@pytest.mark.parametrize("marker", MARKERS)
def test_no_shipped_source_file_carries_the_authors_project(marker):
    hits = [rel for rel, p in _tracked_files()
            if marker in p.read_text(encoding="utf-8", errors="ignore")]
    assert not hits, (
        f"{marker!r} is baked into shipped source: {hits}. Publishing this "
        "would point other people's timelines at the author's Firebase project.")


def test_the_exempt_list_has_not_grown():
    """Exemptions are a decision, not a default. If a new file starts carrying
    the author's project, this fails until someone either cleans it or adds it
    here on purpose."""
    tracked = set(subprocess.run(["git", "ls-files"], cwd=ROOT,
                                 capture_output=True, text=True,
                                 check=True).stdout.split())
    carriers = set()
    for rel in tracked:
        p = ROOT / rel
        if not p.is_file() or set(Path(rel).parts) & SKIP_DIRS:
            continue
        if any(m in p.read_text(encoding="utf-8", errors="ignore")
               for m in MARKERS):
            carriers.add(rel)
    # Compare against the tracked subset — an exempt file that is not committed
    # yet simply is not in scope.
    assert carriers == (EXEMPT & tracked), (
        f"unexpected carriers: {sorted(carriers - EXEMPT)}; "
        f"stale exemptions: {sorted((EXEMPT & tracked) - carriers)}")


def test_private_fixtures_are_not_tracked():
    """They hold the author's Terrarium content; publishing them would put his
    novel material in an Apache-licensed repo."""
    tracked = set(subprocess.run(["git", "ls-files"], cwd=ROOT,
                                 capture_output=True, text=True,
                                 check=True).stdout.split())
    for private in ("engine/TEMPLATE_MANIFEST.json",
                    "engine/FROZEN/alto-cloud.js",
                    "engine/FROZEN/terrarium_glass.html"):
        assert private not in tracked, f"{private} would be published"
    assert not any(t.startswith("firebase/") for t in tracked)


def test_frozen_fixture_is_excluded_from_every_packaging_path():
    """engine/FROZEN is also kept out of every build artifact."""
    assert "engine/FROZEN/" in (ROOT / ".dockerignore").read_text(encoding="utf-8")
    packaged = ROOT / "alto"          # the importable package
    for p in packaged.rglob("*"):
        assert "FROZEN" not in p.parts, f"FROZEN leaked into the package: {p}"


def test_cloud_js_ships_with_sync_disabled():
    """The checked-in source must be inert on its own."""
    src = (ROOT / "alto" / "cloud" / "alto-cloud.js").read_text(encoding="utf-8")
    for marker in MARKERS:
        assert marker not in src
    assert 'apiKey:            ""' in src


def test_unset_env_emits_a_disabled_config(monkeypatch):
    monkeypatch.delenv("ALTO_FIREBASE_CONFIG", raising=False)
    assert load_config() == DISABLED
    out = emit_cloud_js()
    assert 'apiKey: ""' in out
    for marker in MARKERS:
        assert marker not in out


def test_a_publishers_own_config_is_spliced_in(monkeypatch):
    cfg = {"apiKey": "AIzaSyOTHER", "authDomain": "someone-else.firebaseapp.com",
           "projectId": "someone-else", "storageBucket": "someone-else.appspot.com",
           "messagingSenderId": "999", "appId": "1:999:web:abc"}
    monkeypatch.setenv("ALTO_FIREBASE_CONFIG", json.dumps(cfg))
    out = emit_cloud_js()
    assert 'projectId: "someone-else"' in out
    assert "terrarium-alto" not in out
    # exactly one config literal survives the splice
    assert out.count("const firebaseConfig") == 1


def test_unknown_keys_are_dropped(monkeypatch):
    monkeypatch.setenv("ALTO_FIREBASE_CONFIG", json.dumps(
        {"apiKey": "k", "projectId": "p", "appId": "a", "evil": "</script>"}))
    assert "evil" not in emit_cloud_js()


@pytest.mark.parametrize("raw", ["{not json", '"a string"', '{"apiKey": "k"}'])
def test_bad_config_is_rejected_loudly(raw, monkeypatch):
    monkeypatch.setenv("ALTO_FIREBASE_CONFIG", raw)
    with pytest.raises(CloudConfigError):
        load_config()


def test_a_generated_site_carries_no_authors_project(tmp_path, monkeypatch):
    """End to end: publish a timeline with no config and grep the output."""
    from alto.build.builder import load_brief, build_timeline
    from alto.build.single_file import bundle
    from alto.hosted import hosted_timeline
    from alto.publish_static import regenerate_site
    from alto.store.local import LocalStore

    monkeypatch.delenv("ALTO_FIREBASE_CONFIG", raising=False)
    st = LocalStore(tmp_path / "store")
    d = json.loads((ROOT / "samples" / "contracts_brief.json").read_text(encoding="utf-8"))
    b, nodes, conns = load_brief(d)
    html, _ = build_timeline(b, nodes, conns)
    tid = b.timeline_id
    st.put_artifact("local", tid, "hosted.html", hosted_timeline(html, tid))
    st.put_artifact("local", tid, "offline.html", bundle(b, html))
    st.put_timeline("local", tid, {
        "timeline_id": tid, "project_id": "", "brief": d["brief"],
        "status": "published", "visibility": "link",
        "share_slug": f"{tid}-aa22bb33"})

    site = regenerate_site(st, "local", tmp_path / "site")
    for f in site.rglob("*"):
        if not f.is_file():
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for marker in MARKERS:
            assert marker not in text, f"{marker!r} leaked into {f.name}"


@pytest.mark.parametrize("marker", CONTENT_MARKERS)
def test_no_tracked_file_carries_the_authors_characters(marker):
    """The licence covers the software; it must not sweep up the author's
    novel. engine/ templates are content-free by construction and
    tools/check_templates.py proves it, but that gate only ran over the
    templates — this one runs over everything that would be published."""
    import re
    pattern = re.compile(rf"\b{marker}\b", re.I)
    hits = [rel for rel, p in _tracked_files()
            if pattern.search(p.read_text(encoding="utf-8", errors="ignore"))]
    assert not hits, (
        f"{marker!r} appears in tracked files: {hits}. That is the author's "
        "creative content, not part of the licensed software.")
