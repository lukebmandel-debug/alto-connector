"""The desktop search's expand control: a large panel with more of each hit,
remembered per viewer, Esc shrinking before it closes; phones unchanged."""
import json
from pathlib import Path

import pytest

from alto.build.builder import build_timeline, load_brief
from alto.build.engine_patches import PATCHES
from alto.build.pages import build_home

ROOT = Path(__file__).resolve().parent.parent
try:
    from playwright import sync_api as pw
except ImportError:                                  # CI has no Playwright: the browser tests skip
    pw = None
needs_pw = pytest.mark.skipif(pw is None, reason="no Playwright")


@pytest.fixture(scope="module")
def html():
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    return build_timeline(*load_brief(d))[0]


HOME_EX = """window._altoExtra={private:[{key:'k1',title:'Contracts',label:'Contracts',project:'Law School',href:'c.html',search:[
 {id:'offer',t:'Offer',d:'A manifestation of willingness to enter a bargain. The offeror is the master of the offer.'}]}],shared:[]};"""


@pytest.fixture(scope="module")
def files(tmp_path_factory, html):
    d = tmp_path_factory.mktemp("sx")
    (d / "t.html").write_text(html, encoding="utf-8")
    (d / "h.html").write_text(build_home([{"name": "Law", "pid": "p", "courses": [
        {"title": "Contracts", "href": "c.html", "sub": "4 units", "courseId": "c", "units": []}]}]),
        encoding="utf-8")
    return d


def test_the_page_carries_the_expand_control(html):
    assert 'id="alto-sx"' in html and "Expand search" in html and "Collapse search" in html
    assert "alto-search-big" in html
    names = {p["name"] for p in PATCHES}
    assert {"search-expose-render", "search-esc-shrinks-first"} <= names


def test_the_homepage_carries_it_too():
    h = build_home([])
    assert "_altoSXHomeRow" in h and "window._homeSearchRender = render" in h and "alto-search-big" in h


@pytest.fixture()
def browser():
    if pw is None:
        pytest.skip("no Playwright")
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no Chromium: {e}")
        yield b
        b.close()


def open_search(pg, q):
    pg.click("#search-glyph")
    pg.wait_for_timeout(200)
    pg.keyboard.type(q)
    pg.wait_for_timeout(400)


def page_of(browser, files, name="t.html", w=1440, h=900, query=""):
    pg = browser.new_page(viewport={"width": w, "height": h})
    pg.goto(files.joinpath(name).as_uri() + query)
    pg.wait_for_timeout(900)
    return pg


STATE = """()=>{var b=document.getElementById('search-btn').getBoundingClientRect(),r=document.documentElement;
 return {big:r.classList.contains('sx-big'), open:!!window._searchOpen||document.getElementById('search-btn').classList.contains('expanded'),
         w:Math.round(b.width), saved:localStorage.getItem('alto-search-big'),
         scroll:document.scrollingElement.scrollTop, over:r.scrollHeight>innerHeight}}"""


def test_the_control_grows_and_shrinks_the_panel(browser, files):
    pg = page_of(browser, files)
    open_search(pg, "consideration")
    assert pg.get_attribute("#sx-toggle", "title") == "Expand search"
    compact = [t for t in pg.eval_on_selector_all(".search-result .sr-title", "e=>e.map(x=>x.textContent)")]
    pg.click("#sx-toggle")
    s = pg.evaluate(STATE)
    assert s["big"] and s["w"] >= 900 and s["saved"] == "1" and not s["over"] and s["scroll"] == 0
    assert pg.get_attribute("#sx-toggle", "aria-label") == "Collapse search"
    big = pg.eval_on_selector_all(".search-result .sr-title", "e=>e.map(x=>x.textContent)")
    assert big == compact                                  # same results, same order
    row = pg.query_selector(".sr-rich:has(.sr-chips)")     # a card: number, unit, full text, chips
    assert row.query_selector(".sr-num") and row.query_selector(".sr-meta") and row.query_selector(".sr-full")
    assert row.query_selector(".sr-chip")
    pg.click("#sx-toggle")
    pg.wait_for_timeout(500)                               # the width eases back
    s = pg.evaluate(STATE)
    assert not s["big"] and s["w"] < 500 and s["saved"] == "0"


def test_a_page_hit_shows_passages_and_the_card_its_whole_text(browser, files):
    pg = page_of(browser, files)
    open_search(pg, "promise")
    pg.click("#sx-toggle")
    n = pg.eval_on_selector_all(".sr-rich", "e=>e.map(x=>x.querySelectorAll('.sr-pass').length)")
    assert any(k >= 2 for k in n)                          # a page: several passages
    assert pg.eval_on_selector_all(".sr-rich .sr-pass mark, .sr-rich .sr-full mark", "e=>e.length") > 5
    full = pg.evaluate("""()=>{var o=window._altoSearch.search('promise')[0];return o.r.desc}""")
    shown = pg.eval_on_selector(".sr-rich .sr-full", "e=>e.textContent")
    assert shown.strip() == full.strip() or shown.strip() in full or full.strip() in shown.strip()


def test_esc_shrinks_first_then_closes_and_the_choice_survives(browser, files):
    pg = page_of(browser, files)
    open_search(pg, "rule")
    pg.click("#sx-toggle")
    pg.keyboard.press("Escape")
    s = pg.evaluate(STATE)
    assert s["open"] and not s["big"] and s["saved"] == "1"      # shrunk, still open, preference kept
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(200)
    s = pg.evaluate(STATE)
    assert not s["open"] and s["big"]                            # closed; the next search opens big
    pg.reload()
    pg.wait_for_timeout(900)
    open_search(pg, "rule")
    assert pg.evaluate(STATE)["big"]


def test_arrows_and_enter_work_in_both_sizes(browser, files):
    for big in (False, True):
        pg = page_of(browser, files)
        pg.evaluate(f"localStorage.setItem('alto-search-big','{1 if big else 0}')")
        pg.reload(); pg.wait_for_timeout(900)
        open_search(pg, "mailbox")
        pg.keyboard.press("ArrowDown")
        pg.keyboard.press("ArrowDown")
        pg.keyboard.press("ArrowUp")
        assert pg.evaluate("[...document.querySelectorAll('.search-result')].findIndex(e=>e.classList.contains('sx-active'))") == 0
        pg.keyboard.press("ArrowDown")
        want = pg.evaluate("document.querySelectorAll('.search-result')[1].querySelector('.sr-title').textContent")
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(900)
        assert not pg.evaluate("document.getElementById('search-btn').classList.contains('expanded')")
        landed = pg.evaluate("!!window._focusedNodeId || document.getElementById('detail-page').classList.contains('visible')")
        assert landed, f"nothing opened for {want!r}"
        pg.close()


def test_the_panel_sits_over_the_chrome_and_never_scrolls_the_page(browser, files):
    for w, h in ((1440, 900), (1280, 800)):
        pg = page_of(browser, files, w=w, h=h)
        pg.evaluate("localStorage.setItem('alto-search-big','1')")
        pg.reload(); pg.wait_for_timeout(900)
        pg.evaluate("window.enterFocus && enterFocus('offer')"); pg.wait_for_timeout(500)
        open_search(pg, "the")
        r = pg.evaluate("""()=>{var b=document.getElementById('search-btn').getBoundingClientRect(),
          s=document.getElementById('search-results').getBoundingClientRect();
          var top=document.elementFromPoint(b.left+b.width/2,b.top+10), rail=document.getElementById('tab-rail');
          return {l:b.left,r:b.right,t:b.top,bot:s.bottom,vw:innerWidth,vh:innerHeight,onTop:!!top.closest('#search-btn'),
                  z:+getComputedStyle(document.getElementById('search-btn')).zIndex,over:document.documentElement.scrollHeight>innerHeight}}""")
        assert r["l"] >= 0 and r["r"] <= r["vw"] and abs((r["l"] + r["r"]) / 2 - r["vw"] / 2) < 2
        assert r["t"] >= 60 and r["bot"] <= r["vh"] * 0.97 and r["onTop"] and r["z"] > 400 and not r["over"]
        pg.mouse.wheel(0, 600)
        assert pg.evaluate("document.scrollingElement.scrollTop") == 0
        pg.close()


def test_a_phone_has_no_expand_control(browser, files):
    pg = browser.new_page(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    pg.goto((files / "t.html").as_uri() + "?mobile")
    pg.wait_for_timeout(1200)
    assert pg.evaluate("document.documentElement.classList.contains('mobile')")
    assert pg.query_selector("#sx-toggle") is None
    assert not pg.evaluate("document.documentElement.classList.contains('sx-big')")


def test_the_homepage_expands_too(browser, files):
    pg = page_of(browser, files, "h.html")
    pg.evaluate(HOME_EX)
    open_search(pg, "offer")
    pg.click("#sx-toggle")
    s = pg.evaluate(STATE)
    assert s["big"] and s["w"] >= 900 and not s["over"]
    row = pg.query_selector(".sr-rich")
    assert row and "master of the" in row.inner_text() and row.query_selector(".sr-meta").inner_text() == "Law School"
    assert row.query_selector("mark")
    pg.keyboard.press("Escape")
    assert pg.evaluate(STATE)["open"] and not pg.evaluate(STATE)["big"]
    pg.keyboard.press("Escape")
    assert not pg.evaluate(STATE)["open"]


def test_search_stays_fast_on_a_big_timeline(browser, files):
    pg = page_of(browser, files)
    ms = pg.evaluate("""()=>{var S=window._altoSearch, idx=S.build(), base=idx.slice();
      for(var k=0;k<20;k++) base.forEach(function(r){ idx.push(r); });
      document.documentElement.classList.add('sx-big');
      var t=performance.now();
      ['c','co','con','cons','consid','consideration','the','offer','a bargained exchange'].forEach(function(q){ S.rowsHtml(S.search(q),'data-i'); });
      return (performance.now()-t)/9;}""")
    assert ms < 120, ms
