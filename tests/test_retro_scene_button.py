"""Retro's Scene button (#bg-toggle) sits at least 20 screen px in from the window edge: the homepage's button and the timeline rail's,
at a 1000 and a 1440 window, and the homepage's phone tile at 390 (cleanup-241 item 1; was flush on the right edge at 0 px)."""
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from alto.build import backgrounds_import as bi, pages, retro                      # noqa: E402
from alto.build.builder import build_timeline, load_brief                          # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

_RECT = """() => {const e = document.getElementById('bg-toggle'); const b = e.getBoundingClientRect();
  return {retro: document.documentElement.classList.contains('alto-retro'), l: b.left, t: b.top, r: innerWidth - b.right, b: innerHeight - b.bottom}}"""


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("scenebtn")
    (d / "home.html").write_text(pages.build_home([]), encoding="utf-8")
    brief, nodes, conns = load_brief(json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8")))
    (d / "t.html").write_text(build_timeline(brief, nodes, conns)[0], encoding="utf-8")
    (d / "retro").mkdir()
    name, text = retro.retro_asset()
    (d / "retro" / name).write_text(text, encoding="utf-8")
    lib, js = bi.site_file()
    (d / lib).write_text(js, encoding="utf-8")

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


@pytest.mark.parametrize("engine", ["webkit", "chromium"])
@pytest.mark.parametrize("page,w,h", [("home", 1000, 760), ("home", 1440, 900), ("home", 390, 844), ("t", 1000, 760), ("t", 1440, 900)])
def test_the_retro_scene_button_keeps_20px_from_every_edge(base, engine, page, w, h):
    with pw.sync_playwright() as p:
        try:
            br = getattr(p, engine).launch()
        except Exception as e:
            pytest.skip(f"no {engine}: {e}")
        pg = br.new_context(viewport={"width": w, "height": h}).new_page()
        pg.add_init_script("localStorage.setItem('alto-bg-home-v1-style','retro');localStorage.setItem('alto-hl-contracts-outline-style','retro')")
        pg.goto(f"{base}/{page}.html")
        pg.wait_for_timeout(1200)
        r = pg.evaluate(_RECT)
        br.close()
    assert r["retro"], "Retro did not load"
    for side in ("l", "t", "r", "b"):
        assert r[side] >= 19.5, (page, w, side, r)
