"""Flat | Globe on the Memory Atlas (Art's option 1 "Alto-line globe", notes atlas-build (c)): one switch in the map's bottom bar, the same
camera on a sphere (a place, a Tour stop, the plane and the cards carry over), the far side's pins hidden, the choice kept per viewer, and
a phone stays flat. Chromium and WebKit (headless WebGL); real Safari and the iOS Simulator run on Home Desktop."""
from tests.test_world_palace_render import ENL, _open, _settle, browser, html, origin  # noqa: F401


def test_the_globe_switch_keeps_the_place_and_the_tour(browser, origin):  # noqa: F811
    page, errors = _open(browser, origin)
    try:
        if not page.evaluate("AltoWorld.globe(true)"):
            assert not page.evaluate("!!document.querySelector('#wpal-root .wp-seg')")      # no WebGL: no switch at all
            return
        _settle(page, 900)
        assert page.evaluate("document.getElementById('wpal-root').classList.contains('wp-g')")
        assert page.evaluate("document.querySelector('#wpal-root .wp-seg [aria-label=Globe]').getAttribute('aria-pressed')") == "true"
        hidden = page.evaluate("[].filter.call(document.querySelectorAll('#wpal-root .wp-pin'), p => p.style.visibility === 'hidden').length")
        shown = page.evaluate("[].filter.call(document.querySelectorAll('#wpal-root .wp-pin'), p => p.style.visibility !== 'hidden').length")
        assert shown >= 3 and hidden >= 0
        page.evaluate("AltoWorld.select('erie')")
        _settle(page)
        assert page.evaluate(ENL) == "erie"
        page.evaluate("AltoWorld.tourMode(true); AltoWorld.hop(-1)")                     # back to Mexico: the plane flies a great circle
        page.wait_for_timeout(500)
        assert page.evaluate("AltoWorld.plane()")
        _settle(page, 2700)
        assert page.evaluate(ENL) == "sj"
        page.reload()
        page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
        _settle(page, 600)
        assert page.evaluate("AltoWorld.globe()")                                          # kept for this viewer
        page.click("#wpal-root .wp-seg [aria-label='Flat map']")
        _settle(page, 900)
        assert not page.evaluate("AltoWorld.globe()") and abs(page.evaluate("AltoWorld.view().cx")) <= 1100
        assert not errors, errors
    finally:
        page.evaluate("try{ localStorage.removeItem('alto-world-globe'); }catch(e){}")
        page.close()


def test_a_phone_stays_flat(browser, origin):  # noqa: F811
    page = browser.new_page(viewport={"width": 390, "height": 844})
    try:
        page.goto(origin + "/index.html")
        page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
        assert not page.evaluate("AltoWorld.globe(true)")
    finally:
        page.close()
