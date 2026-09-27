"""Mobile fixes found on the Torts outline (1.8.23).

  * the phone's MAP panel headed its groups with the source novel's five acts
    and palette on every timeline;
  * the "under {parent}" crumb shared the chips' row and wrapped in among them;
  * the search pill sat on top of the docked filter bar;
  * the detail page sliding in on a swipe was a flat var(--bg) (black in dark
    mode) that then flashed into the frosted-glass page.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import load_brief, build_timeline  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"
OUTLINE = ROOT / "samples" / "outline_brief.json"


def _build(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    html, _ = build_timeline(*load_brief(d))
    return d, html


def test_mobile_map_names_this_timelines_own_bands():
    for path in (SAMPLE, OUTLINE):
        d, html = _build(path)
        line = html.split("var ACT_NAMES = ", 1)[1].split(";", 1)[0]
        names = json.loads(line.replace("'", '"'))
        assert len(names) == len(d["brief"]["acts"])
        assert "Arrival" not in line
        colors = html.split("var ACCENT_COLORS = ", 1)[1].split(";", 1)[0]
        assert colors.count("#") == len(d["brief"]["acts"])


def test_help_text_does_not_describe_the_novel():
    _, html = _build(SAMPLE)
    for phrase in ("all 5 acts", "Characters, Environments, and Themes",
                   "Moving between scenes", "plot summary"):
        assert phrase not in html


def test_outline_crumb_has_its_own_row():
    _, html = _build(OUTLINE)
    assert "html.mobile .node-crumb{display:block;flex:0 0 100%;" in html


def test_search_pill_moves_below_the_filter_bar():
    _, html = _build(SAMPLE)
    assert "html.mobile.filter-active #m-search{ top:136px; }" in html


def test_swipe_preview_copies_the_detail_page_background():
    _, html = _build(SAMPLE)
    assert "var _dcs = getComputedStyle(detailPage);" in html
