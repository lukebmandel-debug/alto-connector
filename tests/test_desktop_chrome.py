"""Desktop floating chrome in a real browser: the edit toggle holds the corner of
the bottom-right row, with search, info and a round light/dark to its left; a
detail page has a way back to the timeline in the title bar; the magnifier sits
centred in its circle. Skipped when Playwright is not installed."""
import json
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")

from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.reidentify import reidentify  # noqa: E402
from alto.build.single_file import private_page  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
KEY = "czckq4utebcx5rvgdptrgt"


@pytest.fixture(scope="module")
def pages(tmp_path_factory):
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    b, nodes, conns = load_brief(d)
    html = build_timeline(b, nodes, conns)[0]
    share = reidentify(private_page(b, html), KEY)
    t = tmp_path_factory.mktemp("chrome")
    (t / "own.html").write_text(html, encoding="utf-8")
    (t / "share.html").write_text(share, encoding="utf-8")
    return t


@pytest.fixture(params=["chromium", "webkit"])
def browser(request):
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


def open_page(browser, f, w=1400, h=900, scale=1):
    pg = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=scale).new_page()
    pg.goto(f.as_uri())
    pg.wait_for_timeout(1000)
    return pg


RECTS = """()=>{const o={};['search-btn','info-btn','mode-toggle','alto-edit-pill','desk-back'].forEach(id=>{
 const e=document.getElementById(id); if(!e||!e.offsetWidth) return; const r=e.getBoundingClientRect();
 o[id]={l:r.left,r:r.right,t:r.top,b:r.bottom,w:r.width,h:r.height};}); o.W=innerWidth; return o;}"""


def test_row_order_and_spacing_with_the_edit_toggle(browser, pages):
    pg = open_page(browser, pages / "own.html")
    r = pg.evaluate(RECTS)
    order = [r[k] for k in ("search-btn", "info-btn", "mode-toggle", "alto-edit-pill")]
    assert all(a["r"] < b["l"] for a, b in zip(order, order[1:]))
    mids = [(x["t"] + x["b"]) / 2 for x in order]
    assert max(mids) - min(mids) < 0.6
    gaps = [b["l"] - a["r"] for a, b in zip(order, order[1:])]
    assert max(gaps) - min(gaps) < 1.2, gaps
    assert abs(r["W"] - order[-1]["r"] - 24) < 1.5          # the corner inset
    m, i = r["mode-toggle"], r["info-btn"]
    assert abs(m["w"] - i["w"]) < 0.5 and abs(m["h"] - i["h"]) < 0.5
    assert pg.evaluate("document.getElementById('mode-toggle').textContent.trim()") == ""


def test_without_the_edit_toggle_the_circles_sit_flush_right(browser, pages):
    pg = open_page(browser, pages / "share.html")
    r = pg.evaluate(RECTS)
    assert "alto-edit-pill" not in r
    assert abs(r["W"] - r["mode-toggle"]["r"] - 24) < 1.5
    assert r["search-btn"]["r"] < r["info-btn"]["l"] < r["info-btn"]["r"] < r["mode-toggle"]["l"]
    # editing hides the toggle too: the circles close up on the corner
    pg = open_page(browser, pages / "own.html")
    pg.evaluate("document.documentElement.classList.add('alto-editing')")
    pg.wait_for_timeout(200)
    r = pg.evaluate(RECTS)
    assert "alto-edit-pill" not in r and abs(r["W"] - r["mode-toggle"]["r"] - 24) < 1.5


def test_light_dark_still_toggles_and_keeps_its_place(browser, pages):
    pg = open_page(browser, pages / "own.html")
    before = pg.evaluate(RECTS)["mode-toggle"]
    pg.click("#mode-toggle")
    pg.wait_for_timeout(400)
    assert pg.evaluate("document.documentElement.classList.contains('dark')")
    after = pg.evaluate(RECTS)
    assert after["mode-toggle"]["l"] == before["l"] and after["mode-toggle"]["w"] == before["w"]
    assert pg.evaluate("getComputedStyle(document.querySelector('#mode-toggle .mode-sun')).display") == "block"


def test_expanded_info_and_search_stay_clear_of_the_corner(browser, pages):
    pg = open_page(browser, pages / "own.html")
    base = pg.evaluate(RECTS)
    pg.click("#info-btn")
    pg.wait_for_timeout(900)
    r = pg.evaluate(RECTS)
    assert r["info-btn"]["r"] <= base["mode-toggle"]["l"] - 5
    assert r["mode-toggle"]["l"] == base["mode-toggle"]["l"] and r["alto-edit-pill"]["l"] == base["alto-edit-pill"]["l"]
    pg.click("#info-btn")
    pg.wait_for_timeout(700)
    pg.click("#search-btn")
    pg.wait_for_timeout(700)
    r = pg.evaluate(RECTS)
    assert r["search-btn"]["r"] <= r["info-btn"]["l"] - 5 and r["search-btn"]["w"] > 200


def test_back_to_timeline_shows_only_on_a_detail_page(browser, pages):
    pg = open_page(browser, pages / "own.html")
    assert "desk-back" not in pg.evaluate(RECTS)
    pg.evaluate("showDetail('node','offer')")
    pg.wait_for_timeout(700)
    r = pg.evaluate(RECTS)
    b = r["desk-back"]
    # not the green pill, and clear of the clef and the centred title
    assert pg.evaluate("document.getElementById('desk-back').id") != "back-to-overview-bar"
    clef = pg.evaluate("(()=>{const r=document.querySelector('#title-bar .brand-mark').getBoundingClientRect();return [r.left,r.right]})()")
    title = pg.evaluate("(()=>{const r=document.getElementById('title-text').getBoundingClientRect();return [r.left,r.right]})()")
    assert b["l"] > clef[1] and b["r"] < title[0]
    assert b["h"] == r["mode-toggle"]["h"]
    pg.click("#desk-back")
    pg.wait_for_timeout(700)
    assert not pg.evaluate("document.documentElement.classList.contains('detail-open')")
    assert "desk-back" not in pg.evaluate(RECTS)


def test_back_button_narrow_window_keeps_only_its_arrow(browser, pages):
    pg = open_page(browser, pages / "own.html", w=1000, h=800)
    pg.evaluate("showDetail('node','offer')")
    pg.wait_for_timeout(700)
    assert pg.evaluate(RECTS)["desk-back"]["w"] < 40


@pytest.mark.parametrize("scale", [1, 2])
def test_the_magnifier_is_centred_in_its_circle(browser, pages, scale):
    pg = open_page(browser, pages / "own.html", scale=scale)
    d = pg.evaluate("""()=>{const b=document.getElementById('search-btn').getBoundingClientRect();
      const s=document.querySelector('#search-glyph svg'), c=s.querySelector('circle').getBoundingClientRect(), l=s.querySelector('line').getBoundingClientRect();
      const x=(Math.min(c.left,l.left)+Math.max(c.right,l.right))/2-(b.left+b.width/2), y=(Math.min(c.top,l.top)+Math.max(c.bottom,l.bottom))/2-(b.top+b.height/2);
      return [x,y];}""")
    assert abs(d[0]) < 0.4 and abs(d[1]) < 0.4, d


def test_phones_get_none_of_it(browser, pages):
    ua = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
    pg = browser.new_context(viewport={"width": 390, "height": 844}, user_agent=ua, is_mobile=True,
                             has_touch=True).new_page()
    pg.goto((pages / "own.html").as_uri())
    pg.wait_for_timeout(1200)
    pg.evaluate("showDetail('node','offer')")
    pg.wait_for_timeout(700)
    assert pg.evaluate("getComputedStyle(document.getElementById('desk-back')).display") == "none"
    assert pg.evaluate("getComputedStyle(document.getElementById('mode-toggle')).display") == "none"
