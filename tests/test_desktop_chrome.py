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


# ── the Notes / Freewrite panel docks the row and the right-edge tabs ───────

PANEL = """()=>{const q=i=>{const e=document.getElementById(i);if(!e||!e.offsetWidth)return null;const r=e.getBoundingClientRect();return {l:r.left,r:r.right,t:r.top,b:r.bottom}};
 return {p:q('notes-panel'),pill:q('alto-edit-pill'),mode:q('mode-toggle'),info:q('info-btn'),search:q('search-btn'),rail:q('tab-rail'),
  ov:q('overview-toggle'),flt:q('filter-toggle'),nt:q('notes-toggle'),W:innerWidth}}"""


def _row_clear_of_panel(r):
    gap = r["p"]["l"] - r["pill"]["r"]
    assert 22 < gap < 27, gap                                    # the corner inset, from the panel's edge
    row = [r[k] for k in ("search", "info", "mode", "pill")]
    assert all(a["r"] < b["l"] for a, b in zip(row, row[1:]))
    assert max(x["r"] for x in row) < r["p"]["l"]
    assert r["rail"]["r"] <= r["p"]["l"] + 0.6 and r["ov"]["l"] > 0 and r["flt"]["l"] > 0


@pytest.mark.parametrize("mode", ["fw", "notes"])
def test_the_row_and_tabs_sit_left_of_the_open_panel_and_follow_it(browser, pages, mode):
    pg = open_page(browser, pages / "own.html", w=1100, h=800)
    pg.click("#notes-toggle"); pg.wait_for_timeout(500)
    if mode == "fw":
        pg.click("#fw-seg button[data-m=fw]"); pg.wait_for_timeout(500)
    r = pg.evaluate(PANEL)
    _row_clear_of_panel(r)
    assert r["nt"] is None                                       # the Notes tab is redundant while the panel is up
    # the tabs are really on top: a click lands on them, not on the panel or a card
    for k in ("ov", "flt"):
        c = r[k]
        assert pg.evaluate(f"(()=>{{const e=document.elementFromPoint({(c['l']+c['r'])/2},{(c['t']+c['b'])/2});return !!e&&!!e.closest('#overview-toggle,#filter-toggle')}})()")
    if mode == "fw":                                             # drag it wider: the row keeps up live
        box = pg.locator("#fw-resize").bounding_box()
        pg.mouse.move(box["x"] + 4, box["y"] + 200); pg.mouse.down(); pg.mouse.move(box["x"] - 120, box["y"] + 200, steps=4)
        r2 = pg.evaluate(PANEL)
        assert r2["p"]["l"] < r["p"]["l"] - 80
        _row_clear_of_panel(r2)
        pg.mouse.up()
        pg.reload(); pg.wait_for_timeout(1800)                    # Freewrite reopens by itself
        _row_clear_of_panel(pg.evaluate(PANEL))
    pg.click("#notes-close"); pg.wait_for_timeout(600)
    r = pg.evaluate(PANEL)
    assert abs(r["W"] - r["pill"]["r"] - 24) < 1.5 and r["nt"] is not None and r["rail"]["r"] > r["W"] - 1


def test_expanded_info_and_search_stay_on_screen_beside_the_panel(browser, pages):
    pg = open_page(browser, pages / "own.html", w=1100, h=800)
    pg.click("#notes-toggle"); pg.wait_for_timeout(500)
    pg.click("#fw-seg button[data-m=fw]"); pg.wait_for_timeout(500)
    for btn in ("info-btn", "search-btn"):
        pg.click("#" + btn); pg.wait_for_timeout(700)
        b = pg.evaluate("(id)=>{const r=document.getElementById(id).getBoundingClientRect();return [r.left,r.right,r.top,r.bottom,document.getElementById('notes-panel').getBoundingClientRect().left]}", btn)
        assert b[0] >= 0 and b[1] <= b[4] + 0.6 and b[2] >= 0 and b[3] <= 800, b
        pg.mouse.click(200, 400); pg.wait_for_timeout(400)


def test_cards_can_always_be_scrolled_out_from_under_the_panel(browser, pages):
    pg = open_page(browser, pages / "own.html", w=1400, h=900)
    sw = lambda: pg.evaluate("(()=>{const c=document.getElementById('canvas');return c.scrollWidth-c.clientWidth})()")
    before = sw()
    pg.click("#notes-toggle"); pg.wait_for_timeout(500)
    pg.click("#fw-seg button[data-m=fw]"); pg.wait_for_timeout(500)
    assert sw() > before + 300


def test_back_button_stays_put_and_clear_of_the_widest_panel(browser, pages):
    pg = open_page(browser, pages / "own.html", w=1400, h=900)
    pg.evaluate("showDetail('node','offer')"); pg.wait_for_timeout(700)
    a = pg.evaluate(RECTS)["desk-back"]
    pg.click("#notes-toggle"); pg.wait_for_timeout(500)
    pg.click("#fw-seg button[data-m=fw]"); pg.wait_for_timeout(500)
    pg.evaluate("document.getElementById('fw-resize').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowLeft'}))")
    for _ in range(40):
        pg.evaluate("document.getElementById('fw-resize').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowLeft'}))")
    pg.wait_for_timeout(500)
    b = pg.evaluate(RECTS)
    assert b["desk-back"] == a and b["desk-back"]["r"] < pg.evaluate("document.getElementById('notes-panel').getBoundingClientRect().left") - 20
    pg.click("#desk-back"); pg.wait_for_timeout(500)
    assert not pg.evaluate("document.documentElement.classList.contains('detail-open')")
