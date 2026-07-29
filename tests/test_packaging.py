"""Guards on the .mcpb manifests and what goes into a bundle.

The bundles themselves are ~50MB and take minutes to build, so these tests
check the manifest the build script generates and the staging rules around it —
the parts that silently rot. Building and running a real bundle is the manual
step documented in packaging/README.md.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

sys.path.insert(0, str(ROOT / "packaging"))
import build_mcpb  # noqa: E402

from alto.engine import RUNTIME_TEMPLATES  # noqa: E402
from alto.mcp_server import __version__  # noqa: E402


@pytest.fixture(scope="module", params=sorted(build_mcpb.PLATFORMS))
def entry(request):
    key = request.param
    triple, mcpb_platform, interpreter, _site = build_mcpb.PLATFORMS[key]
    return key, build_mcpb.manifest(key, mcpb_platform, interpreter)


def test_manifest_declares_an_icon(entry):
    """Without this the connector shows a letter placeholder, which is the
    whole reason the bundle exists."""
    _, m = entry
    assert m["icon"] == "icon.png"
    assert len(m["icons"]) >= 2
    themes = {i.get("theme") for i in m["icons"]}
    assert {"light", "dark"} <= themes


def test_icon_files_referenced_by_the_manifest_exist():
    png = ROOT / "alto" / "assets" / "png"
    for theme in ("light", "dark"):
        for size in (512, 128):
            assert (png / f"alto-{theme}-{size}.png").exists()


def test_manifest_version_tracks_the_server(entry):
    _, m = entry
    assert m["version"] == __version__


def test_interpreter_is_the_bundled_one(entry):
    """A bare "python" here would use whatever the user happens to have —
    which on stock macOS is 3.9 and too old."""
    _, m = entry
    command = m["server"]["mcp_config"]["command"]
    assert command.startswith("${__dirname}/server/python")


def test_pythonpath_points_only_at_the_package(entry):
    """Dependencies live in the interpreter's own site-packages, not on
    PYTHONPATH. That is what lets .pth files run — pywin32 ships one, and
    without it `pywintypes` is missing on every Windows machine."""
    _, m = entry
    path = m["server"]["mcp_config"]["env"]["PYTHONPATH"]
    assert path.endswith("/server")
    assert "/lib" not in path


def test_dependencies_go_into_the_runtime_site_packages():
    for key, (_t, _p, interpreter, site) in build_mcpb.PLATFORMS.items():
        assert site.startswith("python/"), key
        expected = "Lib" if key.startswith("windows") else "lib"
        assert f"/{expected}/" in f"/{site}/", (key, site)
        assert interpreter.startswith("python/"), key


def test_platform_matches_the_key(entry):
    key, m = entry
    expected = "win32" if key.startswith("windows") else "darwin"
    assert m["compatibility"]["platforms"] == [expected]


def test_no_host_runtime_is_required(entry):
    """The bundle carries its own CPython. Declaring compatibility.runtimes
    would make Claude Desktop probe the host for a Python it does not need,
    which blocked the install the first time round."""
    _, m = entry
    assert "runtimes" not in m["compatibility"]


def test_firebase_config_is_marked_sensitive(entry):
    """It goes to the OS keychain rather than a plaintext config file."""
    _, m = entry
    assert m["user_config"]["firebase_config"]["sensitive"] is True


def test_every_tool_is_listed(entry):
    _, m = entry
    assert len(m["tools"]) == 14
    assert all(t["name"] and t["description"] for t in m["tools"])


def test_bundle_requirements_stay_slim():
    """The hosted variant's dependencies would add tens of megabytes to a file
    people have to download."""
    assert build_mcpb.REQUIREMENTS == ["mcp>=1.28,<2"]
    for heavy in ("fastapi", "uvicorn", "firebase-admin", "google-cloud-storage"):
        assert not any(heavy in r for r in build_mcpb.REQUIREMENTS)


def test_staging_covers_every_runtime_template():
    patterns = {(rel, pat) for rel, pat in build_mcpb.PACKAGE_INCLUDE}
    assert ("alto/engine", "*.html") in patterns
    for name in RUNTIME_TEMPLATES:
        assert (ROOT / "engine" / name).exists(), f"source template {name} missing"


def test_no_proofs_are_staged():
    """FROZEN/ and TEMPLATE_MANIFEST.json are build-time evidence, not runtime
    files, and one of them still carries the author's Firebase key."""
    staged = {f"{rel}/{pat}" for rel, pat in build_mcpb.PACKAGE_INCLUDE}
    assert not any("FROZEN" in s for s in staged)
    assert not any("TEMPLATE_MANIFEST" in s for s in staged)


def test_manifest_is_json_serialisable(entry):
    _, m = entry
    json.dumps(m)
