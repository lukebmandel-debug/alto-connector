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
        assert "--page-grad" in html and "--m-page-veil" in html         # read from the page
        assert "#stage{position:fixed;inset:0;width:100%;height:100%" in html  # frame untouched
