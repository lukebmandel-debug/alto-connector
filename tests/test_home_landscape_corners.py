"""Phone audit B15: on the homepage held sideways every corner control is the same 44 pt on one baseline with 8 pt between neighbours, and opaque in Classic
(the moon and the download-everything button were 28 pt, the download one overlapped the account tile). Runs as an iPhone in WebKit."""
import http.server
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from alto.build import palace_assets            # noqa: E402
from alto.build.pages import build_home         # noqa: E402
from alto.hosted import hosted_home             # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

HOME = {"name": "Law School", "pid": "p", "courses": [{"title": t, "href": f"t{i}.html", "sub": "3 units", "courseId": f"c{i}", "units": []} for i, t in enumerate(["Contracts I", "Torts", "Civil Procedure"])]}


@pytest.fixture(scope="module")
def env():
    if pw is None:
        pytest.skip("Playwright is not installed")
    page = hosted_home(build_home([HOME]))

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            p = self.path.split("?")[0]
            hit = ("text/html", page) if p == "/h.html" else ("text/javascript", "") if p == "/alto-cloud.js" else palace_assets.find(p)
            body = (hit[1] if hit else "no").encode("utf-8")
            self.send_response(200 if hit else 404)
            self.send_header("Content-Type", hit[0] if hit else "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception as e:
            pytest.skip(f"no webkit: {e}")
        dev = dict(p.devices["iPhone 13"])
        dev.pop("default_browser_type", None)
        yield f"http://127.0.0.1:{srv.server_address[1]}/h.html", b, dev
        b.close()
    srv.shutdown()
    srv.server_close()


_J = """() => ['account-btn', 'download-all', 'search-btn', 'info-btn', 'mode-toggle'].map(i => { const e = document.getElementById(i); if(!e) return null;
  const r = e.getBoundingClientRect(); if(!r.width) return null; const m = getComputedStyle(e).backgroundColor.match(/[\\d.]+/g);
  return {id: i, l: r.left, r: r.right, t: r.top, w: r.width, h: r.height, a: m.length > 3 ? +m[3] : 1}; }).filter(Boolean)"""


@pytest.mark.parametrize("look", ["classic", "retro", "holo"])
@pytest.mark.parametrize("size", [(844, 390), (932, 430)])
def test_corner_controls_are_one_size_on_one_baseline(env, look, size):
    url, b, dev = env
    ctx = b.new_context(**{**dev, "viewport": {"width": size[0], "height": size[1]}})
    pg = ctx.new_page()
    try:
        pg.goto(url, wait_until="load")
        pg.wait_for_timeout(1500)
        if look != "classic":
            pg.evaluate(f"window._altoStyle.set('{look}')")
            pg.wait_for_timeout(1500)
        rows = pg.evaluate(_J)
        assert {r["id"] for r in rows} >= {"account-btn", "download-all", "search-btn", "info-btn"}
        for r in rows:
            assert abs(r["w"] - 44) <= .6 and abs(r["h"] - 44) <= .6, r
            assert abs(r["t"] - rows[0]["t"]) <= .6, r
        rows.sort(key=lambda r: r["l"])
        for a, c in zip(rows, rows[1:]):
            assert c["l"] - a["r"] >= 7.5, (a, c)
        if look == "classic":
            assert all(r["a"] >= .94 for r in rows), [(r["id"], r["a"]) for r in rows]
    finally:
        ctx.close()
