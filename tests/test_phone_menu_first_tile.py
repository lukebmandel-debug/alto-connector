"""B10 (phone audit 2026-11-26): the MENU's first tile names the way back by the format it is: "Back to the Memory Blueprint",
"Back to the Memory Atlas", one label, not a heading ("Timeline") over it. WebKit, iPhone size, offline; skipped without Playwright."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

JS = """() => { const b = document.getElementById('drawer-timeline-btn'), L = b.querySelector('.drawer-label'), I = b.querySelector('.drawer-icon'),
  r = b.getBoundingClientRect(), l = L.getBoundingClientRect();
  return {label: L.textContent.trim(), icon: getComputedStyle(I).display, h: Math.round(r.height), fits: l.top >= r.top - 1 && l.bottom <= r.bottom + 1}; }"""


@pytest.fixture(scope="module")
def site():
    import phone_matrix as pm
    try:
        pm._playwright()
    except ImportError:
        pytest.skip("Playwright is not installed")
    pages, plans, art = pm.build_pages()
    s = pm.serve(pages, plans, art)
    yield pm, f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()


@pytest.mark.parametrize("page, label", [("blueprint", "Back to the Memory Blueprint"), ("atlas", "Back to the Memory Atlas"),
                                         ("city", "Back to the Memory Map"), ("system", "Back to the system"), ("timeline", "Back to the timeline")])
def test_the_first_tile_names_its_format_once(site, page, label):
    pm, base = site
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception as e:
            pytest.skip(f"no WebKit: {e}")
        pg = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, user_agent=pm.UA).new_page()
        pg.goto(f"{base}/{page}.html", wait_until="load")
        pg.wait_for_timeout(2500)
        pg.evaluate("window.openNavDrawer()")
        pg.wait_for_timeout(700)
        m = pg.evaluate(JS)
        b.close()
    assert m["label"] == label, m                                  # the Atlas said "Back to the timeline", the Blueprint a "Timeline" heading
    assert m["icon"] == "none", m                                  # no second, heading copy of the name above it
    assert m["h"] >= 44 and m["fits"], m
