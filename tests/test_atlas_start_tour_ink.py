"""The Classic Atlas Start Tour pill reads in dark ink (Art, 2026-11-05): white on the lavender accent was 2.72:1; #14122b is over 4.5:1, matching the
Holographic pill. Retro and Holographic keep their own ink. WebKit, reusing test_atlas_tour_colour.py's server and browser; skipped without Playwright."""
import pytest

from tests.test_atlas_tour_colour import browser, origin  # noqa: E402,F401

JS = """() => { var el = document.querySelector('#wpal-root .wp-row .wp-tt'), c = getComputedStyle(el); return [c.color, c.backgroundColor]; }"""


def _lum(rgb):
    ch = [int(v) / 255 for v in rgb.replace("rgba(", "").replace("rgb(", "").rstrip(")").split(",")[:3]]
    ch = [c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4 for c in ch]
    return .2126 * ch[0] + .7152 * ch[1] + .0722 * ch[2]


def test_the_classic_start_tour_pill_has_dark_ink_over_4_5_to_1(browser, origin):
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto(origin + "/index.html")
    page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=30000)
    fg, bg = page.evaluate(JS)
    assert fg == "rgb(20, 18, 43)", fg
    a, b = sorted((_lum(fg), _lum(bg)))
    assert (b + .05) / (a + .05) >= 4.5, (fg, bg)
