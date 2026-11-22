"""Retro's bottom-right cluster at laptop widths (Board B-1121-LOOK-SIDETOGGLES-R2). WebKit, Retro, lanes page at 1280, 1440, 1680 and 2000 wide: every bottom-right
control (search, list, info, the star/edit pill) lies fully inside the viewport with at least 20 px to the right edge, and each paints a visible left AND right rim
(the pill's rim was a 1px spread shadow, which the 0.85 page zoom reduced below one device pixel: its side borders vanished at 1280 and 1440)."""
import http.server
import io
import json
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from alto.build import palace_assets            # noqa: E402
from alto.build.builder import build_timeline, load_brief       # noqa: E402

try:
    import playwright.sync_api as pw
    from PIL import Image
except ImportError:
    pw = None

IDS = ["search-btn", "info-btn", "key-toggle", "alto-edit-pill"]
READ = "(ids)=>ids.map(i=>{const e=document.getElementById(i);if(!e)return null;const b=e.getBoundingClientRect();return [i,b.left,b.top,b.right,b.bottom,innerWidth]})"


@pytest.fixture(scope="module")
def base():
    page = build_timeline(*load_brief(json.load(open(ROOT / "samples/lanes_v2_brief.json"))))[0]

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(s, *a):
            pass

        def do_GET(s):
            p = s.path.split("?")[0]
            hit = ("text/html", page) if p.endswith(".html") else ("text/javascript", "") if p == "/alto-cloud.js" else palace_assets.find(p)
            body = (hit[1] if hit else "no").encode()
            s.send_response(200 if hit else 404)
            s.send_header("Content-Type", hit[0] if hit else "text/plain")
            s.send_header("Content-Length", str(len(body)))
            s.end_headers()
            s.wfile.write(body)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.mark.skipif(pw is None, reason="playwright/PIL not installed")
@pytest.mark.parametrize("style,widths", [("retro", [1280, 1440, 1680, 2000]), ("classic", [1440]), ("holo", [1440])])
def test_corner_cluster_inside_viewport_with_both_rims(base, style, widths):
    with pw.sync_playwright() as p:
        try:
            br = p.webkit.launch()
        except Exception as e:      # pragma: no cover
            pytest.skip(f"no WebKit: {e}")
        for w in widths:
            cx = br.new_context(viewport={"width": w, "height": int(w * .625)})
            pg = cx.new_page()
            pg.goto(base + "/lanes.html")
            pg.wait_for_timeout(1800)
            pg.evaluate("document.documentElement.classList.add('dark')")
            pg.evaluate("window._altoStyle&&window._altoStyle.set(%r)" % style)
            pg.wait_for_timeout(1000)
            rects = [r for r in pg.evaluate(READ, IDS) if r]
            assert len(rects) == 4, (style, w, rects)
            im = Image.open(io.BytesIO(pg.screenshot())).convert("RGB")
            for i, l, t, r, b, iw in rects:
                assert r <= iw - 20 and l >= 0, (style, w, i, l, r, iw)
                if style != "retro":        # Classic/Holo rims are glass: only the geometry is held
                    continue
                y = int((t + b) / 2)
                for side, x in (("left", round(l)), ("right", round(r))):
                    seen = max(sum(im.getpixel((max(0, min(w - 1, x + k)), y))) for k in (-2, -1, 0, 1))
                    assert seen > 150, (style, w, i, side, "rim not painted")
            cx.close()
        br.close()
