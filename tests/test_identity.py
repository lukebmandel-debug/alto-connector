"""The server's advertised identity: name, version, website and icons.

Regression guard for two things that were silently wrong: the server reported
the MCP SDK's version as its own, and shipped SVG-only icons even though
clients are only required to support PNG.
"""
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import mcp_server as srv  # noqa: E402


def _opts():
    return srv.mcp._mcp_server.create_initialization_options()


def test_reports_its_own_version_not_the_sdks():
    version = _opts().server_version
    assert version == srv.__version__
    assert not version.startswith("1.28"), "still reporting the mcp SDK version"


def test_name_and_website():
    opts = _opts()
    assert opts.server_name == "Alto"
    assert opts.website_url == srv.WEBSITE_URL


def test_a_png_icon_is_offered_first():
    icons = _opts().icons
    assert icons, "no icons advertised"
    assert icons[0].mimeType == "image/png", (
        "clients MUST support PNG but only SHOULD support SVG, so PNG leads")
    assert any(i.mimeType == "image/svg+xml" for i in icons)


def test_icons_declare_sizes_and_themes():
    icons = _opts().icons
    assert all(i.sizes for i in icons)
    themes = {getattr(i, "theme", None) for i in icons}
    assert {"light", "dark"} <= themes, "light/dark variants are indistinguishable"


def test_icon_payloads_are_real_pngs():
    for icon in _opts().icons:
        if icon.mimeType != "image/png":
            continue
        head, _, b64 = icon.src.partition(",")
        assert head == "data:image/png;base64"
        assert base64.b64decode(b64)[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"


def test_light_and_dark_actually_differ():
    by_theme = {}
    for icon in _opts().icons:
        if icon.mimeType == "image/png":
            by_theme[getattr(icon, "theme", None)] = icon.src
    assert by_theme["light"] != by_theme["dark"]
