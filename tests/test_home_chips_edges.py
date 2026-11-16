"""Home chips on the panel edges (14 Nov, L-1114-chips): the Private chip is flush with the first project panel's LEFT edge, the sort chip with its
RIGHT edge, in every style, dark and light, at every width, after a resize; a phone keeps 44 pt targets, 20 px from the screen edge, clear of the HOME row.
Also L-1114-count: no project count beside a project name in any style, and the rename pencil sits as in Classic."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_home_label_b import _hit, _open, _pages, _shared, site  # noqa: E402,F401  (fixtures reused)

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None


@pytest.fixture(scope="module", params=["webkit", "chromium"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


EDGES = """()=>{const r=e=>e&&e.getBoundingClientRect();
  const slab=document.querySelector('.slab-group:not(.hr-off) .project-slab:not(.new-project-slab)');
  const L=document.querySelector('#home-row .hr-switch, #home-row .hr-plain'), R=document.querySelector('#home-row .home-sort');
  const T=document.getElementById('title-bar'), bs=[...document.querySelectorAll('#home-row .hr-chip')];
  const o=x=>x&&{l:x.left,r:x.right,t:x.top,b:x.bottom,w:x.width,h:x.height};
  const top=[...document.querySelectorAll('#search-btn,#bin-btn,#info-btn,#mode-toggle,#bg-toggle,#m-search,#account-btn,#title-bar')].filter(e=>getComputedStyle(e).display!=='none'&&e.getBoundingClientRect().width).map(e=>[e.id,o(r(e))]);
  return {slab:o(r(slab)),L:o(r(L)),R:o(r(R)),btn:bs.map(b=>o(r(b))),top,vw:innerWidth}}"""
SIZES = [(1440, 900), (1280, 800), (1024, 768), (390, 844), (844, 390)]


def _check(pg, size):
    e = pg.evaluate(EDGES)
    s, L, R = e["slab"], e["L"], e["R"]
    assert abs(L["l"] - s["l"]) <= 1, ("left chip edge", L, s)
    assert abs(R["r"] - s["r"]) <= 1, ("right chip edge", R, s)
    phone = size[0] <= 640 or size[1] <= 500
    if phone:
        assert all(b["h"] >= 43.5 for b in e["btn"]), e["btn"]
        assert L["l"] >= 20 - 1 and e["vw"] - R["r"] >= 20 - 1, ("20px from the screen edge", L, R, e["vw"])
        for name, v in e["top"]:
            for b in e["btn"]:
                assert not _hit(b, v), ("overlaps the HOME row", name, b, v)
    return e


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("size", SIZES, ids=lambda s: "%dx%d" % s)
@pytest.mark.parametrize("shared", [True, False], ids=["switch", "plain"])
def test_chips_sit_on_the_panel_edges(browser, site, style, dark, size, shared):
    pg = _open(browser, site, style, dark, size, shared=shared)
    try:
        _check(pg, size)
    finally:
        pg.close()


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_chips_follow_the_panel_after_a_resize(browser, site, style):
    pg = _open(browser, site, style, False, (1440, 900), shared=True)
    try:
        for size in [(1100, 800), (700, 800), (390, 844), (1280, 800), (844, 390)]:
            pg.set_viewport_size({"width": size[0], "height": size[1]})
            pg.wait_for_timeout(300)
            _check(pg, size)
    finally:
        pg.close()


NAMES = """()=>[...document.querySelectorAll('.project-slab:not(.new-project-slab) .slab-kicker')].map(k=>({
  txt:k.textContent.trim(), kids:[...k.children].map(c=>c.className), hasCount:!!k.querySelector('.slab-count'),
  pen:(()=>{const p=k.querySelector('.slab-rename');if(!p)return null;const kr=k.getBoundingClientRect(),pr=p.getBoundingClientRect();
    const rg=document.createRange();rg.selectNodeContents(k.firstChild);const tr=rg.getBoundingClientRect();return {gap:Math.round(pr.left-tr.right),dy:Math.round((pr.top+pr.bottom)/2-(tr.top+tr.bottom)/2)}})()}))"""


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("size", [(1440, 900), (390, 844)], ids=["desktop", "phone"])
def test_no_project_count_in_any_style_and_the_pencil_matches_classic(browser, site, dark, size):
    got = {}
    for style in ["classic", "retro", "holo"]:
        pg = _open(browser, site, style, dark, size, shared=False)
        try:
            pg.wait_for_timeout(400)
            assert pg.locator(".slab-count").count() == 0, style
            got[style] = pg.evaluate(NAMES)
        finally:
            pg.close()
    for style, rows in got.items():
        assert rows and all(not r["hasCount"] for r in rows), style
        assert all(r["txt"] in ("Project 0", "Project 1", "Project 2") for r in rows), (style, rows)   # name only: no number
        assert [r["kids"] for r in rows] == [r["kids"] for r in got["classic"]], (style, rows)           # same children as Classic
