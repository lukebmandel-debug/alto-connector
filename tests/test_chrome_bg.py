"""Page chrome across formats (Luke, 2026-10-22): the background to the very top, readable chip-group labels,
the homepage's clear title bar and compact search, Retro's frame above the marks. No browser."""
import re

from alto.build import clear_top, retro
from alto.build.backgrounds import HEAD_JS
from alto.build.pages import build_home
from alto.build.search import HOME_ROW_JS, sx_block


def test_the_sheet_reaches_the_top_only_where_there_is_one():
    full, lean = clear_top.block(), clear_top.block(sheet=False)
    assert "#glass-slab" in full and "--ct-c0" in full and "updateHeaderTint" in full
    assert "#glass-slab" not in lean and "--ct-c0" not in lean     # a palace or a Star chart hides the sheet
    assert "lanes-ov-sky" in full and "lanes-ov-sky" not in lean
    assert "html.ct-on" in lean and "toggle('ct-on'" in lean


def test_the_picture_starts_at_the_top_when_the_bars_are_clear():
    assert "if(r.classList.contains('alto-clear-top'))return 0;" in HEAD_JS


def test_chip_group_labels_are_full_strength():
    css = clear_top.block(sheet=False)
    rule = re.search(r"#nav \.nav-group-label:not\(#_\)\{[^}]*\}", css).group(0)
    assert "opacity:1" in rule and "color:var(--text)" in rule and "font-size:10px" in rule
    assert "#nav .nav-group-label:not(#_){color:#d9ae55 !important" in retro.COMMON_CSS     # Retro: on a black pad
    assert "background:#000 !important;box-shadow:0 0 0 3px #000" in retro.COMMON_CSS


def test_the_homepage_bar_is_clear_on_a_computer_and_search_opens_compact():
    h = build_home([])
    head = h[:h.index("</head>")]
    assert "alto-home-clear-top" in head and "matchMedia('(min-width:641px)')" in head
    assert head.index("alto-clear-top'") < head.index('id="alto-bg-head"')     # before the picture is placed
    assert "window._altoSXFresh=1;" in HOME_ROW_JS and "window._altoSXFresh=1;" in h
    js = sx_block()
    assert "on=!window._altoSXFresh && localStorage.getItem(KEY)==='1'" in js
    assert "/*" not in js[js.index("<script"):]                                  # the script's comments stay in the source


def test_retro_corners_sit_at_the_top_above_the_marks():
    assert "top:3px;bottom:71px;" in retro.FRAME_CSS and "var(--nav-bottom" not in retro.FRAME_CSS
    assert "X #title-bar:not(#_)>*{translate:0 8px;}" in retro.FRAME_CSS


def test_retro_and_the_theme_follow_one_rule_everywhere():
    """Retro is a dark look (Luke, 2026-10-22: "many things about dark mode do not work on retro star chart"): the hosted
    layer and the System's Star chart share one chrome (dark tokens, bars, controls, panels, detail pages) and one
    function that keeps html.dark on while Retro is and gives the reader's theme back after."""
    from alto.build.solar_draw import SOLAR_JS
    from alto.build.solar_stars import RETRO_CSS, _X
    assert "window._altoRetroDark" in retro.ASSET and "window._altoRetroDark" in SOLAR_JS
    assert "window._altoRetroDark(RETRO && desk());" in SOLAR_JS
    shared = retro._slim(retro.scoped(retro.CHROME_CSS, _X))
    assert shared in RETRO_CSS and _X + " #detail-page:not(#_){background:#000 !important" in shared
    assert _X + " #mode-toggle{display:none !important;}" in shared
    hosted = retro.css()
    assert hosted.startswith("@media screen{") and "html.alto-retro #desk-back:not(#_)" in hosted
    assert "@media print{#sk-frame,#sk-mark{display:none !important;}}" in hosted     # a Retro page prints black on white
    for part in ("#detail-page .char-chip", "#desk-back", ".ast-btn.pri"):
        assert part in retro.CHROME_CSS and part not in retro.BOARD_CSS
