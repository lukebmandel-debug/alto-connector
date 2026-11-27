"""F2: the name that wraps round is set like the other half, with a small turn-back cue (phone audit 2026-11-26). WebKit, iPhone size, offline; skipped without Playwright."""
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


def test_the_wrap_round_name_is_not_a_dark_pill_and_carries_a_turn_back_cue(pg_of):
    pg = pg_of("timeline")
    m = pg.evaluate("""() => { const e = document.querySelector('#tlb-prev .wrap-pill, #tlb-next .wrap-pill, #nav-prev-label .wrap-pill, #nav-next-label .wrap-pill');
      if(!e) return null; const c = getComputedStyle(e), b = getComputedStyle(e, '::before'); return {bg: c.backgroundColor, sh: c.boxShadow, cue: b.content}; }""")
    assert m, "no wrap-round name on the first card"
    assert m["bg"] in ("rgba(0, 0, 0, 0)", "transparent") and m["sh"] == "none", m        # not a filled pill
    assert "\u21ba" in m["cue"].lower(), m                                                 # the small cue
