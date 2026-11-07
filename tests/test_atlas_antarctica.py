"""Antarctica on the Memory Atlas (Luke 2026-11-05, L-1105-184246: "Also, antartica never made it in"). The map's three drawing paths (the flat base map, its 1:50m detail
swap and the globe's rings) each skipped ATA unless a card used it (palace_world.py: `cid==='ATA'&&used[cid]==null`), so the one continent with no country on it never drew. It is
land now, in the same style as the others, in every style and on a phone; it is still not a Tour country (no units, no stop, no flag) and still gets the neutral pennant.
Served from 127.0.0.1 like test_atlas_flags.py; WebKit and Chromium; a page is never closed on its own (the browser's close gets 15 s by an alarm)."""
import re
import signal
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import palace_world  # noqa: E402
from tests.test_atlas_tour_flag_fill import browser, origin  # noqa: E402,F401  (the same two fixtures)


def test_antarctica_is_not_skipped_by_any_of_the_three_drawing_paths():
    assert "cid==='ATA'" not in palace_world.WORLD_ASSET and "used[cid]==null" not in palace_world.WORLD_ASSET


def _open(browser, base, style="classic", size=(1400, 900), globe=False):
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, has_touch=size[0] < 500, is_mobile=size[0] < 500)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(base + "/index.html")
    page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=30000)
    page.evaluate("document.documentElement.classList.add('dark')")
    page.evaluate("window._altoStyle.set(%r)" % style)
    page.wait_for_timeout(700)
    if globe and not page.evaluate("AltoWorld.globe(true)"):
        pytest.skip("no WebGL here")
    if globe:
        page.wait_for_timeout(1500)
    return page, errors


SOUTH = """() => { const out = []; document.querySelectorAll('#wpal-root path.wp-c').forEach(p => { const b = p.getBBox(); if (b.width > 1200 && b.y > 250 && p.getAttribute('d').length > 200) out.push([Math.round(b.x), Math.round(b.y), Math.round(b.width), Math.round(b.height), p.getAttribute('class'), getComputedStyle(p).fill]); }); return out; }"""


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_the_flat_map_draws_antarctica_as_land_along_the_foot(browser, origin, style):
    page, errors = _open(browser, origin[0], style)
    r = page.evaluate(SOUTH)
    assert not errors, errors
    assert len(r) == 1 and r[0][1] > 250 and r[0][2] > 1200, r
    assert "wp-u" not in r[0][4]                                                     # (land, not a unit: no card is in it, so no unit colour and no Tour stop)
    land = page.evaluate("(() => { const a = [...document.querySelectorAll('#wpal-root path.wp-c')].filter(p => !p.classList.contains('wp-u') && p.getBBox().width < 1200)[0]; return getComputedStyle(a).fill; })()")
    assert r[0][5] == land                                                           # (the same land fill as the other unused countries)


@pytest.mark.parametrize("style", ["classic", "holo"])
def test_the_globe_draws_antarctica_too(browser, origin, style):
    page, errors = _open(browser, origin[0], style, globe=True)
    page.wait_for_timeout(1200)
    assert not errors, errors
    assert "ATA" in page.evaluate("AltoWorld.rings()")


def test_antarctica_shows_on_a_phone_and_is_not_a_tour_stop(browser, origin):
    page, errors = _open(browser, origin[0], "classic", size=(390, 844))
    assert not errors, errors
    assert len(page.evaluate(SOUTH)) == 1
    assert not page.evaluate("(window._ALTO_WORLD && (window._ALTO_WORLD.used || {}).ATA) != null")       # (no unit uses it: no stop)
