"""The timeline's right-end phase badges (the Roman or plain unit chips) end at least 20px clear of the Alto wordmark and the side rail, in Classic,
Retro and Holographic, at 1440 and 1000 wide (Board B-1118-UNITNUM-ART: in 1.9.243's shots badge I sat under the logo and II under the Notes rail).
Checked by x alone, so it holds wherever the board is scrolled to (the logo and rail are fixed; the chips ride the board)."""
import http.server
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import test_unit_numbers as T   # noqa: E402

pw = T.pw


@pytest.fixture(scope="module")
def site():
    if pw is None:
        pytest.skip("Playwright is not installed")
    T.PAGES["timeline"] = T._page("contracts")

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            p = self.path.split("?")[0]
            n = p.strip("/").removesuffix(".html")
            hit = (("text/html", T.PAGES[n]) if p.endswith(".html") and n in T.PAGES
                   else ("text/javascript", "") if p == "/alto-cloud.js" else T.palace_assets.find(p))
            b = hit[1] if hit else "no"
            b = b if isinstance(b, bytes) else b.encode()
            self.send_response(200 if hit else 404)
            self.send_header("Content-Type", hit[0] if hit else "text/plain")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


JS = """() => { const R = e => { const b = e.getBoundingClientRect(); return {l: b.left, r: b.right, w: b.width}; };
  return {chips: [...document.querySelectorAll('.phase-numeral')].map(R),
          obs: ['#title-bar .brand-word', '#tab-rail'].map(q => { const e = document.querySelector(q); return e ? Object.assign({q}, R(e)) : {q, w: 0}; })}; }"""


@pytest.mark.parametrize("w", [1440, 1000])
@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_no_phase_badge_comes_within_20px_of_the_logo_or_the_rail(site, style, w):
    with pw.sync_playwright() as p:
        b = p.webkit.launch()
        pg = b.new_page(viewport={"width": w, "height": 900})
        pg.goto(f"{site}/timeline.html")
        pg.wait_for_timeout(300)
        if style != "classic":
            pg.evaluate("localStorage.clear(); window._altoStyle.set('%s')" % style)
            pg.wait_for_timeout(1200)
        pg.reload()
        pg.wait_for_timeout(2200)
        d = pg.evaluate(JS)
        b.close()
    assert len(d["chips"]) >= 2 and any(o["w"] for o in d["obs"]), d
    for c in d["chips"]:
        for o in d["obs"]:
            if o["w"]:
                assert c["r"] <= o["l"] - 20 + 0.5, (style, w, c, o)
