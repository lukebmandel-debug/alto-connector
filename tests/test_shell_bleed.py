"""The sign-in shells paint the page's wallpaper behind their frame, so an
iPhone's status-bar and toolbar strips continue the background."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alto.build import private_shell, share_shell  # noqa: E402


def test_both_shells_paint_the_wallpaper_behind_the_frame():
    for html in (private_shell.shell(), share_shell.shell()):
        assert html.index('id="bleed"') < html.index('id="stage"')      # under the frame
        assert "top:-12%;right:-6%;bottom:-12%;left:-6%" in html         # the page's own oversize
        assert "page-bg" in html and "--m-page-veil" in html            # read from the page
        assert "#stage{position:fixed;inset:0;width:100%;height:100%" in html  # frame untouched


def test_both_shells_repeat_the_pages_theme_colour_and_root_background():
    for html in (private_shell.shell(), share_shell.shell()):
        assert "meta-theme" in html and "'theme-color'" in html
        assert "--m-edge-top" in html and "--m-edge-bot" in html


def test_both_shells_carry_edge_strips_safari_can_sample():
    for html in (private_shell.shell(), share_shell.shell()):
        assert 'id="bar-top"' in html and 'id="bar-bot"' in html
        assert html.index('id="stage"') < html.index('id="bar-top"')      # above the frame
        assert "#bar-top,#bar-bot{position:fixed;left:0;width:100%;height:12px;" in html
        assert "#bar-top{top:-8px}" in html and "#bar-bot{bottom:-8px}" in html


def test_the_mobile_wallpaper_settles_into_one_colour_at_each_edge():
    import json
    from alto.build.builder import build_timeline, load_brief
    d = json.loads((Path(__file__).resolve().parent.parent / "samples" / "contracts_brief.json").read_text(encoding="utf-8"))
    html, _ = build_timeline(*load_brief(d))
    assert "html.mobile{ --m-edge-top:#c2c3d3; --m-edge-bot:#c4d7a2; }" in html
    assert "linear-gradient(to bottom, var(--m-edge-top) 0, var(--m-edge-top) 9.68%" in html


def test_the_top_strip_allows_for_the_headers_saturating_frost():
    for html in (private_shell.shell(), share_shell.shell()):
        assert "function saturate(c, s)" in html and "top = saturate(top," in html
