"""The New tile is exactly as wide and as tall as the tiles beside it, also when it wraps alone onto a new row (Luke 2026-11-12:
"make sure new buttons are all equal in size and not squeezed if on a new row").

Browser (WebKit; skipped without Playwright): Classic, Retro and Holographic at 402x874, 874x292, 1000x520 and 1440x900. For each, a tile
count is searched that leaves the New tile alone on its row (where the grid has two or more columns); width and height are then compared with
every other tile in the grid to within half a pixel."""
import http.server
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import holo, pages, retro            # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

LONE = []        # (style, size) cases that really put the New tile alone on a wrapped row


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("ntsite")
    (d / "h.html").write_text(pages.build_home([]), encoding="utf-8")
    (d / "holo").mkdir()
    (d / "retro").mkdir()
    name, text = holo.holo_asset()
    (d / "holo" / name).write_text(text, encoding="utf-8")
    name, text = retro.retro_asset()
    (d / "retro" / name).write_text(text, encoding="utf-8")

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(d), **k)

        def log_message(self, *a):
            pass
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


@pytest.fixture(scope="module")
def browser():
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception as e:
            pytest.skip(f"no webkit: {e}")
        yield b
        b.close()


def _pages(n):
    return [{"key": "k%d" % i, "project": "Project", "title": "Tile number %d" % i, "heading": "Tile number %d" % i, "tid": "t%d" % i,
             "added": 1.7e12 - i, "viewedAt": 1.7e12 - i, "fmt": "timeline", "units": [{"label": "U", "color": "#7c5cff"}]} for i in range(n)]


MEASURE = """()=>{const g=document.querySelector('.private-group .course-grid'); if(!g) return null;
  const t=[...g.children].filter(e=>e.classList.contains('course-tile'));
  const r=t.map(e=>{const b=e.getBoundingClientRect();return {nt:e.classList.contains('new-tile'),l:b.left,t:b.top,w:b.width,h:b.height}});
  const rows=new Set(r.map(x=>Math.round(x.t))).size, cols=new Set(r.map(x=>Math.round(x.l))).size;
  const nt=r.find(x=>x.nt); const alone=nt? r.filter(x=>Math.abs(x.t-nt.t)<2).length===1 : false;
  return {r, rows, cols, alone}}"""


def _open(browser, site, style, size, n):
    pg = browser.new_page(viewport={"width": size[0], "height": size[1]})
    pg.add_init_script("try{localStorage.setItem('alto-bg-home-v1-style','%s');localStorage.removeItem('alto-home-view-v1')}catch(e){}" % style)
    pg.goto(f"{site}/h.html")
    pg.wait_for_timeout(700)
    pg.evaluate("p=>{drawPrivate(p)}", _pages(n))
    pg.wait_for_timeout(300)
    return pg


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("size", [(402, 874), (874, 292), (1000, 520), (1440, 900)], ids=["phone-up", "phone-side", "narrow1000", "wide1440"])
def test_the_new_tile_matches_its_neighbours_also_alone_on_a_row(browser, site, style, size):
    pg = _open(browser, site, style, size, 3)
    try:
        m = pg.evaluate(MEASURE)
        cols = m["cols"]
        n = 3
        if cols > 1:                                     # find a count that leaves the New tile alone on its last row
            for n in range(1, 3 * cols + 1):
                pg.evaluate("p=>{drawPrivate(p)}", _pages(n))
                pg.wait_for_timeout(120)
                m = pg.evaluate(MEASURE)
                if m["alone"] and m["rows"] > 1:
                    LONE.append((style, size))
                    break
        else:
            assert m["rows"] >= 2                        # one column: every tile is on its own row
        if cols > 1:
            assert m["alone"] and m["rows"] > 1, ("no lone-wrap count found", style, size, cols)
        tiles = m["r"]
        new = [x for x in tiles if x["nt"]]
        others = [x for x in tiles if not x["nt"]]
        assert len(new) == 1 and others, m
        for o in others:
            assert abs(o["w"] - new[0]["w"]) <= 0.5, ("width", style, size, n, new[0], o)
            assert abs(o["h"] - new[0]["h"]) <= 0.5, ("height", style, size, n, new[0], o)
    finally:
        pg.close()


def test_a_lone_wrapped_new_tile_was_really_tested():
    if pw is None:
        pytest.skip("Playwright is not installed")
    assert len(LONE) >= 6, LONE
