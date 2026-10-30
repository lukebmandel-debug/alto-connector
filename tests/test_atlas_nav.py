"""The Memory Atlas moves the System's way (briefs: cloud-atlas step 1; solar_navopt.py adapted to the map): Back goes up a level, Next
along it, where you are is named between them, the places beside the enlarged card are lit and numbered (1-9 go there), the arrows go
round them with the Tour off (on, they step the Tour as before), O is the whole world, ? lists the keys, and the minimap shows only while a
card or a unit is enlarged. Desktop only; a phone's map is unchanged (suggest-first). Chromium and WebKit, served as
test_world_palace_render.py serves its page."""
import pytest

from tests.test_world_palace_render import ENL, _open, _settle, browser, html, origin  # noqa: F401  (the shared page and browsers)

AT = "document.querySelector('#wpal-root .wp-nav .wp-at').textContent"


def test_back_next_and_where_you_are(browser, origin):  # noqa: F811
    page, errors = _open(browser, origin)
    try:
        assert page.evaluate(AT) == "Whole world"
        assert page.evaluate("document.querySelector('#wpal-root .wp-nav .wp-btn').disabled")           # nothing above the world
        assert not page.evaluate("document.querySelector('#wpal-root .wp-mm').classList.contains('on')")  # no minimap at the world
        page.evaluate("AltoWorld.select('erie1')")
        _settle(page)
        at = page.evaluate(AT)
        assert "›" in at                                                                                   # its place › it
        assert page.evaluate("document.querySelector('#wpal-root .wp-mm').classList.contains('on')")
        page.click("#wpal-root .wp-nav .wp-btn")                                                          # Back: up to its place
        _settle(page)
        assert page.evaluate(ENL) == "erie"
        page.click("#wpal-root .wp-nav .wp-btn")                                                          # Back: up to its unit
        _settle(page)
        assert page.evaluate(ENL) is None and page.evaluate(AT) != "Whole world"
        page.keyboard.press("o")
        _settle(page)
        assert page.evaluate(AT) == "Whole world"
        assert not errors, errors
    finally:
        page.close()


def test_numbers_and_arrows_go_round_what_is_beside(browser, origin):  # noqa: F811
    page, errors = _open(browser, origin)
    try:
        page.evaluate("AltoWorld.tourMode(false)")
        page.evaluate("AltoWorld.select('erie')")
        _settle(page)
        hk = page.evaluate("[].map.call(document.querySelectorAll('#wpal-root .wp-hk'), e => e.textContent)")
        assert hk and hk[0] == "1"                                                                        # what is beside it, numbered
        page.keyboard.press("1")
        _settle(page)
        first = page.evaluate(ENL)
        assert first and first != "erie"
        page.keyboard.press("ArrowRight")
        _settle(page)
        assert page.evaluate(ENL) not in (None, first) or len(hk) == 1
        page.keyboard.press("?")
        assert page.evaluate("!!document.querySelector('#wpal-root .wp-help')")
        page.keyboard.press("Escape")
        assert not page.evaluate("!!document.querySelector('#wpal-root .wp-help')")
        page.evaluate("AltoWorld.tourMode(true)")
        assert not errors, errors
    finally:
        page.close()


def test_a_phone_keeps_its_map_as_it_is(browser, origin):  # noqa: F811
    page = browser.new_page(viewport={"width": 390, "height": 844})
    try:
        page.goto(origin + "/index.html")
        page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
        assert page.evaluate("getComputedStyle(document.querySelector('#wpal-root .wp-nav')).display") == "none"
        assert page.evaluate("getComputedStyle(document.querySelector('#wpal-root .wp-mm')).display") == "none"
    finally:
        page.close()
