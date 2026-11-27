"""F15: a search result's kind tag is a small pill, not a full-width empty box (phone audit 2026-11-26). WebKit, iPhone size, offline; skipped without Playwright."""
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


def test_the_search_kind_tag_is_a_small_pill(pg_of):
    pg = pg_of("timeline")
    pg.evaluate("document.getElementById('m-search-glyph').click()")
    pg.wait_for_timeout(500)
    pg.fill("#m-search input", "offer")
    pg.wait_for_timeout(900)
    m = pg.evaluate("""() => { const k = document.querySelector('#m-search-results .sr-kind'), r = document.querySelector('#m-search-results .search-result');
      return k && {kind: k.getBoundingClientRect().width, row: r.getBoundingClientRect().width, txt: k.textContent}; }""")
    assert m, "no results"
    assert m["kind"] < m["row"] * 0.6, m
