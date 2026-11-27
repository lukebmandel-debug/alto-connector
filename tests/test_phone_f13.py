"""F13: "Back to the timeline" is not offered on the timeline itself (phone audit 2026-11-26). WebKit, iPhone size, offline; skipped without Playwright."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))


@pytest.fixture(scope="module")
def pg_of():
    import phone_matrix as pm
    try:
        pm._playwright()
    except ImportError:
        pytest.skip("Playwright is not installed")
    pages, plans, art = pm.build_pages()
    s = pm.serve(pages, plans, art)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception as e:
            pytest.skip(f"no WebKit: {e}")

        def make(page):
            pg = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, user_agent=pm.UA).new_page()
            pg.goto(f"http://127.0.0.1:{s.server_address[1]}/{page}.html", wait_until="load")
            pg.wait_for_timeout(2500)
            return pg
        yield make
        b.close()
    s.shutdown()


def _shown(pg):
    return pg.evaluate("getComputedStyle(document.getElementById('drawer-timeline-btn')).display")


def test_back_to_the_timeline_is_offered_only_away_from_the_timeline(pg_of):
    pg = pg_of("timeline")
    pg.evaluate("window.openNavDrawer()")
    pg.wait_for_timeout(500)
    assert _shown(pg) == "none"                                      # on the timeline: it does nothing
    for cls in ("detail-open", "summary-open"):
        pg.evaluate("c => { document.documentElement.classList.remove('detail-open', 'summary-open'); document.documentElement.classList.add(c); }", cls)
        assert _shown(pg) != "none", cls                             # from a detail page or the Overview: it does something
