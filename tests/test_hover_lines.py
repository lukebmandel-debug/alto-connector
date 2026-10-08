"""The clef, the wordmark and the timeline's name each draw a hover line, drawn beside
them so their boxes (and the homepage's parity with them) do not change. The browser
parts are skipped when Playwright is not installed."""
import json
import re
from pathlib import Path

import pytest

from alto.build import hover_lines
from alto.build.builder import build_timeline, load_brief

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def html():
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    return build_timeline(*load_brief(d))[0]


def test_the_hover_lines_are_in_the_page_and_never_on_a_phone_or_in_print(html):
    assert html.count('<style id="alto-hl-css">') == 1 and html.count('<script id="alto-hl-js">') == 1
    assert "html.mobile #title-bar .alto-hl, html.printing #title-bar .alto-hl{ display:none; }" in html
    assert "#title-text:hover::after{ border-color:var(--muted); }" in html
    # one visual pixel, as a border (an <svg> outline paints only its corners in WebKit)
    assert "border:var(--chip-rule, 1px) solid transparent" in hover_lines.CSS
    assert "outline" not in hover_lines.CSS


try:
    import playwright.sync_api as pw
except ImportError:
    pw = None
needs_browser = pytest.mark.skipif(pw is None, reason="Playwright is not installed")


@pytest.fixture(params=["chromium", "webkit"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            try:
                if request.param != "chromium":
                    raise e
                b = p.chromium.launch(channel="chrome")
            except Exception:
                pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


@needs_browser
@pytest.mark.parametrize("w,h", [(1280, 800), (1500, 900), (1920, 1080)])
def test_each_line_fits_its_mark_and_shows_on_hover(browser, html, tmp_path, w, h):
    f = tmp_path / "t.html"
    f.write_text(html, encoding="utf-8")
    pg = browser.new_page(viewport={"width": w, "height": h})
    pg.goto(f.as_uri()); pg.wait_for_timeout(2000)
    probe = """(sel)=>{const m=document.querySelector(sel[0]), r=document.querySelector(sel[1]);
      const a=m.getBoundingClientRect(), b=r.getBoundingClientRect(), c=getComputedStyle(r);
      return {dl:a.left-b.left, dr:b.right-a.right, dt:a.top-b.top, db:b.bottom-a.bottom,
              color:c.borderTopColor, width:c.borderTopWidth, inner:getComputedStyle(r,'::after')?1:0}}"""
    for mark, ring in (("#title-bar .brand-mark", "#alto-hl-mark"), ("#title-bar .brand-word", "#alto-hl-word")):
        z = pg.evaluate("parseFloat(document.documentElement.style.getPropertyValue('--alto-zoom'))||0.8")
        before = pg.evaluate(probe, [mark, ring])
        # the ring surrounds the mark with a little room each side, tight (not loose)
        for k in ("dl", "dr"):
            assert 2.0 * z <= before[k] <= 7.5 * z, (mark, k, before)
        for k in ("dt", "db"):
            assert 0.8 * z <= before[k] <= 5.5 * z, (mark, k, before)
        assert before["color"] == "rgba(0, 0, 0, 0)"
        pg.hover(mark); pg.wait_for_timeout(450)
        after = pg.evaluate(probe, [mark, ring])
        assert after["color"] != "rgba(0, 0, 0, 0)" and float(after["width"][:-2]) >= 0.9, (mark, after)
        pg.mouse.move(w // 2, h - 5); pg.wait_for_timeout(450)
    # the name: the line is a pseudo-element, so its own box is not touched
    box0 = pg.evaluate("JSON.stringify(document.getElementById('title-text').getBoundingClientRect())")
    pg.hover("#title-text"); pg.wait_for_timeout(450)
    assert pg.evaluate("getComputedStyle(document.getElementById('title-text'),'::after').borderTopColor") != "rgba(0, 0, 0, 0)"
    assert pg.evaluate("JSON.stringify(document.getElementById('title-text').getBoundingClientRect())") == box0
    pg.close()
