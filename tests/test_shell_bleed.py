"""On a phone the sign-in shells give Safari real pixels behind its status bar and
toolbar (a wallpaper stage plus a pinned scroll runway) so the timeline reads as
one page from the top of the screen to the bottom."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alto.build import private_shell, share_shell  # noqa: E402


def test_both_shells_carry_the_wallpaper_stage_and_runway():
    for html in (private_shell.shell(), share_shell.shell()):
        assert html.index('id="rw-stage"') < html.index('id="stage"')      # behind the frame
        assert "html.rw body{height:auto;min-height:calc(100dvh + 124px)}" in html   # the runway
        assert "window.scrollTo(0, OFF)" in html and "addEventListener('scroll', pin" in html  # pinned
        assert "--m-edge-top" in html and "--m-edge-bot" in html          # ends match the wallpaper
        assert "#stage{position:fixed;inset:0;width:100%;height:100%" in html  # frame untouched


def test_no_pinned_element_with_a_background_sits_on_the_top_or_bottom_edge():
    """Safari samples those and goes back to a flat strip."""
    for html in (private_shell.shell(), share_shell.shell()):
        assert "bar-top" not in html and "bar-bot" not in html
        assert "position:fixed;left:0;width:100%;height:12px" not in html


def test_the_header_tint_continues_up_under_the_clock():
    for html in (private_shell.shell(), share_shell.shell()):
        assert "navext.style.background = navBg" in html
        assert "navext.style.backdropFilter" in html


def test_the_mobile_wallpaper_settles_into_one_colour_at_each_edge():
    import json
    from alto.build.builder import build_timeline, load_brief
    d = json.loads((Path(__file__).resolve().parent.parent / "samples" / "contracts_brief.json").read_text(encoding="utf-8"))
    html, _ = build_timeline(*load_brief(d))
    assert "html.mobile{ --m-edge-top:#c2c3d3; --m-edge-bot:#c4d7a2; }" in html
    assert "linear-gradient(to bottom, var(--m-edge-top) 0, var(--m-edge-top) 9.68%" in html
