"""Phone audit B3 / B4 / B8 (26 Nov 2026): on a Classic phone a panel that carries reading text is opaque (the card never reads through the menu, How to use,
Notes, Map…), the prev/next pill is gone, not faded, while a panel is open, and on a detail page the pill is opaque. Retro and Holo keep their own grounds.
Runs as an iPhone in WebKit (skipped without Playwright)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_phone_minimal import pages, site, phone_ctx, pg, _go, _RETRO   # noqa: E402,F401

_ALPHA = """(sel) => { const c = getComputedStyle(document.querySelector(sel)).backgroundColor, m = c.match(/[\\d.]+/g); return m.length > 3 ? +m[3] : 1; }"""
_TOKEN = """() => { const c = getComputedStyle(document.documentElement).getPropertyValue('--panel-glass-bg'), m = c.match(/[\\d.]+/g); return m.length > 3 ? +m[3] : 1; }"""


def test_classic_phone_panels_are_opaque_in_light_and_dark(pg, site):
    _go(pg, site + "/timeline.html")
    assert pg.evaluate(_TOKEN) >= .94
    pg.evaluate("document.documentElement.classList.add('dark')")
    assert pg.evaluate(_TOKEN) >= .94
    pg.evaluate("document.documentElement.classList.remove('dark')")
    pg.evaluate("openNavDrawer()")
    pg.wait_for_timeout(500)
    assert pg.evaluate(_ALPHA, "#nav-drawer") >= .94
    pg.evaluate("closeNavDrawer()")
    pg.evaluate("toggleNotes()")
    pg.wait_for_timeout(500)
    assert pg.evaluate(_ALPHA, "#notes-panel") >= .94


def test_retro_keeps_its_own_panel_ground(pg, site):
    _go(pg, site + "/retro.html")
    assert .96 <= pg.evaluate(_TOKEN) <= 1


def test_the_prev_next_pill_is_hidden_not_dimmed_while_a_panel_is_open(pg, site):
    _go(pg, site + "/timeline.html")
    vis = "getComputedStyle(document.getElementById('timeline-label-bar')).visibility"
    assert pg.evaluate(vis) == "visible"
    for opener, closer in (("toggleNotes()", "toggleNotes()"), ("openNavDrawer()", "closeNavDrawer()")):
        pg.evaluate(opener)
        pg.wait_for_timeout(400)
        assert pg.evaluate(vis) == "hidden", opener
        pg.evaluate(closer)
        pg.wait_for_timeout(400)
        assert pg.evaluate(vis) == "visible", closer


def test_find_and_menu_tiles_are_hidden_while_a_panel_is_open(pg, site):
    _go(pg, site + "/timeline.html")
    vis = "['pmin-find', 'hamburger-tab'].map(i => getComputedStyle(document.getElementById(i)).visibility)"
    assert pg.evaluate(vis) == ["visible", "visible"]
    pg.evaluate("toggleNotes()")
    pg.wait_for_timeout(500)
    assert pg.evaluate(vis) == ["hidden", "hidden"]
    assert pg.evaluate(_ALPHA, "#notes-panel") == 1


def test_on_a_detail_page_the_pill_is_opaque(pg, site):
    _go(pg, site + "/timeline.html")
    pg.evaluate("showDetail('node', document.querySelector('.node').dataset.id)")
    pg.wait_for_timeout(900)
    assert pg.evaluate("document.documentElement.classList.contains('detail-open')")
    assert pg.evaluate(_ALPHA, "#node-nav-bar") >= .94


def test_the_system_menu_drawer_is_opaque_and_the_tiles_are_hidden(pg, site):
    _go(pg, site + "/system.html")
    pg.evaluate("openNavDrawer()")
    pg.wait_for_timeout(600)
    assert pg.evaluate(_ALPHA, "#nav-drawer") == 1
    assert pg.evaluate("['pmin-find', 'hamburger-tab'].map(i => getComputedStyle(document.getElementById(i)).visibility)") == ["hidden", "hidden"]
