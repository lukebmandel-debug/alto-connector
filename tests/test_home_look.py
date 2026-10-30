"""The homepage's cards and its Retro style (home_look.py; item 15, Luke's answers 1C 2B 3B 4C 5C 6A 7A 8A)."""
from alto.build import home_look, pages


def _page():
    return pages.build_home([])


def test_the_strip_is_the_timelines_own_unit_colours():
    p = _page()
    assert "function unitStrip(units, fmt)" in p and ".slice(0, 7)" in p
    assert "unitStrip(pg.units, pg.fmt)" in p and "unitStrip(it.units, it.fmt)" in p
    assert "const strip = unitStrip(c.units, c.fmt);" in p
    assert set(home_look.FMT_ACCENT) >= {"timeline", "lanes", "outline", "system", "palace", "building", "world"}


def test_the_title_keeps_clear_of_the_symbol_and_a_phone_gets_two_up():
    css = home_look.CSS
    assert "margin-right:115px" in css
    assert "repeat(2, minmax(0, 1fr))" in css and "repeat(3, minmax(0, 1fr))" in css
    assert "min-height:132px" in css and "inset:-8px -3px" in css
    assert css in _page()


def test_the_dead_switch_is_gone_and_retro_has_no_moon_or_cartouche_on_the_homepage():
    from alto.build import retro
    c = retro.css()
    assert "html.alto-retro.alto-home #sk-mark{display:none" in c
    assert "html.alto-retro #mode-toggle{display:none" in c
    assert "classList.add('alto-home')" in _page()


def test_titles_bind_the_dash_to_the_word_before_it():
    assert "u00a0$1" in pages.build_home([])


def test_only_very_long_title_words_get_soft_hyphens():
    html = pages.build_home([])
    assert "{11,}" in html and "u00ad" in html
    assert "hyphens:auto" not in html and "hyphens:manual" in html


# ── regression (6cbb529): unitStrip read a top-level const that was not set yet when the first card was drawn,
# so a timeline with no unit colours killed the whole homepage script (search never wired up). ──
import pytest

try:
    from playwright import sync_api as pw
except ImportError:                                  # CI has no Playwright: the browser test skips
    pw = None


def test_the_accent_map_is_not_a_top_level_const_read_before_it_is_set():
    p = _page()
    a = p.index("function unitStrip(units, fmt){")
    assert a < p.index("const HOME_FMT_ACCENT") < p.index("const ok =", a)       # declared inside the function, before it is used


@pytest.mark.skipif(pw is None, reason="no Playwright")
@pytest.mark.parametrize("engine", ["chromium", "webkit"])
def test_a_timeline_with_no_unit_colours_does_not_crash_the_homepage(tmp_path, engine):
    page = pages.build_home([{"name": "Law", "pid": "p", "courses": [
        {"title": "No units", "href": "a.html", "sub": "0 units", "courseId": "a", "units": []},
        {"title": "No key", "href": "b.html", "sub": "0 units", "courseId": "b"},
        {"title": "Two", "href": "c.html", "sub": "2 units", "courseId": "c", "units": ["#4a9eff", "#f43f5e"]}]}])
    f = tmp_path / "h.html"
    f.write_text(page, encoding="utf-8")
    errs = []
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, engine).launch()
        except Exception as e:                       # that engine is not installed here
            pytest.skip(str(e)[:80])
        pg = b.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(f.as_uri())
        pg.wait_for_timeout(600)
        tiles = pg.evaluate("document.querySelectorAll('.course-tile:not(.new-tile) .unit-strip span').length")
        pg.click("#search-btn")
        pg.wait_for_timeout(300)
        opened = pg.evaluate("document.getElementById('search-btn').classList.contains('expanded')")
        b.close()
    assert errs == []
    assert tiles >= 4 and opened                     # the empty ones got their one accent segment, and search is wired
