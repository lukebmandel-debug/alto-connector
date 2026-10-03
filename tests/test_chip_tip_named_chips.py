"""A chip that already shows its name gets no hover label; others keep it."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import build_from_file  # noqa: E402


def test_named_chip_label_rules_are_in_every_page():
    html, _ = build_from_file(str(ROOT / "samples" / "outline_brief.json"))
    # hover label is skipped only for chips flagged data-notip
    assert ".esym-btn:hover:not([data-notip]) ~ .chip-tip" in html
    assert ".csym-btn:hover:not([data-notip]) ~ .chip-tip" in html
    assert ".tsym-btn:hover:not([data-notip]) ~ .chip-tip" in html
    # name fully visible in the chip's own text -> no label; cut off -> label
    assert "window._altoChipNoTip=function(chip,label)" in html
    assert "chip.scrollWidth<=chip.clientWidth+1" in html
    # phone long-press asks the same helper
    assert "window._altoChipNoTip && window._altoChipNoTip(target,title)" in html
    # label still sits over the hovered chip's own row
    assert "tip.style.top=chip.offsetTop+'px';" in html


def test_label_hugs_chip_and_named_chips_may_use_the_whole_row():
    html, _ = build_from_file(str(ROOT / "samples" / "outline_brief.json"))
    # placed by on-screen position (zoom-proof), 3px above the chip
    assert "window._altoTipFit=function(chip,tip)" in html
    assert "calc(-100% - 3px)" in html
    # a named chip grows to its name, up to the footer's width
    assert ".esym-btn,.tsym-btn{max-width:100%;overflow:hidden;" in html
    assert "max-width:150px;overflow:hidden" not in html
