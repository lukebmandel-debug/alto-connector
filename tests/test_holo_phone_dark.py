"""Holographic is dark only on a phone too (Luke 2026-11-13: "also i noticed light mode is still available incorrectly on mobile holo").

Browser (WebKit; skipped without Playwright): the home page on a phone, upright (402x874) and on its side (874x402), with a saved LIGHT
choice. Holographic: no light/dark button, the page dark, the saved choice left as it is, and the corner row closed up (info in the
button's place, no hole). Classic: the button is there and the saved light theme is respected. Retro (dark only since it came in): no
button, dark, its row closed up the same way."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_nt_dialog_scroll import browser, site   # noqa: E402,F401  (the same home page and WebKit)

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 "
      "Safari/604.1")
PROBE = """()=>{const m=document.getElementById('mode-toggle'), on=e=>!!e && e.getBoundingClientRect().width>0 && getComputedStyle(e).display!='none';
  const box=id=>{const e=document.getElementById(id); return on(e) ? e.getBoundingClientRect().toJSON() : null};
  return {dark:document.documentElement.classList.contains('dark'), toggle:on(m), saved:localStorage.getItem('alto-theme-v1'),
          info:box('info-btn'), search:box('search-btn'), vw:innerWidth}}"""


def _home(browser, site, style, size):
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, user_agent=UA, has_touch=True, is_mobile=True)
    pg = ctx.new_page()
    pg.add_init_script("try{localStorage.setItem('alto-bg-home-v1-style','%s');localStorage.setItem('alto-theme-v1','light')}catch(e){}" % style)
    pg.goto(f"{site}/h.html")
    pg.wait_for_timeout(900)
    return ctx, pg.evaluate(PROBE)


@pytest.mark.parametrize("style", ["holo", "retro"])
@pytest.mark.parametrize("size", [(402, 874), (874, 402)], ids=["upright", "on-its-side"])
def test_a_dark_only_style_on_a_phone_has_no_light_dark_button_and_no_hole(browser, site, style, size):
    ctx, r = _home(browser, site, style, size)
    try:
        assert not r["toggle"], r
        assert r["dark"], r
        assert r["saved"] == "light", r                                   # never overwritten: Classic keeps it
        # the row closes up: the rightmost corner control sits where the light/dark button would (14px in upright, 24px * zoom on its side)
        gap = r["vw"] - r["info"]["right"]
        assert gap < 30, f"a hole where the light/dark button was: info ends {gap:.0f}px from the edge {r}"
        if size[0] > 640:
            assert r["info"]["left"] - r["search"]["right"] < 15, r      # search closes up beside info
    finally:
        ctx.close()


@pytest.mark.parametrize("size", [(402, 874), (874, 402)], ids=["upright", "on-its-side"])
def test_classic_on_a_phone_keeps_its_button_and_the_saved_light_theme(browser, site, size):
    ctx, r = _home(browser, site, "classic", size)
    try:
        assert r["toggle"], r
        assert not r["dark"], r
        assert r["saved"] == "light", r
    finally:
        ctx.close()
