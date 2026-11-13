"""The homepage's bottom-right row moves as one when the Alto guide (info) opens (Luke 2026-11-12: "info button is not pushing trash button
with search button when opening"). The cause: opening the guide slid the search pill aside by script, button by button, and the bin was never in
that list. Now one CSS rule (html.info-open) slides everything left of the info circle.

Browser (WebKit, and Chrome where it is installed; skipped without Playwright): Classic, Retro and Holographic, light and dark, a computer at 1000
and 1440 wide, a phone upright and sideways. Open the guide, close it, open it while search is open: the row moved together, nothing overlaps."""
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


def test_the_row_slides_by_one_rule_not_button_by_button():
    p = pages.build_home([])
    assert "html.info-open #search-btn, html.info-open #bin-btn{ transform:translateX(-324px); }" in p
    assert "slideAside(" not in p
    assert "classList.toggle('info-open', expanded)" in p


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("irsite")
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


@pytest.fixture(params=["webkit", "chromium"], scope="module")
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch() if request.param == "webkit" else p.chromium.launch(channel="chrome")
        except Exception as e:
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


IDS = ["search-btn", "bin-btn", "info-btn", "mode-toggle"]
RECTS = """()=>{const o={};for(const id of %s){const e=document.getElementById(id);if(!e){continue;}
  const s=getComputedStyle(e);if(s.display==='none'||s.visibility==='hidden')continue;
  const r=e.getBoundingClientRect();o[id]={l:r.left,t:r.top,r:r.right,b:r.bottom};}
  const c=document.getElementById('info-content');if(c){const r=c.getBoundingClientRect();o.guide={l:r.left,t:r.top,r:r.right,b:r.bottom};}
  return o}""" % IDS
BIN = """()=>{if(document.getElementById('bin-btn'))return;const g=document.createElement('div');g.id='bin-corner';
  const b=document.createElement('button');b.id='bin-btn';b.type='button';b.textContent='';g.appendChild(b);document.body.appendChild(g);alignSearch();}"""


def _hit(a, b):
    return a["l"] < b["r"] - 0.5 and b["l"] < a["r"] - 0.5 and a["t"] < b["b"] - 0.5 and b["t"] < a["b"] - 0.5


def _open(browser, site, style, dark, size):
    pg = browser.new_page(viewport={"width": size[0], "height": size[1]})
    pg.add_init_script("try{localStorage.setItem('alto-bg-home-v1-style','%s')}catch(e){}" % style)
    pg.goto(f"{site}/h.html")
    pg.wait_for_timeout(800)
    pg.evaluate("d=>document.documentElement.classList.toggle('dark', d)", dark)
    pg.evaluate(BIN)
    pg.wait_for_timeout(300)
    return pg


def _toggle_info(pg, want):
    now = pg.evaluate("document.getElementById('info-btn').classList.contains('expanded')")
    if now != want:
        pg.evaluate("toggleInfo()")
    pg.wait_for_timeout(400)
    pg.wait_for_function("document.getAnimations().filter(a => a.effect && a.effect.target && ['search-btn','bin-btn','info-btn'].includes(a.effect.target.id) && a.playState === 'running').length === 0", timeout=8000)      # slides and the box's growth are done


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("size", [(1000, 700), (1440, 800), (390, 844), (844, 390)], ids=["narrow1000", "wide1440", "phone-up", "phone-side"])
def test_the_corner_row_moves_as_one(browser, site, style, dark, size):
    pg = _open(browser, site, style, dark, size)
    try:
        shut = pg.evaluate(RECTS)
        assert {"search-btn", "bin-btn", "info-btn"} <= set(shut)
        row = [k for k in shut if k != "guide"]
        for i, a in enumerate(row):
            for b in row[i + 1:]:
                assert not _hit(shut[a], shut[b]), ("closed", a, b, shut)
        # open
        _toggle_info(pg, True)
        op = pg.evaluate(RECTS)
        assert pg.evaluate("document.documentElement.classList.contains('info-open')")
        panel = op["guide"] if size[0] <= 640 else op["info-btn"]      # a computer's guide IS the info box; a phone's drops from the tile
        moved = [k for k in ("search-btn", "bin-btn") if abs(op[k]["l"] - shut[k]["l"]) > 1]
        if size[0] > 640:
            dxs = {round(op[k]["l"] - shut[k]["l"]) for k in ("search-btn", "bin-btn")}
            assert len(dxs) == 1 and moved == ["search-btn", "bin-btn"], (dxs, moved)        # the same shift: they travel together
            assert abs(op["mode-toggle"]["l"] - shut["mode-toggle"]["l"]) < 1 if "mode-toggle" in op else True
            for k in ("search-btn", "bin-btn"):
                assert not _hit(op[k], panel), ("covered by the guide", k, op)
            assert not _hit(op["search-btn"], op["bin-btn"])
            assert op["bin-btn"]["r"] <= panel["l"] + 0.5
        else:
            assert moved == [], moved                                       # a phone's guide drops down: nothing slides
            for k in ("search-btn", "bin-btn"):
                assert not _hit(op[k], panel), ("covered by the guide", k, op)
        # close: back where it was
        _toggle_info(pg, False)
        back = pg.evaluate(RECTS)
        for k in row:
            assert abs(back[k]["l"] - shut[k]["l"]) < 1 and abs(back[k]["t"] - shut[k]["t"]) < 1, ("close", k, back[k], shut[k])
        # open it while search is open
        pg.evaluate("document.getElementById('search-glyph').click()")
        pg.wait_for_timeout(500)
        assert pg.evaluate("document.getElementById('search-btn').classList.contains('expanded')")
        _toggle_info(pg, True)
        assert not pg.evaluate("document.getElementById('search-btn').classList.contains('expanded')")      # one panel at a time
        both = pg.evaluate(RECTS)
        panel = both["guide"] if size[0] <= 640 else both["info-btn"]
        for k in ("search-btn", "bin-btn"):
            assert not _hit(both[k], panel), ("search open then info", k, both)
        if size[0] > 640:
            assert round(both["bin-btn"]["l"] - shut["bin-btn"]["l"]) == round(both["search-btn"]["l"] - shut["search-btn"]["l"])
            assert abs(both["search-btn"]["l"] - op["search-btn"]["l"]) < 1
    finally:
        pg.close()
