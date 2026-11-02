"""Line-breaks at dividers (Luke, 2026-11-01: "the break need only be as large as the dividing line/box its traversing", Retro too): in Retro and
Holographic a connector breaks only the divider's thickness + 6 px (7 px for the 1 px line) and runs behind the name chip and the numeral;
Classic keeps its tube-sized break exactly (same paths, built before and after). A phone has no river."""
from __future__ import annotations

import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from alto.build import holo, retro                                    # noqa: E402
from alto.build.builder import build_timeline, load_brief             # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

GAPS = """()=>{var s=new Set(),n=0;[...document.querySelectorAll('#river-svg path[data-edge]')].forEach(p=>{
  var re=/L (-?[\\d.]+) (-?[\\d.]+) M (-?[\\d.]+) (-?[\\d.]+)/g,m,d=p.getAttribute('d');while(m=re.exec(d)){s.add(Math.round(Math.abs(m[4]-m[2])));n++}});return {sizes:[...s],n:n,
  paths:[...document.querySelectorAll('#river-svg path[data-edge]')].map(p=>p.getAttribute('d'))}}"""


def test_the_thin_break_is_in_the_engine_and_classic_is_untouched():
    t = (ROOT / "alto" / "engine" / "timeline_template.html").read_text(encoding="utf-8")
    assert "_thinBreak" in t and "_behindABox" in t and "r.cy - 3.5" in t and "r.cy + 3.5" in t
    assert "window._unitBarYRanges.push({top:bandTop+TUBE_TOP-4, bottom:bandTop+TUBE_TOP+TUBE_H+4, cy:" in t   # Classic's own range is the same


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("divsite")
    j = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    brief, nodes, conns = load_brief(j)
    (d / "t.html").write_text(build_timeline(brief, nodes, conns)[0], encoding="utf-8")
    for sub, mod, fn in (("holo", holo, "holo_asset"), ("retro", retro, "retro_asset")):
        (d / sub).mkdir()
        name, text = getattr(mod, fn)()
        (d / sub / name).write_text(text, encoding="utf-8")

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


@pytest.fixture(params=["chromium", "webkit"])
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


def test_retro_and_holographic_break_by_the_divider_and_classic_keeps_its_own(browser, site):
    pg = browser.new_page(viewport={"width": 1400, "height": 900})
    pg.goto(site + "/t.html")
    pg.wait_for_timeout(600)
    classic = pg.evaluate(GAPS)
    assert classic["n"] > 0 and max(classic["sizes"]) >= 80, classic["sizes"]       # the tube-sized break
    for style in ("retro", "holo", "classic"):
        pg.evaluate("window._altoStyle.set('%s')" % style)
        pg.wait_for_timeout(900)
        got = pg.evaluate(GAPS)
        if style == "classic":
            assert got["paths"] == classic["paths"]                                  # exactly as it was, every path
        else:
            assert got["n"] > 0 and got["sizes"] == [7], (style, got["sizes"])       # 1 px divider + 6 px
    pg.close()


def test_a_phone_keeps_its_page(browser, site):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    pg = ctx.new_page()
    pg.goto(site + "/t.html?mobile")                      # the engine's own phone switch (html.mobile)
    pg.wait_for_timeout(500)
    assert pg.evaluate("document.documentElement.classList.contains('mobile')")
    before = pg.evaluate(GAPS)["paths"]
    pg.evaluate("window._altoStyle.set('retro')")
    pg.wait_for_timeout(700)
    assert pg.evaluate(GAPS)["paths"] == before
    ctx.close()
