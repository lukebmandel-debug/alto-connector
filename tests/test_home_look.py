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
