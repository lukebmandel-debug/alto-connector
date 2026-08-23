"""What the distribution is allowed to claim about files it does not host.

The download page and server.json both describe assets on a GitHub release,
and every one of those is built in CI — so nothing derived from a local build
can describe them. That went wrong once already: alto-get.web.app served
v1.4.0 files under v1.3.0 checksums, which reads to anyone checking as a
tampered download. server.json had the same defect with sharper teeth, since
the registry verifies each download against fileSha256 — a wrong value there
does not merely look untrustworthy, it fails the install.

The page's buttons follow `releases/latest/download`; server.json pins
`releases/download/v{version}`. Each takes its checksums from the release it
actually names.
"""
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packaging"))

import make_distribution as md  # noqa: E402
from alto.mcp_server import __version__ as VERSION  # noqa: E402

LOCAL_HASH = "dead" * 16          # what a local build would have hashed to
RELEASED_HASH = "beef" * 16       # what GitHub reports for the shipped asset

# bundles() no longer produces a sha256 at all — there is nothing a local hash
# could correctly describe. It stays here as a poison pill: hand one to either
# generator and it must still not come out the other side.
FILES = [{"key": "macos-arm64", "os": "macOS", "arch": "Apple Silicon",
          "name": "Alto-macos-arm64.mcpb", "mb": 48, "sha256": LOCAL_HASH},
         {"key": "windows-x64", "os": "Windows", "arch": "64-bit",
          "name": "Alto-windows-x64.mcpb", "mb": 59, "sha256": LOCAL_HASH}]

# What the page's `releases/latest` lookup returns, and what server.json's
# v{version} lookup returns. They are the same release only by coincidence.
RELEASE = ("v1.4.0", {f["name"]: RELEASED_HASH for f in FILES})
PINNED = (f"v{VERSION}", {f["name"]: RELEASED_HASH for f in FILES})


@pytest.fixture
def ident():
    return md.identity()


def _fake_urlopen(payload, seen=None):
    def urlopen(request, timeout=None):
        if seen is not None:
            seen.append(request.full_url)
        return io.BytesIO(json.dumps(payload).encode())
    return urlopen


def mcpb(entry):
    return [p for p in entry["packages"] if p["registryType"] == "mcpb"]


# ── the page ─────────────────────────────────────────────────────────────────

def test_a_local_hash_never_reaches_the_page(ident):
    """The regression itself. A hash of packaging/dist next to a
    `releases/latest` link is guaranteed wrong, in either direction."""
    for release in (None, RELEASE):
        page = md.build_page(ident, FILES, release)
        assert LOCAL_HASH not in page


def test_checksums_come_from_the_release(ident):
    page = md.build_page(ident, FILES, RELEASE)
    assert "Verifying your download" in page
    assert page.count(RELEASED_HASH) == len(FILES)
    assert "v1.4.0 assets" in page, "the block should name the release it describes"


def test_no_release_means_no_checksum_block(ident):
    """Offline, or before the first release. Printing nothing is the fallback —
    never a locally computed stand-in."""
    page = md.build_page(ident, FILES, None)
    assert "Verifying your download" not in page
    assert "sha256" not in page.lower()


def test_page_survives_losing_the_block(ident):
    """Dropping the block must not damage the page around it."""
    page = md.build_page(ident, FILES, None)
    assert page.count("<details") == page.count("</details>")
    assert page.rstrip().endswith("</html>")
    for marker in ("<footer>", "Download", "Installing"):
        assert marker in page


def test_a_partial_digest_set_drops_the_whole_block(ident):
    """Listing two checksums under three buttons implicates the third."""
    partial = ("v1.4.0", {FILES[0]["name"]: RELEASED_HASH})
    page = md.build_page(ident, FILES, partial)
    assert "Verifying your download" not in page


def test_buttons_still_track_the_latest_release(ident):
    page = md.build_page(ident, FILES, RELEASE)
    for f in FILES:
        assert f'/releases/latest/download/{f["name"]}' in page


def test_page_declares_the_ico_favicon(ident):
    """Claude Desktop's tile comes from a favicon service that asks for
    /favicon.ico by name; the SVG link alone leaves it 404ing."""
    page = md.build_page(ident, FILES, RELEASE)
    assert '<link rel="icon" href="/favicon.ico" sizes="any">' in page
    assert (md.ROOT / "alto" / "assets" / "favicon.ico").is_file()


# ── the lookup ───────────────────────────────────────────────────────────────

def test_digest_prefix_is_stripped(ident, monkeypatch):
    monkeypatch.delenv("ALTO_NO_RELEASE_LOOKUP", raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen({
        "tag_name": "v1.4.0",
        "assets": [{"name": "Alto-macos-arm64.mcpb",
                    "digest": f"sha256:{RELEASED_HASH}"}]}))
    assert md.released_digests(ident) == (
        "v1.4.0", {"Alto-macos-arm64.mcpb": RELEASED_HASH})


def test_a_tag_asks_for_that_exact_release(ident, monkeypatch):
    """server.json pins one version's assets, so it has to ask for that
    release by tag — `latest` is a different set of files as soon as the
    version moves on."""
    seen = []
    monkeypatch.delenv("ALTO_NO_RELEASE_LOOKUP", raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen({
        "tag_name": "v1.4.0",
        "assets": [{"name": "Alto-macos-arm64.mcpb",
                    "digest": f"sha256:{RELEASED_HASH}"}]}, seen))
    assert md.released_digests(ident, "v1.4.0") == (
        "v1.4.0", {"Alto-macos-arm64.mcpb": RELEASED_HASH})
    assert seen[0].endswith("/releases/tags/v1.4.0")


def test_no_tag_still_asks_for_the_latest_release(ident, monkeypatch):
    """The page's buttons track whatever is newest, so its lookup must too."""
    seen = []
    monkeypatch.delenv("ALTO_NO_RELEASE_LOOKUP", raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen({
        "tag_name": "v1.4.0",
        "assets": [{"name": "Alto-macos-arm64.mcpb",
                    "digest": f"sha256:{RELEASED_HASH}"}]}, seen))
    md.released_digests(ident)
    assert seen[0].endswith("/releases/latest")


def test_assets_without_a_sha256_digest_are_skipped(ident, monkeypatch):
    """GitHub only records digests for assets uploaded since 2025, and may use
    another algorithm. Either way there is nothing to quote."""
    monkeypatch.delenv("ALTO_NO_RELEASE_LOOKUP", raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen({
        "tag_name": "v1.0.0",
        "assets": [{"name": "old.mcpb", "digest": None},
                   {"name": "other.mcpb", "digest": "md5:abc"}]}))
    assert md.released_digests(ident) is None


def test_no_network_is_not_an_error(ident, monkeypatch):
    """Generating the page offline still has to work; it just loses the block."""
    monkeypatch.delenv("ALTO_NO_RELEASE_LOOKUP", raising=False)

    def refuse(request, timeout=None):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    assert md.released_digests(ident) is None


def test_a_broken_response_is_not_an_error(ident, monkeypatch):
    monkeypatch.delenv("ALTO_NO_RELEASE_LOOKUP", raising=False)

    def truncated(request, timeout=None):
        return io.BytesIO(b"{not json")

    monkeypatch.setattr(urllib.request, "urlopen", truncated)
    assert md.released_digests(ident) is None


def test_the_lookup_can_be_switched_off(ident, monkeypatch):
    monkeypatch.setenv("ALTO_NO_RELEASE_LOOKUP", "1")

    def fail(request, timeout=None):
        raise AssertionError("no request should be made when disabled")

    monkeypatch.setattr(urllib.request, "urlopen", fail)
    assert md.released_digests(ident) is None


# ── server.json ──────────────────────────────────────────────────────────────

def test_server_json_pins_released_digests(ident):
    """The same defect as the page's, with a harder failure: fileSha256 has to
    describe the asset at the identifier URL, and the registry downloads that
    asset and checks it. A hash of packaging/dist never matches a bundle CI
    built, so it does not look wrong — it makes the install fail."""
    entry = md.server_json(ident, FILES, PINNED)
    packages = mcpb(entry)
    assert len(packages) == len(FILES)
    for package in packages:
        assert package["fileSha256"] == RELEASED_HASH
    assert LOCAL_HASH not in json.dumps(entry)


def test_server_json_still_pins_the_version(ident):
    """The URLs stay on v{version} instead of following `latest`: an entry
    names the exact files its digests describe."""
    entry = md.server_json(ident, FILES, PINNED)
    assert entry["version"] == VERSION
    for package in mcpb(entry):
        assert f"/releases/download/v{VERSION}/" in package["identifier"]
        assert "/releases/latest/" not in package["identifier"]


def test_no_release_means_no_server_json(ident):
    """Where the page drops its checksum block, this cannot: an entry without
    fileSha256 is one nobody can verify, and a local hash breaks every
    install. So it stops, naming the release it wanted."""
    with pytest.raises(SystemExit) as stop:
        md.server_json(ident, FILES, None)
    assert f"v{VERSION}" in str(stop.value)


def test_a_partial_digest_set_stops_server_json(ident):
    """A short entry is still a broken entry, and the package left out is the
    one that would fail."""
    partial = (f"v{VERSION}", {FILES[0]["name"]: RELEASED_HASH})
    with pytest.raises(SystemExit) as stop:
        md.server_json(ident, FILES, partial)
    assert FILES[1]["name"] in str(stop.value)


def test_digests_from_another_release_are_refused(ident):
    """Published digests are not automatically the right ones. Pinning some
    other release's assets to v{version} URLs is the original bug again, just
    harder to spot for being real hashes of real files."""
    elsewhere = ("v0.9.0", {f["name"]: RELEASED_HASH for f in FILES})
    with pytest.raises(SystemExit) as stop:
        md.server_json(ident, FILES, elsewhere)
    assert "v0.9.0" in str(stop.value)
