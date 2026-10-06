"""The help text names the controls as they are, and the suggested build route."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import build_from_file  # noqa: E402

HTML = build_from_file(str(ROOT / "samples" / "contracts_brief.json"))[0]


def test_info_panel_and_sheet_say_the_suggested_route():
    assert HTML.count("suggested route") >= 2          # the ⓘ panel and the phone sheet
    assert "Edit with Claude</em>: bigger changes" in HTML
    assert "Freewrite" in HTML


def test_help_has_no_stale_controls_or_source_novel_words():
    for stale in ("beside the &#9432;", "above the Search pill", "Search</strong> pill at the bottom",
                  "all 5 acts", "plot summary", "Moving between scenes", "Tap <strong>Back</strong> (top-left)"):
        assert stale not in HTML, stale


def test_edit_pill_halves_say_what_each_is_for():
    assert 'data-tip="Edit with Claude: best for bigger changes"' in HTML
    assert 'data-tip="Edit manually: best for small fixes"' in HTML
