"""What the download page is allowed to claim about files it does not host.

The page's buttons point at `releases/latest/download`, and the released
bundles are built in CI — so nothing derived from a local build can describe
them. That went wrong once already: alto-get.web.app served v1.4.0 files under
v1.3.0 checksums, which reads to anyone checking as a tampered download.
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

LOCAL_HASH = "dead" * 16          # what a local build would have hashed to
RELEASED_HASH = "beef" * 16       # what GitHub reports for the shipped asset

FILES = [{"key": "macos-arm64", "os": "macOS", "arch": "Apple Silicon",
          "name": "Alto-macos-arm64.mcpb", "mb": 48, "sha256": LOCAL_HASH},
         {"key": "windows-x64", "os": "Windows", "arch": "64-bit",
          "name": "Alto-windows-x64.mcpb", "mb": 59, "sha256": LOCAL_HASH}]

RELEASE = ("v1.4.0", {f["name"]: RELEASED_HASH for f in FILES})


@pytest.fixture
def ident():
    return md.identity()


def _fake_urlopen(payload):
    def urlopen(request, timeout=None):
        return io.BytesIO(json.dumps(payload).encode())
    return urlopen


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


# ── the lookup ───────────────────────────────────────────────────────────────

def test_digest_prefix_is_stripped(ident, monkeypatch):
    monkeypatch.delenv("ALTO_NO_RELEASE_LOOKUP", raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen({
        "tag_name": "v1.4.0",
        "assets": [{"name": "Alto-macos-arm64.mcpb",
                    "digest": f"sha256:{RELEASED_HASH}"}]}))
    assert md.released_digests(ident) == (
        "v1.4.0", {"Alto-macos-arm64.mcpb": RELEASED_HASH})


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


# ── server.json is deliberately untouched ────────────────────────────────────

def test_server_json_still_pins_the_version(ident):
    """The registry entry stays pinned to v{version} assets with the local
    hash; only the page moved to published digests."""
    from alto.mcp_server import __version__

    entry = md.server_json(ident, FILES)
    assert entry["version"] == __version__
    for package in entry["packages"]:
        if package["registryType"] != "mcpb":
            continue
        assert f"/releases/download/v{__version__}/" in package["identifier"]
        assert package["fileSha256"] == LOCAL_HASH
