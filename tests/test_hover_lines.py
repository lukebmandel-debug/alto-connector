"""The clef, the wordmark and the timeline's name each draw a hover line that follows the
shape of what is hovered (never a box), and no box on the page changes when it shows. The
browser parts are skipped when Playwright is not installed."""
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
    css = hover_lines.CSS
    # every rule that shows a line is for a computer, outside print
    for sel in ("brand-mark:hover .alto-ring", "brand-word:hover .alto-word", "#title-text:hover::before"):
        line = next(l for l in css.splitlines() if sel in l)
        assert "html:not(.mobile):not(.printing)" in line, sel
    # a line that follows the shape: no box, no outline (an <svg> outline paints only its corners in WebKit)
    assert "outline" not in css and "border" not in css and "alto-hl-mark" not in html


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
@pytest.mark.parametrize("w,h", [(1280, 800), (1920, 1080)])
@pytest.mark.parametrize("dark", [False, True])
def test_each_line_hugs_its_shape_shows_on_hover_and_moves_nothing(browser, html, tmp_path, w, h, dark):
    f = tmp_path / "t.html"
    f.write_text(html, encoding="utf-8")
    pg = browser.new_page(viewport={"width": w, "height": h})
    pg.goto(f.as_uri()); pg.wait_for_timeout(2000)
    if dark:
        pg.evaluate("document.documentElement.classList.add('dark')")
    boxes = """()=>JSON.stringify(['#title-bar .brand-mark','#title-bar #title-text','#title-bar .brand-word','#back','#desk-back']
        .map(s=>{const e=document.querySelector(s);if(!e)return null;const r=e.getBoundingClientRect();return [r.x,r.y,r.width,r.height]}))"""
    before = pg.evaluate(boxes)
    # the clef: a copy of its strokes, a little wider, in the muted ink, behind it
    ring = "document.querySelector('#title-bar .brand-mark .alto-ring')"
    assert pg.evaluate(f"getComputedStyle({ring}).display") == "none"
    pg.hover("#title-bar .brand-mark"); pg.wait_for_timeout(300)
    assert pg.evaluate(f"getComputedStyle({ring}).display") != "none"
    widths = pg.evaluate(f"[...{ring}.querySelectorAll('path')].map(p=>[+p.getAttribute('data-w'), +p.getAttribute('stroke-width')])")
    assert len(widths) >= 8 and all(b > a > 0 for a, b in widths if a), widths
    paint = pg.evaluate(f"getComputedStyle({ring}.querySelector('path')).stroke")
    muted = pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--muted').trim()")
    assert paint and paint != "none" and paint.startswith("rgb")
    assert pg.evaluate(f"{ring}.nextElementSibling.classList.contains('alto-ink')")          # drawn behind the ink
    pg.mouse.move(w // 2, h - 5); pg.wait_for_timeout(300)
    assert pg.evaluate(f"getComputedStyle({ring}).display") == "none"
    # the wordmark: its own letters take a stroke behind their fill
    word = "document.querySelector('#title-bar .brand-word .alto-word')"
    assert pg.evaluate(f"getComputedStyle({word}).stroke") == "none"
    pg.hover("#title-bar .brand-word"); pg.wait_for_timeout(300)
    assert pg.evaluate(f"getComputedStyle({word}).stroke") != "none"
    assert float(pg.evaluate(f"getComputedStyle({word}).strokeWidth").rstrip("px")) > 0.5
    assert pg.evaluate(f"getComputedStyle({word}).paintOrder").startswith("stroke")
    pg.mouse.move(w // 2, h - 5); pg.wait_for_timeout(300)
    # the name: a copy of its letters with a text stroke sits behind it
    name = pg.evaluate("document.getElementById('title-text').textContent")
    pg.hover("#title-text"); pg.wait_for_timeout(300)
    assert pg.evaluate("getComputedStyle(document.getElementById('title-text'),'::before').content") == json.dumps(name)
    assert float(pg.evaluate("getComputedStyle(document.getElementById('title-text'),'::before').webkitTextStrokeWidth").rstrip("px")) > 0.3
    assert pg.evaluate("getComputedStyle(document.getElementById('title-text'),'::before').zIndex") == "-1"
    # nothing moved
    assert pg.evaluate(boxes) == before
    pg.close()


@needs_browser
def test_the_name_has_no_hover_line_while_it_is_being_edited(browser, html, tmp_path):
    f = tmp_path / "t.html"
    f.write_text(html, encoding="utf-8")
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(f.as_uri()); pg.wait_for_timeout(2000)
    pg.evaluate("document.documentElement.classList.add('alto-editing')")
    pg.hover("#title-text"); pg.wait_for_timeout(300)
    assert pg.evaluate("getComputedStyle(document.getElementById('title-text'),'::before').content") in ("none", "normal")
    pg.close()
