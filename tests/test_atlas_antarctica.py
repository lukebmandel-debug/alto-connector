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


# the globe's outline (AltoWorld.ata(): the ring the globe draws, as lon/lat). Luke 2026-11-07 / Art: every coast vertex, the two antimeridian-cut rings stitched end to end, the cut-line
# vertices left out, closed through the pole; so the Peninsula, the Ronne/Weddell bay and the Ross bay have the flat map's shape (not the star-shaped sliver, notch and two spikes).
def _inside(pt, ring):
    x, y, c = pt[0], pt[1], False
    for i in range(len(ring)):
        (x1, y1), (x2, y2) = ring[i], ring[(i + 1) % len(ring)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def _arc(a, b):
    import math

    def v(l):
        la, lo = math.radians(l[1]), math.radians(l[0])
        return math.cos(la) * math.sin(lo), math.sin(la), math.cos(la) * math.cos(lo)
    return math.degrees(math.acos(max(-1, min(1, sum(p * q for p, q in zip(v(a), v(b)))))))


def _cross(p, q, r, s):
    def o(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return o(p, q, r) * o(p, q, s) < 0 and o(r, s, p) * o(r, s, q) < 0


def test_the_globe_outline_is_the_whole_coast_closed_simple_and_spikeless(browser, origin):
    page, errors = _open(browser, origin[0], "classic", globe=True)
    assert not errors, errors
    raw, rings = page.evaluate("AltoWorld.ata(true)"), page.evaluate("AltoWorld.ata()")
    big = max(rings, key=len)
    n = len(big)
    coast_vertices = sum(len(r) for r in raw if len(r) > 40 and any(abs(p[0]) > 179.9 for p in r)) - 2 * 5       # (the two cut rings' own vertices, less their cut-line spurs)
    assert n >= coast_vertices - 4, (n, coast_vertices)                                                              # (every coast vertex kept, none thinned to one per degree)
    assert n > 150                                                                                                    # (the old outline had at most 360, in practice about 120 distinct)
    assert big[0][0] < -179.9 and big[-1][0] > 179.9 and big[0][1] < -89 and big[-1][1] < -89                         # (west end to east end, pole corners: closed round the pole)
    assert sum(1 for p in big if abs(p[0]) > 179.9) == 4                                                              # (the two corners and the one coast point on each side of the cut: no spurs)
    lons = [p[0] for p in big[1:-1]]
    assert sum(1 for i in range(1, len(lons)) if abs(lons[i] - lons[i - 1]) > 40) == 0                              # (the coast runs once round, no jump)
    assert max(_arc(big[i], big[(i + 1) % n]) for i in range(n)) < 5.5                                              # (no spike or long chord: the longest edge is a pole corner's 5 degrees)
    assert not any(_cross(big[i], big[(i + 1) % n], big[j], big[(j + 1) % n]) for i in range(n) for j in range(i + 2, n) if not (i == 0 and j == n - 1))   # (simple)
    assert _inside((-58.5, -64.0), big) and _inside((-66.5, -67.5), big)                                               # (the Peninsula, to its tip near lat -63 lon -57)
    assert not _inside((-45, -75), big) and not _inside((-170, -80), big) and not _inside((170, -78), big)         # (the Weddell and Ross seas are water)
    assert _inside((0, -85), big) and _inside((90, -80), big)                                                          # (the plateau is land)
