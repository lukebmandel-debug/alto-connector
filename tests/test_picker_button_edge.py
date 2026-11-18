"""The round background-picker button (#bg-toggle) keeps at least 20 screen px from every edge of the window (its bounding box; its soft glow is not a ring) on Reports, the
homepage, an outline and a timeline, in Holographic and in Retro, at 1000 and 1440 wide (cleanup-241, Board B-1118-LOOK242: it ran to the edge on Reports in Holographic and sat 17 px in on a timeline)."""
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from alto.build import backgrounds_import as bi, holo, pages, retro                    # noqa: E402
from alto.build.builder import build_timeline, load_brief                              # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None


def _tl(name):
    br, n, c = load_brief(json.loads((ROOT / "samples" / f"{name}_brief.json").read_text(encoding="utf-8")))
    return build_timeline(br, n, c)[0]


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("edgesite")
    for k, v in {"reports": pages.build_reports([], "x"), "home": pages.build_home([]), "outline": _tl("outline"), "timeline": _tl("contracts")}.items():
        (d / f"{k}.html").write_text(v, encoding="utf-8")
    for sub, (name, text) in (("retro", retro.retro_asset()), ("holo", holo.holo_asset())):
        (d / sub).mkdir()
        (d / sub / name).write_text(text, encoding="utf-8")
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
@pytest.mark.parametrize("style", ["holo", "retro"])
@pytest.mark.parametrize("page", ["reports", "home", "outline", "timeline"])
@pytest.mark.parametrize("w,h", [(1000, 760), (1440, 900)])
def test_the_picker_button_keeps_20px_from_every_edge(base, engine, style, page, w, h):
    with pw.sync_playwright() as p:
        try:
            br = getattr(p, engine).launch()
        except Exception as e:
            pytest.skip(f"no {engine}: {e}")
        pg = br.new_context(viewport={"width": w, "height": h}).new_page()
        pg.goto(f"{base}/{page}.html")
        key = pg.evaluate("window._altoBg.key")
        pg.evaluate("([k, s]) => { localStorage.setItem(/-bg$/.test(k) ? k.replace(/-bg$/, '-style') : k + '-style', s); localStorage.setItem(k, JSON.stringify({v: 'h-neon-rain', t: Date.now()})); }", [key, style])
        pg.reload()
        pg.wait_for_timeout(1800)
        assert pg.evaluate(f"document.documentElement.classList.contains('alto-{style}')")
        r = pg.evaluate("() => { const b = document.getElementById('bg-toggle').getBoundingClientRect(); return {l: b.left, t: b.top, r: innerWidth - b.right, b: innerHeight - b.bottom}; }")
        br.close()
    for side in ("l", "t", "r", "b"):
        assert r[side] >= 19.5, (page, style, w, side, r)
