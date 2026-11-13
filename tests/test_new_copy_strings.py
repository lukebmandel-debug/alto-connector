"""The homepage and Reports pages say "New", not "New timeline" (Luke 2026-11-12). Non-browser: what the two templates carry."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = (ROOT / "alto" / "engine" / "home_template.html").read_text(encoding="utf-8")
REPORTS = (ROOT / "alto" / "engine" / "reports_template.html").read_text(encoding="utf-8")


def test_no_new_timeline_anywhere():
    for t in (HOME, REPORTS):
        assert "New timeline" not in t and "NEW TIMELINE" not in t and "newTimelineTile" not in t


def test_the_tile_label_is_exactly_new():
    assert '<span class="nt-label">New</span>' in HOME and "function newTile(" in HOME


def test_the_new_dialog_heads_are_new_and_new_project():
    assert 'id="nt-head">New<' in HOME
    assert "projectName ? 'New' : 'New project'" in HOME
    assert "Name it." in HOME and "Name the timeline." not in HOME


def test_the_info_panel_names_no_timelines():
    assert "timelines and outlines" not in HOME and "opens a timeline" not in HOME
    assert "(<em>&#65291; New</em> or <em>Start new project</em>)" in HOME


def test_menus_and_fallbacks_drop_the_noun():
    for s in ("Rename timeline", "Delete timeline", "Untitled timeline", "Shared timeline", "Timeline name"):
        assert s not in HOME and s not in REPORTS
    assert "btn('Rename…'" in HOME and "btn('Delete…'" in HOME and "thisOne(pg.fmt)" in HOME
    assert "const FMT_NOUN" in HOME and "memory atlas" in HOME


def test_the_timeline_format_name_stays():
    assert '"timeline":["Timeline"' in HOME and '"lanes":["Timeline · Horizontal"' in HOME


# ── the Board's four settled strings (12 Nov) ──
TIMELINE = (ROOT / "alto" / "engine" / "timeline_template.html").read_text(encoding="utf-8")
PRINT_VIEWS = (ROOT / "alto" / "build" / "print_views.py").read_text(encoding="utf-8")
PAGES = (ROOT / "alto" / "build" / "pages.py").read_text(encoding="utf-8")


def test_ink_saver_print_option_names_the_format():
    assert "function printInkLabel(f)" in HOME and "printInkLabel(pg.fmt)" in HOME
    assert "Timeline picture" not in HOME
    assert "var want = fmtName() + ' picture, ink-saver'" in PRINT_VIEWS and "return 'Outline'" in PRINT_VIEWS


def test_unknown_search_kind_shows_no_word():
    assert "kind:'', fmt:'generic'" in PAGES and "kind:'Timeline'" not in PAGES
    assert "if(k === 'generic') return GENERIC_SYM;" in HOME


def test_save_to_account_button_names_the_format():
    assert 'data-save="timeline">Timeline</button>' not in TIMELINE
    assert "_pageFmtName() + '</button>'" in TIMELINE


def test_lanes_reads_horizontal_wherever_users_see_it():
    from alto import entitlements
    assert entitlements.LABELS["lanes"] == "Horizontal"
    assert "['lanes', 'Horizontal', '']" in HOME and "Horizontal timeline" not in HOME
